"""Find ranks the full requested symbol and the component's actual duty."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "read_find"
PARENT = "map-read"
IMPLEMENTED_BY = {"DefinedSymbols": "flowguard/map/views.py:defined_symbols", "Locate": "flowguard/map/views.py:render_locate"}
USES = {"Find": "flowguard/map/views.py:find_owners"}
TESTED_BY = {
    "locate_prefers_owner": ["tests/test_map_views.py:test_locate_prefers_the_owner_over_a_deeper_reacher"],
    "test_location_shows_models_and_code": ["tests/test_map_views.py:test_locate_bound_test_shows_model_rule_and_code"],
    "find_view_within_budget": ["tests/test_map_views.py:test_locate_output_within_budget"],
    "find_ranks_duty_owner_first": ["tests/test_map_views.py:test_find_bonus_needs_the_joined_query"],
    "find_exact_symbol_first": ["tests/test_map_views.py:test_find_ranks_the_component_that_defines_an_exact_symbol_first"],
}
QUERIES = {"duty": "promote target", "exact": "find_owners"}


@dataclass(frozen=True)
class State:
    case: str = ""
    winner: str = ""
    size: int = 0


class Rank:
    name = "DefinedSymbols"
    reads = ()
    writes = ("case", "winner")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        if event in LOCATIONS: return (FunctionResult(event,state),)
        wrong = event == "duty" and self.defect == "bonus_per_query_word" or event == "exact" and self.defect == "ignores_exact_symbol"
        return (FunctionResult(event, State(event, "generic" if wrong else "duty"), label=event),)


from _locate_fixture import CASES as LOCATIONS
EXPECTED_LOCATIONS={"owned":"owner","reached":"none","unowned":"none","bound":"bound","unbound":"unbound","file":"file","unknown":"unknown"}
class Locate:
    name="Locate"
    reads=()
    writes=("case","winner","size")
    def __init__(self,defect=""):self.defect=defect
    def apply(self,event,state):
        if event not in LOCATIONS:return (FunctionResult(event,state),)
        winner=EXPECTED_LOCATIONS[event]
        if self.defect=="deepest_reacher_first" and event in ("owned","reached"):winner="deeper"
        if self.defect=="test_location_unknown_symbol" and event in ("bound","unbound","file"):winner="unknown"
        size=3000 if self.defect=="find_view_exceeds_budget" else 150
        return (FunctionResult(event,State(event,winner,size)),)


INVARIANTS = (
    Invariant("locate_prefers_owner","ownership wins over a deeper reacher",lambda s,t:s.case not in ("owned","reached","unowned") or s.winner==EXPECTED_LOCATIONS[s.case]),
    Invariant("test_location_shows_models_and_code","test locations show bindings, calls and owning code",lambda s,t:s.case not in ("bound","unbound","file") or s.winner==EXPECTED_LOCATIONS[s.case]),
    Invariant("find_view_within_budget","each actual find view is within 2000 characters",lambda s,t:s.case not in LOCATIONS or s.size<=2000),
    Invariant("find_ranks_duty_owner_first", "an incidental single-word symbol cannot outrank the whole requested duty",
              lambda s,t: InvariantResult.fail("incidental symbol won") if s.case == "duty" and s.winner != "duty" else InvariantResult.pass_()),
    Invariant("find_exact_symbol_first", "a whole symbol query ranks its actual definition first",
              lambda s,t: InvariantResult.fail("exact symbol lost") if s.case == "exact" and s.winner != "duty" else InvariantResult.pass_()),
)


def _explorer(defect=""):
    return Explorer(Workflow((Rank(defect),Locate(defect))), (State(),), tuple(QUERIES)+tuple(LOCATIONS), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer(): return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("bonus_per_query_word", "ignores_exact_symbol", "deepest_reacher_first", "test_location_unknown_symbol", "find_view_exceeds_budget")}


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
        from _locate_fixture import fixture,observe
        project=Path(folder)/"locations";fixture(project)
        for case in LOCATIONS:
            status,text=observe(project,case)
            correct=(status==1 and text.startswith("no symbol") if case=="unknown" else
                     status==0 and text.startswith("locate ") and "model owner (owned: Run)" in text if case=="owned" else
                     status==0 and text.startswith("no model owns") if case in ("reached","unowned") else
                     status==0 and "bound to: owner (rule safe)" in text and "api.py:owned" in text if case=="bound" else
                     status==0 and "bound to: none (unbound)" in text and "next: bind it in owner's TESTED_BY" in text if case=="unbound" else
                     status==0 and "bound: owner 1; unbound 2" in text)
            facts.append(Fact("locate_"+case,correct and len(text)<=2000,text))
        return CodeFactsReport(tuple(facts))
