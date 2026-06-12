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
    code_contract_id: str = ""
    runtime_node_id: str = ""
    output: str = ""
    side_effects: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "source_state_id", str(self.source_state_id))
        object.__setattr__(self, "target_state_id", str(self.target_state_id))
        object.__setattr__(self, "function_block", str(self.function_block))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "runtime_node_id", str(self.runtime_node_id))
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
            "code_contract_id": self.code_contract_id,
            "runtime_node_id": self.runtime_node_id,
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
class UIBlindspot:
    """One intentionally scoped or unverified UI branch with its validation boundary."""

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
    residual_blindspots: tuple[UIBlindspot, ...] = ()
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
    implementation_blindspots: tuple[UIBlindspot, ...] = ()
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
class UIVisibleSurfaceItem:
    """One user-facing text/control/status item visible on a UI surface."""

    item_id: str
    item_kind: str = "text"
    text: str = ""
    state_ids: tuple[str, ...] = ()
    region_id: str = ""
    owner_control_id: str = ""
    owner_display_id: str = ""
    purpose: str = ""
    disabled_reason: str = ""
    priority: str = "secondary"
    placeholder: bool = False
    presents_as_functionality: bool = False
    internal_term_rationale: str = ""
    redundancy_rationale: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_kind", str(self.item_kind))
        object.__setattr__(self, "text", str(self.text))
        object.__setattr__(self, "state_ids", _as_tuple(self.state_ids))
        object.__setattr__(self, "region_id", str(self.region_id))
        object.__setattr__(self, "owner_control_id", str(self.owner_control_id))
        object.__setattr__(self, "owner_display_id", str(self.owner_display_id))
        object.__setattr__(self, "purpose", str(self.purpose))
        object.__setattr__(self, "disabled_reason", str(self.disabled_reason))
        object.__setattr__(self, "priority", str(self.priority))
        object.__setattr__(self, "placeholder", bool(self.placeholder))
        object.__setattr__(self, "presents_as_functionality", bool(self.presents_as_functionality))
        object.__setattr__(self, "internal_term_rationale", str(self.internal_term_rationale))
        object.__setattr__(self, "redundancy_rationale", str(self.redundancy_rationale))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_kind": self.item_kind,
            "text": self.text,
            "state_ids": list(self.state_ids),
            "region_id": self.region_id,
            "owner_control_id": self.owner_control_id,
            "owner_display_id": self.owner_display_id,
            "purpose": self.purpose,
            "disabled_reason": self.disabled_reason,
            "priority": self.priority,
            "placeholder": self.placeholder,
            "presents_as_functionality": self.presents_as_functionality,
            "internal_term_rationale": self.internal_term_rationale,
            "redundancy_rationale": self.redundancy_rationale,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIVisibleSurface:
    """Visible UI surface inventory before visual design or implementation claims."""

    surface_id: str
    source_interaction_model_id: str = ""
    items: tuple[UIVisibleSurfaceItem, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "items": [item.to_dict() for item in self.items],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


OBSERVED_UI_ITEM_KINDS = (
    "button",
    "icon_button",
    "input",
    "select",
    "dropdown",
    "checkbox",
    "toggle",
    "tab",
    "table",
    "display_field",
    "status_text",
    "native_dialog_trigger",
    "command",
    "menu_item",
    "link",
    "text",
)

OBSERVED_UI_ACTIONABLE_KINDS = (
    "button",
    "icon_button",
    "input",
    "select",
    "dropdown",
    "checkbox",
    "toggle",
    "tab",
    "native_dialog_trigger",
    "command",
    "menu_item",
    "link",
)

FUNCTIONAL_CHAIN_EVIDENCE_KINDS = (
    "browser_click",
    "desktop_click",
    "runtime_trace",
    "log",
    "test_result",
    "manual_observation",
)

MATLAB_CALLBACK_KINDS = (
    "uigetfile",
    "uigetdir",
    "winopen",
    "no_callback",
    "ordinary_callback",
)

MATLAB_CALLBACK_REQUIRED_BRANCHES = {
    "uigetfile": ("choose", "cancel", "path_selected", "load_result", "error_path"),
    "uigetdir": ("choose", "cancel", "path_selected", "load_result", "error_path"),
    "winopen": ("trigger", "opened", "error_path"),
    "no_callback": ("visible_disposition",),
    "ordinary_callback": ("trigger", "success", "error_path"),
}

MATLAB_NO_CALLBACK_DISPOSITIONS = ("disabled", "non_functional", "replacement_chain", "out_of_scope")


@dataclass(frozen=True)
class UIObservedSurfaceItem:
    """One item observed on the real rendered UI before model completion is claimed."""

    item_id: str
    item_kind: str
    label: str = ""
    state_id: str = ""
    region_id: str = ""
    selector: str = ""
    visible: bool = True
    enabled: bool = False
    mapped_control_id: str = ""
    mapped_display_id: str = ""
    mapped_visible_item_id: str = ""
    blindspot_id: str = ""
    evidence_ref: str = ""
    evidence_kind: str = "manual_observation"
    observed_value: str = ""
    options: tuple[str, ...] = ()
    table_columns: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_kind", str(self.item_kind))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "state_id", str(self.state_id))
        object.__setattr__(self, "region_id", str(self.region_id))
        object.__setattr__(self, "selector", str(self.selector))
        object.__setattr__(self, "visible", bool(self.visible))
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "mapped_control_id", str(self.mapped_control_id))
        object.__setattr__(self, "mapped_display_id", str(self.mapped_display_id))
        object.__setattr__(self, "mapped_visible_item_id", str(self.mapped_visible_item_id))
        object.__setattr__(self, "blindspot_id", str(self.blindspot_id))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "evidence_kind", str(self.evidence_kind))
        object.__setattr__(self, "observed_value", str(self.observed_value))
        object.__setattr__(self, "options", _as_tuple(self.options))
        object.__setattr__(self, "table_columns", _as_tuple(self.table_columns))
        object.__setattr__(self, "rationale", str(self.rationale))

    def owner_ids(self) -> tuple[str, ...]:
        return tuple(
            owner
            for owner in (
                self.mapped_control_id,
                self.mapped_display_id,
                self.mapped_visible_item_id,
                self.blindspot_id,
            )
            if owner
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_kind": self.item_kind,
            "label": self.label,
            "state_id": self.state_id,
            "region_id": self.region_id,
            "selector": self.selector,
            "visible": self.visible,
            "enabled": self.enabled,
            "mapped_control_id": self.mapped_control_id,
            "mapped_display_id": self.mapped_display_id,
            "mapped_visible_item_id": self.mapped_visible_item_id,
            "blindspot_id": self.blindspot_id,
            "evidence_ref": self.evidence_ref,
            "evidence_kind": self.evidence_kind,
            "observed_value": self.observed_value,
            "options": list(self.options),
            "table_columns": list(self.table_columns),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIObservedSurfaceInventory:
    """Observed real UI inventory for an existing, migrated, or runnable UI target."""

    inventory_id: str
    observation_target: str
    current_revision: str
    observation_method: str = ""
    source_interaction_model_id: str = ""
    source_visible_surface_id: str = ""
    evidence_ref: str = ""
    items: tuple[UIObservedSurfaceItem, ...] = ()
    scoped_blindspots: tuple[UIBlindspot, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "inventory_id", str(self.inventory_id))
        object.__setattr__(self, "observation_target", str(self.observation_target))
        object.__setattr__(self, "current_revision", str(self.current_revision))
        object.__setattr__(self, "observation_method", str(self.observation_method))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "source_visible_surface_id", str(self.source_visible_surface_id))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "scoped_blindspots", tuple(self.scoped_blindspots))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items)

    def blindspot_ids(self) -> tuple[str, ...]:
        return tuple(blindspot.blindspot_id for blindspot in self.scoped_blindspots)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_id": self.inventory_id,
            "observation_target": self.observation_target,
            "current_revision": self.current_revision,
            "observation_method": self.observation_method,
            "source_interaction_model_id": self.source_interaction_model_id,
            "source_visible_surface_id": self.source_visible_surface_id,
            "evidence_ref": self.evidence_ref,
            "items": [item.to_dict() for item in self.items],
            "scoped_blindspots": [blindspot.to_dict() for blindspot in self.scoped_blindspots],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIControlFunctionalChain:
    """Click-to-effect proof for one enabled actionable UI control."""

    chain_id: str
    control_id: str
    event_id: str
    code_owner: str
    function_ref: str
    function_kind: str = "local"
    observed_state_id: str = ""
    observed_display_id: str = ""
    observed_output: str = ""
    evidence_ref: str = ""
    evidence_kind: str = "browser_click"
    result: str = "passed"
    current_revision: str = ""
    native_boundary: str = ""
    manual_boundary: str = ""
    blindspot_id: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_id", str(self.chain_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "code_owner", str(self.code_owner))
        object.__setattr__(self, "function_ref", str(self.function_ref))
        object.__setattr__(self, "function_kind", str(self.function_kind))
        object.__setattr__(self, "observed_state_id", str(self.observed_state_id))
        object.__setattr__(self, "observed_display_id", str(self.observed_display_id))
        object.__setattr__(self, "observed_output", str(self.observed_output))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "evidence_kind", str(self.evidence_kind))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "current_revision", str(self.current_revision))
        object.__setattr__(self, "native_boundary", str(self.native_boundary))
        object.__setattr__(self, "manual_boundary", str(self.manual_boundary))
        object.__setattr__(self, "blindspot_id", str(self.blindspot_id))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_observed_ui_effect(self) -> bool:
        return bool(self.observed_state_id or self.observed_display_id or self.observed_output)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "control_id": self.control_id,
            "event_id": self.event_id,
            "code_owner": self.code_owner,
            "function_ref": self.function_ref,
            "function_kind": self.function_kind,
            "observed_state_id": self.observed_state_id,
            "observed_display_id": self.observed_display_id,
            "observed_output": self.observed_output,
            "evidence_ref": self.evidence_ref,
            "evidence_kind": self.evidence_kind,
            "result": self.result,
            "current_revision": self.current_revision,
            "native_boundary": self.native_boundary,
            "manual_boundary": self.manual_boundary,
            "blindspot_id": self.blindspot_id,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIControlFunctionalChainSet:
    """Functional-chain evidence for enabled controls in an observed UI inventory."""

    chain_set_id: str
    source_inventory_id: str = ""
    source_interaction_model_id: str = ""
    source_implementation_validation_id: str = ""
    current_revision: str = ""
    chains: tuple[UIControlFunctionalChain, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_set_id", str(self.chain_set_id))
        object.__setattr__(self, "source_inventory_id", str(self.source_inventory_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "source_implementation_validation_id", str(self.source_implementation_validation_id))
        object.__setattr__(self, "current_revision", str(self.current_revision))
        object.__setattr__(self, "chains", tuple(self.chains))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def chain_ids(self) -> tuple[str, ...]:
        return tuple(chain.chain_id for chain in self.chains)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_set_id": self.chain_set_id,
            "source_inventory_id": self.source_inventory_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "source_implementation_validation_id": self.source_implementation_validation_id,
            "current_revision": self.current_revision,
            "chains": [chain.to_dict() for chain in self.chains],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MATLABCallbackSemantics:
    """Baseline callback semantics for MATLAB-to-UI migration parity."""

    semantic_id: str
    control_id: str
    callback_kind: str
    baseline_callback: str = ""
    required_branches: tuple[str, ...] = ()
    covered_branches: tuple[str, ...] = ()
    evidence_ref: str = ""
    result: str = "passed"
    native_boundary: str = ""
    manual_boundary: str = ""
    migration_disposition: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "semantic_id", str(self.semantic_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "callback_kind", str(self.callback_kind))
        object.__setattr__(self, "baseline_callback", str(self.baseline_callback))
        object.__setattr__(self, "required_branches", _as_tuple(self.required_branches))
        object.__setattr__(self, "covered_branches", _as_tuple(self.covered_branches))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "native_boundary", str(self.native_boundary))
        object.__setattr__(self, "manual_boundary", str(self.manual_boundary))
        object.__setattr__(self, "migration_disposition", str(self.migration_disposition))
        object.__setattr__(self, "rationale", str(self.rationale))

    def expected_branches(self) -> tuple[str, ...]:
        if self.required_branches:
            return self.required_branches
        return MATLAB_CALLBACK_REQUIRED_BRANCHES.get(self.callback_kind, ())

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_id": self.semantic_id,
            "control_id": self.control_id,
            "callback_kind": self.callback_kind,
            "baseline_callback": self.baseline_callback,
            "required_branches": list(self.required_branches),
            "covered_branches": list(self.covered_branches),
            "evidence_ref": self.evidence_ref,
            "result": self.result,
            "native_boundary": self.native_boundary,
            "manual_boundary": self.manual_boundary,
            "migration_disposition": self.migration_disposition,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MATLABBaselineCallbackGate:
    """MATLAB callback semantics gate for migration UI parity claims."""

    gate_id: str
    source_baseline_ref: str
    target_ui_revision: str
    callbacks: tuple[MATLABCallbackSemantics, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", str(self.gate_id))
        object.__setattr__(self, "source_baseline_ref", str(self.source_baseline_ref))
        object.__setattr__(self, "target_ui_revision", str(self.target_ui_revision))
        object.__setattr__(self, "callbacks", tuple(self.callbacks))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def semantic_ids(self) -> tuple[str, ...]:
        return tuple(callback.semantic_id for callback in self.callbacks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "source_baseline_ref": self.source_baseline_ref,
            "target_ui_revision": self.target_ui_revision,
            "callbacks": [callback.to_dict() for callback in self.callbacks],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


UI_HUMAN_OPERABILITY_EVIDENCE_KINDS = (
    "task_coverage",
    "affordance_review",
    "action_grammar",
    "dialog_return",
    "keyboard_focus",
    "human_walkthrough",
    "manual_observation",
    "browser_click",
    "desktop_click",
    "test_result",
)

UI_PERCEIVED_ACTIONABLE_ROLES = (
    "button",
    "icon_button",
    "input",
    "select",
    "dropdown",
    "checkbox",
    "toggle",
    "tab",
    "link",
    "menu_item",
)

UI_ACTUAL_ACTIONABLE_ROLES = (
    "actionable",
    "editable",
    "selectable",
    "navigates",
    "opens_dialog",
)

UI_ACTUAL_NON_ACTIONABLE_ROLES = (
    "readonly",
    "status",
    "display",
    "container",
    "title",
    "decorative",
)

UI_AFFORDANCE_MISMATCH_DISPOSITIONS = (
    "clarify",
    "restyle",
    "disable",
    "label_as_readonly",
    "scoped",
)

UI_REGION_ROLES = (
    "input",
    "action",
    "result",
    "status",
    "recovery",
    "navigation",
    "dialog",
    "mixed",
)

UI_DIALOG_TYPES = (
    "native_file_picker",
    "native_dir_picker",
    "save_dialog",
    "os_shell",
    "custom_modal",
    "popover",
    "drawer",
)


@dataclass(frozen=True)
class UIUserTaskFrame:
    """One user task that bridges functional capability and UI path."""

    task_id: str
    user_goal: str
    source_feature_ids: tuple[str, ...] = ()
    entry_state_ids: tuple[str, ...] = ()
    main_path_event_ids: tuple[str, ...] = ()
    alternate_path_event_ids: tuple[str, ...] = ()
    cancel_event_ids: tuple[str, ...] = ()
    error_state_ids: tuple[str, ...] = ()
    success_state_ids: tuple[str, ...] = ()
    required_control_ids: tuple[str, ...] = ()
    required_display_ids: tuple[str, ...] = ()
    required_dialog_ids: tuple[str, ...] = ()
    required_feedback_item_ids: tuple[str, ...] = ()
    keyboard_contract_id: str = ""
    cancel_behavior: str = ""
    error_behavior: str = ""
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "user_goal", str(self.user_goal))
        object.__setattr__(self, "source_feature_ids", _as_tuple(self.source_feature_ids))
        object.__setattr__(self, "entry_state_ids", _as_tuple(self.entry_state_ids))
        object.__setattr__(self, "main_path_event_ids", _as_tuple(self.main_path_event_ids))
        object.__setattr__(self, "alternate_path_event_ids", _as_tuple(self.alternate_path_event_ids))
        object.__setattr__(self, "cancel_event_ids", _as_tuple(self.cancel_event_ids))
        object.__setattr__(self, "error_state_ids", _as_tuple(self.error_state_ids))
        object.__setattr__(self, "success_state_ids", _as_tuple(self.success_state_ids))
        object.__setattr__(self, "required_control_ids", _as_tuple(self.required_control_ids))
        object.__setattr__(self, "required_display_ids", _as_tuple(self.required_display_ids))
        object.__setattr__(self, "required_dialog_ids", _as_tuple(self.required_dialog_ids))
        object.__setattr__(self, "required_feedback_item_ids", _as_tuple(self.required_feedback_item_ids))
        object.__setattr__(self, "keyboard_contract_id", str(self.keyboard_contract_id))
        object.__setattr__(self, "cancel_behavior", str(self.cancel_behavior))
        object.__setattr__(self, "error_behavior", str(self.error_behavior))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_goal": self.user_goal,
            "source_feature_ids": list(self.source_feature_ids),
            "entry_state_ids": list(self.entry_state_ids),
            "main_path_event_ids": list(self.main_path_event_ids),
            "alternate_path_event_ids": list(self.alternate_path_event_ids),
            "cancel_event_ids": list(self.cancel_event_ids),
            "error_state_ids": list(self.error_state_ids),
            "success_state_ids": list(self.success_state_ids),
            "required_control_ids": list(self.required_control_ids),
            "required_display_ids": list(self.required_display_ids),
            "required_dialog_ids": list(self.required_dialog_ids),
            "required_feedback_item_ids": list(self.required_feedback_item_ids),
            "keyboard_contract_id": self.keyboard_contract_id,
            "cancel_behavior": self.cancel_behavior,
            "error_behavior": self.error_behavior,
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIUserTaskCoverageLedger:
    """Ledger mapping feature capability to user tasks, UI paths, and evidence."""

    ledger_id: str
    source_function_model_id: str = ""
    source_interaction_model_id: str = ""
    feature_ids: tuple[str, ...] = ()
    task_frames: tuple[UIUserTaskFrame, ...] = ()
    feature_task_links: tuple[tuple[str, str], ...] = ()
    task_journey_links: tuple[tuple[str, str], ...] = ()
    task_control_links: tuple[tuple[str, str], ...] = ()
    task_functional_chain_links: tuple[tuple[str, str], ...] = ()
    primary_control_ids: tuple[str, ...] = ()
    out_of_scope_feature_ids: tuple[str, ...] = ()
    out_of_scope_task_ids: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger_id", str(self.ledger_id))
        object.__setattr__(self, "source_function_model_id", str(self.source_function_model_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "feature_ids", _as_tuple(self.feature_ids))
        object.__setattr__(self, "task_frames", tuple(self.task_frames))
        object.__setattr__(self, "feature_task_links", _as_pairs(self.feature_task_links))
        object.__setattr__(self, "task_journey_links", _as_pairs(self.task_journey_links))
        object.__setattr__(self, "task_control_links", _as_pairs(self.task_control_links))
        object.__setattr__(self, "task_functional_chain_links", _as_pairs(self.task_functional_chain_links))
        object.__setattr__(self, "primary_control_ids", _as_tuple(self.primary_control_ids))
        object.__setattr__(self, "out_of_scope_feature_ids", _as_tuple(self.out_of_scope_feature_ids))
        object.__setattr__(self, "out_of_scope_task_ids", _as_tuple(self.out_of_scope_task_ids))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.task_frames)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "source_function_model_id": self.source_function_model_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "feature_ids": list(self.feature_ids),
            "task_frames": [task.to_dict() for task in self.task_frames],
            "feature_task_links": [list(pair) for pair in self.feature_task_links],
            "task_journey_links": [list(pair) for pair in self.task_journey_links],
            "task_control_links": [list(pair) for pair in self.task_control_links],
            "task_functional_chain_links": [list(pair) for pair in self.task_functional_chain_links],
            "primary_control_ids": list(self.primary_control_ids),
            "out_of_scope_feature_ids": list(self.out_of_scope_feature_ids),
            "out_of_scope_task_ids": list(self.out_of_scope_task_ids),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIRegionSemanticMap:
    """Semantic ownership for a UI region used by human task paths."""

    map_id: str
    region_id: str
    region_role: str
    task_ids: tuple[str, ...] = ()
    control_ids: tuple[str, ...] = ()
    display_ids: tuple[str, ...] = ()
    status_item_ids: tuple[str, ...] = ()
    allowed_item_kinds: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "map_id", str(self.map_id))
        object.__setattr__(self, "region_id", str(self.region_id))
        object.__setattr__(self, "region_role", str(self.region_role))
        object.__setattr__(self, "task_ids", _as_tuple(self.task_ids))
        object.__setattr__(self, "control_ids", _as_tuple(self.control_ids))
        object.__setattr__(self, "display_ids", _as_tuple(self.display_ids))
        object.__setattr__(self, "status_item_ids", _as_tuple(self.status_item_ids))
        object.__setattr__(self, "allowed_item_kinds", _as_tuple(self.allowed_item_kinds))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "region_id": self.region_id,
            "region_role": self.region_role,
            "task_ids": list(self.task_ids),
            "control_ids": list(self.control_ids),
            "display_ids": list(self.display_ids),
            "status_item_ids": list(self.status_item_ids),
            "allowed_item_kinds": list(self.allowed_item_kinds),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIAffordanceContract:
    """Perceived role versus actual UI role for one visible item."""

    contract_id: str
    visible_item_id: str
    perceived_role: str
    actual_role: str
    task_id: str = ""
    control_id: str = ""
    visual_cues: tuple[str, ...] = ()
    interaction_cues: tuple[str, ...] = ()
    expected_user_action: str = ""
    expected_result: str = ""
    mismatch_disposition: str = ""
    evidence_ref: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        object.__setattr__(self, "visible_item_id", str(self.visible_item_id))
        object.__setattr__(self, "perceived_role", str(self.perceived_role))
        object.__setattr__(self, "actual_role", str(self.actual_role))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "control_id", str(self.control_id))
        object.__setattr__(self, "visual_cues", _as_tuple(self.visual_cues))
        object.__setattr__(self, "interaction_cues", _as_tuple(self.interaction_cues))
        object.__setattr__(self, "expected_user_action", str(self.expected_user_action))
        object.__setattr__(self, "expected_result", str(self.expected_result))
        object.__setattr__(self, "mismatch_disposition", str(self.mismatch_disposition))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "visible_item_id": self.visible_item_id,
            "perceived_role": self.perceived_role,
            "actual_role": self.actual_role,
            "task_id": self.task_id,
            "control_id": self.control_id,
            "visual_cues": list(self.visual_cues),
            "interaction_cues": list(self.interaction_cues),
            "expected_user_action": self.expected_user_action,
            "expected_result": self.expected_result,
            "mismatch_disposition": self.mismatch_disposition,
            "evidence_ref": self.evidence_ref,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIActionGrammar:
    """One semantic user action and its primary/alternate controls."""

    action_id: str
    task_id: str
    user_intent: str
    source_state_ids: tuple[str, ...] = ()
    primary_control_id: str = ""
    alternate_control_ids: tuple[str, ...] = ()
    conflicting_control_ids: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    expected_next_state_id: str = ""
    expected_feedback_item_ids: tuple[str, ...] = ()
    duplicate_policy: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", str(self.action_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "user_intent", str(self.user_intent))
        object.__setattr__(self, "source_state_ids", _as_tuple(self.source_state_ids))
        object.__setattr__(self, "primary_control_id", str(self.primary_control_id))
        object.__setattr__(self, "alternate_control_ids", _as_tuple(self.alternate_control_ids))
        object.__setattr__(self, "conflicting_control_ids", _as_tuple(self.conflicting_control_ids))
        object.__setattr__(self, "preconditions", _as_tuple(self.preconditions))
        object.__setattr__(self, "expected_next_state_id", str(self.expected_next_state_id))
        object.__setattr__(self, "expected_feedback_item_ids", _as_tuple(self.expected_feedback_item_ids))
        object.__setattr__(self, "duplicate_policy", str(self.duplicate_policy))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "task_id": self.task_id,
            "user_intent": self.user_intent,
            "source_state_ids": list(self.source_state_ids),
            "primary_control_id": self.primary_control_id,
            "alternate_control_ids": list(self.alternate_control_ids),
            "conflicting_control_ids": list(self.conflicting_control_ids),
            "preconditions": list(self.preconditions),
            "expected_next_state_id": self.expected_next_state_id,
            "expected_feedback_item_ids": list(self.expected_feedback_item_ids),
            "duplicate_policy": self.duplicate_policy,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIDialogWindowContract:
    """Dialog, native picker, or OS window return semantics."""

    contract_id: str
    task_id: str
    trigger_control_id: str
    dialog_type: str
    modal: bool = True
    success_return: str = ""
    cancel_return: str = ""
    error_return: str = ""
    focus_return_target_id: str = ""
    feedback_item_ids: tuple[str, ...] = ()
    native_boundary: str = ""
    manual_boundary: str = ""
    evidence_ref: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "trigger_control_id", str(self.trigger_control_id))
        object.__setattr__(self, "dialog_type", str(self.dialog_type))
        object.__setattr__(self, "modal", bool(self.modal))
        object.__setattr__(self, "success_return", str(self.success_return))
        object.__setattr__(self, "cancel_return", str(self.cancel_return))
        object.__setattr__(self, "error_return", str(self.error_return))
        object.__setattr__(self, "focus_return_target_id", str(self.focus_return_target_id))
        object.__setattr__(self, "feedback_item_ids", _as_tuple(self.feedback_item_ids))
        object.__setattr__(self, "native_boundary", str(self.native_boundary))
        object.__setattr__(self, "manual_boundary", str(self.manual_boundary))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "task_id": self.task_id,
            "trigger_control_id": self.trigger_control_id,
            "dialog_type": self.dialog_type,
            "modal": self.modal,
            "success_return": self.success_return,
            "cancel_return": self.cancel_return,
            "error_return": self.error_return,
            "focus_return_target_id": self.focus_return_target_id,
            "feedback_item_ids": list(self.feedback_item_ids),
            "native_boundary": self.native_boundary,
            "manual_boundary": self.manual_boundary,
            "evidence_ref": self.evidence_ref,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIKeyboardFocusContract:
    """Keyboard and focus behavior for a task path."""

    contract_id: str
    task_id: str
    state_id: str = ""
    tab_order_control_ids: tuple[str, ...] = ()
    default_enter_control_id: str = ""
    escape_behavior: str = ""
    focus_return_rules: tuple[tuple[str, str], ...] = ()
    disabled_skip_policy: str = ""
    error_focus_target_id: str = ""
    evidence_ref: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "state_id", str(self.state_id))
        object.__setattr__(self, "tab_order_control_ids", _as_tuple(self.tab_order_control_ids))
        object.__setattr__(self, "default_enter_control_id", str(self.default_enter_control_id))
        object.__setattr__(self, "escape_behavior", str(self.escape_behavior))
        object.__setattr__(self, "focus_return_rules", _as_pairs(self.focus_return_rules))
        object.__setattr__(self, "disabled_skip_policy", str(self.disabled_skip_policy))
        object.__setattr__(self, "error_focus_target_id", str(self.error_focus_target_id))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "task_id": self.task_id,
            "state_id": self.state_id,
            "tab_order_control_ids": list(self.tab_order_control_ids),
            "default_enter_control_id": self.default_enter_control_id,
            "escape_behavior": self.escape_behavior,
            "focus_return_rules": [list(pair) for pair in self.focus_return_rules],
            "disabled_skip_policy": self.disabled_skip_policy,
            "error_focus_target_id": self.error_focus_target_id,
            "evidence_ref": self.evidence_ref,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIHumanWalkthroughStep:
    """One structured human walkthrough step."""

    step_id: str
    visible_prompt: str
    user_action: str
    expected_feedback: str
    actual_feedback: str
    evidence_ref: str
    confusion: bool = False
    mitigation: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "visible_prompt", str(self.visible_prompt))
        object.__setattr__(self, "user_action", str(self.user_action))
        object.__setattr__(self, "expected_feedback", str(self.expected_feedback))
        object.__setattr__(self, "actual_feedback", str(self.actual_feedback))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "confusion", bool(self.confusion))
        object.__setattr__(self, "mitigation", str(self.mitigation))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "visible_prompt": self.visible_prompt,
            "user_action": self.user_action,
            "expected_feedback": self.expected_feedback,
            "actual_feedback": self.actual_feedback,
            "evidence_ref": self.evidence_ref,
            "confusion": self.confusion,
            "mitigation": self.mitigation,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIHumanWalkthroughScenario:
    """Human walkthrough evidence for one task and persona."""

    scenario_id: str
    task_id: str
    persona: str = "first_time"
    steps: tuple[UIHumanWalkthroughStep, ...] = ()
    evidence_ref: str = ""
    result: str = "passed"
    confusion_notes: tuple[str, ...] = ()
    mitigation: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", str(self.scenario_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "persona", str(self.persona))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "confusion_notes", _as_tuple(self.confusion_notes))
        object.__setattr__(self, "mitigation", str(self.mitigation))
        object.__setattr__(self, "rationale", str(self.rationale))

    def step_ids(self) -> tuple[str, ...]:
        return tuple(step.step_id for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "task_id": self.task_id,
            "persona": self.persona,
            "steps": [step.to_dict() for step in self.steps],
            "evidence_ref": self.evidence_ref,
            "result": self.result,
            "confusion_notes": list(self.confusion_notes),
            "mitigation": self.mitigation,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIHumanOperabilityAssessment:
    """Aggregate human-operability evidence for a UI target revision."""

    assessment_id: str
    task_coverage: UIUserTaskCoverageLedger
    source_interaction_model_id: str = ""
    current_revision: str = ""
    region_maps: tuple[UIRegionSemanticMap, ...] = ()
    affordance_contracts: tuple[UIAffordanceContract, ...] = ()
    action_grammars: tuple[UIActionGrammar, ...] = ()
    dialog_contracts: tuple[UIDialogWindowContract, ...] = ()
    keyboard_contracts: tuple[UIKeyboardFocusContract, ...] = ()
    walkthroughs: tuple[UIHumanWalkthroughScenario, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", str(self.assessment_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "current_revision", str(self.current_revision))
        object.__setattr__(self, "region_maps", tuple(self.region_maps))
        object.__setattr__(self, "affordance_contracts", tuple(self.affordance_contracts))
        object.__setattr__(self, "action_grammars", tuple(self.action_grammars))
        object.__setattr__(self, "dialog_contracts", tuple(self.dialog_contracts))
        object.__setattr__(self, "keyboard_contracts", tuple(self.keyboard_contracts))
        object.__setattr__(self, "walkthroughs", tuple(self.walkthroughs))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "task_coverage": self.task_coverage.to_dict(),
            "source_interaction_model_id": self.source_interaction_model_id,
            "current_revision": self.current_revision,
            "region_maps": [item.to_dict() for item in self.region_maps],
            "affordance_contracts": [item.to_dict() for item in self.affordance_contracts],
            "action_grammars": [item.to_dict() for item in self.action_grammars],
            "dialog_contracts": [item.to_dict() for item in self.dialog_contracts],
            "keyboard_contracts": [item.to_dict() for item in self.keyboard_contracts],
            "walkthroughs": [item.to_dict() for item in self.walkthroughs],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


SUPPORTED_UI_EVIDENCE_KINDS = (
    "screenshot",
    "browser_click",
    "desktop_click",
    "dom_text",
    "computed_style",
    "geometry",
    "accessibility",
    "aria",
    "runtime_trace",
    "log",
    "test_result",
    "manual_observation",
)


@dataclass(frozen=True)
class UIRenderEvidence:
    """One render or implementation evidence record for a visible UI target."""

    evidence_id: str
    evidence_kind: str
    evidence_target: str
    source_interaction_model_id: str = ""
    implementation_target: str = ""
    result: str = "passed"
    evidence_ref: str = ""
    model_revision: str = ""
    observed_state_id: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_kind", str(self.evidence_kind))
        object.__setattr__(self, "evidence_target", str(self.evidence_target))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "implementation_target", str(self.implementation_target))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "model_revision", str(self.model_revision))
        object.__setattr__(self, "observed_state_id", str(self.observed_state_id))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_kind": self.evidence_kind,
            "evidence_target": self.evidence_target,
            "source_interaction_model_id": self.source_interaction_model_id,
            "implementation_target": self.implementation_target,
            "result": self.result,
            "evidence_ref": self.evidence_ref,
            "model_revision": self.model_revision,
            "observed_state_id": self.observed_state_id,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIRenderEvidenceSet:
    """Render evidence boundary for implemented/runnable UI claims."""

    evidence_set_id: str
    source_interaction_model_id: str = ""
    implementation_target: str = ""
    current_model_revision: str = ""
    evidence: tuple[UIRenderEvidence, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_set_id", str(self.evidence_set_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "implementation_target", str(self.implementation_target))
        object.__setattr__(self, "current_model_revision", str(self.current_model_revision))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_set_id": self.evidence_set_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "implementation_target": self.implementation_target,
            "current_model_revision": self.current_model_revision,
            "evidence": [item.to_dict() for item in self.evidence],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIGeometryLayoutEvidence:
    """One universal geometry/layout evidence row for a UI item or surface."""

    evidence_id: str
    target_id: str
    viewport: str = ""
    text_overflow: bool = False
    control_overlap: bool = False
    out_of_bounds: bool = False
    focus_reachable: bool = True
    keyboard_reachable: bool = True
    scroll_owner: str = ""
    result: str = "passed"
    evidence_ref: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "target_id", str(self.target_id))
        object.__setattr__(self, "viewport", str(self.viewport))
        object.__setattr__(self, "text_overflow", bool(self.text_overflow))
        object.__setattr__(self, "control_overlap", bool(self.control_overlap))
        object.__setattr__(self, "out_of_bounds", bool(self.out_of_bounds))
        object.__setattr__(self, "focus_reachable", bool(self.focus_reachable))
        object.__setattr__(self, "keyboard_reachable", bool(self.keyboard_reachable))
        object.__setattr__(self, "scroll_owner", str(self.scroll_owner))
        object.__setattr__(self, "result", str(self.result))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "target_id": self.target_id,
            "viewport": self.viewport,
            "text_overflow": self.text_overflow,
            "control_overlap": self.control_overlap,
            "out_of_bounds": self.out_of_bounds,
            "focus_reachable": self.focus_reachable,
            "keyboard_reachable": self.keyboard_reachable,
            "scroll_owner": self.scroll_owner,
            "result": self.result,
            "evidence_ref": self.evidence_ref,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIGeometryLayoutEvidenceSet:
    """Geometry/layout evidence boundary for universal UI layout risks."""

    geometry_id: str
    source_interaction_model_id: str = ""
    entries: tuple[UIGeometryLayoutEvidence, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "geometry_id", str(self.geometry_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def entry_ids(self) -> tuple[str, ...]:
        return tuple(entry.evidence_id for entry in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry_id": self.geometry_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "entries": [entry.to_dict() for entry in self.entries],
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIHotPathAction:
    """Immediate UI feedback expected after a direct user interaction."""

    action_id: str
    event_id: str = ""
    feedback_target_id: str = ""
    feedback_description: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", str(self.action_id))
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "feedback_target_id", str(self.feedback_target_id))
        object.__setattr__(self, "feedback_description", str(self.feedback_description))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "event_id": self.event_id,
            "feedback_target_id": self.feedback_target_id,
            "feedback_description": self.feedback_description,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIColdPathWork:
    """Deferred UI work that must not stale-overwrite newer state."""

    work_id: str
    trigger_event_id: str = ""
    result_target_id: str = ""
    stale_guard: str = ""
    cancellation_rule: str = ""
    coalescing_rule: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "work_id", str(self.work_id))
        object.__setattr__(self, "trigger_event_id", str(self.trigger_event_id))
        object.__setattr__(self, "result_target_id", str(self.result_target_id))
        object.__setattr__(self, "stale_guard", str(self.stale_guard))
        object.__setattr__(self, "cancellation_rule", str(self.cancellation_rule))
        object.__setattr__(self, "coalescing_rule", str(self.coalescing_rule))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_stale_protection(self) -> bool:
        return bool(self.stale_guard or self.cancellation_rule or self.coalescing_rule)

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "trigger_event_id": self.trigger_event_id,
            "result_target_id": self.result_target_id,
            "stale_guard": self.stale_guard,
            "cancellation_rule": self.cancellation_rule,
            "coalescing_rule": self.coalescing_rule,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIStableRegionRule:
    """A UI region that should remain stable across unrelated input changes."""

    region_id: str
    preservation_rule: str = ""
    unrelated_input_ids: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "region_id", str(self.region_id))
        object.__setattr__(self, "preservation_rule", str(self.preservation_rule))
        object.__setattr__(self, "unrelated_input_ids", _as_tuple(self.unrelated_input_ids))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "preservation_rule": self.preservation_rule,
            "unrelated_input_ids": list(self.unrelated_input_ids),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIResponsivenessContract:
    """Hot/cold path contract for UI responsiveness-sensitive interactions."""

    contract_id: str
    source_interaction_model_id: str = ""
    hot_path_actions: tuple[UIHotPathAction, ...] = ()
    cold_path_work: tuple[UIColdPathWork, ...] = ()
    stable_region_rules: tuple[UIStableRegionRule, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        object.__setattr__(self, "source_interaction_model_id", str(self.source_interaction_model_id))
        object.__setattr__(self, "hot_path_actions", tuple(self.hot_path_actions))
        object.__setattr__(self, "cold_path_work", tuple(self.cold_path_work))
        object.__setattr__(self, "stable_region_rules", tuple(self.stable_region_rules))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "source_interaction_model_id": self.source_interaction_model_id,
            "hot_path_actions": [action.to_dict() for action in self.hot_path_actions],
            "cold_path_work": [work.to_dict() for work in self.cold_path_work],
            "stable_region_rules": [rule.to_dict() for rule in self.stable_region_rules],
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


@dataclass(frozen=True)
class UIVisibleSurfaceReport:
    """Structured review result for a visible UI surface inventory."""

    ok: bool
    surface_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_visible_surface={self.surface_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI visible surface review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"surface: {self.surface_id}",
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
            "surface_id": self.surface_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIObservedSurfaceInventoryReport:
    """Structured review result for observed real UI inventory coverage."""

    ok: bool
    inventory_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    observed_item_ids: tuple[str, ...] = ()
    mapped_item_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "inventory_id", str(self.inventory_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "observed_item_ids", _as_tuple(self.observed_item_ids))
        object.__setattr__(self, "mapped_item_ids", _as_tuple(self.mapped_item_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_observed_surface_inventory={self.inventory_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI observed surface inventory review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"inventory: {self.inventory_id}",
            f"observed_items: {len(self.observed_item_ids)}",
            f"mapped_items: {len(self.mapped_item_ids)}",
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
            "inventory_id": self.inventory_id,
            "observed_item_ids": list(self.observed_item_ids),
            "mapped_item_ids": list(self.mapped_item_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIControlFunctionalChainReport:
    """Structured review result for enabled-control click-to-effect chains."""

    ok: bool
    chain_set_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    covered_control_ids: tuple[str, ...] = ()
    covered_event_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_set_id", str(self.chain_set_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_control_ids", _as_tuple(self.covered_control_ids))
        object.__setattr__(self, "covered_event_ids", _as_tuple(self.covered_event_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_control_functional_chains={self.chain_set_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI control functional chain review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"chain_set: {self.chain_set_id}",
            f"covered_controls: {len(self.covered_control_ids)}",
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
            "chain_set_id": self.chain_set_id,
            "covered_control_ids": list(self.covered_control_ids),
            "covered_event_ids": list(self.covered_event_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class MATLABBaselineCallbackGateReport:
    """Structured review result for MATLAB baseline callback semantics."""

    ok: bool
    gate_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    covered_callback_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", str(self.gate_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_callback_ids", _as_tuple(self.covered_callback_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: matlab_baseline_callback_gate={self.gate_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard MATLAB baseline callback semantics review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"gate: {self.gate_id}",
            f"covered_callbacks: {len(self.covered_callback_ids)}",
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
            "gate_id": self.gate_id,
            "covered_callback_ids": list(self.covered_callback_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIHumanOperabilityReport:
    """Structured review result for human-operable UI task coverage."""

    ok: bool
    assessment_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    covered_task_ids: tuple[str, ...] = ()
    covered_feature_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", str(self.assessment_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_task_ids", _as_tuple(self.covered_task_ids))
        object.__setattr__(self, "covered_feature_ids", _as_tuple(self.covered_feature_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_human_operability={self.assessment_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI human-operability review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"assessment: {self.assessment_id}",
            f"covered_tasks: {len(self.covered_task_ids)}",
            f"covered_features: {len(self.covered_feature_ids)}",
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
            "assessment_id": self.assessment_id,
            "covered_task_ids": list(self.covered_task_ids),
            "covered_feature_ids": list(self.covered_feature_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIRenderEvidenceReport:
    """Structured review result for UI render evidence kinds."""

    ok: bool
    evidence_set_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    evidence_kinds: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_set_id", str(self.evidence_set_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "evidence_kinds", _as_tuple(self.evidence_kinds))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_render_evidence={self.evidence_set_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI render evidence review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"evidence_set: {self.evidence_set_id}",
            f"evidence_kinds: {', '.join(self.evidence_kinds) if self.evidence_kinds else '(none)'}",
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
            "evidence_set_id": self.evidence_set_id,
            "evidence_kinds": list(self.evidence_kinds),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIGeometryLayoutEvidenceReport:
    """Structured review result for universal UI geometry/layout evidence."""

    ok: bool
    geometry_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    checked_targets: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "geometry_id", str(self.geometry_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "checked_targets", _as_tuple(self.checked_targets))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_geometry_layout={self.geometry_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI geometry layout evidence review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"geometry: {self.geometry_id}",
            f"checked_targets: {len(self.checked_targets)}",
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
            "geometry_id": self.geometry_id,
            "checked_targets": list(self.checked_targets),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class UIResponsivenessContractReport:
    """Structured review result for UI hot/cold path responsiveness."""

    ok: bool
    contract_id: str
    findings: tuple[UIFlowStructureFinding, ...] = ()
    hot_path_ids: tuple[str, ...] = ()
    cold_path_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "hot_path_ids", _as_tuple(self.hot_path_ids))
        object.__setattr__(self, "cold_path_ids", _as_tuple(self.cold_path_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_responsiveness={self.contract_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard UI responsiveness contract review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"contract: {self.contract_id}",
            f"hot_paths: {len(self.hot_path_ids)}",
            f"cold_paths: {len(self.cold_path_ids)}",
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
            "contract_id": self.contract_id,
            "hot_path_ids": list(self.hot_path_ids),
            "cold_path_ids": list(self.cold_path_ids),
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
_INTERNAL_VISIBLE_TERMS = (
    "mock",
    "backend",
    "hydration",
    "debug route",
    "dataset id",
    "render strategy",
    "api route",
)
_STATE_MESSAGE_ITEM_KINDS = {"empty", "loading", "pending", "error", "success", "status"}
_VISIBLE_HELPER_KINDS = {"helper", "helper_copy", "help_text"}
_PASSED_UI_RESULTS = {"passed", "pass", "ok"}


def _norm_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _text_contains_internal_term(value: str) -> str:
    normalized = _norm_text(value)
    for term in _INTERNAL_VISIBLE_TERMS:
        if term in normalized:
            return term
    return ""


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


def review_ui_visible_surface(
    surface: UIVisibleSurface,
    *,
    interaction_model: UIInteractionModel | None = None,
) -> UIVisibleSurfaceReport:
    """Review user-facing visible UI surface inventory."""

    findings: list[UIFlowStructureFinding] = []
    known_states = set(interaction_model.state_ids()) if interaction_model is not None else set()
    known_controls = set(interaction_model.control_ids()) if interaction_model is not None else set()
    known_displays = set(interaction_model.display_ids()) if interaction_model is not None else set()
    controls_by_id = interaction_model.controls_by_id() if interaction_model is not None else {}

    if not surface.surface_id:
        findings.append(UIFlowStructureFinding("missing_visible_surface_id", "UI visible surface has no id"))
    if interaction_model is not None:
        if not surface.source_interaction_model_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_visible_surface_source_model",
                    "UI visible surface has no source interaction model id",
                )
            )
        elif surface.source_interaction_model_id != interaction_model.model_id:
            findings.append(
                UIFlowStructureFinding(
                    "visible_surface_model_mismatch",
                    "UI visible surface does not reference the supplied interaction model",
                    metadata={
                        "surface_source": surface.source_interaction_model_id,
                        "interaction_model": interaction_model.model_id,
                    },
                )
            )
    if not surface.items:
        findings.append(UIFlowStructureFinding("missing_visible_surface_items", "UI visible surface has no items"))
    if not surface.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_visible_surface_validation", "UI visible surface has no validation boundaries")
        )
    if not surface.rationale:
        findings.append(UIFlowStructureFinding("missing_visible_surface_rationale", "UI visible surface has no rationale"))

    findings.extend(_duplicate_values(surface.item_ids(), code="duplicate_visible_surface_item_id", noun="visible surface item"))

    primary_state_messages: dict[str, list[UIVisibleSurfaceItem]] = {}
    for item in surface.items:
        if not item.item_id:
            findings.append(UIFlowStructureFinding("missing_visible_surface_item_id", "visible surface item has no id"))
        if not item.item_kind:
            findings.append(
                UIFlowStructureFinding(
                    "missing_visible_surface_item_kind",
                    f"visible surface item {item.item_id} has no kind",
                    item_id=item.item_id,
                )
            )
        if not item.text and item.item_kind not in {"control", "region", "surface"}:
            findings.append(
                UIFlowStructureFinding(
                    "missing_visible_surface_text",
                    f"visible surface item {item.item_id} has no visible text",
                    item_id=item.item_id,
                )
            )
        if not (item.state_ids or item.region_id or item.owner_control_id or item.owner_display_id):
            findings.append(
                UIFlowStructureFinding(
                    "missing_visible_surface_owner",
                    f"visible surface item {item.item_id} has no state, region, control, or display owner",
                    item_id=item.item_id,
                )
            )
        if not item.purpose:
            findings.append(
                UIFlowStructureFinding(
                    "missing_visible_surface_purpose",
                    f"visible surface item {item.item_id} has no user-facing purpose",
                    item_id=item.item_id,
                )
            )
        if not item.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_visible_surface_item_rationale",
                    f"visible surface item {item.item_id} has no rationale",
                    item_id=item.item_id,
                )
            )
        for state_id in item.state_ids:
            if interaction_model is not None and state_id not in known_states:
                findings.append(
                    UIFlowStructureFinding(
                        "visible_surface_state_not_registered",
                        f"visible surface item {item.item_id} references unknown state {state_id}",
                        item_id=item.item_id,
                    )
                )
        if interaction_model is not None and item.owner_control_id and item.owner_control_id not in known_controls:
            findings.append(
                UIFlowStructureFinding(
                    "visible_surface_control_not_registered",
                    f"visible surface item {item.item_id} references unknown control {item.owner_control_id}",
                    item_id=item.item_id,
                )
            )
        if interaction_model is not None and item.owner_display_id and item.owner_display_id not in known_displays:
            findings.append(
                UIFlowStructureFinding(
                    "visible_surface_display_not_registered",
                    f"visible surface item {item.item_id} references unknown display {item.owner_display_id}",
                    item_id=item.item_id,
                )
            )
        internal_term = _text_contains_internal_term(item.text)
        if internal_term and not item.internal_term_rationale:
            findings.append(
                UIFlowStructureFinding(
                    "visible_internal_terminology",
                    f"visible surface item {item.item_id} exposes internal term '{internal_term}' without a user-facing rationale",
                    item_id=item.item_id,
                    metadata={"term": internal_term},
                )
            )
        if item.item_kind == "disabled_control" and not item.disabled_reason:
            findings.append(
                UIFlowStructureFinding(
                    "missing_disabled_reason",
                    f"disabled visible control {item.item_id} has no user-understandable reason",
                    item_id=item.item_id,
                )
            )
        if (item.placeholder or item.item_kind == "placeholder") and item.presents_as_functionality:
            findings.append(
                UIFlowStructureFinding(
                    "placeholder_presented_as_functionality",
                    f"placeholder item {item.item_id} is presented as completed product functionality",
                    item_id=item.item_id,
                )
            )
        if item.item_kind in _VISIBLE_HELPER_KINDS and item.owner_control_id:
            control = controls_by_id.get(item.owner_control_id)
            if control is not None and _norm_text(item.text) == _norm_text(control.label) and not item.redundancy_rationale:
                findings.append(
                    UIFlowStructureFinding(
                        "low_value_repeated_helper_copy",
                        f"helper copy {item.item_id} repeats control label {item.owner_control_id} without added user value",
                        item_id=item.item_id,
                    )
                )
        if item.item_kind in _STATE_MESSAGE_ITEM_KINDS and item.priority == "primary":
            for state_id in item.state_ids or ("*",):
                primary_state_messages.setdefault(state_id, []).append(item)

    for state_id, items in sorted(primary_state_messages.items()):
        if len(items) > 1 and not _redundancy_justified(items):
            findings.append(
                UIFlowStructureFinding(
                    "competing_primary_state_messages",
                    f"state {state_id} has multiple primary state messages without a dominance or redundancy rationale",
                    item_id=state_id,
                    metadata={"item_ids": [item.item_id for item in items]},
                )
            )

    blockers = _blocker_findings(findings)
    return UIVisibleSurfaceReport(ok=not blockers, surface_id=surface.surface_id, findings=tuple(findings))


def review_ui_observed_surface_inventory(
    inventory: UIObservedSurfaceInventory,
    *,
    interaction_model: UIInteractionModel | None = None,
    visible_surface: UIVisibleSurface | None = None,
) -> UIObservedSurfaceInventoryReport:
    """Review real rendered UI inventory before a UI model is called complete."""

    findings: list[UIFlowStructureFinding] = []
    known_controls = set(interaction_model.control_ids()) if interaction_model is not None else set()
    known_displays = set(interaction_model.display_ids()) if interaction_model is not None else set()
    known_states = set(interaction_model.state_ids()) if interaction_model is not None else set()
    visible_item_ids = set(visible_surface.item_ids()) if visible_surface is not None else set()
    blindspot_ids = set(inventory.blindspot_ids())

    if not inventory.inventory_id:
        findings.append(UIFlowStructureFinding("missing_observed_inventory_id", "observed UI inventory has no id"))
    if not inventory.observation_target:
        findings.append(UIFlowStructureFinding("missing_observation_target", "observed UI inventory has no target"))
    if not inventory.current_revision:
        findings.append(UIFlowStructureFinding("missing_observation_revision", "observed UI inventory has no current revision"))
    if not inventory.observation_method:
        findings.append(UIFlowStructureFinding("missing_observation_method", "observed UI inventory has no observation method"))
    if not inventory.evidence_ref:
        findings.append(UIFlowStructureFinding("missing_observation_evidence_ref", "observed UI inventory has no evidence reference"))
    if not inventory.items:
        findings.append(UIFlowStructureFinding("missing_observed_items", "observed UI inventory has no real visible items"))
    if not inventory.validation_boundaries:
        findings.append(UIFlowStructureFinding("missing_observed_inventory_validation", "observed UI inventory has no validation boundaries"))
    if not inventory.rationale:
        findings.append(UIFlowStructureFinding("missing_observed_inventory_rationale", "observed UI inventory has no rationale"))
    if interaction_model is not None:
        if not inventory.source_interaction_model_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_inventory_source_model",
                    "observed UI inventory has no source interaction model id",
                )
            )
        elif inventory.source_interaction_model_id != interaction_model.model_id:
            findings.append(
                UIFlowStructureFinding(
                    "observed_inventory_model_mismatch",
                    "observed UI inventory does not reference the supplied interaction model",
                    metadata={
                        "inventory_source": inventory.source_interaction_model_id,
                        "interaction_model": interaction_model.model_id,
                    },
                )
            )
    if visible_surface is not None:
        if not inventory.source_visible_surface_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_inventory_visible_surface",
                    "observed UI inventory has no source visible surface id",
                )
            )
        elif inventory.source_visible_surface_id != visible_surface.surface_id:
            findings.append(
                UIFlowStructureFinding(
                    "observed_inventory_visible_surface_mismatch",
                    "observed UI inventory does not reference the supplied visible surface",
                    metadata={
                        "inventory_source": inventory.source_visible_surface_id,
                        "visible_surface": visible_surface.surface_id,
                    },
                )
            )

    findings.extend(_duplicate_values(inventory.item_ids(), code="duplicate_observed_item_id", noun="observed UI item"))
    findings.extend(_duplicate_values(inventory.blindspot_ids(), code="duplicate_observed_blindspot_id", noun="observed UI blindspot"))

    for blindspot in inventory.scoped_blindspots:
        if not blindspot.blindspot_id:
            findings.append(UIFlowStructureFinding("missing_observed_blindspot_id", "observed UI blindspot has no id"))
        if not blindspot.reason:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_blindspot_reason",
                    f"observed UI blindspot {blindspot.blindspot_id} has no reason",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.owner:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_blindspot_owner",
                    f"observed UI blindspot {blindspot.blindspot_id} has no owner",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.validation_boundaries:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_blindspot_validation",
                    f"observed UI blindspot {blindspot.blindspot_id} has no validation boundary",
                    item_id=blindspot.blindspot_id,
                )
            )
        if not blindspot.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_blindspot_rationale",
                    f"observed UI blindspot {blindspot.blindspot_id} has no rationale",
                    item_id=blindspot.blindspot_id,
                )
            )

    observed_item_ids: list[str] = []
    mapped_item_ids: list[str] = []
    supported_kinds = set(SUPPORTED_UI_EVIDENCE_KINDS)
    for item in inventory.items:
        if item.visible:
            observed_item_ids.append(item.item_id)
        if item.owner_ids():
            mapped_item_ids.append(item.item_id)
        if not item.item_id:
            findings.append(UIFlowStructureFinding("missing_observed_item_id", "observed UI item has no id"))
        if not item.item_kind:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_item_kind",
                    f"observed UI item {item.item_id} has no kind",
                    item_id=item.item_id,
                )
            )
        elif item.item_kind not in OBSERVED_UI_ITEM_KINDS:
            findings.append(
                UIFlowStructureFinding(
                    "unknown_observed_item_kind",
                    f"observed UI item {item.item_id} uses unknown kind {item.item_kind}",
                    item_id=item.item_id,
                    metadata={"supported_kinds": list(OBSERVED_UI_ITEM_KINDS)},
                )
            )
        if item.visible and not (item.label or item.observed_value or item.table_columns):
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_item_label",
                    f"observed UI item {item.item_id} has no visible label, value, or columns",
                    item_id=item.item_id,
                )
            )
        if item.state_id and interaction_model is not None and item.state_id not in known_states:
            findings.append(
                UIFlowStructureFinding(
                    "observed_item_state_not_registered",
                    f"observed UI item {item.item_id} references unknown state {item.state_id}",
                    item_id=item.item_id,
                )
            )
        if item.mapped_control_id and interaction_model is not None and item.mapped_control_id not in known_controls:
            findings.append(
                UIFlowStructureFinding(
                    "observed_item_control_not_registered",
                    f"observed UI item {item.item_id} maps to unknown control {item.mapped_control_id}",
                    item_id=item.item_id,
                )
            )
        if item.mapped_display_id and interaction_model is not None and item.mapped_display_id not in known_displays:
            findings.append(
                UIFlowStructureFinding(
                    "observed_item_display_not_registered",
                    f"observed UI item {item.item_id} maps to unknown display {item.mapped_display_id}",
                    item_id=item.item_id,
                )
            )
        if item.mapped_visible_item_id and visible_surface is not None and item.mapped_visible_item_id not in visible_item_ids:
            findings.append(
                UIFlowStructureFinding(
                    "observed_item_visible_surface_not_registered",
                    f"observed UI item {item.item_id} maps to unknown visible surface item {item.mapped_visible_item_id}",
                    item_id=item.item_id,
                )
            )
        if item.blindspot_id and item.blindspot_id not in blindspot_ids:
            findings.append(
                UIFlowStructureFinding(
                    "observed_item_blindspot_not_registered",
                    f"observed UI item {item.item_id} maps to unknown blindspot {item.blindspot_id}",
                    item_id=item.item_id,
                )
            )
        if item.visible and not item.owner_ids():
            findings.append(
                UIFlowStructureFinding(
                    "observed_visible_item_unmapped",
                    f"observed visible item {item.item_id} is not mapped to a UIControl, UIDisplayElement, UIVisibleSurfaceItem, or blindspot",
                    item_id=item.item_id,
                    metadata={"item_kind": item.item_kind},
                )
            )
        if item.enabled and item.item_kind in OBSERVED_UI_ACTIONABLE_KINDS and not (item.mapped_control_id or item.blindspot_id):
            findings.append(
                UIFlowStructureFinding(
                    "observed_enabled_control_without_model_owner",
                    f"observed enabled control {item.item_id} has no mapped UIControl or scoped blindspot",
                    item_id=item.item_id,
                    metadata={"item_kind": item.item_kind},
                )
            )
        if not item.evidence_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_item_evidence_ref",
                    f"observed UI item {item.item_id} has no evidence reference",
                    item_id=item.item_id,
                )
            )
        if item.evidence_kind and item.evidence_kind not in supported_kinds:
            findings.append(
                UIFlowStructureFinding(
                    "unknown_observed_item_evidence_kind",
                    f"observed UI item {item.item_id} uses unknown evidence kind {item.evidence_kind}",
                    item_id=item.item_id,
                )
            )
        if not item.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_observed_item_rationale",
                    f"observed UI item {item.item_id} has no rationale",
                    item_id=item.item_id,
                )
            )

    blockers = _blocker_findings(findings)
    return UIObservedSurfaceInventoryReport(
        ok=not blockers,
        inventory_id=inventory.inventory_id,
        findings=tuple(findings),
        observed_item_ids=tuple(observed_item_ids),
        mapped_item_ids=tuple(mapped_item_ids),
    )


