from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from research_agent.agent import AgentWorker
from research_agent.benchmark import (
    evaluate_predictions,
    load_labels,
    load_predictions,
    scope_labels_to_prediction_companies,
)
from research_agent.config import Settings
from research_agent.database import Database
from research_agent.events import EventLogger
from research_agent.extractors import FixtureExtractor, OpenAICompatibleExtractor
from research_agent.research import FixtureResearchTool, OfficialWebsiteResearchTool
from research_agent.schemas import CompanyInput

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "fixtures" / "companies.json"
DEFAULT_BENCHMARK_LABELS = PROJECT_ROOT / "benchmarks" / "primary_source_labels.v1.json"


def _database(args: argparse.Namespace) -> Database:
    database = Database(args.database_url or os.getenv("DATABASE_URL", Settings().database_url))
    database.init()
    return database


def _settings(args: argparse.Namespace) -> Settings:
    return Settings.from_env(
        database_url=args.database_url,
        mode=getattr(args, "mode", None),
        log_path=getattr(args, "log_path", None),
        lease_seconds=getattr(args, "lease_seconds", None),
        max_retries=getattr(args, "max_retries", None),
        group_delay_seconds=getattr(args, "group_delay", None),
    )


def _build_worker(database: Database, settings: Settings) -> AgentWorker:
    if settings.mode == "fixture":
        research_tool = FixtureResearchTool(DEFAULT_FIXTURE)
        extractor = FixtureExtractor()
    else:
        research_tool = OfficialWebsiteResearchTool(
            timeout=settings.request_timeout_seconds,
            max_chars=settings.max_source_chars,
        )
        assert settings.llm_base_url and settings.llm_api_key and settings.llm_model
        extractor = OpenAICompatibleExtractor(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.request_timeout_seconds,
            structured_output=settings.llm_structured_output,
            max_tokens=settings.llm_max_tokens,
        )
    return AgentWorker(
        database,
        settings,
        research_tool,
        extractor,
        EventLogger(settings.log_path),
    )


def command_db_init(args: argparse.Namespace) -> int:
    database = _database(args)
    print(json.dumps({"status": "initialized", "database": database.url}, sort_keys=True))
    return 0


def command_import(args: argparse.Namespace) -> int:
    database = _database(args)
    path = Path(args.path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    inputs = [
        CompanyInput(
            name=row["name"].strip(),
            website=(row.get("website") or "").strip() or None,
            fixture_key=(row.get("fixture_key") or "").strip() or None,
        )
        for row in rows
    ]
    created = database.enqueue(inputs)
    print(json.dumps({"rows": len(inputs), "jobs_created": created}, sort_keys=True))
    return 0


def load_fixture_inputs(
    path: Path = DEFAULT_FIXTURE, limit: int | None = None
) -> list[CompanyInput]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if limit is not None:
        records = records[:limit]
    return [
        CompanyInput(name=item["name"], website=item["website"], fixture_key=item["key"])
        for item in records
    ]


def command_demo_seed(args: argparse.Namespace) -> int:
    database = _database(args)
    inputs = load_fixture_inputs(limit=args.companies)
    created = database.enqueue(inputs)
    print(json.dumps({"companies": len(inputs), "jobs_created": created}, sort_keys=True))
    return 0


def command_run(args: argparse.Namespace) -> int:
    database = _database(args)
    settings = _settings(args)
    worker = _build_worker(database, settings)
    result = worker.run()
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "processed": result.processed,
                "failed": result.failed,
                "recovered": result.recovered,
                "elapsed_seconds": round(result.elapsed_seconds, 6),
                "summary": database.status(),
            },
            sort_keys=True,
        )
    )
    return 0 if result.failed == 0 else 1


