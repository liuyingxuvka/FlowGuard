import unittest
from dataclasses import dataclass, replace

from flowguard import FunctionResult, InvariantResult, Workflow, assumption_card, conditional_assumption
from flowguard.checks import no_duplicate_values
from flowguard.model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    canonical_fingerprint,
)
from flowguard.plan import FlowGuardCheckPlan
from flowguard.risk import RiskIntent, RiskProfile, SkippedCheck
from flowguard.risk_templates import (
    KnownBadProof,
    MinimumModelContract,
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


def _fingerprint(value: str) -> str:
    return canonical_fingerprint({"value": value})


def path_quality_pair() -> tuple[PathQualitySubject, PathQualityResult]:
    subject = PathQualitySubject(
        model_id="recording",
        boundary_id="workflow:recording",
        model_fingerprint=_fingerprint("recording-model"),
        normalized_facts_fingerprint=_fingerprint("recording-facts"),
        retained_element_inventory_fingerprint=_fingerprint("recording-retained"),
        purpose_fingerprint=_fingerprint("recording-purpose"),
        intent_fingerprint=_fingerprint("recording-intent"),
        obligation_fingerprint=_fingerprint("recording-obligations"),
        provider_fingerprint=_fingerprint("recording-provider"),
        dependency_fingerprint=_fingerprint("recording-dependencies"),
        code_fingerprint=_fingerprint("recording-code"),
        test_fingerprint=_fingerprint("recording-tests"),
        oracle_fingerprint=_fingerprint("recording-oracles"),
        evidence_fingerprint=_fingerprint("recording-evidence"),
        currentness_id="revision:recording:1",
    )
    result = PathQualityResult(
        result_id="path-quality:recording:current",
        subject_fingerprint=subject.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=_fingerprint("recording-witnesses"),
        detail_evidence_fingerprint=_fingerprint("recording-path-quality-detail"),
        producer_id="model_maturation",
        currentness_id=subject.currentness_id,
    )
    return subject, result


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
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
            scenario_matrix_config={"max_scenarios": 4},
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertEqual("pass_with_gaps", summary.overall_status)
        self.assertNotIn("template_reuse_review", sections)
        self.assertNotIn("template_harvest_review", sections)
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

    def test_run_model_first_checks_does_not_add_template_gates(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            risk_profile=formal_risk_profile(),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
        )

        summary = run_model_first_checks(plan)
        sections = {section.name: section for section in summary.sections}

        self.assertNotIn("template_reuse_review", sections)
        self.assertNotIn("template_harvest_review", sections)
        self.assertNotIn("model_path_quality", sections)
        self.assertEqual("pass", sections["minimum_model_review"].status)

    def test_run_model_first_checks_consumes_only_current_compact_path_quality(self):
        subject, result = path_quality_pair()
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            risk_profile=formal_risk_profile(),
            minimum_model_contract=formal_minimum_contract(),
            known_bad_proofs=(formal_known_bad_proof(),),
            path_quality_subject=subject.to_dict(),
            path_quality_result=result.to_compact_dict(),
        )

        summary = run_model_first_checks(plan)
        section = {item.name: item for item in summary.sections}["model_path_quality"]
        compact = dict(summary.metadata)["model_path_quality_result"]

        self.assertEqual("pass", section.status)
        self.assertEqual(result.to_compact_dict(), compact)
        self.assertEqual(result.to_compact_dict(), plan.to_dict()["path_quality_result"])
        self.assertNotIn("candidates", compact)
        self.assertNotIn("necessity_witnesses", compact)
        self.assertIn("subject=provided result=provided", plan.format_text())

        stale_plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            path_quality_subject=subject,
            path_quality_result=replace(result, currentness_id="revision:recording:old"),
        )
        stale_summary = run_model_first_checks(stale_plan)
        stale_section = {
            item.name: item for item in stale_summary.sections
        }["model_path_quality"]
        self.assertEqual("blocked", stale_section.status)
        self.assertIn("path_quality_result_currentness_mismatch", stale_section.findings)

    def test_run_model_first_checks_propagates_assumption_card_to_model_report(self):
        card = make_runner_assumption_card()
        plan = FlowGuardCheckPlan(
            workflow=Workflow((IdempotentRecord(),), name="recording"),
            initial_states=(State(),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            assumption_card=card,
            risk_profile=formal_risk_profile(),
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
