import unittest

import flowguard
from flowguard import (
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
    TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
    TEST_KIND_EDGE_PATH,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    ProofArtifactRef,
    review_model_test_alignment,
)


def api_name(name):
    return getattr(flowguard, name)


def obligation(obligation_id, **kwargs):
    defaults = {"required_test_kinds": (TEST_KIND_HAPPY_PATH,)}
    defaults.update(kwargs)
    return ModelObligation(obligation_id, **defaults)


def code_contract(contract_id, *covered, **kwargs):
    defaults = {
        "path": "checkout/service.py",
        "symbol": "CheckoutService.submit",
        "role": api_name("CODE_CONTRACT_ROLE_OWNER"),
        "implements_obligations": tuple(covered),
    }
    defaults.update(kwargs)
    return api_name("CodeContract")(contract_id, **defaults)


def evidence(evidence_id, *covered, **kwargs):
    defaults = {
        "result_status": "passed",
        "evidence_current": True,
        "test_kind": TEST_KIND_HAPPY_PATH,
        "covered_obligations": tuple(covered),
    }
    defaults.update(kwargs)
    return TestEvidence(evidence_id, **defaults)


def proof_artifact(artifact_id, *covered):
    return ProofArtifactRef(
        artifact_id,
        result_status="passed",
        exit_code=0,
        result_path=f"tmp/{artifact_id.replace(':', '_')}.json",
        artifact_fingerprints={f"tmp/{artifact_id.replace(':', '_')}.json": "sha256:test"},
        covered_obligation_ids=covered,
    )


def contract_evidence(evidence_id, obligation_id, contract_id, **kwargs):
    defaults = {
        "covered_code_contracts": (contract_id,),
        "assertion_scope": api_name("TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT"),
    }
    defaults.update(kwargs)
    return evidence(evidence_id, obligation_id, **defaults)


def finding_codes(report):
    return [finding.code for finding in report.findings]


def source_audit_finding_codes(report):
    return [finding.code for finding in report.findings]


