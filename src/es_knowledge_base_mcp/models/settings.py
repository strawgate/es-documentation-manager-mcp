import logging

import os
from typing import Any, Literal, Optional, Dict, Self
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator
from es_knowledge_base_mcp.models.constants import BASE_LOGGER_NAME

logger = logging.getLogger(BASE_LOGGER_NAME)

ELASTICSEARCH_ENV_PREFIX = "ES_"

# region Transport Settings


class TransportSettings(BaseSettings):
    """Settings for configuring the transport layer."""

    model_config = SettingsConfigDict()

    mcp_transport: Literal["stdio", "sse"] = Field(default="stdio", description="Transport type, either sse or stdio.")


# endregion Transport Settings


# region Logging Settings
class LoggingSettings(BaseSettings):
    """Settings for configuring logging."""

    model_config = SettingsConfigDict()

    log_level: str = Field(default="INFO", alias="MCP_LOG_LEVEL", description="Logging level.")

    # include the PID in the log format
    log_format: str = Field(
        default=f"%(asctime)s : {os.getpid()} - %(name)s - %(levelname)s - %(message)s",
        description="Logging format.",
    )
    log_file: Optional[str] = Field(default=None, description="Log file path.")

    def configure_logging(self):
        """Configure logging based on the settings."""
        logging.basicConfig(level=self.log_level, format=self.log_format, filename=self.log_file, filemode="a", force=True)

        return logger


# endregion Logging Settings

# region Elasticsearch Settings


class BaseElasticsearchSettings(BaseSettings):
    """Base options for the various Elastisearch Settings classes."""

    model_config = SettingsConfigDict(
        cli_parse_args=True,
        cli_kebab_case=True,
    )


class ElasticsearchAuthenticationSettings(BaseElasticsearchSettings):
    """Settings for configuring authentication to Elasticsearch."""

    username: Optional[str] = Field(default=None, alias="ES_USERNAME", description="Username for basic authentication.")
    password: Optional[SecretStr] = Field(default=None, alias="ES_PASSWORD", exclude=True, description="Password for basic authentication.")
    api_key: Optional[SecretStr] = Field(default=None, alias="ES_API_KEY", exclude=True, description="API key for authentication.")

    # validate that only one of the authentication methods is set
    @model_validator(mode="after")
    def validate_authentication(self) -> Self:
        """Validate that only one authentication method is set."""
        if self.api_key and (self.username or self.password):
            raise ValueError("Cannot use both API key and basic authentication.")
        if self.username and not self.password:
            raise ValueError("Username requires a password.")
        if self.password and not self.username:
            raise ValueError("Password requires a username.")
        return self


