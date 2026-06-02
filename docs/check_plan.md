# RiskProfile and Check Plans

The direct FlowGuard path remains:

```text
State + FunctionBlock + Invariant + Explorer
```

`RiskProfile`, `FlowGuardCheckPlan`, and `run_model_first_checks()` are optional
orchestration helpers for AI coding agents that need a single low-friction
entry point.

They live in the reporting/helper layer, not the core layer. Direct
`Explorer(...)` use remains the simplest valid path; see `docs/api_surface.md`
for the API layer map.

## RiskProfile

`RiskProfile` declares what the current model is trying to cover. Start with a
Risk Intent Brief so the model is aimed at the accidents it should expose:

```python
from flowguard import RiskIntent, RiskProfile, SkippedCheck

risk_profile = RiskProfile(
    modeled_boundary="job recording",
    risk_classes=("deduplication", "idempotency"),
    risk_intent=RiskIntent(
        failure_modes=("duplicate job record", "retry creates second side effect"),
        protected_harms=("downstream workflow acts on the same job twice",),
        must_model_state=("records", "side_effect_log"),
        adversarial_inputs=("same job repeated", "retry after partial progress"),
        hard_invariants=("one record per job", "one side effect per job"),
        blindspots=("real database isolation is checked by conformance replay"),
    ),
    confidence_goal="model_level",
    skipped_checks=(
        SkippedCheck("conformance_replay", "no production adapter yet"),
    ),
)
```

Known risk classes include:

- `deduplication`
- `idempotency`
- `cache`
- `retry`
- `side_effect`
- `queue`
- `loop`
- `module_boundary`
- `conformance`

Unknown risk classes are allowed. They appear as warnings because the audit
heuristics only know the standard classes.

The `risk_intent` field can be omitted for direct or minimal plans, but agents
should treat a missing or thin Risk Intent Brief as a pre-modeling gap. It
should explain the failure modes, protected harms, state and side effects that
must be visible, adversarial inputs to simulate, hard invariants, and known
blindspots. Direct `Explorer(...)` usage can keep the same brief in comments,
model notes, or the adoption log instead of using `RiskProfile`.

Confidence goals:

- `model_level`: report what the model checked.
- `production_conformance`: warn if production replay or equivalent real-code
  evidence is missing.
- `exploratory`: useful for early modeling; do not overstate confidence.

Skipped checks must include a reason. Skipped is not pass.

## FlowGuardCheckPlan

`FlowGuardCheckPlan` packages one optional runner invocation:

```python
from flowguard import FlowGuardCheckPlan

plan = FlowGuardCheckPlan(
    workflow=workflow,
    initial_states=(initial_state,),
    external_inputs=(job_a, job_b),
    invariants=invariants,
    max_sequence_length=2,
    risk_profile=risk_profile,
)
```

Optional fields include scenarios, contracts, progress config, conformance
status/report, scenario matrix config, and metadata. Missing optional fields do
not fail the plan; they become `not_run`, `skipped_with_reason`, or audit gaps
when relevant.

## run_model_first_checks

`run_model_first_checks(plan)` returns a `FlowGuardSummaryReport`.

Execution order:

1. `ModelQualityAudit`
2. optional `ScenarioMatrixBuilder`
3. `Explorer`
4. counterexample minimization for the first invariant violation
5. scenario review when scenarios exist
6. optional transition coverage projection when broad model-to-code-to-test
   coverage is claimed
7. optional progress, contract, and conformance sections
8. unified summary report

If Explorer fails, the summary fails. If Explorer passes but audit has warnings
or generated scenarios need review, the summary is `pass_with_gaps`. If
conformance is not run, it is a confidence gap, not a failure and not a pass.
Generated transition coverage cells are also not pass evidence; project them to
Model-Test Alignment obligations and code contracts, then bind current test
evidence to the same cell and contract before claiming coverage.

Every `FlowGuardSummaryReport` also exposes `finding_ledger` and
`maintenance_obligations`, and `to_dict()` includes both as machine-readable
output. The ledger flattens model check failures, audit warnings,
scenario/live-audit gaps, progress findings, contract findings, conformance
findings, and skipped/not-run sections into one coverage-first list. The
maintenance obligations turn those non-pass gaps into route-owned memory for
future `review_maintenance_scan(...)` runs. Use them before FlowGuard or
LiveFlowGuard framework upgrades and post-runtime model-miss repairs so the
next action is chosen deliberately: fix the real system, adjust the check flow,
extend the model, or record a boundary as out of scope. For in-scope
model-miss repairs, the next action also includes upgrading tests from an
observed-bug regression to same-class evidence and rerunning Model-Test
Alignment before full closure.

## Domain Packs

Domain packs are small recipes:

```python
from flowguard import DeduplicationPack

pack = DeduplicationPack(
    record_selector=lambda state: state.records,
    key=lambda record: record.job_id,
    value_name="record",
)

invariants = pack.invariants()
```

Available packs:

- `DeduplicationPack`
- `CachePack`
- `RetryPack`
- `SideEffectPack`

Packs only create optional invariants and scenario scaffolds from selectors and
keys you provide. They are not a plugin system, not a DSL, and not required for
valid FlowGuard use.
