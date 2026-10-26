"""Parallel model runs retain registry order and the sequential verdicts."""
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "model_runs"
PARENT = "map-proof"
IMPLEMENTED_BY = {"RunModels": "flowguard/map/proof.py:run_models"}
TESTED_BY = {"parallel_output_in_registry_order": ["tests/test_flowguard_map_proof.py:test_jobs_output_equals_sequential"]}


@dataclass(frozen=True)
class State:
    order: tuple = ()


class Run:
    name = "RunModels"
    reads = ()
    writes = ("order",)

    def __init__(self, reversed_order=False):
        self.reversed_order = reversed_order

    def apply(self, event, state):
        order = ("second", "first") if self.reversed_order else ("first", "second")
        return (FunctionResult(order, State(order), label="run"),)


INVARIANTS = (Invariant("parallel_output_in_registry_order", "completion order never reorders registered models",
          lambda s, t: InvariantResult.pass_() if not s.order or s.order == ("first", "second")
          else InvariantResult.fail("registry order changed")),)


def _explorer(reversed_order=False):
    return Explorer(Workflow((Run(reversed_order),)), (State(),), ("run",), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"orders_by_completion": _explorer(True)}


def make_fixture(root, *, wrong_second=False):
    directory = root / ".flowguard/models"
    directory.mkdir(parents=True)
    (root / "native.py").write_text(f"def first_value(): return 1\ndef second_value(): return {2 if wrong_second else 1}\n")
    for name, delay in (("first", 0.12), ("second", 0)):
        source = '''from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
from pathlib import Path
import time
MODEL_ID = {name!r}
PARENT = "app"
IMPLEMENTED_BY = {{"Run": "native.py:{name}_value"}}
RULE = Invariant("one", "one is the allowed answer", lambda s,t: InvariantResult.pass_() if s == 1 else InvariantResult.fail("two"))
class Run:
    name = "Run"
    def __init__(self, value=1): self.value = value
    def apply(self, event, state): return (FunctionResult(self.value, self.value),)
def make(value): return Explorer(Workflow((Run(value),)), (1,), ("run",), invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {{"two": make(2)}}
def conformance():
    time.sleep({delay})
    actual = load_anchor(IMPLEMENTED_BY["Run"], root=Path.cwd())()
    return CodeFactsReport((Fact("native_value", actual == 1, repr(actual)),))
'''.format(name=name, delay=delay)
        (directory / (name + ".py")).write_text(source)
    comp = {"id": "app", "summary": "Two independent native values", "responsibilities": ["Compute values"],
            "files": ["native.py"], "models": [".flowguard/models/first.py", ".flowguard/models/second.py"],
            "status": "draft"}
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [comp]}))


def conformance():
    from flowguard.map.proof import run_models
    facts = []
    for wrong in (False, True):
        with TemporaryDirectory(prefix="fg-model-runs-") as directory:
            root = Path(directory)
            make_fixture(root, wrong_second=wrong)
            try:
                sequential = run_models(root, [], jobs=1)
                parallel = run_models(root, [], jobs=2)
            except TypeError as exc:
                return CodeFactsReport((Fact("native_jobs", False, str(exc)),))
            expected = [("first", "pass"), ("second", "fail" if wrong else "pass"), ("system", "pass")]
            first = [(r.model, r.status) for r in sequential]
            second = [(r.model, r.status) for r in parallel]
            facts.append(Fact(f"registry_order_{wrong}", first == second == expected, repr((first, second))))
    return CodeFactsReport(tuple(facts))
