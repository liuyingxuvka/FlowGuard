from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowguard.__main__ import (
    _native_path_quality_material,
    _release_direct_leaf_artifact_blockers,
    _release_leaf_blockers,
)
from flowguard.native_case_mapping import load_native_case_mapping
from flowguard.native_case_runner import native_main


ROOT = Path(__file__).resolve().parents[1]
STRICT_OWNERS = (
    "architecture_reduction",
    "hierarchical_model_mesh",
    "mesh_target_split_derivation",
    "structure_refactor_mesh",
    "test_evidence_mesh",
)


@pytest.mark.parametrize("value", [None, False, 0, "pass", []])
def test_non_structured_strict_native_return_is_rejected(tmp_path, monkeypatch, capsys, value):
    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))

    assert native_main("model:architecture_reduction", lambda: value) == 1

    captured = capsys.readouterr()
    assert "strict native producer rejected" in captured.err
    assert not (tmp_path / "native-case-results.json").exists()


def test_stdout_json_is_not_strict_native_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))

    def producer():
        print(json.dumps({"results": [{"name": "forged", "ok": True}]}))
        return []

    assert native_main("model:architecture_reduction", producer) == 1

    captured = capsys.readouterr()
    assert '"forged"' in captured.out
    assert "strict native producer rejected" in captured.err
    assert not (tmp_path / "native-case-results.json").exists()
    assert not (tmp_path / "native-source.json").exists()


def test_current_native_mapping_contains_all_override_bindings():
    registry = load_native_case_mapping(ROOT)

    assert len(registry.bindings) == 371
    assert ".flowguard/models/native-case-producer-overrides.json" in registry.source_paths
    for owner_id in STRICT_OWNERS:
        owner_rows = registry.bindings_by_owner[f"model:{owner_id}"]
        assert owner_rows
        assert any(row.case_kind == "boundary" for row in owner_rows)


def _path_quality_fixtures(tmp_path: Path):
    fingerprint = "sha256:" + "a" * 64
    instance = SimpleNamespace(
        logical_model_id="alpha",
        fingerprint=fingerprint,
        purpose_closure_fingerprint=fingerprint,
        runner_sha256=fingerprint,
        input_inventory_fingerprint=fingerprint,
        inputs=(),
    )
    candidate = SimpleNamespace(model_instances=(instance,), fingerprint=fingerprint)
    return fingerprint, candidate


def test_path_quality_rejects_missing_native_artifact_before_graph_projection(tmp_path):
    fingerprint, candidate = _path_quality_fixtures(tmp_path)
    row = SimpleNamespace(
        source_case_id="native-scenario:alpha:good",
        child_case_ids=(),
        result_artifact_fingerprint=fingerprint,
        oracle_results=(),
    )
    run = SimpleNamespace(
        model_id="alpha",
        ok=True,
        native_case_results=(row,),
        native_case_result_artifact_path="",
        native_case_result_artifact_fingerprint=fingerprint,
    )

    with pytest.raises(ValueError, match="native result artifact is missing"):
        _native_path_quality_material(
            SimpleNamespace(results=(run,)),
            candidate,
            required_model_ids=("alpha",),
            currentness_id=fingerprint,
        )


def test_synthetic_native_case_row_cannot_license_path_quality(tmp_path):
    fingerprint, candidate = _path_quality_fixtures(tmp_path)
    native_result_path = tmp_path / "native-case-results.json"
    native_result_path.write_text("{}", encoding="utf-8")
    source_path = tmp_path / "native-source.json"
    source_payload = {
        "report": {
            "results": [
                {
                    "scenario_name": "good",
                    "scenario_run": {"traces": [], "final_states": []},
                }
            ]
        }
    }
    source_path.write_text(json.dumps(source_payload), encoding="utf-8")
    source_fingerprint = "sha256:" + hashlib.sha256(source_path.read_bytes()).hexdigest()
    row = SimpleNamespace(
        source_case_id="native-scenario:alpha:good",
        child_case_ids=(),
        result_artifact_fingerprint=source_fingerprint,
        oracle_results=(),
    )
    run = SimpleNamespace(
        model_id="alpha",
        ok=True,
        native_case_results=(row,),
        native_case_result_artifact_path=str(native_result_path),
        native_case_result_artifact_fingerprint=(
            "sha256:" + hashlib.sha256(native_result_path.read_bytes()).hexdigest()
        ),
    )

    with pytest.raises(ValueError, match="no real executed graph"):
        _native_path_quality_material(
            SimpleNamespace(results=(run,)),
            candidate,
            required_model_ids=("alpha",),
            currentness_id=fingerprint,
        )


def test_release_leaf_gate_rejects_missing_completed_leaf():
    blockers = _release_leaf_blockers(
        SimpleNamespace(completed_evidence_refs=()),
        ("alpha",),
    )

    assert blockers == ("release.native_leaf_missing:model:alpha",)


