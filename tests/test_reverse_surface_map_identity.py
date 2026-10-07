from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import flowguard.validation_ownership as ownership
import flowguard.reverse_surface_owner_authority as reverse_owner_authority
import flowguard.reverse_surface_map_identity as reverse_surface_map_identity
import flowguard.behavior_surface_audit as behavior_surface_audit
from flowguard.affected_blueprint_reader import AffectedImpactPlan
from flowguard.evidence_receipts import _receipt_filename, fingerprint_value
from flowguard.model_regressions import (
    ModelRegressionEntry,
    ModelRegressionManifest,
    ModelRegressionManifestError,
    audit_selected_reverse_surface_map_currentness,
    compile_model_impact_map,
    resolve_entry_input_inventory,
)
from flowguard.reverse_surface_map_identity import (
    IMPLEMENTATION_SURFACE_MAP_PATH,
    ReverseSurfaceMapIdentityError,
    model_input_projection,
    reverse_owner_semantic_map_fingerprint,
)
from flowguard.source_identity import (
    functional_source_fingerprint,
    model_input_fingerprint,
    source_file_fingerprint,
)
from flowguard.validation_ownership import (
    ValidationOwnerContract,
    build_affected_impact_plan,
    resolve_input_manifest,
)


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _seal(payload: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(payload)
    result.pop("authoring_fingerprint", None)
    result["authoring_fingerprint"] = _canonical_hash(result)
    return result


def _canonical_owner_reference(directory: str, digest: str) -> str:
    receipt_id = "receipt:validation-owner:behavior_commitment_ledger:" + digest * 32
    return directory + "/" + _receipt_filename(receipt_id) + "#" + receipt_id


_OWNER_RECEIPT_OLD_REF = _canonical_owner_reference(
    ".flowguard/evidence/model-owner-receipts", "a",
)
_OWNER_RECEIPT_NEW_REF = _canonical_owner_reference(
    "work/verification/current-owner", "b",
)


def _map_payload() -> dict[str, object]:
    return _seal(
        {
            "schema_version": "flowguard.implementation_surface_map.v1",
            "inventory_id": "flowguard",
            "project_boundary": "FlowGuard public source",
            "current_revision": "rev-current-a",
            "discovery_fingerprint": "sha256:" + "a" * 64,
            "claim_boundary": "Explicit semantic bindings only.",
            "authoring_schema": "flowguard.implementation_surface_semantic_authoring.v1",
            "authoring_status": "authored_pending_audit",
            "semantic_authority": "explicit_target_owner",
            "no_fallback_policy": "unknown rows remain gaps",
            "extensions": {
                "authoring_fingerprint": "authored extension value",
                "receipt_refs": ["proof:extension"],
            },
            "surfaces": [
                {
                    "surface_id": "surface:flowguard.api.read",
                    "surface_kind": "function",
                    "surface_class": "public_api",
                    "review_group_id": "group:api",
                    "review_granularity": "surface",
                    "source_path": "flowguard/api.py",
                    "source_ref": "flowguard/api.py::read",
                    "source_fingerprint": "sha256:" + "9" * 64,
                    "disposition": "governed",
                    "owner": "behavior_commitment_ledger",
                    "intent_id": "intent:read-contract",
                    "model_owner_id": "behavior_commitment_ledger",
                    "model_obligation_ids": ["obligation:read"],
                    "test_refs": ["tests/test_api.py"],
                    "test_owner_ids": ["test:read"],
                    "receipt_refs": [_OWNER_RECEIPT_OLD_REF, "test-receipt:read"],
                    "proof_ref": "proof:read",
                    "reason": "internal boundary proof",
                    "proof_refs": ["proof:read"],
                    "owner_receipt_id": "validation-owner:old",
                    "owner_receipt_fingerprint": "sha256:" + "b" * 64,
                }
            ],
            "component_groups": [
                {
                    "review_group_id": "group:api",
                    "review_granularity": "component",
                    "surface_ids": ["surface:flowguard.api.write"],
                    "disposition": "governed",
                    "owner": "behavior_commitment_ledger",
                    "intent_id": "intent:write-contract",
                    "model_owner_id": "behavior_commitment_ledger",
                    "model_obligation_ids": ["obligation:write"],
                    "test_refs": ["tests/test_api.py::test_write"],
                    "test_owner_ids": ["test:write"],
                    "receipt_refs": [_OWNER_RECEIPT_OLD_REF, "test-receipt:write"],
                }
            ],
            "model_obligations": [
                {
                    "obligation_id": "obligation:read",
                    "disposition": "governed",
                    "surface_ids": ["surface:flowguard.api.read"],
                    "intent_id": "intent:read-contract",
                    "model_owner_id": "behavior_commitment_ledger",
                },
                {
                    "obligation_id": "obligation:write",
                    "disposition": "governed",
                    "surface_ids": ["surface:flowguard.api.write"],
                    "intent_id": "intent:write-contract",
                    "model_owner_id": "behavior_commitment_ledger",
                }
            ],
            "owner_receipt_identities": [
                {
                    "owner_id": "behavior_commitment_ledger",
                    "model_ids": ["behavior_commitment_ledger"],
                    "receipt_id": "validation-owner:old",
                    "receipt_fingerprint": "sha256:" + "c" * 64,
                }
            ],
            "current_authority_join": {
                "join_fingerprint": "sha256:" + "d" * 64,
                "authority_head": "sha256:" + "e" * 64,
                "rows": [{"owner_receipt_id": "validation-owner:old"}],
            },
            "current_behavior_ledger_join": {
                "join_fingerprint": "sha256:" + "f" * 64,
                "ledger_fingerprint": "sha256:" + "1" * 64,
            },
            "terminal_receipt_refs": [_OWNER_RECEIPT_OLD_REF, "proof:terminal"],
        }
    )


def _write_map(root: Path, payload: dict[str, object] | None = None) -> Path:
    value = payload or _map_payload()
    path = root / IMPLEMENTATION_SURFACE_MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    discovery_path = root / ".flowguard/structure/reverse-surfaces/current-discovery.json"
    discovery_path.write_text(
        json.dumps(
            {
                "schema_version": "flowguard.implementation_surface_audit.v1",
                "status": "passed",
                "discovery_fingerprint": value["discovery_fingerprint"],
                "source_paths": ["flowguard/api.py"],
                "surface_count": 1,
                "surfaces": [{"surface_id": "surface:test"}],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _entry(patterns: tuple[str, ...]) -> ModelRegressionEntry:
    return ModelRegressionEntry.from_dict(
        {
            "model_id": "map-owner",
            "model_path": ".flowguard/models/owners/map-owner/model.py",
            "runner": ["{python}", "runner.py"],
            "tier": "full",
            "timeout_seconds": 5,
            "shard_safe": True,
            "mutation_policy": "none",
            "input_globs": list(patterns),
        }
    )


def _route_model_audit_fixture(root: Path):
    (root / "app.py").write_text("def run(value):\n    return value\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text(
        "def test_run():\n    assert 1 == 1\n", encoding="utf-8"
    )
    (root / "receipt.txt").write_text("surface-pass\n", encoding="utf-8")
    binding_path = root / ".flowguard/structure/owner-bindings.json"
    binding_path.parent.mkdir(parents=True)
    binding_path.write_text(
        json.dumps({
            "schema": "flowguard.native_owner_model_bindings.v1",
            "bindings": [{"owner_route": "supervisor", "model_ids": ["model-a", "model-b"]}],
        }), encoding="utf-8",
    )
    receipt = {
        "owner_route": "supervisor",
        "receipt_id": "receipt:validation-owner:supervisor:" + "a" * 32,
        "receipt_fingerprint": "sha256:" + "b" * 64,
        "subject_fingerprint": "sha256:" + "c" * 64,
        "candidate_snapshot_fingerprint": "sha256:" + "c" * 64,
    }
    join = {
        "schema_version": behavior_surface_audit.IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA,
        "head_fingerprint": "sha256:" + "d" * 64,
        "snapshot_fingerprint": "sha256:" + "c" * 64,
        "revision_set_fingerprint": "sha256:" + "e" * 64,
        "activation_receipt_fingerprint": "sha256:" + "f" * 64,
        "model_owner_ids": ["model-a", "model-b", "real-foreign-model"],
        "owner_receipt_identities": [receipt],
    }
    join["join_fingerprint"] = _canonical_hash(join)
    assert behavior_surface_audit._validate_current_authority_join_projection(join) == []
    discovery = behavior_surface_audit.discover_implementation_behavior_surfaces(root)
    rows = [{
        "surface_id": observed["surface_id"],
        "owner": "supervisor",
        "model_owner_id": "model-a",
        "intent_id": "intent:" + observed["surface_id"],
        "model_obligation_ids": ["obligation:" + observed["surface_id"]],
        "disposition": "governed",
        "test_refs": ["tests/test_app.py#test_run"],
        "receipt_refs": ["receipt.txt#surface-pass"],
        "owner_receipt_id": receipt["receipt_id"],
        "owner_receipt_fingerprint": receipt["receipt_fingerprint"],
    } for observed in discovery["surfaces"]]
    mapping = {
        "schema_version": "flowguard.implementation_surface_map.v1",
        "inventory_id": "route-model-test",
        "project_boundary": "fixture source",
        "current_revision": "fixture-current",
        "claim_boundary": "fixture reverse closure",
        "discovery_fingerprint": discovery["discovery_fingerprint"],
        "surfaces": rows,
        "model_obligations": [{
            "obligation_id": row["model_obligation_ids"][0],
            "disposition": "governed",
            "surface_ids": [row["surface_id"]],
        } for row in rows],
        "current_authority_join": join,
    }
    return discovery, mapping, join


@pytest.mark.parametrize("disposition", ["governed", "internal_proven"])
def test_reverse_audit_rejects_foreign_route_with_current_model_and_receipt(tmp_path, disposition):
    discovery, mapping, join = _route_model_audit_fixture(tmp_path)
    row = mapping["surfaces"][0]
    row.update(disposition=disposition, model_owner_id="real-foreign-model")
    # Neither global current-model admission nor the exact current route receipt
    # establishes that supervisor owns this otherwise real model.
    assert row["model_owner_id"] in join["model_owner_ids"]
    assert row["owner_receipt_id"] == join["owner_receipt_identities"][0]["receipt_id"]
    with patch.object(behavior_surface_audit, "_load_current_authority_join", return_value=join):
        blocked = behavior_surface_audit.audit_implementation_behavior_surface(
            tmp_path, mapping, discovery=discovery,
        )
    assert blocked["status"] == "blocked"
    assert blocked["current_authority_join"]["status"] == "current"
    codes = {finding["code"] for finding in blocked["findings"]}
    assert "implementation_surface_owner_route_model_mismatch" in codes
    assert "implementation_surface_current_model_owner_unknown" not in codes
    assert "implementation_surface_current_owner_receipt_mismatch" not in codes


def test_reverse_audit_accepts_declared_multi_model_supervisor(tmp_path):
    discovery, mapping, join = _route_model_audit_fixture(tmp_path)
    for index, row in enumerate(mapping["surfaces"]):
        row["model_owner_id"] = ("model-a", "model-b")[index % 2]
    with patch.object(behavior_surface_audit, "_load_current_authority_join", return_value=join):
        accepted = behavior_surface_audit.audit_implementation_behavior_surface(
            tmp_path, mapping, discovery=discovery,
        )
    assert accepted["status"] == "passed", accepted["findings"]
    assert accepted["reverse_closure_complete"] is True


@pytest.mark.parametrize("collection", ["surfaces", "component_groups"])
@pytest.mark.parametrize("disposition", ["governed", "internal_proven"])
def test_reverse_owner_builder_rejects_foreign_route_before_evidence_writes(tmp_path, collection, disposition):
    mapping = _map_payload()
    mapping[collection][0].update(
        owner="supervisor", model_owner_id="authoritative_model_system", disposition=disposition,
    )
    with (
        patch.object(reverse_owner_authority, "load_current_model_authority_state", return_value=object()),
        patch.object(reverse_owner_authority, "_authority_identity", return_value={}),
        patch.object(reverse_owner_authority, "_load_current_discovery", return_value=("sha256:" + "a" * 64, 2)),
        patch.object(reverse_owner_authority, "_load_owner_bindings", return_value=({
            "supervisor": ("behavior_commitment_ledger", "other-real-model"),
            "behavior_commitment_ledger": ("behavior_commitment_ledger",),
        }, "sha256:" + "b" * 64)),
        patch.object(reverse_owner_authority, "load_current_reverse_surface_map_with_semantic_fingerprint", return_value=(mapping, "sha256:" + "c" * 64)),
        patch.object(reverse_owner_authority, "_parent_for_current") as parent,
        patch.object(reverse_owner_authority, "save_child_bound_owner_receipt") as save_receipt,
        patch.object(reverse_owner_authority, "_write_json") as publish,
    ):
        with pytest.raises(reverse_owner_authority.ReverseSurfaceOwnerAuthorityError, match="does not own model_owner_id"):
            reverse_owner_authority.build_current_reverse_surface_owner_authority(
                tmp_path, model_parent_receipt=tmp_path / "parent.json",
            )
    parent.assert_not_called()
    save_receipt.assert_not_called()
    publish.assert_not_called()
    assert not (tmp_path / ".flowguard/evidence").exists()


def test_reverse_route_model_guard_accepts_multi_model_groups_and_surfaces():
    mapping = _map_payload()
    mapping["surfaces"][0].update(owner="supervisor", model_owner_id="model-a")
    mapping["component_groups"][0].update(owner="supervisor", model_owner_id="model-b", disposition="internal_proven")
    reverse_owner_authority.validate_reverse_surface_route_model_membership(
        mapping, {"supervisor": ("model-a", "model-b")},
    )


def test_semantic_projection_changes_for_authored_bindings():
    base = _map_payload()
    base_fingerprint = _canonical_hash(model_input_projection(base))
    mutations = {
        "surface owner": lambda value: value["surfaces"][0].update(
            owner="authoritative_model_system"
        ),
        "intent": lambda value: value["surfaces"][0].update(
            intent_id="intent:changed"
        ),
        "disposition": lambda value: value["surfaces"][0].update(
            disposition="internal_proven"
        ),
        "model obligation": lambda value: value["surfaces"][0].update(
            model_obligation_ids=["obligation:changed"]
        ),
        "test reference": lambda value: value["surfaces"][0].update(
            test_refs=["tests/test_api.py::test_changed"]
        ),
        "proof reference": lambda value: value["surfaces"][0].update(
            proof_ref="proof:changed"
        ),
        "component membership": lambda value: value["component_groups"][0].update(
            surface_ids=[
                "surface:flowguard.api.write",
                "surface:flowguard.api.other",
            ]
        ),
        "reserved-looking extension fields": lambda value: value["extensions"].update(
            authoring_fingerprint="different authored extension",
            receipt_refs=["proof:changed-extension"],
        ),
    }
    for label, mutate in mutations.items():
        changed = copy.deepcopy(base)
        mutate(changed)
        changed = _seal(changed)
        assert _canonical_hash(model_input_projection(changed)) != base_fingerprint, label


def test_generated_currentness_and_owner_receipts_do_not_change_model_identity():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        original_path = _write_map(root)
        original_model_identity = functional_source_fingerprint(
            root, IMPLEMENTATION_SURFACE_MAP_PATH
        )
        original_raw_identity = source_file_fingerprint(original_path)

        changed = _map_payload()
        changed.update(
            {
                "authoring_status": "current",
                "current_revision": "rev-current-b",
                "discovery_fingerprint": "sha256:" + "2" * 64,
                "current_authority_join": {
                    "join_fingerprint": "sha256:" + "3" * 64,
                    "authority_head": "sha256:" + "4" * 64,
                    "rows": [{"owner_receipt_id": "validation-owner:new"}],
                },
                "current_behavior_ledger_join": {
                    "join_fingerprint": "sha256:" + "5" * 64,
                    "ledger_fingerprint": "sha256:" + "6" * 64,
                },
                "owner_receipt_identities": [
                    {
                        "owner_id": "behavior_commitment_ledger",
                        "model_ids": ["behavior_commitment_ledger"],
                        "receipt_id": "validation-owner:new",
                        "receipt_fingerprint": "sha256:" + "7" * 64,
                    }
                ],
            }
        )
        changed["surfaces"][0].update(
            {
                "owner_receipt_id": "validation-owner:new",
                "owner_receipt_fingerprint": "sha256:" + "8" * 64,
                "receipt_refs": [_OWNER_RECEIPT_NEW_REF, "test-receipt:read"],
            }
        )
        changed["terminal_receipt_refs"] = [
            _OWNER_RECEIPT_NEW_REF,
            "proof:terminal",
        ]
        changed_path = _write_map(root, _seal(changed))

        assert functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH) == original_model_identity
        assert source_file_fingerprint(changed_path) != original_raw_identity


def test_map_discovery_fingerprint_must_match_current_discovery_before_input_admission():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = _write_map(root)
        stale = _map_payload()
        stale["discovery_fingerprint"] = "sha256:" + "b" * 64
        path.write_text(
            json.dumps(_seal(stale), ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        with pytest.raises(ReverseSurfaceMapIdentityError, match="discovery fingerprint is stale"):
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)
        with pytest.raises(ModelRegressionManifestError, match="discovery fingerprint is stale"):
            resolve_entry_input_inventory(
                root,
                _entry((IMPLEMENTATION_SURFACE_MAP_PATH,)),
            )


def test_matching_declared_discovery_marker_does_not_prove_live_source_currentness():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write_map(root)
        # The lightweight identity layer can prove the map and discovery
        # declare the same marker, but only the full source validator can
        # prove that the stored observation still matches live source files.
        reverse_surface_map_identity.load_current_reverse_surface_map_model_input_projection(
            root
        )
        with pytest.raises(
            behavior_surface_audit.PublicBehaviorSurfaceAuditError,
            match="is stale or blocked",
        ):
            behavior_surface_audit.validate_current_implementation_surface_discovery(
                root
            )

        manifest = SimpleNamespace(owner_patterns_for=lambda _model_id: ())
        errors = audit_selected_reverse_surface_map_currentness(
            root,
            manifest,
            (_entry((IMPLEMENTATION_SURFACE_MAP_PATH,)),),
        )
        assert len(errors) == 1
        assert "live discovery/map currentness failed" in errors[0]


def test_file_projection_validates_large_map_once_per_identity_request():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write_map(root)
        validator = reverse_surface_map_identity.validate_reverse_surface_map_payload
        with patch.object(
            reverse_surface_map_identity,
            "validate_reverse_surface_map_payload",
            wraps=validator,
        ) as validate:
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)
            assert validate.call_count == 1
        with patch.object(
            reverse_surface_map_identity,
            "validate_reverse_surface_map_payload",
            wraps=validator,
        ) as validate:
            reverse_owner_authority._semantic_map_binding_fingerprint(root)
            assert validate.call_count == 1


def test_reverse_owner_semantic_identity_excludes_joins_but_contract_binds_authority():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        base = _map_payload()
        _write_map(root, base)
        base_fingerprint = reverse_owner_authority._semantic_map_binding_fingerprint(root)
        assert base_fingerprint == reverse_owner_semantic_map_fingerprint(base)

        authority_join_changed = copy.deepcopy(base)
        authority_join_changed["current_authority_join"]["authority_head"] = (
            "sha256:" + "a" * 64
        )
        authority_join_changed = _seal(authority_join_changed)
        _write_map(root, authority_join_changed)
        assert reverse_owner_authority._semantic_map_binding_fingerprint(root) == base_fingerprint

        behavior_join_changed = copy.deepcopy(base)
        behavior_join_changed["current_behavior_ledger_join"]["ledger_fingerprint"] = (
            "sha256:" + "b" * 64
        )
        behavior_join_changed = _seal(behavior_join_changed)
        _write_map(root, behavior_join_changed)
        assert reverse_owner_authority._semantic_map_binding_fingerprint(root) == base_fingerprint

        markers_changed = copy.deepcopy(base)
        markers_changed.update(
            {
                "authoring_status": "current",
                "current_revision": "rev-current-b",
                "discovery_fingerprint": "sha256:" + "c" * 64,
            }
        )
        markers_changed = _seal(markers_changed)
        _write_map(root, markers_changed)
        assert reverse_owner_authority._semantic_map_binding_fingerprint(root) == base_fingerprint

        authored_change = copy.deepcopy(base)
        authored_change["surfaces"][0]["intent_id"] = "intent:changed"
        authored_change = _seal(authored_change)
        _write_map(root, authored_change)
        authored_fingerprint = reverse_owner_authority._semantic_map_binding_fingerprint(root)
        assert authored_fingerprint != base_fingerprint

        def contract_inputs(*, head: str = "1", parent: str = "8") -> dict[str, str]:
            contract = reverse_owner_authority.build_reverse_owner_contract(
                route="behavior_commitment_ledger",
                model_ids=("behavior_commitment_ledger",),
                authority_identity={
                    "head_fingerprint": "sha256:" + head * 64,
                    "snapshot_fingerprint": "sha256:" + "2" * 64,
                    "revision_set_fingerprint": "sha256:" + "3" * 64,
                    "activation_receipt_fingerprint": "sha256:" + "4" * 64,
                },
                discovery_fingerprint=base["discovery_fingerprint"],
                owner_bindings_fingerprint="sha256:" + "5" * 64,
                route_set_fingerprint="sha256:" + "6" * 64,
                model_parent_fingerprint="sha256:" + parent * 64,
                semantic_map_fingerprint=base_fingerprint,
                child_receipts={
                    "behavior_commitment_ledger": SimpleNamespace(
                        fingerprint="sha256:" + "7" * 64
                    )
                },
            )
            return dict(contract.projected_inputs)

        original_contract = contract_inputs()
        changed_head_contract = contract_inputs(head="9")
        changed_parent_contract = contract_inputs(parent="a")
        semantic_map_key = "reverse-surface:semantic-map"
        assert original_contract[semantic_map_key] == changed_head_contract[semantic_map_key]
        assert original_contract[semantic_map_key] == changed_parent_contract[semantic_map_key]
        assert (
            original_contract["reverse-surface:authority-head"]
            != changed_head_contract["reverse-surface:authority-head"]
        )
        assert (
            original_contract["reverse-surface:model-parent"]
            != changed_parent_contract["reverse-surface:model-parent"]
        )


def test_bad_schema_or_authoring_fingerprint_fails_closed():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = _write_map(root)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["authoring_fingerprint"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="authoring fingerprint is stale"):
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)

        payload = _seal({**_map_payload(), "schema_version": "old.schema"})
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="schema is not current"):
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)

        path.write_text(
            '{"schema_version":"flowguard.implementation_surface_map.v1",'
            '"schema_version":"flowguard.implementation_surface_map.v1"}',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="duplicates JSON field"):
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("model_obligations", None, "model_obligations must be an array"),
        ("surfaces", [{"surface_id": "surface:broken"}], "surface_kind"),
    ),
)
def test_current_schema_rejects_malformed_rows_after_a_valid_checksum(
    field: str, replacement: object, message: str
):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        malformed = _map_payload()
        if replacement is None:
            malformed.pop(field)
        else:
            malformed[field] = replacement
        path = _write_map(root, _seal(malformed))
        with pytest.raises(ReverseSurfaceMapIdentityError, match=message):
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)


