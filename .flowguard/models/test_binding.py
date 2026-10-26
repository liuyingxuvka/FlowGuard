"""Bound tests must pass, reach an implementation anchor and name the rules they guard.

Each feature uses a fresh copy of one tiny two-rule project.  A missing
binding is observed as a real warning while native model proof remains green.
Only singleton defects are explored, to bound nested pytest startup costs.
"""
from pathlib import Path
import shutil
import sys
import tempfile

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.map.proof import run_bound_tests, run_model_in_process

MODEL_ID = "test_binding"
PARENT = "map-proof"
NOT_MODELED = {
    "flowguard/map/testreach.py:main.Reach.pytest_exception_interact": "pytest hook inside the reach-recording "
        "subprocess; it only marks a failed call, and the failed-binding verdict it feeds is this model's "
        "each_defect_rejected rule replayed on real bound tests",
}
IMPLEMENTED_BY = {
    "BoundTests": "flowguard/map/proof.py:run_bound_tests",
}
USES = {"RuleWarnings": "flowguard/map/proof.py:run_model_in_process"}
TESTED_BY = {
    "each_defect_rejected": [
        "tests/test_flowguard_map_proof.py:test_tested_by_must_reach_the_anchored_code[empty-tested_by_misses_anchor]",
        "tests/test_flowguard_map_proof.py:test_tested_by_must_reach_the_anchored_code[fail-tested_by_failed]",
        "tests/test_flowguard_map_proof.py:test_rule_without_a_test_is_named",
    ],
    "every_defect_reported": [
        "tests/test_flowguard_map_proof.py:test_tested_by_must_reach_the_anchored_code[empty-tested_by_misses_anchor]",
        "tests/test_flowguard_map_proof.py:test_tested_by_must_reach_the_anchored_code[fail-tested_by_failed]",
        "tests/test_flowguard_map_proof.py:test_rule_without_a_test_is_named",
    ],
}

BASE = '''from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.workflow import Workflow
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "binding_case"
IMPLEMENTED_BY = {"Advance": "binding_target.py:advance"}
TESTED_BY = {"at_most_one": ["tests/test_binding_target.py:test_advance"],
             "nonnegative": ["tests/test_binding_target.py:test_advance"]}
class Step:
    name = "Advance"
    def __init__(self, result=1): self.result = result
    def apply(self, event, state):
        return (FunctionResult(self.result, self.result),)
RULES = (Invariant("at_most_one", "advance at most once", lambda state, trace: state <= 1),
         Invariant("nonnegative", "advance never reverses", lambda state, trace: state >= 0))
def make(value=1):
    return Explorer(Workflow((Step(value),)), (0,), ("advance",), invariants=RULES,
                    max_sequence_length=1, progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"too_far": make(2), "reversed": make(-1)}
def conformance():
    actual = load_anchor(IMPLEMENTED_BY["Advance"])(0)
    return CodeFactsReport((Fact("advance_once", actual == 1, "actual=" + repr(actual)),))
'''
TEST_SOURCE = '''def test_advance():
    from binding_target import advance
    assert advance(0) == 1
'''


def _change(key, old, new):
    def apply(fixture):
        assert old in fixture[key]
        return {**fixture, key: fixture[key].replace(old, new, 1)}
    return apply


FEATURES = (
    Feature("bound_test_fails", True, ("tested_by_failed",),
            _change("test", "assert advance(0) == 1", "assert advance(0) == 99")),
    Feature("bound_test_misses_anchor", True, ("tested_by_misses_anchor",),
            _change("test", "    from binding_target import advance\n    assert advance(0) == 1",
                    "    assert 1 == 1")),
    Feature("rule_without_test", True, ("invariant_untested",),
            _change("model", ',\n             "nonnegative": ["tests/test_binding_target.py:test_advance"]', "")),
)


def build_explorer():
    return feature_explorer(FEATURES, max_features=1)


def broken_variants():
    return feature_variants(FEATURES, max_features=1)


def _review(template, fixture):
    saved_path = sys.path[:]
    names = ("binding_target", "_flowguard_model_binding_case")
    saved_modules = {name: sys.modules.pop(name) for name in names if name in sys.modules}
    try:
        with tempfile.TemporaryDirectory(prefix="flowguard-binding-case-") as directory:
            root = Path(directory) / "project"
            shutil.copytree(template, root)
            path = root / ".flowguard/models/binding_case.py"
            path.write_text(fixture["model"], encoding="utf-8")
            (root / "tests/test_binding_target.py").write_text(fixture["test"], encoding="utf-8")
            result = run_model_in_process(root, path)
            if result.status == "error":
                raise RuntimeError("native fixture error: " + "; ".join(result.problems))
            missing_warning = ("invariant_untested: nonnegative have no TESTED_BY test; "
                               "bind a test that fails when the rule is broken")
            if result.warnings and result.warnings != [missing_warning]:
                raise RuntimeError("unexpected native fixture warnings: " + "; ".join(result.warnings))
            if result.status != "pass" or result.warnings != [missing_warning]:
                run_bound_tests(root, path, result)
    finally:
        sys.path[:] = saved_path
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
    if result.status == "error":
        raise RuntimeError("bound test environment error: " + "; ".join(result.problems))
    text = "\n".join(result.problems + result.warnings)
    codes = tuple(code for code in ("tested_by_failed", "tested_by_misses_anchor", "invariant_untested")
                  if code + (":" if code == "invariant_untested" else " ") in text)
    if codes == ("invariant_untested",) and result.status != "pass":
        raise RuntimeError("missing binding must remain a native PASS: " + text)
    return result.status == "pass" and not codes, codes


def conformance():
    with tempfile.TemporaryDirectory(prefix="flowguard-binding-template-") as directory:
        template = Path(directory)
        (template / ".flowguard/models").mkdir(parents=True)
        (template / "tests").mkdir()
        (template / "binding_target.py").write_text("def advance(value):\n    return value + 1\n", encoding="utf-8")
        (template / ".flowguard/models/binding_case.py").write_text(BASE, encoding="utf-8")
        (template / "tests/test_binding_target.py").write_text(TEST_SOURCE, encoding="utf-8")
        return feature_conformance(FEATURES, lambda: {"model": BASE, "test": TEST_SOURCE},
                                   lambda fixture: _review(template, fixture), max_features=1)
