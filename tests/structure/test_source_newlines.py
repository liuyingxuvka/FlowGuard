"""The source reader and its fingerprint agree on physical newlines."""
from pathlib import Path

import pytest

from flowguard.map.common import content_digest, read_source


@pytest.mark.parametrize('raw,expected', [
    (b'\xef\xbb\xbfVALUE = 1\r', 'VALUE = 1\n'),
    (b'# coding: latin-1\rVALUE = "\xe9"\r', '# coding: latin-1\nVALUE = "é"\n'),
    (b'#!/bin/python\r# coding: latin-1\rVALUE = "\xe9"\r',
     '#!/bin/python\n# coding: latin-1\nVALUE = "é"\n'),
])
def test_carriage_return_sources_keep_bom_and_declared_encoding(raw, expected):
    assert read_source(Path('subject.py'), data=raw) == expected


def test_physical_source_newlines_share_identity_but_binary_bytes_do_not():
    assert content_digest(Path('subject.py'), data=b'x\r') == content_digest(Path('subject.py'), data=b'x\n')
    assert content_digest(Path('subject.bin'), data=b'x\r', source_only=True) != content_digest(
        Path('subject.bin'), data=b'x\n', source_only=True)
