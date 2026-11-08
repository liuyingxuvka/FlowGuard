"""Python launcher spelling must not change real watch execution or exit state."""
import pytest

from flowguard.intent import debug
from tests.intent_engine.test_debug_views import project, restored, state


@pytest.mark.parametrize('executable', ['python.EXE', 'Python3.12.Exe'])
@pytest.mark.parametrize('ending,expected,status', [
    ('', 0, 'ok'), ('raise SystemExit(7)', 7, 'red'),
    ('raise ValueError("native failure")', 1, 'red'),
])
def test_python_launcher_case_runs_real_script_and_restores_state(tmp_path, executable, ending, expected, status):
    cfg, index, name = project(tmp_path,
        '# flowguard: event DONE\ndef done(): return 7\ndone()\n' + ending + '\n')
    # watch runs in this interpreter, so the launcher need not exist. Use a
    # native absolute path on each OS, including a space before the basename.
    launcher = str(tmp_path / 'Python bin' / executable)
    before = state()
    result = debug.watch(cfg, [launcher, name + '.py'], index=index)
    restored(before)
    assert result['executed'] is True and result['exit_code'] == expected and result['status'] == status, result
    assert [(event.anchor, event.phase) for event in result['events']] == [('DONE', 'call'), ('DONE', 'return')]
    assert result['events'][-1].result == 7
    if expected == 1:
        assert 'ValueError: native failure' in result['error']


def test_non_python_exe_name_is_refused_before_script_execution(tmp_path):
    marker = tmp_path / 'must-not-execute'
    cfg, index, name = project(tmp_path, 'from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
    before = state()
    result = debug.watch(cfg, ['python-helper.EXE', name + '.py'], index=index)
    restored(before)
    assert result['executed'] is False and result['exit_code'] == 2 and result['status'] == 'grey', result
    assert result['events'] == [] and not marker.exists()
