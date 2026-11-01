"""Independent owner rules judge recorded facts without touching the world."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def rule_project(root, expression="3", fixture="step"):
    from flowguard.map.requests import store_request
    store_request(root, b"The quantity must be at most three.\n", identifier="R3")
    directory = root / "tests/rules/quota"
    directory.mkdir(parents=True)
    path = directory / "test_cap.py"
    view = 'step.after.count("U1")' if fixture == "step" else 'state.count("U1")'
    path.write_text('from flowguard.behave.rules import rule, owner\n'
                    '@rule(owner("R3", "The quantity must be at most three."))\n'
                    f'def test_cap({fixture}):\n    assert {view} <= {expression}\n')
    return path


def captures(value=4):
    def observed(n):
        return {"values": [{"query": "count", "entity": "unit", "args": ["U1"], "value": n}],
                "identifiers": {"unit": ["U1"]}, "unknown": []}
    prefix = [{"name": "advance", "args": ["U1"]}] * value
    return {"spec": {"entities": {"unit": {"list": "units"}},
                     "queries": ["units", "count", "unrecorded"], "actions": ["advance"]},
            "steps": [{"start": {"world": "small", "seed": 0}, "prefix": prefix,
                       "outcomes": ["success"] * value, "call": prefix[-1], "outcome": "success",
                       "args": {"unit_id": "U1"}, "before_key": "before", "after_key": "after",
                       "before": observed(value - 1), "after": observed(value)}],
            "states": [{"start": {}, "prefix": prefix, "outcomes": ["success"] * value,
                        "state_key": "after", "observation": observed(value)}],
            "complete": True, "missing": []}


def test_owner_rule_rejudges_same_immutable_facts_when_only_literal_changes(tmp_path, monkeypatch):
    from flowguard.behave.rules import collect_rules, judge
    from flowguard.behave import project
    path = rule_project(tmp_path)
    facts = captures()
    original = copy.deepcopy(facts)
    monkeypatch.setattr(project, "replay", lambda *a, **k: pytest.fail("offline judge ran the world"))
    plan = collect_rules(tmp_path)
    assert not plan["errors"]
    result = judge(plan, facts)
    assert result["rules"][0]["status"] == "broken"
    assert result["candidates"][0]["rule"] == "quota.test_cap"
    assert result["candidates"][0]["prefix"] == facts["steps"][0]["prefix"]
    assert plan["rules"][0]["provenance"][0]["request"] == "R3"
    assert judge(plan, captures(3))["rules"][0]["status"] == "clean"
    path.write_text(path.read_text().replace("<= 3", "<= 4"))
    revised = collect_rules(tmp_path)
    assert revised["identity"] != plan["identity"]
    assert judge(revised, facts)["rules"][0]["status"] == "clean"
    assert facts == original


def test_missing_public_query_and_incomplete_scope_never_pass(tmp_path):
    from flowguard.behave.rules import collect_rules, judge
    path = rule_project(tmp_path, fixture="state")
    path.write_text(path.read_text().replace('state.count("U1")', "state.unrecorded()"))
    result = judge(collect_rules(tmp_path), captures())
    assert result["rules"][0]["status"] == "not-judged"
    assert not result["candidates"]
    assert "unrecorded" in result["rules"][0]["reason"]
    path.write_text(path.read_text().replace("state.unrecorded()", 'state.count("U1")'))
    facts = captures(3)
    facts["complete"] = False
    assert judge(collect_rules(tmp_path), facts)["rules"][0]["status"] == "not-judged"


def test_closure_includes_helpers_constants_defaults_and_world(tmp_path):
    from flowguard.behave.rules import collect_rules, judge
    path = rule_project(tmp_path, expression="limit()")
    path.write_text('LIMIT = 3\ndef limit(value=LIMIT):\n    return value\n' + path.read_text())
    first = collect_rules(tmp_path)
    assert judge(first, captures())["candidates"]
    path.write_text(path.read_text().replace("LIMIT = 3", "LIMIT = 4"))
    second = collect_rules(tmp_path)
    assert second["rules"][0]["closure"] != first["rules"][0]["closure"]
    assert judge(second, captures())["rules"][0]["status"] == "clean"
    (path.parent / "world.py").write_text("WORLD = None\n")
    third = collect_rules(tmp_path)
    assert third["rules"][0]["closure"] != second["rules"][0]["closure"]
    assert judge(third, captures())["rules"][0]["status"] == "not-judged"


def test_owner_quote_and_system_import_are_static_errors(tmp_path):
    from flowguard.behave.rules import collect_rules
    path = rule_project(tmp_path)
    path.write_text(path.read_text().replace("at most three", "at most four"))
    assert "quote_not_in_request" in {row["code"] for row in collect_rules(tmp_path)["errors"]}
    path.write_text('from program import LIMIT\n' + path.read_text())
    assert "rule_imports_system" in {row["code"] for row in collect_rules(tmp_path)["errors"]}


def test_imported_rule_helper_is_in_closure_and_views_reject_mutation(tmp_path):
    from flowguard.behave.rules import collect_rules, judge
    path = rule_project(tmp_path, expression="LIMIT")
    helper = tmp_path / "tests/rules/helper.py"
    helper.write_text("LIMIT = 3\n")
    path.write_text("from tests.rules.helper import LIMIT\n" + path.read_text())
    first = collect_rules(tmp_path)
    assert not first["errors"]
    assert judge(first, captures())["candidates"]
    helper.write_text("LIMIT = 4\n")
    second = collect_rules(tmp_path)
    assert second["identity"] != first["identity"]
    assert judge(second, captures())["rules"][0]["status"] == "clean"
    path.write_text(path.read_text().replace('    assert step.after.count("U1") <= LIMIT',
                                             '    step.after.units().append("invented")'))
    facts = captures()
    before = copy.deepcopy(facts)
    assert judge(collect_rules(tmp_path), facts)["rules"][0]["status"] == "not-judged"
    assert facts == before


def test_closure_tracks_each_definition_on_same_physical_line(tmp_path):
    from flowguard.behave.rules import collect_rules, judge
    path = rule_project(tmp_path, expression="min(A, B)")
    original = "A = 3; B = 5\n" + path.read_text()
    path.write_text(original)
    baseline = collect_rules(tmp_path)
    assert not baseline["errors"]
    first = baseline["rules"][0]["closure"]
    for before, after in (("A = 3", "A = 4"), ("B = 5", "B = 6")):
        path.write_text(original.replace(before, after))
        revised = collect_rules(tmp_path)
        assert not revised["errors"]
        assert revised["rules"][0]["closure"] != first, before
    path.write_text(original)
    assert judge(collect_rules(tmp_path), captures())["rules"][0]["status"] == "broken"
    path.write_text(original.replace("A = 3", "A = 4"))
    assert judge(collect_rules(tmp_path), captures())["rules"][0]["status"] == "clean"


def test_dynamic_system_load_is_not_judged_and_pure_math_helper_stays_independent(tmp_path):
    from flowguard.behave.rules import collect_rules, judge
    path = rule_project(tmp_path)
    marker = tmp_path / "system-loaded"
    system = tmp_path / "program.py"
    system.write_text(f'LIMIT = 4\nopen({str(marker)!r}, "w").write("loaded")\n')
    header = path.read_text().split("def test_cap", 1)[0]
    path.write_text(header + 'def test_cap(step):\n    import importlib.util\n'
        f'    spec = importlib.util.spec_from_file_location("hidden_system", {str(system)!r})\n'
        '    system = importlib.util.module_from_spec(spec)\n    spec.loader.exec_module(system)\n'
        '    assert step.after.count("U1") <= system.LIMIT\n')
    result = judge(collect_rules(tmp_path), captures())
    assert result["rules"][0]["status"] == "not-judged"
    assert not result["candidates"] and not marker.exists()
    path.write_text('import math\ndef limit():\n    return math.floor(3.9)\n' + header +
                    'def test_cap(step):\n    assert step.after.count("U1") <= limit()\n')
    assert judge(collect_rules(tmp_path), captures())["rules"][0]["status"] == "broken"
    assert judge(collect_rules(tmp_path), captures(3))["rules"][0]["status"] == "clean"


def test_spec_and_answers_are_detached_readonly_even_with_private_reason(tmp_path):
    from flowguard.behave.rules import _View, collect_rules, judge
    path = rule_project(tmp_path)
    path.write_text(path.read_text().replace('@rule(owner("R3", "The quantity must be at most three."))',
        '@rule(owner("R3", "The quantity must be at most three."), private="reviewed reason")')
        .replace('    assert step.after.count("U1") <= 3', '    step.after._spec["actions"].clear()'))
    facts = captures()
    original = copy.deepcopy(facts)
    assert judge(collect_rules(tmp_path), facts)["rules"][0]["status"] == "not-judged"
    view = _View(facts["steps"][0]["after"], facts["spec"])
    with pytest.raises((AttributeError, TypeError)):
        view._spec["actions"].clear()
    assert facts == original


def test_local_helper_import_and_package_relative_import_belong_to_closure(tmp_path):
    from flowguard.behave.rules import collect_rules, judge
    path = rule_project(tmp_path)
    package = tmp_path / "tests/rules/limits"
    package.mkdir()
    (package / "__init__.py").write_text("from .helper import LIMIT\n")
    helper = package / "helper.py"
    helper.write_text("LIMIT = 3\n")
    header = path.read_text().split("def test_cap", 1)[0]
    path.write_text(header + 'def test_cap(step):\n    from tests.rules.limits import LIMIT\n'
                    '    assert step.after.count("U1") <= LIMIT\n')
    plan = collect_rules(tmp_path)
    assert not plan["errors"]
    assert judge(plan, captures())["rules"][0]["status"] == "broken"
    helper.write_text("LIMIT = 4\n")
    revised = collect_rules(tmp_path)
    assert revised["identity"] != plan["identity"]
    assert judge(revised, captures())["rules"][0]["status"] == "clean"


def test_decorator_without_plugin_skips_locally_and_fails_in_ci(tmp_path):
    rule_project(tmp_path)
    root = Path(__file__).resolve().parents[2]
    command = [sys.executable, "-m", "pytest", "-q", str(tmp_path / "tests/rules"), "--rootdir", str(tmp_path)]
    env = {**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("CI", None)
    local = subprocess.run(command, env=env, capture_output=True, text=True)
    assert local.returncode == 0 and "1 skipped" in local.stdout
    required = subprocess.run(command, env={**env, "CI": "true"}, capture_output=True, text=True)
    assert required.returncode == 1 and "explored result for this tree not ready" in required.stdout
