# Benchmark Baseline Contract

This document defines the durable benchmark baseline that future flowguard
upgrades must preserve. The goal is to keep the test rig useful as a long-term
product asset rather than reshaping it around each new feature.

## Frozen Baseline Shape

The main corpus is `real_software_problem_corpus`.

Current fixed shape:

- `total_cases: 2100`
- `base_1500: 1500`
- `gap_500: 500`
- `pressure_100: 100`
- `workflow_families: 25`
- `model_variant_total: 150`
- `model_families_with_six_variants: 25`
- `generic_fallback_cases: 0`
- `not_executable_yet: 0`

The `pressure_100` section is part of the main benchmark. It covers:

- bounded progress and fairness;
- eventual obligation and temporal order;
- contract composition and refinement;
- benchmark freeze and artifact stability.

The 25 bounded-progress cases were originally preserved as `known_limitation`.
After Phase 13 they are expected to report explicit progress findings:

- `potential_nontermination`;
- `missing_progress_guarantee`.

Do not relabel progress findings as `pass` without executable ranking,
bounded-progress, or equivalent progress evidence.

## Allowed Changes

Future phases may add new cases, reports, checkers, or metadata when those
changes are additive.

Allowed:

- adding a new corpus section with a clear section name;
- adding new pressure cases for a new checker;
- adding new report fields while preserving old fields;
- adding stronger oracles while keeping old expected-vs-observed outcomes
  auditable;
- adding new model variants if an existing family cannot represent a real
  software structure honestly.

## Disallowed Changes

Do not mutate the baseline to make a new phase look successful.

Disallowed:

- removing existing cases;
- weakening hard invariants;
- converting progress findings, `known_limitation`, or `needs_human_review`
  into `pass` without new executable evidence;
- replacing real model bindings with generic fallback templates;
- hiding raw production bugs through projection;
- changing expected statuses without documenting the architectural reason;
- using random generation, Monte Carlo, Hypothesis, external services, LLM APIs,
  databases, or GUI checks for this baseline.

## Verification Contract

Before claiming a major upgrade improved flowguard, run:

```powershell
python -m unittest discover -s tests
python examples/problem_corpus/run_corpus_review.py
python examples/problem_corpus/run_executable_corpus_review.py
python examples/problem_corpus/run_coverage_audit.py
python examples/problem_corpus/run_benchmark_hardening.py
```

The reports must preserve:

```text
total_cases: 2100
executable_cases: 2100
real_model_cases: 2100
generic_fallback_cases: 0
not_executable_yet: 0
failure_cases: 0
model_variant_total: 150
model_families_with_six_variants: 25
production_conformance_family_count: 26
benchmark_conformance_family_count: 25
total_replays: 78
failures: 0
```

If a future phase adds cases, the new total may increase, but old section
counts and old accepted outcomes must remain visible.

## Interpretation

This baseline proves that flowguard can run deterministic, model-first,
expected-vs-observed checks across a broad set of workflow families and
side-effect risks.
Phase 13 also proves that escape-edge cycles without a progress guarantee can
be reported as explicit progress findings instead of hidden limitations.

It does not prove:

- full production correctness;
- complete formal refinement;
- unbounded termination;
- complete fairness or liveness for every possible workflow;
- correctness of external systems or human decisions.

Those require later checkers. The baseline should make those gaps visible
instead of hiding them.
