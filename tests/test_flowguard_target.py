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
