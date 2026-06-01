"""Run FlowGuard checks for AI-facing field prompt reduction."""

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
            "fields_grouped",
            "tests_added",
            "focused_validation_passed",
            "broad_regression_complete",
            "local_surfaces_synced",
            "done_accepted",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


def main() -> int:
    checks = (
        run_workflow("correct_field_prompt_reduction", model.build_correct_workflow(), expect_ok=True),
        run_workflow("broken_drops_required_evidence", model.build_broken_evidence_workflow(), expect_ok=False),
        run_workflow("broken_prompt_only_completion", model.build_broken_prompt_only_workflow(), expect_ok=False),
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
