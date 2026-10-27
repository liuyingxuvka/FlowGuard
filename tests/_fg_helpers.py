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
target_SHELF_BASE: dict[str,str] = {**{}, **{relative:(Path(__file__).parents[1]/"examples/shelf"/''/relative).read_text(encoding="utf-8") for relative in ('shelf/members.py', 'shelf/__init__.py', 'shelf/cli.py', 'shelf/loans.py', 'shelf/catalog.py', 'tests/test_catalog.py', 'tests/test_loans.py', 'tests/test_cli.py', '.flowguard/map.json', '.flowguard/models/desk.py', '.flowguard/models/lending.py')}}
target_SHELF_TARGET: dict[str,str] = {**{'map_reports.json': '{\n  "schema": "flowguard.target.v1",\n  "goal": "reports: list overdue loans",\n  "components": [\n    {\n      "id": "reports",\n      "layer": "lending",\n      "summary": "Lists overdue loans.",\n      "responsibilities": [\n        "list overdue loans"\n      ],\n      "files": [\n        "shelf/reports.py"\n      ],\n      "entrypoints": [\n        "shelf/reports.py:overdue"\n      ],\n      "state": [],\n      "side_effects": [],\n      "depends_on": [\n        "loans"\n      ],\n      "tests": [\n        "tests/test_reports.py"\n      ],\n      "models": []\n    }\n  ],\n  "flows": [],\n  "remove": []\n}\n'}, **{relative:(Path(__file__).parents[1]/"examples/shelf"/'target/'/relative).read_text(encoding="utf-8") for relative in ('map.json', 'models/lending.py')}}
target_SHELF_AFTER: dict[str,str] = {**{'shelf/reports.py': '"""Reports over current loans."""\n\nfrom shelf.loans import LoanService\n\n\ndef overdue(service: LoanService, members_late):\n    return [(member, book) for member, book in service.loans if member in members_late]\n', 'tests/test_reports.py': 'from shelf.loans import LoanService\nfrom shelf.reports import overdue\n\n\ndef test_overdue_lists_late_members():\n    s = LoanService()\n    s.members.join("ann")\n    s.catalog.add("dune", 1)\n    s.borrow("ann", "dune")\n    assert overdue(s, {"ann"}) == [("ann", "dune")]\n'}, **{relative:(Path(__file__).parents[1]/"examples/shelf"/'after/'/relative).read_text(encoding="utf-8") for relative in ('shelf/loans.py', 'tests/test_loans.py')}}
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
        git = ['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0', '-c', 'core.autocrlf=false', '-c', 'user.name=FlowGuard tests', '-c', 'user.email=flowguard-tests@example.invalid']
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

def target__target_life_cycle_fixture_helpers(name="target_life_cycle"):
    """Load only filesystem builders through the canonical current/target view."""
    from pathlib import Path
    import runpy
    from flowguard.map.mapfile import load_map, resolve_model_path
    from flowguard.map.targetfile import ModelView, build_target_view, load_target
    repository = Path(__file__).resolve().parents[1]
    active = load_target(repository)
    sources = {p.relative_to(repository).as_posix(): p.relative_to(repository).as_posix() for p in (repository / '.flowguard/models').glob('*.py')}
    helper_view = build_target_view(repository, load_map(repository), active) if active is not None else ModelView(repository, load_map(repository), sources, {Path(p).stem for p in sources})
    helper_path = resolve_model_path(repository, '.flowguard/models/'+name+'.py', view=helper_view)
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


import json as flowguard_map_contracts421_json
import subprocess as flowguard_map_contracts421_subprocess
from pathlib import Path as flowguard_map_contracts421_Path
import pytest as flowguard_map_contracts421_pytest
from flowguard.__main__ import main as flowguard_map_contracts421_main
from flowguard.map.cli import _context as flowguard_map_contracts421__context
from flowguard.map.check import run_check as flowguard_map_contracts421_run_check
from flowguard.map.lint import run_lint as flowguard_map_contracts421_run_lint

