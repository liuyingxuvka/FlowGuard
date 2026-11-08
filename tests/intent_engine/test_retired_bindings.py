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


def test_distinct_decorator_cannot_store_or_call_an_adapter(tmp_path):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'tests/intent/policy.py').write_text('''from flowguard.intent import distinct
@distinct('A','B',why='different roles',source='assumed: original separation')
def adapter(c,fn):raise RuntimeError('cannot be called')
''')
    model=load(root=tmp_path)
    assert any('call adapters were removed'in e['msg']and'rebuild'in e['msg']for e in model.errors)
    assert all(not hasattr(d,'adapter')for d in model.distincts)


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
