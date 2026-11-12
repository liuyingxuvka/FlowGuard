"""The archive backs a source; it does not prove that the interpretation is correct."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field, replace
import fnmatch
from pathlib import Path
import re
import shlex
import tomllib

from .api import IntentError
from flowguard.map.requests import (REQUEST_DIR, RETIRED_DIR, added_since, exact_quote, quote_matches, read_request_bytes,
                                    request_states)
from flowguard.map.common import git_blob, git_common_directory, git_head, git_run


@dataclass
class Source:
    kind: str                   # owner, doc, assumed, lesson; request (`R74 "words"`); rule (`rule.<id>`)
    text: str
    rids: tuple = ()
    path: str = ''
    quote: str = ''
    line: int = 0
    rule: str = ''              # the id `rule.<id>` names
    strict: bool = False        # its words are compared exactly (`exact_quote`), never whitespace-folded or elided


CATALOG_ID = r'[A-Za-z0-9][A-Za-z0-9_-]*'          # the id of `[rule.<id>]` and `[known.<id>]`: a TOML bare key
RULE_FORM = re.compile(r'rule\.(' + CATALOG_ID + ')')
REQUEST_FORM = re.compile(r'([A-Za-z][A-Za-z0-9_-]*) "(.*)"', re.S)
DOC_FORM = re.compile(r'doc (\S+) "(.*)"', re.S)


def _canonical(text):
    """The source form of rules.toml and known.toml (design 4.4), or None: `R74 "words"` or `doc PATH "words"`, the
    words between the first `"` and the last one, read as they are written (no escapes)."""
    document = DOC_FORM.fullmatch(text)
    if document:
        return Source('doc', text, path=document[1], quote=document[2], strict=True)
    request = REQUEST_FORM.fullmatch(text)
    if request and request[1] != 'doc':
        return Source('request', text, (request[1],), quote=request[2], strict=True)
    return None


def parse(text, strict=False):
    """The source of an intent declaration, or with `strict` one of rules.toml or known.toml (only `R74 "words"` and
    `doc PATH "words"`, compared exactly). An intent declaration may also cite a rule of rules.toml (`rule.<id>`, its
    source checked strictly) or the request form; its older forms (`owner R1`, `doc PATH "words"` read as shell words,
    `assumed:`, `lesson:`) keep their whitespace-folding comparison."""
    if strict:
        if RULE_FORM.fullmatch(text):
            raise IntentError('a rules.toml or known.toml source quotes the owner\'s words or a document, not another '
                              'entry: R<id> "exact words" or doc PATH "exact words"')
        source = _canonical(text)
        if source is None:
            raise IntentError('source is R<id> "exact words" (a stored request) or doc PATH "exact words" (a document of '
                              'authority_docs)')
        return source
    match = re.fullmatch(r'owner\s+([A-Za-z][A-Za-z0-9_-]*)(?::\s*(.*))?', text.strip(), re.S)
    if match:
        return Source('owner', text, (match[1],))
    cited = RULE_FORM.fullmatch(text.strip())
    if cited:
        return Source('rule', text, rule=cited[1], strict=True)
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
    request = REQUEST_FORM.fullmatch(text)
    if request:
        return Source('request', text, (request[1],), quote=request[2], strict=True)
    raise IntentError('source needs rule.<id> (a rule of .flowguard/rules.toml), R<id> "exact words", owner R-id, '
                      'doc PATH "quoted words", assumed: or lesson:')


class Archive:
    """Stored owner words, each request checked when a source first cites it: a session pays for the
    requests its rules cite, not for every stored request."""
    def __init__(self, root):
        self.root = Path(root)
        self.present = (self.root / '.flowguard/requests').is_dir()
        self.rows = {}

    def read(self, rids):
        """Check the stored requests of `rids` not read yet, with one listing of the archive for all of them
        (`request_states`)."""
        unread = [rid for rid in dict.fromkeys(rids) if rid not in self.rows]
        if self.present and unread:
            self.rows.update(request_states(self.root, unread))

    def row(self, rid):
        """`request_state` of one stored request (None when none is stored), read once."""
        self.read([rid])
        return self.rows.get(rid)

    def status(self, rid, quote=None):
        item = self.row(rid)
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


_ARCHIVES = {}      # resolved root -> (what its request files are, the Archive read from them)


def shared_archive(root):
    """The Archive of `root` for this process, shared by the engine, the static findings, the dependency digests
    and show, so one run checks each cited request once; a fresh one once a file under .flowguard/requests was
    added, removed or rewritten (a request stored, retired or edited, its .gitattributes changed)."""
    root = Path(root).resolve()
    directory = root / REQUEST_DIR
    stamp = tuple(sorted((path.relative_to(directory).as_posix(), status.st_size, status.st_mtime_ns)
                         for path in directory.rglob('*') for status in [path.lstat()])) if directory.is_dir() else ()
    held = _ARCHIVES.get(root)
    if held is None or held[0] != stamp:
        held = _ARCHIVES[root] = (stamp, Archive(root))
    return held[1]


# flowguard: sensor SOURCE_AUTHORITY(src: source, rule_confirmed: request, cfg: config, archive: archive, quote: words) -> answer: tuple[bool, str] calibrated_by=tests/test_anchor_self_rules.py::test_authority_anchor_case[EXACT]
def authority(src: Source, rule_confirmed: str | None, cfg: object, archive: object, quote: str | None = None) -> tuple[bool, str]:
    if src.strict:
        return catalog_authority(src, cfg, archive)
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


RULES, KNOWN = CATALOG_FILES
PREFIX = {'rule': 'rules', 'known': 'known'}         # the input findings: rules-entry:rule.<id>, known-file:<path>, ...
RULE_KEYS = ('text', 'source')
KNOWN_KEYS = ('sites', 'why', 'act', 'ask', 'asked', 'fix', 'source', 'finding')
SHA = re.compile(r'[0-9a-f]{40}([0-9a-f]{24})?')     # a commit id: what it names never changes
_HEADER = re.compile(r'\s*\[\s*(rule|known)\s*\.\s*(?:"([^"\\]*)"|\'([^\']*)\'|([A-Za-z0-9_-]+))\s*\]\s*(?:#.*)?')
_AT = {}            # (root, commit, what) -> what that commit holds: its catalog, a file's bytes, its intent declarations


def _held(cfg, revision, what, compute):
    """`compute()` once per process for a commit (`SHA`); every time for the working tree or a name like HEAD."""
    if revision is None or not SHA.fullmatch(revision):
        return compute()
    key = (str(cfg.root), revision, what)
    if key not in _AT:
        _AT[key] = compute()
    return _AT[key]


def _bytes_at(cfg, revision, path):
    """A file's bytes in the working tree (revision None) or at a commit; None when it is not there."""
    if revision is None:
        target = cfg.root / path
        return target.read_bytes() if target.is_file() else None
    return _held(cfg, revision, 'blob:' + path, lambda: git_blob(cfg.root, revision, path))


