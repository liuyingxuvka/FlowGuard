from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from flowguard.__main__ import main
from flowguard.development_process_simulator import (
    DevelopmentProcessSimulationRequest,
    review_development_process_simulator,
)


class ModelSimulatorCommandTests(unittest.TestCase):
    @property
    def repository(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def invoke(self, *arguments: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["simulator", "--root", str(self.repository), *arguments, "--json"])
        return exit_code, json.loads(stdout.getvalue())

    def assert_retired_operation(
        self, exit_code: int, payload: dict[str, object], operation: str
    ) -> None:
        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(f"unknown operation: {operation}", payload["error"])
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def test_list_audits_one_canonical_manifest(self) -> None:
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                request_id="current-readiness",
                validation_freshness_risk=True,
            )
        )
        self.assertEqual("pass", report.status)
        self.assertEqual(("execution_freshness",), report.selected_modes)
        exit_code, payload = self.invoke("--list")
        self.assert_retired_operation(exit_code, payload, "simulator")

    def test_execution_scope_is_required(self) -> None:
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(request_id="missing-scope")
        )
        self.assertEqual("needs_revision", report.status)
        self.assertIn(
            "no_development_process_mode_selected",
            {finding.code for finding in report.findings},
        )
        exit_code, payload = self.invoke()
        self.assert_retired_operation(exit_code, payload, "simulator")

    def test_unmatched_selector_is_not_empty_success(self) -> None:
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                request_id="invalid-optimization",
                process_optimization_reasons=("unknown-reason",),
            )
        )
        self.assertEqual("blocked", report.status)
        self.assertIn(
            "process_optimization_reason_invalid",
            {finding.code for finding in report.findings},
        )
        exit_code, payload = self.invoke("--model", "does-not-exist")
        self.assert_retired_operation(exit_code, payload, "simulator")

    def test_selected_model_runs_through_native_runner_with_bounded_evidence(self) -> None:
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                request_id="current-implementation",
                implementation_work=True,
                final_claim_requested=True,
                execution_freshness_evidence_ids=("evidence:current",),
            )
        )
        self.assertEqual("pass", report.status)
        self.assertTrue(report.ok)
        self.assertEqual(("execution_freshness",), report.selected_modes)
        exit_code, payload = self.invoke(
            "--model",
            "architecture_reduction",
            "--tier",
            "focused",
        )
        self.assert_retired_operation(exit_code, payload, "simulator")


if __name__ == "__main__":
    unittest.main()
