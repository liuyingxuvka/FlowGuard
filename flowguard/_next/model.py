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


REQUESTS = Path(".flowguard") / "requests"
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def request_file(root, rid) -> Path | None:
    """The file of a stored request: .flowguard/requests/<id>.md. None when rid is no
    request id (empty, a path, a space): an id never reaches another file."""
    if not isinstance(rid, str) or not _REQUEST_ID.fullmatch(rid) or ".." in rid:
        return None
    return Path(root) / REQUESTS / f"{rid}.md"


def check_second_routes(model: Model, root: Path, reads: set) -> None:
    """m.second_route keeps a second route only for a request the owner stored: its
    source= must be the id of a file in .flowguard/requests/. The file is a read either
    way, so storing it later makes the model's parts run again."""
    for sr in model.second_routes:
        if request_file(root, sr.source) is None:
            a, b = sr.actions
            raise ModelError(f"second_route({a!r}, {b!r}): source {sr.source!r} is no request id (the name of a "
                             f"file in {REQUESTS.as_posix()}/, such as R11)", _rel(model.path), sr.line)
        rel = (REQUESTS / f"{sr.source}.md").as_posix()
        reads.add(rel)
        if not (root / rel).is_file():
            a, b = sr.actions
            raise ModelError(f"second_route({a!r}, {b!r}): source {sr.source!r} is no stored request ({rel}); "
                             f"a second route stays only when a stored owner request asks for it",
                             _rel(model.path), sr.line)


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
_ALIKE_FUNCS = {"all", "any", "sum", "len", "set", "frozenset", "bool", "isinstance", "need", "list", "tuple",
                "reversed", "iter"}
_SET_METHODS = {"union", "intersection", "difference", "symmetric_difference", "issubset", "issuperset",
                "isdisjoint"}
_DECLARATIONS = {"action", "option", "progress", "reach", "only_when", "after", "always", "field", "setting",
                 "objects", "terminal", "second_route", "source"}
# What an expression holding ids is (its form) decides which uses treat the ids alike:
#   scalar     one id                          record   a tuple holding ids at data positions
#   kindlist   ids in the declared order       kindrecs records in an order taken from it
#   kindvals   other values in that order      unordered a set of ids (iteration follows hashes)
#   sequence   ids in data order (a field value that is a tuple)
#   table      a mapping keyed by ids, built over all of them
_COLLECTIONS = {"kindlist", "kindrecs", "kindvals", "unordered", "sequence", "record", "table"}
_BY_KIND = {"kindlist", "kindrecs", "kindvals", "unordered", "table"}     # their order is no data
_TRANSPARENT = (ast.Tuple, ast.List, ast.Set, ast.IfExp, ast.Starred)
_DYNAMIC = {"eval", "exec", "compile", "globals", "locals", "vars", "getattr", "setattr", "delattr", "__import__"}
_STATE = ("state", None)                  # the model state an action or rule receives


def _element(form):
    """What iterating over a collection of this form yields."""
    return {"kindrecs": "record", "kindvals": None}.get(form, "scalar")


def _whole_step(step) -> bool:
    """Whether a slice step keeps every item ([:], [::1], [::-1]); any other step, or one the
    rule cannot read, picks items by their place."""
    if step is None:
        return True
    if isinstance(step, ast.UnaryOp) and isinstance(step.op, ast.USub) and isinstance(step.operand, ast.Constant):
        return step.operand.value == 1
    return isinstance(step, ast.Constant) and step.value in (1, -1)


def _target_names(target) -> list[str]:
    """The names an assignment target binds."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for x in target.elts for n in _target_names(x)]
    return []


def _binds(scope, name) -> bool:
    """Whether a function, lambda or comprehension binds name itself (a parameter, an
    assignment of its own, a comprehension target): then name there is not the outer one."""
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = scope.args
        params = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs] + \
                 [a.arg for a in (args.vararg, args.kwarg) if a is not None]
        if name in params:
            return True
        body = scope.body if isinstance(scope.body, list) else [scope.body]
        return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)
                   for stmt in body for n in ast.walk(stmt))
    return any(name in _target_names(g.target) for g in scope.generators)


def _reads_outside(scope, loop, name) -> bool:
    """Whether name is read in scope outside the loop (nested scopes that bind name
    themselves read their own)."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        n = stack.pop()
        if n is loop:
            continue
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.GeneratorExp, ast.ListComp,
                          ast.SetComp, ast.DictComp)) and _binds(n, name):
            continue
        if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load):
            return True
        stack.extend(ast.iter_child_nodes(n))
    return False


