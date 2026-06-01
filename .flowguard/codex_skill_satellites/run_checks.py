"""Run the FlowGuard model for the Codex skill satellite upgrade."""

from __future__ import annotations

from flowguard import Explorer
import model


def run_workflow(name: str, workflow, *, expect_ok: bool) -> bool:
    report = Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "topology_prepared",
            "runtime_surfaces_synced",
            "validations_passed",
            "version_surfaces_aligned",
            "release_accepted",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    return ok is expect_ok


def main() -> int:
    checks = (
        run_workflow("correct_skill_satellite_release", model.build_correct_workflow(), expect_ok=True),
        run_workflow("broken_early_release", model.build_broken_workflow(), expect_ok=False),
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
