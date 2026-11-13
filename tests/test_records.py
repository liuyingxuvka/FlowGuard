"""Independent byte protection through the current request archive, without old producers."""
from __future__ import annotations
import hashlib, json, shutil
import pytest
from _pure_helpers import call as _call, git as _git, project as _project, integrity_result as _integrity
from flowguard.map.requests import store_request

def _seed_git(root):
    _git(root, 'init', '-q')
    paths = [p for p in ('app.py', '.flowguard/requests') if (root / p).exists()]
    _git(root, 'add', '--', *paths)
    _git(root, 'commit', '-qm', 'project baseline')


def _request_project(root, *, git=False):
    _project(root)
    if git:
        _seed_git(root)
    store_request(root, b'Keep the limit at 3.\r\n', identifier='R1')
    return root / '.flowguard/requests/R1.md'


def test_request_is_write_once_before_commit_and_after_clone(tmp_path):
    from flowguard.map import records
    from flowguard.map.common import MapError
    root = tmp_path / 'project'
    body = _request_project(root, git=True)
    originals = {body.name: body.read_bytes(), body.with_suffix('.json').name: body.with_suffix('.json').read_bytes()}
    for name, raw in originals.items():
        path = body.parent / name
        with pytest.raises(MapError, match='immutable file'):
            records.write_once(root, path.relative_to(root), raw)
        path.unlink()
        with pytest.raises(MapError, match='immutable file'):
            records.write_once(root, path.relative_to(root), raw)
        path.write_bytes(raw + b'edited before first commit')
        assert _integrity(root)[0] == 1
        path.write_bytes(raw)
    _git(root, 'add', '--', '.flowguard/requests')
    _git(root, 'commit', '-qm', 'original request')
    clone = tmp_path / 'clone'
    _git(tmp_path, 'clone', '-q', str(root), str(clone))
    assert not (clone / '.git/flowguard/written').exists()
    assert _integrity(clone)[0] == 0
    for name, raw in originals.items():
        path = clone / '.flowguard/requests' / name
        assert path.read_bytes() == raw
        path.write_bytes(raw + b'edited after fresh clone')
        assert _integrity(clone)[0] == 1
        path.write_bytes(raw)


def test_legacy_original_snapshot_survives_cache_loss_and_never_learns_edited_bytes(tmp_path):
    # Literal historical data, including fixed hashes. This is no snapshot producer:
    # no directory enumeration and no digest learned from the files under test.
    raw = b'Keep the original request.\r\n'
    metadata = b'{"bytes": 28, "id": "R1", "kind": "request", "received": "2026-11-01T00:00:00+00:00", "sha256": "f53eeeac3887b150efed7793cb1625e81eda61a31f15bbed261d4df6f36d4ab7"}\n'
    snapshot = b'{"captured": "2026-11-01T00:00:00+00:00", "files": {".flowguard/requests/R1.json": "970c4f524f7d2e36c4f2e8edb626512891d1caa6b38e156990a97223aa335a92", ".flowguard/requests/R1.md": "f53eeeac3887b150efed7793cb1625e81eda61a31f15bbed261d4df6f36d4ab7"}}\n'
    request_dir = tmp_path / '.flowguard/requests'
    request_dir.mkdir(parents=True)
    (request_dir / '.gitattributes').write_bytes(b'*.md -text\n*.json -text\n')
    body, sidecar = request_dir / 'R1.md', request_dir / 'R1.json'
    body.write_bytes(raw); sidecar.write_bytes(metadata)
    boundary = tmp_path / '.flowguard/release-base/records.json'
    boundary.parent.mkdir(); boundary.write_bytes(snapshot)
    (tmp_path / '.flowguard/cache').mkdir()
    shutil.rmtree(tmp_path / '.flowguard/cache')
    assert _integrity(tmp_path)[0] == 0
    body.write_bytes(raw + b'edited')
    assert _integrity(tmp_path)[0] == 1 and 'R1.md' in _integrity(tmp_path)[1]
    assert boundary.read_bytes() == snapshot
    body.write_bytes(raw)
    assert _integrity(tmp_path)[0] == 0
    _git(tmp_path, 'init', '-q')
    code, output, _ = _integrity(tmp_path)
    assert code == 0 and 'unverified' in output and 'R1.md' not in output
    _git(tmp_path, 'add', '--', '.flowguard/requests', '.flowguard/release-base')
    _git(tmp_path, 'commit', '-qm', 'first committed original bytes')
    assert _integrity(tmp_path)[0] == 0
    body.write_bytes(raw + b'edited')
    assert _integrity(tmp_path)[0] == 1 and 'R1.md' in _integrity(tmp_path)[1]
    assert boundary.read_bytes() == snapshot

