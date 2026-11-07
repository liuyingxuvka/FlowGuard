"""Real imports must execute changed bytes even when timestamp and size collide."""
import importlib.util
import os
from pathlib import Path
import py_compile
import subprocess
import sys

import pytest


SDK = str(Path(__file__).resolve().parents[2])


def collision(path, before, after):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(before)
    py_compile.compile(str(path), doraise=True)
    stamp = path.stat()
    assert len(before.encode()) == len(after.encode())
    path.write_text(after)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    cached = Path(importlib.util.cache_from_source(str(path)))
    assert cached.read_bytes()[4:8] == b'\0\0\0\0'
    return cached


def python(root, body, *args):
    setup = 'import sys;sys.path.insert(0,sys.argv.pop(1));'
    return subprocess.run([sys.executable, '-c', setup + body, SDK, *map(str, args)],
                          cwd=root, capture_output=True, text=True)


def test_content_cache_replaces_old_timestamp_once_and_reuses_unchanged_code(tmp_path):
    cached = collision(tmp_path / 'owned.py', 'VALUE = 3\n', 'VALUE = 4\n')
    result = python(tmp_path, '''
from flowguard.intent.imports import prepare, _Source
prepare('.')
compiled = []
previous = _Source.source_to_code
def compile_source(self, *args, **kwargs):
    compiled.append(self.path)
    return previous(self, *args, **kwargs)
_Source.source_to_code = compile_source
import owned
assert owned.VALUE == 4
first = owned
prepare('.')
assert __import__('owned') is first
sys.modules.pop('owned')
import owned
assert owned.VALUE == 4
assert len(compiled) == 1, compiled
''')
    assert result.returncode == 0, result.stdout + result.stderr
    assert cached.read_bytes()[4:8] == b'\x03\0\0\0'


@pytest.mark.parametrize('placement', ['outside', 'environment'])
def test_dependency_caches_keep_their_own_loader(tmp_path, placement):
    project = tmp_path / 'project'
    project.mkdir()
    library = tmp_path / 'library' if placement == 'outside' else project / '.venv/lib/site-packages'
    if placement == 'environment':
        library.mkdir(parents=True)
        (project / '.venv/pyvenv.cfg').write_text('home = external\n')
    cached = collision(library / 'dependency.py', 'VALUE = 3\n', 'VALUE = 4\n')
    original = cached.read_bytes()
    result = python(project, '''
from flowguard.intent.imports import prepare
prepare('.')
sys.path.insert(0, sys.argv[1])
import dependency
# This is deliberately the external interpreter's timestamp cache: FlowGuard
# must not silently change the dependency installation or its loader.
assert dependency.VALUE == 3
''', library)
    assert result.returncode == 0, result.stdout + result.stderr
    assert cached.read_bytes() == original


