from typing import AsyncIterator
from elasticsearch import ApiError, AsyncElasticsearch, AuthenticationException, AuthorizationException, BadRequestError, ConnectionError
from contextlib import asynccontextmanager
from es_knowledge_base_mcp.models.errors import ElasticsearchConnectionError, ElasticsearchError, InvalidConfigurationError

from fastmcp.utilities.logging import get_logger

logger = get_logger("knowledge-base-mcp.elasticsearch")


@asynccontextmanager
async def elasticsearch_manager(elasticsearch_client: AsyncElasticsearch) -> AsyncIterator[AsyncElasticsearch]:
    """Context manager for Elasticsearch client."""

    try:
        await elasticsearch_client.info()
    except AuthenticationException as e:
        raise InvalidConfigurationError("Authentication failed for Elasticsearch.") from e
    except AuthorizationException as e:
        raise InvalidConfigurationError("Authorization failed for Elasticsearch.") from e
    except ConnectionError as e:
        raise InvalidConfigurationError("Could not connect to Elasticsearch.") from e
    except Exception as e:
        raise InvalidConfigurationError("Unknown error connecting to Elasticsearch.") from e
    finally:
        await elasticsearch_client.close()
    try:
        async with handle_errors("Elasticsearch client initialization"):
            yield elasticsearch_client
    finally:
        await elasticsearch_client.close()


@asynccontextmanager
async def handle_errors(operation: str) -> AsyncIterator[None]:
    """Context manager for error handling."""

    logger.debug(f"Attempting {operation}...")

    try:
        yield
    except ConnectionError as e:
        raise ElasticsearchConnectionError("Connection error occurred during {operation}.") from e
    except BadRequestError as e:
        raise ElasticsearchError("Elasticsearch returned 'Bad Request' during {operation}.") from e
    except ApiError as e:
        raise ElasticsearchError("Elasticsearch returned an Api Error during {operation}.") from e
    except Exception as e:
        raise ElasticsearchError("Unknown error during Elasticsearch {operation}.") from e

    logger.debug(f"Completed {operation}.")


# region Index Handling


def url_to_index_name(url) -> str:
    # Convert URL to a valid index name
    # We can have 256 characters of lowercase alphanumeric characters, underscores, hyphens and periods

    # We'll want to keep only the first 50 characters of the URL
    # we want www.python.org/docs/index.html to turn into www_python_org.docs.index_html
    # so we replace dots with underscores
    # slashes with dots
    # strip all other characters
    id = url.replace("https://", "").replace("http://", "").replace(".", "_").replace("/", ".").replace("-", "_")
    id = "".join(c for c in id if c.isalnum() or c in ["_", "-", "."])
    # trim off any leading or trailing dashes, underscores, or periods

    return id[:50].strip("-_.").lower()


# endregion Index Handling
