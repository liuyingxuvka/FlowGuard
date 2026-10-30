"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


from _fg_helpers import (
    flowguard_port421_escalation_model as escalation_model,
    map_impact_of as impact_of,
    flowguard_map_discover421_literal_fixture as literal_fixture,
    map_function_fixture,
    target__target_life_cycle_fixture_helpers,
)

def test_impact_shared_test_binding_and_unknown_helper(impact_project):
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
    from flowguard.map.impact import render_impact

    root, data = impact_project
    path = root / "shop/storage.py"
    text = path.read_text(encoding="utf-8")
    edited = {
        "comment": text.replace("DB = {}\n", "DB = {}  # in-memory store\n\n"),
        "docstring": '"""Order storage."""\n' + text,
        "code": text.replace("return x", "return x or None"),
        "untouched": text,
    }[edit]
    path.write_bytes(edited.replace("\n", line_endings).encode("utf-8"))
    imp = impact_of(root, data, ["shop/storage.py"], base="HEAD", broad=True)
    assert imp.direct == ["storage"]
    if edit == "comment":
        assert imp.comment_only == ["shop/storage.py"] and "comment-only edits" in render_impact(
            imp
        )
        assert imp.dependents == [] and imp.tests == [] and imp.models == []
    else:
        assert imp.comment_only == [] and imp.dependents == ["api", "orders"]
        assert "tests/test_storage.py" in imp.tests and "orders_check" in imp.model_ids










def test_removed_literal_sites_reach_function_selection(tmp_path):
    impact, text = target__target_life_cycle_fixture_helpers("_literal_fixture")["native_case"](
        tmp_path, "literal"
    )
    assert {"consumer_model", "policy"} == set(impact.model_ids)
    assert "consumer.py:use" in impact.changed_functions
    assert "producer no longer produces 'stale'" in text


def test_uncertain_source_broadens_selection(tmp_path):
    impact = map_function_fixture()["native_case"](tmp_path, "removed")
    assert impact.uncertain_files == {"core.py": "a symbol was removed or renamed"}
    assert {"child", "importer", "other", "parent"} == set(impact.model_ids)
    assert impact.whole_test_files == ["tests/test_core.py"]


def test_missing_selected_model_is_blocked(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact, render_impact
    from flowguard.map.common import DEFAULT_IGNORE

    data = map_function_fixture()["fixture"](tmp_path)
    impact = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        [".flowguard/models/missing.py"],
        base="HEAD",
    )
    assert impact.blocked == [
        ".flowguard/models/missing.py: selected model is missing or is not an executable registered model"
    ]
    assert "BLOCKED" in render_impact(impact)

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import pytest
from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
from flowguard.map.scan import guess_tests, new_map, propose_components
from dataclasses import fields, is_dataclass, replace
import runpy
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree

def test_s4a_rename_names_the_consumers(tmp_path):
    import json
    import shutil
    import subprocess
    import sys
    import tempfile
    import unittest
    from pathlib import Path
    import pytest
    from flowguard.map.discover import (
        component_summary,
        console_scripts,
        discover,
        discover_inventory,
        file_facts,
    )
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import (
        entrypoint_coverage_findings,
        run_lint,
        scoped_architecture_findings,
    )
    from flowguard.map.scan import guess_tests, new_map, propose_components

    impact, text = literal_fixture()["native_case"](tmp_path, "literal")
    lines = [
        line
        for line in text.splitlines()
        if line.startswith("producer no longer produces 'stale' that ")
    ]
    assert len(lines) == 2
    assert "consumer.py:" in lines[0]
    assert ".flowguard/models/consumer_model.py:" in lines[1]
    assert "consumer_model" in impact.model_ids
    assert "consumer.py:use" in impact.changed_functions
    assert "tests/test_result.py" in impact.tests


def test_removed_rule_known_bad_and_test_are_promises(tmp_path):
    import json
    import shutil
    import subprocess
    import sys
    import tempfile
    import unittest
    from pathlib import Path
    import pytest
    from flowguard.map.discover import (
        component_summary,
        console_scripts,
        discover,
        discover_inventory,
        file_facts,
    )
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import (
        entrypoint_coverage_findings,
        run_lint,
        scoped_architecture_findings,
    )
    from flowguard.map.scan import guess_tests, new_map, propose_components

    result, text = literal_fixture()["native_case"](tmp_path, "removed")
    assert "promises: policy: -rule safe; -known-bad bad; -test safe" in text
    assert len(result.promise_findings) == 3
    assert all(
        f["level"] == "warn" and f["code"] == "promise_removed" for f in result.promise_findings
    )


