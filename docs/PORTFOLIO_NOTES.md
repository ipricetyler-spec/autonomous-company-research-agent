# Portfolio notes

## Project summary

I built an unattended public-company research agent in Python. It claims work from a persistent
queue, researches five source-affinity groups, validates 15 structured fields with citations,
checkpoints each group, and continues across company-local failures without human approval.

## Technologies

Python 3.12+, Pydantic, SQLAlchemy, HTTPX, SQLite replay mode, PostgreSQL queue design,
OpenAI-compatible model abstraction, pytest, Ruff, JSON Lines logging, Docker Compose, and GitHub
Actions.

## What makes it autonomous

The worker owns the full loop: recover stale jobs, atomically claim the next company, inspect its
checkpoint, choose the next predefined research group, call the approved source tool, invoke the
extractor, validate, retry when appropriate, persist, complete or isolate failure, and claim again.
No routine approval is required between steps or companies.

## Reliability mechanisms

- PostgreSQL row locking with `SKIP LOCKED`; atomic `UPDATE ... RETURNING` for SQLite replay.
- Worker leases, heartbeat renewal, and stale-job recovery.
- Group checkpoints committed with field results.
- Upserts on stable company/field keys.
- Bounded exponential backoff with jitter.
- Exact Pydantic schemas and citation allowlisting.
- Per-group unavailable statuses and per-company fatal isolation.
- Structured event logs and aggregate status metrics.

## Most important failure encountered

The initial process-kill demonstration exposed a configuration-default bug. A dataclass with slots
was reading class member descriptors instead of concrete instance defaults, so the child worker
exited before processing. I changed environment loading to begin from an instantiated settings
object and added regression coverage. This was a harness/runtime integration failure that the
unit-only path had not exposed.

## What broke during scale testing

Nothing in the queue or persistence path failed at the tested 25-company deterministic scale. The
first full demo attempt failed at startup for the settings reason above. After the fix, the forced
kill/restart run completed all 25 companies with one reclaimed job and no duplicate field rows.
That distinction matters: this is evidence at small portfolio scale, not a claim of production
volume.

## Crash/recovery result

The worker was killed after 3 completed jobs and after one group of company 4 was checkpointed.
Restart reclaimed company 4 after lease expiry, skipped its committed identity group, and finished
the queue. Final state: 25 complete, 0 failed, 26 claims, and exactly 375 unique result rows.

## Batch-run metrics

Deterministic replay on 2026-08-18: 25 companies, 300 found statuses, 75 not-found statuses, 0
validation failures, 0 retries, 1 recovered job, and 3.563639 seconds end to end. A separate live
run used official Microsoft, Apple, and NVIDIA pages with local Ollama `gemma3:4b`: all 3 companies
completed with 45 unique field rows, 2 recovered extraction retries, and no external API key.
Twenty-seven fields passed as `found`; 18 were honestly retained as not found, unreachable, or
validation failed. This demonstrates the live path and its safety boundaries, not fact accuracy.

The current local gate is 38 passing tests, one PostgreSQL integration test skipped without an
explicit disposable service, and Ruff passing. GitHub Actions provisions that PostgreSQL service
and runs two concurrent workers against it.

## What I built and learned

The most useful design choice was making a source-affinity group the unit of retrieval, validation,
and recovery. It reuses evidence without creating the large failure boundary of one giant prompt.
The crash test also reinforced that subprocess configuration and restart behavior need end-to-end
evidence; unit coverage alone did not catch the settings integration bug.

## Screening answer: unattended agent

> I built an unattended Python company-research agent with an explicit worker loop rather than a
> chatbot or one-shot prompt. It uses SQLAlchemy for a persistent transactional queue, Pydantic for
> schema validation, HTTPX for approved source retrieval, and an OpenAI-compatible extractor
> abstraction. Each company is researched in five source-affinity groups, and every populated field
> retains a citation. The first 25-company demo attempt exposed a settings-default bug in the child
> worker before processing began; I fixed it and added regression tests. The rerun was deliberately
> killed after three companies, recovered the interrupted leased job, and finished 25 companies
> with 375 unique field rows and no duplicates. I also executed the live path against three
> official sites using a local OpenAI-compatible Ollama model: all three jobs completed and the
> validator retained 18 uncertain or invalid fields as explicit non-success statuses. I treat that
> as execution and failure-boundary evidence, not an accuracy benchmark.

## Screening answer: run dies midway

> Completed companies stay committed. The interrupted job remains running until its lease expires,
> while later jobs remain pending. On restart, stale work is returned to pending and atomically
> reclaimed. The worker loads the group checkpoint, skips committed groups, and replays only the
> unfinished group. Field writes are upserts on company plus field name, so replay cannot append
> duplicate final rows. I demonstrated that path with a real subprocess kill and automatic restart.

## Screening answer: accuracy across datapoints

> I grouped fields by source affinity, reused authoritative pages within a group, and validated the
> exact expected field set with Pydantic. A `found` value cannot be committed without a source URL,
> and live model output cannot cite a URL the tool did not supply. Missing, unreachable, and invalid
> results have explicit statuses rather than being silently treated as empty successes. The fixture
> deterministic demo validates those mechanics. A separate official-web/local-model run exercised
> the live path and recovered both malformed JSON and an unsupplied citation. Its output still
> requires human review; credentialed-provider accuracy has not been benchmarked.