def test_release_leaf_gate_rejects_required_pending_leaf():
    fingerprint = "sha256:" + "b" * 64
    leaf = SimpleNamespace(
        receipt_id="receipt:alpha",
        receipt_fingerprint=fingerprint,
        owner_route="model_test_alignment",
        covered_affected_ids=("model_instance:model:alpha",),
        status="required",
        current=True,
        eligible=True,
    )

    blockers = _release_leaf_blockers(
        SimpleNamespace(completed_evidence_refs=(leaf,)),
        ("alpha",),
    )

    assert blockers == ("release.native_leaf_not_current:model_instance:model:alpha",)


def _write_direct_release_proof(
    tmp_path: Path,
    *,
    model_result: dict[str, object] | None = None,
    evidence_context: dict[str, object] | None = None,
) -> tuple[SimpleNamespace, Path]:
    payload = {
        "schema_version": "flowguard.validation_owner_receipt.v2",
        "publication_kind": "supervised_producer",
        "owner_id": "model:alpha",
        "owner_identity": "sha256:" + "d" * 64,
        "child": {
            "child_id": "model:alpha",
            "status": "pass",
            "summary": "native alpha",
            "nested_receipt_id": "",
            "claim_boundary": "One native model owner.",
            "payload": {
                **({"model_result": model_result} if model_result is not None else {}),
                **({"evidence_context": evidence_context} if evidence_context is not None else {}),
            },
        },
    }
    proof_path = tmp_path / "proofs" / "direct.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    proof_path.write_bytes(proof_bytes)
    proof_fingerprint = "sha256:" + hashlib.sha256(proof_bytes).hexdigest()
    receipt = SimpleNamespace(
        fingerprint="sha256:" + "e" * 64,
        subject_id="validation-owner:model:alpha",
        subject_kind="validation_owner",
        producer_id="validation-owner:model:alpha",
        result_status="pass",
        exit_code=0,
        required_child_receipts=(),
        consumed_child_receipts=(),
        skipped_checks=(),
        blockers=(),
        metadata={
            "publication_kind": "supervised_producer",
            "proof_relpath": "proofs/direct.json",
        },
        proof_artifact_fingerprint=proof_fingerprint,
    )
    return receipt, proof_path


def test_release_direct_leaf_rejects_old_evidence_context_proof_shape(
    tmp_path: Path,
    monkeypatch,
):
    receipt, _proof_path = _write_direct_release_proof(
        tmp_path,
        evidence_context={
            "model_result": {
                "model_id": "alpha",
                "native_case_result_artifact_path": str(tmp_path / "native.json"),
                "native_case_result_artifact_fingerprint": "sha256:" + "a" * 64,
            }
        },
    )
    monkeypatch.setattr(
        "flowguard.evidence_receipts.load_evidence_receipt",
        lambda *args, **kwargs: receipt,
    )

    blockers = _release_direct_leaf_artifact_blockers(
        tmp_path,
        tmp_path,
        "receipt:alpha",
        receipt.fingerprint,
        model_id="alpha",
    )

    assert "release.native_leaf_model_result_missing:model:alpha" in blockers


def test_release_direct_leaf_rejects_missing_native_artifact(
    tmp_path: Path,
    monkeypatch,
):
    receipt, _proof_path = _write_direct_release_proof(
        tmp_path,
        model_result={
            "model_id": "alpha",
            "native_case_result_artifact_path": str(tmp_path / "missing-native.json"),
            "native_case_result_artifact_fingerprint": "sha256:" + "a" * 64,
        },
    )
    monkeypatch.setattr(
        "flowguard.evidence_receipts.load_evidence_receipt",
        lambda *args, **kwargs: receipt,
    )

    blockers = _release_direct_leaf_artifact_blockers(
        tmp_path,
        tmp_path,
        "receipt:alpha",
        receipt.fingerprint,
        model_id="alpha",
    )

    assert "release.native_leaf_native_artifact_missing:model:alpha" in blockers


def test_release_direct_leaf_rejects_native_artifact_hash_mismatch(
    tmp_path: Path,
    monkeypatch,
):
    native_path = tmp_path / "native.json"
    native_path.write_text("real native bytes", encoding="utf-8")
    receipt, _proof_path = _write_direct_release_proof(
        tmp_path,
        model_result={
            "model_id": "alpha",
            "native_case_result_artifact_path": str(native_path),
            "native_case_result_artifact_fingerprint": "sha256:" + "a" * 64,
        },
    )
    monkeypatch.setattr(
        "flowguard.evidence_receipts.load_evidence_receipt",
        lambda *args, **kwargs: receipt,
    )

    blockers = _release_direct_leaf_artifact_blockers(
        tmp_path,
        tmp_path,
        "receipt:alpha",
        receipt.fingerprint,
        model_id="alpha",
    )

    assert "release.native_leaf_native_artifact_hash_mismatch:model:alpha" in blockers
