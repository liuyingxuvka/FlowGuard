"""UI interaction flow and model-derived structure helpers.

UI flow structure keeps UI design model-first. It first reviews a UI-level
interaction model, then reviews a structure derivation that maps that model to
regions, menu levels, parent/child nodes, overlays, stable placements, and
intentional display/control redundancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_pairs(values: Sequence[tuple[str, str]] | None) -> tuple[tuple[str, str], ...]:
    if values is None:
        return ()
    return tuple((str(left), str(right)) for left, right in values)


def _pair_map(pairs: Sequence[tuple[str, str]]) -> dict[str, str]:
    return {str(key): str(value) for key, value in pairs}


@dataclass(frozen=True)
class UIControl:
    """One visible or invokable control in a UI interaction model."""

    control_id: str
    label: str = ""
    control_type: str = "button"
    level: str = "contextual"
    placement_hint: str = ""
    persistent: bool = False
    destructive: bool = False
    depends_on_states: tuple[str, ...] = ()
    rationale: str = ""
    function_key: str = ""
    duplicate_group: str = ""
    redundancy_rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "control_type", str(self.control_type))
        object.__setattr__(self, "level", str(self.level))
        object.__setattr__(self, "function_key", str(self.function_key))
        object.__setattr__(self, "placement_hint", str(self.placement_hint))
        object.__setattr__(self, "persistent", bool(self.persistent))
        object.__setattr__(self, "destructive", bool(self.destructive))
        object.__setattr__(self, "depends_on_states", _as_tuple(self.depends_on_states))
        object.__setattr__(self, "duplicate_group", str(self.duplicate_group))
        object.__setattr__(self, "redundancy_rationale", str(self.redundancy_rationale))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "label": self.label,
            "control_type": self.control_type,
            "level": self.level,
            "function_key": self.function_key,
            "placement_hint": self.placement_hint,
            "persistent": self.persistent,
            "destructive": self.destructive,
            "depends_on_states": list(self.depends_on_states),
            "duplicate_group": self.duplicate_group,
            "redundancy_rationale": self.redundancy_rationale,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIStateNode:
    """One abstract UI state such as empty, dialog open, running, or result ready."""

    state_id: str
    parent_state_id: str = ""
    role: str = "normal"
    visible_controls: tuple[str, ...] = ()
    enabled_controls: tuple[str, ...] = ()
    disabled_controls: tuple[str, ...] = ()
    hidden_controls: tuple[str, ...] = ()
    recovery_controls: tuple[str, ...] = ()
    terminal: bool = False
    failure: bool = False
    rationale: str = ""
    visible_displays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", str(self.state_id))
        object.__setattr__(self, "parent_state_id", str(self.parent_state_id))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "visible_controls", _as_tuple(self.visible_controls))
        object.__setattr__(self, "visible_displays", _as_tuple(self.visible_displays))
        object.__setattr__(self, "enabled_controls", _as_tuple(self.enabled_controls))
        object.__setattr__(self, "disabled_controls", _as_tuple(self.disabled_controls))
        object.__setattr__(self, "hidden_controls", _as_tuple(self.hidden_controls))
        object.__setattr__(self, "recovery_controls", _as_tuple(self.recovery_controls))
        object.__setattr__(self, "terminal", bool(self.terminal))
        object.__setattr__(self, "failure", bool(self.failure))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_availability(self) -> bool:
        return bool(
            self.visible_controls
            or self.enabled_controls
            or self.disabled_controls
            or self.hidden_controls
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "parent_state_id": self.parent_state_id,
            "role": self.role,
            "visible_controls": list(self.visible_controls),
            "visible_displays": list(self.visible_displays),
            "enabled_controls": list(self.enabled_controls),
            "disabled_controls": list(self.disabled_controls),
            "hidden_controls": list(self.hidden_controls),
            "recovery_controls": list(self.recovery_controls),
            "terminal": self.terminal,
            "failure": self.failure,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UITransition:
    """One modeled UI event transition."""

    event_id: str
    control_id: str
    source_state_id: str
    target_state_id: str
    function_block: str = ""
    output: str = ""
    side_effects: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "source_state_id", str(self.source_state_id))
        object.__setattr__(self, "target_state_id", str(self.target_state_id))
        object.__setattr__(self, "function_block", str(self.function_block))
        object.__setattr__(self, "output", str(self.output))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "control_id": self.control_id,
            "source_state_id": self.source_state_id,
            "target_state_id": self.target_state_id,
            "function_block": self.function_block,
            "output": self.output,
            "side_effects": list(self.side_effects),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIDisplayElement:
    """One modeled information element shown by the UI."""

    display_id: str
    semantic_key: str
    label: str = ""
    display_type: str = "text"
    depends_on_states: tuple[str, ...] = ()
    region_hint: str = ""
    duplicate_group: str = ""
    redundancy_rationale: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_id", str(self.display_id))
        object.__setattr__(self, "semantic_key", str(self.semantic_key))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "display_type", str(self.display_type))
        object.__setattr__(self, "depends_on_states", _as_tuple(self.depends_on_states))
        object.__setattr__(self, "region_hint", str(self.region_hint))
        object.__setattr__(self, "duplicate_group", str(self.duplicate_group))
        object.__setattr__(self, "redundancy_rationale", str(self.redundancy_rationale))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "display_id": self.display_id,
            "semantic_key": self.semantic_key,
            "label": self.label,
            "display_type": self.display_type,
            "depends_on_states": list(self.depends_on_states),
            "region_hint": self.region_hint,
            "duplicate_group": self.duplicate_group,
            "redundancy_rationale": self.redundancy_rationale,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIInteractionModel:
    """UI-level interaction model used before deriving interface structure."""

    model_id: str
    initial_state_id: str
    states: tuple[UIStateNode, ...] = ()
    controls: tuple[UIControl, ...] = ()
    transitions: tuple[UITransition, ...] = ()
    displays: tuple[UIDisplayElement, ...] = ()
    source_product_model_id: str = ""
    source_product_model_path: str = ""
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "initial_state_id", str(self.initial_state_id))
        object.__setattr__(self, "states", tuple(self.states))
        object.__setattr__(self, "controls", tuple(self.controls))
        object.__setattr__(self, "transitions", tuple(self.transitions))
        object.__setattr__(self, "displays", tuple(self.displays))
        object.__setattr__(self, "source_product_model_id", str(self.source_product_model_id))
        object.__setattr__(self, "source_product_model_path", str(self.source_product_model_path))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def state_ids(self) -> tuple[str, ...]:
        return tuple(state.state_id for state in self.states)

    def control_ids(self) -> tuple[str, ...]:
        return tuple(control.control_id for control in self.controls)

    def transition_event_ids(self) -> tuple[str, ...]:
        return tuple(transition.event_id for transition in self.transitions)

    def display_ids(self) -> tuple[str, ...]:
        return tuple(display.display_id for display in self.displays)

    def controls_by_id(self) -> dict[str, UIControl]:
        return {control.control_id: control for control in self.controls}

    def displays_by_id(self) -> dict[str, UIDisplayElement]:
        return {display.display_id: display for display in self.displays}

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "initial_state_id": self.initial_state_id,
            "states": [state.to_dict() for state in self.states],
            "controls": [control.to_dict() for control in self.controls],
            "displays": [display.to_dict() for display in self.displays],
            "transitions": [transition.to_dict() for transition in self.transitions],
            "source_product_model_id": self.source_product_model_id,
            "source_product_model_path": self.source_product_model_path,
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIRegionRecommendation:
    """One UI region, menu level, panel, overlay, or child component boundary."""

    region_id: str
    level: str = "secondary"
    placement: str = ""
    parent_region_id: str = ""
    owns_states: tuple[str, ...] = ()
    owns_controls: tuple[str, ...] = ()
    owns_events: tuple[str, ...] = ()
    stable_across_states: bool = False
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""
    owns_displays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "region_id", str(self.region_id))
        object.__setattr__(self, "level", str(self.level))
        object.__setattr__(self, "placement", str(self.placement))
        object.__setattr__(self, "parent_region_id", str(self.parent_region_id))
        object.__setattr__(self, "owns_states", _as_tuple(self.owns_states))
        object.__setattr__(self, "owns_controls", _as_tuple(self.owns_controls))
        object.__setattr__(self, "owns_displays", _as_tuple(self.owns_displays))
        object.__setattr__(self, "owns_events", _as_tuple(self.owns_events))
        object.__setattr__(self, "stable_across_states", bool(self.stable_across_states))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "level": self.level,
            "placement": self.placement,
            "parent_region_id": self.parent_region_id,
            "owns_states": list(self.owns_states),
            "owns_controls": list(self.owns_controls),
            "owns_displays": list(self.owns_displays),
            "owns_events": list(self.owns_events),
            "stable_across_states": self.stable_across_states,
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIStructureDerivation:
    """UI structure derived from a reviewed UI interaction model."""

    derivation_id: str
    source_interaction_model_id: str
    parent_surface_id: str
    target_regions: tuple[UIRegionRecommendation, ...] = ()
    interaction_model_reviewed: bool = False
    state_region_map: tuple[tuple[str, str], ...] = ()
    control_region_map: tuple[tuple[str, str], ...] = ()
    event_region_map: tuple[tuple[str, str], ...] = ()
    display_region_map: tuple[tuple[str, str], ...] = ()
    hierarchy_edges: tuple[tuple[str, str], ...] = ()
    persistent_control_ids: tuple[str, ...] = ()
    contextual_control_ids: tuple[str, ...] = ()
    overlay_region_ids: tuple[str, ...] = ()
    stable_region_ids: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "derivation_id", str(self.derivation_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "parent_surface_id", str(self.parent_surface_id))
        object.__setattr__(self, "target_regions", tuple(self.target_regions))
        object.__setattr__(self, "interaction_model_reviewed", bool(self.interaction_model_reviewed))
        object.__setattr__(self, "state_region_map", _as_pairs(self.state_region_map))
        object.__setattr__(self, "control_region_map", _as_pairs(self.control_region_map))
        object.__setattr__(self, "event_region_map", _as_pairs(self.event_region_map))
        object.__setattr__(self, "display_region_map", _as_pairs(self.display_region_map))
        object.__setattr__(self, "hierarchy_edges", _as_pairs(self.hierarchy_edges))
        object.__setattr__(self, "persistent_control_ids", _as_tuple(self.persistent_control_ids))
        object.__setattr__(self, "contextual_control_ids", _as_tuple(self.contextual_control_ids))
        object.__setattr__(self, "overlay_region_ids", _as_tuple(self.overlay_region_ids))
        object.__setattr__(self, "stable_region_ids", _as_tuple(self.stable_region_ids))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def region_ids(self) -> tuple[str, ...]:
        return tuple(region.region_id for region in self.target_regions)

    def state_regions(self) -> dict[str, str]:
        return _pair_map(self.state_region_map)

    def control_regions(self) -> dict[str, str]:
        return _pair_map(self.control_region_map)

    def display_regions(self) -> dict[str, str]:
        return _pair_map(self.display_region_map)

    def event_regions(self) -> dict[str, str]:
        return _pair_map(self.event_region_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "derivation_id": self.derivation_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "parent_surface_id": self.parent_surface_id,
            "target_regions": [region.to_dict() for region in self.target_regions],
            "interaction_model_reviewed": self.interaction_model_reviewed,
            "state_region_map": [list(pair) for pair in self.state_region_map],
            "control_region_map": [list(pair) for pair in self.control_region_map],
            "display_region_map": [list(pair) for pair in self.display_region_map],
            "event_region_map": [list(pair) for pair in self.event_region_map],
            "hierarchy_edges": [list(pair) for pair in self.hierarchy_edges],
            "persistent_control_ids": list(self.persistent_control_ids),
            "contextual_control_ids": list(self.contextual_control_ids),
            "overlay_region_ids": list(self.overlay_region_ids),
            "stable_region_ids": list(self.stable_region_ids),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIFlowStructureFinding:
    """One finding from reviewing a UI interaction model or structure derivation."""

    code: str
    message: str
    severity: str = "blocker"
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class UIInteractionModelReport:
    """Structured review result for a UI interaction model."""

    ok: bool
    model_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_interaction_model={self.model_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI interaction model review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"model: {self.model_id}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "model_id": self.model_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIStructureDerivationReport:
    """Structured review result for a UI structure derivation."""

    ok: bool
    derivation_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "derivation_id", str(self.derivation_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_structure_derivation={self.derivation_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI structure derivation review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"derivation: {self.derivation_id}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "derivation_id": self.derivation_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _blocker_findings(findings: Sequence[UIFlowStructureFinding]) -> tuple[UIFlowStructureFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _duplicate_values(values: Sequence[str], *, code: str, noun: str) -> list[UIFlowStructureFinding]:
    findings: list[UIFlowStructureFinding] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    for value in sorted(duplicates):
        findings.append(
            UIFlowStructureFinding(
                code,
                f"{noun} {value} is declared more than once",
                item_id=value,
            )
        )
    return findings


def _duplicate_pair_keys(
    pairs: Sequence[tuple[str, str]],
    *,
    code: str,
    noun: str,
) -> list[UIFlowStructureFinding]:
    findings: list[UIFlowStructureFinding] = []
    owners: dict[str, list[str]] = {}
    for item_id, region_id in pairs:
        owners.setdefault(item_id, []).append(region_id)
    for item_id, region_ids in sorted(owners.items()):
        if len(set(region_ids)) > 1:
            findings.append(
                UIFlowStructureFinding(
                    code,
                    f"{noun} {item_id} has multiple recommended regions",
                    item_id=item_id,
                    metadata={"regions": sorted(set(region_ids))},
                )
            )
    return findings


def _redundancy_justified(items: Sequence[Any]) -> bool:
    if any(getattr(item, "redundancy_rationale", "") for item in items):
        return True
    duplicate_groups = {
        getattr(item, "duplicate_group", "")
        for item in items
        if getattr(item, "duplicate_group", "")
    }
    return len(duplicate_groups) == 1


def review_ui_interaction_model(model: UIInteractionModel) -> UIInteractionModelReport:
    """Review whether a UI interaction model is complete enough for derivation."""

    findings: list[UIFlowStructureFinding] = []
    state_ids = set(model.state_ids())
    control_ids = set(model.control_ids())
    display_ids = set(model.display_ids())
    controls_by_id = model.controls_by_id()
    displays_by_id = model.displays_by_id()
    event_control_ids = {transition.control_id for transition in model.transitions}
    outgoing_by_state: dict[str, list[UITransition]] = {}
    transitions_by_state_control: dict[tuple[str, str], list[UITransition]] = {}
    for transition in model.transitions:
        outgoing_by_state.setdefault(transition.source_state_id, []).append(transition)
        transitions_by_state_control.setdefault((transition.source_state_id, transition.control_id), []).append(
            transition
        )

    if not model.model_id:
        findings.append(UIFlowStructureFinding("missing_model_id", "UI interaction model has no model id"))
    if not model.initial_state_id:
        findings.append(
            UIFlowStructureFinding("missing_initial_state", "UI interaction model has no initial UI state")
        )
    elif model.initial_state_id not in state_ids:
        findings.append(
            UIFlowStructureFinding(
                "initial_state_not_registered",
                f"initial state {model.initial_state_id} is not in the state list",
                item_id=model.initial_state_id,
            )
        )
    if not model.states:
        findings.append(UIFlowStructureFinding("missing_states", "UI interaction model has no UI states"))
    if not model.controls:
        findings.append(UIFlowStructureFinding("missing_controls", "UI interaction model has no controls"))
    if not model.transitions:
        findings.append(UIFlowStructureFinding("missing_transitions", "UI interaction model has no transitions"))
    if not any(state.has_availability() for state in model.states):
        findings.append(
            UIFlowStructureFinding(
                "missing_state_availability_matrix",
                "UI states do not declare visible, enabled, disabled, or hidden controls",
            )
        )
    if not model.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_validation_plan", "UI interaction model has no validation boundaries")
        )
    if not model.rationale:
        findings.append(
            UIFlowStructureFinding("missing_model_rationale", "UI interaction model has no modeling rationale")
        )

    findings.extend(_duplicate_values(model.state_ids(), code="duplicate_state_id", noun="state"))
    findings.extend(_duplicate_values(model.control_ids(), code="duplicate_control_id", noun="control"))
    findings.extend(_duplicate_values(model.display_ids(), code="duplicate_display_id", noun="display"))
    findings.extend(_duplicate_values(model.transition_event_ids(), code="duplicate_event_id", noun="event"))

    for state in model.states:
        if state.parent_state_id and state.parent_state_id not in state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "parent_state_not_registered",
                    f"state {state.state_id} references unknown parent state {state.parent_state_id}",
                    item_id=state.state_id,
                )
            )
        for control_id in (
            state.visible_controls
            + state.enabled_controls
            + state.disabled_controls
            + state.hidden_controls
            + state.recovery_controls
        ):
            if control_id not in control_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "state_control_not_registered",
                        f"state {state.state_id} references unknown control {control_id}",
                        item_id=control_id,
                    )
                )
        for display_id in state.visible_displays:
            if display_id not in display_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "state_display_not_registered",
                        f"state {state.state_id} references unknown display {display_id}",
                        item_id=display_id,
                    )
                )
        if state.failure and not state.terminal and not state.recovery_controls and not outgoing_by_state.get(state.state_id):
            findings.append(
                UIFlowStructureFinding(
                    "missing_failure_recovery",
                    f"recoverable failure state {state.state_id} has no recovery control or outgoing transition",
                    item_id=state.state_id,
                )
            )

    for control in model.controls:
        if control.destructive and control.level in {"primary", "global"}:
            findings.append(
                UIFlowStructureFinding(
                    "destructive_control_too_prominent",
                    f"destructive control {control.control_id} is marked as {control.level}",
                    item_id=control.control_id,
                )
            )
        if (
            control.control_type not in {"display", "label", "status"}
            and not control.persistent
            and control.control_id not in event_control_ids
        ):
            findings.append(
                UIFlowStructureFinding(
                    "unmodeled_control_event",
                    f"control {control.control_id} has no modeled event transition",
                    item_id=control.control_id,
                )
            )
        if (
            not control.function_key
            and not control.persistent
            and control.control_type not in {"display", "label", "status"}
        ):
            transition_keys = [
                transition.function_block or transition.output
                for transition in model.transitions
                if transition.control_id == control.control_id
            ]
            if not any(transition_keys):
                findings.append(
                    UIFlowStructureFinding(
                        "missing_control_function_key",
                        f"control {control.control_id} has no function key or modeled action",
                        item_id=control.control_id,
                    )
                )
        for state_id in control.depends_on_states:
            if state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "control_dependency_state_not_registered",
                        f"control {control.control_id} depends on unknown state {state_id}",
                        item_id=control.control_id,
                    )
                )

    for display in model.displays:
        if not display.semantic_key:
            findings.append(
                UIFlowStructureFinding(
                    "missing_display_semantic_key",
                    f"display {display.display_id} has no semantic key for duplicate-information review",
                    item_id=display.display_id,
                )
            )
        if not display.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_display_rationale",
                    f"display {display.display_id} has no information-purpose rationale",
                    item_id=display.display_id,
                )
            )
        for state_id in display.depends_on_states:
            if state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "display_dependency_state_not_registered",
                        f"display {display.display_id} depends on unknown state {state_id}",
                        item_id=display.display_id,
                    )
                )

    for state in model.states:
        display_ids_for_state = set(state.visible_displays)
        for display in model.displays:
            if state.state_id in display.depends_on_states:
                display_ids_for_state.add(display.display_id)
        displays_by_semantic: dict[str, list[UIDisplayElement]] = {}
        for display_id in display_ids_for_state:
            display = displays_by_id.get(display_id)
            if display is not None and display.semantic_key:
                displays_by_semantic.setdefault(display.semantic_key, []).append(display)
        for semantic_key, displays in sorted(displays_by_semantic.items()):
            if len(displays) > 1 and not _redundancy_justified(displays):
                findings.append(
                    UIFlowStructureFinding(
                        "duplicate_information_same_state",
                        f"state {state.state_id} shows semantic information {semantic_key} more than once without a redundancy rationale",
                        item_id=state.state_id,
                        metadata={"display_ids": sorted(display.display_id for display in displays)},
                    )
                )

        action_groups: dict[tuple[str, str], set[str]] = {}
        active_controls = state.enabled_controls or state.visible_controls
        for control_id in active_controls:
            control = controls_by_id.get(control_id)
            if control is None:
                continue
            transitions = transitions_by_state_control.get((state.state_id, control_id), ())
            action_keys = {
                control.function_key or transition.function_block or transition.output
                for transition in transitions
                if control.function_key or transition.function_block or transition.output
            }
            if not action_keys and control.function_key:
                action_keys = {control.function_key}
            for action_key in action_keys:
                action_groups.setdefault((control.level, action_key), set()).add(control_id)
        for (level, action_key), grouped_control_ids in sorted(action_groups.items()):
            if len(grouped_control_ids) <= 1:
                continue
            grouped_controls = [controls_by_id[control_id] for control_id in sorted(grouped_control_ids)]
            if not _redundancy_justified(grouped_controls):
                findings.append(
                    UIFlowStructureFinding(
                        "duplicate_control_function_same_state_level",
                        f"state {state.state_id} has multiple {level} controls for function {action_key} without a redundancy rationale",
                        item_id=state.state_id,
                        metadata={"control_ids": sorted(grouped_control_ids), "function_key": action_key},
                    )
                )

    for transition in model.transitions:
        if transition.control_id not in control_ids:
            findings.append(
                UIFlowStructureFinding(
                    "transition_control_not_registered",
                    f"transition {transition.event_id} references unknown control {transition.control_id}",
                    item_id=transition.event_id,
                )
            )
        if transition.source_state_id not in state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "transition_source_state_not_registered",
                    f"transition {transition.event_id} references unknown source state {transition.source_state_id}",
                    item_id=transition.event_id,
                )
            )
        if transition.target_state_id not in state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "transition_target_state_not_registered",
                    f"transition {transition.event_id} references unknown target state {transition.target_state_id}",
                    item_id=transition.event_id,
                )
            )
        if not transition.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_transition_rationale",
                    f"transition {transition.event_id} has no modeled-effect rationale",
                    item_id=transition.event_id,
                )
            )

    blockers = _blocker_findings(findings)
    return UIInteractionModelReport(
        ok=not blockers,
        model_id=model.model_id,
        findings=tuple(findings),
    )


def review_ui_structure_derivation(
    derivation: UIStructureDerivation,
    *,
    interaction_model: UIInteractionModel | None = None,
) -> UIStructureDerivationReport:
    """Review whether UI structure follows from a reviewed UI interaction model."""

    findings: list[UIFlowStructureFinding] = []
    region_ids = set(derivation.region_ids())
    region_by_id = {region.region_id: region for region in derivation.target_regions}

    if not derivation.source_interaction_model_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_interaction_model",
                "UI structure derivation has no source UI interaction model id",
            )
        )
    if interaction_model is not None and derivation.source_interaction_model_id != interaction_model.model_id:
        findings.append(
            UIFlowStructureFinding(
                "source_interaction_model_mismatch",
                "UI structure derivation does not reference the supplied interaction model",
                metadata={
                    "derivation_source": derivation.source_interaction_model_id,
                    "interaction_model": interaction_model.model_id,
                },
            )
        )
    if not derivation.interaction_model_reviewed:
        findings.append(
            UIFlowStructureFinding(
                "source_interaction_model_not_reviewed",
                "UI structure was derived before the UI interaction model was marked reviewed",
            )
        )
    if not derivation.parent_surface_id:
        findings.append(
            UIFlowStructureFinding("missing_parent_surface", "UI structure derivation has no parent UI surface")
        )
    if not derivation.target_regions:
        findings.append(UIFlowStructureFinding("missing_target_regions", "UI structure derivation has no regions"))
    if not derivation.state_region_map:
        findings.append(
            UIFlowStructureFinding("missing_state_region_map", "UI structure derivation maps no states to regions")
        )
    if not derivation.control_region_map:
        findings.append(
            UIFlowStructureFinding(
                "missing_control_region_map",
                "UI structure derivation maps no controls to menu levels or regions",
            )
        )
    if interaction_model is not None and interaction_model.displays and not derivation.display_region_map:
        findings.append(
            UIFlowStructureFinding(
                "missing_display_region_map",
                "UI structure derivation maps no information displays to regions",
            )
        )
    if not derivation.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_validation_plan", "UI structure derivation has no validation boundaries")
        )
    if not derivation.rationale:
        findings.append(
            UIFlowStructureFinding(
                "missing_structure_rationale",
                "UI structure derivation has no rationale for hierarchy and placement",
            )
        )

    findings.extend(_duplicate_values(derivation.region_ids(), code="duplicate_region_id", noun="region"))
    findings.extend(
        _duplicate_pair_keys(
            derivation.state_region_map,
            code="duplicate_state_region_owner",
            noun="state",
        )
    )
    findings.extend(
        _duplicate_pair_keys(
            derivation.control_region_map,
            code="duplicate_control_region_owner",
            noun="control",
        )
    )
    findings.extend(
        _duplicate_pair_keys(
            derivation.display_region_map,
            code="duplicate_display_region_owner",
            noun="display",
        )
    )
    findings.extend(
        _duplicate_pair_keys(
            derivation.event_region_map,
            code="duplicate_event_region_owner",
            noun="event",
        )
    )

    for region in derivation.target_regions:
        if not region.region_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_region_id",
                    "UI region recommendation has no region id",
                    metadata=region.to_dict(),
                )
            )
        if region.parent_region_id and region.parent_region_id not in region_ids:
            findings.append(
                UIFlowStructureFinding(
                    "parent_region_not_registered",
                    f"region {region.region_id} references unknown parent region {region.parent_region_id}",
                    item_id=region.region_id,
                )
            )
        if not region.placement:
            findings.append(
                UIFlowStructureFinding(
                    "missing_region_placement",
                    f"region {region.region_id} has no placement recommendation",
                    item_id=region.region_id,
                )
            )
        if not region.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_region_rationale",
                    f"region {region.region_id} has no hierarchy or grouping rationale",
                    item_id=region.region_id,
                )
            )
        if region.level == "overlay" and region.placement not in {"modal", "drawer", "popover", "inspector"}:
            findings.append(
                UIFlowStructureFinding(
                    "overlay_region_missing_overlay_placement",
                    f"overlay region {region.region_id} is placed as {region.placement or '(none)'}",
                    item_id=region.region_id,
                )
            )

    for code, noun, pairs in (
        ("state_region_not_registered", "state", derivation.state_region_map),
        ("control_region_not_registered", "control", derivation.control_region_map),
        ("display_region_not_registered", "display", derivation.display_region_map),
        ("event_region_not_registered", "event", derivation.event_region_map),
    ):
        for item_id, region_id in pairs:
            if region_id not in region_ids:
                findings.append(
                    UIFlowStructureFinding(
                        code,
                        f"{noun} {item_id} is assigned to unknown region {region_id}",
                        item_id=item_id,
                    )
                )

    for parent_id, child_id in derivation.hierarchy_edges:
        if parent_id not in region_ids:
            findings.append(
                UIFlowStructureFinding(
                    "hierarchy_parent_not_registered",
                    f"hierarchy edge references unknown parent region {parent_id}",
                    item_id=parent_id,
                )
            )
        if child_id not in region_ids:
            findings.append(
                UIFlowStructureFinding(
                    "hierarchy_child_not_registered",
                    f"hierarchy edge references unknown child region {child_id}",
                    item_id=child_id,
                )
            )

    control_region = derivation.control_regions()
    for control_id in derivation.persistent_control_ids:
        region = region_by_id.get(control_region.get(control_id, ""))
        if region is None or region.level != "global" or not region.stable_across_states:
            findings.append(
                UIFlowStructureFinding(
                    "persistent_control_not_stable_global",
                    f"persistent control {control_id} is not assigned to a stable global region",
                    item_id=control_id,
                )
            )
    for control_id in derivation.contextual_control_ids:
        region = region_by_id.get(control_region.get(control_id, ""))
        if region is not None and region.level == "global":
            findings.append(
                UIFlowStructureFinding(
                    "contextual_control_assigned_global",
                    f"contextual control {control_id} is assigned to a global region",
                    item_id=control_id,
                )
            )
    for region_id in derivation.overlay_region_ids:
        region = region_by_id.get(region_id)
        if region is None:
            findings.append(
                UIFlowStructureFinding(
                    "overlay_region_not_registered",
                    f"overlay region {region_id} is not registered",
                    item_id=region_id,
                )
            )
        elif region.level != "overlay":
            findings.append(
                UIFlowStructureFinding(
                    "overlay_region_wrong_level",
                    f"overlay region {region_id} is declared at level {region.level}",
                    item_id=region_id,
                )
            )
    for region_id in derivation.stable_region_ids:
        region = region_by_id.get(region_id)
        if region is None:
            findings.append(
                UIFlowStructureFinding(
                    "stable_region_not_registered",
                    f"stable region {region_id} is not registered",
                    item_id=region_id,
                )
            )
        elif not region.stable_across_states:
            findings.append(
                UIFlowStructureFinding(
                    "stable_region_not_marked_stable",
                    f"stable region {region_id} is not marked stable across states",
                    item_id=region_id,
                )
            )

    if interaction_model is not None:
        known_states = set(interaction_model.state_ids())
        known_controls = set(interaction_model.control_ids())
        known_displays = set(interaction_model.display_ids())
        known_events = set(interaction_model.transition_event_ids())
        for state_id, _region_id in derivation.state_region_map:
            if state_id not in known_states:
                findings.append(
                    UIFlowStructureFinding(
                        "state_not_in_interaction_model",
                        f"state {state_id} is not in the source interaction model",
                        item_id=state_id,
                    )
                )
        for control_id, _region_id in derivation.control_region_map:
            if control_id not in known_controls:
                findings.append(
                    UIFlowStructureFinding(
                        "control_not_in_interaction_model",
                        f"control {control_id} is not in the source interaction model",
                        item_id=control_id,
                    )
                )
        for display_id, _region_id in derivation.display_region_map:
            if display_id not in known_displays:
                findings.append(
                    UIFlowStructureFinding(
                        "display_not_in_interaction_model",
                        f"display {display_id} is not in the source interaction model",
                        item_id=display_id,
                    )
                )
        for event_id, _region_id in derivation.event_region_map:
            if event_id not in known_events:
                findings.append(
                    UIFlowStructureFinding(
                        "event_not_in_interaction_model",
                        f"event {event_id} is not in the source interaction model",
                        item_id=event_id,
                    )
                )

        displays_by_id = interaction_model.displays_by_id()
        displays_by_region_semantic: dict[tuple[str, str], list[UIDisplayElement]] = {}
        for display_id, region_id in derivation.display_region_map:
            display = displays_by_id.get(display_id)
            if display is not None and display.semantic_key:
                displays_by_region_semantic.setdefault((region_id, display.semantic_key), []).append(display)
        for (region_id, semantic_key), displays in sorted(displays_by_region_semantic.items()):
            if len(displays) > 1 and not _redundancy_justified(displays):
                findings.append(
                    UIFlowStructureFinding(
                        "duplicate_information_same_region",
                        f"region {region_id} shows semantic information {semantic_key} more than once without a redundancy rationale",
                        item_id=region_id,
                        metadata={"display_ids": sorted(display.display_id for display in displays)},
                    )
                )

    blockers = _blocker_findings(findings)
    return UIStructureDerivationReport(
        ok=not blockers,
        derivation_id=derivation.derivation_id,
        findings=tuple(findings),
    )


__all__ = [
    "UIControl",
    "UIDisplayElement",
    "UIFlowStructureFinding",
    "UIInteractionModel",
    "UIInteractionModelReport",
    "UIRegionRecommendation",
    "UIStateNode",
    "UIStructureDerivation",
    "UIStructureDerivationReport",
    "UITransition",
    "review_ui_interaction_model",
    "review_ui_structure_derivation",
]
