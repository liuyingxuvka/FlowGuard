"""`owners.Change` at the baseline: the writes and the calls the baseline code had, and the static assembly's hooks.

Each fixture commits its baseline, then edits one file, adds one and leaves the rest; the map is the working tree's.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, sources
from flowguard.intent.config import load_config
from flowguard.intent.health import Issue
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _git, _write

SCHEMA = 'model Item {\n  id    String @id\n  state String\n  note  String\n}\n'
SET_STATE = """
    export async function setState(prisma: any) {
      await prisma.item.update({ where: { id: '1' }, data: { state: 'A' } });
    }
    export function rename(item: any) { item.note = 'z'; }
"""
SET_NOTE = """
    export async function setNote(prisma: any) {
      await prisma.item.update({ where: { id: '1' }, data: { %s: 'x' } });
    }
"""
ORDER = """
    class Order:
        status: str
        reason: str

    def close(order: Order):
        order.%s = 'closed'
"""


def _writes(rows):
    return [(row['file'], row['function'], row['field']) for row in rows]


def _project(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': SET_STATE, 'app/b.ts': SET_NOTE % 'note',
                       'app/order.py': ORDER % 'status'})
    _write(tmp_path, {'app/b.ts': SET_NOTE % 'state', 'app/order.py': ORDER % 'reason', 'app/c.ts': """
        export async function addNote(prisma: any) {
          await prisma.item.update({ where: { id: '2' }, data: { note: 'y' } });
        }
    """})
    return tmp_path


def test_baseline_writes_keep_unchanged_files_and_read_changed_ones_at_the_baseline(tmp_path):
    root = _project(tmp_path)
    with closing(build(root)) as graph:
        change = owners.Change(load_config(root), graph, 'HEAD')
        assert change.files == {'app/b.ts', 'app/c.ts', 'app/order.py'}
        assert _writes(graph.writes('Item.state')) == [('app/a.ts', 'setState', 'state'), ('app/b.ts', 'setNote', 'state')]
        assert _writes(change.baseline_writes('Item.state')) == [('app/a.ts', 'setState', 'state')]
        # The changed file's baseline write, and none of the file this change adds.
        assert _writes(change.baseline_writes('Item.note')) == [('app/b.ts', 'setNote', 'note')]
        assert _writes(change.baseline_writes()) == [('app/a.ts', 'setState', 'state'), ('app/b.ts', 'setNote', 'note'),
                                                     ('app/order.py', 'close', 'status')]
        assert _writes(change.baseline_writes('Order')) == [('app/order.py', 'close', 'status')]
        assert _writes(graph.writes('Order')) == [('app/order.py', 'close', 'reason')]
        # A property assignment matched by its field name alone counts only with by_name, as in graph.writes.
        assert ('app/a.ts', 'rename', 'note') not in _writes(change.baseline_writes('note'))
        assert ('app/a.ts', 'rename', 'note') in _writes(change.baseline_writes('note', by_name=True))
        assert change.baseline_writes('Item.state') is change.baseline_writes('Item.state')
        # Without a baseline the baseline is the working tree.
        plain = owners.Change(load_config(root), graph, None)
        assert _writes(plain.baseline_writes('Item.state')) == _writes(graph.writes('Item.state'))


FLOW = """
    from app.lib import a, b, c
    print('start')
    %s

    def run(x):
        def inner(y):
            return %s(y)
        return inner(x) + b(x)

    def keep(x):
        return a(x)
"""
UI = """
    import { load, save, drop } from './lib';
    export function start(items: number[]) {
      return items.map((item) => %s(item));
    }
    export function stay() { return save(1); }
