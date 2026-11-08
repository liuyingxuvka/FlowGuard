"""Function footprints and call edges only: no argument, result or state recording."""
from __future__ import annotations

import sys

_ACTIVE = []
_TOOL = None
_PROJECT = None
_PROJECTS = ()
_OLD_TRACE = None
_OLD_PROFILE = None
_OLD_CALLBACK = None
_USING_TRACE = False
_OWNERSHIP = {}
_IMPLICIT = frozenset({'<genexpr>', '<listcomp>', '<dictcomp>', '<setcomp>'})


def _within(frame, key):
    while frame:
        if (frame.f_code.co_filename, frame.f_code.co_firstlineno) == key:
            return True
        frame = frame.f_back
    return False


def _record(code, frame):
    if code.co_name in _IMPLICIT:
        return sys.monitoring.DISABLE if hasattr(sys, 'monitoring') else None
    if not _PROJECT(code.co_filename):
        return sys.monitoring.DISABLE if hasattr(sys, 'monitoring') else None
    _record_owned(code, frame)


def _record_owned(code, frame):
    if code.co_name in _IMPLICIT:
        return  # Its AST is part of the enclosing named function's fingerprint.
    direct = frame.f_back
    single = len(_ACTIVE) == 1
    key = caller = None
    for footprint in _ACTIVE:
        # _ACTIVE changes before _refresh updates the aggregate predicate. A new
        # scope may reuse the earlier check only when that exact predicate ran.
        if not (single and footprint.is_project is _PROJECT) and not footprint.is_project(code.co_filename):
            continue
        if footprint.inside is not None and not _within(frame, footprint.inside):
            continue
        if key is None:
            key = (code.co_filename, code.co_firstlineno, code.co_qualname)
            caller = direct
            while caller and caller.f_code.co_name in _IMPLICIT:
                caller = caller.f_back
        footprint.entered.add(key)
        if caller and footprint.is_project(caller.f_code.co_filename):
            footprint.edges.add(((caller.f_code.co_filename, caller.f_code.co_firstlineno, caller.f_code.co_qualname), key))
        if direct:
            footprint.call_lines.add((key, direct.f_code.co_filename, direct.f_lineno))


def _refresh():
    global _PROJECT, _PROJECTS
    predicates = tuple(dict.fromkeys(fp.is_project for fp in _ACTIVE))
    if predicates != _PROJECTS:
        _PROJECTS = predicates
        _PROJECT = predicates[0] if len(predicates) == 1 else lambda filename: any(check(filename) for check in predicates)
        _OWNERSHIP.clear()
        if hasattr(sys, 'monitoring') and _TOOL is not None:
            sys.monitoring.restart_events()


def _start():
    global _TOOL, _OLD_TRACE, _OLD_PROFILE, _OLD_CALLBACK, _USING_TRACE
    _refresh()
    if not hasattr(sys, 'monitoring'):
        _OLD_PROFILE = sys.getprofile()
        _USING_TRACE = _OLD_PROFILE is not None and not callable(_OLD_PROFILE)
        if _USING_TRACE:
            _OLD_TRACE = sys.gettrace()
            _OLD_CALLBACK = _OLD_TRACE
            sys.settrace(_trace)
        else:
            _OLD_CALLBACK = _OLD_PROFILE
            sys.setprofile(_trace if _OLD_CALLBACK else _profile)
        return
    if _TOOL is None:
        free = [number for number in (4, 3) if sys.monitoring.get_tool(number) is None]
        if not free:
            raise RuntimeError('FlowGuard cannot trace: sys.monitoring IDs 3 and 4 are busy')
        _TOOL = free[0]
        sys.monitoring.use_tool_id(_TOOL, 'flowguard')
        sys.monitoring.register_callback(_TOOL, sys.monitoring.events.PY_START, _on_start)
        sys.monitoring.register_callback(_TOOL, sys.monitoring.events.PY_RESUME, _on_start)
        sys.monitoring.register_callback(_TOOL, sys.monitoring.events.PY_THROW, _on_throw)
    events = sys.monitoring.events
    sys.monitoring.set_events(_TOOL, events.PY_START | events.PY_RESUME | events.PY_THROW)


def _on_start(code, offset):
    return _record(code, sys._getframe(1))


def _on_throw(code, offset, exception):
    if _PROJECT(code.co_filename):
        _record_owned(code, sys._getframe(1))


def _profile(frame, event, arg, get=_OWNERSHIP.get):
    if event != 'call':
        return
    code = frame.f_code
    filename = code.co_filename
    owned = get(filename)
    if owned is None:
        owned = _OWNERSHIP[filename] = _PROJECT(filename)
    if owned:
        _record_owned(code, frame)


def _trace(frame, event, arg):
    _profile(frame, event, arg)
    # Returning None disables per-line tracing for this frame. An existing
    # coverage/debugger tracer keeps its own local callback unchanged.
    return _OLD_CALLBACK(frame, event, arg) if _OLD_CALLBACK else None


class Footprint:
    def __init__(self, is_project, inside=None):
        self.is_project, self.inside = is_project, inside
        self.entered, self.edges = set(), set()
        self.call_lines = set()

    def __enter__(self):
        first = not _ACTIVE
        _ACTIVE.append(self)
        _start() if first else _refresh()
        return self

    def __exit__(self, *error):
        _ACTIVE.remove(self)
        if not _ACTIVE:
            if hasattr(sys, 'monitoring'):
                sys.monitoring.set_events(_TOOL, 0)
            elif not _USING_TRACE:
                sys.setprofile(_OLD_PROFILE)
            else:
                sys.settrace(_OLD_TRACE)
        else:
            _refresh()
        return False

    def keys(self):
        return {(path, line) for path, line, _ in self.entered}
