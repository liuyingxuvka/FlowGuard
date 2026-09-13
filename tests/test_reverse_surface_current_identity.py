import copy
from types import SimpleNamespace
from pathlib import Path

import flowguard.behavior_surface_audit as surface_audit
import flowguard.reverse_surface_owner_authority as reverse_owner_authority
from flowguard.behavior_surface_audit import (
    IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA,
    IMPLEMENTATION_SURFACE_MAP_SCHEMA,
    audit_implementation_behavior_surface,
    discover_implementation_behavior_surfaces,
    _surface_hash,
)


def test_reverse_owner_contract_binds_exact_semantic_map_fingerprint():
    semantic_map_fingerprint = "sha256:" + "a" * 64
    contract = reverse_owner_authority.build_reverse_owner_contract(
        route="fixture-owner",
        model_ids=("fixture-model",),
        authority_identity={
            "head_fingerprint": "sha256:" + "1" * 64,
            "snapshot_fingerprint": "sha256:" + "2" * 64,
            "revision_set_fingerprint": "sha256:" + "3" * 64,
            "activation_receipt_fingerprint": "sha256:" + "4" * 64,
        },
        discovery_fingerprint="sha256:" + "5" * 64,
        owner_bindings_fingerprint="sha256:" + "6" * 64,
        route_set_fingerprint="sha256:" + "7" * 64,
        model_parent_fingerprint="sha256:" + "8" * 64,
        semantic_map_fingerprint=semantic_map_fingerprint,
        child_receipts={
            "fixture-model": SimpleNamespace(
                fingerprint="sha256:" + "9" * 64
            )
        },
    )

    assert dict(contract.projected_inputs)["reverse-surface:semantic-map"] == (
        semantic_map_fingerprint
    )


def _fixture_root(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text(
        "def run():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "proof.txt").write_text("n/a-proof\n", encoding="utf-8")
    (tmp_path / "receipt.txt").write_text("terminal-pass\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "def test_run_surface():\n    assert True\n",
        encoding="utf-8",
    )
    # This file only marks a modeled target for the loader seam.  The test
    # replaces the native loader with a frozen current authority projection.
    project = tmp_path / ".flowguard"
    project.mkdir()
    (project / "project.toml").write_text("[project]\n", encoding="utf-8")
    return tmp_path


def _current_join() -> dict:
    body = {
        "schema_version": IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA,
        "head_fingerprint": "sha256:" + "1" * 64,
        "snapshot_fingerprint": "sha256:" + "2" * 64,
        "revision_set_fingerprint": "sha256:" + "3" * 64,
        "activation_receipt_fingerprint": "sha256:" + "4" * 64,
        "model_owner_ids": ["fixture-model"],
        "owner_receipt_identities": [
            {
                "owner_route": "fixture-owner",
                "receipt_id": "receipt:fixture-owner:current",
                "receipt_fingerprint": "sha256:" + "5" * 64,
                "subject_fingerprint": "sha256:" + "2" * 64,
                "candidate_snapshot_fingerprint": "sha256:" + "2" * 64,
            }
        ],
    }
    return {**body, "join_fingerprint": _surface_hash(body)}


def _complete_map(discovery: dict, join: dict) -> dict:
    surfaces = []
    for row in discovery["surfaces"]:
        surfaces.append(
            {
                "surface_id": row["surface_id"],
                "owner": "fixture-owner",
                "owner_receipt_id": "receipt:fixture-owner:current",
                "owner_receipt_fingerprint": "sha256:" + "5" * 64,
                "test_refs": ["tests/test_app.py#test_run_surface"],
                "receipt_refs": ["receipt.txt#terminal-pass"],
                "disposition": "retired_proven",
                "proof_ref": "proof.txt#n/a-proof",
                "reason": "the fixture source observation is intentionally retired",
            }
        )
    return {
        "schema_version": IMPLEMENTATION_SURFACE_MAP_SCHEMA,
        "inventory_id": "fixture-current-identity",
        "project_boundary": "fixture source boundary",
        "current_revision": "fixture-v1",
        "discovery_fingerprint": discovery["discovery_fingerprint"],
        "claim_boundary": "fixture reverse closure with current identity join",
        "current_authority_join": copy.deepcopy(join),
        "surfaces": surfaces,
        "model_obligations": [
            {
                "obligation_id": "obligation:model-only",
                "disposition": "model_only_proven",
                "surface_ids": [],
                "proof_ref": "proof.txt#n/a-proof",
                "reason": "the fixture has no executable model obligation",
            }
        ],
    }


def test_modeled_reverse_map_requires_an_exact_current_join(monkeypatch, tmp_path):
    root = _fixture_root(tmp_path)
    join = _current_join()
    monkeypatch.setattr(surface_audit, "_load_current_authority_join", lambda _root: join)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_map(discovery, join)

    accepted = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert accepted["status"] == "passed", accepted["findings"]
    assert accepted["current_authority_join"]["status"] == "current"

    missing = copy.deepcopy(mapping)
    missing.pop("current_authority_join")
    blocked = audit_implementation_behavior_surface(root, missing, discovery=discovery)
    assert blocked["status"] == "blocked"
    assert "implementation_surface_current_authority_join_missing" in {
        row["code"] for row in blocked["findings"]
    }


def test_light_reverse_currentness_reuses_unchanged_source_pointer(monkeypatch, tmp_path):
    root = _fixture_root(tmp_path)
    join = _current_join()
    monkeypatch.setattr(surface_audit, "_load_current_authority_join", lambda _root: join)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_map(discovery, join)
    hash_calls: list[Path] = []
    original_hash = surface_audit._sha256_file

    def counted_hash(path: Path) -> str:
        hash_calls.append(path)
        return original_hash(path)

    monkeypatch.setattr(surface_audit, "_sha256_file", counted_hash)
    accepted = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
        currentness_profile="light",
    )
    assert accepted["status"] == "passed", accepted["findings"]
    assert hash_calls == []

    exact = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
        currentness_profile="full",
    )
    assert exact["status"] == "passed", exact["findings"]
    assert hash_calls


