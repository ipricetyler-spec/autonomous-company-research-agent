from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_agent.schemas import FieldResult, FieldStatus, GroupResult


def test_found_field_requires_source() -> None:
    with pytest.raises(ValidationError, match="source_url"):
        FieldResult(field_name="legal_name", status=FieldStatus.FOUND, value="Example Inc.")


def test_unavailable_field_rejects_value() -> None:
    with pytest.raises(ValidationError, match="cannot contain value"):
        FieldResult(field_name="ceo", status=FieldStatus.NOT_FOUND, value="Nobody")


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unsupported field_name"):
        FieldResult(field_name="private_email", status=FieldStatus.NOT_FOUND)


def test_group_rejects_missing_fields() -> None:
    with pytest.raises(ValidationError, match="must contain exactly"):
        GroupResult(
            group="leadership",
            results=[],
        )


def test_group_rejects_duplicate_fields() -> None:
    result = FieldResult(field_name="ceo", status=FieldStatus.NOT_FOUND)
    with pytest.raises(ValidationError, match="duplicate"):
        GroupResult(group="leadership", results=[result, result])


def test_valid_found_field() -> None:
    result = FieldResult(
        field_name="legal_name",
        status=FieldStatus.FOUND,
        value="Example Inc.",
        source_url="https://example.com/about",
    )
    assert str(result.source_url) == "https://example.com/about"

