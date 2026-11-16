"""Raw owner words and independent immutable reader contracts, without legacy targets."""
from __future__ import annotations
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import pytest
from _pure_helpers import call as _call, git as _git, project as _project, integrity_result as _integrity

def test_quote_check_verbatim_and_elision():
    from flowguard.map.requests import quote_matches
    text = 'Renewals keep\n the limit 3.\n续借的 limit 仍然是 3'
    assert quote_matches(text, 'Renewals keep the limit 3.')
    assert quote_matches(text, 'Renewals ... limit 3.')
    assert not quote_matches(text, 'Renewals keep the limit 4.')
    assert quote_matches(text, '续借的 limit 仍然是 3')
    assert not quote_matches(text, '续借的 limit 仍然是 4')

def _citations(root):
    from flowguard.map.requests import owner_words
    return {row['id']: row['cited_by'] for row in owner_words(root)['rows']}

def test_req_add_stores_bytes_and_digest(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    _git(root, 'init', '-q')
    (root / '.gitattributes').write_bytes(b'* text=auto eol=lf\n')
    raw = '主人原话 request\r\nkeep exact bytes\n'.encode()
    source = tmp_path / 'owner.md'
    source.write_bytes(raw)
    code, output, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'R9')
    assert code == 0 and (not errors), (output, errors)
    body = root / '.flowguard/requests/R9.md'
    metadata = body.with_suffix('.json')
    assert body.read_bytes() == raw
    item = json.loads(metadata.read_bytes())
    assert item['id'] == 'R9' and item['kind'] == 'request'
    assert item['sha256'] == hashlib.sha256(raw).hexdigest() and item['bytes'] == len(raw)
    assert datetime.fromisoformat(item['received']).utcoffset().total_seconds() == 0
    before = metadata.read_bytes()
    code, output, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'R9')
    assert code == 2 and 'request_exists' in errors
    assert metadata.read_bytes() == before and body.read_bytes() == raw
    _git(root, 'add', '.flowguard/requests')
    assert _git(root, 'show', ':.flowguard/requests/R9.md') == raw
    assert b'*.md -text' in (body.parent / '.gitattributes').read_bytes()
    blob = subprocess.run(['git', '-C', str(root), 'hash-object', '-w', '--stdin'], input=raw.replace(b'\r\n', b'\n'), check=True, capture_output=True).stdout.strip().decode()
    _git(root, 'update-index', '--cacheinfo', '100644', blob, '.flowguard/requests/R9.md')
    code, output, _ = _integrity(root)
    assert code == 1 and 'R9.md' in output and (body.read_bytes() == raw)
    _git(root, 'add', '.flowguard/requests')


@pytest.mark.parametrize('has_git', [False, True])
def test_owner_text_edited_with_and_without_git(tmp_path, capsys, has_git):
    root = _project(tmp_path / 'project', capsys)
    if has_git:
        _git(root, 'init', '-q')
    source = tmp_path / 'owner.md'
    source.write_bytes(b'the owner asks for an exact request\r\n')
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'R1')[0] == 0
    body = root / '.flowguard/requests/R1.md'
    metadata = body.with_suffix('.json')
    original = (body.read_bytes(), metadata.read_bytes())
    body.write_bytes(original[0] + b'edited')
    code, output, _ = _integrity(root)
    assert code == 1 and 'R1.md' in output
    item = json.loads(original[1])
    item['sha256'] = hashlib.sha256(body.read_bytes()).hexdigest()
    item['bytes'] = len(body.read_bytes())
    metadata.write_bytes(json.dumps(item).encode())
    code, output, _ = _integrity(root)
    assert code == 1 and 'R1.md' in output and ('R1.json' in output)
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    assert _integrity(root)[0] == 0
    body.unlink()
    metadata.unlink()
    code, output, _ = _integrity(root)
    assert code == 1 and 'R1.md' in output and ('R1.json' in output)
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    if has_git:
        _git(root, 'add', '.')
        _git(root, 'commit', '-qm', 'original request')
        clone = tmp_path / 'clone'
        _git(tmp_path, 'clone', '-q', str(root), str(clone))
        changed = clone / '.flowguard/requests/R1.md'
        assert changed.read_bytes() == original[0]
        changed.write_bytes(original[0] + b'changed after clone')
        assert 'R1.md' in _integrity(clone)[1]


