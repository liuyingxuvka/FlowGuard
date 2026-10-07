from __future__ import annotations

import copy
import hashlib
import json
import threading
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from flowguard.behavior_surface_audit import (
    discover_implementation_behavior_surfaces,
    discover_implementation_surface_shard,
    merge_implementation_surface_shards,
    plan_implementation_surface_shards,
    validate_current_implementation_surface_discovery,
)
from flowguard.model_regressions import (
    ManifestAudit,
    MANIFEST_SCHEMA,
    ModelRegressionEntry,
    ModelRegressionEvidenceError,
    ModelRegressionManifest,
    audit_selected_reverse_surface_map_currentness,
    run_manifest_regressions,
    verify_selected_reverse_surface_map_currentness,
)
from flowguard import model_regressions as model_regressions_module
from flowguard.reverse_surface_map_identity import (
    CURRENT_SURFACE_DISCOVERY_PATH,
    IMPLEMENTATION_SURFACE_AUTHORING_SCHEMA,
    IMPLEMENTATION_SURFACE_MAP_PATH,
    IMPLEMENTATION_SURFACE_MAP_SCHEMA,
)


def _canonical_fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _seal_map(payload: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(payload)
    result.pop("authoring_fingerprint", None)
    result["authoring_fingerprint"] = _canonical_fingerprint(result)
    return result


def _write_current_snapshot_and_matching_map(
    root: Path,
    *,
    merged: bool = False,
    shard_max_rows: int = 5000,
    additional_source: bool = False,
) -> tuple[Path, str]:
    """Create a valid live D0 observation and a structurally valid map bound to it."""

    (root / "app.py").write_text(
        "def run(value: int) -> int:\n    return value + 1\n",
        encoding="utf-8",
    )
    if additional_source:
        (root / "extra.py").write_text(
            "def extra(value: int) -> int:\n    return value * 2\n",
            encoding="utf-8",
        )
    if merged:
        plan = plan_implementation_surface_shards(
            root,
            max_rows=shard_max_rows,
        )
        assert plan["status"] == "planned", plan.get("findings")
        shards = [
            discover_implementation_surface_shard(
                root,
                plan,
                str(shard["shard_id"]),
            )
            for shard in plan["shards"]
        ]
        discovery = merge_implementation_surface_shards(root, plan, shards)
    else:
        discovery = discover_implementation_behavior_surfaces(root)
    assert discovery["status"] == "passed", discovery.get("findings")
    assert discovery["surfaces"]
    discovery_fingerprint = str(discovery["discovery_fingerprint"])

    discovery_path = root / CURRENT_SURFACE_DISCOVERY_PATH
    discovery_path.parent.mkdir(parents=True, exist_ok=True)
    discovery_path.write_text(
        json.dumps(discovery, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mapped_surfaces: list[dict[str, object]] = []
    model_obligations: list[dict[str, object]] = []
    for observed_surface in discovery["surfaces"]:
        surface_id = str(observed_surface["surface_id"])
        obligation_id = f"obligation:{surface_id}"
        mapped_surfaces.append(
            {
                "surface_id": surface_id,
                "surface_kind": str(observed_surface["surface_kind"]),
                "surface_class": str(observed_surface["surface_class"]),
                "review_group_id": str(observed_surface["review_group_id"]),
                "review_granularity": str(
                    observed_surface["review_granularity"]
                ),
                "source_path": str(observed_surface["source_path"]),
                "disposition": "governed",
                "owner": "fixture-owner",
                "intent_id": f"intent:{surface_id}",
                "model_owner_id": "model:fixture-owner",
                "model_obligation_ids": [obligation_id],
                "test_refs": ["tests/test_current_discovery_admission.py"],
                "receipt_refs": ["receipts/fixture-owner.json"],
            }
        )
        model_obligations.append(
            {
                "obligation_id": obligation_id,
                "disposition": "governed",
                "surface_ids": [surface_id],
                "intent_id": f"intent:{surface_id}",
                "model_owner_id": "model:fixture-owner",
            }
        )
    map_payload = _seal_map(
        {
            "schema_version": IMPLEMENTATION_SURFACE_MAP_SCHEMA,
            "inventory_id": "fixture-current-discovery-admission",
            "project_boundary": "One temporary production source file.",
            "current_revision": "fixture-revision-d0",
            "discovery_fingerprint": discovery_fingerprint,
            "claim_boundary": "The fixture proves discovery admission only.",
            "authoring_schema": IMPLEMENTATION_SURFACE_AUTHORING_SCHEMA,
            "authoring_status": "authored_pending_audit",
            "semantic_authority": "explicit_target_owner",
            "no_fallback_policy": "unknown rows remain gaps",
            "surfaces": mapped_surfaces,
            "component_groups": [],
            "model_obligations": model_obligations,
            "terminal_receipt_refs": [],
        }
    )
    map_path = root / IMPLEMENTATION_SURFACE_MAP_PATH
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(
        json.dumps(map_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Prove the stored D0 is a usable source-current observation before either
    # drift scenario changes the fixture.
    assert validate_current_implementation_surface_discovery(root) == (
        discovery_fingerprint,
        len(discovery["surfaces"]),
    )
    return map_path, discovery_fingerprint


def _selected_map_owner(
    root: Path,
) -> tuple[ModelRegressionManifest, ModelRegressionEntry]:
    entry = ModelRegressionEntry.from_dict(
        {
            "model_id": "fixture-map-owner",
            "model_path": ".flowguard/models/owners/fixture-map-owner/model.py",
            "runner": [
                "{python}",
                ".flowguard/verification/owners/fixture-map-owner/run_checks.py",
            ],
            "tier": "full",
            "timeout_seconds": 5,
            "shard_safe": True,
            "mutation_policy": "none",
            "input_globs": [IMPLEMENTATION_SURFACE_MAP_PATH],
        }
    )
    manifest = ModelRegressionManifest(
        path=root / ".flowguard/models/regression-manifest.json",
        entries=(entry,),
        governed_input_globs=(),
        snapshot_only_input_globs=(),
        shared_input_groups=(),
    )
    return manifest, entry


def _assert_selected_map_owner_is_blocked(root: Path) -> None:
    manifest, entry = _selected_map_owner(root)
    errors = audit_selected_reverse_surface_map_currentness(
        root,
        manifest,
        (entry,),
    )
    assert len(errors) == 1
    assert errors[0].startswith(
        "implementation_surface_map: live discovery/map currentness failed "
        "before model-owner admission for fixture-map-owner"
    )


def _assert_stored_markers_remain_d0(
    root: Path,
    discovery_fingerprint: str,
) -> None:
    discovery = json.loads(
        (root / CURRENT_SURFACE_DISCOVERY_PATH).read_text(encoding="utf-8")
    )
    surface_map = json.loads(
        (root / IMPLEMENTATION_SURFACE_MAP_PATH).read_text(encoding="utf-8")
    )
    assert discovery["discovery_fingerprint"] == discovery_fingerprint
    assert surface_map["discovery_fingerprint"] == discovery_fingerprint


def test_selected_map_owner_blocks_when_an_existing_source_changes_after_d0(
    tmp_path: Path,
) -> None:
    map_path, d0 = _write_current_snapshot_and_matching_map(tmp_path)
    assert (
        json.loads(map_path.read_text(encoding="utf-8"))["discovery_fingerprint"]
        == d0
    )

    source_path = tmp_path / "app.py"
    source_path.write_text(
        source_path.read_text(encoding="utf-8") + "\n# changed after D0\n",
        encoding="utf-8",
    )
    live = discover_implementation_behavior_surfaces(tmp_path)

    _assert_stored_markers_remain_d0(tmp_path, d0)
    assert live["status"] == "passed", live.get("findings")
    assert live["discovery_fingerprint"] != d0
    _assert_selected_map_owner_is_blocked(tmp_path)


def test_selected_map_owner_blocks_when_a_new_source_is_added_after_d0(
    tmp_path: Path,
) -> None:
    _map_path, d0 = _write_current_snapshot_and_matching_map(tmp_path)
    (tmp_path / "new_entry.py").write_text(
        "def newly_added(value: int) -> int:\n    return value * 2\n",
        encoding="utf-8",
    )
    live = discover_implementation_behavior_surfaces(tmp_path)

    _assert_stored_markers_remain_d0(tmp_path, d0)
    assert live["status"] == "passed", live.get("findings")
    assert live["discovery_fingerprint"] != d0
    _assert_selected_map_owner_is_blocked(tmp_path)


def test_model_owner_start_rechecks_discovery_only_source_after_observation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _map_path, discovery_fingerprint = _write_current_snapshot_and_matching_map(
        tmp_path
    )
    manifest, entry = _selected_map_owner(tmp_path)
    model_path = tmp_path / entry.model_path
    runner_path = tmp_path / entry.runner[1]
    model_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("VALUE = 1\n", encoding="utf-8")
    runner_path.write_text("print('ok')\n", encoding="utf-8")
    entry = ModelRegressionEntry.from_dict(
        {
            "model_id": entry.model_id,
            "model_path": entry.model_path,
            "runner": list(entry.runner),
            "tier": "full",
            "timeout_seconds": 5,
            "shard_safe": True,
            "mutation_policy": "none",
            "input_globs": [
                entry.model_path,
                entry.runner[1],
                IMPLEMENTATION_SURFACE_MAP_PATH,
            ],
        }
    )
    manifest = ModelRegressionManifest(
        path=tmp_path / ".flowguard" / "models" / "regression-manifest.json",
        entries=(entry,),
        governed_input_globs=(),
        snapshot_only_input_globs=(),
        shared_input_groups=(),
    )
    manifest.path.parent.mkdir(parents=True, exist_ok=True)
    manifest.path.write_text(
        json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA,
                "governed_input_globs": [],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [],
                "models": [
                    {
                        "model_id": entry.model_id,
                        "model_path": entry.model_path,
                        "runner": list(entry.runner),
                        "tier": entry.tier,
                        "timeout_seconds": entry.timeout_seconds,
                        "shard_safe": entry.shard_safe,
                        "mutation_policy": entry.mutation_policy,
                        "input_globs": list(entry.input_globs),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        model_regressions_module,
        "audit_manifest",
        lambda _root, _manifest: ManifestAudit(
            True,
            (entry.model_id,),
            (entry.model_id,),
            (),
        ),
    )

    original_execute = model_regressions_module._execute_pending_models

    def drift_after_observation(*args, **kwargs):
        source_path = tmp_path / "app.py"
        source_path.write_text(
            source_path.read_text(encoding="utf-8") + "\n# drift after owner observation\n",
            encoding="utf-8",
        )
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(
        model_regressions_module,
        "_execute_pending_models",
        drift_after_observation,
    )
    run_entry = Mock(side_effect=AssertionError("owner runner must not start"))
    monkeypatch.setattr(model_regressions_module, "_run_entry", run_entry)

    with pytest.raises(
        ModelRegressionEvidenceError,
        match="immediately before owner start.*current source changed after discovery preview: app\\.py",
    ):
        run_manifest_regressions(
            tmp_path,
            tier="full",
            output_dir=tmp_path / "outputs" / "map-source-drift",
        )

    run_entry.assert_not_called()
    stored_discovery = json.loads(
        (tmp_path / CURRENT_SURFACE_DISCOVERY_PATH).read_text(encoding="utf-8")
    )
    assert stored_discovery["discovery_fingerprint"] == discovery_fingerprint


def test_current_merged_discovery_replays_with_its_frozen_row_bound(
    tmp_path: Path,
) -> None:
    _map_path, fingerprint = _write_current_snapshot_and_matching_map(
        tmp_path,
        merged=True,
        shard_max_rows=3,
        additional_source=True,
    )

    discovery = json.loads(
        (tmp_path / CURRENT_SURFACE_DISCOVERY_PATH).read_text(encoding="utf-8")
    )
    assert discovery["shard_id"] == "merged"
    assert discovery["shard_max_rows"] == 3
    assert len(discovery["shard_ids"]) == 2
    assert validate_current_implementation_surface_discovery(tmp_path) == (
        fingerprint,
        discovery["surface_count"],
    )


def test_resealed_incomplete_merged_denominator_is_rejected(
    tmp_path: Path,
) -> None:
    _write_current_snapshot_and_matching_map(
        tmp_path,
        merged=True,
        shard_max_rows=100,
    )
    discovery_path = tmp_path / CURRENT_SURFACE_DISCOVERY_PATH
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    assert len(discovery["surfaces"]) > 1
    discovery["surfaces"].pop()
    discovery["surface_count"] = len(discovery["surfaces"])
    call_graph = sorted(
        discovery["call_graph"],
        key=lambda row: (
            str(row.get("caller_surface_id", "")),
            str(row.get("callee_name", "")),
            str(row.get("resolution", "")),
        ),
    )
    discovery["discovery_fingerprint"] = _canonical_fingerprint(
        {
            "schema_version": discovery["schema_version"],
            "shard_id": discovery["shard_id"],
            "source_paths": discovery["source_paths"],
            "source_identities": discovery["source_identities"],
            "surfaces": sorted(
                discovery["surfaces"],
                key=lambda row: str(row.get("surface_id", "")),
            ),
            "call_graph": call_graph,
            "external_contracts": discovery["external_contracts"],
            "unbound_surface_ids": discovery["unbound_surface_ids"],
            "shard_max_rows": discovery["shard_max_rows"],
            "shard_plan_fingerprint": discovery["shard_plan_fingerprint"],
            "shard_ids": discovery["shard_ids"],
        }
    )
    discovery_path.write_text(
        json.dumps(discovery, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="differs from the complete live source observation"):
        validate_current_implementation_surface_discovery(tmp_path)


def test_reused_admission_proof_blocks_source_drift_before_owner_execution(
    tmp_path: Path,
) -> None:
    _write_current_snapshot_and_matching_map(tmp_path)
    manifest, entry = _selected_map_owner(tmp_path)
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path,
        manifest,
        (entry,),
    )
    assert errors == ()
    assert admission is not None
    assert audit_selected_reverse_surface_map_currentness(
        tmp_path,
        manifest,
        (entry,),
        admission=admission,
    ) == ()

    source_path = tmp_path / "app.py"
    source_path.write_text(
        source_path.read_text(encoding="utf-8") + "\n# changed after preview\n",
        encoding="utf-8",
    )
    errors = audit_selected_reverse_surface_map_currentness(
        tmp_path,
        manifest,
        (entry,),
        admission=admission,
    )
    assert len(errors) == 1
    assert "changed after discovery preview" in errors[0]


def test_no_selected_exact_map_consumer_needs_no_discovery_or_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace
    from flowguard import behavior_surface_audit as surface_audit

    manifest, selected = _selected_map_owner(tmp_path)
    selected = replace(selected, input_globs=(".flowguard/**/*",))
    manifest = replace(manifest, entries=(selected,))
    discovery = Mock(side_effect=AssertionError("non-consumer started discovery"))
    map_loader = Mock(side_effect=AssertionError("non-consumer read a map"))
    monkeypatch.setattr(
        surface_audit, "capture_current_implementation_surface_discovery", discovery,
    )
    monkeypatch.setattr(
        model_regressions_module,
        "load_current_reverse_surface_map_with_semantic_fingerprint", map_loader,
    )
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (selected,),
    )
    assert errors == ()
    assert admission is None
    assert audit_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (selected,),
    ) == ()
    discovery.assert_not_called()
    map_loader.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_explicit_exact_map_consumer_still_blocks_when_no_map_is_authored(
    tmp_path: Path,
) -> None:
    manifest, selected = _selected_map_owner(tmp_path)
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (selected,),
    )
    assert len(errors) == 1
    assert "before model-owner admission for fixture-map-owner" in errors[0]
    assert admission is None
    assert not (tmp_path / IMPLEMENTATION_SURFACE_MAP_PATH).exists()


def _mock_pending_map_owners(root, monkeypatch, *, owner_count=2, on_publish=None):
    """Exercise admission boundaries without launching or publishing an owner."""

    manifest, entry = _selected_map_owner(root)
    pending = tuple(
        replace(entry, model_id=f"fixture-map-owner-{index}")
        for index in range(owner_count)
    )
    contracts = tuple(
        SimpleNamespace(owner_id=f"model:{row.model_id}") for row in pending
    )
    currents = {
        contract.owner_id: SimpleNamespace(owner_identity="sha256:" + "a" * 64)
        for contract in contracts
    }
    freshness = SimpleNamespace(current_by_owner=currents)
    monkeypatch.setattr(
        model_regressions_module, "evidence_execution_lease",
        lambda *args, **kwargs: nullcontext({}),
    )
    monkeypatch.setattr(
        model_regressions_module, "_assert_validation_owner_current_fresh",
        lambda *args, **kwargs: freshness,
    )
    result = SimpleNamespace(
        status="pass", finding_codes=(),
        supervision=SimpleNamespace(cleanup_confirmed=True),
    )
    runner = Mock(return_value=result)
    monkeypatch.setattr(model_regressions_module, "_run_entry", runner)

    def publish(*args, **kwargs):
        if on_publish is not None:
            on_publish()
        return result

    monkeypatch.setattr(model_regressions_module, "_persist_model_owner_result", publish)
    final_source_check = Mock(return_value=freshness)
    monkeypatch.setattr(
        model_regressions_module, "assert_validation_owner_observation_fresh",
        final_source_check,
    )
    return {
        "root_path": root.resolve(),
        "pending": pending,
        "jobs": 1,
        "timeout": None,
        "output_path": root / "outputs",
        "receipt_root": root / "receipts",
        "currents": currents,
        "contracts": contracts,
        "planning_observation": SimpleNamespace(),
        "cancel": threading.Event(),
        "progress": None,
    }, runner, final_source_check, manifest, entry


def test_serial_second_owner_blocks_new_discovery_source_between_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_current_snapshot_and_matching_map(tmp_path)

    def add_unselected_production_source():
        (tmp_path / "new_entry.py").write_text(
            "def added_after_first_owner():\n    return 1\n", encoding="utf-8",
        )

    arguments, runner, final_source_check, manifest, entry = _mock_pending_map_owners(
        tmp_path, monkeypatch, on_publish=add_unselected_production_source,
    )
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (entry,),
    )
    assert errors == () and admission is not None
    arguments["reverse_surface_admission"] = admission
    with pytest.raises(
        ModelRegressionEvidenceError,
        match="immediately before owner start.*source path set changed",
    ):
        model_regressions_module._execute_pending_models(**arguments)
    assert runner.call_count == 1
    assert runner.call_args.args[1].model_id == "fixture-map-owner-0"
    final_source_check.assert_not_called()


@pytest.mark.parametrize("jobs", [1, 2])
def test_final_map_source_boundary_blocks_drift_after_last_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jobs: int,
) -> None:
    _write_current_snapshot_and_matching_map(tmp_path)
    arguments, runner, final_source_check, manifest, entry = _mock_pending_map_owners(
        tmp_path, monkeypatch, owner_count=1,
    )
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (entry,),
    )
    assert errors == () and admission is not None
    arguments.update(jobs=jobs, reverse_surface_admission=admission)
    returned_result = runner.return_value

    def add_source_after_owner(*args, **kwargs):
        (tmp_path / "new_entry.py").write_text(
            "def added_after_last_owner():\n    return 1\n", encoding="utf-8",
        )
        return returned_result

    runner.side_effect = add_source_after_owner
    with pytest.raises(
        ModelRegressionEvidenceError,
        match="at final source boundary.*source path set changed",
    ):
        model_regressions_module._execute_pending_models(**arguments)
    assert runner.call_count == 1
    final_source_check.assert_not_called()


def test_serial_map_consumers_revalidate_each_owner_and_final_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_current_snapshot_and_matching_map(tmp_path)
    arguments, runner, final_source_check, manifest, entry = _mock_pending_map_owners(
        tmp_path, monkeypatch,
    )
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (entry,),
    )
    assert errors == () and admission is not None
    arguments["reverse_surface_admission"] = admission
    revalidate = Mock(wraps=model_regressions_module._revalidate_current_reverse_surface_admission)
    monkeypatch.setattr(
        model_regressions_module, "_revalidate_current_reverse_surface_admission", revalidate,
    )
    results, _freshness = model_regressions_module._execute_pending_models(**arguments)
    assert len(results) == runner.call_count == 2
    assert revalidate.call_count == 3
    final_source_check.assert_called_once()


