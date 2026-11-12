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
from flowguard.map.common import MapError, read_source

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


_MAIN = ast.dump(ast.parse('__name__ == "__main__"', mode='eval').body)


def _immutable(value):
    """A value no code can change in place: what a project module may give another module's sealed def."""
    return type(value) in (type(None), bool, int, float, complex, str, bytes) or (
        type(value) is tuple and all(_immutable(item) for item in value))


def _loads(tree):
    """Where running this module's top level could change a value its source assigns, as 'LINE what', or ''.
    A function body does not run when the module loads; its decorators, defaults and annotations do, and
    so does every other statement: a call, a decorator, a `with` block, a class made from a base, keyword
    or decorator, or an attribute or item write could rebind a module's names or change them in place."""
    todo = list(reversed(tree.body))
    while todo:
        node = todo.pop()
        if isinstance(node, ast.If) and ast.dump(node.test) == _MAIN:
            todo.extend(reversed(node.orelse))      # the `__main__` block never runs on import
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if getattr(node, 'decorator_list', None):
                return f'{node.decorator_list[0].lineno} runs a decorator'
            arguments = node.args
            todo.extend([*arguments.defaults, *(value for value in arguments.kw_defaults if value is not None),
                         *(argument.annotation for argument in [*arguments.posonlyargs, *arguments.args,
                           *arguments.kwonlyargs, *([arguments.vararg] if arguments.vararg else []),
                           *([arguments.kwarg] if arguments.kwarg else [])] if argument.annotation is not None),
                         *([node.returns] if getattr(node, 'returns', None) is not None else [])])
            continue
        if isinstance(node, ast.ClassDef) and (node.bases or node.keywords or node.decorator_list):
            return f'{node.lineno} defines a class from a base, keyword or decorator'
        if isinstance(node, ast.Call):
            return f'{node.lineno} calls a function'
        if isinstance(node, (ast.With, ast.AsyncWith)):
            return f'{node.lineno} enters a with block'
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return f'{node.lineno} writes an attribute or item'
        todo.extend(reversed(list(ast.iter_child_nodes(node))))
    return ''


def _loaded_imports(tree):
    """The import statements that run when the module loads: none inside a function body or `__main__` block."""
    todo = list(tree.body)
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
        elif isinstance(node, ast.If) and ast.dump(node.test) == _MAIN:
            todo.extend(node.orelse)
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            todo.extend(child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt) or
                        isinstance(child, (ast.excepthandler, ast.match_case)))


@dataclass(frozen=True)
class _Module:
    """One project module source the sealed environment reads literal constants from (`Runtime.imports`)."""
    runtime: object
    file: str
    name: str
    old: bool

    def literals(self, binding):
        try:
            return self.runtime._literals(self.file, self.old)
        except Refused as error:        # the module does not parse: only this binding is refused
            raise Refused('uses ' + binding + ': ' + str(error)) from None

    def _loading(self, binding):
        try:
            return self.runtime._loading(self.file, self.name, self.old)
        except Refused as error:        # a module it loads does not parse
            raise Refused('uses ' + binding + ': ' + str(error)) from None

    def value(self, member):
        reason = self._loading(member)
        if reason:
            raise Refused('uses ' + member + ': ' + reason)
        return self.literals(member)[member]

    def namespace(self, binding):
        """The module as attribute chains read it: its literal constants, or none when loading it could change
        them (`_withheld` then keeps why, for the attribute chain that reads one; sealed code reads no `_` name)."""
        reason, literals = self._loading(binding), self.literals(binding)
        return types.SimpleNamespace(_withheld=(reason, frozenset(literals))) if reason else types.SimpleNamespace(**literals)


