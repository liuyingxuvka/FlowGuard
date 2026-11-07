"""Ordinary pytest owns execution; this plugin adds intent items and source footprints."""
from __future__ import annotations

import fnmatch
from functools import cache
from contextlib import closing, ExitStack, contextmanager
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
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
SCHEMA = '''
CREATE TABLE IF NOT EXISTS reading(test TEXT PRIMARY KEY, outcome TEXT, kind TEXT, reason TEXT,
  phase TEXT, seconds REAL, stamp REAL);
CREATE TABLE IF NOT EXISTS footprint(test TEXT, node TEXT, fp TEXT, file TEXT, line INTEGER,
  qual TEXT, origin TEXT, call_lines TEXT, PRIMARY KEY(test,node,origin));
CREATE TABLE IF NOT EXISTS result(item TEXT PRIMARY KEY, rule TEXT, verdict TEXT, payload TEXT, stamp REAL);
'''


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
        self.results, self.readings, self.footprints, self.children, self.durations = {}, {}, {}, {}, {}
        self.sentinel = None
        self.ordinary_selected, self.early_exit, self.session_errors = set(), [], []
        self.ordinary_files, self.ordinary_deselected = set(), False
        self.last_test = None
        self.process_calls, self.closed = [], False
        self.main_process = os.getpid()
        self.main_thread = threading.get_ident()
        self.started = time.time()
        self.folder = self.bootstrap = None
        self.events, self.anchor_issues = [], []
        self.diagnostics, self.diagnostic_issues, self.diagnostic_models = None, [], []
        self.owns_diagnostics = True
        self.diagnostic_scope = self.main_process, id(config)
        self.calibration_facts = {}

    def start_diagnostics(self, config):
        requested = (config.getoption('--flowguard-diagnose', default=False)
                     or getattr(getattr(config, 'known_args_namespace', None), 'flowguard_diagnose', False))
        append = (config.getoption('--flowguard-diagnose-append', default=False)
                  or getattr(getattr(config, 'known_args_namespace', None), 'flowguard_diagnose_append', False))
        if append and not requested:
            raise pytest.UsageError('--flowguard-diagnose-append requires --flowguard-diagnose')
        if requested and self.diagnostics is None:
            from .calibration import probe_context
            sessions, seen = [], set()
            current = self
            while current is not None and id(current) not in seen:
                seen.add(id(current))
                sessions.append(current)
                current = getattr(current, 'previous_session', None)
            # Drivers register before configure activates their private capability.
            # Excluding their diagnostics must not change that capability's meaning.
            if any(probe_context(state.config) or any(
                    getattr(candidate, '_flowguard_calibration_driver', False)
                    for candidate in state.config.pluginmanager.get_plugins()) for state in sessions):
                return
            from .diagnostics import EventLog
            owner = next((state for state in sessions[1:]
                          if state.cfg.root == self.cfg.root and state.main_process == self.main_process
                          and state.main_thread == self.main_thread and state.diagnostics is not None), None)
            if owner is not None:
                self.diagnostics, self.owns_diagnostics = owner.diagnostics, False
            else:
                self.diagnostics = EventLog(self.cfg.cache / 'anchor-events.jsonl', append=append)
            self.diagnostics.write(dict(kind='session', pid=self.main_process, scope_id=self.diagnostic_scope, root=str(self.cfg.root),
                                        append=bool(append or owner is not None), nested=owner is not None,
                                        scope='ordinary-test activated anchors; calibration probes are not expanded'))
            config.pluginmanager.register(self)

    @contextmanager
    def verification(self):
        from .anchors import _execution_session
        from .calibration import _execution_session as calibrated_session
        with calibrated_session(self.cfg.root, facts=self.calibration_facts), _execution_session(self.cfg.root):
            yield

    def import_children(self):
        if self.folder is None:
            self.folder = tempfile.TemporaryDirectory(prefix='flowguard-child-')
            self.bootstrap = Path(self.folder.name) / 'bootstrap'
            self.bootstrap.mkdir()
            # All Python children read current source; only recorded tests trace.
            sdk = Path(__file__).resolve().parents[1]
            (self.bootstrap / 'sitecustomize.py').write_text(
                'import importlib.util, sys\n'
                f'_spec = importlib.util.spec_from_file_location("flowguard", {str(sdk / "__init__.py")!r}, '
                f'submodule_search_locations=[{str(sdk)!r}])\n'
                '_package = importlib.util.module_from_spec(_spec)\n'
                'sys.modules["flowguard"] = _package\n'
                '_spec.loader.exec_module(_package)\n'
                'from flowguard.intent.child import start\nstart()\n', encoding='utf-8')
        paths = [str(self.bootstrap), str(self.cfg.root),
                 *(str(p) for p in self.cfg.roots), *os.environ.get('PYTHONPATH', '').split(os.pathsep)]
        values = dict(FLOWGUARD_IMPORT_ROOT=str(self.cfg.root), PYTHONPATH=os.pathsep.join(dict.fromkeys(paths)))
        inherited = ('FLOWGUARD_TRACE_ROOT', 'FLOWGUARD_TRACE_CHILDREN', 'FLOWGUARD_TRACE_TEST')
        self.import_environment = {name: os.environ.get(name) for name in (*values, *inherited)}
        # A nested pytest session owns propagation to its children. The caller's
        # active footprint remains real, but its child context is not this
        # session's ordinary-test recording policy. Restore it when we close.
        for name in inherited:
            os.environ.pop(name, None)
        os.environ.update(values)

    def _diagnostic_unavailable(self, output, error):
        issue = f'diagnostics unavailable: {output} reporting raised {type(error).__name__}'
        self.diagnostic_issues.append(issue)
        if self.diagnostics is not None:
            self.diagnostics.issues.append(issue)
            self.diagnostics.write(dict(kind='diagnostic-unavailable', output=output,
                                        error=type(error).__name__))

    def _report_diagnostic(self, text, *, stream, output):
        from .diagnostics import report_diagnostic
        error = report_diagnostic(text, file=stream)
        if error is not None:
            self._diagnostic_unavailable(output, error)

    def pytest_runtest_logreport(self, report):
        # This receives the final pytest outcome, including effective xfail and
        # FlowGuard's skip/marked-guard corrections. Private probe sessions never
        # register this enabled diagnostic owner.
        if not report.failed or self.diagnostics is None:
            return
        from .calibration import probe_context
        if probe_context(self.config):
            return
        try:
            stream = self.config.get_terminal_writer()
            text = f'\nFlowGuard failure: {report.nodeid} [{report.when}]\n{report.longreprtext}'
        except Exception as error:
            self._diagnostic_unavailable('terminal', error)
            return
        self._report_diagnostic(text, stream=stream, output='terminal')

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
        for name, value in self.import_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.folder.cleanup()
        if self.diagnostics is not None:
            grey = sum(len(result.get('grey', ())) for result in self.diagnostic_models)
            unclaimed = sum(result.get('runtime', {}).get('unclaimed_relations', 0) for result in self.diagnostic_models)
            outside = sum('anchor not included' in message for result in self.diagnostic_models for message in result.get('info', ()))
            self.diagnostic_issues.extend(self.diagnostics.issues)
            self._report_diagnostic(f'FlowGuard anchor diagnostics: {len(self.diagnostic_models)} model result(s), '
                                    f'{grey} unverified reason(s), {unclaimed} readings outside rules, '
                                    f'{outside} unmodelled anchor notices; {self.diagnostics.path}',
                                    stream=sys.stdout, output='stdout')
        for issue in dict.fromkeys(self.diagnostic_issues):
            self._report_diagnostic('FlowGuard ' + issue, stream=sys.stderr, output='stderr')
        if self.diagnostics is not None:
            if self.owns_diagnostics:
                self.diagnostics.write(dict(kind='closed', scope_id=self.diagnostic_scope, model_results=len(self.diagnostic_models)))
                self.diagnostics.close()
            for issue in tuple(self.diagnostics.issues):
                if issue not in self.diagnostic_issues:
                    self.diagnostic_issues.append(issue)
                    self._report_diagnostic('FlowGuard ' + issue, stream=sys.stderr, output='stderr')

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

    def child_folder(self, item):
        folder = Path(self.folder.name) / str(len(self.children))
        folder.mkdir()
        self.children[item.nodeid] = folder
        return folder

    def get_model(self):
        if self.model is None:
            from .calibration import probe_context
            probe = probe_context(self.config)
            previous = self.previous_session
            index = (previous.model.anchor_index if probe and previous is not None
                     and previous.cfg.root == self.cfg.root and previous.model is not None else None)
            with self.verification():
                self.model = load(self.cfg, anchor_index=index,
                                  map_path=Path(self.folder.name) / 'anchor-map.sqlite' if probe else None)
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
                elif getattr(binding, 'anchor', None) and binding.anchor.calibrated_by:
                    _prepare(self.cfg.root, binding.anchor)

    def get_map(self):
        if self.map is None:
            from flowguard.structure import build
            self.map = build(self.cfg.root, roots=self.cfg.roots)
        return self.map

    def child_records(self, item):
        folder = self.children.get(item if isinstance(item, str) else item.nodeid)
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))] if folder else []


