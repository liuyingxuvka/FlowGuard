"""FieldLifecycleMesh for the direct current process-optimization replacement.

This inventory separates current owner fields from retired duplicated fields.
Retired rows have an explicit migrated, delegated, or deleted disposition; no
compatibility reader or alternate success path remains.
"""

from __future__ import annotations

from flowguard import (
    FIELD_DISPOSITION_DELEGATED,
    FIELD_DISPOSITION_DELETED,
    FIELD_DISPOSITION_MIGRATED,
    FIELD_IMPACT_EXTERNAL_CONTRACT,
    FIELD_IMPACT_ROUTING,
    FIELD_LIFECYCLE_ACTIVE,
    FIELD_LIFECYCLE_NEW,
    FIELD_LIFECYCLE_REPLACED,
    FIELD_ROLE_ROUTING,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
    review_field_lifecycle,
)


OWNER_LOCATIONS = {
    "process_optimization": "flowguard/development_process_strategy.py",
    "development_process_flow": "flowguard/development_process_flow.py",
    "development_process_simulator": "flowguard/development_process_simulator.py",
    "test_mesh_maintenance": "flowguard/testmesh.py",
    "finding_ledger": "flowguard/summary_report.py",
    "plan_detailing_compiler": "flowguard/plan_detailing.py",
    "model_test_alignment": "flowguard/model_test_alignment.py",
}

