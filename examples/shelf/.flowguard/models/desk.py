"""A desk receives the lending decision and tells the caller when borrowing is refused."""
from contextlib import redirect_stdout
from dataclasses import dataclass,replace
from io import StringIO
from pathlib import Path
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact,load_anchor
MODEL_ID = "desk"
PARENT = "cli"
IMPLEMENTED_BY = {"Main":"shelf/cli.py:main"}
HANDOFF = {"lending":{"answer":"answer"}}
KEEPS = ("request","reply")
TESTED_BY = {"refused_borrow_is_told":["tests/test_cli.py:test_main_tells_refused_borrow"]}
@dataclass(frozen=True)
class DeskState:
    request: str = ""
    answer: str = ""
    reply: str = ""
@dataclass(frozen=True)
class Request:
    request: str
    receipt: tuple
    @property
    def answer(self):return self.receipt[0]
class TakeRequest:
    name="TakeRequest"
    reads=()
    writes=("request",)
    def apply(self,event,state):return (FunctionResult(event,replace(state,request=event.request)),)
class Receive:
    name="Receive"
    reads=("request",)
    writes=("request","answer")
    def apply(self,event,state):return (FunctionResult(event.answer,replace(state,answer=event.answer),label=event.answer),)
class Reply:
    name="Reply"
    reads=("answer",)
    writes=("reply",)
    def __init__(self,bad=False):self.bad=bad
    def apply(self,value,state):
        reply="hidden" if self.bad and state.answer=="refused" else state.answer
        return (FunctionResult(reply,replace(state,reply=reply)),)
RULE = Invariant("refused_borrow_is_told","a refusal reaches the caller",lambda s,t:s.answer!="refused" or s.reply in ("","refused"))
def make(block):
    return Explorer(Workflow((TakeRequest(),Receive(),block)),(DeskState(),),tuple(Request(request,(answer,)) for request in ("lend_request","deny_request") for answer in ("lent","refused")),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer(): return make(Reply())
def broken_variants():return {"reply_hides_refusal":make(Reply(True))}
def conformance():
    native=load_anchor(IMPLEMENTED_BY["Main"],root=Path.cwd())
    from shelf import members
    facts=[]
    old_limit=members.LIMIT
    try:
        for limit,expected in ((2,"lent"),(0,"refused")):
            members.LIMIT=limit
            out=StringIO()
            with redirect_stdout(out):code=native()
            facts.append(Fact(expected,code==0 and out.getvalue().strip()==expected,out.getvalue()))
    finally:members.LIMIT=old_limit
    return CodeFactsReport(tuple(facts))
