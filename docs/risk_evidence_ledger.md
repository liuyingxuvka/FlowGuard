# Risk Evidence Ledger

Risk Evidence Ledger is the final confidence boundary for FlowGuard work. It is
for the exact gap that ordinary testing often leaves behind: the model says a
risk was represented, tests are green, but no one checked whether the green
evidence actually covers the user-facing risk, the public code contract, and the
current route evidence. In strict mode, current evidence means more than a
`passed/current` declaration: each consumed row must carry a `ProofArtifactRef`
with a result path, artifact fingerprint, passing exit status, current route
evidence, matching obligation coverage, and an external-contract assertion
scope when the risk requires public behavior proof.

The ledger does not make FlowGuard models deeper. It connects the coarse model
to ordinary evidence:

```text
user risk -> UI real-surface/functional-chain/done-claim gates -> payload gates -> topology hazard review -> model obligation -> remembered maintenance obligation -> public code contract -> obligation-family gate -> analogous scan -> defect-family gate -> current proof evidence
```

If any link is missing, stale, skipped, progress-only, or internal-path-only, the
report downgrades the final claim instead of letting the agent say "fully
validated."

The defect-family link is only used when a same-class model miss recurs or is
high risk enough that another local point fix would overclaim the final
confidence boundary. It is a FlowGuard helper/evidence object consumed by the
existing Model-Miss Review, Model-Test Alignment, DevelopmentProcessFlow, and
Risk Evidence Ledger chain. It is not a new skill route and it is not owned by a
downstream app.

For non-trivial bug repairs, the ledger row should connect the repaired model
obligation, owner code contract, observed-regression proof, same-class proof,
analogous or family proof when relevant, and any legacy path disposition. If
one of those links is missing, the row should stay scoped or blocked rather
than reporting full confidence from a green command alone.

When the risk ledger depends on project-specific plan construction or evidence
adapter rows, run `review_plan_intake_completeness(...)`,
`review_evidence_adapter_conformance(...)`,
`review_false_negative_backpropagation(...)`, `review_plan_mutations(...)`, and
`review_flowguard_claim_chain(...)` before treating a ledger result as a broad
completion claim. The ledger checks declared risk rows; these helpers check
whether the rows and later claim promotion were too narrow.

## Public API

- `RiskEvidenceRow`: one user-meaningful risk and the model/code/evidence IDs
  that should prove it. Route-specific checks live in `gates`, not in separate
  flat fields per route.
- `RiskEvidenceGate`: one optional gate such as `defect_family`,
  `model_split`, `test_split`, `family`, `analogous_scan`,
  `ui_implementation`, `ui_real_surface`, `ui_functional_chain`,
  `ui_done_claim`, `matlab_callback_semantics`, `artifact_payload`,
  `topology_hazard`, `model_angle_review`, `parent_model_evidence`, or
  `maintenance_obligation`.
  A gate has one `kind`, one `evidence_id`, current status, confidence, and
  scoped reasons.
- `RiskEvidenceProof`: one test, replay, route report, or manual validation item.
  For full-confidence strict reviews, attach a `proof_artifact` instead of
  relying on the row's declared status alone.
- `ProofArtifactRef`: the concrete validation artifact produced by a command,
  replay, or evidence collector. Strict consumers reject missing artifacts,
  missing result paths, missing fingerprints, non-passing statuses, stale route
  evidence, progress-only artifacts, and internal-only assertion scope.
- `RiskEvidenceLedgerPlan`: the rows and evidence being reviewed.
- `MaintenanceObligation`: route-owned maintenance memory consumed by the
  ledger. Open obligations block, scoped obligations downgrade confidence, and
  resolved obligations need owner-route evidence ids.
- `RiskEvidenceLedgerReport`: final decision, confidence, and findings.
- `review_risk_evidence_ledger(plan)`: the executable checker.
- `DefectFamilyGate`, `DefectFamilyEvidence`,
  `DefectFamilyGatePlan`, and `review_defect_family_gates(plan)`: helper
  objects for proving recurring model-miss families before the ledger consumes
  the gate status.

## Minimal Example

