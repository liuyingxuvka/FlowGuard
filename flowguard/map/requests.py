"""Store owner bytes once and derive request facts without a mutable index."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .common import MapError, git_blob, git_common_directory, git_head, git_run, normalize_newlines, sha256_bytes
from .records import (NO_ORIGINAL_FACT, Unverifiable, integrity_problem, prepare_directory, protected_paths, restore_advice,
                      validate_new_files, write_once, read_original_bytes)

REQUEST_DIR = Path('.flowguard/requests')
RETIRED_DIR = REQUEST_DIR / 'retired'
REQUEST_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]*\Z')
KINDS = ('request', 'glossary', 'adoption')
RETIRE_FIELDS = {'id', 'kind', 'not_owner', 'request_sha256', 'retired'}


def glossary_entries(raw: bytes) -> list[tuple[str, tuple[str, ...]]]:
    """Parse the owner's confirmed word mappings; never rewrite their text."""
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError as error:
        raise MapError('glossary_syntax: glossary text must be UTF-8') from error
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        word, separator, terms = line.partition('=')
        identifiers = tuple(value.strip() for value in terms.split(','))
        if (not separator or not word.strip() or not identifiers
                or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', term) for term in identifiers)):
            raise MapError(f'glossary_syntax: line {number}: expected owner word = term, term')
        entries.append((word.strip(), identifiers))
    if not entries:
        raise MapError('glossary_syntax: name at least one owner word = term')
    return entries


# flowguard: event REQUEST_STORE(root: Path, raw: bytes, identifier: str | None, kind: str, supersedes: tuple | list)
def store_request(root: Path, raw: bytes, *, identifier: str | None = None, kind: str = 'request',
                  supersedes: tuple | list = ()) -> dict:
    root = Path(root).resolve()
    if not raw:
        raise MapError('request_empty: no owner words received; pass a nonempty file or pipe the request text to stdin')
    if kind not in KINDS:
        raise MapError('request_kind_invalid: expected request, glossary or adoption')
    supersedes = list(dict.fromkeys(supersedes))
    validate_request_links(root, [dict(id=value, part=False) for value in supersedes])
    if kind == 'glossary':
        glossary_entries(raw)
    received = datetime.now(timezone.utc).isoformat()
    digest = sha256_bytes(raw)
    directory = root / REQUEST_DIR
    existing = set(_identifiers(root))
    exists = lambda value: value in existing
    if identifier is None:
        prefix = 'R' + received[:10].replace('-', '') + '-'
        identifier = prefix + digest[:4]
        if exists(identifier):
            identifier = prefix + digest[:6]
    if not REQUEST_ID.fullmatch(identifier):
        raise MapError('request_id_invalid: use [A-Za-z][A-Za-z0-9_-]*, for example R9 or Owner_note')
    if exists(identifier):
        raise MapError(f'request_exists: {identifier} is stored; a correction from the owner is a new request')
    item = dict(id=identifier, kind=kind, sha256=digest, received=received, bytes=len(raw))
    if supersedes:
        item['supersedes'] = supersedes
    prepare_directory(root, REQUEST_DIR, ('.md', '.json'))
    body = REQUEST_DIR / (identifier + '.md')
    sidecar = body.with_suffix('.json')
    metadata = (json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    validate_new_files(root, (body, sidecar))
    write_once(root, body, raw)
    write_once(root, sidecar, metadata)
    return item


# flowguard: sensor REQUEST_BODY(root: Path, identifier: str) -> body: bytes
def read_request_bytes(root: Path, identifier: str) -> bytes:
    """Read the actual request body, keeping its identity separate from the sidecar."""
    return read_original_bytes(root, REQUEST_DIR / (identifier + '.md'))


# flowguard: sensor REQUEST_METADATA(path: Path, identifier: str) -> metadata: dict
def _metadata(path: Path, identifier: str) -> dict:
    """The one sidecar validator: any malformed sidecar is a ValueError."""
    item = json.loads(path.read_bytes())
    if (not isinstance(item, dict) or item.get('id') != identifier
            or not REQUEST_ID.fullmatch(identifier) or item.get('kind') not in KINDS
            or not re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256', '')))
            or type(item.get('bytes')) is not int or item['bytes'] < 0
            or not isinstance(item.get('received'), str)):
        raise ValueError('invalid request sidecar fields')
    received = datetime.fromisoformat(item['received'])
    if received.tzinfo is None or received.utcoffset().total_seconds() != 0:
        raise ValueError('received must be UTC')
    supersedes = item.get('supersedes', [])
    if not isinstance(supersedes, list) or any(not isinstance(value, str) or not REQUEST_ID.fullmatch(value)
                                               for value in supersedes):
        raise ValueError('supersedes must list request IDs')
    return item


def _stems(root: Path, directory: Path) -> list[str]:
    """Record names directly inside one directory, on disk or protected."""
    paths = {path for suffix in ('*.md', '*.json') for path in (root / directory).glob(suffix)}
    paths.update(Path(path) for path in protected_paths(root, directory)
                 if Path(path).suffix in {'.md', '.json'} and Path(path).parent == directory)
    return sorted({path.stem for path in paths})


def _identifiers(root: Path) -> list[str]:
    return _stems(root, REQUEST_DIR)


def _retire_record(root: Path, identifier: str) -> dict:
    """A retire record whose bytes are protected and whose sha names the request it retires.

    A request sidecar that cannot be read, or that was edited since it was stored, is that sidecar's own
    finding (request_meta_edited), never an edit of this record: the link is checked only against a
    readable sidecar, and a mismatch blames this record only when the sidecar's own bytes hold."""
    relative = RETIRED_DIR / (identifier + '.json')
    problem = integrity_problem(root, relative)
    if problem:
        raise ValueError(problem)
    item = json.loads((root / relative).read_bytes())
    if (not isinstance(item, dict) or not RETIRE_FIELDS <= set(item) or set(item) - RETIRE_FIELDS - {'note'}
            or item['id'] != identifier or item['kind'] != 'retired' or item['not_owner'] is not True
            or not isinstance(item.get('note', ''), str)):
        raise ValueError('invalid retire record fields')
    sidecar_path = REQUEST_DIR / (identifier + '.json')
    try:
        sidecar = _metadata(root / sidecar_path, identifier)
    except (OSError, ValueError):
        return item  # the sidecar's own finding names it
    if item['request_sha256'] != sidecar['sha256']:
        try:
            if integrity_problem(root, sidecar_path):
                return item  # the sidecar was edited: its own finding names it
        except Unverifiable:
            pass  # which side changed is unknown here
        raise ValueError(f'it names other bytes than {identifier}')
    return item


def _missing_record(path: Path, relative: Path):
    """What stands where a retire record should be when no regular file is there; None when one is."""
    name = relative.as_posix()
    if path.is_file():
        return None
    if path.is_symlink():
        return (f"is missing: {name} is a symbolic link to {os.readlink(path)}"
                + ("" if path.exists() else ", which does not exist"))
    if path.is_dir():
        return f"is missing: a directory stands at {name}"
    if os.path.lexists(path):
        return f"is missing: {name} is not a regular file"
    return f"is missing: {name} was deleted"


def _retire_states(root: Path, *, identifiers=None) -> dict:
    """(kind, problem) of every retire record: the one check behind status and map check.

    kind is None (verified here), 'unverified', 'missing', 'unreadable' or 'edited'."""
    states = {}
    for identifier in _stems(root, RETIRED_DIR):
        if identifiers is not None and identifier not in identifiers:
            continue
        relative = RETIRED_DIR / (identifier + '.json')
        missing = _missing_record(root / relative, relative)
        if missing:
            states[identifier] = ('missing', missing)
            continue
        try:
            _retire_record(root, identifier)
            states[identifier] = (None, None)
        except Unverifiable:
            states[identifier] = ('unverified', "cannot be checked here: " + NO_ORIGINAL_FACT)
        except OSError as error:
            states[identifier] = ('unreadable', f"cannot be read: {error}")
        except ValueError as error:
            states[identifier] = ('edited', f"edited: {error}")
    return states


def retired_requests(root: Path) -> dict:
    """Every retire record as written, by request ID, with its integrity problem (None when verified here).

    A retire record applies for display in every checkout; whether its bytes can be verified is a separate
    fact that owner_words reports in retire_problems."""
    return {identifier: problem for identifier, (_, problem) in _retire_states(Path(root).resolve()).items()}


def retire_request(root: Path, identifier: str, *, note: str | None = None) -> dict:
    """Record once that a stored text is not the owner's words; the stored bytes stay as they are."""
    root = Path(root).resolve()
    relative = RETIRED_DIR / (identifier + '.json')
    if identifier in _stems(root, RETIRED_DIR):
        raise MapError(f'request_retired: {identifier} is already retired ({relative.as_posix()})')
    validate_request_links(root, [dict(id=identifier, part=False)])
    sidecar = _metadata(root / REQUEST_DIR / (identifier + '.json'), identifier)
    item = dict(id=identifier, kind='retired', not_owner=True, request_sha256=sidecar['sha256'],
                retired=datetime.now(timezone.utc).isoformat())
    if note:
        item['note'] = note
    prepare_directory(root, REQUEST_DIR, ('.md', '.json'))
    raw = (json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    validate_new_files(root, (relative,))
    write_once(root, relative, raw)
    return item


def _request_problems(root: Path, identifier: str, unverified: list):
    """(owner text problem, sidecar problem, sidecar) of one stored request: the one check map check and status use.

    A file with no original-byte fact here is added to `unverified`; the owner text is then still checked
    against its sidecar digest."""
    body = REQUEST_DIR / (identifier + '.md')
    meta = body.with_suffix('.json')
    def problem_of(path):
        try:
            return integrity_problem(root, path)
        except Unverifiable:
            unverified.append(path)
            return None
    body_problem = problem_of(body)
    meta_problem = problem_of(meta)
    try:
        item = _metadata(root / meta, identifier)
    except (OSError, ValueError) as error:
        item = None
        meta_problem = meta_problem or str(error)
    if item is not None and meta_problem is None and (root / body).is_file():
        raw = read_request_bytes(root, identifier)
        if sha256_bytes(raw) != item['sha256'] or len(raw) != item['bytes']:
            body_problem = body_problem or 'bytes differ from the immutable sidecar'
    return body_problem, meta_problem, item




def request_commits(root: Path) -> dict:
    """The one parser for Request trailers, with explicit history and syntax limits."""
    root = Path(root).resolve()
    if git_common_directory(root) is None:
        return dict(commits=[], known=False, unknown=["request commit history unavailable: no Git repository"])
    if git_head(root) is None:
        return dict(commits=[], known=True, unknown=[])
    unknown = []
    if git_run(root, 'rev-parse', '--is-shallow-repository').stdout.strip() == b'true':
        unknown.append('request commit history is shallow; earlier symbol/request links are unknown')
    log = git_run(root, 'log', '--format=%H%x00%P%x00%B%x1e', '-E', '--grep=^Request:')
    commits = []
    for entry in log.stdout.decode('utf-8', errors='replace').split('\x1e'):
        if not entry.strip():
            continue
        commit, parents, body = entry.strip('\n').split('\0', 2)
        requests = []
        for line in body.splitlines():
            if not line.startswith('Request:'):
                continue
            identifiers = re.split(r'[,\s]+', line[len('Request:'):].strip())
            if not identifiers or any(not REQUEST_ID.fullmatch(value) for value in identifiers):
                unknown.append(f'commit {commit[:12]} has malformed Request: line: {line}')
                continue
            requests.extend(identifiers)
        commits.append(dict(commit=commit, parents=parents.split(), requests=list(dict.fromkeys(requests))))
    return dict(commits=commits, known=True, unknown=unknown)


def request_citations(root: Path) -> tuple[dict, bool]:
    """Live citation facts come from the one Request trailer parser."""
    cited = {}
    history = request_commits(root)
    for entry in history['commits']:
        for identifier in entry['requests']:
            cited.setdefault(identifier, []).append('commit ' + entry['commit'][:7])
    return cited, history['known']


def _readable(path: Path) -> bool:
    try:
        path.read_bytes()
    except OSError:
        return False
    return True


def _owner_row(root, identifier, retired, cited, common):
    # A retire record applies as written, whatever the state of the request files it hides. Every
    # request's files, retired or not, are checked against their original bytes; edited text is never shown.
    edited, invalid, item = _request_problems(root, identifier, [])
    intact = invalid is None and edited is None
    text = read_request_bytes(root, identifier).decode('utf-8-sig', errors='replace').splitlines() if intact else []
    if invalid is not None:
        # A sidecar whose bytes can be read but are not the stored ones was edited; only a sidecar that
        # cannot be read is unreadable. Either way none of its fields are trusted or shown.
        files = [(REQUEST_DIR / (identifier + suffix)).as_posix() for suffix in ('.md', '.json')]
        problem = f'{invalid}; {restore_advice(root, files, common)}'
        readable = item is not None or _readable(root / REQUEST_DIR / (identifier + '.json'))
        return dict(id=identifier, kind=None, received='', first_line='', extra_lines=0, supersedes=[],
                    superseded_by=[], retired=identifier in retired, cited_by=[],
                    edited=problem if readable else None, invalid=None if readable else problem)
    if edited is not None:
        edited = f"{edited}; {restore_advice(root, [(REQUEST_DIR / (identifier + '.md')).as_posix()], common)}"
    return dict(id=identifier, kind=item['kind'], received=item['received'],
                first_line=text[0] if text else '', extra_lines=max(0, len(text) - 1),
                supersedes=item.get('supersedes', []), superseded_by=[],
                retired=identifier in retired, cited_by=cited.get(identifier, []), edited=edited, invalid=None)


def owner_word(root: Path, identifier: str) -> dict | None:
    """One on-disk request's display facts; archive links remain in owner_words."""
    root = Path(root).resolve()
    if not REQUEST_ID.fullmatch(identifier) or not (root / REQUEST_DIR / (identifier + '.md')).is_file():
        return None
    retired = _retire_states(root, identifiers={identifier})
    return _owner_row(root, identifier, retired, {}, git_common_directory(root))


def request_state(root: Path, identifier: str) -> dict | None:
    """owner_words' row for one stored request (None when there is none), checking only that request's
    files and the requests whose sidecar may name it as superseded, not every stored request.
    `cited_by` is not read here (it is history, not a state)."""
    return request_states(root, [identifier])[identifier]


def request_states(root: Path, identifiers) -> dict:
    """`request_state` of each identifier ({id: row, or None when it is not stored}), the archive's listing, its
    retire records and each sidecar read once for all of them: every row a source check cites costs that
    request's own files, not another listing of the archive."""
    root = Path(root).resolve()
    stored = _identifiers(root)
    states = dict.fromkeys(identifiers)
    wanted = [identifier for identifier in states if identifier in stored]
    if not wanted:
        return states
    common = git_common_directory(root)
    retired = set(_stems(root, RETIRED_DIR))
    rows = {identifier: _owner_row(root, identifier, {identifier: None} if identifier in retired else {}, {}, common)
            for identifier in wanted}
    for other in stored:
        meta = root / REQUEST_DIR / (other + '.json')
        if not meta.is_file() or not _readable(meta):
            continue        # without a readable sidecar its row is invalid and supersedes nothing
        raw = meta.read_bytes()
        # Only a sidecar that spells an id (even escaped) can list it.
        named = [identifier for identifier in wanted if identifier.encode() in raw or b'\\u' in raw]
        if not named:
            continue
        supersedes = (rows[other] if other in rows else _owner_row(root, other, {}, {}, common))['supersedes']
        for identifier in named:
            if identifier in supersedes:
                rows[identifier]['superseded_by'].append(other)
    states.update(rows)
    return states


def owner_words(root: Path) -> dict:
    """Stored owner words, newest first, with supersession, retirement and citations; never a to-do state.

    Each integrity problem carries its restore step, in any source project."""
    root = Path(root).resolve()
    retired = retired_requests(root)
    common = git_common_directory(root)
    cited, commits_known = request_citations(root)
    rows = [_owner_row(root, identifier, retired, cited, common) for identifier in _identifiers(root)]
    by_id = {row['id']: row for row in rows}
    for row in rows:
        for old in row['supersedes']:
            if old in by_id:
                by_id[old]['superseded_by'].append(row['id'])
    rows.sort(key=lambda row: (row['received'], row['id']), reverse=True)
    problems = {identifier: problem if problem.startswith('cannot be checked here') else
                f"{problem}; {restore_advice(root, [(RETIRED_DIR / (identifier + '.json')).as_posix()], common)}"
                for identifier, problem in retired.items() if problem is not None}
    return dict(rows=rows, commit_links_known=commits_known, retire_problems=problems)




def validate_request_links(root: Path, links) -> None:
    """Require real stored owner bytes, not just a syntactically valid target id."""
    import shlex

    root = Path(root).resolve()
    for link in links:
        identifier = link['id']
        if not REQUEST_ID.fullmatch(identifier):
            raise MapError(f'request_link_invalid: {identifier!r}; use a stored request ID')
        body = REQUEST_DIR / (identifier + '.md')
        meta = body.with_suffix('.json')
        if not (root / body).is_file() or not (root / meta).is_file():
            command = shlex.join(['python', '-m', 'flowguard', 'req', 'add', '<owner-file>',
                                  '--id', identifier, '--root', str(root)])
            raise MapError(f'request_unknown: {identifier} is not stored; store it first: {command}')
        retired = RETIRED_DIR / (identifier + '.json')
        if identifier in _stems(root, RETIRED_DIR):
            raise MapError(f"request_retired: {identifier} was retired as not the owner's words ({retired.as_posix()}); "
                           "quote or link the owner's own words")
        for path, code in ((body, 'owner_text_edited'), (meta, 'request_meta_edited')):
            try:
                problem = integrity_problem(root, path)
            except Unverifiable as error:
                raise MapError(f'request_unverifiable: {identifier}: {error}; link or quote it in a checkout that '
                               'holds one') from error
            if problem:
                raise MapError(f'{code}: {problem}')
        try:
            item = _metadata(root / meta, identifier)
            raw = read_request_bytes(root, identifier)
            if sha256_bytes(raw) != item['sha256'] or len(raw) != item['bytes']:
                raise ValueError('owner bytes differ from the sidecar')
        except ValueError as error:
            raise MapError(f'request_meta_edited: {identifier}: {error}') from error


# flowguard: sensor QUOTE_MATCH(text: words, quote: words) -> matched: bool calibrated_by=tests/test_anchor_self_rules.py::test_quote_anchor_case[EXACT]
def quote_matches(text: str, quote: str) -> bool:
    """Compare owner words exactly, permitting only whitespace runs and ... elision."""
    source = ' '.join(text.split())
    position = 0
    fragments = [fragment for fragment in quote.split('...') if fragment.strip()]
    if not fragments:
        return False
    for fragment in fragments:
        fragment = ' '.join(fragment.split())
        found = source.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return bool(quote.strip())


def exact_quote(raw: bytes, quote: str) -> bool:
    """The strict quote of `.flowguard/rules.toml` and `.flowguard/known.toml`: `quote` occurs in `raw` exactly,
    after only CRLF and CR become LF on both sides (`normalize_newlines`). No whitespace is folded and `...` is three
    dots, not an elision; an empty quote matches nothing."""
    words = normalize_newlines(quote.encode('utf-8')).decode('utf-8')
    return bool(words) and words in normalize_newlines(raw).decode('utf-8-sig')


def added_since(root: Path, baseline: str, identifier: str) -> bool:
    """Whether the request `identifier` was stored after `baseline`: its sidecar is not in that commit. Requests are
    only ever added, so a request that supersedes another and was stored in this task is exactly this case. Its fields
    are read by the one sidecar validator (`request_state`), never here."""
    return git_blob(root, baseline, (REQUEST_DIR / (identifier + '.json')).as_posix()) is None
