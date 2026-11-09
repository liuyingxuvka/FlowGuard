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
import os
from pathlib import Path
import re
import sqlite3
import sys
import textwrap
import threading
import types

from . import cells, sites
from flowguard.map.common import MapError

is_transport = sites.is_transport
transport = sites.transport

_PRIVATE = ContextVar('flowguard_runtime_private', default=False)
_OBSERVING = ContextVar('flowguard_runtime_observing', default=frozenset())
_MISSING = object()
_SAFE = {bool, int, float, str, bytes, tuple, list, dict, set, frozenset, len, abs, min,
         max, sum, all, any, sorted, round, isinstance, issubclass, type, range, enumerate,
         zip, Decimal, date, datetime, timedelta, Path}


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


def _neighbours(value):
    """Representable neighbours of exact native quantities, without user operators."""
    if not any(type(value) is kind for kind in (int, float, Decimal, date, datetime, timedelta)):
        return
    try:
        step = cells.epsilon(value)
    except ArithmeticError:
        return
    if step is not None:
        for lower in (True, False):
            try:
                candidate = value - step if lower else value + step
                if _simple(candidate) and (type(candidate) is not Decimal or candidate.is_finite()):
                    yield candidate
            except ArithmeticError:
                pass  # A native endpoint has no representable neighbour here.


# ---- replay guard -------------------------------------------------------------------------------
# A call-site replay (the current code, the baseline code swapped in, the original-value recheck)
# runs its calls inside one guard: only in the replaying thread and only while a replayed call runs.
# The audit hook refuses file writes, processes, threads and network access before they happen.
# sqlite3 connections in the arguments (and their attributes, two levels deep) refuse writing
# statements and return to a savepoint afterwards; connections opened during a call refuse them too.
# Any refusal voids the whole replay, also when the replayed code catches it. Arguments the guard
# cannot see into (a file open for writing, a socket, another database driver) are not replayed.

class Refused(BaseException):
    """Raised in the audit hook, so the refused operation does not happen. A BaseException: an
    ordinary `except Exception` in the replayed code does not continue with further effects."""


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_REFUSED_EVENTS = {
    'os.remove': '删除文件', 'os.rename': '改名或移动文件', 'os.rmdir': '删除目录', 'os.mkdir': '新建目录',
    'os.chmod': '改文件权限', 'os.chown': '改文件属主', 'os.utime': '改文件时间', 'os.truncate': '截断文件',
    'os.link': '新建链接', 'os.symlink': '新建链接', 'shutil.rmtree': '删除目录树',
    'subprocess.Popen': '启动子进程', 'os.system': '执行 shell 命令', 'os.exec': '替换当前进程',
    'os.spawn': '启动子进程', 'os.posix_spawn': '启动子进程', 'os.fork': '复制当前进程', 'os.forkpty': '复制当前进程',
    'os.kill': '给进程发信号', 'os.putenv': '改环境变量', 'os.unsetenv': '改环境变量',
    'socket.connect': '连接网络', 'socket.sendto': '发送网络数据', 'socket.sendmsg': '发送网络数据',
    'urllib.Request': '发起网络请求',
    '_thread.start_new_thread': '启动线程', '_thread.start_joinable_thread': '启动线程',
}
_MUTATORS = {'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'update', 'setdefault', 'add', 'discard',
             'sort', 'reverse', 'popitem', 'appendleft', 'extendleft', 'popleft', 'write', 'writelines',
             'put', 'put_nowait', '__setitem__', '__delitem__'}
_SQL_READS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, 33}  # 33: SQLITE_RECURSIVE
_SQL_TABLE_PRAGMAS = {'table_info', 'table_xinfo', 'index_list', 'index_info', 'index_xinfo', 'foreign_key_list'}
_SQL_READ_PRAGMAS = _SQL_TABLE_PRAGMAS | {
    'table_list', 'database_list', 'function_list', 'pragma_list', 'collation_list', 'module_list',
    'compile_options', 'user_version', 'schema_version', 'application_id', 'encoding', 'page_count',
    'page_size', 'freelist_count', 'data_version', 'foreign_keys', 'integrity_check', 'quick_check'}
