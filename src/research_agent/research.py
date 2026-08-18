from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from research_agent.database import Company
from research_agent.schemas import FIELD_GROUPS, SourceDocument


class ResearchError(RuntimeError):
    pass


class TransientResearchError(ResearchError):
    pass


class UnsafeNetworkTargetError(ResearchError):
    pass


class ResearchTool(ABC):
    @abstractmethod
    def collect(self, company: Company, group: str) -> list[SourceDocument]:
        """Use approved sources to gather evidence for one field group."""


class FixtureResearchTool(ResearchTool):
    def __init__(self, fixture_path: Path) -> None:
        records = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.records = {record["key"]: record for record in records}

    def collect(self, company: Company, group: str) -> list[SourceDocument]:
        record = self.records.get(company.fixture_key or "")
        if record is None:
            raise ResearchError(f"no fixture record for {company.name}")
        source_url = record["website"]
        fields = {
            field: record.get(field)
            for field in FIELD_GROUPS[group]
            if record.get(field) is not None
        }
        return [
            SourceDocument(
                url=source_url,
                title=f"Deterministic replay profile: {record['name']}",
                content=json.dumps(
                    {
                        "fixture_snapshot": "2026-08-18",
                        "company": record["name"],
                        "group": group,
                        "fields": fields,
                    },
                    sort_keys=True,
                ),
            )
        ]


_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def html_to_text(body: str) -> str:
    body = _SCRIPT_STYLE.sub(" ", body)
    body = _TAGS.sub(" ", body)
    return _SPACE.sub(" ", html.unescape(body)).strip()


def is_allowed_host(imported_host: str, final_host: str) -> bool:
    allowed_domain = imported_host.lower().removeprefix("www.")
    candidate = final_host.lower()
    return candidate == allowed_domain or candidate.endswith("." + allowed_domain)


Resolver = Callable[..., list[tuple[object, object, object, object, tuple[object, ...]]]]


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value.split("%", 1)[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global


def resolve_public_addresses(
    hostname: str,
    port: int,
    *,
    resolver: Resolver = socket.getaddrinfo,
) -> frozenset[str]:
    """Resolve a hostname and reject any non-public answer before a connection is attempted."""

    try:
        answers = resolver(hostname, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise TransientResearchError(f"DNS resolution failed for {hostname}") from error
    addresses = frozenset(str(answer[4][0]).split("%", 1)[0] for answer in answers)
    if not addresses:
        raise TransientResearchError(f"DNS resolution returned no addresses for {hostname}")
    blocked = sorted(address for address in addresses if not _is_public_address(address))
    if blocked:
        raise UnsafeNetworkTargetError(
            f"blocked non-public network target for {hostname}: {', '.join(blocked)}"
        )
    return addresses


def validate_public_url(
    url: str,
    imported_host: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
) -> frozenset[str]:
    """Apply the live-mode URL, domain, credential, port, and DNS policy."""

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise UnsafeNetworkTargetError("live research permits only absolute HTTP(S) URLs")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeNetworkTargetError("URL credentials are not permitted")
    if not is_allowed_host(imported_host, hostname):
        raise UnsafeNetworkTargetError(f"redirect left the imported official domain: {hostname}")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise UnsafeNetworkTargetError("URL contains an invalid port") from error
    if port not in {80, 443}:
        raise UnsafeNetworkTargetError(f"nonstandard network port is not permitted: {port}")
    return resolve_public_addresses(hostname, port, resolver=resolver)


def _validate_connected_peer(response: httpx.Response) -> None:
    """Reject a non-public connected peer when HTTPX exposes the socket address."""

    stream = response.extensions.get("network_stream")
    get_extra_info = getattr(stream, "get_extra_info", None)
    if not callable(get_extra_info):
        return
    peer = get_extra_info("server_addr")
    if isinstance(peer, tuple) and peer and isinstance(peer[0], str):
        try:
            public = _is_public_address(peer[0])
        except ValueError as error:
            raise UnsafeNetworkTargetError("connected peer address is invalid") from error
        if not public:
            raise UnsafeNetworkTargetError(f"blocked non-public connected peer: {peer[0]}")


class OfficialWebsiteResearchTool(ResearchTool):
    """Fetches only user-supplied official domains and a small fixed path allowlist."""

    GROUP_PATHS = {
        "identity": ("/", "/about", "/company"),
        "leadership": ("/leadership", "/about/leadership"),
        "organization": ("/investors", "/about"),
        "commercial": ("/", "/products", "/services"),
        "public_presence": ("/careers", "/news", "/newsroom"),
    }

    def __init__(
        self,
        *,
        timeout: float,
        max_chars: int,
        resolver: Resolver = socket.getaddrinfo,
        max_redirects: int = 5,
    ) -> None:
        self.timeout = timeout
        self.max_chars = max_chars
        self.resolver = resolver
        self.max_redirects = max_redirects

    def _get(self, client: httpx.Client, url: str, imported_host: str) -> httpx.Response:
        current_url = url
        for redirect_count in range(self.max_redirects + 1):
            validate_public_url(current_url, imported_host, resolver=self.resolver)
            response = client.get(current_url)
            _validate_connected_peer(response)
            if not response.is_redirect:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            if redirect_count >= self.max_redirects:
                raise ResearchError(f"redirect limit exceeded for {url}")
            current_url = urljoin(str(response.url), location)
        raise AssertionError("redirect loop terminated unexpectedly")

    def collect(self, company: Company, group: str) -> list[SourceDocument]:
        if not company.website:
            raise ResearchError("live research requires a company website")
        origin = urlparse(company.website)
        allowed_host = (origin.hostname or "").lower()
        documents: list[SourceDocument] = []
        seen_urls: set[str] = set()
        collected_chars = 0
        headers = {"User-Agent": "PortfolioResearchAgent/0.1 (+local educational demo)"}
        with httpx.Client(timeout=self.timeout, follow_redirects=False, headers=headers) as client:
            for path in self.GROUP_PATHS[group]:
                url = urljoin(company.website, path)
                try:
                    response = self._get(client, url, allowed_host)
                    response.raise_for_status()
                except httpx.TransportError as error:
                    raise TransientResearchError(str(error)) from error
                except httpx.HTTPStatusError as error:
                    if (
                        error.response.status_code in {408, 425, 429}
                        or error.response.status_code >= 500
                    ):
                        raise TransientResearchError(str(error)) from error
                    continue
                final_host = (response.url.host or "").lower()
                if not is_allowed_host(allowed_host, final_host):
                    continue
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    continue
                final_url = str(response.url)
                if final_url in seen_urls:
                    continue
                remaining_chars = self.max_chars - collected_chars
                if remaining_chars <= 0:
                    break
                text = html_to_text(response.text)[:remaining_chars]
                if text:
                    documents.append(
                        SourceDocument(
                            url=final_url,
                            title=f"{company.name} official website: {response.url.path or '/'}",
                            content=text,
                        )
                    )
                    seen_urls.add(final_url)
                    collected_chars += len(text)
        if not documents:
            raise ResearchError(f"no usable official pages for {company.name}/{group}")
        return documents
