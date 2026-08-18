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
and exactly 375 unique result rows. A separate three-company run exercised official-web retrieval,
strict JSON Schema output, semantic validation, citation allowlisting, and bounded retry using a
local Ollama model with no external API credential. All three jobs completed with 45 unique field
rows; uncertain and invalid output remained explicit non-success statuses. This is live execution
evidence, not a claim of benchmarked model accuracy.

## Skills

Python; AI Agents; LLM Integration; SQLAlchemy; PostgreSQL; SQLite; Pydantic; HTTPX; Automation;
Data Validation; Web Research; Structured Data; Error Handling; Retry/Backoff; Testing; GitHub
Actions; Docker Compose.

## Evidence

- Repository README and architecture diagram
- `docs/ARCHITECTURE.md`
- `docs/FAILURE_RECOVERY.md`
- `docs/DEMO_RESULTS.md`
- `docs/LIVE_DEMO_RESULTS.md`
- `evidence/crash_snapshot.json`
- `evidence/crash_recovery_excerpt.jsonl`
- `evidence/live_demo_results.json`
- `evidence/live_demo_excerpt.jsonl`

Public repository: https://github.com/ipricetyler-spec/autonomous-company-research-agent

No private contact information is included.

