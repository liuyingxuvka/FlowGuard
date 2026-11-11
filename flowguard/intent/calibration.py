"""Calibrated observations from the calls a test made in the one ordinary pytest session.

There is no transport, collector or test runner here, and no test runs again (design 4.5, 8): the
pytest integration supplies its real items, the runtime's recorded calls and the anchor events of the
ordinary run. A calibrated point is the named test's recorded JSON call with the requested inputs put
in place, evaluated in the sealed environment.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
import inspect
from pathlib import Path

from . import sites
from .cells import Raised
from .runtime import _PRIVATE, outcome_equal

_FACTS = ContextVar('flowguard_calibration_facts', default=None)
_CURRENT = ContextVar('flowguard_calibration_session', default=None)


class _Unavailable(ValueError):
    pass


@dataclass
class _Session:
    runtime: object
    items: tuple
    nextitem: object = None
    events: list = ()           # the anchor events the ordinary tests recorded


@contextmanager
def session(runtime, items, *, nextitem=None, events=()):
    """The real pytest plugin supplies its existing Runtime, collected items and recorded events."""
    token = _CURRENT.set(_Session(runtime, tuple(items), nextitem, events))
    try:
        with _execution_session(runtime.root):
            yield
    finally:
        _CURRENT.reset(token)


@contextmanager
def _execution_session(root, *, facts=None):
    root = Path(root).resolve()
    current = _FACTS.get()
    if current is not None and current[0] == root:
        yield
        return
    token = _FACTS.set((root, {} if facts is None else facts))
    try:
        yield
    finally:
        _FACTS.reset(token)


def probe_context(config):
    scope = _CURRENT.get()
    return bool(scope and _PRIVATE.get() and any(item.config is config for item in scope.items))


def _unavailable(reason, *, status='grey'):
    return dict(status=status, reasons=[reason])


def _context(root, selector):
    scope = _CURRENT.get()
    if scope is None or scope.runtime.root != Path(root).resolve():
        raise ValueError('calibrated observation needs the existing collected pytest session')
    import pytest
    file, separator, selected = selector.partition('::')
    expected = (Path(root) / file).resolve()
    if not separator or not expected.is_relative_to(Path(root).resolve()):
        raise ValueError('calibration test does not belong to the indexed project source')
    matches = []
    for item in scope.items:
        module = item.getparent(pytest.Module)
        if module is None or Path(item.path).resolve() != expected:
            continue
        prefix = module.nodeid + '::'
        if item.nodeid.startswith(prefix) and item.nodeid[len(prefix):] == selected:
            matches.append(item)
    if len(matches) != 1:
        raise ValueError('calibration must name exactly one collected test, including its parameter id')
    item = matches[0]
    return scope, item


def _observation(status, anchor, value=None, reasons=(), *, check_type=True):
    from .anchors import Observation, _accepts
    if check_type and status == 'ok' and anchor.output_type and not isinstance(value, Raised):
        try:
            accepted = _accepts(anchor.output_type, value)
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return Observation('grey', value, ('declared return type is not supported for observation',), anchor.target)
        if not accepted:
            return Observation('red', value, ('actual return does not match the anchor return type',), anchor.target)
    return Observation(status, value, tuple(reasons), anchor.target)


def _result(anchor, result, *, check_type=True):
    return _observation(result['status'], anchor, result.get('outcome'), result.get('reasons', ()), check_type=check_type)


def _values(anchor, values):
    from .anchors import _accepts
    names = {parameter.name: parameter for parameter in anchor.parameters}
    if set(values) - names.keys():
        return _unavailable('values name undeclared anchor parameters', status='red')
    for name, value in values.items():
        parameter = names[name]
        if getattr(parameter, 'role', 'input') == 'context' and not getattr(parameter, 'inferred', False):
            return _unavailable(name + ': context is supplied by the real test and cannot be replaced', status='red')
        try:
            accepted = _accepts(parameter.source_type, value)
        except (ValueError, SyntaxError, TypeError, AttributeError):
            continue
        if not accepted:
            return _unavailable(name + ': input does not have its source parameter type', status='red')
    return None


def _value_in_context(anchor, original, name, incoming, actual):
    if not isinstance(incoming, Enum):
        return incoming
    parameter = next(p for p in anchor.parameters if p.name == name)
    expression = ast.parse(parameter.source_type, mode='eval').body
    names = []
    while isinstance(expression, ast.Attribute):
        names.append(expression.attr)
        expression = expression.value
    native = original.__globals__.get(expression.id) if isinstance(expression, ast.Name) else None
    for part in reversed(names):
        native = vars(native).get(part) if inspect.ismodule(native) else None
    if type(actual) is not native or type(incoming) is not native:
        raise _Unavailable('enum parameter has no matching actual source type')
    members, by_value = vars(native).get('_member_map_', {}), vars(native).get('_value2member_map_', {})
    for value in (actual, incoming):
        name, raw = inspect.getattr_static(value, '_name_', None), inspect.getattr_static(value, '_value_', None)
        try:
            valid = type(name) is str and members.get(name) is value and by_value.get(raw) is value
        except TypeError:
            valid = False
        if not valid:
            raise _Unavailable('enum parameter is not a real member of its source enum type')
    return incoming


def _recorded(scope, item, function):
    """The one reading of `function` the named test's ordinary run recorded, or why there is none."""
    target = function.__module__ + ':' + function.__qualname__
    found = [reading for reading in scope.runtime.readings if reading.target == target and item.nodeid in reading.tests]
    if not found:
        if item.nodeid not in scope.runtime.ran:
            return _unavailable('not compared: the named test did not run in this session')
        if scope.runtime.full(function):
            return _unavailable('not compared: the named test\'s call was not recorded; '
                                '20 distinct inputs were recorded before it ran')
    if len(found) != 1:
        return _passed(scope, item) or _unavailable('test must reach the actual anchor exactly once; '
                                                     'target may be absent or ambiguous')
    reading = found[0]
    actual = reading.actual[1] if reading.actual is not None else None
    if isinstance(actual, Raised) and not isinstance(actual.error, Exception):
        return _unavailable('not compared: the named test\'s call ended with ' + type(actual.error).__name__)
    if reading.actual is None or reading.sample is None:
        return _unavailable('not compared: ' + ('; '.join(reading.reasons) or 'actual calibration call has no JSON reading'))
    return reading


