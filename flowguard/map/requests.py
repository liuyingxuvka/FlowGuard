"""Store owner bytes once and derive request facts without a mutable index."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .common import (MapError, decode_text, document_text, git_blob, git_common_directory, git_head, git_run,
                     normalize_newlines, sha256_bytes)
from .records import (NO_ORIGINAL_FACT, Unverifiable, integrity_problem, prepare_directory, protected_paths, restore_advice,
                      validate_new_files, write_once, read_original_bytes)

REQUEST_DIR = Path('.flowguard/requests')
RETIRED_DIR = REQUEST_DIR / 'retired'
OFFER_DIR = REQUEST_DIR / 'offers'      # a choice's offered options: the agent's words, never listed as a request
REQUEST_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]*\Z')
# Every stored kind: a FlowGuard before 5.0 also stored glossary and adoption records, which stay part of the archive
# and keep loading; 5.0 stores requests (`store_request`) and, since 5.1, the owner's pick among options the agent
# offered (`store_choice`, kind `choice`).
KINDS = ('request', 'glossary', 'adoption', 'choice')
CHOICE_FIELDS = ('offer', 'picked', 'reply')        # a choice's own sidecar fields; no other kind has one of them
REPLIES = ('typed', 'selected')     # the owner typed his reply, or picked an option with no words of his own
RETIRE_FIELDS = {'id', 'kind', 'not_owner', 'request_sha256', 'retired'}


# flowguard: event REQUEST_STORE(root: Path, raw: bytes, identifier: str | None, supersedes: tuple | list)
def store_request(root: Path, raw: bytes, *, identifier: str | None = None, supersedes: tuple | list = ()) -> dict:
    """Store the owner's words `raw` once, byte for byte, as a request record (kind `request`)."""
    return _store(root, raw, identifier, supersedes)


def offer_path(identifier: str) -> Path:
    """Where a choice keeps the options the agent offered (`.flowguard/requests/offers/<id>.md`)."""
    return OFFER_DIR / (identifier + '.md')


def _occurrences(text: str, part: str) -> int:
    """How often `part` occurs in `text`, overlapping occurrences counted."""
    count, at = 0, text.find(part)
    while at >= 0:
        count, at = count + 1, text.find(part, at + 1)
    return count


def store_choice(root: Path, reply: bytes, offer: bytes, picked: tuple | list, *, identifier: str | None = None,
                 selected: bool = False, supersedes: tuple | list = ()) -> dict:
    """Store the owner's pick among options the agent offered, once, byte for byte (kind `choice`): `reply` is his
    answer as it reached the agent (with `selected`, the answer an interface returned for a pick he did not type),
    `offer` the exact text the agent showed him, the agent's words, kept apart in `offers/<id>.md`, and `picked` the
    whole text of each option he picked as the offer spells it, each occurring exactly once in it (compared after
    `normalize_newlines`). The mapping from his reply to an option is the agent's statement; it is stored beside the
    reply, never as his words."""
    if not offer:
        raise MapError('choice_offer_empty: the offer is empty; pass the exact question and options the owner saw, '
                       'byte for byte')
    shown, problem = document_text('the offer', offer)
    if problem:
        raise MapError(f'choice_offer_unreadable: {problem}')
    text = normalize_newlines(shown[0].encode('utf-8')).decode('utf-8')
    picked = list(picked)
    if not picked:
        raise MapError('choice_picked_missing: name the option the owner picked with --picked TEXT, its whole text as '
                       'the offer spells it (once for each option he picked)')
    for number, option in enumerate(picked):
        if not isinstance(option, str) or not option.strip():
            raise MapError(f'choice_picked_empty: a picked option is its text, not {option!r}')
        if option in picked[:number]:
            raise MapError(f'choice_picked_repeated: {json.dumps(option, ensure_ascii=False)} is named twice')
        count = _occurrences(text, normalize_newlines(option.encode('utf-8')).decode('utf-8'))
        if count != 1:
            raise MapError(f'choice_picked_{"absent" if count == 0 else "ambiguous"}: '
                           f'{json.dumps(option, ensure_ascii=False)} occurs {count} times in the offer; pass the whole '
                           'text of the picked option, as the offer spells it, so that it occurs exactly once')
    fields = dict(offer=dict(sha256=sha256_bytes(offer), bytes=len(offer)), picked=picked,
                  reply='selected' if selected else 'typed')
    return _store(root, reply, identifier, supersedes, choice=(fields, offer))


