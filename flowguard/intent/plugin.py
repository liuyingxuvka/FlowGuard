"""Ordinary pytest owns execution; this plugin adds intent items and source footprints."""
from __future__ import annotations

import fnmatch
from functools import cache
from contextlib import closing, ExitStack, contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time

import pytest

from .config import load_config, project_code
from .engine import Engine
from .loader import load
from .readings import classify, classify_collection
from .tracer import Footprint

SENTINEL = 'test_flowguard_intent'
NO_SKIP = 'this suite allows no skip, expected failure or early exit: a check that did not run is never reported as fine'
_CURRENT = None
_SIGNALS = ContextVar('flowguard_signals', default=None)
_TRY = ContextVar('flowguard_try', default=None)
SCHEMA = '''
CREATE TABLE IF NOT EXISTS reading(test TEXT PRIMARY KEY, outcome TEXT, kind TEXT, reason TEXT,
  phase TEXT, seconds REAL, stamp REAL);
CREATE TABLE IF NOT EXISTS result(item TEXT PRIMARY KEY, rule TEXT, verdict TEXT, payload TEXT, stamp REAL);
'''


@contextmanager
def collect_signals():
    """Let a multi-batch check render its runtime facts exactly once."""
    reports = []
    token = _SIGNALS.set(reports)
    try:
        yield reports
    finally:
        _SIGNALS.reset(token)


@contextmanager
def try_reading(target, name, values, grid=False):
    """Add requested input points to the normal runtime, never narrow its model."""
    request = dict(target=target, name=name, values=dict(values), grid=grid, readings=[], reasons=[], partition_reasons=[], actual_inputs={})
    token = _TRY.set(request)
    try:
        yield request
    finally:
        _TRY.reset(token)


def observation_payload(value, seen=frozenset()):
    import math
    kind = type(value)
    if any(kind is native for native in (type(None), bool, int, str)) or kind is float and math.isfinite(value):
        return value
    namespace = type.__dict__['__dict__'].__get__(kind)
    module = namespace.get('__module__', 'builtins')
    label = (module if type(module) is str else '?') + '.' + type.__dict__['__qualname__'].__get__(kind)
    if any(kind is native for native in (dict, list, tuple)) and id(value) not in seen:
        seen = seen | {id(value)}
        if kind is dict:
            if all(type(key) is str for key in value):
                return {key: observation_payload(part, seen) for key, part in value.items()}
        else:
            return [observation_payload(part, seen) for part in value]
    return {'unverified_type': label}

def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=repr)


# flowguard: states Session.sentinel = None | 'failed' | 'ok'
class Session:
    def __init__(self, config):
        self.config = config
        self.owns_host = False
        self.owns_root = False
        self.cfg = load_config(config.rootpath)
        self.is_project = project_code(self.cfg)
        self.model = self.engine = self.map = None
        self.collected, self.selected, self.deferred = set(), set(), set()
        self.results, self.readings, self.footprints, self.durations = {}, {}, {}, {}
        self.sentinel = None
        self.ordinary_selected, self.early_exit, self.session_errors = set(), [], []
        self.ordinary_files, self.ordinary_deselected = set(), False
        self.last_test = None
        self.completed = set()
        self.process_calls, self.closed = [], False
        self.main_process = os.getpid()
        self.main_thread = threading.get_ident()
        self.started = time.time()
        self.events, self.anchor_issues = [], []
        self.calibration_facts = {}
        self.runtime = None
        self.observations = None
        self.source_items = ()
        self.complete_collection = None

    @contextmanager
    def verification(self):
        from .anchors import _execution_session
        from .calibration import _execution_session as calibrated_session
        with calibrated_session(self.cfg.root, facts=self.calibration_facts), _execution_session(self.cfg.root):
            yield

    def close(self):
        global _CURRENT
        _CURRENT = self.previous_session
        self.closed = True
        for module, name, real, refused in reversed(self.process_calls):
            if getattr(module, name) is refused:
                setattr(module, name, real)
        from .imports import release_host, release_root
        if self.owns_root:
            release_root(self.cfg.root)
        if self.owns_host:
            release_host(self.cfg.root)
        if self.map is not None:
            self.map.close()

    def guard_process_exit(self, config):
        recording = (config.getoption('--flowguard-record-tests', default=False)
                     or getattr(getattr(config, 'known_args_namespace', None), 'flowguard_record_tests', False))
        if self.process_calls or not (self.cfg.skip_policy == 'forbid' or recording):
            return
        modules = {id(module): module for module in (os, sys.modules.get(os.name)) if module is not None}
        for module in modules.values():
            for name in ('_exit', 'execv', 'execve', 'execl', 'execle', 'execlp', 'execlpe', 'execvp', 'execvpe'):
                real = getattr(module, name, None)
                if real is not None:
                    refused = self.refuse_process_call(real, module.__name__ + '.' + name)
                    self.process_calls.append((module, name, real, refused))
                    setattr(module, name, refused)

    def refuse_process_call(self, real, label):
        def refused(*args, **kwargs):
            if self.closed or os.getpid() != self.main_process:
                return real(*args, **kwargs)
            reason = f'{label}() would end or replace the test process'
            self.early_exit.append(reason)
            guidance = NO_SKIP if self.cfg.skip_policy == 'forbid' else 'selected tests did not finish; do not report this check as passed'
            pytest.fail(reason + '; ' + guidance, pytrace=False)
        return refused

    def get_model(self):
        if self.model is None:
            with self.verification():
                self.model = load(self.cfg)
                self.model.deep = self.config.getoption('--flowguard-deep', default=False)
                self.engine = Engine(self.model)
                from .runtime import Runtime
                self.runtime = Runtime(self.cfg.root)
        return self.model

    def prepare_declaration(self, declaration):
        """Calibrate only a selected contract, before its probe installs code."""
        from .calibration import _prepare, _prepare_scenario, probe_context
        from .flow import _registered_flow, _flow_export, Unverified
        model = self.get_model()
        if model.errors or probe_context(self.config):
            return
        pending = [declaration]
        seen = set()
        while pending:
            reference = pending.pop()
            try:
                flow = _registered_flow(reference, model.flows)
            except Unverified:
                continue  # The Flow checker reports an unregistered boundary.
            identifier = getattr(reference, 'id', reference)
            if flow is not None:
                if flow.id in seen:
                    continue
                seen.add(flow.id)
                pending.extend(relation.rule for relation in flow.relations)
                pending.extend(node.model for node in flow.nodes if node.model is not None)
                try:
                    pending.append(_flow_export(flow, model.rules)[0])
                except Unverified:
                    pass  # Missing/ambiguous exports remain grey at their owner.
                continue
            if identifier in seen or identifier not in model.rules:
                continue
            seen.add(identifier)
            rule = model.rules[identifier]
            pending.extend(rule.uses)
            pending.extend(other.id for other in model.key(rule.decides) if other.id not in seen)
            for binding in rule.homes:
                if hasattr(binding, 'scenario'):
                    _prepare_scenario(self.cfg.root, binding)
                elif getattr(binding, 'anchor', None) and binding.anchor.calibrated_by:
                    _prepare(self.cfg.root, binding.anchor)

    def get_map(self):
        if self.map is None:
            from flowguard.structure import build
            self.map = build(self.cfg.root, roots=self.cfg.roots)
        return self.map


def _metadata_value(value):
    """Hash only exact inert data; unknown objects never run cache-key hooks."""
    from datetime import date, datetime, timedelta
    from decimal import Decimal
    import math
    kind = type(value)
    for number, native in enumerate((type(None), bool, int, str, bytes)):
        if kind is native:
            return number, value
    if kind is float:
        return ('float', value.hex()) if math.isfinite(value) else None
    if kind is Decimal:
        return ('decimal', value.as_tuple()) if value.is_finite() else None
    if kind is datetime:
        return ('datetime', value.isoformat(), value.fold) if value.tzinfo is None else None
    if kind is date:
        return 'date', value.isoformat()
    if kind is timedelta:
        return 'timedelta', value.days, value.seconds, value.microseconds
    if kind is tuple:
        values = tuple(_metadata_value(item) for item in value)
        return ('tuple', values) if all(item is not None for item in values) else None
    for number, constructor in enumerate((bool, int, float, str, bytes, Decimal, date, datetime, timedelta)):
        if value is constructor:
            return 'constructor', number
    return None


