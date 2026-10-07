"""Finite actual producer/acceptance tests; no maintained-source owners run."""

from pathlib import Path
import os
import time
import json
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("line_ending", ("\n", "\r\n", "\r"), ids=("LF", "CRLF", "CR"))
@pytest.mark.parametrize("changed", (False, True), ids=("current", "changed_timeout"))
def test_r8_native_mapping_manifest_uses_canonical_cached_source_identity(tmp_path, line_ending, changed):
    """Mapping identity normalizes newlines but retains all manifest fields."""
    from dataclasses import replace
    from types import SimpleNamespace
    from flowguard.native_case_runner import write_r8_finite_native_fixture
    from flowguard.native_case_mapping import NativeCaseMappingRegistry, compute_native_case_mapping_fingerprint
    from flowguard.source_identity import source_file_fingerprint, functional_source_fingerprint
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _finite_native_material
    write_r8_finite_native_fixture(tmp_path)  # Declarations only; no owner execution.
    manifest_path = tmp_path / ".flowguard/models/regression-manifest.json"
    mapping_path = tmp_path / ".flowguard/models/native-case-mapping.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    canonical_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    manifest_path.write_bytes(canonical_text.encode("utf-8"))
    old = NativeCaseMappingRegistry.from_payload(json.loads(mapping_path.read_text(encoding="utf-8")))
    declared = source_file_fingerprint(manifest_path)
    mapping_fp = compute_native_case_mapping_fingerprint(source_manifest_fingerprint=declared,
        source_paths=old.source_paths, bindings=old.bindings,
        diagnostic_native_case_ids=old.diagnostic_native_case_ids)
    registry = replace(old, source_manifest_fingerprint=declared, mapping_fingerprint=mapping_fp,
        bindings=tuple(replace(row, mapping_fingerprint=mapping_fp) for row in old.bindings))
    mapping_path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")
    functional_before = functional_source_fingerprint(tmp_path, ".flowguard/models/regression-manifest.json")
    if changed:
        payload["models"][0]["timeout_seconds"] += 1
        canonical_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    raw = canonical_text.replace("\n", line_ending).encode("utf-8")
    manifest_path.write_bytes(raw)
    assert functional_source_fingerprint(tmp_path, ".flowguard/models/regression-manifest.json") == functional_before
    assert (source_file_fingerprint(manifest_path) == declared) == (not changed)
    context = _SelectedReadContext(tmp_path)
    expected = "native mapping manifest is stale" if changed else "task has no original architecture native material"
    state = SimpleNamespace(snapshot=SimpleNamespace(model_instances=()))
    with patch("flowguard.validation_ownership._build_owner_current", side_effect=AssertionError("no native owner may run")), \
            pytest.raises(ValueError, match=expected):
        _finite_native_material(tmp_path, state, (), context)
    relative = manifest_path.relative_to(tmp_path).as_posix()
    assert context.payloads[relative] == raw
    assert context.read_counts[relative] == 1
    assert context.artifact_bytes(relative) == raw and context.read_counts[relative] == 1


@pytest.mark.parametrize("damage", ("", "missing_snapshot_model", "foreign_model_fingerprint", "missing_subject"))
def test_r8_path_quality_prerequisite_uses_exact_selected_model_scope(damage):
    """A wider accepted snapshot is allowed; selected missing/foreign proof is not."""
    from types import SimpleNamespace
    from dataclasses import replace
    from flowguard.functional_task_context import review_functional_task_prerequisites
    from flowguard.model_authority_store import SelectedModelClosureRead
    from flowguard.model_path_quality import lightweight_path_review
    from tests.test_model_path_quality import subject, clean_facts, fp
    selected = SelectedModelClosureRead("pass", "current", selected_model_ids=("alpha",))
    alpha = SimpleNamespace(logical_model_id="alpha", fingerprint=fp("alpha"))
    beta = SimpleNamespace(logical_model_id="beta", fingerprint=fp("unselected-beta"))
    owner = subject(model_id="alpha", model_fingerprint=alpha.fingerprint, currentness_id=fp("snapshot"))
    quality = lightweight_path_review(owner, clean_facts())
    models = (alpha, beta)
    if damage == "missing_snapshot_model": models = (beta,)
    elif damage == "foreign_model_fingerprint":
        models = (SimpleNamespace(logical_model_id="alpha", fingerprint=fp("foreign-alpha")), beta)
    state = SimpleNamespace(snapshot=SimpleNamespace(fingerprint=fp("snapshot"), model_instances=models),
        head=SimpleNamespace(fingerprint=fp("head")), accepted_revision=SimpleNamespace(current_effective_intent_view=None))
    binding_report = SimpleNamespace(required_model_element_ids=(), bindings=(), semantic_specs=(), oracles=(),
        fingerprint=fp("binding-report"), ok=True)
    material = {"implementation_inventory": object(), "binding_report": binding_report,
        "code_contracts": (), "native_contracts": (), "native_bindings": (), "native_results": (),
        "receipts": (), "receipt_contexts": {}, "raw_artifact_root": None,
        "current_native_identities": {}, "current_source_fingerprints": {}, "native_input_class_ids": {},
        "observed_source_inputs": (), "responsibility_evidence_bindings": {}, "owner_materials": {}}
    facts = SimpleNamespace(task_id="finite-selected-quality", fingerprint=fp("facts"))
    # Keep unrelated domain checks out of this quality-boundary test. The
    # quality reviewer itself remains the real strict production verifier.
    with patch("flowguard.implementation_blueprint.review_model_implementation_bindings", return_value=binding_report), \
            patch("flowguard.implementation_inventory.review_implementation_surface_inventory", return_value=SimpleNamespace(ok=True)), \
            patch("flowguard.model_maturation.review_functional_outcome_bindings", return_value={"ok": True, "gap_ids": []}):
        result = review_functional_task_prerequisites(state=state, facts=facts, selected_read=selected,
            subjects=() if damage == "missing_subject" else (owner,),
            results=() if damage == "missing_subject" else (quality,), details=(), material=material,
            outcome_refs=(), preflight=SimpleNamespace(selected_source_currentness="current", growth_gaps=()),
            preflight_report=SimpleNamespace(ok=True, findings=()))
    check = next(row for row in result["checks"] if row["check_id"] == "accepted_path_quality")
    assert check["ok"] == (not damage)
    expected = {"missing_snapshot_model": "path_quality_expected_model_fingerprint_missing",
        "foreign_model_fingerprint": "path_quality_subject_model_fingerprint_mismatch",
        "missing_subject": "path_quality_subject_missing"}
    if damage: assert expected[damage] in check["gap_ids"]
    else: assert not check["gap_ids"]
    assert "path_quality_expected_model_fingerprint_extra" not in check["gap_ids"]


