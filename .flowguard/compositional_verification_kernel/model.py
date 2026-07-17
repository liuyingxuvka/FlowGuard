"""FlowGuard model for the portable compositional verification kernel.

Purpose:
Prevent non-current schemas, unsafe/non-progressing portable models,
unmapped refinements, and open/conflicting compositions from receiving a
portable verification pass.

Run:
python .flowguard/compositional_verification_kernel/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class VerificationRequest:
    request_id: str
    current_schema: bool = True
    safety_passed: bool = True
    temporal_passed: bool = True
    refinement_complete: bool = True
    contracts_substitutable: bool = True
    assumptions_provided: bool = True
    conflicts_absent: bool = True


@dataclass(frozen=True)
class ModelValidated:
    request: VerificationRequest


@dataclass(frozen=True)
class SemanticsChecked:
    request: VerificationRequest


@dataclass(frozen=True)
class RefinementChecked:
    request: VerificationRequest


@dataclass(frozen=True)
class CompositionChecked:
    request: VerificationRequest


@dataclass(frozen=True)
class VerificationAccepted:
    request_id: str


@dataclass(frozen=True)
class VerificationRejected:
    request_id: str
    reason: str


@dataclass(frozen=True)
class State:
    current_schema_ids: tuple[str, ...] = ()
    safe_ids: tuple[str, ...] = ()
    temporal_ids: tuple[str, ...] = ()
    refinement_ids: tuple[str, ...] = ()
    substitutable_ids: tuple[str, ...] = ()
    provider_closed_ids: tuple[str, ...] = ()
    conflict_free_ids: tuple[str, ...] = ()
    accepted_ids: tuple[str, ...] = ()


class ValidateCurrentSchema:
    name = "ValidateCurrentSchema"
    accepted_input_type = VerificationRequest

    def apply(self, input_obj: VerificationRequest, state: State) -> Iterable[FunctionResult]:
        if not input_obj.current_schema:
            yield FunctionResult(
                VerificationRejected(input_obj.request_id, "non_current_schema"),
                state,
                label="schema_rejected",
            )
            return
        yield FunctionResult(
            ModelValidated(input_obj),
            replace(state, current_schema_ids=state.current_schema_ids + (input_obj.request_id,)),
            label="validated",
        )


class CheckPortableSemantics:
    name = "CheckPortableSemantics"
    accepted_input_type = ModelValidated

    def apply(self, input_obj: ModelValidated, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        if not request.safety_passed:
            yield FunctionResult(
                VerificationRejected(request.request_id, "safety_failed"),
                state,
                label="semantics_rejected",
            )
            return
        if not request.temporal_passed:
            yield FunctionResult(
                VerificationRejected(request.request_id, "temporal_failed"),
                state,
                label="semantics_rejected",
            )
            return
        yield FunctionResult(
            SemanticsChecked(request),
            replace(
                state,
                safe_ids=state.safe_ids + (request.request_id,),
                temporal_ids=state.temporal_ids + (request.request_id,),
            ),
            label="semantics_checked",
        )


class CheckRefinement:
    name = "CheckRefinement"
    accepted_input_type = SemanticsChecked

    def apply(self, input_obj: SemanticsChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        if not request.refinement_complete:
            yield FunctionResult(
                VerificationRejected(request.request_id, "refinement_incomplete"),
                state,
                label="refinement_rejected",
            )
            return
        if not request.contracts_substitutable:
            yield FunctionResult(
                VerificationRejected(request.request_id, "contract_not_substitutable"),
                state,
                label="refinement_rejected",
            )
            return
        yield FunctionResult(
            RefinementChecked(request),
            replace(
                state,
                refinement_ids=state.refinement_ids + (request.request_id,),
                substitutable_ids=state.substitutable_ids + (request.request_id,),
            ),
            label="refinement_checked",
        )


class CheckComposition:
    name = "CheckComposition"
    accepted_input_type = RefinementChecked

    def apply(self, input_obj: RefinementChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        if not request.assumptions_provided:
            yield FunctionResult(
                VerificationRejected(request.request_id, "assumption_provider_missing"),
                state,
                label="composition_rejected",
            )
            return
        if not request.conflicts_absent:
            yield FunctionResult(
                VerificationRejected(request.request_id, "guarantee_conflict"),
                state,
                label="composition_rejected",
            )
            return
        next_state = replace(
            state,
            provider_closed_ids=state.provider_closed_ids + (request.request_id,),
            conflict_free_ids=state.conflict_free_ids + (request.request_id,),
        )
        yield FunctionResult(
            CompositionChecked(request),
            next_state,
            label="composition_checked",
        )


class CloseVerification:
    name = "CloseVerification"
    accepted_input_type = CompositionChecked

    def apply(self, input_obj: CompositionChecked, state: State) -> Iterable[FunctionResult]:
        request_id = input_obj.request.request_id
        yield FunctionResult(
            VerificationAccepted(request_id),
            replace(state, accepted_ids=state.accepted_ids + (request_id,)),
            label="accepted",
        )


class BrokenSchemaGate(ValidateCurrentSchema):
    name = "BrokenSchemaGate"

    def apply(self, input_obj: VerificationRequest, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(ModelValidated(input_obj), state, label="validated")


class BrokenTemporalGate(CheckPortableSemantics):
    name = "BrokenTemporalGate"

    def apply(self, input_obj: ModelValidated, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        yield FunctionResult(
            SemanticsChecked(request),
            replace(state, safe_ids=state.safe_ids + (request.request_id,)),
            label="semantics_checked",
        )


class BrokenRefinementGate(CheckRefinement):
    name = "BrokenRefinementGate"

    def apply(self, input_obj: SemanticsChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        yield FunctionResult(RefinementChecked(request), state, label="refinement_checked")


class BrokenCompositionGate(CheckComposition):
    name = "BrokenCompositionGate"

    def apply(self, input_obj: RefinementChecked, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(CompositionChecked(input_obj.request), state, label="composition_checked")


def accepted_have_all_evidence(state: State, _trace) -> InvariantResult:
    required_sets = (
        set(state.current_schema_ids),
        set(state.safe_ids),
        set(state.temporal_ids),
        set(state.refinement_ids),
        set(state.substitutable_ids),
        set(state.provider_closed_ids),
        set(state.conflict_free_ids),
    )
    missing = tuple(
        request_id
        for request_id in state.accepted_ids
        if any(request_id not in evidence for evidence in required_sets)
    )
    if missing:
        return InvariantResult.fail(f"accepted verification missing gate evidence: {missing!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_have_all_evidence",
        "portable verification accepts only after schema, semantics, refinement, and composition gates",
        accepted_have_all_evidence,
    ),
)

EXTERNAL_INPUTS = (
    VerificationRequest("good"),
    VerificationRequest("bad-schema", current_schema=False),
    VerificationRequest("bad-temporal", temporal_passed=False),
    VerificationRequest("bad-refinement", refinement_complete=False),
    VerificationRequest("bad-provider", assumptions_provided=False),
)

MAX_SEQUENCE_LENGTH = 1


def initial_state() -> State:
    return State()


def workflow(
    schema_gate=ValidateCurrentSchema(),
    semantics_gate=CheckPortableSemantics(),
    refinement_gate=CheckRefinement(),
    composition_gate=CheckComposition(),
) -> Workflow:
    return Workflow(
        (schema_gate, semantics_gate, refinement_gate, composition_gate, CloseVerification()),
        name="portable_compositional_verification",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (VerificationAccepted, VerificationRejected))


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
