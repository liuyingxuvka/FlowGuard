"""show NAME and model draft read what an ordinary pytest run just observed.

In 4.0 a plain pytest run recorded no anchor events unless the project had flow
models, a working-tree change, or ran under check; show and model draft were
empty until check had run once.
"""
from pathlib import Path
import subprocess
import sys
import textwrap

from flowguard.intent import cli


SOURCE = Path(__file__).resolve().parents[2]


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def project(root):
    (root / 'tests').mkdir(parents=True)
    (root / 'app.py').write_text(textwrap.dedent('''
        # flowguard: sensor LIMIT
        def limit(days: int) -> bool:
            return days <= 3

        # flowguard: event ENTER
        def enter():
            pass

        # flowguard: event SAVE
        def save():
            pass

        # flowguard: event PUBLISH
        def publish():
            pass
    ''').lstrip())
    (root / 'tests/test_app.py').write_text(textwrap.dedent('''
        from app import enter, limit, publish

        def test_release():
            enter()
            publish()
            assert limit(2) is True
    ''').lstrip())
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    return root


def test_show_and_model_draft_have_data_after_plain_pytest(tmp_path, capsys):
    root = project(tmp_path / 'views')
    assert not (root / '.flowguard').exists(), 'no check and no earlier run'
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, str(SOURCE), '-q', '-p', 'no:cacheprovider'],
                            cwd=root, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0 and '1 passed' in result.stdout, result.stdout + result.stderr
    assert cli.main(['--root', str(root), 'show', 'PUBLISH']) == 0
    text = capsys.readouterr().out
    assert 'PUBLISH: historical observations' in text, text
    assert "{'call': 1, 'return': 1}" in text, text
    assert cli.main(['--root', str(root), 'show', 'LIMIT']) == 0
    text = capsys.readouterr().out
    assert "results: {'True': 1}" in text, text
    assert cli.main(['--root', str(root), 'model', 'draft', 'OBSERVED']) == 0
    text = capsys.readouterr().out
    assert "MODEL = flow('OBSERVED'" in text and "anchor='PUBLISH'" in text and "anchor='ENTER'" in text, text
    assert "anchor='SAVE'" not in text, 'only the observed path is drafted'
    compile(text, '<draft>', 'exec')
