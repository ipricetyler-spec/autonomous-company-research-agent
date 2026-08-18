from __future__ import annotations

import json
from typing import Any

import pytest

from research_agent.database import Company
from research_agent.extractors import ExtractionError, OpenAICompatibleExtractor
from research_agent.schemas import SourceDocument


class FakeResponse:
    status_code = 200

    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": self.content}}]}


def extractor() -> OpenAICompatibleExtractor:
    return OpenAICompatibleExtractor(
        base_url="https://model.example/v1",
        api_key="test-key",
        model="test-model",
        timeout=1,
    )


def source() -> SourceDocument:
    return SourceDocument(
        url="https://company.example/leadership",
        title="Leadership",
        content="Evidence text only.",
    )


def leadership_payload(source_url: str) -> str:
    return json.dumps(
        {
            "group": "leadership",
            "results": [
                {
                    "field_name": "ceo",
                    "status": "found",
                    "value": "Example Person",
                    "source_url": source_url,
                }
            ],
        }
    )


def test_live_extractor_accepts_only_valid_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = source()
    monkeypatch.setattr(
        "research_agent.extractors.httpx.post",
        lambda *args, **kwargs: FakeResponse(leadership_payload(str(document.url))),
    )
    result = extractor().extract(Company(name="Example"), "leadership", [document])
    assert result.results[0].value == "Example Person"


def test_live_extractor_rejects_unsupplied_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "research_agent.extractors.httpx.post",
        lambda *args, **kwargs: FakeResponse(
            leadership_payload("https://untrusted.example/fabricated")
        ),
    )
    with pytest.raises(ExtractionError, match="unsupplied URL"):
        extractor().extract(Company(name="Example"), "leadership", [source()])


def test_live_extractor_rejects_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "research_agent.extractors.httpx.post",
        lambda *args, **kwargs: FakeResponse("not json"),
    )
    with pytest.raises(ExtractionError, match="invalid model output"):
        extractor().extract(Company(name="Example"), "leadership", [source()])