def _partition_copy(axes, part):
    from .differences import Partition, Region
    return ({name: list(pool) for name, pool in axes.items()},
            Partition([Region(dict(region.inputs), region.label) for region in part.regions],
                      part.complete, list(part.reasons), part.representative_points), [])


class Observations:
    """Connect loaded source points to the one runtime during ordinary tests."""
    def __init__(self, state):
        import ast
        from . import anchors, cache, differences
        from .runtime import Runtime, _functions, _binding_facts
        from ..map.common import MapError, git_run, read_source
        self.state, self.cfg = state, state.cfg
        self.comparison_requested = bool(state.config.getoption('--flowguard-base', default=None))
        baseline = state.config.getoption('--flowguard-base', default=None) or cache.session_baseline(self.cfg, remember=False) or 'HEAD'
        self.runtime = state.runtime = Runtime(self.cfg.root, baseline)
        if state.config.getoption('--flowguard-base', default=None) and self.runtime._baseline_error:
            raise pytest.UsageError(self.runtime._baseline_error)
        self.index = state.model.anchor_index or differences._source_index(self.cfg.root)
        state.model.anchor_index = self.index
        try:
            changed = git_run(self.cfg.root, 'diff', '--name-only', '-z', baseline).stdout
            added = git_run(self.cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
            self.files = {os.fsdecode(value) for value in (changed + added).split(b'\0')
                          if value and value.endswith(b'.py') and state.is_project(str(self.cfg.root / os.fsdecode(value)))}
        except MapError:
            self.files = set()
        self.points = {a.target: dict(anchor=a, target=a.target, file=a.file, module=a.module, qual=a.qual,
                                     name=a.name, kind=a.kind, node=None)
                       for a in self.index.entries if a.kind in ('sensor', 'event') and a.source_role != 'test'}
        self.changed, self.records, self.pairs, self.red, self.grey, self.paths = bool(self.files), [], [], [], [], []
        self.metadata, self.bound, self.event_codes, self.payload = {}, {}, {}, None
        self.request, self.text = _TRY.get(), ''
        self.rules = {}
        for rule in state.model.rules.values():
            for home in rule.homes:
                if not hasattr(home, 'scenario'):
                    self.rules.setdefault(home.target, []).append(rule)
        self.by_file = {}
        if self.changed:
            # The existing map supplies module ownership for unanchored changed functions.
            graph = state.get_map()
            views = {}
            # The running FlowGuard never observes its own observation code: hooking the
            # changed Runtime.observe (or a replay helper) re-enters itself without end.
            tool = Path(__file__).resolve().parents[1]
            for row in graph.nodes():
                if row['file'] not in self.files or row['kind'] not in ('function', 'method') or not state.is_project(str(self.cfg.root / row['file'])):
                    continue
                if (self.cfg.root / row['file']).resolve().is_relative_to(tool):
                    continue
                if row['file'] not in views:
                    tree = ast.parse(read_source(self.cfg.root / row['file']))
                    old = self.runtime._source(row['file'])
                    old_tree = ast.parse(old) if old else ast.Module(body=[], type_ignores=[])
                    views[row['file']] = (dict(_functions(tree)), dict(_functions(old_tree)),
                                          _binding_facts(old_tree), _binding_facts(tree))
                current_functions, prior_functions, old_facts, facts = views[row['file']]
                node = current_functions.get(row['qual'])
                if node is None:
                    continue
                params = tuple(anchors.Parameter(arg.arg, '', anchors._annotation(arg.annotation),
                                                anchors._parameter_role(anchors._annotation(arg.annotation)), True)
                               for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                               if arg.arg not in ('self', 'cls'))
                if not any(p.role == 'input' for p in params):
                    continue
                prior = prior_functions.get(row['qual'])
                if prior is not None and ast.dump(prior, include_attributes=False) == ast.dump(node, include_attributes=False):
                    loaded = {part.id for part in ast.walk(node) if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)}
                    if not any(old_facts.get(name) != facts.get(name) for name in loaded):
                        continue
                self.points.setdefault(row['id'], dict(anchor=None, parameters=params, target=row['id'], file=row['file'],
                                                       module=row['module'], qual=row['qual'], name=row['qual'], kind='sensor', node=node))
        for point in self.points.values():
            self.by_file.setdefault(point['file'], []).append(point)

    def _module(self, module):
        from .runtime import _PRIVATE
        token = _PRIVATE.set(True)
        try:
            return self._bind_module(module)
        finally:
            _PRIVATE.reset(token)

    def _bind_module(self, module):
        import inspect
        import types
        filename = getattr(module, '__file__', None)
        if not filename:
            return
        for point in self.by_file.get(self.cfg.rel(filename), ()):
            if point['target'] in self.bound:
                continue
            value, receiver = module, None
            for part in point['qual'].split('.'):
                receiver = value if isinstance(value, type) else None
                value = vars(value).get(part) if isinstance(value, (types.ModuleType, type)) else None
                value = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
            if not isinstance(value, types.FunctionType):
                continue
            from . import sites
            fn = sites.unwrap(value)
            point['fn'], point['receiver'] = fn, receiver
            groups = self.index.named(point['name'], 'sensor') if point['anchor'] else ()
            if not self.changed and (point['kind'] == 'event' or not self.comparison_requested and len(groups) < 2 and not self.rules.get(point['target'])
                                     and not (self.request and self.request['target'] == point['target'])):
                continue
            self.runtime.register(fn)
            self.bound[point['target']] = point
            if point['kind'] == 'event':
                self.event_codes[id(fn.__code__)] = (fn.__code__, point['name'])
                continue
            try:
                original = self.scopes.enter_context(self.runtime.hook(fn, name=point['name'],
                    axes=lambda original, bound, point=point: self._at_call(point, original, bound)))
                point['original'] = original
            except (ValueError, TypeError, sites.NotMutable) as error:
                self.grey.append(point['name'] + ': ' + str(error))

    def _partition(self, point, original, bound):
        import ast
        from types import SimpleNamespace
        from . import anchors, cells as C, differences as D
        from .runtime import _definition
        parameters = point.get('parameters', getattr(point['anchor'], 'parameters', ()))
        kinds, unknown = {}, []
        for parameter in parameters:
            try:
                kind = anchors.parameter_kind(parameter, bound.arguments.get(parameter.name, ...))
            except ValueError as error:
                unknown.append(str(error))
            else:
                if kind is not None:
                    kinds[parameter.name] = kind
        path = self.cfg.root / point['file']
        source = path.read_bytes()
        code = original.__code__
        patch = self.runtime.patches.get(point['fn'])
        old_code = patch.code if patch else None
        old_source = self.runtime._source(point['file']) if patch else None
        baseline, old_identity = _metadata_value(self.runtime.baseline), _metadata_value(old_source)
        identity = (id(code), source, old_identity, baseline, id(old_code))
        key = point['file'], original.__qualname__
        cacheable = baseline is not None and old_identity is not None and Path(code.co_filename).resolve() == path.resolve()
        data = self.metadata.setdefault(key, {}) if cacheable else {}
        if (data.get('identity') != identity or data.get('code') is not code
                or data.get('old_code') is not old_code):
            file_data = self.metadata.setdefault((point['file'],), {}) if cacheable else {}
            source_identity = source, old_identity, baseline
            if file_data.get('identity') != source_identity:
                tree = ast.parse(source.decode('utf-8-sig'))
                file_data.update(identity=source_identity, tree=tree,
                                 old_tree=ast.parse(old_source) if patch else tree)
            current = _definition(original)
            previous = patch.node if patch else current
            data.clear()
            data.update(identity=identity, code=code, old_code=old_code,
                        tree=file_data['tree'], current=current, previous=previous, old_tree=file_data['old_tree'],
                        names=sorted({node.id for body in (previous, current) for node in ast.walk(body)
                                      if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}))
        tree, current, previous, old_tree = (data[name] for name in ('tree', 'current', 'previous', 'old_tree'))
        env = anchors._literal_globals(tree)
        old_env = anchors._literal_globals(old_tree)
        old_env.update(self.runtime._constants(old_tree, original.__module__))
        from .runtime import _simple
        for (_, name), (namespace, before) in self.runtime.constants.items():
            if namespace is original.__globals__ and name in namespace and _simple(namespace[name]):
                env[name] = namespace[name]
                old_env[name] = self.runtime._old_value(namespace, name, before)
        roles = tuple((p.name, p.unit, p.source_type, p.role, p.inferred) for p in parameters)
        domains = tuple((name, kind.name, kind.optional, kind.literals) for name, kind in kinds.items())
        facts = [roles, domains]
        for namespace in (env, old_env, original.__globals__):
            facts.append(tuple((name, namespace[name]) for name in data['names'] if name in namespace))
        tokens = [_metadata_value(value) for value in facts]
        reusable = (not unknown and all(kind.enum_type is None for kind in kinds.values())
                    and all(value is not None for value in tokens))
        domain_key = tuple(tokens) if reusable else None
        if reusable and data.get('domain_key') == domain_key and 'partition' in data:
            return _partition_copy(*data['partition'])
        count = len(kinds)
        now_read = C.read_predicate(SimpleNamespace(__globals__=env), kinds, node=current)
        old_read = C.read_predicate(SimpleNamespace(__globals__=old_env), kinds, node=previous)
        # An unclosed numeric range keeps candidate examples, never a proof.
        candidates = {}
        for name in list(kinds):
            evidence = kinds[name].name in ('bool', 'enum') or any(
                reading.consts.get(name) or any(name in plane.coefs for plane in reading.planes)
                or any(name in link for link in reading.links) for reading in (now_read, old_read))
            if not evidence:
                unknown.append(name + ': no closed range; these are candidate examples')
                kind = kinds.pop(name)
                literals = [C.coerce(node.value, kind) for tree in (previous, current) for node in ast.walk(tree)
                            if isinstance(node, ast.Constant) and kind.accepts(C.coerce(node.value, kind))]
                candidates[name] = C.points(kind, literals)
                if name in bound.arguments:
                    env[name] = old_env[name] = bound.arguments[name]
        readings = (old_read, now_read) if len(kinds) == count else tuple(
            C.read_predicate(SimpleNamespace(__globals__=values), kinds, node=node)
            for node, values in ((previous, old_env), (current, env)))
        views = [SimpleNamespace(kinds=kinds, reading=reading, issues=(), node=node, literal_globals=values)
                 for node, values, reading in zip((previous, current), (old_env, env), readings)]
        part = D.joint_partition(*views)
        # joint_partition already built the joint space and retained every
        # logical class. Rebuilding that space here duplicated both work and
        # grid points; the runtime needs these proved representatives only.
        axes = {name: [] for name in kinds}
        from .runtime import outcome_equal
        for region in part.regions:
            for name, value in region.inputs.items():
                if not any(outcome_equal(value, prior) for prior in axes[name]):
                    axes[name].append(value)
        axes.update(candidates)
        if reusable and not unknown and part.complete and all(
                _metadata_value(tuple(region.inputs.values())) is not None for region in part.regions):
            saved_axes, saved_part, _ = _partition_copy(axes, part)
            data.update(domain_key=domain_key, partition=(saved_axes, saved_part))
        return axes, part if not unknown else None, unknown

    def _at_call(self, point, original, bound):
        from . import runtime as R
        token = R._PRIVATE.set(True)
        try:
            return self._classes_at_call(point, original, bound)
        finally:
            R._PRIVATE.reset(token)

    def _classes_at_call(self, point, original, bound):
        from . import runtime as R
        if problem := self.runtime.safety(original, bound.arguments):
            self.records.append((len(self.runtime.readings), point, None, [problem], None))
            return {}  # Runtime still records its refusal and makes the one real call.
        try:
            axes, part, unknown = self._partition(point, original, bound)
        except (ValueError, TypeError, OSError, SyntaxError, AttributeError) as error:
            axes, part, unknown = {}, None, [str(error)]
        if self.request and self.request['target'] == point['target']:
            from . import anchors
            parameters = {parameter.name: parameter for parameter in
                          point.get('parameters', getattr(point['anchor'], 'parameters', ()))}
            for parameter in parameters.values():
                actual = bound.arguments.get(parameter.name, ...)
                try:
                    if anchors.parameter_kind(parameter, actual) is not None and R._simple(actual):
                        self.request['actual_inputs'][parameter.name] = actual
                except ValueError:
                    pass  # Unknown inputs never become an invented default.
            for name, value in self.request['values'].items():
                try:
                    kind = anchors.parameter_kind(parameters[name], bound.arguments.get(name, ...))
                    if kind is None:
                        raise ValueError(name + ': context inputs cannot be replaced')
                    if not kind.accepts(value):
                        raise ValueError(name + ': requested value has the wrong input type')
                except (KeyError, ValueError) as error:
                    self.request['reasons'].append(str(error))
                    continue
                pool = axes.setdefault(name, [])
                if not any(R.outcome_equal(value, prior) for prior in pool):
                    pool.append(value)
            self.request['partition_reasons'].extend(unknown + (part.reasons if part is not None else []))
        for rule in self.rules.get(point['target'], ()):
            if not set(rule.fields) <= axes.keys():
                self.grey.append(rule.id + ': this real context does not expose all rule inputs')
                continue
            values = self.state.engine.rr_space(rule.decides)[2]
            for field in rule.fields:
                pool = axes.setdefault(field, [])
                additions = [*values.get(field, ()), *(row.inputs[field] for row in rule.live_rows if field in row.inputs)]
                pool.extend(value for value in additions if not any(R.outcome_equal(value, prior) for prior in pool))
        peers, measured = [], []
        if not self.runtime.safety(original, bound.arguments) and point['anchor']:
            for anchor in self.index.named(point['name'], 'sensor'):
                other = self.bound.get(anchor.target)
                if other is point:
                    continue
                if not other or 'original' not in other:
                    self.grey.append(point['name'] + ': copy not loaded in this real context: ' + anchor.target)
                    continue
                # The actual context is borrowed only under the same named roles.
                contexts = {p.name: p.source_type for p in point['anchor'].parameters if p.name not in axes}
                theirs = {p.name: p.source_type for p in anchor.parameters if p.name not in axes}
                if contexts != theirs or ({'self', 'cls'} & bound.arguments.keys() and point.get('receiver') is not other.get('receiver')):
                    self.grey.append(point['name'] + ': copy context is not available under the same roles')
                    continue
                import inspect
                try:
                    arguments = inspect.signature(other['original']).bind(**bound.arguments)
                except TypeError:
                    self.grey.append(point['name'] + ': copy signature does not accept this real context')
                    continue
                if self.runtime.safety(other['original'], arguments.arguments):
                    self.grey.append(point['name'] + ': copy is not safe to replay in this context')
                    continue
                try:
                    other_axes, other_part, other_unknown = self._partition(other, other['original'], arguments)
                except (ValueError, TypeError, OSError, SyntaxError, AttributeError) as error:
                    self.grey.append(point['name'] + ': copy partition unavailable: ' + str(error))
                    continue
                for field, values in other_axes.items():
                    pool = axes.setdefault(field, [])
                    pool.extend(value for value in values if not any(R.outcome_equal(value, prior) for prior in pool))
                if other_unknown or other_part is None or not other_part.complete:
                    self.grey.append(point['name'] + ': same-name partition is not closed; candidate comparisons only')
                measured.append((other, arguments))
        for other, arguments in measured:
            token = R._PRIVATE.set(True)
            index = len(self.runtime.readings)
            try:
                self.runtime.observe(other['original'], arguments, owner=other['fn'], name=point['name'], axes=axes, private=True)
            except Exception:
                pass  # Raised rows, not the synthetic final call, decide agreement.
            finally:
                R._PRIVATE.reset(token)
            if len(self.runtime.readings) > index:
                peers.append(self.runtime.readings[index])
        self.records.append((len(self.runtime.readings), point, part, unknown, self._cause(point, original)))
        self.pairs.append((len(self.runtime.readings), peers))
        return axes

    @contextmanager
    def scope(self, item):
        from .imports import observe_imports
        self.runtime.test = item.nodeid
        self.event_codes = {}
        with ExitStack() as self.scopes:
            self.bound = {}
            with observe_imports(self.cfg.root, self._module):
                for name in {point['module'] for point in self.points.values()}:
                    if (module := sys.modules.get(name)) is not None:
                        self._module(module)
                path = []
                def event(frame, phase, value):
                    match = self.event_codes.get(id(frame.f_code))
                    if phase == 'call' and match and match[0] is frame.f_code:
                        path.append(match[1])
                    return None
                record = self.runtime.record(predicate=lambda code: (match := self.event_codes.get(id(code)))
                                              and match[0] is code, callback=event, entry_only=True)
                if self.changed and any(point['kind'] == 'event' for point in self.points.values()):
                    with record:
                        yield
                else:
                    yield
                self.actual_path = path

    def old_path(self, item, nextitem):
        if not self.changed or not self.actual_path or not self.event_codes:
            return
        old = []
        with self.runtime.old_code():
            codes = {id(point['fn'].__code__): (point['fn'].__code__, point['name']) for point in self.bound.values()
                     if point['kind'] == 'event' and point['fn'] in self.runtime.patches}
            if len(codes) != len(self.event_codes):
                self.grey.append(item.nodeid + ': baseline event code is unavailable')
                return
            def event(frame, phase, value):
                match = codes.get(id(frame.f_code))
                if phase == 'call' and match and match[0] is frame.f_code:
                    old.append(match[1])
                return None
            with self.runtime.record(codes=list(codes.values()), callback=event, private=True, entry_only=True):
                result = self.runtime.replay(item, nextitem=nextitem)
        if result['status'] == 'ok':
            self.paths.append(dict(test=item.nodeid, before=old, after=self.actual_path))
        else:
            self.grey.extend(item.nodeid + ': ' + reason for reason in result['reasons'])

    def _rule_signals(self):
        """Check already observed values; partial pytest never invents full receipts."""
        from . import cells as C
        from .engine import CONFLICT, PredicateError, outcome_eq
        from .sources import parse
        engine, checked, quoted = self.state.engine, {}, set()
        for index, point, part, unknown, cause in self.records:
            if index >= len(self.runtime.readings):
                continue
            reading = self.runtime.readings[index]
            # A refused replay leaves the real call: its own inputs and outcome are still a current reading.
            rows = reading.rows if reading.status == 'ok' and reading.rows else [reading.actual] if reading.actual else []
            for rule in self.rules.get(point['target'], ()):
                if not rows:
                    self.grey.append(rule.id + ': no verified current reading in this test context')
                    continue
                active = [other for other in self.state.model.active(rule.decides)
                          if other is rule or not self.state.model.distinct_pair(rule.id, other.id)]
                for other in active:
                    if other.id not in checked:
                        item = self.state.model.file_of[other.id] + '::' + other.id + '[rules]'
                        checked[other.id] = self.state.results.get(item) or engine.run_rules(other)
                guards = [checked[other.id] for other in active]
                if reasons := [reason for guard in guards for reason in guard['grey']]:
                    self.grey.extend(rule.id + ': ' + reason for reason in reasons)
                    continue
                self.red.extend(rule.id + ': ' + message for guard in guards for message in guard['red'])
                required = {field for other in active for field in other.fields}
                for inputs, actual in rows:
                    if not required <= inputs.keys():
                        self.grey.append(rule.id + ': this reading does not expose all rule inputs')
                        continue
                    try:
                        expected = engine.effective(rule, inputs)
                    except PredicateError as error:
                        self.red.append(str(error))
                        continue
                    if expected is CONFLICT:
                        continue  # The independent rule conflict above owns this red.
                    if expected is not None and not outcome_eq(expected, actual):
                        self.red.append(f'{rule.id}: {C.show_cell(inputs)} -> rule {C.show(expected)}, code {str(actual) if type(actual) is bool else C.show(actual)}')
                        if rule.id not in quoted:
                            source = parse(rule.source)
                            self.red.append(rule.id + ' 出处：' + (source.quote or source.text))
                            quoted.add(rule.id)
                        break

    def _flow_signals(self):
        """Check actual projected readings without proving or replaying a contract."""
        from dataclasses import replace
        from .flow import runtime_check, _rule, _test_entry_references, Unverified
        from .sources import authority, parse
        state, results, guards = self.state, [], {}
        self.grey.extend(state.anchor_issues)
        observed_anchors = {event.anchor for event in state.events}
        observed_calls = {event.anchor for event in state.events if event.phase == 'call'}
        for identifier, model in state.model.flows.items():
            if f'{state.model.file_of[identifier]}::{identifier}[flow]' in state.results:
                continue  # The explicitly selected Flow item owns its complete check.
            if not observed_anchors.intersection(node.reference for node in model.nodes):
                continue
            entries = _test_entry_references(model, self.index)
            if entries and not entries.intersection(observed_calls):
                continue  # A sensor called outside this explicit scenario is not its case.
            relations, grey, quotes = [], [], {}
            for relation in model.relations:
                try:
                    rule = _rule(relation, state.model.rules)
                except Unverified:
                    relations.append(relation)  # The reading owner reports the unknown rule.
                    continue
                reasons = []
                for active in state.model.active(rule.decides):
                    if active is not rule and state.model.distinct_pair(rule.id, active.id):
                        continue
                    if active.id not in guards:
                        source = parse(active.source)
                        valid, reason = authority(source, active.confirmed, self.cfg, state.engine.archive, active.quote)
                        borrowed = state.engine.borrowed(active)
                        guards[active.id] = (([reason] if not valid else []) + borrowed, source.quote or source.text)
                    reasons.extend(active.id + ': ' + reason for reason in guards[active.id][0])
                    quotes[active.id] = guards[active.id][1]
                if reasons:
                    grey.extend(reasons)
                else:
                    relations.append(relation)
            observed = runtime_check(replace(model, relations=tuple(relations)), state.events, self.index,
                                     rules=state.model.rules, engine=state.engine, _observed_only=True)
            source = parse(model.source)
            valid, reason = authority(source, None, self.cfg, state.engine.archive, None)
            observed['grey'].extend([*grey, *([] if valid else [reason])])
            observed['verdict'] = 'red' if observed['red'] else 'grey' if observed['grey'] else 'ok'
            observed['info'].append('rule scope: actual input points and static project-reference checks; full independence remains an intent check')
            observed.update(id=identifier, scope='observed paths and relations only', complete=False)
            self.grey.extend(identifier + ': ' + reason for reason in observed['grey'])
            self.red.extend(identifier + ': ' + reason for reason in observed['red'])
            if observed['red']:
                if (quote := source.quote or source.text) not in quotes.values():
                    quotes[identifier] = quote
                self.red.extend(name + ' 出处：' + quote for name, quote in quotes.items())
            results.append(observed)
        return results

    def report(self):
        from types import SimpleNamespace
        from . import cells as C, differences as D, runtime as R, signals
        self._rule_signals()
        partial_flows = self._flow_signals()
        items, leads = [], []
        key = lambda inputs: tuple((name, type(value).__name__, repr(value)) for name, value in sorted(inputs.items()))
        for index, point, part, unknown, cause in self.records:
            if index >= len(self.runtime.readings):
                continue
            reading = self.runtime.readings[index]
            if self.request and self.request['target'] == point['target']:
                self.request['readings'].append(reading)
            actual = {key(inputs): value for inputs, value in reading.rows}
            changes = {key(inputs): old for inputs, old, new in reading.changed}
            if part is not None:
                before, after = [], []
                for region in part.regions:
                    signature = key(region.inputs)
                    available = signature in actual and reading.status == reading.comparison_status == 'ok'
                    before.append(SimpleNamespace(status='ok' if available else 'grey', reasons=tuple(reading.reasons + reading.comparison_reasons),
                                                  value=changes.get(signature, actual.get(signature))))
                    after.append(SimpleNamespace(status='ok' if available else 'grey', reasons=tuple(reading.reasons), value=actual.get(signature)))
                result = D._result(point['name'], part, before, after)
                result['reasons'] += unknown
                result['complete'] &= not unknown
            else:
                from dataclasses import asdict
                result = asdict(reading)
                result['reasons'] += unknown
                result['complete'] = False
            result.update(name=point['name'], file=point['file'], line=getattr(point['anchor'], 'target_line', 0) or point['node'].lineno,
                          unanchored=point['anchor'] is None)
            if reading.status != 'ok':
                result.update(complete=False, reasons=reading.reasons, status='grey')
            if cause:
                result['cause'] = cause
                if isinstance(cause, dict):
                    leads.append(signals.stale_copies(self.state.get_map(), [dict(cause, target=point['target'], fields=list(part.regions[0].inputs) if part and part.regions else [])], limit=5))
            items.append(result)
        for index, peers in self.pairs:
            if index >= len(self.runtime.readings):
                continue
            current = self.runtime.readings[index]
            for peer in peers:
                now = {key(inputs): value for inputs, value in current.rows}
                other = {key(inputs): value for inputs, value in peer.rows}
                for signature in now.keys() & other.keys():
                    if current.status == peer.status == 'ok' and not R.outcome_equal(now[signature], other[signature]):
                        self.red.append(f'同名锚点 {current.name}：' + ', '.join(f'{name}={value}' for name, kind, value in signature) + '，'
                                        f'{C.show(now[signature])} ≠ {C.show(other[signature])}')
                        break
        for result in self.state.results.values():
            if result.get('red'):
                rule = self.state.model.rules.get(result.get('rule'))
                quote = ''
                if rule:
                    from .sources import parse
                    source = parse(rule.source)
                    quote = source.quote or source.text
                self.red.extend(signals.constraint(message, result.get('rule') or '规矩') for message in result['red'])
                if quote:
                    self.red.append(str(result.get('rule') or '规矩') + ' 出处：' + quote)
        for issue in self.index.issues:
            if issue.level == 'red':
                self.red.append(issue.message)
        self.red.extend(f'load {error["file"]}:{error["line"]}: {error["msg"]}' for error in self.state.model.errors)
        items = [dict(name='未覆盖', status='grey', complete=False, changes=[], changed=0, total=0, reasons=[reason]) for reason in dict.fromkeys(self.grey)] + items
        report = dict(source_changed=self.changed, comparison_requested=self.comparison_requested, items=items, paths=self.paths,
                      leads=leads, red=list(dict.fromkeys(self.red)), partial_flows=partial_flows)
        from dataclasses import fields
        from .flow import Event
        self.payload = observation_payload(dict(stamp=self.state.started, baseline=self.runtime.baseline, items=report, paths=self.paths,
                                  events=[{field.name: getattr(event, field.name) for field in fields(Event)}
                                          for event in self.state.events if type(event) is Event]))
        collector = _SIGNALS.get()
        if collector is not None:
            collector.append(report)
        else:
            self.text = signals.render(report)
        return bool(self.red)

    def _cause(self, point, original=None):
        import ast
        import difflib
        from . import runtime as R
        fn = original or point['fn']
        for (_, name), (namespace, before) in self.runtime.constants.items():
            if namespace is not fn.__globals__ or name not in fn.__code__.co_names:
                continue
            after = namespace[name]
            if R.outcome_equal(self.runtime._old_value(namespace, name, before), after):
                continue
            tree = ast.parse((self.cfg.root / point['file']).read_text(encoding='utf-8-sig'))
            line = next((node.lineno for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                         and any(isinstance(target, ast.Name) and target.id == name for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))), 1)
            return dict(name=name, before=before, after=after, file=point['file'], line=line)
        from ..map.common import MapError
        try:
            old = self.runtime._source(point['file'])
        except MapError:
            return None  # Runtime owns the explicit unavailable-baseline reason.
        if old is None:
            return None
        source = (self.cfg.root / point['file']).read_text(encoding='utf-8-sig')
        from .runtime import _functions
        current = dict(_functions(ast.parse(source))).get(point['qual'])
        if current is None:
            return None
        patch = self.runtime.patches.get(point['fn'])
        if patch is not None:
            import copy
            class Shape(ast.NodeTransformer):
                def visit_Constant(self, node):
                    return ast.copy_location(ast.Constant(type(node.value).__name__), node)
            if ast.dump(Shape().visit(copy.deepcopy(patch.node)), include_attributes=False) == ast.dump(Shape().visit(copy.deepcopy(current)), include_attributes=False):
                for before_node, after_node in zip((node for node in ast.walk(patch.node) if isinstance(node, ast.Constant)),
                                                   (node for node in ast.walk(current) if isinstance(node, ast.Constant))):
                    if type(before_node.value) is type(after_node.value) and not R.outcome_equal(before_node.value, after_node.value):
                        return dict(name=point['name'] + ' 的常量', before=before_node.value, after=after_node.value,
                                    file=point['file'], line=after_node.lineno)
        for tag, i, stop, j, end in difflib.SequenceMatcher(a=old.splitlines(), b=source.splitlines()).get_opcodes():
            if tag != 'equal' and current.lineno <= j + 1 <= current.end_lineno:
                return f'{point["name"]}（{point["file"]}:{j + 1}）'
        return None

