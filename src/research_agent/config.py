from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///data/research_agent.db"
    mode: str = "fixture"
    log_path: str | None = "data/events.jsonl"
    lease_seconds: int = 30
    max_retries: int = 3
    backoff_base_seconds: float = 0.2
    request_timeout_seconds: float = 15.0
    max_source_chars: int = 40_000
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    group_delay_seconds: float = 0.0

    @classmethod
    def from_env(cls, **overrides: object) -> Settings:
        defaults = cls()
        values: dict[str, object] = {
            "database_url": os.getenv("DATABASE_URL", defaults.database_url),
            "mode": os.getenv("RESEARCH_AGENT_MODE", defaults.mode),
            "log_path": os.getenv("LOG_PATH", defaults.log_path),
            "lease_seconds": _positive_int("LEASE_SECONDS", defaults.lease_seconds),
            "max_retries": _positive_int("MAX_RETRIES", defaults.max_retries),
            "backoff_base_seconds": _positive_float(
                "BACKOFF_BASE_SECONDS", defaults.backoff_base_seconds
            ),
            "request_timeout_seconds": _positive_float(
                "REQUEST_TIMEOUT_SECONDS", defaults.request_timeout_seconds
            ),
            "max_source_chars": _positive_int("MAX_SOURCE_CHARS", defaults.max_source_chars),
            "llm_base_url": os.getenv("LLM_BASE_URL"),
            "llm_api_key": os.getenv("LLM_API_KEY"),
            "llm_model": os.getenv("LLM_MODEL"),
            "group_delay_seconds": float(os.getenv("GROUP_DELAY_SECONDS", "0")),
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        settings = cls(**values)
        if settings.mode not in {"fixture", "live"}:
            raise ValueError("RESEARCH_AGENT_MODE must be 'fixture' or 'live'")
        if settings.mode == "live" and not all(
            (settings.llm_base_url, settings.llm_api_key, settings.llm_model)
        ):
            raise ValueError("live mode requires LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL")
        return settings
