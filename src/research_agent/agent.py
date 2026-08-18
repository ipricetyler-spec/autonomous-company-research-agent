from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from time import monotonic

from research_agent.config import Settings
from research_agent.database import Company, Database, Job
from research_agent.events import EventLogger
from research_agent.extractors import (
    ExtractionError,
    Extractor,
    TransientExtractionError,
)
from research_agent.research import ResearchError, ResearchTool, TransientResearchError
from research_agent.retry import RetryExhaustedError, retry_call
from research_agent.schemas import FIELD_GROUPS, FieldResult, FieldStatus, GroupResult


@dataclass(slots=True)
class WorkerResult:
    run_id: str
    processed: int
    failed: int
    recovered: int
    elapsed_seconds: float


class AgentWorker:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        research_tool: ResearchTool,
        extractor: Extractor,
        logger: EventLogger,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.research_tool = research_tool
        self.extractor = extractor
        self.logger = logger
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:10]}"

    def run(self) -> WorkerResult:
        run_id = f"run-{uuid.uuid4().hex}"
        started = monotonic()
        processed = 0
        failed = 0
        self.database.begin_run(run_id, self.worker_id, self.settings.mode)
        recovered = self.database.recover_stale(run_id)
        self.logger.emit(
            "run_started",
            run_id=run_id,
            worker_id=self.worker_id,
            mode=self.settings.mode,
            recovered_jobs=recovered,
        )
        try:
            while claimed := self.database.claim(
                self.worker_id, run_id, self.settings.lease_seconds
            ):
                job, company = claimed
                try:
                    self._process_company(run_id, job, company)
                    processed += 1
                except Exception as error:
                    failed += 1
                    self.database.fail_job(job.id, self.worker_id, str(error))
                    self.logger.emit(
                        "company_failed",
                        run_id=run_id,
                        worker_id=self.worker_id,
                        company_id=company.id,
                        company=company.name,
                        job_id=job.id,
                        attempt=job.attempts,
                        status="failed",
                        error_category=type(error).__name__,
                        error=str(error),
                    )
        finally:
            self.database.finish_run(run_id)
        elapsed = monotonic() - started
        self.logger.emit(
            "run_completed",
            run_id=run_id,
            worker_id=self.worker_id,
            processed=processed,
            failed=failed,
            recovered_jobs=recovered,
            elapsed_seconds=round(elapsed, 6),
            status="complete",
        )
        return WorkerResult(run_id, processed, failed, recovered, elapsed)

    def _process_company(self, run_id: str, job: Job, company: Company) -> None:
        completed_groups = set(job.checkpoint.get("completed_groups", []))
        self.logger.emit(
            "company_started",
            run_id=run_id,
            worker_id=self.worker_id,
            company_id=company.id,
            company=company.name,
            job_id=job.id,
            attempt=job.attempts,
            resumed_groups=sorted(completed_groups),
            status="running",
        )
        for group in FIELD_GROUPS:
            if group in completed_groups:
                self.logger.emit(
                    "group_skipped_checkpoint",
                    run_id=run_id,
                    worker_id=self.worker_id,
                    company_id=company.id,
                    company=company.name,
                    job_id=job.id,
                    group=group,
                    status="checkpointed",
                )
                continue
            if not self.database.heartbeat(job.id, self.worker_id, self.settings.lease_seconds):
                raise RuntimeError("job lease lost before research group")
            started = monotonic()
            results = self._run_group(run_id, job, company, group)
            self.database.save_group(
                job.id,
                self.worker_id,
                group,
                results.results,
                self.settings.lease_seconds,
            )
            self.logger.emit(
                "group_checkpointed",
                run_id=run_id,
                worker_id=self.worker_id,
                company_id=company.id,
                company=company.name,
                job_id=job.id,
                group=group,
                attempt=job.attempts,
                status="checkpointed",
                elapsed_seconds=round(monotonic() - started, 6),
            )
            if self.settings.group_delay_seconds:
                time.sleep(self.settings.group_delay_seconds)
        self.database.complete_job(job.id, self.worker_id)
        self.logger.emit(
            "company_completed",
            run_id=run_id,
            worker_id=self.worker_id,
            company_id=company.id,
            company=company.name,
            job_id=job.id,
            attempt=job.attempts,
            status="complete",
        )

    def _run_group(self, run_id: str, job: Job, company: Company, group: str) -> GroupResult:
        def on_retry(attempt: int, error: Exception, delay: float) -> None:
            self.database.increment_run(run_id, "retries")
            self.logger.emit(
                "retry_scheduled",
                run_id=run_id,
                worker_id=self.worker_id,
                company_id=company.id,
                company=company.name,
                job_id=job.id,
                group=group,
                attempt=attempt,
                status="retrying",
                delay_seconds=round(delay, 6),
                error_category=type(error).__name__,
                error=str(error),
            )

        try:
            sources = retry_call(
                lambda: self.research_tool.collect(company, group),
                attempts=self.settings.max_retries,
                base_seconds=self.settings.backoff_base_seconds,
                retryable=(TransientResearchError,),
                on_retry=on_retry,
            )
        except (RetryExhaustedError, ResearchError) as error:
            return self._unavailable_group(group, FieldStatus.SOURCE_UNREACHABLE, str(error))

        try:
            result = retry_call(
                lambda: self.extractor.extract(company, group, sources),
                attempts=self.settings.max_retries,
                base_seconds=self.settings.backoff_base_seconds,
                retryable=(TransientExtractionError, ExtractionError),
                on_retry=on_retry,
            )
            rejected_fields = sum(
                item.status is FieldStatus.VALIDATION_FAILED for item in result.results
            )
            if rejected_fields:
                self.database.increment_run(run_id, "validation_failures", rejected_fields)
                self.logger.emit(
                    "group_partially_validated",
                    run_id=run_id,
                    worker_id=self.worker_id,
                    company_id=company.id,
                    company=company.name,
                    job_id=job.id,
                    group=group,
                    status="partial",
                    validation_failures=rejected_fields,
                )
            return result
        except (RetryExhaustedError, ExtractionError) as error:
            self.database.increment_run(
                run_id,
                "validation_failures",
                len(FIELD_GROUPS[group]),
            )
            return self._unavailable_group(group, FieldStatus.VALIDATION_FAILED, str(error))

    @staticmethod
    def _unavailable_group(group: str, status: FieldStatus, error: str) -> GroupResult:
        return GroupResult(
            group=group,
            results=[
                FieldResult(
                    field_name=field,
                    status=status,
                    evidence=error[:1000],
                )
                for field in FIELD_GROUPS[group]
            ],
        )