def review_ui_control_functional_chains(
    chain_set: UIControlFunctionalChainSet,
    *,
    observed_inventory: UIObservedSurfaceInventory,
    interaction_model: UIInteractionModel | None = None,
) -> UIControlFunctionalChainReport:
    """Review enabled-control proof from real click to code owner and UI result."""

    findings: list[UIFlowStructureFinding] = []
    known_controls = set(interaction_model.control_ids()) if interaction_model is not None else set()
    known_events = set(interaction_model.transition_event_ids()) if interaction_model is not None else set()
    known_states = set(interaction_model.state_ids()) if interaction_model is not None else set()
    known_displays = set(interaction_model.display_ids()) if interaction_model is not None else set()
    transitions_by_event = _transitions_by_event(interaction_model) if interaction_model is not None else {}
    observed_enabled_controls = {
        item.mapped_control_id: item
        for item in observed_inventory.items
        if item.visible and item.enabled and item.item_kind in OBSERVED_UI_ACTIONABLE_KINDS and item.mapped_control_id
    }
    observed_blindspot_controls = {
        item.mapped_control_id
        for item in observed_inventory.items
        if item.visible and item.enabled and item.item_kind in OBSERVED_UI_ACTIONABLE_KINDS and item.blindspot_id
    }
    chain_by_control = {chain.control_id: chain for chain in chain_set.chains if chain.control_id}
    covered_control_ids: list[str] = []
    covered_event_ids: list[str] = []

    if not chain_set.chain_set_id:
        findings.append(UIFlowStructureFinding("missing_functional_chain_set_id", "functional chain set has no id"))
    if not chain_set.source_inventory_id:
        findings.append(UIFlowStructureFinding("missing_functional_chain_inventory", "functional chain set has no source inventory id"))
    elif chain_set.source_inventory_id != observed_inventory.inventory_id:
        findings.append(
            UIFlowStructureFinding(
                "functional_chain_inventory_mismatch",
                "functional chain set does not reference the supplied observed inventory",
                metadata={"chain_inventory": chain_set.source_inventory_id, "inventory": observed_inventory.inventory_id},
            )
        )
    if interaction_model is not None:
        if not chain_set.source_interaction_model_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_source_model",
                    "functional chain set has no source interaction model id",
                )
            )
        elif chain_set.source_interaction_model_id != interaction_model.model_id:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_model_mismatch",
                    "functional chain set does not reference the supplied interaction model",
                )
            )
    if not chain_set.current_revision:
        findings.append(UIFlowStructureFinding("missing_functional_chain_revision", "functional chain set has no current revision"))
    if not chain_set.chains:
        findings.append(UIFlowStructureFinding("missing_functional_chains", "functional chain set has no chains"))
    if not chain_set.validation_boundaries:
        findings.append(UIFlowStructureFinding("missing_functional_chain_validation", "functional chain set has no validation boundaries"))
    if not chain_set.rationale:
        findings.append(UIFlowStructureFinding("missing_functional_chain_set_rationale", "functional chain set has no rationale"))

    findings.extend(_duplicate_values(chain_set.chain_ids(), code="duplicate_functional_chain_id", noun="functional chain"))

    for control_id, item in sorted(observed_enabled_controls.items()):
        if control_id in observed_blindspot_controls:
            continue
        if control_id not in chain_by_control:
            findings.append(
                UIFlowStructureFinding(
                    "enabled_control_missing_functional_chain",
                    f"observed enabled control {control_id} from item {item.item_id} has no click-to-effect functional chain",
                    item_id=control_id,
                    metadata={"observed_item_id": item.item_id},
                )
            )

    for chain in chain_set.chains:
        if chain.control_id:
            covered_control_ids.append(chain.control_id)
        if chain.event_id:
            covered_event_ids.append(chain.event_id)
        if not chain.chain_id:
            findings.append(UIFlowStructureFinding("missing_functional_chain_id", "functional chain has no id"))
        if not chain.control_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_control",
                    f"functional chain {chain.chain_id} has no control id",
                    item_id=chain.chain_id,
                )
            )
        elif interaction_model is not None and chain.control_id not in known_controls:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_control_not_registered",
                    f"functional chain {chain.chain_id} references unknown control {chain.control_id}",
                    item_id=chain.chain_id,
                )
            )
        if not chain.event_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_event",
                    f"functional chain {chain.chain_id} has no event id",
                    item_id=chain.chain_id,
                )
            )
        elif interaction_model is not None and chain.event_id not in known_events:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_event_not_registered",
                    f"functional chain {chain.chain_id} references unknown event {chain.event_id}",
                    item_id=chain.chain_id,
                )
            )
        event = transitions_by_event.get(chain.event_id)
        if event is not None and chain.control_id and chain.control_id != event.control_id:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_event_control_mismatch",
                    f"functional chain {chain.chain_id} control {chain.control_id} does not own event {chain.event_id}",
                    item_id=chain.chain_id,
                )
            )
        if not chain.code_owner:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_code_owner",
                    f"functional chain {chain.chain_id} has no code owner",
                    item_id=chain.chain_id,
                )
            )
        if not chain.function_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_function_ref",
                    f"functional chain {chain.chain_id} has no backend, local, native, or handler function reference",
                    item_id=chain.chain_id,
                )
            )
        if not chain.has_observed_ui_effect():
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_missing_ui_state_update",
                    f"functional chain {chain.chain_id} has no observed UI state, display, or output update",
                    item_id=chain.chain_id,
                )
            )
            if chain.function_kind in {"api", "backend", "local"} and chain.function_ref:
                findings.append(
                    UIFlowStructureFinding(
                        "functional_chain_api_only",
                        f"functional chain {chain.chain_id} cites a function/API but no observed UI effect",
                        item_id=chain.chain_id,
                    )
                )
        if chain.evidence_kind in {"dom_text", "accessibility", "aria", "computed_style"}:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_label_only_evidence",
                    f"functional chain {chain.chain_id} uses render/label evidence rather than click-to-effect evidence",
                    item_id=chain.chain_id,
                )
            )
        elif chain.evidence_kind and chain.evidence_kind not in FUNCTIONAL_CHAIN_EVIDENCE_KINDS:
            findings.append(
                UIFlowStructureFinding(
                    "unknown_functional_chain_evidence_kind",
                    f"functional chain {chain.chain_id} uses unsupported evidence kind {chain.evidence_kind}",
                    item_id=chain.chain_id,
                )
            )
        if not chain.evidence_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_evidence_ref",
                    f"functional chain {chain.chain_id} has no evidence reference",
                    item_id=chain.chain_id,
                )
            )
        if chain.result.lower() not in _PASSED_UI_RESULTS:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_not_passed",
                    f"functional chain {chain.chain_id} result is {chain.result}, not passed",
                    item_id=chain.chain_id,
                )
            )
        if not chain.current_revision:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_current_revision",
                    f"functional chain {chain.chain_id} has no current revision",
                    item_id=chain.chain_id,
                )
            )
        elif chain_set.current_revision and chain.current_revision != chain_set.current_revision:
            findings.append(
                UIFlowStructureFinding(
                    "stale_functional_chain_evidence",
                    f"functional chain {chain.chain_id} validates {chain.current_revision}, not current {chain_set.current_revision}",
                    item_id=chain.chain_id,
                )
            )
        if chain.observed_state_id and interaction_model is not None and chain.observed_state_id not in known_states:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_observed_state_not_registered",
                    f"functional chain {chain.chain_id} observed unknown state {chain.observed_state_id}",
                    item_id=chain.chain_id,
                )
            )
        if chain.observed_display_id and interaction_model is not None and chain.observed_display_id not in known_displays:
            findings.append(
                UIFlowStructureFinding(
                    "functional_chain_observed_display_not_registered",
                    f"functional chain {chain.chain_id} observed unknown display {chain.observed_display_id}",
                    item_id=chain.chain_id,
                )
            )
        if chain.function_kind == "native" and not (chain.native_boundary or chain.manual_boundary):
            findings.append(
                UIFlowStructureFinding(
                    "native_functional_chain_missing_boundary",
                    f"native functional chain {chain.chain_id} has no native/manual boundary",
                    item_id=chain.chain_id,
                )
            )
        if not chain.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_functional_chain_rationale",
                    f"functional chain {chain.chain_id} has no rationale",
                    item_id=chain.chain_id,
                )
            )

    blockers = _blocker_findings(findings)
    return UIControlFunctionalChainReport(
        ok=not blockers,
        chain_set_id=chain_set.chain_set_id,
        findings=tuple(findings),
        covered_control_ids=tuple(sorted(set(covered_control_ids))),
        covered_event_ids=tuple(sorted(set(covered_event_ids))),
    )


