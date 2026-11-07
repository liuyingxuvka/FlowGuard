"""The one isolated transport for real anchor observations and calibrated pytest calls.

Only the selected anchor is intercepted.  A controlled stop remains a failed
pytest report; it never becomes an ordinary test confirmation or a cached pass.
"""
from __future__ import annotations

import ast
import base64
from contextlib import contextmanager, ExitStack, redirect_stdout, redirect_stderr
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import dis
from enum import Enum
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path, PosixPath, WindowsPath
import subprocess
import sys
import tempfile

from .cells import Raised
from . import sites

_FACTS = ContextVar('flowguard_calibration_facts', default=None)
_ACTIVE = ContextVar('flowguard_calibration_active', default=False)
_REMOTE = {}


@dataclass(frozen=True)
class _EnumRef:
    module: str
    qual: str
    name: str
    value: object


def _encode(value, _active=None):
    if value is None or type(value) in (bool, int, str):
        return ['literal', value]
    if type(value) is float:
        return ['float', repr(value)]
    if isinstance(value, _EnumRef):
        return ['enum', value.module, value.qual, value.name, _encode(value.value)]
    if isinstance(value, Enum):
        data = object.__getattribute__(value, '__dict__')
        raw = data.get('_value_')
        if type(raw) not in (str, int, bool, float, bytes, type(None)):
            raise TypeError('enum requires a primitive source identity')
        return ['enum', type(value).__module__, type(value).__qualname__, data['_name_'], _encode(raw)]
    if type(value) is Raised:
        error = value.error
        identity = getattr(error, '_flowguard_remote_identity', None) or [(c.__module__, c.__qualname__) for c in type(error).__mro__ if c is not object]
        return ['raised', identity, str(error)]
    if type(value) is Decimal:
        return ['decimal', str(value)]
    if type(value) is datetime:
        return ['datetime', value.isoformat()]
    if type(value) is date:
        return ['date', value.isoformat()]
    if type(value) is timedelta:
        return ['timedelta', value.days, value.seconds, value.microseconds]
    if type(value) in (PosixPath, WindowsPath):
        return ['path', str(value)]
    if type(value) is bytes:
        return ['bytes', base64.b64encode(value).decode('ascii')]
    if type(value) in (list, tuple, dict):
        active = set() if _active is None else _active
        if id(value) in active:
            raise TypeError('cyclic observation cannot be transferred')
        active.add(id(value))
        try:
            if type(value) is dict:
                return ['dict', [[_encode(k, active), _encode(v, active)] for k, v in value.items()]]
            return [type(value).__name__, [_encode(v, active) for v in value]]
        finally:
            active.remove(id(value))
    raise TypeError('observation cannot transfer ' + type(value).__qualname__)


def _error(identity, message):
    """Remote type identity without importing the project's class in the caller."""
    import builtins
    key = tuple(tuple(v) for v in identity)
    if key[0][0] == 'builtins':
        kind = getattr(builtins, key[0][1], None)
        if isinstance(kind, type) and issubclass(kind, Exception):
            error = kind(message)
            if str(error) == message:
                return error
    if key not in _REMOTE:
        base = Exception
        for module, qual in reversed(key[:-1] if key[-1][1] == 'BaseException' else key):
            if qual == 'Exception':
                continue
            base = type(qual.rsplit('.', 1)[-1], (base,), {
                '__module__': module, '__qualname__': qual,
                '__str__': lambda self: self._flowguard_message})
        _REMOTE[key] = base
    error = _REMOTE[key](message)
    error._flowguard_message = message
    error._flowguard_remote_identity = key
    return error


def _decode(data):
    tag, *parts = data
    if tag == 'literal': return parts[0]
    if tag == 'float': return float(parts[0])
    if tag == 'decimal': return Decimal(parts[0])
    if tag == 'datetime': return datetime.fromisoformat(parts[0])
    if tag == 'date': return date.fromisoformat(parts[0])
    if tag == 'timedelta': return timedelta(days=parts[0], seconds=parts[1], microseconds=parts[2])
    if tag == 'path': return Path(parts[0])
    if tag == 'bytes': return base64.b64decode(parts[0])
    if tag in ('tuple', 'list'):
        values = [_decode(v) for v in parts[0]]
        return tuple(values) if tag == 'tuple' else values
    if tag == 'dict': return {_decode(k): _decode(v) for k, v in parts[0]}
    if tag == 'enum': return _EnumRef(parts[0], parts[1], parts[2], _decode(parts[3]))
    if tag == 'raised': return Raised(_error(*parts))
    raise ValueError('unknown private observation tag')


