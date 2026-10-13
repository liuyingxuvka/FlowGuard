"""TEMPLATE - copy to .flowguard/models/<your_model>.py and replace the order example.

Executable model: placing an order charges the customer at most once per order id.
Protected failure: a client retry with the same order id charges the card twice.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import FunctionResult, ReplayObservation, Workflow, at_most_once_by, replay_trace, select_covering_traces
from flowguard.explorer import Explorer
from flowguard.conformance import projected_output_matches, projected_state_matches

MODEL_ID = "order_placement"
COMPONENTS = ["orders"]
IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}


@dataclass(frozen=True)
class Place:
    order_id: str


@dataclass(frozen=True)
class State:
    orders: tuple = ()
    charges: tuple = ()


class PlaceOrder:
    """Intended design: a retry of a known order id is acknowledged, not charged again."""
    name = "PlaceOrder"
    reads = ("orders",)
    writes = ("orders", "charges")

    def apply(self, inp: Place, state: State):
        if inp.order_id in state.orders:
            return [FunctionResult("already_placed", state, label="idempotent_retry")]
        return [FunctionResult("placed", replace(state, orders=state.orders + (inp.order_id,),
                                                 charges=state.charges + (inp.order_id,)), label="first_charge")]


class ChargeEveryTime(PlaceOrder):
    """Known-bad variant: charges on every call."""

    def apply(self, inp: Place, state: State):
        orders = state.orders if inp.order_id in state.orders else state.orders + (inp.order_id,)
        return [FunctionResult("placed", replace(state, orders=orders, charges=state.charges + (inp.order_id,)),
                               label="charge")]


INVARIANTS = (at_most_once_by("one_charge_per_order", "a customer is charged at most once per order id", lambda s: s.charges, lambda c: c, "charge"),)
INPUTS = (Place("o1"), Place("o2"))


def _explorer(block) -> Explorer:
    return Explorer(workflow=Workflow((block,)), initial_states=(State(),), external_inputs=INPUTS,
                    invariants=INVARIANTS, max_sequence_length=3, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(PlaceOrder())


def broken_variants() -> dict:
    return {"charge_every_time": _explorer(ChargeEveryTime())}


class _Adapter:
    """Drive the real OrderService with the model's trace and project its state."""

    def reset(self, initial_state):
        from shop.orders import OrderService
        self.svc = OrderService()

    def apply_step(self, step):
        output = self.svc.place(step.function_input.order_id, 1)
        return ReplayObservation(function_name=step.function_name, observed_output=output,
                                 observed_state=self.observe_state())

    def observe_state(self):
        return State(orders=tuple(self.svc.orders), charges=tuple(self.svc.charges))

    def observe_output(self):
        return None


def conformance():
    """Replay traces that cover every modeled transition against the real code; return the first failure."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        last = replay_trace(trace=trace, adapter=_Adapter(), invariants=INVARIANTS,
                            rules=(projected_state_matches(), projected_output_matches()))
        if not last.ok:
            return last
    return last
