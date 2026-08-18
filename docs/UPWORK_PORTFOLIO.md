# Upwork portfolio entry

## Title

Autonomous Company Research Agent

## One-line description

An unattended Python/LLM research agent with persistent state, validated structured outputs,
citations, retries, and crash-safe recovery.

## Short project description

Built a portfolio-grade agent that processes a persistent queue of public companies without human
approval between normal steps. The system groups related research fields to reuse sources, validates
all model-shaped output, preserves a citation for every populated fact, checkpoints after each
group, and isolates failures so one company does not stop the batch.

Reliability is demonstrated with a reproducible 25-company deterministic run. A worker process was
forcibly terminated after three completed companies and one checkpoint on the fourth. The restarted
worker reclaimed the expired lease, reused the checkpoint, and finished with 25 completed companies
and exactly 375 unique result rows. Live provider accuracy is deliberately not claimed because the
measured run used the included zero-cost replay fixtures.

## Skills

Python; AI Agents; LLM Integration; SQLAlchemy; PostgreSQL; SQLite; Pydantic; HTTPX; Automation;
Data Validation; Web Research; Structured Data; Error Handling; Retry/Backoff; Testing; GitHub
Actions; Docker Compose.

## Evidence

- Repository README and architecture diagram
- `docs/ARCHITECTURE.md`
- `docs/FAILURE_RECOVERY.md`
- `docs/DEMO_RESULTS.md`
- `evidence/crash_snapshot.json`
- `evidence/crash_recovery_excerpt.jsonl`

Add the public GitHub URL after repository publication. No private contact information is included.

