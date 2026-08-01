"""FlowGuard Risk Purpose Header.

Purpose:
Models the mandatory FlowGuard closure contract for complete use claims.

Guards against:
- treating closure as an optional/default mode;
- accepting complete FlowGuard use from only a model pass or test pass;
- claiming done/release/production confidence while intake, ownership,
  same-class miss evidence, alignment, freshness, ledger, or claim-chain gates
  are missing.

Run:
python .flowguard/flowguard_closure_contract/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class ClosureAction:
    action_type: str
    maturation_evidence_id: str = ""
    maturation_current: bool = False
    maturation_decision: str = ""


@dataclass(frozen=True)
class ClosureOutput:
    status: str


@dataclass(frozen=True)
class ClosureState:
    contract_declared: bool = False
    described_as_mode: bool = False
    plan_risk_intake_current: bool = False
    model_ownership_current: bool = False
    same_class_miss_evidence_current: bool = False
    alignment_current: bool = False
    mesh_or_boundary_current: bool = False
    freshness_current: bool = False
    ledger_current: bool = False
    claim_chain_current: bool = False
    model_maturation_current: bool = False
    model_maturation_closed: bool = False
    model_maturation_evidence_id: str = ""
    risk_maturation_evidence_id: str = ""
    completion_claim: str = "none"

    def closure_ready(self) -> bool:
        return (
            self.contract_declared
            and not self.described_as_mode
            and self.plan_risk_intake_current
            and self.model_ownership_current
            and self.same_class_miss_evidence_current
            and self.alignment_current
            and self.mesh_or_boundary_current
            and self.freshness_current
            and self.ledger_current
            and self.claim_chain_current
            and self.model_maturation_current
            and self.model_maturation_closed
            and bool(self.model_maturation_evidence_id)
            and self.risk_maturation_evidence_id
            == self.model_maturation_evidence_id
        )


class ClosureContractFlow:
    name = "ClosureContractFlow"
    reads = (
        "contract_declared",
        "described_as_mode",
        "plan_risk_intake_current",
        "model_ownership_current",
        "same_class_miss_evidence_current",
        "alignment_current",
        "mesh_or_boundary_current",
        "freshness_current",
        "ledger_current",
        "claim_chain_current",
        "model_maturation_current",
        "model_maturation_closed",
        "model_maturation_evidence_id",
        "risk_maturation_evidence_id",
    )
    writes = reads + ("completion_claim",)
    accepted_input_type = ClosureAction
    input_description = "FlowGuard closure-contract action"
    output_description = "current closure evidence and completion claim"
    idempotency = "Complete FlowGuard use is accepted only after closure gates are current."

    def apply(self, input_obj: ClosureAction, state: ClosureState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "declare_contract":
            yield FunctionResult(ClosureOutput("contract_declared"), replace(state, contract_declared=True), label="contract_declared")
        elif action == "describe_as_optional_mode":
            yield FunctionResult(ClosureOutput("described_as_mode"), replace(state, described_as_mode=True), label="described_as_mode")
        elif action == "complete_plan_risk_intake":
            yield FunctionResult(ClosureOutput("plan_risk_intake_current"), replace(state, plan_risk_intake_current=True), label="plan_risk_intake_current")
        elif action == "confirm_model_ownership":
            yield FunctionResult(ClosureOutput("model_ownership_current"), replace(state, model_ownership_current=True), label="model_ownership_current")
        elif action == "add_same_class_miss_evidence":
            yield FunctionResult(ClosureOutput("same_class_miss_evidence_current"), replace(state, same_class_miss_evidence_current=True), label="same_class_miss_evidence_current")
        elif action == "align_model_code_test":
            yield FunctionResult(ClosureOutput("alignment_current"), replace(state, alignment_current=True), label="alignment_current")
        elif action == "prove_mesh_or_boundary":
            yield FunctionResult(ClosureOutput("mesh_or_boundary_current"), replace(state, mesh_or_boundary_current=True), label="mesh_or_boundary_current")
        elif action == "refresh_evidence":
            yield FunctionResult(ClosureOutput("freshness_current"), replace(state, freshness_current=True), label="freshness_current")
        elif action == "consume_model_maturation":
            current_closed = (
                bool(input_obj.maturation_evidence_id)
                and input_obj.maturation_current
                and input_obj.maturation_decision == "closed_for_task"
            )
            yield FunctionResult(
                ClosureOutput(
                    "model_maturation_current" if current_closed else "model_maturation_rejected"
                ),
                replace(
                    state,
                    model_maturation_current=current_closed,
                    model_maturation_closed=current_closed,
                    model_maturation_evidence_id=input_obj.maturation_evidence_id,
                ),
                label=(
                    "model_maturation_current" if current_closed else "model_maturation_rejected"
                ),
            )
        elif action == "run_risk_ledger":
            exact = (
                bool(input_obj.maturation_evidence_id)
                and input_obj.maturation_evidence_id
                == state.model_maturation_evidence_id
            )
            yield FunctionResult(
                ClosureOutput("ledger_current" if exact else "ledger_maturation_mismatch"),
                replace(
                    state,
                    ledger_current=exact,
                    risk_maturation_evidence_id=input_obj.maturation_evidence_id,
                ),
                label="ledger_current" if exact else "ledger_maturation_mismatch",
            )
        elif action == "run_claim_chain":
            yield FunctionResult(ClosureOutput("claim_chain_current"), replace(state, claim_chain_current=True), label="claim_chain_current")
        elif action == "claim_complete_flowguard_use":
            claim = "accepted" if state.closure_ready() else "rejected"
            yield FunctionResult(ClosureOutput(f"completion_{claim}"), replace(state, completion_claim=claim), label=f"completion_{claim}")


class BrokenPointEvidenceCompletion(ClosureContractFlow):
    name = "BrokenPointEvidenceCompletion"
    idempotency = "Broken variant treats a model/test pass as complete FlowGuard use."

    def apply(self, input_obj: ClosureAction, state: ClosureState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_complete_flowguard_use":
            enough_point_evidence = state.model_ownership_current and state.alignment_current
            claim = "accepted" if enough_point_evidence else "rejected"
            yield FunctionResult(ClosureOutput(f"completion_{claim}"), replace(state, completion_claim=claim), label=f"completion_{claim}")
            return
        yield from super().apply(input_obj, state)


def no_complete_claim_without_closure(state: ClosureState, trace) -> InvariantResult:
    del trace
    if state.completion_claim == "accepted" and not state.closure_ready():
        return InvariantResult.fail("complete FlowGuard use accepted without current closure contract")
    return InvariantResult.pass_()


def closure_is_not_optional_mode(state: ClosureState, trace) -> InvariantResult:
    del trace
    if state.described_as_mode:
        return InvariantResult.fail("closure was treated as an optional/default mode")
    return InvariantResult.pass_()


def closure_and_risk_use_same_maturation_identity(
    state: ClosureState, trace
) -> InvariantResult:
    del trace
    if state.completion_claim == "accepted" and (
        not state.model_maturation_evidence_id
        or state.risk_maturation_evidence_id
        != state.model_maturation_evidence_id
    ):
        return InvariantResult.fail(
            "closure and risk ledger did not consume the same model-maturation evidence identity"
        )
    return InvariantResult.pass_()


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, ClosureOutput) and current_output.status.startswith("completion_")


INVARIANTS = (
    Invariant(
        "no_complete_claim_without_closure",
        "Complete FlowGuard use requires every required closure gate.",
        no_complete_claim_without_closure,
    ),
    Invariant(
        "closure_is_not_optional_mode",
        "The closure contract is intrinsic to FlowGuard use, not a mode.",
        closure_is_not_optional_mode,
    ),
    Invariant(
        "closure_and_risk_use_same_maturation_identity",
        "Risk and closure must consume the same current closed-for-task maturation evidence.",
        closure_and_risk_use_same_maturation_identity,
    ),
)

EXTERNAL_INPUTS = (
    ClosureAction("declare_contract"),
    ClosureAction("describe_as_optional_mode"),
    ClosureAction("complete_plan_risk_intake"),
    ClosureAction("confirm_model_ownership"),
    ClosureAction("add_same_class_miss_evidence"),
    ClosureAction("align_model_code_test"),
    ClosureAction("prove_mesh_or_boundary"),
    ClosureAction("refresh_evidence"),
    ClosureAction("consume_model_maturation"),
    ClosureAction("run_risk_ledger"),
    ClosureAction("run_claim_chain"),
    ClosureAction("claim_complete_flowguard_use"),
)

GOOD_SEQUENCE = (
    ClosureAction("declare_contract"),
    ClosureAction("complete_plan_risk_intake"),
    ClosureAction("confirm_model_ownership"),
    ClosureAction("add_same_class_miss_evidence"),
    ClosureAction("align_model_code_test"),
    ClosureAction("prove_mesh_or_boundary"),
    ClosureAction("refresh_evidence"),
    ClosureAction(
        "consume_model_maturation",
        maturation_evidence_id="maturation:self-upgrade",
        maturation_current=True,
        maturation_decision="closed_for_task",
    ),
    ClosureAction(
        "run_risk_ledger",
        maturation_evidence_id="maturation:self-upgrade",
    ),
    ClosureAction("run_claim_chain"),
    ClosureAction("claim_complete_flowguard_use"),
)

BROKEN_POINT_SEQUENCE = (
    ClosureAction("confirm_model_ownership"),
    ClosureAction("align_model_code_test"),
    ClosureAction("claim_complete_flowguard_use"),
)

BROKEN_MATURATION_IDENTITY_SEQUENCE = (
    ClosureAction("declare_contract"),
    ClosureAction("complete_plan_risk_intake"),
    ClosureAction("confirm_model_ownership"),
    ClosureAction("add_same_class_miss_evidence"),
    ClosureAction("align_model_code_test"),
    ClosureAction("prove_mesh_or_boundary"),
    ClosureAction("refresh_evidence"),
    ClosureAction(
        "consume_model_maturation",
        maturation_evidence_id="maturation:one",
        maturation_current=True,
        maturation_decision="closed_for_task",
    ),
    ClosureAction("run_risk_ledger", maturation_evidence_id="maturation:two"),
    ClosureAction("run_claim_chain"),
    ClosureAction("claim_complete_flowguard_use"),
)

BROKEN_MODE_SEQUENCE = (
    ClosureAction("declare_contract"),
    ClosureAction("describe_as_optional_mode"),
    ClosureAction("complete_plan_risk_intake"),
    ClosureAction("confirm_model_ownership"),
    ClosureAction("add_same_class_miss_evidence"),
    ClosureAction("align_model_code_test"),
    ClosureAction("prove_mesh_or_boundary"),
    ClosureAction("refresh_evidence"),
    ClosureAction(
        "consume_model_maturation",
        maturation_evidence_id="maturation:self-upgrade",
        maturation_current=True,
        maturation_decision="closed_for_task",
    ),
    ClosureAction(
        "run_risk_ledger",
        maturation_evidence_id="maturation:self-upgrade",
    ),
    ClosureAction("run_claim_chain"),
    ClosureAction("claim_complete_flowguard_use"),
)


def initial_state() -> ClosureState:
    return ClosureState()


def build_correct_workflow() -> Workflow:
    return Workflow((ClosureContractFlow(),), name="closure_contract_correct")


def build_broken_workflow() -> Workflow:
    return Workflow((BrokenPointEvidenceCompletion(),), name="closure_contract_broken")


__all__ = [
    "BROKEN_MODE_SEQUENCE",
    "BROKEN_MATURATION_IDENTITY_SEQUENCE",
    "BROKEN_POINT_SEQUENCE",
    "EXTERNAL_INPUTS",
    "GOOD_SEQUENCE",
    "INVARIANTS",
    "ClosureAction",
    "ClosureOutput",
    "ClosureState",
    "build_broken_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
