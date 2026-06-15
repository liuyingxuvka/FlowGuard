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
- stored outputs that cannot be traced to an Accepted output;
- completed outputs that do not have durable completion evidence.

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
class Completed:
    item_id: str


@dataclass(frozen=True)
class State:
    seen_ids: tuple[str, ...] = ()
    stored_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    completed_ids: tuple[str, ...] = ()


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


class RecordCompletionEvidence:
    name = "RecordCompletionEvidence"
    reads = ("stored_ids", "evidence_ids", "completed_ids")
    writes = ("evidence_ids", "completed_ids")
    accepted_input_type = Stored
    input_description = "Stored"
    output_description = "Completed"
    idempotency = "Completion is recorded once only after storage evidence exists."

    def apply(self, input_obj: Stored, state: State) -> Iterable[FunctionResult]:
        if input_obj.item_id not in state.stored_ids:
            return
        if input_obj.item_id in state.completed_ids:
            yield FunctionResult(
                output=Completed(input_obj.item_id),
                new_state=state,
                label="already_completed",
            )
            return
        yield FunctionResult(
            output=Completed(input_obj.item_id),
            new_state=replace(
                state,
                evidence_ids=state.evidence_ids + (input_obj.item_id,),
                completed_ids=state.completed_ids + (input_obj.item_id,),
            ),
            label="completed_with_evidence",
        )


class BrokenCompleteWithoutEvidence(RecordCompletionEvidence):
    name = "BrokenCompleteWithoutEvidence"

    def apply(self, input_obj: Stored, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            output=Completed(input_obj.item_id),
            new_state=replace(state, completed_ids=state.completed_ids + (input_obj.item_id,)),
            label="completed_without_evidence",
        )


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, (Rejected, Completed))


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


def completion_requires_evidence(state: State, trace) -> InvariantResult:
    del trace
    missing = tuple(item_id for item_id in state.completed_ids if item_id not in state.evidence_ids)
    if missing:
        return InvariantResult.fail(f"completed without evidence: {missing!r}")
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
    Invariant(
        name="completion_requires_evidence",
        description="Completed outputs must have durable completion evidence",
        predicate=completion_requires_evidence,
        metadata={"property_classes": ("completion_evidence", "known_bad_case")},
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
    return Workflow((ValidateInput(), StoreAccepted(), RecordCompletionEvidence()), name="model_template")


def broken_workflow() -> Workflow:
    return Workflow((ValidateInput(), StoreAccepted(), BrokenCompleteWithoutEvidence()), name="model_template_broken")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "Accepted",
    "Completed",
    "Input",
    "Rejected",
    "State",
    "Stored",
    "broken_workflow",
    "build_workflow",
    "initial_state",
    "terminal_predicate",
]
'''

RUN_CHECKS_TEMPLATE = '''"""Run the formal minimum valuable model_template checks."""

from __future__ import annotations

from flowguard import (
    FlowGuardCheckPlan,
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    TemplateHarvestReview,
    TemplateReuseReview,
    run_model_first_checks,
)
import model


def build_plan(workflow, known_bad_proofs=()):
    return FlowGuardCheckPlan(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("stored", "completed_with_evidence", "rejected_duplicate"),
        risk_profile=RiskProfile(
            modeled_boundary="validate-store-complete sample workflow",
            risk_classes=("deduplication", "side_effect"),
            risk_intent=RiskIntent(
                failure_modes=("completion without durable evidence", "duplicate item storage"),
                protected_error_classes=("premature_completion", "duplicate_side_effect"),
                protected_harms=("caller trusts an output that was not durably recorded",),
                must_model_state=("seen_ids", "stored_ids", "evidence_ids", "completed_ids"),
                must_model_side_effects=("storage_write", "completion_record"),
                completion_evidence=("evidence_ids",),
                adversarial_inputs=("same item repeated", "invalid item", "completion after partial work"),
                hard_invariants=("completed ids have evidence", "stored ids are accepted once"),
                known_bad_cases=("complete_without_evidence",),
                used_template_ids=("completion_requires_evidence", "side_effect_at_most_once"),
                blindspots=("production storage adapter replay is outside this sample template",),
            ),
        ),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=("completion_requires_evidence", "side_effect_at_most_once"),
            searched_layers=("public", "local"),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=("premature_completion", "duplicate_side_effect"),
            modeled_state=("seen_ids", "stored_ids", "evidence_ids", "completed_ids"),
            modeled_side_effects=("storage_write", "completion_record"),
            completion_evidence=("evidence_ids",),
            known_bad_cases=("complete_without_evidence",),
        ),
        known_bad_proofs=known_bad_proofs,
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        scenario_matrix_config={"enabled": False},
    )


def known_bad_proof_from_broken_summary(summary):
    sections = {section.name: section for section in summary.sections}
    model_status = sections["model_check"].status
    caught = model_status == "failed"
    return KnownBadProof(
        "complete_without_evidence",
        protected_error_class="premature_completion",
        method="formal_broken_workflow",
        expected_failure="failed",
        observed_status="failed" if caught else "passed",
        observed_failure=(
            "completion_requires_evidence caught BrokenCompleteWithoutEvidence"
            if caught
            else "BrokenCompleteWithoutEvidence unexpectedly passed"
        ),
        evidence_id="model:model_template_broken",
    )


def main() -> int:
    broken_summary = run_model_first_checks(build_plan(model.broken_workflow()))
    proof = known_bad_proof_from_broken_summary(broken_summary)
    report = run_model_first_checks(build_plan(model.build_workflow(), known_bad_proofs=(proof,)))
    sections = {section.name: section for section in report.sections}
    runnable_ok = (
        sections["model_check"].status == "pass"
        and sections["known_bad_proof"].status == "pass"
        and proof.observed_status == "failed"
    )
    print(f"status: {'OK' if runnable_ok else 'BLOCKED'}")
    print(report.format_text())
    print(f"known_bad_without_evidence_rejected: {'yes' if proof.observed_status == 'failed' else 'no'}")
    model_report = dict(report.metadata)["model_check_report"]
    labels = sorted({label for trace in model_report.traces for label in trace.labels})
    print("labels: " + ",".join(labels))
    expected_labels = {"stored", "completed_with_evidence", "rejected_duplicate"}
    return 0 if (
        runnable_ok
        and proof.observed_status == "failed"
        and expected_labels.issubset(labels)
    ) else 1


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