def pytest_addoption(parser):
    group = parser.getgroup('flowguard')
    group.addoption('--flowguard-base', default=None, help='Compare with this baseline commit')
    group.addoption('--flowguard-deep', action='store_true', help='Include explicit decision probes and mutation-survival checks')
    group.addoption('--flowguard-complete', action='store_true', help='Require the complete ordinary collection without filters')
    group.addoption('--flowguard-rules', default=None, help='Run these changed rules; other fully collected rules are deferred to the cache')
    group.addoption('--flowguard-record-tests', action='store_true', help='Record the ordinary tests actually selected by check')


def _require_complete_collection(config, state):
    options = config.option
    selectors = ('keyword', 'markexpr', 'deselect', 'ignore', 'ignore_glob', 'lf', 'newfirst',
                 'stepwise', 'stepwise_skip', 'collectonly', 'setuponly', 'setupplan')
    overrides = {'testpaths', 'python_files', 'python_classes', 'python_functions',
                 'norecursedirs', 'collect_imported_tests', 'addopts'}
    if (not config.getoption('--flowguard-record-tests') or config.getoption('--flowguard-rules') is not None
            or getattr(config.args_source, 'name', '') == 'ARGS'
            or any(getattr(options, name, None) for name in selectors)
            or any(value.partition('=')[0].strip() in overrides for value in (options.override_ini or ()))
            or state.ordinary_deselected):
        raise pytest.UsageError('complete checks require the full ordinary collection: no paths, filters or collection overrides')



