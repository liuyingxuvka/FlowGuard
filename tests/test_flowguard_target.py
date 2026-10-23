"""Native target lifecycle tests and the reusable, self-contained shelf fixture."""

from __future__ import annotations

import json
import subprocess
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


def shelf_project(tmp_path: Path) -> Path:
    """Write the original shelf baseline, commit it, then confirm its current map."""
    root = tmp_path / "project"
    root.mkdir()
    for relative, text in SHELF_BASE.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    git = ["git", "-c", "core.autocrlf=false", "-c", "user.name=FlowGuard tests",
           "-c", "user.email=flowguard-tests@example.invalid"]
    for arguments in (("init", "-q"), ("add", "."), ("commit", "-qm", "shelf baseline")):
        subprocess.run([*git, *arguments], cwd=root, check=True, capture_output=True)
    assert cli.main(["map", "confirm", "all", "--root", str(root)]) == 0
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
    assert output.splitlines()[1].startswith('target: "holds": +0 ~3 -0 nodes')
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
    assert output.splitlines()[1].startswith(
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
    assert (root / ".flowguard/target/models/lending.py").read_bytes() == model.read_bytes()
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


def _assert_current_lending(root: Path, capsys) -> None:
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in output and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "models", "lending")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()) and not errors, (output, errors)
    assert "never_over_lent" in output and "limit_respected" in output
    assert "no_idle_copy_while_held" not in output


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
    for finding in ("component_empty", "anchor_broken", "test_missing", "dep_unused"):
        assert any(line.startswith("TO-DO ") and finding in line for line in output.splitlines()), output
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
    code, output, errors = _run(root, capsys, "map", "models", "ns_parent")
    assert code == 0 and "one_step_1" in output and "one_step_2" not in output, (output, errors)
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
    code, output, errors = _run(root, capsys, "map", "models", "ns_parent")
    assert code == 0 and "one_step_1" in output and "one_step_2" not in output, (output, errors)
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
    code, output, errors = _run(root, capsys, "map", "models", "ns_parent")
    assert code == 0 and "one_step_1" in output, (output, errors)


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
    assert code == expected_code and not errors, (output, errors)
    if expected_code == 1:
        assert "ERROR model lending:" in output and "flowguard_missing_external_dependency" in output
        assert "TESTED_BY dependency/import error" in output
    else:
        assert "TO-DO model lending:" in output and "shelf.future_feature" in output
        assert not any(line.startswith("ERROR ") for line in output.splitlines())


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
    assert "changes:" not in output and "was:" not in output
    (directory / "models/lending.py").unlink()
    (directory / "map.json").write_text(json.dumps({"schema": "flowguard.target.v1", "goal": "retire lending",
        "components": [], "flows": [], "remove": ["component:loans", "model:lending"]}), encoding="utf-8")
    code, removed, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (removed, errors)
    assert "## - loans" in removed and "\n  - model lending:" in removed, removed
    assert removed.count("(removed by the target)") == 2, removed
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
    assert "next: python -m flowguard change" in output
    assert not directory.exists()
    assert (root / ".flowguard/models/lending.py").read_bytes() == checked_model
    loans = next(component for component in _load_map(root)["components"] if component["id"] == "loans")
    assert loans["status"] == "draft" and "fingerprint" not in loans
    assert "tests/test_loans.py" in loans["tests"]
    code, output, errors = _run(root, capsys, "map", "confirm", "loans")
    assert code == 0 and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s), 0 warning(s)" in output and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "models", "lending", "--tests")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()), (output, errors)
    assert "no_idle_copy_while_held" in output
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
    destination = root / ".flowguard/models/lending.py"
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
    assert after_dirs == before_dirs
    assert set(after_files) == set(before_files)  # no backup or completion marker
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
    assert len(owner_errors) == 2, output
    assert any("entrypoint 'shelf/members.py:Members.may_borrow'" in line for line in owner_errors), output
    assert any("state 'known members'" in line for line in owner_errors), output
    all_errors = [line for line in output.splitlines() if line.startswith("ERROR ")]
    code, changed, errors = _run(root, capsys, "change")
    assert code == 0 and not errors, (changed, errors)
    assert f'TARGET "merge members into loans": {len(all_errors)} design error(s)' in changed, changed
    before_refusal = _project_snapshot(root)
    code, refused, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "promote refused:" in refused + errors, (refused, errors)
    assert "run python -m flowguard target check" in refused + errors
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
    data["remove"] = ["component:members", "entrypoint:shelf/members.py:Members.may_borrow", "state:known members"]
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
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)

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
