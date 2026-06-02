"""Run FlowGuard checks for maintenance obligation memory."""

from __future__ import annotations

from flowguard import (
    Explorer,
    MAINTENANCE_ARTIFACT_CODE,
    MAINTENANCE_ROUTE_STRUCTURE_MESH,
    OBLIGATION_STATUS_RESOLVED,
    MaintenanceChangedArtifact,
    MaintenanceEvidence,
    MaintenanceObligation,
    MaintenanceScanPlan,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_maintenance_scan,
    review_risk_evidence_ledger,
)
import model


def run_workflow(name: str, workflow, *, expect_ok: bool) -> bool:
    report = Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "anchored_obligation_recorded",
            "unanchored_observation_recorded",
            "anchor_touched",
            "owner_evidence_recorded",
            "scoped_claim_only",
            "full_claim_accepted",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


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
                    maintenance_obligations_required=True,
                    maintenance_obligation_ids=("structure:checkout",),
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
                    maintenance_obligations_required=True,
                    maintenance_obligation_ids=("structure:checkout",),
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
    workflow_checks = [
        run_workflow("correct_maintenance_obligation_memory", model.build_correct_workflow(), expect_ok=True)
    ]
    for broken in model.build_broken_workflows():
        workflow_checks.append(run_workflow(broken.name, broken, expect_ok=False))
    helper_checks = run_helper_cases()
    return 0 if all(workflow_checks) and helper_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
