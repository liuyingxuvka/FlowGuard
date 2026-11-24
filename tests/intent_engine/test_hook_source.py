"""The call hook's source text is inspect.getsource's, whatever changed since the last test asked, while it is still
the hooked function's own text: a file saved after FlowGuard imported it, or lines inserted above the function, never
put another function's text into its hook (R85)."""
import ast
import re
import importlib.util
import inspect
import linecache
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import types
import uuid

import pytest

from flowguard.intent import sites


def load(path):
    spec = importlib.util.spec_from_file_location('hook_source_' + uuid.uuid4().hex, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rewrite(path, text):
    before = os.stat(path).st_mtime_ns
    path.write_text(text)
    os.utime(path, ns=(before + 10**9, before + 10**9))      # a new status even within one clock tick


def test_reused_block_follows_the_file_and_the_cached_lines(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text('def grace(days):\n    return days > 3\nLIMIT = 1\n')
    grace = load(path).grace
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days > 3\n'
    # The body changes on disk: checkcache drops the old lines.
    rewrite(path, 'def grace(days):\n    return days >= 30\nLIMIT = 1\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n'
    # The line after the block, which the tokenizer read to end it, becomes part of the block.
    rewrite(path, 'def grace(days):\n    return days >= 30\n    LIMIT = 1\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n    LIMIT = 1\n'
    # The function now ends the file; text appended later still belongs to it.
    rewrite(path, 'def grace(days):\n    return days >= 30\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n'
    rewrite(path, 'def grace(days):\n    return days >= 30\n    # still the body\n    pass\n')
    assert sites._source(grace) == inspect.getsource(grace)
    assert sites._source(grace).endswith('    pass\n')
    # The cached lines themselves are edited, without any file change.
    lines = linecache.getlines(str(path))
    lines[1] = '    return days < 0\n'
    assert sites._source(grace) == inspect.getsource(grace)
    assert 'days < 0' in sites._source(grace)


def test_a_block_found_without_reading_the_lines_is_not_kept(tmp_path, monkeypatch):
    # A getblock that indexes its lines instead of tokenizing them: nothing shows which lines its answer read.
    def indexed(lines):
        return lines[:next((i for i in range(1, len(lines)) if not lines[i].startswith(' ')), len(lines))]
    monkeypatch.setattr(inspect, 'getblock', indexed)
    path = tmp_path / 'policy.py'
    path.write_text('def grace(days):\n    return days > 3\nLIMIT = 1\n')
    grace = load(path).grace
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days > 3\n'
    rewrite(path, 'def grace(days):\n    return days >= 30\n    LIMIT = 1\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n    LIMIT = 1\n'


@pytest.mark.parametrize('name', ['getsource', 'getsourcelines', 'getblock'])
def test_a_replaced_inspect_function_is_used_as_getsource_uses_it(tmp_path, monkeypatch, name):
    path = tmp_path / 'policy.py'
    path.write_text('def grace(days):\n    return days > 3\n')
    grace = load(path).grace
    assert sites._source(grace) == 'def grace(days):\n    return days > 3\n'       # the block is kept now
    real = getattr(inspect, name)
    if name == 'getsource':
        replaced = lambda fn: 'def grace(days):\n    pass\n'
    elif name == 'getsourcelines':
        replaced = lambda fn: (['def grace(days):\n', '    pass\n'], 1)
    else:
        replaced = lambda lines: [lines[0], '    pass\n']
    monkeypatch.setattr(inspect, name, replaced)
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    pass\n'
    # A block read while the replacement stood is not the one read after it is gone.
    monkeypatch.setattr(inspect, name, real)
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days > 3\n'


def test_an_object_that_claims_to_be_a_function_is_read_as_getsource_reads_it(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text('def grace(days):\n    return days > 3\n')
    grace = load(path).grace
    reads = []

    class Claimed:
        def __getattribute__(self, name):
            reads.append(name)
            return types.FunctionType if name == '__class__' else getattr(grace, name)

    claimed = Claimed()
    text = inspect.getsource(claimed)
    expected, reads[:] = list(reads), []
    assert sites._source(claimed) == text == 'def grace(days):\n    return days > 3\n'
    assert reads == expected and reads.count('__wrapped__') == 1


def test_reused_block_keeps_the_shim_of_the_current_source(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text('class Grace:\n    def days(self, value):\n        return value > 3\n')
    owner = load(path).Grace
    with sites.intercepted(owner.days, lambda original, bound: original(*bound.args, **bound.kwargs)):
        assert owner().days(4) is True
    # A private name in the body refuses the shim; the earlier block must not hide it.
    rewrite(path, 'class Grace:\n    def days(self, value):\n        return self.__limit(value)\n')
    with pytest.raises(sites.NotMutable, match='^private names in a method$'):
        with sites.intercepted(owner.days, lambda original, bound: original(*bound.args, **bound.kwargs)):
            pass


# A body the parser warns about three times: an invalid escape, and a decimal and a hexadecimal literal
# directly followed by a keyword. The tokenizer that finds the block does not warn; the parse does, every time.
WARNED = ('import re\n\n\ndef code(text, limit=0):\n'
          '    return re.fullmatch("[A-Z]\\d+", text) is not None and (1if limit else 0x1for limit) > 0\n')


def test_every_hook_parses_again_and_warns_as_the_parser_does(tmp_path, recwarn):
    path = tmp_path / 'policy.py'
    path.write_text(WARNED)
    code = load(path).code
    recwarn.clear()
    ast.parse(textwrap.dedent(inspect.getsource(code)))
    parsed = [(warning.category, str(warning.message)) for warning in recwarn]
    assert len(parsed) == 3 and any(message == "invalid escape sequence '\\d'" for _, message in parsed), parsed
    for _ in range(3):
        recwarn.clear()
        with sites.intercepted(code, lambda original, bound: original(*bound.args, **bound.kwargs)):
            assert code('A1') is True
        assert [(warning.category, str(warning.message)) for warning in recwarn] == parsed


def _git(root, *arguments):
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    *arguments], check=True, capture_output=True, text=True, timeout=60)


def _summary(stdout):
    """pytest's warnings summary: each message with the places listed above it."""
    section = stdout.split(' warnings summary ', 1)[1].split('\n-- Docs:', 1)[0]
    places = {}
    for entry in section.strip('= \n').split('\n\n'):
        lines = entry.splitlines()
        heads = [line for line in lines if not line.startswith(' ')]
        places.setdefault(lines[len(heads)].strip(), []).extend(heads)
    return places


def test_a_changed_function_hooked_in_two_tests_warns_in_both(tmp_path):
    root = tmp_path / 'shop'
    root.mkdir()
    (root / 'policy.py').write_text('def code(text, limit=0):\n    return text[:1].isupper()\n')
    (root / 'test_policy.py').write_text('from policy import code\n\n\ndef test_one():\n    assert code("A1")\n\n\n'
                                         'def test_two():\n    assert not code("a1")\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    (root / 'policy.py').write_text(WARNED)             # not committed: FlowGuard hooks the changed function
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, str(Path(__file__).resolve().parents[2]), '-q',
                             '-p', 'no:cacheprovider'], cwd=root, capture_output=True, text=True, timeout=180)
    assert '2 passed' in result.stdout, result.stdout + result.stderr
    # Each test's hook parses the function's text again, so pytest records the parser's warnings in both.
    hooked = [places for message, places in _summary(result.stdout).items()
              if message.startswith('<unknown>:2: ') and message.endswith("invalid escape sequence '\\d'")]
    assert hooked == [['test_policy.py::test_one', 'test_policy.py::test_two']], result.stdout


# The PEMEL Studio module: area(w, h) between two other functions (2026-11-23 note).
AREA = 'def head():\n    return 1\n\n\ndef area(w, h):\n    return w * h\n\n\ndef tail(x):\n    return x + 1\n'
ABOVE = {'helper': 'def clamp(x): return max(0, x)\n\n\n', 'three parameters': 'def other(a, b, c):\n    return a\n\n\n',
         'no def': 'LIMIT = 0\n\n\n'}


@pytest.mark.parametrize('above', ABOVE.values(), ids=ABOVE)
def test_lines_inserted_above_a_function_never_become_its_hook(tmp_path, above):
    # A module another loader read: no import fingerprint, so the text must start at the code's first line and define
    # the code's name. Before, inspect.findsource read the def above (or, on 3.11/3.12, walked back to head) and the
    # hook was compiled from that signature into area.__code__.
    path = tmp_path / 'mod.py'
    path.write_text(AREA)
    area = load(path).area
    code = area.__code__
    rewrite(path, AREA.replace('def area', above + 'def area', 1))
    with pytest.raises(sites.NotMutable, match=f'^source of {re.escape(str(path))} no longer holds area at line 5$'):
        with sites.intercepted(area, lambda original, bound: original(*bound.args, **bound.kwargs)):
            pass
    with pytest.raises(sites.NotMutable, match=' no longer holds area at line 5$'):
        sites.sites_of(area)
    assert area.__code__ is code and area.__code__.co_varnames == ('w', 'h')
    assert area(w=1, h=1) == 1


def test_a_same_named_def_above_is_not_read_as_the_hooked_method(tmp_path):
    # Python 3.11 and 3.12 walk back from the code's first line to the nearest def: here Square.area, of the same name.
    path = tmp_path / 'shapes.py'
    text = ('class Square:\n    def area(self, side):\n        return side * side\n\n\n'
            'class Rect:\n    def area(self, w, h):\n        return w * h\n')
    path.write_text(text)
    rect = load(path).Rect
    code = rect.area.__code__
    rewrite(path, text.replace('class Rect:\n', 'class Rect:\n    LIMIT = 0\n\n', 1))
    with pytest.raises(sites.NotMutable, match=' no longer holds Rect.area at line 7$'):
        with sites.intercepted(rect.area, lambda original, bound: original(*bound.args, **bound.kwargs)):
            pass
    assert rect.area.__code__ is code and rect().area(w=2, h=3) == 6


def test_a_decorated_function_still_hooks_from_its_first_decorator(tmp_path):
    path = tmp_path / 'mod.py'
    path.write_text('import functools\n\n\ndef logged(fn):\n    @functools.wraps(fn)\n'
                    '    def inner(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return inner\n\n\n'
                    'def mark(fn):\n    return fn\n\n\n@logged\n@mark\ndef area(w, h):\n    return w * h\n')
    area = load(path).area
    assert sites.unwrap(area).__code__.co_firstlineno == 15          # the first decorator's line
    calls = []
    with sites.intercepted(area, lambda original, bound: calls.append(dict(bound.arguments)) or original(*bound.args)):
        assert area(w=2, h=3) == 6
    assert calls == [{'w': 2, 'h': 3}] and area(1, 1) == 1


IMPORTED = """
import os, sys
from pathlib import Path
from flowguard.intent import sites
from flowguard.intent.imports import prepare
prepare('.')
import mod
area, code = mod.area, mod.area.__code__
calls = []
hook = lambda original, bound: calls.append(dict(bound.arguments)) or original(*bound.args, **bound.kwargs)
with sites.intercepted(area, hook):
    assert area(2, 3) == 6
assert calls == [{'w': 2, 'h': 3}] and area.__code__ is code
assert [site.text for site in sites.sites_of(area)] == ['w > 0']
source = Path('mod.py')
saved = source.read_text()
for text in sys.argv[1:]:
    source.write_text(text)       # the same lines and names: only the bytes show it is not the imported text
    for read in (lambda: sites.intercepted(area, hook).__enter__(), lambda: sites.sites_of(area)):
        try:
            read()
        except sites.NotMutable as error:
            assert str(error) == 'source of mod.py changed on disk after import', error
        else:
            raise AssertionError('a file saved after import was read as the imported function')
    assert area.__code__ is code and area(w=1, h=1) == 1
import warnings
source.write_text(saved.replace('w * h if', 'len("\\\\d") * w * h if'))
with warnings.catch_warnings(record=True) as caught:      # its text is not read: no warning of a text never imported
    warnings.simplefilter('always')
    try:
        sites.sites_of(area)
    except sites.NotMutable as error:
        assert str(error) == 'source of mod.py changed on disk after import', error
    else:
        raise AssertionError('a file saved after import was read as the imported function')
assert caught == [], [str(warning.message) for warning in caught]
source.unlink()
try:
    sites.sites_of(area)
except sites.NotMutable as error:
    assert str(error) == 'source of mod.py changed on disk after import', error
else:
    raise AssertionError('a deleted file was read as the imported function')
read = sites._source
for text in sys.argv[1:]:         # saved while the text is read: the read fails, or reads the new text
    def saving(fn, text=text):
        source.write_text(text)
        return read(fn)
    source.write_text(saved)
    sites._source = saving
    try:
        sites.sites_of(area)
    except sites.NotMutable as error:
        assert str(error) == 'source of mod.py changed on disk after import', error
    else:
        raise AssertionError('a file saved during the read was read as the imported function')
    finally:
        sites._source = read
source.write_text(saved)          # the imported bytes again: hooked and read as before
with sites.intercepted(area, hook):
    assert area(4, 5) == 20
assert calls[-1] == {'w': 4, 'h': 5} and [site.text for site in sites.sites_of(area)] == ['w > 0']
print('ok')
"""


def test_a_file_saved_after_import_is_not_read_as_the_imported_function(tmp_path):
    source = 'def head():\n    return 1\n\n\ndef area(w, h):\n    return w * h if w > 0 else 0\n'
    (tmp_path / 'mod.py').write_text(source)
    setup = 'import sys;sys.path.insert(0,sys.argv.pop(1));'
    saves = [source.replace('w * h', 'w + h'), source.replace('area(w, h)', 'area(w, h, d)'), '']
    result = subprocess.run([sys.executable, '-c', setup + IMPORTED, str(Path(__file__).resolve().parents[2]), *saves],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and result.stdout == 'ok\n', result.stdout + result.stderr


# The PEMEL Studio run: another agent saves app/mod.py while pytest runs. test_two saves it; test_three and
# test_four call area after that. Each save is checked with FlowGuard and without it (addopts empty).
SAVES = {
    'shorter': "MOD.write_text('def area(w, h):\\n    return max(w * h, 1)\\n')",
    'helper above': "MOD.write_text(MOD.read_text().replace('def area', 'def clamp(x): return max(0, x)\\n\\n\\ndef area', 1))",
    'three parameters above': "MOD.write_text(MOD.read_text().replace('def area', 'def other(a, b, c):\\n    return a\\n\\n\\ndef area', 1))",
    'no save': 'pass',
}


def _pemel(root, save):
    (root / 'app').mkdir(parents=True)
    (root / 'tests').mkdir()
    (root / 'app/__init__.py').write_text('')
    (root / 'app/mod.py').write_text(AREA)
    (root / 'tests/test_a.py').write_text(
        'import pathlib\nfrom app import mod\nfrom app.mod import area\n\n'
        "MOD = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'mod.py'\n\n\n"
        'def test_one():\n    assert area(2, 3) == 6\n\n\n'
        f'def test_two():\n    {save}\n    assert area(2, 2) == 4\n\n\n'
        "def test_three():\n    assert mod.area.__code__.co_varnames == ('w', 'h')\n    assert area(w=1, h=1) == 1\n\n\n"
        'def test_four():\n    assert area(0, 5) >= 0\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\naddopts = "-p flowguard.intent.plugin"\n'
                                         'pythonpath = ["."]\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    (root / 'app/mod.py').write_text(AREA.replace('return w * h', 'return max(w * h, 1)'))    # the task's change


@pytest.mark.parametrize('save', SAVES, ids=SAVES)
def test_a_source_saved_during_the_run_never_changes_a_test_outcome(tmp_path, save):
    from tests.intent_engine._cli_fixture import block
    _pemel(tmp_path, SAVES[save])
    changed = (tmp_path / 'app/mod.py').read_text()
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    runs = {}
    for name, options in (('FlowGuard', ()), ('without', ('-o', 'addopts='))):
        (tmp_path / 'app/mod.py').write_text(changed)
        runs[name] = subprocess.run([sys.executable, '-c', bootstrap, str(Path(__file__).resolve().parents[2]), '-q',
                                     '-p', 'no:cacheprovider', *options], cwd=tmp_path, capture_output=True, text=True,
                                    timeout=180)
    for result in runs.values():
        assert result.returncode == 0 and '4 passed' in result.stdout, result.stdout + result.stderr
        assert 'INTERNALERROR' not in result.stdout + result.stderr, result.stdout + result.stderr
    lines = block(runs['FlowGuard'])
    if save == 'no save':       # an unchanged file is hooked and compared as before
        assert lines[1:] == ['changed: area (mod.py:5): (w=0, h=5) was 0, now 1; 1/4 inputs differ -> if you meant it, '
                             'say so'], lines
    else:
        assert lines[1:] == ['not compared: area (source of app/mod.py changed on disk after import) -> not a failure'], \
            lines


def test_a_status_taken_while_the_file_was_just_saved_proves_no_unchanged_bytes(tmp_path):
    # CI on Windows (5.1): a file saved twice within one timestamp tick with the same size kept its status (inode,
    # size, mtime, ctime), so the cached hash said the imported bytes were still there and FlowGuard read the second
    # save's text as the imported function. A status taken while the mtime was that recent is not trusted (git's
    # racily clean entries); an old file's status still is, so a session does not read every file again.
    import time
    from types import SimpleNamespace
    from flowguard.intent import imports
    status = {}

    class Coarse(type(Path())):
        def stat(self, **_):     # a file system that keeps the same status for both saves
            return SimpleNamespace(st_ino=7, st_size=6, st_mtime_ns=status['mtime'], st_ctime_ns=7)

    path = Coarse(tmp_path / 'mod.py')
    finder = imports._finder
    for age, again in ((0, True), (3600, False)):
        status['mtime'] = time.time_ns() - age * 1_000_000_000
        path.write_bytes(b'x = 1\n')
        first = finder.source_hash(path)
        path.write_bytes(b'x = 2\n')
        assert (finder.source_hash(path) != first) is again, age
        finder.hashes.pop(path, None)
