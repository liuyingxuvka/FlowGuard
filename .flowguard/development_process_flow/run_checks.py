"""Run the development_process_flow rollout model checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
from flowguard import Scenario, ScenarioExpectation, review_scenarios
import model


REQUIRED_LABELS = ("validation_passed", "release_accepted")


def run_implementation_admission_model() -> bool:
    report = review_scenarios(
        (
            Scenario(
                "closed_model_admits_implementation",
                "current closed-for-task maturation admits the requested scope",
                model.admission_initial_state(),
                model.GOOD_CLOSED_ADMISSION_SEQUENCE,
                ScenarioExpectation(expected_status="ok"),
                workflow=model.build_admission_workflow(),
            ),
            Scenario(
                "exact_authorization_allows_scoped_attempt",
                "an exact authorization permits only its bounded scope without changing understanding",
                model.admission_initial_state(),
                model.GOOD_SCOPED_ADMISSION_SEQUENCE,
                ScenarioExpectation(expected_status="ok"),
                workflow=model.build_admission_workflow(),
            ),
            Scenario(
                "authorization_cannot_erase_gaps",
                "a mismatched authorization cannot manufacture full model confidence",
                model.admission_initial_state(),
                model.BROKEN_AUTHORIZATION_SEQUENCE,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=(
                        "no_admission_without_task_sufficiency_or_exact_scope",
                    ),
                ),
                workflow=model.build_admission_workflow(broken=True),
            ),
        ),
        default_invariants=model.ADMISSION_INVARIANTS,
    )
    print(report.format_text())
    print()
    return report.ok


def run_release_identity_model() -> bool:
    scenarios = []
    for identity, sequence in model.STALE_OR_SUBSTITUTED_RELEASE_SEQUENCES:
        scenarios.append(
            Scenario(
                f"{identity}_stale_or_substituted_is_rejected",
                f"a stale or substituted {identity} identity cannot support release",
                model.initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("release_rejected",),
                    forbidden_trace_labels=("release_accepted",),
                ),
                workflow=model.build_correct_workflow(),
            )
        )
        scenarios.append(
            Scenario(
                f"broken_{identity}_substitution_is_detected",
                f"the known-bad gate exposes an accepted release with substituted {identity}",
                model.initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=(
                        "no_release_with_stale_or_incomplete_evidence",
                    ),
                    required_trace_labels=("release_accepted",),
                ),
                workflow=model.build_broken_workflow(),
            )
        )
    report = review_scenarios(tuple(scenarios), default_invariants=model.INVARIANTS)
    print(report.format_text())
    print()
    return report.ok


def run_author_shadow_sync_model() -> bool:
    scenarios = [
        Scenario(
            "failed_author_activation_rolls_back_before_claim",
            "a failed author activation restores the prior shadow and cannot claim author currentness",
            model.author_sync_initial_state(),
            model.GOOD_AUTHOR_SYNC_ROLLBACK_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("author_sync_rolled_back",),
                forbidden_trace_labels=("author_sync_accepted",),
            ),
            workflow=model.build_author_sync_workflow(),
        )
    ]
    for case_id, _failure_id, invariant_id, sequence in model.AUTHOR_SYNC_FAILURE_CASES:
        scenarios.append(
            Scenario(
                f"{case_id}_is_rejected",
                f"the correct author-sync gate rejects {case_id.replace('_', ' ')}",
                model.author_sync_initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("author_sync_rejected",),
                    forbidden_trace_labels=("author_sync_accepted",),
                ),
                workflow=model.build_author_sync_workflow(),
            )
        )
        scenarios.append(
            Scenario(
                f"broken_{case_id}",
                f"the known-bad author-sync gate exposes {case_id.replace('_', ' ')}",
                model.author_sync_initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=(invariant_id,),
                    required_trace_labels=("author_sync_accepted",),
                ),
                workflow=model.build_author_sync_workflow(broken=True),
            )
        )
    report = review_scenarios(
        tuple(scenarios),
        default_invariants=model.AUTHOR_SYNC_INVARIANTS,
    )
    print(report.format_text())
    print()
    exact_ok = run_exact_workflow_case(
        "correct_author_shadow_sync",
        workflow=model.build_author_sync_workflow(),
        initial_state=model.author_sync_initial_state(),
        external_input_sequence=model.GOOD_AUTHOR_SYNC_SEQUENCE,
        invariants=model.AUTHOR_SYNC_INVARIANTS,
        final_state_predicate=lambda state: state.claim == "accepted",
    )
    return report.ok and exact_ok


def run_path_quality_lifecycle_model() -> bool:
    scenarios = [
        Scenario(
            "ordinary_path_quality_stays_lightweight",
            "an ordinary change refreshes only the deterministic light review before activation",
            model.path_quality_lifecycle_initial_state(),
            model.GOOD_PATH_QUALITY_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("activation_bound_to_current_review",),
                forbidden_trace_labels=("deep_review_current",),
            ),
            workflow=model.build_path_quality_lifecycle_workflow(),
        ),
        Scenario(
            "evidence_triggered_deep_review_stays_current",
            "a triggered deep review runs before implementation and again after the change",
            model.path_quality_lifecycle_initial_state(),
            model.GOOD_TRIGGERED_DEEP_PATH_QUALITY_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "deep_review_triggered",
                    "deep_review_current",
                    "activation_bound_to_current_review",
                ),
            ),
            workflow=model.build_path_quality_lifecycle_workflow(),
        ),
    ]
    for case_id, sequence, rejected_label in model.PATH_QUALITY_FAILURE_SEQUENCES:
        scenarios.append(
            Scenario(
                f"{case_id}_is_rejected",
                f"the process rejects {case_id.replace('_', ' ')}",
                model.path_quality_lifecycle_initial_state(),
                sequence,
                ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=(rejected_label,),
                    forbidden_trace_labels=("activation_bound_to_current_review",),
                ),
                workflow=model.build_path_quality_lifecycle_workflow(),
            )
        )
    stale_sequence = next(
        sequence
        for case_id, sequence, _label in model.PATH_QUALITY_FAILURE_SEQUENCES
        if case_id == "candidate_without_post_change_refresh"
    ) + (model.PathQualityLifecycleAction("activate", model.PATH_QUALITY_STALE_FINGERPRINT),)
    scenarios.append(
        Scenario(
            "broken_gate_exposes_stale_activation",
            "the known-bad gate exposes activation without a refreshed exact result",
            model.path_quality_lifecycle_initial_state(),
            stale_sequence,
            ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=(
                    "path_quality_activation_requires_current_exact_result",
                ),
                required_trace_labels=("activation_bound_to_current_review",),
            ),
            workflow=model.build_path_quality_lifecycle_workflow(broken=True),
        )
    )
    report = review_scenarios(
        tuple(scenarios),
        default_invariants=model.PATH_QUALITY_LIFECYCLE_INVARIANTS,
    )
    print(report.format_text())
    print()
    return report.ok


def main() -> int:
    admission_ok = run_implementation_admission_model()
    release_identity_ok = run_release_identity_model()
    author_sync_ok = run_author_shadow_sync_model()
    path_quality_lifecycle_ok = run_path_quality_lifecycle_model()
    exact_ok = run_exact_workflow_case(
        "correct_development_process_flow",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.GOOD_RELEASE_SEQUENCE,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.release_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "development_process_flow",
        (
            FormalWorkflowCase("broken_reuses_stale_or_progress_evidence", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase(
                "broken_accepts_wrong_plane_action",
                model.build_broken_plane_workflow(),
                False,
                required_labels=("wrong_plane_action_accepted",),
            ),
            FormalWorkflowCase(
                "broken_accepts_mutating_spec_context",
                model.build_broken_workflow(),
                False,
                required_labels=("validation_passed", "release_accepted"),
                external_inputs=(
                    model.LifecycleAction(
                        "run_validation",
                        spec_context_read_only=False,
                        spec_receipt_bridge_present=True,
                    ),
                    model.LifecycleAction("claim_release"),
                ),
                max_sequence_length=2,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="stale_process_evidence",
    )
    return (
        0
        if admission_ok
        and release_identity_ok
        and author_sync_ok
        and path_quality_lifecycle_ok
        and exact_ok
        and report.ok
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