CURRENT_OWNER_FIELDS = {
    "process_optimization": (
        "ProcessOptimizationContract.contract_id",
        "ProcessOptimizationContract.terminal_outcome_ids",
        "ProcessOptimizationContract.required_obligation_ids",
        "ProcessOptimizationContract.required_evidence_ids",
        "ProcessOptimizationContract.safety_constraint_ids",
        "ProcessOptimizationContract.protected_side_effect_ids",
        "ProcessOptimizationContract.dependency_authority_ids",
        "ProcessOptimizationContract.execution_owner_ids",
        "ProcessOptimizationContract.revision",
        "ProcessOptimizationCandidate.candidate_id",
        "ProcessOptimizationCandidate.contract_id",
        "ProcessOptimizationCandidate.terminal_outcome_ids",
        "ProcessOptimizationCandidate.covered_obligation_ids",
        "ProcessOptimizationCandidate.evidence_ids",
        "ProcessOptimizationCandidate.safety_constraint_ids",
        "ProcessOptimizationCandidate.protected_side_effect_ids",
        "ProcessOptimizationCandidate.dependency_authority_ids",
        "ProcessOptimizationCandidate.execution_owner_ids",
        "ProcessOptimizationCandidate.step_ids",
        "ProcessOptimizationCandidate.validation_requirement_ids",
        "ProcessOptimizationCandidate.dependency_edges",
        "ProcessOptimizationCandidate.stop_condition_ids",
        "ProcessOptimizationCandidate.diagnostic_boundary",
        "ProcessOptimizationCandidate.execution_mode",
        "ProcessOptimizationCandidate.dependency_isolation_evidence_ids",
        "ProcessOptimizationCandidate.state_isolation_evidence_ids",
        "ProcessOptimizationCandidate.side_effect_isolation_evidence_ids",
        "ProcessOptimizationCandidate.execution_owner_isolation_evidence_ids",
        "ProcessOptimizationCandidate.comparison_basis",
        "ProcessOptimizationCandidate.comparison_evidence_ids",
        "ProcessOptimizationCandidate.applicable",
        "ProcessOptimizationCandidate.current",
        "ProcessRepairGroup.group_id",
        "ProcessRepairGroup.finding_ids",
        "ProcessRepairGroup.relation_evidence_ids",
        "ProcessRepairGroup.root_cause_claim",
        "ProcessRepairGroup.disproof_check_ids",
        "ProcessRepairGroup.affected_obligation_ids",
        "ProcessRepairGroup.owner_evidence_ids",
        "ProcessRepairGroup.repair_action_ids",
        "ProcessRepairGroup.required_revalidation_ids",
        "ProcessRepairGroup.current_revalidation_ids",
        "ProcessRepairGroup.status",
        "ProcessOptimizationDecision.decision_id",
        "ProcessOptimizationDecision.outcome_contract",
        "ProcessOptimizationDecision.activation_reasons",
        "ProcessOptimizationDecision.candidates",
        "ProcessOptimizationDecision.repair_groups",
        "ProcessOptimizationDecision.selected_candidate_id",
        "ProcessOptimizationDecision.input_revision",
        "ProcessOptimizationDecision.current_evidence_ids",
        "ProcessOptimizationDecision.material_evidence_ids",
        "ProcessOptimizationDecision.selection_rationale",
        "ProcessOptimizationReport.status",
        "ProcessOptimizationReport.claim_boundary",
    ),
    "development_process_flow": (
        "DevelopmentProcessPlan.process_optimization_reasons",
        "DevelopmentProcessPlan.required_process_optimization_evidence_ids",
        "ProcessEvidence.revalidation_cost",
        "ProcessEvidence.revalidation_cost_basis",
        "RevalidationRecommendation.revalidation_cost",
        "RevalidationRecommendation.revalidation_cost_basis",
        "RevalidationRecommendation.selection_boundary",
        "DevelopmentProcessFlowReport.process_optimization_status",
        "DevelopmentProcessFlowReport.revalidation_optimality_boundary",
    ),
    "development_process_simulator": (
        "DevelopmentProcessSimulationRequest.process_optimization_reasons",
        "DevelopmentProcessSimulationRequest.process_optimization_evidence_ids",
    ),
    "test_mesh_maintenance": (
        "TestSuiteEvidence.planned_count",
        "TestSuiteEvidence.executed_count",
        "TestSuiteEvidence.failed_count",
        "TestSuiteEvidence.not_run_count",
        "TestSuiteEvidence.diagnostic_campaign_id",
        "TestSuiteEvidence.diagnostic_boundary",
        "TestSuiteEvidence.finding_ids",
        "TestSuiteEvidence.not_run_reason",
    ),
    "finding_ledger": (
        "FlowGuardFindingLedgerEntry.finding_id",
        "FlowGuardFindingLedgerEntry.source_finding_code",
        "FlowGuardFindingLedgerEntry.source_subject_ids",
        "FlowGuardFindingLedgerEntry.evidence_ids",
    ),
    "plan_detailing_compiler": (
        "PlanDetail.process_optimization_reasons",
        "PlanDetail.required_process_optimization_evidence_ids",
    ),
    "model_test_alignment": (
        "ModelTestAlignmentPlan.obligations",
        "ModelTestAlignmentPlan.code_contracts",
        "ModelTestAlignmentPlan.test_evidence",
        "CodeContract.code_contract_id",
        "TestEvidence.evidence_id",
    ),
}

ACTIVE_EXISTING_FIELDS = {
    "ProcessEvidence.revalidation_cost",
    "RevalidationRecommendation.revalidation_cost",
    "RevalidationRecommendation.selection_boundary",
    "DevelopmentProcessFlowReport.revalidation_optimality_boundary",
    "TestSuiteEvidence.planned_count",
    "TestSuiteEvidence.executed_count",
    "TestSuiteEvidence.failed_count",
    "TestSuiteEvidence.not_run_count",
    "TestSuiteEvidence.diagnostic_campaign_id",
    "TestSuiteEvidence.not_run_reason",
    "FlowGuardFindingLedgerEntry.finding_id",
    "FlowGuardFindingLedgerEntry.source_finding_code",
    "FlowGuardFindingLedgerEntry.source_subject_ids",
    "FlowGuardFindingLedgerEntry.evidence_ids",
    "ModelTestAlignmentPlan.obligations",
    "ModelTestAlignmentPlan.code_contracts",
    "ModelTestAlignmentPlan.test_evidence",
    "CodeContract.code_contract_id",
    "TestEvidence.evidence_id",
}


def _field_id(field_name: str) -> str:
    return "field:" + field_name


