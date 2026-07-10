import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.formal_runner import (
    FormalWorkflowCase,
    run_exact_workflow_case,
    run_formal_workflow_suite,
)
from flowguard.formal_runner import _summary_observed_ok
from flowguard.summary_report import FlowGuardSection, FlowGuardSummaryReport


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


class RecordOnce:
    name = "RecordOnce"
    reads = ("records",)
    writes = ("records",)
    accepted_input_type = str
    input_description = "record key"
    output_description = "recorded or rejected duplicate"
    idempotency = "same key is recorded once"

    def apply(self, input_obj, state):
        if input_obj in state.records:
            return (FunctionResult("duplicate", state, label="duplicate_rejected"),)
        return (FunctionResult("recorded", State(state.records + (input_obj,)), label="recorded"),)


class RecordDuplicate(RecordOnce):
    name = "RecordDuplicate"
    idempotency = "broken variant records duplicates"

    def apply(self, input_obj, state):
        return (FunctionResult("recorded", State(state.records + (input_obj,)), label="recorded"),)


def no_duplicates(state, _trace):
    if len(state.records) != len(set(state.records)):
        return InvariantResult.fail("duplicate records")
    return InvariantResult.pass_()


INVARIANTS = (Invariant("no_duplicates", "records are unique", no_duplicates),)


class FormalRunnerTests(unittest.TestCase):
    def test_exact_workflow_case_requires_declared_terminal_state(self):
        accepted = run_exact_workflow_case(
            "accepted",
            workflow=Workflow((RecordOnce(),)),
            initial_state=State(),
            external_input_sequence=("record",),
            invariants=(),
            final_state_predicate=lambda state: state.records == ("record",),
            print_report=False,
        )
        rejected = run_exact_workflow_case(
            "rejected",
            workflow=Workflow((RecordOnce(),)),
            initial_state=State(),
            external_input_sequence=("record",),
            invariants=(),
            final_state_predicate=lambda state: False,
            print_report=False,
        )

        self.assertTrue(accepted)
        self.assertFalse(rejected)

    def test_default_success_requires_exact_pass_not_pass_with_gaps(self):
        summary = FlowGuardSummaryReport(
            "pass_with_gaps",
            (
                FlowGuardSection("model_check", "pass"),
                FlowGuardSection("minimum_model_review", "pass"),
                FlowGuardSection("known_bad_proof", "pass"),
                FlowGuardSection("template_harvest_review", "pass_with_gaps"),
            ),
        )
        self.assertFalse(_summary_observed_ok(summary))
        self.assertTrue(_summary_observed_ok(summary, ("pass", "pass_with_gaps")))

    def test_scoped_status_must_be_explicit_on_case(self):
        strict = FormalWorkflowCase("strict", Workflow((RecordOnce(),)), True)
        scoped = FormalWorkflowCase(
            "scoped",
            Workflow((RecordOnce(),)),
            True,
            allowed_success_statuses=("pass", "pass_with_gaps"),
        )
        self.assertEqual(("pass",), strict.allowed_success_statuses)
        self.assertEqual(("pass", "pass_with_gaps"), scoped.allowed_success_statuses)

    def test_suite_proves_expected_bad_workflow_before_correct_claim(self):
        report = run_formal_workflow_suite(
            "record-once",
            (
                FormalWorkflowCase(
                    "correct_record_once",
                    Workflow((RecordOnce(),), name="record_once"),
                    True,
                    required_labels=("recorded", "duplicate_rejected"),
                    allowed_success_statuses=("pass", "pass_with_gaps"),
                ),
                FormalWorkflowCase(
                    "broken_records_duplicate",
                    Workflow((RecordDuplicate(),), name="record_duplicate"),
                    False,
                    required_labels=("recorded",),
                    protected_error_class="duplicate_record",
                ),
            ),
            initial_states=(State(),),
            external_inputs=("a",),
            invariants=INVARIANTS,
            max_sequence_length=2,
            protected_error_class="duplicate_record",
            print_reports=False,
        )

        self.assertTrue(report.ok, report.format_text(verbose=True))
        self.assertEqual(
            ("correct_record_once_duplicate_rejected", "broken_records_duplicate"),
            tuple(proof.case_id for proof in report.known_bad_proofs),
        )
        self.assertEqual(
            ("rejected", "failed"),
            tuple(proof.observed_status for proof in report.known_bad_proofs),
        )

    def test_suite_fails_when_expected_bad_workflow_is_not_caught(self):
        report = run_formal_workflow_suite(
            "record-once",
            (
                FormalWorkflowCase(
                    "correct_record_once",
                    Workflow((RecordOnce(),), name="record_once"),
                    True,
                    required_labels=("recorded", "duplicate_rejected"),
                ),
                FormalWorkflowCase(
                    "bad_case_that_is_actually_correct",
                    Workflow((RecordOnce(),), name="record_once"),
                    False,
                    required_labels=("recorded",),
                    protected_error_class="duplicate_record",
                ),
            ),
            initial_states=(State(),),
            external_inputs=("a",),
            invariants=INVARIANTS,
            max_sequence_length=2,
            protected_error_class="duplicate_record",
            print_reports=False,
        )

        self.assertFalse(report.ok)
        self.assertIn("expected_bad_case_not_caught", report.findings[0])
        statuses = {proof.case_id: proof.observed_status for proof in report.known_bad_proofs}
        self.assertEqual("passed", statuses["bad_case_that_is_actually_correct"])


if __name__ == "__main__":
    unittest.main()
