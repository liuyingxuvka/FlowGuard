"""show NAME reads what a real test run observed and keeps its uncertainty visible."""
from pathlib import Path
import subprocess
import sys

from flowguard.intent import cache, cli
from flowguard.intent.config import load_config

SOURCE = Path(__file__).resolve().parents[2]


def project(root):
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\naddopts = "-p flowguard.intent.plugin"\n')
    (root / 'app.py').write_text('''# flowguard: sensor LIMIT
def limit(days: int) -> bool:
    return days <= 3
# flowguard: event ENTER
def enter(): pass
# flowguard: event SAVE
def save(): pass
# flowguard: event PUBLISH
def publish(): pass
''')
    (root / 'tests/test_app.py').write_text('from app import enter, publish\n\ndef test_release():\n    enter()\n    publish()\n')
    (root / 'tests/intent/policy.py').write_text('''from flowguard.intent import flow, Node
PIPELINE = flow('PIPELINE', source='assumed: save before publication',
    nodes=[Node('enter', 'ENTER', start=True), Node('save', 'SAVE'), Node('publish', 'PUBLISH', end=True)],
    edges=[('enter', 'save'), ('save', 'publish')])
''')
    return load_config(root)


def run_tests(root):
    """The project's own pytest run with the plugin, in its own process: it saves the anchor events show reads."""
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    return subprocess.run([sys.executable, '-c', bootstrap, str(SOURCE), '-q', '-p', 'no:cacheprovider', 'tests/test_app.py'],
                          cwd=root, capture_output=True, text=True, timeout=120)


def test_show_flow_checks_the_observed_path_of_the_last_test_run(tmp_path, capsys):
    cfg = project(tmp_path)
    result = run_tests(tmp_path)
    assert '1 passed' in result.stdout, result.stdout + result.stderr
    records = cache.observations(cfg)
    assert records['events'] and records['events'][0]['anchor'] == 'ENTER'
    assert cli.main(['--root', str(tmp_path), 'show', 'PIPELINE']) == 1
    text = capsys.readouterr().out
    assert 'historical model observations' in text and 'enter -> save: 0; unobserved' in text
    assert 'runtime path enter -> publish is not allowed' in text


def test_show_anchor_never_executes_intent_and_marks_changed_history(tmp_path, capsys):
    cfg = project(tmp_path)
    result = run_tests(tmp_path)
    assert '1 passed' in result.stdout, result.stdout + result.stderr
    (cfg.intent / 'policy.py').write_text('raise AssertionError("show must not execute intent")\n')
    path = tmp_path / 'app.py'
    path.write_text(path.read_text().replace('def publish(): pass', 'def publish(): return 8'))
    assert cli.main(['--root', str(tmp_path), 'show', 'PUBLISH']) == 0
    text = capsys.readouterr().out
    assert 'historical observations' in text and 'stale:' in text


def test_show_model_never_hides_a_model_load_error(tmp_path, capsys):
    cfg = project(tmp_path)
    policy = cfg.intent / 'policy.py'
    policy.write_text(policy.read_text() + 'raise RuntimeError("broken current model")\n')
    assert cli.main(['--root', str(tmp_path), 'show', 'PIPELINE']) == 1
    assert 'broken current model' in capsys.readouterr().out
