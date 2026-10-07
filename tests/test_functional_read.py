"""Finite public reading preserves functional evidence without running owners."""
import hashlib
import json
from unittest.mock import patch

import pytest

from test_functional_task_context import functional_case

def _r9_aliased_reference(root, path, payload):
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    artifact = root / path
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(raw)
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest()}


@pytest.mark.parametrize("terminal", ("external_input", "scope_excluded", "iteration_limit", "progress_stalled"))
def test_r8_maturation_terminal_reasons_are_preserved_in_task_view(functional_case, terminal):
    from dataclasses import replace
    from flowguard import model_maturation
    from flowguard.functional_task_context import produce_functional_task_context
    from flowguard.functional_read import read_root_reference
    from flowguard.__main__ import _read_operation
    from test_functional_task_context import _r9_prepare_task
    names = {"external_input": model_maturation.MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED,
        "scope_excluded": model_maturation.MODEL_MATURATION_DECISION_SCOPE_EXCLUDED,
        "iteration_limit": model_maturation.MODEL_MATURATION_DECISION_ITERATION_LIMIT,
        "progress_stalled": model_maturation.MODEL_MATURATION_DECISION_PROGRESS_STALLED}
    root, _, original = functional_case
    request, output = _r9_prepare_task(functional_case)
    real_review = model_maturation.review_model_maturation_loop
    def finite_non_success(plan):
        actual = real_review(plan)
        return replace(actual, ok=False, decision=names[terminal], terminal_reason=names[terminal],
            confidence="blocked", next_actions=("task-model-maturation:original-" + terminal,))
    # Only a negative domain result is injected. No receipt/Verified object is
    # constructed, and its actual published typed report is independently read.
    with patch.object(model_maturation, "review_model_maturation_loop", finite_non_success), \
            patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("no native reexecution")):
        produced = produce_functional_task_context(repository_root=root, request=request,
            output_directory=output, command="finite-test:r9-original-terminal")
    assert produced["status"] == "blocked" and produced.get("task_context_ref"), produced
    doc = read_root_reference(root, produced["task_context_ref"])
    assert doc["maturation_receipt_ref"] is None and doc["context_kind"] == "diagnostic"
    with patch("flowguard.model_maturation_receipt.publish_model_maturation_receipt", side_effect=AssertionError("read must not publish")):
        result = _read_operation(root, {"operation": "read", "target_id": "flowguard",
            "scope": ["alpha", "beta"], "task_context": produced["task_context_ref"], "read_batch": True}, {})
    assert result["status"] == "pass", result
    view = result["pages"][0]["functional_understanding"]
    for key in ("stopping_disposition", "maturation_decision", "maturation_terminal_reason"):
        assert view[key] == names[terminal]
    assert view["maturation_confidence"] == "blocked"
    assert view["satisfied_outcome_ids"] == []
    assert view["first_gap"] == produced["functional_understanding"]["first_gap"]
    successful = _read_operation(root, {"operation": "read", "target_id": "flowguard",
        "scope": ["alpha", "beta"], "task_context": original["task_context_ref"], "read_batch": True}, {})
    assert successful["pages"][0]["functional_understanding"]["stopping_disposition"] == "model_maturation_closed_for_task"


