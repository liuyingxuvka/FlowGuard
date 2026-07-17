"""Finite bad cases and ordinary model/code/test closure for process optimization.

DevelopmentProcessFlow remains the sole owner.  Diagnostic counts stay in
TestMesh, findings stay in the Finding Ledger, and repair closure uses the
ordinary Model-Test Alignment obligation/owner/evidence mesh.
"""

from __future__ import annotations

from dataclasses import replace

from flowguard import (
    CODE_CONTRACT_ROLE_OWNER,
    CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_ORACLE_MARK_STALE,
    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
    CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
    CONTRACT_ROUTE_TEST_MESH,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_EVIDENCE_ROLE_PRIMARY,
    TEST_KIND_REPLAY,
    TEST_STATUS_PASSED,
    CodeContract,
    ContractCoverageUniverse,
    ContractExhaustionPlan,
    ContractMutationCase,
    ContractOracle,
    ModelTestAlignmentPlan,
    TestEvidence,
    contract_exhaustion_to_model_obligations,
    review_contract_exhaustion,
    review_model_test_alignment,
)


MODEL_ID = "development_process_strategy"
PLAN_ID = "development-process-optimization:finite-bad-cases:v2"
PRIMARY_PATH_ID = "path:development-process-flow:strategy-selection"
ORACLE_BLOCK_ID = "oracle:development-process-optimization:block"
ORACLE_STALE_ID = "oracle:development-process-optimization:mark-stale"
CODE_CONTRACT_PREFIX = "contract:development-process-optimization"
EVIDENCE_PREFIX = "evidence:development-process-optimization"

_REQUIRED_ROUTES = (
    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
    CONTRACT_ROUTE_TEST_MESH,
    CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
)

_BAD_CASES = (
    (
        "ordinary-work-forced-through-optimizer",
        "inactive_path_has_ceremony",
        ORACLE_BLOCK_ID,
        "Keep ordinary single-route work free of optimizer candidates, cost records, and evidence gates.",
    ),
    (
        "cheaper-non-equivalent-candidate",
        "candidate_not_equivalent",
        ORACLE_BLOCK_ID,
        "Reject a cheaper route until all six hard equivalence dimensions match.",
    ),
    (
        "correlated-findings-without-relation-evidence",
        "repair_group_relation_missing",
        ORACLE_BLOCK_ID,
        "Do not group findings merely because they appeared in one run.",
    ),
    (
        "hard-blocker-hidden-by-continued-execution",
        "hard_blocker_not_visible",
        ORACLE_BLOCK_ID,
        "Stop when a hard blocker makes downstream evidence invalid or unsafe and keep descendants visible as not run.",
    ),
    (
        "budgeted-boundary-without-stop-reason",
        "diagnostic_boundary_unaccounted",
        ORACLE_BLOCK_ID,
        "Require a declared reason for valid work outside a budgeted diagnostic boundary.",
    ),
    (
        "unsafe-parallel-execution",
        "parallel_isolation_missing",
        ORACLE_BLOCK_ID,
        "Reject parallel execution unless dependency, mutable-state, side-effect, and owner isolation are current.",
    ),
    (
        "repair-without-primary-owner",
        "repair_owner_missing",
        ORACLE_BLOCK_ID,
        "Require an ordinary primary CodeContract owner for every repair group.",
    ),
    (
        "stale-process-decision",
        "material_change_without_new_selection",
        ORACLE_STALE_ID,
        "Mark a decision stale when material evidence changes its inputs.",
    ),
    (
        "incomplete-affected-revalidation",
        "repair_revalidation_missing",
        ORACLE_BLOCK_ID,
        "Keep a repair open until every affected obligation has current revalidation evidence.",
    ),
    (
        "qualitative-evidence-overclaimed-as-minimum",
        "comparison_boundary_overclaim",
        ORACLE_BLOCK_ID,
        "Estimated or qualitative comparison may support a preference, never a measured minimum or global optimum.",
    ),
)