class _Import:
    """An import binding of the sealed file, read only when a sealed function reads its name: `import X.Y`
    (`member` None; `bound` when it binds X rather than an `as` name) or `from X import member`. `imports`
    finds a project module's source (`Runtime.imports`); nothing is imported or executed."""
    __slots__ = ('imports', 'module', 'level', 'member', 'bound')

    def __init__(self, imports, module, level, member=None, bound=False):
        self.imports, self.module, self.level, self.member, self.bound = imports, module, level, member, bound

    def value(self):
        """The literal or module namespace the binding reads, or _MISSING when it is no project literal;
        Refused when loading the module could change the value."""
        if self.member is None:
            found = self.imports(self.module, 0)
            if found is None:
                return _MISSING
            space, parts = found.namespace(self.module), self.module.split('.')
            for depth in range(len(parts) - 1, 0, -1) if self.bound else ():
                parent = self.imports('.'.join(parts[:depth]), 0)
                outer = parent.namespace(self.module) if parent is not None else types.SimpleNamespace()
                setattr(outer, parts[depth], space)
                space = outer
            return space
        owner = self.imports(self.module, self.level)
        if owner is not None and self.member in owner.literals(self.member):
            return owner.value(self.member)
        child = self.imports(self.module + '.' + self.member if self.module else self.member, self.level)
        return child.namespace(self.member) if child is not None else _MISSING      # `from package import module`


_FOLDED = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.FloorDiv: '//', ast.Mod: '%', ast.Pow: '**',
           ast.UAdd: '+', ast.USub: '-'}


def _foldable(node, env):
    """Whether a right side is built only from literals, signs, + - * / // % ** and names, so that no value it reads
    can be changed through the new binding: an operation gives a new value, and a bare name is folded only when it
    names a number, a text or another fold (an alias of a list or a module could change it in place)."""
    if isinstance(node, ast.Name):
        return type(env.get(node.id)) in (int, float, str, _Fold)
    return all(isinstance(part, (ast.Name, ast.Load, ast.Constant, ast.UnaryOp, ast.BinOp, *_FOLDED)) for part in ast.walk(node))


class _Fold:
    """A top-level constant whose right side is `_foldable` (design 4.5): folded by walking it, nothing runs, when a
    sealed function reads it. `bindings` are the values its names had at its line (a literal, an `_Import`, an
    earlier `_Fold`, or _MISSING); a name the module may rebind later (`global` in a function, `blocked` when the
    whole top level is read) is no constant. `order` is its place in the source (line, column): it reads only earlier
    folds."""
    __slots__ = ('name', 'node', 'bindings', 'blocked', 'order', 'result')

    def __init__(self, name, node, bindings, blocked, order):
        self.name, self.node, self.bindings, self.blocked, self.order, self.result = name, node, bindings, blocked, order, None

    def folded(self):
        """(value, '') or (None, why it does not fold). The earlier folds it reads are computed first, in source order,
        so a long chain needs no deep recursion; an imported name is read as `_Import.value` reads it (Refused when
        loading its module could change it)."""
        if self.result is None:
            needed, todo = {}, [self]
            while todo:
                fold = todo.pop()
                if fold.result is None and id(fold) not in needed:
                    needed[id(fold)] = fold
                    todo.extend(item for item in fold.bindings.values() if type(item) is _Fold)
            for fold in sorted(needed.values(), key=lambda item: item.order):
                fold.result = fold._compute()
        return self.result

    def value(self):
        value, why = self.folded()
        if why:
            raise Refused(f'uses {self.name}: {why}')
        return value

    def _compute(self):
        def lookup(name):
            found = self.bindings.get(name, _MISSING)
            if type(found) is _Import:
                found = found.value()
            if found is _MISSING or name in self.blocked:
                return None, f'{name} is not a number or text constant before it'
            if type(found) is _Fold:
                value, why = found.result
                return (None, f'uses {name}: {why}') if why else (value, '')
            return found, ''
        return _fold(self.node, lookup)


