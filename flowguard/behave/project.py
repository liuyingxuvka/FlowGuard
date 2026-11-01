"""Native calls and complete supported observations in disposable worlds."""

from __future__ import annotations

import base64
import copy
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
import hashlib
import inspect
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
_ACTIVE_SOURCE_ROOT = None


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
    def __init__(self, arena, source_root, empty_bytecode):
        self.arena = Path(arena)
        self.source_root = str(Path(source_root).resolve()) + os.sep
        self.empty_bytecode = Path(empty_bytecode)
        self.files, self.directories = {}, {}
        self.busy = False
        self.reusable = True
        self.recording_tests = False
        self.untracked = set()
        imported = Path(__file__).absolute().parents[2]
        package = imported / "flowguard"
        self.engine_package = Path(__file__).resolve().parents[1]
        self.engine_import_root = None
        try:
            if {path.name for path in imported.iterdir()} == {"flowguard"}:
                if package.is_symlink() and package.resolve() == self.engine_package:
                    self.engine_import_root = imported
                elif imported.name.startswith("flowguard-package-"):
                    self.reusable = False
                    self.untracked.add("copied engine import shim lacks a stable source path")
        except OSError:
            pass

    def record(self, event, args, *, caller=None):
        if self.busy or event not in {"open", "os.listdir", "os.scandir", "metadata", "import"}:
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
                    self.untracked.add("read file descriptor without a path")
                    return
                values.append((path, self.files, file_stamp))
            elif event in {"os.listdir", "os.scandir"}:
                if isinstance(args[0], int):
                    self.reusable = False
                    self.untracked.add("directory enumeration via a descriptor")
                    return
                values.append((args[0] or os.curdir, self.directories, directory_stamp))
            elif event == "metadata":
                values.append((args[0], self.files, file_stamp))
            elif event == "import":
                if args[1]:
                    values.append((args[1], self.files, file_stamp))
                else:
                    values.extend((path, self.directories, directory_stamp) for path in sys.path if path and Path(path).is_dir())
            for value, rows, stamp in values:
                path = Path(os.fsdecode(value)).absolute()
                if path.is_relative_to(self.empty_bytecode):
                    if path.exists():
                        self.reusable = False
                        self.untracked.add("controller bytecode probe directory was not empty")
                    continue
                if self.engine_import_root is not None:
                    # The existing import owner exposes one controlled symlink, not an arbitrary /tmp tree.
                    if path == self.engine_import_root:
                        path = self.engine_package
                    elif path.is_relative_to(self.engine_import_root / "flowguard"):
                        path = self.engine_package / path.relative_to(self.engine_import_root / "flowguard")
                try:
                    path.relative_to(self.arena)
                    if event in {"os.listdir", "os.scandir"}:
                        frame = caller
                        while frame is not None:
                            if frame.f_code is snapshot.__code__ or frame.f_code.co_filename.startswith("<frozen importlib"):
                                break
                            if frame.f_code.co_filename.startswith(self.source_root):
                                self.reusable = False  # Snapshot files preserve content, not directory enumeration order.
                                self.untracked.add("application-consumed arena directory enumeration order")
                                break
                            frame = frame.f_back
                    continue  # Recreated closed-world inputs are already identified by the starting recipe.
                except ValueError:
                    pass
                key = str(path)
                if key not in rows:
                    rows[key] = stamp(path)
        except (OSError, TypeError, ValueError):
            self.reusable = False
            self.untracked.add("unidentified filesystem input: " + event)
        finally:
            self.busy = False

    def receipt(self):
        return {"files": self.files, "directories": self.directories, "reusable": self.reusable,
                "untracked": sorted(self.untracked)}