def development_process_strategy_contract_plan() -> ContractExhaustionPlan:
    """Declare the finite current bad-case universe for this capability."""

    case_ids = tuple(
        f"case:development-process-optimization:{slug}" for slug, *_ in _BAD_CASES
    )
    cases = tuple(
        ContractMutationCase(
            case_id=case_id,
            mutation_type=mutation_type,
            source_route="development_process_flow",
            source_case_id=slug,
            oracle_id=oracle_id,
            expected_status=(
                CONTRACT_ORACLE_MARK_STALE
                if oracle_id == ORACLE_STALE_ID
                else CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM
            ),
            required_routes=_REQUIRED_ROUTES,
            required_test_cell_id=f"test-cell:{case_id}",
            risk_gate_id=f"risk-gate:{case_id}",
            freshness_scope="current_process_optimization_input_revision",
            description=description,
            model_id=MODEL_ID,
            metadata={
                "behavior_commitment_id": "commitment:development-process-strategy-selection",
                "public_owner_route": "development_process_flow",
            },
        )
        for case_id, (slug, mutation_type, oracle_id, description) in zip(
            case_ids, _BAD_CASES
        )
    )
    return ContractExhaustionPlan(
        PLAN_ID,
        seed_cases=cases,
        oracles=(
            ContractOracle(
                ORACLE_BLOCK_ID,
                CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
                expected_message_fields=("case_id", "reason", "required_next_evidence"),
                forbidden_downstream_steps=(
                    "enforce_unsupported_process_choice",
                    "claim_process_complete",
                ),
                required_repair_fields=("owner", "evidence_scope", "revalidation"),
                description="Block unsafe, unsupported, or needlessly ceremonial process optimization.",
            ),
            ContractOracle(
                ORACLE_STALE_ID,
                CONTRACT_ORACLE_MARK_STALE,
                expected_message_fields=("decision_revision", "material_revision"),
                forbidden_downstream_steps=("reuse_stale_process_decision",),
                required_repair_fields=("process_optimization_evidence_id",),
                description="Invalidate a materially stale decision and require current selection evidence.",
            ),
        ),
        claim_scope="routine",
        source_model_ids=(MODEL_ID,),
        generation_policy="finite_declared_inventory",
        required_route_ids=_REQUIRED_ROUTES,
        require_actionable_oracle_feedback=True,
        inventory_revision="development-process-optimization-bad-cases:v2",
        coverage_universe=ContractCoverageUniverse(
            "universe:development-process-optimization:v2",
            claim_scope="finite_known-bad-boundary",
            source_refs=(
                ".flowguard/development_process_strategy/model.py",
                "flowguard/development_process_strategy.py",
                "tests/test_development_process_strategy.py",
                "tests/test_development_process_strategy_benchmark.py",
            ),
            required_case_ids=case_ids,
            require_full_product=False,
            metadata={
                "boundary": "the ten declared process-optimization failure families; not every future workflow shape",
            },
        ),
        require_coverage_universe=True,
        model_id=MODEL_ID,
        model_level="child",
        metadata={
            "owner_route": "development_process_flow",
            "optimality_claim_boundary": "bounded current evidence only; never a global optimum",
        },
    )


def review_development_process_strategy_contracts():
    return review_contract_exhaustion(development_process_strategy_contract_plan())


def development_process_strategy_alignment_plan() -> ModelTestAlignmentPlan:
    """Use ordinary obligations, primary code owners, and replay evidence."""

    contract_report = review_development_process_strategy_contracts()
    obligations = tuple(
        replace(
            obligation,
            behavior_plane="development_process",
            business_intent_id="intent:development-process-strategy-selection",
            behavior_commitment_id="commitment:development-process-strategy-selection",
            primary_path_id=PRIMARY_PATH_ID,
        )
        for obligation in contract_exhaustion_to_model_obligations(contract_report)
    )
    contracts = tuple(
        CodeContract(
            f"{CODE_CONTRACT_PREFIX}:{index}",
            path="flowguard/development_process_strategy.py",
            symbol="review_process_optimization",
            role=CODE_CONTRACT_ROLE_OWNER,
            implements_obligations=(obligation.obligation_id,),
            external_inputs=obligation.external_inputs,
            external_outputs=obligation.external_outputs,
            state_reads=obligation.state_reads,
            state_writes=obligation.state_writes,
            side_effects=obligation.side_effects,
            error_paths=obligation.error_paths,
            behavior_plane="development_process",
            business_intent_id="intent:development-process-strategy-selection",
            behavior_commitment_id="commitment:development-process-strategy-selection",
            primary_path_id=PRIMARY_PATH_ID,
        )
        for index, obligation in enumerate(obligations, start=1)
    )
    evidence = tuple(
        TestEvidence(
            f"{EVIDENCE_PREFIX}:{index}",
            test_name=f"known_bad_replay_{index}",
            path=".flowguard/development_process_strategy/run_checks.py",
            command="python .flowguard/development_process_strategy/run_checks.py",
            result_status=TEST_STATUS_PASSED,
            evidence_current=contract_report.ok,
            test_kind=TEST_KIND_REPLAY,
            covered_obligations=(obligation.obligation_id,),
            covered_code_contracts=(contract.code_contract_id,),
            assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            evidence_role=TEST_EVIDENCE_ROLE_PRIMARY,
            behavior_plane="development_process",
            business_intent_id="intent:development-process-strategy-selection",
            behavior_commitment_id="commitment:development-process-strategy-selection",
            primary_path_id=PRIMARY_PATH_ID,
        )
        for index, (obligation, contract) in enumerate(
            zip(obligations, contracts), start=1
        )
    )
    return ModelTestAlignmentPlan(
        MODEL_ID,
        obligations=obligations,
        code_contracts=contracts,
        test_evidence=evidence,
        require_stable_authority_ids=True,
        require_behavior_plane_binding=True,
    )


def review_development_process_strategy_alignment():
    return review_model_test_alignment(development_process_strategy_alignment_plan())


__all__ = [
    "development_process_strategy_alignment_plan",
    "development_process_strategy_contract_plan",
    "review_development_process_strategy_alignment",
    "review_development_process_strategy_contracts",
]
