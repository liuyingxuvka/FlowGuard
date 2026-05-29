"""Template text for FlowGuard core route."""

from __future__ import annotations

MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models a sample validate-and-store workflow before related production changes.

Guards against:
- duplicate item storage when the same input is repeated;
- invalid inputs being stored as accepted records;
- stored outputs that cannot be traced to an Accepted output.

Use before editing:
validation, deduplication, storage, retry, or state-transition logic.

Run:
python run_checks.py

Replace this sample domain with the workflow under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class Input:
    item_id: str
    valid: bool


@dataclass(frozen=True)
class Accepted:
    item_id: str


@dataclass(frozen=True)
class Rejected:
    item_id: str
    reason: str


@dataclass(frozen=True)
class Stored:
    item_id: str


@dataclass(frozen=True)
class State:
    seen_ids: tuple[str, ...] = ()
    stored_ids: tuple[str, ...] = ()


class ValidateInput:
    name = "ValidateInput"
    reads = ("seen_ids",)
    writes = ("seen_ids",)
    accepted_input_type = Input
    input_description = "external abstract input"
    output_description = "Accepted or Rejected"
    idempotency = "Repeated item_id returns Rejected('duplicate') without changing state."

    def apply(self, input_obj: Input, state: State) -> Iterable[FunctionResult]:
        if not input_obj.valid:
            yield FunctionResult(
                output=Rejected(input_obj.item_id, "invalid"),
                new_state=state,
                label="rejected_invalid",
            )
            return
        if input_obj.item_id in state.seen_ids:
            yield FunctionResult(
                output=Rejected(input_obj.item_id, "duplicate"),
                new_state=state,
                label="rejected_duplicate",
            )
            return
        yield FunctionResult(
            output=Accepted(input_obj.item_id),
            new_state=replace(state, seen_ids=state.seen_ids + (input_obj.item_id,)),
            label="accepted",
        )


class StoreAccepted:
    name = "StoreAccepted"
    reads = ("stored_ids",)
    writes = ("stored_ids",)
    accepted_input_type = Accepted
    input_description = "Accepted"
    output_description = "Stored"
    idempotency = "Stores each accepted item once."

    def apply(self, input_obj: Accepted, state: State) -> Iterable[FunctionResult]:
        if input_obj.item_id in state.stored_ids:
            yield FunctionResult(
                output=Stored(input_obj.item_id),
                new_state=state,
                label="already_stored",
            )
            return
        yield FunctionResult(
            output=Stored(input_obj.item_id),
            new_state=replace(state, stored_ids=state.stored_ids + (input_obj.item_id,)),
            label="stored",
        )


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, Rejected)


def no_duplicate_stores(state: State, trace) -> InvariantResult:
    del trace
    if len(state.stored_ids) != len(set(state.stored_ids)):
        return InvariantResult.fail("stored_ids contains duplicates")
    return InvariantResult.pass_()


def every_store_was_accepted(state: State, trace) -> InvariantResult:
    del state
    accepted = {
        step.function_output.item_id
        for step in trace.steps
        if step.label == "accepted" and isinstance(step.function_output, Accepted)
    }
    stored = {
        step.function_output.item_id
        for step in trace.steps
        if step.label == "stored" and isinstance(step.function_output, Stored)
    }
    missing = tuple(sorted(stored - accepted))
    if missing:
        return InvariantResult.fail(f"stored without accepted source: {missing!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="no_duplicate_stores",
        description="stored_ids contains each item at most once",
        predicate=no_duplicate_stores,
    ),
    Invariant(
        name="every_store_was_accepted",
        description="Stored outputs must be traceable to Accepted outputs",
        predicate=every_store_was_accepted,
    ),
)


EXTERNAL_INPUTS = (
    Input("item_a", True),
    Input("item_bad", False),
)

MAX_SEQUENCE_LENGTH = 2


def initial_state() -> State:
    return State()


def build_workflow() -> Workflow:
    return Workflow((ValidateInput(), StoreAccepted()), name="model_template")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "Accepted",
    "Input",
    "Rejected",
    "State",
    "Stored",
    "build_workflow",
    "initial_state",
    "terminal_predicate",
]
'''

RUN_CHECKS_TEMPLATE = '''"""Run the minimal model_template checks."""

from __future__ import annotations

from flowguard import Explorer
import model


def main() -> int:
    report = Explorer(
        workflow=model.build_workflow(),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("stored", "rejected_duplicate"),
    ).explore()
    print(report.format_text())
    labels = sorted({label for trace in report.traces for label in trace.labels})
    print("labels: " + ",".join(labels))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

ADOPTION_LOG_TEMPLATE = """# flowguard Adoption Log

Use this file to keep a human-readable record of model-first work in this
project. Keep machine-readable entries in `.flowguard/adoption_log.jsonl` when
automation is available.

Each entry should record:

- task id;
- task summary;
- trigger reason;
- status: `in_progress`, `completed`, `blocked`, `skipped_with_reason`, or `failed`;
- model files touched;
- checks run;
- elapsed time;
- findings and counterexamples;
- skipped steps and reasons;
- risk evidence ledger summary for final confidence claims;
- friction points;
- next actions.

Do not use this log as a substitute for executable flowguard checks.
Do not treat `in_progress`, `blocked`, `skipped_with_reason`, or `failed` as
successful completion.
"""

MODEL_NOTES_TEMPLATE = """# flowguard Model Notes

## Scope

Describe the workflow boundary being modeled.

## Function Blocks

List each function block as `Input x State -> Set(Output x State)`.

## Invariants

List hard invariants that must not be weakened to pass checks.

## Scenario Review

Record expected-vs-observed scenario outcomes and counterexamples.

## Conformance Replay

Record production adapters, projection decisions, and replay outcomes.

## Known Limits

Record `needs_human_review` and known limitations honestly.
"""

__all__ = [
    'MODEL_TEMPLATE',
    'RUN_CHECKS_TEMPLATE',
    'ADOPTION_LOG_TEMPLATE',
    'MODEL_NOTES_TEMPLATE',
]