def test_request_after_git_init_is_checked_against_its_first_commit(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    source = tmp_path / 'owner.md'
    source.write_bytes(b'Keep the original request across git init.\r\n')
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'RTransition')[0] == 0
    body = root / '.flowguard/requests/RTransition.md'
    meta = body.with_suffix('.json')
    original = (body.read_bytes(), meta.read_bytes())
    assert _integrity(root)[0] == 0
    _git(root, 'init', '-q')
    code, output, _ = _integrity(root)
    assert code == 0 and 'unverified' in output and ('RTransition.md' not in output), output
    body.write_bytes(original[0] + b'edited')
    code, output, _ = _integrity(root)
    assert code == 1 and 'RTransition.md' in output and ('immutable sidecar' in output), output
    body.write_bytes(original[0])
    _git(root, 'add', '--', '.flowguard/requests')
    _git(root, 'commit', '-qm', 'original request')
    code, output, _ = _integrity(root)
    assert code == 0 and 'unverified' not in output, output
    from flowguard.map.records import _written_path
    common = Path(_git(root, 'rev-parse', '--git-common-dir').decode().strip())
    if not common.is_absolute():
        common = root / common
    competing = _written_path(root, body, common)
    competing.parent.mkdir(parents=True, exist_ok=True)
    competing.write_text(json.dumps(dict(path=body.as_posix(), sha256='0' * 64)), encoding='ascii')
    assert _integrity(root)[0] == 0
    competing.unlink()
    body.write_bytes(original[0] + b'edited')
    item = json.loads(original[1])
    item.update(sha256=hashlib.sha256(body.read_bytes()).hexdigest(), bytes=len(body.read_bytes()))
    meta.write_bytes(json.dumps(item).encode())
    code, output, _ = _integrity(root)
    assert code == 1 and 'RTransition.md' in output and ('RTransition.json' in output)
    body.unlink()
    meta.unlink()
    code, output, _ = _integrity(root)
    assert code == 1 and 'RTransition.md' in output and ('RTransition.json' in output)
    code, _, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'RTransition')
    assert code == 2 and 'request_exists' in errors
    assert not body.exists() and (not meta.exists())


def test_unclaimed_owner_words_are_listed_by_req_list(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    source = tmp_path / 'owner.md'
    source.write_bytes(b'Keep an unclaimed request visible.\n')
    for identifier in ('R5', 'R7'):
        assert _call(root, capsys, 'req', 'add', str(source), '--id', identifier)[0] == 0
    code, output, errors = _call(root, capsys, 'req', 'list')
    assert code == 0 and (not errors)
    rows = [line.split()[0] for line in output.splitlines() if line.startswith('  R')]
    assert rows == ['R7', 'R5'], output
    code, output, errors = _call(root, capsys, 'show', 'R5')
    assert code == 0 and (not errors) and ('requests:' not in output)
    assert not (root / '.flowguard/requests/index.json').exists()

def test_final_request_ids_and_stdin_keep_utc_time(tmp_path, capsys, monkeypatch):
    import io
    import sys
    root = _project(tmp_path / 'project', capsys)
    source = tmp_path / 'owner.md'
    identifiers = []
    for number, length in ((25, 4), (143, 6)):
        raw = f'owner note {number}\n'.encode()
        source.write_bytes(raw)
        code, output, errors = _call(root, capsys, 'req', 'add', str(source))
        identifier = 'R' + datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + hashlib.sha256(raw).hexdigest()[:length]
        assert code == 0 and (not errors) and (identifier in output)
        assert (root / f'.flowguard/requests/{identifier}.md').read_bytes() == raw
        identifiers.append(identifier)
    assert identifiers[1].startswith(identifiers[0]) and identifiers[0] != identifiers[1]
    assert _call(root, capsys, 'req', 'add', str(source), '--id', '9bad')[0] == 2
    words = '续借 = renew, renewal\r\n'.encode()
    with monkeypatch.context() as scoped:
        scoped.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(words), encoding='utf-8'))
        assert _call(root, capsys, 'req', 'add', '-', '--id', 'G1')[0] == 0
    assert (root / '.flowguard/requests/G1.md').read_bytes() == words
    item = json.loads((root / '.flowguard/requests/G1.json').read_bytes())
    assert item['kind'] == 'request'
    assert 'stored_during' not in item and datetime.fromisoformat(item['received']).utcoffset().total_seconds() == 0
    # 5.0 stores no glossary or adoption record: the option that wrote one is refused and nothing is stored
    for kind in ('glossary', 'adoption'):
        code, output, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'R0', '--kind', kind)
        assert (code, output, errors) == (2, '', f'flowguard: req add --kind {kind} was removed in 5.0 -> '
                                                 'python -m flowguard req add FILE --id R<n>\n')
        assert not (root / '.flowguard/requests/R0.md').exists() and not (root / '.flowguard/requests/R0.json').exists()


