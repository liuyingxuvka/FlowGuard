"""Historical immutable records and release boundaries, independent of retired producers."""
from __future__ import annotations
import hashlib, json, shutil
import pytest
from _pure_helpers import call as _call, git as _git, project as _project, integrity_result as _integrity, historical_change

def _seed_git(root):
    _git(root, 'init', '-q')
    paths = [p for p in ('app.py', '.flowguard/requests') if (root / p).exists()]
    _git(root, 'add', '--', *paths)
    _git(root, 'commit', '-qm', 'project baseline')

def _historical_project(root, capsys=None, *, git=False):
    from flowguard.map.requests import store_request
    _project(root)
    if git:
        _seed_git(root)
    store_request(root, b'extend shelf\n', identifier='R1')
    return historical_change(root, links=[dict(id='R1', part=False)])

def _record_refused(root, capsys):
    from flowguard.map.records import change_records, record_findings, save_release_snapshot
    from flowguard.map.common import MapError
    unreadable = []
    assert change_records(root, unreadable=unreadable) == [] and unreadable
    assert any((item.code == 'record_edited' for item in record_findings(root)))
    from flowguard.map.common import git_common_directory
    if git_common_directory(root) is None:
        with pytest.raises(MapError, match='unreadable'):
            save_release_snapshot(root)

def test_real_record_is_write_once_before_commit_and_after_clone(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.common import MapError
    root = tmp_path / 'project'
    record = _historical_project(root, capsys, git=True)
    assert not record.with_suffix('.msg').exists()
    originals = {record.name: record.read_bytes()}
    for name, raw in originals.items():
        path = record.parent / name
        relative = path.relative_to(root)
        with pytest.raises(MapError, match='immutable file'):
            records.write_once(root, relative, raw)
        path.unlink()
        with pytest.raises(MapError, match='immutable file'):
            records.write_once(root, relative, raw)
        path.write_bytes(raw + b'edited before first commit')
        _record_refused(root, capsys)
        path.write_bytes(raw)
    _git(root, 'add', '--', '.flowguard/requests', '.flowguard/changes')
    _git(root, 'commit', '-qm', 'original historical record')
    clone = tmp_path / 'clone'
    _git(tmp_path, 'clone', '-q', str(root), str(clone))
    assert not (clone / '.git/flowguard/written').exists()
    assert records.record_findings(clone) == []
    for name, raw in originals.items():
        path = clone / '.flowguard/changes' / name
        assert path.read_bytes() == raw
        path.write_bytes(raw + b'edited after fresh clone')
        _record_refused(clone, capsys)
        path.write_bytes(raw)

def test_nongit_release_snapshot_survives_cache_loss_and_rejects_edited_record(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.common import read_git_paths
    from flowguard.map.requests import request_findings, retire_request, store_request
    record = _historical_project(tmp_path, capsys)
    store_request(tmp_path, b'Keep this pending request visible.\n', identifier='RWaiting')
    store_request(tmp_path, b'1. a plan an AI stored\n', identifier='RPlan')
    retire_request(tmp_path, 'RPlan')
    records.save_release_snapshot(tmp_path)
    assert not [item for item in records.record_findings(tmp_path) if item.level == 'error']
    (tmp_path / '.flowguard/cache').mkdir(parents=True, exist_ok=True)
    snapshots = [tmp_path / '.flowguard/release-base' / name for name in ('records.json', 'covered.json')]
    original = {path: path.read_bytes() for path in snapshots}
    shutil.rmtree(tmp_path / '.flowguard/cache')
    assert records.record_findings(tmp_path) == request_findings(tmp_path) == []
    history = records.since_release(tmp_path, records.change_records(tmp_path), read_git_paths)
    assert history['changes'] == [] and 'snapshot' in history['known_from'].lower()
    store_request(tmp_path, b'A later request.\n', identifier='RLater')
    retire_request(tmp_path, 'RWaiting')
    from flowguard.map.requests import owner_words
    words = owner_words(tmp_path)
    assert [row['id'] for row in words['rows'] if not row['retired']] == ['RLater', 'R1']
    assert next(row for row in words['rows'] if row['id'] == 'RWaiting')['retired']
    assert request_findings(tmp_path) == []
    original_record = record.read_bytes()
    record.write_bytes(original_record + b'\n')
    _record_refused(tmp_path, capsys)
    assert {path: path.read_bytes() for path in snapshots} == original
    record.write_bytes(original_record)
    assert records.record_findings(tmp_path) == []
    _seed_git(tmp_path)
    code, output, _ = _integrity(tmp_path)
    assert code == 0 and 'immutable_unverified' in output and ('record_edited' not in output), output
    assert records.change_records(tmp_path) == []
    _git(tmp_path, 'add', '--', '.flowguard/changes', '.flowguard/release-base')
    _git(tmp_path, 'commit', '-qm', 'first committed record bytes')
    assert records.record_findings(tmp_path) == []
    assert [identifier for identifier, _ in records.change_records(tmp_path)] == [record.stem]
    assert _integrity(tmp_path)[0] == 0
    record.write_bytes(original_record + b'\n')
    _record_refused(tmp_path, capsys)
    assert {path: path.read_bytes() for path in snapshots} == original


def _immutable_codes(output):
    return {code for code in ('owner_text_edited', 'request_meta_edited', 'record_edited') if code in output}

def test_unedited_copy_without_git_is_unverifiable_not_edited(tmp_path, capsys):
    root = tmp_path / 'project'
    _historical_project(root, capsys, git=True)
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'historical record')
    copy = tmp_path / 'copy'
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns('.git'))
    code, output, _ = _integrity(copy)
    assert code == 0 and (not _immutable_codes(output)), output
    assert 'immutable_unverified' in output
    from flowguard.map.records import save_release_snapshot
    save_release_snapshot(copy)
    assert not _immutable_codes(_integrity(copy)[1])
    body = copy / '.flowguard/requests/R1.md'
    body.write_bytes(body.read_bytes() + b'x')
    code, output, _ = _integrity(copy)
    assert code == 1 and 'owner_text_edited' in output, output