"""


def test_callees_read_the_calls_of_a_function_and_its_nested_functions_now_and_at_the_baseline(tmp_path):
    lib = 'def a(x):\n    return x\n\ndef b(x):\n    return x\n\ndef c(x):\n    return a(x)\n'
    _commit(tmp_path, {'app/__init__.py': '', 'app/lib.py': lib, 'app/flow.py': FLOW % ('', 'a'), 'app/ui.ts': UI % 'load',
                       'app/lib.ts': 'export const load = (x: number) => x;\nexport const save = load;\nexport const drop = load;\n'})
    _write(tmp_path, {'app/flow.py': FLOW % ('c(0)', 'c'), 'app/ui.ts': UI % 'drop', 'app/added.py': 'def new():\n    return len([])\n'})
    with closing(build(tmp_path)) as graph:
        change = owners.Change(load_config(tmp_path), graph, 'HEAD')
        # A Python function's calls also name what it passes on (x, y), as the call index reads them.
        assert change.callees('app.flow:run') == {'inner', 'b', 'c', 'x', 'y'}
        assert change.callees('app.flow:run', old=True) == {'inner', 'b', 'a', 'x', 'y'}
        assert change.callees('app.flow:run.inner') == {'c', 'y'}
        assert change.callees('app.flow:keep') == change.callees('app.flow:keep', old=True) == {'a', 'x'}
        # A module's own code, without its functions.
        assert change.callees('app.flow') == {'print', 'c'} and change.callees('app.flow', old=True) == {'print'}
        # A JS/TS function with its callback, now and at the baseline.
        ui = graph.con.execute("SELECT id FROM node WHERE kind='module' AND file='app/ui.ts'").fetchone()[0]
        assert change.callees(ui + ':start') == {'items.map', 'drop'}
        assert change.callees(ui + ':start', old=True) == {'items.map', 'load'}
        assert change.callees(ui + ':stay') == change.callees(ui + ':stay', old=True) == {'save'}
        # A file this change adds had no calls at the baseline; a function of no mapped file calls nothing.
        assert change.callees('app.added:new') == {'len'} and change.callees('app.added:new', old=True) == frozenset()
        # A file this change leaves alone is read once, as it is now.
        assert 'app/lib.py' not in change.files and change.callees('app.lib:c', old=True) == change.callees('app.lib:c') == {'a', 'x'}
        assert change.callees('nowhere:f') == change.callees('nowhere:f', old=True) == frozenset()


def test_static_findings_take_the_catalog_loosened_and_impact_findings_and_carry_known_entries(tmp_path, monkeypatch):
    root = _project(tmp_path)
    with closing(build(root)) as graph:
        cfg, index = load_config(root), anchors.collect(graph)
        plain = owners.static_findings(cfg, graph, index)
        assert plain.known == [] and all(issue.family for issue in plain.issues)
        # Without rules.toml or known.toml, now or at the baseline, the catalog adds nothing, not even a loosened line
        # (loosened and field_impact have their own tests); what each hook returns joins the one list.
        assert sources.findings(cfg, graph, owners.Change(cfg, graph, 'HEAD')) == owners.Findings()
        assert sources.findings(cfg, graph, owners.Change(cfg, graph, None)) == owners.Findings()
        entry = sources.Known('k', ('app/a.ts:setState',), 'why', 'leave')
        catalog = Issue('input:known.k', 1, 'known.k', 'text', 'step', family='input', subject='known.k',
                        parts=(('', '.flowguard/known.toml:1', 'is invalid', 'fix it'),), fresh=frozenset({''}))
        monkeypatch.setattr(sources, 'findings', lambda cfg, graph, change: owners.Findings(issues=[catalog], known=[entry]))
        monkeypatch.setattr(owners, 'loosened', lambda change, index: owners.Findings(red=['loosened red']))
        monkeypatch.setattr(owners, 'field_impact', lambda change, index: owners.Findings(leads=['impact lead']))
        found = owners.static_findings(cfg, graph, index)
    assert found.known == [entry] and catalog in found.issues
    assert 'loosened red' in found.red and 'impact lead' in found.leads


PASS = """
    from app.lib import run, save, drop

    def f(order):
        def later():
            return run(key=%s)
        return run(%s)
