"""One in-process observation boundary, shared by tests and explicit checks.

The runtime never collects tests or opens another Python/test session. Replay is
private; real calls and their exceptions still run normally. Unknown replay
boundaries produce unavailable observations, never evidence of agreement.
"""
from __future__ import annotations

import ast
import builtins
import copy
import dis
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
import enum
import inspect
import importlib.util
import itertools
from pathlib import Path
import re
import sqlite3
import sys
import textwrap
import types

from . import cells, sites
from flowguard.map.common import MapError

is_transport = sites.is_transport
transport = sites.transport

_PRIVATE = ContextVar('flowguard_runtime_private', default=False)
_OBSERVING = ContextVar('flowguard_runtime_observing', default=frozenset())
_MISSING = object()
_INERT = object()
_SAFE = {bool, int, float, str, bytes, tuple, list, dict, set, frozenset, len, abs, min,
         max, sum, all, any, sorted, round, isinstance, issubclass, type, range, enumerate,
         zip, Decimal, date, datetime, timedelta, Path}
_READ_METHODS = {'get', 'keys', 'values', 'items', 'count', 'index', 'startswith',
                 'endswith', 'lower', 'upper', 'strip', 'split', 'join', 'replace'}


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
    try:
        return fn(*bound.args, **bound.kwargs)
    except Exception as error:
        return cells.Raised(error)


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


def _read_sql(connection, text):
    if type(connection) is not sqlite3.Connection or connection.row_factory is not None or not (
            connection.text_factory is str or connection.text_factory is bytes):
        return False
    if not text.lstrip().upper().startswith(('SELECT ', 'SELECT\n')):
        return False
    if '--' in text or '/*' in text or re.search(r'["`\]]\s*\(', text):
        return False  # Obfuscated function names are not a proven literal read.
    calls = {name.upper() for name in re.findall(r'\b([^\W\d]\w*)\s*\(', text)}
    syntax = {'IN', 'EXISTS', 'NOT', 'AND', 'OR', 'WHERE', 'SELECT', 'CASE', 'CAST'}
    functions = calls - syntax
    if not functions:
        return True
    inert = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'IFNULL', 'NULLIF',
             'LENGTH', 'ABS', 'LOWER', 'UPPER', 'ROUND'}
    if not functions <= inert:
        return False
    try:
        installed = connection.execute('PRAGMA function_list').fetchall()
    except sqlite3.Error:
        return False
    return all(any(row[0].upper() == name and row[1] for row in installed)
               and not any(row[0].upper() == name and not row[1] for row in installed) for name in functions)


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
class Patch:
    function: object
    code: object
    defaults: tuple | None
    kwdefaults: dict | None
    node: object
    dependencies: tuple = ()

    def callable(self):
        fn = self.function
        result = types.FunctionType(self.code, fn.__globals__, fn.__name__, self.defaults, fn.__closure__)
        result.__kwdefaults__ = self.kwdefaults
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


class _ObserverHub:
    """One monitoring/trace owner, with local boundaries and optional discovery."""
    def __init__(self):
        self.records, self.tool = [], None
        self.codes = __import__('weakref').WeakValueDictionary()
        self.trace = self._trace
        self.previous = None
        self.foreign, self.lines = {}, {}

    def add(self, record):
        current = sys.gettrace()
        external = self.previous if self.records and current is self.trace and not hasattr(sys, 'monitoring') else current
        if not record.entry_only and external is not None and external is not self.trace:
            record.issues.append('another debugger/trace hook is active; observation was not installed')
            return
        self.records.append(record)
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
        record.active = False
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


_HUB = _ObserverHub()


class _Record:
    def __init__(self, runtime, codes, predicate, callback, private, ignored, entry_only):
        pairs = codes.items() if hasattr(codes, 'items') else codes
        self.runtime, self.codes = runtime, {id(code): (code, name) for code, name in pairs}
        self.predicate, self.callback, self.private = predicate, callback, private
        self.ignored, self.entry_only = ignored, entry_only
        self.issues, self.frames, self.pending = [], set(), {}
        self.events = runtime.events
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
        return interested

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


