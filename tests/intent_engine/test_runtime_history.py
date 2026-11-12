"""Previous function proof never substitutes current imports or dynamic state."""
import ast
from contextlib import closing
import json
from pathlib import Path
import sys
import uuid

from flowguard.intent import history
from flowguard.intent.loader import load
from tests.intent_engine._source_fixture import annotate, scenario, source_engine, source_sessions
from tests.intent_engine.test_incremental import fixture, git


def saved_case(tmp_path, old, new):
    root,cfg,module=fixture(tmp_path)
    file=root/(module+'.py')
    file.write_text(annotate(old,'accept','LIMIT',{'x':'int'}))
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','old source')
    base=git(root,'rev-parse','HEAD')
    file.write_text(annotate(new,'accept','LIMIT',{'x':'int'}))
    model=load(cfg);rule=model.rules['LIMIT']
    return history.proven(cfg,rule,rule.live_rows[0],base)


def test_old_literal_constant_is_sealed_without_swapping_current_globals(tmp_path):
    result=saved_case(tmp_path,'LIMIT=4\ndef accept(x):return x<=LIMIT\n',
                      'LIMIT=3\ndef accept(x):return x<=LIMIT\n')
    assert result['status']=='proven',result
    assert result['homes'][0]['actual']=='True'
    assert 'not the whole previous project' in result['scope']


def test_old_dynamic_global_is_unknown(tmp_path):
    result=saved_case(tmp_path,'LIMIT=int("4")\ndef accept(x):return x<=LIMIT\n',
                      'LIMIT=3\ndef accept(x):return x<=LIMIT\n')
    assert result['status']=='unknown',result


def test_external_attribute_is_not_taken_from_current_environment(tmp_path):
    result=saved_case(tmp_path,'import decimal\ndef accept(x):return x<=decimal.MAX_PREC\n',
                      'import decimal\ndef accept(x):return x<=3\n')
    assert result['status']=='unknown',result
    assert 'MAX_PREC' in result['homes'][0]['reason']


def test_old_whitelisted_import_does_not_borrow_the_current_import(tmp_path):
    result=saved_case(tmp_path,'from decimal import Decimal as Numeric\ndef accept(x):return x<=Numeric("4")\n',
                      'from datetime import date as Numeric\ndef accept(x):return x<=3\n')
    assert result['status']=='proven' and result['homes'][0]['actual']=='True',result
    from datetime import date
    live = sys.modules[result['homes'][0]['home'].partition(':')[0]]
    assert live.Numeric is date and live.accept(4) is False


def test_changed_observation_meaning_cannot_use_the_current_anchor_for_old_proof(tmp_path):
    root,cfg,module=fixture(tmp_path)
    source=root/(module+'.py')
    source.write_text(annotate('def accept(x):return x<=4\n','accept','LIMIT',{'x':'int'}).replace('-> answer:', '-> previous:'))
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','old observation meaning')
    source.write_text(annotate('def accept(x):return x<=3\n','accept','LIMIT',{'x':'int'}))
    model=load(cfg);rule=model.rules['LIMIT']
    result=history.proven(cfg,rule,rule.live_rows[0],'HEAD')
    assert result['status']=='unknown',result
    assert 'observation meaning' in result['homes'][0]['reason']


