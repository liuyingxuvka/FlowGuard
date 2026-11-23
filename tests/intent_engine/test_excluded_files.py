"""A file `[tool.flowguard] exclude` lists is out of every comparison, and a reader that cannot run never replaces
pytest's own outcome (R85).

PEMEL Studio keeps Qt Linguist catalogues as `.ts` XML and excludes them. On 5.0.1 a catalogue edited after
new-task still entered the change set (`MapHandle._git_changed` filtered nothing), was read at the baseline with the
TypeScript reader on a Python-only install, and `check --static` exited 2 while pytest ended in a traceback instead
of its `1 passed` line; three agents patched `_git_changed` in a local pytest plugin for every run. A file that this
change newly excludes took its agreements off the map without a line, so an edit that broke a `same` copy there was
0 red. `ABSENT` makes the languages extra absent as such an install has it: no tree-sitter distribution and no
tree_sitter module, FlowGuard itself untouched.
"""
from contextlib import closing
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from flowguard.intent import anchors, owners, signals
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests.intent_engine._cli_fixture import display_text
from tests.intent_engine.test_static_check import _commit, _git, _write

SOURCE = str(Path(__file__).resolve().parents[2])
ABSENT = r'''
import importlib.metadata as metadata, sys

class _Absent:
    """No tree_sitter module: the languages extra is not installed."""
    def find_spec(self, name, path=None, target=None):
        if name.partition('.')[0].startswith('tree_sitter'):
            raise ModuleNotFoundError(f'No module named {name!r}', name=name)
        return None

_installed = metadata.distribution
def _distribution(name):
    if name.lower().replace('_', '-').startswith('tree-sitter'):
        raise metadata.PackageNotFoundError(name)
    return _installed(name)

sys.meta_path.insert(0, _Absent())
metadata.distribution = _distribution
sys.path.insert(0, sys.argv.pop(1))
'''
PYTEST = ABSENT + 'import pytest\nraise SystemExit(pytest.main(sys.argv[1:]))\n'
FLOWGUARD = ABSENT + 'from flowguard.__main__ import main\nraise SystemExit(main(sys.argv[1:]))\n'
PYPROJECT = '[project]\nname = "studio"\nversion = "0"\n{flowguard}[tool.pytest.ini_options]\npythonpath = ["."]\n' \
            'addopts = "-p flowguard.intent.plugin"\n'
CORE = {'app/__init__.py': '', 'app/core.py': 'def total(a, b):\n    return a + b\n',
        'tests/test_core.py': 'from app.core import total\n\n\ndef test_total():\n    assert total(1, 2) == 3\n'}
STEP = ('pip install "flowguard[languages] @ git+https://github.com/liuyingxuvka/FlowGuard.git", '
        'or list it in [tool.flowguard] exclude')


def _run(root, program, *arguments):
    """pytest or `python -m flowguard` in a fresh interpreter whose languages extra is absent (`ABSENT`)."""
    return subprocess.run([sys.executable, '-c', program, SOURCE, *arguments], cwd=root, capture_output=True, text=True,
                          timeout=180)


def _pytest(root, *arguments):
    return _run(root, PYTEST, '-q', '-p', 'no:cacheprovider', *arguments)


def _flowguard(root, *arguments):
    return _run(root, FLOWGUARD, *arguments)


