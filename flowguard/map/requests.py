"""Store owner bytes once and derive request facts without a mutable index."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

from .common import Finding, sha256_bytes
from .mapfile import MapError
from .records import integrity_problem, prepare_directory, protected_paths, validate_new_files, write_once

REQUEST_DIR = Path('.flowguard/requests')
REQUEST_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]*\Z')
KINDS = ('request', 'glossary', 'adoption')


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


def store_request(root: Path, raw: bytes, *, identifier: str | None = None, kind: str = 'request') -> dict:
    root = Path(root).resolve()
    if kind not in KINDS:
        raise MapError('request_kind_invalid: expected request, glossary or adoption')
    if kind == 'glossary':
        glossary_entries(raw)
    received = datetime.now(timezone.utc).isoformat()
    digest = sha256_bytes(raw)
    directory = root / REQUEST_DIR
    exists = lambda value: any((directory / (value + suffix)).exists() for suffix in ('.md', '.json'))
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
    item = json.loads(path.read_bytes())
    if (not isinstance(item, dict) or item.get('id') != identifier
            or not REQUEST_ID.fullmatch(identifier) or item.get('kind') not in KINDS
            or not re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256', '')))
            or type(item.get('bytes')) is not int or item['bytes'] < 0):
        raise ValueError('invalid request sidecar fields')
    received = datetime.fromisoformat(item['received'])
    if received.tzinfo is None or received.utcoffset().total_seconds() != 0:
        raise ValueError('received must be UTC')
    return item


def _identifiers(root: Path) -> list[str]:
    directory = root / REQUEST_DIR
    paths = {path for suffix in ('*.md', '*.json') for path in directory.glob(suffix)}
    paths.update(Path(path) for path in protected_paths(root, REQUEST_DIR) if Path(path).suffix in {'.md', '.json'})
    return sorted({path.stem for path in paths})


def request_findings(root: Path) -> list[Finding]:
    """Integrity is a fresh byte comparison, including before the first commit."""
    import shlex

    root = Path(root).resolve()
    findings = []
    for identifier in _identifiers(root):
        body = REQUEST_DIR / (identifier + '.md')
        meta = body.with_suffix('.json')
        body_problem = integrity_problem(root, body)
        meta_problem = integrity_problem(root, meta)
        try:
            item = _metadata(root / meta, identifier)
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
            item = None
            meta_problem = meta_problem or str(error)
        if item is not None and meta_problem is None and (root / body).is_file():
            raw = (root / body).read_bytes()
            if sha256_bytes(raw) != item['sha256'] or len(raw) != item['bytes']:
                body_problem = body_problem or 'bytes differ from the immutable sidecar'
        for path, problem, code in ((body, body_problem, 'owner_text_edited'),
                                    (meta, meta_problem, 'request_meta_edited')):
            if problem:
                restore = shlex.join(['git', '-C', str(root), 'checkout', '--', path.as_posix()])
                findings.append(Finding('error', code, identifier,
                    f'{root / path} differs from the stored request: {problem}; restore its original bytes '
                    f'({restore} when committed); a correction from the owner is a new request'))
    return findings


def request_rows(root: Path) -> list[str]:
    """Derive current links, other worktrees and completed records; write nothing."""
    from .records import change_records

    root = Path(root).resolve()
    current = {link['id'] for link in _target_links(root)}
    others = {}
    for worktree in _other_worktrees(root):
        for link in _target_links(worktree):
            others.setdefault(link['id'], str(worktree))
    done = {link['id']: identifier for identifier, record in change_records(root)
            for link in record['requests'] if not link['part']}
    rows = []
    for identifier in _identifiers(root):
        try:
            item = _metadata(root / REQUEST_DIR / (identifier + '.json'), identifier)
            state = ('in this change' if identifier in current else
                     f'in another change ({others[identifier]})' if identifier in others else
                     f'done (change {done[identifier]})' if identifier in done else
                     f"open since {item['received'][:10]} (no target)")
            rows.append((item['received'], f'{identifier} {state}'))
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            rows.append(('', f'{identifier} invalid (run map check)'))
    return [row for _, row in sorted(rows)]


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
        for path, code in ((body, 'owner_text_edited'), (meta, 'request_meta_edited')):
            problem = integrity_problem(root, path)
            if problem:
                raise MapError(f'{code}: {problem}')
        try:
            item = _metadata(root / meta, identifier)
            raw = (root / body).read_bytes()
            if sha256_bytes(raw) != item['sha256'] or len(raw) != item['bytes']:
                raise ValueError('owner bytes differ from the sidecar')
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            raise MapError(f'request_meta_edited: {identifier}: {error}') from error


def _target_links(root: Path):
    try:
        target = json.loads((root / '.flowguard/target/map.json').read_bytes())
        links = target.get('requests', [])
    except (OSError, ValueError, AttributeError):
        return []
    return [link for link in links if isinstance(link, dict)
            and isinstance(link.get('id'), str) and type(link.get('part')) is bool] if isinstance(links, list) else []


def _other_worktrees(root: Path):
    try:
        top = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True)
        if top.returncode:
            return []
        prefix = root.relative_to(Path(os.fsdecode(top.stdout).strip()).resolve())
        result = subprocess.run(['git', '-C', str(root), 'worktree', 'list', '--porcelain', '-z'],
                                capture_output=True)
    except (OSError, ValueError):
        return []
    if result.returncode:
        return []
    return [path for field in result.stdout.split(b'\0') if field.startswith(b'worktree ')
            and (path := (Path(os.fsdecode(field[9:])) / prefix).resolve()) != root]
