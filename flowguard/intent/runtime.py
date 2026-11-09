"""One in-process observation boundary, shared by tests and explicit checks.

The runtime never collects tests or opens another Python/test session. Replay is
private; real calls and their exceptions still run normally. Unknown replay
boundaries produce unavailable observations, never evidence of agreement.
"""
from __future__ import annotations

import _thread
import ast
import builtins
import collections
import copy
import dis
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
import enum
import functools
import gc
import inspect
import importlib.util
import itertools
import os
from pathlib import Path
import random
import re
import sqlite3
import sys
import textwrap
import threading
import time
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
# A call-site replay (the current code, the baseline code swapped in, the original-value recheck) runs its calls
# inside one guard: only in the replaying thread and only while a replayed call runs. The audit hook refuses
# file writes, directory changes, processes, signals, threads and network access before they happen. Calls
# that raise no audit event (sqlite3.connect, threading.Thread.start, os.mkfifo, os.mknod, and
# _thread.start_new_thread on Python 3.11) are wrapped while a replayed call runs, for the replaying thread.
# sqlite3 connections in the arguments and in the module state the function reads (at any depth) hold a
# savepoint and a read transaction (nothing can be backed up into them), are query_only and refuse writing
# statements; they return to the savepoint afterwards. Connections opened during a call are protected the
# same way. Logging records made in a replayed call are dropped and the random module's state is restored.
# Any refusal voids the whole replay, also when the replayed code catches it. What the guard cannot copy or
# see into (a generator, an open file, a function, a logger, a queue, another database driver ...) is not
# replayed, and a replay that runs too long (the owners' watchdog) or recurses too deeply is void.

class Refused(BaseException):
    """Raised in the audit hook, so the refused operation does not happen. A BaseException: an
    ordinary `except Exception` in the replayed code does not continue with further effects."""


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_REFUSED_EVENTS = {
    'os.remove': '删除文件', 'os.rename': '改名或移动文件', 'os.rmdir': '删除目录', 'os.mkdir': '新建目录',
    'os.chmod': '改文件权限', 'os.chown': '改文件属主', 'os.utime': '改文件时间', 'os.truncate': '截断文件',
    'os.link': '新建链接', 'os.symlink': '新建链接', 'shutil.rmtree': '删除目录树',
    'os.setxattr': '改文件扩展属性', 'os.removexattr': '删除文件扩展属性', 'os.chdir': '切换工作目录',
    'subprocess.Popen': '启动子进程', 'os.system': '执行 shell 命令', 'os.exec': '替换当前进程',
    'os.spawn': '启动子进程', 'os.posix_spawn': '启动子进程', 'os.fork': '复制当前进程', 'os.forkpty': '复制当前进程',
    'os.kill': '给进程发信号', 'os.killpg': '给进程组发信号', 'signal.pthread_kill': '给线程发信号',
    'os.putenv': '改环境变量', 'os.unsetenv': '改环境变量',
    'socket.connect': '连接网络', 'socket.sendto': '发送网络数据', 'socket.sendmsg': '发送网络数据',
    'urllib.Request': '发起网络请求',
    '_thread.start_new_thread': '启动线程', '_thread.start_joinable_thread': '启动线程',
}
_MUTATORS = {'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'update', 'setdefault', 'add', 'discard',
             'sort', 'reverse', 'popitem', 'appendleft', 'extendleft', 'popleft', 'write', 'writelines',
             'put', 'put_nowait', '__setitem__', '__delitem__', 'move_to_end', 'rotate'}


def _mutating_functions():
    """Standard functions that change the object given as their first argument."""
    import bisect
    import collections
    import heapq
    import operator
    functions = [heapq.heappush, heapq.heappop, heapq.heapify, heapq.heapreplace, heapq.heappushpop,
                 bisect.insort, bisect.insort_left, bisect.insort_right, random.shuffle, next,
                 operator.setitem, operator.delitem,
                 *(getattr(operator, name) for name in ('iadd', 'iand', 'iconcat', 'ifloordiv', 'ilshift', 'imatmul',
                                                         'imod', 'imul', 'ior', 'ipow', 'irshift', 'isub', 'itruediv', 'ixor'))]
    for kind in (list, dict, set, bytearray, collections.deque, collections.OrderedDict):
        functions.extend(vars(kind)[name] for name in _MUTATORS if name in vars(kind))
    return functions


_MUTATING = _mutating_functions()       # kept alive, so their ids below stay theirs
_MUTATING_IDS = frozenset(map(id, _MUTATING))
# Methods that change a sqlite3 connection itself: on a connection the replay shares with the test, they
# would change the test's own connection (it cannot be copied).
_CONNECTION_CALLS = {'close', 'set_authorizer', 'set_progress_handler', 'set_trace_callback', 'create_function',
                     'create_aggregate', 'create_window_function', 'create_collation', 'backup', 'blobopen',
                     'enable_load_extension', 'load_extension', 'interrupt', 'setlimit', 'setconfig', 'deserialize'}
# What a protected connection itself answers to a write that bypasses its authorizer: a backup into it (it
# holds a read transaction) and a Blob write (it is query_only).
_PROTECTED_ERRORS = {'destination database is in use', 'attempt to write a readonly database'}
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
_LOOK = 10000         # objects one visibility check looks at; a larger argument or module state is not replayed
_PERF, _SLEEP = time.perf_counter, time.sleep      # the real ones: a test's patched time.time cannot stretch a wait
_TICK_WAIT = max(0.05, 4 * max(time.get_clock_info(name).resolution for name in ('time', 'monotonic')))
# Objects that are code, not state: a visibility check does not look into them.
_CODE = (types.FunctionType, types.BuiltinFunctionType, types.MethodType, types.MethodDescriptorType,
         types.WrapperDescriptorType, types.MethodWrapperType, types.ClassMethodDescriptorType,
         types.GetSetDescriptorType, types.MemberDescriptorType, types.CodeType, types.FrameType,
         types.ModuleType, classmethod, staticmethod, property, functools.partial)
_PLAIN = (type(None), bool, int, float, str, bytes)


class _Local(threading.local):
    guard = None
    connecting = False      # inside the sqlite3.connect wrapper: the connection being opened is protected


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
    elif event == 'sqlite3.connect':
        if not _LOCAL.connecting:
            what = '打开 sqlite3 连接没经过回放保护（例如 from sqlite3 import connect 在回放之前已经绑定）'
        elif _creates_database(args[0]):
            what = '新建数据库文件 ' + os.fsdecode(args[0])
        else:
            return
    elif event in _REFUSED_EVENTS:
        what = _REFUSED_EVENTS[event] + ''.join(' ' + os.fsdecode(value) for value in args[:1] if isinstance(value, (str, bytes)))
    else:
        return
    frame = sys._getframe(1)
    if _bytecode_cache(frame):
        return
    raise Refused(guard.refuse(what, frame))


