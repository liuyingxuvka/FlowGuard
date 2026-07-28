"""FlowGuard self-model for ModelMesh closure meta-model design."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import FrozenSet, Tuple

from flowguard import FunctionBlock, FunctionResult, Invariant, state_invariant


@dataclass(frozen=True)
class ClosureInput:
    token: str


@dataclass(frozen=True)
class ClosureState:
    produced: FrozenSet[str] = frozenset()
    consumed: FrozenSet[str] = frozenset()
    required: FrozenSet[str] = frozenset()
    joins: FrozenSet[str] = frozenset()
    terminal: bool = False
    normal_exit: bool = False
    violations: Tuple[str, ...] = ()

    @property
    def pending(self) -> FrozenSet[str]:
        return frozenset(self.required - self.consumed)


class StartRoot(FunctionBlock):
    name = "StartRoot"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "root_start":
            return (FunctionResult(input_value, state),)
        return (
            FunctionResult(
                ClosureInput("payment_request"),
                replace(
                    state,
                    produced=state.produced | {"root_start", "payment_request"},
                    required=state.required | {"payment_result", "inventory_result"},
                ),
                label="root_started",
            ),
        )


class ChildPayment(FunctionBlock):
    name = "ChildPayment"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "payment_request":
            return (FunctionResult(input_value, state),)
        return (
            FunctionResult(
                ClosureInput("payment_result"),
                replace(state, produced=state.produced | {"payment_result"}),
                label="payment_done",
            ),
        )


class ConsumePayment(FunctionBlock):
    name = "ConsumePayment"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "payment_result":
            return (FunctionResult(input_value, state),)
        return (
            FunctionResult(
                ClosureInput("inventory_result"),
                replace(
                    state,
                    produced=state.produced | {"inventory_result"},
                    consumed=state.consumed | {"payment_result", "inventory_result"},
                    joins=state.joins | {"checkout_ready"},
                ),
                label="payment_consumed",
            ),
        )


class FinishOrder(FunctionBlock):
    name = "FinishOrder"
    accepted_input_type = ClosureInput

    def apply(self, input_value, state):
        if input_value.token != "inventory_result":
            return (FunctionResult(input_value, state),)
        if "checkout_ready" not in state.joins:
            return (
                FunctionResult(
                    input_value,
                    replace(state, violations=state.violations + ("missing_join",)),
                    label="missing_join",
                ),
            )
        return (
            FunctionResult(
                ClosureInput("order_complete"),
                replace(state, terminal=True, normal_exit=True),
                label="normal_exit",
            ),
        )


def closure_invariant(state, trace):
    if state.violations:
        return False
    if state.terminal:
        return state.normal_exit and not state.pending
    return True


def build_blocks():
    return (StartRoot(), ChildPayment(), ConsumePayment(), FinishOrder())


invariants = (
    Invariant(
        "mesh_closure_no_pending_required_outputs",
        "mesh closure leaves no pending required output at terminal",
        closure_invariant,
    ),
)


def initial_state() -> ClosureState:
    return ClosureState()


def external_inputs():
    return (ClosureInput("root_start"),)


terminal_predicate = lambda current_output, state, trace: bool(state.terminal)