def _load(raw):
    """(the TOML table, '') of a catalog file's bytes, or (None, what is wrong) when they are not UTF-8 TOML."""
    try:
        return tomllib.loads(raw.decode('utf-8-sig')), ''
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        return None, str(error)


def _input(name, subject, place, problems, step, files):
    """The input finding of an invalid catalog file or entry: red in every run (D4), it closes and checks nothing.
    Its line names the file or entry once, as its subject (`red: known.x: act is one of ...`): `place` (the file, or
    `file:table.id`) is the line's place without being repeated in its text."""
    from .health import Issue
    what = '; '.join(problems)
    # Rank 0 is no rank of the structure listing (health.RANKS): the 4.3 lines report it, not the structure checks.
    return Issue(name, 0, subject, f'{subject}: {what}', step, files=frozenset(files), new=True, family='input',
                 subject=subject, parts=(('', (place,), what, step),), fresh=frozenset({''}), detail=tuple(problems))


def _date_problem(text):
    """'' for a YYYY-MM-DD calendar date, else what is wrong."""
    match = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', text)
    if not match:
        return f'asked is a date written YYYY-MM-DD, not {text!r}'
    year, month, day = map(int, match.groups())
    if not 1 <= month <= 12 or not 1 <= day <= calendar.monthrange(year, month)[1]:
        return f'asked {text} is no calendar date'
    return ''


def _site_problem(cfg, site, revision):
    """'' for a site spelt `path:symbol`, its path relative to the repository (and a file of the working tree), else
    what is wrong. Which function, method, holder.method, constant or Model.field it names is read on the map
    (`known_sites`)."""
    if not isinstance(site, str) or not site:
        return f'a site is a string path:symbol, not {site!r}'
    path, colon, symbol = site.rpartition(':')
    if not colon:
        return f'site {site} is a bare name: write path:symbol, the path relative to the repository'
    if not path or path.startswith('/') or '\\' in path or ':' in path or any(part in ('', '.', '..') for part in path.split('/')):
        return f'site {site} needs a repository-relative path before the colon (forward slashes, no ..)'
    if not re.fullmatch(r'(?:[^\W\d]|\$)[\w$]*(?:\.(?:[^\W\d]|\$)[\w$]*)*', symbol):
        return f'site {site} needs a function, object.method, constant or Model.field after the colon'
    if revision is None and not (cfg.root / path).is_file():
        return f'site {site}: {path} is not a file of this repository'
    return ''