def pytest_load_initial_conftests(early_config):
    _session(early_config)


def _session(config):
    global _CURRENT
    from .imports import prepare, hold_root
    try:
        nested = (_CURRENT is not None and _CURRENT.main_process == os.getpid()
                  and _CURRENT.main_thread == threading.get_ident())
        claimed = prepare(config.rootpath, host=not nested)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error
    if not hasattr(config, '_flowguard_intent'):
        state = config._flowguard_intent = Session(config)
        state.owns_host = claimed
        state.owns_root = hold_root(state.cfg.root)
        state.previous_session, _CURRENT = _CURRENT, state
        config.add_cleanup(state.close)
    config._flowguard_intent.guard_process_exit(config)
    return config._flowguard_intent


def pytest_configure(config):
    config.addinivalue_line('markers', 'rule(ID): this test must actually enter a source anchor of the declared rule')
    _session(config)


def _intent_path(path, config):
    folder = config._flowguard_intent.cfg.intent
    return (path.suffix == '.py' and not path.name.startswith('_')
            and (path.is_relative_to(folder) or path.parent.resolve().is_relative_to(folder.resolve())))


def pytest_collect_file(file_path, parent):
    if _intent_path(file_path, parent.config):
        # The ordinary Python collector calls our makemodule hook for matching files.
        patterns = parent.config.getini('python_files')
        if not parent.session.isinitpath(file_path) and not any(fnmatch.fnmatch(file_path.name, p) for p in patterns):
            return IntentFile.from_parent(parent, path=file_path)


