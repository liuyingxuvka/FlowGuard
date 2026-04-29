# FlowGuard Framework Upgrade Checks

This page is for FlowGuard framework upgrades, benchmark claims, and internal
capability reports. It is not part of the ordinary project modeling path.

For normal project work, start with:

```text
State + FunctionBlock + Invariant + Explorer
```

Use `run_model_first_checks(...)`, scenario review, progress checks, contracts,
and conformance replay only when they fit the project risk. Do not require the
full internal benchmark suite for ordinary bug fixes.

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
