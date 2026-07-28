"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models task-local prediction freezing, independent production replay, candidate
model revision, acceptance, rejection, and rollback.

Guards against:
- treating a status-only ``pass`` as real conformance evidence;
- allowing a production adapter to receive the model's expected output;
- accepting a candidate task model before every required replay passes;
- losing the base task model when a candidate is rejected or rolled back.

Use before editing:
conformance replay, task-local model revision, production summary gating, or
exact runtime-path occurrence checks.

Run:
python .flowguard/task_local_prediction_replay/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class PredictionRequest:
    request_id: str
    adapter_independent: bool
    current_report: bool
    replay_matches: bool
    required_replays_pass: bool


@dataclass(frozen=True)
class PredictionFrozen:
    request_id: str
    current_report: bool
    replay_matches: bool
    required_replays_pass: bool


@dataclass(frozen=True)
class ReplayObserved:
    request_id: str
    current_report: bool
    replay_matches: bool
    required_replays_pass: bool


@dataclass(frozen=True)
class RevisionProposed:
    request_id: str
    current_report: bool
    replay_matches: bool
    required_replays_pass: bool


@dataclass(frozen=True)
class RevisionAccepted:
    request_id: str


@dataclass(frozen=True)
class RevisionRejected:
    request_id: str
    reason: str


@dataclass(frozen=True)
class RevisionRolledBack:
    request_id: str


@dataclass(frozen=True)
class State:
    base_model_ids: tuple[str, ...] = ()
    frozen_prediction_ids: tuple[str, ...] = ()
    independent_adapter_ids: tuple[str, ...] = ()
    current_report_ids: tuple[str, ...] = ()
    matching_replay_ids: tuple[str, ...] = ()
    proposed_candidate_ids: tuple[str, ...] = ()
    accepted_candidate_ids: tuple[str, ...] = ()
    rejected_candidate_ids: tuple[str, ...] = ()
    rolled_back_candidate_ids: tuple[str, ...] = ()
    active_candidate_ids: tuple[str, ...] = ()


class FreezePrediction:
    name = "FreezePrediction"
    reads = ()
    writes = (
        "base_model_ids",
        "frozen_prediction_ids",
        "independent_adapter_ids",
    )
    accepted_input_type = PredictionRequest
    input_description = "task model and pre-observation prediction request"
    output_description = "PredictionFrozen or RevisionRejected"

    def apply(self, input_obj: PredictionRequest, state: State) -> Iterable[FunctionResult]:
        if not input_obj.adapter_independent:
            yield FunctionResult(
                RevisionRejected(input_obj.request_id, "adapter_received_expected_output"),
                replace(
                    state,
                    base_model_ids=state.base_model_ids + (input_obj.request_id,),
                    rejected_candidate_ids=state.rejected_candidate_ids + (input_obj.request_id,),
                ),
                label="adapter_rejected",
            )
            return
        yield FunctionResult(
            PredictionFrozen(
                input_obj.request_id,
                input_obj.current_report,
                input_obj.replay_matches,
                input_obj.required_replays_pass,
            ),
            replace(
                state,
                base_model_ids=state.base_model_ids + (input_obj.request_id,),
                frozen_prediction_ids=state.frozen_prediction_ids + (input_obj.request_id,),
                independent_adapter_ids=state.independent_adapter_ids + (input_obj.request_id,),
            ),
            label="prediction_frozen",
        )


class ReplayProduction:
    name = "ReplayProduction"
    reads = ("frozen_prediction_ids",)
    writes = ("current_report_ids", "matching_replay_ids")
    accepted_input_type = PredictionFrozen
    input_description = "frozen prediction"
    output_description = "ReplayObserved"

    def apply(self, input_obj: PredictionFrozen, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            ReplayObserved(
                input_obj.request_id,
                input_obj.current_report,
                input_obj.replay_matches,
                input_obj.required_replays_pass,
            ),
            replace(
                state,
                current_report_ids=(
                    state.current_report_ids + (input_obj.request_id,)
                    if input_obj.current_report
                    else state.current_report_ids
                ),
                matching_replay_ids=(
                    state.matching_replay_ids + (input_obj.request_id,)
                    if input_obj.current_report and input_obj.replay_matches
                    else state.matching_replay_ids
                ),
            ),
            label=(
                "replay_matched"
                if input_obj.current_report and input_obj.replay_matches
                else "replay_blocked"
            ),
        )


