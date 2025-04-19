import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator
from elasticsearch import AsyncElasticsearch
from fastmcp import FastMCP
import yaml

from es_knowledge_base_mcp.clients.elasticsearch import elasticsearch_manager
from es_knowledge_base_mcp.clients.knowledge_base import KnowledgeBaseServer
from es_knowledge_base_mcp.models.errors import InvalidConfigurationError
from es_knowledge_base_mcp.models.settings import DocsManagerSettings
from es_knowledge_base_mcp.servers.ask import AskServer
from es_knowledge_base_mcp.servers.learn import LearnServer
from fastmcp.utilities.logging import get_logger

from es_knowledge_base_mcp.servers.manage import ManageServer
from es_knowledge_base_mcp.servers.remember import MemoryServer

logger = get_logger("knowledge-base-mcp")
logger.setLevel("DEBUG")


def arg_parsing():
    parser = argparse.ArgumentParser(
        description="Knowledge Base MCP Server",
        add_help=True,
    )
    parser.add_argument("--smoke", action="help", help="To run this script please provide two arguments")

    args, unknown = parser.parse_known_args()


def load_settings():
    try:
        return DocsManagerSettings()
    except Exception as e:
        raise InvalidConfigurationError(f"Failed to load settings: {e}")


@dataclass
class RootContext:
    knowledge_base_server: KnowledgeBaseServer
    memory_server: MemoryServer
    ask_server: AskServer
    manage_server: ManageServer
    learn_server: LearnServer | None


async def main():
    arg_parsing()

    settings: DocsManagerSettings = load_settings()

    elasticsearch_client_args = settings.elasticsearch.to_client_settings()

    elasticsearch_client: AsyncElasticsearch
    async with elasticsearch_manager(elasticsearch_client=AsyncElasticsearch(**elasticsearch_client_args)) as new_client:
        elasticsearch_client = new_client

    elasticsearch_client = AsyncElasticsearch(**elasticsearch_client_args)

    # monkey patch so our yaml emitter doesnt include class names in output
    yaml.emitter.Emitter.prepare_tag = lambda self, tag: ""

    def response_formatter(response) -> str:
        """Format the response from Elasticsearch."""
        return yaml.dump(response, default_flow_style=False, width=10000, sort_keys=False)

    knowledge_base_server = KnowledgeBaseServer(
        settings=settings.knowledge_base,
        elasticsearch_client=elasticsearch_client,
        # response_formatter=response_formatter,
    )

    memory_server = MemoryServer(
        knowledge_base_server=knowledge_base_server,
        memory_server_settings=settings.memory,
        response_formatter=response_formatter,
    )

    ask_server = AskServer(
        knowledge_base_server=knowledge_base_server,
        response_formatter=response_formatter,
    )

    learn_server = LearnServer(
        knowledge_base_server=knowledge_base_server,
        crawler_settings=settings.crawler,
        elasticsearch_settings=settings.elasticsearch,
        response_formatter=response_formatter,
    )

    manage_server = ManageServer(
        knowledge_base_server=knowledge_base_server,
        response_formatter=response_formatter,
    )

    root_mcp = FastMCP("knowledge-base-mcp")

    @asynccontextmanager
    async def root_lifespan(server: FastMCP) -> AsyncGenerator[RootContext, None]:
        """Lifespan for the FastMCP application."""

        yield RootContext(
            knowledge_base_server=knowledge_base_server,
            memory_server=memory_server,
            ask_server=ask_server,
            learn_server=learn_server,
            manage_server=manage_server,
        )

    root_mcp = FastMCP("kbmcp", lifespan=root_lifespan)

    await knowledge_base_server.async_init()

    await manage_server.async_init()
    manage_server.register_with_mcp(root_mcp)

    await memory_server.async_init()
    memory_server.register_with_mcp(root_mcp)

    await ask_server.async_init()
    ask_server.register_with_mcp(root_mcp)

    try:
        await learn_server.async_init()
        learn_server.register_with_mcp(root_mcp)
    except Exception as e:
        logger.warning(f"Failed to initialize Learn server, likely due to Docker not being available. Error: {e}")
        learn_server = None

    try:
        await root_mcp.run_async(transport=settings.mcps.mcp_transport)
    finally:
        await knowledge_base_server.async_shutdown()
        await memory_server.async_shutdown()
        await ask_server.async_shutdown()

        if learn_server:  # Conditionally shutdown learn_server
            await learn_server.async_shutdown()

        await manage_server.async_shutdown()

        await elasticsearch_client.close()


def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting...")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        logger.info("Server shutdown complete.")


if __name__ == "__main__":
    logger.error("This script is not meant to be run directly. Please use the MCP CLI to start the server.")
    run()
