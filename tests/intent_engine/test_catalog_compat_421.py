"""FlowGuard 4.2.1 reads a project that has the two new files, .flowguard/rules.toml and .flowguard/known.toml,
without a red line (design 6.2): it reads neither file, and 4.3 adds no `[tool.flowguard]` key it would refuse."""
import ast
import io
from pathlib import Path
import re
import site
import subprocess
import sys
import tarfile
import textwrap

ROOT = Path(__file__).resolve().parents[2]
RELEASE = 'ec55562d'             # the 4.2.1 release commit (CI checks out the whole history)


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, timeout=120).stdout


def _release_421(target):
    """The `flowguard` package of the 4.2.1 commit, unpacked into `target`."""
    with tarfile.open(fileobj=io.BytesIO(_git(ROOT, 'archive', '--format=tar', RELEASE, 'flowguard'))) as archive:
        archive.extractall(target, filter='data')
    assert (target / 'flowguard/__init__.py').read_text(encoding='utf-8').count('__version__ = "4.2.1"') == 1
    return target


def _run_421(release, project, code):
    """`code` under 4.2.1: `-I -S` reads no PYTHONPATH and no .pth file (so not the editable 4.3 install); the
    release comes first on the path, then this interpreter's site-packages for its dependencies."""
    paths = [str(release), *site.getsitepackages()]
    boot = f'import sys; sys.path[:0] = {paths!r}; import flowguard; assert flowguard.__version__ == "4.2.1"; ' + code
    return subprocess.run([sys.executable, '-I', '-S', '-c', boot], cwd=project, capture_output=True, text=True,
                          encoding='utf-8', timeout=600)


FILES = {
    '.gitignore': '.flowguard/cache/\n__pycache__/\n.pytest_cache/\n',
    'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n',
    'shop/__init__.py': '',
    'shop/fees.py': '''
        WEEKS = 52


        def fee(days):
            return days * 2
    ''',
    'tests/test_fees.py': '''
        from shop.fees import fee


        def test_fee():
            assert fee(2) == 4
    ''',
}

CATALOG = {
    '.flowguard/rules.toml': '''
        [rule.fees]
        text = "A fee is two per day."
        source = 'R1 "Two per day."'
    ''',
    '.flowguard/known.toml': '''
        [known.weeks]
        sites = ["shop/fees.py:WEEKS"]
        why = "52 is not every ISO year's week count"
        act = "ask"
        ask = "Should a year have 53 weeks when ISO says so?"

        [known.broken]
        act = "later"
    ''',
}


def _write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8', newline='\n')


def test_flowguard_421_checks_a_project_with_rules_toml_and_known_toml_without_red(tmp_path):
    release = _release_421(tmp_path / 'release')
    project = tmp_path / 'project'
    _write(project, FILES)
    _git(project, 'init', '-q', '-b', 'main')
    initialized = _run_421(release, project, 'from flowguard.intent.cli import main; sys.exit(main(["init"]))')
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    _write(project, CATALOG)        # a valid rule and entry, and one 4.3 refuses: 4.2.1 reads neither file
    _git(project, 'add', '.')
    _git(project, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'baseline')
    (project / 'shop/fees.py').write_text('WEEKS = 52\n\n\ndef fee(days):\n    return 2 * days\n', encoding='utf-8')
    static = _run_421(release, project, 'from flowguard.intent.cli import main; sys.exit(main(["check", "--static"]))')
    assert static.returncode == 0 and not re.search(r'^red', static.stdout + static.stderr, re.M), static.stdout + static.stderr
    tests = _run_421(release, project, 'import pytest; sys.exit(pytest.main(["-q", "-p", "no:cacheprovider"]))')
    assert tests.returncode == 0 and '2 passed' in tests.stdout, tests.stdout + tests.stderr
    assert not re.search(r'^red', tests.stdout, re.M), tests.stdout


def _allowed(text):
    """The `[tool.flowguard]` keys `load_config` accepts, read from its source."""
    match = re.search(r"allowed = (\{[^}]*\})", text)
    return ast.literal_eval(match[1])


def test_flowguard_43_adds_no_configuration_key_that_421_refuses():
    old = _git(ROOT, 'show', f'{RELEASE}:flowguard/intent/config.py').decode('utf-8')
    now = (ROOT / 'flowguard/intent/config.py').read_text(encoding='utf-8')
    assert _allowed(now) == _allowed(old) == {'roots', 'intent', 'exclude', 'authority_docs', 'screen_lines',
                                              'check_lines', 'skip_policy', 'ledger', 'propagate', 'archives'}
