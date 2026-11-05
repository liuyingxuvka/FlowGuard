"""Native calls and complete supported observations in disposable worlds."""

from __future__ import annotations

import base64
import copy
import dis
import datetime
import math
import marshal
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
from importlib.util import resolve_name
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

from flowguard.map.common import _child_package_import_root, child_import_path
from flowguard.map.runner import run_isolated_process
from .inputs import OWNED_ENVIRONMENT, directory_stamp, environment_stamp, file_stamp, module_lookup_stamp

_ACTIVE_ARENA = None
_ACTIVE_CLASSES = set()
_ACTIVE_SOURCE_ROOT = None


def state_key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()



class _Inputs:
    def __init__(self, arena, source_root, empty_bytecode):
        self.arena = Path(arena)
        self.source_root = str(Path(source_root).resolve()) + os.sep
        self.empty_bytecode = Path(empty_bytecode)
        self.files, self.directories = {}, {}
        self.source_data_reads = {}
        self.directory_uses = {}
        self.world_reads = []
        self.busy = False
        self.reusable = True
        self.recording_tests = False
        self.untracked = set()
        self.phase = "execution"
        self.environment, self.environment_events = {}, []
        self.environment_reads = {}
        self.environment_shadow = {}
        self.environment_initial = {}
        self.environment_enumerated = False
        self.failure = None
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

    def environment_context(self, caller, *, dependency=False):
        while caller is not None:
            filename = caller.f_code.co_filename
            module = caller.f_globals.get("__name__", "")
            importing = (self.phase == "import" and caller.f_code.co_name == "<module>"
                         and getattr(caller.f_globals.get("__spec__"), "_initializing", False))
            subject = filename.startswith(self.source_root)
            if dependency and subject:
                return None  # A dependency import does not authorize callbacks into the subject.
            if importing and (not dependency or not subject and not module.startswith("flowguard.")):
                return {"module": module, "path": filename, "function": caller.f_code.co_qualname, "line": caller.f_lineno}
            if not dependency and self.phase == "execution" and subject:
                return {"module": module, "path": filename, "function": caller.f_code.co_qualname, "line": caller.f_lineno}
            caller = caller.f_back
        return None

    def environment_input(self, key, context):
        key = os.fsdecode(key)
        if os.name == "nt":
            key = key.upper()
        if key not in self.environment:
            self.environment[key] = {"owned": OWNED_ENVIRONMENT[key]} if key in OWNED_ENVIRONMENT else environment_stamp(key)
        self.environment_reads.setdefault(key, context)
        self.record("metadata", (context["path"],))
        return key

    def environment_access(self, frame, *, enumerate=False):
        context = self.environment_context(frame.f_back)
        if context is None:
            return
        if enumerate:
            self.environment_enumerated = True
            self.reusable = False
            self.untracked.add("environment enumeration needs an explicit input scope")
        elif not self.environment_enumerated and isinstance(frame.f_locals["key"], (str, bytes)):
            self.environment_input(frame.f_locals["key"], context)

    def environment_mutation(self, event, args, caller):
        context = self.environment_context(caller, dependency=True)
        if context is None:
            origin = self.environment_context(caller)
            source = "; source=" + origin["path"] + "#" + origin["function"] + ":" + str(origin["line"]) if origin else ""
            self.failure = UnsupportedWorld(event + " needs an explicit environment world; phase=" + self.phase + source)
            raise self.failure
        key = self.environment_input(args[0], context)
        before = self.environment_shadow.get(key, environment_stamp(key))
        self.environment_initial.setdefault(key, before)
        value = {"missing": True} if event == "os.unsetenv" else {"sha256": hashlib.sha256(os.fsdecode(args[1]).encode("utf-8", "surrogatepass")).hexdigest()}
        self.environment_shadow[key] = value
        def published(stamp):
            return self.environment[key] if self.environment[key].get("owned") and stamp == self.environment_initial[key] else stamp
        self.environment_events.append({"phase": self.phase, "event": event, "key": key, **context,
                                        "before": published(before), "after": published(value), "status": "audit-attempt"})

    @contextmanager
    def importing(self):
        previous, self.phase = self.phase, "import"
        first = len(self.environment_events)
        try:
            yield
            for event in self.environment_events[first:]:
                key = event["key"]
                inherited = self.environment_initial[key]
                if self.environment_shadow[key] != inherited or environment_stamp(key) != inherited:
                    self.failure = UnsupportedWorld(event["event"] + " environment key was not restored; phase=import; module=" + event["module"])
                    raise self.failure
                event["import_completed"] = True
        finally:
            self.phase = previous

    def record(self, event, args, *, caller=None):
        if self.busy or event not in {"open", "os.listdir", "os.scandir", "metadata", "import", "sqlite3.connect"}:
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
            elif event == "sqlite3.connect" and args[0] != ':memory:':
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
                    if event in {'open','sqlite3.connect'}:
                        frame = caller
                        while frame is not None and not frame.f_code.co_filename.startswith(self.source_root):
                            frame = frame.f_back
                        if frame is not None:
                            self.world_reads.append({'path':path.relative_to(self.arena).as_posix(),'event':event,
                                'source':{'path':frame.f_code.co_filename[len(self.source_root):].replace(os.sep,'/'),
                                          'function':frame.f_code.co_qualname,'line':frame.f_lineno}})
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
                if rows is self.files and caller is not None:
                    context = self.environment_context(caller)
                    if context is not None:
                        self.source_data_reads.setdefault(key, context)
                if key not in rows:
                    rows[key] = stamp(path)
                if rows is self.directories:
                    self._directory_use(path, event, args, caller)
        except (OSError, TypeError, ValueError):
            self.reusable = False
            self.untracked.add("unidentified filesystem input: " + event)
        finally:
            self.busy = False

    def _directory_use(self, path, event, args, caller):
        """Keep physical listings; narrow only a real module finder lookup."""
        key = str(path)
        previous = self.directory_uses.get(key)
        if previous and previous["kind"] == "listing":
            return
        name = None
        if event == "import" and isinstance(args[0], str):
            name = args[0].split(".", 1)[0]
        elif caller is not None:
            finder_type = importlib.machinery.FileFinder
            if caller.f_code is finder_type._fill_cache.__code__:
                finder = caller.f_locals.get("self")
                frame = caller.f_back
                while frame is not None and frame.f_code.co_filename.startswith("<frozen importlib"):
                    if frame.f_code is finder_type.find_spec.__code__ and frame.f_locals.get("self") is finder:
                        fullname = frame.f_locals.get("fullname")
                        if isinstance(fullname, str) and Path(finder.path).absolute() == path:
                            name = fullname.rsplit(".", 1)[-1]
                        break
                    frame = frame.f_back
        if name:
            usage = self.directory_uses.setdefault(key, {"kind": "module-lookup", "lookups": {}})
            usage["lookups"].setdefault(name, module_lookup_stamp(path, name))
        else:
            self.directory_uses[key] = {"kind": "listing", "event": event,
                "caller": [caller.f_code.co_filename, caller.f_code.co_qualname] if caller is not None else None}

    def receipt(self):
        return {"files": self.files, "source_data_reads": self.source_data_reads,
                "directories": self.directories, "reusable": self.reusable,
                "directory_uses": self.directory_uses, "untracked": sorted(self.untracked),
                "environment": self.environment, "environment_reads": self.environment_reads,
                "environment_events": self.environment_events, "world_reads":self.world_reads}


