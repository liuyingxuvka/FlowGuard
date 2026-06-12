"""Run the minimum valuable model entry self-checks."""

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
        required_labels=("template_search_done", "minimum_model_accepted", "local_candidate_harvested"),
    ).explore()


def main() -> int:
    correct = _run(model.correct_workflow())
    broken_without_evidence = _run(model.broken_without_evidence_workflow())
    broken_hardcoded_root = _run(model.broken_hardcoded_root_workflow())

    print("=== flowguard minimum valuable model entry ===")
    print(f"correct: {'PASS' if correct.ok else 'FAIL'}")
    print(f"broken_without_evidence_rejected: {'PASS' if not broken_without_evidence.ok else 'FAIL'}")
    print(f"broken_hardcoded_root_rejected: {'PASS' if not broken_hardcoded_root.ok else 'FAIL'}")
    print()
    print(correct.format_text())
    if broken_without_evidence.ok:
        print("broken_without_evidence unexpectedly passed")
    else:
        print("broken_without_evidence violation observed")
    if broken_hardcoded_root.ok:
        print("broken_hardcoded_root unexpectedly passed")
    else:
        print("broken_hardcoded_root violation observed")
    return 0 if correct.ok and not broken_without_evidence.ok and not broken_hardcoded_root.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
