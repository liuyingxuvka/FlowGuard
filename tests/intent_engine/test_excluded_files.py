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


UNREADABLE_ROOTS = [
    ('pkg/pyproject.toml', b'# caf\xe9\n[project]\nname = "pkg"\nversion = "0"\n',
     "pkg/pyproject.toml is no UTF-8 text: 'utf-8' codec can't decode byte 0xe9 in position 5: invalid continuation byte"),
    ('pkg/pyproject.toml', b'[project]\nname = "pkg"\n<<<<<<< HEAD\n',
     'pkg/pyproject.toml does not parse: Invalid statement (at line 3, column 1)'),
    ('pkg/pyproject.toml', b'[project]\nname = "pkg"\n[tool]\nsetuptools = "x"\n',
     'pkg/pyproject.toml: tool.setuptools is a string (not a table)'),
    ('pkg/pyproject.toml', b'[tool.pytest]\nini_options = "x"\n',
     'pkg/pyproject.toml: tool.pytest.ini_options is a string (not a table)'),
    ('pyproject.toml', PYPROJECT.format(flowguard='[tool.setuptools]\npackage-dir = "src"\n').encode(),
     'pyproject.toml: tool.setuptools.package-dir is a string (not a table)'),
]


@pytest.mark.parametrize('name, raw, words', UNREADABLE_ROOTS)
def test_a_pyproject_the_import_roots_cannot_read_is_one_red_line_after_pytests_summary(tmp_path, name, raw, words):
    # Review of 5.1 (FD4 nit 0, R85): a package's own pyproject.toml below the root, read for the map's import roots by
    # roots._toml, ended pytest in INTERNALERROR (`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9`, exit 3,
    # no test run, or `AttributeError: 'str' object has no attribute 'get'` from `[tool] setuptools = "x"`), and check
    # --static said `flowguard: 'utf-8' codec can't decode byte 0xe9 ...` naming no file, or printed a traceback; a
    # file that did not parse was read as empty. It is read by the reader every pyproject.toml has
    # (`store.project_config`), refused with the file and the reason: pytest's own summary and exit, then the map
    # checks' red line, as for a reader that cannot run; check --static exits 2 with that text. A table of the
    # project's own pyproject.toml that load_config does not read (`tool.setuptools`) is judged so too.
    files = {'pyproject.toml': PYPROJECT.format(flowguard=''), **CORE}
    _write(tmp_path, {path: text for path, text in files.items() if path != name})
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_bytes(raw)
    root = _commit(tmp_path)
    red = f'red: map checks: {words} -> correct this error and rerun the tests'
    for changed in (False, True):
        if changed:
            (root / 'app/core.py').write_text('def total(a, b):\n    return b + a\n', encoding='utf-8')
        result = _pytest(root)
        text = display_text(result)
        assert result.returncode == 1 and '1 passed' in text, text
        assert 'INTERNALERROR' not in text and 'Traceback' not in text, text
        assert [line for line in text.splitlines() if line.startswith('red: ')] == [red], text
        assert text.index('1 passed') < text.index('red: map checks')
    last = _flowguard(root, 'show', '--last').stdout
    assert '    the flowguard comments were not read, so no function one names was compared' in last, last
    static = _flowguard(root, 'check', '--static')
    assert (static.returncode, static.stdout, static.stderr) == (2, '', f'flowguard: {words}\n'), static