def test_a_cached_old_proof_cannot_replace_execution_at_the_requested_base(tmp_path):
    from flowguard.structure import build
    root,cfg,module=fixture(tmp_path,'return x<=4')
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','old boundary')
    old=git(root,'rev-parse','HEAD')
    (root/(module+'.py')).write_text(annotate('def accept(x):return x<=3\n','accept','LIMIT',{'x':'int'}))
    model=load(cfg);rule=model.rules['LIMIT'];row=rule.live_rows[0]
    previous=history.proven(cfg,rule,row,old)
    assert previous['status']=='proven',previous
    git(root,'add',module+'.py');git(root,'commit','-qm','correct boundary')
    current=git(root,'rev-parse','HEAD')
    with closing(build(root,workers=1)) as graph:
        graph.con.execute('CREATE TABLE IF NOT EXISTS result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
        graph.con.execute('INSERT OR REPLACE INTO result VALUES(?,?,?,?,?)',
                          ('tests/intent/limit.py::LIMIT[rules]','LIMIT','ok',json.dumps({'kind':'rules','verdict':'ok','provisional':True,'proven_rows':[previous]}),1.0))
        graph.con.commit()
    assert history.confirmation(cfg,rule)['cleared']
    observed=history.proven(cfg,rule,row,current)
    assert observed['status']=='regression',observed
    assert observed['homes'][0]['actual']=='False'
    assert sys.modules[module].accept(4) is False


def test_deleted_old_constant_is_replayed_as_its_old_value_not_a_nameerror(tmp_path):
    result=saved_case(tmp_path,'LIMIT=4\ndef accept(x):return x<=LIMIT\n','def accept(x):return x<=3\n')
    assert result['status']=='proven',result
    assert result['homes'][0]['actual']=='True'


def test_dynamic_previous_function_presence_is_not_invented_new_code(tmp_path):
    root,cfg,module=fixture(tmp_path)
    source=root/(module+'.py')
    source.write_text('if True:\n    def accept(x):return x<=4\n')
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','conditional old function')
    source.write_text(annotate('def accept(x):return x<=3\n','accept','LIMIT',{'x':'int'}))
    model=load(cfg);rule=model.rules['LIMIT']
    result=history.proven(cfg,rule,rule.live_rows[0],'HEAD')
    assert result['status']=='unknown',result
    assert 'dynamic function binding' in result['homes'][0]['reason']


def test_stale_row_object_cannot_be_a_new_proof(tmp_path):
    root,cfg,module=fixture(tmp_path,'return x<=4')
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','old boundary')
    (root/(module+'.py')).write_text(annotate('def accept(x):return x<=3\n','accept','LIMIT',{'x':'int'}))
    model=load(cfg);rule=model.rules['LIMIT'];row=rule.live_rows[0]
    file=Path(rule.file);file.write_text(file.read_text().replace('expect=False','expect=True'))
    result=history.proven(cfg,rule,row,'HEAD')
    assert result['status']=='unknown' and 'current row does not pass' in result['reason'],result


def scene_case(tmp_path, changed_fixture=False):
    root=tmp_path/('history_'+uuid.uuid4().hex)
    (root/'tests/intent').mkdir(parents=True)
    module='history_app_'+uuid.uuid4().hex
    intent='''from flowguard.intent import rule,row
@rule('LIMIT',decides='limit',fields={'x':int},source='assumed: independent third-day boundary')
def LIMIT(x):return x<=3
LIMIT.rows(row(x=4,expect=False,why='real fourth-day correction'))
'''
    code,intent=scenario(root,module,'def accept(x):return x<=4\n',intent,rule='LIMIT',target='accept',
                         parameters={'x':'int'},source_parameters={'x':'int'},
                         body='answer=app.accept(x)\nassert type(answer)is bool')
    (root/(module+'.py')).write_text(code)
    (root/'tests/intent/policy.py').write_text(intent)
    if changed_fixture:(root/'tests/conftest.py').write_text('import pytest\n@pytest.fixture(autouse=True)\ndef context():return \"old\"\n')
    git(root,'init','-q');git(root,'add','.');git(root,'commit','-qm','old boundary and native fixture')
    base=git(root,'rev-parse','HEAD')
    (root/(module+'.py')).write_text(code.replace('x <= 4','x <= 3').replace('x<=4','x<=3'))
    if changed_fixture:(root/'tests/conftest.py').write_text('import pytest\n@pytest.fixture(autouse=True)\ndef context():return \"new\"\n')
    model=load(root=root)
    source_engine(model)  # supplies real items and nextitem from this actual Session
    rule=model.rules['LIMIT']
    return history.proven(model.cfg,rule,rule.live_rows[0],base)


NOT_RUN_AGAIN=('source observation unavailable: not compared: the scenario test ran with x=0; '
               'another input needs the test to run again, which FlowGuard never does')


def test_historical_scenario_is_unknown_without_old_event_path_replay(tmp_path):
    result=scene_case(tmp_path)
    # The row (x=4) is not the input the scenario test ran with (its fixture's 0), and no test runs again:
    # the current row is unknown, so no historical answer is claimed, old or new.
    assert result['status']=='unknown' and result['reason']=='current row does not pass at every home',result
    assert result['current']['homes']==[dict(home=result['current']['homes'][0]['home'],status='unknown',reason=NOT_RUN_AGAIN)],result
    assert 'homes' not in result and not any('actual' in answer for answer in result['current']['homes'])


def test_changed_native_fixture_context_is_unknown(tmp_path):
    result=scene_case(tmp_path,changed_fixture=True)
    assert result['status']=='unknown' and result['reason']=='current row does not pass at every home',result
    assert [answer['reason'] for answer in result['current']['homes']]==[NOT_RUN_AGAIN],result


def test_history_product_has_no_archive_rpc_or_private_test_runner():
    tree=ast.parse(Path(history.__file__).read_text())
    imports={alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names}
    assert not imports.intersection({'subprocess','tarfile','tempfile'})
    assert '_PROBE' not in vars(history)
