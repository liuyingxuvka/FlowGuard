"""Shared native process probes; pytest does not collect this module."""
import os,sys,subprocess,signal
from pathlib import Path
from flowguard import pytest_shards_cli as shard_runner

def process_cleanup_case(tmp_path, parent_exits):
    pidfile = tmp_path / "child.pid"
    script = (
        "import subprocess,sys,time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"Path({str(pidfile)!r}).write_text(str(child.pid)); "
        + ("sys.exit(0)" if parent_exits else "time.sleep(30)")
    )
    result = shard_runner._run_process(
        [sys.executable, "-c", script], cwd=tmp_path, environment=dict(os.environ),
        stdout_path=tmp_path / "stdout", stderr_path=tmp_path / "stderr",
        timeout_seconds=.5,
    )
    pid = int(pidfile.read_text())
    try:
        if Path(f"/proc/{pid}/stat").exists():
            assert Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
        else:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        if parent_exits:
            assert result["exit_code"] == 0 and result["lingering_killed"] is True
        else:
            assert result["exit_code"] != 0
        assert result["timed_out"] is not parent_exits
        assert result["cleanup_confirmed"] is True
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


import io
import json
import shutil
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
import pytest
from flowguard.map import cli as map_cli
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory

def map_git(root: Path, *args: str) -> None:
    # Templates are copied immediately after commits; keep background Git
    # maintenance from changing their object directories during that copy.
    subprocess.run(['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
                    '-C', str(root), *args], check=True, capture_output=True)

def map_write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def map_run(root: Path, *argv: str, capsys=None) -> tuple[int, str]:
    code = map_cli.main(['--root', str(root), *argv])
    out = capsys.readouterr().out if capsys else ''
    return (code, out)

def map_load(root: Path) -> dict:
    return json.loads((root / '.flowguard/map.json').read_text(encoding='utf-8'))

def map_save(root: Path, data: dict) -> None:
    (root / '.flowguard/map.json').write_text(json.dumps(data, indent=2), encoding='utf-8')

def map_fill(root: Path) -> dict:
    """What the AI does after scan: describe components, merge, set layers."""
    data = map_load(root)
    data['layers'] = ['entry', 'domain', 'infra']
    data['components'] = [{'id': 'api', 'layer': 'entry', 'summary': 'HTTP entry', 'responsibilities': ['accept order requests'], 'files': ['shop/api.py', 'shop/__init__.py'], 'entrypoints': ['shop/api.py:handle'], 'state': [], 'side_effects': [], 'depends_on': ['orders'], 'tests': [], 'models': [], 'status': 'draft', 'fingerprint': ''}, {'id': 'orders', 'layer': 'domain', 'summary': 'Order rules', 'responsibilities': ['place an order once'], 'files': ['shop/orders.py'], 'entrypoints': ['shop/orders.py:OrderService.place'], 'state': [], 'side_effects': [], 'depends_on': ['storage'], 'tests': ['tests/test_orders.py'], 'models': [], 'status': 'draft', 'fingerprint': ''}, {'id': 'storage', 'layer': 'infra', 'summary': 'Persistence', 'responsibilities': ['save orders to the database'], 'files': ['shop/storage.py'], 'entrypoints': ['shop/storage.py:save'], 'state': ['DB dict'], 'side_effects': ['writes DB'], 'depends_on': [], 'tests': ['tests/test_storage.py'], 'models': [], 'status': 'draft', 'fingerprint': ''}, {'id': 'web', 'layer': 'entry', 'summary': 'Browser client', 'responsibilities': ['render the shop page'], 'files': ['web/*.js'], 'entrypoints': ['web/app.js:x'], 'state': [], 'side_effects': [], 'depends_on': [], 'tests': [], 'models': [], 'status': 'draft', 'fingerprint': ''}]
    data['flows'] = [{'id': 'place_order', 'summary': 'request to saved order', 'steps': ['api:handle', 'orders:place', 'storage:save']}]
    map_save(root, data)
    return data

def map_codes(root: Path, command: str, capsys) -> list[str]:
    map_cli.main(['--root', str(root), command, '--json'])
    return [f['code'] for f in json.loads(capsys.readouterr().out)['findings']]

def map_impact_of(root, data, changed, **kwargs):
    from flowguard.map.impact import compute_impact
    return compute_impact(root, data, build_inventory(root, DEFAULT_IGNORE), changed, **kwargs)

def map__release_project(root, *, legacy=False):
    from hashlib import sha256
    from flowguard.map.common import SCHEMA, content_digest
    from flowguard.map.mapfile import fingerprint
    files = {'pkg/__init__.py': '"""__version__ = "example" note."""\n__version__: str = "1.0.0"\nX = 1\n', 'pyproject.toml': '[project]\nname = "app"\nversion = "1.0.0"\n[tool.x]\nversion = "stable"\n', 'VERSION': '1.0.0\n'}
    for path, text in files.items():
        map_write(root, path, text)
    comp = {'id': 'app', 'layer': 'app', 'summary': 'A versioned package', 'responsibilities': ['Declare package values'], 'files': list(files), 'status': 'confirmed', 'depends_on': [], 'tests': [], 'models': []}
    comp['fingerprint'] = fingerprint(root, list(files))
    if legacy:
        old = sha256()
        for path in sorted(files):
            old.update(f'{path}\x00{content_digest(root / path)}\n'.encode())
        comp['fingerprint'] = 'sha256:' + old.hexdigest()
    data = {'schema': SCHEMA, 'layers': ['app'], 'components': [comp], 'fingerprint_format': 1 if legacy else 2}
    map_write(root, '.flowguard/map.json', json.dumps(data))
    return (data, comp)

def map_function_fixture():
    import runpy, sys
    base = Path(__file__).parents[1] / '.flowguard'
    directory = base / 'target/models' if (base / 'target/models/_function_fixture.py').exists() else base / 'models'
    return runpy.run_path(str(directory / '_function_fixture.py'))

def map__signature_fixture(tmp_path, source, before, after):
    helper = map_function_fixture()
    data = helper['fixture'](tmp_path)
    helper['write'](tmp_path, 'core.py', source)
    helper['write'](tmp_path, '.flowguard/models/constructor.py', 'MODEL_ID="constructor"\nPARENT="api"\nIMPLEMENTED_BY={"Construct":"api.py:call"}\ndef build_explorer(): pass\n')
    map_git(tmp_path, 'add', '.')
    map_git(tmp_path, '-c', 'user.name=FlowGuard', '-c', 'user.email=model@example.invalid', 'commit', '-qm', 'signature baseline')
    helper['write'](tmp_path, 'core.py', source.replace(before, after))
    return map_impact_of(tmp_path, data, ['core.py'], base='HEAD')

def map__select_test_fixture(tmp_path):
    from flowguard.map.tree import build_tree
    h = map_function_fixture()
    data = h['fixture'](tmp_path)
    path = tmp_path / 'core.py'
    path.write_text(path.read_text().replace('def other(): return 2', 'def other(): return own()+1'))
    h['write'](tmp_path, 'tests/test_half.py', 'from core import own\ndef test_one(): assert own()\ndef test_two(): pass\n')
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    return (data, inv, build_tree(tmp_path, data, inv))
import json
import os
import signal
import subprocess
from pathlib import Path
import pytest
from flowguard.map import cli as proof_cli
from flowguard.template_text.behaviour import BEHAVIOUR_MODEL_TEMPLATE
from flowguard.map.inventory import build_inventory
from flowguard.map.common import DEFAULT_IGNORE
proof_MODEL_SOURCE = BEHAVIOUR_MODEL_TEMPLATE
proof_BUGGY = 'class OrderService:\n    def __init__(self):\n        self.orders = {}\n        self.charges = []\n\n    def place(self, order_id, amount):\n        self.charges.append(order_id)          # BUG: a retry charges again\n        self.orders[order_id] = amount\n        return "placed"\n'
proof_FIXED = 'class OrderService:\n    def __init__(self):\n        self.orders = {}\n        self.charges = []\n\n    def place(self, order_id, amount):\n        if order_id in self.orders:\n            return "already_placed"\n        self.charges.append(order_id)\n        self.orders[order_id] = amount\n        return "placed"\n'