def _damaged_request_paths(output):
    return {line.split(':', 1)[0] for line in output.splitlines()
            if line.startswith('.flowguard/requests/')}

def test_unedited_copy_without_git_is_unverifiable_not_edited(tmp_path, capsys):
    root = tmp_path / 'project'
    _request_project(root, git=True)
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'historical record')
    copy = tmp_path / 'copy'
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns('.git'))
    code, output, _ = _integrity(copy)
    assert code == 0 and (not _damaged_request_paths(output)), output
    assert 'unverified' in output
    body = copy / '.flowguard/requests/R1.md'
    body.write_bytes(body.read_bytes() + b'x')
    code, output, _ = _integrity(copy)
    assert code == 1 and 'R1.md' in output, output

def test_moved_nongit_project_is_unverifiable_not_edited(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    source = tmp_path / 'owner.md'
    source.write_bytes(b'Keep this request after the folder moves.\n')
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'R1')[0] == 0
    assert _integrity(root)[0] == 0
    moved = tmp_path / 'moved'
    root.rename(moved)
    code, output, _ = _integrity(moved)
    assert code == 0 and (not _damaged_request_paths(output)), output
    assert 'unverified' in output
    body = moved / '.flowguard/requests/R1.md'
    body.write_bytes(body.read_bytes() + b'x')
    code, output, _ = _integrity(moved)
    assert code == 1 and 'R1.md' in output, output

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
    assert code == 1 and 'R1.md' in output, output
    _git(root, 'add', '--', '.flowguard/requests')
    _git(root, 'commit', '-qm', 'committed request bytes')
    clone = tmp_path / 'clone'
    _git(tmp_path, 'clone', '-q', str(root), str(clone))
    answers = []
    for checkout in (root, clone):
        code, output, _ = _integrity(checkout)
        answers.append((code, _damaged_request_paths(output)))
    assert answers == [(0, set()), (0, set())], answers
    for checkout in (root, clone):
        changed = checkout / '.flowguard/requests/R1.md'
        changed.write_bytes(changed.read_bytes() + b'x')
        code, output, _ = _integrity(checkout)
        assert code == 1 and 'R1.md' in output, output


def test_a_damaged_request_sidecar_is_named_and_never_dropped_silently(tmp_path):
    from flowguard.map.requests import owner_words
    body = _request_project(tmp_path, git=True)
    _git(tmp_path, 'add', '-A'); _git(tmp_path, 'commit', '-qm', 'original request')
    sidecar = body.with_suffix('.json')
    sidecar.write_bytes(b'{')
    code, text, _ = _integrity(tmp_path)
    assert code == 1 and sidecar.name in text and 'immutable file bytes changed' in text
    row = owner_words(tmp_path)['rows'][0]
    assert row['id'] == 'R1' and row['edited'] and row['first_line'] == ''
    assert sidecar.name in row['edited'] and 'restore its original bytes' in row['edited']