def _passed(scope, item, refusal=None):
    """None when the named test's ordinary run passed (or failed only by raising `refusal`, the declared
    outcome it observed), else the red that its real run did not pass."""
    failed = scope.runtime.outcomes.get(item.nodeid, ())
    if not failed or (refusal is not None and len(failed) == 1 and failed[0][:2] == ('call', 'failed')
                      and failed[0][2] is refusal.error):
        return None
    return _unavailable('real calibration test did not pass completely: '
                        + ', '.join(when + ' ' + outcome for when, outcome, _ in failed), status='red')


def _sensor(root, anchor, values):
    from .anchors import _source, parameter_kind
    issue = _values(anchor, values)
    if issue:
        return issue
    try:
        _source(root, anchor)
        scope, item = _context(root, anchor.calibrated_by)
        function = sites.unwrap(sites.resolve_loaded(anchor.target))
        if (not inspect.isfunction(function) or Path(function.__code__.co_filename).resolve() != (Path(root) / anchor.file).resolve()
                or function.__qualname__.replace('.<locals>.', '.') != anchor.qual):
            return _unavailable('loaded function does not match the actual source anchor')
        if _instrumented((anchor.target,)):
            return _unavailable('calibration cannot replace installed code instrumentation with source execution')
        reason = scope.runtime.safety(function)        # a source the sealed environment cannot run is never compared
        if reason:
            return _unavailable(reason)
        reading = _recorded(scope, item, function)
        if isinstance(reading, dict):
            return reading
        if anchor.fields and (reading.fields is None or reading.field_reasons):
            return _unavailable('; '.join(reading.field_reasons) or 'actual calibration fields are unavailable')
        signature = inspect.signature(function, follow_wrapped=False)
        bound = inspect.BoundArguments(signature, dict(reading.sample['inputs']))
        expected, reason = scope.runtime.guarded(function, bound)
        if reason:
            return _unavailable(reason)
        actual = reading.actual[1]
        # A raised exception agrees by its type and message, as the sealed environment reports it.
        agrees = outcome_equal(actual, expected) if isinstance(actual, Raised) else \
            not isinstance(expected, Raised) and outcome_equal(reading.json_result, expected)
        if not agrees:
            return _unavailable('actual named-test outcome differs from the sealed source outcome')
        if failed := _passed(scope, item):
            return failed
        from .tracer import recorded_entry
        recorded_entry(function.__code__)           # the named test's recorded call entered the anchor
        if not values:
            return dict(status='ok', outcome=expected)
        # The named test's own call is the context; only the requested inputs take other values.
        requested = inspect.BoundArguments(signature, dict(bound.arguments))
        for parameter in anchor.parameters:
            if parameter.name not in values:
                continue
            if parameter.source not in requested.arguments:
                return _unavailable(parameter.name + ': not an argument of the named test\'s call')
            if parameter_kind(parameter, requested.arguments[parameter.source]) is None:
                return _unavailable(parameter.name + ': actual test context cannot be replaced')
            requested.arguments[parameter.source] = values[parameter.name]
        outcome, reason = scope.runtime.guarded(function, requested)
        if reason:
            return _unavailable(reason)
        return dict(status='ok', outcome=outcome)
    except (OSError, ValueError, TypeError, SyntaxError, AttributeError, sites.NotMutable) as error:
        return _unavailable(str(error))


