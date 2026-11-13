"""One committed file with a syntax error leaves only that file unknown.

The real case was a stray ``_tmp_*.py`` in a project: the plugin parsed it while
indexing source anchors and pytest ended with INTERNALERROR. The file must stay
grey by itself, and ``[tool.flowguard] exclude`` must keep it out entirely.
"""
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests.intent_engine._cli_fixture import display_text, main as cli_main


BROKEN = 'import sys\nsys.path.insert(0, "vendor")\ndef broken(:\n    pass\n'


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=30).stdout


def _project(root, *, exclude=False, rule=False):
    (root / 'tests').mkdir(parents=True)
    (root / 'policy.py').write_text(textwrap.dedent('''
        # flowguard: sensor LIMIT(days: day) -> allowed: bool
        def accept(days: int) -> bool:
            return days <= 3
    ''').lstrip())
    (root / '_tmp_x.py').write_text(BROKEN)
    (root / 'tests/test_policy.py').write_text('from policy import accept\ndef test_accept(): assert accept(2)\n')
    if rule:
        (root / 'tests/intent').mkdir()
        (root / 'tests/intent/decisions.py').write_text(textwrap.dedent('''
            from flowguard.intent import rule, row
            @rule('LIMIT', decides='acceptance', fields={'days': int}, anchor='LIMIT', source='assumed: three days')
            def LIMIT(days):
                return days <= 3
            LIMIT.rows(row(days=4, expect=False, why='fourth day refused'))
        ''').lstrip())
        (root / 'tests/test_flowguard_intent.py').write_text(
            'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n' + ('exclude = ["_tmp_*.py"]\n' if exclude else '')
                                         + '\n[tool.pytest.ini_options]\npythonpath = ["."]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline with a stray broken file')
    # A working-tree change starts the source observations that index anchors.
    source = root / 'policy.py'
    source.write_text(source.read_text().replace('days <= 3', 'days < 4'))
    return root


def _pytest(root):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    source = str(Path(__file__).resolve().parents[2])
    return subprocess.run([sys.executable, '-c', bootstrap, source, '-q', '-p', 'no:cacheprovider'],
                          cwd=root, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize('rule', [False, True])
def test_broken_file_is_grey_by_itself_in_ordinary_pytest(tmp_path, rule):
    root = _project(tmp_path / 'project', rule=rule)
    result = _pytest(root)
    text = display_text(result)
    assert 'INTERNALERROR' not in text, text
    assert result.returncode == 0, text
    assert 'passed' in text and 'failed' not in text, text
    assert '_tmp_x.py' in text and 'cannot be parsed' in text, 'the unreadable file is reported, not hidden'
    assert not any(line.startswith('red') and '_tmp_x.py' in line for line in text.splitlines()), text


def test_broken_file_does_not_crash_check(tmp_path, capsys):
    root = _project(tmp_path / 'project')
    status = cli_main(['--root', str(root), 'check'], cwd=root)
    captured = capsys.readouterr()
    text = display_text(captured.out + captured.err)
    assert 'Traceback' not in text and 'SyntaxError' not in text.replace('invalid syntax', ''), text
    assert status == 0, text


def test_exclude_keeps_the_broken_file_out_of_pytest_and_check(tmp_path, capsys):
    root = _project(tmp_path / 'project', exclude=True)
    result = _pytest(root)
    text = display_text(result)
    assert 'INTERNALERROR' not in text and result.returncode == 0, text
    assert '_tmp_x.py' not in text, text
    status = cli_main(['--root', str(root), 'check'], cwd=root)
    captured = capsys.readouterr()
    checked = display_text(captured.out + captured.err)
    assert status == 0 and '_tmp_x.py' not in checked and 'Traceback' not in checked, checked
