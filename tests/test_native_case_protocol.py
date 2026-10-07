from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from flowguard.native_case_protocol import (
    BAD_DIMENSIONS,
    GOOD_DIMENSIONS,
    NativeCaseBinding,
    NativeCaseProtocolError,
    NativeModelCaseContract,
    NativeModelCaseResult,
    boundary_case_id,
    load_native_model_case_results,
    qualified_case_id,
    verify_native_model_cases,
)
from flowguard.native_case_mapping import (
    NATIVE_CASE_MAPPING_SCHEMA,
    NativeCaseMappingError,
    NativeCaseMappingRegistry,
    compute_native_case_mapping_fingerprint,
    load_native_case_mapping,
)
from flowguard.source_identity import source_file_fingerprint


def _fp(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _good_contract(owner: str = "model:alpha", case: str = "case:good") -> NativeModelCaseContract:
    return NativeModelCaseContract(
        owner_id=owner,
        source_case_id=case,
        case_kind="good",
        callable_ref="model.alpha.good",
        result_selector="report.case_results[case:good]",
        expected_status="pass",
        covered_dimensions=GOOD_DIMENSIONS,
        oracle_member_ids=tuple(f"oracle:{item}" for item in GOOD_DIMENSIONS),
        evidence_scope="model_policy",
        input_contract_fingerprint=_fp("input"),
        oracle_content_fingerprint=_fp("oracle"),
    )


def _result(contract: NativeModelCaseContract, *, dimensions=None, finding_codes=()):
    dimensions = tuple(dimensions or contract.covered_dimensions)
    return NativeModelCaseResult(
        owner_id=contract.owner_id,
        source_case_id=contract.source_case_id,
        outcome=contract.expected_status,
        observed_status=contract.expected_status,
        observed_finding_codes=tuple(finding_codes),
        executed_dimensions=dimensions,
        oracle_results=tuple(
            {
                "dimension": dimension,
                "oracle_member_id": f"oracle:{dimension}",
                "status": "pass",
                "ok": True,
            }
            for dimension in dimensions
        ),
        result_artifact_fingerprint=_fp("raw"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="raw.json",
    )


def test_boundary_id_is_stable_when_runner_content_changes():
    assert boundary_case_id("model:alpha") == "boundary:alpha"
    assert boundary_case_id("model:alpha") == boundary_case_id("model:alpha")


def test_native_source_case_maps_to_one_exact_blueprint_case():
    contract = _good_contract()
    result = _result(contract)
    report = verify_native_model_cases((contract,), (result,))
    assert report.ok
    assert report.leaf_case_ids == ("model:alpha:case:good",)


def test_unasserted_dimension_remains_not_run():
    contract = _good_contract()
    result = _result(contract, dimensions=GOOD_DIMENSIONS[:-1])
    report = verify_native_model_cases((contract,), (result,))
    assert not report.ok
    assert "model:alpha:case:good:completion" in report.unasserted_dimensions


def test_missing_foreign_and_duplicate_case_blocks():
    contract = _good_contract()
    first = _result(contract)
    foreign_payload = first.to_dict()
    foreign_payload.pop("schema_version", None)
    foreign_payload["source_case_id"] = "foreign"
    foreign = NativeModelCaseResult(**foreign_payload)
    report = verify_native_model_cases((contract,), (first, first, foreign))
    assert not report.ok
    assert report.duplicate_case_ids
    assert report.foreign_case_ids == ("model:alpha:foreign",)


def test_aggregate_proof_cannot_substitute_for_children():
    child = _good_contract(case="case:child")
    aggregate = NativeModelCaseContract(
        owner_id="model:alpha",
        source_case_id="case:aggregate",
        case_kind="aggregate",
        callable_ref="model.alpha.suite",
        result_selector="report.aggregate",
        expected_status="pass",
        evidence_scope="model_policy",
        required_child_case_ids=("case:child",),
    )
    aggregate_result = NativeModelCaseResult(
        owner_id="model:alpha",
        source_case_id="case:aggregate",
        outcome="pass",
        observed_status="pass",
        result_artifact_fingerprint=_fp("raw"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="raw.json",
        child_case_ids=("case:child",),
    )
    report = verify_native_model_cases((child, aggregate), (aggregate_result,))
    assert not report.ok
    assert report.missing_case_ids == ("model:alpha:case:child",)
    assert any(item.startswith("aggregate_child_result_missing") for item in report.findings)


def test_model_policy_pass_does_not_become_implementation_pass():
    contract = _good_contract()
    report = verify_native_model_cases((contract,), (_result(contract),))
    assert report.ok
    assert report.model_policy_pass
    assert not report.implementation_boundary_pass


def test_wrong_error_class_is_not_successful_known_bad_case():
    contract = NativeModelCaseContract(
        owner_id="model:alpha",
        source_case_id="case:bad",
        case_kind="bad",
        protected_failure_ids=("failure:expected",),
        callable_ref="model.alpha.bad",
        result_selector="report.bad",
        expected_status="rejected",
        expected_finding_codes=("failure:expected",),
        covered_dimensions=BAD_DIMENSIONS,
        oracle_member_ids=tuple(f"oracle:{item}" for item in BAD_DIMENSIONS),
        evidence_scope="model_policy",
        input_contract_fingerprint=_fp("input"),
        oracle_content_fingerprint=_fp("oracle"),
    )
    result = _result(contract, finding_codes=("failure:other",))
    report = verify_native_model_cases((contract,), (result,))
    assert not report.ok
    assert any(item.startswith("finding_code_missing") for item in report.findings)


def test_contract_rejects_incomplete_dimensions_and_boundary_alias():
    with pytest.raises(NativeCaseProtocolError, match="dimensions must be exact"):
        NativeModelCaseContract(
            owner_id="model:alpha",
            source_case_id="case:good",
            case_kind="good",
            callable_ref="model.alpha.good",
            result_selector="report.good",
            expected_status="pass",
            covered_dimensions=GOOD_DIMENSIONS[:-1],
            oracle_member_ids=("oracle:input",),
            evidence_scope="model_policy",
        )
    with pytest.raises(NativeCaseProtocolError, match="stable"):
        NativeModelCaseContract(
            owner_id="model:alpha",
            source_case_id="case:boundary:alpha:runner-v2",
            case_kind="boundary",
            callable_ref="model.alpha.boundary",
            result_selector="report.boundary",
            expected_status="pass",
            covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
            oracle_member_ids=("oracle:boundary",),
            evidence_scope="model_policy",
        )


def test_current_result_envelope_round_trips_row_schema(tmp_path):
    contract = _good_contract()
    result = _result(contract)
    path = tmp_path / "native-case-results.json"
    path.write_text(
        json.dumps(
            {"schema_version": "flowguard.native_model_case_result.v1", "results": [result.to_dict()]}
        ),
        encoding="utf-8",
    )

    loaded = load_native_model_case_results(path)

    assert loaded == (result,)


def test_oracle_members_and_contract_fingerprints_are_exact():
    contract = _good_contract()
    result = _result(contract)
    wrong_oracle_payload = result.to_dict()
    wrong_oracle_payload.pop("schema_version", None)
    wrong_oracle_payload["oracle_results"] = [
        {
            "dimension": dimension,
            "oracle_member_id": f"oracle:wrong:{dimension}",
            "status": "pass",
            "ok": True,
        }
        for dimension in contract.covered_dimensions
    ]
    wrong_oracle = NativeModelCaseResult(
        **wrong_oracle_payload
    )
    report = verify_native_model_cases((contract,), (wrong_oracle,))
    assert not report.ok
    assert any(item.startswith("oracle_member_mismatch") for item in report.findings)

    changed_input_payload = result.to_dict()
    changed_input_payload.pop("schema_version", None)
    changed_input_payload["input_fingerprint"] = _fp("different-input")
    changed_input = NativeModelCaseResult(**changed_input_payload)
    report = verify_native_model_cases((contract,), (changed_input,))
    assert not report.ok
    assert any(
        item.startswith("input_contract_fingerprint_mismatch")
        for item in report.findings
    )


def test_qualified_aggregate_consumes_cross_owner_child_result():
    child = _good_contract(owner="owner:child", case="case:child")
    aggregate = NativeModelCaseContract(
        owner_id="owner:parent",
        source_case_id="case:aggregate",
        case_kind="aggregate",
        callable_ref="model.parent.aggregate",
        result_selector="report.aggregate",
        expected_status="pass",
        evidence_scope="model_policy",
        required_child_case_ids=(qualified_case_id(child.owner_id, child.source_case_id),),
    )
    aggregate_result = NativeModelCaseResult(
        owner_id=aggregate.owner_id,
        source_case_id=aggregate.source_case_id,
        outcome="pass",
        observed_status="pass",
        result_artifact_fingerprint=_fp("aggregate-raw"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="aggregate.raw.json",
        child_case_ids=aggregate.required_child_case_ids,
    )
    report = verify_native_model_cases(
        (aggregate,),
        (aggregate_result,),
        available_case_keys=(qualified_case_id(child.owner_id, child.source_case_id),),
    )
    assert report.ok, report.findings


def _binding(
    *,
    owner: str = "model:alpha",
    blueprint: str = "behavior-case:surface:good:source",
    native: tuple[str, ...] = ("native:good",),
    mapping_fingerprint: str = "",
) -> NativeCaseBinding:
    return NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id=blueprint,
        blueprint_source_case_id="source",
        native_case_ids=native,
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=GOOD_DIMENSIONS,
        expected_status="pass",
        mapping_fingerprint=mapping_fingerprint,
    )


def test_binding_projection_requires_concrete_aggregate_children():
    from flowguard.native_case_protocol import verify_native_case_bindings

    aggregate = NativeCaseBinding(
        owner_id="model:alpha",
        blueprint_case_id="behavior-case:surface:good:suite",
        blueprint_source_case_id="suite",
        native_case_ids=("native:suite",),
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=GOOD_DIMENSIONS,
        expected_status="pass",
        required_child_case_ids=("model:alpha::native:child",),
    )
    result = _result(
        _good_contract(owner="model:alpha", case="native:suite")
    )
    payload = result.to_dict()
    payload.pop("schema_version", None)
    payload["source_case_id"] = "native:suite"
    payload["child_case_ids"] = ["model:alpha::native:child"]
    aggregate_result = NativeModelCaseResult(**payload)
    report = verify_native_case_bindings((aggregate,), (aggregate_result,))
    assert not report.ok
    assert any("binding_child_result_missing" in item for item in report.findings)


def test_mapping_registry_round_trips_and_rejects_stale_fingerprint(tmp_path):
    source_fp = _fp("manifest")
    skeleton = _binding()
    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_fp,
        source_paths=("MAPPING_SCENARIO.md",),
        bindings=(skeleton,),
    )
    row = _binding(mapping_fingerprint=mapping_fp)
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=source_fp,
        source_paths=("MAPPING_SCENARIO.md",),
        bindings=(row,),
    )
    path = tmp_path / "native-case-mapping.json"
    path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")
    loaded = load_native_case_mapping(path)
    assert loaded.mapping_fingerprint == mapping_fp
    assert loaded.bindings_by_owner["model:alpha"] == (row,)

    stale = registry.to_dict()
    stale["mapping_fingerprint"] = _fp("stale")
    with pytest.raises(NativeCaseMappingError, match="fingerprint"):
        NativeCaseMappingRegistry.from_payload(stale)


def test_mapping_reuses_one_current_native_row_for_two_compatible_obligations():
    first = _binding(blueprint="behavior-case:surface:good:first")
    second = _binding(blueprint="behavior-case:surface:good:repair-preservation")
    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=_fp("manifest"),
        source_paths=("MAPPING_BENCHMARK.md",),
        bindings=(first, second),
    )
    first = _binding(
        blueprint="behavior-case:surface:good:first",
        mapping_fingerprint=mapping_fp,
    )
    second = _binding(
        blueprint="behavior-case:surface:good:repair-preservation",
        mapping_fingerprint=mapping_fp,
    )
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=_fp("manifest"),
        source_paths=("MAPPING_BENCHMARK.md",),
        bindings=(first, second),
    )
    result = _result(_good_contract(case="native:good"))
    payload = result.to_dict()
    payload.pop("schema_version", None)
    payload["source_case_id"] = "native:good"
    result = NativeModelCaseResult(**payload)

    from flowguard.native_case_protocol import verify_native_case_bindings

    report = verify_native_case_bindings(
        registry.bindings,
        (result,),
        mapping_fingerprint=mapping_fp,
    )
    assert report.ok, report.findings
    assert set(report.projected_case_ids) == {
        "behavior-case:surface:good:first",
        "behavior-case:surface:good:repair-preservation",
    }


