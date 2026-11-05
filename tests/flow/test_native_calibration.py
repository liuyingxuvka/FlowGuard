"""A corrected native model retains the original inventory receipt and promises."""
import runpy

import pytest

from checkrun import run_check
from flowguard.flow.jobs import Planned, lookup
from flowguard.flow.model import load_model
from flowguard.flow.project import read_conflicts


MODEL = '''from flowguard.flow import Model, need
from flowguard.flow.adapter import fields
m = Model("calibration", covers=["app.py:Program"])
m.setting("limit", 1, source="R1")
m.field("n", (0, 1), 0, source="R1")
@m.action(source="R1")
def step(s):
    need(s["n"] == 0)
    s["n"] = 1
    return "done"
m.terminal("n", [1], source="R1")
m.reach("completion reachable", lambda s: s["n"] == 1, source="R1")
m.after("step finishes", "step", lambda before, after: after["n"] == 1, source="R1")
m.bind_adapter({"system":"app:Program", "classes":["app:Program"], "refusal":["app:Refusal"]},
    state=lambda snapshot:{"n":fields(snapshot, names=("n",))["n"]}, operations={"step":"step"})
MODEL = m
'''

CALIBRATED = MODEL.replace('covers=["app.py:Program"]', 'covers=["app.py:Program.step"]')\
    .replace('    need(s["n"] == 0)', '    need(s["n"] == 0)\n    need(True)')

APP = '''class Refusal(Exception): pass
class Program:
    def __init__(self): self.n = 0
    def step(self):
        if self.n != 0: raise Refusal("finished")
        self.n = NEXT
        return "done"
    def admin_reset(self): self.n = 0
    def admin_status(self): return "administration"
    @classmethod
    def load(cls): return cls()
    @staticmethod
    def admin_ping(): return "administration"
'''


def _app(project, *, broken):
    return project.file("app.py", APP.replace("NEXT", "0" if broken else "1"))


def _core(project, stored):
    saved = stored["models"]["calibration"]["core"]
    core = lookup(project.root, Planned.from_json(saved["planned"]), recorded_digest=saved["digest"])
    assert core is not None
    return core


def _initial_inventory_drift(project, *, broken, model=MODEL):
    project.request("R1", "Step must finish at n=1 and return done; completion must remain reachable.")
    _app(project, broken=broken)
    project.flow("calibration", model)
    first = run_check(project.root, "--json")
    assert first.code == 1, first.out + first.err
    stored = read_conflicts(project.root)
    entry, = stored["conflicts"]
    assert entry["kind"] == "MODEL DRIFT"
    native = _core(project, stored).info["native"]
    check, = native["checks"].values()
    assert check["status"] == "drift"
    assert {row["rule_name"] for row in check["conformance"]["violations"]} == {"operation_inventory"}
    assert native["operation_coverage"]["witnesses"] == []
    assert "skipped" in native["operation_coverage"]
    assert "walk" not in native
    assert check["native"]["steps"] == []
    after, = [row for row in entry["history"]["baseline"]["obligations"] if row["kind"] == "after"]
    assert after["cases"] is None
    loaded = load_model(project.root / ".flowguard/flow/calibration.py", project.root)
    predicate, = [rule.pred for rule in loaded.model.rules if rule.kind == "after"]
    assert not predicate.__code__.co_names and not predicate.__code__.co_freevars
    return entry, after


def _assert_original_preserved(current, original):
    assert current["id"] == original["id"]
    assert current["history"]["baseline"] == original["history"]["baseline"]
    assert current["detail"]["native_origin"] == original["detail"]["native_origin"]


def _assert_executed_closure(project, original, *, kind):
    stored = read_conflicts(project.root)
    assert not stored["conflicts"]
    closed, = stored["closed"]
    _assert_original_preserved(closed, original)
    proof = closed["closure"]
    assert proof["kind"] == kind
    assert proof["model_correction"]["kind"] == "model_corrected"
    assert proof["complete_scope"] is True and proof["original_condition_gone"] is True
    assert proof["regression"]["passed"] is True
    core = _core(project, stored)
    native = core.info["native"]
    assert native["status"] == "conformant" and native["footprints"]
    assert proof["checks"]
    assert all(native["checks"][key]["status"] == "conformant" for key in proof["checks"])
    regression = project.root / proof["regression"]["path"]
    assert regression.is_file()
    runpy.run_path(str(regression), run_name="__main__")
    return regression


