"""Executable model: a map component's description is never reported current after its code changed.

The fingerprint written by ``confirm`` is the component's "current pointer".
Protected failures:
  * check reports a confirmed component as clean although its files changed
  * confirm accepts a component that has no description
Conformance replays model traces against the real flowguard.map implementation
in a throw-away project directory.
"""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "component_pointer"
COMPONENTS = ["map-file", "map-analysis"]
IMPLEMENTED_BY = {
    "Confirm": "flowguard/map/cli.py:cmd_confirm",
    "Check": "flowguard/map/check.py:run_check",
    "Fingerprint": "flowguard/map/mapfile.py:fingerprint",
}

MAX_EDITS = 2


@dataclass(frozen=True)
class Event:
    kind: str                       # edit | describe | confirm | check


@dataclass(frozen=True)
class State:
    status: str = "draft"           # draft | confirmed
    described: bool = False         # summary and responsibilities filled in
    code_version: int = 0           # how many times the owned file changed
    confirmed_version: int = -1     # code_version captured by the last successful confirm
    last_report: str = ""           # draft | stale | clean (from the last check)


class Step:
    """Intended behavior of edit / describe / confirm / check."""

    name = "Step"
    reads = ("status", "described", "code_version", "confirmed_version")
    writes = ("status", "described", "code_version", "confirmed_version", "last_report")

    def confirm_allowed(self, state: State) -> bool:
        return state.described

    def report(self, state: State) -> str:
        if state.status == "draft":
            return "draft"
        return "clean" if state.confirmed_version == state.code_version else "stale"

    def apply(self, event: Event, state: State):
        if event.kind == "edit":
            if state.code_version >= MAX_EDITS:                 # keep the explored space finite
                return (FunctionResult("edit_limit", state, label="edit_limit"),)
            # an earlier check result says nothing about the new code
            return (FunctionResult("edited", replace(state, code_version=state.code_version + 1, last_report=""),
                                   label="edit"),)
        if event.kind == "describe":
            return (FunctionResult("described", replace(state, described=True), label="describe"),)
        if event.kind == "confirm":
            if not self.confirm_allowed(state):
                return (FunctionResult("refused", state, label="confirm_refused"),)
            return (FunctionResult("confirmed", replace(state, status="confirmed", confirmed_version=state.code_version),
                                   label="confirm"),)
        report = self.report(state)
        return (FunctionResult(report, replace(state, last_report=report), label=f"check_{report}"),)


class ConfirmWithoutDescription(Step):
    """Known-bad: confirm does not require a description."""

    def confirm_allowed(self, state: State) -> bool:
        return True


class CheckIgnoresChanges(Step):
    """Known-bad: check reports every confirmed component as clean."""

    def report(self, state: State) -> str:
        return "draft" if state.status == "draft" else "clean"


def _clean_means_current(state: State, trace) -> InvariantResult:
    if state.last_report == "clean" and state.confirmed_version != state.code_version:
        return InvariantResult.fail("check reported clean after the owned file changed")
    return InvariantResult.pass_()


def _confirmed_means_described(state: State, trace) -> InvariantResult:
    if state.status == "confirmed" and not state.described:
        return InvariantResult.fail("a component without description was confirmed")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("clean_means_current", "clean is reported only when the code is unchanged since confirm", _clean_means_current),
    Invariant("confirmed_means_described", "confirm requires summary and responsibilities", _confirmed_means_described),
)
EVENTS = tuple(Event(kind) for kind in ("edit", "describe", "confirm", "check"))


def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=5, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Step())


def broken_variants() -> dict:
    return {"confirm_without_description": _explorer(ConfirmWithoutDescription()),
            "check_ignores_changes": _explorer(CheckIgnoresChanges())}


class _RealMap:
    """Drives the real flowguard.map code in a temporary project with one component."""

    def reset(self, initial_state: State) -> None:
        from flowguard.map import cli
        self.cli = cli
        self.root = Path(tempfile.mkdtemp(prefix="fg-pointer-"))
        (self.root / "app").mkdir()
        self.code_version = 0
        self.version_of: dict[str, int] = {}
        self._write_code()
        self._run("scan")
        data = self._map()
        data["components"] = [dict(data["components"][0], id="app", files=["app/*.py"], summary="",
                                   responsibilities=[], depends_on=[], tests=[])]
        self._save(data)
        self.last_report = ""

    def _write_code(self) -> None:
        (self.root / "app" / "core.py").write_text(f"VERSION = {self.code_version}\n", encoding="utf-8")
        from flowguard.map.mapfile import fingerprint
        self.version_of[fingerprint(self.root, ["app/core.py"])] = self.code_version

    def _run(self, *argv: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.cli.main(["--root", str(self.root), *argv])

    def _map(self) -> dict:
        return json.loads((self.root / ".flowguard" / "map.json").read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        (self.root / ".flowguard" / "map.json").write_text(json.dumps(data), encoding="utf-8")

    def apply_step(self, step) -> ReplayObservation:
        kind = step.function_input.kind
        if kind == "edit":
            if self.code_version >= MAX_EDITS:
                output = "edit_limit"
            else:
                self.code_version += 1
                self._write_code()
                self.last_report = ""
                output = "edited"
        elif kind == "describe":
            data = self._map()
            data["components"][0].update(summary="the app", responsibilities=["run the app"])
            self._save(data)
            output = "described"
        elif kind == "confirm":
            output = "confirmed" if self._run("confirm", "app") == 0 else "refused"
        else:
            from flowguard.map.check import run_check
            from flowguard.map.inventory import build_inventory
            from flowguard.map.mapfile import ignore_patterns, load_map
            data = load_map(self.root)
            codes = {f.code for f in run_check(self.root, data, build_inventory(self.root, ignore_patterns(data)))}
            output = "draft" if "draft" in codes else "stale" if "stale" in codes else "clean"
            self.last_report = output
        return ReplayObservation(function_name=step.function_name, observed_output=output,
                                 observed_state=self.observe_state())

    def observe_state(self) -> State:
        comp = self._map()["components"][0]
        confirmed = comp["status"] == "confirmed"
        return State(status=comp["status"], described=bool(comp.get("summary") and comp.get("responsibilities")),
                     code_version=self.code_version,
                     confirmed_version=self.version_of.get(comp.get("fingerprint", ""), -1) if confirmed else -1,
                     last_report=self.last_report)

    def observe_output(self):
        return None


def conformance():
    """Replay traces covering every modeled transition against the real implementation."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        last = replay_trace(trace=trace, adapter=_RealMap(), invariants=INVARIANTS,
                            rules=(projected_state_matches(), projected_output_matches()))
        if not last.ok:
            return last
    return last
