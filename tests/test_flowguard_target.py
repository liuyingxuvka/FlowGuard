"""Native target lifecycle tests and the reusable, self-contained shelf fixture."""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import flowguard.__main__ as cli

SHELF_BASE: dict[str, str] = {
    '.flowguard/map.json': '{\n  "schema": "flowguard.map.v1",\n  "project": "shelf",\n  "layers": [\n    "interface",\n    "lending",\n    "records"\n  ],\n  "ignore": [],\n  "test_command": "python -m pytest -q",\n  "components": [\n    {\n      "id": "cli",\n      "layer": "interface",\n      "summary": "Command line demo of lending.",\n      "responsibilities": [\n        "run the demo"\n      ],\n      "files": [\n        "shelf/cli.py",\n        "shelf/__init__.py"\n      ],\n      "entrypoints": [\n        "shelf/cli.py:main"\n      ],\n      "state": [],\n      "side_effects": [\n        "prints the result"\n      ],\n      "depends_on": [\n        "loans"\n      ],\n      "tests": [],\n      "models": [],\n      "status": "draft"\n    },\n    {\n      "id": "loans",\n      "layer": "lending",\n      "summary": "Lends and takes back books for members.",\n      "responsibilities": [\n        "lend a free copy",\n        "take a lent copy back"\n      ],\n      "files": [\n        "shelf/loans.py"\n      ],\n      "entrypoints": [\n        "shelf/loans.py:LoanService.borrow",\n        "shelf/loans.py:LoanService.give_back"\n      ],\n      "state": [\n        "current loans"\n      ],\n      "side_effects": [],\n      "depends_on": [\n        "catalog",\n        "members"\n      ],\n      "tests": [\n        "tests/test_loans.py"\n      ],\n      "models": [],\n      "status": "draft"\n    },\n    {\n      "id": "catalog",\n      "layer": "records",\n      "summary": "Counts free copies per book.",\n      "responsibilities": [\n        "count free copies"\n      ],\n      "files": [\n        "shelf/catalog.py"\n      ],\n      "entrypoints": [\n        "shelf/catalog.py:Catalog.take"\n      ],\n      "state": [\n        "free copies per book"\n      ],\n      "side_effects": [],\n      "depends_on": [],\n      "tests": [\n        "tests/test_catalog.py"\n      ],\n      "models": [],\n      "status": "draft"\n    },\n    {\n      "id": "members",\n      "layer": "records",\n      "summary": "Knows members and their loan limit.",\n      "responsibilities": [\n        "enforce the loan limit"\n      ],\n      "files": [\n        "shelf/members.py"\n      ],\n      "entrypoints": [\n        "shelf/members.py:Members.may_borrow"\n      ],\n      "state": [\n        "known members"\n      ],\n      "side_effects": [],\n      "depends_on": [],\n      "tests": [],\n      "models": [],\n      "status": "draft"\n    }\n  ],\n  "flows": [\n    {\n      "id": "borrow",\n      "summary": "member borrows a book",\n      "steps": [\n        "cli:main",\n        "loans:LoanService.borrow",\n        "members:Members.may_borrow",\n        "catalog:Catalog.take"\n      ]\n    }\n  ],\n  "accepted_debts": []\n}\n',
    '.flowguard/models/lending.py': '"""Lending model: a member never holds more than LIMIT loans and a book is never lent beyond its copies.\nProtected failures: lending a copy that is not free; exceeding the member limit; returning what was not lent.\n"""\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, replace\n\nfrom flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces\nfrom flowguard.conformance import projected_output_matches, projected_state_matches\nfrom flowguard.explorer import Explorer\n\nMODEL_ID = "lending"\nIMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow", "GiveBack": "shelf/loans.py:LoanService.give_back"}\nTESTED_BY = {"never_over_lent": ["tests/test_loans.py:test_borrow_and_return"],\n             "limit_respected": ["tests/test_loans.py:test_limit"]}\nSTOCK = {"b": 1, "c": 2}\nLIMIT = 2\n\n\n@dataclass(frozen=True)\nclass Borrow:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass GiveBack:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass State:\n    loans: tuple = ()\n\n\ndef _free(state, book):\n    return STOCK.get(book, 0) - sum(1 for _, b in state.loans if b == book)\n\n\nclass BorrowBlock:\n    name = "Borrow"\n    accepted_input_type = Borrow\n\n    def apply(self, inp, state):\n        if sum(1 for m, _ in state.loans if m == inp.member) >= LIMIT:\n            return [FunctionResult("refused", state, label="refused")]\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass GiveBackBlock:\n    name = "GiveBack"\n    accepted_input_type = GiveBack\n\n    def apply(self, inp, state):\n        if (inp.member, inp.book) not in state.loans:\n            return [FunctionResult("not_lent", state, label="not_lent")]\n        loans = list(state.loans)\n        loans.remove((inp.member, inp.book))\n        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]\n\n\nclass LendAlways(BorrowBlock):\n    def apply(self, inp, state):\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass NoLimit(BorrowBlock):\n    def apply(self, inp, state):\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\ndef _never_over_lent(state, trace):\n    return InvariantResult.pass_() if all(_free(state, b) >= 0 for b in STOCK) else InvariantResult.fail("a book is lent beyond its copies")\n\n\ndef _limit(state, trace):\n    members = {m for m, _ in state.loans}\n    return InvariantResult.pass_() if all(sum(1 for m, _ in state.loans if m == x) <= LIMIT for x in members) else InvariantResult.fail("member over limit")\n\n\nINVARIANTS = (Invariant("never_over_lent", "a book is never lent beyond its copies", _never_over_lent),\n              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))\nINPUTS = (Borrow("ann", "b"), Borrow("bob", "b"), GiveBack("ann", "b"), Borrow("ann", "c"))\n\n\ndef _explorer(borrow) -> Explorer:\n    return Explorer(workflow=Workflow((borrow, GiveBackBlock()), mode="choice"), initial_states=(State(),),\n                    external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=4, progress_steps=0)\n\n\ndef build_explorer():\n    return _explorer(BorrowBlock())\n\n\ndef broken_variants():\n    return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit())}\n\n\nclass _Adapter:\n    def reset(self, initial_state):\n        from shelf.loans import LoanService\n        self.svc = LoanService()\n        for m in ("ann", "bob"):\n            self.svc.members.join(m)\n        for book, n in STOCK.items():\n            self.svc.catalog.add(book, n)\n\n    def apply_step(self, step):\n        inp = step.function_input\n        out = self.svc.borrow(inp.member, inp.book) if isinstance(inp, Borrow) else self.svc.give_back(inp.member, inp.book)\n        return ReplayObservation(function_name=step.function_name, observed_output=out, observed_state=self.observe_state())\n\n    def observe_state(self):\n        return State(loans=tuple(self.svc.loans))\n\n    def observe_output(self):\n        return None\n\n\ndef conformance():\n    last = None\n    for trace in select_covering_traces(build_explorer().explore().traces):\n        last = replay_trace(trace=trace, adapter=_Adapter(), invariants=INVARIANTS,\n                            rules=(projected_state_matches(), projected_output_matches()))\n        if not last.ok:\n            return last\n    return last\n',
    'shelf/__init__.py': '"""Tiny library lending package."""\n',
    'shelf/catalog.py': '"""Catalog of books and their free copies."""\n\n\nclass Catalog:\n    def __init__(self):\n        self.copies = {}\n\n    def add(self, book, count=1):\n        self.copies[book] = self.copies.get(book, 0) + count\n\n    def free(self, book):\n        return self.copies.get(book, 0)\n\n    def take(self, book):\n        if self.copies.get(book, 0) <= 0:\n            raise ValueError("no free copy")\n        self.copies[book] -= 1\n\n    def put_back(self, book):\n        self.copies[book] = self.copies.get(book, 0) + 1\n',
    'shelf/cli.py': '"""Command line demo."""\n\nimport sys\n\nfrom shelf.loans import LoanService\n\n\ndef main(argv=None):\n    svc = LoanService()\n    svc.members.join("ann")\n    svc.catalog.add("dune", 1)\n    print(svc.borrow("ann", "dune"))\n    return 0\n\n\nif __name__ == "__main__":\n    sys.exit(main(sys.argv[1:]))\n',
    'shelf/loans.py': '"""Lending: borrow and return books."""\n\nfrom shelf.catalog import Catalog\nfrom shelf.members import Members\n\n\nclass LoanService:\n    def __init__(self, catalog=None, members=None):\n        self.catalog = catalog or Catalog()\n        self.members = members or Members()\n        self.loans = []          # (member, book)\n\n    def count(self, member):\n        return sum(1 for m, _ in self.loans if m == member)\n\n    def borrow(self, member, book):\n        if not self.members.may_borrow(member, self.count(member)):\n            return "refused"\n        if self.catalog.free(book) <= 0:\n            return "unavailable"\n        self.catalog.take(book)\n        self.loans.append((member, book))\n        return "lent"\n\n    def give_back(self, member, book):\n        if (member, book) not in self.loans:\n            return "not_lent"\n        self.loans.remove((member, book))\n        self.catalog.put_back(book)\n        return "returned"\n',
    'shelf/members.py': '"""Members and their loan limits."""\n\nLIMIT = 2\n\n\nclass Members:\n    def __init__(self):\n        self.known = set()\n\n    def join(self, member):\n        self.known.add(member)\n\n    def may_borrow(self, member, current_loans):\n        return member in self.known and current_loans < LIMIT\n',
    'tests/test_catalog.py': 'from shelf.catalog import Catalog\n\n\ndef test_take_put_back():\n    c = Catalog()\n    c.add("x")\n    c.take("x")\n    assert c.free("x") == 0\n    c.put_back("x")\n    assert c.free("x") == 1\n',
    'tests/test_loans.py': 'from shelf.loans import LoanService\n\n\ndef _svc():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    return s\n\n\ndef test_borrow_and_return():\n    s = _svc()\n    assert s.borrow("ann", "dune") == "lent"\n    assert s.borrow("ann", "dune") == "unavailable"\n    assert s.give_back("ann", "dune") == "returned"\n    assert s.catalog.free("dune") == 1\n\n\ndef test_limit():\n    s = _svc()\n    s.catalog.add("a", 3)\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "refused"\n',
}

SHELF_TARGET: dict[str, str] = {
    'map.json': '{\n  "schema": "flowguard.target.v1",\n  "goal": "holds: a member may reserve a lent-out book; a returned copy goes to the first holder",\n  "components": [\n    {\n      "id": "loans",\n      "layer": "lending",\n      "summary": "Lends and takes back books for members.",\n      "responsibilities": [\n        "lend a free copy",\n        "take a lent copy back",\n        "hold a lent-out book for a member"\n      ],\n      "files": [\n        "shelf/loans.py"\n      ],\n      "entrypoints": [\n        "shelf/loans.py:LoanService.borrow",\n        "shelf/loans.py:LoanService.give_back",\n        "shelf/loans.py:LoanService.hold"\n      ],\n      "state": [\n        "current loans",\n        "holds per book in order"\n      ],\n      "side_effects": [],\n      "depends_on": [\n        "catalog",\n        "members"\n      ],\n      "tests": [\n        "tests/test_loans.py"\n      ],\n      "models": []\n    }\n  ],\n  "flows": [],\n  "remove": []\n}\n',
    'map_reports.json': '{\n  "schema": "flowguard.target.v1",\n  "goal": "reports: list overdue loans",\n  "components": [\n    {\n      "id": "reports",\n      "layer": "lending",\n      "summary": "Lists overdue loans.",\n      "responsibilities": [\n        "list overdue loans"\n      ],\n      "files": [\n        "shelf/reports.py"\n      ],\n      "entrypoints": [\n        "shelf/reports.py:overdue"\n      ],\n      "state": [],\n      "side_effects": [],\n      "depends_on": [\n        "loans"\n      ],\n      "tests": [\n        "tests/test_reports.py"\n      ],\n      "models": []\n    }\n  ],\n  "flows": [],\n  "remove": []\n}\n',
    'models/lending.py': '"""Lending model: loans respect copies and the member limit; a returned copy goes to the first member holding it.\nProtected failures: lending a copy that is not free; exceeding the member limit; a free copy left idle while a member holds the book.\n"""\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, replace\n\nfrom flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces\nfrom flowguard.conformance import projected_output_matches, projected_state_matches\nfrom flowguard.explorer import Explorer\n\nMODEL_ID = "lending"\nIMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow", "GiveBack": "shelf/loans.py:LoanService.give_back", "Hold": "shelf/loans.py:LoanService.hold"}\nTESTED_BY = {"never_over_lent": ["tests/test_loans.py:test_borrow_and_return"],\n             "limit_respected": ["tests/test_loans.py:test_limit"],\n             "no_idle_copy_while_held": ["tests/test_loans.py:test_hold_gets_returned_copy"]}\nSTOCK = {"b": 1, "c": 2}\nLIMIT = 2\n\n\n@dataclass(frozen=True)\nclass Borrow:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass GiveBack:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass Hold:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass State:\n    loans: tuple = ()\n    holds: tuple = ()\n\n\ndef _free(state, book):\n    return STOCK.get(book, 0) - sum(1 for _, b in state.loans if b == book)\n\n\nclass BorrowBlock:\n    name = "Borrow"\n    accepted_input_type = Borrow\n\n    def apply(self, inp, state):\n        if sum(1 for m, _ in state.loans if m == inp.member) >= LIMIT:\n            return [FunctionResult("refused", state, label="refused")]\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass GiveBackBlock:\n    name = "GiveBack"\n    accepted_input_type = GiveBack\n\n    def apply(self, inp, state):\n        if (inp.member, inp.book) not in state.loans:\n            return [FunctionResult("not_lent", state, label="not_lent")]\n        loans = list(state.loans)\n        loans.remove((inp.member, inp.book))\n        waiting = [h for h in state.holds if h[1] == inp.book]\n        if waiting:\n            first = waiting[0]\n            holds = list(state.holds)\n            holds.remove(first)\n            return [FunctionResult("returned", replace(state, loans=tuple(loans) + (first,), holds=tuple(holds)), label="handed_to_holder")]\n        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]\n\n\nclass HoldBlock:\n    name = "Hold"\n    accepted_input_type = Hold\n\n    def apply(self, inp, state):\n        if _free(state, inp.book) > 0 or (inp.member, inp.book) in state.holds:\n            return [FunctionResult("no_hold", state, label="no_hold")]\n        return [FunctionResult("held", replace(state, holds=state.holds + ((inp.member, inp.book),)), label="held")]\n\n\nclass GiveBackOld(GiveBackBlock):\n    def apply(self, inp, state):\n        if (inp.member, inp.book) not in state.loans:\n            return [FunctionResult("not_lent", state, label="not_lent")]\n        loans = list(state.loans)\n        loans.remove((inp.member, inp.book))\n        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]\n\n\nclass LendAlways(BorrowBlock):\n    def apply(self, inp, state):\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass NoLimit(BorrowBlock):\n    def apply(self, inp, state):\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\ndef _never_over_lent(state, trace):\n    return InvariantResult.pass_() if all(_free(state, b) >= 0 for b in STOCK) else InvariantResult.fail("a book is lent beyond its copies")\n\n\ndef _limit(state, trace):\n    members = {m for m, _ in state.loans}\n    return InvariantResult.pass_() if all(sum(1 for m, _ in state.loans if m == x) <= LIMIT for x in members) else InvariantResult.fail("member over limit")\n\n\ndef _no_idle_copy(state, trace):\n    return InvariantResult.pass_() if all(_free(state, b) == 0 for _, b in state.holds) else InvariantResult.fail("a copy sits free while a member holds it")\n\n\nINVARIANTS = (Invariant("never_over_lent", "a book is never lent beyond its copies", _never_over_lent),\n              Invariant("no_idle_copy_while_held", "a held book has no free copy", _no_idle_copy),\n              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))\nINPUTS = (Borrow("ann", "b"), Borrow("bob", "b"), GiveBack("ann", "b"), Borrow("ann", "c"), Hold("bob", "b"))\n\n\ndef _explorer(borrow, giveback=None) -> Explorer:\n    giveback = giveback or GiveBackBlock()\n    return Explorer(workflow=Workflow((borrow, giveback, HoldBlock()), mode="choice"), initial_states=(State(),),\n                    external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=4, progress_steps=0)\n\n\ndef build_explorer():\n    return _explorer(BorrowBlock())\n\n\ndef broken_variants():\n    return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit()), "return_ignores_holds": _explorer(BorrowBlock(), GiveBackOld())}\n\n\nclass _Adapter:\n    def reset(self, initial_state):\n        from shelf.loans import LoanService\n        self.svc = LoanService()\n        for m in ("ann", "bob"):\n            self.svc.members.join(m)\n        for book, n in STOCK.items():\n            self.svc.catalog.add(book, n)\n\n    def apply_step(self, step):\n        inp = step.function_input\n        if isinstance(inp, Borrow):\n            out = self.svc.borrow(inp.member, inp.book)\n        elif isinstance(inp, Hold):\n            out = self.svc.hold(inp.member, inp.book)\n        else:\n            out = self.svc.give_back(inp.member, inp.book)\n        return ReplayObservation(function_name=step.function_name, observed_output=out, observed_state=self.observe_state())\n\n    def observe_state(self):\n        return State(loans=tuple(self.svc.loans), holds=tuple(getattr(self.svc, "holds", ())))\n\n    def observe_output(self):\n        return None\n\n\ndef conformance():\n    last = None\n    for trace in select_covering_traces(build_explorer().explore().traces):\n        last = replay_trace(trace=trace, adapter=_Adapter(), invariants=INVARIANTS,\n                            rules=(projected_state_matches(), projected_output_matches()))\n        if not last.ok:\n            return last\n    return last\n',
}

