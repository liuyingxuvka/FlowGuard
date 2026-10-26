"""Focused component reads show one concise port line for each model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from _target_fixture import make_port_project, probe_port_model
MODEL_ID="read_component"
PARENT="map-read"
IMPLEMENTED_BY={"Facets":"flowguard/map/facets.py:component_facets"}
USES={"Show":"flowguard/map/views.py:render_show"}
TESTED_BY={"port_line_shown":["tests/test_map_views.py:test_read_component_prints_one_port_line_per_model"]}
RULES=(Invariant("port_line_shown","one concise port per model",lambda s,t:s),)
class Read:
    name="Read"
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state): return (FunctionResult(not self.bad,not self.bad),)
def make(bad=False): return Explorer(Workflow((Read(bad),)),(True,),("read",),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"hides_port_line":make(True)}
def conformance():
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_show
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix="fg-component-port-") as directory:
        root=Path(directory);data=make_port_project(root)
        inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
        text=render_show(root,data,inv,component="cli",detail=False,budget=8000)
        ports=[line.strip() for line in text.splitlines() if line.strip().startswith("port:")]
        models=[line for line in text.splitlines() if line.strip().startswith("model ")]
        return CodeFactsReport((Fact("ports_shown",len(ports)==len(models) and len(ports)>=2 and all(len(line)<=200 for line in ports),text),))
