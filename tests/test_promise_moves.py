"""Moving a model's bindings and state preserves their declared guarantees."""
import ast

import pytest

from flowguard.map.facets import model_promises, promise_changes


def record(root, identifier, *, fields=(), tests=None, rules=("safe",)):
    fields = fields or ("unchanged",)
    source = f'''from dataclasses import dataclass
from flowguard import Invariant, Workflow
from flowguard.explorer import Explorer
MODEL_ID = {identifier!r}
PARENT = "group"
TESTED_BY = {tests or {}!r}
@dataclass(frozen=True)
class State:
''' + ''.join(f'    {name}: str = ""\n' for name in fields) + '''
class Step:
    name = "Step"
    def apply(self, value, state): return ()
def build_explorer():
    return Explorer(Workflow((Step(),)), (State(),), (), invariants=(
''' + ''.join(f'        Invariant({name!r}, "holds", lambda s, t: True),\n' for name in rules) + '''    ))
def broken_variants(): return {"bad": build_explorer()}
'''
    return model_promises(root, f'.flowguard/models/{identifier}.py', ast.parse(source))


@pytest.mark.parametrize('donor,receiver', [('original', 'separate'), ('separate', 'original')])
def test_split_preserves_relocated_test_file_and_state(root_path, donor, receiver):
    before = {donor: record(root_path, donor, fields=('kept', 'moved_value'),
                           tests={'safe': ['tests/test_original.py:test_value']})}
    after = {donor: record(root_path, donor, fields=('kept',), rules=()),
             receiver: record(root_path, receiver, fields=('moved_value',),
                              tests={'safe': ['tests/test_separate.py:test_value']})}
    lines, warnings = promise_changes(before, after, {donor, receiver})
    assert not warnings
    move = next(line for line in lines if f'from {donor} to {receiver}' in line)
    assert '1 test(s)' in move and 'moved_value' in move


def test_true_deletion_still_reports_test_and_state(root_path):
    before = {'original': record(root_path, 'original', fields=('kept', 'lost'),
                                 tests={'safe': ['tests/test_original.py:test_value']})}
    after = {'original': record(root_path, 'original', fields=('kept',))}
    _, warnings = promise_changes(before, after, {'original'})
    assert {row['message'] for row in warnings} == {'-test safe', '-field lost'}


@pytest.mark.parametrize('binding', ['safe', 'other'])
def test_relocation_does_not_hide_changed_parameter_or_binding(root_path, binding):
    before = {'original': record(root_path, 'original',
                                 tests={'safe': ['tests/test_original.py:test_value[one]']})}
    after = {'original': record(root_path, 'original', tests={}),
             'separate': record(root_path, 'separate',
                                tests={binding: ['tests/test_separate.py:test_value[two]' if binding == 'safe'
                                                 else 'tests/test_separate.py:test_value[one]']})}
    _, warnings = promise_changes(before, after, after)
    assert any(row['component'] == 'original' and row['message'] == '-test safe' for row in warnings)


def test_ambiguous_receivers_do_not_hide_a_removed_test(root_path):
    before = {'original': record(root_path, 'original', tests={'safe': ['tests/test_old.py:test_value']})}
    after = {'original': record(root_path, 'original'),
             **{name: record(root_path, name, tests={'safe': [f'tests/test_{name}.py:test_value']})
                for name in ('first', 'second')}}
    _, warnings = promise_changes(before, after, after)
    assert any(row['component'] == 'original' and row['message'] == '-test safe' for row in warnings)


def test_a_preexisting_unrelated_field_is_not_a_transfer(root_path):
    before = {'original': record(root_path, 'original', fields=('kept', 'lost')),
              'other': record(root_path, 'other', fields=('lost',))}
    after = {'original': record(root_path, 'original', fields=('kept',)), 'other': before['other']}
    _, warnings = promise_changes(before, after, after)
    assert any(row['component'] == 'original' and row['message'] == '-field lost' for row in warnings)


def test_ambiguous_donors_do_not_hide_removed_test_bindings(root_path):
    before = {name: record(root_path, name, tests={'safe': [f'tests/test_{name}.py:test_value']})
              for name in ('first', 'second')}
    after = {name: record(root_path, name) for name in before}
    after['receiver'] = record(root_path, 'receiver', tests={'safe': ['tests/test_receiver.py:test_value']})
    _, warnings = promise_changes(before, after, after)
    assert {row['component'] for row in warnings if row['message'] == '-test safe'} == {'first', 'second'}


def test_ambiguous_field_receivers_do_not_hide_a_removed_field(root_path):
    before = {'original': record(root_path, 'original', fields=('kept', 'lost'))}
    after = {'original': record(root_path, 'original', fields=('kept',)),
             **{name: record(root_path, name, fields=('lost',)) for name in ('first', 'second')}}
    _, warnings = promise_changes(before, after, after)
    assert any(row['component'] == 'original' and row['message'] == '-field lost' for row in warnings)


def test_same_method_leaf_in_another_class_is_not_a_binding_move(root_path):
    before = {'original': record(root_path, 'original',
                                 tests={'safe': ['tests/test_old.py:TestOriginal.test_value']})}
    after = {'original': record(root_path, 'original'),
             'receiver': record(root_path, 'receiver',
                                tests={'safe': ['tests/test_new.py:TestOther.test_value']})}
    _, warnings = promise_changes(before, after, after)
    assert any(row['component'] == 'original' and row['message'] == '-test safe' for row in warnings)


def test_removed_owner_reports_only_the_field_not_received_elsewhere(root_path):
    before = {'original': record(root_path, 'original', fields=('moved', 'lost'),
                                 tests={'safe': ['tests/test_old.py:test_value']})}
    after = {'receiver': record(root_path, 'receiver', fields=('moved',),
                                tests={'safe': ['tests/test_new.py:test_value']})}
    lines, warnings = promise_changes(before, after, before.keys() | after.keys())
    assert {row['message'] for row in warnings} == {'-field lost'}
    assert any('1 field(s): moved' in line and '1 test(s)' in line for line in lines)


@pytest.fixture
def root_path(tmp_path):
    return tmp_path
