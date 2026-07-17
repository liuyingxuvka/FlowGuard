"""FlowGuard rollout model for architecture reduction governance.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the model-to-code architecture reduction route before
implementation. It guards against treating model simplification as enough,
recommending code contraction without an observable contract, bypassing
StructureMesh for public entrypoints, hiding risky candidates, and letting the
new route rewrite production code directly.

Run:
python .flowguard/architecture_reduction/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class ArchitectureReductionCase:
    name: str
    existing_model_grounded: bool = True
    observable_contract_declared: bool = True
    code_mapping_present: bool = True
    candidates_classified: bool = True
    proof_status_visible: bool = True
    risky_candidates_kept_visible: bool = True
    public_entrypoint_structuremesh_gate: bool = True
    target_structure_handoff: bool = True
    completed_candidates_not_requeued: bool = True
    companion_route_triggers: bool = True
    no_direct_code_rewrite: bool = True
    validation_gates_visible: bool = True
    expected_candidate_inventory_declared: bool = True
    expected_candidates_materialized: bool = True
    similarity_provenance_materialized: bool = True
    facade_delegation_current: bool = True
    facade_has_no_independent_success: bool = True


@dataclass(frozen=True)
class ArchitectureReductionPolicy:
    case_name: str = ""
    existing_model_grounded: bool = False
    observable_contract_declared: bool = False
    code_mapping_present: bool = False
    candidates_classified: bool = False
    proof_status_visible: bool = False
    risky_candidates_kept_visible: bool = False
    public_entrypoint_structuremesh_gate: bool = False
    target_structure_handoff: bool = False
    completed_candidates_not_requeued: bool = False
    companion_route_triggers: bool = False
    no_direct_code_rewrite: bool = False
    validation_gates_visible: bool = False
    expected_candidate_inventory_declared: bool = False
    expected_candidates_materialized: bool = False
    similarity_provenance_materialized: bool = False
    facade_delegation_current: bool = False
    facade_has_no_independent_success: bool = False


GOOD_PLAN = ArchitectureReductionCase("good_architecture_reduction_plan")
BROKEN_NO_MODEL_GROUNDING = ArchitectureReductionCase("broken_no_model_grounding", existing_model_grounded=False)
BROKEN_NO_OBSERVABLE_CONTRACT = ArchitectureReductionCase(
    "broken_no_observable_contract",
    observable_contract_declared=False,
)
BROKEN_NO_CODE_MAPPING = ArchitectureReductionCase("broken_no_code_mapping", code_mapping_present=False)
BROKEN_UNCLASSIFIED_CANDIDATES = ArchitectureReductionCase("broken_unclassified_candidates", candidates_classified=False)
BROKEN_HIDDEN_PROOF_STATUS = ArchitectureReductionCase("broken_hidden_proof_status", proof_status_visible=False)
BROKEN_RISKY_CANDIDATES_HIDDEN = ArchitectureReductionCase(
    "broken_risky_candidates_hidden",
    risky_candidates_kept_visible=False,
)
BROKEN_PUBLIC_ENTRYPOINT_BYPASS = ArchitectureReductionCase(
    "broken_public_entrypoint_bypass",
    public_entrypoint_structuremesh_gate=False,
)
BROKEN_NO_TARGET_HANDOFF = ArchitectureReductionCase("broken_no_target_handoff", target_structure_handoff=False)
BROKEN_COMPLETED_CANDIDATE_REQUEUED = ArchitectureReductionCase(
    "broken_completed_candidate_requeued",
    completed_candidates_not_requeued=False,
)
BROKEN_NO_COMPANION_TRIGGERS = ArchitectureReductionCase(
    "broken_no_companion_triggers",
    companion_route_triggers=False,
)
BROKEN_DIRECT_REWRITE = ArchitectureReductionCase("broken_direct_rewrite", no_direct_code_rewrite=False)
BROKEN_NO_VALIDATION_GATES = ArchitectureReductionCase("broken_no_validation_gates", validation_gates_visible=False)
BROKEN_NO_EXPECTED_CANDIDATE_INVENTORY = ArchitectureReductionCase(
    "broken_no_expected_candidate_inventory",
    expected_candidate_inventory_declared=False,
)
BROKEN_OMITTED_EXPECTED_CANDIDATE = ArchitectureReductionCase(
    "broken_omitted_expected_candidate",
    expected_candidates_materialized=False,
)
BROKEN_OPAQUE_SIMILARITY_PROVENANCE = ArchitectureReductionCase(
    "broken_opaque_similarity_provenance",
    similarity_provenance_materialized=False,
)
BROKEN_STALE_FACADE_DELEGATION = ArchitectureReductionCase(
    "broken_stale_facade_delegation",
    facade_delegation_current=False,
)
BROKEN_FACADE_PARALLEL_SUCCESS = ArchitectureReductionCase(
    "broken_facade_parallel_success",
    facade_has_no_independent_success=False,
)


class EvaluateArchitectureReductionPlan:
    name = "EvaluateArchitectureReductionPlan"
    reads = ("ArchitectureReductionPolicy",)
    writes = (
        "case_name",
        "existing_model_grounded",
        "observable_contract_declared",
        "code_mapping_present",
        "candidates_classified",
        "proof_status_visible",
        "risky_candidates_kept_visible",
        "public_entrypoint_structuremesh_gate",
        "target_structure_handoff",
        "completed_candidates_not_requeued",
        "companion_route_triggers",
        "no_direct_code_rewrite",
        "validation_gates_visible",
        "expected_candidate_inventory_declared",
        "expected_candidates_materialized",
        "similarity_provenance_materialized",
        "facade_delegation_current",
        "facade_has_no_independent_success",
    )
    accepted_input_type = ArchitectureReductionCase
    input_description = "architecture reduction route case"
    output_description = "architecture reduction governance policy"
    idempotency = "same case produces one policy state"

    def apply(self, input_obj: ArchitectureReductionCase, _state: ArchitectureReductionPolicy):
        new_state = ArchitectureReductionPolicy(
            case_name=input_obj.name,
            existing_model_grounded=input_obj.existing_model_grounded,
            observable_contract_declared=input_obj.observable_contract_declared,
            code_mapping_present=input_obj.code_mapping_present,
            candidates_classified=input_obj.candidates_classified,
            proof_status_visible=input_obj.proof_status_visible,
            risky_candidates_kept_visible=input_obj.risky_candidates_kept_visible,
            public_entrypoint_structuremesh_gate=input_obj.public_entrypoint_structuremesh_gate,
            target_structure_handoff=input_obj.target_structure_handoff,
            completed_candidates_not_requeued=input_obj.completed_candidates_not_requeued,
            companion_route_triggers=input_obj.companion_route_triggers,
            no_direct_code_rewrite=input_obj.no_direct_code_rewrite,
            validation_gates_visible=input_obj.validation_gates_visible,
            expected_candidate_inventory_declared=input_obj.expected_candidate_inventory_declared,
            expected_candidates_materialized=input_obj.expected_candidates_materialized,
            similarity_provenance_materialized=input_obj.similarity_provenance_materialized,
            facade_delegation_current=input_obj.facade_delegation_current,
            facade_has_no_independent_success=input_obj.facade_has_no_independent_success,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="projected architecture reduction route decision into policy state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: ArchitectureReductionPolicy) -> bool:
    return not state.case_name


def existing_model_is_grounded(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.existing_model_grounded:
        return _fail("existing_model_is_grounded", "architecture reduction must reuse or inspect existing model ownership first")
    return _pass()


def observable_contract_exists(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.observable_contract_declared:
        return _fail("observable_contract_exists", "code contraction needs an explicit observable behavior boundary")
    return _pass()


def code_mapping_exists(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.code_mapping_present:
        return _fail("code_mapping_exists", "model reduction must map to code nodes before recommending contraction")
    return _pass()


def candidates_and_proofs_are_visible(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.candidates_classified:
        return _fail("candidates_and_proofs_are_visible", "reduction candidates are not classified")
    if not state.proof_status_visible:
        return _fail("candidates_and_proofs_are_visible", "candidate proof status is hidden")
    return _pass()


def risky_candidates_are_not_deleted_silently(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.risky_candidates_kept_visible:
        return _fail("risky_candidates_are_not_deleted_silently", "risky duplicate-looking branches must stay visible")
    return _pass()


def public_entrypoints_use_structuremesh_gate(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.public_entrypoint_structuremesh_gate:
        return _fail(
            "public_entrypoints_use_structuremesh_gate",
            "public entrypoint contractions must go through StructureMesh or equivalent parity gate",
        )
    return _pass()


def target_structure_handoff_exists(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.target_structure_handoff:
        return _fail("target_structure_handoff_exists", "reduced model must hand off target structure recommendations")
    return _pass()


def completed_candidates_leave_active_queue(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.completed_candidates_not_requeued:
        return _fail(
            "completed_candidates_leave_active_queue",
            "completed or historical candidates need evidence but must not stay in ready work",
        )
    return _pass()


def companion_route_triggers_exist(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.companion_route_triggers:
        return _fail("companion_route_triggers_exist", "related skills need complexity-growth triggers")
    return _pass()


def architecture_reduction_does_not_rewrite_code(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.no_direct_code_rewrite:
        return _fail("architecture_reduction_does_not_rewrite_code", "architecture reduction must not rewrite production code directly")
    return _pass()


def validation_gates_remain_visible(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.validation_gates_visible:
        return _fail("validation_gates_remain_visible", "tests, conformance, and StructureMesh gates must remain visible")
    return _pass()


def expected_candidate_inventory_is_complete(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.expected_candidate_inventory_declared:
        return _fail(
            "expected_candidate_inventory_is_complete",
            "candidate completeness requires an independently declared expected inventory",
        )
    if not state.expected_candidates_materialized:
        return _fail(
            "expected_candidate_inventory_is_complete",
            "an expected reduction candidate is omitted without a scoped disposition",
        )
    return _pass()


def similarity_provenance_is_materialized(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.similarity_provenance_materialized:
        return _fail(
            "similarity_provenance_is_materialized",
            "similarity relation and code-obligation ids must bind concrete candidates and target actions",
        )
    return _pass()


def retained_facades_delegate_only(state: ArchitectureReductionPolicy, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.facade_delegation_current:
        return _fail(
            "retained_facades_delegate_only",
            "retained facade lacks current proof of delegation to the selected primary path",
        )
    if not state.facade_has_no_independent_success:
        return _fail(
            "retained_facades_delegate_only",
            "retained facade still owns an independent success or primary side effect",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "existing_model_is_grounded",
        "Architecture reduction starts from existing model ownership.",
        existing_model_is_grounded,
    ),
    Invariant(
        "observable_contract_exists",
        "Architecture reduction declares what public behavior must stay unchanged.",
        observable_contract_exists,
    ),
    Invariant(
        "code_mapping_exists",
        "Model reduction is mapped back to code nodes before code contraction is suggested.",
        code_mapping_exists,
    ),
    Invariant(
        "candidates_and_proofs_are_visible",
        "Reduction candidates and proof status stay explicit.",
        candidates_and_proofs_are_visible,
    ),
    Invariant(
        "risky_candidates_are_not_deleted_silently",
        "Risky candidates remain visible instead of being treated as safe deletes.",
        risky_candidates_are_not_deleted_silently,
    ),
    Invariant(
        "public_entrypoints_use_structuremesh_gate",
        "Public entrypoint changes require StructureMesh or equivalent parity evidence.",
        public_entrypoints_use_structuremesh_gate,
    ),
    Invariant(
        "target_structure_handoff_exists",
        "Reduced model evidence feeds target code structure planning.",
        target_structure_handoff_exists,
    ),
    Invariant(
        "completed_candidates_leave_active_queue",
        "Completed candidates stay visible without being re-queued as ready work.",
        completed_candidates_leave_active_queue,
    ),
    Invariant(
        "companion_route_triggers_exist",
        "Related FlowGuard skills know when to invoke architecture reduction.",
        companion_route_triggers_exist,
    ),
    Invariant(
        "architecture_reduction_does_not_rewrite_code",
        "Architecture reduction reviews and hands off instead of rewriting code directly.",
        architecture_reduction_does_not_rewrite_code,
    ),
    Invariant(
        "validation_gates_remain_visible",
        "Refactor validation gates remain visible before completion claims.",
        validation_gates_remain_visible,
    ),
    Invariant(
        "expected_candidate_inventory_is_complete",
        "Expected candidate inventory is independent, current, and fully dispositioned.",
        expected_candidate_inventory_is_complete,
    ),
    Invariant(
        "similarity_provenance_is_materialized",
        "Similarity handoffs bind concrete reduction candidates and target actions.",
        similarity_provenance_is_materialized,
    ),
    Invariant(
        "retained_facades_delegate_only",
        "Retained facades have current delegation proof and no independent authority.",
        retained_facades_delegate_only,
    ),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateArchitectureReductionPlan(),), name="architecture_reduction_rollout")


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def scenario(
    name: str,
    description: str,
    case: ArchitectureReductionCase,
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=ArchitectureReductionPolicy(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario(
        "good_plan_passes",
        "A complete architecture reduction route plan passes.",
        GOOD_PLAN,
        _expect_ok("complete architecture reduction plan passes", labels=("good_architecture_reduction_plan",)),
    ),
    scenario(
        "missing_model_grounding_fails",
        "Reduction must inspect existing model ownership first.",
        BROKEN_NO_MODEL_GROUNDING,
        _expect_violation("missing existing model grounding fails", ("existing_model_is_grounded",)),
    ),
    scenario(
        "missing_observable_contract_fails",
        "Code contraction needs an observable contract.",
        BROKEN_NO_OBSERVABLE_CONTRACT,
        _expect_violation("missing observable contract fails", ("observable_contract_exists",)),
    ),
    scenario(
        "missing_code_mapping_fails",
        "Model reductions must map back to code nodes.",
        BROKEN_NO_CODE_MAPPING,
        _expect_violation("missing code mapping fails", ("code_mapping_exists",)),
    ),
    scenario(
        "unclassified_candidates_fail",
        "Candidates must be classified.",
        BROKEN_UNCLASSIFIED_CANDIDATES,
        _expect_violation("unclassified candidates fail", ("candidates_and_proofs_are_visible",)),
    ),
    scenario(
        "hidden_proof_status_fails",
        "Proof status must stay visible.",
        BROKEN_HIDDEN_PROOF_STATUS,
        _expect_violation("hidden proof status fails", ("candidates_and_proofs_are_visible",)),
    ),
    scenario(
        "risky_candidates_hidden_fail",
        "Risky candidates must not be silently deleted.",
        BROKEN_RISKY_CANDIDATES_HIDDEN,
        _expect_violation("hidden risky candidates fail", ("risky_candidates_are_not_deleted_silently",)),
    ),
    scenario(
        "public_entrypoint_bypass_fails",
        "Public entrypoints need StructureMesh parity gates.",
        BROKEN_PUBLIC_ENTRYPOINT_BYPASS,
        _expect_violation("public entrypoint bypass fails", ("public_entrypoints_use_structuremesh_gate",)),
    ),
    scenario(
        "missing_target_handoff_fails",
        "Reduced model evidence must hand off target structure.",
        BROKEN_NO_TARGET_HANDOFF,
        _expect_violation("missing target structure handoff fails", ("target_structure_handoff_exists",)),
    ),
    scenario(
        "completed_candidate_requeued_fails",
        "Completed candidates must not remain ready work.",
        BROKEN_COMPLETED_CANDIDATE_REQUEUED,
        _expect_violation("completed candidate requeue fails", ("completed_candidates_leave_active_queue",)),
    ),
    scenario(
        "missing_companion_triggers_fails",
        "Related skills need architecture reduction triggers.",
        BROKEN_NO_COMPANION_TRIGGERS,
        _expect_violation("missing companion triggers fails", ("companion_route_triggers_exist",)),
    ),
    scenario(
        "direct_rewrite_fails",
        "Architecture reduction must not directly rewrite production code.",
        BROKEN_DIRECT_REWRITE,
        _expect_violation("direct rewrite fails", ("architecture_reduction_does_not_rewrite_code",)),
    ),
    scenario(
        "missing_validation_gates_fails",
        "Validation and parity gates must remain visible.",
        BROKEN_NO_VALIDATION_GATES,
        _expect_violation("missing validation gates fails", ("validation_gates_remain_visible",)),
    ),
    scenario(
        "missing_expected_candidate_inventory_fails",
        "Candidate completeness needs an independent expected inventory.",
        BROKEN_NO_EXPECTED_CANDIDATE_INVENTORY,
        _expect_violation("missing candidate inventory fails", ("expected_candidate_inventory_is_complete",)),
    ),
    scenario(
        "omitted_expected_candidate_fails",
        "Expected candidates must materialize or receive scoped disposition.",
        BROKEN_OMITTED_EXPECTED_CANDIDATE,
        _expect_violation("omitted expected candidate fails", ("expected_candidate_inventory_is_complete",)),
    ),
    scenario(
        "opaque_similarity_provenance_fails",
        "Similarity ids must bind concrete candidates and actions.",
        BROKEN_OPAQUE_SIMILARITY_PROVENANCE,
        _expect_violation("opaque similarity provenance fails", ("similarity_provenance_is_materialized",)),
    ),
    scenario(
        "stale_facade_delegation_fails",
        "Facade delegation evidence must be current.",
        BROKEN_STALE_FACADE_DELEGATION,
        _expect_violation("stale facade delegation fails", ("retained_facades_delegate_only",)),
    ),
    scenario(
        "facade_parallel_success_fails",
        "Facade cannot own an independent business success.",
        BROKEN_FACADE_PARALLEL_SUCCESS,
        _expect_violation("facade parallel success fails", ("retained_facades_delegate_only",)),
    ),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)


from flowguard.skill_contract_model import (  # noqa: E402
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing architecture-reduction owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-architecture-reduction",
        route_id="architecture_reduction",
        owner_id="architecture_reduction",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Reduce mapped architecture without changing observable behavior or creating a second authority.",
        claim_boundary="Projection only; native reduction scenarios, proof status, and downstream parity evidence remain authoritative.",
    )
