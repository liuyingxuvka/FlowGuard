"""Run FlowGuard checks for maintenance obligation memory."""

from __future__ import annotations

from flowguard import (
    MAINTENANCE_ARTIFACT_CODE,
    MAINTENANCE_ROUTE_STRUCTURE_MESH,
    OBLIGATION_STATUS_RESOLVED,
    MaintenanceChangedArtifact,
    MaintenanceEvidence,
    MaintenanceObligation,
    MaintenanceScanPlan,
    RISK_GATE_MAINTENANCE_OBLIGATION,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_maintenance_scan,
    review_risk_evidence_ledger,
    run_exact_sequence,
)
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "anchored_obligation_recorded",
    "unanchored_observation_recorded",
    "anchor_touched",
    "owner_evidence_recorded",
    "scoped_claim_only",
    "full_claim_accepted",
)


def run_workflow_suite() -> bool:
    exact = run_exact_sequence(
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
    )
    exact_ok = (
        exact.model_report.ok
        and len(exact.final_states) == 1
        and exact.final_states[0].broad_claim == "full_accepted"
    )
    print(
        "correct_maintenance_obligation_memory: "
        + ("observed=OK expected=OK match=yes exact=yes" if exact_ok else "observed=VIOLATION expected=OK match=no")
    )
    cases = [FormalWorkflowCase(broken.name, broken, False) for broken in model.build_broken_workflows()]
    report = run_formal_workflow_suite(
        "maintenance_obligation_memory",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="maintenance_obligation_not_remembered",
    )
    return exact_ok and report.ok


def helper_case(name: str, ok: bool, text: str) -> bool:
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(text)
    print()
    return ok


def run_helper_cases() -> bool:
    open_obligation = MaintenanceObligation(
        "structure:checkout",
        owner_route=MAINTENANCE_ROUTE_STRUCTURE_MESH,
        reason_code="large_module",
        anchor_paths=("flowguard/checkout.py",),
    )
    reopened = review_maintenance_scan(
        MaintenanceScanPlan(
            "self-model-reopen",
            changed_artifacts=(
                MaintenanceChangedArtifact(
                    "checkout-code",
                    MAINTENANCE_ARTIFACT_CODE,
                    path="src/flowguard/checkout.py",
                ),
            ),
            prior_obligations=(open_obligation,),
        )
    )

    blocked_ledger = review_risk_evidence_ledger(
        RiskEvidenceLedgerPlan(
            "self-model-blocked-ledger",
            rows=(
                RiskEvidenceRow(
                    "risk:structure",
                    model_obligation_id="model:structure",
                    code_contract_id="code:structure",
                    proof_evidence_ids=("proof:unit",),
                    gates=(RiskEvidenceGate(RISK_GATE_MAINTENANCE_OBLIGATION, "structure:checkout"),),
                ),
            ),
            proof_evidence=(RiskEvidenceProof("proof:unit", result_status="passed"),),
            maintenance_obligations=(open_obligation,),
        )
    )

    resolved_obligation = MaintenanceObligation(
        "structure:checkout",
        owner_route=MAINTENANCE_ROUTE_STRUCTURE_MESH,
        reason_code="large_module",
        status=OBLIGATION_STATUS_RESOLVED,
        evidence_ids=("structuremesh:passed",),
    )
    clear_ledger = review_risk_evidence_ledger(
        RiskEvidenceLedgerPlan(
            "self-model-clear-ledger",
            rows=(
                RiskEvidenceRow(
                    "risk:structure",
                    model_obligation_id="model:structure",
                    code_contract_id="code:structure",
                    proof_evidence_ids=("proof:unit",),
                    gates=(RiskEvidenceGate(RISK_GATE_MAINTENANCE_OBLIGATION, "structure:checkout"),),
                ),
            ),
            proof_evidence=(RiskEvidenceProof("proof:unit", result_status="passed"),),
            maintenance_obligations=(resolved_obligation,),
        )
    )

    resolved_scan = review_maintenance_scan(
        MaintenanceScanPlan(
            "self-model-resolved-scan",
            changed_artifacts=(
                MaintenanceChangedArtifact(
                    "checkout-code",
                    MAINTENANCE_ARTIFACT_CODE,
                    path="src/flowguard/checkout.py",
                ),
            ),
            prior_obligations=(open_obligation,),
            evidence=(
                MaintenanceEvidence(
                    "structuremesh:passed",
                    MAINTENANCE_ROUTE_STRUCTURE_MESH,
                    status="passed",
                    current=True,
                ),
            ),
        )
    )

    return all(
        (
            helper_case(
                "anchored_obligation_reopens_maintenance_scan",
                reopened.reopened_obligation_ids == ("structure:checkout",)
                and bool(reopened.unresolved_required_action_ids),
                reopened.format_text(),
            ),
            helper_case(
                "open_obligation_blocks_risk_ledger",
                not blocked_ledger.ok and blocked_ledger.decision == "open_maintenance_obligation",
                blocked_ledger.format_text(),
            ),
            helper_case(
                "resolved_obligation_allows_risk_ledger",
                clear_ledger.ok and clear_ledger.decision == "risk_evidence_full_confidence",
                clear_ledger.format_text(),
            ),
            helper_case(
                "owner_evidence_resolves_reopened_scan",
                resolved_scan.ok and not resolved_scan.unresolved_required_action_ids,
                resolved_scan.format_text(),
            ),
        )
    )


def main() -> int:
    workflow_checks = run_workflow_suite()
    helper_checks = run_helper_cases()
    return 0 if workflow_checks and helper_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