def test_the_absent_extra_is_absent_in_the_child():
    probe = ABSENT + '''
import importlib.metadata
try:
    import tree_sitter
except ModuleNotFoundError:
    pass
else:
    raise AssertionError('tree_sitter was imported')
try:
    importlib.metadata.version('tree-sitter')
except importlib.metadata.PackageNotFoundError:
    print('absent')
'''
    result = subprocess.run([sys.executable, '-c', probe, SOURCE], capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == 'absent', result.stdout + result.stderr


def test_an_excluded_catalogue_edited_after_new_task_is_never_read(tmp_path):
    # PEMEL ex1: `exclude = ["translations/*.ts"]` and a Qt Linguist catalogue, a Python-only install, an empty cache.
    root = _commit(tmp_path, {'pyproject.toml': PYPROJECT.format(flowguard='[tool.flowguard]\nexclude = ["translations/*.ts"]\n'),
                              'translations/app.ts': '<TS version="2.1"></TS>\n', **CORE})
    started = _flowguard(root, 'new-task')
    assert started.returncode == 0, started.stdout + started.stderr
    (root / 'translations/app.ts').write_text('<TS version="2.1"><context/></TS>\n', encoding='utf-8')
    for name in ('map.sqlite', 'map.sqlite-wal', 'map.sqlite-shm'):
        (root / '.flowguard/cache' / name).unlink(missing_ok=True)
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 0, text
    assert '1 passed' in text and 'Traceback' not in text and 'reader unavailable' not in text, text
    assert 'FlowGuard 5.0 (since ' in text and ': 0 red;' in text, text
    static = _flowguard(root, 'check', '--static')
    assert static.returncode == 0, static.stdout + static.stderr
    assert 'reader unavailable' not in static.stdout + static.stderr


def test_the_change_set_holds_only_what_the_map_reads(tmp_path):
    # Untracked bytecode without a .gitignore, an excluded file, an interpreter environment's source: none is a change
    # of the map's (the environment's pyvenv.cfg, no source, is listed as the map's inventory lists it); a file this
    # change deletes still is, with the module the map gave it.
    root = tmp_path
    (root / 'app').mkdir()
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nexclude = ["generated/**"]\n', encoding='utf-8')
    (root / 'app/core.py').write_text('def total(a, b):\n    return a + b\n', encoding='utf-8')
    (root / 'app/gone.py').write_text('def old():\n    return 1\n', encoding='utf-8')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'baseline')
    (root / 'app/__pycache__').mkdir()
    (root / 'app/__pycache__/core.cpython-312.pyc').write_bytes(b'\x00bytecode')
    (root / 'generated').mkdir()
    (root / 'generated/schema.py').write_text('X = 1\n', encoding='utf-8')
    (root / 'env/lib').mkdir(parents=True)
    (root / 'env/pyvenv.cfg').write_text('home = /usr\n', encoding='utf-8')
    (root / 'env/lib/site.py').write_text('Y = 2\n', encoding='utf-8')
    (root / 'app/core.py').write_text('def total(a, b):\n    return b + a\n', encoding='utf-8')
    (root / 'app/gone.py').unlink()
    with closing(build(root)) as graph:
        change = owners.Change(load_config(root), graph, 'HEAD')
        assert change.files == {'app/core.py', 'app/gone.py', 'env/pyvenv.cfg'}
        assert change.baseline_paths() == change.files
        assert graph.impact(since='HEAD')['files'] == ['app/core.py', 'app/gone.py', 'env/pyvenv.cfg']
        assert change.module('app/gone.py') == 'app.gone' and change.module('generated/schema.py') is None
        assert {ident for ident, kind, *_ in change.delta(sorted(change.files))} == {'app.core:total', 'app.gone:old'}


def test_an_included_file_whose_reader_is_absent_is_one_red_line_after_pytests_summary(tmp_path):
    # PEMEL ex2: no exclude, an included web/a.ts edited, the extra absent. pytest's summary stays and the session
    # has one red line with the error's text and step; check --static exits 2 with the same text.
    root = _commit(tmp_path, {'pyproject.toml': PYPROJECT.format(flowguard=''), 'web/a.ts': 'export const a = 1;\n',
                              **CORE})
    (root / 'web/a.ts').write_text('export const a = 2;\n', encoding='utf-8')
    result = _pytest(root, '--junitxml', str(tmp_path / 'junit.xml'))
    text = display_text(result)
    assert result.returncode == 1, text
    assert '1 passed' in text and 'Traceback' not in text and 'INTERNALERROR' not in text, text
    assert 'FlowGuard 5.0 (since ' in text and ': 1 red;' in text, text
    reds = [line for line in text.splitlines() if line.startswith('red: ')]
    assert reds == [f'red: map checks: a.ts: typescript reader unavailable: missing tree-sitter -> {STEP}'], text
    assert text.index('1 passed') < text.index('red: map checks')       # the block comes after pytest's summary
    case = ET.parse(tmp_path / 'junit.xml').getroot().find(".//testcase[@classname='flowguard'][@name='session']")
    assert case is not None and 'typescript reader unavailable' in case.find('failure').get('message', '') + (case.find('failure').text or '')
    last = _flowguard(root, 'show', '--last')
    assert 'web/a.ts: typescript reader unavailable: missing tree-sitter' in last.stdout, last.stdout + last.stderr
    assert '    the map checks of this change did not run' in last.stdout, last.stdout
    static = _flowguard(root, 'check', '--static')
    assert static.returncode == 2, static.stdout + static.stderr
    assert static.stderr.strip() == f'flowguard: web/a.ts: typescript reader unavailable: missing tree-sitter -> {STEP}'


def test_a_changed_python_file_beside_it_still_runs_the_tests(tmp_path):
    # The same with app/core.py edited too: 5.0.1 built the map when the session began and stopped pytest there
    # (INTERNALERROR, no test run). The tests run, and the red line says what was not compared.
    root = _commit(tmp_path, {'pyproject.toml': PYPROJECT.format(flowguard=''), 'web/a.ts': 'export const a = 1;\n',
                              **CORE})
    (root / 'web/a.ts').write_text('export const a = 2;\n', encoding='utf-8')
    (root / 'app/core.py').write_text('def total(a, b):\n    return b + a\n', encoding='utf-8')
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 1 and '1 passed' in text and 'INTERNALERROR' not in text, text
    assert [line for line in text.splitlines() if line.startswith('red: ')] == [
        f'red: map checks: a.ts: typescript reader unavailable: missing tree-sitter -> {STEP}'], text
    last = _flowguard(root, 'show', '--last').stdout
    assert ('    the functions this change edits that no flowguard comment names, and the files that import a '
            'constant it changes, were not compared') in last, last


