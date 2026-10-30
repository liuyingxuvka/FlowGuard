"""A static recovery screen reads project facts without creating verdicts."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest

from _fg_helpers import target__target_life_cycle_fixture_helpers as fixture_helpers


def _git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=probe', '-c', 'user.email=probe@example.invalid',
                           '-C', str(root), *args], capture_output=True, check=True).stdout.decode().strip()


def _status(root, capsys, *options):
    from flowguard.__main__ import main
    assert main(['status', '--root', str(root), *options, '--json']) == 0
    return json.loads(capsys.readouterr().out)


def _project(root):
    fixture_helpers()['make_project'](root)
    return root


def _start(root, request=None):
    from flowguard.map.target import start_target, add_to_target
    start_target(root, 'resume the shelf change', requests=[request] if request else [])
    add_to_target(root, 'shelf_rule')


def _record(root, links):
    from flowguard.map.records import prepare_change, publish_change
    from flowguard.map.mapfile import load_map
    from flowguard.map.common import sha256_bytes
    inputs = {path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
              for path in root.rglob('*') if path.is_file() and '.git' not in path.parts}
    prepared = prepare_change(root, goal='fixture change record', links=links, base={}, inputs=inputs,
                              merged=load_map(root), model_bytes={}, deleted=[],
                              checked='Static fixture record; no model verdict claimed.')
    publish_change(root, prepared)
    return prepared['id']


def test_status_request_status_derived(tmp_path, capsys):
    from flowguard.__main__ import main
    from flowguard.map.requests import store_request

    fixture_helpers()['make_project'](tmp_path)
    store_request(tmp_path, b'Keep the unclaimed request visible.\n', identifier='R7')
    assert main(['status', '--root', str(tmp_path), '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['requests'][0]['id'] == 'R7'
    assert result['requests'][0]['state'].startswith('open since ')

    store_request(tmp_path, b'Completed request\n', identifier='R5')
    store_request(tmp_path, b'Partial request\n', identifier='R6')
    identifier = _record(tmp_path, [dict(id='R5', part=False), dict(id='R6', part=True)])
    result = _status(tmp_path, capsys)
    states = {row['id']: row['state'] for row in result['requests']}
    assert states['R5'] == f'done (change {identifier})'
    assert states['R6'].startswith('open since ') and states['R7'].startswith('open since ')
    _start(tmp_path, 'R5:part')
    capsys.readouterr()
    result = _status(tmp_path, capsys)
    assert next(row for row in result['requests'] if row['id'] == 'R5')['state'] == 'in this change'


def test_status_never_explores_or_writes(tmp_path, capsys, monkeypatch):
    from flowguard.__main__ import main
    from flowguard.map import proof
    from flowguard.map.requests import store_request

    root = _project(tmp_path)
    _git(root, 'init', '-q')
    store_request(root, b'Recover the request\n', identifier='R7')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'seed')
    _start(root, 'R7')
    capsys.readouterr()
    (root / 'shelf/loans.py').write_text('def advance(): return 2\n')
    def forbidden(*args, **kwargs):
        pytest.fail('a static view started model execution')
    monkeypatch.setattr(proof, 'run_models', forbidden)
    monkeypatch.setattr(proof, 'run_model_in_process', forbidden)
    index = Path(_git(root, 'rev-parse', '--git-path', 'index'))
    if not index.is_absolute():
        index = root / index
    def snapshot():
        return {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in root.rglob('*')
                if path.is_file() and '.git' not in path.relative_to(root).parts}
    before, index_before = snapshot(), (index.read_bytes(), index.stat().st_mtime_ns)
    for options in ([], ['--json'], ['--hook'], ['--wait', '0.01']):
        assert main(['status', '--root', str(root), *options]) == 0
        output = capsys.readouterr().out
        assert 'PASS' not in output
    assert snapshot() == before
    assert (index.read_bytes(), index.stat().st_mtime_ns) == index_before
    first = _status(root, capsys)
    shutil.rmtree(root / '.flowguard/cache', ignore_errors=True)
    again = _status(root, capsys)
    for field in ('root', 'git', 'plan', 'requests', 'since_release', 'next'):
        assert first[field] == again[field]


def test_status_plan_rows_with_known_from(tmp_path, capsys):
    root = _project(tmp_path)
    _start(root)
    capsys.readouterr()
    (root / '.flowguard/target/PLAN.txt').write_text(
        '# Static plan\ntouch: shelf/loans.py:advance\n'
        'changes: shelf_rule.one_loan_step because "Keep the shelf contract deliberate."\n')
    first = _status(root, capsys)
    assert [row['number'] for row in first['plan']] == [1, 2]
    assert first['plan'][0]['state'] == 'not edited'
    assert first['plan'][1]['state'] == 'static, now'
    assert all(row['known_from'] == 'static, now' for row in first['plan'])
    (root / 'shelf/loans.py').write_text('def advance(): return 2\n')
    result = _status(root, capsys)
    assert result['plan'][0]['state'] == 'edited, not verified'
    assert 'shelf/loans.py:advance' in result['change']['edited_functions']
    assert result['verdicts']['stored'] is False
    assert '--root' in result['verdicts']['command']


def test_status_next_absolute_cwd_independent(tmp_path, capsys):
    import sys
    root = _project(tmp_path / '项目 space')
    _start(root)
    capsys.readouterr()
    result = _status(root, capsys)
    other = tmp_path / 'different cwd'
    other.mkdir()
    environment = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
    completed = subprocess.run(shlex.split(result['next']['command']), cwd=other, env=environment,
                               text=True, capture_output=True)
    assert completed.returncode in (0, 1)
    assert 'target:' in completed.stdout and 'no target' not in completed.stderr


def test_status_hook_silent_outside_project_never_fails(tmp_path, capsys, monkeypatch):
    from flowguard.__main__ import main
    assert main(['status', '--root', str(tmp_path), '--hook']) == 0
    assert capsys.readouterr().out == ''
    _project(tmp_path)
    from flowguard.map import status
    def broken(*args, **kwargs):
        raise ValueError('private details')
    monkeypatch.setattr(status, 'collect_status', broken)
    assert main(['status', '--root', str(tmp_path), '--hook']) == 0
    output = capsys.readouterr()
    assert output.out == ('flowguard status failed (ValueError); '
                          'run python -m flowguard status for details\n')
    assert output.err == ''


def test_status_lists_other_worktree_changes(tmp_path, capsys):
    from flowguard.map.requests import store_request
    root = _project(tmp_path / 'repository/project')
    _git(root.parent, 'init', '-q')
    store_request(root, b'Collect in another worktree\n', identifier='R11')
    _git(root.parent, 'add', '.')
    _git(root.parent, 'commit', '-qm', 'seed')
    peer_root = tmp_path / 'peer'
    _git(root, 'worktree', 'add', '-qb', 'peer', str(peer_root))
    peer = peer_root / 'project'
    _start(peer, 'R11:part')
    capsys.readouterr()
    result = _status(root, capsys)
    assert result['git']['worktree_count'] == 2
    assert result['requests'][0]['state'] == f'in another change ({peer})'
    assert result['other_changes'][0]['root'] == str(peer)
    assert result['other_changes'][0]['goal'] == 'resume the shelf change'
    identifier = _record(root, [])
    result = _status(root, capsys)
    assert f'.flowguard/changes/{identifier}.json' in result['git']['uncommitted_paths']
    assert all(not path.startswith('project/') for path in result['git']['uncommitted_paths'])
    assert result['next']['id'] == 'commit'
    assert str(root / '.flowguard/changes' / (identifier + '.msg')) in result['next']['command']
    _git(root, 'config', 'user.name', 'probe')
    _git(root, 'config', 'user.email', 'probe@example.invalid')
    _git(root, 'add', '.flowguard/changes')
    committed = subprocess.run(shlex.split(result['next']['command']), cwd=tmp_path,
                               text=True, capture_output=True)
    assert committed.returncode == 0, committed.stderr


def test_status_lists_commits_without_record(tmp_path, capsys):
    from flowguard.__main__ import main
    root = _project(tmp_path)
    _git(root, 'init', '-q')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'release')
    _git(root, 'tag', 'v0.1.0')
    (root / 'shelf/loans.py').write_text('def advance(): return 2\n')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'unrecorded code')
    code_commit = _git(root, 'rev-parse', 'HEAD')
    _record(root, [])
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'add a record separately')
    result = _status(root, capsys)
    assert result['since_release']['release'] == 'v0.1.0'
    assert [row['commit'] for row in result['since_release']['code_commits_without_record']] == [code_commit]
    assert len(result['since_release']['changes']) == 1
    assert main(['status', '--root', str(root)]) == 0
    text = capsys.readouterr().out
    assert '1 changes; 1 code commits without a record' in text
    assert code_commit not in text and code_commit[:12] not in text
    assert 'status --json --root' in text

    original = _git(root, 'branch', '--show-current')
    _git(root, 'checkout', '-qb', 'side')
    (root / 'side.py').write_text('def side(): return True\n')
    _git(root, 'add', 'side.py')
    _git(root, 'commit', '-qm', 'side code')
    _git(root, 'checkout', original)
    (root / 'main.py').write_text('def main(): return True\n')
    _git(root, 'add', 'main.py')
    _git(root, 'commit', '-qm', 'main code')
    _git(root, 'merge', '--no-ff', '-qm', 'merge side', 'side')
    merge = _git(root, 'rev-parse', 'HEAD')
    result = _status(root, capsys)
    merged = next(row for row in result['since_release']['code_commits_without_record'] if row['commit'] == merge)
    assert merged['paths'] == ['side.py']


def test_status_lists_requests_stored_since_release(tmp_path, capsys):
    from flowguard.map.requests import store_request
    root = _project(tmp_path)
    _git(root, 'init', '-q')
    store_request(root, b'Old first line\n', identifier='R5')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'release')
    _git(root, 'tag', 'v0.1.0')
    _start(root)
    store_request(root, '主人第一行\nDo not lose this request.\n'.encode(), identifier='R7')
    capsys.readouterr()
    result = _status(root, capsys)
    rows = {row['id']: row for row in result['requests']}
    assert rows['R5']['since_release'] is False
    assert rows['R7']['since_release'] is True
    assert rows['R7']['first_line'] == '主人第一行'
    assert rows['R7']['kind'] == 'request'
    assert rows['R7']['stored_during']['goal'] == 'resume the shelf change'
    assert 'release' in result['since_release']['known_from']