def _fold(node, lookup, leaf=None):
    """The value of a right side built from literals, signs, + - * / // % ** and names (`lookup(name)` gives (value,
    why)), one operation at a time with Python's numbers (`features.fold_step`, bounded: nothing past a bound is
    computed), walking the syntax tree without recursion: (value, '') or (None, why it does not fold). Any other part
    is `leaf(part)`'s (value, why), or does not fold. The Python side of `vitest._ecma_fold`; `_Fold` and the old
    module constants of `_literal` fold with it."""
    from ..structure.features import fold_step
    stack, done = [(node, False)], []
    while stack:
        node, ready = stack.pop()
        arithmetic = isinstance(node, (ast.UnaryOp, ast.BinOp)) and type(node.op) in _FOLDED
        if isinstance(node, ast.Constant):
            done.append(node.value)
            continue
        if isinstance(node, ast.Name) or not arithmetic:
            value, why = lookup(node.id) if isinstance(node, ast.Name) else \
                leaf(node) if leaf is not None else (None, 'cannot fold ' + type(node).__name__)
            if why:
                return None, why
            done.append(value)
            continue
        children = [node.operand] if isinstance(node, ast.UnaryOp) else [node.left, node.right]
        if not ready:
            stack.append((node, True))
            stack.extend((child, False) for child in reversed(children))
            continue
        value, why = fold_step(_FOLDED[type(node.op)], done[-len(children):])
        if why:
            return None, why
        del done[-len(children):]
        done.append(value)
    return done[0], ''


def _receiver(function, arguments):
    """The parameter holding the receiver of a method call (self, or cls of a class method), or None: the
    function is that argument's class attribute as a plain or class method, found without running code."""
    qual = function.__qualname__
    if '.' not in qual or qual.rpartition('.')[0].endswith('<locals>') or not arguments:
        return None
    first, value = next(iter(arguments.items()))
    owner = value if type in type(value).__mro__ else type(value)
    found = inspect.getattr_static(owner, function.__name__, None)
    found = found.__func__ if type(found) is classmethod else found
    return first if found is function else None


def _register(value, spaces):
    """Each module namespace a resolved import binding holds, as a namespace attribute chains may read."""
    if type(value) is types.SimpleNamespace:
        spaces[id(value)] = value
        for item in vars(value).values():
            _register(item, spaces)


