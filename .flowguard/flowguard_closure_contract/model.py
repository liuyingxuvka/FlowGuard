"""Executable model for the thin FlowGuard ClosureContract.

Closure consumes exact upstream identities and terminal decisions. It checks
identity, required material, and terminal agreement; it never recomputes model
quality, test coverage, implementation authorization, or risk.

Run: python .flowguard/flowguard_closure_contract/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class ClosureAction:
    action_type: str
    task_id: str = ""
    maturation_receipt_id: str = ""
    maturation_status: str = ""
    admission_status: str = ""
    risk_decision: str = ""
    risk_confidence: str = ""


@dataclass(frozen=True)
class ClosureOutput:
    status: str


@dataclass(frozen=True)
class ClosureState:
    task_id: str = ""
    maturation_receipt_id: str = ""
    maturation_status: str = "not_run"
    admission_maturation_receipt_id: str = ""
    admission_status: str = "not_requested"
    risk_maturation_receipt_id: str = ""
    risk_decision: str = "not_run"
    risk_confidence: str = "not_run"
    completion_claim: str = "none"

    def closure_ready(self) -> bool:
        same_identity = bool(self.task_id and self.maturation_receipt_id) and (
            self.admission_maturation_receipt_id == self.maturation_receipt_id
            and self.risk_maturation_receipt_id == self.maturation_receipt_id
        )
        terminal_pair = (self.risk_decision, self.risk_confidence) in {
            ("risk_evidence_full_confidence", "full"),
            ("risk_evidence_scoped_confidence", "scoped"),
        }
        admission_terminal = self.admission_status in {
            "ready",
            "ready_scoped",
            "no_code_requested",
        }
        return (
            same_identity
            and self.maturation_status in {"verified", "scoped_verified"}
            and admission_terminal
            and terminal_pair
        )


class ThinClosureContract:
    name = "ThinClosureContract"
    reads = (
        "task_id",
        "maturation_receipt_id",
        "maturation_status",
        "admission_maturation_receipt_id",
        "admission_status",
        "risk_maturation_receipt_id",
        "risk_decision",
        "risk_confidence",
    )
    writes = reads + ("completion_claim",)
    accepted_input_type = ClosureAction
    input_description = "Exact upstream maturation, admission, and risk terminal results"
    output_description = "Thin identity/material/terminal closure result"

    def apply(self, input_obj: ClosureAction, state: ClosureState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "consume_maturation":
            yield FunctionResult(
                ClosureOutput("maturation_consumed"),
                replace(
                    state,
                    task_id=input_obj.task_id,
                    maturation_receipt_id=input_obj.maturation_receipt_id,
                    maturation_status=input_obj.maturation_status,
                ),
                label="maturation_consumed",
            )
        elif input_obj.action_type == "consume_admission":
            yield FunctionResult(
                ClosureOutput("admission_consumed"),
                replace(
                    state,
                    admission_maturation_receipt_id=input_obj.maturation_receipt_id,
                    admission_status=input_obj.admission_status,
                ),
                label="admission_consumed",
            )
        elif input_obj.action_type == "consume_risk":
            yield FunctionResult(
                ClosureOutput("risk_consumed"),
                replace(
                    state,
                    risk_maturation_receipt_id=input_obj.maturation_receipt_id,
                    risk_decision=input_obj.risk_decision,
                    risk_confidence=input_obj.risk_confidence,
                ),
                label="risk_consumed",
            )
        elif input_obj.action_type == "check_closure":
            claim = "accepted" if state.closure_ready() else "blocked"
            yield FunctionResult(
                ClosureOutput(f"closure_{claim}"),
                replace(state, completion_claim=claim),
                label=f"closure_{claim}",
            )


class BrokenClosureRescoresRisk(ThinClosureContract):
    name = "BrokenClosureRescoresRisk"

    def apply(self, input_obj: ClosureAction, state: ClosureState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "check_closure":
            claim = (
                "accepted"
                if state.maturation_status in {"verified", "scoped_verified"}
                else "blocked"
            )
            yield FunctionResult(
                ClosureOutput(f"closure_{claim}"),
                replace(state, completion_claim=claim),
                label="closure_rescored_risk",
            )
            return
        yield from super().apply(input_obj, state)


def accepted_closure_requires_exact_upstream_terminals(
    state: ClosureState,
    _trace,
) -> InvariantResult:
    if state.completion_claim == "accepted" and not state.closure_ready():
        return InvariantResult.fail(
            "Closure accepted after recomputing or bypassing an upstream terminal decision"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_closure_requires_exact_upstream_terminals",
        "Closure checks exact maturation/admission/risk identity and terminal agreement without rescoring.",
        accepted_closure_requires_exact_upstream_terminals,
    ),
)


GOOD_SEQUENCE = (
    ClosureAction("consume_maturation", "task:self", "receipt:self", "verified"),
    ClosureAction(
        "consume_admission",
        "task:self",
        "receipt:self",
        admission_status="ready",
    ),
    ClosureAction(
        "consume_risk",
        "task:self",
        "receipt:self",
        risk_decision="risk_evidence_full_confidence",
        risk_confidence="full",
    ),
    ClosureAction("check_closure"),
)

BROKEN_IDENTITY_SEQUENCE = (
    ClosureAction("consume_maturation", "task:self", "receipt:self", "verified"),
    ClosureAction(
        "consume_admission",
        "task:self",
        "receipt:other",
        admission_status="ready",
    ),
    ClosureAction(
        "consume_risk",
        "task:self",
        "receipt:self",
        risk_decision="risk_evidence_full_confidence",
        risk_confidence="full",
    ),
    ClosureAction("check_closure"),
)

BROKEN_RESCORE_SEQUENCE = (
    ClosureAction("consume_maturation", "task:self", "receipt:self", "verified"),
    ClosureAction(
        "consume_admission",
        "task:self",
        "receipt:self",
        admission_status="ready",
    ),
    ClosureAction(
        "consume_risk",
        "task:self",
        "receipt:self",
        risk_decision="risk_evidence_blocked",
        risk_confidence="blocked",
    ),
    ClosureAction("check_closure"),
)

EXTERNAL_INPUTS = GOOD_SEQUENCE + BROKEN_IDENTITY_SEQUENCE + BROKEN_RESCORE_SEQUENCE
MAX_SEQUENCE_LENGTH = 4


def initial_state() -> ClosureState:
    return ClosureState()


def build_correct_workflow() -> Workflow:
    return Workflow((ThinClosureContract(),), name="thin_closure_contract")


def build_broken_workflow() -> Workflow:
    return Workflow((BrokenClosureRescoresRisk(),), name="broken_closure_rescores_risk")


def terminal_predicate(current_output, _state, _trace) -> bool:
    return isinstance(current_output, ClosureOutput) and current_output.status.startswith("closure_")


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


__all__ = [
    "BROKEN_IDENTITY_SEQUENCE",
    "BROKEN_RESCORE_SEQUENCE",
    "EXTERNAL_INPUTS",
    "GOOD_SEQUENCE",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "ClosureAction",
    "ClosureOutput",
    "ClosureState",
    "build_broken_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
