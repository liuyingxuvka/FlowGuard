"""Template text for FlowGuard risk evidence ledger route."""

from __future__ import annotations

RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a final FlowGuard confidence claim is backed by model obligations, public code contracts, UI real-surface/functional-capability/functional-chain/done-claim gates, payload gates, topology/business-path gates, recurring defect-family gates, model/test split gates, and current evidence.
Guards against: coarse models hiding untested internal branches, skipped UI inventory, functional capability coverage, functional-chain, source-baseline interaction, click-through, or file/work-package payload evidence for real surfaces, business-path-sensitive claims proved by the wrong route, oversized direct model evidence bypassing ModelMesh, slow or broad validation bypassing TestMesh, recurring same-class misses hiding behind local point fixes, tests covering only helper paths, skipped or stale evidence being treated as pass, and background progress being counted as final proof.
Use before editing: Run this before claiming done, release-ready, or fully validated after model/test/code changes.
Run: python .flowguard/risk_evidence_ledger/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    OBLIGATION_STATUS_RESOLVED,
    RISK_GATE_ARTIFACT_PAYLOAD,
    RISK_GATE_CONTRACT_COVERAGE_SHARD,
    RISK_GATE_DEFECT_FAMILY,
    RISK_GATE_MAINTENANCE_OBLIGATION,
    RISK_GATE_MODEL_CARTESIAN_COVERAGE,
    RISK_GATE_TOPOLOGY_HAZARD,
    RISK_GATE_PARENT_CONSUMED_CHILD_COVERAGE,
    RISK_GATE_UI_SOURCE_BASELINE_INTERACTION,
    RISK_GATE_MODEL_SPLIT,
    RISK_GATE_UI_DONE_CLAIM,
    RISK_GATE_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    RISK_GATE_UI_FUNCTIONAL_CHAIN,
    RISK_GATE_UI_IMPLEMENTATION,
    RISK_GATE_UI_REAL_SURFACE,
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    MaintenanceObligation,
    ProofArtifactRef,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)


def correct_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "checkout-final-confidence",
        require_proof_artifacts=True,
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                model_obligation_id="model:dedupe-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:duplicate-submit",),
                gates=(
                    RiskEvidenceGate(RISK_GATE_DEFECT_FAMILY, "defect-family:duplicate-submit"),
                    RiskEvidenceGate(RISK_GATE_MODEL_CARTESIAN_COVERAGE, "contract_coverage:checkout-child"),
                    RiskEvidenceGate(RISK_GATE_CONTRACT_COVERAGE_SHARD, "contract_shard:checkout-child:duplicate-submit"),
                    RiskEvidenceGate(RISK_GATE_PARENT_CONSUMED_CHILD_COVERAGE, "contract_coverage:checkout-parent"),
                    RiskEvidenceGate(RISK_GATE_UI_IMPLEMENTATION, "ui:duplicate-submit-clickthrough"),
                    RiskEvidenceGate(RISK_GATE_UI_REAL_SURFACE, "ui:checkout-observed-inventory"),
                    RiskEvidenceGate(RISK_GATE_UI_FUNCTIONAL_CAPABILITY_COVERAGE, "ui:checkout-capability-coverage"),
                    RiskEvidenceGate(RISK_GATE_UI_FUNCTIONAL_CHAIN, "ui:duplicate-submit-chain"),
                    RiskEvidenceGate(RISK_GATE_UI_DONE_CLAIM, "ui:checkout-done-claim"),
                    RiskEvidenceGate(RISK_GATE_UI_SOURCE_BASELINE_INTERACTION, "ui:source-baseline-interactions"),
                    RiskEvidenceGate(RISK_GATE_ARTIFACT_PAYLOAD, "payload:checkout-export-pack"),
                    RiskEvidenceGate(RISK_GATE_TOPOLOGY_HAZARD, "topology:submit-order-business-path"),
                    RiskEvidenceGate(RISK_GATE_MAINTENANCE_OBLIGATION, "structure:submit-routing"),
                ),
            ),
            RiskEvidenceRow(
                "invalid_payment",
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


def broken_internal_only_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "internal-only-confidence",
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
                model_obligation_id="model:release-regression",
                code_contract_id="suite:release-regression",
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
                model_obligation_id="model:dedupe-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:duplicate-submit",),
                gates=(RiskEvidenceGate(RISK_GATE_DEFECT_FAMILY),),
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
                model_obligation_id="model:checkout-parent",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("model:checkout-direct",),
                gates=(RiskEvidenceGate(RISK_GATE_MODEL_SPLIT),),
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