def flowguard_map_contracts421_write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def flowguard_map_contracts421_project(tmp_path):
    flowguard_map_contracts421_write(tmp_path, 'app.py', 'def run():\n    return True\n')
    flowguard_map_contracts421_write(tmp_path, 'tests/test_app.py', 'from app import run\n\ndef test_run():\n    assert run() is True\n')
    data = {'schema': 'flowguard.map.v1', 'components': [{'id': 'app', 'summary': 'Runs the application', 'responsibilities': ['run the app'], 'files': ['app.py'], 'entrypoints': ['app.py:run'], 'tests': ['tests/test_app.py'], 'models': [], 'depends_on': [], 'status': 'draft'}]}
    flowguard_map_contracts421_save(tmp_path, data)
    return data

def flowguard_map_contracts421_save(root, data):
    flowguard_map_contracts421_write(root, '.flowguard/map.json', flowguard_map_contracts421_json.dumps(data))

def flowguard_map_contracts421_findings(root):
    data, inv = flowguard_map_contracts421__context(root)
    return flowguard_map_contracts421_run_check(root, data, inv)
flowguard_map_contracts421_CONTRACT = 'MODEL_ID = "one"\nCOMPONENTS = ["app"]\nIMPLEMENTED_BY = {"Run": "app.py:run"}\ndef build_explorer():\n    pass\n'

def flowguard_map_contracts421__placement_port_source(*, child=None):
    """Only the static port declarations needed by the placement fixtures."""
    fields = ('value', 'received') if child else ('value',)
    return '\nfrom dataclasses import dataclass\nfrom flowguard import Workflow,FunctionResult\nfrom flowguard.explorer import Explorer\n@dataclass(frozen=True)\nclass PortState:\n' + ''.join((f'    {name}: int = 0\n' for name in fields)) + 'class Step:\n    name="Step"\n' + f'    writes={fields!r}\n' + '    def apply(self,event,state): return (FunctionResult(1,state),)\n' + 'OUTPUTS={"value":(1,)}\nKEEPS=("value",)\n' + (f'HANDOFF={{{child!r}:{{"value":"received"}}}}\n' if child else '') + 'def build_explorer(): return Explorer(Workflow((Step(),)),(PortState(),),(1,))\n'

def flowguard_map_contracts421__fg233_parent_project(tmp_path):
    marker = tmp_path / 'parent233-imported-code.txt'
    guarded = f'from pathlib import Path\nPath({str(marker)!r}).write_text("imported")\n'
    flowguard_map_contracts421_write(tmp_path, 'parent233_loans.py', guarded + 'def borrow(): return True\n')
    flowguard_map_contracts421_write(tmp_path, 'parent233_catalog.py', guarded + 'def available(): return True\n')
    flowguard_map_contracts421_write(tmp_path, 'tests/test_parent233.py', guarded + 'from parent233_loans import borrow\ndef test_borrow(): assert borrow() is True\n')
    flowguard_map_contracts421_write(tmp_path, '.flowguard/models/parent233_rules.py', guarded + 'MODEL_ID="parent233_rules"\nPARENT="records"\nIMPLEMENTED_BY={"Borrow":"parent233_loans.py:borrow"}\ndef build_explorer(): raise AssertionError("static check explored a model")\ndef conformance(): raise AssertionError("static check replayed user code")\n')
    data = dict(schema='flowguard.map.v1', layers=['records', 'other'], components=[dict(id='records', layer='records', summary='Record subsystem', responsibilities=['group records'], files=[], tests=[], models=[], depends_on=[], status='draft'), dict(id='loans', parent='records', layer='records', summary='Borrow items', responsibilities=['borrow items'], files=['parent233_loans.py'], entrypoints=['parent233_loans.py:borrow'], tests=['tests/test_parent233.py'], models=[], depends_on=[], status='draft'), dict(id='catalog', parent='records', layer='records', summary='Available items', responsibilities=['count availability'], files=['parent233_catalog.py'], tests=[], models=[], depends_on=[], status='draft')], flows=[], accepted_debts=[])
    flowguard_map_contracts421_save(tmp_path, data)
    return (data, marker)

