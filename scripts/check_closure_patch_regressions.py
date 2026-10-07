"""Run the one finite, source-bound regression batch used by completion repair.

This is deliberately a narrow evidence producer.  It does not acquire a
completion-cycle reservation, invoke a full owner, write a terminal owner
receipt, or retry a failed batch.  The batch is the single place where the
repair admission evidence gets its exact node, input, and process identity.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.model_regressions import ModelRegressionManifest  # noqa: E402
from flowguard.process_supervision import run_supervised  # noqa: E402
from flowguard.validation_ownership import (  # noqa: E402
    manifest_fingerprint,
    validation_input_manifest,
)
from scripts.check_flowguard_skill_suite import _pytest_junit_projection  # noqa: E402


SCHEMA = "flowguard.closure_patch_regression.v1"
REVIEW_SCHEMA = "flowguard.model_review_map.v1"
CHANGE_MANIFEST_SCHEMA = "flowguard.patch_change_manifest.v1"
CHANGE_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "work_id",
        "root",
        "baseline_input_manifest",
        "current_input_manifest",
        "changed_paths",
    }
)
TARGET_TEST_FILES = (
    "tests/test_closure_input_boundaries.py",
    "tests/test_closure_patch_review_map.py",
    "tests/test_boundary_authority_closure.py",
    "tests/test_direct_rebuild_candidate_coherence.py",
    "tests/test_direct_rebuild_added_model_intent.py",
    "tests/test_task_progress_input_boundary.py",
    "tests/test_readiness_semantic_identity.py",
    "tests/test_completion_repair_admission.py",
    "tests/test_light_read_boundary.py",
    "tests/test_existing_model_preflight.py",
    "tests/test_completion_epoch.py",
    "tests/test_completion_repair_cli.py",
    "tests/test_full_completion_readiness.py",
    "tests/test_validation_owner_execution.py",
    "tests/test_model_authority.py",
    "tests/test_model_authority_store.py",
    "tests/test_consumer_current_lifecycle.py",
    "tests/test_model_revision_builder.py",
    "tests/test_model_revision_owner_evidence.py",
    "tests/test_model_parent_consumer_identity.py",
    "tests/test_flowguard_agent_workflow_rehearsal.py",
    "tests/test_development_process_simulator.py",
    "tests/test_model_regression_orchestrator.py",
    "tests/test_flowguard_skill_trigger.py",
    "tests/test_route_topology_governance.py",
    "tests/test_skill_suite_inventory.py",
    "tests/test_pytest_shard_runner.py",
    "tests/test_pytest_shards.py",
    "tests/test_python_function_state_verification_owner.py",
    "tests/test_evidence_storage_lifecycle_owner.py",
    "tests/test_flowguard_normative_registration.py",
    "tests/test_compile_native_case_mapping.py",
    "tests/test_self_blueprint.py",
)


ARCHITECTURE_TEST_NODES = (
    'tests/test_full_validation_composition.py::test_full_cli_plan_only_uses_public_release_lifecycle',
    'tests/test_full_validation_composition.py::test_full_cli_conflicting_operations_return_invalid_without_dispatch',
    'tests/test_full_validation_composition.py::test_full_cli_blocked_profile_never_dispatches',
    'tests/test_public_behavior_surface_audit.py::test_reverse_audit_cache_never_crosses_calls_and_keeps_every_failed_row',
    'tests/test_public_behavior_surface_audit.py::test_reverse_audit_reuses_test_file_parse_and_receipt_read_per_invocation',
    'tests/test_public_behavior_surface_audit.py::test_reverse_reference_errors_preserve_missing_anchor_parse_and_escape',
    'tests/test_public_behavior_surface_audit.py::test_reverse_test_reference_anchor_semantics_remain_exact',
    'tests/test_reverse_surface_current_identity.py::test_registration_identity_join_keeps_native_owner_receipt_gate',
    'tests/test_reverse_surface_current_identity.py::test_registration_identity_join_rejects_broad_required_and_stale_claims',
    'tests/test_self_path_quality_runner_projection.py::test_all_51_declared_ports_pass_actual_path_quality_consumer',
    'tests/test_model_system_inventory.py::ModelSystemInventoryTests::test_repository_snapshot_materializes_authored_semantic_hierarchy',
    'tests/test_model_system_inventory.py::ModelSystemInventoryTests::test_repository_snapshot_has_no_owner_coverage_gaps',
    'tests/test_reverse_surface_map_identity.py::test_reverse_audit_rejects_foreign_route_with_current_model_and_receipt',
    'tests/test_reverse_surface_map_identity.py::test_reverse_audit_accepts_declared_multi_model_supervisor',
    'tests/test_reverse_surface_map_identity.py::test_reverse_owner_builder_rejects_foreign_route_before_evidence_writes',
    'tests/test_reverse_surface_map_identity.py::test_reverse_route_model_guard_accepts_multi_model_groups_and_surfaces',
    'tests/test_public_api_surface.py::PublicApiSurfaceTests::test_missing_declared_lazy_export_does_not_select_another_owner',
    'tests/test_public_api_surface.py::PublicApiSurfaceTests::test_declared_lazy_owner_import_error_is_preserved',
    'tests/test_executable_corpus.py::ExecutableCorpusTests::test_failed_result_blocks_aggregate_confidence',
    'tests/test_executable_corpus.py::ExecutableCorpusTests::test_unknown_result_status_is_not_accepted_as_complete',
    'tests/test_model_path_quality.py::test_missing_goal_fact_preserves_exact_model_action_pointer',
    'tests/test_model_path_quality.py::test_scope_evidence_shape_preserves_current_typed_identity_without_self_cycle',
    'tests/test_model_maturation.py::test_verified_maturation_still_needs_each_requested_outcome',
    'tests/test_model_maturation.py::test_model_policy_case_does_not_close_implementation_outcome',
    'tests/test_consumer_current_lifecycle.py::test_public_change_rejects_foreign_architecture_responsibility_owner',
    'tests/test_consumer_current_lifecycle.py::test_public_change_cannot_discard_unassigned_required_architecture_goal',
    'tests/test_consumer_current_lifecycle.py::test_current_and_normative_direction_are_not_collapsed',
    'tests/test_consumer_current_lifecycle.py::test_public_change_binds_complete_effective_intent',
    'tests/test_consumer_current_lifecycle.py::test_public_change_never_falls_back_to_trace_graph',
    'tests/test_consumer_current_lifecycle.py::test_public_observation_map_can_retain_improvement_debt',
    'tests/test_model_authority_store.py::test_goal_read_is_affected_only_zero_producers_zero_writes',
    'tests/test_model_authority_store.py::test_scoped_graph_read_does_not_claim_whole_software_understanding',
    'tests/test_model_authority_store.py::test_selected_read_preserves_required_goal_and_current_gap',
    'tests/test_model_intent.py::test_architecture_objective_source_scope_and_conflict_are_exact',
    'tests/test_model_intent.py::test_objective_projection_preserves_existing_contribution_and_mapping_wire',
    'tests/test_model_maturation.py::test_architecture_direction_has_no_unrestricted_optimum_claim',
    'tests/test_model_maturation.py::test_generic_architecture_direction_uses_current_facts_and_finite_goal',
    'tests/test_model_maturation.py::test_required_architecture_gap_blocks_improvement_completion',
    'tests/test_model_maturation_receipt.py::test_observation_acceptance_is_not_required_architecture_closure',
    'tests/test_model_path_quality.py::test_check_contract_does_not_license_software_architecture',
    'tests/test_model_path_quality.py::test_consistent_declared_omission_does_not_close_software_architecture',
    'tests/test_model_path_quality.py::test_cross_model_same_semantics_same_context_yields_rewrite_candidate',
    'tests/test_model_path_quality.py::test_declared_graph_keeps_unobserved_and_unreachable_elements',
    'tests/test_model_path_quality.py::test_declared_source_groundings_are_exact_current',
    'tests/test_model_path_quality.py::test_disjoint_context_variants_are_not_merged',
    'tests/test_model_path_quality.py::test_equivalent_provider_representations_do_not_create_method_conflict',
    'tests/test_model_path_quality.py::test_explicit_layer_objective_yields_normative_direction',
    'tests/test_model_path_quality.py::test_gap_projection_preserves_existing_result_wire_and_fingerprint',
    'tests/test_model_path_quality.py::test_hard_behavior_difference_is_false_friend',
    'tests/test_model_path_quality.py::test_identical_copies_do_not_satisfy_shared_mechanism_objective',
    'tests/test_model_path_quality.py::test_model_policy_proof_is_not_implementation_equivalence',
    'tests/test_model_path_quality.py::test_no_objective_does_not_invent_single_owner',
    'tests/test_model_path_quality.py::test_self_declared_matching_hashes_do_not_establish_equivalence',
    'tests/test_model_path_quality.py::test_single_primary_with_two_current_delegates_satisfies_shared_mechanism',
    'tests/test_model_path_quality.py::test_trace_is_not_declared_graph_authority',
    'tests/test_model_path_quality.py::test_unknown_gap_code_blocks_observation',
    'tests/test_model_path_quality.py::test_wrong_native_owner_case_or_oracle_cannot_prove_semantic_relation',
    'tests/test_model_revision_builder.py::test_faithful_current_with_structural_gap_accepts_observation_once',
    'tests/test_model_revision_builder.py::test_generation108_current_wire_loads_before_r6_preflight_and_cas',
    'tests/test_model_revision_builder.py::test_observation_split_does_not_weaken_native_failure_gates',
    'tests/test_native_case_protocol.py::test_aggregate_closure_contains_exact_override_leaf_union',
    'tests/test_native_case_protocol.py::test_positive_regression_guard_is_not_negative_protected_failure',
    'tests/test_native_case_runner.py::test_boundary_leaf_is_not_synthetic_aggregate',
    'tests/test_native_case_runner.py::test_declared_source_export_occurs_once_in_native_episode',
    'tests/test_native_case_runner.py::test_native_owner_requires_exactly_one_boundary_aggregate',
    'tests/test_self_path_quality_runner_projection.py::test_all_51_owners_have_exact_declared_source_port',
    'tests/test_self_path_quality_runner_projection.py::test_exporter_does_not_execute_native_checks',
    'tests/test_self_path_quality_runner_projection.py::test_provider_scope_remains_honest_for_native_contract_models',
    'tests/test_model_path_quality.py::test_cost_bound_requires_independently_admitted_measurement',
    'tests/test_model_maturation.py::test_function_scope_closes_without_unrelated_architecture_expansion',
    'tests/test_model_maturation.py::test_unverified_blueprint_summary_cannot_promote_functional_depth',
    'tests/test_model_maturation.py::test_missing_function_obligation_blocks_stopping',
    'tests/test_model_authority_store.py::test_required_objective_scope_is_not_intersected_down',
    'tests/test_model_maturation.py::test_scoped_out_or_iteration_limit_is_not_function_completion',
    'tests/test_model_path_quality.py::test_independent_writer_inventory_exposes_consistently_omitted_model_element',
    'tests/test_model_path_quality.py::test_partial_context_overlap_preserves_each_variant_remainder',
    'tests/test_model_path_quality.py::test_missing_semantic_proof_yields_exact_evidence_pointer',
    'tests/test_model_path_quality.py::test_architecture_suggestion_names_exact_function_obligations_and_native_owner',
    'tests/test_model_intent.py::test_current_compromise_is_visible_without_closing_required_goal',
    'tests/test_model_intent.py::test_only_current_source_supersession_changes_compromise_goal',
    'tests/test_existing_model_preflight.py::test_full_selected_preflight_never_audits_unrelated_global_authority',
    'tests/test_light_read_boundary.py::test_public_selected_read_shares_current_source_bytes_with_architecture',
    'tests/test_model_authority_store.py::test_selected_read_consumes_authenticated_whole_scope_proof_without_producers',
    'tests/test_light_read_boundary.py::test_new_architecture_pointers_and_scope_proofs_are_exact_across_pages',
    'tests/test_model_path_quality.py::test_derived_architecture_output_has_no_subject_identity_cycle',
    'tests/test_model_path_quality.py::test_native_pointer_join_reads_shared_artifacts_once_per_invocation',
    'tests/test_model_intent.py::test_current_source_observation_is_byte_bound_and_hashed_once',
    'tests/test_model_maturation.py::test_other_function_binding_cannot_satisfy_current_invariant_outcome',
    'tests/test_model_intent.py::test_architecture_source_newlines_preserve_verified_objective_and_compromise_projection',
    'tests/test_model_intent.py::test_architecture_source_newlines_do_not_admit_missing_duplicate_or_malformed_fences',
)

def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_once(path: Path, payload: Mapping[str, Any]) -> None:
    if path.is_symlink():
        raise RuntimeError(f"refusing to write through symlink: {path}")
    data = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != data:
            raise RuntimeError(f"output already exists with different content: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def _assert_output_root(root: Path, output_dir: Path) -> None:
    try:
        output_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("--output-dir must remain inside --root") from exc
    if output_dir.is_symlink():
        raise ValueError("--output-dir must not be a symlink/reparse path")


def _normalise_relative_path(value: object, field_name: str) -> str:
    path = str(value or "").replace("\\", "/").strip()
    if not path or path.startswith("/") or ":" in path.split("/", 1)[0]:
        raise ValueError(f"{field_name} must be a project-relative path")
    parts = tuple(part for part in path.split("/") if part)
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError(f"{field_name} contains an unsafe path: {path}")
    return "/".join(parts)


def _normalise_manifest_rows(value: object, field_name: str) -> tuple[dict[str, str], ...]:
    """Validate one explicit path/fingerprint input table.

    Change manifests are supplied evidence, not a convenience hint.  Keep the
    wire shape deliberately small and deterministic so a handoff agent cannot
    manufacture an affected set by changing only the declared ``changed_paths``.
    """

    if not isinstance(value, list):
        raise ValueError(f"change manifest {field_name} must be an array")
    rows: dict[str, str] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping) or set(raw) != {"path", "sha256"}:
            raise ValueError(
                f"change manifest {field_name}[{index}] must contain only path and sha256"
            )
        relative = _normalise_relative_path(raw.get("path"), f"{field_name}[{index}].path")
        fingerprint = str(raw.get("sha256") or "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint):
            raise ValueError(
                f"change manifest {field_name}[{index}].sha256 must be sha256"
            )
        previous = rows.get(relative)
        if previous is not None:
            if previous != fingerprint:
                raise ValueError(
                    f"change manifest {field_name} contains conflicting path rows: {relative}"
                )
            raise ValueError(
                f"change manifest {field_name} contains duplicate path rows: {relative}"
            )
        rows[relative] = fingerprint
    return tuple(
        {"path": path, "sha256": rows[path]}
        for path in sorted(rows)
    )


def _change_manifest_fingerprint(payload: Mapping[str, Any]) -> str:
    body = {
        key: payload[key]
        for key in sorted(CHANGE_MANIFEST_FIELDS)
        if key in payload
    }
    return _sha256_text(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _load_change_manifest(
    path: Path,
    root: Path,
    *,
    live_current_manifest: tuple[dict[str, str], ...] | None = None,
) -> dict[str, Any]:
    """Load the explicit planned source delta for one finite batch.

    The manifest is an input to this batch, never a generated claim.  Its
    content is deliberately small and exact so an empty list means
    ``no_semantic_change`` rather than an implicit all-model authorization.
    """

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"change manifest is missing or symlinked: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"change manifest is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("change manifest must be a JSON object")
    missing = sorted(CHANGE_MANIFEST_FIELDS - set(payload))
    if missing:
        raise ValueError(f"change manifest is missing fields: {missing}")
    if set(payload) != CHANGE_MANIFEST_FIELDS:
        unknown = sorted(set(payload) - CHANGE_MANIFEST_FIELDS)
        raise ValueError(f"change manifest has unknown fields: {unknown}")
    if payload.get("schema") != CHANGE_MANIFEST_SCHEMA:
        raise ValueError("change manifest schema is not current")
    work_id = str(payload.get("work_id") or "").strip()
    if not work_id:
        raise ValueError("change manifest work_id is required")
    declared_root = str(payload.get("root") or "").strip()
    if not declared_root or not Path(declared_root).is_absolute():
        raise ValueError("change manifest root must be an absolute path")
    if Path(declared_root).resolve() != root.resolve():
        raise ValueError("change manifest root does not match the requested root")
    baseline = _normalise_manifest_rows(
        payload.get("baseline_input_manifest"), "baseline_input_manifest"
    )
    current = _normalise_manifest_rows(
        payload.get("current_input_manifest"), "current_input_manifest"
    )
    raw_paths = payload.get("changed_paths")
    if not isinstance(raw_paths, list):
        raise ValueError("change manifest changed_paths must be an array")
    changed_paths = tuple(
        sorted({_normalise_relative_path(item, "changed_paths") for item in raw_paths})
    )
    baseline_by_path = {row["path"]: row["sha256"] for row in baseline}
    current_by_path = {row["path"]: row["sha256"] for row in current}
    computed_paths = tuple(
        sorted(
            path
            for path in set(baseline_by_path) | set(current_by_path)
            if baseline_by_path.get(path) != current_by_path.get(path)
        )
    )
    if changed_paths != computed_paths:
        raise ValueError(
            "change manifest changed_paths does not match baseline/current input tables"
        )
    live_current = (
        live_current_manifest
        if live_current_manifest is not None
        else validation_input_manifest(root)
    )
    if tuple(live_current) != current:
        raise ValueError(
            "change manifest current_input_manifest is stale or does not match live inputs"
        )
    for relative in set(changed_paths) | set(current_by_path) | set(baseline_by_path):
        resolved = (root / relative).resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError(f"change manifest path escapes project root: {relative}")
    return {
        "schema": CHANGE_MANIFEST_SCHEMA,
        "changed_paths": changed_paths,
        "work_id": work_id,
        "root": str(root.resolve()),
        "baseline_input_manifest": baseline,
        "current_input_manifest": current,
        "change_manifest_fingerprint": _change_manifest_fingerprint(payload),
        "path": str(path),
    }


def _model_review_map(
    root: Path,
    changed_paths: tuple[str, ...],
    tested_manifest: tuple[dict[str, str], ...],
    *,
    planned_changed_paths: tuple[str, ...] | None = None,
    change_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic review map from the registered native manifest.

    A shared core source can feed many owners.  The map therefore computes the
    affected owner set from each registered entry's declared input patterns;
    it never asks the handoff agent to inspect relation ids or guess from an
    owner-name substring.
    """

    manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
    model_manifest = ModelRegressionManifest.load(root)
    rows: list[dict[str, Any]] = []
    allowed: set[str] = set()
    for entry in model_manifest.entries:
        if entry.excluded:
            continue
        # Keep the review map's affected-owner projection identical to the
        # model impact map used by the authoritative rebuild.  A shared input
        # component is a real edge to every declared consumer; omitting it
        # here creates a false "small" review map that the official builder
        # must reject later when it sees the same changed path through
        # ``shared_input_groups``.  That mismatch used to make a legitimate
        # shared-registry refresh look like an unexplained closure failure.
        shared_pattern_owner = getattr(
            model_manifest,
            "owner_patterns_for",
            model_manifest.shared_patterns_for,
        )
        patterns = tuple(
            dict.fromkeys(
                (
                    *(
                        str(item).replace("\\", "/")
                        for item in entry.effective_input_patterns
                    ),
                    *(
                        str(item).replace("\\", "/")
                            for item in shared_pattern_owner(entry.model_id)
                    ),
                )
            )
        )
        matched = tuple(
            path
            for path in changed_paths
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
        )
        if matched:
            allowed.add(entry.model_id)
            rows.append(
                {
                    "model_id": entry.model_id,
                    "disposition": "review_changed_inputs",
                    "matched_paths": list(sorted(set(matched))),
                    "input_patterns": list(patterns),
                }
            )
    # The observed model system also owns the typed
    # ``semantic-system-contains`` relations.  Its relation fingerprint is
    # derived from the current source-input manifest, so any non-empty source
    # delta changes that topology owner even when its authored model file has
    # no direct path match.  Mirror the official revision builder's explicit
    # topology-owner rule here; otherwise a review map can be path-complete
    # yet still be rejected for an unlicensed relation change.
    semantic_source_delta = any(
        path.startswith("flowguard/")
        or path.startswith(".flowguard/models/")
        or path.startswith(".flowguard/structure/")
        for path in changed_paths
    )
    if semantic_source_delta and any(
        not entry.excluded and entry.model_id == "authoritative_model_system"
        for entry in model_manifest.entries
    ):
        if "authoritative_model_system" not in allowed:
            allowed.add("authoritative_model_system")
            rows.append(
                {
                    "model_id": "authoritative_model_system",
                    "disposition": "review_changed_topology",
                    "matched_paths": [],
                    "input_patterns": [],
                }
            )
        # A semantic source delta does not authorize every registered model.
        # The typed candidate snapshot/relation owner is the only authority
        # that can add a topology owner.  This finite map may authorize only
        # direct declared input consumers; otherwise one changed framework
        # file would manufacture an all-model review and restart the entire
        # closure.
    # An empty functional delta is an explicit no-op.  It must not authorize
    # every model merely because a caller is preparing a candidate package.
    decision = "no_semantic_change" if not changed_paths else "review_changed_inputs_only"
    payload: dict[str, Any] = {
        "schema_version": REVIEW_SCHEMA,
        "scope": "patch_regression",
        "root": str(root.resolve()),
        "work_id": str((change_manifest or {}).get("work_id", "")),
        "changed_paths": list(changed_paths),
        "planned_changed_paths": list(planned_changed_paths if planned_changed_paths is not None else changed_paths),
        "tested_input_manifest": [dict(row) for row in tested_manifest],
        "tested_input_manifest_fingerprint": manifest_fingerprint(tested_manifest),
        "allowed_model_ids": sorted(allowed),
        "model_decisions": sorted(rows, key=lambda row: str(row["model_id"])),
        "decision": decision,
        "claim_boundary": (
            "This map is a source-bound review input for one finite patch batch; "
            "it is not model pass evidence or current-authority activation."
        ),
    }
    if change_manifest is not None:
        payload["change_manifest_fingerprint"] = str(
            change_manifest.get("change_manifest_fingerprint", "")
        )
        payload["baseline_input_manifest"] = [
            dict(row) for row in change_manifest.get("baseline_input_manifest", ())
        ]
        payload["current_input_manifest"] = [
            dict(row) for row in change_manifest.get("current_input_manifest", ())
        ]
    payload["review_map_fingerprint"] = _sha256_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return payload


