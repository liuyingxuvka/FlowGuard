"""Review closes one explained suggestion and counts the accepted decision."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "read_review"
PARENT = "map-read"
IMPLEMENTED_BY = {"Candidates": "flowguard/map/review.py:_candidates"}
USES = {"Review": "flowguard/map/review.py:render_review"}
TESTED_BY = {"closed_suggestion_is_counted": ["tests/test_map_views.py:test_closing_debt_hides_one_suggestion"]}
RULES = (Invariant("closed_suggestion_is_counted", "the closed suggestion disappears and the decision is counted",lambda s,t: s == (False,1)),)
class Review:
    name="Review"
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state):
        observed=(self.bad,0 if self.bad else 1)
        return (FunctionResult(observed,observed),)
def _explorer(bad=False): return Explorer(Workflow((Review(bad),)),((False,1),),("review",),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return _explorer()
def broken_variants(): return {"closed_suggestion_reappears": _explorer(True)}
def make_fixture(root):
    (root/"app.py").write_text('def run(): return True\n')
    (root/".flowguard").mkdir(exist_ok=True)
    data=dict(schema="flowguard.map.v1",project="review",components=[dict(id="app",summary="Text templates",responsibilities=["Serve templates"],files=["app.py"],state=["text"],models=[],tests=[],status="draft")],accepted_debts=[dict(code="unmodeled_owner",component="app",reason="static text; no state to explore")])
    (root/".flowguard/map.json").write_text(json.dumps(data)); return data

def conformance():
    from flowguard.map.review import render_review
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix="fg-read-review-") as folder:
        root=Path(folder);data=make_fixture(root);inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
        text=render_review(root,data,inv)
        return CodeFactsReport((Fact("closed_count", "model app:" not in text and "declined: 1 (accepted debts; 0 no longer arise)" in text,text),))
