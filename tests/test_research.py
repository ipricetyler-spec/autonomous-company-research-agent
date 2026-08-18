import httpx
import pytest

from research_agent.database import Company
from research_agent.research import (
    OfficialWebsiteResearchTool,
    html_to_text,
    is_allowed_host,
)


def test_html_to_text_removes_scripts_styles_and_tags() -> None:
    page = "<style>.secret{}</style><h1>Company</h1><script>ignore()</script><p>Profile</p>"
    assert html_to_text(page) == "Company Profile"


def test_official_domain_policy_allows_sibling_subdomains() -> None:
    assert is_allowed_host("www.microsoft.com", "careers.microsoft.com")
    assert is_allowed_host("www.microsoft.com", "microsoft.com")
    assert not is_allowed_host("www.microsoft.com", "microsoft.example")


def test_live_research_deduplicates_redirected_final_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/about":
            return httpx.Response(302, headers={"location": "/"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=f"<h1>{request.url.path}</h1>",
        )

    original_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs: object) -> httpx.Client:
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr("research_agent.research.httpx.Client", client_factory)
    company = Company(name="Example Corp", website="https://example.com/")
    documents = OfficialWebsiteResearchTool(timeout=1, max_chars=1000).collect(
        company, "identity"
    )

    assert [str(document.url) for document in documents] == [
        "https://example.com/",
        "https://example.com/company",
    ]
    assert [document.title for document in documents] == [
        "Example Corp official website: /",
        "Example Corp official website: /company",
    ]