class ProposeRevision:
    name = "ProposeRevision"
    reads = ("base_model_ids", "frozen_prediction_ids")
    writes = ("proposed_candidate_ids",)
    accepted_input_type = ReplayObserved
    input_description = "production replay result"
    output_description = "RevisionProposed"

    def apply(self, input_obj: ReplayObserved, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            RevisionProposed(
                input_obj.request_id,
                input_obj.current_report,
                input_obj.replay_matches,
                input_obj.required_replays_pass,
            ),
            replace(
                state,
                proposed_candidate_ids=state.proposed_candidate_ids + (input_obj.request_id,),
            ),
            label="revision_proposed",
        )


class DecideRevision:
    name = "DecideRevision"
    reads = (
        "independent_adapter_ids",
        "current_report_ids",
        "matching_replay_ids",
        "proposed_candidate_ids",
    )
    writes = (
        "accepted_candidate_ids",
        "rejected_candidate_ids",
        "active_candidate_ids",
    )
    accepted_input_type = RevisionProposed
    input_description = "candidate task-model revision"
    output_description = "RevisionAccepted or RevisionRejected"

    def apply(self, input_obj: RevisionProposed, state: State) -> Iterable[FunctionResult]:
        ready = (
            input_obj.request_id in state.independent_adapter_ids
            and input_obj.request_id in state.current_report_ids
            and input_obj.request_id in state.matching_replay_ids
            and input_obj.required_replays_pass
        )
        if not ready:
            yield FunctionResult(
                RevisionRejected(input_obj.request_id, "required_replay_evidence_missing"),
                replace(
                    state,
                    rejected_candidate_ids=state.rejected_candidate_ids + (input_obj.request_id,),
                ),
                label="revision_rejected",
            )
            return
        yield FunctionResult(
            RevisionAccepted(input_obj.request_id),
            replace(
                state,
                accepted_candidate_ids=state.accepted_candidate_ids + (input_obj.request_id,),
                active_candidate_ids=state.active_candidate_ids + (input_obj.request_id,),
            ),
            label="revision_accepted",
        )


class RollbackRevision:
    name = "RollbackRevision"
    reads = ("accepted_candidate_ids", "active_candidate_ids")
    writes = ("rolled_back_candidate_ids", "active_candidate_ids")
    accepted_input_type = RevisionAccepted
    input_description = "accepted candidate selected for rollback"
    output_description = "RevisionRolledBack"

    def apply(self, input_obj: RevisionAccepted, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            RevisionRolledBack(input_obj.request_id),
            replace(
                state,
                rolled_back_candidate_ids=state.rolled_back_candidate_ids + (input_obj.request_id,),
                active_candidate_ids=tuple(
                    item for item in state.active_candidate_ids if item != input_obj.request_id
                ),
            ),
            label="revision_rolled_back",
        )


class BrokenStatusOnlyReplay(ReplayProduction):
    name = "BrokenStatusOnlyReplay"

    def apply(self, input_obj: PredictionFrozen, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            ReplayObserved(
                input_obj.request_id,
                True,
                True,
                input_obj.required_replays_pass,
            ),
            replace(
                state,
                current_report_ids=state.current_report_ids + (input_obj.request_id,),
                matching_replay_ids=state.matching_replay_ids + (input_obj.request_id,),
            ),
            label="status_only_pass_accepted",
        )