@pytest.fixture(scope="module")
def functional_case(tmp_path_factory):
    from flowguard.native_case_runner import write_r8_finite_native_fixture
    from flowguard.model_regressions import run_manifest_regressions
    from flowguard.functional_task_context import (
        finite_current_design_contributions, prepare_finite_functional_authority,
        prepare_functional_task_request, produce_functional_task_context,
    )
    assert not os.environ.get("FLOWGUARD_R8_ORIGINAL_FINITE_ROOT"), (
        "functional tests must own a fresh module-scoped finite target; protected original reuse is forbidden")
    root = tmp_path_factory.mktemp("actual-functional")
    write_r8_finite_native_fixture(root)
    contributions = finite_current_design_contributions(root)
    parent = run_manifest_regressions(root, tier="full", jobs=1,
        output_dir=root / ".flowguard/work/original",
        receipt_dir=root / ".flowguard/evidence/model-owner-receipts",
        require_executed_case_ids=True)
    assert parent.status == "pass", parent.to_dict()
    state = prepare_finite_functional_authority(repository_root=root, parent=parent,
        current_design_contributions=contributions)
    for row in state.accepted_revision.path_quality_results:
        assert (root / ".flowguard/models/authority/path-quality-details" / (row.detail_evidence_fingerprint.removeprefix("sha256:") + ".json")).is_file()
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _finite_native_material
    from flowguard.model_regressions import resolve_current_full_model_regression_parent
    original = resolve_current_full_model_regression_parent(root,
        receipt_dir=root / ".flowguard/evidence/model-owner-receipts")
    material = _finite_native_material(root, state,
        [{"owner_id":"model:" + model, "receipt_id":leaf.receipt_id,
          "receipt_fingerprint":leaf.receipt_fingerprint}
         for model,leaf in original.child_evidence_by_model_id.items()], _SelectedReadContext(root))
    surfaces = material["implementation_inventory"].required_surface_ids
    outcomes = tuple(sorted({item for code in material["code_contracts"] for item in code.external_outputs}))
    assert len(outcomes) == 2 and all(item.startswith("outcome:r8:") for item in outcomes)
    request, output = prepare_functional_task_request(repository_root=root,
        task_id="finite-readonly-functional-" + str(time.monotonic_ns()), primary_model_id="alpha",
        task_purpose="Understand the independent integer classification functions after acceptance",
        requested_outcome_ids=outcomes,
        affected_surface_ids=surfaces, related_model_ids=("beta",))
    with patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("producer must consume original execution")):
        result = produce_functional_task_context(repository_root=root, request=request,
            output_directory=output, command="finite-test:normal-task-producer")
    (output / "actual-test-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return root, state, result


def test_r8_producer_publishes_real_task_context_without_native_reexecution(functional_case):
    root, state, result = functional_case
    assert result["status"] == "pass", result
    assert result["verification"]["ok"], result
    assert result["functional_understanding"]["stopping_disposition"] == "model_maturation_closed_for_task"
    assert (root / result["task_context_ref"]["path"]).is_file()


def test_r8_real_cli_publishes_tokenized_command_with_exact_argument_boundaries(functional_case):
    """The actual CLI publishes and independently verifies paths containing spaces."""
    import sys
    from dataclasses import replace
    from flowguard.__main__ import _read_operation
    from flowguard.evidence_receipts import (load_evidence_receipt, tokenize_command,
        ReceiptValidationError, _looks_absolute_path)
    from flowguard.functional_read import parse_task_facts, read_root_reference
    from flowguard.functional_task_context import prepare_functional_task_request, MATURATION_ROOT
    from flowguard.process_supervision import run_supervised
    root, _, original = functional_case
    assert original["status"] == "pass", original
    facts = parse_task_facts(read_root_reference(root, original["report_refs"]["facts"]))
    _, output = prepare_functional_task_request(repository_root=root,
        task_id="finite-cli space \u4e2d\u6587-" + str(time.monotonic_ns()), primary_model_id="alpha",
        task_purpose=facts.task_purpose, requested_outcome_ids=facts.requested_outcome_ids,
        affected_surface_ids=facts.affected_surface_ids, related_model_ids=("beta",))
    source = Path(__file__).resolve().parents[1]
    argv = [sys.executable, "-B", str(source / "scripts/produce_flowguard_task_context.py"),
        "--root", str(root), "--request", str(output / "producer-request.json"),
        "--output-dir", str(output), "--json"]
    environment = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1")
    actual = run_supervised(argv, cwd=source, environment=environment, timeout_seconds=90)
    assert actual.cleanup_confirmed and not actual.descendant_process_ids, actual.to_dict()
    assert actual.exit_code == 0, actual.to_dict()
    result = json.loads(actual.stdout)
    assert result["status"] == "pass" and result["verification"]["ok"], result
    freeze = json.loads((output / "producer-freeze.json").read_text(encoding="utf-8"))
    assert json.loads(freeze["command"]) == list(tokenize_command(argv,
        workspace_root=root, python_prefix=sys.prefix))
    assert len(json.loads(freeze["command"])) == len(argv)
    assert any(" " in arg and "\u4e2d\u6587" in arg for arg in json.loads(freeze["command"]))
    doc = read_root_reference(root, result["task_context_ref"])
    receipt = load_evidence_receipt(doc["maturation_receipt_ref"]["receipt_id"], root,
        output_directory=root / MATURATION_ROOT)
    assert receipt.command == (freeze["command"],)
    assert not _looks_absolute_path(json.dumps(receipt.to_dict()["metadata"], ensure_ascii=False))
    # The strict raw tuple gate is preserved; receipt construction cannot silently
    # tokenize an unverified caller-supplied tuple.
    with pytest.raises(ReceiptValidationError, match="untokenized absolute path"):
        replace(receipt, command=(" ".join(argv),))
    with patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read may not run native")), \
            patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read may not produce")):
        read = _read_operation(root, {"operation": "read", "target_id": "flowguard",
            "scope": ["alpha", "beta"], "task_context": result["task_context_ref"], "read_batch": True}, {})
    assert read["status"] == "pass", read
    assert read["pages"][0]["functional_understanding"]["stopping_disposition"] == "model_maturation_closed_for_task"
    assert read["producer_count"] == read["write_count"] == 0


