"""tests/RETIRED_4_3.md: each test retired with the 4.3 sealed comparison names, in its last column, the tests that
still cover what of it holds under 4.3. Each of those must exist, or the list promises coverage no test gives."""
import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
LISTED = TESTS / 'RETIRED_4_3.md'


def _rows(text):
    """(line number, retired test, still covered by) of each row of the table, by its four columns."""
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith('|') or line.startswith(('| Test |', '|---')):
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split(' | ')]
        assert line.startswith('| `') and len(cells) == 4, f'RETIRED_4_3.md:{number} is no row of a retired test: {line}'
        rows.append((number, cells[0], cells[3]))
    return rows


def _tests(path):
    """The tests a pytest file defines: each top-level `test_...` function, and `Class::test_...` of a class."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    found = {node.name for node in tree.body if isinstance(node, functions)}
    found |= {f'{node.name}::{item.name}' for node in tree.body if isinstance(node, ast.ClassDef)
              for item in node.body if isinstance(item, functions)}
    return {name for name in found if name.rpartition('::')[2].startswith('test')}


def _missing(text, tests):
    """Each entry of the last column of `text` that names no test under the folder `tests`: one written as
    `file.py::test_name` (the file by its path below `tests`, or by an end of it that one file alone has), whose file
    defines that test (`_tests`). A backticked entry of any other form names none either."""
    files = [path for path in tests.rglob('*.py') if '__pycache__' not in path.parts]
    problems = []
    for number, _, covered in _rows(text):
        entries = re.findall(r'`([^`]+)`', covered)
        if not entries:
            problems.append(f'RETIRED_4_3.md:{number} names no test that still covers it')
        for entry in entries:
            spelled, _, name = entry.partition('::')
            found = [path for path in files if path.relative_to(tests).as_posix() == spelled
                     or path.relative_to(tests).as_posix().endswith('/' + spelled)]
            if not name or not spelled.endswith('.py'):
                problems.append(f'RETIRED_4_3.md:{number}: {entry} is no file.py::test_name')
            elif len(found) != 1:
                problems.append(f'RETIRED_4_3.md:{number}: {entry}: {len(found)} files are {spelled}')
            elif name.partition('[')[0] not in _tests(found[0]):
                problems.append(f'RETIRED_4_3.md:{number}: {entry}: {spelled} has no test {name}')
    return problems


def test_every_still_covered_by_entry_names_a_test_that_exists():
    text = LISTED.read_text(encoding='utf-8')
    assert _rows(text) and _missing(text, TESTS) == []


def test_an_entry_naming_no_existing_test_is_found(tmp_path):
    (tmp_path / 'engine').mkdir()
    (tmp_path / 'engine/test_kept.py').write_text('def test_kept():\n    pass\n\ndef helper():\n    pass\n\n'
                                                  'class TestGroup:\n    def test_member(self):\n        pass\n')
    (tmp_path / 'engine/test_twice.py').write_text('def test_one():\n    pass\n')
    (tmp_path / 'other').mkdir()
    (tmp_path / 'other/test_twice.py').write_text('def test_one():\n    pass\n')
    head = '| Test | Removed mechanism | Design | Still covered by |\n|---|---|---|---|\n'
    def row(covered):
        return '| `tests/engine/test_gone.py::test_gone` | a mechanism | 4.5 | ' + covered + ' |\n'
    assert _missing(head + row('`test_kept.py::test_kept` (its subject), `engine/test_kept.py::TestGroup::test_member`'),
                    tmp_path) == []
    assert _missing(head + row('`test_kept.py::test_renamed`') + row('`test_kept.py::helper`') + row('`test_absent.py::test_kept`')
                    + row('`test_twice.py::test_one`') + row('`test_kept`') + row('nothing'), tmp_path) == [
        'RETIRED_4_3.md:3: test_kept.py::test_renamed: test_kept.py has no test test_renamed',
        'RETIRED_4_3.md:4: test_kept.py::helper: test_kept.py has no test helper',
        'RETIRED_4_3.md:5: test_absent.py::test_kept: 0 files are test_absent.py',
        'RETIRED_4_3.md:6: test_twice.py::test_one: 2 files are test_twice.py',
        'RETIRED_4_3.md:7: test_kept is no file.py::test_name',
        'RETIRED_4_3.md:8 names no test that still covers it']
