"""Public footprints do not need to own transient execution code."""
import ast
import gc
from pathlib import Path
import types
import weakref

import pytest

from flowguard.intent import loader, sites
from flowguard.intent.tracer import Footprint


def public(footprint):
    return {name: sorted(getattr(footprint, name), key=repr)
            for name in ('entered', 'edges', 'call_lines')} | {'keys': sorted(footprint.keys())}


def intercepted_sequence(nested=False, fail=False):
    fn = loader.is_literal
    original = fn.__code__
    footprint = Footprint(lambda filename: filename == original.co_filename)
    refs, outcomes = [], []

    def forward(function, bound):
        value = function(*bound.args, **bound.kwargs)
        if fail:
            raise ValueError('native callback failure')
        return value

    def once():
        try:
            with sites.intercepted(fn, forward):
                refs.append(weakref.ref(fn.__code__))
                outcomes.append(fn(ast.Constant(1)))
        except ValueError as error:
            assert str(error) == 'native callback failure'
            outcomes.append('raise: native callback failure')
        assert fn.__code__ is original

    with footprint:
        for index in range(8):
            if nested and index == 4:
                with footprint:
                    once()
            else:
                once()
            gc.collect()
        before = public(footprint)
        alive_during = sum(ref() is not None for ref in refs)
    gc.collect()
    assert public(footprint) == before
    assert len(outcomes) == 8 and all(v == outcomes[0] for v in outcomes)
    return {'public': before, 'outcomes': outcomes, 'alive_during': alive_during,
            'alive_after': sum(ref() is not None for ref in refs)}


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('fail', [False, True])
def test_finished_interceptors_are_not_kept_by_an_active_footprint(nested, fail):
    result = intercepted_sequence(nested, fail)
    assert result['public']['entered']
    assert result['alive_during'] == result['alive_after'] == 0


def test_shared_generator_records_each_actual_resumer_edge(tmp_path):
    path = tmp_path / 'resumers.py'
    path.write_text('def leaf(): return 7\n'
                    'def first(): return next(stream)\n'
                    'def second(): return next(stream)\n'
                    'stream = (leaf() for _ in range(2))\n')
    module = types.ModuleType('resumers')
    exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
    with Footprint(lambda filename: filename == str(path)) as outer:
        assert module.first() == 7
        with Footprint(lambda filename: filename == str(path)) as inner:
            assert module.second() == 7
    edges = {(source[2], target[2]) for source, target in outer.edges}
    assert {('first', 'leaf'), ('second', 'leaf')} <= edges
    assert ('second', 'leaf') in {(source[2], target[2]) for source, target in inner.edges}


def test_replaced_function_code_keeps_each_real_callee(tmp_path):
    path = tmp_path / 'dynamic.py'
    path.write_text('def target(): return 0\n' + ''.join(
        f'def leaf_{number}(): return {number}\n' for number in range(8)))
    module = types.ModuleType('dynamic')
    exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
    old = module.target.__code__
    with Footprint(lambda filename: filename == str(path)) as footprint:
        try:
            for number in range(8):
                namespace = {}
                exec(compile(f'def target(): return leaf_{number}()\n', str(path), 'exec'), namespace)
                module.target.__code__ = namespace['target'].__code__
                assert module.target() == number
        finally:
            module.target.__code__ = old
    edges = {(source[2], target[2]) for source, target in footprint.edges}
    assert {('target', f'leaf_{number}') for number in range(8)} <= edges
