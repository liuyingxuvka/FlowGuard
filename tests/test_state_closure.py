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
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    StateClosureDimension,
    StateClosurePlan,
    TemplateHarvestReview,
    TemplateReuseReview,
    Workflow,
    infer_state_closure_plan,
    review_state_closure,
    run_model_first_checks,
)
from flowguard.plan import FlowGuardCheckPlan


ROOT = Path(__file__).resolve().parents[1]


def formal_entry_kwargs():
    return {
        "risk_profile": RiskProfile(
            modeled_boundary="event state closure",
            risk_classes=("side_effect",),
            risk_intent=RiskIntent(
                failure_modes=("unknown event accepted as normal",),
                protected_error_classes=("unsafe_unknown_input",),
                protected_harms=("unexpected input reaches side effects",),
                must_model_state=("status",),
                must_model_side_effects=("event_accept",),
                completion_evidence=("accepted_label",),
                adversarial_inputs=("unknown event status",),
                hard_invariants=("unknowns reject before side effects",),
                known_bad_cases=("unknown_status_accepted",),
                template_no_match_reason="state closure gate owns this local input boundary",
                blindspots=("production adapter replay is outside this unit test",),
            ),
        ),
        "template_reuse_review": TemplateReuseReview(
            no_match_reason="state closure gate owns this local input boundary",
            searched_layers=("public", "local"),
        ),
        "template_harvest_review": TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        "minimum_model_contract": MinimumModelContract(
            protected_error_classes=("unsafe_unknown_input",),
            modeled_state=("status",),
            modeled_side_effects=("event_accept",),
            completion_evidence=("accepted_label",),
            known_bad_cases=("unknown_status_accepted",),
        ),
        "known_bad_proofs": (
            KnownBadProof(
                "unknown_status_accepted",
                protected_error_class="unsafe_unknown_input",
                method="state_closure_review",
                observed_status="failed",
                observed_failure="state closure blocks side effect before unknown resolution",
                evidence_id="state_closure:unknown_status_accepted",
            ),
        ),
    }


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
                **formal_entry_kwargs(),
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
                **formal_entry_kwargs(),
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
        self.assertIn("correct_state_closure_gate: observed=OK expected=OK match=yes", result.stdout)
        self.assertIn("state_closure_missing_generation: observed=VIOLATION expected=VIOLATION", result.stdout)


if __name__ == "__main__":
    unittest.main()
