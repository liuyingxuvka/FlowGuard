"""Authoring API of a flow model, its declaration checks, and the loader.

A model file in `.flowguard/flow/<name>.py` builds one `Model` and ends with `MODEL = m`.
Everything here only records declarations; `explore.py` runs them.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import importlib
import itertools
import os
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Key = str | tuple                    # "day", ("cond", "T1")
Step = tuple                         # (action name, params, args)

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PKG_NAME = __name__.rpartition(".")[0]          # "flowguard._next" (no hard-coded name)
_MISSING = object()
_MAX_IDS = 4
_LOAD = {"root": None}                           # set by load_model while a model file runs


class ModelError(Exception):
    """The model itself is wrong: a declaration, an exception in its code, a bad write."""

    def __init__(self, text, file=None, line=None, at=None):
        super().__init__(text)
        self.text = text
        self.file = file          # path relative to the project root when known
        self.line = line
        self.at = at              # (state index, call index or None) for exploration errors
        self.reads = ()           # set by load_model: the files read before the error

    def where(self) -> str:
        if self.file is None:
            return ""
        return f"{self.file}:{self.line}" if self.line else str(self.file)

    def __str__(self):
        w = self.where()
        return f"{w}: {self.text}" if w else self.text


class Refused(Exception):
    """Raised by need(): the action is not possible in this state."""

    def __init__(self, reason, source=None, where=(None, None)):
        super().__init__(reason)
        self.reason = reason
        self.source = source
        self.where = where        # (file, line) of the need() call that refused

    def __str__(self):
        return str(self.reason)


def need(condition, reason="refused", *, source=None):
    """Inside an action: refuse it (with a reason, and the request it comes from) unless
    condition holds. Without source= the guard carries its action's source."""
    if not condition:
        f = sys._getframe(1)
        raise Refused(reason, source, (f.f_code.co_filename, f.f_lineno))


_NO_SOURCE = contextlib.nullcontext()


class State(dict):
    """A state: field key -> value. Read s["day"], s["cond", t]; assign to change it."""
    __slots__ = ()

    def source(self, request):
        """`with s.source("R10"): ...` marks the effects written in the block as coming
        from that request. The search itself records nothing; a replay does."""
        return _NO_SOURCE


class Ids(tuple):
    """Interchangeable object ids of one kind, from `m.objects(kind, *ids)`."""

    def __new__(cls, kind, ids):
        self = super().__new__(cls, ids)
        self.kind = kind
        return self

    def __radd__(self, other):                    # [None] + TOOLS
        if isinstance(other, list):
            return other + list(self)
        return NotImplemented

    def __repr__(self):
        return f"Ids({self.kind!r}, {tuple(self)!r})"


@dataclass(frozen=True)
class Field:
    key: object
    family: str
    obj: object
    domain: tuple
    init: object
    source: str | None
    value_sources: dict
    note: str | None
    line: int
    kind: str | None = None          # the declared kind of obj (m.objects), else None


@dataclass(frozen=True)
class Action:
    index: int
    name: str
    params: tuple
    domains: tuple
    fn: Callable
    source: str | None
    note: str | None
    line: int


@dataclass(frozen=True)
class Call:
    index: int
    action: Action
    args: tuple

    def step(self) -> Step:
        return (self.action.name, self.action.params, self.args)


@dataclass(frozen=True)
class Option:
    name: str
    params: tuple
    domains: tuple
    offered: Callable
    action: str
    source: str | None
    note: str | None
    line: int


@dataclass(frozen=True)
class Rule:
    kind: str                         # always | only_when | after | progress | reach
    name: str                         # unique; per-object rules end in " [T1]"
    base: str                         # the name as written
    action: str | None
    pred: Callable | None
    when: Callable | None
    goal: Callable | None
    obj: object
    source: str | None
    note: str | None
    line: int
    over_kind: str | None = None      # kind of obj when the rule was declared over m.objects


@dataclass(frozen=True)
class Setting:
    name: str
    value: object
    origin: str                       # "code" | "model only"
    where: str | None                 # "counter/config.py: Config.maintain_every"
    source: str | None
    vary: tuple | None
    note: str | None


@dataclass(frozen=True)
class SecondRoute:
    actions: tuple
    source: str
    why: str
    line: int