def test_independent_branches_merge_automatic_requests_without_a_mutable_index(tmp_path):
    from flowguard.map.requests import owner_words
    root = _project(tmp_path / 'project')
    _seed_git(root)
    seed = _git(root, 'rev-parse', 'HEAD').strip().decode()
    identifiers = []
    for branch in ('left', 'right'):
        _git(root, 'checkout', '-qb', branch, seed)
        request = store_request(root, f'Keep the {branch} request.\r\n'.encode())
        identifiers.append(request['id'])
        _git(root, 'add', '--', '.flowguard/requests')
        _git(root, 'commit', '-qm', branch + ' original request\n\nRequest: ' + request['id'])
    assert len(set(identifiers)) == 2
    _git(root, 'merge', '--no-edit', 'left')
    assert _integrity(root)[0] == 0
    rows = owner_words(root)['rows']
    assert {row['id'] for row in rows if any(c.startswith('commit ') for c in row['cited_by'])} == set(identifiers)
    assert _git(root, 'ls-files', '-u') == b''
    assert not (root / '.flowguard/requests/index.json').exists()

def test_unreadable_receipt_is_reported_as_unreadable_not_as_an_edit(tmp_path):
    from flowguard.map.records import _written_path
    from flowguard.map.requests import store_request
    from flowguard.map.common import MapError
    root = _project(tmp_path / 'project')
    store_request(root, b'Keep the request when its receipt is damaged.\n', identifier='R1')
    receipt = _written_path(root, root / '.flowguard/requests/R1.md', None)
    receipt.write_text('not a receipt\n', encoding='ascii')
    with pytest.raises(MapError, match='receipt_unreadable') as error:
        from flowguard.map.requests import owner_words
        owner_words(root)
    assert str(receipt) in str(error.value) and (not _damaged_request_paths(str(error.value)))


def test_history_listings_begun_ahead_give_each_check_what_it_reads_alone(tmp_path, monkeypatch):
    """Inside `FirstListings` each integrity check reads its own file's history listing, begun a few checks ahead:
    the same answers as alone for intact, edited, removed and re-added, missing and unlisted files, in the listed
    order and in another; every run begun is waited for when the block ends, read or not, and outside Git none
    begins."""
    from flowguard.map import records
    from flowguard.map.common import git_common_directory
    root = tmp_path / 'project'
    _project(root)
    for index in range(8):
        store_request(root, f'words {index}\n'.encode(), identifier=f'R{index}')
    _seed_git(root)
    requests = root / '.flowguard/requests'
    (requests / 'R1.md').write_bytes(b'edited words\n')
    (requests / 'R2.md').unlink()
    _git(root, 'commit', '-qam', 'remove R2')
    (requests / 'R2.md').write_bytes(b'other words\n')
    _git(root, 'add', '--', '.flowguard/requests')
    _git(root, 'commit', '-qm', 'add R2 again')
    (requests / 'R3.json').unlink()
    names = [f'.flowguard/requests/R{index}.{suffix}' for index in range(8) for suffix in ('md', 'json')]

    def answer(name):
        return records.integrity_problem(root, name)
    alone = {name: answer(name) for name in names + ['app.py']}
    assert alone['.flowguard/requests/R0.md'] is None and 'bytes changed' in alone['.flowguard/requests/R1.md']
    assert 'bytes changed' in alone['.flowguard/requests/R2.md'] and 'missing' in alone['.flowguard/requests/R3.json']
    listed = []
    original = records.git_run
    def counted(root, *arguments, **options):
        listed.extend([arguments[-1]] if arguments[0] == 'log' else [])
        return original(root, *arguments, **options)
    monkeypatch.setattr(records, 'git_run', counted)
    common = git_common_directory(root)
    for order in (names, names[::-1]):
        listed.clear()
        with records.FirstListings(root, names[2:] + ['../outside.md', 'absent.md'], common) as listings:
            assert {name: answer(name) for name in order + ['app.py']} == alone
        assert '.flowguard/requests/R3.json' not in listings.runs and not {'../outside.md', 'absent.md'} & set(listings.runs)
        assert all(run.process.returncode is not None for run in listings.runs.values())
        # a listed file's check read the run begun for it; the two files not listed were read alone
        assert sorted(listed) == ['.flowguard/requests/R0.json', '.flowguard/requests/R0.md']
    with records.FirstListings(root, names[:2], common) as unread:
        pass
    assert unread.runs and all(run.process.returncode is not None for run in unread.runs.values())
    with records.FirstListings(root, names, None) as outside:
        assert not outside.runs
