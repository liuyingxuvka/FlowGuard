"""Ordinary pytest owns execution; this plugin adds intent items and source footprints.

PYTEST_DONT_REWRITE: `python -m flowguard check` imports this module before its pytest session loads it
with `-p`; the plugin is no test module, so pytest skips rewriting it instead of warning that it came late.
"""
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
        self.calibration_facts, self.anchor_facts = {}, {}
        self._runtime = None
        self.observations = None
        self.source_items = ()
        self.complete_collection = None
        self.ledger_result = None
        self.sentinel_ledger = False
        self.session_red = []            # reds only the session decides: a failed JUnit testcase

    @property
    def runtime(self):
        """The session's one runtime; Observations gives it its baseline. Made only when something needs
        it before then, so a session does not resolve its baseline twice."""
        if self._runtime is None:
            from .runtime import Runtime
            self._runtime = Runtime(self.cfg.root)
        return self._runtime

    @runtime.setter
    def runtime(self, value):
        self._runtime = value

    @contextmanager
    def verification(self):
        from .anchors import _execution_session
        from .calibration import _execution_session as calibrated_session
        with calibrated_session(self.cfg.root, facts=self.calibration_facts), \
                _execution_session(self.cfg.root, facts=self.anchor_facts):
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
                elif getattr(binding, 'anchor', None) and binding.anchor.calibrated_by and not binding.anchor.fields:
                    # A `fields` anchor is checked on its tests' calls; its calibrated test is not rerun.
                    _prepare(self.cfg.root, binding.anchor)

    def rule_contracts(self):
        """A rule whose items all ran in this session takes its contract from those actual results;
        a Flow with that rule as a lower model reads it. Rerunning it after more items ran is the same."""
        model = self.model
        for identifier, rule in model.rules.items():
            required = {model.file_of[identifier] + '::' + name for name in model.items_of(rule)}
            if required <= self.results.keys():
                parts = [self.results[item] for item in required]
                owner = model.file_of[identifier] + '::' + identifier + '[rules]'
                self.results[owner]['own_contract'] = self.engine.contract_summary(rule, parts=parts)

    def get_map(self):
        if self.map is None:
            from flowguard.structure import build
            self.map = build(self.cfg.root, roots=self.cfg.roots)
        return self.map

    def ledger(self):
        """The fallback ledger compared with the map once per session; a failed comparison is red with its error."""
        if self.ledger_result is None:
            from . import cache, ledger
            from ..map.common import MapError
            if not ledger.path(self.cfg).is_file():
                # Without a ledger only its deletion is checked, from the baseline diff the session already read.
                observed = self.observations
                gone = observed is not None and ledger.LEDGER in observed.differs
                self.ledger_result = ledger.removed(observed.runtime.baseline or 'HEAD') if gone else ledger.Result(present=False)
                return self.ledger_result
            try:
                baseline = self.config.getoption('--flowguard-base', default=None) or cache.session_baseline(self.cfg)
                self.ledger_result = ledger.evaluate(self.cfg, self.get_map(), baseline=baseline)
            except (MapError, OSError, UnicodeError) as error:
                self.ledger_result = ledger.Result(present=True, red=[ledger.Finding(
                    f'兜底账本没有核对完：{type(error).__name__}: {error}', ('改正这个错误后重新运行测试',))])
        return self.ledger_result


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


def _canonical(point, name):
    """The declared name of a source parameter (`ELIGIBLE(days=overdue_days)` reads overdue_days as days)."""
    anchor = point.get('anchor')
    return next((p.name for p in anchor.parameters if p.alias == name), name) if anchor else name


def _spelled(point, name):
    """The source parameter spelling of a declared name."""
    anchor = point.get('anchor')
    return next((p.source for p in anchor.parameters if p.name == name), name) if anchor else name


def _declared(point, inputs):
    return {_canonical(point, name): value for name, value in inputs.items()}


def _partition_copy(axes, part):
    from .differences import Partition, Region
    return ({name: list(pool) for name, pool in axes.items()},
            Partition([Region(dict(region.inputs), region.label) for region in part.regions],
                      part.complete, list(part.reasons), part.representative_points), [])


_UNHOOKABLE = '函数：调用处的结果不能比较'      # the end of a lost reading's reason when the call became a generator or coroutine
_OPAQUE = '回放结果不是可以比较的简单数据'


def _restore_step(lost):
    """The first way out of a lost observation, for what made it grey."""
    if lost.startswith(_OPAQUE):
        return '恢复可观察：让这次调用像基准代码那样返回可以比较的简单数据（数字、字符串、布尔、None，或由它们组成的列表、元组、字典）；'
    if lost.endswith(_UNHOOKABLE):
        return '恢复可观察：让它像基准代码那样直接返回结果，不改成生成器或协程函数；'
    return '恢复可观察：改掉上面那一处，让这次调用不再写文件、数据库、进程或网络；'


