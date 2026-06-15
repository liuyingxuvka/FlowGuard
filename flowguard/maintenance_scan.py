"""Maintenance scan router for FlowGuard-managed project changes.

The scan is a thin router over existing FlowGuard capabilities. It turns
changed artifacts, skipped candidate routes, stale evidence, and explicit
maintenance signals into concrete next-route actions. It does not run tests,
refactor code, split models, or replace the owning specialist route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .evidence_fields import PASSING_EVIDENCE_GATE_STATUSES
from .export import to_jsonable
from .maintenance_obligation import (
    MaintenanceObligation,
    coerce_maintenance_obligation,
    obligation_from_maintenance_action,
)


MAINTENANCE_ARTIFACT_MODEL = "model"
MAINTENANCE_ARTIFACT_CODE = "code"
MAINTENANCE_ARTIFACT_TEST = "test"
MAINTENANCE_ARTIFACT_STRUCTURE = "structure"
MAINTENANCE_ARTIFACT_EVIDENCE = "evidence"
MAINTENANCE_ARTIFACT_GUIDANCE = "guidance"
MAINTENANCE_ARTIFACT_RELEASE = "release"

MAINTENANCE_SIGNAL_MODEL_CODE_TEST_MISMATCH = "model_code_test_mismatch"
MAINTENANCE_SIGNAL_STALE_EVIDENCE = "stale_evidence"
MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH = "reducible_branch"
MAINTENANCE_SIGNAL_PASS_THROUGH_ADAPTER = "pass_through_adapter"
MAINTENANCE_SIGNAL_DUPLICATE_VALIDATION = "duplicate_validation"
MAINTENANCE_SIGNAL_REMOVABLE_STATE_FIELD = "removable_state_field"
MAINTENANCE_SIGNAL_LARGE_MODULE = "large_module"
MAINTENANCE_SIGNAL_PUBLIC_API_SPLIT = "public_api_split"
MAINTENANCE_SIGNAL_OVERSIZED_MODEL = "oversized_model"
MAINTENANCE_SIGNAL_STALE_CHILD_MODEL = "stale_child_model_evidence"
MAINTENANCE_SIGNAL_SLOW_TESTS = "slow_tests"
MAINTENANCE_SIGNAL_PROGRESS_ONLY_TESTS = "progress_only_tests"
MAINTENANCE_SIGNAL_BROAD_VALIDATION = "broad_validation"
MAINTENANCE_SIGNAL_SKIPPED_CANDIDATE_ROUTE = "skipped_candidate_route"
MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP = "state_closure_gap"
MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP = "topology_hazard_gap"
MAINTENANCE_SIGNAL_MODEL_ANGLE_GAP = "model_angle_gap"
MAINTENANCE_SIGNAL_BUSINESS_PATH_DUPLICATE = "business_path_duplicate_gap"
MAINTENANCE_SIGNAL_BUSINESS_PATH_CONFLICT = "business_path_conflict_gap"
MAINTENANCE_SIGNAL_BUSINESS_PATH_UNPROVEN = "business_path_unproven_gap"
MAINTENANCE_SIGNAL_BUSINESS_PATH_LEGACY_DISPOSITION = "business_path_legacy_disposition_gap"

MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL = "agent_workflow_rehearsal"
MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION = "architecture_reduction"
MAINTENANCE_ROUTE_CODE_STRUCTURE_RECOMMENDATION = "code_structure_recommendation"
MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW = "development_process_flow"
MAINTENANCE_ROUTE_MODEL_MESH = "model_mesh_maintenance"
MAINTENANCE_ROUTE_MODEL_MATURATION = "model_maturation_loop"
MAINTENANCE_ROUTE_MODEL_SIMILARITY = "model_similarity_consolidation"
MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
MAINTENANCE_ROUTE_RISK_EVIDENCE_LEDGER = "risk_evidence_ledger"
MAINTENANCE_ROUTE_STRUCTURE_MESH = "structure_mesh_maintenance"
MAINTENANCE_ROUTE_TEST_MESH = "test_mesh_maintenance"

MAINTENANCE_ACTION_REQUIRED = "required"
MAINTENANCE_ACTION_SUGGESTED = "suggested"
MAINTENANCE_ACTION_OPTIONAL = "optional"

MAINTENANCE_SCAN_DECISION_CLEAR = "maintenance_scan_clear"
MAINTENANCE_SCAN_DECISION_SUGGESTED = "maintenance_scan_actions_suggested"
MAINTENANCE_SCAN_DECISION_REQUIRED = "maintenance_scan_actions_required"
MAINTENANCE_SCAN_DECISION_SCOPED = "maintenance_scan_scoped_confidence"
MAINTENANCE_SCAN_DECISION_BLOCKED = "maintenance_scan_blocked"

MAINTENANCE_SCAN_CONFIDENCE_FULL = "full"
MAINTENANCE_SCAN_CONFIDENCE_SCOPED = "scoped"
MAINTENANCE_SCAN_CONFIDENCE_BLOCKED = "blocked"

_BROAD_CLAIMS = {"done", "release", "publish", "production", "full"}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return tuple(ordered)


@dataclass(frozen=True)
class MaintenanceChangedArtifact:
    """One project artifact considered by a maintenance scan."""

    artifact_id: str
    artifact_kind: str
    path: str = ""
    changed: bool = True
    current: bool = True
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "artifact_kind", str(self.artifact_kind))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "changed", bool(self.changed))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "path": self.path,
            "changed": self.changed,
            "current": self.current,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class MaintenanceEvidence:
    """Current or prior owner-route evidence available to the scan."""

    evidence_id: str
    route_id: str
    status: str = "not_run"
    current: bool = False
    covers_artifact_ids: tuple[str, ...] = ()
    covers_signal_ids: tuple[str, ...] = ()
    result_path: str = ""
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "covers_artifact_ids", _as_tuple(self.covers_artifact_ids))
        object.__setattr__(self, "covers_signal_ids", _as_tuple(self.covers_signal_ids))
        object.__setattr__(self, "result_path", str(self.result_path))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_current_pass(self) -> bool:
        return self.current and self.status in PASSING_EVIDENCE_GATE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "route_id": self.route_id,
            "status": self.status,
            "current": self.current,
            "covers_artifact_ids": list(self.covers_artifact_ids),
            "covers_signal_ids": list(self.covers_signal_ids),
            "result_path": self.result_path,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class MaintenanceSignal:
    """One explicit maintenance signal supplied by an agent or project adapter."""

    signal_id: str
    signal_type: str
    route_id: str = ""
    strength: str = MAINTENANCE_ACTION_REQUIRED
    artifact_ids: tuple[str, ...] = ()
    required_input_kinds: tuple[str, ...] = ()
    proof_gap_codes: tuple[str, ...] = ()
    claim_effect: str = ""
    suggested_commands: tuple[str, ...] = ()
    source_obligation_ids: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", str(self.signal_id))
        object.__setattr__(self, "signal_type", str(self.signal_type))
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "strength", str(self.strength))
        object.__setattr__(self, "artifact_ids", _as_tuple(self.artifact_ids))
        object.__setattr__(self, "required_input_kinds", _as_tuple(self.required_input_kinds))
        object.__setattr__(self, "proof_gap_codes", _as_tuple(self.proof_gap_codes))
        object.__setattr__(self, "claim_effect", str(self.claim_effect))
        object.__setattr__(self, "suggested_commands", _as_tuple(self.suggested_commands))
        object.__setattr__(self, "source_obligation_ids", _as_tuple(self.source_obligation_ids))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "route_id": self.route_id,
            "strength": self.strength,
            "artifact_ids": list(self.artifact_ids),
            "required_input_kinds": list(self.required_input_kinds),
            "proof_gap_codes": list(self.proof_gap_codes),
            "claim_effect": self.claim_effect,
            "suggested_commands": list(self.suggested_commands),
            "source_obligation_ids": list(self.source_obligation_ids),
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class MaintenanceSkippedRoute:
    """Candidate FlowGuard route that was skipped during the task."""

    route_id: str
    reason: str = ""
    accepted_scope: bool = False
    consequence: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "accepted_scope", bool(self.accepted_scope))
        object.__setattr__(self, "consequence", str(self.consequence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_unresolved(self) -> bool:
        return not (self.reason and self.accepted_scope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "reason": self.reason,
            "accepted_scope": self.accepted_scope,
            "consequence": self.consequence,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class MaintenanceAction:
    """One maintenance route action produced by the scan."""

    action_id: str
    route_id: str
    strength: str
    reason_code: str
    message: str
    artifact_ids: tuple[str, ...] = ()
    signal_ids: tuple[str, ...] = ()
    owner_evidence_ids: tuple[str, ...] = ()
    required_input_kinds: tuple[str, ...] = ()
    proof_gap_codes: tuple[str, ...] = ()
    claim_effect: str = ""
    suggested_commands: tuple[str, ...] = ()
    source_obligation_ids: tuple[str, ...] = ()
    resolved: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", str(self.action_id))
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "strength", str(self.strength))
        object.__setattr__(self, "reason_code", str(self.reason_code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "artifact_ids", _as_tuple(self.artifact_ids))
        object.__setattr__(self, "signal_ids", _as_tuple(self.signal_ids))
        object.__setattr__(self, "owner_evidence_ids", _as_tuple(self.owner_evidence_ids))
        object.__setattr__(self, "required_input_kinds", _as_tuple(self.required_input_kinds))
        object.__setattr__(self, "proof_gap_codes", _as_tuple(self.proof_gap_codes))
        object.__setattr__(self, "claim_effect", str(self.claim_effect))
        object.__setattr__(self, "suggested_commands", _as_tuple(self.suggested_commands))
        object.__setattr__(self, "source_obligation_ids", _as_tuple(self.source_obligation_ids))
        object.__setattr__(self, "resolved", bool(self.resolved))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_open_required(self) -> bool:
        return self.strength == MAINTENANCE_ACTION_REQUIRED and not self.resolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "route_id": self.route_id,
            "strength": self.strength,
            "reason_code": self.reason_code,
            "message": self.message,
            "artifact_ids": list(self.artifact_ids),
            "signal_ids": list(self.signal_ids),
            "owner_evidence_ids": list(self.owner_evidence_ids),
            "required_input_kinds": list(self.required_input_kinds),
            "proof_gap_codes": list(self.proof_gap_codes),
            "claim_effect": self.claim_effect,
            "suggested_commands": list(self.suggested_commands),
            "source_obligation_ids": list(self.source_obligation_ids),
            "resolved": self.resolved,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class MaintenanceScanPlan:
    """Inputs for a FlowGuard maintenance scan."""

    plan_id: str
    changed_artifacts: tuple[MaintenanceChangedArtifact, ...] = ()
    evidence: tuple[MaintenanceEvidence, ...] = ()
    signals: tuple[MaintenanceSignal, ...] = ()
    skipped_routes: tuple[MaintenanceSkippedRoute, ...] = ()
    prior_obligations: tuple[MaintenanceObligation, ...] = ()
    claim_scope: str = "bounded"
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "changed_artifacts", tuple(self.changed_artifacts))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "skipped_routes", tuple(self.skipped_routes))
        object.__setattr__(
            self,
            "prior_obligations",
            tuple(coerce_maintenance_obligation(item) for item in self.prior_obligations),
        )
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "allow_scoped_confidence", bool(self.allow_scoped_confidence))

    def broad_claim(self) -> bool:
        return self.claim_scope in _BROAD_CLAIMS

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "changed_artifacts": [artifact.to_dict() for artifact in self.changed_artifacts],
            "evidence": [item.to_dict() for item in self.evidence],
            "signals": [signal.to_dict() for signal in self.signals],
            "skipped_routes": [route.to_dict() for route in self.skipped_routes],
            "prior_obligations": [obligation.to_dict() for obligation in self.prior_obligations],
            "claim_scope": self.claim_scope,
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class MaintenanceScanReport:
    """Structured maintenance scan result."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    actions: tuple[MaintenanceAction, ...] = ()
    unresolved_required_action_ids: tuple[str, ...] = ()
    reopened_obligation_ids: tuple[str, ...] = ()
    visible_obligation_ids: tuple[str, ...] = ()
    obligations: tuple[MaintenanceObligation, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(
            self,
            "unresolved_required_action_ids",
            _as_tuple(self.unresolved_required_action_ids),
        )
        object.__setattr__(self, "reopened_obligation_ids", _as_tuple(self.reopened_obligation_ids))
        object.__setattr__(self, "visible_obligation_ids", _as_tuple(self.visible_obligation_ids))
        object.__setattr__(
            self,
            "obligations",
            tuple(coerce_maintenance_obligation(item) for item in self.obligations),
        )
        object.__setattr__(self, "summary", str(self.summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "actions": [action.to_dict() for action in self.actions],
            "unresolved_required_action_ids": list(self.unresolved_required_action_ids),
            "reopened_obligation_ids": list(self.reopened_obligation_ids),
            "visible_obligation_ids": list(self.visible_obligation_ids),
            "obligations": [obligation.to_dict() for obligation in self.obligations],
            "summary": self.summary,
        }

    def format_text(self) -> str:
        lines = [
            "=== flowguard maintenance scan ===",
            f"plan_id: {self.plan_id}",
            f"status: {'pass' if self.ok else 'needs_maintenance'}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"summary: {self.summary}",
        ]
        if self.actions:
            lines.append("actions:")
            for action in self.actions:
                resolved = "resolved" if action.resolved else "open"
                lines.append(
                    f"- {action.action_id}: {action.strength} {action.route_id} "
                    f"({action.reason_code}, {resolved})"
                )
                if action.message:
                    lines.append(f"  message: {action.message}")
        if self.unresolved_required_action_ids:
            lines.append(
                "unresolved_required_action_ids: "
                + ", ".join(self.unresolved_required_action_ids)
            )
        if self.reopened_obligation_ids:
            lines.append("reopened_obligation_ids: " + ", ".join(self.reopened_obligation_ids))
        return "\n".join(lines)


_SIGNAL_ROUTE_MAP = {
    MAINTENANCE_SIGNAL_MODEL_CODE_TEST_MISMATCH: MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
    MAINTENANCE_SIGNAL_STALE_EVIDENCE: MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW,
    MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH: MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION,
    MAINTENANCE_SIGNAL_PASS_THROUGH_ADAPTER: MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION,
    MAINTENANCE_SIGNAL_DUPLICATE_VALIDATION: MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION,
    MAINTENANCE_SIGNAL_REMOVABLE_STATE_FIELD: MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION,
    MAINTENANCE_SIGNAL_LARGE_MODULE: MAINTENANCE_ROUTE_STRUCTURE_MESH,
    MAINTENANCE_SIGNAL_PUBLIC_API_SPLIT: MAINTENANCE_ROUTE_STRUCTURE_MESH,
    MAINTENANCE_SIGNAL_OVERSIZED_MODEL: MAINTENANCE_ROUTE_MODEL_MESH,
    MAINTENANCE_SIGNAL_STALE_CHILD_MODEL: MAINTENANCE_ROUTE_MODEL_MESH,
    MAINTENANCE_SIGNAL_SLOW_TESTS: MAINTENANCE_ROUTE_TEST_MESH,
    MAINTENANCE_SIGNAL_PROGRESS_ONLY_TESTS: MAINTENANCE_ROUTE_TEST_MESH,
    MAINTENANCE_SIGNAL_BROAD_VALIDATION: MAINTENANCE_ROUTE_TEST_MESH,
    MAINTENANCE_SIGNAL_SKIPPED_CANDIDATE_ROUTE: MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL,
    MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP: MAINTENANCE_ROUTE_MODEL_MATURATION,
    MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP: MAINTENANCE_ROUTE_MODEL_MATURATION,
    MAINTENANCE_SIGNAL_MODEL_ANGLE_GAP: MAINTENANCE_ROUTE_MODEL_MATURATION,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_DUPLICATE: MAINTENANCE_ROUTE_MODEL_SIMILARITY,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_CONFLICT: MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_UNPROVEN: MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_LEGACY_DISPOSITION: MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION,
}

_SIGNAL_DEFAULT_STRENGTH = {
    MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH: MAINTENANCE_ACTION_SUGGESTED,
    MAINTENANCE_SIGNAL_PASS_THROUGH_ADAPTER: MAINTENANCE_ACTION_SUGGESTED,
    MAINTENANCE_SIGNAL_DUPLICATE_VALIDATION: MAINTENANCE_ACTION_SUGGESTED,
    MAINTENANCE_SIGNAL_REMOVABLE_STATE_FIELD: MAINTENANCE_ACTION_SUGGESTED,
    MAINTENANCE_SIGNAL_BUSINESS_PATH_DUPLICATE: MAINTENANCE_ACTION_SUGGESTED,
}


def _current_evidence_by_route(plan: MaintenanceScanPlan) -> dict[str, tuple[str, ...]]:
    by_route: dict[str, list[str]] = {}
    for item in plan.evidence:
        if item.is_current_pass():
            by_route.setdefault(item.route_id, []).append(item.evidence_id)
    return {route: tuple(ids) for route, ids in by_route.items()}


def _make_action(
    *,
    route_id: str,
    strength: str,
    reason_code: str,
    message: str,
    artifact_ids: Sequence[str] = (),
    signal_ids: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    required_input_kinds: Sequence[str] = (),
    proof_gap_codes: Sequence[str] = (),
    claim_effect: str = "",
    suggested_commands: Sequence[str] = (),
    source_obligation_ids: Sequence[str] = (),
) -> MaintenanceAction:
    action_id = f"{route_id}:{reason_code}"
    return MaintenanceAction(
        action_id=action_id,
        route_id=route_id,
        strength=strength,
        reason_code=reason_code,
        message=message,
        artifact_ids=_unique(artifact_ids),
        signal_ids=_unique(signal_ids),
        owner_evidence_ids=_unique(evidence_ids),
        required_input_kinds=_unique(required_input_kinds),
        proof_gap_codes=_unique(proof_gap_codes),
        claim_effect=claim_effect,
        suggested_commands=_unique(suggested_commands),
        source_obligation_ids=_unique(source_obligation_ids),
        resolved=bool(evidence_ids),
    )


def _action_from_obligation(
    obligation: MaintenanceObligation,
    *,
    evidence_ids: Sequence[str] = (),
) -> MaintenanceAction:
    reason = f"open_obligation:{obligation.reason_code or obligation.obligation_id}"
    return _make_action(
        route_id=obligation.owner_route,
        strength=obligation.strength,
        reason_code=reason,
        message=obligation.message
        or f"Open maintenance obligation {obligation.obligation_id} requires {obligation.owner_route}.",
        artifact_ids=obligation.artifact_ids,
        signal_ids=(obligation.obligation_id,),
        evidence_ids=evidence_ids,
        required_input_kinds=obligation.required_input_kinds,
        proof_gap_codes=obligation.proof_gap_codes,
        claim_effect=obligation.claim_effect,
        suggested_commands=obligation.suggested_commands,
        source_obligation_ids=(obligation.obligation_id,),
    )


def _merge_actions(actions: Sequence[MaintenanceAction]) -> tuple[MaintenanceAction, ...]:
    by_id: dict[str, MaintenanceAction] = {}
    for action in actions:
        existing = by_id.get(action.action_id)
        if existing is None:
            by_id[action.action_id] = action
            continue
        strength = (
            MAINTENANCE_ACTION_REQUIRED
            if MAINTENANCE_ACTION_REQUIRED in {existing.strength, action.strength}
            else existing.strength
        )
        by_id[action.action_id] = MaintenanceAction(
            action_id=existing.action_id,
            route_id=existing.route_id,
            strength=strength,
            reason_code=existing.reason_code,
            message=existing.message,
            artifact_ids=_unique(existing.artifact_ids + action.artifact_ids),
            signal_ids=_unique(existing.signal_ids + action.signal_ids),
            owner_evidence_ids=_unique(existing.owner_evidence_ids + action.owner_evidence_ids),
            required_input_kinds=_unique(existing.required_input_kinds + action.required_input_kinds),
            proof_gap_codes=_unique(existing.proof_gap_codes + action.proof_gap_codes),
            claim_effect=existing.claim_effect or action.claim_effect,
            suggested_commands=_unique(existing.suggested_commands + action.suggested_commands),
            source_obligation_ids=_unique(existing.source_obligation_ids + action.source_obligation_ids),
            resolved=existing.resolved or action.resolved,
            metadata={**existing.metadata, **action.metadata},
        )
    return tuple(by_id.values())


def review_maintenance_scan(plan: MaintenanceScanPlan) -> MaintenanceScanReport:
    """Review maintenance signals and route open work to FlowGuard specialists."""

    evidence_by_route = _current_evidence_by_route(plan)
    actions: list[MaintenanceAction] = []
    reopened_obligation_ids: list[str] = []
    visible_obligation_ids: list[str] = []
    changed_by_kind: dict[str, list[MaintenanceChangedArtifact]] = {}
    for artifact in plan.changed_artifacts:
        if artifact.changed:
            changed_by_kind.setdefault(artifact.artifact_kind, []).append(artifact)
    changed_artifacts = tuple(
        artifact
        for artifacts in changed_by_kind.values()
        for artifact in artifacts
    )

    model_artifacts = changed_by_kind.get(MAINTENANCE_ARTIFACT_MODEL, [])
    code_or_test_artifacts = changed_by_kind.get(MAINTENANCE_ARTIFACT_CODE, []) + changed_by_kind.get(
        MAINTENANCE_ARTIFACT_TEST,
        [],
    )
    if model_artifacts and code_or_test_artifacts:
        artifacts = tuple(artifact.artifact_id for artifact in model_artifacts + code_or_test_artifacts)
        actions.append(
            _make_action(
                route_id=MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT,
                strength=MAINTENANCE_ACTION_REQUIRED,
                reason_code="changed_model_code_test_boundary",
                message="Changed model and code/test artifacts need owner-route model/code/test alignment.",
                artifact_ids=artifacts,
                evidence_ids=evidence_by_route.get(MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT, ()),
            )
        )

    stale_kinds = {
        MAINTENANCE_ARTIFACT_EVIDENCE,
        MAINTENANCE_ARTIFACT_GUIDANCE,
        MAINTENANCE_ARTIFACT_RELEASE,
    }
    stale_artifacts = [
        artifact
        for kind in stale_kinds
        for artifact in changed_by_kind.get(kind, ())
        if not artifact.current or plan.broad_claim()
    ]
    if stale_artifacts:
        actions.append(
            _make_action(
                route_id=MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW,
                strength=MAINTENANCE_ACTION_REQUIRED,
                reason_code="changed_evidence_or_guidance",
                message="Changed evidence, guidance, or release artifacts can stale earlier validation.",
                artifact_ids=tuple(artifact.artifact_id for artifact in stale_artifacts),
                evidence_ids=evidence_by_route.get(MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW, ()),
            )
        )

    for signal in plan.signals:
        route_id = signal.route_id or _SIGNAL_ROUTE_MAP.get(signal.signal_type, MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW)
        strength = signal.strength or _SIGNAL_DEFAULT_STRENGTH.get(signal.signal_type, MAINTENANCE_ACTION_REQUIRED)
        if signal.signal_type in _SIGNAL_DEFAULT_STRENGTH and signal.strength == MAINTENANCE_ACTION_REQUIRED:
            strength = _SIGNAL_DEFAULT_STRENGTH[signal.signal_type]
        actions.append(
            _make_action(
                route_id=route_id,
                strength=strength,
                reason_code=signal.signal_type,
                message=signal.description or f"Maintenance signal requires {route_id}.",
                artifact_ids=signal.artifact_ids,
                signal_ids=(signal.signal_id,),
                evidence_ids=evidence_by_route.get(route_id, ()),
                required_input_kinds=signal.required_input_kinds,
                proof_gap_codes=signal.proof_gap_codes,
                claim_effect=signal.claim_effect,
                suggested_commands=signal.suggested_commands,
                source_obligation_ids=signal.source_obligation_ids,
            )
        )

    for skipped in plan.skipped_routes:
        if skipped.is_unresolved():
            actions.append(
                _make_action(
                    route_id=MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL,
                    strength=MAINTENANCE_ACTION_REQUIRED,
                    reason_code=f"skipped:{skipped.route_id}",
                    message="Skipped candidate route lacks accepted scope and consequence evidence.",
                    signal_ids=(skipped.route_id,),
                    evidence_ids=evidence_by_route.get(MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL, ()),
                )
            )

    for obligation in plan.prior_obligations:
        if not obligation.is_active():
            continue
        visible_obligation_ids.append(obligation.obligation_id)
        if not obligation.has_anchor() or not obligation.touches_any(changed_artifacts):
            continue
        reopened_obligation_ids.append(obligation.obligation_id)
        actions.append(
            _action_from_obligation(
                obligation,
                evidence_ids=evidence_by_route.get(obligation.owner_route, ()),
            )
        )

    merged_actions = _merge_actions(actions)
    unresolved = tuple(action.action_id for action in merged_actions if action.is_open_required())
    has_required = any(action.strength == MAINTENANCE_ACTION_REQUIRED for action in merged_actions)
    has_suggested = any(action.strength == MAINTENANCE_ACTION_SUGGESTED for action in merged_actions)

    if unresolved and plan.broad_claim():
        decision = (
            MAINTENANCE_SCAN_DECISION_SCOPED
            if plan.allow_scoped_confidence
            else MAINTENANCE_SCAN_DECISION_BLOCKED
        )
        confidence = (
            MAINTENANCE_SCAN_CONFIDENCE_SCOPED
            if plan.allow_scoped_confidence
            else MAINTENANCE_SCAN_CONFIDENCE_BLOCKED
        )
        ok = plan.allow_scoped_confidence
        summary = "Required maintenance actions remain before broad FlowGuard confidence."
    elif unresolved:
        decision = MAINTENANCE_SCAN_DECISION_REQUIRED
        confidence = MAINTENANCE_SCAN_CONFIDENCE_BLOCKED
        ok = False
        summary = "Required maintenance actions remain open."
    elif has_required:
        decision = MAINTENANCE_SCAN_DECISION_REQUIRED
        confidence = MAINTENANCE_SCAN_CONFIDENCE_FULL
        ok = True
        summary = "Required maintenance actions have current owner-route evidence."
    elif has_suggested:
        decision = MAINTENANCE_SCAN_DECISION_SUGGESTED
        confidence = MAINTENANCE_SCAN_CONFIDENCE_SCOPED
        ok = True
        summary = "Suggested maintenance actions are visible; scan itself is not validation."
    else:
        decision = MAINTENANCE_SCAN_DECISION_CLEAR
        confidence = MAINTENANCE_SCAN_CONFIDENCE_FULL
        ok = True
        summary = "No maintenance route signals found; scan itself is not model/test/replay validation."

    return MaintenanceScanReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        actions=merged_actions,
        unresolved_required_action_ids=unresolved,
        reopened_obligation_ids=_unique(reopened_obligation_ids),
        visible_obligation_ids=_unique(visible_obligation_ids),
        obligations=tuple(obligation_from_maintenance_action(action) for action in merged_actions),
        summary=summary,
    )


def _signal_strength_for_ledger_entry(entry: Any) -> str:
    severity = str(getattr(entry, "severity", "") or "")
    if severity in {"failure", "blocker"}:
        return MAINTENANCE_ACTION_REQUIRED
    return MAINTENANCE_ACTION_SUGGESTED


def maintenance_scan_plan_from_summary_report(
    report: Any,
    *,
    plan_id: str = "",
    changed_artifacts: Sequence[MaintenanceChangedArtifact] = (),
    evidence: Sequence[MaintenanceEvidence] = (),
    skipped_routes: Sequence[MaintenanceSkippedRoute] = (),
    prior_obligations: Sequence[MaintenanceObligation] = (),
    claim_scope: str = "bounded",
    allow_scoped_confidence: bool = True,
) -> MaintenanceScanPlan:
    """Build a maintenance scan plan from a FlowGuard summary report.

    The bridge preserves MaintenanceScan as the router. It does not run owner
    routes or validate the summary's gaps.
    """

    ledger = getattr(report, "finding_ledger", None)
    entries = tuple(getattr(ledger, "entries", ()) or ())
    report_obligations = tuple(
        getattr(getattr(report, "maintenance_obligations", None), "obligations", ()) or ()
    )
    signals: list[MaintenanceSignal] = []
    for index, entry in enumerate(entries, start=1):
        if str(getattr(entry, "severity", "") or "") == "info":
            continue
        route_id = str(getattr(entry, "owner_route", "") or "") or MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW
        signal_id = f"summary:{getattr(entry, 'section_name', 'section')}:{index}"
        signals.append(
            MaintenanceSignal(
                signal_id,
                str(getattr(entry, "category", "") or "summary_gap"),
                route_id=route_id,
                strength=_signal_strength_for_ledger_entry(entry),
                required_input_kinds=tuple(getattr(entry, "required_input_kinds", ()) or ()),
                proof_gap_codes=tuple(getattr(entry, "proof_gap_codes", ()) or ()),
                claim_effect=str(getattr(entry, "claim_effect", "") or ""),
                suggested_commands=tuple(getattr(entry, "suggested_commands", ()) or ()),
                source_obligation_ids=tuple(
                    obligation.obligation_id
                    for obligation in report_obligations
                    if obligation.source_route == getattr(entry, "section_name", "")
                ),
                description=str(getattr(entry, "message", "") or ""),
                metadata={"summary_ledger_entry": getattr(entry, "to_dict", lambda: repr(entry))()},
            )
        )
    return MaintenanceScanPlan(
        plan_id or str(getattr(report, "summary", "") or "summary-report"),
        changed_artifacts=tuple(changed_artifacts),
        evidence=tuple(evidence),
        signals=tuple(signals),
        skipped_routes=tuple(skipped_routes),
        prior_obligations=tuple(prior_obligations) + report_obligations,
        claim_scope=claim_scope,
        allow_scoped_confidence=allow_scoped_confidence,
    )


__all__ = [
    "MAINTENANCE_ACTION_OPTIONAL",
    "MAINTENANCE_ACTION_REQUIRED",
    "MAINTENANCE_ACTION_SUGGESTED",
    "MAINTENANCE_ARTIFACT_CODE",
    "MAINTENANCE_ARTIFACT_EVIDENCE",
    "MAINTENANCE_ARTIFACT_GUIDANCE",
    "MAINTENANCE_ARTIFACT_MODEL",
    "MAINTENANCE_ARTIFACT_RELEASE",
    "MAINTENANCE_ARTIFACT_STRUCTURE",
    "MAINTENANCE_ARTIFACT_TEST",
    "MAINTENANCE_ROUTE_AGENT_WORKFLOW_REHEARSAL",
    "MAINTENANCE_ROUTE_ARCHITECTURE_REDUCTION",
    "MAINTENANCE_ROUTE_CODE_STRUCTURE_RECOMMENDATION",
    "MAINTENANCE_ROUTE_DEVELOPMENT_PROCESS_FLOW",
    "MAINTENANCE_ROUTE_MODEL_MESH",
    "MAINTENANCE_ROUTE_MODEL_MATURATION",
    "MAINTENANCE_ROUTE_MODEL_SIMILARITY",
    "MAINTENANCE_ROUTE_MODEL_TEST_ALIGNMENT",
    "MAINTENANCE_ROUTE_RISK_EVIDENCE_LEDGER",
    "MAINTENANCE_ROUTE_STRUCTURE_MESH",
    "MAINTENANCE_ROUTE_TEST_MESH",
    "MAINTENANCE_SCAN_CONFIDENCE_BLOCKED",
    "MAINTENANCE_SCAN_CONFIDENCE_FULL",
    "MAINTENANCE_SCAN_CONFIDENCE_SCOPED",
    "MAINTENANCE_SCAN_DECISION_BLOCKED",
    "MAINTENANCE_SCAN_DECISION_CLEAR",
    "MAINTENANCE_SCAN_DECISION_REQUIRED",
    "MAINTENANCE_SCAN_DECISION_SCOPED",
    "MAINTENANCE_SCAN_DECISION_SUGGESTED",
    "MAINTENANCE_SIGNAL_BROAD_VALIDATION",
    "MAINTENANCE_SIGNAL_BUSINESS_PATH_CONFLICT",
    "MAINTENANCE_SIGNAL_BUSINESS_PATH_DUPLICATE",
    "MAINTENANCE_SIGNAL_BUSINESS_PATH_LEGACY_DISPOSITION",
    "MAINTENANCE_SIGNAL_BUSINESS_PATH_UNPROVEN",
    "MAINTENANCE_SIGNAL_DUPLICATE_VALIDATION",
    "MAINTENANCE_SIGNAL_LARGE_MODULE",
    "MAINTENANCE_SIGNAL_MODEL_CODE_TEST_MISMATCH",
    "MAINTENANCE_SIGNAL_MODEL_ANGLE_GAP",
    "MAINTENANCE_SIGNAL_OVERSIZED_MODEL",
    "MAINTENANCE_SIGNAL_PASS_THROUGH_ADAPTER",
    "MAINTENANCE_SIGNAL_PROGRESS_ONLY_TESTS",
    "MAINTENANCE_SIGNAL_PUBLIC_API_SPLIT",
    "MAINTENANCE_SIGNAL_REDUCIBLE_BRANCH",
    "MAINTENANCE_SIGNAL_REMOVABLE_STATE_FIELD",
    "MAINTENANCE_SIGNAL_SKIPPED_CANDIDATE_ROUTE",
    "MAINTENANCE_SIGNAL_SLOW_TESTS",
    "MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP",
    "MAINTENANCE_SIGNAL_STALE_CHILD_MODEL",
    "MAINTENANCE_SIGNAL_STALE_EVIDENCE",
    "MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP",
    "MaintenanceAction",
    "MaintenanceChangedArtifact",
    "MaintenanceEvidence",
    "MaintenanceScanPlan",
    "MaintenanceScanReport",
    "MaintenanceSignal",
    "MaintenanceSkippedRoute",
    "maintenance_scan_plan_from_summary_report",
    "review_maintenance_scan",
]