SHELF_AFTER: dict[str, str] = {
    'shelf/loans.py': '"""Lending: borrow and return books."""\n\nfrom shelf.catalog import Catalog\nfrom shelf.members import Members\n\n\nclass LoanService:\n    def __init__(self, catalog=None, members=None):\n        self.catalog = catalog or Catalog()\n        self.members = members or Members()\n        self.loans = []          # (member, book)\n        self.holds = []          # (member, book) waiting in order\n\n    def count(self, member):\n        return sum(1 for m, _ in self.loans if m == member)\n\n    def borrow(self, member, book):\n        if not self.members.may_borrow(member, self.count(member)):\n            return "refused"\n        if self.catalog.free(book) <= 0:\n            return "unavailable"\n        self.catalog.take(book)\n        self.loans.append((member, book))\n        return "lent"\n\n    def give_back(self, member, book):\n        if (member, book) not in self.loans:\n            return "not_lent"\n        self.loans.remove((member, book))\n        waiting = [h for h in self.holds if h[1] == book]\n        if waiting:\n            self.holds.remove(waiting[0])\n            self.loans.append(waiting[0])\n            return "returned"\n        self.catalog.put_back(book)\n        return "returned"\n\n    def hold(self, member, book):\n        if self.catalog.free(book) > 0 or (member, book) in self.holds:\n            return "no_hold"\n        self.holds.append((member, book))\n        return "held"\n',
    'shelf/reports.py': '"""Reports over current loans."""\n\nfrom shelf.loans import LoanService\n\n\ndef overdue(service: LoanService, members_late):\n    return [(member, book) for member, book in service.loans if member in members_late]\n',
    'tests/test_loans.py': 'from shelf.loans import LoanService\n\n\ndef _svc():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    return s\n\n\ndef test_borrow_and_return():\n    s = _svc()\n    assert s.borrow("ann", "dune") == "lent"\n    assert s.borrow("ann", "dune") == "unavailable"\n    assert s.give_back("ann", "dune") == "returned"\n    assert s.catalog.free("dune") == 1\n\n\ndef test_limit():\n    s = _svc()\n    s.catalog.add("a", 3)\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "refused"\n\n\ndef test_hold_gets_returned_copy():\n    s = _svc()\n    s.members.join("bob")\n    assert s.borrow("ann", "dune") == "lent"\n    assert s.hold("bob", "dune") == "held"\n    assert s.give_back("ann", "dune") == "returned"\n    assert ("bob", "dune") in s.loans and s.catalog.free("dune") == 0\n',
    'tests/test_reports.py': 'from shelf.loans import LoanService\nfrom shelf.reports import overdue\n\n\ndef test_overdue_lists_late_members():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    s.borrow("ann", "dune")\n    assert overdue(s, {"ann"}) == [("ann", "dune")]\n',
}


_SHELF_TEMPLATE: list[Path] = []


def _shelf_template() -> Path:
    """Build the committed and confirmed shelf baseline once per test process; tests get copies."""
    if not _SHELF_TEMPLATE:
        import atexit
        import tempfile

        holder = tempfile.TemporaryDirectory(prefix="flowguard-shelf-template-")
        atexit.register(holder.cleanup)
        root = Path(holder.name) / "project"
        root.mkdir()
        for relative, text in SHELF_BASE.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        git = ["git", "-c", "core.autocrlf=false", "-c", "user.name=FlowGuard tests",
               "-c", "user.email=flowguard-tests@example.invalid"]
        for arguments in (("init", "-q"), ("add", "."), ("commit", "-qm", "shelf baseline")):
            subprocess.run([*git, *arguments], cwd=root, check=True, capture_output=True)
        with redirect_stdout(io.StringIO()):
            assert cli.main(["map", "confirm", "all", "--root", str(root)]) == 0
        _SHELF_TEMPLATE.append(root)
    return _SHELF_TEMPLATE[0]


def shelf_project(tmp_path: Path) -> Path:
    """The original shelf baseline, committed, with its current map confirmed (a copy of one template)."""
    import shutil

    root = tmp_path / "project"
    shutil.copytree(_shelf_template(), root)
    return root


def _run(root: Path, capsys, *arguments: str):
    code = cli.main([*arguments, "--root", str(root)])
    output = capsys.readouterr()
    return code, output.out, output.err


def _load_map(root: Path) -> dict:
    return json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))


def _write_map(root: Path, data: dict) -> None:
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture()
def _no_model_execution(monkeypatch):
    from flowguard.map import proof

    def forbidden(*args, **kwargs):
        pytest.fail("target storage and static read must not execute a model")

    for name in ("run_models", "run_model", "run_model_in_process"):
        monkeypatch.setattr(proof, name, forbidden)


@pytest.mark.usefixtures("_no_model_execution")
def test_target_start_add_drop_and_read_line(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    loans = next(component for component in current["components"] if component["id"] == "loans")
    loans["_hint"] = "current-only drafting hint"
    _write_map(root, current)
    original_map = (root / ".flowguard/map.json").read_bytes()
    code, check_before, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in check_before and not errors

    code, output, errors = _run(root, capsys, "target", "start", "holds")
    assert code == 0 and not errors
    assert 'target started: "holds"' in output
    assert "next: python -m flowguard target add" in output
    directory = root / ".flowguard/target"
    target_path = directory / "map.json"
    assert target_path.is_file() and (directory / "models").is_dir()
    assert json.loads(target_path.read_text(encoding="utf-8")) == {
        "schema": "flowguard.target.v1", "goal": "holds", "components": [], "flows": [], "remove": []}

    code, _, errors = _run(root, capsys, "target", "start", "second goal")
    assert code == 2 and 'a target already exists: "holds"' in errors
    assert "target promote" in errors and "target drop --yes" in errors
    for node, message in (("loans", "added component loans"), ("lending", "added model lending"),
                          ("flow:borrow", "added flow borrow")):
        code, output, errors = _run(root, capsys, "target", "add", node)
        assert code == 0 and message in output and not errors
    target = json.loads(target_path.read_text(encoding="utf-8"))
    assert target["components"] == [{key: value for key, value in loans.items()
                                      if key not in {"status", "fingerprint", "_hint"}}]
    assert target["flows"] == current["flows"]
    assert (directory / "models/lending.py").read_bytes() == (root / ".flowguard/models/lending.py").read_bytes()
    before_errors = target_path.read_bytes()
    code, _, errors = _run(root, capsys, "target", "add", "loans")
    assert code == 2 and "component loans is already in the target" in errors
    code, _, errors = _run(root, capsys, "target", "add", "nope")
    assert code == 2 and "unknown node 'nope'" in errors
    assert "components:" in errors and "loans" in errors and "models:" in errors and "lending" in errors
    assert target_path.read_bytes() == before_errors

    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors
    assert next(line for line in output.splitlines() if line.startswith("target:")).startswith('target: "holds": +0 ~3 -0 nodes')
    code, check_after, errors = _run(root, capsys, "map", "check")
    assert code == 0 and check_after == check_before and not errors
    assert (root / ".flowguard/map.json").read_bytes() == original_map

    target_files = {p.relative_to(directory).as_posix(): p.read_bytes()
                    for p in directory.rglob("*") if p.is_file()}
    code, output, errors = _run(root, capsys, "target", "drop")
    assert code == 1 and not errors and 'would delete .flowguard/target/ ("holds", 2 file(s))' in output
    assert "re-run with --yes" in output
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()} == target_files
    code, output, errors = _run(root, capsys, "target", "drop", "--yes")
    assert code == 0 and 'dropped target "holds"' in output and not errors
    assert not directory.exists()
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors and not any(line.startswith("target:") for line in output.splitlines())
    assert (root / ".flowguard/map.json").read_bytes() == original_map


@pytest.mark.parametrize("contents", ["{broken json", json.dumps({
    "schema": "wrong.target.schema", "goal": "holds", "components": [], "flows": [], "remove": []})])
@pytest.mark.usefixtures("_no_model_execution")
def test_invalid_target_map_does_not_break_read(tmp_path, capsys, contents):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    original_map = (root / ".flowguard/map.json").read_bytes()
    directory = root / ".flowguard/target"
    directory.mkdir()
    path = directory / "map.json"
    path.write_text(contents, encoding="utf-8")
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors
    assert next(line for line in output.splitlines() if line.startswith("target:")).startswith(
        "target: .flowguard/target/map.json is invalid; run python -m flowguard target check")
    assert path.read_text(encoding="utf-8") == contents
    assert (root / ".flowguard/map.json").read_bytes() == original_map


@pytest.mark.parametrize("goal", ["", "  "])
@pytest.mark.usefixtures("_no_model_execution")
def test_target_start_rejects_empty_goal_and_missing_map(tmp_path, capsys, goal):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    code, _, errors = _run(root, capsys, "target", "start", goal)
    assert code == 2 and "the goal must be a nonempty sentence" in errors
    assert not (root / ".flowguard/target").exists()
    empty = tmp_path / "empty"
    empty.mkdir()
    code, _, errors = _run(empty, capsys, "target", "start", "holds")
    assert code == 2 and "map" in errors.lower()
    assert not (empty / ".flowguard/target").exists()


@pytest.mark.usefixtures("_no_model_execution")
def test_target_commands_require_a_target_and_offer_help(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("add", "loans"), ("drop",), ("drop", "--yes")):
        code, _, errors = _run(root, capsys, "target", *arguments)
        assert code == 2 and "no target" in errors and "target start" in errors
    for arguments in (("target",), ("target", "--help"), ("target", "start", "--help")):
        try:
            code = cli.main([*arguments, "--root", str(root)])
        except SystemExit as exc:
            code = exc.code
        output = capsys.readouterr()
        assert code == 0 and "usage:" in output.out.lower() and not output.err
    assert not (root / ".flowguard/target").exists()


