import pytest
from unittest.mock import patch

from es_knowledge_base_mcp.servers.learn import LearnServer


@pytest.mark.asyncio
async def test_extract_urls_from_webpage():
    """Tests the extract_urls_from_webpage tool."""

    with patch("requests.get") as mock_get:
        mock_response = patch("requests.Response").start()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None  # Simulate success
        mock_response.content = """
        <html>
        <body>
            <a href="http://example.com/page1">Link 1</a>
            <a href="/page2">Link 2</a>
            <a href="https://anothersite.com/page3">Link 3</a>
        </body>
        </html>
        """.encode("utf-8")

        mock_get.return_value = mock_response

        urls = await LearnServer.extract_urls_from_webpage(url="http://example.com")

        expected_urls = [
            "http://example.com/page1",
            "http://example.com/page2",
            "https://anothersite.com/page3",
        ]
        assert urls == expected_urls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html_content, expected_urls",
    [
        (
            """
            <html>
            <body>
                <a href="http://example.com/page1">Link 1</a>
                <a href="/page2">Link 2</a>
                <a href="https://anothersite.com/page3">Link 3</a>
            </body>
            </html>
            """,
            sorted(
                [
                    "http://example.com/page1",
                    "http://example.com/page2",
                    "https://anothersite.com/page3",
                ]
            ),
        ),
        (
            """
            <html>
            <body>
                <a href="http://example.com/page1#section1">Link 1</a>
                <a href="/page2?id=5">Link 2</a>
                <a href="http://example.com/page1">Link 3</a>
            </body>
            </html>
            """,
            sorted(
                list(
                    set(
                        [
                            "http://example.com/page1",
                            "http://example.com/page2",
                        ]
                    )
                )
            ),
        ),
        (
            """
            <html>
            <body>
                <a href="/page1">Link 1</a>
                <a href="/page1">Link 2</a>
                <a href="/page1#section1">Link 3</a>
                <a href="/page1?id=5">Link 4</a>
            </body>
            </html>
            """,
            sorted(
                list(
                    set(
                        [
                            "http://example.com/page1",
                        ]
                    )
                )
            ),
        ),
        (
            """
            <html>
            <body>
            </body>
            </html>
            """,
            [],
        ),
    ],
    ids=[
        "Basic HTML with multiple links",
        "HTML with duplicate and parameterized links",
        "HTML with only one link",
        "Empty HTML",
    ],
)
async def test_extract_urls_from_webpage_parametrized(html_content, expected_urls):
    """Tests the extract_urls_from_webpage tool with various inputs."""
    base_url = "http://example.com"
    with patch("requests.get") as mock_get:
        mock_response = patch("requests.Response").start()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None  # Simulate success
        mock_response.content = html_content.encode("utf-8")

        mock_get.return_value = mock_response

        urls = await LearnServer.extract_urls_from_webpage(url=base_url)

        assert urls == expected_urls
