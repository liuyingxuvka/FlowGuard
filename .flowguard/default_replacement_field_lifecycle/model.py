"""FlowGuard model for default replacement and field lifecycle closure.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: ensure replacement work cannot claim full completion until field
inventory, behavior projection, minimal field evidence route refs, old
path/field disposition, model-code-test binding, same-class bug repair
evidence, freshness, and closure evidence are current.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/default_replacement_field_lifecycle/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class LifecycleAction:
    action_type: str


@dataclass(frozen=True)
class LifecycleOutput:
    status: str


@dataclass(frozen=True)
class LifecycleState:
    fields_discovered: bool = False
    all_fields_accounted: bool = False
    ui_reader_fields_handed_to_content_admission: bool = False
    non_ui_fields_kept_out_of_ui_plan: bool = False
    behavior_fields_projected: bool = False
    field_evidence_route_bound: bool = False
    old_paths_disposed: bool = False
    old_fields_disposed: bool = False
    model_code_test_aligned: bool = False
    observed_bug_recorded: bool = False
    same_class_bug_case_added: bool = False
    field_root_cause_backpropagated: bool = False
    freshness_current: bool = False
    closure_review_passed: bool = False
    final_claim: str = "none"

    def ready_for_full_claim(self) -> bool:
        return (
            self.fields_discovered
            and self.all_fields_accounted
            and self.ui_reader_fields_handed_to_content_admission
            and self.non_ui_fields_kept_out_of_ui_plan
            and self.behavior_fields_projected
            and self.field_evidence_route_bound
            and self.old_paths_disposed
            and self.old_fields_disposed
            and self.model_code_test_aligned
            and self.observed_bug_recorded
            and self.same_class_bug_case_added
            and self.field_root_cause_backpropagated
            and self.freshness_current
            and self.closure_review_passed
        )


class CorrectReplacementFieldLifecycle:
    name = "CorrectReplacementFieldLifecycle"
    reads = (
        "fields_discovered",
        "all_fields_accounted",
        "ui_reader_fields_handed_to_content_admission",
        "non_ui_fields_kept_out_of_ui_plan",
        "behavior_fields_projected",
        "field_evidence_route_bound",
        "old_paths_disposed",
        "old_fields_disposed",
        "model_code_test_aligned",
        "observed_bug_recorded",
        "same_class_bug_case_added",
        "field_root_cause_backpropagated",
        "freshness_current",
        "closure_review_passed",
        "final_claim",
    )
    writes = reads
    accepted_input_type = LifecycleAction
    input_description = "field lifecycle and replacement closure action"
    output_description = "replacement lifecycle state or final claim"
    idempotency = (
        "Full claims require field inventory, behavior projection, old path and "
        "old field disposition, minimal field evidence route refs, "
        "model-code-test alignment, bug repair closure, freshness, and "
        "closure review."
    )

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "inventory_fields":
            yield FunctionResult(
                LifecycleOutput("fields_accounted"),
                replace(
                    state,
                    fields_discovered=True,
                    all_fields_accounted=True,
                    final_claim="none",
                ),
                label="fields_accounted",
            )
        elif action == "handoff_ui_reader_fields":
            if not state.all_fields_accounted:
                yield FunctionResult(
                    LifecycleOutput("ui_reader_handoff_rejected"),
                    state,
                    label="ui_reader_handoff_rejected",
                )
                return
            yield FunctionResult(
                LifecycleOutput("ui_reader_fields_handed_to_content_admission"),
                replace(
                    state,
                    ui_reader_fields_handed_to_content_admission=True,
                    non_ui_fields_kept_out_of_ui_plan=True,
                    final_claim="none",
                ),
                label="ui_reader_fields_handed_to_content_admission",
            )
        elif action == "project_and_dispose":
            yield FunctionResult(
                LifecycleOutput("field_projection_and_disposition_done"),
                replace(
                    state,
                    behavior_fields_projected=True,
                    field_evidence_route_bound=True,
                    old_paths_disposed=True,
                    old_fields_disposed=True,
                    final_claim="none",
                ),
                label="field_projection_and_disposition_done",
            )
        elif action == "align_and_repair":
            yield FunctionResult(
                LifecycleOutput("model_code_test_and_bug_repair_done"),
                replace(
                    state,
                    model_code_test_aligned=True,
                    observed_bug_recorded=True,
                    same_class_bug_case_added=True,
                    field_root_cause_backpropagated=True,
                    final_claim="none",
                ),
                label="model_code_test_and_bug_repair_done",
            )
        elif action == "refresh_and_close":
            yield FunctionResult(
                LifecycleOutput("freshness_and_closure_current"),
                replace(
                    state,
                    freshness_current=True,
                    closure_review_passed=True,
                    final_claim="none",
                ),
                label="freshness_and_closure_current",
            )
        elif action == "claim_full_done":
            claim = "full" if state.ready_for_full_claim() else "blocked"
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )


class BrokenMissingFieldAccounting(CorrectReplacementFieldLifecycle):
    name = "BrokenMissingFieldAccounting"
    idempotency = "Broken variant lets replacement completion skip all-field accounting."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "inventory_fields":
            yield FunctionResult(
                LifecycleOutput("fields_discovered_without_full_accounting"),
                replace(state, fields_discovered=True, all_fields_accounted=False, final_claim="none"),
                label="fields_discovered_without_full_accounting",
            )
            return
        if input_obj.action_type == "claim_full_done":
            claim = "full" if state.fields_discovered and state.behavior_fields_projected else "blocked"
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingProjection(CorrectReplacementFieldLifecycle):
    name = "BrokenMissingProjection"
    idempotency = "Broken variant treats field inventory as enough without behavior projection."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_done":
            claim = "full" if state.fields_discovered and state.all_fields_accounted else "blocked"
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingUIReaderHandoff(CorrectReplacementFieldLifecycle):
    name = "BrokenMissingUIReaderHandoff"
    idempotency = "Broken variant claims full closure without handing ordinary-UI reader fields to content admission."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "handoff_ui_reader_fields":
            yield FunctionResult(
                LifecycleOutput("ui_reader_handoff_skipped"),
                replace(
                    state,
                    ui_reader_fields_handed_to_content_admission=False,
                    non_ui_fields_kept_out_of_ui_plan=True,
                    final_claim="none",
                ),
                label="ui_reader_handoff_skipped",
            )
            return
        if input_obj.action_type == "claim_full_done":
            legacy_ready = (
                state.fields_discovered
                and state.all_fields_accounted
                and state.behavior_fields_projected
                and state.field_evidence_route_bound
                and state.old_paths_disposed
                and state.old_fields_disposed
                and state.model_code_test_aligned
                and state.observed_bug_recorded
                and state.same_class_bug_case_added
                and state.field_root_cause_backpropagated
                and state.freshness_current
                and state.closure_review_passed
            )
            claim = "full" if legacy_ready else "blocked"
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMissingFieldEvidenceRoute(CorrectReplacementFieldLifecycle):
    name = "BrokenMissingFieldEvidenceRoute"
    idempotency = "Broken variant treats projection as enough without gate/test/replay route refs."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "project_and_dispose":
            yield FunctionResult(
                LifecycleOutput("field_projection_without_route_refs"),
                replace(
                    state,
                    behavior_fields_projected=True,
                    field_evidence_route_bound=False,
                    old_paths_disposed=True,
                    old_fields_disposed=True,
                    final_claim="none",
                ),
                label="field_projection_without_route_refs",
            )
            return
        if input_obj.action_type == "claim_full_done":
            claim = (
                "full"
                if state.all_fields_accounted
                and state.behavior_fields_projected
                and state.old_paths_disposed
                and state.old_fields_disposed
                and state.model_code_test_aligned
                and state.freshness_current
                and state.closure_review_passed
                else "blocked"
            )
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenUnknownOldFieldDisposition(CorrectReplacementFieldLifecycle):
    name = "BrokenUnknownOldFieldDisposition"
    idempotency = "Broken variant lets old fields remain unknown when old paths are disposed."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "project_and_dispose":
            yield FunctionResult(
                LifecycleOutput("field_projection_with_old_field_unknown"),
                replace(
                    state,
                    behavior_fields_projected=True,
                    field_evidence_route_bound=True,
                    old_paths_disposed=True,
                    old_fields_disposed=False,
                    final_claim="none",
                ),
                label="field_projection_with_old_field_unknown",
            )
            return
        if input_obj.action_type == "claim_full_done":
            claim = (
                "full"
                if state.all_fields_accounted
                and state.behavior_fields_projected
                and state.old_paths_disposed
                and state.model_code_test_aligned
                else "blocked"
            )
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenStaleAlignment(CorrectReplacementFieldLifecycle):
    name = "BrokenStaleAlignment"
    idempotency = "Broken variant claims done after alignment but before freshness and closure review."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_done":
            claim = (
                "full"
                if state.all_fields_accounted
                and state.behavior_fields_projected
                and state.old_paths_disposed
                and state.old_fields_disposed
                and state.model_code_test_aligned
                else "blocked"
            )
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPointFixOnlyBugRepair(CorrectReplacementFieldLifecycle):
    name = "BrokenPointFixOnlyBugRepair"
    idempotency = "Broken variant records observed bug but omits same-class and root-cause field closure."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "align_and_repair":
            yield FunctionResult(
                LifecycleOutput("observed_bug_only_repair"),
                replace(
                    state,
                    model_code_test_aligned=True,
                    observed_bug_recorded=True,
                    same_class_bug_case_added=False,
                    field_root_cause_backpropagated=False,
                    final_claim="none",
                ),
                label="observed_bug_only_repair",
            )
            return
        if input_obj.action_type == "claim_full_done":
            claim = (
                "full"
                if state.all_fields_accounted
                and state.behavior_fields_projected
                and state.old_paths_disposed
                and state.old_fields_disposed
                and state.model_code_test_aligned
                and state.observed_bug_recorded
                and state.freshness_current
                else "blocked"
            )
            yield FunctionResult(
                LifecycleOutput(f"claim_{claim}"),
                replace(state, final_claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, LifecycleOutput) and current_output.status.startswith("claim_")


def no_full_claim_without_complete_loop(state: LifecycleState, trace) -> InvariantResult:
    del trace
    if state.final_claim == "full" and not state.ready_for_full_claim():
        return InvariantResult.fail(
            "full replacement claim accepted before field inventory, ordinary-UI reader handoff, backend-field exclusion, behavior projection, field evidence route refs, old path/field disposition, model-code-test alignment, same-class bug repair, freshness, and closure evidence"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_full_claim_without_complete_loop",
        "Replacement and field lifecycle completion requires the whole model-code-test-field-route-repair loop.",
        no_full_claim_without_complete_loop,
    ),
)

EXTERNAL_INPUTS = (
    LifecycleAction("inventory_fields"),
    LifecycleAction("handoff_ui_reader_fields"),
    LifecycleAction("project_and_dispose"),
    LifecycleAction("align_and_repair"),
    LifecycleAction("refresh_and_close"),
    LifecycleAction("claim_full_done"),
)

BAD_CASE_EXTERNAL_INPUTS = tuple(
    action for action in EXTERNAL_INPUTS if action.action_type != "handoff_ui_reader_fields"
)

# The exact happy path above executes all six stages. The exhaustive known-bad
# search stays bounded at five steps so it can find the unsafe legacy shortcut
# that claims completion while omitting the new UI-reader handoff stage.
MAX_SEQUENCE_LENGTH = 5


def initial_state() -> LifecycleState:
    return LifecycleState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectReplacementFieldLifecycle(),), name="default_replacement_field_lifecycle_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenMissingFieldAccounting(),), name="field_lifecycle_missing_field_accounting"),
        Workflow((BrokenMissingUIReaderHandoff(),), name="field_lifecycle_missing_ui_reader_handoff"),
        Workflow((BrokenMissingProjection(),), name="field_lifecycle_missing_projection"),
        Workflow((BrokenMissingFieldEvidenceRoute(),), name="field_lifecycle_missing_evidence_route"),
        Workflow((BrokenUnknownOldFieldDisposition(),), name="field_lifecycle_unknown_old_field_disposition"),
        Workflow((BrokenStaleAlignment(),), name="field_lifecycle_stale_alignment"),
        Workflow((BrokenPointFixOnlyBugRepair(),), name="field_lifecycle_point_fix_only_bug_repair"),
    )


__all__ = [
    "BAD_CASE_EXTERNAL_INPUTS",
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "LifecycleAction",
    "LifecycleOutput",
    "LifecycleState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]


from flowguard.skill_contract_model import (
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing field-lifecycle owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-field-lifecycle-mesh",
        route_id="field_lifecycle_mesh",
        owner_id="field_lifecycle_mesh",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Account for each behavior-bearing field, projection, reader, writer, and old-field disposition.",
        claim_boundary="Projection only; field inventory, UI-reader handoff, replacement disposition, and native tests remain authoritative.",
    )


__all__ = [*__all__, "FLOWGUARD_MODEL_MARKER", "export_contract_model"]
