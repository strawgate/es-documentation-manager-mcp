"""MCP Server for the Ask tool."""

from enum import Enum
from typing import Callable, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import yaml

from es_knowledge_base_mcp.clients.knowledge_base import KnowledgeBaseServer, SearchResult

from fastmcp.utilities.logging import get_logger


logger = get_logger("knowledge-base-mcp.ask")


class AskQuestionResponse(BaseModel):
    question: str = Field(description="The question.")
    results: List[SearchResult] = Field(description="The search results.")

    def __getstate__(self):
        """Only include the underlying dictionary in the state for serialization."""
        return self.__dict__

    def to_yaml(self) -> str:
        """Converts the search result to a string."""

        formatted = yaml.dump(
            {"Question": self.question, "Results": [result.to_dict() for result in self.results]},
            indent=2,
            width=10000,
            sort_keys=False,
            default_style="",
        )

        return formatted


class QuestionAnswerStyle(str, Enum):
    """Enum for answer styles. Representing the thoroughness of the answer: Concise, Normal, Comprehensive, or Exhaustive."""

    CONCISE = "concise"
    NORMAL = "normal"
    COMPREHENSIVE = "comprehensive"
    EXHAUSTIVE = "exhaustive"

    def to_search_size(self) -> int:
        """Converts the answer style to a search size."""
        return {
            self.CONCISE: 1,
            self.NORMAL: 4,
            self.COMPREHENSIVE: 8,
            self.EXHAUSTIVE: 12,
        }[self]


class AskServer:
    """Ask server for the Ask tool."""

    knowledge_base_server: KnowledgeBaseServer
    response_formatter: Callable

    def __init__(self, knowledge_base_server: KnowledgeBaseServer, response_formatter: Callable | None = None):
        """Initialize the Ask server."""
        self.knowledge_base_server = knowledge_base_server
        self.response_formatter = response_formatter or (lambda response: response)

    def register_with_mcp(self, mcp: FastMCP):
        """Register the tools with the MCP server."""
        mcp.add_tool(self.questions)
        mcp.add_tool(self.questions_for_kb)

    async def async_init(self):
        pass

    async def async_shutdown(self):
        pass

    def _questions_to_queries(self, questions: list[str], answer_style: QuestionAnswerStyle) -> list[dict]:
        """Convert questions to queries."""

        fragments = results = answer_style.to_search_size()
        queries = [
            {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"headings": {"query": question, "boost": 1}}},
                            {"semantic": {"field": "body", "query": question, "boost": 2}},
                        ]
                    }
                },
                "_source": ["title", "url"],
                "size": results,
                "highlight": {"number_of_fragments": fragments, "fragment_size": 500, "fields": {"body": {}}},
            }
            for question in questions
        ]

        return queries

    async def questions(self, questions: list[str], answer_style: QuestionAnswerStyle = QuestionAnswerStyle.NORMAL) -> list[str]:
        """
        Ask questions of the knowledge base. This is the main entry point for asking questions. Ask questions in plain English
          and the knowledge base will return the most relevant results. You can ask as many questions as you want, as often
            as you want. The knowledge base will return the most relevant results for each question.

        Args:
            questions: A list of strings, where each string is a question to ask the knowledge base.
            answer_style: The desired thoroughness of the answer. Defaults to QuestionAnswerStyle.NORMAL.

        Returns:
            A list of formatted strings, where each string contains the answer to a question.

        Example:
            >>> await self.questions(questions=["What is the capital of France?", "What is the highest mountain in the world?"], answer_style=QuestionAnswerStyle.COMPREHENSIVE)
            [
                "Question: What is the capital of France?\nResults:\n  - Title: Paris\n    URL: http://example.com/paris\n    Content: Paris is the capital and most populous city of France.",
                "Question: What is the highest mountain in the world?\nResults:\n  - Title: Mount Everest\n    URL: http://example.com/everest\n    Content: Mount Everest is the Earth's highest mountain above sea level."
            ]
        """

        question_results = zip(
            questions,
            await self.knowledge_base_server.search_kb_all(
                questions=questions, results=answer_style.to_search_size(), fragments=answer_style.to_search_size()
            ),
        )

        return self.response_formatter([AskQuestionResponse(question=question, results=results) for question, results in question_results])
        # return "\n".join([AskQuestionResponse(question=question, results=results).to_yaml() for question, results in question_results])

    async def questions_for_kb(
        self, questions: list[str], knowledge_base_name: str, answer_style: QuestionAnswerStyle = QuestionAnswerStyle.NORMAL
    ) -> str:
        """
        Ask questions of a specific knowledge base.

        Args:
            questions: A list of strings, where each string is a question to ask the knowledge base.
            knowledge_base_name: The name of the knowledge base to query.
            answer_style: The desired thoroughness of the answer. Defaults to QuestionAnswerStyle.NORMAL.

        Returns:
            A formatted string containing the answers to the questions from the specified knowledge base.

        Example:
            >>> await self.questions_for_kb(questions=["How do I install the library?"], knowledge_base_name="My Python Library Docs", answer_style=QuestionAnswerStyle.NORMAL)
            "Question: How do I install the library?\nResults:\n  - Title: Installation Guide\n    URL: http://example.com/docs/install\n    Content: To install the library, use pip: `pip install my-library`."
        """

        knowledge_base = await self.knowledge_base_server.get_kb_by_name(name=knowledge_base_name)

        question_results = zip(
            questions,
            await self.knowledge_base_server.search_kb(
                knowledge_base=knowledge_base,
                questions=questions,
                results=answer_style.to_search_size(),
                fragments=answer_style.to_search_size(),
            ),
        )

        return self.response_formatter([AskQuestionResponse(question=question, results=results) for question, results in question_results])
        # return "\n".join([AskQuestionResponse(question=question, results=results).to_yaml() for question, results in question_results])
