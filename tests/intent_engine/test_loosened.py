"""What a change loosens in its `flowguard:` comments (design 4.7, D9; stage 3 lane C): each is one `loosened`
line, never red and never silent, and the owner must say yes. Tightening (a partner, writer or exception removed
from what it allowed, an on= dropped, a new agreement) is not loosened.

Each fixture commits its baseline and edits the working tree; the lines are `owners.loosened`'s, passed through
`signals.deliver` as lines already of their kind.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, signals
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _git, _write

SCHEMA = 'model Item {\n  id    String @id\n  state String\n  note  String\n  kind  String\n}\n'
BODY = """export async function setState(prisma: any) {
  await prisma.item.update({ where: { id: '1' }, data: { state: 'A', note: 'n', kind: 'k' } });
}
export async function legacy(prisma: any) {
  await prisma.item.update({ where: { id: '2' }, data: { state: 'B' } });
}
"""
LABEL = '// flowguard: same LABEL\nexport function label(x: string) { return x; }\n'


def _app(*comments, label=LABEL):
    return '\n'.join(comments) + '\n' + BODY + label


def _loosened(root, base='HEAD'):
    cfg = load_config(root)
    with closing(build(root, roots=cfg.roots)) as graph:
        found = owners.loosened(owners.Change(cfg, graph, base), anchors.collect(graph))
    lines, _ = signals.deliver([], touched_functions=(), touched_files=(), extra=found.lines)
    assert all(line.kind == 'loosened' and line.step == "name it in your report; needs the owner's yes" for line in lines)
    return [line.text for line in lines], lines


BASE = _app('// flowguard: together Item.state Item.note,Item.kind', '// flowguard: writers Item.note setState')


def test_an_exception_on_an_on_a_writer_or_a_removed_partner_same_or_writers_agreement_is_loosened(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': BASE,
                       'app/gone.ts': '// flowguard: same LABEL\nexport function label(x: string) { return x + 1; }\n',
                       'app/w.ts': '// flowguard: writers Item.kind setKind\nexport function setKind() { return 1; }\n'})
    _write(tmp_path, {'app/a.ts': _app('// flowguard: together Item.state Item.note on=update except=app/a.ts:legacy(old import)',
                                       '// flowguard: writers Item.note setState,app/w.ts:setKind', label=''),
                      'app/w.ts': 'export function setKind() { return 1; }\n'})
    (tmp_path / 'app/gone.ts').unlink()
    texts, lines = _loosened(tmp_path)
    assert sorted(texts) == sorted([
        'except=legacy added to together Item.state',
        'Item.kind removed from together Item.state',
        'on=update added to together Item.state',
        'app/w.ts:setKind added to writers Item.note',        # a function of another file, spelled as the comment does
        'writers Item.kind removed',
        'same LABEL removed from app/a.ts:label',
        'same LABEL removed from app/gone.ts:label',          # a file this change deletes, read at the baseline
    ])
    same = next(line for line in lines if line.text == 'same LABEL removed from app/a.ts:label')
    assert same.function == 'typescript/app/a.ts:label' and same.places == ('app/a.ts:9',)      # the baseline's comment
    exception = next(line for line in lines if line.text.startswith('except='))
    assert exception.name == 'loosened:except:Item.state:typescript/app/a.ts:legacy' and exception.places == ('app/a.ts:1',)


def test_a_new_agreement_with_an_exception_is_loosened_and_tightening_is_not(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA,
                       'app/a.ts': _app('// flowguard: together Item.state Item.note on=update except=app/a.ts:legacy(old)',
                                        '// flowguard: writers Item.note setState,legacy')})
    # A partner added, the on= dropped (it now holds creates too), the exception and a writer removed: tighter.
    _write(tmp_path, {'app/a.ts': _app('// flowguard: together Item.state Item.note,Item.kind',
                                       '// flowguard: writers Item.note setState',
                                       '// flowguard: together Item.kind Item.note except=app/a.ts:setState(seeded)',
                                       '// flowguard: writers Item.kind setState')})
    texts, _ = _loosened(tmp_path)
    assert texts == ['except=setState added to together Item.kind']
    # An on= that changes scope is loosened too.
    _write(tmp_path, {'app/a.ts': _app('// flowguard: together Item.state Item.note on=create except=app/a.ts:legacy(old)',
                                       '// flowguard: writers Item.note setState,legacy')})
    assert _loosened(tmp_path)[0] == ['on=create replaces on=update in together Item.state']


def test_the_old_comment_spellings_and_python_are_read_the_same_way(tmp_path):
    source = '''# flowguard: owner Order.status writers=close with=Order.reason,Order.at
class Order:
    status: str
    reason: str
    at: str


# flowguard: sensor LIMIT
def close(order: Order):
    order.status = "x"
    order.reason = "y"
    order.at = "z"
'''
    _commit(tmp_path, {'app/__init__.py': '', 'app/order.py': source})
    _write(tmp_path, {'app/order.py': source.replace('with=Order.reason,Order.at', 'with=Order.reason alone=reopen(legacy)')
                      .replace('writers=close', 'writers=close,reopen').replace('# flowguard: sensor LIMIT\n', '')})
    assert sorted(_loosened(tmp_path)[0]) == sorted([
        'Order.at removed from together Order.status', 'except=reopen added to together Order.status',
        'reopen added to writers Order.status', 'same LIMIT removed from app/order.py:close'])


def test_moving_a_comment_between_files_or_renaming_a_file_loosens_nothing_and_no_baseline_compares_nothing(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': BASE})
    _git(tmp_path, 'mv', 'app/a.ts', 'app/b.ts')
    assert _loosened(tmp_path)[0] == []
    # A comment moved to another file means the same functions when it names them by that file's path.
    _write(tmp_path, {'app/b.ts': BODY + LABEL,
                      'app/c.ts': '// flowguard: together Item.state Item.note,Item.kind\n// flowguard: writers Item.note app/b.ts:setState\n'})
    assert _loosened(tmp_path)[0] == []
    _write(tmp_path, {'app/c.ts': 'export const none = 1;\n'})
    assert len(_loosened(tmp_path)[0]) == 2 and _loosened(tmp_path, base=None)[0] == []


def test_a_file_moved_without_git_keeps_its_agreements(tmp_path):
    # Git sees a deleted file and an untracked one; their comments, the same up to the file they name, moved together.
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': BASE})
    (tmp_path / 'app/a.ts').rename(tmp_path / 'app/b.ts')
    _write(tmp_path, {'app/b.ts': (tmp_path / 'app/b.ts').read_text(encoding='utf-8') + 'export const more = 1;\n'})
    assert _loosened(tmp_path)[0] == []


SAVE = "export async function save(prisma: any) {\n  await prisma.item.update({ where: { id: '1' }, data: { state: '%s' } });\n}\n"


def test_a_comment_moved_to_a_file_with_a_same_named_function_names_another_function(tmp_path):
    # A bare name is the function of the comment's own file (design 4.4): moved beside another save, the agreement
    # lets that save write the field and no longer the first one; a same mark moved so compares another function.
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': '// flowguard: writers Item.state save\n' + SAVE % 'a',
                       'app/b.ts': SAVE % 'b', 'app/ref.ts': '// flowguard: same LABEL ref\nexport function label(x: string) { return x; }\n',
                       'app/c.ts': '// flowguard: same LABEL\n' + 'export function label(x: string) { return x + 1; }\n',
                       'app/d.ts': 'export function label(x: string) { return x + 2; }\n'})
    _write(tmp_path, {'app/a.ts': SAVE % 'a', 'app/b.ts': '// flowguard: writers Item.state save\n' + SAVE % 'b',
                      'app/c.ts': 'export function label(x: string) { return x + 1; }\n',
                      'app/d.ts': '// flowguard: same LABEL\n' + 'export function label(x: string) { return x + 2; }\n'})
    texts, lines = _loosened(tmp_path)
    assert sorted(texts) == ['same LABEL removed from app/c.ts:label', 'save added to writers Item.state']
    writer = next(line for line in lines if line.text.startswith('save added'))
    assert writer.places == ('app/b.ts:1',) and writer.name == 'loosened:writer:Item.state:typescript/app/b.ts:save'
    # Moved beside the other save but naming the first one by its path, the agreement means what it meant.
    _write(tmp_path, {'app/b.ts': '// flowguard: writers Item.state app/a.ts:save\n' + SAVE % 'b'})
    assert _loosened(tmp_path)[0] == ['same LABEL removed from app/c.ts:label']


def test_an_exception_moved_with_its_comment_is_loosened_only_when_it_names_another_function(tmp_path):
    together = '// flowguard: together Item.state Item.note except=app/%s.ts:save(old import)\n'
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': together % 'a' + SAVE % 'a', 'app/b.ts': SAVE % 'b'})
    _write(tmp_path, {'app/a.ts': SAVE % 'a', 'app/b.ts': together % 'a' + SAVE % 'b'})
    assert _loosened(tmp_path)[0] == []
    _write(tmp_path, {'app/b.ts': together % 'b' + SAVE % 'b'})
    assert _loosened(tmp_path)[0] == ['except=save added to together Item.state']


def test_the_static_assembly_carries_the_loosened_lines(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': _app('// flowguard: writers Item.note setState')})
    _write(tmp_path, {'app/a.ts': _app('// flowguard: writers Item.note setState,legacy')})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    assert [(line.kind, line.text) for line in found.lines if line.kind == 'loosened'] == [
        ('loosened', 'legacy added to writers Item.note')]
