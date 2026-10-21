"""FlowGuard rollout model for model/test/code contract alignment.

Purpose: review the Model-Test Alignment upgrade that binds model obligations,
owner code contracts, source audit, closure targets, and test evidence.
Guards against: green alignment claims when a model obligation has no code
contract, a code contract misses or adds external behavior, a test does not
bind the code contract it proves, a test checks only internal paths, source
audit is missing for real-code claims, or a counterexample lacks target-aware
owner-code replay evidence. It also keeps pre-code design separate from
executed evidence and preserves bidirectional model/implementation
traceability. Plane-aware obligations also block when
product runtime, AI operation, and development-process evidence are mixed.

Run:
python -m flowguard map models model_test_code_alignment
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

from flowguard import (
    CODE_CONTRACT_ROLE_FACADE,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    ClosureEvidenceTarget,
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_model_test_alignment,
    review_python_contract_source_audit,
)
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants

PLANE = "product_runtime"
RELATION = "canonical-relation:checkout-duplicate-handlers"
RELATION_TEST = "relation-test:checkout-duplicate-handlers"
RELATION_CODE = "relation-code:checkout-duplicate-handlers"
MAIN, FACADE, COUNTEREXAMPLE = "checkout_reject_duplicate", "checkout_public_facade", "checkout_reject_counterexample"
PAIR = ("test_duplicate_happy", "test_duplicate_failure")
REPLAY = "test_duplicate_counterexample_replay"


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
        relation_ids=(RELATION,),
        relation_test_obligation_ids=(RELATION_TEST,),
        relation_impacted_model_ids=("checkout",),
        behavior_plane=PLANE,
    )


def _contract(**overrides: object) -> CodeContract:
    values = {
        "code_contract_id": MAIN,
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
        "behavior_plane": PLANE,
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
        "covered_code_contracts": (MAIN,),
        "assertion_scope": TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
        "business_intent_id": "checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.reject-duplicate",
        "behavior_plane": PLANE,
    }
    values.update(overrides)
    return TestEvidence(evidence_id, **values)


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


@lru_cache(maxsize=1)                 # the plan is immutable; features build changed copies
def complete_plan() -> ModelTestAlignmentPlan:
    """Every part aligned: the duplicate-order obligation with its code contract, happy and failure tests,
    a delegating facade, a materialized canonical relation, a replayed counterexample target, behavior
    planes and a source audit of the real code and tests."""
    counterexample = ModelObligation(
        "reject_duplicate_counterexample",
        obligation_type="model_miss",
        description="duplicate-order counterexample is replayed through owner code",
        external_inputs=("order_id",),
        external_outputs=("Rejected",),
        required_test_kinds=(TEST_KIND_HAPPY_PATH,),
        required_closure_targets=(ClosureEvidenceTarget(
            "counterexample:duplicate-order", closure_evidence_role=TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION),),
        behavior_plane=PLANE,
    )
    plan = ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(), counterexample),
        code_contracts=(
            _contract(relation_ids=(RELATION,), relation_code_obligation_ids=(RELATION_CODE,)),
            _contract(code_contract_id=FACADE, role=CODE_CONTRACT_ROLE_FACADE, delegates_to_code_contract_id=MAIN,
                      delegation_evidence_id="runtime:checkout-public-facade", delegation_evidence_current=True,
                      delegation_only=True),
            _contract(code_contract_id=COUNTEREXAMPLE, implements_obligations=("reject_duplicate_counterexample",)),
        ),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
            _evidence(REPLAY, TEST_KIND_HAPPY_PATH, covered_obligations=("reject_duplicate_counterexample",),
                      covered_code_contracts=(COUNTEREXAMPLE,),
                      closure_evidence_role=TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
                      evidence_target_id="counterexample:duplicate-order"),
        ),
        canonical_relation_handoff={
            "relations": ({
                "relation_id": RELATION,
                "relation_type": "duplicate_boundary",
                "source_endpoint_kind": "model",
                "source_endpoint_id": "checkout",
                "target_endpoint_kind": "code_contract",
                "target_endpoint_id": MAIN,
                "source_ids": ("semantic-mesh:checkout",),
            },),
            "relation_group_ids": ("relation-group:checkout",),
            "affected_model_ids": ("checkout",),
            "test_obligation_ids": (RELATION_TEST,),
            "code_obligation_ids": (RELATION_CODE,),
            "evidence_current": True,
        },
        require_behavior_plane_binding=True,
    )
    return replace(plan, require_source_audit=True, source_audit_reports=(source_audit_report(plan),))


__all__ = ["complete_plan"]


# FlowGuard contract (feature kit): each former broken plan is a feature that changes one part of the
# complete plan; the kit explores every feature alone and every pair, and conformance reviews each
# combination with the real model-test alignment review.  "pre_code_status=incomplete" is reported as a
# code, so a defect that must not block the pre-code design (tests not run) is checked too.
MODEL_ID = "model_test_code_alignment"
COMPONENTS = ["model-test"]
IMPLEMENTED_BY = {"Review": "flowguard/model_test_alignment.py:review_model_test_alignment"}
TESTED_BY = {"each_defect_rejected": [
    "tests/test_model_test_alignment.py:test_pre_code_design_ready_does_not_promote_not_run_evidence",
    "tests/test_model_test_alignment.py:test_missing_code_contract_blocks_required_external_contract"]}
INCOMPLETE = "pre_code_status=incomplete"


def _contracts(contract_id: str, **values):
    return lambda plan: replace(plan, code_contracts=tuple(replace(c, **values) if c.code_contract_id == contract_id
                                                           else c for c in plan.code_contracts))


def _tests(evidence_ids, **values):
    return lambda plan: replace(plan, test_evidence=tuple(replace(e, **values) if e.evidence_id in evidence_ids
                                                          else e for e in plan.test_evidence))


def _unrelated(plan):
    obligation = replace(_obligation(), relation_ids=(), relation_test_obligation_ids=(),
                         relation_impacted_model_ids=())
    return replace(_contracts(MAIN, relation_ids=(), relation_code_obligation_ids=())(plan),
                   obligations=(obligation,) + plan.obligations[1:])


def _unimplemented_obligation(plan):
    obligation = ModelObligation("reject_unknown_order", external_inputs=("order_id",), external_outputs=("Rejected",),
                                 exact_external_contract=True, required_test_kinds=(TEST_KIND_HAPPY_PATH,),
                                 behavior_plane=PLANE)
    test = _evidence("test_unknown_order", TEST_KIND_HAPPY_PATH, covered_obligations=("reject_unknown_order",),
                     covered_code_contracts=())
    return replace(plan, obligations=plan.obligations + (obligation,), test_evidence=plan.test_evidence + (test,))


def _alternate_path(plan):
    return _contracts(FACADE, primary_path_id="path:checkout.alternate-success")(
        _contracts(MAIN, primary_path_id="path:checkout.alternate-success")(plan))


FEATURES = (
    Feature("tests_not_run", True, ("test_evidence_not_passing", "missing_test_evidence",
                                    "missing_code_contract_test_evidence"), _tests(PAIR, result_status="not_run")),
    Feature("missing_source_audit", True, ("missing_source_audit_report",),
            lambda plan: replace(plan, source_audit_reports=())),
    Feature("counterexample_not_replayed", True, ("missing_counterexample_regression_test", INCOMPLETE),
            _tests((REPLAY,), closure_evidence_role="", evidence_target_id="")),
    Feature("missing_code_contract", True, ("missing_code_contract", "test_not_bound_to_code_contract",
                                            "missing_test_evidence", INCOMPLETE), _unimplemented_obligation),
    Feature("extra_code_side_effect", True, ("code_contract_extra_behavior",),
            _contracts(MAIN, side_effects=("publish_duplicate_metric",))),
    Feature("missing_code_output", True, ("code_contract_missing_behavior",), _contracts(MAIN, external_outputs=())),
    Feature("tests_not_bound_to_code_contract", True, ("test_not_bound_to_code_contract", "missing_test_evidence",
                                                       "missing_code_contract_test_evidence", INCOMPLETE),
            _tests(PAIR, covered_code_contracts=())),
    Feature("internal_path_only_tests", True, ("test_checks_internal_path_only", "missing_test_evidence",
                                               "missing_code_contract_test_evidence", INCOMPLETE),
            _tests(PAIR, assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH)),
    Feature("model_code_test_binding_mismatch", True, ("model_code_test_binding_mismatch", INCOMPLETE),
            _tests(("test_duplicate_failure",), covered_code_contracts=(COUNTEREXAMPLE,))),
    Feature("primary_path_mismatch", True, ("primary_path_id_mismatch",), _alternate_path),
    Feature("stale_facade_delegation", True, ("facade_delegation_evidence_stale",),
            _contracts(FACADE, delegation_evidence_current=False)),
    Feature("facade_parallel_success", True, ("facade_independent_business_authority",),
            _contracts(FACADE, delegation_only=False)),
    Feature("opaque_canonical_relation", True, ("unmaterialized_canonical_relation_id",
                                                "unmaterialized_relation_test_obligation_id",
                                                "unmaterialized_relation_code_obligation_id"), _unrelated),
    Feature("cross_plane_code_binding", True, ("behavior_plane_mismatch",),
            _contracts(MAIN, behavior_plane="agent_operation")),
    Feature("evidence_listed_in_reverse_order", False, (),
            lambda plan: replace(plan, code_contracts=plan.code_contracts[::-1], test_evidence=plan.test_evidence[::-1])),
)


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def _review(plan):
    report = review_model_test_alignment(plan)
    return report.ok, tuple(finding.code for finding in report.findings) + (f"pre_code_status={report.pre_code_status}",)


def conformance():
    return feature_conformance(FEATURES, complete_plan, _review)
