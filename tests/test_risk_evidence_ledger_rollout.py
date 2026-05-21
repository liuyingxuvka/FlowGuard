import unittest

from examples.risk_evidence_ledger.run_checks import run_rollout_checks


class RiskEvidenceLedgerRolloutTests(unittest.TestCase):
    def test_rollout_model_blocks_known_bad_confidence_claims(self):
        correct, broken = run_rollout_checks()

        self.assertTrue(correct.ok, correct.format_text(max_examples=1))
        self.assertFalse(broken.ok)
        self.assertIn("claim_blocked", {label for trace in correct.traces for label in trace.labels})
        self.assertIn(
            "no_known_gap_case_allowed",
            [violation.invariant_name for violation in broken.violations],
        )


if __name__ == "__main__":
    unittest.main()
