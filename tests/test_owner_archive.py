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

def test_retired_text_cannot_be_linked_or_superseded(tmp_path, capsys):
    from flowguard.map.requests import store_request, retire_request, validate_request_links
    from flowguard.map.common import MapError
    root = _project(tmp_path / 'project')
    store_request(root, b'Renewals keep the limit 3.\n', identifier='RQuote')
    retire_request(root, 'RQuote')
    with pytest.raises(MapError, match='request_retired: RQuote'):
        validate_request_links(root, [dict(id='RQuote', part=False)])
    source = tmp_path / 'replacement.md'
    source.write_text("The owner's own replacement.\n", encoding='utf-8')
    code, _, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'R2', '--supersedes', 'RQuote')
    assert code == 2 and 'request_retired: RQuote' in errors
    assert not (root / '.flowguard/requests/R2.md').exists()

def test_an_edited_retire_record_is_an_error(tmp_path, capsys):
    from flowguard.map.requests import owner_words, retired_requests
    root = _plain(tmp_path)
    _words(root, capsys, 'planner list\n')
    assert _call(root, capsys, 'req', 'retire', 'R1', '--not-owner')[0] == 0
    assert owner_words(root)['retire_problems'] == {} and set(retired_requests(root)) == {'R1'}
    path = root / '.flowguard/requests/retired/R1.json'
    path.write_bytes(path.read_bytes().replace(b'"not_owner": true', b'"not_owner": false'))
    assert 'edited:' in owner_words(root)['retire_problems']['R1']
    assert list(retired_requests(root)) == ['R1'] and 'immutable file bytes changed' in retired_requests(root)['R1']

def test_a_retire_record_in_a_copy_without_git_is_unverifiable_not_edited(tmp_path, capsys):
    import shutil
    from flowguard.map.requests import owner_words, retired_requests
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
    words = owner_words(copy)
    assert 'cannot be checked here' in words['retire_problems']['R1']
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
    from flowguard.map.requests import owner_words, retired_requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    record = root / '.flowguard/requests/retired/R1.json'
    record.unlink()
    if shape == 'directory':
        record.mkdir()
    elif shape == 'link':
        record.symlink_to(tmp_path / 'absent.json')
    problem = retired_requests(root)['R1']
    assert problem.startswith('is missing:') and 'edited' not in problem
    reported = owner_words(root)['retire_problems']['R1']
    assert reported.startswith('is missing:') and 'edited' not in reported


def test_retire_permission_error_keeps_its_actual_cause(tmp_path, capsys, monkeypatch):
    from flowguard.map import requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    def unreadable(root, identifier):
        raise PermissionError(13, 'Permission denied', str(root / requests.RETIRED_DIR / (identifier + '.json')))
    monkeypatch.setattr(requests, '_retire_record', unreadable)
    problem = requests.retired_requests(root)['R1']
    assert problem.startswith('cannot be read: ') and 'edited' not in problem
    reported = requests.owner_words(root)['retire_problems']['R1']
    assert reported.startswith('cannot be read:') and 'Permission denied' in reported


def test_damaged_retired_sidecar_stays_retired_and_names_the_sidecar(tmp_path, capsys):
    from flowguard.map.requests import owner_words, retired_requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    sidecar = root / '.flowguard/requests/R1.json'
    sidecar.write_bytes(sidecar.read_bytes().replace(b'"kind": "request"', b'"kind": "bogus"'))
    assert retired_requests(root) == {'R1': None}
    row = next(row for row in owner_words(root)['rows'] if row['id'] == 'R1')
    assert row['id'] == 'R1' and row['retired'] and row['edited']
    assert 'R1.json' in row['edited'] and 'first_line' not in row      # a row holds no words of his


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


