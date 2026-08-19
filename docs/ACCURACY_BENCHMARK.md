# Accuracy benchmark

## Purpose

The benchmark turns a JSON export into a reproducible field-level scorecard. It is deliberately
separate from schema validation: a result can be well-formed and cited while still disagreeing
with a reference label.

The default label source is `benchmarks/primary_source_labels.v1.json`. It contains 25 companies,
50 dated primary sources, and 125 verified labels across five objective fields: legal name,
official website, headquarters, ownership status, and stock ticker. Each label retains its source
identifier, evidence locator, review date, and verification status.

The source registry uses current annual Form 10-K filings for legal identity, principal executive
offices, public registration, and trading symbols. Official company sites support the canonical
website label. Headquarters omit postal details, and companies with multiple traded share classes
use the Class A symbol. The generated file is reproducible from
`scripts/build_primary_source_labels.py`; its reviewed values are independent from the demo fixture.

The remaining ten fields are explicitly excluded rather than silently inherited from the authored
fixture. Subjective fields need a taxonomy or semantic rubric; volatile and numeric fields need an
as-of/tolerance policy; careers and external social URLs need canonicalization and ownership rules.

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

`evidence/live_accuracy_primary_source_v1.json` scores the previously recorded Microsoft, Apple,
and NVIDIA local-model run. The command uses `--scope-to-predictions`, so the other 22 reference
companies do not count as missing predictions. On the 15 primary-source labels in scope, the run
answered 13, matched 9 exactly, achieved 86.7% coverage, 69.2% precision when answered, and 60.0%
overall exact-match accuracy.

This is a source-grounded engineering baseline, not a general production accuracy claim. The
current set has one primary-source desk review and intentionally narrow exact-match fields. That is
the completed scope for this portfolio application. Optional governance improvements for a future
consequential production system are:

1. add independent review if the benchmark will control release decisions;
2. define acceptable aliases and numeric tolerances before expanding scored fields;
3. refresh or expire labels when their source snapshot becomes stale;
4. report results by field and company cohort, not only one aggregate percentage.

## Commands

Full reference cohort:

```bash
research-agent benchmark data/results.json --output evidence/accuracy.json
```

Partial recorded cohort:

```bash
research-agent benchmark data/live-batch3-evidence-results.json \
  --scope-to-predictions \
  --output evidence/live_accuracy_primary_source_v1.json
```

Rebuild the materialized label file after a reviewed metadata change:

```bash
python scripts/build_primary_source_labels.py
```
