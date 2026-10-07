"""Light entry is a bounded read; cache writes are explicit author work."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from flowguard.skill_contracts import ContractCompileReport
from flowguard.skill_suite import (
    FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES,
    SkillSuiteMemberReport,
    SkillSuiteReport,
)
from flowguard.model_authority_store import read_selected_model_closure
from flowguard.__main__ import _bounded_read_page, _read_cursor_token


def _r9_transport_fixture():
    fields = ("facts_scope", "objective_refs", "finding_refs", "suggestion_refs",
              "observation_gap_ids", "improvement_gap_ids", "improvement_pointers", "scope_proof_refs")
    base = {"operation": "read", "stale_obligations": ["stale:" + str(i) for i in range(50)],
            "architecture": {key: [{"id": key + str(i), "value": "边界🙂" * 15}
                                    for i in range(25)] for key in fields},
            "functional_understanding": {"status": "needs_evidence", "actions": [
                {"id": str(i), "value": "下一步" * 20} for i in range(30)]}}
    base["growth_gaps"] = [{"gap_id": "growth:" + str(i), "next_action": "提供当前模型" * 10}
                           for i in range(30)]
    base["checked_observed_paths"] = ["src/observed_" + str(i) + ".py" for i in range(30)]
    base["architecture"]["summary"] = {
        "current": {"selected_model_count": 1},
        "target": ["objective:" + str(i) for i in range(30)],
        "gap": {"observation_gap_ids": ["observation:" + str(i) for i in range(30)],
                "improvement_gap_ids": ["improvement:" + str(i) for i in range(30)],
                "growth_gap_ids": ["growth:" + str(i) for i in range(30)], "task_first_gap_ref": None},
        "action": {"pointer_ids": ["pointer:" + str(i) for i in range(30)],
                   "next_owner_ids": ["owner:" + str(i) for i in range(30)],
                   "detail_refs": [{"path": "detail/" + str(i) + ".json", "sha256": "a" * 64} for i in range(30)],
                   "action_target_count": 30},
        "scope": {"claim_scope": "transport_fixture_only"},
    }
    compact = {"models": [{"model_id": "alpha", "input_paths": ["src/" + str(i) + ".py" for i in range(90)]}],
               "intents": [{"id": "intent:" + str(i)} for i in range(10)],
               "relations": [{"id": "relation:" + str(i)} for i in range(10)],
               "boundary_nodes": [{"id": "boundary:" + str(i)} for i in range(10)]}
    return base, compact


def _r9_pages(base, compact, prepared=None):
    pages, cursor = [], None
    while True:
        page = _bounded_read_page(base, compact, head_fingerprint="sha256:" + "a" * 64,
                                  scope=("alpha",), cursor=cursor, prepared_transport=prepared)
        pages.append(page)
        cursor = page["next_cursor"]
        if cursor is None:
            return pages


def test_r9_e06_02_new_test_same_prepared_transport_object_used_once_across_two_wide_explicit_bat():
    import flowguard.__main__ as entry
    base, compact = _r9_transport_fixture()
    with patch.object(entry, "_prepare_read_transport", wraps=entry._prepare_read_transport) as prepare:
        prepared = entry._prepare_read_transport(base, compact)
        pages = _r9_pages(base, compact, prepared)
        assert len(pages) > 2 and prepare.call_count == 1
    for field, rows in base["architecture"].items():
        if field == "summary":
            continue
        assert [r for p in pages for r in p["architecture"][field]] == rows
    assert [r for p in pages for r in p["functional_understanding"]["actions"]] == base["functional_understanding"]["actions"]
    for field in ("growth_gaps", "checked_observed_paths"):
        assert [r for p in pages for r in p[field]] == base[field]
    summary = base["architecture"]["summary"]
    for key in ("current", "scope"):
        transported = [p["architecture"]["summary"][key] for p in pages
                       if p["architecture"]["summary"][key]]
        assert transported == [summary[key]]
    assert all(p["architecture"]["summary"]["gap"]["task_first_gap_ref"] is None for p in pages)
    assert all(p["architecture"]["summary"]["action"]["action_target_count"] == 30 for p in pages)
    assert [r for p in pages for r in p["architecture"]["summary"]["target"]] == summary["target"]
    for group, fields in (("gap", ("observation_gap_ids", "improvement_gap_ids", "growth_gap_ids")),
                          ("action", ("pointer_ids", "next_owner_ids", "detail_refs"))):
        for field in fields:
            assert [r for p in pages for r in p["architecture"]["summary"][group][field]] == summary[group][field]


def test_r9_e06_03_new_test_separate_cursor_invocation_prepares_its_own_transport():
    import flowguard.__main__ as entry
    base, compact = _r9_transport_fixture()
    with patch.object(entry, "_prepare_read_transport", wraps=entry._prepare_read_transport) as prepare:
        first = entry._bounded_read_page(base, compact, head_fingerprint="sha256:" + "a" * 64,
                                        scope=("alpha",), cursor=None)
        entry._bounded_read_page(base, compact, head_fingerprint="sha256:" + "a" * 64,
                                scope=("alpha",), cursor=first["next_cursor"])
        assert prepare.call_count == 2


def test_r9_e06_04_new_test_old_vs_extracted_records_order_full_reassembly_and_exact_emitted_utf8():
    from flowguard.__main__ import _prepare_read_transport
    base, compact = _r9_transport_fixture()
    independently_prepared_pages = _r9_pages(base, compact)
    shared_pages = _r9_pages(base, compact, _prepare_read_transport(base, compact))
    encode = lambda p: json.dumps(p, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    assert [encode(p) for p in shared_pages] == [encode(p) for p in independently_prepared_pages]
    assert all(len(encode(p)) <= 8192 for p in shared_pages)
    assert [r for p in shared_pages for r in p["stale_obligations"]] == base["stale_obligations"]
    for lane in ("intents", "relations", "boundary_nodes"):
        assert [r for p in shared_pages for r in p["map"][lane]] == compact[lane]


def test_r8_default_light_budget_is_unset_but_explicit_budget_still_blocks():
    from scripts.check_flowguard_skill_suite import _LightSuiteCost, _LightSuiteBudgetExceeded
    cost = _LightSuiteCost(None, None)
    cost.step(1024)
    assert cost.operation_count == 1024
    with pytest.raises(_LightSuiteBudgetExceeded, match="operation budget exceeded"):
        _LightSuiteCost(0, None).step()
    with pytest.raises(_LightSuiteBudgetExceeded, match="time budget exceeded"):
        _LightSuiteCost(None, 0).check()


@pytest.mark.parametrize("request_extra", ({"read_batch": 1}, {"read_batch": True, "cursor": None}, {"unknown": True}))
def test_r8_read_batch_request_rejects_foreign_or_conflicting_fields(tmp_path, request_extra):
    from flowguard.__main__ import _read_operation
    with pytest.raises(ValueError):
        _read_operation(tmp_path, {"operation": "read", "target_id": "fixture", "scope": ["alpha"], **request_extra}, {})


@pytest.mark.parametrize("drift", (False, True))
def test_r8_complete_selected_batch_constructs_once_and_preserves_all_lanes(tmp_path, drift):
    import flowguard.__main__ as entry
    from flowguard.model_authority import ModelAuthorityHead, canonical_fingerprint
    from flowguard.model_authority_store import _artifact_path, render_model_authority_section, SelectedModelClosureRead
    head = ModelAuthorityHead("fixture", "sha256:"+"a"*64, "fixture", 1,
        "sha256:"+"b"*64, "", "sha256:"+"c"*64)
    manifest=tmp_path/".flowguard/project.toml"
    manifest.parent.mkdir()
    manifest.write_text(render_model_authority_section(head, snapshot_path=".flowguard/models/fixture.json", coverage_status="pass"), encoding="utf-8")
    payload={"schema": "flowguard.test.batch_index.v1", "models": {"alpha": {}}}
    fp=canonical_fingerprint(payload)
    index={**payload,"fingerprint":fp}
    index_path=_artifact_path(tmp_path,"read-projection-indexes",fp)
    index_path.parent.mkdir(parents=True)
    index_path.write_text(json.dumps(index),encoding="utf-8")
    source=tmp_path/"selected.py"
    source.write_bytes(b"value = 1\n")
    fields=("facts_scope","objective_refs","finding_refs","suggestion_refs","observation_gap_ids","improvement_gap_ids","improvement_pointers","scope_proof_refs")
    architecture={field:[{"id":field+":"+str(i),"detail":"x"*90} for i in range(30)] for field in fields}
    architecture["facts_scope"] = [dict(row, understanding_status="native_check_only",
        responsibility_count=0, target_count=0) for row in architecture["facts_scope"]]
    architecture["objective_refs"] = [dict(row, objective={"objective_id": row["id"]})
                                      for row in architecture["objective_refs"]]
    architecture["improvement_pointers"] = [dict(row, pointer_id=row["id"],
        action_target_count=0, next_owner_ids=[],
        detail_ref={"path": "detail/" + str(i) + ".json", "sha256": "a" * 64})
        for i, row in enumerate(architecture["improvement_pointers"])]
    calls=[]
    def selected(root, **kwargs):
        calls.append(kwargs)
        kwargs["read_context"].bytes("selected.py")
        if drift:
            source.write_bytes(b"value = 2\n")
        return SelectedModelClosureRead(selected_model_ids=("alpha",),
            selected_models=(), relations=(), stale_obligations=(),
            authority_integrity="pass", selected_source_currentness="current", architecture=architecture)
    with patch("flowguard.model_authority_store.load_observed_model_head",return_value=head), \
         patch("flowguard.model_authority_store._load_bound_read_projection",return_value={"index":index,"index_fingerprint":fp}), \
         patch("flowguard.model_authority_store.read_selected_model_projection",side_effect=selected):
        result=entry._read_operation(tmp_path,{"operation":"read","target_id":"fixture","scope":["alpha"],"read_batch":True},{})
    assert len(calls)==1
    assert result["producer_count"]==result["write_count"]==0
    assert result["observation_boundary"]=="single_invocation_as_of"
    if drift:
        assert result["status"]=="blocked" and result["pages"]==[]
        return
    assert result["status"]=="pass" and result["page_count"]>1
    assert result["terminal_next_cursor"] is None
    for page in result["pages"]:
        assert len(json.dumps(page,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8"))+1<=8192
    for field in fields:
        assert [row for page in result["pages"] for row in page["architecture"][field]]==architecture[field]


@pytest.mark.parametrize("mutation", ("source", "head", "index", "appeared", "parent-became-file", "git-index", "other-manifest", "raw-manifest", "growth-manifest", "functional-growth-manifest"))
def test_r8_batch_rejects_selected_input_or_accepted_model_head_drift(tmp_path, mutation):
    """Finite typed fixture tests the guard; it publishes no accepted authority."""
    import os
    from dataclasses import replace
    from flowguard.model_authority import ModelAuthorityHead, canonical_fingerprint
    from flowguard.model_authority_store import (
        _SelectedReadContext, _artifact_path, _observe_growth_paths,
        bind_selected_read_authority, freeze_selected_read_observation,
        verify_selected_read_observation, render_model_authority_section,
    )
    root = tmp_path.resolve()
    head = ModelAuthorityHead("fixture", "sha256:" + "a" * 64, "fixture-current", 1,
        "sha256:" + "b" * 64, "", "sha256:" + "c" * 64)
    manifest = root / ".flowguard/project.toml"
    manifest.parent.mkdir()
    model_section = render_model_authority_section(head, snapshot_path=".flowguard/models/fixture.json", coverage_status="pass")
    manifest.write_text('[project]\nname="fixture"\n' + model_section, encoding="utf-8")
    identity = {"schema": "flowguard.test.guard-index.v1", "head": head.fingerprint}
    fingerprint = canonical_fingerprint(identity)
    index = {**identity, "fingerprint": fingerprint}
    index_path = _artifact_path(root, "read-projection-indexes", fingerprint)
    index_path.parent.mkdir(parents=True)
    index_path.write_text(json.dumps(index), encoding="utf-8")
    source = root / "selected.py"
    source.write_bytes(b"value = 1\n")
    context = _SelectedReadContext(root)
    bind_selected_read_authority(context, head=head, projection={"index_fingerprint": fingerprint, "index": index})
    if mutation == "raw-manifest":
        context.raw_fingerprint(".flowguard/project.toml", artifact=True)
    elif mutation == "growth-manifest":
        _observe_growth_paths(context, (".flowguard/project.toml",))
    elif mutation == "functional-growth-manifest":
        from flowguard.functional_read import observe_functional_growth_paths
        observe_functional_growth_paths(context, (".flowguard/project.toml",))
    if mutation in ("raw-manifest", "growth-manifest", "functional-growth-manifest"):
        assert ".flowguard/project.toml" in context.raw
        assert context.read_counts[".flowguard/project.toml"] == 1
    assert context.bytes("selected.py") is context.bytes("selected.py")
    assert context.read_counts["selected.py"] == 1
    _observe_growth_paths(context, ("missing.py", "missing-directory/child.py"))
    observation = freeze_selected_read_observation(context)
    assert verify_selected_read_observation(observation).ok
    if mutation == "source":
        stat = source.stat()
        source.write_bytes(b"value = 2\n")  # Same length, with the original mtime restored.
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    elif mutation == "head":
        new_head = replace(head, generation=2)
        manifest.write_text(render_model_authority_section(new_head, snapshot_path=".flowguard/models/fixture.json", coverage_status="pass"), encoding="utf-8")
    elif mutation == "index":
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")  # Same canonical content, different actual bytes.
    elif mutation == "appeared":
        (root / "missing.py").write_bytes(b"new\n")
    elif mutation == "parent-became-file":
        (root / "missing-directory").write_bytes(b"file prevents original missing path resolution")
    elif mutation == "git-index":
        (root / ".git").mkdir()
        (root / ".git/index").write_bytes(b"unrelated staging metadata")
    else:
        manifest.write_text('[project]\nname="changed unrelated metadata"\n' + model_section, encoding="utf-8")
    result = verify_selected_read_observation(observation)
    assert result.ok == (mutation in ("git-index", "other-manifest"))
    if mutation in ("raw-manifest", "growth-manifest", "functional-growth-manifest"):
        assert {"code": "selected_read_raw_input_drift", "path": ".flowguard/project.toml"} in result.findings
    assert result.to_dict()["producer_count"] == result.to_dict()["write_count"] == 0
    # A new invocation captures its own current raw bytes, never the previous cache.
    next_context = _SelectedReadContext(root)
    assert next_context.bytes("selected.py") == source.read_bytes()
    assert context.bytes("selected.py") == b"value = 1\n"


def _assert_lossless_read_pages(base, model_map, head, scope, *, prepared_transport=None):
    fields = ("facts_scope", "objective_refs", "finding_refs", "suggestion_refs", "observation_gap_ids", "improvement_gap_ids", "improvement_pointers", "scope_proof_refs")
    seen_architecture = {field: [] for field in fields}
    seen_context = {field: [] for field in ("intents", "relations", "boundary_nodes")}
    seen_models, seen_stale, pages = {}, [], []
    cursor = None
    while True:
        page = _bounded_read_page(base, model_map, head_fingerprint=head, scope=scope, cursor=cursor,
                                  prepared_transport=prepared_transport)
        assert len(json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1 <= 8192
        for field in fields:
            seen_architecture[field].extend(page["architecture"][field])
        for field in seen_context:
            seen_context[field].extend(page["map"][field])
        for row in page["map"]["models"]:
            model_id = row["model_id"]
            metadata = {key: value for key, value in row.items() if key != "input_paths"}
            if model_id not in seen_models:
                seen_models[model_id] = {**metadata, "input_paths": []}
            assert {key: value for key, value in seen_models[model_id].items() if key != "input_paths"} == metadata
            seen_models[model_id]["input_paths"].extend(row["input_paths"])
        seen_stale.extend(page["stale_obligations"])
        pages.append(page)
        following = page["next_cursor"]
        if following is None:
            break
        assert following != cursor and len(pages) < 2000
        cursor = following
    assert list(seen_models.values()) == model_map["models"]
    assert seen_context == {field: model_map[field] for field in seen_context}
    assert seen_architecture == {field: base["architecture"].get(field, []) for field in fields}
    assert seen_stale == base["stale_obligations"]
    summary = base["architecture"].get("summary")
    if summary:
        assert all(set(page["architecture"]["summary"]) == set(summary) for page in pages)
        for key in ("current", "scope"):
            transported = [page["architecture"]["summary"][key] for page in pages
                           if page["architecture"]["summary"][key]]
            assert transported == [summary[key]]
        for path in (("target",), ("gap", "observation_gap_ids"),
                     ("gap", "improvement_gap_ids"), ("gap", "growth_gap_ids"),
                     ("action", "pointer_ids"), ("action", "next_owner_ids"),
                     ("action", "detail_refs")):
            actual = [value for page in pages for value in
                      (page["architecture"]["summary"][path[0]] if len(path) == 1
                       else page["architecture"]["summary"][path[0]][path[1]])]
            expected = summary[path[0]] if len(path) == 1 else summary[path[0]][path[1]]
            assert actual == expected
    return pages


def test_wide_selected_scope_cursor_preserves_all_eight_architecture_lanes():
    # Three public selection lists model the metadata of a whole 51-model read.
    scope = tuple(f"model_{index:02d}_workflow_contract" for index in range(51))
    head = "sha256:" + "f" * 64
    fields = ("facts_scope", "objective_refs", "finding_refs", "suggestion_refs", "observation_gap_ids", "improvement_gap_ids", "improvement_pointers", "scope_proof_refs")
    architecture = {"schema": "flowguard.architecture_read_projection.v1", "architecture_confidence": "scoped", "requested_model_ids": list(scope), "effective_intent_view_fingerprint": head}
    for field in fields:
        architecture[field] = [{"reference_id": f"{field}:{index}", "model_id": scope[index], "material": "中" * 35} for index in range(51)]
    base = {"operation": "read", "status": "pass", "requested_model_ids": list(scope), "selected_model_ids": list(scope), "as_of": {key: head for key in ("authority_head_fingerprint", "snapshot_fingerprint", "accepted_revision_set_fingerprint", "activation_fingerprint", "read_index_fingerprint")}, "architecture": architecture, "stale_obligations": [f"obligation:{index}" for index in range(90)], "producer_count": 0, "write_count": 0}
    model_map = {"models": [{"model_id": model_id, "model_path": f"models/{model_id}.py", "runner_path": f"runners/{model_id}.py", "input_paths": [f"inputs/{model_id}/{index:03d}-" + "x" * 60 for index in range(120 if position == 0 else 12)]} for position, model_id in enumerate(scope)], **{field: [{"reference_id": f"{field}:{index}", "material": "中" * 35} for index in range(70)] for field in ("intents", "relations", "boundary_nodes")}}
    pages = _assert_lossless_read_pages(base, model_map, head, scope)
    assert len(pages) > 1
    cursor = pages[0]["next_cursor"]
    payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    assert "scope" not in payload and len(payload["scope_fingerprint"]) == 64
    assert len(cursor) < 600
    for other_head, other_scope in (("sha256:" + "a" * 64, scope), (head, scope[:-1]), (head, tuple(reversed(scope)))):
        with pytest.raises(ValueError, match="another authority head or scope"):
            _bounded_read_page(base, model_map, head_fingerprint=other_head, scope=other_scope, cursor=cursor)
    payload["scope_fingerprint"] = "0" * 64
    tampered = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    with pytest.raises(ValueError, match="integrity check failed"):
        _bounded_read_page(base, model_map, head_fingerprint=head, scope=scope, cursor=tampered)
    # An old transparent-scope shape has no compatibility authority.
    payload.pop("scope_fingerprint")
    payload["scope"] = list(scope)
    old_shape = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    with pytest.raises(ValueError, match="shape is not exact-current"):
        _bounded_read_page(base, model_map, head_fingerprint=head, scope=scope, cursor=old_shape)


def test_architecture_read_pages_preserve_all_references_with_bounded_bytes():
    head = "sha256:" + "f" * 64
    fields = ("facts_scope", "objective_refs", "finding_refs", "suggestion_refs", "observation_gap_ids", "improvement_gap_ids")
    architecture = {"schema": "flowguard.architecture_read_projection.v1", "architecture_confidence": "scoped"}
    for field in fields:
        architecture[field] = [f"{field}:{index}:" + "中" * 90 for index in range(45)]
    base = {"operation": "read", "architecture": architecture, "stale_obligations": []}
    model_map = {"models": [{"model_id": "alpha", "input_paths": ["model.py"]}], "intents": [], "relations": [], "boundary_nodes": []}
    seen = {field: [] for field in fields}
    cursor, page_count = None, 0
    while True:
        page = _bounded_read_page(base, model_map, head_fingerprint=head, scope=("alpha",), cursor=cursor)
        assert len(json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1 <= 8192
        for field in fields:
            seen[field].extend(page["architecture"][field])
        page_count += 1
        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        assert next_cursor != cursor and page_count < 100
        cursor = next_cursor
    assert page_count > 1
    assert seen == {field: architecture[field] for field in fields}
def test_public_selected_read_shares_current_source_bytes_with_architecture(tmp_path):
    import os
    import flowguard.model_authority_store as store
    from tests.test_model_authority_store import _r7_two_model_architecture_read_fixture
    from flowguard.source_identity import functional_source_fingerprint
    head, projection, shards, payload, revision, details = _r7_two_model_architecture_read_fixture(tmp_path)
    normative = next(row.source_ref for row in revision.current_effective_intent_view.active_contributions if row.logical_model_id.removeprefix("model:") == "alpha")
    tasks = "openspec/changes/fixture/tasks.md"
    task_path = tmp_path / tasks
    task_path.parent.mkdir(parents=True)
    task_path.write_bytes(b"- [ ] preserve contract\r\n```\r\n- [x] literal code\r\n```\r\n")
    for shard in shards:
        shard["source_paths"] = {normative: functional_source_fingerprint(tmp_path, normative), tasks: functional_source_fingerprint(tmp_path, tasks)}
    original_bytes, original_text = Path.read_bytes, Path.read_text
    reads, hashes, intents, intent_hashes = [], [], [], []
    from flowguard.model_intent import _ArchitectureSourceObservation
    observe = _ArchitectureSourceObservation.from_bytes
    def source_observation(data, kind):
        intent_hashes.append((data, kind))
        return observe(data, kind)
    watched = {tmp_path / normative, task_path, tmp_path / "beta-design.md"}
    fingerprint = store._selected_source_fingerprint
    from flowguard.model_intent import bind_architecture_objective_source
    def bytes_read(path):
        if path in watched: reads.append((path.relative_to(tmp_path).as_posix(), "bytes"))
        return original_bytes(path)
    def text_read(path, *args, **kwargs):
        if path in watched: reads.append((path.relative_to(tmp_path).as_posix(), "text"))
        return original_text(path, *args, **kwargs)
    def hash_source(root, path, data):
        hashes.append(path)
        return fingerprint(root, path, data)
    def intent_source(*args, **kwargs):
        intents.append(args[0].contribution_id)
        return bind_architecture_objective_source(*args, **kwargs)
    before = task_path.stat()
    with patch("flowguard.model_authority_store._read_content_addressed_payload", side_effect=payload), patch("flowguard.model_authority_store._load_selected_read_shards", return_value=shards), patch.object(Path, "read_bytes", bytes_read), patch.object(Path, "read_text", text_read), patch.object(store, "_selected_source_fingerprint", hash_source), patch("flowguard.model_intent.bind_architecture_objective_source", side_effect=intent_source), patch.object(_ArchitectureSourceObservation, "from_bytes", side_effect=source_observation):
        read = store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha", "beta"))
        assert sorted(reads) == sorted([(normative, "bytes"), (tasks, "bytes"), ("beta-design.md", "bytes")])
        assert sorted(hashes) == sorted((normative, tasks)) and len(intents) == 2
        assert read.selected_source_currentness == "current" and not read.architecture["observation_gap_ids"]
        assert read.architecture["objective_refs"][0]["objective"]["model_ids"] == ["alpha"]
        assert len(intent_hashes) == 2
        from flowguard.__main__ import _compact_read_map
        base = {"operation": "read", "as_of": dict(read.as_of), "architecture": read.architecture, "stale_obligations": []}
        page = _bounded_read_page(base, _compact_read_map(read), head_fingerprint=head.fingerprint, scope=("alpha", "beta"), cursor=None)
        assert page["next_cursor"] is None and page["architecture"]["objective_refs"] == read.architecture["objective_refs"]
        encoded = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        print("R7_READ_PROXY=" + json.dumps({"claim_boundary": "finite selected reader fixture; output bytes are a proxy, no token/speed claim", "selected_model_ids": list(read.selected_model_ids), "head_fingerprint": head.fingerprint, "revision_set_fingerprint": head.accepted_revision_set_fingerprint, "snapshot_fingerprint": head.snapshot_fingerprint, "read_index_fingerprint": projection["index_fingerprint"], "effective_intent_view_fingerprint": read.architecture["effective_intent_view_fingerprint"], "physical_read_counts": dict(read.read_counts), "physical_read_text_count": sum(kind == "text" for _, kind in reads), "functional_projection_counts": {path: hashes.count(path) for path in set(hashes)}, "intent_projection_count": len(intent_hashes), "raw_projections_not_requested": True, "required_objective_refs": read.architecture["objective_refs"], "full_reader_json_lf_bytes": len(encoded(read.to_dict())), "compact_page_json_lf_bytes": len(encoded(page)), "producer_count": read.producer_count, "write_count": read.write_count}, ensure_ascii=False, sort_keys=True))
        task_path.write_bytes(b"- [x] preserve contract\n```\n- [x] literal code\n```\n")
        checkbox = store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha", "beta"))
        assert checkbox.selected_source_currentness == "current"
        task_path.write_bytes(b"- [x] changed contract \n```\n- [x] literal code\n```\n")
        os.utime(task_path, ns=(before.st_atime_ns, before.st_mtime_ns))
        changed = store.read_selected_model_projection(tmp_path, head=head, projection=projection, selected_model_ids=("alpha", "beta"))
        assert changed.selected_source_currentness == "stale"
        assert len(reads) == 9 and len(hashes) == 6 and len(intents) == 6 and len(intent_hashes) == 6
        assert changed.producer_count == changed.write_count == 0


def test_new_architecture_pointers_and_scope_proofs_are_exact_across_pages():
    from flowguard.model_path_quality import ArchitectureImprovementPointer
    head = "sha256:" + "e" * 64
    fields = ("facts_scope", "objective_refs", "finding_refs", "suggestion_refs", "observation_gap_ids", "improvement_gap_ids", "improvement_pointers", "scope_proof_refs")
    architecture = {"schema": "flowguard.architecture_read_projection.v1", "architecture_confidence": "scoped"}
    for field in fields:
        architecture[field] = [{"reference_id": f"{field}:{index}", "material": "中" * 95} for index in range(23)]
    architecture["improvement_pointers"] = [ArchitectureImprovementPointer("", "model_gap", "needs_evidence", "normative_target", ("alpha",), ("responsibility:A",), (), ("class:accepted",), (), {"alpha": head}, ({"path": "docs/有限边界.md", "source_fingerprint": head},), (), (), (), ({"kind": "boundary_manifest", "model_id": "alpha", "responsibility_id": "responsibility:A", "reference_id": f"inventory:{index}:" + "中" * 95, "next_owner_id": "owner:inventory"},), ("owner:inventory",), ()).to_dict() for index in range(23)]
    architecture["scope_proof_refs"] = [{"model_id": "alpha", "subject_fingerprint": head, "claim_boundary": "complete_within_authenticated_frozen_boundary", "boundary_fingerprint": head, "inventory_fingerprint": head, "binding_report_fingerprint": head, "producer_receipt_id": f"receipt:{index}:" + "中" * 95, "producer_receipt_fingerprint": head, "live_unregistered_file_detection": "NOT_OBSERVED"} for index in range(23)]
    base = {"operation": "read", "architecture": architecture, "stale_obligations": []}
    model_map = {"models": [{"model_id": "alpha", "input_paths": ["model.py"]}], "intents": [], "relations": [], "boundary_nodes": []}
    seen, cursor, pages = {field: [] for field in fields}, None, 0
    while True:
        page = _bounded_read_page(base, model_map, head_fingerprint=head, scope=("alpha",), cursor=cursor)
        assert len(json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1 <= 8192
        for field in fields: seen[field].extend(page["architecture"][field])
        pages += 1
        if page["next_cursor"] is None: break
        assert page["next_cursor"] != cursor and pages < 100
        cursor = page["next_cursor"]
    assert pages > 1 and seen == {field: architecture[field] for field in fields}
    with pytest.raises(ValueError):
        _bounded_read_page(base, model_map, head_fingerprint="sha256:" + "a" * 64, scope=("alpha",), cursor=cursor)


def _compact_pointer_detail_fixture(tmp_path):
    """Independent accepted-storage fixture; no live project or native owner."""
    from dataclasses import replace
    from flowguard.model_intent import ArchitectureObjective, BoundArchitectureObjective
    from flowguard.model_path_quality import ArchitectureImprovementPointer, _NATIVE_REF_FIELDS
    from flowguard.model_authority_store import _artifact_path
    from tests.test_model_authority_store import _r6_architecture_read_fixture, _r7_bound_read_detail
    head, projection, shard, _, revision, details = _r6_architecture_read_fixture(tmp_path)
    identity = revision.current_effective_intent_view.verified_source_identities[0]
    subject = revision.path_quality_subjects[0]
    originals = []
    for index in range(3):
        objective = ArchitectureObjective(f"objective:fixture:goal:{index}", True,
            ("alpha",), (f"responsibility:fixture:{index}",), ("class:accepted",),
            "functional_obligations", {"required_obligation_ids": [f"obligation:fixture:{index}"],
                "required_code_contract_ids": [f"code-contract:fixture:{index}"],
                "native_case_pairs": [{"owner_id": "model:alpha", "source_case_id": f"case:fixture:{index}", "satisfied_observed_status": "ok"}]},
            "model:alpha", ("failure:fixture",))
        bound = BoundArchitectureObjective(objective, identity.contribution_id, identity.fingerprint,
            identity.source_ref, identity.source_fingerprint, revision.current_effective_intent_view.fingerprint)
        native = {key: "sha256:" + "a" * 64 if key.endswith("fingerprint") else "fixture:" + key
                  for key in _NATIVE_REF_FIELDS}
        native["oracle_member_ids"] = [f"oracle:fixture:{member}:" + "observed" * 12 for member in range(23)]
        originals.append(ArchitectureImprovementPointer("", "goal_mismatch", "needs_evidence", "normative_target",
            ("alpha",), (f"responsibility:fixture:{index}",), (f"element:fixture:{index}",),
            ("class:accepted",), (), {"alpha": subject.fingerprint},
            ({"path": f"docs/功能边界{index}.md", "source_fingerprint": identity.source_fingerprint},),
            (bound.to_dict(),), (f"obligation:fixture:{index}",), (native,),
            ({"kind": "objective_source", "model_id": "alpha", "responsibility_id": f"responsibility:fixture:{index}",
              "reference_id": objective.objective_id, "next_owner_id": "model:alpha"},),
            ("model:alpha",),
            ({"trigger_id": f"trigger:fixture:{index}", "source_ref": "docs/再次审查.md",
              "source_fingerprint": identity.source_fingerprint, "condition_ref": "condition:changed"},)).to_dict())
    facts = json.loads(json.dumps(details[0].body["model_facts"]))
    facts["architecture"]["improvement_pointers"] = originals
    revision, details, payload = _r7_bound_read_detail(head, projection, revision, facts)
    # Output-only pointers do not alter the normalized subject identity.
    assert revision.path_quality_subjects[0].fingerprint == subject.fingerprint
    detail = details[0]
    path = _artifact_path(tmp_path, "path-quality-details", detail.fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(detail.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    detail_ref = {"path": path.relative_to(tmp_path).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return head, projection, shard, payload, revision, details, originals, detail_ref


def test_compact_improvement_pointers_preserve_wide_scope_and_complete_details(tmp_path):
    import flowguard.model_authority_store as store
    head, projection, shard, payload, revision, details, originals, detail_ref = _compact_pointer_detail_fixture(tmp_path)
    with patch.object(store, "_read_content_addressed_payload", side_effect=payload), \
         patch.object(store, "_load_selected_read_shards", return_value=(shard,)):
        architecture = store.derive_architecture_read_projection(
            tmp_path, head=head, projection=projection, selected_model_ids=("alpha",)).to_dict()
    compact = architecture["improvement_pointers"]
    assert compact == [store._architecture_pointer_read_reference(row, detail_ref=detail_ref) for row in originals]
    assert all(len(json.dumps(row, ensure_ascii=False).encode("utf-8")) > 5400 for row in originals)
    assert len(compact) == 3 and all(row["status"] == "needs_evidence" for row in compact)
    for before, after in zip(originals, compact):
        assert all(after[key] == before[key] for key in store._ARCHITECTURE_POINTER_READ_FIELDS)
        assert after["objective_ids"] == [before["objective_refs"][0]["objective"]["objective_id"]]
    scope = ("alpha", *(f"model_{index:02d}_workflow_contract" for index in range(53)))
    architecture["requested_model_ids"] = list(scope)
    base = {"operation": "read", "status": "pass", "target_id": "flowguard",
        "requested_model_ids": list(scope), "selected_model_ids": list(scope),
        "as_of": {key: head.fingerprint for key in ("authority_head_fingerprint", "snapshot_fingerprint", "accepted_revision_set_fingerprint", "read_projection_index_fingerprint")},
        "architecture": architecture, "stale_obligations": [], "producer_count": 0, "write_count": 0}
    model_map = {"models": [{"model_id": model, "input_paths": [model + "/模块.py"]} for model in scope],
                 "intents": [], "relations": [], "boundary_nodes": []}
    pages = _assert_lossless_read_pages(base, model_map, head.fingerprint, scope)
    assert len(pages) > 1
    with patch.object(store, "load_observed_model_head", return_value=head), \
         patch.object(store, "_load_bound_read_projection", return_value=projection), \
         patch.object(store, "_read_content_addressed_payload", side_effect=payload):
        assert [store.resolve_architecture_improvement_pointer(tmp_path, row) for row in compact] == originals


@pytest.mark.parametrize("damage", ("hash", "path", "semantic", "head", "duplicate"))
def test_compact_pointer_resolver_rejects_foreign_or_changed_evidence(tmp_path, damage):
    import flowguard.model_authority_store as store
    head, projection, shard, payload, revision, details, originals, ref = _compact_pointer_detail_fixture(tmp_path)
    row = store._architecture_pointer_read_reference(originals[0], detail_ref=ref)
    if damage == "hash":
        row["detail_ref"]["sha256"] = "0" * 64
    elif damage == "path":
        row["detail_ref"]["path"] = ".flowguard/models/authority/path-quality-details/" + "0" * 64 + ".json"
    elif damage == "semantic":
        row["next_owner_ids"] = ["model:foreign"]
    elif damage == "head":
        projection["index"]["revision_set_fingerprint"] = "sha256:" + "0" * 64
    else:
        row["objective_ids"] *= 2
    with patch.object(store, "load_observed_model_head", return_value=head), \
         patch.object(store, "_load_bound_read_projection", return_value=projection), \
         patch.object(store, "_read_content_addressed_payload", side_effect=payload), \
         pytest.raises((ValueError, store.ModelAuthorityError)):
        store.resolve_architecture_improvement_pointer(tmp_path, row)


def test_functional_objective_missing_reference_remains_in_local_detail_gaps():
    from flowguard.__main__ import _scoped_architecture_objective_gaps
    goal = "objective:fixture:functional-map"
    missing = "functional_objective_evidence_missing:" + goal + ":code-contract:fixture:missing"
    required = "required_architecture_objective_unmet:" + goal
    foreign = "functional_objective_evidence_missing:objective:foreign:" + goal
    unrelated = "functional_objective_evidence_missing:objective:fixture:functional-mapping:case:other"
    assert not missing.endswith(":" + goal)
    assert _scoped_architecture_objective_gaps((missing, required, foreign, unrelated), (goal,)) == {missing, required}


@pytest.mark.parametrize("change", ("", "foreign_only", "missing_pair"))
def test_functional_goal_verifies_only_its_complete_original_native_binding(tmp_path, change):
    """Two independently bound finite receipts with disjoint obligations."""
    from dataclasses import replace
    from flowguard.model_path_quality import evaluate_architecture_objectives, verify_architecture_native_case_refs, derive_architecture_improvement_pointers
    from flowguard.evidence_receipts import save_evidence_receipt
    from tests.test_evidence_receipts import current_context
    from tests.test_model_path_quality import _r8_verified_function_material, _r8_functional_goal, _r7_native_material, subject
    fact, code, inventory, report, material, inputs, review, required = _r8_verified_function_material(tmp_path)
    goals, view = _r8_functional_goal(tmp_path, fact, code, required)
    other_root = tmp_path / "other"
    other = _r7_native_material(other_root, obligations=("obligation:other-owner",))
    contract = replace(other["native_contracts"][0], owner_id="model:beta", source_case_id="case:other")
    result = replace(other["native_results"][0], owner_id=contract.owner_id, source_case_id=contract.source_case_id,
                     raw_artifact_path=str(other_root / "native.json"))
    binding = replace(other["native_bindings"][0], owner_id=contract.owner_id, native_case_ids=(contract.source_case_id,))
    envelope = other_root / "native-results.json"
    envelope.write_text(json.dumps({"schema_version": result.to_dict()["schema_version"], "results": [result.to_dict()]}), encoding="utf-8")
    proof = {"child": {"payload": {"model_result": {"model_id": "beta", "input_inventory_fingerprint": result.input_fingerprint,
        "native_case_result_artifact_path": str(envelope),
        "native_case_result_artifact_fingerprint": "sha256:" + hashlib.sha256(envelope.read_bytes()).hexdigest(),
        "executed_case_ids": [result.source_case_id], "native_case_results": [result.to_dict()]}}}}
    raw_proof = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt = replace(other["receipts"][0], receipt_id="receipt:validation-owner:model:beta:finite",
        subject_id="validation-owner:model:beta", producer_id="validation-owner:model:beta",
        proof_artifact_fingerprint="sha256:" + hashlib.sha256(raw_proof).hexdigest(),
        result_fingerprint="sha256:" + hashlib.sha256(raw_proof).hexdigest(),
        metadata={"proof_relpath": "proofs/beta.json"})
    (other_root / "receipts/proofs/beta.json").write_bytes(raw_proof)
    save_evidence_receipt(receipt, output_directory=other_root / "receipts")
    context = current_context(receipt, receipt_store_repository_root=str(tmp_path),
                              receipt_store_output_directory=str(other_root / "receipts"))
    identity = other["current_native_identities"][(other["native_contracts"][0].owner_id, other["native_contracts"][0].source_case_id)]
    foreign = {"native_contracts": (contract,), "native_bindings": (binding,), "native_results": (result,),
        "receipts": (receipt,), "receipt_contexts": {receipt.receipt_id: context}, "raw_artifact_root": tmp_path,
        "current_native_identities": {(contract.owner_id, contract.source_case_id): identity}}
    foreign_refs, foreign_gaps = verify_architecture_native_case_refs(**foreign, required_obligation_ids=("obligation:other-owner",))
    assert len(foreign_refs) == 1 and not foreign_gaps
    mixed = {**material,
        **{key: (*material[key], *foreign[key]) for key in ("native_contracts", "native_bindings", "native_results", "receipts")},
        "receipt_contexts": {**material["receipt_contexts"], **foreign["receipt_contexts"]},
        "current_native_identities": {**material["current_native_identities"], **foreign["current_native_identities"]}}
    # The old all-owner join incorrectly demanded alpha's obligation from beta.
    _, unscoped_gaps = verify_architecture_native_case_refs(**mixed, required_obligation_ids=(required,))
    assert any(row["kind"] == "owner_receipt" and row["next_owner_id"] == "model:beta" for row in unscoped_gaps)
    if change == "foreign_only": mixed["native_bindings"] = foreign["native_bindings"]
    elif change == "missing_pair": mixed["native_bindings"] = ()
    actual = evaluate_architecture_objectives(goals, (fact,), code_contracts=(code,),
        binding_report=report, implementation_inventory=inventory, semantic_reviews=(review,),
        native_materials=mixed, current_source_fingerprints=inputs["current_source_fingerprints"],
        effective_intent_view=view, root=tmp_path)
    assert bool(actual["satisfied_objective_ids"]) == (change == "")
    if change:
        assert actual["observation_gap_ids"] and any(row["kind"] == "native_result" and row["reference_id"] == "case:good" for row in actual["missing_inputs"])
        owner = subject(model_id=fact.model_id, intent_fingerprint=view.fingerprint)
        pointers = derive_architecture_improvement_pointers(responsibilities=(fact,), subjects=(owner,),
            objectives=goals, objective_evaluation=actual, semantic_reviews=(review,),
            code_contracts=(code,), binding_report=report, native_materials=mixed)
        assert pointers and all(pointer.status == "needs_evidence" for pointer in pointers)
        assert any(row["kind"] == "native_result" and row["reference_id"] == "case:good"
                   for pointer in pointers for row in pointer.missing_input_refs)
        assert not any(row["kind"] == "objective_source" for pointer in pointers for row in pointer.missing_input_refs)
    else:
        assert not actual["observation_gap_ids"] and not actual["improvement_gap_ids"]


from scripts import check_flowguard_skill_suite as suite


def _fixture(root: Path) -> tuple[SkillSuiteReport, ContractCompileReport]:
    skill = root / ".agents" / "skills" / "target"
    for relative in FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES:
        path = skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}\n", encoding="utf-8")
    (root / ".skillguard" / "flowguard-suite").mkdir(parents=True)
    (root / ".skillguard" / "flowguard-suite" / "suite-map.json").write_text(
        json.dumps(
            {
                "schema_version": "skillguard.suite_map.v2",
                "suite_name": "flowguard-agent-skill-suite",
                "included_skills": [
                    {
                        "name": "target",
                        "path": ".agents/skills/target",
                        "role": "public_satellite",
                        "owner": "target",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (root / ".flowguard" / "work" / "flowguard").mkdir(parents=True)
    member = SkillSuiteMemberReport(
        skill_id="target",
        role="public_satellite",
        owner="target",
        declared_path=".agents/skills/target",
        repository_role="skill_maintainer_source",
        discovered=True,
        control_root_present=True,
        required_files={relative: True for relative in FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES},
        source_hash="SOURCE",
    )
    inventory = SkillSuiteReport(
        root=str(root.resolve()),
        schema_version="skillguard.suite_map.v2",
        suite_name="flowguard-agent-skill-suite",
        inventory_hash="INVENTORY",
        semantic_hash="SEMANTIC",
        declared_member_ids=("target",),
        discovered_member_ids=("target",),
        members=(member,),
        findings=(),
    )
    compiler = ContractCompileReport(
        root=str(root.resolve()),
        mode="check",
        member_ids=("target",),
        contract_hashes={"target": "CONTRACT"},
        route_registry_hash="ROUTES",
    )
    return inventory, compiler


def test_light_miss_is_read_only_and_starts_no_producer(tmp_path: Path):
    inventory, compiler = _fixture(tmp_path)
    with (
        patch.object(suite, "validate_skill_suite", return_value=inventory) as validate,
        patch.object(suite, "compile_skill_suite", return_value=compiler) as compile_suite,
    ):
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "miss_not_written"
    assert validate.call_count == 1
    assert compile_suite.call_count == 1
    assert not (tmp_path / ".flowguard" / "work" / "flowguard" / "light-suite-index.json").exists()


def test_light_hit_reuses_cache_without_refresh_or_write(tmp_path: Path):
    inventory, compiler = _fixture(tmp_path)
    with patch.object(suite, "validate_skill_suite", return_value=inventory), patch.object(
        suite, "compile_skill_suite", return_value=compiler
    ):
        suite.run_light_suite(tmp_path, allow_cache_write=True)
    with patch.object(suite, "validate_skill_suite") as validate, patch.object(
        suite, "compile_skill_suite"
    ) as compile_suite:
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "hit"
    validate.assert_not_called()
    compile_suite.assert_not_called()


def test_corrupt_light_cache_is_not_authority_and_default_run_does_not_repair_it(tmp_path: Path):
    inventory, compiler = _fixture(tmp_path)
    with patch.object(suite, "validate_skill_suite", return_value=inventory), patch.object(
        suite, "compile_skill_suite", return_value=compiler
    ):
        suite.run_light_suite(tmp_path, allow_cache_write=True)
    cache = tmp_path / ".flowguard" / "work" / "flowguard" / "light-suite-index.json"
    cache.write_text("{corrupt\n", encoding="utf-8")
    with patch.object(suite, "validate_skill_suite", return_value=inventory), patch.object(
        suite, "compile_skill_suite", return_value=compiler
    ):
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "miss_not_written"
    assert cache.read_text(encoding="utf-8") == "{corrupt\n"


def test_light_budget_blocks_without_escalating_to_affected_or_full(tmp_path: Path):
    (tmp_path / ".flowguard").mkdir()
    with patch.object(suite, "validate_skill_suite") as validate, patch.object(
        suite, "compile_skill_suite"
    ) as compile_suite:
        result = suite.run_light_suite(tmp_path, operation_budget=0)
    assert result["status"] == "blocked"
    assert any(
        blocker.startswith("light_suite_operation_budget_exceeded:")
        for blocker in result["blockers"]
    )
    validate.assert_not_called()
    compile_suite.assert_not_called()


@pytest.mark.parametrize("damage", ("", "missing", "foreign_root", "content_changed"))
def test_selected_boundary_contract_uses_logical_path_and_exact_cached_identity(tmp_path, damage):
    import flowguard.model_authority_store as store
    from flowguard.model_authority import canonical_fingerprint
    from contextlib import nullcontext
    model = tmp_path / "alpha.py"; model.write_bytes(b"alpha\n")
    runner = tmp_path / "run_alpha.py"; runner.write_bytes(b"run-alpha\n")
    body = {"contract_id": "boundary-contract:finite", "scope": "independent finite reader test"}
    fingerprint = canonical_fingerprint(body)
    path = store._artifact_path(tmp_path, "boundary-contracts", fingerprint)
    path.parent.mkdir(parents=True)
    raw = json.dumps({**body, "fingerprint": fingerprint}).encode("utf-8")
    path.write_bytes(raw)
    alpha = SimpleNamespace(logical_model_id="alpha", fingerprint=canonical_fingerprint("alpha"),
        model_path="alpha.py", model_sha256="sha256:"+hashlib.sha256(model.read_bytes()).hexdigest(),
        runner_path="run_alpha.py", runner_sha256="sha256:"+hashlib.sha256(runner.read_bytes()).hexdigest(), inputs=())
    endpoint = SimpleNamespace(endpoint_kind="boundary_contract", endpoint_id=body["contract_id"], fingerprint=fingerprint)
    snapshot = SimpleNamespace(fingerprint=canonical_fingerprint("snapshot"), subject_revision="finite-reader",
        unresolved_gap_ids=(), model_instances=(alpha,), relations=(), owner_artifact_refs=(endpoint,))
    override = nullcontext()
    if damage == "missing": path.unlink()
    elif damage == "content_changed":
        path.write_bytes(json.dumps({**body, "scope": "changed", "fingerprint": fingerprint}).encode("utf-8"))
    elif damage == "foreign_root":
        foreign = tmp_path.parent / (tmp_path.name + "-foreign") / path.name
        foreign.parent.mkdir(); foreign.write_bytes(raw)
        override = patch.object(store, "_artifact_path", return_value=foreign)
    context = store._SelectedReadContext(tmp_path.resolve())
    with override, patch.object(store, "_windows_io_path", wraps=store._windows_io_path) as io_path, \
            patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("no owner execution")):
        result = store.read_selected_model_closure(tmp_path, selected_model_ids=("alpha",),
            snapshot=snapshot, read_context=context)
    # Windows I/O spellings must not participate in logical relative-path joins.
    io_path.assert_not_called()
    if damage:
        assert result.selected_source_currentness == "stale"
        assert any(row["code"] == "selected_contract_unavailable" for row in result.stale_obligation_details)
        if damage == "foreign_root":
            assert "escapes project root" in result.stale_obligation_details[0]["message"]
    else:
        relative = path.relative_to(tmp_path).as_posix()
        assert result.selected_source_currentness == "current" and not result.stale_obligations
        assert result.selected_contract_paths == (relative,)
        assert context.payloads[relative] == raw and context.read_counts[relative] == 1
        assert context.artifact_bytes(relative) == raw and context.read_counts[relative] == 1
    assert result.producer_count == result.write_count == 0


def test_selected_model_closure_is_read_only_and_deduplicates_shared_input(tmp_path: Path):
    def write(relative: str, payload: bytes) -> Path:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def sha(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    shared = write(".flowguard/inputs/shared.json", b"{}\n")
    alpha_model = write(".flowguard/models/alpha.py", b"alpha\n")
    alpha_runner = write(".flowguard/runners/alpha.py", b"run-alpha\n")
    beta_model = write(".flowguard/models/beta.py", b"beta\n")
    beta_runner = write(".flowguard/runners/beta.py", b"run-beta\n")

    def instance(model_id: str, model_path: Path, runner_path: Path):
        return SimpleNamespace(
            logical_model_id=model_id,
            model_kind="state_machine",
            model_path=model_path.relative_to(tmp_path).as_posix(),
            model_sha256=sha(model_path),
            runner_path=runner_path.relative_to(tmp_path).as_posix(),
            runner_sha256=sha(runner_path),
            fingerprint=f"sha256:{model_id}",
            purpose_closure_fingerprint=f"sha256:purpose-{model_id}",
            inputs=(
                SimpleNamespace(
                    path=shared.relative_to(tmp_path).as_posix(),
                    sha256=sha(shared),
                ),
            ),
        )

    alpha = instance("alpha", alpha_model, alpha_runner)
    beta = instance("beta", beta_model, beta_runner)
    result = read_selected_model_closure(
        tmp_path,
        selected_model_ids=("alpha", "beta"),
        snapshot=SimpleNamespace(
            fingerprint="sha256:snapshot",
            subject_revision="revision:test",
            unresolved_gap_ids=(),
            model_instances=(alpha, beta),
            relations=(),
        ),
    )

    assert result.authority_integrity == "pass"
    assert result.selected_source_currentness == "current"
    assert result.execution_evidence_status == "not_run"
    serialized = result.to_dict()
    assert "selected_currentness" not in serialized
    assert "execution_status" not in serialized
    assert "as_of_map" not in serialized
    assert serialized["selected_source_currentness"] == "current"
    assert serialized["execution_evidence_status"] == "not_run"
    assert serialized["as_of"] == dict(result.as_of)
    assert dict(result.read_counts)[shared.relative_to(tmp_path).as_posix()] == 1
    assert result.producer_count == 0
    assert result.write_count == 0


def test_bounded_read_page_paginates_large_input_inventory_without_duplicates():
    base_payload = {
        "operation": "read",
        "status": "pass",
        "target_id": "flowguard",
        "requested_model_ids": ["alpha"],
        "selected_model_ids": ["alpha"],
        "as_of": {"authority_head_fingerprint": "sha256:" + "a" * 64},
        "authority_integrity": "pass",
        "selected_source_currentness": "current",
        "execution_evidence_status": "not_run",
        "required_count": 0,
        "run_count": 0,
        "reused_count": 0,
        "producer_count": 0,
        "write_count": 0,
        "stale_obligations": [],
        "blockers": [],
        "claim_boundary": "bounded selected projection read",
    }
    input_paths = [
        f".flowguard/inputs/{index:03d}-{'x' * 80}.json"
        for index in range(120)
    ]
    compact_map = {
        "models": [
            {
                "model_id": "alpha",
                "model_path": ".flowguard/models/alpha.py",
                "runner_path": ".flowguard/runners/alpha.py",
                "input_paths": input_paths,
            }
        ],
        "intents": [],
        "relations": [],
        "boundary_nodes": [],
    }
    head_fingerprint = "sha256:" + "b" * 64
    cursor = None
    first_cursor = None
    seen: list[str] = []
    pages = 0
    while True:
        page = _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor=cursor,
        )
        encoded = json.dumps(
            page, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        assert len(encoded) + 1 <= 8192
        rows = page["map"]["models"]
        assert len(rows) == 1
        seen.extend(rows[0]["input_paths"])
        pages += 1
        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        assert next_cursor != cursor
        if first_cursor is None:
            first_cursor = next_cursor
        cursor = next_cursor
        assert pages < 120

    assert pages > 1
    assert seen == input_paths
    assert len(seen) == len(set(seen)) == 120

    assert first_cursor is not None
    with pytest.raises(ValueError, match="another authority head"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint="sha256:" + "c" * 64,
            scope=("alpha",),
            cursor=first_cursor,
        )
    with pytest.raises(ValueError, match="another authority head"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("beta",),
            cursor=first_cursor,
        )
    with pytest.raises(ValueError, match="read cursor is invalid"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor="not-a-cursor",
        )


@pytest.mark.parametrize("stale_count", [184, 416, 515])
def test_bounded_read_page_paginates_stale_obligations_without_loss_or_duplicates(stale_count):
    stale_obligations = [
        f"selected_source_stale:.flowguard/models/owners/{index:03d}-{'x' * 28}.py"
        for index in range(stale_count)
    ]
    base_payload = {
        "operation": "read",
        "status": "pass",
        "target_id": "flowguard",
        "requested_model_ids": ["alpha"],
        "selected_model_ids": ["alpha"],
        "as_of": {"authority_head_fingerprint": "sha256:" + "a" * 64},
        "authority_integrity": "pass",
        "selected_source_currentness": "stale",
        "execution_evidence_status": "not_run",
        "required_count": 0,
        "run_count": 0,
        "reused_count": 0,
        "producer_count": 0,
        "write_count": 0,
        "stale_obligations": stale_obligations,
        "blockers": [],
        "claim_boundary": "bounded selected projection read",
    }
    input_paths = [
        f".flowguard/inputs/{index:03d}-{'y' * 80}.json"
        for index in range(120)
    ]
    compact_map = {
        "models": [
            {
                "model_id": "alpha",
                "model_path": ".flowguard/models/alpha.py",
                "runner_path": ".flowguard/runners/alpha.py",
                "input_paths": input_paths,
            }
        ],
        "intents": [],
        "relations": [],
        "boundary_nodes": [],
    }
    head_fingerprint = "sha256:" + "b" * 64
    cursor = None
    first_cursor = None
    seen_stale: list[str] = []
    seen_paths: list[str] = []
    pages = 0
    while True:
        page = _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor=cursor,
        )
        encoded = json.dumps(
            page, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        assert len(encoded) + 1 <= 8192
        assert page["authority_integrity"] == "pass"
        assert page["producer_count"] == 0
        assert page["write_count"] == 0
        assert page["page"]["stale_offset"] == len(seen_stale)
        seen_stale.extend(page["stale_obligations"])
        for row in page["map"]["models"]:
            seen_paths.extend(row["input_paths"])
        pages += 1
        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        assert next_cursor != cursor
        if first_cursor is None:
            first_cursor = next_cursor
        cursor = next_cursor
        assert pages < stale_count

    assert len(json.dumps(stale_obligations, separators=(",", ":")).encode("utf-8")) > 8192
    assert pages > 1
    assert seen_stale == stale_obligations
    assert len(seen_stale) == len(set(seen_stale)) == stale_count
    assert seen_paths == input_paths
    assert len(seen_paths) == len(set(seen_paths)) == len(input_paths)
    assert first_cursor is not None

    cursor_payload = json.loads(
        base64.urlsafe_b64decode(first_cursor + "=" * (-len(first_cursor) % 4))
    )
    cursor_payload["stale_offset"] += 1
    mutated_cursor = base64.urlsafe_b64encode(
        json.dumps(
            cursor_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii").rstrip("=")
    with pytest.raises(ValueError, match="read cursor integrity check failed"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor=mutated_cursor,
        )

    negative_cursor = _read_cursor_token(
        head_fingerprint,
        ("alpha",),
        0,
        0,
        stale_offset=-1,
    )
    with pytest.raises(ValueError, match="read cursor position is invalid"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor=negative_cursor,
        )

    out_of_range_cursor = _read_cursor_token(
        head_fingerprint,
        ("alpha",),
        0,
        0,
        stale_offset=stale_count + 1,
    )
    with pytest.raises(ValueError, match="stale-obligation offset is outside"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor=out_of_range_cursor,
        )


from test_functional_task_context import functional_case

def _r9_growth_public_fixture(functional_case):
    from test_functional_task_context import _r9_prepare_task, _r9_run_task_cli
    root, _, _ = functional_case
    changes = [{"kind": "add", "path": "src/w3.py", "previous_path": ""},
               {"kind": "delete", "path": "src/deleted_unknown.py", "previous_path": ""}]
    _, output = _r9_prepare_task(functional_case, changes=changes)
    (root / "src/w3.py").write_text("def newly_observed():\n    return 3\n", encoding="utf-8")
    produced = _r9_run_task_cli(root, output)
    assert produced["status"] == "blocked" and produced.get("task_context_ref"), produced
    return root, produced


def test_r9_public_growth_batch_consumes_one_original_observation_without_reprojection(functional_case, capsys):
    import flowguard.model_authority_store as store
    from flowguard.__main__ import main
    root, produced = _r9_growth_public_fixture(functional_case)
    request_path = root / ".flowguard/evidence/r9-public-read-request.json"
    request_path.write_text(json.dumps({"operation": "read", "target_id": "flowguard",
        "scope": ["alpha", "beta"], "task_context": produced["task_context_ref"], "read_batch": True}), encoding="utf-8")
    contexts = []
    constructor = store._SelectedReadContext
    def capture_context(*args, **kwargs):
        actual = constructor(*args, **kwargs)
        contexts.append(actual)
        return actual
    with patch.object(store, "_SelectedReadContext", side_effect=capture_context), \
            patch.object(store, "read_selected_model_projection", wraps=store.read_selected_model_projection) as projection, \
            patch.object(store, "verify_selected_read_observation", wraps=store.verify_selected_read_observation) as guard, \
            patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read must not produce")), \
            patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read must not execute")):
        exit_code = main(["read", "--root", str(root), "--request", str(request_path), "--json"])
    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "pass" and result["producer_count"] == result["write_count"] == 0
    assert projection.call_count == guard.call_count == 1
    assert len(contexts) == 1
    assert contexts[0].read_counts["src/w3.py"] == 1
    assert "src/deleted_unknown.py" in contexts[0].missing_paths
    report = json.loads((root / produced["report_refs"]["growth"]["path"]).read_text(encoding="utf-8"))
    assert [row for page in result["pages"] for row in page["growth_gaps"]] == report["growth_gaps"]
    assert [path for page in result["pages"] for path in page["checked_observed_paths"]] == report["checked_observed_paths"]
    for page in result["pages"]:
        assert len((json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")) <= 8192


@pytest.mark.parametrize("damage", ("wrong_hash", "foreign_task", "present_drift", "missing_drift", "not_observed"))
def test_r9_growth_ref_rejects_wrong_hash_foreign_task_drift_and_fake_selected_paths(functional_case, damage):
    from flowguard.__main__ import _read_operation
    from flowguard.functional_read import functional_task_growth_reference, read_root_reference
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.model_authority import canonical_fingerprint
    from test_functional_read import _r9_aliased_reference
    root, _, original = functional_case
    if damage == "not_observed":
        read = _read_operation(root, {"operation": "read", "target_id": "flowguard",
            "scope": ["alpha", "beta"], "task_context": original["task_context_ref"], "read_batch": True}, {})
        assert read["status"] == "pass", read
        assert all(page["checked_observed_paths"] == [] and page["live_unregistered_file_detection"] == "NOT_OBSERVED"
                   for page in read["pages"])
        return
    root, produced = _r9_growth_public_fixture(functional_case)
    ref = functional_task_growth_reference(repository_root=root,
        task_context_ref=produced["task_context_ref"], read_context=_SelectedReadContext(root))
    if damage == "wrong_hash":
        ref = dict(ref, sha256="0" * 64)
    elif damage == "foreign_task":
        doc = read_root_reference(root, ref)
        doc["task_id"] = "task:foreign"
        doc["observation_fingerprint"] = canonical_fingerprint({key: value for key, value in doc.items()
                                                              if key != "observation_fingerprint"})
        ref = _r9_aliased_reference(root, ".flowguard/evidence/task-contexts/foreign-growth.json", doc)
    elif damage == "present_drift":
        (root / "src/w3.py").write_text("def changed_after_observation():\n    return 9\n", encoding="utf-8")
    else:
        (root / "src/deleted_unknown.py").write_text("def appeared_after_observation():\n    return 0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        _read_operation(root, {"operation": "read", "target_id": "flowguard",
            "scope": ["alpha", "beta"], "growth_observation": ref, "read_batch": True}, {})


def test_r9_growth_gap_closes_only_with_current_native_bound_finite_inventory(functional_case):
    from dataclasses import replace
    from flowguard.functional_task_context import _current_selected_state, _finite_native_material
    from flowguard.functional_read import read_root_reference
    from flowguard.model_authority_store import _SelectedReadContext, _observe_growth_paths
    root, _, produced = functional_case
    doc = read_root_reference(root, produced["task_context_ref"])
    context = _SelectedReadContext(root)
    state, _, _, _, _ = _current_selected_state(root, "alpha", context, required_model_ids=("beta",))
    material = _finite_native_material(root, state, doc["native_owner_receipt_refs"], context)
    assert _observe_growth_paths(context, ("src/alpha.py",))["growth_gaps"] == ()
    untrusted = _SelectedReadContext(root)
    untrusted.declared_scopes = dict(context.declared_scopes)
    assert _observe_growth_paths(untrusted, ("src/alpha.py",))["growth_gaps"], "declared current flag cannot authenticate native scope"
    inventory, report = material["implementation_inventory"], material["binding_report"]
    excluded = replace(inventory, file_dispositions=tuple(
        replace(row, disposition="scoped_out", reason="finite explicitly excluded test member")
        if row.path == "src/alpha.py" else row for row in inventory.file_dispositions))
    forged = _SelectedReadContext(root)
    forged.declared_scopes[excluded.fingerprint] = (excluded, report)
    forged.authenticated_scopes[excluded.fingerprint] = (excluded, report)
    assert _observe_growth_paths(forged, ("src/alpha.py",))["growth_gaps"], "scoped_out may not masquerade as modeled"
    # Current cache becomes stale only at the independent end guard.
    from flowguard.model_authority_store import freeze_selected_read_observation, verify_selected_read_observation
    before = freeze_selected_read_observation(context)
    (root / "src/alpha.py").write_text("def classify(value):\n    return 'changed'\n", encoding="utf-8")
    assert not verify_selected_read_observation(before).ok


def _r9_recorded_generation125_wide_transport_fixture():
    """Reproduce the real 54-model metadata/goal shape; no authority simulation."""
    import copy
    scope = ('adversarial_scenario_synthesis',
     'ai_entry_surface_reduction',
     'ai_route_handoffs',
     'architecture_reduction',
     'authoritative_model_system',
     'behavior_commitment_ledger',
     'bounded_system_composition_benchmark',
     'code_boundary_conformance',
     'codex_skill_satellites',
     'compositional_verification_kernel',
     'contract_source_audit',
     'default_replacement_field_lifecycle',
     'development_process_flow',
     'development_process_strategy',
     'evidence_storage_lifecycle',
     'existing_model_preflight',
     'field_prompt_reduction',
     'flowguard_closure_contract',
     'guard_closure_contract',
     'guidance_compression',
     'harden_ui_content_visibility_validation',
     'harden_ui_real_surface_validation',
     'hierarchical_model_mesh',
     'implementation_blueprint',
     'maintenance_obligation_memory',
     'mesh_target_split_derivation',
     'minimum_valuable_model_entry',
     'model_impact_freshness_gate',
     'model_maturation_loop',
     'model_mesh_closure_model',
     'model_miss_review',
     'model_test_code_alignment',
     'model_topology_hazard_review',
     'model_visibility',
     'plan_detailing_compiler',
     'primary_path_authority',
     'problem_corpus_coverage',
     'project_adoption_version_gate',
     'python_function_state_verification',
     'runtime_gateway_adoption',
     'runtime_path_evidence',
     'self_maintenance_mesh',
     'skill_kernel_modularization',
     'state_closure_gate',
     'structure_refactor_mesh',
     'task_coverage_demand',
     'task_local_prediction_replay',
     'template_public_release',
     'test_evidence_mesh',
     'ui_flow_structure_skill',
     'ui_human_operability_gate',
     'user_facing_model_diagrams',
     'validation_evidence_gates',
     'work_context')
    base = {'architecture': {'architecture_confidence': 'scoped',
                      'effective_intent_view_fingerprint': 'sha256:fdf6b32462ff638e3b172f2fab3de3e07d7ef4684cb67a3d8f7708c860503a58',
                      'head_fingerprint': 'sha256:9f609838eb21826e03bceb3c1a00bc4be4b5d04246e53d16ae9d252a24c790bf',
                      'improvement_pointers': [],
                      'objective_refs': [{'contribution_id': 'current-design:snapshot-r9-064:authoritative_model_system:3',
                                          'objective': {'applicable_input_class_ids': ['task:selected_current'],
                                                        'constraint_kind': 'functional_obligations',
                                                        'constraint_values': {'native_case_pairs': [{'owner_id': 'model:authoritative_model_system',
                                                                                                     'satisfied_observed_status': 'ok',
                                                                                                     'source_case_id': 'native-scenario:authoritative_model_system:r8_public_task_context_read'}],
                                                                              'required_code_contract_ids': ['code-contract:r8:public-functional-read'],
                                                                              'required_obligation_ids': ['obligation:r8:public_read_consumes_verified_task_context']},
                                                        'model_ids': ['authoritative_model_system'],
                                                        'native_owner_id': 'model:authoritative_model_system',
                                                        'objective_id': 'objective:r8:public_task_context_is_readable',
                                                        'protected_failure_ids': ['failure:authoritative_model_system:frozen_scope_not_authenticated'],
                                                        'required': True,
                                                        'responsibility_ids': ['responsibility:r8:public-functional-read']},
                                          'source_fingerprint': 'sha256:6be13d67f90c3c0068b340d938d3a54b022542ae215c6d30a0ba3fa43271eea6',
                                          'source_ref': 'openspec/specs/task-aware-functional-map/spec.md'},
                                         {'contribution_id': 'current-design:snapshot-r9-064:authoritative_model_system:3',
                                          'objective': {'applicable_input_class_ids': ['planner:one_changed_owner'],
                                                        'constraint_kind': 'functional_obligations',
                                                        'constraint_values': {'native_case_pairs': [{'owner_id': 'model:authoritative_model_system',
                                                                                                     'satisfied_observed_status': 'ok',
                                                                                                     'source_case_id': 'native-scenario:authoritative_model_system:r8_affected_owner_selection'}],
                                                                              'required_code_contract_ids': ['code-contract:r8:affected-native-selection'],
                                                                              'required_obligation_ids': ['obligation:r8:preserve_unaffected_owner_reuse']},
                                                        'model_ids': ['authoritative_model_system'],
                                                        'native_owner_id': 'model:authoritative_model_system',
                                                        'objective_id': 'objective:r8:unaffected_native_owners_are_reused',
                                                        'protected_failure_ids': ['failure:authoritative_model_system:frozen_scope_not_authenticated'],
                                                        'required': True,
                                                        'responsibility_ids': ['responsibility:r8:affected-native-selection']},
                                          'source_fingerprint': 'sha256:6be13d67f90c3c0068b340d938d3a54b022542ae215c6d30a0ba3fa43271eea6',
                                          'source_ref': 'openspec/specs/task-aware-functional-map/spec.md'},
                                         {'contribution_id': 'current-design:snapshot-r9-064:authoritative_model_system:3',
                                          'objective': {'applicable_input_class_ids': ['pointer:accepted_current',
                                                                                       'pointer:wrong_hash_or_head'],
                                                        'constraint_kind': 'functional_obligations',
                                                        'constraint_values': {'native_case_pairs': [{'owner_id': 'model:authoritative_model_system',
                                                                                                     'satisfied_observed_status': 'ok',
                                                                                                     'source_case_id': 'native-scenario:authoritative_model_system:r9_pointer_detail_navigation'}],
                                                                              'required_code_contract_ids': ['code-contract:r9:pointer-detail-navigation'],
                                                                              'required_obligation_ids': ['obligation:r9:resolve_current_action_location']},
                                                        'model_ids': ['authoritative_model_system'],
                                                        'native_owner_id': 'model:authoritative_model_system',
                                                        'objective_id': 'objective:r9:action_location_is_current_and_resolvable',
                                                        'protected_failure_ids': ['r8-functional-actual-checks:r9_pointer_detail_navigation'],
                                                        'required': True,
                                                        'responsibility_ids': ['responsibility:r9:pointer-detail-navigation']},
                                          'source_fingerprint': 'sha256:6be13d67f90c3c0068b340d938d3a54b022542ae215c6d30a0ba3fa43271eea6',
                                          'source_ref': 'openspec/specs/task-aware-functional-map/spec.md'},
                                         {'contribution_id': 'current-design:snapshot-r9-064:authoritative_model_system:3',
                                          'objective': {'applicable_input_class_ids': ['growth:finite_present_and_missing',
                                                                                       'growth:unknown_admission'],
                                                        'constraint_kind': 'functional_obligations',
                                                        'constraint_values': {'native_case_pairs': [{'owner_id': 'model:authoritative_model_system',
                                                                                                     'satisfied_observed_status': 'ok',
                                                                                                     'source_case_id': 'native-scenario:authoritative_model_system:r9_finite_growth_observation'}],
                                                                              'required_code_contract_ids': ['code-contract:r9:finite-growth-observation'],
                                                                              'required_obligation_ids': ['obligation:r9:preserve_finite_growth_and_unknowns']},
                                                        'model_ids': ['authoritative_model_system'],
                                                        'native_owner_id': 'model:authoritative_model_system',
                                                        'objective_id': 'objective:r9:finite_growth_is_original_and_visible',
                                                        'protected_failure_ids': ['r8-functional-actual-checks:r9_finite_growth_observation'],
                                                        'required': True,
                                                        'responsibility_ids': ['responsibility:r9:finite-growth-observation']},
                                          'source_fingerprint': 'sha256:6be13d67f90c3c0068b340d938d3a54b022542ae215c6d30a0ba3fa43271eea6',
                                          'source_ref': 'openspec/specs/task-aware-functional-map/spec.md'},
                                         {'contribution_id': 'current-design:snapshot-r9-064:model_maturation_loop:3',
                                          'objective': {'applicable_input_class_ids': ['comparison:distinct_context',
                                                                                       'comparison:related_overlap'],
                                                        'constraint_kind': 'functional_obligations',
                                                        'constraint_values': {'native_case_pairs': [{'owner_id': 'model:model_maturation_loop',
                                                                                                     'satisfied_observed_status': 'ok',
                                                                                                     'source_case_id': 'case:model_maturation_loop:r8_context_indexed_comparison'}],
                                                                              'required_code_contract_ids': ['code-contract:r8:contextual-architecture-comparison'],
                                                                              'required_obligation_ids': ['obligation:r8:compare_only_context_related_responsibilities']},
                                                        'model_ids': ['model_maturation_loop'],
                                                        'native_owner_id': 'model:model_maturation_loop',
                                                        'objective_id': 'objective:r8:architecture_comparison_uses_scoped_candidates',
                                                        'protected_failure_ids': ['failure:model_maturation_loop:context_remainder_erased'],
                                                        'required': True,
                                                        'responsibility_ids': ['responsibility:r8:contextual-architecture-comparison']},
                                          'source_fingerprint': 'sha256:927b5689afd8e877ea9d8f470e2a99560972705e9d418788ea110dc96c4defda',
                                          'source_ref': 'openspec/specs/context-indexed-architecture-direction/spec.md'},
                                         {'contribution_id': 'current-design:snapshot-r9-064:model_maturation_loop:3',
                                          'objective': {'applicable_input_class_ids': ['normal:current_verified',
                                                                                       'normal:original_diagnostic'],
                                                        'constraint_kind': 'functional_obligations',
                                                        'constraint_values': {'native_case_pairs': [{'owner_id': 'model:model_maturation_loop',
                                                                                                     'satisfied_observed_status': 'ok',
                                                                                                     'source_case_id': 'case:model_maturation_loop:r9_normal_task_context'}],
                                                                              'required_code_contract_ids': ['code-contract:r9:normal-task-context'],
                                                                              'required_obligation_ids': ['obligation:r9:publish_current_task_or_original_gap']},
                                                        'model_ids': ['model_maturation_loop'],
                                                        'native_owner_id': 'model:model_maturation_loop',
                                                        'objective_id': 'objective:r9:normal_task_has_current_result_or_original_gap',
                                                        'protected_failure_ids': ['r8-functional-actual-checks:r9_normal_task_context'],
                                                        'required': True,
                                                        'responsibility_ids': ['responsibility:r9:normal-task-context']},
                                          'source_fingerprint': 'sha256:927b5689afd8e877ea9d8f470e2a99560972705e9d418788ea110dc96c4defda',
                                          'source_ref': 'openspec/specs/context-indexed-architecture-direction/spec.md'}],
                      'observation_gap_ids': [],
                      'read_index_fingerprint': 'sha256:fa62b60af8ca86475d88aab6252e82c88c9c780402dc836dcfbda89ace27e3ad',
                      'revision_set_fingerprint': 'sha256:c27569d3c3782d8017d3b10f1f52c31bef719d08c1c6b40b5268a53e927d23c8',
                      'schema': 'flowguard.architecture_read_projection.v1',
                      'scope_proof_refs': [],
                      'snapshot_fingerprint': 'sha256:e184c7e325edf3376b0b92a836f0ad41f492eaa91010a93ab6de7dadc6ef12ed',
                      'suggestion_refs': [],
                      'summary': {'action': {'action_target_count': 0,
                                             'detail_refs': [],
                                             'next_owner_ids': [],
                                             'pointer_ids': []},
                                  'current': {'behavior_model_count': 43,
                                              'functional_model_count': 0,
                                              'native_check_count': 11,
                                              'responsibility_count': 6,
                                              'selected_model_count': 54},
                                  'gap': {'growth_gap_ids': [],
                                          'observation_gap_ids': [],
                                          'task_first_gap_ref': None},
                                  'scope': {'claim_scope': 'finite_selected_models',
                                            'deepest_proven_layer': 'unknown',
                                            'live_unregistered_file_detection': 'NOT_OBSERVED',
                                            'scoped_out_surface_count': 0,
                                            'unknown_surface_count': 0},
                                  'target': ['objective:r8:architecture_comparison_uses_scoped_candidates',
                                             'objective:r8:public_task_context_is_readable',
                                             'objective:r8:unaffected_native_owners_are_reused',
                                             'objective:r9:action_location_is_current_and_resolvable',
                                             'objective:r9:finite_growth_is_original_and_visible',
                                             'objective:r9:normal_task_has_current_result_or_original_gap']}},
     'as_of': {'accepted_revision_set_fingerprint': 'sha256:c27569d3c3782d8017d3b10f1f52c31bef719d08c1c6b40b5268a53e927d23c8',
               'authority_head_fingerprint': 'sha256:9f609838eb21826e03bceb3c1a00bc4be4b5d04246e53d16ae9d252a24c790bf',
               'read_projection_index_fingerprint': 'sha256:fa62b60af8ca86475d88aab6252e82c88c9c780402dc836dcfbda89ace27e3ad',
               'snapshot_fingerprint': 'sha256:e184c7e325edf3376b0b92a836f0ad41f492eaa91010a93ab6de7dadc6ef12ed',
               'subject_revision': 'source-inventory:d79ed1bcb32732b9c36e09eaf803f5cbacb724e4eeb14eaee4d604aa7ba2d675'},
     'authority_integrity': 'pass',
     'blockers': [],
     'checked_observed_paths': [],
     'claim_boundary': 'This is an as-of read of the selected accepted projection. It does not execute, '
                       'accept, install, or publish.',
     'execution_evidence_status': 'not_run',
     'growth_gaps': [],
     'live_unregistered_file_detection': 'NOT_OBSERVED',
     'observation_fingerprint': '',
     'operation': 'read',
     'producer_count': 0,
     'required_count': 0,
     'reused_count': 0,
     'run_count': 0,
     'selected_source_currentness': 'current',
     'stale_obligations': [],
     'status': 'pass',
     'target_id': 'flowguard',
     'write_count': 0}
    scope_prototype = {'action_count': 0,
     'claim_scope': 'declared_model',
     'detail_evidence_fingerprint': 'sha256:0708d0ac6eb76b3a11baa994c1c857f9d91fe0f925ccc77207c520b5e8d1a169',
     'detail_ref': {'path': '.flowguard/models/authority/path-quality-details/0708d0ac6eb76b3a11baa994c1c857f9d91fe0f925ccc77207c520b5e8d1a169.json',
                    'sha256': 'ef5c17a5fee39f48aa52fa0838a133ead8f9ed30498fb16034d26eacd45877a2'},
     'gap_count': 0,
     'graph_scope': 'model_behavior',
     'model_id': 'adversarial_scenario_synthesis',
     'responsibility_count': 0,
     'target_count': 0,
     'understanding_status': 'behavior_model_only'}
    specialized_scopes = {'authoritative_model_system': {'graph_scope': 'model_behavior',
                                    'responsibility_count': 4,
                                    'target_count': 4,
                                    'understanding_status': 'behavior_model_only'},
     'behavior_commitment_ledger': {'graph_scope': 'native_check_contract',
                                    'responsibility_count': 0,
                                    'target_count': 0,
                                    'understanding_status': 'native_check_only'},
     'code_boundary_conformance': {'graph_scope': 'native_check_contract',
                                   'responsibility_count': 0,
                                   'target_count': 0,
                                   'understanding_status': 'native_check_only'},
     'contract_source_audit': {'graph_scope': 'native_check_contract',
                               'responsibility_count': 0,
                               'target_count': 0,
                               'understanding_status': 'native_check_only'},
     'evidence_storage_lifecycle': {'graph_scope': 'native_check_contract',
                                    'responsibility_count': 0,
                                    'target_count': 0,
                                    'understanding_status': 'native_check_only'},
     'harden_ui_content_visibility_validation': {'graph_scope': 'native_check_contract',
                                                 'responsibility_count': 0,
                                                 'target_count': 0,
                                                 'understanding_status': 'native_check_only'},
     'model_maturation_loop': {'graph_scope': 'model_behavior',
                               'responsibility_count': 2,
                               'target_count': 2,
                               'understanding_status': 'behavior_model_only'},
     'model_test_code_alignment': {'graph_scope': 'native_check_contract',
                                   'responsibility_count': 0,
                                   'target_count': 0,
                                   'understanding_status': 'native_check_only'},
     'plan_detailing_compiler': {'graph_scope': 'native_check_contract',
                                 'responsibility_count': 0,
                                 'target_count': 0,
                                 'understanding_status': 'native_check_only'},
     'primary_path_authority': {'graph_scope': 'native_check_contract',
                                'responsibility_count': 0,
                                'target_count': 0,
                                'understanding_status': 'native_check_only'},
     'problem_corpus_coverage': {'graph_scope': 'native_check_contract',
                                 'responsibility_count': 0,
                                 'target_count': 0,
                                 'understanding_status': 'native_check_only'},
     'python_function_state_verification': {'graph_scope': 'native_check_contract',
                                            'responsibility_count': 0,
                                            'target_count': 0,
                                            'understanding_status': 'native_check_only'},
     'runtime_gateway_adoption': {'graph_scope': 'native_check_contract',
                                  'responsibility_count': 0,
                                  'target_count': 0,
                                  'understanding_status': 'native_check_only'}}
    findings = [{'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:activation_reasons',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:blocked',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:decision_revision',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:dependency_order_violated',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:diagnostic_boundary',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:diagnostic_evidence_current',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:dominated_caller_selection',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:global_optimum_claimed',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:hard_blocker_visible',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:inactive',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:incomplete_process_cost_vector',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:non_equivalent_selected',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:repair_closed_without_revalidation',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:repair_group_ready',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:selected',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:selected_execution_mode',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:stale_decision_reused',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:unowned_repair_selected',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:unrelated_findings_grouped',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:unresolved_non_dominated_boundary',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:unsafe_parallel_selected',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:a54b9d749e0de32a67fac5f87d4e1d026ca686763de7008df3d4347296d5b70b',
      'finding_id': 'behavior_irrelevant_field:field:development_process_strategy:state:unsupported_minimum_claimed',
      'model_id': 'development_process_strategy'},
     {'detail_evidence_fingerprint': 'sha256:0a890448e6e7a9359d383577780284d6b7e77ea7a4b40e3cd36b8bc62bddb04f',
      'finding_id': 'behavior_irrelevant_field:field:work_context:state:behavior_admitted',
      'model_id': 'work_context'},
     {'detail_evidence_fingerprint': 'sha256:0a890448e6e7a9359d383577780284d6b7e77ea7a4b40e3cd36b8bc62bddb04f',
      'finding_id': 'behavior_irrelevant_field:field:work_context:state:blocked',
      'model_id': 'work_context'},
     {'detail_evidence_fingerprint': 'sha256:0a890448e6e7a9359d383577780284d6b7e77ea7a4b40e3cd36b8bc62bddb04f',
      'finding_id': 'behavior_irrelevant_field:field:work_context:state:context_projected',
      'model_id': 'work_context'},
     {'detail_evidence_fingerprint': 'sha256:0a890448e6e7a9359d383577780284d6b7e77ea7a4b40e3cd36b8bc62bddb04f',
      'finding_id': 'behavior_irrelevant_field:field:work_context:state:intent_contributions_projected',
      'model_id': 'work_context'}]
    base["requested_model_ids"] = list(scope)
    base["selected_model_ids"] = list(scope)
    architecture = base["architecture"]
    architecture["requested_model_ids"] = list(scope)
    architecture["facts_scope"] = [
        dict(copy.deepcopy(scope_prototype), model_id=model_id,
             **specialized_scopes.get(model_id, {})) for model_id in scope
    ]
    architecture["finding_refs"] = findings
    gap_ids = [row["finding_id"] for row in findings]
    architecture["improvement_gap_ids"] = list(gap_ids)
    architecture["summary"]["gap"]["improvement_gap_ids"] = list(gap_ids)
    compact = {
        "models": [{"model_id": model_id,
                    "model_path": ".flowguard/models/owners/" + model_id + "/model.py",
                    "runner_path": ".flowguard/verification/owners/" + model_id + "/run_checks.py",
                    "input_paths": ["flowguard/" + model_id + ".py",
                                    "tests/test_" + model_id + ".py"]}
                   for model_id in scope],
        "intents": [], "relations": [], "boundary_nodes": [],
    }
    return base, compact, scope


def test_r9_generation125_whole_scope_transport_retains_real_goals_and_metadata_once():
    import flowguard.__main__ as entry
    base, compact, scope = _r9_recorded_generation125_wide_transport_fixture()
    encode = lambda value: (json.dumps(value, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")) + "\n").encode("utf-8")
    assert len(scope) == len(compact["models"]) == 54
    assert len(base["architecture"]["objective_refs"]) == 6
    assert len(base["architecture"]["facts_scope"]) == 54
    # This is the metadata density of the actual failed accepted Source read:
    # repeated scope lists leave too little room for a normal 1KB goal record.
    assert len(encode(list(scope))) == 1502
    assert all(1000 < len(encode(row)) < 1200
               for row in base["architecture"]["objective_refs"])
    with patch.object(entry, "_prepare_read_transport", wraps=entry._prepare_read_transport) as prepare:
        prepared = entry._prepare_read_transport(base, compact)
        pages = _assert_lossless_read_pages(
            base, compact, base["as_of"]["authority_head_fingerprint"], scope,
            prepared_transport=prepared)
        assert prepare.call_count == 1
    assert len(pages) > 1
    assert all(len(encode(page)) <= 8192 for page in pages)
    assert all(page["status"] == "pass" and page["producer_count"] == page["write_count"] == 0
               and page["as_of"] == base["as_of"] for page in pages)
    for key in ("requested_model_ids", "selected_model_ids"):
        assert all(page[key] == base[key] for page in pages)
    scalar_architecture = set(base["architecture"]) - {
        "facts_scope", "objective_refs", "finding_refs", "suggestion_refs", "observation_gap_ids",
        "improvement_gap_ids", "improvement_pointers", "scope_proof_refs", "summary", "requested_model_ids"}
    assert all({key: page["architecture"][key] for key in scalar_architecture}
               == {key: base["architecture"][key] for key in scalar_architecture}
               for page in pages)
    assert [model_id for page in pages
            for model_id in page["architecture"]["requested_model_ids"]] == list(scope)
    summary = base["architecture"]["summary"]
    assert all(page["architecture"]["summary"]["gap"]["task_first_gap_ref"]
               == summary["gap"]["task_first_gap_ref"] for page in pages)
    assert all(page["architecture"]["summary"]["action"]["action_target_count"]
               == summary["action"]["action_target_count"] for page in pages)
