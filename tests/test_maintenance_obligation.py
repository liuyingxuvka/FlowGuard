import os
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

from flowguard import (
    OBLIGATION_STATUS_OBSERVATION,
    OBLIGATION_STATUS_RESOLVED,
    MaintenanceObligation,
    build_maintenance_obligation_report,
)
from flowguard.summary_report import FlowGuardSection, FlowGuardSummaryReport


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    path: str = ""
    description: str = ""


class MaintenanceObligationTests(unittest.TestCase):
    def test_open_obligation_knows_whether_changed_artifact_touches_anchor(self):
        obligation = MaintenanceObligation(
            "structure:checkout",
            owner_route="structure_mesh_maintenance",
            reason_code="large_module",
            artifact_ids=("module:checkout",),
            anchor_paths=("flowguard/checkout.py",),
        )

        self.assertTrue(obligation.is_active())
        self.assertTrue(obligation.is_required())
        self.assertTrue(obligation.has_anchor())
        self.assertTrue(obligation.touches_artifact(Artifact("module:checkout")))
        self.assertTrue(obligation.touches_artifact(Artifact("other", path="src/flowguard/checkout.py")))
        self.assertFalse(obligation.touches_artifact(Artifact("module:billing", path="src/billing.py")))

    def test_observation_is_memory_without_open_route_gate(self):
        obligation = MaintenanceObligation(
            "observation:wide-module",
            owner_route="structure_mesh_maintenance",
            reason_code="wide_module",
            status=OBLIGATION_STATUS_OBSERVATION,
        )

        self.assertFalse(obligation.is_active())
        self.assertFalse(obligation.has_anchor())

    def test_resolved_obligation_needs_evidence_for_broad_confidence(self):
        missing = MaintenanceObligation(
            "structure:resolved",
            owner_route="structure_mesh_maintenance",
            reason_code="large_module",
            status=OBLIGATION_STATUS_RESOLVED,
        )
        resolved = MaintenanceObligation(
            "structure:resolved",
            owner_route="structure_mesh_maintenance",
            reason_code="large_module",
            status=OBLIGATION_STATUS_RESOLVED,
            evidence_ids=("structuremesh:passed",),
        )

        self.assertFalse(missing.has_resolution_evidence())
        self.assertTrue(resolved.has_resolution_evidence())

    def test_summary_report_turns_non_pass_gaps_into_route_owned_obligations(self):
        summary = FlowGuardSummaryReport.from_sections(
            (
                FlowGuardSection("model_check", "failed", "invariant violation"),
                FlowGuardSection("conformance_replay", "not_run", "not feasible"),
            )
        )

        obligations = summary.maintenance_obligations
        self.assertEqual(2, len(obligations.obligations))
        self.assertEqual(("model-check:failure",), obligations.open_required_obligation_ids[:1])
        self.assertIn("maintenance_obligations", summary.format_text())
        obligation_summary = build_maintenance_obligation_report("r", obligations.obligations).summary
        self.assertIn("open=2", obligation_summary)
        self.assertIn("open_required=1", obligation_summary)

    def test_self_model_checks_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, ".flowguard/maintenance_obligation_memory/run_checks.py"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "correct_maintenance_obligation_memory: observed=OK expected=OK match=yes",
            result.stdout,
        )
        self.assertIn("maintenance_obligation_bad_claim: observed=VIOLATION expected=VIOLATION", result.stdout)


if __name__ == "__main__":
    unittest.main()
