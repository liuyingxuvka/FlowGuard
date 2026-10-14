"""Executable model: the proof cache never reports a result that is not true for the current bytes.

``python -m flowguard.map models`` caches passing model results keyed by the
model file, mapped component/dependency inputs, implementation anchors and engine.
Protected failures:
  * a cached PASS is served after the implementation changed and became wrong
  * a FAIL is cached and keeps being reported after the implementation was fixed
  * a helper becomes wrong while the directly anchored implementation stays unchanged
Conformance drives the real flowguard.map.proof against a tiny project whose
implementation can be switched between a correct and a buggy version.
"""

from __future__ import annotations

import shutil
import json
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "model_cache"
COMPONENTS = ["map-proof"]
IMPLEMENTED_BY = {"Run": "flowguard/map/proof.py:run_models", "Key": "flowguard/map/proof.py:_input_key"}

MAX_EDITS = 2


@dataclass(frozen=True)
class Event:
    kind: str                       # edit_ok | edit_bug | edit_helper_bug | run | run_force


@dataclass(frozen=True)
class State:
    impl_version: int = 0
    impl_buggy: bool = False
    helper_buggy: bool = False
    cached_version: int = -1        # implementation version of the cached PASS, -1 when nothing is cached
    last_result: str = ""           # pass | fail
    last_cached: bool = False


class Step:
    name = "Step"
    reads = ("impl_version", "impl_buggy", "helper_buggy", "cached_version")
    writes = ("impl_version", "impl_buggy", "helper_buggy", "cached_version", "last_result", "last_cached")

    def cache_hit(self, state: State) -> bool:
        return state.cached_version == state.impl_version

    def store(self, state: State, result: str) -> int:
        return state.impl_version if result == "pass" else -1

    def apply(self, event: Event, state: State):
        if event.kind in ("edit_ok", "edit_bug", "edit_helper_bug"):
            if state.impl_version >= MAX_EDITS:
                return (FunctionResult("edit_limit", state, label="edit_limit"),)
            new = replace(state, impl_version=state.impl_version + 1,
                          impl_buggy=state.impl_buggy if event.kind == "edit_helper_bug" else event.kind == "edit_bug",
                          helper_buggy=event.kind == "edit_helper_bug",
                          last_result="", last_cached=False)
            return (FunctionResult("edited", new, label=event.kind),)
        if event.kind == "run" and self.cache_hit(state):
            return (FunctionResult("pass", replace(state, last_result="pass", last_cached=True), label="cache_hit"),)
        result = "fail" if state.impl_buggy or state.helper_buggy else "pass"
        new = replace(state, cached_version=self.store(state, result), last_result=result, last_cached=False)
        return (FunctionResult(result, new, label=f"executed_{result}"),)


class KeyIgnoresImplementation(Step):
    """Known-bad: a cached pass is reused whatever the implementation bytes are."""

    def cache_hit(self, state: State) -> bool:
        return state.cached_version >= 0


class CachesFailures(Step):
    """Known-bad: failures are cached, so a fixed implementation keeps reporting fail."""

    def cache_hit(self, state: State) -> bool:
        return state.cached_version == state.impl_version or state.cached_version < -1

    def store(self, state: State, result: str) -> int:
        return state.impl_version if result == "pass" else -2 - state.impl_version

    def apply(self, event: Event, state: State):
        if event.kind == "run" and state.cached_version == -2 - state.impl_version:
            return (FunctionResult("fail", replace(state, last_result="fail", last_cached=True), label="cached_fail"),)
        if event.kind == "run" and state.cached_version < -1 and not state.impl_buggy:
            return (FunctionResult("fail", replace(state, last_result="fail", last_cached=True), label="stale_fail"),)
        return super().apply(event, state)


class KeyIgnoresHelper(Step):
    """Known-bad: helper bytes are omitted from an otherwise valid cache key."""

    def cache_hit(self, state: State) -> bool:
        return state.cached_version >= 0 if state.helper_buggy else super().cache_hit(state)


def _result_is_true(state: State, trace) -> InvariantResult:
    truth = "fail" if state.impl_buggy or state.helper_buggy else "pass"
    if state.last_result and state.last_result != truth:
        return InvariantResult.fail(f"reported {state.last_result} but the current implementation would {truth}")
    return InvariantResult.pass_()


INVARIANTS = (Invariant("result_is_true", "a reported model result is true for the current bytes", _result_is_true),)
EVENTS = tuple(Event(kind) for kind in ("edit_ok", "edit_bug", "edit_helper_bug", "run", "run_force"))


def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=5, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Step())


def broken_variants() -> dict:
    return {"key_ignores_implementation": _explorer(KeyIgnoresImplementation()),
            "caches_failures": _explorer(CachesFailures()), "key_ignores_helper": _explorer(KeyIgnoresHelper())}


