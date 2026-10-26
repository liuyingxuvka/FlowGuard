"""Read counts real bindings and separates bound, calling and unrelated tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "read_show"
PARENT = "map-read"
IMPLEMENTED_BY = {"Header": "flowguard/map/views.py:_show_header", "Coverage": "flowguard/map/facets.py:coverage_line"}
USES = {"Show": "flowguard/map/views.py:render_show", "TestCalls": "flowguard/map/testtree.py:test_calls"}
TESTED_BY = {"coverage_counts_only_bound": ["tests/test_map_views.py:test_coverage_counts_calls_not_words"],
             "tests_line_counts_bound_and_unbound": ["tests/test_map_views.py:test_tests_line_counts_bound_calling_and_neither"]}
RULES = (Invariant("coverage_counts_only_bound", "words do not count as calls", lambda s,t: s[0] == 2),
         Invariant("tests_line_counts_bound_and_unbound", "one bound, two calling and one unrelated test", lambda s,t: s[1:] == (1,2,1)))
class Show:
    name = "Show"
    def __init__(self, fault=""): self.fault = fault
    def apply(self, event, state):
        value = (3 if self.fault == "words" else 2, 3 if self.fault == "binding" else 1, 2, 1)
        return (FunctionResult(value, value),)
def _explorer(fault=""):
    return Explorer(Workflow((Show(fault),)), ((2,1,2,1),), ("show",), invariants=RULES, max_sequence_length=1, progress_steps=0)
def build_explorer(): return _explorer()
def broken_variants(): return {"counts_docstring_mention_as_test": _explorer("words"), "counts_unbound_as_bound": _explorer("binding")}
def make_fixture(root):
    files = {"app.py": "def modeled(): return True\ndef called(): return True\ndef mentioned(): return True\ndef reasoned(): return True\n",
             "tests/test_app.py": "from app import modeled, called\nimport unittest\ndef test_bound(): assert modeled()\ndef test_call(): assert called() and modeled()\ndef test_words():\n    '''mentioned() is only prose'''\n    assert True\nclass Base(unittest.TestCase): pass\nclass Suite(Base):\n    def test_method(self): assert called() and modeled()\n",
             ".flowguard/models/probe.py": '"""Probe."""\nMODEL_ID="probe"\nPARENT="app"\nIMPLEMENTED_BY={"Run":"app.py:modeled"}\nNOT_MODELED={"app.py:reasoned":"deliberate no-op"}\nTESTED_BY={"works":["tests/test_app.py:test_bound"]}\ndef build_explorer(): pass\n'}
    for rel, text in files.items():
        path = root/rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    data = dict(schema="flowguard.map.v1",project="fixture",components=[dict(id="app",summary="Four entrypoints", responsibilities=["Serve"],files=["app.py"],tests=["tests/test_app.py"],entrypoints=["app.py:"+name for name in ("modeled","called","mentioned","reasoned")],models=[],status="draft")])
    (root/".flowguard/map.json").write_text(json.dumps(data))
    return data

def conformance():
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix="fg-read-show-") as directory:
        root=Path(directory); data=make_fixture(root)
        inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
        text=render_show(root,data,inv,component=None,detail=False,budget=8000)
        return CodeFactsReport((Fact("bound_coverage", "coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted;" in text,text),
            Fact("test_counts", "tests: 4 test functions; 1 bound to a model (TESTED_BY), 2 call a model's code, 1 neither" in text,text)))
