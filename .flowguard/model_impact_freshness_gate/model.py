"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the upgrade-time gate for existing FlowGuard models. The gate classifies
each old model before upgrade confidence is claimed.

Guards against:
- accepting a prior green model result without impact classification;
- reusing old model evidence when the upgrade touched the model's dependency
  surface but no same-output proof exists;
- accepting an affected model without model/test update review and current
  rerun evidence.

Use before editing:
framework upgrade checks, DevelopmentProcessFlow completion claims, release
notes that mention existing FlowGuard model freshness, and model reuse helpers.

Run:
python .flowguard/model_impact_freshness_gate/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class UpgradeAction:
    action_type: str
    observation_scope: str = "invocation_local"
    complete_observation_count: int = 2
    semantic_verification_count: int = 1
    final_identity_freshness_passed: bool = True


@dataclass(frozen=True)
class GateOutput:
    status: str


@dataclass(frozen=True)
class GateState:
    direct_upgrade_impact: bool = False
    impact_mapping_complete: bool = False
    classification: str = "unknown"
    same_output_proof: bool = False
    exact_current_receipt: bool = False
    model_update_reviewed: bool = False
    model_updated: bool = False
    test_update_reviewed: bool = False
    tests_updated: bool = False
    rerun_current: bool = False
    observation_scope: str = ""
    complete_observation_count: int = 0
    semantic_verification_count: int = 0
    final_identity_freshness_passed: bool = False
    old_evidence_passed: bool = True
    claim: str = "none"


def _ready_to_accept(state: GateState) -> bool:
    if not state.impact_mapping_complete:
        return False
    if state.classification == "affected":
        return (
            state.model_update_reviewed
            and state.test_update_reviewed
            and state.rerun_current
            and state.observation_scope == "invocation_local"
            and state.complete_observation_count == 2
            and state.semantic_verification_count == 1
            and state.final_identity_freshness_passed
        )
    if state.classification == "not_impacted":
        if state.direct_upgrade_impact and not state.same_output_proof:
            return False
        return state.exact_current_receipt
    return False