def test_a_source_checks_only_the_cited_request_and_reads_what_the_whole_archive_says(tmp_path):
    """A rule's source checks the request it cites (and the sidecars that may supersede it), not every
    stored request: on FlowGuard's own 54 requests that check took seconds of every pytest session. Each
    status equals the one read from the whole archive, for current, superseded, retired and edited words."""
    import json as _json
    from flowguard.intent.sources import Archive
    from flowguard.map.requests import owner_words, retire_request, store_request
    root = _project(tmp_path / 'project')
    _git(root, 'init', '-q')
    store_request(root, b'Keep the limit at 3.\n', identifier='R1')
    store_request(root, b'Keep the limit at 4.\n', identifier='R2', supersedes=['R1'])
    store_request(root, b'Not the owner.\n', identifier='R3')
    retire_request(root, 'R3')
    store_request(root, b'Members pay too.\n', identifier='R4')
    store_request(root, b'Members pay half.\n', identifier='R5')
    store_request(root, b'Later words.\n', identifier='R6', supersedes=['R5'])
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'requests')
    (root / '.flowguard/requests/R4.md').write_bytes(b'Members pay nothing.\n')          # edited owner text
    sidecar = root / '.flowguard/requests/R6.json'                                       # edited sidecar
    sidecar.write_text(_json.dumps(dict(_json.loads(sidecar.read_text(encoding='utf-8')), note='x')), encoding='utf-8')

    rows = {row['id']: row for row in owner_words(root)['rows']}
    def whole(rid, quote=None):         # the status the whole archive gave before
        item = rows.get(rid)
        if item is None:
            return False, f'{rid} missing -> req add the actual owner words'
        if item.get('invalid') or item.get('edited') or item.get('unverified'):
            return False, f'{rid} bytes unverified -> restore the stored original'
        if item.get('retired') or item.get('superseded_by'):
            return False, f'{rid} is no longer current -> cite the current request'
        return True, f'owner {rid}'
    archive = Archive(root)
    for rid in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'):
        assert archive.status(rid) == whole(rid), rid
    assert [archive.status(rid)[0] for rid in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7')] == [False, True, False, False, True, False, False]
    assert set(archive.rows) == {'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'}
    assert Archive(tmp_path / 'nothing').status('R1') == (False, 'R1 missing -> req add the actual owner words')


def test_stored_request_bytes_have_one_decoder_and_a_row_holds_no_words_of_them(tmp_path):
    """R105: `owner R1` with a quote read the stored request with read_text('utf-8-sig'), a third decoder of stored
    owner bytes beside `decode_text` (`R1 "words"`, `owner R1` at the baseline, `show R1`): a request stored as UTF-16
    with its byte order mark (Windows PowerShell 5.1's `>`) stopped the rule with UnicodeDecodeError while the same
    words held in every other form. And `owner_words` decoded each request's first line with errors='replace' for a
    field nothing read, which put U+FFFD into the rows of bytes that are no such text."""
    from flowguard.intent.sources import Archive, _legacy_match
    from flowguard.map.requests import owner_words, store_request
    root = tmp_path / 'project'
    root.mkdir()
    store_request(root, 'Loans last three d\u00e4ys.\r\n'.encode('utf-16'), identifier='R1')
    from tests.stored_records import stored_as_given
    stored_as_given(root, 'R2', 'Loans last four d\u00e4ys.\n'.encode('latin-1'))     # as 5.0.1's req add stored it
    archive = Archive(root)
    assert archive.status('R1', 'three d\u00e4ys') == (True, 'owner R1')
    assert archive.status('R1', 'ten days') == (False, 'R1 quote gone -> quote the actual stored words')
    # Bytes that are no UTF-8 or UTF-16 text: the one decoder raises, and the owner form, as every other, checks them
    # first (`document_text`): they do not hold, the reason naming the file and the decoder's text (5.1 round A raised
    # UnicodeDecodeError here too, into the rule's test).
    with pytest.raises(UnicodeDecodeError):
        _legacy_match((root / '.flowguard/requests/R2.md').read_bytes(), 'four d\u00e4ys')
    assert archive.status('R2', 'four d\u00e4ys') == (
        False, "R2: .flowguard/requests/R2.md is no UTF-8 or UTF-16 text: 'utf-8' codec can't decode byte 0xe4 in "
               'position 17: invalid continuation byte -> store his original message again as UTF-8 text: python -m '
               'flowguard req add FILE --id R<n> --supersedes R2')
    for row in owner_words(root)['rows']:
        assert 'first_line' not in row and 'extra_lines' not in row, row
        assert not any('\ufffd' in str(value) or 'Loans' in str(value) for value in row.values()), row


def test_a_choice_supersedes_retires_and_lists_like_a_request_and_offers_is_no_request(tmp_path, capsys):
    """R105: a choice is a record of the one archive. It may supersede a request and be retired; the options it keeps
    in offers/ are never listed as a request, nor is a stray file there."""
    from flowguard.map.requests import owner_words, retire_request, store_choice, store_request
    root = _plain(tmp_path)
    store_request(root, b'Keep the PSP field for now.\n', identifier='R104')
    offer = '要怎么处理旧的 PSP 字段？\nA. 先保留一个版本，并在 CHANGELOG 写迁移\nB. 直接删除\n'.encode()
    store_choice(root, '选 B'.encode(), offer, ['B. 直接删除'], identifier='R106', supersedes=['R104'])
    (root / '.flowguard/requests/offers/R9.md').write_bytes(b'a stray file\n')
    rows = {row['id']: row for row in owner_words(root)['rows']}
    assert set(rows) == {'R104', 'R106'}
    assert rows['R104']['superseded_by'] == ['R106'] and rows['R106']['supersedes'] == ['R104']
    assert (rows['R106']['kind'], rows['R106']['picked'], rows['R106']['reply']) == ('choice', ['B. 直接删除'], 'typed')
    retire_request(root, 'R106')
    assert owner_words(root)['rows'][0]['retired'] and owner_words(root)['retire_problems'] == {}
    code, output, _ = _call(root, capsys, 'show', 'R106')
    assert code == 0 and output.startswith('RETIRED R106') and '直接删除' not in output
