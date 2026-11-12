"""Calibrated observations from the calls a test made in the one ordinary pytest session.

There is no transport, collector or test runner here, and no test runs again (design 4.5, 8): the
pytest integration supplies its real items, the runtime's recorded calls and the anchor events of the
ordinary run. A calibrated point is the named test's recorded JSON call with the requested inputs put
in place, evaluated in the sealed environment; a scenario point is the scenario test's own recorded calls
with the inputs it passes straight through put in place, evaluated the same way and read through its Flow.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
import inspect
import json
from pathlib import Path
import types

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
    sealed: dict = field(default_factory=dict)      # sealed answers of this session's recorded calls (_sealed_call)


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
    projects. A requested input other than the recorded one is put into the recorded calls the scenario test
    made itself and evaluated in the sealed environment (`_sealed_point`); no test runs again (design 4.5, 8)."""
    from .anchors import _source, _accepts, parameter_kind
    from .flow import relation_observations
    issue = _values(binding.scenario, values)
    if issue:
        return issue
    try:
        _, _, definition = _source(root, binding.scenario)
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
        changed = {}
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
            if not outcome_equal(recorded[name], value):
                changed[name] = value
        projection = relation_observations(binding.flow, events, binding.anchor_index, _rule_id(binding))
        observations = [row for row in projection['observations'] if row['relation_index'] in binding.relation_indices]
        if projection['status'] != 'observed' or len(observations) != 1:
            return _unavailable('; '.join(projection['grey']) or 'scenario has ambiguous actual reading scopes')
        observed = observations[0]
        site = observed['sources'].get('$actual', {}).get('site')
        if site not in binding.actual_targets:
            return _unavailable('actual reading does not come from a declared production anchor')
        # The recorded run passed, or failed only by raising the declared outcome it observed.
        if failed := _passed(scope, item, observed['actual'] if isinstance(observed['actual'], Raised) else None):
            return failed
        if changed:
            observed = _sealed_point(scope, item, binding, function, definition, events, entries[0], changed)
            if 'status' in observed:
                return observed
        requested = getattr(binding, 'requested_inputs', {field: values[parameter] for field, parameter in binding.field_map.items() if parameter in values})
        for field, value in requested.items():
            if field not in observed['inputs'] or not outcome_equal(observed['inputs'][field], value):
                return _unavailable('actual scenario input did not match ' + field)
        from .tracer import recorded_entry
        recorded_entry(sites.unwrap(sites.resolve_loaded(site)).__code__)
        return dict(status='ok', outcome=observed['actual'], inputs=observed['inputs'], sources=observed['sources'])
    except Exception as error:
        return _unavailable(str(error) if isinstance(error, _Unavailable)
                            else 'scenario verification failed: ' + type(error).__name__ + ': ' + str(error))