def command_status(args: argparse.Namespace) -> int:
    database = _database(args)
    print(
        json.dumps(
            {"summary": database.status(), "running": database.running_jobs()},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def export_database(database: Database, path: Path) -> int:
    records = database.result_records()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        fieldnames = [
            "company",
            "field_name",
            "status",
            "value",
            "source_url",
            "source_title",
            "retrieved_at",
            "confidence",
            "evidence",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                row = dict(record)
                row["value"] = json.dumps(row["value"], ensure_ascii=False)
                writer.writerow(row)
    else:
        path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(records)


def command_export(args: argparse.Namespace) -> int:
    database = _database(args)
    path = Path(args.path)
    count = export_database(database, path)
    print(json.dumps({"records": count, "path": str(path.resolve())}, sort_keys=True))
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    labels = load_labels(Path(args.labels))
    predictions = load_predictions(Path(args.path))
    if args.scope_to_predictions:
        labels = scope_labels_to_prediction_companies(labels, predictions)
    result = evaluate_predictions(labels, predictions)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def command_crash_recovery(args: argparse.Namespace) -> int:
    artifacts = Path(args.artifacts).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    db_path = (artifacts / "crash_recovery.db").resolve()
    if artifacts not in db_path.parents:
        raise RuntimeError("refusing to replace a database outside the artifact directory")
    for suffix in ("", "-shm", "-wal"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()
    database_url = f"sqlite:///{db_path.as_posix()}"
    database = Database(database_url)
    database.init()
    inputs = load_fixture_inputs(limit=args.companies)
    database.enqueue(inputs)
    before_log = artifacts / "worker_before_crash.jsonl"
    after_log = artifacts / "worker_after_restart.jsonl"
    started_at = time.monotonic()
    base_command = [
        sys.executable,
        "-m",
        "research_agent.cli",
        "--database-url",
        database_url,
        "run",
        "--mode",
        "fixture",
        "--lease-seconds",
        str(args.lease_seconds),
        "--max-retries",
        "3",
    ]
    with before_log.open("w", encoding="utf-8", newline="\n") as output:
        process = subprocess.Popen(
            base_command + ["--group-delay", str(args.group_delay), "--log-path", ""],
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
        )
        deadline = time.monotonic() + args.kill_timeout
        while time.monotonic() < deadline:
            status = database.status()
            running = database.running_jobs()
            if status["jobs"]["complete"] >= args.kill_after and running:
                break
            if process.poll() is not None:
                raise RuntimeError("worker exited before the crash-injection point")
            time.sleep(0.05)
        else:
            process.kill()
            process.wait(timeout=10)
            raise RuntimeError("worker did not reach the crash-injection point")
        snapshot = {
            "event": "forced_process_termination",
            "status_before_kill": database.status(),
            "running_before_kill": running,
        }
        process.kill()
        process.wait(timeout=10)
    snapshot["exit_code_after_kill"] = process.returncode
    snapshot["status_after_kill"] = database.status()
    _write_json(artifacts / "crash_snapshot.json", snapshot)
    time.sleep(args.lease_seconds + 0.25)
    with after_log.open("w", encoding="utf-8", newline="\n") as output:
        completed = subprocess.run(
            base_command + ["--group-delay", "0", "--log-path", ""],
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
            check=False,
        )
    final = database.status()
    expected_fields = len(inputs) * 15
    evidence = {
        "mode": "deterministic_fixture_replay",
        "companies_queued": len(inputs),
        "elapsed_seconds": round(time.monotonic() - started_at, 6),
        "first_worker_killed_exit_code": process.returncode,
        "restart_worker_exit_code": completed.returncode,
        "completed_companies": final["jobs"]["complete"],
        "failed_companies": final["jobs"]["failed"],
        "recovered_jobs": final["recovered_jobs"],
        "job_claim_attempts": final["job_claim_attempts"],
        "unique_field_results": final["unique_field_results"],
        "expected_unique_field_results": expected_fields,
        "duplicate_final_results": final["unique_field_results"] != expected_fields,
        "field_status_counts": final["fields"],
        "retries": final["retries"],
        "validation_failures": final["validation_failures"],
        "live_api_verified": False,
    }
    export_database(database, artifacts / "results.json")
    export_database(database, artifacts / "results.csv")
    _write_json(artifacts / "demo_results.json", evidence)
    if completed.returncode != 0:
        raise RuntimeError(f"restart worker exited with {completed.returncode}")
    if (
        evidence["completed_companies"] != len(inputs)
        or evidence["recovered_jobs"] < 1
        or evidence["duplicate_final_results"]
    ):
        raise RuntimeError(f"crash-recovery acceptance failed: {evidence}")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-agent")
    parser.add_argument("--database-url", help="SQLAlchemy database URL")
    commands = parser.add_subparsers(dest="command", required=True)

    db_parser = commands.add_parser("db", help="database operations")
    db_commands = db_parser.add_subparsers(dest="db_command", required=True)
    db_init = db_commands.add_parser("init", help="create database tables")
    db_init.set_defaults(handler=command_db_init)

    companies = commands.add_parser("companies", help="company queue operations")
    company_commands = companies.add_subparsers(dest="company_command", required=True)
    company_import = company_commands.add_parser("import", help="import a CSV queue")
    company_import.add_argument("path")
    company_import.set_defaults(handler=command_import)

    run = commands.add_parser("run", help="process the queue unattended")
    run.add_argument("--mode", choices=["fixture", "live"])
    run.add_argument("--lease-seconds", type=int)
    run.add_argument("--max-retries", type=int)
    run.add_argument("--group-delay", type=float)
    run.add_argument("--log-path")
    run.set_defaults(handler=command_run)

    status = commands.add_parser("status", help="show queue and result status")
    status.set_defaults(handler=command_status)

    export = commands.add_parser("export", help="export .json or .csv results")
    export.add_argument("path")
    export.set_defaults(handler=command_export)

    benchmark = commands.add_parser("benchmark", help="score an exported result set")
    benchmark.add_argument("path", help="JSON export produced by the agent")
    benchmark.add_argument(
        "--labels",
        default=str(DEFAULT_BENCHMARK_LABELS),
        help="labeled JSON reference set (defaults to the primary-source 25-company set)",
    )
    benchmark.add_argument("--output", help="optional path for the machine-readable report")
    benchmark.add_argument(
        "--scope-to-predictions",
        action="store_true",
        help="score only companies present in the result export",
    )
    benchmark.set_defaults(handler=command_benchmark)

    demo = commands.add_parser("demo", help="deterministic demonstrations")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    seed = demo_commands.add_parser("seed", help="enqueue deterministic fixture companies")
    seed.add_argument("--companies", type=int, default=25, choices=range(1, 26))
    seed.set_defaults(handler=command_demo_seed)
    crash = demo_commands.add_parser("crash-recovery", help="kill and restart a real worker")
    crash.add_argument("--companies", type=int, default=25, choices=range(5, 26))
    crash.add_argument("--kill-after", type=int, default=3)
    crash.add_argument("--group-delay", type=float, default=0.08)
    crash.add_argument("--lease-seconds", type=int, default=1)
    crash.add_argument("--kill-timeout", type=float, default=30)
    crash.add_argument("--artifacts", default="demo_artifacts")
    crash.set_defaults(handler=command_crash_recovery)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
