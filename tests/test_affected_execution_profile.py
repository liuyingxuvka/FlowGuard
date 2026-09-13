from __future__ import annotations

from pathlib import Path

from flowguard.affected_blueprint_reader import AffectedImpactPlan
from flowguard.validation_ownership import (
    _prepare_owner_receipt,
    _publish_prepared_owner_receipt,
    ValidationOwnerContract,
    build_affected_impact_plan,
    build_owner_current,
    validate_affected_impact_plan,
)
from flowguard.validation_results import ValidationChildResult


def _contracts() -> tuple[ValidationOwnerContract, ...]:
    return (
        ValidationOwnerContract(
            owner_id="owner_a",
            command=("python", "-c", "pass"),
            input_patterns=("src/a.py",),
            obligation_ids=("model:a",),
        ),
        ValidationOwnerContract(
            owner_id="owner_b",
            command=("python", "-c", "pass"),
            input_patterns=("src/b.py",),
            obligation_ids=("model:b",),
            dependency_owner_ids=("owner_a",),
        ),
        ValidationOwnerContract(
            owner_id="owner_c",
            command=("python", "-c", "pass"),
            input_patterns=("src/c.py",),
            obligation_ids=("model:c",),
        ),
    )


def _root(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "src" / name).write_text(f"# {name}\n", encoding="utf-8")
    return tmp_path


def _components(owner: str, path: str, component: str) -> dict[str, object]:
    return {
        component: {
            "paths": [path],
            "owner_id": owner,
            "model_obligation_ids": [f"obligation:{owner}"],
            "test_owner_ids": [f"test:{owner}"],
            "evidence_owner_ids": [f"evidence:{owner}"],
        }
    }


def _publish_owner_receipt(
    root: Path,
    contract: ValidationOwnerContract,
) -> tuple[str, str]:
    """Publish one genuine supervised-owner-shaped fixture receipt."""

    store = root / ".flowguard" / "evidence" / "validation-owners"
    current = build_owner_current(root, contract, all_contracts=(contract,))
    prepared = _prepare_owner_receipt(
        current,
        ValidationChildResult(
            contract.owner_id,
            "pass",
            "fixture producer passed",
            claim_boundary="fixture owner evidence",
            payload={"fixture": True},
        ),
        store,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        publication_kind="supervised_producer",
    )
    receipt = _publish_prepared_owner_receipt(prepared, root, store)
    return receipt.receipt_id, receipt.fingerprint


def test_missing_changed_path_is_blocked_without_a_producer(tmp_path: Path) -> None:
    plan = build_affected_impact_plan(
        _root(tmp_path),
        _contracts(),
        changed_paths=(),
    )
    assert plan.status == "blocked"
    assert not plan.ok
    assert "changed_paths_missing" in plan.unknown_impact_blockers
    assert plan.affected_member_ids == ()


def test_unmapped_and_ambiguous_paths_are_blocked(tmp_path: Path) -> None:
    root = _root(tmp_path)
    unmapped = build_affected_impact_plan(
        root,
        _contracts(),
        changed_paths=("src/unknown.py",),
        component_bindings={"known": {"paths": ["src/a.py"], "owner_id": "owner_a"}},
    )
    assert unmapped.status == "blocked"
    assert any(item.startswith("unmapped_path:") for item in unmapped.unknown_impact_blockers)

    ambiguous = build_affected_impact_plan(
        root,
        _contracts(),
        changed_paths=("src/a.py",),
        component_bindings=(
            {"component_id": "first", "paths": ["src/a.py"], "owner_id": "owner_a"},
            {"component_id": "second", "paths": ["src/a.py"], "owner_id": "owner_b"},
        ),
    )
    assert ambiguous.status == "blocked"
    assert any(item.startswith("ambiguous_path_component:") for item in ambiguous.unknown_impact_blockers)


def test_exact_component_owner_and_dependency_closure_excludes_unrelated_sibling(tmp_path: Path) -> None:
    plan = build_affected_impact_plan(
        _root(tmp_path),
        _contracts(),
        changed_paths=("src/a.py",),
        component_bindings=_components("owner_a", "src/a.py", "component:a"),
    )
    assert plan.ok
    assert plan.affected_member_ids == ("owner_a", "owner_b")
    assert "owner_c" not in plan.affected_member_ids
    assert "model:a" in plan.affected_model_obligation_ids
    assert "model:b" in plan.affected_model_obligation_ids
    assert "test:owner_a" in plan.affected_test_owner_ids
    assert plan.claim_boundary.startswith("This receipt proves one exact current affected closure")


def test_partial_component_map_is_completed_from_unique_owner_patterns(tmp_path: Path) -> None:
    plan = build_affected_impact_plan(
        _root(tmp_path),
        _contracts(),
        changed_paths=("src/a.py", "src/b.py"),
        component_bindings=_components("owner_a", "src/a.py", "component:a"),
    )

    assert plan.ok
    assert plan.affected_member_ids == ("owner_a", "owner_b")
    assert {item for item, _fingerprint in plan.changed_components} == {
        "component:a",
        "path:src/b.py",
    }