def natural_key(text):
    """R4 before R10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(text))]


def _outside_frame():
    f = sys._getframe(1)
    while f is not None and os.path.dirname(os.path.abspath(f.f_code.co_filename)) == _PKG_DIR:
        f = f.f_back
    return f


def _rel(path):
    root = _LOAD["root"]
    p = os.path.abspath(str(path))
    if root is not None:
        try:
            return Path(p).relative_to(root).as_posix()
        except ValueError:
            return p
    return p


def _here():
    f = _outside_frame()
    if f is None:
        return None, None
    return _rel(f.f_code.co_filename), f.f_lineno


def _fail(text):
    file, line = _here()
    raise ModelError(text, file, line)


def _check_source(source, what):
    if source is not None and (not isinstance(source, str) or not source.strip()):
        _fail(f"{what}: source= must be a request id such as 'R10', not {source!r}")
    return source


def _check_note(note, what):
    if note is not None and not isinstance(note, str):
        _fail(f"{what}: note= must be text, not {note!r}")
    return note


def _key(name, k):
    if k is None:
        return name
    return (name,) + tuple(k) if isinstance(k, tuple) else (name, k)


def show_key(key) -> str:
    if isinstance(key, tuple):
        return f"{key[0]}[{','.join(str(x) for x in key[1:])}]"
    return str(key)


class _RecordingSource:
    def __init__(self, state, request):
        self.state, self.request = state, request

    def __enter__(self):
        self.state._stack.append(self.request)

    def __exit__(self, *exc):
        self.state._stack.pop()
        return False


class RecordingState(State):
    """A state that records which marked block wrote each effect (replay only)."""
    __slots__ = ("_stack", "writes")

    def __init__(self, *args):
        super().__init__(*args)
        self._stack = []
        self.writes = []                          # (key, value, source of the block or None)

    def source(self, request):
        return _RecordingSource(self, request)

    def __setitem__(self, key, value):
        self.writes.append((key, value, self._stack[-1] if self._stack else None))
        super().__setitem__(key, value)


class Model:
    """One flow model. See HOWTO.md."""

    def __init__(self, name, covers=(), config=None, note=None, valid=None):
        if not isinstance(name, str) or not name.strip():
            _fail(f"Model name must be text, not {name!r}")
        if isinstance(covers, str) or not all(isinstance(c, str) for c in covers):
            _fail("covers= must be a list of 'file', 'file:Class' or 'file:Class.method'")
        if config is not None and (not isinstance(config, str) or config.count(":") != 1):
            _fail(f"config= must be 'package.module:Object', not {config!r}")
        if valid is not None and not callable(valid):
            _fail("valid= must be a function of the settings")
        self.id = None                    # the file stem, set by the loader
        self.path = None
        self.root = None
        self.name = name
        self.covers = tuple(covers)
        self.config = config
        self.note = _check_note(note, f"model {name!r}")
        self.valid = valid
        self.settings = {}
        self.setting_info = {}
        self.fields = []
        self.actions = []
        self.options = []
        self.rules = []
        self.terminals = {}
        self.terminal_sources = {}
        self.kinds = {}
        self.second_routes = []
        self.line = _here()[1]
        self._calls = None
        self._config_obj = _MISSING
        self._config_file = None
        if config is not None:
            self._config_obj, self._config_file = _import_config(config)

    def __repr__(self):
        return f"Model({self.name!r})"

    # ------------------------------------------------------------------ declaring
    def setting(self, name, value=_MISSING, *, source=None, vary=None, note=None):
        """A setting. Without a value it is read from the code's configuration object
        (config=); with a value it is a setting the code does not have yet."""
        what = f"setting {name!r}"
        if not isinstance(name, str) or not name.isidentifier():
            _fail(f"setting name must be an identifier, not {name!r}")
        if name in self.setting_info:
            _fail(f"{what} is declared twice")
        _check_source(source, what)
        _check_note(note, what)
        if vary is not None:
            vary = tuple(vary)
        if value is _MISSING:
            if self._config_obj is _MISSING:
                _fail(f"{what} has no value: give the model config='module:Object' or a value")
            if not hasattr(self._config_obj, name):
                _fail(f"{what}: {self.config} has no attribute {name!r}")
            value = getattr(self._config_obj, name)
            where = f"{_rel(self._config_file)}: {self.config.split(':')[1]}.{name}"
            info = Setting(name, value, "code", where, source, vary, note)
        else:
            if self._config_obj is not _MISSING and hasattr(self._config_obj, name):
                _fail(f"{what}: {self.config} has it; read it from the code: drop the value")
            info = Setting(name, value, "model only", None, source, vary, note)
        self.settings[name] = value
        self.setting_info[name] = info
        return value

    def objects(self, kind, *ids):
        """Interchangeable object ids of one kind; explored up to renaming."""
        if not isinstance(kind, str) or not kind.isidentifier():
            _fail(f"objects: the kind must be a word such as 'tool', not {kind!r}")
        if kind in self.kinds:
            _fail(f"objects: kind {kind!r} is declared twice")
        if not ids or not all(isinstance(i, str) and i for i in ids):
            _fail(f"objects {kind!r}: give the ids as text, e.g. m.objects({kind!r}, 'T1', 'T2')")
        if len(set(ids)) != len(ids):
            _fail(f"objects {kind!r}: an id is listed twice")
        if len(ids) > _MAX_IDS:
            _fail(f"objects {kind!r}: at most {_MAX_IDS} ids per kind (the canonical form "
                  f"tries every renaming); use fewer objects")
        for other, oids in self.kinds.items():
            if set(oids) & set(ids):
                _fail(f"objects {kind!r}: ids {sorted(set(oids) & set(ids))} are already {other} ids")
        out = Ids(kind, ids)
        self.kinds[kind] = out
        return out

    def field(self, name, domain, init, over=None, *, source=None, value_sources=None, note=None):
        """One field, or one per object of `over` (read as s[name, obj])."""
        what = f"field {name!r}"
        if not isinstance(name, str) or not name:
            _fail(f"field name must be text, not {name!r}")
        _check_source(source, what)
        _check_note(note, what)
        domain = tuple(domain)
        if not domain:
            _fail(f"{what} has an empty domain")
        value_sources = dict(value_sources or {})
        for v, src in value_sources.items():
            if v not in domain:
                _fail(f"{what}: value_sources names {v!r}, which is not in its domain")
            _check_source(src, f"{what} value {v!r}")
        kind = over.kind if isinstance(over, Ids) else None
        line = _here()[1]
        known = {f.key for f in self.fields}
        for k in ([None] if over is None else list(over)):
            value = init[k] if (isinstance(init, dict) and k is not None) else init
            key = _key(name, k)
            if key in known:
                _fail(f"field {show_key(key)} is declared twice")
            if value not in domain:
                _fail(f"init {value!r} of {show_key(key)} is not in its domain")
            self.fields.append(Field(key, name, k, domain, value, source, value_sources, note, line, kind))

    def action(self, *, source=None, note=None, **params):
        """Decorator: @m.action(t=TOOLS, source="R4") def rent(s, t): need(...); s[...] = ..."""
        _check_source(source, "action")
        _check_note(note, "action")

        def register(fn):
            if not callable(fn) or not hasattr(fn, "__code__"):
                _fail("@m.action(...) decorates a function")
            code = fn.__code__
            names = code.co_varnames[:code.co_argcount]
            for reserved in ("source", "note"):
                if reserved in names:
                    _fail(f"action {fn.__name__}: {reserved!r} is a reserved word, not a parameter name")
            if not code.co_flags & 0x04 and tuple(names[1:]) != tuple(params):
                _fail(f"action {fn.__name__} declares parameters ({', '.join(params)}) but the "
                      f"function takes ({', '.join(names[1:])}) after the state")
            if any(a.name == fn.__name__ for a in self.actions):
                _fail(f"action {fn.__name__} is declared twice")
            self.actions.append(Action(len(self.actions), fn.__name__, tuple(params),
                                       tuple(tuple(v) for v in params.values()), fn, source, note,
                                       code.co_firstlineno))
            self._calls = None
            return fn
        return register

    def option(self, name, offered, action=None, *, source=None, note=None, **params):
        """A screen option: offered(s, *args) says when a screen shows it; when it is
        shown, `action` (default: the same name) must work with the same arguments."""
        what = f"option {name!r}"
        _check_source(source, what)
        _check_note(note, what)
        if not callable(offered):
            _fail(f"{what}: offered must be a function of the state")
        if any(o.name == name for o in self.options):
            _fail(f"{what} is declared twice")
        self.options.append(Option(name, tuple(params), tuple(tuple(v) for v in params.values()),
                                   offered, action or name, source, note, _here()[1]))

    def terminal(self, field, values, *, source=None):
        """The values of field family `field` that end an object's life by design."""
        _check_source(source, f"terminal {field!r}")
        self.terminals[field] = tuple(values)
        self.terminal_sources[field] = source

    def _rule(self, kind, name, base, action=None, pred=None, when=None, goal=None, obj=None,
              source=None, note=None, line=None, over_kind=None):
        what = f"{kind} {base!r}"
        _check_source(source, what)
        _check_note(note, what)
        if any(r.name == name for r in self.rules):
            _fail(f"rule name {name!r} is used twice")
        self.rules.append(Rule(kind, name, base, action, pred, when, goal, obj, source, note,
                               line if line is not None else _here()[1], over_kind))

    def always(self, name, pred, *, source=None, note=None):
        """pred(s) holds in every reachable state."""
        self._rule("always", name, name, pred=pred, source=source, note=note)

    def only_when(self, name, action, pred, *, source=None, note=None):
        """Whenever `action` succeeds, pred(s_before, *args) held before it."""
        self._rule("only_when", name, name, action=action, pred=pred, source=source, note=note)

    def after(self, name, action, pred, *, source=None, note=None):
        """After every success of `action`: pred(before, after, *args); action="*": after
        every step, pred(before, after, action_name, args)."""
        self._rule("after", name, name, action=action, pred=pred, source=source, note=note)

    def progress(self, name, when, goal, over=None, *, source=None, note=None):
        """From every reachable state where when(s[, k]) holds, some path reaches goal(s[, k])."""
        line = _here()[1]
        kind = over.kind if isinstance(over, Ids) else None
        for k in ([None] if over is None else list(over)):
            self._rule("progress", name if k is None else f"{name} [{k}]", name, when=when, goal=goal,
                       obj=k, source=source, note=note, line=line, over_kind=kind)

    def reach(self, name, pred, over=None, *, source=None, note=None):
        """Some reachable state satisfies pred(s[, k])."""
        line = _here()[1]
        kind = over.kind if isinstance(over, Ids) else None
        for k in ([None] if over is None else list(over)):
            self._rule("reach", name if k is None else f"{name} [{k}]", name, pred=pred, obj=k,
                       source=source, note=note, line=line, over_kind=kind)

    def second_route(self, a, b, *, source, why):
        """The only way to keep a second route to the same result: name the request."""
        if not isinstance(source, str) or not source.strip():
            _fail(f"second_route({a!r}, {b!r}): source= must name the request that asks for it")
        if not isinstance(why, str) or not why.strip():
            _fail(f"second_route({a!r}, {b!r}): why= must say why both routes stay")
        if a == b:
            _fail(f"second_route({a!r}, {b!r}): name two different actions")
        self.second_routes.append(SecondRoute((a, b), source, why, _here()[1]))

    # ------------------------------------------------------------------ reading
    def calls(self) -> list[Call]:
        """Every action with every argument, in declaration x product order."""
        if self._calls is None:
            out = []
            for a in self.actions:
                for args in itertools.product(*a.domains):
                    out.append(Call(len(out), a, args))
            self._calls = out
        return self._calls

    def replace_actions(self, actions: list[Action]) -> "Model":
        """A copy of this model with other (for example wrapped) actions."""
        new = copy.copy(self)
        new.actions = list(actions)
        new._calls = None
        return new

    def action_named(self, name) -> Action | None:
        for a in self.actions:
            if a.name == name:
                return a
        return None

    def init_state(self) -> tuple:
        return tuple(f.init for f in self.fields)