class _ObservedState:
    """Bounded observation of package data referenced by executed function frames."""
    def __init__(self, spec, arena, inputs=None):
        self.root = str(Path(spec["root"]).resolve()) + os.sep
        self.arena = arena
        self.enabled = False
        self.pending = {}
        self.hit = set()
        self.recorded_hits = set()
        self.lines = set()
        self.statement_hits = set()
        self.call_hits = set()
        self.statement_ids = {(row["path"], row["function"], row["line"]): row["id"]
                              for row in spec.get("statements", []) if row["unambiguous"]}
        self.monitoring_tool = None
        self.monitored_codes = set()
        self.busy = False
        self.inputs = inputs

    def line(self, code, line):
        if not self.enabled or self.busy or not code.co_filename.startswith(self.root) or code.co_name == "<module>":
            return
        path = code.co_filename[len(self.root):].replace(os.sep, "/")
        self.lines.add((path, line))
        identifier = self.statement_ids.get((path, code.co_qualname, line))
        if identifier is not None:
            self.statement_hits.add(identifier)
            self.call_hits.add(identifier)

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
        recording = self.inputs is not None and self.inputs.recording_tests
        if (not self.enabled and not recording) or self.busy or event not in {"call", "c_call"}:
            return
        caller = frame.f_back if event == "call" else frame
        if caller is None:
            return
        direct = caller.f_code.co_filename.startswith(self.root)
        if not direct:
            possible = frame.f_code.co_name if event == "call" else getattr(arg, "__name__", "")
            if possible not in {"exists", "is_file", "is_dir", "is_symlink", "isfile", "isdir", "islink", "stat", "lstat", "fstat", "getmtime", "getatime", "getctime", "getsize"}:
                return
        module = frame.f_globals.get("__name__", "") if event == "call" else getattr(arg, "__module__", None)
        if not module and event == "c_call":
            owner = getattr(arg, "__self__", None)
            module = getattr(owner if isinstance(owner, type) else type(owner), "__module__", "")
        name = frame.f_code.co_name if event == "call" else getattr(arg, "__name__", "")
        metadata = module.split(".")[0] in {"os", "posix", "nt", "pathlib", "genericpath", "ntpath", "posixpath"} and name in {"exists", "is_file", "is_dir", "is_symlink", "isfile", "isdir", "islink", "stat", "lstat", "fstat", "getmtime", "getatime", "getctime", "getsize"}
        if not direct:
            if not metadata:
                return
            ancestor = caller
            while ancestor is not None and not ancestor.f_code.co_filename.startswith(self.root):
                if ancestor.f_code is snapshot.__code__:
                    return  # Recording checkpoints read their own arena, not application metadata.
                ancestor = ancestor.f_back
            if ancestor is None or (self.inputs is not None and self.inputs.busy):
                return
        if self.inputs is not None and module.split(".")[0] in {"os", "posix", "nt", "pathlib", "genericpath", "ntpath", "posixpath"}:
            if (name == "stat" and caller.f_code.co_filename == "<frozen importlib._bootstrap_external>"
                    and caller.f_code.co_name == "_path_stat"):
                current, resolving = caller.f_back, False
                while current is not None and current.f_code.co_filename.startswith(("<frozen importlib.", "<frozen zipimport>")):
                    resolving |= current.f_code.co_name in {"_find_and_load", "_find_and_load_unlocked"}
                    current = current.f_back
                if resolving:
                    path = caller.f_locals.get("path")
                    if isinstance(path, (str, bytes, os.PathLike)):
                        self.inputs.record("metadata", (path,))
                    else:
                        self.inputs.reusable = False
                        self.inputs.untracked.add("import resolution metadata path was unavailable")
                    return
            if event == "call" and name in {"exists", "is_file", "is_dir", "is_symlink", "isfile", "isdir", "islink"}:
                path = frame.f_locals.get("self", frame.f_locals.get("path"))
                if isinstance(path, (str, bytes, os.PathLike)):
                    self.inputs.record("metadata", (path,))
                else:
                    self.inputs.reusable = False
                    self.inputs.untracked.add("filesystem metadata path was unavailable")
            elif name in {"stat", "lstat", "fstat", "getmtime", "getatime", "getctime", "getsize"}:
                ancestor = caller
                while ancestor is not None:
                    if ancestor.f_globals.get("__name__", "").split(".")[0] in {"pathlib", "genericpath", "ntpath", "posixpath"} and ancestor.f_code.co_name in {"exists", "is_file", "is_dir", "is_symlink", "isfile", "isdir", "islink"}:
                        break  # Only the already-recorded boolean result escapes this helper.
                    if ancestor.f_code.co_filename.startswith(self.root):
                        ancestor = None
                        break
                    ancestor = ancestor.f_back
                if ancestor is None:
                    self.inputs.reusable = False  # Full metadata records exceed this input boundary.
                    self.inputs.untracked.add("application-consumed full filesystem metadata")
        if event == "c_call" and module == "builtins" and name == "globals":
            if recording:
                self.inputs.reusable = False
                self.inputs.untracked.add("recording consumed dynamic global namespace")
            else:
                raise UnsupportedWorld("dynamic global namespace access needs an explicit world")
        if module.split(".")[0] in {"random", "time", "datetime", "secrets", "threading", "_thread"}:
            if recording:
                self.inputs.reusable = False
                self.inputs.untracked.add("recording called nondeterministic resource: " + module + "." + name)
            else:
                raise UnsupportedWorld("called nondeterministic resource needs an explicit world")

    def trace(self, frame, event, arg):
        if (not self.enabled and self.inputs is not None and self.inputs.recording_tests
                and not self.busy and event == "call" and frame.f_code.co_filename.startswith(self.root)
                and not frame.f_code.co_name.startswith("<")):
            ancestor = frame.f_back
            while ancestor is not None:
                if ancestor.f_code is snapshot.__code__:
                    return None
                ancestor = ancestor.f_back
            self.recorded_hits.add(frame.f_code.co_filename[len(self.root):].replace(os.sep, "/")
                                   + "#" + frame.f_code.co_qualname.replace(".<locals>.", "."))
        if not self.enabled or self.busy or not frame.f_code.co_filename.startswith(self.root) or frame.f_code.co_name == "<module>":
            return None
        self.busy = True
        try:
            key = id(frame)
            if event == "call":
                if self.monitoring_tool is not None:
                    frame.f_trace_lines = False
                    if frame.f_code not in self.monitored_codes:
                        sys.monitoring.set_local_events(self.monitoring_tool, frame.f_code, sys.monitoring.events.LINE)
                        self.monitored_codes.add(frame.f_code)
                if not frame.f_code.co_name.startswith("<"):
                    self.hit.add(frame.f_code.co_filename[len(self.root):].replace(os.sep, "/") + "#" + frame.f_code.co_qualname.replace(".<locals>.", "."))
                self.pending[key] = self.capture(frame)
            elif event == "line":
                if self.monitoring_tool is None:
                    self.line(frame.f_code, frame.f_lineno)
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
        # The worker has already canonicalized this owned root. Other paths still
        # resolve normally, including relative paths and aliases supplied by callers.
        self.arena = (_ACTIVE_ARENA if _ACTIVE_ARENA is not None
                      and type(arena) is type(_ACTIVE_ARENA) and arena == _ACTIVE_ARENA
                      else Path(arena).resolve())
        self.seen = {}
        self.nodes = []

    def value(self, value):
        if value is str or value is int or value is float or value is bool:
            return {"builtin_type": value.__module__ + ":" + value.__qualname__}
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