def test_r8_real_maturation_inventory_order_preserves_exact_members(functional_case):
    """Publish and verify actual owner proofs in a valid non-SHA ordering."""
    from dataclasses import replace
    from flowguard import model_maturation
    from flowguard.functional_task_context import prepare_functional_task_request, produce_functional_task_context
    from flowguard.functional_read import read_root_reference, parse_task_facts
    root, _, original = functional_case
    assert original["status"] == "pass", original
    facts = parse_task_facts(read_root_reference(root, original["report_refs"]["facts"]))
    request, output = prepare_functional_task_request(repository_root=root,
        task_id="finite-owner-inventory-order-" + str(time.monotonic_ns()), primary_model_id="alpha",
        task_purpose=facts.task_purpose, requested_outcome_ids=facts.requested_outcome_ids,
        affected_surface_ids=facts.affected_surface_ids, related_model_ids=("beta",))
    compiler = model_maturation.compile_model_maturation_plan
    derive = model_maturation.derive_functional_understanding
    captured = {}
    def compile_reordered(intake):
        contributions = tuple(sorted(intake.contributions,
            key=lambda row:row.owner_resolution.resolution_fingerprint, reverse=True))
        return compiler(replace(intake, contributions=contributions))
    def capture_real_verification(**kwargs):
        captured.update(kwargs)
        return derive(**kwargs)
    with patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("native must not reexecute")), \
            patch.object(model_maturation, "compile_model_maturation_plan", compile_reordered), \
            patch.object(model_maturation, "derive_functional_understanding", capture_real_verification):
        result = produce_functional_task_context(repository_root=root, request=request,
            output_directory=output, command="finite-test:real-owner-inventory-order")
    (output / "actual-test-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert result["status"] == "pass", result
    report, verified = captured["maturation_report"], captured["verified_maturation"]
    assert len(report.owner_resolution_fingerprints) == 2
    assert report.owner_resolution_fingerprints != verified.owner_resolution_fingerprints
    assert tuple(sorted(report.owner_resolution_fingerprints)) == verified.owner_resolution_fingerprints
    for bad_fingerprints in (report.owner_resolution_fingerprints[:1],
            ("sha256:" + "0"*64, *report.owner_resolution_fingerprints[1:])):
        bad = dict(captured, maturation_report=replace(report, owner_resolution_fingerprints=bad_fingerprints))
        rejected = derive(**bad)
        assert rejected["stopping_disposition"] == "needs_evidence"
        assert "verified_maturation_current_receipt_missing_or_mismatched" in rejected["gap_ids"]


@pytest.mark.parametrize("mutation", ("none", "unmatched_output", "cross_owner_output",
    "wrong_binding", "wrong_native_binding", "missing_other_output", "obligation_selector"))
def test_r8_actual_external_output_mapping_cannot_borrow_foreign_proof(functional_case, mutation):
    from dataclasses import replace
    from flowguard.functional_task_context import _current_selected_state, _finite_native_material, _outcomes, _native_subset
    from flowguard.functional_read import read_root_reference, parse_task_facts
    from flowguard.model_maturation import review_functional_outcome_bindings
    from flowguard.model_authority_store import _SelectedReadContext
    root, _, produced = functional_case
    assert produced["status"] == "pass", produced
    facts = parse_task_facts(read_root_reference(root, produced["report_refs"]["facts"]))
    doc = read_root_reference(root, produced["task_context_ref"])
    context = _SelectedReadContext(root)
    state, selected, _, _, _ = _current_selected_state(root, "alpha", context, required_model_ids=("beta",))
    material = _finite_native_material(root, state, doc["native_owner_receipt_refs"], context)
    if mutation == "unmatched_output":
        facts = replace(facts, requested_outcome_ids=("outcome:r8:never_declared",), fact_observations=())
    elif mutation == "cross_owner_output":
        alpha = next(code for code in material["code_contracts"] if code.code_contract_id.endswith(":alpha"))
        beta = next(code for code in material["code_contracts"] if code.code_contract_id.endswith(":beta"))
        facts = replace(facts, requested_outcome_ids=alpha.external_outputs, fact_observations=())
        material = dict(material, code_contracts=tuple(
            replace(code, external_outputs=beta.external_outputs) if code == alpha else code
            for code in material["code_contracts"]))
    elif mutation == "obligation_selector":
        code = next(code for code in material["code_contracts"] if code.code_contract_id.endswith(":alpha"))
        facts = replace(facts, requested_outcome_ids=code.implements_obligations, fact_observations=())
    refs = _outcomes(facts, selected, state.accepted_revision.current_effective_intent_view, material)
    if mutation == "wrong_binding":
        refs[0] = {**refs[0], "binding_fingerprints":["sha256:"+"0"*64]}
    elif mutation == "wrong_native_binding":
        refs[0] = {**refs[0], "native_case_binding_fingerprints":["sha256:"+"0"*64]}
    elif mutation == "missing_other_output":
        refs = [row for row in refs if row["outcome_id"] == facts.requested_outcome_ids[0]]
    result = review_functional_outcome_bindings(task_facts=facts, selected_read=selected,
        current_effective_intent_view=state.accepted_revision.current_effective_intent_view,
        binding_report=material["binding_report"], implementation_inventory=material["implementation_inventory"],
        outcome_refs=refs, native_materials=_native_subset(material))
    assert result["ok"] == (mutation in {"none", "obligation_selector"}), result
    if mutation == "none":
        assert len(refs) == 2
        assert all(row["outcome_id"].startswith("outcome:r8:") and row["target_id"].startswith("obligation:") for row in refs)
    elif mutation not in {"none", "obligation_selector"}:
        assert result["missing_outcome_ids"]

def _r9_prepare_task(functional_case, *, changes=(), requested_outcome_ids=None):
    from flowguard.functional_read import read_root_reference, parse_task_facts
    from flowguard.functional_task_context import prepare_functional_task_request
    root, _, original = functional_case
    assert original["status"] == "pass", original
    facts = parse_task_facts(read_root_reference(root, original["report_refs"]["facts"]))
    return prepare_functional_task_request(repository_root=root,
        task_id="r9-normal-" + str(time.monotonic_ns()), primary_model_id="alpha",
        task_purpose=facts.task_purpose,
        requested_outcome_ids=facts.requested_outcome_ids if requested_outcome_ids is None else requested_outcome_ids,
        affected_surface_ids=facts.affected_surface_ids, related_model_ids=("beta",),
        observed_path_changes=changes)


def _r9_run_task_cli(root, output):
    import sys
    from flowguard.process_supervision import run_supervised
    source = Path(__file__).resolve().parents[1]
    before = {path.relative_to(root).as_posix(): path.read_bytes()
              for parent in ("model-owner-receipts", "skill-native-receipts")
              for path in (root / ".flowguard/evidence" / parent).rglob("*.json")}
    authority_before = (root / ".flowguard/project.toml").read_bytes()
    actual = run_supervised([sys.executable, "-B", str(source / "scripts/produce_flowguard_task_context.py"),
        "--root", str(root), "--request", str(output / "producer-request.json"),
        "--output-dir", str(output), "--json"], cwd=source,
        environment=dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1"),
        timeout_seconds=90)
    assert actual.cleanup_confirmed and not actual.descendant_process_ids, actual.to_dict()
    assert actual.exit_code in (0, 2), actual.to_dict()
    result = json.loads(actual.stdout)
    (output / "actual-cli-invocation.json").write_text(
        json.dumps(actual.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "actual-cli-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"] == "blocked":
        after = {path.relative_to(root).as_posix(): path.read_bytes()
                 for parent in ("model-owner-receipts", "skill-native-receipts")
                 for path in (root / ".flowguard/evidence" / parent).rglob("*.json")}
        assert before == after, "blocked normal production must publish no native/maturation receipt"
    assert (root / ".flowguard/project.toml").read_bytes() == authority_before, "normal producer must not CAS"
    return result


def test_r9_preflight_block_publishes_original_diagnostic_context_without_receipt(functional_case, request):
    from flowguard.functional_read import read_root_reference
    from flowguard.__main__ import _read_operation
    root, _, _ = functional_case
    _, output = _r9_prepare_task(functional_case)
    # The real preflight requires a canonical ledger once this explicit plane
    # exists. Its genuinely missing input is not a fabricated blocker boolean.
    ledger_dir = root / ".flowguard/behavior/inventory"
    original_directories = {path: path.exists() for path in (ledger_dir, ledger_dir.parent)}
    ledger_file = ledger_dir / "ledger.json"
    original_ledger = ledger_file.read_bytes() if ledger_file.is_file() else None
    ledger_dir.mkdir(parents=True, exist_ok=True)
    if original_ledger is not None:
        ledger_file.unlink()
    def restore_ledger_directory():
        if original_ledger is not None:
            ledger_file.write_bytes(original_ledger)
        if not original_directories[ledger_dir]:
            ledger_dir.rmdir()
        if not original_directories[ledger_dir.parent] and not list(ledger_dir.parent.iterdir()):
            ledger_dir.parent.rmdir()
    request.addfinalizer(restore_ledger_directory)
    result = _r9_run_task_cli(root, output)
    assert result["status"] == "blocked" and result.get("task_context_ref"), result
    doc = read_root_reference(root, result["task_context_ref"])
    diagnostic = read_root_reference(root, doc["diagnostic_ref"])
    original = read_root_reference(root, diagnostic["preflight_report_ref"])
    blocker = next(row for row in original["report"]["findings"] if row["severity"] == "blocker")
    assert diagnostic["first_gap"] == {"gap_id": blocker["code"],
        "input_ref": diagnostic["preflight_report_ref"]["path"],
        "next_owner_id": "existing-model-owner", "reason": blocker["message"]}
    assert doc["context_kind"] == "diagnostic" and doc["maturation_receipt_ref"] is None
    assert diagnostic["status"] == "needs_evidence" and diagnostic["claim_boundary"] == "diagnostic_observation_only"
    with patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read may not produce")), \
            patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read may not execute")):
        read = _read_operation(root, {"operation": "read", "target_id": "flowguard", "scope": ["alpha", "beta"],
            "task_context": result["task_context_ref"], "read_batch": True}, {})
    assert read["status"] == "pass", read
    assert read["pages"][0]["functional_understanding"]["first_gap"] == diagnostic["first_gap"]
    assert read["producer_count"] == read["write_count"] == 0


