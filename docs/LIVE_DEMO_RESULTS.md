# Live official-web/local-model results

- Run date: 2026-08-18
- Mode: official company websites plus local OpenAI-compatible model
- Companies: Microsoft Corporation, Apple Inc., NVIDIA Corporation
- Model: Ollama 0.32.14 with `gemma3:4b`
- External API credentials: none

## Result

| Metric | Measured value |
|---|---:|
| Companies queued | 3 |
| Companies complete | 3 |
| Companies failed | 0 |
| Unique final field rows | 45 |
| `found` rows | 27 |
| `not_found` rows | 1 |
| `source_unreachable` rows | 2 |
| `validation_failed` rows | 15 |
| Validation-failure counter | 15 |
| Retries | 2 |
| Job claims | 3 |
| End-to-end elapsed time | 84.16011 seconds |

The status totals equal all 45 expected company/field records, and the validation-failure metric
matches the 15 persisted `validation_failed` records. Each company completed independently.

## Failure behavior observed

The local 4-billion-parameter model produced two retryable boundary violations during the run:

- one commercial-group response contained truncated JSON;
- one public-presence response cited a LinkedIn URL that the research tool had not supplied.

Both were rejected, logged, retried with bounded backoff, and isolated without failing the company
or stopping the queue. Other semantic problems were rejected at field granularity, so a bad year,
count, ticker, URL, or placeholder did not erase valid sibling fields.

## Evidence files

- `evidence/live_demo_results.json`: machine-readable run metadata, reconciled counts, and hashes.
- `evidence/live_demo_excerpt.jsonl`: key start, validation, retry, company completion, and final
  events.

The full 45-row export and complete event log are reproducible runtime artifacts and remain ignored.
Their measured SHA-256 hashes are:

| Artifact | SHA-256 |
|---|---|
| Full JSON results export | `4452508E623F1028BE05C95D7EE934786F570158B3D49BD05B07463DF9E855E4` |
| Full JSON Lines event log | `A008747978E3B99D37C11290A9554B1EBD4E7C7B96FD90A3AA8ED6AF980BB6A0` |

## Evidence boundary

This run verifies end-to-end official-page retrieval, local model invocation, strict structured
output, per-field semantic validation, citation allowlisting, retries, persistence, and unattended
continuation. It is intentionally not presented as an accuracy benchmark: official pages can omit
fields, page text can be noisy, and model-derived facts require human review before consequential
use. Results from `gemma3:4b` should not be generalized to a different model or provider.