class ElasticsearchSettings(BaseElasticsearchSettings):
    """Settings for configuring the connection to Elasticsearch."""

    host: str = Field(
        default="https://localhost:9200",
        alias="ES_HOST",
        description="Elasticsearch host URL in the form `https://<host>:<port>`.",
    )

    request_timeout: int = Field(
        default=600,
        alias="ES_REQUEST_TIMEOUT",
        description="Request timeout for Elasticsearch operations in seconds.",
    )

    index_prefix: str = Field(
        default="kbmcp-docs.*",
        alias="ES_INDEX_PREFIX",
        description="Prefix for the Elasticsearch indices used to store documentation.",
    )

    bulk_api_max_items: int = Field(
        default=200,
        alias="ES_BULK_API_MAX_ITEMS",
        description="Maximum number of items for bulk API operations.",
    )

    bulk_api_max_size_bytes: int = Field(
        default=10485760,
        alias="ES_BULK_API_MAX_SIZE_BYTES",
        description="Maximum size in bytes for bulk API operations.",
    )

    authentication: ElasticsearchAuthenticationSettings = Field(default=ElasticsearchAuthenticationSettings())

    @model_validator(mode="after")
    def validate_host(self) -> Self:
        return self

    @property
    def host_port(self):
        """Get the Elasticsearch port."""
        parsed_url = urlparse(self.host)
        return parsed_url.port if parsed_url.port else 443 if parsed_url.scheme == "https" else 80

    @property
    def host_scheme(self):
        """Get the Elasticsearch scheme."""
        parsed_url = urlparse(self.host)
        return parsed_url.scheme

    @property
    def host_name(self):
        """Get the hostname for the ."""
        parsed_url = urlparse(self.host)
        return parsed_url.hostname

    @property
    def index_pattern(self) -> str:
        """Generate the Elasticsearch index name using the prefix and a wildcard."""
        return f"{self.index_prefix}-*"

    def _get_auth_dict(self) -> Dict[str, Any]:
        """Get the authentication dictionary for Elasticsearch."""
        auth_dict = {}

        if self.authentication.api_key:
            auth_dict["api_key"] = self.authentication.api_key.get_secret_value()
        elif self.authentication.username and self.authentication.password:
            auth_dict["basic_auth"] = (
                self.authentication.username,
                self.authentication.password.get_secret_value(),
            )
        else:
            logger.warning("No authentication method specified for Elasticsearch.")

        return auth_dict

    def to_client_settings(self) -> Dict[str, Any]:
        settings = {
            "hosts": [self.host],
            "request_timeout": self.request_timeout,
            "http_compress": True,
            "retry_on_status": (408, 429, 502, 503, 504),
            "retry_on_timeout": True,
            "max_retries": 5,
            **self._get_auth_dict(),
        }

        return settings

    def to_crawler_settings(self) -> Dict[str, Any]:
        settings = {
            "host": self.host,
            "port": self.host_port,
            "request_timeout": self.request_timeout,
            "bulk_api.max_items": self.bulk_api_max_items,
            "bulk_api.max_size_bytes": self.bulk_api_max_size_bytes,
            **self._get_auth_dict(),
        }

        return settings


class KnowledgeBaseServerSettings(BaseElasticsearchSettings):
    base_index_prefix: str = Field(
        default="kbmcp-",
    )

    @property
    def base_index_pattern(self) -> str:
        """Generate the Elasticsearch index name using the prefix and a wildcard."""
        return f"{self.base_index_prefix}*"


class LearnServerSettings(BaseElasticsearchSettings):
    """Settings for configuring the learn server."""

    learn_index_prefix: str = Field(
        default="kbmcp-docs.",
        alias="KB_DOCS_INDEX_PREFIX",
        description="Elasticsearch index for storing learn. Added to the base index prefix.",
    )

    @property
    def learn_index_pattern(self) -> str:
        return f"{self.learn_index_prefix}*"


class MemoryServerSettings(BaseElasticsearchSettings):
    """Settings for configuring the memory Server."""

    memory_index_prefix: str = Field(
        default="kbmcp-memories.",
        alias="MEMORY_INDEX_PREFIX",
        description="Elasticsearch index for storing memories. Added to the base index prefix.",
    )

    @property
    def memory_index_pattern(self) -> str:
        return f"{self.memory_index_prefix}*"


class CrawlerSettings(BaseSettings):
    """Settings for configuring the crawler."""

    model_config = SettingsConfigDict()

    elasticsearch_pipeline: str = Field(
        default="search-default-ingestion",
        alias="crawler_es_pipeline",
        description="Elasticsearch pipeline for processing crawler documents.",
    )

    docker_image: str = Field(alias="crawler_docker_image", default="ghcr.io/strawgate/es-crawler:main")


# endregion Elasticsearch Settings

# region Main Settings


class BaseDocumentationManagerSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True, cli_kebab_case=True)


class DocsManagerSettings(BaseDocumentationManagerSettings):
    """Load settings for the Docs Manager."""

    mcps: TransportSettings = Field(default=TransportSettings())

    logging: LoggingSettings = Field(default=LoggingSettings())

    elasticsearch: ElasticsearchSettings = Field(default=ElasticsearchSettings())

    knowledge_base: KnowledgeBaseServerSettings = Field(default=KnowledgeBaseServerSettings())

    learn: LearnServerSettings = Field(default=LearnServerSettings())

    memory: MemoryServerSettings = Field(default=MemoryServerSettings())

    crawler: CrawlerSettings = Field(default=CrawlerSettings())


# endregion Main Settings
