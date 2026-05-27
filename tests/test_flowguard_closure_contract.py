import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FlowGuardClosureContractModelTests(unittest.TestCase):
    def test_closure_contract_model_runner_succeeds(self):
        completed = subprocess.run(
            [sys.executable, ".flowguard/flowguard_closure_contract/run_checks.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Scenario: good_closure_contract", completed.stdout)
        self.assertIn("Scenario: broken_point_evidence_completion", completed.stdout)
        self.assertIn("broken_optional_mode", completed.stdout)


if __name__ == "__main__":
    unittest.main()
