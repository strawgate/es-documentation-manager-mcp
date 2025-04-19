from typing import TYPE_CHECKING, Any, List
import uuid
from elasticsearch import AsyncElasticsearch
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager


from elasticsearch import (
    NotFoundError,
    ApiError,
)


from fastmcp.utilities.logging import get_logger
from es_knowledge_base_mcp.clients.elasticsearch import url_to_index_name
from es_knowledge_base_mcp.models.constants import CRAWLER_INDEX_MAPPING
from es_knowledge_base_mcp.models.errors import ElasticsearchError, ElasticsearchNotFoundError, ElasticsearchSearchError
from es_knowledge_base_mcp.models.settings import KnowledgeBaseServerSettings


MEMORY_KNOWLEDGE_BASE_NAME = "Memory Knowledge Base"

if TYPE_CHECKING:
    pass

logger = get_logger("knowledge-base-mcp.knowledge-base")


class KnowledgeBaseProto(BaseModel):
    """Knowledge Base tool."""

    name: str = Field(default="name of the knowledge base")
    source: str = Field(default="source of the knowledge base")
    description: str = Field(default="description of the knowledge base")

    def to_metadata_mapping(self) -> dict[str, Any]:
        """Converts the object to a dictionary."""

        return {
            "knowledge_base": {
                "name": self.name,
                "source": self.source,
                "description": self.description,
            }
        }


class KnowledgeBase(KnowledgeBaseProto):
    """Knowledge Base tool."""

    id: str = Field(default="raw index name of the knowledge base")
    doc_count: int = Field(default=0, description="Number of documents in the knowledge base")

    def __getstate__(self):
        """Only include the underlying dictionary in the state for serialization."""

        # return in a specific order
        return {
            "title": self.name,
            "description": self.description,
            "source": self.source,
            "id": self.id,
            "doc_count": self.doc_count,
        }


class SearchResult(BaseModel):
    knowledge_base_name: str | None = Field(default=None, description="The name of the knowledge base.")
    title: str = Field(default="A friendly `title` for knowledge base document.")
    url: str = Field(default="The original URL of the document searched.")
    highlights: List[str] | None = Field(default=None, description="The highlights of the search result.")
    body: str | None = Field(default=None, description="The body of the search result.")

    def __getstate__(self):
        """Only include the underlying dictionary in the state for serialization."""
        return self.__dict__

    def to_dict(self) -> dict[str, Any]:
        """Converts the object to a dictionary."""

        return {k: v for k, v in self.__dict__.items() if v is not None and v != ""}

    @classmethod
    def extract_from_hit(cls, hit: dict[str, Any]):
        """
        Extracts specified keys from the source dictionary.
        """
        # index = hit.get("_index", "")
        source = hit.get("_source", {})

        highlights = hit.get("highlight", {})

        title = source.get("title", "")
        url = source.get("url", "")
        body = source.get("body", "")

        if highlights := highlights.get("body", []):
            highlights = [highlight for highlight in highlights if highlight]

        return cls(title=title, url=url, highlights=highlights, body=body)


