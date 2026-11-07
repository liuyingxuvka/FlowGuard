"""Nested real pytest sessions cannot truncate or close the outer diagnostic log."""
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from flowguard.intent import cli


def execute(root, source):
    (root/'tests').mkdir(exist_ok=True)
    (root/'pyproject.toml').write_text('[tool.pytest.ini_options]\naddopts="-p flowguard.intent.plugin --flowguard-diagnose"\n')
    (root/'tests/test_parent.py').write_text(textwrap.dedent(source))
    command = [sys.executable, '-c',
               'import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;raise SystemExit(pytest.main(sys.argv[1:]))',
               str(Path(cli.__file__).resolve().parents[2]), '-q', 'tests/test_parent.py']
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    raw = (root/'.flowguard/cache/anchor-events.jsonl').read_text()
    assert '\x00' not in raw
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [row['value'] for row in rows if row['kind'] == 'marker'] == ['before', 'after']
    assert sum(row['kind'] == 'closed' for row in rows) == 1
    return rows


@pytest.mark.parametrize('wrong', [False, True])
def test_addopts_nested_pytest_shares_live_parent_writer_without_closing_it(tmp_path, wrong):
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests/test_child.py').write_text(textwrap.dedent(f'''
        def test_child(request):
            state = request.config._flowguard_intent
            assert state.diagnostics is state.previous_session.diagnostics
            assert state.owns_diagnostics is False
            assert {not wrong}
    '''))
    source = f'''
        import pytest
        def test_parent(request):
            state = request.config._flowguard_intent
            writer = state.diagnostics
            writer.write(dict(kind='marker', value='before'))
            assert int(pytest.main(['-q', 'tests/test_child.py'])) == {int(wrong)}
            assert writer.saved is not None
            assert state.diagnostics is writer
            writer.write(dict(kind='marker', value='after'))
    '''
    rows = execute(tmp_path, source)
    sessions = [row for row in rows if row['kind'] == 'session']
    assert len(sessions) == 2 and sessions[0]['nested'] is False and sessions[1]['nested'] is True


def test_addopts_private_calibration_never_reopens_parent_diagnostic_file(tmp_path):
    (tmp_path/'tests').mkdir()
    (tmp_path/'app.py').write_text(
        '# flowguard: sensor LIMIT(x: count) -> allowed: bool calibrated_by=tests/test_probe.py::test_probe\n'
        'def limit(x: int) -> bool:\n    return x <= 3\n')
    (tmp_path/'tests/test_probe.py').write_text(textwrap.dedent('''
        from app import limit
        from flowguard.intent.calibration import probe_context
        def test_probe(request):
            state = request.config._flowguard_intent
            assert probe_context(request.config)
            assert state.diagnostics is None
            assert limit(2) is True
    '''))
    rows = execute(tmp_path, '''
        from pathlib import Path
        from flowguard.intent import anchors, calibration
        def test_parent(request):
            state = request.config._flowguard_intent
            writer = state.diagnostics
            writer.write(dict(kind='marker', value='before'))
            root = Path.cwd()
            anchor = anchors.collect_sources(root, [('app.py', 'app')]).entries[0]
            result = calibration._stage(root, anchor, {}, 'baseline')
            assert result['status'] == 'ok' and result['pytest_exit'] == 0, result
            assert writer.saved is not None
            writer.write(dict(kind='marker', value='after'))
    ''')
    assert sum(row['kind'] == 'session' for row in rows) == 1


def test_same_node_reentry_pairs_each_actual_session_without_changing_model_results(tmp_path):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'tests/intent/events.py').write_text(
        'from flowguard.intent import flow,Node\n'
        'flow("RUN",source="assumed: one actual run returns",nodes=[Node("begin","RUN",phase="call"),'
        'Node("end","RUN",phase="return")],edges=[("begin","end")])\n')
    (tmp_path/'tests/test_flowguard_intent.py').write_text(cli.SENTINEL)
    (tmp_path/'app.py').write_text(textwrap.dedent('''
        import time
        import pytest
        entered = False
        # flowguard: event RUN()
        def run():
            global entered
            if entered:
                time.sleep(.01)
                return 0
            entered = True
            return int(pytest.main(['-q', 'tests/intent/events.py',
                'tests/test_reentry.py::test_reentry', 'tests/test_flowguard_intent.py']))
    '''))
    (tmp_path/'tests/test_reentry.py').write_text(textwrap.dedent('''
        import json
        from pathlib import Path
        import app
        def test_reentry(request):
            state = request.config._flowguard_intent
            if app.entered:
                assert app.run() == 0
                return
            writer = state.diagnostics
            if writer is not None:
                writer.write(dict(kind='marker', value='before'))
            def save_results():
                summary = {item: {name: value.get(name) for name in ('verdict', 'red', 'grey')}
                           for item, value in state.results.items()}
                Path('model-results.json').write_text(json.dumps(summary, sort_keys=True))
            request.config.add_cleanup(save_results)
            assert app.run() == 0
            if writer is not None:
                assert writer.saved is not None
                writer.write(dict(kind='marker', value='after'))
    '''))
    outcomes = []
    command = [sys.executable, '-c',
               'import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;raise SystemExit(pytest.main(sys.argv[1:]))',
               str(Path(cli.__file__).resolve().parents[2]), '-q', 'tests/intent/events.py',
               'tests/test_reentry.py::test_reentry', 'tests/test_flowguard_intent.py']
    for enabled in (False, True):
        (tmp_path/'pyproject.toml').write_text(
            '[tool.pytest.ini_options]\naddopts="-p flowguard.intent.plugin'
            + (' --flowguard-diagnose' if enabled else '') + '"\n')
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
        # The original model rejects the parent's repeated call/return path.
        # Diagnostics must preserve that real red, rather than make it green.
        assert result.returncode == 1, (command, result.stdout, result.stderr)
        outcomes.append(json.loads((tmp_path/'model-results.json').read_text()))
        if not enabled:
            assert not (tmp_path/'.flowguard/cache/anchor-events.jsonl').exists()
    assert outcomes[0] == outcomes[1]
    assert any(value['verdict'] == 'red' for value in outcomes[0].values())
    raw = (tmp_path/'.flowguard/cache/anchor-events.jsonl').read_text()
    assert '\x00' not in raw
    rows = [json.loads(line) for line in raw.splitlines()]
    sessions = [row for row in rows if row['kind'] == 'session']
    assert len(sessions) == 2 and sessions[0]['scope_id'] != sessions[1]['scope_id']
    assert [row['value'] for row in rows if row['kind'] == 'marker'] == ['before', 'after']
    assert sum(row['kind'] == 'closed' for row in rows) == 1
    events = [row for row in rows if row['kind'] == 'event' and row['anchor'] == 'RUN']
    def key(row):
        return tuple(row['scope_id']), row['case'], row['site'], row['occurrence']
    calls = {key(row): row for row in events if row['phase'] == 'call'}
    returns = {key(row): row for row in events if row['phase'] == 'return'}
    assert len(calls) == len(returns) == 3 and calls.keys() == returns.keys()
    assert all(row['elapsed_ns'] == row['monotonic_ns']-calls[item]['monotonic_ns']
               for item, row in returns.items())
    outer = next(row for row in returns.values() if row['scope_id'] == sessions[0]['scope_id'] and row['occurrence'] == 1)
    inner = next(row for row in returns.values() if row['scope_id'] == sessions[1]['scope_id'])
    assert outer['elapsed_ns'] is not None and outer['elapsed_ns'] >= inner['elapsed_ns'] > 0
    assert all(row['scope_id'] in [session['scope_id'] for session in sessions]
               for row in rows if row['kind'] == 'validation')