def proof_write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def proof_models(root: Path, capsys, *extra: str) -> tuple[int, str]:
    code = proof_cli.main(['--root', str(root), 'models', *extra])
    return (code, capsys.readouterr().out)

def proof__native_model(root, path):
    """Exercise the native API without lending another temporary shop its imports."""
    import sys
    from flowguard.map.proof import run_model_in_process
    saved_path = sys.path[:]
    model_name = '_flowguard_model_' + path.stem
    saved = {name: module for name, module in sys.modules.items() if name == 'shop' or name.startswith('shop.') or name == model_name}
    for name in saved:
        sys.modules.pop(name)
    try:
        return run_model_in_process(root, path)
    finally:
        sys.path[:] = saved_path
        for name in list(sys.modules):
            if name == 'shop' or name.startswith('shop.') or name == model_name:
                sys.modules.pop(name)
        sys.modules.update(saved)
proof__MINIMAL_MODEL = proof_MODEL_SOURCE.replace('MODEL_ID = "order_placement"', 'MODEL_ID = "minimal"').replace('IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}', 'IMPLEMENTED_BY = {}').replace('def conformance():', 'def _unused_conformance():')
proof_MODEL = '.flowguard/models/order_placement.py'

def proof__edit_model(root, old, new):
    path = root / proof_MODEL
    text = path.read_text(encoding='utf-8')
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
proof__CRASH = ('return {"charge_every_time": _explorer(ChargeEveryTime())}', 'return {"charge_every_time": _explorer(Crashes())}')

def proof__check_codes(shop, capsys):
    proof_cli.main(['--root', str(shop), 'check'])
    return capsys.readouterr().out

def proof__anchor_watch_helpers():
    import runpy
    directory = Path(__file__).resolve().parents[1] / '.flowguard/models'
    if not (directory / 'anchor_watch.py').is_file():
        directory = directory.parent / 'target/models'
    return runpy.run_path(str(directory / 'anchor_watch.py'))

