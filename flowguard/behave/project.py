"""Native calls and complete supported observations in disposable worlds."""

from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
import hashlib
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
import types

from flowguard.map.common import child_import_path
from flowguard.map.runner import run_isolated_process

_ACTIVE_ARENA = None
_ACTIVE_CLASSES = set()


def state_key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_stamp(value):
    path = Path(value)
    try:
        info = path.lstat()
        row = {"mode": stat.S_IMODE(info.st_mode), "resolved": str(path.resolve())}
        if path.is_symlink():
            row["link"] = os.readlink(path)
        if path.is_file():
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            row["directory"] = True
        else:
            row["opaque"] = True
        return row
    except FileNotFoundError:
        return {"missing": True}


def directory_stamp(value):
    path = Path(value)
    if not path.is_dir():
        return {"missing": True}
    # Preserve actual enumeration order: applications may consume it.
    return {"entries": [[item.name, "link" if item.is_symlink() else "directory" if item.is_dir() else "file",
                          stat.S_IMODE(item.lstat().st_mode), os.readlink(item) if item.is_symlink() else None]
                         for item in path.iterdir()]}


class _Inputs:
    def __init__(self, arena):
        self.arena = Path(arena)
        self.files, self.directories = {}, {}
        self.busy = False
        self.reusable = True

    def record(self, event, args):
        if self.busy:
            return
        self.busy = True
        try:
            values = []
            if event == "open":
                path, mode, flags = args
                writing = bool(mode and any(char in mode for char in "wax+")) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
                if writing:
                    return
                if isinstance(path, int):
                    self.reusable = False
                    return
                values.append((path, self.files, file_stamp))
            elif event in {"os.listdir", "os.scandir"}:
                if isinstance(args[0], int):
                    self.reusable = False
                    return
                values.append((args[0] or os.curdir, self.directories, directory_stamp))
            elif event == "import":
                if args[1]:
                    values.append((args[1], self.files, file_stamp))
                else:
                    values.extend((path, self.directories, directory_stamp) for path in sys.path if path and Path(path).is_dir())
            for value, rows, stamp in values:
                path = Path(os.fsdecode(value)).absolute()
                try:
                    path.relative_to(self.arena)
                    continue  # Recreated closed-world inputs are already identified by the starting recipe.
                except ValueError:
                    pass
                key = str(path)
                if key not in rows:
                    rows[key] = stamp(path)
        except (OSError, TypeError, ValueError):
            self.reusable = False
        finally:
            self.busy = False

    def receipt(self):
        return {"files": self.files, "directories": self.directories, "reusable": self.reusable}


