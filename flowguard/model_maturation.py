"""Model maturation loop review helpers.

This helper turns post-code, post-test, mesh, freshness, or model-miss signals
into explicit model-upgrade actions before a broad FlowGuard claim is made.
It does not replace the owning satellite routes; it records when their evidence
means the model itself is too coarse, stale, or only supports scoped confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .maintenance_obligation import (
    MaintenanceObligation,
    coerce_maintenance_obligation,
    obligations_from_maturation_findings,
)


MODEL_MATURATION_DECISION_CURRENT = "model_maturation_current"
MODEL_MATURATION_DECISION_UPGRADE_REQUIRED = "model_maturation_upgrade_required"
MODEL_MATURATION_DECISION_SCOPED = "model_maturation_scoped_claim"
MODEL_MATURATION_DECISION_BLOCKED = "model_maturation_blocked"

MODEL_MATURATION_CONFIDENCE_FULL = "full"
MODEL_MATURATION_CONFIDENCE_SCOPED = "scoped"
MODEL_MATURATION_CONFIDENCE_BLOCKED = "blocked"

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
            "metadata": to_jsonable(dict(self.metadata)),
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "require_full_closure", bool(self.require_full_closure))
        object.__setattr__(self, "allow_scoped_claim", bool(self.allow_scoped_claim))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "signals": [signal.to_dict() for signal in self.signals],
            "claim_scope": self.claim_scope,
            "require_full_closure": self.require_full_closure,
            "allow_scoped_claim": self.allow_scoped_claim,
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


def review_model_maturation_loop(plan: ModelMaturationPlan) -> ModelMaturationReport:
    """Review whether route evidence requires a model upgrade before closure."""

    findings: list[ModelMaturationFinding] = []
    recommended_actions: list[str] = []
    scoped_signal_ids: list[str] = []

    for signal in plan.signals:
        if not signal.model_id or not signal.risk_id:
            signal = replace(
                signal,
                model_id=signal.model_id or plan.model_id,
                risk_id=signal.risk_id or plan.risk_id,
            )

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

        if not signal.in_scope:
            if signal.required:
                findings.append(
                    _signal_finding(
                        "model_maturation_signal_out_of_scope",
                        "required maturation signal was scoped out and must limit the claim",
                        signal=signal,
                        severity="warning",
                        action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                    )
                )
                scoped_signal_ids.append(signal.signal_id)
                recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)
            continue

        if signal.signal_type not in MODEL_MATURATION_SIGNAL_TYPES:
            findings.append(
                _signal_finding(
                    "unknown_model_maturation_signal",
                    "maturation signal type is unknown and cannot support full confidence",
                    signal=signal,
                    action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                )
            )
            recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)

        if signal.resolved:
            continue

        signal_actions = signal.actions()
        recommended_actions.extend(signal_actions)
        if signal.required:
            for action in signal_actions:
                findings.append(
                    _signal_finding(
                        "model_upgrade_required",
                        "unresolved in-scope maturation signal requires model upgrade action",
                        signal=signal,
                        action=action,
                    )
                )
            if plan.require_full_closure:
                scoped_signal_ids.append(signal.signal_id)
        else:
            findings.append(
                _signal_finding(
                    "optional_model_maturation_signal_open",
                    "optional maturation signal remains open and should be tracked as scoped evidence",
                    signal=signal,
                    severity="warning",
                    action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                )
            )
            scoped_signal_ids.append(signal.signal_id)
            recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)

    recommended = _unique(recommended_actions)
    scoped_ids = _unique(scoped_signal_ids)
    unresolved_blockers = [finding for finding in findings if finding.severity == "blocker"]

    if not findings:
        return ModelMaturationReport(
            ok=True,
            plan_id=plan.plan_id,
            model_id=plan.model_id,
            risk_id=plan.risk_id,
            decision=MODEL_MATURATION_DECISION_CURRENT,
            confidence=MODEL_MATURATION_CONFIDENCE_FULL,
            recommended_actions=(MATURITY_ACTION_NO_CHANGE,),
            summary="No current route signal requires model maturation.",
        )

    if unresolved_blockers and (not plan.allow_scoped_claim or not plan.require_full_closure):
        decision = MODEL_MATURATION_DECISION_BLOCKED
        confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
        ok = False
    elif unresolved_blockers:
        decision = MODEL_MATURATION_DECISION_SCOPED
        confidence = MODEL_MATURATION_CONFIDENCE_SCOPED
        ok = True
        recommended = _unique((*recommended, MATURITY_ACTION_DOWNGRADE_CLAIM))
    else:
        decision = MODEL_MATURATION_DECISION_SCOPED
        confidence = MODEL_MATURATION_CONFIDENCE_SCOPED
        ok = True

    if decision == MODEL_MATURATION_DECISION_BLOCKED:
        summary = "Model maturation blockers must be resolved before this claim is safe."
    elif decision == MODEL_MATURATION_DECISION_SCOPED:
        summary = "Only a scoped FlowGuard claim is supported until maturation signals are resolved."
    else:
        summary = "Model maturation upgrade is required."

    if decision != MODEL_MATURATION_DECISION_SCOPED and unresolved_blockers:
        decision = MODEL_MATURATION_DECISION_UPGRADE_REQUIRED if plan.allow_scoped_claim else decision

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
    "MODEL_MATURATION_DECISION_BLOCKED",
    "MODEL_MATURATION_DECISION_CURRENT",
    "MODEL_MATURATION_DECISION_SCOPED",
    "MODEL_MATURATION_DECISION_UPGRADE_REQUIRED",
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
    "ModelMaturationPlan",
    "ModelMaturationReport",
    "ModelMaturationSignal",
    "review_model_maturation_loop",
]