def test_inventory_only_model_calibration_retains_sourced_after_and_closes(project):
    original, before_after = _initial_inventory_drift(project, broken=False)
    project.flow("calibration", CALIBRATED)
    result = run_check(project.root, "--json")
    assert result.code == 0, result.out + result.err
    core = _core(project, read_conflicts(project.root))
    after, = [row for row in core.info["descriptor"]["obligations"] if row["kind"] == "after"]
    assert after["cases"] is None and after["definition"] == before_after["definition"]
    assert after["dependencies"] != before_after["dependencies"]
    _assert_executed_closure(project, original, kind="model_corrected")


def test_model_calibration_keeps_real_bug_open_until_code_and_regression_are_fixed(project):
    original, _ = _initial_inventory_drift(project, broken=True)
    project.flow("calibration", CALIBRATED)
    calibrated = run_check(project.root, "--json")
    assert calibrated.code == 1, calibrated.out + calibrated.err
    stored = read_conflicts(project.root)
    current, = stored["conflicts"]
    _assert_original_preserved(current, original)
    assert not stored["closed"]
    native = _core(project, stored).info["native"]
    assert native["status"] == "drift" and native["operation_coverage"]["witnesses"]
    construction = native["checks"][native["operation_coverage"]["construction_check"]]
    assert construction["status"] == "conformant"
    assert native["walk"]["status"] == "drift"
    assert native["walk"]["replay_inputs_literal"] != "[]"
    assert any(row["rule_name"] == "projected_state_matches"
               for check in native["checks"].values()
               for row in check.get("conformance", {}).get("violations", []))
    _app(project, broken=False)
    repaired = run_check(project.root, "--json")
    assert repaired.code == 0, repaired.out + repaired.err
    regression = _assert_executed_closure(project, original, kind="code_fixed")
    _app(project, broken=True)
    with pytest.raises(AssertionError, match="native regression"):
        runpy.run_path(str(regression), run_name="__main__")


@pytest.mark.parametrize("change", ["missing_promise", "changed_after", "global_after", "call_after"])
def test_inventory_calibration_cannot_drop_or_change_the_original_sourced_after(project, change):
    original, _ = _initial_inventory_drift(project, broken=False)
    after = 'm.after("step finishes", "step", lambda before, after: after["n"] == 1, source="R1")'
    replacements = {
        "missing_promise": "",
        "changed_after": after.replace('after["n"] == 1', 'after["n"] >= 0'),
        "global_after": 'TARGET = 1\n' + after.replace('after["n"] == 1', 'after["n"] == TARGET'),
        "call_after": after.replace('after["n"] == 1', 'bool(after["n"] == 1)'),
    }
    project.flow("calibration", CALIBRATED.replace(after, replacements[change]))
    result = run_check(project.root, "--json")
    assert result.code == 1, result.out + result.err
    stored = read_conflicts(project.root)
    current, = stored["conflicts"]
    _assert_original_preserved(current, original)
    assert not stored["closed"]
    assert _core(project, stored).info["native"]["status"] == "conformant"


def test_ordinary_method_anchor_removal_is_not_class_inventory_calibration(project):
    method_scope = MODEL.replace('covers=["app.py:Program"]',
                                 'covers=["app.py:Program.step", "app.py:Program.admin_status"]')
    original, _ = _initial_inventory_drift(project, broken=False, model=method_scope)
    project.flow("calibration", CALIBRATED)
    result = run_check(project.root, "--json")
    assert result.code == 1, result.out + result.err
    stored = read_conflicts(project.root)
    current, = stored["conflicts"]
    _assert_original_preserved(current, original)
    assert not stored["closed"]
    assert _core(project, stored).info["native"]["status"] == "conformant"
