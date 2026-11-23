"""A point read keeps archive integrity without checking unrelated owner bodies."""
import hashlib
import json
import shutil

import pytest

from _pure_helpers import call, git


def test_show_one_request_keeps_full_archive_links_and_checks_only_its_body(tmp_path, capsys, monkeypatch):
    from flowguard.intent import cli
    from flowguard.map import requests

    root = tmp_path / 'project'
    root.mkdir()
    raw = '\ufeff主人的原话\r\nsecond line\n'.encode()
    requests.store_request(root, b'older words\n', identifier='Rold')
    requests.store_request(root, raw, identifier='Rtarget', supersedes=['Rold'])
    requests.store_request(root, b'unrelated words\n', identifier='Rother')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'Store words\n\nRequest: Rtarget')
    stamp = git(root, 'rev-parse', '--short=7', 'HEAD').decode().strip()
    rows = requests.owner_words(root)['rows']
    assert [row['id'] for row in rows] == ['Rother', 'Rtarget', 'Rold']
    by_id = {row['id']: row for row in rows}
    assert by_id['Rtarget']['supersedes'] == ['Rold']
    assert by_id['Rold']['superseded_by'] == ['Rtarget']
    assert by_id['Rtarget']['cited_by'] == ['commit ' + stamp]
    code, output, errors = call(root, capsys, 'req', 'list')
    assert code == 0 and not errors and 'Rold request' in output and 'superseded' in output

    (root / '.flowguard/requests/Rother.md').write_bytes(b'changed unrelated body')
    checked = []
    original = requests._request_problems
    def checking(root, identifier, unverified):
        checked.append(identifier)
        return original(root, identifier, unverified)
    def unrelated(*args, **kwargs):
        pytest.fail('a point read must not scan intent, build the map or read archive citations')
    monkeypatch.setattr(requests, '_request_problems', checking)
    monkeypatch.setattr(requests, 'request_citations', unrelated)
    monkeypatch.setattr(cli.cache, 'read', unrelated)
    monkeypatch.setattr(cli, 'build', unrelated)
    code, output, errors = call(root, capsys, 'show', 'Rtarget')
    assert (code, output, errors) == (0, 'OWNER Rtarget\n' + raw.decode('utf-8-sig') + '\n', '')
    assert checked == ['Rtarget']


@pytest.mark.parametrize('damage', ['body', 'sidecar', 'missing_sidecar', 'index', 'attributes'])
def test_show_rechecks_target_bytes_index_and_attributes(tmp_path, capsys, damage):
    from flowguard.map.requests import store_request

    store_request(tmp_path, b'original private words\n', identifier='Rtarget')
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'Original words')
    body = tmp_path / '.flowguard/requests/Rtarget.md'
    if damage == 'body':
        body.write_bytes(b'changed private words\n')
    elif damage == 'sidecar':
        body.with_suffix('.json').write_bytes(b'not JSON')
    elif damage == 'missing_sidecar':
        body.with_suffix('.json').unlink()
    elif damage == 'index':
        body.write_bytes(b'changed private words\n')
        git(tmp_path, 'add', '.flowguard/requests/Rtarget.md')
        body.write_bytes(b'original private words\n')
    else:
        (tmp_path / '.git/info/attributes').write_text('.flowguard/requests/Rtarget.md text\n')
    code, output, errors = call(tmp_path, capsys, 'show', 'Rtarget')
    assert code == 2 and not output and 'stored original is not verified' in errors
    assert 'private words' not in errors


@pytest.mark.parametrize('supersedes', ['Rold', ['../Rold']])
def test_show_rejects_original_sidecar_with_invalid_supersedes(tmp_path, capsys, supersedes):
    from flowguard.map.records import prepare_directory, write_once
    from flowguard.map.requests import REQUEST_DIR

    # A malformed archived input with its own original-byte receipt still needs schema validation.
    raw = b'private original words\n'
    item = dict(id='Rbad', kind='request', received='2026-11-07T00:00:00+00:00',
                sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), supersedes=supersedes)
    prepare_directory(tmp_path, REQUEST_DIR, ('.md', '.json'))
    write_once(tmp_path, REQUEST_DIR / 'Rbad.md', raw)
    write_once(tmp_path, REQUEST_DIR / 'Rbad.json', json.dumps(item).encode())
    code, output, errors = call(tmp_path, capsys, 'show', 'Rbad')
    assert code == 2 and not output and 'stored original is not verified' in errors
    assert 'private original words' not in errors


@pytest.mark.parametrize('damage', ['edited', 'missing'])
def test_show_keeps_damaged_or_deleted_protected_retirement_hidden(tmp_path, capsys, damage):
    from flowguard.map.requests import store_request, retire_request

    store_request(tmp_path, b'retired private words\n', identifier='Rtarget')
    retire_request(tmp_path, 'Rtarget')
    record = tmp_path / '.flowguard/requests/retired/Rtarget.json'
    if damage == 'missing':
        record.unlink()  # The first-write receipt must still make this a retired request.
    else:
        record.write_bytes(b'not JSON')
    code, output, errors = call(tmp_path, capsys, 'show', 'Rtarget')
    assert code == 0 and not errors and output.startswith('RETIRED Rtarget:')
    assert 'private words' not in output
    (tmp_path / '.flowguard/requests/Rtarget.json').write_bytes(b'not JSON')
    code, output, errors = call(tmp_path, capsys, 'show', 'Rtarget')
    assert code == 2 and not output and 'stored original is not verified' in errors