def pytest_pycollect_makemodule(module_path, parent):
    if _intent_path(module_path, parent.config):
        return IntentFile.from_parent(parent, path=module_path)


class IntentFailure(Exception):
    pass


class IntentFile(pytest.File):
    def collect(self):
        state = self.config._flowguard_intent
        model = state.get_model()
        rel = model.cfg.rel(self.path)
        for nodeid in model.declared_items():
            file, _, name = nodeid.partition('::')
            if file != rel:
                continue
            if name == 'load':
                kind, rid, target = 'load', None, None
            else:
                rid, detail = name.split('[', 1)
                detail = detail[:-1]
                target, _, kind = detail.rpartition(':')
                if not target:
                    kind, target = detail, None
                else:
                    target = next((h.target for h in model.rules[rid].homes if h.short == target), target)
            yield IntentItem.from_parent(self, name=name, kind=kind, rule_id=rid, target=target)


class IntentItem(pytest.Item):
    def __init__(self, *, kind, rule_id, target, **kwargs):
        super().__init__(**kwargs)
        self.kind, self.rule_id, self.target = kind, rule_id, target

    def runtest(self):
        with self.config._flowguard_intent.verification():
            return self.run_verified()

    def run_verified(self):
        if hasattr(self, '_evaluation_error'):
            error, traceback = self._evaluation_error
            raise error.with_traceback(traceback)
        result = self._prepared_result if hasattr(self, '_prepared_result') else self.evaluate_verified()
        state = self.config._flowguard_intent
        state.results[self.nodeid] = dict(result, rule=self.rule_id, target=self.target)
        if result['verdict'] == 'red':
            raise IntentFailure('\n'.join(result['red']))

    def evaluate_verified(self):
        state = self.config._flowguard_intent
        model, engine = state.model, state.engine
        declaration = (model.rules.get(self.rule_id) or model.states.get(self.rule_id)
                       or model.structures.get(self.rule_id) or model.flows.get(self.rule_id)
                       or model.anchor_distincts.get(self.rule_id))
        if declaration is not None:
            state.prepare_declaration(declaration)
        if self.kind == 'load':
            red = [f"{e['file']}:{e['line']}: {e['msg']}" for e in model.errors if e['file'] == model.cfg.rel(self.path)]
            result = dict(kind='load', verdict='red', red=red, grey=[], info=[])
        elif self.kind in ('states', 'structure', 'flow', 'anchor_distinct'):
            declaration = (model.states if self.kind == 'states' else model.flows if self.kind == 'flow'
                           else model.anchor_distincts if self.kind == 'anchor_distinct' else model.structures)[self.rule_id]
            result = getattr(engine, 'run_' + self.kind)(declaration)
        else:
            rule = model.rules[self.rule_id]
            if self.kind == 'rules':
                result = engine.run_rules(rule)
            else:
                home = next(h for h in rule.homes if h.target == self.target)
                result = engine.run_live(rule, home) if self.kind == 'live' else engine.run_home(rule, home, self.kind)
        return result

    def repr_failure(self, excinfo):
        return str(excinfo.value) if isinstance(excinfo.value, IntentFailure) else super().repr_failure(excinfo)

    def reportinfo(self):
        state = self.config._flowguard_intent
        model = state.model
        declaration = (model.rules.get(self.rule_id) or model.states.get(self.rule_id) or model.structures.get(self.rule_id)
                       or model.flows.get(self.rule_id) or model.anchor_distincts.get(self.rule_id))
        return self.path, max(0, declaration.line - 1) if declaration else 0, self.name


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    from .calibration import probe_context
    if probe_context(config):
        return  # A private source subtree cannot replace the real collection.
    state = config._flowguard_intent
    state.collected = {i.nodeid for i in items if isinstance(i, IntentItem)}
    if config.getoption('--flowguard-complete', default=False):
        _require_complete_collection(config, state)
        state.complete_collection = {item.nodeid for item in items}
    only = config.getoption('--flowguard-rules')
    if only is None or state.model is None:
        return
    requested = {name for name in only.split(',') if name}
    keys = {r.decides for name, r in state.model.rules.items() if name in requested}
    requested |= {r.id for r in state.model.rules.values() if r.decides in keys}
    keep, drop = [], []
    for item in items:
        (drop if isinstance(item, IntentItem) and item.rule_id is not None and item.rule_id not in requested else keep).append(item)
    state.deferred = {item.nodeid for item in drop}
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    state = session.config._flowguard_intent
    if state.complete_collection is not None and {item.nodeid for item in session.items} != state.complete_collection:
        raise pytest.UsageError('another selection changed the full ordinary collection')
    state.get_model()
    state.observations = Observations(state)
    state.source_items = tuple(item for item in session.items if not isinstance(item, IntentItem) and item.name != SENTINEL)
    session.items[:] = [*state.source_items, *(item for item in session.items if isinstance(item, IntentItem)),
                       *(item for item in session.items if item.name == SENTINEL)]


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session):
    state = session.config._flowguard_intent
    if state.complete_collection is not None and {item.nodeid for item in session.items} != state.complete_collection:
        raise pytest.UsageError('another selection changed the full ordinary collection')
    state.selected = {i.nodeid for i in session.items if isinstance(i, IntentItem)}
    state.ordinary_selected = {i.nodeid for i in session.items if not isinstance(i, IntentItem) and i.name != SENTINEL}