def test_exact_map_rejects_a_symlinked_parent_component():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        target_dir = root / ".flowguard" / "alternate-reverse-surfaces"
        target_dir.mkdir(parents=True)
        target = target_dir / "implementation-surface-map.json"
        target.write_text(
            json.dumps(_map_payload(), ensure_ascii=False), encoding="utf-8"
        )
        link = root / ".flowguard" / "structure" / "reverse-surfaces"
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(target_dir, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"directory symlink creation is unavailable: {exc}")

        with pytest.raises(ReverseSurfaceMapIdentityError, match="symlink or reparse point"):
            model_input_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)
        with pytest.raises(ReverseSurfaceMapIdentityError, match="symlink or reparse point"):
            functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH)
        with patch.object(ownership, "_git_candidate_paths", return_value=None):
            with pytest.raises(ReverseSurfaceMapIdentityError, match="symlink or reparse point"):
                resolve_input_manifest(root, (IMPLEMENTATION_SURFACE_MAP_PATH,))
            with pytest.raises(ReverseSurfaceMapIdentityError, match="symlink or reparse point"):
                ownership._fingerprint_manifest_paths(
                    root,
                    (IMPLEMENTATION_SURFACE_MAP_PATH,),
                    explicitly_admitted_paths=(IMPLEMENTATION_SURFACE_MAP_PATH,),
                )
        with pytest.raises(
            ModelRegressionManifestError,
            match="map-owner: input selection is invalid: repository evidence path crosses a symlink or reparse point:",
        ):
            resolve_entry_input_inventory(
                root,
                _entry((IMPLEMENTATION_SURFACE_MAP_PATH,)),
            )


