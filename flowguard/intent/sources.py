"""The archive backs a source; it does not prove that the interpretation is correct."""
from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
from pathlib import Path
import re
import shlex

from .api import IntentError
from flowguard.map.requests import quote_matches, request_state
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
    """Stored owner words, each request checked when a source first cites it: a session pays for the
    requests its rules cite, not for every stored request."""
    def __init__(self, root):
        self.root = Path(root)
        self.present = (self.root / '.flowguard/requests').is_dir()
        self.rows = {}

    def status(self, rid, quote=None):
        if self.present and rid not in self.rows:
            self.rows[rid] = request_state(self.root, rid)
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


# ---- the catalog: .flowguard/rules.toml and .flowguard/known.toml (4.3) ------------------------------------

CATALOG_FILES = ('.flowguard/rules.toml', '.flowguard/known.toml')
ACTS = ('leave', 'ask', 'fix', 'ignore')       # what a known entry asks of the agent (`act`)


@dataclass(frozen=True)
class CatalogRule:
    """`[rule.<id>]` of rules.toml: a rule in force, its one-line text and its source (`R<n> "words"`)."""
    id: str
    text: str
    source: str
    line: int


@dataclass(frozen=True)
class Known:
    """`[known.<id>]` of known.toml: an open matter, its sites (`path:symbol`) and what to do about it; `nodes`
    and `files` are the sites resolved on the map."""
    id: str
    sites: tuple
    why: str
    act: str                    # one of ACTS
    ask: str = ''
    asked: str = ''             # YYYY-MM-DD, once the owner was asked
    fix: str = ''
    source: str = ''
    finding: str = ''           # the finding name FlowGuard can judge (Issue.name or same:NAME)
    line: int = 0
    nodes: frozenset = frozenset()
    files: frozenset = frozenset()


@dataclass
class Catalog:
    """The valid rules and known entries by id, and the input findings of the invalid ones (health.Issue)."""
    rules: dict = field(default_factory=dict)
    known: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)


def catalog_files(cfg):
    """The catalog files present in the working tree."""
    return [name for name in CATALOG_FILES if (cfg.root / name).is_file()]


def catalog(cfg, revision=None):
    """The catalog in the working tree, or at `revision`. This version reads neither file yet: the catalog is
    empty, also when one of them is present."""
    return Catalog()


def findings(cfg, graph, change):
    """The catalog's findings for `owners.static_findings`: invalid entries and the sources they cite. None yet."""
    from .owners import Findings
    return Findings()