def ui_identity(spec, prefix, receiver):
    """Name a public UI actor independently of its run-local receiver handle."""
    construction = next((row for row in prefix if row.get("construct") == "ui" and row["receiver"] == receiver), None)
    if construction is None:
        raise UnsupportedWorld("the UI witness has no public construction event")
    parameters = [row for row in spec["ui_constructor"]["parameters"] if row["name"] != spec["ui_constructor"]["system_parameter"]]
    actor = {row["name"]: row["default"] for row in parameters if "default" in row}
    actor.update({row["name"]: value for row, value in zip(parameters, construction.get("args", []))})
    actor.update(construction.get("kwargs", {}))
    return {"receiver": spec["ui"], "actor": actor}


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


def call(objects, recipe, arena, defaults, refusals=(), results=None, *, capture=False):
    if _ACTIVE_ARENA is None:
        raise UnsupportedWorld("calls require a fresh native worker")
    name = recipe["name"]
    if name.startswith("_"):
        raise UnsupportedWorld("only public calls form a trace")
    before = snapshot(objects, arena, defaults)
    receiver = objects[recipe.get("receiver", "system")]
    results = [] if results is None else results
    output, error = io.StringIO(), io.StringIO()
    bindings, bindings_graph, binding_error = None, None, None
    with redirect_stdout(output), redirect_stderr(error):
        try:
            attribute = getattr(receiver, name)
            if recipe.get("property"):
                value = attribute
                if capture:
                    bindings = {}
                    bindings_graph = _Graph(arena).pack({})
            else:
                args = _arguments(recipe.get("args", []), arena, results)
                kwargs = _arguments(recipe.get("kwargs", {}), arena, results)
                if capture:
                    try:
                        bound = inspect.signature(attribute).bind(*args, **kwargs)
                        bound.apply_defaults()
                        from .explore import plain
                        bindings_graph = _Graph(arena).pack(dict(bound.arguments))
                        bindings = plain(bindings_graph)
                        json.dumps(bindings, allow_nan=False)
                    except (TypeError, ValueError, RecursionError, UnsupportedWorld) as exc:
                        bindings, binding_error = None, str(exc)
                value = attribute(*args, **kwargs)
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
            stack, traceback = [], exc.__traceback__
            while traceback is not None:
                frame = traceback.tb_frame
                filename = Path(frame.f_code.co_filename)
                if _ACTIVE_SOURCE_ROOT is not None and filename.is_absolute():
                    try:
                        relative = filename.resolve().relative_to(_ACTIVE_SOURCE_ROOT)
                    except (OSError, RuntimeError, ValueError):
                        pass
                    else:
                        stack.append({"path": relative.as_posix(), "line": traceback.tb_lineno,
                                      "function": frame.f_code.co_qualname})
                traceback = traceback.tb_next
            exception.update(source=stack[-1] if stack else None, stack=stack)
    results.append(value)
    after = snapshot(objects, arena, defaults)
    row = {"call": recipe, "outcome": outcome, "exception": exception,
            "value": _Graph(arena).pack(value), "stdout": _diagnostic(output.getvalue(), arena), "stderr": _diagnostic(error.getvalue(), arena),
            "before": before, "after": after, "before_key": state_key(before), "after_key": state_key(after)}
    if capture:
        row.update(resolved_args=bindings, resolved_args_graph=bindings_graph, binding_error=binding_error)
    return row


