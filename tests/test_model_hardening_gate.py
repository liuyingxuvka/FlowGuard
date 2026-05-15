import subprocess
import sys
import unittest


class ModelHardeningGateTests(unittest.TestCase):
    def test_model_hardening_gate_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/model_hardening_gate/run_checks.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("correct_gate_with_untouched_heavy_checks", completed.stdout)
        self.assertIn("correct_gate_with_touched_heavy_checks", completed.stdout)
        self.assertIn("expected violations observed: 6", completed.stdout)
        self.assertIn("code_first_change", completed.stdout)
        self.assertIn("happy_path_only_model_trust", completed.stdout)
        self.assertIn("hard_coded_heavy_model_names", completed.stdout)
        self.assertIn("touched_heavy_model_skipped", completed.stdout)
        self.assertIn("peer_changes_overwritten", completed.stdout)
        self.assertIn("premature_release", completed.stdout)


if __name__ == "__main__":
    unittest.main()