@pytest.mark.parametrize("change", ("add", "delete", "rename", "unknown_neighbor"))
def test_r9_normal_growth_cli_preserves_new_deleted_renamed_and_unknown_neighbor(functional_case, change, request):
    from flowguard.functional_read import read_root_reference, functional_task_growth_reference
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.__main__ import _read_operation
    root, _, _ = functional_case
    path = "src/neighbor.py" if change == "unknown_neighbor" else "src/w3.py" if change == "add" else "src/alpha_renamed.py" if change == "rename" else "src/alpha.py"
    saved = {item:(root / item).read_bytes() if (root / item).is_file() else None for item in {"src/alpha.py", path}}
    def restore_finite_paths():
        for item, raw in saved.items():
            target = root / item
            if raw is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(raw)
    request.addfinalizer(restore_finite_paths)
    declaration = {"kind": "add" if change == "unknown_neighbor" else change,
                   "path": path, "previous_path": "src/alpha.py" if change == "rename" else ""}
    _, output = _r9_prepare_task(functional_case, changes=[declaration])
    assert not (output / "inputs/growth-observation.json").exists(), "prepare is declarations only"
    if change in {"add", "unknown_neighbor"}:
        (root / path).write_text("def independently_added():\n    return 3\n", encoding="utf-8")
    elif change == "delete":
        (root / path).unlink()
    else:
        (root / "src/alpha.py").rename(root / path)
    result = _r9_run_task_cli(root, output)
    assert result["status"] == "blocked" and result.get("task_context_ref"), result
    context = _SelectedReadContext(root)
    growth_ref = functional_task_growth_reference(repository_root=root,
        task_context_ref=result["task_context_ref"], read_context=context)
    observation = read_root_reference(root, growth_ref, context)
    assert observation["source_kind"] == "explicit_task_paths"
    assert observation["declared_path_changes"] == [declaration]
    expected_paths = sorted({"src/alpha.py", path}) if change == "rename" else [path]
    assert [row["path"] for row in observation["observations"]] == expected_paths
    assert {row["path"]: row["state"] for row in observation["observations"]} == {
        observed_path: "missing" if observed_path == "src/alpha.py" and change in {"delete", "rename"} else "present"
        for observed_path in expected_paths}
    doc = read_root_reference(root, result["task_context_ref"], context)
    diagnostic = read_root_reference(root, doc["diagnostic_ref"], context)
    report = read_root_reference(root, diagnostic["growth_report_ref"], context)
    assert {row["gap_id"] for row in report["growth_gaps"]} == {"model_growth_unbound:" + item for item in expected_paths}
    for row in report["growth_gaps"]:
        if row["path"] == "src/alpha.py":
            assert "current_inventory" in row["required_input_refs"]
            assert "current_implementation_binding" in row["required_input_refs"]
        else:
            assert row["next_owner_id"] == ""
            assert row["required_input_refs"] == ["boundary_admission_required:" + row["path"]]
    with patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read may not produce")):
        read = _read_operation(root, {"operation": "read", "target_id": "flowguard", "scope": ["alpha", "beta"],
            "task_context": result["task_context_ref"], "read_batch": True}, {})
    assert read["status"] == "pass", read
    assert read["pages"][0]["functional_understanding"]["first_gap"] == diagnostic["first_gap"]
    assert [row for page in read["pages"] for row in page["growth_gaps"]] == report["growth_gaps"]
    assert [item for page in read["pages"] for item in page["checked_observed_paths"]] == expected_paths
    assert all(page["live_unregistered_file_detection"] == "FINITE_OBSERVATION" for page in read["pages"])