def _sealed_point(scope, item, binding, test, definition, events, entry, changed):
    """The Flow's reading of the scenario's recorded events with the `changed` inputs put in place (design 4.5, 8).

    The entry takes the inputs. Each production anchor call a relation of this rule reads is the scenario test's
    own recorded JSON call, with every argument the test passes straight from a changed input replaced, evaluated
    in the sealed environment; the Flow then projects these events as it projects the recorded ones. A call that
    is not the test's own, that takes a changed input any other way, or that the sealed environment cannot run
    is not compared, with why. Nothing runs the test again. Returns the observation, or why there is none."""
    from dataclasses import replace
    from .flow import _caller_matches, relation_observations
    sources = {parameter.name: parameter.source for parameter in binding.scenario.parameters}
    passed = {sources[name]: name for name in changed}          # the test's own parameter -> its scenario input
    # What the test's source says about these inputs, read once per source version and set of changed inputs.
    facts = ('test', binding.scenario.file, binding.scenario.source_digest, binding.scenario.qual, item.nodeid,
             frozenset(passed))
    if facts not in scope.sealed:
        # No call changes an inert input the test did not change, nor a module, function or class it names globally.
        fixed = {sources[name] for name, value in entry.values.items() if name not in changed and _inert(value)}
        immutable = fixed | {name for name, value in test.__globals__.items()
                             if isinstance(value, (types.ModuleType, types.FunctionType, type))}
        stored, tainted = _stored(definition), _tainted(definition, set(passed), immutable)
        # An unchanged inert input the test never assigns has its recorded value at every input.
        scope.sealed[facts] = (sorted(set(passed) & stored), tainted, _spans(definition, tainted), fixed - stored,
                               stored)
    assigned, tainted, calls, kept, stored = scope.sealed[facts]
    if assigned:
        return _unavailable(f'not compared: the scenario test assigns {assigned[0]}; another input cannot be put '
                            'into its calls')
    flow, index = binding.flow, binding.anchor_index
    relations = [flow.relations[position] for position in binding.relation_indices]
    read = {part.node for relation in relations for part in (*relation.inputs.values(), relation.actual) if part is not None}
    read |= {relation.on or flow.nodes[-1].name for relation in relations}
    nodes = [node for node in flow.nodes if node.name in read]
    begun = entry.anchor, entry.site, entry.occurrence
    reads = [event for event in events if event.phase == 'call' and (event.anchor, event.site, event.occurrence) != begun
             and any(node.reference == event.anchor and node.occurrence in (None, event.occurrence)
                     and _caller_matches(node, event, flow, events, index) for node in nodes)]
    made = {tuple(event.caller[3]) for event in reads if len(event.caller) >= 4}    # the calls evaluated here
    evaluated = {}
    for event in reads:
        point = _sealed_call(scope, item, index, test, calls, event, entry.values, passed, changed,
                             (tainted, kept, stored), made)
        if isinstance(point, dict):
            return point
        evaluated[event.anchor, event.site, event.occurrence] = point
    substituted, raised = [], None
    for event in events:
        identity = event.anchor, event.site, event.occurrence
        if raised is not None:
            if identity == begun and event.phase != 'call':     # the error leaves the test: its entry raises it
                substituted.append(replace(event, values={**event.values, **changed}, phase='raise', result=None, error=raised))
            continue
        if identity == begun:
            substituted.append(replace(event, values={**event.values, **changed}))
        elif identity not in evaluated:
            substituted.append(event)
        else:
            values, outcome, propagates = evaluated[identity]
            if event.phase == 'call':
                substituted.append(replace(event, values=values))
                continue
            failed = isinstance(outcome, Raised)
            if event.phase == 'raise' and not failed:
                return _unavailable(f'not compared: {event.anchor} raised in the recorded call and returns with these '
                                    'inputs; the rest of the scenario test was not recorded')
            if failed and event.phase == 'return':
                if not propagates:
                    return _unavailable(f'not compared: {event.anchor} raises with these inputs inside a try or with '
                                        'block of the scenario test; what the test does then was not recorded')
                raised = outcome.error
            substituted.append(replace(event, values=values, phase='raise' if failed else 'return',
                                       result=None if failed else outcome, error=outcome.error if failed else None))
    projection = relation_observations(flow, substituted, index, _rule_id(binding))
    observations = [row for row in projection['observations'] if row['relation_index'] in binding.relation_indices]
    if projection['status'] != 'observed' or len(observations) != 1:
        return _unavailable('not compared: ' + ('; '.join(projection['grey']) or 'the sealed point has no single reading'))
    observed = observations[0]
    if observed['sources'].get('$actual', {}).get('site') not in binding.actual_targets:
        return _unavailable('actual reading does not come from a declared production anchor')
    return observed


