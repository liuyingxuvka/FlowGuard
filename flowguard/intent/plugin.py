"""Ordinary pytest owns execution; this plugin adds intent items and source footprints.

PYTEST_DONT_REWRITE: `python -m flowguard check` imports this module before its pytest session loads it
with `-p`; the plugin is no test module, so pytest skips rewriting it instead of warning that it came late.
"""
from __future__ import annotations

from collections import Counter
import fnmatch
from functools import cache
from contextlib import closing, ExitStack, contextmanager
from contextvars import ContextVar
import json
import math
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


class SignalReports(list):
    """One check's reports and its already computed static findings; never serialized."""
    def __init__(self, everything=False):
        super().__init__()
        self.everything = everything
        self.static = {}


@contextmanager
def collect_signals(*, everything=False):
    """Let a multi-batch check render its runtime facts exactly once."""
    reports = SignalReports(everything)
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
    # Types are compared by identity only, so no class hook of an observed value runs.
    kind = type(value)
    if kind is str or kind is int or kind is bool or kind is _NONE or kind is float and math.isfinite(value):
        return value
    if (kind is dict or kind is list or kind is tuple) and id(value) not in seen:
        seen = seen | {id(value)}
        if kind is dict:
            if all(type(key) is str for key in value):
                return {key: observation_payload(part, seen) for key, part in value.items()}
        else:
            return [observation_payload(part, seen) for part in value]
    namespace = type.__dict__['__dict__'].__get__(kind)
    module = namespace.get('__module__', 'builtins')
    return {'unverified_type': (module if type(module) is str else '?') + '.' + type.__dict__['__qualname__'].__get__(kind)}


_NONE = type(None)

def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=repr)


# flowguard: states Session.sentinel = None | 'failed' | 'ok'
class Session:
    def __init__(self, config):
        timing = time.perf_counter()
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
        self.tool_seconds = time.perf_counter() - timing

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
                    f'fallback ledger check did not complete: {type(error).__name__}: {error}', ('correct this error and rerun the tests',))])
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


def _sealed_numbers(tree, qual):
    """The numbers a same-name copy works with in the sealed environment: the int and float literals of the
    function and of the same-file functions it calls, and of the literal module constants they read (each
    number of a tuple, list, set or dict constant too), in that order. `-5` is -5, and 1 and 1.0 stay apart.
    None when the module has no such function."""
    import ast
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if qual not in functions:
        return None
    constants = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            literal = _literal_numbers(node.value)
            for target in targets:
                if isinstance(target, ast.Name):
                    if literal is not None:
                        constants[target.id] = literal
                    else:
                        constants.pop(target.id, None)
    numbers, todo, seen, read = [], [qual], set(), []
    while todo:
        name = todo.pop(0)
        if name in seen:
            continue
        seen.add(name)
        negated = set()
        for part in ast.walk(functions[name]):
            if isinstance(part, ast.UnaryOp) and isinstance(part.op, ast.USub) and _numeric(part.operand):
                numbers.append(-part.operand.value)
                negated.add(id(part.operand))
            elif _numeric(part) and id(part) not in negated:
                numbers.append(part.value)
            elif isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load):
                if part.id in functions:
                    todo.append(part.id)
                elif part.id in constants:
                    read.extend(constants[part.id])
    return list({(type(number), number): number for number in [*numbers, *read]}.values())


def _numeric(node):
    import ast
    return isinstance(node, ast.Constant) and type(node.value) in (int, float)


