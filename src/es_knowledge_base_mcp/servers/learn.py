"""MCP Server for the Learn MCP Server."""

from typing import Callable
import requests
from bs4 import BeautifulSoup, Tag
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from urllib.parse import urljoin, urlparse, urlunparse

from es_knowledge_base_mcp.clients.crawl import Crawler, CrawlerSettings
from es_knowledge_base_mcp.clients.knowledge_base import KnowledgeBaseProto, KnowledgeBaseServer
from es_knowledge_base_mcp.models.settings import ElasticsearchSettings

from fastmcp.utilities.logging import get_logger

logger = get_logger("knowledge-base-mcp.learn")

MEMORY_KNOWLEDGE_BASE_NAME = "Memory Knowledge Base"


# region Web Docs
class LearnWebDocumentationRequestArgs(BaseModel):
    """Parameters for the web documentation request."""

    url: str = Field(default="The URL to crawl.")
    knowledge_base_name: str = Field(default="Name of the new or existing knowledge base to place the documents into.")
    knowledge_base_description: str = Field(default="Description of the new or existing knowledge base to place the documents into.")


class LearnServer:
    """learn server for the learn tool."""

    crawler: Crawler

    knowledge_base_server: KnowledgeBaseServer

    response_formatter: Callable

    def __init__(
        self,
        knowledge_base_server: KnowledgeBaseServer,
        crawler_settings: CrawlerSettings,
        elasticsearch_settings: ElasticsearchSettings,
        response_formatter: Callable | None = None,
    ):
        self.knowledge_base_server = knowledge_base_server

        self.crawler = Crawler(settings=crawler_settings, elasticsearch_settings=elasticsearch_settings)

        self.response_formatter = response_formatter or (lambda response: response)

    async def async_init(self):
        """Initialize the learn server."""

        await self.crawler.async_init()

    async def async_shutdown(self):
        """Shutdown the learn server."""

        await self.crawler.async_shutdown()

        pass

    def register_with_mcp(self, mcp: FastMCP):
        # Register tools after their definitions
        mcp.add_tool(self.extract_urls_from_webpage)
        mcp.add_tool(self.from_web_documentation_requests)
        mcp.add_tool(self.from_web_documentation_request)
        mcp.add_tool(self.from_web_documentation)

    @classmethod
    async def extract_urls_from_webpage(cls, url: str) -> list[str]:
        """
        Extracts all unique URLs from a given webpage, stripping fragments and query parameters. This is extremely
        useful for determining what urls to crawl from a given seed page. For example, if you know you want rspec documentation,
        you can use this tool to find all the urls on the rspec documentation page and then use those urls to crawl the
        rspec documentation of the version and type you're looking for.

        Args:
            url: The URL of the webpage to extract URLs from.

        Returns:
            A sorted list of unique URLs found on the page.

        Example:
            >>> await self.extract_urls_from_webpage(url="https://www.example.com")
            ['https://www.example.com/about', 'https://www.example.com/contact', 'https://www.example.com/products']
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            urls = [urljoin(url, str(a["href"])) for a in soup.find_all("a", href=True) if isinstance(a, Tag)]
            # Strip fragments and query parameters and deduplicate
            cleaned_urls = []
            for u in urls:
                parsed_url = urlparse(u)
                cleaned_url = urlunparse(parsed_url._replace(fragment="", query=""))
                cleaned_urls.append(cleaned_url)

            sorted_urls = list(set(cleaned_urls))
            sorted_urls.sort()

            return sorted_urls
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching or parsing webpage: {e}")
            return []

    async def git_repository(self, directory_path: str):
        pass

    async def directory_documentation(self, directory_path: str):
        raise NotImplementedError("Directory documentation is not implemented yet.")

    async def file_documentation(self, file_path: str):
        raise NotImplementedError("File documentation is not implemented yet.")

    async def from_web_documentation(
        self, url: str, knowledge_base_name: str, knowledge_base_description: str
    ) -> tuple[KnowledgeBaseProto, str]:
        """
        Starts a crawl job based on a seed page and creates a knowledge base entry for it.

        Args:
            url: The seed URL to start the crawl from.
            knowledge_base_name: The name for the new or existing knowledge base.
            knowledge_base_description: A description for the new or existing knowledge base.

        Returns:
            A tuple containing the created or updated KnowledgeBaseProto and the container ID of the crawl job.

        Example:
            >>> await self.from_web_documentation(url="https://docs.python.org/", knowledge_base_name="Python Docs", knowledge_base_description="Official Python documentation")
            (<KnowledgeBaseProto name='Python Docs' source='https://docs.python.org/' description='Official Python documentation'>, 'container_id_abc123')
        """

        knowledge_base_proto = KnowledgeBaseProto(
            name=knowledge_base_name,
            source=url,
            description=knowledge_base_description,
        )

        return self.response_formatter(await self._from_web_documentation_request(knowledge_base_proto=knowledge_base_proto))

    async def from_web_documentation_request(self, knowledge_base_proto: KnowledgeBaseProto) -> tuple[KnowledgeBaseProto, str]:
        """
        Starts a crawl job based on a seed page using a provided KnowledgeBaseProto.

        Args:
            knowledge_base_proto: The KnowledgeBaseProto object containing the name, source URL, and description for the knowledge base.

        Returns:
            A tuple containing the created or updated KnowledgeBaseProto and the container ID of the crawl job.

        Example:
            >>> await self.from_web_documentation_request(knowledge_base_proto=KnowledgeBaseProto(name="Example KB", source="https://www.example.com/docs", description="Example documentation"))
            (<KnowledgeBaseProto name='Example KB' source='https://www.example.com/docs' description='Example documentation'>, 'container_id_xyz789')
        """

        return self.response_formatter(await self._from_web_documentation_request(knowledge_base_proto=knowledge_base_proto))

    async def from_web_documentation_requests(
        self, knowledge_base_protos: list[KnowledgeBaseProto]
    ) -> list[tuple[KnowledgeBaseProto, str]]:
        """
        Starts multiple crawl jobs based on a list of KnowledgeBaseProto objects. This is the main entry point for starting crawl jobs from web documentation requests.
          Use this to create or update knowledge bases based on multiple seed pages. This allows you to make the user experience more efficient by allowing them to
            start multiple crawl jobs at once.

        Args:
            knowledge_base_protos: A list of KnowledgeBaseProto objects, each containing the name, source URL, and description for a knowledge base.

        Returns:
            A list of tuples, where each tuple contains the created or updated KnowledgeBaseProto and the container ID for each crawl job.

        Example:
            >>> await self.from_web_documentation_requests(knowledge_base_protos=[KnowledgeBaseProto(name="KB1", source="url1", description="desc1"), KnowledgeBaseProto(name="KB2", source="url2", description="desc2")])
            [(<KnowledgeBaseProto name='KB1' source='url1' description='desc1'>, 'container_id_111'), (<KnowledgeBaseProto name='KB2' source='url2' description='desc2'>, 'container_id_222')]
        """
        return self.response_formatter(
            [
                await self._from_web_documentation_request(knowledge_base_proto=knowledge_base_proto)
                for knowledge_base_proto in knowledge_base_protos
            ]
        )

    async def _from_web_documentation_request(self, knowledge_base_proto: KnowledgeBaseProto):
        """Starts a crawl job based on a seed page."""

        new_knowledge_base = await self.knowledge_base_server.create_kb_with_scope(scope="docs", knowledge_base_proto=knowledge_base_proto)

        url = new_knowledge_base.source

        assert new_knowledge_base is not None, f"Failed to create new knowledge base for {url}."

        logger.debug("Starting crawl job for URL: %s", url)

        crawl_parameters = self.crawler.derive_crawl_params(url)

        container_id = await self.crawler.crawl_domain(elasticsearch_index_name=new_knowledge_base.id, **crawl_parameters)

        return (new_knowledge_base, container_id)