def pytest_deselected(items):
    from .calibration import probe_context
    if any(probe_context(item.config) for item in items):
        return
    if _CURRENT is not None and any(not isinstance(item, IntentItem) for item in items):
        _CURRENT.ordinary_deselected = True


def pytest_keyboard_interrupt(excinfo):
    if _CURRENT is not None and isinstance(excinfo.value, pytest.exit.Exception):
        _CURRENT.early_exit.append(f'the run was ended early by pytest.exit({excinfo.value.msg!r})')


def _missing(state, declared):
    missing = (declared - state.collected) | (declared - state.selected - state.deferred)
    if state.deferred:
        path = state.cfg.cache / 'map.sqlite'
        cached = set()
        if path.is_file():
            with closing(sqlite3.connect(path)) as connection, connection:
                if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='result'").fetchone():
                    cached = {row[0] for row in connection.execute('SELECT item FROM result')}
        missing |= state.deferred - cached
    return sorted(missing)


# flowguard: event SENTINEL_CHECK(config: pytest.Config)
def sentinel(config: pytest.Config):
    state = getattr(config, '_flowguard_intent', None)
    if state is None:
        from .cache import scan, declaration_names
        cfg = load_config(config.rootpath)
        summary = scan(cfg)
        declared, unresolved = declaration_names(cfg, summary)
        incomplete = '; static declaration errors also need correction' if summary['errors'] else ''
        if unresolved:
            incomplete += '; additional scenario bindings are not counted without the plugin: ' + ', '.join(unresolved)
        raise AssertionError(f'FlowGuard plugin not loaded: 0 of {len(declared)} intent items; missing '
                             + ', '.join(declared[:3]) + incomplete + ' -> load -p flowguard.intent.plugin')
    declared = set(state.get_model().declared_items())
    missing = _missing(state, declared)
    state.sentinel = 'failed' if missing else 'ok'
    if missing:
        raise AssertionError(f'only {len(declared) - len(missing)} of {len(declared)} intent items collected or reusable; missing ' + ', '.join(missing[:3]) + ' -> run the complete declared collection')


