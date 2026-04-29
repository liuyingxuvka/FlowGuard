"""Lightweight risk profile declarations for model-first checks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


KNOWN_RISK_CLASSES = (
    "deduplication",
    "idempotency",
    "cache",
    "retry",
    "side_effect",
    "queue",
    "loop",
    "module_boundary",
    "conformance",
)

CONFIDENCE_GOALS = (
    "model_level",
    "production_conformance",
    "exploratory",
)

SKIPPED_CHECK_STATUSES = (
    "skipped_with_reason",
    "not_feasible",
    "blocked",
)


@dataclass(frozen=True)
class SkippedCheck:
    """One explicitly skipped model-first check."""

    name: str
    reason: str
    status: str = "skipped_with_reason"
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        status = str(self.status or "skipped_with_reason").strip().lower()
        if status not in SKIPPED_CHECK_STATUSES:
            raise ValueError(f"skipped check status must be one of {SKIPPED_CHECK_STATUSES!r}")
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkippedCheck":
        return cls(
            name=str(data.get("name", "")),
            reason=str(data.get("reason", "")),
            status=str(data.get("status", "skipped_with_reason")),
            metadata=data.get("metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reason": self.reason,
            "status": self.status,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RiskProfile:
    """Small declaration of what a FlowGuard model is trying to cover."""

    modeled_boundary: str
    risk_classes: tuple[str, ...] = ()
    confidence_goal: str = "model_level"
    skipped_checks: tuple[SkippedCheck, ...] = ()
    notes: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __init__(
        self,
        modeled_boundary: str,
        risk_classes: Iterable[str] = (),
        confidence_goal: str = "model_level",
        skipped_checks: Iterable[SkippedCheck | Mapping[str, Any]] | Mapping[str, Any] = (),
        notes: str = "",
        metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
    ) -> None:
        normalized_risks = tuple(
            str(risk).strip().lower()
            for risk in risk_classes
            if str(risk).strip()
        )
        goal = str(confidence_goal or "model_level").strip().lower()
        if goal not in CONFIDENCE_GOALS:
            raise ValueError(f"confidence_goal must be one of {CONFIDENCE_GOALS!r}")
        object.__setattr__(self, "modeled_boundary", str(modeled_boundary))
        object.__setattr__(self, "risk_classes", normalized_risks)
        object.__setattr__(self, "confidence_goal", goal)
        object.__setattr__(self, "skipped_checks", _normalize_skipped_checks(skipped_checks))
        object.__setattr__(self, "notes", str(notes or ""))
        object.__setattr__(self, "metadata", freeze_metadata(metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RiskProfile":
        return cls(
            modeled_boundary=str(data.get("modeled_boundary", "")),
            risk_classes=tuple(data.get("risk_classes", ()) or ()),
            confidence_goal=str(data.get("confidence_goal", "model_level")),
            skipped_checks=data.get("skipped_checks", ()) or (),
            notes=str(data.get("notes", "")),
            metadata=data.get("metadata"),
        )

    @property
    def unknown_risk_classes(self) -> tuple[str, ...]:
        return tuple(
            risk
            for risk in self.risk_classes
            if risk not in KNOWN_RISK_CLASSES
        )

    @property
    def validation_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if not self.modeled_boundary.strip():
            warnings.append("modeled_boundary is empty")
        if self.unknown_risk_classes:
            warnings.append(f"unknown risk_classes: {self.unknown_risk_classes!r}")
        for skipped in self.skipped_checks:
            if not skipped.reason.strip():
                warnings.append(f"skipped check {skipped.name!r} has no reason")
        return tuple(warnings)

    def format_text(self) -> str:
        lines = [
            "=== flowguard risk profile ===",
            f"modeled_boundary: {self.modeled_boundary or '(unspecified)'}",
            f"confidence_goal: {self.confidence_goal}",
            f"risk_classes: {', '.join(self.risk_classes) if self.risk_classes else '(none)'}",
        ]
        if self.notes:
            lines.append(f"notes: {self.notes}")
        if self.skipped_checks:
            lines.append("skipped_checks:")
            for skipped in self.skipped_checks:
                lines.append(f"  - {skipped.name}: {skipped.status}; {skipped.reason}")
        if self.validation_warnings:
            lines.append("warnings:")
            for warning in self.validation_warnings:
                lines.append(f"  - {warning}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "modeled_boundary": self.modeled_boundary,
            "risk_classes": list(self.risk_classes),
            "confidence_goal": self.confidence_goal,
            "skipped_checks": [skipped.to_dict() for skipped in self.skipped_checks],
            "notes": self.notes,
            "metadata": to_jsonable(self.metadata),
            "known_risk_classes": list(KNOWN_RISK_CLASSES),
            "unknown_risk_classes": list(self.unknown_risk_classes),
            "validation_warnings": list(self.validation_warnings),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _normalize_skipped_checks(
    skipped_checks: Iterable[SkippedCheck | Mapping[str, Any]] | Mapping[str, Any],
) -> tuple[SkippedCheck, ...]:
    if isinstance(skipped_checks, Mapping):
        items = (
            {"name": name, "reason": reason, "status": "skipped_with_reason"}
            for name, reason in skipped_checks.items()
        )
    else:
        items = skipped_checks
    normalized = []
    for item in items:
        if isinstance(item, SkippedCheck):
            normalized.append(item)
        elif isinstance(item, Mapping):
            normalized.append(SkippedCheck.from_dict(item))
        else:
            raise TypeError("skipped_checks must contain SkippedCheck objects or mappings")
    return tuple(normalized)


__all__ = [
    "CONFIDENCE_GOALS",
    "KNOWN_RISK_CLASSES",
    "SKIPPED_CHECK_STATUSES",
    "RiskProfile",
    "SkippedCheck",
]
