"""The SDK's one small check flow, observed at actual call boundaries.

This records only check's expensive boundaries. It neither installs a trace hook
nor starts another checker. The ordinary Flow validator checks the saved events
once, on exit; it does not turn a completed failing check into success.
"""
from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
import inspect
from pathlib import Path
import subprocess
import time

from .anchors import collect_sources
from .api import Rule
from .diagnostics import EventLog, report_diagnostic
from .flow import Event, Flow, Node, Read, Relation, _snapshot, runtime_check, finite_check
from .sites import installed_origin


def _load_exit(errors, exit_code):
    return errors >= 0 and (errors == 0 or exit_code != 0)


def _source_exit(red, exit_code):
    return not red or exit_code != 0


def _pytest_exit(pytest_code, exit_code):
    return pytest_code == 0 or exit_code != 0


LOAD_EXIT = Rule('CHECK_LOAD_EXIT', 'load_errors_prevent_check_success',
    'lesson: a check with declaration loading errors cannot return zero',
    {'errors': int, 'exit_code': int}, _load_exit)
SOURCE_EXIT = Rule('CHECK_SOURCE_EXIT', 'source_errors_prevent_check_success',
    'lesson: a source check reporting red cannot return zero',
    {'red': bool, 'exit_code': int}, _source_exit)
PYTEST_EXIT = Rule('CHECK_PYTEST_EXIT', 'pytest_failure_prevents_check_success',
    'lesson: an observed nonzero pytest result cannot return zero; ambiguous batches remain unverified',
    {'pytest_code': int, 'exit_code': int}, _pytest_exit)


CHECK_FLOW = Flow('CHECK_PIPELINE', 'lesson: a check exposes actual loading, selection, pytest and result boundaries',
    nodes=(Node('begin', 'CHECK_RUN'), Node('loaded', 'CHECK_LOAD', phase='return'),
           Node('selected', 'CHECK_SELECTION', phase='return'), Node('pytest_start', 'CHECK_PYTEST'),
           Node('pytest_end', 'CHECK_PYTEST', phase='return'), Node('collected', 'CHECK_RESULTS', phase='return'),
           Node('sources_start', 'CHECK_SOURCES'), Node('sources', 'CHECK_SOURCES', phase='return'),
           Node('returned', 'CHECK_RUN', phase='return', end=True),
           Node('aborted', 'CHECK_RUN', phase='raise', end=True)),
    edges=(('begin', 'loaded'), ('begin', 'aborted'), ('loaded', 'selected'), ('loaded', 'sources_start'),
           ('loaded', 'aborted'), ('selected', 'pytest_start'), ('selected', 'sources_start'), ('selected', 'aborted'),
           ('pytest_start', 'pytest_end'), ('pytest_start', 'aborted'), ('pytest_end', 'collected'),
           ('pytest_end', 'aborted'), ('collected', 'pytest_start'), ('collected', 'sources_start'),
           ('collected', 'aborted'), ('sources_start', 'sources'), ('sources_start', 'aborted'),
           ('sources', 'returned'), ('sources', 'aborted')),
    relations=(Relation(LOAD_EXIT, {'errors': Read('loaded', 'result.errors'),
                                   'exit_code': Read('returned')}, on='returned'),
               Relation(SOURCE_EXIT, {'red': Read('sources'),
                                     'exit_code': Read('returned')}, on='returned'),
               Relation(PYTEST_EXIT, {'pytest_code': Read('pytest_end', 'result.returncode'),
                                     'exit_code': Read('returned')}, on='returned')))

_CURRENT = ContextVar('flowguard_check_observation', default=None)


def _source_index():
    return collect_sources(Path(__file__).resolve().parents[2], (
        ('flowguard/intent/cli.py', 'flowguard.intent.cli'),
        ('flowguard/intent/loader.py', 'flowguard.intent.loader'),
        ('flowguard/intent/cache.py', 'flowguard.intent.cache')))


def anchor_identity(anchor):
    return (anchor.name, anchor.target, anchor.file, anchor.source_digest,
            anchor.kind, anchor.target_line, anchor.parameters)


def covered_sdk_anchors(root):
    """The canonical internal model covers these SDK sources, never a namesake."""
    if Path(root).resolve() != Path(__file__).resolve().parents[2]:
        return set()
    references = {node.reference for node in CHECK_FLOW.nodes}
    index = _source_index()
    covered = set()
    for reference in references:
        candidates = index.named(reference)
        if len(candidates) == 1 and candidates[0].status == 'ok':
            covered.add(anchor_identity(candidates[0]))
    return covered


def _input_summary(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Path):
        return str(value)
    if type(value) in (dict, list, tuple, set, frozenset):
        return dict(type=type(value).__name__, count=len(value))
    return dict(type=type(value).__name__)


def observe(function, *args, **kwargs):
    observation = _CURRENT.get()
    return observation.call(function, *args, **kwargs) if observation is not None else function(*args, **kwargs)


