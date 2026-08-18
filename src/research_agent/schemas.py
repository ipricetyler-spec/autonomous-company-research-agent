from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


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
