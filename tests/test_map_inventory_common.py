"""Tests grouped by their model or native component."""
from __future__ import annotations

def test_normalize_newlines_handles_crlf_and_lone_cr(tmp_path):
    from flowguard.map.common import content_digest
    mixed = tmp_path / 'mixed.py'
    lf = tmp_path / 'lf.py'
    mixed.write_bytes(b'a\r\nb\rc\n')
    lf.write_bytes(b'a\nb\nc\n')
    assert content_digest(mixed) == content_digest(lf)
    from flowguard.map.common import normalize_newlines
    assert normalize_newlines(mixed.read_bytes()) == lf.read_bytes()
    assert normalize_newlines(lf.read_bytes()) == lf.read_bytes()
    lf.write_bytes(b'a\nb\nchanged\n')
    assert content_digest(mixed) != content_digest(lf)
