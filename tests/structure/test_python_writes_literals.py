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


def test_python_literals_follow_the_ts_contexts(tmp_path):
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
        assert {('My organization', 'return'), ('mine', 'return')} <= found, found      # other.py


# ---- PEMEL17-4: tuple, list, starred, for and with targets are writes of each element ----------------------

UNPACK = '''
import threading


class Pair:
    def __init__(self, other):
        self.left, self.right = 'l', 1
        [self.top, (self.inner, rest)] = ['t', (None, 2)]
        self.head, *self.tail = 'h', 'x'
        self.first, self.second = other.pair()
        self.alpha, self.beta = 'a', 'b', 'c'
        self.flag, self.none = True, None
        for self.item in other.items:
            pass
        for index, self.slot in enumerate(other.items):
            pass
        with threading.Lock() as self.held, open('f') as (self.stream, self.mode):
            pass
'''


def test_each_element_of_a_tuple_list_starred_for_or_with_target_is_its_own_write(tmp_path):
    (tmp_path / 'pair.py').write_text(textwrap.dedent(UNPACK).lstrip())
    with closing(build(tmp_path)) as graph:
        found = {row['field']: row.get('value', '<none>') for row in graph.writes(by_name=True) if row['file'] == 'pair.py'}
        lines = {row['field']: row['line'] for row in graph.writes(by_name=True)}
    # An element takes its value only from a right side of the same length (none is guessed from `other.pair()`, from
    # three values for two names, or for a starred element); a loop or `as` target has none.
    assert found == {'left': 'l', 'right': 1, 'top': 't', 'inner': None, 'head': 'h', 'tail': '<none>',
                     'first': '<none>', 'second': '<none>', 'alpha': '<none>', 'beta': '<none>', 'flag': True, 'none': None,
                     'item': '<none>', 'slot': '<none>', 'held': '<none>', 'stream': '<none>', 'mode': '<none>'}, found
    assert (lines['left'], lines['item'], lines['slot'], lines['held'], lines['mode']) == (6, 12, 14, 16, 16), lines


def test_a_nested_element_takes_the_value_at_its_place_and_names_rebind_as_single_assignments_do(tmp_path):
    (tmp_path / 'swap.py').write_text(textwrap.dedent('''
        import os
        import json


        class Job:
            def run(self):
                self.state, (self.code, self.note) = 'stop', (0, 'done')
                a, b = os.path, json
                a, b = b, a
                return a.dumps, b.join
    ''').lstrip())
    with closing(build(tmp_path)) as graph:
        values = {row['field']: row.get('value', '<none>') for row in graph.writes('Job.state')
                  + graph.writes('Job.code') + graph.writes('Job.note')}
        resolved = {row['text']: row['resolved'] for row in graph.calls(include_reads=True) if row.get('read')}
    assert values == {'state': 'stop', 'code': 0, 'note': 'done'}, values
    # The right side is read before either name is bound again: `a, b = b, a` swaps the two bindings.
    assert (resolved['a.dumps'], resolved['b.join']) == ('json.dumps', 'os.path.join'), resolved


SETTINGS = '''
from dataclasses import asdict, astuple, dataclass, replace


@dataclass
class Settings:
    appearance: str = "light"
    language: str = "en"

    def __post_init__(self):
        self.appearance = self.appearance.strip()


@dataclass
class Controller:
    settings: Settings


class SettingsDialog:
    def __init__(self):
        self.appearance = "dialog"

    def refresh(self):
        self.reload()
        self._on_done()

    def reload(self):
        return self.appearance


def direct(settings: Settings):
    return settings.appearance


def chained(controller: Controller):
    return controller.settings.appearance


def aliased(controller: Controller):
    settings = controller.settings
    return settings.appearance


def serialized(settings: Settings):
    return asdict(settings), astuple(settings), vars(settings)


def replacement(settings: Settings):
    return replace(settings, appearance="dark")


def named(settings: Settings):
    return getattr(settings, "language")


def dialog_read(dialog: SettingsDialog):
    return dialog.appearance


def untyped(settings, items, other: Settings):
    other = make()
    return settings.appearance, other.appearance, [s.appearance for s in items], (lambda other: other.appearance)


def closure(settings: Settings):
    def inner():
        return settings.appearance
    return inner
'''


def _reads(rows):
    return sorted((row['function'], row['line'], row['model'], row['field'], row['method'], tuple(row.get('except', ())))
                  for row in rows)


def test_python_reads_of_a_field_are_typed_as_writes_type_their_receiver(tmp_path):
    # PYREAD18-2: a read counts through self, an annotated name, a local alias of a typed value and an attribute whose
    # class declares its type; asdict, astuple and vars read every field, replace every field but those it sets.
    (tmp_path / 'settings.py').write_text(textwrap.dedent(SETTINGS).lstrip())
    with closing(build(tmp_path, workers=1)) as graph:
        assert _reads(graph.field_reads('Settings.appearance')) == [
            ('Settings.__post_init__', 10, 'Settings', 'appearance', 'attribute', ()),
            ('aliased', 40, 'Settings', 'appearance', 'attribute', ()),
            ('chained', 35, 'Settings', 'appearance', 'attribute', ()),
            ('closure.inner', 66, 'Settings', 'appearance', 'attribute', ()),
            ('direct', 31, 'Settings', 'appearance', 'attribute', ()),
            ('serialized', 44, 'Settings', '*', 'asdict', ()),
            ('serialized', 44, 'Settings', '*', 'astuple', ()),
            ('serialized', 44, 'Settings', '*', 'vars', ())]
        # replace(settings, appearance=...) builds a new value from every other field: it reads language, not
        # appearance, and writes no field of settings.
        assert ('replacement', 48, 'Settings', '*', 'replace', ('appearance',)) in _reads(graph.field_reads('Settings.language'))
        assert ('named', 52, 'Settings', 'language', 'getattr', ()) in _reads(graph.field_reads('Settings.language'))
        assert not [row for row in graph.writes() if row['function'] == 'replacement']
        # Class identity follows the annotation: the dialog's field is another field of the same name.
        assert _reads(graph.field_reads('SettingsDialog.appearance')) == [
            ('SettingsDialog.reload', 27, 'SettingsDialog', 'appearance', 'attribute', ()),
            ('dialog_read', 56, 'SettingsDialog', 'appearance', 'attribute', ())]
        # A method the class holds called through self is a call; a callable attribute it does not hold is read to call it.
        assert _reads(graph.field_reads('SettingsDialog.reload')) == []
        assert _reads(graph.field_reads('SettingsDialog._on_done')) == [
            ('SettingsDialog.refresh', 24, 'SettingsDialog', '_on_done', 'call', ())]
        # No untyped name-only reader: an unannotated parameter, an annotated name bound again to an untyped value, a
        # comprehension's target and a lambda's parameter.
        assert not [row for row in graph.field_reads() if row['function'] == 'untyped']