def proof__watch_native_module(tmp_path):
    import importlib.util
    path = tmp_path / 'native_calls.py'
    path.write_text('def ping(): return 1\n')
    spec = importlib.util.spec_from_file_location('native_calls', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def proof__size_project(root, **options):
    import runpy
    base = Path(__file__).resolve().parents[1] / '.flowguard'
    path = base / 'target/models/_size_fixture.py'
    if not path.exists():
        path = base / 'models/_size_fixture.py'
    return runpy.run_path(str(path))['fixture'](root, **options)
import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
import pytest
import flowguard.__main__ as target_cli
target_SHELF_BASE: dict[str, str] = {'.flowguard/map.json': '{\n  "schema": "flowguard.map.v1",\n  "project": "shelf",\n  "layers": [\n    "interface",\n    "lending",\n    "records"\n  ],\n  "ignore": [],\n  "test_command": "python -m pytest -q",\n  "components": [\n    {\n      "id": "cli",\n      "layer": "interface",\n      "summary": "Command line demo of lending.",\n      "responsibilities": [\n        "run the demo"\n      ],\n      "files": [\n        "shelf/cli.py",\n        "shelf/__init__.py"\n      ],\n      "entrypoints": [\n        "shelf/cli.py:main"\n      ],\n      "state": [],\n      "side_effects": [\n        "prints the result"\n      ],\n      "depends_on": [\n        "loans"\n      ],\n      "tests": [],\n      "models": [],\n      "status": "draft"\n    },\n    {\n      "id": "loans",\n      "layer": "lending",\n      "summary": "Lends and takes back books for members.",\n      "responsibilities": [\n        "lend a free copy",\n        "take a lent copy back"\n      ],\n      "files": [\n        "shelf/loans.py"\n      ],\n      "entrypoints": [\n        "shelf/loans.py:LoanService.borrow",\n        "shelf/loans.py:LoanService.give_back"\n      ],\n      "state": [\n        "current loans"\n      ],\n      "side_effects": [],\n      "depends_on": [\n        "catalog",\n        "members"\n      ],\n      "tests": [\n        "tests/test_loans.py"\n      ],\n      "models": [],\n      "status": "draft"\n    },\n    {\n      "id": "catalog",\n      "layer": "records",\n      "summary": "Counts free copies per book.",\n      "responsibilities": [\n        "count free copies"\n      ],\n      "files": [\n        "shelf/catalog.py"\n      ],\n      "entrypoints": [\n        "shelf/catalog.py:Catalog.take"\n      ],\n      "state": [\n        "free copies per book"\n      ],\n      "side_effects": [],\n      "depends_on": [],\n      "tests": [\n        "tests/test_catalog.py"\n      ],\n      "models": [],\n      "status": "draft"\n    },\n    {\n      "id": "members",\n      "layer": "records",\n      "summary": "Knows members and their loan limit.",\n      "responsibilities": [\n        "enforce the loan limit"\n      ],\n      "files": [\n        "shelf/members.py"\n      ],\n      "entrypoints": [\n        "shelf/members.py:Members.may_borrow"\n      ],\n      "state": [\n        "known members"\n      ],\n      "side_effects": [],\n      "depends_on": [],\n      "tests": [],\n      "models": [],\n      "status": "draft"\n    }\n  ],\n  "flows": [\n    {\n      "id": "borrow",\n      "summary": "member borrows a book",\n      "steps": [\n        "cli:main",\n        "loans:LoanService.borrow",\n        "members:Members.may_borrow",\n        "catalog:Catalog.take"\n      ]\n    }\n  ],\n  "accepted_debts": []\n}\n', '.flowguard/models/lending.py': '"""Lending model: a member never holds more than LIMIT loans and a book is never lent beyond its copies.\nProtected failures: lending a copy that is not free; exceeding the member limit; returning what was not lent.\n"""\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, replace\n\nfrom flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces\nfrom flowguard.conformance import projected_output_matches, projected_state_matches\nfrom flowguard.explorer import Explorer\n\nMODEL_ID = "lending"\nIMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow", "GiveBack": "shelf/loans.py:LoanService.give_back"}\nTESTED_BY = {"never_over_lent": ["tests/test_loans.py:test_borrow_and_return"],\n             "limit_respected": ["tests/test_loans.py:test_limit"]}\nSTOCK = {"b": 1, "c": 2}\nLIMIT = 2\n\n\n@dataclass(frozen=True)\nclass Borrow:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass GiveBack:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass State:\n    loans: tuple = ()\n\n\ndef _free(state, book):\n    return STOCK.get(book, 0) - sum(1 for _, b in state.loans if b == book)\n\n\nclass BorrowBlock:\n    name = "Borrow"\n    accepted_input_type = Borrow\n\n    def apply(self, inp, state):\n        if sum(1 for m, _ in state.loans if m == inp.member) >= LIMIT:\n            return [FunctionResult("refused", state, label="refused")]\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass GiveBackBlock:\n    name = "GiveBack"\n    accepted_input_type = GiveBack\n\n    def apply(self, inp, state):\n        if (inp.member, inp.book) not in state.loans:\n            return [FunctionResult("not_lent", state, label="not_lent")]\n        loans = list(state.loans)\n        loans.remove((inp.member, inp.book))\n        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]\n\n\nclass LendAlways(BorrowBlock):\n    def apply(self, inp, state):\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass NoLimit(BorrowBlock):\n    def apply(self, inp, state):\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\ndef _never_over_lent(state, trace):\n    return InvariantResult.pass_() if all(_free(state, b) >= 0 for b in STOCK) else InvariantResult.fail("a book is lent beyond its copies")\n\n\ndef _limit(state, trace):\n    members = {m for m, _ in state.loans}\n    return InvariantResult.pass_() if all(sum(1 for m, _ in state.loans if m == x) <= LIMIT for x in members) else InvariantResult.fail("member over limit")\n\n\nINVARIANTS = (Invariant("never_over_lent", "a book is never lent beyond its copies", _never_over_lent),\n              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))\nINPUTS = (Borrow("ann", "b"), Borrow("bob", "b"), GiveBack("ann", "b"), Borrow("ann", "c"))\n\n\ndef _explorer(borrow) -> Explorer:\n    return Explorer(workflow=Workflow((borrow, GiveBackBlock()), mode="choice"), initial_states=(State(),),\n                    external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=4, progress_steps=0)\n\n\ndef build_explorer():\n    return _explorer(BorrowBlock())\n\n\ndef broken_variants():\n    return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit())}\n\n\nclass _Adapter:\n    def reset(self, initial_state):\n        from shelf.loans import LoanService\n        self.svc = LoanService()\n        for m in ("ann", "bob"):\n            self.svc.members.join(m)\n        for book, n in STOCK.items():\n            self.svc.catalog.add(book, n)\n\n    def apply_step(self, step):\n        inp = step.function_input\n        out = self.svc.borrow(inp.member, inp.book) if isinstance(inp, Borrow) else self.svc.give_back(inp.member, inp.book)\n        return ReplayObservation(function_name=step.function_name, observed_output=out, observed_state=self.observe_state())\n\n    def observe_state(self):\n        return State(loans=tuple(self.svc.loans))\n\n    def observe_output(self):\n        return None\n\n\ndef conformance():\n    last = None\n    for trace in select_covering_traces(build_explorer().explore().traces):\n        last = replay_trace(trace=trace, adapter=_Adapter(), invariants=INVARIANTS,\n                            rules=(projected_state_matches(), projected_output_matches()))\n        if not last.ok:\n            return last\n    return last\n', 'shelf/__init__.py': '"""Tiny library lending package."""\n', 'shelf/catalog.py': '"""Catalog of books and their free copies."""\n\n\nclass Catalog:\n    def __init__(self):\n        self.copies = {}\n\n    def add(self, book, count=1):\n        self.copies[book] = self.copies.get(book, 0) + count\n\n    def free(self, book):\n        return self.copies.get(book, 0)\n\n    def take(self, book):\n        if self.copies.get(book, 0) <= 0:\n            raise ValueError("no free copy")\n        self.copies[book] -= 1\n\n    def put_back(self, book):\n        self.copies[book] = self.copies.get(book, 0) + 1\n', 'shelf/cli.py': '"""Command line demo."""\n\nimport sys\n\nfrom shelf.loans import LoanService\n\n\ndef main(argv=None):\n    svc = LoanService()\n    svc.members.join("ann")\n    svc.catalog.add("dune", 1)\n    print(svc.borrow("ann", "dune"))\n    return 0\n\n\nif __name__ == "__main__":\n    sys.exit(main(sys.argv[1:]))\n', 'shelf/loans.py': '"""Lending: borrow and return books."""\n\nfrom shelf.catalog import Catalog\nfrom shelf.members import Members\n\n\nclass LoanService:\n    def __init__(self, catalog=None, members=None):\n        self.catalog = catalog or Catalog()\n        self.members = members or Members()\n        self.loans = []          # (member, book)\n\n    def count(self, member):\n        return sum(1 for m, _ in self.loans if m == member)\n\n    def borrow(self, member, book):\n        if not self.members.may_borrow(member, self.count(member)):\n            return "refused"\n        if self.catalog.free(book) <= 0:\n            return "unavailable"\n        self.catalog.take(book)\n        self.loans.append((member, book))\n        return "lent"\n\n    def give_back(self, member, book):\n        if (member, book) not in self.loans:\n            return "not_lent"\n        self.loans.remove((member, book))\n        self.catalog.put_back(book)\n        return "returned"\n', 'shelf/members.py': '"""Members and their loan limits."""\n\nLIMIT = 2\n\n\nclass Members:\n    def __init__(self):\n        self.known = set()\n\n    def join(self, member):\n        self.known.add(member)\n\n    def may_borrow(self, member, current_loans):\n        return member in self.known and current_loans < LIMIT\n', 'tests/test_catalog.py': 'from shelf.catalog import Catalog\n\n\ndef test_take_put_back():\n    c = Catalog()\n    c.add("x")\n    c.take("x")\n    assert c.free("x") == 0\n    c.put_back("x")\n    assert c.free("x") == 1\n', 'tests/test_loans.py': 'from shelf.loans import LoanService\n\n\ndef _svc():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    return s\n\n\ndef test_borrow_and_return():\n    s = _svc()\n    assert s.borrow("ann", "dune") == "lent"\n    assert s.borrow("ann", "dune") == "unavailable"\n    assert s.give_back("ann", "dune") == "returned"\n    assert s.catalog.free("dune") == 1\n\n\ndef test_limit():\n    s = _svc()\n    s.catalog.add("a", 3)\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "refused"\n'}
target_SHELF_TARGET: dict[str, str] = {'map.json': '{\n  "schema": "flowguard.target.v1",\n  "goal": "holds: a member may reserve a lent-out book; a returned copy goes to the first holder",\n  "components": [\n    {\n      "id": "loans",\n      "layer": "lending",\n      "summary": "Lends and takes back books for members.",\n      "responsibilities": [\n        "lend a free copy",\n        "take a lent copy back",\n        "hold a lent-out book for a member"\n      ],\n      "files": [\n        "shelf/loans.py"\n      ],\n      "entrypoints": [\n        "shelf/loans.py:LoanService.borrow",\n        "shelf/loans.py:LoanService.give_back",\n        "shelf/loans.py:LoanService.hold"\n      ],\n      "state": [\n        "current loans",\n        "holds per book in order"\n      ],\n      "side_effects": [],\n      "depends_on": [\n        "catalog",\n        "members"\n      ],\n      "tests": [\n        "tests/test_loans.py"\n      ],\n      "models": []\n    }\n  ],\n  "flows": [],\n  "remove": []\n}\n', 'map_reports.json': '{\n  "schema": "flowguard.target.v1",\n  "goal": "reports: list overdue loans",\n  "components": [\n    {\n      "id": "reports",\n      "layer": "lending",\n      "summary": "Lists overdue loans.",\n      "responsibilities": [\n        "list overdue loans"\n      ],\n      "files": [\n        "shelf/reports.py"\n      ],\n      "entrypoints": [\n        "shelf/reports.py:overdue"\n      ],\n      "state": [],\n      "side_effects": [],\n      "depends_on": [\n        "loans"\n      ],\n      "tests": [\n        "tests/test_reports.py"\n      ],\n      "models": []\n    }\n  ],\n  "flows": [],\n  "remove": []\n}\n', 'models/lending.py': '"""Lending model: loans respect copies and the member limit; a returned copy goes to the first member holding it.\nProtected failures: lending a copy that is not free; exceeding the member limit; a free copy left idle while a member holds the book.\n"""\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, replace\n\nfrom flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces\nfrom flowguard.conformance import projected_output_matches, projected_state_matches\nfrom flowguard.explorer import Explorer\n\nMODEL_ID = "lending"\nIMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow", "GiveBack": "shelf/loans.py:LoanService.give_back", "Hold": "shelf/loans.py:LoanService.hold"}\nTESTED_BY = {"never_over_lent": ["tests/test_loans.py:test_borrow_and_return"],\n             "limit_respected": ["tests/test_loans.py:test_limit"],\n             "no_idle_copy_while_held": ["tests/test_loans.py:test_hold_gets_returned_copy"]}\nSTOCK = {"b": 1, "c": 2}\nLIMIT = 2\n\n\n@dataclass(frozen=True)\nclass Borrow:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass GiveBack:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass Hold:\n    member: str\n    book: str\n\n\n@dataclass(frozen=True)\nclass State:\n    loans: tuple = ()\n    holds: tuple = ()\n\n\ndef _free(state, book):\n    return STOCK.get(book, 0) - sum(1 for _, b in state.loans if b == book)\n\n\nclass BorrowBlock:\n    name = "Borrow"\n    accepted_input_type = Borrow\n\n    def apply(self, inp, state):\n        if sum(1 for m, _ in state.loans if m == inp.member) >= LIMIT:\n            return [FunctionResult("refused", state, label="refused")]\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass GiveBackBlock:\n    name = "GiveBack"\n    accepted_input_type = GiveBack\n\n    def apply(self, inp, state):\n        if (inp.member, inp.book) not in state.loans:\n            return [FunctionResult("not_lent", state, label="not_lent")]\n        loans = list(state.loans)\n        loans.remove((inp.member, inp.book))\n        waiting = [h for h in state.holds if h[1] == inp.book]\n        if waiting:\n            first = waiting[0]\n            holds = list(state.holds)\n            holds.remove(first)\n            return [FunctionResult("returned", replace(state, loans=tuple(loans) + (first,), holds=tuple(holds)), label="handed_to_holder")]\n        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]\n\n\nclass HoldBlock:\n    name = "Hold"\n    accepted_input_type = Hold\n\n    def apply(self, inp, state):\n        if _free(state, inp.book) > 0 or (inp.member, inp.book) in state.holds:\n            return [FunctionResult("no_hold", state, label="no_hold")]\n        return [FunctionResult("held", replace(state, holds=state.holds + ((inp.member, inp.book),)), label="held")]\n\n\nclass GiveBackOld(GiveBackBlock):\n    def apply(self, inp, state):\n        if (inp.member, inp.book) not in state.loans:\n            return [FunctionResult("not_lent", state, label="not_lent")]\n        loans = list(state.loans)\n        loans.remove((inp.member, inp.book))\n        return [FunctionResult("returned", replace(state, loans=tuple(loans)), label="returned")]\n\n\nclass LendAlways(BorrowBlock):\n    def apply(self, inp, state):\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\nclass NoLimit(BorrowBlock):\n    def apply(self, inp, state):\n        if _free(state, inp.book) <= 0:\n            return [FunctionResult("unavailable", state, label="unavailable")]\n        return [FunctionResult("lent", replace(state, loans=state.loans + ((inp.member, inp.book),)), label="lent")]\n\n\ndef _never_over_lent(state, trace):\n    return InvariantResult.pass_() if all(_free(state, b) >= 0 for b in STOCK) else InvariantResult.fail("a book is lent beyond its copies")\n\n\ndef _limit(state, trace):\n    members = {m for m, _ in state.loans}\n    return InvariantResult.pass_() if all(sum(1 for m, _ in state.loans if m == x) <= LIMIT for x in members) else InvariantResult.fail("member over limit")\n\n\ndef _no_idle_copy(state, trace):\n    return InvariantResult.pass_() if all(_free(state, b) == 0 for _, b in state.holds) else InvariantResult.fail("a copy sits free while a member holds it")\n\n\nINVARIANTS = (Invariant("never_over_lent", "a book is never lent beyond its copies", _never_over_lent),\n              Invariant("no_idle_copy_while_held", "a held book has no free copy", _no_idle_copy),\n              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))\nINPUTS = (Borrow("ann", "b"), Borrow("bob", "b"), GiveBack("ann", "b"), Borrow("ann", "c"), Hold("bob", "b"))\n\n\ndef _explorer(borrow, giveback=None) -> Explorer:\n    giveback = giveback or GiveBackBlock()\n    return Explorer(workflow=Workflow((borrow, giveback, HoldBlock()), mode="choice"), initial_states=(State(),),\n                    external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=4, progress_steps=0)\n\n\ndef build_explorer():\n    return _explorer(BorrowBlock())\n\n\ndef broken_variants():\n    return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit()), "return_ignores_holds": _explorer(BorrowBlock(), GiveBackOld())}\n\n\nclass _Adapter:\n    def reset(self, initial_state):\n        from shelf.loans import LoanService\n        self.svc = LoanService()\n        for m in ("ann", "bob"):\n            self.svc.members.join(m)\n        for book, n in STOCK.items():\n            self.svc.catalog.add(book, n)\n\n    def apply_step(self, step):\n        inp = step.function_input\n        if isinstance(inp, Borrow):\n            out = self.svc.borrow(inp.member, inp.book)\n        elif isinstance(inp, Hold):\n            out = self.svc.hold(inp.member, inp.book)\n        else:\n            out = self.svc.give_back(inp.member, inp.book)\n        return ReplayObservation(function_name=step.function_name, observed_output=out, observed_state=self.observe_state())\n\n    def observe_state(self):\n        return State(loans=tuple(self.svc.loans), holds=tuple(getattr(self.svc, "holds", ())))\n\n    def observe_output(self):\n        return None\n\n\ndef conformance():\n    last = None\n    for trace in select_covering_traces(build_explorer().explore().traces):\n        last = replay_trace(trace=trace, adapter=_Adapter(), invariants=INVARIANTS,\n                            rules=(projected_state_matches(), projected_output_matches()))\n        if not last.ok:\n            return last\n    return last\n'}
target_SHELF_AFTER: dict[str, str] = {'shelf/loans.py': '"""Lending: borrow and return books."""\n\nfrom shelf.catalog import Catalog\nfrom shelf.members import Members\n\n\nclass LoanService:\n    def __init__(self, catalog=None, members=None):\n        self.catalog = catalog or Catalog()\n        self.members = members or Members()\n        self.loans = []          # (member, book)\n        self.holds = []          # (member, book) waiting in order\n\n    def count(self, member):\n        return sum(1 for m, _ in self.loans if m == member)\n\n    def borrow(self, member, book):\n        if not self.members.may_borrow(member, self.count(member)):\n            return "refused"\n        if self.catalog.free(book) <= 0:\n            return "unavailable"\n        self.catalog.take(book)\n        self.loans.append((member, book))\n        return "lent"\n\n    def give_back(self, member, book):\n        if (member, book) not in self.loans:\n            return "not_lent"\n        self.loans.remove((member, book))\n        waiting = [h for h in self.holds if h[1] == book]\n        if waiting:\n            self.holds.remove(waiting[0])\n            self.loans.append(waiting[0])\n            return "returned"\n        self.catalog.put_back(book)\n        return "returned"\n\n    def hold(self, member, book):\n        if self.catalog.free(book) > 0 or (member, book) in self.holds:\n            return "no_hold"\n        self.holds.append((member, book))\n        return "held"\n', 'shelf/reports.py': '"""Reports over current loans."""\n\nfrom shelf.loans import LoanService\n\n\ndef overdue(service: LoanService, members_late):\n    return [(member, book) for member, book in service.loans if member in members_late]\n', 'tests/test_loans.py': 'from shelf.loans import LoanService\n\n\ndef _svc():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    return s\n\n\ndef test_borrow_and_return():\n    s = _svc()\n    assert s.borrow("ann", "dune") == "lent"\n    assert s.borrow("ann", "dune") == "unavailable"\n    assert s.give_back("ann", "dune") == "returned"\n    assert s.catalog.free("dune") == 1\n\n\ndef test_limit():\n    s = _svc()\n    s.catalog.add("a", 3)\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "lent"\n    assert s.borrow("ann", "a") == "refused"\n\n\ndef test_hold_gets_returned_copy():\n    s = _svc()\n    s.members.join("bob")\n    assert s.borrow("ann", "dune") == "lent"\n    assert s.hold("bob", "dune") == "held"\n    assert s.give_back("ann", "dune") == "returned"\n    assert ("bob", "dune") in s.loans and s.catalog.free("dune") == 0\n', 'tests/test_reports.py': 'from shelf.loans import LoanService\nfrom shelf.reports import overdue\n\n\ndef test_overdue_lists_late_members():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    s.borrow("ann", "dune")\n    assert overdue(s, {"ann"}) == [("ann", "dune")]\n'}
target__SHELF_TEMPLATE: list[Path] = []

def target__shelf_template() -> Path:
    """Build the committed and confirmed shelf baseline once per test process; tests get copies."""
    if not target__SHELF_TEMPLATE:
        import atexit
        import tempfile
        holder = tempfile.TemporaryDirectory(prefix='flowguard-shelf-template-')
        atexit.register(holder.cleanup)
        root = Path(holder.name) / 'project'
        root.mkdir()
        for relative, text in target_SHELF_BASE.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode('utf-8'))
        git = ['git', '-c', 'core.autocrlf=false', '-c', 'user.name=FlowGuard tests', '-c', 'user.email=flowguard-tests@example.invalid']
        for arguments in (('init', '-q'), ('add', '.'), ('commit', '-qm', 'shelf baseline')):
            subprocess.run([*git, *arguments], cwd=root, check=True, capture_output=True)
        with redirect_stdout(io.StringIO()):
            assert target_cli.main(['map', 'confirm', 'all', '--root', str(root)]) == 0
        target__SHELF_TEMPLATE.append(root)
    return target__SHELF_TEMPLATE[0]

