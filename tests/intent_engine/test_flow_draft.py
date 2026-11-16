"""An observed path does not assert a requirement; finite models exhaust their real domain."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import uuid

import pytest

from flowguard.intent.anchors import collect_sources
from flowguard.intent.flow import Capture, Flow, Node, Transition, check_flow, finite_check, validate


def project(tmp_path, body):
    module = 'draft_app_' + uuid.uuid4().hex
    path = tmp_path / (module + '.py')
    path.write_text(body)
    index = collect_sources(tmp_path, [(path.name, module)])
    spec = importlib.util.spec_from_file_location(module, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[module] = obj
    spec.loader.exec_module(obj)
    return index, obj


def large_model(tmp_path):
    values = ' | '.join(str(n) for n in range(65))
    body = f'''# flowguard: states Counter.a = {values}
# flowguard: states Counter.b = {values}
class Counter:
    a = 0
    b = 0
# flowguard: event A()
def a(): pass
# flowguard: event B()
def b(): pass
'''
    index, _ = project(tmp_path, body)
    transitions = tuple(Transition('Counter.' + state, n, (n + 1) % 65, node, initial=n == 0)
                        for state, node in [('a', 'A'), ('b', 'B')] for n in range(65))
    model = Flow('COUNTERS', 'assumed: test finite domain',
                 (Node('a', 'A', start=True, end=True), Node('b', 'B', end=True)),
                 (('a', 'a'), ('a', 'b'), ('b', 'a'), ('b', 'b')),
                 tuple(replace(t, on=t.on.lower()) for t in transitions))
    return index, model


def test_default_exhaustion_crosses_4096_and_deduplicates_cycles(tmp_path):
    index, model = large_model(tmp_path)
    result = finite_check(model, index)
    assert result['verdict'] == 'ok', result
    assert result['exhausted'] and result['states'] == 2 * 65 * 65
    assert result['reachable'] == ['a', 'b']


def test_only_an_explicit_debug_limit_truncates_and_stays_grey(tmp_path):
    index, model = large_model(tmp_path)
    result = finite_check(model, index, max_states=1000)
    assert result['verdict'] == 'grey' and not result['red'], result
    assert result['states'] == 1000 and not result['exhausted']
    assert any('not exhausted' in why for why in result['grey'])


def test_debug_truncation_does_not_invent_an_unreachable_final_node(tmp_path):
    index, _ = project(tmp_path, '# flowguard: event A()\ndef a(): pass\n')
    model = Flow('CHAIN', 'assumed: chain', tuple(Node(str(n), 'A') for n in range(4)),
                 tuple((str(n), str(n + 1)) for n in range(3)))
    result = finite_check(model, index, max_states=3)
    assert result['verdict'] == 'grey' and not result['red'], result
    assert result['states'] == 3 and not result['exhausted']
    complete = finite_check(model, index)
    assert complete['verdict'] == 'ok' and complete['states'] == 4


@pytest.mark.parametrize('limit', [0, -1, True, 1.5])
def test_debug_limit_rejects_invalid_values_instead_of_claiming_exhaustion(tmp_path, limit):
    index, _ = project(tmp_path, '# flowguard: event A()\ndef a(): pass\n')
    with pytest.raises(ValueError, match='positive integer'):
        finite_check(Flow('ONE', 'assumed: one', ('A',), ()), index, max_states=limit)


BODY = '''# flowguard: event ENTRY(value: int)
def entry(value: int):
    save(value)
    return publish(value)
# flowguard: event SAVED(value: int)
def save(value: int): return value
# flowguard: event PUBLISHED(value: int)
def publish(value: int): return value
'''


def recorded(tmp_path):
    index, obj = project(tmp_path, BODY)
    with Capture(tmp_path, index, 'ordinary') as captured:
        obj.entry(3)
    return index, captured.events


# The path `entry(3)` takes, call and completion phases in the order they happened, as a Flow whose source is an
# assumption (an observation is no requirement).
OBSERVED = [('ENTRY', 'call'), ('SAVED', 'call'), ('SAVED', 'return'), ('PUBLISHED', 'call'), ('PUBLISHED', 'return'),
            ('ENTRY', 'return')]


def observed_flow(name, steps=OBSERVED, extra=()):
    nodes = tuple(Node(f'n{number}', anchor, phase=phase, start=number == 1, end=number == len(steps))
                  for number, (anchor, phase) in enumerate(steps, 1))
    return Flow(name, 'assumed: observed paths only; confirm required paths and relations', nodes,
                (*((f'n{number}', f'n{number + 1}') for number in range(1, len(steps))), *extra))


def test_a_flow_of_the_observed_path_holds_and_an_unwalked_edge_stays_grey(tmp_path):
    index, events = recorded(tmp_path)
    model = observed_flow('PUBLISH')
    result = check_flow(model, index, events)
    assert result['verdict'] == 'ok', result
    assert result['runtime']['observed_edges'] == list(model.edges)
    extended = observed_flow('PUBLISH', extra=[('n1', 'n4')])
    result = check_flow(extended, index, events)
    assert result['verdict'] == 'grey' and not result['red'], result
    assert any('unobserved edge' in why for why in result['grey'])


def test_missing_source_identity_is_not_silently_licensed(tmp_path):
    index, events = recorded(tmp_path)
    events = [replace(e, source_digest='') for e in events]
    result = check_flow(observed_flow('UNVERIFIED'), index, events)
    assert result['verdict'] == 'grey' and not result['red'], result


def test_large_observed_layer_is_preserved_and_requests_hierarchy(tmp_path):
    body = ''.join(f'# flowguard: event E{n}()\ndef e{n}(): pass\n' for n in range(6))
    index, obj = project(tmp_path, body)
    with Capture(tmp_path, index, 'ordinary') as captured:
        for n in range(6):
            getattr(obj, f'e{n}')()
    model = observed_flow('LARGE', [(f'E{n}', phase) for n in range(6) for phase in ('call', 'return')])
    assert len(model.nodes) == 12
    checked = validate(model, index)
    assert any('10' in why and 'split' in why for why in [*checked['red'], *checked['grey'], *checked['info']]), checked
    assert check_flow(model, index, captured.events)['verdict'] == 'ok'


def test_existing_engine_keeps_an_observed_flow_grey_until_its_requirement_is_sourced(tmp_path):
    import importlib
    from flowguard.intent.engine import Engine
    from flowguard.intent.loader import load
    name = 'draft_engine_' + uuid.uuid4().hex
    path = tmp_path / (name + '.py')
    path.write_text(BODY)
    index = collect_sources(tmp_path, [(path.name, name)])
    model = load(root=tmp_path)  # Source verification precedes ordinary project imports.
    obj = importlib.import_module(name)
    with Capture(tmp_path, index, 'ordinary') as captured:
        obj.entry(3)
    observed = observed_flow('PUBLISH')
    model.anchor_index = index
    model.flows[observed.id] = observed
    result = Engine(model).run_flow(observed, captured.events)
    assert result['verdict'] == 'grey' and not result['red'], result
    assert any(why.startswith('assumed') for why in result['grey'])