def _sealed_call(scope, item, index, test, calls, event, inputs, passed, changed, known, made):
    """(anchor values, outcome, whether its error leaves the test) of one production anchor call the scenario
    test made itself: its recorded JSON call with each argument the test passes straight from a changed input
    replaced, evaluated sealed. The call expression must name the anchor function itself, and each argument it
    passes from an input must have that input's recorded value (`inputs`) in the recorded call, so the expression
    binds to the function's parameters as Python binds it. Every other argument must be a literal or an unchanged
    input the test never assigns, so that its recorded value is its value at every input, and nothing the changed
    inputs may steer decides whether or how often the test makes the call, except the earlier calls this point
    evaluates itself (`made`, by span). The recorded call's own sealed outcome must be the recorded one first. Or
    why it is not compared. `calls`: the test's call expressions by source span (`_spans`); `known`: the test's
    names that may depend on a changed input, its fixed inputs and every name it binds."""
    from .flow import _resolved
    tainted, kept, stored = known
    anchors = [anchor for anchor in index.named(event.anchor) if anchor.target == event.site]
    if len(anchors) != 1:
        return _unavailable(f'not compared: {event.anchor} has no unique indexed source anchor')
    anchor = anchors[0]
    if (len(event.caller) < 4 or _resolved(event.caller[0]) != _resolved(test.__code__.co_filename)
            or event.caller[1] != test.__qualname__.replace('.<locals>.', '.')):
        return _unavailable(f'not compared: {anchor.name} is called inside another function, not by the scenario '
                            'test itself; another input cannot be put into that call')
    function = sites.unwrap(sites.resolve_loaded(anchor.target))
    if (not inspect.isfunction(function) or _resolved(function.__code__.co_filename) != _resolved(str(scope.runtime.root / anchor.file))
            or function.__qualname__.replace('.<locals>.', '.') != anchor.qual):
        return _unavailable('loaded function does not match the actual source anchor')
    # The sealed environment is deterministic: one answer per source, recorded call and inputs in this session.
    # A source that changed since its anchor was indexed fails the Flow's source identity check after this.
    from .runtime import _HISTORICAL
    answers, source = scope.sealed, (_HISTORICAL.get(), anchor.target, anchor.source_digest)
    if source not in answers:
        answers[source] = scope.runtime.safety(function)
    if answers[source]:                     # a source the sealed environment cannot run is never compared
        return _unavailable(answers[source])
    reading = _call_reading(scope, item, anchor, function, event)
    if isinstance(reading, dict):
        return reading
    signature = inspect.signature(function, follow_wrapped=False)
    bound = inspect.BoundArguments(signature, dict(reading.sample['inputs']))
    recorded = source + (reading.index,)
    if recorded not in answers:
        answers[recorded] = scope.runtime.guarded(function, bound)
    expected, reason = answers[recorded]
    if reason:
        return _unavailable(reason)
    actual = reading.actual[1]
    agrees = outcome_equal(actual, expected) if isinstance(actual, Raised) else \
        not isinstance(expected, Raised) and outcome_equal(reading.json_result, expected)
    if not agrees:
        return _unavailable(f'not compared: the scenario test\'s recorded call of {anchor.name} differs from its sealed '
                            'source outcome')
    span = tuple(event.caller[3])               # the call expression at the span the runtime recorded
    if span not in calls:
        return _unavailable(f'not compared: the scenario test\'s call of {anchor.name} is not one call expression '
                            'in its source')
    call, propagates, steering = calls[span]
    arguments, failure = _passed_arguments(call, signature, passed, tainted, kept, anchor.name)
    if failure:
        return failure
    for parameter, name in arguments.items():
        sample = reading.sample['inputs']
        if parameter not in sample or not outcome_equal(sample[parameter], inputs[name]):
            has = f'{parameter}={sample[parameter]!r}' if parameter in sample else f'no {parameter}'
            return _unavailable(f'not compared: the recorded call of {anchor.name} has {has} while the scenario test\'s '
                                f'input {name} is {inputs[name]!r}; the call does not pass that input straight to '
                                f'{anchor.name}')
    if _callee(call.func, test, stored) is not function:
        return _unavailable(f'not compared: the scenario test calls {anchor.name} through {ast.unparse(call.func)}, '
                            'not by a module name for the function itself; how that passes its arguments was not '
                            'recorded')
    for how, names, statement in steering:
        if statement is None or statement not in made:
            return _unavailable(_STEERED[how].format(call=anchor.name, names=', '.join(sorted(names))))
    if not arguments:
        return dict(event.values), expected, propagates
    requested = inspect.BoundArguments(signature, dict(bound.arguments))
    values = dict(event.values)
    for parameter, name in arguments.items():
        requested.arguments[parameter] = changed[name]
        values.update((declared.name, changed[name]) for declared in anchor.parameters if declared.source == parameter)
    point = recorded + tuple(sorted((parameter, type(changed[name]).__qualname__, repr(changed[name]))
                                    for parameter, name in arguments.items()))
    if point not in answers:
        answers[point] = scope.runtime.guarded(function, requested)
    outcome, reason = answers[point]
    if reason:
        return _unavailable(reason)
    return values, outcome, propagates


