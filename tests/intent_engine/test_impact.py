"""The impact line (design 4.6, stage 3 lane C): one `impact` line per function this change edits or adds whose
set of written fields changed, with counts and one name; `show Model.field` lists what the line counts.

Each fixture commits its baseline and edits the working tree; the lines are `owners.field_impact`'s, passed
through `signals.deliver` as lines already of their kind.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, signals
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _flowguard, _write

SCHEMA = '''
model Entry {
  id        String   @id
  value     Float
  note      String
  updatedAt DateTime
}
'''


def _update(function, data, comment=''):
    return comment + f"""export async function {function}(prisma: any) {{
  await prisma.entry.update({{ where: {{ id: '1' }}, data: {{ {data} }} }});
}}
"""


BASE = {
    'prisma/schema.prisma': SCHEMA,
    'app/set.ts': _update('setValue', "note: 'n'") + _update('keep', "note: 'k'"),
    'app/b.ts': _update('otherB', 'value: 1'),
    'app/c.ts': _update('otherC', 'value: 2'),
    'prisma/seed.ts': _update('seedEntries', 'value: 3'),
    'app/drop.ts': _update('dropNote', "note: 'd'"),
    'app/read.ts': '''export async function listEntries(prisma: any) { return prisma.entry.findMany({ where: { note: 'a' } }); }
export async function countEntries(prisma: any) { return prisma.entry.count({ where: { value: 1 } }); }
''',
    'tests/entry.test.ts': "export async function fixture(prisma: any) { return prisma.entry.findMany({ where: { id: '1' } }); }\n",
}
CHANGED = {
    # setValue now writes value (updatedAt is bookkeeping) and no longer note; keep writes what it wrote.
    'app/set.ts': _update('setValue', 'value: 4, updatedAt: new Date()') + _update('keep', "note: 'kept'"),
    'app/drop.ts': 'export async function dropNote(prisma: any) {\n  return prisma;\n}\n',
    'app/new.ts': _update('createEntry', "note: 'c'"),
    'prisma/seed.ts': _update('seedEntries', "value: 3, note: 's'"),          # a seed script: not reported
    'tests/entry.test.ts': "export async function fixture(prisma: any) {\n  return prisma.entry.update({ where: { id: '1' }, data: { note: 't' } });\n}\n",
}


def _impact(root, base='HEAD'):
    cfg = load_config(root)
    with closing(build(root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        found = owners.field_impact(owners.Change(cfg, graph, base), index)
        modules = dict(graph.con.execute('SELECT path, module FROM file'))
    return found, modules


def test_a_changed_function_whose_written_fields_changed_gets_one_impact_line_with_counts_and_one_name(tmp_path):
    _commit(tmp_path, BASE)
    _write(tmp_path, CHANGED)
    found, modules = _impact(tmp_path)
    lines, _ = signals.deliver([], touched_functions=(), touched_files=(), extra=found.lines)
    by_function = {line.function: line for line in lines}
    assert [line.kind for line in lines] == ['impact'] * 3 and not found.issues
    assert sorted(by_function) == sorted([modules['app/set.ts'] + ':setValue', modules['app/drop.ts'] + ':dropNote',
                                          modules['app/new.ts'] + ':createEntry'])
    line = by_function[modules['app/set.ts'] + ':setValue']
    # Other writers of Entry.value: otherB and otherC (the seed script is left out); four files write it without a
    # writers agreement (the seed's too); two functions read Entry (the test file's fixture now updates it).
    assert line.name == 'impact:' + line.function and line.places == ('app/set.ts:setValue',)
    assert line.text == ('setValue now writes Entry.value; no longer writes Entry.note; 2 other writers (no writers agreement), '
                         '2 readers of Entry')
    assert line.step == 'check them for this change only (python -m flowguard show Entry.value)'
    assert sorted(line.detail) == sorted([f'other writer of Entry.value: {modules["app/b.ts"]}:otherB',
                                          f'other writer of Entry.value: {modules["app/c.ts"]}:otherC',
                                          f'reader of Entry: {modules["app/read.ts"]}:countEntries',
                                          f'reader of Entry: {modules["app/read.ts"]}:listEntries'])
    # An added function; one that only stopped writing a field. keep, createEntry and the seed write Entry.note now:
    # three files without a writers agreement, of which two production functions besides each.
    assert by_function[modules['app/new.ts'] + ':createEntry'].text == \
        'createEntry now writes Entry.note; 1 other writer (no writers agreement), 2 readers of Entry'
    assert by_function[modules['app/drop.ts'] + ':dropNote'].text == \
        'dropNote no longer writes Entry.note; 2 other writers (no writers agreement), 2 readers of Entry'
    assert by_function[modules['app/drop.ts'] + ':dropNote'].step.endswith('(python -m flowguard show Entry.note)')


def test_a_writers_agreement_on_the_field_leaves_out_the_merged_writers_problem_and_no_baseline_gives_no_line(tmp_path):
    agreement = '// flowguard: writers Entry.value setValue,app/b.ts:otherB,app/c.ts:otherC,prisma/seed.ts:seedEntries\n'
    _commit(tmp_path, {**BASE, 'app/set.ts': _update('setValue', "note: 'n'", agreement)})
    _write(tmp_path, {'app/set.ts': _update('setValue', 'value: 4', agreement)})
    found, modules = _impact(tmp_path)
    # Every function that reads the model counts, the test file's fixture too.
    assert [line.text for line in found.lines] == ['setValue now writes Entry.value; no longer writes Entry.note; 2 other writers, 3 readers of Entry']
    assert _impact(tmp_path, base=None)[0].lines == []


def test_the_static_assembly_carries_the_impact_lines(tmp_path):
    _commit(tmp_path, BASE)
    _write(tmp_path, {'app/new.ts': _update('createEntry', "note: 'c'")})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    assert [(line.kind, line.name.partition(':')[0]) for line in found.lines] == [('impact', 'impact')]
    lines, _ = signals.deliver(found.issues, touched_functions=found.touched_functions, touched_files=found.touched_files,
                               ran=found.ran, extra=found.lines)
    # No code creates Entry rows: the new update is also a new member of that structure finding, an impact line too.
    assert sorted((line.kind, line.name) for line in lines) == [('impact', 'impact:typescript/app/new.ts:createEntry'),
                                                               ('impact', 'uncreated:Entry')]


def test_show_of_a_field_lists_its_models_readers_the_callers_of_its_writers_and_the_tests_that_reach_them(tmp_path):
    _commit(tmp_path, {
        **BASE,
        'app/__init__.py': '',
        'app/model.py': 'class Account:\n    status: str\n',
        'app/service.py': 'from app.model import Account\n\n\ndef close(account: Account):\n    account.status = "closed"\n',
        'app/api.py': 'from app.service import close\n\n\ndef handle(account):\n    return close(account)\n',
        'tests/test_service.py': 'from app.service import close\n\n\ndef test_close():\n    assert close is not None\n',
    })
    code, text = _flowguard(tmp_path, 'show', 'Account.status', '--full')
    lines = text.splitlines()
    assert code == 0, text
    assert 'writes Account.status app/service.py:5 close (assign)' in lines, text
    assert 'caller of close: handle (app/api.py:4)' in lines, text
    assert 'test tests/test_service.py reaches a writer of Account.status' in lines, text
    code, text = _flowguard(tmp_path, 'show', 'Entry.value', '--full')
    lines = text.splitlines()
    assert code == 0, text
    assert 'reads Entry app/read.ts:1 listEntries (findMany)' in lines and 'reads Entry app/read.ts:2 countEntries (count)' in lines, text
    assert 'reads Entry tests/entry.test.ts:1 fixture (findMany)' in lines, text       # every read of the model


def test_a_function_that_stops_writing_one_of_two_fields_gets_its_line_and_the_static_check_still_runs(tmp_path):
    # It still writes Entry.value, so the field it no longer writes is found among the baseline's rows only.
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/set.ts': _update('setBoth', "value: 1, note: 'n'")})
    _write(tmp_path, {'app/set.ts': _update('setBoth', 'value: 1')})
    found, modules = _impact(tmp_path)
    assert [(line.function, line.text, line.places) for line in found.lines] == [
        (modules['app/set.ts'] + ':setBoth', 'setBoth no longer writes Entry.note; 0 other writers, 0 readers of Entry',
         ('app/set.ts:setBoth',))]
    assert found.lines[0].step == 'check them for this change only (python -m flowguard show Entry.note)'
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        assembled = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    assert [line.text for line in assembled.lines if line.kind == 'impact'] == [found.lines[0].text]
    code, text = _flowguard(tmp_path, 'check', '--static')
    assert code == 0 and 'Traceback' not in text, text


def test_a_sql_write_is_shown_by_its_column_and_a_select_of_its_table_counts_as_a_reader(tmp_path):
    """SQL in string literals (Python): `show table.column` names the column each UPDATE writes, and the impact line
    and show count the function whose SELECT reads that table, in the number each count needs."""
    store = '''def reserve(db, booking_id, unit):
    db.execute("UPDATE booking SET unit_id = ? WHERE id = ?", (unit, booking_id))


def release(db, booking_id):
    db.execute("UPDATE booking SET unit_id = NULL WHERE id = ?", (booking_id,))


def close_day(db, booking_id):
    db.execute("UPDATE booking SET note = 'closed' WHERE id = ?", (booking_id,))


def load(db, booking_id):
    return db.execute("SELECT unit_id FROM booking WHERE id = ?", (booking_id,)).fetchone()
'''
    _commit(tmp_path, {'store.py': store})
    _write(tmp_path, {'store.py': store.replace("SET note = 'closed' WHERE", "SET note = 'closed', unit_id = NULL WHERE")})
    found, _ = _impact(tmp_path)
    assert [line.text for line in found.lines] == [
        'close_day now writes booking.unit_id; 2 other writers, 1 reader of booking'], found.lines
    code, text = _flowguard(tmp_path, 'show', 'booking.unit_id', '--full')
    lines = text.splitlines()
    assert code == 0 and 'writes booking.unit_id store.py:10 close_day (sql:update)' in lines, text
    assert 'reads booking store.py:13 load (select)' in lines and 'None' not in text, text