def review_matlab_baseline_callback_gate(
    gate: MATLABBaselineCallbackGate,
    *,
    interaction_model: UIInteractionModel | None = None,
) -> MATLABBaselineCallbackGateReport:
    """Review MATLAB callback semantics for migration parity claims."""

    findings: list[UIFlowStructureFinding] = []
    known_controls = set(interaction_model.control_ids()) if interaction_model is not None else set()
    covered_callback_ids: list[str] = []

    if not gate.gate_id:
        findings.append(UIFlowStructureFinding("missing_matlab_callback_gate_id", "MATLAB callback gate has no id"))
    if not gate.source_baseline_ref:
        findings.append(UIFlowStructureFinding("missing_matlab_baseline_ref", "MATLAB callback gate has no source baseline reference"))
    if not gate.target_ui_revision:
        findings.append(UIFlowStructureFinding("missing_matlab_target_revision", "MATLAB callback gate has no target UI revision"))
    if not gate.callbacks:
        findings.append(UIFlowStructureFinding("missing_matlab_callback_semantics", "MATLAB callback gate has no callback semantics rows"))
    if not gate.validation_boundaries:
        findings.append(UIFlowStructureFinding("missing_matlab_callback_validation", "MATLAB callback gate has no validation boundaries"))
    if not gate.rationale:
        findings.append(UIFlowStructureFinding("missing_matlab_callback_gate_rationale", "MATLAB callback gate has no rationale"))

    findings.extend(_duplicate_values(gate.semantic_ids(), code="duplicate_matlab_callback_semantic_id", noun="MATLAB callback semantic"))

    for callback in gate.callbacks:
        if callback.semantic_id:
            covered_callback_ids.append(callback.semantic_id)
        if not callback.semantic_id:
            findings.append(UIFlowStructureFinding("missing_matlab_callback_semantic_id", "MATLAB callback semantic has no id"))
        if not callback.control_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_matlab_callback_control",
                    f"MATLAB callback semantic {callback.semantic_id} has no control id",
                    item_id=callback.semantic_id,
                )
            )
        elif interaction_model is not None and callback.control_id not in known_controls:
            findings.append(
                UIFlowStructureFinding(
                    "matlab_callback_control_not_registered",
                    f"MATLAB callback semantic {callback.semantic_id} references unknown control {callback.control_id}",
                    item_id=callback.semantic_id,
                )
            )
        if not callback.callback_kind:
            findings.append(
                UIFlowStructureFinding(
                    "missing_matlab_callback_kind",
                    f"MATLAB callback semantic {callback.semantic_id} has no callback kind",
                    item_id=callback.semantic_id,
                )
            )
        elif callback.callback_kind not in MATLAB_CALLBACK_KINDS:
            findings.append(
                UIFlowStructureFinding(
                    "unknown_matlab_callback_kind",
                    f"MATLAB callback semantic {callback.semantic_id} uses unknown callback kind {callback.callback_kind}",
                    item_id=callback.semantic_id,
                )
            )
        expected = set(callback.expected_branches())
        covered = set(callback.covered_branches)
        missing = sorted(expected - covered)
        if missing:
            findings.append(
                UIFlowStructureFinding(
                    "matlab_callback_missing_branch_semantics",
                    f"MATLAB callback semantic {callback.semantic_id} is missing branches: {', '.join(missing)}",
                    item_id=callback.semantic_id,
                    metadata={"missing_branches": missing},
                )
            )
        if callback.callback_kind in {"uigetfile", "uigetdir", "winopen"} and not (callback.native_boundary or callback.manual_boundary):
            findings.append(
                UIFlowStructureFinding(
                    "matlab_native_callback_missing_boundary",
                    f"MATLAB callback semantic {callback.semantic_id} has no native/manual boundary",
                    item_id=callback.semantic_id,
                )
            )
        if callback.callback_kind == "no_callback" and callback.migration_disposition not in MATLAB_NO_CALLBACK_DISPOSITIONS:
            findings.append(
                UIFlowStructureFinding(
                    "matlab_no_callback_missing_disposition",
                    f"MATLAB no-callback control {callback.semantic_id} has no migration disposition",
                    item_id=callback.semantic_id,
                    metadata={"allowed_dispositions": list(MATLAB_NO_CALLBACK_DISPOSITIONS)},
                )
            )
        if not callback.evidence_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_matlab_callback_evidence_ref",
                    f"MATLAB callback semantic {callback.semantic_id} has no evidence reference",
                    item_id=callback.semantic_id,
                )
            )
        if callback.result.lower() not in _PASSED_UI_RESULTS:
            findings.append(
                UIFlowStructureFinding(
                    "matlab_callback_not_passed",
                    f"MATLAB callback semantic {callback.semantic_id} result is {callback.result}, not passed",
                    item_id=callback.semantic_id,
                )
            )
        if not callback.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_matlab_callback_rationale",
                    f"MATLAB callback semantic {callback.semantic_id} has no rationale",
                    item_id=callback.semantic_id,
                )
            )

    blockers = _blocker_findings(findings)
    return MATLABBaselineCallbackGateReport(
        ok=not blockers,
        gate_id=gate.gate_id,
        findings=tuple(findings),
        covered_callback_ids=tuple(sorted(set(covered_callback_ids))),
    )


