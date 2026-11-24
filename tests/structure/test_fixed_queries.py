"""Only six source queries; no runtime execution or second source scanner."""
import ast
from collections import Counter

import pytest

from flowguard.structure import build
from flowguard.structure.query import (assigns, bindings, call_on_every_path, handler_outcome, may_suppress,
                                      on_every_path)


def test_config_roots_accept_the_config_objects_absolute_paths(repo, tmp_path):
    repo.write({'src/one.py': 'def one(): return 1\n'})
    mapped = build(repo.path, tmp_path / 'explicit.sqlite', roots=[repo.path / 'src'])
    assert mapped.node('one:one')['file'] == 'src/one.py'
    mapped.close()
    with pytest.raises(ValueError, match='inside the project'):
        build(repo.path, tmp_path / 'outside.sqlite', roots=[tmp_path / 'elsewhere'])


def test_string_pytest_pythonpath_is_one_list_not_a_list_of_characters(repo):
    repo.write({'pyproject.toml': '[tool.pytest.ini_options]\npythonpath="scripts lib"\n',
                'scripts/tool.py': 'def check(): return True', 'lib/helper.py': 'VALUE=3'})
    mapped = repo.build()
    roots = {row['path'] for row in mapped.roots()}
    assert {'scripts', 'lib'} <= roots and 's' not in roots


def test_fixed_queries_read_numeric_tables_in_function_bodies_and_returns(repo):
    repo.write({'units.py': 'TABLE={"one":1,"kilo":1000,"milli":0.001,"half":1/2}\n',
                'consumer.py': '''
                    def check(x):
                        factors = [(f,0.) for f in (0.001,1000,0.5,1/60)]
                        return {"weights": [0.001,1000,0.5], "shape": x}
                '''})
    mapped = repo.build()
    tables = mapped.literal_sets(numeric=True, min_size=3, shares_with='units:TABLE', min_shared=3).outside('units')
    assert tables and {row['node'] for row in tables} == {'consumer:check'}
    assert all(row['partial'] for row in tables)


def test_literal_cache_preserves_unusual_python_literals_as_data(repo):
    repo.write({'sample.py': '''
        VALUES = {b"id": [b"payload", 1j, ...], (1,2): {3,4}}
        def read(): return VALUES
    '''})
    mapped = repo.build()
    tables = mapped.literal_sets()
    assert tables and tables[0]['value']["(1, 2)"] == [3, 4]
    assert tables[0]['value']["b'id'"][0] == {'literal_type': 'bytes', 'hex': '7061796c6f6164'}


def test_state_writers_resolve_only_declared_types_and_keep_unknowns_visible(repo):
    repo.write({'models.py': 'class Hire: pass\n',
                'writers.py': '''
                    from models import Hire as H
                    import models as m
                    class Local:
                        def close(self): self.status = "closed"
                    def a(hire: H): hire.status = "held"
                    def b(hire: m.Hire): hire.status = "returned"
                    def c(hire: "H | None"): hire.status = "lost"
                    def d():
                        hire: H
                        hire.status = "open"
                    def unknown(hire): hire.status = "maybe"
                '''})
    mapped = repo.build()
    writes = {row['value']: (row['field'], row['unresolved']) for row in mapped.assignments() if row['value'] in {'closed','held','returned','lost','open','maybe'}}
    assert writes['closed'] == ('writers:Local.status', False)
    for value in ('held','returned','lost','open'):
        assert writes[value] == ('models:Hire.status', False)
    assert writes['maybe'] == ('writers:hire.status', True)


def test_moving_a_test_keeps_its_old_fingerprint_for_a_proposal(repo):
    repo.write({'tests/test_before.py': 'def test_boundary():\n    assert 4 > 3\n'})
    mapped = repo.build()
    mapped.close()
    repo.remove('tests/test_before.py')
    repo.write({'tests/test_after.py': 'def test_boundary():\n    assert 4 > 3\n'})
    mapped = repo.build()
    assert mapped.node('tests.test_before:test_boundary') is None
    assert mapped.moved(['tests.test_before:test_boundary'])[0]['new'] == 'tests.test_after:test_boundary'


def test_moving_real_code_to_a_test_helper_does_not_lose_identity(repo):
    repo.write({'guard.py': 'class Result:\n    def as_dict(self):\n        return {"status": self.status}\n'})
    mapped = repo.build()
    mapped.close()
    repo.remove('guard.py')
    repo.write({'tests/helpers.py': 'class Result:\n    def as_dict(self):\n        return {"status": self.status}\n'})
    mapped = repo.build()
    assert mapped.moved(['guard:Result.as_dict'])[0]['new'] == 'tests.helpers:Result.as_dict'


