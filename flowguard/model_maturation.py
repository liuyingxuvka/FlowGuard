"""Model maturation loop review helpers.

This helper turns post-code, post-test, mesh, freshness, or model-miss signals
into explicit model-upgrade actions before a broad FlowGuard claim is made.
It does not replace the owning satellite routes; it records when their evidence
means the model itself is too coarse, stale, or only supports scoped confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .maintenance_obligation import (
    MaintenanceObligation,
    coerce_maintenance_obligation,
    obligations_from_maturation_findings,
)


MODEL_MATURATION_DECISION_CLOSED_FOR_TASK = "model_maturation_closed_for_task"
MODEL_MATURATION_DECISION_PROGRESS_STALLED = "model_maturation_progress_stalled"
MODEL_MATURATION_DECISION_ITERATION_LIMIT = "model_maturation_iteration_limit"
MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED = "model_maturation_external_input_required"
MODEL_MATURATION_DECISION_SCOPE_EXCLUDED = "model_maturation_scope_excluded"
# Kept as the public name used by older callers.  A green result now means
# closed for the declared task, not that a model has a permanent maturity
# level.
MODEL_MATURATION_DECISION_CURRENT = MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
MODEL_MATURATION_DECISION_UPGRADE_REQUIRED = "model_maturation_upgrade_required"
MODEL_MATURATION_DECISION_SCOPED = "model_maturation_scoped_claim"
MODEL_MATURATION_DECISION_BLOCKED = "model_maturation_blocked"

MODEL_MATURATION_CONFIDENCE_FULL = "full"
MODEL_MATURATION_CONFIDENCE_SCOPED = "scoped"
MODEL_MATURATION_CONFIDENCE_BLOCKED = "blocked"

MODEL_MATURATION_RESOLUTION_MODEL_EDIT = "model_edit"
MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION = "evidence_acquisition"
MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED = "external_input_required"
MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED = "scope_excluded"
MODEL_MATURATION_RESOLUTION_CLASSES = (
    MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
    MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
    MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
)

MATURITY_ACTION_NO_CHANGE = "no_model_change_needed"
MATURITY_ACTION_ADD_STATE_FIELD = "add_state_field"
MATURITY_ACTION_ADD_TRANSITION_CASE = "add_transition_case"
MATURITY_ACTION_ADD_INVARIANT = "add_invariant"
MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO = "add_same_class_scenario"
MATURITY_ACTION_SPLIT_CHILD_MODEL = "split_child_model"
MATURITY_ACTION_REATTACH_PARENT_MODEL = "reattach_parent_model"
MATURITY_ACTION_REFRESH_EVIDENCE = "refresh_evidence"
MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION = "add_code_boundary_observation"
MATURITY_ACTION_ADD_MODEL_OBLIGATION = "add_model_obligation"
MATURITY_ACTION_DOWNGRADE_CLAIM = "downgrade_claim"

MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE = "state_too_coarse"
MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING = "input_branch_missing"
MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING = "boundary_missing"
MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK = "invariant_too_weak"
MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING = "same_class_missing"
MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING = "child_reattachment_missing"
MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED = "child_boundary_changed"
MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH = "duplicate_primary_edge_path"
MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL = "oversized_model"
MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION = "missing_model_obligation"
MODEL_MATURATION_SIGNAL_STALE_EVIDENCE = "stale_evidence"
MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE = "progress_only_evidence"
MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH = "code_boundary_mismatch"
MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION = "missing_code_boundary_observation"

MODEL_MATURATION_SIGNAL_TYPES = (
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
    MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING,
    MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING,
    MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK,
    MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
    MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING,
    MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED,
    MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH,
    MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL,
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
    MODEL_MATURATION_SIGNAL_STALE_EVIDENCE,
    MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE,
    MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH,
    MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION,
)

MODEL_MATURATION_TERMINAL_REASONS = (
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_DECISION_PROGRESS_STALLED,
    MODEL_MATURATION_DECISION_ITERATION_LIMIT,
    MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_DECISION_SCOPE_EXCLUDED,
)

MODEL_MATURATION_ACTIONS_BY_SIGNAL = {
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE: (MATURITY_ACTION_ADD_STATE_FIELD,),
    MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING: (MATURITY_ACTION_ADD_TRANSITION_CASE,),
    MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING: (
        MATURITY_ACTION_ADD_TRANSITION_CASE,
        MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION,
    ),
    MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK: (MATURITY_ACTION_ADD_INVARIANT,),
    MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING: (MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO,),
    MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING: (MATURITY_ACTION_REATTACH_PARENT_MODEL,),
    MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED: (MATURITY_ACTION_REATTACH_PARENT_MODEL,),
    MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH: (MATURITY_ACTION_SPLIT_CHILD_MODEL,),
    MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL: (MATURITY_ACTION_SPLIT_CHILD_MODEL,),
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION: (MATURITY_ACTION_ADD_MODEL_OBLIGATION,),
    MODEL_MATURATION_SIGNAL_STALE_EVIDENCE: (MATURITY_ACTION_REFRESH_EVIDENCE,),
    MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE: (MATURITY_ACTION_REFRESH_EVIDENCE,),
    MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH: (
        MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION,
        MATURITY_ACTION_ADD_MODEL_OBLIGATION,
    ),
    MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION: (
        MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION,
    ),
}


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


def _stable_fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelMaturationSignal:
    """One route signal that may require the model to be upgraded."""

    signal_id: str
    signal_type: str
    source_route: str = ""
    model_id: str = ""
    risk_id: str = ""
    evidence_id: str = ""
    description: str = ""
    in_scope: bool = True
    required: bool = True
    resolved: bool = False
    current: bool = True
    suggested_actions: tuple[str, ...] = ()
    coverage_id: str = ""
    resolution_class: str = ""
    prediction: str = ""
    falsifier: str = ""
    evidence_fingerprint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", str(self.signal_id))
        object.__setattr__(self, "signal_type", str(self.signal_type))
        object.__setattr__(self, "source_route", str(self.source_route))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "resolved", bool(self.resolved))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "suggested_actions", _as_tuple(self.suggested_actions))
        object.__setattr__(self, "coverage_id", str(self.coverage_id))
        object.__setattr__(self, "resolution_class", str(self.resolution_class))
        object.__setattr__(self, "prediction", str(self.prediction))
        object.__setattr__(self, "falsifier", str(self.falsifier))
        object.__setattr__(self, "evidence_fingerprint", str(self.evidence_fingerprint))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_open(self) -> bool:
        return self.in_scope and self.required and not self.resolved

    def actions(self) -> tuple[str, ...]:
        if self.suggested_actions:
            return self.suggested_actions
        return MODEL_MATURATION_ACTIONS_BY_SIGNAL.get(
            self.signal_type,
            (MATURITY_ACTION_DOWNGRADE_CLAIM,),
        )

    def resolution(self) -> str:
        value = self.resolution_class or str(self.metadata.get("resolution_class", ""))
        return value if value in MODEL_MATURATION_RESOLUTION_CLASSES else MODEL_MATURATION_RESOLUTION_MODEL_EDIT

    def gap_fingerprint(self) -> str:
        return _stable_fingerprint(
            {
                "signal_id": self.signal_id,
                "signal_type": self.signal_type,
                "coverage_id": self.coverage_id,
                "description": self.description,
                "resolution_class": self.resolution(),
                "prediction": self.prediction,
                "falsifier": self.falsifier,
                "evidence_fingerprint": self.evidence_fingerprint,
                "current": self.current,
            }
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelMaturationSignal":
        return cls(
            signal_id=str(value.get("signal_id", "")),
            signal_type=str(value.get("signal_type", "")),
            source_route=str(value.get("source_route", "")),
            model_id=str(value.get("model_id", "")),
            risk_id=str(value.get("risk_id", "")),
            evidence_id=str(value.get("evidence_id", "")),
            description=str(value.get("description", "")),
            in_scope=bool(value.get("in_scope", True)),
            required=bool(value.get("required", True)),
            resolved=bool(value.get("resolved", False)),
            current=bool(value.get("current", True)),
            suggested_actions=tuple(value.get("suggested_actions", ())),
            coverage_id=str(value.get("coverage_id", "")),
            resolution_class=str(value.get("resolution_class", "")),
            prediction=str(value.get("prediction", "")),
            falsifier=str(value.get("falsifier", "")),
            evidence_fingerprint=str(value.get("evidence_fingerprint", "")),
            metadata=value.get("metadata", {}) if isinstance(value.get("metadata", {}), Mapping) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source_route": self.source_route,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "evidence_id": self.evidence_id,
            "description": self.description,
            "in_scope": self.in_scope,
            "required": self.required,
            "resolved": self.resolved,
            "current": self.current,
            "suggested_actions": list(self.suggested_actions),
            "coverage_id": self.coverage_id,
            "resolution_class": self.resolution_class or self.resolution(),
            "prediction": self.prediction,
            "falsifier": self.falsifier,
            "evidence_fingerprint": self.evidence_fingerprint,
            "gap_fingerprint": self.gap_fingerprint(),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelMaturationIteration:
    """Immutable evidence of one model-review iteration."""

    iteration_id: str
    plan_id: str
    iteration: int
    model_fingerprint: str
    coverage_fingerprint: str
    input_fingerprint: str
    open_gap_fingerprints: tuple[str, ...] = ()
    resolved_gap_fingerprints: tuple[str, ...] = ()
    progressed: bool = False
    terminal_reason: str = ""
    next_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "iteration_id", str(self.iteration_id))
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "iteration", int(self.iteration))
        object.__setattr__(self, "model_fingerprint", str(self.model_fingerprint))
        object.__setattr__(self, "coverage_fingerprint", str(self.coverage_fingerprint))
        object.__setattr__(self, "input_fingerprint", str(self.input_fingerprint))
        object.__setattr__(self, "open_gap_fingerprints", _as_tuple(self.open_gap_fingerprints))
        object.__setattr__(self, "resolved_gap_fingerprints", _as_tuple(self.resolved_gap_fingerprints))
        object.__setattr__(self, "progressed", bool(self.progressed))
        object.__setattr__(self, "terminal_reason", str(self.terminal_reason))
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration_id": self.iteration_id,
            "plan_id": self.plan_id,
            "iteration": self.iteration,
            "model_fingerprint": self.model_fingerprint,
            "coverage_fingerprint": self.coverage_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "resolved_gap_fingerprints": list(self.resolved_gap_fingerprints),
            "progressed": self.progressed,
            "terminal_reason": self.terminal_reason,
            "next_actions": list(self.next_actions),
        }


@dataclass(frozen=True)
class ModelMaturationSession:
    """A sequence of immutable iterations for one task-local model review."""

    session_id: str
    task_id: str
    iterations: tuple[ModelMaturationIteration, ...] = ()
    terminal_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", str(self.session_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "iterations", tuple(self.iterations))
        object.__setattr__(self, "terminal_reason", str(self.terminal_reason))

    @property
    def closed(self) -> bool:
        return self.terminal_reason == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "iterations": [item.to_dict() for item in self.iterations],
            "terminal_reason": self.terminal_reason,
            "closed": self.closed,
        }


@dataclass(frozen=True)
class ModelMaturationFinding:
    """One model maturation loop diagnostic."""

    code: str
    message: str
    severity: str = "blocker"
    signal_id: str = ""
    model_id: str = ""
    risk_id: str = ""
    action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "signal_id", str(self.signal_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "signal_id": self.signal_id,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "action": self.action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelMaturationPlan:
    """Inputs for a model maturation review."""

    plan_id: str
    model_id: str = ""
    risk_id: str = ""
    signals: tuple[ModelMaturationSignal, ...] = ()
    claim_scope: str = "bounded"
    require_full_closure: bool = False
    allow_scoped_claim: bool = True
    task_id: str = ""
    coverage_ids: tuple[str, ...] = ()
    iteration: int = 0
    max_iterations: int = 8
    prior_gap_fingerprints: tuple[str, ...] = ()
    model_fingerprint: str = ""
    evidence_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "require_full_closure", bool(self.require_full_closure))
        object.__setattr__(self, "allow_scoped_claim", bool(self.allow_scoped_claim))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "coverage_ids", _as_tuple(self.coverage_ids))
        object.__setattr__(self, "iteration", max(0, int(self.iteration)))
        object.__setattr__(self, "max_iterations", max(1, int(self.max_iterations)))
        object.__setattr__(self, "prior_gap_fingerprints", _as_tuple(self.prior_gap_fingerprints))
        object.__setattr__(self, "model_fingerprint", str(self.model_fingerprint))
        object.__setattr__(self, "evidence_fingerprint", str(self.evidence_fingerprint))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelMaturationPlan":
        signals = value.get("signals", ())
        return cls(
            plan_id=str(value.get("plan_id", "")),
            model_id=str(value.get("model_id", "")),
            risk_id=str(value.get("risk_id", "")),
            signals=tuple(ModelMaturationSignal.from_dict(item) for item in signals if isinstance(item, Mapping)),
            claim_scope=str(value.get("claim_scope", "bounded")),
            require_full_closure=bool(value.get("require_full_closure", False)),
            allow_scoped_claim=bool(value.get("allow_scoped_claim", True)),
            task_id=str(value.get("task_id", "")),
            coverage_ids=tuple(value.get("coverage_ids", ())),
            iteration=int(value.get("iteration", 0)),
            max_iterations=int(value.get("max_iterations", 8)),
            prior_gap_fingerprints=tuple(value.get("prior_gap_fingerprints", ())),
            model_fingerprint=str(value.get("model_fingerprint", "")),
            evidence_fingerprint=str(value.get("evidence_fingerprint", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "signals": [signal.to_dict() for signal in self.signals],
            "claim_scope": self.claim_scope,
            "require_full_closure": self.require_full_closure,
            "allow_scoped_claim": self.allow_scoped_claim,
            "task_id": self.task_id,
            "coverage_ids": list(self.coverage_ids),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "prior_gap_fingerprints": list(self.prior_gap_fingerprints),
            "model_fingerprint": self.model_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
        }


@dataclass(frozen=True)
class ModelMaturationReport:
    """Result of a model maturation review."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    model_id: str = ""
    risk_id: str = ""
    recommended_actions: tuple[str, ...] = ()
    findings: tuple[ModelMaturationFinding, ...] = ()
    scoped_signal_ids: tuple[str, ...] = ()
    maintenance_obligations: tuple[MaintenanceObligation, ...] = ()
    summary: str = ""
    task_id: str = ""
    iteration: int = 0
    terminal_reason: str = ""
    next_actions: tuple[str, ...] = ()
    open_gap_fingerprints: tuple[str, ...] = ()
    input_fingerprint: str = ""
    progressed: bool = False
    iteration_record: ModelMaturationIteration | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "recommended_actions", _as_tuple(self.recommended_actions))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "scoped_signal_ids", _as_tuple(self.scoped_signal_ids))
        obligations = self.maintenance_obligations or obligations_from_maturation_findings(self.findings)
        object.__setattr__(
            self,
            "maintenance_obligations",
            tuple(coerce_maintenance_obligation(item) for item in obligations),
        )
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "iteration", int(self.iteration))
        object.__setattr__(self, "terminal_reason", str(self.terminal_reason or self.decision))
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions or self.recommended_actions))
        object.__setattr__(self, "open_gap_fingerprints", _as_tuple(self.open_gap_fingerprints))
        object.__setattr__(self, "input_fingerprint", str(self.input_fingerprint))
        object.__setattr__(self, "progressed", bool(self.progressed))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "recommended_actions": list(self.recommended_actions),
            "findings": [finding.to_dict() for finding in self.findings],
            "scoped_signal_ids": list(self.scoped_signal_ids),
            "maintenance_obligations": [obligation.to_dict() for obligation in self.maintenance_obligations],
            "summary": self.summary,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "terminal_reason": self.terminal_reason,
            "next_actions": list(self.next_actions),
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "input_fingerprint": self.input_fingerprint,
            "progressed": self.progressed,
            "iteration_record": self.iteration_record.to_dict() if self.iteration_record else None,
        }

    def format_text(self) -> str:
        lines = [
            f"FlowGuard model maturation loop: {self.decision}",
            f"confidence: {self.confidence}",
        ]
        if self.model_id:
            lines.append(f"model: {self.model_id}")
        if self.risk_id:
            lines.append(f"risk: {self.risk_id}")
        if self.recommended_actions:
            lines.append("recommended actions:")
            lines.extend(f"- {action}" for action in self.recommended_actions)
        if self.findings:
            lines.append("findings:")
            lines.extend(
                f"- [{finding.severity}] {finding.code}: {finding.message}"
                for finding in self.findings
            )
        if self.maintenance_obligations:
            lines.append("maintenance obligations:")
            lines.extend(
                f"- {obligation.status} {obligation.strength}: {obligation.obligation_id}"
                for obligation in self.maintenance_obligations
            )
        if self.summary:
            lines.append(self.summary)
        if self.task_id:
            lines.append(f"task: {self.task_id} iteration: {self.iteration}")
        if self.terminal_reason:
            lines.append(f"terminal reason: {self.terminal_reason}")
        if self.next_actions:
            lines.append("next actions:")
            lines.extend(f"- {action}" for action in self.next_actions)
        return "\n".join(lines)


