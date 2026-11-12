"""FlowGuard's own text is ASCII (design 4.7, D18): the block, steps, titles, show output and CLI messages read the
same on every console, and a Windows console needs no escape for them (`differences.display` escapes project text
only).

The rule: every string literal of FlowGuard's Python code (`flowguard/**/*.py`) except a docstring is ASCII, and the
vitest adapter's JavaScript (`flowguard/adapters/**/*.mjs`) is ASCII throughout. A literal that is not FlowGuard's
own words, but input it reads or a saved value it keeps, is listed in EXCEPTIONS with the reason; nothing else."""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / 'flowguard'

# (file below flowguard/, literal): why it is not FlowGuard's own text
EXCEPTIONS = {
    ('intent/cli.py', '﻿'): 'the byte-order mark a project file may start with, read and written back as it is',
    ('intent/engine.py', '⁣flowguard'): "an invisible separator that makes a probe string apart from the project's own "
                                             'values, never a message',
    ('intent/ledger.py', '旧账'): 'the legacy rule marker `rule = "旧账"` of the fallback ledger, a saved value ledgers carry',
    ('intent/ledger.py', '换成真实的理由：这处做了什么、为什么可以留（不少于 8 个词）'):
        'the placeholder reason an earlier ledger init wrote, read so an unedited old entry stays refused',
    ('intent/ledger.py', '换成真实的理由：为什么这个判断不再回放、由什么守住它（不少于 8 个词）'):
        'the placeholder [unverified] reason an earlier ledger init wrote, read so an unedited old entry stays refused',
    ('intent/ledger.py', '成文规矩所在的文件'): 'the placeholder rule file an earlier ledger init wrote, read so it stays refused',
    ('intent/ledger.py', '该文件里必须出现的一句话'): 'the placeholder rule sentence an earlier ledger init wrote, read so it stays refused',
    ('intent/ledger.py', '[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]'): 'counts Chinese, Japanese and Korean words of a reason',
    ('intent/owners.py', '、'): 'the full-width punctuation `_ascii` turns into ASCII in text that holds it',
    ('intent/owners.py', '；'): 'the full-width punctuation `_ascii` turns into ASCII in text that holds it',
    ('intent/owners.py', '：'): 'the full-width punctuation `_ascii` turns into ASCII in text that holds it',
    ('intent/owners.py', '（'): 'the full-width punctuation `_ascii` turns into ASCII in text that holds it',
    ('intent/owners.py', '）'): 'the full-width punctuation `_ascii` turns into ASCII in text that holds it',
    ('intent/owners.py', '，'): 'the full-width punctuation `_ascii` turns into ASCII in text that holds it',
    ('intent/owners.py', '→'): 'the arrow `_ascii` turns into ASCII in text that holds it',
    ('intent/vitest.py', ' '): 'a JavaScript line terminator the reader of string escapes decodes',
    ('intent/vitest.py', ' '): 'a JavaScript line terminator the reader of string escapes decodes',
    ('structure/query.py', '[一-鿿]'): 'finds the Chinese characters of a query, whose pairs are its words',
}


def _docstrings(tree):
    """The string constants that are a module's, class's or function's docstring (documentation, not output)."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def non_ascii(root=PACKAGE):
    """{(file below `root`, literal): line} of every non-ASCII string literal of the Python files below `root` that is no
    docstring (an f-string's literal parts too), and of every non-ASCII character of the .mjs files there."""
    found = {}
    for path in sorted(root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        docs = _docstrings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and not node.value.isascii() and id(node) not in docs:
                found.setdefault((path.relative_to(root).as_posix(), node.value), node.lineno)
    for path in sorted(root.rglob('*.mjs')):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            for character in dict.fromkeys(character for character in line if not character.isascii()):
                found.setdefault((path.relative_to(root).as_posix(), character), number)
    return found


def test_flowguards_own_text_is_ascii_and_every_exception_says_why():
    found = non_ascii()
    unlisted = {key: line for key, line in found.items() if key not in EXCEPTIONS}
    assert not unlisted, '\n'.join(f'flowguard/{file}:{line}: {text!r}' for (file, text), line in sorted(unlisted.items()))
    assert set(EXCEPTIONS) <= set(found), sorted(set(EXCEPTIONS) - set(found))       # no exception outlives its literal
    assert all(len(reason.split()) >= 8 for reason in EXCEPTIONS.values())


def test_the_scan_finds_a_full_width_literal_an_f_string_part_and_a_character_of_an_adapter(tmp_path):
    (tmp_path / 'intent').mkdir()
    (tmp_path / 'intent/a.py').write_text('"""文档"""\nSTEP = "fix it：now"\nWHERE = f"{1}（line）"\nOK = "plain"\n', encoding='utf-8')
    (tmp_path / 'adapter.mjs').write_text("// ok\nconst x = '→';\n", encoding='utf-8')
    assert non_ascii(tmp_path) == {('intent/a.py', 'fix it：now'): 2, ('intent/a.py', '（line）'): 3, ('adapter.mjs', '→'): 2}
