"""Native calls and complete supported observations in disposable worlds."""

from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
import io
import json
import os
from pathlib import Path, PosixPath, WindowsPath
import random
import re
import stat
import subprocess
import sys
import tempfile

from flowguard.map.common import child_import_path
from flowguard.map.runner import run_isolated_process

_ACTIVE_ARENA = None
_ACTIVE_CLASSES = set()


class UnsupportedWorld(ValueError):
    """An observation or construction cannot be represented faithfully."""


def _diagnostic(text, arena):
    return re.sub(re.escape(str(arena)) + r"(?=$|[\\/\s'\"),\]}:])", "<world>", text)


class _Graph:
    def __init__(self, arena):
        self.arena = Path(arena).resolve()
        self.seen = {}
        self.nodes = []

    def value(self, value):
        if value is None or type(value) in (bool, int):
            return value
        if type(value) is str:
            prefix = str(self.arena)
            return "<world>" + value[len(prefix):] if value == prefix or value.startswith(prefix + os.sep) else value
        if type(value) is float:
            return {"float": value.hex()}
        if type(value) is bytes:
            return {"bytes": base64.b64encode(value).decode("ascii")}
        if isinstance(value, Path):
            if type(value) not in {Path, PosixPath, WindowsPath}:
                raise UnsupportedWorld("custom path state needs an explicit world")
            return {"path": self.value(str(value))}
        if isinstance(value, Enum):
            if type(value.value) not in (bool, int, str) or set(vars(value)) - {"_value_", "_name_", "__objclass__", "_sort_order_"}:
                raise UnsupportedWorld("custom enum payload needs an explicit world")
            return {"enum": type(value).__module__ + ":" + type(value).__qualname__, "name": value.name, "value": value.value}
        identity = id(value)  # transient alias lookup; addresses never enter the observation
        if identity in self.seen:
            return {"ref": self.seen[identity]}
        number = len(self.nodes)
        self.seen[identity] = number
        node = {"type": type(value).__module__ + ":" + type(value).__qualname__}
        self.nodes.append(node)
        if type(value) in (list, tuple):
            node["items"] = [self.value(item) for item in value]
        elif type(value) is dict:
            node["items"] = [[self.value(key), self.value(item)] for key, item in value.items()]
        elif type(value) in (set, frozenset):
            # Unordered scalar sets have a canonical order; object sets need a world-specific view.
            if any(item is not None and type(item) not in (str, bytes, bool, int, float) for item in value):
                raise UnsupportedWorld("object-valued sets need an explicit world")
            node["items"] = sorted((self.value(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
        elif isinstance(value, (list, tuple, dict, set, frozenset, str, bytes, int, float)):
            raise UnsupportedWorld("container subtype needs an explicit world: " + node["type"])
        elif hasattr(value, "__dict__") or any("__slots__" in cls.__dict__ for cls in type(value).__mro__):
            if node["type"] not in _ACTIVE_CLASSES or callable(value):
                raise UnsupportedWorld("opaque state: " + node["type"])
            if any(cls is not object and cls.__module__ + ":" + cls.__qualname__ not in _ACTIVE_CLASSES for cls in type(value).__mro__[1:]):
                raise UnsupportedWorld("opaque native base: " + node["type"])
            attributes = dict(vars(value)) if hasattr(value, "__dict__") else {}
            for cls in reversed(type(value).__mro__):
                slots = cls.__dict__.get("__slots__", ())
                for name in (slots,) if isinstance(slots, str) else slots:
                    if name in {"__dict__", "__weakref__"}:
                        continue
                    prefix = cls.__name__.lstrip("_")
                    actual = "_" + prefix + name if prefix and name.startswith("__") and not name.endswith("__") else name
                    try:
                        item = object.__getattribute__(value, actual)
                    except AttributeError:
                        continue  # Absence is distinct from a present slot in the encoded attribute list.
                    attributes.setdefault(actual, item)
            node["attributes"] = [[name, self.value(item)] for name, item in attributes.items()]
        else:
            raise UnsupportedWorld("opaque state: " + node["type"])
        return {"ref": number}

    def pack(self, value):
        root = self.value(value)
        return {"root": root, "nodes": self.nodes}


def snapshot(objects, arena, defaults=None):
    """Read instance state independently of any application serializer."""
    arena = Path(arena).resolve()
    files = []
    def entries(directory):
        # Unlike recursive globs, an unreadable directory must not silently disappear.
        for path in directory.iterdir():
            yield path
            if not path.is_symlink() and path.is_dir():
                yield from entries(path)
    for path in sorted(entries(arena)):
        name = path.relative_to(arena).as_posix()
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        if path.is_symlink():
            target = os.readlink(path)
            prefix = str(arena)
            if target == prefix or target.startswith(prefix + os.sep):
                target = "<world>" + target[len(prefix):]
            files.append([name, "symlink", mode, target])
        elif path.is_dir():
            files.append([name, "directory", mode])
        elif path.is_file():
            if metadata.st_nlink > 1:
                raise UnsupportedWorld("hard-linked files need an explicit world: " + name)
            files.append([name, "file", mode, base64.b64encode(path.read_bytes()).decode("ascii")])
        else:
            raise UnsupportedWorld("unsupported filesystem node: " + name)
    return {"graph": _Graph(arena).pack(objects), "defaults": defaults, "files": files}


def _load(locator):
    module, separator, name = locator.partition(":")
    if not separator:
        raise UnsupportedWorld("invalid source locator: " + locator)
    value = importlib.import_module(module)
    for part in name.split("."):
        value = getattr(value, part)
    return value


def construct(spec, start=None):
    """Called by the worker after its arena and environment have been installed."""
    if _ACTIVE_ARENA is None:
        raise UnsupportedWorld("construction requires a fresh native worker")
    if spec.get("unsupported"):
        raise UnsupportedWorld("; ".join(spec["unsupported"]))
    start = start or {}
    cls = _load(spec["system"])
    kwargs = {}
    defaults = {}
    if spec.get("settings"):
        settings_type = _load(spec["settings"])
        shipped = settings_type()
        if not is_dataclass(shipped):
            raise UnsupportedWorld("the selected settings root is not a dataclass")
        defaults = {field.name: getattr(shipped, field.name) for field in fields(shipped)}
        # JSON is also the explicit finite boundary for setting recipes.
        json.dumps(defaults, allow_nan=False)
        if "settings" in start:
            kwargs[spec["settings_parameter"]] = settings_type(**start["settings"])
    elif start.get("settings"):
        raise UnsupportedWorld("this root has no derived settings parameter")
    objects = {"system": cls(**kwargs)}
    seeded = []
    if start.get("world"):
        sizes = spec["worlds"].get(start["world"])
        if sizes is None:
            raise UnsupportedWorld("unknown finite world: " + str(start["world"]))
        system = objects["system"]
        entities = spec["entities"]
        identifiers = {kind: list(getattr(system, item["list"])()) for kind, item in entities.items()}
        references = {item["parameters"][0]["name"]: kind for kind, item in entities.items()}
        pending = list(entities)
        while pending:
            progressed = False
            for kind in list(pending):
                item = entities[kind]
                required = [row for row in item["parameters"] if row["required"]]
                if any(references.get(row["name"]) in pending and references.get(row["name"]) != kind and not identifiers[references[row["name"]]] for row in required):
                    continue
                number = 1
                while len(identifiers[kind]) < sizes[kind]:
                    identifier = number if item["parameters"][0].get("annotation") == "int" else kind[:1].upper() + str(number)
                    number += 1
                    if identifier in identifiers[kind]:
                        continue
                    given = {}
                    for index, row in enumerate(required):
                        dependency = references.get(row["name"])
                        given[row["name"]] = (identifier if index == 0 else identifiers[dependency][0] if dependency
                                              else number if row.get("annotation") == "int" else kind + " " + str(number - 1))
                    try:
                        getattr(system, item["add"])(**given)
                    except Exception as exc:
                        raise UnsupportedWorld("cannot seed " + kind + ": " + str(exc)) from exc
                    seeded.append({"name": item["add"], "kwargs": given})
                    current = list(getattr(system, item["list"])())
                    if current == identifiers[kind]:
                        raise UnsupportedWorld("seeding did not create the requested entity")
                    identifiers[kind] = current
                pending.remove(kind)
                progressed = True
            if not progressed:
                raise UnsupportedWorld("cyclic entity construction needs an explicit world")
    if start.get("ui") is not None:
        if not spec.get("ui"):
            raise UnsupportedWorld("no UI root was derived")
        objects["ui"] = _load(spec["ui"])(objects["system"], **start["ui"])
    return objects, defaults, seeded


def _arguments(value, arena, results=()):
    if isinstance(value, dict):
        if set(value) == {"$file"}:
            path = Path(value["$file"])
            if path.is_absolute() or ".." in path.parts:
                raise UnsupportedWorld("file recipes must be relative to the world")
            return str(Path(arena) / path)
        if set(value) == {"$result"}:
            index = value["$result"]
            if type(index) is not int or not 0 <= index < len(results):
                raise UnsupportedWorld("a result recipe must name an earlier call")
            result = results[index]
            if result is not None and type(result) not in (bool, int, float, str):
                raise UnsupportedWorld("non-scalar result recipes need an explicit world")
            return result
        return {key: _arguments(item, arena, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_arguments(item, arena, results) for item in value]
    return value


def call(objects, recipe, arena, defaults, refusals=(), results=None):
    if _ACTIVE_ARENA is None:
        raise UnsupportedWorld("calls require a fresh native worker")
    name = recipe["name"]
    if name.startswith("_"):
        raise UnsupportedWorld("only public calls form a trace")
    before = snapshot(objects, arena, defaults)
    receiver = objects[recipe.get("receiver", "system")]
    results = [] if results is None else results
    output, error = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(error):
        try:
            value = getattr(receiver, name)(
                *_arguments(recipe.get("args", []), arena, results),
                **_arguments(recipe.get("kwargs", {}), arena, results),
            )
            if recipe.get("replace"):
                if type(value) is not type(objects["system"]):
                    raise UnsupportedWorld("a restored system has the wrong type")
                objects["system"] = value
                if "ui" in objects:
                    raise UnsupportedWorld("restore a UI through its public prefix")
            outcome, exception = "success", None
        except UnsupportedWorld:
            raise
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise UnsupportedWorld("the call terminated its interpreter") from exc
            value = None
            outcome = "refusal" if isinstance(exc, refusals) else "crash"
            exception = {"type": type(exc).__module__ + ":" + type(exc).__qualname__, "message": _diagnostic(str(exc), arena)}
    results.append(value)
    return {"call": recipe, "outcome": outcome, "exception": exception,
            "value": _Graph(arena).pack(value), "stdout": _diagnostic(output.getvalue(), arena), "stderr": _diagnostic(error.getvalue(), arena),
            "before": before, "after": snapshot(objects, arena, defaults)}


def _arena_guard(arena):
    """Bound supported synchronous Python I/O; this is not an OS security sandbox."""
    root = Path(arena).resolve()
    active = True
    original_open = os.open

    def ordinary_open(path, flags, mode=0o777, *, dir_fd=None):
        # The open audit event omits dir_fd, so its path cannot be resolved safely there.
        if dir_fd is not None:
            raise UnsupportedWorld("descriptor-relative I/O needs an explicit world")
        return original_open(path, flags, mode)

    def inside(value):
        if isinstance(value, int):
            raise UnsupportedWorld("descriptor I/O needs an explicit world")
        if isinstance(value, (str, bytes, os.PathLike)):
            try:
                Path(os.fsdecode(value)).resolve().relative_to(root)
            except ValueError as exc:
                raise UnsupportedWorld("write outside the disposable world") from exc

    def audit(event, args):
        if not active:
            return
        if event == "open":
            _path, mode, flags = args
            if (mode and any(char in mode for char in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                # fdopen is needed for ordinary mkstemp saves; the fd was opened through ordinary_open.
                if not isinstance(_path, int):
                    inside(_path)
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chdir", "os.chmod", "os.chown", "os.utime", "os.truncate"}:
            position = {"os.mkdir": 2, "os.remove": 1, "os.rmdir": 1, "os.chmod": 2, "os.chown": 3, "os.utime": 3}.get(event)
            if position is not None and args[position] not in (None, -1):
                raise UnsupportedWorld("descriptor-relative I/O needs an explicit world")
            inside(args[0])
        elif event in {"os.rename", "os.link", "os.symlink"}:
            if any(value not in (None, -1) for value in args[2:]):
                raise UnsupportedWorld("descriptor-relative I/O needs an explicit world")
            inside(args[0])
            inside(args[1])
        elif event in {"socket.connect", "subprocess.Popen", "os.fork"}:
            raise UnsupportedWorld("external processes or network need an explicit world")
    sys.addaudithook(audit)
    os.open = ordinary_open

    def finish():
        nonlocal active
        active = False
        os.open = original_open
    return finish


def _worker(request_path, response_path):
    global _ACTIVE_ARENA, _ACTIVE_CLASSES
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    response = None
    # This directory belongs only to this interpreter; protocol files stay outside it.
    with tempfile.TemporaryDirectory(prefix="flowguard-world-") as directory:
        arena = Path(directory)
        original_directory = Path.cwd()
        os.chdir(arena)
        _ACTIVE_ARENA = arena
        _ACTIVE_CLASSES = set(request["spec"]["classes"])
        for name in ("home", "temp"):
            (arena / name).mkdir()
        os.environ.update(HOME=str(arena / "home"), TMPDIR=str(arena / "temp"), TEMP=str(arena / "temp"), TMP=str(arena / "temp"))
        tempfile.tempdir = str(arena / "temp")
        random.seed(request.get("start", {}).get("seed", 0))
        finish_guard = _arena_guard(arena)
        try:
            for name, data in request.get("start", {}).get("files", {}).items():
                path = Path(_arguments({"$file": name}, arena))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(data))
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                objects, defaults, seeded = construct(request["spec"], request.get("start"))
                refusals = tuple(_load(name) for name in request["spec"].get("refusal", []))
            initial = snapshot(objects, arena, defaults)
            results = []
            steps = [call(objects, item, arena, defaults, refusals, results) for item in request["calls"]]
            response = {"initial": initial, "steps": steps, "final": snapshot(objects, arena, defaults),
                        "defaults": defaults, "construction_stdout": _diagnostic(output.getvalue(), arena), "construction_stderr": _diagnostic(error.getvalue(), arena)}
            response["seeding"] = seeded
        except BaseException as exc:
            response = {"unsupported": type(exc).__name__ + ": " + _diagnostic(str(exc), arena)}
        try:
            encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
            # The engine opened this protocol descriptor before entering the application world.
            os.write(int(response_path), encoded.encode("utf-8"))
        finally:
            # Engine cleanup uses descriptor-relative stdlib operations after all application work ends.
            finish_guard()
            os.chdir(original_directory)


def replay(spec, calls, start=None, *, timeout=30):
    """One real trace in a fresh interpreter, using the existing process owner."""
    root = Path(spec["root"]).resolve()
    with tempfile.TemporaryDirectory(prefix="flowguard-replay-") as directory:
        path = Path(directory)
        request = path / "request.json"
        request.write_text(json.dumps({"spec": spec, "calls": calls, "start": start or {}}), encoding="utf-8")
        response = path / "response.json"
        # The shared runner owns Popen; the worker opens its protocol stream before installing the arena guard.
        code = (
            "import os,sys;from flowguard.behave.project import _worker;"
            "fd=os.open(sys.argv[2],os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);"
            "_worker(sys.argv[1],fd)"
        )
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(child_import_path(root, {})),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
        completed, timed_out, clean = run_isolated_process(
            [sys.executable, "-c", code, str(request), str(response)], cwd=path, env=env,
            timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if timed_out or not clean or completed.returncode:
            raise UnsupportedWorld("native child failed: " + (completed.stderr or str(completed.returncode)))
        try:
            result = json.loads(response.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UnsupportedWorld("native child returned no complete observation") from exc
        if "unsupported" in result:
            raise UnsupportedWorld(result["unsupported"])
        return result


def restore(spec, prefix, checkpoint, start=None, tail=()):
    """Reconstruct only through public calls; reject an incomplete checkpoint."""
    result = replay(spec, [*prefix, *tail], start)
    observed = result["steps"][len(prefix) - 1]["after"] if prefix else result["initial"]
    if observed != checkpoint:
        raise UnsupportedWorld("public prefix did not reconstruct the complete checkpoint")
    return result
