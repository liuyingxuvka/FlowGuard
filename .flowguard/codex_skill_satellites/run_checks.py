"""Run the FlowGuard model for the Codex skill satellite upgrade."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
            "topology_prepared",
            "runtime_surfaces_synced",
            "validations_passed",
            "version_surfaces_aligned",
            "release_accepted",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_skill_satellite_release",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.release_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "codex_skill_satellites",
        (
            FormalWorkflowCase("broken_early_release", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="premature_skill_release",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
