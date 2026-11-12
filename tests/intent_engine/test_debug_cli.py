"""Optional commands observe real code and keep their uncertainty visible."""
from pathlib import Path
import subprocess
import sys
import uuid

from flowguard.intent import cache, cli
from flowguard.intent.config import load_config
from tests.intent_engine._cli_fixture import display_text


def project(root):
    name = 'view_' + uuid.uuid4().hex
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (root / (name + '.py')).write_text('''# flowguard: sensor LIMIT
def limit(days: int) -> bool:
    return days <= 3
# flowguard: event ENTER
def enter(): pass
# flowguard: event SAVE
def save(): pass
# flowguard: event PUBLISH
def publish(): pass
enter()
publish()
''')
    folder = root / 'tests' / 'intent'
    folder.mkdir(parents=True)
    (folder / 'policy.py').write_text('''from flowguard.intent import flow, Node
PIPELINE = flow('PIPELINE', source='assumed: save before publication',
    nodes=[Node('enter', 'ENTER', start=True), Node('save', 'SAVE'), Node('publish', 'PUBLISH', end=True)],
    edges=[('enter', 'save'), ('save', 'publish')])
''')
    return name, load_config(root)


def test_try_cli_parses_literal_and_uses_source_point(tmp_path, capsys):
    _, cfg = project(tmp_path)
    # A pure module is independent from the watch fixture's normal entry calls.
    path = next(tmp_path.glob('view_*.py'))
    path.write_text(path.read_text().partition('# flowguard: event ENTER')[0])
    assert cli.main(['--root', str(tmp_path), 'try', 'LIMIT', 'days=4']) == 0
    text = capsys.readouterr().out
    assert "{'days': 4}" in text and 'False' in text
    assert cli.main(['--root', str(tmp_path), 'try', 'LIMIT', 'days=4', '--grid']) == 0
    assert 'representatives evaluated' in capsys.readouterr().out


def test_try_cli_never_executes_input_expression(tmp_path, capsys):
    project(tmp_path)
    marker = tmp_path / 'input-executed'
    expression = "__import__('pathlib').Path(" + repr(str(marker)) + ").touch()"
    assert cli.main(['--root', str(tmp_path), 'try', 'LIMIT', 'days=' + expression]) == 2
    assert not marker.exists()
    assert 'Python literal' in capsys.readouterr().err


def test_watch_cli_checks_real_path_and_saves_historical_view(tmp_path, capsys):
    name, cfg = project(tmp_path)
    assert cli.main(['--root', str(tmp_path), 'watch', '--', sys.executable, name + '.py']) == 1
    text = capsys.readouterr().out
    assert 'target exited 0' in text and 'runtime path enter -> publish is not allowed' in text
    records = cache.observations(cfg)
    assert records['events'] and records['events'][0]['anchor'] == 'ENTER'
    assert cli.main(['--root', str(tmp_path), 'show', 'PIPELINE']) == 1
    text = capsys.readouterr().out
    assert 'historical model observations' in text and 'enter -> save: 0; unobserved' in text
    assert 'runtime path enter -> publish is not allowed' in text


def test_watch_cli_preserves_native_exit_and_unsupported_command_has_no_setup(tmp_path, capsys):
    name, cfg = project(tmp_path)
    path = tmp_path / (name + '.py')
    path.write_text(path.read_text() + 'raise SystemExit(7)\n')
    assert cli.main(['--root', str(tmp_path), 'watch', '--', name + '.py']) == 7
    capsys.readouterr()
    marker = tmp_path / 'must-not-initialize'
    policy = cfg.intent / 'policy.py'
    policy.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
    assert cli.main(['--root', str(tmp_path), 'watch', '--', 'node', 'app.js']) == 2
    assert not marker.exists() and 'unsupported watch' in capsys.readouterr().out


def test_show_anchor_never_executes_intent_and_marks_changed_history(tmp_path, capsys):
    name, cfg = project(tmp_path)
    assert cli.main(['--root', str(tmp_path), 'watch', '--', name + '.py']) == 1
    capsys.readouterr()
    (cfg.intent / 'policy.py').write_text('raise AssertionError("show must not execute intent")\n')
    path = tmp_path / (name + '.py')
    path.write_text(path.read_text().replace('def publish(): pass', 'def publish(): return 8'))
    assert cli.main(['--root', str(tmp_path), 'show', 'PUBLISH']) == 0
    text = capsys.readouterr().out
    assert 'historical observations' in text and 'stale:' in text


def test_model_draft_cli_uses_recorded_path_and_stays_unverified(tmp_path, capsys):
    name, _ = project(tmp_path)
    assert cli.main(['--root', str(tmp_path), 'watch', '--', name + '.py']) == 1
    capsys.readouterr()
    assert cli.main(['--root', str(tmp_path), 'model', 'draft', 'OBSERVED']) == 0
    text = capsys.readouterr().out
    assert '# grey: Observed paths only' in text and "MODEL = flow('OBSERVED'" in text
    assert "anchor='SAVE'" not in text and "anchor='PUBLISH'" in text
    compile(text, '<draft>', 'exec')