def _r9_read_context(root):
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _current_selected_state
    context = _SelectedReadContext(root)
    state, selected, *_ = _current_selected_state(root, "alpha", context)
    return context, state, selected


def _r9_restore_bytes(request, path):
    original = path.read_bytes()
    request.addfinalizer(lambda: path.write_bytes(original))
    return original


def test_r9_e03_03_new_test_instrument_all_actual_reads_each_path_initial_once_and_endguard_once(functional_case):
    from collections import Counter
    import flowguard.model_authority_store as store
    from flowguard.functional_task_context import _current_selected_state, _selected_native_leaf_refs, _finite_native_material
    root, _, _ = functional_case
    accounting = store.ReadAccounting()
    context = store._SelectedReadContext(root, accounting=accounting)
    physical = []
    unshared_text_reads = []
    original = Path.read_bytes
    original_text = Path.read_text
    def read_bytes(path):
        raw = original(path)
        if path.absolute().is_relative_to(root):
            physical.append((path.absolute().relative_to(root).as_posix(), len(raw)))
        return raw
    def read_text(path, *args, **kwargs):
        if path.absolute().is_relative_to(root):
            unshared_text_reads.append(path.absolute().relative_to(root).as_posix())
        return original_text(path, *args, **kwargs)
    # Test-local instrumentation detects both shared and accidentally retained
    # direct readers. Production has no global Path patch or cache.
    with patch.object(Path, "read_bytes", new=read_bytes), patch.object(Path, "read_text", new=read_text):
        state, selected, *_ = _current_selected_state(root, "alpha", context)
        refs = _selected_native_leaf_refs(root, state, tuple(selected.selected_model_ids), read_context=context)
        _finite_native_material(root, state, refs, context)
        # A repeated consumer must reuse every original byte without changing
        # the full typed authority or re-running any native producer.
        _current_selected_state(root, "alpha", context, selected)
        _finite_native_material(root, state, refs, context)
        guard = store.verify_selected_read_observation(store.freeze_selected_read_observation(context), accounting=accounting)
    assert guard.ok, guard.to_dict()
    assert not unshared_text_reads, unshared_text_reads
    assert Counter(physical) == Counter((path, size) for path, _, size in accounting.calls)
    assert Counter(path for path, phase, _ in accounting.calls if phase == "initial") == Counter({path: 1 for path in context.payloads})
    assert Counter(path for path, phase, _ in accounting.calls if phase == "endguard") == Counter({path: 1 for path in context.payloads})
    assert not any(phase == "legacy_unshared" for _, phase, _ in accounting.calls)


