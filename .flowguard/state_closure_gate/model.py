"""FlowGuard model for the automatic state closure gate.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: ensure the model-first helper does not treat finite enumeration as
complete when unknown or other states may exist.
Guards against: missing representative unknown cases, accepting unknown states
as ordinary flow, allowing side effects before unknown resolution, or claiming
full confidence while the closure policy is still inferred.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/state_closure_gate/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class StateClosureInput:
    action_type: str


@dataclass(frozen=True)
class StateClosureOutput:
    status: str


@dataclass(frozen=True)
class StateClosureState:
    unknown_possible: bool = False
    representative_case_generated: bool = False
    safe_handling_declared: bool = False
    side_effect_before_resolution: bool = False
    final_claim: str = "none"

    def full_claim_allowed(self) -> bool:
        return (
            (not self.unknown_possible or self.representative_case_generated)
            and self.safe_handling_declared
            and not self.side_effect_before_resolution
        )


class CorrectStateClosureGate:
    name = "CorrectStateClosureGate"
    reads = (
        "unknown_possible",
        "representative_case_generated",
        "safe_handling_declared",
        "side_effect_before_resolution",
        "final_claim",
    )
    writes = reads
    accepted_input_type = StateClosureInput
    input_description = "state closure observation or claim"
    output_description = "state closure review state"

    def apply(self, input_obj: StateClosureInput, state: StateClosureState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "observe_unknown_possible":
            yield FunctionResult(
                StateClosureOutput("unknown_observed"),
                replace(state, unknown_possible=True, final_claim="none"),
                label="unknown_observed",
            )
        elif action == "generate_representative_case":
            yield FunctionResult(
                StateClosureOutput("unknown_case_generated"),
                replace(state, representative_case_generated=True, final_claim="none"),
                label="unknown_case_generated",
            )
        elif action == "declare_safe_handling":
            yield FunctionResult(
                StateClosureOutput("safe_handling_declared"),
                replace(state, safe_handling_declared=True, final_claim="none"),
                label="safe_handling_declared",
            )
        elif action == "observe_side_effect_before_resolution":
            yield FunctionResult(
                StateClosureOutput("side_effect_blocked"),
                replace(state, side_effect_before_resolution=True, final_claim="blocked"),
                label="side_effect_blocked",
            )
        elif action == "claim_full_confidence":
            if state.full_claim_allowed():
                yield FunctionResult(
                    StateClosureOutput("full_claim_accepted"),
                    replace(state, final_claim="full"),
                    label="full_claim_accepted",
                )
            else:
                yield FunctionResult(
                    StateClosureOutput("scoped_or_blocked_claim"),
                    replace(state, final_claim="scoped_or_blocked"),
                    label="scoped_or_blocked_claim",
                )


class BrokenMissingGeneration(CorrectStateClosureGate):
    name = "BrokenMissingGeneration"

    def apply(self, input_obj: StateClosureInput, state: StateClosureState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "generate_representative_case":
            yield FunctionResult(
                StateClosureOutput("generation_skipped"),
                replace(state, final_claim="none"),
                label="generation_skipped",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenFullWithoutSafeHandling(CorrectStateClosureGate):
    name = "BrokenFullWithoutSafeHandling"

    def apply(self, input_obj: StateClosureInput, state: StateClosureState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_full_confidence":
            yield FunctionResult(
                StateClosureOutput("full_claim_accepted"),
                replace(state, final_claim="full"),
                label="full_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSideEffectAccepted(CorrectStateClosureGate):
    name = "BrokenSideEffectAccepted"

    def apply(self, input_obj: StateClosureInput, state: StateClosureState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "observe_side_effect_before_resolution":
            yield FunctionResult(
                StateClosureOutput("side_effect_accepted"),
                replace(state, side_effect_before_resolution=True, final_claim="full"),
                label="side_effect_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, StateClosureOutput) and current_output.status in {
        "full_claim_accepted",
        "scoped_or_blocked_claim",
        "side_effect_blocked",
        "side_effect_accepted",
    }


def unknown_generates_representative_case(state: StateClosureState, trace) -> InvariantResult:
    del trace
    if state.unknown_possible and state.final_claim == "full" and not state.representative_case_generated:
        return InvariantResult.fail("full confidence accepted before representative unknown case was generated")
    return InvariantResult.pass_()


def full_claim_requires_safe_handling(state: StateClosureState, trace) -> InvariantResult:
    del trace
    if state.final_claim == "full" and not state.safe_handling_declared:
        return InvariantResult.fail("full confidence accepted before safe unknown handling was declared")
    return InvariantResult.pass_()


def side_effect_blocks_full_claim(state: StateClosureState, trace) -> InvariantResult:
    del trace
    if state.side_effect_before_resolution and state.final_claim == "full":
        return InvariantResult.fail("full confidence accepted after side effect before unknown resolution")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "unknown_generates_representative_case",
        "Unknown/other possibility must generate representative closure cases before full confidence.",
        unknown_generates_representative_case,
    ),
    Invariant(
        "full_claim_requires_safe_handling",
        "Full confidence requires safe unknown handling.",
        full_claim_requires_safe_handling,
    ),
    Invariant(
        "side_effect_blocks_full_claim",
        "Unknown side effects before resolution block full confidence.",
        side_effect_blocks_full_claim,
    ),
)

EXTERNAL_INPUTS = (
    StateClosureInput("observe_unknown_possible"),
    StateClosureInput("generate_representative_case"),
    StateClosureInput("declare_safe_handling"),
    StateClosureInput("observe_side_effect_before_resolution"),
    StateClosureInput("claim_full_confidence"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> StateClosureState:
    return StateClosureState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectStateClosureGate(),), name="state_closure_gate_correct")


def build_broken_workflows() -> tuple[Workflow, ...]:
    return (
        Workflow((BrokenMissingGeneration(),), name="state_closure_missing_generation"),
        Workflow((BrokenFullWithoutSafeHandling(),), name="state_closure_full_without_handling"),
        Workflow((BrokenSideEffectAccepted(),), name="state_closure_side_effect_accepted"),
    )


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "StateClosureInput",
    "StateClosureOutput",
    "StateClosureState",
    "build_broken_workflows",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
