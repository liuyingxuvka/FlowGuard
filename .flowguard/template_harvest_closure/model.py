"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models mandatory local template harvest closure after a new or materially
deepened FlowGuard model.

Guards against:
- claiming model work complete after only search/build/check steps;
- using vague "not useful" wording instead of a bounded not-harvestable reason;
- recording write/merge/duplicate harvest closure without a template id.

Use before editing:
risk template harvest APIs, model-first skill prompts, CheckPlan, audit,
runner, CLI, or starter templates.

Run:
python .flowguard/template_harvest_closure/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


HARVEST_WITH_TEMPLATE_ID = ("written", "merged", "duplicate_linked")
ACCEPTED_NOT_HARVESTABLE_REASONS = (
    "not_reusable_project_specific",
    "no_new_pattern",
    "missing_known_bad_case",
    "missing_completion_evidence",
    "write_blocked",
    "human_deferred",
)


@dataclass(frozen=True)
class ModelWork:
    model_id: str
    reusable: bool
    completion_evidence: bool
    known_bad_case: bool
    preferred_disposition: str = "written"
    not_harvestable_reason: str = ""


@dataclass(frozen=True)
class ModelAccepted:
    model_id: str
    reusable: bool
    preferred_disposition: str
    not_harvestable_reason: str


@dataclass(frozen=True)
class HarvestClosed:
    model_id: str
    disposition: str
    template_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class CompletionClaimed:
    model_id: str


@dataclass(frozen=True)
class Rejected:
    model_id: str
    reason: str


@dataclass(frozen=True)
class State:
    accepted_model_ids: tuple[str, ...] = ()
    completion_evidence_ids: tuple[str, ...] = ()
    known_bad_case_ids: tuple[str, ...] = ()
    harvest_closed_ids: tuple[str, ...] = ()
    valid_harvest_closed_ids: tuple[str, ...] = ()
    claimed_model_ids: tuple[str, ...] = ()
    invalid_harvest_ids: tuple[str, ...] = ()


class AcceptMinimumModel:
    name = "AcceptMinimumModel"
    reads = ()
    writes = ("accepted_model_ids", "completion_evidence_ids", "known_bad_case_ids")
    accepted_input_type = ModelWork
    input_description = "new or deepened model work"
    output_description = "ModelAccepted or Rejected"

    def apply(self, input_obj: ModelWork, state: State) -> Iterable[FunctionResult]:
        if not input_obj.completion_evidence:
            yield FunctionResult(Rejected(input_obj.model_id, "completion_evidence_missing"), state, label="model_rejected")
            return
        if not input_obj.known_bad_case:
            yield FunctionResult(Rejected(input_obj.model_id, "known_bad_case_missing"), state, label="model_rejected")
            return
        yield FunctionResult(
            ModelAccepted(
                input_obj.model_id,
                reusable=input_obj.reusable,
                preferred_disposition=input_obj.preferred_disposition,
                not_harvestable_reason=input_obj.not_harvestable_reason,
            ),
            replace(
                state,
                accepted_model_ids=state.accepted_model_ids + (input_obj.model_id,),
                completion_evidence_ids=state.completion_evidence_ids + (input_obj.model_id,),
                known_bad_case_ids=state.known_bad_case_ids + (input_obj.model_id,),
            ),
            label="minimum_model_accepted",
        )


class CloseTemplateHarvest:
    name = "CloseTemplateHarvest"
    reads = ("accepted_model_ids",)
    writes = ("harvest_closed_ids", "valid_harvest_closed_ids", "invalid_harvest_ids")
    accepted_input_type = ModelAccepted
    input_description = "accepted minimum model"
    output_description = "HarvestClosed"

    def apply(self, input_obj: ModelAccepted, state: State) -> Iterable[FunctionResult]:
        if input_obj.model_id not in state.accepted_model_ids:
            yield FunctionResult(Rejected(input_obj.model_id, "model_not_accepted"), state, label="harvest_rejected")
            return

        if input_obj.reusable:
            disposition = input_obj.preferred_disposition
            template_id = f"{input_obj.model_id}_template"
            reason = ""
        else:
            disposition = "not_harvestable"
            template_id = ""
            reason = input_obj.not_harvestable_reason or "not_reusable_project_specific"

        valid = _valid_harvest(disposition, template_id, reason)
        yield FunctionResult(
            HarvestClosed(input_obj.model_id, disposition, template_id, reason),
            replace(
                state,
                harvest_closed_ids=state.harvest_closed_ids + (input_obj.model_id,),
                valid_harvest_closed_ids=(
                    state.valid_harvest_closed_ids + (input_obj.model_id,)
                    if valid
                    else state.valid_harvest_closed_ids
                ),
                invalid_harvest_ids=(
                    state.invalid_harvest_ids + (input_obj.model_id,)
                    if not valid
                    else state.invalid_harvest_ids
                ),
            ),
            label="template_harvest_closed",
        )