def _scope(tree, imports=None, *, imported=False):
    """The sealed globals of one module's top level: its literal constants (`ast.literal_eval`, or a `_Fold` of
    literals and constants above it), the whitelisted modules, the import bindings of project modules (`_Import`,
    when `imports` finds their source), its functions and the names nothing may read. A name any function
    declares `global` may be rebound while the program runs and is never a value. Returns (env, functions,
    blocked, namespaces by id, literal constant names). For an `imported` module only its literal constants are
    read: a star import there hides the ones before it."""
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
                elif imports is not None:    # `import X.Y as Z` binds the module X.Y; `import X.Y` binds X
                    values[name] = _Import(imports, a.name, 0, bound=not a.asname)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name == '*':
                    if not imported:
                        raise Refused('uses wildcard import')
                    literals.clear()        # any name before it may be rebound
                    continue
                name = a.asname or a.name
                names.add(name)
                if not n.level and n.module in modules:
                    if not a.name.startswith('_') and hasattr(modules[n.module], a.name):
                        values[name] = getattr(modules[n.module], a.name)
                elif imports is not None and not a.name.startswith('_'):
                    values[name] = _Import(imports, n.module or '', n.level, a.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            if n.value is None:
                continue
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = {p.id for target in targets for p in ast.walk(target) if isinstance(p, ast.Name)}
            try:
                value = ast.literal_eval(n.value)
            except (ValueError, TypeError, SyntaxError):
                value = _MISSING
                if all(isinstance(target, ast.Name) for target in targets) and _foldable(n.value, env):
                    value = _Fold(targets[0].id, n.value, {p.id: env.get(p.id, _MISSING) for p in ast.walk(n.value)
                                                           if isinstance(p, ast.Name)}, blocked, (n.lineno, n.col_offset))
                else:
                    names.update(p.id for p in ast.walk(n.value) if isinstance(p, ast.Name))
            for target in targets:
                if value is not _MISSING and isinstance(target, ast.Name):
                    values[target.id] = value
        else:
            names = {p.id for p in ast.walk(n) if isinstance(p, ast.Name)}
            names.update(p.name for p in ast.walk(n) if isinstance(p, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef,
                                                                       ast.MatchAs, ast.MatchStar, ast.ExceptHandler)) and p.name)
            names.update(p.rest for p in ast.walk(n) if isinstance(p, ast.MatchMapping) and p.rest)
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
    for name in {name for node in ast.walk(tree) if isinstance(node, ast.Global) for name in node.names}:
        functions.pop(name, None)
        env.pop(name, None)
        blocked.add(name)
        literals.discard(name)
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
        for part in ast.walk(n):        # an import or a fold is read only when the function or a helper reads its name
            if isinstance(part, ast.Name) and part.id not in local and type(env.get(part.id)) is _Import:
                value = env[part.id].value()
                if value is _MISSING:
                    del env[part.id]
                    blocked.add(part.id)
                else:
                    env[part.id] = value
                    _register(value, spaces)
            elif isinstance(part, ast.Name) and part.id not in local and type(env.get(part.id)) is _Fold:
                env[part.id] = env[part.id].value()
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
                    reason, names = vars(namespace).get('_withheld', ('', ()))
                    raise Refused('uses ' + part.attr + ': ' + reason if part.attr in names else 'uses unavailable attribute ' + part.attr)
                if part.attr.startswith('_') or isinstance(part.ctx, (ast.Store, ast.Del)) or part.attr not in _METHODS and not module:
                    raise Refused('uses attribute ' + part.attr)
        todo.extend(p.id for p in ast.walk(n) if isinstance(p, ast.Name) and isinstance(p.ctx, ast.Load)
                    and p.id in functions and p.id not in local)
        definitions.append(n)
    for name in [name for name, value in env.items() if type(value) in (_Import, _Fold)]:
        del env[name]       # never read: the sealed code has no way to reach it
    exec(compile(ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[])),
                 '<flowguard-sealed>', 'exec'), env)
    return env[qual]


def _module_at(path, file, module):
    """The module name `path` has under the import root that names `file` `module` (a moved file's name at
    the baseline); '' when `path` is outside that root, so no project import resolves from it."""
    def names(rel):
        parts = list(Path(rel).with_suffix('').parts)
        return parts[:-1] if parts and parts[-1] == '__init__' else parts
    own, old, dotted = names(file), names(path), module.split('.') if module else []
    if not dotted or own[len(own) - len(dotted):] != dotted:
        return ''
    root = own[:len(own) - len(dotted)]
    return '.'.join(old[len(root):]) if old[:len(root)] == root and len(old) > len(root) else ''


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
    """The value of an old module constant's right side, computed without running code or a previous module
    initializer: literals and tuples, lists, sets and dicts of values, the `constants` above it, signs and
    + - * / // % ** of numbers and texts (`_fold`, bounded as the sealed environments fold: an exponent outside
    -64..64, a number above 2**256 or a text over 10,000 characters is not computed), and calls of the inert
    constructors Decimal, date, datetime and timedelta. Raises ValueError with why it is not folded."""
    constructors = (Decimal, date, datetime, timedelta)
    allowed = {name: value for name, value in constants.items() if any(value is fn for fn in constructors)}
    def lookup(name):
        return (constants[name], '') if name in constants else (None, 'old constant/default names an unknown value: ' + name)
    def value(part):
        found, why = _fold(part, lookup, leaf)
        if why:
            raise ValueError(why)
        return found
    def leaf(part):
        if isinstance(part, (ast.Tuple, ast.List, ast.Set)) and not any(isinstance(e, ast.Starred) for e in part.elts):
            items = [value(e) for e in part.elts]
            return (tuple(items) if isinstance(part, ast.Tuple) else items if isinstance(part, ast.List) else set(items)), ''
        if isinstance(part, ast.Dict) and None not in part.keys:
            return {value(k): value(v) for k, v in zip(part.keys, part.values)}, ''
        if isinstance(part, ast.Call) and isinstance(part.func, ast.Name) and part.func.id in allowed \
                and not any(isinstance(a, ast.Starred) for a in part.args) and all(k.arg for k in part.keywords):
            return allowed[part.func.id](*map(value, part.args), **{k.arg: value(k.value) for k in part.keywords}), ''
        return None, 'old constant/default is not an inert expression'
    return value(node)

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
    """Top-level binding identity; function bodies have their own fingerprints. A bare annotation (`LIMIT: int`)
    binds nothing, as `_scope` reads it."""
    result = {}
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign) and statement.value is None:
            continue
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


