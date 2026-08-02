"""FlowGuard self-model for open-ended model-angle deliberation.

Purpose: Keep the new route from collapsing into a fixed checklist, and prove
that a caller-declared ``resolved`` boolean cannot authorize broad confidence
without current evidence from the selected owner route.
"""

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    MODEL_ANGLE_ACTION_REUSE_EXISTING,
    ModelAngleDeliberation,
    ProofArtifactRef,
    Workflow,
)


SELF_MODEL_FINGERPRINT = "sha256:" + "1" * 64


def _owner_proof(angle_id: str, owner_route: str) -> ProofArtifactRef:
    return ProofArtifactRef(
        artifact_id=f"proof:{angle_id}",
        producer_route=owner_route,
        command="python .flowguard/model_angle_deliberation/run_checks.py",
        result_path=f".flowguard/evidence/model-angle/{angle_id.replace(':', '-')}.json",
        result_status="passed",
        exit_code=0,
        started_at="2026-08-02T00:00:00+00:00",
        finished_at="2026-08-02T00:00:01+00:00",
        subject_id=angle_id,
        subject_fingerprint=SELF_MODEL_FINGERPRINT,
        artifact_fingerprints={"self_model": SELF_MODEL_FINGERPRINT},
        covered_obligation_ids=(angle_id,),
        current=True,
    )


@dataclass(frozen=True)
class AngleProofAction:
    action_type: str
    angle_id: str = "angle:required"
    owner_route: str = "model_maturation_loop"
    proof_owner_route: str = ""
    proof_current: bool = False
    proof_passed: bool = False
    proof_covers_angle: bool = False
    subject_fingerprint_matches: bool = False
    caller_says_resolved: bool = False


@dataclass(frozen=True)
class AngleProofOutput:
    status: str


@dataclass(frozen=True)
class AngleProofState:
    owner_evidence_valid: bool = False
    bare_resolution_accepted: bool = False
    broad_claim: str = "none"