def _loosened(root, base='HEAD'):
    cfg = load_config(root)
    with closing(build(root, roots=cfg.roots)) as graph:
        found = owners.loosened(owners.Change(cfg, graph, base), anchors.collect(graph))
    lines, _ = signals.deliver([], touched_functions=(), touched_files=(), extra=found.lines)
    assert all(line.kind == 'loosened' and line.step == signals.LOOSENED_STEP for line in lines)
    return sorted(line.text for line in lines)


EXCLUDED = ' (its file is now excluded by [tool.flowguard] exclude)'
RUNNER = '''# flowguard: together Runner.task_id Runner.operation
class Runner:
    def __init__(self):
        self.task_id = ""
        self.operation = ""

    def start(self):
        self.task_id = "id"
        self.operation = "parse"
'''
JOB = '''# flowguard: writers Job.state Job.start
class Job:
    def __init__(self):
        self.state = "new"

    def start(self):
        self.state = "run"
'''


def test_a_newly_excluded_same_copy_is_loosened_in_pytest_and_check(tmp_path):
    # PEMEL23-2b: 5.0.1 gave `0 red` and no line once app/b.py was excluded with its copy edited to x*3.
    root = _commit(tmp_path, {'pyproject.toml': PYPROJECT.format(flowguard=''),
                              'app/__init__.py': '',
                              'app/a.py': '# flowguard: same RATE ref\ndef rate(x):\n    return x * 2\n',
                              'app/b.py': '# flowguard: same RATE\ndef rate(x):\n    return x * 2\n',
                              'tests/test_a.py': 'from app.a import rate\n\n\ndef test_one():\n    assert rate(1) == 2\n'})
    (root / 'app/b.py').write_text('# flowguard: same RATE\ndef rate(x):\n    return x * 3\n', encoding='utf-8')
    (root / 'pyproject.toml').write_text(PYPROJECT.format(flowguard='[tool.flowguard]\nexclude = ["app/b.py"]\n'),
                                         encoding='utf-8')
    line = f'loosened: same RATE removed from b.py:rate{EXCLUDED} -> {signals.LOOSENED_STEP}'
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 0 and '1 passed' in text and ': 0 red, 1 loosened;' in text, text
    assert line in text.splitlines(), text
    static = _flowguard(root, 'check', '--static')
    assert static.returncode == 0 and line in display_text(static).splitlines(), static.stdout + static.stderr
    assert _loosened(root) == ['same RATE removed from app/b.py:rate' + EXCLUDED]


def test_newly_excluded_together_and_writers_agreements_are_loosened(tmp_path):
    # PEMEL17-3: runner.py's together and w.py's writers agreement; deleting the comments was loosened on 5.0.1,
    # excluding their files was not.
    _commit(tmp_path, {'pyproject.toml': '[project]\nname = "tup"\nversion = "0"\n', 'runner.py': RUNNER, 'w.py': JOB})
    _write(tmp_path, {'pyproject.toml': '[project]\nname = "tup"\nversion = "0"\n[tool.flowguard]\nexclude = ["runner.py", "w.py"]\n'})
    assert _loosened(tmp_path) == ['together Runner.task_id Runner.operation removed' + EXCLUDED,
                                   'writers Job.state removed' + EXCLUDED]
    # An exclude that leaves them on the map, or one the baseline already had, loosens nothing.
    _write(tmp_path, {'pyproject.toml': '[project]\nname = "tup"\nversion = "0"\n[tool.flowguard]\nexclude = ["docs/**"]\n'})
    assert _loosened(tmp_path) == []
    _commit(tmp_path, {'pyproject.toml': '[project]\nname = "tup"\nversion = "0"\n[tool.flowguard]\nexclude = ["w.py"]\n'},
            message='w.py excluded')
    assert _loosened(tmp_path) == []