def test_current_model_or_receipt_identity_drift_is_fail_closed(monkeypatch, tmp_path):
    root = _fixture_root(tmp_path)
    join = _current_join()
    monkeypatch.setattr(surface_audit, "_load_current_authority_join", lambda _root: join)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_map(discovery, join)

    stale_join = copy.deepcopy(mapping)
    stale_join["current_authority_join"]["snapshot_fingerprint"] = "sha256:" + "9" * 64
    stale = audit_implementation_behavior_surface(root, stale_join, discovery=discovery)
    assert stale["status"] == "blocked"
    assert "implementation_surface_current_authority_identity_mismatch" in {
        row["code"] for row in stale["findings"]
    }

    stale_receipt = copy.deepcopy(mapping)
    stale_receipt["surfaces"][0]["owner_receipt_fingerprint"] = "sha256:" + "8" * 64
    receipt_gap = audit_implementation_behavior_surface(
        root,
        stale_receipt,
        discovery=discovery,
    )
    assert receipt_gap["status"] == "blocked"
    assert "implementation_surface_current_owner_receipt_mismatch" in {
        row["code"] for row in receipt_gap["findings"]
    }


def test_malformed_native_owner_receipt_join_cannot_be_current(monkeypatch, tmp_path):
    root = _fixture_root(tmp_path)
    join = _current_join()
    join["owner_receipt_identities"].append(
        {
            "owner_route": "fixture-owner",
            "receipt_id": "receipt:fixture-owner:current",
            "receipt_fingerprint": "sha256:" + "6" * 64,
            "subject_fingerprint": "sha256:" + "2" * 64,
            "candidate_snapshot_fingerprint": "sha256:" + "2" * 64,
        }
    )
    monkeypatch.setattr(surface_audit, "_load_current_authority_join", lambda _root: join)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_map(discovery, join)

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    codes = {row["code"] for row in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert blocked["current_authority_join"]["status"] == "blocked"
    assert "implementation_surface_current_authority_owner_receipt_duplicate" in codes
    assert "implementation_surface_current_authority_join_fingerprint_mismatch" in codes


def test_persistent_reverse_owner_receipt_replaces_delta_local_identity(
    monkeypatch, tmp_path
):
    """The reverse denominator has one canonical receipt per persistent route."""

    def identity(route: str, receipt_id: str, marker: str) -> dict[str, str]:
        return {
            "owner_route": route,
            "receipt_id": receipt_id,
            "receipt_fingerprint": "sha256:" + marker * 64,
            "subject_fingerprint": "sha256:" + "2" * 64,
            "candidate_snapshot_fingerprint": "sha256:" + "2" * 64,
        }

    state = SimpleNamespace(
        head=SimpleNamespace(
            fingerprint="sha256:" + "1" * 64,
            snapshot_fingerprint="sha256:" + "2" * 64,
            accepted_revision_set_fingerprint="sha256:" + "3" * 64,
            activation_receipt_fingerprint="sha256:" + "4" * 64,
        ),
        snapshot=SimpleNamespace(
            model_instances=[SimpleNamespace(logical_model_id="fixture-model")]
        ),
        accepted_revision=SimpleNamespace(
            completed_evidence_refs=[
                identity("persistent-route", "receipt:delta", "5"),
                identity("revision-only-route", "receipt:revision", "6"),
            ]
        ),
    )
    persistent = identity("persistent-route", "receipt:persistent", "7")
    monkeypatch.setattr(
        reverse_owner_authority,
        "load_current_reverse_surface_owner_authority",
        lambda _root, *, authority_identity: {
            "owner_receipt_identities": [persistent],
        },
    )

    joined = surface_audit._current_authority_join_payload(state, root=tmp_path)
    rows = joined["owner_receipt_identities"]

    assert [(row["owner_route"], row["receipt_id"]) for row in rows] == [
        ("persistent-route", "receipt:persistent"),
        ("revision-only-route", "receipt:revision"),
    ]
    assert len({row["owner_route"] for row in rows}) == len(rows)


def test_current_behavior_ledger_join_rejects_invented_intent_and_obligation(
    monkeypatch, tmp_path
):
    root = _fixture_root(tmp_path)
    join = _current_join()
    monkeypatch.setattr(surface_audit, "_load_current_authority_join", lambda _root: join)
    inventory = root / ".flowguard" / "behavior" / "inventory"
    inventory.mkdir(parents=True)
    (inventory / "ledger.json").write_text(
        """
{
  "ledger_id": "fixture-ledger",
  "current_revision": "fixture-ledger-v1",
  "commitments": [
    {
      "commitment_id": "commitment:fixture",
      "business_intent_id": "intent:fixture",
      "primary_owner_model_id": ".flowguard/models/owners/fixture/model.py",
      "evidence": {
        "model_obligation_ids": ["obligation:fixture"],
        "current": true,
        "evidence_state": "current_pass"
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_map(discovery, join)
    mapping["current_behavior_ledger_join"] = (
        surface_audit._load_current_behavior_ledger_join(root)
    )
    mapping["model_obligations"] = [
        {
            "obligation_id": "obligation:fixture",
            "disposition": "model_only_proven",
            "surface_ids": [],
            "proof_ref": "proof.txt#n/a-proof",
            "reason": "the fixture model obligation is intentionally not an implementation row",
        }
    ]

    accepted = audit_implementation_behavior_surface(
        root, mapping, discovery=discovery
    )
    assert accepted["status"] == "passed", accepted["findings"]
    assert accepted["current_behavior_ledger_join"]["status"] == "current"
    assert accepted["current_model_obligation_ids"] == ["obligation:fixture"]

    invented = copy.deepcopy(mapping)
    invented["current_behavior_ledger_join"]["intent_ids"] = ["intent:invented"]
    blocked = audit_implementation_behavior_surface(
        root, invented, discovery=discovery
    )
    assert blocked["status"] == "blocked"
    assert "implementation_surface_current_behavior_ledger_identity_mismatch" in {
        row["code"] for row in blocked["findings"]
    }

    invented_obligation = copy.deepcopy(mapping)
    invented_obligation["model_obligations"][0]["obligation_id"] = (
        "obligation:invented"
    )
    blocked_obligation = audit_implementation_behavior_surface(
        root, invented_obligation, discovery=discovery
    )
    assert blocked_obligation["status"] == "blocked"
    assert "implementation_surface_model_obligation_current_unknown" in {
        row["code"] for row in blocked_obligation["findings"]
    }
