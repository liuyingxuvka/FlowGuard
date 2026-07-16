"""FlowGuard model for validated template-pack registry decisions.

Purpose:
Prevent stale manifests, implicit/conflicting selection, parameter drift, and
stale instance receipts from reaching an accepted template instance.

Run:
python openspec/changes/add-validated-template-pack-registry/model/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


SELECTABLE_DISPOSITIONS = ("base_selected", "selected", "composed")


@dataclass(frozen=True)
class SelectionRequest:
    request_id: str
    manifest_current: bool = True
    match_count: int = 1
    base_present: bool = False
    all_composable: bool = True
    fields_disjoint: bool = True
    parameters_exact: bool = True
    receipt_current: bool = True


@dataclass(frozen=True)
class ManifestValidated:
    request: SelectionRequest


@dataclass(frozen=True)
class SelectionClosed:
    request: SelectionRequest
    disposition: str


@dataclass(frozen=True)
class InstanceRendered:
    request: SelectionRequest


@dataclass(frozen=True)
class InstanceAccepted:
    request_id: str


@dataclass(frozen=True)
class InstanceBlocked:
    request_id: str
    reason: str


@dataclass(frozen=True)
class State:
    current_manifest_ids: tuple[str, ...] = ()
    selection_receipt_ids: tuple[str, ...] = ()
    selection_eligible_ids: tuple[str, ...] = ()
    instance_receipt_ids: tuple[str, ...] = ()
    exact_parameter_ids: tuple[str, ...] = ()
    current_instance_ids: tuple[str, ...] = ()
    accepted_ids: tuple[str, ...] = ()


class ValidateManifest:
    name = "ValidateManifest"
    accepted_input_type = SelectionRequest

    def apply(self, input_obj: SelectionRequest, state: State) -> Iterable[FunctionResult]:
        if not input_obj.manifest_current:
            yield FunctionResult(
                SelectionClosed(input_obj, "invalid_manifest"),
                replace(
                    state,
                    selection_receipt_ids=state.selection_receipt_ids + (input_obj.request_id,),
                ),
                label="selection_receipt_emitted",
            )
            return
        yield FunctionResult(
            ManifestValidated(input_obj),
            replace(
                state,
                current_manifest_ids=state.current_manifest_ids + (input_obj.request_id,),
            ),
            label="manifest_validated",
        )


class SelectTemplatePacks:
    name = "SelectTemplatePacks"
    accepted_input_type = (ManifestValidated, SelectionClosed)

    def apply(
        self,
        input_obj: ManifestValidated | SelectionClosed,
        state: State,
    ) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SelectionClosed):
            yield FunctionResult(input_obj, state, label="selection_closed")
            return
        request = input_obj.request
        disposition = selection_disposition(request)
        selectable = disposition in SELECTABLE_DISPOSITIONS
        yield FunctionResult(
            SelectionClosed(request, disposition),
            replace(
                state,
                selection_receipt_ids=state.selection_receipt_ids + (request.request_id,),
                selection_eligible_ids=(
                    state.selection_eligible_ids + (request.request_id,)
                    if selectable
                    else state.selection_eligible_ids
                ),
            ),
            label="selection_receipt_emitted",
        )


class InstantiateTemplatePacks:
    name = "InstantiateTemplatePacks"
    accepted_input_type = SelectionClosed

    def apply(self, input_obj: SelectionClosed, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        next_state = replace(
            state,
            instance_receipt_ids=state.instance_receipt_ids + (request.request_id,),
        )
        if input_obj.disposition not in SELECTABLE_DISPOSITIONS:
            yield FunctionResult(
                InstanceBlocked(request.request_id, f"selection_{input_obj.disposition}"),
                next_state,
                label="instance_receipt_emitted",
            )
            return
        if not request.parameters_exact:
            yield FunctionResult(
                InstanceBlocked(request.request_id, "parameters_not_exact"),
                next_state,
                label="instance_receipt_emitted",
            )
            return
        yield FunctionResult(
            InstanceRendered(request),
            replace(
                next_state,
                exact_parameter_ids=next_state.exact_parameter_ids + (request.request_id,),
            ),
            label="instance_receipt_emitted",
        )


class ValidateInstanceReceipt:
    name = "ValidateInstanceReceipt"
    accepted_input_type = (InstanceRendered, InstanceBlocked)

    def apply(
        self,
        input_obj: InstanceRendered | InstanceBlocked,
        state: State,
    ) -> Iterable[FunctionResult]:
        if isinstance(input_obj, InstanceBlocked):
            yield FunctionResult(input_obj, state, label="instance_blocked")
            return
        request = input_obj.request
        if not request.receipt_current:
            yield FunctionResult(
                InstanceBlocked(request.request_id, "instance_receipt_stale"),
                state,
                label="receipt_stale",
            )
            return
        yield FunctionResult(
            InstanceAccepted(request.request_id),
            replace(
                state,
                current_instance_ids=state.current_instance_ids + (request.request_id,),
                accepted_ids=state.accepted_ids + (request.request_id,),
            ),
            label="instance_accepted",
        )


class BrokenManifestGate(ValidateManifest):
    name = "BrokenManifestGate"

    def apply(self, input_obj: SelectionRequest, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(ManifestValidated(input_obj), state, label="manifest_validated")


class BrokenSelectionGate(SelectTemplatePacks):
    name = "BrokenSelectionGate"

    def apply(
        self,
        input_obj: ManifestValidated | SelectionClosed,
        state: State,
    ) -> Iterable[FunctionResult]:
        if isinstance(input_obj, SelectionClosed):
            yield FunctionResult(input_obj, state, label="selection_closed")
            return
        request = input_obj.request
        yield FunctionResult(
            SelectionClosed(request, "selected"),
            replace(
                state,
                selection_receipt_ids=state.selection_receipt_ids + (request.request_id,),
            ),
            label="selection_receipt_emitted",
        )


class BrokenParameterGate(InstantiateTemplatePacks):
    name = "BrokenParameterGate"

    def apply(self, input_obj: SelectionClosed, state: State) -> Iterable[FunctionResult]:
        request = input_obj.request
        yield FunctionResult(
            InstanceRendered(request),
            replace(
                state,
                instance_receipt_ids=state.instance_receipt_ids + (request.request_id,),
            ),
            label="instance_receipt_emitted",
        )


class BrokenFreshnessGate(ValidateInstanceReceipt):
    name = "BrokenFreshnessGate"

    def apply(
        self,
        input_obj: InstanceRendered | InstanceBlocked,
        state: State,
    ) -> Iterable[FunctionResult]:
        if isinstance(input_obj, InstanceBlocked):
            yield FunctionResult(input_obj, state, label="instance_blocked")
            return
        request_id = input_obj.request.request_id
        yield FunctionResult(
            InstanceAccepted(request_id),
            replace(state, accepted_ids=state.accepted_ids + (request_id,)),
            label="instance_accepted",
        )


def selection_disposition(request: SelectionRequest) -> str:
    if request.match_count == 0:
        return "base_selected" if request.base_present else "no_match"
    if request.match_count == 1:
        return "selected"
    if request.all_composable and request.fields_disjoint:
        return "composed"
    return "conflict"


def accepted_instances_have_all_evidence(state: State, _trace) -> InvariantResult:
    evidence_sets = (
        set(state.current_manifest_ids),
        set(state.selection_receipt_ids),
        set(state.selection_eligible_ids),
        set(state.instance_receipt_ids),
        set(state.exact_parameter_ids),
        set(state.current_instance_ids),
    )
    missing = tuple(
        request_id
        for request_id in state.accepted_ids
        if any(request_id not in evidence for evidence in evidence_sets)
    )
    if missing:
        return InvariantResult.fail(
            f"accepted template instance missing gate evidence: {missing!r}"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_instances_have_all_evidence",
        "accepted instances require current manifest, selectable decision, exact parameters, and current receipts",
        accepted_instances_have_all_evidence,
    ),
)

EXTERNAL_INPUTS = (
    SelectionRequest("base", match_count=0, base_present=True),
    SelectionRequest("no-match", match_count=0),
    SelectionRequest("one", match_count=1),
    SelectionRequest("many", match_count=2, all_composable=True, fields_disjoint=True),
    SelectionRequest("non-composable", match_count=2, all_composable=False),
    SelectionRequest("field-conflict", match_count=2, fields_disjoint=False),
    SelectionRequest("stale-manifest", manifest_current=False),
    SelectionRequest("bad-parameters", parameters_exact=False),
    SelectionRequest("stale-receipt", receipt_current=False),
)

EXPECTED_ACCEPTED_IDS = ("base", "one", "many")
MAX_SEQUENCE_LENGTH = 1


def initial_state() -> State:
    return State()


def workflow(
    manifest_gate=ValidateManifest(),
    selection_gate=SelectTemplatePacks(),
    parameter_gate=InstantiateTemplatePacks(),
    freshness_gate=ValidateInstanceReceipt(),
) -> Workflow:
    return Workflow(
        (manifest_gate, selection_gate, parameter_gate, freshness_gate),
        name="validated_template_pack_registry",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    if isinstance(current_output, InstanceAccepted):
        return True
    if isinstance(current_output, InstanceBlocked):
        return True
    return isinstance(current_output, SelectionClosed) and current_output.disposition not in SELECTABLE_DISPOSITIONS


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
