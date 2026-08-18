from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, model_validator


class FieldStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    SOURCE_UNREACHABLE = "source_unreachable"
    VALIDATION_FAILED = "validation_failed"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("legal_name", "official_website", "headquarters", "founded_year", "industry"),
    "leadership": ("ceo",),
    "organization": ("employee_count_estimate", "ownership_status", "stock_ticker"),
    "commercial": ("description", "products_services", "geographic_markets"),
    "public_presence": ("careers_url", "linkedin_url", "recent_development"),
}
ALLOWED_FIELDS = frozenset(field for fields in FIELD_GROUPS.values() for field in fields)
URL_VALUE_FIELDS = frozenset({"official_website", "careers_url", "linkedin_url"})
OWNERSHIP_VALUES = frozenset(
    {"public", "private", "subsidiary", "nonprofit", "government", "cooperative"}
)
UNAVAILABLE_PLACEHOLDERS = frozenset(
    {"not found", "unknown", "n/a", "na", "none", "null", "unavailable"}
)
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
_TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FieldResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str
    status: FieldStatus
    value: Any | None = None
    source_url: HttpUrl | None = None
    source_title: str | None = Field(default=None, max_length=300)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_status_contract(self) -> FieldResult:
        if self.field_name not in ALLOWED_FIELDS:
            raise ValueError(f"unsupported field_name: {self.field_name}")
        if self.status is FieldStatus.FOUND:
            if self.value is None or self.value == "":
                raise ValueError("found results require a non-empty value")
            if self.source_url is None:
                raise ValueError("found results require source_url")
            if (
                isinstance(self.value, str)
                and self.value.strip().casefold() in UNAVAILABLE_PLACEHOLDERS
            ):
                raise ValueError("unavailable placeholder cannot use found status")
            if self.field_name in URL_VALUE_FIELDS:
                _HTTP_URL_ADAPTER.validate_python(self.value)
            elif self.field_name == "founded_year":
                current_year = datetime.now(UTC).year
                if isinstance(self.value, bool) or not isinstance(self.value, int):
                    raise ValueError("founded_year must be an integer")
                if not 1600 <= self.value <= current_year:
                    raise ValueError("founded_year is outside the supported range")
            elif self.field_name == "employee_count_estimate":
                if (
                    isinstance(self.value, bool)
                    or not isinstance(self.value, int)
                    or self.value < 1
                ):
                    raise ValueError("employee_count_estimate must be a positive integer")
            elif self.field_name == "ownership_status":
                if not isinstance(self.value, str) or self.value.casefold() not in OWNERSHIP_VALUES:
                    raise ValueError(f"ownership_status must be one of {sorted(OWNERSHIP_VALUES)}")
            elif self.field_name == "stock_ticker":
                if not isinstance(self.value, str) or not _TICKER.fullmatch(self.value):
                    raise ValueError("stock_ticker must be an uppercase market symbol")
            elif self.field_name == "products_services":
                if not isinstance(self.value, list) or not self.value or not all(
                    isinstance(item, str) and item.strip() for item in self.value
                ):
                    raise ValueError("products_services must be a non-empty string list")
        elif self.value is not None or self.source_url is not None:
            raise ValueError("unavailable results cannot contain value or source_url")
        return self


class GroupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str
    results: list[FieldResult]

    @model_validator(mode="after")
    def validate_group(self) -> GroupResult:
        expected = FIELD_GROUPS.get(self.group)
        if expected is None:
            raise ValueError(f"unsupported group: {self.group}")
        names = [item.field_name for item in self.results]
        if len(names) != len(set(names)):
            raise ValueError("duplicate field_name in group")
        if set(names) != set(expected):
            raise ValueError(f"group {self.group} must contain exactly {sorted(expected)}")
        return self


class CompanyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=300)
    website: HttpUrl | None = None
    fixture_key: str | None = Field(default=None, max_length=100)
