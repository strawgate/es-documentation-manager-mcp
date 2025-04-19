"""Errors for the Knowledge Base MCP Server."""


class KnowledgeBaseMCPError(Exception):
    """Base class for all Knowledge Base errors."""

    msg: str = "Generic Knowledge Base error"

    def __init__(self, message: str, original_exception: Exception | None = None):
        super().__init__(message)
        self.msg = message
        self.original_exception = original_exception

    def __str__(self) -> str:
        """Return a user-friendly string representation."""
        cause = self.__cause__
        if cause:
            self.msg += f": {cause}"
        return self.msg


class KnowledgeBaseNotFoundError(KnowledgeBaseMCPError):
    """Raised when the Knowledge Base is not found."""


class LearnError(KnowledgeBaseMCPError):
    """Raised when the crawler encounters an error."""

    msg: str = "Unknown Learn error"


class CrawlerError(LearnError):
    """Raised when the crawler encounters an error."""

    msg: str = "Unknown Crawler error"


class DockerError(CrawlerError):
    """Raised when the crawler encounters a Docker error."""

    msg: str = "Unknown Crawler Docker error"


class DockerImageError(DockerError):
    """Raised when the crawler encounters an error checking or pulling Docker images."""

    msg: str = "Error checking or pulling the Docker image for the Crawler"


class DockerContainerError(DockerError):
    """Raised when the crawler encounters a Docker container error."""

    msg: str = "Error starting the Docker container for the Crawler"


class InvalidConfigurationError(KnowledgeBaseMCPError):
    """Raised when the configuration is invalid."""

    msg: str = "Invalid Configuration provided"


class SearchError(KnowledgeBaseMCPError):
    """Raised when a search operation fails."""

    msg: str = "Unknown Search error"


class ElasticsearchError(SearchError):
    """Raised when an Elasticsearch error occurs."""

    msg: str = "Unknown Elasticsearch error"


class ElasticsearchConnectionError(ElasticsearchError):
    """Raised when the connection to Elasticsearch fails."""

    msg: str = "Unable to connect to Elasticsearch"


class ElasticsearchSearchError(ElasticsearchError):
    """Raised when a search operation fails."""

    msg: str = "Unable to search in Elasticsearch"


class ElasticsearchNotFoundError(ElasticsearchSearchError):
    """Raised when a document is not found in Elasticsearch."""

    msg: str = "Elasticsearch request returned not found"


class UnknownError(KnowledgeBaseMCPError):
    """Raised when an unknown error occurs."""

    msg: str = "Unknown error"
