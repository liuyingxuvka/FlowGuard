"""Automatic state and input closure review for model-first checks.

The review does not make FlowGuard infinite-state. It makes the finite boundary
explicit: closed dimensions say the modeled values are complete, open
dimensions need representative outside-enumeration cases and safe handling, and
inferred unknown dimensions automatically scope confidence until the model owner
declares the missing policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Iterable, Mapping, Sequence

from .export import to_jsonable


STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT = "external_input"
STATE_CLOSURE_DIMENSION_INPUT_FIELD = "input_field"
STATE_CLOSURE_DIMENSION_STATE_FIELD = "state_field"
STATE_CLOSURE_DIMENSION_OUTPUT = "output"

STATE_CLOSURE_POLICY_CLOSED = "closed_enumeration"
STATE_CLOSURE_POLICY_OPEN = "open_boundary"
STATE_CLOSURE_POLICY_UNBOUNDED = "unbounded_boundary"
STATE_CLOSURE_POLICY_UNKNOWN = "unknown_policy"
STATE_CLOSURE_POLICIES = (
    STATE_CLOSURE_POLICY_CLOSED,
    STATE_CLOSURE_POLICY_OPEN,
    STATE_CLOSURE_POLICY_UNBOUNDED,
    STATE_CLOSURE_POLICY_UNKNOWN,
)

STATE_CLOSURE_CASE_UNKNOWN_ENUM = "unknown_enum"
STATE_CLOSURE_CASE_MALFORMED_INPUT = "malformed_input"
STATE_CLOSURE_CASE_MISSING_REQUIRED_FIELD = "missing_required_field"
STATE_CLOSURE_CASE_CONFLICTING_IDENTITY = "conflicting_same_identity"
STATE_CLOSURE_CASE_OLD_SCHEMA_VERSION = "old_schema_version"
STATE_CLOSURE_CASE_TERMINAL_REPLAY = "terminal_replay"
STATE_CLOSURE_CASE_INVALID_INITIAL_STATE = "invalid_initial_state"
STATE_CLOSURE_CASE_EXTERNAL_UNKNOWN = "external_unknown"

STATE_CLOSURE_HANDLING_UNKNOWN = "unknown_handling"
STATE_CLOSURE_HANDLING_REJECT = "reject_before_side_effect"
STATE_CLOSURE_HANDLING_BLOCK = "block_before_side_effect"
STATE_CLOSURE_HANDLING_ISOLATE = "isolate_before_side_effect"
STATE_CLOSURE_HANDLING_ROUTE_TO_MODEL_MATURATION = "route_to_model_maturation"
STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL = "accept_as_normal"
STATE_CLOSURE_HANDLINGS = (
    STATE_CLOSURE_HANDLING_UNKNOWN,
    STATE_CLOSURE_HANDLING_REJECT,
    STATE_CLOSURE_HANDLING_BLOCK,
    STATE_CLOSURE_HANDLING_ISOLATE,
    STATE_CLOSURE_HANDLING_ROUTE_TO_MODEL_MATURATION,
    STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
)

STATE_CLOSURE_FINDING_INFO = "info"
STATE_CLOSURE_FINDING_CONFIDENCE_GAP = "confidence_gap"
STATE_CLOSURE_FINDING_BLOCKER = "blocker"
STATE_CLOSURE_FINDING_SEVERITIES = (
    STATE_CLOSURE_FINDING_INFO,
    STATE_CLOSURE_FINDING_CONFIDENCE_GAP,
    STATE_CLOSURE_FINDING_BLOCKER,
)

STATE_CLOSURE_DECISION_PASS = "state_closure_pass"
STATE_CLOSURE_DECISION_SCOPED = "state_closure_scoped_confidence"
STATE_CLOSURE_DECISION_BLOCKED = "state_closure_blocked"

STATE_CLOSURE_CONFIDENCE_FULL = "full"
STATE_CLOSURE_CONFIDENCE_SCOPED = "scoped"
STATE_CLOSURE_CONFIDENCE_BLOCKED = "blocked"

_SAFE_HANDLINGS = {
    STATE_CLOSURE_HANDLING_REJECT,
    STATE_CLOSURE_HANDLING_BLOCK,
    STATE_CLOSURE_HANDLING_ISOLATE,
    STATE_CLOSURE_HANDLING_ROUTE_TO_MODEL_MATURATION,
}
_UNSAFE_HANDLINGS = {STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL}
_BROAD_CLAIMS = {"done", "release", "publish", "production", "production_conformance", "full"}
_STATE_FIELD_HINTS = {
    "action",
    "bucket",
    "category",
    "event",
    "kind",
    "mode",
    "phase",
    "schema_version",
    "stage",
    "state",
    "status",
    "step",
    "type",
    "version",
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _value_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return repr(value)
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}:{repr(value)}"


def _field_is_state_like(name: str) -> bool:
    normalized = name.strip().lower()
    if normalized in _STATE_FIELD_HINTS:
        return True
    return any(normalized.endswith(f"_{hint}") for hint in _STATE_FIELD_HINTS)


def _representative_unknowns(values: Sequence[Any], *, include_malformed: bool = False) -> tuple[str, ...]:
    texts = {_value_text(value) for value in values}
    candidates = ["__flowguard_other__"]
    if include_malformed:
        candidates.extend(("__flowguard_malformed__", "__flowguard_missing_required__"))
    for candidate in candidates:
        if candidate not in texts:
            return (candidate,)
    return ("__flowguard_other_2__",)


@dataclass(frozen=True)
class StateClosureCase:
    """One representative outside-enumeration case generated or supplied for review."""

    case_id: str
    dimension_id: str
    case_kind: str
    value: Any = None
    description: str = ""
    generated: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "dimension_id", str(self.dimension_id))
        object.__setattr__(self, "case_kind", str(self.case_kind))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "generated", bool(self.generated))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "dimension_id": self.dimension_id,
            "case_kind": self.case_kind,
            "value": to_jsonable(self.value),
            "description": self.description,
            "generated": self.generated,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class StateClosureDimension:
    """One finite model dimension whose outside-enumeration behavior matters."""

    dimension_id: str
    dimension_kind: str
    policy: str = STATE_CLOSURE_POLICY_UNKNOWN
    known_values: tuple[str, ...] = ()
    representative_unknowns: tuple[str, ...] = ()
    handling: str = STATE_CLOSURE_HANDLING_UNKNOWN
    side_effects_before_resolution: bool = False
    required: bool = True
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        policy = str(self.policy or STATE_CLOSURE_POLICY_UNKNOWN)
        if policy not in STATE_CLOSURE_POLICIES:
            raise ValueError(f"policy must be one of {STATE_CLOSURE_POLICIES!r}")
        handling = str(self.handling or STATE_CLOSURE_HANDLING_UNKNOWN)
        if handling not in STATE_CLOSURE_HANDLINGS:
            raise ValueError(f"handling must be one of {STATE_CLOSURE_HANDLINGS!r}")
        object.__setattr__(self, "dimension_id", str(self.dimension_id))
        object.__setattr__(self, "dimension_kind", str(self.dimension_kind))
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "known_values", _as_tuple(self.known_values))
        object.__setattr__(self, "representative_unknowns", _as_tuple(self.representative_unknowns))
        object.__setattr__(self, "handling", handling)
        object.__setattr__(self, "side_effects_before_resolution", bool(self.side_effects_before_resolution))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "dimension_kind": self.dimension_kind,
            "policy": self.policy,
            "known_values": list(self.known_values),
            "representative_unknowns": list(self.representative_unknowns),
            "handling": self.handling,
            "side_effects_before_resolution": self.side_effects_before_resolution,
            "required": self.required,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class StateClosureFinding:
    """One state closure gap or blocker."""

    code: str
    message: str
    severity: str = STATE_CLOSURE_FINDING_CONFIDENCE_GAP
    dimension_id: str = ""
    case_id: str = ""
    action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        severity = str(self.severity or STATE_CLOSURE_FINDING_CONFIDENCE_GAP)
        if severity not in STATE_CLOSURE_FINDING_SEVERITIES:
            raise ValueError(f"severity must be one of {STATE_CLOSURE_FINDING_SEVERITIES!r}")
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "dimension_id", str(self.dimension_id))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "dimension_id": self.dimension_id,
            "case_id": self.case_id,
            "action": self.action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class StateClosurePlan:
    """Inputs for reviewing whether unknown state/input cases are safely scoped."""

    plan_id: str
    dimensions: tuple[StateClosureDimension, ...] = ()
    supplied_cases: tuple[StateClosureCase, ...] = ()
    claim_scope: str = "bounded"
    allow_scoped_confidence: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "dimensions", tuple(self.dimensions))
        object.__setattr__(self, "supplied_cases", tuple(self.supplied_cases))
        object.__setattr__(self, "claim_scope", str(self.claim_scope or "bounded"))
        object.__setattr__(self, "allow_scoped_confidence", bool(self.allow_scoped_confidence))
        object.__setattr__(self, "notes", str(self.notes or ""))

    def broad_claim(self) -> bool:
        return self.claim_scope.strip().lower() in _BROAD_CLAIMS

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "dimensions": [dimension.to_dict() for dimension in self.dimensions],
            "supplied_cases": [case.to_dict() for case in self.supplied_cases],
            "claim_scope": self.claim_scope,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class StateClosureReport:
    """Structured result for the automatic state/input closure gate."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    generated_cases: tuple[StateClosureCase, ...] = ()
    findings: tuple[StateClosureFinding, ...] = ()
    unresolved_finding_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "generated_cases", tuple(self.generated_cases))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "unresolved_finding_ids", _as_tuple(self.unresolved_finding_ids))
        object.__setattr__(self, "summary", str(self.summary or ""))

    def format_text(self) -> str:
        lines = [
            "=== flowguard state closure ===",
            f"plan_id: {self.plan_id}",
            f"status: {'pass' if self.ok else 'blocked'}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"summary: {self.summary}",
            f"generated_cases: {len(self.generated_cases)}",
        ]
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                suffix = f" action={finding.action}" if finding.action else ""
                lines.append(
                    f"- {finding.severity}: {finding.code}: {finding.message}{suffix}"
                )
        if self.unresolved_finding_ids:
            lines.append("unresolved_finding_ids: " + ", ".join(self.unresolved_finding_ids))
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "generated_cases": [case.to_dict() for case in self.generated_cases],
            "findings": [finding.to_dict() for finding in self.findings],
            "unresolved_finding_ids": list(self.unresolved_finding_ids),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def infer_state_closure_dimensions(
    *,
    external_inputs: Sequence[Any] = (),
    initial_states: Sequence[Any] = (),
) -> tuple[StateClosureDimension, ...]:
    """Infer visible model dimensions that need an outside-enumeration policy."""

    dimensions: list[StateClosureDimension] = []
    external_inputs = tuple(external_inputs)
    initial_states = tuple(initial_states)
    if external_inputs:
        dimensions.append(
            StateClosureDimension(
                "external_input",
                STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
                known_values=_unique(_value_text(value) for value in external_inputs),
                representative_unknowns=_representative_unknowns(external_inputs, include_malformed=True),
                description="The finite external input set supplied to the model.",
                metadata={"inferred": True},
            )
        )
        dimensions.extend(_field_dimensions("input", external_inputs, STATE_CLOSURE_DIMENSION_INPUT_FIELD))
    if initial_states:
        dimensions.extend(_field_dimensions("state", initial_states, STATE_CLOSURE_DIMENSION_STATE_FIELD))
    return tuple(dimensions)


