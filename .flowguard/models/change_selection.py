"""After an edit, select exactly the changed models, their importers and interface consumers.

The fixture has two components, a parent importing a child and an underscore
helper, and an explicit review child importing its parent. Test edits exercise
ancestor expansion independently of model-import expansion. An unused helper is
legitimately unselected; an ordinary unregistered nested model remains covered
by the existing native BLOCKED regression, not reinterpreted as this helper.
"""
from dataclasses import dataclass, replace
import json
import shutil
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
PARENT = "map-impact"
IMPLEMENTED_BY = {"Impact": "flowguard/map/impact.py:compute_impact"}
TESTED_BY = {
    "comments_select_no_checks": ["tests/test_flowguard_map.py:test_comment_only_edit_keeps_review_but_selects_no_checks"],
    "underscore_helper_not_blocked": ["tests/test_flowguard_map.py:test_impact_shared_test_binding_and_unknown_helper"],
    "model_importers_selected": ["tests/test_flowguard_map.py:test_change_selects_importers_and_ancestors_of_a_changed_model"],
    "unexplained_functions_listed": ["tests/test_flowguard_map.py:test_change_lists_unexplained_functions_of_changed_files"],
    "flow_models_selected": ["tests/test_flowguard_map.py:test_change_selects_the_model_of_a_flow_whose_step_changed"],
    "relied_models_selected": ["tests/test_flowguard_map.py:test_change_selects_models_whose_anchors_the_edit_calls"],
}

ALL = ("child", "parent", "review")
UNEXPLAINED = {"flow_step_edit": ("jobs: jobs.py:run (entrypoint)",)}
EXPECTED = {
    "code": (ALL, ("tests/test_child.py", "tests/test_parent.py", "tests/test_review.py")),
    "comment": ((), ()),
    "child": (ALL, ("tests/test_child.py", "tests/test_parent.py", "tests/test_review.py")),
    "helper": (ALL, ("tests/test_child.py", "tests/test_parent.py", "tests/test_review.py")),
    "test": (("child",), ("tests/test_child.py",)),
    "unused": ((), ()),
    # The parent model file really changes; its review child imports it inside a function.
    "parent_edit": (("parent", "review"), ("tests/test_parent.py", "tests/test_review.py")),
    # api.py calls core.py:work, the anchor of all three models; api owns no model itself.
    "caller_edit": (("child",), ("tests/test_child.py",)),
    # jobs.py is the second step of flow chain (model child); jobs imports nothing from core.
    "flow_step_edit": (("child",), ("tests/test_child.py",)),
}
PATHS = {"code": "core.py", "comment": "core.py", "child": ".flowguard/models/child.py",
         "helper": ".flowguard/models/_helper.py", "test": "tests/test_child.py",
         "unused": ".flowguard/models/_unused.py", "parent_edit": ".flowguard/models/parent.py",
         "caller_edit": "api.py", "flow_step_edit": "jobs.py"}


@dataclass(frozen=True)
class State:
    event: str = ""
    selected_models: tuple[str, ...] = ()
    selected_tests: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    unexplained: tuple[str, ...] = ()
    relied: tuple[str, ...] = ()


class Select:
    name = "Select"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        models, tests = EXPECTED[event]
        # jobs.py:run is a listed entrypoint with no model anchor, test or NOT_MODELED reason.
        result = State(event, models, tests, unexplained=UNEXPLAINED.get(event, ()),
                       relied=tuple(mid+" via core:work" for mid in ALL) if event=="caller_edit" else ())
        if self.defect == "ignore_importers" and event in {"child", "helper"}:
            result = replace(result, selected_models=tuple(x for x in models if x != "parent"))
        elif self.defect == "select_comments" and event == "comment":
            result = replace(result, selected_tests=("tests/test_core.py",))
        elif self.defect == "ignore_relied_models" and event == "caller_edit":
            result = replace(result, relied=())
        elif self.defect == "hides_unexplained" and event == "flow_step_edit":
            result = replace(result, unexplained=())
        elif self.defect == "ignore_flow_models" and event == "flow_step_edit":
            result = replace(result, selected_models=(), selected_tests=("tests/test_jobs.py",))
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
    _rule("comments_select_no_checks", {"comment"}, lambda state: not state.selected_models and not state.selected_tests,
          "a comment-only edit selected checks"),
    _rule("relied_models_selected", {"caller_edit"}, lambda state: state.selected_models == ("child",) and set(mid+" via core:work" for mid in ALL) <= set(state.relied),
          "relied models are printed; only the directly edited flow selects child"),
    _rule("unexplained_functions_listed", {"flow_step_edit"},
          lambda state: "jobs: jobs.py:run (entrypoint)" in state.unexplained,
          "an unexplained entrypoint of the changed file was not listed"),
    _rule("flow_models_selected", {"flow_step_edit"}, lambda state: "child" in state.selected_models,
          "the model of a flow whose step changed was omitted"),
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
            ("ignore_importers", "select_comments", "block_helper",
             "ignore_relied_models", "ignore_flow_models", "hides_unexplained")}


