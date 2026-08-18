from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from research_agent.schemas import CompanyInput, FieldResult, JobStatus


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String(2000))
    fixture_key: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    job: Mapped[Job] = relationship(back_populates="company", uselist=False)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(100), index=True)
    run_id: Mapped[str | None] = mapped_column(String(100), index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    checkpoint_json: Mapped[str] = mapped_column(Text, default='{"completed_groups":[]}')

    company: Mapped[Company] = relationship(back_populates="job")

    @property
    def checkpoint(self) -> dict[str, Any]:
        return json.loads(self.checkpoint_json)


class FieldResultRow(Base):
    __tablename__ = "field_results"
    __table_args__ = (UniqueConstraint("company_id", "field_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    value_json: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2000))
    source_title: Mapped[str | None] = mapped_column(String(300))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(20))
    evidence: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retries: Mapped[int] = mapped_column(Integer, default=0)
    validation_failures: Mapped[int] = mapped_column(Integer, default=0)
    recovered_jobs: Mapped[int] = mapped_column(Integer, default=0)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        if url.startswith("sqlite:///"):
            path = Path(url.removeprefix("sqlite:///"))
            if str(path) != ":memory:":
                path.parent.mkdir(parents=True, exist_ok=True)
        connect_args = (
            {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
        )
        self.engine = create_engine(url, future=True, connect_args=connect_args)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._configure_sqlite)

    @staticmethod
    def _configure_sqlite(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    def init(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def enqueue(self, inputs: Sequence[CompanyInput]) -> int:
        created = 0
        with self.session() as session:
            for item in inputs:
                company = session.scalar(select(Company).where(Company.name == item.name))
                if company is None:
                    company = Company(
                        name=item.name,
                        website=str(item.website) if item.website else None,
                        fixture_key=item.fixture_key,
                    )
                    session.add(company)
                    session.flush()
                if session.scalar(select(Job).where(Job.company_id == company.id)) is None:
                    session.add(Job(company_id=company.id))
                    created += 1
        return created

    def begin_run(self, run_id: str, worker_id: str, mode: str) -> None:
        with self.session() as session:
            session.add(Run(id=run_id, worker_id=worker_id, mode=mode))

    def finish_run(self, run_id: str) -> None:
        with self.session() as session:
            session.execute(update(Run).where(Run.id == run_id).values(completed_at=utcnow()))

    def increment_run(self, run_id: str, field: str, amount: int = 1) -> None:
        if field not in {"retries", "validation_failures", "recovered_jobs"}:
            raise ValueError(f"unsupported run counter: {field}")
        column = getattr(Run, field)
        with self.session() as session:
            session.execute(update(Run).where(Run.id == run_id).values({field: column + amount}))

    def recover_stale(self, run_id: str) -> int:
        now = utcnow()
        with self.session() as session:
            result = session.execute(
                update(Job)
                .where(Job.status == JobStatus.RUNNING.value, Job.lease_until < now)
                .values(
                    status=JobStatus.PENDING.value,
                    worker_id=None,
                    run_id=None,
                    lease_until=None,
                    updated_at=now,
                    last_error="worker lease expired; job reclaimed automatically",
                )
            )
            count = int(result.rowcount or 0)
        if count:
            self.increment_run(run_id, "recovered_jobs", count)
        return count

    def claim(self, worker_id: str, run_id: str, lease_seconds: int) -> tuple[Job, Company] | None:
        now = utcnow()
        lease_until = now + timedelta(seconds=lease_seconds)
        with self.session() as session:
            if self.engine.dialect.name == "postgresql":
                job = session.scalar(
                    select(Job)
                    .where(Job.status == JobStatus.PENDING.value)
                    .order_by(Job.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if job is None:
                    return None
                job.status = JobStatus.RUNNING.value
                job.worker_id = worker_id
                job.run_id = run_id
                job.attempts += 1
                job.started_at = job.started_at or now
                job.updated_at = now
                job.lease_until = lease_until
                session.flush()
                company = session.get(Company, job.company_id)
                assert company is not None
                session.expunge(job)
                session.expunge(company)
                return job, company

            candidate = (
                select(Job.id)
                .where(Job.status == JobStatus.PENDING.value)
                .order_by(Job.id)
                .limit(1)
                .scalar_subquery()
            )
            result = session.execute(
                update(Job)
                .where(Job.id == candidate, Job.status == JobStatus.PENDING.value)
                .values(
                    status=JobStatus.RUNNING.value,
                    worker_id=worker_id,
                    run_id=run_id,
                    attempts=Job.attempts + 1,
                    started_at=func.coalesce(Job.started_at, now),
                    updated_at=now,
                    lease_until=lease_until,
                )
                .returning(Job.id)
            ).first()
            if result is None:
                return None
            job = session.get(Job, result[0])
            assert job is not None
            company = session.get(Company, job.company_id)
            assert company is not None
            session.expunge(job)
            session.expunge(company)
            return job, company

    def heartbeat(self, job_id: int, worker_id: str, lease_seconds: int) -> bool:
        now = utcnow()
        with self.session() as session:
            result = session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.worker_id == worker_id,
                    Job.status == JobStatus.RUNNING.value,
                )
                .values(updated_at=now, lease_until=now + timedelta(seconds=lease_seconds))
            )
            return bool(result.rowcount)

    def save_group(
        self,
        job_id: int,
        worker_id: str,
        group: str,
        results: Sequence[FieldResult],
        lease_seconds: int,
    ) -> None:
        now = utcnow()
        with self.session() as session:
            job = session.scalar(
                select(Job).where(
                    Job.id == job_id,
                    Job.worker_id == worker_id,
                    Job.status == JobStatus.RUNNING.value,
                )
            )
            if job is None:
                raise RuntimeError("job lease lost before checkpoint")
            for result in results:
                values = {
                    "company_id": job.company_id,
                    "field_name": result.field_name,
                    "status": result.status.value,
                    "value_json": (
                        json.dumps(result.value, default=str)
                        if result.value is not None
                        else None
                    ),
                    "source_url": str(result.source_url) if result.source_url else None,
                    "source_title": result.source_title,
                    "retrieved_at": result.retrieved_at,
                    "confidence": str(result.confidence) if result.confidence is not None else None,
                    "evidence": result.evidence,
                    "updated_at": now,
                }
                insert = (
                    pg_insert(FieldResultRow)
                    if self.engine.dialect.name == "postgresql"
                    else sqlite_insert(FieldResultRow)
                )
                statement = insert.values(**values).on_conflict_do_update(
                    index_elements=[FieldResultRow.company_id, FieldResultRow.field_name],
                    set_={
                        key: value
                        for key, value in values.items()
                        if key not in {"company_id", "field_name"}
                    },
                )
                session.execute(statement)
            checkpoint = job.checkpoint
            groups = set(checkpoint.get("completed_groups", []))
            groups.add(group)
            job.checkpoint_json = json.dumps({"completed_groups": sorted(groups)})
            job.updated_at = now
            job.lease_until = now + timedelta(seconds=lease_seconds)

    def complete_job(self, job_id: int, worker_id: str) -> None:
        now = utcnow()
        with self.session() as session:
            result = session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.worker_id == worker_id,
                    Job.status == JobStatus.RUNNING.value,
                )
                .values(
                    status=JobStatus.COMPLETE.value,
                    completed_at=now,
                    updated_at=now,
                    lease_until=None,
                    last_error=None,
                )
            )
            if not result.rowcount:
                raise RuntimeError("job lease lost before completion")

    def fail_job(self, job_id: int, worker_id: str, error: str) -> None:
        with self.session() as session:
            session.execute(
                update(Job)
                .where(Job.id == job_id, Job.worker_id == worker_id)
                .values(
                    status=JobStatus.FAILED.value,
                    updated_at=utcnow(),
                    lease_until=None,
                    last_error=error[:2000],
                )
            )

    def status(self) -> dict[str, Any]:
        with self.session() as session:
            job_counts = dict(
                session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
            )
            field_counts = dict(
                session.execute(
                    select(FieldResultRow.status, func.count(FieldResultRow.id)).group_by(
                        FieldResultRow.status
                    )
                ).all()
            )
            retries = session.scalar(select(func.coalesce(func.sum(Run.retries), 0))) or 0
            validation_failures = (
                session.scalar(select(func.coalesce(func.sum(Run.validation_failures), 0))) or 0
            )
            recovered_jobs = (
                session.scalar(select(func.coalesce(func.sum(Run.recovered_jobs), 0))) or 0
            )
            unique_results = session.scalar(select(func.count(FieldResultRow.id))) or 0
            companies = session.scalar(select(func.count(Company.id))) or 0
            attempts = session.scalar(select(func.coalesce(func.sum(Job.attempts), 0))) or 0
            return {
                "companies": int(companies),
                "jobs": {
                    status.value: int(job_counts.get(status.value, 0)) for status in JobStatus
                },
                "fields": {key: int(value) for key, value in sorted(field_counts.items())},
                "unique_field_results": int(unique_results),
                "job_claim_attempts": int(attempts),
                "retries": int(retries),
                "validation_failures": int(validation_failures),
                "recovered_jobs": int(recovered_jobs),
            }

    def result_records(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.execute(
                select(Company, FieldResultRow)
                .join(FieldResultRow, FieldResultRow.company_id == Company.id)
                .order_by(Company.id, FieldResultRow.field_name)
            ).all()
            return [
                {
                    "company": company.name,
                    "field_name": result.field_name,
                    "status": result.status,
                    "value": json.loads(result.value_json) if result.value_json else None,
                    "source_url": result.source_url,
                    "source_title": result.source_title,
                    "retrieved_at": result.retrieved_at.isoformat(),
                    "confidence": float(result.confidence) if result.confidence else None,
                    "evidence": result.evidence,
                }
                for company, result in rows
            ]

    def running_jobs(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.execute(
                select(Job, Company)
                .join(Company, Company.id == Job.company_id)
                .where(Job.status == JobStatus.RUNNING.value)
            ).all()
            return [
                {
                    "job_id": job.id,
                    "company": company.name,
                    "worker_id": job.worker_id,
                    "run_id": job.run_id,
                    "attempts": job.attempts,
                    "lease_until": job.lease_until.isoformat() if job.lease_until else None,
                    "checkpoint": job.checkpoint,
                }
                for job, company in rows
            ]


def dispose_engine(engine: Engine) -> None:
    engine.dispose()
