"""FlowGuard model for AI-facing field prompt reduction.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the field-prompt reduction for FlowGuard skill guidance before
and after implementation. It guards against reducing repeated field lists while
dropping required evidence, freshness, external-boundary, installed-skill,
shadow-workspace, or git evidence gates.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/field_prompt_reduction/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class FieldPromptAction:
    action_type: str


@dataclass(frozen=True)
class FieldPromptOutput:
    status: str


@dataclass(frozen=True)
class FieldPromptState:
    field_groups_declared: bool = False
    required_evidence_preserved: bool = False
    optional_details_lazy_loaded: bool = False
    prompt_field_caps_tested: bool = False
    focused_validation_passed: bool = False
    broad_regression_complete: bool = False
    installed_skills_synced: bool = False
    shadow_workspace_synced: bool = False
    git_evidence_recorded: bool = False
    done_claim: str = "none"

    def ready_for_done(self) -> bool:
        return (
            self.field_groups_declared
            and self.required_evidence_preserved
            and self.optional_details_lazy_loaded
            and self.prompt_field_caps_tested
            and self.focused_validation_passed
            and self.broad_regression_complete
            and self.installed_skills_synced
            and self.shadow_workspace_synced
            and self.git_evidence_recorded
        )


class CorrectFieldPromptReduction:
    name = "CorrectFieldPromptReduction"
    reads = (
        "field_groups_declared",
        "required_evidence_preserved",
        "optional_details_lazy_loaded",
        "prompt_field_caps_tested",
        "focused_validation_passed",
        "broad_regression_complete",
        "installed_skills_synced",
        "shadow_workspace_synced",
        "git_evidence_recorded",
        "done_claim",
    )
    writes = reads
    accepted_input_type = FieldPromptAction
    input_description = "field prompt reduction lifecycle action"
    output_description = "field prompt reduction state or claim decision"
    idempotency = "Done claims require grouped fields plus evidence, validation, install, shadow, and git gates."

    def apply(self, input_obj: FieldPromptAction, state: FieldPromptState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "group_fields":
            yield FunctionResult(
                FieldPromptOutput("fields_grouped"),
                replace(
                    state,
                    field_groups_declared=True,
                    required_evidence_preserved=True,
                    optional_details_lazy_loaded=True,
                ),
                label="fields_grouped",
            )
        elif action == "add_tests":
            yield FunctionResult(
                FieldPromptOutput("tests_added"),
                replace(state, prompt_field_caps_tested=True),
                label="tests_added",
            )
        elif action == "run_focused_validation":
            yield FunctionResult(
                FieldPromptOutput("focused_validation_passed"),
                replace(state, focused_validation_passed=True),
                label="focused_validation_passed",
            )
        elif action == "run_broad_regression":
            yield FunctionResult(
                FieldPromptOutput("broad_regression_complete"),
                replace(state, broad_regression_complete=True),
                label="broad_regression_complete",
            )
        elif action == "sync_local_surfaces":
            yield FunctionResult(
                FieldPromptOutput("local_surfaces_synced"),
                replace(
                    state,
                    installed_skills_synced=True,
                    shadow_workspace_synced=True,
                    git_evidence_recorded=True,
                ),
                label="local_surfaces_synced",
            )
        elif action == "claim_done":
            claim = "accepted" if state.ready_for_done() else "rejected"
            yield FunctionResult(
                FieldPromptOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )


class BrokenDropsRequiredEvidence(CorrectFieldPromptReduction):
    name = "BrokenDropsRequiredEvidence"
    idempotency = "Broken variant groups fields but drops the required evidence boundary."

    def apply(self, input_obj: FieldPromptAction, state: FieldPromptState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "group_fields":
            yield FunctionResult(
                FieldPromptOutput("fields_grouped"),
                replace(
                    state,
                    field_groups_declared=True,
                    required_evidence_preserved=False,
                    optional_details_lazy_loaded=True,
                ),
                label="fields_grouped",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPromptOnlyCompletion(CorrectFieldPromptReduction):
    name = "BrokenPromptOnlyCompletion"
    idempotency = "Broken variant accepts done after grouping fields and focused validation only."

    def apply(self, input_obj: FieldPromptAction, state: FieldPromptState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done":
            claim = "accepted" if state.field_groups_declared and state.focused_validation_passed else "rejected"
            yield FunctionResult(
                FieldPromptOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, FieldPromptOutput) and current_output.status.startswith("done_")


def no_done_without_evidence_and_sync(state: FieldPromptState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "done accepted before grouped fields, required evidence, lazy detail, tests, validation, regression, install, shadow, and git gates"
        )
    return InvariantResult.pass_()


def grouped_fields_preserve_required_evidence(state: FieldPromptState, trace) -> InvariantResult:
    del trace
    if state.field_groups_declared and not state.required_evidence_preserved:
        return InvariantResult.fail("field grouping dropped required evidence or boundary fields")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_evidence_and_sync",
        "Field prompt reduction completion requires evidence preservation, validation, install, shadow, and git evidence.",
        no_done_without_evidence_and_sync,
    ),
    Invariant(
        "grouped_fields_preserve_required_evidence",
        "Grouped fields must preserve required ids, status, freshness, skipped visibility, and boundary evidence.",
        grouped_fields_preserve_required_evidence,
    ),
)

EXTERNAL_INPUTS = (
    FieldPromptAction("group_fields"),
    FieldPromptAction("add_tests"),
    FieldPromptAction("run_focused_validation"),
    FieldPromptAction("run_broad_regression"),
    FieldPromptAction("sync_local_surfaces"),
    FieldPromptAction("claim_done"),
)

MAX_SEQUENCE_LENGTH = 6


def initial_state() -> FieldPromptState:
    return FieldPromptState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectFieldPromptReduction(),), name="field_prompt_reduction_correct")


def build_broken_evidence_workflow() -> Workflow:
    return Workflow((BrokenDropsRequiredEvidence(),), name="field_prompt_reduction_broken_evidence")


def build_broken_prompt_only_workflow() -> Workflow:
    return Workflow((BrokenPromptOnlyCompletion(),), name="field_prompt_reduction_broken_prompt_only")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "FieldPromptAction",
    "FieldPromptOutput",
    "FieldPromptState",
    "build_broken_evidence_workflow",
    "build_broken_prompt_only_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