def pytest_addoption(parser):
    group = parser.getgroup('flowguard')
    group.addoption('--flowguard-rules', default=None, help='Run these changed rules; other fully collected rules are deferred to the cache')
    group.addoption('--flowguard-record-tests', action='store_true', help='Record the ordinary tests actually selected by check')
    group.addoption('--flowguard-diagnose', action='store_true', help='Write live diagnostics for activated ordinary-test anchors')
    group.addoption('--flowguard-diagnose-append', action='store_true', help='Append a later diagnostic batch from the same check')


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
        state.import_children()
        config.add_cleanup(state.close)
    config._flowguard_intent.guard_process_exit(config)
    config._flowguard_intent.start_diagnostics(config)
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
        state.results[self.nodeid] = dict(result, rule=self.rule_id, target=self.target)
        if result['verdict'] == 'red':
            raise IntentFailure('\n'.join(result['red']))

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
    state = config._flowguard_intent
    state.collected = {i.nodeid for i in items if isinstance(i, IntentItem)}
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


def pytest_collection_finish(session):
    state = session.config._flowguard_intent
    state.selected = {i.nodeid for i in session.items if isinstance(i, IntentItem)}
    state.ordinary_selected = {i.nodeid for i in session.items if not isinstance(i, IntentItem) and i.name != SENTINEL}


