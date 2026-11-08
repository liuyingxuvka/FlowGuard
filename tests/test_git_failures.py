"""Retained Git object/path/worktree failures, without target or change-selection owners."""
from __future__ import annotations
import os
import stat
import pytest
from flowguard.map.common import MapError, git_blob
from test_reported_failures import _failing_git, _git
from _pure_helpers import write

def _committed_shelf_project(tmp_path):
    root = tmp_path / 'repo'
    write(root, 'shelf/loans.py', 'def value(): return 1\n')
    write(root, 'shelf/catalog.py', 'VALUE = 1\n')
    _git(root, 'init', '-q')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'base')
    return root

def test_a_missing_base_tree_stops_the_origin_reader_instead_of_reading_no_file(tmp_path):
    root = _committed_shelf_project(tmp_path)
    assert git_blob(root, 'HEAD', 'shelf/absent.py') is None and git_blob(root, ':', 'shelf/absent.py') is None
    tree = _git(root, 'rev-parse', 'HEAD:shelf').decode().strip()
    tree_object = root / '.git/objects' / tree[:2] / tree[2:]
    # Git objects are read-only on Windows; corrupt the same tree deliberately.
    tree_object.chmod(tree_object.stat().st_mode | stat.S_IWRITE)
    tree_object.unlink()
    loans = root / 'shelf/loans.py'
    assert git_blob(root, ':', 'shelf/catalog.py') is not None
    for read in (lambda: git_blob(root, 'HEAD', 'shelf/loans.py'), lambda: git_blob(root, 'HEAD', 'shelf/absent.py')):
        with pytest.raises(MapError, match=tree):
            read()

def test_a_repository_git_cannot_give_a_work_tree_is_an_error_not_a_folder_without_git(tmp_path, capsys):
    from flowguard.__main__ import main
    from flowguard.map.common import git_common_directory
    root = _committed_shelf_project(tmp_path)
    _git(root, 'config', 'core.bare', 'true')
    with pytest.raises(MapError, match='must be run in a work tree'):
        git_common_directory(root)
    capsys.readouterr()
    assert main(['req', 'list', '--root', str(root)]) == 2
    assert 'must be run in a work tree' in capsys.readouterr().err

@pytest.mark.skipif(os.name == 'nt', reason='a POSIX shell script stands in for a failing git')
def test_a_failing_git_tree_listing_stops_the_origin_reader_with_gits_own_message(tmp_path, monkeypatch):
    from flowguard.map.common import read_git_paths
    root = _committed_shelf_project(tmp_path)
    _git(root, 'tag', 'v1.0.0')
    _failing_git(tmp_path, monkeypatch, 'ls-tree')
    with pytest.raises(MapError, match='git ls-tree failed in .*simulated ls-tree failure'):
        read_git_paths(root, 'ls-tree', '-r', '--name-only', '-z', 'v1.0.0', '--', 'shelf')

@pytest.mark.parametrize('literal', ['0', '1'])
def test_the_path_probe_reads_names_literally_whatever_the_pathspec_setting(tmp_path, monkeypatch, literal):
    """A name with glob characters is that one file, in a commit and in the index, also under GIT_LITERAL_PATHSPECS."""
    from flowguard.map.common import git_blob
    root = tmp_path / 'repo'
    root.mkdir()
    _git(root, 'init', '-q')
    (root / 'axb.py').write_bytes(b'x\n')
    _git(root, 'add', '-A')
    # Git can store this literal path on Windows, whose filesystem cannot.
    source = tmp_path / 'star-blob'
    source.write_bytes(b'star\n')
    blob = _git(root, 'hash-object', '-w', str(source)).decode().strip()
    _git(root, 'config', 'core.protectNTFS', 'false')
    _git(root, 'update-index', '--add', '--cacheinfo', '100644', blob, 'a*b.py')
    _git(root, 'commit', '-qm', 'base')
    monkeypatch.setenv('GIT_LITERAL_PATHSPECS', literal)
    for revision in ('HEAD', ':'):
        assert git_blob(root, revision, 'a*b.py') == b'star\n', revision
        assert git_blob(root, revision, 'a?b.py') is None, revision
