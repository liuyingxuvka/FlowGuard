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
from typing import Iterable, Literal

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


StageStatus = Literal["pass", "fail", "blocked", "invalid", "not_run"]
FindingKind = Literal["none", "safety", "temporal"]


@dataclass(frozen=True)
class VerificationRequest:
    request_id: str
    schema_status: StageStatus = "pass"
    safety_status: StageStatus = "pass"
    temporal_status: StageStatus = "pass"
    refinement_status: StageStatus = "pass"
    substitution_status: StageStatus = "pass"
    provider_status: StageStatus = "pass"
    conflict_status: StageStatus = "pass"
    impact_slice_status: StageStatus = "pass"
    system_status: StageStatus = "pass"
    exploration_status: StageStatus = "pass"
    system_finding_kind: FindingKind = "none"
    safety_witness_confirmed: bool = False


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
class SystemInteractionsChecked:
    request: VerificationRequest


@dataclass(frozen=True)
class VerificationAccepted:
    request_id: str


@dataclass(frozen=True)
class VerificationRejected:
    request_id: str
    status: Literal["fail", "blocked", "invalid"]
    reason: str


def rejection_status(stage_status: StageStatus) -> Literal["fail", "blocked", "invalid"]:
    if stage_status == "invalid":
        return "invalid"
    if stage_status == "fail":
        return "fail"
    return "blocked"


@dataclass(frozen=True)
class State:
    current_schema_ids: tuple[str, ...] = ()
    safe_ids: tuple[str, ...] = ()
    temporal_ids: tuple[str, ...] = ()
    refinement_ids: tuple[str, ...] = ()
    substitutable_ids: tuple[str, ...] = ()
    provider_closed_ids: tuple[str, ...] = ()
    conflict_free_ids: tuple[str, ...] = ()
    impact_slice_ids: tuple[str, ...] = ()
    system_interaction_ids: tuple[str, ...] = ()
    exploration_complete_ids: tuple[str, ...] = ()
    accepted_ids: tuple[str, ...] = ()


class ValidateCurrentSchema:
    name = "ValidateCurrentSchema"
    accepted_input_type = VerificationRequest

    def apply(self, input_obj: VerificationRequest, state: State) -> Iterable[FunctionResult]:
        if input_obj.schema_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    input_obj.request_id,
                    rejection_status(input_obj.schema_status),
                    "non_current_schema",
                ),
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
        if request.safety_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.safety_status),
                    "safety_not_passed",
                ),
                state,
                label="semantics_rejected",
            )
            return
        if request.temporal_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.temporal_status),
                    "temporal_not_passed",
                ),
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
        if request.refinement_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.refinement_status),
                    "refinement_not_passed",
                ),
                state,
                label="refinement_rejected",
            )
            return
        if request.substitution_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.substitution_status),
                    "contract_not_substitutable",
                ),
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
        if request.provider_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.provider_status),
                    "assumption_provider_not_passed",
                ),
                state,
                label="composition_rejected",
            )
            return
        if request.conflict_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.conflict_status),
                    "guarantee_conflict",
                ),
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


class CheckSystemInteractions:
    name = "CheckSystemInteractions"
    accepted_input_type = CompositionChecked

    def apply(self, input_obj: CompositionChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        if request.impact_slice_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.impact_slice_status),
                    "impact_slice_not_passed",
                ),
                state,
                label="system_interactions_rejected",
            )
            return
        if request.exploration_status != "pass":
            if (
                request.exploration_status == "blocked"
                and request.system_status == "fail"
                and request.system_finding_kind == "safety"
                and request.safety_witness_confirmed
            ):
                yield FunctionResult(
                    VerificationRejected(
                        request.request_id,
                        "fail",
                        "confirmed_safety_failure_with_truncation_residual",
                    ),
                    state,
                    label="system_interactions_rejected",
                )
                return
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.exploration_status),
                    "exploration_incomplete",
                ),
                state,
                label="system_interactions_rejected",
            )
            return
        if request.system_status != "pass":
            yield FunctionResult(
                VerificationRejected(
                    request.request_id,
                    rejection_status(request.system_status),
                    "system_interaction_not_passed",
                ),
                state,
                label="system_interactions_rejected",
            )
            return
        yield FunctionResult(
            SystemInteractionsChecked(request),
            replace(
                state,
                impact_slice_ids=state.impact_slice_ids + (request.request_id,),
                system_interaction_ids=state.system_interaction_ids + (request.request_id,),
                exploration_complete_ids=state.exploration_complete_ids + (request.request_id,),
            ),
            label="system_interactions_checked",
        )