def _skip_violation(item, call, report):
    policy = item.config._flowguard_intent.cfg.skip_policy
    if (policy == 'forbid' and hasattr(report, 'wasxfail')) or (policy != 'platform' and report.skipped):
        what = ('is marked as expected to fail' if hasattr(report, 'wasxfail') else 'was skipped') if policy == 'forbid' else 'ended skipped'
        reason = report.wasxfail if hasattr(report, 'wasxfail') else _skip_reason(report)
        report.outcome = 'failed'
        guidance = NO_SKIP if policy == 'forbid' else 'this suite allows no skips: a skip hides why the test could not run'
        report.longrepr = f'{item.nodeid} {what} ({reason or "no reason given"}); {guidance}'
        report._flowguard_skip_violation = True
        if hasattr(report, 'wasxfail'):
            del report.wasxfail
        return
    if not report.skipped:
        return
    from _pytest.skipping import evaluate_condition, evaluate_xfail_marks
    if hasattr(report, 'wasxfail') and evaluate_xfail_marks(item) is not None:
        return
    if not hasattr(report, 'wasxfail') and call.when == 'setup':
        for mark in item.iter_markers('skipif'):
            conditions = mark.args or ((mark.kwargs['condition'],) if 'condition' in mark.kwargs else ())
            if not conditions or any(evaluate_condition(item, mark, condition)[0] for condition in conditions):
                return
    error = call.excinfo.value if call.excinfo is not None else None
    hidden = (error.__cause__ or error.__context__) if error is not None else None
    prefix = f'skip raised while handling {type(hidden).__name__}: {hidden}; ' if hidden is not None else 'skip '
    report.outcome = 'failed'
    report.longrepr = prefix + 'not from a skipif or xfail marker; no effective skipif/xfail marker -> fail the test and report the original error'
    report._flowguard_skip_violation = True
    if hasattr(report, 'wasxfail'):
        del report.wasxfail


def _skip_reason(report):
    text = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else str(report.longrepr)
    return text.removeprefix('Skipped: ')


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    state = item.config._flowguard_intent
    from .runtime import _PRIVATE
    if _PRIVATE.get():
        yield
        return
    if isinstance(item, IntentItem):
        # Evaluate before pytest sets up this intent item. A source test replay
        # can then use its own real fixture lifecycle in the same Session.
        from .calibration import session as source_session
        try:
            state.get_model()
            with state.verification(), source_session(state.runtime, state.source_items, nextitem=item):
                item._prepared_result = item.evaluate_verified()
        except Exception as error:
            item._evaluation_error = error, error.__traceback__
    state.last_test = item.nodeid
    capture = None
    with ExitStack() as scopes:
        if not isinstance(item, IntentItem) and item.name != SENTINEL and state.observations is not None:
            scopes.enter_context(state.observations.scope(item))
        from .calibration import probe_context
        if (not isinstance(item, IntentItem) and item.name != SENTINEL and state.model is not None
                and state.model.anchor_index.entries and not probe_context(item.config)
                and (state.model.flows or state.observations.changed or item.config.getoption('--flowguard-record-tests'))):
            from .flow import Capture
            capture = scopes.enter_context(Capture(state.cfg.root, state.model.anchor_index, item.nodeid,
                                                   models=state.model.flows.values() if state.model.flows and not state.observations.changed else None, _ordinary=True))
        try:
            if (isinstance(item, IntentItem) or item.name == SENTINEL
                    or not any(item.iter_markers('rule'))):
                yield
            else:
                with Footprint(state.is_project) as footprint:
                    state.footprints[item.nodeid] = footprint
                    yield
        finally:
            if capture:
                scopes.close()
                state.events.extend(capture.events)
                state.anchor_issues.extend(capture.issues)
    if (not isinstance(item, IntentItem) and item.name != SENTINEL and state.observations is not None
            and state.readings.get(item.nodeid, {}).get('outcome') == 'passed'):
        state.observations.old_path(item, nextitem)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    from .runtime import _PRIVATE
    if _PRIVATE.get():
        return
    state = item.config._flowguard_intent
    if state.complete_collection is not None and report.when == 'teardown':
        state.completed.add(item.nodeid)
    _skip_violation(item, call, report)
    state.durations[item.nodeid] = state.durations.get(item.nodeid, 0.0) + report.duration
    if item.name == SENTINEL and report.when == 'call':
        state.sentinel = 'ok' if report.passed else 'failed'
    if isinstance(item, IntentItem) or item.name == SENTINEL:
        return
    if report.when == 'call' and report.passed:
        for marker in item.iter_markers('rule'):
            entered = set(state.footprints[item.nodeid].keys())
            model = state.get_model()
            rid = marker.args[0] if marker.args else ''
            rule = model.rules.get(rid)
            homes = [state.engine.home_sites(h.target)[0] for h in rule.homes] if rule else []
            from .sites import unwrap
            if not any((code.co_filename, code.co_firstlineno) in entered for fn in homes if fn is not None and (code := getattr(unwrap(fn), '__code__', None))):
                report.outcome = 'failed'
                report.longrepr = f'marked but never enters {rid}: no declared source anchor ran -> call the real source anchor or correct the marker'
    if report.failed or report.skipped or report.when == 'call':
        captured = '\n'.join(str(text) for _, text in getattr(report, 'sections', []))
        if getattr(report, '_flowguard_skip_violation', False):
            kind, reason = 'code', ('unguarded skip' if state.cfg.skip_policy == 'platform' else 'forbidden test outcome')
        else:
            kind, reason = classify(call.when, call.excinfo, state.cfg, text=str(report.longrepr or '') + captured) if report.failed else ('', '')
        state.readings[item.nodeid] = dict(outcome=report.outcome, kind=kind, reason=reason, phase=call.when, seconds=state.durations[item.nodeid])
    elif item.nodeid in state.readings:
        state.readings[item.nodeid]['seconds'] = state.durations[item.nodeid]


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    outcome = yield
    report = outcome.get_result()
    if report.passed and isinstance(collector, pytest.Module) and collector.path.name != SENTINEL + '.py':
        collector.config._flowguard_intent.ordinary_files.add(collector.config._flowguard_intent.cfg.rel(collector.path))
    violation = report.skipped
    if violation:
        call = getattr(report, 'call', None)
        error = call.excinfo.value if call is not None and call.excinfo is not None else None
        hidden = (error.__cause__ or error.__context__) if error is not None else None
        cause = f' while handling {type(hidden).__name__}: {hidden}' if hidden is not None else ''
        report.outcome = 'failed'
        policy = collector.config._flowguard_intent.cfg.skip_policy
        if policy != 'platform':
            guidance = NO_SKIP if policy == 'forbid' else 'this suite allows no skips: a skip hides why the tests could not run'
            report.longrepr = f'{report.nodeid} was skipped while it was collected ({_skip_reason(report)}); {guidance}'
        else:
            report.longrepr = (f'{report.nodeid} skipped while collected, not from a skipif or xfail marker; '
                               f'collection skip{cause}: {report.longrepr!s} -> report the missing dependency or original error; do not skip collection')
    if report.failed:
        state = collector.config._flowguard_intent
        kind, reason = ('code', 'unguarded collection skip') if violation else classify_collection(str(report.longrepr), state.cfg)
        state.readings[report.nodeid] = dict(outcome='failed', kind=kind, reason=reason, phase='collect', seconds=0.0)