def test_mapping_registry_rejects_unknown_fields(tmp_path):
    path = tmp_path / "native-case-mapping.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": NATIVE_CASE_MAPPING_SCHEMA,
                "mapping_fingerprint": _fp("map"),
                "source_manifest_fingerprint": _fp("manifest"),
                "source_paths": [],
                "bindings": [],
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(NativeCaseMappingError, match="unknown fields"):
        load_native_case_mapping(path)


def test_mapping_registry_rejects_stale_current_manifest(tmp_path):
    manifest = tmp_path / ".flowguard" / "models" / "regression-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":"flowguard.model_regression_manifest.v4","models":[]}', encoding="utf-8")
    source_fp = source_file_fingerprint(manifest)
    binding = _binding()
    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_fp,
        source_paths=(".flowguard/models/regression-manifest.json",),
        bindings=(binding,),
    )
    binding = _binding(mapping_fingerprint=mapping_fp)
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=source_fp,
        source_paths=(".flowguard/models/regression-manifest.json",),
        bindings=(binding,),
    )
    assert registry.assert_current_manifest(tmp_path) == source_fp

    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(NativeCaseMappingError, match="source manifest fingerprint is stale"):
        registry.assert_current_manifest(tmp_path)


# Frozen R6 annex child identities; these are fixture declarations, not receipts.
_R6_AGGREGATE_CHILDREN = {'model:structure_refactor_mesh': ('native-scenario:structure_refactor_mesh:complete_architecture_reduction_handoff_passes',
                                   'native-scenario:structure_refactor_mesh:config_drift_fails',
                                   'native-scenario:structure_refactor_mesh:dependency_cycle_fails',
                                   'native-scenario:structure_refactor_mesh:duplicate_config_fails',
                                   'native-scenario:structure_refactor_mesh:duplicate_partition_fails',
                                   'native-scenario:structure_refactor_mesh:duplicate_side_effect_fails',
                                   'native-scenario:structure_refactor_mesh:duplicate_state_fails',
                                   'native-scenario:structure_refactor_mesh:flat_split_fails',
                                   'native-scenario:structure_refactor_mesh:good_plan_passes',
                                   'native-scenario:structure_refactor_mesh:missing_facade_fails',
                                   'native-scenario:structure_refactor_mesh:missing_owner_fails',
                                   'native-scenario:structure_refactor_mesh:package_api_registry_partition_is_required',
                                   'native-scenario:structure_refactor_mesh:public_entrypoint_removed_fails',
                                   'native-scenario:structure_refactor_mesh:receipt_supervision_partition_is_required',
                                   'native-scenario:structure_refactor_mesh:reduction_handoff_without_consumer_test_map_fails',
                                   'native-scenario:structure_refactor_mesh:reduction_handoff_without_current_proof_fails',
                                   'native-scenario:structure_refactor_mesh:reduction_handoff_without_next_route_fails',
                                   'native-scenario:structure_refactor_mesh:reduction_handoff_without_observable_contract_fails',
                                   'native-scenario:structure_refactor_mesh:reduction_handoff_without_target_action_fails',
                                   'native-scenario:structure_refactor_mesh:reduction_handoff_without_universe_member_fails',
                                   'native-scenario:structure_refactor_mesh:release_scope_requires_release_parity',
                                   'native-scenario:structure_refactor_mesh:stale_parity_fails',
                                   'native-scenario:structure_refactor_mesh:structuremesh_does_not_refactor_directly',
                                   'native-scenario:structure_refactor_mesh:target_boundary_map_missing_fails',
                                   'native-scenario:structure_refactor_mesh:target_not_model_derived_fails',
                                   'native-scenario:structure_refactor_mesh:ui_evidence_partition_is_required',
                                   'native-scenario:structure_refactor_mesh:unregistered_owner_fails'),
 'model:model_maturation_loop': ('case:model_maturation_loop:broken_permission_upgrades_blocked_maturation',
                                 'case:model_maturation_loop:correct_model_maturation_loop',
                                 'case:model_maturation_loop:disjoint_context_variant_preserved',
                                 'case:model_maturation_loop:generic_duplicate_responsibility_direction',
                                 'case:model_maturation_loop:identical_copy_not_shared_primary',
                                 'case:model_maturation_loop:required_architecture_gap_blocks_completion'),
 'model:authoritative_model_system': ('native-scenario:authoritative_model_system:active_direct_intent_source_requires_owner_model_input',
                                      'native-scenario:authoritative_model_system:addressable_maturation_gap_cannot_stop_the_loop',
                                      'native-scenario:authoritative_model_system:affected_reader_must_follow_every_semantic_dependency',
                                      'native-scenario:authoritative_model_system:caller_declared_diff_cannot_replace_canonical_diff',
                                      'native-scenario:authoritative_model_system:checked_in_semantic_declaration_cannot_self_certify_topology_currentness',
                                      'native-scenario:authoritative_model_system:complete_transaction_passes',
                                      'native-scenario:authoritative_model_system:declared_optional_local_model_cannot_disappear_from_coverage',
                                      'native-scenario:authoritative_model_system:direct_intent_source_fingerprint_must_be_current',
                                      'native-scenario:authoritative_model_system:empty_intent_inventory_cannot_pass_by_vacuity',
                                      'native-scenario:authoritative_model_system:empty_semantic_derivation_fingerprint_is_rejected',
                                      'native-scenario:authoritative_model_system:export_completion_does_not_promote_model_depth',
                                      'native-scenario:authoritative_model_system:faithful_current_with_improvement_gaps',
                                      'native-scenario:authoritative_model_system:five_model_slice_cannot_claim_whole_system_understanding',
                                      'native-scenario:authoritative_model_system:intent_source_cannot_change_during_revision_build',
                                      'native-scenario:authoritative_model_system:internally_consistent_provider_payload_cannot_replace_current_native_report',
                                      'native-scenario:authoritative_model_system:inventory_only_cannot_claim_whole_system_understanding',
                                      'native-scenario:authoritative_model_system:legacy_authority_schema_cannot_remain_a_second_reader',
                                      'native-scenario:authoritative_model_system:maturation_cannot_accept_resolved_boolean_as_evidence',
                                      'native-scenario:authoritative_model_system:maturation_cannot_use_caller_narrowed_coverage',
                                      'native-scenario:authoritative_model_system:native_hard_failure_cannot_be_improvement',
                                      'native-scenario:authoritative_model_system:old_rollback_contract_cannot_replay_at_same_snapshot',
                                      'native-scenario:authoritative_model_system:partial_multi_model_activation_rejected',
                                      'native-scenario:authoritative_model_system:pointer_only_operational_rollback_rejected',
                                      'native-scenario:authoritative_model_system:portable_export_preserves_every_blueprint_layer',
                                      'native-scenario:authoritative_model_system:project_document_must_carry_its_intent_authority',
                                      'native-scenario:authoritative_model_system:provider_lineage_cannot_be_omitted_from_broad_blueprint',
                                      'native-scenario:authoritative_model_system:raw_manifest_cannot_self_certify_semantic_mesh',
                                      'native-scenario:authoritative_model_system:revision_builder_cannot_activate_authority',
                                      'native-scenario:authoritative_model_system:revision_builder_rejects_caller_forged_native_owner_verification',
                                      'native-scenario:authoritative_model_system:revision_builder_rejects_canonical_receipt_disappearance',
                                      'native-scenario:authoritative_model_system:revision_builder_rejects_relabeled_scoped_parent',
                                      'native-scenario:authoritative_model_system:revision_builder_rejects_stale_parent_evidence',
                                      'native-scenario:authoritative_model_system:revision_builder_requires_one_exact_leaf_receipt_per_native_owner',
                                      'native-scenario:authoritative_model_system:revision_builder_requires_one_explicit_model_binding_per_native_owner_route',
                                      'native-scenario:authoritative_model_system:same_head_live_source_drift_blocks_activation',
                                      'native-scenario:authoritative_model_system:scoped_graph_not_whole_software_confidence',
                                      'native-scenario:authoritative_model_system:semantic_mesh_fingerprint_must_be_derived_from_reviewed_topology',
                                      'native-scenario:authoritative_model_system:stale_base_blocks_activation',
                                      'native-scenario:authoritative_model_system:stale_target_snapshot_cannot_support_broad_blueprint',
                                      'native-scenario:authoritative_model_system:target_cannot_be_current_by_label',
                                      'native-scenario:authoritative_model_system:topology_cannot_consume_ghost_runtime_evidence',
                                      'native-scenario:authoritative_model_system:topology_feedback_loop_rejects_stale_progress_contract',
                                      'native-scenario:authoritative_model_system:topology_feedback_loop_requires_current_progress_evidence',
                                      'native-scenario:authoritative_model_system:topology_feedback_loop_requires_progress_contract',
                                      'native-scenario:authoritative_model_system:topology_feedback_relation_classification_must_be_complete',
                                      'native-scenario:authoritative_model_system:topology_keeps_cross_boundary_support_non_structural',
                                      'native-scenario:authoritative_model_system:topology_parent_receipt_proves_only_composition',
                                      'native-scenario:authoritative_model_system:topology_rejects_duplicate_child_receipt_identity',
                                      'native-scenario:authoritative_model_system:topology_rejects_foreign_owner_child_receipt',
                                      'native-scenario:authoritative_model_system:topology_rejects_second_structural_parent',
                                      'native-scenario:authoritative_model_system:topology_rejects_stale_child_receipt',
                                      'native-scenario:authoritative_model_system:topology_rejects_two_root_sentinels',
                                      'native-scenario:authoritative_model_system:topology_repair_loop_requires_progress_contract',
                                      'native-scenario:authoritative_model_system:topology_requires_exact_child_receipt_coverage',
                                      'native-scenario:authoritative_model_system:topology_requires_one_root_sentinel',
                                      'native-scenario:authoritative_model_system:topology_retry_loop_requires_progress_contract',
                                      'native-scenario:authoritative_model_system:trace_projection_cannot_claim_full_graph',
                                      'native-scenario:authoritative_model_system:unfrozen_provider_registry_cannot_support_broad_blueprint',
                                      'native-scenario:authoritative_model_system:unverified_semantic_artifact_cannot_claim_completion',
                                      'native-scenario:authoritative_model_system:work_context_intent_source_requires_exact_current_identity'),
 'model:hierarchical_model_mesh': ('native-scenario:hierarchical_model_mesh:affected_sibling_models_become_stale',
                                   'native-scenario:hierarchical_model_mesh:background_evidence_required',
                                   'native-scenario:hierarchical_model_mesh:bug_instance_scope_rejected',
                                   'native-scenario:hierarchical_model_mesh:checked_in_semantic_declaration_cannot_certify_child_currentness',
                                   'native-scenario:hierarchical_model_mesh:checked_in_semantic_declaration_cannot_certify_progress_currentness',
                                   'native-scenario:hierarchical_model_mesh:child_boundary_diff_required',
                                   'native-scenario:hierarchical_model_mesh:child_receipt_identities_must_be_distinct',
                                   'native-scenario:hierarchical_model_mesh:coverage_gap_fails',
                                   'native-scenario:hierarchical_model_mesh:cross_boundary_support_cannot_masquerade_as_parent',
                                   'native-scenario:hierarchical_model_mesh:cross_child_connections_need_tests',
                                   'native-scenario:hierarchical_model_mesh:every_declared_child_needs_one_receipt',
                                   'native-scenario:hierarchical_model_mesh:feedback_loop_rejects_stale_progress_contract',
                                   'native-scenario:hierarchical_model_mesh:feedback_loop_rejects_stale_progress_evidence',
                                   'native-scenario:hierarchical_model_mesh:feedback_loop_requires_progress_contract',
                                   'native-scenario:hierarchical_model_mesh:feedback_relation_classification_must_be_complete',
                                   'native-scenario:hierarchical_model_mesh:finite_leaf_boundaries_must_execute',
                                   'native-scenario:hierarchical_model_mesh:foreign_owner_child_receipt_cannot_reattach',
                                   'native-scenario:hierarchical_model_mesh:full_parent_receipt_cannot_replace_declared_child_receipts',
                                   'native-scenario:hierarchical_model_mesh:global_cartesian_table_is_not_materialized',
                                   'native-scenario:hierarchical_model_mesh:good_plan_passes',
                                   'native-scenario:hierarchical_model_mesh:good_typed_current_topology_evidence_passes',
                                   'native-scenario:hierarchical_model_mesh:legacy_contract_required',
                                   'native-scenario:hierarchical_model_mesh:mesh_cannot_inline_child_graphs',
                                   'native-scenario:hierarchical_model_mesh:one_child_cannot_have_two_structural_parents',
                                   'native-scenario:hierarchical_model_mesh:overlap_review_required',
                                   'native-scenario:hierarchical_model_mesh:parent_must_classify_boundary_diff',
                                   'native-scenario:hierarchical_model_mesh:parent_must_consume_subtree_receipts',
                                   'native-scenario:hierarchical_model_mesh:parent_rerun_required_on_contract_drift',
                                   'native-scenario:hierarchical_model_mesh:recursive_depth_must_be_declared',
                                   'native-scenario:hierarchical_model_mesh:release_sync_required',
                                   'native-scenario:hierarchical_model_mesh:repair_loop_requires_progress_contract',
                                   'native-scenario:hierarchical_model_mesh:retry_loop_requires_progress_contract',
                                   'native-scenario:hierarchical_model_mesh:scale_trigger_required',
                                   'native-scenario:hierarchical_model_mesh:semantic_topology_trigger_required',
                                   'native-scenario:hierarchical_model_mesh:side_effect_owner_conflict_fails',
                                   'native-scenario:hierarchical_model_mesh:stale_child_receipt_cannot_reattach',
                                   'native-scenario:hierarchical_model_mesh:state_owner_conflict_fails',
                                   'native-scenario:hierarchical_model_mesh:topology_rejects_two_root_sentinels',
                                   'native-scenario:hierarchical_model_mesh:topology_requires_one_root_sentinel')}



