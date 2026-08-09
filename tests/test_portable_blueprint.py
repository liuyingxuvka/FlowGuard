from __future__ import annotations

import json
from pathlib import Path

import pytest

from flowguard.implementation_blueprint import (
    CanonicalBlueprintProjection,
    _make_shard,
)
from flowguard.portable_blueprint import (
    PORTABLE_BLUEPRINT_BUNDLE_SCHEMA,
    PortableBlueprintBundleError,
    build_portable_blueprint_bundle,
    compact_portable_blueprint_projection,
    load_portable_blueprint_bundle,
    portable_blueprint_from_dict,
    verify_portable_blueprint_bundle,
    write_portable_blueprint_bundle,
)


def projection() -> CanonicalBlueprintProjection:
    return CanonicalBlueprintProjection(
        blueprint_fingerprint="sha256:blueprint",
        shards=(
            _make_shard(
                "identity",
                ({"blueprint_id": "blueprint:one", "member_ids": ["member:a"]},),
            ),
            _make_shard(
                "readiness",
                ({"readiness_kind": "static_blueprint", "status": "pass"},),
            ),
        ),
    )


def test_portable_bundle_round_trips_the_canonical_projection(tmp_path: Path):
    bundle = build_portable_blueprint_bundle(
        projection(),
        subject_revision="revision:one",
        target_profile="workflow",
        static_status="ready",
        execution_status="not_run",
    )
    output = write_portable_blueprint_bundle(bundle, tmp_path / "bundle.json")
    loaded = load_portable_blueprint_bundle(output)

    assert loaded.to_dict() == bundle.to_dict()
    verification = verify_portable_blueprint_bundle(loaded)
    assert verification.ok is True
    assert verification.status == "complete"
    assert verification.shard_count == 2
    assert verification.member_count == 3
    assert loaded.to_dict()["schema_version"] == PORTABLE_BLUEPRINT_BUNDLE_SCHEMA


def test_portable_bundle_rejects_changed_shard_and_stale_fingerprint():
    bundle = build_portable_blueprint_bundle(projection())
    payload = bundle.to_dict()
    payload["shards"][0]["payload"][0]["blueprint_id"] = "blueprint:changed"

    with pytest.raises(PortableBlueprintBundleError):
        portable_blueprint_from_dict(payload)

    verification = verify_portable_blueprint_bundle(
        bundle, expected_blueprint_fingerprint="sha256:other"
    )
    assert verification.ok is False
    assert verification.findings == ("blueprint_fingerprint_mismatch",)


def test_portable_bundle_rejects_unknown_status_and_reconstruction_claim():
    bundle = build_portable_blueprint_bundle(projection())
    payload = bundle.to_dict()
    payload["statuses"]["portable"] = "reconstruction"
    with pytest.raises(PortableBlueprintBundleError, match="current status"):
        portable_blueprint_from_dict(payload)

    payload = bundle.to_dict()
    payload["claim_boundary"] = "This is a reconstruction authority"
    with pytest.raises(PortableBlueprintBundleError, match="reconstruction"):
        portable_blueprint_from_dict(payload)


def test_portable_loader_rejects_duplicate_keys_and_non_finite_numbers(tmp_path: Path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"flowguard.portable_blueprint_bundle.v1",'
        '"schema_version":"flowguard.portable_blueprint_bundle.v1"}',
        encoding="utf-8",
    )
    with pytest.raises(PortableBlueprintBundleError, match="duplicate key"):
        load_portable_blueprint_bundle(duplicate)

    non_finite = tmp_path / "non-finite.json"
    non_finite.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(PortableBlueprintBundleError, match="non-finite"):
        load_portable_blueprint_bundle(non_finite)


def test_compact_portable_projection_is_bounded_and_deterministic():
    bundle = build_portable_blueprint_bundle(
        projection(), subject_revision="revision:one", target_profile="software"
    )
    compact = compact_portable_blueprint_projection(bundle, member_limit=1)

    assert compact["schema_version"] == "flowguard.portable_blueprint_compact.v1"
    assert compact["member_ids"] == ["blueprint:one"]
    assert compact["omitted_member_count"] == 2
    assert compact["statuses"] == {
        "static": "unknown",
        "portable": "ready",
        "execution": "not_run",
    }
    assert compact["compact_fingerprint"].startswith("sha256:")
    assert json.loads(json.dumps(compact)) == compact
