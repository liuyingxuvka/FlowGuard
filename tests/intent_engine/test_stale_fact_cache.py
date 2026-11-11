"""Reusing static old-value facts never reuses a finding or eagerly reads a reference."""
import ast
from contextlib import closing
from decimal import Decimal
import json

import pytest

from flowguard.intent import signals
from flowguard.structure import build


def change(before, *, target='', identity=''):
    return dict(before=before, after='new', target=target, identity=identity, file='policy.py', line=1)


def targets(report):
    assert report['total'] == len(report['locations'])
    return {row['target'] for row in report['locations']}


@pytest.mark.parametrize('encoded, old', [('7', 7), ('not JSON[', 'not JSON[')])
def test_direct_members_are_reused_and_bad_indices_stay_lazy(tmp_path, monkeypatch, encoded, old):
    (tmp_path / 'policy.py').write_text('LIMITS = [99]\ndef first(x): return x <= 7\ndef second(x): return x <= 7\n')
    with closing(build(tmp_path)) as graph:
        graph.con.execute('UPDATE site SET value=? WHERE node IN (?, ?)', (encoded, 'policy:first', 'policy:second'))
        graph.con.execute('UPDATE site SET identity=? WHERE node=?', ('policy:LIMITS[broken(]', 'policy:first'))
        decoded, evaluated = [], []
        load, literal = json.loads, ast.literal_eval

        def record_load(value, *args, **kwargs):
            if type(value) is str and value == encoded:
                decoded.append(value)
            return load(value, *args, **kwargs)

        def record_literal(value):
            if type(value) is str:
                evaluated.append(value)
            return literal(value)

        monkeypatch.setattr(json, 'loads', record_load)
        monkeypatch.setattr(ast, 'literal_eval', record_literal)
        assert targets(signals.stale_copies(graph, [change(old)])) == {'policy:first', 'policy:second'}
        assert 'broken(' not in evaluated
        assert signals.stale_copies(graph, [change(8)])['total'] == 0
        assert signals.stale_copies(graph, [change(9)])['total'] == 0
        assert targets(signals.stale_copies(graph, [change(old)])) == {'policy:first', 'policy:second'}
        assert decoded == [encoded]
        assert evaluated.count('broken(') == 1


def test_member_reuse_preserves_boolean_string_and_decimal_identity(tmp_path):
    (tmp_path / 'policy.py').write_text('''BAG = (True, "7", 7.0)
def numeric(x): return x == 7
def text(x): return x == "7"
def boolean(x): return x == True
def bag(x): return x in BAG
''')
    with closing(build(tmp_path)) as graph:
        assert targets(signals.stale_copies(graph, [change(Decimal('7.0'))])) == {'policy:numeric', 'policy:bag'}
        assert targets(signals.stale_copies(graph, [change('7')])) == {'policy:text', 'policy:bag'}
        assert signals.stale_copies(graph, [change(True)])['total'] == 0
        assert targets(signals.stale_copies(graph, [change(Decimal('7.00'))])) == {'policy:numeric', 'policy:bag'}


def test_refresh_discards_direct_and_selected_constant_members(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text('LIMITS = (7,)\ndef first(x): return x <= LIMITS[0]\n')
    with closing(build(tmp_path)) as graph:
        assert signals.stale_copies(graph, [change(6)])['total'] == 0
        assert targets(signals.stale_copies(graph, [change(7)])) == {'policy:first'}
        path.write_text('LIMITS = (99,)\ndef first(x): return x <= LIMITS[0]\n')
        graph.refresh()
        assert signals.stale_copies(graph, [change(7)])['total'] == 0
        assert targets(signals.stale_copies(graph, [change(99)])) == {'policy:first'}


def test_each_old_value_and_target_is_checked_again_after_fact_reuse(tmp_path):
    (tmp_path / 'policy.py').write_text('def first(x): return x <= 7\ndef second(x): return x <= 7\ndef third(x): return x <= 8\n')
    with closing(build(tmp_path)) as graph:
        assert targets(signals.stale_copies(graph, [change(7, target='policy:first')])) == {'policy:second'}
        assert targets(signals.stale_copies(graph, [change(7, target='policy:second')])) == {'policy:first'}
        assert targets(signals.stale_copies(graph, [change(8, target='policy:first')])) == {'policy:third'}
        graph.reset_query_coverage()
        assert targets(signals.stale_copies(graph, [change(7, target='policy:first')])) == {'policy:second'}
        assert graph.query_coverage()['queried'] == ['literals']


class Numeric(str):
    """A str subclass equal() reads as a number, never as text."""


OLD_VALUES = [7, 7.0, Decimal('7.000'), '7', 'seven', True, False, None, float('nan'), float('inf'), -0.0, 0,
              10 ** 5000, Numeric('7'), (7,), 99, 'not JSON[', 3.5]


def test_indexed_reads_find_what_a_first_full_read_finds_for_every_old_value(tmp_path):
    (tmp_path / 'policy.py').write_text('''LIMITS = (7, 99)
NAMES = {"a": "seven", "b": 3.5}
def numeric(x): return x <= 7
def floating(x): return x == 3.5
def zero(x): return x == 0
def text(x): return x == "seven"
def quoted(x): return x == "7"
def member(x): return x in (7, "seven", 99)
def limit(x): return x <= LIMITS[1]
def named(x): return x == NAMES["b"]
def boolean(x): return x is True
def infinite(x): return x < float("inf")
''')
    with closing(build(tmp_path)) as warm:
        # The same graph answers every old value in turn: after its first read most sites are indexed.
        reused = [signals.stale_copies(warm, [change(old)]) for old in OLD_VALUES]
    for old, report in zip(OLD_VALUES, reused):
        with closing(build(tmp_path)) as fresh:
            # A fresh graph's first read visits every site, as the scan without an index did.
            assert report == signals.stale_copies(fresh, [change(old)]), old
    assert targets(reused[0]) == {'policy:numeric', 'policy:member'}
    assert targets(reused[OLD_VALUES.index(99)]) == {'policy:member', 'policy:limit'}
    assert reused[OLD_VALUES.index(10 ** 5000)]['total'] == 0
