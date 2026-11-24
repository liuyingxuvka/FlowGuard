"""A pytest session's finish keeps pytest's own outcome (R85): it reads only the sources its tests ran, so a file
deleted or rewritten during the run is not compared; a test that loads a project file by path runs as without
FlowGuard; and FlowGuard's own error at the finish is one red line after pytest's summary (R106, option 1A), never a
traceback in its place. The fixtures take PEMEL Studio's shape (2026-11-23 afternoon notes): `names.py` holds the
reference of `same TITLE`, `comparison_commands.py` its copy and `compare`, and a test acts on the files itself, so
the timing that another agent's save gave there is fixed here."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests._pure_helpers import git, write
from tests.intent_engine._cli_fixture import block, last

SOURCE = str(Path(__file__).resolve().parents[2])
REFERENCE = '# flowguard: same TITLE ref\ndef title(name: str) -> str:\n    return name.strip().title()\n'
COPIES = {
    'same': '# flowguard: same TITLE\ndef title(name: str) -> str:\n    return name.strip().title()\n\n\n'
            'def compare(a, b):\n    return a == b\n',
    'sensor': '# flowguard: sensor COMPARE\ndef compare(a, b):\n    return a == b\n',
    'plain': 'def compare(a, b):\n    return a == b\n',
}
ACTS = {
    'deleted': "subprocess.run(['git', 'rm', '-q', str(COPY)], check=True, cwd=ROOT)",
    'syntax error': "COPY.write_text(COPY.read_text().replace('name.strip().title()', 'name.strip(.title()'))",
    # another FlowGuard run rebuilds the shared map after the deletion, as the agent's own `show` did
    'deleted, map rebuilt': "subprocess.run(['git', 'rm', '-q', str(COPY)], check=True, cwd=ROOT); "
                            "subprocess.run([sys.executable, '-m', 'flowguard', 'show', 'compare'], cwd=ROOT, check=True, "
                            "capture_output=True)",
}


def _project(root, copy, act, *, changed):
    write(root, 'pyproject.toml', '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
                                  'addopts = "-p flowguard.intent.plugin"\n')
    write(root, '.gitignore', '.flowguard/cache/\n__pycache__/\n')
    write(root, 'src/app/__init__.py', '')
    write(root, 'src/app/names.py', REFERENCE)
    write(root, 'src/app/comparison_commands.py', COPIES[copy])
    write(root, 'tests/test_names.py', textwrap.dedent(f'''\
        import pathlib, subprocess, sys
        from app.names import title

        ROOT = pathlib.Path(__file__).resolve().parents[1]
        COPY = ROOT / 'src' / 'app' / 'comparison_commands.py'


        def test_title():
            assert title(" ab ") == "Ab"


        def test_act():
            {act}


        def test_fails():
            assert title("x") == "y"
        '''))
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', 'baseline')
    if changed:     # the task's change: the session builds its map when it starts
        (root / 'src/app/names.py').write_text(REFERENCE + '\n\ndef extra():\n    return 1\n')


def _pytest(root, *options):
    environment = dict(os.environ, PYTHONPATH=SOURCE + os.pathsep + os.environ.get('PYTHONPATH', ''))
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *options], cwd=root,
                          capture_output=True, text=True, timeout=180, env=environment)


def _restore(root):
    git(root, 'reset', '-q', '--hard')
    git(root, 'clean', '-qfdx', '-e', '.flowguard')


@pytest.mark.parametrize('copy, act, changed', [
    ('same', 'deleted', False), ('same', 'syntax error', False), ('same', 'deleted', True),
    ('sensor', 'deleted', True), ('plain', 'deleted, map rebuilt', True), ('same', 'deleted, map rebuilt', True)],
    ids=['copy deleted', 'copy saved with a syntax error', 'copy deleted, map built at start',
         '4.2 spelling deleted', 'plain file deleted, map rebuilt', 'copy deleted, map rebuilt'])
def test_a_file_deleted_or_rewritten_during_the_run_keeps_pytests_outcome(tmp_path, copy, act, changed):
    # 5.0.1 and the 5.1 candidate ended each of these runs in a traceback from the session's finish instead of
    # pytest's failure list and summary: FileNotFoundError from compare_copies or anchors.collect, SyntaxError from
    # compare_copies, KeyError from owners.loosened when another run had rebuilt the map.
    root = tmp_path / 'pemel'
    _project(root, copy, ACTS[act], changed=changed)
    names = (root / 'src/app/names.py').read_text()
    without = _pytest(root, '-o', 'addopts=')
    _restore(root)
    (root / 'src/app/names.py').write_text(names)
    result = _pytest(root)
    output = result.stdout + result.stderr
    assert 'Traceback' not in output and 'INTERNALERROR' not in output, output
    assert result.returncode == without.returncode == 1, output
    assert '1 failed, 2 passed' in result.stdout and 'FAILED tests/test_names.py::test_fails' in result.stdout, output
    lines = block(result)
    assert 'internal error' not in '\n'.join(lines), lines
    if copy == 'same':
        reason = 'its file changed during the run' if act == 'syntax error' else 'its file was deleted during the run'
        assert f'title (src/app/comparison_commands.py:2) -> not a failure\n    {reason}' in last(root), last(root)


def test_a_file_unchanged_during_the_run_keeps_its_comparison(tmp_path):
    # The counterexample: the same copy with a different answer, untouched during the run, stays a red same line.
    root = tmp_path / 'pemel'
    _project(root, 'same', 'pass', changed=False)
    (root / 'src/app/comparison_commands.py').write_text(COPIES['same'].replace('name.strip().title()', 'name.title()'))
    result = _pytest(root)
    assert '1 failed, 2 passed' in result.stdout and result.returncode == 1, result.stdout + result.stderr
    assert any(line.startswith('red: same TITLE') for line in block(result)), result.stdout


MANUAL = 'LABELS = {"empirical": "Empirical", "fitted": "Fitted"}\n\n\n# flowguard: same CITATION\n' \
         'def citation_text(identifier: str) -> str:\n    return LABELS.get(identifier, "Unknown")\n'
# The Python docs' recipe, as PEMEL Studio's tests/test_manual.py follows it.
BY_PATH = '''import importlib.util
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "tools" / "model_manual" / "build_manual.py"


def _load():
    spec = importlib.util.spec_from_file_location("{name}", PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["{name}"] = module
    spec.loader.exec_module(module)
    return module


'''
LOADS = {
    'module level': BY_PATH + 'build_manual = _load()\n\n\ndef test_citation():\n'
                    '    assert build_manual.citation_text("empirical") == "Empirical"\n',
    'test body': BY_PATH + 'def test_citation():\n    assert _load().citation_text("empirical") == "Empirical"\n',
}
RULE = '''from flowguard.intent import rule, row


@rule("CITATION", decides="citation label", fields={"identifier": str},
      source='assumed: the label of an empirical parameter', anchor="CITATION")
def CITATION(identifier):
    if identifier == "empirical":
        return "Empirical"
    return None


CITATION.rows(row(identifier="empirical", expect="Empirical", why="the label of an empirical parameter"))
'''


def _manual(root, load, *, name='build_manual', rule=False):
    write(root, 'pyproject.toml', '[tool.pytest.ini_options]\naddopts = "-p flowguard.intent.plugin"\n')
    write(root, '.gitignore', '.flowguard/cache/\n__pycache__/\n')
    write(root, 'tools/model_manual/build_manual.py', MANUAL)
    # collected before tests/intent/, as PEMEL Studio's tests/a_tools/: the model loads after the module-level load
    write(root, 'tests/a_tools/test_manual.py', LOADS[load].replace('{name}', name))
    if rule:
        write(root, 'tests/intent/citation.py', RULE)
        write(root, 'tests/test_flowguard_intent.py', 'def test_flowguard_intent(request):\n'
                                                      '    from flowguard.intent.plugin import sentinel\n'
                                                      '    sentinel(request.config)\n')
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', 'baseline')


@pytest.mark.parametrize('rule', [False, True], ids=['no rules', 'a rule homed there'])
def test_a_test_that_loads_a_project_file_by_path_keeps_pytests_outcome(tmp_path, rule):
    # 5.0.1 and the 5.1 candidate stopped at collection's finish: `ValueError: build_manual was imported before source
    # verification`, 59 INTERNALERROR lines, no test run and exit 1, where pytest alone gives `1 passed`.
    for load in LOADS:
        root = tmp_path / load.replace(' ', '-') / 'manual'
        _manual(root, load, rule=rule)
        # without the plugin, the sentinel test that checks the rules were collected fails by design
        without = _pytest(root, '-o', 'addopts=', '--deselect', 'tests/test_flowguard_intent.py::test_flowguard_intent')
        result = _pytest(root)
        output = result.stdout + result.stderr
        assert 'INTERNALERROR' not in output and 'imported before source verification' not in output, output
        assert result.returncode == without.returncode == 0, output
        assert ('2 passed, 3 unverified' if rule else '1 passed') in result.stdout, output
        lines = block(result)
        # the rule's home is grey, never red: its own observation imports the file and says why it cannot
        assert lines[0].split(': ', 1)[1].startswith('0 red, 3 not compared;' if rule else '0 red;'), lines
        assert not [line for line in lines if line.startswith('red: ')], lines
    # The CLI's own process, which imports project code by itself, still refuses a module another loader made.
    script = textwrap.dedent(f'''\
        import importlib.util, sys
        sys.path.insert(0, {SOURCE!r})
        spec = importlib.util.spec_from_file_location("build_manual", "tools/model_manual/build_manual.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["build_manual"] = module
        spec.loader.exec_module(module)
        from flowguard.intent.imports import prepare
        try:
            prepare(".")
        except ValueError as error:
            print(error)
        ''')
    refused = subprocess.run([sys.executable, '-c', script], cwd=root, capture_output=True, text=True, timeout=60)
    assert 'build_manual was imported before source verification' in refused.stdout, refused.stdout + refused.stderr


def test_a_by_path_instance_beside_the_imported_module_is_never_read_as_it(tmp_path):
    # tools/ as a package: the test loads build_manual.py by path under the map's own module name, and imports it
    # normally too. The changed function is compared on the imported module's calls alone, and neither instance's
    # readings pass for the other's.
    root = tmp_path / 'manual'
    _manual(root, 'module level', name='tools.model_manual.build_manual')
    write(root, 'tools/__init__.py', '')
    write(root, 'tools/model_manual/__init__.py', '')
    write(root, 'tests/test_imported.py', 'from tools.model_manual.build_manual import citation_text\n\n\n'
                                          'def test_imported():\n    assert citation_text("fitted") == "Fitted"\n')
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', 'packages')
    (root / 'tools/model_manual/build_manual.py').write_text(MANUAL.replace('"Unknown"', '"unknown"'))
    without, result = _pytest(root, '-o', 'addopts='), _pytest(root)
    output = result.stdout + result.stderr
    assert 'INTERNALERROR' not in output and 'Traceback' not in output, output
    assert result.returncode == without.returncode == 0 and '2 passed' in result.stdout, output
    assert not [line for line in block(result) if line.startswith('red: ')], output


FORCED = '''from flowguard.intent import plugin


def broken(self):
    raise KeyError('src/app/comparison_commands.py')


plugin.Observations.report = broken
'''


@pytest.mark.parametrize('failing', [True, False], ids=['a test fails', 'every test passes'])
def test_flowguard_s_own_error_at_session_finish_is_one_red_line_after_pytests_summary(tmp_path, failing):
    # R106, option 1A: before, the KeyError's traceback replaced pytest's failure list and summary.
    root = tmp_path / 'shop'
    write(root, 'pyproject.toml', '[tool.pytest.ini_options]\naddopts = "-p flowguard.intent.plugin"\n')
    write(root, '.gitignore', '.flowguard/cache/\n__pycache__/\n')
    write(root, 'conftest.py', FORCED)
    write(root, 'test_shop.py', 'def test_one():\n    assert 1\n\n\ndef test_two():\n    assert ' + ('1 == 2' if failing else '2 == 2') + '\n')
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', 'baseline')
    result = _pytest(root)
    output = result.stdout + result.stderr
    assert 'Traceback' not in output and 'INTERNALERROR' not in output, output
    summary = '1 failed, 1 passed' if failing else '2 passed'
    assert summary in result.stdout and result.returncode == 1, output       # never passes because FlowGuard broke
    lines = block(result)
    assert result.stdout.index(summary) < result.stdout.index(lines[0]), output
    assert lines[1:] == ["red: session: FlowGuard internal error: KeyError: 'src/app/comparison_commands.py' "
                         "(flowguard/intent/plugin.py:" + lines[1].rpartition('plugin.py:')[2]], lines
    assert lines[1].endswith(' _verify)') and lines[0].split(': ', 1)[1].startswith('1 red;'), lines
    shown = last(root)
    assert f'pytest: exit 1, {1 if failing else 0} failed' in shown and lines[1] in shown, shown
    assert '    Traceback (most recent call last):' in shown and "    KeyError: 'src/app/comparison_commands.py'" in shown, shown
    assert 'in broken' in shown, shown
