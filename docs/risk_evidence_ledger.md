# Risk Evidence Ledger

Risk Evidence Ledger is the final confidence boundary for FlowGuard work. It is
for the exact gap that ordinary testing often leaves behind: the model says a
risk was represented, tests are green, but no one checked whether the green
evidence actually covers the user-facing risk, the public code contract, and the
current route evidence.

The ledger does not make FlowGuard models deeper. It connects the coarse model
to ordinary evidence:

```text
user risk -> model obligation -> public code contract -> current proof evidence
```

If any link is missing, stale, skipped, progress-only, or internal-path-only, the
report downgrades the final claim instead of letting the agent say "fully
validated."

## Public API

- `RiskEvidenceRow`: one user-meaningful risk and the model/code/evidence IDs
  that should prove it.
- `RiskEvidenceProof`: one test, replay, route report, or manual validation item.
- `RiskEvidenceLedgerPlan`: the rows and evidence being reviewed.
- `RiskEvidenceLedgerReport`: final decision, confidence, and findings.
- `review_risk_evidence_ledger(plan)`: the executable checker.

## Minimal Example

```python
from flowguard import (
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)

plan = RiskEvidenceLedgerPlan(
    "submit-final-confidence",
    require_code_contracts=True,
    rows=(
        RiskEvidenceRow(
            "duplicate_submit",
            model_obligation_id="model:dedupe-submit",
            code_contract_id="api:submit_order",
            proof_evidence_ids=("test:helper-dedupe",),
        ),
    ),
    proof_evidence=(
        RiskEvidenceProof(
            "test:helper-dedupe",
            result_status=RISK_PROOF_STATUS_PASSED,
            assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH,
        ),
    ),
)

report = review_risk_evidence_ledger(plan)
print(report.format_text())
```

This report blocks full confidence with `internal_path_only_evidence`: the test
passed, but it proved a helper path, not the public submit behavior.

## Decisions

- `risk_evidence_full_confidence`: every in-scope required risk has a model
  obligation and current passing evidence at the expected boundary.
- `risk_evidence_scoped_confidence`: required in-scope risks pass, but an
  explicitly scoped-out row remains visible.
- blocker findings such as `missing_model_obligation`,
  `missing_code_contract`, `missing_proof_evidence`,
  `missing_current_passing_proof`, `internal_path_only_evidence`,
  `stale_proof_evidence`, `route_gap_visible`, or
  `proof_evidence_not_passing`: do not claim full confidence.

## Route Responsibilities

- Model-Test Alignment produces model obligations, optional code contracts, and
  ordinary test evidence.
- TestMesh produces child-suite evidence status, freshness, skipped/timeout
  visibility, and release/routine boundaries.
- ModelMesh produces parent/child model evidence and reattachment status.
- StructureMesh and UI Flow Structure produce public-entrypoint or journey
  evidence when structure or UI claims are involved.
- DevelopmentProcessFlow checks the ledger before done, archive, publish, or
  release claims.
- Model-Miss Review updates the ledger when runtime evidence proves that earlier
  model/test evidence was too narrow.

Use the template with:

```powershell
python -m flowguard risk-evidence-ledger-template --output .
python .flowguard/risk_evidence_ledger/run_checks.py
```