_TARGET_MODEL = '''
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from app.impl import ok

MODEL_ID = "target"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Check": "app/impl.py:ok"}


class Check:
    name = "Check"
    def apply(self, value, state):
        return (FunctionResult("checked", ok(), label="checked"),)


def _ok(state, trace):
    return InvariantResult.pass_() if state else InvariantResult.fail("implementation reports failure")


def build_explorer():
    return Explorer(workflow=Workflow((Check(),)), initial_states=(True,), external_inputs=(1,),
                    invariants=(Invariant("ok", "ok", _ok),), max_sequence_length=1, progress_steps=0)
'''


class _RealProof:
    """Drives the real flowguard.map.proof cache in a temporary project."""

    def reset(self, initial_state: State) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="fg-cache-"))
        (self.root / "app").mkdir()
        (self.root / "app" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / ".flowguard" / "models").mkdir(parents=True)
        (self.root / ".flowguard" / "models" / "target.py").write_text(_TARGET_MODEL, encoding="utf-8")
        from flowguard.map.common import SCHEMA
        data = {"schema": SCHEMA, "components": [{"id": "app", "files": ["app/*.py"],
                "depends_on": [], "status": "draft", "models": [".flowguard/models/target.py"]}]}
        (self.root / ".flowguard" / "map.json").write_text(json.dumps(data), encoding="utf-8")
        self.version, self.buggy, self.helper_buggy, self.last = 0, False, False, ("", False)
        self.version_of_key: dict[str, int] = {}
        self._write_impl()
        self._write_helper()

    def _current_key(self) -> str:
        from flowguard.map.mapfile import read_model_contract
        from flowguard.map.proof import _input_key
        path = self.root / ".flowguard" / "models" / "target.py"
        return _input_key(self.root, path, read_model_contract(path))

    def _write_impl(self) -> None:
        value = "False" if self.buggy else "True"
        (self.root / "app" / "impl.py").write_text(f"from app.helper import ok as helper_ok\nVERSION = {self.version}\n\ndef ok():\n    return {value} and helper_ok()\n",
                                                   encoding="utf-8")
        self.version_of_key[self._current_key()] = self.version

    def _write_helper(self) -> None:
        value = "False" if self.helper_buggy else "True"
        (self.root / "app" / "helper.py").write_text(f"def ok():\n    return {value}\n", encoding="utf-8")
        self.version_of_key[self._current_key()] = self.version

    def apply_step(self, step) -> ReplayObservation:
        from flowguard.map.proof import run_models
        kind = step.function_input.kind
        if kind in ("edit_ok", "edit_bug", "edit_helper_bug"):
            if self.version >= MAX_EDITS:
                output = "edit_limit"
            else:
                self.version, self.last = self.version + 1, ("", False)
                if kind == "edit_helper_bug":
                    self.helper_buggy = True
                else:
                    self.buggy, self.helper_buggy = kind == "edit_bug", False
                    self._write_impl()
                self._write_helper()
                output = "edited"
        else:
            result = run_models(self.root, [], force=kind == "run_force")[0]
            output = "pass" if result.status == "pass" else "fail"
            self.last = (output, result.cached)
        return ReplayObservation(function_name=step.function_name, observed_output=output,
                                 observed_state=self.observe_state())

    def observe_state(self) -> State:
        cache_file = self.root / ".flowguard" / "cache" / "models.json"
        cached = json.loads(cache_file.read_text(encoding="utf-8"))["models"] if cache_file.is_file() else {}
        key = cached.get("target.py", {}).get("key")
        return State(impl_version=self.version, impl_buggy=self.buggy,
                     helper_buggy=self.helper_buggy,
                     cached_version=self.version_of_key.get(key, -1) if key else -1,
                     last_result=self.last[0], last_cached=self.last[1])

    def observe_output(self):
        return None

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def conformance():
    """Replay five failure-mode witnesses; exhaustive state exploration stays abstract.

    Cover direct/helper invalidation, repair after failure, force/cache and the
    finite edit limit without replaying every equivalent version combination.
    """
    scenarios = {
        ("run", "run", "edit_bug", "run", "run_force"),
        ("edit_bug", "run", "edit_ok", "run", "run"),
        ("run", "edit_helper_bug", "run", "run_force"),
        ("edit_ok", "edit_ok", "edit_bug", "run"),
        ("run_force", "run"),
    }
    witnesses = {tuple(event.kind for event in trace.external_inputs): trace
                 for trace in build_explorer().explore().traces
                 if tuple(event.kind for event in trace.external_inputs) in scenarios}
    if set(witnesses) != scenarios:
        raise RuntimeError("cache conformance is missing a declared failure-mode witness")
    last = None
    for scenario in sorted(scenarios):
        trace = witnesses[scenario]
        adapter = _RealProof()
        last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                            rules=(projected_state_matches(), projected_output_matches()))
        adapter.close()
        if not last.ok:
            return last
    return last
