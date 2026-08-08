from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = (
    ROOT / ".flowguard/authoritative_model_system/semantic_self_model.py"
)
MESH_PATH = ROOT / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
MANIFEST_PATH = ROOT / ".flowguard/model-regression-manifest.json"
BLUEPRINT_DEFINITION_PATH = (
    ROOT
    / ".flowguard/authoritative_model_system/software_blueprint_definition.json"
)

SPEC = importlib.util.spec_from_file_location(
    "flowguard_semantic_self_model_direct_current",
    MODEL_PATH,
)
assert SPEC is not None and SPEC.loader is not None
SEMANTIC_MODEL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SEMANTIC_MODEL
SPEC.loader.exec_module(SEMANTIC_MODEL)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _failure_prefixes(payload: dict[str, object]) -> tuple[str, ...]:
    return SEMANTIC_MODEL._review_payload(ROOT, payload).failures


def test_checked_in_mesh_is_exactly_the_current_manifest_universe() -> None:
    payload = _load(MESH_PATH)
    manifest = _load(MANIFEST_PATH)
    base = _load(ROOT / str(payload["derivation_base_snapshot_path"]))

    current_ids = {str(row["model_id"]) for row in manifest["models"]}
    base_ids = {str(row["logical_model_id"]) for row in base["model_instances"]}
    mesh_ids = {str(row["model_id"]) for row in payload["models"]}

    report = SEMANTIC_MODEL.review_semantic_self_mesh(ROOT)
    assert report.ok, report.failures
    assert report.model_count == len(current_ids)
    assert report.parent_count == 7
    expected_relation_count = sum(
        1
        + len(row["cross_boundary_parent_ids"])
        + len(row["consumer_ids"])
        for row in payload["models"]
    )
    assert report.relation_count == expected_relation_count
    assert report.completion_licensed is False
    assert mesh_ids == current_ids
    assert set(payload["observed_base_added_model_ids"]) == current_ids - base_ids
    assert set(payload["observed_base_removed_model_ids"]) == base_ids - current_ids
    assert "candidate_added_model_ids" not in payload
    assert "candidate_removed_model_ids" not in payload


def test_retired_rows_and_dangling_consumers_are_directly_removed() -> None:
    payload = _load(MESH_PATH)
    rows = {str(row["model_id"]): row for row in payload["models"]}
    retired_ids = {
        "ai_surface_streamlining",
        "legacy_compatibility_cleanup",
        "maintenance_scan_router",
        "model_angle_deliberation",
        "model_similarity_consolidation",
        "openspec_archive_cleanup",
        "readme_positioning_20260602",
        "reduce_architecture_surface",
        "release_visibility_process",
        "risk_purpose_header",
        "simplify_field_schema",
        "simplify_flowguard_structure",
        "structure_surface_simplification",
        "template_harvest_closure",
    }

    assert retired_ids.isdisjoint(rows)
    assert rows["existing_model_preflight"]["consumer_ids"] == [
        "model:task_coverage_demand"
    ]
    assert rows["maintenance_obligation_memory"]["consumer_ids"] == [
        "model:development_process_flow"
    ]
    assert rows["model_miss_review"]["consumer_ids"] == [
        "model:model_maturation_loop",
        "model:model_test_code_alignment",
    ]
    assert rows["model_topology_hazard_review"]["consumer_ids"] == [
        "model:model_maturation_loop",
        "model:development_process_flow",
    ]
    assert "model:implementation_blueprint" in rows[
        "authoritative_model_system"
    ]["consumer_ids"]
    assert rows["template_public_release"]["consumer_ids"] == [
        "model:development_process_flow"
    ]
    assert "directly to the DevelopmentProcessFlow owner" in rows[
        "template_public_release"
    ]["rationale"]

    model_edges = {
        (str(row["model_id"]), str(consumer_id).removeprefix("model:"))
        for row in payload["models"]
        for consumer_id in row["consumer_ids"]
        if str(consumer_id).startswith("model:")
    }
    adjacency = {model_id: set() for model_id in rows}
    for producer_id, consumer_id in model_edges:
        adjacency[producer_id].add(consumer_id)
    cyclic_relation_ids = set()
    for producer_id, consumer_id in model_edges:
        pending = [consumer_id]
        visited = set()
        while pending:
            current = pending.pop()
            if current == producer_id:
                cyclic_relation_ids.add(
                    f"topology:{producer_id}:model-obligation:{consumer_id}"
                )
                break
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency[current])

    progress_relation_ids = {
        str(contract["relation_id"])
        for contract in payload["feedback_progress_contracts"]
    }
    assert len(progress_relation_ids) == 15
    assert progress_relation_ids == cyclic_relation_ids
    assert {
        "topology:authoritative_model_system:model-obligation:implementation_blueprint",
        "topology:implementation_blueprint:model-obligation:authoritative_model_system",
        "topology:authoritative_model_system:model-obligation:self_maintenance_mesh",
        "topology:self_maintenance_mesh:model-obligation:authoritative_model_system",
    }.issubset(progress_relation_ids)


