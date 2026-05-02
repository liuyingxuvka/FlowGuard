import subprocess
import sys
import unittest

from examples.assumption_card_safety.model import run_assumption_policy_check


EXPECTED_BROKEN_VIOLATIONS = {
    "no_bad_assumption_acceptances",
    "no_internal_equivalence_claim_accepted",
    "accepted_assumptions_are_visible",
    "accepted_assumptions_keep_preconditions",
}


class AssumptionCardSafetyModelTests(unittest.TestCase):
    def test_correct_policy_passes_and_broken_policy_is_caught(self):
        correct = run_assumption_policy_check()
        broken = run_assumption_policy_check(broken=True)

        self.assertTrue(correct.ok, correct.format_text())
        self.assertFalse(broken.ok)
        violation_names = {violation.invariant_name for violation in broken.violations}
        self.assertTrue(EXPECTED_BROKEN_VIOLATIONS.issubset(violation_names))

    def test_assumption_card_safety_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/assumption_card_safety/run_checks.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("correct assumption policy", completed.stdout)
        self.assertIn("broken accept-all policy", completed.stdout)


if __name__ == "__main__":
    unittest.main()