def target_shelf_project(tmp_path: Path) -> Path:
    """The original shelf baseline, committed, with its current map confirmed (a copy of one template)."""
    import shutil
    root = tmp_path / 'project'
    shutil.copytree(target__shelf_template(), root)
    return root

def target__run(root: Path, capsys, *arguments: str):
    code = target_cli.main([*arguments, '--root', str(root)])
    output = capsys.readouterr()
    return (code, output.out, output.err)

def target__load_map(root: Path) -> dict:
    return json.loads((root / '.flowguard/map.json').read_text(encoding='utf-8'))

def target__write_map(root: Path, data: dict) -> None:
    (root / '.flowguard/map.json').write_text(json.dumps(data, indent=2), encoding='utf-8')

def target__install_shelf_target(root: Path, *, reports: bool=False) -> Path:
    directory = root / '.flowguard/target'
    (directory / 'models').mkdir(parents=True)
    (directory / 'map.json').write_text(target_SHELF_TARGET['map_reports.json' if reports else 'map.json'], encoding='utf-8')
    if not reports:
        (directory / 'models/lending.py').write_text(target_SHELF_TARGET['models/lending.py'], encoding='utf-8')
    else:
        source = target_SHELF_BASE['.flowguard/models/lending.py']
        old = 'return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit())}'
        assert source.count(old) == 1
        (directory / 'models/lending.py').write_text(source.replace(old, old[:-1] + ', "lend_always_again": _explorer(LendAlways())}'), encoding='utf-8')
    return directory