@pytest.mark.parametrize("damage", ("receipt", "proof", "native", "foreign_root", "bad_sha"))
def test_r9_e03_04_new_test_cached_native_receipt_bytes_still_reject_tamper_store_foreign_root_ba(functional_case, tmp_path, request, damage):
    from flowguard.functional_task_context import _selected_native_leaf_refs, _finite_native_material
    from flowguard.evidence_receipts import receipt_path, load_evidence_receipt, ReceiptValidationError
    from flowguard.functional_read import read_root_reference
    from flowguard.validation_ownership import _proof_path
    root, _, _ = functional_case
    context, state, selected = _r9_read_context(root)
    refs = _selected_native_leaf_refs(root, state, tuple(selected.selected_model_ids), read_context=context)
    ref = refs[0]
    path = receipt_path(ref["receipt_id"], root, output_directory=root / ".flowguard/evidence/model-owner-receipts")
    receipt = load_evidence_receipt(path, read_context=context)
    if damage == "foreign_root":
        from flowguard.model_authority_store import _SelectedReadContext
        with pytest.raises(ReceiptValidationError):
            load_evidence_receipt(path, read_context=_SelectedReadContext(tmp_path))
        return
    if damage == "bad_sha":
        with pytest.raises(ValueError, match="raw fingerprint changed"):
            read_root_reference(root, {"path": path.relative_to(root).as_posix(), "sha256": "0" * 64}, context)
        return
    if damage != "receipt":
        path = _proof_path(root / ".flowguard/evidence/model-owner-receipts", receipt)
        if damage == "native":
            proof = json.loads(path.read_bytes())
            path = Path(proof["child"]["payload"]["model_result"]["native_case_result_artifact_path"])
            if not path.is_absolute():
                path = root / path
    original = _r9_restore_bytes(request, path)
    if damage == "receipt":
        # Exact cached original receipt bytes remain stable within invocation,
        # but the independent guard must catch even JSON-whitespace drift.
        path.write_bytes(original + b"\n")
        from flowguard.model_authority_store import freeze_selected_read_observation, verify_selected_read_observation
        assert load_evidence_receipt(path, read_context=context) == receipt
        assert not verify_selected_read_observation(freeze_selected_read_observation(context)).ok
    else:
        path.write_bytes(b"{}\n")
        with pytest.raises((ValueError, KeyError, TypeError)):
            _finite_native_material(root, state, refs, context)


def test_r9_e03_05_new_test_selected_second_invocation_performs_its_own_current_validation(functional_case, request):
    from flowguard.functional_task_context import _selected_native_leaf_refs, _finite_native_material
    root, _, _ = functional_case
    context, state, selected = _r9_read_context(root)
    refs = _selected_native_leaf_refs(root, state, tuple(selected.selected_model_ids), read_context=context)
    _finite_native_material(root, state, refs, context)
    source = root / "src/alpha.py"
    raw = _r9_restore_bytes(request, source)
    source.write_bytes(raw + b"\n# second invocation must see actual current bytes\n")
    new_context, new_state, new_selected = _r9_read_context(root)
    new_refs = _selected_native_leaf_refs(root, new_state, tuple(new_selected.selected_model_ids), read_context=new_context)
    with pytest.raises(ValueError, match="changed|stale|current"):
        _finite_native_material(root, new_state, new_refs, new_context)
    assert new_context is not context and new_state is not state


def test_r9_e03_06_new_test_cached_state_retains_all54_full_typed_members_and_original_snapshot_f(functional_case, tmp_path):
    from tests.test_model_intent_authority import _snapshot
    from flowguard.model_authority import ModelSystemSnapshot
    from flowguard.model_authority_store import _SelectedReadContext, _write_immutable_json, load_current_model_authority_state
    # Authenticate a complete 54-member typed snapshot through the real raw
    # content-addressed parser; no selected snapshot or copied full FP is made.
    complete = _snapshot(tuple("model%02d" % number for number in range(54)))
    _write_immutable_json(tmp_path, "snapshots", complete.fingerprint, complete.to_dict())
    full_context = _SelectedReadContext(tmp_path)
    parsed = full_context.typed_artifact("snapshots", complete.fingerprint, ModelSystemSnapshot.from_dict)
    assert len(parsed.model_instances) == 54 and parsed == complete
    assert parsed.fingerprint == complete.fingerprint
    assert full_context.typed_artifact("snapshots", complete.fingerprint, ModelSystemSnapshot.from_dict) is parsed
    # The independently accepted two-function fixture additionally checks the
    # entire real revision/activation/boundary state is retained in its cache.
    root, original, _ = functional_case
    context, state, selected = _r9_read_context(root)
    again = load_current_model_authority_state(root, read_context=context)
    assert again is state and state.snapshot == original.snapshot
    assert state.snapshot.fingerprint == original.snapshot.fingerprint
    assert state.accepted_revision == original.accepted_revision
    assert len(state.snapshot.model_instances) >= len(selected.selected_model_ids)


def test_r9_e03_07_new_test_malformed_unselected_typed_member_still_rejected_by_full_authority_va(functional_case, request):
    from flowguard.model_authority_store import _SelectedReadContext, load_current_model_authority_state
    root, state, _ = functional_case
    path = root / ".flowguard/models/authority/snapshots" / (state.snapshot.fingerprint.removeprefix("sha256:") + ".json")
    raw = _r9_restore_bytes(request, path)
    payload = json.loads(raw)
    victim = next(row for row in payload["model_instances"] if row["logical_model_id"] == "beta")
    victim["model_path"] = "../foreign.py"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_current_model_authority_state(root, read_context=_SelectedReadContext(root))