def test_a_newly_excluded_typescript_file_is_read_as_comment_lines_without_a_grammar(tmp_path, monkeypatch):
    # Every TS file excluded: the map needs no grammar now, and the baseline's comments are read as text, its comment
    # lines only (a `flowguard:` inside a string is no agreement).
    _commit(tmp_path, {'pyproject.toml': '[project]\nname = "web"\nversion = "0"\n',
                       'web/a.ts': '// flowguard: same RATE ref\nexport function rate(x: number) { return x * 2; }\n',
                       'web/b.ts': 'const note = "// flowguard: same FAKE";\n'
                                   '// flowguard: same RATE\nexport function rate(x: number) { return x * 2; }\n'
                                   '// flowguard: together Job.a Job.b\nexport function save(job: any) { job.a = 1; job.b = 2; }\n'})
    _write(tmp_path, {'pyproject.toml': '[project]\nname = "web"\nversion = "0"\n[tool.flowguard]\nexclude = ["web/*.ts"]\n'})
    from flowguard.structure.readers import registry

    def unread(*arguments):
        raise AssertionError(f'a grammar read {arguments[1]}')
    monkeypatch.setattr(registry, 'extract', unread)
    assert _loosened(tmp_path) == ['same RATE removed from web/a.ts:1' + EXCLUDED, 'same RATE removed from web/b.ts:2' + EXCLUDED,
                                   'together Job.a Job.b removed' + EXCLUDED]


def test_comment_agreements_reads_comment_lines_only():
    text = ('const a = "// flowguard: writers Job.state save";\n'
            '  // flowguard: writers Job.kind save\n'
            'let b = 1; // flowguard: same AFTER\n'
            '// flowguard: same RATE ref\n')
    rows = anchors.comment_agreements(text, 'typescript/web/b.ts', 'web/b.ts')
    assert [(row['kind'], row['name'], row['line'], row['qual'], row['owner']) for row in rows] == [
        ('owner', 'Job.kind', 2, '', False), ('sensor', 'RATE', 4, '', True)]


@pytest.mark.parametrize('broken, cause', [
    (b'[project]\nname = "studio"\nversion = "0"\n<<<<<<< HEAD\n', 'does not parse'),
    (b'[project]\nname = "studio"\nversion = "0"\ndescription = "caf\xe9"\n', 'is no UTF-8 text'),
], ids=['conflict-marker', 'latin-1'])
def test_a_task_that_repairs_an_unreadable_baseline_pyproject_is_one_not_compared_line(tmp_path, broken, cause):
    # Round A of 5.1, F1: the baseline commit held a pyproject.toml pytest itself refuses (a conflict marker, Latin-1
    # bytes), so repairing it is a task's natural first change. Every run of that task was red (`map checks:
    # pyproject.toml at the baseline ... does not parse`, check --static exit 2) and the Latin-1 one ended pytest in a
    # traceback instead of its summary; 5.0.1 never read it. Which files this change takes out of the map is not
    # known: one not compared line in the decoder's or parser's words, and the other map checks still run (a `same`
    # comment removed in the same change is loosened).
    import tomllib
    with pytest.raises((UnicodeDecodeError, tomllib.TOMLDecodeError)) as refused:     # the words of this Python's
        tomllib.loads(broken.decode('utf-8-sig'))                                       # decoder or parser
    words = f'{cause}: {refused.value}'
    (tmp_path / 'pyproject.toml').write_bytes(broken)
    root = _commit(tmp_path, {'pytest.ini': '[pytest]\npythonpath = .\naddopts = -p flowguard.intent.plugin\n',
                              'app/a.py': '# flowguard: same RATE ref\ndef rate(x):\n    return x * 2\n',
                              'app/b.py': '# flowguard: same RATE\ndef rate(x):\n    return x * 2\n', **CORE})
    sha = _git(root, 'rev-parse', '--short=7', 'HEAD').strip()
    (root / 'pyproject.toml').write_text('[project]\nname = "studio"\nversion = "0"\n', encoding='utf-8')
    started = _flowguard(root, 'new-task')
    assert started.returncode == 0, started.stdout + started.stderr
    (root / 'app/b.py').write_text('def rate(x):\n    return x * 2\n', encoding='utf-8')
    loosened = f'loosened: same RATE removed from b.py:rate -> {signals.LOOSENED_STEP}'
    unknown = 'the files this change takes out of the map'
    subject = f'not compared: {unknown} (pyproject.toml at the baseline {sha} {cause}: '
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 0, text
    shown = text.splitlines()
    assert '1 passed' in text and 'Traceback' not in text and not [line for line in shown if line.startswith('red: ')], text
    assert f'FlowGuard 5.0 (since {sha}): 0 red, 1 loosened, 1 not compared;' in text, text
    assert loosened in shown and [line for line in shown if line.startswith('not compared: ')][0].startswith(subject), text
    last = _flowguard(root, 'show', '--last').stdout.splitlines()
    assert last[last.index(f'not compared: {unknown} -> not a failure') + 1] == \
        f'    pyproject.toml at the baseline {sha} {words}', last
    static = _flowguard(root, 'check', '--static')
    shown = display_text(static).splitlines()
    assert static.returncode == 0 and static.stderr == '', static.stdout + static.stderr
    assert shown[0].startswith(f'FlowGuard 5.0 (since {sha}): 0 red, 1 loosened, 1 not compared;'), shown
    assert loosened in shown and shown[-1].startswith(subject), shown