class CorrectAngleProofGate:
    name = "CorrectAngleProofGate"
    reads = ("owner_evidence_valid", "bare_resolution_accepted", "broad_claim")
    writes = reads
    accepted_input_type = AngleProofAction
    input_description = "model-angle owner-evidence action"
    output_description = "owner-evidence validation or broad-claim decision"
    idempotency = "Only exact current owner proof may resolve a required model angle."

    def apply(
        self, input_obj: AngleProofAction, state: AngleProofState
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type == "validate_owner_evidence":
            valid = (
                bool(input_obj.angle_id)
                and input_obj.proof_owner_route == input_obj.owner_route
                and input_obj.proof_current
                and input_obj.proof_passed
                and input_obj.proof_covers_angle
                and input_obj.subject_fingerprint_matches
            )
            yield FunctionResult(
                AngleProofOutput("owner_evidence_valid" if valid else "owner_evidence_rejected"),
                replace(state, owner_evidence_valid=valid),
                label="owner_evidence_valid" if valid else "owner_evidence_rejected",
            )
            return
        if input_obj.action_type == "claim_broad_confidence":
            claim = "accepted" if state.owner_evidence_valid else "rejected"
            yield FunctionResult(
                AngleProofOutput(f"broad_claim_{claim}"),
                replace(state, broad_claim=claim),
                label=f"broad_claim_{claim}",
            )


class BrokenBooleanResolutionGate(CorrectAngleProofGate):
    name = "BrokenBooleanResolutionGate"
    idempotency = "Broken variant treats the caller's resolved boolean as owner proof."

    def apply(
        self, input_obj: AngleProofAction, state: AngleProofState
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type == "validate_owner_evidence" and input_obj.caller_says_resolved:
            yield FunctionResult(
                AngleProofOutput("bare_resolution_accepted"),
                replace(state, bare_resolution_accepted=True),
                label="bare_resolution_accepted",
            )
            return
        if input_obj.action_type == "claim_broad_confidence" and state.bare_resolution_accepted:
            yield FunctionResult(
                AngleProofOutput("broad_claim_accepted"),
                replace(state, broad_claim="accepted"),
                label="broad_claim_accepted",
            )
            return
        yield from super().apply(input_obj, state)


def no_broad_claim_from_bare_resolution(
    state: AngleProofState, _trace
) -> InvariantResult:
    if state.broad_claim == "accepted" and not state.owner_evidence_valid:
        return InvariantResult.fail(
            "broad confidence accepted from a caller-declared resolved boolean without exact owner proof"
        )
    return InvariantResult.pass_()


ANGLE_PROOF_INVARIANTS = (
    Invariant(
        "no_broad_claim_from_bare_resolution",
        "A required model angle needs current passing proof from its exact owner route and subject.",
        no_broad_claim_from_bare_resolution,
    ),
)

GOOD_ANGLE_PROOF_SEQUENCE = (
    AngleProofAction(
        "validate_owner_evidence",
        proof_owner_route="model_maturation_loop",
        proof_current=True,
        proof_passed=True,
        proof_covers_angle=True,
        subject_fingerprint_matches=True,
    ),
    AngleProofAction("claim_broad_confidence"),
)

BROKEN_BARE_RESOLUTION_SEQUENCE = (
    AngleProofAction("validate_owner_evidence", caller_says_resolved=True),
    AngleProofAction("claim_broad_confidence"),
)


def angle_proof_initial_state() -> AngleProofState:
    return AngleProofState()


def build_angle_proof_workflow(*, broken: bool = False) -> Workflow:
    gate = BrokenBooleanResolutionGate() if broken else CorrectAngleProofGate()
    return Workflow((gate,), name="model_angle_owner_proof")


def correct_model_angle_deliberations():
    return (
        ModelAngleDeliberation(
            "self:existing-preflight",
            "Existing preflight is necessary but not enough",
            trigger_observation="The user noticed AI stays inside narrow route or field-flow prompts.",
            current_model_sees="Existing Model Preflight finds current model owners and duplicate boundaries.",
            current_model_misses="It does not force open-ended missing-viewpoint reasoning before route trust.",
            failure_if_ignored="The agent can claim grounded reuse while a needed model angle is absent.",
            candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            existing_model_ids=("existing_model_preflight",),
            proposed_model_boundary="Model-angle rows consumed by preflight, ledger, closure, and scan routes.",
            owner_route_hint="model_maturation_loop",
            evidence_needed=("tests:test_model_angle_deliberation", "tests:test_existing_model_preflight"),
            resolved=True,
            owner_evidence=_owner_proof(
                "self:existing-preflight", "model_maturation_loop"
            ),
            subject_fingerprints={"self_model": SELF_MODEL_FINGERPRINT},
        ),
        ModelAngleDeliberation(
            "self:model-mesh-handoff",
            "Candidate child model pressure",
            trigger_observation="Some missing viewpoints should become child models instead of more prompt text.",
            current_model_sees="ModelMesh owns parent/child split and reattachment evidence.",
            current_model_misses="A prompt-only fix can keep adding vague checklist bullets to the parent route.",
            failure_if_ignored="Large models keep growing without a clear child ownership boundary.",
            candidate_action=MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
            existing_model_ids=("model_mesh_maintenance",),
            proposed_model_boundary="Model-angle deliberation names split pressure before ModelMesh does the split.",
            owner_route_hint="model_mesh_maintenance",
            evidence_needed=("maintenance_scan:model_angle_gap",),
            resolved=True,
            owner_evidence=_owner_proof(
                "self:model-mesh-handoff", "model_mesh_maintenance"
            ),
            subject_fingerprints={"self_model": SELF_MODEL_FINGERPRINT},
        ),
        ModelAngleDeliberation(
            "self:no-overfix",
            "Known route remains enough when no angle is missing",
            trigger_observation="The user rejected over-repair and narrow checklist expansion.",
            current_model_sees="Some tasks only need the selected direct route.",
            current_model_misses="Nothing material after open-ended deliberation.",
            failure_if_ignored="The system would create ceremony without improving confidence.",
            candidate_action=MODEL_ANGLE_ACTION_REUSE_EXISTING,
            existing_model_ids=("development_process_flow",),
            resolved=True,
        ),
    )


def unresolved_model_angle_deliberations():
    return (
        ModelAngleDeliberation(
            "self:open-angle",
            "Unresolved missing viewpoint",
            trigger_observation="A possible missing model angle was noticed.",
            current_model_sees="The current model sees only route ownership.",
            current_model_misses="The new angle may require field lifecycle or mesh split evidence.",
            failure_if_ignored="Broad confidence would hide an unowned model boundary.",
            candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            existing_model_ids=("existing_model_preflight",),
            proposed_model_boundary="Name and resolve the missing viewpoint through its owner route.",
            resolved=False,
        ),
    )


__all__ = [
    "ANGLE_PROOF_INVARIANTS",
    "BROKEN_BARE_RESOLUTION_SEQUENCE",
    "GOOD_ANGLE_PROOF_SEQUENCE",
    "AngleProofAction",
    "AngleProofState",
    "angle_proof_initial_state",
    "build_angle_proof_workflow",
    "correct_model_angle_deliberations",
    "unresolved_model_angle_deliberations",
]