def _spread(form):
    """The form of a display that spreads a collection of this form (`[*IDS]`): its items in
    the order of the ids."""
    return {"kindrecs": "kindrecs", "kindvals": "kindvals"}.get(form, "kindlist")


class _IdUses:
    """Where interchangeable ids flow in a model file and its helpers, beyond the names
    bound to m.objects: action, option and rule parameters whose domain holds ids (a kind,
    a copy of it, or values built from it such as pairs), loop variables, field values that
    hold ids, module-level and local names assigned from any of these, and what helpers
    return. Every expression that holds ids is judged by where it is used (a whitelist):
    ordering ids, picking one by its place in the declared order (or in a set), or a loop
    over them that stops early is a violation; a use the rule cannot judge (the id's text,
    a table built from their order, a function the model does not define) is a doubt, and
    a model in doubt is explored without reduction."""

    def __init__(self, trees: list, model: "Model", kinds: dict):
        self.trees = trees                         # (path, tree)
        self.kinds = kinds                         # name bound to m.objects -> kind
        self.ids = {i: k for k, idl in model.kinds.items() for i in idl}
        self.all_families = {f.family for f in model.fields}
        fam = {}
        for f in model.fields:
            for v in f.domain:
                if isinstance(v, str) and v in self.ids:
                    fam.setdefault(f.family, set()).add(("scalar", self.ids[v]))
                elif isinstance(v, (tuple, frozenset)) and any(isinstance(x, str) and x in self.ids for x in v):
                    kind = next(self.ids[x] for x in v if isinstance(x, str) and x in self.ids)
                    fam.setdefault(f.family, set()).add(("unordered" if isinstance(v, frozenset) else "sequence",
                                                         kind))
        self.families = {f: sorted(v)[0] for f, v in fam.items()}    # family -> (form, kind)
        self.over = {f.family: f.kind for f in model.fields if f.kind}  # family -> kind of the ids it is over
        self.actions = {}                          # action name -> {param: (form, kind)}
        self.params = {}                           # id(function node) -> {param: (form, kind)}
        self.returns = {}                          # helper name -> (form, kind) of what it returns
        self.functions = {}                        # helper name -> FunctionDef
        self.parents = {}                          # id(node) -> parent node
        self.modules = {}                          # path -> module-level names holding ids
        self.enclosing = {}                        # id(function node) -> enclosing function node
        self.violations, self.doubts = [], []
        for path, tree in trees:
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    self.parents[id(child)] = node

    # -------------------------------------------------------------- which parameters hold ids
    def domain(self, node, env):
        """(form, kind) of one value of a declared domain (an action parameter's, an over=)."""
        sh = self.shape(node, env)
        if sh is None or sh[0] not in _COLLECTIONS:
            return None
        form = _element(sh[0])
        return (form, sh[1]) if form is not None else None

    def mark(self, fn, position, sh):
        if fn is None or sh is None:
            return
        args = [a.arg for a in fn.args.args]
        if position < len(args):
            self.params.setdefault(id(fn), {}).setdefault(args[position], sh)

    def callable_node(self, node):
        if isinstance(node, ast.Lambda):
            return node
        if isinstance(node, ast.Name):
            return self.functions.get(node.id)
        return None

    def module_env(self, path):
        env = self.modules.get(path)
        if env is None:
            env = self.modules[path] = {}
            tree = dict(self.trees)[path]
            body = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            for node in body:                      # names imported from a helper that hold ids there
                if isinstance(node, ast.ImportFrom) and node.module:
                    for other, _ in self.trees:
                        if other != path and other.stem == node.module.split(".")[-1]:
                            theirs = self.module_env(other)
                            for alias in node.names:
                                if alias.name in theirs:
                                    env[alias.asname or alias.name] = theirs[alias.name]
            self.bind(body, env, keep=set(env))
        return env

    def declarations(self):
        calls = []
        for path, tree in self.trees:
            env = self.module_env(path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.functions.setdefault(node.name, node)
                    up = self.parents.get(id(node))
                    while up is not None and not isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                        up = self.parents.get(id(up))
                    if up is not None:
                        self.enclosing[id(node)] = up
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "action":
                            kinds = {k.arg: self.domain(k.value, env) for k in dec.keywords
                                     if k.arg not in (None, "source", "note")}
                            self.actions[node.name] = kinds
                            self.mark(node, 0, _STATE)
                            for pos, a in enumerate(node.args.args[1:], 1):
                                self.mark(node, pos, kinds.get(a.arg))
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    calls.append((node, env))

        def arg(call, n, name):
            for k in call.keywords:
                if k.arg == name:
                    return k.value
            return call.args[n] if len(call.args) > n else None

        for call, env in calls:
            what = call.func.attr
            if what == "always":
                self.mark(self.callable_node(arg(call, 1, "pred")), 0, _STATE)
            if what == "option":
                fn = self.callable_node(arg(call, 1, "offered"))
                self.mark(fn, 0, _STATE)
                params = [k for k in call.keywords if k.arg not in (None, "action", "source", "note")]
                for pos, k in enumerate(params, 1):
                    self.mark(fn, pos, self.domain(k.value, env))
            elif what in ("progress", "reach"):
                over = arg(call, 99, "over")
                sh = self.domain(over, env) if over is not None else None
                for n, name in ((1, "when"), (2, "goal")) if what == "progress" else ((1, "pred"),):
                    self.mark(self.callable_node(arg(call, n, name)), 0, _STATE)
                    self.mark(self.callable_node(arg(call, n, name)), 1, sh)
            elif what in ("only_when", "after"):
                action = arg(call, 1, "action")
                fn = self.callable_node(arg(call, 2, "pred"))
                lead = 1 if what == "only_when" else 2
                for pos in range(lead):
                    self.mark(fn, pos, _STATE)
                if isinstance(action, ast.Constant) and action.value == "*":
                    self.mark(fn, 3, ("record", next(iter(self.ids.values()), None)) if self.ids else None)
                elif isinstance(action, ast.Constant) and action.value in self.actions:
                    act = self.functions.get(action.value)
                    names = [a.arg for a in act.args.args[1:]] if act is not None else []
                    for pos, name in enumerate(names, lead):
                        self.mark(fn, pos, self.actions[action.value].get(name))

    # -------------------------------------------------------------- what an expression holds
    def state_access(self, node):
        """s["field", ...] or s["field"]: a read or write of the model's state."""
        key = node.slice
        first = key.elts[0] if isinstance(key, ast.Tuple) and key.elts else key
        return isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value in self.all_families

    def shape(self, node, env):
        """(form, kind) when the expression holds ids (or values ordered by them), else None."""
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in self.kinds:
                return ("kindlist", self.kinds[node.id])
            return None
        if isinstance(node, ast.Subscript):
            if self.state_access(node):
                key = node.slice
                first = key.elts[0] if isinstance(key, ast.Tuple) else key
                return self.families.get(first.value)
            inner = self.shape(node.value, env)
            if inner is None or inner[0] not in _COLLECTIONS:
                return None
            if isinstance(node.slice, ast.Slice):
                return inner
            if inner[0] == "table":
                return None
            form = _element(inner[0])
            return (form, inner[1]) if form is not None else None
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for e in node.elts:                    # [*IDS]: the ids in the order they are spread
                inner = self.shape(e.value, env) if isinstance(e, ast.Starred) else None
                if inner is not None and inner[0] in _BY_KIND:
                    if isinstance(node, ast.Set):
                        return ("unordered", inner[1])
                    return (_spread(inner[0]), inner[1])
            for e in node.elts:
                sh = self.shape(e, env)
                if sh is not None:
                    return ({ast.Tuple: "record", ast.List: "sequence", ast.Set: "unordered"}[type(node)], sh[1])
            return None
        if isinstance(node, ast.NamedExpr):
            return self.shape(node.value, env)
        if isinstance(node, ast.Starred):
            return self.shape(node.value, env)
        if isinstance(node, ast.Dict):
            for k in node.keys:
                sh = self.shape(k, env) if k is not None else None
                if sh is not None:
                    return ("table", sh[1])
            return None
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            inner = self.comprehension_locals(node, env)
            iters = [self.shape(g.iter, env if n == 0 else inner) for n, g in enumerate(node.generators)]
            by_kind = next((sh for sh in iters if sh is not None and sh[0] in _BY_KIND), None)
            if isinstance(node, ast.DictComp):
                key = self.shape(node.key, inner)
                return ("table", key[1]) if key is not None else (("kindvals", by_kind[1]) if by_kind else None)
            elt = self.shape(node.elt, inner)
            if isinstance(node, ast.SetComp):
                return ("unordered", elt[1]) if elt is not None else None
            if by_kind is not None:
                if elt is None:
                    return ("kindvals", by_kind[1])
                return ("kindrecs" if elt[0] in ("record", "sequence") else "kindlist", elt[1])
            return ("sequence", elt[1]) if elt is not None else None
        if isinstance(node, ast.IfExp):
            return self.shape(node.body, env) or self.shape(node.orelse, env)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.BitOr, ast.Sub, ast.BitAnd)):
            sides = [x for x in (self.shape(node.left, env), self.shape(node.right, env)) if x is not None]
            if not sides:
                return None
            if not isinstance(node.op, ast.Add):
                return ("unordered", sides[0][1])
            return next((x for x in sides if x[0] in _BY_KIND), sides[0])
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in ("tuple", "list", "reversed", "iter", "sorted") and node.args:
                    inner = self.shape(node.args[0], env)
                    return ("kindlist", inner[1]) if inner is not None and inner[0] == "table" else inner
                if func.id == "sum" and node.args:         # sum of lists: their items, in the order of the ids
                    inner = self.shape(node.args[0], env)
                    return ("kindlist", inner[1]) if inner is not None and inner[0] == "kindrecs" else None
                if func.id in ("set", "frozenset") and node.args:
                    sh = self.shape(node.args[0], env)
                    if sh is None:
                        return None
                    return ("unordered", sh[1]) if _element(sh[0]) is not None else sh
                if func.id in self.returns:
                    return self.returns[func.id]
                return None
            if isinstance(func, ast.Attribute):
                owner = self.shape(func.value, env)
                if owner is None:
                    return None
                if owner[0] == "table" and func.attr in ("keys", "values", "items"):
                    return ({"keys": "kindlist", "values": "kindvals", "items": "kindrecs"}[func.attr], owner[1])
                if func.attr == "copy" or func.attr in _SET_METHODS:
                    return owner if func.attr == "copy" else ("unordered", owner[1])
            return None
        return None

    def comprehension_locals(self, node, env):
        """The names a comprehension binds, over the enclosing ones (its targets shadow them;
        a target over a value the rule cannot follow holds nothing it follows)."""
        env = dict(env)
        for gen in node.generators:
            sh = self.shape(gen.iter, env)
            el = (_element(sh[0]), sh[1]) if sh is not None and sh[0] in _COLLECTIONS and _element(sh[0]) else None
            for name in _target_names(gen.target):
                env.pop(name, None)
            self.bind_target(gen.target, el, env)
        return env

    def bind_target(self, target, sh, env):
        if sh is None:
            return False
        if isinstance(target, ast.Name):
            if target.id not in env:
                env[target.id] = sh
                return True
            return False
        if isinstance(target, (ast.Tuple, ast.List)):     # unpacking a record: each part may be an id
            return any([self.bind_target(t, ("scalar", sh[1]), env) for t in target.elts])
        return False

    def sites(self, body):
        """(target, value, kind) for every binding a block makes in its own scope: kind "value"
        (an assignment; value None when the rule cannot know it: +=, with, except, import),
        "iter" (a loop over value). Nested functions, lambdas, classes and comprehensions
        have their own names (a walrus in a comprehension is judged where it stands)."""
        out = []
        stack = list(body)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append((ast.Name(id=node.name, ctx=ast.Store()), None, "value"))
                stack.extend(node.decorator_list)
                continue
            if isinstance(node, (ast.Lambda, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
                continue
            if isinstance(node, (ast.For, ast.AsyncFor)):
                out.append((node.target, node.iter, "iter"))
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                if _is_objects_call(node.value):
                    continue                       # TOOLS = m.objects(...): the kind itself (self.kinds)
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List)) \
                            and len(target.elts) == len(node.value.elts) \
                            and not any(isinstance(x, ast.Starred) for x in target.elts + node.value.elts):
                        out += [(x, y, "value") for x, y in zip(target.elts, node.value.elts)]
                    else:
                        out.append((target, node.value, "value"))
            elif isinstance(node, ast.AugAssign):
                out.append((node.target, None, "value"))
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                out += [(item.optional_vars, None, "value") for item in node.items if item.optional_vars is not None]
            elif isinstance(node, ast.ExceptHandler) and node.name:
                out.append((ast.Name(id=node.name, ctx=ast.Store()), None, "value"))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                out += [(ast.Name(id=(a.asname or a.name).split(".")[0], ctx=ast.Store()), None, "value")
                        for a in node.names]
            stack.extend(ast.iter_child_nodes(node))
        return out

    def bind(self, body, env, keep=()):
        """The names a block binds in its own scope, to a fixpoint. A name holds what every
        binding of it holds (a constant such as None adds nothing); one binding the rule
        cannot follow (text made into an id, a value from code it does not read) and the name
        holds nothing it follows, so its uses as an id are judged in doubt. keep: names whose
        entry in env is one of their bindings (the parameters, the names imported from a
        helper); every other name the block binds is the block's own."""
        sites = self.sites(body)
        own = {n for target, _, _ in sites for n in _target_names(target)}
        start = {n: env[n] for n in own if n in keep and n in env}
        for n in own:
            env.pop(n, None)
        env.update(start)
        for _ in range(12):
            seen = {n: ([start[n]] if n in start else []) for n in own}
            for target, value, kind in sites:
                if kind == "iter":
                    sh = self.shape(value, env)
                    el = ((_element(sh[0]), sh[1]) if sh is not None and sh[0] in _COLLECTIONS and _element(sh[0])
                          else None)
                    self._collect(target, el, seen, constant=False)
                else:
                    constant = isinstance(value, ast.Constant)
                    self._collect(target, None if value is None else self.shape(value, env), seen, constant)
            new = {}
            for n, shapes in seen.items():
                if shapes and all(s is not None and s == shapes[0] for s in shapes):
                    new[n] = shapes[0]
                elif shapes:
                    new[n] = None                  # bound to something the rule does not follow
            if all(env.get(n, "absent") == new.get(n, "absent") for n in own):
                break
            for n in own:
                env.pop(n, None)
            env.update(new)

    @staticmethod
    def _collect(target, sh, seen, constant):
        """The shape a binding gives each name of its target (constants add nothing)."""
        if isinstance(target, ast.Name):
            if not constant:
                seen.setdefault(target.id, []).append(sh)
        elif isinstance(target, (ast.Tuple, ast.List)):
            part = ("scalar", sh[1]) if sh is not None else None     # unpacking: each part may be an id
            for x in target.elts:
                _IdUses._collect(x.value if isinstance(x, ast.Starred) else x, part, seen, constant)
        elif isinstance(target, ast.Starred):
            _IdUses._collect(target.value, sh, seen, constant)

    def scope_env(self, path, fn):
        up = self.enclosing.get(id(fn))
        env = dict(self.scope_env(path, up)) if up is not None else dict(self.module_env(path))
        args = fn.args
        names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs] + \
                [a.arg for a in (args.vararg, args.kwarg) if a is not None]
        for name in names:
            env.pop(name, None)                    # a parameter shadows an outer name
        env.update(self.params.get(id(fn), {}))
        self.bind(fn.body if isinstance(fn.body, list) else [fn.body], env, keep=set(names))
        return env

    # -------------------------------------------------------------- uses
    def scopes(self):
        """Every function, lambda and module body that can run: a def that nothing names and
        no decorator registers never runs, so its parameters are not judged."""
        named = {n.id for _, tree in self.trees for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        named |= {n.attr for _, tree in self.trees for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for path, tree in self.trees:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.decorator_list or node.name in named:
                        yield path, node
                elif isinstance(node, ast.Lambda):
                    yield path, node
            yield path, tree

    def run(self):
        for _ in range(6):                         # helpers called with ids: parameters and returns hold ids
            before = ({k: dict(v) for k, v in self.params.items()}, dict(self.returns))
            self.modules = {}                      # module names may hold what a helper returns
            self.declarations()
            for path, fn in self.scopes():
                self.uses(path, fn, propagate_only=True)
            if before == (self.params, self.returns):
                break
        for path, fn in self.scopes():
            self.uses(path, fn)
        return self.violations, self.doubts

    def uses(self, path, fn, propagate_only=False):
        if isinstance(fn, ast.Module):
            env = self.module_env(path)
            body = fn.body
        else:
            env = self.scope_env(path, fn)
            body = fn.body if isinstance(fn.body, list) else [fn.body]
        for stmt in body:
            self.visit(path, stmt, env, propagate_only)

    def visit(self, path, node, env, propagate_only):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:        # the declaration is code of the enclosing scope
                self.visit(path, dec, env, propagate_only)
            return                                 # the body is its own scope
        if isinstance(node, ast.Lambda):
            return
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                self.visit(path, stmt, env, propagate_only)
            return
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            inner = self.comprehension_locals(node, env)
            for n, gen in enumerate(node.generators):
                self.visit(path, gen.iter, env if n == 0 else inner, propagate_only)
                for cond in gen.ifs:
                    self.visit(path, cond, inner, propagate_only)
            for part in ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]):
                self.visit(path, part, inner, propagate_only)
        else:
            for child in ast.iter_child_nodes(node):
                self.visit(path, child, env, propagate_only)
        if isinstance(node, ast.Return) and node.value is not None:
            fn = self.function_of(node)
            sh = self.shape(node.value, env)
            if fn is not None and sh is not None and isinstance(fn, ast.FunctionDef):
                self.returns.setdefault(fn.name, sh)
        if isinstance(node, ast.Call):
            self.propagate(node, env)
        if not propagate_only and self.ids:
            self.judge_code(path, node, env)
        if propagate_only or not isinstance(node, ast.expr):
            return
        if isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del)):
            return
        sh = self.shape(node, env)
        if sh is not None:
            self.judge(path, node, sh, env)

    def judge_code(self, path, node, env):
        """Dynamic code, and a write of a value the rule cannot follow into a field that
        holds ids (an id made from text): both can tell the ids apart unseen."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _DYNAMIC:
            self.doubts.append((path, node.lineno, f"runs code the rule cannot follow ({node.func.id}())"))
        if isinstance(node, ast.Assign) and not isinstance(node.value, (ast.Tuple, ast.List)):
            sh = self.shape(node.value, env)
            if sh is not None and sh[0] in _BY_KIND and any(isinstance(x, (ast.Tuple, ast.List)) for x in node.targets):
                self.violations.append((path, node.lineno, f"unpacking {sh[1]} ids gives each name the id of one "
                                                           f"place in the declared order", sh[1]))
        if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, (ast.Tuple, ast.List)):
            sh = self.shape(node.iter, env)
            if sh is not None and sh[0] in _COLLECTIONS and _element(sh[0]) == "scalar":
                self.doubts.append((path, node.lineno, f"unpacks the text of a {sh[1]} id"))
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self.judge_loop_keeps(path, node, env)
        if isinstance(node, ast.NamedExpr) and self.in_comprehension(node):
            sh = self.shape(node.value, env)
            if sh is not None:
                self.violations.append((path, node.lineno, f"':=' inside a comprehension over {sh[1]} ids keeps "
                                                           f"the id of one place in the declared order", sh[1]))
        pairs = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List)):
                    pairs += list(zip(target.elts, node.value.elts))
                elif isinstance(target, (ast.Tuple, ast.List)):
                    pairs += [(x, None) for x in target.elts]
                else:
                    pairs.append((target, node.value))
        elif isinstance(node, ast.AugAssign):
            pairs.append((node.target, None))
        for target, value in pairs:
            if not (isinstance(target, ast.Subscript) and self.state_access(target)):
                continue
            key = target.slice
            family = (key.elts[0] if isinstance(key, ast.Tuple) else key).value
            if family in self.families and (value is None or not self.followed(value, env)):
                self.doubts.append((path, node.lineno, f"writes a value the rule cannot follow into {family!r}, "
                                                       f"which holds {self.families[family][1]} ids"))

    def judge_loop_keeps(self, path, loop, env):
        """A loop over ids in their declared order (or a set's) whose variable, or a name it
        sets to an id inside the loop, is read after the loop keeps the id of one place: the
        last one, or the last that met a condition."""
        sh = self.shape(loop.iter, env)
        if sh is None or sh[0] not in _BY_KIND or _element(sh[0]) is None or _loop_exits(loop.body):
            return                                 # a loop that stops early is judged as such (judge)
        inner = dict(env)
        for name in _target_names(loop.target):
            inner.pop(name, None)
        self.bind_target(loop.target, (_element(sh[0]), sh[1]), inner)
        kept = set(_target_names(loop.target))
        for target, value, kind in self.sites(loop.body):
            if kind == "value" and value is not None and self.shape(value, inner) is not None:
                kept.update(_target_names(target))
        scope = self.function_of(loop) or dict(self.trees)[path]
        for name in sorted(kept):
            if _reads_outside(scope, loop, name):
                self.violations.append((path, loop.lineno, f"a loop over {sh[1]} ids keeps {name!r} after it ends: "
                                                           f"the id of one place in the declared order", sh[1]))
                return

    def in_comprehension(self, node):
        up = self.parents.get(id(node))
        while up is not None and not isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.Module)):
            if isinstance(up, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
                return True
            up = self.parents.get(id(up))
        return False

    def function_of(self, node):
        up = self.parents.get(id(node))
        while up is not None and not isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            up = self.parents.get(id(up))
        return up

    def propagate(self, node, env):
        """A helper of the model called with ids: its parameters hold ids too."""
        func = node.func
        if isinstance(func, ast.Name) and func.id in self.functions:
            fn = self.functions[func.id]
            for n, a in enumerate(node.args):
                self.mark(fn, n, self.shape(a, env))
            names = [a.arg for a in fn.args.args]
            for k in node.keywords:
                if k.arg in names:
                    self.mark(fn, names.index(k.arg), self.shape(k.value, env))

    def judge(self, path, e, sh, env):
        """The use of an expression that holds ids, by its parent."""
        form, kind = sh
        p = self.parents.get(id(e))
        line = getattr(e, "lineno", getattr(p, "lineno", 0))
        bad = lambda text: self.violations.append((path, line, text, kind))  # noqa: E731
        doubt = lambda text: self.doubts.append((path, line, text))         # noqa: E731
        if form == "state":
            self.judge_state(e, p, doubt, env)
            return
        if isinstance(e, ast.Starred) and form in _BY_KIND - {"unordered"} and isinstance(p, ast.Call) \
                and isinstance(p.func, ast.Name) and p.func.id in self.functions:
            bad(f"*... spreads {kind} ids into parameters by their place in the declared order")
            return
        if p is None or isinstance(p, (ast.Expr, ast.Assign, ast.AnnAssign, ast.NamedExpr, ast.Return,
                                       ast.BoolOp, ast.Assert, ast.If, ast.While, ast.Lambda, ast.Await)):
            return
        if isinstance(p, ast.UnaryOp):
            if isinstance(p.op, ast.Not):
                return
            doubt(f"computes with a {kind} id ({type(p.op).__name__})")
            return
        if isinstance(p, _TRANSPARENT) or isinstance(p, (ast.Dict, ast.comprehension, ast.GeneratorExp, ast.ListComp,
                                                         ast.SetComp, ast.DictComp)):
            if isinstance(p, ast.comprehension) and p.iter is not e:
                return
            return                                 # the container holds the ids: judged where it is used
        if isinstance(p, (ast.For, ast.AsyncFor)):
            if p.iter is e and form in _BY_KIND and _loop_exits(p.body):
                bad(f"a loop over {kind} ids that stops early depends on the order of the {kind} ids")
            return
        if isinstance(p, ast.Compare):
            items = [p.left] + list(p.comparators)
            for op, a, b in zip(p.ops, items, items[1:]):
                if e is not a and e is not b:
                    continue
                other = b if e is a else a
                if isinstance(op, _ORDER_OPS):
                    bad(f"compares {kind} ids by order")
                elif isinstance(op, (ast.In, ast.NotIn)):
                    if e is a and form in ("scalar", "record") and isinstance(other, ast.Constant) \
                            and isinstance(other.value, str):
                        doubt(f"looks for the text of a {kind} id in a text")
                    elif e is a and form in ("scalar", "record") and not self.followed(other, env):
                        doubt(f"looks a {kind} id up in a value the rule cannot follow")
                    elif e is a and not self.followed(other, env):
                        doubt(f"looks {kind} ids up in a value the rule cannot follow")
                    elif e is b and form == "scalar":     # "1" in t: a search of the id's text
                        doubt(f"looks for a value in the text of a {kind} id")
                    elif e is b and not self.followed(other, env):
                        doubt(f"looks a value the rule cannot follow up among {kind} ids")
                elif form in _BY_KIND - {"unordered", "table"}:
                    doubt(f"compares a list in the declared order of the {kind} ids")
                elif form in ("scalar", "record") and not self.followed(other, env):
                    doubt(f"compares a {kind} id with a value the rule cannot follow")
                elif not self.followed(other, env):       # [t] == [...], {t} == {...}, {t: 1} == {...}
                    doubt(f"compares {kind} ids with a value the rule cannot follow")
            return
        if isinstance(p, ast.Subscript):
            if p.value is e:
                if form == "table" and not isinstance(p.slice, ast.Slice) and not self.followed(p.slice, env):
                    doubt(f"looks a table of {kind} ids up at a key the rule cannot follow")
                elif form == "scalar":
                    doubt(f"uses the text of a {kind} id ([...])")
                elif form in _BY_KIND - {"table"} and not isinstance(p.slice, ast.Slice):
                    bad(f"[...] picks one {kind} id by its place in the declared order")
                elif form in _BY_KIND - {"table"} and (p.slice.lower is not None or p.slice.upper is not None
                                                        or not _whole_step(p.slice.step)):
                    bad(f"[...] picks {kind} ids by their place in the declared order")
                return
            if self.state_access(p):
                return
            owner = self.shape(p.value, env)
            if owner is not None and owner[0] in ("table", "state"):
                return
            doubt(f"looks a {kind} id up in a table the rule cannot judge")
            return
        if isinstance(p, ast.BinOp):
            if isinstance(p.op, (ast.Add, ast.BitOr, ast.Sub, ast.BitAnd)) and form in _COLLECTIONS:
                other = p.right if p.left is e else p.left
                if not self.followed(other, env):          # set(IDS) - {"T" + "1"}: some ids, by their text
                    doubt(f"combines {kind} ids with a value the rule cannot follow ({type(p.op).__name__})")
                return
            doubt(f"computes with a {kind} id ({type(p.op).__name__})")
            return
        if isinstance(p, (ast.FormattedValue, ast.JoinedStr)):
            doubt(f"writes a {kind} id into text")
            return
        if isinstance(p, ast.Attribute):
            call = self.parents.get(id(p))
            if not (isinstance(call, ast.Call) and call.func is p):
                doubt(f"uses the text of a {kind} id (.{p.attr})")
                return
            if form == "scalar":
                doubt(f"uses the text of a {kind} id (.{p.attr})")
            elif p.attr == "index" and form in _BY_KIND:
                bad(f"{kind} ids .index() depends on the order of the {kind} ids")
            elif p.attr in ("count", "index", "get") or p.attr in _SET_METHODS:
                looked = list(call.args) + [k.value for k in call.keywords]
                if not all(self.followed(x.value if isinstance(x, ast.Starred) else x, env) for x in looked[:1]):
                    doubt(f"looks a value the rule cannot follow up among {kind} ids (.{p.attr})")
                elif p.attr in _SET_METHODS and not all(self.followed(x, env) for x in looked):
                    doubt(f"looks a value the rule cannot follow up among {kind} ids (.{p.attr})")
            elif p.attr in ("copy", "keys", "values", "items"):
                pass
            else:
                doubt(f"passes {kind} ids to .{p.attr}()")
            return
        call, keyword = (self.parents.get(id(p)), p) if isinstance(p, ast.keyword) else (p, None)
        if isinstance(call, ast.Call):
            self.judge_call(call, e, form, kind, bad, doubt, env)
            return
        doubt(f"uses a {kind} id in a way the rule cannot judge ({type(p).__name__})")

    def judge_state(self, e, p, doubt, env):
        """The model state may be read and written by key, mark its effects (s.source) and go to
        a helper of the model; anything else (its keys, values, length, iteration) can tell
        the objects apart by their declared order. A key must name its field and, for a field
        over interchangeable ids, take each id from a value the rule follows: an id made from
        text, read from the model's declarations or from code the rule does not read could be
        any one of them."""
        if isinstance(p, ast.Subscript) and p.value is e:
            if not self.state_access(p):
                doubt("reads or writes the model state at a key the rule cannot follow")
                return
            key = p.slice
            family = (key.elts[0] if isinstance(key, ast.Tuple) else key).value
            kind = self.over.get(family)
            parts = key.elts[1:] if isinstance(key, ast.Tuple) else []
            for part in parts if kind is not None else []:
                sh = self.shape(part, env)
                if (sh is None or sh[0] != "scalar") and not isinstance(part, ast.Constant):
                    doubt(f"reads or writes {family!r} at a {kind} id the rule cannot follow")
            return
        if isinstance(p, ast.Attribute) and p.value is e and p.attr == "source":
            return
        if isinstance(p, (ast.Assign, ast.Expr, ast.Return, ast.IfExp, ast.BoolOp)):
            return
        if isinstance(p, ast.Call) and e in p.args and isinstance(p.func, ast.Name) and p.func.id in self.functions:
            return
        what = f".{p.attr}" if isinstance(p, ast.Attribute) else type(p).__name__
        doubt(f"uses the model state in a way the rule cannot judge ({what})")

    def followed(self, node, env):
        """Whether the rule knows what the other side of a comparison holds: ids it follows,
        a constant, or a display of constants (a constant equal to an id is refused anyway)."""
        if self.shape(node, env) is not None or isinstance(node, ast.Constant):
            return True
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return all(self.followed(x, env) for x in node.elts)
        return False

    def judge_call(self, call, e, form, kind, bad, doubt, env):
        func = call.func
        if func is e:
            doubt(f"calls a {kind} id")
            return
        if isinstance(func, ast.Name):
            name = func.id
            if name in self.functions:
                return                             # a helper of the model: its parameter is judged there
            if name in _ORDER_FUNCS:
                if form != "kindvals":
                    bad(f"{name}(...) orders {kind} ids")
                return
            if name == "next":
                if form in _BY_KIND:
                    bad(f"next(...) picks one {kind} id by its place in the declared order")
                else:
                    doubt(f"passes a {kind} id to next()")
                return
            if name in _TEXT_FUNCS and form == "scalar":
                doubt(f"uses the text of a {kind} id ({name}())")
                return
            if name in _ALIKE_FUNCS:
                return
            doubt(f"passes a {kind} id to {name}()")
            return
        if isinstance(func, ast.Attribute):
            if func.attr in _DECLARATIONS:
                return
            owner = self.shape(func.value, env)
            if func.attr in ("get", "index", "count") and owner is not None:
                if func.attr == "index" and owner[0] in _BY_KIND:
                    bad(f".index(...) depends on the order of the {kind} ids")
                return
            if func.attr in _SET_METHODS and owner is not None:
                return
            doubt(f"passes a {kind} id to .{func.attr}()")
            return
        doubt(f"passes a {kind} id to a computed function")


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
        path, line, text, kind = min(violations, key=lambda v: (str(v[0]), v[1], v[2]))
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
        check_second_routes(model, root, reads)
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