def _import_config(spec):
    modname, _, objpath = spec.partition(":")
    try:
        module = importlib.import_module(modname)
    except ImportError as err:
        _fail(f"config {spec!r}: cannot import {modname!r} from the project ({err})")
    obj = module
    for part in objpath.split("."):
        if not hasattr(obj, part):
            _fail(f"config {spec!r}: {modname} has no {objpath!r}")
        obj = getattr(obj, part)
    return obj, getattr(module, "__file__", None)


# ---------------------------------------------------------------------- declaration checks
def validate(model: Model) -> None:
    """Checks that need the whole model (run by the loader after the file ran)."""
    names = {a.name for a in model.actions}
    for o in model.options:
        if o.action not in names:
            raise ModelError(f"option {o.name!r} names action {o.action!r}, which does not exist",
                             _rel(model.path) if model.path else None, o.line)
        params = model.action_named(o.action).params
        if set(o.params) != set(params) or len(o.params) != len(params):
            raise ModelError(f"option {o.name!r} takes ({', '.join(o.params)}) but action {o.action} takes "
                             f"({', '.join(params)}): an option passes its arguments to the action by name",
                             _rel(model.path) if model.path else None, o.line)
    for r in model.rules:
        if r.kind in ("only_when", "after") and r.action != "*" and r.action not in names:
            raise ModelError(f"{r.kind} {r.base!r} names action {r.action!r}, which does not exist",
                             _rel(model.path) if model.path else None, r.line)
    for sr in model.second_routes:
        for a in sr.actions:
            if a not in names:
                raise ModelError(f"second_route names action {a!r}, which does not exist",
                                 _rel(model.path) if model.path else None, sr.line)
    families = {}
    for f in model.fields:
        families.setdefault(f.family, set()).update(f.domain)
    for fam, values in model.terminals.items():
        if fam not in families:
            raise ModelError(f"terminal names field {fam!r}, which does not exist",
                             _rel(model.path) if model.path else None, None)
        bad = [v for v in values if v not in families[fam]]
        if bad:
            raise ModelError(f"terminal {fam!r}: {bad!r} not in the field's domain",
                             _rel(model.path) if model.path else None, None)
    if not model.fields:
        raise ModelError("the model declares no field", _rel(model.path) if model.path else None, None)


