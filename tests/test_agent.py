from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import update

from research_agent.agent import AgentWorker
from research_agent.cli import load_fixture_inputs
from research_agent.config import Settings
from research_agent.database import Company, Database, Job, utcnow
from research_agent.events import EventLogger
from research_agent.extractors import ExtractionError, Extractor, FixtureExtractor
from research_agent.research import FixtureResearchTool, ResearchTool, TransientResearchError
from research_agent.schemas import GroupResult, SourceDocument

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "fixtures" / "companies.json"


def settings(database: Database, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": database.url,
        "mode": "fixture",
        "log_path": None,
        "lease_seconds": 30,
        "max_retries": 2,
        "backoff_base_seconds": 0.001,
    }
    values.update(overrides)
    return Settings(**values)


def worker(
    database: Database,
    research: ResearchTool | None = None,
    extractor: Extractor | None = None,
    **overrides: object,
) -> AgentWorker:
    return AgentWorker(
        database,
        settings(database, **overrides),
        research or FixtureResearchTool(FIXTURES),
        extractor or FixtureExtractor(),
        EventLogger(stream=False),
        worker_id="test-worker",
    )


def test_worker_processes_multiple_companies_unattended(database: Database) -> None:
    database.enqueue(load_fixture_inputs(limit=2))
    result = worker(database).run()
    status = database.status()
    assert result.processed == 2
    assert result.failed == 0
    assert status["jobs"]["complete"] == 2
    assert status["unique_field_results"] == 30


class TransientOnceResearch(ResearchTool):
    def __init__(self) -> None:
        self.delegate = FixtureResearchTool(FIXTURES)
        self.failed = False

    def collect(self, company: Company, group: str) -> list[SourceDocument]:
        if not self.failed:
            self.failed = True
            raise TransientResearchError("simulated timeout")
        return self.delegate.collect(company, group)


def test_transient_tool_failure_is_retried_and_counted(database: Database) -> None:
    database.enqueue(load_fixture_inputs(limit=1))
    result = worker(database, research=TransientOnceResearch()).run()
    assert result.processed == 1
    assert database.status()["retries"] == 1


class MalformedLeadershipExtractor(Extractor):
    def __init__(self) -> None:
        self.delegate = FixtureExtractor()

    def extract(
        self, company: Company, group: str, sources: list[SourceDocument]
    ) -> GroupResult:
        if group == "leadership":
            raise ExtractionError("simulated malformed model JSON")
        return self.delegate.extract(company, group, sources)


def test_malformed_group_is_isolated_and_checkpointed(database: Database) -> None:
    database.enqueue(load_fixture_inputs(limit=1))
    result = worker(database, extractor=MalformedLeadershipExtractor()).run()
    status = database.status()
    assert result.processed == 1
    assert result.failed == 0
    assert status["fields"]["validation_failed"] == 1
    assert status["validation_failures"] == 1
    assert status["retries"] == 1


class MalformedIdentityExtractor(Extractor):
    def __init__(self) -> None:
        self.delegate = FixtureExtractor()

    def extract(
        self, company: Company, group: str, sources: list[SourceDocument]
    ) -> GroupResult:
        if group == "identity":
            raise ExtractionError("simulated malformed multi-field model JSON")
        return self.delegate.extract(company, group, sources)


def test_validation_counter_counts_every_isolated_field(database: Database) -> None:
    database.enqueue(load_fixture_inputs(limit=1))
    result = worker(database, extractor=MalformedIdentityExtractor()).run()
    status = database.status()
    assert result.processed == 1
    assert result.failed == 0
    assert status["fields"]["validation_failed"] == 5
    assert status["validation_failures"] == 5
    assert status["retries"] == 1


class FatalFirstCompanyExtractor(Extractor):
    def __init__(self, first_company: str) -> None:
        self.first_company = first_company
        self.delegate = FixtureExtractor()

    def extract(
        self, company: Company, group: str, sources: list[SourceDocument]
    ) -> GroupResult:
        if company.name == self.first_company:
            raise RuntimeError("simulated company-local fatal error")
        return self.delegate.extract(company, group, sources)


def test_fatal_company_does_not_stop_later_job(database: Database) -> None:
    inputs = load_fixture_inputs(limit=2)
    database.enqueue(inputs)
    result = worker(
        database,
        extractor=FatalFirstCompanyExtractor(inputs[0].name),
    ).run()
    status = database.status()
    assert result.failed == 1
    assert result.processed == 1
    assert status["jobs"]["failed"] == 1
    assert status["jobs"]["complete"] == 1


def test_worker_resumes_from_persisted_group_checkpoint(database: Database) -> None:
    database.enqueue(load_fixture_inputs(limit=1))
    database.begin_run("interrupted-run", "old-worker", "fixture")
    job, company = database.claim("old-worker", "interrupted-run", 30) or (None, None)
    assert job is not None and company is not None
    research = FixtureResearchTool(FIXTURES)
    identity = FixtureExtractor().extract(
        company, "identity", research.collect(company, "identity")
    )
    database.save_group(job.id, "old-worker", "identity", identity.results, 30)
    with database.session() as session:
        session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(lease_until=utcnow() - timedelta(seconds=1))
        )

    result = worker(database).run()
    status = database.status()
    assert result.recovered == 1
    assert status["jobs"]["complete"] == 1
    assert status["job_claim_attempts"] == 2
    assert status["unique_field_results"] == 15
