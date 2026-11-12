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


def test_the_project_files_outside_git_are_those_the_map_walk_finds(tmp_path):
    """`git_files`, the list no shortened path of a block may name: outside Git the map's own walk (`list_files`),
    without what it skips (.git, node_modules, __pycache__, .venv); in a Git work tree Git's list."""
    import subprocess
    from flowguard.map.common import git_files
    for name in ('a/orders.py', 'b/orders.py', 'README.md', 'node_modules/pkg/orders.py', '.venv/lib/orders.py',
                 'a/__pycache__/orders.cpython-312.pyc'):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text('x\n', encoding='utf-8')
    assert git_files(tmp_path) == {'a/orders.py', 'b/orders.py', 'README.md'}
    (tmp_path / '.gitignore').write_text('node_modules/\n.venv/\n__pycache__/\nREADME.md\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(tmp_path), 'init', '-q', '-b', 'main'], check=True, capture_output=True, timeout=60)
    assert git_files(tmp_path) == {'a/orders.py', 'b/orders.py', '.gitignore'}
