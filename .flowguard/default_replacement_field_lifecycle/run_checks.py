"""Run FlowGuard checks for default replacement and field lifecycle closure."""

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
            "fields_accounted",
            "field_projection_and_disposition_done",
            "model_code_test_and_bug_repair_done",
            "freshness_and_closure_current",
            "claim_full",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


def main() -> int:
    results = [
        run_workflow(
            "correct_default_replacement_field_lifecycle",
            model.build_correct_workflow(),
            expect_ok=True,
        )
    ]
    for workflow in model.build_broken_workflows():
        results.append(
            run_workflow(
                workflow.name,
                workflow,
                expect_ok=False,
            )
        )
    ok = all(results)
    if ok:
        print("default replacement field lifecycle model checks passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
