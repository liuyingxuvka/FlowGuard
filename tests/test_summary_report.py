import json
import unittest
from dataclasses import dataclass

from flowguard import Workflow
from flowguard.audit import audit_model
from flowguard.report import CheckReport
from flowguard.summary_report import (
    FlowGuardSection,
    FlowGuardSummaryReport,
    build_flowguard_summary_report,
)


class Block:
    name = "Block"
    reads = ()
    writes = ()

    def apply(self, input_obj, state):
        return ()


@dataclass(frozen=True)
class Violation:
    name: str
    message: str


@dataclass(frozen=True)
class GenericReport:
    ok: bool
    summary: str
    violations: tuple[Violation, ...]


class SummaryReportTests(unittest.TestCase):
    def test_not_run_section_creates_pass_with_gaps_not_failure(self):
        report = FlowGuardSummaryReport.from_sections(
            (
                FlowGuardSection("model_check", "pass", "explorer ok"),
                FlowGuardSection("conformance", "not_run", "not feasible"),
            )
        )

        self.assertEqual("pass_with_gaps", report.overall_status)
        self.assertIn("conformance: not_run", report.format_text())

    def test_failed_section_wins_over_gaps(self):
        report = FlowGuardSummaryReport.from_sections(
            (
                FlowGuardSection("model_check", "failed", "invariant violation"),
                FlowGuardSection("conformance", "not_run", "not feasible"),
            )
        )

        self.assertEqual("failed", report.overall_status)
        self.assertEqual("failed", json.loads(report.to_json_text())["overall_status"])

    def test_builder_combines_explorer_pass_with_audit_warnings(self):
        model_report = CheckReport(ok=True, summary="sequences=1 traces=1")
        audit_report = audit_model(
            workflow=Workflow((Block(),)),
            invariants=(),
            external_inputs=("x",),
            max_sequence_length=1,
            declared_risk_classes=("deduplication",),
        )

        summary = build_flowguard_summary_report(
            model_check_report=model_report,
            audit_report=audit_report,
            not_run_sections=("conformance_replay",),
        )

        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertEqual(["model_check", "model_quality_audit", "conformance_replay"], [s.name for s in summary.sections])
        self.assertIn("findings:", summary.format_text())
        self.assertIn("missing_repeated_input", summary.format_text(verbose=True))

    def test_empty_summary_is_not_run(self):
        report = FlowGuardSummaryReport.from_sections(())

        self.assertEqual("not_run", report.overall_status)
        self.assertIn("no sections", report.summary)

    def test_generic_failed_report_preserves_violation_findings(self):
        summary = build_flowguard_summary_report(
            contract_report=GenericReport(
                ok=False,
                summary="contract failed",
                violations=(Violation("forbidden_write", "changed records"),),
            )
        )

        self.assertEqual("failed", summary.overall_status)
        self.assertIn("forbidden_write: changed records", summary.format_text(verbose=True))
        self.assertIn("metadata", json.loads(summary.to_json_text())["sections"][0])


if __name__ == "__main__":
    unittest.main()