def outcome_key(value):
    """One equality key for local/remote actual outcomes, without target imports."""
    def canonical(data):
        if data[0] == 'dict':
            items = [(canonical(k), canonical(v)) for k, v in data[1]]
            return ['dict', sorted(items, key=lambda p: json.dumps(p[0], sort_keys=True))]
        if data[0] in ('tuple', 'list'):
            return [data[0], [canonical(v) for v in data[1]]]
        return data
    return json.dumps(canonical(_encode(value)), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def outcome_equal(first, second):
    """Existing numerical/Refused semantics plus cross-process exception identity."""
    from .cells import same
    if isinstance(first, (Enum, _EnumRef)) or isinstance(second, (Enum, _EnumRef)):
        return outcome_key(first) == outcome_key(second)
    if isinstance(first, Raised) or isinstance(second, Raised):
        return isinstance(first, Raised) and isinstance(second, Raised) and outcome_key(first) == outcome_key(second)
    return same(first, second)


def _observation(status, anchor, value=None, reasons=()):
    from .anchors import Observation, _accepts
    if status == 'ok' and anchor.kind == 'sensor' and not isinstance(value, Raised):
        try:
            accepted = _accepts(anchor.output_type, value)
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return Observation('grey', value, ('declared return type is not supported for observation',), anchor.target)
        if not accepted:
            return Observation('red', value, ('actual return does not match the anchor return type',), anchor.target)
    return Observation(status, value, tuple(reasons), anchor.target)


@contextmanager
def _execution_session(root, *, facts=None):
    root = Path(root).resolve()
    current = _FACTS.get()
    if current is not None and current[0] == root:
        yield
        return
    token = _FACTS.set((root, {} if facts is None else facts))
    try:
        yield
    finally:
        _FACTS.reset(token)


def probe_context(config):
    """Private capability shared through the real pytest config across SDK namespaces."""
    context = getattr(config, '_flowguard_calibration_probe', None)
    owner = getattr(context, 'owner', None)
    return bool(getattr(context, 'active', False) and getattr(context, 'config', None) is config
                and owner is not None and config.pluginmanager.is_registered(owner)
                and getattr(owner, '_flowguard_calibration_driver', False))


class _Stop(BaseException):
    pass


class _Unsupported(BaseException):
    pass


class _Driver:
    _flowguard_calibration_driver = True

    def __init__(self, root, anchor, values, stage, expected_fn=None):
        self.root, self.anchor, self.values, self.stage = root, anchor, values, stage
        self.expected_fn = expected_fn
        self.outcomes, self.reports, self.problems = [], [], []
        self.phase = ''
        self.selected = 0
        self.stack = None
        self.ready = False
        self.config = self.previous = self.context = None
        self.running = False
        self.entries = []

    def pytest_configure(self, config):
        from types import SimpleNamespace
        self.config = config
        self.previous = getattr(config, '_flowguard_calibration_probe', None)
        self.context = SimpleNamespace(active=True, config=config, owner=self)
        config._flowguard_calibration_probe = self.context
        # Pytest has installed its assertion-rewrite hook by configure. Keep the
        # one delegating source finder ahead of it before collection, even in
        # projects that do not permanently enable FlowGuard's pytest plugin.
        from .imports import prepare
        prepare(self.root)

    def close(self):
        if self.context is not None:
            self.context.active = False
            if getattr(self.config, '_flowguard_calibration_probe', None) is self.context:
                if self.previous is None:
                    del self.config._flowguard_calibration_probe
                else:
                    self.config._flowguard_calibration_probe = self.previous

    def pytest_unconfigure(self, config):
        self.close()

    def pytest_collection_modifyitems(self, items):
        self.selected = len(items)
        if len(items) != 1:
            self.problems.append('calibrated_by must select exactly one test, including its parameter id')

    def _install(self):
        if self.ready or self.stack is None:
            return
        try:
            fn = sites.unwrap(sites.resolve_loaded(self.anchor.target))
        except (AttributeError, sites.NotMutable):
            return  # setup may legitimately import the module later
        if self.expected_fn is not None and fn is not self.expected_fn:
            self.problems.append('calibration test rebound the actual anchor function')
            return
        if not inspect.isfunction(fn) or fn.__code__.co_freevars or inspect.iscoroutinefunction(fn) or inspect.isgeneratorfunction(fn) or inspect.isasyncgenfunction(fn):
            self.problems.append('calibration closure/async/generator/non-function is unsupported')
            return
        expected = (Path(self.root) / self.anchor.file).resolve()
        if Path(fn.__code__.co_filename).resolve() != expected or fn.__qualname__.replace('.<locals>', '') != self.anchor.qual:
            self.problems.append('loaded function does not match the actual source anchor')
            return
        from .flow import _TraceUnavailable
        try:
            if self.stage == 'baseline':
                self.stack.enter_context(self._monitor(fn))
            else:
                ignored = set()
                self.stack.enter_context(self._observing(ignored=ignored))
                self.stack.enter_context(sites.intercepted(fn, self._call))
                ignored.add(fn.__code__)
        except (sites.NotMutable, _TraceUnavailable) as error:
            self.problems.append(str(error))
            return
        self.ready = True

    @contextmanager
    def _observing(self, callback=None, *, ignored=()):
        from .flow import _TraceScope
        scope = _TraceScope(callback, ignored=ignored)
        try:
            with scope:
                yield
        finally:
            self.problems.extend(scope.problems)

    def _monitor(self, fn):
        code, frames = fn.__code__, {}
        def trace(frame, event, arg):
            if frame.f_code is not code or self.phase not in ('setup', 'call'):
                return None
            if event == 'call':
                self._entry(frame)
                frames[frame] = None
            elif event == 'exception':
                frames[frame] = arg[1]
            elif event == 'return':
                operation = dis.opname[frame.f_code.co_code[frame.f_lasti]]
                error = frames.pop(frame, None)
                if operation in ('RETURN_VALUE', 'RETURN_CONST'):
                    self.outcomes.append(arg)
                elif isinstance(error, Exception):
                    self.outcomes.append(Raised(error))
                else:
                    self.problems.append('target did not return a supported value/exception')
            return trace
        return self._observing(trace)

    def _entry(self, frame):
        actual = {}
        for parameter in self.anchor.parameters:
            if parameter.name in frame.f_locals:
                try:
                    actual[parameter.name] = _encode(frame.f_locals[parameter.name])
                except TypeError:
                    continue  # other fixture-bound opaque values are not invented
        self.entries.append(actual)

    def _value_in_context(self, incoming, original, *, function=None, parameter=''):
        if isinstance(incoming, (Enum, _EnumRef)):
            source = next((p.source_type for p in self.anchor.parameters if p.name == parameter), '')
            try:
                expression = ast.parse(source, mode='eval').body
                names = []
                while isinstance(expression, ast.Attribute):
                    names.append(expression.attr); expression = expression.value
                if not isinstance(expression, ast.Name) or function is None:
                    raise ValueError('no static enum name')
                enum_type = function.__globals__.get(expression.id)
                for name in reversed(names):
                    if not inspect.ismodule(enum_type): raise ValueError('enum owner is not an imported module')
                    enum_type = vars(enum_type).get(name)
                if not isinstance(original, Enum) or type(original) is not enum_type:
                    raise ValueError('native enum does not match its source binding')
            except (SyntaxError, ValueError):
                raise _Unsupported('enum parameter has no verified actual source type')
        if isinstance(incoming, Enum):
            if not isinstance(original, Enum) or type(incoming) is not type(original):
                raise _Unsupported('current enum object differs from its native test type')
            return incoming
        if not isinstance(incoming, _EnumRef):
            return incoming
        if not isinstance(original, Enum) or (type(original).__module__, type(original).__qualname__) != (incoming.module, incoming.qual):
            raise _Unsupported('enum input has no matching native test parameter identity')
        members = type(original).__dict__.get('_member_map_', {})
        member = members.get(incoming.name)
        if member is None or _encode(member) != _encode(incoming):
            raise _Unsupported('enum member identity differs from the actual test type')
        return member

    def _call(self, original, bound):
        __tracebackhide__ = lambda info: info.errisinstance(_Stop)
        if self.running:
            raise _Unsupported('recursive calibration target is ambiguous')
        if self.stage == 'case':
            unknown = set(self.values) - {p.name for p in self.anchor.parameters}
            if unknown:
                raise _Unsupported('values name undeclared anchor parameters: ' + ', '.join(sorted(unknown)))
            for name, value in self.values.items():
                bound.arguments[name] = self._value_in_context(value, bound.arguments.get(name), function=original, parameter=name)
        self.running = True
        previous_profile = sys.getprofile()
        if previous_profile is not None and not callable(previous_profile):
            raise _Unsupported('existing profiler cannot be composed with anchor entry observation')
        def entered(frame, event, arg):
            if previous_profile is not None:
                previous_profile(frame, event, arg)
            if event == 'call' and frame.f_code is original.__code__:
                self._entry(frame)
        sys.setprofile(entered)
        try:
            try:
                outcome = original(*bound.args, **bound.kwargs)
            except Exception as error:
                outcome = Raised(error)
            self.outcomes.append(outcome)
        finally:
            sys.setprofile(previous_profile)
            self.running = False
        if len(self.entries) != 1:
            raise _Unsupported('actual target entry is ambiguous')
        if self.stage == 'case' and any(self.entries[0].get(name) != _encode(value) for name, value in self.values.items()):
            raise _Unsupported('replacement did not enter the actual target')
        raise _Stop('anchor returned; controlled calibration stop is not a test pass')

    def pytest_runtest_protocol(self, item):
        if self.selected != 1:
            yield
            return
        with ExitStack() as self.stack:
            self._install()
            yield
        self.stack = None

    def pytest_runtest_setup(self, item):
        self.phase = 'setup'
        yield
        self.phase = ''

    def pytest_runtest_call(self, item):
        self._install()
        self.phase = 'call'
        yield
        self.phase = ''

    def pytest_runtest_teardown(self, item):
        self.phase = 'teardown'
        yield
        self.phase = ''

    def pytest_runtest_makereport(self, item, call):
        report = yield
        result = report.get_result()
        error = call.excinfo.value if call.excinfo is not None else None
        if isinstance(error, _Unsupported):
            self.problems.append(str(error))
        self.reports.append((result.when, result.outcome, isinstance(error, _Stop)))


def _stage(root, anchor, values, stage, expected_fn=None):
    import pytest
    from .config import load_config, setup_path
    from .imports import prepare
    from .anchors import _source
    try:
        _source(root, anchor)
    except (OSError, ValueError, SyntaxError) as error:
        return dict(status='red', reasons=[str(error)])
    if anchor.kind != 'sensor' or anchor.source_role != 'production':
        return dict(status='grey', reasons=['test driving requires a production sensor anchor'])
    if set(values) - {p.name for p in anchor.parameters}:
        return dict(status='red', reasons=['values name undeclared anchor parameters'])
    from .anchors import _accepts
    for parameter in anchor.parameters:
        if parameter.name in values:
            try:
                accepted = _accepts(parameter.source_type, values[parameter.name])
            except (ValueError, SyntaxError, TypeError, AttributeError):
                continue  # fixture-bound non-simple types do not claim a finite domain
            if not accepted:
                return dict(status='red', reasons=[parameter.name + ': value does not have the source parameter type'])
    cfg = load_config(root)
    setup_path(cfg)
    prepare(root)
    path, separator, _ = anchor.calibrated_by.partition('::')
    test = (Path(root) / path).resolve()
    if not separator or not test.is_relative_to(Path(root).resolve()) or not test.is_file():
        return dict(status='grey', reasons=['calibrated_by must name an existing project test node'])
    driver = _Driver(root, anchor, values, stage, expected_fn)
    code = _run_pytest(root, anchor.calibrated_by, driver)
    if driver.problems:
        return dict(status='grey', reasons=driver.problems)
    if driver.selected != 1 or len(driver.outcomes) != 1:
        return dict(status='grey', reasons=['test must reach the actual anchor exactly once; target may be absent or ambiguous'])
    failed = [(phase, outcome, stop) for phase, outcome, stop in driver.reports if outcome != 'passed']
    if stage == 'baseline':
        if code != 0 or failed:
            return dict(status='red', reasons=['original calibration test did not pass completely'])
    elif code == 0 or not any(stop for _, _, stop in failed):
        return dict(status='grey', reasons=['controlled stop did not escape the test as a non-passing report'])
    elif any(phase == 'teardown' and outcome != 'passed' or not stop for phase, outcome, stop in failed):
        return dict(status='red', reasons=['calibration had another test/fixture failure besides controlled stop'])
    if anchor.qual.endswith('__init__') and driver.outcomes[0] is None:
        return dict(status='grey', reasons=['constructor None is not a judgment observation'])
    try:
        outcome = _encode(driver.outcomes[0])
    except (TypeError, ValueError) as error:
        return dict(status='grey', reasons=[str(error)])
    return dict(status='ok', outcome=outcome, pytest_exit=code, entry_values=driver.entries)


def _run_pytest(root, selector, driver):
    import pytest
    from .flow import _without_ordinary_observers
    for name in ('pytest_runtest_protocol', 'pytest_runtest_setup', 'pytest_runtest_call',
                 'pytest_runtest_teardown', 'pytest_runtest_makereport'):
        pytest.hookimpl(hookwrapper=True)(getattr(type(driver), name))
    pytest.hookimpl(tryfirst=True)(type(driver).pytest_configure)
    capture = io.StringIO()
    token = _ACTIVE.set(True)
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        with _without_ordinary_observers(), redirect_stdout(capture), redirect_stderr(capture):
            code = int(pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider', selector], plugins=[driver]))
    finally:
        os.chdir(previous_cwd)
        driver.close()
        _ACTIVE.reset(token)
    return code


def _anchor(data):
    from .anchors import Anchor, Issue, Parameter
    data = dict(data)
    data['parameters'] = tuple(Parameter(**v) for v in data.get('parameters', ()))
    data['issues'] = tuple(Issue(**v) for v in data.get('issues', ()))
    data['values'] = tuple(data.get('values', ()))
    return Anchor(**data)


def _worker(request_file, result_file):
    request = json.loads(Path(request_file).read_text(encoding='utf-8'))
    root = Path(request['root']).resolve()
    if request['operation'] == 'scenario':
        result = _scenario_stage(root, _binding(request['binding']), _decode(request['values']), request['stage'])
    elif request['operation'] == 'stage':
        result = _stage(root, _anchor(request['anchor']), _decode(request['values']), request['stage'])
    else:
        from .anchors import _execution_session, _observe_current
        observations = []
        with _execution_session(root):
            for data, values in request['requests']:
                anchor = _anchor(data)
                try:
                    observation = _observe_current(root, anchor, _decode(values))
                except Exception as error:
                    observation = _observation('red', anchor, reasons=['anchor execution failed: ' + type(error).__name__ + ': ' + str(error)])
                try:
                    value = _encode(observation.value)
                    observations.append(dict(status=observation.status, value=value, reasons=observation.reasons, anchor=observation.anchor))
                except (TypeError, ValueError) as error:
                    observations.append(dict(status='grey', value=_encode(None), reasons=[str(error)], anchor=anchor.target))
        result = observations
    Path(result_file).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


def _child(request):
    sdk = Path(__file__).resolve().parents[1]
    from .config import load_config
    cfg = load_config(request['root'])
    # Reuse the native plugin's source owner only when Python would import this
    # very SDK. A distinct project/package (including a src layout) must retain
    # its real "flowguard" name; never replace an old native SDK dependency.
    shadow = any((root / 'flowguard').is_dir() and (root / 'flowguard').resolve() != sdk
                 for root in [cfg.root, *cfg.roots])
    bootstrap = f"""import importlib.util, importlib.machinery, sys
from pathlib import Path
sdk = Path({str(sdk)!r})
normal = importlib.machinery.PathFinder.find_spec('flowguard')
loaded = sys.modules.get('flowguard')
same_loaded = loaded is None or Path(vars(loaded).get('__file__', '')).resolve() == sdk / '__init__.py'
name = 'flowguard' if {not shadow!r} and same_loaded and normal and normal.origin and Path(normal.origin).resolve() == sdk / '__init__.py' else '_flowguard_execution'
if name == '_flowguard_execution' or name not in sys.modules:
    spec = importlib.util.spec_from_file_location(name, sdk / '__init__.py', submodule_search_locations=[str(sdk)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
module = __import__(name + '.intent.calibration', fromlist=['_worker'])
module._worker(sys.argv[1], sys.argv[2])
"""
    env = os.environ.copy()
    for name in ('FLOWGUARD_TRACE_ROOT', 'FLOWGUARD_TRACE_CHILDREN', 'FLOWGUARD_TRACE_TEST', 'FLOWGUARD_IMPORT_ROOT'):
        env.pop(name, None)
    if env.get('PYTHONPATH'):
        env['PYTHONPATH'] = os.pathsep.join(p for p in env['PYTHONPATH'].split(os.pathsep)
            if not (Path(p).name == 'bootstrap' and Path(p).parent.name.startswith('flowguard-child-')))
    with tempfile.TemporaryDirectory(prefix='flowguard-observe-') as folder:
        source, target = Path(folder) / 'request.json', Path(folder) / 'result.json'
        source.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
        try:
            process = subprocess.run([sys.executable, '-B', '-c', bootstrap, str(source), str(target)],
                                     cwd=request['root'], env=env, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return dict(status='grey', reasons=['anchor verification exceeded 60 seconds'])
        if process.returncode or not target.is_file():
            return dict(status='grey', reasons=['isolated anchor execution did not complete'])
        return json.loads(target.read_text(encoding='utf-8'))


def _key(root, anchor):
    from ..map.common import content_digest
    file = anchor.calibrated_by.partition('::')[0]
    return (str(Path(root).resolve()), anchor.target, anchor.source_digest, anchor.calibrated_by,
            content_digest(Path(root) / file) if file and (Path(root) / file).is_file() else '')


def _namespace_issue(root, anchor):
    target_package = Path(root).resolve() / 'flowguard'
    if anchor.module.split('.')[0] == 'flowguard' and target_package.is_dir():
        from ..map.common import content_digest
        current = Path(__file__).resolve().parents[1]
        for rel in ('intent/calibration.py', 'intent/plugin.py'):
            old, new = target_package / rel, current / rel
            if not old.is_file() or content_digest(old) != content_digest(new):
                return 'calibrated historical FlowGuard plugin namespace is unsupported; pure source observation remains available'
    return ''


def _prepare(root, anchor, *, _reuse=True):
    if _ACTIVE.get():
        return dict(status='grey', reasons=['calibration cannot recursively prepare another test'])
    if anchor.issues:
        return dict(status=anchor.status, reasons=[issue.message for issue in anchor.issues])
    issue = _namespace_issue(root, anchor)
    if issue:
        return dict(status='grey', reasons=[issue])
    scope = _FACTS.get()
    key = _key(root, anchor)
    if _reuse and scope is not None and key in scope[1]:
        return scope[1][key]
    try:
        fn = sites.resolve_loaded(anchor.target)
    except (AttributeError, sites.NotMutable):
        fn = None
    if fn is not None and inspect.isfunction(sites.unwrap(fn)) and Path(sites.unwrap(fn).__code__.co_filename).resolve() == (Path(root) / anchor.file).resolve() and sites.installed_origin(fn) is not None:
        return dict(status='grey', reasons=['calibration must be verified before code instrumentation'])
    request = dict(operation='stage', root=str(Path(root).resolve()), anchor=asdict(anchor), values=_encode({}))
    baseline = _child(dict(request, stage='baseline'))
    if baseline.get('status') != 'ok':
        return baseline
    stopped = _child(dict(request, stage='zero'))
    if stopped.get('status') != 'ok':
        return stopped
    if outcome_key(_decode(baseline['outcome'])) != outcome_key(_decode(stopped['outcome'])):
        return dict(status='grey', reasons=['independent zero-replacement outcome differs from the complete original test'])
    fact = dict(status='ok', outcome=baseline['outcome'])
    if _reuse and scope is not None:
        scope[1][key] = fact
    return fact


def _observe_current(root, anchor, values):
    from .flow import _without_ordinary_observers
    if _ACTIVE.get():
        return _observation('grey', anchor, reasons=['a calibration test cannot recursively drive another calibration'])
    scope = _FACTS.get()
    fact = scope[1].get(_key(root, anchor)) if scope is not None else None
    if fact is None:
        return _observation('grey', anchor, reasons=['calibrated anchor must be prepared before current-code instrumentation'])
    try:
        fn = sites.unwrap(sites.resolve_loaded(anchor.target))
    except (AttributeError, sites.NotMutable) as error:
        return _observation('grey', anchor, reasons=[str(error)])
    with _without_ordinary_observers():
        result = _stage(root, anchor, values, 'case', expected_fn=fn)
    return _observation(result['status'], anchor, _decode(result['outcome']) if 'outcome' in result else None, result.get('reasons', ()))


def execute(root, anchor, values):
    return execute_many(root, [(anchor, values)])[0]


def execute_many(root, requests):
    requests = list(requests)
    output = [None] * len(requests)
    pure = []
    with _execution_session(root):
        for index, (anchor, values) in enumerate(requests):
            if anchor.issues:
                output[index] = _observation(anchor.status, anchor, reasons=[i.message for i in anchor.issues])
            elif anchor.calibrated_by:
                try:
                    fact = _prepare(root, anchor, _reuse=False)
                    result = (_child(dict(operation='stage', root=str(Path(root).resolve()), anchor=asdict(anchor),
                                          values=_encode(values), stage='case')) if fact['status'] == 'ok' else fact)
                    output[index] = _observation(result['status'], anchor, _decode(result['outcome']) if 'outcome' in result else None, result.get('reasons', ()))
                except (TypeError, ValueError) as error:
                    output[index] = _observation('grey', anchor, reasons=[str(error)])
            else:
                pure.append((index, anchor, values))
        if pure:
            try:
                result = _child(dict(operation='pure', root=str(Path(root).resolve()),
                                     requests=[[asdict(anchor), _encode(values)] for _, anchor, values in pure]))
                for position, (index, anchor, _) in enumerate(pure):
                    row = result[position] if isinstance(result, list) else result
                    output[index] = _observation(row['status'], anchor, _decode(row['value']) if 'value' in row else None, row.get('reasons', ()))
            except (TypeError, ValueError) as error:
                for index, anchor, _ in pure:
                    output[index] = _observation('grey', anchor, reasons=[str(error)])
    return output


# A scenario is an ordinary test event, not a user-supplied result adapter.
def _rule_id(binding):
    rule = getattr(binding, 'observed_rule', getattr(binding, 'rule', ''))
    return getattr(rule, 'id', rule)


def _read_data(read):
    if read is None:
        return None
    from .flow import _UNSET
    data = dict(node=read.node, field=read.field, occurrence=read.occurrence, view=read.view)
    if read.equals is not _UNSET:
        data['equals'] = _encode(read.equals)
    return data


def _binding_data(binding):
    model = binding.flow
    index = binding.anchor_index
    nodes = [dict(name=n.name, anchor=n.anchor, phase=n.phase, occurrence=n.occurrence,
                  start=n.start, end=n.end, model=getattr(n.model, 'id', n.model), caller=n.caller)
             for n in model.nodes]
    relations = [dict(rule=getattr(r.rule, 'id', r.rule), inputs={k: _read_data(v) for k, v in r.inputs.items()},
                      actual=_read_data(r.actual), on=r.on) for r in model.relations]
    result = dict(flow=dict(id=model.id, source=model.source, nodes=nodes, edges=model.edges, relations=relations,
                          file=model.file, line=model.line),
                scenario=asdict(binding.scenario), anchor=asdict(binding.anchor),
                entries=[asdict(a) for a in index.entries], field_map=dict(binding.field_map),
                testnode=binding.testnode, rule=_rule_id(binding),
                relation_indices=list(getattr(binding, 'relation_indices', range(len(relations)))),
                actual_targets=list(binding.actual_targets), targets=list(binding.targets))
    if hasattr(binding, 'requested_inputs'):
        result['requested_inputs'] = _encode(binding.requested_inputs)
    return result


def _binding(data):
    from types import SimpleNamespace
    from .anchors import Index
    from .flow import Flow, Node, Read, Relation
    def read(value):
        if value is None:
            return None
        value = dict(value)
        if 'equals' in value:
            value['equals'] = _decode(value['equals'])
        return Read(**value)
    model = dict(data['flow'])
    model['nodes'] = tuple(Node(**n) for n in model['nodes'])
    model['relations'] = tuple(Relation(r['rule'], {k: read(v) for k, v in r['inputs'].items()},
                                         read(r['actual']), r['on']) for r in model['relations'])
    result = SimpleNamespace(flow=Flow(**model), scenario=_anchor(data['scenario']), anchor=_anchor(data['anchor']),
                           anchor_index=Index(tuple(_anchor(a) for a in data['entries'])),
                           field_map=data['field_map'], testnode=data['testnode'], observed_rule=data['rule'],
                           relation_indices=tuple(data['relation_indices']), actual_targets=tuple(data['actual_targets']),
                           targets=tuple(data['targets']))
    if 'requested_inputs' in data:
        result.requested_inputs = _decode(data['requested_inputs'])
    return result


def _installed_codes(binding):
    targets = set(binding.targets) | set(binding.actual_targets)
    result = []
    for target in sorted(targets):
        try:
            fn = sites.unwrap(sites.resolve_loaded(target))
            origin = sites.installed_origin(fn)
        except (AttributeError, sites.NotMutable):
            continue
        if origin is not None and inspect.isfunction(fn):
            result.append((fn, origin, fn.__code__))
    return tuple(result)


def _verifier_codes(binding):
    sdk = Path(__file__).resolve().parents[1]
    return tuple(row for row in _installed_codes(binding)
                 if Path(row[1].co_filename).resolve().is_relative_to(sdk))


@contextmanager
def _code_scope(codes, *, actual):
    previous = [(fn, fn.__code__) for fn, _, _ in codes]
    try:
        for fn, origin, installed in codes:
            fn.__code__ = installed if actual else origin
        yield codes
    finally:
        for fn, code in reversed(previous):
            fn.__code__ = code


class _ScenarioDriver(_Driver):
    def __init__(self, root, binding, values, stage, verifier_codes=()):
        self.verifier_codes = verifier_codes
        super().__init__(root, binding.scenario, values, stage)
        from .flow import Capture
        self.binding = binding
        self.capture = Capture(root, binding.anchor_index, binding.testnode)
        self.item = None
        self.ignored = set()
        self.errors = []

    def _install(self):
        if self.ready or self.stack is None or self.item is None:
            return
        fn = sites.unwrap(self.item.obj)
        expected = (Path(self.root) / self.anchor.file).resolve()
        if (not inspect.isfunction(fn) or Path(fn.__code__.co_filename).resolve() != expected
                or fn.__qualname__.replace('.<locals>.', '.') != self.anchor.qual):
            self.problems.append('selected pytest function is not the declared scenario event')
            return
        if fn.__code__.co_freevars or inspect.iscoroutinefunction(fn) or inspect.isgeneratorfunction(fn):
            self.problems.append('scenario closure/async/generator is unsupported')
            return
        from .flow import _TraceUnavailable
        try:
            self.stack.enter_context(self._observing(self.capture.on_trace, ignored=self.ignored))
            if self.stage != 'baseline':
                self.stack.enter_context(sites.intercepted(fn, self._call))
                self.ignored.add(fn.__code__)
        except (sites.NotMutable, _TraceUnavailable) as error:
            self.problems.append(str(error))
            return
        self.ready = True

    def _call(self, original, bound):
        __tracebackhide__ = lambda info: info.errisinstance(_Stop)
        if self.running:
            raise _Unsupported('recursive scenario entry is ambiguous')
        unknown = set(self.values) - {p.name for p in self.anchor.parameters}
        if unknown:
            raise _Unsupported('scenario values name undeclared parameters: ' + ', '.join(sorted(unknown)))
        if self.stage == 'case':
            for name, value in self.values.items():
                bound.arguments[name] = self._value_in_context(value, bound.arguments.get(name), function=original, parameter=name)
        self.running = True
        try:
            with _code_scope(self.verifier_codes, actual=True):
                original(*bound.args, **bound.kwargs)  # All original body assertions run.
        finally:
            self.running = False
        raise _Stop('scenario body completed; test return is not the measured outcome')

    def pytest_runtest_protocol(self, item):
        self.item = item
        yield from super().pytest_runtest_protocol(item)

    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        error = call.excinfo.value if call.excinfo is not None else None
        if isinstance(error, _Unsupported):
            self.problems.append(str(error))
        self.reports.append((report.when, report.outcome, isinstance(error, _Stop)))
        if error is not None and not isinstance(error, _Stop):
            self.errors.append((report.when, error))


def _scenario_stage(root, binding, values, stage):
    # A verifier's own installed mutant belongs in the native case, not in
    # collection/model loading that must first reach that case. Keep its real
    # function object and current code; never reload pristine target source.
    with _code_scope(_verifier_codes(binding), actual=False) as codes:
        return _scenario_stage_with_codes(root, binding, values, stage, codes)


def _scenario_stage_with_codes(root, binding, values, stage, codes):
    from .anchors import _source
    from .config import load_config, setup_path
    from .imports import prepare
    from .flow import relation_observations
    try:
        _source(root, binding.scenario)
        if binding.scenario.kind != 'event' or binding.scenario.source_role != 'test':
            return dict(status='red', reasons=['scenario must reference a real ordinary-test event'])
        from .anchors import _accepts
        if set(values) - {p.name for p in binding.scenario.parameters}:
            return dict(status='red', reasons=['scenario values name undeclared parameters'])
        for parameter in binding.scenario.parameters:
            if parameter.name in values:
                try:
                    accepted = _accepts(parameter.source_type, values[parameter.name])
                except (ValueError, SyntaxError, TypeError, AttributeError):
                    continue  # actual native Enum/fixture identity is checked at call time
                if not accepted:
                    return dict(status='red', reasons=[parameter.name + ': scenario input does not have its source parameter type'])
        cfg = load_config(root)
        setup_path(cfg)
        prepare(root)
        file, separator, _ = binding.testnode.partition('::')
        path = (Path(root) / file).resolve()
        if not separator or not path.is_relative_to(Path(root).resolve()) or not path.is_file():
            return dict(status='grey', reasons=['scenario needs an existing exact testnode'])
        driver = _ScenarioDriver(root, binding, values, stage, codes)
        try:
            code = _run_pytest(root, binding.testnode, driver)
        finally:
            driver.capture.close()
        if driver.problems:
            return dict(status='grey', reasons=driver.problems)
        if driver.selected != 1:
            return dict(status='grey', reasons=['scenario must select exactly one pytest case'])
        failed = [(phase, status, stop) for phase, status, stop in driver.reports if status != 'passed']
        if stage == 'baseline' and (code or failed):
            return dict(status='red', reasons=['original scenario test did not pass completely'])
        if any(phase == 'teardown' and status != 'passed' for phase, status, _ in failed):
            return dict(status='red', reasons=['scenario teardown failed'])
        projection = relation_observations(binding.flow, driver.capture, binding.anchor_index, _rule_id(binding))
        observations = [r for r in projection['observations'] if r['relation_index'] in binding.relation_indices]
        if projection['status'] != 'observed' or len(observations) != 1:
            return dict(status='grey', reasons=projection['grey'] or ['scenario has ambiguous actual reading scopes'])
        observed = observations[0]
        source = observed['sources'].get('$actual', {})
        if source.get('site') not in binding.actual_targets:
            return dict(status='grey', reasons=['actual reading does not come from a declared production anchor'])
        if stage == 'case':
            requested = getattr(binding, 'requested_inputs', {field: values[parameter] for field, parameter in binding.field_map.items() if parameter in values})
            for field, value in requested.items():
                if field not in observed['inputs'] or not outcome_equal(observed['inputs'][field], value):
                    return dict(status='grey', reasons=['actual scenario input did not match ' + field])
        actual = observed['actual']
        native_failures = [(phase, error) for phase, error in driver.errors if not isinstance(error, _Unsupported)]
        genuine_refusal = (isinstance(actual, Raised) and len(native_failures) == 1
                           and native_failures[0][0] == 'call' and native_failures[0][1] is actual.error)
        if stage != 'baseline':
            stopped = any(stop for _, _, stop in failed)
            if not stopped and not genuine_refusal:
                return dict(status='red' if failed else 'grey', reasons=['scenario did not finish its body or expose the declared native refusal'])
            if any(not stop for _, _, stop in failed) and not genuine_refusal:
                return dict(status='red', reasons=['scenario test failed outside its actual production reading'])
        return dict(status='ok', outcome=_encode(actual), inputs=_encode(observed['inputs']),
                    sources=observed['sources'], pytest_exit=code)
    except Exception as error:
        return dict(status='grey', reasons=['scenario verification failed: ' + type(error).__name__ + ': ' + str(error)])


def _scenario_key(root, binding):
    data = _binding_data(binding)
    data.pop('requested_inputs', None)
    from ..map.common import content_digest
    test = Path(root) / binding.testnode.partition('::')[0]
    return ('scenario', str(Path(root).resolve()), json.dumps(data, sort_keys=True),
            content_digest(test) if test.is_file() else '')


def _prepare_scenario(root, binding):
    if _ACTIVE.get():
        return dict(status='grey', reasons=['a calibration probe cannot prepare another scenario'])
    try:
        key = _scenario_key(root, binding)
        scope = _FACTS.get()
        if scope is not None and key in scope[1]:
            return scope[1][key]
        issue = _namespace_issue(root, binding.anchor)
        if issue:
            return dict(status='grey', reasons=[issue])
        if _installed_codes(binding):
            return dict(status='grey', reasons=['scenario must be calibrated before code instrumentation'])
        request = dict(operation='scenario', root=str(Path(root).resolve()), binding=_binding_data(binding), values=_encode({}))
        baseline = _child(dict(request, stage='baseline'))
        if baseline.get('status') != 'ok':
            return baseline
        zero = _child(dict(request, stage='zero'))
        if zero.get('status') != 'ok':
            return zero
        if (outcome_key(_decode(baseline['outcome'])) != outcome_key(_decode(zero['outcome']))
                or outcome_key(_decode(baseline['inputs'])) != outcome_key(_decode(zero['inputs']))):
            return dict(status='grey', reasons=['independent zero-replacement scenario readings differ from the complete original test'])
        fact = dict(status='ok')
        if scope is not None:
            scope[1][key] = fact
        return fact
    except Exception as error:
        return dict(status='grey', reasons=['scenario preparation failed: ' + type(error).__name__ + ': ' + str(error)])


def _scene_observation(binding, result):
    from .anchors import Observation
    return Observation(result['status'], _decode(result['outcome']) if 'outcome' in result else None,
                       tuple(result.get('reasons', ())), binding.anchor.target)


def execute_scenario(root, binding, values):
    try:
        with _execution_session(root):
            fact = _prepare_scenario(root, binding)
            result = (_child(dict(operation='scenario', root=str(Path(root).resolve()), binding=_binding_data(binding),
                                  values=_encode(values), stage='case')) if fact['status'] == 'ok' else fact)
        return _scene_observation(binding, result)
    except Exception as error:
        return _scene_observation(binding, dict(status='grey', reasons=['scenario execution failed: ' + type(error).__name__ + ': ' + str(error)]))


def _observe_scenario_current(root, binding, values):
    from .flow import _without_ordinary_observers
    if _ACTIVE.get():
        return _scene_observation(binding, dict(status='grey', reasons=['recursive scenario calibration is unsupported']))
    try:
        scope = _FACTS.get()
        if scope is None or _scenario_key(root, binding) not in scope[1]:
            return _scene_observation(binding, dict(status='grey', reasons=['scenario must be prepared before current-code instrumentation']))
        with _without_ordinary_observers():
            return _scene_observation(binding, _scenario_stage(root, binding, values, 'case'))
    except Exception as error:
        return _scene_observation(binding, dict(status='grey', reasons=['current scenario failed: ' + type(error).__name__ + ': ' + str(error)]))
