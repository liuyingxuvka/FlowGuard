"""Optional live diagnostics over existing anchor Events; never a verifier.

Only an explicitly enabled observer creates this latest-run file. The event's
real source identity and readings remain the verifier's responsibility; these
clocks describe the observed boundary, not an independent correctness proof.
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PosixPath, WindowsPath
import time


def report_diagnostic(message, file=None):
    """Flush optional diagnostic output without replacing the caller's result."""
    try:
        print(message, file=file, flush=True)
    except Exception as error:
        return error
    return None


def _safe(value, depth=0):
    """Keep small literal readings, without repr/getters or a second ledger."""
    if value is None or type(value) in (bool, int, float):
        return value
    if type(value) is str:
        return value if len(value) <= 1024 else dict(omitted='long str', characters=len(value))
    if type(value) is bytes:
        return dict(type='bytes', hex=value.hex()) if len(value) <= 256 else dict(omitted='long bytes', bytes=len(value))
    if type(value) in (Path, PosixPath, WindowsPath):
        return str(value)
    if depth < 4 and type(value) in (tuple, list) and len(value) <= 32:
        return [_safe(item, depth + 1) for item in value]
    if depth < 4 and type(value) is dict and len(value) <= 32 and all(type(key) is str and len(key) <= 256 for key in value):
        return {key: _safe(item, depth + 1) for key, item in value.items()}
    return dict(omitted=type(value).__name__)


class EventLog:
    """One optional, flushed latest stream, shared by both observation backends.

    I/O failures disable diagnostics and remain visible in ``issues``. They do
    not interrupt the real event recorder or alter its model verdict/outcome.
    """
    def __init__(self, path, *, append=False):
        self.path, self.issues, self.saved = Path(path), [], None
        self.pid = os.getpid()
        self._started = {}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.saved = self.path.open('a' if append else 'w', encoding='utf-8')
        except Exception as error:
            self._failed(error)

    def _failed(self, error):
        self.issues.append(f'diagnostics unavailable: {type(error).__name__} ({self.path})')
        saved, self.saved = self.saved, None
        if saved is not None:
            try:
                saved.close()
            except Exception:
                pass

    def write(self, value):
        if self.saved is None:
            return
        try:
            self.saved.write(json.dumps(value, ensure_ascii=False, default=lambda obj: dict(omitted=type(obj).__name__)) + '\n')
            self.saved.flush()
        except Exception as error:
            self._failed(error)

    def event(self, event, *, scope=None):
        if self.saved is None:
            return
        try:
            # Monotonic and high resolution, including on Windows Python 3.12.
            now = time.perf_counter_ns()
            key = scope, event.case, event.anchor, event.site, event.occurrence
            elapsed = None
            if event.phase == 'call':
                self._started[key] = now
            elif event.phase in {'return', 'raise'}:
                started = self._started.pop(key, None)
                if started is not None:
                    elapsed = now - started
            row = dict(kind='event', anchor=event.anchor, phase=event.phase,
                       occurrence=event.occurrence, sequence=event.sequence,
                       case=event.case, scope_id=_safe(scope), site=event.site, file=event.file,
                       source_digest=event.source_digest, pid=self.pid,
                       inputs=_safe(event.values) if event.phase == 'call' else None,
                       result=_safe(event.result) if event.phase == 'return' else None,
                       states=_safe(event.states), before_states=_safe(event.before_states),
                       error=type(event.error).__name__ if event.error is not None else None,
                       monotonic_ns=now, wall_ns=time.time_ns(), elapsed_ns=elapsed)
            self.write(row)
            return row if self.saved is not None else None
        except Exception as error:
            self._failed(error)

    def close(self):
        saved, self.saved = self.saved, None
        if saved is not None:
            try:
                saved.close()
            except Exception as error:
                self._failed(error)

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.close()
