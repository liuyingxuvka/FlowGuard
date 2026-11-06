"""Only six source queries; no runtime execution or second source scanner."""
import ast

import pytest

from flowguard.structure import build
from flowguard.structure.query import handler_outcome


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


def test_observed_edges_are_one_fact_even_when_many_tests_enter_them(repo):
    repo.write({'work.py': 'def first(): return 1\ndef second(): return first()\n'})
    mapped = repo.build()
    pair = ('work:second', 'work:first')
    other = ('tests:example', 'work:first')
    assert mapped.add_observed([pair, pair, other, pair]) == 2
    assert mapped.add_observed([other, pair, pair]) == 0
    assert mapped.con.execute("SELECT COUNT(*) FROM edge WHERE prov='observed'").fetchone()[0] == 2


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
