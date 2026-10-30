"""Tests grouped by their model or native component."""
from __future__ import annotations
import json
import os
import pytest
from pathlib import Path




from _fg_helpers import (
    target__fg403_helpers as _fg403_helpers,
    target__load_map as _load_map,
)

def test_rule_broken_by_old_code_is_an_expected_gap(tmp_path):
    from flowguard.map import target as native
    helpers = _fg403_helpers()
    root = tmp_path
    helpers["make_project"](root, helpers["regular_source"]())
    native.start_target(root, "raise the native answer")
    native.add_to_target(root, "one")
    (root / ".flowguard/target/models/one.py").write_text(helpers["regular_source"](expected=2))
    report = native.check_target(root)
    assert not report.errors and report.todos
    assert "EXPECTED GAP one:" in native.render_target_report(report)
    (root / "native.py").write_text("def value(): return 2\n")
    report = native.check_target(root)
    assert not report.errors and not report.todos
    assert "GAP CLOSED one:" in native.render_target_report(report)
    assert native.promote_target(root) == 0
    assert "model_digests" in _load_map(root)


def test_split_into_child_prints_moved_rules_only():
    result = _fg403_helpers()["native_case"]("move")
    assert "moved rules only: moved (1 from one; no gap expected)" in result["text"]
    assert ">positive (from one)" in str(result["goal"])


def test_recorded_rule_prints_no_gap():
    result = _fg403_helpers()["native_case"]("recorded")
    assert "NO GAP one:" in result["text"] and not result["errors"] and not result["todos"]


def test_no_gap_changed_rule_needs_line(tmp_path):
    from flowguard.map import target as native
    helpers = _fg403_helpers()
    source = helpers["regular_source"](positive=True)
    helpers["make_project"](tmp_path, source)
    native.start_target(tmp_path, "record the revised lower bound")
    native.add_to_target(tmp_path, "one")
    model = tmp_path / ".flowguard/target/models/one.py"
    model.write_text(source.replace('def _positive(s): return s >= 0',
                                    'def _positive(s): return s >= -1').replace('"negative": make(-1)',
                                                                                 '"negative": make(-2)'))
    report = native.check_target(tmp_path)
    assert not report.errors
    assert any(item.code == "rule_changed_without_line" for item in report.todos), report
    assert native.promote_target(tmp_path) == 1
    (tmp_path / ".flowguard/target/PLAN.txt").write_text(
        'changes: one.positive because "The revised lower bound is intentional."\n', encoding="utf-8")
    report = native.check_target(tmp_path)
    assert not report.errors and not report.todos, report
    assert native.promote_target(tmp_path) == 0


def test_missing_bound_test_is_never_a_gap():
    result = _fg403_helpers()["native_case"]("missing_test")
    assert "NO GAP one:" in result["text"] and "EXPECTED GAP" not in result["text"]
    assert not result["todos"]


@pytest.mark.parametrize("case", ["anchor_exception", "engine_exception", "adapter_exception"])
def test_exception_classification(case):
    import runpy
    directory = Path(__file__).parents[1] / ".flowguard"
    helper = directory / "target/models/_gap_cases.py"
    if not helper.exists():
        helper = directory / "models/_gap_cases.py"
    result = runpy.run_path(str(helper))["native_case"](case)
    if case == "anchor_exception":
        assert "EXPECTED GAP one:" in result["text"] and result["todos"] and not result["errors"]
    else:
        assert result["errors"] and "EXPECTED GAP" not in result["text"]
        assert "getattr(report," in result["text"]


def test_shared_rule_tuple_marks_only_changed_names(tmp_path):
    from flowguard.map.facets import target_goal_rules
    from flowguard.map import target as native
    source = _fg403_helpers()["regular_source"](positive=True)
    start = source.index("INVARIANTS = (")
    end = source.index("\nclass Value:", start)
    source = source[:start] + 'RULE_DATA = (("answer matches", lambda s,t: InvariantResult.pass_() if s in (0, 1) else InvariantResult.fail("answer")),\n             ("answer nonnegative", lambda s,t: InvariantResult.pass_() if s >= 0 else InvariantResult.fail("negative")))\nINVARIANTS = (Invariant("answer", RULE_DATA[0][0], RULE_DATA[0][1]),\n              Invariant("positive", RULE_DATA[1][0], RULE_DATA[1][1]),)' + source[end:]
    source = source.replace('def broken_variants(): return {"wrong": make(EXPECTED["answer"] + 1), "negative": make(-1)}',
                            'BAD_DATA = (("wrong", 2), ("negative", -1))\ndef broken_variants(): return {name: make(value) for name, value in BAD_DATA}')
    _fg403_helpers()["make_project"](tmp_path, source)
    native.start_target(tmp_path, "clarify just the answer rule")
    native.add_to_target(tmp_path, "one")
    model = tmp_path / ".flowguard/target/models/one.py"
    model.write_text(source.replace('"answer matches"', '"answer equals the declared native value"'))
    from flowguard.map.targetfile import load_target
    assert target_goal_rules(tmp_path, load_target(tmp_path)) == ["model one: ~answer"]


def test_missing_anchor_names_symbol_without_claiming_conformance():
    import runpy
    directory = Path(__file__).parents[1] / ".flowguard"
    helper = directory / "target/models/_gap_cases.py"
    if not helper.exists():
        helper = directory / "models/_gap_cases.py"
    result = runpy.run_path(str(helper))["native_case"]("anchor_only")
    assert "only the missing anchor symbol 'future_value' in native.py" in result["text"]
    assert "conformance did not run" in result["text"]
    assert result["todos"] and not result["errors"]


def test_helper_table_identity_ignores_unused_entries(tmp_path):
    from flowguard.map.facets import target_goal_rules
    from flowguard.map import target as native
    from flowguard.map.targetfile import load_target

    source = _fg403_helpers()["regular_source"](positive=True)
    source = source.replace('EXPECTED = {"answer": 1}', 'EXPECTED = {"answer": 1, "floor": 0}')
    source = source.replace(
        "def _positive(s): return s >= 0", 'def _positive(s): return s >= EXPECTED["floor"]'
    )
    _fg403_helpers()["make_project"](tmp_path, source)
    native.start_target(tmp_path, "preserve per-rule dependencies in a helper")
    native.add_to_target(tmp_path, "one")
    model = tmp_path / ".flowguard/target/models/one.py"
    model.write_text(source.replace('"floor": 0}', '"floor": 0, "unused": 9}'))
    assert target_goal_rules(tmp_path, load_target(tmp_path)) == []
    model.write_text(source.replace('"floor": 0}', '"floor": 1}'))
    lines = target_goal_rules(tmp_path, load_target(tmp_path))
    rules = [
        item
        for line in lines
        for item in line.partition(": ")[2].split(", ")
        if not item.endswith("(known-bad)")
    ]
    assert rules == ["~positive"], lines
    model.write_text(source.replace('s >= EXPECTED["floor"]', 's > EXPECTED["floor"]'))
    lines = target_goal_rules(tmp_path, load_target(tmp_path))
    rules = [
        item
        for line in lines
        for item in line.partition(": ")[2].split(", ")
        if not item.endswith("(known-bad)")
    ]
    assert rules == ["~positive"], lines
