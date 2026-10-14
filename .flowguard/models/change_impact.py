"""Finite model: change selection preserves callers and registered check identities.

Seven independent changes in the same a -> b -> c, unrelated d boundary protect
the daily selector. Replay calls the real impact function and proof runner; it
never starts pytest or copies the implementation's graph traversal.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation,
                       Workflow, replay_trace, select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "change_impact"
COMPONENTS = ["map-analysis"]
IMPLEMENTED_BY = {
    "Select": "flowguard/map/impact.py:compute_impact",
    "Run": "flowguard/map/proof.py:run_models",
    "Command": "flowguard/map/cli.py:cmd_impact",
}


@dataclass(frozen=True)
class Event:
    kind: str


@dataclass(frozen=True)
class State:
    scenario: str = ""
    components: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    model_ids: tuple[str, ...] = ()
    blocked: bool = False


# This is an explicit finite oracle, not another dependency-selector algorithm.
_ABC = (("a", "b", "c"), ("tests/test_a.py", "tests/test_b.py", "tests/test_c.py"), ("b", "c"))
_AB = (("a", "b"), ("tests/test_a.py", "tests/test_b.py"), ("b",))
EXPECTED = {
    "c_change": _ABC,
    "c_delete": _ABC,
    "runner_change": _AB,
    "runner_helper": _AB,
    "test_change": _ABC,
    "binding_change": (("a", "b"), ("tests/test_a.py", "tests/test_b.py", "tests/test_shared.py"), ("b",)),
    "unknown_source": ((), (), ()),
}


class Select:
    name = "Select"
    reads = ()
    writes = ("scenario", "components", "tests", "model_ids", "blocked")

    def selection(self, kind: str) -> State:
        components, tests, model_ids = EXPECTED[kind]
        return State(kind, components, tests, model_ids, kind == "unknown_source")

    def apply(self, event: Event, state: State):
        selected = self.selection(event.kind)
        return (FunctionResult("blocked" if selected.blocked else "selected", selected, label=event.kind),)


class OneHop(Select):
    def selection(self, kind: str) -> State:
        selected = super().selection(kind)
        if kind in {"c_change", "c_delete", "test_change"}:
            return replace(selected, components=("b", "c"), tests=("tests/test_b.py", "tests/test_c.py"))
        return selected


class MissingModelBackreference(Select):
    def selection(self, kind: str) -> State:
        if kind in {"runner_change", "runner_helper"}:
            return State(scenario=kind)
        return super().selection(kind)


def _complete_selection(state: State, trace) -> InvariantResult:
    if state.scenario and (state.components, state.tests, state.model_ids) != EXPECTED[state.scenario]:
        return InvariantResult.fail("a caller or registered check identity was omitted, or unrelated d was selected")
    return InvariantResult.pass_()


def _unknown_is_blocked(state: State, trace) -> InvariantResult:
    if state.scenario == "unknown_source" and not state.blocked:
        return InvariantResult.fail("unknown ownership was reported as a successful empty selection")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("complete_selection", "the finite affected set and registered checks are selected exactly", _complete_selection),
    Invariant("unknown_is_blocked", "unmapped source needs review rather than empty success", _unknown_is_blocked),
)
EVENTS = tuple(Event(kind) for kind in EXPECTED)


def _explorer(selector: Select) -> Explorer:
    return Explorer(workflow=Workflow((selector,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Select())


def broken_variants() -> dict:
    return {"one_hop": _explorer(OneHop()), "missing_model_backreference": _explorer(MissingModelBackreference())}


class _RealSelection:
    def reset(self, initial_state: State) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="fg-impact-")
        self.root = Path(self.directory.name)
        contents = {
            "a.py": "import b\n", "b.py": "import c\n", "c.py": "VALUE = 1\n", "d.py": "VALUE = 4\n",
            **{f"tests/test_{cid}.py": "def test_value():\n    assert True\n" for cid in "abcd"},
            "tests/test_shared.py": "def test_shared():\n    assert True\n",
            ".flowguard/models/owners/b/model.py": "VALUE = 1\n",
            ".flowguard/models/owners/b/helper.py": "VALUE = 1\n",
            ".flowguard/verification/owners/b/run_checks.py": "raise SystemExit(0)\n",
            ".flowguard/verification/owners/c/run_checks.py": "raise SystemExit(0)\n",
        }
        for rel, text in contents.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.data = {
            "schema": "flowguard.map.v1", "project": "finite-impact", "layers": ["app"],
            "components": [
                {"id": cid, "layer": "app", "summary": cid, "responsibilities": [cid],
                 "files": [f"{cid}.py"], "depends_on": [chr(ord(cid) + 1)] if cid in "ab" else [],
                 "tests": [f"tests/test_{cid}.py"], "status": "draft",
                 "models": [f".flowguard/verification/owners/{cid}/run_checks.py"] if cid in "bc" else []}
                for cid in "abcd"
            ],
        }
        self._save()
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=FlowGuard fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "baseline")):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True)
        self.state = initial_state

    def _save(self) -> None:
        (self.root / ".flowguard/map.json").write_text(json.dumps(self.data), encoding="utf-8")

    def apply_step(self, step) -> ReplayObservation:
        from flowguard.map import cli
        from flowguard.map.impact import compute_impact
        from flowguard.map.inventory import build_inventory
        from flowguard.map.mapfile import ignore_patterns
        from flowguard.map.proof import run_models

        kind = step.function_input.kind
        paths = {"c_change": "c.py", "c_delete": "c.py",
                 "runner_change": ".flowguard/verification/owners/b/run_checks.py",
                 "runner_helper": ".flowguard/models/owners/b/helper.py",
                 "test_change": "tests/test_c.py", "binding_change": ".flowguard/map.json",
                 "unknown_source": "orphan.py"}
        changed = paths[kind]
        if kind == "c_delete":
            (self.root / changed).unlink()
        elif kind == "binding_change":
            self.data["components"][1]["tests"].append("tests/test_shared.py")
            self._save()
        elif kind == "unknown_source":
            (self.root / changed).write_text("VALUE = 0\n", encoding="utf-8")
        else:
            with (self.root / changed).open("a", encoding="utf-8") as stream:
                stream.write("# changed\n")
        impact = compute_impact(self.root, self.data, build_inventory(self.root, ignore_patterns(self.data)),
                                [changed], base="HEAD")
        blocked = bool(impact.unmapped or impact.blocked)
        model_ids = tuple(sorted(impact.model_ids))
        if model_ids and not blocked:
            results = run_models(self.root, list(model_ids))
            # Confirm the selected command identities are exactly what the runner executes.
            model_ids = tuple(sorted(result.model for result in results if result.status == "pass"))
        if kind == "unknown_source":
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = cli.main(["--root", str(self.root), "impact", changed])
            blocked = blocked and exit_code != 0
        self.state = State(kind, tuple(sorted(set(impact.direct + impact.dependents))),
                           tuple(impact.tests), model_ids, blocked)
        output = "blocked" if blocked else "selected"
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=self.state)

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None

    def close(self) -> None:
        self.directory.cleanup()


def conformance():
    """Replay the seven finite changes on real selection and tiny registered runners."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealSelection()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