def pytest_deselected(items):
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
            with sqlite3.connect(path) as connection:
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
def pytest_runtest_protocol(item):
    state = item.config._flowguard_intent
    state.last_test = item.nodeid
    capture = None
    with ExitStack() as scopes:
        from .calibration import probe_context
        if (not isinstance(item, IntentItem) and item.name != SENTINEL and state.model is not None
                and state.model.flows and not probe_context(item.config)):
            from .flow import Capture
            capture = scopes.enter_context(Capture(state.cfg.root, state.model.anchor_index, item.nodeid,
                                                   models=state.model.flows.values(), _ordinary=True,
                                                   on_event=(lambda event: state.diagnostics.event(event, scope=state.diagnostic_scope))
                                                   if state.diagnostics is not None else None))
        try:
            if (isinstance(item, IntentItem) or item.name == SENTINEL
                    or not item.config.getoption('--flowguard-record-tests') and not any(item.iter_markers('rule'))):
                yield
                return
            folder = state.child_folder(item)
            values = dict(FLOWGUARD_TRACE_ROOT=str(state.cfg.root), FLOWGUARD_TRACE_CHILDREN=str(folder), FLOWGUARD_TRACE_TEST=item.nodeid)
            previous = {name: os.environ.get(name) for name in values}
            os.environ.update(values)
            with Footprint(state.is_project) as footprint:
                state.footprints[item.nodeid] = footprint
                try:
                    yield
                finally:
                    for name, value in previous.items():
                        if value is None:
                            os.environ.pop(name, None)
                        else:
                            os.environ[name] = value
        finally:
            if capture:
                scopes.close()
                state.events.extend(capture.events)
                state.anchor_issues.extend(capture.issues)
                state.diagnostic_issues.extend(capture.diagnostic_issues)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    state = item.config._flowguard_intent
    _skip_violation(item, call, report)
    state.durations[item.nodeid] = state.durations.get(item.nodeid, 0.0) + report.duration
    if item.name == SENTINEL and report.when == 'call':
        state.sentinel = 'ok' if report.passed else 'failed'
    if isinstance(item, IntentItem) or item.name == SENTINEL:
        return
    if report.when == 'call' and report.passed:
        for marker in item.iter_markers('rule'):
            entered = set(state.footprints[item.nodeid].keys())
            entered.update((entry[0], entry[1]) for child in state.child_records(item) for entry in child['entered'])
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
            kind, reason = classify(call.when, call.excinfo, state.cfg, text=str(report.longrepr or '') + captured,
                                    children=state.child_records(item)) if report.failed else ('', '')
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
    from .cache import save_trace_signatures
    unrecorded = state.readings.keys() - state.footprints.keys()
    con.executemany('DELETE FROM footprint WHERE test=?', [(test,) for test in unrecorded])
    for file in (test for test in unrecorded if '::' not in test):
        prefix = file + '::'
        con.execute('DELETE FROM footprint WHERE substr(test,1,?)=?', (len(prefix), prefix))
    save_trace_signatures(con, {}, drop=unrecorded)
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
    with session.config._flowguard_intent.verification():
        return finish_verified(session, exitstatus)


