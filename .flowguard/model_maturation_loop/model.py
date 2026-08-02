"""Executable model for maturation receipt verification and separate admission."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class MaturationRequest:
    task_id: str
    demand_fingerprint: str
    unresolved_owner_ids: tuple[str, ...]
    implementation_authorized: bool


@dataclass(frozen=True)
class MaturationEvaluated:
    task_id: str
    demand_fingerprint: str
    decision: str


@dataclass(frozen=True)
class ReceiptPublished:
    task_id: str
    demand_fingerprint: str
    decision: str
    receipt_fingerprint: str


@dataclass(frozen=True)
class ReceiptVerified:
    task_id: str
    demand_fingerprint: str
    decision: str
    receipt_fingerprint: str


@dataclass(frozen=True)
class AdmissionDecided:
    task_id: str
    admission: str
    receipt_fingerprint: str
    maturation_decision: str


@dataclass(frozen=True)
class ConfidenceDecided:
    task_id: str
    confidence: str
    receipt_fingerprint: str


@dataclass(frozen=True)
class ClosureChecked:
    task_id: str
    closure: str
    confidence: str
    receipt_fingerprint: str


@dataclass(frozen=True)
class State:
    maturation_decisions: tuple[tuple[str, str], ...] = ()
    published_receipts: tuple[str, ...] = ()
    verified_receipts: tuple[str, ...] = ()
    ready_task_ids: tuple[str, ...] = ()
    confidence_by_task: tuple[tuple[str, str], ...] = ()
    closed_task_ids: tuple[str, ...] = ()
    authorization_by_task: tuple[tuple[str, bool], ...] = ()


class EvaluateMaturation:
    name = "EvaluateMaturation"
    reads = ()
    writes = ("maturation_decisions", "authorization_by_task")
    accepted_input_type = MaturationRequest
    input_description = "Exact task, compiled demand, and independent authorization fact"
    output_description = "Closed or blocked maturation result"

    def apply(self, input_obj: MaturationRequest, state: State) -> Iterable[FunctionResult]:
        decision = "closed" if not input_obj.unresolved_owner_ids else "blocked"
        yield FunctionResult(
            MaturationEvaluated(input_obj.task_id, input_obj.demand_fingerprint, decision),
            replace(
                state,
                maturation_decisions=state.maturation_decisions + ((input_obj.task_id, decision),),
                authorization_by_task=state.authorization_by_task + ((input_obj.task_id, input_obj.implementation_authorized),),
            ),
            label="maturation_closed" if decision == "closed" else "maturation_blocked",
        )


class PublishReceipt:
    name = "PublishReceipt"
    reads = ("maturation_decisions",)
    writes = ("published_receipts",)
    accepted_input_type = MaturationEvaluated
    input_description = "Terminal maturation result"
    output_description = "Content-addressed maturation receipt"

    def apply(self, input_obj: MaturationEvaluated, state: State) -> Iterable[FunctionResult]:
        fingerprint = f"receipt:{input_obj.task_id}:{input_obj.demand_fingerprint}:{input_obj.decision}"
        yield FunctionResult(
            ReceiptPublished(input_obj.task_id, input_obj.demand_fingerprint, input_obj.decision, fingerprint),
            replace(state, published_receipts=state.published_receipts + (fingerprint,)),
            label="maturation_receipt_published",
        )


class VerifyReceipt:
    name = "VerifyReceipt"
    reads = ("published_receipts",)
    writes = ("verified_receipts",)
    accepted_input_type = ReceiptPublished
    input_description = "Canonical receipt reference"
    output_description = "Independently verified maturation projection"

    def apply(self, input_obj: ReceiptPublished, state: State) -> Iterable[FunctionResult]:
        if input_obj.receipt_fingerprint not in state.published_receipts:
            return
        yield FunctionResult(
            ReceiptVerified(input_obj.task_id, input_obj.demand_fingerprint, input_obj.decision, input_obj.receipt_fingerprint),
            replace(state, verified_receipts=state.verified_receipts + (input_obj.receipt_fingerprint,)),
            label="maturation_receipt_verified",
        )


class DecideAdmission:
    name = "DecideAdmission"
    reads = ("verified_receipts", "authorization_by_task", "maturation_decisions")
    writes = ("ready_task_ids",)
    accepted_input_type = ReceiptVerified
    input_description = "Verified maturation result"
    output_description = "Separate implementation admission"

    def apply(self, input_obj: ReceiptVerified, state: State) -> Iterable[FunctionResult]:
        authorized = next((value for task_id, value in state.authorization_by_task if task_id == input_obj.task_id), False)
        if input_obj.receipt_fingerprint not in state.verified_receipts or input_obj.decision != "closed":
            admission = "blocked"
        elif not authorized:
            admission = "no_code_requested"
        else:
            admission = "ready"
        yield FunctionResult(
            AdmissionDecided(
                input_obj.task_id,
                admission,
                input_obj.receipt_fingerprint,
                input_obj.decision,
            ),
            replace(
                state,
                ready_task_ids=state.ready_task_ids + ((input_obj.task_id,) if admission == "ready" else ()),
            ),
            label=f"implementation_{admission}",
        )


class DecideConfidence:
    name = "DecideConfidence"
    reads = ("verified_receipts", "maturation_decisions")
    writes = ("confidence_by_task",)
    accepted_input_type = AdmissionDecided
    input_description = "Implementation admission bound to the verified maturation receipt"
    output_description = "Broad, scoped, or blocked confidence decision"

    def apply(self, input_obj: AdmissionDecided, state: State) -> Iterable[FunctionResult]:
        verified = input_obj.receipt_fingerprint in state.verified_receipts
        if verified and input_obj.maturation_decision == "closed" and input_obj.admission == "ready":
            confidence = "full"
        elif verified and input_obj.maturation_decision == "closed" and input_obj.admission == "no_code_requested":
            confidence = "scoped"
        else:
            confidence = "blocked"
        yield FunctionResult(
            ConfidenceDecided(input_obj.task_id, confidence, input_obj.receipt_fingerprint),
            replace(
                state,
                confidence_by_task=state.confidence_by_task + ((input_obj.task_id, confidence),),
            ),
            label=f"risk_confidence_{confidence}",
        )


class VerifyClosure:
    name = "VerifyClosure"
    reads = ("verified_receipts", "confidence_by_task")
    writes = ("closed_task_ids",)
    accepted_input_type = ConfidenceDecided
    input_description = "Risk decision and exact maturation receipt identity"
    output_description = "Thin closure-integrity decision"

    def apply(self, input_obj: ConfidenceDecided, state: State) -> Iterable[FunctionResult]:
        exact = (
            input_obj.receipt_fingerprint in state.verified_receipts
            and dict(state.confidence_by_task).get(input_obj.task_id) == input_obj.confidence
        )
        closure = "closed" if exact and input_obj.confidence in {"full", "scoped"} else "blocked"
        yield FunctionResult(
            ClosureChecked(
                input_obj.task_id,
                closure,
                input_obj.confidence,
                input_obj.receipt_fingerprint,
            ),
            replace(
                state,
                closed_task_ids=state.closed_task_ids + ((input_obj.task_id,) if closure == "closed" else ()),
            ),
            label=f"closure_integrity_{closure}",
        )


class BrokenPermissionUpgradesMaturation(DecideAdmission):
    name = "BrokenPermissionUpgradesMaturation"

    def apply(self, input_obj: ReceiptVerified, state: State) -> Iterable[FunctionResult]:
        authorized = next((value for task_id, value in state.authorization_by_task if task_id == input_obj.task_id), False)
        admission = "ready" if authorized else "no_code_requested"
        yield FunctionResult(
            AdmissionDecided(
                input_obj.task_id,
                admission,
                input_obj.receipt_fingerprint,
                input_obj.decision,
            ),
            replace(state, ready_task_ids=state.ready_task_ids + ((input_obj.task_id,) if admission == "ready" else ())),
            label="permission_upgraded_maturation",
        )


def ready_requires_verified_closed_receipt(state: State, _trace) -> InvariantResult:
    decisions = dict(state.maturation_decisions)
    for task_id in state.ready_task_ids:
        if decisions.get(task_id) != "closed" or not state.verified_receipts:
            return InvariantResult.fail(f"implementation ready without verified closed maturation: {task_id}")
    return InvariantResult.pass_()


def confidence_and_closure_preserve_verified_maturation(state: State, _trace) -> InvariantResult:
    decisions = dict(state.maturation_decisions)
    confidence = dict(state.confidence_by_task)
    for task_id, level in confidence.items():
        if level == "full" and decisions.get(task_id) != "closed":
            return InvariantResult.fail(f"full confidence upgraded blocked maturation: {task_id}")
    for task_id in state.closed_task_ids:
        if confidence.get(task_id) not in {"full", "scoped"} or decisions.get(task_id) != "closed":
            return InvariantResult.fail(f"closure hid insufficient maturation or risk: {task_id}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("ready_requires_verified_closed_receipt", "permission cannot upgrade insufficient maturation", ready_requires_verified_closed_receipt),
    Invariant(
        "confidence_and_closure_preserve_verified_maturation",
        "risk owns confidence and closure owns only exact integrity; neither upgrades maturation",
        confidence_and_closure_preserve_verified_maturation,
    ),
)
CLOSED_REQUEST = MaturationRequest("task:closed", "sha256:demand-closed", (), True)
BLOCKED_REQUEST = MaturationRequest("task:blocked", "sha256:demand-blocked", ("ui-flow",), True)
EXTERNAL_INPUTS = (CLOSED_REQUEST, BLOCKED_REQUEST)
MAX_SEQUENCE_LENGTH = 4


def initial_state() -> State:
    return State()


def correct_workflow() -> Workflow:
    return Workflow(
        (
            EvaluateMaturation(),
            PublishReceipt(),
            VerifyReceipt(),
            DecideAdmission(),
            DecideConfidence(),
            VerifyClosure(),
        ),
        name="model_maturation_loop",
    )


def broken_permission_upgrade_workflow() -> Workflow:
    return Workflow(
        (
            EvaluateMaturation(),
            PublishReceipt(),
            VerifyReceipt(),
            BrokenPermissionUpgradesMaturation(),
            DecideConfidence(),
            VerifyClosure(),
        ),
        name="broken_permission_upgrade",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, ClosureChecked)


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
