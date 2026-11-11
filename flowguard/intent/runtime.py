"""Actual-call observation and one source-only sealed execution boundary."""
from __future__ import annotations

import ast
import builtins
import copy
import dis
import enum
import inspect
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import textwrap
import types
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from . import cells, sites
from flowguard.map.common import MapError

is_transport, transport = sites.is_transport, sites.transport
_PRIVATE = ContextVar('flowguard_runtime_private', default=False)
_OBSERVING = ContextVar('flowguard_runtime_observing', default=frozenset())
_HISTORICAL = ContextVar('flowguard_runtime_historical', default=None)
_MISSING = object()
_PERF = time.perf_counter
_FINITE = math.isfinite
_SAFE = {bool, int, float, str, tuple, list, dict, set, frozenset, len, abs, min,
         max, sum, all, any, sorted, round, isinstance, range, enumerate,
         zip, Decimal, date, datetime, timedelta}


def _private_call(function, *args):
    token = _PRIVATE.set(True)
    try:
        return function(*args)
    finally:
        _PRIVATE.reset(token)

def outcome_equal(left, right):
    if isinstance(left, cells.Raised) or isinstance(right, cells.Raised):
        return (isinstance(left, cells.Raised) and isinstance(right, cells.Raised)
                and type(left.error) is type(right.error)
                and str(left.error) == str(right.error))
    return cells.same(left, right)

def _value(fn, bound):
    """One bounded call, for an explicit current object or a compiled closed def."""
    global _CALLING
    scope = types.SimpleNamespace(reason='')
    _install()
    with _bounded(scope):
        previous, _LOCAL.guard = _LOCAL.guard, scope
        _CALLING += 1
        try:
            try:
                value = fn(*bound.args, **bound.kwargs)
            except Exception as error:
                value = cells.Raised(error)
        finally:
            _CALLING -= 1
            _LOCAL.guard = previous
    if scope.reason:
        raise Refused(scope.reason)
    return value

def _raw_value(value):
    """A boundary summary; source-declared readings belong to Capture's callback."""
    if type(value) in (type(None), bool, int, float, str, bytes, Decimal, date, datetime, timedelta):
        return value
    return '<' + type.__getattribute__(type(value), '__name__') + '>'

def _binding(signature, arguments):
    return inspect.BoundArguments(signature, dict(arguments))

def _simple(value):
    kinds = (type(None), bool, int, float, str, Decimal, date, datetime, timedelta)
    if type(value) in kinds:
        return True
    operations = ('__eq__', '__lt__', '__le__', '__gt__', '__ge__', '__bool__', '__int__', '__float__')
    return (type(type(value)) is enum.EnumType and type(inspect.getattr_static(value, '_value_', object())) in kinds
            and all(type(inspect.getattr_static(type(value), name, None)) in
                    (type(None), types.WrapperDescriptorType, types.MethodDescriptorType, types.BuiltinFunctionType)
                    for name in operations))

# The closed environment has values, never a project module or its live globals.
class Refused(BaseException):
    pass


class _Globals(dict):
    def __missing__(self, name):
        raise Refused('uses ' + name)


class _Local(threading.local):
    guard = None


_LOCAL, _CALLING, _HOOKED = _Local(), 0, False


def _install():
    global _HOOKED
    if not _HOOKED:
        sys.addaudithook(_audit)
        _HOOKED = True


def _audit(event, args):
    scope = _LOCAL.guard
    if _CALLING and scope is not None and (event == 'open' or event.startswith(
            ('os.', 'socket.', 'subprocess.', 'sqlite3.', 'urllib.', '_thread.')) or event == 'import'):
        scope.reason = 'uses ' + event
        raise Refused(scope.reason)


@contextmanager
def _bounded(scope):
    from . import owners
    try:
        with owners.watchdog(owners.TIMEOUT):
            yield
    except owners._Timeout:
        scope.reason = f'exceeded {owners.TIMEOUT:g} seconds without completion'


@contextmanager
def unguarded():
    previous, _LOCAL.guard = _LOCAL.guard, None
    try:
        yield
    finally:
        _LOCAL.guard = previous


def _json(value):
    """The one JSON text of exact JSON data; anything else is refused before it is encoded."""
    _checked(value, frozenset())
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(',', ':'))


def _checked(value, trail):
    kind = type(value)
    if kind in (type(None), bool, int, float, str):
        if kind is float and not _FINITE(value):
            raise Refused('non-finite JSON number')
    elif kind in (list, dict):
        if id(value) in trail:
            raise Refused('cyclic JSON value')
        trail = trail | {id(value)}
        if kind is dict and any(type(key) is not str for key in value):
            raise Refused('JSON object keys must be strings')
        for item in value.values() if kind is dict else value:
            _checked(item, trail)
    else:
        raise Refused('not JSON data')


def _clock(*args, **kwargs):
    raise Refused('uses current time')


class _Date(date):
    today = classmethod(_clock)


class _DateTime(datetime):
    now = utcnow = today = classmethod(_clock)


_BUILTINS = {name: getattr(builtins, name) for name in (
    'abs all any bool dict divmod enumerate filter float frozenset int isinstance len list map max min '
    'range repr reversed round set sorted str sum tuple zip').split()}
_BUILTINS.update((name, value) for name, value in vars(builtins).items()
                 if isinstance(value, type) and issubclass(value, Exception))
_MATH = {name: value for name, value in vars(math).items() if not name.startswith('_') and (
    type(value) in (int, float) or type(value) is types.BuiltinFunctionType
    and value.__module__ == 'math' and value.__name__ == name)}