def capture_facts(spec, states, events, *, complete=False, missing=(), initial=None):
    """Detach public observations from executed rows; never run a normative rule."""
    captured = {"spec": spec, "steps": [], "states": [], "complete": complete, "missing": list(missing)}
    if initial is not None:
        captured["states"].append(initial)
    if len(states) != len(events):
        captured["missing"].append("native event and origin ledger lengths differ")
    for origin, event in zip(states, events):
        before, after = event.get("before_observations"), event.get("after_observations")
        if before is None or after is None:
            captured["missing"].append("public before/after observations were not captured")
            continue
        start, prefix, outcomes = origin["start"], origin["prefix"], origin["outcomes"]
        end_prefix, end_outcomes = [*prefix, event["call"]], [*outcomes, event["outcome"]]
        captured["states"].extend([
            {"start": start, "prefix": prefix, "outcomes": outcomes,
             "state_key": event["before_key"], "observation": before},
            {"start": start, "prefix": end_prefix, "outcomes": end_outcomes,
             "state_key": event["after_key"], "observation": after},
        ])
        captured["steps"].append({"start": start, "prefix": end_prefix, "outcomes": end_outcomes,
            "call": event["call"], "outcome": event["outcome"], "args": event.get("resolved_args"),
            "before_key": event["before_key"], "after_key": event["after_key"], "before": before, "after": after})
    captured["missing"] = sorted(set(captured["missing"]))
    captured["complete"] = complete and not captured["missing"]
    return captured


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
        if not active or event not in {
            "open", "os.listdir", "os.scandir", "metadata", "import",
            "os.mkdir", "os.remove", "os.rmdir", "os.chdir", "os.chmod", "os.chown", "os.utime", "os.truncate",
            "os.rename", "os.link", "os.symlink", "socket.connect", "subprocess.Popen", "os.fork", "os.system",
            "os.exec", "os.posix_spawn", "os.putenv", "os.unsetenv",
        }:
            return
        if inputs is not None and event in {"open", "os.listdir", "os.scandir", "metadata", "import"}:
            inputs.record(event, args, caller=sys._getframe(1) if event in {"os.listdir", "os.scandir"} else None)
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
        self.public_steps = 0
        self.replayed_steps = 0
        self.resets = 0
        self.query_facts = {}
        self.base_prefix = []
        self.observe_transitions = False
        self._key_current = None
        self._key_defaults = None
        self._key_value = None
        from .capture import Ledger
        self.rule_ledger = Ledger(spec) if spec.get("capture_shape") else None
        self.capture_admitted = True
        self._capture_reading = False
        self._capture_view_cache = None
        self._capture_prefix = None
        self._capture_ref = None
        self._capture_settings = {**spec.get("shipped", {}), **start.get("settings", {})}

    def _capture_enabled(self):
        return (self.rule_ledger is not None and self.capture_admitted and not self._capture_reading
                and state_key({**self.spec.get("shipped", {}), **self.start.get("settings", {})}) == state_key(self._capture_settings))

    def _capture_origin(self):
        if self._capture_prefix is not self.prefix or self._capture_length != len(self.prefix):
            self._capture_ref = self.rule_ledger.origin(self.start, self.prefix, self.outcomes)
            self._capture_prefix, self._capture_length = self.prefix, len(self.prefix)
        return self._capture_ref

    def _capture_view(self):
        """Read pure public facts; an impure probe cannot continue this producer."""
        key = self.current_key
        if self._capture_view_cache is not None and self._capture_view_cache[0] == key:
            return self._capture_view_cache[1]
        values, unknown, identifiers, identifiers_graph = [], [], {}, {}
        previous_reading = self._capture_reading
        self._capture_reading = True

        def read(name, args=()):
            try:
                result = self.query("system", name, args)
            except UnsupportedWorld as exc:
                if not getattr(exc, "pure_observation", False):
                    # An escaping watcher error may precede call()'s after
                    # snapshot. Never infer heap purity from cached current.
                    self.rule_ledger.missing.append("capture query could not be observed purely: " + name)
                    raise
                unknown.append(name)
                return None
            return result

        try:
            for kind, entity in self.spec.get("entities", {}).items():
                result = read(entity["list"])
                if result is not None:
                    identifiers_graph[kind] = result
                    from .explore import plain
                    try:
                        identifiers[kind] = plain(result)
                    except (UnsupportedWorld, TypeError, RecursionError):
                        unknown.append(entity["list"])
            for query, facts in self.spec.get("entity_queries", {}).items():
                for identifier in identifiers.get(facts["entity"], ()):
                    value = read(query, [identifier])
                    if query not in unknown:
                        values.append({"query": query, "entity": facts["entity"], "args": [identifier], "value_graph": value})
        finally:
            self._capture_reading = previous_reading
        result = {"values": values, "unknown": sorted(set(unknown)), "identifiers": identifiers,
                  "identifiers_graph": identifiers_graph}
        self._capture_view_cache = (self.current_key, result)
        return result

    def _capture_state(self):
        ref = self._capture_origin()
        view = self._capture_view()
        return self.rule_ledger.view(self.current_key, view, ref), view

    @property
    def current_key(self):
        """Memoize one engine-owned observation, not a future execution state.

        Graph/file observations are detached and read-only; defaults retain their
        original alias, so fingerprint those small values on every lookup. Custom
        JSON containers and cycles keep the original full-serialization path.
        """
        current = self.current
        pending, active = [(current["defaults"], False)], set()
        while pending:
            value, leaving = pending.pop()
            if value is None or type(value) in (bool, int, float, str):
                continue
            if type(value) not in (dict, list, tuple):
                return state_key(current)
            identity = id(value)
            if leaving:
                active.remove(identity)
                continue
            if identity in active:
                return state_key(current)
            active.add(identity)
            pending.append((value, True))
            children = (item for pair in value.items() for item in pair) if type(value) is dict else value
            pending.extend((item, False) for item in children)
        defaults_key = state_key(current["defaults"])
        if self._key_current is not current or self._key_defaults != defaults_key:
            self._key_value = state_key(current)
            self._key_current, self._key_defaults = current, defaults_key
        return self._key_value

    def reset(self, prefix=(), *, start=None):
        # Each construction event below recreates its own session after its preceding public setup.
        prefix = prefix or self.base_prefix
        if start is not None:
            self.start = start
        self.observed.enabled = False
        self.observed.pending.clear()
        self.query_facts.clear()  # Source modules and their actual class bindings are rebuilt below.
        self._capture_view_cache = None
        self._capture_prefix = None
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
        self.refusals = tuple(_load(name) for name in self.spec.get("refusal", []))
        self.observed.enabled = True
        output, error = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(output), redirect_stderr(error):
                self.objects, self.defaults, self.seeded = construct(self.spec, self.start)
        except self.refusals as exc:
            kind = type(exc).__module__ + ":" + type(exc).__qualname__
            raise UnsupportedWorld("declared construction refusal " + kind + ": " + _diagnostic(str(exc), self.arena)) from exc
        self.construction_stdout = _diagnostic(output.getvalue(), self.arena)
        self.construction_stderr = _diagnostic(error.getvalue(), self.arena)
        self.prefix, self.results, self.outcomes = [], [], []
        self.last = None
        self.current = snapshot(self.objects, self.arena, self.defaults)
        self.resets += 1
        if self._capture_enabled():
            self._capture_state()
        for recipe in prefix:
            self.step(recipe)
            self.replayed_steps += 1
        return self.current

    def step(self, recipe, *, keep=True):
        before_observations = None
        capture = keep and self._capture_enabled()
        before_ref = None
        if capture:
            before_ref, before_observations = self._capture_state()
        if keep and self.observe_transitions:
            from .explore import observations
            before_observations = observations(self, all_queries=True)
        self.observed.call_hits.clear()
        if recipe.get("construct"):
            receiver = recipe.get("receiver", "")
            if recipe["construct"] != "ui" or not self.spec.get("ui") or not receiver.startswith("ui:") or receiver in self.objects:
                raise UnsupportedWorld("invalid source-bound session construction")
            before = self.current
            output, error = io.StringIO(), io.StringIO()
            constructor = _load(self.spec["ui"])
            args = _arguments(recipe.get("args", []), self.arena, self.results)
            kwargs = _arguments(recipe.get("kwargs", {}), self.arena, self.results)
            bindings, bindings_graph, binding_error = None, None, None
            if capture:
                try:
                    signature = inspect.signature(constructor)
                    bound = signature.bind(self.objects["system"], *args, **kwargs)
                    bound.apply_defaults()
                    bound.arguments.pop(next(iter(signature.parameters)), None)
                    from .explore import plain
                    bindings_graph = _Graph(self.arena).pack(dict(bound.arguments))
                    bindings = plain(bindings_graph)
                except (TypeError, ValueError, RecursionError, UnsupportedWorld) as exc:
                    binding_error = str(exc)
            with redirect_stdout(output), redirect_stderr(error):
                value = constructor(self.objects["system"], *args, **kwargs)
            self.objects[receiver] = value
            after = snapshot(self.objects, self.arena, self.defaults)
            row = {"call": recipe, "outcome": "success", "exception": None,
                   "value": _Graph(self.arena).pack(None), "stdout": _diagnostic(output.getvalue(), self.arena),
                   "stderr": _diagnostic(error.getvalue(), self.arena), "before": before, "after": after,
                   "before_key": state_key(before), "after_key": state_key(after)}
            if capture:
                row.update(resolved_args=bindings, resolved_args_graph=bindings_graph, binding_error=binding_error)
        else:
            receiver = recipe.get("receiver", "system")
            refusals = self.refusals
            if receiver != "system":
                import builtins
                refusals += tuple(getattr(builtins, name) for name in self.spec.get("ui_refusal", []))
            row = call(self.objects, recipe, self.arena, self.defaults, refusals, self.results if keep else [],
                       capture=keep and bool(self.spec.get("capture_shape")))
        row["hit_statements"] = sorted(self.observed.call_hits)
        self.executed_calls += 1
        self.current = row["after"]
        if keep and self.observe_transitions:
            after_observations = observations(self, all_queries=True)
            previous = {(item["query"], state_key(item["args"])): item["value"] for item in before_observations["values"]}
            row.update(before_observations=before_observations, after_observations=after_observations)
            row["transitions"] = [{"query": item["query"], "args": item["args"],
                                   "before": previous[(item["query"], state_key(item["args"]))], "value": item["value"],
                                   "action": recipe.get("name"), "receiver": "system"}
                                  for item in after_observations["values"]
                                  if (item["query"], state_key(item["args"])) in previous
                                  and state_key(previous[(item["query"], state_key(item["args"]))]) != state_key(item["value"])]
        if keep:
            self.public_steps += 1
            self.prefix.append(recipe)
            self.outcomes.append(row["outcome"])
            self.last = row
            if capture:
                self._capture_ref = self.rule_ledger.advance(self._capture_ref, recipe, row["outcome"])
                self._capture_prefix, self._capture_length = self.prefix, len(self.prefix)
                if row["outcome"] == "success" or row["before_key"] != row["after_key"]:
                    after_ref, _ = self._capture_state()
                    self.rule_ledger.record(self._capture_ref, row, before_ref, after_ref)
        return row

    def query(self, receiver, name, args=(), kwargs=None, *, property=False):
        previous = self.current
        key = (self.current_key, receiver, name, state_key(_Graph(self.arena).pack([list(args), kwargs or {}, property])))
        reusable = self.observed.inputs is not None and self.observed.inputs.reusable
        if reusable and key in self.query_facts:
            return self.query_facts[key]
        row = self.step({"receiver": receiver, "name": name, "args": list(args), "kwargs": kwargs or {}, "property": property}, keep=False)
        if row["outcome"] != "success" or row["before_key"] != row["after_key"]:
            error = UnsupportedWorld("a required public query is not a pure successful observation")
            error.pure_observation = row["outcome"] == "refusal" and row["before_key"] == row["after_key"]
            raise error
        same_observation = key[0] == row["before_key"] == row["after_key"]
        if same_observation:
            self.current = previous
        if same_observation and reusable and self.observed.inputs.reusable:
            self.query_facts[key] = row["value"]
        return row["value"]

    def checkpoint(self):
        """A run-local heap copy; public prefixes remain the reproducible external recipe."""
        if Path.cwd() != self.arena:
            raise UnsupportedWorld("checkpoints need an unchanged working directory")
        bundle = (self.objects, self.results, self.defaults)
        graph = _Graph(self.arena)
        graph.pack(bundle)
        for node in graph.nodes:
            if node["type"] in _ACTIVE_CLASSES:
                cls = _load(node["type"])
                if any(any(name in base.__dict__ for name in ("__copy__", "__deepcopy__", "__reduce__", "__reduce_ex__", "__getstate__", "__setstate__")) for base in cls.__mro__ if base is not object and base.__module__ != "builtins"):
                    raise UnsupportedWorld("custom copy or serialization hooks need public-prefix restoration")
        cloned = copy.deepcopy(bundle)
        clone_graph = _Graph(self.arena)
        clone_graph.pack(cloned)
        mutable = {identity for identity, number in graph.seen.items() if graph.nodes[number]["type"] not in {"builtins:tuple", "builtins:frozenset"}}
        if mutable & set(clone_graph.seen):
            raise UnsupportedWorld("a checkpoint copy shares mutable state with its source")
        if snapshot(cloned[0], self.arena, cloned[2]) != self.current or snapshot(self.objects, self.arena, self.defaults) != self.current:
            raise UnsupportedWorld("a checkpoint copy did not preserve the complete observation")
        return {"bundle": cloned, "observation": copy.deepcopy(self.current), "prefix": list(self.prefix),
                "outcomes": list(self.outcomes), "last": {key: value for key, value in self.last.items() if key not in {"before", "after"}} if self.last else None}

    def restore_checkpoint(self, checkpoint):
        self.objects, self.results, self.defaults = copy.deepcopy(checkpoint["bundle"])
        os.chmod(self.arena, 0o700)
        def remove(path):
            if path.is_dir() and not path.is_symlink():
                os.chmod(path, 0o700)
                for child in path.iterdir(): remove(child)
                path.rmdir()
            else:
                path.unlink()
        for path in self.arena.iterdir(): remove(path)
        directories = []
        for name, kind, mode, *payload in checkpoint["observation"]["files"]:
            path = self.arena / name
            if kind == "directory":
                path.mkdir(parents=True, exist_ok=True)
                directories.append((path, mode))
            elif kind == "file":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(payload[0]))
                path.chmod(mode)
            else:
                target = payload[0].replace("<world>", str(self.arena), 1) if payload[0].startswith("<world>") else payload[0]
                path.symlink_to(target)
        for path, mode in reversed(directories): path.chmod(mode)
        self.arena.chmod(checkpoint["observation"]["root_mode"])
        self.prefix, self.outcomes = list(checkpoint["prefix"]), list(checkpoint["outcomes"])
        self.last = checkpoint["last"]
        self._capture_prefix = None
        self.current = snapshot(self.objects, self.arena, self.defaults)
        if self.current != checkpoint["observation"]:
            raise UnsupportedWorld("checkpoint restoration changed the complete observation")
        self.resets += 1
        return self.current

    def receipt(self):
        return {"child_pid": os.getpid(), "executed_calls": self.executed_calls, "resets": self.resets,
                "public_steps": self.public_steps,
                "replayed_steps": self.replayed_steps,
                "hit_functions": sorted(self.observed.hit), "hit_lines": sorted(self.observed.lines),
                "hit_statements": sorted(self.observed.statement_hits)}


