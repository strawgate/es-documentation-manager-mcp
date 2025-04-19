import pytest

from es_knowledge_base_mcp.clients.elasticsearch import url_to_index_name


@pytest.mark.parametrize(
    "url, expected_index_name",
    [
        ("http://www.python.org/docs/index.html", "www_python_org.docs.index_html"),
        ("https://www.python.org/docs/index.html", "www_python_org.docs.index_html"),
        ("https://example.com/path/to/resource?query=1", "example_com.path.to.resourcequery1"),
        (
            "https://example.com/very-long-path/that-exceeds-the-fifty-character-limit/by-quite-a-bit",
            "example_com.very_long_path.that_exceeds_the_fifty",
        ),
        ("https://domain_with_underscores.com/path", "domain_with_underscores_com.path"),
        ("https://domain-with-hyphens.com/path", "domain_with_hyphens_com.path"),
        ("https://example.com/path#fragment", "example_com.pathfragment"),
        ("example.com", "example_com"),
        ("http://localhost:8000/api/v1", "localhost8000.api.v1"),
        ("https://!@#$%^&*().com/", "com"),
        ("https://a_b-c.d/e.f-g/h", "a_b_c_d.e_f_g.h"),
        (
            "https://this.is.a.very.long.domain.name.that.will.surely.be.truncated/path",
            "this_is_a_very_long_domain_name_that_will_surely_b",
        ),
        ("http://127.0.0.1/", "127_0_0_1"),
        ("", ""),  # Empty input
        ("https://Example.com/Path", "example_com.path"),
    ],
)
def test_url_to_index_name(url: str, expected_index_name: str):
    """
    Tests the url_to_index_name function with various inputs.
    """
    assert url_to_index_name(url) == expected_index_name