def test_moved_nongit_project_is_unverifiable_not_edited(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    source = tmp_path / 'owner.md'
    source.write_bytes(b'Keep this request after the folder moves.\n')
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'R1')[0] == 0
    assert _integrity(root)[0] == 0
    moved = tmp_path / 'moved'
    root.rename(moved)
    code, output, _ = _integrity(moved)
    assert code == 0 and (not _immutable_codes(output)), output
    assert 'immutable_unverified' in output
    body = moved / '.flowguard/requests/R1.md'
    body.write_bytes(body.read_bytes() + b'x')
    code, output, _ = _integrity(moved)
    assert code == 1 and 'owner_text_edited' in output, output

def test_committed_file_has_one_answer_in_every_checkout(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    _seed_git(root)
    source = tmp_path / 'owner.md'
    source.write_bytes(b'Keep one answer for committed requests.\n')
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'R1')[0] == 0
    body = root / '.flowguard/requests/R1.md'
    meta = body.with_suffix('.json')
    item = json.loads(meta.read_bytes())
    body.write_bytes(body.read_bytes() + b'edited before the first commit\n')
    item.update(sha256=hashlib.sha256(body.read_bytes()).hexdigest(), bytes=len(body.read_bytes()))
    meta.write_bytes(json.dumps(item).encode())
    code, output, _ = _integrity(root)
    assert code == 1 and 'owner_text_edited' in output, output
    _git(root, 'add', '--', '.flowguard/requests')
    _git(root, 'commit', '-qm', 'committed request bytes')
    clone = tmp_path / 'clone'
    _git(tmp_path, 'clone', '-q', str(root), str(clone))
    answers = []
    for checkout in (root, clone):
        code, output, _ = _integrity(checkout)
        answers.append((code, _immutable_codes(output)))
    assert answers == [(0, set()), (0, set())], answers
    for checkout in (root, clone):
        changed = checkout / '.flowguard/requests/R1.md'
        changed.write_bytes(changed.read_bytes() + b'x')
        code, output, _ = _integrity(checkout)
        assert code == 1 and 'owner_text_edited' in output, output

