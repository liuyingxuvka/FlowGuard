"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the FlowGuard AI entry upgrade that turns the default model-first path
into a minimum valuable model with public/local template reuse.

Guards against:
- generating a model before searching public and local risk templates;
- claiming a model is useful without a protected error class, completion
  evidence, and a known-bad case;
- harvesting local templates without reusable evidence or a portable local root.

Use before editing:
model-first entry guidance, risk template library APIs, public templates, audit
rules, runner sections, or installed skill prompts.

Run:
python .flowguard/minimum_valuable_model_entry/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class ModelRequest:
    request_id: str
    protected_error_class: bool
    template_match: bool
    completion_evidence: bool
    known_bad_case: bool
    reusable_pattern: bool = True
    portable_local_root: bool = True


@dataclass(frozen=True)
class TemplateSearchDone:
    request_id: str
    used_template: bool
    no_match_reason: bool
    protected_error_class: bool
    completion_evidence: bool
    known_bad_case: bool
    reusable_pattern: bool


@dataclass(frozen=True)
class ModelDrafted:
    request_id: str
    accepted: bool


@dataclass(frozen=True)
class CandidateHarvested:
    request_id: str


@dataclass(frozen=True)
class Rejected:
    request_id: str
    reason: str


@dataclass(frozen=True)
class State:
    searched_request_ids: tuple[str, ...] = ()
    accepted_model_ids: tuple[str, ...] = ()
    harvested_template_ids: tuple[str, ...] = ()
    used_template_ids: tuple[str, ...] = ()
    no_match_request_ids: tuple[str, ...] = ()
    completion_evidence_ids: tuple[str, ...] = ()
    known_bad_case_ids: tuple[str, ...] = ()
    portable_local_root_ids: tuple[str, ...] = ()


class SearchTemplates:
    name = "SearchTemplates"
    reads = ()
    writes = ("searched_request_ids", "used_template_ids", "no_match_request_ids", "portable_local_root_ids")
    accepted_input_type = ModelRequest
    input_description = "AI model creation or deepening request"
    output_description = "TemplateSearchDone or Rejected"

    def apply(self, input_obj: ModelRequest, state: State) -> Iterable[FunctionResult]:
        if not input_obj.portable_local_root:
            yield FunctionResult(Rejected(input_obj.request_id, "non_portable_local_root"), state, label="root_rejected")
            return
        yield FunctionResult(
            TemplateSearchDone(
                input_obj.request_id,
                used_template=input_obj.template_match,
                no_match_reason=not input_obj.template_match,
                protected_error_class=input_obj.protected_error_class,
                completion_evidence=input_obj.completion_evidence,
                known_bad_case=input_obj.known_bad_case,
                reusable_pattern=input_obj.reusable_pattern,
            ),
            replace(
                state,
                searched_request_ids=state.searched_request_ids + (input_obj.request_id,),
                used_template_ids=(
                    state.used_template_ids + (input_obj.request_id,)
                    if input_obj.template_match
                    else state.used_template_ids
                ),
                no_match_request_ids=(
                    state.no_match_request_ids + (input_obj.request_id,)
                    if not input_obj.template_match
                    else state.no_match_request_ids
                ),
                portable_local_root_ids=state.portable_local_root_ids + (input_obj.request_id,),
            ),
            label="template_search_done",
        )


class DraftMinimumModel:
    name = "DraftMinimumModel"
    reads = ("searched_request_ids",)
    writes = ("accepted_model_ids", "completion_evidence_ids", "known_bad_case_ids")
    accepted_input_type = TemplateSearchDone
    input_description = "Template search result"
    output_description = "ModelDrafted or Rejected"

    def apply(self, input_obj: TemplateSearchDone, state: State) -> Iterable[FunctionResult]:
        if input_obj.request_id not in state.searched_request_ids:
            yield FunctionResult(Rejected(input_obj.request_id, "template_search_missing"), state, label="draft_rejected")
            return
        if not (input_obj.used_template or input_obj.no_match_reason):
            yield FunctionResult(Rejected(input_obj.request_id, "template_reuse_unexplained"), state, label="draft_rejected")
            return
        if not input_obj.protected_error_class:
            yield FunctionResult(Rejected(input_obj.request_id, "protected_error_class_missing"), state, label="draft_rejected")
            return
        if not input_obj.completion_evidence:
            yield FunctionResult(Rejected(input_obj.request_id, "completion_evidence_missing"), state, label="draft_rejected")
            return
        if not input_obj.known_bad_case:
            yield FunctionResult(Rejected(input_obj.request_id, "known_bad_case_missing"), state, label="draft_rejected")
            return
        yield FunctionResult(
            ModelDrafted(input_obj.request_id, accepted=True),
            replace(
                state,
                accepted_model_ids=state.accepted_model_ids + (input_obj.request_id,),
                completion_evidence_ids=state.completion_evidence_ids + (input_obj.request_id,),
                known_bad_case_ids=state.known_bad_case_ids + (input_obj.request_id,),
            ),
            label="minimum_model_accepted",
        )


