"""The project's existing pyproject configuration; no separate model configuration."""
from __future__ import annotations

import fnmatch
from functools import cache
import os
from pathlib import Path
import sys
import tomllib
from dataclasses import dataclass, field

_INSERTED_PATHS = set()


@dataclass
class Config:
    root: Path
    roots: list[Path] = field(default_factory=list)
    intent: Path | None = None
    exclude: list[str] = field(default_factory=list)
    authority_docs: list[str] = field(default_factory=list)
    screen_lines: int = 40
    check_lines: int = 20
    skip_policy: str = 'platform'
    ledger_paths: list[str] = field(default_factory=lambda: ['**'])
    ledger_exclude: list[str] = field(default_factory=list)

    @property
    def cache(self):
        return self.root / '.flowguard' / 'cache'

    def rel(self, path):
        resolved = Path(path).resolve()
        return resolved.relative_to(self.root).as_posix() if resolved.is_relative_to(self.root) else str(resolved)


def find_root(start=None):
    here = Path(start or os.getcwd()).resolve()
    for path in (here, *here.parents):
        if (path / 'pyproject.toml').is_file() or (path / '.git').exists():
            return path
    return here


def load_config(root=None):
    root = Path(root or find_root()).resolve()
    path = root / 'pyproject.toml'
    data = tomllib.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    settings = data.get('tool', {}).get('flowguard', {})
    # `propagate` names TS/JS functions that hand a caught error on; the map reader reads it.
    allowed = {'roots', 'intent', 'exclude', 'authority_docs', 'screen_lines', 'check_lines', 'skip_policy', 'ledger',
               'propagate'}
    if set(settings) - allowed:
        raise ValueError('unknown [tool.flowguard] keys: ' + ', '.join(sorted(set(settings) - allowed)))
    cfg = Config(root, [root / value for value in settings.get('roots', [])],
                 root / settings.get('intent', 'tests/intent'),
                 list(settings.get('exclude', [])), list(settings.get('authority_docs', [])),
                 settings.get('screen_lines', 40), settings.get('check_lines', 20), settings.get('skip_policy', 'platform'))
    if not cfg.roots and (root / 'src').is_dir():
        cfg.roots = [root / 'src']
    for value in (cfg.screen_lines, cfg.check_lines):
        if type(value) is not int or value < 1:
            raise ValueError('screen_lines and check_lines must be positive whole numbers')
    if cfg.skip_policy not in ('platform', 'no_skip', 'forbid'):
        raise ValueError('skip_policy must be platform, no_skip or forbid')
    if 'ledger' in settings:
        ledger = settings['ledger']
        if not isinstance(ledger, dict) or set(ledger) - {'paths', 'exclude'}:
            raise ValueError('[tool.flowguard.ledger] takes only paths and exclude')
        for name in ('paths', 'exclude'):
            if name in ledger and (not isinstance(ledger[name], list) or not all(isinstance(item, str) and item for item in ledger[name])):
                raise ValueError(f'[tool.flowguard.ledger] {name} must be a list of path patterns')
        cfg.ledger_paths = list(ledger['paths']) if 'paths' in ledger else cfg.ledger_paths
        cfg.ledger_exclude = list(ledger['exclude']) if 'exclude' in ledger else cfg.ledger_exclude
    return cfg


def setup_path(cfg):
    """Match pytest's configured pythonpath and prepend import mode for intent helpers."""
    for text in _INSERTED_PATHS:
        if text in sys.path:
            sys.path.remove(text)
    _INSERTED_PATHS.clear()
    path = cfg.root / 'pyproject.toml'
    ini = tomllib.loads(path.read_text(encoding='utf-8-sig')).get('tool', {}).get('pytest', {}).get('ini_options', {}) if path.is_file() else {}
    extras = ini.get('pythonpath', [])
    extras = extras.split() if isinstance(extras, str) else extras
    paths = [cfg.root, *cfg.roots, *(cfg.root / part for part in extras)]
    for file in intent_files(cfg):
        base = file.parent
        while (base / '__init__.py').is_file():
            base = base.parent
        paths.append(base)
    for folder in dict.fromkeys(reversed(paths)):
        text = str(folder)
        if text in sys.path:
            sys.path.remove(text)
        else:
            _INSERTED_PATHS.add(text)
        sys.path.insert(0, text)


def intent_files(cfg):
    return sorted(p for p in cfg.intent.rglob('*.py') if not p.name.startswith('_')) if cfg.intent.is_dir() else []


def is_test_rel(rel):
    parts = Path(rel).parts
    return any(p in {'tests', 'test', 'testing'} for p in parts[:-1]) or parts[-1].startswith('test_') or parts[-1].endswith('_test.py') or parts[-1] == 'conftest.py'


def project_code(cfg):
    from ..structure.paths import project_code as owned

    @cache
    def check(filename):
        if not owned(filename, cfg.root):
            return False
        path = Path(filename).resolve()
        rel = cfg.rel(path)
        return (not is_test_rel(rel) and not path.is_relative_to(cfg.intent)
                and not any(fnmatch.fnmatch(rel, pattern) for pattern in cfg.exclude))
    return check
