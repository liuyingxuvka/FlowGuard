"""Real static clues remain clues until an explicit home is checked by pytest."""
import collections
import subprocess


def test_class_search_uses_constructor_and_methods_and_excludes_its_members(repo):
    repo.write({'policy.py': '''
        class Policy:
            def __init__(self, quota):
                self.accepted = quota <= 3
            def check(self, quota):
                return quota <= 3
        def other(quota): return quota <= 3
    '''})
    mapped = repo.build()
    result = mapped.search_homes('policy:Policy')
    assert result['searched']
    assert result['anchors'][0] == 'policy:Policy.__init__'
    assert {r['id'] for r in result['candidates']} == {'policy:other'}


def test_zero_sites_and_explicit_zero_realized_sites_are_not_searched(repo):
    repo.write({'policy.py': 'class Empty: pass\ndef fixed(): return 1\ndef check(quota): return quota <= 3\n'})
    mapped = repo.build()
    for target, scope in [('policy:Empty', None), ('policy:fixed', None), ('policy:check', [])]:
        result = mapped.search_homes(target, sites=scope)
        assert not result['searched'] and 'not searched' in result['reason']


def test_a_gone_home_is_explicitly_unsearched_not_an_empty_success(repo):
    repo.write({'policy.py': 'def owner(quota): return quota <= 3\n'})
    mapped = repo.build()
    result = mapped.search_homes('policy:gone')
    assert not result['searched'] and result['total'] == 0
    assert result['candidates'] == [] and 'anchor gone: policy:gone' in result['reason']


def test_import_root_aliases_do_not_recommend_a_bound_home_again(repo):
    repo.write({'pyproject.toml': '[tool.flowguard]\nroots=["src"]\n',
                'src/pkg/__init__.py': '',
                'src/pkg/policy.py': 'def first(quota): return quota <= 3\ndef bound(quota): return quota <= 3\n'})
    mapped = repo.build()
    assert mapped.canonical('src.pkg.policy:first') == 'pkg.policy:first'
    result = mapped.search_homes('src.pkg.policy:first', not_same=['src.pkg.policy:bound'])
    assert result['searched'] and result['anchors'] == ['pkg.policy:first']
    assert result['candidates'] == []


def test_comparisons_returned_inside_containers_are_decisions(repo):
    repo.write({'policy.py': 'def card(importance): return {"important": importance >= 0.75}\ndef count(importance): return importance >= 0.7\n'})
    mapped = repo.build()
    assert any(site['field']=='importance' for site in mapped.sites('policy:card'))


def test_cached_old_constants_find_stale_copies_after_a_change(repo):
    repo.write({'limits.py': 'TRANSFER_LIMIT = 1000000\n',
                'policy.py': 'from limits import TRANSFER_LIMIT\ndef check(transfer_bytes): return transfer_bytes <= TRANSFER_LIMIT\n',
                'copy.py': 'def copied(transfer_bytes): return transfer_bytes <= 1000000\n'})
    mapped = repo.build()
    mapped.close()
    repo.write({'limits.py': 'TRANSFER_LIMIT = 2000000\n'})
    mapped = repo.build()
    candidate = next(r for r in mapped.search_homes('policy:check')['candidates'] if r['id']=='copy:copied')
    assert candidate['stale'] and candidate['old_values']==['1000000']
    assert not candidate['identity_shared'] and 'verdict' not in candidate


def test_fresh_clone_uses_git_old_source_without_executing_it(repo):
    repo.write({'limits.py': 'TRANSFER_LIMIT = 1000000\n',
                'policy.py': 'from limits import TRANSFER_LIMIT\ndef check(transfer_bytes): return transfer_bytes <= TRANSFER_LIMIT\n',
                'copy.py': 'def copied(transfer_bytes): return transfer_bytes <= 1000000\n'})
    command = ['git','-C',str(repo.path)]
    subprocess.run(command+['init','-q'],check=True)
    subprocess.run(command+['add','-A'],check=True)
    subprocess.run(command+['-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','old decision'],check=True)
    repo.write({'limits.py': 'TRANSFER_LIMIT = 2000000\n'})
    mapped = repo.build()
    candidate = next(r for r in mapped.search_homes('policy:check',since='HEAD')['candidates'] if r['id']=='copy:copied')
    assert candidate['stale'] and candidate['old_values']==['1000000']


