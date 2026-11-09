"""Python write points and decision literals, read by the same map queries as TS/JS."""
from contextlib import closing
import textwrap

from flowguard.structure import build
from flowguard.structure.analysis import sql_names


SHOP = '''
import logging
from typing import Literal
log = logging.getLogger(__name__)
Kind = Literal['member', 'guest']


class Hire:
    def __init__(self):
        self.reserved = 0


def reserve(db, hire_id):
    db.execute("UPDATE hires SET reserved = 1, note = 'it''s held' WHERE id = ?", (hire_id,))


def cancel(db, hire: Hire, other):
    hire.reserved = 0
    other.reserved = None
    db.execute("""
        INSERT INTO audit (hire, action) VALUES (?, 'cancel')""", (1,))
    db.execute("DELETE FROM holds WHERE hire = ?", (1,))
    db.execute("SELECT reserved FROM hires WHERE id = ?", (1,))


def label(kind, row, mapping):
    if kind == 'My Organization':
        log.info('ignored %s', 'Logged')
        return 'Mine' if row else 'Other'
    if kind in ('a', 'b') and 'id' in row:
        raise ValueError('bad id')
    match kind:
        case 'zz':
            return {'id': 1, 'ID': 2}
    print('printed')
    return mapping['Key'] or 'fallback'


ALLOWED = {'x', 'y'}
FROZEN = frozenset(['p'])
'''


def test_python_writes_are_attribute_assignments_and_sql_statements_in_string_literals(tmp_path):
    (tmp_path / 'shop.py').write_text(textwrap.dedent(SHOP).lstrip())
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_shop.py').write_text('def test_x(db):\n    db.execute("UPDATE hires SET reserved = 9")\n')
    with closing(build(tmp_path)) as graph:
        rows = graph.writes('hires.reserved', by_name=True)
        found = {(row['function'], row['kind'], row.get('model'), row.get('table'), row.get('how')): row.get('value', '<none>')
                 for row in rows}
        assert found == {('reserve', 'sql:update', None, 'hires', 'sql'): 1,
                         ('cancel', 'assign', None, None, 'name'): None}, found
        assert graph.writes('Hire.reserved') and {row['value'] for row in graph.writes('Hire.reserved')} == {0}
        audit = {row['db_column']: row.get('value', '<none>') for row in graph.writes('audit')}
        assert audit == {'hire': '<none>', 'action': 'cancel'}       # a placeholder spells no value
        note = next(row for row in graph.writes('hires.note'))
        assert note['value'] == "it's held" and note['line'] == 13
        holds = graph.writes('holds')
        assert [(row['kind'], row['db_column'], row['line']) for row in holds] == [('sql:delete', '*', 21)]
        assert all(row['file'] == 'shop.py' for row in rows)       # a test's own SQL is fixture data
        assert graph.query_coverage()['complete']


def test_sql_names_reads_written_tables_and_columns_through_the_statement_reader():
    reads, writes, _ = sql_names('INSERT INTO dbo.loans (member, item) VALUES (?, ?)')
    assert writes == {'sql:dbo.loans', 'col:member', 'col:item'}
    _, writes, _ = sql_names('CREATE TABLE t (id INTEGER, name TEXT, PRIMARY KEY (id))')
    assert writes == {'sql:t', 'col:id', 'col:name'}             # a constraint is not a column
    _, writes, _ = sql_names('REPLACE INTO cache (k) VALUES (1)')
    assert writes == {'sql:cache', 'col:k'}


def test_python_literals_follow_the_ts_contexts_and_share_one_grouping(tmp_path):
    (tmp_path / 'shop.py').write_text(textwrap.dedent(SHOP).lstrip())
    (tmp_path / 'other.py').write_text("def name(kind):\n    return 'My organization' if kind else 'mine'\n")
    with closing(build(tmp_path)) as graph:
        found = {(row['value'], row['context']) for row in graph.literals(language='python')}
        assert {('member', 'union'), ('guest', 'union'), ('My Organization', 'compare'), ('Mine', 'return'),
                ('Other', 'return'), ('a', 'member'), ('b', 'member'), ('zz', 'case'), ('fallback', 'return'),
                ('x', 'set'), ('y', 'set'), ('p', 'set')} <= found, found
        values = {value for value, _ in found}
        # Dict keys, `'id' in row`, logging, print, exception messages and subscripts are not decisions.
        assert not values & {'id', 'ID', 'Key', 'ignored %s', 'Logged', 'bad id', 'printed'}, found
        groups = {group['key']: sorted(group['spellings']) for group in graph.literal_groups()}
        assert groups['myorganization'] == ['My Organization', 'My organization']
        assert groups['mine'] == ['Mine', 'mine'] and 'id' not in groups
