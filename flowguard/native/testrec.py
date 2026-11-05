"""Record test public prefixes as facts, then replay them under shipped settings."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import builtins
from functools import wraps
import hashlib
import io
import json
import math
import os
import sys
from pathlib import Path
from contextlib import chdir, redirect_stderr, redirect_stdout

from flowguard.map.common import normalize_newlines

from .session import NativeEngineError, UnsupportedWorld, _load, snapshot


class _RecipeError(ValueError):
    pass


def _json_value(value):
    if value is None or type(value) in (bool, int, str):
        if type(value) is str and Path(value).is_absolute():
            raise _RecipeError("absolute path arguments need a reproducible file recipe")
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        return [_json_value(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _json_value(item) for key, item in value.items()}
    raise _RecipeError("only JSON scalar/list/dict arguments are recordable")


class _Recorder:
    def __init__(self, spec, arena):
        self.spec, self.arena = spec, Path(arena)
        self.system_type = _load(spec["system"]) if spec.get("system") else None
        self.ui_type = _load(spec["ui"]) if spec.get("ui") else None
        self.settings_type = _load(spec["settings"]) if spec.get("settings") else None
        self.refusals = tuple(_load(name) for name in spec.get("refusal", ()))
        self.defaults = spec.get("shipped", {})
        self.rows, self.saved = [], []
        self.current = None
        self.failure = None
        self.depth = 0
        self.objects = {}
        self.receivers = {}
        self.next_ui = 0
        self.last_after = None
        self.last_settings = None

    def stop(self, kind, reason, *, evidence_status="unknown"):
        if self.current is not None and self.current["stop"] is None:
            self.current["stop"] = {"kind": kind, "index": len(self.current["events"]), "reason": reason,
                                    "evidence_status": evidence_status}

    def failed(self, exc):
        self.failure = NativeEngineError(str(exc), phase="capture")
        return self.failure

    def boundary(self):
        if self.current is None or self.current["stop"] or not self.objects:
            return False
        try:
            now = snapshot(self.objects, self.arena, self.defaults)
        except (UnsupportedWorld, OSError) as exc:
            self.stop("unsupported", "complete boundary observation unavailable: " + str(exc),
                      evidence_status="unreadable" if isinstance(exc, OSError) else "unknown")
            return False
        except BaseException as exc:
            raise self.failed(exc) from exc
        if self.last_after is not None and now != self.last_after:
            self.stop("edit", "state changed outside an outermost public call")
            return False
        return True

    def checkpoint(self):
        if self.current is not None and not self.current["stop"]:
            try:
                self.last_after = snapshot(self.objects, self.arena, self.defaults)
            except (UnsupportedWorld, OSError) as exc:
                self.stop("unsupported", "complete boundary observation unavailable: " + str(exc),
                          evidence_status="unreadable" if isinstance(exc, OSError) else "unknown")
            except BaseException as exc:
                raise self.failed(exc) from exc

    def commit(self, event, error, receiver):
        try:
            event["outcome"] = self.outcome(error, receiver)
            self.current["events"].append(event)
            self.checkpoint()
        except BaseException as exc:
            raise self.failed(exc) from exc

    def outcome(self, error, receiver="system"):
        refusals = self.refusals
        if receiver.startswith("ui:"):
            refusals += tuple(getattr(builtins, name) for name in self.spec.get("ui_refusal", ()))
        return "success" if error is None else "refusal" if isinstance(error, refusals) else "crash"

    def save(self, cls, name, replacement):
        self.saved.append((cls, name, cls.__dict__[name]))
        setattr(cls, name, replacement)

    def install(self):
        if self.system_type is None:
            return  # Observer-only function libraries have no public object-prefix recording.
        root_init = self.system_type.__dict__.get("__init__")
        if root_init is None:
            raise UnsupportedWorld("test recording needs an explicit system constructor")

        @wraps(root_init)
        def root_created(obj, *args, **kwargs):
            active = self.current is not None and not self.depth and not self.current["stop"]
            if active and self.objects:
                self.stop("unsupported", "a second system root needs a separate recording")
                active = False
            self.depth += 1
            try:
                result = root_init(obj, *args, **kwargs)
            except BaseException:
                if active:
                    self.stop("constructor", "the initial system constructor did not succeed")
                raise
            finally:
                self.depth -= 1
            if active:
                self.objects = {"system": obj}
                self.receivers = {id(obj): "system"}
                actual = None
                parameter = self.spec.get("settings_parameter")
                if parameter:
                    names = root_init.__code__.co_varnames[1:root_init.__code__.co_argcount]
                    given = dict(zip(names, args))
                    given.update(kwargs)
                    actual = given.get(parameter)
                if actual is None and self.settings_type:
                    attributes = vars(obj).values() if hasattr(obj, "__dict__") else ()
                    actual = next((value for value in attributes if isinstance(value, self.settings_type)), self.last_settings)
                if actual is not None and is_dataclass(actual):
                    try:
                        self.current["settings"] = _json_value({field.name: getattr(actual, field.name) for field in fields(actual)})
                    except (_RecipeError, RecursionError) as exc:
                        self.stop("unsupported", "settings are not a finite JSON profile: " + str(exc))
                    except BaseException as exc:
                        raise self.failed(exc) from exc
                self.checkpoint()
            return result

        self.save(self.system_type, "__init__", root_created)
        if self.settings_type is not None:
            settings_init = self.settings_type.__dict__.get("__init__")
            if settings_init is not None:
                @wraps(settings_init)
                def settings_created(obj, *args, **kwargs):
                    result = settings_init(obj, *args, **kwargs)
                    self.last_settings = obj
                    return result
                self.save(self.settings_type, "__init__", settings_created)
        if self.ui_type is not None:
            ui_init = self.ui_type.__dict__.get("__init__")
            if ui_init is not None:
                @wraps(ui_init)
                def ui_created(obj, *args, **kwargs):
                    active = self.current is not None and not self.depth and not self.current["stop"]
                    event = None
                    receiver = None
                    if active:
                        if not self.objects or not self.boundary():
                            self.stop("unsupported", "a UI requires the recorded system root")
                        else:
                            given, options = list(args), dict(kwargs)
                            names = ui_init.__code__.co_varnames[1:ui_init.__code__.co_argcount]
                            first = names[0] if names else None
                            if given and given[0] is self.objects["system"]:
                                given.pop(0)
                            elif first and options.get(first) is self.objects["system"]:
                                del options[first]
                            else:
                                self.stop("unsupported", "the UI constructor is not bound to the recorded system")
                            if not self.current["stop"]:
                                try:
                                    receiver = "ui:" + str(self.next_ui)
                                    self.next_ui += 1
                                    event = {"construct": "ui", "receiver": receiver,
                                             "args": _json_value(given), "kwargs": _json_value(options)}
                                except (_RecipeError, RecursionError) as exc:
                                    self.stop("unsupported", str(exc))
                                except BaseException as exc:
                                    raise self.failed(exc) from exc
                    self.depth += 1
                    error = None
                    try:
                        return ui_init(obj, *args, **kwargs)
                    except BaseException as exc:
                        error = exc
                        raise
                    finally:
                        self.depth -= 1
                        if event is not None and not self.current["stop"]:
                            if error is None:
                                self.objects[receiver] = obj
                                self.receivers[id(obj)] = receiver
                            self.commit(event, error, receiver)
                self.save(self.ui_type, "__init__", ui_created)
        for cls in (self.system_type, self.ui_type):
            if cls is None:
                continue
            for name, descriptor in list(cls.__dict__.items()):
                if name.startswith("_") or isinstance(descriptor, property):
                    continue
                if isinstance(descriptor, (staticmethod, classmethod)):
                    fn = descriptor.__func__
                    wrapped = self.method(name, fn, static=isinstance(descriptor, staticmethod))
                    self.save(cls, name, type(descriptor)(wrapped))
                elif callable(descriptor) and hasattr(descriptor, "__code__"):
                    self.save(cls, name, self.method(name, descriptor))

    def method(self, name, fn, *, static=False):
        @wraps(fn)
        def public_called(*args, **kwargs):
            if self.current is None or self.depth or self.current["stop"]:
                return fn(*args, **kwargs)
            obj = None if static else args[0]
            receiver = "system" if static or isinstance(obj, type) else self.receivers.get(id(obj))
            event = None
            if not self.objects or receiver is None:
                self.stop("unsupported", "a public call has no recorded root or UI instance")
            elif self.boundary():
                try:
                    event = {"name": name, "receiver": receiver,
                             "args": _json_value(list(args if static else args[1:])), "kwargs": _json_value(kwargs)}
                except (_RecipeError, RecursionError) as exc:
                    self.stop("unsupported", str(exc))
                except BaseException as exc:
                    raise self.failed(exc) from exc
            before = self.last_after
            self.depth += 1
            error = None
            try:
                value = fn(*args, **kwargs)
                if event is not None and isinstance(value, self.system_type) and value is not self.objects["system"]:
                    self.stop("unsupported", "a second returned system root needs a separate recording")
                return value
            except BaseException as exc:
                error = exc
                raise
            finally:
                self.depth -= 1
                if event is not None and not self.current["stop"]:
                    if receiver.startswith("ui:") and name != self.spec["ui_methods"]["choose"]:
                        try:
                            after = snapshot(self.objects, self.arena, self.defaults)
                        except (UnsupportedWorld, OSError) as exc:
                            self.stop("unsupported", str(exc))
                        except BaseException as exc:
                            raise self.failed(exc) from exc
                        else:
                            if after != before:
                                self.stop("edit", "UI state changed outside its public choose method")
                    if not self.current["stop"]:
                        self.commit(event, error, receiver)
        return public_called

    def restore(self):
        for cls, name, original in reversed(self.saved):
            setattr(cls, name, original)

    def begin(self, item):
        source = Path(str(item.path)).resolve()
        self.current = {"test": item.nodeid, "source": str(source),
                        "digest": hashlib.sha256(normalize_newlines(source.read_bytes())).hexdigest(),
                        "events": [], "settings": {}, "stop": None, "pytest_reports": [], "pytest_outcome": "unknown"}
        self.rows.append(self.current)
        self.objects, self.receivers = {}, {}
        self.depth, self.next_ui = 0, 0
        self.last_after = self.last_settings = None

    def finish(self):
        if self.current is not None:
            if not self.objects:
                self.stop("no-system", "this test created no recordable system root")
            else:
                self.boundary()
        self.current = None


def record(spec, arena, *, observed=None, test_nodeids=None):
    """One already-created worker runs actual pytest tests; no application runs in the parent."""
    import pytest

    recorder = _Recorder(spec, arena)
    scope = {"collected": [], "finished": False, "stop_reason": None, "observer_gaps": [], "unassigned_events": []}
    scope_gaps = set()
    consumed_events = 0
    class Plugin:
        def pytest_collection_finish(self, session):
            try:
                scope["collected"] = [item.nodeid for item in session.items]
            except BaseException as exc:
                raise recorder.failed(exc) from exc

        def pytest_sessionfinish(self, session, exitstatus):
            try:
                reason = session.shouldstop or session.shouldfail
                scope["stop_reason"] = str(reason) if reason else None
                scope["finished"] = (not reason and int(exitstatus) in (0, 1)
                                     and set(scope["collected"]) == {row["test"] for row in recorder.rows}
                                     and all({report["when"] for report in row["pytest_reports"]}
                                             == {"setup", "call", "teardown"} for row in recorder.rows))
            except BaseException as exc:
                raise recorder.failed(exc) from exc

        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def pytest_runtest_protocol(self, item, nextitem):
            nonlocal consumed_events
            try:
                if observed is not None:
                    scope["unassigned_events"].extend(observed.events[consumed_events:])
                    scope_gaps.update(observed.recorded_gaps)
                    observed.recorded_hits.clear()
                    observed.recorded_gaps.clear()
                    observed.events.clear()
                    consumed_events = 0
                recorder.begin(item)
            except BaseException as exc:
                raise recorder.failed(exc) from exc
            try:
                yield
            finally:
                try:
                    recorder.finish()
                    if observed is not None:
                        recorder.rows[-1]["function_hits"] = sorted(observed.recorded_hits)
                        recorder.rows[-1]["observer_events"] = list(observed.events)
                        recorder.rows[-1]["observer_gaps"] = sorted(observed.recorded_gaps)
                        consumed_events = len(observed.events)
                except BaseException as exc:
                    raise recorder.failed(exc) from exc
        def pytest_runtest_logreport(self, report):
            try:
                row = next((row for row in reversed(recorder.rows) if row["test"] == report.nodeid), None)
                if row is None:
                    return
                row["pytest_reports"].append({"when": report.when, "outcome": report.outcome,
                                               **({"wasxfail": str(report.wasxfail)} if hasattr(report, "wasxfail") else {})})
                reports = row["pytest_reports"]
                row["pytest_outcome"] = ("failed" if any(item["outcome"] == "failed" for item in reports) else
                                         "skipped" if any(item["outcome"] == "skipped" for item in reports) else
                                         "passed" if {item["when"] for item in reports} == {"setup", "call", "teardown"} else "unknown")
            except BaseException as exc:
                raise recorder.failed(exc) from exc
    root = Path(spec["root"])
    location = root / "tests" if (root / "tests").is_dir() else root
    targets = [str(location)]
    if test_nodeids is not None:
        if not isinstance(test_nodeids, list) or not test_nodeids or any(not isinstance(item, str) or not item for item in test_nodeids):
            raise UnsupportedWorld("selected test nodeids must be a nonempty list")
        targets = []
        for nodeid in test_nodeids:
            path, *suffix = nodeid.split("::")
            path = (root / path).resolve()
            if not path.is_relative_to(root.resolve()):
                raise UnsupportedWorld("selected test is outside the recorded source root")
            targets.append("::".join([str(path), *suffix]))
    output, error = io.StringIO(), io.StringIO()
    if (not spec.get("system") and (root / "flowguard/__init__.py").is_file()
            and (root / "flowguard").resolve() != Path(__file__).resolve().parents[1]):
        # The recorder's loaded references stay the engine. Subject tests and their
        # subprocesses must import the subject's same-named package, never its observer.
        sys.path.insert(0, str(root))
        os.environ["PYTHONPATH"] = os.pathsep.join([str(root), os.environ.get("PYTHONPATH", "")])
        for name in list(sys.modules):
            if name == "flowguard" or name.startswith("flowguard."):
                del sys.modules[name]
    recorder.install()
    try:
        with chdir(root), redirect_stdout(output), redirect_stderr(error):
            result = pytest.main(["-q", "--rootdir", str(root), "--basetemp", str(Path(arena) / "pytest"),
                                  "--ignore", str(root / "tests/rules"), "-p", "no:cacheprovider", *targets], plugins=[Plugin()])
    finally:
        recorder.restore()
    if recorder.failure is not None:
        raise recorder.failure
    if observed is not None:
        scope_gaps.update(observed.recorded_gaps)
        scope["unassigned_events"].extend(observed.events[consumed_events:])
    scope["observer_gaps"] = sorted(scope_gaps)
    return {"recordings": recorder.rows, "pytest_exitcode": int(result), "test_scope": scope,
            "tests": len(recorder.rows), "stopped": sum(row["stop"] is not None for row in recorder.rows),
            "scope": "outer-call and teardown snapshots; transient edits restored between boundaries are not observed"}