def review_ui_human_operability(
    assessment: UIHumanOperabilityAssessment,
    *,
    interaction_model: UIInteractionModel | None = None,
    visible_surface: UIVisibleSurface | None = None,
    journey_coverage: UIJourneyCoverage | None = None,
    functional_chains: UIControlFunctionalChainSet | None = None,
) -> UIHumanOperabilityReport:
    """Review whether a UI is understandable and operable for user tasks."""

    findings: list[UIFlowStructureFinding] = []
    ledger = assessment.task_coverage
    task_ids = set(ledger.task_ids())
    feature_ids = set(ledger.feature_ids)
    scoped_feature_ids = set(ledger.out_of_scope_feature_ids)
    scoped_task_ids = set(ledger.out_of_scope_task_ids)
    in_scope_task_ids = task_ids - scoped_task_ids
    known_controls = set(interaction_model.control_ids()) if interaction_model is not None else set()
    known_events = set(interaction_model.transition_event_ids()) if interaction_model is not None else set()
    known_states = set(interaction_model.state_ids()) if interaction_model is not None else set()
    known_displays = set(interaction_model.display_ids()) if interaction_model is not None else set()
    known_visible_items = set(visible_surface.item_ids()) if visible_surface is not None else set()
    known_journeys = set(journey_coverage.feature_ids()) if journey_coverage is not None else set()
    known_chains = set(functional_chains.chain_ids()) if functional_chains is not None else set()
    feature_to_tasks: dict[str, set[str]] = {}
    task_to_controls: dict[str, set[str]] = {}
    task_to_journeys: dict[str, set[str]] = {}
    task_to_chains: dict[str, set[str]] = {}

    for feature_id, task_id in ledger.feature_task_links:
        feature_to_tasks.setdefault(feature_id, set()).add(task_id)
    for task_id, control_id in ledger.task_control_links:
        task_to_controls.setdefault(task_id, set()).add(control_id)
    for task_id, journey_id in ledger.task_journey_links:
        task_to_journeys.setdefault(task_id, set()).add(journey_id)
    for task_id, chain_id in ledger.task_functional_chain_links:
        task_to_chains.setdefault(task_id, set()).add(chain_id)

    if not assessment.assessment_id:
        findings.append(UIFlowStructureFinding("missing_human_operability_assessment_id", "UI human-operability assessment has no id"))
    if not assessment.current_revision:
        findings.append(UIFlowStructureFinding("missing_human_operability_revision", "UI human-operability assessment has no current revision"))
    if not assessment.validation_boundaries:
        findings.append(UIFlowStructureFinding("missing_human_operability_validation", "UI human-operability assessment has no validation boundaries"))
    if not assessment.rationale:
        findings.append(UIFlowStructureFinding("missing_human_operability_rationale", "UI human-operability assessment has no rationale"))
    if not ledger.ledger_id:
        findings.append(UIFlowStructureFinding("missing_user_task_coverage_ledger_id", "user task coverage ledger has no id"))
    if not ledger.feature_ids:
        findings.append(UIFlowStructureFinding("missing_user_visible_feature_inventory", "user task coverage ledger has no feature inventory"))
    if not ledger.task_frames:
        findings.append(UIFlowStructureFinding("missing_user_task_frames", "user task coverage ledger has no task frames"))
    if not ledger.validation_boundaries:
        findings.append(UIFlowStructureFinding("missing_user_task_coverage_validation", "user task coverage ledger has no validation boundaries"))
    if not ledger.rationale:
        findings.append(UIFlowStructureFinding("missing_user_task_coverage_rationale", "user task coverage ledger has no rationale"))

    findings.extend(_duplicate_values(ledger.feature_ids, code="duplicate_user_visible_feature_id", noun="user-visible feature"))
    findings.extend(_duplicate_values(ledger.task_ids(), code="duplicate_user_task_id", noun="user task"))
    findings.extend(_duplicate_values(ledger.primary_control_ids, code="duplicate_primary_control_id", noun="primary control"))

    for feature_id in sorted(feature_ids - scoped_feature_ids):
        linked_tasks = feature_to_tasks.get(feature_id, set()) - scoped_task_ids
        if not linked_tasks:
            findings.append(
                UIFlowStructureFinding(
                    "feature_without_user_task",
                    f"user-visible feature {feature_id} has no in-scope user task",
                    item_id=feature_id,
                )
            )

    for feature_id, task_id in ledger.feature_task_links:
        if feature_id not in feature_ids:
            findings.append(
                UIFlowStructureFinding(
                    "feature_task_link_unknown_feature",
                    f"feature-task link references unknown feature {feature_id}",
                    item_id=feature_id,
                )
            )
        if task_id not in task_ids:
            findings.append(
                UIFlowStructureFinding(
                    "feature_task_link_unknown_task",
                    f"feature-task link references unknown task {task_id}",
                    item_id=task_id,
                )
            )

    for task_id, control_id in ledger.task_control_links:
        if task_id not in task_ids:
            findings.append(UIFlowStructureFinding("task_control_link_unknown_task", f"task-control link references unknown task {task_id}", item_id=task_id))
        if interaction_model is not None and control_id not in known_controls:
            findings.append(UIFlowStructureFinding("task_control_link_unknown_control", f"task-control link references unknown control {control_id}", item_id=control_id))
    for task_id, journey_id in ledger.task_journey_links:
        if task_id not in task_ids:
            findings.append(UIFlowStructureFinding("task_journey_link_unknown_task", f"task-journey link references unknown task {task_id}", item_id=task_id))
        if journey_coverage is not None and journey_id not in known_journeys:
            findings.append(UIFlowStructureFinding("task_journey_link_unknown_journey", f"task-journey link references unknown journey {journey_id}", item_id=journey_id))
    for task_id, chain_id in ledger.task_functional_chain_links:
        if task_id not in task_ids:
            findings.append(UIFlowStructureFinding("task_functional_chain_link_unknown_task", f"task-chain link references unknown task {task_id}", item_id=task_id))
        if functional_chains is not None and chain_id not in known_chains:
            findings.append(UIFlowStructureFinding("task_functional_chain_link_unknown_chain", f"task-chain link references unknown functional chain {chain_id}", item_id=chain_id))

    for task in ledger.task_frames:
        if task.task_id in scoped_task_ids:
            continue
        if not task.task_id:
            findings.append(UIFlowStructureFinding("missing_user_task_id", "user task frame has no id"))
        if not task.user_goal:
            findings.append(UIFlowStructureFinding("missing_user_task_goal", f"user task {task.task_id} has no user goal", item_id=task.task_id))
        if not task.source_feature_ids:
            findings.append(UIFlowStructureFinding("user_task_without_feature", f"user task {task.task_id} has no source feature id", item_id=task.task_id))
        for feature_id in task.source_feature_ids:
            if feature_id not in feature_ids:
                findings.append(UIFlowStructureFinding("user_task_unknown_feature", f"user task {task.task_id} references unknown feature {feature_id}", item_id=task.task_id))
        if not task.entry_state_ids:
            findings.append(UIFlowStructureFinding("user_task_missing_entry_state", f"user task {task.task_id} has no entry state", item_id=task.task_id))
        if not task.main_path_event_ids:
            findings.append(UIFlowStructureFinding("user_task_missing_main_path", f"user task {task.task_id} has no main path events", item_id=task.task_id))
        if not task.success_state_ids:
            findings.append(UIFlowStructureFinding("user_task_missing_success_state", f"user task {task.task_id} has no success state", item_id=task.task_id))
        if not task.required_feedback_item_ids:
            findings.append(UIFlowStructureFinding("user_task_missing_feedback", f"user task {task.task_id} has no required visible feedback", item_id=task.task_id))
        if not (task.cancel_event_ids or task.cancel_behavior):
            findings.append(UIFlowStructureFinding("user_task_missing_cancel_path", f"user task {task.task_id} has no cancel path or cancel behavior", item_id=task.task_id))
        if not (task.error_state_ids or task.error_behavior):
            findings.append(UIFlowStructureFinding("user_task_missing_error_path", f"user task {task.task_id} has no error path or error behavior", item_id=task.task_id))
        if task.task_id not in task_to_controls and task.task_id not in task_to_journeys:
            findings.append(UIFlowStructureFinding("user_task_without_ui_path", f"user task {task.task_id} has no UI journey or control path", item_id=task.task_id))
        if not task.keyboard_contract_id:
            findings.append(UIFlowStructureFinding("user_task_without_keyboard_focus_contract", f"user task {task.task_id} has no keyboard/focus contract", item_id=task.task_id))
        if not task.rationale:
            findings.append(UIFlowStructureFinding("missing_user_task_rationale", f"user task {task.task_id} has no rationale", item_id=task.task_id))
        for state_id in task.entry_state_ids + task.success_state_ids + task.error_state_ids:
            if interaction_model is not None and state_id not in known_states:
                findings.append(UIFlowStructureFinding("user_task_state_not_registered", f"user task {task.task_id} references unknown state {state_id}", item_id=task.task_id))
        for event_id in task.main_path_event_ids + task.alternate_path_event_ids + task.cancel_event_ids:
            if interaction_model is not None and event_id not in known_events:
                findings.append(UIFlowStructureFinding("user_task_event_not_registered", f"user task {task.task_id} references unknown event {event_id}", item_id=task.task_id))
        for control_id in task.required_control_ids:
            if interaction_model is not None and control_id not in known_controls:
                findings.append(UIFlowStructureFinding("user_task_control_not_registered", f"user task {task.task_id} references unknown control {control_id}", item_id=task.task_id))
        for display_id in task.required_display_ids:
            if interaction_model is not None and display_id not in known_displays:
                findings.append(UIFlowStructureFinding("user_task_display_not_registered", f"user task {task.task_id} references unknown display {display_id}", item_id=task.task_id))

    linked_control_ids = {control_id for controls in task_to_controls.values() for control_id in controls}
    for control_id in ledger.primary_control_ids:
        if control_id not in linked_control_ids:
            findings.append(
                UIFlowStructureFinding(
                    "orphan_primary_control",
                    f"primary control {control_id} is not owned by any user task",
                    item_id=control_id,
                )
            )
        if interaction_model is not None and control_id not in known_controls:
            findings.append(UIFlowStructureFinding("primary_control_not_registered", f"primary control {control_id} is not registered", item_id=control_id))

    findings.extend(_duplicate_values(tuple(item.map_id for item in assessment.region_maps), code="duplicate_region_semantic_map_id", noun="region semantic map"))
    for region in assessment.region_maps:
        if not region.map_id:
            findings.append(UIFlowStructureFinding("missing_region_semantic_map_id", "region semantic map has no id"))
        if not region.region_id:
            findings.append(UIFlowStructureFinding("missing_region_id", f"region semantic map {region.map_id} has no region id", item_id=region.map_id))
        if region.region_role not in UI_REGION_ROLES:
            findings.append(UIFlowStructureFinding("unknown_region_role", f"region {region.region_id} uses unknown role {region.region_role}", item_id=region.region_id))
        if not (region.task_ids or region.control_ids or region.display_ids or region.status_item_ids):
            findings.append(UIFlowStructureFinding("region_semantics_without_owned_items", f"region {region.region_id} has no owned tasks, controls, displays, or status items", item_id=region.region_id))
        if region.region_role in {"status", "result"} and region.control_ids and "control" not in region.allowed_item_kinds:
            findings.append(UIFlowStructureFinding("region_role_conflict", f"{region.region_role} region {region.region_id} owns controls without allowing controls", item_id=region.region_id))
        if not region.rationale:
            findings.append(UIFlowStructureFinding("missing_region_semantic_rationale", f"region {region.region_id} has no rationale", item_id=region.region_id))
        for task_id in region.task_ids:
            if task_id not in task_ids:
                findings.append(UIFlowStructureFinding("region_task_not_registered", f"region {region.region_id} references unknown task {task_id}", item_id=region.region_id))
        for control_id in region.control_ids:
            if interaction_model is not None and control_id not in known_controls:
                findings.append(UIFlowStructureFinding("region_control_not_registered", f"region {region.region_id} references unknown control {control_id}", item_id=region.region_id))
        for display_id in region.display_ids:
            if interaction_model is not None and display_id not in known_displays:
                findings.append(UIFlowStructureFinding("region_display_not_registered", f"region {region.region_id} references unknown display {display_id}", item_id=region.region_id))

    findings.extend(_duplicate_values(tuple(item.contract_id for item in assessment.affordance_contracts), code="duplicate_affordance_contract_id", noun="affordance contract"))
    for affordance in assessment.affordance_contracts:
        perceived_actionable = affordance.perceived_role in UI_PERCEIVED_ACTIONABLE_ROLES
        actual_actionable = affordance.actual_role in UI_ACTUAL_ACTIONABLE_ROLES
        actual_non_actionable = affordance.actual_role in UI_ACTUAL_NON_ACTIONABLE_ROLES
        if not affordance.contract_id:
            findings.append(UIFlowStructureFinding("missing_affordance_contract_id", "affordance contract has no id"))
        if not affordance.visible_item_id:
            findings.append(UIFlowStructureFinding("missing_affordance_visible_item", f"affordance {affordance.contract_id} has no visible item id", item_id=affordance.contract_id))
        elif visible_surface is not None and affordance.visible_item_id not in known_visible_items:
            findings.append(UIFlowStructureFinding("affordance_visible_item_not_registered", f"affordance {affordance.contract_id} references unknown visible item {affordance.visible_item_id}", item_id=affordance.contract_id))
        if affordance.task_id and affordance.task_id not in task_ids:
            findings.append(UIFlowStructureFinding("affordance_task_not_registered", f"affordance {affordance.contract_id} references unknown task {affordance.task_id}", item_id=affordance.contract_id))
        if affordance.control_id and interaction_model is not None and affordance.control_id not in known_controls:
            findings.append(UIFlowStructureFinding("affordance_control_not_registered", f"affordance {affordance.contract_id} references unknown control {affordance.control_id}", item_id=affordance.contract_id))
        if actual_actionable and not affordance.visual_cues:
            findings.append(UIFlowStructureFinding("actionable_item_missing_visual_cue", f"actionable item {affordance.visible_item_id} has no visual cue", item_id=affordance.visible_item_id))
        if actual_actionable and not affordance.expected_user_action:
            findings.append(UIFlowStructureFinding("actionable_item_missing_expected_action", f"actionable item {affordance.visible_item_id} has no expected user action", item_id=affordance.visible_item_id))
        if actual_actionable and not affordance.expected_result:
            findings.append(UIFlowStructureFinding("actionable_item_missing_expected_result", f"actionable item {affordance.visible_item_id} has no expected result", item_id=affordance.visible_item_id))
        if actual_actionable and not perceived_actionable:
            findings.append(UIFlowStructureFinding("clickable_item_not_visually_actionable", f"item {affordance.visible_item_id} is actionable but not perceived as actionable", item_id=affordance.visible_item_id))
        if perceived_actionable and actual_non_actionable and affordance.mismatch_disposition not in UI_AFFORDANCE_MISMATCH_DISPOSITIONS:
            findings.append(UIFlowStructureFinding("affordance_role_mismatch", f"item {affordance.visible_item_id} looks actionable but actual role is {affordance.actual_role}", item_id=affordance.visible_item_id))
        if not affordance.rationale:
            findings.append(UIFlowStructureFinding("missing_affordance_rationale", f"affordance {affordance.contract_id} has no rationale", item_id=affordance.contract_id))

    grammar_groups: dict[tuple[str, str, str], set[str]] = {}
    findings.extend(_duplicate_values(tuple(item.action_id for item in assessment.action_grammars), code="duplicate_action_grammar_id", noun="action grammar"))
    for grammar in assessment.action_grammars:
        if not grammar.action_id:
            findings.append(UIFlowStructureFinding("missing_action_grammar_id", "action grammar has no id"))
        if grammar.task_id not in task_ids:
            findings.append(UIFlowStructureFinding("action_grammar_task_not_registered", f"action grammar {grammar.action_id} references unknown task {grammar.task_id}", item_id=grammar.action_id))
        if not grammar.user_intent:
            findings.append(UIFlowStructureFinding("missing_action_grammar_user_intent", f"action grammar {grammar.action_id} has no user intent", item_id=grammar.action_id))
        if not grammar.primary_control_id:
            findings.append(UIFlowStructureFinding("missing_action_grammar_primary_control", f"action grammar {grammar.action_id} has no primary control", item_id=grammar.action_id))
        elif interaction_model is not None and grammar.primary_control_id not in known_controls:
            findings.append(UIFlowStructureFinding("action_grammar_primary_control_not_registered", f"action grammar {grammar.action_id} references unknown primary control {grammar.primary_control_id}", item_id=grammar.action_id))
        if grammar.conflicting_control_ids and not grammar.duplicate_policy:
            findings.append(UIFlowStructureFinding("action_grammar_conflict", f"action grammar {grammar.action_id} has conflicting controls without duplicate policy", item_id=grammar.action_id))
        if not grammar.expected_feedback_item_ids:
            findings.append(UIFlowStructureFinding("action_grammar_missing_feedback", f"action grammar {grammar.action_id} has no expected feedback item", item_id=grammar.action_id))
        if not grammar.rationale:
            findings.append(UIFlowStructureFinding("missing_action_grammar_rationale", f"action grammar {grammar.action_id} has no rationale", item_id=grammar.action_id))
        for state_id in grammar.source_state_ids or ("",):
            grammar_groups.setdefault((grammar.task_id, state_id, grammar.user_intent), set()).add(grammar.primary_control_id)
        for control_id in grammar.alternate_control_ids + grammar.conflicting_control_ids:
            if interaction_model is not None and control_id not in known_controls:
                findings.append(UIFlowStructureFinding("action_grammar_control_not_registered", f"action grammar {grammar.action_id} references unknown control {control_id}", item_id=grammar.action_id))
    for (task_id, state_id, user_intent), primary_ids in sorted(grammar_groups.items()):
        primary_ids.discard("")
        if len(primary_ids) > 1:
            findings.append(
                UIFlowStructureFinding(
                    "duplicate_primary_action",
                    f"task {task_id} has multiple primary controls for {user_intent} in state {state_id or '(any)'}",
                    item_id=task_id,
                    metadata={"primary_control_ids": sorted(primary_ids)},
                )
            )

    findings.extend(_duplicate_values(tuple(item.contract_id for item in assessment.dialog_contracts), code="duplicate_dialog_window_contract_id", noun="dialog/window contract"))
    for dialog in assessment.dialog_contracts:
        if dialog.task_id not in task_ids:
            findings.append(UIFlowStructureFinding("dialog_task_not_registered", f"dialog contract {dialog.contract_id} references unknown task {dialog.task_id}", item_id=dialog.contract_id))
        if dialog.dialog_type not in UI_DIALOG_TYPES:
            findings.append(UIFlowStructureFinding("unknown_dialog_type", f"dialog contract {dialog.contract_id} uses unknown dialog type {dialog.dialog_type}", item_id=dialog.contract_id))
        if not dialog.trigger_control_id:
            findings.append(UIFlowStructureFinding("dialog_missing_trigger_control", f"dialog contract {dialog.contract_id} has no trigger control", item_id=dialog.contract_id))
        elif interaction_model is not None and dialog.trigger_control_id not in known_controls:
            findings.append(UIFlowStructureFinding("dialog_trigger_control_not_registered", f"dialog contract {dialog.contract_id} references unknown trigger control {dialog.trigger_control_id}", item_id=dialog.contract_id))
        if not dialog.success_return:
            findings.append(UIFlowStructureFinding("dialog_missing_success_return", f"dialog contract {dialog.contract_id} has no success return", item_id=dialog.contract_id))
        if not dialog.cancel_return:
            findings.append(UIFlowStructureFinding("dialog_missing_cancel_return", f"dialog contract {dialog.contract_id} has no cancel return", item_id=dialog.contract_id))
        if not dialog.error_return:
            findings.append(UIFlowStructureFinding("dialog_missing_error_return", f"dialog contract {dialog.contract_id} has no error return", item_id=dialog.contract_id))
        if not dialog.focus_return_target_id:
            findings.append(UIFlowStructureFinding("dialog_missing_focus_return", f"dialog contract {dialog.contract_id} has no focus return target", item_id=dialog.contract_id))
        if not dialog.feedback_item_ids:
            findings.append(UIFlowStructureFinding("dialog_missing_feedback", f"dialog contract {dialog.contract_id} has no feedback item", item_id=dialog.contract_id))
        if dialog.dialog_type.startswith("native_") and not (dialog.native_boundary or dialog.manual_boundary):
            findings.append(UIFlowStructureFinding("native_dialog_missing_boundary", f"native dialog contract {dialog.contract_id} has no native/manual boundary", item_id=dialog.contract_id))
        if not dialog.evidence_ref:
            findings.append(UIFlowStructureFinding("dialog_missing_evidence_ref", f"dialog contract {dialog.contract_id} has no evidence reference", item_id=dialog.contract_id))
        if not dialog.rationale:
            findings.append(UIFlowStructureFinding("missing_dialog_rationale", f"dialog contract {dialog.contract_id} has no rationale", item_id=dialog.contract_id))

    keyboard_by_id = {item.contract_id: item for item in assessment.keyboard_contracts}
    findings.extend(_duplicate_values(tuple(keyboard_by_id), code="duplicate_keyboard_focus_contract_id", noun="keyboard/focus contract"))
    for task in ledger.task_frames:
        if task.task_id in scoped_task_ids:
            continue
        if task.keyboard_contract_id and task.keyboard_contract_id not in keyboard_by_id:
            findings.append(UIFlowStructureFinding("task_keyboard_contract_not_registered", f"user task {task.task_id} references unknown keyboard/focus contract {task.keyboard_contract_id}", item_id=task.task_id))
    for keyboard in assessment.keyboard_contracts:
        if keyboard.task_id not in task_ids:
            findings.append(UIFlowStructureFinding("keyboard_task_not_registered", f"keyboard contract {keyboard.contract_id} references unknown task {keyboard.task_id}", item_id=keyboard.contract_id))
        if keyboard.state_id and interaction_model is not None and keyboard.state_id not in known_states:
            findings.append(UIFlowStructureFinding("keyboard_state_not_registered", f"keyboard contract {keyboard.contract_id} references unknown state {keyboard.state_id}", item_id=keyboard.contract_id))
        if not keyboard.tab_order_control_ids:
            findings.append(UIFlowStructureFinding("keyboard_missing_tab_order", f"keyboard contract {keyboard.contract_id} has no Tab order", item_id=keyboard.contract_id))
        if not keyboard.default_enter_control_id:
            findings.append(UIFlowStructureFinding("keyboard_missing_enter_behavior", f"keyboard contract {keyboard.contract_id} has no default Enter behavior", item_id=keyboard.contract_id))
        if not keyboard.escape_behavior:
            findings.append(UIFlowStructureFinding("keyboard_missing_escape_behavior", f"keyboard contract {keyboard.contract_id} has no Escape behavior", item_id=keyboard.contract_id))
        if not keyboard.focus_return_rules:
            findings.append(UIFlowStructureFinding("keyboard_missing_focus_return", f"keyboard contract {keyboard.contract_id} has no focus return rules", item_id=keyboard.contract_id))
        if not keyboard.disabled_skip_policy:
            findings.append(UIFlowStructureFinding("keyboard_missing_disabled_skip_policy", f"keyboard contract {keyboard.contract_id} has no disabled-control skip policy", item_id=keyboard.contract_id))
        if not keyboard.evidence_ref:
            findings.append(UIFlowStructureFinding("keyboard_missing_evidence_ref", f"keyboard contract {keyboard.contract_id} has no evidence reference", item_id=keyboard.contract_id))
        if not keyboard.rationale:
            findings.append(UIFlowStructureFinding("missing_keyboard_rationale", f"keyboard contract {keyboard.contract_id} has no rationale", item_id=keyboard.contract_id))
        for control_id in keyboard.tab_order_control_ids + (keyboard.default_enter_control_id, keyboard.error_focus_target_id):
            if control_id and interaction_model is not None and control_id not in known_controls:
                findings.append(UIFlowStructureFinding("keyboard_control_not_registered", f"keyboard contract {keyboard.contract_id} references unknown control {control_id}", item_id=keyboard.contract_id))

    walkthrough_task_ids = {item.task_id for item in assessment.walkthroughs if item.result.lower() in _PASSED_UI_RESULTS}
    for task_id in sorted(in_scope_task_ids - walkthrough_task_ids):
        findings.append(UIFlowStructureFinding("user_task_without_walkthrough", f"user task {task_id} has no passing human walkthrough", item_id=task_id))
    findings.extend(_duplicate_values(tuple(item.scenario_id for item in assessment.walkthroughs), code="duplicate_walkthrough_scenario_id", noun="walkthrough scenario"))
    for scenario in assessment.walkthroughs:
        if scenario.task_id not in task_ids:
            findings.append(UIFlowStructureFinding("walkthrough_task_not_registered", f"walkthrough {scenario.scenario_id} references unknown task {scenario.task_id}", item_id=scenario.scenario_id))
        if not scenario.steps:
            findings.append(UIFlowStructureFinding("walkthrough_missing_steps", f"walkthrough {scenario.scenario_id} has no steps", item_id=scenario.scenario_id))
        if not scenario.evidence_ref:
            findings.append(UIFlowStructureFinding("walkthrough_missing_evidence_ref", f"walkthrough {scenario.scenario_id} has no evidence reference", item_id=scenario.scenario_id))
        if scenario.result.lower() not in _PASSED_UI_RESULTS:
            findings.append(UIFlowStructureFinding("walkthrough_not_passed", f"walkthrough {scenario.scenario_id} result is {scenario.result}, not passed", item_id=scenario.scenario_id))
        if scenario.confusion_notes and not scenario.mitigation:
            findings.append(UIFlowStructureFinding("walkthrough_confusion_unmitigated", f"walkthrough {scenario.scenario_id} has confusion notes without mitigation", item_id=scenario.scenario_id))
        if not scenario.rationale:
            findings.append(UIFlowStructureFinding("missing_walkthrough_rationale", f"walkthrough {scenario.scenario_id} has no rationale", item_id=scenario.scenario_id))
        findings.extend(_duplicate_values(scenario.step_ids(), code="duplicate_walkthrough_step_id", noun="walkthrough step"))
        for step in scenario.steps:
            if not step.visible_prompt:
                findings.append(UIFlowStructureFinding("walkthrough_missing_visible_prompt", f"walkthrough step {step.step_id} has no visible prompt", item_id=step.step_id))
            if not step.user_action:
                findings.append(UIFlowStructureFinding("walkthrough_missing_user_action", f"walkthrough step {step.step_id} has no user action", item_id=step.step_id))
            if not step.expected_feedback:
                findings.append(UIFlowStructureFinding("walkthrough_missing_expected_feedback", f"walkthrough step {step.step_id} has no expected feedback", item_id=step.step_id))
            if not step.actual_feedback:
                findings.append(UIFlowStructureFinding("walkthrough_missing_actual_feedback", f"walkthrough step {step.step_id} has no actual feedback", item_id=step.step_id))
            if not step.evidence_ref:
                findings.append(UIFlowStructureFinding("walkthrough_step_missing_evidence_ref", f"walkthrough step {step.step_id} has no evidence reference", item_id=step.step_id))
            if step.confusion and not step.mitigation:
                findings.append(UIFlowStructureFinding("walkthrough_step_confusion_unmitigated", f"walkthrough step {step.step_id} reports confusion without mitigation", item_id=step.step_id))

    blockers = _blocker_findings(findings)
    return UIHumanOperabilityReport(
        ok=not blockers,
        assessment_id=assessment.assessment_id,
        findings=tuple(findings),
        covered_task_ids=tuple(sorted(task_ids)),
        covered_feature_ids=tuple(sorted(feature_ids)),
    )


