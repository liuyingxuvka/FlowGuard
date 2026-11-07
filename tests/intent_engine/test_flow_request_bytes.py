"""Original literal REQUEST_BYTES cases exercise native disk postconditions.

The isolated source copy retains the production anchors and business reader.
No exercise callback returns the expected payload to the model.
"""
from contextlib import contextmanager
import ast
import difflib
import importlib.util
from pathlib import Path
import sys
import uuid

import pytest

from flowguard.intent import api
from flowguard.intent.anchors import collect_sources
from flowguard.intent.flow import Capture, Flow, Node, Read, Relation, runtime_check
from flowguard.map import records


ORIGINAL_CASES = (
    (False, '原话不加换行'),
    (False, 'line one\r\nline two\n'),
    (True, 'changed words'),
)


def native_reader_source(original):
    assert 'def integrity_problem(root, relative_path):' in original
    tree = ast.parse(original)
    for name in ('write_once', 'read_original_bytes'):
        assert len([node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]) == 1
    return original


def stale_reader_source(text):
    helper = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)
                  and node.name == 'read_original_bytes')
    calls = [node for node in ast.walk(helper) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == '_paths']
    assert len(calls) == 1
    old_call = ast.get_source_segment(text, calls[0])
    altered = ast.parse(old_call, mode='eval').body
    altered.args[1] = ast.Constant('previous.md')
    old_helper = ast.get_source_segment(text, helper)
    return text.replace(old_helper, old_helper.replace(old_call, ast.unparse(altered), 1), 1)


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def scenario(tmp_path, variant='original'):
    original = Path(records.__file__).read_text()
    text = native_reader_source(original)
    reader = 'read_original_bytes'
    if variant == 'normalize': text=text.replace('stream.write(raw)', 'stream.write(raw.replace(b"\\r\\n", b"\\n"))',1)
    elif variant == 'empty': text=text.replace('stream.write(raw)', 'stream.write(b"")',1)
    elif variant == 'overwrite':
        text=text.replace('if path.exists() or any(candidate.exists() for candidate in candidates):','if False:',1)
        text=text.replace('with path.open("xb") as stream:', 'with path.open("wb") as stream:',1)
    elif variant == 'wrong_path': text=text.replace('path, written = _new_file(root, relative_path)','path, written = _new_file(root, relative_path)\n    path = path.with_name("other.md")',1)
    elif variant == 'stale_reader': text=stale_reader_source(text)
    elif variant == 'moved':
        reader='read_original_bytes_moved'
        text=text.replace('read_original_bytes(',reader+'(')
    unique=uuid.uuid4().hex; native_name='flowguard.map.flow_native_'+unique
    native_path=tmp_path/'native_records.py';native_path.write_text(text)
    native=load_source(native_path,native_name)
    case_name='flow_case_'+unique;case_path=tmp_path/'native_case.py'
    body=f'''from pathlib import Path
import {native_name} as native
# flowguard: event request_case(root: str, exists: bool, payload: str)
def request_case(root: str, exists: bool, payload: str):
    path=Path(root)/'original.md'
    (Path(root)/'previous.md').write_bytes(b'previous payload')
    if exists: path.write_bytes(b'first record')
    assert path.exists() is exists
    try:
        native.write_once(root,'original.md',payload.encode('utf-8'))
    except native.MapError:
        assert exists
        assert path.read_bytes()==b'first record'
        return
    body=native.{reader}(root,'original.md')
    assert not exists, 'an existing file must be refused'
    assert body==payload.encode('utf-8')
'''
    case_path.write_text(body);case=load_source(case_path,case_name)
    index=collect_sources(tmp_path,[(native_path.name,native_name),(case_path.name,case_name,True)])
    assert not [i for i in index.issues if i.level=='red'],index.issues
    # Execute the original declaration/rows verbatim; retain their Row objects.
    saved=list(api.DECLARED)
    namespace={}
    source=(Path(__file__).parents[1]/'intent/archive_and_sources.py').read_text()
    tree=ast.parse(source)
    declaration=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='REQUEST_BYTES')
    rows=next(node for node in tree.body if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
              and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name)
              and node.value.func.value.id=='REQUEST_BYTES' and node.value.func.attr=='rows')
    start=min(node.lineno for node in declaration.decorator_list)-1
    original_rule=''.join(source.splitlines(keepends=True)[start:rows.end_lineno])
    try:
        exec("from flowguard.intent import rule,row,Refused\n"+original_rule,namespace)
        rule=namespace['REQUEST_BYTES']
    finally:
        api.DECLARED[:]=saved
    model=Flow('REQUEST_BYTES_FLOW',rule.source,
        (Node('case','request_case',start=True),Node('write','RECORD_WRITE',phase='return',caller='case'),
         Node('refused','RECORD_WRITE',phase='raise',end=True,caller='case'),Node('read','ORIGINAL_BYTES',phase='return',end=True,caller='case')),
        (('case','write'),('write','read'),('case','refused')),
        relations=(Relation(rule,{'exists':Read('case','arg.exists'),'payload':Read('case','arg.payload')},Read('read',view='utf8'),'read'),
                   Relation(rule,{'exists':Read('case','arg.exists'),'payload':Read('case','arg.payload')},Read('refused','error'),'refused')))
    return native,case,index,model,rule,text,original


