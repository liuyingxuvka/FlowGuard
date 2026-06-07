import unittest

from flowguard import (
    ADAPTER_CONFORMANCE_DECISION_FULL,
    CLAIM_CHAIN_DECISION_FULL,
    CLAIM_CHAIN_DECISION_SCOPED,
    CLAIM_DEPENDENCY_STATUS_PASSED,
    CLAIM_DEPENDENCY_STATUS_SCOPED,
    CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID,
    CLAIM_SCOPE_FALSE_NEGATIVE_CLOSED,
    CLAIM_SCOPE_MODEL_VALID,
    CLAIM_SCOPE_MUTATION_REVIEW_VALID,
    CLAIM_SCOPE_PLAN_VALID_ONLY,
    CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
    CLAIM_SCOPE_RISK_EVIDENCE_VALID,
    CLAIM_SCOPE_RUNTIME_REPLAY_VALID,
    FALSE_NEGATIVE_CAUSE_ADAPTER_MAPPING_LOSS,
    FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
    FALSE_NEGATIVE_DECISION_FULL,
    MUTATION_EXPECTED_FAIL,
    MUTATION_RESULT_FAILED,
    MUTATION_RESULT_PASSED,
    PLAN_INTAKE_DECISION_FULL,
    PLAN_MUTATION_DECISION_FULL,
    RISK_CONFIDENCE_FULL,
    RISK_CONFIDENCE_SCOPED,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    EvidenceAdapterConformancePlan,
    EvidenceAdapterMapping,
    FalseNegativeBackpropagationPlan,
    FalseNegativeCase,
    FlowGuardClaimChainPlan,
    FlowGuardClaimDependency,
    PlanIntakeCompletenessPlan,
    PlanIntakeRiskSurface,
    PlanMutationCase,
    PlanMutationReviewPlan,
    review_evidence_adapter_conformance,
    review_false_negative_backpropagation,
    review_flowguard_claim_chain,
    review_plan_intake_completeness,
    review_plan_mutations,
)


def codes(report):
    return {finding.code for finding in report.findings}


def dependency(dependency_id, scope, **kwargs):
    return FlowGuardClaimDependency(
        dependency_id,
        scope,
        status=kwargs.pop("status", CLAIM_DEPENDENCY_STATUS_PASSED),
        confidence=kwargs.pop("confidence", RISK_CONFIDENCE_FULL),
        evidence_id=kwargs.pop("evidence_id", f"evidence:{dependency_id}"),
        **kwargs,
    )