def _rule_entry(value):
    """(CatalogRule fields, problems) of one `[rule.<id>]` table."""
    problems = [f'unknown key {key} (a rule has only text and source)' for key in value if key not in RULE_KEYS]
    problems += [f'missing {key}' for key in RULE_KEYS if key not in value]
    text, source = value.get('text'), value.get('source')
    if 'text' in value and (not isinstance(text, str) or not text.strip() or '\n' in text or '\r' in text):
        problems.append('text is one line of words')
    if 'source' in value:
        problems.extend(_source_problems(source))
    return dict(text=text, source=source), problems


def _source_problems(source):
    """What is wrong with the syntax of a catalog source (its words are checked against the archive separately)."""
    if not isinstance(source, str):
        return [f'source is a string R<id> "exact words" or doc PATH "exact words", not {source!r}']
    if RULE_FORM.fullmatch(source):
        return [f'source {source} cites another catalog entry: quote the owner\'s words or a document instead']
    if _canonical(source) is None:
        return [f'source {source!r} is neither R<id> "exact words" nor doc PATH "exact words"']
    return []


def _known_entry(cfg, value, revision):
    """(Known fields, problems) of one `[known.<id>]` table (design 4.4; D10: only a structure finding may be ignored)."""
    from .signals import FAMILIES, family_of
    problems = [f'unknown key {key} (known.toml entries have {", ".join(KNOWN_KEYS)})' for key in value if key not in KNOWN_KEYS]
    for key in ('sites', 'why', 'act'):
        if key not in value:
            problems.append(f'missing {key}')
    for key in ('why', 'act', 'ask', 'asked', 'fix', 'finding'):
        if key in value and not isinstance(value[key], str):
            problems.append(f'{key} is a string, not {value[key]!r}')
    text = {key: value[key] for key in ('why', 'act', 'ask', 'asked', 'fix', 'finding') if isinstance(value.get(key), str)}
    sites = value.get('sites')
    if 'sites' in value:
        if not isinstance(sites, list) or not sites:
            problems.append('sites is a non-empty list of path:symbol')
            sites = []
        problems.extend(problem for problem in (_site_problem(cfg, site, revision) for site in sites) if problem)
    why, act, finding = text.get('why', ''), text.get('act', ''), text.get('finding', '')
    if 'why' in text and not why.strip():
        problems.append('why says what the matter is: it is empty')
    if 'act' in text and act not in ACTS:
        problems.append(f'act is one of {", ".join(ACTS)}, not {act!r}')
    if act == 'ask' and not text.get('ask', '').strip():
        problems.append('act = "ask" needs ask: the question for the owner')
    if text.get('asked'):
        problems.extend(problem for problem in [_date_problem(text['asked'])] if problem)
    if finding and not family_of(finding):
        problems.append(f'finding {finding} names no finding FlowGuard reports (pair:, values:, same:, ...)')
    if act == 'ignore' and not (finding and family_of(finding) and FAMILIES[family_of(finding)][2]):
        problems.append('act = "ignore" is only for a finding of an automatic structure check (delete:, columns:, '
                        'ondelete:, labels:, uncreated:, copies:, declarations:, writers:); for an agreement of a '
                        'flowguard: comment write except= there')
    if 'source' in value:
        problems.extend(_source_problems(value['source']))
    fields = dict(sites=tuple(sites) if isinstance(sites, list) else (), why=why, act=act, ask=text.get('ask', ''),
                  asked=text.get('asked', ''), fix=text.get('fix', ''), source=value.get('source', ''), finding=finding)
    return fields, problems


def catalog(cfg, revision=None):
    """`.flowguard/rules.toml` and `.flowguard/known.toml` in the working tree, or at the commit `revision`: the valid
    rules and known entries by id in file order, and one input finding (family 'input') per file that is not UTF-8
    TOML, per table outside `[rule.<id>]` / `[known.<id>]` and per invalid entry, which is left out (fail-closed: a
    valid site beside an invalid one does not make the entry count). A missing file is an empty part. The sites are
    resolved on the map by `known_sites`; the words of the sources are checked by `catalog_authority`."""
    return _held(cfg, revision, 'catalog', lambda: _read_catalog(cfg, revision))


