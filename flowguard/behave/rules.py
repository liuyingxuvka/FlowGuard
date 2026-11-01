"""Independent rules over immutable recorded public facts; no world execution."""

from __future__ import annotations

import ast
import base64
import builtins
from collections.abc import Mapping
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import types
from types import MappingProxyType

from flowguard.map.common import normalize_newlines, read_source
from flowguard.map.inventory import syntax_tree
from flowguard.map.mapfile import MapError
from flowguard.map.requests import REQUEST_DIR, validate_request_links

from .capture import failure_context, iter_states, iter_steps

_API = "flowguard.behave.rules"
_NOT_READY = "explored result for this tree not ready: python -m flowguard.behave audit"
_API_NAMES = {"rule", "owner", "imported", "derived", "decision"}
# A temporary supported source fragment, not full F7 standard-library support.
_PURE_STDLIB = {"math"}
_PURE_BUILTINS = {"abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "isinstance",
                  "len", "list", "map", "max", "min", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip"}


def owner(request, quote):
    return {"kind": "owner", "request": request, "quote": quote}


def imported(path, quote):
    return {"kind": "imported", "path": path, "quote": quote}


def derived(serves, *, why):
    return {"kind": "derived", "serves": serves, "why": why}


def decision(*, why):
    return {"kind": "decision", "why": why}


def rule(*provenance, private=None):
    """A normal pytest run cannot manufacture an explored clean rule result."""
    def decorate(function):
        def unavailable():
            import pytest
            if os.environ.get("CI", "").lower() == "true":
                pytest.fail(_NOT_READY, pytrace=False)
            pytest.skip(_NOT_READY)
        unavailable.__name__ = function.__name__
        unavailable.__doc__ = function.__doc__
        unavailable._flowguard_rule = function
        unavailable._flowguard_provenance = provenance
        unavailable._flowguard_private = private
        return unavailable
    return decorate


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + "." + node.attr
    return ""


def _normal(node):
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        if isinstance(child, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if child.body and isinstance(child.body[0], ast.Expr) and isinstance(child.body[0].value, ast.Constant) and isinstance(child.body[0].value.value, str):
                child.body = child.body[1:]
        if isinstance(child, ast.Call) and _name(child.func).split(".")[-1] == "rule":
            child.args = []
    return ast.dump(node, include_attributes=False)


def _module_name(path):
    return path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")


def _import_name(node, module, *, package=False):
    if not isinstance(node, ast.ImportFrom):
        return ""
    if not node.level:
        return node.module or ""
    parents = (module if package else module.rpartition(".")[0]).split(".")
    return ".".join(parents[:len(parents) - node.level + 1] + ([node.module] if node.module else []))


def collect_rules(root, *, rules_root="tests/rules"):
    """Collect ASTs and source closures independently of pytest selection."""
    root, relative = Path(root).resolve(), Path(rules_root)
    directory = root / relative
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("rules_root must be a project-relative directory")
    modules, errors, rules = {}, [], []

    def error(code, path, node, message, identifier=None):
        errors.append({"code": code, "path": path, "line": getattr(node, "lineno", 1),
                       "message": message, **({"rule": identifier} if identifier else {})})

    for file in sorted(directory.rglob("*.py")) if directory.is_dir() else ():
        path = file.relative_to(root).as_posix()
        try:
            tree = syntax_tree(read_source(file))
        except (OSError, SyntaxError, UnicodeError) as exc:
            error("rule_file_impure", path, None, str(exc))
            continue
        definitions, bindings = {}, {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id] = node
                try:
                    ast.literal_eval(node.value)
                    if any(not isinstance(target, ast.Name) for target in targets):
                        raise ValueError("attribute assignment")
                except (ValueError, TypeError):
                    error("rule_file_impure", path, node, "module assignments must be literal constants")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    definitions[alias.asname or alias.name.split(".")[0]] = node
                    bindings[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                module = _import_name(node, _module_name(path), package=path.endswith("/__init__.py"))
                for alias in node.names:
                    definitions[alias.asname or alias.name] = node
                    bindings[alias.asname or alias.name] = module + "." + alias.name
            elif not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                error("rule_file_impure", path, node, "a rule module contains only imports, literal constants and definitions")
        modules[path] = {"tree": tree, "definitions": definitions, "bindings": bindings, "unsupported": [],
                         "sha256": hashlib.sha256(normalize_newlines(file.read_bytes())).hexdigest()}

    by_module = {_module_name(path): path for path in modules}

    def target(name):
        return by_module.get(name)

    def imported_paths(path, node):
        names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [
            _import_name(node, _module_name(path), package=path.endswith("/__init__.py"))]
        paths = []
        for name in names:
            if name == _API:
                if isinstance(node, ast.ImportFrom) and any(alias.name not in _API_NAMES for alias in node.names):
                    error("rule_imports_system", path, node, "import only the public rule metadata names")
                continue
            found = target(name)
            children = [target(name + "." + alias.name) for alias in node.names] if isinstance(node, ast.ImportFrom) else []
            if found or any(children) or any(key.startswith(name + ".") for key in by_module):
                paths.extend(child for child in children if child)
            if found:
                paths.append(found)
            if found or any(children) or any(key.startswith(name + ".") for key in by_module):
                continue
            top = name.split(".")[0]
            shadowed = (root / (top + ".py")).exists() or (root / top / "__init__.py").exists()
            if top not in sys.stdlib_module_names or shadowed:
                error("rule_imports_system", path, node, "import only the rule API, standard library or conforming rules-root helpers: " + name)
            elif top not in _PURE_STDLIB:
                modules[path]["unsupported"].append("standard-library surface not supported by this first slice: " + name)
        return paths

    for path, module in modules.items():
        module["imports"] = {}
        for node in ast.walk(module["tree"]):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module["imports"][node.lineno] = imported_paths(path, node)
                if isinstance(node, ast.Import):
                    module["bindings"].update({alias.asname or alias.name.split(".")[0]: alias.name for alias in node.names})
                else:
                    base = _import_name(node, _module_name(path), package=path.endswith("/__init__.py"))
                    module["bindings"].update({alias.asname or alias.name: base + "." + alias.name for alias in node.names})

    # Only the current finite assertion fragment is executable. This avoids
    # pretending that arbitrary Python effects are a read-only norm evaluator.
    for path, module in modules.items():
        helper_names = {name for name, node in module["definitions"].items() if isinstance(node, ast.FunctionDef)}
        imported_helpers = {name for name, value in module["bindings"].items()
                            if any(value == key or value.startswith(key + ".") for key in by_module)}
        marker_calls = set()
        for fn in module["tree"].body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            for decorator in fn.decorator_list:
                name = _name(decorator.func) if isinstance(decorator, ast.Call) else _name(decorator)
                first, dot, rest = name.partition(".")
                canonical = module["bindings"].get(first, first) + (dot + rest if dot else "")
                if canonical == _API + ".rule":
                    marker_calls.update(id(item) for item in ast.walk(decorator) if isinstance(item, ast.Call))
                else:
                    module["unsupported"].append("helper decorators are not supported by the finite rule slice")
            if any(isinstance(item, ast.Call) for default in [*fn.args.defaults, *[value for value in fn.args.kw_defaults if value]]
                   for item in ast.walk(default)):
                module["unsupported"].append("computed signature defaults are not supported by the finite rule slice")
        for node in ast.walk(module["tree"]):
            reason = None
            if isinstance(node, (ast.ClassDef, ast.While, ast.With, ast.AsyncWith, ast.Global, ast.Nonlocal)):
                reason = "source construct not supported by the finite rule slice: " + type(node).__name__
            elif isinstance(node, ast.Attribute) and (node.attr.startswith("_") or isinstance(node.ctx, (ast.Store, ast.Del))):
                reason = "private/effectful attribute access is not captured by this slice"
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id.startswith("__"):
                reason = "dynamic namespace access is not supported by this slice"
            elif isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                reason = "mutation is not supported by the finite rule slice"
            elif isinstance(node, ast.Call) and id(node) not in marker_calls:
                name = _name(node.func)
                first = name.split(".")[0]
                canonical = module["bindings"].get(first, first)
                view = first in {"step", "state"} and isinstance(node.func, ast.Attribute) and not isinstance(node.func.value, ast.Call)
                pure_module = canonical.split(".")[0] in _PURE_STDLIB
                if not (name in _PURE_BUILTINS or name in helper_names or first in imported_helpers or view or pure_module):
                    reason = "dynamic/effectful call is not supported by the finite rule slice: " + (name or type(node.func).__name__)
            if reason:
                module["unsupported"].append(reason)

    def closure(path, function, world):
        pending, kept, seen = [(path, function)], [], set()
        while pending:
            source, node = pending.pop()
            key = source, id(node)
            if key in seen:
                continue
            seen.add(key)
            kept.append([source, _normal(node)])
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                pending.extend((other, modules[other]["tree"]) for other in modules[source]["imports"].get(node.lineno, ()))
            if isinstance(node, ast.Module):
                pending.extend((source, item) for item in node.body)
            else:
                local = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    local.update(arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
                names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)} - local
                pending.extend((source, modules[source]["definitions"][name]) for name in names if name in modules[source]["definitions"])
                pending.extend((source, item) for item in ast.walk(node) if isinstance(item, (ast.Import, ast.ImportFrom)))
        assertions = {}
        for source, _ in seen:
            assertions[source] = sorted({item.lineno for item in ast.walk(modules[source]["tree"]) if isinstance(item, ast.Assert)})
        return _digest([sorted(kept), world]), assertions

    for path, module in modules.items():
        def canonical(node):
            name = _name(node)
            first, dot, rest = name.partition(".")
            return module["bindings"].get(first, first) + (dot + rest if dot else "")
        for function in module["tree"].body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            markers = [node for node in function.decorator_list if isinstance(node, ast.Call) and canonical(node.func) == _API + ".rule"]
            if not markers:
                continue
            owner_directory = Path(path).parent.relative_to(relative).as_posix().replace("/", ".")
            owner_directory = "" if owner_directory == "." else owner_directory
            identifier = (owner_directory + "." if owner_directory else "") + function.name
            marker = markers[0]
            parameters = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
            fixture = parameters[0].arg if len(parameters) == 1 else ""
            if (fixture not in {"step", "state", "reach", "pair", "index"} or function.args.defaults
                    or function.args.kw_defaults or function.args.vararg or function.args.kwarg or isinstance(function, ast.AsyncFunctionDef)):
                error("rule_signature", path, function, "a rule takes exactly one fixture parameter with no default", identifier)
            if len(markers) != 1 or any(node not in markers for node in function.decorator_list):
                error("rule_decorator_unknown", path, function, "only @rule is implemented in this slice", identifier)
            private = None
            for keyword in marker.keywords:
                if keyword.arg == "private":
                    try:
                        private = ast.literal_eval(keyword.value)
                    except (ValueError, TypeError):
                        error("rule_file_impure", path, keyword.value, "private reason must be a literal", identifier)
                else:
                    error("rule_decorator_unknown", path, function, "the rule marker accepts provenance and private only", identifier)
            provenance = []
            for node in marker.args:
                kind = canonical(node.func).removeprefix(_API + ".") if isinstance(node, ast.Call) else ""
                if kind != "owner":
                    provenance.append({"kind": kind or "unknown", "supported": False})
                    continue
                try:
                    request, quote = [ast.literal_eval(arg) for arg in node.args]
                    validate_request_links(root, [{"id": request, "part": False}])
                    body = REQUEST_DIR / (request + ".md")
                    text = normalize_newlines((root / body).read_bytes()).decode("utf-8")
                    if not isinstance(quote, str) or not quote or quote not in text:
                        error("quote_not_in_request", path, node, "quote the stored owner words verbatim", identifier)
                        continue
                    provenance.append({"kind": "owner", "request": request, "quote": quote,
                                       "path": body.as_posix(), "line": text[:text.index(quote)].count("\n") + 1})
                except (ValueError, TypeError, OSError, MapError) as exc:
                    code = str(exc).partition(":")[0] if isinstance(exc, MapError) else "rule_without_provenance"
                    error(code, path, node, str(exc), identifier)
            if not marker.args:
                error("rule_without_provenance", path, function, "supply at least one provenance", identifier)
            for node in ast.walk(function):
                if isinstance(node, ast.Attribute) and node.attr.startswith("_") and not private:
                    error("rule_reads_private", path, node, "private reads require an explicit reason", identifier)
            world = "skeleton"
            for parent in [Path(path).parent, *Path(path).parent.parents]:
                if parent == relative.parent:
                    break
                found = [parent / name for name in ("world.py", "machine.py") if (root / parent / name).is_file()]
                if found:
                    world = found[0].as_posix()
                    break
            fingerprint, assertions = closure(path, function, world)
            rules.append({"id": identifier, "function": owner_directory, "name": function.name,
                          "path": path, "line": function.lineno, "fixture": fixture, "closure": fingerprint,
                          "provenance": provenance, "private": private, "world": world, "assertions": assertions,
                          "unsupported": sorted({reason for source in assertions for reason in modules[source]["unsupported"]})})
    for identifier in {row["id"] for row in rules}:
        if sum(row["id"] == identifier for row in rules) > 1:
            error("rule_name_duplicate", "", None, "rule identity appears more than once: " + identifier, identifier)
    source = {path: {"sha256": row["sha256"]} for path, row in modules.items()}
    return {"root": str(root), "rules_root": relative.as_posix(), "rules": rules, "errors": errors,
            "modules": source, "identity": _digest([rules, errors])}


class _Unavailable(Exception):
    pass


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _readonly(*args, **kwargs):
    raise _Unavailable("captured public values are read-only")


class _ListView(list):
    __slots__ = ()
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = _readonly
    __iadd__ = __imul__ = _readonly


class _DictView(dict):
    __slots__ = ()
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _readonly


class _SetView(set):
    __slots__ = ()
    add = clear = difference_update = discard = intersection_update = pop = remove = symmetric_difference_update = update = _readonly
    __ior__ = __iand__ = __ixor__ = __isub__ = _readonly


def _read_graph(pack):
    """Read the existing native graph into detached readonly builtin values."""
    nodes, memo, pending = pack["nodes"], {}, set()

    def read(value):
        if value is None or type(value) in (bool, int, str):
            return value
        if not isinstance(value, Mapping):
            raise _Unavailable("unsupported native public value")
        if "float" in value:
            return float.fromhex(value["float"])
        if "bytes" in value:
            return base64.b64decode(value["bytes"], validate=True)
        if "builtin_type" in value:
            types = {"builtins:" + name: item for name, item in (("str", str), ("int", int), ("float", float), ("bool", bool))}
            if value["builtin_type"] in types:
                return types[value["builtin_type"]]
        if "ref" not in value:
            raise _Unavailable("this native public type needs an explicit rule view")
        number = value["ref"]
        if number in memo:
            return memo[number]
        if number in pending:
            raise _Unavailable("cyclic public values need an explicit rule view")
        pending.add(number)
        node = nodes[number]
        if node["type"] == "builtins:dict":
            result = _DictView((read(key), read(item)) for key, item in node["items"])
        elif node["type"] == "builtins:list":
            result = _ListView(read(item) for item in node["items"])
        elif node["type"] == "builtins:tuple":
            result = tuple(read(item) for item in node["items"])
        elif node["type"] == "builtins:set":
            result = _SetView(read(item) for item in node["items"])
        elif node["type"] == "builtins:frozenset":
            result = frozenset(read(item) for item in node["items"])
        else:
            raise _Unavailable("this native public type needs an explicit rule view: " + node["type"])
        pending.remove(number)
        memo[number] = result
        return result

    return read(pack["root"])


class _View:
    __slots__ = ("_observation", "_spec")

    def __init__(self, observation, spec):
        object.__setattr__(self, "_observation", _freeze(copy.deepcopy(observation)))
        object.__setattr__(self, "_spec", spec if isinstance(spec, MappingProxyType) else _freeze(copy.deepcopy(spec)))

    def __setattr__(self, name, value):
        raise _Unavailable("rule views are read-only")

    def __getattr__(self, name):
        if name.startswith("_"):
            raise _Unavailable("private state was not captured: " + name)
        if name in self._spec.get("actions", ()):
            raise _Unavailable("rule_calls_action: " + name)
        def query(*args, **kwargs):
            for kind, entity in self._spec.get("entities", {}).items():
                if name == entity["list"]:
                    ids = self._observation.get("identifiers", {})
                    if args or kwargs or kind not in ids:
                        raise _Unavailable("entity identifiers were not captured: " + name)
                    graphs = self._observation.get("identifiers_graph", {})
                    return _read_graph(graphs[kind]) if kind in graphs else ids[kind]
            if kwargs or name in self._observation.get("unknown", ()):
                raise _Unavailable("public query was not captured: " + name)
            for row in self._observation.get("values", ()):
                if row["query"] == name and tuple(row.get("args", ())) == args:
                    return _read_graph(row["value_graph"]) if "value_graph" in row else row["value"]
            raise _Unavailable("public query was not captured: " + name)
        return query


class _Step:
    __slots__ = ("name", "args", "before", "after", "_spec")

    def __init__(self, row, spec):
        object.__setattr__(self, "name", row["call"].get("name", row["call"].get("construct")))
        if "args" not in row and "args_graph" not in row:
            raise _Unavailable("resolved public arguments were not captured")
        object.__setattr__(self, "args", _read_graph(row["args_graph"]) if "args_graph" in row else _freeze(copy.deepcopy(row["args"])))
        object.__setattr__(self, "before", _View(row["before"], spec))
        object.__setattr__(self, "after", _View(row["after"], spec))
        object.__setattr__(self, "_spec", spec if isinstance(spec, MappingProxyType) else _freeze(copy.deepcopy(spec)))

    def __setattr__(self, name, value):
        raise _Unavailable("rule views are read-only")

    def created(self, kind):
        before, after = self.before._observation.get("identifiers", {}), self.after._observation.get("identifiers", {})
        if kind not in before or kind not in after:
            raise _Unavailable("created entity identifiers were not captured: " + kind)
        return tuple(value for value in after[kind] if value not in before[kind])


class _Modules:
    """A single judge call's module namespace; no sys.path or persistent registry."""
    def __init__(self, plan):
        self.plan, self.loaded = plan, {}
        self.paths = {_module_name(path): path for path in plan["modules"]}

    def load(self, name):
        if name in self.loaded:
            return self.loaded[name]
        path = self.paths.get(name)
        module = types.ModuleType(name)
        module.__package__ = name if path is None or path.endswith("/__init__.py") else name.rpartition(".")[0]
        self.loaded[name] = module
        if path is None:
            return module
        physical = Path(self.plan["root"]) / path
        if hashlib.sha256(normalize_newlines(physical.read_bytes())).hexdigest() != self.plan["modules"][path]["sha256"]:
            raise _Unavailable("rule source changed after collection: " + path)
        values = dict(vars(builtins))
        values["__import__"] = self.import_module
        module.__dict__.update(__builtins__=values, __file__=str(physical))
        exec(compile(copy.deepcopy(syntax_tree(read_source(physical))), str(physical), "exec", dont_inherit=True, optimize=0), module.__dict__)
        return module

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            package = (globals or {}).get("__package__", "").split(".")
            name = ".".join(package[:len(package) - level + 1] + ([name] if name else []))
        if name == _API:
            module = types.ModuleType(_API)
            module.__dict__.update({key: globals_api for key in _API_NAMES if (globals_api := vars(sys.modules[__name__])[key])})
            return module
        if name in self.paths or any(key.startswith(name + ".") for key in self.paths):
            module = self.load(name)
            if fromlist:
                for member in fromlist:
                    child = name + "." + member
                    if child in self.paths:
                        setattr(module, member, self.load(child))
                return module
            pieces = name.split(".")
            for index in range(1, len(pieces)):
                parent = self.load(".".join(pieces[:index]))
                setattr(parent, pieces[index], self.load(".".join(pieces[:index + 1])))
            return self.load(pieces[0])
        if name.split(".")[0] not in _PURE_STDLIB:
            raise _Unavailable("import is outside the finite offline rule slice: " + name)
        return builtins.__import__(name, globals, locals, fromlist, 0)


def judge(plan, captures):
    """Recompute the current norm judgment over supplied facts; never query a world."""
    result = {"identity": plan["identity"], "rules": [], "candidates": [], "not_judged": [],
              "errors": plan["errors"], "evaluated": 0,
              "scope": {"complete": bool(captures.get("complete", False)), "missing": list(captures.get("missing", ())),
                        "steps": len(captures.get("steps", ())), "states": len(captures.get("states", ()))}}
    modules = _Modules(plan)
    spec = _freeze(copy.deepcopy(captures.get("spec", {})))
    monitoring = getattr(sys, "monitoring", None)
    slot = next((number for number in range(6) if monitoring.get_tool(number) is None), None) if monitoring else None
    active, hits = set(), [0]
    def line(code, lineno):
        if (code.co_filename, lineno) in active:
            hits[0] += 1
    if slot is not None:
        monitoring.use_tool_id(slot, "flowguard-rule-assertions")
        monitoring.register_callback(slot, monitoring.events.LINE, line)
        monitoring.set_events(slot, monitoring.events.LINE)
    try:
        for rule_spec in plan["rules"]:
            row = {key: rule_spec[key] for key in ("id", "function", "path", "line", "fixture", "closure", "provenance")}
            row.update(status="not-judged", evaluated=0, assertion_hits=0)
            reasons, failures = [], []
            reasons.extend(rule_spec.get("unsupported", ()))
            if plan["errors"]:
                reasons.append("rule collection has static errors")
            if rule_spec["fixture"] not in {"step", "state"}:
                reasons.append("fixture is not implemented in this slice: " + rule_spec["fixture"])
            if rule_spec["world"] != "skeleton":
                reasons.append("no matching captured judging world: " + rule_spec["world"])
            if any(value.get("kind") != "owner" for value in rule_spec["provenance"]):
                reasons.append("provenance is not implemented in this slice")
            if slot is None:
                reasons.append("native rule assertion monitoring is unavailable")
            if not reasons:
                try:
                    function = getattr(modules.load(_module_name(rule_spec["path"])), rule_spec["name"])
                    function = function._flowguard_rule
                    active.clear()
                    active.update((str(Path(plan["root"]) / path), number)
                                  for path, numbers in rule_spec["assertions"].items() for number in numbers)
                    records = iter_steps(captures) if rule_spec["fixture"] == "step" else iter_states(captures)
                    for record in records:
                        if rule_spec["fixture"] == "step" and record.get("outcome") != "success":
                            continue
                        previous = hits[0]
                        try:
                            view = _Step(record, spec) if rule_spec["fixture"] == "step" else _View(record["observation"], spec)
                            row["evaluated"] += 1
                            function(view)
                        except AssertionError as exc:
                            failures.append({**failure_context(record),
                                **{key: record[key] for key in ("call", "before_key", "after_key", "state_key") if key in record},
                                "rule": rule_spec["id"], **{key: rule_spec[key] for key in ("function", "path", "line", "closure", "fixture", "provenance")},
                                "message": str(exc) or "assertion failed",
                                "action": record.get("call", {}).get("name", "state")})
                        except Exception as exc:
                            reasons.append(str(exc) or type(exc).__name__)
                        finally:
                            row["assertion_hits"] += hits[0] - previous
                except Exception as exc:
                    reasons.append(str(exc) or type(exc).__name__)
            if failures:
                row["status"] = "broken"
                shortest = {}
                for candidate in failures:
                    action = candidate["action"]
                    if action not in shortest or len(candidate["prefix"]) < len(shortest[action]["prefix"]):
                        shortest[action] = candidate
                result["candidates"].extend(shortest.values())
            else:
                if not captures.get("complete", False):
                    reasons.extend(captures.get("missing") or ["captured scope is incomplete"])
                if not row["evaluated"] or not row["assertion_hits"]:
                    reasons.append("rule_never_applies: no captured assertion executed")
                if not reasons:
                    row["status"] = "clean"
            if reasons:
                row["reason"] = "; ".join(sorted(set(reasons)))
                result["not_judged"].append({"rule": row["id"], "reason": row["reason"]})
            result["rules"].append(row)
            result["evaluated"] += row["evaluated"]
    finally:
        if slot is not None:
            monitoring.set_events(slot, 0)
            monitoring.register_callback(slot, monitoring.events.LINE, None)
            monitoring.free_tool_id(slot)
    return result


def pytest_pycollect_makeitem(collector, name, obj):
    """Pytest presents rules; the engine remains their independent collector."""
    if not name.startswith("test_") or not hasattr(obj, "_flowguard_rule"):
        return None
    import pytest
    class RuleItem(pytest.Item):
        def runtest(self):
            from . import engine
            read = getattr(engine, "judge_cached_rules", None)
            result = read(Path(self.config.rootpath)) if read else None
            current = collect_rules(Path(self.config.rootpath))
            row = next((row for row in (result or {}).get("rules", ()) if row["id"] == self.rule_id), None)
            if result is None or result.get("identity") != current["identity"] or row is None or row["status"] == "not-judged":
                if os.environ.get("CI", "").lower() == "true" or self.config.getoption("fg_require_explored", False):
                    pytest.fail(_NOT_READY, pytrace=False)
                pytest.skip(_NOT_READY)
            if row["status"] == "broken":
                pytest.fail("RULE " + self.rule_id + " failed on recorded facts; python -m flowguard.behave audit", pytrace=False)
        def reportinfo(self):
            return self.path, obj._flowguard_rule.__code__.co_firstlineno - 1, self.name
    path = Path(obj._flowguard_rule.__code__.co_filename)
    root = Path(collector.config.rootpath)
    function = path.parent.relative_to(root / "tests/rules").as_posix().replace("/", ".")
    identifier = (function + "." if function != "." else "") + name
    provenance = obj._flowguard_provenance
    owner_text = ", ".join("owner " + value["request"] for value in provenance if value.get("kind") == "owner")
    item = RuleItem.from_parent(collector, name="RULE " + identifier + (" (" + owner_text + ")" if owner_text else ""))
    item.rule_id = identifier
    return item


def pytest_addoption(parser):
    parser.addoption("--fg-require-explored", action="store_true", default=False,
                     help="fail rule items without a current explored judgment")


def pytest_terminal_summary(terminalreporter):
    selected = [report for reports in terminalreporter.stats.values() for report in reports
                if "RULE " in getattr(report, "nodeid", "") and getattr(report, "when", "call") == "call"]
    if selected:
        missing = sum(report.skipped or _NOT_READY in str(getattr(report, "longrepr", "")) for report in selected)
        failed = sum(report.failed and _NOT_READY not in str(getattr(report, "longrepr", "")) for report in selected)
        word = "BLOCKED" if failed else "UNCHECKED"
        terminalreporter.write_line(f"FLOWGUARD {word}: {len(selected)} rule items, {missing} not judged; rule-only display, use audit for the complete verdict")