_SQL_WRITES = {
    sqlite3.SQLITE_INSERT: 'INSERT', sqlite3.SQLITE_UPDATE: 'UPDATE', sqlite3.SQLITE_DELETE: 'DELETE',
    sqlite3.SQLITE_ALTER_TABLE: 'ALTER', sqlite3.SQLITE_TRANSACTION: 'BEGIN/COMMIT/ROLLBACK',
    sqlite3.SQLITE_SAVEPOINT: 'SAVEPOINT', sqlite3.SQLITE_ATTACH: 'ATTACH', sqlite3.SQLITE_DETACH: 'DETACH',
    sqlite3.SQLITE_REINDEX: 'REINDEX', sqlite3.SQLITE_ANALYZE: 'ANALYZE', sqlite3.SQLITE_PRAGMA: 'PRAGMA',
    **{getattr(sqlite3, name): 'CREATE' for name in dir(sqlite3) if name.startswith('SQLITE_CREATE_')},
    **{getattr(sqlite3, name): 'DROP' for name in dir(sqlite3) if name.startswith('SQLITE_DROP_')}}


class _Local(threading.local):
    guard = None


_LOCAL = _Local()
_CALLING = 0          # the one switch the audit hook reads: replayed calls now running in any thread
_HOOKED = False


def _install():
    """Install the audit hook on the first replay; it cannot be removed and costs one global test."""
    global _HOOKED
    if not _HOOKED:
        sys.addaudithook(_audit)
        _HOOKED = True


def _audit(event, args):
    if not _CALLING:
        return
    guard = _LOCAL.guard
    if guard is None:
        return
    if event == 'open':
        mode, flags = args[1], args[2]
        if not (type(mode) is str and any(letter in mode for letter in 'wax+')
                or type(flags) is int and flags & _WRITE_FLAGS):
            return
        what = '写文件 ' + (os.fsdecode(args[0]) if isinstance(args[0], (str, bytes, os.PathLike)) else f'（文件描述符 {args[0]}）')
    elif event == 'sqlite3.connect/handle':
        guard.opened.append(args[0])    # not initialised yet: the connect wrapper installs its authorizer
        return
    elif event == 'sqlite3.connect':
        if not _creates_database(args[0]):
            return
        what = '新建数据库文件 ' + os.fsdecode(args[0])
    elif event in _REFUSED_EVENTS:
        what = _REFUSED_EVENTS[event] + ''.join(' ' + os.fsdecode(value) for value in args[:1] if isinstance(value, (str, bytes)))
    else:
        return
    frame = sys._getframe(1)
    if _bytecode_cache(frame):
        return
    raise Refused(guard.refuse(what, frame))


def _connect(*args, **kwargs):
    """sqlite3.connect while a replayed call runs: the new connection refuses writes like the arguments' ones."""
    connection = _SQLITE_CONNECT(*args, **kwargs)
    guard = _LOCAL.guard
    if guard is not None:
        guard.adopt(connection)
    return connection


_SQLITE_CONNECT = sqlite3.connect


def _creates_database(database):
    """sqlite3.connect creates a missing database file at once; memory and existing files do not."""
    name = os.fsdecode(database) if isinstance(database, (str, bytes, os.PathLike)) else ''
    if name in ('', ':memory:') or name.startswith('file:') and ('mode=memory' in name or 'mode=ro' in name):
        return False
    return not Path(name.removeprefix('file:').partition('?')[0]).exists()


def _bytecode_cache(frame):
    """The import system writing a .pyc for a module imported during the replay is not its effect."""
    for _ in range(4):
        if frame is None:
            return False
        code = frame.f_code
        if code.co_filename.startswith('<frozen importlib') and code.co_name in ('_write_atomic', 'set_data'):
            return True
        frame = frame.f_back
    return False


@contextmanager
def unguarded():
    """FlowGuard's own work that happens to run inside a replayed call (an import observer) is not guarded."""
    previous, _LOCAL.guard = _LOCAL.guard, None
    try:
        yield
    finally:
        _LOCAL.guard = previous


def _data(value, trail=frozenset()):
    """Inert data whose comparison runs no project operator: the only outcomes a replay compares."""
    if type(value) in (type(None), bool, int, float, str, bytes, Decimal, date, timedelta):
        return True
    if type(value) is datetime:
        return value.tzinfo is None
    if isinstance(value, cells.Raised):
        return True
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
    return all(_data(item, trail | {id(value)}) for item in children)


