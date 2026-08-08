"""Sole private owner of development-process validation and selection.

Public records and the entrypoint stay in ``development_process_strategy``.
"""

from __future__ import annotations

from collections import Counter
import math
from typing import Sequence

from .development_process_strategy import (
    _ACTIVATION_REASONS,
    _COMPARISON_BASES,
    _COST_COMPONENT_IDS,
    _DIAGNOSTIC_BOUNDARIES,
    _EVIDENCE_GAP_SUFFIXES,
    _EXECUTION_MODES,
    _REPAIR_STATUSES,
    ProcessOptimizationCandidate,
    ProcessOptimizationContract,
    ProcessOptimizationDecision,
    ProcessOptimizationReport,
    ProcessRepairGroup,
)


def _duplicates(values: Sequence[object]) -> tuple[object, ...]:
    return tuple(value for value, count in Counter(values).items() if count > 1)


def _has_cycle(nodes: Sequence[str], edges: Sequence[tuple[str, str]]) -> bool:
    outgoing: dict[str, list[str]] = {node: [] for node in nodes}
    indegree: dict[str, int] = {node: 0 for node in nodes}
    for source, target in edges:
        if source not in outgoing or target not in outgoing:
            continue
        outgoing[source].append(target)
        indegree[target] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for target in outgoing[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return visited != len(outgoing)


def _step_metadata_findings(
    candidate: ProcessOptimizationCandidate,
    prefix: str,
) -> list[str]:
    findings: list[str] = []
    steps = set(candidate.step_ids)
    relations = (
        ("artifact_read", candidate.step_artifact_reads, None),
        ("artifact_write", candidate.step_artifact_writes, None),
        ("artifact_invalidation", candidate.step_artifact_invalidations, None),
        ("validation", candidate.step_validation_ids, set(candidate.validation_requirement_ids)),
        ("execution_owner", candidate.step_execution_owner_ids, set(candidate.execution_owner_ids)),
        ("side_effect", candidate.step_side_effect_ids, set(candidate.protected_side_effect_ids)),
        ("effort_evidence", candidate.step_effort_evidence_ids, None),
    )
    for label, rows, allowed_targets in relations:
        if _duplicates(rows) or any(
            not step or step not in steps or not target
            or (allowed_targets is not None and target not in allowed_targets)
            for step, target in rows
        ):
            findings.append(prefix + f"step_{label}_binding_invalid")
    owner_steps = tuple(step for step, _ in candidate.step_execution_owner_ids)
    if set(owner_steps) != steps or _duplicates(owner_steps):
        findings.append(prefix + "step_execution_owner_incomplete")
    cost_steps = tuple(step for step, _ in candidate.step_effort_costs)
    if _duplicates(cost_steps) or any(
        step not in steps or not math.isfinite(cost) or cost < 0
        for step, cost in candidate.step_effort_costs
    ):
        findings.append(prefix + "step_effort_cost_invalid")
    if cost_steps and set(cost_steps) != steps:
        findings.append(prefix + "comparable_step_cost_incomplete")
    if candidate.comparison_basis == "measured":
        evidence_steps = tuple(step for step, _ in candidate.step_effort_evidence_ids)
        if set(cost_steps) != steps:
            findings.append(prefix + "measured_step_cost_missing")
        if set(evidence_steps) != steps or _duplicates(evidence_steps):
            findings.append(prefix + "measured_step_cost_evidence_missing")
    return findings


def _candidate_cost_vector(
    candidate: ProcessOptimizationCandidate,
) -> tuple[float | None, ...]:
    positions = {step: index for index, step in enumerate(candidate.step_ids)}
    writes: dict[str, list[int]] = {}
    invalidations: dict[str, list[int]] = {}
    for step, artifact in candidate.step_artifact_writes:
        writes.setdefault(artifact, []).append(positions[step])
    for step, artifact in candidate.step_artifact_invalidations:
        invalidations.setdefault(artifact, []).append(positions[step])
    invalidated = sum(
        any(invalidation > write for invalidation in invalidations.get(artifact, ()))
        for artifact, write_positions in writes.items()
        for write in write_positions
    )
    repeated_writes = sum(max(0, len(rows) - 1) for rows in writes.values())
    validations = tuple(validation for _, validation in candidate.step_validation_ids)
    repeated_validations = len(validations) - len(set(validations))
    owners = dict(candidate.step_execution_owner_ids)
    coordination = sum(
        owners[left] != owners[right]
        for left, right in zip(candidate.step_ids, candidate.step_ids[1:])
    )
    side_effects = len(candidate.step_side_effect_ids)
    costs = dict(candidate.step_effort_costs)
    effort = (
        sum(costs[step] for step in candidate.step_ids)
        if set(costs) == set(candidate.step_ids)
        else None
    )
    values = (
        invalidated, repeated_writes, repeated_validations,
        coordination, side_effects, effort,
    )
    return tuple(None if value is None else float(value) for value in values)


def _cost_relation(
    left: tuple[float | None, ...],
    right: tuple[float | None, ...],
) -> str:
    if any(value is None for value in (*left, *right)):
        return "incomparable"
    left_values = tuple(float(value) for value in left if value is not None)
    right_values = tuple(float(value) for value in right if value is not None)
    left_better = any(a < b for a, b in zip(left_values, right_values))
    right_better = any(a > b for a, b in zip(left_values, right_values))
    if left_better and not right_better:
        return "dominates"
    if right_better and not left_better:
        return "dominated"
    if not left_better and not right_better:
        return "equal"
    return "tradeoff"


def _derived_selection_rationale(cost_row: tuple[object, ...] | None) -> str:
    if cost_row is None or len(cost_row) != len(_COST_COMPONENT_IDS) + 1:
        return ""
    values = ", ".join(
        f"{name}={float(value):g}"
        for name, value in zip(_COST_COMPONENT_IDS, cost_row[1:])
        if value is not None
    )
    return (
        f"model-derived Pareto-dominating process candidate {cost_row[0]} "
        f"within the declared comparable dimensions: {values}"
    )


def _candidate_findings(
    candidate: ProcessOptimizationCandidate,
    contract: ProcessOptimizationContract,
) -> list[str]:
    prefix = f"candidate:{candidate.candidate_id or '(missing)'}:"
    findings: list[str] = []
    if not candidate.candidate_id:
        findings.append(prefix + "identity_invalid")
    if candidate.contract_id != contract.contract_id:
        findings.append(prefix + "contract_mismatch")
    dimensions = (
        ("terminal_outcome", candidate.terminal_outcome_ids, contract.terminal_outcome_ids),
        ("obligation", candidate.covered_obligation_ids, contract.required_obligation_ids),
        ("evidence", candidate.evidence_ids, contract.required_evidence_ids),
        ("safety", candidate.safety_constraint_ids, contract.safety_constraint_ids),
        ("side_effect", candidate.protected_side_effect_ids, contract.protected_side_effect_ids),
        ("dependency_authority", candidate.dependency_authority_ids, contract.dependency_authority_ids),
        ("execution_owner", candidate.execution_owner_ids, contract.execution_owner_ids),
    )
    for label, actual, required in dimensions:
        if set(actual) != set(required):
            findings.append(prefix + f"{label}_boundary_mismatch")
    if candidate.diagnostic_boundary not in _DIAGNOSTIC_BOUNDARIES:
        findings.append(prefix + "diagnostic_boundary_invalid")
    if candidate.execution_mode not in _EXECUTION_MODES:
        findings.append(prefix + "execution_mode_invalid")
    if candidate.comparison_basis not in _COMPARISON_BASES:
        findings.append(prefix + "comparison_basis_invalid")
    if not candidate.comparison_evidence_ids:
        findings.append(prefix + "comparison_evidence_missing")
    nodes = candidate.step_ids + candidate.validation_requirement_ids
    if _duplicates(nodes):
        findings.append(prefix + "dependency_node_duplicate")
    if any(
        not source or not target or source not in nodes or target not in nodes
        for source, target in candidate.dependency_edges
    ):
        findings.append(prefix + "dependency_edge_invalid")
    elif _has_cycle(nodes, candidate.dependency_edges):
        findings.append(prefix + "dependency_cycle")
    else:
        positions = {node: index for index, node in enumerate(nodes)}
        if any(positions[source] >= positions[target] for source, target in candidate.dependency_edges):
            findings.append(prefix + "declared_order_not_dependency_linearization")
    findings.extend(_step_metadata_findings(candidate, prefix))
    if candidate.execution_mode == "safe_parallel":
        isolation_rows = (
            candidate.dependency_isolation_evidence_ids,
            candidate.state_isolation_evidence_ids,
            candidate.side_effect_isolation_evidence_ids,
            candidate.execution_owner_isolation_evidence_ids,
        )
        if any(not row for row in isolation_rows):
            findings.append(prefix + "parallel_isolation_evidence_missing")
    if not candidate.applicable:
        findings.append(prefix + "not_applicable")
    if not candidate.current:
        findings.append(prefix + "not_current")
    return findings


def _repair_findings(
    group: ProcessRepairGroup,
    contract: ProcessOptimizationContract,
) -> list[str]:
    prefix = f"repair_group:{group.group_id or '(missing)'}:"
    findings: list[str] = []
    for value, code in (
        (group.group_id, "identity_invalid"),
        (group.finding_ids, "finding_ids_missing"),
        (group.root_cause_claim, "root_cause_claim_missing"),
        (group.disproof_check_ids, "disproof_checks_missing"),
        (group.owner_evidence_ids, "owner_evidence_missing"),
        (group.repair_action_ids, "repair_actions_missing"),
        (group.required_revalidation_ids, "required_revalidation_missing"),
    ):
        if not value:
            findings.append(prefix + code)
    if len(group.finding_ids) > 1 and not group.relation_evidence_ids:
        findings.append(prefix + "relation_evidence_missing")
    if not group.affected_obligation_ids:
        findings.append(prefix + "affected_obligations_missing")
    elif not set(group.affected_obligation_ids).issubset(contract.required_obligation_ids):
        findings.append(prefix + "affected_obligation_unknown")
    if group.status not in _REPAIR_STATUSES:
        findings.append(prefix + "status_invalid")
    if group.status == "complete" and not set(group.required_revalidation_ids).issubset(
        group.current_revalidation_ids
    ):
        findings.append(prefix + "revalidation_incomplete")
    return findings


def _review_process_optimization(
    decision: ProcessOptimizationDecision,
) -> ProcessOptimizationReport:
    findings: list[str] = []
    reasons = decision.activation_reasons
    if not reasons:
        unnecessary = bool(
            decision.candidates
            or decision.repair_groups
            or decision.selected_candidate_id
            or decision.current_evidence_ids
            or decision.material_evidence_ids
            or decision.selection_rationale
        )
        if unnecessary:
            findings.append("inactive_optimizer_state_present")
            return ProcessOptimizationReport(
                False,
                "blocked",
                decision.decision_id,
                finding_codes=tuple(findings),
                claim_boundary="ordinary work must not carry optimizer ceremony",
                summary="blocked: inactive process contains optimization state",
            )
        return ProcessOptimizationReport(
            True,
            "not_needed",
            decision.decision_id,
            claim_boundary="one clear route; ordinary DevelopmentProcessFlow governance applies",
            summary="not needed: no material process-optimization reason",
        )

    invalid_reasons = sorted(set(reasons) - _ACTIVATION_REASONS)
    if invalid_reasons or _duplicates(reasons):
        findings.append("activation_reason_invalid")
    for value, code in (
        (decision.decision_id, "decision_identity_invalid"),
        (decision.input_revision, "input_revision_missing"),
        (decision.current_evidence_ids, "current_evidence_missing"),
        (decision.material_evidence_ids, "material_evidence_missing"),
    ):
        if not value:
            findings.append(code)
    contract = decision.outcome_contract
    if not contract.contract_id or not contract.revision:
        findings.append("outcome_contract_identity_invalid")
    if not contract.terminal_outcome_ids:
        findings.append("terminal_outcome_missing")
    if not contract.required_obligation_ids or not contract.required_evidence_ids:
        findings.append("outcome_contract_evidence_missing")

    current_evidence = set(decision.current_evidence_ids)
    evidence_references: list[tuple[str, tuple[str, ...]]] = [
        ("contract", contract.required_evidence_ids),
        ("material", decision.material_evidence_ids),
    ]

    candidate_ids = [candidate.candidate_id for candidate in decision.candidates]
    if _duplicates(candidate_ids):
        findings.append("candidate_identity_duplicate")
    if any(not candidate_id for candidate_id in candidate_ids):
        findings.append("candidate_set_identity_invalid")
    eligible: list[str] = []
    rejected: list[str] = []
    rejected_candidate_findings: list[str] = []
    findings_by_candidate: dict[str, tuple[str, ...]] = {}
    for candidate in decision.candidates:
        candidate_findings = _candidate_findings(candidate, contract)
        candidate_evidence_references = (
            ("equivalence", candidate.evidence_ids),
            ("comparison", candidate.comparison_evidence_ids),
            ("dependency-isolation", candidate.dependency_isolation_evidence_ids),
            ("state-isolation", candidate.state_isolation_evidence_ids),
            ("side-effect-isolation", candidate.side_effect_isolation_evidence_ids),
            ("execution-owner-isolation", candidate.execution_owner_isolation_evidence_ids),
            (
                "step-effort",
                tuple(evidence for _, evidence in candidate.step_effort_evidence_ids),
            ),
        )
        for label, evidence_ids in candidate_evidence_references:
            if set(evidence_ids) - current_evidence:
                candidate_findings.append(
                    f"candidate:{candidate.candidate_id}:current_evidence_reference_missing:{label}"
                )
        frozen_candidate_findings = tuple(candidate_findings)
        findings_by_candidate[candidate.candidate_id] = frozen_candidate_findings
        if frozen_candidate_findings:
            rejected.append(candidate.candidate_id)
            rejected_candidate_findings.extend(frozen_candidate_findings)
        else:
            eligible.append(candidate.candidate_id)

    if not decision.candidates:
        findings.append("candidate_selection_missing")
    elif not eligible:
        findings.append("no_current_hard_equivalent_candidate")
    if decision.selected_candidate_id and decision.selected_candidate_id not in candidate_ids:
        findings.append("selected_candidate_unknown")
    elif decision.selected_candidate_id and findings_by_candidate.get(
        decision.selected_candidate_id
    ):
        findings.append("selected_candidate_ineligible")

    group_ids = [group.group_id for group in decision.repair_groups]
    if _duplicates(group_ids):
        findings.append("repair_group_identity_duplicate")
    grouped_findings: list[str] = []
    required_revalidation: list[str] = []
    for group in decision.repair_groups:
        findings.extend(_repair_findings(group, contract))
        grouped_findings.extend(group.finding_ids)
        required_revalidation.extend(group.required_revalidation_ids)
        evidence_references.extend(
            (f"repair_group:{group.group_id}:{label}", ids)
            for label, ids in (
                ("relation", group.relation_evidence_ids),
                ("owner", group.owner_evidence_ids),
                ("revalidation", group.current_revalidation_ids),
            )
        )
    if _duplicates(grouped_findings):
        findings.append("raw_finding_grouped_more_than_once")
    for label, evidence_ids in evidence_references:
        if set(evidence_ids) - current_evidence:
            findings.append(f"current_evidence_reference_missing:{label}")

    eligible_candidates = tuple(
        candidate
        for candidate in decision.candidates
        if candidate.candidate_id in eligible
    )
    bases = {candidate.comparison_basis for candidate in eligible_candidates}
    if len(bases) > 1:
        findings.append("candidate_comparison_basis_incomparable")
    cost_rows = tuple(
        (candidate.candidate_id, *_candidate_cost_vector(candidate))
        for candidate in eligible_candidates
    )
    costs_by_candidate = {str(row[0]): tuple(row[1:]) for row in cost_rows}
    if any(
        any(value is None for value in costs)
        for costs in costs_by_candidate.values()
    ):
        findings.append("candidate_cost_vector_incomplete")
    non_dominated: tuple[str, ...] = ()
    derived_selected_id = ""
    if cost_rows and len(bases) == 1 and not any(
        value is None
        for costs in costs_by_candidate.values()
        for value in costs
    ):
        non_dominated = tuple(
            candidate_id
            for candidate_id, costs in costs_by_candidate.items()
            if not any(
                other_id != candidate_id
                and _cost_relation(other_costs, costs) == "dominates"
                for other_id, other_costs in costs_by_candidate.items()
            )
        )
        dominating_all = tuple(
            candidate_id
            for candidate_id, costs in costs_by_candidate.items()
            if all(
                other_id == candidate_id
                or _cost_relation(costs, other_costs) == "dominates"
                for other_id, other_costs in costs_by_candidate.items()
            )
        )
        if len(cost_rows) == 1:
            derived_selected_id = str(cost_rows[0][0])
        elif len(dominating_all) == 1:
            derived_selected_id = dominating_all[0]
        else:
            relations = {
                _cost_relation(left, right)
                for left_id, left in costs_by_candidate.items()
                for right_id, right in costs_by_candidate.items()
                if left_id < right_id
            }
            findings.append(
                "candidate_cost_tie_unresolved"
                if relations and relations == {"equal"}
                else "candidate_cost_tradeoff_unresolved"
            )
            if decision.selected_candidate_id:
                findings.append("caller_selection_cannot_break_non_dominated_boundary")
    if derived_selected_id and decision.selected_candidate_id:
        if decision.selected_candidate_id != derived_selected_id:
            caller_cost = costs_by_candidate.get(decision.selected_candidate_id)
            selected_cost = costs_by_candidate[derived_selected_id]
            if (
                caller_cost is not None
                and _cost_relation(selected_cost, caller_cost) == "dominates"
            ):
                findings.append("caller_selected_candidate_dominated")
    selected_cost_row = next(
        (row for row in cost_rows if row[0] == derived_selected_id),
        None,
    )
    derived_rationale = _derived_selection_rationale(selected_cost_row)
    if derived_selected_id and not derived_rationale:
        findings.append("derived_selection_rationale_missing")
    selected = next(
        (
            candidate
            for candidate in eligible_candidates
            if candidate.candidate_id == derived_selected_id
        ),
        None,
    )
    if findings:
        evidence_only = all(
            code.endswith(_EVIDENCE_GAP_SUFFIXES)
            or code
            in {
                "candidate_cost_tie_unresolved",
                "candidate_cost_tradeoff_unresolved",
                "caller_selection_cannot_break_non_dominated_boundary",
            }
            for code in findings
        )
        status = "needs_evidence" if evidence_only else "blocked"
        return ProcessOptimizationReport(
            False,
            status,
            decision.decision_id,
            selected_candidate_id=derived_selected_id,
            eligible_candidate_ids=tuple(eligible),
            rejected_candidate_ids=tuple(rejected),
            selected_comparison_basis=selected.comparison_basis if selected else "",
            candidate_cost_rows=cost_rows,
            non_dominated_candidate_ids=non_dominated,
            required_revalidation_ids=tuple(dict.fromkeys(required_revalidation)),
            finding_codes=tuple(findings),
            summary=f"{status}: {len(findings)} process-optimization gap(s)",
            rejected_candidate_finding_codes=tuple(rejected_candidate_findings),
            selection_rationale=derived_rationale,
            caller_selection_rationale=decision.selection_rationale,
            claim_boundary="no process recommendation is valid until every listed gap is closed",
        )

    basis = selected.comparison_basis if selected else ""
    qualifier = "measured" if basis == "measured" else "qualitative"
    return ProcessOptimizationReport(
        True,
        "selected",
        decision.decision_id,
        selected_candidate_id=derived_selected_id,
        eligible_candidate_ids=tuple(eligible),
        rejected_candidate_ids=tuple(rejected),
        selected_comparison_basis=basis,
        candidate_cost_rows=cost_rows,
        non_dominated_candidate_ids=non_dominated,
        required_revalidation_ids=tuple(dict.fromkeys(required_revalidation)),
        rejected_candidate_finding_codes=tuple(rejected_candidate_findings),
        selection_rationale=derived_rationale,
        caller_selection_rationale=decision.selection_rationale,
        claim_boundary=(
            "Pareto-dominating process candidate within the declared "
            f"hard-equivalent candidates under current {qualifier} evidence dimensions; "
            "this is not a model-path quality conclusion and no unrestricted global optimum is claimed"
        ),
        summary=f"selected: {derived_selected_id}",
    )