def _blocked(
    root: Path,
    output_dir: Path,
    reason: str,
    before: tuple[dict[str, str], ...],
    *,
    planned_changed_paths: tuple[str, ...] = (),
    observed_drift_paths: tuple[str, ...] = (),
    change_manifest: Mapping[str, Any] | None = None,
) -> int:
    payload = {
        "schema_version": SCHEMA,
        "status": "blocked",
        "ok": False,
        "scope": "patch_regression",
        "tested_input_manifest": [dict(row) for row in before],
        "tested_input_manifest_fingerprint": manifest_fingerprint(before),
        "planned_changed_paths": list(planned_changed_paths),
        "observed_drift_paths": list(observed_drift_paths),
        "changed_input_fingerprints": list(observed_drift_paths),
        "argv": [],
        "nodeids": [],
        "collection_fingerprint": "",
        "environment": {"platform": sys.platform, "python": sys.executable},
        "exit_code": 70,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "report_sha256": "",
        "stdout_sha256": "",
        "stderr_sha256": "",
        "cleanup_confirmed": True,
        "producer_invocations": 0,
        "validation_producer_invocations": 0,
        "full_producer_invocations": 0,
        "change_manifest_path": str(change_manifest.get("path", "")) if change_manifest else "",
        "change_manifest_fingerprint": str(change_manifest.get("change_manifest_fingerprint", "")) if change_manifest else "",
        "blockers": [reason],
        "claim_boundary": "Patch regression was not executed; no completion producer or terminal receipt was started.",
    }
    _write_once(output_dir / "patch-regression.json", payload)
    return 1