def _attributes(value):
    """An object's own attribute dictionary, read without running project code."""
    descriptor = inspect.getattr_static(value, '__dict__', None)
    if type(descriptor) is types.GetSetDescriptorType:
        found = descriptor.__get__(value)
        return found if type(found) is dict else {}
    return {}


def _children(value):
    if type(value) is dict:
        return [(f'[{key!r}]', item) for key, item in itertools.islice(value.items(), 1000)]
    if type(value) in (list, tuple, set, frozenset):
        return [(f'[{index}]', item) for index, item in enumerate(itertools.islice(value, 1000))]
    return [('.' + str(name), item) for name, item in itertools.islice(_attributes(value).items(), 1000)]


def _callbacks(connection):
    """True when the connection holds a Python callback (authorizer, progress, trace, collation,
    function or row factory). No Python version can read an authorizer back, so the replay could not
    restore it; the other callbacks would run again in every replayed statement."""
    import functools
    import gc
    noise, cache = [sqlite3.Connection, connection.text_factory], False
    if connection.row_factory is not None or not (connection.text_factory is str or connection.text_factory is bytes):
        return True
    for ref in gc.get_referents(connection):
        if not callable(ref):
            continue
        found = next((i for i, value in enumerate(noise) if ref is value), None)
        if found is not None:
            noise.pop(found)
        elif not cache and type(ref) is functools._lru_cache_wrapper and inspect.getattr_static(ref, '__wrapped__', None) is connection:
            cache = True
        else:
            return True
    return False


def _visible(arguments):
    """(sqlite3 connections and cursors to keep shared, why the replay cannot see the arguments).

    The arguments and their attributes or items, two levels deep: a file open for writing, a socket,
    a database connection other than sqlite3, or a sqlite3 connection holding Python callbacks keeps
    the replay from running."""
    import io
    sockets = sys.modules.get('socket')
    shared, seen = [], set()

    def problem(value, label, depth):
        if id(value) in seen or _simple(value):
            return ''
        seen.add(id(value))
        kind = type(value)
        if kind is sqlite3.Cursor:
            shared.append(value)
            value, kind = value.connection, sqlite3.Connection
        if kind is sqlite3.Connection:
            if value not in shared:
                shared.append(value)
            return f'参数 {label} 的 sqlite3 连接带着 Python 回调（authorizer、progress、trace、函数或行工厂），回放后恢复不了' \
                if _callbacks(value) else ''
        if sockets is not None and isinstance(value, sockets.socket):
            return f'参数 {label} 是套接字'
        if isinstance(value, io.IOBase) and not value.closed and value.writable():
            return f'参数 {label} 是写模式打开的文件'
        names = {name for name in ('cursor', 'commit', 'rollback', 'execute', 'fetchone')
                 if callable(inspect.getattr_static(kind, name, None))}
        if {'cursor', 'commit', 'rollback'} <= names or {'execute', 'commit'} <= names or {'execute', 'fetchone'} <= names:
            return f'参数 {label} 是 sqlite3 以外的数据库连接（{kind.__module__}.{kind.__qualname__}）'
        if depth >= 2:
            return ''
        for name, item in _children(value):
            if found := problem(item, label + name, depth + 1):
                return found
        return ''

    for name, value in arguments.items():
        if found := problem(value, name, 0):
            return shared, found
    return shared, ''


def _snapshot(value):
    """What a replay could change in an argument it could not copy: its own simple attributes and items."""
    return [(name, item if _simple(item) else ('object', id(item))) for name, item in _children(value)]