class CloseVerification:
    name = "CloseVerification"
    accepted_input_type = SystemInteractionsChecked

    def apply(self, input_obj: SystemInteractionsChecked, state: State) -> Iterable[FunctionResult]:
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


class BrokenImpactSliceGate(CheckSystemInteractions):
    name = "BrokenImpactSliceGate"

    def apply(self, input_obj: CompositionChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        yield FunctionResult(
            SystemInteractionsChecked(request),
            replace(
                state,
                system_interaction_ids=state.system_interaction_ids + (request.request_id,),
                exploration_complete_ids=state.exploration_complete_ids + (request.request_id,),
            ),
            label="system_interactions_checked",
        )


class BrokenSystemInteractionGate(CheckSystemInteractions):
    name = "BrokenSystemInteractionGate"

    def apply(self, input_obj: CompositionChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        yield FunctionResult(
            SystemInteractionsChecked(request),
            replace(
                state,
                impact_slice_ids=state.impact_slice_ids + (request.request_id,),
                exploration_complete_ids=state.exploration_complete_ids + (request.request_id,),
            ),
            label="system_interactions_checked",
        )


class BrokenExplorationCompletenessGate(CheckSystemInteractions):
    name = "BrokenExplorationCompletenessGate"

    def apply(self, input_obj: CompositionChecked, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        yield FunctionResult(
            SystemInteractionsChecked(request),
            replace(
                state,
                impact_slice_ids=state.impact_slice_ids + (request.request_id,),
                system_interaction_ids=state.system_interaction_ids + (request.request_id,),
            ),
            label="system_interactions_checked",
        )


def accepted_have_all_evidence(state: State, _trace) -> InvariantResult:
    required_sets = (
        set(state.current_schema_ids),
        set(state.safe_ids),
        set(state.temporal_ids),
        set(state.refinement_ids),
        set(state.substitutable_ids),
        set(state.provider_closed_ids),
        set(state.conflict_free_ids),
        set(state.impact_slice_ids),
        set(state.system_interaction_ids),
        set(state.exploration_complete_ids),
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
    VerificationRequest("bad-schema", schema_status="invalid"),
    VerificationRequest("bad-temporal", temporal_status="fail"),
    VerificationRequest("bad-refinement", refinement_status="blocked"),
    VerificationRequest("bad-provider", provider_status="blocked"),
    VerificationRequest("bad-slice", impact_slice_status="blocked"),
    VerificationRequest(
        "bad-system",
        system_status="fail",
        system_finding_kind="safety",
        safety_witness_confirmed=True,
    ),
    VerificationRequest("bad-truncation", exploration_status="blocked"),
    VerificationRequest(
        "safety-fail-with-truncation",
        system_status="fail",
        exploration_status="blocked",
        system_finding_kind="safety",
        safety_witness_confirmed=True,
    ),
    VerificationRequest(
        "temporal-observation-with-truncation",
        system_status="fail",
        exploration_status="blocked",
        system_finding_kind="temporal",
    ),
    VerificationRequest("system-not-run", system_status="not_run"),
)

MAX_SEQUENCE_LENGTH = 1


def initial_state() -> State:
    return State()


def workflow(
    schema_gate=ValidateCurrentSchema(),
    semantics_gate=CheckPortableSemantics(),
    refinement_gate=CheckRefinement(),
    composition_gate=CheckComposition(),
    system_interaction_gate=CheckSystemInteractions(),
) -> Workflow:
    return Workflow(
        (
            schema_gate,
            semantics_gate,
            refinement_gate,
            composition_gate,
            system_interaction_gate,
            CloseVerification(),
        ),
        name="portable_compositional_verification",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, (VerificationAccepted, VerificationRejected))


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
