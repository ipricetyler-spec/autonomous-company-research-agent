# Autonomous Company Research Agent

A portfolio-grade Python agent that processes a persistent queue of public companies without
human approval between research steps. It performs grouped source collection, validates every
structured field, checkpoints progress, retries transient failures, and automatically reclaims
work after a crashed worker's lease expires.

The repository includes a deterministic 25-company crash/restart demonstration that requires no
API key and a measured three-company live run against official websites using a local Ollama
model. Live mode remains provider-neutral through an OpenAI-compatible Chat Completions endpoint.

> Evidence boundary: live execution is verified and the recorded three-company run has an
> exact-match baseline against a dated primary-source reference set. The current label audit has
> one reviewer, and model-derived facts still require human review before consequential use.

## Architecture

```mermaid
flowchart LR
    Q[(Persistent queue)] --> C[Atomic claim + lease]
    C --> P[Grouped research plan]
    P --> T[Approved source tool]
    T --> X[Structured extractor]
    X --> V[Pydantic validation]
    V --> U[(Idempotent field upsert)]
    U --> K[Checkpoint group]
    K -->|more groups| P
    K -->|company done| Q
    C -->|expired lease| R[Automatic stale recovery]
    R --> Q
```

PostgreSQL uses `SELECT ... FOR UPDATE SKIP LOCKED`. SQLite uses one atomic
`UPDATE ... RETURNING` claim and WAL mode, which makes the local replay easy to run without
Docker. Both backends enforce one job per company and one result per company/field.

## Quick start

Python 3.12 or newer is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"

research-agent --database-url sqlite:///data/demo.db db init
research-agent --database-url sqlite:///data/demo.db demo seed --companies 25
research-agent --database-url sqlite:///data/demo.db run --mode fixture
research-agent --database-url sqlite:///data/demo.db status
research-agent --database-url sqlite:///data/demo.db export data/results.json
research-agent --database-url sqlite:///data/demo.db export data/results.csv
```

## Crash/restart evidence

This command starts a subprocess, waits for three completed companies, kills it while another job
is running, records the database state, waits for the lease to expire, restarts a worker, and
verifies completion and result uniqueness:

```bash
research-agent demo crash-recovery --companies 25
```

Outputs are written to `demo_artifacts/`, including both worker logs, the before/after snapshot,
JSON/CSV exports, and measured `demo_results.json`.

## PostgreSQL

```bash
docker compose up -d postgres
python -m pip install -e ".[postgres,dev]"
research-agent --database-url postgresql+psycopg://agent:agent_local_only@localhost:5432/research_agent db init
```

See [Architecture](docs/ARCHITECTURE.md), [failure recovery](docs/FAILURE_RECOVERY.md),
[security](docs/SECURITY.md), [crash/restart results](docs/DEMO_RESULTS.md),
[live demo results](docs/LIVE_DEMO_RESULTS.md), and [portfolio notes](docs/PORTFOLIO_NOTES.md).

## Accuracy benchmark

Score any JSON result export against the default 25-company, primary-source reference set:

```bash
research-agent benchmark data/results.json --output evidence/accuracy.json
```

For a partial run, explicitly scope the labels to companies present in that export:

```bash
research-agent benchmark data/live-results.json \
  --scope-to-predictions \
  --output evidence/live-accuracy.json
```

The report separates overall accuracy, answer coverage, precision when answered, abstentions,
missing rows, and predictions for fields without labels. See
[Accuracy benchmark](docs/ACCURACY_BENCHMARK.md) for metric definitions and evidence limits.

## Live mode

Use `.env.example` as a reference and export `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` into
the process environment. Import a CSV containing `name,website`; then run with `--mode live`.
Secrets are read from environment variables and never included in prompts or logs. External page
text is explicitly delimited as untrusted evidence and cannot choose tools or execution goals.
Before every live request, the collector rejects URL credentials, nonstandard ports, cross-domain
redirects, and DNS answers containing loopback, private, link-local, reserved, or other non-public
addresses. Redirects are validated before they are followed.

For a credential-free local run with Ollama's OpenAI-compatible endpoint:

```bash
ollama pull gemma3:4b
# PowerShell equivalents can use $env:NAME='value'
export LLM_BASE_URL=http://127.0.0.1:11434/v1
export LLM_API_KEY=ollama-local
export LLM_MODEL=gemma3:4b
export LLM_STRUCTURED_OUTPUT=json_schema
research-agent --database-url sqlite:///data/live.db db init
research-agent --database-url sqlite:///data/live.db companies import examples/companies.csv
research-agent --database-url sqlite:///data/live.db run --mode live
```

## Tests and checks

```bash
pytest
ruff check .
```

CI runs both commands on Python 3.12, exercises two concurrent workers against a PostgreSQL 18
service, and performs a deterministic five-company smoke run.
