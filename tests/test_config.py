from __future__ import annotations

import pytest

from research_agent.config import Settings


def test_from_env_uses_concrete_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL",
        "RESEARCH_AGENT_MODE",
        "LOG_PATH",
        "LEASE_SECONDS",
        "MAX_RETRIES",
        "BACKOFF_BASE_SECONDS",
        "REQUEST_TIMEOUT_SECONDS",
        "MAX_SOURCE_CHARS",
        "LLM_STRUCTURED_OUTPUT",
        "LLM_MAX_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.lease_seconds == 30
    assert settings.database_url == "sqlite:///data/research_agent.db"
    assert settings.llm_structured_output == "json_schema"
    assert settings.llm_max_tokens == 2000


def test_live_mode_requires_provider_configuration() -> None:
    with pytest.raises(ValueError, match="live mode requires"):
        Settings.from_env(mode="live", llm_base_url=None, llm_api_key=None, llm_model=None)


def test_unknown_structured_output_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="LLM_STRUCTURED_OUTPUT"):
        Settings.from_env(llm_structured_output="wishful")