def target__project_snapshot(root: Path) -> tuple[dict, set]:
    """Observe the actual check's no-write promise, including newly created caches."""
    files = {}
    directories = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            files[relative] = (path.read_bytes(), path.stat().st_mtime_ns)
        elif path.is_dir():
            directories.add(relative)
    return (files, directories)

def target__check_without_writes(root: Path, capsys):
    before = target__project_snapshot(root)
    result = target__run(root, capsys, 'target', 'check')
    assert target__project_snapshot(root) == before
    return result

def target__run_models_with_results(root, capsys, *arguments):
    from unittest.mock import patch
    from flowguard.map import cli as map_cli
    original, captured = (map_cli.run_models, [])

    def capture(*args, **kwargs):
        results = original(*args, **kwargs)
        captured.extend(results)
        return results
    with patch.object(map_cli, 'run_models', side_effect=capture):
        code, output, errors = target__run(root, capsys, 'map', 'models', *arguments)
    return (code, output, errors, captured)

def target__assert_current_lending(root: Path, capsys) -> None:
    code, output, errors = target__run(root, capsys, 'map', 'check')
    assert code == 0 and '0 error(s)' in output and (not errors), (output, errors)
    code, output, errors, results = target__run_models_with_results(root, capsys, 'lending')
    assert code == 0 and any((line.split()[:2] == ['PASS', 'lending'] for line in output.splitlines())) and (not errors), (output, errors)
    assert {'never_over_lent', 'limit_respected'} <= set(results[0].rules)
    assert 'no_idle_copy_while_held' not in results[0].rules
    assert 'rules:' not in output

def target__namespace_project(tmp_path: Path) -> Path:
    """Two real contracts share a helper and a parent port, without TESTED_BY duplication."""
    root = target_shelf_project(tmp_path)
    (root / 'namespace_subject.py').write_text('def advance(value):\n    return min(1, value + 1)\n', encoding='utf-8')
    (root / 'namespace-marker.txt').write_text('actual project root\n', encoding='utf-8')
    data = target__load_map(root)
    data['components'].append({'id': 'namespace-subject', 'layer': 'records', 'summary': 'Advance a bounded counter.', 'responsibilities': ['advance the namespace fixture counter'], 'files': ['namespace_subject.py', 'namespace-marker.txt'], 'entrypoints': ['namespace_subject.py:advance'], 'state': [], 'side_effects': [], 'depends_on': [], 'tests': [], 'models': [], 'status': 'draft'})
    target__write_map(root, data)
    common = 'from pathlib import Path\nfrom flowguard import FunctionResult, Invariant, InvariantResult, Workflow\nfrom flowguard.explorer import Explorer\nfrom flowguard.map.facts import CodeFactsReport, Fact\nfrom _view_setting import VALUE\nIMPLEMENTED_BY = {"Step": "namespace_subject.py:advance"}\nTESTED_BY = {}\n\nclass Step:\n    name = "Step"\n    accepted_input_type = int\n    def apply(self, inp, state):\n        return [FunctionResult("stepped", min(1, state + inp))]\n\nclass Bad(Step):\n    def apply(self, inp, state):\n        return [FunctionResult("stepped", 2)]\n\ndef _bounded(state, trace):\n    return InvariantResult.pass_() if state in (0, 1) else InvariantResult.fail("counter escaped")\n\nINVARIANTS = (Invariant(f"one_step_{VALUE}", "counter remains bounded", _bounded),)\n\ndef _explorer(block, starts=(0,)):\n    return Explorer(workflow=Workflow((block,)), initial_states=starts, external_inputs=(1,),\n                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)\n\ndef broken_variants():\n    return {"escaped": _explorer(Bad())}\n\ndef conformance():\n    from namespace_subject import advance\n    project = Path(__file__).resolve().parents[2]\n    return CodeFactsReport((Fact("real bounded advance", advance(0) == 1 and advance(1) == 1),\n        Fact("canonical project filename", (project / "namespace-marker.txt").read_text() == "actual project root\\n")))\n'
    parent = common + '\nMODEL_ID = "ns_parent"\nPARENT = "namespace-subject"\nimport ns_child\n\ndef build_explorer():\n    return _explorer(ns_child.Step())\n'
    child = common + '\nMODEL_ID = "ns_child"\nPARENT = "ns_parent"\n\ndef project_parent_state(state):\n    return state\n\ndef build_explorer():\n    from flowguard.kit import reachable_states\n    return _explorer(Step(), reachable_states(ns_parent.build_explorer(), project_parent_state))\n\nimport ns_parent\n'
    models = root / '.flowguard/models'
    (models / '_view_setting.py').write_text('VALUE = 1\n', encoding='utf-8')
    (models / 'ns_parent.py').write_text(parent, encoding='utf-8')
    (models / 'ns_child.py').write_text(child, encoding='utf-8')
    directory = root / '.flowguard/target'
    (directory / 'models').mkdir(parents=True)
    (directory / 'map.json').write_text(json.dumps({'schema': 'flowguard.target.v1', 'goal': 'replace the child and shared helper', 'components': [], 'flows': [], 'remove': []}), encoding='utf-8')
    (directory / 'models/_view_setting.py').write_text('VALUE = 2\n', encoding='utf-8')
    target_child = child.replace('Fact("canonical project filename",', 'Fact("loader selects target bytes", "# target child" in __loader__.get_source(__name__)),\n        Fact("canonical project filename",')
    (directory / 'models/ns_child.py').write_text(target_child + '\n# target child\n', encoding='utf-8')
    return root