class _Guard:
    """One guarded replay of one call site; `void` holds the first refusal of the current code."""

    def __init__(self, runtime, arguments):
        self.runtime = runtime
        self.shared, self.unseen = _visible(arguments)
        self.connections = [value for value in self.shared if type(value) is sqlite3.Connection]
        self.void = self.void_old = ''
        self.adopted, self.opened, self.compared, self.saved = [], [], {}, []
        self.old = False
        self.functions = set()
        self.code = _value.__code__     # the frame that calls the replayed function: where a location search stops

    def __enter__(self):
        _install()
        for connection in self.connections:
            before = connection.total_changes
            # SQL functions defined in Python run project code on every statement that calls them.
            self.functions |= {row[0].lower() for row in connection.execute('PRAGMA function_list') if not row[1]}
            connection.execute('SAVEPOINT flowguard_replay')
            connection.set_authorizer(self._authorize)
            self.saved.append((connection, before))
        return self

    def __exit__(self, *error):
        for connection, before in reversed(self.saved):
            connection.set_authorizer(None)
            connection.execute('ROLLBACK TO flowguard_replay')
            connection.execute('RELEASE flowguard_replay')
            if connection.total_changes != before:
                self._mark(f'回放被拦住：回放之后数据库仍有改动（total_changes {before} → {connection.total_changes}）')
        for connection in self.adopted:
            try:
                connection.set_authorizer(None)
            except sqlite3.ProgrammingError:
                pass  # The replayed call closed the connection it opened; nothing is left to restore.
        for name, (value, before) in self.compared.items():
            if _snapshot(value) != before:
                self._mark(f'回放改了参数 {name}：它复制不了，回放之后和原值不同')
        return False

    def _mark(self, reason):
        if self.old:
            self.void_old = self.void_old or reason
        else:
            self.void = self.void or reason

    def adopt(self, connection):
        """A connection opened during a replayed call refuses writes like the arguments' connections."""
        connection.set_authorizer(self._authorize)
        self.adopted.append(connection)

    def _unadopted(self):
        """A connection opened without the sqlite3.connect wrapper (an alias bound before the replay) had no
        authorizer: whatever it did is not known, so the replay is void."""
        for connection in self.opened:
            if not any(connection is adopted for adopted in self.adopted):
                self._mark('回放被拦不住：回放期间新建的 sqlite3 连接没经过 sqlite3.connect（例如 from sqlite3 import connect），'
                           '它的写入看不见')
        self.opened.clear()

    def refuse(self, what, frame):
        reason = '回放被拦住：' + self._where(frame) + what
        self._mark(reason)
        return reason

    def _where(self, frame):
        """`file:line text：` of the innermost project frame; a baseline function's line is its baseline line."""
        import linecache
        old = {id(patch.code): patch for patch in self.runtime.patches.values()} if self.old else {}
        while frame is not None and frame.f_code is not self.code:
            file = frame.f_code.co_filename
            if self.runtime._project_file(file):
                relative = Path(file).resolve().relative_to(self.runtime.root).as_posix()
                line, text = frame.f_lineno, ''
                if (patch := old.get(id(frame.f_code))) is not None:
                    # The swapped code keeps the current first line; its body lines are the baseline's, shifted.
                    line += patch.node.lineno - frame.f_code.co_firstlineno
                    source = self.runtime._source(relative) or ''
                    text = source.splitlines()[line - 1].strip() if 0 < line <= len(source.splitlines()) else ''
                    relative += '（基准）'
                else:
                    text = linecache.getline(file, line).strip()
                return f'{relative}:{line} ' + (f'{text}：' if text else '')
            frame = frame.f_back
        return ''

    def _authorize(self, action, first, second, database, trigger):
        if action == sqlite3.SQLITE_FUNCTION and (second or '').lower() in self.functions:
            self.refuse(f'调用 Python 写的 SQL 函数 {second}', sys._getframe(1))
            return sqlite3.SQLITE_DENY
        if action in _SQL_READS or action == sqlite3.SQLITE_PRAGMA and (first or '').lower() in _SQL_READ_PRAGMAS and (
                second is None or (first or '').lower() in _SQL_TABLE_PRAGMAS):
            return sqlite3.SQLITE_OK
        self.refuse('写数据库 ' + _SQL_WRITES.get(action, f'（authorizer 动作 {action}）') + (f' {first}' if first else ''),
                    sys._getframe(1))
        return sqlite3.SQLITE_DENY

    def call(self, fn, bound, *, old=False):
        """One replayed call: its outcome, with the arguments copied and every effect refused."""
        global _CALLING
        previous, _LOCAL.guard = _LOCAL.guard, self
        self.old = old
        sqlite = sys.modules.get('sqlite3')
        patched = sqlite is not None and sqlite.connect is _SQLITE_CONNECT
        if patched:
            sqlite.connect = _connect    # other threads calling it meanwhile get the plain behaviour
        _CALLING += 1
        try:
            return _value(fn, self._copied(bound))
        except Refused as error:
            return cells.Raised(error)  # The refusal is already recorded; this whole replay is void.
        finally:
            _CALLING -= 1
            if patched:
                sqlite.connect = _SQLITE_CONNECT
            self._unadopted()
            self.old = False
            _LOCAL.guard = previous

    def _copied(self, bound):
        """Replay on deep copies; what cannot be copied is compared with its original afterwards."""
        memo = {id(value): value for value in self.shared}
        arguments = {}
        for name, value in bound.arguments.items():
            if _simple(value) or id(value) in memo:
                arguments[name] = value
                continue
            try:
                arguments[name] = copy.deepcopy(value, dict(memo))
            except (TypeError, ValueError, AttributeError, RecursionError, copy.Error):
                arguments[name] = value  # Not copyable: the replay runs on the original and compares it afterwards.
                self.compared.setdefault(name, (value, _snapshot(value)))
        return _binding(bound.signature, arguments)


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
    actual: tuple | None = None  # (simple inputs, outcome) of the real call; never a replay.
    lost: str = ''  # why it is grey, when the baseline code in this same context replays cleanly


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