def _read_catalog(cfg, revision):
    result = Catalog()
    for name, table in ((RULES, 'rule'), (KNOWN, 'known')):
        raw = _bytes_at(cfg, revision, name)
        if raw is None:
            continue
        data, error = _load(raw)
        if data is None:
            result.issues.append(_input(f'{PREFIX[table]}-file:{name}', name, name, [f'not TOML: {error}'],
                                        f'correct the TOML syntax of {name}', [name]))
            continue
        lines = {}
        for number, text in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
            match = _HEADER.fullmatch(text)
            if match and match[1] == table:
                lines.setdefault(match[2] or match[3] or match[4], number)
        others = [key for key in data if key != table]
        if others or not isinstance(data.get(table, {}), dict):
            result.issues.append(_input(f'{PREFIX[table]}-file:{name}', name, name,
                                        [f'holds only [{table}.<id>] tables, not {", ".join(others) or repr(data[table])}'],
                                        f'move each entry under [{table}.<id>] in {name}', [name]))
        entries = data.get(table, {}) if isinstance(data.get(table, {}), dict) else {}
        for identifier, value in entries.items():
            subject, place = f'{table}.{identifier}', f'{name}:{table}.{identifier}'
            if not re.fullmatch(CATALOG_ID, identifier):
                problems, fields = [f'the id {identifier!r} is letters, digits, - and _'], {}
            elif not isinstance(value, dict):
                problems, fields = [f'[{subject}] is a table of keys, not {value!r}'], {}
            elif table == 'rule':
                fields, problems = _rule_entry(value)
            else:
                fields, problems = _known_entry(cfg, value, revision)
            if problems:
                result.issues.append(_input(f'{PREFIX[table]}-entry:{subject}', subject, place, problems,
                                            f'correct [{subject}] in {name}', [name]))
            elif table == 'rule':
                result.rules[identifier] = CatalogRule(identifier, fields['text'], fields['source'], lines.get(identifier, 0))
            else:
                result.known[identifier] = Known(identifier, line=lines.get(identifier, 0), **fields)
    return result


# ---- the words a source cites, now and at a commit (4.7: a quote is judged with the document before the change) ----

def _short(words, width=40):
    return words if len(words) <= width else words[:width - 3] + '...'


def _authority_docs(cfg, revision):
    """The `authority_docs` patterns of `[tool.flowguard]` in pyproject.toml: the configuration's now, the commit's at
    `revision` (none when that commit has no pyproject.toml or no such key)."""
    if revision is None:
        return list(cfg.authority_docs)
    raw = _bytes_at(cfg, revision, 'pyproject.toml')
    if raw is None:
        return []
    return tomllib.loads(raw.decode('utf-8-sig')).get('tool', {}).get('flowguard', {}).get('authority_docs', [])


def _added(cfg, revision, rid):
    return _held(cfg, revision, 'added:' + rid, lambda: added_since(cfg.root, revision, rid))


def _request_problem(cfg, archive, rid, quote, matches, revision, baseline):
    """(what is wrong, the step) of a cited request now (`revision` None: the archive's state) or at a commit (the
    request and its retire record as that commit holds them, and the requests of today's supersession that it holds);
    None when it holds. `baseline` only words a supersession this task stored."""
    row = archive.row(rid)
    if revision is None:
        if row is None:
            return f'{rid} is not stored', f"store the owner's words with python -m flowguard req add - --id {rid}"
        if row['invalid'] or row['edited']:
            return f'{rid} differs from its stored original', 'restore the stored original'
        retired, later = row['retired'], list(row['superseded_by'])
        raw = read_request_bytes(cfg.root, rid) if not retired and not later else None
    else:
        if _added(cfg, revision, rid):
            return f'{rid} was not stored then', f"store the owner's words with python -m flowguard req add - --id {rid}"
        retired = _bytes_at(cfg, revision, (RETIRED_DIR / (rid + '.json')).as_posix()) is not None
        later = [other for other in (row['superseded_by'] if row else ()) if not _added(cfg, revision, other)]
        raw = _bytes_at(cfg, revision, (REQUEST_DIR / (rid + '.md')).as_posix())
    if retired:
        return f"{rid} was retired as not the owner's words", "quote the owner's own words"
    if later:
        stored = baseline is not None and revision is None and any(_added(cfg, baseline, other) for other in later)
        return (f'{rid} is superseded by {", ".join(later)}' + (' (stored in this task)' if stored else ''),
                f"update it from {later[0]}'s words")
    if raw is None:
        return f'{rid} was not stored then', f"store the owner's words with python -m flowguard req add - --id {rid}"
    if quote is not None and not matches(raw, quote):
        return f'"{_short(quote)}" is not in {rid}', 'quote the stored words exactly'
    return None


