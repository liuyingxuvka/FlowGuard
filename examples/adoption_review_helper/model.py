"""Model the lightweight adoption-review helper classification rules."""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow


@dataclass(frozen=True)
class EvidenceObservation:
    project: str
    has_jsonl: bool
    has_markdown: bool
    has_model_file: bool
    status: str = ""
    has_commands: bool = False
    has_command_failure: bool = False
    has_finding: bool = False
    has_skipped_step: bool = False
    mentions_fallback: bool = False


@dataclass(frozen=True)
class ReviewState:
    project: str = ""
    has_jsonl: bool = False
    has_markdown: bool = False
    has_model_file: bool = False
    status: str = ""
    has_commands: bool = False
    has_command_failure: bool = False
    has_finding: bool = False
    has_skipped_step: bool = False
    mentions_fallback: bool = False
    classification: str = "new"


class LoadEvidence:
    name = "LoadEvidence"
    accepted_input_type = EvidenceObservation
    reads = ("evidence_files",)
    writes = ("review_state",)
    input_description = "observed project evidence"
    output_description = "loaded evidence state"
    idempotency = "same project evidence maps to one review state"

    def apply(self, input_obj: EvidenceObservation, _state: ReviewState):
        yield FunctionResult(
            input_obj,
            ReviewState(
                project=input_obj.project,
                has_jsonl=input_obj.has_jsonl,
                has_markdown=input_obj.has_markdown,
                has_model_file=input_obj.has_model_file,
                status=input_obj.status,
                has_commands=input_obj.has_commands,
                has_command_failure=input_obj.has_command_failure,
                has_finding=input_obj.has_finding,
                has_skipped_step=input_obj.has_skipped_step,
                mentions_fallback=input_obj.mentions_fallback,
            ),
            label="evidence_loaded",
            reason="project evidence was normalized into a small review state",
        )


class ClassifyEvidence:
    name = "ClassifyEvidence"
    accepted_input_type = EvidenceObservation
    reads = ("review_state",)
    writes = ("classification",)
    input_description = "loaded evidence state"
    output_description = "evidence classification"
    idempotency = "classification is deterministic for the evidence summary"

    def apply(self, _input_obj: EvidenceObservation, state: ReviewState):
        if state.mentions_fallback:
            classification = "historical_fallback"
        elif state.status in {"blocked", "failed"}:
            classification = "blocked_or_failed"
        elif state.status == "in_progress":
            classification = "in_progress"
        elif (
            state.status == "completed"
            and state.has_commands
            and not state.has_command_failure
            and state.has_skipped_step
        ):
            classification = "complete_with_skips"
        elif state.status == "completed" and state.has_commands and not state.has_command_failure:
            classification = "complete"
        elif state.has_jsonl and (state.has_commands or state.has_finding):
            classification = "useful_but_incomplete"
        elif state.has_markdown or state.has_model_file:
            classification = "in_progress"
        else:
            classification = "no_evidence"
        yield FunctionResult(
            classification,
            ReviewState(
                project=state.project,
                has_jsonl=state.has_jsonl,
                has_markdown=state.has_markdown,
                has_model_file=state.has_model_file,
                status=state.status,
                has_commands=state.has_commands,
                has_command_failure=state.has_command_failure,
                has_finding=state.has_finding,
                has_skipped_step=state.has_skipped_step,
                mentions_fallback=state.mentions_fallback,
                classification=classification,
            ),
            label=f"classified_{classification}",
            reason="classified adoption evidence without requiring a large form",
        )


def complete_requires_jsonl_and_commands() -> Invariant:
    def predicate(state: ReviewState, _trace):
        if state.classification == "complete" and not (state.has_jsonl and state.has_commands):
            return InvariantResult.fail("complete evidence requires JSONL and commands")
        return InvariantResult.pass_()

    return Invariant(
        "complete_requires_jsonl_and_commands",
        "Complete evidence must include machine-readable log and checks run.",
        predicate,
    )