def _connect(*args, **kwargs):
    """sqlite3.connect while a replayed call runs: the new connection is protected like the arguments' ones."""
    guard = _LOCAL.guard
    if guard is None:
        return _SQLITE_CONNECT(*args, **kwargs)
    _LOCAL.connecting = True
    try:
        connection = _SQLITE_CONNECT(*args, **kwargs)
    finally:
        _LOCAL.connecting = False
    guard.adopt(connection)
    return connection


_SQLITE_CONNECT = sqlite3.connect


def _refusing(function, what):
    """`function` for every thread, refused in a replayed call: it raises no audit event of its own."""
    def refusing(*args, **kwargs):
        guard = _LOCAL.guard
        if guard is not None:
            path = args[0] if args and isinstance(args[0], (str, bytes, os.PathLike)) else None
            raise Refused(guard.refuse(what + ('' if path is None else ' ' + os.fsdecode(path)), sys._getframe(1)))
        return function(*args, **kwargs)
    refusing.__wrapped__ = function
    return refusing


# (owner, name, original, wrapper): put in place while a replayed call runs. Thread.start is refused before it
# registers the thread (the audit event comes later, from _thread); Python 3.11 has no thread audit event.
_PATCHES = [(sqlite3, 'connect', _SQLITE_CONNECT, _connect),
            (threading.Thread, 'start', vars(threading.Thread)['start'],
             _refusing(vars(threading.Thread)['start'], '启动线程')),
            *((os, name, getattr(os, name), _refusing(getattr(os, name), what))
              for name, what in (('mkfifo', '新建命名管道'), ('mknod', '新建设备文件')) if hasattr(os, name)),
            *(((_thread, 'start_new_thread', _thread.start_new_thread, _refusing(_thread.start_new_thread, '启动线程')),)
              if sys.version_info < (3, 12) else ())]


def _wrap():
    """The wrappers, where the original is still in place (a test's own replacement stays)."""
    for owner, name, original, wrapper in _PATCHES:
        if getattr(owner, name, None) is original:
            setattr(owner, name, wrapper)


def _unwrap():
    """The originals back, where a wrapper is in place; repeating it changes nothing."""
    for owner, name, original, wrapper in _PATCHES:
        if getattr(owner, name, None) is wrapper:
            setattr(owner, name, original)


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


def _quiet(record):
    """A filter on every logging handler while a guard is active: a record made in a replayed call is dropped."""
    return _LOCAL.guard is None


def _handlers():
    """The logging handlers of every logger, and the last-resort one; none when logging is not imported."""
    logging = sys.modules.get('logging')
    if logging is None:
        return []
    loggers = [logging.root, *(item for item in list(logging.Logger.manager.loggerDict.values())
                                if isinstance(item, logging.Logger))]
    found, seen = [], set()
    for handler in [handler for logger in loggers for handler in list(logger.handlers)] + [logging.lastResort]:
        if handler is not None and id(handler) not in seen:
            seen.add(id(handler))
            found.append(handler)
    return found


def _unquiet(handler):
    for index, item in enumerate(handler.filters):
        if item is _quiet:
            del handler.filters[index]
            return


def _clocks():
    return time.time(), time.monotonic()


def _next_tick(before):
    """Wait until the wall clock and the monotonic clock have both moved on from `before`, so that the
    original-value recheck runs a clock tick later than the first call: on a coarse clock (1/64 s on
    Windows) the two calls of a clock-reading function would otherwise often read the same value. The
    wait is bounded by the real performance counter (a frozen clock never moves)."""
    deadline = _PERF() + _TICK_WAIT
    while _PERF() < deadline:
        wall, steady = _clocks()
        if wall != before[0] and steady != before[1]:
            return
        _SLEEP(0.0005)


@contextmanager
def _bounded(guard):
    """The replay owners' watchdog (`owners.watchdog`, `owners.TIMEOUT` seconds) around the replayed calls of one
    guard: a replay that runs longer is interrupted, and it is void."""
    from . import owners
    seconds = owners.TIMEOUT
    try:
        with owners.watchdog(seconds):
            yield
    except owners._Timeout:
        # The interruption may have cut a replayed call's own restoring short: put the originals back.
        if not _CALLING:
            _unwrap()
        guard.timed_out, guard.old = True, False     # the current reading is void, whichever code was running
        guard._mark(f'超过 {seconds:g} 秒没有结束')


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
    if id(value) in trail:
        return False
    if type(value) in (tuple, list, dict, set, frozenset):
        children = [*value.keys(), *value.values()] if type(value) is dict else value
    elif (fields := _record_fields(value)) is not None:
        children = fields
    else:
        return False
    return all(_data(item, trail | {id(value)}) for item in children)


def _record_fields(value):
    """The field values of a plain record result (a NamedTuple, or a dataclass whose equality is the
    generated one), so comparing two of them runs no project operator; None for anything else."""
    import dataclasses
    kind = type(value)
    if isinstance(value, tuple) and type(inspect.getattr_static(kind, '_fields', None)) is tuple:
        return list(value) if inspect.getattr_static(kind, '__eq__') is tuple.__eq__ else None
    if not dataclasses.is_dataclass(kind) or not kind.__dataclass_params__.eq:
        return None
    equality = inspect.getattr_static(kind, '__eq__')
    if getattr(getattr(equality, '__code__', None), 'co_filename', None) != '<string>':
        return None     # a hand-written __eq__ is project code
    state = _attributes(value)
    names = [field.name for field in dataclasses.fields(kind)]
    return [state[name] for name in names] if all(name in state for name in names) else None


def _attributes(value):
    """An object's own attribute dictionary, read without running project code. The `__dict__` descriptor is
    taken from the object's type, so a class passed as an argument (a classmethod's `cls`) reads its own
    namespace instead of the descriptor its instances use."""
    namespace = type.__dict__['__dict__'].__get__
    descriptor = next((namespace(klass)['__dict__'] for klass in type(value).__mro__ if '__dict__' in namespace(klass)),
                      None)
    if type(descriptor) is types.GetSetDescriptorType:
        found = descriptor.__get__(value)
        return dict(found) if type(found) in (dict, types.MappingProxyType) else {}
    return {}


def _namespace(owner):
    """A module's globals or another object's own attributes, read without running project code."""
    return vars(owner) if type(owner) is types.ModuleType else _attributes(owner)