def test_show_without_original_fact_keeps_sidecar_comparison(tmp_path, capsys):
    from flowguard.map.requests import store_request

    original = tmp_path / 'original'
    original.mkdir()
    store_request(original, b'original copied words\r\n', identifier='Rtarget')
    git(original, 'init', '-q')
    git(original, 'add', '.')
    git(original, 'commit', '-qm', 'Original words')
    copied = tmp_path / 'copy'
    shutil.copytree(original, copied, ignore=shutil.ignore_patterns('.git', 'cache'))
    code, output, errors = call(copied, capsys, 'show', 'Rtarget')
    assert (code, output, errors) == (0, 'OWNER Rtarget\noriginal copied words\r\n\n', '')
    (copied / '.flowguard/requests/Rtarget.md').write_bytes(b'changed copied words')
    code, output, errors = call(copied, capsys, 'show', 'Rtarget')
    assert code == 2 and not output and 'stored original is not verified' in errors


OFFER = '要怎么处理旧的 PSP 字段？\nA. 先保留一个版本，并在 CHANGELOG 写迁移\nB. 直接删除\n'.encode()
PICKED = 'A. 先保留一个版本，并在 CHANGELOG 写迁移'


def test_a_choice_row_carries_its_reply_offer_and_picks_and_its_offer_is_checked_like_its_reply(tmp_path, capsys):
    """R105: the options the agent offered are part of the choice record. An edited or deleted offer makes the whole
    record unverified, in the row, in show, as a link and as a source, naming the offer file and its restore step."""
    from flowguard.intent import sources
    from flowguard.intent.config import load_config
    from flowguard.map.common import MapError
    from flowguard.map.requests import owner_words, request_state, store_choice, validate_request_links

    root = tmp_path / 'project'
    root.mkdir()
    store_choice(root, '选 A'.encode(), OFFER, [PICKED], identifier='R106')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'Store the choice')
    row = request_state(root, 'R106')
    assert (row['kind'], row['first_line'], row['offer'], row['picked'], row['reply'], row['edited'], row['offer_edited']) == (
        'choice', '选 A', '.flowguard/requests/offers/R106.md', [PICKED], 'typed', None, False)
    cfg = load_config(root)
    picked = sources.parse('R106 picked "先保留一个版本"', strict=True)
    assert sources.catalog_authority(picked, cfg, None)[0]
    offer = root / '.flowguard/requests/offers/R106.md'
    for damage in ('edited', 'deleted'):
        if damage == 'edited':
            offer.write_bytes(OFFER.replace('B. 直接删除'.encode(), 'B. 保留'.encode()))
        else:
            offer.unlink()
        row = request_state(root, 'R106')
        assert row['offer_edited'] and row['edited'].startswith('offer of R106 differs from its stored original (')
        assert 'git -C' in row['edited'] and '.flowguard/requests/offers/R106.md' in row['edited'], row['edited']
        assert row['first_line'] == ''
        assert [item['edited'] for item in owner_words(root)['rows']] == [row['edited']]
        code, output, errors = call(root, capsys, 'show', 'R106')
        assert code == 2 and not output and 'stored original is not verified' in errors
        assert sources.catalog_authority(picked, cfg, sources.Archive(root)) == (
            False, 'offer of R106 differs from its stored original -> restore the stored original')
        with pytest.raises(MapError, match='offer_edited: offer of R106 differs from its stored original'):
            validate_request_links(root, [dict(id='R106', part=False)])
        git(root, 'checkout', '--', '.flowguard/requests/offers/R106.md')
        assert request_state(root, 'R106')['edited'] is None


def test_a_5_0_sidecar_with_choice_fields_or_a_choice_without_them_is_invalid(tmp_path, capsys):
    """`_metadata` requires offer, picked and reply on a choice and refuses them on every other kind."""
    from flowguard.map.records import prepare_directory, write_once
    from flowguard.map.requests import REQUEST_DIR, request_state

    raw = b'private original words\n'
    digest = hashlib.sha256(raw).hexdigest()
    offer = dict(sha256=digest, bytes=len(raw))
    prepare_directory(tmp_path, REQUEST_DIR, ('.md', '.json'))
    shapes = {'Rplain': dict(kind='request', picked=['x']), 'Rbare': dict(kind='choice'),
              'Rreply': dict(kind='choice', offer=offer, picked=['x'], reply='clicked'),
              'Rnone': dict(kind='choice', offer=offer, picked=[], reply='typed')}
    for identifier, fields in shapes.items():
        item = dict(id=identifier, received='2026-11-23T08:00:00+00:00', sha256=digest, bytes=len(raw), **fields)
        write_once(tmp_path, REQUEST_DIR / (identifier + '.md'), raw)
        write_once(tmp_path, REQUEST_DIR / (identifier + '.json'), json.dumps(item).encode())
        assert request_state(tmp_path, identifier)['kind'] is None, identifier
        code, output, errors = call(tmp_path, capsys, 'show', identifier)
        assert code == 2 and not output and 'stored original is not verified' in errors
