"""A check reads each fact once: the parts a query takes are the record's own rows, and what one check derives is kept.

`check --static` on a 1 100-file TypeScript project spent most of its time decoding facts it then threw away (every
syntax call to resolve a few by name, every assignment to find the member writes, every file's calls for the
ledger's Python warning filters) and redoing work per call or per agreement. These tests hold the shortcuts to the
answers of the long way.
"""
from contextlib import closing
import subprocess

from flowguard.intent import anchors
from flowguard.structure import build
from flowguard.structure.readers.registry import ECMA, language_for


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


FILES = {
    'backend/package.json': '{"name": "backend"}\n',
    'frontend/package.json': '{"name": "frontend"}\n',
    'backend/src/store.ts': ("export function save(x: number) { return x; }\n"
                             "export const repo = { find(id: number) { return save(id); } };\n"),
    'backend/src/service.ts': ("import { prisma } from './db';\n"
                               "export class Service {\n  helper() { return 1; }\n"
                               "  run(row: any) { row.state = 'done'; return this.helper() + repo.find(2) + save(3); }\n}\n"
                               "export class Other {\n  helper() { return 2; }\n"
                               "  go() { prisma.user.update({ where: { id: 1 }, data: { name: 'x' } }); return this.helper(); }\n}\n"
                               "export function loose(thing: any) { let n = 0; n = 1; return thing.find(4) + n; }\n"),
    'backend/src/db.ts': 'export const prisma: any = {};\n',
    'backend/prisma/schema.prisma': 'model User {\n  id Int @id\n  name String\n}\n',
    'frontend/src/save.ts': "export function save(y: string) { return y; }\nexport function use() { return save('a'); }\n",
    'frontend/src/other.ts': "export function other() { return save('b'); }\n",
    'frontend/src/view.tsx': "export function Widget() { return null; }\nexport function Page() { return <Widget />; }\n",
    'app.py': ('import warnings\n\n\nclass Order:\n    status = "open"\n\n\ndef quiet(order: Order):\n'
               '    warnings.simplefilter("ignore")\n    order.status = "shut"\n    return helper()\n\n\ndef helper():\n    return 1\n'),
}

NAMED = {   # the JS/TS calls the linker leaves unresolved and the call index resolves by name
    ('typescript/backend/src/service.ts:Service.run', 'typescript/backend/src/service.ts:Service.helper'),
    ('typescript/backend/src/service.ts:Service.run', 'typescript/backend/src/store.ts:find'),
    ('typescript/backend/src/service.ts:Service.run', 'typescript/backend/src/store.ts:save'),
    ('typescript/backend/src/service.ts:Other.go', 'typescript/backend/src/service.ts:Other.helper'),
    ('typescript/backend/src/service.ts:loose', 'typescript/backend/src/store.ts:find'),
    ('typescript/frontend/src/other.ts:other', 'typescript/frontend/src/save.ts:save'),
}


def named_calls(graph):
    down, up = graph.call_index()
    assert {(dst, src) for src, targets in down.items() for dst in targets} == {
        (dst, src) for dst, sources in up.items() for src in sources}
    return {(src, dst) for src, targets in down.items() for dst, how in targets.items() if how == 'name'}


def test_calls_resolved_by_name_stay_in_their_package_and_holder(tmp_path):
    """`this.helper()` names the method of its own class; `save()` the one function of that name in the caller's
    package, for each file of its own (backend's from the backend, frontend's from the frontend); `repo.find()` the
    method of the object literal `repo`; a JSX element and a Prisma client call are never resolved by name."""
    write(tmp_path, FILES)
    with closing(build(tmp_path)) as graph:
        assert named_calls(graph) == NAMED
        assert graph.call_index() is graph.call_index()       # read once per handle
        tree = graph.call_tree('typescript/backend/src/service.ts:Service.run', 1)
        assert tree['typescript/backend/src/store.ts:save'] == 'name'
        assert graph.call_tree('typescript/backend/src/service.ts:Service.run', 1) == tree


def records(graph):
    return {path: facts for path, _, facts in graph._files()}


