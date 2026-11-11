"""`owners.Change` at the baseline: the writes and the calls the baseline code had, and the static assembly's hooks.

Each fixture commits its baseline, then edits one file, adds one and leaves the rest; the map is the working tree's.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, sources
from flowguard.intent.config import load_config
from flowguard.intent.health import Issue
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _write

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
        assert change.callees('app.flow:run') == {'inner', 'b', 'c'}
        assert change.callees('app.flow:run', old=True) == {'inner', 'b', 'a'}
        assert change.callees('app.flow:run.inner') == {'c'}
        assert change.callees('app.flow:keep') == change.callees('app.flow:keep', old=True) == {'a'}
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
        assert 'app/lib.py' not in change.files and change.callees('app.lib:c', old=True) == change.callees('app.lib:c') == {'a'}
        assert change.callees('nowhere:f') == change.callees('nowhere:f', old=True) == frozenset()


def test_static_findings_take_the_catalog_loosened_and_impact_findings_and_carry_known_entries(tmp_path, monkeypatch):
    root = _project(tmp_path)
    with closing(build(root)) as graph:
        cfg, index = load_config(root), anchors.collect(graph)
        plain = owners.static_findings(cfg, graph, index)
        assert plain.known == [] and not [issue for issue in plain.issues if issue.family]
        # The stubs add nothing; what each hook returns joins the one list.
        assert sources.findings(cfg, graph, None) == owners.Findings()
        assert owners.loosened(None, index) == owners.Findings() == owners.field_impact(None, index)
        entry = sources.Known('k', ('app/a.ts:setState',), 'why', 'leave')
        catalog = Issue('input:known.k', 1, 'known.k', 'text', 'step', family='input', subject='known.k',
                        parts=(('', '.flowguard/known.toml:1', 'is invalid', 'fix it'),), fresh=frozenset({''}))
        monkeypatch.setattr(sources, 'findings', lambda cfg, graph, change: owners.Findings(issues=[catalog], known=[entry]))
        monkeypatch.setattr(owners, 'loosened', lambda change, index: owners.Findings(red=['loosened red']))
        monkeypatch.setattr(owners, 'field_impact', lambda change, index: owners.Findings(leads=['impact lead']))
        found = owners.static_findings(cfg, graph, index)
    assert found.known == [entry] and catalog in found.issues
    assert 'loosened red' in found.red and 'impact lead' in found.leads