def _r6_source_binding_fixtures():
    root = Path(__file__).resolve().parents[1]
    mapping = json.loads((root / ".flowguard/models/native-case-mapping.json").read_text(encoding="utf-8"))
    overrides = json.loads((root / ".flowguard/models/native-case-producer-overrides.json").read_text(encoding="utf-8"))
    by_blueprint = {row["blueprint_case_id"]: row for row in mapping["bindings"]}
    # Project the declared source extension into in-memory test fixtures only.
    # This does not compile, write, or certify the generated mapping artifact.
    by_blueprint.update({row["blueprint_case_id"]: row for row in overrides["bindings"]})
    bindings = tuple(
        NativeCaseBinding(**{
            key: value for key, value in row.items()
            if key not in {"schema_version", "binding_fingerprint"}
        })
        for row in by_blueprint.values()
    )
    return root, mapping, overrides, bindings


def _r6_fixture_result(binding, native_id):
    from dataclasses import replace

    result = _result(_good_contract(owner=binding.owner_id, case=native_id), dimensions=binding.covered_dimensions)
    return replace(
        result,
        outcome=binding.expected_status,
        observed_status=binding.expected_observed_status or binding.expected_status,
        # The wire requires both actual oracle finding codes and independent
        # protected-failure assertions. DPF's invariant name is deliberately
        # distinct from its eight protected producer failure identities.
        observed_finding_codes=tuple(sorted(set(binding.expected_finding_codes) | set(binding.protected_failure_ids))),
        child_case_ids=binding.required_child_case_ids,
    )