def broken_missing_cartesian_coverage_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "missing-cartesian-coverage-gate",
        rows=(
            RiskEvidenceRow(
                "contract_matrix",
                model_obligation_id="model:request-boundary",
                code_contract_id="api:parse_request",
                proof_evidence_ids=("test:request-boundary",),
                gates=(
                    RiskEvidenceGate(RISK_GATE_MODEL_CARTESIAN_COVERAGE),
                    RiskEvidenceGate(RISK_GATE_CONTRACT_COVERAGE_SHARD),
                    RiskEvidenceGate(RISK_GATE_PARENT_CONSUMED_CHILD_COVERAGE),
                ),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:request-boundary",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_request_boundary",
                summary="case tests passed, but no model coverage receipt, shard, or parent-consumed-child gate was supplied",
            ),
        ),
    )


def broken_missing_artifact_payload_gate_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "missing-artifact-payload-gate",
        rows=(
            RiskEvidenceRow(
                "checkout_export",
                model_obligation_id="model:export-checkout",
                code_contract_id="api:export_checkout",
                proof_evidence_ids=("test:checkout-export",),
                gates=(RiskEvidenceGate(RISK_GATE_ARTIFACT_PAYLOAD),),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:checkout-export",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_checkout_export",
                summary="unit test passed, but no real-surface payload proof gate was consumed",
            ),
        ),
    )


def broken_open_maintenance_obligation_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "open-maintenance-obligation",
        rows=(
            RiskEvidenceRow(
                "structure_parity",
                model_obligation_id="model:structure-parity",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:structure-parity",),
                gates=(RiskEvidenceGate(RISK_GATE_MAINTENANCE_OBLIGATION, "structure:checkout"),),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:structure-parity",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="structure_mesh_maintenance",
                command="python .flowguard/structure_mesh/run_checks.py",
                summary="test passed, but the remembered StructureMesh obligation is still open",
            ),
        ),
        maintenance_obligations=(
            MaintenanceObligation(
                "structure:checkout",
                owner_route="structure_mesh_maintenance",
                reason_code="large_module",
                anchor_paths=("checkout.py",),
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
        review_risk_evidence_ledger(broken_missing_cartesian_coverage_ledger()),
        review_risk_evidence_ledger(broken_missing_artifact_payload_gate_ledger()),
        review_risk_evidence_ledger(broken_open_maintenance_obligation_ledger()),
    )
'''

RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE = '''"""Run the Risk Evidence Ledger template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    (
        correct,
        internal_only,
        progress_only,
        missing_defect_family,
        missing_model_split,
        missing_cartesian_coverage,
        missing_artifact_payload,
        open_obligation,
    ) = run_checks()
    print(correct.format_text())
    print()
    print(internal_only.format_text(max_findings=5))
    print()
    print(progress_only.format_text(max_findings=5))
    print()
    print(missing_defect_family.format_text(max_findings=5))
    print()
    print(missing_model_split.format_text(max_findings=5))
    print()
    print(missing_cartesian_coverage.format_text(max_findings=5))
    print()
    print(missing_artifact_payload.format_text(max_findings=5))
    print()
    print(open_obligation.format_text(max_findings=5))
    expected_blockers = (
        not internal_only.ok
        and internal_only.decision == "internal_path_only_evidence"
        and not progress_only.ok
        and progress_only.decision == "proof_evidence_not_passing"
        and not missing_defect_family.ok
        and missing_defect_family.decision == "missing_defect_family_gate"
        and not missing_model_split.ok
        and missing_model_split.decision == "missing_model_split_gate"
        and not missing_cartesian_coverage.ok
        and missing_cartesian_coverage.decision == "missing_model_cartesian_coverage_gate"
        and not missing_artifact_payload.ok
        and missing_artifact_payload.decision == "missing_artifact_payload_gate"
        and not open_obligation.ok
        and open_obligation.decision == "open_maintenance_obligation"
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
- each model-scoped Cartesian coverage claim has current coverage receipt,
  shard, and parent-consumed-child gates when the final claim depends on it;
- each required ModelMesh or TestMesh split gate is current before broad parent
  confidence is claimed;
- each remembered maintenance obligation is resolved by owner-route evidence,
  explicitly scoped, or still blocks full confidence;
- UI release claims can require separate real-surface, functional capability
  coverage, functional-chain, implementation, source-baseline, and done-claim
  gates;
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