def _doc_problem(cfg, path, quote, matches, revision):
    """(what is wrong, the step) of a cited document now or at a commit, or None."""
    if not path or path.startswith('/') or '\\' in path or any(part in ('', '.', '..') for part in path.split('/')):
        return f'doc {path} is not a path relative to the repository', 'cite a document of this repository by its path'
    if not any(fnmatch.fnmatch(path, pattern) for pattern in _authority_docs(cfg, revision)):
        return (f'{path} is not in authority_docs',
                'list it in [tool.flowguard] authority_docs of pyproject.toml, or cite a listed document')
    raw = _bytes_at(cfg, revision, path)
    if raw is None:
        return f'{path} is gone', 'restore it, or cite the document that holds the words'
    if not matches(raw, quote):
        return f'{path} does not contain "{_short(quote)}"', 'quote the document exactly'
    return None


def _legacy_match(raw, words):
    return quote_matches(raw.decode('utf-8-sig'), words)


def _problem(src, cfg, archive, *, revision=None, baseline=None, quote=None):
    """(what is wrong, the step) of a source now (`revision` None) or at a commit, None when it holds: `rule.<id>` by
    its rules.toml entry at the same commit, a request or document by its bytes there. Strict sources compare their
    words exactly (`exact_quote`); the intent forms `owner` (with the rule's `quote`) and `doc` keep `quote_matches`."""
    matches = exact_quote if src.strict else _legacy_match
    if src.kind == 'rule':
        found = catalog(cfg, revision)
        entry = found.rules.get(src.rule)
        if entry is None:
            invalid = any(issue.name in (f'rules-entry:rule.{src.rule}', f'rules-file:{RULES}') for issue in found.issues)
            return ((f'rule.{src.rule} is an invalid entry of {RULES}', f'python -m flowguard show rule.{src.rule}') if invalid
                    else (f'rule.{src.rule} is not in {RULES}', f'add [rule.{src.rule}] to {RULES}, or cite a rule it has'))
        problem = _problem(parse(entry.source, strict=True), cfg, archive, revision=revision, baseline=baseline)
        return None if problem is None else (f'rule.{src.rule}: {problem[0]}', problem[1])
    if src.kind in ('owner', 'request'):
        return _request_problem(cfg, archive, src.rids[0], src.quote if src.kind == 'request' else quote, matches,
                                revision, baseline)
    if src.kind == 'doc':
        return _doc_problem(cfg, src.path, src.quote, matches, revision)
    raise ValueError(f'an {src.kind}: source is confirmed by a request, never judged by its own words')


def catalog_authority(src, cfg, archive, *, revision=None, baseline=None):
    """(valid, reason) of a strict source (`R74 "words"`, `doc PATH "words"` of the catalog, `rule.<id>`), now or at
    the commit `revision`: the request is stored, neither retired nor superseded, and holds the words exactly after
    `normalize_newlines`; the document is listed in that commit's `authority_docs` and holds them; `rule.<id>` is a
    valid rule of that commit's rules.toml whose own source holds. No permissive comparison follows a strict miss."""
    problem = _problem(src, cfg, shared_archive(cfg.root) if archive is None else archive, revision=revision, baseline=baseline)
    if problem is not None:
        return False, f'{problem[0]} -> {problem[1]}'
    return True, (f'rule.{src.rule}' if src.kind == 'rule' else f'owner {src.rids[0]}' if src.kind == 'request'
                  else f'doc {src.path}')


def cited(src, cfg, found=None):
    """The source whose words a rule's lines quote: for `rule.<id>` its rules.toml entry's source (the rule source
    itself while the entry is missing or invalid, so the line names rule.<id>); any other source is its own. `found`
    is the working tree's catalog when the caller already read it (one session reads it once)."""
    if src.kind != 'rule':
        return src
    entry = (catalog(cfg) if found is None else found).rules.get(src.rule)
    return src if entry is None else parse(entry.source, strict=True)


def _declarations_at(cfg, revision):
    """The intent declarations of a commit, by id, as the static scan reads them (`cache.scan` over that commit's
    intent files; no code runs)."""
    from .cache import scan
    from .history import _texts
    return _held(cfg, revision, 'intent', lambda: scan(cfg, _texts(cfg, revision, cfg.rel(cfg.intent)))['rules'])