def target__rename_return_toward_target(root: Path) -> None:
    directory = target__install_shelf_target(root)
    for path in (directory / 'map.json', directory / 'models/lending.py'):
        source = path.read_text(encoding='utf-8')
        assert 'shelf/loans.py:LoanService.give_back' in source
        path.write_text(source.replace('shelf/loans.py:LoanService.give_back', 'shelf/loans.py:LoanService.return_book'), encoding='utf-8')
    code = root / 'shelf/loans.py'
    source = code.read_text(encoding='utf-8')
    assert source.count('def give_back(') == 1
    code.write_text(source.replace('def give_back(', 'def return_book('), encoding='utf-8')

def target__static_target_read(root: Path, capsys, monkeypatch, *arguments: str):
    from flowguard.map import check, lint, proof, target
    from flowguard.map import cli as map_cli

    def forbidden(*args, **kwargs):
        pytest.fail('read must use static source facts, not import models or run a checker')
    with monkeypatch.context() as scoped:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            scoped.setattr(proof, name, forbidden)
        scoped.setattr(check, 'run_check', forbidden)
        scoped.setattr(map_cli, 'run_check', forbidden)
        scoped.setattr(lint, 'run_lint', forbidden)
        scoped.setattr(target, 'check_target', forbidden)
        scoped.setattr(map_cli, 'check_target', forbidden)
        return target__run(root, capsys, *arguments)

