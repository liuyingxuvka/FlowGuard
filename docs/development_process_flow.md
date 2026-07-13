# DevelopmentProcessFlow

DevelopmentProcessFlow reviews a staged development lifecycle as a stateful
process: which steps run, which artifacts changed, which validation evidence
covered which versions, and whether the agent can safely continue or claim
done. It also checks whether a release, archive, or publish claim still has
current evidence.

It is the development-process front door for non-trivial rough-plan discussion,
multi-skill/tool setup, staged execution, install/sync, archive/publish/release,
post-change scanning, and final process claims. It can reference evidence ids
produced by ContractExhaustionMesh, ModelMesh, TestMesh, StructureMesh,
Model-Test Alignment, Model Topology Hazard Review, LongCheck, or Conformance
Adoption, but it does not inspect or supervise those route internals.

For product-language and validated-path changes, repository source, shadow
workspace, formal repository, editable package, installed skills, and local Git
are separate freshness domains. A passing receipt from one cannot stand in for
another. Peer or unknown-writer edits stale affected evidence and must be
re-read and merged; restoring an older green snapshot is not permission to
overwrite concurrent work. Background logs, PIDs, and heartbeats prove only
liveness until a terminal TestMesh receipt exists.

For behavior-bearing work, DevelopmentProcessFlow is also the first routing
place to select the behavior-ledger change mode: `bootstrap_ledger`,
`add_behavior`, `change_behavior`, `remove_or_replace_behavior`,
`coverage_gap_backfill`, or `model_miss_check`. This selection does not create
a new workflow. It tells the existing routes which evidence to refresh:
ExistingModelPreflight finds the owner model, Behavior Commitment Ledger
updates the external behavior row, ContractExhaustionMesh generates DCAR cases,
Model-Test Alignment and TestMesh bind current evidence, and SelfMaintenance
consumes the child reports before broad claims.

Process actions themselves remain in the `development_process` plane. Use
`ProcessAction.behavior_plane`, `target_behavior_planes`,
`target_commitment_ids`, and `typed_commitment_relation_refs` to say what the
process governs, invokes, validates, or consumes as evidence. Product
commitments and `agent_operation` steps are typed targets; referencing them
does not copy their behavior into this route or transfer their owner.

When a lifecycle claim is broad enough to say done, release, archive, publish,
or framework-sync confidence, use `require_proof_artifacts=True`. In that mode,
each consumed `ProcessEvidence` row must attach a proof artifact with a result
path and fingerprint; a green status string without a concrete artifact remains
only a declaration.

For vague or short upstream plans, enter DevelopmentProcessFlow first and let
its simulator select `plan_detailing` when needed (or use that delegated mode
when explicitly requested). `plan_detail_to_development_process(...)` converts
`ProcessArtifact`, ordered `PlanDetailStep`, `PlanDetailEvidence`,
`PlanDetailValidation`, and `PlanDetailFreshnessRule` rows into the lifecycle
shape below, including proof artifact references when a result path exists.
DevelopmentProcessFlow owns lifecycle order and evidence freshness; the
delegated plan-detail pass only proves that enough rows exist to continue.

## Public API

```python
from flowguard import (
    DevelopmentProcessPlan,
    FreshnessRule,
    ProofArtifactRef,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)

plan = DevelopmentProcessPlan(
    "checkout-lifecycle",
    require_proof_artifacts=True,
    artifacts=(
        ProcessArtifact("requirements.checkout", "requirement", "2"),
        ProcessArtifact("code.checkout", "code", "4"),
        ProcessArtifact("tests.checkout", "test", "1"),
    ),
    actions=(
        ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
        ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
        ProcessAction("claim-release", action_type="claim_release", required_evidence_ids=("unit-pass",)),
    ),
    evidence=(
        ProcessEvidence(
            "unit-pass",
            evidence_kind="unit",
            producer_route="test_mesh_maintenance",
            status="passed",
            covers_artifacts=("code.checkout",),
            verifier_artifacts=("tests.checkout",),
            covered_versions={"code.checkout": "3", "tests.checkout": "1"},
            produced_by_action_id="run-unit",
            proof_artifact=ProofArtifactRef(
                "artifact:unit-pass",
                result_status="passed",
                exit_code=0,
                result_path="tmp/unit-pass.json",
                artifact_fingerprints={"tmp/unit-pass.json": "sha256:..."},
                covered_obligation_ids=("unit-current",),
            ),
        ),
    ),
    validation_requirements=(
        ValidationRequirement(
            "unit-current",
            required_artifact_ids=("code.checkout",),
            required_evidence_kinds=("unit",),
            evidence_ids=("unit-pass",),
        ),
    ),
)

report = review_development_process_flow(plan)
print(report.format_text())
```