def test_r9_e03_08_new_test_same_head_with_changed_content_addressed_revision_raw_bytes_blocked(functional_case, request):
    from flowguard.model_authority_store import freeze_selected_read_observation, verify_selected_read_observation
    root, _, _ = functional_case
    context, state, _ = _r9_read_context(root)
    before = freeze_selected_read_observation(context)
    path = root / ".flowguard/models/authority/revisions" / (state.head.accepted_revision_set_fingerprint.removeprefix("sha256:") + ".json")
    original = _r9_restore_bytes(request, path)
    path.write_bytes(original + b"\n")
    guard = verify_selected_read_observation(before)
    assert not guard.ok
    assert {row["path"] for row in guard.findings if row["code"] == "selected_read_raw_input_drift"} == {path.relative_to(root).as_posix()}


def test_r9_e03_09_new_test_allow_legacy_bootstrap_source_reverify_options_cannot_share_cached_re(functional_case):
    from flowguard.model_authority_store import _SelectedReadContext, load_current_model_authority_state
    root, _, _ = functional_case
    context = _SelectedReadContext(root)
    states = {}
    for allow in (False, True):
        for reverify in (False, True):
            value = load_current_model_authority_state(root, read_context=context,
                allow_legacy_bootstrap_source=allow, reverify_current_sources=reverify)
            states[(allow, reverify)] = value
            assert value.current_sources_reverified is reverify
            assert load_current_model_authority_state(root, read_context=context,
                allow_legacy_bootstrap_source=allow, reverify_current_sources=reverify) is value
    assert len(context.authority_states) == 4
    assert len({id(value) for value in states.values()}) == 4


@pytest.mark.parametrize("damage", ("root", "head", "snapshot", "half_head", "half_snapshot", "bound_head"))
def test_r9_e03_10_new_test_wrong_root_bound_head_snapshot_or_half_supplied_pair_rejected_before_(functional_case, tmp_path, damage):
    from dataclasses import replace
    from flowguard.model_authority_store import load_current_model_authority_state
    root, _, _ = functional_case
    context, state, _ = _r9_read_context(root)
    kwargs = {"head": state.head, "snapshot": state.snapshot}
    actual_root = root
    if damage == "root":
        actual_root = tmp_path
    elif damage == "head":
        kwargs["head"] = replace(state.head, generation=state.head.generation + 1)
    elif damage == "snapshot":
        kwargs["snapshot"] = replace(state.snapshot, snapshot_id="foreign-snapshot")
    elif damage == "half_head":
        kwargs.pop("snapshot")
    elif damage == "half_snapshot":
        kwargs.pop("head")
    else:
        context.authority_section = {**context.authority_section, "generation": state.head.generation + 1}
    with pytest.raises(ValueError):
        load_current_model_authority_state(actual_root, read_context=context, **kwargs)


def _r9_complete_parent_index(tmp_path):
    """Synthetic immutable index only, never native/current leaf evidence."""
    from types import SimpleNamespace
    from flowguard.native_case_runner import write_r8_finite_native_fixture
    from tests.test_model_intent_authority import _snapshot
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.model_regressions import (MODEL_REGRESSION_PARENT_ARTIFACT_TYPE,
        MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA, MODEL_REGRESSION_PARENT_CURRENT_SCHEMA)
    from flowguard.evidence_receipts import fingerprint_value
    write_r8_finite_native_fixture(tmp_path)
    path = tmp_path / ".flowguard/models/regression-manifest.json"
    doc = json.loads(path.read_bytes())
    model_ids = tuple("model%02d" % number for number in range(54))
    original = doc["models"][0]
    doc["models"] = [{**original, "model_id": model, "model_path": ".flowguard/" + model + "/model.py"} for model in model_ids]
    doc["shared_input_groups"] = []
    path.write_text(json.dumps(doc), encoding="utf-8")
    context = _SelectedReadContext(tmp_path)
    fp = lambda value: fingerprint_value(value)
    parent = {"artifact_type": MODEL_REGRESSION_PARENT_ARTIFACT_TYPE,
        "schema_version": MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA, "claim_scope": "full", "tier": "full", "status": "pass",
        "manifest_sha256": context.functional_fingerprint(path.relative_to(tmp_path).as_posix()),
        "selected_model_ids": list(model_ids), "skipped_model_ids": [],
        "children": [{"model_id": model, "receipt_id": "index-only:" + model, "receipt_fingerprint": fp(model)} for model in model_ids],
        "execution_receipt_id": "index-only:parent", "execution_receipt_fingerprint": fp("parent"),
        "claim_boundary": "Synthetic index table shape only; no native currentness claim"}
    directory = tmp_path / ".flowguard/evidence/model-owner-receipts/model-parents"
    directory.mkdir(parents=True, exist_ok=True)
    def publish(value):
        value = {key: item for key, item in value.items() if key != "parent_receipt_fingerprint"}
        value["parent_receipt_fingerprint"] = fp(value)
        path = directory / (value["parent_receipt_fingerprint"].removeprefix("sha256:") + ".json")
        path.write_text(json.dumps(value), encoding="utf-8")
        (directory / "CURRENT.json").write_text(json.dumps({"artifact_type": MODEL_REGRESSION_PARENT_ARTIFACT_TYPE,
            "schema_version": MODEL_REGRESSION_PARENT_CURRENT_SCHEMA,
            "parent_receipt_fingerprint": value["parent_receipt_fingerprint"]}), encoding="utf-8")
        return path
    parent_path = publish(parent)
    return SimpleNamespace(snapshot=_snapshot(model_ids)), parent, parent_path, publish


