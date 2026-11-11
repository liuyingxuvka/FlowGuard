"""A failure FlowGuard cannot answer around is reported as that failure, never read as an absent or unknown state."""
from __future__ import annotations
import json
import os
import shlex
import subprocess
from pathlib import Path
import pytest
from flowguard.map.common import MapError

def _git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=probe', '-c', 'user.email=probe@example.invalid', '-C', str(root), *args], check=True, capture_output=True).stdout

def _plain_folder_request(tmp_path):
    from flowguard.map.requests import store_request
    root = tmp_path / 'plain'
    (root / '.flowguard').mkdir(parents=True)
    store_request(root, b'Keep the limit at 3.\n', identifier='R1')
    return root

def _broken_index_repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    _git(root, 'init', '-q')
    (root / 'a.py').write_text('x = 1\n', encoding='utf-8')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'base')
    (root / '.git/index').write_bytes(b'DIRCgarbage')
    return root

def test_an_invalid_legacy_snapshot_is_one_error_not_edited_requests(tmp_path):
    from flowguard.map import records
    from flowguard.map.requests import owner_words
    root = _plain_folder_request(tmp_path)
    path = root / '.flowguard/release-base/records.json'
    path.parent.mkdir(parents=True)
    path.write_text('{', encoding='utf-8')
    with pytest.raises(MapError, match='release_snapshot_invalid'):
        owner_words(root)
    with pytest.raises(MapError, match='release_snapshot_invalid'):
        records._release_records(root)

def test_a_missing_git_executable_is_an_error_not_a_copy_without_git(tmp_path, monkeypatch):
    from flowguard.map.requests import owner_words, store_request
    root = tmp_path / 'repo'
    (root / '.flowguard').mkdir(parents=True)
    _git(root, 'init', '-q')
    store_request(root, b'Keep the limit at 3.\n', identifier='R1')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'r1')
    monkeypatch.setenv('PATH', str(tmp_path / 'no-bin'))
    with pytest.raises(MapError, match='git executable not found'):
        owner_words(root)

def test_an_unreadable_request_is_named_by_its_reader_and_refuses_a_link(tmp_path):
    from flowguard.map.requests import owner_words, validate_request_links
    root = _plain_folder_request(tmp_path)
    sidecar = root / '.flowguard/requests/R1.json'
    sidecar.write_bytes(b'{')
    row = owner_words(root)['rows'][0]
    problem = row['edited'] or row['invalid']
    assert row['id'] == 'R1' and sidecar.name in problem and row['first_line'] == ''
    assert 'copy, archive or backup' in problem and 'map check' not in problem
    with pytest.raises(MapError, match='request_meta_edited'):
        validate_request_links(root, [dict(id='R1', part=False)])


def test_sidecar_validator_names_every_original_malformed_shape(tmp_path):
    from flowguard.map.requests import _metadata
    sidecar = tmp_path / 'R1.json'
    base = {'id': 'R1', 'kind': 'request', 'sha256': '0' * 64, 'bytes': 3}
    for broken in (base, {**base, 'received': 7}):
        sidecar.write_text(json.dumps(broken), encoding='utf-8')
        with pytest.raises(ValueError):
            _metadata(sidecar, 'R1')

def test_a_programming_error_while_reading_owner_words_is_not_shown_as_invalid(tmp_path, monkeypatch):
    from flowguard.map import requests
    root = _plain_folder_request(tmp_path)

    def broken(path, identifier):
        raise KeyError('injected')
    monkeypatch.setattr(requests, '_metadata', broken)
    with pytest.raises(KeyError, match='injected'):
        requests.owner_words(root)


def test_commit_citations_in_a_repository_without_commits_are_known_to_be_none(tmp_path):
    from flowguard.map.requests import request_citations
    root = tmp_path / 'repo'
    root.mkdir()
    _git(root, 'init', '-q')
    assert request_citations(root) == ({}, True)

def test_a_malformed_glossary_is_rejected_before_storage(tmp_path):
    from flowguard.map.requests import store_request
    with pytest.raises(MapError, match='glossary_syntax'):
        store_request(tmp_path, b'owner word without a mapping', identifier='G1', kind='glossary')
    assert not (tmp_path / '.flowguard/requests/G1.json').exists()
    assert not (tmp_path / '.flowguard/requests/G1.md').exists()




