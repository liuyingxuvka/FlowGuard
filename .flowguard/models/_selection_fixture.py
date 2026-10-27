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
class LegacyState:
    event: str = ""
    selected_models: tuple[str, ...] = ()
    selected_tests: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    unexplained: tuple[str, ...] = ()
    relied: tuple[str, ...] = ()


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
        subprocess.run(["git", "-c", "maintenance.auto=false", "-c", "gc.auto=0", *args], cwd=root, check=True, capture_output=True)


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
        self.state = LegacyState(event, tuple(impact.model_ids), tuple(impact.tests), tuple(impact.blocked),
                           tuple(getattr(impact, "unexplained", ())), tuple(impact.relied_models))
        return ReplayObservation(function_name=step.function_name, observed_output=event, observed_state=self.state)

    def observe_state(self):
        return self.state

    def close(self):
        self.directory.cleanup()



def observe_case(root, event):
    from types import SimpleNamespace
    _build_baseline(root)
    driver=RealSelection(root)
    driver.reset(LegacyState())
    try:
        observation=driver.apply_step(SimpleNamespace(function_input=event,function_name='Select'))
        return observation.observed_state
    finally:
        driver.close()