def command_failure_not_complete() -> Invariant:
    def predicate(state: ReviewState, _trace):
        if state.classification == "complete" and state.has_command_failure:
            return InvariantResult.fail("command failure evidence cannot be collapsed into complete")
        return InvariantResult.pass_()

    return Invariant(
        "command_failure_not_complete",
        "Failed commands preserved as evidence should not be classified as fully complete.",
        predicate,
    )


def skipped_steps_not_hidden() -> Invariant:
    def predicate(state: ReviewState, _trace):
        if state.has_skipped_step and state.classification == "complete":
            return InvariantResult.fail("skipped steps must not be hidden under plain complete")
        return InvariantResult.pass_()

    return Invariant(
        "skipped_steps_not_hidden",
        "Completed evidence with skipped steps should be visibly classified.",
        predicate,
    )


def fallback_is_historical() -> Invariant:
    def predicate(state: ReviewState, _trace):
        if state.mentions_fallback and state.classification != "historical_fallback":
            return InvariantResult.fail("fallback evidence must stay historical/partial")
        return InvariantResult.pass_()

    return Invariant(
        "fallback_is_historical",
        "Old fallback models are useful history, not full formal adoption.",
        predicate,
    )


INVARIANTS = (
    complete_requires_jsonl_and_commands(),
    command_failure_not_complete(),
    skipped_steps_not_hidden(),
    fallback_is_historical(),
)


def build_workflow() -> Workflow:
    return Workflow((LoadEvidence(), ClassifyEvidence()), name="adoption_review_helper")


def scenarios() -> tuple[Scenario, ...]:
    workflow = build_workflow()
    return (
        Scenario(
            name="ARH01_complete_evidence",
            description="JSONL plus successful checks can be complete.",
            initial_state=ReviewState(),
            external_input_sequence=(
                EvidenceObservation(
                    "Khaos Brain",
                    has_jsonl=True,
                    has_markdown=True,
                    has_model_file=True,
                    status="completed",
                    has_commands=True,
                    has_finding=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("classified_complete",),
                summary="OK; complete evidence stays lightweight",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="ARH02_markdown_only_is_in_progress",
            description="Markdown/model evidence without JSONL should not be called complete.",
            initial_state=ReviewState(),
            external_input_sequence=(
                EvidenceObservation(
                    "WaermeCheck",
                    has_jsonl=False,
                    has_markdown=True,
                    has_model_file=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("classified_in_progress",),
                summary="OK; thin evidence is pending, not failure",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="ARH03_completed_with_failed_command_is_incomplete",
            description="Completed task with preserved failed command evidence is useful but incomplete.",
            initial_state=ReviewState(),
            external_input_sequence=(
                EvidenceObservation(
                    "FlowGuard release",
                    has_jsonl=True,
                    has_markdown=True,
                    has_model_file=True,
                    status="completed",
                    has_commands=True,
                    has_command_failure=True,
                    has_finding=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("classified_useful_but_incomplete",),
                summary="OK; command failure evidence is visible",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="ARH04_fallback_stays_historical",
            description="Old fallback models should be retained but classified separately.",
            initial_state=ReviewState(),
            external_input_sequence=(
                EvidenceObservation(
                    "older pilot",
                    has_jsonl=True,
                    has_markdown=True,
                    has_model_file=True,
                    status="completed",
                    has_commands=True,
                    has_finding=True,
                    mentions_fallback=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("classified_historical_fallback",),
                summary="OK; fallback evidence remains historical",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="ARH05_completed_with_skips_is_visible",
            description="Completed work with skipped steps should stay complete but visibly qualified.",
            initial_state=ReviewState(),
            external_input_sequence=(
                EvidenceObservation(
                    "Job-Hunter",
                    has_jsonl=True,
                    has_markdown=True,
                    has_model_file=True,
                    status="completed",
                    has_commands=True,
                    has_finding=True,
                    has_skipped_step=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("classified_complete_with_skips",),
                summary="OK; completed evidence keeps skipped-step caveat visible",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
    )


__all__ = [
    "EvidenceObservation",
    "ReviewState",
    "INVARIANTS",
    "build_workflow",
    "scenarios",
]