def _signal_finding(
    code: str,
    message: str,
    *,
    signal: ModelMaturationSignal,
    severity: str = "blocker",
    action: str = "",
) -> ModelMaturationFinding:
    return ModelMaturationFinding(
        code=code,
        message=message,
        severity=severity,
        signal_id=signal.signal_id,
        model_id=signal.model_id,
        risk_id=signal.risk_id,
        action=action,
        metadata=signal.to_dict(),
    )


def _legacy_plan(plan: ModelMaturationPlan) -> bool:
    """Recognize pre-iterative callers without weakening the current route.

    Existing integrations did not have task/coverage/prediction fields.  Their
    historical scoped result remains readable, while every new task declares a
    task or coverage identity and uses the strict loop below.
    """

    return not plan.task_id and not plan.coverage_ids and not any(
        signal.coverage_id
        or signal.resolution_class
        or signal.prediction
        or signal.falsifier
        or signal.evidence_fingerprint
        for signal in plan.signals
    )


def _iteration_for(
    plan: ModelMaturationPlan,
    *,
    open_gap_fingerprints: Sequence[str],
    findings: Sequence[ModelMaturationFinding],
    decision: str,
    recommended: Sequence[str],
) -> ModelMaturationIteration:
    coverage_fingerprint = _stable_fingerprint(plan.coverage_ids)
    input_fingerprint = _stable_fingerprint(
        {
            "plan": plan.plan_id,
            "task": plan.task_id,
            "model": plan.model_id,
            "risk": plan.risk_id,
            "signals": [signal.to_dict() for signal in plan.signals],
        }
    )
    previous = set(plan.prior_gap_fingerprints)
    current = set(open_gap_fingerprints)
    progressed = plan.iteration == 0 or current != previous or bool(findings) and not previous
    resolved = tuple(sorted(previous - current))
    return ModelMaturationIteration(
        iteration_id=f"{plan.plan_id}:{plan.iteration}",
        plan_id=plan.plan_id,
        iteration=plan.iteration,
        model_fingerprint=plan.model_fingerprint or _stable_fingerprint(plan.model_id),
        coverage_fingerprint=coverage_fingerprint,
        input_fingerprint=input_fingerprint,
        open_gap_fingerprints=tuple(sorted(current)),
        resolved_gap_fingerprints=resolved,
        progressed=progressed,
        terminal_reason=decision,
        next_actions=_unique(recommended),
    )