def review_ui_render_evidence(
    evidence_set: UIRenderEvidenceSet,
    *,
    interaction_model: UIInteractionModel | None = None,
) -> UIRenderEvidenceReport:
    """Review render/implementation evidence kinds for a runnable UI claim."""

    findings: list[UIFlowStructureFinding] = []
    supported_kinds = set(SUPPORTED_UI_EVIDENCE_KINDS)

    if not evidence_set.evidence_set_id:
        findings.append(UIFlowStructureFinding("missing_render_evidence_set_id", "UI render evidence set has no id"))
    if interaction_model is not None:
        if not evidence_set.source_interaction_model_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_render_evidence_source_model",
                    "UI render evidence set has no source interaction model id",
                )
            )
        elif evidence_set.source_interaction_model_id != interaction_model.model_id:
            findings.append(
                UIFlowStructureFinding(
                    "render_evidence_model_mismatch",
                    "UI render evidence set does not reference the supplied interaction model",
                )
            )
    if not evidence_set.implementation_target:
        findings.append(
            UIFlowStructureFinding("missing_render_implementation_target", "UI render evidence has no implementation target")
        )
    if not evidence_set.current_model_revision:
        findings.append(
            UIFlowStructureFinding("missing_render_current_revision", "UI render evidence has no current model or implementation revision")
        )
    if not evidence_set.evidence:
        findings.append(UIFlowStructureFinding("missing_render_evidence", "UI render evidence set has no evidence rows"))
    if not evidence_set.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_render_validation_boundary", "UI render evidence set has no validation boundaries")
        )
    if not evidence_set.rationale:
        findings.append(UIFlowStructureFinding("missing_render_evidence_rationale", "UI render evidence set has no rationale"))

    findings.extend(_duplicate_values(evidence_set.evidence_ids(), code="duplicate_render_evidence_id", noun="render evidence"))

    for evidence in evidence_set.evidence:
        if not evidence.evidence_id:
            findings.append(UIFlowStructureFinding("missing_render_evidence_id", "render evidence row has no id"))
        if not evidence.evidence_kind:
            findings.append(
                UIFlowStructureFinding(
                    "missing_render_evidence_kind",
                    f"render evidence {evidence.evidence_id} has no evidence kind",
                    item_id=evidence.evidence_id,
                )
            )
        elif evidence.evidence_kind not in supported_kinds:
            findings.append(
                UIFlowStructureFinding(
                    "unknown_render_evidence_kind",
                    f"render evidence {evidence.evidence_id} uses unknown evidence kind {evidence.evidence_kind}",
                    item_id=evidence.evidence_id,
                    metadata={"supported_kinds": sorted(supported_kinds)},
                )
            )
        if not evidence.evidence_target:
            findings.append(
                UIFlowStructureFinding(
                    "missing_render_evidence_target",
                    f"render evidence {evidence.evidence_id} has no evidence target",
                    item_id=evidence.evidence_id,
                )
            )
        if not evidence.evidence_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_render_evidence_ref",
                    f"render evidence {evidence.evidence_id} has no evidence reference",
                    item_id=evidence.evidence_id,
                )
            )
        if evidence.result.lower() not in _PASSED_UI_RESULTS:
            findings.append(
                UIFlowStructureFinding(
                    "render_evidence_not_passed",
                    f"render evidence {evidence.evidence_id} result is {evidence.result}",
                    item_id=evidence.evidence_id,
                )
            )
        if not evidence.model_revision:
            findings.append(
                UIFlowStructureFinding(
                    "missing_render_evidence_revision",
                    f"render evidence {evidence.evidence_id} has no model or implementation revision",
                    item_id=evidence.evidence_id,
                )
            )
        elif evidence_set.current_model_revision and evidence.model_revision != evidence_set.current_model_revision:
            findings.append(
                UIFlowStructureFinding(
                    "stale_render_evidence",
                    f"render evidence {evidence.evidence_id} references stale revision {evidence.model_revision}",
                    item_id=evidence.evidence_id,
                    metadata={
                        "evidence_revision": evidence.model_revision,
                        "current_revision": evidence_set.current_model_revision,
                    },
                )
            )
        if evidence.source_interaction_model_id and evidence_set.source_interaction_model_id and (
            evidence.source_interaction_model_id != evidence_set.source_interaction_model_id
        ):
            findings.append(
                UIFlowStructureFinding(
                    "render_evidence_source_model_mismatch",
                    f"render evidence {evidence.evidence_id} references a different interaction model",
                    item_id=evidence.evidence_id,
                )
            )
        if not evidence.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_render_evidence_rationale",
                    f"render evidence {evidence.evidence_id} has no rationale",
                    item_id=evidence.evidence_id,
                )
            )

    blockers = _blocker_findings(findings)
    evidence_kinds = tuple(dict.fromkeys(evidence.evidence_kind for evidence in evidence_set.evidence if evidence.evidence_kind))
    return UIRenderEvidenceReport(
        ok=not blockers,
        evidence_set_id=evidence_set.evidence_set_id,
        findings=tuple(findings),
        evidence_kinds=evidence_kinds,
    )