"""


def test_python_callees_include_the_callables_a_function_passes_on_which_its_call_tree_follows(tmp_path):
    lib = 'def run(cb=None, key=None):\n    return cb()\n\ndef save():\n    return 1\n\ndef drop():\n    return 2\n'
    _commit(tmp_path, {'app/__init__.py': '', 'app/lib.py': lib, 'app/flow.py': PASS % ('save', 'save'),
                       'tests/test_flow.py': 'from app.lib import run, save\n\ndef test_f():\n    assert run(save) == 1\n'})
    _write(tmp_path, {'app/flow.py': PASS % ('drop', 'drop'),
                      'tests/test_flow.py': 'from app.lib import run, drop\n\ndef test_f():\n    assert run(drop) == 2\n'})
    with closing(build(tmp_path)) as graph:
        change = owners.Change(load_config(tmp_path), graph, 'HEAD')
        tree = set(graph.call_tree('app.flow:f', 1))
        assert 'app.lib:drop' in tree and 'app.lib:save' not in tree
        # The call tree follows `drop` passed to run, so the callees name it, now and (`save`) at the baseline.
        assert change.callees('app.flow:f') == {'run', 'drop'}
        assert change.callees('app.flow:f', old=True) == {'run', 'save'}
        assert change.callees('app.flow:f.later') == {'run', 'drop'}
        # A test file keeps no function facts: its syntax calls alone.
        test = graph.con.execute("SELECT module FROM file WHERE path='tests/test_flow.py'").fetchone()[0]
        assert change.callees(test + ':test_f') == change.callees(test + ':test_f', old=True) == {'run'}


def test_files_this_change_deletes_or_renames_away_are_read_at_the_baseline(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': SET_STATE, 'app/order.py': ORDER % 'status',
                       'app/__init__.py': '', 'app/lib.py': 'def a(x):\n    return x\n',
                       'app/gone.py': 'from app.lib import a\n\ndef f(x):\n    return a(x)\n',
                       'app/old.py': 'from app.lib import a\n\ndef g(x):\n    return a(x)\n'})
    _git(tmp_path, 'rm', '-q', 'app/order.py')               # staged
    (tmp_path / 'app/gone.py').unlink()                         # not staged
    _git(tmp_path, 'mv', 'app/a.ts', 'app/moved.ts')
    _git(tmp_path, 'mv', 'app/old.py', 'app/new.py')
    with closing(build(tmp_path)) as graph:
        change = owners.Change(load_config(tmp_path), graph, 'HEAD')
        # Git's rename detection names a staged rename by its new path only.
        assert change.files == {'app/order.py', 'app/gone.py', 'app/moved.ts', 'app/new.py'}
        assert change.baseline_paths() == change.files | {'app/a.ts', 'app/old.py'}
        assert _writes(graph.writes('Item.state')) == [('app/moved.ts', 'setState', 'state')]
        assert _writes(change.baseline_writes('Item.state')) == [('app/a.ts', 'setState', 'state')]
        assert _writes(change.baseline_writes('Order')) == [('app/order.py', 'close', 'status')]
        assert change.callees('app.gone:f', old=True) == {'a', 'x'} and change.callees('app.gone:f') == frozenset()
        assert change.callees('app.old:g', old=True) == {'a', 'x'} and change.callees('app.new:g', old=True) == frozenset()
        assert change.old_facts('app/gone.py')['module'] == 'app.gone'
        assert [node['qual'] for node in change.old_part('app/order.py', 'nodes')] == ['Order', 'close']
        # A file this change never had at the baseline, or that the map does not read, has no baseline facts.
        assert change.old_facts('app/new.py') == {} and change.old_part('app/new.py', 'nodes') is None
        assert change.old_facts('README.md') == {} and change.module('README.md') is None


STATES = "export const S = { A: '%s', B: 'shut' } as const;\n"
SET_BY_NAME = """
    import { S } from './states';
    export async function setState(prisma: any) {
      await prisma.item.update({ where: { id: '1' }, data: { state: S.A } });
    }
    export async function setOther(prisma: any) {
      await prisma.item.update({ where: { id: '2' }, data: { state: S.B } });
    }
