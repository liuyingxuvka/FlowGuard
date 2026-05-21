"""Model-backed architecture reduction review helpers.

Architecture reduction reviews whether a modeled flow can support simpler code
structure without changing declared observable behavior. It reports candidates
and handoff requirements; it does not rewrite production code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .code_structure import CodeStructureRecommendation, review_code_structure_recommendation
from .export import to_jsonable


ARCHITECTURE_REDUCTION_ROUTE = "architecture_reduction"

CANDIDATE_MERGE_HANDLERS = "merge_handlers"
CANDIDATE_MERGE_MODULES = "merge_modules"
CANDIDATE_COLLAPSE_ADAPTER = "collapse_adapter"
CANDIDATE_REMOVE_BRANCH = "remove_branch"
CANDIDATE_REMOVE_STATE_FIELD = "remove_state_field"
CANDIDATE_MERGE_STATE_PHASE = "merge_state_phase"
CANDIDATE_REMOVE_DUPLICATE_VALIDATION = "remove_duplicate_validation"
CANDIDATE_KEEP_PUBLIC_FACADE = "keep_public_facade"
CANDIDATE_MANUAL_REVIEW = "manual_review"

ARCHITECTURE_REDUCTION_CANDIDATE_TYPES = {
    CANDIDATE_MERGE_HANDLERS,
    CANDIDATE_MERGE_MODULES,
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_REMOVE_BRANCH,
    CANDIDATE_REMOVE_STATE_FIELD,
    CANDIDATE_MERGE_STATE_PHASE,
    CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
    CANDIDATE_KEEP_PUBLIC_FACADE,
    CANDIDATE_MANUAL_REVIEW,
}

PROOF_SAFE_BY_EQUIVALENCE = "safe_by_equivalence"
PROOF_SAFE_BY_PUBLIC_FACADE = "safe_by_public_facade"
PROOF_PROPERTY_ONLY_SAFE = "property_only_safe"
PROOF_NEEDS_CONFORMANCE_REPLAY = "needs_conformance_replay"
PROOF_RISKY_KEEP = "risky_keep"
PROOF_BLOCKED_BY_MISSING_EVIDENCE = "blocked_by_missing_evidence"

ARCHITECTURE_REDUCTION_PROOF_STATUSES = {
    PROOF_SAFE_BY_EQUIVALENCE,
    PROOF_SAFE_BY_PUBLIC_FACADE,
    PROOF_PROPERTY_ONLY_SAFE,
    PROOF_NEEDS_CONFORMANCE_REPLAY,
    PROOF_RISKY_KEEP,
    PROOF_BLOCKED_BY_MISSING_EVIDENCE,
}

READY_PROOF_STATUSES = {
    PROOF_SAFE_BY_EQUIVALENCE,
    PROOF_SAFE_BY_PUBLIC_FACADE,
}

TARGET_ACTION_MERGE = "merge"
TARGET_ACTION_COLLAPSE = "collapse"
TARGET_ACTION_REMOVE = "remove"
TARGET_ACTION_KEEP_FACADE = "keep_facade"
TARGET_ACTION_MANUAL_REVIEW = "manual_review"

ARCHITECTURE_REDUCTION_TARGET_ACTIONS = {
    TARGET_ACTION_MERGE,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_REMOVE,
    TARGET_ACTION_KEEP_FACADE,
    TARGET_ACTION_MANUAL_REVIEW,
}

ROUTE_DEVELOPMENT_PROCESS_FLOW = "development_process_flow"
ROUTE_EXISTING_MODEL_PREFLIGHT = "existing_model_preflight"
ROUTE_CODE_STRUCTURE_RECOMMENDATION = "code_structure_recommendation"
ROUTE_STRUCTURE_MESH = "structure_mesh"
ROUTE_MODEL_MESH = "model_mesh"
ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
ROUTE_UI_FLOW_STRUCTURE = "ui_flow_structure"
ROUTE_CONFORMANCE_REPLAY = "conformance_replay"
ROUTE_MANUAL_REVIEW = "manual_review"

ARCHITECTURE_REDUCTION_COMPANION_ROUTES = {
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_EXISTING_MODEL_PREFLIGHT,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_STRUCTURE_MESH,
    ROUTE_MODEL_MESH,
    ROUTE_MODEL_TEST_ALIGNMENT,
    ROUTE_UI_FLOW_STRUCTURE,
    ROUTE_CONFORMANCE_REPLAY,
    ROUTE_MANUAL_REVIEW,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class ObservableArchitectureContract:
    """Public behavior boundary that code contraction must preserve."""

    source_model_id: str
    source_code_boundary_id: str
    public_entrypoints: tuple[str, ...] = ()
    observable_outputs: tuple[str, ...] = ()
    observable_state: tuple[str, ...] = ()
    observable_side_effects: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "source_code_boundary_id", str(self.source_code_boundary_id))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "observable_outputs", _as_tuple(self.observable_outputs))
        object.__setattr__(self, "observable_state", _as_tuple(self.observable_state))
        object.__setattr__(self, "observable_side_effects", _as_tuple(self.observable_side_effects))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.source_model_id:
            missing.append("source_model_id")
        if not self.source_code_boundary_id:
            missing.append("source_code_boundary_id")
        if not self.public_entrypoints:
            missing.append("public_entrypoints")
        if not self.observable_outputs:
            missing.append("observable_outputs")
        if not self.validation_boundaries:
            missing.append("validation_boundaries")
        if not self.rationale:
            missing.append("rationale")
        return tuple(missing)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_model_id": self.source_model_id,
            "source_code_boundary_id": self.source_code_boundary_id,
            "public_entrypoints": list(self.public_entrypoints),
            "observable_outputs": list(self.observable_outputs),
            "observable_state": list(self.observable_state),
            "observable_side_effects": list(self.observable_side_effects),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ArchitectureReductionCandidate:
    """One model-backed code contraction candidate."""

    candidate_id: str
    candidate_type: str
    code_node_id: str
    source_model_element: str
    target_action: str
    proof_status: str
    required_next_route: str
    rationale: str
    affected_public_entrypoints: tuple[str, ...] = ()
    affected_state: tuple[str, ...] = ()
    affected_side_effects: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "candidate_type", str(self.candidate_type))
        object.__setattr__(self, "code_node_id", str(self.code_node_id))
        object.__setattr__(self, "source_model_element", str(self.source_model_element))
        object.__setattr__(self, "target_action", str(self.target_action))
        object.__setattr__(self, "proof_status", str(self.proof_status))
        object.__setattr__(self, "required_next_route", str(self.required_next_route))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "affected_public_entrypoints", _as_tuple(self.affected_public_entrypoints))
        object.__setattr__(self, "affected_state", _as_tuple(self.affected_state))
        object.__setattr__(self, "affected_side_effects", _as_tuple(self.affected_side_effects))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def is_ready(self) -> bool:
        return self.proof_status in READY_PROOF_STATUSES

    def touches_public_entrypoint(self) -> bool:
        return bool(self.affected_public_entrypoints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "code_node_id": self.code_node_id,
            "source_model_element": self.source_model_element,
            "target_action": self.target_action,
            "proof_status": self.proof_status,
            "required_next_route": self.required_next_route,
            "rationale": self.rationale,
            "affected_public_entrypoints": list(self.affected_public_entrypoints),
            "affected_state": list(self.affected_state),
            "affected_side_effects": list(self.affected_side_effects),
            "evidence_refs": list(self.evidence_refs),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArchitectureReductionTrigger:
    """Complexity-growth signal from a companion FlowGuard route."""

    route_id: str
    trigger_reason: str
    complexity_signal: str = ""
    recommended_timing: str = ""
    required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "trigger_reason", str(self.trigger_reason))
        object.__setattr__(self, "complexity_signal", str(self.complexity_signal))
        object.__setattr__(self, "recommended_timing", str(self.recommended_timing))
        object.__setattr__(self, "required", bool(self.required))

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "trigger_reason": self.trigger_reason,
            "complexity_signal": self.complexity_signal,
            "recommended_timing": self.recommended_timing,
            "required": self.required,
        }


@dataclass(frozen=True)
class TargetArchitectureAction:
    """One target code-structure action derived from a candidate."""

    candidate_id: str
    action: str
    code_node_id: str
    required_next_route: str
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "code_node_id", str(self.code_node_id))
        object.__setattr__(self, "required_next_route", str(self.required_next_route))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "code_node_id": self.code_node_id,
            "required_next_route": self.required_next_route,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ArchitectureReductionPlan:
    """Review input for model-backed code architecture reduction."""

    reduction_id: str
    observable_contract: ObservableArchitectureContract
    candidates: tuple[ArchitectureReductionCandidate, ...] = ()
    companion_route_triggers: tuple[ArchitectureReductionTrigger, ...] = ()
    target_structure: CodeStructureRecommendation | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reduction_id", str(self.reduction_id))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "companion_route_triggers", tuple(self.companion_route_triggers))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reduction_id": self.reduction_id,
            "observable_contract": self.observable_contract.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "companion_route_triggers": [trigger.to_dict() for trigger in self.companion_route_triggers],
            "target_structure": self.target_structure.to_dict() if self.target_structure else None,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ArchitectureReductionFinding:
    """One architecture reduction finding."""

    code: str
    message: str
    severity: str = "blocker"
    candidate_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "candidate_id": self.candidate_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArchitectureReductionReport:
    """Structured architecture reduction review result."""

    ok: bool
    reduction_id: str
    decision: str
    findings: tuple[ArchitectureReductionFinding, ...] = ()
    ready_candidate_ids: tuple[str, ...] = ()
    target_actions: tuple[TargetArchitectureAction, ...] = ()
    required_next_routes: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reduction_id", str(self.reduction_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "ready_candidate_ids", _as_tuple(self.ready_candidate_ids))
        object.__setattr__(self, "target_actions", tuple(self.target_actions))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: reduction={self.reduction_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard architecture reduction review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"reduction: {self.reduction_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        if self.ready_candidate_ids:
            lines.append(f"ready_candidates: {', '.join(self.ready_candidate_ids)}")
        if self.required_next_routes:
            lines.append(f"required_next_routes: {', '.join(self.required_next_routes)}")
        if self.target_actions:
            lines.append("target_actions:")
            for action in self.target_actions:
                lines.append(f"  - {action.action} {action.code_node_id} via {action.required_next_route}")
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"candidate: {finding.candidate_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reduction_id": self.reduction_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "ready_candidate_ids": list(self.ready_candidate_ids),
            "target_actions": [action.to_dict() for action in self.target_actions],
            "required_next_routes": list(self.required_next_routes),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _blockers(findings: Sequence[ArchitectureReductionFinding]) -> tuple[ArchitectureReductionFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(
    findings: Sequence[ArchitectureReductionFinding],
    *,
    candidate_count: int,
    ready_count: int,
) -> str:
    blockers = _blockers(findings)
    if blockers:
        priority = [
            ("missing_observable_contract", "missing_observable_contract"),
            ("incomplete_candidate", "candidate_blocked"),
            ("invalid_candidate_type", "candidate_blocked"),
            ("invalid_target_action", "candidate_blocked"),
            ("invalid_proof_status", "candidate_blocked"),
            ("missing_required_next_route", "candidate_blocked"),
            ("public_entrypoint_requires_structure_mesh", "structure_mesh_required"),
            ("removes_observable_state", "observable_contract_blocked"),
            ("observable_side_effect_without_equivalence", "observable_contract_blocked"),
            ("conformance_replay_required", "conformance_required"),
            ("blocked_by_missing_evidence", "evidence_blocked"),
            ("target_structure_blocked", "target_structure_blocked"),
        ]
        codes = {finding.code for finding in blockers}
        for code, decision in priority:
            if code in codes:
                return decision
        return "architecture_reduction_blocked"
    if any(finding.code == "property_only_reduction" for finding in findings):
        return "property_only_review"
    if candidate_count == 0:
        return "no_reduction_candidates"
    if ready_count == 0:
        return "no_ready_reduction_candidates"
    return "architecture_reduction_ready"


def _candidate_incomplete(candidate: ArchitectureReductionCandidate) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in (
        "candidate_id",
        "candidate_type",
        "code_node_id",
        "source_model_element",
        "target_action",
        "proof_status",
        "required_next_route",
        "rationale",
    ):
        if not getattr(candidate, field_name):
            missing.append(field_name)
    return tuple(missing)


def _target_action_from_candidate(candidate: ArchitectureReductionCandidate) -> TargetArchitectureAction:
    return TargetArchitectureAction(
        candidate_id=candidate.candidate_id,
        action=candidate.target_action,
        code_node_id=candidate.code_node_id,
        required_next_route=candidate.required_next_route,
        rationale=candidate.rationale,
    )


def review_architecture_reduction(plan: ArchitectureReductionPlan) -> ArchitectureReductionReport:
    """Review whether modeled flow evidence supports code architecture contraction."""

    findings: list[ArchitectureReductionFinding] = []
    ready_candidates: list[str] = []
    target_actions: list[TargetArchitectureAction] = []
    required_routes: set[str] = set()

    if not plan.reduction_id:
        findings.append(
            ArchitectureReductionFinding(
                "missing_reduction_id",
                "architecture reduction review has no reduction id",
            )
        )
    if not plan.rationale:
        findings.append(
            ArchitectureReductionFinding(
                "missing_reduction_rationale",
                "architecture reduction review has no route rationale",
                severity="warning",
            )
        )

    missing_contract_fields = plan.observable_contract.missing_fields()
    if missing_contract_fields:
        findings.append(
            ArchitectureReductionFinding(
                "missing_observable_contract",
                "observable architecture contract is incomplete",
                metadata={"missing_fields": missing_contract_fields},
            )
        )

    if not plan.companion_route_triggers:
        findings.append(
            ArchitectureReductionFinding(
                "missing_companion_route_triggers",
                "no companion FlowGuard route triggers are recorded",
                severity="warning",
            )
        )
    for trigger in plan.companion_route_triggers:
        if trigger.route_id not in ARCHITECTURE_REDUCTION_COMPANION_ROUTES:
            findings.append(
                ArchitectureReductionFinding(
                    "unknown_companion_route",
                    f"companion route {trigger.route_id!r} is not recognized",
                    severity="warning",
                    item_id=trigger.route_id,
                )
            )
        if not trigger.trigger_reason:
            findings.append(
                ArchitectureReductionFinding(
                    "missing_companion_trigger_reason",
                    f"companion route {trigger.route_id!r} has no trigger reason",
                    severity="warning",
                    item_id=trigger.route_id,
                )
            )

    observable_state = set(plan.observable_contract.observable_state)
    observable_side_effects = set(plan.observable_contract.observable_side_effects)

    for candidate in plan.candidates:
        missing_candidate_fields = _candidate_incomplete(candidate)
        if missing_candidate_fields:
            findings.append(
                ArchitectureReductionFinding(
                    "incomplete_candidate",
                    "architecture reduction candidate is incomplete",
                    candidate_id=candidate.candidate_id,
                    metadata={"missing_fields": missing_candidate_fields},
                )
            )
        if candidate.candidate_type not in ARCHITECTURE_REDUCTION_CANDIDATE_TYPES:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_candidate_type",
                    f"candidate type {candidate.candidate_type!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.candidate_type,
                )
            )
        if candidate.target_action not in ARCHITECTURE_REDUCTION_TARGET_ACTIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_target_action",
                    f"target action {candidate.target_action!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.target_action,
                )
            )
        if candidate.proof_status not in ARCHITECTURE_REDUCTION_PROOF_STATUSES:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_proof_status",
                    f"proof status {candidate.proof_status!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.proof_status,
                )
            )
        if candidate.required_next_route not in ARCHITECTURE_REDUCTION_COMPANION_ROUTES:
            findings.append(
                ArchitectureReductionFinding(
                    "missing_required_next_route",
                    "candidate does not name a recognized next route",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.required_next_route,
                )
            )
        else:
            required_routes.add(candidate.required_next_route)

        if candidate.touches_public_entrypoint() and candidate.required_next_route != ROUTE_STRUCTURE_MESH:
            findings.append(
                ArchitectureReductionFinding(
                    "public_entrypoint_requires_structure_mesh",
                    "candidate affects public entrypoints and must route through StructureMesh",
                    candidate_id=candidate.candidate_id,
                    metadata={"affected_public_entrypoints": candidate.affected_public_entrypoints},
                )
            )

        removed_observable_state = tuple(sorted(observable_state.intersection(candidate.affected_state)))
        if candidate.target_action == TARGET_ACTION_REMOVE and removed_observable_state:
            findings.append(
                ArchitectureReductionFinding(
                    "removes_observable_state",
                    "candidate removes state declared observable by the contract",
                    candidate_id=candidate.candidate_id,
                    metadata={"observable_state": removed_observable_state},
                )
            )

        touched_observable_side_effects = tuple(sorted(observable_side_effects.intersection(candidate.affected_side_effects)))
        if (
            candidate.target_action in {TARGET_ACTION_REMOVE, TARGET_ACTION_COLLAPSE}
            and touched_observable_side_effects
            and candidate.proof_status != PROOF_SAFE_BY_EQUIVALENCE
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "observable_side_effect_without_equivalence",
                    "candidate changes observable side-effect structure without full equivalence proof",
                    candidate_id=candidate.candidate_id,
                    metadata={"observable_side_effects": touched_observable_side_effects},
                )
            )

        if candidate.proof_status == PROOF_PROPERTY_ONLY_SAFE:
            findings.append(
                ArchitectureReductionFinding(
                    "property_only_reduction",
                    "candidate only preserves declared properties, not full observable behavior",
                    severity="warning",
                    candidate_id=candidate.candidate_id,
                )
            )
        elif candidate.proof_status == PROOF_NEEDS_CONFORMANCE_REPLAY:
            findings.append(
                ArchitectureReductionFinding(
                    "conformance_replay_required",
                    "candidate needs conformance replay before it can support code contraction",
                    candidate_id=candidate.candidate_id,
                )
            )
        elif candidate.proof_status == PROOF_RISKY_KEEP:
            findings.append(
                ArchitectureReductionFinding(
                    "risky_candidate_kept",
                    "candidate looks reducible but must be kept unless stronger evidence is added",
                    severity="warning",
                    candidate_id=candidate.candidate_id,
                )
            )
        elif candidate.proof_status == PROOF_BLOCKED_BY_MISSING_EVIDENCE:
            findings.append(
                ArchitectureReductionFinding(
                    "blocked_by_missing_evidence",
                    "candidate lacks enough evidence for architecture contraction",
                    candidate_id=candidate.candidate_id,
                )
            )

        if candidate.is_ready:
            ready_candidates.append(candidate.candidate_id)
            target_actions.append(_target_action_from_candidate(candidate))

    if plan.target_structure is not None:
        structure_report = review_code_structure_recommendation(plan.target_structure)
        if not structure_report.ok:
            for structure_finding in structure_report.findings:
                findings.append(
                    ArchitectureReductionFinding(
                        "target_structure_blocked",
                        f"target structure recommendation is blocked: {structure_finding.code}",
                        item_id=structure_finding.item_id,
                        metadata=structure_finding.to_dict(),
                    )
                )

    decision = _decision_for_findings(
        findings,
        candidate_count=len(plan.candidates),
        ready_count=len(ready_candidates),
    )
    blockers = _blockers(findings)
    return ArchitectureReductionReport(
        ok=not blockers,
        reduction_id=plan.reduction_id,
        decision=decision,
        findings=tuple(findings),
        ready_candidate_ids=tuple(ready_candidates),
        target_actions=tuple(target_actions),
        required_next_routes=tuple(sorted(required_routes)),
    )


__all__ = [
    "ARCHITECTURE_REDUCTION_CANDIDATE_TYPES",
    "ARCHITECTURE_REDUCTION_COMPANION_ROUTES",
    "ARCHITECTURE_REDUCTION_PROOF_STATUSES",
    "ARCHITECTURE_REDUCTION_ROUTE",
    "ARCHITECTURE_REDUCTION_TARGET_ACTIONS",
    "CANDIDATE_COLLAPSE_ADAPTER",
    "CANDIDATE_KEEP_PUBLIC_FACADE",
    "CANDIDATE_MANUAL_REVIEW",
    "CANDIDATE_MERGE_HANDLERS",
    "CANDIDATE_MERGE_MODULES",
    "CANDIDATE_MERGE_STATE_PHASE",
    "CANDIDATE_REMOVE_BRANCH",
    "CANDIDATE_REMOVE_DUPLICATE_VALIDATION",
    "CANDIDATE_REMOVE_STATE_FIELD",
    "PROOF_BLOCKED_BY_MISSING_EVIDENCE",
    "PROOF_NEEDS_CONFORMANCE_REPLAY",
    "PROOF_PROPERTY_ONLY_SAFE",
    "PROOF_RISKY_KEEP",
    "PROOF_SAFE_BY_EQUIVALENCE",
    "PROOF_SAFE_BY_PUBLIC_FACADE",
    "READY_PROOF_STATUSES",
    "ROUTE_CODE_STRUCTURE_RECOMMENDATION",
    "ROUTE_CONFORMANCE_REPLAY",
    "ROUTE_DEVELOPMENT_PROCESS_FLOW",
    "ROUTE_EXISTING_MODEL_PREFLIGHT",
    "ROUTE_MANUAL_REVIEW",
    "ROUTE_MODEL_MESH",
    "ROUTE_MODEL_TEST_ALIGNMENT",
    "ROUTE_STRUCTURE_MESH",
    "ROUTE_UI_FLOW_STRUCTURE",
    "TARGET_ACTION_COLLAPSE",
    "TARGET_ACTION_KEEP_FACADE",
    "TARGET_ACTION_MANUAL_REVIEW",
    "TARGET_ACTION_MERGE",
    "TARGET_ACTION_REMOVE",
    "ArchitectureReductionCandidate",
    "ArchitectureReductionFinding",
    "ArchitectureReductionPlan",
    "ArchitectureReductionReport",
    "ArchitectureReductionTrigger",
    "ObservableArchitectureContract",
    "TargetArchitectureAction",
    "review_architecture_reduction",
]
