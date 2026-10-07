"""The retired SkillGuard command-binding fixture has no current authority.

Its execution, pytest sharing, and command-resume tests belong to the actual
native/model/process owners. Current03 tests are consumer-only below and in
 test_skill_native_model_receipts; no old schema reader is kept to pass them.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flowguard.skill_native_checks import run_native_skill_check
from scripts.run_flowguard_skill_native_checks import build_parser, main


class SkillNativeCheckTests(unittest.TestCase):
    def test_missing_outer_unit_evidence_never_executes_model_checks(self):
        with tempfile.TemporaryDirectory() as directory, patch("subprocess.run", side_effect=AssertionError("native consumer must not execute")):
            with self.assertRaisesRegex(ValueError, "completion_run_manifest_required"):
                run_native_skill_check(Path(directory), "flowguard")

    def test_unregistered_member_is_rejected_before_observation(self):
        with patch("flowguard.skill_native_checks.observe_current_native_models",
                   side_effect=AssertionError("foreign member must not be observed")):
            with self.assertRaisesRegex(ValueError, "unregistered_native_evidence_member"):
                run_native_skill_check(".", "legacy-fixture")

    def test_old_resume_and_pytest_producer_options_are_retired(self):
        parser = build_parser()
        common = ["--output-dir", "run", "--completion-run-manifest", "manifest.json",
                  "--model-receipt-dir", "models", "--validation-receipt-dir", "owners"]
        for flag in ("--resume", "--pytest-leaf-plan", "--keep-going"):
            with self.subTest(flag=flag), self.assertRaises(SystemExit):
                parser.parse_args(common + [flag])

if __name__ == "__main__":
    unittest.main()
