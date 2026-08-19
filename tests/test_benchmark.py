import json
from pathlib import Path

import pytest

from research_agent.benchmark import (
    BenchmarkError,
    evaluate_predictions,
    load_labels,
    load_predictions,
    normalize_value,
    scope_labels_to_prediction_companies,
)
from research_agent.cli import DEFAULT_BENCHMARK_LABELS

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_normalization_is_field_aware() -> None:
    assert normalize_value("legal_name", "  Example   CORP. ") == "example corp."
    assert normalize_value("official_website", "HTTPS://EXAMPLE.COM:443/") == (
        "https://example.com/"
    )
    assert normalize_value("products_services", ["Cloud", "AI"]) == ["ai", "cloud"]


def test_evaluator_separates_accuracy_coverage_and_unsupported_predictions() -> None:
    labels = {
        ("Example", "legal_name"): "Example Corp.",
        ("Example", "stock_ticker"): "EX",
        ("Example", "industry"): "Technology",
        ("Example", "founded_year"): 2001,
    }
    predictions = {
        ("Example", "legal_name"): {"status": "found", "value": "example corp."},
        ("Example", "stock_ticker"): {"status": "found", "value": "WRONG"},
        ("Example", "industry"): {"status": "not_found", "value": None},
        ("Example", "ceo"): {"status": "found", "value": "A Person"},
    }

    report = evaluate_predictions(labels, predictions)

    assert report["summary"] == {
        "labels": 4,
        "correct": 1,
        "incorrect": 1,
        "abstained": 1,
        "missing": 1,
        "answered": 2,
        "coverage": 0.5,
        "accuracy_overall": 0.25,
        "precision_when_answered": 0.5,
        "unsupported_prediction_count": 1,
    }


def test_loaders_reject_duplicate_rows(tmp_path: Path) -> None:
    labels_path = write_json(
        tmp_path / "labels.json",
        [
            {"name": "Example", "legal_name": "Example"},
            {"name": "Example", "legal_name": "Duplicate"},
        ],
    )
    results_path = write_json(
        tmp_path / "results.json",
        [
            {"company": "Example", "field_name": "legal_name", "status": "found"},
            {"company": "Example", "field_name": "legal_name", "status": "found"},
        ],
    )

    with pytest.raises(BenchmarkError, match="duplicate label"):
        load_labels(labels_path)
    with pytest.raises(BenchmarkError, match="duplicate prediction"):
        load_predictions(results_path)


def test_scope_uses_only_companies_present_in_predictions() -> None:
    labels = {
        ("Included", "legal_name"): "Included Inc.",
        ("Excluded", "legal_name"): "Excluded Inc.",
    }
    predictions = {
        ("Included", "legal_name"): {"status": "found", "value": "Included Inc."}
    }

    assert scope_labels_to_prediction_companies(labels, predictions) == {
        ("Included", "legal_name"): "Included Inc."
    }


def test_load_adjudicated_labels_requires_verified_dated_sources(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "labels.json",
        {
            "schema_version": 2,
            "sources": {
                "example_10k": {
                    "url": "https://www.sec.gov/example",
                    "source_kind": "primary_regulatory_filing",
                    "source_period_end": "2025-12-31",
                    "accessed_at": "2026-08-18",
                }
            },
            "companies": [
                {
                    "name": "Example",
                    "fields": {
                        "legal_name": {
                            "value": "Example Inc.",
                            "source_ids": ["example_10k"],
                            "evidence_locator": "cover page",
                            "reviewed_at": "2026-08-18",
                            "review_status": "verified",
                        }
                    },
                }
            ],
        },
    )

    assert load_labels(path) == {("Example", "legal_name"): "Example Inc."}


def test_load_adjudicated_labels_rejects_unknown_sources(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "labels.json",
        {
            "schema_version": 2,
            "sources": {
                "known": {
                    "url": "https://example.com",
                    "source_kind": "official_company_site",
                    "accessed_at": "2026-08-18",
                }
            },
            "companies": [
                {
                    "name": "Example",
                    "fields": {
                        "legal_name": {
                            "value": "Example Inc.",
                            "source_ids": ["missing"],
                            "evidence_locator": "cover page",
                            "reviewed_at": "2026-08-18",
                            "review_status": "verified",
                        }
                    },
                }
            ],
        },
    )

    with pytest.raises(BenchmarkError, match="unknown sources"):
        load_labels(path)


def test_primary_source_label_set_has_complete_objective_cohort() -> None:
    labels = load_labels(PROJECT_ROOT / "benchmarks" / "primary_source_labels.v1.json")

    assert len({company for company, _field in labels}) == 25
    assert len(labels) == 125
    assert {field for _company, field in labels} == {
        "legal_name",
        "official_website",
        "headquarters",
        "ownership_status",
        "stock_ticker",
    }


def test_cli_default_benchmark_labels_exist() -> None:
    assert DEFAULT_BENCHMARK_LABELS.is_file()
    assert len(load_labels(DEFAULT_BENCHMARK_LABELS)) == 125
