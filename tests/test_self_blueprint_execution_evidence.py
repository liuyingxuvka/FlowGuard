from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
import flowguard.model_regressions as model_regressions

from flowguard.model_regressions import (
    CurrentModelRegressionChildEvidence,
    CurrentModelRegressionParentEvidence,
    ModelRegressionEvidenceError,
    NATIVE_CASE_RESULT_ARTIFACT_NAME,
    build_model_regression_execution_evidence,
    parse_executed_case_ids,
)
from flowguard.native_case_protocol import (
    GOOD_DIMENSIONS,
    NATIVE_CASE_RESULT_SCHEMA,
    NativeModelCaseContract,
    NativeModelCaseResult,
)


def _fp(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _native_good_contract() -> NativeModelCaseContract:
    return NativeModelCaseContract(
        owner_id="model:alpha",
        source_case_id="case:good",
        case_kind="good",
        callable_ref="model.alpha.good",
        result_selector="report.case_results[case:good]",
        expected_status="pass",
        covered_dimensions=GOOD_DIMENSIONS,
        oracle_member_ids=tuple(f"oracle:{item}" for item in GOOD_DIMENSIONS),
        evidence_scope="model_policy",
        input_contract_fingerprint=_fp("input"),
        oracle_content_fingerprint=_fp("oracle"),
    )


def _native_good_result(contract: NativeModelCaseContract) -> NativeModelCaseResult:
    return NativeModelCaseResult(
        owner_id=contract.owner_id,
        source_case_id=contract.source_case_id,
        outcome=contract.expected_status,
        observed_status=contract.expected_status,
        executed_dimensions=contract.covered_dimensions,
        oracle_results=tuple(
            {
                "dimension": dimension,
                "oracle_member_id": f"oracle:{dimension}",
                "status": "pass",
                "ok": True,
            }
            for dimension in contract.covered_dimensions
        ),
        result_artifact_fingerprint=_fp("raw-result"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="raw.json",
    )


def _raw_rows(tmp_path: Path, count: int = 96):
    raw = tmp_path / "raw.json"
    raw.write_text("raw-result", encoding="utf-8")
    artifact = tmp_path / NATIVE_CASE_RESULT_ARTIFACT_NAME
    rows = tuple(
        replace(_native_good_result(_native_good_contract()), source_case_id=f"case:{index}")
        for index in range(count)
    )
    artifact.write_text(
        json.dumps({"schema_version": NATIVE_CASE_RESULT_SCHEMA, "results": [row.to_dict() for row in rows]}),
        encoding="utf-8",
    )
    return raw, artifact, rows


def _verify_rows(artifact: Path, rows):
    return model_regressions._verify_native_case_result_rows(
        owner_id="model:alpha",
        marker_case_ids=tuple(row.source_case_id for row in rows),
        rows=rows,
        artifact_path=artifact,
    )


def test_native_raw_hash_is_once_per_distinct_file_and_per_invocation(tmp_path: Path):
    raw, artifact, rows = _raw_rows(tmp_path)
    with patch.object(model_regressions, "_file_sha256", wraps=model_regressions._file_sha256) as digest:
        assert _verify_rows(artifact, rows).ok
        assert digest.call_count == 1
        second = tmp_path / "second.json"
        second.write_bytes(raw.read_bytes())
        assert _verify_rows(artifact, (*rows[:-1], replace(rows[-1], raw_artifact_path=second.name))).ok
        assert digest.call_count == 3
        raw.write_text("changed-result", encoding="utf-8")
        changed = _verify_rows(artifact, rows)
        assert not changed.ok
        assert digest.call_count == 4
        assert any("fingerprint_mismatch" in code for code in changed.findings)


def test_native_shared_hash_does_not_skip_later_declared_digest(tmp_path: Path):
    _raw, artifact, rows = _raw_rows(tmp_path, 2)
    bad = replace(rows[1], result_artifact_fingerprint=_fp("wrong-declaration"))
    result = _verify_rows(artifact, (rows[0], bad))
    assert not result.ok
    assert result.findings == ("native_result_raw_artifact_fingerprint_mismatch:model:alpha:case:1",)


def test_native_envelope_is_read_once_and_its_exact_bytes_are_hashed(tmp_path: Path):
    _raw, artifact, rows = _raw_rows(tmp_path, 2)
    expected = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    original = Path.read_bytes
    reads = []

    def read(path):
        reads.append(path)
        return original(path)

    with patch.object(Path, "read_bytes", read):
        loaded, _path, digest, verification = model_regressions._load_native_case_result_artifact(
            artifact, owner_id="model:alpha", marker_case_ids=tuple(row.source_case_id for row in rows)
        )
    assert loaded == rows
    assert verification.ok
    assert digest == expected
    assert reads.count(artifact.resolve()) == 1


@pytest.mark.parametrize("payload", [b"{broken", b"\xff"])
def test_native_unreadable_envelope_stays_blocked(tmp_path: Path, payload: bytes):
    artifact = tmp_path / NATIVE_CASE_RESULT_ARTIFACT_NAME
    artifact.write_bytes(payload)
    with pytest.raises(ModelRegressionEvidenceError, match="unreadable"):
        model_regressions._load_native_case_result_artifact(artifact, owner_id="model:alpha", marker_case_ids=("case:0",))


def test_native_raw_link_is_rejected_before_resolve(tmp_path: Path):
    raw, artifact, rows = _raw_rows(tmp_path, 1)
    original_link = Path.is_symlink
    original_resolve = Path.resolve
    resolved = []

    def resolve(path, *args, **kwargs):
        resolved.append(path)
        return original_resolve(path, *args, **kwargs)

    with patch.object(Path, "is_symlink", lambda path: path == raw or original_link(path)), patch.object(Path, "resolve", resolve):
        result = _verify_rows(artifact, rows)
    assert not result.ok
    assert raw not in resolved
    assert any("raw_artifact_invalid" in code for code in result.findings)


@pytest.mark.parametrize("change", ["missing", "escape", "foreign", "duplicate", "oracle"])
def test_native_optimized_verifier_preserves_negative_boundaries(tmp_path: Path, change: str):
    _raw, artifact, rows = _raw_rows(tmp_path, 2)
    if change == "missing":
        rows = (replace(rows[0], raw_artifact_path="absent.json"), rows[1])
    elif change == "escape":
        outside = tmp_path.parent / (tmp_path.name + "-outside.json")
        outside.write_text("raw-result", encoding="utf-8")
        rows = (replace(rows[0], raw_artifact_path=str(outside)), rows[1])
    elif change == "foreign":
        rows = (replace(rows[0], owner_id="model:foreign"), rows[1])
    elif change == "duplicate":
        rows = (rows[0], rows[0])
    else:
        rows = (replace(rows[0], oracle_results=()), rows[1])
    assert not _verify_rows(artifact, rows).ok


def _parent(*, executed_case_ids: tuple[str, ...] = ()) -> CurrentModelRegressionParentEvidence:
    return CurrentModelRegressionParentEvidence(
        manifest_fingerprint="sha256:manifest",
        parent_artifact_path="model-parent.json",
        parent_artifact_fingerprint="sha256:parent-artifact",
        parent_execution_receipt_id="receipt:validation-owner:model-regression-parent",
        parent_execution_receipt_fingerprint="sha256:parent-receipt",
        children=(
            CurrentModelRegressionChildEvidence(
                model_id="alpha",
                receipt_id="receipt:validation-owner:model:alpha",
                receipt_fingerprint="sha256:alpha-receipt",
                executed_case_ids=executed_case_ids,
            ),
        ),
    )


def test_native_case_projection_requires_one_explicit_marker() -> None:
    assert parse_executed_case_ids(
        "diagnostic\nFLOWGUARD_EXECUTED_CASE_IDS=[\"case:good\", \"case:boundary\"]\n"
    ) == ("case:good", "case:boundary")
    assert parse_executed_case_ids("diagnostic\n") == ()
    with pytest.raises(ModelRegressionEvidenceError, match="duplicate"):
        parse_executed_case_ids(
            "FLOWGUARD_EXECUTED_CASE_IDS=[\"case:good\"]\n"
            "FLOWGUARD_EXECUTED_CASE_IDS=[\"case:good\"]\n"
        )
    with pytest.raises(ModelRegressionEvidenceError, match="did not emit"):
        parse_executed_case_ids("diagnostic\n", require_marker=True)


def test_model_execution_package_does_not_forge_missing_or_parent_case_evidence() -> None:
    package = build_model_regression_execution_evidence(
        _parent(executed_case_ids=("case:good", "foreign:case")),
        required_case_ids_by_owner={
            "model:alpha": ("case:good", "case:boundary"),
        },
    )
    owner = package.owner("model:alpha")
    assert owner is not None
    assert owner.matches_case_id("case:good")
    assert not owner.matches_case_id("case:boundary")
    assert owner.missing_case_ids == ("case:boundary",)
    assert owner.foreign_case_ids == ("foreign:case",)
    assert package.status == "blocked"
    assert package.executed_case_count == 2


def test_parent_receipt_identity_is_never_accepted_as_a_leaf() -> None:
    parent = _parent()
    child = parent.children[0]
    forged = CurrentModelRegressionParentEvidence(
        manifest_fingerprint=parent.manifest_fingerprint,
        parent_artifact_path=parent.parent_artifact_path,
        parent_artifact_fingerprint=parent.parent_artifact_fingerprint,
        parent_execution_receipt_id=parent.parent_execution_receipt_id,
        parent_execution_receipt_fingerprint=parent.parent_execution_receipt_fingerprint,
        children=(
            CurrentModelRegressionChildEvidence(
                model_id=child.model_id,
                receipt_id=parent.parent_execution_receipt_id,
                receipt_fingerprint=parent.parent_execution_receipt_fingerprint,
            ),
        ),
    )
    package = build_model_regression_execution_evidence(
        forged,
        required_case_ids_by_owner={"model:alpha": ("case:good",)},
    )
    owner = package.owner("model:alpha")
    assert owner is not None
    assert "model_parent_receipt_used_as_leaf" in owner.finding_codes
    assert "model_parent_fingerprint_used_as_leaf" in owner.finding_codes
    assert not owner.complete


def test_empty_native_marker_cannot_pass_strict_owner() -> None:
    package = build_model_regression_execution_evidence(
        _parent(),
        required_case_ids_by_owner={"model:alpha": ("case:good",)},
        require_native_case_results=True,
    )
    owner = package.owner("model:alpha")
    assert owner is not None
    assert "native_case_results_missing" in owner.finding_codes
    assert "native_case_result_artifact_missing" in owner.finding_codes
    assert not owner.native_case_protocol_complete
    assert not owner.complete


def test_marker_only_reuse_is_blocked_by_strict_native_result_gate() -> None:
    package = build_model_regression_execution_evidence(
        _parent(executed_case_ids=("case:good",)),
        required_case_ids_by_owner={"model:alpha": ("case:good",)},
        require_native_case_results=True,
    )
    owner = package.owner("model:alpha")
    assert owner is not None
    assert "native_case_result_artifact_missing" in owner.finding_codes
    assert not owner.native_case_protocol_complete
    assert package.status == "blocked"


def test_native_source_id_maps_to_one_exact_blueprint_case(tmp_path) -> None:
    contract = _native_good_contract()
    result = _native_good_result(contract)
    raw_path = tmp_path / "raw.json"
    raw_path.write_text("raw-result", encoding="utf-8")
    envelope_path = tmp_path / NATIVE_CASE_RESULT_ARTIFACT_NAME
    envelope_path.write_text(
        json.dumps(
            {
                "schema_version": NATIVE_CASE_RESULT_SCHEMA,
                "results": [result.to_dict()],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    child = CurrentModelRegressionChildEvidence(
        model_id="alpha",
        receipt_id="receipt:validation-owner:model:alpha",
        receipt_fingerprint="sha256:alpha-receipt",
        executed_case_ids=("case:good",),
        native_case_results=(result,),
        native_case_result_artifact_path=str(envelope_path),
        native_case_result_artifact_fingerprint=_fp(
            envelope_path.read_text(encoding="utf-8")
        ),
    )
    parent = CurrentModelRegressionParentEvidence(
        manifest_fingerprint="sha256:manifest",
        parent_artifact_path="model-parent.json",
        parent_artifact_fingerprint="sha256:parent-artifact",
        parent_execution_receipt_id="receipt:validation-owner:model-regression-parent",
        parent_execution_receipt_fingerprint="sha256:parent-receipt",
        children=(child,),
    )
    package = build_model_regression_execution_evidence(
        parent,
        required_case_ids_by_owner={"model:alpha": ("case:good",)},
        native_case_contracts_by_owner={"model:alpha": (contract,)},
    )
    owner = package.owner("model:alpha")
    assert owner is not None
    assert owner.native_case_protocol_complete
    assert owner.native_case_verification is not None
    assert owner.native_case_verification.ok
    assert owner.native_case_results[0].source_case_id == "case:good"
    assert owner.missing_case_ids == ()
    assert owner.foreign_case_ids == ()


def test_malformed_native_result_envelope_blocks_owner(tmp_path) -> None:
    envelope_path = tmp_path / NATIVE_CASE_RESULT_ARTIFACT_NAME
    envelope_path.write_text(
        json.dumps({"schema_version": "obsolete", "results": []}),
        encoding="utf-8",
    )
    child = CurrentModelRegressionChildEvidence(
        model_id="alpha",
        receipt_id="receipt:validation-owner:model:alpha",
        receipt_fingerprint="sha256:alpha-receipt",
        executed_case_ids=("case:good",),
        native_case_result_artifact_path=str(envelope_path),
        native_case_result_artifact_fingerprint=_fp(
            envelope_path.read_text(encoding="utf-8")
        ),
    )
    parent = CurrentModelRegressionParentEvidence(
        manifest_fingerprint="sha256:manifest",
        parent_artifact_path="model-parent.json",
        parent_artifact_fingerprint="sha256:parent-artifact",
        parent_execution_receipt_id="receipt:validation-owner:model-regression-parent",
        parent_execution_receipt_fingerprint="sha256:parent-receipt",
        children=(child,),
    )
    package = build_model_regression_execution_evidence(
        parent,
        required_case_ids_by_owner={"model:alpha": ("case:good",)},
        require_native_case_results=True,
    )
    owner = package.owner("model:alpha")
    assert owner is not None
    assert "native_case_results_invalid" in owner.finding_codes
    assert not owner.complete
