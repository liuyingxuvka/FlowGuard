"""UI journeys over declared states, controls and transitions.

The structural review and executable journeys share the same interaction model.
Source comparison checks control identifiers and handler anchors; it does not render a UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .export import to_jsonable



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
    hidden_displays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", str(self.state_id))
        object.__setattr__(self, "parent_state_id", str(self.parent_state_id))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "visible_controls", _as_tuple(self.visible_controls))
        object.__setattr__(self, "visible_displays", _as_tuple(self.visible_displays))
        object.__setattr__(self, "hidden_displays", _as_tuple(self.hidden_displays))
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
            or self.visible_displays
            or self.hidden_displays
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "parent_state_id": self.parent_state_id,
            "role": self.role,
            "visible_controls": list(self.visible_controls),
            "visible_displays": list(self.visible_displays),
            "hidden_displays": list(self.hidden_displays),
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
    function_block: str = ''
    output: str = ''
    side_effects: tuple[str, ...] = ()
    rationale: str = ''
    business_bearing: bool = False
    pure_ui: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, 'event_id', str(self.event_id))
        object.__setattr__(self, 'control_id', str(self.control_id))
        object.__setattr__(self, 'source_state_id', str(self.source_state_id))
        object.__setattr__(self, 'target_state_id', str(self.target_state_id))
        object.__setattr__(self, 'function_block', str(self.function_block))
        object.__setattr__(self, 'output', str(self.output))
        object.__setattr__(self, 'side_effects', _as_tuple(self.side_effects))
        object.__setattr__(self, 'rationale', str(self.rationale))
        object.__setattr__(self, 'business_bearing', bool(self.business_bearing))
        object.__setattr__(self, 'pure_ui', bool(self.pure_ui))

    def to_dict(self) -> dict[str, Any]:
        return {'event_id': self.event_id, 'control_id': self.control_id, 'source_state_id': self.source_state_id,
            'target_state_id': self.target_state_id, 'function_block': self.function_block, 'output': self.output,
            'side_effects': list(self.side_effects), 'rationale': self.rationale, 'business_bearing': self.business_bearing,
            'pure_ui': self.pure_ui}


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
    content_visibility_id: str = ""
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
        object.__setattr__(self, "content_visibility_id", str(self.content_visibility_id))
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
            "content_visibility_id": self.content_visibility_id,
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
    content_visibility_plan_id: str = ""
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
        object.__setattr__(self, "content_visibility_plan_id", str(self.content_visibility_plan_id))
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
            "content_visibility_plan_id": self.content_visibility_plan_id,
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


def _redundancy_justified(items: Sequence[Any]) -> bool:
    if any(getattr(item, "redundancy_rationale", "") for item in items):
        return True
    duplicate_groups = {
        getattr(item, "duplicate_group", "")
        for item in items
        if getattr(item, "duplicate_group", "")
    }
    return len(duplicate_groups) == 1


def _usable_ui_transitions(model: UIInteractionModel) -> tuple[UITransition, ...]:
    """The declared edges a user can activate; include every nondeterministic target."""
    states = {state.state_id: state for state in model.states}
    controls = set(model.control_ids())
    return tuple(
        transition for transition in model.transitions
        if transition.source_state_id in states and transition.target_state_id in states
        and transition.control_id in controls
        and transition.control_id in states[transition.source_state_id].enabled_controls
        and transition.control_id not in states[transition.source_state_id].disabled_controls
        and transition.control_id not in states[transition.source_state_id].hidden_controls
    )



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
        transitions_by_state_control.setdefault((transition.source_state_id, transition.control_id), []).append(transition)
    if not model.model_id:
        findings.append(UIFlowStructureFinding('missing_model_id', 'UI interaction model has no model id'))
    if not model.initial_state_id:
        findings.append(UIFlowStructureFinding('missing_initial_state', 'UI interaction model has no initial UI state'))
    elif model.initial_state_id not in state_ids:
        findings.append(UIFlowStructureFinding('initial_state_not_registered',
            f'initial state {model.initial_state_id} is not in the state list', item_id=model.initial_state_id))
    if not model.states:
        findings.append(UIFlowStructureFinding('missing_states', 'UI interaction model has no UI states'))
    if not model.controls:
        findings.append(UIFlowStructureFinding('missing_controls', 'UI interaction model has no controls'))
    if not model.transitions:
        findings.append(UIFlowStructureFinding('missing_transitions', 'UI interaction model has no transitions'))
    if not any((state.has_availability() for state in model.states)):
        findings.append(UIFlowStructureFinding('missing_state_availability_matrix',
            'UI states do not declare visible, enabled, disabled, or hidden controls'))
    findings.extend(_duplicate_values(model.state_ids(), code='duplicate_state_id', noun='state'))
    findings.extend(_duplicate_values(model.control_ids(), code='duplicate_control_id', noun='control'))
    findings.extend(_duplicate_values(model.display_ids(), code='duplicate_display_id', noun='display'))
    findings.extend(_duplicate_values(model.transition_event_ids(), code='duplicate_event_id', noun='event'))
    for state in model.states:
        if state.parent_state_id and state.parent_state_id not in state_ids:
            findings.append(UIFlowStructureFinding('parent_state_not_registered',
                f'state {state.state_id} references unknown parent state {state.parent_state_id}', item_id=state.state_id))
        for control_id in state.visible_controls + state.enabled_controls + state.disabled_controls + state.hidden_controls + state.recovery_controls:
            if control_id not in control_ids:
                findings.append(UIFlowStructureFinding('state_control_not_registered',
                    f'state {state.state_id} references unknown control {control_id}', item_id=control_id))
        for display_id in state.visible_displays:
            if display_id not in display_ids:
                findings.append(UIFlowStructureFinding('state_display_not_registered',
                    f'state {state.state_id} references unknown display {display_id}', item_id=display_id))
        for display_id in state.hidden_displays:
            if display_id not in display_ids:
                findings.append(UIFlowStructureFinding('state_hidden_display_not_registered',
                    f'state {state.state_id} hides unknown display {display_id}', item_id=display_id))
        hidden_control_conflicts = set(state.hidden_controls) & (set(state.visible_controls) | set(state.enabled_controls) | set(state.disabled_controls))
        enabled_disabled_conflicts = set(state.enabled_controls) & set(state.disabled_controls)
        for control_id in sorted(hidden_control_conflicts | enabled_disabled_conflicts):
            findings.append(UIFlowStructureFinding('conflicting_control_availability',
                f'state {state.state_id} gives control {control_id} conflicting visible/enabled/disabled/hidden dispositions',
                item_id=control_id))
        for display_id in sorted(set(state.visible_displays) & set(state.hidden_displays)):
            findings.append(UIFlowStructureFinding('conflicting_display_visibility',
                f'state {state.state_id} marks display {display_id} both visible and hidden', item_id=display_id))
        if state.failure and (not state.terminal) and (not state.recovery_controls) and (not outgoing_by_state.get(state.state_id)):
            findings.append(UIFlowStructureFinding('missing_failure_recovery',
                f'recoverable failure state {state.state_id} has no recovery control or outgoing transition',
                item_id=state.state_id))
    for control in model.controls:
        if control.destructive and control.level in {'primary', 'global'}:
            findings.append(UIFlowStructureFinding('destructive_control_too_prominent',
                f'destructive control {control.control_id} is marked as {control.level}', item_id=control.control_id))
        if control.control_type not in {'display', 'label',
            'status'} and (not control.persistent) and (control.control_id not in event_control_ids):
            findings.append(UIFlowStructureFinding('unmodeled_control_event',
                f'control {control.control_id} has no modeled event transition', item_id=control.control_id))
        if not control.function_key and (not control.persistent) and (control.control_type not in {'display', 'label', 'status'}):
            transition_keys = [transition.function_block or transition.output for transition in model.transitions if transition.control_id == control.control_id]
            if not any(transition_keys):
                findings.append(UIFlowStructureFinding('missing_control_function_key',
                    f'control {control.control_id} has no function key or modeled action', item_id=control.control_id))
        for state_id in control.depends_on_states:
            if state_id not in state_ids:
                findings.append(UIFlowStructureFinding('control_dependency_state_not_registered',
                    f'control {control.control_id} depends on unknown state {state_id}', item_id=control.control_id))
    for display in model.displays:
        if not display.semantic_key:
            findings.append(UIFlowStructureFinding('missing_display_semantic_key',
                f'display {display.display_id} has no semantic key for duplicate-information review', item_id=display.display_id))
        for state_id in display.depends_on_states:
            if state_id not in state_ids:
                findings.append(UIFlowStructureFinding('display_dependency_state_not_registered',
                    f'display {display.display_id} depends on unknown state {state_id}', item_id=display.display_id))
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
            if len(displays) > 1 and (not _redundancy_justified(displays)):
                findings.append(UIFlowStructureFinding('duplicate_information_same_state',
                    f'state {state.state_id} shows semantic information {semantic_key} more than once without a redundancy rationale', item_id=state.state_id, metadata={'display_ids': sorted((display.display_id for display in displays))}))
        action_groups: dict[tuple[str, str], set[str]] = {}
        active_controls = state.enabled_controls or state.visible_controls
        for control_id in active_controls:
            control = controls_by_id.get(control_id)
            if control is None:
                continue
            transitions = transitions_by_state_control.get((state.state_id, control_id), ())
            action_keys = {control.function_key or transition.function_block or transition.output for transition in transitions if control.function_key or transition.function_block or transition.output}
            if not action_keys and control.function_key:
                action_keys = {control.function_key}
            for action_key in action_keys:
                action_groups.setdefault((control.level, action_key), set()).add(control_id)
        for (level, action_key), grouped_control_ids in sorted(action_groups.items()):
            if len(grouped_control_ids) <= 1:
                continue
            grouped_controls = [controls_by_id[control_id] for control_id in sorted(grouped_control_ids)]
            if not _redundancy_justified(grouped_controls):
                findings.append(UIFlowStructureFinding('duplicate_control_function_same_state_level',
                    f'state {state.state_id} has multiple {level} controls for function {action_key} without a redundancy rationale', item_id=state.state_id, metadata={'control_ids': sorted(grouped_control_ids), 'function_key': action_key}))
    for transition in model.transitions:
        if transition.control_id not in control_ids:
            findings.append(UIFlowStructureFinding('transition_control_not_registered',
                f'transition {transition.event_id} references unknown control {transition.control_id}',
                item_id=transition.event_id))
        if transition.source_state_id not in state_ids:
            findings.append(UIFlowStructureFinding('transition_source_state_not_registered',
                f'transition {transition.event_id} references unknown source state {transition.source_state_id}',
                item_id=transition.event_id))
        if transition.target_state_id not in state_ids:
            findings.append(UIFlowStructureFinding('transition_target_state_not_registered',
                f'transition {transition.event_id} references unknown target state {transition.target_state_id}',
                item_id=transition.event_id))
    usable = _usable_ui_transitions(model)
    for state in model.states:
        if state.role in {'dialog', 'modal',
            'overlay'} and (not any((transition.source_state_id == state.state_id and transition.target_state_id != state.state_id for transition in usable))):
            findings.append(UIFlowStructureFinding('dialog_cannot_close',
                f'dialog state {state.state_id} has no enabled transition to another declared state', item_id=state.state_id))
    reached = {model.initial_state_id} if model.initial_state_id in state_ids else set()
    pending = list(reached)
    outgoing = {}
    for transition in usable:
        outgoing.setdefault(transition.source_state_id, set()).add(transition.target_state_id)
    while pending:
        current = pending.pop()
        for target in outgoing.get(current, ()):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    for state in model.states:
        if state.state_id not in reached:
            findings.append(UIFlowStructureFinding('state_unreachable',
                f'declared state {state.state_id} cannot be reached from the initial state by enabled controls',
                item_id=state.state_id))
    blockers = _blocker_findings(findings)
    return UIInteractionModelReport(ok=not blockers, model_id=model.model_id, findings=tuple(findings))


@dataclass(frozen=True)
class UIJourneyState:
    """State of a UI journey model: the UI state reached, and an enabled control that led nowhere."""

    state_id: str
    dead_control: str = ""
    interaction_model: UIInteractionModel | None = field(default=None, compare=False, repr=False)


class _UIActivate:
    """Function block: activate one control in the current UI state (Input x State -> Set(Output x State))."""

    name = "ActivateControl"
    reads = ("state_id",)
    writes = ("state_id", "dead_control")

    def __init__(self, model: UIInteractionModel) -> None:
        self.model = model
        self.enabled = {node.state_id: set(node.enabled_controls) for node in model.states}
        self.targets: dict[tuple[str, str], list[str]] = {}
        for transition in model.transitions:
            self.targets.setdefault((transition.source_state_id, transition.control_id), []).append(
                transition.target_state_id)

    def apply(self, control_id: str, state: UIJourneyState):
        from .core import FunctionResult

        configuration = state.interaction_model if state.interaction_model is not None else self.model
        if state.interaction_model is None:
            state = UIJourneyState(state.state_id, state.dead_control, configuration)
        enabled = (self.enabled if configuration is self.model else
                   {node.state_id: set(node.enabled_controls) for node in configuration.states})
        if control_id not in enabled.get(state.state_id, set()):
            return (FunctionResult("unavailable", state, label="unavailable"),)
        targets = (self.targets.get((state.state_id, control_id), []) if configuration is self.model else
                   [transition.target_state_id for transition in configuration.transitions
                    if transition.source_state_id == state.state_id and transition.control_id == control_id])
        if not targets:
            return (FunctionResult("no_transition", UIJourneyState(state.state_id, control_id, configuration),
                                   label="dead_control"),)
        return tuple(FunctionResult(target, UIJourneyState(target, interaction_model=configuration),
                                    label=f"{control_id}->{target}") for target in targets)


def ui_journey_explorer(model: UIInteractionModel, *, max_steps: int = 3):
    """UI journeys as a model: activate any control from the initial state, up to ``max_steps`` times.

    Invariants: review_ui_interaction_model accepts the model; every reached state is declared; an enabled
    control always leads somewhere; a reached state that is not terminal has an enabled control that leads on.
    """
    from .core import Invariant, InvariantResult
    from .explorer import Explorer
    from .workflow import Workflow

    review = review_ui_interaction_model(model)
    declared = {node.state_id: node for node in model.states}
    block = _UIActivate(model)

    def configuration_of(state):
        actual = getattr(state, "interaction_model", None)
        return actual if actual is not None else model

    def review_accepts(state, trace):
        actual = configuration_of(state)
        actual_review = review if actual is model else review_ui_interaction_model(actual)
        codes = ", ".join(finding.code for finding in actual_review.findings[:5])
        return (InvariantResult.pass_() if actual_review.ok else
                InvariantResult.fail(f"review_ui_interaction_model blocks: {codes}"))

    def state_declared(state, trace):
        actual = configuration_of(state)
        actual_declared = declared if actual is model else {node.state_id: node for node in actual.states}
        if state.state_id in actual_declared:
            return InvariantResult.pass_()
        return InvariantResult.fail(f"a journey reaches the undeclared UI state {state.state_id!r}")

    def control_leads_somewhere(state, trace):
        if state.dead_control:
            return InvariantResult.fail(f"enabled control {state.dead_control!r} in {state.state_id!r} leads nowhere")
        return InvariantResult.pass_()

    def way_on(state, trace):
        actual = configuration_of(state)
        actual_declared = declared if actual is model else {node.state_id: node for node in actual.states}
        targets = (block.targets if actual is model else
                   {(transition.source_state_id, transition.control_id) for transition in actual.transitions})
        node = actual_declared.get(state.state_id)
        if node is None or node.terminal or any((state.state_id, c) in targets for c in node.enabled_controls):
            return InvariantResult.pass_()
        return InvariantResult.fail(f"UI state {state.state_id!r} is a dead end: no enabled control leads on")

    invariants = (
        Invariant("ui_review_accepts", "review_ui_interaction_model accepts the interaction model", review_accepts),
        Invariant("reached_state_is_declared", "every state a journey reaches is declared", state_declared),
        Invariant("enabled_control_leads_somewhere", "an enabled control always has a transition", control_leads_somewhere),
        Invariant("non_terminal_state_has_a_way_on", "a reached non-terminal state lets the user go on", way_on),
    )
    return Explorer(workflow=Workflow((block,)), initial_states=(UIJourneyState(model.initial_state_id, interaction_model=model),),
                    external_inputs=tuple(control.control_id for control in model.controls), invariants=invariants,
                    max_sequence_length=max_steps, progress_steps=0)


def ui_flow_code_facts(model: UIInteractionModel, files: Sequence[str], *, anchors=(), root=None):
    """Compare a UI interaction model with the UI source (static code facts, nothing is rendered).

    Every declared control id is present in ``files``; every anchor (the handlers) exists.
    """
    from .map.facts import CodeFacts

    facts = CodeFacts(root)
    if anchors:
        facts.anchors_exist(anchors)
    for control in model.controls:
        facts.present(control.control_id, files, f"control {control.control_id} is in the UI source")
    return facts.report()


__all__ = ['UIControl', 'UIStateNode', 'UITransition', 'UIDisplayElement', 'UIInteractionModel', 'UIFlowStructureFinding',
    'UIInteractionModelReport', 'UIJourneyState', 'review_ui_interaction_model', 'ui_journey_explorer', 'ui_flow_code_facts']
