"""Direct rebuild helpers keep one candidate and explicit relation ownership."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.build_direct_model_rebuild_inputs import (
    _intent_review_models,
    _load_review_map,
    _relation_targets,
    _write_json,
)


def test_write_json_is_write_once_or_identical(tmp_path: Path):
    path = tmp_path / "output.json"
    _write_json(path, {"value": 1})
    _write_json(path, {"value": 1})
    with pytest.raises(RuntimeError, match="different content"):
        _write_json(path, {"value": 2})


def test_relation_targets_use_typed_model_endpoints_not_id_substrings():
    relation = SimpleNamespace(
        relation_id="relation:opaque-name",
        source=SimpleNamespace(endpoint_kind="model_instance", endpoint_id="model:alpha"),
        target=SimpleNamespace(endpoint_kind="parent_closure", endpoint_id="parent:domain"),
    )
    diff = SimpleNamespace(changed_relation_ids=("relation:opaque-name",))
    snapshot = SimpleNamespace(relations=(relation,))
    result = _relation_targets(
        diff,
        ("alpha", "beta"),
        base_snapshot=snapshot,
        candidate_snapshot=snapshot,
    )
    assert result == {"alpha": ("relation:opaque-name",), "beta": ()}


def test_intent_review_models_match_single_relation_owner():
    relation = SimpleNamespace(
        relation_id="relation:opaque-name",
        source=SimpleNamespace(endpoint_kind="model_instance", endpoint_id="model:alpha"),
        target=SimpleNamespace(endpoint_kind="model_instance", endpoint_id="model:beta"),
    )
    diff = SimpleNamespace(changed_relation_ids=("relation:opaque-name",))
    snapshot = SimpleNamespace(relations=(relation,))
    result = _intent_review_models(
        diff,
        (),
        base_snapshot=snapshot,
        candidate_snapshot=snapshot,
    )
    assert result == ("alpha",)


def test_changed_relation_only_reviews_the_changed_model_endpoint():
    base_relation = SimpleNamespace(
        relation_id="relation:semantic-model-affects-consumer:alpha:beta",
        kind="affects",
        source=SimpleNamespace(
            endpoint_kind="model_instance",
            endpoint_id="model:alpha",
            fingerprint="sha256:alpha-old",
        ),
        target=SimpleNamespace(
            endpoint_kind="model_instance",
            endpoint_id="model:beta",
            fingerprint="sha256:beta-old",
        ),
    )
    candidate_relation = SimpleNamespace(
        relation_id=base_relation.relation_id,
        kind=base_relation.kind,
        source=base_relation.source,
        target=SimpleNamespace(
            endpoint_kind="model_instance",
            endpoint_id="model:beta",
            fingerprint="sha256:beta-new",
        ),
    )
    diff = SimpleNamespace(changed_relation_ids=(base_relation.relation_id,))
    base = SimpleNamespace(relations=(base_relation,))
    candidate = SimpleNamespace(relations=(candidate_relation,))

    assert _intent_review_models(
        diff,
        (),
        base_snapshot=base,
        candidate_snapshot=candidate,
    ) == ("beta",)
    assert _relation_targets(
        diff,
        ("alpha", "beta"),
        base_snapshot=base,
        candidate_snapshot=candidate,
    ) == {"alpha": (), "beta": (base_relation.relation_id,)}


def test_review_map_fingerprint_is_verified_before_candidate_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from flowguard.validation_ownership import manifest_fingerprint

    tested = []
    monkeypatch.setattr(
        "scripts.build_direct_model_rebuild_inputs.validation_input_manifest",
        lambda root: tuple(tested),
    )
    body = {
        "schema_version": "flowguard.model_review_map.v1",
        "scope": "patch_regression",
        "root": str(tmp_path.resolve()),
        "work_id": "work-1",
        "allowed_model_ids": ["alpha"],
        "changed_paths": ["flowguard/example.py"],
        "planned_changed_paths": ["flowguard/example.py"],
        "tested_input_manifest": tested,
        "tested_input_manifest_fingerprint": manifest_fingerprint(tested),
        "model_decisions": [],
        "decision": "review_changed_inputs_only",
        "claim_boundary": "finite patch review input",
    }
    import hashlib

    body["review_map_fingerprint"] = "sha256:" + hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    path = tmp_path / "review-map.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    assert _load_review_map(path, tmp_path)["allowed_model_ids"] == ["alpha"]
    body["allowed_model_ids"] = ["beta"]
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(RuntimeError, match="fingerprint"):
        _load_review_map(path, tmp_path)


def test_review_map_without_typed_current_observation_is_rejected(tmp_path: Path):
    body = {
        "schema_version": "flowguard.model_review_map.v1",
        "allowed_model_ids": ["alpha"],
    }
    import hashlib

    body["review_map_fingerprint"] = "sha256:" + hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    path = tmp_path / "review-map.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(RuntimeError, match="root|work_id|observation"):
        _load_review_map(path, tmp_path)