def test_exact_map_literal_is_admitted_but_broad_globs_stay_excluded():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = _write_map(root)
        expected = ({
            "path": IMPLEMENTATION_SURFACE_MAP_PATH,
            "sha256": functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH),
        },)

        with patch.object(ownership, "_git_candidate_paths", return_value=None):
            exact = resolve_input_manifest(root, (IMPLEMENTATION_SURFACE_MAP_PATH,))
            broad = resolve_input_manifest(root, (".flowguard/**/*",))
            reverse_tree = resolve_input_manifest(
                root, (".flowguard/structure/reverse-surfaces/**/*",)
            )
            mixed = resolve_input_manifest(
                root,
                (".flowguard/**/*", IMPLEMENTATION_SURFACE_MAP_PATH),
            )

        assert exact == expected
        assert broad == ()
        assert reverse_tree == ()
        assert mixed == expected
        assert ownership._fingerprint_manifest_paths(
            root, (IMPLEMENTATION_SURFACE_MAP_PATH,)
        ) == ()
        assert ownership.filter_resolved_input_manifest(
            expected, (".flowguard/**/*",)
        ) == ()
        assert ownership.filter_resolved_input_manifest(
            expected, (IMPLEMENTATION_SURFACE_MAP_PATH,)
        ) == expected
        assert ownership.filter_resolved_input_manifest(
            expected, (".flowguard/**/*", IMPLEMENTATION_SURFACE_MAP_PATH)
        ) == expected
        assert model_input_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH) == expected[0]["sha256"]


