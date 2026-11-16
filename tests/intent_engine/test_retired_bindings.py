"""Retired public calls refuse explicitly; source bindings retain real cache/proof boundaries."""
from contextlib import closing
from pathlib import Path

import pytest

from flowguard.intent import api,calibration,history
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load
from flowguard.intent import deps
from flowguard.structure import build
from tests.intent_engine._source_fixture import annotate,source_sessions
from tests.intent_engine.test_incremental import fixture,execute


def test_removed_adapter_execution_is_not_a_second_public_path():
    assert not hasattr(api,'Home')
    assert not hasattr(api.Rule,'home')
    assert not hasattr(Engine,'call_adapter')
    assert not hasattr(Engine,'run_distinct')
    assert not (Path(api.__file__).parent/'guards.py').exists()


@pytest.mark.parametrize('old',["@R.home('app:accept')\ndef mirror(c,fn):return c.days<=3\n",'from flowguard.intent.api import Home\n'])
def test_old_binding_is_refused_before_intent_execution_with_a_rebuild_route(tmp_path,old):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'tests/intent/policy.py').write_text('raise RuntimeError("must not execute")\nfrom flowguard.intent import rule\n@rule("R",decides="eligibility",fields={"days":int},source="assumed: fixture")\ndef R(days):return days<=3\n'+old)
    model=load(root=tmp_path)
    assert model.errors and all('removed'in e['msg']and'rebuild'in e['msg']for e in model.errors)


# 5.0 removed the intent API 4.3 announced; each name says what to do instead (design 4.7: never ignored silently).
FLOW_ORDER = 'declare the order as flow(ID, source=..., nodes=[Node(...), ...], edges=[...])'
NO_STATE_CHANGES = 'delete it; 5.0 checks no state changes, states(...) still checks the values a field is given'
REMOVED = {
    'precedes': 'precedes was removed in 5.0 -> ' + FLOW_ORDER,
    'guarded_by': 'guarded_by was removed in 5.0 -> ' + FLOW_ORDER,
    'transitions': 'transitions was removed in 5.0 -> ' + NO_STATE_CHANGES,
    'Transition': 'Transition was removed in 5.0 -> ' + NO_STATE_CHANGES,
    'flow(transitions=)': 'flow(transitions=) was removed in 5.0 -> delete transitions= from this flow; 5.0 checks no state changes',
    'checks': 'checks was removed in 5.0 -> bind the rule to its scenario test with flow(ID, ..., relations=[Relation(RULE, {...}, Read(...))])',
    'distinct': ('distinct was removed in 5.0 -> delete it; two rules of one decides= key must agree unless one overrides= the '
                 'other, and python -m flowguard known add copies:NAME --act ignore --why TEXT records copies that are meant to differ'),
    'structure_rule': ('structure_rule was removed in 5.0 -> delete it; states(...) checks the literal values a field is given, '
                       'an ordinary test can check any other source fact'),
    'allow': 'allow was removed in 5.0 -> delete it with its structure_rule',
}


@pytest.mark.parametrize('old,found', [
    ('from flowguard.intent import precedes, guarded_by\nprecedes("SAVED", "PUBLISHED")\n', [(2, 'precedes'), (2, 'guarded_by')]),
    ('from flowguard.intent import transitions, checks\n', [(2, 'transitions'), (2, 'checks')]),
    ('from flowguard.intent.api import Transition, structure_rule, allow\n', [(2, 'Transition'), (2, 'structure_rule'), (2, 'allow')]),
    ("import flowguard.intent as fg\nfg.distinct('A', 'B', why='different roles', source='assumed: separation')\n", [(3, 'distinct')]),
    ("from flowguard.intent import distinct as separate\nseparate('A', 'B', why='different roles', source='assumed: separation')\n",
     [(2, 'distinct')]),
    ("from flowguard.intent import distinct\n@distinct('A', 'B', why='different roles', source='assumed: separation')\n"
     "def adapter(c, fn): raise RuntimeError('cannot be called')\n", [(2, 'distinct')]),
    ("from flowguard.intent import *\n@structure_rule('PATHS', source='assumed: paths')\ndef PATHS(graph): return []\n"
     "def own(checks): return checks\n", [(3, 'structure_rule')]),
    ("from flowguard.intent import flow, Node\nflow('F', source='assumed: f', nodes=[Node('a')], edges=[], transitions=[])\n",
     [(3, 'flow(transitions=)')]),
])
def test_a_removed_intent_name_is_refused_before_the_file_runs_with_what_to_do(tmp_path, old, found):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'tests/intent/policy.py').write_text('raise RuntimeError("must not execute")\n' + old)
    expected = [dict(file='tests/intent/policy.py', line=line, msg=REMOVED[name]) for line, name in found]
    assert load(root=tmp_path).errors == expected
    from flowguard.intent import cache
    from flowguard.intent.config import load_config
    assert cache.scan(load_config(tmp_path))['errors'] == expected        # the static screen and history read the same


def test_a_removed_name_read_in_python_raises_what_to_do():
    import flowguard.intent as fg
    for name in ('precedes', 'guarded_by', 'transitions', 'Transition', 'checks', 'distinct', 'structure_rule', 'allow'):
        for module in (fg, api):
            with pytest.raises(api.IntentError) as raised:
                getattr(module, name)
            assert str(raised.value) == REMOVED[name]
        assert name not in fg.__all__ and name not in api.__all__
    with pytest.raises(api.IntentError, match=r'line \d+: flow\(transitions=\) was removed in 5\.0 -> delete transitions='):
        fg.flow('F', source='assumed: f', nodes=[fg.Node('a')], edges=[], transitions=())
    with pytest.raises(AttributeError):
        fg.no_such_name


