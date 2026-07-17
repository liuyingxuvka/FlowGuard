"""Run the development_process_flow rollout model checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


REQUIRED_LABELS = ("validation_passed", "release_accepted")


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_development_process_flow",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(
            model.LifecycleAction("update_requirement"),
            model.LifecycleAction("update_code"),
            model.LifecycleAction("update_tests"),
            model.LifecycleAction("run_validation"),
            model.LifecycleAction("claim_release"),
        ),
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.release_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "development_process_flow",
        (
            FormalWorkflowCase("broken_reuses_stale_or_progress_evidence", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase(
                "broken_accepts_wrong_plane_action",
                model.build_broken_plane_workflow(),
                False,
                required_labels=("wrong_plane_action_accepted",),
            ),
            FormalWorkflowCase(
                "broken_accepts_checked_tasks_without_post_snapshot",
                model.build_broken_workflow(),
                False,
                required_labels=("validation_passed", "release_accepted"),
                external_inputs=(
                    model.LifecycleAction("run_validation", spec_post_fingerprint=""),
                    model.LifecycleAction("claim_release"),
                ),
                max_sequence_length=2,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="stale_process_evidence",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