def test_derived_parts_are_the_record_rows_their_readers_take(tmp_path):
    """`syntax_calls.unresolved` holds each JS/TS call the linker left unresolved (JSX elements aside), and
    `assignments.writes` a Python file's assignments and a JS/TS file's member assignments with a field: `writes()`
    from them is `writes()` from the whole records, also after a rebuild changes and removes files."""
    write(tmp_path, FILES)
    for step in range(2):
        with closing(build(tmp_path)) as graph:
            whole = records(graph)
            unresolved = {path: data['syntax_calls.unresolved'] for path, _, data in graph._kinds('syntax_calls.unresolved')
                          if 'syntax_calls.unresolved' in data}
            assert unresolved == {path: rows for path, rows in (
                (path, [[call['node'], call['file'], call['text']] for call in facts.get('syntax_calls', ())
                        if not (call.get('resolved') or call.get('kind') == 'jsx-element')])
                for path, facts in whole.items() if facts.get('language', 'python') in ECMA) if rows}
            assert any(text == 'save' for rows in unresolved.values() for _, _, text in rows)
            written = {path: data['assignments'] for path, _, data in graph.write_records() if 'assignments' in data}
            assert written == {path: rows for path, rows in (
                (path, facts['assignments'] if facts.get('language', 'python') == 'python' else
                 [row for row in facts['assignments'] if row.get('form') == 'member' and row.get('field')])
                for path, facts in whole.items() if facts.get('assignments')
                and facts.get('language', 'python') in ('python', *ECMA)) if rows}
            assert {row['field'] for rows in written.values() for row in rows} >= {'state', 'app:Order.status'}
            for by_name in (True, False):
                assert graph.writes(by_name=by_name) == graph.writes(by_name=by_name, facts=[whole[path] for path in sorted(whole)])
                assert graph.writes(by_name=by_name, fold=False) == graph.writes(
                    by_name=by_name, fold=False, facts=[whole[path] for path in sorted(whole)])
            assert named_calls(graph) == (NAMED if step == 0 else NAMED - {
                ('typescript/frontend/src/other.ts:other', 'typescript/frontend/src/save.ts:save')} | {
                ('typescript/backend/src/service.ts:Service.run', 'typescript/backend/src/service.ts:Service.later')})
        if step == 0:
            write(tmp_path, {'backend/src/service.ts': FILES['backend/src/service.ts'].replace(
                'return this.helper() +', 'row.later = 1; return this.later() + this.helper() +').replace(
                '  helper() { return 1; }\n', '  helper() { return 1; }\n  later() { return 0; }\n')})
            (tmp_path / 'frontend/src/other.ts').unlink()


def test_the_ledger_reads_the_python_calls_alone_as_calls_has_them(tmp_path):
    write(tmp_path, FILES)
    with closing(build(tmp_path)) as graph:
        python = graph.python_calls()
        assert python == [row for row in graph.calls() if language_for(row['file']) == 'python']
        assert {row['resolved'] for row in python} >= {'warnings.simplefilter'}
        assert graph.python_calls() == python and graph.python_calls() is not python      # read once, a list of its own
        graph.reset_query_coverage()
        graph.python_calls()
        alone = graph.query_coverage()
        graph.reset_query_coverage()
        graph.calls()
        assert alone == graph.query_coverage()


def test_agreement_positions_are_read_for_the_modules_asked_for(tmp_path):
    write(tmp_path, FILES)
    with closing(build(tmp_path)) as graph:
        modules = dict(graph.con.execute('SELECT path, module FROM file'))
        positions = anchors._agreement_positions(graph, modules)
        assert positions['typescript/backend/src/store.ts'] == {
            'save': ['typescript/backend/src/store.ts:save'], 'repo.find': ['typescript/backend/src/store.ts:find']}
        assert positions['app'] == {'quiet': ['app:quiet'], 'helper': ['app:helper']}
        assert positions['no.such.module'] == {}
        assert set(positions) == {'typescript/backend/src/store.ts', 'app', 'no.such.module'}


def test_a_decoded_baseline_record_gives_its_parts(tmp_path):
    write(tmp_path, {'app.py': FILES['app.py']})
    for args in (['init', '-q', '-b', 'main'], ['add', '.'], ['commit', '-qm', 'start']):
        subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args],
                       check=True)
    with closing(build(tmp_path)) as graph:
        whole = graph._baseline_facts('HEAD', 'app.py', 'app')
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'nodes') is whole['nodes']
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'no such kind') is None
    with closing(build(tmp_path)) as graph:          # another handle reads the part kept for the record
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'nodes') == whole['nodes']


def test_pair_writes_by_target_are_the_rows_writes_target_selects(tmp_path):
    """The pair check finds a target's write rows through the names each row writes; the answer is the rows
    `_writes_target` selects from all of them, in their order, for a model, a table, a field, a column, `Model.field`
    in any case, and for the Python attribute writes matched by field name alone (no model)."""
    from flowguard.intent.owners import _TargetWrites
    from flowguard.structure.api import _writes_target
    write(tmp_path, {**FILES, 'shop.py': ('class Order:\n    status = "open"\n\n\ndef close(order: Order, thing):\n'
                                          '    order.status = "shut"\n    thing.status = "gone"\n    thing.note = 1\n')})
    with closing(build(tmp_path)) as graph:
        rows, models = graph.writes(by_name=True), graph._models()
        assert {row['how'] for row in rows} >= {'prisma', 'attribute', 'name'}
        assert any(row['how'] == 'name' and row['model'] is None and row['language'] == 'python' for row in rows)
        names = {str(row.get(key)) for row in rows for key in ('model', 'table', 'field', 'db_column') if row.get(key)}
        targets = sorted(names | {f'{a}.{b}' for a in names for b in names} | {name.upper() for name in names}
                         | {'Nope.status', 'nothing', 'User.*'})
        found = _TargetWrites(rows, models)
        for target in targets:
            assert found(target) == [row for row in rows if _writes_target(row, target, models)], target
        assert found('Order.status') is found('Order.status')
        assert any(row['how'] == 'name' for row in found('Order.status'))      # found by its field alone
        assert found('Nope.status') == [row for row in rows if row['field'] == 'status' and row['how'] == 'name'
                                        and row['model'] is None]
