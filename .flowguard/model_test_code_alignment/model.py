"""FlowGuard rollout model for model/test/code contract alignment.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the Model-Test Alignment upgrade that binds model obligations,
owner code contracts, source audit, closure targets, and test evidence.
Guards against: green alignment claims when a model obligation has no code
contract, a code contract misses or adds external behavior, a test does not
bind the code contract it proves, a test checks only internal paths, source
audit is missing for real-code claims, or a counterexample lacks target-aware
owner-code replay evidence. Plane-aware obligations also block when product
runtime, AI operation, and development-process evidence are mixed.

Run:
python .flowguard/model_test_code_alignment/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import (
    CodeContract,
    ClosureEvidenceTarget,
    ModelObligation,
    ModelTestAlignmentPlan,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
    TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    CODE_CONTRACT_ROLE_FACADE,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
    review_model_test_alignment,
)


@dataclass(frozen=True)
class RolloutCase:
    name: str
    plan: ModelTestAlignmentPlan
    expected_ok: bool
    expected_codes: tuple[str, ...] = ()


def _obligation() -> ModelObligation:
    return ModelObligation(
        "reject_duplicate_order",
        obligation_type="hazard",
        description="duplicate order is rejected without a second side effect",
        external_inputs=("order_id",),
        external_outputs=("Rejected",),
        state_reads=("order_status",),
        side_effects=(),
        error_paths=("duplicate_order",),
        exact_external_contract=True,
        required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
        business_intent_id="checkout.submit-order",
        behavior_commitment_id="commitment:checkout.submit-order",
        primary_path_id="path:checkout.reject-duplicate",
    )


def _contract(**overrides: object) -> CodeContract:
    values = {
        "code_contract_id": "checkout_reject_duplicate",
        "path": "checkout/service.py",
        "symbol": "reject_duplicate_order",
        "implements_obligations": ("reject_duplicate_order",),
        "external_inputs": ("order_id",),
        "external_outputs": ("Rejected",),
        "state_reads": ("order_status",),
        "side_effects": (),
        "error_paths": ("duplicate_order",),
        "business_intent_id": "checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.reject-duplicate",
    }
    values.update(overrides)
    return CodeContract(**values)


def _evidence(evidence_id: str, kind: str, **overrides: object) -> TestEvidence:
    values = {
        "test_name": evidence_id,
        "path": "tests/test_checkout.py",
        "result_status": "passed",
        "test_kind": kind,
        "covered_obligations": ("reject_duplicate_order",),
        "covered_code_contracts": ("checkout_reject_duplicate",),
        "assertion_scope": TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
        "business_intent_id": "checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.reject-duplicate",
    }
    values.update(overrides)
    return TestEvidence(evidence_id, **values)


def aligned_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


SOURCE = {
    "checkout/service.py": """
def reject_duplicate_order(order_id):
    if order_id:
        return "Rejected"
    return "Rejected"
""",
    "tests/test_checkout.py": """
def test_duplicate_happy():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_duplicate_failure():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_duplicate_counterexample_replay():
    assert reject_duplicate_order("counterexample:duplicate-order") == "Rejected"
