"""A nested calibration run must leave its caller's import paths intact."""
import sys

import pytest

from flowguard.intent import anchors, calibration, config


@pytest.fixture
def import_state():
    path, entries = sys.path, sys.path[:]
    inserted = config._INSERTED_PATHS.copy()
    try:
        yield
    finally:
        path[:] = entries
        sys.path = path
        config._INSERTED_PATHS.clear()
        config._INSERTED_PATHS.update(inserted)


def test_repeated_native_anchor_stages_restore_exact_paths(tmp_path, import_state):
    tests = tmp_path / 'tests'
    tests.mkdir()
    (tmp_path / 'policy.py').write_text('''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=tests/test_path_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''')
    (tests / 'test_path_policy.py').write_text('''from policy import limit
def test_native(): assert limit(2) is True
''')
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    anchor = anchors.collect_sources(tmp_path, [('policy.py', 'policy')]).entries[0]
    config.setup_path(config.load_config(tmp_path))
    duplicate = str(tmp_path / 'caller-duplicate')
    sys.path.extend([duplicate, duplicate])
    path, entries = sys.path, sys.path[:]
    inserted = config._INSERTED_PATHS.copy()

    for stage, values in [('baseline', {}), ('zero', {}), ('case', {'x': 5}), ('case', {'x': 1})]:
        result = calibration._stage(tmp_path, anchor, values, stage)
        assert result['status'] == 'ok', result
        assert result['pytest_exit'] == (0 if stage == 'baseline' else 1)
        assert sys.path is path
        assert sys.path == entries
        assert config._INSERTED_PATHS == inserted


@pytest.mark.parametrize('error', [RuntimeError('broken session'), KeyboardInterrupt()])
def test_nested_session_exception_restores_path_object_and_ownership(tmp_path, monkeypatch, import_state, error):
    parent, child = tmp_path / 'parent', tmp_path / 'child'
    parent.mkdir()
    child.mkdir()
    config.setup_path(config.load_config(parent))
    path, entries = sys.path, sys.path[:]
    inserted = config._INSERTED_PATHS.copy()
    driver = calibration._Driver(child, None, {}, 'baseline')

    def broken_session(*args, **kwargs):
        config.setup_path(config.load_config(child))
        sys.path = ['nested replacement']
        raise error

    monkeypatch.setattr(pytest, 'main', broken_session)
    with pytest.raises(type(error), match=str(error) or '^$'):
        calibration._run_pytest(child, 'test_unused.py::test_native', driver)
    assert sys.path is path
    assert sys.path == entries
    assert config._INSERTED_PATHS == inserted
    assert not calibration._ACTIVE.get()
    # The next project still removes the parent path that FlowGuard owned.
    config.setup_path(config.load_config(child))
    assert str(parent) not in sys.path
    assert str(child) in sys.path
