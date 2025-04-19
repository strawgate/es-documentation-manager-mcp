from __future__ import annotations
from uuid import uuid4
import yaml
import urllib.parse
from typing import TYPE_CHECKING, List, Dict, Any
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


from es_knowledge_base_mcp.clients import docker as docker_utils
from es_knowledge_base_mcp.clients.docker import InjectFile
from es_knowledge_base_mcp.models.errors import CrawlerError


from fastmcp.utilities.logging import get_logger

from es_knowledge_base_mcp.models.settings import CrawlerSettings

if TYPE_CHECKING:
    from es_knowledge_base_mcp.models.settings import ElasticsearchSettings

logger = get_logger("knowledge-base-mcp.crawl")

# endregion Crawler Settings


class Crawler:
    """Handles the logic for crawling websites using Docker."""

    docker_socket: str | None

    docker_client: Docker

    settings: CrawlerSettings

    # Container Label used to identify containers managed by this component
    MANAGED_BY_LABEL = "managed-by"
    MANAGED_BY_VALUE = "mcp-crawler"

    DOMAIN_LABEL = "crawl-domain"
    CONFIG_FILENAME = "crawl.yml"

    def __init__(
        self,
        settings: CrawlerSettings,
        elasticsearch_settings: ElasticsearchSettings,
    ):
        """Initializes the Crawler component."""

        self.elasticsearch_settings = elasticsearch_settings

        self.settings = settings
        self.docker_socket = settings.docker_socket

        logger.debug("Crawler component initialized with settings: %s", self.settings)

    async def async_init(self) -> None:
        """Initializes the Docker client for the crawler."""
        logger.debug("Initializing Docker client for Crawler...")

        try:
            self.docker_client = Docker(url=self.docker_socket)
        except DockerError as e:
            logger.error("Failed to initialize Docker client: %s", e)
            raise CrawlerError(f"Failed to initialize Docker client: {e}") from e

        logger.debug("Docker client initialized.")

    async def async_shutdown(self) -> None:
        """Cleans up the Docker client for the crawler."""
        try:
            await self.docker_client.close()
        except Exception as e:
            logger.error("Failed to close Docker client: %s", e)
            raise CrawlerError(f"Failed to close Docker client: {e}") from e

    # region Prepare Config
    async def _prepare_crawl_config_file(
        self, domain: str, seed_url: str, filter_pattern: str, elasticsearch_index_name: str
    ) -> InjectFile:
        """
        Generates the crawler configuration content (as YAML) in memory.

        Returns:
            InjectFile: An object containing the generated config content and target path within the container.
        """

        config = {
            "domains": [
                {
                    "url": domain,
                    "seed_urls": [seed_url],
                    "crawl_rules": [
                        {"policy": "allow", "type": "begins", "pattern": filter_pattern},
                        {"policy": "deny", "type": "regex", "pattern": ".*"},
                    ],
                }
            ],
            "output_sink": "elasticsearch",
            "output_index": elasticsearch_index_name,
            "elasticsearch": {
                **self.elasticsearch_settings.to_crawler_settings(),
            },
        }

        config_container_path = "/config/" + self.CONFIG_FILENAME

        return InjectFile(filename=config_container_path, content=yaml.dump(config, indent=2))

    # endregion Prepare Config

    def derive_crawl_params(self, url: str) -> Dict[str, str]:
        """Derives crawl parameters using a heuristic based on the URL. Intelligently determine
        the right parameters to use based on the URL provided:
        1. If the url has a file extension, we assume it's a file. We then crawl everything that matches the url
            up to the last `/` character.
        2. If the url doesn't have a file extension, we assume it's a directory. We then crawl everything url
            starts with the url provided.

        Args:
            url: The URL to process.

        Returns:
            A dictionary containing "page_url", "domain", "filter_pattern", and "elasticsearch_index_name".
        """

        parsed = urllib.parse.urlparse(url)

        path = parsed.path
        filter_pattern = path

        # if end of the url is a file, we need to crawl everything that matches the url up to the last `/` character
        if not path.endswith("/") and "." in path.split("/")[-1]:
            filter_pattern = path[: path.rfind("/") + 1] or "/"

        return {
            "seed_url": url,
            "domain": parsed.scheme + "://" + parsed.netloc,
            "filter_pattern": filter_pattern,
        }

    # endregion Crawl Parameters

    # region Image Handling
    async def pull_crawler_image(self) -> None:
        """Pulls the configured crawler Docker image."""
        image_name = self.settings.docker_image

        await docker_utils.pull_image(self.docker_client, image_name)

    # endregion Image Handling

    # region Start Crawl

    async def crawl_domain(
        self,
        domain: str,
        seed_url: str,
        filter_pattern: str,
        elasticsearch_index_name: str,
    ) -> str:
        """
        Starts a crawl job asynchronously by launching a container.

        Args:
            domain (str): The domain to crawl.
            seed_url (str): The seed URL to start the crawl from.
            filter_pattern (str): The filter pattern for the crawl.
            elasticsearch_index_name (str): The suffix for the output index name.

        Returns:
            str: The ID of the started container.

        Example:
            >>> crawl_domain("http://example.com", "http://example.com/start", "/filter", "example_com")
            "container_id_123456"
        """

        logger.debug(f"Attempting to start crawl for domain '{domain}' -> index '{elasticsearch_index_name}'")

        config_file_to_inject = await self._prepare_crawl_config_file(domain, seed_url, filter_pattern, elasticsearch_index_name)

        random_id = uuid4().hex[:8]
        try:
            container_id = await docker_utils.start_container_with_files(
                docker_client=self.docker_client,
                container_name=f"mcp-crawler-{elasticsearch_index_name}-{random_id}",
                image_name=self.settings.docker_image,
                command=["ruby", "bin/crawler", "crawl", config_file_to_inject.filename],
                files_to_inject=[config_file_to_inject],
                labels={
                    self.MANAGED_BY_LABEL: self.MANAGED_BY_VALUE,
                    self.DOMAIN_LABEL: domain,
                },
            )

            logger.info(f"Started crawl for domain '{domain}' -> index '{elasticsearch_index_name}' with container ID '{container_id}'")

            return container_id

        except (DockerError, RuntimeError) as e:
            raise CrawlerError(f"Failed to start crawler for domain '{domain}': {e}") from e

    # endregion Crawl

    # region Manage Crawls
    async def list_crawls(self) -> List[Dict[str, Any]]:
        """Lists all containers managed by this crawler component."""
        label_filter = f"{self.MANAGED_BY_LABEL}={self.MANAGED_BY_VALUE}"

        return await docker_utils.get_containers_details(self.docker_client, label_filter)

    async def get_crawl_logs(self, container_id: str) -> str:
        """Gets logs for a specific crawl container.

        Args:
            container_id (str): The ID of the container to retrieve logs for."""

        return await docker_utils.container_logs(self.docker_client, container_id)

    async def stop_crawl(self, container_id: str) -> None:
        """Stops and removes a specific crawl container.

        Args:
            container_id (str): The ID of the container to stop and remove.
        """
        await docker_utils.remove_container(self.docker_client, container_id)

    # endregion Manage Crawls

    # region Cleanup

    async def remove_completed_crawls(self) -> Dict[str, Any]:
        """
        Removes all completed (exited) crawl containers managed by this component.
        Returns a summary of the operation.
        """
        logger.info("Attempting to remove completed crawl containers...")

        crawler_containers = await docker_utils.get_containers(
            self.docker_client, f"{self.MANAGED_BY_LABEL}={self.MANAGED_BY_VALUE}", all_containers=True
        )

        completed_crawls = [container for container in crawler_containers if container["State"] == "exited"]

        logger.debug(f"Found {len(completed_crawls)} completed crawls.")

        [await docker_utils.remove_container(self.docker_client, container["Id"]) for container in completed_crawls]

        logger.info(f"Removed {len(completed_crawls)} completed crawls.")

        return {
            "removed": len(completed_crawls),
            "total": len(crawler_containers),
        }

    # endregion Cleanup
