"""Writers and together agreements on the fields of Python classes, as PEMEL Studio wrote them (5.1, R85, R105).

PEMEL Studio's `Project` is a dataclass whose `dirty: bool = False` only the methods `mark_changed` and `mark_saved` may
write. On 5.0.1 the class-body default counted as an outside write: a pytest run that added the agreement exited 1
although every test passed (PEMELPM-238), an unrelated `tools/build.py:Project` was held to the agreement too
(PEMELPM-318), and a together candidate counted the class body as one of the functions (PEMELPM-327). A class imported
under `if TYPE_CHECKING:` typed no write and no read, and a parameter typed `Any` filed its write under a class named
Any (PEMELPM-317, PEMELPM-333).
"""
import subprocess
import sys

from tests.intent_engine.test_static_check import _block, _commit, _flowguard, _pytest, _static, _write

DOMAIN = '''
    from dataclasses import dataclass, field


    @dataclass
    class Project:
        name: str = "untitled"
        # flowguard: writers Project.dirty Project.mark_changed,Project.mark_saved
        dirty: bool = False
        modified: float = 0.0

        def rename(self, name):
            self.name = name
            self.mark_changed()

        def mark_changed(self):
            self.dirty = True

        def mark_saved(self):
            self.dirty = False
'''
TEST = '''
    from app.domain import Project


    def test_rename():
        project = Project()
        project.rename("x")
        assert project.dirty
        project.mark_saved()
        assert not project.dirty
'''
BASE = {'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n',
        'app/__init__.py': '', 'tools/__init__.py': '',
        'app/domain.py': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Project:\n    name: str = "untitled"\n',
        'tests/test_domain.py': 'from app.domain import Project\n\n\ndef test_name():\n    assert Project().name == "untitled"\n'}


def _plain_pytest(root):
    """pytest without FlowGuard's plugin: the exit code the project's own run has."""
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'], cwd=root,
                            capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout + result.stderr


def _reds(text):
    return [line for line in _block(text) if line.startswith('red: ')]


def test_a_class_body_default_is_no_write_outside_a_writers_agreement(tmp_path):
    # dc2: the change adds the field with its default, the agreement and its two writers; every test passes
    for spelled in ('dirty: bool = False', 'dirty: bool = field(default=False)'):
        root = _commit(tmp_path / spelled.rpartition(' ')[2].partition('(')[0], BASE)
        _write(root, {'app/domain.py': DOMAIN.replace('dirty: bool = False', spelled), 'tests/test_domain.py': TEST})
        assert _plain_pytest(root)[0] == 0
        code, text = _pytest(root)
        assert code == 0 and '1 passed' in text and _reds(text) == [], text
        code, text = _static(root, '--all')
        assert code == 0 and not [line for line in _block(text, everything=True) if 'writers Project.dirty' in line], text
        code, text = _flowguard(root, 'show', 'Project.dirty')
        default = 'declares Project.dirty app/domain.py:8 Project (default' + (' False)' if '= False' in spelled else ')')
        assert code == 0 and default in text.splitlines() and 'outside writers' not in text, text
    # a plain class's default declares it too
    root = _commit(tmp_path / 'plain', BASE)
    _write(root, {'app/domain.py': DOMAIN.replace('@dataclass\n    ', '').replace(': bool = False', ' = False'),
                  'tests/test_domain.py': TEST})
    code, text = _static(root)
    assert code == 0 and _reds(text) == [], text


def test_a_method_that_writes_the_field_outside_the_agreement_stays_red(tmp_path):
    root = _commit(tmp_path, BASE)
    writes = DOMAIN.replace('        def rename(self, name):\n            self.name = name\n            self.mark_changed()',
                            '        def __post_init__(self):\n            self.dirty = False\n\n'
                            '        def rename(self, name):\n            self.name = name\n            self.dirty = True')
    _write(root, {'app/domain.py': writes, 'tests/test_domain.py': TEST})
    code, text = _static(root)
    assert code == 1 and _reds(text) == [
        'red: writers Project.dirty: domain.py:Project.__post_init__ writes Project.dirty outside Project.mark_changed, '
        'Project.mark_saved -> call Project.mark_changed or Project.mark_saved instead',
        'red: writers Project.dirty: domain.py:Project.rename writes Project.dirty outside Project.mark_changed, '
        'Project.mark_saved -> call Project.mark_changed or Project.mark_saved instead'], text