def _meta(con, name, value):
    con.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', (name, _json(value)))


def _save_readings(con, state):
    con.executemany('INSERT OR REPLACE INTO reading VALUES(?,?,?,?,?,?,?)',
                    [(test, r['outcome'], r['kind'], r['reason'], r['phase'], r['seconds'], state.started)
                     for test, r in state.readings.items()])


def _save_ordinary_collection(con, session, state):
    options = session.config.option
    if (session.exitstatus not in {pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED} or state.session_errors or state.early_exit or state.ordinary_deselected
            or options.collectonly or getattr(options, 'setuponly', False) or getattr(options, 'setupplan', False)
            or options.keyword or options.markexpr or getattr(options, 'deselect', ())
            or any('::' in arg for arg in session.config.args)):
        return
    from .cache import save_test_collection
    files = {file: set() for file in state.ordinary_files}
    for test in state.ordinary_selected:
        if test.partition('::')[0] in files:
            files[test.partition('::')[0]].add(test)
    files = {file: tests for file, tests in files.items() if tests <= state.readings.keys()
             and not any(test.partition('::')[0] == file and reading['phase'] == 'collect'
                         for test, reading in state.readings.items())}
    save_test_collection(con, files, state.started)


def _completion_policy(session, state, declared):
    if session.exitstatus != pytest.ExitCode.OK:
        return
    options = session.config.option
    recording = session.config.getoption('--flowguard-record-tests')
    if not recording and (options.collectonly or getattr(options, 'setuponly', False) or getattr(options, 'setupplan', False)):
        return
    strict = state.cfg.skip_policy == 'forbid'
    if not strict and not recording:
        return
    problems = list(state.early_exit) if strict or recording else []
    failed = sorted(test for test, reading in state.readings.items() if reading['outcome'] == 'failed')
    if failed:
        problems.append(f'{len(failed)} test(s) failed ({", ".join(failed[:3])})')
    missing = sorted(state.ordinary_selected - state.readings.keys())
    if missing:
        problems.append(f'{len(missing)} collected test(s) never ran ({", ".join(missing[:3])})')
    if recording and declared:
        if state.sentinel != 'ok':
            problems.append('the intent sentinel did not execute successfully')
        if state.selected - state.results.keys():
            problems.append('selected intent items never ran')
    if problems:
        reason = '; '.join(problems)
        guidance = NO_SKIP if strict else 'selected tests did not finish; do not report this check as passed'
        print('\nFlowGuard: ' + reason + '; ' + guidance, file=sys.stderr)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        state.session_errors = problems
        failed = set(missing)
        if state.early_exit and state.last_test in state.ordinary_selected:
            failed.add(state.last_test)
        for test in failed:
            state.readings[test] = dict(outcome='failed', kind='code', reason=reason, phase='run', seconds=state.durations.get(test, 0.0))


def pytest_sessionfinish(session, exitstatus):
    state = session.config._flowguard_intent
    with state.verification():
        result = finish_verified(session, exitstatus)
    # Verification and transaction completion precede optional terminal output.
    if state.observations is not None and state.observations.text:
        from .differences import display
        try:
            display(state.observations.text)
        except (OSError, ValueError) as error:
            state.observations.payload['display_unavailable'] = type(error).__name__
            path = state.cfg.cache / 'map.sqlite'
            if path.is_file():
                try:
                    with closing(sqlite3.connect(path, timeout=30)) as con, con:
                        _meta(con, 'runtime_observations', state.observations.payload)
                except sqlite3.Error:
                    pass  # The earlier committed verdict remains authoritative.
    return result


def finish_verified(session, exitstatus):
    state = session.config._flowguard_intent
    from .calibration import probe_context
    if probe_context(session.config):
        declared = set(state.model.declared_items()) if state.model is not None else set()
        _completion_policy(session, state, declared)
        return  # Unselected intent is not part of this ordinary-test probe.
    model = state.get_model()
    declared = set(model.declared_items())
    if state.complete_collection is not None:
        unfinished = state.complete_collection - state.completed
        if unfinished:
            state.session_errors.append('complete collection did not finish: ' + ', '.join(sorted(unfinished)[:3]))
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    _completion_policy(session, state, declared)
    for identifier, rule in model.rules.items():
        required = {model.file_of[identifier] + '::' + name for name in model.items_of(rule)}
        if required <= state.results.keys():
            parts = [state.results[item] for item in required]
            owner = model.file_of[identifier] + '::' + identifier + '[rules]'
            state.results[owner]['own_contract'] = state.engine.contract_summary(rule, parts=parts)
    for identifier, flow in model.flows.items():
        item = f'{model.file_of[identifier]}::{identifier}[flow]'
        if item not in state.results:
            continue
        result = state.engine.run_flow(flow, state.events, state.anchor_issues)
        state.results[item] = dict(result, rule=identifier, target=None)
        if result['verdict'] == 'red':
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    if state.observations is not None and state.observations.report():
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    exitstatus = session.exitstatus
    missing = _missing(state, declared)
    attempt = dict(declared=len(declared), collected=len(state.collected), selected=len(state.selected),
                   deferred=len(state.deferred), missing=missing, sentinel=state.sentinel, exit=int(exitstatus),
                   errors=state.session_errors, stamp=state.started, deep=model.deep)
    if state.complete_collection is not None:
        attempt['complete_collection'] = dict(collected_nodeids=sorted(state.complete_collection),
                                               completed_nodeids=sorted(state.completed))
    observed = state.observations is not None and (state.observations.records or state.observations.paths or state.observations.red)
    if not declared and not state.footprints and not observed:
        # Standalone pytest does not build a map, but must retire old traces
        # for a test it ran without recording. Never refresh them by implication.
        path = state.cfg.cache / 'map.sqlite'
        if path.is_file() and state.readings:
            with closing(sqlite3.connect(path, timeout=30)) as con:
                con.executescript(SCHEMA)
                with con:
                    con.execute('BEGIN IMMEDIATE')
                    _meta(con, 'intent_attempt', attempt)
                    if state.observations is not None and state.observations.payload is not None:
                        _meta(con, 'runtime_observations', state.observations.payload)
                    _save_readings(con, state)
                    _save_ordinary_collection(con, session, state)
        return
    with closing(state.get_map()) as mapping:
        con = mapping.con
        con.executescript(SCHEMA)
        con.execute('BEGIN IMMEDIATE')
        _meta(con, 'intent_attempt', attempt)
        if state.observations is not None and state.observations.payload is not None:
            _meta(con, 'runtime_observations', state.observations.payload)
        if not missing and state.sentinel == 'ok' and not state.session_errors:
            _meta(con, 'intent_collection', attempt)
            if not model.deep:
                con.execute("DELETE FROM result WHERE item LIKE '%:live]'")
            for item, result in state.results.items():
                con.execute('INSERT OR REPLACE INTO result VALUES(?,?,?,?,?)', (item, result['rule'], result['verdict'], _json(result), state.started))
            from .deps import record
            from .cache import save_dependencies
            fresh = {result['rule'] for result in state.results.values() if result['rule'] is not None}
            records = {}
            for rid in fresh:
                declaration = (model.rules.get(rid) or model.states.get(rid) or model.structures.get(rid)
                               or model.flows.get(rid) or model.anchor_distincts.get(rid))
                records[rid] = record(state.cfg, model, declaration,
                                      [r for r in state.results.values() if r['rule'] == rid], mapping)
            save_dependencies(con, records)
        _save_readings(con, state)
        _save_ordinary_collection(con, session, state)
        con.commit()
