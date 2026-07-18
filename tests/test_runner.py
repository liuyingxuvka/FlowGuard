import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, InvariantResult, Workflow, assumption_card, conditional_assumption
from flowguard.checks import no_duplicate_values
from flowguard.plan import FlowGuardCheckPlan
from flowguard.risk import RiskIntent, RiskProfile, SkippedCheck
from flowguard.risk_templates import (
    KnownBadProof,
    MinimumModelContract,
    TemplateHarvestReview,
    TemplateReuseReview,
)
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


def formal_risk_profile(*, confidence_goal="model_level", risk_classes=("deduplication",), skipped_checks=()):
    return RiskProfile(
        modeled_boundary="recording",
        risk_classes=risk_classes,
        risk_intent=RiskIntent(
            failure_modes=("retry creates duplicate record",),
            protected_error_classes=("duplicate_side_effect",),
            protected_harms=("downstream workflow sees the same job twice",),
            must_model_state=("records",),
            must_model_side_effects=("record_write",),
            completion_evidence=("record_added_label",),
            adversarial_inputs=("same job repeated",),
            hard_invariants=("records are unique",),
            known_bad_cases=("retry_adds_duplicate_record",),
            used_template_ids=("side_effect_at_most_once",),
            blindspots=("production storage replay is checked separately",),
        ),
        confidence_goal=confidence_goal,
        skipped_checks=skipped_checks,
    )


def formal_minimum_contract():
    return MinimumModelContract(
        protected_error_classes=("duplicate_side_effect",),
        modeled_state=("records",),
        modeled_side_effects=("record_write",),
        completion_evidence=("record_added_label",),
        known_bad_cases=("retry_adds_duplicate_record",),
    )


def formal_template_reuse():
    return TemplateReuseReview(
        used_template_ids=("side_effect_at_most_once",),
        searched_layers=("public", "local"),
    )


def formal_known_bad_proof(**kwargs):
    values = {
        "case_id": "retry_adds_duplicate_record",
        "protected_error_class": "duplicate_side_effect",
        "method": "broken_workflow",
        "expected_failure": "failed",
        "observed_status": "failed",
        "observed_failure": "no_duplicate_records invariant failed",
        "evidence_id": "model:retry_adds_duplicate_record",
    }
    values.update(kwargs)
    return KnownBadProof(**values)


def formal_template_harvest(**kwargs):
    values = {
        "disposition": "duplicate_linked",
        "linked_template_ids": ("side_effect_at_most_once",),
    }
    values.update(kwargs)
    return TemplateHarvestReview(**values)


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
            risk_profile=formal_risk_profile(
                skipped_checks=(SkippedCheck("conformance_replay", "no production adapter yet"),),
            ),
            template_reuse_review=formal_template_reuse(),
            template_harvest_review=formal_template_harvest(),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
            scenario_matrix_config={"max_scenarios": 4},
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertEqual("pass", sections["template_harvest_review"].status)
        self.assertEqual("pass", sections["model_check"].status)
        self.assertEqual("pass_with_gaps", sections["scenario_matrix"].status)
        self.assertIn("auto-generated", sections["scenario_matrix"].summary)
        self.assertIn("input-shape coverage only", sections["scenario_matrix"].summary)
        self.assertEqual("pass_with_gaps", sections["model_derived_challenges"].status)
        self.assertIn("model-derived challenge scenarios", sections["model_derived_challenges"].summary)
        self.assertTrue(
            any("needs_human_review" in finding for finding in sections["scenario_matrix"].findings)
        )
        self.assertIn("auto_generated=true", sections["scenario_review"].summary)
        self.assertIn("needs_domain_expectations=true", sections["scenario_review"].summary)
        self.assertEqual("not_run", sections["conformance_replay"].status)
        self.assertIn("model_check_report", dict(summary.metadata))
        self.assertIn("model_derived_challenge_scenarios", dict(summary.metadata))

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
            risk_profile=formal_risk_profile(),
            template_reuse_review=formal_template_reuse(),
            template_harvest_review=formal_template_harvest(),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
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
            risk_profile=formal_risk_profile(
                confidence_goal="production_conformance",
                risk_classes=("conformance",),
            ),
            template_reuse_review=formal_template_reuse(),
            template_harvest_review=formal_template_harvest(
                disposition="not_harvestable",
                linked_template_ids=(),
                not_harvestable_reason="no_new_pattern",
            ),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
            conformance_status="skipped_with_reason",
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertEqual("skipped_with_reason", sections["conformance_replay"].status)
        self.assertTrue(
            any("production confidence goal" in finding for finding in sections["model_quality_audit"].findings)
        )
        ledger = summary.finding_ledger
        self.assertTrue(ledger.entries)
        self.assertIn("conformance_gap", {entry.category for entry in ledger.entries})
        self.assertIn("finding_ledger", summary.to_dict())

    def test_status_only_passing_conformance_is_blocked(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            risk_profile=formal_risk_profile(
                confidence_goal="production_conformance",
                risk_classes=("conformance",),
            ),
            template_reuse_review=formal_template_reuse(),
            template_harvest_review=formal_template_harvest(
                disposition="not_harvestable",
                linked_template_ids=(),
                not_harvestable_reason="no_new_pattern",
            ),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
            conformance_status="pass",
        )

        summary = run_model_first_checks(plan)
        section = {
            item.name: item for item in summary.sections
        }["conformance_replay"]

        self.assertEqual("blocked", summary.overall_status)
        self.assertEqual("blocked", section.status)
        self.assertIn("current ConformanceReport required", section.summary)

    def test_run_model_first_checks_blocks_missing_template_harvest_closure(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            risk_profile=formal_risk_profile(),
            template_reuse_review=formal_template_reuse(),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("blocked", summary.overall_status)
        self.assertEqual("blocked", sections["template_harvest_review"].status)
        self.assertIn("missing_template_harvest_review", sections["template_harvest_review"].findings)

    def test_run_model_first_checks_propagates_assumption_card_to_model_report(self):
        card = make_runner_assumption_card()
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            assumption_card=card,
            risk_profile=formal_risk_profile(),
            template_reuse_review=formal_template_reuse(),
            template_harvest_review=formal_template_harvest(),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
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