def test_an_agreement_holds_only_the_writes_of_its_own_class(tmp_path):
    # sn: an unrelated tools/build.py:Project sets self.dirty; a write through the package's re-export, and one matched
    # by the field name alone, are still held
    root = _commit(tmp_path, {**BASE, 'app/domain.py': DOMAIN, 'tests/test_domain.py': TEST})
    _write(root, {'tools/build.py': '''
        class Project:
            """A build script's own project record, unrelated to app.domain.Project."""

            def __init__(self):
                self.dirty = False
    ''', 'tests/test_build.py': 'from tools.build import Project\n\n\ndef test_build():\n    assert not Project().dirty\n'})
    assert _plain_pytest(root)[0] == 0
    code, text = _pytest(root)
    assert code == 0 and '2 passed' in text and _reds(text) == [], text
    code, text = _flowguard(root, 'show', 'Project.dirty')
    assert code == 0 and ('writes Project.dirty tools/build.py:5 Project.__init__ (assign) (another class, '
                          'tools.build:Project: not held)') in text.splitlines(), text
    _write(root, {'app/__init__.py': 'from app.domain import Project\n', 'app/work.py': '''
        from app import Project


        def exported(project: Project):
            project.dirty = True


        def untyped(projects):
            project = projects[0]
            project.dirty = True
    '''})
    code, text = _static(root)
    assert code == 1 and [line.partition(' writes ')[0] for line in _reds(text)] == [
        'red: writers Project.dirty: work.py:exported', 'red: writers Project.dirty: work.py:untyped'], text


def test_the_view_of_a_field_no_agreement_names_marks_a_test_double_as_a_fixture(tmp_path):
    root = _commit(tmp_path, {**BASE, 'app/domain.py': DOMAIN.replace('        # flowguard: writers Project.dirty '
                                                                       'Project.mark_changed,Project.mark_saved\n', ''),
                              'tests/test_double.py': 'class Project:\n    def __init__(self):\n        self.dirty = False\n'})
    code, text = _flowguard(root, 'show', 'Project.dirty')
    assert code == 0 and [line for line in text.splitlines() if line.startswith(('writes ', 'declares '))] == [
        'declares Project.dirty app/domain.py:7 Project (default False)',
        'writes Project.dirty app/domain.py:15 Project.mark_changed (assign)',
        'writes Project.dirty app/domain.py:18 Project.mark_saved (assign)',
        'writes Project.dirty tests/test_double.py:3 Project.__init__ (assign) (test fixture)'], text


def test_an_agreement_this_change_adds_over_an_old_writer_says_what_held_at_task_start(tmp_path):
    # dc1 (PEMELPM-254): Project.save wrote dirty before any agreement; this change adds the agreement
    saving = DOMAIN + '''
        def save(self):
            self.dirty = False
    '''
    root = _commit(tmp_path / 'added', {**BASE, 'app/domain.py': saving.replace(
        '        # flowguard: writers Project.dirty Project.mark_changed,Project.mark_saved\n', ''), 'tests/test_domain.py': TEST})
    _write(root, {'app/domain.py': saving})
    code, text = _static(root, '--all')
    assert code == 0 and [line for line in _block(text, everything=True) if line.startswith('before: writers')] == [
        'before: writers Project.dirty at domain.py:Project.save already wrote Project.dirty outside this agreement at '
        'task start; this change added the agreement -> leave it unless your task is about it'], text
    # the same writer under an agreement the task start had broke it
    root = _commit(tmp_path / 'committed', {**BASE, 'app/domain.py': saving, 'tests/test_domain.py': TEST})
    _write(root, {'app/domain.py': saving.replace('"untitled"', '"new"')})
    code, text = _static(root, '--all')
    assert code == 0 and [line for line in _block(text, everything=True) if line.startswith('before: writers')] == [
        'before: writers Project.dirty at domain.py:Project.save was broken at task start -> leave it unless your task '
        'is about it'], text