def test_a_rule_bound_to_a_comment_is_not_run_where_the_map_cannot_be_built(tmp_path):
    # The same where an intent rule is bound to a flowguard comment: its loader builds the map when pytest collects
    # it, and 5.0.1 and 5.1's earlier rounds stopped there (INTERNALERROR, exit 1, no test run), for a reader that
    # cannot run too. The tests run; the rule's bindings are not run, never `anchor gone`, and the map checks say why.
    name, raw, words = UNREADABLE_ROOTS[0]
    rule = ('from flowguard.intent import rule\n\n\n@rule("TOTAL", decides="a sum", fields={"a": int, "b": int}, '
            'source="assumed: test", anchor="TOTAL")\ndef TOTAL(a, b):\n    return a + b\n')
    sentinel = ('def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n'
                '    sentinel(request.config)\n')
    _write(tmp_path, {'pyproject.toml': PYPROJECT.format(flowguard=''), **CORE, 'tests/intent/total.py': rule,
                      'tests/test_flowguard_intent.py': sentinel,
                      'app/core.py': '# flowguard: same TOTAL\ndef total(a: int, b: int) -> int:\n    return a + b\n'})
    (tmp_path / 'pkg').mkdir()
    (tmp_path / name).write_bytes(raw)
    root = _commit(tmp_path)
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 1 and '2 passed, 3 unverified' in text, text
    assert 'INTERNALERROR' not in text and 'Traceback' not in text and 'anchor gone' not in text, text
    assert [line for line in text.splitlines() if line.startswith('red: ')] == [
        f'red: map checks: {words} -> correct this error and rerun the tests'], text
    last = _flowguard(root, 'show', '--last').stdout
    assert 'not compared: TOTAL[anchor.TOTAL:cells] -> not a failure' in last and 'anchor gone' not in last, last
    shown = _flowguard(root, 'check')
    assert (shown.returncode, shown.stderr) == (2, f'flowguard: {words}\n'), shown


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


def _head(words):
    """A reason as the not compared line sums it up: before its parentheses (`signals._reason`)."""
    return words.split(' (')[0]


def _repaired_baseline(tmp_path, broken, words):
    """A baseline pyproject.toml FlowGuard cannot read (`broken`), which the task repairs while it removes a `same`
    comment: one not compared line whose detail is `words`, the loosened line, `1 passed`, exit 0, no red line and no
    traceback, in pytest and check --static alike."""
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
    subject = f'not compared: {unknown} ({words[:40]}'          # the block's head
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 0, text
    shown = text.splitlines()
    assert '1 passed' in text and 'Traceback' not in text and not [line for line in shown if line.startswith('red: ')], text
    assert f'FlowGuard 5.0 (since {sha}): 0 red, 1 loosened, 1 not compared;' in text, text
    said = [line for line in shown if line.startswith('not compared: ')]
    assert loosened in shown and len(said) == 1 and said[0].startswith(subject), text
    last = _flowguard(root, 'show', '--last').stdout.splitlines()
    assert last[last.index(f'not compared: {unknown} -> not a failure') + 1] == f'    {words}', last
    static = _flowguard(root, 'check', '--static')
    shown = display_text(static).splitlines()
    assert static.returncode == 0 and static.stderr == '', static.stdout + static.stderr
    assert shown[0].startswith(f'FlowGuard 5.0 (since {sha}): 0 red, 1 loosened, 1 not compared;'), shown
    assert loosened in shown and shown[-1] == said[0], shown
    return sha, said[0]


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
    _repaired_baseline(tmp_path, broken, f'baseline pyproject.toml {cause}: {refused.value}')


PROJECT = b'[project]\nname = "studio"\nversion = "0"\n'


@pytest.mark.parametrize('broken, words', [
    (PROJECT + b'\n[tool.flowguard]\nexclude = 5\n',
     'baseline pyproject.toml: tool.flowguard.exclude is an integer (not an array of strings)'),
    (PROJECT + b'\n[tool.flowguard]\nexclude = "app/b.py"\n',
     'baseline pyproject.toml: tool.flowguard.exclude is a string (not an array of strings)'),
    (PROJECT + b'\n[tool.flowguard]\nexclude = ["app/b.py", 5]\n',
     'baseline pyproject.toml: tool.flowguard.exclude[1] is an integer (not a string)'),
    (PROJECT + b'\n[tool]\nflowguard = "x"\n', 'baseline pyproject.toml: tool.flowguard is a string (not a table)'),
    (b'tool = "x"\n\n' + PROJECT, 'baseline pyproject.toml: tool is a string (not a table)'),
], ids=['exclude-integer', 'exclude-string', 'exclude-item', 'section-string', 'tool-string'])
def test_a_baseline_pyproject_whose_flowguard_values_have_another_type_is_one_not_compared_line(tmp_path, broken, words):
    # Round A of 5.1, F1's neighbour (R85): the baseline's pyproject.toml parses, but its `tool` table, [tool.flowguard]
    # or `exclude` has another TOML type than FlowGuard reads, and the task repairs it. Every run of that task
    # ended in a traceback (`TypeError: 'int' object is not iterable` from `store.ignored`, `AttributeError: 'str'
    # object has no attribute 'get'`) instead of pytest's summary, and check --static exited 1; a string `exclude` was
    # read as one pattern per character. It is unreadable as a baseline that does not parse: one not compared line
    # naming the key and the type found, never red. The block line keeps both (FD2 open 3: `pyproject.toml at the
    # baseline 1a2b3c4 sets tool.flowguard.exclude to an array ...` was cut before the type found).
    _, said = _repaired_baseline(tmp_path, broken, words)
    assert said == f'not compared: the files this change takes out of the map ({_head(words)}) -> not a failure', said