class CorrectModelImpactFreshnessGate:
    name = "CorrectModelImpactFreshnessGate"
    reads = (
        "direct_upgrade_impact",
        "impact_mapping_complete",
        "classification",
        "same_output_proof",
        "exact_current_receipt",
        "model_update_reviewed",
        "test_update_reviewed",
        "rerun_current",
        "observation_scope",
        "complete_observation_count",
        "semantic_verification_count",
        "final_identity_freshness_passed",
        "claim",
    )
    writes = reads
    accepted_input_type = UpgradeAction
    input_description = "model impact freshness action"
    output_description = "classification, reuse, rerun, or claim decision"
    idempotency = "Upgrade confidence requires classification plus either reuse proof or current rerun evidence."

    def apply(self, input_obj: UpgradeAction, state: GateState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "record_direct_upgrade_impact":
            yield FunctionResult(
                GateOutput("direct_upgrade_impact_recorded"),
                replace(state, direct_upgrade_impact=True, claim="none"),
                label="direct_upgrade_impact_recorded",
            )
            return
        if action == "record_impact_mapping_complete":
            yield FunctionResult(
                GateOutput("impact_mapping_complete"),
                replace(state, impact_mapping_complete=True, claim="none"),
                label="impact_mapping_complete",
            )
            return
        if action == "record_unknown_impact":
            yield FunctionResult(
                GateOutput("unknown_impact_blocked"),
                replace(
                    state,
                    impact_mapping_complete=False,
                    classification="unknown",
                    claim="rejected",
                ),
                label="unknown_impact_blocked",
            )
            return
        if action == "classify_affected":
            yield FunctionResult(
                GateOutput("classified_affected"),
                replace(state, classification="affected", claim="none"),
                label="classified_affected",
            )
            return
        if action == "classify_not_impacted_with_same_output":
            yield FunctionResult(
                GateOutput("classified_not_impacted_with_same_output"),
                replace(state, classification="not_impacted", same_output_proof=True, claim="none"),
                label="classified_not_impacted_with_same_output",
            )
            return
        if action == "classify_not_impacted_without_proof":
            if state.direct_upgrade_impact:
                yield FunctionResult(
                    GateOutput("classification_rejected_without_same_output"),
                    replace(state, claim="rejected"),
                    label="classification_rejected_without_same_output",
                )
                return
            yield FunctionResult(
                GateOutput("classified_not_impacted"),
                replace(state, classification="not_impacted", claim="none"),
                label="classified_not_impacted",
            )
            return
        if action == "verify_exact_current_receipt":
            if state.impact_mapping_complete and state.classification == "not_impacted" and (
                not state.direct_upgrade_impact or state.same_output_proof
            ):
                yield FunctionResult(
                    GateOutput("exact_current_receipt_verified"),
                    replace(state, exact_current_receipt=True, claim="none"),
                    label="exact_current_receipt_verified",
                )
                return
            yield FunctionResult(
                GateOutput("receipt_reuse_rejected"),
                replace(state, claim="rejected"),
                label="receipt_reuse_rejected",
            )
            return
        if action == "update_model_and_tests":
            if state.classification == "affected":
                yield FunctionResult(
                    GateOutput("model_and_tests_update_reviewed"),
                    replace(
                        state,
                        model_update_reviewed=True,
                        model_updated=True,
                        test_update_reviewed=True,
                        tests_updated=True,
                        claim="none",
                    ),
                    label="model_and_tests_update_reviewed",
                )
                return
            yield FunctionResult(
                GateOutput("update_review_rejected"),
                replace(state, claim="rejected"),
                label="update_review_rejected",
            )
            return
        if action == "rerun_model":
            if state.classification == "affected" and state.model_update_reviewed and state.test_update_reviewed:
                yield FunctionResult(
                    GateOutput("rerun_passed"),
                    replace(
                        state,
                        rerun_current=True,
                        observation_scope=input_obj.observation_scope,
                        complete_observation_count=(
                            input_obj.complete_observation_count
                        ),
                        semantic_verification_count=(
                            input_obj.semantic_verification_count
                        ),
                        final_identity_freshness_passed=(
                            input_obj.final_identity_freshness_passed
                        ),
                        claim="none",
                    ),
                    label="rerun_passed",
                )
                return
            yield FunctionResult(
                GateOutput("rerun_rejected"),
                replace(state, claim="rejected"),
                label="rerun_rejected",
            )
            return
        if action == "claim_upgrade_gate":
            accepted = _ready_to_accept(state)
            claim = "accepted" if accepted else "rejected"
            yield FunctionResult(
                GateOutput(f"claim_{claim}"),
                replace(state, claim=claim),
                label=f"claim_{claim}",
            )


class BrokenReusesOldEvidence(CorrectModelImpactFreshnessGate):
    name = "BrokenReusesOldEvidence"
    idempotency = "Broken variant accepts prior green evidence without classification."

    def apply(self, input_obj: UpgradeAction, state: GateState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_upgrade_gate":
            accepted = state.old_evidence_passed
            claim = "accepted" if accepted else "rejected"
            yield FunctionResult(
                GateOutput(f"claim_{claim}"),
                replace(state, claim=claim),
                label=f"claim_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenAffectedWithoutRerun(CorrectModelImpactFreshnessGate):
    name = "BrokenAffectedWithoutRerun"
    idempotency = "Broken variant accepts affected models on old evidence."

    def apply(self, input_obj: UpgradeAction, state: GateState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_upgrade_gate" and state.classification == "affected":
            yield FunctionResult(
                GateOutput("claim_accepted"),
                replace(state, claim="accepted"),
                label="claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenUnknownImpactRunsAll(CorrectModelImpactFreshnessGate):
    name = "BrokenUnknownImpactRunsAll"
    idempotency = "Broken variant treats unknown impact as authority to run all and accept."

    def apply(self, input_obj: UpgradeAction, state: GateState) -> Iterable[FunctionResult]:
        if (
            input_obj.action_type == "claim_upgrade_gate"
            and not state.impact_mapping_complete
        ):
            yield FunctionResult(
                GateOutput("claim_accepted"),
                replace(state, claim="accepted"),
                label="claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, GateOutput) and current_output.status.startswith("claim_")


def accepted_claim_requires_classification_and_current_evidence(state: GateState, trace) -> InvariantResult:
    last_label = trace.steps[-1].label if trace.steps else ""
    if last_label != "claim_accepted":
        return InvariantResult.pass_()
    if not state.impact_mapping_complete:
        return InvariantResult.fail(
            "upgrade gate accepted with unknown or ambiguous impact mapping"
        )
    if state.classification == "unknown":
        return InvariantResult.fail("upgrade gate accepted without model impact classification")
    if state.classification == "affected" and not (
        state.model_update_reviewed
        and state.test_update_reviewed
        and state.rerun_current
        and state.observation_scope == "invocation_local"
        and state.complete_observation_count == 2
        and state.semantic_verification_count == 1
        and state.final_identity_freshness_passed
    ):
        return InvariantResult.fail(
            "affected model accepted without one invocation-local semantic observation "
            "and one final identity freshness check"
        )
    if state.classification == "not_impacted" and not state.exact_current_receipt:
        return InvariantResult.fail(
            "not-impacted model accepted without an exact-current receipt"
        )
    if state.direct_upgrade_impact and state.classification == "not_impacted" and not state.same_output_proof:
        return InvariantResult.fail("directly touched model reused without same-output proof")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_claim_requires_classification_and_current_evidence",
        "Upgrade gate acceptance requires classification plus reuse proof or affected-model rerun evidence.",
        accepted_claim_requires_classification_and_current_evidence,
    ),
)

EXTERNAL_INPUTS = (
    UpgradeAction("record_direct_upgrade_impact"),
    UpgradeAction("record_impact_mapping_complete"),
    UpgradeAction("classify_affected"),
    UpgradeAction("classify_not_impacted_with_same_output"),
    UpgradeAction("classify_not_impacted_without_proof"),
    UpgradeAction("verify_exact_current_receipt"),
    UpgradeAction("update_model_and_tests"),
    UpgradeAction("rerun_model"),
    UpgradeAction("claim_upgrade_gate"),
)
CORRECT_INPUTS = EXTERNAL_INPUTS

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> GateState:
    return GateState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectModelImpactFreshnessGate(),), name="model_impact_freshness_correct")


def build_broken_reuse_workflow() -> Workflow:
    return Workflow((BrokenReusesOldEvidence(),), name="model_impact_freshness_broken_reuse")


def build_broken_affected_workflow() -> Workflow:
    return Workflow((BrokenAffectedWithoutRerun(),), name="model_impact_freshness_broken_affected")


def build_broken_unknown_impact_workflow() -> Workflow:
    return Workflow(
        (BrokenUnknownImpactRunsAll(),),
        name="model_impact_freshness_broken_unknown_impact",
    )


__all__ = [
    "CORRECT_INPUTS",
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "GateOutput",
    "GateState",
    "UpgradeAction",
    "build_broken_affected_workflow",
    "build_broken_unknown_impact_workflow",
    "build_broken_reuse_workflow",
    "build_correct_workflow",
    "initial_state",
    "terminal_predicate",
]
