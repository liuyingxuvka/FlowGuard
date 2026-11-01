"""Record test public prefixes as facts, then replay them under shipped settings."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import builtins
from functools import wraps
import hashlib
import io
import json
import math
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout

from flowguard.map.common import normalize_newlines

from .project import UnsupportedWorld, _load, snapshot


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
        self.system_type = _load(spec["system"])
        self.ui_type = _load(spec["ui"]) if spec.get("ui") else None
        self.settings_type = _load(spec["settings"]) if spec.get("settings") else None
        self.refusals = tuple(_load(name) for name in spec.get("refusal", ()))
        self.defaults = spec.get("shipped", {})
        self.rows, self.saved = [], []
        self.current = None
        self.depth = 0
        self.objects = {}
        self.receivers = {}
        self.next_ui = 0
        self.last_after = None
        self.last_settings = None

    def stop(self, kind, reason):
        if self.current is not None and self.current["stop"] is None:
            self.current["stop"] = {"kind": kind, "index": len(self.current["events"]), "reason": reason}

    def boundary(self):
        if self.current is None or self.current["stop"] or not self.objects:
            return False
        try:
            now = snapshot(self.objects, self.arena, self.defaults)
        except (ValueError, OSError, TypeError, RecursionError) as exc:
            self.stop("unsupported", "complete boundary observation unavailable: " + str(exc))
            return False
        if self.last_after is not None and now != self.last_after:
            self.stop("edit", "state changed outside an outermost public call")
            return False
        return True

    def checkpoint(self):
        if self.current is not None and not self.current["stop"]:
            try:
                self.last_after = snapshot(self.objects, self.arena, self.defaults)
            except (ValueError, OSError, TypeError, RecursionError) as exc:
                self.stop("unsupported", "complete boundary observation unavailable: " + str(exc))

    def outcome(self, error, receiver="system"):
        refusals = self.refusals
        if receiver.startswith("ui:"):
            refusals += tuple(getattr(builtins, name) for name in self.spec.get("ui_refusal", ()))
        return "success" if error is None else "refusal" if isinstance(error, refusals) else "crash"

    def save(self, cls, name, replacement):
        self.saved.append((cls, name, cls.__dict__[name]))
        setattr(cls, name, replacement)

    def install(self):
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
                    except (ValueError, TypeError, RecursionError) as exc:
                        self.stop("unsupported", "settings are not a finite JSON profile: " + str(exc))
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
                                except (ValueError, TypeError, RecursionError) as exc:
                                    self.stop("unsupported", str(exc))
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
                            event["outcome"] = self.outcome(error, receiver)
                            self.current["events"].append(event)
                            self.checkpoint()
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
                except (ValueError, TypeError, RecursionError) as exc:
                    self.stop("unsupported", str(exc))
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
                        except (ValueError, OSError, TypeError, RecursionError) as exc:
                            self.stop("unsupported", str(exc))
                        else:
                            if after != before:
                                self.stop("edit", "UI state changed outside its public choose method")
                    if not self.current["stop"]:
                        event["outcome"] = self.outcome(error, receiver)
                        self.current["events"].append(event)
                        self.checkpoint()
        return public_called

    def restore(self):
        for cls, name, original in reversed(self.saved):
            setattr(cls, name, original)

    def begin(self, item):
        source = Path(str(item.path)).resolve()
        self.current = {"test": item.nodeid, "source": str(source),
                        "digest": hashlib.sha256(normalize_newlines(source.read_bytes())).hexdigest(),
                        "events": [], "settings": {}, "stop": None}
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


def record(spec, arena, *, observed=None):
    """One already-created worker runs actual pytest tests; no application runs in the parent."""
    import pytest

    recorder = _Recorder(spec, arena)
    class Plugin:
        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def pytest_runtest_protocol(self, item, nextitem):
            if observed is not None:
                observed.recorded_hits.clear()
            recorder.begin(item)
            try:
                yield
            finally:
                recorder.finish()
                if observed is not None:
                    recorder.rows[-1]["function_hits"] = sorted(observed.recorded_hits)
    root = Path(spec["root"])
    location = root / "tests" if (root / "tests").is_dir() else root
    output, error = io.StringIO(), io.StringIO()
    recorder.install()
    try:
        with redirect_stdout(output), redirect_stderr(error):
            result = pytest.main(["-q", "--rootdir", str(root), "--basetemp", str(Path(arena) / "pytest"), "-p", "no:cacheprovider", str(location)], plugins=[Plugin()])
    finally:
        recorder.restore()
    return {"recordings": recorder.rows, "pytest_exitcode": int(result),
            "tests": len(recorder.rows), "stopped": sum(row["stop"] is not None for row in recorder.rows),
            "scope": "outer-call and teardown snapshots; transient edits restored between boundaries are not observed"}


def replay_prefixes(session, recordings):
    """Keep only concrete shipped public prefixes, never the original test assertions."""
    from .explore import _terms, plain, observations

    rows = recordings.get("recordings", []) if isinstance(recordings, dict) else recordings
    witnesses, ignored, divergences, prefixes, replays = {}, [], [], [], []
    original_start = session.start

    def retain(row):
        for kind, entity in session.spec["entities"].items():
            if not plain(session.query("system", entity["list"])):
                return False
        terms = _terms(session)
        last = session.last
        if last and last["call"].get("construct"):
            receiver = last["call"]["receiver"]
            if plain(session.query(receiver, "screen", property=True)) != "home":
                raise UnsupportedWorld("a test UI must be constructed at home")
        if last and "name" in last["call"] and last["call"]["name"] in session.spec["actions"]:
            terms.append({"kind": "action", "receiver": last["call"].get("receiver", "system"),
                          "name": last["call"]["name"], "outcome": last["outcome"]})
        for term in terms:
            witness = {"semantic": term, "prefix": list(session.prefix), "outcomes": list(session.outcomes),
                       "start": {}, "origin": "test", "test": row["test"],
                       "source": row.get("source"), "digest": row.get("digest")}
            key = json.dumps(term, sort_keys=True)
            previous = witnesses.get(key)
            if previous is None or (len(witness["prefix"]), witness["test"]) < (len(previous["prefix"]), previous["test"]):
                witnesses[key] = witness
        prefixes.append({"test": row["test"], "prefix": list(session.prefix), "outcomes": list(session.outcomes),
                         "start": {}, "observations": observations(session)})
        return True

    try:
        for recording in rows:
            session.start = {}
            session.reset()
            profile = recording.get("settings", {})
            if profile and profile != session.spec.get("shipped", {}):
                ignored.append({"test": recording["test"], "settings": profile})
            valid_prefix, valid_outcomes = [], []
            eligible = retain(recording)
            stop = recording.get("stop")
            limit = min(len(recording["events"]), stop["index"]) if stop else len(recording["events"])
            for index, event in enumerate(recording["events"][:limit]):
                recipe = {key: value for key, value in event.items() if key != "outcome"}
                try:
                    row = session.step(recipe)
                    if row["outcome"] != event["outcome"]:
                        divergences.append({"test": recording["test"], "index": index,
                                            "expected": event["outcome"], "actual": row["outcome"]})
                        stop = {"kind": "outcome", "index": index}
                        break
                    valid_prefix.append(recipe)
                    valid_outcomes.append(row["outcome"])
                    eligible = retain(recording)
                except (UnsupportedWorld, ValueError, OSError) as exc:
                    divergences.append({"test": recording["test"], "index": index, "reason": str(exc)})
                    stop = {"kind": "unsupported", "index": index, "reason": str(exc)}
                    break
            if stop and stop["kind"] == "edit":
                divergences.append({"test": recording["test"], **stop})
            replays.append({"test": recording["test"], "prefix": valid_prefix, "outcomes": valid_outcomes,
                            "start": {}, "eligible": eligible, "stop": stop})
    finally:
        session.start = original_start
        session.reset()
    return {"witnesses": [witnesses[key] for key in sorted(witnesses)], "ignored_settings": ignored,
            "divergences": divergences, "prefixes": prefixes, "replays": replays,
            "recorded_tests": len(rows)}
