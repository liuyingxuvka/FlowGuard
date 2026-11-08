"""Finite input proof does not require a finite/single-kind output domain."""
import sys
from pathlib import Path

import pytest

from flowguard.intent import anchors as A
from test_anchors import source, session


MIXED = '''# flowguard: sensor unit_labels(expected: 1, observed: 1) -> mismatch: str | bool | None
def compare(expected: str | None, observed: str | None) -> str | bool | None:
    return expected and observed and expected != observed
'''


@pytest.mark.parametrize('expected,observed,result', [
    (None, 'W', None),
    ('', 'W', ''),
    ('W', None, None),
    ('W', '', ''),
    ('W', 'W', False),
    ('W', 'kW', True),
])
def test_actual_mixed_return_keeps_value_and_exact_type(tmp_path, expected, observed, result):
    root, index = source(tmp_path, MIXED)
    with session(root):
        actual = A.observe(root, index.entries[0], {'expected': expected, 'observed': observed})
    assert actual.status == 'ok'
    assert type(actual.value) is type(result) and actual.value == result


def test_actual_return_outside_declared_union_is_red(tmp_path):
    root, index = source(tmp_path, MIXED.replace('return expected and observed and expected != observed', 'return 1'))
    with session(root):
        actual = A.observe(root, index.entries[0], {'expected': 'W', 'observed': 'W'})
    assert actual.status == 'red' and type(actual.value) is int and actual.value == 1


def test_mixed_return_does_not_waive_unknown_call_purity(tmp_path):
    root, index = source(tmp_path, MIXED.replace('return expected and observed and expected != observed', 'return opaque(expected, observed)'))
    with session(root):
        actual = A.observe(root, index.entries[0], {'expected': 'W', 'observed': 'W'})
    assert actual.status == 'grey' and any('opaque' in reason for reason in actual.reasons), actual.reasons
    assert actual.value is None
    loaded = sys.modules[index.entries[0].module]
    assert Path(loaded.__file__).resolve() == root / index.entries[0].file


def test_mixed_return_unknown_helper_never_runs_its_write(tmp_path, monkeypatch):
    prefix = '''CALLS = []
def opaque(expected, observed):
    CALLS.append((expected, observed))
    with open('marker', 'w') as stream:
        stream.write('bad')
    return False
'''
    root, index = source(tmp_path, prefix + MIXED.replace(
        'return expected and observed and expected != observed', 'return opaque(expected, observed)'))
    monkeypatch.chdir(root)
    with session(root):
        actual = A.observe(root, index.entries[0], {'expected': 'W', 'observed': 'W'})
    # A known helper is inspected; its write remains forbidden even though the
    # declared return permits several kinds and no result is guessed.
    assert actual.status == 'grey' and any('possible side effect' in reason for reason in actual.reasons), actual.reasons
    assert actual.value is None
    loaded = sys.modules[index.entries[0].module]
    assert Path(loaded.__file__).resolve() == root / index.entries[0].file
    assert loaded.CALLS == []
    assert not (root / 'marker').exists()


def test_list_input_remains_outside_the_proved_finite_input_kinds(tmp_path):
    root, index = source(tmp_path, '''# flowguard: sensor mixed(values: 1) -> out: str | bool | None
def mixed(values: list[str]) -> str | bool | None: return values and 'present'
''')
    with session(root):
        actual = A.observe(root, index.entries[0], {'values': ['W']})
    assert actual.status == 'grey' and 'source type' in actual.reasons[0]


@pytest.mark.parametrize('active,wanted', [(False, []), (True, ['ready'])])
def test_safely_validated_output_structure_needs_no_cells_kind(tmp_path, active, wanted):
    root, index = source(tmp_path, '''from __future__ import annotations
# flowguard: sensor readiness(active: 1) -> out: list[str]
def readiness(active: bool) -> list[str]: return ['ready'] if active else []
''')
    with session(root):
        actual = A.observe(root, index.entries[0], {'active': active})
    assert actual.status == 'ok' and actual.value == wanted
