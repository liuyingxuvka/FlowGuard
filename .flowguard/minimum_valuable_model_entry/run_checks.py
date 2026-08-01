"""Run the minimum valuable model entry self-checks."""

from __future__ import annotations

from pathlib import Path

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
from flowguard.prompt_budget import review_prompt_bundles
import model


ROOT = Path(__file__).resolve().parents[2]


REQUIRED_LABELS = ("template_search_done", "minimum_model_accepted", "local_candidate_harvested")


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
    correct = run_exact_sequence(
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=tuple(
            request
            for request in model.EXTERNAL_INPUTS
            if request.protected_error_class
            and request.completion_evidence
            and request.known_bad_case
            and request.portable_local_root
        ),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok and len(correct.final_states) == 1
    print(f"correct_minimum_valuable_model: {'exact model pass' if correct_ok else 'failed'}")
    report = run_formal_workflow_suite(
        "minimum_valuable_model_entry",
        (
            FormalWorkflowCase("broken_without_evidence", model.broken_without_evidence_workflow(), False),
            FormalWorkflowCase("broken_hardcoded_root", model.broken_hardcoded_root_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="minimum_valuable_model_missing_evidence",
    )
    projection_ok = run_narrow_entry_projection_review()
    return 0 if correct_ok and report.ok and projection_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
