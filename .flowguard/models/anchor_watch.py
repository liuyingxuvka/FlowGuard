"""Observe real conformance calls across threads without observing abstract exploration."""
from contextlib import chdir
from dataclasses import dataclass
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "anchor_watch"
PARENT = 'model_runs'
IMPLEMENTED_BY = {"Watch": "flowguard/map/facts.py:AnchorWatch"}
TESTED_BY = {'conformance_calls_are_seen': ['tests/test_anchor_watch.py:test_anchor_called_in_worker_thread_is_consulted'], 'explore_is_not_watched': ['tests/test_anchor_watch.py:test_anchor_called_only_in_explore_fails'], 'unconsulted_anchor_fails_the_model': ['tests/test_anchor_watch.py:test_anchor_called_only_in_explore_fails']}


@dataclass(frozen=True)
class State:
    case: str = ""
    seen: bool = False
    anchors: str = "never_ran"


class Watch:
    name = "Watch"
    reads = ()
    writes = ("case", "seen", "anchors")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        seen = event == "worker"
        if self.defect == "misses_worker_thread_call" and event == "worker": seen = False
        if self.defect == "watches_explore" and event == "explore": seen = True
        anchors="seen" if seen or event=="unconsulted" and self.defect=="passes_unconsulted_anchor" else "never_ran"
        return (FunctionResult(anchors, State(event, seen, anchors), label=event),)


INVARIANTS = (
    Invariant("unconsulted_anchor_fails_the_model", "an unconsulted anchor never receives credit", lambda s,t:s.case!="unconsulted" or s.anchors=="never_ran"),
    Invariant("conformance_calls_are_seen", "a conformance call from a worker thread is observed",
              lambda s,t: InvariantResult.fail("worker call missed") if s.case == "worker" and not s.seen else InvariantResult.pass_()),
    Invariant("explore_is_not_watched", "abstract-only execution cannot satisfy a native binding",
              lambda s,t: InvariantResult.fail("abstract call was credited") if s.case == "explore" and s.seen else InvariantResult.pass_()),
)


def _explorer(defect=""):
    return Explorer(Workflow((Watch(defect),)), (State(),State(anchors="seen")), ("worker", "explore", "unconsulted"), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer(): return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("misses_worker_thread_call", "watches_explore", "passes_unconsulted_anchor")}


MODEL_SOURCE = '''from pathlib import Path
import threading
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "watch_probe"
IMPLEMENTED_BY = {"Value": "NATIVE.py:ping"}
TESTED_BY = {}
class Value:
    name = "Value"
    def __init__(self, value): self.value = value
    def apply(self, event, state):
        ABSTRACT_CALL
        return (FunctionResult(self.value,self.value),)
RULE = Invariant("one_value", "one native value", lambda s,t: InvariantResult.pass_() if s in (0,1) else InvariantResult.fail("wrong value"))
def make(value): return Explorer(Workflow((Value(value),)), (0,), ("value",), invariants=(RULE,), max_sequence_length=1,progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {"two_values": make(2)}
def conformance():
    CONFORMANCE
'''


def make_probe(root, case):
    root.mkdir(parents=True, exist_ok=True)
    module = "native_" + case
    (root / (module + ".py")).write_text("def ping(): return 1\n")
    model = root / ".flowguard/models/probe.py"
    model.parent.mkdir(parents=True)
    source = MODEL_SOURCE.replace("NATIVE", module)
    source = source.replace("ABSTRACT_CALL", 'load_anchor(IMPLEMENTED_BY["Value"],root=Path.cwd())()' if case == "explore" else "pass")
    conformance = '''values = []
    native = load_anchor(IMPLEMENTED_BY["Value"],root=Path.cwd())
    worker = threading.Thread(target=lambda: values.append(native()))
    worker.start()
    worker.join()
    return CodeFactsReport((Fact("worker_value", values == [1], repr(values)),))'''
    if case == "explore": conformance = 'return CodeFactsReport((Fact("design_only", True),))'
    model.write_text(source.replace("CONFORMANCE", conformance))
    return model


def native_probe(root, case):
    from flowguard.map.proof import run_model_in_process
    model = make_probe(root, case)
    previous_path = sys.path[:]
    previous_modules = {name: module for name, module in sys.modules.items() if name.startswith(("native_", "_flowguard_model_"))}
    try:
        with chdir(root):
            return run_model_in_process(root, model)
    finally:
        sys.path[:] = previous_path
        for name in list(sys.modules):
            if name.startswith(("native_", "_flowguard_model_")) and name not in previous_modules:
                sys.modules.pop(name, None)
        sys.modules.update(previous_modules)


def conformance():
    facts = []
    with TemporaryDirectory(prefix="fg-watch-") as folder:
        for case in ("worker", "explore"):
            result = native_probe(Path(folder) / case, case)
            ok = result.status == "pass" if case == "worker" else result.status == "fail" and any("never ran" in p for p in result.problems)
            facts.append(Fact(case, ok, repr((result.status, result.problems))))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'anchors': ('seen', 'never_ran')}