def test_an_unreadable_historical_record_is_named_by_its_reader_and_never_dropped_silently(tmp_path, capsys):
    """The historical reader names damaged old records without coupling current status to them."""
    from flowguard.map.common import MapError
    from flowguard.map.records import change_records
    record = _historical_project(tmp_path, capsys, git=True)
    _git(tmp_path, 'add', '-A')
    _git(tmp_path, 'commit', '-qm', 'historical record')
    record.write_bytes(record.read_bytes().replace(b'"goal"', b'"goal" ', 1))
    with pytest.raises(MapError, match=f'change record {record.stem} unreadable'):
        change_records(tmp_path)
    unreadable = []
    assert change_records(tmp_path, unreadable=unreadable) == [] and [key for key, _ in unreadable] == [record.stem]
    from flowguard.map.records import record_findings
    findings = record_findings(tmp_path)
    assert [(item.level, item.code, item.component) for item in findings] == [('error', 'record_edited', record.stem)]
    assert record.name in findings[0].message and 'restore its original bytes' in findings[0].message

def test_historical_record_retains_declared_fields_and_function_links(tmp_path):
    from flowguard.map.records import change_records
    from flowguard.map.requests import store_request
    _project(tmp_path)
    store_request(tmp_path, b'Keep the original rule.\n', identifier='R1')
    path = historical_change(tmp_path, links=[dict(id='R1', part=True)], fields=dict(implemented_by=['app.py:value'], rules=[dict(id='old.rule', old=None, new='fp:' + 'a' * 64, provenance='owner R1')]))
    original = json.loads(path.read_bytes())
    assert change_records(tmp_path) == [(path.stem, original)]
    assert original['requests'] == [dict(id='R1', part=True)]
    assert original['checked'] == 'Historical fixture input.' and original['plan'] == []
    assert not path.with_suffix('.msg').exists()
    assert original['implemented_by'] == ['app.py:value']
    assert original['rules'][0]['id'] == 'old.rule'

def test_independent_branches_merge_automatic_requests_and_real_records(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.requests import owner_words, store_request
    root = _project(tmp_path / 'project')
    _seed_git(root)
    seed = _git(root, 'rev-parse', 'HEAD').strip().decode()
    identifiers = []
    changes = []
    for branch, record_id in [('left', '20261101-0000-aaaaaa'), ('right', '20261101-0000-bbbbbb')]:
        _git(root, 'checkout', '-qb', branch, seed)
        request = store_request(root, f'extend shelf for {branch}\n'.encode())
        identifiers.append(request['id'])
        path = historical_change(root, identifier=record_id, links=[dict(id=request['id'], part=False)], goal=f'Historical {branch} fixture')
        changes.append(path.stem)
        _git(root, 'add', '--', '.flowguard/requests', '.flowguard/changes')
        _git(root, 'commit', '-qm', branch + ' historical records\n\nRequest: ' + request['id'])
    assert len(set(identifiers)) == len(set(changes)) == 2
    _git(root, 'merge', '--no-edit', 'left')
    assert {identifier for identifier, _ in records.change_records(root)} == set(changes)
    assert records.record_findings(root) == []
    assert {row['id'] for row in owner_words(root)['rows'] if any((c.startswith('commit ') for c in row['cited_by']))} == set(identifiers)
    assert _git(root, 'ls-files', '-u') == b''
    assert not (root / '.flowguard/requests/index.json').exists() and (not (root / '.flowguard/changes/index.json').exists())

def test_unreadable_receipt_is_reported_as_unreadable_not_as_an_edit(tmp_path):
    from flowguard.map.records import _written_path
    from flowguard.map.requests import store_request, request_findings
    from flowguard.map.common import MapError
    root = _project(tmp_path / 'project')
    store_request(root, b'Keep the request when its receipt is damaged.\n', identifier='R1')
    receipt = _written_path(root, root / '.flowguard/requests/R1.md', None)
    receipt.write_text('not a receipt\n', encoding='ascii')
    with pytest.raises(MapError, match='receipt_unreadable') as error:
        request_findings(root)
    assert str(receipt) in str(error.value) and (not _immutable_codes(str(error.value)))