class ModelTestAlignmentTests(unittest.TestCase):
    def test_legacy_model_test_only_alignment_can_continue(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation("accept_valid_order"),
                obligation("reject_duplicate_order"),
            ),
            test_evidence=(
                evidence("test_accept_valid_order", "accept_valid_order"),
                evidence("test_reject_duplicate_order", "reject_duplicate_order"),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok)
        self.assertEqual("model_test_alignment_green", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard model-test alignment", report.format_text())

    def test_model_code_contract_and_test_evidence_alignment_can_continue(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
                obligation(
                    "reject_duplicate_order",
                    required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
                    external_inputs=("order",),
                    external_outputs=("rejected_duplicate",),
                    side_effects=("preserve_single_write",),
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.submit",
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
                code_contract(
                    "checkout.reject_duplicate",
                    "reject_duplicate_order",
                    external_inputs=("order",),
                    external_outputs=("rejected_duplicate",),
                    side_effects=("preserve_single_write",),
                ),
            ),
            test_evidence=(
                contract_evidence(
                    "test_accept_valid_order",
                    "accept_valid_order",
                    "checkout.submit",
                ),
                contract_evidence(
                    "test_reject_duplicate_order_happy",
                    "reject_duplicate_order",
                    "checkout.reject_duplicate",
                ),
                contract_evidence(
                    "test_reject_duplicate_order_failure",
                    "reject_duplicate_order",
                    "checkout.reject_duplicate",
                    test_kind=TEST_KIND_FAILURE_PATH,
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok)
        self.assertEqual("model_test_alignment_green", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertEqual(
            ["checkout.submit", "checkout.reject_duplicate"],
            [item["code_contract_id"] for item in plan.to_dict()["code_contracts"]],
        )

    def test_missing_code_contract_blocks_required_external_contract(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
                obligation(
                    "reject_duplicate_order",
                    external_inputs=("order",),
                    external_outputs=("rejected_duplicate",),
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.submit",
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            test_evidence=(
                contract_evidence(
                    "test_accept_valid_order",
                    "accept_valid_order",
                    "checkout.submit",
                ),
                evidence("test_reject_duplicate_order", "reject_duplicate_order"),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_code_contract", report.decision)
        self.assertIn("missing_code_contract", finding_codes(report))

    def test_code_contract_extra_behavior_blocks_green(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                    exact_external_contract=True,
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.submit",
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted", "silently_upgraded"),
                ),
            ),
            test_evidence=(
                contract_evidence(
                    "test_accept_valid_order",
                    "accept_valid_order",
                    "checkout.submit",
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("code_contract_extra_behavior", report.decision)
        self.assertIn("code_contract_extra_behavior", finding_codes(report))

    def test_code_contract_missing_behavior_blocks_green(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_order",
                    external_inputs=("order",),
                    external_outputs=("rejected_duplicate",),
                    side_effects=("preserve_single_write",),
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.reject_duplicate",
                    "reject_duplicate_order",
                    external_inputs=("order",),
                    external_outputs=("rejected_duplicate",),
                ),
            ),
            test_evidence=(
                contract_evidence(
                    "test_reject_duplicate_order",
                    "reject_duplicate_order",
                    "checkout.reject_duplicate",
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("code_contract_missing_behavior", report.decision)
        self.assertIn("code_contract_missing_behavior", finding_codes(report))

    def test_model_test_evidence_must_bind_to_code_contract(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.submit",
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            test_evidence=(evidence("test_accept_valid_order", "accept_valid_order"),),
        )

        report = review_model_test_alignment(plan)
        codes = set(finding_codes(report))

        self.assertFalse(report.ok)
        self.assertTrue(
            {"test_not_bound_to_code_contract", "missing_code_contract_test_evidence"} & codes,
            codes,
        )

    def test_internal_path_only_test_does_not_satisfy_code_contract(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.submit",
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            test_evidence=(
                contract_evidence(
                    "test_accept_valid_order_internal_helper",
                    "accept_valid_order",
                    "checkout.submit",
                    assertion_scope=api_name("TEST_ASSERTION_SCOPE_INTERNAL_PATH"),
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertIn("test_checks_internal_path_only", finding_codes(report))

    def test_unknown_code_contract_reference_is_visible(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            code_contracts=(
                code_contract(
                    "checkout.submit",
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("accepted",),
                ),
            ),
            test_evidence=(
                contract_evidence(
                    "test_accept_valid_order",
                    "accept_valid_order",
                    "checkout.submit",
                    covered_code_contracts=("checkout.submit", "checkout.not_declared"),
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertIn("unknown_code_contract_reference", finding_codes(report))

    def test_missing_test_evidence_blocks_green(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("reject_duplicate_order"),),
            test_evidence=(),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_test_evidence", report.decision)
        self.assertIn("missing_test_evidence", finding_codes(report))

    def test_orphan_and_unknown_test_evidence_are_visible(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("accept_valid_order"),),
            test_evidence=(
                evidence("test_unbound"),
                evidence("test_unknown", "unknown_obligation"),
                evidence("test_accept_valid_order", "accept_valid_order"),
            ),
        )

        report = review_model_test_alignment(plan)
        codes = finding_codes(report)

        self.assertFalse(report.ok)
        self.assertEqual("orphan_test_evidence", report.decision)
        self.assertIn("orphan_test_evidence", codes)
        self.assertIn("unknown_obligation_reference", codes)

    def test_duplicate_same_kind_claims_block_unless_shared(self):
        blocked = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("accept_valid_order"),),
            test_evidence=(
                evidence("test_accept_a", "accept_valid_order"),
                evidence("test_accept_b", "accept_valid_order"),
            ),
        )
        allowed = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("accept_valid_order", allow_shared_evidence=True),),
            test_evidence=blocked.test_evidence,
        )

        blocked_report = review_model_test_alignment(blocked)
        allowed_report = review_model_test_alignment(allowed)

        self.assertFalse(blocked_report.ok)
        self.assertEqual("duplicate_test_evidence_owner", blocked_report.decision)
        self.assertTrue(allowed_report.ok)

    def test_duplicate_primary_edge_path_requires_child_split(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("terminal_ledger", required_test_kinds=(TEST_KIND_EDGE_PATH,)),),
            test_evidence=(
                evidence("test_source_entries", "terminal_ledger", test_kind=TEST_KIND_EDGE_PATH),
                evidence("test_replay_closure", "terminal_ledger", test_kind=TEST_KIND_EDGE_PATH),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("child_model_split_required", report.decision)
        self.assertIn("obligation_too_coarse_for_primary_evidence", finding_codes(report))

    def test_leaf_matrix_cell_evidence_does_not_duplicate_primary_edge(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("validate_submit", required_test_kinds=(TEST_KIND_EDGE_PATH,)),),
            test_evidence=(
                evidence(
                    "test_empty_idle_cell",
                    "validate_submit",
                    test_kind=TEST_KIND_EDGE_PATH,
                    evidence_role=api_name("TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL"),
                    evidence_target_id="submit.empty:idle",
                ),
                evidence(
                    "test_valid_idle_cell",
                    "validate_submit",
                    test_kind=TEST_KIND_EDGE_PATH,
                    evidence_role=api_name("TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL"),
                    evidence_target_id="submit.valid:idle",
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_supporting_and_leaf_evidence_need_targets(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("validate_submit"),),
            test_evidence=(
                evidence(
                    "test_leaf_without_cell",
                    "validate_submit",
                    evidence_role=api_name("TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL"),
                ),
                evidence(
                    "test_support_without_target",
                    "validate_submit",
                    evidence_role=api_name("TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT"),
                ),
            ),
        )

        report = review_model_test_alignment(plan)
        codes = finding_codes(report)

        self.assertFalse(report.ok)
        self.assertIn("leaf_matrix_cell_target_missing", codes)
        self.assertIn("supporting_evidence_target_missing", codes)

    def test_stale_or_non_passing_evidence_is_not_current_coverage(self):
        cases = (
            evidence("stale_pass", "reject_duplicate_order", evidence_current=False),
            evidence("skipped", "reject_duplicate_order", result_status="skipped"),
            evidence("failed", "reject_duplicate_order", result_status="failed"),
            evidence("timeout", "reject_duplicate_order", result_status="timeout"),
            evidence("not_run", "reject_duplicate_order", result_status="not_run"),
        )
        for item in cases:
            with self.subTest(item=item.evidence_id):
                plan = ModelTestAlignmentPlan(
                    model_id="checkout",
                    obligations=(obligation("reject_duplicate_order"),),
                    test_evidence=(item,),
                )

                report = review_model_test_alignment(plan)
                codes = finding_codes(report)

                self.assertFalse(report.ok)
                self.assertIn("missing_test_evidence", codes)

    def test_required_failure_path_cannot_be_replaced_by_happy_path_only(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_order",
                    required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
                ),
            ),
            test_evidence=(evidence("test_duplicate_happy", "reject_duplicate_order"),),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_required_test_kind", report.decision)
        self.assertIn("missing_required_test_kind", finding_codes(report))

    def test_distinct_required_kinds_are_not_duplicate_ownership(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_order",
                    required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
                ),
            ),
            test_evidence=(
                evidence("test_duplicate_happy", "reject_duplicate_order"),
                evidence(
                    "test_duplicate_failure",
                    "reject_duplicate_order",
                    test_kind=TEST_KIND_FAILURE_PATH,
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok)

    def test_model_miss_closure_requires_observed_and_same_class_evidence(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_submit_family",
                    model_miss_origin=True,
                    requires_same_class_test_evidence=True,
                ),
            ),
            test_evidence=(
                evidence(
                    "test_observed_duplicate_submit",
                    "reject_duplicate_submit_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                ),
                evidence(
                    "test_same_class_duplicate_submit_variants",
                    "reject_duplicate_submit_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("model_test_alignment_green", report.decision)
        self.assertEqual(
            [
                TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
            ],
            list(plan.obligations[0].required_closure_evidence_roles),
        )

    def test_model_miss_observed_regression_only_blocks_same_class_closure(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_submit_family",
                    model_miss_origin=True,
                    requires_same_class_test_evidence=True,
                ),
            ),
            test_evidence=(
                evidence(
                    "test_observed_duplicate_submit",
                    "reject_duplicate_submit_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_same_class_test_evidence", report.decision)
        self.assertIn("missing_same_class_test_evidence", finding_codes(report))

    def test_model_miss_same_class_evidence_must_target_repaired_obligation(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_submit_family",
                    model_miss_origin=True,
                    requires_same_class_test_evidence=True,
                ),
                obligation("other_repair_family"),
            ),
            test_evidence=(
                evidence(
                    "test_observed_duplicate_submit",
                    "reject_duplicate_submit_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                ),
                evidence(
                    "test_same_class_wrong_family",
                    "other_repair_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertIn("missing_same_class_test_evidence", finding_codes(report))

    def test_model_miss_overclaimed_same_class_evidence_stays_blocking(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_submit_family",
                    model_miss_origin=True,
                    requires_same_class_test_evidence=True,
                ),
            ),
            test_evidence=(
                evidence(
                    "test_observed_duplicate_submit",
                    "reject_duplicate_submit_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                ),
                evidence(
                    "test_same_class_overclaim",
                    "reject_duplicate_submit_family",
                    closure_evidence_role=TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
                    overclaims_model_confidence=True,
                ),
            ),
        )

        report = review_model_test_alignment(plan)
        codes = finding_codes(report)

        self.assertFalse(report.ok)
        self.assertIn("missing_same_class_test_evidence", codes)
        self.assertIn("test_overclaims_model_confidence", codes)

    def test_python_source_audit_accepts_external_contract_test(self):
        contract = code_contract(
            "checkout.submit",
            "accept_valid_order",
            path="checkout.py",
            symbol="submit_order",
            external_inputs=("order_id",),
            external_outputs=("accepted",),
            state_writes=("order_status",),
            side_effects=("publish_accept",),
            error_paths=("ValueError",),
        )
        test_item = contract_evidence(
            "test_submit_order",
            "accept_valid_order",
            "checkout.submit",
            path="test_checkout.py",
            test_name="test_submit_order",
        )
        code_source = '''
def submit_order(order_id):
    if order_id == "bad":
        raise ValueError("bad order")
    state = {}
    state["order_status"] = "accepted"
    publish_accept(order_id)
    return "accepted"
'''
        test_source = '''
def test_submit_order():
    result = submit_order("order-1")
    assert result == "accepted"
'''

        code_audit = api_name("audit_python_code_contracts")((contract,), {"checkout.py": code_source})
        test_audit = api_name("audit_python_test_assertions")((test_item,), (contract,), {"test_checkout.py": test_source})
        report = api_name("review_python_contract_source_audit")((contract,), (test_item,), code_audit, test_audit)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("python_contract_source_audit_green", report.decision)
        self.assertEqual(["order_id"], list(code_audit[0].parameters))
        self.assertIn("ValueError", code_audit[0].raised_errors)
        self.assertIn("publish_accept", code_audit[0].side_effects)
        self.assertIn("publish_accept", code_audit[0].calls)
        self.assertEqual(("checkout.submit",), test_audit[0].called_code_contracts)

    def test_python_source_audit_flags_code_contract_gaps(self):
        contract = code_contract(
            "checkout.submit",
            "accept_valid_order",
            path="checkout.py",
            symbol="submit_order",
            external_inputs=("order_id", "payment_token"),
            external_outputs=("accepted",),
            state_writes=("order_status",),
        )
        code_source = '''
def submit_order(order_id):
    publish_metric("accepted")
'''

        code_audit = api_name("audit_python_code_contracts")((contract,), {"checkout.py": code_source})
        report = api_name("review_python_contract_source_audit")((contract,), (), code_audit, ())
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("source_contract_missing_input", report.decision)
        self.assertIn("source_contract_missing_input", codes)
        self.assertIn("source_contract_missing_output", codes)
        self.assertIn("source_contract_missing_state_write", codes)
        self.assertIn("source_contract_extra_side_effect", codes)

    def test_python_source_audit_flags_missing_symbol(self):
        contract = code_contract(
            "checkout.submit",
            "accept_valid_order",
            path="checkout.py",
            symbol="submit_order",
        )

        code_audit = api_name("audit_python_code_contracts")((contract,), {"checkout.py": "def other(): pass"})
        report = api_name("review_python_contract_source_audit")((contract,), (), code_audit, ())

        self.assertFalse(report.ok)
        self.assertEqual("source_contract_missing_symbol", report.decision)

    def test_python_test_audit_flags_internal_path_only_test(self):
        contract = code_contract(
            "checkout.submit",
            "accept_valid_order",
            path="checkout.py",
            symbol="submit_order",
        )
        test_item = contract_evidence(
            "test_submit_order",
            "accept_valid_order",
            "checkout.submit",
            path="test_checkout.py",
            test_name="test_submit_order",
        )
        test_source = '''
def test_submit_order():
    result = helper_submit("order-1")
    assert result == "accepted"
'''

        test_audit = api_name("audit_python_test_assertions")((test_item,), (contract,), {"test_checkout.py": test_source})
        report = api_name("review_python_contract_source_audit")((contract,), (test_item,), (), test_audit)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("source_contract_missing_symbol", report.decision)
        self.assertIn("source_test_missing_code_contract_call", codes)
        self.assertIn("source_test_internal_path_only", codes)

    def test_python_test_audit_flags_missing_external_assertion(self):
        contract = code_contract(
            "checkout.submit",
            "accept_valid_order",
            path="checkout.py",
            symbol="submit_order",
        )
        test_item = contract_evidence(
            "test_submit_order",
            "accept_valid_order",
            "checkout.submit",
            path="test_checkout.py",
            test_name="test_submit_order",
        )
        test_source = '''
def test_submit_order():
    submit_order("order-1")
'''

        test_audit = api_name("audit_python_test_assertions")((test_item,), (contract,), {"test_checkout.py": test_source})
        report = api_name("review_python_contract_source_audit")((contract,), (test_item,), (), test_audit)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertIn("source_test_missing_external_assertion", codes)

    def test_strict_alignment_rejects_declaration_only_test_evidence(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            require_proof_artifacts=True,
            obligations=(obligation("accept_valid_order"),),
            test_evidence=(evidence("test_accept_valid_order", "accept_valid_order"),),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertIn("missing_test_proof_artifact", finding_codes(report))

    def test_strict_alignment_accepts_artifact_backed_test_evidence(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            require_proof_artifacts=True,
            obligations=(obligation("accept_valid_order"),),
            test_evidence=(
                evidence(
                    "test_accept_valid_order",
                    "accept_valid_order",
                    proof_artifact=proof_artifact("artifact:accept", "accept_valid_order"),
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok, report.format_text())


if __name__ == "__main__":
    unittest.main()