def _stored_before_5(root, identifier, kind, raw):
    """A glossary or adoption record exactly as FlowGuard 4.3 stored it: the owner's bytes and the sidecar, each
    written once by the archive's own writer."""
    from flowguard.map.records import prepare_directory, write_once
    from flowguard.map.requests import REQUEST_DIR
    item = dict(id=identifier, kind=kind, sha256=hashlib.sha256(raw).hexdigest(), received='2026-11-01T08:00:00+00:00',
                bytes=len(raw))
    prepare_directory(root, REQUEST_DIR, ('.md', '.json'))
    write_once(root, REQUEST_DIR / (identifier + '.md'), raw)
    write_once(root, REQUEST_DIR / (identifier + '.json'),
               (json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8'))
    return item


def test_glossary_and_adoption_records_stored_before_5_0_still_load_list_and_show(tmp_path, capsys):
    """The owner-word archive is a public saved input: records of the kinds 5.0 no longer writes keep loading,
    listing, showing and serving as a link, byte for byte."""
    from flowguard.map.requests import owner_words, read_request_bytes, request_state, validate_request_links
    root = _project(tmp_path / 'project', capsys)
    glossary = '续借次数 = availability_ceiling\r\n'.encode()
    adoption = b'We adopt FlowGuard for the loan rules.\n'
    stored = {'G1': _stored_before_5(root, 'G1', 'glossary', glossary), 'A1': _stored_before_5(root, 'A1', 'adoption', adoption)}
    rows = {row['id']: row for row in owner_words(root)['rows']}
    assert {identifier: (row['kind'], row['edited'], row['invalid']) for identifier, row in rows.items()} == {
        'G1': ('glossary', None, None), 'A1': ('adoption', None, None)}
    for identifier, raw in (('G1', glossary), ('A1', adoption)):
        assert read_request_bytes(root, identifier) == raw
        assert hashlib.sha256(raw).hexdigest() == stored[identifier]['sha256']
        assert request_state(root, identifier)['kind'] == stored[identifier]['kind']
    validate_request_links(root, [dict(id='G1', part=False), dict(id='A1', part=False)])
    code, output, errors = _call(root, capsys, 'req', 'list')
    assert code == 0 and not errors
    assert output.splitlines()[1:] == ['  G1 glossary 2026-11-01T08:00:00+00:00 stored',
                                       '  A1 adoption 2026-11-01T08:00:00+00:00 stored'], output
    code, output, errors = _call(root, capsys, 'show', 'G1')
    assert (code, errors) == (0, '') and output == 'OWNER G1\n' + glossary.decode('utf-8') + '\n', output

def test_written_protection_distinguishes_linked_worktrees(tmp_path, capsys):
    root = _project(tmp_path / 'main', capsys)
    _git(root, 'init', '-q')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'seed')
    seed = _git(root, 'rev-parse', 'HEAD').strip().decode()
    peer = tmp_path / 'peer'
    _git(root, 'worktree', 'add', '-qb', 'peer', str(peer))
    source = tmp_path / 'owner.md'
    for project, raw in ((root, b'first original\r\n'), (peer, b'second original\r\n')):
        source.write_bytes(raw)
        assert _call(project, capsys, 'req', 'add', str(source), '--id', 'R9')[0] == 0
        assert _integrity(project)[0] == 0
    _git(peer, 'add', '.flowguard/requests')
    _git(peer, 'commit', '-qm', 'peer request')
    body = root / '.flowguard/requests/R9.md'
    metadata = body.with_suffix('.json')
    original = (body.read_bytes(), metadata.read_bytes())
    body.unlink()
    metadata.unlink()
    assert 'R9.md' in _integrity(root)[1]
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    body.write_bytes(body.read_bytes() + b'changed')
    assert 'R9.md' in _integrity(root)[1]
    assert _integrity(peer)[0] == 0
    _git(peer, 'checkout', '-qb', 'without-request', seed)
    assert not (peer / '.flowguard/requests/R9.md').exists()
    assert _integrity(peer)[0] == 0


def test_sidecar_attribute_conflict_leaves_no_half_request(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    _git(root, 'init', '-q')
    (root / '.git/info/attributes').write_text('.flowguard/requests/R9.json text\n', encoding='utf-8')
    source = tmp_path / 'owner.md'
    source.write_bytes(b'one original\r\n')
    code, output, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'R9')
    assert code == 2 and 'Git attributes transform immutable bytes' in errors
    assert not (root / '.flowguard/requests/R9.md').exists()
    assert not (root / '.flowguard/requests/R9.json').exists()


def test_request_readers_preserve_stored_bytes_and_digests(tmp_path):
    from flowguard.map.requests import store_request, read_request_bytes
    raw = '续借次数保持为1。\nOwner original second line.\n'.encode()
    request = store_request(tmp_path, raw, identifier='RDuring')
    assert hashlib.sha256(read_request_bytes(tmp_path, 'RDuring')).hexdigest() == request['sha256']
    assert (tmp_path / '.flowguard/requests/RDuring.md').read_bytes() == raw

@pytest.mark.parametrize('partial', [False, True])
def test_legacy_change_files_never_become_live_citations_or_completion_state(tmp_path, partial):
    from flowguard.map.requests import store_request
    root = _project(tmp_path / 'project')
    store_request(root, b'Keep the limit at 3.\r\n', identifier='R1')
    store_request(root, b'Leave this request visible.\n', identifier='R2')
    originals = {p.name: p.read_bytes() for p in (root / '.flowguard/requests').glob('R*.*')}
    path = root / '.flowguard/changes/20261101-0000-abcdef.json'
    path.parent.mkdir()
    path.write_bytes(json.dumps({'requests': [{'id': 'R1', 'part': partial}]}).encode())
    assert _citations(root) == {'R1': [], 'R2': []}
    assert {p.name: p.read_bytes() for p in (root / '.flowguard/requests').glob('R*.*')} == originals
    path.write_bytes(path.read_bytes() + b' ')
    assert _citations(root) == {'R1': [], 'R2': []}
    assert {p.name: p.read_bytes() for p in (root / '.flowguard/requests').glob('R*.*')} == originals

def test_stored_links_refuse_unknown_and_edited_requests(tmp_path):
    from flowguard.map.requests import store_request, validate_request_links
    from flowguard.map.common import MapError
    root = _project(tmp_path / 'project')
    with pytest.raises(MapError, match='request_unknown: R9 is not stored'):
        validate_request_links(root, [dict(id='R9', part=False)])
    store_request(root, b'complete this request\n', identifier='R1')
    assert validate_request_links(root, [dict(id='R1', part=True)]) is None
    body = root / '.flowguard/requests/R1.md'
    body.write_bytes(body.read_bytes() + b'edited')
    with pytest.raises(MapError, match='owner_text_edited'):
        validate_request_links(root, [dict(id='R1', part=False)])
    assert not (root / '.flowguard/changes').exists()


def test_empty_request_bytes_do_not_create_records_or_reserve_the_id(tmp_path):
    from flowguard.map.common import MapError
    from flowguard.map.requests import store_request

    with pytest.raises(MapError, match="request_empty"):
        store_request(tmp_path, b"", identifier="REmpty")
    assert not (tmp_path / ".flowguard").exists()
    raw = b" \t\r\n"
    item = store_request(tmp_path, raw, identifier="REmpty")
    assert item["bytes"] == len(raw)
    assert (tmp_path / ".flowguard/requests/REmpty.md").read_bytes() == raw

@pytest.mark.parametrize("input_source", ["file", "stdin"])
def test_req_add_reports_empty_input_before_writing(tmp_path, capsys, monkeypatch, input_source):
    import io
    import sys

    empty = tmp_path / "empty.md"
    empty.write_bytes(b"")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b""), encoding="utf-8"))
    source = "-" if input_source == "stdin" else str(empty)
    code, output, errors = _call(tmp_path, capsys, "req", "add", source, "--id", "REmpty")
    assert code == 2 and not output and "request_empty" in errors
    assert "stdin" in errors
    assert not (tmp_path / ".flowguard/requests").exists()
    empty.write_bytes(b"Keep the owner's words.\r\n")
    code, _, errors = _call(tmp_path, capsys, "req", "add", str(empty), "--id", "REmpty")
    assert code == 0 and not errors
