# Accuracy benchmark

## Purpose

The benchmark turns a JSON export into a reproducible field-level scorecard. It is deliberately
separate from schema validation: a result can be well-formed and cited while still disagreeing
with a reference label.

The default label source is `fixtures/companies.json`. It contains 25 companies and 300 authored
labels across 12 fields. Three volatile or unavailable fields (`ceo`, `employee_count_estimate`,
and `recent_development`) are not labeled and are reported as unsupported predictions instead of
being silently scored.

## Metrics

- **accuracy_overall**: correct answers divided by all labels in scope;
- **coverage**: found predictions divided by all labels in scope;
- **precision_when_answered**: correct answers divided by found predictions;
- **abstained**: a row exists but its status is not `found`;
- **missing**: no prediction row exists for a label;
- **unsupported predictions**: result rows whose company/field pair has no label.

Text comparison is Unicode-normalized, case-insensitive, and whitespace-normalized. Lists are
compared as normalized unordered values. URLs normalize scheme/host casing, default ports,
fragments, and trailing slashes. The evaluator otherwise uses exact match; it does not award
semantic similarity that could conceal a factual error.

## Recorded baseline

`evidence/live_accuracy_baseline.json` scores the previously recorded Microsoft, Apple, and NVIDIA
local-model run. The command uses `--scope-to-predictions`, so the other 22 reference companies do
not count as missing predictions.

This is an initial engineering baseline, not a production accuracy claim. The reference labels
were authored for deterministic replay and have not been independently reviewed against dated
primary sources. A production benchmark should:

1. retain a dated source URL and reviewer for every label;
2. use at least two reviewers for ambiguous or time-sensitive fields;
3. version the label snapshot separately from model runs;
4. define acceptable aliases and numeric tolerances before scoring;
5. report results by field and company cohort, not only one aggregate percentage.

## Commands

Full reference cohort:

```bash
research-agent benchmark data/results.json --output evidence/accuracy.json
```

Partial recorded cohort:

```bash
research-agent benchmark data/live-batch3-evidence-results.json \
  --scope-to-predictions \
  --output evidence/live_accuracy_baseline.json
```
