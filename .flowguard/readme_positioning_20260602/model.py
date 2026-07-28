"""FlowGuard README positioning maintenance model.

Purpose:
Guard the README rewrite requested on 2026-06-02 so the public first screen
leads with the AI-coding maintenance-debt problem, then explains FlowGuard's
mechanism and boundaries.

Guards against:
- rewriting the README as mechanism-first finite-state-model copy again;
- claiming FlowGuard absolutely prevents bugs or replaces tests;
- publishing to GitHub while the user explicitly scoped this to local README
  maintenance.

Run:
python .flowguard/readme_positioning_20260602/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class ReadmeAction:
    action_type: str


@dataclass(frozen=True)
class ReadmeOutput:
    status: str


@dataclass(frozen=True)
class ReadmeState:
    facts_checked: bool = False
    logic_model_ready: bool = False
    positioning: str = "none"
    overclaim_present: bool = False
    validation_status: str = "none"
    github_status: str = "not_touched"
    done_claim: str = "none"

    def can_claim_done(self) -> bool:
        return (
            self.facts_checked
            and self.logic_model_ready
            and self.positioning == "pain_first"
            and not self.overclaim_present
            and self.validation_status == "passed"
            and self.github_status != "published"
        )


class CorrectReadmeRewriteGate:
    name = "CorrectReadmeRewriteGate"
    accepted_input_type = ReadmeAction
    reads = (
        "facts_checked",
        "logic_model_ready",
        "positioning",
        "overclaim_present",
        "validation_status",
        "github_status",
        "done_claim",
    )
    writes = reads
    input_description = "README rewrite lifecycle action"
    output_description = "README positioning state update"
    idempotency = "Repeated local README checks must not turn into GitHub publication."

    def apply(self, input_obj: ReadmeAction, state: ReadmeState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "inspect_repo":
            yield FunctionResult(
                ReadmeOutput("facts_checked"),
                replace(state, facts_checked=True),
                label="facts_checked",
            )
            return
        if action == "build_logic_model":
            if not state.facts_checked:
                yield FunctionResult(ReadmeOutput("model_waiting_for_facts"), state, label="blocked")
                return
            yield FunctionResult(
                ReadmeOutput("logic_model_ready"),
                replace(state, logic_model_ready=True),
                label="logic_model_ready",
            )
            return
        if action == "write_pain_first":
            if not state.logic_model_ready:
                yield FunctionResult(ReadmeOutput("rewrite_waiting_for_model"), state, label="blocked")
                return
            yield FunctionResult(
                ReadmeOutput("readme_pain_first"),
                replace(
                    state,
                    positioning="pain_first",
                    overclaim_present=False,
                    validation_status="stale",
                ),
                label="pain_first_written",
            )
            return
        if action == "write_mechanism_first":
            yield FunctionResult(ReadmeOutput("mechanism_first_rejected"), state, label="blocked")
            return
        if action == "write_absolute_guarantee":
            yield FunctionResult(ReadmeOutput("overclaim_rejected"), state, label="blocked")
            return
        if action == "validate_readme":
            if state.positioning != "pain_first" or state.overclaim_present:
                yield FunctionResult(ReadmeOutput("validation_rejected"), state, label="blocked")
                return
            yield FunctionResult(
                ReadmeOutput("validation_passed"),
                replace(state, validation_status="passed"),
                label="validation_passed",
            )
            return
        if action == "publish_github":
            yield FunctionResult(
                ReadmeOutput("github_publish_deferred"),
                replace(state, github_status="deferred"),
                label="github_deferred",
            )
            return
        if action == "claim_done":
            claim = "accepted" if state.can_claim_done() else "rejected"
            yield FunctionResult(
                ReadmeOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )


class BrokenReadmeRewriteGate(CorrectReadmeRewriteGate):
    name = "BrokenReadmeRewriteGate"
    idempotency = "Broken variant accepts mechanism-first copy, overclaims, and publication."

    def apply(self, input_obj: ReadmeAction, state: ReadmeState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "write_mechanism_first":
            yield FunctionResult(
                ReadmeOutput("readme_mechanism_first"),
                replace(state, positioning="mechanism_first", validation_status="stale"),
                label="mechanism_first_written",
            )
            return
        if action == "write_absolute_guarantee":
            yield FunctionResult(
                ReadmeOutput("absolute_guarantee_written"),
                replace(state, overclaim_present=True, validation_status="stale"),
                label="overclaim_written",
            )
            return
        if action == "publish_github":
            yield FunctionResult(
                ReadmeOutput("github_published"),
                replace(state, github_status="published"),
                label="github_published",
            )
            return
        if action == "claim_done":
            claim = "accepted" if state.positioning != "none" else "rejected"
            yield FunctionResult(
                ReadmeOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, ReadmeOutput) and current_output.status.startswith("done_")


def done_claim_requires_safe_positioning(state: ReadmeState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.can_claim_done():
        return InvariantResult.fail(
            "done accepted without pain-first positioning, no-overclaim validation, and local-only scope"
        )
    return InvariantResult.pass_()


def github_publication_stays_deferred(state: ReadmeState, trace) -> InvariantResult:
    del trace
    if state.github_status == "published":
        return InvariantResult.fail("GitHub publication occurred despite local-only user scope")
    return InvariantResult.pass_()


def mechanism_first_copy_is_not_final(state: ReadmeState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and state.positioning == "mechanism_first":
        return InvariantResult.fail("mechanism-first README copy was accepted as final")
    return InvariantResult.pass_()


def absolute_guarantee_is_not_final(state: ReadmeState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and state.overclaim_present:
        return InvariantResult.fail("absolute bug-prevention guarantee was accepted as final")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "done_claim_requires_safe_positioning",
        "README completion requires pain-first positioning, validation, and no GitHub publication.",
        done_claim_requires_safe_positioning,
    ),
    Invariant(
        "github_publication_stays_deferred",
        "The user scoped this task to local README maintenance, so GitHub publication stays deferred.",
        github_publication_stays_deferred,
    ),
    Invariant(
        "mechanism_first_copy_is_not_final",
        "The rewritten README must not return to a mechanism-first first screen.",
        mechanism_first_copy_is_not_final,
    ),
    Invariant(
        "absolute_guarantee_is_not_final",
        "The README must not claim FlowGuard absolutely prevents bugs or replaces tests.",
        absolute_guarantee_is_not_final,
    ),
)

EXTERNAL_INPUTS = (
    ReadmeAction("inspect_repo"),
    ReadmeAction("build_logic_model"),
    ReadmeAction("write_pain_first"),
    ReadmeAction("write_mechanism_first"),
    ReadmeAction("write_absolute_guarantee"),
    ReadmeAction("validate_readme"),
    ReadmeAction("publish_github"),
    ReadmeAction("claim_done"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> ReadmeState:
    return ReadmeState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectReadmeRewriteGate(),), name="readme_positioning_correct")


def build_broken_workflow() -> Workflow:
    return Workflow((BrokenReadmeRewriteGate(),), name="readme_positioning_broken")