def _binding_reads(tree):
    """{name: the names its top-level binding reads}, by the statement that binds it last, as `_binding_facts` reads
    it. A function, class or import binding reads nothing here (a same-file function is followed by its own body)."""
    reads = {}
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign) and statement.value is None:
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            reads.pop(statement.name, None)
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            for alias in statement.names:
                reads.pop(alias.asname or alias.name.split('.')[0], None)
        elif isinstance(statement, ast.Delete):
            for node in ast.walk(statement):
                if isinstance(node, ast.Name):
                    reads.pop(node.id, None)
        else:
            value = statement.value if isinstance(statement, (ast.Assign, ast.AnnAssign)) else statement
            loaded = {node.id for node in ast.walk(value) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    reads[node.id] = loaded
    return reads


def _read_through(names, reads):
    """`names` and every name a binding of `reads` (`_binding_reads`) among them reads, at any depth: with
    LIMIT = BASE * 2, a function reading LIMIT reads BASE too."""
    found, todo = set(names), list(names)
    while todo:
        for name in reads.get(todo.pop(), ()):
            if name not in found:
                found.add(name)
                todo.append(name)
    return found


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
        self._texts, self._exported, self._loaded = {}, {}, {}     # project modules the sealed environment reads
        self._renames = None        # {path now: path at the baseline} of the files this change moved (`baseline_place`)
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
        project source file (never an installed package, a link out of the project or an environment). A
        package's `__init__.py` wins over a module file of the same name, as in Python. The baseline source
        when `old`. Each answer is a `_Module`; None when no project file has the name."""
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
            for candidate in (Path(*prefix, *name.split('.'), '__init__.py'), Path(*prefix, *name.split('.')).with_suffix('.py')):
                relative = candidate.as_posix()
                if self._project_file(str(self.root / relative)) and self._text(relative, old) is not None:
                    return _Module(self, relative, name, old)
            return None
        return find

    def _text(self, file, old):
        """A project source as Python reads it (PEP 263), once per runtime; the baseline blob when `old`;
        None when there is no such file."""
        if old:
            return self._source(file)
        if (file, old) not in self._texts:
            path = self.root / file
            self._texts[file, old] = read_source(path) if path.is_file() else None
        return self._texts[file, old]

    def _tree(self, file, old):
        try:
            return self._parsed(self._text(file, old), file)
        except SyntaxError as error:    # its own words: str() names the file differently on Windows
            raise Refused(f'{file} does not parse: {error.msg} (line {error.lineno})') from None
        except ValueError as error:     # a null byte on Python 3.11
            raise Refused(f'{file} does not parse: {error}') from None

    def _literals(self, file, old):
        """{name: value} of the literal constants a project module gives another module's sealed def: assigned
        once at its top level to an immutable literal or one that folds (`_Fold`), never rebound and never `global`
        in a function (`_scope` of an imported module). Read from its source once per runtime."""
        if (file, old) not in self._exported:
            env, _, _, _, literals = _scope(self._tree(file, old), imported=True)
            values = {name: env[name].folded() if type(env[name]) is _Fold else (env[name], '') for name in literals}
            self._exported[file, old] = {name: value for name, (value, why) in values.items()
                                         if not name.startswith('_') and not why and _immutable(value)}
        return self._exported[file, old]

    def _loading(self, file, module, old):
        """Why loading project module `module` (source `file`) could change a value its source assigns, or ''.
        Each package above it, the module itself and every project module these import load first, and none
        may call a function, run a decorator or write an attribute or item while it loads (`_loads`). Each
        source is read once, and the answer is kept, for this runtime. What runs later, outside these modules
        (the importing file's own top level, the program's setup, a test's monkeypatch), can still write a
        module attribute, as it can a same-file constant: the comparison reads the source's value."""
        if (file, old) not in self._loaded:
            reason, todo, seen = '', [(file, module)], {file}
            while todo and not reason:
                current, name = todo.pop()
                tree = self._tree(current, old)
                where = _loads(tree)
                reason = current + ':' + where + ' when the module loads' if where else ''
                find = self.imports(current, name, old)
                targets = [('.'.join(name.split('.')[:depth]), 0) for depth in range(1, name.count('.') + 1)]
                for node in _loaded_imports(tree):
                    if isinstance(node, ast.Import):
                        targets += [('.'.join(a.name.split('.')[:depth]), 0) for a in node.names
                                    for depth in range(1, a.name.count('.') + 2)]
                    else:
                        base = node.module or ''
                        targets += [(base, node.level), *((base + '.' + a.name if base else a.name, node.level)
                                                          for a in node.names if a.name != '*')]
                        targets += [('.'.join(base.split('.')[:depth]), node.level) for depth in range(1, base.count('.') + 1)]
                for target in targets:
                    found = find(*target)
                    if found is not None and found.file not in seen:
                        seen.add(found.file)
                        todo.append((found.file, found.name))
            self._loaded[file, old] = reason
        return self._loaded[file, old]

    def baseline_place(self, file, module):
        """(path, module name) a project file had at the baseline: its old path and the module name that path has
        under the same import root when this change moved it (`git_renames`, read once per runtime), else its own.
        A runtime given its `previous` sources reads no renames."""
        if self._renames is None:
            from flowguard.map.common import git_renames
            self._renames = git_renames(self.root, self.baseline) if self.previous is None and self.baseline else {}
        old = self._renames.get(file)
        return (old, _module_at(old, file, module)) if old else (file, module)

    def _input(self, function, historical=False):
        """(fn, file, module, source) of a function's source: its file now, or (`historical`) its baseline version,
        which a file this change moved has at its old path, with that path's module name (`baseline_place`), so the
        imports of the baseline source resolve as they did there."""
        fn = sites.unwrap(function)
        file, module = Path(inspect.getsourcefile(fn)).resolve().relative_to(self.root).as_posix(), fn.__module__
        if historical:
            file, module = self.baseline_place(file, module)
        source = self._source(file) if historical else (self.root / file).read_text(encoding='utf-8-sig')
        if source is None:
            raise ValueError('function has no baseline source')
        return fn, file, module, source

    def full(self, function):
        """Twenty distinct encoded inputs of the function are recorded: its hook comes off."""
        return len(self._seen.get(sites.unwrap(function), ())) >= 20

    def safety(self, function, arguments=None, seen=None, *, historical=False, node=None, reads=None):
        """Compatibility qualification for explicit callers; ordinary hooks never use it."""
        owner = self if historical else (_HISTORICAL.get() or self)
        try:
            old = historical or _HISTORICAL.get() is not None
            fn, file, module, source = owner._input(function, historical=old)
            _closed(source, fn.__qualname__, owner.imports(file, module, old))
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
            function, file, module, source = owner._input(fn, historical=historical)
            answer = sealed(source, function.__qualname__, list(bound.args), dict(bound.kwargs),
                            owner.imports(file, module, historical))
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
            fn, file, module, source = self._input(original)
            parameters = ', '.join(inspect.signature(fn, follow_wrapped=False).parameters)
            values = {}
            for name, expression in fields:
                body = source + f'\ndef _flowguard_field({parameters}):\n    return ({expression})\n'
                answer = sealed(body, '_flowguard_field', list(bound.args), dict(bound.kwargs), self.imports(file, module))
                if answer['status'] != 'ok':
                    reading.field_reasons.append('field ' + name + ': ' + answer.get('reason', str(answer.get('error'))))
                    return
                values[name] = answer['value']
            reading.fields = values
        except (OSError, ValueError, TypeError) as error:
            reading.field_reasons.append(str(error))

    def observe(self, original, bound, *, owner=None, name='', axes=None, private=False, fields=(), line=0, recorded=None,
                named=False):
        started = _PERF()
        function = sites.unwrap(owner or original)
        if (_PRIVATE.get() and not private) or function in _OBSERVING.get() \
                or (not private and not named and len(self._seen.get(function, ())) >= 20):
            return original(*bound.args, **bound.kwargs)
        bound.apply_defaults()
        receiver = _receiver(function, bound.arguments)
        try:    # the call's arguments decide args and kwargs; a method call is looked up without its receiver
            key, reason = _json({k: v for k, v in bound.arguments.items() if k != receiver}), ''
        except (Refused, ValueError, TypeError, RecursionError) as error:
            key, reason = None, str(error)
        seen = self._seen.setdefault(function, {}) if not private else None
        if seen is not None and key is not None and key in seen:
            # This encoded input was recorded before (design 4.5): one encode and one lookup, no reading.
            seen[key].tests.add(self.test)
            self.seconds += _PERF() - started
            return original(*bound.args, **bound.kwargs)
        token = _PRIVATE.set(True)
        observing = _OBSERVING.set(_OBSERVING.get() | {function})
        reading = Reading(name or function.__qualname__, function.__module__ + ':' + function.__qualname__,
                          test=self.test, baseline=self.baseline or '', tests={self.test})
        reading.actual_inputs = dict(bound.arguments)
        if key is None or receiver is not None:
            reading.reasons.append(reason or 'not JSON data')       # a receiver is never JSON data
        else:
            reading.sample = dict(args=json.loads(_json(list(bound.args))), kwargs=json.loads(_json(dict(bound.kwargs))),
                                  inputs=json.loads(key))
        if seen is not None:
            # A call that cannot be encoded cannot be looked up again: it counts as one more distinct input.
            seen[key if key is not None else (None, len(seen))] = reading
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
    def hook(self, function, *, name='', axes=None, private=False, fields=(), line=0, recorded=None, named=False):
        """Record the real calls of `function` while the hook is open. `named`: the test running now is the
        one a calibrated anchor names, whose calls are recorded even after 20 distinct inputs."""
        function = sites.unwrap(function)
        if not private and not named and self.full(function):
            yield function
            return
        def callback(original, bound):
            return self.observe(original, bound, owner=function, name=name, axes=axes,
                                private=private, fields=fields, line=line, recorded=recorded, named=named)
        callback.__flowguard_transport__ = (type(self).observe.__code__,)
        with sites.intercepted(function, callback, keep=lambda: private or named or not self.full(function)) as original:
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
                _, file, module, source = self._input(fn, historical=True)
                compiled = _closed(source, fn.__qualname__, self.imports(file, module, True))
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

    def _constants(self, tree, module, seen=None, *, historical=True, reasons=None):
        """{name: value} of a module's top-level constants as `_literal` computes them from its source, in source
        order, and of the inert constants its `from` imports bind. `reasons` (a dict) receives, for each name an
        assignment binds to no such value, why: the error `_literal` or the constructor it calls raises."""
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
                except (ValueError, TypeError, SyntaxError, ArithmeticError) as error:
                    for name in names:
                        constants.pop(name, None)
                        if reasons is not None:
                            reasons[name] = str(error) or type(error).__name__
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
