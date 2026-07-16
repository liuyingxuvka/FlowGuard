"""Conditional process optimization owned by DevelopmentProcessFlow.

The optimizer is intentionally small.  It does not run diagnostics, tests, or
repairs.  It admits process comparison only when a real optimization reason is
present, rejects routes that weaken the declared outcome contract, and keeps
every recommendation bounded by current evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .export import to_jsonable


_ACTIVATION_REASONS = {
    "explicit_request",
    "multiple_equivalent_routes",
    "material_rework_risk",
    "diagnostic_boundary_choice",
}
_DIAGNOSTIC_BOUNDARIES = {"targeted", "declared_complete", "budgeted"}
_EXECUTION_MODES = {"sequential", "safe_parallel"}
_COMPARISON_BASES = {"qualitative", "measured"}
_REPAIR_STATUSES = {"open", "complete", "blocked"}
_EVIDENCE_GAP_SUFFIXES = (
    "_evidence_missing",
    "_revision_missing",
    "_rationale_missing",
    "_selection_missing",
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_pairs(
    values: Sequence[Sequence[str]] | None,
) -> tuple[tuple[str, str], ...]:
    if values is None:
        return ()
    pairs: list[tuple[str, str]] = []
    for value in values:
        if len(value) != 2:
            pairs.append(("", ""))
        else:
            pairs.append((str(value[0]), str(value[1])))
    return tuple(pairs)


def _duplicates(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    repeated: list[str] = []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return tuple(repeated)


def _record_dict(record: Any) -> dict[str, Any]:
    return dict(to_jsonable(asdict(record)))


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


@dataclass(frozen=True)
class ProcessOptimizationContract:
    """The observable guarantees every comparable route must preserve."""

    contract_id: str
    terminal_outcome_ids: tuple[str, ...] = ()
    required_obligation_ids: tuple[str, ...] = ()
    required_evidence_ids: tuple[str, ...] = ()
    safety_constraint_ids: tuple[str, ...] = ()
    protected_side_effect_ids: tuple[str, ...] = ()
    dependency_authority_ids: tuple[str, ...] = ()
    execution_owner_ids: tuple[str, ...] = ()
    revision: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        for name in (
            "terminal_outcome_ids",
            "required_obligation_ids",
            "required_evidence_ids",
            "safety_constraint_ids",
            "protected_side_effect_ids",
            "dependency_authority_ids",
            "execution_owner_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "revision", str(self.revision))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessOptimizationCandidate:
    """One outcome-equivalent route and its two independent process choices."""

    candidate_id: str
    contract_id: str
    terminal_outcome_ids: tuple[str, ...] = ()
    covered_obligation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    safety_constraint_ids: tuple[str, ...] = ()
    protected_side_effect_ids: tuple[str, ...] = ()
    dependency_authority_ids: tuple[str, ...] = ()
    execution_owner_ids: tuple[str, ...] = ()
    step_ids: tuple[str, ...] = ()
    validation_requirement_ids: tuple[str, ...] = ()
    dependency_edges: tuple[tuple[str, str], ...] = ()
    stop_condition_ids: tuple[str, ...] = ()
    diagnostic_boundary: str = "targeted"
    execution_mode: str = "sequential"
    dependency_isolation_evidence_ids: tuple[str, ...] = ()
    state_isolation_evidence_ids: tuple[str, ...] = ()
    side_effect_isolation_evidence_ids: tuple[str, ...] = ()
    execution_owner_isolation_evidence_ids: tuple[str, ...] = ()
    comparison_basis: str = "qualitative"
    comparison_evidence_ids: tuple[str, ...] = ()
    applicable: bool = True
    current: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "contract_id", str(self.contract_id))
        for name in (
            "terminal_outcome_ids",
            "covered_obligation_ids",
            "evidence_ids",
            "safety_constraint_ids",
            "protected_side_effect_ids",
            "dependency_authority_ids",
            "execution_owner_ids",
            "step_ids",
            "validation_requirement_ids",
            "stop_condition_ids",
            "dependency_isolation_evidence_ids",
            "state_isolation_evidence_ids",
            "side_effect_isolation_evidence_ids",
            "execution_owner_isolation_evidence_ids",
            "comparison_evidence_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "dependency_edges", _as_pairs(self.dependency_edges))
        object.__setattr__(self, "diagnostic_boundary", str(self.diagnostic_boundary))
        object.__setattr__(self, "execution_mode", str(self.execution_mode))
        object.__setattr__(self, "comparison_basis", str(self.comparison_basis))
        object.__setattr__(self, "applicable", bool(self.applicable))
        object.__setattr__(self, "current", bool(self.current))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessRepairGroup:
    """An evidence-backed shared repair that never replaces raw findings."""

    group_id: str
    finding_ids: tuple[str, ...] = ()
    relation_evidence_ids: tuple[str, ...] = ()
    root_cause_claim: str = ""
    disproof_check_ids: tuple[str, ...] = ()
    affected_obligation_ids: tuple[str, ...] = ()
    owner_evidence_ids: tuple[str, ...] = ()
    repair_action_ids: tuple[str, ...] = ()
    required_revalidation_ids: tuple[str, ...] = ()
    current_revalidation_ids: tuple[str, ...] = ()
    status: str = "open"

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", str(self.group_id))
        for name in (
            "finding_ids",
            "relation_evidence_ids",
            "disproof_check_ids",
            "affected_obligation_ids",
            "owner_evidence_ids",
            "repair_action_ids",
            "required_revalidation_ids",
            "current_revalidation_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "root_cause_claim", str(self.root_cause_claim))
        object.__setattr__(self, "status", str(self.status))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessOptimizationDecision:
    """One conditional optimization decision bound to current evidence."""

    decision_id: str
    outcome_contract: ProcessOptimizationContract
    activation_reasons: tuple[str, ...] = ()
    candidates: tuple[ProcessOptimizationCandidate, ...] = ()
    repair_groups: tuple[ProcessRepairGroup, ...] = ()
    selected_candidate_id: str = ""
    input_revision: str = ""
    current_evidence_ids: tuple[str, ...] = ()
    material_evidence_ids: tuple[str, ...] = ()
    selection_rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", str(self.decision_id))
        object.__setattr__(self, "activation_reasons", _as_tuple(self.activation_reasons))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "repair_groups", tuple(self.repair_groups))
        object.__setattr__(self, "selected_candidate_id", str(self.selected_candidate_id))
        object.__setattr__(self, "input_revision", str(self.input_revision))
        object.__setattr__(self, "current_evidence_ids", _as_tuple(self.current_evidence_ids))
        object.__setattr__(self, "material_evidence_ids", _as_tuple(self.material_evidence_ids))
        object.__setattr__(self, "selection_rationale", str(self.selection_rationale))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessOptimizationReport:
    """A bounded result; never a claim of unrestricted global optimality."""

    ok: bool
    status: str
    decision_id: str
    selected_candidate_id: str = ""
    eligible_candidate_ids: tuple[str, ...] = ()
    rejected_candidate_ids: tuple[str, ...] = ()
    selected_comparison_basis: str = ""
    required_revalidation_ids: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()
    claim_boundary: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


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
    if any(not source or not target or source not in nodes or target not in nodes for source, target in candidate.dependency_edges):
        findings.append(prefix + "dependency_edge_invalid")
    elif _has_cycle(nodes, candidate.dependency_edges):
        findings.append(prefix + "dependency_cycle")
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
    if not group.group_id:
        findings.append(prefix + "identity_invalid")
    if not group.finding_ids:
        findings.append(prefix + "finding_ids_missing")
    if len(group.finding_ids) > 1 and not group.relation_evidence_ids:
        findings.append(prefix + "relation_evidence_missing")
    if not group.root_cause_claim:
        findings.append(prefix + "root_cause_claim_missing")
    if not group.disproof_check_ids:
        findings.append(prefix + "disproof_checks_missing")
    if not group.affected_obligation_ids:
        findings.append(prefix + "affected_obligations_missing")
    elif not set(group.affected_obligation_ids).issubset(contract.required_obligation_ids):
        findings.append(prefix + "affected_obligation_unknown")
    if not group.owner_evidence_ids:
        findings.append(prefix + "owner_evidence_missing")
    if not group.repair_action_ids:
        findings.append(prefix + "repair_actions_missing")
    if not group.required_revalidation_ids:
        findings.append(prefix + "required_revalidation_missing")
    if group.status not in _REPAIR_STATUSES:
        findings.append(prefix + "status_invalid")
    if group.status == "complete" and not set(group.required_revalidation_ids).issubset(
        group.current_revalidation_ids
    ):
        findings.append(prefix + "revalidation_incomplete")
    return findings


def review_process_optimization(
    decision: ProcessOptimizationDecision,
) -> ProcessOptimizationReport:
    """Review one conditional process choice without executing its workflow."""

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
    if not decision.decision_id:
        findings.append("decision_identity_invalid")
    if not decision.input_revision:
        findings.append("input_revision_missing")
    if not decision.current_evidence_ids:
        findings.append("current_evidence_missing")
    if not decision.material_evidence_ids:
        findings.append("material_evidence_missing")
    if not decision.selection_rationale:
        findings.append("selection_rationale_missing")

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
    eligible: list[str] = []
    rejected: list[str] = []
    findings_by_candidate: dict[str, tuple[str, ...]] = {}
    for candidate in decision.candidates:
        candidate_findings = tuple(_candidate_findings(candidate, contract))
        findings.extend(candidate_findings)
        findings_by_candidate[candidate.candidate_id] = candidate_findings
        if candidate_findings:
            rejected.append(candidate.candidate_id)
        else:
            eligible.append(candidate.candidate_id)
        evidence_references.extend(
            [
                (f"candidate:{candidate.candidate_id}:equivalence", candidate.evidence_ids),
                (f"candidate:{candidate.candidate_id}:comparison", candidate.comparison_evidence_ids),
                (
                    f"candidate:{candidate.candidate_id}:dependency-isolation",
                    candidate.dependency_isolation_evidence_ids,
                ),
                (
                    f"candidate:{candidate.candidate_id}:state-isolation",
                    candidate.state_isolation_evidence_ids,
                ),
                (
                    f"candidate:{candidate.candidate_id}:side-effect-isolation",
                    candidate.side_effect_isolation_evidence_ids,
                ),
                (
                    f"candidate:{candidate.candidate_id}:execution-owner-isolation",
                    candidate.execution_owner_isolation_evidence_ids,
                ),
            ]
        )

    if not decision.candidates:
        findings.append("candidate_selection_missing")
    if not decision.selected_candidate_id:
        findings.append("selected_candidate_missing")
    elif decision.selected_candidate_id not in candidate_ids:
        findings.append("selected_candidate_unknown")
    elif findings_by_candidate.get(decision.selected_candidate_id):
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
            [
                (f"repair_group:{group.group_id}:relation", group.relation_evidence_ids),
                (f"repair_group:{group.group_id}:owner", group.owner_evidence_ids),
                (
                    f"repair_group:{group.group_id}:revalidation",
                    group.current_revalidation_ids,
                ),
            ]
        )
    if _duplicates(grouped_findings):
        findings.append("raw_finding_grouped_more_than_once")
    for label, evidence_ids in evidence_references:
        if set(evidence_ids) - current_evidence:
            findings.append(f"current_evidence_reference_missing:{label}")

    selected = next(
        (
            candidate
            for candidate in decision.candidates
            if candidate.candidate_id == decision.selected_candidate_id
        ),
        None,
    )
    if findings:
        evidence_only = all(
            code.endswith(_EVIDENCE_GAP_SUFFIXES)
            for code in findings
        )
        status = "needs_evidence" if evidence_only else "blocked"
        return ProcessOptimizationReport(
            False,
            status,
            decision.decision_id,
            selected_candidate_id=decision.selected_candidate_id,
            eligible_candidate_ids=tuple(eligible),
            rejected_candidate_ids=tuple(rejected),
            selected_comparison_basis=selected.comparison_basis if selected else "",
            required_revalidation_ids=tuple(dict.fromkeys(required_revalidation)),
            finding_codes=tuple(findings),
            claim_boundary="no process recommendation is valid until every listed gap is closed",
            summary=f"{status}: {len(findings)} process-optimization gap(s)",
        )

    basis = selected.comparison_basis if selected else ""
    qualifier = "measured" if basis == "measured" else "qualitative"
    return ProcessOptimizationReport(
        True,
        "selected",
        decision.decision_id,
        selected_candidate_id=decision.selected_candidate_id,
        eligible_candidate_ids=tuple(eligible),
        rejected_candidate_ids=tuple(rejected),
        selected_comparison_basis=basis,
        required_revalidation_ids=tuple(dict.fromkeys(required_revalidation)),
        claim_boundary=(
            f"preferred among the declared hard-equivalent candidates under current {qualifier} "
            "evidence; no unrestricted global optimum is claimed"
        ),
        summary=f"selected: {decision.selected_candidate_id}",
    )


__all__ = [
    "ProcessOptimizationContract",
    "ProcessOptimizationCandidate",
    "ProcessRepairGroup",
    "ProcessOptimizationDecision",
    "ProcessOptimizationReport",
    "review_process_optimization",
]
