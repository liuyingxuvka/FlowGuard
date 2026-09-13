"""Finite patch-manifest and review-map boundary regressions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.check_closure_patch_regressions as patch_review
from scripts.build_direct_model_rebuild_inputs import _load_review_map


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _manifest_row(path: str, value: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha(value)}


def _change_manifest(
    root: Path,
    baseline: list[dict[str, str]],
    current: list[dict[str, str]],
    changed: list[str],
) -> dict[str, object]:
    return {
        "schema": patch_review.CHANGE_MANIFEST_SCHEMA,
        "work_id": "flowguard-usability-closure-test",
        "root": str(root.resolve()),
        "baseline_input_manifest": baseline,
        "current_input_manifest": current,
        "changed_paths": changed,
    }


def test_change_manifest_derives_changed_paths_and_checks_live_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    current = (_manifest_row("flowguard/current.py", "new"),)
    baseline = (_manifest_row("flowguard/current.py", "old"),)
    monkeypatch.setattr(patch_review, "validation_input_manifest", lambda root: current)
    path = tmp_path / "change-manifest.json"
    path.write_text(
        json.dumps(
            _change_manifest(tmp_path, list(baseline), list(current), ["flowguard/current.py"])
        ),
        encoding="utf-8",
    )
    loaded = patch_review._load_change_manifest(path, tmp_path)
    assert loaded["changed_paths"] == ("flowguard/current.py",)
    assert loaded["work_id"] == "flowguard-usability-closure-test"


def test_change_manifest_rejects_forged_changed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    current = (_manifest_row("flowguard/current.py", "same"),)
    baseline = (_manifest_row("flowguard/current.py", "same"),)
    monkeypatch.setattr(patch_review, "validation_input_manifest", lambda root: current)
    path = tmp_path / "change-manifest.json"
    path.write_text(
        json.dumps(
            _change_manifest(tmp_path, list(baseline), list(current), ["flowguard/current.py"])
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match"):
        patch_review._load_change_manifest(path, tmp_path)


def test_missing_change_manifest_blocks_without_running_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        patch_review,
        "validation_input_manifest",
        lambda root: (_manifest_row("flowguard/current.py", "same"),),
    )
    called = {"value": False}

    def fail_if_started(*args, **kwargs):
        called["value"] = True
        raise AssertionError("pytest producer must not start without a manifest")

    monkeypatch.setattr(patch_review, "run_supervised", fail_if_started)
    assert patch_review.run(tmp_path, tmp_path / "out") == 1
    assert not called["value"]
    payload = json.loads((tmp_path / "out" / "patch-regression.json").read_text())
    assert payload["blockers"] == ["change_manifest_required"]


def test_review_map_embedded_current_table_rejects_self_hashed_stale_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    old = (_manifest_row("flowguard/current.py", "old"),)
    live = (_manifest_row("flowguard/current.py", "new"),)
    monkeypatch.setattr(
        "scripts.build_direct_model_rebuild_inputs.validation_input_manifest",
        lambda root: live,
    )
    body = {
        "schema_version": "flowguard.model_review_map.v1",
        "scope": "patch_regression",
        "root": str(tmp_path.resolve()),
        "work_id": "work-1",
        "changed_paths": ["flowguard/current.py"],
        "planned_changed_paths": ["flowguard/current.py"],
        "tested_input_manifest": [dict(row) for row in old],
        "tested_input_manifest_fingerprint": patch_review.manifest_fingerprint(old),
        "current_input_manifest": [dict(row) for row in old],
        "baseline_input_manifest": [dict(row) for row in old],
        "allowed_model_ids": ["alpha"],
        "model_decisions": [],
        "decision": "review_changed_inputs_only",
        "claim_boundary": "finite patch review input with explicit source binding",
    }
    body["review_map_fingerprint"] = _sha(
        json.dumps(
            {key: value for key, value in body.items() if key != "review_map_fingerprint"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    path = tmp_path / "review-map.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no longer current|stale"):
        _load_review_map(path, tmp_path)


def test_no_semantic_delta_does_not_authorize_all_models(monkeypatch: pytest.MonkeyPatch):
    class Manifest:
        entries = (
            SimpleNamespace(model_id="alpha", excluded=False, effective_input_patterns=("flowguard/*.py",)),
            SimpleNamespace(model_id="beta", excluded=False, effective_input_patterns=("flowguard/*.py",)),
        )

        @staticmethod
        def shared_patterns_for(model_id: str):
            return ()

    monkeypatch.setattr(patch_review.ModelRegressionManifest, "load", lambda root: Manifest())
    result = patch_review._model_review_map(
        Path("."),
        (),
        (),
    )
    assert result["decision"] == "no_semantic_change"
    assert result["allowed_model_ids"] == []


def test_unrelated_input_delta_does_not_authorize_topology_owner(
    monkeypatch: pytest.MonkeyPatch,
):
    class Manifest:
        entries = (
            SimpleNamespace(
                model_id="authoritative_model_system",
                excluded=False,
                effective_input_patterns=(".flowguard/models/authority.py",),
            ),
        )

        @staticmethod
        def shared_patterns_for(model_id: str):
            return ()

    monkeypatch.setattr(patch_review.ModelRegressionManifest, "load", lambda root: Manifest())
    result = patch_review._model_review_map(
        Path("."),
        ("docs/README.md",),
        (_manifest_row("docs/README.md", "current"),),
    )
    assert result["allowed_model_ids"] == []


def test_shared_input_delta_authorizes_every_declared_consumer(
    monkeypatch: pytest.MonkeyPatch,
):
    class Manifest:
        entries = (
            SimpleNamespace(
                model_id="alpha",
                excluded=False,
                effective_input_patterns=("flowguard/alpha.py",),
            ),
            SimpleNamespace(
                model_id="beta",
                excluded=False,
                effective_input_patterns=("flowguard/beta.py",),
            ),

        )

        @staticmethod
        def shared_patterns_for(model_id: str):
            return ("shared/registry.json",) if model_id in {"alpha", "beta"} else ()

    monkeypatch.setattr(patch_review.ModelRegressionManifest, "load", lambda root: Manifest())
    result = patch_review._model_review_map(
        Path("."),
        ("shared/registry.json",),
        (_manifest_row("shared/registry.json", "current"),),
    )
    assert result["allowed_model_ids"] == ["alpha", "beta"]
    assert all(
        row["matched_paths"] == ["shared/registry.json"]
        for row in result["model_decisions"]
    )


def test_semantic_source_delta_authorizes_only_typed_topology_owner(
    monkeypatch: pytest.MonkeyPatch,
):
    class Manifest:
        entries = (
            SimpleNamespace(
                model_id="authoritative_model_system",
                excluded=False,
                effective_input_patterns=(".flowguard/models/authority.py",),
            ),
            SimpleNamespace(
                model_id="child_model",
                excluded=False,
                effective_input_patterns=("flowguard/child.py",),
            ),
            SimpleNamespace(
                model_id="excluded_model",
                excluded=True,
                effective_input_patterns=("flowguard/excluded.py",),
            ),
        )

        @staticmethod
        def shared_patterns_for(model_id: str):
            return ()

    monkeypatch.setattr(patch_review.ModelRegressionManifest, "load", lambda root: Manifest())
    result = patch_review._model_review_map(
        Path("."),
        ("flowguard/implementation_inventory.py",),
        (_manifest_row("flowguard/implementation_inventory.py", "current"),),
    )
    assert result["allowed_model_ids"] == ["authoritative_model_system"]
    assert {
        row["disposition"] for row in result["model_decisions"]
    } == {"review_changed_topology"}