def _identity():
    scope = _CURRENT.get()
    return id(scope.runtime) if scope else None


def _instrumented(targets):
    for target in targets:
        try:
            function = sites.resolve_loaded(target)
            if sites.installed_origin(function) is not None and not sites.is_transport(function.__code__):
                return True
        except (AttributeError, sites.NotMutable):
            continue
    return False


def _key(anchor):
    return ('sensor', _identity(), anchor.target, anchor.source_digest, anchor.calibrated_by)


def _facts(root):
    facts = _FACTS.get()
    return facts[1] if facts is not None and facts[0] == Path(root).resolve() else None


def _prepare(root, anchor, *, _reuse=True):
    if anchor.issues:
        return dict(status=anchor.status, reasons=[issue.message for issue in anchor.issues])
    facts = _facts(root)
    key = _key(anchor)
    if _reuse and facts is not None and key in facts and facts[key]['status'] == 'ok':
        return facts[key]
    if _instrumented((anchor.target,)):
        return _unavailable('calibration must be prepared before code instrumentation')
    baseline = _sensor(root, anchor, {})
    result = dict(status='ok') if baseline['status'] == 'ok' else baseline
    # A red or grey preparation keeps its own verdict and reason for this session.
    if _reuse and facts is not None:
        facts[key] = result
    return result


def _observe_current(root, anchor, values):
    facts = _FACTS.get()
    if facts is None or facts[0] != Path(root).resolve() or _key(anchor) not in facts[1]:
        return _observation('grey', anchor, reasons=('calibrated anchor must be prepared in the real pytest session',))
    prepared = facts[1][_key(anchor)]
    if prepared['status'] != 'ok':
        from .anchors import _source
        try:
            _source(root, anchor)
        except (OSError, ValueError, SyntaxError) as error:
            return _result(anchor, _unavailable(str(error)))
        return _result(anchor, prepared)
    return _result(anchor, _sensor(root, anchor, values))


def execute(root, anchor, values):
    if anchor.calibrated_by:
        with _execution_session(root):
            prepared = _prepare(root, anchor)
            return _result(anchor, _sensor(root, anchor, values) if prepared['status'] == 'ok' else prepared)
    from .anchors import _execution_session as anchor_session, _observe_current as observe
    with anchor_session(root):
        return observe(root, anchor, values)


def execute_many(root, requests):
    with _execution_session(root):
        return [execute(root, anchor, values) for anchor, values in requests]


def _rule_id(binding):
    rule = getattr(binding, 'observed_rule', getattr(binding, 'rule', ''))
    return getattr(rule, 'id', rule)


def _tuple_point(value):
    """An inert rule point is not an automatically enumerated tuple domain."""
    from .runtime import _simple
    if type(value) is tuple:
        return all(_tuple_point(item) for item in value)
    return not isinstance(value, Enum) and _simple(value)


