import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

from flowguard import (
    STATE_CLOSURE_CONFIDENCE_BLOCKED,
    STATE_CLOSURE_CONFIDENCE_FULL,
    STATE_CLOSURE_CONFIDENCE_SCOPED,
    STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
    STATE_CLOSURE_DIMENSION_INPUT_FIELD,
    STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
    STATE_CLOSURE_HANDLING_REJECT,
    STATE_CLOSURE_POLICY_OPEN,
    FunctionResult,
    StateClosureDimension,
    StateClosurePlan,
    Workflow,
    infer_state_closure_plan,
    review_state_closure,
    run_model_first_checks,
)
from flowguard.plan import FlowGuardCheckPlan


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Event:
    status: str


@dataclass(frozen=True)
class State:
    phase: str = "idle"


class AcceptEvent:
    name = "AcceptEvent"
    reads = ("phase",)
    writes = ("phase",)

    def apply(self, input_obj, state):
        return (FunctionResult(input_obj, State("seen"), label="accepted"),)


class StateClosureTests(unittest.TestCase):
    def test_inference_generates_unknown_cases_for_external_and_status_fields(self):
        plan = infer_state_closure_plan(
            workflow=Workflow((AcceptEvent(),), name="events"),
            initial_states=(State("idle"),),
            external_inputs=(Event("known"),),
        )
        report = review_state_closure(plan)

        self.assertTrue(report.ok)
        self.assertEqual(STATE_CLOSURE_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("external_input", {dimension.dimension_id for dimension in plan.dimensions})
        self.assertIn("input.status", {dimension.dimension_id for dimension in plan.dimensions})
        self.assertIn("state.phase", {dimension.dimension_id for dimension in plan.dimensions})
        self.assertTrue(report.generated_cases)
        self.assertIn(
            "state_closure_policy_missing",
            {finding.code for finding in report.findings},
        )

    def test_explicit_open_boundary_with_safe_handling_passes(self):
        report = review_state_closure(
            StateClosurePlan(
                "safe",
                dimensions=(
                    StateClosureDimension(
                        "external_input",
                        STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
                        policy=STATE_CLOSURE_POLICY_OPEN,
                        known_values=("known",),
                        representative_unknowns=("other",),
                        handling=STATE_CLOSURE_HANDLING_REJECT,
                    ),
                    StateClosureDimension(
                        "input.status",
                        STATE_CLOSURE_DIMENSION_INPUT_FIELD,
                        policy=STATE_CLOSURE_POLICY_OPEN,
                        known_values=("known",),
                        representative_unknowns=("cancelled",),
                        handling=STATE_CLOSURE_HANDLING_REJECT,
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(STATE_CLOSURE_CONFIDENCE_FULL, report.confidence)

    def test_unsafe_or_side_effect_unknown_handling_blocks(self):
        report = review_state_closure(
            StateClosurePlan(
                "unsafe",
                dimensions=(
                    StateClosureDimension(
                        "external_input",
                        STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
                        policy=STATE_CLOSURE_POLICY_OPEN,
                        known_values=("known",),
                        representative_unknowns=("other",),
                        handling=STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
                    ),
                    StateClosureDimension(
                        "input.status",
                        STATE_CLOSURE_DIMENSION_INPUT_FIELD,
                        policy=STATE_CLOSURE_POLICY_OPEN,
                        known_values=("known",),
                        representative_unknowns=("bad",),
                        handling=STATE_CLOSURE_HANDLING_REJECT,
                        side_effects_before_resolution=True,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(STATE_CLOSURE_CONFIDENCE_BLOCKED, report.confidence)
        self.assertIn(
            "state_closure_side_effect_before_resolution",
            {finding.code for finding in report.findings},
        )

    def test_runner_adds_state_closure_section_automatically(self):
        summary = run_model_first_checks(
            FlowGuardCheckPlan(
                workflow=Workflow((AcceptEvent(),), name="events"),
                initial_states=(State("idle"),),
                external_inputs=(Event("known"),),
                max_sequence_length=1,
            )
        )
        sections = {section.name: section for section in summary.sections}
        metadata = dict(summary.metadata)

        self.assertIn("state_closure", sections)
        self.assertEqual("pass_with_gaps", sections["state_closure"].status)
        self.assertIn("state_closure_report", metadata)
        self.assertTrue(metadata["state_closure_report"].generated_cases)

    def test_runner_respects_explicit_safe_state_closure_plan(self):
        closure_plan = StateClosurePlan(
            "safe-runner",
            dimensions=(
                StateClosureDimension(
                    "external_input",
                    STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
                    policy=STATE_CLOSURE_POLICY_OPEN,
                    known_values=("known",),
                    representative_unknowns=("other",),
                    handling=STATE_CLOSURE_HANDLING_REJECT,
                ),
            ),
        )
        summary = run_model_first_checks(
            FlowGuardCheckPlan(
                workflow=Workflow((AcceptEvent(),), name="events"),
                initial_states=(State("idle"),),
                external_inputs=(Event("known"),),
                max_sequence_length=1,
                state_closure_plan=closure_plan,
            )
        )
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("pass", sections["state_closure"].status)
        self.assertIn("state_closure_plan: provided", dict(summary.metadata)["plan"].format_text())

    def test_self_model_checks_pass(self):
        result = subprocess.run(
            [sys.executable, ".flowguard/state_closure_gate/run_checks.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("correct_state_closure_gate: OK", result.stdout)
        self.assertIn("state_closure_missing_generation: VIOLATION", result.stdout)


if __name__ == "__main__":
    unittest.main()