def test_context_try_cli_reports_non_json_context_as_not_compared(tmp_path, capsys):
    name = 'context_' + uuid.uuid4().hex
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (tmp_path / (name + '.py')).write_text('''import sqlite3
# flowguard: sensor LIMIT calibrated_by=tests/test_case.py::test_limit
def limit(db: sqlite3.Connection, days: int, enabled: bool) -> bool:
    return days <= 3 and enabled and db.execute('SELECT 6').fetchone()[0] == 6
''')
    tests = tmp_path / 'tests'
    tests.mkdir()
    (tests / 'test_case.py').write_text('''import sqlite3
from ''' + name + ''' import limit
def test_limit():
    with sqlite3.connect(':memory:') as db:
        assert limit(db, 2, True) is True
''')
    # A real command owns one top-level Session; an SDK test never nests one.
    result = subprocess.run([sys.executable, '-m', 'flowguard', '--root', str(tmp_path), 'try', 'LIMIT', 'days=4'],
                            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert 'not compared' in result.stdout and 'JSON' in result.stdout


def test_context_try_cli_refuses_a_test_that_does_not_call_the_anchor(tmp_path, capsys):
    name = 'context_' + uuid.uuid4().hex
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (tmp_path / (name + '.py')).write_text('''# flowguard: sensor LIMIT calibrated_by=tests/test_case.py::test_limit
def limit(db: object, days: int) -> bool:
    return days <= 3
''')
    tests = tmp_path / 'tests'
    tests.mkdir()
    (tests / 'test_case.py').write_text('def test_limit(): pass\n')
    result = subprocess.run([sys.executable, '-m', 'flowguard', '--root', str(tmp_path), 'try', 'LIMIT', 'days=4'],
                            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert '0 readings' in result.stdout


def test_context_try_does_not_replay_writes_or_replace_real_context(tmp_path, capsys):
    name = 'context_' + uuid.uuid4().hex
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (tmp_path / (name + '.py')).write_text('''# flowguard: sensor LIMIT calibrated_by=tests/test_case.py::test_limit
def limit(db: object, days: int) -> bool:
    db.append(days)
    return days <= 3
''')
    tests = tmp_path / 'tests'
    tests.mkdir()
    (tests / 'test_case.py').write_text('''from ''' + name + ''' import limit
def test_limit():
    db = []
    assert limit(db, 2) is True
    assert db == [2]
''')
    for inputs, code, expected in ((['days=4'], 2, 'not compared: uses attribute append'), (['days=4', 'db=1'], 2, 'context inputs cannot be replaced')):
        result = subprocess.run([sys.executable, '-m', 'flowguard', '--root', str(tmp_path), 'try', 'LIMIT', *inputs],
                                cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)
        # The ordinary call still leaves only [2]; the closed engine refuses the mutating method.
        assert result.returncode == code, (result.stdout, result.stderr)
        assert expected in display_text(result.stdout)
        assert 'ordinary test exited' not in result.stdout


def test_context_try_uses_json_inputs_without_replacing_the_ordinary_call(tmp_path):
    name = 'context_' + uuid.uuid4().hex
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (tmp_path / (name + '.py')).write_text('''# flowguard: sensor LIMIT calibrated_by=tests/test_case.py::test_limit
def limit(config: dict, days: int) -> bool:
    return days <= config['limit']
''')
    tests = tmp_path / 'tests'; tests.mkdir()
    (tests / 'test_case.py').write_text('from ' + name + ' import limit\n' + '''from pathlib import Path
def test_limit():
    with open(Path(__file__).with_name('runs.log'), 'a', encoding='utf-8') as log:
        log.write('run\\n')
    config = {'limit': 3}
    assert limit(config, 2) is True
    assert config == {'limit': 3}
''')
    result = subprocess.run([sys.executable, '-m', 'flowguard', '--root', str(tmp_path), 'try', 'LIMIT', 'days=4'],
                            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    # The deprecated command runs the named test once, ordinarily, in its own process, never more.
    assert (tests / 'runs.log').read_text(encoding='utf-8').split() == ['run']
    # a Windows console escapes the arrow (`\u2192`): read the text a reader sees, as the test above does
    assert "{'days': 4} -> False" in display_text(result.stdout) and 'ordinary call unchanged' in result.stdout


def test_watch_and_model_show_never_hide_a_model_load_error(tmp_path, capsys):
    name, cfg = project(tmp_path)
    policy = cfg.intent / 'policy.py'
    policy.write_text(policy.read_text() + 'raise RuntimeError("broken current model")\n')
    assert cli.main(['--root', str(tmp_path), 'watch', '--', name + '.py']) == 1
    assert 'broken current model' in capsys.readouterr().out
    assert cli.main(['--root', str(tmp_path), 'show', 'PIPELINE']) == 1
    assert 'broken current model' in capsys.readouterr().out
