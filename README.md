# Elasticsearch Knowledge Base MCP Server

## Overview

This MCP server empowers your AI Assistant to ASK, LEARN, and REMEMBER:
*   **ASK**: Ask questions of the gathered knowledge bases, in plain language like, "What's the best way to use `local_example` in ruby Rspec tests?".
*   **LEARN**: Obtain and index entire documentation stores (e.x. every word of every page of https://docs.pytest.org/en/stable/contents.html) from the Web, git repositories, or the local filesystem.
*   **REMEMBER**: Store working information, user preferences, and rules as "memories" for future reference.

This MCP Server is powered by [Elasticsearch Serverless Search (Start a free trial)](https://www.elastic.co/guide/en/serverless/current/what-is-elasticsearch-serverless.html) for inference, and vector search, and [Elastic Crawler](https://github.com/elastic/crawler) for crawling, parsing, and indexing. 

## Benefits

This MCP Server significantly reduces token usage of the AI Assistant by allowing it to reference specific documentation for the task at hand instead of relying on the AI model's internal knowledge. This allows the AI Assistant to one-shot complex tasks because it doesn't need to guess parameter names, types, or usage. It also allows the AI Assistant to reference documentation as needed without needing to be trained on it.

## Demo

### Searching Documentation

See how you can autonomously search documentation stored in a knowledge base to gather details needed for a task:

https://github.com/user-attachments/assets/64b5fee1-a983-4a92-9485-bfc54f879374

### Crawling Documentation

Watch how you can identify project dependencies and automatically crawl relevant web documentation to build a knowledge base:

https://github.com/user-attachments/assets/c7226aa9-9b40-45fb-877b-8721550e0576


## Configuration

To use this server, the MCP host (e.g., Roo VS Code extension, Cline, VS Code) must be configured with the connection details for the target Elasticsearch cluster, including the host URL and authentication credentials (like an API Key).

This server requires connection details for your Elasticsearch cluster and is configured directly within your MCP host's settings file (e.g., `mcp_settings.json` for the Roo VS Code extension).

The recommended way to run this server is using `uvx`, which handles fetching and running the code directly from GitHub. 

### VS Code 

1. Open the command palette (Ctrl+Shift+P or Cmd+Shift+P).
2. Type "Settings" and select "Preferences: Open User Settings (JSON)".
3. Add the following MCP Server configuration

```json
{
    "mcp": {
        "inputs": [

            {
                "type": "promptString",
                "id": "es-host",
                "description": "Elasticsearch Host",
                "password": false
            },
            {
                "type": "promptString",
                "id": "es-api-key",
                "description": "Elasticsearch API Key",
                "password": false
            }
        ],
        "servers": {
            "External Documentation - GitHub": {
                "command": "uvx",
                "args": [
                    "git+https://github.com/strawgate/es-documentation-manager-mcp"
                ],
                "env": {
                    "ES_HOST": "${input:es-host}",
                    "ES_API_KEY": "${input:es-api-key}",
                },
            }
        }
    }
}
```

### Cline / Roo Code
Add the following configuration block to your `mcpServers` object:

```json
  "Knowledge Base": {
      "command": "uvx",
      "args": [
        "git+https://github.com/strawgate/es-knowledge-base-mcp"
      ],
      "env": {
        "ES_HOST": "https://YOUR_ELASTICSEARCH_HOST_URL:443",
        // --- Authentication: Provide EITHER API Key
        "ES_API_KEY": "YOUR_BASE64_ENCODED_API_KEY",
        // OR Username/Password
        "ES_USERNAME": "YOUR_ELASTICSEARCH_USERNAME",
        "ES_PASSWORD": "YOUR_ELASTICSEARCH_PASSWORD",
      },
      "alwaysAllow": [
        "get_documentation_types",
        "pull_crawler_image",
        "crawl_domains",
        "search_specific_documentation",
        "search_all_documentation",
        "get_document_by_url",
        "get_document_by_title"
      ],
      "disabled": false
    }
```

## Available Tools

The `knowledge-base` server provides the following tools to interact with Elasticsearch knowledge bases:

### Learning from Web Sources

*   **`from_web_documentation`**: Initiate a web crawl starting from a given URL (`url`) to gather information and store it as a new knowledge base. You need to provide a `knowledge_base_name` and `knowledge_base_description`.
*   **`from_web_documentation_request`**: Start a web crawl based on a structured request object (`KnowledgeBaseProto`) containing the name, source URL, and description.
*   **`from_web_documentation_requests`**: Initiate multiple web crawls simultaneously by providing a list of structured request objects (`KnowledgeBaseProto`).

### Memory - Storing Thoughts

*   **`from_thought`**: Save a single piece of information (a "thought") with a `title` and `body` directly into the knowledge base system.
*   **`from_thoughts`**: Save multiple thoughts at once by providing a list of thought objects, each with a `title` and `body`.

### Querying Knowledge

*   **`questions`**: Ask one or more `questions` (as a list of strings) and receive answers based on information across *all* available knowledge bases. You can specify the desired `answer_style` (concise, normal, comprehensive, exhaustive).
*   **`questions_for_kb`**: Ask one or more `questions` targeted at a *specific* knowledge base, identified by its `knowledge_base_name`. You can also specify the `answer_style` as concise, normal, or comprehensive.

## Resources

*   **`kb://entry`**: Access the details (Title, Source, Description) of a specific knowledge base entry using its unique ID or assigned name. 

### Knowledge Base Management

*   **`get`**: Retrieve a list of all existing knowledge base entries.
*   **`get_by_id_or_name`**: Fetch details of a specific knowledge base using its unique ID or assigned name.
*   **`update`**: Modify the name, source URL, or description associated with a knowledge base entry.
*   **`update_name`**: Change only the name of a specific knowledge base entry.
*   **`update_description`**: Change only the description of a specific knowledge base entry.
*   **`delete`**: Remove a specific knowledge base entry entirely.


## Contributing

For details on local development, setup, and contributing to this project, please see the [Contributing Guide](contributing.md).