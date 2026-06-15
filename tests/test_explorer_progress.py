import io
import os
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from unittest.mock import patch

from flowguard import (
    FlowGuardCheckPlan,
    FunctionResult,
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    TemplateHarvestReview,
    TemplateReuseReview,
    Workflow,
    run_model_first_checks,
)
from flowguard.explorer import Explorer


@dataclass(frozen=True)
class State:
    seen: tuple[str, ...] = ()


class RecordInput:
    name = "RecordInput"

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                output=input_obj,
                new_state=State(state.seen + (input_obj,)),
                label="recorded",
            ),
        )


def run_with_captured_streams(explorer):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch.dict(os.environ, {"FLOWGUARD_PROGRESS": "1"}), redirect_stdout(stdout), redirect_stderr(stderr):
        report = explorer.explore()
    return report, stdout.getvalue(), stderr.getvalue()


def formal_entry_kwargs():
    return {
        "risk_profile": RiskProfile(
            modeled_boundary="recording progress",
            risk_classes=("side_effect",),
            risk_intent=RiskIntent(
                failure_modes=("recording reports complete without evidence",),
                protected_error_classes=("missing_record_evidence",),
                protected_harms=("caller trusts an unrecorded input",),
                must_model_state=("seen",),
                must_model_side_effects=("record_write",),
                completion_evidence=("recorded_label",),
                adversarial_inputs=("single input record",),
                hard_invariants=("recorded input is visible in state",),
                known_bad_cases=("record_without_seen_state",),
                template_no_match_reason="progress test uses a local recording model",
                blindspots=("this test checks progress output, not production replay",),
            ),
        ),
        "template_reuse_review": TemplateReuseReview(
            no_match_reason="progress test uses a local recording model",
            searched_layers=("public", "local"),
        ),
        "template_harvest_review": TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        "minimum_model_contract": MinimumModelContract(
            protected_error_classes=("missing_record_evidence",),
            modeled_state=("seen",),
            modeled_side_effects=("record_write",),
            completion_evidence=("recorded_label",),
            known_bad_cases=("record_without_seen_state",),
        ),
        "known_bad_proofs": (
            KnownBadProof(
                "record_without_seen_state",
                protected_error_class="missing_record_evidence",
                method="broken_workflow",
                observed_status="failed",
                observed_failure="recorded label without state evidence rejected",
                evidence_id="model:record_without_seen_state",
            ),
        ),
    }


class ExplorerProgressTests(unittest.TestCase):
    def make_explorer(self, *, progress_steps=10, external_inputs=("a", "b", "c"), max_sequence_length=2):
        return Explorer(
            workflow=Workflow((RecordInput(),), name="recording"),
            initial_states=(State(),),
            external_inputs=external_inputs,
            max_sequence_length=max_sequence_length,
            progress_steps=progress_steps,
        )

    def test_default_progress_emits_start_and_ten_buckets_to_stderr(self):
        report, stdout, stderr = run_with_captured_streams(self.make_explorer())

        self.assertTrue(report.ok)
        self.assertEqual("", stdout)
        self.assertEqual("sequences=12 initial_states=1 traces=21", report.summary)

        lines = [line for line in stderr.splitlines() if line]
        progress_lines = [line for line in lines if "[flowguard] progress" in line]

        self.assertEqual("[flowguard] start phase=explore work_total=12 progress_steps=10", lines[0])
        self.assertEqual(10, len(progress_lines))
        self.assertIn("progress 10% work=2/12", progress_lines[0])
        self.assertIn("progress 100% work=12/12", progress_lines[-1])
        self.assertTrue(all("traces=" in line and "violations=" in line for line in progress_lines))
        self.assertEqual(
            [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            [int(re.search(r"progress (\d+)%", line).group(1)) for line in progress_lines],
        )

    def test_progress_steps_zero_disables_output(self):
        report, stdout, stderr = run_with_captured_streams(self.make_explorer(progress_steps=0))

        self.assertTrue(report.ok)
        self.assertEqual("", stdout)
        self.assertEqual("", stderr)

    def test_environment_zero_disables_output(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict(os.environ, {"FLOWGUARD_PROGRESS": "0"}), redirect_stdout(stdout), redirect_stderr(stderr):
            report = self.make_explorer().explore()

        self.assertTrue(report.ok)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_small_total_reaches_one_hundred_percent(self):
        report, stdout, stderr = run_with_captured_streams(
            self.make_explorer(external_inputs=("a",), max_sequence_length=1)
        )

        self.assertTrue(report.ok)
        self.assertEqual("", stdout)
        progress_lines = [line for line in stderr.splitlines() if "[flowguard] progress" in line]
        self.assertEqual(1, len(progress_lines))
        self.assertIn("progress 100% work=1/1", progress_lines[0])

    def test_runner_inherits_explorer_progress(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((RecordInput(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("a",),
            max_sequence_length=1,
            **formal_entry_kwargs(),
        )
        stderr = io.StringIO()
        with patch.dict(os.environ, {"FLOWGUARD_PROGRESS": "1"}), redirect_stderr(stderr):
            summary = run_model_first_checks(plan)

        self.assertIn("model_check", {section.name for section in summary.sections})
        self.assertIn("[flowguard] start phase=explore work_total=1 progress_steps=10", stderr.getvalue())
        self.assertIn("[flowguard] progress 100% work=1/1", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