class _ObservedState:
    """Bounded observation of package data referenced by executed function frames."""
    def __init__(self, spec, arena, inputs=None):
        self.root = str(Path(spec["root"]).resolve()) + os.sep
        self.arena = arena
        self.enabled = False
        self.pending = {}
        self.hit = set()
        self.lines = set()
        self.busy = False
        self.inputs = inputs

    def namespace(self, value, depth=0, requested=()):
        definitions = (types.FunctionType, types.BuiltinFunctionType, staticmethod, classmethod, property,
                       types.MethodDescriptorType, types.GetSetDescriptorType, types.MemberDescriptorType, types.WrapperDescriptorType)
        omitted = {"__module__", "__doc__", "__qualname__", "__annotations__", "__dataclass_fields__",
                   "__dataclass_params__", "__match_args__", "__dict__", "__weakref__", "__builtins__",
                   "__loader__", "__spec__", "__package__", "__cached__"}
        result, identities = {}, []
        for name, item in vars(value).items():
            if name in omitted and name not in requested:
                continue
            if isinstance(item, definitions):
                identities.append((name, id(item)))
                continue
            if isinstance(item, type):
                if item.__module__ + ":" + item.__qualname__ not in _ACTIVE_CLASSES:
                    continue
                if depth >= 2:
                    raise UnsupportedWorld("deep package namespace data needs an explicit world")
                result[name], nested = self.namespace(item, depth + 1, requested)
                identities.extend(nested)
            elif isinstance(item, types.ModuleType):
                continue
            else:
                result[name] = item
            identities.append((name, id(item)))  # Temporary binding identity, never persisted as state.
        return result, identities

    def capture(self, frame):
        values, identities = {}, []
        names = set(frame.f_code.co_names) | set(frame.f_code.co_freevars)
        inferred = {}
        for locator in _ACTIVE_CLASSES:
            module, _, qualname = locator.partition(":")
            value = sys.modules.get(module)
            if qualname in names and value is not None and hasattr(value, qualname):
                inferred.setdefault(qualname, getattr(value, qualname))
        candidates = []
        # Defaults and attributes of the executing function can carry state outside its instances.
        candidates.extend(("function:" + name, value) for name, value in frame.f_globals.items()
                          if isinstance(value, types.FunctionType) and value.__code__ is frame.f_code)
        owner = frame.f_locals.get("self", frame.f_locals.get("cls"))
        if owner is not None:
            cls = owner if isinstance(owner, type) else type(owner)
            for base in cls.__mro__:
                value = base.__dict__.get(frame.f_code.co_name)
                value = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
                if isinstance(value, types.FunctionType) and value.__code__ is frame.f_code:
                    candidates.append(("executing-method", value))
        for name in sorted(names):
            if name in frame.f_code.co_freevars:
                value = frame.f_locals.get(name)
                identities.append(("closure:" + name, id(value)))
            elif name in frame.f_globals:
                value = frame.f_globals[name]
                identities.append(("global:" + name, id(value)))
            else:
                identities.append(("global:" + name, None))
                value = inferred.get(name, sys.modules.get(name))
                if value is None:
                    continue
            candidates.append((name, value))
        candidates.extend(("local:" + name, value) for name, value in frame.f_locals.items() if isinstance(value, (type, types.ModuleType)))
        namespaces = {}
        for name, value in candidates:
            if isinstance(value, types.ModuleType):
                filename = getattr(value, "__file__", "") or ""
                label = "module:" + value.__name__
                if not filename.startswith(self.root):
                    selected = {key: item for key, item in vars(value).items() if key in names and not isinstance(item, (types.ModuleType, type, types.FunctionType, types.BuiltinFunctionType))}
                    namespaces[label] = (selected, [(key, id(item)) for key, item in vars(value).items() if key in names])
                    continue
                namespaces[label] = self.namespace(value, requested=names)
            elif isinstance(value, type):
                if value.__module__ + ":" + value.__qualname__ not in _ACTIVE_CLASSES:
                    continue
                label = "class:" + value.__module__ + ":" + value.__qualname__
                namespaces[label] = self.namespace(value, requested=names)
            elif isinstance(value, (types.FunctionType, types.BuiltinFunctionType)):
                if isinstance(value, types.FunctionType) and value.__code__.co_filename.startswith(self.root):
                    values["function:" + name] = {"attributes": vars(value), "defaults": value.__defaults__, "kwdefaults": value.__kwdefaults__}
                continue
            else:
                values[name] = value
        for label, (data, references) in namespaces.items():
            values[label] = data
            identities.extend((label, *row) for row in references)
        return _Graph(self.arena).pack(dict(sorted(values.items()))), sorted(set(identities), key=str)

    def profile(self, frame, event, arg):
        # Observe calls that cross the source boundary, rather than names in unexecuted paths.
        if not self.enabled or self.busy or event not in {"call", "c_call"}:
            return
        caller = frame.f_back if event == "call" else frame
        if caller is None or not caller.f_code.co_filename.startswith(self.root):
            return
        module = frame.f_globals.get("__name__", "") if event == "call" else getattr(arg, "__module__", None)
        if not module and event == "c_call":
            owner = getattr(arg, "__self__", None)
            module = getattr(owner if isinstance(owner, type) else type(owner), "__module__", "")
        name = frame.f_code.co_name if event == "call" else getattr(arg, "__name__", "")
        if self.inputs is not None and module in {"os", "posix", "nt", "pathlib", "genericpath", "ntpath", "posixpath"} and name in {"stat", "lstat", "fstat", "getmtime", "getatime", "getctime", "getsize"}:
            self.inputs.reusable = False  # These actual calls have no complete input audit event.
        if event == "c_call" and module == "builtins" and name == "globals":
            raise UnsupportedWorld("dynamic global namespace access needs an explicit world")
        if module.split(".")[0] in {"random", "time", "datetime", "secrets", "threading", "_thread"}:
            raise UnsupportedWorld("called nondeterministic resource needs an explicit world")

    def trace(self, frame, event, arg):
        if not self.enabled or self.busy or not frame.f_code.co_filename.startswith(self.root) or frame.f_code.co_name == "<module>":
            return None
        self.busy = True
        try:
            key = id(frame)
            if event == "call":
                if not frame.f_code.co_name.startswith("<"):
                    self.hit.add(frame.f_code.co_filename[len(self.root):].replace(os.sep, "/") + "#" + frame.f_code.co_qualname.replace(".<locals>.", "."))
                self.pending[key] = self.capture(frame)
            elif event == "line":
                self.lines.add((frame.f_code.co_filename[len(self.root):].replace(os.sep, "/"), frame.f_lineno))
            elif event in {"return", "exception"} and key in self.pending:
                previous = self.pending[key]
                if self.capture(frame) != previous:
                    raise UnsupportedWorld("executed package class/global/closure data changed outside the instance graph")
                if event == "return":
                    self.pending.pop(key, None)
        finally:
            self.busy = False
        return self.trace


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
    return {"graph": _Graph(arena).pack(objects), "defaults": defaults, "files": files,
            "root_mode": stat.S_IMODE(arena.stat().st_mode)}


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
    # Static declarations are hints. The worker observes only actually executed package frames.
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
            attribute = getattr(receiver, name)
            value = attribute if recipe.get("property") else attribute(
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
    after = snapshot(objects, arena, defaults)
    return {"call": recipe, "outcome": outcome, "exception": exception,
            "value": _Graph(arena).pack(value), "stdout": _diagnostic(output.getvalue(), arena), "stderr": _diagnostic(error.getvalue(), arena),
            "before": before, "after": after, "before_key": state_key(before), "after_key": state_key(after)}


def _arena_guard(arena, inputs=None):
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
        if inputs is not None:
            inputs.record(event, args)
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
        elif event in {"socket.connect", "subprocess.Popen", "os.fork", "os.system", "os.exec", "os.posix_spawn", "os.putenv", "os.unsetenv"}:
            raise UnsupportedWorld("external processes or network need an explicit world")
    sys.addaudithook(audit)
    os.open = ordinary_open

    def finish():
        nonlocal active
        active = False
        os.open = original_open
    return finish


class _Session:
    """One concrete world in one child, reconstructed only through public prefixes."""
    def __init__(self, spec, start, arena, observed):
        self.spec, self.start, self.arena, self.observed = spec, start, Path(arena), observed
        self.import_path = list(sys.path)
        self.executed_calls = 0
        self.resets = 0

    def reset(self, prefix=()):
        self.observed.enabled = False
        self.observed.pending.clear()
        self.objects = None
        os.chmod(self.arena, 0o700)
        def remove(path):
            if path.is_dir() and not path.is_symlink():
                os.chmod(path, 0o700)
                for child in path.iterdir():
                    remove(child)
                path.rmdir()
            else:
                path.unlink()
        for path in self.arena.iterdir():
            remove(path)
        for name in ("home", "temp"):
            (self.arena / name).mkdir()
        for name, data in self.start.get("files", {}).items():
            path = Path(_arguments({"$file": name}, self.arena))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(data))
        sys.path[:] = self.import_path
        for name, module in list(sys.modules.items()):
            filename = getattr(module, "__file__", "") or ""
            if filename.startswith(self.observed.root):
                del sys.modules[name]
        importlib.invalidate_caches()
        random.seed(self.start.get("seed", 0))
        _load(self.spec["system"])
        if self.spec.get("settings"):
            _load(self.spec["settings"])
        if self.spec.get("ui"):
            _load(self.spec["ui"])
        self.observed.enabled = True
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            self.objects, self.defaults, self.seeded = construct(self.spec, self.start)
        self.construction_stdout = _diagnostic(output.getvalue(), self.arena)
        self.construction_stderr = _diagnostic(error.getvalue(), self.arena)
        self.refusals = tuple(_load(name) for name in self.spec.get("refusal", []))
        self.prefix, self.results, self.outcomes = [], [], []
        self.last = None
        self.current = snapshot(self.objects, self.arena, self.defaults)
        self.resets += 1
        for recipe in prefix:
            self.step(recipe)
        return self.current

    def step(self, recipe, *, keep=True):
        row = call(self.objects, recipe, self.arena, self.defaults, self.refusals, self.results if keep else [])
        self.executed_calls += 1
        self.current = row["after"]
        if keep:
            self.prefix.append(recipe)
            self.outcomes.append(row["outcome"])
            self.last = row
        return row

    def query(self, receiver, name, args=(), kwargs=None, *, property=False):
        row = self.step({"receiver": receiver, "name": name, "args": list(args), "kwargs": kwargs or {}, "property": property}, keep=False)
        if row["outcome"] != "success" or row["before_key"] != row["after_key"]:
            raise UnsupportedWorld("a required public query is not a pure successful observation")
        return row["value"]

    def receipt(self):
        return {"child_pid": os.getpid(), "executed_calls": self.executed_calls, "resets": self.resets,
                "hit_functions": sorted(self.observed.hit), "hit_lines": sorted(self.observed.lines)}


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
        inputs = _Inputs(arena)
        observed = _ObservedState(request["spec"], arena, inputs)
        finish_guard = _arena_guard(arena, inputs)
        old_trace = sys.gettrace()
        old_profile = sys.getprofile()
        sys.settrace(observed.trace)
        sys.setprofile(observed.profile)
        try:
            session = _Session(request["spec"], request.get("start", {}), arena, observed)
            session.reset()
            operation = request.get("operation", "trace")
            if operation == "trace":
                initial = session.current
                steps = [session.step(item) for item in request["calls"]]
                response = {"initial": initial, "steps": steps, "final": session.current, "defaults": session.defaults,
                            "seeding": session.seeded, "construction_stdout": session.construction_stdout,
                            "construction_stderr": session.construction_stderr}
            else:
                from .explore import explore, focused_search, directed_search, evaluate
                options = request.get("options", {})
                if operation == "explore":
                    response = explore(session, **options)
                elif operation == "search":
                    response = focused_search(session, **options)
                elif operation == "directed":
                    response = directed_search(session, **options)
                elif operation == "prove":
                    divergence = None
                    for index, item in enumerate(request["calls"]):
                        row = session.step(item)
                        expected = options.get("outcomes")
                        if expected is not None and (index >= len(expected) or row["outcome"] != expected[index]):
                            divergence = index
                            break
                    response = {"matched": divergence is None and evaluate(session, options["goal"]),
                                "divergence": divergence, "state_key": state_key(session.current)}
                else:
                    raise UnsupportedWorld("unknown native operation")
            if operation != "trace":
                response["execution"] = session.receipt()
            response["footprint"] = inputs.receipt()
        except BaseException as exc:
            response = {"unsupported": type(exc).__name__ + ": " + _diagnostic(str(exc), arena)}
        try:
            observed.enabled = False
            sys.settrace(old_trace)
            sys.setprofile(old_profile)
            encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
            # The engine opened this protocol descriptor before entering the application world.
            os.write(int(response_path), encoded.encode("utf-8"))
        finally:
            # Engine cleanup uses descriptor-relative stdlib operations after all application work ends.
            finish_guard()
            os.chdir(original_directory)


def replay(spec, calls, start=None, *, timeout=30, operation="trace", options=None):
    """One real trace in a fresh interpreter, using the existing process owner."""
    root = Path(spec["root"]).resolve()
    with tempfile.TemporaryDirectory(prefix="flowguard-replay-") as directory:
        path = Path(directory)
        request = path / "request.json"
        request.write_text(json.dumps({"spec": spec, "calls": calls, "start": start or {},
                                       "operation": operation, "options": options or {}}), encoding="utf-8")
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


def restore(spec, prefix, checkpoint, start=None, tail=(), *, session=None):
    """Reconstruct only through public calls; reject an incomplete checkpoint."""
    if session is not None:
        observed = session.reset(prefix)
        if observed != checkpoint:
            raise UnsupportedWorld("public prefix did not reconstruct the complete checkpoint")
        return [session.step(item) for item in tail]
    result = replay(spec, [*prefix, *tail], start)
    observed = result["steps"][len(prefix) - 1]["after"] if prefix else result["initial"]
    if observed != checkpoint:
        raise UnsupportedWorld("public prefix did not reconstruct the complete checkpoint")
    return result