def review_model_maturation_loop(plan: ModelMaturationPlan) -> ModelMaturationReport:
    """Review one task-local iteration and require executable closure.

    The function deliberately does not ask the model whether it understood
    anything.  A gap closes only when the route supplies a current signal with
    a prediction/falsifier or an explicit external/scope disposition.  A later
    call with the next candidate model is the next iteration.
    """

    findings: list[ModelMaturationFinding] = []
    recommended_actions: list[str] = []
    scoped_signal_ids: list[str] = []
    external_signal_ids: list[str] = []
    open_gap_fingerprints: list[str] = []
    normalized_signals: list[ModelMaturationSignal] = []

    for original in plan.signals:
        signal = original
        if not signal.model_id or not signal.risk_id:
            signal = replace(
                signal,
                model_id=signal.model_id or plan.model_id,
                risk_id=signal.risk_id or plan.risk_id,
            )
        normalized_signals.append(signal)

        if not signal.current:
            findings.append(
                _signal_finding(
                    "model_maturation_signal_stale",
                    "maturation signal is stale and cannot support a current model claim",
                    signal=signal,
                    action=MATURITY_ACTION_REFRESH_EVIDENCE,
                )
            )
            recommended_actions.append(MATURITY_ACTION_REFRESH_EVIDENCE)
            if signal.required:
                open_gap_fingerprints.append(signal.gap_fingerprint())

        if signal.metadata.get("understood") is not None or signal.metadata.get("understanding_level") is not None:
            findings.append(
                _signal_finding(
                    "self_report_not_evidence",
                    "a self-reported understanding field is not executable evidence",
                    signal=signal,
                    action=MATURITY_ACTION_ADD_MODEL_OBLIGATION,
                )
            )
            recommended_actions.append(MATURITY_ACTION_ADD_MODEL_OBLIGATION)

        resolution = signal.resolution()
        if not signal.in_scope:
            if resolution == MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED:
                scoped_signal_ids.append(signal.signal_id)
            elif signal.required:
                findings.append(
                    _signal_finding(
                        "model_maturation_signal_out_of_scope",
                        "a required signal was scoped out without an explicit scope disposition",
                        signal=signal,
                        action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                    )
                )
                open_gap_fingerprints.append(signal.gap_fingerprint())
                recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)
            continue

        if signal.signal_type not in MODEL_MATURATION_SIGNAL_TYPES:
            findings.append(
                _signal_finding(
                    "unknown_model_maturation_signal",
                    "maturation signal type is unknown and cannot support full confidence",
                    signal=signal,
                    action=MATURITY_ACTION_ADD_MODEL_OBLIGATION,
                )
            )
            recommended_actions.append(MATURITY_ACTION_ADD_MODEL_OBLIGATION)
            if signal.required and not signal.resolved:
                open_gap_fingerprints.append(signal.gap_fingerprint())

        if signal.resolved:
            continue

        signal_actions = signal.actions()
        recommended_actions.extend(signal_actions)
        if resolution == MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED:
            external_signal_ids.append(signal.signal_id)
            findings.append(
                _signal_finding(
                    "external_input_required",
                    "the next model-discriminating observation belongs to an external provider or operator",
                    signal=signal,
                    action=MATURITY_ACTION_REFRESH_EVIDENCE,
                )
            )
            open_gap_fingerprints.append(signal.gap_fingerprint())
        elif resolution == MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED:
            scoped_signal_ids.append(signal.signal_id)
            findings.append(
                _signal_finding(
                    "scope_excluded",
                    "this signal is explicitly outside the declared task boundary",
                    signal=signal,
                    severity="warning",
                    action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                )
            )
            recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)
        elif signal.required:
            for action in signal_actions:
                findings.append(
                    _signal_finding(
                        "model_upgrade_required",
                        "an unresolved addressable signal requires another model/evidence iteration",
                        signal=signal,
                        action=action,
                    )
                )
            open_gap_fingerprints.append(signal.gap_fingerprint())
        else:
            findings.append(
                _signal_finding(
                    "optional_model_maturation_signal_open",
                    "optional signal remains open and must be tracked as scoped evidence",
                    signal=signal,
                    severity="warning",
                    action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                )
            )
            scoped_signal_ids.append(signal.signal_id)
            recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)

    if plan.coverage_ids:
        covered = {signal.coverage_id for signal in normalized_signals if signal.coverage_id and signal.resolved}
        externally_disposed = {
            signal.coverage_id
            for signal in normalized_signals
            if signal.coverage_id
            and not signal.resolved
            and signal.resolution() in {
                MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
                MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
            }
        }
        for coverage_id in plan.coverage_ids:
            if coverage_id not in covered and coverage_id not in externally_disposed:
                coverage_signal = ModelMaturationSignal(
                    signal_id=f"coverage:{coverage_id}",
                    signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
                    model_id=plan.model_id,
                    risk_id=plan.risk_id,
                    coverage_id=coverage_id,
                    description=f"declared coverage item {coverage_id} has no resolved native evidence",
                )
                findings.append(
                    _signal_finding(
                        "missing_model_coverage",
                        coverage_signal.description,
                        signal=coverage_signal,
                        action=MATURITY_ACTION_ADD_MODEL_OBLIGATION,
                    )
                )
                recommended_actions.append(MATURITY_ACTION_ADD_MODEL_OBLIGATION)
                open_gap_fingerprints.append(coverage_signal.gap_fingerprint())

    recommended = _unique(recommended_actions)
    scoped_ids = _unique(scoped_signal_ids)
    blockers = [finding for finding in findings if finding.severity == "blocker"]
    addressable = [
        finding for finding in blockers
        if finding.code not in {"external_input_required"}
    ]
    new_mode = not _legacy_plan(plan)

    if not new_mode:
        # Preserve the old result shape for callers that have not yet supplied
        # a task/coverage identity. New route prompts always use the strict
        # branch above, so scoped claims cannot evade addressable gaps there.
        if blockers and plan.require_full_closure:
            scoped_ids = _unique(
                (*scoped_ids, *(signal.signal_id for signal in normalized_signals if signal.required and not signal.resolved))
            )
        if not findings:
            decision = MODEL_MATURATION_DECISION_CURRENT
            confidence = MODEL_MATURATION_CONFIDENCE_FULL
            ok = True
            summary = "No current route signal requires model maturation."
            recommended = (MATURITY_ACTION_NO_CHANGE,)
        elif blockers and (not plan.allow_scoped_claim or not plan.require_full_closure):
            decision = MODEL_MATURATION_DECISION_BLOCKED
            confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
            ok = False
            summary = "Model maturation blockers must be resolved before this claim is safe."
        elif blockers:
            decision = MODEL_MATURATION_DECISION_SCOPED
            confidence = MODEL_MATURATION_CONFIDENCE_SCOPED
            ok = True
            recommended = _unique((*recommended, MATURITY_ACTION_DOWNGRADE_CLAIM))
            summary = "Only a scoped legacy FlowGuard claim is supported until maturation signals are resolved."
        else:
            decision = MODEL_MATURATION_DECISION_SCOPED
            confidence = MODEL_MATURATION_CONFIDENCE_SCOPED
            ok = True
            summary = "Only a scoped legacy FlowGuard claim is supported until maturation signals are resolved."
        if decision != MODEL_MATURATION_DECISION_SCOPED and blockers:
            decision = MODEL_MATURATION_DECISION_UPGRADE_REQUIRED if plan.allow_scoped_claim else decision
        iteration_record = None
    else:
        previous = set(plan.prior_gap_fingerprints)
        current = set(open_gap_fingerprints)
        unchanged = plan.iteration > 0 and current and current == previous
        if not current and not blockers and not scoped_ids:
            decision = MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
            confidence = MODEL_MATURATION_CONFIDENCE_FULL
            ok = True
            summary = "All declared task coverage is closed by current model/evidence signals."
            recommended = recommended or (MATURITY_ACTION_NO_CHANGE,)
        elif external_signal_ids and not addressable:
            decision = MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED
            confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
            ok = False
            summary = "The next discriminating observation is external and must be supplied before another iteration."
        elif scoped_ids and not addressable and not external_signal_ids:
            decision = MODEL_MATURATION_DECISION_SCOPE_EXCLUDED
            confidence = MODEL_MATURATION_CONFIDENCE_SCOPED
            ok = False
            summary = "The task boundary explicitly excludes remaining coverage; no full-task claim is allowed."
        elif unchanged:
            decision = MODEL_MATURATION_DECISION_PROGRESS_STALLED
            confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
            ok = False
            summary = "The new iteration did not change the open-gap fingerprint."
        elif plan.iteration >= plan.max_iterations:
            decision = MODEL_MATURATION_DECISION_ITERATION_LIMIT
            confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
            ok = False
            summary = "The iteration budget ended while addressable gaps remained open."
        elif addressable:
            decision = MODEL_MATURATION_DECISION_UPGRADE_REQUIRED
            confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
            ok = False
            summary = "Addressable gaps require another model/evidence iteration; they cannot be scoped away."
        else:
            decision = MODEL_MATURATION_DECISION_BLOCKED
            confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
            ok = False
            summary = "The current evidence cannot establish task-local model closure."
        iteration_record = _iteration_for(
            plan,
            open_gap_fingerprints=open_gap_fingerprints,
            findings=findings,
            decision=decision,
            recommended=recommended or (MATURITY_ACTION_NO_CHANGE,),
        )

    input_fingerprint = iteration_record.input_fingerprint if iteration_record else _stable_fingerprint(plan.to_dict())
    return ModelMaturationReport(
        ok=ok,
        plan_id=plan.plan_id,
        model_id=plan.model_id,
        risk_id=plan.risk_id,
        decision=decision,
        confidence=confidence,
        recommended_actions=recommended or (MATURITY_ACTION_DOWNGRADE_CLAIM,),
        findings=tuple(findings),
        scoped_signal_ids=scoped_ids,
        summary=summary,
        task_id=plan.task_id,
        iteration=plan.iteration,
        terminal_reason=decision if decision in MODEL_MATURATION_TERMINAL_REASONS else "",
        next_actions=recommended,
        open_gap_fingerprints=tuple(sorted(set(open_gap_fingerprints))),
        input_fingerprint=input_fingerprint,
        progressed=(plan.iteration == 0 or set(open_gap_fingerprints) != set(plan.prior_gap_fingerprints)),
        iteration_record=iteration_record,
    )


