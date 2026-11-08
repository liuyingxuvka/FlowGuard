"""Source-bound observations in the one already collected pytest session.

There is no transport, collector or test runner here. The pytest integration
supplies its real items; Runtime owns call replay, events and fixture isolation.
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


@contextmanager
def session(runtime, items, *, nextitem=None):
    """The real pytest plugin supplies its existing Runtime and collected items."""
    token = _CURRENT.set(_Session(runtime, tuple(items), nextitem))
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


def _codes(index):
    codes = []
    for anchor in index.entries:
        if anchor.kind not in {'sensor', 'event'}:
            continue
        try:
            function = sites.unwrap(sites.resolve_loaded(anchor.target))
        except (AttributeError, sites.NotMutable):
            continue
        if inspect.isfunction(function):
            codes.append((function.__code__, anchor.target))
    return codes


def _reports(result, *, refusal=None):
    if not result.get('reports'):
        return _unavailable('; '.join(result.get('reasons', ())) or 'the real test was not replayed')
    unsupported = [error for _, error in result.get('errors', ()) if isinstance(error, _Unavailable)]
    if unsupported:
        return _unavailable('; '.join(str(error) for error in unsupported))
    failures = [report for report in result['reports'] if not report.passed]
    if not failures:
        return None
    errors = result.get('errors', ())
    if (isinstance(refusal, Raised) and len(errors) == 1
            and errors[0][0] == 'call' and errors[0][1] is refusal.error
            and len(failures) == 1 and failures[0].when == 'call' and failures[0].failed):
        return None
    return _unavailable('real calibration test did not pass completely: '
                        + ', '.join(report.when + ' ' + report.outcome for report in failures), status='red')


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
        readings = []
        def observe(original, bound):
            axes = {}
            for parameter in anchor.parameters:
                name = parameter.name
                if name not in bound.arguments:
                    continue
                actual = bound.arguments[name]
                try:
                    kind = parameter_kind(parameter, actual)
                except ValueError as error:
                    raise _Unavailable(str(error)) from error
                if kind is not None:
                    axes[name] = [_value_in_context(anchor, original, name, values.get(name, actual), actual)]
                elif name in values:
                    raise _Unavailable(name + ': actual test context cannot be replaced')
            position = len(scope.runtime.readings)
            try:
                return scope.runtime.observe(original, bound, owner=function, name=anchor.name, axes=axes, private=True)
            finally:
                if len(scope.runtime.readings) > position:
                    reading = scope.runtime.readings[position]
                    requested = {name: grid[0] for name, grid in axes.items()}
                    rows = [value for inputs, value in reading.rows
                            if inputs.keys() == requested.keys() and all(outcome_equal(inputs[k], v) for k, v in requested.items())]
                    readings.append((reading, rows))
        observe.__flowguard_transport__ = (type(scope.runtime).observe.__code__,)
        scope.runtime.register(function)
        with sites.intercepted(function, observe):
            replay = scope.runtime.replay(item, nextitem=scope.nextitem)
        if problems := scope.runtime.observer_issues():
            return _unavailable('; '.join(problems))
        failed = _reports(replay)
        if failed:
            return failed
        if len(readings) != 1:
            return _unavailable('test must reach the actual anchor exactly once; target may be absent or ambiguous')
        reading, rows = readings[0]
        if reading.status != 'ok' or len(rows) != 1:
            return _unavailable('; '.join(reading.reasons) or 'requested reading is unavailable or ambiguous')
        return dict(status='ok', outcome=rows[0])
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
    if _reuse and facts is not None and key in facts:
        return facts[key]
    if _instrumented((anchor.target,)):
        return _unavailable('calibration must be prepared before code instrumentation')
    baseline = _sensor(root, anchor, {})
    zero = _sensor(root, anchor, {}) if baseline['status'] == 'ok' else baseline
    result = (dict(status='ok') if baseline['status'] == zero['status'] == 'ok'
              and outcome_equal(baseline['outcome'], zero['outcome']) else
              _unavailable('original-value recheck differs from the complete original test')
              if baseline['status'] == zero['status'] == 'ok' else zero)
    if _reuse and facts is not None and result['status'] == 'ok':
        facts[key] = result
    return result


def _observe_current(root, anchor, values):
    facts = _FACTS.get()
    if facts is None or facts[0] != Path(root).resolve() or _key(anchor) not in facts[1]:
        return _observation('grey', anchor, reasons=('calibrated anchor must be prepared in the real pytest session',))
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
    from .anchors import _source, _accepts, parameter_kind
    from .flow import Capture, relation_observations
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
        capture = Capture(root, binding.anchor_index, binding.testnode)
        calls = []
        def enter(original, bound):
            for name, value in values.items():
                parameter = next(p for p in binding.scenario.parameters if p.name == name)
                try:
                    kind = parameter_kind(parameter, bound.arguments.get(name))
                except ValueError as error:
                    raise _Unavailable(str(error)) from error
                actual = bound.arguments.get(name)
                if kind is None and not (
                        parameter.inferred and name in binding.field_map.values()
                        and type(value) is tuple and type(actual) is tuple
                        and _tuple_point(value) and _tuple_point(actual)
                        and _accepts(parameter.source_type, value) and _accepts(parameter.source_type, actual)):
                    raise _Unavailable(name + ': actual test context cannot be replaced')
                bound.arguments[name] = _value_in_context(binding.scenario, original, name, value, bound.arguments.get(name))
            calls.append(dict(bound.arguments))
            return original(*bound.args, **bound.kwargs)
        codes = _codes(binding.anchor_index)
        codes.append((function.__code__, binding.scenario.target))
        previous = len(scope.runtime.issues)
        try:
            with sites.intercepted(function, enter):
                with scope.runtime.record(codes, callback=capture.on_trace, private=True):
                    replay = scope.runtime.replay(item, nextitem=scope.nextitem)
        finally:
            capture.close()
        problems = capture.issues + scope.runtime.issues[previous:] + scope.runtime.observer_issues()
        if problems:
            return _unavailable('; '.join(problems))
        if len(calls) != 1:
            return _reports(replay) or _unavailable('scenario must reach exactly one actual pytest entry')
        projection = relation_observations(binding.flow, capture, binding.anchor_index, _rule_id(binding))
        observations = [row for row in projection['observations'] if row['relation_index'] in binding.relation_indices]
        if projection['status'] != 'observed' or len(observations) != 1:
            failed = _reports(replay)
            return failed or _unavailable('; '.join(projection['grey']) or 'scenario has ambiguous actual reading scopes')
        observed = observations[0]
        if observed['sources'].get('$actual', {}).get('site') not in binding.actual_targets:
            return _unavailable('actual reading does not come from a declared production anchor')
        requested = getattr(binding, 'requested_inputs', {field: values[parameter] for field, parameter in binding.field_map.items() if parameter in values})
        for field, value in requested.items():
            if field not in observed['inputs'] or not outcome_equal(observed['inputs'][field], value):
                return _unavailable('actual scenario input did not match ' + field)
        failed = _reports(replay, refusal=observed['actual'])
        if failed:
            return failed
        return dict(status='ok', outcome=observed['actual'], inputs=observed['inputs'], sources=observed['sources'])
    except Exception as error:
        return _unavailable('scenario verification failed: ' + type(error).__name__ + ': ' + str(error))


def _scenario_key(binding):
    return ('scenario', _identity(), binding.testnode, binding.scenario.source_digest, binding.anchor.target,
            binding.anchor.source_digest, _rule_id(binding), tuple(binding.relation_indices))


def _prepare_scenario(root, binding):
    facts = _facts(root)
    key = _scenario_key(binding)
    if facts is not None and key in facts:
        return facts[key]
    if _instrumented(set(binding.targets) | set(binding.actual_targets)):
        return _unavailable('scenario must be prepared before code instrumentation')
    baseline = _scenario(root, binding, {})
    zero = _scenario(root, binding, {}) if baseline['status'] == 'ok' else baseline
    if baseline['status'] == zero['status'] == 'ok':
        result = (dict(status='ok') if outcome_equal(baseline['outcome'], zero['outcome'])
                  and outcome_equal(baseline['inputs'], zero['inputs']) else
                  _unavailable('original-value scenario readings differ from the complete original test'))
    else:
        result = zero
    if facts is not None and result['status'] == 'ok':
        facts[key] = result
    return result


def execute_scenario(root, binding, values):
    with _execution_session(root):
        prepared = _prepare_scenario(root, binding)
        result = _scenario(root, binding, values) if prepared['status'] == 'ok' else prepared
        return _result(binding.anchor, result, check_type=False)


def _observe_scenario_current(root, binding, values):
    facts = _FACTS.get()
    if facts is None or facts[0] != Path(root).resolve() or _scenario_key(binding) not in facts[1]:
        return _observation('grey', binding.anchor, reasons=('scenario must be prepared in the real pytest session',))
    return _result(binding.anchor, _scenario(root, binding, values), check_type=False)
