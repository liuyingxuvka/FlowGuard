"""FlowGuard model for AI entry surface reduction.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: keep routine AI entry points route-first and compact while preserving
full/deep route surfaces and gate/test/replay evidence for escalation.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/ai_entry_surface_reduction/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class EntryAction:
    action_type: str


@dataclass(frozen=True)
class EntryOutput:
    status: str


@dataclass(frozen=True)
class EntryState:
    openspec_ready: bool = False
    starter_api_available: bool = False
    starter_api_compact: bool = False
    advanced_api_available: bool = False
    compact_templates_default: bool = False
    full_templates_available: bool = False
    safety_evidence_preserved: bool = False
    docs_use_starter_first: bool = False
    field_inventory_tiered: bool = False
    validations_current: bool = False
    install_shadow_git_synced: bool = False
    done_claim: str = "none"

    def ready_for_done(self) -> bool:
        return (
            self.openspec_ready
            and self.starter_api_available
            and self.starter_api_compact
            and self.advanced_api_available
            and self.compact_templates_default
            and self.full_templates_available
            and self.safety_evidence_preserved
            and self.docs_use_starter_first
            and self.field_inventory_tiered
            and self.validations_current
            and self.install_shadow_git_synced
        )


class CorrectAIEntryReduction:
    name = "CorrectAIEntryReduction"
    reads = (
        "openspec_ready",
        "starter_api_available",
        "starter_api_compact",
        "advanced_api_available",
        "compact_templates_default",
        "full_templates_available",
        "safety_evidence_preserved",
        "docs_use_starter_first",
        "field_inventory_tiered",
        "validations_current",
        "install_shadow_git_synced",
        "done_claim",
    )
    writes = reads
    accepted_input_type = EntryAction
    input_description = "AI entry surface reduction lifecycle action"
    output_description = "AI entry surface reduction state or claim decision"
    idempotency = "Completion requires starter API, compact defaults, full escalation, safety evidence, validation, install, shadow, and git evidence."

    def apply(self, input_obj: EntryAction, state: EntryState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "prepare_openspec":
            yield FunctionResult(
                EntryOutput("openspec_ready"),
                replace(state, openspec_ready=True),
                label="openspec_ready",
            )
        elif action == "add_api_layers":
            yield FunctionResult(
                EntryOutput("api_layers_added"),
                replace(
                    state,
                    starter_api_available=True,
                    starter_api_compact=True,
                    advanced_api_available=True,
                ),
                label="api_layers_added",
            )
        elif action == "add_compact_templates":
            yield FunctionResult(
                EntryOutput("templates_layered"),
                replace(
                    state,
                    compact_templates_default=True,
                    full_templates_available=True,
                    safety_evidence_preserved=True,
                ),
                label="templates_layered",
            )
        elif action == "update_guidance_and_inventory":
            yield FunctionResult(
                EntryOutput("guidance_and_inventory_updated"),
                replace(state, docs_use_starter_first=True, field_inventory_tiered=True),
                label="guidance_and_inventory_updated",
            )
        elif action == "run_validations":
            valid = (
                state.openspec_ready
                and state.starter_api_available
                and state.starter_api_compact
                and state.advanced_api_available
                and state.compact_templates_default
                and state.full_templates_available
                and state.safety_evidence_preserved
                and state.docs_use_starter_first
                and state.field_inventory_tiered
            )
            yield FunctionResult(
                EntryOutput("validations_passed" if valid else "validations_blocked"),
                replace(state, validations_current=valid),
                label="validations_passed" if valid else "validations_blocked",
            )
        elif action == "sync_install_shadow_git":
            synced = state.validations_current
            yield FunctionResult(
                EntryOutput("local_surfaces_synced" if synced else "sync_blocked"),
                replace(state, install_shadow_git_synced=synced),
                label="local_surfaces_synced" if synced else "sync_blocked",
            )
        elif action == "claim_done":
            accepted = state.ready_for_done()
            yield FunctionResult(
                EntryOutput("done_accepted" if accepted else "done_rejected"),
                replace(state, done_claim="accepted" if accepted else "rejected"),
                label="done_accepted" if accepted else "done_rejected",
            )


class BrokenDefaultUsesFullApi(CorrectAIEntryReduction):
    name = "BrokenDefaultUsesFullApi"
    idempotency = "Broken variant exposes advanced API but no compact starter."

    def apply(self, input_obj: EntryAction, state: EntryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_api_layers":
            yield FunctionResult(
                EntryOutput("full_api_exposed_first"),
                replace(
                    state,
                    starter_api_available=False,
                    starter_api_compact=False,
                    advanced_api_available=True,
                ),
                label="full_api_exposed_first",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenCompactDropsSafetyEvidence(CorrectAIEntryReduction):
    name = "BrokenCompactDropsSafetyEvidence"
    idempotency = "Broken variant makes compact templates but drops gate/test/replay evidence."

    def apply(self, input_obj: EntryAction, state: EntryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_compact_templates":
            yield FunctionResult(
                EntryOutput("templates_compact_but_unsafe"),
                replace(
                    state,
                    compact_templates_default=True,
                    full_templates_available=True,
                    safety_evidence_preserved=False,
                ),
                label="templates_compact_but_unsafe",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenFullPathMissing(CorrectAIEntryReduction):
    name = "BrokenFullPathMissing"
    idempotency = "Broken variant defaults to compact but hides the deep route scaffold."

    def apply(self, input_obj: EntryAction, state: EntryState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_compact_templates":
            yield FunctionResult(
                EntryOutput("compact_only_no_full_path"),
                replace(
                    state,
                    compact_templates_default=True,
                    full_templates_available=False,
                    safety_evidence_preserved=True,
                ),
                label="compact_only_no_full_path",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, EntryOutput) and current_output.status.startswith("done_")


def no_done_without_layered_entry(state: EntryState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "done accepted before starter API, compact defaults, full escalation, safety evidence, validation, install, shadow, and git evidence aligned"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_layered_entry",
        "AI entry reduction completion requires compact starter surfaces, full escalation paths, preserved safety evidence, and current sync evidence.",
        no_done_without_layered_entry,
    ),
)

EXTERNAL_INPUTS = (
    EntryAction("prepare_openspec"),
    EntryAction("add_api_layers"),
    EntryAction("add_compact_templates"),
    EntryAction("update_guidance_and_inventory"),
    EntryAction("run_validations"),
    EntryAction("sync_install_shadow_git"),
    EntryAction("claim_done"),
)

MAX_SEQUENCE_LENGTH = 7


def initial_state() -> EntryState:
    return EntryState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectAIEntryReduction(),), name="ai_entry_surface_reduction_correct")


def build_broken_full_api_workflow() -> Workflow:
    return Workflow((BrokenDefaultUsesFullApi(),), name="ai_entry_surface_reduction_full_api_first")


def build_broken_unsafe_template_workflow() -> Workflow:
    return Workflow((BrokenCompactDropsSafetyEvidence(),), name="ai_entry_surface_reduction_unsafe_compact")


def build_broken_full_path_missing_workflow() -> Workflow:
    return Workflow((BrokenFullPathMissing(),), name="ai_entry_surface_reduction_no_full_path")
