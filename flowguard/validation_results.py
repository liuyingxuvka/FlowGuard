"""Canonical result semantics for productized FlowGuard validation commands."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


VALIDATION_STATUS_PASS = "pass"
VALIDATION_STATUS_FAIL = "fail"
VALIDATION_STATUS_BLOCKED = "blocked"
VALIDATION_STATUS_PARTIAL = "partial"
VALIDATION_STATUS_INVALID_INPUT = "invalid_input"
VALIDATION_STATUS_TIMEOUT = "timeout"
VALIDATION_STATUS_CANCELLED = "cancelled"
VALIDATION_STATUS_INTERNAL_ERROR = "internal_error"
VALIDATION_STATUSES = (
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_FAIL,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_PARTIAL,
    VALIDATION_STATUS_INVALID_INPUT,
    VALIDATION_STATUS_TIMEOUT,
    VALIDATION_STATUS_CANCELLED,
    VALIDATION_STATUS_INTERNAL_ERROR,
)
VALIDATION_EXIT_CODES = {
    VALIDATION_STATUS_PASS: 0,
    VALIDATION_STATUS_FAIL: 1,
    VALIDATION_STATUS_BLOCKED: 2,
    VALIDATION_STATUS_INVALID_INPUT: 3,
    VALIDATION_STATUS_TIMEOUT: 4,
    VALIDATION_STATUS_CANCELLED: 5,
    VALIDATION_STATUS_PARTIAL: 6,
    VALIDATION_STATUS_INTERNAL_ERROR: 70,
}


@dataclass(frozen=True)
class SkippedValidation:
    check_id: str
    reason: str
    impact: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "reason": self.reason,
            "impact": self.impact,
            "required": self.required,
        }


@dataclass(frozen=True)
class ValidationChildResult:
    child_id: str
    status: str
    summary: str = ""
    receipt_id: str = ""
    artifact_paths: tuple[str, ...] = ()
    claim_boundary: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if self.status not in VALIDATION_STATUSES:
            raise ValueError(f"unsupported validation child status: {self.status}")
        object.__setattr__(self, "artifact_paths", tuple(str(item) for item in self.artifact_paths))
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_id": self.child_id,
            "status": self.status,
            "summary": self.summary,
            "receipt_id": self.receipt_id,
            "artifact_paths": list(self.artifact_paths),
            "claim_boundary": self.claim_boundary,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class ValidationResult:
    command: str
    status: str
    scope: str
    tier: str = ""
    counts: Mapping[str, int] = field(default_factory=dict, compare=False)
    evidence: tuple[Mapping[str, Any], ...] = ()
    failures: tuple[Mapping[str, Any] | str, ...] = ()
    blockers: tuple[Mapping[str, Any] | str, ...] = ()
    skipped_checks: tuple[SkippedValidation, ...] = ()
    residual_risk: tuple[str, ...] = ()
    claim_boundary: str = ""
    progress_summary: Mapping[str, Any] = field(default_factory=dict, compare=False)
    artifact_paths: tuple[str, ...] = ()
    children: tuple[ValidationChildResult, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in VALIDATION_STATUSES:
            raise ValueError(f"unsupported validation status: {self.status}")
        if not self.command or not self.scope or not self.claim_boundary:
            raise ValueError("command, scope, and claim_boundary are required")
        object.__setattr__(self, "counts", {str(key): int(value) for key, value in self.counts.items()})
        object.__setattr__(self, "evidence", tuple(dict(item) for item in self.evidence))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "blockers", tuple(self.blockers))
        object.__setattr__(self, "skipped_checks", tuple(self.skipped_checks))
        object.__setattr__(self, "residual_risk", tuple(str(item) for item in self.residual_risk))
        object.__setattr__(self, "progress_summary", dict(self.progress_summary))
        object.__setattr__(self, "artifact_paths", tuple(str(item) for item in self.artifact_paths))
        object.__setattr__(self, "children", tuple(self.children))

    @property
    def ok(self) -> bool:
        return self.status == VALIDATION_STATUS_PASS

    @property
    def exit_code(self) -> int:
        return VALIDATION_EXIT_CODES[self.status]

    @property
    def broad_success(self) -> bool:
        return self.ok and not self.failures and not self.blockers and not any(
            item.required for item in self.skipped_checks
        ) and all(child.status == VALIDATION_STATUS_PASS for child in self.children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "flowguard.validation_result.v1",
            "command": self.command,
            "status": self.status,
            "ok": self.ok,
            "broad_success": self.broad_success,
            "exit_code": self.exit_code,
            "scope": self.scope,
            "tier": self.tier,
            "counts": dict(self.counts),
            "evidence": [dict(item) for item in self.evidence],
            "failures": [dict(item) if isinstance(item, Mapping) else str(item) for item in self.failures],
            "blockers": [dict(item) if isinstance(item, Mapping) else str(item) for item in self.blockers],
            "skipped_checks": [item.to_dict() for item in self.skipped_checks],
            "residual_risk": list(self.residual_risk),
            "claim_boundary": self.claim_boundary,
            "progress_summary": dict(self.progress_summary),
            "artifact_paths": list(self.artifact_paths),
            "children": [child.to_dict() for child in self.children],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self, *, full: bool = False, max_findings: int = 5) -> str:
        lines = [
            f"status: {self.status}",
            f"scope: {self.scope}" + (f" tier={self.tier}" if self.tier else ""),
            "counts: " + " ".join(f"{key}={value}" for key, value in sorted(self.counts.items())),
        ]
        failures: Sequence[Mapping[str, Any] | str] = self.failures if full else self.failures[:max_findings]
        blockers: Sequence[Mapping[str, Any] | str] = self.blockers if full else self.blockers[:max_findings]
        for item in failures:
            lines.append(f"failure: {_finding_text(item)}")
        for item in blockers:
            lines.append(f"blocker: {_finding_text(item)}")
        for item in self.skipped_checks if full else self.skipped_checks[:max_findings]:
            lines.append(f"skipped: {item.check_id}: {item.reason}; impact={item.impact}")
        if not full and len(self.failures) + len(self.blockers) > 2 * max_findings:
            lines.append("more_findings: use --full or inspect artifact paths")
        for path in self.artifact_paths:
            lines.append(f"artifact: {path}")
        if full:
            for child in self.children:
                lines.append(f"child: {child.child_id}: {child.status}: {child.summary}")
            for risk in self.residual_risk:
                lines.append(f"residual_risk: {risk}")
        lines.append(f"claim_boundary: {self.claim_boundary}")
        return "\n".join(lines)


def _finding_text(value: Mapping[str, Any] | str) -> str:
    if isinstance(value, str):
        return value
    return str(value.get("message") or value.get("code") or json.dumps(value, sort_keys=True))


def aggregate_status(children: Sequence[ValidationChildResult], *, required_child_ids: Sequence[str] = ()) -> str:
    by_id = {child.child_id: child for child in children}
    if any(child_id not in by_id for child_id in required_child_ids):
        return VALIDATION_STATUS_BLOCKED
    statuses = {child.status for child in children}
    if not statuses or statuses == {VALIDATION_STATUS_PASS}:
        return VALIDATION_STATUS_PASS
    if VALIDATION_STATUS_INTERNAL_ERROR in statuses:
        return VALIDATION_STATUS_INTERNAL_ERROR
    if VALIDATION_STATUS_CANCELLED in statuses:
        return VALIDATION_STATUS_CANCELLED
    if VALIDATION_STATUS_TIMEOUT in statuses:
        return VALIDATION_STATUS_TIMEOUT
    if VALIDATION_STATUS_INVALID_INPUT in statuses:
        return VALIDATION_STATUS_INVALID_INPUT
    if VALIDATION_STATUS_BLOCKED in statuses:
        return VALIDATION_STATUS_BLOCKED
    if VALIDATION_STATUS_FAIL in statuses:
        return VALIDATION_STATUS_FAIL
    return VALIDATION_STATUS_PARTIAL


__all__ = [
    "SkippedValidation",
    "VALIDATION_EXIT_CODES",
    "VALIDATION_STATUSES",
    "VALIDATION_STATUS_BLOCKED",
    "VALIDATION_STATUS_CANCELLED",
    "VALIDATION_STATUS_FAIL",
    "VALIDATION_STATUS_INTERNAL_ERROR",
    "VALIDATION_STATUS_INVALID_INPUT",
    "VALIDATION_STATUS_PARTIAL",
    "VALIDATION_STATUS_PASS",
    "VALIDATION_STATUS_TIMEOUT",
    "ValidationChildResult",
    "ValidationResult",
    "aggregate_status",
]