def _worker(request_path, response_path):
    global _ACTIVE_ARENA, _ACTIVE_CLASSES, _ACTIVE_SOURCE_ROOT
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    # A same-size timestamp-valid application pyc must never override the identified current source.
    sys.pycache_prefix = str(Path(request_path).parent / "bytecode")
    response = None
    # This directory belongs only to this interpreter; protocol files stay outside it.
    with tempfile.TemporaryDirectory(prefix="flowguard-world-") as directory:
        arena = Path(directory).resolve()
        original_directory = Path.cwd()
        os.chdir(arena)
        _ACTIVE_ARENA = arena
        _ACTIVE_CLASSES = set(request["spec"]["classes"])
        _ACTIVE_SOURCE_ROOT = Path(request["spec"]["root"]).resolve()
        for name in ("home", "temp"):
            (arena / name).mkdir()
        os.environ.update(HOME=str(arena / "home"), TMPDIR=str(arena / "temp"), TEMP=str(arena / "temp"), TMP=str(arena / "temp"))
        tempfile.tempdir = str(arena / "temp")
        random.seed(request.get("start", {}).get("seed", 0))
        inputs = _Inputs(arena, request["spec"]["root"], sys.pycache_prefix)
        observed = _ObservedState(request["spec"], arena, inputs)
        operation = request.get("operation", "trace")
        recording_active = operation == "record"
        inputs.recording_tests = recording_active
        if recording_active:
            # Ordinary tests run as tests; every retained public prefix still needs the guarded native replay.
            def record_inputs(event, args):
                if recording_active and event in {"open", "os.listdir", "os.scandir", "metadata", "import"}:
                    inputs.record(event, args, caller=sys._getframe(1) if event in {"os.listdir", "os.scandir"} else None)
            sys.addaudithook(record_inputs)
            finish_guard = lambda: None
        else:
            finish_guard = _arena_guard(arena, inputs)
        old_trace = sys.gettrace()
        old_profile = sys.getprofile()
        sys.settrace(observed.trace)
        sys.setprofile(observed.profile)
        try:
            monitoring = getattr(sys, "monitoring", None)
            if monitoring is None:
                raise UnsupportedWorld("native statement monitoring requires Python 3.12")
            slot = next((number for number in range(6) if monitoring.get_tool(number) is None), None)
            if slot is None:
                raise UnsupportedWorld("no native statement monitoring slot is available")
            monitoring.use_tool_id(slot, "flowguard-native-statements")
            observed.monitoring_tool = slot
            monitoring.set_events(slot, 0)
            monitoring.register_callback(slot, monitoring.events.LINE, observed.line)
            if operation == "record":
                from .testrec import record
                response = record(request["spec"], arena, observed=observed)
            else:
                response = _run_session(request, arena, observed)
            if operation == "rule-proof":
                execution_footprint = copy.deepcopy(inputs.receipt())
                observed.enabled = False
                from .rules import judge
                response["judgment"] = judge(request["options"]["rule_plan"], response["captures"])
                response["judgment_footprint"] = copy.deepcopy(inputs.receipt())
                response["footprint"] = execution_footprint
            else:
                response["footprint"] = inputs.receipt()
        except BaseException as exc:
            response = {"unsupported": type(exc).__name__ + ": " + _diagnostic(str(exc), arena)}
        try:
            observed.enabled = False
            inputs.recording_tests = False
            recording_active = False
            if observed.monitoring_tool is not None:
                slot = observed.monitoring_tool
                monitoring.set_events(slot, 0)
                for code in observed.monitored_codes:
                    monitoring.set_local_events(slot, code, 0)
                monitoring.register_callback(slot, monitoring.events.LINE, None)
                monitoring.free_tool_id(slot)
                observed.monitoring_tool = None
            sys.settrace(old_trace)
            sys.setprofile(old_profile)
            encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
            os.write(int(response_path), encoded.encode("utf-8"))
        finally:
            finish_guard()
            os.chdir(original_directory)


