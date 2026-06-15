# RiskProfile and Check Plans

The FlowGuard modeling entry remains small:

```text
RiskIntent + Workflow + FlowGuardCheckPlan + run_model_first_checks
```

For new or deepened FlowGuard models, do not start from a direct finite-engine
run. Use `FlowGuardCheckPlan` and `run_model_first_checks()` so
the model must name what it protects, bind the minimum useful model contract,
prove at least one representative known-bad case is caught, and close template
reuse/harvest.

The deterministic finite exploration engine remains underneath that runner. It
is not the public first-read path for non-trivial model creation.
See `docs/api_surface.md` for the API layer map.

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
        protected_error_classes=("duplicate_side_effect",),
        protected_harms=("downstream workflow acts on the same job twice",),
        must_model_state=("records", "side_effect_log"),
        must_model_side_effects=("record_write", "notification_send"),
        completion_evidence=("record_id", "side_effect_receipt"),
        adversarial_inputs=("same job repeated", "retry after partial progress"),
        hard_invariants=("one record per job", "one side effect per job"),
        known_bad_cases=("retry_writes_second_record",),
        used_template_ids=("side_effect_at_most_once",),
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

The `risk_intent` field is the normal place for the Risk Intent Brief. A
minimum valuable brief explains the failure modes, protected error classes,
protected harms, state and side effects that must be visible, completion
evidence, adversarial inputs to simulate, known-bad cases, used public/local
template ids or a no-match reason, hard invariants, and blindspots. Missing or
thin risk intent, missing template search/no-match reason, missing completion
evidence, or missing known-bad cases are pre-modeling gaps.

Confidence goals:

- `model_level`: report what the model checked.
- `production_conformance`: warn if production replay or equivalent real-code
  evidence is missing.
- `exploratory`: useful for early modeling; do not overstate confidence.

Skipped checks must include a reason. Skipped is not pass.

## FlowGuardCheckPlan

`FlowGuardCheckPlan` packages the formal runner invocation:

```python
from flowguard import FlowGuardCheckPlan, KnownBadProof, MinimumModelContract

plan = FlowGuardCheckPlan(
    workflow=workflow,
    initial_states=(initial_state,),
    external_inputs=(job_a, job_b),
    invariants=invariants,
    max_sequence_length=2,
    risk_profile=risk_profile,
    minimum_model_contract=MinimumModelContract(
        protected_error_classes=("duplicate_side_effect",),
        modeled_state=("records", "side_effect_log"),
        modeled_side_effects=("record_write", "notification_send"),
        completion_evidence=("record_id", "side_effect_receipt"),
        known_bad_cases=("retry_writes_second_record",),
    ),
    known_bad_proofs=(
        KnownBadProof(
            "retry_writes_second_record",
            protected_error_class="duplicate_side_effect",
            method="broken_workflow_variant",
            observed_status="failed",
            observed_failure="retry variant creates a second side effect",
        ),
    ),
)
```

Route-specific fields still exist for scenarios, contracts, progress config,
conformance status/report, scenario matrix config, and metadata. The minimum
model contract, template reuse/no-match review, known-bad proof, and template
harvest closure are not cosmetic; missing items become blocked or gap sections
instead of silent pass evidence.

## run_model_first_checks

`run_model_first_checks(plan)` returns a `FlowGuardSummaryReport`.

Execution order:

1. `ModelQualityAudit`
2. optional `ScenarioMatrixBuilder`
3. internal finite model run
4. counterexample minimization for the first invariant violation
5. scenario review when scenarios exist
6. optional transition coverage projection when broad model-to-code-to-test
   coverage is claimed
7. optional progress, contract, and conformance sections
8. unified summary report

If the finite model run fails, the summary fails. If it passes but audit has
warnings or generated scenarios need review, the summary is `pass_with_gaps`. If
conformance is not run, it is a confidence gap, not a failure and not a pass.
Generated transition coverage cells are also not pass evidence; project them to
Model-Test Alignment obligations and code contracts, then bind current test
evidence to the same cell and contract before claiming coverage.

For same-class, field/schema, payload, transition, parent/child, or no-delta
coverage beyond one representative known-bad proof, use ContractExhaustionMesh.
The owning route declares the finite boundary; `review_contract_exhaustion()`
creates canonical case ids and expected oracle reactions; MTA/TestMesh/ModelMesh
and the Risk Evidence Ledger close the evidence. Do not treat hand-written
analogous examples as exhaustive coverage.

Every `FlowGuardSummaryReport` also exposes `finding_ledger` and
`maintenance_obligations`, and `to_dict()` includes both as machine-readable
output. The ledger flattens model check failures, audit warnings,
scenario/live-audit gaps, progress findings, contract findings, conformance
findings, and skipped/not-run sections into one coverage-first list. The
maintenance obligations turn those non-pass gaps into route-owned memory for
future `review_maintenance_scan(...)` runs. Use them before FlowGuard or
LiveFlowGuard framework upgrades and non-trivial bug/model-miss repairs so the
next action is chosen deliberately: fix the real system, adjust the check flow,
extend the model, or record a boundary as out of scope. For in-scope
bug/model-miss repairs, the next action also includes root-cause
backpropagation, projecting the same-class or finite-boundary surface through
ContractExhaustionMesh, binding the owner code contract, and rerunning
Model-Test Alignment before full closure.

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