The report flags stale evidence because `unit-pass` covered `code.checkout@3`
while the current artifact is `code.checkout@4`.

## What It Checks

- non-trivial staged development or modification sequences such as plan, edit,
  test, fix, and verify;
- unknown artifact, evidence, validation, and action references;
- out-of-order process dependencies;
- stale evidence after code, test, model, requirement, field lifecycle, field
  projection, replacement disposition, bug-repair closure, or direct
  invalidation;
- verifier changes after validation, such as tests or model files changing;
- UI action-map, visible-control, click-through, pure-UI classification, or
  manual/native-dialog boundary changes after implementation evidence;
- UI observed inventory, human-operability, enabled-control functional chain,
  source-baseline interaction gate, or UI done-claim review changes after evidence was produced;
- payload schema, fixture, real import/export/save/load/generate behavior,
  generated artifact, or AI work-package format changes after synthetic payload
  evidence;
- explicit upstream freshness rules, such as requirement changes invalidating
  downstream code and validation evidence;
- model-miss repair changes that invalidate earlier alignment evidence, such
  as a new miss classification, ContractExhaustionMesh case id, closure
  evidence role, or test row used to prove closure;
- bug-repair evidence changes that invalidate earlier closure, such as a new
  root-cause backpropagation record, owner code contract, old-path
  disposition, observed-regression test, contract-exhaustion case
  test, or Risk
  Evidence Ledger row;
- ambiguous freshness policy for declared upstream/downstream artifacts;
- progress-only background evidence, hidden skipped validation, failed
  evidence, and not-run evidence;
- background completion claims without a final `run_id`, terminal `passed`
  status, exit code 0, concrete result artifact and fingerprint, covered
  obligation ids, inventory revision, and current artifact/verifier versions;
- UI task checkboxes without current evidence type, such as model coverage,
  static test, runtime click, browser DOM/geometry, desktop/manual
  observation, native-dialog blindspot, work mode, source baseline,
  source-target mapping, source interaction, observed-source alignment,
  observed inventory, functional chain,
  human-operability, implementation validation, or done-claim review;
- final done, archive, publish, or release claims that have no current Risk
  Evidence Ledger decision;
- FlowGuard framework upgrade claims that have no current model-impact
  freshness decision for existing `.flowguard` models;
- missing V-style validation pairs;
- release-required evidence under routine and release scopes;
- minimum revalidation recommendations.

## Template

Use the starter template in another project:

```powershell
python -m flowguard development-process-flow-template --output .
```

The template writes:

- `.flowguard/development_process_flow/model.py`
- `.flowguard/development_process_flow/run_checks.py`
- `docs/flowguard_development_process_flow.md`

The generated model includes one green lifecycle and one broken lifecycle where
a release claim reuses stale validation evidence after code and requirement
changes.

## Boundary

Use DevelopmentProcessFlow when non-trivial staged development or modification
work has validation, or when development ordering and evidence freshness are the
risk. Skip only for truly single-step work with no meaningful validation or
artifact freshness risk, such as a tiny typo fix, pure explanation, or
formatting-only change. Use TestMesh when the validation hierarchy itself needs
a parent/child split. Use StructureMesh when code structure is being split. Use
Model-Test Alignment when model obligations and test or code-contract evidence
need direct comparison. Use Conformance Adoption when production traces or
install/runtime sync determine confidence.

For field-bearing work, register field lifecycle plans, field projections,
replacement disposition rows, and bug-repair closure rows as first-class
process artifacts. Evidence that covered those artifacts before a later write
must be rerun or refreshed before done, release, archive, or publish
confidence.