def source_state(engine, declaration, confirmed=None, quote=None, *, gone_red=True):
    """(state, reason) of an intent declaration's source for the engine's verdict: 'ok'; 'grey' for a source that
    cannot be confirmed (a missing request, an unlisted document, an assumption, ...); 'red' when this change broke it;
    'before' when the same citation (the declaration's source and quote unchanged) already failed at the session's
    baseline (`engine.baseline`), judged with that commit's archive, documents and authority_docs (design 4.7, D28).
    Judged so are every failure of a strict source (`rule.<id>`, `R74 "words"`) and a quote gone or a request no
    longer current of the forms `owner` and `doc`; a request stored in this task that supersedes or retires the cited
    one makes it red (D27). Without a baseline nothing is compared (D13): a strict source is grey, and the intent
    forms keep their 4.2.1 colours, a gone quote red where `gone_red` (rules and flows; 4.2.1 left the source of states
    and structure rules grey) and the rest grey."""
    cfg = engine.m.cfg
    src = parse(declaration.source)
    valid, reason = authority(src, confirmed, cfg, engine.archive, quote)
    if valid:
        return 'ok', reason
    judged = src.strict or src.kind in ('owner', 'doc') and ('quote gone' in reason or 'no longer current' in reason)
    if not judged:
        return 'grey', reason
    if engine.baseline is None:
        return ('red' if gone_red and not src.strict and 'quote gone' in reason else 'grey'), reason
    if src.strict:
        what, step = _problem(src, cfg, engine.archive, baseline=engine.baseline)
        reason = f'{what} -> {step}'
    old = _declarations_at(cfg, engine.baseline).get(declaration.id)
    same = old is not None and old['source'] == declaration.source and old.get('quote') == quote
    if same and _problem(src, cfg, engine.archive, revision=engine.baseline, quote=quote) is not None:
        return 'before', reason
    return 'red', reason


# ---- the catalog's findings for the static checks ---------------------------------------------------------------

LOOSENED_STEP = "name it in your report; needs the owner's yes"
FUNCTION_VALUES = ('arrow_function', 'function_expression', 'function', 'generator_function')


def _declarations(path, data, symbol):
    """The module-level declarations of `symbol` in one TS/JS or Python source (`data`, its bytes) that a site may
    name as a constant, whatever its value (design 4.4), each as a fingerprint an edit of it changes and formatting or
    a comment does not: in TS/JS each `const`, `let` or `var` declarator of that name whose value is no function (a
    function is found on the map as a function site); in Python each assignment to it at the top level, also in an
    `if`, `try` or `with` block there, as the map reads a module's constants. A Python source that does not parse
    raises SyntaxError (the caller asks the map first)."""
    import ast
    from flowguard.map.common import read_source
    from flowguard.map.inventory import syntax_tree
    from ..structure.readers.common import fingerprint, parse, text
    from ..structure.readers.ecma import unwrap
    from ..structure.readers.registry import language_for
    found = []
    if language_for(path) != 'python':
        source, tree = parse(data, language_for(path))
        for statement in tree.root_node.named_children:
            inner = statement.child_by_field_name('declaration') if statement.type == 'export_statement' else statement
            if inner is None or inner.type not in ('lexical_declaration', 'variable_declaration'):
                continue
            for item in inner.named_children:
                name, value = item.child_by_field_name('name'), unwrap(item.child_by_field_name('value'))
                if item.type == 'variable_declarator' and name is not None and name.type == 'identifier' \
                        and text(name, source) == symbol and (value is None or value.type not in FUNCTION_VALUES):
                    found.append(inner.children[0].type + ' ' + fingerprint(item, source))
        return found
    todo = list(reversed(syntax_tree(read_source(Path(path), data=data)).body))
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.If, ast.Try, ast.TryStar, ast.With)):
            todo.extend(reversed([*node.body, *(statement for handler in getattr(node, 'handlers', ()) for statement in handler.body),
                                  *getattr(node, 'orelse', ()), *getattr(node, 'finalbody', ())]))
        elif isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store) and part.id == symbol
                   for target in targets for part in ast.walk(target)):
                found.append(ast.dump(node))
    return found


def _declaration_edited(change, path, symbol, now):
    """Whether this change edits the one declaration of constant `symbol` in `path` (fingerprint `now`): the file
    is new, its baseline did not parse, or its baseline declarations of that name are not just that one."""
    from ..structure.readers.registry import language_for
    if change is None or not change.baseline or path not in change.files:
        return False
    old = {new: old for old, new in change.renamed().items()}.get(path, path)
    data = change.graph._baseline_bytes(change.baseline, old)
    if data is None or language_for(old) == 'python' and change.old_facts(old).get('parse_error'):
        return True
    return _declarations(old, data, symbol) != [now]


