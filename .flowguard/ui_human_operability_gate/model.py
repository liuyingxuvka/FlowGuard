"""FlowGuard model for UI human-operability hardening.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: prevent UI completion claims from passing when functional capabilities
are not mapped to user tasks, tasks are not mapped to UI paths, or the UI is
technically wired but confusing to humans.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/ui_human_operability_gate/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class UIHumanAction:
    action_type: str


@dataclass(frozen=True)
class UIHumanOutput:
    status: str
    reason: str = ""


@dataclass(frozen=True)
class UIHumanState:
    openspec_valid: bool = False
    existing_model_preflight_current: bool = False
    feature_inventory_current: bool = False
    task_coverage_ledger_current: bool = False
    all_features_mapped_to_tasks: bool = False
    all_tasks_have_flows: bool = False
    all_tasks_mapped_to_ui_paths: bool = False
    no_orphan_primary_controls: bool = False
    region_semantics_current: bool = False
    affordance_contracts_current: bool = False
    action_grammar_current: bool = False
    dialog_return_contracts_current: bool = False
    keyboard_focus_contracts_current: bool = False
    walkthrough_evidence_current: bool = False
    no_unmitigated_confusion: bool = False
    implementation_validation_current: bool = False
    closure_gate_current: bool = False
    tests_current: bool = False
    installed_skills_synced: bool = False
    shadow_and_git_synced: bool = False
    done_claim: str = "none"

    def ready_for_human_operable_claim(self) -> bool:
        return (
            self.openspec_valid
            and self.existing_model_preflight_current
            and self.feature_inventory_current
            and self.task_coverage_ledger_current
            and self.all_features_mapped_to_tasks
            and self.all_tasks_have_flows
            and self.all_tasks_mapped_to_ui_paths
            and self.no_orphan_primary_controls
            and self.region_semantics_current
            and self.affordance_contracts_current
            and self.action_grammar_current
            and self.dialog_return_contracts_current
            and self.keyboard_focus_contracts_current
            and self.walkthrough_evidence_current
            and self.no_unmitigated_confusion
            and self.implementation_validation_current
            and self.closure_gate_current
            and self.tests_current
            and self.installed_skills_synced
            and self.shadow_and_git_synced
        )


class CorrectUIHumanOperabilityHardening:
    name = "CorrectUIHumanOperabilityHardening"
    reads = tuple(UIHumanState.__dataclass_fields__.keys())
    writes = reads
    accepted_input_type = UIHumanAction
    input_description = "UI human-operability route action"
    output_description = "UI human-operability evidence state or claim decision"
    idempotency = (
        "Human-operable UI requires feature-to-task coverage, task flows, "
        "task-to-UI links, no orphan primary controls, region semantics, "
        "affordance, action grammar, dialog returns, keyboard/focus, "
        "walkthroughs, implementation validation, tests, and sync."
    )

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "validate_openspec":
            yield FunctionResult(UIHumanOutput("openspec_valid"), replace(state, openspec_valid=True), label="openspec_valid")
        elif action == "run_existing_model_preflight":
            ok = state.openspec_valid
            yield FunctionResult(
                UIHumanOutput("preflight_current" if ok else "preflight_blocked"),
                replace(state, existing_model_preflight_current=ok),
                label="preflight_current" if ok else "preflight_blocked",
            )
        elif action == "inventory_features":
            ok = state.existing_model_preflight_current
            yield FunctionResult(
                UIHumanOutput("feature_inventory_current" if ok else "feature_inventory_blocked"),
                replace(state, feature_inventory_current=ok),
                label="feature_inventory_current" if ok else "feature_inventory_blocked",
            )
        elif action == "build_task_coverage_ledger":
            ok = state.feature_inventory_current
            yield FunctionResult(
                UIHumanOutput("task_coverage_ledger_current" if ok else "task_coverage_blocked"),
                replace(state, task_coverage_ledger_current=ok),
                label="task_coverage_ledger_current" if ok else "task_coverage_blocked",
            )
        elif action == "map_features_to_tasks":
            ok = state.task_coverage_ledger_current
            yield FunctionResult(
                UIHumanOutput("features_mapped_to_tasks" if ok else "feature_task_mapping_blocked"),
                replace(state, all_features_mapped_to_tasks=ok),
                label="features_mapped_to_tasks" if ok else "feature_task_mapping_blocked",
            )
        elif action == "model_task_flows":
            ok = state.all_features_mapped_to_tasks
            yield FunctionResult(
                UIHumanOutput("task_flows_current" if ok else "task_flows_blocked"),
                replace(state, all_tasks_have_flows=ok),
                label="task_flows_current" if ok else "task_flows_blocked",
            )
        elif action == "map_tasks_to_ui_paths":
            ok = state.all_tasks_have_flows
            yield FunctionResult(
                UIHumanOutput("tasks_mapped_to_ui_paths" if ok else "task_ui_mapping_blocked"),
                replace(state, all_tasks_mapped_to_ui_paths=ok),
                label="tasks_mapped_to_ui_paths" if ok else "task_ui_mapping_blocked",
            )
        elif action == "classify_primary_controls":
            ok = state.all_tasks_mapped_to_ui_paths
            yield FunctionResult(
                UIHumanOutput("primary_controls_owned" if ok else "primary_control_blocked"),
                replace(state, no_orphan_primary_controls=ok),
                label="primary_controls_owned" if ok else "primary_control_blocked",
            )
        elif action == "review_region_semantics":
            ok = state.no_orphan_primary_controls
            yield FunctionResult(
                UIHumanOutput("region_semantics_current" if ok else "region_semantics_blocked"),
                replace(state, region_semantics_current=ok),
                label="region_semantics_current" if ok else "region_semantics_blocked",
            )
        elif action == "review_affordance":
            ok = state.region_semantics_current
            yield FunctionResult(
                UIHumanOutput("affordance_contracts_current" if ok else "affordance_blocked"),
                replace(state, affordance_contracts_current=ok),
                label="affordance_contracts_current" if ok else "affordance_blocked",
            )
        elif action == "review_action_grammar":
            ok = state.affordance_contracts_current
            yield FunctionResult(
                UIHumanOutput("action_grammar_current" if ok else "action_grammar_blocked"),
                replace(state, action_grammar_current=ok),
                label="action_grammar_current" if ok else "action_grammar_blocked",
            )
        elif action == "review_dialog_returns":
            ok = state.action_grammar_current
            yield FunctionResult(
                UIHumanOutput("dialog_returns_current" if ok else "dialog_returns_blocked"),
                replace(state, dialog_return_contracts_current=ok),
                label="dialog_returns_current" if ok else "dialog_returns_blocked",
            )
        elif action == "review_keyboard_focus":
            ok = state.dialog_return_contracts_current
            yield FunctionResult(
                UIHumanOutput("keyboard_focus_current" if ok else "keyboard_focus_blocked"),
                replace(state, keyboard_focus_contracts_current=ok),
                label="keyboard_focus_current" if ok else "keyboard_focus_blocked",
            )
        elif action == "run_walkthroughs":
            ok = state.keyboard_focus_contracts_current
            yield FunctionResult(
                UIHumanOutput("walkthroughs_current" if ok else "walkthroughs_blocked"),
                replace(state, walkthrough_evidence_current=ok, no_unmitigated_confusion=ok),
                label="walkthroughs_current" if ok else "walkthroughs_blocked",
            )
        elif action == "bind_implementation_validation":
            ok = state.walkthrough_evidence_current and state.no_unmitigated_confusion
            yield FunctionResult(
                UIHumanOutput("implementation_validation_current" if ok else "implementation_validation_blocked"),
                replace(state, implementation_validation_current=ok),
                label="implementation_validation_current" if ok else "implementation_validation_blocked",
            )
        elif action == "add_closure_gate":
            ok = state.implementation_validation_current
            yield FunctionResult(
                UIHumanOutput("closure_gate_current" if ok else "closure_gate_blocked"),
                replace(state, closure_gate_current=ok),
                label="closure_gate_current" if ok else "closure_gate_blocked",
            )
        elif action == "run_tests":
            ok = state.closure_gate_current
            yield FunctionResult(
                UIHumanOutput("tests_current" if ok else "tests_blocked"),
                replace(state, tests_current=ok),
                label="tests_current" if ok else "tests_blocked",
            )
        elif action == "sync_installed_skills":
            ok = state.tests_current
            yield FunctionResult(
                UIHumanOutput("installed_skills_synced" if ok else "installed_sync_blocked"),
                replace(state, installed_skills_synced=ok),
                label="installed_skills_synced" if ok else "installed_sync_blocked",
            )
        elif action == "sync_shadow_and_git":
            ok = state.installed_skills_synced
            yield FunctionResult(
                UIHumanOutput("shadow_and_git_synced" if ok else "shadow_git_sync_blocked"),
                replace(state, shadow_and_git_synced=ok),
                label="shadow_and_git_synced" if ok else "shadow_git_sync_blocked",
            )
        elif action == "claim_human_operable_done":
            accepted = state.ready_for_human_operable_claim()
            yield FunctionResult(
                UIHumanOutput("human_operable_done_accepted" if accepted else "human_operable_done_rejected"),
                replace(state, done_claim="accepted" if accepted else "rejected"),
                label="human_operable_done_accepted" if accepted else "human_operable_done_rejected",
            )


class BrokenMissingTaskCoverage(CorrectUIHumanOperabilityHardening):
    name = "BrokenMissingTaskCoverage"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "build_task_coverage_ledger":
            yield FunctionResult(
                UIHumanOutput("task_coverage_missing_but_continues"),
                replace(state, task_coverage_ledger_current=False),
                label="task_coverage_missing_but_continues",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenOrphanPrimaryControl(CorrectUIHumanOperabilityHardening):
    name = "BrokenOrphanPrimaryControl"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "classify_primary_controls":
            yield FunctionResult(
                UIHumanOutput("orphan_primary_control_accepted"),
                replace(state, no_orphan_primary_controls=False),
                label="orphan_primary_control_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenDuplicatePrimaryAction(CorrectUIHumanOperabilityHardening):
    name = "BrokenDuplicatePrimaryAction"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_action_grammar":
            yield FunctionResult(
                UIHumanOutput("duplicate_primary_action_accepted"),
                replace(state, action_grammar_current=False),
                label="duplicate_primary_action_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenDialogReturn(CorrectUIHumanOperabilityHardening):
    name = "BrokenDialogReturn"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_dialog_returns":
            yield FunctionResult(
                UIHumanOutput("dialog_return_missing_but_accepted"),
                replace(state, dialog_return_contracts_current=False),
                label="dialog_return_missing_but_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenKeyboardFocus(CorrectUIHumanOperabilityHardening):
    name = "BrokenKeyboardFocus"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "review_keyboard_focus":
            yield FunctionResult(
                UIHumanOutput("keyboard_focus_missing_but_accepted"),
                replace(state, keyboard_focus_contracts_current=False),
                label="keyboard_focus_missing_but_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenConfusedWalkthrough(CorrectUIHumanOperabilityHardening):
    name = "BrokenConfusedWalkthrough"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "run_walkthroughs":
            yield FunctionResult(
                UIHumanOutput("walkthrough_confusion_accepted"),
                replace(state, walkthrough_evidence_current=True, no_unmitigated_confusion=False),
                label="walkthrough_confusion_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenOverbroadHumanDone(CorrectUIHumanOperabilityHardening):
    name = "BrokenOverbroadHumanDone"

    def apply(self, input_obj: UIHumanAction, state: UIHumanState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_human_operable_done":
            yield FunctionResult(
                UIHumanOutput("human_operable_done_accepted_without_evidence"),
                replace(state, shadow_and_git_synced=False, done_claim="accepted"),
                label="human_operable_done_accepted_without_evidence",
            )
            return
        yield from super().apply(input_obj, state)


HAPPY_PATH = (
    "validate_openspec",
    "run_existing_model_preflight",
    "inventory_features",
    "build_task_coverage_ledger",
    "map_features_to_tasks",
    "model_task_flows",
    "map_tasks_to_ui_paths",
    "classify_primary_controls",
    "review_region_semantics",
    "review_affordance",
    "review_action_grammar",
    "review_dialog_returns",
    "review_keyboard_focus",
    "run_walkthroughs",
    "bind_implementation_validation",
    "add_closure_gate",
    "run_tests",
    "sync_installed_skills",
    "sync_shadow_and_git",
    "claim_human_operable_done",
)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, UIHumanOutput) and current_output.status.startswith("human_operable_done_")


def no_human_operable_done_without_evidence(state: UIHumanState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_human_operable_claim():
        return InvariantResult.fail(
            "human-operable UI accepted without task coverage, task flows, task-to-UI links, affordance, action grammar, dialog, keyboard, walkthrough, validation, tests, install, shadow, and git evidence"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_human_operable_done_without_evidence",
        "Human-operable UI completion requires task coverage and user-comprehension evidence.",
        no_human_operable_done_without_evidence,
    ),
)

EXTERNAL_INPUTS = tuple(UIHumanAction(action) for action in HAPPY_PATH)
MAX_SEQUENCE_LENGTH = len(HAPPY_PATH)


def initial_state() -> UIHumanState:
    return UIHumanState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectUIHumanOperabilityHardening(),), name="ui_human_operability_correct")