class KnowledgeBaseServer:
    """Handles the logic for knowledge bases."""

    index_prefix: str
    index_pattern: str

    elasticsearch_client: AsyncElasticsearch

    def __init__(self, settings: KnowledgeBaseServerSettings, elasticsearch_client: AsyncElasticsearch):
        self.index_prefix = settings.base_index_prefix
        self.index_pattern = settings.base_index_pattern

        self.elasticsearch_client = elasticsearch_client

    async def async_init(self):
        pass

    async def async_shutdown(self):
        pass

    @asynccontextmanager
    async def error_handler(self, operation: str):
        """Context manager for Elasticsearch client."""

        logger.debug(f"Attempting {operation}.")

        try:
            yield

        except NotFoundError as e:
            err_text = f"Not found error while {operation}"
            logger.exception(err_text)
            raise ElasticsearchNotFoundError(err_text) from e

        except ApiError as e:
            err_text = f"Elasticsearch API error while {operation}."
            logger.exception(err_text)
            raise ElasticsearchSearchError(err_text) from e

        except Exception as e:
            err_text = f"Unexpected error while {operation}."
            logger.exception(err_text)
            raise ElasticsearchError(err_text) from e

        logger.debug(f"Completed {operation}.")

    # region KB Management

    async def get_kb(self) -> list[KnowledgeBase]:
        """Get a list of knowledge bases that match the match."""

        async with self.error_handler("getting knowledge base indices"):
            response = await self.elasticsearch_client.indices.get(index=self.index_pattern, allow_no_indices=True)

        async with self.error_handler("getting doc counts"):
            cat_response = await self.elasticsearch_client.cat.indices(index=self.index_pattern, format="json", h=["index", "docs.count"])

            json_responses: list[dict[str, Any]] = cat_response.body  # type: ignore

            doc_counts = {item["index"]: item["docs.count"] for item in json_responses}

        knowledge_base_indices: dict[str, Any] = response.body

        return [
            KnowledgeBase(
                id=index,
                name=knowledge_base_metadata.get("name", ""),
                description=knowledge_base_metadata.get("description", ""),
                source=knowledge_base_metadata.get("source", ""),
                doc_count=doc_counts.get(index, 0),
            )
            for index, metadata in knowledge_base_indices.items()
            if (knowledge_base_metadata := metadata.get("mappings", {}).get("_meta", {}).get("knowledge_base", {}))
        ]

    async def try_get_kb_by_name(self, name: str) -> KnowledgeBase | None:
        """Test a knowledge base entry by ID."""

        try:
            return await self.get_kb_by_name(name)
        except ElasticsearchNotFoundError:
            return None

    async def get_kb_by_name(self, name: str) -> KnowledgeBase:
        """Get a knowledge base entry by ID."""

        knowledge_base = await self.get_kb()

        matching_kb = [entry for entry in knowledge_base if entry.name == name]

        if not matching_kb:
            raise ElasticsearchNotFoundError(f"Knowledge base '{name}' not found.")
        if len(matching_kb) > 1:
            raise ElasticsearchError(f"Multiple knowledge bases found with name '{name}'.")

        return matching_kb[0]

    async def try_get_kb_by_id(self, id: str) -> KnowledgeBase | None:
        """Test a knowledge base entry by ID."""

        try:
            return await self.get_kb_by_id(id)
        except ElasticsearchNotFoundError:
            return None

    async def get_kb_by_id(self, id: str) -> KnowledgeBase:
        """Get a knowledge base entry by ID."""

        knowledge_base = await self.get_kb()

        matching_kb = [entry for entry in knowledge_base if entry.id == id]

        if not matching_kb:
            raise ElasticsearchNotFoundError(f"Knowledge base '{id}' not found.")
        if len(matching_kb) > 1:
            raise ElasticsearchError(f"Multiple knowledge bases found with ID '{id}'.")

        return matching_kb[0]

    async def get_kb_by_id_or_name(self, id_or_name: str) -> KnowledgeBase:
        """Get a knowledge base entry by ID or name."""

        kb_by_id = await self.try_get_kb_by_id(id_or_name)
        if kb_by_id is not None:
            return kb_by_id

        kb_by_name = await self.try_get_kb_by_name(id_or_name)
        if kb_by_name is not None:
            return kb_by_name

        raise ElasticsearchNotFoundError(f"Knowledge base '{id_or_name}' not found.")

    async def create_kb_with_id(self, id: str, knowledge_base_proto: KnowledgeBaseProto):
        """Create a new knowledge base entry."""

        mappings = {"_meta": knowledge_base_proto.to_metadata_mapping(), **CRAWLER_INDEX_MAPPING}

        index_name = id

        await self.elasticsearch_client.indices.create(index=index_name, mappings=mappings)

        return KnowledgeBase(
            id=index_name,
            name=knowledge_base_proto.name,
            description=knowledge_base_proto.description,
            source=knowledge_base_proto.source,
        )

    async def create_kb_with_scope(self, scope: str, knowledge_base_proto: KnowledgeBaseProto):
        """Create a new knowledge base entry with the specified scope."""

        id_prefix = self._scoped_index_prefix(scope)
        id = url_to_index_name(knowledge_base_proto.source)
        id_suffix = str(uuid.uuid4())[:8]

        id = f"{id_prefix}-{id}-{id_suffix}"

        return await self.create_kb_with_id(id=id, knowledge_base_proto=knowledge_base_proto)

    async def create_kb(self, knowledge_base_proto: KnowledgeBaseProto):
        """Create a new knowledge base entry."""

        id_prefix = self.index_prefix
        id = url_to_index_name(knowledge_base_proto.source)
        id_suffix = str(uuid.uuid4())[:8]

        id = f"{id_prefix}-{id}-{id_suffix}"

        return await self.create_kb_with_id(id=id, knowledge_base_proto=knowledge_base_proto)

    async def update_kb(self, id: str, knowledge_base_proto: KnowledgeBaseProto):
        """Update a knowledge base entry."""
        async with self.error_handler("updating knowledge base metadata"):
            await self.elasticsearch_client.indices.put_mapping(index=id, meta=knowledge_base_proto.to_metadata_mapping())

    async def delete_kb(self, knowledge_base: KnowledgeBase):
        """Delete a knowledge base entry."""
        async with self.error_handler("deleting knowledge base"):
            await self.elasticsearch_client.indices.delete(index=knowledge_base.id)

    # endregion KB Management

    # region KB Search

    async def search_kb_all(self, questions: list[str], results: int = 5, fragments: int = 5):
        return await self._search_by_indices(questions, [self.index_pattern], results=results, fragments=fragments)

    async def search_kb(self, knowledge_base: KnowledgeBase, questions: list[str], results: int = 5, fragments: int = 5):
        """Search the knowledge base for the questions."""

        return await self._search_by_knowledge_bases(questions, knowledge_base=[knowledge_base], results=results, fragments=fragments)

    async def search_kbs(self, knowledge_bases: list[KnowledgeBase], questions: list[str], results: int = 5, fragments: int = 5):
        """Search the knowledge base for the questions."""

        return await self._search_by_knowledge_bases(questions, knowledge_base=knowledge_bases, results=results, fragments=fragments)

    async def _search_by_knowledge_bases(
        self, questions: list[str], knowledge_base: list[KnowledgeBase], results: int = 5, fragments: int = 5
    ):
        """Search the knowledge base for the questions."""

        knowledge_base_indices = [entry.id for entry in knowledge_base]

        return await self._search_by_indices(questions, knowledge_base_indices, results=results, fragments=fragments)

    async def _search_by_indices(self, questions: list[str], index: list[str], results: int = 5, fragments: int = 5):
        """Search the knowledge base for the query."""

        operations = []

        for question in questions:
            operations.append({"index": index})
            operations.append(self._question_to_query(question, size=results, fragments=fragments))

        msearch_results = await self.elasticsearch_client.msearch(searches=operations)

        # We want to translate indices to knowledge bases
        knowledge_bases = await self.get_kb()
        knowledge_base_map = {kb.id: kb for kb in knowledge_bases}

        multi_search_results: list[list[SearchResult]] = []

        for msearch_result in msearch_results["responses"]:
            search_results = []

            if msearch_result.get("error", None):
                err_text = f"Elasticsearch returned an error for query: {msearch_result['error']}"
                raise ElasticsearchSearchError(err_text)

            if not msearch_result.get("hits", {}).get("hits", None):
                err_text = f"Elasticsearch returned no hits for query: {msearch_result}"
                raise ElasticsearchNotFoundError(err_text)

            for hit in msearch_result["hits"]["hits"]:
                search_result = SearchResult.extract_from_hit(hit)

                if knowledge_base := knowledge_base_map.get(hit["_index"], None):
                    search_result.knowledge_base_name = knowledge_base.name

                search_results.append(search_result)

            multi_search_results.append(search_results)

        return multi_search_results

    # endregion KB Search

    # region KB Documents

    async def create_kb_documents(self, knowledge_base: KnowledgeBase, documents: list[dict]):
        """Create a document into a knowledge base."""

        operations = []

        for document in documents:
            operations.append({"index": {"_index": knowledge_base.id}})
            operations.append(document)

        async with self.error_handler("creating documents"):
            await self.elasticsearch_client.bulk(index=knowledge_base.id, operations=operations)

    async def update_kb_document(self, knowledge_base: KnowledgeBase, id: str, document: dict):
        """Update a document into a knowledge base."""

        async with self.error_handler("updating document"):
            await self.elasticsearch_client.update(index=knowledge_base.id, id=id, body=document)

    async def delete_kb_document(self, knowledge_base: KnowledgeBase, id: str):
        """Delete a document into a knowledge base."""

        async with self.error_handler("deleting document"):
            await self.elasticsearch_client.delete(index=knowledge_base.id, id=id)

    def _scoped_index_prefix(self, scope: str) -> str:
        """Generate the Elasticsearch index name using the prefix and a wildcard."""
        return f"{self.index_prefix}-{scope}"

    def _scoped_index_pattern(self, scope: str) -> str:
        """Generate the Elasticsearch index name using the prefix and a wildcard."""
        return f"{self._scoped_index_prefix(scope)}.*"

    def _question_to_query(self, question: str, size: int = 5, fragments: int = 5) -> dict[str, Any]:
        """Convert questions to queries."""
        return {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"headings": {"query": question, "boost": 1}}},
                        {"semantic": {"field": "body", "query": question, "boost": 2}},
                    ]
                }
            },
            "_source": ["title", "url"],
            "size": size,
            "highlight": {"number_of_fragments": fragments, "fragment_size": 500, "fields": {"body": {}}},
        }


# endregion Documents