_METHODS = frozenset(('real imag numerator denominator year month day hour minute second microsecond days seconds '
    'date weekday isoweekday isocalendar isoformat fromisoformat total_seconds '
    'lower upper strip lstrip rstrip split rsplit splitlines join replace startswith endswith find rfind '
    'count index isalpha isdigit isdecimal isalnum isspace capitalize title casefold zfill '
    'keys values items get copy bit_length as_integer_ratio quantize normalize is_finite').split())


def _project_space(imports, name, level, seen):
    """The literal constants of one project module as a namespace, read from its source with the same scan
    as the sealed file's own top level (`_scope`); nothing is imported or executed. None when `imports`
    finds no project source for the module (a standard or installed module, or no resolver). A module that
    does not parse makes the importing source unavailable with that error."""
    found = imports(name, level) if imports is not None else None
    if found is None or found[2] in seen:
        return None
    text, nested, key = found
    env, _, _, _, literals = _scope(ast.parse(text, key), nested, seen | {key})
    return types.SimpleNamespace(**{name: env[name] for name in literals if not name.startswith('_')})


def _scope(tree, imports=None, seen=frozenset()):
    """The sealed globals of one module's top level: its literal constants, the whitelisted modules, the
    literal constants of the project modules it imports (`imports` finds their source), its functions and the
    names nothing may read. Returns (env, functions, blocked, namespaces by id, literal constant names)."""
    modules = {'math': types.SimpleNamespace(**{name: value for name, value in _MATH.items()
               if vars(math).get(name) is value}), 'decimal': types.SimpleNamespace(Decimal=Decimal),
               'datetime': types.SimpleNamespace(date=_Date, datetime=_DateTime, timedelta=timedelta)}
    spaces = {id(space): space for space in modules.values()}
    env = _Globals(__builtins__=_BUILTINS, **_BUILTINS)
    functions, blocked, literals = {}, set(), set()
    for n in tree.body:
        names, values = set(), {}
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[n.name] = n
            env.pop(n.name, None)
            blocked.discard(n.name)
            literals.discard(n.name)
            continue
        if isinstance(n, ast.Import):
            for a in n.names:
                name = a.asname or a.name.split('.')[0]
                names.add(name)
                if a.name in modules:
                    values[name] = modules[a.name]
                    continue
                # `import X.Y as Z` binds the module X.Y; `import X.Y` binds X with its attribute Y.
                space = _project_space(imports, a.name, 0, seen)
                parts = a.name.split('.')
                for depth in range(len(parts) - 1, 0, -1) if space is not None and not a.asname else ():
                    spaces[id(space)] = space
                    parent = _project_space(imports, '.'.join(parts[:depth]), 0, seen) or types.SimpleNamespace()
                    setattr(parent, parts[depth], space)
                    space = parent
                if space is not None:
                    values[name] = spaces[id(space)] = space
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name == '*':
                    raise Refused('uses wildcard import')
                name = a.asname or a.name
                names.add(name)
                if not n.level and n.module in modules:
                    if not a.name.startswith('_') and hasattr(modules[n.module], a.name):
                        values[name] = getattr(modules[n.module], a.name)
                elif not a.name.startswith('_'):
                    owner = _project_space(imports, n.module or '', n.level, seen)
                    if owner is not None and hasattr(owner, a.name):
                        values[name] = getattr(owner, a.name)
                    else:       # `from package import module`
                        module = _project_space(imports, ((n.module or '') + '.' + a.name).lstrip('.') if n.module
                                                else a.name, n.level, seen)
                        if module is not None:
                            values[name] = spaces[id(module)] = module
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            if n.value is None:
                continue
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = {p.id for target in targets for p in ast.walk(target) if isinstance(p, ast.Name)}
            try:
                value = ast.literal_eval(n.value)
            except (ValueError, TypeError, SyntaxError):
                value = _MISSING
                names.update(p.id for p in ast.walk(n.value) if isinstance(p, ast.Name))
            for target in targets:
                if value is not _MISSING and isinstance(target, ast.Name):
                    values[target.id] = value
        else:
            names = {p.id for p in ast.walk(n) if isinstance(p, ast.Name)}
            names.update(p.name for p in ast.walk(n) if isinstance(p, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))
            names.update(p.asname or p.name.split('.')[0] for p in ast.walk(n) if isinstance(p, ast.alias))
        for name in names:
            functions.pop(name, None)
            env.pop(name, None)
            blocked.add(name)
            literals.discard(name)
        env.update(values)
        blocked.difference_update(values)
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            literals.update(values)
    return env, functions, blocked, spaces, literals