def _scenario(root, binding, values):
    """The scenario test's own recorded run: its entry arguments and the production anchor reading the Flow
    projects. A requested input other than the recorded one would need the test to run again, which never
    happens (design 4.5, 8): that point is not compared."""
    from .anchors import _source, _accepts, parameter_kind
    from .flow import relation_observations
    issue = _values(binding.scenario, values)
    if issue:
        return issue
    try:
        _source(root, binding.scenario)
        if binding.scenario.kind != 'event' or binding.scenario.source_role != 'test':
            return _unavailable('scenario must reference a real ordinary-test event', status='red')
        scope, item = _context(root, binding.testnode)
        function = sites.unwrap(item.obj)
        if (Path(function.__code__.co_filename).resolve() != (Path(root) / binding.scenario.file).resolve()
                or function.__qualname__.replace('.<locals>.', '.') != binding.scenario.qual):
            return _unavailable('selected pytest function is not the declared scenario event')
        if _instrumented(set(binding.targets) | set(binding.actual_targets)):
            return _unavailable('the scenario was recorded before code instrumentation; its outcome is not the instrumented code\'s')
        events = [event for event in scope.events if event.case == item.nodeid]
        entries = [event for event in events if event.site == binding.scenario.target and event.phase == 'call']
        if not entries and item.nodeid not in scope.runtime.ran:
            return _unavailable('not compared: the scenario test did not run in this session')
        if len(entries) != 1:
            return _unavailable('scenario must reach exactly one actual pytest entry')
        recorded = entries[0].values
        for name, value in values.items():
            parameter = next(p for p in binding.scenario.parameters if p.name == name)
            actual = recorded.get(name)
            if parameter_kind(parameter, actual) is None and not (
                    parameter.inferred and name in binding.field_map.values()
                    and type(value) is tuple and type(actual) is tuple
                    and _tuple_point(value) and _tuple_point(actual)
                    and _accepts(parameter.source_type, value) and _accepts(parameter.source_type, actual)):
                return _unavailable(name + ': actual test context cannot be replaced')
            _value_in_context(binding.scenario, function, name, value, actual)
            if name not in recorded or not outcome_equal(recorded[name], value):
                shown = repr(recorded[name]) if name in recorded else 'no recorded value'
                return _unavailable(f'not compared: the scenario test ran with {name}={shown}; another input '
                                    'needs the test to run again, which FlowGuard never does')
        projection = relation_observations(binding.flow, events, binding.anchor_index, _rule_id(binding))
        observations = [row for row in projection['observations'] if row['relation_index'] in binding.relation_indices]
        if projection['status'] != 'observed' or len(observations) != 1:
            return _unavailable('; '.join(projection['grey']) or 'scenario has ambiguous actual reading scopes')
        observed = observations[0]
        if observed['sources'].get('$actual', {}).get('site') not in binding.actual_targets:
            return _unavailable('actual reading does not come from a declared production anchor')
        requested = getattr(binding, 'requested_inputs', {field: values[parameter] for field, parameter in binding.field_map.items() if parameter in values})
        for field, value in requested.items():
            if field not in observed['inputs'] or not outcome_equal(observed['inputs'][field], value):
                return _unavailable('actual scenario input did not match ' + field)
        if failed := _passed(scope, item, observed['actual'] if isinstance(observed['actual'], Raised) else None):
            return failed
        from .tracer import recorded_entry
        recorded_entry(sites.unwrap(sites.resolve_loaded(observed['sources']['$actual']['site'])).__code__)
        return dict(status='ok', outcome=observed['actual'], inputs=observed['inputs'], sources=observed['sources'])
    except Exception as error:
        return _unavailable(str(error) if isinstance(error, _Unavailable)
                            else 'scenario verification failed: ' + type(error).__name__ + ': ' + str(error))


def _scenario_key(binding):
    return ('scenario', _identity(), binding.testnode, binding.scenario.source_digest, binding.anchor.target,
            binding.anchor.source_digest, _rule_id(binding), tuple(binding.relation_indices))


def _prepare_scenario(root, binding):
    facts = _facts(root)
    key = _scenario_key(binding)
    if facts is not None and key in facts and facts[key]['status'] == 'ok':
        return facts[key]
    if _instrumented(set(binding.targets) | set(binding.actual_targets)):
        return _unavailable('scenario must be prepared before code instrumentation')
    baseline = _scenario(root, binding, {})
    result = dict(status='ok') if baseline['status'] == 'ok' else baseline
    if facts is not None:
        facts[key] = result
    return result


def _observe_scenario_current(root, binding, values):
    facts = _FACTS.get()
    if facts is None or facts[0] != Path(root).resolve() or _scenario_key(binding) not in facts[1]:
        return _observation('grey', binding.anchor, reasons=('scenario must be prepared in the real pytest session',))
    prepared = facts[1][_scenario_key(binding)]
    if prepared['status'] != 'ok':
        return _result(binding.anchor, prepared, check_type=False)
    return _result(binding.anchor, _scenario(root, binding, values), check_type=False)