def test_rare_result_literals_help_search_but_common_status_words_do_not(repo):
    repo.write({'policy.py': 'def first(): return "unpaid membership"\ndef second(): return "unpaid membership"\ndef common(): return "PASS"\ndef another(): return "PASS"\n'})
    mapped = repo.build()
    assert 'policy:second' in {r['id'] for r in mapped.search_homes('policy:first')['candidates']}
    assert not mapped.search_homes('policy:common')['searched']


def test_bound_and_distinct_homes_are_not_recommended_again(repo):
    repo.write({'policy.py': 'def first(quota): return quota <= 3\ndef bound(quota): return quota <= 3\ndef distinct(quota): return quota <= 4\n'})
    mapped = repo.build()
    assert not mapped.search_homes('policy:first',not_same=['policy:bound','policy:distinct'])['candidates']


CONTEXTS = '''
import contextlib as cl
from contextlib import suppress as quiet
hush = cl.suppress
also = getattr(cl, 'suppress')
class Swallow:
    def __enter__(self): return self
    def __exit__(self, *details): return True
class Passes:
    def __exit__(self, *details): return None
class Lambda:
    __exit__ = lambda self, *details: True
def f():
    with quiet(OSError): g()
    with cl.suppress(KeyError): g()
    with hush(ValueError): g()
    with also(TypeError): g()
'''


def test_fixed_handlers_preserve_the_six_existing_lw_context_controls(repo):
    repo.write({'probe.py': CONTEXTS})
    mapped = repo.build()
    found = collections.Counter(row['node'].partition(':')[2]+':'+row['type'] for row in mapped.handlers())
    assert found == {'f:suppress(OSError)':1,'f:suppress(KeyError)':1,'f:suppress(ValueError)':1,'f:suppress(TypeError)':1,
                     'Swallow.__exit__:may return true':1,'Lambda:__exit__ may return true':1}


def test_call_aliases_and_finally_exit_share_the_same_source_reader(repo):
    repo.write({'probe.py': '''
        from pytest import skip as hidden
        def f():
            try: broken()
            finally: return None
        def g(): hidden('reason')
    '''})
    mapped = repo.build()
    assert any(row['kind']=='finally' for row in mapped.handlers())
    assert any(row['resolved']=='pytest.skip' for row in mapped.calls())


def test_numeric_tables_do_not_borrow_call_arguments_or_subscript_indices(repo):
    repo.write({'units.py': 'TABLE={"small":0.001,"large":1000,"hour":3600}\n',
                'probe.py': 'def real(): return (0.001,1000,3600)\ndef not_a_table(x): return [build(0.001,1000,3600), x[3600]]\n'})
    mapped = repo.build()
    found = mapped.literal_sets(numeric=True,shares_with='units:TABLE',min_shared=3).outside('units')
    assert {row['node'] for row in found}=={'probe:real'}


def test_source_lines_are_physical_lines_from_the_one_read(repo):
    repo.write({'policy.py': '# comment\n\ndef check(): return True\n', 'tests/test_policy.py': 'def test_ok(): assert True\n'})
    mapped = repo.build()
    assert mapped.stats['source_lines']==3 and mapped.stats['test_lines']==1


def test_word_search_ranks_sites_before_names(repo):
    repo.write({'policy.py': 'def unrelated(quota): return quota <= 3\ndef documented():\n    """quota"""\n    return 1\ndef quota_name(): return 1\n'})
    mapped = repo.build()
    assert [row['id'] for row in mapped.search('quota')][:3]==['policy:unrelated','policy:documented','policy:quota_name']
