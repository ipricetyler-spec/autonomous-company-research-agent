# Measured demo results

Run date: 2026-08-18  
Mode: deterministic fixture replay  
Command: `research-agent demo crash-recovery --companies 25`

## Result

| Metric | Measured value |
|---|---:|
| Companies queued | 25 |
| Companies complete | 25 |
| Companies failed | 0 |
| Completed before forced kill | 3 |
| Running at forced kill | 1 |
| Pending at forced kill | 21 |
| Groups persisted for interrupted company | 1 (`identity`) |
| Stale jobs recovered | 1 |
| Total job claims | 26 |
| Unique final field rows | 375 |
| Expected field rows | 375 |
| `found` rows | 300 |
| `not_found` rows | 75 |
| Duplicate final results | No |
| Retries | 0 |
| Validation failures | 0 |
| End-to-end elapsed time | 3.563639 seconds |
| Automated tests in final local gate | 28 passed |
| Lint | Passed |

The first worker was terminated with subprocess `kill()` and returned exit code 1. The restarted
worker returned 0. Its first run event reported one recovered job; it then logged
`group_skipped_checkpoint` for company 4's identity group and completed that company on attempt 2.

## Evidence files

- `evidence/crash_snapshot.json`: database state immediately around forced termination.
- `evidence/crash_recovery_excerpt.jsonl`: key before/after worker events.
- `evidence/demo_results.json`: machine-readable measured summary.

The full generated database, 375-row JSON/CSV exports, and complete logs are reproducible but
ignored because they are runtime artifacts. Their SHA-256 hashes in the measured run were:

| Artifact | SHA-256 |
|---|---|
| `crash_snapshot.json` | `783423CE3C3FEA0C0094CBC823C988C7B98D60D307E7F695B79B0FDFC19CC666` |
| `demo_results.json` | `541E63073046A859B450B89E2C7EC568E229D3BEE918888B2A6F56D13F03482B` |
| `results.json` | `1DE6182C924E529E269AA76FB90CCA2C7073BEC7201D1B2F5AD45E8AAD185DF9` |
| `results.csv` | `12D925D5B76F78659691625BD4BAFCFD3F3B5D866E7C9DC1C7586E19A1CE938D` |

## Evidence boundary

This run demonstrates unattended control flow, persistent state, real process termination,
lease-based recovery, checkpoint reuse, and idempotent persistence. Fixture facts were not fetched
live, and no model API was called in this specific run. See [the separate live demonstration](LIVE_DEMO_RESULTS.md)
for measured official-web/local-model execution. Neither demonstration is an accuracy benchmark.

## Failure found while building the demo

The first 25-company crash-demo attempt failed before the kill point because the slots-based
settings dataclass accessed class descriptors as defaults. The child process rejected the lease
setting. The fix instantiates concrete defaults before environment parsing and adds two regression
tests. The rerun produced the metrics above. No queue failure appeared at 25-company fixture scale.