@pytest.mark.parametrize("damage", ("foreign_head", "stale_input", "forged_closed", "forged_owner", "missing_plane"))
def test_r9_diagnostic_context_rejects_foreign_head_stale_input_and_forged_closed(functional_case, damage):
    from flowguard.functional_task_context import produce_functional_task_context
    from flowguard.functional_read import read_root_reference
    from flowguard.__main__ import _read_operation
    from test_functional_task_context import _r9_prepare_task
    root, _, _ = functional_case
    request, output = _r9_prepare_task(functional_case, requested_outcome_ids=("outcome:r9:actually-missing",))
    produced = produce_functional_task_context(repository_root=root, request=request,
        output_directory=output, command="finite-test:r9-diagnostic-negative")
    assert produced["status"] == "blocked" and produced.get("task_context_ref"), produced
    doc = read_root_reference(root, produced["task_context_ref"])
    diagnostic = read_root_reference(root, doc["diagnostic_ref"])
    if damage == "foreign_head":
        diagnostic["accepted_head_fingerprint"] = "sha256:" + "0" * 64
    elif damage == "forged_closed":
        diagnostic["status"] = "model_maturation_closed_for_task"
        diagnostic["terminal_reason"] = "model_maturation_closed_for_task"
    elif damage == "forged_owner":
        diagnostic["first_gap"]["next_owner_id"] = "caller-invented-owner"
    elif damage == "missing_plane":
        from dataclasses import replace
        from flowguard.functional_read import parse_task_facts
        original_ref = doc["task_facts_ref"]
        facts = parse_task_facts(read_root_reference(root, original_ref))
        incomplete = replace(facts, source_snapshots=tuple(
            row for row in facts.source_snapshots if row.source_plane != "lifecycle"),
            fact_observations=())
        facts_ref = _r9_aliased_reference(root,
            output.relative_to(root).as_posix() + "/incomplete-task-facts.json", incomplete.to_dict())
        doc["task_facts_ref"] = diagnostic["task_facts_ref"] = facts_ref
        diagnostic["input_refs"] = sorted(
            [facts_ref if ref == original_ref else ref for ref in diagnostic["input_refs"]],
            key=lambda ref: ref["path"])
    else:
        facts = read_root_reference(root, doc["task_facts_ref"])
        source = next(row["source_ref"] for row in facts["source_snapshots"] if row["source_plane"] == "request")
        with (root / source).open("ab") as stream:
            stream.write(b"\n")
    doc["diagnostic_ref"] = _r9_aliased_reference(root,
        output.relative_to(root).as_posix() + "/damaged-diagnostic.json", diagnostic)
    ref = _r9_aliased_reference(root, output.relative_to(root).as_posix() + "/damaged-context.json", doc)
    with patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read may not retry")), \
            patch("flowguard.model_maturation_receipt.publish_model_maturation_receipt", side_effect=AssertionError("no diagnostic receipt")):
        result = _read_operation(root, {"operation": "read", "target_id": "flowguard",
            "scope": ["alpha", "beta"], "task_context": ref, "read_batch": True}, {})
    assert result["producer_count"] == result["write_count"] == 0
    view = result["pages"][0]["functional_understanding"]
    assert view["stopping_disposition"] == "needs_evidence"
    assert view["gap_ids"] == ["functional_task_context_invalid"], result
    unknown_fields = (("requested_outcome_count", "requested_outcome_ids"),
        ("satisfied_outcome_count", "satisfied_outcome_ids"),
        ("missing_outcome_count", "missing_outcome_ids"),
        ("required_obligation_count", "required_obligation_ids"),
        ("required_owner_count", "required_owner_ids"))
    for counter, field in unknown_fields:
        assert field not in view, "Invalid context supplies no proven task denominator"
        assert result["pages"][0]["architecture"]["summary"]["denominator"][counter] is None
        assert all(page["understanding_navigation"]["denominator"][counter] is None
                   for page in result["pages"])
    navigation = result["pages"][0]["architecture"]["summary"]["navigation"]
    assert navigation["first_gap"] == view["first_gap"]
    assert navigation["first_gap_state"] == "present"
    assert navigation["stopping_disposition"] == view["stopping_disposition"]
    assert all(page["understanding_transport"]["decision_basis_complete"] is False
               for page in result["pages"])
    assert result["understanding_transport"]["decision_basis_complete"] is False
    if damage == "missing_plane":
        assert "four independent source planes" in view["first_gap"]["reason"]


