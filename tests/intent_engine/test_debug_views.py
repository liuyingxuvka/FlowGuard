"""Optional debugging consumes the same source identities and runtime as tests."""
from dataclasses import asdict
from pathlib import Path
import sys
import uuid

import pytest

from flowguard.intent import anchors, config, debug
from flowguard.intent.flow import Flow, Node


def project(root, source):
    name = 'debug_app_' + uuid.uuid4().hex
    (root / (name + '.py')).write_text(source)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    return config.load_config(root), anchors.collect_sources(root, [(name + '.py', name)]), name


def state():
    return sys.path, sys.path[:], sys.argv, sys.argv[:], Path.cwd(), sys.gettrace(), config._INSERTED_PATHS.copy()


def restored(before):
    assert sys.path is before[0] and sys.path == before[1]
    assert sys.argv is before[2] and sys.argv == before[3]
    assert Path.cwd() == before[4] and sys.gettrace() is before[5]
    assert config._INSERTED_PATHS == before[6]


@pytest.mark.parametrize('comment', ['# flowguard: sensor LIMIT', '# flowguard: sensor LIMIT(x: count) -> allowed: bool'])
def test_try_uses_shared_pure_runtime_and_old_units(tmp_path, comment):
    cfg, index, _ = project(tmp_path, comment + '\ndef limit(x: int) -> bool:\n    return x <= 3\n')
    before = state()
    result = debug.try_anchor(cfg, 'LIMIT', {'x': 4}, index=index)
    restored(before)
    assert result['status'] == 'ok', result
    assert result['value'] is False and result['tested'] > 0


def test_try_grid_evaluates_and_prints_all_rows_when_explicitly_requested(tmp_path):
    parameters = ', '.join(f'{letter}: bool' for letter in 'abcdefghi')
    cfg, index, _ = project(tmp_path, '# flowguard: sensor VOTE\ndef vote(' + parameters + ') -> bool:\n    return a\n')
    result = debug.try_anchor(cfg, 'VOTE', dict.fromkeys('abcdefghi', False), grid=True, index=index)
    assert result['status'] == 'ok', result
    assert result['tested'] == len(result['rows']) == 512
    assert len(result['lines']) == 513
    assert sum('→' in line for line in result['lines']) == 512
    assert sum(value is True for _, value in result['rows']) == 256


def test_context_try_requires_or_delegates_to_current_session_runner(tmp_path):
    cfg, index, _ = project(tmp_path, '# flowguard: sensor AVAILABLE\ndef available(db: object, x: int) -> bool:\n    return db.get(x) is None\n')
    assert debug.try_anchor(cfg, 'AVAILABLE', {'x': 2}, index=index)['status'] == 'grey'
    calls = []
    def runner(actual_cfg, anchor, values, *, grid):
        calls.append((actual_cfg, anchor.target, values, grid))
        return dict(status='ok', lines=['current session'], value=True)
    result = debug.try_anchor(cfg, 'AVAILABLE', {'x': 2}, runner=runner, index=index)
    assert result['value'] is True and calls == [(cfg, index.entries[0].target, {'x': 2}, False)]


def test_try_rejects_side_effects_without_calling_them(tmp_path):
    marker = tmp_path / 'side-effect.txt'
    cfg, index, _ = project(tmp_path, '# flowguard: sensor WRITE\ndef write(x: int) -> bool:\n    open(' + repr(str(marker)) + ', "w").write("bad")\n    return x > 0\n')
    result = debug.try_anchor(cfg, 'WRITE', {'x': 1}, index=index)
    assert result['status'] == 'grey' and not marker.exists()


@pytest.mark.parametrize('exit_text,expected,status', [('', 0, 'ok'), ('raise SystemExit(7)', 7, 'red'), ('raise ValueError("native failure")', 1, 'red')])
def test_watch_keeps_target_exit_and_restores_process_state(tmp_path, exit_text, expected, status):
    cfg, index, name = project(tmp_path, '# flowguard: event DONE\ndef done():\n    return 7\ndone()\n' + exit_text + '\n')
    before = state()
    result = debug.watch(cfg, [sys.executable, name + '.py'], index=index)
    restored(before)
    assert result['exit_code'] == expected and result['status'] == status, result
    assert [(event.anchor, event.phase) for event in result['events']] == [('DONE', 'call'), ('DONE', 'return')]
    assert result['events'][-1].result == 7
    if exit_text.startswith('raise ValueError'):
        assert 'ValueError: native failure' in result['error']