def check_covers(model: Model, root: Path, reads: set) -> None:
    """covers= entries must name existing files, classes and methods; each file is a read."""
    for entry in model.covers:
        file, _, inner = entry.partition(":")
        path = root / file
        reads.add(Path(file).as_posix())
        if not path.is_file():
            raise ModelError(f"covers {entry!r}: no file {file!r} in the project",
                             _rel(model.path), model.line)
        if not inner:
            continue
        cls, _, meth = inner.partition(".")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls), None)
        if node is None:
            raise ModelError(f"covers {entry!r}: {file} has no class {cls}", _rel(model.path), model.line)
        if meth and not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == meth
                            for n in node.body):
            raise ModelError(f"covers {entry!r}: class {cls} has no method {meth}", _rel(model.path),
                             model.line)


_SYM_CALLS = {"list", "tuple", "set", "frozenset", "all", "any", "sum", "len"}
_ORDER_CALLS = {"min", "max", "sorted", "enumerate", "zip", "reversed"}


def _is_objects_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "objects")


def _loop_exits(body):
    """True when the loop body (not nested functions or loops) breaks or returns."""
    stack = list(body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(n, ast.Return):
            return True
        if isinstance(n, ast.Break):
            return True
        if isinstance(n, (ast.For, ast.AsyncFor, ast.While)):
            stack.extend(x for x in ast.walk(n) if isinstance(x, ast.Return))
            continue
        stack.extend(ast.iter_child_nodes(n))
    return False


def scalarset_violations(tree: ast.Module, ids: dict, model_file: bool) -> list[tuple[int, str]]:
    """Murphi's scalarset rule on one file: ids of an objects() kind may be used only
    symmetrically. ids: id string -> kind. Returns (line, text) per violation."""
    parent = {}
    allowed_literals = set()
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
        if _is_objects_call(node):
            for a in node.args:
                allowed_literals.add(id(a))
    out = []
    bound = {}                                     # name -> kind
    if model_file:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _is_objects_call(node.value) and node.value.args:
                first = node.value.args[0]
                kind = first.value if isinstance(first, ast.Constant) else "?"
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        bound[t.id] = kind
        changed = True
        while changed:                             # simple aliases: OTHER = TOOLS
            changed = False
            for node in ast.walk(tree):
                if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                        and node.value.id in bound):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id not in bound:
                            bound[t.id] = bound[node.value.id]
                            changed = True
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ids
                and id(node) not in allowed_literals):
            out.append((node.lineno, f"the literal {node.value!r} names one {ids[node.value]} id"))
        if not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in bound):
            continue
        name, kind = node.id, bound[node.id]
        p = parent.get(node)
        problem = None
        if isinstance(p, ast.keyword):
            pass
        elif isinstance(p, ast.BinOp) and isinstance(p.op, ast.Add) and isinstance(
                p.left if p.right is node else p.right, (ast.List, ast.Tuple)):
            pass
        elif isinstance(p, ast.Call) and node in p.args and isinstance(p.func, ast.Name) and p.func.id in _SYM_CALLS:
            pass
        elif isinstance(p, ast.Call) and node in p.args and isinstance(p.func, ast.Name) and p.func.id in _ORDER_CALLS:
            problem = f"{p.func.id}({name}) depends on the order of the {kind} ids"
        elif isinstance(p, ast.comprehension) and p.iter is node:
            pass
        elif isinstance(p, (ast.For, ast.AsyncFor)) and p.iter is node:
            if _loop_exits(p.body):
                problem = f"a loop over {name} that stops early depends on the order of the ids"
        elif isinstance(p, ast.Compare) and node in p.comparators and all(
                isinstance(op, (ast.In, ast.NotIn)) for op in p.ops):
            pass
        elif isinstance(p, ast.Assign) and p.value is node and all(isinstance(t, ast.Name) for t in p.targets):
            pass
        elif isinstance(p, ast.Subscript) and p.value is node:
            problem = f"{name}[...] picks one {kind} id"
        elif isinstance(p, ast.Attribute) and p.value is node:
            problem = f"{name}.{p.attr} depends on the order of the {kind} ids"
        elif isinstance(p, ast.Compare):
            problem = f"compares {name} by order"
        else:
            problem = f"uses {name} in a way that can tell the {kind} ids apart"
        if problem:
            out.append((node.lineno, problem))
    return sorted(set(out))