_HUB = _ObserverHub()


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
        """Why this call is not replayed, or ''. Only explicit writes stop a replay statically: a
        `global`/`nonlocal` name the function assigns, an assignment, deletion or mutating method call
        on module state, here and in the project helpers it calls. The arguments must be visible to the
        replay guard. Reads, dates, properties and unresolved calls run under the guard instead."""
        fn = sites.unwrap(function)
        top = seen is None
        seen = set() if seen is None else seen
        if fn in seen:
            return ''
        seen.add(fn)
        if top and arguments:
            unseen = _visible(arguments)[1]
            if unseen:
                return '看不清：' + unseen
        if inspect.isgeneratorfunction(fn) or inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn):
            return '看不清：生成器或协程函数的函数体在回放里不运行'
        try:
            if historical:
                if fn not in self.patches:
                    return 'baseline function is unavailable: ' + self.unavailable.get(fn, fn.__qualname__)
                node = self.patches[fn].node
            else:
                node = _definition(fn)
        except (OSError, TypeError, SyntaxError):
            return 'source is unavailable for side-effect checking'
        parts = list(sites.own_nodes(node))
        declared = {name for part in parts if isinstance(part, (ast.Global, ast.Nonlocal)) for name in part.names}
        stored = {part.id for part in parts if isinstance(part, ast.Name) and isinstance(part.ctx, (ast.Store, ast.Del))}
        local = ({arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                                      *(x for x in (node.args.vararg, node.args.kwarg) if x))} | stored) - declared
        namespace = fn.__globals__

        def line(part):
            return part.lineno if historical else fn.__code__.co_firstlineno + part.lineno - 1

        def shared(expression):
            """The module-level object an attribute/subscript/method chain starts from, if it is module state."""
            while isinstance(expression, (ast.Attribute, ast.Subscript, ast.Call)):
                expression = expression.func if isinstance(expression, ast.Call) else expression.value
            if not isinstance(expression, ast.Name) or expression.id in local:
                return None
            value = namespace.get(expression.id, _MISSING)
            if value is _MISSING or callable(value) or type(value) is types.ModuleType or _simple(value):
                return None
            return expression.id

        for part in parts:
            if isinstance(part, (ast.Global, ast.Nonlocal)) and set(part.names) & stored:
                kind = '全局变量' if isinstance(part, ast.Global) else '外层变量'
                return f'明确的写操作：第 {line(part)} 行给{kind} {", ".join(sorted(set(part.names) & stored))} 赋值'
            targets = part.targets if isinstance(part, (ast.Assign, ast.Delete)) else [part.target] \
                if isinstance(part, ast.AugAssign) or isinstance(part, ast.AnnAssign) and part.value is not None else []
            for target in targets:
                for item in ast.walk(target):
                    if isinstance(item, (ast.Attribute, ast.Subscript)) and (name := shared(item.value)):
                        return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{ast.unparse(item)}）'
            if not isinstance(part, ast.Call):
                continue
            if isinstance(part.func, ast.Attribute) and part.func.attr in _MUTATORS and (name := shared(part.func.value)):
                return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{ast.unparse(part.func)}）'
            if isinstance(part.func, ast.Name) and part.func.id in ('setattr', 'delattr') and part.func.id not in local \
                    and part.args and (name := shared(ast.Attribute(part.args[0], 'x', ast.Load()))):
                return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{part.func.id}）'
            target = _resolve(part.func, namespace)
            if type(target) is types.FunctionType and self._project(target):
                if problem := self.safety(target, None, seen, historical=historical and target in self.patches):
                    return problem
        return ''

    def guarded(self, fn, bound):
        """One guarded call that is not a test's own call: (outcome, why it was refused or '')."""
        guard = _Guard(self, bound.arguments)
        if guard.unseen:
            return None, '看不清：' + guard.unseen
        with guard:
            outcome = guard.call(fn, bound)
        return outcome, guard.void

    def _lost(self, reading, owner, bound):
        """Mark a grey reading lost when the baseline code, in this same context, replays cleanly:
        compared with the baseline it would have been red or green."""
        patch = self.register(owner)
        if patch is None or self.safety(owner, bound.arguments, historical=True):
            return
        guard = _Guard(self, bound.arguments)
        if guard.unseen:
            return
        with guard, self.old_code():
            outcome = guard.call(patch.callable(), bound, old=True)
        if not guard.void_old and _data(outcome):
            reading.lost = reading.reasons[0]

    def axes(self, function, bound, explicit=None):
        """Retain all proved representatives and actuals without cross-axis guesses.

        The generic grid adds source constants and their neighbours; the replay
        loop supplements an explicit grid with actual-tuple neighbours.
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
                values.append(value)
                values.extend(_neighbours(value))
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
        index = len(self.readings)
        try:
            self._replay_rows(original, bound, owner=owner, name=name, axes=axes)
        finally:
            _OBSERVING.reset(observing)
            _PRIVATE.reset(token)
        reading = self.readings[index] if index < len(self.readings) else None
        inputs = {name: value for name, value in bound.arguments.items() if _simple(value)}
        try:
            outcome = original(*bound.args, **bound.kwargs)
        except Exception as error:
            if reading is not None:
                reading.actual = (inputs, cells.Raised(error))
            raise
        if reading is not None:
            reading.actual = (inputs, outcome)
        return outcome

    def _replay_rows(self, original, bound, *, owner, name, axes):
        """No normal call here, including when metadata or a replay gate is grey. Every replayed call
        runs in one guard; a refused effect voids the reading."""
        reading = Reading(name or owner.__qualname__, owner.__module__ + ':' + owner.__qualname__,
                          test=self.test, baseline=self.baseline)
        self.readings.append(reading)
        problem = self.safety(original, bound.arguments)
        if problem:
            reading.status, reading.reasons = 'grey', [problem]
            reading.comparison_status, reading.comparison_reasons = 'grey', [problem]
            if not problem.startswith('看不清'):
                self._lost(reading, owner, bound)
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
        points = (dict(zip(axes, values)) for values in itertools.product(*axes.values()))
        neighbours = []
        if supplied_axes:
            actual = {name: bound.arguments.get(name) for name in axes}
            for name in axes:
                for value in _neighbours(actual[name]):
                    if not any(outcome_equal(value, prior) for prior in axes[name]):
                        neighbours.append({**actual, name: value})
        opaque = ''
        guard = _Guard(self, bound.arguments)
        with guard:
            baseline = guard.call(original, bound)
            if not _data(baseline):
                opaque = type(baseline).__name__
            for inputs in itertools.chain(points, neighbours):
                if guard.void or opaque:
                    break
                arguments = _binding(bound.signature, {**bound.arguments, **inputs})
                now = guard.call(original, arguments)
                old = None
                if patch is not None and not guard.void_old:
                    with self.old_code():
                        old = guard.call(patch.callable(), arguments, old=True)
                if not _data(now) or not _data(old):
                    opaque = type(now if not _data(now) else old).__name__
                    break
                reading.rows.append((inputs, now))
                if patch is not None and not guard.void_old and not outcome_equal(old, now):
                    reading.changed.append((inputs, old, now))
            again = None if guard.void or opaque else guard.call(original, bound)
        if guard.void:
            reading.status, reading.reasons = 'grey', [guard.void]
            reading.rows.clear()
            reading.changed.clear()
            self._lost(reading, owner, bound)
            return
        if opaque or not _data(again):
            reading.status, reading.reasons = 'grey', [f'回放结果不是可以比较的简单数据（{opaque or type(again).__name__}）：不运行它的比较运算']
            reading.rows.clear()
            reading.changed.clear()
            return
        if guard.void_old:
            reading.comparison_status = 'grey'
            reading.comparison_reasons.append('基准代码的' + guard.void_old)
            reading.changed.clear()
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
