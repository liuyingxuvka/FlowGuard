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
    root = _committed_shelf_project(tmp_path)
    _git(root, 'tag', 'v1.0.0')
    _failing_git(tmp_path, monkeypatch, 'ls-tree')
    with pytest.raises(MapError, match='git ls-tree failed in .*simulated ls-tree failure'):
        git_blob(root, 'v1.0.0', 'shelf/loans.py')

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

def test_the_batch_blob_reader_gives_each_path_what_the_single_reader_gives(tmp_path):
    """`git_blobs` reads many paths of one commit in one batch: the same bytes or None per path as `git_blob`, by
    the path as given, also for a name with glob characters, a link and a folder below the repository's top; after
    a new commit it reads that commit's bytes; a missing tree, a missing blob and a folder fail with Git's message as
    `git_blob` does."""
    from flowguard.map.common import git_blobs
    root = _committed_shelf_project(tmp_path)
    write(root, 'shelf/a*b.py', 'star\n') if os.name != 'nt' else None
    write(root, 'shelf/twin.py', 'VALUE = 1\n')
    if os.name != 'nt':
        os.symlink('loans.py', root / 'shelf/link.py')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-qm', 'more')
    paths = ['shelf/loans.py', 'shelf/catalog.py', 'shelf/twin.py', 'shelf/absent.py', 'shelf/a*b.py', 'shelf/a?b.py',
             'shelf/link.py', 'shelf/loans.py', 'absent/deep.py']
    for revision in ('HEAD', 'HEAD~1'):
        assert git_blobs(root, revision, paths) == {path: git_blob(root, revision, path) for path in paths}, revision
    assert git_blobs(root / 'shelf', 'HEAD', ['loans.py', 'catalog.py']) == {
        name: git_blob(root / 'shelf', 'HEAD', name) for name in ('loans.py', 'catalog.py')} == {
        'loans.py': b'def value(): return 1\n', 'catalog.py': b'VALUE = 1\n'}
    write(root, 'shelf/loans.py', 'def value(): return 2\n')
    _git(root, 'commit', '-qam', 'edit')
    assert git_blobs(root, 'HEAD', ['shelf/loans.py']) == {'shelf/loans.py': b'def value(): return 2\n'}
    assert git_blobs(root, 'HEAD', []) == {}
    with pytest.raises(MapError) as single:
        git_blob(root, 'HEAD', 'shelf')
    with pytest.raises(MapError) as batch:
        git_blobs(root, 'HEAD', ['shelf/catalog.py', 'shelf'])
    assert str(batch.value) == str(single.value)
    with pytest.raises(MapError, match='is not in the Git repository'):
        git_blobs(root, 'f' * 40, ['shelf/loans.py'])
    blob = _git(root, 'rev-parse', 'HEAD:shelf/catalog.py').decode().strip()
    blob_object = root / '.git/objects' / blob[:2] / blob[2:]
    blob_object.chmod(blob_object.stat().st_mode | stat.S_IWRITE)
    blob_object.unlink()
    with pytest.raises(MapError) as single:
        git_blob(root, 'HEAD', 'shelf/catalog.py')
    with pytest.raises(MapError) as batch:
        git_blobs(root, 'HEAD', ['shelf/loans.py', 'shelf/catalog.py'])
    assert str(batch.value) == str(single.value) and blob in str(single.value)
    tree = _git(root, 'rev-parse', 'HEAD:shelf').decode().strip()
    tree_object = root / '.git/objects' / tree[:2] / tree[2:]
    tree_object.chmod(tree_object.stat().st_mode | stat.S_IWRITE)
    tree_object.unlink()
    with pytest.raises(MapError, match=tree):
        git_blobs(root, 'HEAD', ['shelf/loans.py', 'shelf/absent.py'])
