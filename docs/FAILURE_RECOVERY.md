# Failure recovery

## Concrete example: the run dies on company 17 of 30

Companies 1–16 remain `complete`. Their field rows and completion timestamps were committed in
earlier transactions. Company 17 remains `running` with its last committed group checkpoint,
worker ID, attempt count, and lease expiration. Companies 18–30 remain `pending`.

On restart:

1. The worker creates a new run record.
2. It changes any `running` job with an expired lease back to `pending`.
3. Atomic claiming selects a pending job. The interrupted job is eventually claimed with a new
   worker/run ID and incremented attempt count.
4. The worker loads `completed_groups` and skips those groups.
5. If the process died between an external call and a commit, that group is replayed.
6. Each replay writes with an upsert keyed by company and field, so it cannot append duplicate
   final rows.
7. Once every group is checkpointed, the job becomes `complete`, and the queue continues.

The lease prevents a second healthy worker from immediately stealing active work. This version
heartbeats before every group and renews the lease on every checkpoint. A very long single network
request must therefore use a lease longer than the configured request timeout.

## Demonstrated behavior

The measured 25-company fixture replay was deliberately killed after three companies completed
and after the identity group for company 4 was committed. The snapshot showed 3 complete, 1
running, and 21 pending jobs. After lease expiry, the restarted worker reclaimed one job, skipped
the persisted identity checkpoint, and completed all 25 companies. There were 26 claims and 375
unique result rows—the exact 25 × 15 expected—with no duplicate final results.

See `evidence/crash_snapshot.json`, `evidence/crash_recovery_excerpt.jsonl`, and
`evidence/demo_results.json`.