def run_cases(tmp_path, variant):
    native,case,index,model,rule,_,_=scenario(tmp_path,variant)
    assert [(r.inputs['exists'],r.inputs['payload'])for r in rule.live_rows]==list(ORIGINAL_CASES)
    events=[];native_failures=[]
    for i,(exists,payload)in enumerate(ORIGINAL_CASES):
        directory=tmp_path/('case_'+str(i));directory.mkdir()
        with Capture(tmp_path,index,'row_'+str(i))as capture:
            try: case.request_case(str(directory),exists,payload)
            except (AssertionError,OSError) as error:native_failures.append(type(error).__name__)
        assert capture.issues==[],capture.issues
        events.extend(capture.events)
    return runtime_check(model,events,index),native_failures,(native,index,rule)


def test_original_literal_rows_measure_real_bytes_and_real_refusal(tmp_path):
    result,failures,_=run_cases(tmp_path,'original')
    assert result['verdict']=='ok' and result['checked_relations']==3,result
    assert failures==[]


@pytest.mark.parametrize('variant',['normalize','empty','overwrite','wrong_path','stale_reader'])
def test_native_corruption_is_not_hidden_by_writer_inputs_or_none_return(tmp_path,variant):
    result,failures,_=run_cases(tmp_path,variant)
    assert result['verdict']=='red',result
    assert failures, 'the independent native assertion/read must also reject the bad source'


def test_moved_reader_keeps_anchor_identity_and_same_original_rows(tmp_path):
    result,failures,_=run_cases(tmp_path,'moved')
    assert result['verdict']=='ok' and failures==[],result


def test_reader_is_actually_reused_by_native_integrity_business_function(tmp_path):
    native,case,index,model,rule,_,_=scenario(tmp_path)
    directory=tmp_path/'business';directory.mkdir()
    native.write_once(directory,'original.md',b'original\r\nbytes')
    with Capture(tmp_path,index,'business_read')as captured:
        assert native.integrity_problem(directory,'original.md') is None
    assert [e.result for e in captured.events if e.anchor=='ORIGINAL_BYTES' and e.phase=='return']==[b'original\r\nbytes']


def test_utf8_measurement_view_does_not_strip_bom_or_normalize_newlines(tmp_path):
    native,case,index,model,rule,_,_=scenario(tmp_path)
    # Additional independent native boundary; the three old literal rows above stay unchanged.
    for i,payload in enumerate(('\ufeff原话\r\n','combining e\u0301\n','no newline')):
        directory=tmp_path/('unicode_'+str(i));directory.mkdir()
        with Capture(tmp_path,index,str(i))as captured:case.request_case(str(directory),False,payload)
        assert runtime_check(model,captured.events,index)['red']==[]
        actual=[e.result for e in captured.events if e.anchor=='ORIGINAL_BYTES'and e.phase=='return']
        assert actual==[payload.encode('utf-8')]


def test_scenario_projection_reads_real_outcome_without_calling_rule_predicate(tmp_path):
    from flowguard.intent.flow import relation_observations
    native,case,index,model,rule,_,_=scenario(tmp_path)
    directory=tmp_path/'actual';directory.mkdir()
    with Capture(tmp_path,index,'one')as captured:case.request_case(str(directory),False,'原话不加换行')
    def forbidden(**kw): raise AssertionError('projection must never compute the expected answer')
    rule.eval=forbidden
    projected=relation_observations(model,captured,index,'REQUEST_BYTES')
    assert projected['status']=='observed',projected
    assert len(projected['observations'])==1
    actual=projected['observations'][0]
    assert actual['inputs']==dict(exists=False,payload='原话不加换行')
    assert actual['actual']=='原话不加换行'
    assert actual['sources']['$actual']['anchor']=='ORIGINAL_BYTES'
    assert actual['sources']['$actual']['view']=='utf8'


def test_scenario_projection_preserves_real_refusal_and_missing_readout_is_grey(tmp_path):
    from flowguard.intent.cells import Raised
    from flowguard.intent.flow import relation_observations
    native,case,index,model,rule,_,_=scenario(tmp_path)
    directory=tmp_path/'exists';directory.mkdir()
    with Capture(tmp_path,index,'one')as captured:case.request_case(str(directory),True,'changed words')
    projected=relation_observations(model,captured,index,'REQUEST_BYTES')
    assert projected['status']=='observed',projected
    actual=projected['observations'][0]['actual']
    assert isinstance(actual,Raised) and isinstance(actual.error,native.MapError)
    missing=relation_observations(model,[],index,'REQUEST_BYTES')
    assert missing['status']=='grey' and missing['observations']==[]


def test_projection_refuses_orphan_completions_and_source_identity_changes(tmp_path):
    from dataclasses import replace
    from flowguard.intent.flow import relation_observations
    native,case,index,model,rule,_,_=scenario(tmp_path)
    directory=tmp_path/'actual';directory.mkdir()
    with Capture(tmp_path,index,'one')as captured:case.request_case(str(directory),False,'原话不加换行')
    orphan=[e for e in captured.events if not(e.anchor=='ORIGINAL_BYTES'and e.phase=='call')]
    projected=relation_observations(model,orphan,index,'REQUEST_BYTES')
    assert projected['status']=='grey' and projected['observations']==[]
    broken=[replace(e,source_digest='wrong')if e.anchor=='ORIGINAL_BYTES'else e for e in captured.events]
    projected=relation_observations(model,broken,index,'REQUEST_BYTES')
    assert projected['status']=='grey' and projected['observations']==[]
    assert any('source identity' in r for r in projected['grey'])
