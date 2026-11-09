"""Each kind of a file's facts is stored once more on its own, so a query unpacks only what it reads.

A map query that needs one or two kinds of every file (languages, anchors, writes, value sets) used to
unpack every file's whole record; on a 1 100-file project that alone took seconds. The parts must give
exactly the record's facts, also after a file is changed, relinked or removed.
"""
from contextlib import closing

from flowguard.intent import anchors
from flowguard.structure import build
from flowguard.structure.paths import project_code, project_files


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


FILES = {
    'shop/__init__.py': '',
    'shop/policy.py': ('from enum import Enum\nfrom shop.store import save as keep\n\n\nclass Status(Enum):\n    OPEN = "open"\n'
                       '    SHUT = "shut"\n\n\nclass Order:\n    status: Status\n\n\n'
                       '# flowguard: sensor GRACE\ndef grace(days: int) -> bool:\n    """grace days after expiry"""\n'
                       '    return days <= 3\n\n\ndef close(order: Order):\n    order.status = "gone"\n    keep(order)\n'),
    'shop/store.py': 'ROWS = []\n\n\ndef save(order):\n    ROWS.append(order)\n    return order\n',
    'web/app.ts': ("import { api } from './client';\nexport function countWorkingDays(a: number): number {\n"
                   "  try { return api(a); } catch (e) { return 0; }\n}\n"
                   "export function mark(x: { state: string }) { if (x.state === 'My Organization') { x.state = 'done'; } }\n"),
    'web/client.ts': 'export const api = (a: number) => a + 1;\n',
    'db/schema.prisma': 'model Employee {\n  id Int @id\n  organizationalUnitId Int\n}\n',
}


def same_as_records(graph):
    records = {path: (error, facts) for path, error, facts in graph._files()}
    kinds = sorted({kind for _, facts in records.values() for kind in facts})
    parted = graph._kinds(*kinds)
    assert [path for path, _, _ in parted] == sorted(records)
    for path, error, facts in parted:
        assert (error, facts) == records[path], path
    for kind in [kind for kind in kinds if all(isinstance(facts.get(kind, []), list) for _, facts in records.values())]:
        assert graph._syntax(kind) == [fact for _, (_, facts) in sorted(records.items()) for fact in facts.get(kind, [])]


def test_parts_are_the_stored_records_after_every_kind_of_build(tmp_path):
    write(tmp_path, FILES)
    with closing(build(tmp_path)) as graph:
        same_as_records(graph)
        index = anchors.collect(graph)
        assert [entry.name for entry in index.entries] == ['GRACE']
        assert [issue.code for issue in index.issues if issue.code == 'states-values'] == ['states-values']
        assert graph.capabilities()['languages']['typescript']['files'] == 2
        assert {row['field'] for row in graph.writes('Order.status')} == {'status'}
    write(tmp_path, {'shop/store.py': 'ROWS = []\n\n\ndef save(order):\n    """kept"""\n    return order\n',
                     'web/client.ts': 'export const api = (a: number) => a + 2;\nexport const other = 1;\n'})
    (tmp_path / 'db/schema.prisma').unlink()
    with closing(build(tmp_path)) as graph:
        assert graph.stats['changed']
        same_as_records(graph)
        assert graph.con.execute("SELECT COUNT(*) FROM part WHERE path='db/schema.prisma'").fetchone() == (0,)
        assert graph.capabilities()['languages'].get('prisma') is None


def test_one_listing_of_the_project_boundary_answers_as_each_file_alone(tmp_path):
    write(tmp_path, {'app/a.py': '', 'app/b.py': '', 'env/lib/x.py': '', 'env/pyvenv.cfg': '', 'deep/env2/sub/y.py': '',
                     'deep/env2/pyvenv.cfg': '', 'deep/z.py': '', 'site-packages/s.py': ''})
    (tmp_path / 'link.py').symlink_to(tmp_path / 'app/a.py')
    (tmp_path / 'out.py').symlink_to(tmp_path.parent / 'elsewhere.py')
    names = [str(tmp_path / name) for name in ('app/a.py', 'app/b.py', 'env/lib/x.py', 'deep/env2/sub/y.py', 'deep/z.py',
                                               'site-packages/s.py', 'link.py', 'out.py', 'app/../app/a.py', 'missing.py')]
    names.append(str(tmp_path.parent / 'other.py'))
    alone = [project_code(name, tmp_path) for name in names]
    assert alone == [True, True, False, False, True, False, True, False, True, True, False]
    assert project_files(names, tmp_path) == alone
