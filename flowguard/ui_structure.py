"""UI interaction flow and model-derived structure helpers.

UI flow structure keeps UI design model-first. It first reviews a UI-level
interaction model, then optionally reviews app-level launch-to-terminal journey
coverage when the UI claims complete app coverage, then reviews a structure
derivation that maps that model to regions, menu levels, parent/child nodes,
overlays, stable placements, and intentional display/control redundancy. A
final review surface derives text roles and typography tokens from the reviewed
UI structure so headings, labels, buttons, status text, and repeated semantic
content follow the modeled UI topology instead of ad hoc styling.
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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
class UIJourneyEntryPoint:
    """One app-level entry point that should be available from launch."""

    entry_id: str
    control_id: str
    event_id: str
    label: str = ""
    source_state_ids: tuple[str, ...] = ()
    required: bool = True
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", str(self.entry_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "source_state_ids", _as_tuple(self.source_state_ids))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "control_id": self.control_id,
            "event_id": self.event_id,
            "label": self.label,
            "source_state_ids": list(self.source_state_ids),
            "required": self.required,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIFeatureJourney:
    """One declared feature path from app entry toward success or recovery."""

    feature_id: str
    label: str = ""
    entry_point_ids: tuple[str, ...] = ()
    required_state_ids: tuple[str, ...] = ()
    required_event_ids: tuple[str, ...] = ()
    success_terminal_state_ids: tuple[str, ...] = ()
    failure_state_ids: tuple[str, ...] = ()
    recovery_event_ids: tuple[str, ...] = ()
    cancel_event_ids: tuple[str, ...] = ()
    exit_event_ids: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", str(self.feature_id))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "entry_point_ids", _as_tuple(self.entry_point_ids))
        object.__setattr__(self, "required_state_ids", _as_tuple(self.required_state_ids))
        object.__setattr__(self, "required_event_ids", _as_tuple(self.required_event_ids))
        object.__setattr__(self, "success_terminal_state_ids", _as_tuple(self.success_terminal_state_ids))
        object.__setattr__(self, "failure_state_ids", _as_tuple(self.failure_state_ids))
        object.__setattr__(self, "recovery_event_ids", _as_tuple(self.recovery_event_ids))
        object.__setattr__(self, "cancel_event_ids", _as_tuple(self.cancel_event_ids))
        object.__setattr__(self, "exit_event_ids", _as_tuple(self.exit_event_ids))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def handling_event_ids(self) -> tuple[str, ...]:
        return self.recovery_event_ids + self.cancel_event_ids + self.exit_event_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "label": self.label,
            "entry_point_ids": list(self.entry_point_ids),
            "required_state_ids": list(self.required_state_ids),
            "required_event_ids": list(self.required_event_ids),
            "success_terminal_state_ids": list(self.success_terminal_state_ids),
            "failure_state_ids": list(self.failure_state_ids),
            "recovery_event_ids": list(self.recovery_event_ids),
            "cancel_event_ids": list(self.cancel_event_ids),
            "exit_event_ids": list(self.exit_event_ids),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UITerminalActionAllowance:
    """One allowed outgoing action from a terminal UI state."""

    state_id: str
    event_id: str
    purpose: str
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", str(self.state_id))
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "purpose", str(self.purpose))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "event_id": self.event_id,
            "purpose": self.purpose,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIResidualBlindspot:
    """One intentionally out-of-scope UI branch with its validation boundary."""

    blindspot_id: str
    feature_id: str = ""
    control_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    reason: str = ""
    owner: str = ""
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "blindspot_id", str(self.blindspot_id))
        object.__setattr__(self, "feature_id", str(self.feature_id))
        object.__setattr__(self, "control_ids", _as_tuple(self.control_ids))
        object.__setattr__(self, "event_ids", _as_tuple(self.event_ids))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "blindspot_id": self.blindspot_id,
            "feature_id": self.feature_id,
            "control_ids": list(self.control_ids),
            "event_ids": list(self.event_ids),
            "reason": self.reason,
            "owner": self.owner,
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIJourneyCoverage:
    """App-level launch-to-terminal journey coverage for a UI interaction model."""

    coverage_id: str
    source_interaction_model_id: str
    launch_state_id: str
    entry_points: tuple[UIJourneyEntryPoint, ...] = ()
    feature_journeys: tuple[UIFeatureJourney, ...] = ()
    terminal_action_allowances: tuple[UITerminalActionAllowance, ...] = ()
    residual_blindspots: tuple[UIResidualBlindspot, ...] = ()
    interaction_model_reviewed: bool = False
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "coverage_id", str(self.coverage_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "launch_state_id", str(self.launch_state_id))
        object.__setattr__(self, "entry_points", tuple(self.entry_points))
        object.__setattr__(self, "feature_journeys", tuple(self.feature_journeys))
        object.__setattr__(self, "terminal_action_allowances", tuple(self.terminal_action_allowances))
        object.__setattr__(self, "residual_blindspots", tuple(self.residual_blindspots))
        object.__setattr__(self, "interaction_model_reviewed", bool(self.interaction_model_reviewed))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def entry_point_ids(self) -> tuple[str, ...]:
        return tuple(entry.entry_id for entry in self.entry_points)

    def feature_ids(self) -> tuple[str, ...]:
        return tuple(feature.feature_id for feature in self.feature_journeys)

    def blindspot_ids(self) -> tuple[str, ...]:
        return tuple(blindspot.blindspot_id for blindspot in self.residual_blindspots)

    def terminal_allowance_keys(self) -> tuple[str, ...]:
        return tuple(f"{allowance.state_id}:{allowance.event_id}" for allowance in self.terminal_action_allowances)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_id": self.coverage_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "launch_state_id": self.launch_state_id,
            "entry_points": [entry.to_dict() for entry in self.entry_points],
            "feature_journeys": [feature.to_dict() for feature in self.feature_journeys],
            "terminal_action_allowances": [
                allowance.to_dict() for allowance in self.terminal_action_allowances
            ],
            "residual_blindspots": [blindspot.to_dict() for blindspot in self.residual_blindspots],
            "interaction_model_reviewed": self.interaction_model_reviewed,
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIFeatureContract:
    """One user-visible feature contract that should align with UI journeys."""

    feature_id: str
    label: str = ""
    source_feature_id: str = ""
    user_visible: bool = True
    exposure: str = "ui"
    journey_ids: tuple[str, ...] = ()
    entry_point_ids: tuple[str, ...] = ()
    required_control_ids: tuple[str, ...] = ()
    required_event_ids: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", str(self.feature_id))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "source_feature_id", str(self.source_feature_id))
        object.__setattr__(self, "user_visible", bool(self.user_visible))
        object.__setattr__(self, "exposure", str(self.exposure))
        object.__setattr__(self, "journey_ids", _as_tuple(self.journey_ids))
        object.__setattr__(self, "entry_point_ids", _as_tuple(self.entry_point_ids))
        object.__setattr__(self, "required_control_ids", _as_tuple(self.required_control_ids))
        object.__setattr__(self, "required_event_ids", _as_tuple(self.required_event_ids))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "label": self.label,
            "source_feature_id": self.source_feature_id,
            "user_visible": self.user_visible,
            "exposure": self.exposure,
            "journey_ids": list(self.journey_ids),
            "entry_point_ids": list(self.entry_point_ids),
            "required_control_ids": list(self.required_control_ids),
            "required_event_ids": list(self.required_event_ids),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIImplementationStepEvidence:
    """One observed real-UI step tied back to a modeled UI event."""

    step_id: str
    event_id: str
    control_id: str = ""
    source_state_id: str = ""
    target_state_id: str = ""
    method: str = ""
    result: str = "passed"
    evidence_ref: str = ""
    observed_state_id: str = ""
    observed_output: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "source_state_id", str(self.source_state_id))
        object.__setattr__(self, "target_state_id", str(self.target_state_id))
        object.__setattr__(self, "method", str(self.method))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "observed_state_id", str(self.observed_state_id))
        object.__setattr__(self, "observed_output", str(self.observed_output))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "event_id": self.event_id,
            "control_id": self.control_id,
            "source_state_id": self.source_state_id,
            "target_state_id": self.target_state_id,
            "method": self.method,
            "result": self.result,
            "evidence_ref": self.evidence_ref,
            "observed_state_id": self.observed_state_id,
            "observed_output": self.observed_output,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIImplementationJourneyRun:
    """One browser, desktop, or manual run of a modeled UI feature journey."""

    run_id: str
    feature_id: str
    journey_id: str = ""
    entry_point_id: str = ""
    steps: tuple[UIImplementationStepEvidence, ...] = ()
    method: str = ""
    result: str = "passed"
    evidence_ref: str = ""
    model_revision: str = ""
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", str(self.run_id))
        object.__setattr__(self, "feature_id", str(self.feature_id))
        object.__setattr__(self, "journey_id", str(self.journey_id))
        object.__setattr__(self, "entry_point_id", str(self.entry_point_id))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "method", str(self.method))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "model_revision", str(self.model_revision))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def covered_event_ids(self) -> tuple[str, ...]:
        return tuple(step.event_id for step in self.steps if step.event_id)

    def covered_control_ids(self) -> tuple[str, ...]:
        return tuple(step.control_id for step in self.steps if step.control_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "feature_id": self.feature_id,
            "journey_id": self.journey_id,
            "entry_point_id": self.entry_point_id,
            "steps": [step.to_dict() for step in self.steps],
            "method": self.method,
            "result": self.result,
            "evidence_ref": self.evidence_ref,
            "model_revision": self.model_revision,
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIImplementationBlindspot:
    """One intentionally unverified implemented-UI branch."""

    blindspot_id: str
    feature_id: str = ""
    control_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    reason: str = ""
    owner: str = ""
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "blindspot_id", str(self.blindspot_id))
        object.__setattr__(self, "feature_id", str(self.feature_id))
        object.__setattr__(self, "control_ids", _as_tuple(self.control_ids))
        object.__setattr__(self, "event_ids", _as_tuple(self.event_ids))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "blindspot_id": self.blindspot_id,
            "feature_id": self.feature_id,
            "control_ids": list(self.control_ids),
            "event_ids": list(self.event_ids),
            "reason": self.reason,
            "owner": self.owner,
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIImplementationValidation:
    """Real UI validation aligned to feature contracts and UI journeys."""

    validation_id: str
    source_feature_model_id: str
    source_interaction_model_id: str
    source_journey_coverage_id: str
    implementation_target: str = ""
    current_model_revision: str = ""
    feature_contracts: tuple[UIFeatureContract, ...] = ()
    journey_runs: tuple[UIImplementationJourneyRun, ...] = ()
    pure_ui_control_ids: tuple[str, ...] = ()
    pure_ui_event_ids: tuple[str, ...] = ()
    implementation_blindspots: tuple[UIImplementationBlindspot, ...] = ()
    journey_coverage_reviewed: bool = False
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation_id", str(self.validation_id))
        object.__setattr__(self, "source_feature_model_id", str(self.source_feature_model_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "source_journey_coverage_id", str(self.source_journey_coverage_id))
        object.__setattr__(self, "implementation_target", str(self.implementation_target))
        object.__setattr__(self, "current_model_revision", str(self.current_model_revision))
        object.__setattr__(self, "feature_contracts", tuple(self.feature_contracts))
        object.__setattr__(self, "journey_runs", tuple(self.journey_runs))
        object.__setattr__(self, "pure_ui_control_ids", _as_tuple(self.pure_ui_control_ids))
        object.__setattr__(self, "pure_ui_event_ids", _as_tuple(self.pure_ui_event_ids))
        object.__setattr__(self, "implementation_blindspots", tuple(self.implementation_blindspots))
        object.__setattr__(self, "journey_coverage_reviewed", bool(self.journey_coverage_reviewed))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def feature_ids(self) -> tuple[str, ...]:
        return tuple(contract.feature_id for contract in self.feature_contracts)

    def run_ids(self) -> tuple[str, ...]:
        return tuple(run.run_id for run in self.journey_runs)

    def blindspot_ids(self) -> tuple[str, ...]:
        return tuple(blindspot.blindspot_id for blindspot in self.implementation_blindspots)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "source_feature_model_id": self.source_feature_model_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "source_journey_coverage_id": self.source_journey_coverage_id,
            "implementation_target": self.implementation_target,
            "current_model_revision": self.current_model_revision,
            "feature_contracts": [contract.to_dict() for contract in self.feature_contracts],
            "journey_runs": [run.to_dict() for run in self.journey_runs],
            "pure_ui_control_ids": list(self.pure_ui_control_ids),
            "pure_ui_event_ids": list(self.pure_ui_event_ids),
            "implementation_blindspots": [
                blindspot.to_dict() for blindspot in self.implementation_blindspots
            ],
            "journey_coverage_reviewed": self.journey_coverage_reviewed,
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
class UITypographyToken:
    """One semantic text style token derived from UI hierarchy."""

    token_id: str
    hierarchy_level: int = 4
    text_roles: tuple[str, ...] = ()
    scale: str = ""
    weight: str = ""
    color_role: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "token_id", str(self.token_id))
        object.__setattr__(self, "hierarchy_level", _as_int(self.hierarchy_level, default=0))
        object.__setattr__(self, "text_roles", _as_tuple(self.text_roles))
        object.__setattr__(self, "scale", str(self.scale))
        object.__setattr__(self, "weight", str(self.weight))
        object.__setattr__(self, "color_role", str(self.color_role))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "hierarchy_level": self.hierarchy_level,
            "text_roles": list(self.text_roles),
            "scale": self.scale,
            "weight": self.weight,
            "color_role": self.color_role,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UITextElement:
    """One modeled text element anchored to UI structure or interaction state."""

    text_id: str
    role: str
    token_id: str
    semantic_key: str
    label: str = ""
    region_id: str = ""
    parent_text_id: str = ""
    source_state_ids: tuple[str, ...] = ()
    source_control_id: str = ""
    source_display_id: str = ""
    visible_in_states: tuple[str, ...] = ()
    duplicate_group: str = ""
    redundancy_rationale: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", str(self.text_id))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "token_id", str(self.token_id))
        object.__setattr__(self, "semantic_key", str(self.semantic_key))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "region_id", str(self.region_id))
        object.__setattr__(self, "parent_text_id", str(self.parent_text_id))
        object.__setattr__(self, "source_state_ids", _as_tuple(self.source_state_ids))
        object.__setattr__(self, "source_control_id", str(self.source_control_id))
        object.__setattr__(self, "source_display_id", str(self.source_display_id))
        object.__setattr__(self, "visible_in_states", _as_tuple(self.visible_in_states))
        object.__setattr__(self, "duplicate_group", str(self.duplicate_group))
        object.__setattr__(self, "redundancy_rationale", str(self.redundancy_rationale))
        object.__setattr__(self, "rationale", str(self.rationale))

    def state_scope(self) -> tuple[str, ...]:
        return self.visible_in_states or self.source_state_ids or ("*",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_id": self.text_id,
            "role": self.role,
            "token_id": self.token_id,
            "semantic_key": self.semantic_key,
            "label": self.label,
            "region_id": self.region_id,
            "parent_text_id": self.parent_text_id,
            "source_state_ids": list(self.source_state_ids),
            "source_control_id": self.source_control_id,
            "source_display_id": self.source_display_id,
            "visible_in_states": list(self.visible_in_states),
            "duplicate_group": self.duplicate_group,
            "redundancy_rationale": self.redundancy_rationale,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UITextHierarchyBlueprint:
    """Text hierarchy derived from a reviewed UI interaction and structure model."""

    blueprint_id: str
    source_interaction_model_id: str
    source_structure_derivation_id: str
    parent_surface_id: str
    typography_tokens: tuple[UITypographyToken, ...] = ()
    text_elements: tuple[UITextElement, ...] = ()
    structure_derivation_reviewed: bool = False
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "blueprint_id", str(self.blueprint_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "source_structure_derivation_id", str(self.source_structure_derivation_id))
        object.__setattr__(self, "parent_surface_id", str(self.parent_surface_id))
        object.__setattr__(self, "typography_tokens", tuple(self.typography_tokens))
        object.__setattr__(self, "text_elements", tuple(self.text_elements))
        object.__setattr__(self, "structure_derivation_reviewed", bool(self.structure_derivation_reviewed))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def token_ids(self) -> tuple[str, ...]:
        return tuple(token.token_id for token in self.typography_tokens)

    def text_ids(self) -> tuple[str, ...]:
        return tuple(text.text_id for text in self.text_elements)

    def tokens_by_id(self) -> dict[str, UITypographyToken]:
        return {token.token_id: token for token in self.typography_tokens}

    def text_by_id(self) -> dict[str, UITextElement]:
        return {text.text_id: text for text in self.text_elements}

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "source_structure_derivation_id": self.source_structure_derivation_id,
            "parent_surface_id": self.parent_surface_id,
            "typography_tokens": [token.to_dict() for token in self.typography_tokens],
            "text_elements": [text.to_dict() for text in self.text_elements],
            "structure_derivation_reviewed": self.structure_derivation_reviewed,
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
class UIJourneyCoverageReport:
    """Structured review result for app-level UI journey coverage."""

    ok: bool
    coverage_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    reachable_state_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "coverage_id", str(self.coverage_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "reachable_state_ids", _as_tuple(self.reachable_state_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_journey_coverage={self.coverage_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI journey coverage review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"coverage: {self.coverage_id}",
            f"reachable_states: {len(self.reachable_state_ids)}",
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
            "coverage_id": self.coverage_id,
            "reachable_state_ids": list(self.reachable_state_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIImplementationValidationReport:
    """Structured review result for real UI implementation validation."""

    ok: bool
    validation_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    covered_feature_ids: tuple[str, ...] = ()
    covered_event_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation_id", str(self.validation_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_feature_ids", _as_tuple(self.covered_feature_ids))
        object.__setattr__(self, "covered_event_ids", _as_tuple(self.covered_event_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_implementation_validation={self.validation_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI implementation validation review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"validation: {self.validation_id}",
            f"covered_features: {len(self.covered_feature_ids)}",
            f"covered_events: {len(self.covered_event_ids)}",
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
            "validation_id": self.validation_id,
            "covered_feature_ids": list(self.covered_feature_ids),
            "covered_event_ids": list(self.covered_event_ids),
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


@dataclass(frozen=True)
class UITextHierarchyReport:
    """Structured review result for a UI text hierarchy blueprint."""

    ok: bool
    blueprint_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "blueprint_id", str(self.blueprint_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_text_hierarchy={self.blueprint_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI text hierarchy review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"blueprint: {self.blueprint_id}",
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
            "blueprint_id": self.blueprint_id,
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


_ALLOWED_TERMINAL_ACTION_PURPOSES = {"restart", "export", "close", "recovery", "cancel", "exit"}


def _transitions_by_event(model: UIInteractionModel) -> dict[str, UITransition]:
    return {transition.event_id: transition for transition in model.transitions}


def _outgoing_transitions(model: UIInteractionModel) -> dict[str, list[UITransition]]:
    outgoing: dict[str, list[UITransition]] = {}
    for transition in model.transitions:
        outgoing.setdefault(transition.source_state_id, []).append(transition)
    return outgoing


def _transitions_by_state_control(model: UIInteractionModel) -> dict[tuple[str, str], list[UITransition]]:
    transitions: dict[tuple[str, str], list[UITransition]] = {}
    for transition in model.transitions:
        transitions.setdefault((transition.source_state_id, transition.control_id), []).append(transition)
    return transitions


def _reachable_state_ids(model: UIInteractionModel, launch_state_id: str) -> set[str]:
    state_ids = set(model.state_ids())
    if launch_state_id not in state_ids:
        return set()
    outgoing = _outgoing_transitions(model)
    reachable: set[str] = {launch_state_id}
    pending: list[str] = [launch_state_id]
    while pending:
        state_id = pending.pop(0)
        for transition in outgoing.get(state_id, ()):
            target = transition.target_state_id
            if target in state_ids and target not in reachable:
                reachable.add(target)
                pending.append(target)
    return reachable


def _event_source_ids(event: UITransition | None, fallback_source_ids: Sequence[str]) -> tuple[str, ...]:
    if fallback_source_ids:
        return _as_tuple(fallback_source_ids)
    if event is None:
        return ()
    return (event.source_state_id,)


_CONTROL_TEXT_ROLES = {"button_label", "menu_label", "tab_label", "control_label"}
_TITLE_TEXT_ROLES = {"page_title", "section_title", "panel_title"}
_ROLE_MIN_HIERARCHY_LEVEL = {
    "page_title": 1,
    "section_title": 2,
    "panel_title": 3,
    "field_label": 4,
    "button_label": 4,
    "menu_label": 4,
    "tab_label": 4,
    "control_label": 4,
    "status_text": 4,
    "error_text": 4,
    "data_value": 5,
    "body_text": 5,
    "help_text": 5,
    "caption": 6,
}


def _scoped_groups_by_key(text_elements: Sequence[UITextElement], key_name: str) -> dict[tuple[str, str, str], list[UITextElement]]:
    groups: dict[tuple[str, str, str], list[UITextElement]] = {}
    for text in text_elements:
        if key_name == "semantic_key":
            value = text.semantic_key
        elif key_name == "role":
            value = text.role
        else:
            value = ""
        if not value:
            continue
        for state_id in text.state_scope():
            groups.setdefault((text.region_id, state_id, value), []).append(text)
    return groups


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


def review_ui_journey_coverage(
    coverage: UIJourneyCoverage,
    *,
    interaction_model: UIInteractionModel,
) -> UIJourneyCoverageReport:
    """Review whether declared app UI journeys are covered from launch to terminal states."""

    findings: list[UIFlowStructureFinding] = []
    state_ids = set(interaction_model.state_ids())
    control_ids = set(interaction_model.control_ids())
    event_ids = set(interaction_model.transition_event_ids())
    states_by_id = {state.state_id: state for state in interaction_model.states}
    controls_by_id = interaction_model.controls_by_id()
    events_by_id = _transitions_by_event(interaction_model)
    outgoing_by_state = _outgoing_transitions(interaction_model)
    transitions_by_state_control = _transitions_by_state_control(interaction_model)
    reachable_states = _reachable_state_ids(interaction_model, coverage.launch_state_id)
    entry_points_by_id = {entry.entry_id: entry for entry in coverage.entry_points}
    blindspot_control_id_values = tuple(
        control_id
        for blindspot in coverage.residual_blindspots
        for control_id in blindspot.control_ids
    )
    blindspot_event_id_values = tuple(
        event_id
        for blindspot in coverage.residual_blindspots
        for event_id in blindspot.event_ids
    )
    blindspot_control_ids = set(blindspot_control_id_values)
    blindspot_event_ids = set(blindspot_event_id_values)

    if not coverage.coverage_id:
        findings.append(UIFlowStructureFinding("missing_coverage_id", "UI journey coverage has no coverage id"))
    if not coverage.source_interaction_model_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_interaction_model",
                "UI journey coverage has no source UI interaction model id",
            )
        )
    elif coverage.source_interaction_model_id != interaction_model.model_id:
        findings.append(
            UIFlowStructureFinding(
                "source_interaction_model_mismatch",
                "UI journey coverage does not reference the supplied interaction model",
                metadata={
                    "coverage_source": coverage.source_interaction_model_id,
                    "interaction_model": interaction_model.model_id,
                },
            )
        )
    if not coverage.interaction_model_reviewed:
        findings.append(
            UIFlowStructureFinding(
                "source_interaction_model_not_reviewed",
                "UI journey coverage was reviewed before the UI interaction model was marked reviewed",
            )
        )
    if not coverage.launch_state_id:
        findings.append(UIFlowStructureFinding("missing_launch_state", "UI journey coverage has no launch state"))
    elif coverage.launch_state_id not in state_ids:
        findings.append(
            UIFlowStructureFinding(
                "launch_state_not_registered",
                f"launch state {coverage.launch_state_id} is not in the source interaction model",
                item_id=coverage.launch_state_id,
            )
        )
    if not coverage.entry_points:
        findings.append(UIFlowStructureFinding("missing_entry_points", "UI journey coverage has no entry points"))
    if not coverage.feature_journeys:
        findings.append(
            UIFlowStructureFinding("missing_feature_journeys", "UI journey coverage has no feature journeys")
        )
    if not coverage.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_validation_plan", "UI journey coverage has no validation boundaries")
        )
    if not coverage.rationale:
        findings.append(
            UIFlowStructureFinding(
                "missing_coverage_rationale",
                "UI journey coverage has no rationale for the declared app boundary",
            )
        )

    findings.extend(_duplicate_values(coverage.entry_point_ids(), code="duplicate_entry_point_id", noun="entry point"))
    findings.extend(_duplicate_values(coverage.feature_ids(), code="duplicate_feature_id", noun="feature journey"))
    findings.extend(
        _duplicate_values(blindspot_control_id_values, code="duplicate_blindspot_control", noun="blindspot control")
    )
    findings.extend(_duplicate_values(blindspot_event_id_values, code="duplicate_blindspot_event", noun="blindspot event"))
    findings.extend(
        _duplicate_values(
            coverage.terminal_allowance_keys(),
            code="duplicate_terminal_action_allowance",
            noun="terminal action allowance",
        )
    )
    findings.extend(_duplicate_values(coverage.blindspot_ids(), code="duplicate_blindspot_id", noun="blindspot"))

    for entry in coverage.entry_points:
        event = events_by_id.get(entry.event_id)
        if not entry.control_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_entry_control",
                    f"entry point {entry.entry_id} has no control id",
                    item_id=entry.entry_id,
                )
            )
        elif entry.control_id not in control_ids:
            findings.append(
                UIFlowStructureFinding(
                    "entry_control_not_registered",
                    f"entry point {entry.entry_id} references unknown control {entry.control_id}",
                    item_id=entry.entry_id,
                )
            )
        if not entry.event_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_entry_event",
                    f"entry point {entry.entry_id} has no event id",
                    item_id=entry.entry_id,
                )
            )
        elif entry.event_id not in event_ids:
            findings.append(
                UIFlowStructureFinding(
                    "entry_event_not_registered",
                    f"entry point {entry.entry_id} references unknown event {entry.event_id}",
                    item_id=entry.entry_id,
                )
            )
        if event is not None and entry.control_id and event.control_id != entry.control_id:
            findings.append(
                UIFlowStructureFinding(
                    "entry_event_control_mismatch",
                    f"entry point {entry.entry_id} maps control {entry.control_id} to event {entry.event_id} owned by {event.control_id}",
                    item_id=entry.entry_id,
                )
            )
        source_state_ids = _event_source_ids(event, entry.source_state_ids)
        if not source_state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "missing_entry_source_state",
                    f"entry point {entry.entry_id} has no source state",
                    item_id=entry.entry_id,
                )
            )
        if coverage.launch_state_id and coverage.launch_state_id not in source_state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "entry_point_not_launch_available",
                    f"entry point {entry.entry_id} is not available from launch state {coverage.launch_state_id}",
                    item_id=entry.entry_id,
                    metadata={"source_state_ids": list(source_state_ids)},
                )
            )
        for source_state_id in source_state_ids:
            if source_state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "entry_source_state_not_registered",
                        f"entry point {entry.entry_id} references unknown source state {source_state_id}",
                        item_id=entry.entry_id,
                    )
                )
                continue
            if source_state_id not in reachable_states:
                findings.append(
                    UIFlowStructureFinding(
                        "entry_source_state_unreachable",
                        f"entry point {entry.entry_id} source state {source_state_id} is not reachable from launch",
                        item_id=entry.entry_id,
                    )
                )
            state = states_by_id[source_state_id]
            available_controls = set(state.visible_controls + state.enabled_controls)
            if entry.control_id and available_controls and entry.control_id not in available_controls:
                findings.append(
                    UIFlowStructureFinding(
                        "entry_control_not_available_in_source",
                        f"entry point {entry.entry_id} control {entry.control_id} is not visible or enabled in {source_state_id}",
                        item_id=entry.entry_id,
                    )
                )
        if not entry.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_entry_rationale",
                    f"entry point {entry.entry_id} has no app-entry rationale",
                    item_id=entry.entry_id,
                )
            )

    for feature in coverage.feature_journeys:
        if not feature.entry_point_ids:
            findings.append(
                UIFlowStructureFinding(
                    "missing_feature_entry_points",
                    f"feature journey {feature.feature_id} has no entry points",
                    item_id=feature.feature_id,
                )
            )
        for entry_point_id in feature.entry_point_ids:
            if entry_point_id not in entry_points_by_id:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_entry_point_not_declared",
                        f"feature journey {feature.feature_id} references undeclared entry point {entry_point_id}",
                        item_id=feature.feature_id,
                    )
                )
        if not feature.success_terminal_state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "missing_feature_success_terminal",
                    f"feature journey {feature.feature_id} has no success terminal state",
                    item_id=feature.feature_id,
                )
            )
        for state_id in feature.required_state_ids + feature.success_terminal_state_ids + feature.failure_state_ids:
            if state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_state_not_registered",
                        f"feature journey {feature.feature_id} references unknown state {state_id}",
                        item_id=feature.feature_id,
                        metadata={"state_id": state_id},
                    )
                )
                continue
            if state_id not in reachable_states:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_state_unreachable_from_launch",
                        f"feature journey {feature.feature_id} state {state_id} is not reachable from launch",
                        item_id=feature.feature_id,
                        metadata={"state_id": state_id},
                    )
                )
        for terminal_state_id in feature.success_terminal_state_ids:
            state = states_by_id.get(terminal_state_id)
            if state is not None and not state.terminal:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_success_state_not_terminal",
                        f"feature journey {feature.feature_id} success state {terminal_state_id} is not marked terminal",
                        item_id=feature.feature_id,
                    )
                )
        for event_id in feature.required_event_ids + feature.handling_event_ids():
            if event_id not in event_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_event_not_registered",
                        f"feature journey {feature.feature_id} references unknown event {event_id}",
                        item_id=feature.feature_id,
                        metadata={"event_id": event_id},
                    )
                )
        for event_id in feature.required_event_ids:
            event = events_by_id.get(event_id)
            if event is not None and event.source_state_id not in reachable_states:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_event_source_unreachable",
                        f"feature journey {feature.feature_id} event {event_id} source state is not reachable from launch",
                        item_id=feature.feature_id,
                        metadata={"event_id": event_id, "source_state_id": event.source_state_id},
                    )
                )
        handling_event_ids = set(feature.handling_event_ids())
        for failure_state_id in feature.failure_state_ids:
            failure_state = states_by_id.get(failure_state_id)
            if failure_state is None:
                continue
            if not failure_state.failure:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_failure_state_not_marked_failure",
                        f"feature journey {feature.feature_id} failure state {failure_state_id} is not marked failure",
                        item_id=feature.feature_id,
                    )
                )
            if failure_state.terminal:
                continue
            failure_outgoing = outgoing_by_state.get(failure_state_id, ())
            handled = any(event.event_id in handling_event_ids for event in failure_outgoing)
            if not handled:
                findings.append(
                    UIFlowStructureFinding(
                        "missing_feature_failure_handling",
                        f"feature journey {feature.feature_id} failure state {failure_state_id} has no named recovery, cancel, or exit event",
                        item_id=feature.feature_id,
                    )
                )
        if not feature.validation_boundaries:
            findings.append(
                UIFlowStructureFinding(
                    "missing_feature_validation",
                    f"feature journey {feature.feature_id} has no validation boundaries",
                    item_id=feature.feature_id,
                )
            )
        if not feature.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_feature_rationale",
                    f"feature journey {feature.feature_id} has no coverage rationale",
                    item_id=feature.feature_id,
                )
            )

    allowed_terminal_events = {
        (allowance.state_id, allowance.event_id): allowance
        for allowance in coverage.terminal_action_allowances
    }
    covered_event_ids = {
        entry.event_id
        for entry in coverage.entry_points
        if entry.event_id
    }
    for feature in coverage.feature_journeys:
        covered_event_ids.update(feature.required_event_ids)
        covered_event_ids.update(feature.handling_event_ids())
    covered_event_ids.update(allowance.event_id for allowance in coverage.terminal_action_allowances)
    covered_event_ids.update(blindspot_event_ids)

    uncovered_event_checks: set[str] = set()
    for state_id in sorted(reachable_states):
        state = states_by_id.get(state_id)
        if state is None:
            continue
        active_control_ids = state.enabled_controls if state.enabled_controls else state.visible_controls
        for control_id in active_control_ids:
            control = controls_by_id.get(control_id)
            if control is None or control.control_type in {"display", "label", "status"}:
                continue
            transitions = transitions_by_state_control.get((state_id, control_id), ())
            if not transitions and control_id not in blindspot_control_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "visible_control_without_modeled_event",
                        f"reachable state {state_id} exposes actionable control {control_id} without a modeled event or residual blindspot",
                        item_id=control_id,
                        metadata={"state_id": state_id},
                    )
                )
            for transition in transitions:
                uncovered_event_checks.add(transition.event_id)
        for transition in outgoing_by_state.get(state_id, ()):
            uncovered_event_checks.add(transition.event_id)
    for event_id in sorted(uncovered_event_checks):
        transition = events_by_id.get(event_id)
        if transition is None:
            continue
        if event_id in covered_event_ids or transition.control_id in blindspot_control_ids:
            continue
        findings.append(
            UIFlowStructureFinding(
                "journey_event_not_covered",
                f"reachable UI event {event_id} from state {transition.source_state_id} is not covered by any feature journey, terminal allowance, or residual blindspot",
                item_id=event_id,
                metadata={
                    "control_id": transition.control_id,
                    "source_state_id": transition.source_state_id,
                    "target_state_id": transition.target_state_id,
                },
            )
        )

    for allowance in coverage.terminal_action_allowances:
        if allowance.state_id not in state_ids:
            findings.append(
                UIFlowStructureFinding(
                    "terminal_allowance_state_not_registered",
                    f"terminal action allowance references unknown state {allowance.state_id}",
                    item_id=allowance.event_id,
                )
            )
        if allowance.event_id not in event_ids:
            findings.append(
                UIFlowStructureFinding(
                    "terminal_allowance_event_not_registered",
                    f"terminal action allowance references unknown event {allowance.event_id}",
                    item_id=allowance.event_id,
                )
            )
        event = events_by_id.get(allowance.event_id)
        if event is not None and event.source_state_id != allowance.state_id:
            findings.append(
                UIFlowStructureFinding(
                    "terminal_allowance_source_mismatch",
                    f"terminal action allowance {allowance.event_id} is declared for {allowance.state_id} but event starts at {event.source_state_id}",
                    item_id=allowance.event_id,
                )
            )
        if allowance.purpose not in _ALLOWED_TERMINAL_ACTION_PURPOSES:
            findings.append(
                UIFlowStructureFinding(
                    "terminal_action_purpose_not_allowed",
                    f"terminal action allowance {allowance.event_id} has unsupported purpose {allowance.purpose}",
                    item_id=allowance.event_id,
                )
            )
        if not allowance.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_terminal_action_rationale",
                    f"terminal action allowance {allowance.event_id} has no rationale",
                    item_id=allowance.event_id,
                )
            )

    for state in interaction_model.states:
        if not state.terminal:
            continue
        for transition in outgoing_by_state.get(state.state_id, ()):
            allowance = allowed_terminal_events.get((state.state_id, transition.event_id))
            if allowance is None:
                findings.append(
                    UIFlowStructureFinding(
                        "terminal_action_without_allowance",
                        f"terminal state {state.state_id} has outgoing event {transition.event_id} without an allowed terminal action purpose",
                        item_id=transition.event_id,
                    )
                )
                continue
            if transition.target_state_id != transition.source_state_id and allowance.purpose not in {
                "restart",
                "close",
                "recovery",
                "cancel",
                "exit",
            }:
                findings.append(
                    UIFlowStructureFinding(
                        "terminal_forward_action",
                        f"terminal state {state.state_id} event {transition.event_id} moves to {transition.target_state_id} without a restart, close, recovery, cancel, or exit purpose",
                        item_id=transition.event_id,
                    )
                )

    for blindspot in coverage.residual_blindspots:
        for control_id in blindspot.control_ids:
            if control_id not in control_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "blindspot_control_not_registered",
                        f"residual blindspot {blindspot.blindspot_id} references unknown control {control_id}",
                        item_id=blindspot.blindspot_id,
                    )
                )
        for event_id in blindspot.event_ids:
            if event_id not in event_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "blindspot_event_not_registered",
                        f"residual blindspot {blindspot.blindspot_id} references unknown event {event_id}",
                        item_id=blindspot.blindspot_id,
                    )
                )
        if not blindspot.control_ids and not blindspot.event_ids and not blindspot.feature_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_blindspot_scope",
                    f"residual blindspot {blindspot.blindspot_id} has no feature, control, or event scope",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.reason:
            findings.append(
                UIFlowStructureFinding(
                    "missing_blindspot_reason",
                    f"residual blindspot {blindspot.blindspot_id} has no reason",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.owner:
            findings.append(
                UIFlowStructureFinding(
                    "missing_blindspot_owner",
                    f"residual blindspot {blindspot.blindspot_id} has no owner or downstream check",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.validation_boundaries:
            findings.append(
                UIFlowStructureFinding(
                    "missing_blindspot_validation",
                    f"residual blindspot {blindspot.blindspot_id} has no validation boundary",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_blindspot_rationale",
                    f"residual blindspot {blindspot.blindspot_id} has no rationale",
                    item_id=blindspot.blindspot_id,
                )
            )

    blockers = _blocker_findings(findings)
    return UIJourneyCoverageReport(
        ok=not blockers,
        coverage_id=coverage.coverage_id,
        findings=tuple(findings),
        reachable_state_ids=tuple(sorted(reachable_states)),
    )


_PASSED_IMPLEMENTATION_RESULTS = {"passed", "pass", "ok"}
_PURE_UI_EXPOSURES = {"pure_ui", "ui_only", "navigation", "system"}


def review_ui_implementation_validation(
    validation: UIImplementationValidation,
    *,
    interaction_model: UIInteractionModel,
    journey_coverage: UIJourneyCoverage,
) -> UIImplementationValidationReport:
    """Review real UI evidence against feature contracts and UI journey coverage."""

    findings: list[UIFlowStructureFinding] = []
    state_ids = set(interaction_model.state_ids())
    control_ids = set(interaction_model.control_ids())
    event_ids = set(interaction_model.transition_event_ids())
    states_by_id = {state.state_id: state for state in interaction_model.states}
    controls_by_id = interaction_model.controls_by_id()
    events_by_id = _transitions_by_event(interaction_model)
    outgoing_by_state = _outgoing_transitions(interaction_model)
    transitions_by_state_control = _transitions_by_state_control(interaction_model)
    reachable_states = _reachable_state_ids(interaction_model, journey_coverage.launch_state_id)
    journeys_by_id = {feature.feature_id: feature for feature in journey_coverage.feature_journeys}
    entry_points_by_id = {entry.entry_id: entry for entry in journey_coverage.entry_points}
    contract_by_id = {contract.feature_id: contract for contract in validation.feature_contracts}

    blindspot_feature_ids = {
        blindspot.feature_id
        for blindspot in validation.implementation_blindspots
        if blindspot.feature_id
    }
    blindspot_control_ids = {
        control_id
        for blindspot in validation.implementation_blindspots
        for control_id in blindspot.control_ids
    }
    blindspot_event_ids = {
        event_id
        for blindspot in validation.implementation_blindspots
        for event_id in blindspot.event_ids
    }
    pure_ui_control_ids = set(validation.pure_ui_control_ids)
    pure_ui_event_ids = set(validation.pure_ui_event_ids)

    passed_runs = [
        run
        for run in validation.journey_runs
        if run.result.lower() in _PASSED_IMPLEMENTATION_RESULTS
    ]
    covered_feature_ids = {
        run.feature_id
        for run in passed_runs
        if run.feature_id
    }
    covered_event_ids = {
        event_id
        for run in passed_runs
        for event_id in run.covered_event_ids()
    }
    covered_control_ids = {
        control_id
        for run in passed_runs
        for control_id in run.covered_control_ids()
    }

    if not validation.validation_id:
        findings.append(
            UIFlowStructureFinding("missing_implementation_validation_id", "UI implementation validation has no id")
        )
    if not validation.source_feature_model_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_feature_model",
                "UI implementation validation has no source feature model id",
            )
        )
    if not validation.source_interaction_model_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_interaction_model",
                "UI implementation validation has no source UI interaction model id",
            )
        )
    elif validation.source_interaction_model_id != interaction_model.model_id:
        findings.append(
            UIFlowStructureFinding(
                "implementation_interaction_model_mismatch",
                "UI implementation validation does not reference the supplied interaction model",
                metadata={
                    "validation_source": validation.source_interaction_model_id,
                    "interaction_model": interaction_model.model_id,
                },
            )
        )
    if not validation.source_journey_coverage_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_journey_coverage",
                "UI implementation validation has no source journey coverage id",
            )
        )
    elif validation.source_journey_coverage_id != journey_coverage.coverage_id:
        findings.append(
            UIFlowStructureFinding(
                "implementation_journey_coverage_mismatch",
                "UI implementation validation does not reference the supplied journey coverage",
                metadata={
                    "validation_source": validation.source_journey_coverage_id,
                    "journey_coverage": journey_coverage.coverage_id,
                },
            )
        )
    if journey_coverage.source_interaction_model_id != interaction_model.model_id:
        findings.append(
            UIFlowStructureFinding(
                "journey_coverage_model_mismatch",
                "Supplied journey coverage does not reference the supplied interaction model",
            )
        )
    if not validation.journey_coverage_reviewed:
        findings.append(
            UIFlowStructureFinding(
                "journey_coverage_not_reviewed_for_implementation",
                "Implementation validation was reviewed before journey coverage was marked reviewed",
            )
        )
    if not validation.implementation_target:
        findings.append(
            UIFlowStructureFinding(
                "missing_implementation_target",
                "UI implementation validation has no implementation target",
            )
        )
    if not validation.current_model_revision:
        findings.append(
            UIFlowStructureFinding(
                "missing_current_model_revision",
                "UI implementation validation has no current model or implementation revision",
            )
        )
    if not validation.feature_contracts:
        findings.append(
            UIFlowStructureFinding(
                "missing_feature_contracts",
                "UI implementation validation has no feature contracts from the functional model",
            )
        )
    if not validation.journey_runs:
        findings.append(
            UIFlowStructureFinding(
                "missing_implementation_runs",
                "UI implementation validation has no browser, desktop, or manual journey runs",
            )
        )
    if not validation.validation_boundaries:
        findings.append(
            UIFlowStructureFinding(
                "missing_implementation_validation_plan",
                "UI implementation validation has no validation boundaries",
            )
        )
    if not validation.rationale:
        findings.append(
            UIFlowStructureFinding(
                "missing_implementation_validation_rationale",
                "UI implementation validation has no rationale",
            )
        )

    findings.extend(
        _duplicate_values(validation.feature_ids(), code="duplicate_feature_contract_id", noun="feature contract")
    )
    findings.extend(_duplicate_values(validation.run_ids(), code="duplicate_implementation_run_id", noun="implementation run"))
    findings.extend(
        _duplicate_values(validation.blindspot_ids(), code="duplicate_implementation_blindspot_id", noun="implementation blindspot")
    )

    for control_id in pure_ui_control_ids:
        if control_id not in control_ids:
            findings.append(
                UIFlowStructureFinding(
                    "pure_ui_control_not_registered",
                    f"pure UI control {control_id} is not in the interaction model",
                    item_id=control_id,
                )
            )
    for event_id in pure_ui_event_ids:
        if event_id not in event_ids:
            findings.append(
                UIFlowStructureFinding(
                    "pure_ui_event_not_registered",
                    f"pure UI event {event_id} is not in the interaction model",
                    item_id=event_id,
                )
            )

    for contract in validation.feature_contracts:
        if not contract.feature_id:
            findings.append(UIFlowStructureFinding("missing_feature_contract_id", "Feature contract has no id"))
            continue
        if not contract.validation_boundaries:
            findings.append(
                UIFlowStructureFinding(
                    "missing_feature_contract_validation",
                    f"feature contract {contract.feature_id} has no validation boundaries",
                    item_id=contract.feature_id,
                )
            )
        if not contract.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_feature_contract_rationale",
                    f"feature contract {contract.feature_id} has no rationale",
                    item_id=contract.feature_id,
                )
            )
        for control_id in contract.required_control_ids:
            if control_id not in control_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_contract_control_not_registered",
                        f"feature contract {contract.feature_id} references unknown control {control_id}",
                        item_id=contract.feature_id,
                    )
                )
        for event_id in contract.required_event_ids:
            if event_id not in event_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_contract_event_not_registered",
                        f"feature contract {contract.feature_id} references unknown event {event_id}",
                        item_id=contract.feature_id,
                    )
                )
        for journey_id in contract.journey_ids:
            if journey_id not in journeys_by_id:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_contract_journey_not_declared",
                        f"feature contract {contract.feature_id} references missing journey {journey_id}",
                        item_id=contract.feature_id,
                    )
                )
        for entry_point_id in contract.entry_point_ids:
            if entry_point_id not in entry_points_by_id:
                findings.append(
                    UIFlowStructureFinding(
                        "feature_contract_entry_not_declared",
                        f"feature contract {contract.feature_id} references missing entry point {entry_point_id}",
                        item_id=contract.feature_id,
                    )
                )
        if contract.user_visible and contract.exposure == "ui":
            journey_match = contract.feature_id in journeys_by_id or any(
                journey_id in journeys_by_id for journey_id in contract.journey_ids
            )
            entry_match = any(entry_point_id in entry_points_by_id for entry_point_id in contract.entry_point_ids)
            event_match = any(event_id in event_ids for event_id in contract.required_event_ids)
            if not (journey_match or entry_match or event_match or contract.feature_id in blindspot_feature_ids):
                findings.append(
                    UIFlowStructureFinding(
                        "feature_not_exposed_by_ui_model",
                        f"user-visible feature {contract.feature_id} has no UI journey, entry point, event, or implementation blindspot",
                        item_id=contract.feature_id,
                    )
                )

    owned_control_ids = set(validation.pure_ui_control_ids) | blindspot_control_ids
    owned_event_ids = set(validation.pure_ui_event_ids) | blindspot_event_ids
    for contract in validation.feature_contracts:
        owned_control_ids.update(contract.required_control_ids)
        owned_event_ids.update(contract.required_event_ids)
        if contract.exposure in _PURE_UI_EXPOSURES:
            owned_control_ids.update(contract.required_control_ids)
            owned_event_ids.update(contract.required_event_ids)
        for journey_id in contract.journey_ids or ((contract.feature_id,) if contract.feature_id else ()):
            journey = journeys_by_id.get(journey_id)
            if journey is None:
                continue
            owned_event_ids.update(journey.required_event_ids)
            owned_event_ids.update(journey.handling_event_ids())
            for event_id in journey.required_event_ids + journey.handling_event_ids():
                event = events_by_id.get(event_id)
                if event is not None:
                    owned_control_ids.add(event.control_id)

    for state_id in sorted(reachable_states):
        state = states_by_id.get(state_id)
        if state is None:
            continue
        active_control_ids = state.enabled_controls if state.enabled_controls else state.visible_controls
        for control_id in active_control_ids:
            control = controls_by_id.get(control_id)
            if control is None or control.control_type in {"display", "label", "status"}:
                continue
            transitions = transitions_by_state_control.get((state_id, control_id), ())
            if (
                control_id not in owned_control_ids
                and control.function_key not in contract_by_id
                and control_id not in covered_control_ids
            ):
                findings.append(
                    UIFlowStructureFinding(
                        "implementation_control_without_feature_owner",
                        f"reachable control {control_id} in state {state_id} has no feature contract, pure UI classification, run evidence, or blindspot",
                        item_id=control_id,
                        metadata={"state_id": state_id},
                    )
                )
            for transition in transitions:
                if (
                    transition.event_id not in owned_event_ids
                    and transition.function_block not in contract_by_id
                    and transition.event_id not in covered_event_ids
                ):
                    findings.append(
                        UIFlowStructureFinding(
                            "implementation_event_without_feature_owner",
                            f"reachable event {transition.event_id} has no feature contract, pure UI classification, run evidence, or blindspot",
                            item_id=transition.event_id,
                            metadata={"control_id": control_id, "state_id": state_id},
                        )
                    )

    for run in validation.journey_runs:
        if not run.run_id:
            findings.append(UIFlowStructureFinding("missing_implementation_run_id", "Implementation run has no id"))
        if not run.feature_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_feature",
                    f"implementation run {run.run_id} has no feature id",
                    item_id=run.run_id,
                )
            )
        elif run.feature_id not in contract_by_id and run.feature_id not in journeys_by_id and run.feature_id not in blindspot_feature_ids:
            findings.append(
                UIFlowStructureFinding(
                    "run_feature_not_declared",
                    f"implementation run {run.run_id} references unknown feature {run.feature_id}",
                    item_id=run.run_id,
                )
            )
        if run.journey_id and run.journey_id not in journeys_by_id:
            findings.append(
                UIFlowStructureFinding(
                    "run_journey_not_declared",
                    f"implementation run {run.run_id} references unknown journey {run.journey_id}",
                    item_id=run.run_id,
                )
            )
        if run.entry_point_id and run.entry_point_id not in entry_points_by_id:
            findings.append(
                UIFlowStructureFinding(
                    "run_entry_point_not_declared",
                    f"implementation run {run.run_id} references unknown entry point {run.entry_point_id}",
                    item_id=run.run_id,
                )
            )
        if run.result.lower() not in _PASSED_IMPLEMENTATION_RESULTS:
            findings.append(
                UIFlowStructureFinding(
                    "implementation_run_not_passed",
                    f"implementation run {run.run_id} result is {run.result}, not passed",
                    item_id=run.run_id,
                )
            )
        if not run.method:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_method",
                    f"implementation run {run.run_id} has no browser, desktop, or manual method",
                    item_id=run.run_id,
                )
            )
        if not run.evidence_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_evidence_ref",
                    f"implementation run {run.run_id} has no evidence reference",
                    item_id=run.run_id,
                )
            )
        if not run.model_revision:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_model_revision",
                    f"implementation run {run.run_id} has no model or implementation revision",
                    item_id=run.run_id,
                )
            )
        elif validation.current_model_revision and run.model_revision != validation.current_model_revision:
            findings.append(
                UIFlowStructureFinding(
                    "stale_implementation_evidence",
                    f"implementation run {run.run_id} validates {run.model_revision}, not current {validation.current_model_revision}",
                    item_id=run.run_id,
                    metadata={"run_revision": run.model_revision, "current_revision": validation.current_model_revision},
                )
            )
        if not run.steps:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_steps",
                    f"implementation run {run.run_id} has no modeled click-through steps",
                    item_id=run.run_id,
                )
            )
        if not run.validation_boundaries:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_validation",
                    f"implementation run {run.run_id} has no validation boundaries",
                    item_id=run.run_id,
                )
            )
        if not run.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_run_rationale",
                    f"implementation run {run.run_id} has no rationale",
                    item_id=run.run_id,
                )
            )
        findings.extend(
            _duplicate_values(
                tuple(step.step_id for step in run.steps),
                code="duplicate_implementation_step_id",
                noun=f"implementation step in {run.run_id}",
            )
        )
        for step in run.steps:
            event = events_by_id.get(step.event_id)
            if not step.step_id:
                findings.append(
                    UIFlowStructureFinding(
                        "missing_step_id",
                        f"implementation run {run.run_id} has a step without an id",
                        item_id=run.run_id,
                    )
                )
            if not step.event_id:
                findings.append(
                    UIFlowStructureFinding(
                        "missing_step_event",
                        f"implementation step {step.step_id} has no event id",
                        item_id=step.step_id,
                    )
                )
            elif step.event_id not in event_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "step_event_not_registered",
                        f"implementation step {step.step_id} references unknown event {step.event_id}",
                        item_id=step.step_id,
                    )
                )
            if step.control_id and step.control_id not in control_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "step_control_not_registered",
                        f"implementation step {step.step_id} references unknown control {step.control_id}",
                        item_id=step.step_id,
                    )
                )
            if step.source_state_id and step.source_state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "step_source_state_not_registered",
                        f"implementation step {step.step_id} references unknown source state {step.source_state_id}",
                        item_id=step.step_id,
                    )
                )
            if step.target_state_id and step.target_state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "step_target_state_not_registered",
                        f"implementation step {step.step_id} references unknown target state {step.target_state_id}",
                        item_id=step.step_id,
                    )
                )
            if step.observed_state_id and step.observed_state_id not in state_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "step_observed_state_not_registered",
                        f"implementation step {step.step_id} references unknown observed state {step.observed_state_id}",
                        item_id=step.step_id,
                    )
                )
            if event is not None:
                if step.control_id and step.control_id != event.control_id:
                    findings.append(
                        UIFlowStructureFinding(
                            "step_event_control_mismatch",
                            f"implementation step {step.step_id} control {step.control_id} does not match event {step.event_id}",
                            item_id=step.step_id,
                        )
                    )
                if step.source_state_id and step.source_state_id != event.source_state_id:
                    findings.append(
                        UIFlowStructureFinding(
                            "step_event_source_mismatch",
                            f"implementation step {step.step_id} source {step.source_state_id} does not match event {step.event_id}",
                            item_id=step.step_id,
                        )
                    )
                if step.target_state_id and step.target_state_id != event.target_state_id:
                    findings.append(
                        UIFlowStructureFinding(
                            "step_event_target_mismatch",
                            f"implementation step {step.step_id} target {step.target_state_id} does not match event {step.event_id}",
                            item_id=step.step_id,
                        )
                    )
            if not step.method:
                findings.append(
                    UIFlowStructureFinding(
                        "missing_step_method",
                        f"implementation step {step.step_id} has no validation method",
                        item_id=step.step_id,
                    )
                )
            if step.result.lower() not in _PASSED_IMPLEMENTATION_RESULTS:
                findings.append(
                    UIFlowStructureFinding(
                        "step_evidence_not_passed",
                        f"implementation step {step.step_id} result is {step.result}, not passed",
                        item_id=step.step_id,
                    )
                )
            if not step.evidence_ref:
                findings.append(
                    UIFlowStructureFinding(
                        "missing_step_evidence_ref",
                        f"implementation step {step.step_id} has no evidence reference",
                        item_id=step.step_id,
                    )
                )

    for journey in journey_coverage.feature_journeys:
        if journey.feature_id in blindspot_feature_ids:
            continue
        feature_run_events = {
            event_id
            for run in passed_runs
            if run.feature_id == journey.feature_id or run.journey_id == journey.feature_id
            for event_id in run.covered_event_ids()
        }
        if not feature_run_events:
            findings.append(
                UIFlowStructureFinding(
                    "missing_implementation_run_for_journey",
                    f"feature journey {journey.feature_id} has no passed implementation click-through run",
                    item_id=journey.feature_id,
                )
            )
            continue
        required_branch_events = set(journey.required_event_ids + journey.handling_event_ids())
        for event_id in sorted(required_branch_events):
            if event_id in blindspot_event_ids:
                continue
            if event_id not in feature_run_events:
                findings.append(
                    UIFlowStructureFinding(
                        "missing_implementation_event_evidence",
                        f"feature journey {journey.feature_id} event {event_id} has no passed implementation step evidence",
                        item_id=journey.feature_id,
                        metadata={"event_id": event_id},
                    )
                )

    for blindspot in validation.implementation_blindspots:
        for control_id in blindspot.control_ids:
            if control_id not in control_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "implementation_blindspot_control_not_registered",
                        f"implementation blindspot {blindspot.blindspot_id} references unknown control {control_id}",
                        item_id=blindspot.blindspot_id,
                    )
                )
        for event_id in blindspot.event_ids:
            if event_id not in event_ids:
                findings.append(
                    UIFlowStructureFinding(
                        "implementation_blindspot_event_not_registered",
                        f"implementation blindspot {blindspot.blindspot_id} references unknown event {event_id}",
                        item_id=blindspot.blindspot_id,
                    )
                )
        if not blindspot.feature_id and not blindspot.control_ids and not blindspot.event_ids:
            findings.append(
                UIFlowStructureFinding(
                    "missing_implementation_blindspot_scope",
                    f"implementation blindspot {blindspot.blindspot_id} has no feature, control, or event scope",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.reason:
            findings.append(
                UIFlowStructureFinding(
                    "missing_implementation_blindspot_reason",
                    f"implementation blindspot {blindspot.blindspot_id} has no reason",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.owner:
            findings.append(
                UIFlowStructureFinding(
                    "missing_implementation_blindspot_owner",
                    f"implementation blindspot {blindspot.blindspot_id} has no owner",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.validation_boundaries:
            findings.append(
                UIFlowStructureFinding(
                    "missing_implementation_blindspot_validation",
                    f"implementation blindspot {blindspot.blindspot_id} has no validation boundary",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_implementation_blindspot_rationale",
                    f"implementation blindspot {blindspot.blindspot_id} has no rationale",
                    item_id=blindspot.blindspot_id,
                )
            )

    blockers = _blocker_findings(findings)
    return UIImplementationValidationReport(
        ok=not blockers,
        validation_id=validation.validation_id,
        findings=tuple(findings),
        covered_feature_ids=tuple(sorted(covered_feature_ids)),
        covered_event_ids=tuple(sorted(covered_event_ids)),
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


def review_ui_text_hierarchy(
    blueprint: UITextHierarchyBlueprint,
    *,
    interaction_model: UIInteractionModel | None = None,
    structure_derivation: UIStructureDerivation | None = None,
) -> UITextHierarchyReport:
    """Review whether UI text hierarchy follows from the modeled UI structure."""

    findings: list[UIFlowStructureFinding] = []
    token_ids = set(blueprint.token_ids())
    text_ids = set(blueprint.text_ids())
    tokens_by_id = blueprint.tokens_by_id()
    text_by_id = blueprint.text_by_id()
    region_ids = set(structure_derivation.region_ids()) if structure_derivation is not None else set()
    state_regions = structure_derivation.state_regions() if structure_derivation is not None else {}
    control_regions = structure_derivation.control_regions() if structure_derivation is not None else {}
    display_regions = structure_derivation.display_regions() if structure_derivation is not None else {}

    if not blueprint.blueprint_id:
        findings.append(UIFlowStructureFinding("missing_text_blueprint_id", "UI text hierarchy has no blueprint id"))
    if not blueprint.source_interaction_model_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_interaction_model",
                "UI text hierarchy has no source UI interaction model id",
            )
        )
    if interaction_model is not None and blueprint.source_interaction_model_id != interaction_model.model_id:
        findings.append(
            UIFlowStructureFinding(
                "source_interaction_model_mismatch",
                "UI text hierarchy does not reference the supplied interaction model",
                metadata={
                    "blueprint_source": blueprint.source_interaction_model_id,
                    "interaction_model": interaction_model.model_id,
                },
            )
        )
    if not blueprint.source_structure_derivation_id:
        findings.append(
            UIFlowStructureFinding(
                "missing_source_structure_derivation",
                "UI text hierarchy has no source UI structure derivation id",
            )
        )
    if structure_derivation is not None and blueprint.source_structure_derivation_id != structure_derivation.derivation_id:
        findings.append(
            UIFlowStructureFinding(
                "source_structure_derivation_mismatch",
                "UI text hierarchy does not reference the supplied structure derivation",
                metadata={
                    "blueprint_source": blueprint.source_structure_derivation_id,
                    "structure_derivation": structure_derivation.derivation_id,
                },
            )
        )
    if not blueprint.structure_derivation_reviewed:
        findings.append(
            UIFlowStructureFinding(
                "source_structure_derivation_not_reviewed",
                "UI text hierarchy was derived before the UI structure derivation was marked reviewed",
            )
        )
    if not blueprint.parent_surface_id:
        findings.append(UIFlowStructureFinding("missing_parent_surface", "UI text hierarchy has no parent UI surface"))
    if not blueprint.typography_tokens:
        findings.append(
            UIFlowStructureFinding("missing_typography_tokens", "UI text hierarchy defines no typography tokens")
        )
    if not blueprint.text_elements:
        findings.append(UIFlowStructureFinding("missing_text_elements", "UI text hierarchy defines no text elements"))
    if not blueprint.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_validation_plan", "UI text hierarchy has no validation boundaries")
        )
    if not blueprint.rationale:
        findings.append(
            UIFlowStructureFinding(
                "missing_text_hierarchy_rationale",
                "UI text hierarchy has no rationale for deriving text roles from UI structure",
            )
        )

    findings.extend(_duplicate_values(blueprint.token_ids(), code="duplicate_typography_token_id", noun="token"))
    findings.extend(_duplicate_values(blueprint.text_ids(), code="duplicate_text_element_id", noun="text"))

    for token in blueprint.typography_tokens:
        if not token.token_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_typography_token_id",
                    "typography token has no token id",
                    metadata=token.to_dict(),
                )
            )
        if token.hierarchy_level < 1:
            findings.append(
                UIFlowStructureFinding(
                    "invalid_typography_hierarchy_level",
                    f"typography token {token.token_id} has invalid hierarchy level {token.hierarchy_level}",
                    item_id=token.token_id,
                )
            )
        if not token.text_roles:
            findings.append(
                UIFlowStructureFinding(
                    "missing_typography_token_roles",
                    f"typography token {token.token_id} is not assigned to any text roles",
                    item_id=token.token_id,
                )
            )
        if not token.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_typography_token_rationale",
                    f"typography token {token.token_id} has no hierarchy rationale",
                    item_id=token.token_id,
                )
            )

    known_states = set(interaction_model.state_ids()) if interaction_model is not None else set()
    known_controls = set(interaction_model.control_ids()) if interaction_model is not None else set()
    known_displays = set(interaction_model.display_ids()) if interaction_model is not None else set()
    controls_by_id = interaction_model.controls_by_id() if interaction_model is not None else {}
    displays_by_id = interaction_model.displays_by_id() if interaction_model is not None else {}

    for text in blueprint.text_elements:
        if not text.text_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_text_element_id",
                    "text element has no text id",
                    metadata=text.to_dict(),
                )
            )
        if not text.role:
            findings.append(
                UIFlowStructureFinding(
                    "missing_text_role",
                    f"text element {text.text_id} has no semantic text role",
                    item_id=text.text_id,
                )
            )
        if not text.token_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_text_token",
                    f"text element {text.text_id} has no typography token",
                    item_id=text.text_id,
                )
            )
        elif text.token_id not in token_ids:
            findings.append(
                UIFlowStructureFinding(
                    "text_token_not_registered",
                    f"text element {text.text_id} references unknown typography token {text.token_id}",
                    item_id=text.text_id,
                )
            )
        else:
            token = tokens_by_id[text.token_id]
            if token.text_roles and text.role not in token.text_roles:
                findings.append(
                    UIFlowStructureFinding(
                        "text_token_role_mismatch",
                        f"text element {text.text_id} role {text.role} does not match token {text.token_id}",
                        item_id=text.text_id,
                        metadata={"token_roles": list(token.text_roles)},
                    )
                )
            minimum_level = _ROLE_MIN_HIERARCHY_LEVEL.get(text.role)
            if minimum_level is not None and token.hierarchy_level < minimum_level:
                findings.append(
                    UIFlowStructureFinding(
                        "text_role_too_prominent",
                        f"text element {text.text_id} uses token {text.token_id} above its role level",
                        item_id=text.text_id,
                        metadata={
                            "role": text.role,
                            "token_level": token.hierarchy_level,
                            "minimum_level": minimum_level,
                        },
                    )
                )
        if not text.semantic_key:
            findings.append(
                UIFlowStructureFinding(
                    "missing_text_semantic_key",
                    f"text element {text.text_id} has no semantic key for duplicate text review",
                    item_id=text.text_id,
                )
            )
        if structure_derivation is not None and not text.region_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_text_region",
                    f"text element {text.text_id} is not assigned to a UI region",
                    item_id=text.text_id,
                )
            )
        if structure_derivation is not None and text.region_id and text.region_id not in region_ids:
            findings.append(
                UIFlowStructureFinding(
                    "text_region_not_registered",
                    f"text element {text.text_id} is assigned to unknown region {text.region_id}",
                    item_id=text.text_id,
                )
            )
        if text.parent_text_id and text.parent_text_id not in text_ids:
            findings.append(
                UIFlowStructureFinding(
                    "parent_text_not_registered",
                    f"text element {text.text_id} references unknown parent text {text.parent_text_id}",
                    item_id=text.text_id,
                )
            )
        if not text.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_text_rationale",
                    f"text element {text.text_id} has no role or hierarchy rationale",
                    item_id=text.text_id,
                )
            )
        if (
            text.role not in {"page_title", "section_title", "panel_title"}
            and not text.source_control_id
            and not text.source_display_id
            and not text.source_state_ids
            and not text.parent_text_id
        ):
            findings.append(
                UIFlowStructureFinding(
                    "unanchored_text_element",
                    f"text element {text.text_id} is not anchored to a state, control, display, or parent text",
                    item_id=text.text_id,
                )
            )

        for state_id in text.source_state_ids + text.visible_in_states:
            if interaction_model is not None and state_id not in known_states:
                findings.append(
                    UIFlowStructureFinding(
                        "text_state_not_in_interaction_model",
                        f"text element {text.text_id} references unknown state {state_id}",
                        item_id=text.text_id,
                    )
                )
        if interaction_model is not None and text.source_control_id:
            if text.source_control_id not in known_controls:
                findings.append(
                    UIFlowStructureFinding(
                        "text_control_not_in_interaction_model",
                        f"text element {text.text_id} references unknown control {text.source_control_id}",
                        item_id=text.text_id,
                    )
                )
            elif text.role not in _CONTROL_TEXT_ROLES:
                findings.append(
                    UIFlowStructureFinding(
                        "control_text_role_mismatch",
                        f"control text {text.text_id} uses role {text.role} instead of a control label role",
                        item_id=text.text_id,
                    )
                )
        if interaction_model is not None and text.source_display_id:
            if text.source_display_id not in known_displays:
                findings.append(
                    UIFlowStructureFinding(
                        "text_display_not_in_interaction_model",
                        f"text element {text.text_id} references unknown display {text.source_display_id}",
                        item_id=text.text_id,
                    )
                )
            else:
                display = displays_by_id[text.source_display_id]
                if display.semantic_key and text.semantic_key and text.semantic_key != display.semantic_key:
                    findings.append(
                        UIFlowStructureFinding(
                            "text_display_semantic_mismatch",
                            f"text element {text.text_id} semantic key does not match source display {text.source_display_id}",
                            item_id=text.text_id,
                            metadata={"text_semantic_key": text.semantic_key, "display_semantic_key": display.semantic_key},
                        )
                    )
                if text.role in _CONTROL_TEXT_ROLES:
                    findings.append(
                        UIFlowStructureFinding(
                            "display_text_role_mismatch",
                            f"display text {text.text_id} uses control label role {text.role}",
                            item_id=text.text_id,
                        )
                    )

        if structure_derivation is not None and text.source_control_id:
            expected_region = control_regions.get(text.source_control_id, "")
            if expected_region and text.region_id and text.region_id != expected_region:
                findings.append(
                    UIFlowStructureFinding(
                        "text_region_mismatch_control_owner",
                        f"text element {text.text_id} is not in the owning region for control {text.source_control_id}",
                        item_id=text.text_id,
                        metadata={"text_region": text.region_id, "expected_region": expected_region},
                    )
                )
        if structure_derivation is not None and text.source_display_id:
            expected_region = display_regions.get(text.source_display_id, "")
            if expected_region and text.region_id and text.region_id != expected_region:
                findings.append(
                    UIFlowStructureFinding(
                        "text_region_mismatch_display_owner",
                        f"text element {text.text_id} is not in the owning region for display {text.source_display_id}",
                        item_id=text.text_id,
                        metadata={"text_region": text.region_id, "expected_region": expected_region},
                    )
                )
        if structure_derivation is not None and text.source_state_ids and text.region_id:
            expected_regions = {state_regions.get(state_id, "") for state_id in text.source_state_ids}
            expected_regions.discard("")
            if len(expected_regions) == 1 and text.region_id not in expected_regions:
                findings.append(
                    UIFlowStructureFinding(
                        "text_region_mismatch_state_owner",
                        f"text element {text.text_id} is not in the owning region for its source state",
                        item_id=text.text_id,
                        metadata={"text_region": text.region_id, "expected_regions": sorted(expected_regions)},
                    )
                )

    for text in blueprint.text_elements:
        if not text.parent_text_id or text.parent_text_id not in text_by_id:
            continue
        parent = text_by_id[text.parent_text_id]
        parent_token = tokens_by_id.get(parent.token_id)
        child_token = tokens_by_id.get(text.token_id)
        if parent_token is None or child_token is None:
            continue
        if child_token.hierarchy_level <= parent_token.hierarchy_level:
            findings.append(
                UIFlowStructureFinding(
                    "child_text_not_less_prominent_than_parent",
                    f"text element {text.text_id} is not visually subordinate to parent {parent.text_id}",
                    item_id=text.text_id,
                    metadata={
                        "parent_level": parent_token.hierarchy_level,
                        "child_level": child_token.hierarchy_level,
                    },
                )
            )

    for (region_id, state_id, semantic_key), elements in sorted(
        _scoped_groups_by_key(blueprint.text_elements, "semantic_key").items()
    ):
        if len(elements) > 1 and not _redundancy_justified(elements):
            findings.append(
                UIFlowStructureFinding(
                    "duplicate_text_semantic_same_region_state",
                    f"region {region_id or '(none)'} repeats semantic text {semantic_key} in state {state_id}",
                    item_id=region_id,
                    metadata={"text_ids": sorted(text.text_id for text in elements)},
                )
            )

    title_elements = [text for text in blueprint.text_elements if text.role in _TITLE_TEXT_ROLES]
    for (region_id, state_id, role), elements in sorted(_scoped_groups_by_key(title_elements, "role").items()):
        if len(elements) > 1 and not _redundancy_justified(elements):
            findings.append(
                UIFlowStructureFinding(
                    "duplicate_title_role_same_region_state",
                    f"region {region_id or '(none)'} has multiple {role} text elements in state {state_id}",
                    item_id=region_id,
                    metadata={"text_ids": sorted(text.text_id for text in elements)},
                )
            )

    blockers = _blocker_findings(findings)
    return UITextHierarchyReport(
        ok=not blockers,
        blueprint_id=blueprint.blueprint_id,
        findings=tuple(findings),
    )


__all__ = [
    "UIControl",
    "UIDisplayElement",
    "UIFeatureJourney",
    "UIFeatureContract",
    "UIFlowStructureFinding",
    "UIImplementationBlindspot",
    "UIImplementationJourneyRun",
    "UIImplementationStepEvidence",
    "UIImplementationValidation",
    "UIImplementationValidationReport",
    "UIInteractionModel",
    "UIInteractionModelReport",
    "UIJourneyCoverage",
    "UIJourneyCoverageReport",
    "UIJourneyEntryPoint",
    "UIRegionRecommendation",
    "UIResidualBlindspot",
    "UIStateNode",
    "UIStructureDerivation",
    "UIStructureDerivationReport",
    "UITextElement",
    "UITextHierarchyBlueprint",
    "UITextHierarchyReport",
    "UITypographyToken",
    "UITerminalActionAllowance",
    "UITransition",
    "review_ui_implementation_validation",
    "review_ui_interaction_model",
    "review_ui_journey_coverage",
    "review_ui_structure_derivation",
    "review_ui_text_hierarchy",
]