def infer_state_closure_plan(
    *,
    workflow: Any = None,
    external_inputs: Sequence[Any] = (),
    initial_states: Sequence[Any] = (),
    risk_profile: Any = None,
    plan_id: str | None = None,
    allow_scoped_confidence: bool = True,
) -> StateClosurePlan:
    """Build an automatic closure plan from a model-first check plan."""

    del workflow
    claim_scope = "bounded"
    if risk_profile is not None:
        claim_scope = str(getattr(risk_profile, "confidence_goal", "bounded") or "bounded")
    return StateClosurePlan(
        plan_id=plan_id or "auto_state_closure",
        dimensions=infer_state_closure_dimensions(
            external_inputs=external_inputs,
            initial_states=initial_states,
        ),
        claim_scope=claim_scope,
        allow_scoped_confidence=allow_scoped_confidence,
        notes="auto-inferred by FlowGuard from the supplied model-first check plan",
    )


def review_state_closure(plan: StateClosurePlan) -> StateClosureReport:
    """Review unknown/other cases before broad model confidence is claimed."""

    generated_cases: list[StateClosureCase] = []
    findings: list[StateClosureFinding] = []
    if not plan.dimensions:
        findings.append(
            StateClosureFinding(
                "state_closure_no_dimensions_inferred",
                "No finite input/state dimensions were inferred for closure review.",
                STATE_CLOSURE_FINDING_INFO,
                action="declare closure dimensions if this model has hidden states or external inputs",
            )
        )

    supplied_case_dimension_ids = {case.dimension_id for case in plan.supplied_cases}
    for dimension in plan.dimensions:
        cases = _cases_for_dimension(dimension)
        generated_cases.extend(cases)
        has_cases = bool(cases) or dimension.dimension_id in supplied_case_dimension_ids
        if dimension.policy == STATE_CLOSURE_POLICY_UNKNOWN:
            findings.append(
                StateClosureFinding(
                    "state_closure_policy_missing",
                    "Closure policy is inferred but not declared; full confidence is scoped until the model says closed or defines unknown handling.",
                    STATE_CLOSURE_FINDING_CONFIDENCE_GAP,
                    dimension_id=dimension.dimension_id,
                    action="declare closed_enumeration or open_boundary handling",
                )
            )
            continue
        if dimension.policy == STATE_CLOSURE_POLICY_CLOSED:
            continue
        if dimension.policy == STATE_CLOSURE_POLICY_UNBOUNDED:
            findings.append(
                StateClosureFinding(
                    "state_closure_unbounded",
                    "Dimension is unbounded; full-flow confidence needs a narrower claim or a generated representative family.",
                    STATE_CLOSURE_FINDING_BLOCKER if plan.broad_claim() else STATE_CLOSURE_FINDING_CONFIDENCE_GAP,
                    dimension_id=dimension.dimension_id,
                    action="narrow claim scope or add representative unknown families",
                )
            )
        if dimension.policy == STATE_CLOSURE_POLICY_OPEN and not has_cases:
            findings.append(
                StateClosureFinding(
                    "state_closure_unknown_case_missing",
                    "Open boundary has no representative outside-enumeration case.",
                    STATE_CLOSURE_FINDING_BLOCKER,
                    dimension_id=dimension.dimension_id,
                    action="add representative_unknowns such as other, malformed, missing field, or old schema",
                )
            )
        if dimension.policy in {STATE_CLOSURE_POLICY_OPEN, STATE_CLOSURE_POLICY_UNBOUNDED}:
            if dimension.handling == STATE_CLOSURE_HANDLING_UNKNOWN:
                findings.append(
                    StateClosureFinding(
                        "state_closure_unknown_handling_missing",
                        "Unknown or other values do not declare safe handling.",
                        STATE_CLOSURE_FINDING_BLOCKER,
                        dimension_id=dimension.dimension_id,
                        action="reject, block, isolate, or route to model maturation before side effects",
                    )
                )
            elif dimension.handling in _UNSAFE_HANDLINGS:
                findings.append(
                    StateClosureFinding(
                        "state_closure_unknown_handling_unsafe",
                        "Unknown or other values are accepted as normal flow.",
                        STATE_CLOSURE_FINDING_BLOCKER,
                        dimension_id=dimension.dimension_id,
                        action="handle unknown values separately before normal side effects",
                    )
                )
            elif dimension.handling not in _SAFE_HANDLINGS:
                findings.append(
                    StateClosureFinding(
                        "state_closure_unknown_handling_unrecognized",
                        "Unknown or other handling is not one of the safe handling policies.",
                        STATE_CLOSURE_FINDING_BLOCKER,
                        dimension_id=dimension.dimension_id,
                    )
                )
        if dimension.side_effects_before_resolution:
            findings.append(
                StateClosureFinding(
                    "state_closure_side_effect_before_resolution",
                    "Unknown or other values can cause side effects before they are rejected, blocked, isolated, or routed.",
                    STATE_CLOSURE_FINDING_BLOCKER,
                    dimension_id=dimension.dimension_id,
                    action="move side effects after closure resolution",
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == STATE_CLOSURE_FINDING_BLOCKER)
    gaps = tuple(finding for finding in findings if finding.severity == STATE_CLOSURE_FINDING_CONFIDENCE_GAP)
    unresolved = tuple(f"{finding.dimension_id or 'state_closure'}:{finding.code}" for finding in blockers)

    if blockers:
        if plan.broad_claim() and plan.allow_scoped_confidence and not _has_side_effect_blocker(blockers):
            decision = STATE_CLOSURE_DECISION_SCOPED
            confidence = STATE_CLOSURE_CONFIDENCE_SCOPED
            ok = True
            summary = "State/input closure has blockers for full confidence; broad claim is scoped."
        else:
            decision = STATE_CLOSURE_DECISION_BLOCKED
            confidence = STATE_CLOSURE_CONFIDENCE_BLOCKED
            ok = False
            summary = "State/input closure is unresolved before safe completion."
    elif gaps:
        decision = STATE_CLOSURE_DECISION_SCOPED
        confidence = STATE_CLOSURE_CONFIDENCE_SCOPED
        ok = True
        summary = "State/input closure ran automatically and found scoped confidence gaps."
    else:
        decision = STATE_CLOSURE_DECISION_PASS
        confidence = STATE_CLOSURE_CONFIDENCE_FULL
        ok = True
        summary = "State/input closure policies are explicit for modeled dimensions."

    return StateClosureReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        generated_cases=tuple(generated_cases),
        findings=tuple(findings),
        unresolved_finding_ids=unresolved,
        summary=summary,
    )


