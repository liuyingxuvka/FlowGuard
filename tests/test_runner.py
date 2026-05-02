import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, InvariantResult, Workflow, assumption_card, conditional_assumption
from flowguard.checks import no_duplicate_values
from flowguard.plan import FlowGuardCheckPlan
from flowguard.risk import RiskProfile, SkippedCheck
from flowguard.runner import run_model_first_checks


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


class IdempotentRecord:
    name = "IdempotentRecord"
    reads = ("records",)
    writes = ("records",)

    def apply(self, input_obj, state):
        if input_obj in state.records:
            return (FunctionResult(input_obj, state, label="already_recorded"),)
        return (
            FunctionResult(
                input_obj,
                State(state.records + (input_obj,)),
                label="record_added",
            ),
        )


class BrokenRecord:
    name = "BrokenRecord"
    reads = ("records",)
    writes = ("records",)

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                input_obj,
                State(state.records + (input_obj,)),
                label="record_added",
            ),
        )


def make_runner_assumption_card():
    return assumption_card(
        (
            conditional_assumption(
                "same_initial_inputs",
                "The abstract initial state and external input set are fixed for this comparison.",
                boundary="uncontrolled caller-provided model inputs",
                preconditions=("initial states are unchanged", "external inputs are unchanged"),
                why_not_modeled=(
                    "This card documents the caller boundary; the workflow model already explores "
                    "the provided finite inputs but cannot prove the caller did not change them."
                ),
                rationale="The helper runner cannot infer whether callers changed their model inputs.",
                invalidated_by=("initial states change", "external inputs change"),
                checks=("compare initial state reprs", "compare external input reprs"),
            ),
        ),
        checked_scope="runner metadata propagation",
    )


class RunnerTests(unittest.TestCase):
    def test_run_model_first_checks_auto_generates_scenarios_for_risk_profile(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1", "job_2"),
            invariants=(
                no_duplicate_values(
                    "no_duplicate_records",
                    "records are unique",
                    lambda state: state.records,
                    "record",
                ),
            ),
            max_sequence_length=2,
            risk_profile=RiskProfile(
                modeled_boundary="recording",
                risk_classes=("deduplication",),
                skipped_checks=(SkippedCheck("conformance_replay", "no production adapter yet"),),
            ),
            scenario_matrix_config={"max_scenarios": 4},
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertEqual("pass", sections["model_check"].status)
        self.assertEqual("pass_with_gaps", sections["scenario_matrix"].status)
        self.assertIn("auto-generated", sections["scenario_matrix"].summary)
        self.assertIn("input-shape coverage only", sections["scenario_matrix"].summary)
        self.assertTrue(
            any("needs_human_review" in finding for finding in sections["scenario_matrix"].findings)
        )
        self.assertIn("auto_generated=true", sections["scenario_review"].summary)
        self.assertIn("needs_domain_expectations=true", sections["scenario_review"].summary)
        self.assertEqual("not_run", sections["conformance_replay"].status)
        self.assertIn("model_check_report", dict(summary.metadata))

    def test_run_model_first_checks_fails_on_explorer_violation_and_minimizes(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((BrokenRecord(),), name="broken_recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            invariants=(
                no_duplicate_values(
                    "no_duplicate_records",
                    "records are unique",
                    lambda state: state.records,
                    "record",
                ),
            ),
            max_sequence_length=2,
            risk_profile={"modeled_boundary": "broken recording", "risk_classes": ("deduplication",)},
            scenario_matrix_config={"enabled": False},
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("failed", summary.overall_status)
        self.assertEqual("failed", sections["model_check"].status)
        self.assertEqual("pass", sections["counterexample_minimization"].status)
        self.assertIn("no_reduction_found", sections["counterexample_minimization"].summary)
        minimization = dict(summary.metadata)["counterexample_minimization"]
        self.assertEqual(("job_1", "job_1"), minimization.original_sequence)

    def test_run_model_first_checks_records_skipped_conformance_without_failure(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            risk_profile=RiskProfile(
                modeled_boundary="recording",
                risk_classes=("conformance",),
                confidence_goal="production_conformance",
            ),
            conformance_status="skipped_with_reason",
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertEqual("skipped_with_reason", sections["conformance_replay"].status)
        self.assertTrue(
            any("production confidence goal" in finding for finding in sections["model_quality_audit"].findings)
        )

    def test_run_model_first_checks_propagates_assumption_card_to_model_report(self):
        card = make_runner_assumption_card()
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            assumption_card=card,
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}
        metadata = dict(summary.metadata)
        model_report = metadata["model_check_report"]

        rendered_summary = summary.format_text()
        self.assertTrue(model_report.ok, model_report.format_text())
        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertIn("assumption_card", sections)
        self.assertIs(card, metadata["assumption_card"])
        self.assertIs(card, model_report.assumption_card)
        self.assertIn("assumption_card: provided", plan.format_text())
        self.assertIn("same_initial_inputs", rendered_summary)
        self.assertIn("why_not_modeled", rendered_summary)
        self.assertEqual(
            "same_initial_inputs",
            plan.to_dict()["assumption_card"]["assumptions"][0]["name"],
        )


if __name__ == "__main__":
    unittest.main()
