"""Same-session replay does not accumulate collector import paths."""
import sys

import pytest

from flowguard.intent import anchors, calibration, config
from flowguard.intent.runtime import _PRIVATE
from tests.intent_engine._protocol_controls import bind_anchor
from tests.intent_engine._source_fixture import source_sessions


def native_project(root):
    tests = root / 'tests'
    tests.mkdir()
    (root / 'policy_paths.py').write_text('''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=tests/test_path_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''')
    (tests / 'test_path_policy.py').write_text('''from policy_paths import limit
import pytest
@pytest.fixture(autouse=True)
def native_paths(monkeypatch):
    monkeypatch.syspath_prepend('native-fixture-only-path')
def test_native(): assert limit(2) is True
''')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    return anchors.collect_sources(root, [('policy_paths.py', 'policy_paths')]).entries[0]


def test_repeated_native_replays_preserve_paths_without_collecting_again(tmp_path, monkeypatch):
    anchor = native_project(tmp_path)
    scope, item = bind_anchor(tmp_path, anchor)
    duplicate = str(tmp_path / 'caller-duplicate')
    sys.path.extend([duplicate, duplicate])
    path, entries = sys.path, sys.path[:]
    inserted = config._INSERTED_PATHS.copy()
    def forbidden(*args, **kwargs):
        raise AssertionError('same-session observations cannot open or collect another session')
    monkeypatch.setattr(pytest, 'main', forbidden)
    monkeypatch.setattr(pytest.Module, 'collect', forbidden)
    for value, expected in [(2, True), (5, False), (1, True), (5, False)]:
        result = calibration.execute(tmp_path, anchor, {'x': value})
        assert result.status == 'ok' and result.value is expected, result
        assert calibration._context(tmp_path, anchor.calibrated_by) == (scope, item)
        assert sys.path is path and sys.path == entries
        assert config._INSERTED_PATHS == inserted
        assert sys.path.count(duplicate) == 2
        assert 'native-fixture-only-path' not in sys.path