def _field_dimensions(prefix: str, values: Sequence[Any], dimension_kind: str) -> tuple[StateClosureDimension, ...]:
    observed: dict[str, list[Any]] = {}
    for value in values:
        if not (is_dataclass(value) and not isinstance(value, type)):
            continue
        for item in fields(value):
            if not _field_is_state_like(item.name):
                continue
            observed.setdefault(item.name, []).append(getattr(value, item.name))
    dimensions: list[StateClosureDimension] = []
    for field_name, field_values in sorted(observed.items()):
        dimension_id = f"{prefix}.{field_name}"
        dimensions.append(
            StateClosureDimension(
                dimension_id,
                dimension_kind,
                known_values=_unique(_value_text(value) for value in field_values),
                representative_unknowns=_representative_unknowns(field_values, include_malformed=True),
                description=f"Inferred {prefix} field {field_name!r}.",
                metadata={"inferred": True, "field_name": field_name},
            )
        )
    return tuple(dimensions)


def _cases_for_dimension(dimension: StateClosureDimension) -> tuple[StateClosureCase, ...]:
    cases: list[StateClosureCase] = []
    for index, value in enumerate(dimension.representative_unknowns, start=1):
        cases.append(
            StateClosureCase(
                f"{dimension.dimension_id}:unknown:{index}",
                dimension.dimension_id,
                STATE_CLOSURE_CASE_UNKNOWN_ENUM,
                value=value,
                description="representative value outside the modeled enumeration",
                generated=True,
            )
        )
    if dimension.required and dimension.dimension_kind in {
        STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
        STATE_CLOSURE_DIMENSION_INPUT_FIELD,
    }:
        cases.append(
            StateClosureCase(
                f"{dimension.dimension_id}:missing_required",
                dimension.dimension_id,
                STATE_CLOSURE_CASE_MISSING_REQUIRED_FIELD,
                value="__flowguard_missing_required__",
                description="representative missing required input or field",
                generated=True,
            )
        )
    if dimension.dimension_kind in {
        STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
        STATE_CLOSURE_DIMENSION_INPUT_FIELD,
    }:
        cases.append(
            StateClosureCase(
                f"{dimension.dimension_id}:malformed",
                dimension.dimension_id,
                STATE_CLOSURE_CASE_MALFORMED_INPUT,
                value="__flowguard_malformed__",
                description="representative malformed input shape",
                generated=True,
            )
        )
    return tuple(cases)


