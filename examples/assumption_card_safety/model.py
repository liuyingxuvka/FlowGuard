"""Executable model for safe conditional assumption handling."""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    Explorer,
    FunctionResult,
    Invariant,
    InvariantResult,
    ReachabilityCondition,
    Workflow,
)


@dataclass(frozen=True)
class AssumptionCase:
    name: str
    boundary_kind: str
    has_preconditions: bool = True
    has_why_not_modeled: bool = True
    modelable_as_finite_states: bool = False
    preconditions_hold: bool = True
    boundary_changed: bool = False
    visible: bool = True


@dataclass(frozen=True)
class AssumptionGateState:
    accepted: tuple[AssumptionCase, ...] = ()
    rejected: tuple[AssumptionCase, ...] = ()
    bad_acceptance_reasons: tuple[str, ...] = ()


VALID_EXTERNAL_ORACLE = AssumptionCase(
    name="valid_external_oracle",
    boundary_kind="external_oracle",
)
VALID_SNAPSHOT = AssumptionCase(
    name="valid_snapshot",
    boundary_kind="local_snapshot",
)
MISSING_PRECONDITIONS = AssumptionCase(
    name="missing_preconditions",
    boundary_kind="external_oracle",
    has_preconditions=False,
)
MISSING_WHY_NOT_MODELED = AssumptionCase(
    name="missing_why_not_modeled",
    boundary_kind="external_oracle",
    has_why_not_modeled=False,
)
WEATHER_ALWAYS_SUNNY = AssumptionCase(
    name="weather_always_sunny",
    boundary_kind="external_condition",
    modelable_as_finite_states=True,
)
INVALIDATED_BY_CHANGED_BOUNDARY = AssumptionCase(
    name="invalidated_by_changed_boundary",
    boundary_kind="external_oracle",
    boundary_changed=True,
)
INTERNAL_EQUIVALENCE_CLAIM = AssumptionCase(
    name="internal_equivalence_claim",
    boundary_kind="internal_equivalence_claim",
)
HIDDEN_ASSUMPTION = AssumptionCase(
    name="hidden_assumption",
    boundary_kind="external_oracle",
    visible=False,
)


class SafeAssumptionGate:
    name = "SafeAssumptionGate"
    reads = ("accepted", "rejected")
    writes = ("accepted", "rejected", "bad_acceptance_reasons")

    def apply(self, input_obj: AssumptionCase, state: AssumptionGateState):
        rejection_reasons = _rejection_reasons(input_obj)
        if rejection_reasons:
            return (
                FunctionResult(
                    output=("rejected", rejection_reasons),
                    new_state=AssumptionGateState(
                        accepted=state.accepted,
                        rejected=state.rejected + (input_obj,),
                        bad_acceptance_reasons=state.bad_acceptance_reasons,
                    ),
                    label=f"rejected_{input_obj.name}",
                    reason="; ".join(rejection_reasons),
                ),
            )

        return (
            FunctionResult(
                output=("accepted", ()),
                new_state=AssumptionGateState(
                    accepted=state.accepted + (input_obj,),
                    rejected=state.rejected,
                    bad_acceptance_reasons=state.bad_acceptance_reasons,
                ),
                label=f"accepted_{input_obj.name}",
                reason="assumption stayed inside its explicit conditions",
            ),
        )


class BrokenAcceptAllAssumptionGate:
    name = "BrokenAcceptAllAssumptionGate"
    reads = ("accepted",)
    writes = ("accepted", "bad_acceptance_reasons")

    def apply(self, input_obj: AssumptionCase, state: AssumptionGateState):
        bad_reasons = _rejection_reasons(input_obj)
        return (
            FunctionResult(
                output=("accepted", bad_reasons),
                new_state=AssumptionGateState(
                    accepted=state.accepted + (input_obj,),
                    rejected=state.rejected,
                    bad_acceptance_reasons=state.bad_acceptance_reasons + bad_reasons,
                ),
                label=f"accepted_{input_obj.name}",
                reason="broken gate accepted without enforcing assumption conditions",
            ),
        )


def _rejection_reasons(case: AssumptionCase) -> tuple[str, ...]:
    reasons: list[str] = []
    if case.boundary_kind == "internal_equivalence_claim":
        reasons.append("assumes_the_result_being_checked")
    if not case.has_preconditions:
        reasons.append("missing_preconditions")
    if not case.has_why_not_modeled:
        reasons.append("missing_why_not_modeled")
    if case.modelable_as_finite_states:
        reasons.append("modelable_condition_should_be_state")
    if case.boundary_changed or not case.preconditions_hold:
        reasons.append("invalidated_preconditions")
    if not case.visible:
        reasons.append("hidden_assumption")
    return tuple(reasons)