class BrokenExpectedOutputAdapter(FreezePrediction):
    name = "BrokenExpectedOutputAdapter"

    def apply(self, input_obj: PredictionRequest, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            PredictionFrozen(
                input_obj.request_id,
                input_obj.current_report,
                input_obj.replay_matches,
                input_obj.required_replays_pass,
            ),
            replace(
                state,
                base_model_ids=state.base_model_ids + (input_obj.request_id,),
                frozen_prediction_ids=state.frozen_prediction_ids + (input_obj.request_id,),
            ),
            label="prediction_frozen_with_leaking_adapter",
        )


class BrokenAcceptWithoutReplay(DecideRevision):
    name = "BrokenAcceptWithoutReplay"

    def apply(self, input_obj: RevisionProposed, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            RevisionAccepted(input_obj.request_id),
            replace(
                state,
                accepted_candidate_ids=state.accepted_candidate_ids + (input_obj.request_id,),
                active_candidate_ids=state.active_candidate_ids + (input_obj.request_id,),
            ),
            label="revision_accepted_without_replays",
        )


def accepted_candidates_have_current_replay(state: State, _trace) -> InvariantResult:
    invalid = tuple(
        item
        for item in state.accepted_candidate_ids
        if item not in state.independent_adapter_ids
        or item not in state.current_report_ids
        or item not in state.matching_replay_ids
    )
    if invalid:
        return InvariantResult.fail(
            f"accepted candidates without independent current matching replay: {invalid!r}"
        )
    return InvariantResult.pass_()


def rejected_candidates_keep_base_active(state: State, _trace) -> InvariantResult:
    missing = tuple(
        item for item in state.rejected_candidate_ids if item not in state.base_model_ids
    )
    if missing:
        return InvariantResult.fail(f"rejected candidates lost their base model: {missing!r}")
    return InvariantResult.pass_()


def rolled_back_candidates_restore_base(state: State, _trace) -> InvariantResult:
    invalid = tuple(
        item
        for item in state.rolled_back_candidate_ids
        if item not in state.base_model_ids or item in state.active_candidate_ids
    )
    if invalid:
        return InvariantResult.fail(f"rollback did not restore base authority: {invalid!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_candidates_have_current_replay",
        "candidate acceptance requires independent current matching replay",
        accepted_candidates_have_current_replay,
    ),
    Invariant(
        "rejected_candidates_keep_base_active",
        "candidate rejection preserves the base model",
        rejected_candidates_keep_base_active,
    ),
    Invariant(
        "rolled_back_candidates_restore_base",
        "candidate rollback restores base-model authority",
        rolled_back_candidates_restore_base,
    ),
)

EXTERNAL_INPUTS = (
    PredictionRequest("valid", True, True, True, True),
    PredictionRequest("status_only", True, False, True, True),
    PredictionRequest("leaking_adapter", False, True, True, True),
    PredictionRequest("replay_mismatch", True, True, False, False),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> State:
    return State()


def correct_workflow() -> Workflow:
    return Workflow(
        (
            FreezePrediction(),
            ReplayProduction(),
            ProposeRevision(),
            DecideRevision(),
            RollbackRevision(),
        ),
        name="task_local_prediction_replay",
    )


def broken_status_only_workflow() -> Workflow:
    return Workflow(
        (
            FreezePrediction(),
            BrokenStatusOnlyReplay(),
            ProposeRevision(),
            DecideRevision(),
            RollbackRevision(),
        ),
        name="broken_status_only",
    )


def broken_expected_output_workflow() -> Workflow:
    return Workflow(
        (
            BrokenExpectedOutputAdapter(),
            ReplayProduction(),
            ProposeRevision(),
            BrokenAcceptWithoutReplay(),
            RollbackRevision(),
        ),
        name="broken_expected_output",
    )


def broken_accept_without_replay_workflow() -> Workflow:
    return Workflow(
        (
            FreezePrediction(),
            ReplayProduction(),
            ProposeRevision(),
            BrokenAcceptWithoutReplay(),
            RollbackRevision(),
        ),
        name="broken_accept_without_replay",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (RevisionRejected, RevisionRolledBack))
