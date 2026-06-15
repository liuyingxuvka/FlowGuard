import json
import tempfile
import unittest
from pathlib import Path

from flowguard import audit_flowguard_adoption

ROOT = Path(__file__).resolve().parents[1]


class AdoptionAuditTests(unittest.TestCase):
    def test_stale_fallback_model_is_warning_when_flowguard_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "model.py").write_text(
                "flowguard_package_available = False\n# fallback explorer\n",
                encoding="utf-8",
            )

            report = audit_flowguard_adoption(root, flowguard_available=True)

            self.assertTrue(report.ok)
            self.assertEqual("pass_with_gaps", report.status)
            self.assertIn("stale_fallback_model", [finding.category for finding in report.findings])
            self.assertIn("flowguard_package_available=false", dict(report.findings[0].metadata)["markers"])

    def test_current_fallback_model_is_gap_when_flowguard_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "model.py").write_text(
                "class Explorer:\n    pass\n",
                encoding="utf-8",
            )

            report = audit_flowguard_adoption(root, flowguard_available=False)

            self.assertEqual("pass_with_gaps", report.status)
            self.assertIn("current_fallback_model", [finding.category for finding in report.findings])

    def test_direct_explorer_model_requires_formal_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "model.py").write_text(
                "from flowguard import Explorer, Workflow\n"
                "report = Explorer(Workflow(()), (), ()).explore()\n",
                encoding="utf-8",
            )

            report = audit_flowguard_adoption(root, flowguard_available=True)

            self.assertEqual("pass_with_gaps", report.status)
            self.assertEqual("direct_explorer_formal_entry_required", report.findings[0].category)
            self.assertIn("direct Explorer call", dict(report.findings[0].metadata)["markers"])

    def test_formal_check_plan_with_internal_explorer_reference_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "model.py").write_text(
                "from flowguard import FlowGuardCheckPlan, KnownBadProof, MinimumModelContract, RiskIntent, run_model_first_checks\n"
                "report = run_model_first_checks(FlowGuardCheckPlan(workflow=None, known_bad_proofs=(KnownBadProof('case', protected_error_class='x', method='broken', observed_status='failed'),)))\n",
                encoding="utf-8",
            )

            report = audit_flowguard_adoption(root, flowguard_available=True)

            self.assertEqual("pass", report.status)

    def test_explorer_import_requires_formal_runner_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "model.py").write_text(
                "from flowguard import Explorer, FlowGuardCheckPlan, KnownBadProof, MinimumModelContract, RiskIntent, run_model_first_checks\n"
                "report = run_model_first_checks(FlowGuardCheckPlan(workflow=None, known_bad_proofs=(KnownBadProof('case', protected_error_class='x', method='broken', observed_status='failed'),)))\n",
                encoding="utf-8",
            )

            report = audit_flowguard_adoption(root, flowguard_available=True)

            self.assertEqual("pass_with_gaps", report.status)
            self.assertEqual("direct_explorer_formal_entry_required", report.findings[0].category)
            self.assertIn("Explorer import in current model", dict(report.findings[0].metadata)["markers"])

    def test_historical_fallback_is_suggestion_when_current_models_are_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "model.py").write_text(
                "from flowguard import FlowGuardCheckPlan, KnownBadProof, MinimumModelContract, RiskIntent, run_model_first_checks\n",
                encoding="utf-8",
            )
            (root / ".flowguard" / "adoption_log.jsonl").write_text(
                json.dumps({"findings": ["old fallback was removed"]}) + "\n",
                encoding="utf-8",
            )

            report = audit_flowguard_adoption(root, flowguard_available=True)

            self.assertEqual("pass_with_gaps", report.status)
            self.assertEqual("suggestion", report.findings[0].severity)
            self.assertEqual("historical_fallback_evidence", report.findings[0].category)

    def test_current_project_flowguard_models_have_no_stale_entry_path(self):
        report = audit_flowguard_adoption(ROOT, flowguard_available=True)

        current_stale_categories = {
            "stale_fallback_model",
            "current_fallback_model",
            "direct_explorer_formal_entry_required",
        }
        self.assertFalse(
            current_stale_categories.intersection(finding.category for finding in report.findings),
            report.format_text(),
        )

    def test_missing_flowguard_directory_is_plain_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = audit_flowguard_adoption(tmp, flowguard_available=True)

            self.assertTrue(report.ok)
            self.assertEqual("pass", report.status)
            self.assertEqual([], report.to_dict()["findings"])


if __name__ == "__main__":
    unittest.main()