@pytest.mark.usefixtures("_no_model_execution")
def test_target_add_disambiguates_component_and_model_ids(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    next(component for component in current["components"] if component["id"] == "cli")["id"] = "lending"
    for flow in current["flows"]:
        flow["steps"] = ["lending:" + step.split(":", 1)[1] if step.startswith("cli:") else step
                         for step in flow["steps"]]
    _write_map(root, current)
    assert _run(root, capsys, "target", "start", "disambiguate")[0] == 0
    code, _, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 2 and "is both a component and a model" in errors
    assert "component:lending" in errors and "model:lending" in errors
    for node in ("component:lending", "model:lending"):
        assert _run(root, capsys, "target", "add", node)[0] == 0
    assert (root / ".flowguard/target/models/lending.py").is_file()
    assert [row["id"] for row in json.loads((root / ".flowguard/target/map.json").read_text())["components"]] == ["lending"]


@pytest.mark.usefixtures("_no_model_execution")
def test_target_add_names_helpers_and_current_importers_without_executing_them(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    model = root / ".flowguard/models/lending.py"
    model.write_bytes(model.read_bytes().replace(b"from __future__ import annotations\n",
        b"from __future__ import annotations\nimport _shelf_helper\n", 1))
    (model.parent / "_shelf_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (model.parent / "lending_reader.py").write_text(
        'from lending import BorrowBlock\nMODEL_ID = "lending_reader"\n'
        'IMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow"}\n'
        'def build_explorer():\n    raise AssertionError("must not execute importer")\n', encoding="utf-8")
    assert _run(root, capsys, "target", "start", "change lending")[0] == 0
    code, output, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 0 and not errors
    assert "note: it imports _shelf_helper" in output
    assert "only if the target changes it" in output
    assert "target check also runs these models against the target version: lending_reader" in output
    copied = (root / ".flowguard/target/models/lending.py").read_bytes()
    assert b"import _shelf_helper" in copied
    assert b"import _shelf_helper" not in model.read_bytes()  # tracked edit moved; current is HEAD
    assert not (root / ".flowguard/target/models/_shelf_helper.py").exists()


@pytest.mark.usefixtures("_no_model_execution")
def test_target_overlay_is_independent_and_rejects_invalid_fields(tmp_path, capsys):
    import copy
    from flowguard.map.targetfile import load_target, merge_target_map, target_node_changes, validate_target

    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    before = copy.deepcopy(current)
    loans = copy.deepcopy(next(c for c in current["components"] if c["id"] == "loans"))
    for field in ("status", "fingerprint", "_hint"):
        loans.pop(field, None)
    loans["summary"] = "Loan service with future holds"
    draft = {"schema": "flowguard.target.v1", "goal": "holds", "components": [loans], "flows": [],
             "remove": ["flow:borrow"], "layers": ["records", "lending", "interface"], "accepted_debts": []}
    directory = root / ".flowguard/target"
    directory.mkdir()
    path = directory / "map.json"
    path.write_text(json.dumps(draft))
    target = load_target(root)
    assert target.models == {}  # Git need not retain an empty models directory.
    assert validate_target(root, current, target) == []
    merged = merge_target_map(current, target)
    replacement = next(c for c in merged["components"] if c["id"] == "loans")
    assert replacement["summary"] == "Loan service with future holds"
    assert replacement["status"] == "draft" and "fingerprint" not in replacement
    assert merged["flows"] == [] and merged["layers"] == draft["layers"] and merged["accepted_debts"] == []
    assert target_node_changes(root, current, target) == {"+": [], "~": ["component:loans"], "-": ["flow:borrow"]}
    replacement["responsibilities"].append("only in the returned overlay")
    assert current == before and target.data == draft
    invalid = [
        {**draft, "extra": True},
        {**draft, "components": [{**loans, "status": "confirmed"}]},
        {**draft, "components": [loans, loans]},
        {**draft, "remove": ["component:missing"]},
        {**draft, "remove": ["component:loans"]},
        {**draft, "flows": [{"id": "future", "steps": [123]}]},
        {**draft, "flows": [{"id": "future", "steps": [], "model": 123}]},
        *[{**draft, "flows": [{"id": "future", "steps": [], "model": value}]}
          for value in ("other/foo.py", "foo.py", ".flowguard/target/models/lending.py")]]
    for payload in invalid:
        path.write_text(json.dumps(payload))
        assert "target_invalid" in {issue.code for issue in validate_target(root, current, load_target(root))}
    path.write_text(json.dumps({**draft, "components": [{**loans, "summary": ""}]}))
    assert "target_component_incomplete" in {issue.code for issue in validate_target(root, current, load_target(root))}
    path.write_text(json.dumps(draft))
    (directory / "models").mkdir()
    model = (root / ".flowguard/models/lending.py").read_text()
    (directory / "models/lending2.py").write_text(model + '\nDESIGN_ONLY = "future"\n')
    assert {"target_model_id_clash", "target_design_only"} <= {
        issue.code for issue in validate_target(root, current, load_target(root))}
    assert current == before


def _install_shelf_target(root: Path, *, reports: bool = False) -> Path:
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text(SHELF_TARGET["map_reports.json" if reports else "map.json"],
                                         encoding="utf-8")
    if not reports:
        (directory / "models/lending.py").write_text(SHELF_TARGET["models/lending.py"], encoding="utf-8")
    else:
        # The new reports entrypoint is a promise: tie it to one more known-bad variant of lending.
        source = SHELF_BASE[".flowguard/models/lending.py"]
        old = 'return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit())}'
        assert source.count(old) == 1
        (directory / "models/lending.py").write_text(source.replace(
            old, old[:-1] + ', "lend_always_again": _explorer(LendAlways())}'), encoding="utf-8")
    return directory


def _project_snapshot(root: Path) -> tuple[dict, set]:
    """Observe the actual check's no-write promise, including newly created caches."""
    files = {}
    directories = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            files[relative] = (path.read_bytes(), path.stat().st_mtime_ns)
        elif path.is_dir():
            directories.add(relative)
    return files, directories


def _check_without_writes(root: Path, capsys):
    before = _project_snapshot(root)
    result = _run(root, capsys, "target", "check")
    assert _project_snapshot(root) == before
    return result


def _run_models_with_results(root, capsys, *arguments):
    from unittest.mock import patch
    from flowguard.map import cli as map_cli
    original, captured = map_cli.run_models, []
    def capture(*args, **kwargs):
        results = original(*args, **kwargs)
        captured.extend(results)
        return results
    with patch.object(map_cli, "run_models", side_effect=capture):
        code, output, errors = _run(root, capsys, "map", "models", *arguments)
    return code, output, errors, captured


def _assert_current_lending(root: Path, capsys) -> None:
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in output and not errors, (output, errors)
    code, output, errors, results = _run_models_with_results(root, capsys, "lending")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()) and not errors, (output, errors)
    assert {"never_over_lent", "limit_respected"} <= set(results[0].rules)
    assert "no_idle_copy_while_held" not in results[0].rules
    assert "rules:" not in output


def test_target_check_todos_then_real_code_and_bound_test(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current_map = (root / ".flowguard/map.json").read_bytes()
    current_model = (root / ".flowguard/models/lending.py").read_bytes()
    _assert_current_lending(root, capsys)
    for arguments in (("target", "start", "holds"), ("target", "add", "loans"),
                      ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    directory = root / ".flowguard/target"
    (directory / "map.json").write_text(SHELF_TARGET["map.json"], encoding="utf-8")
    (directory / "models/lending.py").write_text(SHELF_TARGET["models/lending.py"], encoding="utf-8")

    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    assert "TO-DO model lending:" in output and "LoanService.hold" in output
    assert "test_hold_gets_returned_copy" in output
    assert "next: write the code and tests" in output
    _assert_current_lending(root, capsys)
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors
    assert "model lending" in output.split("## loans", 1)[1].split("\n## ", 1)[0]

    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and not errors, (output, errors)
    assert "target check: 0 error(s), 0 to-do" in output
    assert "next: python -m flowguard target promote" in output
    assert (root / ".flowguard/map.json").read_bytes() == current_map
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_model
    _assert_current_lending(root, capsys)


def test_target_check_planned_component_is_todo_then_clean(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root, reports=True)
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    for finding in ("component_empty", "anchor_broken", "dep_unused"):
        assert any(line.startswith("TO-DO ") and finding in line for line in output.splitlines()), output
    assert any(line.startswith("WARN ") and "test_missing" in line for line in output.splitlines())
    _assert_current_lending(root, capsys)
    for relative in ("shelf/reports.py", "tests/test_reports.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "target check: 0 error(s), 0 to-do" in output and not errors, (output, errors)
    # The real new files are unowned in the CURRENT map; the overlay must not
    # silently promote them into it just because its own check is now clean.
    assert not any(component["id"] == "reports" for component in _load_map(root)["components"])
    code, output, errors = _run(root, capsys, "map", "models", "lending")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()) and "no_idle_copy_while_held" not in output, (output, errors)


@pytest.mark.parametrize(("mutation", "finding"), [
    ("passing_bad", "known-bad variant 'return_ignores_holds' passed"),
    ("unknown_remove", "target_invalid"),
    ("design_only", "target_design_only"),
    ("id_clash", "target_model_id_clash"),
    ("duplicate_responsibility", "duplicate_owner"),
])
def test_target_check_rejects_real_design_errors(tmp_path, capsys, mutation, finding):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    map_path, model_path = directory / "map.json", directory / "models/lending.py"
    original_map, original_model = map_path.read_bytes(), model_path.read_bytes()
    extra = directory / "models/lending2.py"
    try:
        target = json.loads(original_map)
        if mutation == "passing_bad":
            source = original_model.decode("utf-8")
            old = '"return_ignores_holds": _explorer(BorrowBlock(), GiveBackOld())'
            assert source.count(old) == 1
            model_path.write_text(source.replace(old, '"return_ignores_holds": _explorer(BorrowBlock())'),
                                  encoding="utf-8")
        elif mutation == "unknown_remove":
            target["remove"] = ["component:nope"]
        elif mutation == "design_only":
            model_path.write_bytes(original_model + b'\nDESIGN_ONLY = "x"\n')
        elif mutation == "id_clash":
            extra.write_bytes(original_model)
        else:
            target["components"][0]["responsibilities"].append("count free copies")
        map_path.write_text(json.dumps(target), encoding="utf-8")
        code, output, errors = _check_without_writes(root, capsys)
        assert code == 1 and not errors, (output, errors)
        assert any(line.startswith("ERROR ") and finding in line for line in output.splitlines()), output
        assert "next: fix the target design (ERROR lines)" in output
    finally:
        map_path.write_bytes(original_map)
        model_path.write_bytes(original_model)
        extra.unlink(missing_ok=True)
    assert map_path.read_bytes() == original_map and model_path.read_bytes() == original_model
    _assert_current_lending(root, capsys)


def test_target_check_distinguishes_absence_from_malformed_existing_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 2 and "no target" in errors and "target start" in errors, (output, errors)
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text("{", encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_invalid" in output, (output, errors)
    assert "Traceback" not in output + errors


def _namespace_project(tmp_path: Path) -> Path:
    """Two real contracts share a helper and a parent port, without TESTED_BY duplication."""
    root = shelf_project(tmp_path)
    (root / "namespace_subject.py").write_text(
        "def advance(value):\n    return min(1, value + 1)\n", encoding="utf-8")
    (root / "namespace-marker.txt").write_text("actual project root\n", encoding="utf-8")
    data = _load_map(root)
    data["components"].append({
        "id": "namespace-subject", "layer": "records", "summary": "Advance a bounded counter.",
        "responsibilities": ["advance the namespace fixture counter"],
        "files": ["namespace_subject.py", "namespace-marker.txt"],
        "entrypoints": ["namespace_subject.py:advance"], "state": [], "side_effects": [],
        "depends_on": [], "tests": [], "models": [], "status": "draft"})
    _write_map(root, data)
    common = '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from _view_setting import VALUE
IMPLEMENTED_BY = {"Step": "namespace_subject.py:advance"}
TESTED_BY = {}

class Step:
    name = "Step"
    accepted_input_type = int
    def apply(self, inp, state):
        return [FunctionResult("stepped", min(1, state + inp))]

class Bad(Step):
    def apply(self, inp, state):
        return [FunctionResult("stepped", 2)]

def _bounded(state, trace):
    return InvariantResult.pass_() if state in (0, 1) else InvariantResult.fail("counter escaped")

INVARIANTS = (Invariant(f"one_step_{VALUE}", "counter remains bounded", _bounded),)

def _explorer(block, starts=(0,)):
    return Explorer(workflow=Workflow((block,)), initial_states=starts, external_inputs=(1,),
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)

def broken_variants():
    return {"escaped": _explorer(Bad())}

def conformance():
    from namespace_subject import advance
    project = Path(__file__).resolve().parents[2]
    return CodeFactsReport((Fact("real bounded advance", advance(0) == 1 and advance(1) == 1),
        Fact("canonical project filename", (project / "namespace-marker.txt").read_text() == "actual project root\\n")))
'''
    parent = common + '''
MODEL_ID = "ns_parent"
PARENT = "namespace-subject"
import ns_child

def build_explorer():
    return _explorer(ns_child.Step())
'''
    child = common + '''
MODEL_ID = "ns_child"
PARENT = "ns_parent"

def project_parent_state(state):
    return state

def build_explorer():
    from flowguard.kit import reachable_states
    return _explorer(Step(), reachable_states(ns_parent.build_explorer(), project_parent_state))

import ns_parent
'''
    models = root / ".flowguard/models"
    (models / "_view_setting.py").write_text("VALUE = 1\n", encoding="utf-8")
    (models / "ns_parent.py").write_text(parent, encoding="utf-8")
    (models / "ns_child.py").write_text(child, encoding="utf-8")
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text(json.dumps({
        "schema": "flowguard.target.v1", "goal": "replace the child and shared helper",
        "components": [], "flows": [], "remove": []}), encoding="utf-8")
    (directory / "models/_view_setting.py").write_text("VALUE = 2\n", encoding="utf-8")
    target_child = child.replace(
        'Fact("canonical project filename",',
        'Fact("loader selects target bytes", "# target child" in __loader__.get_source(__name__)),\n'
        '        Fact("canonical project filename",')
    (directory / "models/ns_child.py").write_text(target_child + "\n# target child\n", encoding="utf-8")
    return root


def test_target_view_restores_imports_and_preserves_canonical_root_and_child_port(tmp_path, capsys):
    import sys
    from flowguard.map.proof import run_model_in_process
    from flowguard.map.targetfile import build_target_view, load_target

    root = _namespace_project(tmp_path)
    capsys.readouterr()
    code, output, errors, results = _run_models_with_results(root, capsys, "ns_parent")
    assert code == 0 and results[0].rules == ["one_step_1"], (output, errors)
    view = build_target_view(root, _load_map(root), load_target(root))
    path_before = list(sys.path)
    names = ("ns_parent", "ns_child", "_view_setting", "namespace_subject",
             "_flowguard_model_ns_parent", "_flowguard_model_ns_child")
    modules_before = {name: sys.modules.get(name) for name in names}
    for name in ("ns_parent", "ns_child"):
        result = run_model_in_process(root, root / f".flowguard/models/{name}.py", view=view)
        assert result.status == "pass", result
        assert result.rules == ["one_step_2"], result
        assert not any("child_start_gap" in warning for warning in result.warnings), result
        assert sys.path == path_before
        assert {key: sys.modules.get(key) for key in names} == modules_before
    # The same-process view has gone away; ordinary commands must still load the
    # current helper and current child, not the target's imported modules.
    code, output, errors, results = _run_models_with_results(root, capsys, "ns_parent")
    assert code == 0 and results[0].rules == ["one_step_1"], (output, errors)
    assert (root / ".flowguard/models/_view_setting.py").read_text() == "VALUE = 1\n"


def test_target_removed_model_cannot_fall_back_to_current_disk(tmp_path, capsys):
    root = _namespace_project(tmp_path)
    capsys.readouterr()
    directory = root / ".flowguard/target"
    # Keep the importing current parent and the real old child on disk, but
    # explicitly remove that child from the requested namespace.
    (directory / "models/ns_child.py").unlink()
    (directory / "models/_view_setting.py").unlink()
    path = directory / "map.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    target["remove"] = ["model:ns_child"]
    path.write_text(json.dumps(target), encoding="utf-8")
    old_child = (root / ".flowguard/models/ns_child.py").read_bytes()
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "ns_child" in line for line in output.splitlines()), output
    assert (root / ".flowguard/models/ns_child.py").read_bytes() == old_child
    code, output, errors, results = _run_models_with_results(root, capsys, "ns_parent")
    assert code == 0 and results[0].rules == ["one_step_1"], (output, errors)


@pytest.mark.parametrize("statement,expected_code", [
    ("import flowguard_missing_external_dependency\n", 1),
    ("import shelf.future_feature\n", 3)])
def test_target_bound_test_imports_keep_environment_errors_distinct(tmp_path, capsys, statement, expected_code):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    tests = root / "tests/test_loans.py"
    tests.write_text(statement + tests.read_text(), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and not errors and "bound tests: not run here" in output, (output, errors)
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "ERROR model lending:" in output, (output, errors)
    assert statement.strip()[7:] in output
    assert not any(line.startswith("TO-DO model lending: tested_by") for line in output.splitlines())


def _rename_return_toward_target(root: Path) -> None:
    directory = _install_shelf_target(root)
    for path in (directory / "map.json", directory / "models/lending.py"):
        source = path.read_text(encoding="utf-8")
        assert "shelf/loans.py:LoanService.give_back" in source
        path.write_text(source.replace("shelf/loans.py:LoanService.give_back",
                                       "shelf/loans.py:LoanService.return_book"), encoding="utf-8")
    code = root / "shelf/loans.py"
    source = code.read_text(encoding="utf-8")
    assert source.count("def give_back(") == 1
    code.write_text(source.replace("def give_back(", "def return_book("), encoding="utf-8")


def test_change_marks_only_planned_breakage_and_keeps_tests(tmp_path, capsys, monkeypatch):
    from flowguard.map import cli as map_cli
    from flowguard.map import proof

    root = shelf_project(tmp_path)
    capsys.readouterr()
    _rename_return_toward_target(root)
    # Retire the old public name explicitly while keeping the renamed entrypoint.
    target_path = root / ".flowguard/target/map.json"
    target_data = json.loads(target_path.read_text(encoding="utf-8"))
    target_data.setdefault("remove", []).append("entrypoint:shelf/loans.py:LoanService.give_back")
    target_path.write_text(json.dumps(target_data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and not errors, (output, errors)
    assert any("INFO" in line and "moving to target:" in line and "LoanService.give_back" in line
               for line in output.splitlines()), output
    code, strict, errors = _run(root, capsys, "map", "check", "--strict")
    assert code == 1 and "ERROR" in strict and "LoanService.give_back" in strict, (strict, errors)

    original_check = map_cli.check_target
    modes = []

    def static_check(*args, **kwargs):
        modes.append(kwargs.get("models", True))
        return original_check(*args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("change must not execute models or TESTED_BY")

    # This guard covers this actual change only; all FG209 native tests remain real.
    with monkeypatch.context() as scoped:
        scoped.setattr(map_cli, "check_target", static_check)
        for name in ("run_models", "run_model", "run_model_in_process"):
            scoped.setattr(proof, name, forbidden)
        code, output, errors = _run(root, capsys, "change", "shelf/loans.py")
    assert code == 0 and not errors, (output, errors)
    assert modes == [False]
    assert "moving to target: lending" in output
    assert any(line.startswith("run:") and "tests/test_loans.py" in line for line in output.splitlines()), output
    for line in output.splitlines():
        if line.startswith("run: python -m flowguard map models "):
            assert "lending" not in line.split()[6:], line
    assert any(line.startswith('TARGET "') and "0 design error(s)" in line for line in output.splitlines()), output


def test_unplanned_catalog_breakage_stays_an_error_with_a_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    path = root / "shelf/catalog.py"
    source = path.read_text(encoding="utf-8")
    assert source.count("def take(") == 1
    path.write_text(source.replace("def take(", "def take_renamed("), encoding="utf-8")
    for arguments in (("map", "check"), ("change", "shelf/catalog.py")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 1 and not errors, (output, errors)
        assert any("ERROR" in line and "anchor_broken" in line and "Catalog.take" in line
                   and "moving to target:" not in line for line in output.splitlines()), output


def test_new_target_file_is_moving_but_strict_remains_an_error(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root, reports=True)
    (root / "shelf/reports.py").write_text(SHELF_AFTER["shelf/reports.py"], encoding="utf-8")
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and not errors, (output, errors)
    assert any("INFO" in line and "file_unmapped" in line and "moving to target:" in line
               and "shelf/reports.py" in line for line in output.splitlines()), output
    code, output, errors = _run(root, capsys, "change", "shelf/reports.py")
    assert code == 0 and not errors, (output, errors)
    assert "moving to target:" in output and "UNMAPPED changed files" not in output
    code, output, errors = _run(root, capsys, "map", "check", "--strict")
    assert code == 1 and any("ERROR" in line and "file_unmapped" in line
                            for line in output.splitlines()), (output, errors)


def test_release_warns_first_but_runs_the_same_current_models(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    before_code, before, before_errors = _run(root, capsys, "release")
    assert before_code == 0 and not before_errors, (before, before_errors)
    assert not any(line.startswith("warning: target ") for line in before.splitlines())
    _install_shelf_target(root)
    code, output, errors = _run(root, capsys, "release")
    assert code == before_code and not errors, (output, errors)
    goal = json.loads(SHELF_TARGET["map.json"])["goal"]
    assert output.splitlines()[0] == (
        f'warning: target "{goal}" exists: release checks only the current tree; '
        'promote or drop the target before releasing')
    # Compare actual proof results/counts, leaving elapsed times out of the oracle.
    def proof_facts(text):
        return ([line.split()[:2] for line in text.splitlines() if line.split()[:1] in (["PASS"], ["FAIL"], ["ERROR"])],
                [line.strip() for line in text.splitlines() if line.startswith("models:") or "rules:" in line],
                [line for line in text.splitlines() if line.startswith("check --strict:")])
    assert proof_facts(output) == proof_facts(before)
    assert "no_idle_copy_while_held" not in output
    assert "verify: PASS" in output


def test_impact_skips_target_changes_before_test_content_lookup(tmp_path, capsys, monkeypatch):
    from flowguard.map import impact
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import ignore_patterns

    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    data = _load_map(root)
    inventory = build_inventory(root, ignore_patterns(data))
    read_source = impact.read_source
    read_tests = []

    def observe_read(path):
        if Path(path).resolve().is_relative_to(root / "tests"):
            read_tests.append(str(path))
        return read_source(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(impact, "read_source", observe_read)
        result = impact.compute_impact(root, data, inventory,
            [".flowguard/target/models/lending.py", ".flowguard/target/map.json"], base="HEAD")
    assert not result.changed and not result.tests and not result.models and not result.unmapped, result
    assert not result.blocked and not read_tests, (result, read_tests)


@pytest.mark.parametrize("node", ["model", "flow", "missing_model"])
def test_target_component_does_not_hide_an_unplanned_model_or_flow(tmp_path, capsys, node):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    if node == "model":
        source = SHELF_BASE[".flowguard/models/lending.py"]
        assert source.count('MODEL_ID = "lending"') == 1
        (root / ".flowguard/models/unplanned_lending.py").write_text(
            source.replace('MODEL_ID = "lending"', 'MODEL_ID = "unplanned_lending"'), encoding="utf-8")
        finding, identity = "model_anchor_broken", ".flowguard/models/unplanned_lending.py"
    elif node == "missing_model":
        data = _load_map(root)
        next(component for component in data["components"] if component["id"] == "loans")["models"] = [
            ".flowguard/models/unknown_contract.py"]
        _write_map(root, data)
        finding, identity = "model_missing", ".flowguard/models/unknown_contract.py"
    else:
        data = _load_map(root)
        data["flows"].append({"id": "unplanned_return", "summary": "Return an existing loan.",
                              "steps": ["loans:LoanService.give_back"]})
        _write_map(root, data)
        finding, identity = "flow_step_broken", "unplanned_return"
    _rename_return_toward_target(root)
    changed = ["shelf/loans.py"] + ([identity] if node == "missing_model" else [])
    for arguments in (("map", "check"), ("change", *changed)):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 1 and not errors, (output, errors)
        assert any("ERROR" in line and finding in line and identity in line
                   and "moving to target:" not in line for line in output.splitlines()), output
        assert any("INFO" in line and "moving to target:" in line and "LoanService.give_back" in line
                   for line in output.splitlines()), output
        if node == "missing_model" and arguments[0] == "change":
            assert any(line.startswith("BLOCKED ") and identity in line for line in output.splitlines()), output


def test_target_keeps_ambiguous_test_command_blocked(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    data = _load_map(root)
    data["test_commands"] = {"tests/test_loans.py": "python -m pytest -q",
                             "tests/test_*.py": "python -m pytest -v"}
    expected = "ambiguous test commands"
    _write_map(root, data)
    import ast
    source=root/"shelf/loans.py"
    lines=source.read_text().splitlines(True)
    method=next(n for n in ast.walk(ast.parse(''.join(lines))) if isinstance(n,ast.FunctionDef) and n.name=='borrow')
    lines.insert(method.body[0].lineno-1,' '*(method.col_offset+4)+'pass\n')
    source.write_text(''.join(lines))
    code, output, errors = _run(root, capsys, "change", "shelf/loans.py")
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("BLOCKED ") and expected in line for line in output.splitlines()), output


def _static_target_read(root: Path, capsys, monkeypatch, *arguments: str):
    from flowguard.map import check, lint, proof, target
    from flowguard.map import cli as map_cli

    def forbidden(*args, **kwargs):
        pytest.fail("read must use static source facts, not import models or run a checker")

    # Fixture confirmation is already complete. These guards cover one read only.
    with monkeypatch.context() as scoped:
        for name in ("run_models", "run_model", "run_model_in_process", "_load"):
            scoped.setattr(proof, name, forbidden)
        scoped.setattr(check, "run_check", forbidden)
        scoped.setattr(map_cli, "run_check", forbidden)
        scoped.setattr(lint, "run_lint", forbidden)
        scoped.setattr(target, "check_target", forbidden)
        scoped.setattr(map_cli, "check_target", forbidden)
        return _run(root, capsys, *arguments)


def test_read_target_shows_holds_facets_from_target_bytes_and_keeps_current_read(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    model = directory / "models/lending.py"
    source = model.read_text(encoding="utf-8")
    first_line = source.splitlines()[0]
    model.write_text(source.replace(first_line, '"""Target-only reservation policy.', 1)
                     + '\nraise AssertionError("a read imported the target model")\n', encoding="utf-8")
    current_bytes = (root / ".flowguard/models/lending.py").read_bytes()
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors and len(output.rstrip("\n")) <= 8000, (output, errors)
    for text in ("## ~ loans", "~ model lending", "rules + no_idle_copy_while_held",
                 "known-bad + return_ignores_holds", "code + Hold -> shelf/loans.py:LoanService.hold",
                 "tests + no_idle_copy_while_held -> tests/test_loans.py:test_hold_gets_returned_copy",
                 "state + holds per book in order", "unchanged: 3 component(s)"):
        assert text in output, (text, output)
    assert "Target-only reservation policy." in output
    assert "## catalog" not in output and "## members" not in output

    code, detail, errors = _static_target_read(root, capsys, monkeypatch,
                                              "read", "--target", "--component", "loans")
    assert code == 0 and not errors, (detail, errors)
    detail = "\n".join(line for line in detail.splitlines() if not line.startswith("goal rules:"))
    component, model_text = detail.split("model lending:", 1)
    labels = ("purpose:", "rules:", "known-bad:", "code:", "tests:")
    for section in (component, model_text):
        positions = [section.index(label) for label in labels]
        assert positions == sorted(positions), section
    # The component purpose is unchanged, while the model purpose really differs.
    for section, changed_purpose in ((component, False), (model_text, True)):
        purpose = section.split("purpose:", 1)[1].split("rules:", 1)[0]
        assert ("was:" in purpose) == changed_purpose, purpose
    assert "was:" in component.split("rules:", 1)[1].split("known-bad:", 1)[0]
    assert "was:" in model_text.split("known-bad:", 1)[1].split("code:", 1)[0]
    assert "was:" in model_text.split("tests:", 1)[1]
    code, current, errors = _static_target_read(root, capsys, monkeypatch,
                                               "read", "--component", "loans")
    assert code == 0 and not errors, (current, errors)
    assert "no_idle_copy_while_held" not in current and "return_ignores_holds" not in current
    assert "Target-only reservation policy." not in current
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_bytes


def test_read_target_added_removed_flows_and_mermaid_use_real_node_identity(tmp_path, capsys, monkeypatch):
    import re

    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    path = directory / "map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"].extend(json.loads(SHELF_TARGET["map_reports.json"])["components"])
    data["remove"] = ["component:cli"]
    data["flows"] = [
        {"id": "borrow", "summary": "Borrow with future holds.", "steps": ["loans:LoanService.hold"]},
        {"id": "overdue", "summary": "List overdue loans.", "steps": ["reports:overdue"]}]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (output, errors)
    for text in ("## + reports", "## - cli", "(removed by the target)", "> ~ flow borrow:", "> + flow overdue:"):
        assert text in output, (text, output)
    removed = output.split("## - cli", 1)[1].split("\n## ", 1)[0]
    assert "purpose:" not in removed and "changes:" not in removed
    code, diagram, errors = _static_target_read(root, capsys, monkeypatch,
                                               "read", "--mermaid", "--target")
    assert code == 0 and not errors and diagram.startswith("flowchart TD\n"), (diagram, errors)
    for style in ("added", "changed", "removed"):
        assert f"classDef {style} " in diagram
    assert "stroke-dasharray" in next(line for line in diagram.splitlines() if "classDef removed " in line)
    # Resolve IDs from actual definitions, rather than assume the renderer's sanitizer.
    def component_id(label):
        matches = re.findall(r'^\s*(\w+)\["' + re.escape(label) + r'<br/>[^"\n]*"\]', diagram, re.M)
        assert len(matches) == 1, (label, diagram)
        return matches[0]
    loans, reports, removed_cli = (component_id(label) for label in ("loans", "reports", "cli"))
    models = re.findall(r'^\s*(\w+)\(\["model lending<br/>[^"\n]*"\]\)', diagram, re.M)
    assert len(models) == 1, diagram
    lending = models[0]
    for node, style in ((loans, "changed"), (lending, "changed"), (reports, "added"), (removed_cli, "removed")):
        assert any(line.strip().rstrip(";") == f"class {node} {style}" for line in diagram.splitlines()), diagram
    assert f"{loans} --> {lending}" in diagram
    assert f"root_system --> {reports}" in diagram
    code, focused, errors = _static_target_read(root, capsys, monkeypatch,
        "read", "--target", "--mermaid", "--component", "loans")
    assert code == 0 and "model lending" in focused and not errors, (focused, errors)
    assert "reports<br/>" not in focused and "cli<br/>" not in focused


def test_read_target_comments_do_not_invent_facet_changes(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text(json.dumps({"schema": "flowguard.target.v1", "goal": "explain lending",
        "components": [], "flows": [], "remove": []}), encoding="utf-8")
    (directory / "models/lending.py").write_text(
        SHELF_BASE[".flowguard/models/lending.py"] + "\n# Explanation only, no declared fact changed.\n", encoding="utf-8")
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and "model lending" in output and not errors, (output, errors)
    assert "goal rules: none (no promise changes" in output
    output = "\n".join(line for line in output.splitlines() if not line.startswith("goal rules:"))
    assert "changes:" not in output and "was:" not in output
    (directory / "models/lending.py").unlink()
    (directory / "map.json").write_text(json.dumps({"schema": "flowguard.target.v1", "goal": "retire lending",
        "components": [], "flows": [], "remove": ["component:loans", "model:lending"]}), encoding="utf-8")
    code, removed, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (removed, errors)
    assert "## - loans" in removed and "\n  - model lending:" in removed, removed
    assert removed.count("(removed by the target)") == 2, removed
    removed = "\n".join(line for line in removed.splitlines() if not line.startswith("goal rules:"))
    assert not any(label in removed for label in ("purpose:", "rules:", "known-bad:", "code:", "tests:")), removed


@pytest.mark.parametrize("state", ["absent", "invalid"])
def test_read_target_absent_or_invalid_is_not_a_current_view(tmp_path, capsys, monkeypatch, state):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    if state == "invalid":
        directory = root / ".flowguard/target"
        directory.mkdir()
        (directory / "map.json").write_text("{", encoding="utf-8")
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 1, (output, errors)
    text = output + errors
    if state == "absent":
        assert 'no target; start one with python -m flowguard target start "<goal>"' in text
    else:
        assert "target: .flowguard/target/map.json is invalid" in text
    assert "## loans" not in output


def test_read_target_conflicts_only_with_find(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    with pytest.raises(SystemExit) as error:
        _static_target_read(root, capsys, monkeypatch, "read", "--target", "--find", "loans")
    assert error.value.code == 2
    capsys.readouterr()


def _promote_with_real_check(root: Path, capsys, monkeypatch):
    from flowguard.map import target

    original_check = target.check_target
    modes = []

    def observe_check(*args, **kwargs):
        modes.append(kwargs.get("models", True))
        return original_check(*args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(target, "check_target", observe_check)
        result = _run(root, capsys, "target", "promote")
    assert modes == [True], modes
    return result


def test_target_promote_real_shelf_lifecycle_without_dropping_bindings(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    before_missing = _project_snapshot(root)
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 2 and "no target; start one" in output + errors, (output, errors)
    assert _project_snapshot(root) == before_missing
    for arguments in (("target", "start", "holds"), ("target", "add", "loans"),
                      ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    directory = root / ".flowguard/target"
    (directory / "map.json").write_text(SHELF_TARGET["map.json"], encoding="utf-8")
    (directory / "models/lending.py").write_text(SHELF_TARGET["models/lending.py"], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and "TO-DO model lending:" in output and not errors, (output, errors)
    before = _project_snapshot(root)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 1 and "promote refused:" in output + errors, (output, errors)
    assert _project_snapshot(root) == before

    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and not errors, (output, errors)
    checked_model = (directory / "models/lending.py").read_bytes()
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 0 and not errors and output.startswith('promoted "'), (output, errors)
    assert "next: python -m flowguard map confirm loans" in output
    assert "next: commit (the code, .flowguard/models/ and .flowguard/map.json together)" in output
    assert not directory.exists()
    assert (root / ".flowguard/models/lending.py").read_bytes() == checked_model
    loans = next(component for component in _load_map(root)["components"] if component["id"] == "loans")
    assert loans["status"] == "draft" and "fingerprint" not in loans
    assert "tests/test_loans.py" in loans["tests"]
    code, output, errors = _run(root, capsys, "map", "confirm", "loans")
    assert code == 0 and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s), 0 warning(s)" in output and not errors, (output, errors)
    code, output, errors, results = _run_models_with_results(root, capsys, "lending", "--tests")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()), (output, errors)
    assert "no_idle_copy_while_held" in results[0].rules
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors, (output, errors)
    assert not any(line.startswith("target:") for line in output.splitlines())
    directory.mkdir()
    (directory / "map.json").write_text("{", encoding="utf-8")
    before_invalid = _project_snapshot(root)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 1 and "promote refused:" in output + errors, (output, errors)
    assert _project_snapshot(root) == before_invalid


def test_target_promote_adds_reports_and_removes_the_requested_flow(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root, reports=True)
    path = directory / "map.json"
    draft = json.loads(path.read_text(encoding="utf-8"))
    draft["remove"] = ["flow:borrow"]
    path.write_text(json.dumps(draft), encoding="utf-8")
    for relative in ("shelf/reports.py", "tests/test_reports.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 0 and not errors, (output, errors)
    assert not directory.exists()
    data = _load_map(root)
    reports = next(component for component in data["components"] if component["id"] == "reports")
    assert reports["status"] == "draft" and "fingerprint" not in reports
    assert not any(flow["id"] == "borrow" for flow in data["flows"])
    assert "next: python -m flowguard map confirm reports" in output
    assert _run(root, capsys, "map", "confirm", "reports")[0] == 0
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in output and not errors, (output, errors)


def test_target_promote_keeps_replacement_filename_when_old_model_id_is_removed(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text(json.dumps({"schema": "flowguard.target.v1", "goal": "rename the model identity",
        "components": [], "flows": [], "remove": ["model:lending"]}), encoding="utf-8")
    source = SHELF_BASE[".flowguard/models/lending.py"]
    assert source.count('MODEL_ID = "lending"') == 1
    replacement = source.replace('MODEL_ID = "lending"', 'MODEL_ID = "lending_v2"').encode("utf-8")
    (directory / "models/lending.py").write_bytes(replacement)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 0 and not errors, (output, errors)
    assert not directory.exists()
    assert (root / ".flowguard/models/lending.py").read_bytes() == replacement
    code, output, errors = _run(root, capsys, "map", "models", "lending_v2", "--tests")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending_v2"] for line in output.splitlines()), (output, errors)


def test_target_promote_refuses_a_model_that_edits_its_checked_source(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    model = directory / "models/lending.py"
    model.write_text(model.read_text(encoding="utf-8") + '''
_original_conformance = conformance

def conformance():
    from pathlib import Path
    report = _original_conformance()
    target = Path(__file__).resolve().parents[2] / ".flowguard/target/models/lending.py"
    with target.open("a", encoding="utf-8", newline="\\n") as stream:
        stream.write("\\n# edited during the real conformance check\\n")
    return report
''', encoding="utf-8")
    before_files, before_dirs = _project_snapshot(root)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 1 and "promote refused:" in output + errors, (output, errors)
    assert "changed" in (output + errors).lower()
    after_files, after_dirs = _project_snapshot(root)
    relative = ".flowguard/target/models/lending.py"
    assert after_files[relative][0] == before_files[relative][0] + b"\n# edited during the real conformance check\n"
    # The real model's explicit edit survives; the promoter writes nothing else.
    assert {p: v for p, v in after_files.items() if p != relative} == {
        p: v for p, v in before_files.items() if p != relative}
    assert after_dirs == before_dirs and directory.is_dir()


def test_target_promote_reports_real_write_failure_without_backup_or_automatic_git(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    before_files, before_dirs = _project_snapshot(root)
    original_write = Path.write_bytes
    destination = root / ".flowguard/models/lending.py.tmp"
    attempted = []

    def fail_destination(path, content):
        if path == destination:
            attempted.append(path)
            raise OSError("injected target destination write failure")
        return original_write(path, content)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "write_bytes", fail_destination)
        code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert attempted == [destination]
    assert code == 2 and "injected target destination write failure" in output + errors, (output, errors)
    assert "restore with: git checkout -- .flowguard && git clean -fd .flowguard" in output + errors
    assert directory.is_dir()
    after_files, after_dirs = _project_snapshot(root)
    backup = directory / ".replaced/models/lending.py"
    assert backup.is_file() and backup.read_bytes() == before_files[".flowguard/models/lending.py"][0]
    assert (directory / "models/lending.py").is_file()
    assert "promote stopped:" in output + errors
    # git restore/clean is guidance only: no index, ref, log or object changes.
    assert {p: v for p, v in after_files.items() if p.startswith(".git/")} == {
        p: v for p, v in before_files.items() if p.startswith(".git/")}



def test_merge_a_component_keeps_its_promises(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "merge members into loans"), ("target", "add", "loans")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["remove"] = ["component:members"]
    path.write_text(json.dumps(data), encoding="utf-8")

    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    owner_errors = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped:" in line]
    assert len(owner_errors) == 3, output
    assert any("entrypoint 'shelf/members.py:Members.may_borrow'" in line for line in owner_errors), output
    assert any("state 'known members'" in line for line in owner_errors), output
    assert any("responsibility 'enforce the loan limit'" in line for line in owner_errors), output
    all_errors = [line for line in output.splitlines() if line.startswith("ERROR ")]
    code, changed, errors = _run(root, capsys, "change")
    assert code == 0 and not errors, (changed, errors)
    assert f'TARGET "merge members into loans": {len(all_errors)} design error(s)' in changed, changed
    before_refusal = _project_snapshot(root)
    code, refused, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "promote refused:" in refused + errors, (refused, errors)
    assert all(line in refused for line in all_errors)
    assert _project_snapshot(root) == before_refusal

    loans = data["components"][0]
    loans["files"].append("shelf/members.py")
    loans["entrypoints"].append("shelf/members.py:Members.may_borrow")
    # A word-order change still names the same state; entrypoint anchors remain exact.
    loans["state"].append("members known")
    loans["responsibilities"].append("enforce the loan limit")
    loans["depends_on"].remove("members")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "add", "flow:borrow")
    assert code == 0 and not errors, (output, errors)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["flows"][0]["steps"] = [step.replace("members:", "loans:", 1) for step in data["flows"][0]["steps"]]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)
    data["components"][0]["state"][-1] = "known members"
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0 and not errors, (output, errors)
    current = _load_map(root)
    assert "members" not in {component["id"] for component in current["components"]}
    kept = next(component for component in current["components"] if component["id"] == "loans")
    assert "shelf/members.py" in kept["files"]
    assert "shelf/members.py:Members.may_borrow" in kept["entrypoints"]
    assert "known members" in kept["state"] and "enforce the loan limit" in kept["responsibilities"]
    code, output, errors = _run(root, capsys, "map", "confirm", "loans")
    assert code == 0 and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in output and not errors, (output, errors)


def test_dropping_an_entrypoint_on_purpose_is_written_in_remove(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "retire explicit member promises"),
                      ("target", "add", "loans"), ("target", "add", "cli"),
                      ("target", "add", "flow:borrow")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["remove"] = ["component:members", "entrypoint:shelf/members.py:Members.may_borrow", "state:known members",
                      "responsibility:enforce the loan limit"]
    loans = next(component for component in data["components"] if component["id"] == "loans")
    loans["files"].append("shelf/members.py")
    loans["depends_on"].remove("members")
    command = next(component for component in data["components"] if component["id"] == "cli")
    command["side_effects"] = []
    # A counterclaim in the wrong facet cannot take over a real side effect.
    command["state"] = ["prints the result"]
    data["flows"][0]["steps"] = [step.replace("members:", "loans:", 1) for step in data["flows"][0]["steps"]]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    owner_errors = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped:" in line]
    assert len(owner_errors) == 1 and "side_effect 'prints the result'" in owner_errors[0], output
    assert "component cli" in owner_errors[0]
    command["state"] = []
    data["remove"].append("side_effect:prints the result")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "owner_dropped" not in output and not errors, (output, errors)
    assert "(+0 ~3 -1 nodes)" in output, output
    code, current_read, errors = _run(root, capsys, "read")
    assert code == 0 and not errors, (current_read, errors)
    assert 'target: "retire explicit member promises": +0 ~3 -1 nodes;' in current_read, current_read
    code, target_read, errors = _run(root, capsys, "read", "--target")
    assert code == 0 and not errors, (target_read, errors)
    header = next(line for line in target_read.splitlines() if line.startswith("target:"))
    assert "-1 nodes)" in header, header
    removed_nodes = [line for line in target_read.splitlines() if line.startswith("## - ")]
    assert len(removed_nodes) == 1 and removed_nodes[0].startswith("## - members ["), target_read
    code, changed, errors = _run(root, capsys, "change")
    assert code == 0 and 'TARGET "retire explicit member promises": 0 design error(s)' in changed and not errors, (changed, errors)
    data["remove"].append("entrypoint:shelf/nope.py:x")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_invalid" in output and not errors, (output, errors)
    assert "entrypoint:shelf/nope.py:x" in output


def test_removed_symbol_still_referenced_is_a_todo(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "drop Catalog.free"), ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/models/lending.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace("from dataclasses import dataclass, replace\n",
                            "from dataclasses import dataclass, replace\nfrom pathlib import Path\n"
                            "from flowguard.map.facts import CodeFacts\n", 1)
    prefix, separator, suffix = source.rpartition("    return last\n")
    assert separator and not suffix
    path.write_text(prefix + '    facts = CodeFacts(Path(__file__).resolve().parents[2])\n'
                    '    facts.unreferenced("shelf/catalog.py:Catalog.free")\n'
                    '    facts.check("the lending replay still conforms", last.ok, last.format_text())\n'
                    '    return facts.report()\n', encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and "TO-DO model lending:" in output and "Catalog.free" in output and not errors, (output, errors)
    assert "still referenced at shelf/loans.py:" in output, output
    catalog = root / "shelf/catalog.py"
    catalog_source = catalog.read_text(encoding="utf-8")
    old_definition = '    def free(self, book):\n        return self.copies.get(book, 0)\n\n'
    assert catalog_source.count(old_definition) == 1
    catalog.write_text(catalog_source.replace(old_definition, ""), encoding="utf-8")
    loans = root / "shelf/loans.py"
    loan_source = loans.read_text(encoding="utf-8")
    assert loan_source.count("self.catalog.free(book)") == 1
    loans.write_text(loan_source.replace("self.catalog.free(book)", "self.catalog.copies.get(book, 0)"), encoding="utf-8")
    tests = {"tests/test_catalog.py": (("c.free(\"x\")", 'c.copies.get("x", 0)'),),
             "tests/test_loans.py": (("s.catalog.free(\"dune\")", 's.catalog.copies.get("dune", 0)'),)}
    for relative, replacements in tests.items():
        test_path = root / relative
        text = test_path.read_text(encoding="utf-8")
        for old, new in replacements:
            assert old in text
            text = text.replace(old, new)
        test_path.write_text(text, encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)



def test_target_keeps_state_unique_and_public_entries_owned(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "plan a lending split"), ("target", "add", "loans")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["state"].append("holds per book in order")
    data["components"].append({"id": "holds", "layer": "lending", "summary": "Records member reservations",
                               "responsibilities": ["record a member reservation"], "files": ["shelf/holds.py"],
                               "entrypoints": [], "state": ["holds per book in order"], "side_effects": [],
                               "depends_on": [], "tests": [], "models": []})
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "duplicate_owner:" in line
               and "state 'holds per book in order'" in line for line in output.splitlines()), output

    current = _load_map(root)
    desk = json.loads(json.dumps(next(component for component in current["components"] if component["id"] == "loans")))
    command = json.loads(json.dumps(next(component for component in current["components"] if component["id"] == "cli")))
    for component in (desk, command):
        for field in ("status", "fingerprint", "_hint"):
            component.pop(field, None)
    desk.update(id="lending-desk", summary="Lends free copies", responsibilities=["lend a free copy"],
                entrypoints=["shelf/loans.py:LoanService.borrow"])
    command["depends_on"] = ["lending-desk"]
    returns = {"id": "returns", "layer": "lending", "summary": "Takes back a lent copy",
               "responsibilities": ["take a lent copy back"], "files": ["shelf/returns.py"],
               "entrypoints": [], "state": [], "side_effects": [], "depends_on": [], "tests": [], "models": []}
    data["components"] = [desk, returns, command]
    data["remove"] = ["component:loans"]
    flow = json.loads(json.dumps(current["flows"][0]))
    flow["steps"] = [step.replace("loans:", "lending-desk:", 1) for step in flow["steps"]]
    data["flows"] = [flow]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    dropped = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped:" in line]
    assert len(dropped) == 1 and "entrypoint 'shelf/loans.py:LoanService.give_back'" in dropped[0], output
    assert "duplicate_owner:" not in output, output



def test_rename_a_field_through_the_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current_model = (root / ".flowguard/models/lending.py").read_bytes()
    for arguments in (("target", "start", "rename the member loan limit"), ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    code, output, errors = _check_without_writes(root, capsys)
    # A fresh copy changes nothing yet.
    assert code == 1 and "target_noop" in output and "1 error(s), 0 to-do" in output and not errors, (output, errors)

    model = root / ".flowguard/target/models/lending.py"
    source = model.read_text(encoding="utf-8")
    old_import = "from dataclasses import dataclass, replace\n"
    assert source.count(old_import) == 1
    source = source.replace(old_import, old_import + "from pathlib import Path\nfrom flowguard.map.facts import CodeFacts\n", 1)
    prefix, separator, suffix = source.rpartition("    return last\n")
    assert separator and not suffix
    model.write_text(prefix + '    facts = CodeFacts(Path(__file__).resolve().parents[2])\n'
                     '    facts.check("the lending replay still conforms", last.ok, last.format_text())\n'
                     '    facts.absent("LIMIT", ["shelf/members.py"])\n'
                     '    facts.present("LOAN_LIMIT", ["shelf/members.py"])\n'
                     '    return facts.report()\n', encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert "TO-DO model lending:" in output and "LIMIT" in output, output
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_model

    members = root / "shelf/members.py"
    source = members.read_text(encoding="utf-8")
    assert source.count("LIMIT") == 2 and "LOAN_LIMIT" not in source
    members.write_text(source.replace("LIMIT", "LOAN_LIMIT"), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_model


def test_current_design_only_model_stays_an_error_with_a_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    original = (root / ".flowguard/models/lending.py").read_text(encoding="utf-8")
    declaration = 'MODEL_ID = "lending"'
    assert original.count(declaration) == 1
    source = original.replace(declaration, 'MODEL_ID = "retired_current"')
    path = root / ".flowguard/models/retired_current.py"
    path.write_text(source + "\nDESIGN_ONLY = False\n", encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "design_only_model" in line and "retired_current.py" in line
               for line in output.splitlines()), output
    assert not any(line.startswith("TO-DO ") and "design_only_model" in line for line in output.splitlines()), output
    assert "move this file to .flowguard/target/models/" in output, output
    path.unlink()
    _assert_current_lending(root, capsys)


def test_target_child_can_plan_code_owned_by_its_component(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root, reports=True)
    source = '''from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "report_child"
PARENT = "reports"
IMPLEMENTED_BY = {"Overdue": "shelf/reports.py:overdue"}
TESTED_BY = {}
class Overdue:
    name = "Overdue"
    def __init__(self, bad=False): self.bad = bad
    def apply(self, late, state):
        result = (("alice", "book"),) if late or self.bad else ()
        return [FunctionResult(result, (late, result))]
def explorer(bad=False):
    return Explorer(Workflow((Overdue(bad),)), initial_states=((False, ()),), external_inputs=(False, True),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("only_overdue", "only late members appear",
                                          lambda s, t: s[1] == ((("alice", "book"),) if s[0] else ())),))
def build_explorer(): return explorer()
def broken_variants(): return {"ignores_lateness": explorer(True)}
def conformance():
    from types import SimpleNamespace
    from shelf.reports import overdue
    service = SimpleNamespace(loans=[("alice", "book")])
    return CodeFactsReport(tuple(Fact("actual overdue result", tuple(overdue(service, {"alice"} if late else set()))
                                     == ((("alice", "book"),) if late else ())) for late in (False, True)))
'''
    child = directory / "models/report_child.py"
    child.write_text(source, encoding="utf-8")
    assert not (root / "shelf/reports.py").exists()
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    assert any(line.startswith("TO-DO ") and "model_anchor_broken" in line and "shelf/reports.py" in line
               for line in output.splitlines()), output
    _assert_current_lending(root, capsys)

    child.write_text(source.replace("shelf/reports.py:overdue", "shelf/unowned_report.py:overdue"), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") and "anchor_outside_home" in line for line in output.splitlines()), output
    assert any(line.startswith("TO-DO ") and "shelf/unowned_report.py" in line
               for line in output.splitlines()), output

    # This final guard observes the current tree after removing the overlay.
    code, output, errors = _run(root, capsys, "target", "drop", "--yes")
    assert code == 0 and not errors and not directory.exists(), (output, errors)
    current_model = root / ".flowguard/models/lending.py"
    current_source = current_model.read_text(encoding="utf-8")
    anchor = "shelf/loans.py:LoanService.borrow"
    assert current_source.count(anchor) == 1
    current_model.write_text(current_source.replace(anchor, "shelf/loans.py:LoanService.missing_borrow"), encoding="utf-8")
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "model_anchor_broken" in line and "missing_borrow" in line
               for line in output.splitlines()), output


def test_target_refuses_to_remove_a_component_parent_with_children(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    for component in current['components']:
        if component['id'] in {'catalog', 'loans'}:
            component['parent'] = 'records'
            component['layer'] = 'records'
    current['components'].append(dict(
        id='records', layer='records', summary='Record subsystem', responsibilities=['group records'],
        files=[], tests=[], models=[], depends_on=[], status='draft'))
    _write_map(root, current)
    assert _run(root, capsys, 'map', 'check')[0] == 0
    assert _run(root, capsys, 'map', 'confirm', 'all')[0] == 0
    before = (root / '.flowguard/map.json').read_bytes()
    assert _run(root, capsys, 'target', 'start', 'remove the records parent')[0] == 0
    path = root / '.flowguard/target/map.json'
    draft = json.loads(path.read_text(encoding='utf-8'))
    draft['remove'] = ['component:records']
    path.write_text(json.dumps(draft), encoding='utf-8')
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith('ERROR') and 'target_invalid' in line and 'parent' in line and 'records' in line
               for line in output.splitlines()), output
    assert (root / '.flowguard/map.json').read_bytes() == before
    assert {component['id'] for component in _load_map(root)['components'] if component.get('parent') == 'records'} == {'catalog', 'loans'}


def _target_life_cycle_fixture_helpers():
    """Load only filesystem builders through the canonical current/target view."""
    from pathlib import Path
    import runpy
    from flowguard.map.mapfile import load_map, resolve_model_path
    from flowguard.map.targetfile import ModelView, build_target_view, load_target

    repository = Path(__file__).resolve().parents[1]
    active = load_target(repository)
    sources = {p.relative_to(repository).as_posix(): p.relative_to(repository).as_posix()
               for p in (repository / ".flowguard/models").glob("*.py")}
    helper_view = (build_target_view(repository, load_map(repository), active) if active is not None else
                   ModelView(repository, load_map(repository), sources, {Path(p).stem for p in sources}))
    helper_path = resolve_model_path(repository, ".flowguard/models/target_life_cycle.py", view=helper_view)
    assert helper_path is not None
    from flowguard.map.proof import model_namespace
    with model_namespace(helper_view):
        return runpy.run_path(str(helper_path))


def test_target_small_promotion_preserves_map_and_model_bytes(tmp_path):
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import build_target_view, load_target

    helpers = _target_life_cycle_fixture_helpers()
    make, stage, snapshot = helpers["make_project"], helpers["stage_target"], helpers["snapshot"]

    root = make(tmp_path / "promotion")
    stage(root)
    helpers["edit_missing_method"](root)
    report = native.check_target(root)
    assert not report.errors and any(f.code == "anchor_broken" for f in report.todos), report
    before = snapshot(root)
    assert native.promote_target(root) == 1
    assert snapshot(root) == before

    helpers["write_method"](root)
    report = native.check_target(root)
    assert not report.errors and not report.todos, report
    current, draft = load_map(root), load_target(root)
    expected = build_target_view(root, current, draft).data
    expected_models = {name: (root / rel).read_bytes() for name, rel in draft.models.items()}
    assert expected_models and expected_models["shelf_rule.py"] != (root / ".flowguard/models/shelf_rule.py").read_bytes()
    assert native.promote_target(root) == 0
    assert load_map(root) == expected
    assert all((root / ".flowguard/models" / name).read_bytes() == content
               for name, content in expected_models.items())
    assert not (root / ".flowguard/target").exists()
    assert not any(flow["id"] == "borrow" for flow in load_map(root)["flows"])
    loans = next(c for c in load_map(root)["components"] if c["id"] == "loans")
    assert loans["status"] == "draft" and "fingerprint" not in loans


def test_target_real_proof_dispositions_and_hard_boundaries(tmp_path):
    import json
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import build_target_view, load_target

    helpers = _target_life_cycle_fixture_helpers()
    make, stage, snapshot = helpers["make_project"], helpers["stage_target"], helpers["snapshot"]
    prove = helpers["probe_regular_model"]

    # Three related provenance cases share a small fixture, not a result.
    # Every changed artifact is reproved through real run_model_in_process AND a fresh
    # full check_target. No fabricated ModelResult or mocked model runner.
    root = make(tmp_path / "provenance")
    stage(root)
    code_path = root / "shelf/loans.py"
    model_path = root / ".flowguard/target/models/shelf_rule.py"
    original_code, original_model = code_path.read_bytes(), model_path.read_bytes()
    logical_model = root / ".flowguard/models/shelf_rule.py"

    code_path.write_text(original_code.decode().replace("value + capacity()", "value + capacity() + 1"), encoding="utf-8")
    view = build_target_view(root, load_map(root), load_target(root))
    result = prove(root, logical_model, view=view)
    assert result.status == "fail" and result.code_gaps, result
    assert set(result.code_gaps) <= set(result.problems)
    report = native.check_target(root)
    for message in result.code_gaps:
        assert any(f.node == "model shelf_rule" and f.message == message for f in report.todos), report
        assert not any(f.message == message for f in report.errors + report.warnings), report

    code_path.write_bytes(original_code)
    source = original_model.decode()
    assert source.count('return {"advance_twice": make(2)}') == 1
    model_path.write_text(source.replace('return {"advance_twice": make(2)}',
                                         'return {"advance_twice": make(1)}'), encoding="utf-8")
    view = build_target_view(root, load_map(root), load_target(root))
    result = prove(root, logical_model, view=view)
    assert result.status == "fail" and not result.code_gaps, result
    design_failures = [p for p in result.problems if "known-bad variant" in p and "passed" in p]
    assert design_failures, result
    report = native.check_target(root)
    for message in design_failures:
        assert any(f.node == "model shelf_rule" and f.message == message for f in report.errors), report
        assert not any(f.message == message for f in report.todos + report.warnings), report

    partial = original_model.decode().replace("invariants=(RULE,)", "invariants=(RULE, SECOND)")
    partial += ('\nTESTED_BY = {"one_loan_step": ["tests/test_shelf.py:test_advance"]}\n'
                'SECOND = Invariant("at_most_one", "no double advance", lambda s,t: s <= 1)\n')
    model_path.write_text(partial, encoding="utf-8")
    partial_model = model_path.read_bytes()
    view = build_target_view(root, load_map(root), load_target(root))
    result = prove(root, logical_model, view=view)
    assert result.status == "pass" and not result.code_gaps and not result.problems, result
    assert any(w.startswith("invariant_untested:") for w in result.warnings), result
    report = native.check_target(root)
    assert not report.errors and not report.todos, report
    assert any(f.node == "model shelf_rule" and f.code == "invariant_untested" for f in report.warnings), report
    assert not any(f.code == "invariant_untested" for f in report.errors + report.todos), report
    assert native.main(["check", "--root", str(root)]) == 0
    assert code_path.read_bytes() == original_code and model_path.read_bytes() == partial_model


    # Four actual hard boundaries must remain ERROR, independently of TODO
    # allowances for missing future code. Each case starts from new real files.
    # Full check_target is invoked with its normal model selection; no models
    # flag, runner patch or fabricated Finding/ModelResult supplies a verdict.
    for code in ("owner_dropped", "entrypoint_owner", "design_only_model", "runner_model"):
        hard_root = make(tmp_path / ("hard-" + code))
        stage(hard_root, with_model=False)
        target_path = hard_root / ".flowguard/target/map.json"
        draft = json.loads(target_path.read_text(encoding="utf-8"))
        marker = None
        if code == "owner_dropped":
            draft["remove"] = ["component:catalog"]
            draft["components"][0]["depends_on"] = []
            target_path.write_text(json.dumps(draft), encoding="utf-8")
        elif code == "entrypoint_owner":
            draft["components"][0]["entrypoints"].append("shelf/catalog.py:capacity")
            target_path.write_text(json.dumps(draft), encoding="utf-8")
        elif code == "design_only_model":
            path = hard_root / ".flowguard/models/shelf_rule.py"
            path.write_text(path.read_text(encoding="utf-8") + "\nDESIGN_ONLY = False\n", encoding="utf-8")
        else:
            marker = hard_root / "legacy-runner-was-executed.marker"
            runner = hard_root / ".flowguard/verification/owners/legacy/run_checks.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("from pathlib import Path\nPath(" + repr(str(marker)) +
                              ").write_text('executed')\nraise RuntimeError('legacy runner executed')\n", encoding="utf-8")
        before = snapshot(hard_root)
        report = native.check_target(hard_root)
        assert any(f.code == code for f in report.errors), (code, report)
        assert not any(f.code == code for f in report.todos + report.warnings), (code, report)
        assert snapshot(hard_root) == before
        if marker is not None:
            assert marker.is_absolute() and not marker.exists()


def test_read_target_changes_skip_computed_coverage(tmp_path, capsys, monkeypatch):
    """A target that adds one entrypoint reports that entrypoint, not recomputed coverage text."""
    root = shelf_project(tmp_path)
    capsys.readouterr()
    target = json.loads(SHELF_TARGET["map.json"])
    loans = target["components"][0]
    loans["responsibilities"] = loans["responsibilities"][:2]
    loans["state"] = ["current loans"]
    target["goal"] = "one more loans entrypoint"
    (root / ".flowguard/target").mkdir()
    (root / ".flowguard/target/map.json").write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (output, errors)
    changes = [line for line in output.splitlines() if line.strip().startswith("changes:")]
    assert changes and all("coverage" not in line for line in changes), output
    assert any("code + shelf/loans.py:LoanService.hold" in line for line in changes), output
    assert "\n\n\n" not in output


def test_dropping_a_responsibility_is_owner_dropped(tmp_path, capsys):
    """A responsibility needs a new owner or an explicit responsibility:<text> retirement."""
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "loans lends only"), ("target", "add", "loans"), ("target", "add", "catalog")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    loans = next(component for component in data["components"] if component["id"] == "loans")
    loans["responsibilities"] = ["lend a free copy"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    dropped = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped: responsibility" in line]
    assert code == 1 and len(dropped) == 1 and "'take a lent copy back'" in dropped[0], output
    assert '"responsibility:take a lent copy back" in remove' in dropped[0]
    data["remove"] = ["responsibility:take a lent copy back"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "owner_dropped" not in output and "target_invalid" not in output, output
    data["remove"] = []
    catalog = next(component for component in data["components"] if component["id"] == "catalog")
    catalog["responsibilities"].append("take a lent copy back")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "owner_dropped" not in output, output
    data["remove"] = ["responsibility:no such duty"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "target_invalid" in output and "remove names no current node" in output, output


def _target_with(root, capsys, goal, *nodes):
    for arguments in (("target", "start", goal), *(("target", "add", node) for node in nodes)):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    return root / ".flowguard/target/map.json"


def test_unchanged_target_is_target_noop(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _target_with(root, capsys, "copy loans", "loans")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_noop: the target changes nothing yet" in output, output
    before = (root / ".flowguard/map.json").read_bytes()
    code, refused, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "promote refused:" in refused + errors
    assert (root / ".flowguard/map.json").read_bytes() == before
    code, output, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 0, (output, errors)
    model = root / ".flowguard/target/models/lending.py"
    model.write_text(model.read_text(encoding="utf-8") + "\n# only a comment\n", encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "target_noop" in output, output


def test_behaviour_target_without_a_rule_is_untied(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "loans can renew", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["entrypoints"].append("shelf/loans.py:LoanService.renew")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_goal_untied: the target changes a promise (entrypoints: " \
        "shelf/loans.py:LoanService.renew)" in output, output
    assert "goal rules: none\n" in output and "target_noop" not in output
    code, output, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 0, (output, errors)
    model = root / ".flowguard/target/models/lending.py"
    source = model.read_text(encoding="utf-8")
    model.write_text(source.replace(
        '              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))',
        '              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit),\n'
        '              Invariant("renewal_keeps_limit", "a renewal never exceeds LIMIT", _limit))'), encoding="utf-8")
    from flowguard.map.target import check_target, render_target_report
    output = render_target_report(check_target(root, models=False))      # goal rules are static
    assert "target_goal_untied" not in output and "goal rules: model lending: +renewal_keeps_limit" in output, output
    code, shown, errors = _run(root, capsys, "read", "--target")
    assert "goal rules: model lending: +renewal_keeps_limit" in shown, shown


def test_structure_only_target_prints_structure_goal(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "reword and move", "loans", "catalog")
    data = json.loads(path.read_text(encoding="utf-8"))
    loans, catalog = data["components"]
    loans["summary"] = "Lends books and takes them back."
    code, output, errors = _check_without_writes(root, capsys)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "target_goal_untied" not in output and "target_noop" not in output, output
    assert "goal rules: none (no promise changes" in output
    # moving an entrypoint between components keeps the project-wide set
    catalog["entrypoints"].append(loans["entrypoints"].pop())
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "target_goal_untied" not in output, output
    # retiring an entrypoint explicitly is governed by owner_dropped, not by goal rules
    catalog["entrypoints"].pop()
    data["remove"] = ["entrypoint:shelf/loans.py:LoanService.give_back"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "target_goal_untied" not in output and "goal rules: none (no promise changes" in output, output


def test_copied_but_unchanged_entry_stays_an_error(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "describe loans better", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["summary"] = "Lends books to members and takes them back."
    path.write_text(json.dumps(data), encoding="utf-8")
    code_path = root / "shelf/loans.py"
    source = code_path.read_text(encoding="utf-8")
    assert source.count("def give_back(") == 1
    code_path.write_text(source.replace("def give_back(", "def hand_back("), encoding="utf-8")
    code, output, errors = _run(root, capsys, "change")
    broken = [line for line in output.splitlines() if line.split()[1:2] == ["anchor_broken"] and "give_back" in line]
    assert code == 1 and broken and all(line.startswith("ERROR") and "moving to target" not in line for line in broken), output
    data["components"][0]["entrypoints"] = [entry.replace("give_back", "hand_back") for entry in data["components"][0]["entrypoints"]]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "change")
    broken = [line for line in output.splitlines() if line.split()[1:2] == ["anchor_broken"] and "give_back" in line]
    assert broken and all("moving to target: " in line for line in broken), output


OLD_CHILD_MODEL = '''from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "loan_count"
PARENT = "lending"
IMPLEMENTED_BY = {"Count": "shelf/loans.py:LoanService.count"}
class Count:
    name = "Count"
    def __init__(self, value=0): self.value = value
    def apply(self, event, state):
        return (FunctionResult(self.value, self.value, label="counted"),)
ZERO = Invariant("starts_at_zero", "a fresh service counts no loans", lambda s, t:
    InvariantResult.pass_() if s == 0 else InvariantResult.fail("not zero"))
SANE = Invariant("never_negative", "a count is never negative", lambda s, t:
    InvariantResult.pass_() if s >= 0 else InvariantResult.fail("negative"))
def make(value):
    return Explorer(Workflow((Count(value),)), (0,), ("count",), invariants=(ZERO, SANE),
                    max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(0)
def broken_variants(): return {"counts_one": make(1)}
def conformance():
    from shelf.loans import LoanService
    actual = LoanService().count("ann")
    return CodeFactsReport((Fact("fresh_count_is_zero", actual == 0, repr(actual)),))
'''


def test_old_findings_of_unchanged_models_do_not_block(tmp_path, capsys):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import ignore_patterns
    from flowguard.map.target import _unchanged_models
    from flowguard.map.targetfile import build_target_view, load_target
    from flowguard.map.tree import build_tree

    root = shelf_project(tmp_path)
    (root / ".flowguard/models/loan_count.py").write_text(OLD_CHILD_MODEL.replace('MODEL_ID = "loan_count"', 'MODEL_ID = "loan_count"\nimport _lending_bridge').replace('PARENT = "lending"', 'PARENT = "loans"'), encoding="utf-8")
    # This is a two-hop import dependency, not an exclusive parent/child decomposition.
    (root / ".flowguard/models/_lending_bridge.py").write_text("import lending\n", encoding="utf-8")
    assert cli.main(["map", "confirm", "all", "--root", str(root)]) == 0
    path = _target_with(root, capsys, "describe the catalog; one more lending known-bad", "catalog", "lending")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["summary"] = "Counts the free copies of each book."
    path.write_text(json.dumps(data), encoding="utf-8")
    model = root / ".flowguard/target/models/lending.py"
    old = 'return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit())}'
    model.write_text(model.read_text(encoding="utf-8").replace(
        old, old[:-1] + ', "no_limit_again": _explorer(NoLimit())}'), encoding="utf-8")
    # One real check: the old uncovered invariant of the unchanged child is a WARN and promotion stays open.
    code, output, errors = _check_without_writes(root, capsys)
    old_lines = [line for line in output.splitlines() if line.startswith("WARN  model loan_count: old_finding: ")]
    assert code == 0 and len(old_lines) == 1 and "uncovered_invariant: invariant 'never_negative'" in old_lines[0], output
    assert "(already in the current tree; the target does not change this model or its code;" in old_lines[0]
    assert any("(1 old)" in line for line in output.splitlines()) and "next: python -m flowguard target promote" in output

    def classify():
        current = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
        target = load_target(root)
        view = build_target_view(root, current, target)
        inv = build_inventory(root, ignore_patterns(view.data), write_cache=False)
        tree = build_tree(root, view.data, inv, view=view)
        return _unchanged_models(root, current, target, inv, tree, ["lending", "loan_count"])

    assert classify() == ({"loan_count"}, {"loan_count"})
    # Its anchored code changes: still unchanged by the target, but no longer old (it stays ERROR / TO-DO,
    # with the "model unchanged by the target" note that check_target adds for such models).
    loans = root / "shelf/loans.py"
    loans.write_text(loans.read_text(encoding="utf-8") + "\nLOANS_EDITED = True\n", encoding="utf-8")
    assert classify() == ({"loan_count"}, set())


def test_target_check_warns_about_debts_it_makes_stale(tmp_path, capsys):
    root = shelf_project(tmp_path)
    data = _load_map(root)
    data["accepted_debts"] = [{"code": "untested_component", "component": "members",
                               "reason": "members are tested through the loans tests"}]
    _write_map(root, data)
    capsys.readouterr()
    path = _target_with(root, capsys, "merge members into loans", "loans", "cli", "flow:borrow")
    target = json.loads(path.read_text(encoding="utf-8"))
    target["remove"] = ["component:members", "entrypoint:shelf/members.py:Members.may_borrow", "state:known members",
                        "responsibility:enforce the loan limit"]
    loans = next(component for component in target["components"] if component["id"] == "loans")
    loans["files"].append("shelf/members.py")
    loans["depends_on"].remove("members")
    target["flows"][0]["steps"] = [step.replace("members:", "loans:", 1) for step in target["flows"][0]["steps"]]
    path.write_text(json.dumps(target), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    stale = [line for line in output.splitlines() if line.startswith("WARN ") and "debt_stale" in line]
    assert code == 0 and len(stale) == 1, output
    assert "members are tested through the loans tests" in stale[0]
    assert stale[0].endswith("(remove the debt in the target's accepted_debts)")
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0 and "promoted" in output, (output, errors)


def test_promote_lists_what_to_re_read(tmp_path, capsys):
    import re

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "lending under a shelf policy", "catalog", "lending")
    target = json.loads(path.read_text(encoding="utf-8"))
    target["components"][0]["summary"] = "Counts the free copies of each book."
    path.write_text(json.dumps(target), encoding="utf-8")
    models = root / ".flowguard/target/models"
    source = (models / "lending.py").read_text(encoding="utf-8")
    # A component grouping changes placement without inventing a second domain model.
    parent = dict(id="shelf_policy", layer="lending", summary="Group shelf policy code", responsibilities=["group the lending components"],
                  files=[], tests=[], models=[], depends_on=[], state=[], side_effects=[])
    target["components"].append(parent)
    current_loans = next(c for c in _load_map(root)["components"] if c["id"] == "loans")
    target["components"].append({**{k:v for k,v in current_loans.items() if k not in {"status","fingerprint","_hint"}}, "parent": "shelf_policy"})
    path.write_text(json.dumps(target), encoding="utf-8")
    source = source.replace('MODEL_ID = "lending"', 'MODEL_ID = "lending"\nPARENT = "shelf_policy"')
    source = source.replace(',\n             "limit_respected": ["tests/test_loans.py:test_limit"]}', '}')
    (models / "lending.py").write_text(source, encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0, (output, errors)
    lines = output.splitlines()
    assert "re-read: model lending: its parent changed from loans to shelf_policy; check its purpose" in lines, output
    assert "re-read: flow borrow: it crosses changed component loans; check its steps and model" in lines, output
    assert "re-read: test tests/test_loans.py:test_limit: no longer bound by any TESTED_BY; bind it or delete it" in lines
    assert lines.index("re-read: test tests/test_loans.py:test_limit: no longer bound by any TESTED_BY; bind it or delete it") \
        < next(index for index, line in enumerate(lines) if line.startswith("next: "))


def test_removed_component_file_hint_says_delete(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "retire members", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["remove"] = ["component:members"]
    data["components"][0]["depends_on"].remove("members")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    unmapped = [line for line in output.splitlines() if line.startswith("TO-DO ") and "file_unmapped" in line
                and "shelf/members.py" in line]
    assert unmapped and unmapped[0].endswith("(delete the file, or give it an owner in the target)"), output


def test_target_check_reports_unwritten_code_as_todo(tmp_path, capsys):
    """An entrypoint the target plans but the code does not have yet is a TO-DO, never an ERROR."""
    from flowguard.map.target import check_target

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "loans can renew", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["entrypoints"].append("shelf/loans.py:LoanService.renew")
    path.write_text(json.dumps(data), encoding="utf-8")
    report = check_target(root, models=False)
    assert any(f.code == "anchor_broken" and "renew" in f.message for f in report.todos), report
    assert not any(f.code == "anchor_broken" for f in report.errors), report


def test_promote_refuses_inputs_changed_after_its_check(tmp_path, capsys, monkeypatch):
    """promote_target checks once; when a checked input changes afterwards it refuses and writes nothing."""
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers()
    root = helpers["make_project"](tmp_path / "promotion")
    helpers["stage_target"](root)
    helpers["edit_missing_method"](root)
    helpers["write_method"](root)
    original = native.check_target

    def check_then_edit(checked_root, **options):
        report = original(checked_root, **options)
        model = Path(checked_root) / ".flowguard/target/models/shelf_rule.py"
        model.write_text(model.read_text(encoding="utf-8") + "\n# edited after the check\n", encoding="utf-8")
        return report

    monkeypatch.setattr(native, "check_target", check_then_edit)
    current = (root / ".flowguard/map.json").read_bytes()
    capsys.readouterr()
    assert native.promote_target(root) == 1
    assert "promote refused: checked inputs changed" in capsys.readouterr().out
    assert (root / ".flowguard/target").is_dir() and (root / ".flowguard/map.json").read_bytes() == current


def test_shelf_example_matches_the_fixture_and_runs_the_target_workflow(tmp_path, capsys):
    """examples/shelf holds the shelf fixture as files; copied out it runs the whole target workflow."""
    import shutil

    example = Path(__file__).resolve().parents[1] / "examples/shelf"
    expected = {**SHELF_BASE,
                **{"target/" + name: SHELF_TARGET[name] for name in ("map.json", "models/lending.py")},
                **{"after/" + name: SHELF_AFTER[name] for name in ("shelf/loans.py", "tests/test_loans.py")}}
    found = {path.relative_to(example).as_posix(): path.read_bytes().decode("utf-8").replace("\r\n", "\n")
             for path in example.rglob("*") if path.is_file() and path.name != "README.md" and "__pycache__" not in path.parts}
    assert found == {name: text.replace("\r\n", "\n") for name, text in expected.items()}
    root = tmp_path / "shelf"          # the project is the example without its target/ and after/ folders
    for part in (".flowguard", "shelf", "tests"):
        shutil.copytree(example / part, root / part)
    git = ["git", "-c", "core.autocrlf=false", "-c", "user.name=FlowGuard tests",
           "-c", "user.email=flowguard-tests@example.invalid"]
    for arguments in (("init", "-q"), ("add", "."), ("commit", "-qm", "shelf baseline")):
        subprocess.run([*git, *arguments], cwd=root, check=True, capture_output=True)
    assert _run(root, capsys, "map", "confirm", "all")[0] == 0
    shutil.copytree(example / "target", root / ".flowguard/target")
    code, output, errors = _run(root, capsys, "target", "check")
    assert code == 3 and "TO-DO" in output and "ERROR" not in output, (output, errors)
    shutil.copytree(example / "after", root, dirs_exist_ok=True)
    code, output, errors = _run(root, capsys, "target", "check")
    assert code == 0, (output, errors)
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0 and not (root / ".flowguard/target").exists(), (output, errors)


def test_refused_promote_prints_the_report(tmp_path, monkeypatch, capsys):
    from flowguard.map import target
    root = shelf_project(tmp_path)
    assert target.start_target(root, "invalid goal case") == 0
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text())
    data["goal"] = ""
    path.write_text(json.dumps(data))
    paths = [root / ".flowguard/map.json", *(root / ".flowguard/models").glob("*.py"), path]
    before = {p: p.read_bytes() for p in paths}
    original, calls = target.check_target, []
    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(target, "check_target", counted)
    capsys.readouterr()
    assert target.promote_target(root) == 1
    output = capsys.readouterr().out
    assert "ERROR" in output and "promote refused: 1 error(s), 0 to-do" in output
    assert len(calls) == 1
    assert all(p.read_bytes() == content for p, content in before.items())


# FG-403: small native fixtures exercise the public target route.
def _fg403_helpers():
    import runpy
    directory = Path(__file__).resolve().parents[1] / ".flowguard/models"
    if not (directory / "_gap_cases.py").is_file():
        directory = directory.parent / "target/models"
    return runpy.run_path(str(directory / "_gap_cases.py"))


def test_rule_broken_by_old_code_is_an_expected_gap(tmp_path):
    from flowguard.map import target as native
    helpers = _fg403_helpers()
    root = tmp_path
    helpers["make_project"](root, helpers["regular_source"]())
    native.start_target(root, "raise the native answer")
    native.add_to_target(root, "one")
    (root / ".flowguard/target/models/one.py").write_text(helpers["regular_source"](expected=2))
    report = native.check_target(root)
    assert not report.errors and report.todos
    assert "EXPECTED GAP one:" in native.render_target_report(report)
    (root / "native.py").write_text("def value(): return 2\n")
    report = native.check_target(root)
    assert not report.errors and not report.todos
    assert "NO GAP one:" in native.render_target_report(report)
    assert native.promote_target(root) == 0
    assert "model_digests" in _load_map(root)


def test_split_into_child_prints_moved_rules_only():
    result = _fg403_helpers()["native_case"]("move")
    assert "moved rules only: moved (1 from one; no gap expected)" in result["text"]
    assert ">positive (from one)" in str(result["goal"])


def test_recorded_rule_prints_no_gap():
    result = _fg403_helpers()["native_case"]("recorded")
    assert "NO GAP one:" in result["text"] and not result["errors"] and not result["todos"]


def test_missing_bound_test_is_never_a_gap():
    result = _fg403_helpers()["native_case"]("missing_test")
    assert "NO GAP one:" in result["text"] and "EXPECTED GAP" not in result["text"]
    assert not result["todos"]


@pytest.mark.parametrize("case", ["anchor_exception", "engine_exception", "adapter_exception"])
def test_exception_classification(case):
    result = _fg403_helpers()["native_case"](case)
    if case == "anchor_exception":
        assert "EXPECTED GAP one:" in result["text"] and result["todos"] and not result["errors"]
    else:
        assert result["errors"] and "EXPECTED GAP" not in result["text"]
        assert "getattr(report," in result["text"]


def test_rule_reading_a_changed_table_is_changed():
    result = _fg403_helpers()["native_case"]("table")
    assert "~answer" in str(result["goal"]) and "EXPECTED GAP one:" in result["text"]


def test_kit_model_binding_edit_prints_no_rule_change():
    result = _fg403_helpers()["native_case"]("kit_binding")
    assert "no rule change: one" in result["text"] and not result["errors"]


def test_kit_feature_table_change_changes_the_rules(tmp_path):
    from flowguard.map import target as native
    from flowguard.map.facets import target_goal_rules
    from flowguard.map.targetfile import load_target
    helpers = _fg403_helpers()
    source = helpers["KIT_SOURCE"]
    helpers["make_project"](tmp_path, source)
    native.start_target(tmp_path, "change a kit feature")
    native.add_to_target(tmp_path, "one")
    (tmp_path / ".flowguard/target/models/one.py").write_text(source.replace("lambda value: 1", "lambda value: 2"))
    goal = target_goal_rules(tmp_path, load_target(tmp_path))
    assert len(goal) == 1 and "~" in goal[0], goal


@pytest.mark.parametrize("case", ["remove_clean", "remove_gap"])
def test_removed_rule_only_prints_no_rule_change(case):
    result = _fg403_helpers()["native_case"](case)
    assert "no rule change: one" in result["text"]
    assert ("code gap(s) are TO-DO" in result["text"]) == (case == "remove_gap")


def test_name_added_to_two_models_moves_into_one():
    result = _fg403_helpers()["native_case"]("move_twice")
    assert "moved rules only: moved" in result["text"] and "model second: +positive" in str(result["goal"])


def test_writes_only_target_prints_no_rule_change(tmp_path):
    from flowguard.map import target as native
    helpers = _fg403_helpers()
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    native.start_target(tmp_path, "declare the write footprint")
    native.add_to_target(tmp_path, "one")
    p = tmp_path / ".flowguard/target/models/one.py"
    p.write_text(p.read_text().replace('name = "Value"', 'name = "Value"\n    writes = ("value",)'))
    text = native.render_target_report(native.check_target(tmp_path))
    assert "no rule change: one" in text and "~answer" not in text


def _fg403_clean_target(tmp_path):
    from flowguard.map import target as native
    helpers = _fg403_helpers()
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    native.start_target(tmp_path, "record a positive native answer")
    native.add_to_target(tmp_path, "one")
    (tmp_path / ".flowguard/target/models/one.py").write_text(helpers["regular_source"](positive=True))
    return native


def test_target_check_runs_no_pytest_and_promote_runs_one_check(tmp_path, monkeypatch):
    from flowguard.map import proof
    native = _fg403_clean_target(tmp_path)
    original = proof.run_bound_tests
    calls = []
    def counted(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)
    monkeypatch.setattr(proof, "run_bound_tests", counted)
    report = native.check_target(tmp_path)
    assert not report.errors and not report.todos and calls == []
    assert "bound tests: not run here; target promote runs them once" in native.render_target_report(report)
    assert native.promote_target(tmp_path) == 0 and len(calls) == 1


def test_promote_names_stale_component_to_confirm(tmp_path, capsys):
    from flowguard.map.cli import cmd_confirm
    from types import SimpleNamespace
    native = _fg403_clean_target(tmp_path)
    cmd_confirm(tmp_path, SimpleNamespace(ids=["app"]))
    path = tmp_path / "native.py"
    path.write_text(path.read_text() + "\n# source changed after confirmation\n")
    capsys.readouterr()
    assert native.promote_target(tmp_path) == 0
    assert "next: python -m flowguard map confirm app" in capsys.readouterr().out


def test_promote_oserror_keeps_replaced_files(tmp_path, monkeypatch, capsys):
    native = _fg403_clean_target(tmp_path)
    helpers = _fg403_helpers()
    second = tmp_path / ".flowguard/models/moved.py"
    second.write_text(helpers["regular_source"]("moved"))
    staged = tmp_path / ".flowguard/target/models/moved.py"
    staged.write_text(helpers["regular_source"]("moved", positive=True))
    before = (tmp_path / ".flowguard/models/one.py").read_bytes()
    second_before = second.read_bytes()
    write_bytes = Path.write_bytes
    def interrupted(path, content):
        if path == second.with_name("moved.py.tmp"):
            raise OSError("injected second model replacement")
        return write_bytes(path, content)
    monkeypatch.setattr(Path, "write_bytes", interrupted)
    assert native.promote_target(tmp_path) == 2
    assert (tmp_path / ".flowguard/target/.replaced/models/one.py").read_bytes() == before
    assert (tmp_path / ".flowguard/target/.replaced/models/moved.py").read_bytes() == second_before
    assert (tmp_path / ".flowguard/target/models/one.py").is_file()
    text = capsys.readouterr().err
    assert "promote stopped:" in text and "copy them back into .flowguard/ to restore" in text
    assert "git checkout" not in text


def _fg403_add_case(tmp_path, case):
    from flowguard.map import target as native
    from flowguard.map.common import content_digest, normalize_newlines
    helpers = _fg403_helpers()
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    path = tmp_path / ".flowguard/models/one.py"
    before = path.read_bytes()
    if case != "no_git":
        def git(*args):
            return subprocess.run(["git", "-c", "user.name=Guard", "-c", "user.email=guard@example.invalid", *args],
                                  cwd=tmp_path, check=True, capture_output=True)
        git("init", "-q")
        git("add", "native.py", ".flowguard/map.json")
        if case != "untracked":
            git("add", ".flowguard/models")
        git("commit", "-qm", "baseline")
    data = _load_map(tmp_path)
    data["model_digests"] = {".flowguard/models/one.py": content_digest(path)}
    if case in {"dirty", "promoted"}:
        path.write_bytes(before + b"\n# changed model\n")
    edited = path.read_bytes()
    if case == "promoted":
        data["model_digests"][".flowguard/models/one.py"] = content_digest(path)
    _write_map(tmp_path, data)
    native.start_target(tmp_path, "edit the model safely")
    native.add_to_target(tmp_path, "one")
    assert normalize_newlines(path.read_bytes()) == normalize_newlines(before if case == "dirty" else edited)
    assert normalize_newlines((tmp_path / ".flowguard/target/models/one.py").read_bytes()) == normalize_newlines(edited)


def test_target_add_keeps_untracked_model(tmp_path):
    _fg403_add_case(tmp_path, "untracked")


def test_target_add_after_uncommitted_promote_copies(tmp_path):
    _fg403_add_case(tmp_path, "promoted")


def test_target_add_moves_in_place_edit_of_committed_model(tmp_path):
    _fg403_add_case(tmp_path, "dirty")


def test_shelf_without_git_runs_the_whole_route(tmp_path):
    from flowguard.map import target as native
    helpers = _target_life_cycle_fixture_helpers()
    root = helpers["make_project"](tmp_path / "shelf")
    old = (root / ".flowguard/models/shelf_rule.py").read_bytes()
    assert not (root / ".git").exists()
    helpers["stage_target"](root)
    helpers["edit_missing_method"](root)
    assert not native.check_target(root).errors
    assert (root / ".flowguard/models/shelf_rule.py").read_bytes() == old
    helpers["write_method"](root)
    assert native.promote_target(root) == 0
    assert (root / ".flowguard/models/shelf_rule.py").read_bytes() != old
    assert not (root / ".flowguard/target").exists()


def test_in_place_edit_without_target_is_named(tmp_path):
    from flowguard.map.check import model_edit_findings
    from flowguard.map.common import content_digest
    helpers = _fg403_helpers()
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    p = tmp_path / ".flowguard/models/one.py"
    data = _load_map(tmp_path)
    data["model_digests"] = {".flowguard/models/one.py": content_digest(p)}
    p.write_text(p.read_text() + "\n# unplanned edit\n")
    assert len(model_edit_findings(tmp_path, data, "warn")) == 1
    assert model_edit_findings(tmp_path, data, "error")[0].level == "error"


def test_port_change_without_parent_is_an_error(tmp_path):
    import runpy
    from flowguard.map.target import check_target
    fixture = runpy.run_path(str(Path(__file__).parents[1]/".flowguard/models/_target_fixture.py"))
    fixture["make_port_project"](tmp_path)
    call = fixture["call_target"]
    assert call(tmp_path,"start","extend lending outputs") == 0
    assert call(tmp_path,"add","lending") == 0
    path = tmp_path/".flowguard/target/models/lending.py"
    path.write_text(path.read_text().replace('("lent","refused")}', '("lent","refused","waitlisted")}'))
    report = check_target(tmp_path,models=False)
    findings = [f for f in report.errors if f.code == "port_changed_parent_missing"]
    assert len(findings) == 1
    assert findings[0].message == "the target changes the port of lending (out +waitlisted) but not its parent desk; python -m flowguard target add desk, then make desk receive 'waitlisted' (a CHECK step that takes it; with a full-form HANDOFF entry, also map it there)"
    assert not (tmp_path/".flowguard/target/models/desk.py").exists()
    assert call(tmp_path,"add","desk") == 0
    assert not any(f.code == "port_changed_parent_missing" for f in check_target(tmp_path,models=False).errors)


def test_promote_runs_what_function_selection_reaches(tmp_path):
    """A real direct-calling test outside TESTED_BY must prevent promotion on failure."""
    from flowguard.map import target as native
    helpers=_target_life_cycle_fixture_helpers()
    root=helpers['make_project'](tmp_path/'selection')
    helpers['stage_target'](root);helpers['edit_missing_method'](root);helpers['write_method'](root)
    path=root/'tests/test_extra.py'
    path.write_text('from shelf.loans import advance\ndef test_extra():\n    advance(0)\n    assert False, "direct caller failed"\n')
    # No git uses the conservative file fallback; this test actually calls an anchor.
    assert native.promote_target(root)==1
    assert (root/'.flowguard/target').exists()