def run(
    root: Path,
    output_dir: Path,
    *,
    change_manifest_path: Path | None = None,
) -> int:
    _assert_output_root(root, output_dir)
    before = validation_input_manifest(root)
    if change_manifest_path is None:
        return _blocked(
            root,
            output_dir,
            "change_manifest_required",
            before,
        )
    change_manifest: dict[str, Any] | None = None
    try:
        change_manifest = _load_change_manifest(
            change_manifest_path.resolve(),
            root,
            live_current_manifest=before,
        )
    except (OSError, ValueError, TypeError) as exc:
        return _blocked(root, output_dir, str(exc), before)
    planned_changed_paths = tuple(change_manifest["changed_paths"])
    if tuple(change_manifest["current_input_manifest"]) != before:
        return _blocked(
            root,
            output_dir,
            "change manifest current input observation is stale",
            before,
            planned_changed_paths=planned_changed_paths,
            change_manifest=change_manifest,
        )
    missing = tuple(path for path in TARGET_TEST_FILES if not (root / path).is_file())
    if missing:
        return _blocked(
            root,
            output_dir,
            "required regression test file is missing: " + ", ".join(missing),
            before,
            planned_changed_paths=planned_changed_paths,
            change_manifest=change_manifest,
        )

    collection_path = output_dir / "collection.json"
    nodeids_path = output_dir / "nodeids.json"
    junit_path = output_dir / "pytest-junit.xml"
    stdout_path = output_dir / "stdout.log"
    stderr_path = output_dir / "stderr.log"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "flowguard.pytest_shard_plugin",
        "-p",
        "flowguard.pytest_nodeid_recorder",
        "-m",
        "not flowguard_capability",
        f"--junit-xml={junit_path}",
        *TARGET_TEST_FILES,
        *(node for node in ARCHITECTURE_TEST_NODES if node.split("::", 1)[0] not in TARGET_TEST_FILES),
    ]
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "FLOWGUARD_PYTEST_COLLECTION_NODEIDS": str(collection_path),
            "FLOWGUARD_PYTEST_NODEIDS": str(nodeids_path),
        }
    )
    result = run_supervised(command, cwd=root, timeout_seconds=1800.0, environment=environment)
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    after = validation_input_manifest(root)
    changed = tuple(
        sorted(
            {
                str(row["path"])
                for row in before
                if next((item["sha256"] for item in after if item["path"] == row["path"]), "") != row["sha256"]
            }
            | {str(row["path"]) for row in after if not any(item["path"] == row["path"] for item in before)}
        )
    )
    # Source/test/config changes during the finite regression invalidate this
    # evidence.  Generated reports are excluded by validation_input_manifest,
    # so they cannot create a self-referential freshness loop.
    if changed:
        return _blocked(
            root,
            output_dir,
            "validation_input_drift_during_patch_regression",
            before,
            planned_changed_paths=planned_changed_paths,
            observed_drift_paths=changed,
            change_manifest=change_manifest,
        )
    projection = _pytest_junit_projection(
        junit_path,
        nodeid_manifest=nodeids_path,
        require_exact_nodeids=True,
    )
    collection = {}
    if collection_path.is_file():
        collection = json.loads(collection_path.read_text(encoding="utf-8"))
    projection = projection or {}
    review_map = _model_review_map(
        root,
        planned_changed_paths,
        before,
        planned_changed_paths=planned_changed_paths,
        change_manifest=change_manifest,
    )
    review_path = output_dir / "review-map.json"
    _write_once(review_path, review_map)
    semantic_pass = bool(
        result.exit_code == 0
        and result.cleanup_confirmed
        and not result.timed_out
        and not result.cancelled
        and not result.interrupted
        and projection
        and not projection.get("failed")
        and not projection.get("errors")
        and not projection.get("skipped")
        and not changed
    )
    payload = {
        "schema_version": SCHEMA,
        "status": "pass" if semantic_pass else "blocked",
        "ok": semantic_pass,
        "scope": "patch_regression",
        "tested_input_manifest": [dict(row) for row in before],
        "tested_input_manifest_fingerprint": manifest_fingerprint(before),
        "post_run_input_manifest": [dict(row) for row in after],
        "post_run_input_manifest_fingerprint": manifest_fingerprint(after),
        "planned_changed_paths": list(planned_changed_paths),
        "observed_drift_paths": list(changed),
        "changed_input_fingerprints": list(changed),
        "argv": command,
        "nodeids": list(projection.get("node_ids", ())),
        "collection": collection,
        "collection_fingerprint": _sha256_text(json.dumps(collection, ensure_ascii=False, sort_keys=True)),
        "environment": {
            "platform": sys.platform,
            "python": sys.executable,
            "cwd": str(root),
            "pytest_capability_scope": "non_platform",
        },
        "exit_code": result.exit_code,
        "passed": int(projection.get("passed", 0)),
        "failed": int(projection.get("failed", 0)),
        "skipped": int(projection.get("skipped", 0)),
        "report_sha256": _sha256_file(junit_path) if junit_path.is_file() else "",
        "stdout_sha256": _sha256_text(result.stdout),
        "stderr_sha256": _sha256_text(result.stderr),
        "cleanup_confirmed": result.cleanup_confirmed,
        "terminal_reason": result.terminal_reason,
        "producer_invocations": 0,
        "validation_producer_invocations": 1,
        "full_producer_invocations": 0,
        "change_manifest_path": str(change_manifest.get("path", "")) if change_manifest else "",
        "change_manifest_fingerprint": str(change_manifest.get("change_manifest_fingerprint", "")) if change_manifest else "",
        "review_map_path": str(review_path),
        "review_map_fingerprint": review_map["review_map_fingerprint"],
        "blockers": [] if semantic_pass else ["patch_regression_not_pass"],
        "claim_boundary": "This is finite patch-regression evidence only; it never certifies a full owner or current authority.",
    }
    _write_once(output_dir / "patch-regression.json", payload)
    return 0 if semantic_pass else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--change-manifest",
        type=Path,
        help=(
            "Explicit flowguard.patch_change_manifest.v1 input.  It is always "
            "required, including an explicit empty changed_paths no-op."
        ),
    )
    args = parser.parse_args(argv)
    try:
        return run(
            args.root.expanduser().resolve(),
            args.output_dir.expanduser().resolve(),
            change_manifest_path=(
                args.change_manifest.expanduser().resolve()
                if args.change_manifest is not None
                else None
            ),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
