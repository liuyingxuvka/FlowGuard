"""Run FlowGuard checks for AI guidance compression."""

from __future__ import annotations

from pathlib import Path

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
from flowguard.prompt_budget import review_prompt_bundles
import model


ROOT = Path(__file__).resolve().parents[2]


REQUIRED_LABELS = (
            "guidance_compressed",
            "budget_tests_added",
            "validations_passed",
            "local_surfaces_synced",
            "done_accepted",
)


def run_real_load_graph_budget_review() -> bool:
    report = review_prompt_bundles(ROOT)
    kernel = next(item for item in report["bundles"] if item["route_id"] == "flowguard")
    component_paths = {item["path"] for item in kernel["components"]}
    conditional_paths = {item["path"] for item in kernel["conditional_edges"]}
    ok = (
        report["ok"]
        and report["provider_token_usage_available"] is False
        and kernel["headroom_ok"]
        and ".agents/skills/flowguard/references/route_index.md" in component_paths
        and ".agents/skills/flowguard/references/modeling_protocol.md" in conditional_paths
    )
    print(
        "derived first-read load graph and headroom: "
        f"{'pass' if ok else 'fail'}; routes={report['bundle_count']}; "
        f"failed={report['failed_route_ids']}"
    )
    print()
    return ok


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_guidance_compression",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claim == "accepted",
    )
    workflow_report = run_formal_workflow_suite(
        "guidance_compression",
        (
            FormalWorkflowCase("broken_prompt_only_completion", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="guidance_prompt_only_completion",
    )
    reports = (
        ("architecture reduction", model.architecture_reduction_report()),
        ("development process flow", model.development_process_report()),
    )
    report_checks = []
    for label, report in reports:
        print(f"=== {label} ===")
        print(report.format_text())
        print()
        report_checks.append(report.ok)
    load_graph_ok = run_real_load_graph_budget_review()
    return 0 if exact_ok and workflow_report.ok and all(report_checks) and load_graph_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
