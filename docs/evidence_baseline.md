# Evidence Baseline

Phase 10.5 adds an upgrade-readiness baseline before Phase 11. The goal is to
avoid blind upgrades. Before adding new mathematical or engineering features,
`flowguard` should know what the current system catches, what it does not
claim, and what remains a known limitation.

The baseline is not a replacement for unit tests. It is a structured scorecard
that combines several evidence sources:

- unit-test inventory;
- job-matching scenario review;
- job-matching conformance replay;
- job-matching model checks;
- loop/stuck review.

## Why This Exists

Future phases add substantial capability:

- Phase 11 adds benchmark breadth.
- Phase 12 extends production conformance breadth.
- Phase 13 adds progress/fairness/temporal checks.
- Phase 14 adds contract composition and refinement.
- Phase 15 adds engineering hardening.

Those upgrades should show measurable evidence. A phase is not useful merely
because it adds code. It is useful when the expected-vs-observed baseline shows
that new bug classes are caught, known limitations are reduced, or current
coverage stays stable while the model gets stronger.

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

The current target is at least 100 structured evidence cases. This count should
not be treated as magic. It is a guard against upgrading from too little
evidence.

## Groups

The Phase 10.5 baseline includes:

- `unit_test_inventory`
- `scenario:job_matching`
- `conformance:job_matching`
- `model_check:job_matching`
- `loop:looping_workflow`

The unit-test inventory records test presence; actual test execution still
happens through:

```powershell
python -m unittest discover -s tests
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

This grouping is what lets future phases prove they helped.

## How To Run

Run the baseline:

```powershell
python examples/evidence_baseline/run_baseline.py
```

Run the full test suite:

```powershell
python -m unittest discover -s tests
```

Before Phase 11 or later upgrades, run both commands and save the observed
scorecard mentally or as an artifact if needed. After the upgrade, run them
again and compare status counts and bug-class counts.

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

Phase 10.5 is an evidence harness. It does not add new mathematical checking
power. It does not implement the Phase 11 benchmark zoo, Phase 13 progress
properties, or Phase 14 contract/refinement checks. It prepares the project to
measure those upgrades when they happen.
