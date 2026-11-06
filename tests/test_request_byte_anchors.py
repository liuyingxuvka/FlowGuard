"""Ordinary native archive scenarios; the policy is the original REQUEST_BYTES Rule.

These tests create real files, call the business entry, then take real readings.
They neither accept a function callback nor turn an entry's None into an answer.
"""
import hashlib
import pytest
from flowguard.map.common import MapError
from flowguard.map import records, requests
from tests.intent_support import archive_folder


CASES = [(False, '原话不加换行'), (False, 'line one\r\nline two\n'),
         (True, 'changed words'), (False, '0'), (False, '\ufeff原话'),
         (False, 'e\u0301'), (False, '')]
CASE_IDS = ['unicode', 'crlf', 'existing', 'zero', 'bom', 'combining', 'empty']


# flowguard: event RECORD_CASE(exists: bool, payload: str) calibrated_by=tests/test_request_byte_anchors.py::test_record_anchor_case[unicode]
@pytest.mark.parametrize('exists,payload', CASES, ids=CASE_IDS)
def test_record_anchor_case(exists: bool, payload: str):
    with archive_folder(exists, request_api=False) as (root, path):
        assert path.exists() is exists
        try:
            records.write_once(root, 'original.md', payload.encode('utf-8'))
        except MapError:
            return
        actual = records.read_original_bytes(root, 'original.md')
        assert type(actual) is bytes


# flowguard: event REQUEST_CASE(exists: bool, payload: str) calibrated_by=tests/test_request_byte_anchors.py::test_request_anchor_case[unicode]
@pytest.mark.parametrize('exists,payload', CASES, ids=CASE_IDS)
def test_request_anchor_case(exists: bool, payload: str):
    with archive_folder(exists, request_api=True) as (root, path):
        assert path.exists() is exists
        try:
            requests.store_request(root, payload.encode('utf-8'), identifier='Rfixture')
        except MapError:
            return
        metadata = requests._metadata(path.with_suffix('.json'), 'Rfixture')
        assert type(metadata) is dict
        actual = requests.read_request_bytes(root, 'Rfixture')
        assert type(actual) is bytes


@pytest.mark.parametrize('raw', [b'0', b'', b'line one\r\nline two\n', '\ufeff原话'.encode(), 'e\u0301'.encode()])
def test_original_reader_and_integrity_keep_exact_bytes(tmp_path, raw):
    records.write_once(tmp_path, 'original.md', raw)
    assert records.read_original_bytes(tmp_path, 'original.md') == raw
    assert records.integrity_problem(tmp_path, 'original.md') is None
    with pytest.raises(MapError):
        records.write_once(tmp_path, 'original.md', b'replacement')
    assert records.read_original_bytes(tmp_path, 'original.md') == raw


def test_original_reader_rejects_path_escape_and_non_utf8_is_not_decoded(tmp_path):
    sibling = tmp_path.parent / 'outside-original.md'
    sibling.write_bytes(b'outside')
    with pytest.raises(MapError, match='inside the project'):
        records.read_original_bytes(tmp_path, '../outside-original.md')
    records.write_once(tmp_path, 'binary.md', b'\xff\x00')
    assert records.read_original_bytes(tmp_path, 'binary.md') == b'\xff\x00'


@pytest.mark.parametrize('raw', [b'0', b'body\r\nlast\n', '\ufeff原话'.encode()])
def test_request_body_and_sidecar_are_distinct_real_roles(tmp_path, raw):
    item = requests.store_request(tmp_path, raw, identifier='Rroles')
    body = requests.read_request_bytes(tmp_path, 'Rroles')
    meta = requests._metadata(tmp_path / '.flowguard/requests/Rroles.json', 'Rroles')
    assert body == raw
    assert meta == item
    assert meta['sha256'] == hashlib.sha256(body).hexdigest()
    assert meta['bytes'] == len(body)
    assert (tmp_path / '.flowguard/requests/Rroles.json').read_bytes() != body
    with pytest.raises(MapError):
        requests.store_request(tmp_path, b'replacement', identifier='Rroles')
    assert requests.read_request_bytes(tmp_path, 'Rroles') == raw