def test_reuse_current_requires_a_receipt_and_plan_round_trips_current_schema(tmp_path: Path) -> None:
    fingerprint = "sha256:" + "a" * 64
    plan = build_affected_impact_plan(
        _root(tmp_path),
        _contracts(),
        changed_paths=("src/a.py",),
        component_bindings=_components("owner_a", "src/a.py", "component:a"),
        owner_dispositions={"owner_a": "reuse_current", "owner_b": "execute"},
        owner_receipts={"owner_a": {"receipt_id": "receipt:owner-a", "receipt_fingerprint": fingerprint}},
    )
    assert plan.ok
    decoded = AffectedImpactPlan.from_dict(plan.to_dict())
    assert decoded.fingerprint == plan.fingerprint
    assert validate_affected_impact_plan(decoded, selected_member_ids=("owner_a", "owner_b")).ok


def test_reuse_current_requires_a_canonical_current_receipt(tmp_path: Path) -> None:
    root = _root(tmp_path)
    contract = _contracts()[0]
    receipt_id, receipt_fingerprint = _publish_owner_receipt(root, contract)
    plan = build_affected_impact_plan(
        root,
        _contracts(),
        changed_paths=("src/a.py",),
        component_bindings=_components("owner_a", "src/a.py", "component:a"),
        owner_dispositions={"owner_a": "reuse_current"},
        owner_receipts={
            "owner_a": {
                "receipt_id": receipt_id,
                "receipt_fingerprint": receipt_fingerprint,
            }
        },
    )

    row = next(item for item in plan.owner_rows if item.owner_id == "owner_a")
    assert plan.ok
    assert row.disposition == "reuse_current"
    assert row.receipt_id == receipt_id
    assert row.receipt_fingerprint == receipt_fingerprint


def test_missing_stale_and_foreign_receipts_fall_back_to_execute(tmp_path: Path) -> None:
    root = _root(tmp_path)
    contracts = _contracts()
    owner_a = contracts[0]
    owner_b = contracts[1]
    foreign_id, foreign_fingerprint = _publish_owner_receipt(root, owner_b)
    component = _components("owner_a", "src/a.py", "component:a")

    def build(receipt_id: str, receipt_fingerprint: str):
        plan = build_affected_impact_plan(
            root,
            contracts,
            changed_paths=("src/a.py",),
            component_bindings=component,
            owner_dispositions={"owner_a": "reuse_current"},
            owner_receipts={
                "owner_a": {
                    "receipt_id": receipt_id,
                    "receipt_fingerprint": receipt_fingerprint,
                }
            },
        )
        return next(item for item in plan.owner_rows if item.owner_id == "owner_a")

    missing = build(
        "receipt:validation-owner:owner_a:missing",
        "sha256:" + "a" * 64,
    )
    assert missing.disposition == "execute"
    assert not missing.receipt_id

    stale_id, stale_fingerprint = _publish_owner_receipt(root, owner_a)
    (root / "src" / "a.py").write_text("# changed after receipt\n", encoding="utf-8")
    stale = build(stale_id, stale_fingerprint)
    assert stale.disposition == "execute"
    assert not stale.receipt_id

    foreign = build(foreign_id, foreign_fingerprint)
    assert foreign.disposition == "execute"
    assert not foreign.receipt_id


def test_multi_path_component_gets_one_aggregate_identity(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "src" / "a_extra.py").write_text("# extra\n", encoding="utf-8")
    contracts = (
        ValidationOwnerContract(
            owner_id="owner_a",
            command=("python", "-c", "pass"),
            input_patterns=("src/a.py", "src/a_extra.py"),
            obligation_ids=("model:a",),
        ),
    )
    plan = build_affected_impact_plan(
        root,
        contracts,
        changed_paths=("src/a.py", "src/a_extra.py"),
        component_bindings={
            "component:a": {
                "paths": ["src/a.py", "src/a_extra.py"],
                "owner_id": "owner_a",
            }
        },
    )
    assert plan.ok
    assert len(plan.changed_components) == 1
    assert plan.changed_components[0][0] == "component:a"


def test_reparse_or_escape_path_is_blocked(tmp_path: Path) -> None:
    root = _root(tmp_path)
    outside = tmp_path.parent / "outside-flowguard.py"
    outside.write_text("# outside\n", encoding="utf-8")
    plan = build_affected_impact_plan(
        root,
        _contracts(),
        changed_paths=("../outside-flowguard.py",),
    )
    assert plan.status == "blocked"
    assert any("repository-relative" in item for item in plan.unknown_impact_blockers)


def test_wire_reader_rejects_scalar_id_arrays() -> None:
    fingerprint = "sha256:" + "a" * 64
    payload = {
        "schema_version": "flowguard.affected_impact_plan.v1",
        "status": "pass",
        "ok": True,
        "changed_paths": ["src/a.py"],
        "changed_components": [
            {"component_id": "component:a", "fingerprint": fingerprint}
        ],
        "affected_member_ids": "owner_a",
        "affected_model_obligation_ids": [],
        "affected_test_owner_ids": [],
        "affected_evidence_owner_ids": [],
        "required_parent_dependencies": [],
        "required_sibling_dependencies": [],
        "unknown_impact_blockers": [],
        "source_fingerprint": fingerprint,
        "model_fingerprint": fingerprint,
        "test_fingerprint": fingerprint,
        "owner_fingerprint": fingerprint,
        "owner_rows": [],
        "claim_boundary": "boundary",
        "fingerprint": fingerprint,
    }
    import pytest

    with pytest.raises(ValueError, match="JSON array"):
        AffectedImpactPlan.from_dict(payload)