def flowguard_map_contracts421__scope_helpers():
    import runpy
    directory = flowguard_map_contracts421_Path(__file__).resolve().parents[1] / '.flowguard/models'
    pending = directory.parent / 'target/models/model_scope.py'
    if pending.is_file():
        directory = pending.parent
    return runpy.run_path(str(directory / 'model_scope.py'))
import json as flowguard_map_discover421_json
import shutil as flowguard_map_discover421_shutil
import subprocess as flowguard_map_discover421_subprocess
import sys as flowguard_map_discover421_sys
import tempfile as flowguard_map_discover421_tempfile
import unittest as flowguard_map_discover421_unittest
from pathlib import Path as flowguard_map_discover421_Path
import pytest as flowguard_map_discover421_pytest
from flowguard.map.discover import component_summary as flowguard_map_discover421_component_summary, console_scripts as flowguard_map_discover421_console_scripts, discover as flowguard_map_discover421_discover, discover_inventory as flowguard_map_discover421_discover_inventory, file_facts as flowguard_map_discover421_file_facts
from flowguard.map.common import DEFAULT_IGNORE as flowguard_map_discover421_DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory as flowguard_map_discover421_build_inventory
from flowguard.map.lint import entrypoint_coverage_findings as flowguard_map_discover421_entrypoint_coverage_findings, run_lint as flowguard_map_discover421_run_lint, scoped_architecture_findings as flowguard_map_discover421_scoped_architecture_findings
from flowguard.map.scan import guess_tests as flowguard_map_discover421_guess_tests, new_map as flowguard_map_discover421_new_map, propose_components as flowguard_map_discover421_propose_components
flowguard_map_discover421_ROOT = flowguard_map_discover421_Path(__file__).resolve().parents[1]
flowguard_map_discover421_APP = '\nimport requests\nfrom notes.store import NoteStore\n\nclass App:\n    def __init__(self):\n        self.routes = {}\n    def route(self, path, methods=None):\n        def wrap(fn):\n            self.routes[path] = fn\n            return fn\n        return wrap\n\napp = App()\nstore = NoteStore("notes.db")\n\n@app.route("/notes", methods=["POST"])\ndef create_note(body):\n    store.add(body)\n    requests.post("https://hooks.example/notes", json=body)\n\n@app.route("/notes")\ndef list_notes():\n    return store.all()\n\ndef tally(items):\n    requests = []\n    requests.append(len(items))\n    return requests\n'
flowguard_map_discover421_STORE = '\nimport sqlite3\n\nclass NoteStore:\n    def __init__(self, path):\n        self.conn = sqlite3.connect(path)\n        self.count = 0\n    def add(self, body):\n        cur = self.conn.cursor()\n        cur.execute("insert into notes values (?)", (body,))\n        self.count += 1\n    def all(self):\n        return self.conn.cursor().execute("select * from notes").fetchall()\n'
flowguard_map_discover421_CLI = '\nimport argparse\nimport shutil\n\ndef main(argv=None):\n    p = argparse.ArgumentParser()\n    sub = p.add_subparsers(dest="cmd")\n    sub.add_parser("backup")\n    if p.parse_args(argv).cmd == "backup":\n        shutil.copy("notes.db", "notes.bak")\n\n\n\nif __name__ == "__main__":\n    main()\n'

def flowguard_map_discover421_write_project(root: Path) -> None:
    (root / 'notes').mkdir()
    (root / 'tests').mkdir()
    (root / 'notes' / '__init__.py').write_text('', encoding='utf-8')
    (root / 'notes' / 'app.py').write_text(flowguard_map_discover421_APP, encoding='utf-8')
    (root / 'notes' / 'store.py').write_text(flowguard_map_discover421_STORE, encoding='utf-8')
    (root / 'notes' / 'cli.py').write_text(flowguard_map_discover421_CLI, encoding='utf-8')
    (root / 'tests' / 'test_store.py').write_text('def test_x():\n    assert True\n', encoding='utf-8')
    flowguard_map_discover421_subprocess.run(['git', 'init', '-q'], cwd=root, check=True)

