"""Conditional assumption cards for model-first reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


TextItems = str | Sequence[str] | None


@dataclass(frozen=True)
class ConditionalAssumption:
    """One explicit assumption used to bound an analysis or comparison."""

    name: str
    fixed: str
    boundary: str
    preconditions: tuple[str, ...]
    why_not_modeled: str
    rationale: str
    invalidated_by: tuple[str, ...]
    checks: tuple[str, ...]
    scope: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __init__(
        self,
        name: str,
        fixed: str,
        *,
        boundary: str,
        preconditions: TextItems,
        why_not_modeled: str,
        rationale: str,
        invalidated_by: TextItems,
        checks: TextItems,
        scope: str = "",
        metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
    ) -> None:
        object.__setattr__(self, "name", _required_text(name, "name"))
        object.__setattr__(self, "fixed", _required_text(fixed, "fixed"))
        object.__setattr__(self, "boundary", _required_text(boundary, "boundary"))
        object.__setattr__(self, "preconditions", _required_items(preconditions, "preconditions"))
        object.__setattr__(self, "why_not_modeled", _required_text(why_not_modeled, "why_not_modeled"))
        object.__setattr__(self, "rationale", _required_text(rationale, "rationale"))
        object.__setattr__(self, "invalidated_by", _required_items(invalidated_by, "invalidated_by"))
        object.__setattr__(self, "checks", _required_items(checks, "checks"))
        object.__setattr__(self, "scope", str(scope or ""))
        object.__setattr__(self, "metadata", freeze_metadata(metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConditionalAssumption":
        return cls(
            name=str(data.get("name", "")),
            fixed=str(data.get("fixed", "")),
            boundary=str(data.get("boundary", "")),
            preconditions=_text_items_from_mapping(data, "preconditions"),
            why_not_modeled=str(data.get("why_not_modeled", "")),
            rationale=str(data.get("rationale", "")),
            invalidated_by=_text_items_from_mapping(data, "invalidated_by"),
            checks=_text_items_from_mapping(data, "checks"),
            scope=str(data.get("scope", "")),
            metadata=data.get("metadata"),
        )

    def format_text(self, *, index: int | None = None) -> str:
        prefix = f"{index}. " if index is not None else ""
        lines = [
            f"{prefix}{self.name}",
            f"   fixed: {self.fixed}",
            f"   boundary: {self.boundary}",
        ]
        if self.scope:
            lines.append(f"   scope: {self.scope}")
        lines.extend(_format_item_lines("preconditions", self.preconditions))
        lines.append(f"   why_not_modeled: {self.why_not_modeled}")
        lines.append(f"   rationale: {self.rationale}")
        lines.extend(_format_item_lines("invalidated_by", self.invalidated_by))
        lines.extend(_format_item_lines("checks", self.checks))
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fixed": self.fixed,
            "boundary": self.boundary,
            "preconditions": list(self.preconditions),
            "why_not_modeled": self.why_not_modeled,
            "rationale": self.rationale,
            "invalidated_by": list(self.invalidated_by),
            "checks": list(self.checks),
            "scope": self.scope,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class AssumptionCard:
    """Visible assumptions attached to a FlowGuard plan or check report."""

    assumptions: tuple[ConditionalAssumption, ...] = ()
    title: str = "Conditional Assumptions"
    purpose: str = "conditional_equivalence"
    checked_scope: tuple[str, ...] = ()
    not_covered: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __init__(
        self,
        assumptions: Sequence[ConditionalAssumption | Mapping[str, Any]] = (),
        *,
        title: str = "Conditional Assumptions",
        purpose: str = "conditional_equivalence",
        checked_scope: TextItems = (),
        not_covered: TextItems = (),
        metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
    ) -> None:
        assumption_items = tuple(_coerce_assumption(item) for item in assumptions)
        _raise_on_duplicate_assumption_names(assumption_items)
        object.__setattr__(self, "assumptions", assumption_items)
        object.__setattr__(self, "title", _required_text(title, "title"))
        object.__setattr__(self, "purpose", _required_text(purpose, "purpose"))
        object.__setattr__(self, "checked_scope", _normalize_items(checked_scope))
        object.__setattr__(self, "not_covered", _normalize_items(not_covered))
        object.__setattr__(self, "metadata", freeze_metadata(metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssumptionCard":
        return cls(
            assumptions=tuple(data.get("assumptions", ()) or ()),
            title=str(data.get("title", "Conditional Assumptions")),
            purpose=str(data.get("purpose", "conditional_equivalence")),
            checked_scope=_text_items_from_mapping(data, "checked_scope"),
            not_covered=_text_items_from_mapping(data, "not_covered"),
            metadata=data.get("metadata"),
        )

    def format_text(self) -> str:
        lines = [
            f"=== {self.title} ===",
            f"purpose: {self.purpose}",
        ]
        if self.checked_scope:
            lines.extend(_format_item_lines("checked_scope", self.checked_scope))
        if self.assumptions:
            lines.append("assumptions:")
            for index, item in enumerate(self.assumptions, start=1):
                lines.append(item.format_text(index=index))
        else:
            lines.append("assumptions: none")
        if self.not_covered:
            lines.extend(_format_item_lines("not_covered", self.not_covered))
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "purpose": self.purpose,
            "checked_scope": list(self.checked_scope),
            "assumptions": [item.to_dict() for item in self.assumptions],
            "not_covered": list(self.not_covered),
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def conditional_assumption(
    name: str,
    fixed: str,
    *,
    boundary: str,
    preconditions: TextItems,
    why_not_modeled: str,
    rationale: str,
    invalidated_by: TextItems,
    checks: TextItems,
    scope: str = "",
    metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
) -> ConditionalAssumption:
    """Build a validated conditional assumption."""

    return ConditionalAssumption(
        name=name,
        fixed=fixed,
        boundary=boundary,
        preconditions=preconditions,
        why_not_modeled=why_not_modeled,
        rationale=rationale,
        invalidated_by=invalidated_by,
        checks=checks,
        scope=scope,
        metadata=metadata,
    )


def assumption_card(
    assumptions: Sequence[ConditionalAssumption | Mapping[str, Any]] = (),
    *,
    title: str = "Conditional Assumptions",
    purpose: str = "conditional_equivalence",
    checked_scope: TextItems = (),
    not_covered: TextItems = (),
    metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
) -> AssumptionCard:
    """Build a visible assumption card for a model-first report."""

    return AssumptionCard(
        assumptions=assumptions,
        title=title,
        purpose=purpose,
        checked_scope=checked_scope,
        not_covered=not_covered,
        metadata=metadata,
    )


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _normalize_items(value: TextItems) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _required_items(value: TextItems, field_name: str) -> tuple[str, ...]:
    items = _normalize_items(value)
    if not items:
        raise ValueError(f"{field_name} must include at least one item")
    return items


def _text_items_from_mapping(data: Mapping[str, Any], key: str) -> TextItems:
    value = data.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        return value
    return tuple(value)


def _coerce_assumption(value: ConditionalAssumption | Mapping[str, Any]) -> ConditionalAssumption:
    if isinstance(value, ConditionalAssumption):
        return value
    if isinstance(value, Mapping):
        return ConditionalAssumption.from_dict(value)
    raise TypeError("assumptions must be ConditionalAssumption objects or mappings")


def _raise_on_duplicate_assumption_names(assumptions: tuple[ConditionalAssumption, ...]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in assumptions:
        if item.name in seen:
            duplicates.append(item.name)
        seen.add(item.name)
    if duplicates:
        raise ValueError(f"duplicate assumption names: {tuple(duplicates)!r}")


def _format_item_lines(label: str, values: tuple[str, ...]) -> list[str]:
    if not values:
        return []
    lines = [f"   {label}:"]
    lines.extend(f"   - {value}" for value in values)
    return lines


__all__ = [
    "AssumptionCard",
    "ConditionalAssumption",
    "assumption_card",
    "conditional_assumption",
]
