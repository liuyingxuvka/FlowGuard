"""Change-specific ArchitectureReduction evidence for optimizer contraction."""

from __future__ import annotations

from flowguard import (
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_DISPOSITION_COMPLETED,
    CANDIDATE_MANUAL_REVIEW,
    COMPATIBILITY_ACTION_REJECT,
    COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
    PROOF_NEEDS_CONFORMANCE_REPLAY,
    PROOF_SAFE_BY_EQUIVALENCE,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionTrigger,
    CompatibilitySurfaceClassification,
    ObservableArchitectureContract,
    review_architecture_reduction,
)


RETIRED_PUBLIC_NAMES = (
    "DevelopmentProcessStrategyPlan",
    "ProcessCostVector",
    "DiagnosticCampaign",
    "FailureObservation",
    "FailureCluster",
    "RootCauseHypothesis",
    "RepairBatch",
    "StrategyReevaluation",
    "ProcessDependencyGraph",
    "ProcessStrategyReport",
    "review_development_process_strategy",
)


def development_process_strategy_reduction_plan() -> ArchitectureReductionPlan:
    internal = ArchitectureReductionCandidate(
        "candidate:process-optimization:collapse-internal-graph",
        candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
        code_node_id="flowguard.development_process_strategy.internal_record_graph",
        source_model_element="conditional_optimization_preserves_hard_contracts",
        target_action=TARGET_ACTION_COLLAPSE,
        proof_status=PROOF_SAFE_BY_EQUIVALENCE,
        required_next_route=ROUTE_CODE_STRUCTURE_RECOMMENDATION,
        rationale="Thirteen mixed records and six pseudo-strategies collapse into five owner records and one review while retaining the declared inactive, equivalence, safety, repair, freshness, and claim behavior.",
        affected_state=(
            "process_optimization_decision",
            "repair_group_references",
        ),
        evidence_refs=(
            ".flowguard/development_process_strategy/model.py",
            ".flowguard/development_process_strategy/field_lifecycle.py",
            "tests/test_development_process_strategy.py",
            "tests/test_development_process_strategy_benchmark.py",
        ),
        lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED,
        completion_evidence_refs=(
            "flowguard/development_process_strategy.py",
            "tests/test_development_process_strategy.py",
        ),
        business_intent_id="intent:development-process-strategy-selection",
        behavior_commitment_id="commitment:development-process-strategy-selection",
        primary_path_id="path:development-process-flow:strategy-selection",
        inventory_revision="process-optimization-reduction:v1",
    )
    public = ArchitectureReductionCandidate(
        "candidate:process-optimization:retire-public-vocabulary",
        candidate_type=CANDIDATE_MANUAL_REVIEW,
        code_node_id="flowguard.public.retired_process_strategy_api",
        source_model_element="openspec:simplify-development-process-optimization",
        target_action=TARGET_ACTION_REMOVE,
        proof_status=PROOF_NEEDS_CONFORMANCE_REPLAY,
        required_next_route=ROUTE_STRUCTURE_MESH,
        rationale="This is an OpenSpec-authorized breaking API contraction, not a behavior-equivalent internal merge. Structure/API parity and negative legacy tests prove the sole current surface.",
        affected_public_entrypoints=RETIRED_PUBLIC_NAMES,
        evidence_refs=(
            "openspec/changes/simplify-development-process-optimization/specs/flowguard-api-registry/spec.md",
            "tests/test_api_surface.py",
        ),
        lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED,
        completion_evidence_refs=(
            "tests/test_api_surface.py",
            "tests/test_process_optimization_zero_residuals.py",
        ),
        business_intent_id="intent:development-process-strategy-selection",
        behavior_commitment_id="commitment:development-process-strategy-selection",
        primary_path_id="path:development-process-flow:strategy-selection",
        inventory_revision="process-optimization-reduction:v1",
        metadata={
            "breaking_change_authority": "openspec:simplify-development-process-optimization",
            "equivalence_claim": "not_claimed",
        },
    )
    retired_surface = CompatibilitySurfaceClassification(
        "surface:retired-process-strategy-api",
        classification=COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
        recommended_action=COMPATIBILITY_ACTION_REJECT,
        rationale="Retired public names are accepted only as negative-test subjects and have no runtime authority or compatibility reader.",
        public_entrypoints=RETIRED_PUBLIC_NAMES,
        runtime_authority=False,
        candidate_ids=(public.candidate_id,),
        evidence_refs=("tests/test_api_surface.py",),
    )
    candidate_ids = (internal.candidate_id, public.candidate_id)
    return ArchitectureReductionPlan(
        "development-process-optimization-reduction:v1",
        observable_contract=ObservableArchitectureContract(
            source_model_id=".flowguard/development_process_strategy/model.py",
            source_code_boundary_id="flowguard.development_process_strategy",
            public_entrypoints=(
                "flowguard.FLOWGUARD_ROUTE_API['development_process_flow']",
                "flowguard.review_process_optimization",
            ),
            observable_outputs=(
                "not_needed|selected|blocked",
                "eligible and rejected candidate ids",
                "required affected revalidation ids",
                "bounded claim text",
            ),
            observable_state=(
                "process_optimization_decision",
                "repair_group_references",
            ),
            validation_boundaries=(
                ".flowguard/development_process_strategy/run_checks.py",
                "tests/test_development_process_strategy.py",
                "tests/test_api_surface.py",
                "tests/test_process_optimization_zero_residuals.py",
            ),
            rationale="Preserve the conditional DPF behavior commitment while deleting duplicated machinery and retiring the old public vocabulary under explicit change authority.",
        ),
        candidates=(internal, public),
        companion_route_triggers=(
            ArchitectureReductionTrigger(
                ROUTE_CODE_STRUCTURE_RECOMMENDATION,
                "derive the compact five-record implementation boundary",
                complexity_signal="thirteen mixed records and duplicated owner fields",
                recommended_timing="before runtime contraction",
            ),
            ArchitectureReductionTrigger(
                ROUTE_STRUCTURE_MESH,
                "govern the OpenSpec-authorized breaking public API contraction",
                complexity_signal="retired public entrypoints must have zero current authority",
                recommended_timing="before API parity closure",
            ),
        ),
        compatibility_surfaces=(retired_surface,),
        rationale="Contract the implementation and public surface without adding a route, skill, compatibility reader, or alternate success path.",
        inventory_revision="process-optimization-reduction:v1",
        inventory_source_ref=".flowguard/development_process_strategy/code_structure.json",
        inventory_current=True,
        expected_candidate_ids=candidate_ids,
        require_complete_inventory=True,
    )


def review_development_process_strategy_reduction():
    return review_architecture_reduction(
        development_process_strategy_reduction_plan()
    )


__all__ = [
    "RETIRED_PUBLIC_NAMES",
    "development_process_strategy_reduction_plan",
    "review_development_process_strategy_reduction",
]