class _ObservedState:
    """Bounded observation of package data referenced by executed function frames."""
    def __init__(self, spec, arena, inputs=None):
        self.root = str(Path(spec["root"]).resolve()) + os.sep
        self.arena = arena
        self.enabled = False
        self.pending = {}
        self.local_cells = {}
        self.global_dependencies = {}
        self.import_dependencies = {}
        self.hit = set()
        self.recorded_hits = set()
        self.recorded_gaps = set()
        self.lines = set()
        self.statement_hits = set()
        self.call_hits = set()
        self.statement_ids = {(row["path"], row["function"], row["line"]): row["id"]
                              for row in spec.get("statements", []) if row["unambiguous"]}
        self.truth_names = {}
        self.return_fields, self.frame_return_fields = {}, {}
        for row in spec.get("statements", []):
            names = row.get("truth_names", ())
            if not isinstance(names, (list, tuple)) or any(not isinstance(name, str) or not name.isidentifier() for name in names):
                raise UnsupportedWorld("selected truth facts need explicit Python names")
            if row["unambiguous"] and names:
                self.truth_names[(row["path"], row["function"], row["line"])] = tuple(dict.fromkeys(names))
            selected = row.get("return_fields", ())
            if not isinstance(selected, (list, tuple)) or any(type(name) is not str or not name.isidentifier() for name in selected):
                raise UnsupportedWorld("selected return fields need explicit dictionary field names")
            if row["unambiguous"] and selected:
                key = row["path"], row["function"], row["line"]
                self.return_fields.setdefault(key, set()).update(selected)
        self.failure = None
        self.events = []
        self.call_events = []
        self.frames = {}
        self.call_parents = {}
        self.next_frame = 0
        self.busy = False
        self.inputs = inputs

    def line(self, code, line, *, call_token=None, frame=None):
        if not self.enabled or not code.co_filename.startswith(self.root) or code.co_name == "<module>":
            return
        path = code.co_filename[len(self.root):].replace(os.sep, "/")
        self.lines.add((path, line))
        identifier = self.statement_ids.get((path, code.co_qualname, line))
        if identifier is not None:
            self.statement_hits.add(identifier)
            self.call_hits.add(identifier)
        self.event(code, line, "statement", statement=identifier, call_token=call_token, **(self.name_truth(frame) if frame is not None else {}))

    def name_truth(self, frame):
        """Before-statement facts for selected names; never invoke custom truth semantics."""
        if not self.truth_names:
            return {}
        names = self.truth_names.get((frame.f_code.co_filename[len(self.root):].replace(os.sep, "/"),
                                      frame.f_code.co_qualname, frame.f_lineno), ())
        if not names:
            return {}
        facts = {}
        locals_ = frame.f_locals
        local_names = (*frame.f_code.co_varnames, *frame.f_code.co_cellvars, *frame.f_code.co_freevars)
        supported = (type(None), bool, int, float, complex, str, bytes, list, tuple, dict, set)
        for name in names:
            if name in locals_:
                value = locals_[name]
            elif name not in local_names and name in frame.f_globals:
                value = frame.f_globals[name]
            elif name not in local_names and name in frame.f_builtins:
                value = frame.f_builtins[name]
            else:
                facts[name] = {"status": "unknown", "reason": "name is unbound at this statement"}
                continue
            kind = type(value)
            facts[name] = ({"status": "current", "type": kind.__module__ + ":" + kind.__qualname__, "truth": bool(value)}
                           if any(kind is allowed for allowed in supported) else {"status": "unknown", "reason": "custom truth semantics are not observed"})
        return {"name_truth": facts}

    def event(self, code, line, kind, **detail):
        path = code.co_filename[len(self.root):].replace(os.sep, "/")
        row = {"kind": kind, "path": path, "function": code.co_qualname, "line": line,
               "statement": self.statement_ids.get((path, code.co_qualname, line)),
               "parent_call_token": self.call_parents.get(detail.get("call_token")), **detail}
        if self.inputs is not None and self.inputs.recording_tests:
            self.events.append(row)
        self.call_events.append(row)

    def return_scalar(self, value):
        if value is None or any(type(value) is kind for kind in (bool, int, str)) or type(value) is float and math.isfinite(value):
            if type(value) is str:
                prefix = str(self.arena)
                if value == prefix or value.startswith(prefix + os.sep):
                    value = "<world>" + value[len(prefix):]
            return {"status": "current", "value": value}
        return {"status": "unknown", "reason": "return value is not a finite JSON scalar"}

    def returned(self, frame, value):
        opcode = dis.opname[frame.f_code.co_code[frame.f_lasti]] if frame.f_lasti >= 0 else "unknown"
        completed = opcode in {"RETURN_VALUE", "RETURN_CONST"}
        status = "returned" if completed else "unknown" if opcode in {"YIELD_VALUE", "RETURN_GENERATOR", "unknown"} else "raised"
        result = {"return_status": status, "result": self.return_scalar(value) if completed else
                  {"status": "unknown", "reason": "no completed return value"}}
        if completed:
            kinds = ((type(None),'none'),(bool,'bool'),(int,'int'),(float,'float'),(complex,'complex'),
                     (str,'str'),(bytes,'bytes'),(list,'list'),(tuple,'tuple'),(dict,'dict'),(set,'set'),(frozenset,'frozenset'))
            result['return_kind'] = next((name for kind,name in kinds if type(value) is kind),'other')
        selected = self.frame_return_fields.pop(id(frame), ())
        if selected:
            # Iteration over exact builtin keys avoids invoking a custom key's
            # equality/hash during lookup; unselected values never leave this frame.
            items = {key: item for key, item in dict.items(value) if type(key) is str and key in selected} if completed and type(value) is dict else {}
            result["return_fields"] = {name: self.return_scalar(items[name]) if name in items else
                {"status": "unknown", "reason": "selected dictionary field is unavailable"} for name in sorted(selected)}
        return result

    def _observe(self, callback, *args):
        try:
            return callback(*args)
        except BaseException as exc:
            self.failure = exc if isinstance(exc, (UnsupportedWorld, NativeEngineError)) else NativeEngineError(str(exc), phase="observer")
            raise self.failure from exc

    def namespace(self, value, depth=0, requested=()):
        """Observe executed class cells, without treating unused class tooling as instance data."""
        definitions = (types.FunctionType, types.BuiltinFunctionType, staticmethod, classmethod, property,
                       types.MethodDescriptorType, types.GetSetDescriptorType, types.MemberDescriptorType, types.WrapperDescriptorType)
        omitted = {"__module__", "__doc__", "__qualname__", "__annotations__", "__dataclass_fields__",
                   "__dataclass_params__", "__match_args__", "__dict__", "__weakref__", "__builtins__",
                   "__loader__", "__spec__", "__package__", "__cached__"}
        result, identities = {}, []
        for name, item in vars(value).items():
            if issubclass(type(value), type) and name not in requested:
                continue
            if name in omitted and name not in requested:
                continue
            if issubclass(type(item), definitions):
                identities.append((name, id(item)))
                continue
            if issubclass(type(item), type):
                if item.__module__ + ":" + item.__qualname__ not in _ACTIVE_CLASSES:
                    continue
                if depth >= 2:
                    raise UnsupportedWorld("deep package namespace data needs an explicit world")
                result[name], nested = self.namespace(item, depth + 1, requested)
                identities.extend(nested)
            elif issubclass(type(item), types.ModuleType):
                continue
            else:
                result[name] = item
            identities.append((name, id(item)))  # Temporary binding identity, never persisted as state.
        return result, identities

    @staticmethod
    def _import_module(value):
        if type(value) is not types.ModuleType:
            return False
        attributes = vars(value)
        return (type(attributes.get('__name__')) is str
                and ('__file__' in attributes and (attributes['__file__'] is None or type(attributes['__file__']) is str)
                     or '__file__' not in attributes and '__getattr__' not in attributes))

    @classmethod
    def _import_class(cls, value, requested=(), seen=frozenset()):
        if not issubclass(type(value), type) or id(value) in seen or len(seen) > 2:
            return False  # Existing namespace depth/cycle limits, without evaluating metadata.
        descriptors = vars(type)
        for base in descriptors['__mro__'].__get__(type(value)):
            if base is type:
                break
            attributes = descriptors['__dict__'].__get__(base)
            if ('__getattribute__' in attributes and attributes['__getattribute__'] is not type.__getattribute__
                    or any(name in attributes for name in ('__dict__', '__mro__', '__class__'))
                    or any(name in attributes and type(attributes[name]) is not str
                           for name in ('__module__', '__qualname__'))):
                return False
        try:
            if any(type(descriptors[name].__get__(value)) is not str for name in ('__module__', '__qualname__')):
                return False
        except AttributeError:
            return False
        return all(not issubclass(type(item), type) or cls._import_class(item, requested, seen | {id(value)})
                   for name, item in descriptors['__dict__'].__get__(value).items() if name in requested)

    def capture(self, frame):
        values, identities = {}, []
        names = set(frame.f_code.co_names) | set(frame.f_code.co_freevars)
        accesses = self.global_dependencies.get(frame.f_code)
        if accesses is None:
            # co_names also holds attribute names. Keep those for namespace
            # inspection below, without treating self.x as a read of global x.
            # Writes remain dependencies so ambient mutation still stays unknown.
            instructions = tuple(dis.get_instructions(frame.f_code))
            accesses = frozenset(instruction.argval for instruction in instructions
                                 if instruction.opname in {'LOAD_GLOBAL', 'LOAD_NAME', 'LOAD_FROM_DICT_OR_GLOBALS',
                                                           'STORE_GLOBAL', 'DELETE_GLOBAL'})
            self.global_dependencies[frame.f_code] = accesses
            imports, imported = [], None
            for index, instruction in enumerate(instructions):
                if instruction.opname == 'IMPORT_NAME':
                    imported = instruction.argval, instructions[index - 2].argval
                    imports.append((*imported, None))
                elif instruction.opname == 'IMPORT_FROM' and imported is not None:
                    imports.append((*imported, instruction.argval))
            self.import_dependencies[frame.f_code] = tuple(imports)
        inferred = {}
        for locator in _ACTIVE_CLASSES:
            module, _, qualname = locator.partition(":")
            value = sys.modules.get(module)
            if qualname in names and value is not None and hasattr(value, qualname):
                inferred.setdefault(qualname, getattr(value, qualname))
        candidates = []
        # A local import binds an existing dependency; it does not itself mutate
        # that module. Observe known imports at entry as well as at return, using
        # import bytecode rather than guessing modules from attribute names.
        for module_name, level, member in self.import_dependencies[frame.f_code]:
            if type(level) is not int:
                continue
            if level:
                try:
                    module_name = resolve_name('.' * level + module_name, frame.f_globals.get('__package__'))
                except (ImportError, ValueError):
                    continue  # The actual import retains its own failure outcome.
            module = sys.modules.get(module_name)
            if not self._import_module(module):
                continue
            if member is None:
                candidates.append(('import:' + module_name, module))
                parent = sys.modules.get(module_name.partition('.')[0])
                if self._import_module(parent):
                    candidates.append(('import-parent:' + module_name, parent))
            else:
                value = vars(module).get(member)  # Never invoke a lazy module attribute.
                if self._import_module(value) or self._import_class(value, names):
                    candidates.append(('import:' + module_name + ':' + member, value))
        # Defaults and attributes of the executing function can carry state outside its instances.
        candidates.extend(("function:" + name, value) for name, value in frame.f_globals.items()
                          if issubclass(type(value), types.FunctionType) and value.__code__ is frame.f_code)
        owner = frame.f_locals.get("self", frame.f_locals.get("cls"))
        if owner is not None:
            cls = owner if issubclass(type(owner), type) else type(owner)
            for base in cls.__mro__:
                value = base.__dict__.get(frame.f_code.co_name)
                value = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
                if isinstance(value, types.FunctionType) and value.__code__ is frame.f_code:
                    candidates.append(("executing-method", value))
        for name in sorted(accesses | set(frame.f_code.co_freevars)):
            if name in frame.f_code.co_freevars:
                value = frame.f_locals.get(name)
                if self.local_cell(frame, name, value):
                    continue
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
        candidates.extend(("local:" + name, value) for name, value in frame.f_locals.items() if issubclass(type(value), (type, types.ModuleType)))
        if "__dict__" in names and any(issubclass(type(value), type) and value.__module__ + ":" + value.__qualname__ in _ACTIVE_CLASSES for _, value in candidates):
            raise UnsupportedWorld("dynamic class namespace access needs an explicit world")
        namespaces = {}
        for name, value in candidates:
            if issubclass(type(value), types.ModuleType):
                filename = getattr(value, "__file__", "") or ""
                label = "module:" + value.__name__
                if not filename.startswith(self.root):
                    selected = {key: item for key, item in vars(value).items() if key in names and not issubclass(type(item), (types.ModuleType, type, types.FunctionType, types.BuiltinFunctionType))}
                    namespaces[label] = (selected, [(key, id(item)) for key, item in vars(value).items() if key in names])
                    continue
                namespaces[label] = self.namespace(value, requested=names)
            elif issubclass(type(value), type):
                if value.__module__ + ":" + value.__qualname__ not in _ACTIVE_CLASSES:
                    continue
                label = "class:" + value.__module__ + ":" + value.__qualname__
                namespaces[label] = self.namespace(value, requested=names)
            elif issubclass(type(value), (types.FunctionType, types.BuiltinFunctionType)):
                if isinstance(value, types.FunctionType) and value.__code__.co_filename.startswith(self.root):
                    values["function:" + name] = {"attributes": vars(value), "defaults": value.__defaults__, "kwdefaults": value.__kwdefaults__}
                continue
            else:
                values[name] = value
        for label, (data, references) in namespaces.items():
            values[label] = data
            identities.extend((label, *row) for row in references)
        graph = _Graph(self.arena)
        packed = graph.pack(dict(sorted(values.items())))
        # References nested in a used dispatch table can be replaced by an
        # equal-code function. Identity belongs only to this run-local guard.
        identities.extend(("function-reference", number, identity)
                          for identity, number in graph.seen.items()
                          if graph.nodes[number]["type"] == "builtins:function")
        return packed, sorted(set(identities), key=str)

    def local_cell(self, frame, name, value):
        """A cell first bound by a still-live lexical invocation is temporary local state."""
        owner = frame.f_back
        while owner is not None:
            if (owner.f_globals is frame.f_globals
                    and frame.f_code.co_qualname.startswith(owner.f_code.co_qualname + ".<locals>.")
                    and name in owner.f_code.co_cellvars):
                return (name in self.local_cells.get(id(owner), ())
                        and owner.f_locals.get(name) is value)
            owner = owner.f_back
        return False

    def profile(self, frame, event, arg):
        return self._observe(self._profile, frame, event, arg)

    def _profile(self, frame, event, arg):
        # Observe calls that cross the source boundary, rather than names in unexecuted paths.
        recording = self.inputs is not None and self.inputs.recording_tests
        if self.inputs is not None and event == "call":
            if frame.f_code is type(os.environ).__getitem__.__code__:
                self.inputs.environment_access(frame)
            elif frame.f_code is type(os.environ).__iter__.__code__:
                self.inputs.environment_access(frame, enumerate=True)
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
        if event == "c_call" and module == "builtins" and name in {"getattr", "setattr", "delattr", "vars"}:
            values = [caller.f_globals[key] for key in caller.f_code.co_names if key in caller.f_globals]
            values.extend(caller.f_locals.values())
            classes = [value for value in values if isinstance(value, type)]
            if "type" in caller.f_code.co_names or "__class__" in caller.f_code.co_names:
                classes.extend(type(value) for value in values)
            if any(value.__module__ + ":" + value.__qualname__ in _ACTIVE_CLASSES for value in classes):
                raise UnsupportedWorld("dynamic class namespace access needs an explicit world")
        if module.split(".")[0] in {"random", "time", "datetime", "secrets", "threading", "_thread"}:
            owner = getattr(arg, "__self__", None) if event == "c_call" else None
            date_values = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)
            if (module == "datetime" and name in {"fromisoformat", "isoformat", "utcoffset", "total_seconds"}
                    and (owner in date_values if isinstance(owner, type) else type(owner) in date_values)):
                return  # Explicit value parsing/formatting and fixed offset arithmetic read no clock.
            if recording:
                self.inputs.reusable = False
                self.inputs.untracked.add("recording called nondeterministic resource: " + module + "." + name)
            else:
                raise UnsupportedWorld("called nondeterministic resource needs an explicit world")

    def trace(self, frame, event, arg):
        return self._observe(self._trace, frame, event, arg)

    def _trace(self, frame, event, arg):
        tracked = frame.f_code.co_filename.startswith(self.root) and frame.f_code.co_name != "<module>"
        recording = self.inputs is not None and self.inputs.recording_tests
        if tracked and event == "line" and (self.enabled or recording) and not self.busy:
            key = frame.f_code.co_filename[len(self.root):].replace(os.sep, "/"), frame.f_code.co_qualname, frame.f_lineno
            selected = self.return_fields.get(key)
            if selected:
                self.frame_return_fields.setdefault(id(frame), set()).update(selected)
        if tracked and event == "call":
            self.next_frame += 1
            self.frames[id(frame)] = self.next_frame
            ancestor = frame.f_back
            while ancestor is not None and id(ancestor) not in self.frames:
                ancestor = ancestor.f_back
            self.call_parents[self.next_frame] = self.frames.get(id(ancestor)) if ancestor is not None else None
        call_token = self.frames.get(id(frame))
        if not self.enabled and recording and not self.busy and frame.f_code.co_filename.startswith(self.root) and frame.f_code.co_name != "<module>":
            ancestor = frame.f_back
            while ancestor is not None:
                if ancestor.f_code is snapshot.__code__:
                    return None
                ancestor = ancestor.f_back
            if event == "call" and not frame.f_code.co_name.startswith("<"):
                self.recorded_hits.add(frame.f_code.co_filename[len(self.root):].replace(os.sep, "/")
                                       + "#" + frame.f_code.co_qualname.replace(".<locals>.", "."))
            if event in {"line", "return", "exception"}:
                detail = {"exception": {"type": type(arg[1]).__module__ + ":" + type(arg[1]).__qualname__,
                                         "message": _diagnostic(str(arg[1]), self.arena)}} if event == "exception" else {}
                if event == "return":
                    detail.update(self.returned(frame, arg))
                elif event == "line":
                    detail.update(self.name_truth(frame))
                self.event(frame.f_code, frame.f_lineno, "statement" if event == "line" else event, call_token=call_token, **detail)
            if event == "return":
                self.frames.pop(id(frame), None)
                self.call_parents.pop(call_token, None)
            return self.trace
        if not self.enabled or self.busy or not frame.f_code.co_filename.startswith(self.root) or frame.f_code.co_name == "<module>":
            return None
        self.busy = True
        try:
            key = id(frame)
            if event == "call":
                if not frame.f_code.co_name.startswith("<"):
                    self.hit.add(frame.f_code.co_filename[len(self.root):].replace(os.sep, "/") + "#" + frame.f_code.co_qualname.replace(".<locals>.", "."))
                self.local_cells[key] = set(frame.f_code.co_cellvars) - set(frame.f_locals)
                self.pending[key] = self.capture(frame)
            elif event == "line":
                self.line(frame.f_code, frame.f_lineno, call_token=call_token, frame=frame)
            elif event in {"return", "exception"} and key in self.pending:
                detail = {"exception": {"type": type(arg[1]).__module__ + ":" + type(arg[1]).__qualname__,
                                         "message": _diagnostic(str(arg[1]), self.arena)}} if event == "exception" else {}
                if event == "return":
                    detail.update(self.returned(frame, arg))
                self.event(frame.f_code, frame.f_lineno, event, call_token=call_token, **detail)
                previous = self.pending[key]
                if self.capture(frame) != previous:
                    raise UnsupportedWorld("executed package class/global/closure data changed outside the instance graph")
                if event == "return":
                    self.pending.pop(key, None)
                    self.local_cells.pop(key, None)
                    self.frames.pop(key, None)
                    self.call_parents.pop(call_token, None)
        finally:
            self.busy = False
        return self.trace