_ORDER_OPS = (ast.Lt, ast.Gt, ast.LtE, ast.GtE)
_ORDER_FUNCS = {"sorted", "min", "max"}
_TEXT_FUNCS = {"str", "repr", "hash", "ord", "int", "float", "format", "len", "ascii"}
_ALIKE_FUNCS = _SYM_CALLS | {"bool", "isinstance", "need", "enumerate", "zip", "reversed", "iter", "next", "dict"}
_ALIKE_METHODS = {"index", "count", "union", "intersection", "difference", "symmetric_difference", "issubset",
                  "issuperset", "isdisjoint", "get", "keys", "values", "items", "copy"}
_DECLARATIONS = {"action", "option", "progress", "reach", "only_when", "after", "always", "field", "setting",
                 "objects", "terminal", "second_route", "source"}


class _IdUses:
    """Where interchangeable ids flow in a model file and its helpers, beyond the names
    bound to m.objects: action, option and rule parameters whose domain is a kind, loop
    variables over ids, field values that hold ids, and names assigned from them. A use
    that orders or compares them (<, >, sorted, min, max) is a violation; a use the rule
    cannot judge (the id's text, or an id passed to a function the model does not define)
    is a doubt, and a model in doubt is explored without reduction."""

    def __init__(self, trees: list, model: "Model", kinds: dict):
        self.trees = trees                         # (path, tree)
        self.kinds = kinds                         # name bound to m.objects -> kind
        self.ids = {i: k for k, idl in model.kinds.items() for i in idl}
        fam = {}
        for f in model.fields:
            for v in f.domain:
                if isinstance(v, str) and v in self.ids:
                    fam.setdefault(f.family, set()).add(("scalar", self.ids[v]))
                elif isinstance(v, (tuple, frozenset)) and any(isinstance(x, str) and x in self.ids for x in v):
                    kind = next(self.ids[x] for x in v if isinstance(x, str) and x in self.ids)
                    fam.setdefault(f.family, set()).add(("collection", kind))
        self.families = {f: sorted(v)[0] for f, v in fam.items()}    # family -> (shape, kind)
        self.actions = {}                          # action name -> {param: kind}
        self.params = {}                           # id(function node) -> {param: (shape, kind)}
        self.functions = {}                        # helper name -> FunctionDef
        self.violations, self.doubts = [], []

    # -------------------------------------------------------------- which parameters hold ids
    def kind_of(self, node):
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and n.id in self.kinds:
                return self.kinds[n.id]
        return None

    def mark(self, fn, position, shape, kind):
        if fn is None or kind is None:
            return
        args = [a.arg for a in fn.args.args]
        if position < len(args):
            self.params.setdefault(id(fn), {}).setdefault(args[position], (shape, kind))

    def callable_node(self, node):
        if isinstance(node, ast.Lambda):
            return node
        if isinstance(node, ast.Name):
            return self.functions.get(node.id)
        return None

    def declarations(self):
        calls = []
        for path, tree in self.trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self.functions.setdefault(node.name, node)
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "action":
                            kinds = {k.arg: self.kind_of(k.value) for k in dec.keywords
                                     if k.arg not in (None, "source", "note")}
                            self.actions[node.name] = kinds
                            for pos, a in enumerate(node.args.args[1:], 1):
                                if kinds.get(a.arg):
                                    self.mark(node, pos, "scalar", kinds[a.arg])
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    calls.append(node)

        def arg(call, n, name):
            for k in call.keywords:
                if k.arg == name:
                    return k.value
            return call.args[n] if len(call.args) > n else None

        for call in calls:
            what = call.func.attr
            if what == "option":
                fn = self.callable_node(arg(call, 1, "offered"))
                params = [k for k in call.keywords if k.arg not in (None, "action", "source", "note")]
                for pos, k in enumerate(params, 1):
                    self.mark(fn, pos, "scalar", self.kind_of(k.value))
            elif what in ("progress", "reach"):
                over = arg(call, 99, "over")
                kind = self.kind_of(over) if over is not None else None
                for n, name in ((1, "when"), (2, "goal")) if what == "progress" else ((1, "pred"),):
                    self.mark(self.callable_node(arg(call, n, name)), 1, "scalar", kind)
            elif what in ("only_when", "after"):
                action = arg(call, 1, "action")
                fn = self.callable_node(arg(call, 2, "pred"))
                lead = 1 if what == "only_when" else 2
                if isinstance(action, ast.Constant) and action.value == "*":
                    self.mark(fn, 3, "collection", next(iter(self.ids.values()), None))
                elif isinstance(action, ast.Constant) and action.value in self.actions:
                    act = self.functions.get(action.value)
                    names = [a.arg for a in act.args.args[1:]] if act is not None else []
                    for pos, name in enumerate(names, lead):
                        self.mark(fn, pos, "scalar", self.actions[action.value].get(name))

    # -------------------------------------------------------------- what an expression holds
    def shape(self, node, local):
        """("scalar" | "collection", kind) when the expression holds ids, else None."""
        if isinstance(node, ast.Name):
            if node.id in local:
                return local[node.id]
            if node.id in self.kinds:
                return ("collection", self.kinds[node.id])
            return None
        if isinstance(node, ast.Subscript):
            key = node.slice
            first = key.elts[0] if isinstance(key, ast.Tuple) and key.elts else key
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value in self.families:
                return self.families[first.value]
            inner = self.shape(node.value, local)
            if inner is not None and inner[0] == "collection" and not isinstance(node.slice, ast.Slice):
                return ("scalar", inner[1])
            return inner if inner is not None and isinstance(node.slice, ast.Slice) else None
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for e in node.elts:
                sh = self.shape(e, local)
                if sh is not None:
                    return ("collection", sh[1])
            return None
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            sh = self.shape(node.elt, self.comprehension_locals(node, local))
            return ("collection", sh[1]) if sh is not None else None
        if isinstance(node, ast.IfExp):
            return self.shape(node.body, local) or self.shape(node.orelse, local)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.BitOr, ast.Sub, ast.BitAnd)):
            left, right = self.shape(node.left, local), self.shape(node.right, local)
            both = [x for x in (left, right) if x is not None and x[0] == "collection"]
            return both[0] if both else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
                "tuple", "list", "set", "frozenset", "sorted", "reversed"):
            return self.shape(node.args[0], local) if node.args else None
        return None

    def comprehension_locals(self, node, local):
        local = dict(local)
        for gen in node.generators:
            sh = self.shape(gen.iter, local)
            if sh is not None and sh[0] == "collection" and isinstance(gen.target, ast.Name):
                local[gen.target.id] = ("scalar", sh[1])
        return local

    def scope_locals(self, fn):
        local = dict(self.params.get(id(fn), {}))
        body = fn.body if isinstance(fn.body, list) else [fn.body]
        changed = True
        while changed:
            changed = False
            for stmt in body:
                for node in ast.walk(stmt):
                    targets = []
                    if isinstance(node, (ast.For, ast.AsyncFor)):
                        sh = self.shape(node.iter, local)
                        if sh is not None and sh[0] == "collection":
                            targets.append((node.target, ("scalar", sh[1])))
                    elif isinstance(node, ast.comprehension):
                        sh = self.shape(node.iter, local)
                        if sh is not None and sh[0] == "collection":
                            targets.append((node.target, ("scalar", sh[1])))
                    elif isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                                targets += list(zip(t.elts, [self.shape(v, local) for v in node.value.elts]))
                            else:
                                targets.append((t, self.shape(node.value, local)))
                    for t, sh in targets:
                        if isinstance(t, ast.Name) and sh is not None and t.id not in local:
                            local[t.id] = sh
                            changed = True
        return local

    # -------------------------------------------------------------- uses
    def scopes(self):
        for path, tree in self.trees:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    yield path, node
            yield path, tree

    def run(self):
        self.declarations()
        for _ in range(4):                         # helpers called with ids: parameters hold ids too
            before = {k: dict(v) for k, v in self.params.items()}
            for path, fn in self.scopes():
                self.uses(path, fn, propagate_only=True)
            if before == self.params:
                break
        for path, fn in self.scopes():
            self.uses(path, fn)
        return self.violations, self.doubts

    def uses(self, path, fn, propagate_only=False):
        if isinstance(fn, ast.Module):
            local = {}
            body = [n for n in fn.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        else:
            local = self.scope_locals(fn)
            body = fn.body if isinstance(fn.body, list) else [fn.body]
        for stmt in body:
            for node in ast.walk(stmt):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn:
                    continue
                if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
                    inner = self.comprehension_locals(node, local)
                    for elt in ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]) + [
                            c for g in node.generators for c in g.ifs]:
                        for sub in ast.walk(elt):
                            self.use(path, sub, inner, propagate_only)
                    continue
                self.use(path, node, local, propagate_only)

    def use(self, path, node, local, propagate_only):
        if isinstance(node, ast.Call):
            self.call(path, node, local, propagate_only)
            return
        if propagate_only:
            return
        if isinstance(node, ast.Compare):
            items = [node.left] + list(node.comparators)
            for op, a, b in zip(node.ops, items, items[1:]):
                sh = self.shape(a, local) or self.shape(b, local)
                if isinstance(op, _ORDER_OPS) and sh is not None:
                    self.violations.append((path, node.lineno, f"compares {sh[1]} ids by order"))
        elif isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Store):
            sh = self.shape(node.value, local)
            if sh is not None and sh[0] == "scalar":
                self.doubts.append((path, node.lineno, f"uses the text of a {sh[1]} id (.{node.attr})"))
        elif isinstance(node, ast.Subscript):
            sh = self.shape(node.value, local)
            if sh is not None and sh[0] == "scalar" and not isinstance(node.value, ast.Subscript):
                self.doubts.append((path, node.lineno, f"uses the text of a {sh[1]} id ([...])"))
        elif isinstance(node, ast.FormattedValue):
            sh = self.shape(node.value, local)
            if sh is not None:
                self.doubts.append((path, node.lineno, f"writes a {sh[1]} id into text"))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            for side, other in ((node.left, node.right), (node.right, node.left)):
                sh = self.shape(side, local)
                if sh is not None and sh[0] == "scalar" and isinstance(other, (ast.Constant, ast.JoinedStr)):
                    self.doubts.append((path, node.lineno, f"uses the text of a {sh[1]} id ({type(node.op).__name__})"))
                    break

    def call(self, path, node, local, propagate_only):
        func = node.func
        args = list(node.args) + [k.value for k in node.keywords]
        held = [(n, self.shape(a, local)) for n, a in enumerate(args)]
        held = [(n, sh) for n, sh in held if sh is not None]
        if isinstance(func, ast.Name) and func.id in self.functions:
            fn = self.functions[func.id]
            for n, sh in held:
                if n < len(node.args):
                    self.mark(fn, n, sh[0], sh[1])
            return
        if propagate_only or not held:
            return
        if isinstance(func, ast.Name):
            if func.id in _ORDER_FUNCS:
                self.violations.append((path, node.lineno, f"{func.id}(...) orders {held[0][1][1]} ids"))
            elif func.id in _TEXT_FUNCS and any(sh[0] == "scalar" for _, sh in held):
                self.doubts.append((path, node.lineno, f"uses the text of a {held[0][1][1]} id ({func.id}())"))
            elif func.id not in _ALIKE_FUNCS:
                self.doubts.append((path, node.lineno, f"passes a {held[0][1][1]} id to {func.id}()"))
        elif isinstance(func, ast.Attribute):
            owner = self.shape(func.value, local)
            if func.attr in _DECLARATIONS or func.attr in _ALIKE_METHODS and (owner is None or owner[0] == "collection"):
                return
            self.doubts.append((path, node.lineno, f"passes a {held[0][1][1]} id to .{func.attr}()"))
        else:
            self.doubts.append((path, node.lineno, f"passes a {held[0][1][1]} id to a computed function"))


