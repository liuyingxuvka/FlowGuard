"""Ownership exclusions retain real filesystem boundaries and root order."""
from pathlib import Path
import sys

import pytest

from flowguard.intent import imports


def write(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('VALUE = 1\n')
    return path.resolve()


def test_ownership_keeps_real_project_environment_and_sdk_boundaries(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    normal = write(root / 'normal.py')
    outside = write(tmp_path / 'outside' / 'normal.py')
    sdk = root / 'sdk'
    sdk_source = write(sdk / 'module.py')
    sibling = write(root / 'sdk_extra' / 'module.py')
    environment = root / 'environment'
    write(environment / 'pyvenv.cfg')
    virtual_source = write(environment / 'lib' / 'python3.x' / 'packages' / 'module.py')
    package = write(root / 'site-packages' / 'package' / 'module.py')
    monkeypatch.setattr(imports, '_SDK', sdk.resolve())
    finder = imports._Finder()
    finder.root = finder.host = root.resolve()
    for path in (normal, sdk_source, sibling):
        assert finder.owns(str(path)) is True
    for path in (outside, virtual_source, package):
        assert finder.owns(str(path)) is False
    assert finder.owns(None) is False
    assert finder.application(normal, root) is True
    assert finder.application(sibling, root) is True
    for path in (outside, virtual_source, package, sdk_source):
        assert finder.application(path, root) is False
    interpreter_source = Path(sys.prefix) / 'lib' / 'example.py'
    finder.root = finder.host = Path(sys.prefix).parent
    assert finder.owns(str(interpreter_source)) is False


def test_resolved_sdk_symlink_keeps_the_sdk_exclusion(tmp_path, monkeypatch):
    sdk = tmp_path / 'sdk'
    actual_sdk = write(sdk / 'module.py')
    monkeypatch.setattr(imports, '_SDK', sdk.resolve())
    link = tmp_path / 'sdk_link.py'
    try:
        link.symlink_to(actual_sdk)
    except OSError as error:
        if sys.platform == 'win32' and getattr(error, 'winerror', None) == 1314:
            pytest.skip('This Windows host does not grant symbolic-link creation.')
        raise
    assert imports._Finder().application(link.resolve(), tmp_path) is False


def test_equal_roots_remove_only_the_duplicate_false_lookup(tmp_path, monkeypatch):
    root = (tmp_path / 'project').resolve()
    normal = write(root / 'normal.py')
    host_source = write(tmp_path / 'host' / 'module.py')
    actual, calls = imports.project_code, []
    def counted(filename, project):
        calls.append(project)
        return actual(filename, project)
    monkeypatch.setattr(imports, 'project_code', counted)
    finder = imports._Finder()
    finder.root = finder.host = root
    assert finder.owns(str(host_source)) is False
    assert calls == [root]
    calls.clear()
    assert finder.owns(str(normal)) is True
    assert calls == [root]
    calls.clear()
    finder.host = host_source.parent
    assert finder.owns(str(host_source)) is True
    assert calls == [root, host_source.parent]
    calls.clear()
    finder.root = finder.host = None
    assert finder.owns(str(normal)) is False and calls == []


def test_sdk_exclusion_does_not_change_private_nonpath_short_circuit(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    sdk = root / 'sdk'
    actual_sdk = write(sdk / 'module.py')
    normal = write(root / 'normal.py')
    monkeypatch.setattr(imports, '_SDK', sdk.resolve())
    finder = imports._Finder()
    assert finder.application(None, root) is False
    assert finder.application(str(tmp_path / 'outside.py'), root) is False
    with pytest.raises(AttributeError):
        finder.application(str(normal), root)
    with pytest.raises(AttributeError):
        finder.application(str(actual_sdk), root)