def review_ui_geometry_layout_evidence(
    geometry: UIGeometryLayoutEvidenceSet,
    *,
    interaction_model: UIInteractionModel | None = None,
) -> UIGeometryLayoutEvidenceReport:
    """Review universal UI geometry/layout evidence."""

    findings: list[UIFlowStructureFinding] = []

    if not geometry.geometry_id:
        findings.append(UIFlowStructureFinding("missing_geometry_evidence_id", "UI geometry evidence set has no id"))
    if interaction_model is not None:
        if not geometry.source_interaction_model_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_geometry_source_model",
                    "UI geometry evidence set has no source interaction model id",
                )
            )
        elif geometry.source_interaction_model_id != interaction_model.model_id:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_model_mismatch",
                    "UI geometry evidence set does not reference the supplied interaction model",
                )
            )
    if not geometry.entries:
        findings.append(UIFlowStructureFinding("missing_geometry_entries", "UI geometry evidence set has no entries"))
    if not geometry.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_geometry_validation_boundary", "UI geometry evidence set has no validation boundaries")
        )
    if not geometry.rationale:
        findings.append(UIFlowStructureFinding("missing_geometry_rationale", "UI geometry evidence set has no rationale"))

    findings.extend(_duplicate_values(geometry.entry_ids(), code="duplicate_geometry_evidence_id", noun="geometry evidence"))

    for entry in geometry.entries:
        if not entry.evidence_id:
            findings.append(UIFlowStructureFinding("missing_geometry_entry_id", "geometry evidence row has no id"))
        if not entry.target_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_geometry_target",
                    f"geometry evidence {entry.evidence_id} has no target",
                    item_id=entry.evidence_id,
                )
            )
        if not entry.viewport:
            findings.append(
                UIFlowStructureFinding(
                    "missing_geometry_viewport",
                    f"geometry evidence {entry.evidence_id} has no viewport or container boundary",
                    item_id=entry.evidence_id,
                )
            )
        if not entry.evidence_ref:
            findings.append(
                UIFlowStructureFinding(
                    "missing_geometry_evidence_ref",
                    f"geometry evidence {entry.evidence_id} has no evidence reference",
                    item_id=entry.evidence_id,
                )
            )
        if entry.result.lower() not in _PASSED_UI_RESULTS:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_evidence_not_passed",
                    f"geometry evidence {entry.evidence_id} result is {entry.result}",
                    item_id=entry.evidence_id,
                )
            )
        if entry.text_overflow:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_text_overflow",
                    f"geometry evidence {entry.evidence_id} reports text overflow",
                    item_id=entry.target_id,
                )
            )
        if entry.control_overlap:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_control_overlap",
                    f"geometry evidence {entry.evidence_id} reports overlapping controls",
                    item_id=entry.target_id,
                )
            )
        if entry.out_of_bounds:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_out_of_bounds",
                    f"geometry evidence {entry.evidence_id} reports out-of-bounds UI",
                    item_id=entry.target_id,
                )
            )
        if not entry.focus_reachable:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_focus_not_reachable",
                    f"geometry evidence {entry.evidence_id} reports unreachable focus",
                    item_id=entry.target_id,
                )
            )
        if not entry.keyboard_reachable:
            findings.append(
                UIFlowStructureFinding(
                    "geometry_keyboard_not_reachable",
                    f"geometry evidence {entry.evidence_id} reports unreachable keyboard path",
                    item_id=entry.target_id,
                )
            )
        if not entry.scroll_owner:
            findings.append(
                UIFlowStructureFinding(
                    "missing_geometry_scroll_owner",
                    f"geometry evidence {entry.evidence_id} has no scroll owner",
                    item_id=entry.target_id,
                )
            )
        if not entry.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_geometry_entry_rationale",
                    f"geometry evidence {entry.evidence_id} has no rationale",
                    item_id=entry.evidence_id,
                )
            )

    blockers = _blocker_findings(findings)
    checked_targets = tuple(dict.fromkeys(entry.target_id for entry in geometry.entries if entry.target_id))
    return UIGeometryLayoutEvidenceReport(
        ok=not blockers,
        geometry_id=geometry.geometry_id,
        findings=tuple(findings),
        checked_targets=checked_targets,
    )