def _audit_phase(session, phase, options):
    """One complete audit computation, with public reconstruction between children."""
    from .checks import crashes, offered, reach, stuck
    from .explore import explore

    def handoff():
        # The observation alone omits prior results and their aliases. Retain
        # those plus the last native call, without copying user objects.
        # Monitoring hits and synthesized transitions remain provenance in the
        # walk facts, not native state. Statement/diff searches use their own operations.
        last = {key: session.last[key] for key in ("call", "outcome", "exception", "value", "stdout", "stderr",
                "before_key", "after_key") if key in session.last} if session.last else None
        return {"start": dict(session.start), "prefix": list(session.prefix), "outcomes": list(session.outcomes),
                "observation": json.loads(json.dumps(session.current, ensure_ascii=False, allow_nan=False)),
                "results_graph": _Graph(session.arena).pack([session.objects, session.results]), "last": last}

    if phase == "walk":
        bounds = {key: options[key] for key in ("seed", "steps", "node_cap", "alphabet_cap") if key in options}
        public_before = session.public_steps - session.replayed_steps
        response = explore(session, **bounds)
        response["rule_uncaptured_steps"] = max(0, session.public_steps - session.replayed_steps - public_before - len(response["events"]))
        response["handoff"] = handoff()
    else:
        walk = options["walk"]
        expected = walk["handoff"]
        if expected["start"] != session.start:
            raise UnsupportedWorld("audit phase handoff has a different starting recipe")
        session.reset(expected["prefix"])
        restored = handoff()
        if restored != expected:
            changed = sorted(key for key in restored.keys() | expected.keys() if restored.get(key) != expected.get(key))
            raise UnsupportedWorld("audit phase public prefix did not restore its complete handoff: " + ", ".join(changed))
        recorded = options.get("test_replay", {"witnesses": [], "prefixes": []})
        states = () if options.get("shared_test_probes", False) else recorded["prefixes"]
        public_before = session.public_steps - session.replayed_steps
        if phase == "crash":
            response = crashes(session, walk, states=states)
        elif phase == "agreement":
            response = offered(session, walk, states=states)
        elif phase == "reach":
            response = reach(session, walk, known=options.get("known", []),
                             witnessed=recorded["witnesses"], states=recorded["prefixes"])
        elif phase == "stuck":
            response = stuck(session, walk, states=recorded["prefixes"])
        else:
            raise UnsupportedWorld("unknown audit phase: " + str(phase))
        response["rule_uncaptured_steps"] = session.public_steps - session.replayed_steps - public_before
    result = {**response, "phase": phase}
    if session.rule_ledger is not None:
        result["rule_captures"] = session.rule_ledger.dump()
    return result


