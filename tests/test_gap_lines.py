"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_rule_broken_by_old_code_is_an_expected_gap(tmp_path):
    from _fg_helpers import target__fg403_helpers as _fg403_helpers, target__load_map as _load_map
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
    assert "NO GAP one:" in native.render_target_report(report)
    assert native.promote_target(root) == 0
    assert "model_digests" in _load_map(root)


def test_split_into_child_prints_moved_rules_only():
    from _fg_helpers import target__fg403_helpers as _fg403_helpers
    result = _fg403_helpers()["native_case"]("move")
    assert "moved rules only: moved (1 from one; no gap expected)" in result["text"]
    assert ">positive (from one)" in str(result["goal"])


def test_recorded_rule_prints_no_gap():
    from _fg_helpers import target__fg403_helpers as _fg403_helpers
    result = _fg403_helpers()["native_case"]("recorded")
    assert "NO GAP one:" in result["text"] and not result["errors"] and not result["todos"]


def test_missing_bound_test_is_never_a_gap():
    from _fg_helpers import target__fg403_helpers as _fg403_helpers
    result = _fg403_helpers()["native_case"]("missing_test")
    assert "NO GAP one:" in result["text"] and "EXPECTED GAP" not in result["text"]
    assert not result["todos"]


@pytest.mark.parametrize("case", ["anchor_exception", "engine_exception", "adapter_exception"])
def test_exception_classification(case):
    from _fg_helpers import target__fg403_helpers as _fg403_helpers
    result = _fg403_helpers()["native_case"](case)
    if case == "anchor_exception":
        assert "EXPECTED GAP one:" in result["text"] and result["todos"] and not result["errors"]
    else:
        assert result["errors"] and "EXPECTED GAP" not in result["text"]
        assert "getattr(report," in result["text"]
