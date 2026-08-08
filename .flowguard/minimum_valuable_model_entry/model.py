"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Model the continuing minimum valuable model entry for ordinary FlowGuard work.
The entry accepts a bounded model only when its purpose, protected error,
state, side effects, completion evidence, executable known-bad case, and
current model/code/test bindings are all explicit.

Guards against:
- accepting a model that says what it describes but not which failure it
  prevents;
- accepting a model without explicit state, side effects, or completion
  evidence;
- accepting a model without an executable known-bad case;
- accepting a model whose model, code, and test bindings are incomplete;
- making optional template reuse work part of the ordinary minimum entry.

Use before editing:
model-first entry guidance, minimum-model contracts, formal self-model runners,
or current model/code/test binding rules.

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
    purpose_id: str
    protected_error_classes: tuple[str, ...]
    modeled_state: tuple[str, ...]
    modeled_side_effects: tuple[str, ...]
    completion_evidence_ids: tuple[str, ...]
    known_bad_case_ids: tuple[str, ...]
    model_binding_ids: tuple[str, ...]
    code_binding_ids: tuple[str, ...]
    test_binding_ids: tuple[str, ...]


@dataclass(frozen=True)
class MinimumModelInspected:
    request: ModelRequest
    missing_requirements: tuple[str, ...]


@dataclass(frozen=True)
class ModelAccepted:
    request_id: str


@dataclass(frozen=True)
class Rejected:
    request_id: str
    reason: str


@dataclass(frozen=True)
class State:
    inspected_requests: tuple[ModelRequest, ...] = ()
    accepted_model_ids: tuple[str, ...] = ()


def _append_unique(values: tuple[str, ...], item: str) -> tuple[str, ...]:
    return values if item in values else values + (item,)


def _record_request(
    requests: tuple[ModelRequest, ...],
    request: ModelRequest,
) -> tuple[ModelRequest, ...]:
    if not any(item.request_id == request.request_id for item in requests):
        return requests + (request,)
    return tuple(
        request if item.request_id == request.request_id else item
        for item in requests
    )


def _missing_requirements(request: ModelRequest) -> tuple[str, ...]:
    checks = (
        ("purpose", bool(request.purpose_id.strip())),
        ("protected_error_class", bool(request.protected_error_classes)),
        ("modeled_state", bool(request.modeled_state)),
        ("modeled_side_effects", bool(request.modeled_side_effects)),
        ("completion_evidence", bool(request.completion_evidence_ids)),
        ("known_bad_case", bool(request.known_bad_case_ids)),
        ("model_binding", bool(request.model_binding_ids)),
        ("code_binding", bool(request.code_binding_ids)),
        ("test_binding", bool(request.test_binding_ids)),
    )
    return tuple(name for name, present in checks if not present)


class InspectMinimumModelContract:
    name = "InspectMinimumModelContract"
    reads = ()
    writes = ("inspected_requests",)
    accepted_input_type = ModelRequest
    input_description = "ordinary bounded model request"
    output_description = "minimum-model contract inspection"
    idempotency = "Repeated inspection records the same request coverage once."

    def apply(self, input_obj: ModelRequest, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            MinimumModelInspected(input_obj, _missing_requirements(input_obj)),
            replace(
                state,
                inspected_requests=_record_request(
                    state.inspected_requests,
                    input_obj,
                ),
            ),
            label="minimum_contract_inspected",
        )


class AcceptMinimumModel:
    name = "AcceptMinimumModel"
    reads = ("inspected_requests",)
    writes = ("accepted_model_ids",)
    accepted_input_type = MinimumModelInspected
    input_description = "inspected minimum-model contract"
    output_description = "accepted bounded model or exact rejection"
    idempotency = "Repeated acceptance records one current model identity."

    def apply(self, input_obj: MinimumModelInspected, state: State) -> Iterable[FunctionResult]:
        request_id = input_obj.request.request_id
        if input_obj.request not in state.inspected_requests:
            yield FunctionResult(
                Rejected(request_id, "minimum_contract_inspection_missing"),
                state,
                label="minimum_model_rejected",
            )
            return
        if input_obj.missing_requirements:
            yield FunctionResult(
                Rejected(
                    request_id,
                    "missing:" + ",".join(input_obj.missing_requirements),
                ),
                state,
                label="minimum_model_rejected",
            )
            return
        yield FunctionResult(
            ModelAccepted(request_id),
            replace(
                state,
                accepted_model_ids=_append_unique(
                    state.accepted_model_ids,
                    request_id,
                ),
            ),
            label="minimum_model_accepted",
        )