def _closed(source, qual, imports=None):
    env, functions, blocked, spaces, _ = _scope(ast.parse(source), imports)
    if qual in blocked:
        raise Refused('uses unavailable binding ' + qual)
    if '.' in qual or qual not in functions:
        raise Refused('not a module-level function')
    todo, used, definitions = [qual], set(), []
    while todo:
        name = todo.pop()
        if name in used:
            continue
        used.add(name)
        n = functions[name]
        if isinstance(n, ast.AsyncFunctionDef) or n.decorator_list or getattr(n, 'type_params', ()):
            raise Refused('decorator, async or type parameters')
        n = copy.deepcopy(n)
        n.returns = None
        for a in [*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs, *([n.args.vararg] if n.args.vararg else []),
                  *([n.args.kwarg] if n.args.kwarg else [])]:
            a.annotation = None
        for value in [*n.args.defaults, *(v for v in n.args.kw_defaults if v is not None)]:
            try:
                ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError):
                raise Refused('non-literal default') from None
        local = {p.arg for p in [*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs,
                                *([n.args.vararg] if n.args.vararg else []), *([n.args.kwarg] if n.args.kwarg else [])]}
        local.update(p.id for p in ast.walk(n) if isinstance(p, ast.Name) and isinstance(p.ctx, ast.Store))
        def space(node):
            """The module namespace an attribute chain of global names reads (`math`, `shop.settings`), or None."""
            if isinstance(node, ast.Name):
                found = env.get(node.id) if node.id not in local else None
            elif isinstance(node, ast.Attribute) and (outer := space(node.value)) is not None:
                found = vars(outer).get(node.attr)
            else:
                return None
            return found if id(found) in spaces and spaces[id(found)] is found else None
        for part in ast.walk(n):
            if isinstance(part, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal,
                                 ast.Yield, ast.YieldFrom, ast.Await, ast.Try, ast.With, ast.AsyncWith)):
                raise Refused('unsupported ' + type(part).__name__)
            if isinstance(part, ast.Name) and part.id.startswith('__'):
                raise Refused('uses ' + part.id)
            if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load) and part.id in blocked - local:
                raise Refused('uses unavailable binding ' + part.id)
            if (isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)
                    and part.id not in local and part.id not in functions and part.id not in env):
                raise Refused('uses ' + part.id)
            if isinstance(part, ast.Attribute):
                namespace = space(part.value)
                module = namespace is not None
                if module and not hasattr(namespace, part.attr):
                    raise Refused('uses unavailable attribute ' + part.attr)
                if part.attr.startswith('_') or isinstance(part.ctx, (ast.Store, ast.Del)) or part.attr not in _METHODS and not module:
                    raise Refused('uses attribute ' + part.attr)
        todo.extend(p.id for p in ast.walk(n) if isinstance(p, ast.Name) and isinstance(p.ctx, ast.Load)
                    and p.id in functions and p.id not in local)
        definitions.append(n)
    exec(compile(ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[])),
                 '<flowguard-sealed>', 'exec'), env)
    return env[qual]


def sealed(source, qual, args, kwargs, imports=None):
    """Evaluate one source-only function in fresh globals and strict JSON values. `imports` finds the source
    of a project module the function's file imports constants from (`Runtime.imports`)."""
    token = _PRIVATE.set(True)
    try:
        fn = _closed(source, qual, imports)
        values = json.loads(_json({'args': list(args), 'kwargs': kwargs}))
        value = _value(fn, types.SimpleNamespace(args=values['args'], kwargs=values['kwargs']))
        if isinstance(value, cells.Raised):
            error = value.error
            return dict(status='raised', error=dict(type=type(error).__name__, message=str(error)))
        return dict(status='ok', value=json.loads(_json(value)))
    except Refused as error:
        return dict(status='unavailable', reason=str(error))
    except (ValueError, SyntaxError, TypeError, RecursionError) as error:
        return dict(status='unavailable', reason=type(error).__name__ + ': ' + str(error))
    finally:
        _PRIVATE.reset(token)


def _resolve(expression, env):
    if isinstance(expression, ast.Name):
        return env.get(expression.id, vars(builtins).get(expression.id, _MISSING))
    if isinstance(expression, ast.Constant):
        return expression.value
    if isinstance(expression, ast.Attribute):
        owner = _resolve(expression.value, env)
        if type(owner) in (types.ModuleType, type, enum.EnumType):
            return vars(owner).get(expression.attr, _MISSING)
    return _MISSING

def _chain(expression):
    """An attribute/subscript chain from a name, without calls (`CACHE`, `settings.LIMITS['a']`)."""
    while isinstance(expression, (ast.Attribute, ast.Subscript)):
        expression = expression.value
    return isinstance(expression, ast.Name)

def _definition(fn):
    return ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]

def _functions(tree, prefix=''):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + node.name, node
        elif isinstance(node, ast.ClassDef):
            yield from _functions(node, prefix + node.name + '.')

def _literal(node, constants):
    """Only inert constructors, never execution of a previous module initializer."""
    constructors = (Decimal, date, datetime, timedelta)
    allowed = {name: value for name, value in constants.items() if any(value is fn for fn in constructors)}
    for part in ast.walk(node):
        if isinstance(part, ast.Call) and not (isinstance(part.func, ast.Name) and part.func.id in allowed):
            raise ValueError('old constant/default is not an inert expression')
        if isinstance(part, (ast.Attribute, ast.Lambda, ast.NamedExpr, ast.ListComp, ast.DictComp,
                             ast.SetComp, ast.GeneratorExp, ast.Await, ast.Yield)):
            raise ValueError('old constant/default is not an inert expression')
        if isinstance(part, ast.Name) and part.id not in constants and part.id not in allowed:
            raise ValueError('old constant/default names an unknown value: ' + part.id)
    return eval(compile(ast.Expression(node), '<flowguard old constant>', 'eval'),
                {'__builtins__': {}, **allowed, **constants})

def _literal_equal(left, right):
    """Compare inert source data without running a fixture object's operators."""
    if left is right:
        return True
    if type(left) is not type(right):
        return False
    if type(left) in (type(None), bool, int, float, str, bytes, Decimal, date, timedelta):
        return left == right
    if type(left) is datetime:
        return left == right if left.tzinfo is None and right.tzinfo is None else None
    if type(left) in (set, frozenset):
        inert = (type(None), bool, int, float, str, bytes, Decimal, date, timedelta)
        return left == right if all(type(v) in inert for v in (*left, *right)) else None
    if type(left) in (tuple, list):
        if len(left) != len(right):
            return False
        outcomes = [_literal_equal(a, b) for a, b in zip(left, right)]
    elif type(left) is dict and all(type(k) in (str, int, bool) for k in (*left, *right)):
        if left.keys() != right.keys():
            return False
        outcomes = [_literal_equal(left[k], right[k]) for k in left]
    else:
        return None
    return None if None in outcomes else all(outcomes)