def test_serial_no_map_consumer_never_revalidates_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments, runner, final_source_check, _manifest, _entry = _mock_pending_map_owners(
        tmp_path, monkeypatch,
    )
    revalidate = Mock(side_effect=AssertionError("non-consumer revalidated discovery"))
    monkeypatch.setattr(
        model_regressions_module, "_revalidate_current_reverse_surface_admission", revalidate,
    )
    results, _freshness = model_regressions_module._execute_pending_models(**arguments)
    assert len(results) == runner.call_count == 2
    revalidate.assert_not_called()
    final_source_check.assert_called_once()


def test_final_map_source_boundary_checks_all_reused_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_current_snapshot_and_matching_map(tmp_path)
    arguments, runner, final_source_check, manifest, entry = _mock_pending_map_owners(
        tmp_path, monkeypatch, owner_count=0,
    )
    errors, admission = verify_selected_reverse_surface_map_currentness(
        tmp_path, manifest, (entry,),
    )
    assert errors == () and admission is not None
    arguments["reverse_surface_admission"] = admission
    (tmp_path / "new_entry.py").write_text(
        "def added_after_reuse_observation():\n    return 1\n", encoding="utf-8",
    )
    with pytest.raises(
        ModelRegressionEvidenceError,
        match="at final source boundary.*source path set changed",
    ):
        model_regressions_module._execute_pending_models(**arguments)
    runner.assert_not_called()
    final_source_check.assert_not_called()
