"""Find ranks the full requested symbol and the component's actual duty."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "read_find"
PARENT = "map-read"
IMPLEMENTED_BY = {"DefinedSymbols": "flowguard/map/views.py:defined_symbols"}
USES = {"Find": "flowguard/map/views.py:find_owners"}
TESTED_BY = {
    "find_ranks_duty_owner_first": ["tests/test_map_views.py:test_find_bonus_needs_the_joined_query"],
    "find_exact_symbol_first": ["tests/test_map_views.py:test_find_ranks_the_component_that_defines_an_exact_symbol_first"],
}
QUERIES = {"duty": "promote target", "exact": "find_owners"}


@dataclass(frozen=True)
class State:
    case: str = ""
    winner: str = ""


class Rank:
    name = "DefinedSymbols"
    reads = ()
    writes = ("case", "winner")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        wrong = event == "duty" and self.defect == "bonus_per_query_word" or event == "exact" and self.defect == "ignores_exact_symbol"
        return (FunctionResult(event, State(event, "generic" if wrong else "duty"), label=event),)


INVARIANTS = (
    Invariant("find_ranks_duty_owner_first", "an incidental single-word symbol cannot outrank the whole requested duty",
              lambda s,t: InvariantResult.fail("incidental symbol won") if s.case == "duty" and s.winner != "duty" else InvariantResult.pass_()),
    Invariant("find_exact_symbol_first", "a whole symbol query ranks its actual definition first",
              lambda s,t: InvariantResult.fail("exact symbol lost") if s.case == "exact" and s.winner != "duty" else InvariantResult.pass_()),
)


def _explorer(defect=""):
    return Explorer(Workflow((Rank(defect),)), (State(),), tuple(QUERIES), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer(): return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("bonus_per_query_word", "ignores_exact_symbol")}


def make_fixture(root):
    from flowguard.map.inventory import build_inventory
    (root / "duty.py").write_text("def promote_target(): pass\ndef find_owners(): pass\n")
    (root / "generic.py").write_text("class Target: pass\n")
    data = {"schema": "flowguard.map.v1", "components": [
        {"id": "duty", "summary": "promote target", "responsibilities": ["promote target"], "files": ["duty.py"], "status": "draft"},
        {"id": "generic", "summary": "find owners", "responsibilities": ["find owners"], "files": ["generic.py"], "status": "draft"}]}
    return data, build_inventory(root, [], write_cache=False)


def conformance():
    from flowguard.map.views import find_owners
    with TemporaryDirectory(prefix="fg-find-") as folder:
        data, inv = make_fixture(Path(folder))
        facts = []
        for case, query in QUERIES.items():
            hits = find_owners(data, inv, query.split())
            facts.append(Fact(case, bool(hits) and hits[0][1] == "duty", repr(hits)))
        return CodeFactsReport(tuple(facts))
