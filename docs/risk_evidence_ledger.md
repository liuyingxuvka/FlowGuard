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
user risk -> model obligation -> public code contract -> obligation-family gate -> analogous scan -> defect-family gate -> current proof evidence
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

When the risk ledger depends on project-specific plan construction or evidence
adapter rows, run `review_plan_intake_completeness(...)`,
`review_evidence_adapter_conformance(...)`,
`review_false_negative_backpropagation(...)`, `review_plan_mutations(...)`, and
`review_flowguard_claim_chain(...)` before treating a ledger result as a broad
completion claim. The ledger checks declared risk rows; these helpers check
whether the rows and later claim promotion were too narrow.

## Public API

- `RiskEvidenceRow`: one user-meaningful risk and the model/code/evidence IDs
  that should prove it. Rows can require a current `defect_family_id` when a
  recurring or high-risk same-class model miss family must be closed before
  full confidence. Rows can also require a current family parity gate when a
  risk claims several sibling obligations are equivalently covered. After a
  model miss, rows can require a current analogous defect scan so the final
  claim cannot ignore same-shape sibling risks.
- `RiskEvidenceProof`: one test, replay, route report, or manual validation item.
  For full-confidence strict reviews, attach a `proof_artifact` instead of
  relying on the row's declared status alone.
- `ProofArtifactRef`: the concrete validation artifact produced by a command,
  replay, or evidence collector. Strict consumers reject missing artifacts,
  missing result paths, missing fingerprints, non-passing statuses, stale route
  evidence, progress-only artifacts, and internal-only assertion scope.
- `RiskEvidenceLedgerPlan`: the rows and evidence being reviewed.
- `RiskEvidenceLedgerReport`: final decision, confidence, and findings.
- `review_risk_evidence_ledger(plan)`: the executable checker.
- `DefectFamilyGate`, `DefectFamilyEvidence`,
  `DefectFamilyGatePlan`, and `review_defect_family_gates(plan)`: helper
  objects for proving recurring model-miss families before the ledger consumes
  the gate status.

## Minimal Example

```python
from flowguard import (
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    ProofArtifactRef,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)

plan = RiskEvidenceLedgerPlan(
    "submit-final-confidence",
    require_code_contracts=True,
    require_proof_artifacts=True,
    rows=(
        RiskEvidenceRow(
            "duplicate_submit",
            model_obligation_id="model:dedupe-submit",
            code_contract_id="api:submit_order",
            proof_evidence_ids=("test:helper-dedupe",),
            family_gate_id="family:submit-routing",
            family_gate_required=True,
            analogous_scan_id="analogous:submit-routing",
            analogous_scan_required=True,
            defect_family_id="defect-family:duplicate-submit",
            defect_family_gate_required=True,
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

## Route Responsibilities

- Model-Test Alignment produces model obligations, optional code contracts,
  optional code-boundary observations, obligation-family parity findings, and
  ordinary test evidence.
- TestMesh produces child-suite evidence status, freshness, skipped/timeout
  visibility, and release/routine boundaries.
- ModelMesh produces parent/child model evidence and reattachment status.
- Model Maturation produces model-upgrade or scoped-claim decisions when later
  route evidence says the model is too coarse, stale, or disconnected.
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

Use the template with:

```powershell
python -m flowguard risk-evidence-ledger-template --output .
python .flowguard/risk_evidence_ledger/run_checks.py
```
