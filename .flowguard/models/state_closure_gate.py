"""FlowGuard model for the automatic state closure gate.

FlowGuard model
Purpose: ensure the model-first helper does not treat finite enumeration as
complete when unknown or other states may exist.
Guards against: missing representative unknown cases, accepting unknown states
as ordinary flow, allowing side effects before unknown resolution, or claiming
full confidence while the closure policy is still inferred.
Modeled block shape: Input x State -> Set(Output x State).
Run: python -m flowguard map models state_closure_gate
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

# The owner supplies per-case witness lengths; two is the bounded fallback and
# is sufficient for the missing-generation label witness.  A global depth of
# five would enumerate an unnecessary 5^5 input product for every bad model.
MAX_SEQUENCE_LENGTH = 2


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


# FlowGuard contract: explore the model above, prove its known-bad variants fail, and compare the real
# state-closure review with it (feature kit).  The clean plan has two open dimensions whose unknown values
# are rejected before any side effect.  Each feature changes one dimension: accepting unknown values as
# normal, a side effect before resolution, or no declared handling must block; leaving the representative
# unknown to the gate, another known value and an extra closed dimension must not.
from flowguard import (  # noqa: E402
    STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
    STATE_CLOSURE_DIMENSION_INPUT_FIELD,
    STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
    STATE_CLOSURE_HANDLING_REJECT,
    STATE_CLOSURE_HANDLING_UNKNOWN,
    STATE_CLOSURE_POLICY_CLOSED,
    STATE_CLOSURE_POLICY_OPEN,
    StateClosureDimension,
    StateClosurePlan,
    review_state_closure,
)
from flowguard.explorer import Explorer  # noqa: E402
from flowguard.kit import Feature, feature_conformance  # noqa: E402

MODEL_ID = "state_closure_gate"
COMPONENTS = ["engine-properties"]
IMPLEMENTED_BY = {"Review": "flowguard/state_closure.py:review_state_closure"}
TESTED_BY = {
    "full_claim_requires_safe_handling": [
        "tests/test_state_closure.py:test_explicit_open_boundary_with_safe_handling_passes"],
    "side_effect_blocks_full_claim": [
        "tests/test_state_closure.py:test_unsafe_or_side_effect_unknown_handling_blocks"],
}
REQUIRED_LABELS = ("unknown_observed", "unknown_case_generated", "safe_handling_declared", "full_claim_accepted",
                   "scoped_or_blocked_claim")


def _explorer(workflow, length, labels=()):
    return Explorer(workflow=workflow, initial_states=(initial_state(),), external_inputs=EXTERNAL_INPUTS,
                    invariants=INVARIANTS, max_sequence_length=length, terminal_predicate=terminal_predicate,
                    required_labels=labels, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(build_correct_workflow(), MAX_SEQUENCE_LENGTH, REQUIRED_LABELS)


def broken_variants() -> dict:
    missing_generation, without_handling, side_effect = build_broken_workflows()
    return {missing_generation.name: _explorer(missing_generation, 2, ("unknown_case_generated",)),
            without_handling.name: _explorer(without_handling, 1),
            side_effect.name: _explorer(side_effect, 1)}


def _clean_plan() -> StateClosurePlan:
    return StateClosurePlan("safe", dimensions=(
        StateClosureDimension("external_input", STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT, policy=STATE_CLOSURE_POLICY_OPEN,
                              known_values=("known",), representative_unknowns=("other",),
                              handling=STATE_CLOSURE_HANDLING_REJECT),
        StateClosureDimension("input.status", STATE_CLOSURE_DIMENSION_INPUT_FIELD, policy=STATE_CLOSURE_POLICY_OPEN,
                              known_values=("known",), representative_unknowns=("cancelled",),
                              handling=STATE_CLOSURE_HANDLING_REJECT)))


def _dimension(dimension_id: str, **values):
    return lambda plan: replace(plan, dimensions=tuple(replace(d, **values) if d.dimension_id == dimension_id else d
                                                       for d in plan.dimensions))


FEATURES = (
    Feature("unknown_accepted_as_normal", True, ("state_closure_unknown_handling_unsafe",),
            _dimension("external_input", handling=STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL)),
    Feature("side_effect_before_resolution", True, ("state_closure_side_effect_before_resolution",),
            _dimension("input.status", side_effects_before_resolution=True)),
    Feature("unknown_handling_missing", True, ("state_closure_unknown_handling_missing",),
            _dimension("input.status", handling=STATE_CLOSURE_HANDLING_UNKNOWN)),
    Feature("representative_unknown_left_to_the_gate", False, (),
            _dimension("external_input", representative_unknowns=())),
    Feature("another_known_value", False, (), _dimension("external_input", known_values=("known", "known_2"))),
    Feature("extra_closed_dimension", False, (),
            lambda plan: replace(plan, dimensions=plan.dimensions + (StateClosureDimension(
                "mode", STATE_CLOSURE_DIMENSION_INPUT_FIELD, policy=STATE_CLOSURE_POLICY_CLOSED, known_values=("a", "b")),))),
)


def _review(plan: StateClosurePlan):
    report = review_state_closure(plan)
    return report.ok, tuple(finding.code for finding in report.findings)


def conformance():
    return feature_conformance(FEATURES, _clean_plan, _review)
