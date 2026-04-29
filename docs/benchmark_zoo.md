# Benchmark Zoo

Phase 11 turns the problem corpus into a real-model benchmark zoo.
The goal is not to make a polished tool wrapper. The goal is to test whether
flowguard can model real workflow families rather than only the original
`job_matching` example or a generic executable template.

## Core Rule

Every case must bind to a real domain model:

```text
ProblemCase -> workflow-family model -> exact input sequence -> expected oracle -> observed result
```

The completion gate is:

```text
total_cases = 2100
real_model_cases = 2100
generic_fallback_cases = 0
not_executable_yet = 0
failure_cases = 0
model_variant_total = 150
model_families_with_six_variants = 25
```

`executable_cases = 2100` is not enough by itself. That only proves that a
runner executed something. Phase 11 requires that the execution uses the
workflow family's model blocks, state slots, variants, and structural
invariants.

## Model Binding

The current real-model corpus binding is implemented in:

```text
examples/problem_corpus/real_models.py
```

Each workflow family has a `DomainModelSpec` with:

- `model_name`;
- four domain block names;
- domain state slots;
- owners for source, processing, effect, and decision writes;
- side-effect slots derived from the corpus taxonomy.

Examples:

- `task_queue_leasing` uses `TaskQueueLeaseModel`;
- `retry_side_effect` uses `RetrySideEffectModel`;
- `cache_materialized_view` uses `CacheMaterializedViewModel`;
- `migration_schema_evolution` uses `SchemaMigrationModel`;
- `configuration_feature_flag_rollout` uses `FeatureFlagRolloutModel`.

Cases may share a model factory, but they may not fall back to a single generic
`CorpusApply`-style template.

The mature Phase 11.1 baseline adds `DomainVariantSpec`:

- 25 workflow families;
- six real model variants per family;
- 150 total variants;
- every case binds to one `variant_id`;
- every family must report all six variants in use.

The variants are architecture-level shapes, not 2000 near-duplicate model
files. For example, `task_queue_leasing` includes simple lease, heartbeat
lease, delayed retry, dead-letter queue, priority queue, and competing-worker
lease variants.

Phase 11.2 hardens this into a durable benchmark baseline. The additional
quality gates are:

```text
variant_min_cases >= 8
variants_below_target = 0
families_missing_required_case_kinds = 0
families_missing_required_bug_classes = 0
benchmark_conformance_family_count = 25
production_conformance_family_count = 26
total_replays = 78
failures = 0
```

The current balanced assignment gives every variant 13 to 15 executable cases.
That makes the benchmark useful as a standing regression baseline instead of a
mere "each variant was touched once" smoke check.

The final pre-freeze corpus also includes `pressure_100`: 100 cases across
bounded progress/fairness, eventual obligations, contract/refinement pressure,
and benchmark artifact stability. These are part of the main benchmark, not a
side suite. The progress/fairness pressure cases currently preserve
`known_limitation` outcomes for escape-edge cycles that bottom-SCC-only loop
checking cannot prove terminating.

## What The Models Check

Non-loop cases run through:

```text
DomainCommand
  -> family source block
  -> family processing block
  -> family effect block
  -> family finalize block
```

The state includes structural evidence such as:

- source records;
- process attempts;
- cache entries;
- side-effect records;
- decisions;
- trace links;
- owner writes;
- leases;
- audit events;
- terminal records;
- invalid transitions.

Failure modes are mapped to structural categories such as:

- duplicate side effect;
- repeated processing without refresh;
- cache/source mismatch;
- missing source traceability;
- wrong state owner;
- missing decision;
- contradictory or duplicate decision;
- lease violation;
- downstream non-consumable output;
- invalid transition.

Loop/stuck cases run through workflow-family-specific `LoopCheckConfig`
graphs. The graph nodes use the family block names rather than generic
`maybe/rewrite` labels.

## What This Proves

The Phase 11 real-model benchmark proves that all 2100 corpus cases can be
grounded in finite, deterministic, executable abstract models and checked with
expected-vs-observed reports.

The Phase 11.2 hardening report additionally proves that:

- every one of the 150 variants has meaningful case pressure;
- every workflow family covers all required case kinds;
- every workflow family covers the required benchmark bug classes;
- six priority non-job-matching families carry explicit scenario evidence;
- conformance replay is no longer only represented by `job_matching` because
  seed replays now cover all 25 benchmark workflow families.

It gives a stronger baseline than Phase 10.8:

- correct and boundary cases must pass;
- negative and invalid cases must produce expected violations;
- loop/stuck cases must produce graph evidence;
- every result must identify its model family and variant;
- no generic fallback is allowed.

## What This Does Not Prove

The benchmark still does not prove:

- full production correctness;
- unbounded termination;
- fairness or forced progress when a cycle has an escape edge;
- conformance of real production code for every benchmark family;
- complete formal refinement;
- correctness of real external systems or human decisions.

Those remain later work for conformance benchmarks, progress properties,
contract composition, and refinement.

## How To Run

Run:

```powershell
python examples/problem_corpus/run_executable_corpus_review.py
```

The report must include:

```text
real_model_cases: 2100
generic_fallback_cases: 0
model_variant_total: 150
model_families_with_six_variants: 25
```

Run the Phase 11.2 hardening review:

```powershell
python examples/problem_corpus/run_benchmark_hardening.py
```

The report must include:

```text
variant_min_cases: 13
variants_below_target: 0
families_missing_required_case_kinds: 0
families_missing_required_bug_classes: 0
benchmark_conformance_family_count: 25
production_conformance_family_count: 26
total_replays: 78
failures: 0
```

Run the full test suite:

```powershell
python -m unittest discover -s tests
```