class ClaimModelComplete:
    name = "ClaimModelComplete"
    reads = ("accepted_model_ids", "valid_harvest_closed_ids")
    writes = ("claimed_model_ids",)
    accepted_input_type = HarvestClosed
    input_description = "template harvest closure"
    output_description = "CompletionClaimed"

    def apply(self, input_obj: HarvestClosed, state: State) -> Iterable[FunctionResult]:
        if input_obj.model_id not in state.accepted_model_ids:
            yield FunctionResult(Rejected(input_obj.model_id, "model_not_accepted"), state, label="claim_rejected")
            return
        if input_obj.model_id not in state.valid_harvest_closed_ids:
            yield FunctionResult(Rejected(input_obj.model_id, "harvest_closure_invalid"), state, label="claim_rejected")
            return
        yield FunctionResult(
            CompletionClaimed(input_obj.model_id),
            replace(state, claimed_model_ids=state.claimed_model_ids + (input_obj.model_id,)),
            label="model_completion_claimed",
        )


class BrokenClaimWithoutHarvest:
    name = "BrokenClaimWithoutHarvest"
    reads = ("accepted_model_ids",)
    writes = ("claimed_model_ids",)
    accepted_input_type = ModelAccepted
    input_description = "accepted minimum model"
    output_description = "CompletionClaimed"

    def apply(self, input_obj: ModelAccepted, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            CompletionClaimed(input_obj.model_id),
            replace(state, claimed_model_ids=state.claimed_model_ids + (input_obj.model_id,)),
            label="model_completion_claimed_without_harvest",
        )


class BrokenVagueSkipHarvest(CloseTemplateHarvest):
    name = "BrokenVagueSkipHarvest"

    def apply(self, input_obj: ModelAccepted, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            HarvestClosed(input_obj.model_id, "not_harvestable", reason="not_useful"),
            replace(
                state,
                harvest_closed_ids=state.harvest_closed_ids + (input_obj.model_id,),
                invalid_harvest_ids=state.invalid_harvest_ids + (input_obj.model_id,),
            ),
            label="template_harvest_closed_vague_skip",
        )


def _valid_harvest(disposition: str, template_id: str, reason: str) -> bool:
    if disposition in HARVEST_WITH_TEMPLATE_ID:
        return bool(template_id)
    if disposition == "not_harvestable":
        return reason in ACCEPTED_NOT_HARVESTABLE_REASONS
    return False


def claimed_models_have_valid_harvest_closure(state: State, _trace) -> InvariantResult:
    missing = tuple(model_id for model_id in state.claimed_model_ids if model_id not in state.valid_harvest_closed_ids)
    if missing:
        return InvariantResult.fail(f"claimed model missing valid harvest closure: {missing!r}")
    return InvariantResult.pass_()


def harvest_closure_dispositions_are_valid(state: State, _trace) -> InvariantResult:
    if state.invalid_harvest_ids:
        return InvariantResult.fail(f"invalid harvest closure recorded: {state.invalid_harvest_ids!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "claimed_models_have_valid_harvest_closure",
        "completion claims require written, merged, duplicate-linked, or accepted not-harvestable closure",
        claimed_models_have_valid_harvest_closure,
    ),
    Invariant(
        "harvest_closure_dispositions_are_valid",
        "harvest closure uses bounded dispositions and accepted reasons",
        harvest_closure_dispositions_are_valid,
    ),
)

EXTERNAL_INPUTS = (
    ModelWork("written", True, True, True, preferred_disposition="written"),
    ModelWork("merged", True, True, True, preferred_disposition="merged"),
    ModelWork("duplicate", True, True, True, preferred_disposition="duplicate_linked"),
    ModelWork("project_specific", False, True, True, not_harvestable_reason="not_reusable_project_specific"),
    ModelWork("missing_bad", True, True, False),
)

MAX_SEQUENCE_LENGTH = 3


def initial_state() -> State:
    return State()


def correct_workflow() -> Workflow:
    return Workflow(
        (AcceptMinimumModel(), CloseTemplateHarvest(), ClaimModelComplete()),
        name="template_harvest_closure",
    )


def broken_without_harvest_workflow() -> Workflow:
    return Workflow(
        (AcceptMinimumModel(), BrokenClaimWithoutHarvest()),
        name="broken_without_harvest",
    )


def broken_vague_skip_workflow() -> Workflow:
    return Workflow(
        (AcceptMinimumModel(), BrokenVagueSkipHarvest(), ClaimModelComplete()),
        name="broken_vague_skip",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (Rejected, CompletionClaimed))
