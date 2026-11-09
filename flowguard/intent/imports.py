"""Content-checked imports for the project's verification process.

Only imported project files are touched. Python's normal checked-hash bytecode
format is reused; dependency packages and the interpreter keep their own loaders.
"""
from __future__ import annotations

from contextlib import contextmanager

import importlib
from importlib import _bootstrap_external, machinery, util
import linecache
import os
from pathlib import Path
import sys

from ..structure.paths import project_code

_SDK = Path(__file__).resolve().parent.parent


def _remember(name, path, fingerprint):
    path = Path(path).resolve()
    owner = _finder.root if _finder.root is not None and _finder.project(str(path), _finder.root) else _finder.host
    _finder.loaded[name] = (path, fingerprint, sys.modules.get(name), owner)


def _notify(module):
    filename = getattr(module, '__file__', None)
    if filename:
        for root, callback in tuple(_finder.observers):
            if _finder.project(filename, root):
                callback(module)


@contextmanager
def observe_imports(root, callback):
    """Notify after the same verified loader completes; never bypass its checks."""
    observer = (Path(root).resolve(), callback)
    _finder.observers.append(observer)
    try:
        for path, digest, module, owner in tuple(_finder.loaded.values()):
            if module is not None and _finder.project(str(path), observer[0]):
                callback(module)
        yield
    finally:
        _finder.observers.remove(observer)


class _Source(machinery.SourceFileLoader):
    def exec_module(self, module):
        super().exec_module(module)
        _notify(module)

    def get_code(self, fullname):
        source = self.get_data(self.path)
        fingerprint = util.source_hash(source)
        cached = util.cache_from_source(self.path)
        try:
            header = self.get_data(cached)[:16]
        except OSError:
            header = b''
        previous = _finder.loaded.get(fullname)
        if previous is not None and previous[0] == Path(self.path).resolve() and previous[1] != fingerprint:
            linecache.cache.pop(self.path, None)
        _remember(fullname, self.path, fingerprint)
        if header[:4] == util.MAGIC_NUMBER and header[4:8] == b'\x03\0\0\0' and header[8:] == fingerprint:
            return super().get_code(fullname)
        code = self.source_to_code(source, self.path)
        if not sys.dont_write_bytecode:
            self.set_data(cached, _bootstrap_external._code_to_hash_pyc(code, fingerprint, checked=True))
        return code


class _Rewritten:
    def __init__(self, delegate):
        self.delegate = delegate

    def create_module(self, spec):
        return self.delegate.create_module(spec)

    def exec_module(self, module):
        # Pytest's rewritten cache also uses timestamp+size. Rebuild only this
        # actually selected module, preserving pytest's own assertion rewriting.
        from _pytest.assertion.rewrite import PYC_TAIL, get_cache_dir
        source = Path(module.__spec__.origin)
        cache = get_cache_dir(source) / (source.name[:-3] + PYC_TAIL)
        cache.unlink(missing_ok=True)
        _remember(module.__name__, source, util.source_hash(source.read_bytes()))
        self.delegate.exec_module(module)
        _notify(module)


class _Finder:
    def __init__(self):
        self.root = self.host = None
        self.active = False
        self.loaded = {}
        self.observers = []
        # Modules already classified by prepare() for (root, host): name -> (module id, file).
        self.verified, self.verified_for = {}, None
        self.applications = {}
        self.projects = {}

    def project(self, filename, root):
        """project_code(filename, root) for the observers, decided once per process: the source tree is fixed
        for the session (project_code's callers cache it), and every test's observation asks again."""
        key = (filename, root)
        if key not in self.projects:
            self.projects[key] = project_code(filename, root)
        return self.projects[key]

    def owns(self, filename):
        roots = (self.root,) if self.root == self.host else (self.root, self.host)
        return any(root is not None and project_code(filename, root) for root in roots)

    def application(self, path, root):
        # project_code is fixed for a file within one process (see its docstring);
        # prepare() asks this for every loaded project module on each call.
        key = (path, root)
        if key not in self.applications:
            if isinstance(path, Path) and path.is_relative_to(_SDK):
                self.applications[key] = False
            else:
                self.applications[key] = project_code(str(path), root) and not path.is_relative_to(_SDK)
        return self.applications[key]

    def forget(self, root):
        self.verified.clear()
        for name, (path, _, module, owner) in list(self.loaded.items()):
            if owner == root and self.application(path, root):
                if sys.modules.get(name) is module:
                    sys.modules.pop(name, None)
                del self.loaded[name]

    def find_spec(self, fullname, path=None, target=None):
        spec = machinery.PathFinder.find_spec(fullname, path, target)
        if not spec or not isinstance(spec.loader, machinery.SourceFileLoader) or not self.owns(spec.origin):
            return None
        for hook in sys.meta_path:
            if type(hook).__module__ == '_pytest.assertion.rewrite':
                rewritten = hook.find_spec(fullname, path, target)
                if rewritten is not None:
                    rewritten.loader = _Rewritten(rewritten.loader)
                    return rewritten
        spec.loader = _Source(fullname, spec.origin)
        return spec


_finder = _Finder()


def _find(name, specs=None):
    # Shared package prefixes have one origin within this preparation snapshot.
    # Never retain these resolutions between prepare() calls.
    specs = {} if specs is None else specs
    locations = None
    spec = None
    parts = name.split('.')
    for count in range(1, len(parts) + 1):
        prefix = '.'.join(parts[:count])
        if prefix not in specs:
            specs[prefix] = machinery.PathFinder.find_spec(prefix, locations)
        spec = specs[prefix]
        if spec is None:
            break
        locations = spec.submodule_search_locations
    return spec


