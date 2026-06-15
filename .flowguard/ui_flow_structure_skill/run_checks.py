"""Run the UI flow structure satellite rollout model checks."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


def run_sequence(name: str, workflow, *, expect_ok: bool, sequence: tuple[model.RolloutAction, ...]) -> bool:
    run = run_exact_sequence(
        workflow=workflow,
        initial_state=model.initial_state(),
        external_input_sequence=sequence,
        invariants=model.INVARIANTS,
    )
    ok = run.model_report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(run.model_report.format_text(max_examples=1))
    return ok is expect_ok


DESIGN_SEQUENCE = (
    model.RolloutAction("create_ui_model"),
    model.RolloutAction("review_ui_model"),
    model.RolloutAction("review_journey_coverage"),
    model.RolloutAction("derive_structure"),
    model.RolloutAction("document_skill"),
)

IMPLEMENTATION_SEQUENCE = DESIGN_SEQUENCE[:4] + (
    model.RolloutAction("review_implementation_validation"),
    model.RolloutAction("document_skill"),
    model.RolloutAction("claim_implemented_ui"),
)


def main() -> int:
    workflow_report = run_formal_workflow_suite(
        "ui_flow_structure_skill",
        (
            FormalWorkflowCase(
                "correct_ui_flow_structure_rollout",
                model.build_correct_workflow(),
                True,
                required_labels=(
                    "ui_model_reviewed",
                    "journey_coverage_reviewed",
                    "structure_derived",
                    "skill_documented",
                    "release_accepted",
                ),
            ),
            FormalWorkflowCase(
                "broken_layout_only_without_ui_model",
                model.build_broken_layout_only_workflow(),
                False,
                required_labels=("structure_derived", "release_accepted"),
            ),
            FormalWorkflowCase(
                "broken_no_parent_child_topology",
                model.build_broken_no_topology_workflow(),
                False,
                required_labels=("ui_model_reviewed", "structure_derived_without_topology", "release_accepted"),
            ),
            FormalWorkflowCase(
                "broken_no_journey_coverage",
                model.build_broken_no_journey_coverage_workflow(),
                False,
                required_labels=("ui_model_reviewed", "structure_derived", "skill_documented", "release_accepted"),
            ),
            FormalWorkflowCase(
                "broken_no_visible_branch_coverage",
                model.build_broken_no_visible_branch_coverage_workflow(),
                False,
                required_labels=(
                    "ui_model_reviewed",
                    "journey_coverage_reviewed_without_visible_branch_review",
                    "structure_derived",
                    "skill_documented",
                    "release_accepted",
                ),
            ),
            FormalWorkflowCase(
                "broken_no_typography_handoff",
                model.build_broken_no_typography_handoff_workflow(),
                False,
                required_labels=("structure_derived_without_typography_handoff", "skill_documented", "release_accepted"),
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.RELEASE_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=6,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="ui_flow_structure_evidence_missing",
    )
    checks = (
        workflow_report.ok,
        run_sequence(
            "correct_implemented_ui_validation",
            model.build_correct_workflow(),
            expect_ok=True,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_implementation_without_feature_alignment_sequence",
            model.build_broken_implementation_without_feature_alignment_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_implementation_without_clickthrough_sequence",
            model.build_broken_implementation_without_clickthrough_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_stale_implementation_evidence_sequence",
            model.build_broken_stale_implementation_evidence_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