""",
}


def source_audit_report(plan: ModelTestAlignmentPlan):
    code_audit = audit_python_code_contracts(plan.code_contracts, SOURCE)
    test_audit = audit_python_test_assertions(plan.test_evidence, plan.code_contracts, SOURCE)
    return review_python_contract_source_audit(plan.code_contracts, plan.test_evidence, code_audit, test_audit)


def source_audited_plan() -> ModelTestAlignmentPlan:
    base = aligned_plan()
    return replace(base, require_source_audit=True, source_audit_reports=(source_audit_report(base),))


def missing_source_audit_plan() -> ModelTestAlignmentPlan:
    return replace(aligned_plan(), require_source_audit=True)


def missing_code_contract_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH, covered_code_contracts=()),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH, covered_code_contracts=()),
        ),
    )


def extra_side_effect_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(side_effects=("publish_duplicate_metric",)),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def missing_output_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(external_outputs=()),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def missing_code_bound_test_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH, covered_code_contracts=()),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH, covered_code_contracts=()),
        ),
    )


def internal_path_only_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence(
                "test_duplicate_happy",
                TEST_KIND_HAPPY_PATH,
                assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            ),
            _evidence(
                "test_duplicate_failure",
                TEST_KIND_FAILURE_PATH,
                assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            ),
        ),
    )


def binding_mismatch_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(), ModelObligation("accept_valid_order")),
        code_contracts=(_contract(code_contract_id="checkout_accept_order", implements_obligations=("accept_valid_order",)),),
        test_evidence=(
            _evidence(
                "test_duplicate_happy",
                TEST_KIND_HAPPY_PATH,
                covered_code_contracts=("checkout_accept_order",),
            ),
            _evidence(
                "test_duplicate_failure",
                TEST_KIND_FAILURE_PATH,
                covered_code_contracts=("checkout_accept_order",),
            ),
        ),
    )


def stable_path_mismatch_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(primary_path_id="path:checkout.alternate-success"),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def facade_delegation_plan(*, current: bool, delegation_only: bool) -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(
            _contract(),
            _contract(
                code_contract_id="checkout_public_facade",
                role=CODE_CONTRACT_ROLE_FACADE,
                delegates_to_code_contract_id="checkout_reject_duplicate",
                delegation_evidence_id="runtime:checkout-public-facade",
                delegation_evidence_current=current,
                delegation_only=delegation_only,
            ),
        ),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def similarity_materialization_plan(*, materialized: bool) -> ModelTestAlignmentPlan:
    relation_id = "similarity:checkout-duplicate-handlers"
    test_obligation_id = "similarity-test:checkout-duplicate-handlers"
    code_obligation_id = "similarity-code:checkout-duplicate-handlers"
    obligation = replace(
        _obligation(),
        similarity_relation_ids=(relation_id,) if materialized else (),
        similarity_test_obligation_ids=(test_obligation_id,) if materialized else (),
        similarity_impacted_model_ids=("checkout",) if materialized else (),
    )
    contract = replace(
        _contract(),
        similarity_relation_ids=(relation_id,) if materialized else (),
        similarity_code_obligation_ids=(code_obligation_id,) if materialized else (),
    )
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(obligation,),
        code_contracts=(contract,),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
        similarity_handoff={
            "relation_ids": (relation_id,),
            "maintenance_group_ids": ("similarity-group:checkout",),
            "impacted_model_ids": ("checkout",),
            "test_obligation_ids": (test_obligation_id,),
            "code_obligation_ids": (code_obligation_id,),
            "evidence_current": True,
        },
    )


def plane_aware_alignment_plan(*, mismatch: bool = False) -> ModelTestAlignmentPlan:
    plane_rows = (
        ("behavior_plane_schema", "development_process"),
        ("behavior_plane_lookup", "agent_operation"),
        ("behavior_plane_preflight", "agent_operation"),
        ("behavior_plane_similarity", "agent_operation"),
        ("behavior_plane_migration", "development_process"),
        ("behavior_plane_miss_backfeed", "agent_operation"),
    )
    obligations = tuple(
        ModelObligation(
            obligation_id,
            description=f"{obligation_id} remains bound to its owning behavior plane",
            required_test_kinds=(TEST_KIND_HAPPY_PATH,),
            required_closure_targets=(
                ClosureEvidenceTarget(
                    f"plane-upgrade:{obligation_id}",
                    closure_evidence_role=TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
                ),
            ),
            behavior_plane=behavior_plane,
        )
        for obligation_id, behavior_plane in plane_rows
    )
    contracts = tuple(
        CodeContract(
            f"flowguard.{obligation_id}",
            path="flowguard/behavior_commitment.py",
            symbol=obligation_id,
            implements_obligations=(obligation_id,),
            behavior_plane=(
                "product_runtime"
                if mismatch and obligation_id == "behavior_plane_lookup"
                else behavior_plane
            ),
        )
        for obligation_id, behavior_plane in plane_rows
    )
    evidence = tuple(
        TestEvidence(
            f"test_{obligation_id}",
            result_status="passed",
            test_kind=TEST_KIND_HAPPY_PATH,
            covered_obligations=(obligation_id,),
            covered_code_contracts=(f"flowguard.{obligation_id}",),
            assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            closure_evidence_role=TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
            evidence_target_id=f"plane-upgrade:{obligation_id}",
            behavior_plane=behavior_plane,
        )
        for obligation_id, behavior_plane in plane_rows
    )
    return ModelTestAlignmentPlan(
        model_id="behavior-plane-upgrade",
        obligations=obligations,
        code_contracts=contracts,
        test_evidence=evidence,
        require_behavior_plane_binding=True,
    )


def counterexample_closure_obligation() -> ModelObligation:
    return ModelObligation(
        "reject_duplicate_counterexample",
        obligation_type="model_miss",
        description="duplicate-order counterexample is replayed through owner code",
        external_inputs=("order_id",),
        external_outputs=("Rejected",),
        required_test_kinds=(TEST_KIND_HAPPY_PATH,),
        required_closure_targets=(
            ClosureEvidenceTarget(
                "counterexample:duplicate-order",
                closure_evidence_role=TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
            ),
        ),
    )


def counterexample_closure_plan(include_target_evidence: bool) -> ModelTestAlignmentPlan:
    test_items = (
        _evidence(
            "test_duplicate_counterexample_replay",
            TEST_KIND_HAPPY_PATH,
            covered_obligations=("reject_duplicate_counterexample",),
            covered_code_contracts=("checkout_reject_counterexample",),
            closure_evidence_role=TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION if include_target_evidence else "",
            evidence_target_id="counterexample:duplicate-order" if include_target_evidence else "",
        ),
    )
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(counterexample_closure_obligation(),),
        code_contracts=(
            _contract(
                code_contract_id="checkout_reject_counterexample",
                implements_obligations=("reject_duplicate_counterexample",),
            ),
        ),
        test_evidence=test_items,
    )


def rollout_cases() -> tuple[RolloutCase, ...]:
    return (
        RolloutCase("aligned_model_code_test_contracts", aligned_plan(), True),
        RolloutCase("source_audited_real_code_claim", source_audited_plan(), True),
        RolloutCase("missing_source_audit_blocks", missing_source_audit_plan(), False, ("missing_source_audit_report",)),
        RolloutCase("counterexample_target_closure_passes", counterexample_closure_plan(True), True),
        RolloutCase(
            "counterexample_target_without_replay_blocks",
            counterexample_closure_plan(False),
            False,
            ("missing_counterexample_regression_test",),
        ),
        RolloutCase("missing_code_contract_blocks", missing_code_contract_plan(), False, ("missing_code_contract",)),
        RolloutCase("extra_code_side_effect_blocks", extra_side_effect_plan(), False, ("code_contract_extra_behavior",)),
        RolloutCase("missing_code_output_blocks", missing_output_plan(), False, ("code_contract_missing_behavior",)),
        RolloutCase(
            "test_without_code_contract_binding_blocks",
            missing_code_bound_test_plan(),
            False,
            ("test_not_bound_to_code_contract", "missing_code_contract_test_evidence"),
        ),
        RolloutCase(
            "internal_path_only_test_blocks",
            internal_path_only_plan(),
            False,
            ("test_checks_internal_path_only", "missing_code_contract_test_evidence"),
        ),
        RolloutCase("model_code_test_binding_mismatch_blocks", binding_mismatch_plan(), False, ("model_code_test_binding_mismatch",)),
        RolloutCase("stable_primary_path_mismatch_blocks", stable_path_mismatch_plan(), False, ("primary_path_id_mismatch",)),
        RolloutCase("current_delegating_facade_passes", facade_delegation_plan(current=True, delegation_only=True), True),
        RolloutCase("stale_facade_delegation_blocks", facade_delegation_plan(current=False, delegation_only=True), False, ("facade_delegation_evidence_stale",)),
        RolloutCase("facade_parallel_success_blocks", facade_delegation_plan(current=True, delegation_only=False), False, ("facade_independent_business_authority",)),
        RolloutCase("similarity_handoff_materializes", similarity_materialization_plan(materialized=True), True),
        RolloutCase("opaque_similarity_handoff_blocks", similarity_materialization_plan(materialized=False), False, ("unmaterialized_similarity_relation_id",)),
        RolloutCase("plane_aware_model_code_test_bindings_pass", plane_aware_alignment_plan(), True),
        RolloutCase(
            "cross_plane_code_binding_blocks",
            plane_aware_alignment_plan(mismatch=True),
            False,
            ("behavior_plane_mismatch",),
        ),
    )


def run_rollout_review() -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for case in rollout_cases():
        report = review_model_test_alignment(case.plan)
        codes = tuple(finding.code for finding in report.findings)
        ok_matches = report.ok is case.expected_ok
        codes_match = all(code in codes for code in case.expected_codes)
        results.append((case.name, ok_matches and codes_match, codes))
    return tuple(results)


__all__ = ["rollout_cases", "run_rollout_review"]


from flowguard.skill_contract_model import (
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing model-test-alignment owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-model-test-alignment",
        route_id="model_test_alignment",
        owner_id="model_test_alignment",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Bind model obligations to one owner contract and current tests without plane or path drift.",
        claim_boundary="Projection only; row-level alignment, source audit, replay, similarity provenance, and native runner evidence remain authoritative.",
    )


__all__ = [*__all__, "FLOWGUARD_MODEL_MARKER", "export_contract_model"]