def review_ui_responsiveness_contract(
    contract: UIResponsivenessContract,
    *,
    interaction_model: UIInteractionModel | None = None,
) -> UIResponsivenessContractReport:
    """Review hot-path feedback, cold-path stale guards, and stable regions."""

    findings: list[UIFlowStructureFinding] = []
    known_events = set(interaction_model.transition_event_ids()) if interaction_model is not None else set()

    if not contract.contract_id:
        findings.append(UIFlowStructureFinding("missing_responsiveness_contract_id", "UI responsiveness contract has no id"))
    if interaction_model is not None:
        if not contract.source_interaction_model_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_responsiveness_source_model",
                    "UI responsiveness contract has no source interaction model id",
                )
            )
        elif contract.source_interaction_model_id != interaction_model.model_id:
            findings.append(
                UIFlowStructureFinding(
                    "responsiveness_model_mismatch",
                    "UI responsiveness contract does not reference the supplied interaction model",
                )
            )
    if not (contract.hot_path_actions or contract.cold_path_work or contract.stable_region_rules):
        findings.append(
            UIFlowStructureFinding(
                "missing_responsiveness_entries",
                "UI responsiveness contract has no hot path, cold path, or stable region entries",
            )
        )
    if not contract.validation_boundaries:
        findings.append(
            UIFlowStructureFinding("missing_responsiveness_validation", "UI responsiveness contract has no validation boundaries")
        )
    if not contract.rationale:
        findings.append(
            UIFlowStructureFinding("missing_responsiveness_rationale", "UI responsiveness contract has no rationale")
        )

    findings.extend(
        _duplicate_values(
            tuple(action.action_id for action in contract.hot_path_actions),
            code="duplicate_hot_path_action_id",
            noun="hot path action",
        )
    )
    findings.extend(
        _duplicate_values(
            tuple(work.work_id for work in contract.cold_path_work),
            code="duplicate_cold_path_work_id",
            noun="cold path work",
        )
    )

    for action in contract.hot_path_actions:
        if not action.action_id:
            findings.append(UIFlowStructureFinding("missing_hot_path_action_id", "hot path action has no id"))
        if interaction_model is not None and action.event_id and action.event_id not in known_events:
            findings.append(
                UIFlowStructureFinding(
                    "hot_path_event_not_registered",
                    f"hot path action {action.action_id} references unknown event {action.event_id}",
                    item_id=action.action_id,
                )
            )
        if not (action.feedback_target_id or action.feedback_description):
            findings.append(
                UIFlowStructureFinding(
                    "missing_hot_path_feedback",
                    f"hot path action {action.action_id} has no immediate feedback target or description",
                    item_id=action.action_id,
                )
            )
        if not action.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_hot_path_rationale",
                    f"hot path action {action.action_id} has no rationale",
                    item_id=action.action_id,
                )
            )

    for work in contract.cold_path_work:
        if not work.work_id:
            findings.append(UIFlowStructureFinding("missing_cold_path_work_id", "cold path work has no id"))
        if interaction_model is not None and work.trigger_event_id and work.trigger_event_id not in known_events:
            findings.append(
                UIFlowStructureFinding(
                    "cold_path_event_not_registered",
                    f"cold path work {work.work_id} references unknown event {work.trigger_event_id}",
                    item_id=work.work_id,
                )
            )
        if not work.result_target_id:
            findings.append(
                UIFlowStructureFinding(
                    "missing_cold_path_result_target",
                    f"cold path work {work.work_id} has no result target",
                    item_id=work.work_id,
                )
            )
        if not work.has_stale_protection():
            findings.append(
                UIFlowStructureFinding(
                    "missing_cold_path_stale_guard",
                    f"cold path work {work.work_id} has no stale guard, cancellation rule, or coalescing rule",
                    item_id=work.work_id,
                )
            )
        if not work.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_cold_path_rationale",
                    f"cold path work {work.work_id} has no rationale",
                    item_id=work.work_id,
                )
            )

    for rule in contract.stable_region_rules:
        if not rule.region_id:
            findings.append(UIFlowStructureFinding("missing_stable_region_id", "stable region rule has no region id"))
        if not rule.preservation_rule:
            findings.append(
                UIFlowStructureFinding(
                    "missing_stable_region_preservation",
                    f"stable region {rule.region_id} has no preservation rule",
                    item_id=rule.region_id,
                )
            )
        if not rule.rationale:
            findings.append(
                UIFlowStructureFinding(
                    "missing_stable_region_rationale",
                    f"stable region {rule.region_id} has no rationale",
                    item_id=rule.region_id,
                )
            )

    blockers = _blocker_findings(findings)
    return UIResponsivenessContractReport(
        ok=not blockers,
        contract_id=contract.contract_id,
        findings=tuple(findings),
        hot_path_ids=tuple(action.action_id for action in contract.hot_path_actions),
        cold_path_ids=tuple(work.work_id for work in contract.cold_path_work),
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
    "UIObservedSurfaceInventory",
    "UIObservedSurfaceInventoryReport",
    "UIObservedSurfaceItem",
    "UIControlFunctionalChain",
    "UIControlFunctionalChainReport",
    "UIControlFunctionalChainSet",
    "UIGeometryLayoutEvidence",
    "UIGeometryLayoutEvidenceReport",
    "UIGeometryLayoutEvidenceSet",
    "UIHotPathAction",
    "UIBlindspot",
    "UIColdPathWork",
    "UIImplementationJourneyRun",
    "UIImplementationStepEvidence",
    "UIImplementationValidation",
    "UIImplementationValidationReport",
    "UIInteractionModel",
    "UIInteractionModelReport",
    "UIJourneyCoverage",
    "UIJourneyCoverageReport",
    "UIJourneyEntryPoint",
    "MATLABBaselineCallbackGate",
    "MATLABBaselineCallbackGateReport",
    "MATLABCallbackSemantics",
    "MATLAB_CALLBACK_KINDS",
    "MATLAB_CALLBACK_REQUIRED_BRANCHES",
    "MATLAB_NO_CALLBACK_DISPOSITIONS",
    "FUNCTIONAL_CHAIN_EVIDENCE_KINDS",
    "OBSERVED_UI_ACTIONABLE_KINDS",
    "OBSERVED_UI_ITEM_KINDS",
    "UI_ACTUAL_ACTIONABLE_ROLES",
    "UI_ACTUAL_NON_ACTIONABLE_ROLES",
    "UIAffordanceContract",
    "UIActionGrammar",
    "UI_AFFORDANCE_MISMATCH_DISPOSITIONS",
    "UIDialogWindowContract",
    "UI_DIALOG_TYPES",
    "UIHumanOperabilityAssessment",
    "UIHumanOperabilityReport",
    "UIHumanWalkthroughScenario",
    "UIHumanWalkthroughStep",
    "UIKeyboardFocusContract",
    "UI_PERCEIVED_ACTIONABLE_ROLES",
    "UIRegionRecommendation",
    "UIRegionSemanticMap",
    "UI_REGION_ROLES",
    "UIRenderEvidence",
    "UIRenderEvidenceReport",
    "UIRenderEvidenceSet",
    "UIResponsivenessContract",
    "UIResponsivenessContractReport",
    "UIStableRegionRule",
    "UIStateNode",
    "UIStructureDerivation",
    "UIStructureDerivationReport",
    "UITextElement",
    "UITextHierarchyBlueprint",
    "UITextHierarchyReport",
    "UITypographyToken",
    "UITerminalActionAllowance",
    "UITransition",
    "UIUserTaskCoverageLedger",
    "UIUserTaskFrame",
    "UIVisibleSurface",
    "UIVisibleSurfaceItem",
    "UIVisibleSurfaceReport",
    "UI_HUMAN_OPERABILITY_EVIDENCE_KINDS",
    "SUPPORTED_UI_EVIDENCE_KINDS",
    "review_matlab_baseline_callback_gate",
    "review_ui_control_functional_chains",
    "review_ui_geometry_layout_evidence",
    "review_ui_human_operability",
    "review_ui_implementation_validation",
    "review_ui_interaction_model",
    "review_ui_journey_coverage",
    "review_ui_observed_surface_inventory",
    "review_ui_render_evidence",
    "review_ui_responsiveness_contract",
    "review_ui_structure_derivation",
    "review_ui_text_hierarchy",
    "review_ui_visible_surface",
]