def test_exact_map_admission_survives_git_ignore_without_relaxing_broad_filter():
    if not shutil.which("git"):
        pytest.skip("git is required for ignored-path admission coverage")
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = _write_map(root)
        (root / ".gitignore").write_text(
            ".flowguard/structure/reverse-surfaces/\n", encoding="utf-8"
        )
        subprocess.run(("git", "init", "-q"), cwd=root, check=True)
        exact = resolve_input_manifest(root, (IMPLEMENTATION_SURFACE_MAP_PATH,))
        broad = resolve_input_manifest(root, (".flowguard/**/*",))
        mixed = resolve_input_manifest(
            root, (".flowguard/**/*", IMPLEMENTATION_SURFACE_MAP_PATH)
        )
        expected = ({
            "path": IMPLEMENTATION_SURFACE_MAP_PATH,
            "sha256": functional_source_fingerprint(root, IMPLEMENTATION_SURFACE_MAP_PATH),
        },)
        assert exact == expected
        assert broad == ()
        assert mixed == expected


def test_model_snapshot_owner_observation_and_impact_use_same_map_identity():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write_map(root)
        entry = _entry((IMPLEMENTATION_SURFACE_MAP_PATH,))
        inventory = resolve_entry_input_inventory(root, entry)
        with patch.object(ownership, "_git_candidate_paths", return_value=None):
            observation = resolve_input_manifest(root, (IMPLEMENTATION_SURFACE_MAP_PATH,))
        assert inventory == observation
        assert inventory[0]["sha256"] == model_input_fingerprint(
            root, IMPLEMENTATION_SURFACE_MAP_PATH
        )

        contract = ValidationOwnerContract(
            owner_id="map-owner",
            command=(sys.executable, "-c", "pass"),
            input_patterns=(IMPLEMENTATION_SURFACE_MAP_PATH,),
            obligation_ids=("obligation:map-owner",),
        )
        plan = build_affected_impact_plan(
            root,
            (contract,),
            changed_paths=(IMPLEMENTATION_SURFACE_MAP_PATH,),
        )
        assert isinstance(plan, AffectedImpactPlan)
        expected_component = fingerprint_value(
            {
                "component_id": f"path:{IMPLEMENTATION_SURFACE_MAP_PATH}",
                "paths": [
                    {
                        "path": IMPLEMENTATION_SURFACE_MAP_PATH,
                        "fingerprint": inventory[0]["sha256"],
                    }
                ],
            }
        )
        assert plan.changed_components == (
            (f"path:{IMPLEMENTATION_SURFACE_MAP_PATH}", expected_component),
        )
        assert plan.affected_member_ids == ("map-owner",)

        broad_entry = _entry((".flowguard/**/*",))
        assert IMPLEMENTATION_SURFACE_MAP_PATH not in {
            row["path"] for row in resolve_entry_input_inventory(root, broad_entry)
        }
        mixed_entry = _entry((".flowguard/**/*", IMPLEMENTATION_SURFACE_MAP_PATH))
        assert resolve_entry_input_inventory(root, mixed_entry) == inventory

        missing_root = root / "missing"
        missing_root.mkdir()
        with pytest.raises(
            ModelRegressionManifestError,
            match="map-owner: input selection is invalid: repository evidence file is missing or inaccessible:",
        ):
            resolve_entry_input_inventory(missing_root, entry)


