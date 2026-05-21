import unittest

import flowguard
from flowguard import (
    CodeBoundaryContract,
    CodeBoundaryObservation,
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    review_code_boundary_conformance,
    review_model_test_alignment,
)


def boundary(**overrides):
    values = {
        "boundary_id": "checkout.submit.boundary",
        "code_contract_id": "checkout.submit",
        "model_obligation_id": "accept_valid_order",
        "allowed_inputs": ("valid_order",),
        "rejected_inputs": ("unknown_event",),
        "allowed_outputs": ("Accepted", "RejectedInvalidInput"),
        "allowed_state_writes": ("order_status",),
        "allowed_side_effects": ("publish_accept",),
        "allowed_error_paths": ("invalid_input",),
    }
    values.update(overrides)
    return CodeBoundaryContract(**values)


def observation(observation_id, input_case, **overrides):
    values = {
        "boundary_id": "checkout.submit.boundary",
        "input_case": input_case,
        "accepted": True,
        "observed_output": "Accepted",
        "observed_state_writes": ("order_status",),
        "observed_side_effects": ("publish_accept",),
    }
    values.update(overrides)
    return CodeBoundaryObservation(observation_id, **values)


def finding_codes(report):
    return [finding.code for finding in report.findings]


class CodeBoundaryConformanceTests(unittest.TestCase):
    def test_declared_boundary_with_input_gate_can_continue(self):
        report = review_code_boundary_conformance(
            (boundary(),),
            (
                observation("accept_valid_order", "valid_order"),
                observation(
                    "reject_unknown_event",
                    "unknown_event",
                    accepted=False,
                    observed_output="RejectedInvalidInput",
                    observed_error_path="invalid_input",
                    observed_state_writes=(),
                    observed_side_effects=(),
                ),
            ),
            (CodeContract("checkout.submit"),),
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("code_boundary_conformance_green", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard code boundary conformance", report.format_text())

    def test_forbidden_input_acceptance_blocks_boundary_confidence(self):
        report = review_code_boundary_conformance(
            (boundary(),),
            (
                observation("accept_valid_order", "valid_order"),
                observation("accept_unknown_event", "unknown_event"),
            ),
        )

        self.assertFalse(report.ok)
        self.assertEqual("boundary_missing_rejected_input_evidence", report.decision)
        self.assertIn("boundary_forbidden_input_accepted", finding_codes(report))

    def test_exact_boundary_blocks_extra_outputs_and_side_effects(self):
        report = review_code_boundary_conformance(
            (boundary(allowed_outputs=("Accepted",), allowed_side_effects=()),),
            (
                observation(
                    "accept_valid_order",
                    "valid_order",
                    observed_output="PartialSuccess",
                    observed_side_effects=("publish_accept", "publish_metric"),
                ),
                observation(
                    "reject_unknown_event",
                    "unknown_event",
                    accepted=False,
                    observed_output="RejectedInvalidInput",
                    observed_error_path="invalid_input",
                    observed_state_writes=(),
                    observed_side_effects=(),
                ),
            ),
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("boundary_extra_output", codes)
        self.assertIn("boundary_extra_side_effect", codes)

    def test_missing_rejected_input_gate_evidence_blocks(self):
        report = review_code_boundary_conformance(
            (boundary(),),
            (observation("accept_valid_order", "valid_order"),),
        )

        self.assertFalse(report.ok)
        self.assertEqual("boundary_missing_rejected_input_evidence", report.decision)
        self.assertIn("boundary_missing_rejected_input_evidence", finding_codes(report))

    def test_non_passing_or_internal_boundary_observation_is_not_coverage(self):
        report = review_code_boundary_conformance(
            (boundary(),),
            (
                observation("accept_valid_order", "valid_order", result_status="skipped"),
                observation(
                    "reject_unknown_event",
                    "unknown_event",
                    accepted=False,
                    observed_output="RejectedInvalidInput",
                    observed_error_path="invalid_input",
                    assertion_scope=flowguard.TEST_ASSERTION_SCOPE_INTERNAL_PATH,
                    observed_state_writes=(),
                    observed_side_effects=(),
                ),
            ),
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("boundary_observation_not_passing", codes)
        self.assertIn("boundary_observation_internal_path_only", codes)
        self.assertIn("boundary_missing_runtime_evidence", codes)

    def test_model_test_alignment_blocks_on_boundary_failure(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                ModelObligation(
                    "accept_valid_order",
                    external_inputs=("order",),
                    external_outputs=("Accepted",),
                    exact_external_contract=True,
                ),
            ),
            code_contracts=(
                CodeContract(
                    "checkout.submit",
                    implements_obligations=("accept_valid_order",),
                    external_inputs=("order",),
                    external_outputs=("Accepted",),
                ),
            ),
            test_evidence=(
                TestEvidence(
                    "test_accept_valid_order",
                    result_status="passed",
                    covered_obligations=("accept_valid_order",),
                    covered_code_contracts=("checkout.submit",),
                ),
            ),
            boundary_contracts=(
                boundary(
                    boundary_id="checkout.submit.boundary",
                    code_contract_id="checkout.submit",
                    model_obligation_id="accept_valid_order",
                    allowed_outputs=("Accepted",),
                    allowed_side_effects=(),
                ),
            ),
            boundary_observations=(
                observation(
                    "test_accept_valid_order_boundary",
                    "valid_order",
                    observed_output="AcceptedAndCached",
                    observed_side_effects=("publish_metric",),
                ),
                observation(
                    "test_reject_unknown_event_boundary",
                    "unknown_event",
                    accepted=False,
                    observed_output="RejectedInvalidInput",
                    observed_error_path="invalid_input",
                    observed_state_writes=(),
                    observed_side_effects=(),
                ),
            ),
        )

        report = review_model_test_alignment(plan)
        codes = finding_codes(report)

        self.assertFalse(report.ok)
        self.assertEqual("code_boundary_conformance_failed", report.decision)
        self.assertIn("boundary_extra_output", codes)
        self.assertIn("boundary_extra_side_effect", codes)


if __name__ == "__main__":
    unittest.main()
