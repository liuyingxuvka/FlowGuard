from __future__ import annotations

import hashlib
from dataclasses import replace
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
from flowguard.native_case_protocol import (
    NativeModelCaseResult, load_native_model_case_results, verify_native_case_bindings,
)


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

    declarations = json.loads((ROOT / ".flowguard/models/native-case-producer-overrides.json").read_text())
    actual = {(row.owner_id, row.blueprint_case_id): row for row in registry.bindings}
    assert len(actual) == len(registry.bindings)
    for declared in declarations["bindings"]:
        binding = actual[(declared["owner_id"], declared["blueprint_case_id"])]
        assert set(binding.native_case_ids) == set(declared["native_case_ids"])
        assert set(binding.protected_failure_ids) == set(declared["protected_failure_ids"])
        assert set(binding.expected_finding_codes) == set(declared["expected_finding_codes"])
    # Producer extensions declare new obligations independently of the
    # registry's incidental total; an omitted extension leaf must fail.
    for declaration in declarations["composite_owner_declarations"]:
        rows = registry.bindings_by_owner["model:" + declaration["model_id"]]
        actual_native_ids = {case for row in rows for case in row.native_case_ids}
        assert set(declaration["native_leaf_case_ids"]) <= actual_native_ids
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
    from tests.test_model_authority import detached_current_intent_view
    intent = detached_current_intent_view(candidate.fingerprint, "alpha")
    return fingerprint, candidate, intent


def test_path_quality_rejects_missing_native_artifact_before_graph_projection(tmp_path):
    fingerprint, candidate, intent = _path_quality_fixtures(tmp_path)
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

    with pytest.raises(ValueError, match="path-quality native result missing: alpha"):
        _native_path_quality_material(
            SimpleNamespace(results=(run,)),
            candidate,
            required_model_ids=("alpha",),
            currentness_id=fingerprint,
            effective_intent_view=intent,
        )


def test_synthetic_native_case_row_without_declaration_cannot_license_path_quality(tmp_path):
    fingerprint, candidate, intent = _path_quality_fixtures(tmp_path)
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

    with pytest.raises(ValueError, match="declared_source_missing:alpha"):
        _native_path_quality_material(
            SimpleNamespace(results=(run,)),
            candidate,
            required_model_ids=("alpha",),
            currentness_id=fingerprint,
            effective_intent_view=intent,
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


# These two tests execute only the named finite owner functions in temporary
# output roots. They do not qualify the repository54 inventory or launch a
# validation-owner/full process.
def _load_exact_native_owner_runner(monkeypatch, owner):
    import importlib.util
    import sys
    root = Path(__file__).resolve().parents[1]
    model_path = root / ".flowguard/models/owners" / owner / "model.py"
    model_spec = importlib.util.spec_from_file_location("model", model_path)
    model_module = importlib.util.module_from_spec(model_spec)
    monkeypatch.setitem(sys.modules, "model", model_module)
    model_spec.loader.exec_module(model_module)
    runner_path = root / ".flowguard/verification/owners" / owner / "run_checks.py"
    runner_spec = importlib.util.spec_from_file_location("finite_native_" + owner, runner_path)
    runner = importlib.util.module_from_spec(runner_spec)
    monkeypatch.setitem(sys.modules, runner_spec.name, runner)
    runner_spec.loader.exec_module(runner)
    return root, runner


def test_corpus_owner_captures_real_structured_review_once(tmp_path, monkeypatch, capsys):
    from flowguard.native_case_runner import native_main
    from flowguard.native_case_mapping import load_native_case_mapping
    root, runner = _load_exact_native_owner_runner(monkeypatch, "problem_corpus_coverage")
    calls = []
    actual_review = runner.run_review
    def counted_review():
        calls.append("actual-corpus")
        return actual_review()
    monkeypatch.setattr(runner, "run_review", counted_review)
    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWGUARD_PROJECT_ROOT", str(root))
    assert native_main("model:problem_corpus_coverage", runner.main) == 0
    capsys.readouterr()
    assert calls == ["actual-corpus"]
    raw = json.loads((tmp_path / "native-source.json").read_text())
    assert len(raw["structured_reports"]) == 1
    payload = json.loads((tmp_path / "native-case-results.json").read_text())
    rows = load_native_model_case_results(tmp_path / "native-case-results.json")
    bindings = load_native_case_mapping(root).bindings_by_owner["model:problem_corpus_coverage"]
    verified = verify_native_case_bindings(bindings, rows)
    assert verified.ok, verified.to_dict()
    leaves = {row.source_case_id: row for row in rows}
    assert leaves["case:problem_corpus_coverage:corpus_actual_baseline"].observed_status == "ok"
    for failure in runner.model.PROTECTED_FAILURES:
        row = leaves["case:problem_corpus_coverage:" + failure]
        assert row.observed_status == "blocked"
        assert failure in row.observed_finding_codes


def test_producer_counterexamples_keep_exact_protected_ids_and_missing_id_blocks(tmp_path, monkeypatch, capsys):
    from flowguard.native_case_runner import native_main
    from flowguard.native_case_mapping import load_native_case_mapping
    root, runner = _load_exact_native_owner_runner(monkeypatch, "development_process_flow")
    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWGUARD_PROJECT_ROOT", str(root))
    # Exercise actual finite scenarios, without the separate nested pytest
    # implementation producer owned by the model's complete native entry.
    def episode_only():
        return 0 if runner.run_producer_episode_model() else 1
    assert native_main("model:development_process_flow", episode_only) == 0
    capsys.readouterr()
    payload = json.loads((tmp_path / "native-case-results.json").read_text())
    wanted = {"case:development_process_flow:broken_producer_" + case_id: failure_id
              for case_id, failure_id, _sequence in runner.model.PRODUCER_FAILURE_CASES}
    rows = tuple(row for row in load_native_model_case_results(tmp_path / "native-case-results.json")
                 if row.source_case_id in wanted)
    assert len(rows) == len(wanted) == 8
    for row in rows:
        assert row.outcome == "pass" and row.observed_status == "violation"
        assert wanted[row.source_case_id] in row.observed_finding_codes
        assert "producer_exact_reservation_order_and_terminal" in row.observed_finding_codes
    bindings = tuple(binding for binding in load_native_case_mapping(root).bindings_by_owner[
        "model:development_process_flow"] if set(binding.native_case_ids) <= set(wanted))
    assert len(bindings) == 8
    verified = verify_native_case_bindings(bindings, rows)
    assert verified.ok, verified.to_dict()
    damaged = replace(rows[0], observed_finding_codes=tuple(
        code for code in rows[0].observed_finding_codes if code != wanted[rows[0].source_case_id]))
    rejected = verify_native_case_bindings(bindings, (damaged, *rows[1:]))
    assert not rejected.ok
    assert any(code.startswith("binding_protected_failure_missing:") for code in rejected.findings)