def flowguard_map_discover421_map_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return flowguard_map_discover421_subprocess.run([flowguard_map_discover421_sys.executable, '-m', 'flowguard', 'map', '--root', str(root), *args], cwd=flowguard_map_discover421_ROOT, capture_output=True, text=True, check=False)
flowguard_map_discover421__INJECTED_STORE = 'import json\n\n\nclass NoteStore:\n    def __init__(self, path):\n        self.path = path\n        self.notes = {}\n\n    def save(self, note_id, text):\n        self.notes[note_id] = text\n        with open(self.path, "w") as handle:\n            json.dump(self.notes, handle)\n\n    def delete(self, note_id):\n        self.notes.pop(note_id, None)\n        with open(self.path, "w") as handle:\n            json.dump(self.notes, handle)\n'
flowguard_map_discover421__INJECTED_SERVICE = 'class NoteService:\n    def __init__(self, store):\n        self.store = store\n\n    def add(self, note_id, text):\n        self.store.save(note_id, text)\n\n    def delete(self, note_id):\n        self.store.delete(note_id)\n'
flowguard_map_discover421__INJECTED_CLI = 'from notes.service import NoteService\nfrom notes.store import NoteStore\n\n\ndef main():\n    service = NoteService(NoteStore("notes.json"))\n    service.add("a", "first note")\n'

def flowguard_map_discover421__injected_project(root: Path, *, service: str=flowguard_map_discover421__INJECTED_SERVICE, cli: str | None=flowguard_map_discover421__INJECTED_CLI) -> dict:
    """The constructor-injection shape: cli builds NoteService(NoteStore(...)); service never imports store."""
    files = {'notes/__init__.py': '', 'notes/store.py': flowguard_map_discover421__INJECTED_STORE, 'notes/service.py': service}
    if cli is not None:
        files['notes/cli.py'] = cli
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')

    def component(cid, path, layer, depends_on, entrypoints):
        return dict(id=cid, layer=layer, summary=f'{cid} notes', responsibilities=[f'{cid} notes'], files=[path], entrypoints=entrypoints, state=[], side_effects=[], depends_on=depends_on, tests=[], models=[], status='draft')
    components = [dict(component('store', 'notes/store.py', 'storage', [], []), files=['notes/store.py', 'notes/__init__.py']), component('service', 'notes/service.py', 'domain', ['store'], ['notes/service.py:NoteService.add'])]
    if cli is not None:
        components.append(component('cli', 'notes/cli.py', 'interface', ['service', 'store'], ['notes/cli.py:main']))
    data = {'schema': 'flowguard.map.v1', 'project': 'notes', 'layers': ['interface', 'domain', 'storage'], 'ignore': [], 'components': components, 'flows': [], 'accepted_debts': []}
    (root / '.flowguard').mkdir(exist_ok=True)
    (root / '.flowguard/map.json').write_text(flowguard_map_discover421_json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return data

def flowguard_map_discover421__resolution_case(tmp_path, files, caller, callee, *, import_roots=(), private=True):
    from flowguard.map.lint import private_use_findings
    for relative, source in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    source_path = caller.partition('#')[0]
    target_path = callee.partition('#')[0]
    groups = {'caller': [source_path]}
    others = sorted(set(files) - {source_path})
    if others:
        groups['helper'] = others
    data = {'schema': 'flowguard.map.v1', 'import_roots': list(import_roots), 'components': [{'id': name, 'summary': name, 'responsibilities': ['execute the ' + name], 'files': paths, 'tests': [], 'models': [], 'status': 'draft'} for name, paths in groups.items()]}
    inv = flowguard_map_discover421_build_inventory(tmp_path, [], write_cache=False, import_roots=import_roots)
    raw = flowguard_map_discover421_discover_inventory(tmp_path, inv, write_cache=False, data=data)
    assert callee in raw['edges'].get(caller, []), raw['edges']
    findings = private_use_findings(tmp_path, data, inv)
    assert bool(findings) == private, findings
    if private:
        assert any(('_private' in f.message and f.component == 'caller' for f in findings))
        assert target_path in inv.file_deps[source_path]
    return (data, inv, raw)

def flowguard_map_discover421_literal_fixture():
    import runpy
    directory = flowguard_map_discover421_Path(__file__).parents[1] / '.flowguard'
    target = directory / 'target/models/_literal_fixture.py'
    return runpy.run_path(str(target if target.exists() else directory / 'models/_literal_fixture.py'))
from dataclasses import fields as flowguard_port421_fields, is_dataclass as flowguard_port421_is_dataclass, replace as flowguard_port421_replace
from pathlib import Path as flowguard_port421_Path
import json as flowguard_port421_json
import runpy as flowguard_port421_runpy
from flowguard.map.common import DEFAULT_IGNORE as flowguard_port421_DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory as flowguard_port421_build_inventory
from flowguard.map.mapfile import load_map as flowguard_port421_load_map
from flowguard.map.port import model_port as flowguard_port421_model_port, port_findings as flowguard_port421_port_findings, upward as flowguard_port421_upward
from flowguard.map.tree import build_tree as flowguard_port421_build_tree

def flowguard_port421_helpers():
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    return target__target_life_cycle_fixture_helpers('_target_fixture')

def flowguard_port421_project(root, case='valid'):
    h = flowguard_port421_helpers()
    data = h['make_port_project'](root, case)
    return (data, flowguard_port421_build_inventory(root, flowguard_port421_DEFAULT_IGNORE, write_cache=False))

def flowguard_port421_probe(root, model='desk'):
    return flowguard_port421_helpers()['probe_port_model'](root, model)

def flowguard_port421_errors(root, data, inv):
    return {finding.code for finding in flowguard_port421_build_tree(root, data, inv).findings if finding.level == 'error'}

def flowguard_port421_rewrite(root, model, old, new):
    path = root / '.flowguard/models' / (model + '.py')
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new, 1))