def _binding_facts(tree):
    """Top-level binding identity; function bodies have their own fingerprints."""
    result = {}
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[statement.name] = ('function', statement.name)
        elif isinstance(statement, ast.ClassDef):
            result[statement.name] = ('class', ast.dump(statement, include_attributes=False))
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            for alias in statement.names:
                name = alias.asname or alias.name.split('.')[0]
                result[name] = ('import', alias.name) if isinstance(statement, ast.Import) else \
                    ('from', statement.level, statement.module, alias.name)
        elif isinstance(statement, ast.Delete):
            for node in ast.walk(statement):
                if isinstance(node, ast.Name):
                    result.pop(node.id, None)
        else:
            value = statement.value if isinstance(statement, (ast.Assign, ast.AnnAssign)) else statement
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    result[node.id] = ('value', ast.dump(value, include_attributes=False))
    return result

@dataclass
class Reading:
    name: str
    target: str
    test: str = ''
    status: str = 'ok'
    reasons: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    context: tuple = ()
    baseline: str = ''
    comparison_status: str = 'ok'
    comparison_reasons: list = field(default_factory=list)
    actual: tuple | None = None  # (simple inputs, outcome) of the real call; never a replay.
    lost: str = ''  # why it is grey, when the baseline code in this same context replays cleanly
    fields: dict | None = None  # an anchor's `fields` values at the real call, read before it ran
    field_rows: list = field(default_factory=list)  # the same values at each replayed row (None: not read)
    field_reasons: list = field(default_factory=list)
    actual_inputs: dict = field(default_factory=dict)
    sample: dict | None = None
    json_result: object = None
    index: int = -1
    tests: set = field(default_factory=set)     # every test that called with this encoded input

class _ObserverHub:
    """One monitoring/trace owner, with local boundaries and optional discovery."""
    def __init__(self):
        self.records, self.tool = [], None
        self.codes = __import__('weakref').WeakValueDictionary()
        self.trace = self._trace
        self.previous = None
        self.foreign, self.lines = {}, {}
        self.wanted, self.dynamic = set(), False
        self.wanted_lines = set()   # first lines of the observed code, for the Python 3.11 trace fast path

    def index(self):
        """The observed code objects; a dynamic predicate alone needs every call."""
        self.wanted = {key for record in self.records for key in record.codes}
        self.wanted_lines = {code.co_firstlineno for record in self.records for code, _ in record.codes.values()}
        self.dynamic = any(record.predicate is not None for record in self.records)

    def add(self, record):
        current = sys.gettrace()
        external = self.previous if self.records and current is self.trace and not hasattr(sys, 'monitoring') else current
        if not record.entry_only and external is not None and external is not self.trace:
            record.issues.append('another debugger/trace hook is active; observation was not installed')
            return
        self.records.append(record)
        self.index()
        try:
            if hasattr(sys, 'monitoring'):
                mon = sys.monitoring
                if self.tool is None:
                    self.tool = next((n for n in (4, 3) if mon.get_tool(n) is None), None)
                    if self.tool is None:
                        raise RuntimeError('sys.monitoring IDs 3 and 4 are busy')
                    mon.use_tool_id(self.tool, 'flowguard-runtime')
                    for event, callback in ((mon.events.PY_START, self._start), (mon.events.PY_RESUME, self._start),
                                            (mon.events.PY_THROW, self._throw), (mon.events.PY_RETURN, self._return),
                                            (mon.events.PY_YIELD, self._return), (mon.events.PY_UNWIND, self._unwind)):
                        mon.register_callback(self.tool, event, callback)
                self.refresh()
            elif len(self.records) == 1:
                self.previous = sys.gettrace()
                sys.settrace(self.trace)
            record.active = True
        except Exception as error:
            self.records.remove(record)
            self.index()
            if not self.records:
                self.stop()
            record.issues.append('event observation unavailable: ' + type(error).__name__ + ': ' + str(error))

    def refresh(self):
        mon = sys.monitoring
        dynamic = any(record.predicate is not None for record in self.records)
        mon.set_events(self.tool, mon.events.PY_UNWIND | ((mon.events.PY_START | mon.events.PY_RESUME | mon.events.PY_THROW) if dynamic else 0))
        for record in self.records:
            for code, _ in record.codes.values():
                self.local(code)

    def local(self, code):
        self.codes[id(code)] = code
        mon = sys.monitoring
        mon.set_local_events(self.tool, code, mon.events.PY_START | mon.events.PY_RETURN | mon.events.PY_YIELD)

    def remove(self, record):
        if not record.active:
            return
        if record.interrupted and not hasattr(sys, 'monitoring') and sys.gettrace() is None:
            sys.settrace(self.trace)  # CPython cleared our raising trace callback.
        self.records.remove(record)
        self.index()
        record.active = False
        if not hasattr(sys, 'monitoring'):
            for key in tuple(record.frames):
                if not any(key in other.frames for other in self.records):
                    saved = self.lines.pop(key, None)
                    if saved:
                        saved[0].f_trace_lines = saved[1]
        if self.records and hasattr(sys, 'monitoring'):
            self.refresh()
        elif not self.records:
            self.stop()

    def stop(self):
        if self.tool is not None:
            mon = sys.monitoring
            mon.set_events(self.tool, 0)
            for code in tuple(self.codes.values()):
                mon.set_local_events(self.tool, code, 0)
            for event in (mon.events.PY_START, mon.events.PY_RESUME, mon.events.PY_THROW,
                          mon.events.PY_RETURN, mon.events.PY_YIELD, mon.events.PY_UNWIND):
                mon.register_callback(self.tool, event, None)
            mon.free_tool_id(self.tool)
            self.tool = None
            self.codes.clear()
        elif not hasattr(sys, 'monitoring'):
            if sys.gettrace() is self.trace:
                sys.settrace(self.previous)
            for frame, original in self.lines.values():
                frame.f_trace_lines = original
            self.foreign.clear()
            self.lines.clear()
            self.previous = None

    def dispatch(self, frame, event, arg):
        if event == 'call' and is_transport(frame.f_code):
            return False
        if any(any(frame.f_code is ignored for ignored in record.ignored) for record in self.records):
            return False
        interested = False
        for record in tuple(self.records):
            if event == 'call':
                if _PRIVATE.get() and not record.private:
                    continue
                selected = _private_call(self.selected, record, frame.f_code)
                if not selected:
                    continue
                if _private_call(record.emit, frame, event, arg) and not record.entry_only:
                    record.frames.add(id(frame))
                    interested = True
            elif id(frame) in record.frames:
                _private_call(record.emit, frame, event, arg)
                interested = True
                if event == 'return':
                    record.frames.discard(id(frame))
        if interested and event == 'call' and self.tool is not None:
            self.local(frame.f_code)
        return interested

    def selected(self, record, code):
        entry = record.codes.get(id(code))
        return (entry is not None and entry[0] is code) or (record.predicate is not None and bool(record.predicate(code)))

    def _start(self, code, offset):
        self.dispatch(sys._getframe(1), 'call', None)

    def _throw(self, code, offset, error):
        self.dispatch(sys._getframe(1), 'call', None)

    def _return(self, code, offset, value):
        self.dispatch(sys._getframe(1), 'return', value)

    def _unwind(self, code, offset, error):
        frame = sys._getframe(1)
        self.dispatch(frame, 'exception', (type(error), error, error.__traceback__))
        self.dispatch(frame, 'return', None)

    def _trace(self, frame, event, arg):
        if event == 'call' and self.previous is None and not self.dynamic and (
                frame.f_lasti == 0 and frame.f_lineno not in self.wanted_lines or id(frame.f_code) not in self.wanted):
            # Python 3.11: an unobserved frame costs one lookup and is not traced further. A fresh call
            # starts on its first line, so the line lookup comes first: reading f_code raises an audit
            # event on 3.11, which the replay guard's hook would see on every call.
            return None
        key = id(frame)
        prior = self.previous if event == 'call' else self.foreign.get(key)
        foreign = prior(frame, event, arg) if prior is not None else None
        if foreign is not None:
            self.foreign[key] = foreign
        else:
            self.foreign.pop(key, None)
        interested = self.dispatch(frame, event, arg)
        if event == 'call' and interested and foreign is None and frame.f_trace_lines:
            self.lines[key] = frame, frame.f_trace_lines
            frame.f_trace_lines = False
        elif event == 'return':
            self.foreign.pop(key, None)
            saved = self.lines.pop(key, None)
            if saved:
                frame.f_trace_lines = saved[1]
        return self.trace if interested or foreign is not None else None