def _run_session(request, arena, observed):
    """Dispatch operations over the one worker-owned native session."""
    session = _Session(request["spec"], request.get("start", {}), arena, observed)
    session.reset()

    def finish(response):
        if session.rule_ledger is not None:
            response["rule_captures"] = session.rule_ledger.dump()
        return response

    operation = request.get("operation", "trace")
    if operation == "trace":
        initial = session.current
        steps = [session.step(item) for item in request["calls"]]
        return finish({"initial": initial, "steps": steps, "final": session.current, "defaults": session.defaults,
                "seeding": session.seeded, "construction_stdout": session.construction_stdout,
                "construction_stderr": session.construction_stderr})
    from .explore import explore, focused_search, directed_search, evaluate
    options = request.get("options", {})
    session.observe_transitions = options.get("goal", {}).get("kind") == "transition"
    if operation == "rule-proof":
        for recipe in request["calls"]:
            session.step(recipe)
        return finish({"captures": session.rule_ledger.dump(),
                       "outcomes": list(session.outcomes), "execution": session.receipt()})
    if operation in {"explore", "directed", "search", "diff"} and request["calls"]:
        session.reset(request["calls"])
        session.base_prefix = list(request["calls"])
    if operation == "saves":
        persistence = session.spec.get("persistence")
        if not persistence:
            raise UnsupportedWorld("no public save/load root was derived")
        from .explore import plain
        original = dict(session.start)
        prefixes = options.get("prefixes")
        walk = None
        if not options.get("generate", True):
            prefixes = []
        elif prefixes is None or not prefixes:
            walk = explore(session, **{key: options[key] for key in ("seed", "steps", "node_cap", "alphabet_cap") if key in options})
            # Keep concrete categorical and successful-action witnesses, not every walk step.
            prefixes = [[]] + [row["prefix"] for row in walk["witnesses"]
                               if row["semantic"].get("kind") == "query" or
                               row["semantic"].get("kind") == "action" and row["semantic"].get("outcome") == "success"]
        saves, unknown, seen = [], [], set()

        open_shape = [False]

        def structure(value, identifiers):
            if isinstance(value, dict):
                open_shape[0] |= not value
                fixed, dynamic = {}, []
                for key, item in value.items():
                    if key in identifiers:
                        dynamic.append(structure(item, identifiers))
                    else:
                        fixed[key] = structure(item, identifiers)
                if dynamic:
                    fixed["<entity-id>"] = sorted({json.dumps(item, sort_keys=True) for item in dynamic})
                return {"object": fixed}
            if isinstance(value, list):
                open_shape[0] |= not value
                return {"array": sorted({json.dumps(structure(item, identifiers), sort_keys=True) for item in value})}
            return type(value).__name__

        for prefix in prefixes:
            session.reset(prefix, start=original)
            before = state_key(session.current)
            if before in seen:
                continue
            seen.add(before)
            identifiers = {str(value) for entity in session.spec["entities"].values()
                           for value in plain(session.query("system", entity["list"]))}
            name = "saved.json"
            save_call = {"name": persistence["save"], "args": [{"$file": name}]}
            row = session.step(save_call)
            if row["outcome"] != "success":
                unknown.append({"reason": "old public save " + row["outcome"], "exception": row["exception"], "prefix": prefix})
                continue
            path = session.arena / name
            if not path.is_file() or path.is_symlink():
                unknown.append({"reason": "public save did not produce an ordinary file", "prefix": prefix})
                continue
            data = path.read_bytes()
            open_shape[0] = False
            try:
                observed_schema = structure(json.loads(data), identifiers)
                schema = None if open_shape[0] else observed_schema
            except (ValueError, UnicodeError):
                observed_schema = None
                schema = None  # An opaque format retains its source rather than a guessed schema.
            file = {"name": name, "bytes": base64.b64encode(data).decode("ascii"), "sha256": hashlib.sha256(data).hexdigest()}
            session.reset(start={"files": {name: file["bytes"]}})
            loaded = session.step({"name": persistence["load"], "args": [{"$file": name}], "replace": True})
            saves.append({"recipe": {"start": original, "prefix": prefix, "save": save_call}, "file": file,
                          "schema": schema, "observed_schema": observed_schema,
                          "old_load": {key: loaded[key] for key in ("outcome", "exception", "stdout", "stderr")}})
        for file in options.get("committed", []):
            data = base64.b64decode(file["bytes"])
            session.reset(start={"files": {file["name"]: file["bytes"]}})
            loaded = session.step({"name": persistence["load"], "args": [{"$file": file["name"]}], "replace": True})
            saves.append({"recipe": None, "file": {**file, "sha256": hashlib.sha256(data).hexdigest()}, "schema": None,
                          "old_load": {key: loaded[key] for key in ("outcome", "exception", "stdout", "stderr")}})
        response = {"saves": saves, "unknown": unknown, "extent": walk["extent"] if walk else None}
    elif operation == "saved":
        from .checks import saved_files
        response = saved_files(session, **options)
    elif operation == "loading-proof":
        rows = [session.step(item) for item in request["calls"]]
        response = {"matched": bool(rows) and rows[-1]["outcome"] == options["outcome"],
                    "loading": {key: rows[-1][key] for key in ("outcome", "exception", "stdout", "stderr")} if rows else None}
    elif operation == "explore":
        response = explore(session, **options)
    elif operation == "diff":
        from .checks import offered, stuck
        options = dict(options)
        checks = options.pop("checks", True)
        response = explore(session, **options)
        if checks:
            response["stuck"] = stuck(session, response)
            response["agreement"] = offered(session, response)
    elif operation == "search":
        response = focused_search(session, **options)
    elif operation == "directed":
        response = directed_search(session, **options)
    elif operation == "agreement":
        from .checks import offered
        response = offered(session, **options)
    elif operation == "agreement-proof":
        from .checks import offered
        session.reset(request["calls"])
        response = offered(session, {}, case=options["comparison"])
    elif operation == "crashes":
        from .checks import crashes
        response = crashes(session, **options)
    elif operation == "crash-proof":
        from .checks import crashes
        session.reset(request["calls"])
        response = crashes(session, {}, case=options["case"], generate=False)
    elif operation in {"settings", "settings-proof"}:
        from .checks import setting_effects
        response = setting_effects(session, **options)
    elif operation == "witnesses":
        from .testrec import replay_prefixes
        response = replay_prefixes(session, options["recordings"])
        if options.get("probe_tests"):
            from .checks import crashes, offered
            response["agreement"] = offered(session, {}, states=response["prefixes"])
            response["crashes"] = crashes(session, {}, states=response["prefixes"], generate=False)
    elif operation == "test-start":
        from .checks import crashes, offered, stuck
        options = dict(options)
        initial_states = options.pop("initial_states")
        response = explore(session, initial_states=initial_states, **options)
        response["agreement"] = offered(session, response)
        response["crashes"] = crashes(session, response, generate=False)
        response["stuck"] = stuck(session, response, states=initial_states)
        response["reach"] = {"candidates": [], "unknown": [], "scope": "global reach is judged by the shipped audit runs"}
        for check in ("agreement", "crashes", "stuck"):
            for candidate in response[check]["candidates"]:
                actual = [row for row in response["states"] if row["prefix"] == candidate["prefix"]]
                if not actual:
                    actual = [row for row in initial_states if candidate["prefix"][:len(row["prefix"])] == row["prefix"]]
                if actual:
                    source = max(actual, key=lambda row: len(row["prefix"]))
                    candidate["origin"] = "test-start: " + source["test"]
    elif operation == "audit-phase":
        response = _audit_phase(session, options["phase"], options)
    elif operation == "audit":
        from .testrec import replay_prefixes
        options = dict(options)
        recorded = options.get("test_replay")
        if recorded is None:
            recorded = replay_prefixes(session, options.pop("recordings", []))
        options["test_replay"] = recorded
        walk = _audit_phase(session, "walk", options)
        response = {key: value for key, value in walk.items() if key not in {"phase", "handoff"}}
        for phase, field in (("crash", "crashes"), ("agreement", "agreement"), ("reach", "reach"), ("stuck", "stuck")):
            response[field] = {key: value for key, value in _audit_phase(session, phase, {**options, "walk": walk}).items()
                               if key != "phase"}
        response["test_replay"] = {key: value for key, value in recorded.items() if key not in {"prefixes", "witnesses", "replays", "footprint", "execution"}}
    elif operation == "prove":
        divergence = None
        for index, item in enumerate(request["calls"]):
            row = session.step(item)
            expected = options.get("outcomes")
            if expected is not None and (index >= len(expected) or row["outcome"] != expected[index]):
                divergence = index
                break
        response = {"matched": divergence is None and evaluate(session, options["goal"]),
                    "divergence": divergence, "state_key": state_key(session.current),
                    "last": {key: session.last[key] for key in ("call", "outcome", "hit_statements", "before_observations", "after_observations", "transitions") if session.last and key in session.last}}
    else:
        raise UnsupportedWorld("unknown native operation")
    response["execution"] = session.receipt()
    return finish(response)


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
