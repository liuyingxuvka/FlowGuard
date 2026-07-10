"""Run the minimum valuable model entry self-checks."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = ("template_search_done", "minimum_model_accepted", "local_candidate_harvested")


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=tuple(
            request
            for request in model.EXTERNAL_INPUTS
            if request.protected_error_class
            and request.completion_evidence
            and request.known_bad_case
            and request.portable_local_root
        ),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok and len(correct.final_states) == 1
    print(f"correct_minimum_valuable_model: {'exact model pass' if correct_ok else 'failed'}")
    report = run_formal_workflow_suite(
        "minimum_valuable_model_entry",
        (
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
    return 0 if correct_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