@pytest.mark.parametrize("replacement", ("route_wrapper", "foreign_model"))
def test_r8_responsibility_proof_consumes_model_leaf_not_route_wrapper(functional_case, replacement):
    from flowguard.functional_read import read_root_reference
    from flowguard.__main__ import _read_operation
    from flowguard.model_regressions import resolve_current_full_model_regression_parent
    root, _, produced = functional_case
    assert produced["status"] == "pass", produced
    request = {"operation": "read", "target_id": "flowguard", "scope": ["alpha", "beta"], "read_batch": True}
    original = _read_operation(root, dict(request, task_context=produced["task_context_ref"]), {})
    assert original["pages"][0]["functional_understanding"]["stopping_disposition"] == "model_maturation_closed_for_task"
    doc = read_root_reference(root, produced["task_context_ref"])
    leaves = [dict(row) for row in doc["native_owner_receipt_refs"]]
    if replacement == "route_wrapper":
        parent = resolve_current_full_model_regression_parent(root,
            receipt_dir=root / ".flowguard/evidence/model-owner-receipts")
        leaves[0].update(receipt_id=parent.parent_execution_receipt_id,
                        receipt_fingerprint=parent.parent_execution_receipt_fingerprint)
    else:
        leaves[0].update(receipt_id=leaves[1]["receipt_id"],
                        receipt_fingerprint=leaves[1]["receipt_fingerprint"])
    doc["native_owner_receipt_refs"] = leaves
    original_directory = (root / produced["task_context_ref"]["path"]).parent.relative_to(root).as_posix()
    ref = _r9_aliased_reference(root, original_directory + "/wrong-leaf-" + replacement + ".json", doc)
    with patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read native count must be zero")), \
            patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read producer count must be zero")):
        result = _read_operation(root, dict(request, task_context=ref), {})
    assert result["producer_count"] == result["write_count"] == 0
    view = result["pages"][0]["functional_understanding"]
    assert view["gap_ids"] == ["functional_task_context_invalid"], result
    assert "native leaf" in view["first_gap"]["reason"]



def test_r8_task_context_closes_real_outcomes_with_verified_maturation(functional_case):
    from flowguard.__main__ import _read_operation
    root, _, produced = functional_case
    assert produced["status"] == "pass", produced
    with patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read may not run native")), patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read may not produce")):
        result = _read_operation(root, {"operation":"read", "target_id":"flowguard",
            "scope":["alpha", "beta"], "task_context":produced["task_context_ref"], "read_batch":True}, {})
    assert result["status"] == "pass", result
    pages = result.get("pages", [result])
    assert pages[0]["functional_understanding"]["gap_ids"] == [], pages[0]
    assert pages[0]["functional_understanding"]["stopping_disposition"] == "model_maturation_closed_for_task"
    assert result["producer_count"] == result["write_count"] == 0


def test_r8_task_context_first_gap_is_actionable_without_producer(tmp_path):
    from flowguard.functional_read import load_functional_read_context
    from flowguard.model_authority_store import _SelectedReadContext
    with patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("no retry producer")):
        result = load_functional_read_context(repository_root=tmp_path,
            task_context_ref={"path":"missing.json", "sha256":"0"*64},
            selected_read=None, read_context=_SelectedReadContext(tmp_path))
    assert result["stopping_disposition"] == "needs_evidence"
    assert result["first_gap"]["input_ref"] == "missing.json"
    assert result["first_gap"]["next_owner_id"] == "task-model-maturation"
    from flowguard.model_authority_store import _architecture_understanding_summary
    summary = _architecture_understanding_summary(
        {"facts_scope": [], "objective_refs": [], "observation_gap_ids": [],
         "improvement_gap_ids": [], "improvement_pointers": []},
        _SelectedReadContext(tmp_path), selected_model_ids=(),
        functional_understanding=result)
    assert summary["navigation"]["first_gap"] == result["first_gap"]
    assert summary["navigation"]["first_gap_ref"] is None
    assert summary["navigation"]["first_gap_state"] == "present"
    assert summary["navigation"]["next_owner_ids"] == ["task-model-maturation"]
    assert summary["navigation"]["stopping_disposition"] == result["stopping_disposition"]
    for counter, field in (("requested_outcome_count", "requested_outcome_ids"),
                          ("satisfied_outcome_count", "satisfied_outcome_ids"),
                          ("missing_outcome_count", "missing_outcome_ids"),
                          ("required_obligation_count", "required_obligation_ids"),
                          ("required_owner_count", "required_owner_ids")):
        assert field not in result
        assert summary["denominator"][counter] is None