def check_symmetry_rule(model: Model, files: list[Path], root: Path) -> None:
    """The scalarset rule on the model file and its helpers: an asymmetric use is a model
    error; a use the rule cannot judge records a doubt (model._symmetry_doubt), and the
    model is then explored without reduction (explore.Symmetry.of)."""
    if not model.kinds:
        return
    ids = {i: kind for kind, idl in model.kinds.items() for i in idl}
    trees, bound = [], {}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        trees.append((path, tree))
        bad = scalarset_violations(tree, ids, model_file=(path == model.path))
        if bad:
            line, text = bad[0]
            kind = next(iter(model.kinds))
            raise ModelError(f"treats {kind} ids asymmetrically ({text}); write it symmetrically "
                             f"or use a plain list", _rel(path), line)
        if path == model.path:
            bound = _bound_kinds(tree)
    violations, doubts = _IdUses(trees, model, bound).run()
    if violations:
        path, line, text = min(violations, key=lambda v: (str(v[0]), v[1]))
        kind = text.split(" ids", 1)[0].rsplit(" ", 1)[-1]
        raise ModelError(f"treats {kind} ids asymmetrically ({text}); write it symmetrically "
                         f"or use a plain list", _rel(path), line)
    if doubts:
        path, line, text = min(doubts, key=lambda v: (str(v[0]), v[1]))
        more = f" and {len(doubts) - 1} more" if len(doubts) > 1 else ""
        model.__dict__["_symmetry_doubt"] = f"{_rel(path)}:{line} {text}{more}"