def _failing_git(tmp_path, monkeypatch, subcommand):
    """Put a git first on PATH that fails one subcommand with its own message and runs the real Git otherwise."""
    import shutil
    real = shutil.which('git')
    directory = tmp_path / f'failing-{subcommand}-bin'
    directory.mkdir()
    script = directory / 'git'
    script.write_text(f'#!/bin/sh\nfor argument in "$@"; do\n  if [ "$argument" = "{subcommand}" ]; then\n    echo "fatal: simulated {subcommand} failure" >&2\n    exit 128\n  fi\ndone\nexec {shlex.quote(real)} "$@"\n', encoding='utf-8')
    script.chmod(493)
    monkeypatch.setenv('PATH', f"{directory}{os.pathsep}{os.environ['PATH']}")


def _edit_one_byte(path):
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'"g"', b'"h"', 1) if b'"g"' in raw else raw.replace(b'3', b'4', 1))

@pytest.mark.skipif(os.name == 'nt', reason='a POSIX shell script stands in for a failing git')
@pytest.mark.parametrize('checkout', ['fresh_clone', 'original'])
def test_a_failing_git_log_stops_the_request_check_instead_of_reading_no_history(tmp_path, monkeypatch, checkout):
    from flowguard.map.requests import owner_words, store_request
    origin = tmp_path / 'origin'
    origin.mkdir()
    _git(origin, 'init', '-q')
    store_request(origin, b'Keep the limit at 3.\n', identifier='R1')
    _git(origin, 'add', '-A')
    _git(origin, 'commit', '-qm', 'original request')
    root = origin
    if checkout == 'fresh_clone':
        root = tmp_path / 'clone'
        subprocess.run(['git', 'clone', '-q', str(origin), str(root)], check=True, capture_output=True)
    _edit_one_byte(root / '.flowguard/requests/R1.md')
    _failing_git(tmp_path, monkeypatch, 'log')
    with pytest.raises(MapError, match='simulated log failure'):
        owner_words(root)

@pytest.mark.skipif(os.name == 'nt', reason='a POSIX shell script stands in for a failing git')
def test_a_failing_git_listing_stops_the_request_check_instead_of_reading_no_files(tmp_path, monkeypatch):
    from flowguard.map.requests import owner_words, store_request
    root = tmp_path / 'repo'
    (root / '.flowguard').mkdir(parents=True)
    _git(root, 'init', '-q')
    store_request(root, b'Keep the limit at 3.\n', identifier='R1')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'r1')
    _failing_git(tmp_path, monkeypatch, 'ls-files')
    with pytest.raises(MapError, match='simulated ls-files failure'):
        owner_words(root)


@pytest.mark.parametrize('kind', ['request', 'sidecar'])
def test_fix_advice_in_a_folder_without_git_suggests_no_git_command(tmp_path, kind):
    from flowguard.map.requests import owner_words
    root = _plain_folder_request(tmp_path)
    suffix = 'md' if kind == 'request' else 'json'
    path = root / ('.flowguard/requests/R1.' + suffix)
    path.write_bytes(path.read_bytes() + b'edited')
    row = owner_words(root)['rows'][0]
    message = row['edited'] or row['invalid']
    assert message and path.name in message
    assert 'git -C' not in message and 'checkout --' not in message

def test_a_repository_git_refuses_to_open_is_an_error_not_a_folder_without_git(tmp_path, monkeypatch, capsys):
    """Git exits 128 both outside any repository and for a repository it refuses (dubious ownership)."""
    from flowguard.__main__ import main
    from flowguard.map.common import git_common_directory
    from flowguard.map.requests import store_request
    root = tmp_path / 'repo'
    (root / '.flowguard').mkdir(parents=True)
    (root / 'a.py').write_text('VALUE = 1\n', encoding='utf-8')
    (root / 'pkg').mkdir()
    _git(root, 'init', '-q')
    store_request(root, b'Keep the limit at 3.\n', identifier='R1')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'r1')
    plain = tmp_path / 'plain'
    plain.mkdir()
    monkeypatch.setenv('GIT_TEST_ASSUME_DIFFERENT_OWNER', '1')
    empty_config = tmp_path / 'empty.gitconfig'
    empty_config.write_text('', encoding='utf-8')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(empty_config))
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    for name in ('GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT'):
        monkeypatch.delenv(name, raising=False)
    for place in (root, root / 'pkg'):
        with pytest.raises(MapError, match='dubious ownership'):
            git_common_directory(place)
    assert git_common_directory(plain) is None
    for command in (['req', 'list'],):
        assert main([*command, '--root', str(root)]) == 2, command
        assert 'dubious ownership' in capsys.readouterr().err, command
    before = sorted((path.name for path in (root / '.flowguard/requests').iterdir()))
    source = tmp_path / 'words.md'
    source.write_text('Keep the limit at 4.\n', encoding='utf-8')
    assert main(['req', 'add', str(source), '--id', 'R2', '--root', str(root)]) == 2
    assert 'dubious ownership' in capsys.readouterr().err
    assert sorted((path.name for path in (root / '.flowguard/requests').iterdir())) == before