def _cells(function):
    values = []
    for cell in function.__closure__ or ():
        try:
            values.append(cell.cell_contents)
        except ValueError:
            continue  # An empty cell holds no function.
    return values

def module_codes(module, wanted):
    """Code objects of `module` whose (co_filename, qualname without '<locals>') is in `wanted`.

    Observation points are known functions; their code objects get local events,
    so no process-wide call monitoring is needed to find them. Installed shims
    are skipped for the original code they replaced.
    """
    found, seen = [], set()
    def code_walk(code):
        if id(code) in seen:
            return
        seen.add(id(code))
        if (code.co_filename, code.co_qualname.replace('.<locals>.', '.')) in wanted:
            found.append(code)
        for constant in code.co_consts:
            if isinstance(constant, types.CodeType):
                code_walk(constant)
    def value_walk(value, depth):
        if isinstance(value, (staticmethod, classmethod)):
            value = value.__func__
        if isinstance(value, property):
            for part in (value.fget, value.fset, value.fdel):
                value_walk(part, depth)
            return
        chain = 0
        while isinstance(value, types.FunctionType) and chain < 20:
            for function in (value, *(cell for cell in _cells(value) if isinstance(cell, types.FunctionType))):
                # Both the running code (an installed mutant) and the original under a shim.
                code_walk(function.__code__)
                if (origin := sites.installed_origin(function)) is not None:
                    code_walk(origin)
            value, chain = inspect.getattr_static(value, '__wrapped__', None), chain + 1
        if isinstance(value, type) and depth < 6 and id(value) not in seen:
            seen.add(id(value))
            for part in list(vars(value).values()):
                value_walk(part, depth + 1)
    for value in list(vars(module).values()):
        value_walk(value, 0)
    return found