def test_new_model_authority_paths_have_exact_current_implementation_owners() -> None:
    definition = _load(BLUEPRINT_DEFINITION_PATH)
    overrides = definition["owner_overrides"]

    assert overrides["flowguard/model_revision_plan.py"] == (
        "authoritative_model_system"
    )
    assert overrides["flowguard/model_intent_authority.py"] == (
        "authoritative_model_system"
    )
    assert overrides["scripts/compile_flowguard_self_blueprint_definition.py"] == (
        "authoritative_model_system"
    )


def test_retired_task_instance_surfaces_delegate_to_current_owners() -> None:
    definition = _load(BLUEPRINT_DEFINITION_PATH)
    overrides = definition["owner_overrides"]
    composite_owner_ids = {
        str(row["owner_id"])
        for row in definition["composite_behavior_contracts"]
    }
    retired_ids = {
        "openspec_archive_cleanup",
        "readme_positioning_20260602",
        "release_visibility_process",
        "risk_purpose_header",
    }

    manifest_owner_ids = {
        str(row["model_id"])
        for row in _load(MANIFEST_PATH)["models"]
    }
    assert composite_owner_ids == manifest_owner_ids
    assert retired_ids.isdisjoint(composite_owner_ids)
    assert retired_ids.isdisjoint(overrides.values())
    assert overrides["flowguard/risk.py"] == "minimum_valuable_model_entry"
    assert overrides["flowguard/risk_evidence_ledger.py"] == (
        "model_maturation_loop"
    )
    assert overrides["flowguard/risk_templates.py"] == "template_public_release"
    assert overrides["flowguard/release_verification.py"] == (
        "development_process_flow"
    )
    assert overrides["scripts/verify_flowguard_release.py"] == (
        "development_process_flow"
    )
    assert overrides["scripts/check_openspec_change.py"] == (
        "development_process_flow"
    )
    assert overrides["scripts/check_openspec_semantic_sync.py"] == (
        "development_process_flow"
    )
    assert overrides["scripts/run_openspec_selected_check.py"] == (
        "test_evidence_mesh"
    )
    assert overrides["scripts/verify_openspec_recorded_check.py"] == (
        "test_evidence_mesh"
    )


def test_native_known_bad_review_rejects_all_six_direct_current_failures() -> None:
    ok, failures = SEMANTIC_MODEL.run_known_bad_review(ROOT)
    assert ok is True
    assert failures == ()


@pytest.mark.parametrize(
    ("case_id", "mutate", "expected_prefix"),
    (
        (
            "missing_current_owner",
            lambda payload: (
                payload["models"].pop(),
                payload.__setitem__(
                    "declared_model_count", payload["declared_model_count"] - 1
                ),
            ),
            "semantic_manifest_coverage_missing",
        ),
        (
            "foreign_owner",
            lambda payload: (
                payload["models"].append(
                    {
                        **copy.deepcopy(payload["models"][-1]),
                        "model_id": "retired_parallel_authority",
                    }
                ),
                payload.__setitem__(
                    "declared_model_count", payload["declared_model_count"] + 1
                ),
            ),
            "semantic_manifest_coverage_foreign",
        ),
        (
            "added_diff_drift",
            lambda payload: payload.__setitem__(
                "observed_base_added_model_ids", ["retired_parallel_authority"]
            ),
            "observed_base_added_model_set_drift",
        ),
        (
            "removed_diff_drift",
            lambda payload: payload.__setitem__("observed_base_removed_model_ids", []),
            "observed_base_removed_model_set_drift",
        ),
        (
            "dangling_consumer",
            lambda payload: payload["models"][0].__setitem__(
                "consumer_ids", ["model:retired_parallel_authority"]
            ),
            "consumer_model_unknown",
        ),
        (
            "cycle_without_progress",
            lambda payload: payload["feedback_progress_contracts"].pop(),
            "feedback_progress_contract_missing",
        ),
    ),
)
def test_direct_current_known_bad_family(
    case_id: str,
    mutate: object,
    expected_prefix: str,
) -> None:
    payload = copy.deepcopy(_load(MESH_PATH))
    mutate(payload)
    failures = _failure_prefixes(payload)
    assert any(failure.startswith(expected_prefix) for failure in failures), (
        case_id,
        failures,
    )


def test_v2_and_legacy_diff_field_are_not_compatibly_read() -> None:
    payload = copy.deepcopy(_load(MESH_PATH))
    payload["schema_version"] = "flowguard.semantic_self_mesh.v2"
    payload["candidate_added_model_ids"] = payload.pop(
        "observed_base_added_model_ids"
    )

    failures = _failure_prefixes(payload)
    assert "schema_version_not_current" in failures
    assert any(
        failure.startswith("required_top_level_fields_missing:")
        and "observed_base_added_model_ids" in failure
        for failure in failures
    )
    assert any(
        failure.startswith("unknown_top_level_fields:")
        and "candidate_added_model_ids" in failure
        for failure in failures
    )


@pytest.mark.parametrize(
    "fingerprint_field",
    (
        "semantic_universe_fingerprint",
        "semantic_disposition_fingerprint",
        "semantic_relation_fingerprint",
    ),
)
def test_each_semantic_fingerprint_is_recomputed(
    fingerprint_field: str,
) -> None:
    payload = copy.deepcopy(_load(MESH_PATH))
    payload[fingerprint_field] = "sha256:" + "0" * 64
    failures = _failure_prefixes(payload)
    assert f"{fingerprint_field}_mismatch" in failures