class PlanIntakeCompletenessTests(unittest.TestCase):
    def test_complete_current_intake_with_recurring_history_passes(self):
        report = review_plan_intake_completeness(
            PlanIntakeCompletenessPlan(
                "duplicate-submit",
                source_evidence_ids=("history:duplicate-submit", "runtime:submit-log"),
                risk_surfaces=(
                    PlanIntakeRiskSurface(
                        "duplicate_submit",
                        source_ids=("history:duplicate-submit",),
                        evidence_ids=("test:duplicate-submit",),
                        recurring=True,
                        observed_failure_ids=("obs:duplicate-submit",),
                        same_class_case_ids=("same-class:duplicate-submit",),
                        historical_holdout_ids=("holdout:duplicate-submit",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(PLAN_INTAKE_DECISION_FULL, report.decision)
        self.assertEqual(RISK_CONFIDENCE_FULL, report.confidence)

    def test_omitted_surface_and_missing_history_block(self):
        report = review_plan_intake_completeness(
            PlanIntakeCompletenessPlan(
                "too-thin",
                source_evidence_ids=("runtime:green",),
                risk_surfaces=(
                    PlanIntakeRiskSurface(
                        "duplicate_submit",
                        included=False,
                        recurring=True,
                        evidence_ids=("runtime:green",),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("omitted_in_scope_surface", codes(report))
        self.assertIn("recurring_history_missing_same_class_case", codes(report))
        self.assertIn("recurring_history_missing_historical_holdout", codes(report))

    def test_scoped_out_surface_downgrades_with_reason(self):
        report = review_plan_intake_completeness(
            PlanIntakeCompletenessPlan(
                "scoped",
                source_evidence_ids=("runtime:green",),
                risk_surfaces=(
                    PlanIntakeRiskSurface(
                        "release-history",
                        in_scope=False,
                        out_of_scope_reason="release-only holdout is tracked by the release gate",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("scoped_out_surface", codes(report))

    def test_source_evidence_alias_is_rejected(self):
        with self.assertRaises(TypeError):
            PlanIntakeCompletenessPlan("alias", source_evidence=())


class EvidenceAdapterConformanceTests(unittest.TestCase):
    def test_adapter_mapping_preserves_identity_freshness_and_status(self):
        report = review_evidence_adapter_conformance(
            EvidenceAdapterConformancePlan(
                "adapter",
                mappings=(
                    EvidenceAdapterMapping(
                        "map:runtime",
                        "runtime:submit",
                        "evidence:runtime:submit",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(ADAPTER_CONFORMANCE_DECISION_FULL, report.decision)

    def test_progress_only_raw_mapped_as_pass_blocks(self):
        report = review_evidence_adapter_conformance(
            EvidenceAdapterConformancePlan(
                "adapter",
                mappings=(
                    EvidenceAdapterMapping(
                        "map:pytest",
                        "pytest:background",
                        "evidence:pytest",
                        expected_classification=RISK_PROOF_STATUS_PROGRESS_ONLY,
                        mapped_classification=RISK_PROOF_STATUS_PASSED,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("classification_loss", codes(report))
        self.assertIn("progress_or_stale_mapped_as_passing", codes(report))

    def test_duplicate_and_known_bad_adapter_fields_are_rejected(self):
        removed_field_sets = (
            {"mapped_evidence_ids": ("evidence:fixture",)},
            {"known_bad_fixture": True},
            {"adapter_rejected_known_bad": False},
            {"rejected": False},
        )

        for kwargs in removed_field_sets:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    EvidenceAdapterMapping(
                        "map:known-bad",
                        "fixture:known-bad",
                        "evidence:fixture",
                        **kwargs,
                    )


class FalseNegativeBackpropagationTests(unittest.TestCase):
    def test_structured_false_negative_backpropagation_passes(self):
        report = review_false_negative_backpropagation(
            FalseNegativeBackpropagationPlan(
                "fn",
                cases=(
                    FalseNegativeCase(
                        "fn-1",
                        previous_claim_id="claim:old-green",
                        observed_failure_id="runtime:duplicate-submit",
                        cause=FALSE_NEGATIVE_CAUSE_ADAPTER_MAPPING_LOSS,
                        would_have_failed_if=("raw progress-only status had been preserved",),
                        adapter_gap_ids=("adapter:pytest-status",),
                        new_plan_item_ids=("adapter-known-bad-fixture",),
                        closure_evidence_ids=("test:adapter-known-bad",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(FALSE_NEGATIVE_DECISION_FULL, report.decision)

    def test_missing_condition_and_backprop_item_block(self):
        report = review_false_negative_backpropagation(
            FalseNegativeBackpropagationPlan(
                "fn",
                cases=(
                    FalseNegativeCase(
                        "fn-1",
                        previous_claim_id="claim:old-green",
                        observed_failure_id="runtime:duplicate-submit",
                        cause=FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_would_have_failed_if", codes(report))
        self.assertIn("missing_backprop_plan_update", codes(report))
        self.assertIn("missing_false_negative_closure_evidence", codes(report))

    def test_false_negative_backpropagation_requires_closure_evidence(self):
        report = review_false_negative_backpropagation(
            FalseNegativeBackpropagationPlan(
                "fn",
                cases=(
                    FalseNegativeCase(
                        "fn-1",
                        previous_claim_id="claim:old-green",
                        observed_failure_id="runtime:duplicate-submit",
                        cause=FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                        would_have_failed_if=("duplicate input branch had existed",),
                        new_model_obligation_id="model:duplicate-submit-family",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_false_negative_closure_evidence", codes(report))


class PlanMutationReviewTests(unittest.TestCase):
    def test_known_bad_mutation_failing_as_expected_passes(self):
        report = review_plan_mutations(
            PlanMutationReviewPlan(
                "mutations",
                mutations=(
                    PlanMutationCase(
                        "drop-history",
                        expected_result=MUTATION_EXPECTED_FAIL,
                        observed_result=MUTATION_RESULT_FAILED,
                        check_id="mutation:drop-history",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(PLAN_MUTATION_DECISION_FULL, report.decision)

    def test_known_bad_mutation_that_passes_blocks(self):
        report = review_plan_mutations(
            PlanMutationReviewPlan(
                "mutations",
                mutations=(
                    PlanMutationCase(
                        "drop-history",
                        expected_result=MUTATION_EXPECTED_FAIL,
                        observed_result=MUTATION_RESULT_PASSED,
                        check_id="mutation:drop-history",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("known_bad_mutation_passed", report.decision)


class FlowGuardClaimChainTests(unittest.TestCase):
    def test_production_claim_requires_typed_support(self):
        report = review_flowguard_claim_chain(
            FlowGuardClaimChainPlan(
                "claim:production",
                CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
                dependencies=(
                    dependency("claim:plan", CLAIM_SCOPE_PLAN_VALID_ONLY),
                    dependency("claim:adapter", CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID),
                    dependency("claim:runtime", CLAIM_SCOPE_RUNTIME_REPLAY_VALID),
                    dependency("claim:risk", CLAIM_SCOPE_RISK_EVIDENCE_VALID),
                    dependency("claim:false-negative", CLAIM_SCOPE_FALSE_NEGATIVE_CLOSED),
                    dependency("claim:mutation", CLAIM_SCOPE_MUTATION_REVIEW_VALID),
                ),
                adapter_conformance_required=True,
                false_negative_backprop_required=True,
                mutation_review_required=True,
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(CLAIM_CHAIN_DECISION_FULL, report.decision)

    def test_model_only_claim_cannot_be_promoted_to_production(self):
        report = review_flowguard_claim_chain(
            FlowGuardClaimChainPlan(
                "claim:model",
                CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
                dependencies=(dependency("claim:model-only", CLAIM_SCOPE_MODEL_VALID),),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_required_claim_scope", codes(report))

    def test_scoped_dependency_scopes_target_claim(self):
        report = review_flowguard_claim_chain(
            FlowGuardClaimChainPlan(
                "claim:production",
                CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
                dependencies=(
                    dependency("claim:plan", CLAIM_SCOPE_PLAN_VALID_ONLY),
                    dependency(
                        "claim:runtime",
                        CLAIM_SCOPE_RUNTIME_REPLAY_VALID,
                        status=CLAIM_DEPENDENCY_STATUS_SCOPED,
                        confidence=RISK_CONFIDENCE_SCOPED,
                        scoped_reasons=("manual replay only",),
                    ),
                    dependency("claim:risk", CLAIM_SCOPE_RISK_EVIDENCE_VALID),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(CLAIM_CHAIN_DECISION_SCOPED, report.decision)

    def test_stale_dependency_blocks_target_claim(self):
        report = review_flowguard_claim_chain(
            FlowGuardClaimChainPlan(
                "claim:production",
                CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
                dependencies=(
                    dependency("claim:plan", CLAIM_SCOPE_PLAN_VALID_ONLY),
                    dependency("claim:runtime", CLAIM_SCOPE_RUNTIME_REPLAY_VALID, current=False),
                    dependency("claim:risk", CLAIM_SCOPE_RISK_EVIDENCE_VALID),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("stale_claim_dependency", codes(report))


if __name__ == "__main__":
    unittest.main()
