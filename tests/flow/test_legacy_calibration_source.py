"""Legacy multiline rules need their exact retained source and original target."""
import ast
from copy import deepcopy
import inspect
from pathlib import Path
import runpy
import textwrap

import pytest

from checkrun import run_check
from test_native_calibration import (MODEL, _app, _assert_executed_closure,
                                     _assert_original_preserved, _core,
                                     _initial_inventory_drift)
from flowguard.flow import descriptors
from flowguard.flow.jobs import store
from flowguard.flow.model import load_model
from flowguard.flow.project import read_conflicts, write_conflicts
from flowguard.map.common import content_digest


MODEL_PATH = ".flowguard/flow/calibration.py"
AFTER = 'm.after("step finishes", "step", lambda before, after: after["n"] == 1, source="R1")'
MULTILINE_AFTER = '''m.after("step finishes", "step",
    lambda before, after: after["n"] == 1, source="R1")'''
MULTILINE_MODEL = MODEL.replace(AFTER, MULTILINE_AFTER)
CALIBRATED = MULTILINE_MODEL.replace('covers=["app.py:Program"]', 'covers=["app.py:Program.step"]')\
    .replace('    need(s["n"] == 0)', '    need(s["n"] == 0)\n    need(True)')


def _rule(project):
    loaded = load_model(project.root / MODEL_PATH, project.root)
    rule, = [rule for rule in loaded.model.rules if rule.kind == "after"]
    return rule


def _legacy_original(project, *, broken=False):
    _initial_inventory_drift(project, broken=broken, model=MULTILINE_MODEL)
    source_path = project.root / MODEL_PATH
    source = source_path.read_text(encoding="utf-8")
    assert source == MULTILINE_MODEL
    # Python retains only this incomplete lambda tail for a multiline call.
    with pytest.raises(SyntaxError):
        ast.parse(textwrap.dedent(inspect.getsource(_rule(project).pred)))
    stored = read_conflicts(project.root)
    entry, = stored["conflicts"]
    original_core = _core(project, stored)
    # Synthetic legacy-compatibility fixture: an 816a receipt predates only
    # the new rule-action metadata. Keep every captured source hash intact.
    for obligations in (entry["history"]["baseline"]["obligations"],
                        original_core.info["descriptor"]["obligations"]):
        for row in obligations:
            if row["kind"] in {"after", "only_when"}:
                row.get("dependencies", {}).pop("rule-action", None)
    old_rule, = [row for row in entry["history"]["baseline"]["obligations"] if row["kind"] == "after"]
    assert old_rule["dependencies"][MODEL_PATH] == content_digest(source_path, source_only=True)
    assert old_rule["cases"] is None and "rule-action" not in old_rule["dependencies"]
    entry.setdefault("detail", {})["original_model_source"] = {"path": MODEL_PATH, "text": source}
    store(project.root, original_core)
    write_conflicts(project.root, stored)
    return deepcopy(entry), deepcopy(old_rule)


def test_exact_legacy_multiline_source_closes_only_after_current_native_and_regression(project):
    original, _ = _legacy_original(project)
    project.flow("calibration", CALIBRATED)
    result = run_check(project.root, "--json")
    assert result.code == 0, result.out + result.err
    regression = _assert_executed_closure(project, original, kind="model_corrected")
    _app(project, broken=True)
    with pytest.raises(AssertionError, match="native regression"):
        runpy.run_path(str(regression), run_name="__main__")


def test_capsule_text_that_does_not_match_the_original_source_hash_stays_open(project):
    original, _ = _legacy_original(project)
    stored = read_conflicts(project.root)
    stored["conflicts"][0]["detail"]["original_model_source"]["text"] += "\n# Forged source text.\n"
    write_conflicts(project.root, stored)
    project.flow("calibration", CALIBRATED)
    result = run_check(project.root, "--json")
    assert result.code == 1, result.out + result.err
    stored = read_conflicts(project.root)
    current, = stored["conflicts"]
    _assert_original_preserved(current, original)
    assert not stored["closed"]
    assert _core(project, stored).info["native"]["status"] == "conformant"


@pytest.mark.parametrize("old_registration", ["different_target", "ambiguous_registration"])
def test_static_legacy_source_cannot_prove_a_different_or_ambiguous_old_target(project, old_registration):
    entry, old_rule = _legacy_original(project)
    project.flow("calibration", CALIBRATED)
    if old_registration == "different_target":
        old_source = MULTILINE_MODEL.replace(MULTILINE_AFTER, '''@m.action(source="R1")
def alternate(s):
    need(False)
''' + MULTILINE_AFTER.replace('"step",\n', '"alternate",\n'))
    else:
        old_source = MULTILINE_MODEL.replace(MULTILINE_AFTER, "if True:\n" +
            textwrap.indent(MULTILINE_AFTER, "    ") + "\nelse:\n" +
            textwrap.indent(MULTILINE_AFTER, "    "))
    ast.parse(old_source)
    # Self-consistent synthetic old dictionaries exercise static rejection;
    # these alternate old models are never executed or used as real receipts.
    old_rule["dependencies"][MODEL_PATH] = content_digest(Path(MODEL_PATH), data=old_source.encode("utf-8"),
                                                        source_only=True)
    entry["detail"]["original_model_source"] = {"path": MODEL_PATH, "text": old_source}
    assert descriptors.closed_rule_evidence(_rule(project), old_rule, entry=entry) is None


def test_exact_legacy_source_capsule_cannot_close_a_real_current_code_bug(project):
    original, _ = _legacy_original(project, broken=True)
    project.flow("calibration", CALIBRATED)
    result = run_check(project.root, "--json")
    assert result.code == 1, result.out + result.err
    stored = read_conflicts(project.root)
    current, = stored["conflicts"]
    _assert_original_preserved(current, original)
    assert not stored["closed"]
    assert _core(project, stored).info["native"]["status"] == "drift"
    assert current['detail'].get('original_model_source') == original['detail']['original_model_source']
    _app(project, broken=False)
    fixed = run_check(project.root, '--json')
    assert fixed.code == 0, fixed.out + fixed.err
    _assert_executed_closure(project, original, kind='code_fixed')


def test_future_capture_binds_the_actual_target_for_a_multiline_predicate(project):
    entry, _ = _initial_inventory_drift(project, broken=False, model=MULTILINE_MODEL)
    old, = [row for row in entry['history']['baseline']['obligations'] if row['kind'] == 'after']
    assert 'rule-action' in old['dependencies']
    project.flow('calibration', CALIBRATED)
    evidence = descriptors.closed_rule_evidence(_rule(project), old)
    assert evidence['basis'] == 'recorded-rule-action' and evidence['action'] == 'step'
    changed = CALIBRATED.replace(MULTILINE_AFTER, '''@m.action(source="R1")
def alternate(s):
    need(False)
''' + MULTILINE_AFTER.replace('"step",\n', '"alternate",\n'))
    project.flow('calibration', changed)
    current = _rule(project)
    assert descriptors._definition((current.pred,)) == old['definition']
    assert descriptors.closed_rule_evidence(current, old) is None
