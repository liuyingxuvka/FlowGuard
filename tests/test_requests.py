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
    assert code == 1 and 'owner_text_edited' in output and (body.read_bytes() == raw)
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
    assert code == 1 and 'owner_text_edited' in output
    item = json.loads(original[1])
    item['sha256'] = hashlib.sha256(body.read_bytes()).hexdigest()
    item['bytes'] = len(body.read_bytes())
    metadata.write_bytes(json.dumps(item).encode())
    code, output, _ = _integrity(root)
    assert code == 1 and 'owner_text_edited' in output and ('request_meta_edited' in output)
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    assert _integrity(root)[0] == 0
    body.unlink()
    metadata.unlink()
    code, output, _ = _integrity(root)
    assert code == 1 and 'owner_text_edited' in output and ('request_meta_edited' in output)
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
        assert 'owner_text_edited' in _integrity(clone)[1]

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
    assert code == 0 and 'immutable_unverified' in output and ('owner_text_edited' not in output), output
    body.write_bytes(original[0] + b'edited')
    code, output, _ = _integrity(root)
    assert code == 1 and 'owner_text_edited' in output and ('immutable sidecar' in output), output
    body.write_bytes(original[0])
    _git(root, 'add', '--', '.flowguard/requests')
    _git(root, 'commit', '-qm', 'original request')
    code, output, _ = _integrity(root)
    assert code == 0 and 'immutable_unverified' not in output, output
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
    assert code == 1 and 'owner_text_edited' in output and ('request_meta_edited' in output)
    body.unlink()
    meta.unlink()
    code, output, _ = _integrity(root)
    assert code == 1 and 'owner_text_edited' in output and ('request_meta_edited' in output)
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

def test_final_request_ids_stdin_and_kinds_keep_utc_time(tmp_path, capsys, monkeypatch):
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
    assert _call(root, capsys, 'req', 'add', str(source), '--kind', 'glossary')[0] == 2
    glossary = '续借 = renew, renewal\r\n'.encode()
    with monkeypatch.context() as scoped:
        scoped.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(glossary), encoding='utf-8'))
        assert _call(root, capsys, 'req', 'add', '-', '--id', 'G1', '--kind', 'glossary')[0] == 0
    assert (root / '.flowguard/requests/G1.md').read_bytes() == glossary
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'R0', '--kind', 'adoption')[0] == 0
    item = json.loads((root / '.flowguard/requests/R0.json').read_bytes())
    assert item['kind'] == 'adoption'
    assert 'stored_during' not in item and datetime.fromisoformat(item['received']).utcoffset().total_seconds() == 0

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
    assert 'owner_text_edited' in _integrity(root)[1]
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    body.write_bytes(body.read_bytes() + b'changed')
    assert 'owner_text_edited' in _integrity(root)[1]
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

def test_changes_quote_needs_shared_term(tmp_path):
    from flowguard.map.requests import store_request, owner_quote
    from flowguard.map.common import MapError
    raw = 'Renewals keep the limit 3.\nThe ceiling remains 1.\nThe desk opens at nine.\n续借的 limit 仍然是 3\n续借次数保持为3。\nThe state is visible.\n'
    store_request(tmp_path, raw.encode(), identifier='RQuote')
    for quote, accepted in [('Renewals keep the limit 3.', True), ('The ceiling remains 1.', True), ('The desk opens at nine.', False), ('续借的 limit 仍然是 3', True), ('The state is visible.', False)]:
        if accepted:
            assert owner_quote(tmp_path, quote, ['limit', 'ceiling'], request='RQuote')['id'] == 'RQuote'
        else:
            with pytest.raises(MapError, match='quote_subject_mismatch'):
                owner_quote(tmp_path, quote, ['limit', 'ceiling'], request='RQuote')
    with pytest.raises(MapError, match='quote_subject_mismatch'):
        owner_quote(tmp_path, '续借次数保持为3。', ['limit'], request='RQuote')
    store_request(tmp_path, '续借次数 = limit\n'.encode(), identifier='RGloss', kind='glossary')
    assert owner_quote(tmp_path, '续借次数保持为3。', ['limit'], request='RQuote')['glossaries'][0]['id'] == 'RGloss'

def test_owner_quote_preserves_stored_request_and_glossary(tmp_path):
    from flowguard.map.requests import store_request, owner_quote
    raw = '续借次数保持为1。\nOwner original second line.\n'.encode()
    request = store_request(tmp_path, raw, identifier='RDuring')
    glossary = store_request(tmp_path, '续借次数 = availability_ceiling\n'.encode(), identifier='GDuring', kind='glossary')
    quote = owner_quote(tmp_path, '续借次数保持为1。', ['availability_ceiling'], request='RDuring')
    assert quote['id'] == 'RDuring' and quote['sha256'] == request['sha256']
    assert quote['glossaries'][0]['id'] == 'GDuring' and quote['glossaries'][0]['sha256'] == glossary['sha256']
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

def test_request_links_refuse_unknown_duplicate_and_edited_requests(tmp_path):
    from flowguard.map.requests import store_request, request_links
    from flowguard.map.common import MapError
    root = _project(tmp_path / 'project')
    with pytest.raises(MapError, match='request_unknown: R9 is not stored'):
        request_links(root, ['R9'])
    store_request(root, b'complete this request\n', identifier='R1')
    with pytest.raises(MapError, match='duplicate request R1'):
        request_links(root, ['R1', 'R1:part'])
    assert request_links(root, ['R1:part']) == [dict(id='R1', part=True)]
    body = root / '.flowguard/requests/R1.md'
    body.write_bytes(body.read_bytes() + b'edited')
    with pytest.raises(MapError, match='owner_text_edited'):
        request_links(root, ['R1'])
    assert not (root / '.flowguard/changes').exists()


@pytest.mark.parametrize("kind", ["request", "adoption", "glossary"])
def test_empty_request_bytes_do_not_create_records_or_reserve_the_id(tmp_path, kind):
    from flowguard.map.common import MapError
    from flowguard.map.requests import store_request

    with pytest.raises(MapError, match="request_empty"):
        store_request(tmp_path, b"", identifier="REmpty", kind=kind)
    assert not (tmp_path / ".flowguard").exists()
    raw = b"limit = loan_limit\r\n" if kind == "glossary" else b" \t\r\n"
    item = store_request(tmp_path, raw, identifier="REmpty", kind=kind)
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
