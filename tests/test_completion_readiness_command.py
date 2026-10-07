"""Focused contracts for the private completion-readiness producer entry."""

from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

from flowguard import _completion_readiness_impl as readiness_impl
from flowguard import completion_readiness
from flowguard import self_blueprint
from flowguard.completion_run_manifest import (
    COMPLETION_RUN_MANIFEST_SCHEMA,
    invocation_projection,
    write_manifest,
)
from flowguard.evidence_lifecycle import fingerprint_payload
from scripts import check_flowguard_skill_suite as suite


def _completion_prerequisite_fixture(tmp_path, monkeypatch):
    """Real finite receipt/oracle/binding objects; parent lookup is a seam."""
    from dataclasses import replace
    from tests.test_skill_native_model_receipts import fixture
    from flowguard.source_identity import source_file_fingerprint

    root = tmp_path / "repo"
    root.mkdir()
    material = fixture(root)
    manifest_path = root / ".flowguard/models/regression-manifest.json"
    manifest_path.write_text(json.dumps({"models": [
        {"model_id": "alpha"}, {"model_id": "beta"},
    ]}), encoding="utf-8")
    material.registry = replace(
        material.registry,
        source_manifest_fingerprint=source_file_fingerprint(manifest_path),
    )
    definition = {
        "schema_version": self_blueprint.SELF_BLUEPRINT_DEFINITION_SCHEMA,
        "blueprint_id": "blueprint:finite",
        "inventory_id": "inventory:finite",
        "boundary": {},
        "scan_python_patterns": ["flowguard/**/*.py", "scripts/**/*.py"],
        "scoped_out_patterns": [], "bounded_dynamic_prefixes": [],
        "dynamic_allowances": [], "dynamic_selector_contracts": [],
        "composite_behavior_contracts": [],
        "owner_overrides": {"flowguard/skill_native_checks.py": "alpha"},
        "resource_groups": {},
        "claim_boundary": "Finite static readiness fixture only.",
    }
    definition_path = root / self_blueprint.DEFAULT_SELF_BLUEPRINT_DEFINITION
    definition_path.parent.mkdir(parents=True, exist_ok=True)
    definition_path.write_text(json.dumps(definition), encoding="utf-8")
    material.definition_path = definition_path
    material.observed_manifest = ({
        "path": "flowguard/skill_native_checks.py", "sha256": "sha256:" + "a" * 64,
    },)
    monkeypatch.setattr(self_blueprint, "load_native_case_mapping", lambda _: material.registry)
    monkeypatch.setattr(self_blueprint.ModelRegressionManifest, "load", lambda _: object())
    monkeypatch.setattr(self_blueprint, "select_entries", lambda _, tier: (
        SimpleNamespace(model_id="alpha"), SimpleNamespace(model_id="beta"),
    ))
    material.parent_reads = []

    def current_parent(_root, *, receipt_dir):
        material.parent_reads.append(receipt_dir)
        return material.parent

    monkeypatch.setattr(self_blueprint, "resolve_current_full_model_regression_parent", current_parent)
    for name in ("build_flowguard_self_blueprint", "build_implementation_surface_inventory",
                 "discover_python_implementation_surfaces"):
        monkeypatch.setattr(self_blueprint, name, lambda *a, **k: pytest.fail("no producer or scan"))
    return material


def test_readiness_prerequisites_report_all_unowned_paths_before_native_lookup(tmp_path, monkeypatch):
    material = _completion_prerequisite_fixture(tmp_path, monkeypatch)
    manifest = material.observed_manifest + tuple(
        {"path": path, "sha256": "sha256:" + "b" * 64}
        for path in ("flowguard/new_helper.py", "scripts/new_launcher.py")
    )
    before = material.definition_path.read_bytes()
    with pytest.raises(self_blueprint.FlowGuardSelfBlueprintError) as error:
        self_blueprint.validate_completion_source_prerequisites(
            material.root, resolved_manifest=manifest, model_receipt_dir=material.store,
        )
    assert "self_blueprint_path_owner_missing" in str(error.value)
    assert "flowguard/new_helper.py" in str(error.value)
    assert "scripts/new_launcher.py" in str(error.value)
    assert material.parent_reads == []
    assert material.definition_path.read_bytes() == before


def test_readiness_prerequisites_reject_foreign_path_owner(tmp_path, monkeypatch):
    material = _completion_prerequisite_fixture(tmp_path, monkeypatch)
    definition = json.loads(material.definition_path.read_text("utf-8"))
    definition["owner_overrides"]["flowguard/skill_native_checks.py"] = "foreign"
    material.definition_path.write_text(json.dumps(definition), encoding="utf-8")
    with pytest.raises(self_blueprint.FlowGuardSelfBlueprintError, match="override is unknown"):
        self_blueprint.validate_completion_source_prerequisites(
            material.root, resolved_manifest=material.observed_manifest,
            model_receipt_dir=material.store,
        )
    assert material.parent_reads == []