def _store(root, raw, identifier, supersedes, *, choice=None):
    """Write one record once: the owner's bytes, a choice's offer (`choice` = (its sidecar fields, the offer's bytes)),
    then the sidecar, each with its first-write receipt; nothing is written when one of them could not be."""
    root = Path(root).resolve()
    if not raw:
        raise MapError('request_empty: no owner words received; pass a nonempty file or pipe the request text to stdin')
    supersedes = list(dict.fromkeys(supersedes))
    validate_request_links(root, [dict(id=value, part=False) for value in supersedes])
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
    item = dict(id=identifier, kind='request' if choice is None else 'choice', sha256=digest, received=received,
                bytes=len(raw), **(choice[0] if choice else {}))
    if supersedes:
        item['supersedes'] = supersedes
    prepare_directory(root, REQUEST_DIR, ('.md', '.json'))      # its `*.md -text` also guards offers/
    body = REQUEST_DIR / (identifier + '.md')
    sidecar = body.with_suffix('.json')
    metadata = (json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    validate_new_files(root, (body, sidecar, *([offer_path(identifier)] if choice else [])))
    write_once(root, body, raw)
    if choice:
        write_once(root, offer_path(identifier), choice[1])
    write_once(root, sidecar, metadata)
    return item


def read_offer_bytes(root: Path, identifier: str) -> bytes:
    """The options the agent offered for the choice `identifier`, as stored."""
    return read_original_bytes(root, offer_path(identifier))


# flowguard: same REQUEST_BODY(root: Path, identifier: str) -> body: bytes
def read_request_bytes(root: Path, identifier: str) -> bytes:
    """Read the actual request body, keeping its identity separate from the sidecar."""
    return read_original_bytes(root, REQUEST_DIR / (identifier + '.md'))


# flowguard: same REQUEST_METADATA(path: Path, identifier: str) -> metadata: dict
def _metadata(path: Path, identifier: str) -> dict:
    """The one sidecar validator: any malformed sidecar is a ValueError."""
    return sidecar_fields(path.read_bytes(), identifier)


def sidecar_fields(raw: bytes, identifier: str) -> dict:
    """The fields of a sidecar's bytes (`_metadata`; a commit's sidecar too): any malformed sidecar is a ValueError. A
    choice needs its offer {sha256, bytes}, its picked option texts and its reply (typed or selected); every other kind
    has none of them."""
    item = json.loads(raw)
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
    present = [key for key in CHOICE_FIELDS if key in item]
    if item['kind'] != 'choice' and present:
        raise ValueError(f'{", ".join(present)} belong to a choice record, not a {item["kind"]}')
    if item['kind'] == 'choice':
        offer, picked = item.get('offer'), item.get('picked')
        if (not isinstance(offer, dict) or set(offer) != {'sha256', 'bytes'}
                or not re.fullmatch(r'[0-9a-f]{64}', str(offer['sha256'])) or type(offer['bytes']) is not int
                or offer['bytes'] < 1 or not isinstance(picked, list) or not picked
                or any(not isinstance(text, str) or not text.strip() for text in picked)
                or item.get('reply') not in REPLIES):
            raise ValueError('a choice has offer {sha256, bytes}, picked [option texts] and reply typed or selected')
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
    """(owner text problem, sidecar problem, sidecar, offer problem) of one stored request: the one check map check and
    status use. A choice's offer is checked as its owner text is (original bytes, sidecar digest and size); the offer
    problem is None for every other kind.

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
    offer_problem = None
    if item is not None and meta_problem is None and item['kind'] == 'choice':
        offer = offer_path(identifier)
        offer_problem = problem_of(offer)
        if offer_problem is None and (root / offer).is_file():
            raw = read_offer_bytes(root, identifier)
            if sha256_bytes(raw) != item['offer']['sha256'] or len(raw) != item['offer']['bytes']:
                offer_problem = 'bytes differ from the immutable sidecar'
    return body_problem, meta_problem, item, offer_problem




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
    edited, invalid, item, offer = _request_problems(root, identifier, [])
    intact = invalid is None and edited is None and offer is None
    text = read_request_bytes(root, identifier).decode('utf-8-sig', errors='replace').splitlines() if intact else []
    if invalid is not None:
        # A sidecar whose bytes can be read but are not the stored ones was edited; only a sidecar that
        # cannot be read is unreadable. Either way none of its fields are trusted or shown.
        files = [(REQUEST_DIR / (identifier + suffix)).as_posix() for suffix in ('.md', '.json')]
        problem = f'{invalid}; {restore_advice(root, files, common)}'
        readable = item is not None or _readable(root / REQUEST_DIR / (identifier + '.json'))
        return dict(id=identifier, kind=None, received='', first_line='', extra_lines=0, supersedes=[],
                    superseded_by=[], retired=identifier in retired, cited_by=[],
                    edited=problem if readable else None, invalid=None if readable else problem,
                    offer='', picked=[], reply='', offer_edited=False)
    offer_edited = edited is None and offer is not None
    if edited is not None:
        edited = f"{edited}; {restore_advice(root, [(REQUEST_DIR / (identifier + '.md')).as_posix()], common)}"
    elif offer_edited:
        # The options the agent offered are part of the record: an edited offer makes the whole record unverified.
        edited = (f"offer of {identifier} differs from its stored original ({offer}); "
                  f"{restore_advice(root, [offer_path(identifier).as_posix()], common)}")
    choice = item['kind'] == 'choice'
    return dict(id=identifier, kind=item['kind'], received=item['received'],
                first_line=text[0] if text else '', extra_lines=max(0, len(text) - 1),
                supersedes=item.get('supersedes', []), superseded_by=[],
                retired=identifier in retired, cited_by=cited.get(identifier, []), edited=edited, invalid=None,
                offer=offer_path(identifier).as_posix() if choice else '', picked=list(item['picked']) if choice else [],
                reply=item['reply'] if choice else '', offer_edited=offer_edited)


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
        if item['kind'] == 'choice':        # its offer, as its owner text: original bytes, sidecar digest and size
            offer = offer_path(identifier)
            try:
                problem = integrity_problem(root, offer)
            except Unverifiable as error:
                raise MapError(f'request_unverifiable: {identifier}: {error}; link or quote it in a checkout that '
                               'holds one') from error
            if problem:
                raise MapError(f'offer_edited: offer of {identifier} differs from its stored original: {problem}')
            raw = read_offer_bytes(root, identifier)
            if sha256_bytes(raw) != item['offer']['sha256'] or len(raw) != item['offer']['bytes']:
                raise MapError(f'offer_edited: offer of {identifier} differs from its sidecar')


# flowguard: same QUOTE_MATCH(text: words, quote: words) -> matched: bool calibrated_by=tests/test_anchor_self_rules.py::test_quote_anchor_case[EXACT]
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
    dots, not an elision; an empty quote matches nothing. The bytes are read as every project document is
    (`decode_text`: UTF-8, or UTF-8 or UTF-16 by their BOM, which is no word); bytes that are no such text raise
    UnicodeDecodeError, so a caller that reads a document checks it first (`document_text`)."""
    words = normalize_newlines(quote.encode('utf-8')).decode('utf-8')
    return bool(words) and words in normalize_newlines(decode_text(raw)[0].encode('utf-8')).decode('utf-8')


def added_since(root: Path, baseline: str, identifier: str) -> bool:
    """Whether the request `identifier` was stored after `baseline`: its sidecar is not in that commit. Requests are
    only ever added, so a request that supersedes another and was stored in this task is exactly this case. Its fields
    are read by the one sidecar validator (`request_state`), never here."""
    return git_blob(root, baseline, (REQUEST_DIR / (identifier + '.json')).as_posix()) is None
