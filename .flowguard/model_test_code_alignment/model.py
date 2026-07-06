"""FlowGuard rollout model for model/test/code contract alignment.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the Model-Test Alignment upgrade that binds model obligations,
owner code contracts, source audit, closure targets, and test evidence.
Guards against: green alignment claims when a model obligation has no code
contract, a code contract misses or adds external behavior, a test does not
bind the code contract it proves, a test checks only internal paths, source
audit is missing for real-code claims, or a counterexample lacks target-aware
owner-code replay evidence.

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
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
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