def _has_side_effect_blocker(findings: Sequence[StateClosureFinding]) -> bool:
    return any(finding.code == "state_closure_side_effect_before_resolution" for finding in findings)


__all__ = [
    "STATE_CLOSURE_CASE_CONFLICTING_IDENTITY",
    "STATE_CLOSURE_CASE_EXTERNAL_UNKNOWN",
    "STATE_CLOSURE_CASE_INVALID_INITIAL_STATE",
    "STATE_CLOSURE_CASE_MALFORMED_INPUT",
    "STATE_CLOSURE_CASE_MISSING_REQUIRED_FIELD",
    "STATE_CLOSURE_CASE_OLD_SCHEMA_VERSION",
    "STATE_CLOSURE_CASE_TERMINAL_REPLAY",
    "STATE_CLOSURE_CASE_UNKNOWN_ENUM",
    "STATE_CLOSURE_CONFIDENCE_BLOCKED",
    "STATE_CLOSURE_CONFIDENCE_FULL",
    "STATE_CLOSURE_CONFIDENCE_SCOPED",
    "STATE_CLOSURE_DECISION_BLOCKED",
    "STATE_CLOSURE_DECISION_PASS",
    "STATE_CLOSURE_DECISION_SCOPED",
    "STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT",
    "STATE_CLOSURE_DIMENSION_INPUT_FIELD",
    "STATE_CLOSURE_DIMENSION_OUTPUT",
    "STATE_CLOSURE_DIMENSION_STATE_FIELD",
    "STATE_CLOSURE_FINDING_BLOCKER",
    "STATE_CLOSURE_FINDING_CONFIDENCE_GAP",
    "STATE_CLOSURE_FINDING_INFO",
    "STATE_CLOSURE_FINDING_SEVERITIES",
    "STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL",
    "STATE_CLOSURE_HANDLING_BLOCK",
    "STATE_CLOSURE_HANDLING_ISOLATE",
    "STATE_CLOSURE_HANDLING_REJECT",
    "STATE_CLOSURE_HANDLING_ROUTE_TO_MODEL_MATURATION",
    "STATE_CLOSURE_HANDLING_UNKNOWN",
    "STATE_CLOSURE_HANDLINGS",
    "STATE_CLOSURE_POLICIES",
    "STATE_CLOSURE_POLICY_CLOSED",
    "STATE_CLOSURE_POLICY_OPEN",
    "STATE_CLOSURE_POLICY_UNBOUNDED",
    "STATE_CLOSURE_POLICY_UNKNOWN",
    "StateClosureCase",
    "StateClosureDimension",
    "StateClosureFinding",
    "StateClosurePlan",
    "StateClosureReport",
    "infer_state_closure_dimensions",
    "infer_state_closure_plan",
    "review_state_closure",
]
