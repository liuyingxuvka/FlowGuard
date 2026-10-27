"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_impact_shared_test_binding_and_unknown_helper(impact_project):
    from _fg_helpers import map_impact_of as impact_of
    root, data = impact_project
    data["components"][2]["tests"].append("tests/test_orders.py")
    imp = impact_of(root, data, ["tests/test_orders.py"])
    assert imp.direct == [] and imp.dependents == []
    assert imp.tests == ["tests/test_orders.py"]
    assert imp.model_ids == []
    unknown = impact_of(root, data, [".flowguard/models/owners/unbound/helper.py"])
    assert unknown.blocked and not unknown.models and not unknown.model_ids


@pytest.mark.parametrize("edit", ["comment", "docstring", "code", "untouched"])
@pytest.mark.parametrize("line_endings", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_comment_only_edit_keeps_review_but_selects_no_checks(impact_project, edit, line_endings):
    from _fg_helpers import map_impact_of as impact_of
    from flowguard.map.impact import render_impact
    root, data = impact_project
    path = root / "shop/storage.py"
    text = path.read_text(encoding="utf-8")
    edited = {"comment": text.replace("DB = {}\n", "DB = {}  # in-memory store\n\n"),
              "docstring": '"""Order storage."""\n' + text,
              "code": text.replace("return x", "return x or None"),
              "untouched": text}[edit]
    path.write_bytes(edited.replace("\n", line_endings).encode("utf-8"))
    imp = impact_of(root, data, ["shop/storage.py"], base="HEAD", broad=True)
    assert imp.direct == ["storage"]
    if edit == "comment":
        assert imp.comment_only == ["shop/storage.py"] and "comment-only edits" in render_impact(imp)
        assert imp.dependents == [] and imp.tests == [] and imp.models == []
    else:
        assert imp.comment_only == [] and imp.dependents == ["api", "orders"]
        assert "tests/test_storage.py" in imp.tests and "orders_check" in imp.model_ids










def test_removed_literal_sites_reach_function_selection(tmp_path):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    impact,text=target__target_life_cycle_fixture_helpers('_literal_fixture')['native_case'](tmp_path,'literal')
    assert {'consumer_model','policy'}==set(impact.model_ids)
    assert 'consumer.py:use' in impact.changed_functions
    assert "consumes 'stale'" in text


def test_uncertain_source_broadens_selection(tmp_path):
    from _fg_helpers import map_function_fixture
    impact=map_function_fixture()['native_case'](tmp_path,'removed')
    assert impact.uncertain_files=={'core.py':'a symbol was removed or renamed'}
    assert {'child','importer','other','parent'}==set(impact.model_ids)
    assert impact.whole_test_files==['tests/test_core.py']


def test_missing_selected_model_is_blocked(tmp_path):
    from _fg_helpers import map_function_fixture
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact,render_impact
    from flowguard.map.common import DEFAULT_IGNORE
    data=map_function_fixture()['fixture'](tmp_path)
    impact=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),['.flowguard/models/missing.py'],base='HEAD')
    assert impact.blocked==['.flowguard/models/missing.py: selected model is missing or is not an executable registered model']
    assert 'BLOCKED' in render_impact(impact)
