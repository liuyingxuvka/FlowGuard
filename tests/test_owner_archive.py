"""Owner archival contracts retained independently of the retired status UI."""

from __future__ import annotations

import json, sys

from pathlib import Path

import pytest

from _pure_helpers import call as _call, git as _git, project as _project

def _words(root, capsys, *texts):
    for number, text in enumerate(texts, 1):
        source = root.parent / f'owner-{number}.md'
        source.write_text(text, encoding='utf-8')
        code, output, errors = _call(root, capsys, 'req', 'add', str(source), '--id', f'R{number}')
        assert code == 0 and (not errors), (output, errors)

def _plain(tmp_path, name='project'):
    root = tmp_path / name
    (root / '.flowguard').mkdir(parents=True)
    return root

def test_retired_text_cannot_be_quoted_linked_or_superseded(tmp_path, capsys):
    from flowguard.map.requests import store_request, retire_request, owner_quote, request_links
    from flowguard.map.common import MapError
    root = _project(tmp_path / 'project')
    store_request(root, b'Renewals keep the limit 3.\n', identifier='RQuote')
    retire_request(root, 'RQuote')
    with pytest.raises(MapError, match='request_retired: RQuote'):
        owner_quote(root, 'Renewals keep the limit 3.', ['limit'], request='RQuote')
    with pytest.raises(MapError, match='request_retired: RQuote'):
        request_links(root, ['RQuote'])
    source = tmp_path / 'replacement.md'
    source.write_text("The owner's own replacement.\n", encoding='utf-8')
    code, _, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'R2', '--supersedes', 'RQuote')
    assert code == 2 and 'request_retired: RQuote' in errors
    assert not (root / '.flowguard/requests/R2.md').exists()

def test_an_edited_retire_record_is_an_error(tmp_path, capsys):
    from flowguard.map.requests import request_findings, retired_requests
    root = _plain(tmp_path)
    _words(root, capsys, 'planner list\n')
    assert _call(root, capsys, 'req', 'retire', 'R1', '--not-owner')[0] == 0
    assert request_findings(root) == [] and set(retired_requests(root)) == {'R1'}
    path = root / '.flowguard/requests/retired/R1.json'
    path.write_bytes(path.read_bytes().replace(b'"not_owner": true', b'"not_owner": false'))
    assert [item.code for item in request_findings(root)] == ['request_retire_edited']
    assert list(retired_requests(root)) == ['R1'] and 'immutable file bytes changed' in retired_requests(root)['R1']

def test_a_retire_record_in_a_copy_without_git_is_unverifiable_not_edited(tmp_path, capsys):
    import shutil
    from flowguard.map.requests import request_findings, retired_requests
    root = _plain(tmp_path)
    _words(root, capsys, 'planner list\n')
    _git(root, 'init', '-q')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'stored words')
    assert _call(root, capsys, 'req', 'retire', 'R1', '--not-owner')[0] == 0
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'retire')
    copy = tmp_path / 'copy'
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns('.git'))
    findings = request_findings(copy)
    assert [(item.level, item.code) for item in findings] == [('info', 'immutable_unverified')], findings
    assert list(retired_requests(copy)) == ['R1'] and 'cannot be checked here' in retired_requests(copy)['R1']
    code, _, errors = _call(copy, capsys, 'req', 'add', str(tmp_path / 'owner-1.md'), '--id', 'R2', '--supersedes', 'R1')
    assert code == 2 and 'request_retired: R1' in errors, errors

def _retired_copy_without_git(tmp_path, capsys):
    import shutil
    root = _plain(tmp_path)
    _words(root, capsys, '1. a planner list\n', "The owner's own words.\n")
    _git(root, 'init', '-q')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'stored words')
    assert _call(root, capsys, 'req', 'retire', 'R1', '--not-owner')[0] == 0
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'retire')
    copy = tmp_path / 'copy'
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns('.git'))
    return (root, copy)

@pytest.mark.parametrize('shape', ['missing', 'directory', pytest.param('link', marks=pytest.mark.skipif(sys.platform == 'win32', reason='symbolic links need extra Windows privileges'))])
def test_retire_path_damage_is_not_misreported_as_edited(tmp_path, capsys, shape):
    from flowguard.map.requests import request_findings, retired_requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    record = root / '.flowguard/requests/retired/R1.json'
    record.unlink()
    if shape == 'directory':
        record.mkdir()
    elif shape == 'link':
        record.symlink_to(tmp_path / 'absent.json')
    problem = retired_requests(root)['R1']
    assert problem.startswith('is missing:') and 'edited' not in problem
    findings = request_findings(root)
    assert [(item.code, item.component) for item in findings] == [('request_retire_missing', 'R1')]
    assert 'edited' not in findings[0].message


def test_retire_permission_error_keeps_its_actual_cause(tmp_path, capsys, monkeypatch):
    from flowguard.map import requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    def unreadable(root, identifier):
        raise PermissionError(13, 'Permission denied', str(root / requests.RETIRED_DIR / (identifier + '.json')))
    monkeypatch.setattr(requests, '_retire_record', unreadable)
    problem = requests.retired_requests(root)['R1']
    assert problem.startswith('cannot be read: ') and 'edited' not in problem
    findings = requests.request_findings(root)
    assert [(item.code, item.component) for item in findings] == [('request_retire_unreadable', 'R1')]
    assert 'Permission denied' in findings[0].message


def test_damaged_retired_sidecar_stays_retired_and_names_the_sidecar(tmp_path, capsys):
    from flowguard.map.requests import request_findings, retired_requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    sidecar = root / '.flowguard/requests/R1.json'
    sidecar.write_bytes(sidecar.read_bytes().replace(b'"kind": "request"', b'"kind": "bogus"'))
    assert retired_requests(root) == {'R1': None}
    assert [(item.code, item.component) for item in request_findings(root)] == [('request_meta_edited', 'R1')]


def test_show_does_not_present_retired_ai_prose_as_owner_words(tmp_path, capsys):
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    code, output, errors = _call(root, capsys, 'show', 'R1')
    assert code == 0 and not errors
    assert 'RETIRED' in output and 'OWNER' not in output and 'planner list' not in output


def test_show_rejects_changed_words_and_does_not_repeat_them(tmp_path, capsys):
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    (root / '.flowguard/requests/R2.md').write_bytes(b'Someone changed these words.')
    code, output, errors = _call(root, capsys, 'show', 'R2')
    assert code == 2 and 'not verified' in errors
    assert 'Someone changed' not in output + errors