def finish_verified(session, exitstatus):
    state = session.config._flowguard_intent
    from .calibration import probe_context
    if probe_context(session.config):
        declared = set(state.model.declared_items()) if state.model is not None else set()
        _completion_policy(session, state, declared)
        return  # Unselected intent is not part of this ordinary-test probe.
    model = state.get_model()
    declared = set(model.declared_items())
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
        if state.diagnostics is not None:
            summary = {key: result.get(key) for key in ('verdict', 'red', 'grey', 'info')}
            summary['runtime'] = {key: result.get('runtime', {}).get(key) for key in (
                'verdict', 'unclaimed_relations', 'checked_relations', 'observed_edges', 'ignored_case_scopes')}
            summary['finite'] = {key: result.get('finite', {}).get(key) for key in ('verdict', 'states', 'exhausted')}
            summary['static'] = {key: result.get('static', {}).get(key) for key in ('verdict', 'grey')}
            state.diagnostic_models.append(summary)
            state.diagnostics.write(dict(kind='validation', scope_id=state.diagnostic_scope, model=identifier, result=summary))
        if result['verdict'] == 'red':
            print('\nFlowGuard flow ' + identifier + ': ' + '; '.join(result['red']), file=sys.stderr)
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    from .cli import anchor_checks, behavior_changes
    from .differences import display
    index, observation_lines, observation_red = anchor_checks(state.cfg, index=model.anchor_index, automatic=True)
    if observation_red:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    observation_lines.extend(behavior_changes(state.cfg, automatic=True, index=index))
    if observation_lines:
        display('\n'.join(observation_lines))
    exitstatus = session.exitstatus
    missing = _missing(state, declared)
    attempt = dict(declared=len(declared), collected=len(state.collected), selected=len(state.selected),
                   deferred=len(state.deferred), missing=missing, sentinel=state.sentinel, exit=int(exitstatus),
                   errors=state.session_errors, stamp=state.started)
    if not declared and not state.footprints:
        # Standalone pytest does not build a map, but must retire old traces
        # for a test it ran without recording. Never refresh them by implication.
        path = state.cfg.cache / 'map.sqlite'
        if path.is_file() and state.readings:
            with closing(sqlite3.connect(path, timeout=30)) as con:
                con.executescript(SCHEMA)
                with con:
                    con.execute('BEGIN IMMEDIATE')
                    _meta(con, 'intent_attempt', attempt)
                    _save_readings(con, state)
                    _save_ordinary_collection(con, session, state)
        return
    with closing(state.get_map()) as mapping:
        con = mapping.con
        con.executescript(SCHEMA)
        if 'call_lines' not in {row[1] for row in con.execute('PRAGMA table_info(footprint)')}:
            con.execute('ALTER TABLE footprint ADD COLUMN call_lines TEXT')
        con.execute('BEGIN IMMEDIATE')
        _meta(con, 'intent_attempt', attempt)
        if not missing and state.sentinel == 'ok' and not state.session_errors:
            _meta(con, 'intent_collection', attempt)
            for rid, rule in model.rules.items():
                required = {model.file_of[rid] + '::' + name for name in model.items_of(rule)}
                if required <= state.results.keys():
                    parts = [state.results[item] for item in required]
                    owner = model.file_of[rid] + '::' + rid + '[rules]'
                    state.results[owner]['own_contract'] = state.engine.contract_summary(rule, parts=parts)
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
        # Maps provide the sole fingerprint owner. Missing dynamic functions stay explicitly unmapped.
        nodes = {(row['file'], row['qual']): row for row in mapping.nodes()}
        @cache
        def relative(filename):
            return state.cfg.rel(filename)

        @cache
        def node_of(entry):
            filename, line, qual = entry
            rel = relative(filename)
            owner_qual = '' if qual == '<module>' else qual.replace('.<locals>.', '.')
            node = nodes.get((rel, owner_qual))
            return rel, node, node['id'] if node else f'{rel}:{qual}'

        observed, rows = set(), []
        for test, footprint in state.footprints.items():
            con.execute('DELETE FROM footprint WHERE test=?', (test,))
            entries = [('parent', footprint.entered, footprint.edges, footprint.call_lines)]
            entries += [('child', child['entered'], child['edges'], child.get('call_lines', [])) for child in state.child_records(test)]
            for origin, entered, edges, call_lines in entries:
                grouped = {}
                for target, file, line in call_lines:
                    grouped.setdefault(tuple(target), set()).add((relative(file), line))
                for entry in entered:
                    entry = tuple(entry)
                    rel, node, ident = node_of(entry)
                    rows.append((test, ident, node['fp'] if node else '', rel, entry[1], entry[2], origin, _json(sorted(grouped.get(entry, [])))))
                for a, b in edges:
                    first, second = node_of(tuple(a)), node_of(tuple(b))
                    if first[1] and second[1]:
                        observed.add((first[2], second[2]))
        con.executemany('INSERT OR REPLACE INTO footprint VALUES(?,?,?,?,?,?,?,?)', rows)
        from .deps import trace_signatures
        from .cache import save_trace_signatures
        save_trace_signatures(con, trace_signatures(state.cfg, mapping, state.footprints))
        mapping.add_observed(observed)
