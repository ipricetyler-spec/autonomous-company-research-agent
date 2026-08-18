from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from research_agent.database import Company
from research_agent.extractors import (
    ExtractionError,
    OpenAICompatibleExtractor,
    TransientExtractionError,
    group_json_schema,
)
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


def test_live_extractor_requests_strict_group_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    document = source()
    captured: dict[str, Any] = {}

    def fake_post(*args: Any, **kwargs: Any) -> FakeResponse:
        captured.update(kwargs["json"])
        return FakeResponse(leadership_payload(str(document.url)))

    monkeypatch.setattr("research_agent.extractors.httpx.post", fake_post)
    extractor().extract(Company(name="Example"), "leadership", [document])
    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert schema == group_json_schema("leadership")
    assert schema["properties"]["results"]["minItems"] == 1
    result_schema = schema["properties"]["results"]["items"]
    assert result_schema["properties"]["evidence"] == {"type": "null"}
    assert result_schema["properties"]["confidence"] == {"type": "null"}


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


def test_live_extractor_classifies_duplicate_fields_as_extraction_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = source()
    payload = json.loads(leadership_payload(str(document.url)))
    payload["results"].append(dict(payload["results"][0]))
    monkeypatch.setattr(
        "research_agent.extractors.httpx.post",
        lambda *args, **kwargs: FakeResponse(json.dumps(payload)),
    )
    with pytest.raises(ExtractionError, match="duplicate"):
        extractor().extract(Company(name="Example"), "leadership", [document])


def test_live_extractor_isolates_semantically_invalid_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = json.dumps(
        {
            "group": "leadership",
            "results": [
                {
                    "field_name": "ceo",
                    "status": "found",
                    "value": "Not found",
                    "source_url": str(source().url),
                    "source_title": "model title",
                    "retrieved_at": "2026-01-01T00:00:00Z",
                    "confidence": None,
                    "evidence": None,
                }
            ],
        }
    )
    monkeypatch.setattr(
        "research_agent.extractors.httpx.post",
        lambda *args, **kwargs: FakeResponse(invalid),
    )
    result = extractor().extract(Company(name="Example"), "leadership", [source()])
    assert result.results[0].status.value == "validation_failed"
    assert result.results[0].value is None
    assert "placeholder" in (result.results[0].evidence or "")


def test_live_extractor_classifies_protocol_disconnect_as_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("POST", "http://127.0.0.1:11434/v1/chat/completions")

    def disconnect(*args: Any, **kwargs: Any) -> FakeResponse:
        raise httpx.RemoteProtocolError("disconnected", request=request)

    monkeypatch.setattr("research_agent.extractors.httpx.post", disconnect)
    with pytest.raises(TransientExtractionError, match="disconnected"):
        extractor().extract(Company(name="Example"), "leadership", [source()])