class BrokenAcceptIncompleteModel(AcceptMinimumModel):
    name = "BrokenAcceptIncompleteModel"

    def apply(self, input_obj: MinimumModelInspected, state: State) -> Iterable[FunctionResult]:
        request_id = input_obj.request.request_id
        yield FunctionResult(
            ModelAccepted(request_id),
            replace(
                state,
                accepted_model_ids=_append_unique(
                    state.accepted_model_ids,
                    request_id,
                ),
            ),
            label="minimum_model_accepted",
        )


class BrokenTemplateSearchDuringInspection(InspectMinimumModelContract):
    name = "TemplateSearchDuringMinimumModelInspection"


def _accepted_missing(
    state: State,
    requirement_names: tuple[str, ...],
) -> tuple[str, ...]:
    inspected = {request.request_id: request for request in state.inspected_requests}
    missing: list[str] = []
    for model_id in state.accepted_model_ids:
        request = inspected.get(model_id)
        if request is None:
            missing.append(f"{model_id}:minimum_contract_inspection")
            continue
        absent = set(_missing_requirements(request))
        missing.extend(
            f"{model_id}:{requirement}"
            for requirement in requirement_names
            if requirement in absent
        )
    return tuple(missing)


def accepted_models_declare_purpose_and_protected_error(
    state: State,
    _trace,
) -> InvariantResult:
    missing = _accepted_missing(state, ("purpose", "protected_error_class"))
    if missing:
        return InvariantResult.fail(
            "accepted model missing purpose or protected error: "
            f"{missing!r}"
        )
    return InvariantResult.pass_()


def accepted_models_make_state_and_effects_explicit(
    state: State,
    _trace,
) -> InvariantResult:
    missing = _accepted_missing(state, ("modeled_state", "modeled_side_effects"))
    if missing:
        return InvariantResult.fail(
            "accepted model missing explicit state or side effects: "
            f"{missing!r}"
        )
    return InvariantResult.pass_()


def accepted_models_have_completion_and_known_bad_evidence(
    state: State,
    _trace,
) -> InvariantResult:
    missing = _accepted_missing(state, ("completion_evidence", "known_bad_case"))
    if missing:
        return InvariantResult.fail(
            "accepted model missing completion evidence or executable known-bad case: "
            f"{missing!r}"
        )
    return InvariantResult.pass_()


def accepted_models_bind_current_model_code_and_tests(
    state: State,
    _trace,
) -> InvariantResult:
    missing = _accepted_missing(
        state,
        ("model_binding", "code_binding", "test_binding"),
    )
    if missing:
        return InvariantResult.fail(
            "accepted model missing current model/code/test binding: "
            f"{missing!r}"
        )
    return InvariantResult.pass_()


def ordinary_entry_does_not_invoke_template_operations(
    _state: State,
    trace,
) -> InvariantResult:
    forbidden = ("template", "no_match", "nomatch", "harvest")
    operations = tuple(
        f"{step.function_name}:{step.label}"
        for step in trace.steps
        if any(
            marker in f"{step.function_name}:{step.label}".lower()
            for marker in forbidden
        )
    )
    if operations:
        return InvariantResult.fail(
            "ordinary minimum-model entry invoked template work: "
            f"{operations!r}"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_models_declare_purpose_and_protected_error",
        "Accepted models declare their purpose and protected error class.",
        accepted_models_declare_purpose_and_protected_error,
    ),
    Invariant(
        "accepted_models_make_state_and_effects_explicit",
        "Accepted models declare the state and side effects they own.",
        accepted_models_make_state_and_effects_explicit,
    ),
    Invariant(
        "accepted_models_have_completion_and_known_bad_evidence",
        "Accepted models bind completion evidence and an executable known-bad case.",
        accepted_models_have_completion_and_known_bad_evidence,
    ),
    Invariant(
        "accepted_models_bind_current_model_code_and_tests",
        "Accepted models bind the current model, code, and test owners.",
        accepted_models_bind_current_model_code_and_tests,
    ),
    Invariant(
        "ordinary_entry_does_not_invoke_template_operations",
        "Ordinary minimum-model admission performs no template operation.",
        ordinary_entry_does_not_invoke_template_operations,
    ),
)


