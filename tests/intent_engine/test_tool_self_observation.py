"""The running FlowGuard never auto-observes its own changed observation code.

In FlowGuard's own repository an uncommitted edit to ``Runtime.observe`` made
the plugin hook that very method as a changed function; every call then
re-entered the hook without end and the test run never finished.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap


SOURCE = Path(__file__).resolve().parents[2]


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def test_changed_runtime_observe_in_the_running_tool_is_not_hooked(tmp_path):
    root = tmp_path / 'tool'
    shutil.copytree(SOURCE / 'flowguard', root / 'flowguard', ignore=shutil.ignore_patterns('__pycache__'))
    (root / 'tests').mkdir()
    (root / 'tests/test_observe.py').write_text(textwrap.dedent('''
        import inspect
        from flowguard.intent.runtime import Runtime

        def positive(x: int) -> bool:
            return x > 0

        def test_observe_runs_once(tmp_path):
            runtime = Runtime(tmp_path)
            assert runtime.observe(positive, inspect.signature(positive).bind(1)) is True
    ''').lstrip())
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'tool copy')
    runtime = root / 'flowguard/intent/runtime.py'
    text = runtime.read_text()
    marker = '        owner = sites.unwrap(owner or original)\n'
    assert text.count(marker) == 1
    runtime.write_text(text.replace(marker, marker + '        observed_by = name\n'))
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, str(root), '-q', '-p', 'no:cacheprovider'],
                            cwd=root, capture_output=True, text=True, timeout=120)
    text = result.stdout + result.stderr
    assert str(root / 'flowguard') in subprocess.run(
        [sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import flowguard; print(flowguard.__file__)', str(root)],
        capture_output=True, text=True, check=True).stdout, 'the copy must be the running tool'
    assert 'RecursionError' not in text, text[-3000:]
    assert result.returncode == 0 and '1 passed' in text, text[-3000:]
