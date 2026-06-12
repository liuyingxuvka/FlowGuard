"""Run the template harvest closure self-checks."""

from __future__ import annotations

from flowguard import Explorer
import model


def _run(workflow):
    return Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("minimum_model_accepted", "template_harvest_closed", "model_completion_claimed"),
    ).explore()


def main() -> int:
    correct = _run(model.correct_workflow())
    broken_without_harvest = _run(model.broken_without_harvest_workflow())
    broken_vague_skip = _run(model.broken_vague_skip_workflow())

    print("=== flowguard template harvest closure ===")
    print(f"correct: {'PASS' if correct.ok else 'FAIL'}")
    print(f"broken_without_harvest_rejected: {'PASS' if not broken_without_harvest.ok else 'FAIL'}")
    print(f"broken_vague_skip_rejected: {'PASS' if not broken_vague_skip.ok else 'FAIL'}")
    print()
    print(correct.format_text())
    if broken_without_harvest.ok:
        print("broken_without_harvest unexpectedly passed")
    else:
        print("broken_without_harvest violation observed")
    if broken_vague_skip.ok:
        print("broken_vague_skip unexpectedly passed")
    else:
        print("broken_vague_skip violation observed")
    return 0 if correct.ok and not broken_without_harvest.ok and not broken_vague_skip.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