class CheckObservation:
    """A scoped consumer of existing source identities and Event/Flow checks."""
    def __init__(self, cfg):
        self.path = cfg.cache / 'check-flow.jsonl'
        self.sdk_root = Path(__file__).resolve().parents[2]
        self.index = _source_index()
        self.events, self.issues, self.counts, self.parents = [], [], Counter(), []
        self._echo_failed = False
        self.finite = finite_check(CHECK_FLOW, self.index)
        self.static = dict(kind='flow-static', verdict='grey', checked=False,
                           red=[], grey=['self static paths not checked'], info=[])
        self.elapsed_ns = 0

    def __enter__(self):
        self.writer = EventLog(self.path)
        self.token = _CURRENT.set(self)
        self._write(dict(kind='model', id=CHECK_FLOW.id, nodes=len(CHECK_FLOW.nodes), finite=self.finite, static=self.static))
        return self

    def _write(self, value):
        self.writer.write(value)

    def _append(self, anchor, phase, values, occurrence, *, result=None, error=None):
        actual = (dict(returncode=result.returncode, stdout_bytes=len((result.stdout or '').encode()),
                       stderr_bytes=len((result.stderr or '').encode())) if isinstance(result, subprocess.CompletedProcess)
                  else result if type(result) in (bool, int, float, str, type(None)) else dict(type=type(result).__name__))
        if phase == 'return' and anchor.name == 'CHECK_LOAD':
            actual = dict(rules=len(result.rules), flows=len(result.flows), errors=len(result.errors))
        elif phase == 'return' and anchor.name == 'CHECK_SELECTION':
            actual = dict(rules=len(result[0]), flows=len(result[1]), ordinary=len(result[2]),
                          test_files=len(result[3]))
        elif phase == 'return' and anchor.name == 'CHECK_RESULTS':
            attempt = result.get('attempt') or {}
            actual = dict(sentinel=attempt.get('sentinel'), missing=len(attempt.get('missing') or ()),
                          errors=len(attempt.get('errors') or ()), recorded_tests=len(result['tests']))
        event = Event(anchor.name, phase, values, _snapshot(actual), error, 'check', occurrence,
                      anchor.target, len(self.events) + 1, parents=tuple(self.parents),
                      file=str(self.sdk_root / anchor.file), source_digest=anchor.source_digest)
        self.events.append(event)
        row = self.writer.event(event)
        if phase == 'call':
            detail = 'start'
        else:
            elapsed = row.get('elapsed_ns') if row is not None else None
            duration = f'{elapsed / 1_000_000:.2f}ms' if elapsed is not None else 'unavailable'
            detail = f'{phase} elapsed={duration}'
            if error is not None:
                detail += f' {type(error).__name__}'
        if not self._echo_failed:
            error = report_diagnostic(f'FlowGuard stage: {anchor.name} #{occurrence} {detail}')
            if error is not None:
                self._echo_failed = True
                self.issues.append(f'diagnostic stage output unavailable: {type(error).__name__}')

    def call(self, function, *args, **kwargs):
        """Capture an indexed function's own result/raise, never a caller's answer."""
        target = getattr(function, '__module__', '') + ':' + getattr(function, '__qualname__', type(function).__name__)
        code = getattr(function, '__code__', None)
        anchors = [a for a in self.index.entries if a.target == target and
                   code is not None and
                   str((self.sdk_root/a.file).resolve()) == str(Path(code.co_filename).resolve()) and
                   a.target_line == code.co_firstlineno and
                   [p.name for p in a.parameters] == list(inspect.signature(function).parameters)]
        replaced = installed_origin(function) is not None if code is not None else False
        if replaced or len(anchors) != 1 or any(i.level == 'red' for a in anchors for i in a.issues):
            self.issues.append(f'{target}: installed code body is unverified' if replaced else
                               f'{target}: actual function identity does not match one valid source anchor')
            self._write(dict(kind='unverified', target=target, message=self.issues[-1]))
            return function(*args, **kwargs)
        anchor = anchors[0]
        bound = inspect.signature(function).bind(*args, **kwargs)
        bound.apply_defaults()
        values = {name: _input_summary(value) for name, value in bound.arguments.items()}
        self.counts[anchor.target] += 1
        occurrence = self.counts[anchor.target]
        self._append(anchor, 'call', values, occurrence)
        self.parents.append((anchor.name, anchor.target, occurrence))
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            self.parents.pop()
            self._append(anchor, 'raise', values, occurrence, error=error)
            raise
        else:
            self.parents.pop()
            self._append(anchor, 'return', values, occurrence, result=result)
            return result

    def __exit__(self, *error):
        _CURRENT.reset(self.token)
        started = time.monotonic_ns()
        self.result = runtime_check(CHECK_FLOW, self.events, self.index)
        self.issues.extend(issue for issue in self.writer.issues if issue not in self.issues)
        self.result['grey'].extend(self.issues)
        if self.issues and self.result['verdict'] == 'ok':
            self.result['verdict'] = 'grey'
        self.elapsed_ns = time.monotonic_ns()-started
        returns = [e for e in self.events if e.anchor == 'CHECK_RUN' and e.phase == 'return']
        # A function returning a failing/interrupt status is an observed return,
        # not evidence of successful verification.
        self._write(dict(kind='validation', result=self.result, validator_elapsed_ns=self.elapsed_ns,
                         run_completed=bool(returns),
                         run_succeeded=bool(returns and returns[-1].result == 0 and not self.result['red'] and not self.issues),
                         coverage_verdict=self.result['verdict'], static=self.static))
        self.writer.close()
        later = [issue for issue in self.writer.issues if issue not in self.issues]
        self.issues.extend(later)
        self.result['grey'].extend(later)
        if later and self.result['verdict'] == 'ok':
            self.result['verdict'] = 'grey'