def test_r8_task_context_rejects_unknown_forged_or_unsafe_wire(tmp_path):
    from flowguard.functional_read import (strict_json_bytes, parse_task_facts,
        parse_task_coverage_demand, parse_model_maturation_report, read_root_reference)
    from flowguard.task_coverage_demand import TaskFacts, compile_task_coverage_demand
    from flowguard.model_maturation import ModelMaturationReport
    records = ((parse_task_facts, TaskFacts("task:wire", "read").to_dict()),
               (parse_task_coverage_demand, compile_task_coverage_demand(TaskFacts("task:wire", "read")).to_dict()),
               (parse_model_maturation_report, ModelMaturationReport(False, "task:wire", "blocked", "blocked").to_dict()))
    for parser, actual in records:
        parser(actual)
        changed = dict(actual, invented_verified=True)
        with pytest.raises((ValueError, TypeError)):
            parser(changed)
        typed = next(key for key,value in actual.items() if type(value) is bool or isinstance(value,list))
        for invalid in (1, "false", {}):
            changed = dict(actual); changed[typed] = invalid
            with pytest.raises((ValueError, TypeError)):
                parser(changed)
    for invalid in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
        with pytest.raises(ValueError): strict_json_bytes(invalid)
    for path in ("../outside.json", "C:/outside.json", "a/../outside.json"):
        with pytest.raises((ValueError, OSError)):
            read_root_reference(tmp_path, {"path":path,"sha256":"0"*64})
    document = tmp_path / "wire.json"; document.write_text('{}')
    with pytest.raises(ValueError):
        read_root_reference(tmp_path, {"path":"wire.json", "sha256":"F"*64})