class UnsupportedWorld(ValueError):
    """Evidence cannot faithfully cover this world; it cannot establish a clean result."""
    def __init__(self, message, *, evidence_status="unknown", outcome=None, exception=None):
        super().__init__(message)
        self.evidence_status = evidence_status
        self.outcome = outcome
        self.exception = exception


class NativeEngineError(RuntimeError):
    """Capture, observation, judgment and worker defects must reach the caller."""
    evidence_status = "engine-error"

    def __init__(self, message, *, phase="execution"):
        super().__init__(message)
        self.phase = phase


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
        if type(value) is types.FunctionType:
            self.function(value, node)
        elif type(value) is re.Pattern:
            node.update(pattern=self.value(value.pattern), flags=value.flags)
        elif type(value) in (list, tuple):
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

    def function(self, value, node):
        """A public source function reference, including its actual mutable data."""
        module_name, qualname, code = value.__module__, value.__qualname__, value.__code__
        problem = "opaque state: builtins:function; a source-bound function without captured business state is required"
        if (type(module_name) is not str or type(qualname) is not str or "<" in qualname
                or _ACTIVE_SOURCE_ROOT is None):
            raise UnsupportedWorld(problem)
        try:
            source = Path(code.co_filename).resolve().relative_to(_ACTIVE_SOURCE_ROOT)
        except ValueError:
            raise UnsupportedWorld(problem) from None
        if not (_ACTIVE_SOURCE_ROOT / source).is_file():
            raise UnsupportedWorld(problem)
        module = sys.modules.get(module_name)
        if type(module) is not types.ModuleType or value.__globals__ is not vars(module):
            raise UnsupportedWorld(problem)
        owner, declared_class = module, None
        for part in qualname.split("."):
            declared_class = owner
            if type(owner) is types.ModuleType:
                namespace = vars(owner)
            elif issubclass(type(owner), type):
                namespace = vars(type)["__dict__"].__get__(owner)
            else:
                raise UnsupportedWorld(problem)
            owner = next((item for name, item in namespace.items() if type(name) is str and name == part), None)
        if type(owner) in (staticmethod, classmethod):
            owner = owner.__func__
        if owner is not value:
            raise UnsupportedWorld(problem)
        closure = value.__closure__
        if closure is not None or code.co_freevars:
            # zero-argument super binds its lexical declaration class, not an
            # arbitrary captured business value. The existing class observer
            # still owns any actual reads/writes of that declared class.
            class_locator = module_name + ":" + qualname.rpartition(".")[0]
            if (code.co_freevars != ("__class__",) or closure is None or len(closure) != 1
                    or not issubclass(type(declared_class), type) or class_locator not in _ACTIVE_CLASSES):
                raise UnsupportedWorld(problem)
            try:
                declared = closure[0].cell_contents
            except ValueError:
                raise UnsupportedWorld(problem) from None
            if declared is not declared_class:
                raise UnsupportedWorld(problem)
            node["class_cell"] = class_locator
        node.update(module=module_name, qualname=qualname, source=source.as_posix(),
                    code_sha256=hashlib.sha256(marshal.dumps(code)).hexdigest(),
                    name=self.value(value.__name__), doc=self.value(value.__doc__),
                    defaults=self.value(value.__defaults__), kwdefaults=self.value(value.__kwdefaults__),
                    attributes=self.value(vars(value)), annotations=self.value(value.__annotations__),
                    type_params=self.value(getattr(value, "__type_params__", ())))

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
    try:
        objects = {"system": cls(**kwargs)}
    except (UnsupportedWorld, NativeEngineError):
        raise
    except BaseException as exc:
        refusals = tuple(_load(name) for name in spec.get("refusal", ()))
        raise UnsupportedWorld(type(exc).__name__ + ": " + _diagnostic(str(exc), _ACTIVE_ARENA),
                               outcome="refusal" if isinstance(exc, refusals) else "crash",
                               exception=_exception_record(exc, _ACTIVE_ARENA)) from exc
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


