"""Function footprints use the runtime's shared observer, without retaining code."""
from __future__ import annotations

from pathlib import Path
from .sites import source_caller

_IMPLICIT = frozenset({'<genexpr>', '<listcomp>', '<dictcomp>', '<setcomp>'})
_ACTIVE = []        # the footprints open now


def recorded_entry(code):
    """A call the ordinary test run recorded entered `code`; every open footprint keeps that entry. A
    calibrated point is read from such a call and evaluated sealed, never by running the code again."""
    for footprint in _ACTIVE:
        footprint.entered.add((code.co_filename, code.co_firstlineno, code.co_qualname))


def _within(frame, key):
    while frame:
        if (frame.f_code.co_filename, frame.f_code.co_firstlineno) == key:
            return True
        frame = frame.f_back
    return False


class Footprint:
    def __init__(self, is_project, inside=None):
        self.is_project, self.inside = is_project, inside
        self.entered, self.edges, self.call_lines = set(), set(), set()
        self._scopes = []

    def _entry(self, frame, event, arg):
        if event != 'call' or (self.inside is not None and not _within(frame, self.inside)):
            return
        code, direct = frame.f_code, source_caller(frame)
        key = code.co_filename, code.co_firstlineno, code.co_qualname
        caller = direct
        while caller and caller.f_code.co_name in _IMPLICIT:
            caller = caller.f_back
        self.entered.add(key)
        if caller and self.is_project(caller.f_code.co_filename):
            self.edges.add(((caller.f_code.co_filename, caller.f_code.co_firstlineno, caller.f_code.co_qualname), key))
        if direct:
            self.call_lines.add((key, direct.f_code.co_filename, direct.f_lineno))

    def __enter__(self):
        from .runtime import Runtime
        runtime = Runtime(Path.cwd(), previous={})       # records only: no baseline is resolved
        scope = runtime.record(predicate=lambda code: code.co_name not in _IMPLICIT and self.is_project(code.co_filename),
                               callback=self._entry, private=True, entry_only=True)
        scope.__enter__()
        if not scope.active:
            raise RuntimeError('; '.join(scope.issues))
        self._scopes.append(scope)
        _ACTIVE.append(self)
        return self

    def __exit__(self, *error):
        _ACTIVE.remove(self)
        self._scopes.pop().__exit__(*error)
        return False

    def keys(self):
        return {(path, line) for path, line, _ in self.entered}