def test_r8_task_cursor_is_bound_and_all_functional_lanes_are_lossless(functional_case):
    from flowguard.__main__ import _read_operation, _compact_read_map
    from flowguard.model_authority_store import _SelectedReadContext
    from flowguard.functional_task_context import _current_selected_state
    root, _, produced = functional_case
    assert produced["status"] == "pass", produced
    request = {"operation":"read", "target_id":"flowguard", "scope":["alpha","beta"],
        "task_context":produced["task_context_ref"]}
    pages, cursors = [], set()
    page = _read_operation(root, request, {})
    while True:
        assert page["status"] == "pass", page
        assert len((json.dumps(page, ensure_ascii=False, sort_keys=True, separators=(",",":")) + "\n").encode("utf-8")) <= 8192
        pages.append(page)
        if page["next_cursor"] is None: break
        assert page["next_cursor"] not in cursors
        cursors.add(page["next_cursor"])
        page = _read_operation(root, dict(request, cursor=page["next_cursor"]), {})
    batch = _read_operation(root, dict(request, read_batch=True), {})
    assert cursors, "This real finite material must exercise pagination and cursor validation"
    assert batch["pages"] == pages
    assert all(page["understanding_transport"]["details_complete"] is False for page in pages)
    assert pages[-1]["next_cursor"] is None
    assert batch["understanding_transport"]["details_complete"] is True
    for kind in ("summary", "functional"):
        assert batch["understanding_transport"][kind + "_record_total"] == pages[0]["understanding_transport"][kind + "_record_total"]
        assert batch["understanding_transport"][kind + "_record_transported_count"] == sum(
            page["understanding_transport"][kind + "_record_transported_count"] for page in pages)
    context = _SelectedReadContext(root)
    _, selected, _, _, _ = _current_selected_state(root, "alpha", context, required_model_ids=("beta",))
    from flowguard.functional_read import load_functional_read_context
    from flowguard.model_authority_store import refresh_architecture_read_understanding
    understanding = load_functional_read_context(repository_root=root,
        task_context_ref=produced["task_context_ref"], selected_read=selected, read_context=context)
    selected = refresh_architecture_read_understanding(selected, context, functional_understanding=understanding)
    expected = _compact_read_map(selected)
    models = {}
    for page in pages:
        for row in page["map"]["models"]:
            if row["model_id"] not in models:
                models[row["model_id"]] = dict(row, input_paths=[])
            assert {key:value for key,value in row.items() if key != "input_paths"} == {key:value for key,value in models[row["model_id"]].items() if key != "input_paths"}
            models[row["model_id"]]["input_paths"].extend(row["input_paths"])
    assert list(models.values()) == expected["models"]
    for lane in ("intents", "relations", "boundary_nodes"):
        actual = [row for page in pages for row in page["map"][lane]]
        assert actual == expected[lane], lane
    for lane in ("facts_scope", "objective_refs", "finding_refs", "suggestion_refs", "observation_gap_ids", "improvement_gap_ids", "improvement_pointers", "scope_proof_refs"):
        assert [row for page in pages for row in page["architecture"][lane]] == selected.architecture[lane], lane
    summary = selected.architecture["summary"]
    assert all(set(page["architecture"]["summary"]) == set(summary) for page in pages)
    for key in ("current", "scope"):
        transported = [page["architecture"]["summary"][key] for page in pages
                       if page["architecture"]["summary"][key]]
        assert transported == [summary[key]], key
    for path in (("target",), ("gap", "observation_gap_ids"),
                 ("gap", "improvement_gap_ids"), ("gap", "growth_gap_ids"),
                 ("action", "pointer_ids"), ("action", "next_owner_ids"),
                 ("action", "detail_refs")):
        actual = [value for page in pages for value in
                  (page["architecture"]["summary"][path[0]] if len(path) == 1
                   else page["architecture"]["summary"][path[0]][path[1]])]
        wanted = summary[path[0]] if len(path) == 1 else summary[path[0]][path[1]]
        assert actual == wanted, path
    for key, value in understanding.items():
        if isinstance(value, list):
            assert [row for page in pages for row in page["functional_understanding"][key]] == value, key
        else:
            assert all(page["functional_understanding"][key] == value for page in pages), key
    # A different valid reference to the same genuine published task is still
    # a different cursor authority. No new native/maturation producer is needed.
    alias = root / ".flowguard/evidence/task-contexts/cursor-reference.json"
    alias.write_bytes((root / produced["task_context_ref"]["path"]).read_bytes())
    different = {"path":alias.relative_to(root).as_posix(), "sha256":hashlib.sha256(alias.read_bytes()).hexdigest()}
    rejection = _read_operation(root, dict(request, task_context=different, cursor=next(iter(cursors))), {})
    assert rejection["status"] == "blocked" and rejection["reason"] == "read_page_invalid", rejection
    forged = dict(produced["task_context_ref"], sha256="0"*64)
    before = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (root / ".flowguard").rglob("*") if path.is_file()}
    with patch("flowguard.model_regressions.run_manifest_regressions", side_effect=AssertionError("read must not execute native")), \
            patch("flowguard.functional_task_context.produce_functional_task_context", side_effect=AssertionError("read must not produce")), \
            patch("flowguard.model_maturation_receipt.publish_model_maturation_receipt", side_effect=AssertionError("read must not publish")):
        rejection = _read_operation(root, dict(request, task_context=forged, cursor=next(iter(cursors))), {})
    assert rejection["status"] == "blocked" and rejection["reason"] == "read_page_invalid", rejection
    assert rejection["blockers"] == ["read_page_invalid"]
    assert rejection["error"] == "read cursor is bound to another authority head or scope"
    assert rejection["map"] == {}
    assert "pages" not in rejection and "next_cursor" not in rejection
    assert all(rejection[key] == 0 for key in ("producer_count", "write_count", "run_count", "reused_count"))
    assert rejection["functional_understanding"] == {
        "task_id": "", "stopping_disposition": "needs_evidence",
        "gap_ids": ["functional_task_context_invalid"],
        "first_gap": {"gap_id": "functional_task_context_invalid", "input_ref": forged["path"],
            "next_owner_id": "task-model-maturation",
            "reason": "functional input raw fingerprint changed: " + forged["path"]},
        "next_actions": ["task-model-maturation:functional_task_context_invalid"],
        "deepest_proven_layer": "unknown",
    }
    after = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in (root / ".flowguard").rglob("*") if path.is_file()}
    assert after == before, "A rejected forged task reference must leave all authority/evidence bytes unchanged"