def _write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _build_baseline(root):
    _write(root, "core.py", "def work():\n    return 1\n")
    _write(root, "api.py", "from core import work\ndef handle():\n    return work()\n")
    _write(root, "jobs.py", "def run():\n    return 'done'\n")
    for name in ("core", "api", "jobs", "child", "parent", "review"):
        _write(root, "tests/test_" + name + ".py", "def test_safe():\n    assert True\n")
    for mid in ALL:
        source = (f'MODEL_ID = {mid!r}\nCOMPONENTS = ["core"]\n'
                  'IMPLEMENTED_BY = {"Work": "core.py:work"}\n'
                  f'TESTED_BY = {{"safe": ["tests/test_{mid}.py:test_safe"]}}\n'
                  'def build_explorer(): pass\n')
        source += {"parent": 'PARENT = "core"\nimport child\n',
                   "child": 'PARENT = "parent"\nfrom _helper import VALUE\n',
                   # The documented split style: import the parent inside a function.
                   "review": 'PARENT = "parent"\ndef _starts():\n    import parent\n    return parent\n'}[mid]
        _write(root, ".flowguard/models/" + mid + ".py", source)
    _write(root, ".flowguard/models/_helper.py", "VALUE = 1\n")
    _write(root, ".flowguard/models/_unused.py", "VALUE = 1\n")
    data = {"schema": "flowguard.map.v1", "project": "selection", "layers": ["interface", "core"],
                 "ignore": [], "test_command": "python -m pytest -q", "components": [
        {"id": name, "layer": "interface" if name == "api" else "core", "summary": name + " behavior",
         "responsibilities": [name + " operation"], "files": [name + ".py"],
         "entrypoints": ["jobs.py:run"] if name == "jobs" else [], "depends_on": ["core"] if name == "api" else [],
         "tests": ["tests/test_" + name + ".py"] if name in ("api", "jobs") else ["tests/test_" + n + ".py" for n in ("core", "child", "parent", "review")],
         "models": [], "status": "draft", "fingerprint": ""} for name in ("core", "api", "jobs")],
        "flows": [{"id": "chain", "summary": "handle then run the job", "steps": ["api:handle", "jobs:run reads out.json"],
                   "model": ".flowguard/models/child.py"}], "accepted_debts": []}
    _write(root, ".flowguard/map.json", json.dumps(data))
    for args in (("init", "-q"), ("add", "--", "."),
                 ("-c", "user.name=FlowGuard model", "-c", "user.email=model@example.invalid", "commit", "-qm", "baseline")):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


class RealSelection:
    def __init__(self, baseline):
        self.baseline = baseline

    def reset(self, initial_state):
        self.directory = tempfile.TemporaryDirectory(prefix="flowguard-selection-model-")
        self.root = Path(shutil.copytree(self.baseline, Path(self.directory.name) / "project"))
        self.data = json.loads((self.root / ".flowguard/map.json").read_text(encoding="utf-8"))
        self.state = initial_state

    def apply_step(self, step):
        event = step.function_input
        path = self.root / PATHS[event]
        text = path.read_text(encoding="utf-8")
        changed = (text + "\n# explanation\n" if event == "comment" else
                   text.replace("return 1", "return 2", 1) if event == "code" else
                   text.replace("VALUE = 1", "VALUE = 2", 1) if event in {"helper", "unused"} else
                   text.replace("assert True", "assert 1 == 1", 1) if event == "test" else
                   text.replace("return work()", "return work() + 0", 1) if event == "caller_edit" else
                   text.replace("return 'done'", "return 'finished'", 1) if event == "flow_step_edit" else
                   text + "\nEDITED = True\n")
        path.write_text(changed, encoding="utf-8")
        impact = compute_impact(self.root, self.data, build_inventory(self.root, DEFAULT_IGNORE), [PATHS[event]], base="HEAD")
        self.state = State(event, tuple(impact.model_ids), tuple(impact.tests), tuple(impact.blocked),
                           tuple(getattr(impact, "unexplained", ())), tuple(impact.relied_models))
        return ReplayObservation(function_name=step.function_name, observed_output=event, observed_state=self.state)

    def observe_state(self):
        return self.state

    def close(self):
        self.directory.cleanup()


def conformance():
    last = None
    with tempfile.TemporaryDirectory(prefix="flowguard-selection-baseline-") as directory:
        baseline = Path(directory)
        _build_baseline(baseline)
        for trace in select_covering_traces(build_explorer().explore().traces):
            adapter = RealSelection(baseline)
            try:
                last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                    rules=(projected_state_matches(), projected_output_matches()))
            finally:
                adapter.close()
            if not last.ok:
                return last
    return last