def review_model_maturation_session(
    plans: Sequence[ModelMaturationPlan],
    *,
    session_id: str = "",
) -> ModelMaturationSession:
    """Review supplied candidate iterations until a terminal result appears."""

    reports: list[ModelMaturationReport] = []
    for plan in plans:
        report = review_model_maturation_loop(plan)
        reports.append(report)
        if report.terminal_reason:
            break
    task_id = next((plan.task_id for plan in plans if plan.task_id), "")
    return ModelMaturationSession(
        session_id=session_id or (plans[0].plan_id if plans else "maturation-session"),
        task_id=task_id,
        iterations=tuple(report.iteration_record for report in reports if report.iteration_record is not None),
        terminal_reason=reports[-1].terminal_reason if reports else MODEL_MATURATION_DECISION_BLOCKED,
    )


__all__ = [
    "MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION",
    "MATURITY_ACTION_ADD_INVARIANT",
    "MATURITY_ACTION_ADD_MODEL_OBLIGATION",
    "MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO",
    "MATURITY_ACTION_ADD_STATE_FIELD",
    "MATURITY_ACTION_ADD_TRANSITION_CASE",
    "MATURITY_ACTION_DOWNGRADE_CLAIM",
    "MATURITY_ACTION_NO_CHANGE",
    "MATURITY_ACTION_REATTACH_PARENT_MODEL",
    "MATURITY_ACTION_REFRESH_EVIDENCE",
    "MATURITY_ACTION_SPLIT_CHILD_MODEL",
    "MODEL_MATURATION_ACTIONS_BY_SIGNAL",
    "MODEL_MATURATION_CONFIDENCE_BLOCKED",
    "MODEL_MATURATION_CONFIDENCE_FULL",
    "MODEL_MATURATION_CONFIDENCE_SCOPED",
    "MODEL_MATURATION_DECISION_CLOSED_FOR_TASK",
    "MODEL_MATURATION_DECISION_BLOCKED",
    "MODEL_MATURATION_DECISION_CURRENT",
    "MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED",
    "MODEL_MATURATION_DECISION_ITERATION_LIMIT",
    "MODEL_MATURATION_DECISION_PROGRESS_STALLED",
    "MODEL_MATURATION_DECISION_SCOPED",
    "MODEL_MATURATION_DECISION_UPGRADE_REQUIRED",
    "MODEL_MATURATION_DECISION_SCOPE_EXCLUDED",
    "MODEL_MATURATION_RESOLUTION_CLASSES",
    "MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION",
    "MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED",
    "MODEL_MATURATION_RESOLUTION_MODEL_EDIT",
    "MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED",
    "MODEL_MATURATION_TERMINAL_REASONS",
    "MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING",
    "MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED",
    "MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING",
    "MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH",
    "MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH",
    "MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING",
    "MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK",
    "MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION",
    "MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION",
    "MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL",
    "MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE",
    "MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING",
    "MODEL_MATURATION_SIGNAL_STALE_EVIDENCE",
    "MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE",
    "MODEL_MATURATION_SIGNAL_TYPES",
    "ModelMaturationFinding",
    "ModelMaturationIteration",
    "ModelMaturationPlan",
    "ModelMaturationReport",
    "ModelMaturationSession",
    "ModelMaturationSignal",
    "review_model_maturation_session",
    "review_model_maturation_loop",
]
