"""The call hook's source text is inspect.getsource's, whatever changed since the last test asked."""
import ast
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
