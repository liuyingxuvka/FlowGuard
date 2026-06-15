# FlowGuard Framework Upgrade Checks

This page is for FlowGuard framework upgrades, benchmark claims, and internal
capability reports. It is not part of the ordinary project modeling path.

For normal project work, start with the formal minimum model entry:

```text
RiskIntent + Input x State -> Set(Output x State)
-> MinimumModelContract + KnownBadProof
-> FlowGuardCheckPlan + run_model_first_checks
```

Use scenario review, progress checks, contracts, and conformance replay when
they fit the project risk. Do not require the full internal benchmark suite for
ordinary bug fixes.

## When To Use This Page

Use these checks when the task changes FlowGuard itself or makes a claim such
as:

- a new FlowGuard framework capability;
- a benchmark baseline improvement;
- broad corpus coverage;
- product-grade benchmark maturity;
- production-conformance seed coverage for the benchmark suite.

Do not use these checks merely because a target project used FlowGuard for one
model-first change.

## Coverage-First Failure Triage

For FlowGuard or LiveFlowGuard framework upgrades triggered by a concrete
failure, start with coverage before adding a point rule. Build the full finding
ledger from the latest model check, model-quality audit, scenario or live-audit
evidence, progress review, contract checks, conformance replay, skipped/not-run
sections, and adoption evidence.

Use that ledger to choose the repair class:

- fix the real system when existing checks already expose the defect;
- adjust the check flow when required checks were skipped, downgraded, or
  hidden under `pass`;
- extend the model when the real failure was outside the current abstraction;
- mark the boundary out of scope when the issue is intentionally not covered.

Do not default to a point-rule patch for the first visible failure until the
ledger shows the rest of the relevant coverage surface has been considered.

## Upgrade Baseline

Before and after major FlowGuard upgrades, run:

```powershell
python examples/evidence_baseline/run_baseline.py
```

The baseline records unit inventory, scenario review outcomes, conformance
replay outcomes, model-check outcomes, loop/stuck review outcomes, and a
bug-class scorecard.

Do not silently convert `needs_human_review`, `known_limitation`,
`unexpected_violation`, `missing_expected_violation`, or `oracle_mismatch`
statuses into ordinary passes.

## Existing Model Impact Freshness

Before saying a FlowGuard framework upgrade has covered existing `.flowguard`
models, classify the model inventory with `review_model_impact_freshness(...)`.
This is a selective gate, not a blanket rerun rule:

- affected models need model/test update review plus current passing rerun
  evidence;
- not-impacted models may reuse old evidence only with a current reuse ticket,
  previous evidence id, fingerprint or same-output proof, and a reason;
- unchanged test results may reuse old evidence only with a current
  `TestResultReuseTicket` and `ProofArtifactRef` that prove unchanged command,
  test source, tested artifact, dependency, environment, result fingerprint,
  and coverage scope;
- directly touched dependencies or FlowGuard semantic ids need a narrower
  non-impact rationale before reuse is accepted;
- deprecated models must stay visible with a replacement model and reason;
- unknown or blocked classifications prevent broad upgrade freshness claims.

Run the executable gate model when changing this protocol:

```powershell
python .flowguard/model_impact_freshness_gate/run_checks.py
```

This prevents both unsafe old-evidence reuse and wasteful full reruns when the
model result is demonstrably unchanged.

## Problem Corpus Review

For major framework upgrades, keep the broader problem corpus visible:

```powershell
python examples/problem_corpus/run_corpus_review.py
```

This checks the problem-intent matrix. It is not the same as executable
behavior testing, so reports must distinguish:

```text
Problem-intent corpus: 2100 cases
Executable corpus review: <executable_cases> executable cases
Evidence baseline: <N> evidence cases
Unit-test inventory: <U> test entries
```

## Executable Corpus Review

For behavior-test coverage claims, run:

```powershell
python examples/problem_corpus/run_executable_corpus_review.py
```

Do not call `total_cases: 2100` executable coverage unless the report shows:

```text
executable_cases: 2100
not_executable_yet: 0
failure_cases: 0
```

For real-model capability claims, the report should also show:

```text
real_model_cases: 2100
generic_fallback_cases: 0
model_variant_total: 150
model_families_with_six_variants: 25
```

The `pressure_100` cases are part of the baseline. Keep `known_limitation`
honest for pressure cases the current checker cannot prove.

## Product-Grade Benchmark Claims

For durable benchmark maturity claims, run:

```powershell
python examples/problem_corpus/run_benchmark_hardening.py
```

The hardening report should show:

```text
variant_min_cases >= 8
variants_below_target: 0
families_missing_required_case_kinds: 0
families_missing_required_bug_classes: 0
benchmark_conformance_family_count = 25
production_conformance_family_count = 26
total_replays = 78
failures = 0
```

A model variant should not count as mature if it was only touched shallowly.

## Production-Conformance Seed Claims

For production-conformance seed claims, run:

```powershell
python examples/problem_corpus/run_conformance_seeds.py
```

The report should confirm that all 25 benchmark workflow families have correct
and broken replay seeds, plus the legacy `job_matching` example.

## What This Page Does Not Prove

The internal benchmark suite does not prove:

- conformance of arbitrary production code;
- correctness of every possible project model;
- that ordinary projects must run FlowGuard's internal evidence suite;
- that a model-only pass is production confidence.

Use project-specific conformance replay or equivalent real-code evidence before
claiming production confidence for a target project.
