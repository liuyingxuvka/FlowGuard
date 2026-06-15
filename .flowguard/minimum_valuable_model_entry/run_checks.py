"""Run the minimum valuable model entry self-checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = ("template_search_done", "minimum_model_accepted", "local_candidate_harvested")


def main() -> int:
    report = run_formal_workflow_suite(
        "minimum_valuable_model_entry",
        (
            FormalWorkflowCase("correct_minimum_valuable_model", model.correct_workflow(), True),
            FormalWorkflowCase("broken_without_evidence", model.broken_without_evidence_workflow(), False),
            FormalWorkflowCase("broken_hardcoded_root", model.broken_hardcoded_root_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="minimum_valuable_model_missing_evidence",
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
