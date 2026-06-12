"""FlowGuard model for hardening UI real-surface validation.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: prevent UI completion claims from passing when the real rendered UI,
enabled-control behavior, MATLAB callback semantics, or final claim evidence is
missing.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/harden_ui_real_surface_validation/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class UIHardeningAction:
    action_type: str


@dataclass(frozen=True)
class UIHardeningOutput:
    status: str
    reason: str = ""


@dataclass(frozen=True)
class UIHardeningState:
    openspec_valid: bool = False
    existing_model_preflight_current: bool = False
    observed_inventory_gate: bool = False
    all_visible_items_mapped: bool = False
    functional_chain_gate: bool = False
    matlab_callback_gate: bool = False
    ui_model_miss_gate: bool = False
    task_evidence_gate: bool = False
    final_done_claim_gate: bool = False
    agent_role_evidence_gate: bool = False
    tests_current: bool = False
    installed_skills_synced: bool = False
    shadow_and_git_synced: bool = False
    done_claim: str = "none"

    def ready_for_full_claim(self) -> bool:
        return (
            self.openspec_valid
            and self.existing_model_preflight_current
            and self.observed_inventory_gate
            and self.all_visible_items_mapped
            and self.functional_chain_gate
            and self.matlab_callback_gate
            and self.ui_model_miss_gate
            and self.task_evidence_gate
            and self.final_done_claim_gate
            and self.agent_role_evidence_gate
            and self.tests_current
            and self.installed_skills_synced
            and self.shadow_and_git_synced
        )


class CorrectUILastMileHardening:
    name = "CorrectUILastMileHardening"
    reads = (
        "openspec_valid",
        "existing_model_preflight_current",
        "observed_inventory_gate",
        "all_visible_items_mapped",
        "functional_chain_gate",
        "matlab_callback_gate",
        "ui_model_miss_gate",
        "task_evidence_gate",
        "final_done_claim_gate",
        "agent_role_evidence_gate",
        "tests_current",
        "installed_skills_synced",
        "shadow_and_git_synced",
        "done_claim",
    )
    writes = reads
    accepted_input_type = UIHardeningAction
    input_description = "UI last-mile validation hardening lifecycle action"
    output_description = "UI last-mile hardening state or claim decision"
    idempotency = (
        "Full claim requires observed inventory, mapping, function chains, "
        "MATLAB semantics, model miss, task evidence, final claim, agent roles, "
        "tests, installed skill sync, and shadow/git sync."
    )

    def apply(self, input_obj: UIHardeningAction, state: UIHardeningState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "validate_openspec":
            yield FunctionResult(
                UIHardeningOutput("openspec_valid"),
                replace(state, openspec_valid=True),
                label="openspec_valid",
            )
        elif action == "run_existing_model_preflight":
            ok = state.openspec_valid
            yield FunctionResult(
                UIHardeningOutput(
                    "existing_model_preflight_current" if ok else "preflight_blocked",
                    "" if ok else "OpenSpec boundary must exist first",
                ),
                replace(state, existing_model_preflight_current=ok),
                label="existing_model_preflight_current" if ok else "preflight_blocked",
            )
        elif action == "add_observed_inventory_gate":
            ok = state.existing_model_preflight_current
            yield FunctionResult(
                UIHardeningOutput("observed_inventory_gate_added" if ok else "inventory_gate_blocked"),
                replace(state, observed_inventory_gate=ok),
                label="observed_inventory_gate_added" if ok else "inventory_gate_blocked",
            )
        elif action == "map_visible_items":
            ok = state.observed_inventory_gate
            yield FunctionResult(
                UIHardeningOutput("visible_items_mapped" if ok else "mapping_blocked"),
                replace(state, all_visible_items_mapped=ok),
                label="visible_items_mapped" if ok else "mapping_blocked",
            )
        elif action == "add_functional_chain_gate":
            ok = state.observed_inventory_gate and state.all_visible_items_mapped
            yield FunctionResult(
                UIHardeningOutput("functional_chain_gate_added" if ok else "functional_chain_blocked"),
                replace(state, functional_chain_gate=ok),
                label="functional_chain_gate_added" if ok else "functional_chain_blocked",
            )
        elif action == "add_matlab_callback_gate":
            ok = state.functional_chain_gate
            yield FunctionResult(
                UIHardeningOutput("matlab_callback_gate_added" if ok else "matlab_gate_blocked"),
                replace(state, matlab_callback_gate=ok),
                label="matlab_callback_gate_added" if ok else "matlab_gate_blocked",
            )
        elif action == "add_model_miss_gate":
            ok = state.functional_chain_gate
            yield FunctionResult(
                UIHardeningOutput("model_miss_gate_added" if ok else "model_miss_gate_blocked"),
                replace(state, ui_model_miss_gate=ok),
                label="model_miss_gate_added" if ok else "model_miss_gate_blocked",
            )
        elif action == "add_task_evidence_gate":
            ok = state.observed_inventory_gate and state.functional_chain_gate
            yield FunctionResult(
                UIHardeningOutput("task_evidence_gate_added" if ok else "task_evidence_blocked"),
                replace(state, task_evidence_gate=ok),
                label="task_evidence_gate_added" if ok else "task_evidence_blocked",
            )
        elif action == "add_final_done_claim_gate":
            ok = state.task_evidence_gate and state.ui_model_miss_gate
            yield FunctionResult(
                UIHardeningOutput("final_done_claim_gate_added" if ok else "done_claim_gate_blocked"),
                replace(state, final_done_claim_gate=ok),
                label="final_done_claim_gate_added" if ok else "done_claim_gate_blocked",
            )
        elif action == "add_agent_role_gate":
            ok = state.observed_inventory_gate and state.functional_chain_gate
            yield FunctionResult(
                UIHardeningOutput("agent_role_gate_added" if ok else "agent_role_gate_blocked"),
                replace(state, agent_role_evidence_gate=ok),
                label="agent_role_gate_added" if ok else "agent_role_gate_blocked",
            )
        elif action == "run_tests":
            ok = (
                state.openspec_valid
                and state.observed_inventory_gate
                and state.all_visible_items_mapped
                and state.functional_chain_gate
                and state.matlab_callback_gate
                and state.ui_model_miss_gate
                and state.task_evidence_gate
                and state.final_done_claim_gate
                and state.agent_role_evidence_gate
            )
            yield FunctionResult(
                UIHardeningOutput("tests_current" if ok else "tests_blocked"),
                replace(state, tests_current=ok),
                label="tests_current" if ok else "tests_blocked",
            )
        elif action == "sync_installed_skills":
            ok = state.tests_current
            yield FunctionResult(
                UIHardeningOutput("installed_skills_synced" if ok else "installed_sync_blocked"),
                replace(state, installed_skills_synced=ok),
                label="installed_skills_synced" if ok else "installed_sync_blocked",
            )
        elif action == "sync_shadow_and_git":
            ok = state.installed_skills_synced
            yield FunctionResult(
                UIHardeningOutput("shadow_and_git_synced" if ok else "shadow_git_sync_blocked"),
                replace(state, shadow_and_git_synced=ok),
                label="shadow_and_git_synced" if ok else "shadow_git_sync_blocked",
            )
        elif action == "claim_done":
            accepted = state.ready_for_full_claim()
            yield FunctionResult(
                UIHardeningOutput("done_accepted" if accepted else "done_rejected"),
                replace(state, done_claim="accepted" if accepted else "rejected"),
                label="done_accepted" if accepted else "done_rejected",
            )


class BrokenNoObservedInventory(CorrectUILastMileHardening):
    name = "BrokenNoObservedInventory"
    idempotency = "Broken variant accepts model-only UI completion."

    def apply(self, input_obj: UIHardeningAction, state: UIHardeningState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_observed_inventory_gate":
            yield FunctionResult(
                UIHardeningOutput("inventory_gate_missing_but_accepted"),
                replace(state, observed_inventory_gate=False, all_visible_items_mapped=False),
                label="inventory_gate_missing_but_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenApiOnlyFunctionalChain(CorrectUILastMileHardening):
    name = "BrokenApiOnlyFunctionalChain"
    idempotency = "Broken variant accepts API/label evidence without click-to-effect proof."

    def apply(self, input_obj: UIHardeningAction, state: UIHardeningState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_functional_chain_gate":
            yield FunctionResult(
                UIHardeningOutput("api_only_chain_accepted"),
                replace(state, functional_chain_gate=False),
                label="api_only_chain_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenMatlabCancelBranchMissing(CorrectUILastMileHardening):
    name = "BrokenMatlabCancelBranchMissing"
    idempotency = "Broken variant accepts MATLAB file picker parity without cancel/error branch semantics."

    def apply(self, input_obj: UIHardeningAction, state: UIHardeningState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_matlab_callback_gate":
            yield FunctionResult(
                UIHardeningOutput("matlab_success_only_accepted"),
                replace(state, matlab_callback_gate=False),
                label="matlab_success_only_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenFinalClaimOverbroad(CorrectUILastMileHardening):
    name = "BrokenFinalClaimOverbroad"
    idempotency = "Broken variant accepts full done before sync and final gates."

    def apply(self, input_obj: UIHardeningAction, state: UIHardeningState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "add_final_done_claim_gate":
            yield FunctionResult(
                UIHardeningOutput("final_done_claim_gate_missing_but_continues"),
                replace(state, final_done_claim_gate=False),
                label="final_done_claim_gate_missing_but_continues",
            )
            return
        if input_obj.action_type == "claim_done":
            yield FunctionResult(
                UIHardeningOutput("done_accepted_without_final_evidence"),
                replace(state, done_claim="accepted"),
                label="done_accepted_without_final_evidence",
            )
            return
        yield from super().apply(input_obj, state)


HAPPY_PATH = (
    "validate_openspec",
    "run_existing_model_preflight",
    "add_observed_inventory_gate",
    "map_visible_items",
    "add_functional_chain_gate",
    "add_matlab_callback_gate",
    "add_model_miss_gate",
    "add_task_evidence_gate",
    "add_final_done_claim_gate",
    "add_agent_role_gate",
    "run_tests",
    "sync_installed_skills",
    "sync_shadow_and_git",
    "claim_done",
)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, UIHardeningOutput) and current_output.status.startswith("done_")


def no_full_done_without_last_mile_evidence(state: UIHardeningState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_full_claim():
        return InvariantResult.fail(
            "full UI done accepted without observed inventory, mapping, functional chain, MATLAB semantics, miss, task, final-claim, agent-role, test, install, shadow, and git evidence"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_full_done_without_last_mile_evidence",
        "Full UI completion requires observed real surface, functional chain, MATLAB semantics, closure, validation, and sync evidence.",
        no_full_done_without_last_mile_evidence,
    ),
)

EXTERNAL_INPUTS = tuple(UIHardeningAction(action) for action in HAPPY_PATH)
MAX_SEQUENCE_LENGTH = len(HAPPY_PATH)


def initial_state() -> UIHardeningState:
    return UIHardeningState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectUILastMileHardening(),), name="ui_last_mile_hardening_correct")


def build_broken_no_inventory_workflow() -> Workflow:
    return Workflow((BrokenNoObservedInventory(),), name="ui_last_mile_hardening_no_inventory")


def build_broken_api_only_workflow() -> Workflow:
    return Workflow((BrokenApiOnlyFunctionalChain(),), name="ui_last_mile_hardening_api_only")


def build_broken_matlab_workflow() -> Workflow:
    return Workflow((BrokenMatlabCancelBranchMissing(),), name="ui_last_mile_hardening_matlab_missing_cancel")


def build_broken_done_claim_workflow() -> Workflow:
    return Workflow((BrokenFinalClaimOverbroad(),), name="ui_last_mile_hardening_overbroad_done")