def test_aggregate_closure_contains_exact_override_leaf_union():
    from dataclasses import replace
    from flowguard.native_case_protocol import verify_native_case_bindings

    root, mapping, overrides, bindings = _r6_source_binding_fixtures()
    current_mapping = load_native_case_mapping(root / ".flowguard/models/native-case-mapping.json")
    current_by_blueprint = {row.blueprint_case_id: row for row in current_mapping.bindings}
    override_ids = [row["blueprint_case_id"] for row in overrides["bindings"]]
    assert override_ids and len(override_ids) == len(set(override_ids))
    override_bindings = tuple(row for row in bindings if row.blueprint_case_id in set(override_ids))
    assert len({row.fingerprint for row in override_bindings}) == len(override_ids)
    for row in override_bindings:
        assert row.blueprint_case_id in current_by_blueprint
        # The generated registry adds its own content identity. All observable
        # override semantics must still match its actual current projection.
        expected = row.to_dict()
        observed = current_by_blueprint[row.blueprint_case_id].to_dict()
        for payload in (expected, observed):
            payload.pop("mapping_fingerprint")
            payload.pop("binding_fingerprint")
        assert observed == expected
    manifest = json.loads((root / ".flowguard/models/regression-manifest.json").read_text(encoding="utf-8"))
    owners = {"model:" + row["model_id"] for row in manifest["models"]}
    assert {row.owner_id for row in current_mapping.bindings} == owners
    diagnostics = set(mapping["diagnostic_native_case_ids"])
    for owner in sorted(owners):
        owner_rows = tuple(row for row in current_mapping.bindings if row.owner_id == owner)
        leaves = tuple(row for row in owner_rows if not row.required_child_case_ids)
        aggregates = tuple(row for row in owner_rows if row.case_kind == "boundary" and row.required_child_case_ids)
        assert len(aggregates) == 1
        children = {native for row in leaves for native in row.native_case_ids}
        added = {
            native for row in override_bindings
            if row.owner_id == owner and not row.required_child_case_ids
            for native in row.native_case_ids
        }
        if owner in _R6_AGGREGATE_CHILDREN:
            assert children == set(_R6_AGGREGATE_CHILDREN[owner]) | added
        assert children
        assert set(aggregates[0].required_child_case_ids) == children
        assert not children & diagnostics
        assert all(not child.startswith("model:") for child in children)
        if owner in _R6_AGGREGATE_CHILDREN:
            prefix = "case:model_maturation_loop:" if owner == "model:model_maturation_loop" else "native-scenario:" + owner.removeprefix("model:") + ":"
            assert all(child.startswith(prefix) for child in children)
        aggregate = aggregates[0]
        fixture_rows = (*leaves, aggregate)
        results_by_id = {
            native: _r6_fixture_result(row, native)
            for row in fixture_rows for native in row.native_case_ids
        }
        report = verify_native_case_bindings(fixture_rows, tuple(results_by_id.values()))
        assert report.ok, report.findings

        distinct_assertion = next((row for row in leaves
                                   if set(row.protected_failure_ids) - set(row.expected_finding_codes)), None)
        if distinct_assertion is not None:
            native_id = distinct_assertion.native_case_ids[0]
            result = results_by_id[native_id]
            assert set(result.observed_finding_codes) == (
                set(distinct_assertion.expected_finding_codes) | set(distinct_assertion.protected_failure_ids)
            )
            # Keeping the genuine invariant finding cannot stand in for the
            # separately required protected-failure assertion (and vice versa).
            report = verify_native_case_bindings((distinct_assertion,), (
                replace(result, observed_finding_codes=distinct_assertion.expected_finding_codes),
            ))
            assert not report.ok
            assert any(item.startswith("binding_protected_failure_missing:") for item in report.findings)
            report = verify_native_case_bindings((distinct_assertion,), (
                replace(result, observed_finding_codes=distinct_assertion.protected_failure_ids),
            ))
            assert not report.ok
            assert any(item.startswith("binding_finding_code_missing:") for item in report.findings)

        if owner in _R6_AGGREGATE_CHILDREN:
            assert added
        checked_children = sorted(added) if added else [sorted(children)[0]]
        for missing in checked_children:
            absent = tuple(result for native, result in results_by_id.items() if native != missing)
            report = verify_native_case_bindings(fixture_rows, absent)
            assert not report.ok
            assert any(item.startswith("binding_child_result_missing:") and item.endswith(":" + missing) for item in report.findings)

        child = checked_children[0]
        foreign = tuple(
            replace(result, owner_id="model:foreign") if native == child else result
            for native, result in results_by_id.items()
        )
        assert not verify_native_case_bindings(fixture_rows, foreign).ok
        missing_child = tuple(
            replace(result, child_case_ids=tuple(item for item in result.child_case_ids if item != child))
            if native in aggregate.native_case_ids else result
            for native, result in results_by_id.items()
        )
        report = verify_native_case_bindings(fixture_rows, missing_child)
        assert not report.ok
        assert any(item.startswith("binding_children_mismatch:") for item in report.findings)
        diagnostic = tuple(
            replace(result, child_case_ids=(*result.child_case_ids, "diagnostic:unasserted"))
            if native in aggregate.native_case_ids else result
            for native, result in results_by_id.items()
        )
        report = verify_native_case_bindings(fixture_rows, diagnostic)
        assert not report.ok
        assert any(item.startswith("binding_children_mismatch:") for item in report.findings)