def target__promote_with_real_check(root: Path, capsys, monkeypatch):
    from flowguard.map import target
    original_check = target.check_target
    modes = []

    def observe_check(*args, **kwargs):
        modes.append(kwargs.get('models', True))
        return original_check(*args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(target, 'check_target', observe_check)
        result = target__run(root, capsys, 'target', 'promote')
    assert modes == [True], modes
    return result

def target__target_life_cycle_fixture_helpers():
    """Load only filesystem builders through the canonical current/target view."""
    from pathlib import Path
    import runpy
    from flowguard.map.mapfile import load_map, resolve_model_path
    from flowguard.map.targetfile import ModelView, build_target_view, load_target
    repository = Path(__file__).resolve().parents[1]
    active = load_target(repository)
    sources = {p.relative_to(repository).as_posix(): p.relative_to(repository).as_posix() for p in (repository / '.flowguard/models').glob('*.py')}
    helper_view = build_target_view(repository, load_map(repository), active) if active is not None else ModelView(repository, load_map(repository), sources, {Path(p).stem for p in sources})
    helper_path = resolve_model_path(repository, '.flowguard/models/target_life_cycle.py', view=helper_view)
    assert helper_path is not None
    from flowguard.map.proof import model_namespace
    with model_namespace(helper_view):
        return runpy.run_path(str(helper_path))

def target__target_with(root, capsys, goal, *nodes):
    for arguments in (('target', 'start', goal), *(('target', 'add', node) for node in nodes)):
        code, output, errors = target__run(root, capsys, *arguments)
        assert code == 0 and (not errors), (output, errors)
    return root / '.flowguard/target/map.json'
target_OLD_CHILD_MODEL = 'from flowguard import FunctionResult, Invariant, InvariantResult, Workflow\nfrom flowguard.explorer import Explorer\nfrom flowguard.map.facts import CodeFactsReport, Fact\nMODEL_ID = "loan_count"\nPARENT = "lending"\nIMPLEMENTED_BY = {"Count": "shelf/loans.py:LoanService.count"}\nclass Count:\n    name = "Count"\n    def __init__(self, value=0): self.value = value\n    def apply(self, event, state):\n        return (FunctionResult(self.value, self.value, label="counted"),)\nZERO = Invariant("starts_at_zero", "a fresh service counts no loans", lambda s, t:\n    InvariantResult.pass_() if s == 0 else InvariantResult.fail("not zero"))\nSANE = Invariant("never_negative", "a count is never negative", lambda s, t:\n    InvariantResult.pass_() if s >= 0 else InvariantResult.fail("negative"))\ndef make(value):\n    return Explorer(Workflow((Count(value),)), (0,), ("count",), invariants=(ZERO, SANE),\n                    max_sequence_length=1, progress_steps=0)\ndef build_explorer(): return make(0)\ndef broken_variants(): return {"counts_one": make(1)}\ndef conformance():\n    from shelf.loans import LoanService\n    actual = LoanService().count("ann")\n    return CodeFactsReport((Fact("fresh_count_is_zero", actual == 0, repr(actual)),))\n'

def target__fg403_helpers():
    import runpy
    directory = Path(__file__).resolve().parents[1] / '.flowguard/models'
    if not (directory / '_gap_cases.py').is_file():
        directory = directory.parent / 'target/models'
    return runpy.run_path(str(directory / '_gap_cases.py'))

def target__fg403_clean_target(tmp_path):
    from flowguard.map import target as native
    helpers = target__fg403_helpers()
    helpers['make_project'](tmp_path, helpers['regular_source']())
    native.start_target(tmp_path, 'record a positive native answer')
    native.add_to_target(tmp_path, 'one')
    (tmp_path / '.flowguard/target/models/one.py').write_text(helpers['regular_source'](positive=True))
    return native

def target__fg403_add_case(tmp_path, case):
    from flowguard.map import target as native
    from flowguard.map.common import content_digest, normalize_newlines
    helpers = target__fg403_helpers()
    helpers['make_project'](tmp_path, helpers['regular_source']())
    path = tmp_path / '.flowguard/models/one.py'
    before = path.read_bytes()
    if case != 'no_git':

        def git(*args):
            return subprocess.run(['git', '-c', 'user.name=Guard', '-c', 'user.email=guard@example.invalid', *args], cwd=tmp_path, check=True, capture_output=True)
        git('init', '-q')
        git('add', 'native.py', '.flowguard/map.json')
        if case != 'untracked':
            git('add', '.flowguard/models')
        git('commit', '-qm', 'baseline')
    data = target__load_map(tmp_path)
    data['model_digests'] = {'.flowguard/models/one.py': content_digest(path)}
    if case in {'dirty', 'promoted'}:
        path.write_bytes(before + b'\n# changed model\n')
    edited = path.read_bytes()
    if case == 'promoted':
        data['model_digests']['.flowguard/models/one.py'] = content_digest(path)
    target__write_map(tmp_path, data)
    native.start_target(tmp_path, 'edit the model safely')
    native.add_to_target(tmp_path, 'one')
    assert normalize_newlines(path.read_bytes()) == normalize_newlines(before if case == 'dirty' else edited)
    assert normalize_newlines((tmp_path / '.flowguard/target/models/one.py').read_bytes()) == normalize_newlines(edited)
import json
from pathlib import Path
from flowguard.map.inventory import Inventory, PyInfo
from flowguard.map.views import file_outline, find_owners, render_show

def view__inventory(root):
    return Inventory(root, [], [], [], {}, {}, {})

def view__component(name, *, responsibilities=(), summary=''):
    return dict(id=name, summary=summary, responsibilities=list(responsibilities), files=[], status='draft', fingerprint='', layer='', depends_on=[])

def view__fg232_view_project(tmp_path):
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    marker = tmp_path / 'fg232-read-imported-code.txt'
    guarded = f'from pathlib import Path\nPath({str(marker)!r}).write_text("imported")\n'
    sources = {'view232_members.py': guarded + 'class Members:\n    def may_borrow(self): return True\n', 'view232_catalog.py': guarded + 'class Catalog:\n' + ''.join((f'    def {name}(self): return True\n' for name in ('take', 'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta'))), 'view232_utils.py': guarded + 'LABEL = "module only"\n', 'view232_loans.py': guarded + 'from view232_members import Members\nimport view232_catalog as stock\nimport view232_utils\nclass LoanService:\n    def __init__(self, catalog=None):\n        self.members = Members()\n        self.catalog = catalog or stock.Catalog()\n    def borrow(self):\n        self.members.may_borrow()\n        return self.catalog.take()\n    def inventory(self):\n        self.catalog.alpha()\n        self.catalog.beta()\n        self.catalog.gamma()\n        self.catalog.delta()\n        self.catalog.epsilon()\n        self.catalog.zeta()\n        self.catalog.eta()\n        return self.catalog.alpha()\n', 'view232_subject.py': guarded + 'def by_model(): return True\ndef by_scope(): return True\ndef by_test(): return True\ndef unexplained(): return True\nclass Ledger:\n    def __init__(self): self.total = 0\n    def record(self): self.total += 1\n    def purge(self): self.total -= 1\n', 'tests/test_subject.py': guarded + 'from view232_subject import by_test\ndef test_by_test(): assert by_test() is True\n', '.flowguard/models/borrow_contract.py': guarded + 'MODEL_ID = "borrow_contract"\nCOMPONENTS = ["loans"]\nIMPLEMENTED_BY = {"Borrow": "view232_loans.py:LoanService.borrow"}\nNOT_MODELED = {"view232_subject.py:by_scope": "Separate integration check"}\ndef build_explorer(): raise AssertionError("read explored a user model")\ndef conformance(): raise AssertionError("read replayed user code")\n', '.flowguard/models/subject_contract.py': guarded + 'MODEL_ID = "subject_contract"\nCOMPONENTS = ["subject"]\nIMPLEMENTED_BY = {"ByModel": "view232_subject.py:by_model", "Record": "view232_subject.py:Ledger.record"}\ndef build_explorer(): raise AssertionError("read explored a user model")\ndef conformance(): raise AssertionError("read replayed user code")\n'}
    for relative, source in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    data = dict(schema='flowguard.map.v1', project='FG232 read fixture', layers=[], components=[dict(view__component('loans', summary='Borrow items', responsibilities=['coordinate borrowing']), files=['view232_loans.py'], tests=[], models=['.flowguard/models/borrow_contract.py'], entrypoints=['view232_loans.py:LoanService.borrow'], depends_on=['catalog', 'members', 'utils']), dict(view__component('catalog', summary='Store items', responsibilities=['store catalog']), files=['view232_catalog.py'], tests=[], models=[]), dict(view__component('members', summary='Check members', responsibilities=['allow members']), files=['view232_members.py'], tests=[], models=[]), dict(view__component('utils', summary='Labels', responsibilities=['label items']), files=['view232_utils.py'], tests=[], models=[]), dict(view__component('subject', summary='Coverage examples', responsibilities=['process examples']), files=['view232_subject.py'], tests=['tests/test_subject.py'], models=['.flowguard/models/subject_contract.py'], entrypoints=[f'view232_subject.py:{name}' for name in ('by_model', 'by_scope', 'by_test', 'unexplained')])], flows=[dict(id='borrow', summary='Borrow an item', steps=['loans:LoanService.borrow', 'members:Members.may_borrow', 'catalog:Catalog.take'], model='.flowguard/models/borrow_contract.py'), dict(id='audit', summary='Audit catalog', steps=['loans:LoanService.inventory', 'catalog:Catalog.alpha'])], accepted_debts=[])
    (tmp_path / '.flowguard/map.json').write_text(json.dumps(data), encoding='utf-8')
    return (data, build_inventory(tmp_path, DEFAULT_IGNORE), marker)

def view__fg232_count_discovery(monkeypatch):
    from flowguard.map import views
    calls = []
    original = views.discover_inventory

    def _fg232_counted_discovery(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(views, 'discover_inventory', _fg232_counted_discovery)
    return calls

def view__fg233_nested_project(tmp_path):
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    data, _inv, marker = view__fg232_view_project(tmp_path)
    data['layers'] = ['records']
    for component in data['components']:
        component['layer'] = 'records'
        if component['id'] in {'catalog', 'loans'}:
            component['parent'] = 'records'
        if component['id'] == 'loans':
            component['tests'] = ['tests/test_parent233_loans.py']
    parent = dict(view__component('records', summary='Inventory subsystem', responsibilities=['group inventory']), layer='records', tests=[], models=[])
    data['components'].insert(0, parent)
    path = tmp_path / 'tests/test_parent233_loans.py'
    path.write_text('from view232_loans import LoanService\ndef test_borrow(): assert LoanService().borrow() is True\n', encoding='utf-8')
    (tmp_path / '.flowguard/map.json').write_text(json.dumps(data), encoding='utf-8')
    return (data, build_inventory(tmp_path, DEFAULT_IGNORE), marker)
view__PROBE_HEAD = '"""Probe."""\nfrom flowguard.core import Invariant\nfrom flowguard.explorer import Explorer\nfrom flowguard.workflow import Workflow\n'

def view__static_project(tmp_path, models):
    """One component `app` anchored by the given models; read never imports them."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    for relative, source in {'app.py': 'def run(): return True\n', 'tests/test_app.py': 'def test_run(): pass\n', **models}.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    data = dict(project='static', layers=[], flows=[], components=[dict(view__component('app', summary='Serve app', responsibilities=['serve']), files=['app.py'], tests=['tests/test_app.py'])])
    return (data, build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False))

def view__runtime_names(tmp_path):
    """Import the fixture models (only in the test) for their real names."""
    import importlib.util
    import sys
    models = tmp_path / '.flowguard/models'
    before, found = (set(sys.modules), {})
    sys.path.insert(0, str(models))
    try:
        for path in sorted(models.glob('[!_]*.py')):
            spec = importlib.util.spec_from_file_location(f'_static_truth_{path.stem}', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            found[module.MODEL_ID] = ({rule.name: rule.description for rule in module.build_explorer().invariants}, sorted(module.broken_variants()))
    finally:
        sys.path.remove(str(models))
        for name in set(sys.modules) - before:
            sys.modules.pop(name, None)
    return found

def view__assert_static_equals_runtime(tmp_path, data, inv):
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    detail = render_show(tmp_path, data, inv, component='app', detail=False, budget=8000)
    lines = detail.splitlines()
    for mid, (rules, bads) in view__runtime_names(tmp_path).items():
        row = next((line for line in overview.splitlines() if line.strip().startswith(f'model {mid}: ')))
        assert f'({len(rules)} rules, {len(bads)} known-bad,' in row, row
        at = next((index for index, line in enumerate(lines) if line.strip().startswith(f'model {mid}: ')))
        facets = {line.strip().partition(': ')[0]: line.strip().partition(': ')[2] for line in lines[at + 1:at + 6]}
        assert facets['rules'] == '; '.join((f'{name}: {text}' for name, text in sorted(rules.items())))
        assert facets['known-bad'] == ', '.join(bads)
view__HELPER_SPLIT_MODELS = {'.flowguard/models/_probe_common.py': view__PROBE_HEAD + 'def _ok(state, trace): return True\nA = Invariant("a_rule", "a holds", _ok)\nB = Invariant("b_rule", "b holds", _ok)\nBOTH = (A, B)\n', '.flowguard/models/probe_child.py': view__PROBE_HEAD + 'from _probe_common import A, B\nMODEL_ID = "probe_child"\nPARENT = "probe_parent"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\nTESTED_BY = {"a_rule": ["tests/test_app.py:test_run"]}\ndef _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=(A, B))\ndef build_explorer(): return _explorer()\ndef broken_variants(): return {"child_bad": _explorer()}\n', '.flowguard/models/probe_parent.py': view__PROBE_HEAD + 'from _probe_common import BOTH\nMODEL_ID = "probe_parent"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\ndef _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=BOTH)\ndef build_explorer(): return _explorer()\ndef broken_variants(): return {"parent_bad": _explorer()}\n', '.flowguard/models/probe_wrapper.py': view__PROBE_HEAD + 'MODEL_ID = "probe_wrapper"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\ndef _rule(name, text):\n    return Invariant(name, text, lambda state, trace: True)\nRULES = (_rule("x_rule", "x holds"), _rule("y_rule", "y holds"))\ndef _explorer(kind=""):\n    return Explorer(Workflow(()), (0,), (), invariants=RULES)\ndef build_explorer(): return _explorer()\ndef broken_variants():\n    return {name: _explorer(name) for name in ("x_bad", "y_bad")}\n'}

def view__assert_kit_matches_runtime(tmp_path, detail):
    lines = detail.splitlines()
    for mid, (rules, bads) in view__runtime_names(tmp_path).items():
        at = next((index for index, line in enumerate(lines) if line.strip().startswith(f'model {mid}: ')))
        facets = {line.strip().partition(': ')[0]: line.strip().partition(': ')[2] for line in lines[at + 1:at + 6]}
        shown = [item for item in facets['rules'].split('; ') if not item.startswith('cases: ')]
        assert shown == [f'{name}: {text}' for name, text in sorted(rules.items())]
        assert facets['known-bad'] == ', '.join(bads)

def view__coverage_project(tmp_path):
    """Four entrypoints: model-anchored, named by a test, NOT_MODELED, and unexplained."""
    write = lambda relative, text: (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True) or (tmp_path / relative).write_text(text, encoding='utf-8')
    write('app.py', 'def run(): return True\ndef tested(): return True\ndef skipped(): return True\ndef loose(): return True\n')
    write('tests/test_app.py', 'from app import run, tested\n\ndef test_tested_function():\n    assert tested()\n\ndef test_unbound_run():\n    assert run()\n')
    write('.flowguard/models/app_model.py', '"""Protect the app."""\nMODEL_ID = "app_model"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\nNOT_MODELED = {"app.py:skipped": "a deliberate no-op kept for the command line"}\nTESTED_BY = {}\nRULES = (Invariant("works", "works", None),)\ndef build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)\ndef broken_variants(): return {"bad": None}\n')
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    data = dict(project='coverage', layers=[], flows=[], components=[dict(view__component('app', summary='Serve app', responsibilities=['serve']), files=['app.py'], tests=['tests/test_app.py'], entrypoints=['app.py:run', 'app.py:tested', 'app.py:skipped', 'app.py:loose'])])
    return (data, build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False))

def view__review_project(tmp_path, *, clean=False):
    """A cycle (ERROR), a hub (used by 3, uses 3, 7 duties), an unexplained writer, a flow with no model."""
    files = {'hub.py': 'import lib1\nimport lib2\nimport lib3\ndef run(): return lib1.run() and lib2.run() and lib3.run()\n', 'lib1.py': 'class Box:\n    def put(self, value):\n        self.value = value\ndef run(): return Box()\n', 'lib2.py': 'def run(): return True\n', 'lib3.py': 'def run(): return True\n', 'u1.py': 'import hub\ndef run(): return hub.run()\n', 'u2.py': 'import hub\ndef run(): return hub.run()\n', 'u3.py': 'import hub\ndef run(): return hub.run()\n', 'app.py': 'import store\ndef run(): return store.save()\n', 'store.py': 'import app\ndef save(): return True\n', '.flowguard/models/probe.py': 'from pathlib import Path\nPath(__file__).parents[2].joinpath("model_import.marker").write_text("imported")\nMODEL_ID = "probe"\nCOMPONENTS = ["lib2"]\nIMPLEMENTED_BY = {"Run": "lib2.py:run"}\ndef build_explorer(): pass\ndef broken_variants(): return {"bad": None}\n'}
    if clean:
        files = {'app.py': 'import store\ndef run(): return store.save()\n', 'store.py': 'def save(): return True\n', 'tests/test_app.py': 'from app import run\ndef test_run(): assert run()\n'}
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    if clean:
        components = [dict(view__component('app', summary='Serve app'), files=['app.py'], depends_on=['store'], tests=['tests/test_app.py'], layer='entry'), dict(view__component('store', summary='Store'), files=['store.py'], tests=['tests/test_app.py'], layer='domain')]
        return dict(project='clean', layers=['entry', 'domain'], components=components)
    duties = [f'serve hub duty {word}' for word in ('one', 'two', 'three', 'four', 'five', 'six', 'seven')]
    components = [dict(view__component(cid), files=[cid + '.py']) for cid in ('app', 'store', 'hub', 'lib1', 'lib2', 'lib3', 'u1', 'u2', 'u3')]
    by_id = {c['id']: c for c in components}
    by_id['app']['depends_on'], by_id['store']['depends_on'] = (['store'], ['app'])
    by_id['hub']['depends_on'], by_id['hub']['responsibilities'] = (['lib1', 'lib2', 'lib3'], duties)
    for cid in ('u1', 'u2', 'u3'):
        by_id[cid]['depends_on'] = ['hub']
    return dict(project='demo', components=components, flows=[dict(id='trip', steps=['u1:run', 'hub:run'])])

def view__quiet_fixture(name):
    import runpy
    directory = Path(__file__).parents[1] / '.flowguard/models'
    path = directory / (name + '.py')
    if not path.exists():
        path = directory.parent / 'target/models' / path.name
    import sys
    sys.path.insert(0, str(path.parent))
    try:
        return runpy.run_path(str(path))
    finally:
        sys.path.remove(str(path.parent))

def view_locate_fixture():
    import runpy
    directory = Path(__file__).parents[1] / '.flowguard'
    target = directory / 'target/models/_locate_fixture.py'
    return runpy.run_path(str(target if target.exists() else directory / 'models/_locate_fixture.py'))

def view__field_project(tmp_path):
    import runpy
    base = Path(__file__).resolve().parents[1] / '.flowguard'
    path = base / 'target/models/_relation_fixture.py'
    if not path.exists():
        path = base / 'models/_relation_fixture.py'
    data = runpy.run_path(str(path))['field_fixture'](tmp_path)
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    return (data, build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False))