def test_repository_efficiency_manifest_does_not_require_an_absent_reverse_map():
    root = Path(__file__).resolve().parents[1]
    manifest = ModelRegressionManifest.load(root)
    impact = compile_model_impact_map(root, manifest)
    assert impact.ok, impact.errors
    assert tuple(
        sorted(
            entry.model_id
            for entry in manifest.entries
            if IMPLEMENTATION_SURFACE_MAP_PATH in entry.effective_input_patterns
        )
    ) == ()
    assert all(
        IMPLEMENTATION_SURFACE_MAP_PATH not in group.globs
        for group in manifest.shared_input_groups
    )
    owner_entries = {
        entry.model_id: entry for entry in manifest.entries
        if entry.model_id in {"authoritative_model_system", "behavior_commitment_ledger"}
    }
    assert set(owner_entries) == {
        "authoritative_model_system",
        "behavior_commitment_ledger",
    }
    assert all(
        "tests/test_reverse_surface_map_identity.py" in entry.effective_input_patterns
        for entry in owner_entries.values()
    )


def test_canonical_producer_owner_reference_replacement_keeps_semantic_identity():
    original = _map_payload()
    changed = copy.deepcopy(original)
    for collection in ("surfaces", "component_groups"):
        for row in changed[collection]:
            row["receipt_refs"] = [
                _OWNER_RECEIPT_NEW_REF if item == _OWNER_RECEIPT_OLD_REF else item
                for item in row["receipt_refs"]
            ]
    changed["terminal_receipt_refs"] = [
        _OWNER_RECEIPT_NEW_REF if item == _OWNER_RECEIPT_OLD_REF else item
        for item in changed["terminal_receipt_refs"]
    ]
    changed = _seal(changed)
    assert changed["authoring_fingerprint"] != original["authoring_fingerprint"]
    assert model_input_projection(changed) == model_input_projection(original)
    assert reverse_owner_semantic_map_fingerprint(changed) == reverse_owner_semantic_map_fingerprint(original)


