"""Run formal checks for task-derived coverage demand."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "task_coverage_demand"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


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
        (
            FormalWorkflowCase("broken_caller_reduces_minimum", model.broken_caller_only_workflow(), False),
            FormalWorkflowCase("broken_missing_fact_source", model.broken_missing_source_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("task_facts_frozen", "coverage_demand_compiled", "coverage_demand_closed"),
        protected_error_class="task_coverage_demand_incomplete",
    )
    return 0 if correct_ok and report.ok else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:task_coverage_demand", main))