def _literal_numbers(node):
    """The numbers of a literal expression (a number, `-5`, or a tuple, list, set or dict of literals), in source
    order; None when the expression is not such a literal. A string, bytes, bool or None literal has none."""
    import ast
    if isinstance(node, ast.Constant):
        return [node.value] if _numeric(node) else []
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) and _numeric(node.operand):
        return [-node.operand.value if isinstance(node.op, ast.USub) else node.operand.value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        parts = node.elts
    elif isinstance(node, ast.Dict) and all(key is not None for key in node.keys):
        parts = [part for pair in zip(node.keys, node.values) for part in pair]
    else:
        return None
    found = [_literal_numbers(part) for part in parts]
    return None if any(numbers is None for numbers in found) else [number for numbers in found for number in numbers]


class Observations:
    """Connect loaded source points to the one runtime during ordinary tests."""
    def __init__(self, state):
        import ast
        from . import anchors, cache, differences
        from .runtime import Runtime, _functions, _binding_facts
        from ..map.common import MapError, git_renames, git_run, read_source
        from ..structure.readers.registry import language_for
        self.state, self.cfg = state, state.cfg
        self.requested_base = state.config.getoption('--flowguard-base', default=None)
        self.comparison_requested = bool(self.requested_base)
        # The first session of a task records HEAD as its baseline when none is recorded, so commits made during
        # the task keep what it changed reported; a recorded one is never moved here (only the brief and new-task
        # move it, and say why). --flowguard-base names its own baseline and records nothing, and so does a session
        # that only collects tests (IDE discovery), which is no task's first run. The title says how far HEAD
        # lies after a recorded start, and names one this repository lacks (kind 'missing': nothing is compared).
        collect_only = bool(state.config.getoption('collectonly', default=False))
        task, kind, self.baseline_ahead = ((None, None, None) if self.comparison_requested
                                           else cache.task_start(self.cfg, record=not collect_only))
        self.baseline_kind = 'base' if self.comparison_requested else kind or 'HEAD'
        self.missing = task if kind == 'missing' else None
        baseline = self.requested_base or task or 'HEAD'
        self.runtime = state.runtime = Runtime(self.cfg.root, baseline)
        if self.requested_base and self.runtime._baseline_error:
            raise pytest.UsageError(self.runtime._baseline_error)
        self.index = state.model.anchor_index or differences._source_index(self.cfg.root)
        state.model.anchor_index = self.index
        self.renamed = {}       # a moved file's baseline version is at its old path
        try:
            changed = git_run(self.cfg.root, 'diff', '--name-only', '-z', baseline).stdout
            added = git_run(self.cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
            self.files = {os.fsdecode(value) for value in (changed + added).split(b'\0')
                          if value and value.endswith(b'.py') and state.is_project(str(self.cfg.root / os.fsdecode(value)))}
            self.differs = {os.fsdecode(value) for value in changed.split(b'\0') if value}
            # A changed TS/JS, Prisma, SQL or other mapped file is a change too: the map checks read it.
            self.mapped = {os.fsdecode(value) for value in (changed + added).split(b'\0')
                           if value and language_for(os.fsdecode(value)) not in (None, 'python')}
            self.renamed = git_renames(self.cfg.root, baseline)
        except MapError:
            self.files = set()
            self.differs = set()
            self.mapped = set()
        self.points = {a.target: dict(anchor=a, target=a.target, file=a.file, module=a.module, qual=a.qual,
                                     name=a.name, kind=a.kind, node=None)
                       for a in self.index.entries if a.kind in ('sensor', 'event') and a.source_role != 'test'
                       and a.file.endswith('.py')}
        self.changed, self.records, self.pairs, self.red, self.grey, self.paths = bool(self.files), [], [], [], [], []
        self.steps = {}         # the next steps to copy under a red line, by its subject
        self.metadata, self.bound, self.event_codes, self.payload = {}, {}, {}, None
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
        views = {}
        def function(file, qual):
            """The current node of `qual` in a changed `file` and whether the function changed since the baseline:
            its body, or a top-level binding it reads (a module constant). A function new since then changed."""
            if file not in views:
                tree = ast.parse(read_source(self.cfg.root / file))
                old = self.runtime._source(self.renamed.get(file, file))
                old_tree = ast.parse(old) if old else ast.Module(body=[], type_ignores=[])
                views[file] = (dict(_functions(tree)), dict(_functions(old_tree)), _binding_facts(old_tree), _binding_facts(tree))
            current_functions, prior_functions, old_facts, facts = views[file]
            node, prior = current_functions.get(qual), prior_functions.get(qual)
            if node is None or prior is None or ast.dump(prior, include_attributes=False) != ast.dump(node, include_attributes=False):
                return node, True
            loaded = {part.id for part in ast.walk(node) if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)}
            return node, any(old_facts.get(name) != facts.get(name) for name in loaded)
        def reaches(file, qual):
            """Whether `qual` or a same-file function it calls, at any depth, changed: its sealed run executes them
            all (design 4.5), as the vitest plan compares the closed source with its helpers."""
            todo, seen = [qual], set()
            while todo:
                name = todo.pop()
                if name in seen:
                    continue
                seen.add(name)
                node, changed = function(file, name)
                if changed:
                    return True
                todo.extend(part.id for part in ast.walk(node) if isinstance(part, ast.Name)
                            and isinstance(part.ctx, ast.Load) and part.id in views[file][0])
            return False
        # A before/after comparison is due for a function whose sealed run changed, not for its unchanged neighbours.
        for point in self.points.values():
            point['changed'] = point['file'] in self.files and reaches(point['file'], point['qual'])
        if self.changed:
            # The existing map supplies module ownership for unanchored changed functions.
            graph = state.get_map()
            # The running FlowGuard never observes its own observation code: hooking the
            # changed Runtime.observe (or a replay helper) re-enters itself without end.
            tool, own = Path(__file__).resolve().parents[1], {}
            for row in graph.nodes():
                if row['file'] not in self.files or row['kind'] not in ('function', 'method') or not state.is_project(str(self.cfg.root / row['file'])):
                    continue
                if row['file'] not in own:
                    own[row['file']] = (self.cfg.root / row['file']).resolve().is_relative_to(tool)     # once per file
                if own[row['file']]:
                    continue
                node, changed = function(row['file'], row['qual'])
                if node is None or not changed:
                    continue
                params = tuple(anchors.Parameter(arg.arg, '', anchors._annotation(arg.annotation),
                                                anchors._parameter_role(anchors._annotation(arg.annotation)), True)
                               for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                               if arg.arg not in ('self', 'cls'))
                self.points.setdefault(row['id'], dict(anchor=None, parameters=params, target=row['id'], file=row['file'],
                                                       module=row['module'], qual=row['qual'], name=row['qual'], kind='sensor',
                                                       node=node, changed=True))
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
            self.bound[point['target']] = point
            if point['kind'] == 'event':
                self.event_codes[id(fn.__code__)] = (fn.__code__, point['name'])
                if self.event_record is not None:
                    self.event_record.add_code(fn.__code__, point['name'])
                continue
            try:
                anchor = point['anchor']
                original = self.scopes.enter_context(self.runtime.hook(fn, name=point['name'],
                    recorded=lambda reading, point=point: self._recorded(point, reading),
                    fields=anchor.fields if anchor else (), line=anchor.line if anchor else 0))
                point['original'] = original
            except (ValueError, TypeError, sites.NotMutable) as error:
                self.grey.append(point['name'] + ': ' + str(error))

    def _recorded(self, point, reading):
        self.records.append((reading.index, point, None, [], None))

    def _compare(self):
        """Only after the session: sources and JSON samples enter the sealed owner."""
        import ast
        from . import runtime as R
        from ..map.common import read_source
        sources, samples, items, before = {}, {}, [], []
        def source(point, old=False):
            key = point['file'], old
            if key not in sources:
                sources[key] = (None if self.runtime._baseline_error else self.runtime._source(self.renamed.get(key[0], key[0]))) \
                    if old else read_source(self.cfg.root / key[0])
            return sources[key]
        def run(point, sample, old=False):
            text = source(point, old)
            return R.sealed(text, point['qual'], sample['args'], sample['kwargs']) if text is not None else dict(status='unavailable', reason='no baseline source')
        def value(out):
            return out.get('value') if out['status'] == 'ok' else {'raises': out.get('error')}
        def equal(left, right):
            return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)
        def comparable(a, b):
            return (a['status'] != 'unavailable' and b['status'] != 'unavailable'
                    and not (a['status'] == b['status'] == 'raised' and a['error'] == b['error']))
        for index, point, _, _, _ in self.records:
            reading = self.runtime.readings[index]
            if reading.sample is not None:
                samples.setdefault(point['target'], {})[json.dumps(reading.sample, sort_keys=True)] = reading.sample
        for target, calls in samples.items():
            calls = list(calls.values())
            point = self.points[target]
            # Before/after only for a function that changed; an unchanged copy still joins its group below.
            if not point['changed']:
                continue
            rows, changes, reasons = [], [], []
            for sample in calls:
                old, now = run(point, sample, True), run(point, sample)
                if not comparable(old, now):
                    reasons.append(old.get('reason') or now.get('reason') or 'both versions raise the same exception')
                    continue
                inputs = _declared(point, sample['inputs'])
                rows.append((inputs, value(now)))
                if not equal(old, now):
                    changes.append((inputs, value(old), value(now)))
            items.append(dict(name=point['name'], file=point['file'], line=getattr(point['anchor'], 'target_line', 0) or getattr(point['node'], 'lineno', 0),
                              unanchored=point['anchor'] is None, status='grey' if reasons else 'ok', complete=not reasons,
                              rows=rows, changed=changes, total=len(calls), reasons=list(dict.fromkeys(reasons))))
        groups = {}
        for point in self.points.values():
            if point['anchor'] and point['kind'] == 'sensor':
                groups.setdefault(point['name'], []).append(point)
        for name, points in groups.items():
            if len(points) < 2:
                continue
            from . import signals, cells as C
            numbers = [number for point in points for number in _sealed_numbers(ast.parse(source(point)), point['qual']) or ()]
            inputs, left = signals.copy_inputs([_declared(point, sample['inputs']) for point in points
                                                for sample in samples.get(point['target'], {}).values()], numbers)
            if not inputs:
                self.grey.append(name + ': no recorded JSON inputs')
            if cut := signals.copy_cut(name, 64, left):
                self.grey.append(cut)
            places = {point['target']: self._place(point['target']) + ' ' + point['qual'] for point in points}
            owner = next((places[point['target']] for point in points if point['anchor'].owner), None)
            rows = []       # (input, current answers, baseline answers, places whose baseline could not run)
            for row in inputs:
                answered = []       # (point, current outcome, baseline outcome or None) of each copy that ran sealed
                for point in points:
                    spelled = {_spelled(point, key): v for key, v in row.items()}
                    node = dict(R._functions(ast.parse(source(point)))).get(point['qual'])
                    positional = [spelled.pop(p.arg) for p in node.args.posonlyargs if p.arg in spelled] if node else []
                    sample = dict(args=positional, kwargs=spelled)
                    now = run(point, sample)
                    if now['status'] == 'unavailable':
                        # This copy is not compared; the copies that ran still are (design 4.5, 6.4).
                        self.grey.append(name + ': ' + places[point['target']] + ' ' + now.get('reason', ''))
                        continue
                    past_text = source(point, True)
                    existed = past_text is not None and point['qual'] in dict(R._functions(ast.parse(past_text)))
                    answered.append((point, now, run(point, sample, True) if existed else None))
                outcomes = [out for _, out, _ in answered]
                if len(outcomes) < 2:
                    continue
                if all(out['status'] == 'raised' for out in outcomes) and all(equal(out, outcomes[0]) for out in outcomes[1:]):
                    self.grey.append(name + ': copies raise exceptions')
                    continue
                rows.append((', '.join(f'{key}={C.show(value)}' for key, value in row.items()),
                             [(places[point['target']], value(out)) for point, out, _ in answered],
                             {places[point['target']]: (value(past), past['status'] == 'raised') for point, _, past in answered
                              if past is not None and past['status'] != 'unavailable'},
                             {places[point['target']] for point, _, past in answered
                              if past is not None and past['status'] == 'unavailable'}))
            new_lines, previous_lines, open_lines = signals.copy_partition(rows, equal, C.show, owner, len(points))
            if previous_lines:
                before.append(signals.copy_red(name, previous_lines))
            if new_lines:
                self.red.append(signals.copy_red(name, new_lines))
            if open_lines:
                self.grey.append(name + ': baseline comparison unavailable; current copies disagree ('
                                 + '; '.join(f'{where}, {text}' for where, text, _, _ in open_lines) + ')')
        return items, before

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
                yield

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
                            self.red.append(rule.id + ' source: ' + (source.quote or source.text))
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
                self.red.extend(name + ' source: ' + quote for name, quote in quotes.items())
            results.append(observed)
        return results

    def report(self):
        timing = time.perf_counter()
        from . import signals
        self._rule_signals()
        partial_flows = self._flow_signals()
        items, before = self._compare()
        leads = []
        for _, point, _, _, _ in self.records:
            if self.request and self.request['target'] == point['target']:
                self.request['readings'].extend(reading for reading in self.runtime.readings if reading.target == point['target'])
        # Only a call due for a comparison is `not compared`: a function that changed itself, or one of two or
        # more same-name copies. A lone unchanged `same` function has nothing to compare it with.
        copies = Counter(point['name'] for point in self.points.values() if point['anchor'] and point['kind'] == 'sensor')
        self.grey.extend(point['name'] + ': no comparable JSON result' for index, point, _, _, _ in self.records
                         if self.runtime.readings[index].sample is None
                         and (point['changed'] or copies[point['name']] > 1))
        unverified, failed_items = [], set()      # an intent item's red is already a failed test
        for item, result in self.state.results.items():
            if result.get('verdict') == 'grey':
                unverified.extend(item.partition('::')[2] + '：' + str(reason) for reason in result.get('grey', ()) or ['unverified'])
            if result.get('red'):
                rule = self.state.model.rules.get(result.get('rule'))
                quote = ''
                if rule:
                    from .sources import parse
                    source = parse(rule.source)
                    quote = source.quote or source.text
                lines = [signals.constraint(message, result.get('rule') or 'rule') for message in result['red']]
                if quote:
                    lines.append(str(result.get('rule') or 'rule') + ' source: ' + quote)
                self.red.extend(lines)
                failed_items.update(lines)
        # Each violated rule names the next step: correct the code, or the rule first when the need changed.
        for rule in self.state.model.rules.values():
            if any(str(message).partition('：')[0].partition(': ')[0].partition(' source')[0].partition(' 出处')[0] == rule.id for message in self.red):
                homes = '、'.join(self._place(home.target) for home in rule.homes if not hasattr(home, 'scenario')) or rule.id + ' binding'
                said = [str(message).partition('：')[2] for message in self.red if str(message).startswith(rule.id + '：')]
                self.steps.setdefault(rule.id, signals.rule_steps(rule.id, homes, f'{self.state.model.file_of[rule.id]}:{rule.line}', said))
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
            collector = _SIGNALS.get()
            everything = collector.everything if collector is not None else False
            key = (self.cfg.root, self.requested_base, everything)
            if collector is not None and key in collector.static:
                found = collector.static[key]
            else:
                found = owners.static_findings(self.cfg, graph, anchors.collect(graph), self.runtime.baseline,
                                              everything=everything)
                if collector is not None:
                    collector.static[key] = found
            self.red.extend(found.red)
            leads.extend(found.leads)
            self.structure = found.summary         # the session brief's count of open structure problems
        self.red.extend(f'load {error["file"]}:{error["line"]}: {error["msg"]}' for error in self.state.model.errors)
        items = [dict(name='uncovered', status='grey', complete=False, changes=[], changed=0, total=0, reasons=[reason]) for reason in dict.fromkeys(self.grey)] + items
        fallbacks = self.state.ledger()
        # a [structure] entry of a later FlowGuard is unverified, never red, also in a run without a source change
        unverified.extend(fallbacks.later)
        report = dict(session=True, baseline=self.missing or self.runtime.baseline, baseline_kind=self.baseline_kind,
                      baseline_ahead=self.baseline_ahead,
                      # the overflow's command keeps --flowguard-base, as `--base`, so it lists these leads
                      more_leads=signals.more_leads('check --static', base=self.requested_base),
                      source_changed=self.changed or bool(self.mapped) or bool(fallbacks.later),
                      comparison_requested=self.comparison_requested, items=items, paths=self.paths,
                      leads=leads, before=list(dict.fromkeys(before)), red=list(dict.fromkeys(self.red)), steps=self.steps, partial_flows=partial_flows, unverified=unverified,
                      ledger_red=[dict(text=finding.text, fix=list(finding.fix)) for finding in fallbacks.red],
                      seconds=self.state.tool_seconds + getattr(self.runtime, 'seconds', 0) + time.perf_counter() - timing)
        from dataclasses import fields
        from .flow import Event
        names = [field.name for field in fields(Event)]
        self.payload = observation_payload(dict(stamp=self.state.started, baseline=self.runtime.baseline, items=report, paths=self.paths,
                                  events=[{name: getattr(event, name) for name in names}
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








def pytest_addoption(parser):
    from .cache import base_commit
    group = parser.getgroup('flowguard')
    group.addoption('--flowguard-base', default=None, type=base_commit, help='Compare with this baseline commit')
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
    if any(any(item.iter_markers('rule')) for item in items):
        from .deprecation import warn
        warn('pytest.mark.rule')
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
    timing = time.perf_counter()
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
    state.tool_seconds += time.perf_counter() - timing


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
    red = ('\n' + ledger.summary(fallbacks) + ' -> run python -m flowguard ledger check for all differences and entries to copy\n'
           + '\n'.join('red: ' + finding.text for finding in fallbacks.red)) if fallbacks.red else ''
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
        # show NAME and model draft have data after a plain pytest run. A source change keeps the
        # Flows' test-entry filter: no old-code rerun reads the other events (design 6.5). Without
        # one (no Flows, or a Flow that starts in production code) an anchor no Flow reads is sampled.
        if (not isinstance(item, IntentItem) and item.name != SENTINEL and state.model is not None
                and state.model.anchor_index.entries and not probe_context(item.config)):
            from .flow import Capture
            capture = scopes.enter_context(Capture(state.cfg.root, state.model.anchor_index, item.nodeid,
                                                   models=state.model.flows.values(), _ordinary=True))
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
        con.commit()
