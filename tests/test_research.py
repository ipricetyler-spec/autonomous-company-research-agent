import httpx
import pytest

from research_agent.database import Company
from research_agent.research import (
    OfficialWebsiteResearchTool,
    UnsafeNetworkTargetError,
    html_to_text,
    is_allowed_host,
    resolve_public_addresses,
    validate_public_url,
)


def public_resolver(
    host: str, port: int, **kwargs: object
) -> list[tuple[object, object, object, object, tuple[object, ...]]]:
    del host, port, kwargs
    return [(None, None, None, None, ("93.184.216.34", 0))]


def test_html_to_text_removes_scripts_styles_and_tags() -> None:
    page = "<style>.secret{}</style><h1>Company</h1><script>ignore()</script><p>Profile</p>"
    assert html_to_text(page) == "Company Profile"


def test_official_domain_policy_allows_sibling_subdomains() -> None:
    assert is_allowed_host("www.microsoft.com", "careers.microsoft.com")
    assert is_allowed_host("www.microsoft.com", "microsoft.com")
    assert not is_allowed_host("www.microsoft.com", "microsoft.example")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "192.168.1.10",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
    ],
)
def test_dns_policy_rejects_non_public_answers(address: str) -> None:
    def resolver(
        host: str, port: int, **kwargs: object
    ) -> list[tuple[object, object, object, object, tuple[object, ...]]]:
        del host, port, kwargs
        return [(None, None, None, None, (address, 0))]

    with pytest.raises(UnsafeNetworkTargetError, match="non-public network target"):
        resolve_public_addresses("example.com", 443, resolver=resolver)


def test_dns_policy_rejects_mixed_public_and_private_answers() -> None:
    def resolver(
        host: str, port: int, **kwargs: object
    ) -> list[tuple[object, object, object, object, tuple[object, ...]]]:
        del host, port, kwargs
        return [
            (None, None, None, None, ("93.184.216.34", 0)),
            (None, None, None, None, ("127.0.0.1", 0)),
        ]

    with pytest.raises(UnsafeNetworkTargetError, match="127.0.0.1"):
        resolve_public_addresses("example.com", 443, resolver=resolver)


def test_url_policy_rejects_credentials_ports_and_cross_domain_redirects() -> None:
    with pytest.raises(UnsafeNetworkTargetError, match="credentials"):
        validate_public_url(
            "https://user:secret@example.com/", "example.com", resolver=public_resolver
        )
    with pytest.raises(UnsafeNetworkTargetError, match="nonstandard network port"):
        validate_public_url("https://example.com:8443/", "example.com", resolver=public_resolver)
    with pytest.raises(UnsafeNetworkTargetError, match="left the imported"):
        validate_public_url("https://attacker.example/", "example.com", resolver=public_resolver)


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
    documents = OfficialWebsiteResearchTool(
        timeout=1, max_chars=1000, resolver=public_resolver
    ).collect(
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


def test_cross_domain_redirect_is_blocked_before_followup_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    original_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs: object) -> httpx.Client:
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr("research_agent.research.httpx.Client", client_factory)
    company = Company(name="Example Corp", website="https://example.com/")
    with pytest.raises(UnsafeNetworkTargetError, match="left the imported"):
        OfficialWebsiteResearchTool(
            timeout=1, max_chars=1000, resolver=public_resolver
        ).collect(company, "identity")

    assert requested == ["https://example.com/"]


def test_connected_private_peer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class PrivateStream:
        def get_extra_info(self, name: str) -> tuple[str, int] | None:
            return ("127.0.0.1", 443) if name == "server_addr" else None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<h1>Example</h1>",
            extensions={"network_stream": PrivateStream()},
        )

    original_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs: object) -> httpx.Client:
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr("research_agent.research.httpx.Client", client_factory)
    company = Company(name="Example Corp", website="https://example.com/")

    with pytest.raises(UnsafeNetworkTargetError, match="connected peer"):
        OfficialWebsiteResearchTool(
            timeout=1, max_chars=1000, resolver=public_resolver
        ).collect(company, "identity")