def test_a_new_reader_invalidates_old_syntax_facts(repo, monkeypatch):
    from flowguard.structure import store
    repo.write({'source.py': 'def accept(value): return value <= 3\n'})
    mapped = repo.build()
    mapped.close()
    before = store.reader_digest()
    monkeypatch.setattr(store, 'reader_digest', lambda: before + ':new-reader')
    mapped = repo.build()
    assert mapped.stats['parsed'] == 1 and mapped.stats['changed']
    mapped.close()
    mapped = repo.build()
    assert mapped.stats['parsed'] == 0 and not mapped.stats['changed']


def test_a_real_package_named_venv_is_not_an_environment(repo):
    repo.write({'venv/__init__.py': 'def owned(): return True\n'})
    mapped = repo.build()
    assert mapped.node('venv:owned') is not None
    mapped.close()
    repo.write({'venv/pyvenv.cfg': 'home = /outside-python\n'})
    mapped = repo.build()
    assert mapped.node('venv:owned') is None




@pytest.mark.parametrize('body,always_raises', [
    ('raise', True), ('raise ValueError("named")', True),
    ('if strict:\n    raise\nreturn None', False),
    ('if strict:\n    raise\nelse:\n    raise ValueError("other")', True),
    ('if quiet:\n    return None\nraise', False),
    ('for row in rows:\n    raise', False),
    ('for row in rows:\n    continue\nraise', True),
    ('def later():\n    raise\nreturn later', False),
    ('try:\n    raise\nfinally:\n    return None', False),
])
def test_handler_query_uses_all_paths_instead_of_any_raise(body, always_raises):
    statements = ast.parse(body).body
    assert (handler_outcome(statements) == (False, False)) == always_raises


@pytest.mark.parametrize('body,always', [
    ('_apply(p)', True), ('self._apply(p)', True), ('return _apply(p)', True), ('log(await _apply(p))', True),
    ('with lock:\n    _apply(p)', True), ('if _apply(p):\n    pass', True), ('x = _apply(p) or q', True),
    ('for row in _apply(p):\n    pass', True), ('[x for x in _apply(p)]', True),
    ('if not p:\n    raise ValueError(p)\n_apply(p)', True), ('def later():\n    return 1\n_apply(p)', True),
    ('if s:\n    _apply(p)', False), ('if s:\n    pass\nelse:\n    _apply(p)', False),
    ('if not p:\n    return\n_apply(p)', False), ('with lock:\n    if s:\n        return\n_apply(p)', False),
    ('for row in rows:\n    _apply(row)', False), ('while s:\n    _apply(p)', False),
    ('try:\n    _apply(p)\nexcept ValueError:\n    pass', False), ('try:\n    pass\nfinally:\n    _apply(p)', False),
    ('match s:\n    case 1:\n        _apply(p)', False), ('x = _apply(p) if s else None', False),
    ('x = q or _apply(p)', False), ('[_apply(x) for x in rows]', False), ('assert _apply(p)', False),
    ('later = lambda: _apply(p)\nlater()', False), ('def later():\n    _apply(p)\nlater()', False),
    ('apply(p)', False),
    # 5.1 review (FM open 3): a chained comparison runs its later operands on some paths only, and a local name's
    # annotation is never evaluated
    ('x = p < q < _apply(p)', False), ('x = _apply(p) < q < s', True), ('x: _apply(p) = 1', False),
    ('x: int = _apply(p)', True),
])
def test_a_call_on_every_path_is_one_no_branch_return_or_nested_scope_can_skip(body, always):
    """PEMEL17-18: writes moved into a helper are one line only where the call runs whenever the function returns."""
    function = ast.parse('async def f(self, p, q, s, rows, lock):\n' + ''.join(f'    {line}\n' for line in body.splitlines())).body[0]
    assert call_on_every_path(function, '_apply', may_suppress(set(), set(), False, lambda call: False, Counter())) \
        is always


SUPPRESSING = '''import contextlib
from contextlib import suppress as quiet


def f(p, lock, guard):
    BODY
'''