def test_prepare_refreshes_imported_aliases_after_changed_bytes(tmp_path):
    (tmp_path / 'owned.py').write_text('def value(): return 3\n')
    (tmp_path / 'consumer.py').write_text('from owned import value\ndef answer(): return value()\n')
    result = python(tmp_path, '''
import errno, os
from pathlib import Path
from flowguard.intent.imports import prepare
prepare('.')
import consumer
assert consumer.answer() == 3
original = consumer
source = Path('owned.py')
stamp = source.stat()
source.write_text('def value(): return 4\\n')
os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
prepare('.')
import consumer
assert consumer is not original
assert consumer.answer() == 4
assert __import__('errno') is errno
again = consumer
prepare('.')
assert __import__('consumer') is again
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_plain_pytest_rewrites_changed_assertions_instead_of_reusing_timestamp_cache(tmp_path):
    (tmp_path / 'test_actual.py').write_text('def test_actual(): assert 3 == 3\n')
    command = "import pytest;raise SystemExit(pytest.main(['-q','-p','flowguard.intent.plugin']))"
    first = python(tmp_path, command)
    assert first.returncode == 0, first.stdout + first.stderr
    source = tmp_path / 'test_actual.py'
    stamp = source.stat()
    source.write_text('def test_actual(): assert 4 == 3\n')
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    second = python(tmp_path, command)
    assert second.returncode == 1, second.stdout + second.stderr
    assert 'assert 4 == 3' in second.stdout


def test_unmarked_pytest_child_imports_fresh_child_only_code(tmp_path):
    collision(tmp_path / 'child_only.py', 'VALUE = 3\n', 'VALUE = 4\n')
    (tmp_path / 'test_actual.py').write_text('''import subprocess, sys
def test_actual():
    subprocess.run([sys.executable, '-c', 'import child_only; assert child_only.VALUE == 4'], check=True)
''')
    result = python(tmp_path, "import pytest;raise SystemExit(pytest.main(['-q','-p','flowguard.intent.plugin']))")
    assert result.returncode == 0, result.stdout + result.stderr


def test_library_load_refuses_unknown_preloaded_project_objects_without_reloading_them(tmp_path):
    (tmp_path / 'owned.py').write_text('VALUE = 3\n')
    result = python(tmp_path, '''
import os
from pathlib import Path
import owned
old = owned
source = Path('owned.py')
stamp = source.stat()
source.write_text('VALUE = 4\\n')
os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
assert owned.VALUE == 3 and '4' in source.read_text()
from flowguard.intent.loader import load
from flowguard.intent.config import load_config
try:
    load(load_config('.'))
except ValueError as error:
    assert 'imported before source verification' in str(error)
    assert 'fresh verification process' in str(error)
else:
    raise AssertionError('an unverified preloaded object must not become a successful check')
assert sys.modules['owned'] is old and old.VALUE == 3
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_switching_projects_does_not_reuse_a_same_named_helper(tmp_path):
    for name, value in [('first', 3), ('second', 4)]:
        root = tmp_path / name
        root.mkdir()
        (root / 'shared.py').write_text(f'VALUE = {value}\n')
    result = python(tmp_path, '''
from flowguard.intent.imports import prepare
from flowguard.intent.config import load_config, setup_path
first, second = load_config('first'), load_config('second')
setup_path(first); prepare(first.root)
import shared
assert shared.VALUE == 3
old = shared
setup_path(second)
assert __import__('shared') is old  # Python's name cache alone ignores the new path.
prepare(second.root)
import shared
assert shared.VALUE == 4 and shared is not old
setup_path(first); prepare(first.root)
import shared
assert shared.VALUE == 3 and shared is not old
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_setup_path_preserves_explicit_pytest_path_precedence_when_reentered(tmp_path):
    for folder, value in [('src', 3), ('preferred', 4)]:
        path = tmp_path / folder
        path.mkdir()
        (path / 'shared.py').write_text(f'VALUE = {value}\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["preferred", "src"]\n')
    result = python(tmp_path, '''
from flowguard.intent.imports import prepare
from flowguard.intent.config import load_config, setup_path
cfg = load_config('.')
setup_path(cfg); prepare(cfg.root)
import shared
assert shared.VALUE == 4
position = list(sys.path)
setup_path(cfg)
assert sys.path == position
''')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('preinstalled', [False, True])
def test_init_plain_pytest_guards_imports_before_project_conftest(tmp_path, preinstalled):
    from flowguard.intent.cli import init
    from flowguard.intent.config import load_config
    (tmp_path / 'owned.py').write_text('VALUE = 3\n')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/conftest.py').write_text('''import pytest
from owned import VALUE
@pytest.fixture
def supplied(): return VALUE
''')
    (tmp_path / 'tests/test_actual.py').write_text('def test_actual(supplied): assert supplied == 3\n')
    init(load_config(tmp_path))
    ordinary = "import pytest;raise SystemExit(pytest.main(['-q']))"
    if preinstalled:
        ordinary = "from flowguard.intent.imports import prepare;prepare('.');" + ordinary
    first = python(tmp_path, ordinary)
    assert first.returncode == 0, first.stdout + first.stderr
    source = tmp_path / 'owned.py'
    stamp = source.stat()
    source.write_text('VALUE = 4\n')
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    second = python(tmp_path, ordinary)
    assert second.returncode == 1, second.stdout + second.stderr
    assert 'assert 4 == 3' in second.stdout
    assert 'imported before source verification' not in second.stdout + second.stderr


def test_pytest_host_source_identity_survives_temporary_project_models(tmp_path):
    for name in ('host', 'temporary'):
        root = tmp_path / name
        (root / 'tests/intent').mkdir(parents=True)
        (root / 'tests/intent/policy.py').write_text('''from flowguard.intent import rule
@rule('LIMIT', decides='flag', fields={'flag': bool}, source='assumed: fixture boundary')
def LIMIT(flag): return flag
''')
    result = python(tmp_path, '''
from flowguard.intent.imports import prepare, release_host
from flowguard.intent.config import load_config
from flowguard.intent.loader import load
host, temporary = load_config('host'), load_config('temporary')
prepare(host.root, host=True)
first = load(host)
name = first.rules['LIMIT'].pred.__module__
module = sys.modules[name]
second = load(temporary)
assert second.rules['LIMIT'].pred.__module__ != name
assert sys.modules[name] is module
prepare(host.root, host=True)
assert sys.modules[name] is module
assert first.rules['LIMIT'].eval({'flag': True}) is True
release_host(host.root)
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_temporary_project_cannot_shadow_a_live_pytest_host_module(tmp_path):
    for name, value in [('host', 3), ('temporary', 4)]:
        root = tmp_path / name
        root.mkdir()
        (root / 'shared.py').write_text(f'VALUE = {value}\n')
    result = python(tmp_path, '''
from flowguard.intent.imports import prepare
from flowguard.intent.config import load_config, setup_path
host, temporary = load_config('host'), load_config('temporary')
setup_path(host); prepare(host.root, host=True)
import shared
original = shared
setup_path(temporary)
try:
    prepare(temporary.root)
except ValueError as error:
    assert 'conflicts with the active pytest verifier' in str(error)
    assert 'fresh verification process' in str(error)
else:
    raise AssertionError('a temporary target cannot borrow a same-named host module')
assert sys.modules['shared'] is original and original.VALUE == 3
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_changed_project_inspection_is_fresh_without_clearing_external_linecache(tmp_path):
    (tmp_path / 'app.py').write_text('def f(): return 3\n')
    result = python(tmp_path, '''
import os, inspect, linecache
from pathlib import Path
from flowguard.intent.imports import prepare
prepare('.')
import app
assert 'return 3' in inspect.getsource(app.f)
external = ('external', None, ['keep this external cache\\n'], 'external')
linecache.cache['external-dependency.py'] = external
source = Path('app.py'); stamp = source.stat()
source.write_text('def f(): return 4\\n')
os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
prepare('.')
import app
assert app.f() == 4
assert 'return 4' in inspect.getsource(app.f)
assert linecache.cache['external-dependency.py'] is external
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_host_import_prefixes_are_resolved_once_per_fresh_prepare(tmp_path):
    for name in ('host', 'temporary'):
        (tmp_path/name).mkdir()
    package = tmp_path/'host/prefix_cohort'
    package.mkdir()
    (package/'__init__.py').write_text('')
    for name in ('one', 'two'):
        (package/(name+'.py')).write_text('VALUE = 3\n')
    result = python(tmp_path, '''
from pathlib import Path
from importlib import invalidate_caches, machinery
from flowguard.intent.imports import prepare
from flowguard.intent.config import load_config, setup_path
host, temporary = load_config('host'), load_config('temporary')
setup_path(host); prepare(host.root, host=True)
import prefix_cohort.one, prefix_cohort.two
original = sys.modules['prefix_cohort.one']
setup_path(temporary)
sys.path.append(str(host.root))  # The live verifier remains importable after the target.
find = machinery.PathFinder.find_spec
calls = []
def counted(name, path=None, target=None):
    calls.append(name)
    return find(name, path, target)
machinery.PathFinder.find_spec = counted
prepare(temporary.root)
assert calls.count('prefix_cohort') == 1, calls
assert calls.count('prefix_cohort.one') == 1, calls
assert calls.count('prefix_cohort.two') == 1, calls
# A new prepare is a new source snapshot, including changed package precedence.
shadow = temporary.root / 'prefix_cohort'
shadow.mkdir()
(shadow/'__init__.py').write_text('')
(shadow/'one.py').write_text('VALUE = 4\\n')
invalidate_caches()
calls.clear()
try:
    prepare(temporary.root)
except ValueError as error:
    assert 'conflicts with the active pytest verifier' in str(error)
else:
    raise AssertionError('a per-prepare prefix cache must not preserve the old origin')
assert calls.count('prefix_cohort') == 1, calls
assert sys.modules['prefix_cohort.one'] is original and original.VALUE == 3
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_local_import_prefix_memo_keeps_namespace_and_missing_parents(tmp_path):
    for folder, module in [('first', 'left'), ('second', 'right')]:
        package = tmp_path/folder/'prefix_namespace'
        package.mkdir(parents=True)
        (package/(module+'.py')).write_text('VALUE = 3\n')
    result = python(tmp_path, '''
from pathlib import Path
from importlib import machinery
from flowguard.intent.imports import _find
sys.path[:0] = [str(Path('first').resolve()), str(Path('second').resolve())]
find = machinery.PathFinder.find_spec
calls = []
def counted(name, path=None, target=None):
    calls.append(name)
    return find(name, path, target)
machinery.PathFinder.find_spec = counted
specs = {}
left = _find('prefix_namespace.left', specs)
right = _find('prefix_namespace.right', specs)
assert specs['prefix_namespace'].origin is None
assert Path(left.origin) == Path('first/prefix_namespace/left.py').resolve()
assert Path(right.origin) == Path('second/prefix_namespace/right.py').resolve()
assert calls.count('prefix_namespace') == 1, calls
assert _find('absent_prefix_72958.one', specs) is None
assert _find('absent_prefix_72958.two', specs) is None
assert calls.count('absent_prefix_72958') == 1, calls
assert 'absent_prefix_72958.one' not in calls and 'absent_prefix_72958.two' not in calls
assert not any(name.startswith('prefix_namespace') for name in sys.modules)
''')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def flat_import_roots(tmp_path):
    for folder in ('host', 'temporary'):
        (tmp_path / folder).mkdir()
    (tmp_path / 'host/verifier_flat_17.py').write_text('VALUE = 3\n')
    return tmp_path


_FLAT_IMPORT_HOST = '''
from importlib import machinery, util
from pathlib import Path
from flowguard.intent.imports import prepare
host, target = Path('host').resolve(), Path('temporary').resolve()
sys.path.insert(0, str(host)); prepare(host, host=True)
import verifier_flat_17
sys.path[:0] = [str(target), str(host)]
machinery.PathFinder.find_spec('absent_verifier_warmup_17', [str(target)])
'''


def test_flat_host_lookup_leaves_late_hooks_alone_and_finds_new_shadow(flat_import_roots):
    result = python(flat_import_roots, _FLAT_IMPORT_HOST + '''
import os
late = str(Path('late_uncached').resolve())
sys.path.insert(2, late)
calls = []
def hook(entry):
    if entry == late:
        calls.append(entry)
        raise RuntimeError('a later hook must remain unreachable')
    raise ImportError
sys.path_hooks.insert(0, hook)
find, lookups = machinery.PathFinder.find_spec, []
def counted(name, path=None, target=None):
    lookups.append(name)
    return find(name, path, target)
machinery.PathFinder.find_spec = counted
prepare(target)
assert 'verifier_flat_17' not in lookups
stamp = target.stat()
(target / 'verifier_flat_17.py').write_text('VALUE = 4\\n')
os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
try:
    prepare(target)
except ValueError as error:
    assert 'conflicts with the active pytest verifier' in str(error)
else:
    raise AssertionError('new same-named source must be rejected on the next prepare')
assert calls == [] and verifier_flat_17.VALUE == 3
''')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('namespace', [True, False], ids=['namespace-provider', 'early-unknown'])
def test_origin_lookup_reaches_source_after_namespace_or_early_unknown(flat_import_roots, namespace):
    result = python(flat_import_roots, _FLAT_IMPORT_HOST + '''
use_namespace = sys.argv[1] == 'True'
if use_namespace:
    (host / 'verifier_flat_17.py').unlink()
    (host / 'verifier_flat_17').mkdir()
    finder = sys.path_importer_cache[str(host)]
    finder.invalidate_caches()
    spec = finder.find_spec('verifier_flat_17')
    assert spec is not None and spec.loader is None and spec.origin is None
(target / 'actual.py').write_text('VALUE = 4\\n')
late = str(Path('late_virtual').resolve())
class Virtual:
    def find_spec(self, name, target=None):
        if name == 'verifier_flat_17':
            return util.spec_from_file_location(name, Path('temporary/actual.py').resolve())
        return None
sys.path_importer_cache[late] = Virtual()
sys.path.insert(2 if use_namespace else 1, late)
try:
    prepare(target)
except ValueError as error:
    assert 'conflicts with the active pytest verifier' in str(error)
else:
    raise AssertionError('namespace or unknown finder must not hide real source')
''', namespace)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('mode', ['find_spec', '_get_spec', '_fill_cache', 'loader'])
def test_unknown_host_finder_behavior_keeps_full_origin_lookup(flat_import_roots, mode):
    result = python(flat_import_roots, _FLAT_IMPORT_HOST + '''
mode = sys.argv[1]
find = machinery.PathFinder.find_spec
calls, comparisons = [], []
def counted(name, path=None, target=None):
    calls.append(name)
    return find(name, path, target)
machinery.PathFinder.find_spec = counted
prepare(target)
assert 'verifier_flat_17' not in calls  # The known prefix really is eligible.
finder = sys.path_importer_cache[str(host)]
if mode == 'loader':
    class EqualMeta(type):
        def __eq__(cls, other):
            comparisons.append(other)
            return True
    class UnknownLoader(metaclass=EqualMeta):
        pass
    finder._loaders.append(('.unused17', UnknownLoader))
else:
    delegate = getattr(finder, mode)
    setattr(finder, mode, lambda *args, **kwargs: delegate(*args, **kwargs))
finder.invalidate_caches()
calls.clear()
prepare(target)
assert calls.count('verifier_flat_17') == 1, calls
assert comparisons == []
''', mode)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(os.name != 'nt', reason='Windows FileFinder normalizes suffix case')
@pytest.mark.parametrize('suffix', ['.PY', '.PYC'])
def test_windows_uppercase_suffix_cannot_hide_a_host_shadow(flat_import_roots, suffix):
    result = python(flat_import_roots, _FLAT_IMPORT_HOST + '''
(target / ('verifier_flat_17' + sys.argv[1])).write_bytes(b'not executed')
sys.path_importer_cache[str(target)].invalidate_caches()
try:
    prepare(target)
except ValueError as error:
    assert 'conflicts with the active pytest verifier' in str(error)
else:
    raise AssertionError('Windows same-named source must not be screened out')
''', suffix)
    assert result.returncode == 0, result.stdout + result.stderr