# old field -> (current replacement, disposition)
# A missing replacement means the duplicated ceremony is deleted outright.
RETIRED_FIELDS = {
    "ProcessOutcomeContract.terminal_outcome_ids": ("ProcessOptimizationContract.terminal_outcome_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessOutcomeContract.required_obligation_ids": ("ProcessOptimizationContract.required_obligation_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessOutcomeContract.required_evidence_ids": ("ProcessOptimizationContract.required_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessOutcomeContract.safety_constraint_ids": ("ProcessOptimizationContract.safety_constraint_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessOutcomeContract.protected_side_effect_ids": ("ProcessOptimizationContract.protected_side_effect_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessOutcomeContract.authority_owner_ids": ("ProcessOptimizationContract.execution_owner_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessOutcomeContract.diagnostic_completeness_required": ("ProcessOptimizationCandidate.diagnostic_boundary", FIELD_DISPOSITION_MIGRATED),
    "ProcessCostVector.effort": (None, FIELD_DISPOSITION_DELETED),
    "ProcessCostVector.elapsed_time": (None, FIELD_DISPOSITION_DELETED),
    "ProcessCostVector.repeated_work": (None, FIELD_DISPOSITION_DELETED),
    "ProcessCostVector.coordination": (None, FIELD_DISPOSITION_DELETED),
    "ProcessCostVector.change_risk": (None, FIELD_DISPOSITION_DELETED),
    "ProcessCostVector.information_value": (None, FIELD_DISPOSITION_DELETED),
    "ProcessCandidate.strategy": ("ProcessOptimizationCandidate.diagnostic_boundary", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.outcome_contract_id": ("ProcessOptimizationCandidate.contract_id", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.covered_obligation_ids": ("ProcessOptimizationCandidate.covered_obligation_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.evidence_ids": ("ProcessOptimizationCandidate.evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.safety_constraint_ids": ("ProcessOptimizationCandidate.safety_constraint_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.protected_side_effect_ids": ("ProcessOptimizationCandidate.protected_side_effect_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.authority_owner_ids": ("ProcessOptimizationCandidate.execution_owner_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.dependency_edges": ("ProcessOptimizationCandidate.dependency_edges", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.campaign_id": ("TestSuiteEvidence.diagnostic_campaign_id", FIELD_DISPOSITION_DELEGATED),
    "ProcessCandidate.repair_batch_ids": ("ProcessOptimizationDecision.repair_groups", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.stop_condition_ids": ("ProcessOptimizationCandidate.stop_condition_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.isolation_evidence_ids": ("ProcessOptimizationCandidate.dependency_isolation_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.applicable": ("ProcessOptimizationCandidate.applicable", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.current": ("ProcessOptimizationCandidate.current", FIELD_DISPOSITION_MIGRATED),
    "ProcessCandidate.decision_revision": ("ProcessOptimizationDecision.input_revision", FIELD_DISPOSITION_MIGRATED),
    "DiagnosticCampaign.planned_item_ids": ("TestSuiteEvidence.planned_count", FIELD_DISPOSITION_DELEGATED),
    "DiagnosticCampaign.executed_item_ids": ("TestSuiteEvidence.executed_count", FIELD_DISPOSITION_DELEGATED),
    "DiagnosticCampaign.failed_item_ids": ("TestSuiteEvidence.failed_count", FIELD_DISPOSITION_DELEGATED),
    "DiagnosticCampaign.not_run_item_ids": ("TestSuiteEvidence.not_run_count", FIELD_DISPOSITION_DELEGATED),
    "DiagnosticCampaign.not_run_reasons": ("TestSuiteEvidence.not_run_reason", FIELD_DISPOSITION_DELEGATED),
    "DiagnosticCampaign.enumeration_status": ("TestSuiteEvidence.diagnostic_boundary", FIELD_DISPOSITION_DELEGATED),
    "DiagnosticCampaign.early_stop_reason": ("TestSuiteEvidence.not_run_reason", FIELD_DISPOSITION_DELEGATED),
    "FailureObservation.source_finding_id": ("FlowGuardFindingLedgerEntry.finding_id", FIELD_DISPOSITION_DELEGATED),
    "FailureObservation.evidence_ids": ("FlowGuardFindingLedgerEntry.evidence_ids", FIELD_DISPOSITION_DELEGATED),
    "FailureObservation.subject_ids": ("FlowGuardFindingLedgerEntry.source_subject_ids", FIELD_DISPOSITION_DELEGATED),
    "FailureCluster.observation_ids": ("ProcessRepairGroup.finding_ids", FIELD_DISPOSITION_MIGRATED),
    "FailureCluster.relation_evidence_ids": ("ProcessRepairGroup.relation_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "RootCauseHypothesis.cluster_ids": ("ProcessRepairGroup.finding_ids", FIELD_DISPOSITION_MIGRATED),
    "RootCauseHypothesis.disproof_check_ids": ("ProcessRepairGroup.disproof_check_ids", FIELD_DISPOSITION_MIGRATED),
    "RepairBatch.cluster_ids": ("ProcessRepairGroup.finding_ids", FIELD_DISPOSITION_MIGRATED),
    "RepairBatch.hypothesis_ids": ("ProcessRepairGroup.root_cause_claim", FIELD_DISPOSITION_MIGRATED),
    "RepairBatch.artifact_ids": ("ProcessRepairGroup.affected_obligation_ids", FIELD_DISPOSITION_MIGRATED),
    "RepairBatch.owner_ids": ("ProcessRepairGroup.owner_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "RepairBatch.required_revalidation_ids": ("ProcessRepairGroup.required_revalidation_ids", FIELD_DISPOSITION_MIGRATED),
    "RepairBatch.current_revalidation_ids": ("ProcessRepairGroup.current_revalidation_ids", FIELD_DISPOSITION_MIGRATED),
    "StrategyReevaluation.material_observation_ids": ("ProcessOptimizationDecision.material_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "StrategyReevaluation.completed_batch_ids": ("ProcessOptimizationDecision.repair_groups", FIELD_DISPOSITION_MIGRATED),
    "StrategyReevaluation.input_revision": ("ProcessOptimizationDecision.input_revision", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessStrategyPlan.rollout_stage": (None, FIELD_DISPOSITION_DELETED),
    "DevelopmentProcessStrategyPlan.selected_candidate_id": ("ProcessOptimizationDecision.selected_candidate_id", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessStrategyPlan.input_revision": ("ProcessOptimizationDecision.input_revision", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessStrategyPlan.candidate_inventory_revision": ("ProcessOptimizationDecision.current_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessStrategyPlan.candidate_set_complete": ("ProcessOptimizationCandidate.comparison_basis", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessStrategyPlan.finite_boundary_id": ("ProcessOptimizationCandidate.comparison_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessStrategyPlan.objective_order": (None, FIELD_DISPOSITION_DELETED),
    "ProcessStrategyReport.optimality_claim": ("ProcessOptimizationReport.claim_boundary", FIELD_DISPOSITION_MIGRATED),
    "ProcessStrategyReport.claim_boundary": ("ProcessOptimizationReport.claim_boundary", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessPlan.strategy_selection_required": ("DevelopmentProcessPlan.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessPlan.required_strategy_evidence_ids": ("DevelopmentProcessPlan.required_process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessPlan.strategy_rollout_stage": (None, FIELD_DISPOSITION_DELETED),
    "DevelopmentProcessPlan.strategy_enforcement_required": (None, FIELD_DISPOSITION_DELETED),
    "RevalidationRecommendation.estimated_cost": ("RevalidationRecommendation.revalidation_cost", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessSimulationRequest.process_optimization_requested": ("DevelopmentProcessSimulationRequest.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessSimulationRequest.multiple_viable_sequences": ("DevelopmentProcessSimulationRequest.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessSimulationRequest.repeated_work_risk": ("DevelopmentProcessSimulationRequest.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessSimulationRequest.diagnostic_campaign": ("DevelopmentProcessSimulationRequest.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessSimulationRequest.adaptive_strategy_required": ("DevelopmentProcessSimulationRequest.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "DevelopmentProcessSimulationRequest.strategy_selection_evidence_ids": ("DevelopmentProcessSimulationRequest.process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "TestSuiteEvidence.execution_policy": ("TestSuiteEvidence.diagnostic_boundary", FIELD_DISPOSITION_MIGRATED),
    "TestSuiteEvidence.enumeration_status": ("TestSuiteEvidence.diagnostic_boundary", FIELD_DISPOSITION_MIGRATED),
    "TestSuiteEvidence.early_stop_reason": ("TestSuiteEvidence.not_run_reason", FIELD_DISPOSITION_MIGRATED),
    "TestSuiteEvidence.failure_observation_ids": ("TestSuiteEvidence.finding_ids", FIELD_DISPOSITION_MIGRATED),
    "TestSuiteEvidence.failure_cluster_ids": (None, FIELD_DISPOSITION_DELETED),
    "PlanDetailStep.strategy_selection_id": ("PlanDetail.required_process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "PlanDetailStep.selected_process_strategy": ("PlanDetail.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "PlanDetailStep.strategy_decision_evidence_ids": ("PlanDetail.required_process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "PlanDetailStep.diagnostic_campaign_id": (None, FIELD_DISPOSITION_DELETED),
    "PlanDetailStep.repair_batch_ids": (None, FIELD_DISPOSITION_DELETED),
    "PlanDetailStep.strategy_reevaluation_evidence_ids": ("PlanDetail.required_process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "PlanDetailValidation.strategy_selection_id": ("PlanDetail.required_process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "PlanDetailValidation.selected_process_strategy": ("PlanDetail.process_optimization_reasons", FIELD_DISPOSITION_MIGRATED),
    "PlanDetailValidation.diagnostic_campaign_id": (None, FIELD_DISPOSITION_DELETED),
    "PlanDetailValidation.repair_batch_ids": (None, FIELD_DISPOSITION_DELETED),
    "PlanDetailValidation.strategy_reevaluation_evidence_ids": ("PlanDetail.required_process_optimization_evidence_ids", FIELD_DISPOSITION_MIGRATED),
    "ProcessStrategyAlignmentBinding.strategy_selection_id": ("ModelTestAlignmentPlan.obligations", FIELD_DISPOSITION_DELEGATED),
    "ProcessStrategyAlignmentBinding.failure_cluster_id": ("ModelTestAlignmentPlan.obligations", FIELD_DISPOSITION_DELEGATED),
    "ProcessStrategyAlignmentBinding.repair_batch_id": ("ModelTestAlignmentPlan.obligations", FIELD_DISPOSITION_DELEGATED),
    "ProcessStrategyAlignmentBinding.model_obligation_ids": ("ModelTestAlignmentPlan.obligations", FIELD_DISPOSITION_DELEGATED),
    "ProcessStrategyAlignmentBinding.owner_code_contract_ids": ("ModelTestAlignmentPlan.code_contracts", FIELD_DISPOSITION_DELEGATED),
    "ProcessStrategyAlignmentBinding.test_evidence_ids": ("ModelTestAlignmentPlan.test_evidence", FIELD_DISPOSITION_DELEGATED),
    "ProcessStrategyAlignmentBinding.current": ("TestEvidence.evidence_id", FIELD_DISPOSITION_DELEGATED),
}


def _projection(field_name: str, owner: str) -> FieldProjection:
    return FieldProjection(
        f"projection:{field_name}",
        _field_id(field_name),
        model_obligation_id=f"obligation:{field_name}",
        code_contract_id=f"contract:{owner}",
        external_outputs=(field_name,),
        state_writes=(field_name,),
        evidence_refs=(
            "gate:development-process-strategy-selection",
            "test:process-optimization-focused",
        ),
        rationale="Current-only process-optimization field ownership and replacement evidence.",
    )


def _owner_for_current(field_name: str) -> str:
    for owner, fields in CURRENT_OWNER_FIELDS.items():
        if field_name in fields:
            return owner
    raise KeyError(field_name)


def _retired_owner(field_name: str) -> str:
    prefix = field_name.split(".", 1)[0]
    if prefix in {"ProcessOutcomeContract", "ProcessCostVector", "ProcessCandidate", "DiagnosticCampaign", "FailureObservation", "FailureCluster", "RootCauseHypothesis", "RepairBatch", "StrategyReevaluation", "DevelopmentProcessStrategyPlan", "ProcessStrategyReport"}:
        return "process_optimization"
    if prefix in {"DevelopmentProcessPlan", "RevalidationRecommendation", "ProcessAction", "ValidationRequirement"}:
        return "development_process_flow"
    if prefix == "DevelopmentProcessSimulationRequest":
        return "development_process_simulator"
    if prefix == "TestSuiteEvidence":
        return "test_mesh_maintenance"
    if prefix in {"PlanDetailStep", "PlanDetailValidation"}:
        return "plan_detailing_compiler"
    return "model_test_alignment"


def development_process_strategy_field_lifecycle_plan() -> FieldLifecyclePlan:
    rows = []
    for owner, field_names in CURRENT_OWNER_FIELDS.items():
        for field_name in field_names:
            rows.append(
                FieldLifecycleRow(
                    _field_id(field_name),
                    field_name=field_name,
                    locations=(OWNER_LOCATIONS[owner],),
                    role=FIELD_ROLE_ROUTING,
                    lifecycle=(
                        FIELD_LIFECYCLE_ACTIVE
                        if field_name in ACTIVE_EXISTING_FIELDS
                        else FIELD_LIFECYCLE_NEW
                    ),
                    behavior_impacts=(FIELD_IMPACT_ROUTING, FIELD_IMPACT_EXTERNAL_CONTRACT),
                    reader_ids=(owner, "development_process_flow"),
                    writer_ids=(owner,),
                    projection=_projection(field_name, owner),
                    metadata={"compatibility_alias": "none"},
                )
            )

    for field_name, (replacement, disposition) in RETIRED_FIELDS.items():
        owner = _retired_owner(field_name)
        rows.append(
            FieldLifecycleRow(
                _field_id(field_name),
                field_name=field_name,
                locations=(OWNER_LOCATIONS[owner],),
                role=FIELD_ROLE_ROUTING,
                lifecycle=FIELD_LIFECYCLE_REPLACED,
                behavior_impacts=(FIELD_IMPACT_ROUTING, FIELD_IMPACT_EXTERNAL_CONTRACT),
                reader_ids=(owner,),
                writer_ids=(owner,),
                replacement_field_id=_field_id(replacement) if replacement else "",
                disposition=disposition,
                disposition_evidence_refs=(
                    "openspec:simplify-development-process-optimization",
                    "test:process-optimization-zero-residuals",
                ),
                projection=_projection(field_name, owner),
                required=False,
                current=False,
                metadata={
                    "replacement": replacement or "deleted_without_alternate_success_path",
                    "compatibility_alias": "none",
                },
            )
        )

    field_ids = tuple(row.field_id for row in rows)
    return FieldLifecyclePlan(
        "development-process-optimization-fields:v2",
        discovered_field_ids=field_ids,
        fields=tuple(rows),
        claim_scope="full",
        allow_scoped_confidence=False,
        notes="Current fields have one owner; every retired duplicated field is migrated, delegated, or deleted with no compatibility route.",
    )


def review_development_process_strategy_fields():
    return review_field_lifecycle(development_process_strategy_field_lifecycle_plan())


__all__ = [
    "ACTIVE_EXISTING_FIELDS",
    "CURRENT_OWNER_FIELDS",
    "OWNER_LOCATIONS",
    "RETIRED_FIELDS",
    "development_process_strategy_field_lifecycle_plan",
    "review_development_process_strategy_fields",
]
