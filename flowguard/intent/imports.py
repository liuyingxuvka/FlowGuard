"""Content-checked imports for the project's verification process.

Only imported project files are touched. Python's normal checked-hash bytecode
format is reused; dependency packages and the interpreter keep their own loaders.
"""
from __future__ import annotations

import importlib
from importlib import _bootstrap_external, machinery, util
import linecache
from pathlib import Path
import sys

from flowguard.structure.paths import project_code

_SDK = Path(__file__).resolve().parent.parent


def _remember(name, path, fingerprint):
    path = Path(path).resolve()
    owner = _finder.root if _finder.root is not None and project_code(str(path), _finder.root) else _finder.host
    _finder.loaded[name] = (path, fingerprint, sys.modules.get(name), owner)


class _Source(machinery.SourceFileLoader):
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


class _Finder:
    def __init__(self):
        self.root = self.host = None
        self.loaded = {}

    def owns(self, filename):
        return any(root is not None and project_code(filename, root) for root in (self.root, self.host))

    def application(self, path, root):
        return project_code(str(path), root) and not path.is_relative_to(_SDK)

    def forget(self, root):
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


def _find(name):
    locations = None
    spec = None
    parts = name.split('.')
    for count in range(1, len(parts) + 1):
        spec = machinery.PathFinder.find_spec('.'.join(parts[:count]), locations)
        if spec is None:
            break
        locations = spec.submodule_search_locations
    return spec


def prepare(root, *, host=False):
    """Start a verification snapshot before application imports.

    Recreate a Model/Engine after changing files. Existing references held by an
    application are not hot-reloaded; use the CLI for an independent process.
    """
    root = Path(root).resolve()
    if host:
        if _finder.host is not None and _finder.host != root:
            raise ValueError('another pytest verification is active; start a fresh verification process')
        _finder.host = root
    if _finder.root is not None and _finder.root not in (root, _finder.host):
        _finder.forget(_finder.root)
    _finder.root = root
    # Pytest installs its rewrite hook after sitecustomize. Keep our delegating
    # finder ahead of it when the same process enters verification.
    if _finder in sys.meta_path:
        sys.meta_path.remove(_finder)
    sys.meta_path.insert(0, _finder)
    if _finder.host is not None and _finder.host != root:
        for name, (path, _, module, owner) in _finder.loaded.items():
            if owner != _finder.host or not _finder.application(path, owner):
                continue
            expected = _find(name)
            if (expected is not None and expected.origin and project_code(expected.origin, root)
                    and Path(expected.origin).resolve() != path and sys.modules.get(name) is module):
                raise ValueError(f'{name} conflicts with the active pytest verifier; '
                                 'start a fresh verification process for this project')
    for name, module in list(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if (not filename or not str(filename).endswith(tuple(machinery.SOURCE_SUFFIXES))
                or not _finder.owns(str(filename))):
            continue
        path = Path(filename).resolve()
        if not _finder.application(path, root):
            continue
        previous = _finder.loaded.get(name)
        if previous is None or previous[0] != path or previous[2] is not module:
            raise ValueError(f'{name} was imported before source verification: {path}; '
                             'start a fresh verification process before importing project code '
                             '(python -m flowguard check --all)')
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
        if root == _finder.host:
            raise ValueError('project source changed during pytest verification; start a fresh verification process')
        _finder.forget(root)
    importlib.invalidate_caches()


def source_spec(name, path):
    return util.spec_from_file_location(name, path, loader=_Source(name, str(path)))


def release_host(root):
    if _finder.host == Path(root).resolve():
        _finder.host = None
