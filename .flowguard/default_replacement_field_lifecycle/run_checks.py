"""Run FlowGuard checks for default replacement and field lifecycle closure."""

from __future__ import annotations

import json
import os
from pathlib import Path

from flowguard import (
    FIELD_DISPOSITION_MIGRATED,
    FIELD_ROLE_METADATA,
    FIELD_ROLE_PERMISSION,
    FIELD_ROLE_PRESENTATION,
    FIELD_ROLE_PROMPT_CONFIG,
    FIELD_ROLE_ROUTING,
    FIELD_ROLE_STATE,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
    review_field_lifecycle,
    ui_content_visibility_candidate_ids_from_field_lifecycle,
)
from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "fields_accounted",
            "field_projection_and_disposition_done",
            "model_code_test_and_bug_repair_done",
            "freshness_and_closure_current",
            "claim_full",
)


def ui_reader_handoff_contract() -> tuple[bool, tuple[str, ...]]:
    plan = FieldLifecyclePlan(
        "ui-reader-handoff-contract",
        discovered_field_ids=(
            "field:title",
            "field:phase",
            "field:permission",
            "field:audit_trace",
        ),
        fields=(
            FieldLifecycleRow(
                "field:title",
                role=FIELD_ROLE_PRESENTATION,
                reader_ids=("ordinary-ui-view",),
            ),
            FieldLifecycleRow(
                "field:phase",
                role=FIELD_ROLE_STATE,
                reader_ids=("ordinary-ui-view",),
            ),
            FieldLifecycleRow(
                "field:permission",
                role=FIELD_ROLE_PERMISSION,
                reader_ids=("ordinary-ui-view",),
            ),
            FieldLifecycleRow(
                "field:audit_trace",
                role=FIELD_ROLE_METADATA,
                reader_ids=("audit-log",),
            ),
        ),
    )
    candidate_ids = ui_content_visibility_candidate_ids_from_field_lifecycle(
        plan,
        ui_reader_ids=("ordinary-ui-view",),
    )
    return (
        candidate_ids == ("field:title", "field:phase", "field:permission"),
        candidate_ids,
    )