class Observations:
    """Connect loaded source points to the one runtime during ordinary tests."""
    def __init__(self, state):
        import ast
        from . import anchors, cache, differences
        from .runtime import Runtime, _functions, _binding_facts
        from ..map.common import MapError, git_run, read_source
        from ..structure.readers.registry import language_for
        self.state, self.cfg = state, state.cfg
        self.comparison_requested = bool(state.config.getoption('--flowguard-base', default=None))
        task = cache.session_baseline(self.cfg, remember=False)
        self.baseline_kind = 'base' if self.comparison_requested else 'task' if task else 'HEAD'
        baseline = state.config.getoption('--flowguard-base', default=None) or task or 'HEAD'
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
            self.differs = {os.fsdecode(value) for value in changed.split(b'\0') if value}
            # A changed TS/JS, Prisma, SQL or other mapped file is a change too: the map checks read it.
            self.mapped = {os.fsdecode(value) for value in (changed + added).split(b'\0')
                           if value and language_for(os.fsdecode(value)) not in (None, 'python')}
        except MapError:
            self.files = set()
            self.differs = set()
            self.mapped = set()
        self.points = {a.target: dict(anchor=a, target=a.target, file=a.file, module=a.module, qual=a.qual,
                                     name=a.name, kind=a.kind, node=None)
                       for a in self.index.entries if a.kind in ('sensor', 'event') and a.source_role != 'test'}
        self.changed, self.records, self.pairs, self.red, self.grey, self.paths = bool(self.files), [], [], [], [], []
        self.steps = {}         # the next steps to copy under a red line, by its subject
        self.metadata, self.bound, self.event_codes, self.payload = {}, {}, {}, None
        # Comparisons by fingerprint (_reuse): the key of each reading index, the stored results this
        # session kept, the new results to store, and the engine identity and stored entries, read once.
        self.keys, self.reused, self.fresh, self.engine_digest, self.stored = {}, {}, {}, None, None
        self.structure = None
        self.event_record = self.capture = None
        self.request, self.text = _TRY.get(), ''
        self.session_red = []       # set by report(): the reds no failed test carries
        self.rules = {}
        for rule in state.model.rules.values():
            for home in rule.homes:
                if not hasattr(home, 'scenario'):
                    self.rules.setdefault(home.target, []).append(rule)
        self.by_file, self.rels = {}, {}
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
        from .runtime import _PRIVATE, unguarded
        token = _PRIVATE.set(True)
        try:
            # A module first imported inside a replayed call is bound by FlowGuard, not by that call.
            with unguarded():
                if self.capture is not None:
                    self.capture.loaded(module)
                return self._bind_module(module)
        finally:
            _PRIVATE.reset(token)

    def _bind_module(self, module):
        import inspect
        import types
        filename = getattr(module, '__file__', None)
        if not filename:
            return
        if filename not in self.rels:
            self.rels[filename] = self.cfg.rel(filename)       # every test binds every loaded module again
        for point in self.by_file.get(self.rels[filename], ()):
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
                if self.event_record is not None:
                    self.event_record.add_code(fn.__code__, point['name'])
                continue
            try:
                anchor = point['anchor']
                original = self.scopes.enter_context(self.runtime.hook(fn, name=point['name'],
                    axes=lambda original, bound, point=point: self._at_call(point, original, bound),
                    fields=anchor.fields if anchor else (), line=anchor.line if anchor else 0))
                point['original'] = original
            except (ValueError, TypeError, sites.NotMutable) as error:
                if not self._watch_unhookable(point, fn, str(error)):
                    self.grey.append(point['name'] + ': ' + str(error))

    def _watch_unhookable(self, point, fn, reason):
        """A generator or coroutine function cannot be hooked, so its result is never compared. When the
        baseline code of an anchored or ruled point is a plain function, the first entry of a test's call
        replays that baseline with the same arguments; a clean replay makes the grey a lost observation.
        A test that never enters it lists the hook's reason as before."""
        import inspect
        kind = ('协程' if inspect.iscoroutinefunction(fn) else '异步生成器' if inspect.isasyncgenfunction(fn)
                else '生成器' if inspect.isgeneratorfunction(fn) else '')
        if not kind or not self.changed or not self._losable(point):
            return False
        import dis
        entered = []

        def entry(frame, event, arg):
            # Python 3.11's trace also reports the call that only creates the generator (RETURN_GENERATOR):
            # its body has not started, so that is not an entry.
            created = frame.f_lasti >= 0 and dis.opname[frame.f_code.co_code[frame.f_lasti]] == 'RETURN_GENERATOR'
            if event == 'call' and not created and not entered:
                entered.append(True)
                self._unhookable_call(point, fn, kind, frame.f_locals)

        record = self.runtime.record(codes=[(fn.__code__, point['name'])], callback=entry, entry_only=True)
        self.scopes.enter_context(record)

        def closed():
            if not entered:
                self.grey.append(point['name'] + ': ' + reason)
            # The recorder keeps a failed callback's error as an issue; it is this point's grey, with its text.
            self.grey.extend(point['name'] + ': ' + issue for issue in record.issues)

        self.scopes.callback(closed)
        return True

    def _unhookable_call(self, point, fn, kind, values):
        import inspect
        from .runtime import Reading
        signature = inspect.signature(fn)
        args, kwargs = [], {}
        for parameter in signature.parameters.values():
            value = values[parameter.name]
            if parameter.kind is parameter.POSITIONAL_ONLY:
                args.append(value)
            elif parameter.kind is parameter.VAR_POSITIONAL:
                args.extend(value)
            elif parameter.kind is parameter.VAR_KEYWORD:
                kwargs.update(value)
            else:
                kwargs[parameter.name] = value
        reading = Reading(point['name'], fn.__module__ + ':' + fn.__qualname__, test=self.runtime.test,
                          baseline=self.runtime.baseline, status='grey',
                          reasons=[f'{fn.__qualname__} 现在是{kind}' + _UNHOOKABLE])
        self.records.append((len(self.runtime.readings), point, None, [], None))
        self.runtime.readings.append(reading)
        self.runtime._lost(reading, fn, signature.bind(*args, **kwargs))

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
            if any(getattr(parameter, 'alias', '') for parameter in parameters):
                current = anchors._declared_names(current, parameters)[0]      # read under the declared names
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

    def _reuse(self, point, original, bound):
        """The comparison an earlier session computed under this call's fingerprint, as the reading the
        runtime keeps in place of a replay; None when there is none or no key can be taken. The key covers
        FlowGuard's own code, the baseline, the anchor's file and the project configuration, the bodies of the
        target and of the project functions it calls, the current values of the constants they read and the
        call's arguments. Only a session with a change has a key (its map is built already); a point with rules,
        `fields`, same-name copies or a try request has none, and nor has one whose inputs the map cannot
        read completely (deps.comparison_inputs)."""
        from . import cache, deps, runtime as R
        anchor = point['anchor']
        if (not self.changed or self.rules.get(point['target']) or not self.runtime.baseline
                or anchor is not None and (anchor.fields or len(self.index.named(point['name'], 'sensor')) > 1)
                or self.request and self.request['target'] == point['target']):
            return None
        graph = self.state.get_map()
        fingerprints, constants, reasons = deps.comparison_inputs(graph, point['target'])
        values = [(module, name, _metadata_value(vars(sys.modules[module]).get(name, ...)))
                  for module, name in constants if module in sys.modules]
        arguments = [(name, _metadata_value(value)) for name, value in bound.arguments.items()]
        if reasons or len(values) != len(constants) or any(item[-1] is None for item in [*values, *arguments]):
            return None
        if self.engine_digest is None:
            self.engine_digest = deps.Now(self.cfg, graph)('engine:')
        key = deps.digest((self.engine_digest, self.runtime.baseline, point['target'], point['name'],
                           deps.file_digest(self.cfg.root / point['file']), deps.file_digest(self.cfg.root / 'pyproject.toml'),
                           sorted(fingerprints.items()), values, arguments))
        index = len(self.runtime.readings)
        self.keys[index] = key
        if self.stored is None:
            self.stored = cache.comparisons(self.cfg, self.runtime.baseline)
        if key not in self.stored:
            return None
        self.reused[index] = json.loads(self.stored[key])
        self.records.append((index, point, None, [], self._cause(point, original)))
        self.pairs.append((index, point, []))
        return R.Reading(point['name'], self.reused[index]['target'], test=self.runtime.test, baseline=self.runtime.baseline)

    def _classes_at_call(self, point, original, bound):
        from . import runtime as R
        if problem := self.runtime.safety(original, bound.arguments):
            self.records.append((len(self.runtime.readings), point, None, [problem], None))
            return {}  # Runtime still records its refusal and makes the one real call.
        if (reading := self._reuse(point, original, bound)) is not None:
            return reading
        try:
            axes, part, unknown = self._partition(point, original, bound)
        except (ValueError, TypeError, OSError, SyntaxError, AttributeError) as error:
            axes, part, unknown = {}, None, [str(error)]
        part, unknown = self._widen(point, original, axes, part, unknown)
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
        fields = {name for name, _ in point['anchor'].fields} if point['anchor'] else set()
        for rule in self.rules.get(point['target'], ()):
            if not set(rule.fields) <= axes.keys() | fields:
                self.grey.append(rule.id + ': this real context does not expose all rule inputs'
                                 + (f'（参数和 fields 里没有 {", ".join(sorted(set(rule.fields) - axes.keys() - fields))}）' if fields else ''))
                continue
            values = self.state.engine.rr_space(rule.decides)[2]
            for field in [name for name in rule.fields if name not in fields]:
                pool = axes.setdefault(field, [])
                additions = [*values.get(field, ()), *(row.inputs[field] for row in rule.live_rows if field in row.inputs)]
                pool.extend(value for value in additions if not any(R.outcome_equal(value, prior) for prior in pool))
        peers, measured = [], []
        declared = {_canonical(point, name): value for name, value in bound.arguments.items()}
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
                    arguments = inspect.signature(other['original']).bind(
                        **{_spelled(other, name): value for name, value in declared.items()})
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
                self.runtime.observe(other['original'], arguments, owner=other['fn'], name=point['name'],
                                     axes={_spelled(other, name): values for name, values in axes.items()}, private=True)
            except Exception:
                pass  # Raised rows, not the synthetic final call, decide agreement.
            finally:
                R._PRIVATE.reset(token)
            if len(self.runtime.readings) > index:
                peers.append((self.runtime.readings[index], other))
        self.records.append((len(self.runtime.readings), point, part, unknown, self._cause(point, original)))
        self.pairs.append((len(self.runtime.readings), point, peers))
        return {_spelled(point, name): values for name, values in axes.items()}

    @contextmanager
    def scope(self, item):
        from .imports import observe_imports
        self.runtime.test = item.nodeid
        self.event_codes, self.event_record = {}, None
        with ExitStack() as self.scopes:
            self.bound = {}
            with observe_imports(self.cfg.root, self._module):
                for name in {point['module'] for point in self.points.values()}:
                    if (module := sys.modules.get(name)) is not None:
                        self._module(module)
                entered = []          # the runtime record's own entries of the event code objects
                if self.changed and any(point['kind'] == 'event' for point in self.points.values()):
                    # Event code objects only, with local events; later imports add theirs.
                    self.event_record = self.runtime.record(list(self.event_codes.values()), entry_only=True, events=entered)
                    try:
                        with self.event_record:
                            yield
                    finally:
                        self.event_record = None
                else:
                    yield
                self.actual_path = [event['anchor'] for event in entered if event['phase'] == 'call']

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
            with self.runtime.record(codes=list(codes.values()), private=True, entry_only=True, events=old):
                result = self.runtime.replay(item, nextitem=nextitem)
        if result['status'] == 'ok':
            before = [event['anchor'] for event in old if event['phase'] == 'call']
            self.paths.append(dict(test=item.nodeid, before=before, after=self.actual_path))
        else:
            self.grey.extend(item.nodeid + ': ' + reason for reason in result['reasons'])

    @staticmethod
    def _rule_rows(point, reading):
        """(rule inputs, outcome) of each call one reading holds, and why a call's fields were not read.
        The replayed rows when the replay is valid, else the real call: a refused replay still leaves the
        real call's own inputs and outcome. A `fields` anchor's values join each call's parameters."""
        replayed = reading.status == 'ok' and reading.rows
        if not (point['anchor'] and point['anchor'].fields):
            return (reading.rows if replayed else [reading.actual] if reading.actual else []), []
        if replayed:
            rows = [({**inputs, **values}, outcome) for (inputs, outcome), values in zip(reading.rows, reading.field_rows)
                    if values is not None]
        else:
            rows = [({**reading.actual[0], **reading.fields}, reading.actual[1])] \
                if reading.actual and reading.fields is not None else []
        return rows, list(reading.field_reasons)

    def rule_calls(self, rule, home):
        """The calls of a `fields` anchor the tests reached in this session, as (rule inputs, outcome,
        test), and why fields could not be read. `calibrated_by=` keeps the calls of that one test."""
        calls, reasons = [], []
        selector = home.anchor.calibrated_by
        for index, point, part, unknown, cause in self.records:
            if point['target'] != home.target or index >= len(self.runtime.readings):
                continue
            reading = self.runtime.readings[index]
            if selector and not self._named_test(reading.test, selector):
                continue
            rows, why = self._rule_rows(point, reading)
            calls.extend((inputs, outcome, reading.test) for inputs, outcome in rows)
            reasons.extend(why)
        return calls, list(dict.fromkeys(reasons))

    def _named_test(self, nodeid, selector):
        file, _, name = selector.partition('::')
        test_file, _, test_name = nodeid.partition('::')
        return test_name == name and (self.state.config.rootpath / test_file).resolve() == (self.cfg.root / file).resolve()

    def _rule_signals(self):
        """Check already observed values; partial pytest never invents full receipts."""
        from . import cells as C
        from .engine import CONFLICT, PredicateError, outcome_eq
        from .loader import item_names
        from .sources import parse
        engine, checked, quoted = self.state.engine, {}, set()
        for index, point, part, unknown, cause in self.records:
            if index >= len(self.runtime.readings):
                continue
            reading = self.runtime.readings[index]
            rows, reasons = self._rule_rows(point, reading)
            for rule in self.rules.get(point['target'], ()):
                if point['anchor'] and point['anchor'].fields and any(
                        self.state.model.file_of[rule.id] + '::' + name in self.state.results
                        for name in item_names(rule.id, [point['target']])[1:]):
                    continue    # this session's own items of the rule on the anchor report its calls
                self.grey.extend(rule.id + ': ' + reason for reason in reasons)
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
            if not model.nodes:      # a transitions template: any anchored call that read its state
                if not any(t.state in event.states for event in state.events for t in model.transitions):
                    continue
            elif not observed_anchors.intersection(node.reference for node in model.nodes):
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
            actual = {key(_declared(point, inputs)): value for inputs, value in reading.rows}
            changes = {key(_declared(point, inputs)): old for inputs, old, new in reading.changed}
            if index in self.reused:
                result = self.reused[index]['result']
            elif part is not None:
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
                if index in self.keys and reading.status == reading.comparison_status == 'ok':
                    self.fresh[self.keys[index]] = json.dumps(dict(target=reading.target, result=result), ensure_ascii=False)
            else:
                from dataclasses import asdict
                result = asdict(reading)
                result['reasons'] += unknown
                result['complete'] = False
            # `lost` marks a point whose loss is red or listed under [unverified]; an unanchored point
            # without a rule is never red, so its grey stays listed as unverified.
            result.update(name=point['name'], file=point['file'], line=getattr(point['anchor'], 'target_line', 0) or point['node'].lineno,
                          unanchored=point['anchor'] is None, lost=reading.lost if self._losable(point) else '')
            if reading.status != 'ok':
                result.update(complete=False, reasons=reading.reasons, status='grey', rows=[])
            if cause:
                result['cause'] = cause
            items.append(result)
        from .anchors import project
        def projected(point, value):
            try:
                return True, project(point['anchor'], value) if point['anchor'] else value
            except ValueError as error:
                self.grey.append(point['name'] + ': ' + str(error))
                return False, None
        reported = set()
        for index, point, peers in self.pairs:
            if index >= len(self.runtime.readings):
                continue
            current = self.runtime.readings[index]
            for peer, other_point in peers:
                if frozenset((current.target, peer.target)) in reported:
                    continue  # The other copy's own observation already reported this pair.
                now = {key(_declared(point, inputs)): value for inputs, value in current.rows}
                other = {key(_declared(other_point, inputs)): value for inputs, value in peer.rows}
                def nearest(signature):       # report the smallest differing input, whatever the set order
                    def size(text):
                        try:
                            return 0, abs(float(text)), float(text)
                        except ValueError:
                            return 1, 0, text
                    return [size(value) for _, _, value in signature]
                for signature in sorted(now.keys() & other.keys(), key=nearest):
                    if current.status != 'ok' or peer.status != 'ok':
                        continue
                    (mine_ok, mine), (theirs_ok, theirs) = projected(point, now[signature]), projected(other_point, other[signature])
                    if mine_ok and theirs_ok and not R.outcome_equal(mine, theirs):
                        reported.add(frozenset((current.target, peer.target)))
                        owner = other_point if other_point['anchor'] and other_point['anchor'].owner else None
                        where = (f'{point["file"]}:{getattr(point["anchor"], "target_line", 0)}' if owner else '')
                        self.red.append(f'同名锚点 {current.name}：' + (where + ' ' if where else '') + ', '.join(f'{name}={value}' for name, kind, value in signature) + '，'
                                        + (f'{C.show(mine)}（负责人 {owner["file"]}:{owner["anchor"].target_line} 给 {C.show(theirs)}）' if owner
                                           else f'{C.show(mine)} ≠ {C.show(theirs)}（{self._place(current.target)} ≠ {self._place(peer.target)}）')
                                        + f' -> 让 {point["qual"]} 和{"负责人" if owner else "同名副本"}一致，或改用不同的锚点名并写 distinct')
                        break
                        break
        unverified, failed_items = [], set()      # an intent item's red is already a failed test
        for item, result in self.state.results.items():
            if result.get('verdict') == 'grey':
                unverified.extend(item.partition('::')[2] + '：' + str(reason) for reason in result.get('grey', ()) or ['未验证'])
            if result.get('red'):
                rule = self.state.model.rules.get(result.get('rule'))
                quote = ''
                if rule:
                    from .sources import parse
                    source = parse(rule.source)
                    quote = source.quote or source.text
                lines = [signals.constraint(message, result.get('rule') or '规矩') for message in result['red']]
                if quote:
                    lines.append(str(result.get('rule') or '规矩') + ' 出处：' + quote)
                self.red.extend(lines)
                failed_items.update(lines)
        unverified.extend(self._lost())
        # Each violated rule names the next step: correct the code, or the rule first when the need changed.
        for rule in self.state.model.rules.values():
            if any(str(message).partition('：')[0].partition(': ')[0].partition(' 出处')[0] == rule.id for message in self.red):
                homes = '、'.join(self._place(home.target) for home in rule.homes if not hasattr(home, 'scenario')) or rule.id + ' 的绑定'
                self.steps.setdefault(rule.id, [
                    f'改代码，让 {homes} 符合规则 {rule.id}；',
                    f'需求确实变了：先用 python -m flowguard req add 存下新的原话，再改规则 {self.state.model.file_of[rule.id]}:{rule.line}'])
        for issue in self.index.issues:
            if issue.level == 'red':
                self.red.append(issue.message)
            elif issue.code == 'source-syntax':
                self.grey.append(f'{issue.file}' + (f':{issue.line}' if issue.line else '')
                                 + ': cannot be parsed, only this file is unverified: ' + issue.message)
        if self.changed or self.mapped:
            # Static leads and owner writes need no replay: an old value still elsewhere (rules too),
            # a new spelling of a label, a new write outside a data owner's writers, a pair, a value.
            from . import anchors, owners
            graph = self.state.get_map()       # the map's index also holds the TS/JS owners (check --static reads it)
            found = owners.static_findings(self.cfg, graph, anchors.collect(graph), self.runtime.baseline)
            self.red.extend(found.red)
            leads.extend(found.leads)
            self.structure = found.summary         # the session brief's count of open structure problems
        self.red.extend(f'load {error["file"]}:{error["line"]}: {error["msg"]}' for error in self.state.model.errors)
        items = [dict(name='未覆盖', status='grey', complete=False, changes=[], changed=0, total=0, reasons=[reason]) for reason in dict.fromkeys(self.grey)] + items
        fallbacks = self.state.ledger()
        report = dict(session=True, baseline=self.runtime.baseline, baseline_kind=self.baseline_kind,
                      source_changed=self.changed or bool(self.mapped), comparison_requested=self.comparison_requested,
                      items=items, paths=self.paths,
                      leads=leads, red=list(dict.fromkeys(self.red)), steps=self.steps, partial_flows=partial_flows, unverified=unverified,
                      ledger_red=[dict(text=finding.text, fix=list(finding.fix)) for finding in fallbacks.red])
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
        # The reds no failed test carries: a lost observation, a copy, a static finding; the ledger's
        # unless the sentinel test already failed on it.
        self.session_red = [*(line for line in report['red'] if line not in failed_items),
                            *([] if self.state.sentinel_ledger else [finding['text'] for finding in report['ledger_red']])]
        return bool(self.red or fallbacks.red)

    def _red(self, subject, *texts, next=()):
        from . import signals
        message, steps = signals.red(subject, *texts, next=next)
        self.red.append(message)
        for key, lines in steps.items():
            self.steps.setdefault(key, lines)

    def _place(self, target):
        point = self.points.get(target)
        if point is None:
            return target
        return f"{point['file']}:{getattr(point['anchor'], 'target_line', 0) or getattr(point['node'], 'lineno', 0)}"

    def _lost(self):
        """Observations that the baseline code makes in the same context and the current code turns grey.

        Each fails the run, unless `.flowguard/ledger.toml` lists its anchor or rule under [unverified]
        with a reason; listed ones are returned as unverified lines. Without a baseline nothing is lost."""
        from . import ledger
        listed = ledger.unverified(self.cfg)[0]     # its malformed lines are red in the ledger's own check
        model = self.state.model      # check --all asks for any grey owner-sourced declaration, a Flow too
        names = ({anchor.name for anchor in self.index.entries} | set(model.rules) | set(model.flows)
                 | set(model.states) | set(model.structures) | set(model.anchor_distincts))
        for name in sorted(set(listed) - names):
            self._red(f'[unverified] 里的 {name}', f'不是锚点、规则或模型的名字，从 {ledger.LEDGER} 的 [unverified] 段删掉它')
        kept, seen = [], set()
        for index, point, part, unknown, cause in self.records:
            if index >= len(self.runtime.readings) or not self._losable(point):
                continue
            reading = self.runtime.readings[index]
            if not reading.lost:
                continue
            subjects = [point['name']] if point['anchor'] else []
            subjects += [rule.id for rule in self.rules.get(point['target'], ())]
            key = point['target'], reading.lost
            if key in seen:
                continue
            seen.add(key)
            reason = next((listed[name] for name in subjects if name in listed), '')
            if reason:
                kept.append(f'{subjects[0]}（{self._place(point["target"])}）：已登记不回放：{reason}')
                continue
            self._red('观察丢失 ' + '、'.join(subjects),
                      f'{self._place(point["target"])} 在 {reading.test or "这个测试"} 里，基准代码能比较，现在是灰：{reading.lost}',
                      next=[_restore_step(reading.lost),
                            f'或者确实不再回放：在 {ledger.LEDGER} 的 [unverified] 段写一句理由（不少于 {ledger.MIN_WORDS} 个词）'
                            + ('' if ledger.path(self.cfg).is_file() else '；还没有这个文件时先运行 python -m flowguard ledger init') + '：',
                            '[unverified]', f'{subjects[0]} = ' + ledger._quote(ledger.PLACEHOLDER_UNVERIFIED)])
        return kept

    def _losable(self, point):
        """Only an anchor, or a function a rule is bound to, can lose its observation."""
        return point['anchor'] is not None or bool(self.rules.get(point['target']))

    def _reachable(self, fn):
        """The function and the project helpers it calls, as the runtime registered them."""
        found, pending = [], [fn]
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.append(current)
            patch = self.runtime.patches.get(current)
            pending.extend(patch.dependencies if patch else ())
        return found

    def _moved_constants(self, fn):
        """(name, namespace, before, after, file, function) of the module constants that this function, or a project
        helper it calls, reads and that differ from the baseline."""
        import ast
        import inspect
        from . import runtime as R
        found = []
        for function in self._reachable(fn):
            # Names from the source, not the code object: an observed helper runs FlowGuard's call hook.
            names = self.metadata.setdefault(('names', function), {node.id for node in ast.walk(R._definition(function))
                                                                   if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)})
            for (_, name), (namespace, before) in self.runtime.constants.items():
                if namespace is not function.__globals__ or name not in names:
                    continue
                after = namespace[name]
                if R.outcome_equal(self.runtime._old_value(namespace, name, before), after):
                    continue
                file = Path(inspect.getsourcefile(function)).resolve().relative_to(self.cfg.root).as_posix()
                if (name, file) not in {(entry[0], entry[4]) for entry in found}:
                    found.append((name, namespace, before, after, file, function))
        return found

    def _moved_literals(self, point, current):
        """(before, after, line) of the literals that differ inside an otherwise identical function body."""
        import ast
        import copy
        from . import runtime as R
        patch = self.runtime.patches.get(point['fn'])
        if patch is None:
            return []
        class Shape(ast.NodeTransformer):
            def visit_Constant(self, node):
                return ast.copy_location(ast.Constant(type(node.value).__name__), node)
        if ast.dump(Shape().visit(copy.deepcopy(patch.node)), include_attributes=False) != ast.dump(Shape().visit(copy.deepcopy(current)), include_attributes=False):
            return []
        return [(before.value, after.value, after.lineno) for before, after in zip(
                    (node for node in ast.walk(patch.node) if isinstance(node, ast.Constant)),
                    (node for node in ast.walk(current) if isinstance(node, ast.Constant)))
                if type(before.value) is type(after.value) and not R.outcome_equal(before.value, after.value)]

    def _widen(self, point, original, axes, part, unknown):
        """Comparison points the branch partition alone misses, for integer inputs:

        - every value between the old and the new value of a moved integer constant (also one read by a
          helper, or a literal changed inside the body), so a moved boundary shows as its whole interval;
        - for a function that returns arithmetic on an input, six consecutive values from each
          representative, since the branch classes do not separate arithmetic results. That grid is
          not a partition: the comparison is then reported as incomplete."""
        import ast
        import itertools
        from . import sites
        from .runtime import _definition
        integer = [name for name, pool in axes.items() if pool and all(type(value) is int for value in pool)]
        if not integer:
            return part, unknown
        try:
            current = _definition(original)
        except (OSError, TypeError, SyntaxError):
            return part, unknown
        own = list(sites.own_nodes(current))

        def related(names=(), helpers=(), line=0):
            """The integer inputs compared with the moved value, or passed to the helper that reads it."""
            found = set()
            for node in own:
                inside = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
                if isinstance(node, ast.Compare) and (inside & set(names) or line and node.lineno <= line <= node.end_lineno):
                    found |= inside
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in helpers:
                    found |= inside
            return [name for name in integer if name in found] or integer
        moved = [(before, after, related(names=[name] if function is point['fn'] else (),
                                         helpers=[function.__name__] if function is not point['fn'] else ()))
                 for name, _, before, after, _, function in self._moved_constants(point['fn'])]
        moved += [(before, after, related(line=line)) for before, after, line in self._moved_literals(point, current)]
        for before, after, inputs in moved:
            if type(before) is int and type(after) is int and abs(before - after) <= 64:
                for name in inputs:
                    axes[name].extend(value for value in range(min(before, after) - 1, max(before, after) + 2)
                                      if value not in axes[name])
        patch = self.runtime.patches.get(point['fn'])
        bodies = [current] + ([patch.node] if patch is not None else [])
        arithmetic = set()
        for body in bodies:
            parts = list(sites.own_nodes(body))
            computed = {target.id for part in parts if isinstance(part, ast.Assign) and any(isinstance(node, ast.BinOp) for node in ast.walk(part.value))
                        for target in part.targets if isinstance(target, ast.Name)}
            returns = [part.value for part in parts if isinstance(part, ast.Return) and part.value is not None]
            if body.returns is not None and ast.unparse(body.returns) == 'bool' or not any(
                    isinstance(node, ast.BinOp) or isinstance(node, ast.Name) and node.id in computed
                    for value in returns for node in ast.walk(value)):
                continue
            arithmetic |= {node.id for part in parts if isinstance(part, ast.BinOp) for node in ast.walk(part) if isinstance(node, ast.Name)}
        windowed = {name: sorted({step for value in axes[name] for step in range(value - 1, value + 6)}) for name in integer if name in arithmetic}
        sizes = [len(windowed.get(name, axes[name])) for name in axes]
        if windowed and all(len(values) <= 40 for values in windowed.values()) and len(list(itertools.islice(
                itertools.product(*(range(size) for size in sizes)), 4097))) <= 4096:
            for name, values in windowed.items():
                axes[name].extend(value for value in values if value not in axes[name])
            part, unknown = None, [*unknown, '算术结果：每类取了连续的代表值，不是完整划分']
        return part, unknown

    def _cause(self, point, original=None):
        import ast
        import difflib
        from . import runtime as R
        for name, namespace, before, after, file, _ in self._moved_constants(point['fn']):
            tree = ast.parse((self.cfg.root / file).read_text(encoding='utf-8-sig'))
            line = next((node.lineno for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                         and any(isinstance(target, ast.Name) and target.id == name for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))), 1)
            return dict(name=name, before=before, after=after, file=file, line=line)
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
        for before, after, line in self._moved_literals(point, current):
            return dict(name=point['name'] + ' 的常量', before=before, after=after, file=point['file'], line=line)
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
    _refuse_distribution(config)
    _session(config)


