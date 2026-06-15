"""Run the FlowGuard model for the Codex skill satellite upgrade."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
            "topology_prepared",
            "runtime_surfaces_synced",
            "validations_passed",
            "version_surfaces_aligned",
            "release_accepted",
)


def main() -> int:
    report = run_formal_workflow_suite(
        "codex_skill_satellites",
        (
            FormalWorkflowCase("correct_skill_satellite_release", model.build_correct_workflow(), True, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase("broken_early_release", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="premature_skill_release",
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
