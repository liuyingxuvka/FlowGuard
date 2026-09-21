"""Focused writer-bound selected-read receipts for the public map projection."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from flowguard.affected_blueprint_reader import (
    AffectedBlueprintReadError,
    load_affected_blueprint_projection,
)
from tests.test_blueprint_cli_routes import BlueprintCliRouteTests as _ProjectionFixture

_ProjectionFixture.__test__ = False


def _projection_fixture(tmp_path: Path) -> Path:
    fixture = _ProjectionFixture(
        "test_retired_affected_understanding_cli_route_is_rejected"
    )
    return fixture._write_selective_projection_fixture(tmp_path)


def test_writer_publishes_one_projection_bound_offset_cache(tmp_path: Path):
    projection_root = _projection_fixture(tmp_path)
    manifest = json.loads(
        (projection_root / "manifest.json").read_text(encoding="utf-8")
    )
    projection_fingerprint = str(manifest["projection_fingerprint"])
    cache_path = projection_root.parent / (
        f".{projection_root.name}.lookup-cache-"
        f"{projection_fingerprint.removeprefix('sha256:')}.json"
    )

    assert cache_path.is_file()
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["schema_version"] == "flowguard.projection_lookup_cache.v1"
    assert cache["projection_fingerprint"] == projection_fingerprint
    assert set(cache["containers"]) == {"behavior_shards", "shared_objects"}

    bundle = load_affected_blueprint_projection(
        projection_root,
        authority_root=Path.cwd(),
    )
    try:
        assert bundle.projection_fingerprint == projection_fingerprint
        assert bundle.index.fingerprint
        shard_id = sorted(dict(bundle.index.shard_fingerprints))[0]
        object_id = sorted(dict(bundle.index.object_fingerprints))[0]
        assert bundle.load_shard(shard_id)["shard_id"] == shard_id
        assert bundle.load_object(object_id)
    finally:
        bundle.close()


def test_selected_read_rejects_ancestor_cache_rescue(tmp_path: Path):
    projection_root = _projection_fixture(tmp_path)
    manifest = json.loads(
        (projection_root / "manifest.json").read_text(encoding="utf-8")
    )
    projection_fingerprint = str(manifest["projection_fingerprint"])
    exact_cache = projection_root.parent / (
        f".{projection_root.name}.lookup-cache-"
        f"{projection_fingerprint.removeprefix('sha256:')}.json"
    )
    legacy_ancestor_cache = (
        projection_root.parent
        / "work"
        / "flowguard"
        / "canonical-blueprint"
        / "lookup-cache"
        / f"{projection_fingerprint.removeprefix('sha256:')}.json"
    )
    legacy_ancestor_cache.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exact_cache, legacy_ancestor_cache)
    exact_cache.unlink()

    with pytest.raises(AffectedBlueprintReadError, match="projection_lookup_missing"):
        load_affected_blueprint_projection(
            projection_root,
            authority_root=Path.cwd(),
        )