def _bound_kinds(tree) -> dict:
    """Names bound to m.objects(...) in the model file (and simple aliases) -> kind."""
    bound = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_objects_call(node.value) and node.value.args:
            first = node.value.args[0]
            kind = first.value if isinstance(first, ast.Constant) else "?"
            for t in node.targets:
                if isinstance(t, ast.Name):
                    bound[t.id] = kind
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in bound:
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in bound:
                        bound[t.id] = bound[node.value.id]
                        changed = True
    return bound


# ---------------------------------------------------------------------- loading
@dataclass(frozen=True)
class Loaded:
    model: Model
    reads: tuple          # files under the root the load read (posix, relative to the root)


_COUNTER = itertools.count()


def _engine_module(name):
    return name == _PKG_NAME or name.startswith(_PKG_NAME + ".") or _PKG_NAME.startswith(name + ".")


def _module_file_under(mod, root):
    f = getattr(mod, "__file__", None)
    if not f:
        return None
    p = Path(os.path.abspath(f))
    try:
        rel = p.relative_to(root)
    except ValueError:
        return None
    if {"site-packages", "dist-packages"} & set(rel.parts):
        return None
    return rel.as_posix()


def _project_modules(root):
    out = {}
    for name, mod in list(sys.modules.items()):
        if mod is None or _engine_module(name):
            continue
        rel = _module_file_under(mod, root)
        if rel is not None:
            out[name] = rel
    return out