@pytest.mark.parametrize(
    "reference",
    [
        "proofs/validation-owner-note.json#proof:validation-owner:original",
        "proofs/current.json#receipt:validation-ownerish:ledger:" + "a" * 32,
        "proofs/current.json#receipt:validation-owner:ledger:not-a-receipt-id",
        "proofs/current.json#receipt:validation-owner:ledger:" + "a" * 32,
        "../outside.json#receipt:validation-owner:ledger:" + "a" * 32,
        "/absolute.json#receipt:validation-owner:ledger:" + "a" * 32,
        "C:/outside.json#receipt:validation-owner:ledger:" + "a" * 32,
        "proofs/current.json#receipt:validation-owner:ledger:" + "a" * 32 + "#extra",
        "validation-owner:untyped-author-assertion",
    ],
)
def test_owner_reference_lookalikes_remain_authored_semantic_inputs(reference):
    original = _map_payload()
    changed = copy.deepcopy(original)
    changed["surfaces"][0]["receipt_refs"].append(reference)
    changed["terminal_receipt_refs"].append(reference)
    changed = _seal(changed)
    projected = model_input_projection(changed)
    assert reference in projected["surfaces"][0]["receipt_refs"]
    assert reference in projected["terminal_receipt_refs"]
    assert reverse_owner_semantic_map_fingerprint(changed) != reverse_owner_semantic_map_fingerprint(original)


@pytest.mark.parametrize("field", ["test_refs", "proof_refs", "model_obligation_ids"])
def test_authored_non_owner_bindings_remain_freshness_inputs(field):
    original = _map_payload()
    changed = copy.deepcopy(original)
    changed["surfaces"][0][field] = ["authored:new-semantic-binding"]
    changed = _seal(changed)
    assert reverse_owner_semantic_map_fingerprint(changed) != reverse_owner_semantic_map_fingerprint(original)
