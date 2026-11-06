"""The archive backs a source; it does not prove that the interpretation is correct."""
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path
import re
import shlex

from .api import IntentError
from flowguard.map.requests import owner_words, quote_matches
from flowguard.map.common import git_blob, git_common_directory, git_head, git_run


@dataclass
class Source:
    kind: str
    text: str
    rids: tuple = ()
    path: str = ''
    quote: str = ''
    line: int = 0


def parse(text):
    match = re.fullmatch(r'owner\s+([A-Za-z][A-Za-z0-9_-]*)(?::\s*(.*))?', text.strip(), re.S)
    if match:
        return Source('owner', text, (match[1],))
    if text.startswith('doc '):
        try:
            parts = shlex.split(text)
        except ValueError as error:
            raise IntentError(f'invalid doc source: {error}') from error
        if len(parts) == 3 and parts[2].strip():
            path, colon, line = parts[1].rpartition(':')
            return Source('doc', text, path=path if colon and line.isdigit() else parts[1],
                          quote=parts[2], line=int(line) if colon and line.isdigit() else 0)
        raise IntentError('doc source needs its words: doc PATH "quoted words"; a line number alone can drift')
    for kind in ('assumed', 'lesson'):
        if text.startswith(kind + ':'):
            return Source(kind, text, tuple(re.findall(r'\bR\d+[A-Za-z0-9_-]*\b', text)))
    raise IntentError('source needs owner R-id, doc PATH "quoted words", assumed: or lesson:')


class Archive:
    def __init__(self, root):
        self.root = Path(root)
        self.rows = {r['id']: r for r in owner_words(self.root)['rows']} if (self.root / '.flowguard/requests').is_dir() else {}

    def status(self, rid, quote=None):
        item = self.rows.get(rid)
        if item is None:
            return False, f'{rid} missing -> req add the actual owner words'
        if item.get('invalid') or item.get('edited') or item.get('unverified'):
            return False, f'{rid} bytes unverified -> restore the stored original'
        if item.get('retired') or item.get('superseded_by'):
            return False, f'{rid} is no longer current -> cite the current request'
        if quote is not None:
            text = (self.root / '.flowguard/requests' / (rid + '.md')).read_text(encoding='utf-8-sig')
            if not quote_matches(text, quote):
                return False, f'{rid} quote gone -> quote the actual stored words'
        return True, f'owner {rid}'


# flowguard: sensor SOURCE_AUTHORITY(src: source, rule_confirmed: request, cfg: config, archive: archive, quote: words) -> answer: tuple[bool, str] calibrated_by=tests/test_anchor_self_rules.py::test_authority_anchor_case[EXACT]
def authority(src: Source, rule_confirmed: str | None, cfg: object, archive: object, quote: str | None = None) -> tuple[bool, str]:
    if src.kind == 'owner':
        return archive.status(src.rids[0], quote)
    if src.kind == 'doc':
        if not any(fnmatch.fnmatch(src.path, pattern) for pattern in cfg.authority_docs):
            return False, f'doc {src.path} not listed -> list the agreed authority_docs'
        path = (cfg.root / src.path).resolve()
        if not path.is_relative_to(cfg.root) or not path.is_file():
            return False, f'doc {src.path} gone -> restore or update its source'
        if not quote_matches(path.read_text(encoding='utf-8-sig'), src.quote):
            return False, f'doc quote gone: {src.path} -> update the rule from the original'
        return True, f'doc {src.path}'
    if rule_confirmed:
        return archive.status(rule_confirmed)
    for rid in src.rids:
        valid, reason = archive.status(rid)
        if valid:
            return True, reason
    return False, f'{src.kind} -> confirm against actual owner words'


def provisional(src, cfg, intent_file):
    """A doc and its authority entry written with the rule are visible as green*."""
    if src.kind != 'doc':
        return False
    if git_common_directory(cfg.root) is None or git_head(cfg.root) is None:
        return True
    relative = cfg.rel(intent_file)
    tracked = git_run(cfg.root, 'ls-files', '--error-unmatch', '--', relative, allowed=(0, 1)).returncode == 0
    changes = git_run(cfg.root, 'status', '--porcelain', '--', relative, src.path, 'pyproject.toml').stdout
    if not tracked or changes:
        return True
    history = git_run(cfg.root, 'log', '-1', '--format=%H', '--', relative).stdout.decode().strip()
    if not history:
        return True
    parent = git_run(cfg.root, 'rev-parse', '--verify', history + '^', allowed=(0, 128))
    if parent.returncode:
        return True
    revision = parent.stdout.decode().strip()
    old_doc = git_blob(cfg.root, revision, src.path)
    if old_doc is None or not quote_matches(old_doc.decode('utf-8-sig'), src.quote):
        return True
    import tomllib
    old_cfg = git_blob(cfg.root, revision, 'pyproject.toml')
    allowed = tomllib.loads(old_cfg.decode('utf-8-sig')).get('tool', {}).get('flowguard', {}).get('authority_docs', []) if old_cfg else []
    return not any(fnmatch.fnmatch(src.path, pattern) for pattern in allowed)