def _error_location(err, root):
    tb = err.__traceback__
    best = None
    while tb is not None:
        fn = os.path.abspath(tb.tb_frame.f_code.co_filename)
        if os.path.dirname(fn) != _PKG_DIR:
            best = (fn, tb.tb_lineno)
        tb = tb.tb_next
    if best is None:
        return None, None
    try:
        return Path(best[0]).relative_to(root).as_posix(), best[1]
    except ValueError:
        return best[0], best[1]


def load_model(path: Path, root: Path, transform: Callable[[ast.Module], ast.Module] | None = None) -> Loaded:
    """Run a model file as a fresh module and return its MODEL with every project file
    the load read. transform (routes, mutation) rewrites the model file's AST only."""
    path = Path(path).resolve()
    root = Path(root).resolve()
    for name in _project_modules(root):            # project modules are imported fresh
        del sys.modules[name]
    added = [str(root), str(path.parent)]
    sys.path[:0] = added
    modname = f"_flowguard_model_{path.stem}_{next(_COUNTER)}"
    module = types.ModuleType(modname)
    module.__file__ = str(path)
    old_root = _LOAD["root"]
    _LOAD["root"] = root
    rel_model = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    reads = {rel_model}
    try:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as err:
            raise ModelError(f"syntax error: {err.msg}", rel_model, err.lineno) from None
        if transform is not None:
            tree = ast.fix_missing_locations(transform(tree))
        code = compile(tree, str(path), "exec")
        sys.modules[modname] = module
        try:
            exec(code, module.__dict__)
        except ModelError:
            raise
        except Exception as err:  # model code: reported with its location, never swallowed
            file, line = _error_location(err, root)
            raise ModelError(f"loading raised {type(err).__name__}: {err}", file, line) from err
        if "MODEL" not in module.__dict__:
            old = [n for n in ("MACHINE", "MACHINES") if n in module.__dict__]
            hint = f" ({old[0]} is not read: write MODEL = m)" if old else ""
            raise ModelError(f"the file defines no MODEL{hint}", rel_model, None)
        model = module.__dict__["MODEL"]
        if not isinstance(model, Model):
            raise ModelError(f"MODEL is a {type(model).__name__}, not a Model", rel_model, None)
        model.id = path.stem
        model.path = path
        model.root = root
        project = _project_modules(root)
        reads.update(project.values())
        validate(model)
        check_covers(model, root, reads)
        helpers = [root / r for r in project.values()
                   if (root / r).parent == path.parent and Path(r).name.startswith("_")]
        check_symmetry_rule(model, [path] + sorted(helpers), root)
        from .explore import Symmetry               # start state and domains under renaming
        Symmetry.of(model)
        return Loaded(model, tuple(sorted(reads)))
    except ModelError as err:
        err.reads = tuple(sorted(reads | set(_project_modules(root).values())))
        raise
    finally:
        _LOAD["root"] = old_root
        for p in added:
            if p in sys.path:
                sys.path.remove(p)
        sys.modules.pop(modname, None)
        for name in _project_modules(root):
            del sys.modules[name]