```python
from flowguard import (
    OBLIGATION_STATUS_RESOLVED,
    RISK_GATE_ANALOGOUS_SCAN,
    RISK_GATE_ARTIFACT_PAYLOAD,
    RISK_GATE_DEFECT_FAMILY,
    RISK_GATE_FAMILY,
    RISK_GATE_MAINTENANCE_OBLIGATION,
    RISK_GATE_TOPOLOGY_HAZARD,
    RISK_GATE_MATLAB_CALLBACK_SEMANTICS,
    RISK_GATE_UI_DONE_CLAIM,
    RISK_GATE_UI_FUNCTIONAL_CHAIN,
    RISK_GATE_UI_IMPLEMENTATION,
    RISK_GATE_UI_REAL_SURFACE,
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    MaintenanceObligation,
    ProofArtifactRef,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)

plan = RiskEvidenceLedgerPlan(
    "submit-final-confidence",
    require_proof_artifacts=True,
    rows=(
        RiskEvidenceRow(
            "duplicate_submit",
            model_obligation_id="model:dedupe-submit",
            code_contract_id="api:submit_order",
            proof_evidence_ids=("test:helper-dedupe",),
            gates=(
                RiskEvidenceGate(RISK_GATE_FAMILY, "family:submit-routing"),
                RiskEvidenceGate(RISK_GATE_ANALOGOUS_SCAN, "analogous:submit-routing"),
                RiskEvidenceGate(RISK_GATE_TOPOLOGY_HAZARD, "topology:submit-routing"),
                RiskEvidenceGate(RISK_GATE_UI_IMPLEMENTATION, "ui:submit-clickthrough"),
                RiskEvidenceGate(RISK_GATE_UI_REAL_SURFACE, "ui:observed-inventory"),
                RiskEvidenceGate(RISK_GATE_UI_FUNCTIONAL_CHAIN, "ui:submit-functional-chain"),
                RiskEvidenceGate(RISK_GATE_UI_DONE_CLAIM, "ui:done-claim-review"),
                RiskEvidenceGate(RISK_GATE_MATLAB_CALLBACK_SEMANTICS, "ui:matlab-callbacks"),
                RiskEvidenceGate(RISK_GATE_ARTIFACT_PAYLOAD, "payload:submit-export"),
                RiskEvidenceGate(RISK_GATE_MAINTENANCE_OBLIGATION, "structure:submit-routing"),
                RiskEvidenceGate(RISK_GATE_DEFECT_FAMILY, "defect-family:duplicate-submit"),
            ),
        ),
    ),
    proof_evidence=(
        RiskEvidenceProof(
            "test:helper-dedupe",
            result_status=RISK_PROOF_STATUS_PASSED,
            assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH,
            proof_artifact=ProofArtifactRef(
                "artifact:test-helper-dedupe",
                result_status=RISK_PROOF_STATUS_PASSED,
                exit_code=0,
                result_path="tmp/test-helper-dedupe.json",
                artifact_fingerprints={"tmp/test-helper-dedupe.json": "sha256:..."},
                covered_obligation_ids=("model:dedupe-submit",),
                assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH,
            ),
        ),
    ),
    maintenance_obligations=(
        MaintenanceObligation(
            "structure:submit-routing",
            owner_route="structure_mesh_maintenance",
            reason_code="public_entrypoint_parity",
            status=OBLIGATION_STATUS_RESOLVED,
            evidence_ids=("structuremesh:submit-routing",),
        ),
    ),
)

report = review_risk_evidence_ledger(plan)
print(report.format_text())
```

This report blocks full confidence with `internal_path_only_evidence`: the test
passed, and the proof artifact is current, but it proved a helper path, not the
public submit behavior.

## Decisions

- `risk_evidence_full_confidence`: every in-scope required risk has a model
  obligation and current passing evidence at the expected boundary.
- `risk_evidence_scoped_confidence`: required in-scope risks pass, but an
  explicitly scoped-out row remains visible.
