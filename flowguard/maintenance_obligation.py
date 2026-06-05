"""Maintenance obligation memory helpers for existing FlowGuard routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .export import to_jsonable


OBLIGATION_STATUS_OPEN = "open"
OBLIGATION_STATUS_RESOLVED = "resolved"
OBLIGATION_STATUS_SCOPED = "scoped"
OBLIGATION_STATUS_OBSERVATION = "observation"
OBLIGATION_STATUSES = (
    OBLIGATION_STATUS_OPEN,
    OBLIGATION_STATUS_RESOLVED,
    OBLIGATION_STATUS_SCOPED,
    OBLIGATION_STATUS_OBSERVATION,
)

OBLIGATION_STRENGTH_REQUIRED = "required"
OBLIGATION_STRENGTH_SUGGESTED = "suggested"
OBLIGATION_STRENGTH_OPTIONAL = "optional"
OBLIGATION_STRENGTHS = (
    OBLIGATION_STRENGTH_REQUIRED,
    OBLIGATION_STRENGTH_SUGGESTED,
    OBLIGATION_STRENGTH_OPTIONAL,
)

OBLIGATION_CONFIDENCE_FULL = "full"
OBLIGATION_CONFIDENCE_SCOPED = "scoped"
OBLIGATION_CONFIDENCE_BLOCKED = "blocked"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return tuple(ordered)


def _slug(value: str) -> str:
    text = str(value or "obligation").strip().lower()
    chars = [char if char.isalnum() else "-" for char in text]
    collapsed = "-".join(part for part in "".join(chars).split("-") if part)
    return collapsed or "obligation"


@dataclass(frozen=True)
class MaintenanceObligation:
    """One unresolved route-owned maintenance obligation."""

    obligation_id: str
    owner_route: str
    reason_code: str
    source_route: str = ""
    status: str = OBLIGATION_STATUS_OPEN
    strength: str = OBLIGATION_STRENGTH_REQUIRED
    artifact_ids: tuple[str, ...] = ()
    anchor_paths: tuple[str, ...] = ()
    anchor_symbols: tuple[str, ...] = ()
    model_ids: tuple[str, ...] = ()
    risk_ids: tuple[str, ...] = ()
    code_contract_ids: tuple[str, ...] = ()
    public_entrypoint_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    required_input_kinds: tuple[str, ...] = ()
    proof_gap_codes: tuple[str, ...] = ()
    claim_effect: str = ""
    suggested_commands: tuple[str, ...] = ()
    message: str = ""
    scope_reason: str = ""
    current: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "reason_code", str(self.reason_code))
        object.__setattr__(self, "source_route", str(self.source_route))
        status = str(self.status or OBLIGATION_STATUS_OPEN)
        if status not in OBLIGATION_STATUSES:
            raise ValueError(f"status must be one of {OBLIGATION_STATUSES!r}")
        object.__setattr__(self, "status", status)
        strength = str(self.strength or OBLIGATION_STRENGTH_REQUIRED)
        if strength not in OBLIGATION_STRENGTHS:
            raise ValueError(f"strength must be one of {OBLIGATION_STRENGTHS!r}")
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "artifact_ids", _as_tuple(self.artifact_ids))
        object.__setattr__(self, "anchor_paths", _as_tuple(self.anchor_paths))
        object.__setattr__(self, "anchor_symbols", _as_tuple(self.anchor_symbols))
        object.__setattr__(self, "model_ids", _as_tuple(self.model_ids))
        object.__setattr__(self, "risk_ids", _as_tuple(self.risk_ids))
        object.__setattr__(self, "code_contract_ids", _as_tuple(self.code_contract_ids))
        object.__setattr__(self, "public_entrypoint_ids", _as_tuple(self.public_entrypoint_ids))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "required_input_kinds", _as_tuple(self.required_input_kinds))
        object.__setattr__(self, "proof_gap_codes", _as_tuple(self.proof_gap_codes))
        object.__setattr__(self, "claim_effect", str(self.claim_effect))
        object.__setattr__(self, "suggested_commands", _as_tuple(self.suggested_commands))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "scope_reason", str(self.scope_reason))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_active(self) -> bool:
        return self.status == OBLIGATION_STATUS_OPEN and self.current

    def is_required(self) -> bool:
        return self.strength == OBLIGATION_STRENGTH_REQUIRED

    def has_anchor(self) -> bool:
        return bool(
            self.artifact_ids
            or self.anchor_paths
            or self.anchor_symbols
            or self.model_ids
            or self.risk_ids
            or self.code_contract_ids
            or self.public_entrypoint_ids
        )

    def has_resolution_evidence(self) -> bool:
        return bool(self.evidence_ids or (self.status == OBLIGATION_STATUS_SCOPED and self.scope_reason))

    def touches_artifact(self, artifact: Any) -> bool:
        artifact_id = str(getattr(artifact, "artifact_id", "") or "")
        path = str(getattr(artifact, "path", "") or "")
        description = str(getattr(artifact, "description", "") or "")
        if artifact_id and artifact_id in self.artifact_ids:
            return True
        if path and path in self.anchor_paths:
            return True
        for anchor in self.anchor_paths:
            if anchor and path and (path.endswith(anchor) or anchor.endswith(path)):
                return True
        for symbol in self.anchor_symbols + self.public_entrypoint_ids:
            if symbol and (symbol == artifact_id or symbol in path or symbol in description):
                return True
        return False

    def touches_any(self, artifacts: Iterable[Any]) -> bool:
        return any(self.touches_artifact(artifact) for artifact in artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "owner_route": self.owner_route,
            "reason_code": self.reason_code,
            "source_route": self.source_route,
            "status": self.status,
            "strength": self.strength,
            "artifact_ids": list(self.artifact_ids),
            "anchor_paths": list(self.anchor_paths),
            "anchor_symbols": list(self.anchor_symbols),
            "model_ids": list(self.model_ids),
            "risk_ids": list(self.risk_ids),
            "code_contract_ids": list(self.code_contract_ids),
            "public_entrypoint_ids": list(self.public_entrypoint_ids),
            "evidence_ids": list(self.evidence_ids),
            "required_input_kinds": list(self.required_input_kinds),
            "proof_gap_codes": list(self.proof_gap_codes),
            "claim_effect": self.claim_effect,
            "suggested_commands": list(self.suggested_commands),
            "message": self.message,
            "scope_reason": self.scope_reason,
            "current": self.current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class MaintenanceObligationReport:
    """Summary of obligations produced or consumed by a FlowGuard helper."""

    report_id: str
    obligations: tuple[MaintenanceObligation, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        obligations = tuple(coerce_maintenance_obligation(item) for item in self.obligations)
        object.__setattr__(self, "report_id", str(self.report_id))
        object.__setattr__(self, "obligations", obligations)
        object.__setattr__(self, "summary", self.summary or _obligation_summary(obligations))

    @property
    def open_required_obligation_ids(self) -> tuple[str, ...]:
        return tuple(
            obligation.obligation_id
            for obligation in self.obligations
            if obligation.is_active() and obligation.is_required()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "summary": self.summary,
            "open_required_obligation_ids": list(self.open_required_obligation_ids),
            "obligations": [obligation.to_dict() for obligation in self.obligations],
        }

    def format_text(self, max_obligations: int = 12) -> str:
        lines = [
            "=== flowguard maintenance obligations ===",
            f"report: {self.report_id}",
            f"summary: {self.summary}",
        ]
        for obligation in self.obligations[:max_obligations]:
            lines.append(
                f"- {obligation.status} {obligation.strength}: "
                f"{obligation.obligation_id} -> {obligation.owner_route} "
                f"({obligation.reason_code})"
            )
            if obligation.message:
                lines.append(f"  message: {obligation.message}")
        if len(self.obligations) > max_obligations:
            lines.append(f"- ... {len(self.obligations) - max_obligations} more")
        return "\n".join(lines)


def coerce_maintenance_obligation(value: MaintenanceObligation | Mapping[str, Any]) -> MaintenanceObligation:
    if isinstance(value, MaintenanceObligation):
        return value
    if isinstance(value, Mapping):
        return MaintenanceObligation(**dict(value))
    raise TypeError("maintenance obligation must be a MaintenanceObligation or mapping")


def _owner_route_for_section(section_name: str, category: str) -> str:
    section = str(section_name)
    text = f"{section_name} {category}".lower()
    if "conformance" in text:
        return "development_process_flow"
    if "state_closure" in text or "topology_hazard" in text:
        return "model_maturation_loop"
    if "model" in text or "scenario" in text or "contract" in text or "progress" in text:
        return "model_maturation_loop"
    return "development_process_flow" if section in {"not_run", "skipped_with_reason"} else "model_maturation_loop"


def obligation_from_finding_ledger_entry(entry: Any) -> MaintenanceObligation | None:
    section_name = str(getattr(entry, "section_name", "") or "")
    severity = str(getattr(entry, "severity", "") or "")
    category = str(getattr(entry, "category", "") or "")
    if severity == "info":
        return None
    owner_route = str(getattr(entry, "owner_route", "") or "") or _owner_route_for_section(section_name, category)
    finding_index = getattr(entry, "finding_index", None)
    obligation_id = f"{_slug(section_name)}:{_slug(category)}"
    if finding_index is not None:
        obligation_id = f"{obligation_id}:{finding_index}"
    return MaintenanceObligation(
        obligation_id=obligation_id,
        owner_route=owner_route,
        reason_code=category or "summary_gap",
        source_route=section_name,
        strength=OBLIGATION_STRENGTH_REQUIRED if severity in {"failure", "blocker"} else OBLIGATION_STRENGTH_SUGGESTED,
        required_input_kinds=tuple(getattr(entry, "required_input_kinds", ()) or ()),
        proof_gap_codes=tuple(getattr(entry, "proof_gap_codes", ()) or ()),
        claim_effect=str(getattr(entry, "claim_effect", "") or ""),
        suggested_commands=tuple(getattr(entry, "suggested_commands", ()) or ()),
        message=str(getattr(entry, "message", "") or ""),
        metadata={"ledger_entry": getattr(entry, "to_dict", lambda: repr(entry))()},
    )


def obligations_from_finding_ledger(ledger: Any) -> tuple[MaintenanceObligation, ...]:
    obligations = [
        obligation
        for entry in tuple(getattr(ledger, "entries", ()) or ())
        for obligation in (obligation_from_finding_ledger_entry(entry),)
        if obligation is not None
    ]
    return tuple(obligations)


def obligation_from_maintenance_action(action: Any, *, source_route: str = "maintenance_scan_router") -> MaintenanceObligation:
    strength = str(getattr(action, "strength", "") or OBLIGATION_STRENGTH_REQUIRED)
    if strength not in OBLIGATION_STRENGTHS:
        strength = OBLIGATION_STRENGTH_REQUIRED
    resolved = bool(getattr(action, "resolved", False))
    evidence_ids = tuple(getattr(action, "owner_evidence_ids", ()) or ())
    status = OBLIGATION_STATUS_RESOLVED if resolved else OBLIGATION_STATUS_OPEN
    route_id = str(getattr(action, "route_id", "") or "")
    reason_code = str(getattr(action, "reason_code", "") or "maintenance_action")
    return MaintenanceObligation(
        obligation_id=str(getattr(action, "action_id", "") or f"{route_id}:{reason_code}"),
        owner_route=route_id,
        reason_code=reason_code,
        source_route=source_route,
        status=status,
        strength=strength,
        artifact_ids=tuple(getattr(action, "artifact_ids", ()) or ()),
        evidence_ids=evidence_ids,
        required_input_kinds=tuple(getattr(action, "required_input_kinds", ()) or ()),
        proof_gap_codes=tuple(getattr(action, "proof_gap_codes", ()) or ()),
        claim_effect=str(getattr(action, "claim_effect", "") or ""),
        suggested_commands=tuple(getattr(action, "suggested_commands", ()) or ()),
        message=str(getattr(action, "message", "") or ""),
        metadata={"maintenance_action": getattr(action, "to_dict", lambda: repr(action))()},
    )


def obligations_from_maintenance_actions(actions: Iterable[Any]) -> tuple[MaintenanceObligation, ...]:
    return tuple(obligation_from_maintenance_action(action) for action in actions)


def obligation_from_maturation_finding(finding: Any) -> MaintenanceObligation:
    signal_id = str(getattr(finding, "signal_id", "") or "")
    model_id = str(getattr(finding, "model_id", "") or "")
    risk_id = str(getattr(finding, "risk_id", "") or "")
    code = str(getattr(finding, "code", "") or "model_maturation")
    action = str(getattr(finding, "action", "") or "model_maturation_loop")
    severity = str(getattr(finding, "severity", "") or "blocker")
    status = OBLIGATION_STATUS_SCOPED if severity == "warning" else OBLIGATION_STATUS_OPEN
    return MaintenanceObligation(
        obligation_id=f"model-maturation:{_slug(signal_id or code)}",
        owner_route="model_maturation_loop",
        reason_code=code,
        source_route="model_maturation_loop",
        status=status,
        strength=OBLIGATION_STRENGTH_REQUIRED if severity == "blocker" else OBLIGATION_STRENGTH_SUGGESTED,
        model_ids=(model_id,) if model_id else (),
        risk_ids=(risk_id,) if risk_id else (),
        message=str(getattr(finding, "message", "") or ""),
        scope_reason=str(getattr(finding, "message", "") or "") if status == OBLIGATION_STATUS_SCOPED else "",
        metadata={
            "recommended_action": action,
            "maturation_finding": getattr(finding, "to_dict", lambda: repr(finding))(),
        },
    )


def obligations_from_maturation_findings(findings: Iterable[Any]) -> tuple[MaintenanceObligation, ...]:
    return tuple(obligation_from_maturation_finding(finding) for finding in findings)


def _obligation_summary(obligations: tuple[MaintenanceObligation, ...]) -> str:
    open_required = sum(1 for obligation in obligations if obligation.is_active() and obligation.is_required())
    open_total = sum(1 for obligation in obligations if obligation.is_active())
    scoped = sum(1 for obligation in obligations if obligation.status == OBLIGATION_STATUS_SCOPED)
    resolved = sum(1 for obligation in obligations if obligation.status == OBLIGATION_STATUS_RESOLVED)
    return (
        f"obligations={len(obligations)} open={open_total} "
        f"open_required={open_required} scoped={scoped} resolved={resolved}"
    )


def build_maintenance_obligation_report(
    report_id: str,
    obligations: Iterable[MaintenanceObligation | Mapping[str, Any]],
) -> MaintenanceObligationReport:
    return MaintenanceObligationReport(report_id, tuple(coerce_maintenance_obligation(item) for item in obligations))


__all__ = [
    "OBLIGATION_CONFIDENCE_BLOCKED",
    "OBLIGATION_CONFIDENCE_FULL",
    "OBLIGATION_CONFIDENCE_SCOPED",
    "OBLIGATION_STATUS_OBSERVATION",
    "OBLIGATION_STATUS_OPEN",
    "OBLIGATION_STATUS_RESOLVED",
    "OBLIGATION_STATUS_SCOPED",
    "OBLIGATION_STATUSES",
    "OBLIGATION_STRENGTH_OPTIONAL",
    "OBLIGATION_STRENGTH_REQUIRED",
    "OBLIGATION_STRENGTH_SUGGESTED",
    "OBLIGATION_STRENGTHS",
    "MaintenanceObligation",
    "MaintenanceObligationReport",
    "build_maintenance_obligation_report",
    "coerce_maintenance_obligation",
    "obligation_from_finding_ledger_entry",
    "obligation_from_maintenance_action",
    "obligation_from_maturation_finding",
    "obligations_from_finding_ledger",
    "obligations_from_maintenance_actions",
    "obligations_from_maturation_findings",
]