def test_positive_regression_guard_is_not_negative_protected_failure():
    from dataclasses import replace
    from flowguard.model_purpose import ModelPurposeClosure
    from flowguard.native_case_protocol import verify_native_case_bindings

    root, _, _, bindings = _r6_source_binding_fixtures()
    positive_labels = {
        "case:authoritative_model_system:faithful_current_with_improvement_gaps": "failure:authoritative_model_system:bad_architecture_hidden_for_acceptance",
        "case:model_maturation_loop:generic_duplicate_responsibility_direction": "failure:model_maturation_loop:cross_boundary_duplicate_method_missed",
        "case:model_maturation_loop:disjoint_context_variant_preserved": "failure:model_maturation_loop:legitimate_context_variant_merged",
    }
    negative_failures = {
        "case:authoritative_model_system:trace_projection_cannot_claim_full_graph": "failure:authoritative_model_system:trace_only_map_accepted",
        "case:authoritative_model_system:native_hard_failure_cannot_be_improvement": "failure:authoritative_model_system:hard_failure_reclassified",
        "case:authoritative_model_system:scoped_graph_not_whole_software_confidence": "failure:authoritative_model_system:self_declared_denominator_hides_writer",
        "case:model_maturation_loop:identical_copy_not_shared_primary": "failure:model_maturation_loop:hash_copy_claimed_shared_mechanism",
        "case:model_maturation_loop:required_architecture_gap_blocks_completion": "failure:model_maturation_loop:accepted_observation_claimed_improvement_done",
    }
    new_sources = set(positive_labels) | set(negative_failures)
    extension = {row.blueprint_source_case_id: row for row in bindings if row.blueprint_source_case_id in new_sources}
    assert set(extension) == new_sources
    for source, label in positive_labels.items():
        row = extension[source]
        assert row.expected_observed_status == "ok"
        assert not row.protected_failure_ids and not row.expected_finding_codes
        result = _r6_fixture_result(row, row.native_case_ids[0])
        assert verify_native_case_bindings((row,), (result,)).ok
        counterfeit_negative = replace(row, protected_failure_ids=(label,), expected_finding_codes=(label,), expected_observed_status="violation")
        report = verify_native_case_bindings((counterfeit_negative,), (result,))
        assert not report.ok
        assert any(item.startswith("binding_protected_failure_missing:") for item in report.findings)

    for source, failure in negative_failures.items():
        row = extension[source]
        assert row.expected_observed_status == "violation"
        assert row.protected_failure_ids == row.expected_finding_codes == (failure,)
        result = _r6_fixture_result(row, row.native_case_ids[0])
        assert verify_native_case_bindings((row,), (result,)).ok
        for observed in ("violation", "ok"):
            report = verify_native_case_bindings((row,), (replace(result, observed_status=observed, observed_finding_codes=()),))
            assert not report.ok
            assert any(item.startswith("binding_protected_failure_missing:") for item in report.findings)
        oracle_rows = tuple({**oracle, "ok": False} for oracle in result.oracle_results)
        assert not verify_native_case_bindings((row,), (replace(result, oracle_results=oracle_rows),)).ok

    manifest = json.loads((root / ".flowguard/models/regression-manifest.json").read_text(encoding="utf-8"))
    # The R6 case labels are historical; this inventory is the actual current
    # Source manifest, including three independently declared native owners.
    assert len(manifest["models"]) == 54
    assert {"python_function_state_verification", "problem_corpus_coverage", "evidence_storage_lifecycle"} <= {
        row["model_id"] for row in manifest["models"]
    }
    all_protected = set()
    closures = {}
    for row in manifest["models"]:
        closure = ModelPurposeClosure.from_dict(row["purpose_closure"])
        closure.validate_current_files(root, model_path=row["model_path"], runner_path=row["runner"][1])
        all_protected.update(closure.protected_failure_ids)
        closures[row["model_id"]] = closure
    assert not set(positive_labels.values()) & all_protected
    for source, failure in negative_failures.items():
        owner = extension[source].owner_id.removeprefix("model:")
        protected = tuple(item for item in closures[owner].failure_bindings if item.failure_id == failure)
        assert len(protected) == 1
        assert protected[0].known_bad_case_id == source
        assert protected[0].expected_case_kind == "bad"


