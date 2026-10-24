# Evidence Baseline

This is FlowGuard's own regression baseline, rather than a mechanism projects
need to adopt. It records what the engine catches, what it does not claim, and
what remains a known limitation before and after an upgrade.

The baseline is not a replacement for unit tests. It is a structured scorecard
that combines several evidence sources:

- job-matching scenario review;
- job-matching conformance replay;
- job-matching model checks;
- loop/stuck review.

## Why This Exists

Engine changes should show their effects on actual model checking, replay,
progress properties, composition and engineering behaviour. The expected versus
observed baseline makes it possible to see whether new bug classes are caught,
known limitations are reduced, or existing coverage remains stable.

## Evidence Case

An `EvidenceCaseResult` records one baseline condition:

- `name`
- `group`
- `bug_class`
- `expected`
- `observed`
- `status`
- `evidence`

Accepted statuses are:

- `pass`
- `expected_violation_observed`
- `needs_human_review`
- `known_limitation`

Failure statuses are:

- `unexpected_violation`
- `missing_expected_violation`
- `oracle_mismatch`
- `failed`

The baseline is OK only when no failure status appears and the configured
minimum case count is met.

## Evidence Baseline Report

An `EvidenceBaselineReport` aggregates cases into:

- total case count;
- target case count;
- status counts;
- group counts;
- bug-class counts;
- failed cases;
- text and JSON export.

The current target is at least 50 executed evidence cases; the maintained baseline runs 56. This count should
not be treated as magic. It is a guard against upgrading from too little
evidence.

## Groups

The baseline includes:

- `scenario:job_matching`
- `conformance:job_matching`
- `model_check:job_matching`
- `loop:looping_workflow`

The baseline runs its declared examples; it does not import test modules or count
test names as execution evidence. Run the real test suite separately:

```powershell
python -m pytest -q
```

## Bug Classes

The baseline intentionally groups evidence by bug class, not only by file or
test name. Current bug classes include:

- duplicate side effect;
- repeated processing without refresh;
- cache consistency;
- state owner boundary;
- source traceability;
- downstream non-consumable output;
- missing decision;
- contradictory decision;
- duplicate decision;
- projection anti-pattern;
- non-terminating component;
- stuck state;
- unreachable success;
- terminal semantics;
- progress/fairness known limitation.

This grouping helps compare the behaviour of successive engine revisions.

## How To Run

Run the baseline:

```powershell
python examples/evidence_baseline/run_baseline.py
```

Run the full test suite:

```powershell
python -m pytest -q
```

When evaluating an engine upgrade, record actual results for the compared
revisions and compare status counts and bug-class counts. Reuse an already
completed run on the same source where its scope is sufficient.

## How To Interpret Changes

Good changes:

- a known limitation becomes an expected violation observed;
- a missing expected violation becomes caught;
- a new benchmark adds a new bug class without breaking old cases;
- the same expected-vs-observed semantics remain stable.

Bad changes:

- `unexpected_violation` appears in previously passing cases;
- `missing_expected_violation` appears in known broken cases;
- `needs_human_review` or `known_limitation` is silently converted to `pass`;
- adapter projection hides a raw production bug;
- the case count drops below the target without explanation.

## Limits

The baseline runs and summarizes engine examples. It adds no mathematical
checking power and cannot substitute for the real models, conformance adapters
or tests that exercise a change.