def test_watch_module_arguments_and_keyboard_interrupt_restore(tmp_path):
    cfg, index, name = project(tmp_path, 'import sys\n# flowguard: event ARGUMENTS\ndef arguments():\n    return sys.argv[1:]\narguments()\n')
    before = state()
    result = debug.watch(cfg, ['python', '-m', name, 'given'], index=index)
    restored(before)
    assert result['exit_code'] == 0 and result['events'][-1].result == ['given']
    (tmp_path / (name + '.py')).write_text('raise KeyboardInterrupt()\n')
    with pytest.raises(KeyboardInterrupt):
        debug.watch(cfg, [name + '.py'], index=anchors.Index(()))
    restored(before)


def test_unsupported_watch_does_not_run_command(tmp_path):
    cfg = config.load_config(tmp_path)
    result = debug.watch(cfg, ['node', 'anything.js'])
    assert result['status'] == 'grey' and result['exit_code'] == 2 and not result['executed']


def test_show_history_marks_changed_source_stale(tmp_path):
    cfg, index, name = project(tmp_path, '# flowguard: event DONE\ndef done():\n    return 7\ndone()\n')
    result = debug.watch(cfg, [name + '.py'], index=index)
    shown = debug.show_observation(cfg, 'DONE', index, [asdict(e) for e in result['events']])
    assert shown['status'] == 'ok' and 'historical' in shown['lines'][0]
    path = tmp_path / (name + '.py')
    path.write_text(path.read_text().replace('return 7', 'return 8'))
    current = anchors.collect_sources(tmp_path, [(path.name, name)])
    stale = debug.show_observation(cfg, 'DONE', current, result['events'])
    assert stale['status'] == 'grey' and stale['stale'] == 2
    assert not stale['events'] and any('stale' in line for line in stale['lines'])


def test_show_model_reuses_path_checks_and_counts_unobserved_edges(tmp_path):
    cfg, index, name = project(tmp_path, '# flowguard: event A\ndef a(): pass\n# flowguard: event B\ndef b(): pass\n# flowguard: event C\ndef c(): pass\na()\nc()\n')
    result = debug.watch(cfg, [name + '.py'], index=index)
    model = Flow('STEPS', 'assumed: save before release',
                 (Node('a', 'A', start=True), Node('b', 'B'), Node('c', 'C', end=True)),
                 (('a', 'b'), ('b', 'c')))
    shown = debug.show_observation(cfg, 'STEPS', index, result['events'], model=model)
    assert shown['status'] == 'red' and shown['node_counts'] == {'a': 1, 'c': 1}
    assert shown['edge_counts'] == {('a', 'c'): 1}
    assert any('runtime path a -> c is not allowed' in line for line in shown['lines'])
    assert any('a → b: 0; unobserved' in line for line in shown['lines'])


def test_try_untyped_positional_only_input_and_default(tmp_path):
    cfg, index, _ = project(tmp_path, '# flowguard: sensor LIMIT\ndef limit(x, /, y: int = 3) -> bool:\n    return x <= y\n')
    result = debug.try_anchor(cfg, 'LIMIT', {'x': 4}, index=index)
    assert result['status'] == 'ok' and result['value'] is False, result


def test_watch_restores_trace_when_program_replaces_it_then_raises(tmp_path):
    cfg, index, name = project(tmp_path, 'import sys\n# flowguard: event DONE\ndef done(): return 7\ndone()\ndef trace(frame,event,arg): return trace\nsys.settrace(trace)\nraise ValueError("after replacement")\n')
    before = state()
    result = debug.watch(cfg, [name + '.py'], index=index)
    restored(before)
    assert result['status'] == 'red' and result['exit_code'] == 1
    assert 'ValueError: after replacement' in result['error']


def test_point_try_calls_exact_value_once(tmp_path):
    from flowguard.intent.runtime import Runtime
    cfg, index, name = project(tmp_path, '# flowguard: sensor LIMIT\ndef limit(x: int) -> bool:\n    return x <= 3\n')
    calls = []
    runtime = Runtime(tmp_path)
    with runtime.record(predicate=lambda code: code.co_filename == str(tmp_path / (name + '.py')) and code.co_name == 'limit',
                        callback=lambda frame, event, arg: calls.append(frame.f_locals['x']), private=True, entry_only=True):
        result = debug.try_anchor(cfg, 'LIMIT', {'x': 4}, index=index)
    assert calls == [4] and result['tested'] == 1 and result['value'] is False


def test_point_try_checks_module_initialization_before_import(tmp_path):
    marker = tmp_path / 'must-not-write.txt'
    cfg, index, _ = project(tmp_path, 'from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("bad")\n# flowguard: sensor LIMIT\ndef limit(x: int) -> bool:\n    return x <= 3\n')
    result = debug.try_anchor(cfg, 'LIMIT', {'x': 1}, index=index)
    assert result['status'] == 'grey' and not marker.exists()
