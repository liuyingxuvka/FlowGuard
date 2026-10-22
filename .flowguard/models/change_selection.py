"""Replay a finite after-edit selection model against a real temporary Git project.

The fixture has two components, a parent importing a child and an underscore
helper, and an explicit review child importing its parent. Test edits exercise
ancestor expansion independently of model-import expansion. An unused helper is
legitimately unselected; an ordinary unregistered nested model remains covered
by the existing native BLOCKED regression, not reinterpreted as this helper.
"""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import subprocess
import tempfile

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.impact import compute_impact
from flowguard.map.inventory import build_inventory

MODEL_ID = "change_selection"
PARENT = "map-analysis"
IMPLEMENTED_BY = {"Impact": "flowguard/map/impact.py:compute_impact"}
TESTED_BY = {
    "comments_select_no_checks": ["tests/test_flowguard_map.py:test_comment_only_edit_keeps_review_but_selects_no_checks"],
    "underscore_helper_not_blocked": ["tests/test_flowguard_map.py:test_impact_shared_test_binding_and_unknown_helper"],
    "model_importers_selected": ["tests/test_flowguard_map.py:test_change_selects_importers_and_ancestors_of_a_changed_model"],
    "model_ancestors_selected": ["tests/test_flowguard_map.py:test_change_selects_importers_and_ancestors_of_a_changed_model"],
    "selected_reviews_selected": ["tests/test_flowguard_map.py:test_change_selects_the_review_children_of_a_selected_model"],
}

ALL = ("child", "parent", "review")
EXPECTED = {
    "code": (ALL, ("tests/test_api.py", "tests/test_child.py", "tests/test_core.py", "tests/test_parent.py", "tests/test_review.py")),
    "comment": ((), ()),
    "child": (ALL, ("tests/test_child.py",)),
    "helper": (ALL, ()),
    "test": (ALL, ("tests/test_child.py",)),
    "unused": ((), ()),
}
PATHS = {"code": "core.py", "comment": "core.py", "child": ".flowguard/models/child.py",
         "helper": ".flowguard/models/_helper.py", "test": "tests/test_child.py",
         "unused": ".flowguard/models/_unused.py"}


@dataclass(frozen=True)
class State:
    event: str = ""
    selected_models: tuple[str, ...] = ()
    selected_tests: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()


class Select:
    name = "Select"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        models, tests = EXPECTED[event]
        result = State(event, models, tests)
        if self.defect == "ignore_importers" and event in {"child", "helper"}:
            result = replace(result, selected_models=tuple(x for x in models if x != "parent"))
        elif self.defect == "ignore_ancestors" and event == "test":
            result = replace(result, selected_models=tuple(x for x in models if x != "parent"))
        elif self.defect == "ignore_reviews":
            result = replace(result, selected_models=tuple(x for x in models if x != "review"))
        elif self.defect == "select_comments" and event == "comment":
            result = replace(result, selected_tests=("tests/test_core.py",))
        elif self.defect == "block_helper" and event == "helper":
            result = replace(result, blocked=("underscore helper has no owner",))
        return (FunctionResult(event, result, label=event),)


def _rule(name, relevant, predicate, message):
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in relevant or predicate(state)
                     else InvariantResult.fail(message))


INVARIANTS = (
    _rule("model_importers_selected", {"child", "helper"}, lambda state: "parent" in state.selected_models,
          "the importing parent was omitted"),
    _rule("model_ancestors_selected", {"test"}, lambda state: "parent" in state.selected_models,
          "the selected child's ancestor was omitted"),
    _rule("selected_reviews_selected", {"code", "child", "helper", "test"},
          lambda state: "review" in state.selected_models, "the explicit importing review child was omitted"),
    _rule("comments_select_no_checks", {"comment"}, lambda state: not state.selected_models and not state.selected_tests,
          "a comment-only edit selected checks"),
    _rule("underscore_helper_not_blocked", {"helper", "unused"}, lambda state: not state.blocked,
          "a legitimate underscore helper was BLOCKED"),
)


def _explorer(defect=""):
    return Explorer(Workflow((Select(defect),)), (State(),), tuple(EXPECTED), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in
            ("ignore_importers", "ignore_ancestors", "ignore_reviews", "select_comments", "block_helper")}


def _write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class RealSelection:
    def reset(self, initial_state):
        self.directory = tempfile.TemporaryDirectory(prefix="flowguard-selection-model-")
        self.root = Path(self.directory.name)
        _write(self.root, "core.py", "def work():\n    return 1\n")
        _write(self.root, "api.py", "from core import work\ndef handle():\n    return work()\n")
        for name in ("core", "api", "child", "parent", "review"):
            _write(self.root, "tests/test_" + name + ".py", "def test_safe():\n    assert True\n")
        for mid in ALL:
            source = (f'MODEL_ID = {mid!r}\nCOMPONENTS = ["core"]\n'
                      'IMPLEMENTED_BY = {"Work": "core.py:work"}\n'
                      f'TESTED_BY = {{"safe": ["tests/test_{mid}.py:test_safe"]}}\n'
                      'def build_explorer(): pass\n')
            source += {"parent": 'PARENT = "core"\nimport child\n',
                       "child": 'PARENT = "parent"\nfrom _helper import VALUE\n',
                       "review": 'PARENT = "parent"\nimport parent\n'}[mid]
            _write(self.root, ".flowguard/models/" + mid + ".py", source)
        _write(self.root, ".flowguard/models/_helper.py", "VALUE = 1\n")
        _write(self.root, ".flowguard/models/_unused.py", "VALUE = 1\n")
        self.data = {"schema": "flowguard.map.v1", "project": "selection", "layers": ["interface", "core"],
                     "ignore": [], "test_command": "python -m pytest -q", "components": [
            {"id": name, "layer": "interface" if name == "api" else "core", "summary": name + " behavior",
             "responsibilities": [name + " operation"], "files": [name + ".py"],
             "entrypoints": [], "depends_on": ["core"] if name == "api" else [],
             "tests": ["tests/test_api.py"] if name == "api" else ["tests/test_" + n + ".py" for n in ("core", "child", "parent", "review")],
             "models": [], "status": "draft", "fingerprint": ""} for name in ("core", "api")],
            "flows": [], "accepted_debts": []}
        _write(self.root, ".flowguard/map.json", json.dumps(self.data))
        for args in (("init", "-q"), ("add", "--", "."),
                     ("-c", "user.name=FlowGuard model", "-c", "user.email=model@example.invalid", "commit", "-qm", "baseline")):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        self.state = initial_state

    def apply_step(self, step):
        event = step.function_input
        path = self.root / PATHS[event]
        text = path.read_text(encoding="utf-8")
        changed = (text + "\n# explanation\n" if event == "comment" else
                   text.replace("return 1", "return 2", 1) if event == "code" else
                   text.replace("VALUE = 1", "VALUE = 2", 1) if event in {"helper", "unused"} else
                   text.replace("assert True", "assert 1 == 1", 1) if event == "test" else
                   text + "\nEDITED = True\n")
        path.write_text(changed, encoding="utf-8")
        impact = compute_impact(self.root, self.data, build_inventory(self.root, DEFAULT_IGNORE), [PATHS[event]], base="HEAD")
        self.state = State(event, tuple(impact.model_ids), tuple(impact.tests), tuple(impact.blocked))
        return ReplayObservation(function_name=step.function_name, observed_output=event, observed_state=self.state)

    def observe_state(self):
        return self.state

    def close(self):
        self.directory.cleanup()


def conformance():
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = RealSelection()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