def _r8_current_material(root):
    from flowguard.native_case_runner import write_r8_finite_native_fixture, build_r8_finite_architecture_declaration
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint
    write_r8_finite_native_fixture(root)
    path = ".flowguard/models/owners/alpha/model.py"
    source = compile_declared_path_quality_source(model_id="alpha", model_instance_fingerprint=_fp("actual-finite-instance"),
        source_refs=({"path": path, "source_fingerprint": functional_source_fingerprint(root, path)},),
        graph_scope="native_check_contract", declared_contracts={"finite-integer": {"inputs": [-1, 0, 1, "invalid"]}})
    return build_r8_finite_architecture_declaration(root, source)


def test_r8_architecture_material_parses_exact_current_wire(tmp_path):
    from copy import deepcopy
    from flowguard.native_case_protocol import parse_native_architecture_material
    declaration = _r8_current_material(tmp_path)
    raw = declaration.architecture_material
    assert parse_native_architecture_material(raw) == raw
    assert len(raw["native_case_contracts"]) == 2
    assert len(raw["responsibility_context_rows"]) == 23 * 3
    for mutation in ("extra", "missing", "duplicate", "scalar", "nan", "receipt", "unknown_case", "forged_identity"):
        changed = deepcopy(raw)
        if mutation == "extra": changed["unregistered"] = True
        elif mutation == "missing": changed["responsibility_context_rows"].pop()
        elif mutation == "duplicate": changed["responsibility_context_rows"].append(deepcopy(changed["responsibility_context_rows"][0]))
        elif mutation == "scalar": changed["source_refs"] = "not an array"
        elif mutation == "nan": changed["binding_report"]["findings"] = [float("nan")]
        elif mutation == "receipt": changed["binding_report"]["findings"] = [{"owner_receipt_id": "receipt:self"}]
        elif mutation == "unknown_case": changed["responsibility_context_rows"][0]["source_case_ids"] = ["case:foreign:never_executed"]
        else: changed["native_case_contracts"][0]["contract_fingerprint"] = _fp("forged")
        with pytest.raises((ValueError, TypeError), match=".+"):
            parse_native_architecture_material(changed)