def _refuse_distribution(config):
    """One pytest process judges the whole session; distributed workers are refused before any test runs.

    The session verdicts (a lost observation, a Flow over every test's events, the sentinel's complete
    collection, the ledger) need every test of the run in one process. pytest-xdist runs them in workers,
    and its controller reads a worker's exit status only for an interrupt, so a red found there would end
    as a green run. Its own options, read the way it reads them (`dist` with `tx`, or a worker's
    `workerinput`), are set before any `pytest_configure`."""
    option = config.option
    worker = hasattr(config, 'workerinput')
    distributed = getattr(option, 'dist', 'no') != 'no' and bool(getattr(option, 'tx', None)) and not option.collectonly
    if worker or distributed:
        raise pytest.UsageError(
            'FlowGuard judges a test session in one pytest process: pytest-xdist workers (-n, --dist, --tx) '
            'would end a red found in a worker as a passed run -> run pytest without -n, or with -n 0')


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
        elif self.kind == 'flow':
            # Flow items run after every ordinary test and every other intent item, so the session's anchor
            # events and its rules' contracts are complete here: the item itself is red, grey or green.
            state.rule_contracts()
            result = engine.run_flow(model.flows[self.rule_id], state.events, state.anchor_issues)
        elif self.kind in ('states', 'structure', 'anchor_distinct'):
            declaration = (model.states if self.kind == 'states'
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
    state.engine.call_sites = state.observations.rule_calls
    state.source_items = tuple(item for item in session.items if not isinstance(item, IntentItem) and item.name != SENTINEL)
    intent = [item for item in session.items if isinstance(item, IntentItem)]
    # A Flow reads its lower rules' contracts from their items' results, so Flow items run last.
    session.items[:] = [*state.source_items, *(item for item in intent if item.kind != 'flow'),
                       *(item for item in intent if item.kind == 'flow'),
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
    from .calibration import probe_context
    from . import ledger
    fallbacks = ledger.Result(present=False) if probe_context(config) else state.ledger()
    red = ('\n' + ledger.summary(fallbacks) + ' -> 运行 python -m flowguard ledger check 列出全部差异和可照抄的条目\n'
           + '\n'.join('红：' + finding.text for finding in fallbacks.red)) if fallbacks.red else ''
    if missing:
        raise AssertionError(f'only {len(declared) - len(missing)} of {len(declared)} intent items collected or reusable; missing ' + ', '.join(missing[:3]) + ' -> run the complete declared collection' + red)
    if red:
        # The intent collection is complete; only the ledger fails this sentinel.
        state.sentinel_ledger = True
        pytest.fail(red.lstrip('\n'), pytrace=False)


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
        # Anchor events are always recorded (local events on anchored code only), so
        # show NAME and model draft have data after a plain pytest run.
        if (not isinstance(item, IntentItem) and item.name != SENTINEL and state.model is not None
                and state.model.anchor_index.entries and not probe_context(item.config)):
            from .flow import Capture
            capture = scopes.enter_context(Capture(state.cfg.root, state.model.anchor_index, item.nodeid,
                                                   models=state.model.flows.values() if state.model.flows and not state.observations.changed else None, _ordinary=True))
            if state.observations is not None:
                # Modules imported during this test add their anchored code to the capture.
                state.observations.capture = capture
                scopes.callback(setattr, state.observations, 'capture', None)
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


@pytest.hookimpl(tryfirst=True)
def pytest_report_teststatus(report, config):
    """A grey intent item is its own outcome, not a pass: U with -q, UNVERIFIED with -v, `N unverified`
    in the summary. The exit status does not change; no warning, skip or xfail is involved."""
    if report.when == 'call' and report.passed and getattr(report, 'flowguard_unverified', False):
        return 'unverified', 'U', 'UNVERIFIED'


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    from .runtime import _PRIVATE
    if _PRIVATE.get():
        return
    state = item.config._flowguard_intent
    if isinstance(item, IntentItem) and report.when == 'call' and report.passed:
        report.flowguard_unverified = state.results.get(item.nodeid, {}).get('verdict') == 'grey'
        if report.flowguard_unverified:
            # JUnit XML reads the item's properties at teardown: a grey item is not written as a plain pass.
            item.user_properties.append(('flowguard_outcome', 'unverified'))
    if state.complete_collection is not None and report.when == 'teardown':
        state.completed.add(item.nodeid)
    _skip_violation(item, call, report)
    state.durations[item.nodeid] = state.durations.get(item.nodeid, 0.0) + report.duration
    if item.name == SENTINEL and report.when == 'call':
        state.sentinel = 'ok' if report.passed or state.sentinel_ledger else 'failed'
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
    from .cache import put_meta
    put_meta(con, name, _json(value))


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


@pytest.hookimpl(tryfirst=True)     # the session verdict exists before junitxml writes its file
def pytest_sessionfinish(session, exitstatus):
    state = session.config._flowguard_intent
    with state.verification():
        result = finish_verified(session, exitstatus)
    _junit_session(session, state)
    # Verification and transaction completion precede optional terminal output.
    if state.observations is not None and state.observations.text:
        from .differences import display
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        if reporter is not None and reporter._tw.width_of_current_line:
            reporter._tw.line()             # never after the progress line of the last test
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


def _junit_session(session, state):
    """A red that only the session decides is a failed `flowguard::session` testcase in JUnit XML.

    The XML otherwise counts the ordinary tests alone, so a lost observation or a ledger red that exits
    1 would read `failures="0"`. Only the junitxml plugin receives these reports, the same way it
    receives every test's; the terminal counts and the cache do not change."""
    from _pytest.junitxml import xml_key
    xml = session.config.stash.get(xml_key, None)
    if xml is None or not state.session_red:
        return
    text = '\n'.join(dict.fromkeys(state.session_red))
    for when, outcome, longrepr in (('call', 'failed', text), ('teardown', 'passed', None)):
        xml.pytest_runtest_logreport(pytest.TestReport('flowguard::session', ('flowguard', None, 'session'),
                                                       {}, outcome, longrepr, when))


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
    state.rule_contracts()
    if state.observations is not None and state.observations.report():
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        if state.observations.session_red:
            state.session_red.extend(state.observations.text.splitlines() or state.observations.session_red)
    state.session_red[:0] = state.session_errors
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
        # Recorded anchor events are kept even before the first map exists.
        path = state.cfg.cache / 'map.sqlite'
        if (path.is_file() or state.events) and state.readings:
            from flowguard.map.common import cache_dir
            cache_dir(state.cfg.root)
            with closing(sqlite3.connect(path, timeout=30)) as con:
                con.executescript(SCHEMA + 'CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);\n')
                with con:
                    con.execute('BEGIN IMMEDIATE')
                    _meta(con, 'intent_attempt', attempt)
                    if state.observations is not None and state.observations.payload is not None:
                        _meta(con, 'runtime_observations', state.observations.payload)
                    if state.observations is not None and state.observations.structure is not None:
                        from .cache import save_structure
                        save_structure(con, state.observations.structure)
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
        if state.observations is not None and state.observations.structure is not None:
            from .cache import save_structure
            save_structure(con, state.observations.structure)
        if not missing and state.sentinel == 'ok' and not state.session_errors:
            _meta(con, 'intent_collection', attempt)
            if not model.deep:
                con.execute("DELETE FROM result WHERE item LIKE '%:live]'")
            for item, result in state.results.items():
                con.execute('INSERT OR REPLACE INTO result VALUES(?,?,?,?,?)', (item, result['rule'], result['verdict'], _json(result), state.started))
            from .deps import Now, record
            from .cache import save_dependencies
            fresh = {result['rule'] for result in state.results.values() if result['rule'] is not None}
            records, now, found = {}, Now(state.cfg, mapping), {}     # one session's digests for all records
            now.archive = state.engine.archive        # the owner words this session's rules already checked
            for rid in fresh:
                declaration = (model.rules.get(rid) or model.states.get(rid) or model.structures.get(rid)
                               or model.flows.get(rid) or model.anchor_distincts.get(rid))
                records[rid] = record(state.cfg, model, declaration,
                                      [r for r in state.results.values() if r['rule'] == rid], mapping, now, found)
            save_dependencies(con, records)
        _save_readings(con, state)
        _save_ordinary_collection(con, session, state)
        if state.observations is not None and state.observations.fresh:
            from .cache import save_comparisons
            save_comparisons(con, state.observations.runtime.baseline, state.observations.fresh)
        con.commit()