- blocker findings such as `missing_model_obligation`,
  `missing_code_contract`, `missing_family_gate`,
  `family_gate_not_current`, `family_gate_blocked`,
  `missing_analogous_scan`, `analogous_scan_not_current`,
  `analogous_scan_blocked`,
  `missing_ui_implementation_gate`, `ui_implementation_gate_not_current`,
  `ui_implementation_gate_blocked`,
  `missing_ui_real_surface_gate`, `ui_real_surface_gate_not_current`,
  `ui_real_surface_gate_blocked`,
  `missing_ui_functional_chain_gate`,
  `ui_functional_chain_gate_not_current`,
  `ui_functional_chain_gate_blocked`,
  `missing_ui_done_claim_gate`, `ui_done_claim_gate_not_current`,
  `ui_done_claim_gate_blocked`,
  `missing_matlab_callback_semantics_gate`,
  `matlab_callback_semantics_gate_not_current`,
  `matlab_callback_semantics_gate_blocked`,
  `missing_artifact_payload_gate`, `artifact_payload_gate_not_current`,
  `artifact_payload_gate_blocked`,
  `missing_topology_hazard_review`,
  `topology_hazard_review_not_current`,
  `topology_hazard_review_blocked`,
  `missing_maintenance_obligation`,
  `unknown_maintenance_obligation_reference`,
  `maintenance_obligation_not_current`,
  `open_maintenance_obligation`,
  `maintenance_obligation_missing_resolution_evidence`,
  `missing_defect_family_gate`,
  `defect_family_gate_not_current`, `defect_family_gate_blocked`,
  `missing_proof_evidence`, `missing_current_passing_proof`,
  `internal_path_only_evidence`, `stale_proof_evidence`,
  `route_gap_visible`, or `proof_evidence_not_passing`: do not claim full
  confidence.
- `defect_family_gate_scoped_confidence`: the recurring family gate is current
  but explicitly scoped; report scoped confidence instead of a full closure
  claim.
- `family_gate_scoped_confidence`: the obligation-family parity gate is current
  but only supports scoped confidence; do not upgrade the row to full
  confidence.
- `analogous_scan_scoped_confidence`: the same-shape defect radius scan is
  current but explicitly scoped; do not claim the repair covered every related
  surface.
- `topology_hazard_review_scoped_confidence`: the model-topology hazard review
  is current but only supports scoped confidence; do not upgrade model-shaped
  future-use risk to a full claim.
- `maintenance_obligation_scoped_confidence`: a remembered route-owned gap is
  explicitly scoped; carry that scoped confidence into the final claim.

## Route Responsibilities

- Model-Test Alignment produces model obligations, owner code contracts,
  optional code-boundary observations, obligation-family parity findings,
  model-code-test binding rows, and ordinary test evidence.
- TestMesh produces child-suite evidence status, freshness, skipped/timeout
  visibility, and release/routine boundaries.
- ModelMesh produces parent/child model evidence and reattachment status.
- Model Maturation produces model-upgrade or scoped-claim decisions when later
  route evidence says the model is too coarse, stale, or disconnected, and can
  emit maintenance obligations that later scans and ledgers inherit.
- Maintenance Scan consumes remembered maintenance obligations; anchored open
  obligations touched by the current change reopen their owner route, while
  unanchored observations stay visible without becoming unrelated hard gates.
- Model Topology Hazard Review produces anchored future-use hazard candidates
  from model shape and usage intent, then hands unresolved hazards to the
  owning route before the ledger accepts broad confidence.
- StructureMesh and UI Flow Structure produce public-entrypoint or journey
  evidence when structure or UI claims are involved.
- DevelopmentProcessFlow checks the ledger before done, archive, publish, or
  release claims.
- Model-Miss Review updates the ledger when runtime evidence proves that earlier
  model/test evidence was too narrow. When the same family recurs, it promotes
  or references a defect-family gate instead of treating the case as another
  ordinary point fix.

## Legacy Path Disposition

When a repair introduces a new route while the old route can still execute,
strict closure also requires a legacy path disposition. Valid outcomes are:
deleted, blocked, delegated to a repaired contract, same-contract repaired, or
explicitly out of scope with a reason. `unknown` blocks closure. Delegated and
same-contract-repaired paths should carry a proof artifact for the repaired
contract before the risk ledger restores full confidence.

Architecture Reduction's compatibility-surface classification can identify an
old or alternate surface before contraction, but it does not close an
executable old path by itself. If that old path remains reachable in a repair
or final-confidence claim, add a `LegacyPathDisposition` row with proof or a
scoped reason.

Use the template with:

```powershell
python -m flowguard risk-evidence-ledger-template --output .
python .flowguard/risk_evidence_ledger/run_checks.py
```