class _Record:
    def __init__(self, runtime, codes, predicate, callback, private, ignored, entry_only, events=None):
        pairs = codes.items() if hasattr(codes, 'items') else codes
        self.runtime, self.codes = runtime, {id(code): (code, name) for code, name in pairs}
        self.predicate, self.callback, self.private = predicate, callback, private
        self.ignored, self.entry_only = ignored, entry_only
        self.issues, self.frames, self.pending = [], set(), {}
        self.events = runtime.events if events is None else events
        self.active, self.failed, self.interrupted, self.ambient = False, False, False, None

    def emit(self, frame, event, arg):
        entry = self.codes.get(id(frame.f_code))
        interested = entry is not None and entry[0] is frame.f_code
        if interested and event == 'exception':
            self.pending[id(frame)] = arg[1]
        if interested and event != 'exception':
            error = self.pending.pop(id(frame), None) if event == 'return' else None
            opcode = dis.opname[frame.f_code.co_code[frame.f_lasti]] if frame.f_lasti >= 0 else ''
            raised = error is not None and opcode not in {'RETURN_VALUE', 'RETURN_CONST'}
            code = frame.f_code
            count = code.co_argcount + code.co_kwonlyargcount + bool(code.co_flags & inspect.CO_VARARGS) \
                + bool(code.co_flags & inspect.CO_VARKEYWORDS)
            values = {name: _raw_value(frame.f_locals[name]) for name in code.co_varnames[:count] if name in frame.f_locals}
            self.events.append(dict(anchor=entry[1], phase='raise' if raised else event,
                                    value=_raw_value(error if raised else arg), values=values, test=self.runtime.test))
        if self.callback is not None and not self.failed:
            try:
                interested = self.callback(frame, event, arg) is not None or interested
            except Exception as error:
                self.failed = True
                self.issues.append('observer callback failed: ' + type(error).__name__ + ': ' + str(error))
            except BaseException:
                self.interrupted = True
                raise
        return interested and self.active

    def add_code(self, code, name):
        """Observe one more code object (a module imported later) with local events only."""
        self.codes[id(code)] = (code, name)
        if self.active:
            _HUB.wanted.add(id(code))
            _HUB.wanted_lines.add(code.co_firstlineno)
            if _HUB.tool is not None:
                _HUB.local(code)

    def __enter__(self):
        self.ambient = sys.gettrace()
        _HUB.add(self)
        return self.events

    def __exit__(self, *error):
        expected = _HUB.trace if not hasattr(sys, 'monitoring') else self.ambient
        if self.active and sys.gettrace() is not expected and not (
                self.interrupted and not hasattr(sys, 'monitoring') and sys.gettrace() is None):
            self.issues.append('trace hook changed during anchor observation')
        _HUB.remove(self)
        self.runtime.issues.extend(self.issues)
        self.frames.clear()
        self.pending.clear()

_HUB = _ObserverHub()



@dataclass
class Patch:
    function: object
    code: object
    defaults: tuple | None
    kwdefaults: dict | None
    node: object
    source: str
    dependencies: tuple = ()

    def callable(self):
        def call(*args, **kwargs):
            result = sealed(self.source, self.node.name, list(args), kwargs)
            if result['status'] == 'unavailable':
                raise Refused(result['reason'])
            if result['status'] == 'raised':
                error = result['error']
                raise getattr(builtins, error['type'], ValueError)(error['message'])
            return result['value']
        return call



