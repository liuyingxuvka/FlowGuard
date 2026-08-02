"""Run formal checks for task-derived coverage demand."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.REQUEST,),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok and len(correct.final_states) == 1
    print(f"correct_task_coverage_demand: {'exact model pass' if correct_ok else 'failed'}")
    report = run_formal_workflow_suite(
        "task_coverage_demand",
        (FormalWorkflowCase("broken_caller_reduces_minimum", model.broken_caller_only_workflow(), False),),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("task_facts_frozen", "coverage_demand_compiled", "coverage_demand_closed"),
        protected_error_class="task_coverage_demand_incomplete",
    )
    return 0 if correct_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