UI implementation validation and artifact payload validation are freshness
sensitive. If a reachable enabled control, modeled UI event, real payload
surface, file format, generated artifact, or AI work-package schema changes
after evidence was captured, rerun UI Flow Structure implementation evidence,
Model-Test Alignment payload validation, or TestMesh payload child evidence
before a done or release claim consumes the old evidence.
OpenSpec artifact completion is not release completion for UI work. A checked
task must name a current evidence type, and a broad done/release claim must
consume observed-inventory, functional-chain, source-baseline interaction
semantics when applicable, `UIImplementationValidation`, and UI done-claim
review evidence.

For final completion claims, DevelopmentProcessFlow should reference the Risk
Evidence Ledger decision as one evidence boundary. If the ledger reports
`risk_evidence_full_confidence`, the process may consume that evidence subject
to freshness rules. If it reports scoped confidence, stale proof,
internal-path-only evidence, progress-only evidence, or a missing route handoff,
the process claim remains scoped or blocked until the owning route supplies
current proof.

When the final claim depends on layered parent/child model confidence,
DevelopmentProcessFlow should reference the layered proof report as a sibling
evidence id. Parent coverage edits, child ownership or contract edits, child
evidence-id changes, and leaf code/test/observation edits stale the related
layered proof rows until they are rerun and reattached.

When the final claim depends on ModelMesh closure, DevelopmentProcessFlow should
also reference the closure report and any transition coverage, Model-Test
Alignment, or TestMesh rows projected from it. Child-output edits,
reattachment-contract edits, repeat-input token changes, repair-feedback token
changes, and runtime node/code contract edits stale those derived rows until
they are regenerated and rerun.

When the final claim closes a model miss or non-trivial bug repair,
DevelopmentProcessFlow should include Model-Test Alignment as a required
validation pair for the repaired model obligation, owner code contract, and
observed/contract-exhaustion case test rows. It should also include the root-cause
backpropagation record, old-path disposition, and Risk
Evidence Ledger row as freshness-sensitive artifacts. If the contract-exhaustion
evidence is large, slow, background, layered, or release-only, it should also
include TestMesh evidence and keep routine confidence scoped until current
release evidence exists.

When the work changes a field/schema boundary, same-class family, payload
contract, transition matrix, parent/child closure, or no-delta loop, rerun
ContractExhaustionMesh before consuming downstream Model-Test Alignment,
TestMesh, ModelMesh, or Risk Evidence Ledger evidence. A stale generated case
matrix is stale process evidence even when a downstream green test still
exists.

When later implementation, validation, alignment, mesh, code-boundary, or
freshness evidence says the model itself is too coarse, stale, disconnected, or
missing an obligation, DevelopmentProcessFlow should also consume
`review_model_maturation_loop(...)`. The lifecycle claim stays scoped or blocked
until the required model upgrade is resolved or explicitly out of scope.

Before done, release, archive, publish, or production-confidence claims,
DevelopmentProcessFlow should review direct model-code-test evidence freshness.
When size, pending states, slow duration, broad obligation coverage,
background progress-only logs, or release-only scope could hide the need for
ModelMesh or TestMesh, run AutoSplit/ModelMesh/TestMesh as its own route and
consume that route's current evidence id or proof artifact here. Do not copy
AutoSplit metrics onto `ProcessEvidence`.

When a lifecycle claim depends on an AI-built plan, a project-specific evidence
adapter, a post-green false-negative repair, or known-bad mutation probes,
DevelopmentProcessFlow should also consume the plan-intake and typed claim-chain
reports as current evidence. `review_plan_intake_completeness(...)`,
`review_evidence_adapter_conformance(...)`,
`review_false_negative_backpropagation(...)`, `review_plan_mutations(...)`, and
`review_flowguard_claim_chain(...)` keep plan-only, model-only, or alignment-only
results from being reported as production confidence.

When a lifecycle claim is a FlowGuard framework upgrade or installed helper
sync, DevelopmentProcessFlow should also consume
`review_model_impact_freshness(...)`. Affected old models remain blocked until
current rerun evidence exists. Unchanged old models can reuse previous evidence
only when a reuse ticket proves the model, dependencies, FlowGuard semantics,
previous evidence, and output fingerprint are still current. Unchanged old test
results can be reused only when a `TestResultReuseTicket` and matching
`ProofArtifactRef` prove the command, test source, tested artifacts,
dependencies, environment, result fingerprint, and covered obligation scope are
current. Later writes that touch any of those fields stale the reuse proof and
force a rerun or refreshed ticket before done confidence.