def no_bad_assumption_acceptances(state: AssumptionGateState, trace) -> InvariantResult:
    del trace
    if state.bad_acceptance_reasons:
        return InvariantResult.fail(
            "invalid assumption was accepted",
            {"reasons": state.bad_acceptance_reasons},
        )
    return InvariantResult.pass_()


def no_internal_equivalence_claim_accepted(state: AssumptionGateState, trace) -> InvariantResult:
    del trace
    if any(case.boundary_kind == "internal_equivalence_claim" for case in state.accepted):
        return InvariantResult.fail("assumption tried to prove the thing being checked")
    return InvariantResult.pass_()


def accepted_assumptions_are_visible(state: AssumptionGateState, trace) -> InvariantResult:
    del trace
    if any(not case.visible for case in state.accepted):
        return InvariantResult.fail("accepted assumption was hidden from the report")
    return InvariantResult.pass_()


def accepted_assumptions_keep_preconditions(state: AssumptionGateState, trace) -> InvariantResult:
    del trace
    for case in state.accepted:
        if not case.has_preconditions or not case.preconditions_hold or case.boundary_changed:
            return InvariantResult.fail("accepted assumption no longer satisfies its preconditions")
    return InvariantResult.pass_()


def accepted_assumptions_are_not_modelable_conditions(
    state: AssumptionGateState,
    trace,
) -> InvariantResult:
    del trace
    if any(case.modelable_as_finite_states for case in state.accepted):
        return InvariantResult.fail("condition could be modeled as finite state instead of assumed")
    return InvariantResult.pass_()


def build_workflow(*, broken: bool = False) -> Workflow:
    gate = BrokenAcceptAllAssumptionGate() if broken else SafeAssumptionGate()
    return Workflow((gate,), name="assumption_card_safety")


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant(
            "no_bad_assumption_acceptances",
            "Assumptions must not be accepted after their conditions fail",
            no_bad_assumption_acceptances,
        ),
        Invariant(
            "no_internal_equivalence_claim_accepted",
            "Assumptions cannot assert the result being checked",
            no_internal_equivalence_claim_accepted,
        ),
        Invariant(
            "accepted_assumptions_are_visible",
            "Accepted assumptions must be visible in reports",
            accepted_assumptions_are_visible,
        ),
        Invariant(
            "accepted_assumptions_keep_preconditions",
            "Accepted assumptions must keep explicit preconditions",
            accepted_assumptions_keep_preconditions,
        ),
        Invariant(
            "accepted_assumptions_are_not_modelable_conditions",
            "Modelable external conditions should be modeled instead of assumed",
            accepted_assumptions_are_not_modelable_conditions,
        ),
    )


def all_cases() -> tuple[AssumptionCase, ...]:
    return (
        VALID_EXTERNAL_ORACLE,
        VALID_SNAPSHOT,
        MISSING_PRECONDITIONS,
        MISSING_WHY_NOT_MODELED,
        WEATHER_ALWAYS_SUNNY,
        INVALIDATED_BY_CHANGED_BOUNDARY,
        INTERNAL_EQUIVALENCE_CLAIM,
        HIDDEN_ASSUMPTION,
    )


def run_assumption_policy_check(*, broken: bool = False):
    return Explorer(
        workflow=build_workflow(broken=broken),
        initial_states=(AssumptionGateState(),),
        external_inputs=all_cases(),
        invariants=invariants(),
        max_sequence_length=1,
        required_labels=(
            "accepted_valid_external_oracle",
            "accepted_valid_snapshot",
            "rejected_missing_preconditions",
            "rejected_missing_why_not_modeled",
            "rejected_weather_always_sunny",
            "rejected_invalidated_by_changed_boundary",
            "rejected_internal_equivalence_claim",
            "rejected_hidden_assumption",
        ) if not broken else (),
        required_reachable=(
            ReachabilityCondition(
                "valid_external_assumption_can_be_accepted",
                lambda state, trace: VALID_EXTERNAL_ORACLE in state.accepted,
                "A valid external-boundary assumption remains usable.",
            ),
        ) if not broken else (),
    ).explore()


__all__ = [
    "AssumptionCase",
    "AssumptionGateState",
    "HIDDEN_ASSUMPTION",
    "INTERNAL_EQUIVALENCE_CLAIM",
    "INVALIDATED_BY_CHANGED_BOUNDARY",
    "MISSING_PRECONDITIONS",
    "MISSING_WHY_NOT_MODELED",
    "VALID_EXTERNAL_ORACLE",
    "VALID_SNAPSHOT",
    "WEATHER_ALWAYS_SUNNY",
    "all_cases",
    "build_workflow",
    "invariants",
    "run_assumption_policy_check",
]
