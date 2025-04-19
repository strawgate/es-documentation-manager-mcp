"""MCP Server for the Learn MCP Server."""

from typing import Callable, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from es_knowledge_base_mcp.models.settings import MemoryServerSettings
from es_knowledge_base_mcp.clients.knowledge_base import KnowledgeBaseProto, KnowledgeBaseServer

from fastmcp.utilities.logging import get_logger

logger = get_logger("knowledge-base-mcp.learn")

MEMORY_KNOWLEDGE_BASE_DEFAULT_ID = "default"
MEMORY_KNOWLEDGE_BASE_NAME = "Memory Knowledge Base"
MEMORY_KNOWLEDGE_DEFAULT_NAME = "Default Memory Knowledge Base"


class Thought(BaseModel):
    """Thought model."""

    title: str = Field(default="A friendly `title` for the thought.")
    body: str = Field(default="The thought.")


class MemoryServer:
    """learn server for the learn tool."""

    knowledge_base_server: KnowledgeBaseServer

    memory_index_prefix: str

    memory_knowledge_base_default_id: str

    response_formatter: Callable

    # memory_knowledge_base: KnowledgeBase

    def __init__(
        self,
        knowledge_base_server: KnowledgeBaseServer,
        memory_server_settings: MemoryServerSettings,
        response_formatter: Callable | None = None,
    ):
        self.knowledge_base_server = knowledge_base_server

        self.memory_knowledge_base_default_id = memory_server_settings.memory_index_prefix + MEMORY_KNOWLEDGE_BASE_DEFAULT_ID
        self.memory_index_prefix = memory_server_settings.memory_index_prefix

        self.response_formatter = response_formatter or (lambda response: response)

    def register_with_mcp(self, mcp: FastMCP):
        """Register the learn server with the MCP."""
        mcp.add_tool(self.thoughts)
        mcp.add_tool(self.thought)

    async def async_init(self):
        name = MEMORY_KNOWLEDGE_DEFAULT_NAME
        if memory_knowledge_base := await self.knowledge_base_server.try_get_kb_by_name(name):
            self.memory_knowledge_base = memory_knowledge_base
        else:
            await self.create_memory_knowledge_base(id=self.memory_knowledge_base_default_id, name=name)

    async def create_memory_knowledge_base(self, id: str, name: str):
        """Create a new memory knowledge base."""

        knowledge_base_proto = KnowledgeBaseProto(
            name=name,
            source="memory",
            description="This is the memory knowledge base.",
        )

        new_knowledge_base = await self.knowledge_base_server.create_kb_with_id(
            id=id,
            knowledge_base_proto=knowledge_base_proto,
        )

        assert new_knowledge_base is not None

        self.memory_knowledge_base = new_knowledge_base

    async def async_shutdown(self):
        pass

    async def thoughts(
        self,
        thoughts: List[Thought],
    ) -> None:
        """
        Send a list of Thoughts to be stored in the memory knowledge base. This is the main method for storing thoughts.
          Use this to record your thoughts in a structured way. You can send multiple thoughts at once. You can recall these
            thoughts later using the `recall` method or by asking questions via the Ask server.

        Args:
            thoughts: A list of Thought objects to store.

        Returns:
            None.

        Example:
            >>> await self.thoughts(thoughts=[Thought(title="Meeting Note", body="Discussed project plan"), Thought(title="Idea", body="New feature idea")])
        """

        await self.knowledge_base_server.create_kb_documents(
            knowledge_base=self.memory_knowledge_base, documents=[thought.model_dump() for thought in thoughts]
        )

    async def thought(
        self,
        title: str = Field(default="A friendly `title` for the thought."),
        body: str = Field(default="The thought."),
    ) -> None:
        """
        Send a single Thought to be stored in the memory knowledge base.

        Args:
            title: A friendly title for the thought.
            body: The content of the thought.

        Returns:
            None.

        Example:
            >>> await self.thought(title="Quick thought", body="Remember to check the logs.")
        """

        await self.thoughts(thoughts=[Thought(title=title, body=body)])

    async def recall(
        self,
        questions: list[str],
    ) -> str:
        """Search the memory knowledge base."""

        return self.response_formatter(
            await self.knowledge_base_server.search_kb(
                knowledge_base=self.memory_knowledge_base,
                questions=questions,
            )
        )
