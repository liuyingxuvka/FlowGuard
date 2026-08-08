"""Executable model for maturation receipt verification and separate admission."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class OwnerResolution:
    owner_id: str
    resolution_id: str
    resolution_fingerprint: str
    disposition: str
    evidence_id: str
    evidence_fingerprint: str


@dataclass(frozen=True)
class PathQualitySummary:
    model_id: str
    subject_fingerprints: tuple[tuple[str, str], ...]
    mode: str
    conclusion: str
    detail_evidence_fingerprint: str
    unresolved_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaturationRequest:
    task_id: str
    demand_id: str
    demand_fingerprint: str
    required_owner_ids: tuple[str, ...]
    owner_resolutions: tuple[OwnerResolution, ...]
    required_model_ids: tuple[str, ...]
    path_quality_summaries: tuple[PathQualitySummary, ...]
    open_gap_ids: tuple[str, ...]
    implementation_authorized: bool


@dataclass(frozen=True)
class MaturationEvaluated:
    task_id: str
    demand_id: str
    demand_fingerprint: str
    resolution_set_fingerprint: str
    decision: str


@dataclass(frozen=True)
class ReceiptPublished:
    task_id: str
    demand_id: str
    demand_fingerprint: str
    resolution_set_fingerprint: str
    decision: str
    receipt_fingerprint: str


@dataclass(frozen=True)
class ReceiptVerified:
    task_id: str
    demand_id: str
    demand_fingerprint: str
    resolution_set_fingerprint: str
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
    published_receipts: tuple[tuple[str, str, str, str, str, str], ...] = ()
    verified_receipts: tuple[tuple[str, str, str, str, str, str], ...] = ()
    ready_task_ids: tuple[str, ...] = ()
    confidence_by_task: tuple[tuple[str, str], ...] = ()
    closed_task_ids: tuple[str, ...] = ()
    authorization_by_task: tuple[tuple[str, bool], ...] = ()
    path_quality_by_task: tuple[tuple[str, str], ...] = ()


class EvaluateMaturation:
    name = "EvaluateMaturation"
    reads = ()
    writes = ("maturation_decisions", "authorization_by_task", "path_quality_by_task")
    accepted_input_type = MaturationRequest
    input_description = "Exact task, compiled demand, and independent authorization fact"
    output_description = "Closed or blocked maturation result"

    def apply(self, input_obj: MaturationRequest, state: State) -> Iterable[FunctionResult]:
        required_owners = tuple(sorted(set(input_obj.required_owner_ids)))
        resolutions = tuple(sorted(input_obj.owner_resolutions, key=lambda item: item.owner_id))
        resolution_owners = tuple(item.owner_id for item in resolutions)
        exact_owner_set = (
            bool(required_owners)
            and len(required_owners) == len(input_obj.required_owner_ids)
            and len(resolution_owners) == len(set(resolution_owners))
            and set(resolution_owners) == set(required_owners)
        )
        exact_resolution_ids = len({item.resolution_id for item in resolutions}) == len(resolutions)
        current_evidence = all(
            item.disposition == "satisfied"
            and bool(item.resolution_id)
            and item.resolution_fingerprint.startswith("sha256:")
            and bool(item.evidence_id)
            and item.evidence_fingerprint.startswith("sha256:")
            for item in resolutions
        )
        exact_demand = (
            bool(input_obj.task_id)
            and bool(input_obj.demand_id)
            and input_obj.demand_fingerprint.startswith("sha256:")
        )
        required_models = tuple(sorted(set(input_obj.required_model_ids)))
        path_summaries = tuple(sorted(input_obj.path_quality_summaries, key=lambda item: item.model_id))
        path_model_ids = tuple(item.model_id for item in path_summaries)
        exact_path_set = (
            bool(required_models)
            and len(required_models) == len(input_obj.required_model_ids)
            and len(path_model_ids) == len(set(path_model_ids))
            and set(path_model_ids) == set(required_models)
        )
        accepted_conclusions = {
            "single_clear_path",
            "preferred_within_candidates",
            "non_dominated_within_boundary",
            "minimum_within_exhausted_finite_set",
            "locally_irreducible_under_declared_rewrites",
        }
        current_path_quality = exact_path_set and all(
            item.mode in {"lightweight", "deep"}
            and item.conclusion in accepted_conclusions
            and item.detail_evidence_fingerprint.startswith("sha256:")
            and not item.unresolved_ids
            and bool(item.subject_fingerprints)
            and len({name for name, _fingerprint in item.subject_fingerprints}) == len(item.subject_fingerprints)
            and all(name and fingerprint.startswith("sha256:") for name, fingerprint in item.subject_fingerprints)
            for item in path_summaries
        )
        decision = (
            "closed"
            if exact_demand
            and exact_owner_set
            and exact_resolution_ids
            and current_evidence
            and current_path_quality
            and not input_obj.open_gap_ids
            else "blocked"
        )
        resolution_set_fingerprint = "sha256:resolution-set:" + ":".join(
            item.resolution_fingerprint.removeprefix("sha256:") for item in resolutions
        )
        yield FunctionResult(
            MaturationEvaluated(
                input_obj.task_id,
                input_obj.demand_id,
                input_obj.demand_fingerprint,
                resolution_set_fingerprint,
                decision,
            ),
            replace(
                state,
                maturation_decisions=state.maturation_decisions + ((input_obj.task_id, decision),),
                authorization_by_task=state.authorization_by_task + ((input_obj.task_id, input_obj.implementation_authorized),),
                path_quality_by_task=state.path_quality_by_task
                + ((input_obj.task_id, "current" if current_path_quality else "blocked"),),
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
        fingerprint = (
            f"receipt:{input_obj.task_id}:{input_obj.demand_id}:"
            f"{input_obj.demand_fingerprint}:{input_obj.resolution_set_fingerprint}:"
            f"{input_obj.decision}"
        )
        yield FunctionResult(
            ReceiptPublished(
                input_obj.task_id,
                input_obj.demand_id,
                input_obj.demand_fingerprint,
                input_obj.resolution_set_fingerprint,
                input_obj.decision,
                fingerprint,
            ),
            replace(
                state,
                published_receipts=state.published_receipts
                + ((
                    input_obj.task_id,
                    input_obj.demand_id,
                    input_obj.demand_fingerprint,
                    input_obj.resolution_set_fingerprint,
                    input_obj.decision,
                    fingerprint,
                ),),
            ),
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
        identity = (
            input_obj.task_id,
            input_obj.demand_id,
            input_obj.demand_fingerprint,
            input_obj.resolution_set_fingerprint,
            input_obj.decision,
            input_obj.receipt_fingerprint,
        )
        if identity not in state.published_receipts:
            return
        yield FunctionResult(
            ReceiptVerified(
                input_obj.task_id,
                input_obj.demand_id,
                input_obj.demand_fingerprint,
                input_obj.resolution_set_fingerprint,
                input_obj.decision,
                input_obj.receipt_fingerprint,
            ),
            replace(state, verified_receipts=state.verified_receipts + (identity,)),
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
        identity = (
            input_obj.task_id,
            input_obj.demand_id,
            input_obj.demand_fingerprint,
            input_obj.resolution_set_fingerprint,
            input_obj.decision,
            input_obj.receipt_fingerprint,
        )
        if identity not in state.verified_receipts or input_obj.decision != "closed":
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
        verified = any(
            task_id == input_obj.task_id
            and decision == input_obj.maturation_decision
            and fingerprint == input_obj.receipt_fingerprint
            for task_id, _demand_id, _demand_fingerprint, _resolution_set, decision, fingerprint in state.verified_receipts
        )
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
            any(
                task_id == input_obj.task_id and fingerprint == input_obj.receipt_fingerprint
                for task_id, _demand_id, _demand_fingerprint, _resolution_set, _decision, fingerprint in state.verified_receipts
            )
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


class BrokenPathQualityBypass(EvaluateMaturation):
    name = "BrokenPathQualityBypass"

    def apply(self, input_obj: MaturationRequest, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            MaturationEvaluated(
                input_obj.task_id,
                input_obj.demand_id,
                input_obj.demand_fingerprint,
                "sha256:resolution-set:path-quality-bypassed",
                "closed",
            ),
            replace(
                state,
                maturation_decisions=state.maturation_decisions + ((input_obj.task_id, "closed"),),
                authorization_by_task=state.authorization_by_task
                + ((input_obj.task_id, input_obj.implementation_authorized),),
                path_quality_by_task=state.path_quality_by_task + ((input_obj.task_id, "blocked"),),
            ),
            label="path_quality_bypassed",
        )


def ready_requires_verified_closed_receipt(state: State, _trace) -> InvariantResult:
    decisions = dict(state.maturation_decisions)
    path_quality = dict(state.path_quality_by_task)
    for task_id in state.ready_task_ids:
        exact_verified = any(
            receipt_task_id == task_id and decision == "closed"
            for receipt_task_id, _demand_id, _demand_fingerprint, _resolution_set, decision, _fingerprint in state.verified_receipts
        )
        if decisions.get(task_id) != "closed" or not exact_verified or path_quality.get(task_id) != "current":
            return InvariantResult.fail(f"implementation ready without verified closed maturation: {task_id}")
    return InvariantResult.pass_()


def confidence_and_closure_preserve_verified_maturation(state: State, _trace) -> InvariantResult:
    decisions = dict(state.maturation_decisions)
    path_quality = dict(state.path_quality_by_task)
    confidence = dict(state.confidence_by_task)
    for task_id, level in confidence.items():
        if level == "full" and (decisions.get(task_id) != "closed" or path_quality.get(task_id) != "current"):
            return InvariantResult.fail(f"full confidence upgraded blocked maturation: {task_id}")
    for task_id in state.closed_task_ids:
        if (
            confidence.get(task_id) not in {"full", "scoped"}
            or decisions.get(task_id) != "closed"
            or path_quality.get(task_id) != "current"
        ):
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
CLOSED_RESOLUTIONS = (
    OwnerResolution(
        "existing-model-preflight",
        "resolution:preflight",
        "sha256:resolution-preflight",
        "satisfied",
        "evidence:preflight",
        "sha256:evidence-preflight",
    ),
    OwnerResolution(
        "model-test-alignment",
        "resolution:alignment",
        "sha256:resolution-alignment",
        "satisfied",
        "evidence:alignment",
        "sha256:evidence-alignment",
    ),
)
CLOSED_REQUEST = MaturationRequest(
    "task:closed",
    "demand:closed",
    "sha256:demand-closed",
    ("existing-model-preflight", "model-test-alignment"),
    CLOSED_RESOLUTIONS,
    ("model:task",),
    (
        PathQualitySummary(
            "model:task",
            (
                ("model", "sha256:model-task"),
                ("purpose", "sha256:purpose-task"),
                ("intent", "sha256:intent-task"),
                ("obligation", "sha256:obligation-task"),
                ("binding", "sha256:binding-task"),
                ("oracle", "sha256:oracle-task"),
            ),
            "lightweight",
            "single_clear_path",
            "sha256:path-quality-task",
        ),
    ),
    (),
    True,
)
BLOCKED_REQUEST = MaturationRequest(
    "task:blocked",
    "demand:blocked",
    "sha256:demand-blocked",
    ("existing-model-preflight", "model-test-alignment", "ui-flow"),
    CLOSED_RESOLUTIONS,
    ("model:task",),
    (),
    ("missing_owner_resolution:ui-flow",),
    True,
)
EXTERNAL_INPUTS = (CLOSED_REQUEST, BLOCKED_REQUEST)
MAX_SEQUENCE_LENGTH = 6


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


def broken_path_quality_bypass_workflow() -> Workflow:
    return Workflow(
        (
            BrokenPathQualityBypass(),
            PublishReceipt(),
            VerifyReceipt(),
            DecideAdmission(),
            DecideConfidence(),
            VerifyClosure(),
        ),
        name="broken_path_quality_bypass",
    )


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, ClosureChecked)


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
