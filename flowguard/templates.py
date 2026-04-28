"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


MODEL_TEMPLATE = '''"""Minimal flowguard model template."""

from dataclasses import dataclass

from flowguard.core import FunctionResult, Invariant, InvariantResult
from flowguard.workflow import Workflow


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


@dataclass(frozen=True)
class Input:
    item_id: str


@dataclass(frozen=True)
class Output:
    item_id: str
    status: str


class RecordItem:
    name = "RecordItem"
    reads = ("records",)
    writes = ("records",)
    input_description = "Input"
    output_description = "Output"
    idempotency = "same item_id is recorded at most once"
    accepted_input_type = Input

    def apply(self, input_obj, state):
        if input_obj.item_id in state.records:
            return (
                FunctionResult(
                    Output(input_obj.item_id, "already_exists"),
                    state,
                    label="record_already_exists",
                    reason="item was already recorded",
                ),
            )
        new_state = State(records=state.records + (input_obj.item_id,))
        return (
            FunctionResult(
                Output(input_obj.item_id, "added"),
                new_state,
                label="record_added",
                reason="item was recorded once",
            ),
        )


def no_duplicate_records():
    def predicate(state, _trace):
        if len(state.records) != len(set(state.records)):
            return InvariantResult.fail("duplicate records")
        return InvariantResult.pass_()

    return Invariant("no_duplicate_records", "records are unique", predicate)


def build_workflow():
    return Workflow((RecordItem(),), name="template_workflow")
'''


RUN_CHECKS_TEMPLATE = '''"""Run the minimal flowguard template."""

from flowguard.scenario import Scenario, ScenarioExpectation, run_exact_sequence
from flowguard.review import review_scenario

from model import Input, State, build_workflow, no_duplicate_records


def main():
    scenario = Scenario(
        name="record_same_item_twice",
        description="Repeated input must not create duplicate records.",
        initial_state=State(),
        external_input_sequence=(Input("item-1"), Input("item-1")),
        expected=ScenarioExpectation(expected_status="ok"),
        workflow=build_workflow(),
        invariants=(no_duplicate_records(),),
    )
    result = review_scenario(scenario)
    print(result.observed_summary)
    print(result.status)
    return 0 if result.status == "pass" else 1


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


def project_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("model.py", MODEL_TEMPLATE),
        TemplateFile("run_checks.py", RUN_CHECKS_TEMPLATE),
    )


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("docs/flowguard_adoption_log.md", ADOPTION_LOG_TEMPLATE),
        TemplateFile("docs/flowguard_model_notes.md", MODEL_NOTES_TEMPLATE),
    )


__all__ = [
    "ADOPTION_LOG_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "TemplateFile",
    "adoption_template_files",
    "project_template_files",
]
