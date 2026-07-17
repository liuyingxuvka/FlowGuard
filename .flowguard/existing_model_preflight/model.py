"""FlowGuard model for existing-model preflight routing.

Purpose:
Models the companion preflight before Codex discusses, proposes, or modifies an
existing modeled system.

Guards against:
- choosing a technical route before existing FlowGuard models are searched;
- using a light discussion note for implementation or proposal work that needs
  full preflight evidence;
- allowing duplicate state, side-effect, entrypoint, or responsibility
  ownership without a reuse/new-boundary rationale.

Use before editing:
global FlowGuard routing, Codex skill prompts, model-grounding helper APIs, or
skill trigger tests for existing-system work.

Run:
python .flowguard/existing_model_preflight/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.behavior_plane import BCL_BEHAVIOR_PLANES, BCL_PLANE_DEVELOPMENT_PROCESS


@dataclass(frozen=True)
class ChangeIdea:
    task_id: str
    existing_modeled_system: bool
    trivial: bool = False
    action_class: str = "discussion"
    model_found: bool = True
    duplicate_risk: bool = False
    duplicate_risk_handled: bool = True
    new_boundary_rationale: bool = False
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    expected_surface_ids: tuple[str, ...] = ()
    materialized_surface_ids: tuple[str, ...] = ()
    scoped_surface_ids: tuple[str, ...] = ()
    surface_inventory_current: bool = True
    behavior_plane: str = BCL_PLANE_DEVELOPMENT_PROCESS
    commitment_lookup_performed: bool = True
    related_plane_hit_promoted: bool = False
    spec_provider_context_present: bool = False
    spec_provider_context_current: bool = True
    spec_reconciliation_current: bool = True


@dataclass(frozen=True)
class ClassifiedNeed:
    task_id: str
    required_level: str
    downstream_route: str
    existing_modeled_system: bool
    duplicate_risk: bool
    duplicate_risk_handled: bool
    new_boundary_rationale: bool
    business_intent_id: str
    behavior_commitment_id: str
    primary_path_id: str
    expected_surface_ids: tuple[str, ...]
    materialized_surface_ids: tuple[str, ...]
    scoped_surface_ids: tuple[str, ...]
    surface_inventory_current: bool
    behavior_plane: str
    commitment_lookup_performed: bool
    related_plane_hit_promoted: bool
    spec_provider_context_present: bool = False
    spec_provider_context_current: bool = True
    spec_reconciliation_current: bool = True


@dataclass(frozen=True)
class GroundedNeed:
    task_id: str
    level: str
    downstream_route: str
    duplicate_risk: bool
    duplicate_risk_handled: bool
    new_boundary_rationale: bool
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    behavior_plane: str = BCL_PLANE_DEVELOPMENT_PROCESS


@dataclass(frozen=True)
class SkippedNeed:
    task_id: str
    reason: str
    downstream_route: str


@dataclass(frozen=True)
class BlockedNeed:
    task_id: str
    reason: str


@dataclass(frozen=True)
class RouteSelected:
    task_id: str
    route: str


@dataclass(frozen=True)
class State:
    classified: tuple[str, ...] = ()
    searched: tuple[str, ...] = ()
    light_grounded: tuple[str, ...] = ()
    full_grounded: tuple[str, ...] = ()
    no_model_found: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    route_selected: tuple[str, ...] = ()
    full_required: tuple[str, ...] = ()
    duplicate_risk: tuple[str, ...] = ()
    duplicate_risk_handled: tuple[str, ...] = ()
    new_boundary_rationale: tuple[str, ...] = ()
    surface_inventory_required: tuple[str, ...] = ()
    surface_inventory_complete: tuple[str, ...] = ()
    stable_authority_required: tuple[str, ...] = ()
    stable_authority_bound: tuple[str, ...] = ()
    lookup_required: tuple[str, ...] = ()
    lookup_complete: tuple[str, ...] = ()
    unsafe_related_plane_promoted: tuple[str, ...] = ()
    spec_provider_context_required: tuple[str, ...] = ()
    spec_provider_context_current: tuple[str, ...] = ()


FULL_ACTIONS = {"implementation", "proposal", "restructure", "high_risk_change"}


def _add_once(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else values + (value,)


def _route_for(action_class: str) -> str:
    if action_class == "bugfix":
        return "model_miss_review"
    if action_class == "ui_change":
        return "ui_flow_structure"
    if action_class == "restructure":
        return "structure_mesh_maintenance"
    if action_class == "implementation":
        return "development_process_flow"
    return "core_modeling"


class ClassifyNeed:
    name = "ClassifyNeed"
    reads = ()
    writes = ("classified", "full_required", "skipped", "lookup_required")
    accepted_input_type = ChangeIdea
    input_description = "existing-system change idea"
    output_description = "ClassifiedNeed or SkippedNeed"

    def apply(self, input_obj: ChangeIdea, state: State) -> Iterable[FunctionResult]:
        if input_obj.trivial or not input_obj.existing_modeled_system:
            skipped = SkippedNeed(input_obj.task_id, "skip_with_reason", _route_for(input_obj.action_class))
            yield FunctionResult(
                skipped,
                replace(state, skipped=_add_once(state.skipped, input_obj.task_id)),
                label="preflight_skipped_with_reason",
            )
            return
        level = "full" if input_obj.action_class in FULL_ACTIONS else "light"
        new_state = replace(
            state,
            classified=_add_once(state.classified, input_obj.task_id),
            full_required=_add_once(state.full_required, input_obj.task_id)
            if level == "full"
            else state.full_required,
            duplicate_risk=_add_once(state.duplicate_risk, input_obj.task_id)
            if input_obj.duplicate_risk
            else state.duplicate_risk,
            duplicate_risk_handled=_add_once(state.duplicate_risk_handled, input_obj.task_id)
            if input_obj.duplicate_risk_handled
            else state.duplicate_risk_handled,
            new_boundary_rationale=_add_once(state.new_boundary_rationale, input_obj.task_id)
            if input_obj.new_boundary_rationale
            else state.new_boundary_rationale,
            surface_inventory_required=_add_once(state.surface_inventory_required, input_obj.task_id)
            if input_obj.expected_surface_ids
            else state.surface_inventory_required,
            stable_authority_required=_add_once(state.stable_authority_required, input_obj.task_id)
            if input_obj.expected_surface_ids
            else state.stable_authority_required,
            lookup_required=_add_once(state.lookup_required, input_obj.task_id),
            spec_provider_context_required=_add_once(state.spec_provider_context_required, input_obj.task_id)
            if input_obj.spec_provider_context_present
            else state.spec_provider_context_required,
        )
        yield FunctionResult(
            ClassifiedNeed(
                input_obj.task_id,
                level,
                _route_for(input_obj.action_class),
                input_obj.existing_modeled_system,
                input_obj.duplicate_risk,
                input_obj.duplicate_risk_handled,
                input_obj.new_boundary_rationale,
                input_obj.business_intent_id,
                input_obj.behavior_commitment_id,
                input_obj.primary_path_id,
                input_obj.expected_surface_ids,
                input_obj.materialized_surface_ids,
                input_obj.scoped_surface_ids,
                input_obj.surface_inventory_current,
                input_obj.behavior_plane,
                input_obj.commitment_lookup_performed,
                input_obj.related_plane_hit_promoted,
                input_obj.spec_provider_context_present,
                input_obj.spec_provider_context_current,
                input_obj.spec_reconciliation_current,
            ),
            new_state,
            label=f"classified_{level}_preflight",
        )


class SearchExistingModels:
    name = "SearchExistingModels"
    reads = ("classified",)
    writes = ("searched", "light_grounded", "full_grounded", "no_model_found", "blocked", "lookup_complete")
    accepted_input_type = (ClassifiedNeed, SkippedNeed)
    input_description = "ClassifiedNeed or SkippedNeed"
    output_description = "GroundedNeed or BlockedNeed"

    def apply(self, input_obj: ClassifiedNeed | SkippedNeed, state: State) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SkippedNeed):
            yield FunctionResult(input_obj, state, label="preflight_skip_carried_forward")
            return
        if input_obj.behavior_plane not in BCL_BEHAVIOR_PLANES or not input_obj.commitment_lookup_performed:
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "plane_first_commitment_lookup_missing"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_plane_first_lookup_missing",
            )
            return
        if input_obj.related_plane_hit_promoted:
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "related_plane_context_promoted_to_primary"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_related_plane_promotion",
            )
            return
        if input_obj.spec_provider_context_present and not (
            input_obj.spec_provider_context_current and input_obj.spec_reconciliation_current
        ):
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "spec_provider_context_stale_or_unmapped"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_spec_provider_context_stale",
            )
            return
        if input_obj.duplicate_risk and not (
            input_obj.duplicate_risk_handled or input_obj.new_boundary_rationale
        ):
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "duplicate_risk_unhandled"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_duplicate_risk",
            )
            return

        missing_surfaces = set(input_obj.expected_surface_ids) - set(input_obj.materialized_surface_ids) - set(input_obj.scoped_surface_ids)
        if missing_surfaces:
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "same_intent_surface_inventory_incomplete"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_surface_inventory_incomplete",
            )
            return
        if input_obj.expected_surface_ids and not input_obj.surface_inventory_current:
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "same_intent_surface_inventory_stale"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_surface_inventory_stale",
            )
            return
        if input_obj.expected_surface_ids and not (
            input_obj.business_intent_id and input_obj.behavior_commitment_id and input_obj.primary_path_id
        ):
            yield FunctionResult(
                BlockedNeed(input_obj.task_id, "stable_authority_identity_missing"),
                replace(state, blocked=_add_once(state.blocked, input_obj.task_id)),
                label="blocked_stable_authority_identity_missing",
            )
            return

        grounded_state = replace(
            state,
            searched=_add_once(state.searched, input_obj.task_id),
            no_model_found=_add_once(state.no_model_found, input_obj.task_id)
            if not input_obj.existing_modeled_system
            else state.no_model_found,
            surface_inventory_complete=_add_once(state.surface_inventory_complete, input_obj.task_id)
            if input_obj.expected_surface_ids
            else state.surface_inventory_complete,
            stable_authority_bound=_add_once(state.stable_authority_bound, input_obj.task_id)
            if input_obj.expected_surface_ids
            else state.stable_authority_bound,
            lookup_complete=_add_once(state.lookup_complete, input_obj.task_id),
            spec_provider_context_current=_add_once(state.spec_provider_context_current, input_obj.task_id)
            if input_obj.spec_provider_context_present
            else state.spec_provider_context_current,
        )
        if input_obj.required_level == "full":
            grounded_state = replace(
                grounded_state,
                full_grounded=_add_once(grounded_state.full_grounded, input_obj.task_id),
            )
            label = "full_existing_model_preflight"
        else:
            grounded_state = replace(
                grounded_state,
                light_grounded=_add_once(grounded_state.light_grounded, input_obj.task_id),
            )
            label = "light_existing_model_grounding"
        yield FunctionResult(
            GroundedNeed(
                input_obj.task_id,
                input_obj.required_level,
                input_obj.downstream_route,
                input_obj.duplicate_risk,
                input_obj.duplicate_risk_handled,
                input_obj.new_boundary_rationale,
                input_obj.business_intent_id,
                input_obj.behavior_commitment_id,
                input_obj.primary_path_id,
                input_obj.behavior_plane,
            ),
            grounded_state,
            label=label,
        )


class SelectDownstreamRoute:
    name = "SelectDownstreamRoute"
    reads = ("light_grounded", "full_grounded", "skipped")
    writes = ("route_selected",)
    accepted_input_type = (GroundedNeed, SkippedNeed)
    input_description = "GroundedNeed or SkippedNeed"
    output_description = "RouteSelected"

    def apply(self, input_obj: GroundedNeed | SkippedNeed, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            RouteSelected(input_obj.task_id, input_obj.downstream_route),
            replace(state, route_selected=_add_once(state.route_selected, input_obj.task_id)),
            label="downstream_route_selected",
        )


class BrokenBypassSearch:
    name = "BrokenBypassSearch"
    reads = ("classified",)
    writes = ("route_selected",)
    accepted_input_type = (ClassifiedNeed, SkippedNeed)

    def apply(self, input_obj: ClassifiedNeed | SkippedNeed, state: State) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SkippedNeed):
            yield FunctionResult(input_obj, state, label="preflight_skip_carried_forward")
            return
        yield FunctionResult(
            RouteSelected(input_obj.task_id, input_obj.downstream_route),
            replace(state, route_selected=_add_once(state.route_selected, input_obj.task_id)),
            label="broken_route_without_model_grounding",
        )


class BrokenLightForFull:
    name = "BrokenLightForFull"
    reads = ("classified",)
    writes = ("searched", "light_grounded")
    accepted_input_type = (ClassifiedNeed, SkippedNeed)

    def apply(self, input_obj: ClassifiedNeed | SkippedNeed, state: State) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SkippedNeed):
            yield FunctionResult(input_obj, state, label="preflight_skip_carried_forward")
            return
        yield FunctionResult(
            GroundedNeed(
                input_obj.task_id,
                "light",
                input_obj.downstream_route,
                input_obj.duplicate_risk,
                input_obj.duplicate_risk_handled,
                input_obj.new_boundary_rationale,
                input_obj.business_intent_id,
                input_obj.behavior_commitment_id,
                input_obj.primary_path_id,
                input_obj.behavior_plane,
            ),
            replace(
                state,
                searched=_add_once(state.searched, input_obj.task_id),
                light_grounded=_add_once(state.light_grounded, input_obj.task_id),
            ),
            label="broken_light_preflight_for_full_work",
        )


class BrokenIgnoresSurfaceInventory:
    name = "BrokenIgnoresSurfaceInventory"
    reads = ("classified",)
    writes = ("searched", "full_grounded")
    accepted_input_type = (ClassifiedNeed, SkippedNeed)

    def apply(self, input_obj: ClassifiedNeed | SkippedNeed, state: State) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SkippedNeed):
            yield FunctionResult(input_obj, state, label="preflight_skip_carried_forward")
            return
        yield FunctionResult(
            GroundedNeed(
                input_obj.task_id,
                input_obj.required_level,
                input_obj.downstream_route,
                input_obj.duplicate_risk,
                input_obj.duplicate_risk_handled,
                input_obj.new_boundary_rationale,
                input_obj.business_intent_id,
                input_obj.behavior_commitment_id,
                input_obj.primary_path_id,
                input_obj.behavior_plane,
            ),
            replace(
                state,
                searched=_add_once(state.searched, input_obj.task_id),
                full_grounded=_add_once(state.full_grounded, input_obj.task_id),
            ),
            label="broken_grounded_from_caller_selected_surface_subset",
        )


class BrokenPromotesRelatedPlane(SearchExistingModels):
    name = "BrokenPromotesRelatedPlane"

    def apply(self, input_obj: ClassifiedNeed | SkippedNeed, state: State) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SkippedNeed):
            yield FunctionResult(input_obj, state, label="preflight_skip_carried_forward")
            return
        yield FunctionResult(
            GroundedNeed(
                input_obj.task_id,
                input_obj.required_level,
                input_obj.downstream_route,
                input_obj.duplicate_risk,
                input_obj.duplicate_risk_handled,
                input_obj.new_boundary_rationale,
                input_obj.business_intent_id,
                input_obj.behavior_commitment_id,
                input_obj.primary_path_id,
                input_obj.behavior_plane,
            ),
            replace(
                state,
                searched=_add_once(state.searched, input_obj.task_id),
                full_grounded=_add_once(state.full_grounded, input_obj.task_id),
                unsafe_related_plane_promoted=_add_once(
                    state.unsafe_related_plane_promoted, input_obj.task_id
                ),
            ),
            label="broken_related_plane_promoted_to_primary",
        )


def terminal_predicate(current_output, state: State, trace) -> bool:
    del state, trace
    return isinstance(current_output, (RouteSelected, BlockedNeed))


def no_route_without_grounding(state: State, trace) -> InvariantResult:
    del trace
    grounded = set(state.light_grounded) | set(state.full_grounded) | set(state.skipped)
    bad = tuple(sorted(set(state.route_selected) - grounded))
    if bad:
        return InvariantResult.fail(f"route selected without existing-model grounding: {bad!r}")
    return InvariantResult.pass_()


def full_work_requires_full_preflight(state: State, trace) -> InvariantResult:
    del trace
    bad = tuple(sorted((set(state.route_selected) & set(state.full_required)) - set(state.full_grounded)))
    if bad:
        return InvariantResult.fail(f"full preflight missing before full-work route: {bad!r}")
    return InvariantResult.pass_()


def duplicate_risk_requires_resolution(state: State, trace) -> InvariantResult:
    del trace
    resolved = set(state.duplicate_risk_handled) | set(state.new_boundary_rationale) | set(state.blocked)
    bad = tuple(sorted((set(state.route_selected) & set(state.duplicate_risk)) - resolved))
    if bad:
        return InvariantResult.fail(f"duplicate ownership risk routed without resolution: {bad!r}")
    return InvariantResult.pass_()


def same_intent_inventory_requires_complete(state: State, trace) -> InvariantResult:
    del trace
    bad = tuple(sorted((set(state.route_selected) & set(state.surface_inventory_required)) - set(state.surface_inventory_complete)))
    if bad:
        return InvariantResult.fail(f"same-intent route selected without complete affected surface inventory: {bad!r}")
    return InvariantResult.pass_()


def same_intent_reuse_requires_stable_authority(state: State, trace) -> InvariantResult:
    del trace
    bad = tuple(sorted((set(state.route_selected) & set(state.stable_authority_required)) - set(state.stable_authority_bound)))
    if bad:
        return InvariantResult.fail(f"same-intent route selected without stable intent/commitment/path identity: {bad!r}")
    return InvariantResult.pass_()


def route_requires_plane_first_commitment_lookup(state: State, trace) -> InvariantResult:
    del trace
    bad = tuple(
        sorted((set(state.route_selected) & set(state.lookup_required)) - set(state.lookup_complete))
    )
    if bad:
        return InvariantResult.fail(f"route selected without plane-first commitment lookup: {bad!r}")
    if state.unsafe_related_plane_promoted:
        return InvariantResult.fail(
            f"related-plane context promoted to primary ownership: {state.unsafe_related_plane_promoted!r}"
        )
    return InvariantResult.pass_()


def spec_provider_context_requires_current_reconciliation(state: State, trace) -> InvariantResult:
    del trace
    bad = tuple(
        sorted(
            (set(state.route_selected) & set(state.spec_provider_context_required))
            - set(state.spec_provider_context_current)
        )
    )
    if bad:
        return InvariantResult.fail(
            f"route selected from stale or unmapped spec provider context: {bad!r}"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_route_without_grounding",
        "Existing-system work cannot select a downstream route before model grounding or explicit skip.",
        no_route_without_grounding,
    ),
    Invariant(
        "full_work_requires_full_preflight",
        "Implementation/proposal/restructure work needs full preflight before route selection.",
        full_work_requires_full_preflight,
    ),
    Invariant(
        "duplicate_risk_requires_resolution",
        "Duplicate ownership risk must be resolved or blocked before route selection.",
        duplicate_risk_requires_resolution,
    ),
    Invariant(
        "same_intent_inventory_requires_complete",
        "Affected same-intent surfaces must be complete or scoped before route selection.",
        same_intent_inventory_requires_complete,
    ),
    Invariant(
        "same_intent_reuse_requires_stable_authority",
        "Same-intent reuse must preserve stable business-intent, commitment, and primary-path ids.",
        same_intent_reuse_requires_stable_authority,
    ),
    Invariant(
        "route_requires_plane_first_commitment_lookup",
        "Non-trivial preflight selects primary ownership only after same-plane lookup.",
        route_requires_plane_first_commitment_lookup,
    ),
    Invariant(
        "spec_provider_context_requires_current_reconciliation",
        "Provider task context cannot support routing until current bidirectional reconciliation is preserved.",
        spec_provider_context_requires_current_reconciliation,
    ),
)


EXTERNAL_INPUTS = (
    ChangeIdea("discuss-router", True, action_class="discussion"),
    ChangeIdea("implement-router", True, action_class="implementation"),
    ChangeIdea("fix-runtime-miss", True, action_class="bugfix"),
    ChangeIdea("trivial-typo", True, trivial=True, action_class="discussion"),
    ChangeIdea(
        "duplicate-state",
        True,
        action_class="implementation",
        duplicate_risk=True,
        duplicate_risk_handled=True,
    ),
    ChangeIdea(
        "new-boundary",
        True,
        action_class="restructure",
        duplicate_risk=True,
        duplicate_risk_handled=False,
        new_boundary_rationale=True,
    ),
    ChangeIdea(
        "unhandled-duplicate",
        True,
        action_class="implementation",
        duplicate_risk=True,
        duplicate_risk_handled=False,
    ),
    ChangeIdea(
        "same-intent-reuse",
        True,
        action_class="implementation",
        business_intent_id="intent:submit-order",
        behavior_commitment_id="commitment:submit-order",
        primary_path_id="path:submit-order",
        expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
        materialized_surface_ids=("surface:ui-submit", "surface:api-submit"),
    ),
    ChangeIdea(
        "omitted-same-intent-surface",
        True,
        action_class="implementation",
        business_intent_id="intent:submit-order",
        behavior_commitment_id="commitment:submit-order",
        primary_path_id="path:submit-order",
        expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
        materialized_surface_ids=("surface:ui-submit",),
    ),
    ChangeIdea(
        "wrong-plane-promotion",
        True,
        action_class="implementation",
        behavior_plane="agent_operation",
        related_plane_hit_promoted=True,
    ),
    ChangeIdea(
        "current-provider-context",
        True,
        action_class="implementation",
        spec_provider_context_present=True,
    ),
    ChangeIdea(
        "stale-provider-context",
        True,
        action_class="implementation",
        spec_provider_context_present=True,
        spec_provider_context_current=False,
        spec_reconciliation_current=False,
    ),
)


def initial_state() -> State:
    return State()


def build_workflow(*, search_block=None) -> Workflow:
    return Workflow(
        (
            ClassifyNeed(),
            search_block or SearchExistingModels(),
            SelectDownstreamRoute(),
        ),
        name="existing_model_preflight",
    )


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-existing-model-preflight",
        route_id="existing_model_preflight",
        owner_id="existing_model_preflight",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Recall the existing same-plane commitment and owner model before non-trivial work.",
        claim_boundary="This projection binds preflight recall and route selection only; it does not execute the selected model or prove downstream closure.",
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "BrokenBypassSearch",
    "BrokenIgnoresSurfaceInventory",
    "BrokenLightForFull",
    "BrokenPromotesRelatedPlane",
    "ChangeIdea",
    "State",
    "build_workflow",
    "export_contract_model",
    "initial_state",
    "terminal_predicate",
]

MAX_SEQUENCE_LENGTH = 2