def _root_names(root):
    """Flat-name candidates and finders in the known standard path prefix."""
    names = set()
    providers = {}
    loaders = (machinery.SourceFileLoader, machinery.SourcelessFileLoader,
               machinery.ExtensionFileLoader)
    try:
        for entry in sys.path:
            if not isinstance(entry, str):
                continue
            # Do not invoke a path hook that the original lookup may never
            # reach. Only this known prefix can certify a stopping point.
            key = entry or os.getcwd()
            if key not in sys.path_importer_cache:
                break
            finder = sys.path_importer_cache[key]
            if finder is None:
                continue
            if (type(finder) is not machinery.FileFinder
                    or any(method in vars(finder) for method in ('find_spec', '_get_spec', '_fill_cache'))
                    or any(not any(loader is standard for standard in loaders) for _, loader in finder._loaders)):
                break
            # Use the cached finder's lexical path: a relative sys.path entry
            # can still refer to an earlier cwd, and symlinks can leave/reenter
            # the root. Resolving this path could wrongly exclude an origin.
            directory = Path(finder.path)
            if not directory.is_absolute():
                break
            if directory.is_relative_to(root):
                for filename in os.listdir(directory):
                    folded = os.path.normcase(filename).casefold()
                    names.add(folded)
                    for suffix, _ in finder._loaders:
                        suffix = os.path.normcase(suffix).casefold()
                        if suffix and folded.endswith(suffix):
                            names.add(folded[:-len(suffix)])
            elif root.is_relative_to(directory):
                names.add(os.path.normcase(root.relative_to(directory).parts[0]).casefold())
            providers[directory] = finder
    except Exception:
        return set(), {}
    return names, providers


def prepare(root, *, host=False):
    """Start a verification snapshot before application imports.

    Recreate a Model/Engine after changing files. Existing references held by an
    application are not hot-reloaded; use the CLI for an independent process.
    """
    root = Path(root).resolve()
    if _finder.active and root != _finder.root:
        raise ValueError('another nested pytest verification is active; start a fresh verification process')
    claimed = host and _finder.host is None
    if host:
        if _finder.host is not None and _finder.host != root:
            raise ValueError('another pytest verification is active; start a fresh verification process')
        _finder.host = root
    if _finder.root is not None and _finder.root not in (root, _finder.host):
        _finder.forget(_finder.root)
    _finder.root = root
    if _finder.verified_for != (root, _finder.host):
        _finder.verified, _finder.verified_for = {}, (root, _finder.host)
    # Pytest installs its rewrite hook after sitecustomize. Keep our delegating
    # finder ahead of it when the same process enters verification.
    if _finder in sys.meta_path:
        sys.meta_path.remove(_finder)
    sys.meta_path.insert(0, _finder)
    if _finder.host is not None and _finder.host != root:
        specs = {}
        names, providers = _root_names(root)
        for name, (path, _, module, owner) in _finder.loaded.items():
            if owner != _finder.host or not _finder.application(path, owner):
                continue
            if (name.isidentifier() and path.name == name + '.py'
                    and os.path.normcase(name).casefold() not in names
                    and (provider := providers.get(path.parent)) is not None):
                try:
                    stopping = provider.find_spec(name)
                    if (stopping is not None and stopping.loader is not None and stopping.origin
                            and not project_code(stopping.origin, root)):
                        continue
                except Exception:
                    pass
            expected = _find(name, specs)
            if (expected is not None and expected.origin and project_code(expected.origin, root)
                    and Path(expected.origin).resolve() != path and sys.modules.get(name) is module):
                raise ValueError(f'{name} conflicts with the active pytest verifier; '
                                 'start a fresh verification process for this project')
    # Classify each loaded module once per (root, host): a later preparation in the
    # same session only looks at modules that are new since then. Changed sources
    # are still found below by their content digests.
    verified = _finder.verified
    for name, module in list(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        identity = (id(module), filename)
        if verified.get(name) == identity:
            continue
        if (not filename or not str(filename).endswith(tuple(machinery.SOURCE_SUFFIXES))
                or not _finder.owns(str(filename))):
            verified[name] = identity
            continue
        path = Path(filename).resolve()
        if not _finder.application(path, root):
            verified[name] = identity
            continue
        previous = _finder.loaded.get(name)
        if previous is None or previous[0] != path or previous[2] is not module:
            raise ValueError(f'{name} was imported before source verification: {path}; '
                             'start a fresh verification process before importing project code '
                             '(python -m flowguard check --all)')
        verified[name] = identity
    # Imported aliases can retain a changed function, so refresh the loaded
    # project cohort together. No directory scan or external module eviction.
    changed = {path for path, digest, _, owner in _finder.loaded.values()
               if owner == root and _finder.application(path, root)
               and (not path.is_file() or util.source_hash(path.read_bytes()) != digest)}
    if changed:
        for path in changed:
            linecache.cache.pop(str(path), None)
        for path, _, module, _ in _finder.loaded.values():
            if path in changed:
                linecache.cache.pop(getattr(module, '__file__', str(path)), None)
        if root == _finder.host or _finder.active:
            raise ValueError('project source changed during pytest verification; start a fresh verification process')
        _finder.forget(root)
    importlib.invalidate_caches()
    return claimed


def source_spec(name, path):
    return util.spec_from_file_location(name, path, loader=_Source(name, str(path)))


def hold_root(root):
    """Keep the one temporary source slot stable for its active pytest session."""
    root = Path(root).resolve()
    if root != _finder.root:
        raise ValueError('verification source changed before its session started')
    if root == _finder.host or _finder.active:
        return False
    _finder.active = True
    return True


def release_root(root):
    if _finder.active and _finder.root == Path(root).resolve():
        _finder.active = False


def release_host(root):
    if _finder.host == Path(root).resolve():
        _finder.host = None