"""
KINDS_PY = "PREFIX = '%s'\nCLOSED = PREFIX\n"
CLOSE_PY = """
    from app.kinds import CLOSED, PREFIX

    class Order:
        status: str
        reason: str

    def close(order: Order):
        order.status = CLOSED

    def mark(order: Order):
        order.reason = PREFIX
"""


def _values(rows):
    return [(row['file'], row['function'], row['field'], row.get('values')) for row in rows]


def test_baseline_writes_resolve_values_and_models_with_the_definitions_the_baseline_had(tmp_path):
    schema = 'model Item {\n  id    String @id\n  state String @map("%s")\n  note  String\n}\n'
    _commit(tmp_path, {'prisma/schema.prisma': schema % 'st', 'app/states.ts': STATES % 'open', 'app/b.ts': SET_BY_NAME,
                       'app/__init__.py': '', 'app/kinds.py': KINDS_PY % 'x-', 'app/order.py': CLOSE_PY})
    _write(tmp_path, {'prisma/schema.prisma': schema % 'item_state', 'app/states.ts': STATES % 'opened',
                      'app/kinds.py': KINDS_PY % 'y-'})
    with closing(build(tmp_path)) as graph:
        change = owners.Change(load_config(tmp_path), graph, 'HEAD')
        assert change.files == {'prisma/schema.prisma', 'app/states.ts', 'app/kinds.py'}
        # app/b.ts and app/order.py are unchanged; the constants and the column they read are not.
        assert _values(graph.writes('Item.state')) == [('app/b.ts', 'setState', 'state', ['opened']),
                                                       ('app/b.ts', 'setOther', 'state', ['shut'])]
        assert _values(change.baseline_writes('Item.state')) == [('app/b.ts', 'setState', 'state', ['open']),
                                                                 ('app/b.ts', 'setOther', 'state', ['shut'])]
        assert [row['db_column'] for row in graph.writes('Item.state')] == ['item_state'] * 2
        assert [row['db_column'] for row in change.baseline_writes('Item.state')] == ['st'] * 2
        # A Python constant, also one folded from another constant of its module.
        assert _values(graph.writes('Order')) == [('app/order.py', 'close', 'status', ['y-']),
                                                  ('app/order.py', 'mark', 'reason', ['y-'])]
        assert _values(change.baseline_writes('Order')) == [('app/order.py', 'close', 'status', ['x-']),
                                                            ('app/order.py', 'mark', 'reason', ['x-'])]
        assert change.baseline_writes('Order')[0]['value'] == 'x-'


def test_baseline_writes_equal_the_maps_when_this_change_alters_no_definition(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/states.ts': STATES % 'open', 'app/b.ts': SET_BY_NAME,
                       'app/__init__.py': '', 'app/kinds.py': KINDS_PY % 'x-', 'app/order.py': CLOSE_PY,
                       'app/other.py': 'X = 1\n'})
    # Lines added after the writes: each changed file's baseline rows are its current ones, read from old facts.
    _write(tmp_path, {'app/other.py': 'X = 2\n', 'app/order.py': CLOSE_PY + '\n    def extra():\n        return 1\n',
                      'app/b.ts': SET_BY_NAME + '\n    export function extra() { return 1; }\n'})
    with closing(build(tmp_path)) as graph:
        change = owners.Change(load_config(tmp_path), graph, 'HEAD')
        assert change.files == {'app/other.py', 'app/order.py', 'app/b.ts'}
        assert _values(change.baseline_writes('Order')) == [('app/order.py', 'close', 'status', ['x-']),
                                                            ('app/order.py', 'mark', 'reason', ['x-'])]
        for target in (None, 'Item.state', 'Order', 'status'):
            for by_name in (False, True):
                assert change.baseline_writes(target, by_name=by_name) == graph.writes(target, by_name=by_name), (target, by_name)
