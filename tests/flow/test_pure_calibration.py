"""Pure model correction preserves an unchanged sourced call precondition."""
import runpy

import pytest

from checkrun import run_check
from flowguard.flow.checks import check_model
from flowguard.flow.jobs import Planned, lookup
from flowguard.flow.model import load_model
from flowguard.flow.project import read_conflicts


MODEL = '''from flowguard.flow import Model, need
m = Model("pure_calibration", covers=["app.py:Tool.step"])
m.field("n", (0, 1), 0, source="R1")
@m.action(source="R1")
def step(s):
    need(s["n"] == 0)
    s["n"] = 1
m.only_when("step needs ready", "step", lambda before: before["n"] == 0, source="R1")
MODEL = m
'''

CORRECTED = MODEL.replace("MODEL = m", '''@m.action(source="R1")
def escape(s):
    need(s["n"] == 1)
    s["n"] = 0
MODEL = m''')


def _core(project, stored):
    receipt = stored["models"]["pure_calibration"]["core"]
    result = lookup(project.root, Planned.from_json(receipt["planned"]),
                    recorded_digest=receipt["digest"])
    assert result is not None
    return result


def _first_stuck(project):
    project.request("R1", "Step may run only when n=0 and sets n=1; an escape must make n=0 available again.")
    project.file("app.py", "class Tool:\n    def step(self): return 1\n")
    project.flow("pure_calibration", MODEL)
    first = run_check(project.root, "--json")
    assert first.code == 1, first.out + first.err
    stored = read_conflicts(project.root)
    original, = stored["conflicts"]
    assert original["kind"] == "STUCK"
    baseline = original["history"]["baseline"]
    rule, = [row for row in baseline["obligations"] if row["kind"] == "only_when"]
    assert rule["cases"] is None
    assert baseline["scope"]["coverage"]["anchors"] == ["app.py:Tool.step"]
    assert not _core(project, stored).info.get("native", {}).get("bound")
    return original, rule


def _correct(project, text=CORRECTED):
    path = project.flow("pure_calibration", text)
    loaded = load_model(path, project.root)
    assert not loaded.model.config and not getattr(loaded.model, "adapter_binding", None)
    report = check_model(loaded)
    assert report.graph.complete and not report.findings
    return run_check(project.root, "--json")


def test_unchanged_sourced_only_when_allows_pure_model_correction_and_executed_regression(project):
    original, before_rule = _first_stuck(project)
    result = _correct(project)
    assert result.code == 0, result.out + result.err
    stored = read_conflicts(project.root)
    assert not stored["conflicts"]
    closed, = stored["closed"]
    assert closed["id"] == original["id"]
    assert closed["history"]["baseline"] == original["history"]["baseline"]
    proof = closed["closure"]
    assert proof["kind"] == "model_corrected" and proof["boundary"] == "model-only"
    assert proof["model_correction"]["kind"] == "model_corrected"
    assert proof["complete_scope"] is True and proof["original_condition_gone"] is True
    assert proof["regression"]["passed"] is True
    assert all(row["why"].startswith("model_corrected:") for row in result.data["closed"])
    core = _core(project, stored)
    assert not core.info.get("native", {}).get("bound")
    after_rule, = [row for row in core.info["descriptor"]["obligations"] if row["kind"] == "only_when"]
    assert after_rule["cases"] is None and after_rule["definition"] == before_rule["definition"]
    assert after_rule["dependencies"] != before_rule["dependencies"]
    regression = project.root / proof["regression"]["path"]
    assert regression.is_file()
    runpy.run_path(str(regression), run_name="__main__")
    project.flow("pure_calibration", CORRECTED.replace('before["n"] == 0', 'before["n"] in (0, 1)'))
    with pytest.raises(AssertionError, match="source-bound model predicate changed"):
        runpy.run_path(str(regression), run_name="__main__")
    project.flow("pure_calibration", MODEL)
    with pytest.raises(AssertionError, match="original model conflict reproduces"):
        runpy.run_path(str(regression), run_name="__main__")


@pytest.mark.parametrize("predicate", [
    'before["n"] in (0, 1)',
    'before["n"] == READY',
    'bool(before["n"] == 0)',
])
def test_changed_or_unsafe_only_when_keeps_the_original_pure_model_conflict_open(project, predicate):
    original, _ = _first_stuck(project)
    corrected = CORRECTED.replace('lambda before: before["n"] == 0', 'lambda before: ' + predicate)
    if "READY" in predicate:
        corrected = corrected.replace('m.only_when(', 'READY = 0\nm.only_when(')
    result = _correct(project, corrected)
    assert result.code == 1, result.out + result.err
    stored = read_conflicts(project.root)
    current, = stored["conflicts"]
    assert current["id"] == original["id"]
    assert current["history"]["baseline"] == original["history"]["baseline"]
    assert not stored["closed"]
    assert not _core(project, stored).info.get("native", {}).get("bound")