def _call_reading(scope, item, anchor, function, event):
    """The runtime's recorded JSON call of `function` that the named test made with this event's anchor values."""
    target = function.__module__ + ':' + function.__qualname__
    found = [reading for reading in scope.runtime.readings if reading.target == target and item.nodeid in reading.tests]
    calls = {}
    for reading in found:
        if reading.sample is None or reading.actual is None:
            continue
        inputs = reading.sample['inputs']
        if all(parameter.source in inputs and parameter.name in event.values
               and outcome_equal(inputs[parameter.source], event.values[parameter.name]) for parameter in anchor.parameters):
            calls[json.dumps(inputs, sort_keys=True)] = reading      # one call: the same encoded inputs
    if len(calls) > 1:
        return _unavailable(f'not compared: the scenario test made several recorded calls of {anchor.name} that its '
                            'anchor values do not tell apart')
    if not calls:
        reasons = list(dict.fromkeys(reason for reading in found for reason in reading.reasons))
        if not found and scope.runtime.full(function):
            reasons.append('20 distinct inputs were recorded before the scenario test ran')
        return _unavailable(f'not compared: the scenario test\'s call of {anchor.name} has no recorded JSON reading'
                            + (' (' + '; '.join(reasons) + ')' if reasons else ''))
    reading = next(iter(calls.values()))
    if isinstance(reading.actual[1], Raised) and not isinstance(reading.actual[1].error, Exception):
        return _unavailable(f'not compared: the scenario test\'s call of {anchor.name} ended with '
                            + type(reading.actual[1].error).__name__)
    return reading


def _passed_arguments(call, signature, passed, tainted, kept, name):
    """({function parameter: scenario input}, None) for the arguments `call` passes straight from a changed
    input (`passed`: the test's parameter name -> its input), or (None, why it is not compared): the call is
    chosen by, or an argument is computed from, a changed input or a name whose value may depend on one
    (`tainted`), or an argument is neither a literal nor an unchanged input in `kept`. The test's source does
    not show every way a value reaches such an argument (an alias, a helper's module state), so its recorded
    value is not its value at another input."""
    def mentions(node):
        return {part.id for part in ast.walk(node) if isinstance(part, ast.Name) and part.id in tainted}
    def unknown(parameter, expression):
        return None, _unavailable(f'not compared: the scenario test passes {ast.unparse(expression)} as the '
                                  f'{parameter} argument of {name}; only a literal, or an input of a fixed value '
                                  'that the test never assigns, is known at another input')
    if found := sorted(mentions(call.func)):
        return None, _unavailable(f'not compared: the scenario test chooses its call of {name} by {", ".join(found)}')
    expressions = [*call.args, *(keyword.value for keyword in call.keywords)]
    if any(isinstance(argument, ast.Starred) for argument in call.args) or any(k.arg is None for k in call.keywords):
        if found := sorted(set().union(*map(mentions, expressions))):
            return None, _unavailable(f'not compared: the scenario test unpacks the arguments of {name} from '
                                      f'{", ".join(found)}')
        for expression in call.args:
            if not _fixed(expression.value if isinstance(expression, ast.Starred) else expression, kept):
                return unknown('unpacked', expression)
        for keyword in call.keywords:
            if not _fixed(keyword.value, kept):
                return unknown('unpacked', ast.Starred(keyword.value) if keyword.arg is None else keyword.value)
        return {}, None
    try:
        bound = signature.bind(*call.args, **{keyword.arg: keyword.value for keyword in call.keywords})
    except TypeError as error:
        return None, _unavailable(f'not compared: the scenario test\'s call of {name} does not bind to its '
                                  f'parameters: {error}')
    arguments = {}
    for parameter, expression in bound.arguments.items():
        if isinstance(expression, ast.Name) and expression.id in passed:
            arguments[parameter] = passed[expression.id]
            continue
        parts = expression if isinstance(expression, tuple) else tuple(expression.values()) \
            if isinstance(expression, dict) else (expression,)
        if found := sorted(set().union(*map(mentions, parts))):
            return None, _unavailable(f'not compared: the scenario test computes the {parameter} argument of {name} '
                                      f'from {", ".join(found)}; the sealed environment does not run the test')
        for part in parts:
            if not _fixed(part, kept):
                return unknown(parameter, part)
    return arguments, None


def _callee(node, test, stored):
    """What the test's call expression `node` calls, read without running anything: a module-level name of the
    test that the test never binds itself (`stored`), or a chain of module attributes from one; else None."""
    path = []
    while isinstance(node, ast.Attribute):
        path.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id in stored or node.id not in test.__globals__:
        return None
    value = test.__globals__[node.id]
    for attribute in reversed(path):
        if not isinstance(value, types.ModuleType) or attribute not in vars(value):
            return None
        value = vars(value)[attribute]
    return value


def _fixed(node, kept):
    """An argument expression of the test with the same value at every input: a literal or a name in `kept`."""
    return isinstance(node, ast.Name) and node.id in kept or _literal(node)