def known_sites(graph, entries, change=None):
    """(entries, input findings): the known entries with their sites resolved on the map, and one input finding per
    entry with a site that names no single function, method, object.method, constant or Model.field of its file (that
    entry is left out). A Model.field is a field of a schema model (Prisma, SQL) of that file, or of a class the file
    declares that the map binds writes to (a Python class written as `order.status = ...`). A constant is any
    module-level declaration of a TS/JS or Python file (`_declarations`), whatever its value, or a constant node of
    the map. `Known.nodes` holds the node of each function, method or constant site the map keeps a node for and, for
    a Model.field site, the functions that write that field now and (with `change`) at its baseline; `Known.files` the
    schema or class file of each Model.field site, the file of each other constant site whose declaration this
    change edits, and the file of each function or method site whose text this change edits although its code is
    the same (a comment or blank line inside it: `Change.edited`) (D31: a site is touched when its node changes, or
    that file changes)."""
    from .anchors import _agreement_positions
    from .owners import row_function
    from ..structure.readers.registry import ECMA, language_for
    entries = list(entries)
    if not entries:
        return [], []
    modules, errors = {}, {}
    for path, module, error in graph.con.execute('SELECT path, module, parse_error FROM file'):
        modules[path], errors[path] = module, error
    positions = _agreement_positions(graph, modules)
    schemas = {}
    for schema in graph.schemas():
        schemas.setdefault(schema['file'], []).append(schema)
    written = {}            # Model.field -> its write rows now, all read once (`graph.writes_to`)
    def writes(symbol):
        if symbol not in written:
            if not written:
                written[None] = graph.writes()
            written[symbol] = graph.writes_to(written[None], symbol)
        return written[symbol]
    resolved, issues = [], []
    for entry in entries:
        nodes, files, problems = set(), set(), []
        for site in entry.sites:
            path, _, symbol = site.rpartition(':')
            module = modules.get(path)
            if module is None:
                problems.append(f'site {site}: the map reads no {path} (excluded, or no source or schema file)')
                continue
            found = list(positions[module].get(symbol, ()))
            mapped = [row[0] for row in graph.con.execute("SELECT id FROM node WHERE module=? AND kind='const' AND qual=?",
                                                          (module, symbol))]
            declared = []
            if '.' in symbol or language_for(path) not in ('python', *ECMA):
                found += mapped
            elif errors[path]:
                problems.append(f'site {site}: {path} does not parse ({errors[path]})')
                continue
            else:
                declared = _declarations(path, (graph.root / path).read_bytes(), symbol)
            model, dot, name = symbol.rpartition('.')
            fields = [symbol for schema in schemas.get(path, ()) for item in schema['models']
                      if dot and item['name'] == model and any(column['name'] == name for column in item['fields'])]
            if dot and not fields and '.' not in model and graph.con.execute(
                    "SELECT 1 FROM node WHERE module=? AND kind='class' AND qual=?", (module, model)).fetchone() \
                    and any(row['model'] == model and row['field'] == name for row in writes(symbol)):
                fields.append(symbol)
            count = len(found) + len(declared) + len(fields)
            if count != 1:
                problems.append(f'site {site} names ' + (f'{count} declarations' if count else 'nothing')
                                + f' in {path}: name one function, object.method, constant or Model.field of that file')
            elif found:
                nodes.update(found)
                if change is not None and change.baseline and path in change.files and any(map(change.edited, found)):
                    files.add(path)
            elif declared:
                if mapped:
                    nodes.update(mapped)
                elif _declaration_edited(change, path, symbol, declared[0]):
                    files.add(path)
            else:
                nodes.update(row_function(row) for row in writes(symbol))
                if change is not None and change.baseline:
                    nodes.update(row_function(row) for row in change.baseline_writes(symbol))
                files.add(path)
        if problems:
            issues.append(_input(f'known-entry:known.{entry.id}', f'known.{entry.id}', f'{KNOWN}:known.{entry.id}', problems,
                                 f'correct the sites of [known.{entry.id}] in {KNOWN}', [KNOWN]))
        else:
            resolved.append(replace(entry, nodes=frozenset(nodes), files=frozenset(files)))
    return resolved, issues


def _cited_file(source):
    return (REQUEST_DIR / (source.rids[0] + '.md')).as_posix() if source.kind == 'request' else source.path


def _source_issue(identifier, file, entry, source, what, step, fresh):
    """The `source:` finding of a catalog entry whose source does not hold; one file-level member, touched when the
    change touches the catalog file or the cited request or document."""
    from .health import Issue
    subject = f'source {identifier}'
    return Issue(f'source:{identifier}', 0, subject, f'{subject}: {what}', step, files=frozenset({file, _cited_file(source)}),
                 new=fresh, family='source', subject=subject, parts=(('', f'{file}:{identifier}', what, step),),
                 fresh=frozenset({''}) if fresh else frozenset(), detail=(f'{identifier} source: {entry.source}',))