def _callbacks(connection):
    """True when the connection holds a Python authorizer, progress handler, trace callback or row factory
    (sqlite3.Row is native; a text factory other than str and bytes counts as well), the callbacks a
    connection refers to: no Python version
    can read an authorizer back, so the replay could not restore it, and the others would run again in
    every replayed statement. SQL functions, aggregates and collations are not seen here; the guard
    refuses a Python SQL function or aggregate when a replayed statement calls it, while a collation
    simply runs again."""
    noise, cache = [sqlite3.Connection, connection.text_factory, connection.row_factory], False
    if connection.row_factory not in (None, sqlite3.Row) or not (connection.text_factory is str or connection.text_factory is bytes):
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


def _callback_state(connection):
    """What of a connection a replayed call could change without a statement: the callables it refers to,
    its row and text factories, its Python SQL functions (name, kind, arguments) and its collations."""
    return (frozenset(id(ref) for ref in gc.get_referents(connection) if callable(ref)),
            connection.row_factory, connection.text_factory,
            frozenset((row[0], row[2], row[4]) for row in connection.execute('PRAGMA function_list') if not row[1]),
            frozenset(row[1] for row in connection.execute('PRAGMA collation_list')))


def _unseen(value, kind, objects):
    """Why a replay cannot copy or see into this one object, or ''. Read without running project code
    (except an open file's own `closed` and `writable`). `objects`: an argument, where a function, a bound
    method or a logger would run on the test's own objects too."""
    import io
    if kind in (types.GeneratorType, types.CoroutineType, types.AsyncGeneratorType):
        return '是生成器或协程（回放会取走它的值）'
    if issubclass(kind, io.IOBase):
        if value.closed:
            return ''
        return '是写模式打开的文件' if value.writable() else '是打开的文件（回放会读走它的内容）'
    sockets = sys.modules.get('socket')
    if sockets is not None and issubclass(kind, sockets.socket):
        return '是套接字'
    if kind is getattr(sqlite3, 'Blob', None):
        return '是 sqlite3 的 Blob（它的写入不经过回放保护）'
    tables = sys.modules.get('_csv')
    if tables is not None and kind in (tables.Reader, tables.Writer):
        return '是 csv 的读写器（回放会读走或写进它的文件）'
    for module, names in (('queue', ('Queue', 'SimpleQueue')), ('asyncio', ('Queue',)),
                          ('multiprocessing.queues', ('Queue', 'SimpleQueue')), ('concurrent.futures', ('Executor',))):
        found = sys.modules.get(module)
        if found is not None and issubclass(kind, tuple(vars(found)[name] for name in names if name in vars(found))):
            return '是队列或线程池（回放的效果会落到别的线程里）'
    if objects:
        owner = value.__self__ if kind is types.BuiltinFunctionType else None
        if kind in (types.FunctionType, types.MethodType, types.MethodWrapperType, functools.partial) or \
                owner is not None and type(owner) is not types.ModuleType and not issubclass(type(owner), type) \
                and not _simple(owner) and type(owner) not in _PLAIN:
            return '是函数或绑定方法（回放会在测试自己的对象上运行它）'
        logging = sys.modules.get('logging')
        if logging is not None and issubclass(kind, (logging.Logger, logging.LoggerAdapter, logging.Handler)):
            return '是 logging 的记录器（deepcopy 返回它本身）'
    names = {name for name in ('cursor', 'commit', 'rollback', 'execute', 'fetchone')
             if callable(inspect.getattr_static(kind, name, None))}
    if {'cursor', 'commit', 'rollback'} <= names or {'execute', 'commit'} <= names or {'execute', 'fetchone'} <= names:
        return f'是 sqlite3 以外的数据库连接（{kind.__module__}.{kind.__qualname__}）'
    return ''


def _parts(value, kind, label, top):
    """(label, object) of what an object holds: items, keys, attributes and the other references the garbage
    collector knows. A class is looked into only as an argument itself (its data attributes); other classes,
    modules and code are not looked into."""
    if issubclass(kind, type):
        if top:
            for name, item in _attributes(value).items():
                if not (name.startswith('__') and name.endswith('__')) and type(item) not in _CODE:
                    yield f'{label}.{name}', item
        return
    if kind in _CODE:
        return
    if issubclass(kind, dict):
        for key, item in dict.items(value):
            yield (f'{label}[{key!r}]' if type(key) in _PLAIN else f'{label}[…]'), item
            yield f'{label}[…]', key
    elif issubclass(kind, (list, tuple, set, frozenset)):
        base = next(base for base in (list, tuple, set, frozenset) if issubclass(kind, base))
        for index, item in enumerate(base.__iter__(value)):
            yield (f'{label}[{index}]' if base in (list, tuple) else f'{label}[…]'), item
    for name, item in _attributes(value).items():
        yield f'{label}.{name}', item
    if kind not in (dict, list, tuple, set, frozenset):
        for item in gc.get_referents(value):
            if item is not kind:
                yield label + '…', item


def _visible(values, what='参数', *, objects=True):
    """(sqlite3 connections and cursors to keep shared, why the replay cannot see into `values`).

    `values` maps a name to an argument (`objects`) or to module state a function reads. Everything they
    hold is looked at, at any depth and without running project code, up to `_LOOK` objects (beyond that
    the replay does not run): an open file, a socket, a database connection other than sqlite3, a sqlite3
    connection holding Python callbacks or a Blob, a generator, a csv reader or writer, a queue or an
    executor keeps the replay from running; for an argument a function, a bound method or a logger does
    too. Module state may hold functions and loggers (a replayed call's log records are dropped)."""
    logging = sys.modules.get('logging')
    quiet = () if objects or logging is None else (logging.Logger, logging.LoggerAdapter, logging.Handler, logging.Manager)
    shared, seen, pending = [], set(), collections.deque()

    def push(value, label, top=False):
        if type(value) not in _PLAIN and id(value) not in seen:
            seen.add(id(value))
            pending.append((value, label, top))

    for name, value in values.items():
        push(value, name, True)
    looked = 0
    while pending:
        value, label, top = pending.popleft()
        if _simple(value):
            continue
        looked += 1
        if looked > _LOOK:
            name = re.match(r'[^.\[…]*', label).group()
            return shared, f'{what} {name} 太大：看了 {_LOOK} 个对象还没看完，不知道里面有没有打开的文件或连接'
        kind = type(value)
        if kind is sqlite3.Cursor:
            shared.append(value)
            value, kind = value.connection, sqlite3.Connection
        if kind is sqlite3.Connection:
            if not any(value is other for other in shared):
                shared.append(value)
            if _callbacks(value):
                return shared, f'{what} {label} 的 sqlite3 连接带着 Python 回调（authorizer、progress、trace 或行工厂），回放后恢复不了'
            continue
        if problem := _unseen(value, kind, objects):
            return shared, f'{what} {label} {problem}'
        if quiet and issubclass(kind, quiet):
            continue
        for name, item in _parts(value, kind, label, top):
            push(item, name)
    return shared, ''


