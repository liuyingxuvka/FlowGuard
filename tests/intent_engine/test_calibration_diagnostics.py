"""The 4.0 ordinary runner retains real native collection failures."""
from flowguard.intent import cache
from flowguard.intent.config import load_config
from tests.intent_engine import _cli_fixture as cli_fixture
from tests.intent_engine.test_calibration import project


def test_calibration_collection_failure_keeps_the_native_error(tmp_path, capsys):
    project(tmp_path, """# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
""", """from policy import limit
raise ImportError('editable collection diagnostic control')
def test_native():
    assert limit(2) is True
""")
    cfg = load_config(tmp_path)
    # pytest stops at the collection error (exit 2): check's one red line says so, the native error is in its output
    assert cli_fixture.check(cfg, everything=True) == 1
    text = capsys.readouterr().out
    assert 'ImportError: editable collection diagnostic control' in text
    assert 'red: pytest: exit 2 -> read .flowguard/cache/check-output.txt and correct the reported error' in text.splitlines(), text
    assert not cache.read(cfg)['results'], 'a collection failure cannot verify a source outcome'


def test_collection_diagnostics_do_not_depend_on_warm_traceback_rendering(tmp_path, capsys):
    project(tmp_path, """# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
""", """from policy import limit
raise AssertionError('same native failure')
def test_native():
    assert limit(2) is True
""")
    cfg = load_config(tmp_path)
    for _ in range(2):
        assert cli_fixture.check(cfg, everything=True) == 1
        text = capsys.readouterr().out
        assert 'AssertionError: same native failure' in text
        assert 'red: pytest: exit 2 -> read .flowguard/cache/check-output.txt and correct the reported error' in text.splitlines(), text
        assert not cache.read(cfg)['results']