@pytest.mark.parametrize('other', ['screen_lines = "40"', 'authority_docs = 5'])
def test_a_wrong_baseline_key_that_exclude_s_reader_does_not_read_keeps_the_exact_loosened_line(tmp_path, other):
    # Round A of 5.1 (FD2 open 0, PEMEL17-3): the baseline's only wrong [tool.flowguard] key had nothing to do with
    # `exclude`; the task repairs it, adds app/b.py to exclude and edits b.py's `same RATE` copy. The first fix judged
    # every key of the section at the baseline, so this gave `0 red, 1 not compared` (`... sets
    # tool.flowguard.screen_lines to a ...`) and lost the loosened line that the parent of that fix printed.
    # `Change.newly_excluded` reads `exclude` alone there and judges only that, its table and `tool`.
    (tmp_path / 'pyproject.toml').write_bytes(PROJECT + f'\n[tool.flowguard]\n{other}\n'.encode())
    root = _commit(tmp_path, {'pytest.ini': '[pytest]\npythonpath = .\naddopts = -p flowguard.intent.plugin\n',
                              'app/a.py': '# flowguard: same RATE\ndef rate(x):\n    return x * 2\n',
                              'app/b.py': '# flowguard: same RATE\ndef rate(x):\n    return x * 2\n', **CORE})
    sha = _git(root, 'rev-parse', '--short=7', 'HEAD').strip()
    (root / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nexclude = ["app/b.py"]\n')
    assert _flowguard(root, 'new-task').returncode == 0
    (root / 'app/b.py').write_text('# flowguard: same RATE\ndef rate(x):\n    return x * 3\n', encoding='utf-8')
    loosened = f'loosened: same RATE removed from b.py:rate{EXCLUDED} -> {signals.LOOSENED_STEP}'
    for run in (_pytest(root), _flowguard(root, 'check', '--static')):
        shown = display_text(run).splitlines()
        assert run.returncode == 0 and 'Traceback' not in run.stdout + run.stderr, run.stdout + run.stderr
        title = next(line for line in shown if line.startswith('FlowGuard '))
        assert title.startswith(f'FlowGuard 5.0 (since {sha}): 0 red, 1 loosened;') and loosened in shown, shown
        assert not [line for line in shown if line.startswith(('red: ', 'not compared: '))], shown


@pytest.mark.parametrize('broken, words', [
    (b'[tool.flowguard]\nexclude = 5\n', 'tool.flowguard.exclude is an integer (not an array of strings)'),
    (b'[tool]\nflowguard = "x"\n', 'tool.flowguard is a string (not a table)'),
    (b'tool = 5\n', 'tool is an integer (not a table)'),
    (b'[tool.flowguard]\nroots = ["src", ["lib"]]\n', 'tool.flowguard.roots[1] is an array (not a string)'),
    (b'[tool.flowguard]\nintent = 5\nexclude = 5\n', 'tool.flowguard.intent is an integer (not a string)'),
    (b'[tool.flowguard]\nledger = []\n', 'tool.flowguard.ledger is an array (not a table)'),
    (b'[tool.flowguard]\ncheck_lines = true\n', 'tool.flowguard.check_lines is a boolean (not an integer)'),
])
def test_project_config_names_the_file_the_key_and_the_type_found_at_a_baseline_and_in_the_project(tmp_path, broken, words):
    from flowguard.structure.store import UnreadableConfig, project_config
    with pytest.raises(UnreadableConfig) as refused:
        project_config(tmp_path, data=broken)
    assert str(refused.value) == 'baseline pyproject.toml: ' + words
    (tmp_path / 'pyproject.toml').write_bytes(broken)
    with pytest.raises(UnreadableConfig) as refused:
        project_config(tmp_path)
    assert str(refused.value) == 'pyproject.toml: ' + words
    good = b'[tool.flowguard]\nexclude = ["docs"]\nscreen_lines = 30\nledger = { paths = ["app"] }\n[tool.other]\nx = 5\n'
    assert project_config(tmp_path, data=good) == dict(exclude=['docs'], screen_lines=30, ledger=dict(paths=['app']))
    assert project_config(tmp_path, data=good, section='other') == dict(x=5)
    assert project_config(tmp_path, data=b'') == {}


def test_a_reader_of_some_keys_judges_and_returns_only_those():
    # FD2 open 0: a reader of the baseline names the keys it reads (`keys=`); a wrong type in another key never stops
    # it, and the section it gets holds only its keys, so it cannot read one it did not judge.
    from flowguard.structure.store import UnreadableConfig, project_config
    data = b'[tool.flowguard]\nscreen_lines = "40"\nauthority_docs = 5\nexclude = ["app/b.py"]\nunknown = 1\n'
    assert project_config(None, data=data, keys=('exclude',)) == dict(exclude=['app/b.py'])
    assert project_config(None, data=b'[project]\nname = "x"\n', keys=('exclude',)) == {}
    for keys, words in ((('authority_docs',), 'tool.flowguard.authority_docs is an integer (not an array of strings)'),
                        (None, 'tool.flowguard.screen_lines is a string (not an integer)')):
        with pytest.raises(UnreadableConfig) as refused:
            project_config(None, data=data, keys=keys)
        assert str(refused.value) == 'baseline pyproject.toml: ' + words
    with pytest.raises(UnreadableConfig, match=r'^baseline pyproject\.toml: tool\.flowguard is a string \(not a table\)$'):
        project_config(None, data=b'[tool]\nflowguard = "x"\n', keys=('exclude',))


def test_the_block_line_of_a_baseline_config_keeps_the_key_and_the_type_found_for_every_key():
    # FD2 open 3: the reason was `pyproject.toml at the baseline a8f702a sets tool.flowguard.authority_docs to ...`, and
    # the block's 80-character head cut the type found for authority_docs, screen_lines, check_lines and skip_policy
    # even for a plain scalar. Each key with the longest type a value can have (a date-time, or an array holding one)
    # keeps its key and that type on the block line, for the map's line and for a source's, and the line's detail,
    # which `show --last` prints, keeps the type it needs too.
    from flowguard.intent.owners import EXCLUDED_UNKNOWN
    from flowguard.intent.sources import unknown_at_baseline
    from flowguard.structure.store import FLOWGUARD_KEYS, UnreadableConfig, project_config
    for key, kind in FLOWGUARD_KEYS.items():
        array = kind == 'an array of strings'
        value = '["a", 1979-05-27T07:32:00Z]' if array else '1979-05-27T07:32:00Z'
        with pytest.raises(UnreadableConfig) as refused:
            project_config(None, data=f'[tool.flowguard]\n{key} = {value}\n'.encode(), keys=(key,))
        found = f'tool.flowguard.{key}[1] is a date-time' if array else f'tool.flowguard.{key} is a date-time'
        expected = 'a string' if array else kind
        assert str(refused.value) == f'baseline pyproject.toml: {found} (not {expected})', refused.value
        for line in (signals.not_compared(EXCLUDED_UNKNOWN, [str(refused.value)], places=('pyproject.toml',)),
                     signals.not_compared('source rule.exact-add', [unknown_at_baseline(
                         'AGENTS.md does not contain "Add numbers exactly." -> quote the document exactly', refused.value)],
                         places=('.flowguard/rules.toml:rule.exact-add',))):
            said = signals.render_block([line], title='FlowGuard').splitlines()[1]
            assert said == f'not compared: {line.text} (baseline pyproject.toml: {found}) -> not a failure', said
            assert f'{found} (not {expected})' in line.detail[0], line.detail      # show --last prints the detail
    with pytest.raises(UnreadableConfig) as refused:
        project_config(None, data=b'[tool.flowguard]\nscreen_lines = "40"\n')
    line = signals.not_compared(EXCLUDED_UNKNOWN, [str(refused.value)], places=('pyproject.toml',))
    assert signals.render_block([line], title='FlowGuard').splitlines()[1] == (
        'not compared: the files this change takes out of the map (baseline pyproject.toml: '
        'tool.flowguard.screen_lines is a string) -> not a failure')


AUTHORITY = {'tool': b'[tool]\nflowguard = "x"\n', 'int': b'[tool.flowguard]\nauthority_docs = 5\n',
             'str': b'[tool.flowguard]\nauthority_docs = "AGENTS.md"\n', 'toml': b'<<<<<<< HEAD\n'}
CAUSE = {'tool': 'baseline pyproject.toml: tool.flowguard is a string (not a table)',
         'int': 'baseline pyproject.toml: tool.flowguard.authority_docs is an integer (not an array of strings)',
         'str': 'baseline pyproject.toml: tool.flowguard.authority_docs is a string (not an array of strings)',
         'toml': 'baseline pyproject.toml does not parse: Invalid statement (at line 5, column 1)'}


@pytest.mark.parametrize('kind', list(AUTHORITY))
def test_a_baseline_authority_docs_that_cannot_be_read_leaves_a_document_source_not_compared(tmp_path, kind):
    # Round A of 5.1, FD2 open 1 (R85): a document source that no longer holds is judged at the baseline with that
    # commit's `authority_docs`, which sources._authority_docs read with bare tomllib and `.get` chains. With the
    # baseline's `[tool] flowguard = "x"` pytest ended in `AttributeError: 'str' object has no attribute 'get'` and
    # check --static exited 1, `authority_docs = 5` gave `TypeError: 'int' object is not iterable`, a conflict marker
    # `tomllib.TOMLDecodeError` (check --static: `flowguard: Invalid statement (at line 4, column 1)`, naming no file),
    # and a string was read one character at a time (a `before`). The baseline's document holds the words and this
    # task takes them out, so whether this change broke such a source is not known: rules.toml's entry is one not
    # compared line and the intent rule citing the document is grey, each with the file's text and what is wrong now;
    # pytest's summary and exit, and check --static's, are as for any not compared item. (A document without the words
    # at the baseline failed there whatever authority_docs held: the next test.)
    (tmp_path / 'pyproject.toml').write_bytes(PROJECT + b'\n' + AUTHORITY[kind])
    root = _commit(tmp_path, {
        'pytest.ini': '[pytest]\npythonpath = .\naddopts = -p flowguard.intent.plugin\n',
        'AGENTS.md': '# Agents\n\nAdd numbers exactly.\n',
        '.flowguard/rules.toml': '[rule.exact-add]\ntext = "add is exact"\nsource = \'doc AGENTS.md "Add numbers exactly."\'\n',
        'tests/intent/add.py': "from flowguard.intent import rule\n\n\n@rule('DOC', decides='sum doc', fields={'a': int}, "
                               "source='doc AGENTS.md \"Add numbers exactly.\"')\ndef DOC(a):\n    return a >= 0\n",
        'tests/test_flowguard_intent.py': '"""Fail when declared FlowGuard intent was not collected."""\n'
                                          'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n'
                                          '    sentinel(request.config)\n', **CORE})
    (root / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = ["AGENTS.md"]\n')    # repaired
    (root / 'AGENTS.md').write_text('# Agents\n\nAdd numbers.\n', encoding='utf-8')         # the words go
    assert _flowguard(root, 'new-task').returncode == 0
    now = 'AGENTS.md does not contain "Add numbers exactly." -> quote the document exactly'
    result = _pytest(root)
    text = display_text(result)
    shown = text.splitlines()
    assert result.returncode == 0 and 'Traceback' not in text and '2 passed, 1 unverified' in text, text
    assert not [line for line in shown if line.startswith(('red: ', 'before: '))], text
    said = [line for line in shown if line.startswith('not compared: ')]
    if kind in ('tool', 'toml'):        # the map's line of the files this change takes out of it says the same
        assert len(said) == 1 and said[0].startswith('not compared: 3 items: DOC[rules], source rule.exact-add and the '
                                                      'files this change takes out of the map (baseline pyproject.toml'), text
        assert said[0].endswith('...model only: bind the actual code home) -> not a failure'), text    # reasons cut
    else:
        assert said == ['not compared: 2 items: DOC[rules] and source rule.exact-add '
                        f'({_head(CAUSE[kind])}, or model only: bind the actual code home) -> not a failure'], text
    last = _flowguard(root, 'show', '--last').stdout.splitlines()
    for item in ('source rule.exact-add', 'DOC[rules]'):
        detail = last[last.index(f'not compared: {item} -> not a failure') + 1]
        assert detail.startswith(f'    {CAUSE[kind]}; whether this change broke it is not known: '), last
    assert last[last.index('not compared: source rule.exact-add -> not a failure') + 1].endswith(now), last
    static = _flowguard(root, 'check', '--static')
    shown = display_text(static).splitlines()
    assert static.returncode == 0 and static.stderr == '' and 'Traceback' not in static.stdout, static.stdout + static.stderr
    assert not [line for line in shown if line.startswith(('red: ', 'before: '))], shown
    assert [line for line in shown if line.startswith('not compared: ')][0].startswith(
        'not compared: ' + ('2 items: source rule.exact-add and the files' if kind in ('tool', 'toml') else
                            f'source rule.exact-add ({_head(CAUSE[kind])}) -> not a failure')), shown


FIXTURE_DOC = {
    'pytest.ini': '[pytest]\npythonpath = .\naddopts = -p flowguard.intent.plugin\n',
    'AGENTS.md': '# Agents\n\nAdd numbers.\n',
    '.flowguard/rules.toml': '[rule.exact-add]\ntext = "add is exact"\nsource = \'doc AGENTS.md "Add numbers exactly."\'\n',
    'tests/intent/add.py': "from flowguard.intent import rule\n\n\n@rule('DOC', decides='sum doc', fields={'a': int}, "
                           "source='doc AGENTS.md \"Add numbers exactly.\"')\ndef DOC(a):\n    return a >= 0\n",
    'tests/test_flowguard_intent.py': '"""Fail when declared FlowGuard intent was not collected."""\n'
                                      'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n'
                                      '    sentinel(request.config)\n', **CORE}


@pytest.mark.parametrize('kind', ['ok', *AUTHORITY])
def test_a_document_without_the_words_at_the_baseline_is_before_whatever_its_authority_docs_held(tmp_path, kind):
    # Round A of 5.1, FD3 open 0: a source's document was judged at the baseline by that commit's authority_docs
    # before its bytes, so a baseline pyproject.toml that cannot be read for them (an integer, a conflict marker, ...)
    # left a source whose words the baseline's AGENTS.md never held `not compared ... whether this change broke it is
    # not known` in every normal run. It failed at the task start whatever authority_docs held: exactly `before`, as
    # with a readable baseline (`ok`), for the rules.toml entry and for the intent rule citing the document alike. The
    # files this change takes out of the map stay not compared where [tool.flowguard] itself cannot be read.
    (tmp_path / 'pyproject.toml').write_bytes(PROJECT + b'\n' + (
        b'[tool.flowguard]\nauthority_docs = ["AGENTS.md"]\nscreen_lines = 40\n' if kind == 'ok' else AUTHORITY[kind]))
    root = _commit(tmp_path, FIXTURE_DOC)
    (root / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = ["AGENTS.md"]\n')
    assert _flowguard(root, 'new-task').returncode == 0
    mapped = kind in ('tool', 'toml')         # [tool.flowguard] itself cannot be read: exclude's reader cannot either
    model = 'DOC[rules] (model only: bind the actual code home)'
    entry = ('before: source rule.exact-add at rules.toml:rule.exact-add was broken at task start -> leave it unless '
             'your task is about it')
    intent = 'before: source DOC at add.py:4 was broken at task start -> leave it unless your task is about it'

    def lines(result, *prefixes):
        text = display_text(result)
        assert result.returncode == 0 and 'Traceback' not in text and 'whether this change broke' not in text, text
        return [line for line in text.splitlines() if line.startswith(prefixes)]

    result = _pytest(root)
    assert '2 passed, 1 unverified' in result.stdout, result.stdout
    assert lines(result, 'red: ', 'before: ', 'not compared: ') == [
        'not compared: 2 items: DOC[rules] and the files this change takes out of the map (model only: bind the actual '
        f'code home, or {_head(CAUSE[kind])}) -> not a failure' if mapped else f'not compared: {model} -> not a failure']
    assert lines(_flowguard(root, 'check', '--static'), 'red: ', 'before: ', 'not compared: ') == (
        [f'not compared: the files this change takes out of the map ({_head(CAUSE[kind])}) -> not a failure']
        if mapped else [])
    excluded = ['not compared: the files this change takes out of the map -> not a failure'] if mapped else []
    assert lines(_flowguard(root, 'check', '--static', '--all'), 'red: ', 'before: ', 'not compared: ') == [
        entry, *excluded]
    assert lines(_flowguard(root, 'check', '--all'), 'red: ', 'before: ', 'not compared: ') == [
        intent, entry, 'not compared: DOC[rules] -> not a failure', *excluded]


@pytest.mark.parametrize('document, problem', [
    (None, 'AGENTS.md is gone -> restore it, or cite the document that holds the words'),
    (b'# Agents\n\nAdd numbers caf\xe9.\n', "AGENTS.md is no UTF-8 or UTF-16 text: 'utf-8' codec can't decode byte 0xe9 "
     'in position 25: invalid continuation byte -> save it as UTF-8, or as UTF-16 with its byte order mark'),
    (b'# Agents\n\nAdd numbers.\n', 'AGENTS.md does not contain "Add numbers exactly." -> quote the document exactly'),
], ids=['gone', 'latin-1', 'other words'])
def test_what_a_commit_s_document_tells_is_judged_before_its_authority_docs(tmp_path, document, problem):
    # FD3 open 0: at a commit whose pyproject.toml cannot be read for authority_docs, a document gone there, no text
    # there or without the words there is that source's problem there (what the commit already tells); only a document
    # holding the words leaves its state there not known (UnreadableConfig reaches the caller). Now the listing is
    # still named first.
    from flowguard.intent import sources
    from flowguard.structure.store import UnreadableConfig
    source = sources.parse('doc AGENTS.md "Add numbers exactly."', strict=True)
    (tmp_path / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = 5\n')
    if document is not None:
        (tmp_path / 'AGENTS.md').write_bytes(document)
    root = _commit(tmp_path, {'README.md': 'x\n'})
    base = _git(root, 'rev-parse', 'HEAD').strip()
    (root / 'AGENTS.md').write_text('# Agents\n\nAdd numbers exactly.\n', encoding='utf-8')
    _commit(root, message='the words')
    held = _git(root, 'rev-parse', 'HEAD').strip()
    (root / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = ["docs/*.md"]\n')
    cfg = load_config(root)
    assert sources.catalog_authority(source, cfg, None, revision=base) == (False, problem)
    with pytest.raises(UnreadableConfig, match='^baseline pyproject.toml: tool.flowguard.authority_docs is an integer'):
        sources.catalog_authority(source, cfg, None, revision=held)
    assert sources.catalog_authority(source, cfg, None) == (False, 'AGENTS.md is not in authority_docs -> list it in '
                                                            '[tool.flowguard] authority_docs of pyproject.toml, or cite '
                                                            'a listed document')


def test_a_rule_whose_earlier_commit_holds_an_unreadable_authority_docs_is_provisional(tmp_path):
    # FD2 open 1: sources.provisional read the pyproject.toml of the commit before the rule's commit with bare tomllib
    # (`TypeError: 'int' object is not iterable` in the rule's test for `authority_docs = 5`). Whether the document was
    # listed then is not known, so the rule is provisional (green*), as without that commit.
    from flowguard.intent import sources
    (tmp_path / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = 5\n')
    root = _commit(tmp_path, {'AGENTS.md': '# Agents\n\nAdd numbers exactly.\n'})
    (root / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = ["AGENTS.md"]\n')
    _commit(root, {'tests/intent/add.py': 'RULE = 1\n'}, message='rule')
    cfg = load_config(root)
    source = sources.parse('doc AGENTS.md "Add numbers exactly."')
    assert sources.provisional(source, cfg, root / 'tests/intent/add.py') is True
    (root / 'pyproject.toml').write_bytes(PROJECT + b'\n[tool.flowguard]\nauthority_docs = ["AGENTS.md"]\n')
    _commit(root, {'tests/intent/add.py': 'RULE = 2\n'}, message='rule again')
    assert sources.provisional(source, load_config(root), root / 'tests/intent/add.py') is False


@pytest.mark.parametrize('value, words', [
    ('[tool.flowguard]\nexclude = 5', 'tool.flowguard.exclude is an integer (not an array of strings)'),
    ('[tool]\nflowguard = "x"', 'tool.flowguard is a string (not a table)'),
])
def test_the_projects_own_pyproject_of_another_type_is_refused_with_its_text_as_a_toml_error_is(tmp_path, value, words):
    # The current tree's pyproject.toml with a [tool.flowguard] value of another type ended pytest, check --static and
    # a vitest preparation in a traceback (the int `exclude` in load_config); `[tool] flowguard = "x"` said `unknown
    # [tool.flowguard] keys: x`. It is refused as a TOML error of that file is: its text, no traceback; pytest says
    # it as it says its own TOML error (exit 4), `python -m flowguard` and the vitest preparation as `flowguard: ...`
    # (exit 2), so a vitest run ends with that text (a TOML error there was a traceback too). A TOML error's text names
    # the file (FD2 open 1: `flowguard: Invalid statement (at line 4, column 1)` named none).
    import tomllib
    root = _commit(tmp_path, {'pytest.ini': '[pytest]\npythonpath = .\naddopts = -p flowguard.intent.plugin\n',
                              'pyproject.toml': '[project]\nname = "studio"\nversion = "0"\n', **CORE})
    (root / 'pyproject.toml').write_text(f'[project]\nname = "studio"\nversion = "0"\n\n{value}\n', encoding='utf-8')
    result = _pytest(root)
    assert result.returncode == 4 and 'Traceback' not in result.stdout + result.stderr, result.stdout + result.stderr
    assert f'ERROR: pyproject.toml: {words}' in (result.stdout + result.stderr).splitlines(), result.stdout + result.stderr
    for command in (['check', '--static'], ['show', 'total']):
        run = _flowguard(root, *command)
        assert (run.returncode, run.stdout, run.stderr) == (2, '', f'flowguard: pyproject.toml: {words}\n'), run
    prepare = _run(root, ABSENT + 'from flowguard.intent.vitest import main\nraise SystemExit(main(sys.argv[1:]))\n',
                   'prepare', '--root', str(root))
    assert (prepare.returncode, prepare.stdout, prepare.stderr) == (2, '', f'flowguard: pyproject.toml: {words}\n'), prepare
    (root / 'pyproject.toml').write_text('[project]\nname = "studio"\nversion = "0"\n<<<<<<< HEAD\n', encoding='utf-8')
    with pytest.raises(tomllib.TOMLDecodeError) as refused:
        tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    said = f'flowguard: pyproject.toml does not parse: {refused.value}\n'
    prepare = _run(root, ABSENT + 'from flowguard.intent.vitest import main\nraise SystemExit(main(sys.argv[1:]))\n',
                   'prepare', '--root', str(root))
    assert (prepare.returncode, prepare.stdout, prepare.stderr) == (2, '', said), prepare
    static = _flowguard(root, 'check', '--static')
    assert (static.returncode, static.stdout, static.stderr) == (2, '', said), static
