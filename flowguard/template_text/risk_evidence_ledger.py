"""Template text for FlowGuard risk evidence ledger route."""

from __future__ import annotations

RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a final FlowGuard confidence claim is backed by model obligations, public code contracts, recurring defect-family gates, model/test split gates, and current evidence.
Guards against: coarse models hiding untested internal branches, oversized direct model evidence bypassing ModelMesh, slow or broad validation bypassing TestMesh, recurring same-class misses hiding behind local point fixes, tests covering only helper paths, skipped or stale evidence being treated as pass, and background progress being counted as final proof.
Use before editing: Run this before claiming done, release-ready, or fully validated after model/test/code changes.
Run: python .flowguard/risk_evidence_ledger/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    ProofArtifactRef,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)


def correct_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "checkout-final-confidence",
        require_code_contracts=True,
        require_proof_artifacts=True,
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                description="Repeated submit must not create duplicate orders.",
                model_obligation_id="model:dedupe-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:duplicate-submit",),
                defect_family_id="defect-family:duplicate-submit",
                defect_family_gate_required=True,
            ),
            RiskEvidenceRow(
                "invalid_payment",
                description="Invalid payment must stop before storage.",
                model_obligation_id="model:reject-invalid-payment",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("replay:invalid-payment",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:duplicate-submit",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_checkout",
                summary="external API duplicate-submit test passed",
                proof_artifact=ProofArtifactRef(
                    "artifact:test-duplicate-submit",
                    result_status=RISK_PROOF_STATUS_PASSED,
                    exit_code=0,
                    result_path="tmp/test-duplicate-submit.json",
                    artifact_fingerprints={"tmp/test-duplicate-submit.json": "sha256:template"},
                    covered_obligation_ids=("model:dedupe-submit",),
                ),
            ),
            RiskEvidenceProof(
                "replay:invalid-payment",
                proof_kind="replay",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="conformance_replay",
                command="python .flowguard/checkout/run_checks.py",
                summary="representative replay covered invalid payment",
                proof_artifact=ProofArtifactRef(
                    "artifact:replay-invalid-payment",
                    result_status=RISK_PROOF_STATUS_PASSED,
                    exit_code=0,
                    result_path="tmp/replay-invalid-payment.json",
                    artifact_fingerprints={"tmp/replay-invalid-payment.json": "sha256:template"},
                    covered_obligation_ids=("model:reject-invalid-payment",),
                ),
            ),
        ),
    )


def broken_internal_only_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "internal-only-confidence",
        require_code_contracts=True,
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                description="Repeated submit must not create duplicate orders.",
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
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_helpers",
                summary="helper path passed but external submit_order was not exercised",
            ),
        ),
    )


def broken_progress_only_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "progress-only-confidence",
        rows=(
            RiskEvidenceRow(
                "release_regression",
                description="Release regression must finish before publication.",
                model_obligation_id="model:release-regression",
                proof_evidence_ids=("suite:release-regression",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "suite:release-regression",
                result_status=RISK_PROOF_STATUS_PROGRESS_ONLY,
                producer_route="test_mesh_maintenance",
                command="python -m pytest -q",
                summary="suite is still running, so it is liveness only",
            ),
        ),
    )


def broken_missing_defect_family_gate_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "missing-defect-family-gate",
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                description="Repeated same-class submit miss must be promoted before full confidence.",
                model_obligation_id="model:dedupe-submit",
                proof_evidence_ids=("test:duplicate-submit",),
                defect_family_gate_required=True,
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:duplicate-submit",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_checkout",
                summary="observed and same-class test evidence passed, but no defect-family gate was consumed",
            ),
        ),
    )


def broken_missing_model_split_gate_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "missing-model-split-gate",
        rows=(
            RiskEvidenceRow(
                "oversized_checkout_model",
                description="Oversized checkout model must consume a current ModelMesh split before full confidence.",
                model_obligation_id="model:checkout-parent",
                proof_evidence_ids=("model:checkout-direct",),
                model_split_gate_required=True,
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "model:checkout-direct",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_mesh_maintenance",
                command="python .flowguard/checkout/run_checks.py",
                summary="direct model evidence passed, but no current parent/child split gate was consumed",
            ),
        ),
    )


def run_checks():
    return (
        review_risk_evidence_ledger(correct_ledger()),
        review_risk_evidence_ledger(broken_internal_only_ledger()),
        review_risk_evidence_ledger(broken_progress_only_ledger()),
        review_risk_evidence_ledger(broken_missing_defect_family_gate_ledger()),
        review_risk_evidence_ledger(broken_missing_model_split_gate_ledger()),
    )
'''

RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE = '''"""Run the Risk Evidence Ledger template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, internal_only, progress_only, missing_defect_family, missing_model_split = run_checks()
    print(correct.format_text())
    print()
    print(internal_only.format_text(max_findings=5))
    print()
    print(progress_only.format_text(max_findings=5))
    print()
    print(missing_defect_family.format_text(max_findings=5))
    print()
    print(missing_model_split.format_text(max_findings=5))
    expected_blockers = (
        not internal_only.ok
        and internal_only.decision == "internal_path_only_evidence"
        and not progress_only.ok
        and progress_only.decision == "proof_evidence_not_passing"
        and not missing_defect_family.ok
        and missing_defect_family.decision == "missing_defect_family_gate"
        and not missing_model_split.ok
        and missing_model_split.decision == "missing_model_split_gate"
    )
    return 0 if correct.ok and expected_blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE = """# FlowGuard Risk Evidence Ledger Notes

Use this scaffold before final confidence claims.

## What The Ledger Reviews

- each user-facing risk has a FlowGuard model obligation owner;
- each required public behavior has a code contract when the project requires it;
- each recurring or high-risk same-class model miss has a current defect-family gate;
- each required ModelMesh or TestMesh split gate is current before broad parent
  confidence is claimed;
- each risk has current proof evidence from tests, replay, route reports, or manual validation;
- internal-path-only tests, stale evidence, skipped checks, and progress-only background runs are visible;
- scoped-out risks have explicit reasons and cannot be silently counted as fully proven.

The ledger is a final claim boundary. It summarizes evidence produced by
Model-Test Alignment, TestMesh, ModelMesh, StructureMesh, UI Flow Structure,
DevelopmentProcessFlow, conformance replay, and ordinary tests. It does not run
those routes for you.
"""

__all__ = [
    'RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE',
    'RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE',
    'RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE',
]