def _shareable(value):
    """Arguments a replay uses as they are: classes and modules are module state (their writes are the
    static check's), and the builtin functions of a module, the methods of builtin types and a few
    immutable values run no project code and cannot change."""
    kind = type(value)
    return (issubclass(kind, type) or kind in (types.ModuleType, types.MethodDescriptorType, types.WrapperDescriptorType,
                                                types.ClassMethodDescriptorType, range, complex, re.Pattern)
            or kind is types.BuiltinFunctionType and (type(value.__self__) is types.ModuleType
                                                      or issubclass(type(value.__self__), type)))


def _unchanged(value, shared):
    """deepcopy returned `value` itself: right for plain data, the shared connections and what a replay shares
    (an immutable tuple of them); anything else returned as it is would be the test's own object."""
    if type(value) in _PLAIN or _simple(value) or _shareable(value) or any(value is other for other in shared):
        return True
    return type(value) in (tuple, frozenset) and all(_unchanged(item, shared) for item in value)


@dataclass
class _Protected:
    """One shared sqlite3 connection under a guard: what it was before, and which protections are in place."""
    connection: object
    changes: int = 0
    callbacks: tuple = ()
    query_only: int = 0
    steps: list = field(default_factory=list)


class _Guard:
    """One guarded replay of one call site; `void` holds the first refusal of the current code, `unseen` why
    the arguments or module state cannot be copied or seen into (then nothing is replayed)."""

    def __init__(self, runtime, arguments, functions=()):
        self.runtime = runtime
        self.shared, self.unseen = _visible(arguments)
        state = {}
        for function, historical in functions:
            state.update(runtime.module_state(function, historical=historical))
        if state and not self.unseen:
            found, self.unseen = _visible(state, '模块全局', objects=False)
            self.shared += [value for value in found if not any(value is other for other in self.shared)]
        self.connections = [value for value in self.shared if type(value) is sqlite3.Connection]
        self.generators = [random, *(value for value in state.values() if type(value) is random.Random)]
        self.void = self.void_old = ''
        self.timed_out = False
        self.protected, self.adopted, self.handlers, self.seeds = [], [], [], []
        self.old = False
        self.functions = set()
        self.authorizer = self._authorize   # one bound method: the connections refer to this very object
        self.code = _value.__code__     # the frame that calls the replayed function: where a location search stops

    def __enter__(self):
        _install()
        self.seeds = [(source.setstate, source.getstate()) for source in self.generators]
        self.handlers = _handlers()
        for handler in self.handlers:
            handler.filters.append(_quiet)
        for connection in self.connections:
            if not self._protect(connection):
                break
        return self

    def __exit__(self, *error):
        for record in reversed(self.protected):
            self._release(record)
        for connection, keeper in self.adopted:
            _forget(connection, keeper)
        for handler in self.handlers:
            _unquiet(handler)
        for setstate, state in self.seeds:
            setstate(state)
        return False

    def _protect(self, connection):
        """Savepoint, read transaction, query_only and authorizer on one shared connection; False (and the
        replay void) when one of them cannot be set up."""
        record = _Protected(connection)
        self.protected.append(record)
        try:
            record.changes = connection.total_changes
            record.callbacks = _callback_state(connection)
            # SQL functions defined in Python run project code on every statement that calls them.
            self.functions |= {name.lower() for name, kind, count in record.callbacks[3]}
            record.query_only = connection.execute('PRAGMA query_only').fetchone()[0]
            connection.execute('SAVEPOINT flowguard_replay')
            record.steps.append('savepoint')
            # A read transaction: nothing can be backed up into the connection. No function is called, so a
            # Python function overriding a built-in one (count) does not run here.
            connection.execute('SELECT 1 FROM sqlite_master LIMIT 1').fetchall()
            connection.execute('PRAGMA query_only=1')
            record.steps.append('query_only')
            connection.set_authorizer(self.authorizer)
            record.steps.append('authorizer')
        except sqlite3.Error as error:
            self._mark(f'回放没有运行：sqlite3 连接装不上回放保护：{type(error).__name__}: {error}')
            return False
        return True

    def _release(self, record):
        """Undo one connection's protection. Each step that fails (the replayed call closed the connection or
        ended its transaction) is recorded, and the remaining steps and connections are still restored."""
        connection = record.connection
        if not record.steps:
            return
        if 'authorizer' in record.steps:
            self._step('去掉回放的 authorizer', connection.set_authorizer, None)
        if 'query_only' in record.steps:
            self._step('恢复 query_only', connection.execute, f'PRAGMA query_only={int(record.query_only)}')
        if self._step('回到 SAVEPOINT', connection.execute, 'ROLLBACK TO flowguard_replay') is not _MISSING:
            self._step('结束 SAVEPOINT', connection.execute, 'RELEASE flowguard_replay')
        changes = self._step('读 total_changes', getattr, connection, 'total_changes')
        if changes is not _MISSING and changes != record.changes:
            self._mark(f'回放被拦住：回放之后数据库仍有改动（total_changes {record.changes} → {changes}）')
        if changes is not _MISSING:
            self._step('恢复连接上的回调', self._callbacks_back, connection, record.callbacks)

    def _step(self, what, action, *args):
        """One step of undoing a connection's protection: its result, or _MISSING with the sqlite3 error
        recorded (the replay is void; the other steps still run)."""
        try:
            return action(*args)
        except sqlite3.Error as error:
            self._mark(f'回放保护收尾出错：{what}：{type(error).__name__}: {error}')
            return _MISSING

    def _callbacks_back(self, connection, before):
        """A replayed call that gave a shared connection a callback, an SQL function or a collation voids the
        replay. Its factories, progress handler and trace callback are put back (the connection held no
        progress or trace callback before, or it would not have been replayed); an SQL function or a
        collation cannot be removed again (passing None leaves a broken entry), so it stays."""
        after = _callback_state(connection)
        if after == before:
            return
        self._mark('回放改了 sqlite3 连接上的回调、SQL 函数或排序规则')
        callables, connection.row_factory, connection.text_factory = before[:3]
        if after[0] != callables:
            connection.set_progress_handler(None, 0)
            connection.set_trace_callback(None)

    def _mark(self, reason):
        if self.old:
            self.void_old = self.void_old or reason
        else:
            self.void = self.void or reason

    def adopt(self, connection):
        """A connection opened during a replayed call is protected like a shared one, without a savepoint (its
        `with` block or commit stays a no-op): an unfinished read keeps nothing from being backed up into it."""
        try:
            keeper = connection.execute('SELECT 1 FROM sqlite_master UNION ALL SELECT 1 UNION ALL SELECT 1')
            connection.execute('PRAGMA query_only=1')
            connection.set_authorizer(self.authorizer)
        except sqlite3.Error as error:
            connection.close()
            raise Refused(self.refuse(f'新建的 sqlite3 连接装不上回放保护：{type(error).__name__}: {error}',
                                      sys._getframe(1))) from error
        self.adopted.append((connection, keeper))

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
        """One replayed call: its outcome, with the arguments copied and every effect refused; None when an
        argument cannot be copied (`unseen`), and then nothing ran."""
        global _CALLING
        previous = _LOCAL.guard
        self.old = old
        outcome = None
        try:
            # No call between these two lines and the `finally` below, so an interruption (the watchdog)
            # cannot leave the switch on: the restoring lines there come first, with no call either.
            _CALLING += 1
            _LOCAL.guard = self
            _wrap()
            arguments = self._copied(bound)
            if arguments is not None:
                outcome = _value(fn, arguments)
        except Refused as error:
            outcome = cells.Raised(error)  # The refusal is already recorded; this whole replay is void.
        finally:
            _CALLING -= 1
            _LOCAL.guard = previous
            if not _CALLING:
                _unwrap()
        self._after(outcome)
        self.old = False
        return outcome

    def _after(self, outcome):
        """After one replayed call: a RecursionError, a write a protected connection refused by itself (a
        backup into it, a Blob), or a shared connection without the guard's authorizer voids the replay."""
        if isinstance(outcome, cells.Raised):
            error = outcome.error
            if isinstance(error, RecursionError):
                self._mark('回放没有结束：递归太深（RecursionError）')
            elif isinstance(error, sqlite3.OperationalError) and str(error) in _PROTECTED_ERRORS:
                trace = error.__traceback__
                while trace is not None and trace.tb_next is not None:
                    trace = trace.tb_next
                self.refuse('往回放保护着的 sqlite3 连接里写（不经过 authorizer 的写入，例如 backup 或 Blob）', trace.tb_frame if trace else None)
        for record in self.protected:
            if 'authorizer' in record.steps and not any(ref is self.authorizer for ref in gc.get_referents(record.connection)):
                self._mark('回放之后 sqlite3 连接上的回放保护不在了（set_authorizer 换掉了它，或者连接被关掉了）')

    def _copied(self, bound):
        """Deep copies of the arguments to replay on, one memo for all (shared objects stay shared); None, with
        `unseen` set, when an argument cannot be copied or deepcopy returns the object itself."""
        memo = {id(value): value for value in self.shared}
        arguments = {}
        for name, value in bound.arguments.items():
            if _simple(value) or id(value) in memo and memo[id(value)] is value or _shareable(value):
                arguments[name] = value
                continue
            try:
                copied = copy.deepcopy(value, memo)
            except (TypeError, ValueError, AttributeError, RecursionError, copy.Error) as error:
                self.unseen = self.unseen or f'参数 {name} 复制不了（{type(error).__name__}: {error}）'
                return None
            if copied is value and not _unchanged(value, self.shared):
                self.unseen = self.unseen or f'参数 {name} 复制不了（deepcopy 返回它本身：{type(value).__name__}）'
                return None
            arguments[name] = copied
        return _binding(bound.signature, arguments)


