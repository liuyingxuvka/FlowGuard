"""Run the project adoption/version gate rollout model."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
    "real_package_verified",
    "global_consumer_suite_verified",
    "registered_artifact_scan_verified",
    "typed_behavior_ledger_migrated",
    "unsupported_registered_envelope_migration_blocked",
    "target_owned_json_migration_blocked",
    "legacy_lookalike_json_migration_blocked",
    "author_maintenance_dependency_blocked",
    "currentness_validation_launch_blocked",
    "agents_block_written",
    "manifest_written",
    "validation_rerun",
    "claim_complete",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_project_adoption_gate",
        workflow=model.build_workflow(model.ProjectAdoptionGate()),
        initial_state=model.initial_state(),
        external_input_sequence=(
            model.ProjectAction("verify_real_package"),
            model.ProjectAction("verify_packaged_global_consumer"),
            model.ProjectAction("verify_registered_artifact_scan"),
            model.ProjectAction("migrate_typed_behavior_ledger"),
            model.ProjectAction("attempt_unsupported_registered_envelope_migration"),
            model.ProjectAction("attempt_target_owned_json_migration"),
            model.ProjectAction("attempt_legacy_lookalike_json_migration"),
            model.ProjectAction("attempt_author_maintenance_dependency"),
            model.ProjectAction("attempt_currentness_validation_launch"),
            model.ProjectAction("installed_newer"),
            model.ProjectAction("write_agents_block"),
            model.ProjectAction("write_manifest"),
            model.ProjectAction("rerun_validation"),
            model.ProjectAction("record_adoption_log"),
            model.ProjectAction("claim_done"),
        ),
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.validation_current
        and state.agents_block_current
        and state.manifest_current,
    )
    report = run_formal_workflow_suite(
        "project_adoption_version_gate",
        (
            FormalWorkflowCase(
                "broken_claim_without_agents",
                model.build_workflow(model.BrokenClaimWithoutAgents()),
                False,
                required_labels=("broken_claim_complete",),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_packaged_global_consumer"),
                    model.ProjectAction("claim_done"),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_upgrade_without_validation",
                model.build_workflow(model.BrokenUpgradeWithoutValidation()),
                False,
                required_labels=("broken_upgrade_claim_complete",),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_packaged_global_consumer"),
                    model.ProjectAction("write_agents_block"),
                    model.ProjectAction("write_manifest"),
                ),
                max_sequence_length=4,
            ),
            FormalWorkflowCase(
                "broken_log_as_completion",
                model.build_workflow(model.BrokenLogAsCompletion()),
                False,
                required_labels=("broken_log_claim_complete",),
                external_inputs=(model.ProjectAction("record_adoption_log"),),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_skillguard_project_pollution",
                model.build_workflow(model.BrokenSkillGuardProjectPollution()),
                False,
                required_labels=("broken_skillguard_project_pollution",),
                external_inputs=(
                    model.ProjectAction("attempt_skillguard_project_write"),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "source_layout_revalidation_is_not_portable_proof",
                model.build_workflow(model.BrokenSourceLayoutRevalidation()),
                False,
                required_labels=("broken_source_layout_claim_complete",),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_packaged_global_consumer"),
                    model.ProjectAction("write_agents_block"),
                    model.ProjectAction("write_manifest"),
                    model.ProjectAction("rerun_validation"),
                    model.ProjectAction("claim_done"),
                ),
                max_sequence_length=6,
            ),
            FormalWorkflowCase(
                "project_local_flowguard_suite_is_not_current_authority",
                model.build_workflow(model.BrokenProjectLocalFlowGuardSuite()),
                False,
                required_labels=("broken_project_local_flowguard_skill_write",),
                external_inputs=(
                    model.ProjectAction("attempt_project_local_flowguard_skill_write"),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "editable_author_suite_is_not_portable_consumer_authority",
                model.build_workflow(model.BrokenEditableAuthorSuiteAuthority()),
                False,
                required_labels=("broken_editable_author_suite_claim_complete",),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_packaged_global_consumer"),
                    model.ProjectAction("write_agents_block"),
                    model.ProjectAction("write_manifest"),
                    model.ProjectAction("rerun_validation"),
                    model.ProjectAction("claim_done"),
                ),
                max_sequence_length=6,
            ),
            FormalWorkflowCase(
                "ordinary_adoption_has_zero_author_maintenance_dependency",
                model.build_workflow(model.BrokenAuthorMaintenanceDependency()),
                False,
                required_labels=("broken_author_maintenance_dependency",),
                external_inputs=(
                    model.ProjectAction(
                        "attempt_author_maintenance_dependency"
                    ),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "read_only_currentness_launches_no_semantic_validator",
                model.build_workflow(model.BrokenCurrentnessValidationLaunch()),
                False,
                required_labels=("broken_currentness_validation_launch",),
                external_inputs=(
                    model.ProjectAction(
                        "attempt_currentness_validation_launch"
                    ),
                ),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "numeric_schema_marker_is_not_artifact_authority",
                model.build_workflow(model.BrokenNumericSchemaArtifactAuthority()),
                False,
                required_labels=(
                    "broken_target_owned_json_written",
                    "broken_numeric_schema_claim_complete",
                ),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_registered_artifact_scan"),
                    model.ProjectAction("attempt_target_owned_json_migration"),
                    model.ProjectAction("claim_done"),
                ),
                max_sequence_length=4,
            ),
            FormalWorkflowCase(
                "unsupported_registered_envelope_has_no_migrator",
                model.build_workflow(
                    model.BrokenUnsupportedRegisteredEnvelopeMigration()
                ),
                False,
                required_labels=(
                    "broken_unsupported_registered_envelope_written",
                    "broken_unsupported_registered_envelope_claim_complete",
                ),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_registered_artifact_scan"),
                    model.ProjectAction(
                        "attempt_unsupported_registered_envelope_migration"
                    ),
                    model.ProjectAction("claim_done"),
                ),
                max_sequence_length=4,
            ),
            FormalWorkflowCase(
                "legacy_lookalike_extra_fields_are_not_artifact_authority",
                model.build_workflow(
                    model.BrokenLegacyLookalikeArtifactAuthority()
                ),
                False,
                required_labels=(
                    "broken_legacy_lookalike_json_written",
                    "broken_legacy_lookalike_claim_complete",
                ),
                external_inputs=(
                    model.ProjectAction("verify_real_package"),
                    model.ProjectAction("verify_registered_artifact_scan"),
                    model.ProjectAction(
                        "attempt_legacy_lookalike_json_migration"
                    ),
                    model.ProjectAction("claim_done"),
                ),
                max_sequence_length=4,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=8,
        required_labels=REQUIRED_LABELS,
        protected_error_class="project_adoption_gate_bypassed",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
