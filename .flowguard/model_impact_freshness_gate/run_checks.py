"""Run the model impact freshness gate checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "direct_upgrade_impact_recorded",
            "impact_mapping_complete",
            "classified_affected",
            "classified_not_impacted_with_same_output",
            "exact_current_receipt_verified",
            "model_and_tests_update_reviewed",
            "rerun_passed",
            "claim_accepted",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_model_impact_freshness_gate",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.CORRECT_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.claim == "accepted",
    )
    bad_observation_cases = (
        (
            "persistent_observation_is_rejected",
            model.UpgradeAction("rerun_model", observation_scope="persistent"),
        ),
        (
            "repeated_semantic_verification_is_rejected",
            model.UpgradeAction("rerun_model", semantic_verification_count=2),
        ),
        (
            "missing_final_identity_freshness_is_rejected",
            model.UpgradeAction(
                "rerun_model",
                complete_observation_count=1,
                final_identity_freshness_passed=False,
            ),
        ),
    )
    observation_shape_ok = True
    for case_id, rerun_action in bad_observation_cases:
        observation_shape_ok = (
            run_exact_workflow_case(
                case_id,
                workflow=model.build_correct_workflow(),
                initial_state=model.initial_state(),
                external_input_sequence=(
                    model.UpgradeAction("record_direct_upgrade_impact"),
                    model.UpgradeAction("record_impact_mapping_complete"),
                    model.UpgradeAction("classify_affected"),
                    model.UpgradeAction("update_model_and_tests"),
                    rerun_action,
                    model.UpgradeAction("claim_upgrade_gate"),
                ),
                invariants=model.INVARIANTS,
                final_state_predicate=lambda state: state.claim == "rejected",
            )
            and observation_shape_ok
        )
    report = run_formal_workflow_suite(
        "model_impact_freshness_gate",
        (
            FormalWorkflowCase("broken_reuses_old_evidence_without_classification", model.build_broken_reuse_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase("broken_accepts_affected_model_without_rerun", model.build_broken_affected_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase(
                "unknown_impact_blocks_without_run_all",
                model.build_broken_unknown_impact_workflow(),
                False,
                required_labels=("claim_accepted",),
                external_inputs=(
                    model.UpgradeAction("record_unknown_impact"),
                    model.UpgradeAction("claim_upgrade_gate"),
                ),
                max_sequence_length=2,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="stale_model_evidence_reuse",
    )
    return 0 if exact_ok and observation_shape_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
