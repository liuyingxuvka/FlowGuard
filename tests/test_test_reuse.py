import unittest

from flowguard import (
    TestResultReuseTicket,
    coerce_test_result_reuse_ticket,
    test_result_reuse_gap_codes as reuse_gap_codes,
)


def reuse_ticket(evidence_id="test:fast", **kwargs):
    defaults = {
        "previous_evidence_id": "test:fast@previous",
        "reason": "same command, source, tested artifact, dependency, and result fingerprints",
        "command_fingerprint": "sha256:command",
        "test_source_fingerprint": "sha256:test-source",
        "tested_artifact_fingerprint": "sha256:tested-artifact",
        "dependency_fingerprints": {"flowguard": "0.39.2"},
        "environment_fingerprint": "python:3.12",
        "result_fingerprint": "sha256:result",
        "covered_obligation_ids": ("accept_valid_order",),
    }
    defaults.update(kwargs)
    return TestResultReuseTicket(evidence_id, **defaults)


class TestResultReuseTicketTests(unittest.TestCase):
    def test_current_ticket_has_no_gap_and_serializes(self):
        ticket = reuse_ticket()

        self.assertEqual((), reuse_gap_codes(ticket))
        self.assertTrue(ticket.has_current_reuse_proof())
        self.assertEqual("test:fast", ticket.to_dict()["evidence_id"])
        self.assertEqual({"flowguard": "0.39.2"}, ticket.to_dict()["dependency_fingerprints"])

    def test_mapping_can_be_coerced_to_ticket(self):
        ticket = coerce_test_result_reuse_ticket(reuse_ticket().to_dict())

        self.assertIsInstance(ticket, TestResultReuseTicket)
        self.assertEqual((), reuse_gap_codes(ticket))

    def test_missing_ticket_is_gap(self):
        self.assertEqual(
            ("missing_test_reuse_ticket",),
            tuple(code for code, _ in reuse_gap_codes(None)),
        )

    def test_stale_inputs_and_missing_scope_are_reported(self):
        ticket = reuse_ticket(
            evidence_id="test:other",
            reason="",
            previous_evidence_id="",
            result_fingerprint="",
            command_current=False,
            test_source_current=False,
            tested_artifacts_current=False,
            dependencies_current=False,
            environment_current=False,
            previous_result_current=False,
            result_fingerprint_matches=False,
            coverage_scope_current=False,
            covered_obligation_ids=("accept_valid_order",),
        )

        codes = {
            code
            for code, _ in reuse_gap_codes(
                ticket,
                expected_evidence_id="test:fast",
                required_obligation_ids=("accept_valid_order", "reject_duplicate_order"),
            )
        }

        self.assertIn("test_reuse_evidence_mismatch", codes)
        self.assertIn("test_reuse_missing_reason", codes)
        self.assertIn("test_reuse_missing_previous_evidence", codes)
        self.assertIn("test_reuse_missing_result_fingerprint", codes)
        self.assertIn("test_reuse_command_stale", codes)
        self.assertIn("test_reuse_source_stale", codes)
        self.assertIn("test_reuse_tested_artifact_stale", codes)
        self.assertIn("test_reuse_dependencies_stale", codes)
        self.assertIn("test_reuse_environment_stale", codes)
        self.assertIn("test_reuse_previous_result_stale", codes)
        self.assertIn("test_reuse_result_fingerprint_mismatch", codes)
        self.assertIn("test_reuse_coverage_scope_stale", codes)
        self.assertIn("test_reuse_missing_obligation", codes)


if __name__ == "__main__":
    unittest.main()
