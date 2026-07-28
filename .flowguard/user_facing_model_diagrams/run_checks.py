"""Run the user-facing model diagram prompt guidance checks."""

from __future__ import annotations

from flowguard import run_exact_sequence

from model import (
    INVARIANTS,
    PromptAction,
    build_broken_mandatory_workflow,
    build_broken_missing_current_situation_workflow,
    build_broken_missing_route_workflow,
    build_broken_shallow_workflow,
    build_correct_workflow,
    initial_state,
)


CORRECT_SEQUENCE = (
    PromptAction("add_kernel_guidance"),
    PromptAction("add_ui_guidance"),
    PromptAction("add_mesh_guidance"),
    PromptAction("add_process_guidance"),
    PromptAction("add_expressive_diagram_guidance"),
    PromptAction("claim_release"),
)

MISSING_ROUTE_SEQUENCE = (
    PromptAction("add_kernel_guidance"),
    PromptAction("add_ui_guidance"),
    PromptAction("add_expressive_diagram_guidance"),
    PromptAction("claim_release"),
)


def run_report(workflow, sequence):
    run = run_exact_sequence(
        workflow=workflow,
        initial_state=initial_state(),
        external_input_sequence=sequence,
        invariants=INVARIANTS,
    )
    return run.model_report


def main() -> int:
    correct = run_report(build_correct_workflow(), CORRECT_SEQUENCE)
    broken_mandatory = run_report(build_broken_mandatory_workflow(), CORRECT_SEQUENCE)
    broken_missing_current = run_report(build_broken_missing_current_situation_workflow(), CORRECT_SEQUENCE)
    broken_shallow = run_report(build_broken_shallow_workflow(), CORRECT_SEQUENCE)
    broken_missing_route = run_report(build_broken_missing_route_workflow(), MISSING_ROUTE_SEQUENCE)

    print("correct_prompt_rollout:", "OK" if correct.ok else "VIOLATION")
    print(correct.format_text(max_examples=1))
    print()
    print("broken_mandatory_diagram_rollout:", "VIOLATION" if not broken_mandatory.ok else "OK")
    print(broken_mandatory.format_text(max_examples=1))
    print()
    print("broken_missing_current_situation_rollout:", "VIOLATION" if not broken_missing_current.ok else "OK")
    print(broken_missing_current.format_text(max_examples=1))
    print()
    print("broken_shallow_diagram_rollout:", "VIOLATION" if not broken_shallow.ok else "OK")
    print(broken_shallow.format_text(max_examples=1))
    print()
    print("broken_missing_route_rollout:", "VIOLATION" if not broken_missing_route.ok else "OK")
    print(broken_missing_route.format_text(max_examples=1))

    return 0 if (
        correct.ok
        and not broken_mandatory.ok
        and not broken_missing_current.ok
        and not broken_shallow.ok
        and not broken_missing_route.ok
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
