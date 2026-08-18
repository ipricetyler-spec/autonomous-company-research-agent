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
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.lease_seconds == 30
    assert settings.database_url == "sqlite:///data/research_agent.db"


def test_live_mode_requires_provider_configuration() -> None:
    with pytest.raises(ValueError, match="live mode requires"):
        Settings.from_env(mode="live", llm_base_url=None, llm_api_key=None, llm_model=None)

