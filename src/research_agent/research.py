from __future__ import annotations

import html
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from research_agent.database import Company
from research_agent.schemas import FIELD_GROUPS, SourceDocument


class ResearchError(RuntimeError):
    pass


class TransientResearchError(ResearchError):
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


class OfficialWebsiteResearchTool(ResearchTool):
    """Fetches only user-supplied official domains and a small fixed path allowlist."""

    GROUP_PATHS = {
        "identity": ("/", "/about", "/company"),
        "leadership": ("/leadership", "/about/leadership"),
        "organization": ("/investors", "/about"),
        "commercial": ("/", "/products", "/services"),
        "public_presence": ("/careers", "/news", "/newsroom"),
    }

    def __init__(self, *, timeout: float, max_chars: int) -> None:
        self.timeout = timeout
        self.max_chars = max_chars

    def collect(self, company: Company, group: str) -> list[SourceDocument]:
        if not company.website:
            raise ResearchError("live research requires a company website")
        origin = urlparse(company.website)
        allowed_host = (origin.hostname or "").lower()
        documents: list[SourceDocument] = []
        headers = {"User-Agent": "PortfolioResearchAgent/0.1 (+local educational demo)"}
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            for path in self.GROUP_PATHS[group]:
                url = urljoin(company.website, path)
                try:
                    response = client.get(url)
                    response.raise_for_status()
                except (httpx.TimeoutException, httpx.NetworkError) as error:
                    raise TransientResearchError(str(error)) from error
                except httpx.HTTPStatusError as error:
                    if (
                        error.response.status_code in {408, 425, 429}
                        or error.response.status_code >= 500
                    ):
                        raise TransientResearchError(str(error)) from error
                    continue
                final_host = (response.url.host or "").lower()
                if final_host != allowed_host and not final_host.endswith("." + allowed_host):
                    continue
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    continue
                text = html_to_text(response.text)[: self.max_chars]
                if text:
                    documents.append(
                        SourceDocument(
                            url=str(response.url),
                            title=f"{company.name} official website: {path}",
                            content=text,
                        )
                    )
        if not documents:
            raise ResearchError(f"no usable official pages for {company.name}/{group}")
        return documents
