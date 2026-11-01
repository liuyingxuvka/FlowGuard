"""Store owner bytes once and derive request facts without a mutable index."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .common import Finding, git_common_directory, git_head, git_run, sha256_bytes
from .mapfile import MapError
from .records import (NO_ORIGINAL_FACT, Unverifiable, integrity_problem, prepare_directory, protected_paths, restore_advice,
                      validate_new_files, write_once)

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


def _stored_during(root: Path):
    directory = root / '.flowguard/target'
    if not directory.is_dir():
        return None
    try:
        target = json.loads((directory / 'map.json').read_text(encoding='utf-8'))
        base = json.loads((directory / 'base.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise MapError('request_target_invalid: repair the open target before storing its context')
    if not isinstance(target, dict) or not isinstance(base, dict):
        raise MapError('request_target_invalid: repair the open target before storing its context')
    # Older targets have no historical timestamp. Preserve that unknown fact.
    return {'goal': target.get('goal', ''), 'started': base.get('started')}


def store_request(root: Path, raw: bytes, *, identifier: str | None = None, kind: str = 'request',
                  supersedes=()) -> dict:
    root = Path(root).resolve()
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
    context = _stored_during(root)
    if context is not None:
        item['stored_during'] = context
    prepare_directory(root, REQUEST_DIR, ('.md', '.json'))
    body = REQUEST_DIR / (identifier + '.md')
    sidecar = body.with_suffix('.json')
    metadata = (json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    validate_new_files(root, (body, sidecar))
    write_once(root, body, raw)
    write_once(root, sidecar, metadata)
    return item


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
    """A retire record whose bytes are protected and whose sha names the request it retires."""
    relative = RETIRED_DIR / (identifier + '.json')
    problem = integrity_problem(root, relative)
    if problem:
        raise ValueError(problem)
    item = json.loads((root / relative).read_bytes())
    if (not isinstance(item, dict) or not RETIRE_FIELDS <= set(item) or set(item) - RETIRE_FIELDS - {'note'}
            or item['id'] != identifier or item['kind'] != 'retired' or item['not_owner'] is not True
            or not isinstance(item.get('note', ''), str)):
        raise ValueError('invalid retire record fields')
    sidecar = _metadata(root / REQUEST_DIR / (identifier + '.json'), identifier)
    if item['request_sha256'] != sidecar['sha256']:
        raise ValueError(f'it names other bytes than {identifier}')
    return item


def retired_requests(root: Path) -> dict:
    """Every retire record as written, by request ID, with its integrity problem (None when verified here).

    A retire record applies for display in every checkout; whether its bytes can be verified is a separate
    fact that status names and request_findings reports (request_retire_edited, immutable_unverified)."""
    root = Path(root).resolve()
    found = {}
    for identifier in _stems(root, RETIRED_DIR):
        try:
            _retire_record(root, identifier)
            found[identifier] = None
        except Unverifiable:
            found[identifier] = "cannot be checked here: " + NO_ORIGINAL_FACT
        except OSError as error:
            found[identifier] = f"cannot be read: {error}"
        except ValueError as error:
            found[identifier] = f"edited: {error}"
    return found


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


def request_findings(root: Path) -> list[Finding]:
    """Integrity is a fresh byte comparison, including before the first commit."""
    root = Path(root).resolve()
    common = git_common_directory(root)
    findings = []
    unverified = []
    def problem_of(path):
        try:
            return integrity_problem(root, path)
        except Unverifiable:
            unverified.append(path)
            return None
    for identifier in _identifiers(root):
        body = REQUEST_DIR / (identifier + '.md')
        meta = body.with_suffix('.json')
        body_problem = problem_of(body)
        meta_problem = problem_of(meta)
        try:
            item = _metadata(root / meta, identifier)
        except (OSError, ValueError) as error:
            item = None
            meta_problem = meta_problem or str(error)
        if item is not None and meta_problem is None and (root / body).is_file():
            raw = (root / body).read_bytes()
            if sha256_bytes(raw) != item['sha256'] or len(raw) != item['bytes']:
                body_problem = body_problem or 'bytes differ from the immutable sidecar'
        for path, problem, code in ((body, body_problem, 'owner_text_edited'),
                                    (meta, meta_problem, 'request_meta_edited')):
            if problem:
                findings.append(Finding('error', code, identifier,
                    f'{root / path} differs from the stored request: {problem}; '
                    f'{restore_advice(root, [path.as_posix()], common)}; a correction from the owner is a new request'))
    for identifier in _stems(root, RETIRED_DIR):
        path = RETIRED_DIR / (identifier + '.json')
        try:
            _retire_record(root, identifier)
        except Unverifiable:
            unverified.append(path)
        except (OSError, ValueError) as error:
            findings.append(Finding('error', 'request_retire_edited', identifier,
                f'{root / path}: {error}; retire records are written once; '
                f'{restore_advice(root, [path.as_posix()], common)}'))
    if unverified:
        findings.append(Finding('info', 'immutable_unverified', '',
            f'{len(unverified)} request file(s) cannot be checked against their original bytes here '
            f'(first: {unverified[0].as_posix()}): {NO_ORIGINAL_FACT}; owner text is still checked against its '
            'sidecar digest; check the rest in a checkout that holds one'))
    return findings


def request_citations(root: Path, records) -> tuple[dict, bool]:
    """Where owner words are cited: change records, their rules, and `Request: R<n>` commit lines."""
    cited = {}
    for change, record in records:
        for link in record['requests']:
            cited.setdefault(link['id'], []).append('change ' + change)
        for rule in record['rules']:
            provenance = rule.get('provenance') if isinstance(rule, dict) else None
            for part in provenance.split('; ') if isinstance(provenance, str) else ():
                if part.startswith('owner '):
                    cited.setdefault(part[len('owner '):], []).append(f"rule {rule.get('id')} (change {change})")
    if git_common_directory(root) is None:
        return cited, False
    if git_head(root) is None:
        return cited, True  # No commit yet, so no commit cites anything.
    log = git_run(root, 'log', '--format=%h%x00%B%x1e', '-E', '--grep=^Request: ')
    for entry in log.stdout.decode('utf-8', errors='replace').split('\x1e'):
        commit, _, body = entry.strip('\n').partition('\0')
        for line in body.splitlines():
            if line.startswith('Request: '):
                for identifier in re.split(r'[,\s]+', line[len('Request: '):].strip()):
                    if REQUEST_ID.fullmatch(identifier):
                        cited.setdefault(identifier, []).append('commit ' + commit)
    return cited, True


def owner_words(root: Path, *, records=None) -> dict:
    """Stored owner words, newest first, with supersession, retirement and citations; never a to-do state."""
    from .records import change_records

    root = Path(root).resolve()
    retired = retired_requests(root)
    cited, commits_known = request_citations(root, change_records(root) if records is None else records)
    rows = []
    for identifier in _identifiers(root):
        try:
            item = _metadata(root / REQUEST_DIR / (identifier + '.json'), identifier)
            text = (root / REQUEST_DIR / (identifier + '.md')).read_bytes().decode('utf-8-sig', errors='replace').splitlines()
        except (OSError, ValueError):
            rows.append(dict(id=identifier, kind=None, received='', first_line='', extra_lines=0, supersedes=[],
                             superseded_by=[], retired=False, cited_by=[], invalid='run python -m flowguard map check'))
            continue
        rows.append(dict(id=identifier, kind=item['kind'], received=item['received'],
                         first_line=text[0] if text else '', extra_lines=max(0, len(text) - 1),
                         supersedes=item.get('supersedes', []), superseded_by=[],
                         retired=identifier in retired, cited_by=cited.get(identifier, []), invalid=None))
    by_id = {row['id']: row for row in rows}
    for row in rows:
        for old in row['supersedes']:
            if old in by_id:
                by_id[old]['superseded_by'].append(row['id'])
    rows.sort(key=lambda row: (row['received'], row['id']), reverse=True)
    problems = {identifier: problem for identifier, problem in retired.items() if problem is not None}
    return dict(rows=rows, commit_links_known=commits_known, retire_problems=problems)


def request_links(root: Path, values) -> list[dict]:
    """Parse CLI links once; request sidecars never store target or done state."""
    links = []
    for value in values:
        identifier, separator, suffix = value.partition(':')
        if not REQUEST_ID.fullmatch(identifier) or separator and suffix != 'part':
            raise MapError(f'request_link_invalid: {value!r}; use ID or ID:part')
        if any(link['id'] == identifier for link in links):
            raise MapError(f'request_link_invalid: duplicate request {identifier}')
        links.append(dict(id=identifier, part=bool(separator)))
    validate_request_links(root, links)
    return links


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
            raw = (root / body).read_bytes()
            if sha256_bytes(raw) != item['sha256'] or len(raw) != item['bytes']:
                raise ValueError('owner bytes differ from the sidecar')
        except ValueError as error:
            raise MapError(f'request_meta_edited: {identifier}: {error}') from error


def _other_worktrees(root: Path):
    root = Path(root).resolve()
    if git_common_directory(root) is None:
        return []
    top = git_run(root, 'rev-parse', '--show-toplevel')
    prefix = root.relative_to(Path(os.fsdecode(top.stdout).strip()).resolve())
    result = git_run(root, 'worktree', 'list', '--porcelain', '-z')
    return [path for field in result.stdout.split(b'\0') if field.startswith(b'worktree ')
            and (path := (Path(os.fsdecode(field[9:])) / prefix).resolve()) != root]


other_worktrees = _other_worktrees
