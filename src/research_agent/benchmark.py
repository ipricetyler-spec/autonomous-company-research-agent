from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from research_agent.schemas import ALLOWED_FIELDS, URL_VALUE_FIELDS


class BenchmarkError(ValueError):
    pass


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.casefold().split())


def _normalize_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return _normalize_text(value)
    port = parsed.port
    default_port = (parsed.scheme == "http" and port == 80) or (
        parsed.scheme == "https" and port == 443
    )
    host = parsed.hostname.casefold()
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), netloc, path, parsed.query, ""))


def normalize_value(field_name: str, value: Any) -> Any:
    if isinstance(value, str):
        if field_name in URL_VALUE_FIELDS:
            return _normalize_url(value)
        return _normalize_text(value)
    if isinstance(value, list):
        return sorted(normalize_value(field_name, item) for item in value)
    return value


def load_labels(path: Path) -> dict[tuple[str, str], Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise BenchmarkError("labels must be a JSON array")
    labels: dict[tuple[str, str], Any] = {}
    for company in raw:
        if not isinstance(company, dict) or not isinstance(company.get("name"), str):
            raise BenchmarkError("every label record requires a company name")
        company_name = company["name"]
        for field_name in ALLOWED_FIELDS:
            if field_name not in company or company[field_name] is None:
                continue
            key = (company_name, field_name)
            if key in labels:
                raise BenchmarkError(f"duplicate label: {company_name}/{field_name}")
            labels[key] = company[field_name]
    if not labels:
        raise BenchmarkError("labels contain no supported field values")
    return labels


def load_predictions(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise BenchmarkError("predictions must be a JSON array")
    predictions: dict[tuple[str, str], dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            raise BenchmarkError("every prediction must be an object")
        company = row.get("company")
        field_name = row.get("field_name")
        status = row.get("status")
        if not all(isinstance(value, str) for value in (company, field_name, status)):
            raise BenchmarkError("predictions require company, field_name, and status strings")
        key = (company, field_name)
        if key in predictions:
            raise BenchmarkError(f"duplicate prediction: {company}/{field_name}")
        predictions[key] = row
    return predictions


def _blank_counts() -> dict[str, int]:
    return {"labels": 0, "correct": 0, "incorrect": 0, "abstained": 0, "missing": 0}


def evaluate_predictions(
    labels: dict[tuple[str, str], Any],
    predictions: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    totals = _blank_counts()
    per_field: dict[str, dict[str, int]] = defaultdict(_blank_counts)
    errors: list[dict[str, Any]] = []
    for (company, field_name), expected in sorted(labels.items()):
        totals["labels"] += 1
        per_field[field_name]["labels"] += 1
        prediction = predictions.get((company, field_name))
        if prediction is None:
            outcome = "missing"
        elif prediction["status"] != "found":
            outcome = "abstained"
        elif normalize_value(field_name, prediction.get("value")) == normalize_value(
            field_name, expected
        ):
            outcome = "correct"
        else:
            outcome = "incorrect"
        totals[outcome] += 1
        per_field[field_name][outcome] += 1
        if outcome != "correct":
            errors.append(
                {
                    "company": company,
                    "field_name": field_name,
                    "outcome": outcome,
                    "expected": expected,
                    "predicted_status": prediction.get("status") if prediction else None,
                    "predicted_value": prediction.get("value") if prediction else None,
                }
            )

    answered = totals["correct"] + totals["incorrect"]
    unsupported = sorted(
        {key for key in predictions if key not in labels}, key=lambda item: (item[0], item[1])
    )
    return {
        "schema_version": 1,
        "summary": {
            **totals,
            "answered": answered,
            "coverage": answered / totals["labels"],
            "accuracy_overall": totals["correct"] / totals["labels"],
            "precision_when_answered": totals["correct"] / answered if answered else None,
            "unsupported_prediction_count": len(unsupported),
        },
        "per_field": dict(sorted(per_field.items())),
        "errors": errors,
        "unsupported_predictions": [
            {"company": company, "field_name": field_name} for company, field_name in unsupported
        ],
    }


def scope_labels_to_prediction_companies(
    labels: dict[tuple[str, str], Any],
    predictions: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], Any]:
    companies = {company for company, _field_name in predictions}
    scoped = {key: value for key, value in labels.items() if key[0] in companies}
    if not scoped:
        raise BenchmarkError("no prediction companies match the label set")
    return scoped