def _bindings(attribute, args, kwargs, arena, *, omit_first=False):
    try:
        signature = inspect.signature(attribute)
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
    except (TypeError, ValueError) as exc:
        return None, None, str(exc)
    if omit_first:
        bound.arguments.pop(next(iter(signature.parameters)), None)
    graph = _Graph(arena).pack(dict(bound.arguments))
    from .capture import plain
    try:
        values = plain(graph)
        json.dumps(values, allow_nan=False)
    except UnsupportedWorld:
        values = None  # The complete object-valued argument graph remains available.
    return values, graph, None


def _exception_record(exc, arena):
    result = {"type": type(exc).__module__ + ":" + type(exc).__qualname__, "message": _diagnostic(str(exc), arena)}
    stack, traceback, location_status = [], exc.__traceback__, "missing"
    while traceback is not None:
        frame = traceback.tb_frame
        filename = Path(frame.f_code.co_filename)
        if _ACTIVE_SOURCE_ROOT is not None and filename.is_absolute():
            try:
                relative = filename.resolve().relative_to(_ACTIVE_SOURCE_ROOT)
            except ValueError:
                pass  # An engine or dependency frame is outside this source root.
            except (OSError, RuntimeError) as error:
                location_status = "unreadable"
                result["location_error"] = str(error)
            else:
                stack.append({"path": relative.as_posix(), "line": traceback.tb_lineno,
                              "function": frame.f_code.co_qualname})
        traceback = traceback.tb_next
    result.update(source=stack[-1] if stack else None, stack=stack,
                  location_status="current" if stack and location_status != "unreadable" else location_status)
    return result


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
    invoking = False
    with redirect_stdout(output), redirect_stderr(error):
        try:
            invoking = True
            attribute = getattr(receiver, name)
            invoking = False
            if recipe.get("property"):
                value = attribute
                if capture:
                    bindings = {}
                    bindings_graph = _Graph(arena).pack({})
            else:
                args = _arguments(recipe.get("args", []), arena, results)
                kwargs = _arguments(recipe.get("kwargs", {}), arena, results)
                if capture:
                    bindings, bindings_graph, binding_error = _bindings(attribute, args, kwargs, arena)
                invoking = True
                value = attribute(*args, **kwargs)
                invoking = False
            if recipe.get("replace"):
                if type(value) is not type(objects["system"]):
                    raise UnsupportedWorld("a restored system has the wrong type")
                objects["system"] = value
                if "ui" in objects:
                    raise UnsupportedWorld("restore a UI through its public prefix")
            outcome, exception = "success", None
        except (UnsupportedWorld, NativeEngineError):
            raise
        except BaseException as exc:
            if not invoking:
                raise
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise UnsupportedWorld("the call terminated its interpreter") from exc
            value = None
            outcome = "refusal" if isinstance(exc, refusals) else "crash"
            exception = _exception_record(exc, arena)
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
            "sqlite3.connect",
        }:
            return
        if inputs is not None and event in {"open", "os.listdir", "os.scandir", "metadata", "import", "sqlite3.connect"}:
            inputs.record(event, args, caller=sys._getframe(1) if event in {"open", "os.listdir", "os.scandir", "sqlite3.connect"} else None)
        if event == 'sqlite3.connect':
            database = os.fsdecode(args[0])
            if database.startswith('file:'):
                raise UnsupportedWorld('SQLite URI inputs need an explicit world')
            if database != ':memory:':
                inside(database)
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
        elif event in {"os.putenv", "os.unsetenv"}:
            if inputs is None:
                raise UnsupportedWorld(event + " needs an explicit environment world; phase=execution")
            try:
                inputs.environment_mutation(event, args, sys._getframe(1))
            except UnsupportedWorld:
                raise
            except BaseException as exc:
                inputs.failure = NativeEngineError(str(exc), phase="capture")
                raise inputs.failure from exc
        elif event in {"socket.connect", "subprocess.Popen", "os.fork", "os.system", "os.exec", "os.posix_spawn"}:
            raise UnsupportedWorld(event + " needs an explicit process/network world; phase=" + (inputs.phase if inputs else "execution"))
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
        self.observe = None
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
                    from .capture import plain
                    try:
                        identifiers[kind] = plain(result)
                    except UnsupportedWorld:
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
        self.observed.local_cells.clear()
        self.observed.frames.clear()
        self.observed.frame_return_fields.clear()
        self.observed.call_parents.clear()
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
        with self.observed.inputs.importing():
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
        except (UnsupportedWorld, NativeEngineError):
            raise
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
            before_observations = self.observe(self, all_queries=True)
        self.observed.call_hits.clear()
        self.observed.call_events.clear()
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
                bindings, bindings_graph, binding_error = _bindings(constructor, [self.objects["system"], *args], kwargs,
                                                                   self.arena, omit_first=True)
            outcome, exception = "success", None
            try:
                with redirect_stdout(output), redirect_stderr(error):
                    value = constructor(self.objects["system"], *args, **kwargs)
            except (UnsupportedWorld, NativeEngineError):
                raise
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise UnsupportedWorld("the call terminated its interpreter") from exc
                import builtins
                refusals = self.refusals + tuple(getattr(builtins, name) for name in self.spec.get("ui_refusal", []))
                outcome = "refusal" if isinstance(exc, refusals) else "crash"
                exception = _exception_record(exc, self.arena)
            else:
                self.objects[receiver] = value
            after = snapshot(self.objects, self.arena, self.defaults)
            row = {"call": recipe, "outcome": outcome, "exception": exception,
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
        if self.observed.failure is not None:
            raise self.observed.failure
        row["hit_statements"] = sorted(self.observed.call_hits)
        row["events"] = list(self.observed.call_events)
        row["unchanged"] = row["before_key"] == row["after_key"]
        self.executed_calls += 1
        self.current = row["after"]
        if keep and self.observe_transitions:
            after_observations = self.observe(self, all_queries=True)
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
        mutable = {identity for identity, number in graph.seen.items() if graph.nodes[number]["type"] not in {"builtins:tuple", "builtins:frozenset", "re:Pattern"}}
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
        _ACTIVE_CLASSES = set(request["spec"].get("classes", []))
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
            def record_input_event(event, args, caller):
                if recording_active and event == "subprocess.Popen":
                    frame = caller
                    while frame is not None and not frame.f_code.co_filename.startswith(observed.root):
                        frame = frame.f_back
                    if frame is not None:
                        observed.recorded_gaps.add("subject subprocess code is outside this process observer")
                if recording_active and event in {"open", "os.listdir", "os.scandir", "metadata", "import", "sqlite3.connect"}:
                    inputs.record(event, args, caller=caller if event in {"open", "os.listdir", "os.scandir", "sqlite3.connect"} else None)
            def record_inputs(event, args):
                if not recording_active or event not in {"subprocess.Popen", "open", "os.listdir", "os.scandir", "metadata", "import", "sqlite3.connect"}:
                    return
                return observed._observe(record_input_event, event, args, sys._getframe(1))
            sys.addaudithook(record_inputs)
            finish_guard = lambda: None
        else:
            finish_guard = _arena_guard(arena, inputs)
        old_trace = sys.gettrace()
        old_profile = sys.getprofile()
        sys.settrace(observed.trace)
        sys.setprofile(observed.profile)
        try:
            if operation == "record":
                from .testrec import record
                response = record(request["spec"], arena, observed=observed,
                                  test_nodeids=request.get("options", {}).get("test_nodeids"))
            else:
                dispatch = _load(request["_dispatch"]) if request.get("_dispatch") else _run_session
                response = dispatch(request, arena, observed)
            if observed.failure is not None:
                raise observed.failure
            if inputs.failure is not None:
                raise inputs.failure
            response.setdefault("footprint", inputs.receipt())
        except UnsupportedWorld as exc:
            response = {"evidence_error": {"status": exc.evidence_status, "message": _diagnostic(str(exc), arena),
                                           "outcome": exc.outcome, "exception": exc.exception}}
        except BaseException as exc:
            response = {"engine_error": {"type": type(exc).__name__, "message": _diagnostic(str(exc), arena),
                                          "phase": getattr(exc, "phase", "execution")}}
        try:
            observed.enabled = False
            inputs.recording_tests = False
            recording_active = False
            sys.settrace(old_trace)
            sys.setprofile(old_profile)
            encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
            os.write(int(response_path), encoded.encode("utf-8"))
        finally:
            finish_guard()
            os.chdir(original_directory)


def _inventory_source(locator):
    module_name, _, symbol = locator.partition(":")
    module = sys.modules.get(module_name)
    namespace = (types.ModuleType.__getattribute__(module, "__dict__")
                 if isinstance(module, types.ModuleType) else {})
    filename = namespace.get("__file__")
    return {"owner": locator, "symbol": symbol,
            "path": filename if type(filename) is str and Path(filename).is_absolute() else None}


def public_inventory(objects, *, limits=None, sources=None):
    """List actual public descriptors without invoking properties or dynamic lookup."""
    result = {}
    for receiver, obj in objects.items():
        rows, seen, unknown = [], set(), []
        ancestry = []
        for owner in type.__getattribute__(type(obj), "__mro__"):
            module_name = type.__getattribute__(owner, "__module__")
            symbol = type.__getattribute__(owner, "__qualname__")
            locator = module_name + ":" + symbol
            # Binding ownership comes from the actual class dictionary, including
            # inherited/decorated methods. A wrapper's code file is not its owner.
            ancestry.append(_inventory_source(locator))
            for name, descriptor in type.__getattribute__(owner, "__dict__").items():
                if name in seen:
                    continue
                seen.add(name)
                if name == "__getattr__":
                    unknown.append("dynamic attribute lookup (__getattr__)")
                elif name == "__getattribute__" and owner is not object:
                    unknown.append("custom attribute lookup (__getattribute__)")
                if name.startswith("_"):
                    continue
                kind = ("static" if isinstance(descriptor, staticmethod) else
                        "class" if isinstance(descriptor, classmethod) else
                        "property" if isinstance(descriptor, property) else
                        "method" if callable(descriptor) else None)
                if kind is not None:
                    rows.append({"name": name, "owner": locator, "kind": kind})
        result[receiver] = sorted(rows, key=lambda row: row["name"])
        if limits is not None:
            limits[receiver] = unknown
        if sources is not None:
            sources[receiver] = ancestry
    return result


def _run_session(request, arena, observed):
    if request.get("operation", "trace") != "trace":
        raise UnsupportedWorld("operation requires an explicit source-pilot dispatch")
    session = _Session(request["spec"], request.get("start", {}), arena, observed)
    session.reset()
    initial = session.current
    steps = [session.step(item) for item in request["calls"]]
    limits, sources = {}, {}
    inventory = public_inventory(session.objects, limits=limits, sources=sources)
    bindings = {receiver: _inventory_source(session.spec["system" if receiver == "system" else "ui"])
                for receiver in session.objects}
    response = {"initial": initial, "steps": steps, "final": session.current, "inventory": inventory, "inventory_limits": limits,
                "inventory_sources": sources, "inventory_bindings": bindings,
                "defaults": session.defaults,
                "seeding": session.seeded, "construction_stdout": session.construction_stdout,
                "construction_stderr": session.construction_stderr}
    if session.rule_ledger is not None:
        response["rule_captures"] = session.rule_ledger.dump()
    return response


def replay(spec, calls, start=None, *, timeout=30, operation="trace", options=None, _dispatch=None, _runner=None):
    """One real trace in a fresh interpreter, using the existing process owner."""
    root = Path(spec["root"]).resolve()
    with tempfile.TemporaryDirectory(prefix="flowguard-replay-") as directory:
        path = Path(directory)
        request = path / "request.json"
        request.write_text(json.dumps({"spec": spec, "calls": calls, "start": start or {},
                                       "operation": operation, "options": options or {}, "_dispatch": _dispatch}), encoding="utf-8")
        response = path / "response.json"
        # The shared runner owns Popen; the worker opens its protocol stream before installing the arena guard.
        code = (
            f"import os,sys;sys.path.insert(0,{_child_package_import_root()!r});"
            "from flowguard.native.session import _worker;sys.path.pop(0);"
            "fd=os.open(sys.argv[2],os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);"
            "_worker(sys.argv[1],fd)"
        )
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(child_import_path(root, {})),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
        completed, timed_out, clean = (_runner or run_isolated_process)(
            [sys.executable, "-c", code, str(request), str(response)], cwd=path, env=env,
            timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if timed_out or not clean or completed.returncode:
            raise NativeEngineError("native child failed: " + (completed.stderr or str(completed.returncode)))
        try:
            result = json.loads(response.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise NativeEngineError("native child returned no complete observation", phase="protocol") from exc
        if "engine_error" in result:
            error = result["engine_error"]
            raise NativeEngineError(error["type"] + ": " + error["message"], phase=error["phase"])
        if "evidence_error" in result:
            error = result["evidence_error"]
            raise UnsupportedWorld(error["message"], evidence_status=error["status"],
                                   outcome=error.get("outcome"), exception=error.get("exception"))
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
