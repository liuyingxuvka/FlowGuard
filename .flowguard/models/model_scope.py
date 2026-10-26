"""Owned anchors stay in the home and declared scopes; read-only bindings own nothing."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "model_scope"
PARENT = "map-file"
IMPLEMENTED_BY = {"Scope": "flowguard/map/tree.py:scope_findings"}
USES = {"BuildTree": "flowguard/map/tree.py:build_tree"}
TESTED_BY = {
    "anchor_inside_scope": ["tests/test_flowguard_map_contracts.py:test_anchor_scope_same_with_or_without_parent",
                            "tests/test_flowguard_map_contracts.py:test_anchor_outside_home_names_common_ancestor"],
    "verdict_independent_of_parent_source": ["tests/test_flowguard_map_contracts.py:test_anchor_scope_same_with_or_without_parent",
                                            "tests/test_flowguard_map_contracts.py:test_model_ancestor_components_are_in_scope"],
    "uses_is_read_only": ["tests/test_flowguard_map_contracts.py:test_unused_uses_fails_and_is_not_coverage"],
}


@dataclass(frozen=True)
class State:
    case: str = ""
    outside: bool = False
    consistent: bool = True
    uses_owns: bool = False


class Scope:
    name = "Scope"
    reads = ()
    writes = ("case", "outside", "consistent", "uses_owns")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        new = State(event, outside=event == "placement")
        if event == "placement" and self.defect == "checks_only_explicit_parent":
            new = replace(new, outside=False, consistent=False)
        if event == "placement" and self.defect == "verdict_depends_on_parent_source":
            new = replace(new, consistent=False)
        if event == "uses" and self.defect == "counts_uses_as_ownership":
            new = replace(new, uses_owns=True)
        return (FunctionResult(event, new, label=event),)


INVARIANTS = (
    Invariant("anchor_inside_scope", "the home and ancestor COMPONENTS delimit owned anchors",
              lambda s,t: InvariantResult.pass_() if s.case not in {"placement", "ancestor"}
              or s.outside == (s.case == "placement") else InvariantResult.fail("owned anchor has the wrong scope verdict")),
    Invariant("verdict_independent_of_parent_source", "an explicit PARENT cannot change the verdict",
              lambda s,t: InvariantResult.pass_() if s.consistent else InvariantResult.fail("parent syntax changed the verdict")),
    Invariant("uses_is_read_only", "a USES anchor adds no ownership",
              lambda s,t: InvariantResult.fail("read-only dependency became owned") if s.uses_owns else InvariantResult.pass_()),
)


def _explorer(defect=""):
    return Explorer(Workflow((Scope(defect),)), (State(),), ("placement", "ancestor", "uses"),
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("checks_only_explicit_parent", "verdict_depends_on_parent_source", "counts_uses_as_ownership")}


CONTRACT = '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "m"
COMPONENTS = ["app"]
PARENT = "app"
IMPLEMENTED_BY = {"Own": "app.py:value"}
TESTED_BY = {}
class Value:
    name = "Own"
    def __init__(self,value): self.value=value
    def apply(self,event,state): return (FunctionResult(self.value,self.value),)
RULE = Invariant("one_value", "the native value is one", lambda s,t: InvariantResult.pass_() if s in (0,1) else InvariantResult.fail("wrong value"))
def make(value): return Explorer(Workflow((Value(value),)), (0,), ("value",), invariants=(RULE,), max_sequence_length=1,progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {"two":make(2)}
def conformance():
    value = load_anchor(IMPLEMENTED_BY["Own"],root=Path.cwd())()
    return CodeFactsReport((Fact("native_value",value==1,repr(value)),))
'''


def scope_fixture(root, case):
    """Build the same real ownership tree with explicit/implicit home or a read-only use."""
    from flowguard.map.inventory import build_inventory
    from flowguard.map.tree import build_tree
    root.mkdir(parents=True, exist_ok=True)
    models = root / ".flowguard/models"
    models.mkdir(parents=True)
    for name in ("app", "lib"):
        (root / (name + ".py")).write_text("def value(): return 1\n")
    components = [dict(id="base", layer="core", summary="Base group", responsibilities=["group native values"],
                       files=[], tests=[], models=[], status="draft")]
    components += [dict(id=name, parent="base", layer="core", summary=name, responsibilities=["provide " + name + " values"],
                        files=[name + ".py"], tests=[], models=[], entrypoints=[name + ".py:value"], status="draft")
                   for name in ("app", "lib")]
    data = dict(schema="flowguard.map.v1", layers=["core"], components=components)
    source = CONTRACT
    if case == "ancestor":
        source = source.replace("from pathlib import Path", "from pathlib import Path\nfrom dataclasses import dataclass")
        source = source.replace("class Value:", '@dataclass(frozen=True)\nclass ValueState:\n    value: int = 0\n    received: int = 0\nOUTPUTS = {"value": (1,)}\nclass Value:')
        source = source.replace('    name = "Own"', '    name = "Own"\n    writes = ("value", "received")')
        source = source.replace('FunctionResult(self.value,self.value)', 'FunctionResult(self.value,ValueState(self.value,self.value))')
        source = source.replace('if s in (0,1)', 'if s.value in (0,1)').replace('(0,), ("value",)', '(ValueState(),), ("value",)')
    if case in {"explicit", "implicit", "ancestor"}:
        source = source.replace('"Own": "app.py:value"', '"Own": "lib.py:value"')
    if case == "implicit":
        source = source.replace('PARENT = "app"\n', '')
    elif case == "ancestor":
        source = source.replace('PARENT = "app"', 'PARENT = "p"')
        parent = source.replace('MODEL_ID = "m"', 'MODEL_ID = "p"').replace('COMPONENTS = ["app"]', 'COMPONENTS = ["app", "lib"]').replace('PARENT = "p"', 'PARENT = "app"').replace('"Own": "lib.py:value"', '"Own": "app.py:value"')
        parent += '\nHANDOFF = {"m": {"value": "received"}}\nKEEPS = ("value",)\n'
        (models / "p.py").write_text(parent)
    elif case == "uses":
        source += '\nUSES = {"Read": "lib.py:value"}\n'
    elif case != "explicit":
        raise ValueError(case)
    (models / "m.py").write_text(source)
    (root / ".flowguard/map.json").write_text(json.dumps(data))
    inv = build_inventory(root, [], write_cache=False)
    tree = build_tree(root, data, inv)
    return data, inv, tree


def conformance():
    facts, outcomes = [], {}
    with TemporaryDirectory(prefix="fg-scope-") as folder:
        for case in ("explicit", "implicit", "ancestor", "uses"):
            _, _, tree = scope_fixture(Path(folder) / case, case)
            outside = any(f.code == "anchor_outside_home" for f in tree.findings)
            outcomes[case] = outside
            if case == "uses":
                facts.append(Fact("uses_is_read_only", "lib" not in tree.nodes["m"].components,
                                  repr(tree.nodes["m"].components)))
            else:
                facts.append(Fact("scope_" + case, outside == (case != "ancestor"), repr(tree.findings)))
        facts.append(Fact("parent_source", outcomes["explicit"] == outcomes["implicit"], repr(outcomes)))
    return CodeFactsReport(tuple(facts))