def test_together_agreements_and_candidates_count_functions_not_class_bodies(tmp_path):
    together = '''
        from dataclasses import dataclass


        @dataclass
        class Project:
            modified: float
            name: str = ""
            # flowguard: together Project.dirty Project.modified
            dirty: bool = False

            def touch(self, now):
                self.dirty = True
                self.modified = now
    '''
    root = _commit(tmp_path / 'tg', {**BASE, 'tests/test_domain.py': 'def test_nothing():\n    pass\n'})
    _write(root, {'app/domain.py': together})
    code, text = _static(root)
    assert code == 0 and _reds(text) == [], text
    # tc: one function writes both fields; the class body is no second one
    root = _commit(tmp_path / 'tc', {**BASE, 'app/domain.py': together.replace(
        '        # flowguard: together Project.dirty Project.modified\n', '').replace('modified: float', 'modified: float = 0.0') + '''
            def save(self):
                self.dirty = False
    '''})
    code, text = _flowguard(root, 'show', 'Project.dirty')
    assert code == 0 and 'together candidate' not in text, text


WORK = '''
    from typing import TYPE_CHECKING, Any, Optional
    import builtins

    from app.domain import Project

    if TYPE_CHECKING:
        from app.domain import Project as LaterProject


    def runtime_typed(project: Project):
        project.dirty = True


    def checking_typed(project: "LaterProject"):
        project.dirty = True


    def any_typed(project: Any):
        project.dirty = True


    def object_typed(project: object):
        project.dirty = True


    def builtin_typed(project: builtins.object):
        project.dirty = True


    def optional_typed(project: Optional["Project"]):
        project.dirty = True


    def quoted_typed(project: "Project"):
        project.dirty = True
'''
READERS = '''
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from app.domain import Project as LaterProject


    def read_checking(project: "LaterProject"):
        return project.dirty
'''


def test_type_checking_imports_and_any_type_writes_and_reads_as_the_class_they_name(tmp_path):
    root = _commit(tmp_path, {**BASE, 'app/domain.py': DOMAIN, 'tests/test_domain.py': TEST, 'app/readers.py': READERS})
    _write(root, {'app/work.py': WORK})
    code, text = _static(root)
    functions = ['any_typed', 'builtin_typed', 'checking_typed', 'object_typed', 'optional_typed', 'quoted_typed',
                 'runtime_typed']
    assert code == 1 and [line.partition(' writes ')[0] for line in _reds(text)] == [
        f'red: writers Project.dirty: work.py:{function}' for function in functions], text
    code, text = _pytest(root)
    assert code == 1 and [line.partition(' writes ')[0] for line in _reds(text)] == [
        f'red: writers Project.dirty: work.py:{function}' for function in functions], text
    code, shown = _flowguard(root, 'show', '--last')
    impact = [line for line in shown.splitlines() if line.startswith('impact: ')]
    assert not [line for line in impact if 'Any.' in line or 'object.' in line], impact
    assert [line for line in impact if line.startswith('impact: checking_typed ')] == [
        'impact: checking_typed now writes Project.dirty; 5 other writers, 1 reader (untyped reads not counted) -> check '
        'them for this change only (python -m flowguard show Project.dirty)'], impact
    code, text = _flowguard(root, 'show', 'Any.dirty')
    assert code == 0 and 'writes Any.dirty' not in text, text


def test_the_view_of_an_agreement_keeps_the_reads_of_its_field(tmp_path):
    # PEMELPM-310's side finding: with a writers agreement, `show Project.dirty` dropped its `reads` lines
    readers = READERS.replace('    if TYPE_CHECKING:', '    from app.domain import Project\n\n    if TYPE_CHECKING:') + \
        '\n\n    def read_runtime(project: Project):\n        return project.dirty\n'
    root = _commit(tmp_path, {**BASE, 'app/domain.py': DOMAIN, 'tests/test_domain.py': TEST, 'app/readers.py': readers})
    code, text = _flowguard(root, 'show', 'Project.dirty')
    assert code == 0 and [line for line in text.splitlines() if line.startswith('reads ')] == [
        'reads Project.dirty app/readers.py:10 read_checking (attribute)',
        'reads Project.dirty app/readers.py:14 read_runtime (attribute)'], text