def test_r8_native_current_wire_roundtrips_and_rejects_coercion():
    contract = _good_contract()
    assert NativeModelCaseContract.from_dict(contract.to_dict()) == contract
    result = _result(contract)
    assert NativeModelCaseResult.from_dict(result.to_dict()) == result
    binding = NativeCaseBinding(contract.owner_id, "blueprint:good", "source:good", (contract.source_case_id,),
        contract.case_kind, contract.evidence_scope, contract.covered_dimensions, contract.expected_status)
    assert NativeCaseBinding.from_dict(binding.to_dict()) == binding
    for cls, wire in ((NativeModelCaseContract, contract.to_dict()), (NativeModelCaseResult, result.to_dict()), (NativeCaseBinding, binding.to_dict())):
        bad = dict(wire); bad["legacy_schema"] = True
        with pytest.raises(NativeCaseProtocolError): cls.from_dict(bad)
        bad = dict(wire)
        array = "executed_dimensions" if cls is NativeModelCaseResult else "covered_dimensions"
        bad[array] = "input"
        with pytest.raises(NativeCaseProtocolError): cls.from_dict(bad)
        bad = dict(wire); bad[array] = list(wire[array]) + [wire[array][0]]
        with pytest.raises(NativeCaseProtocolError): cls.from_dict(bad)


def test_r9_real_source_material_requires_complete_current_context_and_native_owner():
    from copy import deepcopy
    from tests.test_native_case_runner import _r9_current_source_declaration
    from flowguard.native_case_protocol import parse_native_architecture_material
    for model in ("authoritative_model_system", "model_maturation_loop"):
        raw = _r9_current_source_declaration(model).architecture_material
        assert parse_native_architecture_material(raw) == raw
        assert len(raw["code_contracts"]) == 6
        assert len(raw["native_case_contracts"]) == (4 if model == "authoritative_model_system" else 2)
        for mutation in ("missing_context", "foreign_owner", "forged_contract", "receipt"):
            changed = deepcopy(raw)
            if mutation == "missing_context": changed["responsibility_context_rows"].pop()
            elif mutation == "foreign_owner": changed["native_case_contracts"][0]["owner_id"] = "model:foreign"
            elif mutation == "forged_contract": changed["native_case_contracts"][0]["contract_fingerprint"] = _fp("forged-r9")
            else: changed["accepted_head"] = {"head_id": "constructed"}
            with pytest.raises((ValueError, TypeError), match=".+"):
                parse_native_architecture_material(changed)