def flowguard_port421_dispatch_project(root, kind='valid'):
    data, inv = flowguard_port421_project(root)
    models = root / '.flowguard/models'
    (models / 'desk.py').unlink()
    (models / 'lending.py').unlink()
    (root / 'shelf/loans.py').write_text('def borrow(value): return "left"\ndef second(value): return "right"\n')
    (root / 'shelf/cli.py').write_text('from .loans import borrow,second\ndef main(mode): return borrow(mode) if mode=="x" else second(mode)\n')
    head = 'from dataclasses import dataclass,replace\nfrom pathlib import Path\nfrom flowguard import FunctionResult,Invariant,Workflow\nfrom flowguard.explorer import Explorer\nfrom flowguard.map.facts import CodeFactsReport,Fact,load_anchor\n'
    cmd = head + 'MODEL_ID="cmd"\nPARENT="cli"\nIMPLEMENTED_BY={"Serve":"shelf/cli.py:main"}\nHANDOFF={"a":{"answer":"a"},"b":{"answer":"b"}}\nKEEPS=("mode",)\nDISPATCH={"mode":{"x":"a","y":"b"}}\n@dataclass(frozen=True)\nclass Command:\n    mode:str=""\n    a:str=""\n    b:str=""\nclass Choose:\n    name="Choose"\n    reads=()\n    writes=("mode","a","b")\n    def __init__(self,bad=False): self.bad=bad\n    def apply(self,event,state):\n        mode=event\n        a="left" if event=="x" else ""\n        b="right" if event=="y" else ""\n        if KIND=="unknown" and event=="x": mode="z"\n        if KIND in ("wrong_branch","no_dispatch"): a,b=b and "left",a and "right"\n        if KIND=="two_branches" and event=="x": a,b="left","right"\n        if self.bad: a,b="hidden","hidden"\n        result=Command(mode,a,b)\n        return (FunctionResult((a,b),result,label="selected"),)\nRULE=Invariant("visible","branch results stay visible",lambda s,t:s.a!="hidden" and s.b!="hidden")\ndef make(bad=False): return Explorer(Workflow((Choose(bad),)),(Command(),),("x","y"),invariants=(RULE,),max_sequence_length=1,progress_steps=0)\ndef build_explorer(): return make()\ndef broken_variants(): return {"hidden":make(True)}\ndef conformance():\n    main=load_anchor(IMPLEMENTED_BY["Serve"],root=Path.cwd())\n    return CodeFactsReport((Fact("x",main("x")=="left"),Fact("y",main("y")=="right")))\n'
    cmd += '\nKIND=' + repr(kind) + '\n'
    if kind == 'no_dispatch':
        cmd = cmd.replace('DISPATCH={"mode":{"x":"a","y":"b"}}', '')
    if kind == 'unknown_selector':
        cmd = cmd.replace('DISPATCH={"mode"', 'DISPATCH={"ghost"')
    (models / 'cmd.py').write_text(cmd)
    for name, symbol, value in (('a', 'borrow', 'left'), ('b', 'second', 'right')):
        source = head + f'MODEL_ID={name!r}\nPARENT="cmd"\nCOMPONENTS=["loans"]\nIMPLEMENTED_BY={{"Result":"shelf/loans.py:{symbol}"}}\nOUTPUTS={{"answer":({value!r},)}}\n@dataclass(frozen=True)\nclass ResultState:\n    answer:str=""\nclass Produce:\n    name="Produce"\n    writes=("answer",)\n    def __init__(self,bad=False): self.bad=bad\n    def apply(self,event,state): return (FunctionResult(event,ResultState("bad" if self.bad else event)),)\nRULE=Invariant("result","the result is retained",lambda s,t:s.answer in ("",{value!r}))\ndef make(bad=False): return Explorer(Workflow((Produce(bad),)),(ResultState(),),({value!r},),invariants=(RULE,),max_sequence_length=1,progress_steps=0)\ndef build_explorer(): return make()\ndef broken_variants(): return {{"bad":make(True)}}\ndef conformance(): return CodeFactsReport((Fact("native",load_anchor(IMPLEMENTED_BY["Result"],root=Path.cwd())("x")=={value!r}),))\n'
        if name == 'a' and kind == 'nonchild':
            source = source.replace('PARENT="cmd"', 'PARENT="loans"')
        (models / (name + '.py')).write_text(source)
    return (data, flowguard_port421_build_inventory(root, flowguard_port421_DEFAULT_IGNORE, write_cache=False))

def flowguard_port421_escalation_model():
    import sys
    root = flowguard_port421_Path(__file__).parents[1] / '.flowguard'
    current, target = (root / 'models', root / 'target/models')
    source = target / 'port_escalation.py' if (target / 'port_escalation.py').exists() else current / 'port_escalation.py'
    sys.path.insert(0, str(current))
    try:
        return flowguard_port421_runpy.run_path(str(source))
    finally:
        sys.path.pop(0)

def flowguard_port421__select_ports(tmp_path, mid, old, new):
    from flowguard.map.port import model_port, port_selection
    data, inv = flowguard_port421_project(tmp_path)
    tree = flowguard_port421_build_tree(tmp_path, data, inv)
    ports = {key: node.contract['port'] for key, node in tree.nodes.items()}
    ports[mid] = new
    return port_selection(mid, old, new, tree, ports)
import pytest as map_inventory421_pytest, os as map_inventory421_os, json as map_inventory421_json
from pathlib import Path as map_inventory421_Path
import pytest as map_views421_pytest, os as map_views421_os, json as map_views421_json
from pathlib import Path as map_views421_Path