@pytest.mark.parametrize('body,lines,names,held,always', [
    # 5.1 review (FM open 3): a with whose context manager may suppress an error of its block may stop at any of its
    # statements while the function goes on, so neither its block nor, read conservatively, what follows it is on
    # every path
    ('with contextlib.suppress(ValueError):\n        check(p)\n        _apply(p)', {6}, set(), False, False),
    ('with quiet(ValueError):\n        _apply(p)', {6}, set(), False, False),
    ('with contextlib.suppress(ValueError):\n        check(p)\n    _apply(p)', {6}, set(), False, False),
    ('if p:\n        with contextlib.suppress(ValueError):\n            check(p)\n    _apply(p)', {7}, set(), False, False),
    ('with Quiet():\n        _apply(p)', set(), {'Quiet'}, True, False),
    ('with mod.logged():\n        _apply(p)', set(), {'logged'}, False, False),
    ('with guard:\n        _apply(p)', set(), {'Quiet'}, True, False),
    ('with self.guard:\n        _apply(p)', set(), set(), True, False),
    # 5.1 review (FM2 open 3): an ExitStack suppresses what a context manager entered on it suppresses, and a call the
    # reader cannot see into (a library's, a function that returns a context manager) may return one that suppresses
    ('with contextlib.ExitStack() as stack:\n        stack.enter_context(contextlib.suppress(ValueError))\n'
     '        check(p)\n        _apply(p)', set(), set(), False, False),
    ('with contextlib.AsyncExitStack() as stack:\n        _apply(p)', set(), set(), False, False),
    ('with lock.acquire_timeout(5):\n        _apply(p)', set(), set(), False, False),
    ('with make_guard():\n        check(p)\n    _apply(p)', set(), set(), False, False),
    # a context manager the reader sees never suppresses runs its block, and its own expression runs always: the
    # built-in open, and the calls `never` accepts (the caller's reading of the definition a call reaches: the
    # project's own class with an `__exit__` that never returns true, a @contextmanager generator without a quiet
    # handler)
    ('with open(p):\n        _apply(p)', {9}, {'Quiet'}, True, True), ('with lock:\n        _apply(p)', set(), set(), False, True),
    ('with Session():\n        _apply(p)', set(), set(), False, True),
    ('with self.scope():\n        _apply(p)', set(), set(), False, True),
    ('with contextlib.suppress(_apply(p)):\n        pass', {6}, set(), False, True),
    ('_apply(p)\n    with contextlib.suppress(ValueError):\n        check(p)', {7}, set(), False, True),
    # 5.1 review (FM3 open 1): what reads as never suppressing is what the reader sees. `x.open(...)` is no built-in
    # open, and `never` judges the call, not a short name a library call shares (`self.session.begin()`)
    ('with self.store.open(p):\n        _apply(p)', set(), set(), False, False),
    ('with self.session.begin():\n        _apply(p)', set(), set(), False, False),
])
def test_a_call_in_or_after_a_with_that_may_suppress_is_not_on_every_path(body, lines, names, held, always):
    tree = ast.parse(SUPPRESSING.replace('BODY', body))
    never = lambda call: ast.unparse(call.func) in ('Session', 'self.scope')        # noqa: E731
    assert call_on_every_path(tree.body[2], '_apply', may_suppress(lines, names, held, never, bindings(tree))) is always


@pytest.mark.parametrize('module,always', [
    ('def f(p):\n    with open(p):\n        _apply(p)\n', True),
    ('def open(p):\n    return p\n\n\ndef f(p):\n    with open(p):\n        _apply(p)\n', False),
    ('from io import open\n\n\ndef f(p):\n    with open(p):\n        _apply(p)\n', False),
    ('from os import *\n\n\ndef f(p):\n    with open(p):\n        _apply(p)\n', False),
    ('def f(p, open):\n    with open(p):\n        _apply(p)\n', False),
    ('open = None\n\n\ndef f(p):\n    with open(p):\n        _apply(p)\n', False),
])
def test_only_the_builtin_open_called_by_its_bare_name_reads_as_never_suppressing(module, always):
    """5.1 review (FM3 open 1): `open` read as never suppressing by its name alone, a module's own `open` or an
    imported one too. The built-in is the bare name where the module binds no other `open` and has no star import
    (`bindings`)."""
    tree = ast.parse(module)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'f')
    assert call_on_every_path(function, '_apply', may_suppress(set(), set(), False, lambda call: False, bindings(tree))) \
        is always


def test_bindings_counts_each_name_a_module_binds_in_any_scope():
    tree = ast.parse('import os.path\nfrom x import a as b\nfrom y import *\nc = 1\n\n\nclass C:\n    def m(self, d, *e, **f):\n'
                     '        for g in d:\n            with h() as i:\n                pass\n        try:\n            pass\n'
                     '        except E as j:\n            del k\n        global c\n        match d:\n'
                     '            case {"x": l, **m}:\n                pass\n')
    assert bindings(tree) == Counter({'os': 1, 'b': 1, '*': 1, 'c': 2, 'C': 1, 'm': 2, 'self': 1, 'd': 1, 'e': 1, 'f': 1,
                                      'g': 1, 'i': 1, 'j': 1, 'k': 1, 'l': 1})


def test_a_write_on_every_path_is_an_assignment_to_its_field_on_its_line_by_the_same_path_query():
    """5.1 review (FM open 2): the helper's write of a moved field is placed as its write row has it (an assignment on
    the row's line to that field) and judged by the same path query as the call."""
    function = ast.parse('def g(p, s):\n    p.a = 1\n    if s:\n        p.b = 2\n    p.c, p.d = 3, 4\n'
                         '    p["e"] = 5\n    q = p.a\n').body[0]
    never = may_suppress(set(), set(), False, lambda call: False, Counter())
    assert [on_every_path(function, lambda node, line=line, field=field: assigns(node, line, field), never)
            for line, field in ((2, 'a'), (4, 'b'), (5, 'd'), (6, 'e'), (7, 'a'), (2, 'b'))] == \
        [True, False, True, True, False, False]
