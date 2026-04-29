import unittest

from flowguard.benchmark import build_benchmark_scorecard

from examples.problem_corpus.matrix import build_problem_corpus
from examples.problem_corpus.real_models import (
    MODEL_SPECS,
    VARIANT_SPECS,
    classify_failure_mode,
    input_sequence_for_case,
    review_real_model_corpus,
    select_variant_for_case,
    validate_model_specs,
)


class RealModelCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = build_problem_corpus()
        cls.report = review_real_model_corpus(cls.corpus)
        cls.results = cls.report.results

    def test_model_specs_cover_all_workflow_families(self):
        self.assertEqual((), validate_model_specs())
        corpus_families = {case.workflow_family for case in self.corpus.cases}
        self.assertEqual(corpus_families, set(MODEL_SPECS))
        self.assertEqual(25, len(MODEL_SPECS))
        self.assertEqual(25, len(VARIANT_SPECS))
        self.assertEqual(150, sum(len(variants) for variants in VARIANT_SPECS.values()))
        for family, variants in VARIANT_SPECS.items():
            self.assertEqual(6, len(variants), family)

    def test_real_model_report_has_no_generic_fallback(self):
        self.assertTrue(self.report.ok, self.report.format_text())
        self.assertEqual(2100, self.report.total_cases)
        self.assertEqual(2100, self.report.real_model_cases)
        self.assertEqual(0, self.report.generic_fallback_cases)
        self.assertEqual(0, self.report.not_executable_yet)
        self.assertEqual(0, self.report.failure_cases)
        self.assertEqual(25, len(self.report.model_family_counts))
        self.assertEqual(150, self.report.model_variant_total)
        self.assertEqual(25, self.report.model_families_with_six_variants)

    def test_benchmark_scorecard_preserves_real_model_gate(self):
        scorecard = build_benchmark_scorecard(self.report)
        self.assertTrue(scorecard.ok)
        self.assertEqual(2100, scorecard.total_cases)
        self.assertEqual(2100, scorecard.real_model_cases)
        self.assertEqual(0, scorecard.generic_fallback_cases)
        self.assertEqual(150, scorecard.model_variant_total)
        self.assertEqual(25, scorecard.model_families_with_six_variants)
        self.assertEqual(0, scorecard.failure_cases)
        self.assertIn("real_model_cases", scorecard.to_dict())

    def test_every_case_has_phase_11_binding_metadata(self):
        for result in self.results:
            metadata = dict(result.metadata)
            self.assertEqual("real_domain_model", metadata.get("model_binding_kind"), result.case_id)
            self.assertEqual("false", metadata.get("generic_fallback"), result.case_id)
            self.assertEqual(result.workflow_family, metadata.get("model_family"), result.case_id)
            self.assertTrue(metadata.get("model_name"), result.case_id)
            self.assertTrue(metadata.get("model_variant"), result.case_id)
            self.assertTrue(metadata.get("variant_id"), result.case_id)
            self.assertTrue(metadata.get("variant_title"), result.case_id)
            self.assertTrue(metadata.get("structural_category"), result.case_id)
            self.assertTrue(metadata.get("domain_block_names"), result.case_id)
            self.assertTrue(metadata.get("domain_state_slots"), result.case_id)

    def test_every_case_binds_to_one_of_150_variants(self):
        valid_variant_ids = {
            f"{family}:{variant.variant_id}"
            for family, variants in VARIANT_SPECS.items()
            for variant in variants
        }
        observed_variant_ids = {dict(result.metadata)["variant_id"] for result in self.results}
        self.assertEqual(valid_variant_ids, observed_variant_ids)
        for case in self.corpus.cases:
            variant = select_variant_for_case(case)
            self.assertIn(f"{case.workflow_family}:{variant.variant_id}", valid_variant_ids)

    def test_case_input_sequences_are_deterministic_and_non_empty_when_needed(self):
        for case in self.corpus.cases:
            sequence = input_sequence_for_case(case)
            if case.case_kind == "negative_broken_case":
                self.assertGreaterEqual(len(sequence), 1, case.case_id)
            if case.external_inputs and case.external_inputs[0] == "empty_input_sequence":
                self.assertIn(
                    case.case_kind,
                    {
                        "positive_correct_case",
                        "boundary_edge_case",
                        "negative_broken_case",
                        "invalid_initial_state_case",
                        "loop_or_stuck_case",
                    },
                )

    def test_no_counterexample_uses_old_generic_corpus_blocks(self):
        forbidden = {"CorpusIngest", "CorpusApply", "CorpusFinalize"}
        for result in self.results:
            if result.counterexample_trace is None:
                continue
            functions = {step.function_name for step in result.counterexample_trace.steps}
            self.assertFalse(functions & forbidden, result.case_id)

    def test_negative_and_invalid_cases_have_structural_or_graph_evidence(self):
        for result in self.results:
            if result.status != "expected_violation_observed":
                continue
            evidence = "\n".join(result.evidence)
            if result.execution_kind == "real_model_workflow":
                self.assertIn("structural_category=", evidence, result.case_id)
            elif result.execution_kind == "real_model_loop":
                self.assertIn("findings=", evidence, result.case_id)

    def test_failure_mode_classifier_has_no_unknown_bucket(self):
        categories = {classify_failure_mode(case.failure_mode) for case in self.corpus.cases}
        self.assertNotIn("unknown", categories)
        self.assertIn("duplicate_side_effect", categories)
        self.assertIn("cache_source_mismatch", categories)
        self.assertIn("missing_source_traceability", categories)
        self.assertIn("wrong_state_owner", categories)
        self.assertIn("invalid_transition", categories)


if __name__ == "__main__":
    unittest.main()
