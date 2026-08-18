from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from sqlalchemy import update

from research_agent.database import Database, FieldResultRow, Job, utcnow
from research_agent.schemas import CompanyInput, FieldResult, FieldStatus


def company(name: str, key: str = "microsoft") -> CompanyInput:
    return CompanyInput(name=name, website="https://example.com/", fixture_key=key)


def test_enqueue_is_idempotent(database: Database) -> None:
    assert database.enqueue([company("One")]) == 1
    assert database.enqueue([company("One")]) == 0
    assert database.status()["companies"] == 1


def test_claim_transitions_to_running(database: Database) -> None:
    database.enqueue([company("One")])
    database.begin_run("run", "worker", "fixture")
    claimed = database.claim("worker", "run", 30)
    assert claimed is not None
    job, claimed_company = claimed
    assert job.status == "running"
    assert job.attempts == 1
    assert claimed_company.name == "One"


def test_atomic_claim_does_not_duplicate_under_concurrency(tmp_path: Path) -> None:
    path = tmp_path / "concurrent.db"
    setup = Database(f"sqlite:///{path.as_posix()}")
    setup.init()
    setup.enqueue([company("One"), company("Two")])
    setup.begin_run("run-a", "worker-a", "fixture")
    setup.begin_run("run-b", "worker-b", "fixture")

    def claim(worker: str, run: str) -> int | None:
        db = Database(f"sqlite:///{path.as_posix()}")
        result = db.claim(worker, run, 30)
        return result[0].id if result else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(
                lambda pair: claim(*pair),
                [("worker-a", "run-a"), ("worker-b", "run-b")],
            )
        )
    assert None not in ids
    assert len(set(ids)) == 2


def test_upsert_is_idempotent(database: Database) -> None:
    database.enqueue([company("One")])
    database.begin_run("run", "worker", "fixture")
    job, _ = database.claim("worker", "run", 30) or (None, None)
    assert job is not None
    result = FieldResult(
        field_name="ceo",
        status=FieldStatus.FOUND,
        value="First",
        source_url="https://example.com/leadership",
    )
    database.save_group(job.id, "worker", "leadership", [result], 30)
    replacement = result.model_copy(update={"value": "Second"})
    database.save_group(job.id, "worker", "leadership", [replacement], 30)
    records = database.result_records()
    assert len(records) == 1
    assert records[0]["value"] == "Second"


def test_stale_job_recovery_preserves_checkpoint(database: Database) -> None:
    database.enqueue([company("One")])
    database.begin_run("run-a", "worker-a", "fixture")
    job, _ = database.claim("worker-a", "run-a", 30) or (None, None)
    assert job is not None
    result = FieldResult(field_name="ceo", status=FieldStatus.NOT_FOUND)
    database.save_group(job.id, "worker-a", "leadership", [result], 30)
    with database.session() as session:
        session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(lease_until=utcnow() - timedelta(seconds=1))
        )
    database.begin_run("run-b", "worker-b", "fixture")
    assert database.recover_stale("run-b") == 1
    resumed, _ = database.claim("worker-b", "run-b", 30) or (None, None)
    assert resumed is not None
    assert "leadership" in resumed.checkpoint["completed_groups"]
    assert resumed.attempts == 2


def test_unique_constraint_matches_result_count(database: Database) -> None:
    database.enqueue([company("One")])
    database.begin_run("run", "worker", "fixture")
    job, _ = database.claim("worker", "run", 30) or (None, None)
    assert job is not None
    database.save_group(
        job.id,
        "worker",
        "leadership",
        [FieldResult(field_name="ceo", status=FieldStatus.NOT_FOUND)],
        30,
    )
    with database.session() as session:
        assert session.query(FieldResultRow).count() == 1
