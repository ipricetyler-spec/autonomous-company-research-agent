from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from research_agent.agent import AgentWorker
from research_agent.cli import load_fixture_inputs
from research_agent.config import Settings
from research_agent.database import Base, Database
from research_agent.events import EventLogger
from research_agent.extractors import FixtureExtractor
from research_agent.research import FixtureResearchTool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "fixtures" / "companies.json"


def test_postgres_skip_locked_concurrent_workers() -> None:
    url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    if not url.endswith("/research_agent_test"):
        pytest.fail("refusing to reset a database not named research_agent_test")

    setup = Database(url)
    Base.metadata.drop_all(setup.engine)
    setup.init()
    setup.enqueue(load_fixture_inputs(limit=12))

    def run_worker(worker_id: str) -> tuple[int, int]:
        database = Database(url)
        settings = Settings(
            database_url=url,
            mode="fixture",
            log_path=None,
            group_delay_seconds=0.002,
        )
        result = AgentWorker(
            database,
            settings,
            FixtureResearchTool(FIXTURES),
            FixtureExtractor(),
            EventLogger(stream=False),
            worker_id=worker_id,
        ).run()
        return result.processed, result.failed

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_worker, ("postgres-worker-a", "postgres-worker-b")))

    status = setup.status()
    assert sum(processed for processed, _ in results) == 12
    assert all(processed > 0 for processed, _ in results)
    assert sum(failed for _, failed in results) == 0
    assert status["jobs"]["complete"] == 12
    assert status["job_claim_attempts"] == 12
    assert status["unique_field_results"] == 180