class HarvestLocalCandidate:
    name = "HarvestLocalCandidate"
    reads = ("accepted_model_ids", "completion_evidence_ids", "known_bad_case_ids", "portable_local_root_ids")
    writes = ("harvested_template_ids",)
    accepted_input_type = ModelDrafted
    input_description = "Accepted minimum model"
    output_description = "CandidateHarvested"

    def apply(self, input_obj: ModelDrafted, state: State) -> Iterable[FunctionResult]:
        ready = (
            input_obj.accepted
            and input_obj.request_id in state.accepted_model_ids
            and input_obj.request_id in state.completion_evidence_ids
            and input_obj.request_id in state.known_bad_case_ids
            and input_obj.request_id in state.portable_local_root_ids
        )
        if not ready:
            yield FunctionResult(Rejected(input_obj.request_id, "harvest_requirements_missing"), state, label="harvest_rejected")
            return
        yield FunctionResult(
            CandidateHarvested(input_obj.request_id),
            replace(state, harvested_template_ids=state.harvested_template_ids + (input_obj.request_id,)),
            label="local_candidate_harvested",
        )


class BrokenDraftWithoutEvidence(DraftMinimumModel):
    name = "BrokenDraftWithoutEvidence"

    def apply(self, input_obj: TemplateSearchDone, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            ModelDrafted(input_obj.request_id, accepted=True),
            replace(state, accepted_model_ids=state.accepted_model_ids + (input_obj.request_id,)),
            label="minimum_model_accepted_without_teeth",
        )


class BrokenSearchWithHardcodedRoot(SearchTemplates):
    name = "BrokenSearchWithHardcodedRoot"

    def apply(self, input_obj: ModelRequest, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            TemplateSearchDone(
                input_obj.request_id,
                used_template=False,
                no_match_reason=True,
                protected_error_class=input_obj.protected_error_class,
                completion_evidence=input_obj.completion_evidence,
                known_bad_case=input_obj.known_bad_case,
                reusable_pattern=input_obj.reusable_pattern,
            ),
            replace(state, searched_request_ids=state.searched_request_ids + (input_obj.request_id,)),
            label="template_search_done",
        )


def accepted_models_have_teeth(state: State, _trace) -> InvariantResult:
    missing = tuple(
        model_id
        for model_id in state.accepted_model_ids
        if model_id not in state.completion_evidence_ids or model_id not in state.known_bad_case_ids
    )
    if missing:
        return InvariantResult.fail(f"accepted model missing evidence or known-bad case: {missing!r}")
    return InvariantResult.pass_()


def accepted_models_follow_template_review(state: State, _trace) -> InvariantResult:
    missing = tuple(
        model_id
        for model_id in state.accepted_model_ids
        if model_id not in state.used_template_ids and model_id not in state.no_match_request_ids
    )
    if missing:
        return InvariantResult.fail(f"accepted model missing template reuse review: {missing!r}")
    return InvariantResult.pass_()


def harvested_candidates_are_portable(state: State, _trace) -> InvariantResult:
    missing = tuple(
        template_id
        for template_id in state.harvested_template_ids
        if template_id not in state.portable_local_root_ids
    )
    if missing:
        return InvariantResult.fail(f"harvested templates without portable local root: {missing!r}")
    return InvariantResult.pass_()


def accepted_models_have_portable_search(state: State, _trace) -> InvariantResult:
    missing = tuple(
        model_id
        for model_id in state.accepted_model_ids
        if model_id not in state.portable_local_root_ids
    )
    if missing:
        return InvariantResult.fail(f"accepted models without portable local template root: {missing!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_models_have_teeth",
        "accepted models include completion evidence and a known-bad case",
        accepted_models_have_teeth,
    ),
    Invariant(
        "accepted_models_follow_template_review",
        "accepted models used a template or recorded no-match",
        accepted_models_follow_template_review,
    ),
    Invariant(
        "harvested_candidates_are_portable",
        "local candidates are harvested only through a portable per-machine root",
        harvested_candidates_are_portable,
    ),
    Invariant(
        "accepted_models_have_portable_search",
        "accepted models must come from a portable public/local template search",
        accepted_models_have_portable_search,
    ),
)

EXTERNAL_INPUTS = (
    ModelRequest("matched", True, True, True, True),
    ModelRequest("no_match", True, False, True, True),
    ModelRequest("missing_teeth", False, False, False, False),
    ModelRequest("hardcoded", True, False, True, True, portable_local_root=False),
)

MAX_SEQUENCE_LENGTH = 3


def initial_state() -> State:
    return State()


def correct_workflow() -> Workflow:
    return Workflow((SearchTemplates(), DraftMinimumModel(), HarvestLocalCandidate()), name="minimum_value_entry")


def broken_without_evidence_workflow() -> Workflow:
    return Workflow((SearchTemplates(), BrokenDraftWithoutEvidence(), HarvestLocalCandidate()), name="broken_without_evidence")


def broken_hardcoded_root_workflow() -> Workflow:
    return Workflow((BrokenSearchWithHardcodedRoot(), DraftMinimumModel(), HarvestLocalCandidate()), name="broken_hardcoded_root")


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (Rejected, CandidateHarvested))


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard",
        route_id="model_first_function_flow",
        owner_id="model_first_function_flow",
        parent_model_id="flowguard.root",
        business_intent="Select or build the minimum useful FlowGuard model and route ordinary behavior work to its existing owner.",
        claim_boundary="This kernel projection selects and validates a minimum model boundary; it does not replace satellite owners or make every trivial action execute a model.",
    )