def test_a_broken_branch_is_an_error_not_a_repository_before_its_first_commit(tmp_path, capsys):
    from flowguard.__main__ import main
    from flowguard.map.common import git_head
    unborn = tmp_path / 'unborn'
    unborn.mkdir()
    _git(unborn, 'init', '-q')
    assert git_head(unborn) is None
    root = tmp_path / 'repo'
    (root / '.flowguard').mkdir(parents=True)
    (root / 'a.py').write_text('def f():\n    return 1\n', encoding='utf-8')
    _git(root, 'init', '-q')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'base')
    branch = _git(root, 'symbolic-ref', 'HEAD').decode().strip()
    (root / '.git' / branch).write_text('zzzz\n', encoding='ascii')
    with pytest.raises(MapError, match='broken'):
        git_head(root)
    # The archive needs Git history; source-only show makes no history claim.
    assert main(['req', 'list', '--root', str(root)]) == 2
    assert 'broken' in capsys.readouterr().err
    assert main(['show', 'a:f', '--root', str(root)]) == 0
    view = capsys.readouterr()
    assert 'a:f' in view.out and not view.err
    assert 'green' not in view.out and 'history complete' not in view.out


@pytest.mark.skipif(os.name == 'nt', reason='a POSIX shell script stands in for a failing git')
def test_a_failing_git_listing_stops_the_inventory_instead_of_walking_the_folder(tmp_path, monkeypatch):
    from flowguard.map.inventory import list_files
    root = tmp_path / 'repo'
    root.mkdir()
    _git(root, 'init', '-q')
    (root / '.gitignore').write_text('build/\n', encoding='utf-8')
    (root / 'a.py').write_text('x = 1\n', encoding='utf-8')
    (root / 'build').mkdir()
    (root / 'build/generated.py').write_text('y = 2\n', encoding='utf-8')
    assert list_files(root) == ['.gitignore', 'a.py']
    _failing_git(tmp_path, monkeypatch, 'ls-files')
    with pytest.raises(MapError, match='simulated ls-files failure'):
        list_files(root)

def test_a_folder_outside_any_repository_needs_no_git_executable(tmp_path, monkeypatch, capsys):
    from flowguard.__main__ import main
    root = tmp_path / 'plain'
    (root / '.flowguard').mkdir(parents=True)
    (root / 'a.py').write_text('VALUE = 1\n', encoding='utf-8')
    (root / 'a.py').write_text('def f():\n    return 1\n', encoding='utf-8')
    monkeypatch.setenv('PATH', str(tmp_path / 'no-bin'))
    for command in (['req', 'list'], ['show', 'f']):
        assert main([*command, '--root', str(root)]) == 0, (command, capsys.readouterr())
        assert 'git executable not found' not in capsys.readouterr().err, command

def test_a_folder_inside_the_git_directory_is_a_folder_without_git(tmp_path):
    """A cache under .git/ has no work tree: Git says so, and its files are walked instead of listed by Git."""
    from flowguard.map.common import git_common_directory
    from flowguard.map.inventory import list_files
    root = tmp_path / 'repo'
    root.mkdir()
    _git(root, 'init', '-q')
    cache = root / '.git/flowguard/cache/snapshot'
    (cache / 'src').mkdir(parents=True)
    (cache / 'src/program.py').write_text('x = 1\n', encoding='utf-8')
    assert git_common_directory(root) == (root / '.git').resolve()
    assert git_common_directory(cache) is None
    assert list_files(cache) == ['src/program.py']