class Runtime:
    def __init__(self, root, baseline='HEAD', *, previous=None):
        self.root, self.baseline, self.previous = Path(root).resolve(), baseline, previous
        self._baseline_error = ''
        if previous is None:
            from flowguard.map.common import git_run
            try:
                found = git_run(self.root, 'rev-parse', '--verify', baseline + '^{commit}', allowed=(0, 128))
                self.baseline = found.stdout.decode().strip() if not found.returncode else None
                self._baseline_error = '' if self.baseline else 'baseline is unavailable'
            except (MapError, TypeError) as error:
                self.baseline, self._baseline_error = None, str(error)
        self.readings, self.issues, self.events = [], [], []
        self.patches, self.constants, self.unavailable, self.current_constants = {}, {}, {}, {}
        self._sources, self._trees, self._imported, self._projects, self._bindings = {}, {}, {}, {}, {}
        self._seen, self._test, self.ran, self.seconds = {}, '', set(), 0.0
        self.outcomes = {}          # each ordinary test's phases that did not pass: [(when, outcome, error)]

    @property
    def test(self):
        """The ordinary test whose calls are recorded now; `ran` keeps every test that was current."""
        return self._test

    @test.setter
    def test(self, nodeid):
        self._test = nodeid
        self.ran.add(nodeid)

    def outcome(self, nodeid, when, outcome, excinfo=None):
        """One phase of an ordinary test's run that did not pass (`when`: setup, call or teardown)."""
        self.outcomes.setdefault(nodeid, []).append((when, outcome, excinfo.value if excinfo is not None else None))

    def imports(self, file, module, old=False):
        """How the sealed environment finds a project module that `file` (module `module`) imports: by the
        import root that gives `file` its module name, as the map resolves a project import, and only a
        project source file (never an installed package). The baseline source when `old`. Each answer is
        (source text, the resolver for that module, its file); None when no project file has the name."""
        parts = list(Path(file).with_suffix('').parts)
        own = module.split('.') if module else []
        package = bool(parts) and parts[-1] == '__init__'
        if package:
            parts.pop()
        if not own or parts[len(parts) - len(own):] != own:
            return lambda name, level: None          # the name does not follow the path: no import root
        prefix = parts[:len(parts) - len(own)]
        def find(name, level):
            if level:
                base = own if package else own[:-1]
                if level - 1 > len(base):
                    return None
                name = '.'.join([*base[:len(base) - level + 1], *([name] if name else [])])
            if not name:
                return None
            for candidate in (Path(*prefix, *name.split('.')).with_suffix('.py'), Path(*prefix, *name.split('.'), '__init__.py')):
                relative = candidate.as_posix()
                if not self._project_file(str(self.root / relative)):
                    continue
                if old:
                    text = self._source(relative)
                elif (self.root / relative).is_file():
                    text = (self.root / relative).read_text(encoding='utf-8-sig')
                else:
                    text = None
                if text is not None:
                    return text, self.imports(relative, name, old), relative
            return None
        return find

    def _input(self, function, historical=False):
        fn = sites.unwrap(function)
        file = Path(inspect.getsourcefile(fn)).resolve().relative_to(self.root).as_posix()
        source = self._source(file) if historical else (self.root / file).read_text(encoding='utf-8-sig')
        if source is None:
            raise ValueError('function has no baseline source')
        return fn, file, source

    def full(self, function):
        """Twenty distinct encoded inputs of the function are recorded: its hook comes off."""
        return len(self._seen.get(sites.unwrap(function), ())) >= 20

    def safety(self, function, arguments=None, seen=None, *, historical=False, node=None, reads=None):
        """Compatibility qualification for explicit callers; ordinary hooks never use it."""
        owner = self if historical else (_HISTORICAL.get() or self)
        try:
            old = historical or _HISTORICAL.get() is not None
            fn, file, source = owner._input(function, historical=old)
            _closed(source, fn.__qualname__, owner.imports(file, fn.__module__, old))
            if arguments is not None:
                _json(dict(arguments))
            return ''
        except (Refused, ValueError, TypeError, OSError) as error:
            return str(error)

    def guarded(self, fn, bound, *, current=False):
        owner = _HISTORICAL.get()
        try:
            if current and owner is None:
                return _value(fn, bound), ''
            historical = owner is not None
            owner = owner or self
            function, file, source = owner._input(fn, historical=historical)
            answer = sealed(source, function.__qualname__, list(bound.args), dict(bound.kwargs),
                            owner.imports(file, function.__module__, historical))
        except (Refused, ValueError, TypeError, OSError) as error:
            return None, str(error)
        if answer['status'] == 'unavailable':
            return None, answer['reason']
        if answer['status'] == 'raised':
            error = answer['error']
            return cells.Raised(getattr(builtins, error['type'], ValueError)(error['message'])), ''
        return answer['value'], ''

    def field_values(self, original, bound, fields, line, reading):
        """Explicit fields use the same closed engine; opaque context stays unavailable."""
        try:
            fn, file, source = self._input(original)
            parameters = ', '.join(inspect.signature(fn, follow_wrapped=False).parameters)
            values = {}
            for name, expression in fields:
                body = source + f'\ndef _flowguard_field({parameters}):\n    return ({expression})\n'
                answer = sealed(body, '_flowguard_field', list(bound.args), dict(bound.kwargs), self.imports(file, fn.__module__))
                if answer['status'] != 'ok':
                    reading.field_reasons.append('field ' + name + ': ' + answer.get('reason', str(answer.get('error'))))
                    return
                values[name] = answer['value']
            reading.fields = values
        except (OSError, ValueError, TypeError) as error:
            reading.field_reasons.append(str(error))

    def observe(self, original, bound, *, owner=None, name='', axes=None, private=False, fields=(), line=0, recorded=None):
        started = _PERF()
        function = sites.unwrap(owner or original)
        if (_PRIVATE.get() and not private) or function in _OBSERVING.get() \
                or (not private and len(self._seen.get(function, ())) >= 20):
            return original(*bound.args, **bound.kwargs)
        bound.apply_defaults()
        try:
            key, reason = _json(dict(bound.arguments)), ''    # the call's arguments decide args and kwargs
        except (Refused, ValueError, TypeError, RecursionError) as error:
            key, reason = None, str(error)
        seen = self._seen.setdefault(function, {}) if key is not None and not private else None
        if seen is not None and key in seen:
            # This encoded input was recorded before (design 4.5): one encode and one lookup, no reading.
            seen[key].tests.add(self.test)
            self.seconds += _PERF() - started
            return original(*bound.args, **bound.kwargs)
        token = _PRIVATE.set(True)
        observing = _OBSERVING.set(_OBSERVING.get() | {function})
        reading = Reading(name or function.__qualname__, function.__module__ + ':' + function.__qualname__,
                          test=self.test, baseline=self.baseline or '', tests={self.test})
        reading.actual_inputs = dict(bound.arguments)
        if key is None:
            reading.reasons.append(reason)
        else:
            reading.sample = dict(args=json.loads(_json(list(bound.args))), kwargs=json.loads(_json(dict(bound.kwargs))),
                                  inputs=json.loads(key))
        if seen is not None:
            seen[key] = reading
        if fields:
            self.field_values(original, bound, fields, line, reading)
        reading.index = len(self.readings)
        self.readings.append(reading)
        _OBSERVING.reset(observing)
        _PRIVATE.reset(token)
        self.seconds += _PERF() - started
        try:
            value = original(*bound.args, **bound.kwargs)
        except BaseException as error:
            started = _PERF()
            reading.actual = (dict(bound.arguments), cells.Raised(error))
            self._record(function, reading, recorded, raised=True, private=private)
            self.seconds += _PERF() - started
            raise
        started = _PERF()
        reading.actual = (dict(bound.arguments), value)
        self._record(function, reading, recorded, private=private)
        self.seconds += _PERF() - started
        return value

    def _record(self, function, reading, recorded, raised=False, private=False):
        if not raised:
            try:
                reading.json_result = json.loads(_json(reading.actual[1]))
            except (Refused, ValueError, TypeError, RecursionError) as error:
                reading.sample = None
                reading.reasons.append(str(error))
        if recorded is not None:
            recorded(reading)

    @contextmanager
    def hook(self, function, *, name='', axes=None, private=False, fields=(), line=0, recorded=None):
        function = sites.unwrap(function)
        if not private and self.full(function):
            yield function
            return
        def callback(original, bound):
            return self.observe(original, bound, owner=function, name=name, axes=axes,
                                private=private, fields=fields, line=line, recorded=recorded)
        callback.__flowguard_transport__ = (type(self).observe.__code__,)
        with sites.intercepted(function, callback, keep=lambda: private or not self.full(function)) as original:
            yield original

    @staticmethod
    def observer_issues():
        return [issue for record in _HUB.records for issue in record.issues]

    def record(self, codes=(), *, predicate=None, callback=None, private=False, ignored=(), entry_only=False, events=None):
        return _Record(self, codes, predicate, callback, private, ignored, entry_only, events)

    def axes(self, function, bound, explicit=None):
        return {name: list(values) for name, values in (explicit or {}).items()}

    def register(self, function):
        fn = sites.unwrap(function)
        if fn not in self.patches:
            try:
                _, file, source = self._input(fn, historical=True)
                compiled = _closed(source, fn.__qualname__, self.imports(file, fn.__module__, True))
                self.patches[fn] = Patch(fn, compiled.__code__, compiled.__defaults__, compiled.__kwdefaults__,
                                         dict(_functions(ast.parse(source)))[fn.__qualname__], source)
            except (Refused, ValueError, TypeError, OSError) as error:
                self.unavailable[fn] = str(error)
        return self.patches.get(fn)

    @contextmanager
    def old_code(self):
        token = _HISTORICAL.set(self)
        try:
            yield
        finally:
            _HISTORICAL.reset(token)


    def _source(self, file):
        if self._baseline_error:
            raise MapError(self._baseline_error)
        if file not in self._sources:
            if self.previous is not None:
                self._sources[file] = self.previous.get(file)
            else:
                from flowguard.map.common import git_blob
                raw = git_blob(self.root, self.baseline, file)
                self._sources[file] = raw.decode('utf-8-sig') if raw is not None else None
        return self._sources[file]

    def _constants(self, tree, module, seen=None, *, historical=True):
        seen = set() if seen is None else seen
        if module in seen:
            return {}
        seen = seen | {module}
        constants = {}
        for statement in tree.body:
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] \
                if isinstance(statement, ast.AnnAssign) else []
            names = [target.id for target in targets if isinstance(target, ast.Name)]
            if targets and statement.value is not None:
                try:
                    value = _literal(statement.value, constants)
                except (ValueError, TypeError, SyntaxError, ArithmeticError):
                    for name in names:
                        constants.pop(name, None)
                else:
                    constants.update((name, value) for name in names)
            elif isinstance(statement, ast.ImportFrom):
                package_owner = sys.modules.get(module)
                package = vars(package_owner).get('__package__', '') if type(package_owner) is types.ModuleType else ''
                name = importlib.util.resolve_name('.' * statement.level + (statement.module or ''), package)
                imported = sys.modules.get(name)
                file = vars(imported).get('__file__') if type(imported) is types.ModuleType else None
                if name == 'decimal':
                    previous = {'Decimal': Decimal}
                elif name == 'datetime':
                    previous = {'date': date, 'datetime': datetime, 'timedelta': timedelta}
                elif file and self._project_file(file):
                    relative = Path(file).resolve().relative_to(self.root).as_posix()
                    source = self._source(relative) if historical else (self.root / relative).read_text(encoding='utf-8-sig')
                    previous = self._module_constants(source, name, seen, historical) if source is not None else {}
                else:
                    previous = {}
                for alias in statement.names:
                    if alias.name in previous:
                        constants[alias.asname or alias.name] = previous[alias.name]
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                constants.pop(statement.name, None)
            else:
                for part in ast.walk(statement):
                    if isinstance(part, ast.Name) and isinstance(part.ctx, (ast.Store, ast.Del)):
                        constants.pop(part.id, None)  # conditional/dynamic binding is unknown
        return constants

    def _parsed(self, source, filename='<unknown>'):
        """ast.parse(source, filename), once per runtime: callers only read the tree."""
        key = source, filename
        if key not in self._trees:
            self._trees[key] = ast.parse(source, filename)
        return self._trees[key]

    def _module_constants(self, source, module, seen, historical):
        """_constants of a module's source. The same source, module, import path and the same loaded
        modules behind its `from` imports give the same constants, so each is read once per runtime
        (registering every function of a module read it and all its imports' sources again). A copy is
        returned: the values become old constants that a replay puts back into module namespaces."""
        tree = self._parsed(source)
        package_owner = sys.modules.get(module)
        package = vars(package_owner).get('__package__', '') if type(package_owner) is types.ModuleType else ''
        loaded = []
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom):
                name = importlib.util.resolve_name('.' * statement.level + (statement.module or ''), package)
                imported = sys.modules.get(name)
                loaded.append((name, vars(imported).get('__file__') if type(imported) is types.ModuleType else None))
        key = source, module, frozenset(seen), historical, package, tuple(loaded)
        if key not in self._imported:
            self._imported[key] = self._constants(tree, module, seen, historical=historical)
        return copy.deepcopy(self._imported[key])

    def _binding_facts(self, tree):
            """_binding_facts of a tree, once per tree object (callers only read them)."""
            if id(tree) not in self._bindings or self._bindings[id(tree)][0] is not tree:
                self._bindings[id(tree)] = tree, _binding_facts(tree)
            return self._bindings[id(tree)][1]

    def _project_file(self, file):
        """project_code, once per file for this runtime (its callers ask for every name a function reads)."""
        if file not in self._projects:
            from flowguard.structure.paths import project_code
            self._projects[file] = project_code(file, self.root)
        return self._projects[file]