def _forget(connection, keeper):
    """A connection a replayed call opened gets its usual behaviour back, unless that call closed it."""
    try:
        connection.set_authorizer(None)     # first: the guard's authorizer refuses the PRAGMA below
        keeper.close()
        connection.execute('PRAGMA query_only=0')
    except sqlite3.ProgrammingError:
        pass  # The replayed call closed the connection it opened; nothing is left to restore.


class _Field:
    """One `fields NAME=EXPRESSION` of an anchor: called with the anchor function's own arguments, it
    returns the expression's value in that function's module, the arguments being its local names."""

    def __init__(self, function, name, expression):
        self.name, self.expression, self.namespace = name, expression, function.__globals__
        self.signature = inspect.signature(function, follow_wrapped=False)
        self.code = compile(expression, f'<flowguard fields {name}>', 'eval')

    def __call__(self, *args, **kwargs):
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        # One namespace, so comprehensions and lambdas in the expression see the arguments too.
        return eval(self.code, {**self.namespace, **bound.arguments})

    def definition(self, parameters, line):
        """The expression as a function of the same parameters, at the anchor comment's line, for the
        static check of explicit writes."""
        node = ast.parse(f'def _flowguard_field({", ".join(parameters)}):\n    return ({self.expression})\n').body[0]
        ast.increment_lineno(node, line - 2)      # the expression's own line is the comment's
        return node


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


def _written(targets):
    """The attribute and subscript targets of an assignment or deletion, also inside tuples and starred names."""
    for target in targets:
        if isinstance(target, (ast.Tuple, ast.List)):
            yield from _written(target.elts)
        elif isinstance(target, ast.Starred):
            yield from _written([target.value])
        elif isinstance(target, (ast.Attribute, ast.Subscript)):
            yield target


def _module_data(value):
    """Module state a replay could act on: not code, a class, a module or a simple value."""
    return not (value is _MISSING or type(value) in _PLAIN or _simple(value) or type(value) in _CODE
                or issubclass(type(value), type))


