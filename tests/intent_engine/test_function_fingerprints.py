"""A reuse identity follows real source dependencies without importing code."""
from contextlib import closing

from flowguard.intent import deps
from flowguard.structure import build


def snapshot(root):
    with closing(build(root)) as graph:
        return deps.function_fingerprints(graph, ['owner:accept'])


def test_reached_helper_and_constant_changes_change_the_function_closure(tmp_path):
    owner = tmp_path / 'owner.py'
    helper = tmp_path / 'helper.py'
    owner.write_text('from helper import cutoff\ndef accept(x): return cutoff(x)\n')
    helper.write_text('LIMIT=3\ndef cutoff(x): return x <= LIMIT\n')
    before = snapshot(tmp_path)
    assert {'accept'} <= before['owner.py'].keys()
    assert {'cutoff', 'LIMIT'} <= before['helper.py'].keys()
    helper.write_text(helper.read_text().replace('LIMIT=3', 'LIMIT=4'))
    assert snapshot(tmp_path) != before
    helper.write_text('LIMIT=3\ndef cutoff(x): return x < LIMIT\n')
    assert snapshot(tmp_path) != before


def test_unrelated_body_and_whitespace_do_not_change_the_closure(tmp_path):
    owner = tmp_path / 'owner.py'
    owner.write_text('def accept(x): return x <= 3\ndef unused(x): return x + 1\n')
    before = snapshot(tmp_path)
    owner.write_text('def accept(x):\n    # formatting is not a behavior change\n    return x <= 3\n\ndef unused(x): return x + 99\n')
    assert snapshot(tmp_path) == before


def test_source_closure_includes_a_callee_on_an_unexecuted_branch(tmp_path):
    owner = tmp_path / 'owner.py'
    owner.write_text('def branch(x): return x > 3\ndef accept(x): return True if x == 0 else branch(x)\n')
    before = snapshot(tmp_path)
    assert 'branch' in before['owner.py']
    owner.write_text(owner.read_text().replace('x > 3', 'x >= 3'))
    assert snapshot(tmp_path) != before