def _literal(node):
    """A literal expression: a constant, a signed number, or a tuple of these. Nothing else is read as a fixed
    value, not even a module name: a call could change what it holds."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float, complex)
    if isinstance(node, ast.Tuple):
        return all(_literal(item) for item in node.elts)
    return isinstance(node, ast.Constant)


def _inert(value):
    """A value no call can change: None, a bool, number or string, an enum member, or a tuple of these."""
    if type(value) is tuple:
        return all(_inert(item) for item in value)
    return isinstance(value, Enum) or type(value) in (type(None), bool, int, float, str)


def _stored(definition):
    """Every name the test `definition` binds anywhere in its body, or declares global or nonlocal."""
    names = set()
    for node in ast.walk(definition):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not definition:
            names.add(node.name)
        elif isinstance(node, ast.alias):
            names.add((node.asname or node.name).split('.')[0])
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def _tainted(definition, seed, immutable):
    """The names of the test `definition` whose value may depend on the changed inputs `seed`: one assigned from
    an expression that names such a name, or inside a branch, loop, with or try block whose condition or body
    names one; an object given to, or called on by, a call whose arguments name one (the call may change it), unless
    `immutable` says no call can; and every name declared global or nonlocal."""
    tainted = set(seed) | {name for node in ast.walk(definition) if isinstance(node, (ast.Global, ast.Nonlocal))
                           for name in node.names}
    def mentions(*nodes):
        return any(isinstance(part, ast.Name) and part.id in tainted for node in nodes if node is not None
                   for part in ast.walk(node))
    def mark(target):
        tainted.update(part.id for part in ast.walk(target) if isinstance(part, ast.Name))
    def base(node):
        while isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred)):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None
    def expressions(node, controlled):
        for part in ast.walk(node):
            if isinstance(part, ast.NamedExpr) and (controlled or mentions(part.value)):
                mark(part.target)
            elif isinstance(part, ast.comprehension) and (controlled or mentions(part.iter, *part.ifs)):
                mark(part.target)
            elif isinstance(part, ast.Call):
                given = [*part.args, *(keyword.value for keyword in part.keywords)]
                if mentions(*given):
                    owner = base(part.func) if not isinstance(part.func, ast.Name) else None
                    tainted.update(name for name in [owner, *map(base, given)] if name and name not in immutable)
    def visit(statements, controlled):
        for statement in statements:
            if isinstance(statement, (ast.If, ast.While)):
                expressions(statement.test, controlled)
                inner = controlled or mentions(statement.test)
                visit(statement.body, inner)
                visit(statement.orelse, inner)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                expressions(statement.iter, controlled)
                inner = controlled or mentions(statement.iter)
                if inner:
                    mark(statement.target)
                visit(statement.body, inner)
                visit(statement.orelse, inner)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                inner = controlled
                for part in statement.items:
                    expressions(part.context_expr, controlled)
                    inner = inner or mentions(part.context_expr)
                    if part.optional_vars is not None and inner:
                        mark(part.optional_vars)
                visit(statement.body, inner)
            elif isinstance(statement, (ast.Try, ast.TryStar)):
                visit(statement.body, controlled)
                inner = controlled or mentions(*statement.body)
                for handler in statement.handlers:
                    if handler.name and inner:
                        tainted.add(handler.name)
                    visit(handler.body, inner)
                visit(statement.orelse, inner)
                visit(statement.finalbody, inner)
            elif isinstance(statement, ast.Match):
                expressions(statement.subject, controlled)
                for case in statement.cases:
                    inner = controlled or mentions(statement.subject, case.guard)
                    if inner:
                        tainted.update(name for part in ast.walk(case.pattern)
                                       for name in (getattr(part, 'name', None), getattr(part, 'rest', None)) if name)
                    visit(case.body, inner)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if mentions(statement):
                    tainted.add(statement.name)
            else:
                if isinstance(statement, ast.Assign) and (controlled or mentions(statement.value)):
                    for target in statement.targets:
                        mark(target)
                elif isinstance(statement, ast.AugAssign) and (controlled or mentions(statement.value, statement.target)):
                    mark(statement.target)
                elif isinstance(statement, ast.AnnAssign) and statement.value is not None \
                        and (controlled or mentions(statement.value)):
                    mark(statement.target)
                expressions(statement, controlled)
    while True:
        before = set(tainted)
        visit(definition.body, False)
        if tainted == before:
            return tainted


_STEERED = {
    'choice': 'not compared: the scenario test chooses whether to call {call} by {names}; what it does at another '
              'input was not recorded',
    'loop': 'not compared: the scenario test calls {call} in a loop that reads {names}; how often it calls it at '
            'another input was not recorded',
    'before': 'not compared: the scenario test reads {names} before its call of {call}, in code the sealed point does '
              'not evaluate; what it does then at another input was not recorded'}


def _spans(definition, tainted):
    """Each call expression of the test `definition` by its source span: (the call, whether an error it raises
    leaves the test, what the changed inputs may steer it by). An error leaves the test when no try or with block
    of the test encloses the call. What may steer it is a list of (how, names, made) for the `tainted` names that
    a loop around it reads ('loop'), that the test of a branch, conditional expression, match or boolean operand
    deciding whether it runs reads ('choice'), or that a statement before it in the source reads ('before'): such
    a statement may return, raise, break or change state on another input. `made` is the span of the one call a
    statement makes from names and literals, which a sealed point may evaluate itself, else None."""
    def reads(*nodes):
        return {part.id for node in nodes if node is not None for part in ast.walk(node)
                if isinstance(part, ast.Name) and part.id in tainted and isinstance(part.ctx, ast.Load)}
    def span(node):
        return node.lineno, node.end_lineno, node.col_offset, node.end_col_offset
    spans = {}
    def visit(node, enclosed, steered):
        if isinstance(node, ast.Call):
            spans[span(node)] = node, not enclosed, steered
        enclosed = enclosed or isinstance(node, (ast.Try, ast.TryStar, ast.With, ast.AsyncWith))
        def inner(how, names):
            return steered + ((how, frozenset(names), None),) if names else steered
        if isinstance(node, (ast.For, ast.AsyncFor)):
            visit(node.iter, enclosed, steered)            # evaluated once, before the loop
            for child in (node.target, *node.body, *node.orelse):
                visit(child, enclosed, inner('loop', reads(node)))
        elif isinstance(node, (ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for child in ast.iter_child_nodes(node):
                visit(child, enclosed, inner('loop', reads(node)))
        elif isinstance(node, (ast.If, ast.IfExp)):
            visit(node.test, enclosed, steered)
            for child in (node.body, node.orelse) if isinstance(node, ast.IfExp) else (*node.body, *node.orelse):
                visit(child, enclosed, inner('choice', reads(node.test)))
        elif isinstance(node, ast.BoolOp):
            for position, value in enumerate(node.values):
                visit(value, enclosed, inner('choice', reads(*node.values[:position])))
        elif isinstance(node, ast.Match):
            visit(node.subject, enclosed, steered)
            for position, case in enumerate(node.cases):
                deciding = reads(node.subject, *(part for earlier in node.cases[:position + 1]
                                                 for part in (earlier.pattern, earlier.guard)))
                visit(case, enclosed, inner('choice', deciding))
        else:
            for child in ast.iter_child_nodes(node):
                visit(child, enclosed, steered)
    visit(definition, False, ())
    # Every read of a tainted name by a statement of the test, at its source position, with the one call that
    # statement makes when it only makes a call from names and literals.
    before = []
    for statement in ast.walk(definition):
        if not isinstance(statement, ast.stmt) or statement is definition:
            continue
        value = statement.value if isinstance(statement, (ast.Expr, ast.Assign)) else None
        made = span(value) if (isinstance(value, ast.Call) and not reads(value.func)
                               and all(isinstance(target, ast.Name) for target in getattr(statement, 'targets', ()))
                               and all(isinstance(argument, ast.Name) or _literal(argument) for argument in
                                       (*value.args, *(keyword.value for keyword in value.keywords)))
                               and all(keyword.arg for keyword in value.keywords)) else None
        for part in _own(statement):
            if isinstance(part, ast.Name) and part.id in tainted and (
                    isinstance(part.ctx, ast.Load) or isinstance(statement, ast.AugAssign) and part is statement.target):
                before.append(((part.lineno, part.col_offset), part.id, made))
    for key, (call, propagates, steered) in spans.items():
        earlier = {}
        for position, name, made in before:
            if position < (call.lineno, call.col_offset):
                earlier.setdefault(made, set()).add(name)
        spans[key] = call, propagates, steered + tuple(('before', frozenset(names), made) for made, names in sorted(
            earlier.items(), key=lambda pair: (pair[0] is not None, pair[0] or ())))
    return spans


def _own(node):
    """The nodes of `node` outside the statements it contains."""
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.stmt):
            yield child
            yield from _own(child)


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