def test_r9_e04_01_new_test_selected_index_chosen2_from_complete54_produces_exact3field_refs(tmp_path):
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _selected_native_leaf_refs
    state, _, _, _ = _r9_complete_parent_index(tmp_path)
    context = _SelectedReadContext(tmp_path)
    refs = _selected_native_leaf_refs(tmp_path, state, ("model01", "model00"), read_context=context)
    assert [ref["owner_id"] for ref in refs] == ["model:model00", "model:model01"]
    assert all(set(ref) == {"owner_id", "receipt_id", "receipt_fingerprint"} for ref in refs)
    assert len(state.snapshot.model_instances) == 54
    assert not any(path.endswith(".py") for path in context.payloads)


@pytest.mark.parametrize("damage", ("missing", "duplicate", "duplicate_selected", "parent_as_leaf", "foreign_receipt"))
def test_r9_e04_02_new_test_selected_missing_duplicate_parent_as_leaf_foreign_receipt_rejected(functional_case, tmp_path, damage):
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _selected_native_leaf_refs, _finite_native_material
    state, parent, _, publish = _r9_complete_parent_index(tmp_path)
    chosen = ("model00", "model01")
    if damage == "missing":
        parent["children"].pop(0)
    elif damage == "duplicate":
        parent["children"][1]["receipt_id"] = parent["children"][0]["receipt_id"]
    elif damage == "duplicate_selected":
        chosen = ("model00", "model00")
    elif damage == "parent_as_leaf":
        parent["children"][0]["receipt_id"] = parent["execution_receipt_id"]
    else:
        root, _, _ = functional_case
        context, actual_state, _ = _r9_read_context(root)
        refs = _selected_native_leaf_refs(root, actual_state, ("alpha", "beta"), read_context=context)
        foreign = [{**refs[0], "owner_id": "model:beta"}]
        with pytest.raises(ValueError, match="canonical receipt"):
            _finite_native_material(root, actual_state, foreign, context)
        return
    publish(parent)
    with pytest.raises(ValueError):
        _selected_native_leaf_refs(tmp_path, state, chosen, read_context=_SelectedReadContext(tmp_path))


@pytest.mark.parametrize("damage", ("tamper", "manifest", "unknown"))
def test_r9_e04_03_new_test_parent_table_tamper_manifest_mismatch_unknown_selected_id_rejected(tmp_path, damage):
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _selected_native_leaf_refs
    state, parent, path, publish = _r9_complete_parent_index(tmp_path)
    chosen = ("model00", "model01")
    if damage == "tamper":
        value = json.loads(path.read_bytes())
        value["children"][0]["receipt_id"] += ":tampered"
        path.write_text(json.dumps(value), encoding="utf-8")
    elif damage == "manifest":
        parent["manifest_sha256"] = "sha256:" + "0" * 64
        publish(parent)
    else:
        chosen = ("foreign",)
    with pytest.raises(ValueError):
        _selected_native_leaf_refs(tmp_path, state, chosen, read_context=_SelectedReadContext(tmp_path))


@pytest.mark.parametrize("damage", ("source", "proof", "native_mapping"))
def test_r9_e04_04_new_test_selected_finite_native_material_current_source_proof_native_mapping_f(functional_case, request, damage):
    from flowguard.functional_task_context import _selected_native_leaf_refs, _finite_native_material
    from flowguard.evidence_receipts import load_evidence_receipt
    from flowguard.validation_ownership import _proof_path
    root, _, _ = functional_case
    context, state, _ = _r9_read_context(root)
    refs = _selected_native_leaf_refs(root, state, ("alpha",), read_context=context)
    if damage == "source":
        path = root / "src/alpha.py"
    elif damage == "proof":
        receipt = load_evidence_receipt(refs[0]["receipt_id"], root, output_directory=root / ".flowguard/evidence/model-owner-receipts")
        path = _proof_path(root / ".flowguard/evidence/model-owner-receipts", receipt)
    else:
        path = root / ".flowguard/models/native-case-mapping.json"
    raw = _r9_restore_bytes(request, path)
    path.write_bytes(raw + b"\n# changed\n" if damage == "source" else b"{}\n")
    from flowguard.model_authority_store import _SelectedReadContext
    with pytest.raises((ValueError, KeyError, TypeError)):
        _finite_native_material(root, state, refs, _SelectedReadContext(root))


def test_r9_e04_05_new_test_unselected_source_not_reread_but_no_global_current_claim(functional_case, request):
    from flowguard.functional_task_context import _selected_native_leaf_refs, _finite_native_material
    root, _, _ = functional_case
    path = root / "src/beta.py"
    raw = _r9_restore_bytes(request, path)
    path.write_bytes(raw + b"\n# unrelated owner currentness deliberately not observed\n")
    context, state, _ = _r9_read_context(root)
    refs = _selected_native_leaf_refs(root, state, ("alpha",), read_context=context)
    material = _finite_native_material(root, state, refs, context)
    assert set(material["owner_materials"]) == {"model:alpha"}
    assert "src/beta.py" not in context.payloads
    assert all(set(ref) == {"owner_id", "receipt_id", "receipt_fingerprint"} for ref in refs)
    assert len(state.snapshot.model_instances) == 2


@pytest.mark.parametrize("damage", ("unselected_source", "parent_only_input"))
def test_r9_e04_06_new_test_full_resolver_still_rejects_stale_unselected_leaf_and_parent_only_inp(functional_case, request, damage):
    from flowguard.model_regressions import resolve_current_full_model_regression_parent
    root, _, _ = functional_case
    path = root / ("src/beta.py" if damage == "unselected_source" else ".flowguard/models/regression-manifest.json")
    raw = _r9_restore_bytes(request, path)
    if damage == "unselected_source":
        path.write_bytes(raw + b"\n# full consumer must reject stale unrelated leaf\n")
    else:
        doc = json.loads(raw)
        doc["models"][0]["timeout_seconds"] += 1
        path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_current_full_model_regression_parent(root, receipt_dir=root / ".flowguard/evidence/model-owner-receipts")

