# Autonomous Company Research Agent

A portfolio-grade Python agent that processes a persistent queue of public companies without
human approval between research steps. It performs grouped source collection, validates every
structured field, checkpoints progress, retries transient failures, and automatically reclaims
work after a crashed worker's lease expires.

The repository includes a deterministic 25-company replay demonstration that requires no API
key. Live mode uses a provider-neutral OpenAI-compatible Chat Completions endpoint and only
fetches a small allowlist of paths on an imported company's official domain.

> Evidence boundary: the included measured demo exercises deterministic fixture replay, not live
> web/model accuracy. Live provider execution remains unverified until credentials are supplied.

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
research-agent --database-url postgresql+psycopg://agent:agent@localhost:5432/research_agent db init
```

See [Architecture](docs/ARCHITECTURE.md), [failure recovery](docs/FAILURE_RECOVERY.md),
[security](docs/SECURITY.md), [measured demo results](docs/DEMO_RESULTS.md), and
[portfolio notes](docs/PORTFOLIO_NOTES.md).

## Live mode

Copy `.env.example` to `.env` and provide `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in the
process environment. Import a CSV containing `name,website`; then run with `--mode live`.
Secrets are read from environment variables and never included in prompts or logs. External page
text is explicitly delimited as untrusted evidence and cannot choose tools or execution goals.

## Tests and checks

```bash
pytest
ruff check .
```

CI runs both commands on Python 3.12 and performs a deterministic five-company smoke run.

