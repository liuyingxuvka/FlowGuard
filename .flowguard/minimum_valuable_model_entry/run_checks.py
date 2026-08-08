"""Run the continuing minimum valuable model entry self-checks."""

from __future__ import annotations

from pathlib import Path

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
from flowguard.prompt_budget import review_prompt_bundles
import model


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_LABELS = ("minimum_contract_inspected", "minimum_model_accepted")
FORBIDDEN_TEMPLATE_OPERATION_MARKERS = (
    "template",
    "no_match",
    "nomatch",
    "harvest",
)


def _trace_has_template_operation(trace) -> bool:
    return any(
        marker in f"{step.function_name}:{step.label}".lower()
        for step in trace.steps
        for marker in FORBIDDEN_TEMPLATE_OPERATION_MARKERS
    )


def run_ordinary_entry_review() -> bool:
    result = run_exact_sequence(
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.COMPLETE_REQUEST,),
        invariants=model.INVARIANTS,
    )
    accepted = bool(result.final_states) and all(
        state.accepted_model_ids == (model.COMPLETE_REQUEST.request_id,)
        for state in result.final_states
    )
    no_template_operation = all(
        not _trace_has_template_operation(trace)
        for trace in result.traces
    )
    ok = result.model_report.ok and accepted and no_template_operation
    print(f"ordinary minimum-model entry: {'pass' if ok else 'fail'}")
    print(
        "ordinary path template operations: "
        f"{'none' if no_template_operation else 'unexpected'}"
    )
    return ok


def run_rejection_examples() -> bool:
    all_ok = True
    for request in model.INCOMPLETE_REQUESTS:
        result = run_exact_sequence(
            workflow=model.correct_workflow(),
            initial_state=model.initial_state(),
            external_input_sequence=(request,),
            invariants=model.INVARIANTS,
        )
        outputs = tuple(trace.final_output for trace in result.traces)
        expected_requirement = model.EXPECTED_REJECTION_REQUIREMENTS[request.request_id]
        rejected = bool(outputs) and all(
            isinstance(output, model.Rejected)
            and expected_requirement in output.reason
            for output in outputs
        )
        no_template_operation = all(
            not _trace_has_template_operation(trace)
            for trace in result.traces
        )
        case_ok = result.model_report.ok and rejected and no_template_operation
        print(
            f"{request.request_id}: "
            f"{'rejected as expected' if case_ok else 'failed'}"
        )
        all_ok = all_ok and case_ok
    return all_ok


def run_narrow_entry_projection_review() -> bool:
    report = review_prompt_bundles(ROOT)
    kernel = next(item for item in report["bundles"] if item["route_id"] == "flowguard")
    guaranteed = {item["path"] for item in kernel["components"]}
    conditional = {item["path"] for item in kernel["conditional_edges"]}
    ok = (
        kernel["ok"]
        and ".agents/skills/flowguard/references/route_index.md" in guaranteed
        and ".agents/skills/flowguard/references/modeling_protocol.md" not in guaranteed
        and ".agents/skills/flowguard/references/modeling_protocol.md" in conditional
    )
    print(f"narrow minimum-entry projection: {'pass' if ok else 'fail'}")
    return ok


def main() -> int:
    ordinary_ok = run_ordinary_entry_review()
    rejection_ok = run_rejection_examples()
    report = run_formal_workflow_suite(
        "minimum_valuable_model_entry",
        (
            FormalWorkflowCase(
                "broken_accepts_incomplete_model",
                model.broken_incomplete_workflow(),
                False,
            ),
            FormalWorkflowCase(
                "broken_runs_template_operation_on_ordinary_path",
                model.broken_template_operation_workflow(),
                False,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="minimum_valuable_model_missing_contract_or_binding",
    )
    projection_ok = run_narrow_entry_projection_review()
    return 0 if ordinary_ok and rejection_ok and report.ok and projection_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