@pytest.mark.parametrize("mutation", ["missing-protected-finding", "bad-oracle"])
def test_readiness_prerequisites_reject_pass_receipt_with_incomplete_native_binding(
    tmp_path, monkeypatch, mutation,
):
    from dataclasses import replace
    import hashlib

    material = _completion_prerequisite_fixture(tmp_path, monkeypatch)
    child = material.parent.children[1]
    result = child.native_case_results[0]
    result = (
        replace(result, observed_finding_codes=())
        if mutation == "missing-protected-finding"
        else replace(result, oracle_results=tuple(dict(row, ok=False) for row in result.oracle_results))
    )
    path = Path(child.native_case_result_artifact_path)
    payload = json.loads(path.read_text("utf-8"))
    payload["results"] = [result.to_dict()]
    path.write_text(json.dumps(payload), encoding="utf-8")
    child = replace(child, native_case_results=(result,),
                    native_case_result_artifact_fingerprint="sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    assert child.receipt.result_status == "pass" and child.verification.ok
    material.parent = replace(material.parent, children=(material.parent.children[0], child))
    with pytest.raises(self_blueprint.FlowGuardSelfBlueprintError, match="incomplete: model:beta"):
        self_blueprint.validate_completion_source_prerequisites(
            material.root, resolved_manifest=material.observed_manifest,
            model_receipt_dir=material.store,
        )
    assert material.parent_reads == [material.store]


def test_readiness_prerequisites_verify_finite_native_binding_once_without_writes(tmp_path, monkeypatch):
    material = _completion_prerequisite_fixture(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for path in material.root.rglob("*") if path.is_file()}
    result = self_blueprint.validate_completion_source_prerequisites(
        material.root, resolved_manifest=material.observed_manifest,
        model_receipt_dir=material.store,
    )
    assert result == {"scan_path_count": 1, "native_owner_count": 2, "native_case_count": 2,
                      "producer_count": 0, "write_count": 0}
    assert material.parent_reads == [material.store]
    assert before == {path: path.read_bytes() for path in material.root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("entry", ["readiness-freeze", "official-plan-only", "cached-readiness"])
def test_readiness_static_gap_blocks_both_planners_before_owner_or_output(tmp_path, monkeypatch, entry):
    material = _completion_prerequisite_fixture(tmp_path, monkeypatch)
    definition = json.loads(material.definition_path.read_text("utf-8"))
    definition["owner_overrides"] = {}
    material.definition_path.write_text(json.dumps(definition), encoding="utf-8")
    observations = []

    def observe(*a, **k):
        observations.append(1)
        return SimpleNamespace(repository_input_manifest=material.observed_manifest)

    monkeypatch.setattr(suite, "_full_child_specs", lambda *a: ())
    monkeypatch.setattr(suite, "_owner_contracts", lambda *a: ())
    for module in (suite, readiness_impl):
        monkeypatch.setattr(module, "observe_validation_owners", observe)
        monkeypatch.setattr(module, "build_validation_owner_plan", lambda *a, **k: pytest.fail("no owner plan"))
    monkeypatch.setattr(readiness_impl, "_run_gate", lambda *a, **k: pytest.fail("no gate"))
    monkeypatch.setattr(readiness_impl, "write_manifest", lambda *a, **k: pytest.fail("no write"))
    output = material.root / "readiness-output"
    if entry == "readiness-freeze":
        args = readiness_impl._base_suite_args(_args(material.root, output), material.root)
        with pytest.raises(readiness_impl.CompletionReadinessError, match="self_blueprint_path_owner_missing"):
            readiness_impl._freeze_plan(args, material.root)
    elif entry == "official-plan-only":
        state = tmp_path / "author-state"
        state.mkdir()
        args = suite.build_parser().parse_args([
            "--scope", "full", "--root", str(material.root), "--plan-only",
            "--author-state-root", str(state), "--completion-readiness", str(output / "readiness.json"),
        ])
        monkeypatch.setattr(suite, "_load_completion_run_manifest", lambda *a: (None, None, "", ()))
        result = suite.run_full_validation(args)
        assert result.status == suite.VALIDATION_STATUS_BLOCKED
        assert any("self_blueprint_path_owner_missing" in str(item) for item in result.failures)
        assert result.artifact_paths == ()
    else:
        state = tmp_path / "author-state"
        state.mkdir()
        args = _cached_release_args(material.root, output, state)
        _write_cached_readiness_envelope(args)
        saved = {path: path.read_bytes() for path in output.iterdir()}
        monkeypatch.setattr(readiness_impl, "validate_preflight_inputs", lambda *a: {
            "claim_scope": "release", "author_state_root": str(state.resolve()),
            "objective": {"fingerprint": "sha256:" + "d" * 64},
            "read_request": _current_read_request(),
        })
        cached_manifest_path = output / "completion-run-manifest.json"
        cached_manifest = json.loads(cached_manifest_path.read_text("utf-8"))
        monkeypatch.setattr(suite, "_load_completion_run_manifest", lambda *a: (
            cached_manifest, cached_manifest_path, "", (),
        ))
        with pytest.raises(completion_readiness.CompletionReadinessError, match="current full plan"):
            completion_readiness.produce(args)
        assert saved == {path: path.read_bytes() for path in output.iterdir()}
    assert observations == [1]
    assert material.parent_reads == []
    if entry != "cached-readiness":
        assert not output.exists()


def _args(root: Path, output: Path, *extra: str):
    return completion_readiness.build_parser().parse_args(
        ["--root", str(root), "--completion-work-id", "work:test", "--output-dir", str(output), *extra]
    )


def _write_objective(root: Path, name: str = "demo-objective") -> Path:
    change = root / "openspec" / "changes" / name
    (change / "specs" / "demo").mkdir(parents=True)
    (change / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    (change / "proposal.md").write_text("## Why\n\nA reviewed objective.\n", encoding="utf-8")
    (change / "design.md").write_text("## Context\n\nA bounded design.\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1.1 pending\n", encoding="utf-8")
    (change / "specs" / "demo" / "spec.md").write_text(
        "## ADDED Requirements\n\n### Requirement: Demo\n\nThe system SHALL prove it.\n\n"
        "#### Scenario: Pass\n- **WHEN** run\n- **THEN** pass\n",
        encoding="utf-8",
    )
    return change


def _archive_objective(change: Path, day: str = "2026-09-28") -> Path:
    archive = change.parent / "archive"
    archive.mkdir(exist_ok=True)
    return change.rename(archive / f"{day}-{change.name}")


def _valid_read_request(monkeypatch, tmp_path: Path, request: dict | None = None):
    root = tmp_path / "repo"
    request_path = root / ".flowguard" / "read-request.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    payload = request or {
        "operation": "read",
        "target_id": "system:current",
        "scope": ["model:a", "model:b"],
    }
    request_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    head = SimpleNamespace(system_id="system:current", fingerprint="sha256:" + "1" * 64)
    projection = {
        "index_fingerprint": "sha256:" + "2" * 64,
        "index": {"models": {"model:b": {}, "model:a": {}}},
    }
    monkeypatch.setattr(readiness_impl, "load_observed_model_head", lambda _root: head)
    monkeypatch.setattr(readiness_impl, "_load_bound_read_projection", lambda _root, _head: projection)
    return root, request_path, head, projection


def test_private_wrapper_delegates_once(monkeypatch):
    calls = []
    monkeypatch.setattr(completion_readiness, "main", lambda argv=None: calls.append(argv) or 23)
    wrapper = Path(__file__).resolve().parents[1] / "scripts" / "prepare_flowguard_completion_readiness.py"
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(wrapper), run_name="__main__")
    assert exited.value.code == 23
    assert calls == [None]


def test_public_lifecycle_stays_three_operations(capsys):
    from flowguard.__main__ import main

    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "{read,change,release}" in output
    assert "completion-readiness" not in output


@pytest.mark.parametrize("state_kind", ["missing", "inside", "ancestor", "file"])
def test_invalid_release_state_blocks_before_any_gate_or_output(
    tmp_path: Path,
    monkeypatch,
    state_kind: str,
):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "author-state"
    inside = root / "state"
    if state_kind == "inside":
        inside.mkdir()
        state_value = str(inside)
    elif state_kind == "ancestor":
        state_value = str(tmp_path)
    elif state_kind == "file":
        outside.write_text("not a directory", encoding="utf-8")
        state_value = str(outside)
    elif state_kind == "missing":
        state_value = str(outside)
    else:  # pragma: no cover - parameter set is closed
        raise AssertionError(state_kind)
    output = root / ".flowguard" / "evidence" / "completion-readiness" / "run-a"
    args = _args(
        root,
        output,
        "--claim-scope",
        "release",
        "--author-state-root",
        state_value,
    )
    monkeypatch.setattr(
        readiness_impl,
        "_run_gate",
        lambda *a, **k: pytest.fail("a release gate must not run before state admission"),
    )
    with pytest.raises(completion_readiness.CompletionReadinessError, match="author_state_root"):
        completion_readiness.produce(args)
    assert not output.exists()


def test_missing_read_request_blocks_before_gates_or_output(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    output = root / ".flowguard" / "evidence" / "completion-readiness" / "run-a"
    args = _args(root, output)
    monkeypatch.setattr(
        readiness_impl,
        "_run_gate",
        lambda *a, **k: pytest.fail("gates must not run without the fixed project request"),
    )
    monkeypatch.setattr(
        readiness_impl,
        "produce",
        lambda *_a, **_k: pytest.fail("native producer must not run without the fixed project request"),
    )
    with pytest.raises(completion_readiness.CompletionReadinessError, match="completion_read_request_missing"):
        completion_readiness.produce(args)
    assert not output.exists()


def test_prepared_request_uses_current_bound_index_and_complete_sorted_scope(
    monkeypatch,
    tmp_path: Path,
):
    root, request_path, head, projection = _valid_read_request(monkeypatch, tmp_path)

    result = readiness_impl._validate_current_read_request(root)

    assert result["scope"] == ["model:a", "model:b"]
    assert result["target_id"] == head.system_id
    assert result["head_fingerprint"] == head.fingerprint
    assert result["read_projection_index_fingerprint"] == projection["index_fingerprint"]
    assert result["path"] == str(request_path)


@pytest.mark.parametrize(
    ("read_request", "error_code"),
    [
        (
            {"operation": "read", "target_id": "system:current", "scope": ["model:a"]},
            "completion_read_request_scope_mismatch",
        ),
        (
            {"operation": "read", "target_id": "system:current", "scope": ["model:b", "model:a"]},
            "completion_read_request_scope_mismatch",
        ),
        (
            {"operation": "read", "target_id": "system:stale", "scope": ["model:a", "model:b"]},
            "completion_read_request_target_mismatch",
        ),
        (
            {"operation": "read", "target_id": "system:current", "scope": ["model:a", "model:a"]},
            "completion_read_request_invalid",
        ),
        (
            {"operation": "read", "target_id": "system:current", "scope": ["model:a", "model:b"], "cursor": "old"},
            "completion_read_request_invalid",
        ),
    ],
)
def test_read_request_scope_and_fields_are_exact(
    monkeypatch,
    tmp_path: Path,
    read_request: dict,
    error_code: str,
):
    root, *_ = _valid_read_request(monkeypatch, tmp_path, read_request)
    with pytest.raises(readiness_impl.CompletionReadinessError, match=error_code):
        readiness_impl._validate_current_read_request(root)


def _current_read_gate_payload() -> dict:
    return {
        "operation": "read",
        "status": "pass",
        "target_id": "system:current",
        "requested_model_ids": ["model:a", "model:b"],
        "selected_model_ids": ["model:a", "model:b"],
        "as_of": {"authority_head_fingerprint": "sha256:" + "1" * 64},
        "authority_integrity": "pass",
        "selected_source_currentness": "current",
        "execution_evidence_status": "not_run",
        "producer_count": 0,
        "write_count": 0,
        "stale_obligations": [],
        "blockers": [],
        # The currentness summary covers the complete selected scope even
        # when the detailed model projection needs another page.
        "next_cursor": "current-page-two",
    }


def _current_read_gate(payload: dict) -> dict:
    return {
        "parsed": {"format": "json", "payload": payload},
        "gate_fingerprint": "sha256:" + "f" * 64,
    }


def _current_read_request() -> dict:
    return {
        "target_id": "system:current",
        "scope": ["model:a", "model:b"],
        "head_fingerprint": "sha256:" + "1" * 64,
    }


def _write_cached_readiness_envelope(
    args,
    *,
    read_request: dict | None = None,
    objective_fingerprint: str | None = "sha256:" + "d" * 64,
) -> None:
    from flowguard.completion_epoch import (
        COMPLETION_CYCLE_SCHEMA,
        CompletionEpochPlan,
        CompletionEpochReadiness,
    )
    from flowguard.evidence_receipts import fingerprint_value

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    request = read_request or _current_read_request()
    request_path = root / ".flowguard" / "read-request.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "operation": "read",
                "target_id": request["target_id"],
                "scope": request["scope"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    gate_payload = _current_read_gate_payload()
    gate_payload["target_id"] = request["target_id"]
    gate_payload["requested_model_ids"] = request["scope"]
    gate_payload["selected_model_ids"] = request["scope"]
    gate_payload["as_of"]["authority_head_fingerprint"] = request["head_fingerprint"]
    read_gate_semantic = {
        "schema_version": "flowguard.completion_readiness_gate.v1",
        "gate_id": "current-read",
        "command": [
            sys.executable,
            "-m",
            "flowguard",
            "read",
            "--root",
            str(root),
            "--request",
            str(request_path),
            "--json",
        ],
        "cwd": str(root),
        "exit_code": 0,
        "terminal_reason": "exited",
        "cleanup_confirmed": True,
        "parsed": _current_read_gate(gate_payload)["parsed"],
    }
    read_gate = {
        **read_gate_semantic,
        "diagnostics": {
            "stdout_sha256": "sha256:" + "1" * 64,
            "stderr_sha256": "sha256:" + "2" * 64,
            "elapsed_seconds": 0.1,
            "terminal_reason": "exited",
        },
        "gate_fingerprint": fingerprint_payload(read_gate_semantic),
    }
    owner_gate_semantic = {
        "schema_version": "flowguard.completion_readiness_owner_dag.v1",
        "owner_plan_fingerprint": "sha256:" + "3" * 64,
        "parent_identity": "sha256:" + "4" * 64,
        "source_observation_fingerprint": "sha256:" + "5" * 64,
        "owner_ids": ["owner:test"],
        "dependency_edges": [],
        "current_read_gate_fingerprint": read_gate["gate_fingerprint"],
    }
    owner_gate_fingerprint = fingerprint_payload(owner_gate_semantic)
    owner_gate = {
        **owner_gate_semantic,
        "gate_fingerprint": owner_gate_fingerprint,
    }
    suite_args = readiness_impl._base_suite_args(args, root)
    receipt_root = root / ".flowguard" / "evidence" / "validation-owners"
    if objective_fingerprint is None:
        required_ids = suite._required_child_ids(suite._full_child_specs(suite_args, root))
        objective_fingerprint = fingerprint_value(
            {
                "schema_version": COMPLETION_CYCLE_SCHEMA,
                "required_terminal_action_ids": list(required_ids),
            }
        )
    plan = CompletionEpochPlan.freeze(
        source_observation_fingerprint="sha256:" + "1" * 64,
        release_tree_fingerprint="sha256:" + "2" * 64,
        toolchain_environment_fingerprint="sha256:" + "3" * 64,
        fixed_owner_dag_fingerprint="sha256:" + "4" * 64,
        model_authority_head_fingerprint=request["head_fingerprint"],
        model_authority_snapshot_fingerprint="sha256:" + "6" * 64,
        test_inventory_fingerprint="sha256:" + "7" * 64,
        completion_objective_fingerprint=objective_fingerprint,
        required_terminal_action_ids=("owner:test",),
        completion_work_id=args.completion_work_id,
        maintenance_unit_id=args.maintenance_unit_id,
        claim_scope=args.claim_scope,
    )
    readiness = CompletionEpochReadiness.for_plan(
        plan,
        openspec_terminal_receipt_fingerprint="sha256:" + "8" * 64,
        external_roots_sync_receipt_fingerprint="sha256:" + "9" * 64,
        formal_shadow_installed_sync_receipt_fingerprint="sha256:" + "a" * 64,
        reverse_input_acceptance_receipt_fingerprint="sha256:" + "b" * 64,
        owner_dag_freeze_receipt_fingerprint=owner_gate_fingerprint,
    )
    readiness_payload = readiness.to_dict()
    manifest_path = output_dir / "completion-run-manifest.json"
    manifest = {
        "schema_version": COMPLETION_RUN_MANIFEST_SCHEMA,
        "claim_boundary": "test fixture only",
        "invocation": invocation_projection(
            args=args,
            root=root,
            receipt_root=receipt_root,
        ),
        "plan": {
            "readiness_fingerprint": readiness_payload["readiness_fingerprint"],
            "completion_objective_fingerprint": objective_fingerprint,
        },
    }
    manifest["manifest_fingerprint"] = fingerprint_payload(manifest)
    write_manifest(manifest_path, manifest)

    evidence = {
        "schema_version": "flowguard.completion_readiness_evidence.v1",
        "readiness_fingerprint": readiness_payload["readiness_fingerprint"],
        "completion_work_id": args.completion_work_id,
        "claim_scope": args.claim_scope,
        "completion_run_manifest_path": str(manifest_path),
        "completion_run_manifest_fingerprint": manifest["manifest_fingerprint"],
        "gates": {"current_read": read_gate, "owner_dag": owner_gate},
    }
    (output_dir / "readiness.json").write_text(
        json.dumps(readiness_payload, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "readiness.evidence.json").write_text(
        json.dumps(evidence, sort_keys=True), encoding="utf-8"
    )


def _cached_release_args(root: Path, output: Path, author_state: Path):
    return _args(
        root,
        output,
        "--claim-scope",
        "release",
        "--author-state-root",
        str(author_state),
        "--shadow-root",
        str(root / "shadow"),
        "--completion-objective-change",
        "demo-objective",
    )


def _install_cached_preflight(monkeypatch, current: dict) -> None:
    def validate(args, _root):
        args.author_state_root = current["author_state_root"]
        return current

    monkeypatch.setattr(readiness_impl, "validate_preflight_inputs", validate)

    def admitted_plan(args):
        assert args.plan_only is True
        readiness = json.loads(Path(args.completion_readiness).read_text("utf-8"))
        return SimpleNamespace(
            status=suite.VALIDATION_STATUS_PARTIAL,
            scope="full-plan-only",
            counts={"blocked": 0},
            blockers=(),
            artifact_paths=(),
            progress_summary={
                "completed": 0,
                "completion_epoch_admission": {
                    "status": "admitted", "ok": True, "blockers": [],
                },
                "completion_readiness_fingerprint": readiness["readiness_fingerprint"],
            },
        )

    monkeypatch.setattr(suite, "run_full_validation", admitted_plan)


def test_cached_readiness_revalidates_current_read_without_rerunning_gates(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()
    author_state = tmp_path / "author-state"
    author_state.mkdir()
    args = _cached_release_args(root, root / "out", author_state)
    current = {
        "claim_scope": "release",
        "author_state_root": str(author_state.resolve()),
        "objective": {"fingerprint": "sha256:" + "d" * 64},
        "read_request": _current_read_request(),
    }
    _write_cached_readiness_envelope(args)
    _install_cached_preflight(monkeypatch, current)
    monkeypatch.setattr(
        readiness_impl,
        "_run_gate",
        lambda *_a, **_k: pytest.fail("an exact cached handoff must not rerun its gates"),
    )

    result = completion_readiness.produce(args)

    assert result["status"] == "pass"


@pytest.mark.parametrize("current_timeout", [120.0, 900.0])
def test_cached_readiness_preserves_nondefault_gate_timeout(
    tmp_path: Path,
    monkeypatch,
    current_timeout: float,
):
    root = tmp_path / "repo"
    root.mkdir()
    author_state = tmp_path / "author-state"
    author_state.mkdir()
    args = _cached_release_args(root, root / "out", author_state)
    args.gate_timeout = 120.0
    _write_cached_readiness_envelope(args)
    current = {
        "claim_scope": "release",
        "author_state_root": str(author_state.resolve()),
        "objective": {"fingerprint": "sha256:" + "d" * 64},
        "read_request": _current_read_request(),
    }
    _install_cached_preflight(monkeypatch, current)
    monkeypatch.setattr(
        readiness_impl,
        "_run_gate",
        lambda *_a, **_k: pytest.fail("cached readiness must not rerun gates"),
    )
    monkeypatch.setattr(
        suite,
        "_execute_command",
        lambda *_a, **_k: pytest.fail("cached readiness must not start owners"),
    )
    args.gate_timeout = current_timeout
    suite_args = readiness_impl._base_suite_args(args, root)
    assert suite_args.gate_timeout == current_timeout
    output_dir = Path(args.output_dir)
    saved_bytes = {path.name: path.read_bytes() for path in output_dir.iterdir()}
    if current_timeout == 120.0:
        assert completion_readiness.produce(args)["status"] == "pass"
    else:
        with pytest.raises(
            completion_readiness.CompletionReadinessError,
            match="completion_run_manifest_invocation_mismatch",
        ):
            completion_readiness.produce(args)
    assert saved_bytes == {path.name: path.read_bytes() for path in output_dir.iterdir()}


def test_cached_local_readiness_revalidates_default_objective_identity(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()
    args = _args(root, root / "out")
    current = {
        "claim_scope": "local_validation",
        "author_state_root": "",
        "objective": None,
        "read_request": _current_read_request(),
    }
    _write_cached_readiness_envelope(args, objective_fingerprint=None)
    _install_cached_preflight(monkeypatch, current)

    result = completion_readiness.produce(args)

    assert result["status"] == "pass"


@pytest.mark.parametrize(
    "drift",
    ["authority_head", "target", "scope", "author_state_root", "objective_fingerprint"],
)
def test_cached_readiness_blocks_when_current_admission_identity_drifts(
    tmp_path: Path,
    monkeypatch,
    drift: str,
):
    root = tmp_path / "repo"
    root.mkdir()
    original_state = tmp_path / "author-state-original"
    current_state = tmp_path / "author-state-current"
    original_state.mkdir()
    current_state.mkdir()
    args = _cached_release_args(root, root / "out", original_state)
    old_objective_fingerprint = "sha256:" + "d" * 64
    _write_cached_readiness_envelope(
        args,
        read_request=_current_read_request(),
        objective_fingerprint=old_objective_fingerprint,
    )
    output_dir = Path(args.output_dir)
    saved_bytes = {
        name: (output_dir / name).read_bytes()
        for name in (
            "readiness.json",
            "readiness.evidence.json",
            "completion-run-manifest.json",
        )
    }
    current = {
        "claim_scope": "release",
        "author_state_root": str(original_state.resolve()),
        "objective": {"fingerprint": old_objective_fingerprint},
        "read_request": _current_read_request(),
    }
    if drift == "authority_head":
        current["read_request"] = {
            **current["read_request"],
            "head_fingerprint": "sha256:" + "2" * 64,
        }
    elif drift == "target":
        current["read_request"] = {
            **current["read_request"],
            "target_id": "system:current-v2",
        }
    elif drift == "scope":
        current["read_request"] = {
            **current["read_request"],
            "scope": ["model:a"],
        }
    elif drift == "author_state_root":
        args.author_state_root = str(current_state)
        current["author_state_root"] = str(current_state.resolve())
    else:
        current["objective"] = {"fingerprint": "sha256:" + "e" * 64}
    _install_cached_preflight(monkeypatch, current)
    monkeypatch.setattr(
        readiness_impl,
        "_run_gate",
        lambda *_a, **_k: pytest.fail("stale cached readiness must not rerun gates"),
    )

    with pytest.raises(completion_readiness.CompletionReadinessError, match="existing readiness"):
        completion_readiness.produce(args)
    assert saved_bytes == {
        name: (output_dir / name).read_bytes()
        for name in saved_bytes
    }



@pytest.mark.parametrize("changed_kind", ["source", "test", "toolchain"])
def test_cached_readiness_rejects_current_full_plan_drift(
    tmp_path: Path, monkeypatch, changed_kind: str,
):
    root = tmp_path / "repo"
    root.mkdir()
    state = tmp_path / "author-state"
    state.mkdir()
    args = _cached_release_args(root, root / "out", state)
    _write_cached_readiness_envelope(args)
    current = {
        "claim_scope": "release",
        "author_state_root": str(state.resolve()),
        "objective": {"fingerprint": "sha256:" + "d" * 64},
        "read_request": _current_read_request(),
    }
    _install_cached_preflight(monkeypatch, current)
    envelope_paths = [
        root / "out" / name for name in (
            "readiness.json", "readiness.evidence.json",
            "completion-run-manifest.json",
        )
    ]
    before = {path.name: path.read_bytes() for path in envelope_paths}
    governed = root / (changed_kind + ".input")
    governed.write_text("original", encoding="utf-8")
    frozen_bytes = governed.read_bytes()
    governed.write_text("changed", encoding="utf-8")
    calls = []

    def stale_plan(plan_args):
        assert plan_args.plan_only is True
        assert Path(plan_args.completion_readiness) == root / "out" / "readiness.json"
        assert governed.read_bytes() != frozen_bytes
        calls.append(changed_kind)
        return SimpleNamespace(
            status=suite.VALIDATION_STATUS_BLOCKED,
            scope="full",
            counts={"blocked": 1},
            blockers=({"code": "completion_run_manifest_plan_mismatch"},),
            progress_summary={},
            artifact_paths=(),
        )

    monkeypatch.setattr(suite, "run_full_validation", stale_plan)
    monkeypatch.setattr(
        readiness_impl, "_run_gate",
        lambda *_a, **_k: pytest.fail("cache validation must not rerun gates"),
    )
    monkeypatch.setattr(
        suite, "_execute_command",
        lambda *_a, **_k: pytest.fail("cache plan must not start an owner"),
    )
    monkeypatch.setattr(
        completion_readiness, "_write_once",
        lambda *_a, **_k: pytest.fail("cache validation must preserve old evidence"),
    )
    with pytest.raises(
        completion_readiness.CompletionReadinessError, match="current full plan",
    ):
        completion_readiness.produce(args)
    assert calls == [changed_kind]
    assert before == {path.name: path.read_bytes() for path in envelope_paths}

def test_current_read_gate_accepts_only_exact_current_full_read():
    readiness_impl._assert_current_read_gate(
        _current_read_gate(_current_read_gate_payload()),
        read_request=_current_read_request(),
        expected_head_fingerprint="sha256:" + "1" * 64,
    )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("operation", "change", "public read operation"),
        ("authority_integrity", "blocked", "authority integrity"),
        # A later-page stale obligation can be absent from this page; the
        # aggregate currentness field must still block the gate.
        ("selected_source_currentness", "stale", "source currentness"),
        ("stale_obligations", ["model:b:source-stale"], "stale obligations"),
        ("target_id", "system:other", "target differs"),
        ("selected_model_ids", ["model:a"], "complete preflighted model scope"),
        ("execution_evidence_status", "ran", "producer-free"),
        ("producer_count", 1, "start producers"),
        ("write_count", 1, "write evidence"),
        ("blockers", ["source_stale"], "contains blockers"),
    ],
)
def test_current_read_gate_rejects_stale_or_mismatched_read(
    field: str,
    value,
    error: str,
):
    payload = _current_read_gate_payload()
    payload[field] = value
    with pytest.raises(readiness_impl.CompletionReadinessError, match=error):
        readiness_impl._assert_current_read_gate(
            _current_read_gate(payload),
            read_request=_current_read_request(),
            expected_head_fingerprint="sha256:" + "1" * 64,
        )


def test_current_read_gate_rejects_request_head_changed_after_preflight():
    with pytest.raises(readiness_impl.CompletionReadinessError, match="request authority changed"):
        readiness_impl._assert_current_read_gate(
            _current_read_gate(_current_read_gate_payload()),
            read_request=_current_read_request(),
            expected_head_fingerprint="sha256:" + "2" * 64,
        )


def test_current_read_gate_rejects_read_result_from_another_authority_head():
    request = _current_read_request()
    request["head_fingerprint"] = "sha256:" + "2" * 64
    with pytest.raises(readiness_impl.CompletionReadinessError, match="authority head differs"):
        readiness_impl._assert_current_read_gate(
            _current_read_gate(_current_read_gate_payload()),
            read_request=request,
            expected_head_fingerprint="sha256:" + "2" * 64,
        )


def test_release_requires_named_archived_objective_before_gates(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    author_state = tmp_path / "author-state"
    author_state.mkdir()
    _write_objective(root)
    output = root / ".flowguard" / "evidence" / "completion-readiness" / "run-a"
    args = _args(
        root,
        output,
        "--claim-scope",
        "release",
        "--author-state-root",
        str(author_state),
        "--completion-objective-change",
        "demo-objective",
    )
    monkeypatch.setattr(
        readiness_impl,
        "_run_gate",
        lambda *a, **k: pytest.fail("archive admission must precede all gates"),
    )
    with pytest.raises(completion_readiness.CompletionReadinessError, match="completion_objective_not_archived"):
        completion_readiness.produce(args)
    assert not output.exists()


def test_release_requires_unique_valid_archive_and_rejects_bad_date_sibling(tmp_path: Path):
    root = tmp_path / "repo"
    good = _archive_objective(_write_objective(root))

    resolved = readiness_impl._require_archived_completion_objective(root, "demo-objective")
    assert resolved.fingerprint.startswith("sha256:")
    assert not (root / "openspec" / "changes" / "demo-objective").exists()

    (good.parent / "2026-02-30-demo-objective").mkdir()
    with pytest.raises(readiness_impl.CompletionReadinessError, match="completion_objective_invalid_archive_date"):
        readiness_impl._require_archived_completion_objective(root, "demo-objective")


def test_release_objective_rejects_duplicate_archives_and_invalid_reparse_points(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "repo"
    first = _archive_objective(_write_objective(root), "2026-09-28")
    second = root / "openspec" / "changes" / "archive" / "2026-09-29-demo-objective"
    import shutil

    shutil.copytree(first, second)
    with pytest.raises(readiness_impl.CompletionReadinessError, match="completion_objective_ambiguous_archive"):
        readiness_impl._require_archived_completion_objective(root, "demo-objective")

    shutil.rmtree(second)
    from flowguard import completion_objective

    monkeypatch.setattr(
        completion_objective,
        "_is_reparse_point",
        lambda path: path == first or path.name.startswith("2026-") and path != first.parent,
    )
    with pytest.raises(readiness_impl.CompletionReadinessError, match="completion_objective_invalid_root"):
        readiness_impl._require_archived_completion_objective(root, "demo-objective")


def test_local_validation_keeps_active_objective_usable(
    tmp_path: Path,
    monkeypatch,
):
    root, *_ = _valid_read_request(monkeypatch, tmp_path)
    _write_objective(root)
    args = SimpleNamespace(
        claim_scope="local_validation",
        author_state_root="",
        completion_objective_change="demo-objective",
        objective_change="",
    )

    result = readiness_impl.validate_preflight_inputs(args, root)

    assert result["objective"] is None
    assert result["read_request"]["scope"] == ["model:a", "model:b"]


def test_producer_failure_writes_no_readiness(tmp_path: Path, monkeypatch):
    root, *_ = _valid_read_request(monkeypatch, tmp_path)
    output = root / ".flowguard" / "evidence" / "completion-readiness" / "run-failed"
    args = _args(root, output)
    monkeypatch.setattr(readiness_impl, "validate_preflight_inputs", lambda *_: {})
    monkeypatch.setattr(
        readiness_impl,
        "produce",
        lambda *_a, **_k: (_ for _ in ()).throw(
            readiness_impl.CompletionReadinessError("gate failed")
        ),
    )
    with pytest.raises(completion_readiness.CompletionReadinessError, match="gate failed"):
        completion_readiness.produce(args)
    assert not output.exists()


def test_release_state_is_frozen_in_manifest_invocation(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    first_state = tmp_path / "author-state-a"
    second_state = tmp_path / "author-state-b"
    first_state.mkdir()
    second_state.mkdir()
    args = SimpleNamespace(
        author_state_root=str(first_state),
        output_dir=str(root / "out-a"),
        completion_objective_change="demo-objective",
        maintenance_unit_id="unit:flowguard-suite",
        completion_work_id="work:manifest",
        claim_scope="release",
    )
    first = invocation_projection(args=args, root=root, receipt_root=root / "receipts")
    args.author_state_root = str(second_state)
    second = invocation_projection(args=args, root=root, receipt_root=root / "receipts")

    assert first["author_state_root"] == str(first_state.resolve())
    assert second["author_state_root"] == str(second_state.resolve())
    assert first != second


def test_changed_manifest_argument_blocks_before_owner_observation(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()
    first_state = tmp_path / "author-state-a"
    second_state = tmp_path / "author-state-b"
    first_state.mkdir()
    second_state.mkdir()
    receipt_root = root / ".flowguard" / "evidence" / "validation-owners"
    original_args = suite.build_parser().parse_args(
        [
            "--scope",
            "full",
            "--root",
            str(root),
            "--claim-scope",
            "local_validation",
            "--author-state-root",
            str(first_state),
        ]
    )
    payload = {
        "schema_version": COMPLETION_RUN_MANIFEST_SCHEMA,
        "claim_boundary": "test fixture only",
        "invocation": invocation_projection(
            args=original_args,
            root=root,
            receipt_root=receipt_root,
        ),
        "plan": {},
    }
    payload["manifest_fingerprint"] = fingerprint_payload(payload)
    manifest_path = root / ".flowguard" / "evidence" / "completion-readiness" / "manifest.json"
    write_manifest(manifest_path, payload)

    args = suite.build_parser().parse_args(
        [
            "--scope",
            "full",
            "--root",
            str(root),
            "--claim-scope",
            "local_validation",
            "--author-state-root",
            str(second_state),
            "--completion-run-manifest",
            str(manifest_path),
            "--plan-only",
        ]
    )
    monkeypatch.setattr(
        suite,
        "observe_validation_owners",
        lambda *_a, **_k: pytest.fail("manifest mismatch must precede owner observation"),
    )

    result = suite.run_full_validation(args)

    assert result.status == "blocked"
    mismatch = next(
        item for item in result.blockers
        if item.get("code") == "completion_run_manifest_invocation_mismatch"
    )
    assert any(
        item.get("field") == "invocation.author_state_root"
        for item in mismatch.get("differences", ())
    )


def test_readiness_args_forward_author_state_to_full_child(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()
    state = tmp_path / "author-state"
    state.mkdir()
    args = _args(
        root,
        root / "out",
        "--author-state-root",
        str(state),
        "--claim-scope",
        "release",
        "--shadow-root",
        str(tmp_path / "shadow"),
    )
    monkeypatch.setattr(suite, "_author_toolchain_fingerprint", lambda _path: "sha256:" + "a" * 64)

    child_args = readiness_impl._base_suite_args(args, root)
    specs = suite._full_child_specs(child_args, root)
    author_child = next(item for item in specs if item.child_id == "skill_suite_light")

    assert child_args.author_state_root == str(state.resolve())
    assert author_child.command[author_child.command.index("--author-state-root") + 1] == str(state.resolve())


@pytest.mark.parametrize("explicit_manifest", [False, True], ids=["default", "explicit"])
def test_readiness_freezes_and_writes_exact_full_consumer_manifest_path(
    tmp_path: Path, monkeypatch, explicit_manifest: bool,
):
    from flowguard.completion_epoch import CompletionEpochPlan

    root = tmp_path / "repo"
    root.mkdir()
    output = root / ".flowguard" / "evidence" / "completion-readiness" / "current"
    manifest_path = (
        root / ".flowguard" / "evidence" / "explicit-run.json"
        if explicit_manifest else output / "completion-run-manifest.json"
    )
    extra = ("--completion-run-manifest", str(manifest_path)) if explicit_manifest else ()
    args = _args(root, output, *extra)
    plan = CompletionEpochPlan.freeze(
        source_observation_fingerprint="sha256:" + "1" * 64,
        release_tree_fingerprint="sha256:" + "2" * 64,
        toolchain_environment_fingerprint="sha256:" + "3" * 64,
        owner_dag_fingerprint="sha256:" + "4" * 64,
        model_authority_fingerprint="sha256:" + "5" * 64,
        test_inventory_fingerprint="sha256:" + "6" * 64,
        required_terminal_action_ids=("skill_native_checks", "skill_self_governance"),
        maintenance_unit_id=args.maintenance_unit_id,
        completion_work_id=args.completion_work_id,
        claim_scope=args.claim_scope,
    )
    receipt_root = root / ".flowguard" / "evidence" / "validation-owners"
    frozen_commands = {}

    def freeze(child_args, frozen_root):
        assert frozen_root == root
        assert child_args.completion_run_manifest == str(manifest_path)
        assert not manifest_path.exists()  # No provisional manifest or consumer execution.
        for spec in suite._full_child_specs(child_args, frozen_root):
            frozen_commands[spec.child_id] = list(suite.canonical_semantic_command(
                spec.command, resource_options=spec.resource_options,
            ))
        return (
            plan,
            SimpleNamespace(plan_fingerprint="sha256:" + "7" * 64, contracts=()),
            SimpleNamespace(parent_identity="sha256:" + "8" * 64),
            SimpleNamespace(source_observation_fingerprint=plan.source_observation_fingerprint),
            receipt_root,
            None,
        )

    monkeypatch.setattr(readiness_impl, "_freeze_plan", freeze)
    monkeypatch.setattr(readiness_impl, "load_current_model_authority_state", lambda _: SimpleNamespace(
        head=SimpleNamespace(activation_receipt_fingerprint="sha256:" + "a" * 64,
                             fingerprint="sha256:" + "1" * 64),
        accepted_revision=None,
        snapshot=SimpleNamespace(fingerprint="sha256:" + "b" * 64),
    ))
    monkeypatch.setattr(readiness_impl, "load_current_reverse_surface_owner_authority", lambda *a, **k: {
        "authority_artifact_fingerprint": "sha256:" + "a" * 64,
        "discovery_fingerprint": "sha256:" + "b" * 64,
        "discovered_surface_count": 0, "owner_routes": [], "owner_receipt_identities": [],
    })
    gate_ids = []

    def gate(_root, gate_id, command, **kwargs):
        gate_ids.append(gate_id)
        if gate_id == "current-read":
            result = _current_read_gate(_current_read_gate_payload())
            result["gate_fingerprint"] = "sha256:" + "c" * 64
            return result
        return {"gate_fingerprint": "sha256:" + "d" * 64}

    monkeypatch.setattr(readiness_impl, "_run_gate", gate)
    writes = []
    real_write = readiness_impl.write_manifest

    def write(path, manifest):
        writes.append(path)
        return real_write(path, manifest)

    monkeypatch.setattr(readiness_impl, "write_manifest", write)
    readiness, evidence = readiness_impl.produce(
        args, preflight_inputs={"read_request": _current_read_request()},
    )
    manifest = json.loads(manifest_path.read_text("utf-8"))
    assert writes == [manifest_path]
    assert evidence["completion_run_manifest_path"] == str(manifest_path)
    assert evidence["completion_run_manifest_fingerprint"] == manifest["manifest_fingerprint"]
    assert readiness["readiness_fingerprint"] == manifest["plan"]["readiness_fingerprint"]
    assert gate_ids == ["openspec-terminal", "current-read"]
    manifest_commands = {item["child_id"]: item["command"]
                         for item in manifest["plan"]["child_semantic_commands"]}
    full_args = readiness_impl._base_suite_args(args, root)
    full_args.completion_readiness = str(output / "readiness.json")
    if not explicit_manifest:
        full_args.completion_run_manifest = ""  # Normal full CLI discovers the sibling.
    for spec in suite._full_child_specs(full_args, root):
        if spec.child_id in {"skill_native_checks", "skill_self_governance"}:
            full_command = list(suite.canonical_semantic_command(
                spec.command, resource_options=spec.resource_options,
            ))
            assert frozen_commands[spec.child_id] == manifest_commands[spec.child_id] == full_command
            position = full_command.index("--completion-run-manifest")
            assert full_command[position + 1] == str(manifest_path)


@pytest.mark.parametrize("foreign_path", [False, True], ids=["default-output", "explicit-manifest"])
def test_readiness_rejects_foreign_manifest_before_freeze_or_gate(
    tmp_path: Path, monkeypatch, foreign_path: bool,
):
    root = tmp_path / "repo"
    root.mkdir()
    output = root / "out" if foreign_path else tmp_path / "foreign-output"
    extra = ("--completion-run-manifest", str(tmp_path / "foreign.json")) if foreign_path else ()
    args = _args(root, output, *extra)
    monkeypatch.setattr(readiness_impl, "_freeze_plan", lambda *a, **k: pytest.fail("must reject before freeze"))
    monkeypatch.setattr(readiness_impl, "_run_gate", lambda *a, **k: pytest.fail("must reject before gates"))
    with pytest.raises(readiness_impl.CompletionReadinessError, match="must remain inside"):
        readiness_impl.produce(args, preflight_inputs={"read_request": _current_read_request()})
    assert not output.exists()
    assert not (tmp_path / "foreign.json").exists()


def test_readiness_typed_repair_needs_no_provisional_manifest_or_native_consumer(
    tmp_path: Path, monkeypatch,
):
    from flowguard.completion_epoch import (
        CompletionEpochPlan, CompletionEpochTerminalLedger, load_completion_repair_admission_group,
    )

    def plan(source):
        return CompletionEpochPlan.freeze(
            source_observation_fingerprint=source,
            release_tree_fingerprint="sha256:" + "2" * 64,
            toolchain_environment_fingerprint="sha256:" + "3" * 64,
            owner_dag_fingerprint="sha256:" + "4" * 64,
            model_authority_fingerprint="sha256:" + "5" * 64,
            test_inventory_fingerprint="sha256:" + "6" * 64,
            required_terminal_action_ids=("skill_native_checks", "skill_self_governance"),
        )

    previous = plan("sha256:" + "1" * 64).claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(previous, "native consumer context failed")
    ledger_path = ledger.write(tmp_path)
    before = ledger_path.read_bytes()
    current = plan("sha256:" + "8" * 64)
    regression = tmp_path / "narrow-regression.json"
    regression.write_text(json.dumps({
        "scope": "patch_regression", "status": "pass", "exit_code": 0,
        "cleanup_confirmed": True,
        "tested_input_manifest": {"source_observation_fingerprint": current.source_observation_fingerprint},
        "failed_owner_ids": ["skill_native_checks", "skill_self_governance"],
    }), encoding="utf-8")
    monkeypatch.setattr(suite, "run_full_validation", lambda *a, **k: pytest.fail("repair must not run owners"))
    monkeypatch.setattr(readiness_impl, "_run_gate", lambda *a, **k: pytest.fail("repair must not launch gates"))
    repaired, loaded, link, group_path = readiness_impl._prepare_repair_admission(
        args=SimpleNamespace(repair_from_epoch=previous.epoch_id, repair_regression_evidence=str(regression)),
        root=tmp_path, current_plan=current, output_dir=tmp_path / "readiness",
    )
    assert loaded == ledger
    assert repaired.attempt_index == 1 and repaired.full_producer_attempts == 0
    group = load_completion_repair_admission_group(
        repaired.repair_link, tmp_path, previous_ledger=ledger, current_plan=current,
    )
    assert group.producer_invocations == 0
    assert link.is_file() and group_path.is_file()
    assert ledger_path.read_bytes() == before
    assert not list(tmp_path.rglob("completion-run-manifest.json"))
    assert CompletionEpochTerminalLedger.load_for_epoch_id(repaired.epoch_id, tmp_path).is_absent