class Runtime:
    def __init__(self, root, baseline='HEAD', *, previous=None):
        self.root, self.baseline = Path(root).resolve(), baseline
        self.previous = previous
        self._baseline_error = ''
        if previous is None:
            from flowguard.map.common import git_run
            try:
                found = git_run(self.root, 'rev-parse', '--verify', baseline + '^{commit}', allowed=(0, 128))
                if found.returncode:
                    raise MapError(found.stderr.decode(errors='replace').strip() or 'baseline is unavailable')
                self.baseline = found.stdout.decode().strip()
            except (MapError, TypeError) as error:
                self.baseline, self._baseline_error = None, str(error)
        self.readings, self.issues, self.events = [], [], []
        self.patches, self.constants, self.unavailable = {}, {}, {}
        self.current_constants = {}
        self._sources, self._registered = {}, set()
        self.test = ''

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
                    previous = self._constants(ast.parse(source), name, seen, historical=historical) if source is not None else {}
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

    def _remember_constant(self, namespace, name, old_value, current, tree):
        if name not in current and ({name, '*', '__getattr__'} & _binding_facts(tree).keys()):
            raise ValueError('current source constant is unavailable: ' + name)
        key = id(namespace), name
        self.constants[key] = namespace, old_value
        self.current_constants[key] = current.get(name, _MISSING)

    def _old_value(self, namespace, name, old_value):
        actual = namespace.get(name, _MISSING)
        same = _literal_equal(actual, self.current_constants[(id(namespace), name)])
        if same is None:
            raise ValueError('cannot distinguish fixture override from source constant: ' + name)
        return old_value if same else actual

    def register(self, function):
        """Read old functions and reachable project helpers, without importing code."""
        fn = sites.unwrap(function)
        if fn in self._registered:
            return self.patches.get(fn)
        self._registered.add(fn)
        try:
            file = Path(inspect.getsourcefile(fn)).resolve().relative_to(self.root).as_posix()
            source = self._source(file)
            if source is None:
                raise ValueError('function has no source in the baseline')
            tree = ast.parse(source, str(self.root / file))
            node = dict(_functions(tree)).get(fn.__qualname__)
            if node is None:
                raise ValueError('function is absent or structurally different in the baseline')
            current = _definition(fn)
            constants = self._constants(tree, fn.__module__)
            current_tree = ast.parse((self.root / file).read_text(encoding='utf-8-sig'))
            current_constants = self._constants(current_tree, fn.__module__, historical=False)
            # All old constants in this module are swapped together: helpers use
            # their own real globals, including imported aliases to functions.
            old_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            for name in (set(fn.__code__.co_names) | old_names) & constants.keys():
                self._remember_constant(fn.__globals__, name, constants[name], current_constants, current_tree)
            local = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
            local.update(n.id for n in sites.own_nodes(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
            old_bindings, current_bindings = _binding_facts(tree), _binding_facts(current_tree)
            for name in old_names - local - {'__name__', '__package__', '__file__'}:
                value = fn.__globals__.get(name)
                if name not in constants and type(value) in (types.ModuleType, type, enum.EnumType, types.FunctionType) and \
                        old_bindings.get(name) != current_bindings.get(name):
                    raise ValueError('baseline import/binding changed: ' + name)
                if name in fn.__globals__ and name not in constants and type(value) not in (
                        types.ModuleType, type, enum.EnumType, types.FunctionType, types.BuiltinFunctionType):
                    raise ValueError('baseline global value is unavailable: ' + name)
            for part in sites.own_nodes(node):
                if isinstance(part, ast.Attribute):
                    owner = _resolve(part.value, fn.__globals__)
                    imported_file = vars(owner).get('__file__') if type(owner) is types.ModuleType else None
                    if imported_file and self._project_file(imported_file):
                        source = self._source(Path(imported_file).resolve().relative_to(self.root).as_posix())
                        values = self._constants(ast.parse(source), owner.__name__) if source is not None else {}
                        value = vars(owner).get(part.attr)
                        if part.attr in values:
                            current_tree = ast.parse(Path(imported_file).read_text(encoding='utf-8-sig'))
                            current_values = self._constants(current_tree, owner.__name__, historical=False)
                            self._remember_constant(vars(owner), part.attr, values[part.attr], current_values, current_tree)
                        elif type(value) not in (types.ModuleType, type, enum.EnumType, types.FunctionType, types.BuiltinFunctionType):
                            raise ValueError('baseline module value is unavailable: ' + ast.unparse(part))
                    elif type(owner) in (type, enum.EnumType):
                        value = vars(owner).get(part.attr)
                        if _simple(value) or type(value) in (tuple, list, dict, set, frozenset):
                            raise ValueError('baseline class value is unavailable: ' + ast.unparse(part))
            old = copy.deepcopy(node)
            defaults = tuple(_literal(value, constants) for value in old.args.defaults) or None
            kwdefaults = {arg.arg: _literal(value, constants) for arg, value in zip(old.args.kwonlyargs, old.args.kw_defaults)
                          if value is not None} or None
            if ast.dump(current.args, include_attributes=False) != ast.dump(old.args, include_attributes=False):
                # Defaults are evaluated above, but an actual parameter-layout
                # change cannot be installed on existing aliases safely.
                def layout(args):
                    return ([a.arg for a in args.posonlyargs], [a.arg for a in args.args],
                            [a.arg for a in args.kwonlyargs], bool(args.vararg), bool(args.kwarg))
                if layout(current.args) != layout(old.args):
                    raise ValueError('baseline parameter layout changed')
            old.decorator_list, old.returns = [], None
            old.args.defaults, old.args.kw_defaults = [], [None] * len(old.args.kwonlyargs)
            for arg in old.args.posonlyargs + old.args.args + old.args.kwonlyargs + \
                    [x for x in (old.args.vararg, old.args.kwarg) if x]:
                arg.annotation = None
            if fn.__code__.co_freevars:
                raise ValueError('baseline closure cannot be safely replaced')
            namespace = {}
            module = ast.fix_missing_locations(ast.Module(body=[old], type_ignores=[]))
            exec(compile(module, str(self.root / file), 'exec'), fn.__globals__, namespace)
            # Existing anchor identity follows the current function location.
            # Keep node.lineno unchanged as separate historical source metadata.
            code = namespace[old.name].__code__.replace(co_qualname=fn.__code__.co_qualname,
                                                       co_firstlineno=fn.__code__.co_firstlineno)
            self.patches[fn] = Patch(fn, code, defaults, kwdefaults, node)
            dependencies = []
            for call in (n for definition in (current, node) for n in sites.own_nodes(definition)
                         if isinstance(n, ast.Call)):
                helper = _resolve(call.func, fn.__globals__)
                if type(helper) is types.FunctionType and self._project(helper):
                    dependencies.append(helper)
                    self.register(helper)
            self.patches[fn].dependencies = tuple(dict.fromkeys(dependencies))
            return self.patches[fn]
        except (ValueError, TypeError, OSError, SyntaxError, ImportError, MapError) as error:
            self.unavailable[fn] = str(error)
            return None

    def _project(self, fn):
        file = inspect.getsourcefile(fn)
        return bool(file and self._project_file(file))

    def _project_file(self, file):
        from flowguard.structure.paths import project_code
        return project_code(file, self.root)

    @contextmanager
    def old_code(self):
        saved = []
        try:
            for fn, patch in self.patches.items():
                saved.append(('function', fn, (fn.__code__, fn.__defaults__, fn.__kwdefaults__)))
                fn.__code__, fn.__defaults__, fn.__kwdefaults__ = patch.code, patch.defaults, patch.kwdefaults
            for (_, name), (namespace, value) in self.constants.items():
                replacement = self._old_value(namespace, name, value)
                saved.append(('constant', (namespace, name), namespace.get(name, _MISSING)))
                if replacement is _MISSING:
                    namespace.pop(name, None)
                else:
                    namespace[name] = replacement
            yield
        finally:
            for kind, target, value in reversed(saved):
                if kind == 'function':
                    target.__code__, target.__defaults__, target.__kwdefaults__ = value
                elif value is _MISSING:
                    target[0].pop(target[1], None)
                else:
                    target[0][target[1]] = value

    def safety(self, function, arguments=None, seen=None, *, historical=False):
        """Conservative static gate; unknown calls remain unavailable."""
        fn = sites.unwrap(function)
        seen = set() if seen is None else seen
        if fn in seen:
            return 'possible nontermination: recursive replay is not proven finite'
        seen = seen | {fn}
        try:
            if historical:
                if fn not in self.patches:
                    return 'baseline function is unavailable: ' + self.unavailable.get(fn, fn.__qualname__)
                node = self.patches[fn].node
            else:
                node = _definition(fn)
        except (OSError, TypeError, SyntaxError):
            return 'source is unavailable for side-effect checking'
        env = {**fn.__globals__, **(arguments or {})}
        if historical:
            try:
                for (_, name), (namespace, value) in self.constants.items():
                    replacement = self._old_value(namespace, name, value)
                    if namespace is fn.__globals__:
                        if replacement is _MISSING:
                            env.pop(name, None)
                        else:
                            env[name] = replacement
            except ValueError as error:
                return str(error)
        def inert(value, trail=frozenset()):
            if value is _INERT:
                return True
            if type(value) in (type(None), bool, int, float, str, bytes, Decimal, date, timedelta):
                return True
            if type(value) is datetime:
                return value.tzinfo is None
            if type(type(value)) is enum.EnumType and _simple(value):
                hooks = {name for base in type(value).__mro__ for name in vars(base)
                         if name.startswith('__') and name.endswith('__')}
                hooks -= {'__module__', '__doc__', '__qualname__', '__annotations__', '__slots__'}
                native = (type(None), types.WrapperDescriptorType, types.MethodDescriptorType,
                          types.ClassMethodDescriptorType, types.GetSetDescriptorType, types.BuiltinFunctionType)
                return all(inspect.getattr_static(type(value), name, None) is inspect.getattr_static(enum.Enum, name, None)
                           or type(inspect.getattr_static(type(value), name, None)) in native for name in hooks)
            if type(value) not in (tuple, list, dict, set, frozenset) or id(value) in trail:
                return False
            children = [*value.keys(), *value.values()] if type(value) is dict else value
            return all(inert(item, trail | {id(value)}) for item in children)

        def locals_of(body):
            result = {arg.arg: [] for arg in (*body.args.posonlyargs, *body.args.args, *body.args.kwonlyargs)}
            for statement in sites.own_nodes(body):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] \
                    if isinstance(statement, (ast.AnnAssign, ast.NamedExpr)) else []
                for target in targets:
                    if isinstance(target, ast.Name):
                        result.setdefault(target.id, []).append(statement.value)
            return result

        bindings = locals_of(node)
        def helper_arguments(target, call, namespace=env, assignments=bindings, trail=frozenset()):
            if any(isinstance(value, ast.Starred) for value in call.args) or any(kw.arg is None for kw in call.keywords):
                raise ValueError('helper spread arguments are not proved inert')
            def value(expression):
                actual = _resolve(expression, namespace)
                return _INERT if actual is _MISSING and data(expression, namespace, assignments, trail) else actual
            bound = inspect.signature(target, follow_wrapped=False).bind(
                *(value(expression) for expression in call.args), **{kw.arg: value(kw.value) for kw in call.keywords})
            bound.apply_defaults()
            return bound.arguments

        def data(expression, namespace=env, assignments=bindings, trail=frozenset()):
            if expression is None:
                return True
            if isinstance(expression, ast.Name):
                if expression.id in assignments:
                    key = id(assignments), expression.id
                    if key in trail:
                        return False
                    values = assignments[expression.id]
                    return (all(data(value, namespace, assignments, trail | {key}) for value in values)
                            if values else inert(namespace.get(expression.id, _MISSING)))
                return inert(_resolve(expression, namespace))
            if isinstance(expression, (ast.Constant, ast.Attribute)):
                return inert(_resolve(expression, namespace))
            if isinstance(expression, (ast.List, ast.Tuple, ast.Set)):
                return all(data(value, namespace, assignments, trail) for value in expression.elts)
            if isinstance(expression, ast.Dict):
                return all(key is not None and data(key, namespace, assignments, trail) and
                           data(value, namespace, assignments, trail) for key, value in zip(expression.keys, expression.values))
            if isinstance(expression, ast.Subscript):
                return data(expression.value, namespace, assignments, trail) and data(expression.slice, namespace, assignments, trail)
            if isinstance(expression, (ast.Compare, ast.BinOp, ast.BoolOp, ast.UnaryOp, ast.IfExp, ast.Slice)):
                return all(data(value, namespace, assignments, trail) for value in ast.iter_child_nodes(expression)
                           if isinstance(value, ast.expr))
            if not isinstance(expression, ast.Call):
                return False
            if isinstance(expression.func, ast.Attribute) and expression.func.attr in {'fetchone', 'fetchall'}:
                execute = expression.func.value
                if isinstance(execute, ast.Call) and isinstance(execute.func, ast.Attribute) and execute.func.attr == 'execute':
                    connection = _resolve(execute.func.value, namespace)
                    return (type(connection) is sqlite3.Connection and connection.row_factory is None
                            and (connection.text_factory is str or connection.text_factory is bytes) and execute.args
                            and isinstance(execute.args[0], ast.Constant) and type(execute.args[0].value) is str
                            and _read_sql(connection, execute.args[0].value))
            target = _resolve(expression.func, namespace)
            if isinstance(expression.func, ast.Attribute) and expression.func.attr in _READ_METHODS:
                if type(_resolve(expression.func.value, namespace)) in (str, bytes, list, tuple, dict, set, frozenset) and inert(_resolve(expression.func.value, namespace)) and all(data(value, namespace, assignments, trail)
                        for value in [*expression.args, *(kw.value for kw in expression.keywords)]):
                    return True
            if any(target is value for value in _SAFE) and target is not Path:
                return all(data(value, namespace, assignments, trail) for value in expression.args) and all(
                    kw.arg is not None and data(kw.value, namespace, assignments, trail) for kw in expression.keywords)
            if type(target) is types.FunctionType and self._project(target) and id(target) not in trail:
                try:
                    body = self.patches[target].node if historical and target in self.patches else _definition(target)
                    arguments = helper_arguments(target, expression, namespace, assignments, trail)
                    return all(data(part.value, {**target.__globals__, **arguments}, locals_of(body), trail | {id(target)})
                               for part in sites.own_nodes(body) if isinstance(part, ast.Return))
                except (OSError, TypeError, ValueError, SyntaxError):
                    return False
            return False

        parts = list(sites.own_nodes(node))
        call_functions = {id(part.func) for part in parts if isinstance(part, ast.Call)}
        for part in parts:
            if isinstance(part, (ast.Global, ast.Nonlocal, ast.Delete, ast.Yield, ast.YieldFrom, ast.Await,
                                 ast.With, ast.AsyncWith, ast.Import, ast.ImportFrom)):
                return 'possible side effect: ' + type(part).__name__
            targets = part.targets if isinstance(part, ast.Assign) else [part.target] \
                if isinstance(part, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr, ast.For, ast.comprehension)) else []
            if any(isinstance(t, (ast.Attribute, ast.Subscript)) for target in targets for t in ast.walk(target)):
                return 'possible side effect: writing an object or collection'
            operands = []
            if isinstance(part, ast.Compare) and not all(isinstance(op, (ast.Is, ast.IsNot)) for op in part.ops):
                operands = [part.left, *part.comparators]
            elif isinstance(part, (ast.BinOp, ast.BoolOp, ast.UnaryOp, ast.Subscript)):
                operands = [value for value in ast.iter_child_nodes(part) if isinstance(value, ast.expr)]
            elif isinstance(part, (ast.If, ast.IfExp, ast.While, ast.Assert)):
                operands = [part.test]
            elif isinstance(part, (ast.For, ast.comprehension)):
                operands = [part.iter]
            elif isinstance(part, ast.Return) and part.value is not None:
                operands = [part.value]
            elif isinstance(part, ast.Attribute) and id(part) not in call_functions:
                operands = [part]
            unsafe = next((value for value in operands if not data(value)), None)
            if unsafe is not None:
                line = part.lineno if historical else fn.__code__.co_firstlineno + part.lineno - 1
                kind = 'unresolved call result' if any(isinstance(value, ast.Call) for value in ast.walk(unsafe)) else 'operand'
                return f'possible side effect: {kind} {ast.unparse(unsafe)[:120]} is not proved inert at line {line}'
            if not isinstance(part, ast.Call):
                continue
            target = _resolve(part.func, env)
            if any(target is value for value in _SAFE):
                if not all(data(value) for value in [*part.args, *(kw.value for kw in part.keywords)]):
                    return 'possible side effect: builtin argument data is not proved inert'
                continue
            if type(target) in (type, enum.EnumType) and issubclass(target, Exception):
                if any(type(inspect.getattr_static(target, name, None)) not in
                       (types.WrapperDescriptorType, types.MethodDescriptorType, types.BuiltinFunctionType)
                       for name in ('__new__', '__init__')):
                    return 'possible side effect: custom exception construction is not proved inert'
                continue
            if type(target) is types.FunctionType and self._project(target):
                try:
                    arguments = helper_arguments(target, part)
                except (TypeError, ValueError):
                    return 'possible side effect: helper arguments are not proved inert'
                problem = self.safety(target, arguments, seen=seen, historical=historical)
                if not problem:
                    continue
                return problem
            if isinstance(part.func, ast.Attribute):
                owner = _resolve(part.func.value, env)
                name = part.func.attr
                if name in _READ_METHODS and type(owner) in (str, bytes, list, tuple, dict, set, frozenset) and inert(owner) and all(data(value) for value in [*part.args, *(kw.value for kw in part.keywords)]):
                    continue
                if name == 'execute' and type(owner) is sqlite3.Connection and part.args:
                    sql = part.args[0]
                    if isinstance(sql, ast.Constant) and type(sql.value) is str and _read_sql(owner, sql.value):
                        continue
                    return 'possible side effect: database statement is not a literal read'
                if name in {'fetchone', 'fetchall'} and isinstance(part.func.value, ast.Call) and \
                        isinstance(part.func.value.func, ast.Attribute) and part.func.value.func.attr == 'execute':
                    continue  # The inner execute is checked independently.
            return 'possible side effect: unresolved call ' + ast.unparse(part.func)
        return ''

    def axes(self, function, bound, explicit=None):
        """Preserve explicit classes plus the actual input without cross-axis guesses.

        Only the generic grid adds source constants and neighbours. Constraint
        readers already supply the complete joint old/current partition.
        """
        axes = {name: list(values) for name, values in (explicit or {}).items()}
        if explicit is None:
            for name, value in bound.arguments.items():
                if _simple(value):
                    axes[name] = [False, True] if isinstance(value, bool) else [value]
        constants = []
        if explicit is None:
            try:
                for site in sites.sites_of(function):
                    constants.extend(sites.site_constants(site))
            except (OSError, ValueError, TypeError, sites.NotMutable):
                pass
            for (_, name), (namespace, value) in self.constants.items():
                if _simple(value):
                    constants.extend((value, namespace.get(name, _MISSING),
                                      self.current_constants[(id(namespace), name)]))
        for name, values in axes.items():
            actual = bound.arguments.get(name)
            values.append(actual)
            for value in ([actual, *constants] if explicit is None else []):
                if type(value) is not type(actual) or isinstance(value, bool):
                    continue
                step = cells.epsilon(value)
                if step is not None:
                    values.extend((value - step, value, value + step))
            unique = []
            for value in values:
                if not any(outcome_equal(value, old) for old in unique):
                    unique.append(value)
            axes[name] = unique
        return axes

    def observe(self, original, bound, *, owner=None, name='', axes=None, private=False):
        """Metadata and replay are private; the real call always runs outside them."""
        owner = sites.unwrap(owner or original)
        if (_PRIVATE.get() and not private) or owner in _OBSERVING.get():
            return original(*bound.args, **bound.kwargs)
        token = _PRIVATE.set(True)
        observing = _OBSERVING.set(_OBSERVING.get() | {owner})
        try:
            self._replay_rows(original, bound, owner=owner, name=name, axes=axes)
        finally:
            _OBSERVING.reset(observing)
            _PRIVATE.reset(token)
        return original(*bound.args, **bound.kwargs)

    def _replay_rows(self, original, bound, *, owner, name, axes):
        """No normal call here, including when metadata or a replay gate is grey."""
        reading = Reading(name or owner.__qualname__, owner.__module__ + ':' + owner.__qualname__,
                          test=self.test, baseline=self.baseline)
        self.readings.append(reading)
        problem = self.safety(original, bound.arguments)
        if problem:
            reading.status, reading.reasons = 'grey', [problem]
            reading.comparison_status, reading.comparison_reasons = 'grey', [problem]
            return
        patch = self.register(owner)
        old_problem = self.safety(owner, bound.arguments, historical=True)
        if old_problem:
            reading.comparison_status = 'grey'
            reading.comparison_reasons.append(old_problem)
            patch = None
        supplied_axes = axes is not None
        if supplied_axes:
            axes = {name: list(values) for name, values in axes.items()}
            unsupported = [name for name, values in axes.items() if not _simple(bound.arguments.get(name))
                           or any(not _simple(value) for value in values)]
            if unsupported:
                reading.status, reading.reasons = 'grey', ['input is not an inert simple value: ' + ', '.join(unsupported)]
                return
        axes = self.axes(original, bound, axes)
        reading.context = tuple(n for n in bound.arguments if n not in axes)
        unsupported = [name for name, values in axes.items() if not _simple(bound.arguments.get(name))
                       or any(not _simple(value) for value in values)]
        if unsupported:
            reading.status, reading.reasons = 'grey', ['input is not an inert simple value: ' + ', '.join(unsupported)]
            return
        if not axes:
            reading.status, reading.reasons = 'grey', ['no finite simple input classes']
            return
        baseline = _value(original, bound)
        for values in itertools.product(*axes.values()):
            inputs = dict(zip(axes, values))
            arguments = {**bound.arguments, **inputs}
            now = _value(original, _binding(bound.signature, arguments))
            old = None
            if patch is not None:
                with self.old_code():
                    old = _value(patch.callable(), _binding(bound.signature, arguments))
            reading.rows.append((inputs, now))
            if patch is not None and not outcome_equal(old, now):
                reading.changed.append((inputs, old, now))
        again = _value(original, bound)
        if not outcome_equal(baseline, again):
            reading.status, reading.reasons = 'grey', ['original-value recheck changed: possible side effect or unstable input']
            reading.rows.clear()
            reading.changed.clear()
        if not supplied_axes:
            reading.reasons.append('comparison grid is not a proof of partition completeness')

    @contextmanager
    def hook(self, function, *, name='', axes=None, private=False):
        owner = sites.unwrap(function)
        _private_call(self.register, owner)
        def callback(original, bound):
            if (_PRIVATE.get() and not private) or owner in _OBSERVING.get():
                return original(*bound.args, **bound.kwargs)
            if callable(axes):
                values = _private_call(axes, original, bound)
            else:
                values = axes
            return self.observe(original, bound, owner=owner, name=name, axes=values, private=private)
        callback.__flowguard_transport__ = (type(self).observe.__code__,)
        with sites.intercepted(owner, callback) as original:
            yield original

    @staticmethod
    def observer_issues():
        return [issue for record in _HUB.records for issue in record.issues]

    def record(self, codes=(), *, predicate=None, callback=None, private=False, ignored=(), entry_only=False):
        """One hub owns local anchor events and explicit dynamic footprints."""
        return _Record(self, codes, predicate, callback, private, ignored, entry_only)

    def replay(self, item, *, nextitem=None):
        """Called after the real protocol has torn down its function fixtures.

        Shared fixtures cannot be silently reset: doing that also resets their
        lifecycle for the surrounding real suite. Return unavailable instead.
        """
        import pytest
        from _pytest.nodes import Node
        active = [node for node in item.session._setupstate.stack if isinstance(node, pytest.Item)]
        ancestors = set(item.listchain()) - {item}
        if any(node not in ancestors for node in active):
            return dict(status='grey', reasons=['replay requires a completed test protocol'])
        definitions = getattr(getattr(item, '_fixtureinfo', None), 'name2fixturedefs', {})
        borrowed = [name for name, defs in definitions.items() if active and defs and defs[-1].scope == 'function'
                    and defs[-1].cached_result is not None]
        if borrowed:
            return dict(status='grey', reasons=['function fixture is still owned by an active ancestor: ' + ', '.join(borrowed)])
        from _pytest.fixtures import pytestconfig
        from _pytest.tmpdir import tmp_path_factory
        builtins = {inspect.unwrap(pytestconfig), inspect.unwrap(tmp_path_factory)}
        shared = [name for name, defs in definitions.items() if defs and defs[-1].scope != 'function'
                  and inspect.unwrap(defs[-1].func) not in builtins]
        if shared:
            return dict(status='grey', reasons=['shared fixture lifecycle is not replay-isolated: ' + ', '.join(shared)])
        needed = set(item.listchain())
        retained = set(nextitem.listchain()) if nextitem is not None else set()
        for node, (finalizers, _) in item.session._setupstate.stack.items():
            if node not in needed and node in retained and (len(finalizers) > 1 or
                    getattr(node.teardown, '__func__', None) is not Node.teardown):
                return dict(status='grey', reasons=['pending shared collector lifecycle cannot be reset: ' + node.nodeid])
        from _pytest.runner import runtestprotocol
        errors = []
        class Reports:
            def pytest_runtest_makereport(self, item, call):
                if call.excinfo is not None:
                    errors.append((call.when, call.excinfo.value))
        recorder = Reports()
        item.config.pluginmanager.register(recorder)
        token = _PRIVATE.set(True)
        try:
            try:
                item.session._setupstate.teardown_exact(item)
            except BaseException as error:
                if isinstance(error, (KeyboardInterrupt, SystemExit, GeneratorExit, pytest.exit.Exception)):
                    raise
                return dict(status='grey', reports=[], errors=[('teardown', error)],
                            reasons=['collector teardown failed: ' + type(error).__name__ + ': ' + str(error)])
            reports = runtestprotocol(item, log=False, nextitem=nextitem)
            failures = [r for r in reports if not r.passed]
            return dict(status='grey' if failures else 'ok', reports=reports,
                        errors=errors, reasons=[r.when + ': ' + r.outcome for r in failures])
        finally:
            _PRIVATE.reset(token)
            item.config.pluginmanager.unregister(recorder)