def _read(owner, name):
    return _namespace(owner).get(name, _MISSING)


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
    fields: dict | None = None  # an anchor's `fields` values at the real call, read before it ran
    field_rows: list = field(default_factory=list)  # the same values at each replayed row (None: not read)
    field_reasons: list = field(default_factory=list)  # why a field could not be read: its name and error


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
        self._trees, self._imported, self._projects = {}, {}, {}   # parsed sources, module constants, boundary
        self._bindings = {}     # id(parsed tree) -> (tree, its _binding_facts); the trees are kept in _trees
        self._reads = {}     # (function, historical) → the module state its static check found it reads
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

    def _remember_constant(self, namespace, name, old_value, current, tree):
        if name not in current and ({name, '*', '__getattr__'} & self._binding_facts(tree).keys()):
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
            tree = self._parsed(source, str(self.root / file))
            node = dict(_functions(tree)).get(fn.__qualname__)
            if node is None:
                raise ValueError('function is absent or structurally different in the baseline')
            current = _definition(fn)
            constants = self._module_constants(source, fn.__module__, set(), True)
            current_text = (self.root / file).read_text(encoding='utf-8-sig')
            current_tree = self._parsed(current_text)
            current_constants = self._module_constants(current_text, fn.__module__, set(), False)
            # All old constants in this module are swapped together: helpers use
            # their own real globals, including imported aliases to functions.
            old_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            for name in (set(fn.__code__.co_names) | old_names) & constants.keys():
                self._remember_constant(fn.__globals__, name, constants[name], current_constants, current_tree)
            local = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
            local.update(n.id for n in sites.own_nodes(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
            old_bindings, current_bindings = self._binding_facts(tree), self._binding_facts(current_tree)
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
                        values = self._module_constants(source, owner.__name__, set(), True) if source is not None else {}
                        value = vars(owner).get(part.attr)
                        if part.attr in values:
                            current_text = Path(imported_file).read_text(encoding='utf-8-sig')
                            current_tree = self._parsed(current_text)
                            current_values = self._module_constants(current_text, owner.__name__, set(), False)
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
        """project_code, once per file for this runtime (its callers ask for every name a function reads)."""
        if file not in self._projects:
            from flowguard.structure.paths import project_code
            self._projects[file] = project_code(file, self.root)
        return self._projects[file]

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

    def safety(self, function, arguments=None, seen=None, *, historical=False, node=None, reads=None):
        """Why this call is not replayed, or ''. Only explicit writes stop a replay statically: a
        `global`/`nonlocal` name the function assigns; an assignment, deletion or mutating method call on
        module state (a module global, a module's or a class's attribute, also through a local name bound
        to one); module state passed to a standard function that changes its first argument (`heapq`,
        `bisect.insort`, `next`, `list.append(...)`); a call that changes a sqlite3 connection the replay
        shares with the test (`close`, `create_function`, `backup` ...); here and in the project helpers it
        calls. The arguments, and the module state the function and those helpers read, must be visible to
        the replay guard. Reads, dates, properties and unresolved calls run under the guard instead.
        `node` checks another definition in the function's module instead (an anchor's `fields`
        expression, whose lines are the anchor comment's)."""
        fn = sites.unwrap(function)
        top = seen is None
        seen = set() if seen is None else seen
        reads = {} if reads is None else reads
        if fn in seen and node is None:
            return ''
        seen.add(fn)
        if top and arguments:
            unseen = _visible(arguments)[1]
            if unseen:
                return '看不清：' + unseen
        if node is None and not historical and (inspect.isgeneratorfunction(fn) or inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)):
            return '看不清：生成器或协程函数的函数体在回放里不运行'
        written = node is not None       # the given definition carries its own source lines
        if not written:
            try:
                if historical:
                    if fn not in self.patches:
                        return 'baseline function is unavailable: ' + self.unavailable.get(fn, fn.__qualname__)
                    node = self.patches[fn].node
                    # The baseline definition, not the current function object, decides what it was.
                    if isinstance(node, ast.AsyncFunctionDef) or any(isinstance(part, (ast.Yield, ast.YieldFrom)) for part in sites.own_nodes(node)):
                        return '看不清：生成器或协程函数的函数体在回放里不运行'
                else:
                    node = _definition(fn)
            except (OSError, TypeError, SyntaxError):
                return 'source is unavailable for side-effect checking'
        parts = list(sites.own_nodes(node))
        declared = {name for part in parts if isinstance(part, (ast.Global, ast.Nonlocal)) for name in part.names}
        stored = {part.id for part in parts if isinstance(part, ast.Name) and isinstance(part.ctx, (ast.Store, ast.Del))}
        # Modules imported in the function body: `import a.b` binds `a`, `import a.b as c` binds `a.b`.
        imported = {alias.asname or alias.name.partition('.')[0]: alias.name if alias.asname else alias.name.partition('.')[0]
                    for part in parts if isinstance(part, ast.Import) for alias in part.names}
        modules = {name: sys.modules[module] for name, module in imported.items() if module in sys.modules}
        local = ({arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                                      *(x for x in (node.args.vararg, node.args.kwarg) if x))} | stored | set(imported)) - declared
        namespace = fn.__globals__
        # A local name bound to an attribute/subscript chain (`cache = CACHE`, `m = settings`, `for row in ROWS`)
        # names what that chain names; flow-insensitive, like `stored`.
        aliases = {}
        for part in parts:
            if isinstance(part, (ast.Assign, ast.AnnAssign)) and part.value is not None and _chain(part.value):
                targets = part.targets if isinstance(part, ast.Assign) else [part.target]
                if len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id not in declared:
                    aliases.setdefault(targets[0].id, part.value)
            elif isinstance(part, (ast.For, ast.AsyncFor)) and isinstance(part.target, ast.Name) and _chain(part.iter):
                aliases.setdefault(part.target.id, ast.Subscript(part.iter, ast.Constant(None), ast.Load()))

        def line(part):
            return part.lineno if historical or written else fn.__code__.co_firstlineno + part.lineno - 1

        def origin(expression, depth=0):
            """(global name, its value, whether the chain went through a call, whether it went through an
            attribute or item) an attribute/subscript/call chain starts from, following local aliases; None
            for a local value."""
            called = inside = False
            while isinstance(expression, (ast.Attribute, ast.Subscript, ast.Call)):
                called = called or isinstance(expression, ast.Call)
                inside = inside or not isinstance(expression, ast.Call)
                expression = expression.func if isinstance(expression, ast.Call) else expression.value
            if not isinstance(expression, ast.Name) or depth > 8:
                return None
            name = expression.id
            if name in modules:
                return name, modules[name], called, inside
            if name in aliases:
                found = origin(aliases[name], depth + 1)
                return found and (found[0], found[1], found[2] or called, found[3] or inside)
            if name in local:
                return None
            value = namespace.get(name, _MISSING)
            return None if value is _MISSING else (name, value, called, inside)

        def shared(expression, owner=False):
            """The module-level object a chain starts from, if it is module state: a global that is not a
            function or a simple value, or (through attributes and items, without a call) a module or a class.
            `owner`: the chain is the object whose attribute or item is written, so a module or a class itself
            counts too (`settings.LIMIT = 4`); a call on a module or a class itself is no write (`os.remove`)."""
            found = origin(expression)
            if found is None or _simple(found[1]):
                return None
            name, value, called, inside = found
            if type(value) is types.ModuleType or issubclass(type(value), type):
                return None if called or not (owner or inside) else name
            return None if callable(value) else name

        def current(expression, depth=0):
            """The object a chain names in this call (an argument or module state), read without running
            project code; _MISSING when it is not known statically."""
            if depth > 8:
                return _MISSING
            if isinstance(expression, ast.Name):
                name = expression.id
                if name in aliases:
                    return current(aliases[name], depth + 1)
                if arguments and name in arguments:
                    return arguments[name]
                if name in modules:
                    return modules[name]
                return _MISSING if name in local else namespace.get(name, _MISSING)
            if isinstance(expression, ast.Attribute):
                owner = current(expression.value, depth + 1)
                return _MISSING if owner is _MISSING else _namespace(owner).get(expression.attr, _MISSING)
            if isinstance(expression, ast.Subscript) and isinstance(expression.slice, ast.Constant):
                owner = current(expression.value, depth + 1)
                key = expression.slice.value
                if type(owner) is dict and type(key) in _PLAIN:
                    return owner.get(key, _MISSING)
                if type(owner) in (list, tuple) and type(key) is int and -len(owner) <= key < len(owner):
                    return owner[key]
            return _MISSING

        def connection(expression):
            return type(current(expression)) in (sqlite3.Connection, sqlite3.Cursor)

        for part in parts:
            if isinstance(part, (ast.Global, ast.Nonlocal)) and set(part.names) & stored:
                kind = '全局变量' if isinstance(part, ast.Global) else '外层变量'
                return f'明确的写操作：第 {line(part)} 行给{kind} {", ".join(sorted(set(part.names) & stored))} 赋值'
            if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load) and part.id not in local and part.id not in modules:
                value = namespace.get(part.id, _MISSING)
                if _module_data(value):
                    reads.setdefault(part.id, functools.partial(namespace.get, part.id, _MISSING))
            elif isinstance(part, ast.Attribute) and isinstance(part.ctx, ast.Load) and isinstance(part.value, ast.Name) \
                    and (found := origin(part.value)) and not found[2] and not found[3] \
                    and (type(found[1]) is types.ModuleType or issubclass(type(found[1]), type)):
                if _module_data(_namespace(found[1]).get(part.attr, _MISSING)):
                    reads.setdefault(f'{found[0]}.{part.attr}', functools.partial(_read, found[1], part.attr))
            targets = part.targets if isinstance(part, (ast.Assign, ast.Delete)) else [part.target] \
                if isinstance(part, ast.AugAssign) or isinstance(part, ast.AnnAssign) and part.value is not None else []
            for target in _written(targets):
                if name := shared(target.value, owner=True):
                    return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{ast.unparse(target)}）'
                if isinstance(target, ast.Attribute) and connection(target.value):
                    return (f'明确的写操作：第 {line(part)} 行改了 sqlite3 连接 {ast.unparse(target.value)} 的 {target.attr}'
                            '（连接复制不了，回放会改到测试自己的连接）')
            if not isinstance(part, ast.Call):
                continue
            if isinstance(part.func, ast.Attribute) and part.func.attr in _MUTATORS and (name := shared(part.func.value)):
                return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{ast.unparse(part.func)}）'
            if isinstance(part.func, ast.Name) and part.func.id in ('setattr', 'delattr') and part.func.id not in local \
                    and part.args and (name := shared(part.args[0], owner=True)):
                return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{part.func.id}）'
            target = _resolve(part.func, namespace)
            if id(target) in _MUTATING_IDS and part.args and (name := shared(part.args[0])):
                return f'明确的写操作：第 {line(part)} 行改了模块里的 {name}（{ast.unparse(part.func)}）'
            if isinstance(part.func, ast.Attribute) and part.func.attr in _CONNECTION_CALLS and connection(part.func.value) \
                    and (part.func.attr == 'close' or type(current(part.func.value)) is sqlite3.Connection):
                return (f'明确的写操作：第 {line(part)} 行在 sqlite3 连接 {ast.unparse(part.func.value)} 上调用 {part.func.attr}'
                        '（连接复制不了，回放会作用在测试自己的连接上）')
            if type(target) is types.FunctionType and self._project(target):
                # The helper's parameters name what this call passes it, as far as that is known statically.
                passed = None
                if not any(isinstance(item, ast.Starred) for item in part.args) and all(item.arg for item in part.keywords):
                    code = target.__code__
                    names = code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]
                    passed = {name: current(item) for name, item in zip(names[:code.co_argcount], part.args)}
                    passed.update((item.arg, current(item.value)) for item in part.keywords if item.arg in names)
                    passed = {name: value for name, value in passed.items() if value is not _MISSING} or None
                if problem := self.safety(target, passed, seen, historical=historical and target in self.patches, reads=reads):
                    return problem
        if top:
            if not written:
                self._reads[(fn, historical)] = dict(reads)
            values = {label: value for label, read in reads.items() if (value := read()) is not _MISSING}
            if values and (unseen := _visible(values, '模块全局', objects=False)[1]):
                return '看不清：' + unseen
        return ''

    def module_state(self, function, *, historical=False):
        """The module state (non-simple globals, module and class attributes) the function and the project
        helpers it calls read, as the static check found it: name → current value."""
        fn = sites.unwrap(function)
        if (fn, historical) not in self._reads:
            self.safety(fn, historical=historical)
        values = {label: read() for label, read in self._reads.get((fn, historical), {}).items()}
        return {label: value for label, value in values.items() if value is not _MISSING}

    def field_values(self, original, bound, fields, line, reading):
        """An anchor's `fields` values, with the real call's arguments and with each replayed row's, in
        one guard of their own: reading them is a guarded execution like a replay (static explicit-write
        check, audit hook, sqlite savepoint and authorizer, copied arguments). A value that cannot be read
        leaves its call without fields and names the field and its error in `reading.field_reasons`."""
        fn = sites.unwrap(original)
        evaluators = [_Field(fn, name, expression) for name, expression in fields]
        parameters = list(inspect.signature(fn, follow_wrapped=False).parameters)
        for evaluator in evaluators:
            problem = self.safety(fn, None, historical=False, node=evaluator.definition(parameters, line))
            if problem:
                reading.field_reasons.append(f'字段 {evaluator.name}：{problem}')
                return
        guard = _Guard(self, bound.arguments, ((fn, False),))
        if guard.unseen:
            reading.field_reasons.append(f'字段 {", ".join(name for name, _ in fields)}：看不清：{guard.unseen}')
            return
        calls = [bound, *(_binding(bound.signature, {**bound.arguments, **inputs}) for inputs, _ in reading.rows)]
        found = []
        with guard, _bounded(guard):
            for arguments in calls:
                values = {}
                for evaluator in evaluators:
                    value = guard.call(evaluator, arguments)
                    if guard.unseen:
                        guard.void = guard.void or '看不清：' + guard.unseen
                    if guard.void:
                        reading.field_reasons.append(f'字段 {evaluator.name}：{guard.void}')
                        break
                    if isinstance(value, cells.Raised):
                        reason = f'字段 {evaluator.name} 求不出值：{type(value.error).__name__}: {value.error}'
                    elif not _simple(value):
                        reason = f'字段 {evaluator.name} 的值不是简单数据（{type(value).__name__}）'
                    else:
                        values[evaluator.name] = value
                        continue
                    if reason not in reading.field_reasons:
                        reading.field_reasons.append(reason)
                    values = None
                    break
                if guard.void:
                    break
                found.append(values)
        if guard.void:      # a refused effect voids every value this guard read
            if not any(reason.endswith(guard.void) for reason in reading.field_reasons):
                reading.field_reasons.append(f'字段 {", ".join(name for name, _ in fields)}：{guard.void}')
            return
        reading.fields, reading.field_rows = found[0], found[1:]

    def guarded(self, fn, bound):
        """One guarded call that is not a test's own call: (outcome, why it was refused or '')."""
        guard = _Guard(self, bound.arguments, ((fn, False),))
        if guard.unseen:
            return None, '看不清：' + guard.unseen
        outcome = None
        with guard, _bounded(guard):
            outcome = guard.call(fn, bound)
        if guard.unseen:
            return None, '看不清：' + guard.unseen
        return outcome, guard.void

    def _lost(self, reading, owner, bound):
        """Mark a grey reading lost when the baseline code, in this same context, replays cleanly:
        compared with the baseline it would have been red or green."""
        patch = self.register(owner)
        if patch is None or self.safety(owner, bound.arguments, historical=True):
            return
        guard = _Guard(self, bound.arguments, ((owner, True),))
        if guard.unseen:
            return
        outcome = None
        with guard, _bounded(guard), self.old_code():
            outcome = guard.call(patch.callable(), bound, old=True)
        if not (guard.void_old or guard.void or guard.unseen) and _data(outcome):
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

    def observe(self, original, bound, *, owner=None, name='', axes=None, private=False, fields=(), line=0):
        """Metadata and replay are private; the real call always runs outside them. An anchor's
        `fields` are read before the real call, with its arguments and each replayed row's."""
        owner = sites.unwrap(owner or original)
        if (_PRIVATE.get() and not private) or owner in _OBSERVING.get():
            return original(*bound.args, **bound.kwargs)
        token = _PRIVATE.set(True)
        observing = _OBSERVING.set(_OBSERVING.get() | {owner})
        index = len(self.readings)
        try:
            if isinstance(axes, Reading):   # a comparison stored under the same fingerprint: kept, not replayed
                self.readings.append(axes)
            else:
                self._replay_rows(original, bound, owner=owner, name=name, axes=axes)
            if fields and index < len(self.readings):
                self.field_values(original, bound, fields, line, self.readings[index])
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
        runs in one guard; a refused effect voids the reading. The reading is grey until the replay has
        completely finished: an error of FlowGuard's own on the way leaves no green reading behind."""
        reading = Reading(name or owner.__qualname__, owner.__module__ + ':' + owner.__qualname__,
                          test=self.test, baseline=self.baseline, status='grey', reasons=['回放没有完整结束'])
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
        guard = _Guard(self, bound.arguments, ((original, False), (owner, True)))
        outcomes = None, None, ''
        if not guard.unseen:
            with guard, _bounded(guard):
                outcomes = self._grid(guard, reading, original, bound, patch, itertools.chain(points, neighbours))
        baseline, again, opaque = outcomes
        if guard.unseen:
            problem = '看不清：' + guard.unseen
            reading.reasons = [problem]
            reading.comparison_status, reading.comparison_reasons = 'grey', [problem]
            reading.rows.clear()
            reading.changed.clear()
            return
        if guard.void:
            reading.status, reading.reasons = 'grey', [guard.void]
            reading.rows.clear()
            reading.changed.clear()
            if not guard.timed_out:     # a slow machine is no lost observation
                self._lost(reading, owner, bound)
            return
        if opaque or not _data(again):
            reading.status, reading.reasons = 'grey', [f'回放结果不是可以比较的简单数据（{opaque or type(again).__name__}）：不运行它的比较运算']
            reading.rows.clear()
            reading.changed.clear()
            self._lost(reading, owner, bound)
            return
        if guard.void_old:
            reading.comparison_status = 'grey'
            reading.comparison_reasons.append('基准代码的' + guard.void_old)
            reading.changed.clear()
        reading.status, reading.reasons = 'ok', []
        if not outcome_equal(baseline, again):
            reading.status, reading.reasons = 'grey', ['original-value recheck changed: possible side effect or unstable input']
            reading.rows.clear()
            reading.changed.clear()
        if not supplied_axes:
            reading.reasons.append('comparison grid is not a proof of partition completeness')

    def _grid(self, guard, reading, original, bound, patch, inputs):
        """The replayed calls of one reading: the original values, every grid point (the current and the
        baseline code), then the original values again, at least one clock tick after the first call;
        (first outcome, recheck outcome, the type of an outcome that cannot be compared)."""
        if guard.void:
            return None, None, ''
        baseline = guard.call(original, bound)
        if guard.unseen:
            return None, None, ''
        clocks = _clocks()
        opaque = '' if _data(baseline) else type(baseline).__name__
        for point in inputs:
            if guard.void or opaque:
                break
            arguments = _binding(bound.signature, {**bound.arguments, **point})
            now = guard.call(original, arguments)
            old = None
            if patch is not None and not guard.void_old:
                with self.old_code():
                    old = guard.call(patch.callable(), arguments, old=True)
            if not _data(now) or not _data(old):
                opaque = type(now if not _data(now) else old).__name__
                break
            reading.rows.append((point, now))
            if patch is not None and not guard.void_old and not outcome_equal(old, now):
                reading.changed.append((point, old, now))
        if guard.void or opaque:
            return baseline, None, opaque
        _next_tick(clocks)
        return baseline, guard.call(original, bound), opaque

    @contextmanager
    def hook(self, function, *, name='', axes=None, private=False, fields=(), line=0):
        owner = sites.unwrap(function)
        _private_call(self.register, owner)
        def callback(original, bound):
            if (_PRIVATE.get() and not private) or owner in _OBSERVING.get():
                return original(*bound.args, **bound.kwargs)
            if callable(axes):
                values = _private_call(axes, original, bound)
            else:
                values = axes
            return self.observe(original, bound, owner=owner, name=name, axes=values, private=private,
                                fields=fields, line=line)
        callback.__flowguard_transport__ = (type(self).observe.__code__,)
        with sites.intercepted(owner, callback) as original:
            yield original

    @staticmethod
    def observer_issues():
        return [issue for record in _HUB.records for issue in record.issues]

    def record(self, codes=(), *, predicate=None, callback=None, private=False, ignored=(), entry_only=False, events=None):
        """One hub owns local anchor events and explicit dynamic footprints. The record appends its events
        (anchor, phase, values) to `events`, by default the runtime's own list."""
        return _Record(self, codes, predicate, callback, private, ignored, entry_only, events)

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
