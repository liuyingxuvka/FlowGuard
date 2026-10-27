"""Lending model: loans respect copies and the member limit; a returned copy goes to the first member holding it.
Protected failures: lending a copy that is not free; exceeding the member limit; a free copy left idle while a member holds the book.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "lending"
PARENT = "desk"
COMPONENTS = ["loans"]
READS_PARENT = ("request",)
OUTPUTS = {"answer":("lent","refused")}
IMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow", "GiveBack": "shelf/loans.py:LoanService.give_back", "Hold": "shelf/loans.py:LoanService.hold"}
TESTED_BY = {"never_over_lent": ["tests/test_loans.py:test_borrow_and_return"],
             "limit_respected": ["tests/test_loans.py:test_limit"],
             "no_idle_copy_while_held": ["tests/test_loans.py:test_hold_gets_returned_copy"]}
STOCK = {"b": 1, "c": 2}
LIMIT = 2


@dataclass(frozen=True)
class Borrow:
    member: str
    book: str


@dataclass(frozen=True)
class GiveBack:
    member: str
    book: str


@dataclass(frozen=True)
class Hold:
    member: str
    book: str


@dataclass(frozen=True)
class State:
    loans: tuple = ()
    request: str = ""
    answer: str = ""
    holds: tuple = ()


def _free(state, book):
    return STOCK.get(book, 0) - sum(1 for _, b in state.loans if b == book)



def _borrow_answer(method):
    """Keep detailed loan outcomes; expose the caller's two-way borrow answer."""
    def apply(self,inp,state):
        return tuple(FunctionResult(item.output,replace(item.new_state,request="lend_request",answer="lent" if item.output=="lent" else "refused"),label=item.label) for item in method(self,inp,state))
    return apply

class BorrowBlock:
    reads=("request","loans")
    writes=("loans","request","answer")
    name = "Borrow"
    accepted_input_type = Borrow

    @_borrow_answer
    def apply(self, inp, state):
        if sum(1 for m, _ in state.loans if m == inp.member) >= LIMIT:
            return [FunctionResult("refused", state, label="refused")]
        if _free(state, inp.book) <= 0:
            return [FunctionResult("unavailable", state, label="unavailable")]
        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]


class GiveBackBlock:
    name = "GiveBack"
    accepted_input_type = GiveBack

    def apply(self, inp, state):
        if (inp.member, inp.book) not in state.loans:
            return [FunctionResult("not_lent", state, label="not_lent")]
        loans = list(state.loans)
        loans.remove((inp.member, inp.book))
        waiting = [h for h in state.holds if h[1] == inp.book]
        if waiting:
            first = waiting[0]
            holds = list(state.holds)
            holds.remove(first)
            return [FunctionResult("returned", replace(state, loans=tuple(loans) + (first,), holds=tuple(holds)), label="handed_to_holder")]
        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]


class HoldBlock:
    name = "Hold"
    accepted_input_type = Hold

    def apply(self, inp, state):
        if _free(state, inp.book) > 0 or (inp.member, inp.book) in state.holds:
            return [FunctionResult("no_hold", state, label="no_hold")]
        return [FunctionResult("held", replace(state, holds=state.holds + ((inp.member, inp.book),)), label="held")]


class GiveBackOld(GiveBackBlock):
    def apply(self, inp, state):
        if (inp.member, inp.book) not in state.loans:
            return [FunctionResult("not_lent", state, label="not_lent")]
        loans = list(state.loans)
        loans.remove((inp.member, inp.book))
        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]


class LendAlways(BorrowBlock):
    @_borrow_answer
    def apply(self, inp, state):
        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]


class NoLimit(BorrowBlock):
    @_borrow_answer
    def apply(self, inp, state):
        if _free(state, inp.book) <= 0:
            return [FunctionResult("unavailable", state, label="unavailable")]
        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]


def _never_over_lent(state, trace):
    return InvariantResult.pass_() if all(_free(state, b) >= 0 for b in STOCK) else InvariantResult.fail("a book is lent beyond its copies")


def _limit(state, trace):
    members = {m for m, _ in state.loans}
    return InvariantResult.pass_() if all(sum(1 for m, _ in state.loans if m == x) <= LIMIT for x in members) else InvariantResult.fail("member over limit")


def _no_idle_copy(state, trace):
    return InvariantResult.pass_() if all(_free(state, b) == 0 for _, b in state.holds) else InvariantResult.fail("a copy sits free while a member holds it")


INVARIANTS = (Invariant("never_over_lent", "a book is never lent beyond its copies", _never_over_lent),
              Invariant("no_idle_copy_while_held", "a held book has no free copy", _no_idle_copy),
              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))
INPUTS = (Borrow("ann", "b"), Borrow("bob", "b"), GiveBack("ann", "b"), Borrow("ann", "c"), Hold("bob", "b"))


def _explorer(borrow, giveback=None) -> Explorer:
    giveback = giveback or GiveBackBlock()
    return Explorer(workflow=Workflow((borrow, giveback, HoldBlock()), mode="choice"), initial_states=(State(),),
                    external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=4, progress_steps=0)


def build_explorer():
    return _explorer(BorrowBlock())


def broken_variants():
    return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit()), "return_ignores_holds": _explorer(BorrowBlock(), GiveBackOld())}


class _Adapter:
    def reset(self, initial_state):
        from shelf.loans import LoanService
        self.svc = LoanService()
        self.request = initial_state.request
        self.answer = initial_state.answer
        for m in ("ann", "bob"):
            self.svc.members.join(m)
        for book, n in STOCK.items():
            self.svc.catalog.add(book, n)

    def apply_step(self, step):
        inp = step.function_input
        if isinstance(inp, Borrow):
            out = self.svc.borrow(inp.member, inp.book)
        elif isinstance(inp, Hold):
            out = self.svc.hold(inp.member, inp.book)
        else:
            out = self.svc.give_back(inp.member, inp.book)
        if isinstance(inp, Borrow):
            self.request="lend_request"
            self.answer="lent" if out=="lent" else "refused"
        return ReplayObservation(function_name=step.function_name, observed_output=out, observed_state=self.observe_state())

    def observe_state(self):
        return State(loans=tuple(self.svc.loans), holds=tuple(getattr(self.svc, "holds", ())),request=self.request,answer=self.answer)

    def observe_output(self):
        return None


def conformance():
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        last = replay_trace(trace=trace, adapter=_Adapter(), invariants=INVARIANTS,
                            rules=(projected_state_matches(), projected_output_matches()))
        if not last.ok:
            return last
    return last