def test_a_removed_name_and_a_rule_marker_are_red_lines_of_the_block_in_pytest_and_check(tmp_path):
    from tests.intent_engine._cli_fixture import block
    from tests.intent_engine.test_unverified_outcome import _cli, _project, _pytest
    root = _project(tmp_path / 'p', {
        'orders.py': '''
            def accept(days: int) -> bool:
                return days <= 3
        ''',
        'tests/test_orders.py': '''
            import pytest
            from orders import accept

            @pytest.mark.rule('ACCEPT')
            def test_accept():
                assert accept(3)
        ''',
        'tests/intent/order_rules.py': '''
            from flowguard.intent import precedes
            precedes('SAVED', 'PUBLISHED', source='assumed: a draft is saved before it is published')
        '''})
    lines = ['red: load order_rules.py:1: precedes was removed in 5.0 -> ' + FLOW_ORDER
             + '; until then none of its file is checked',
             'red: marker test_orders.py:4: pytest.mark.rule was removed in 5.0 -> delete the marker; a rule is checked at '
             'its anchors, not through marked tests']
    result, text = _pytest(root, '-q')
    assert result.returncode == 1 and [line for line in block(result) if line.startswith('red: ')] == lines, text
    assert 'deprecated' not in result.stderr and 'PytestUnknownMarkWarning' not in text, text
    result, text = _cli(root, 'check', '--all')
    assert result.returncode == 1 and all(line in text.splitlines() for line in lines), text


def test_source_contract_change_invalidates_with_Map_function_and_file_scope(tmp_path):
    root,cfg,module=fixture(tmp_path)
    outside=root/'outside.py'
    outside.write_text('def unrelated(x): return x + 1\n')
    model,graph,saved,result=execute(cfg)
    assert not saved['reasons'] and result['verdict']=='ok'
    target=module+':accept'
    node_key,file_key='node:'+target,'file:'+module+'.py'
    assert saved['dependencies'][node_key]==graph.node(target)['fp']
    assert file_key in saved['dependencies']
    state={'deps':{'LIMIT':saved},'results':{'LIMIT':{'items':{'cells':result}}}}
    source=root/(module+'.py')
    original=source.read_text()
    graph.close()
    outside.write_text('def unrelated(x): return x + 99\n')
    with closing(build(root))as current:
        now=deps.Now(cfg,current)
        assert deps.stale(saved,now)==[]
        assert deps.reusable(state,'LIMIT',now)
    # The function fingerprint stays local, while the declared file dependency
    # conservatively invalidates any body change in that same file.
    source.write_text(original.replace('return x + 1','return x + 99'))
    with closing(build(root))as current:
        now=deps.Now(cfg,current)
        assert now(node_key)==saved['dependencies'][node_key]
        assert file_key in deps.stale(saved,now) and node_key not in deps.stale(saved,now)
        assert not deps.reusable(state,'LIMIT',now)
    contract=original.replace('LIMIT(x: x)','LIMIT(x: count)')
    assert contract!=original
    source.write_text(contract)
    with closing(build(root))as current:
        now=deps.Now(cfg,current)
        assert now(node_key)==saved['dependencies'][node_key]
        assert file_key in deps.stale(saved,now)
        assert not deps.reusable(state,'LIMIT',now)


def test_equivalent_sources_survive_superseding_as_source_bindings(tmp_path):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'app.py').write_text(annotate('def accept(days):return days<=3\n','accept','GRACE',{'days':'int'}))
    (tmp_path/'tests/intent/policy.py').write_text('''from flowguard.intent import rule,row
@rule('OLD',decides='grace',fields={'days':int},source='assumed: fixture',anchor='GRACE',equivalent=('app.py:2','the independent reason is retained'))
def OLD(days):return days<=3
@rule('NEW',decides='grace',fields={'days':int},source='assumed: replacement',supersedes=[OLD])
def NEW(days):return days<=3
''')
    model=load(root=tmp_path)
    assert not model.errors
    old,new=model.rules['OLD'],model.rules['NEW']
    assert len(new.homes)==1 and isinstance(new.homes[0],api._AnchorBinding)
    assert new.homes[0].equivalent==old.equivalent==(('app.py:2','the independent reason is retained'),)
    assert not hasattr(new.homes[0],'adapter')


def test_old_unanchored_existing_function_is_unknown_not_invented_new_code(tmp_path):
    from tests.intent_engine.test_incremental import git
    root,cfg,module=fixture(tmp_path,'return x <= 4')
    source=root/(module+'.py')
    source.write_text('def accept(x): return x <= 4\n')
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','Old source predates the observation comment')
    old=git(root,'rev-parse','HEAD')
    source.write_text(annotate('def accept(x): return x <= 3\n','accept','LIMIT',{'x':'int'}))
    model=load(cfg);rule=model.rules['LIMIT']
    result=history.proven(cfg,rule,rule.live_rows[0],old)
    assert result['status']=='unknown',result
    assert any('no corresponding observation anchor' in r['reason']for r in result['homes'])


def test_history_tool_failure_cannot_satisfy_a_business_exception(tmp_path):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'app.py').write_text(annotate('def accept(x):return 7\n','accept','LIMIT',{'x':'int'}))
    (tmp_path/'tests/intent/policy.py').write_text('''from flowguard.intent import rule,row,Refused
@rule('LIMIT',decides='refusal',fields={'x':int},anchor='LIMIT',source='assumed: actual business refusal required')
def LIMIT(x):return Refused('Exception')
LIMIT.rows(row(x=4,expect=Refused('Exception'),why='a tool error is not the requested actual refusal'))
''')
    model=load(root=tmp_path);rule=model.rules['LIMIT']
    result=history._probe(tmp_path,rule,rule.live_rows[0])
    assert result['status']=='unknown',result
    assert any('observation unavailable'in r['reason']for r in result['homes'])