def findings(cfg, graph, change):
    """The catalog's findings for `owners.static_findings`: the input findings of rules.toml and known.toml (an
    invalid file or entry, a known site that names no single declaration), one `source:` finding per rule or known
    entry whose source does not hold, and the valid known entries with their sites resolved (`Findings.known`). A
    source finding is new (fresh, so red) unless the same source of the same entry already failed at the baseline,
    judged with that commit's archive, documents and authority_docs (design 4.7: a request stored in this task that
    supersedes or retires the cited one makes it new, D27); without a baseline none is new (D13). What the change
    loosened in the two files (`catalog_loosened`, also when it deleted them) are lines of their kind."""
    from .owners import Findings
    loosened_lines = catalog_loosened(cfg, change)
    if not catalog_files(cfg):
        return Findings(lines=loosened_lines)
    now = catalog(cfg)
    known, unresolved = known_sites(graph, now.known.values(), change)
    found = Findings(issues=[*now.issues, *unresolved], known=known, lines=loosened_lines)
    archive, baseline = shared_archive(cfg.root), change.baseline
    then = catalog(cfg, baseline) if baseline else Catalog()
    words = {(table, entry.id): parse(entry.source, strict=True) for table, entries in (('rule', now.rules), ('known', now.known))
             for entry in entries.values() if entry.source}
    archive.read([source.rids[0] for source in words.values() if source.kind == 'request'])     # one listing for all
    for file, table, entries, before in ((RULES, 'rule', now.rules, then.rules), (KNOWN, 'known', now.known, then.known)):
        for entry in entries.values():
            if not entry.source:
                continue
            source = words[table, entry.id]
            problem = _problem(source, cfg, archive, baseline=baseline)
            if problem is None:
                continue
            old = before.get(entry.id)
            held = (baseline is not None and old is not None and old.source == entry.source
                    and _problem(source, cfg, archive, revision=baseline) is not None)
            found.issues.append(_source_issue(f'{table}.{entry.id}', file, entry, source, *problem,
                                              fresh=baseline is not None and not held))
    return found


def loosened(old, new):
    """The `loosened` lines (signals.Line) of rules.toml and known.toml from the catalog `old` (the baseline's) to
    `new` (D9): a rule removed; a known entry removed, or changed in anything but `asked`; a known entry added with an
    act other than "ask". An entry or file that is invalid now is an input finding instead. A rule's changed text or
    source is not loosened."""
    from .signals import Line
    invalid = {issue.name for issue in new.issues}
    lines = []
    def add(identifier, file, text):
        lines.append(Line('loosened', f'loosened:{identifier}', '', text, LOOSENED_STEP, (f'{file}:{identifier}',)))
    if f'rules-file:{RULES}' not in invalid:
        for identifier in old.rules:
            if identifier not in new.rules and f'rules-entry:rule.{identifier}' not in invalid:
                add(f'rule.{identifier}', RULES, f'rule.{identifier} removed from {RULES}')
    if f'known-file:{KNOWN}' not in invalid:
        for identifier, entry in old.known.items():
            if identifier in new.known:
                changed = [key for key in KNOWN_KEYS if key != 'asked' and getattr(new.known[identifier], key) != getattr(entry, key)]
                if changed:
                    add(f'known.{identifier}', KNOWN, f'known.{identifier} changed ({", ".join(changed)})')
            elif f'known-entry:known.{identifier}' not in invalid:
                add(f'known.{identifier}', KNOWN, f'known.{identifier} removed from {KNOWN}')
        for identifier, entry in new.known.items():
            if identifier not in old.known and entry.act != 'ask':
                add(f'known.{identifier}', KNOWN, f'known.{identifier} added with act = "{entry.act}"')
    return lines


def catalog_loosened(cfg, change):
    """`loosened` of the catalog at the change's baseline against the working tree's: the `loosened` lines a static
    check adds (signals.deliver's `extra`). None without a baseline (nothing is compared) or without either file."""
    if not change.baseline or not (catalog_files(cfg) or any(_bytes_at(cfg, change.baseline, name) is not None
                                                           for name in CATALOG_FILES)):
        return []
    return loosened(catalog(cfg, change.baseline), catalog(cfg))


def citing(cfg):
    """{rule id: ['path:declaration id' of each intent declaration whose source is rule.<id>]}, from the static scan of
    the intent files (no code runs)."""
    from .cache import scan
    found = {}
    for identifier, item in scan(cfg)['rules'].items():
        match = RULE_FORM.fullmatch(item['source'].strip()) if isinstance(item['source'], str) else None
        if match:
            found.setdefault(match[1], []).append(f'{item["file"]}:{identifier}')
    return found