def test_moved_rule_prints_moved_not_promise(tmp_path):
    import json
    import shutil
    import subprocess
    import sys
    import tempfile
    import unittest
    from pathlib import Path
    import pytest
    from flowguard.map.discover import (
        component_summary,
        console_scripts,
        discover,
        discover_inventory,
        file_facts,
    )
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import (
        entrypoint_coverage_findings,
        run_lint,
        scoped_architecture_findings,
    )
    from flowguard.map.scan import guess_tests, new_map, propose_components

    result, text = literal_fixture()["native_case"](tmp_path, "moved")
    assert "moved: 1 rule(s), 1 known-bad, 1 test(s) from policy to recipient" in text
    assert not result.promise_findings


def test_rule_edit_selects_the_child_only(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree

    impact, text = escalation_model()["native_case"](tmp_path, "rule")
    assert impact.model_ids == ["lending"]
    assert "port: lending unchanged (this model only)" in text


def test_output_change_selects_parent_not_grandparent(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree

    impact, text = escalation_model()["native_case"](tmp_path, "output")
    assert impact.model_ids == ["consumer", "desk", "lending"]
    assert "out +waitlisted -> verify desk (parent), consumer (HANDOFF)" in text
    assert "grand" not in impact.model_ids


def test_reads_parent_change_selects_parent(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree

    impact, text = escalation_model()["native_case"](tmp_path, "reads")
    assert impact.model_ids == ["desk", "lending"]
    assert "reads +answer -> verify desk (parent)" in text


def test_moved_literal_selects_nothing(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.tree import build_tree
    from flowguard.map.impact_history import _literal_impact

    helper = target__target_life_cycle_fixture_helpers("_literal_fixture")
    data = helper["fixture"](tmp_path)
    helper["write"](tmp_path, "producer.py", 'def emit(): return "updated"\n')
    helper["write"](tmp_path, "relocated.py", 'def emit(): return "stale"\n')
    inv = build_inventory(tmp_path, [], write_cache=False)
    lines, models, functions, tests = _literal_impact(
        tmp_path,
        data,
        inv,
        build_tree(tmp_path, data, inv),
        ["producer.py", "relocated.py"],
        "HEAD",
    )
    assert lines == [] and models == functions == tests == set()


def test_dropped_consumer_lists_producer_code_first(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact

    helper = target__target_life_cycle_fixture_helpers("_literal_fixture")
    data = helper["fixture"](tmp_path)
    helper["write"](
        tmp_path,
        "consumer.py",
        'def use(value): return value == "updated"\ndef fold(value): return value\n',
    )
    impact = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, [], write_cache=False),
        ["consumer.py"],
        base="HEAD",
    )
    assert (
        impact.consumer_lines[0]
        == "consumer no longer handles 'stale' that producer produces at producer.py:1"
    )
    assert "policy" not in impact.model_ids


def test_settings_only_map_edit_is_not_structure(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact, render_impact
    import subprocess

    data = map_function_fixture()["fixture"](tmp_path)
    extra = tmp_path / "tests/test_more.py"
    extra.write_text("def test_more(): assert True\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "existing independent test",
        ],
        cwd=tmp_path,
        check=True,
    )
    data["components"][0].setdefault("tests", []).append("tests/test_more.py")
    data.setdefault("accepted_debts", []).append(
        dict(expires='9999-12-31', code="high_fan_out", component=data["components"][0]["id"], reason="probe")
    )
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data))
    impact = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, [], write_cache=False),
        [".flowguard/map.json"],
        base="HEAD",
    )
    assert impact.model_ids == []
    assert impact.tests == impact.whole_test_files == ["tests/test_more.py"]
    assert not impact.uncertain_files and "UNCERTAIN" not in render_impact(impact)
    assert impact.map_changed
    data["components"][0]["summary"] = "Clarify the same owner without widening checks"
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data))
    for broad in (False, True):
        view = compute_impact(
            tmp_path,
            data,
            build_inventory(tmp_path, [], write_cache=False),
            [".flowguard/map.json"],
            base="HEAD",
            broad=broad,
        )
        assert view.map_review == [data["components"][0]["id"]]
        assert view.map_changed and view.tests == ["tests/test_more.py"] and not view.models
        assert view.selected_test_functions <= view.total_test_functions