COMPLETE_REQUEST = ModelRequest(
    request_id="complete",
    purpose_id="purpose:bounded-workflow",
    protected_error_classes=("duplicate_side_effect",),
    modeled_state=("request_status",),
    modeled_side_effects=("write_result",),
    completion_evidence_ids=("evidence:terminal-result",),
    known_bad_case_ids=("case:duplicate-write",),
    model_binding_ids=("model:bounded-workflow",),
    code_binding_ids=("code:bounded-workflow-owner",),
    test_binding_ids=("test:duplicate-write",),
)

INCOMPLETE_REQUESTS = (
    replace(COMPLETE_REQUEST, request_id="missing_purpose", purpose_id=""),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_protected_error",
        protected_error_classes=(),
    ),
    replace(COMPLETE_REQUEST, request_id="missing_state", modeled_state=()),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_effect",
        modeled_side_effects=(),
    ),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_completion",
        completion_evidence_ids=(),
    ),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_known_bad",
        known_bad_case_ids=(),
    ),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_model_binding",
        model_binding_ids=(),
    ),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_code_binding",
        code_binding_ids=(),
    ),
    replace(
        COMPLETE_REQUEST,
        request_id="missing_test_binding",
        test_binding_ids=(),
    ),
)

EXPECTED_REJECTION_REQUIREMENTS = {
    request.request_id: _missing_requirements(request)[0]
    for request in INCOMPLETE_REQUESTS
}

EXTERNAL_INPUTS = (COMPLETE_REQUEST,) + INCOMPLETE_REQUESTS
MAX_SEQUENCE_LENGTH = 1


def initial_state() -> State:
    return State()


def correct_workflow() -> Workflow:
    return Workflow(
        (InspectMinimumModelContract(), AcceptMinimumModel()),
        name="minimum_valuable_model_entry",
    )


def broken_incomplete_workflow() -> Workflow:
    return Workflow(
        (InspectMinimumModelContract(), BrokenAcceptIncompleteModel()),
        name="broken_accept_incomplete_model",
    )


def broken_template_operation_workflow() -> Workflow:
    return Workflow(
        (BrokenTemplateSearchDuringInspection(), AcceptMinimumModel()),
        name="broken_template_operation_on_ordinary_path",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (Rejected, ModelAccepted))


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    exported = build_skill_contract_model_export(
        skill_id="flowguard",
        route_id="model_first_function_flow",
        owner_id="model_first_function_flow",
        parent_model_id="flowguard.root",
        business_intent=(
            "Accept the minimum useful FlowGuard model only when purpose, protected "
            "failure, state, effects, completion, known-bad proof, and current "
            "model/code/test bindings are explicit."
        ),
        claim_boundary=(
            "This kernel projection owns ordinary minimum-model admission. It does "
            "not replace satellite owners, grant broad software understanding, or "
            "run optional template reuse and publication work."
        ),
    )
    exported["invariant_ids"].append("invariant:model-maturation-closure")
    exported["obligations"].append(
        {
            "obligation_id": "obligation:flowguard:model-maturation-closure",
            "invariant_id": "invariant:model-maturation-closure",
            "owner_step_ids": ["step:flowguard:verify"],
            "required": True,
        }
    )
    exported["invariant_ids"].append("invariant:understanding-readiness")
    exported["obligations"].append(
        {
            "obligation_id": "obligation:flowguard:understanding-readiness",
            "invariant_id": "invariant:understanding-readiness",
            "owner_step_ids": ["step:flowguard:verify"],
            "required": True,
        }
    )
    exported["invariant_ids"].append("invariant:model-revision-build")
    exported["obligations"].append(
        {
            "obligation_id": "obligation:flowguard:model-revision-build",
            "invariant_id": "invariant:model-revision-build",
            "owner_step_ids": ["step:flowguard:verify"],
            "required": True,
        }
    )
    return exported