def product_language_authority_field_contract() -> tuple[bool, dict[str, object]]:
    """Account new authority fields and prove they remain internal UI inputs."""

    routing_fields = (
        ("field:business_intent_id", "behavior_commitment_ledger"),
        ("field:behavior_commitment_id", "behavior_commitment_ledger"),
        ("field:behavior_plane", "behavior_commitment_ledger"),
        ("field:actor_kind", "behavior_commitment_ledger"),
        ("field:relations", "behavior_commitment_ledger"),
        ("field:lookup_binding", "behavior_commitment_ledger"),
        ("field:behavior_lookup_status", "existing_model_preflight"),
        ("field:primary_behavior_plane", "existing_model_preflight"),
        ("field:affected_behavior_plane", "model_miss_review"),
        ("field:affected_commitment_id", "model_miss_review"),
        ("field:same_plane_lookup_performed", "model_miss_review"),
        ("field:coverage_gap_registered", "model_miss_review"),
        ("field:primary_owner_model_id", "behavior_commitment_ledger"),
        ("field:error_signatures", "model_miss_review"),
        ("field:primary_path_id", "primary_path_authority"),
        ("field:expected_surface_ids", "existing_model_preflight"),
        ("field:expected_candidate_ids", "architecture_reduction"),
        ("field:expected_member_ids", "obligation_family"),
        ("field:model_signature.behavior_plane", "model_similarity"),
        ("field:model_signature.typed_commitment_relation_refs", "model_similarity"),
        ("field:model_test_alignment.behavior_plane", "model_test_alignment"),
        ("field:model_test_alignment.require_behavior_plane_binding", "model_test_alignment"),
        ("field:process_action.behavior_plane", "development_process_flow"),
        ("field:process_action.target_behavior_planes", "development_process_flow"),
        ("field:process_action.target_commitment_ids", "development_process_flow"),
        ("field:process_action.typed_commitment_relation_refs", "development_process_flow"),
        ("field:agent_workflow_step.behavior_plane", "agent_workflow_rehearsal"),
        ("field:agent_workflow_step.target_behavior_planes", "agent_workflow_rehearsal"),
        ("field:agent_workflow_step.target_commitment_ids", "agent_workflow_rehearsal"),
        ("field:agent_workflow_step.typed_commitment_relation_refs", "agent_workflow_rehearsal"),
        ("field:agent_workflow_plan.behavior_plane", "agent_workflow_rehearsal"),
        ("field:agent_workflow_plan.require_behavior_plane_boundary", "agent_workflow_rehearsal"),
        ("field:plan_detail_step.behavior_plane", "plan_detailing"),
        ("field:plan_detail_step.target_behavior_planes", "plan_detailing"),
        ("field:plan_detail_step.target_commitment_ids", "plan_detailing"),
        ("field:plan_detail_step.typed_commitment_relation_refs", "plan_detailing"),
        ("field:development_process_plan.behavior_plane", "development_process_flow"),
        ("field:development_process_plan.require_behavior_plane_boundary", "development_process_flow"),
        ("field:plan_detail.require_behavior_plane_boundary", "plan_detailing"),
        ("field:architecture_reduction.business_intent_id", "architecture_reduction"),
        ("field:architecture_reduction.behavior_commitment_id", "architecture_reduction"),
        ("field:architecture_reduction.primary_path_id", "architecture_reduction"),
        ("field:architecture_reduction.owner_code_contract_id", "architecture_reduction"),
        ("field:architecture_reduction.delegates_to_code_contract_id", "architecture_reduction"),
        ("field:architecture_reduction.delegates_to_primary_path_id", "architecture_reduction"),
        ("field:architecture_reduction.delegation_evidence_id", "architecture_reduction"),
        ("field:architecture_reduction.delegation_evidence_current", "architecture_reduction"),
        ("field:architecture_reduction.delegation_only", "architecture_reduction"),
        ("field:architecture_reduction.independent_business_authority", "architecture_reduction"),
        ("field:test_suite.run_id", "test_mesh"),
        ("field:test_suite.terminal_status", "test_mesh"),
        ("field:test_suite.exit_code", "test_mesh"),
        ("field:test_suite.result_fingerprint", "test_mesh"),
        ("field:test_suite.covered_obligation_ids", "test_mesh"),
        ("field:test_suite.artifact_version", "test_mesh"),
        ("field:test_suite.verifier_version", "test_mesh"),
        ("field:spec_check.orchestrator_reuse_policy", "spec_work_package"),
    )
    internal_metadata_fields = (
        "field:variant_of_commitment_id",
        "field:external_difference_fields",
        "field:similarity_relation_ids",
        "field:consistency_rule_ids",
        "field:path_disposition",
        "field:inventory_revision",
        "field:scoped_dispositions",
        "field:materialized_test_obligations",
        "field:materialized_code_obligations",
        "field:primary_commitment_hits",
        "field:related_commitment_hits",
        "field:candidate_commitment_hits",
        "field:plane_ambiguity",
        "field:ledger_fingerprint",
        "field:lookup_match_reasons",
        "field:commitment_hit_role",
        "field:related_behavior_context",
        "field:error_evidence_ids",
        "field:behavior_coverage_gap_candidate",
        "field:canonical_ledger_path",
        "field:legacy_primary_path_ids",
        "field:model_signature.multi_plane_scope_reason",
    )
    prompt_config_fields = (
        "field:skill_contract_v2.schema_version",
        "field:skill_contract_v2.model_id",
        "field:skill_contract_v2.model_path",
        "field:skill_contract_v2.confirmed",
        "field:skill_contract_v2.release_eligible",
        "field:skill_contract_v2.implementation_paths",
        "field:skill_contract_v2.step_bindings",
        "field:skill_contract_v2.checks",
        "field:skill_contract_v2.artifacts",
        "field:skill_contract_v2.closure_profiles",
        "field:skill_contract_v2.judgment_rubrics",
    )
    discovered = tuple(field_id for field_id, _owner in routing_fields) + internal_metadata_fields + prompt_config_fields + (
        "field:primary_path_ids",
        "field:dependency_commitment_ids",
    )
    rows = tuple(
        FieldLifecycleRow(
            field_id,
            role=FIELD_ROLE_ROUTING,
            reader_ids=(owner, "model_test_alignment"),
            writer_ids=(owner,),
            projection=FieldProjection(
                f"projection:{field_id}",
                field_id,
                model_obligation_id=f"obligation:{field_id}",
                code_contract_id=f"contract:{owner}",
                external_outputs=(field_id,),
                state_writes=(field_id,),
                rationale="Stable internal product-language/path-reuse authority field.",
            ),
        )
        for field_id, owner in routing_fields
    ) + tuple(
        FieldLifecycleRow(
            field_id,
            role=FIELD_ROLE_METADATA,
            reader_ids=("flowguard-internal-reviewers",),
            writer_ids=("flowguard-existing-owner",),
            scoped_out_reason="Internal comparison, inventory, or audit metadata; never ordinary UI content.",
        )
        for field_id in internal_metadata_fields
    ) + tuple(
        FieldLifecycleRow(
            field_id,
            role=FIELD_ROLE_PROMPT_CONFIG,
            reader_ids=("skillguard_v2_compiler", "flowguard_skill_installer"),
            writer_ids=("skillguard_contract_source",),
            projection=FieldProjection(
                f"projection:{field_id}",
                field_id,
                model_obligation_id=f"obligation:{field_id}",
                code_contract_id="contract:skillguard-v2-contract-source",
                external_outputs=("compiled-contract.json", "check-manifest.json", "installed-skill-copy"),
                state_writes=(field_id,),
                rationale="Canonical V2 source projects deterministically to generated and installed skill records.",
            ),
        )
        for field_id in prompt_config_fields
    ) + (
        FieldLifecycleRow(
            "field:primary_path_ids",
            role=FIELD_ROLE_METADATA,
            reader_ids=("behavior_commitment_legacy_normalizer",),
            writer_ids=(),
            replacement_field_id="field:primary_path_id",
            disposition=FIELD_DISPOSITION_MIGRATED,
            compatibility_intent="Accept deterministic one-item legacy input only.",
            disposition_evidence_refs=("test:singular-primary-path-migration",),
            scoped_out_reason="Legacy compatibility input is not emitted and is never displayed.",
        ),
        FieldLifecycleRow(
            "field:dependency_commitment_ids",
            role=FIELD_ROLE_METADATA,
            reader_ids=("behavior_commitment_ledger_mapping_upgrader",),
            writer_ids=(),
            replacement_field_id="field:relations",
            disposition=FIELD_DISPOSITION_MIGRATED,
            compatibility_intent="Convert deterministic same-plane dependencies to typed relations only.",
            disposition_evidence_refs=("test:behavior-ledger-dependency-migration",),
            scoped_out_reason="Legacy dependency input is retired from runtime objects and ordinary UI.",
        ),
    )
    plan = FieldLifecyclePlan(
        "product-language-path-reuse-field-contract",
        discovered_field_ids=discovered,
        fields=rows,
        claim_scope="bounded",
        allow_scoped_confidence=True,
        notes="Existing owners write these fields; UI consumes only approved projections and never renders the ids.",
    )
    report = review_field_lifecycle(plan)
    ordinary_ui_candidates = ui_content_visibility_candidate_ids_from_field_lifecycle(
        plan,
        ui_reader_ids=("ordinary-ui-view",),
    )
    return (
        report.ok and not ordinary_ui_candidates,
        {
            "report": report.to_dict(),
            "ordinary_ui_candidate_ids": list(ordinary_ui_candidates),
            "discovered_field_ids": list(discovered),
        },
    )
def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_default_replacement_field_lifecycle",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.final_claim == "full",
    )
    cases = [
        FormalWorkflowCase(workflow.name, workflow, False, required_labels=REQUIRED_LABELS)
        for workflow in model.build_broken_workflows()
    ]
    report = run_formal_workflow_suite(
        "default_replacement_field_lifecycle",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.BAD_CASE_EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="old_field_disposition_gap",
    )
    handoff_ok, candidate_ids = ui_reader_handoff_contract()
    authority_fields_ok, authority_fields = product_language_authority_field_contract()
    ok = exact_ok and report.ok and handoff_ok and authority_fields_ok
    payload = {
        "ok": ok,
        "exact_workflow_ok": exact_ok,
        "formal_report": {
            "ok": report.ok,
            "summary": report.format_text(),
        },
        "ui_reader_handoff": {
            "ok": handoff_ok,
            "candidate_ids": list(candidate_ids),
            "excluded_backend_field_ids": ["field:audit_trace"],
        },
        "product_language_authority_fields": {
            "ok": authority_fields_ok,
            **authority_fields,
        },
    }
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if ok:
        print("default replacement field lifecycle model checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
