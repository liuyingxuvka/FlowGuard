"""Classify real pytest failures without watching files or recording boundary values."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess


def project_module(name, cfg):
    """A missing child of a project package is a code failure too."""
    head = (name or '').split('.')[0]
    return bool(head) and any((base / head).is_dir() or (base / (head + '.py')).is_file()
                              for base in (cfg.root, *cfg.roots))


def _text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value or '')


def _outside(filename, cfg):
    if not filename:
        return False
    path = Path(filename)
    path = path if path.is_absolute() else cfg.root / path
    return not path.resolve().is_relative_to(cfg.root)


def child_failure(text, cfg):
    """Only recognize an actual traceback, not a test's mention of an error name."""
    if 'Traceback (most recent call last)' not in text:
        return None
    match = re.search(r'''(?m)^(?:E\s+)?(?:ModuleNotFoundError|ImportError):.*?(?:No module named|from) ['"]([^'"]+)['"]''', text)
    if match:
        name = match[1]
        return ('code', f'project import {name}') if project_module(name, cfg) else ('env', f'missing package {name}')
    match = re.search(r'''(?m)^(?:E\s+)?(?:FileNotFoundError|PermissionError|OSError):[^\n]*?['"]([^'"]+)['"]''', text)
    if match and _outside(match[1], cfg):
        return 'env', 'child os error outside project'
    return None


def classify(when, excinfo, cfg, *, text=''):
    """Return the cause category; the original pytest outcome is never changed."""
    error = excinfo.value if excinfo is not None else None
    seen, explicit_code = set(), ''
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)) or 'Timeout' in type(error).__name__:
            return 'env', 'timeout'
        if isinstance(error, ImportError):
            name = getattr(error, 'name', '') or ''
            return ('code', f'project import {name}') if project_module(name, cfg) else ('env', f'missing package {name}')
        if isinstance(error, (FileNotFoundError, NotADirectoryError, PermissionError)):
            return ('env', type(error).__name__) if _outside(getattr(error, 'filename', ''), cfg) else ('code', 'project ' + type(error).__name__)
        if isinstance(error, OSError) and _outside(getattr(error, 'filename', ''), cfg):
            return 'env', 'os error outside project'
        if isinstance(error, subprocess.CalledProcessError):
            text += '\n' + _text(error.stdout) + '\n' + _text(error.stderr)
        if isinstance(error, (SyntaxError, AssertionError)):
            explicit_code = type(error).__name__
        error = error.__cause__ or error.__context__
    parsed = child_failure(text, cfg)
    if parsed:
        return parsed
    if when != 'call':
        return ('code', f'{when}: {explicit_code}') if explicit_code else ('env', 'collection' if when == 'collect' else 'fixture')
    return 'code', ''


def classify_collection(text, cfg):
    """Pytest has rendered its collection traceback; keep explicit code defects visible."""
    for name in ('SyntaxError', 'AssertionError', 'IndentationError'):
        if re.search(r'\b' + name + r':', text):
            return 'code', 'collection: ' + name
    match = re.search(r"(?:ModuleNotFoundError|ImportError):.*?No module named ['\"]([^'\"]+)['\"]", text)
    if match and project_module(match[1], cfg):
        return 'code', 'collection: project import ' + match[1]
    return 'env', 'collection'
