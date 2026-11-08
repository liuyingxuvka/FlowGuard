"""Static source navigation follows direct anchors and Flow reading bindings."""
from contextlib import closing

from flowguard.intent import anchors, cache, cli
from flowguard.intent.config import load_config
from flowguard.structure import build


APP = '''# flowguard: sensor grace(days: day) -> allowed: bool calibrated_by=tests/test_app.py::test_allowed
def owner(days: int) -> bool:
    return days <= 3
# flowguard: sensor grace(days: day) -> allowed: bool
def declared_copy(days: int) -> bool:
    return days <= 3
# flowguard: sensor preview(days: day) -> visible: bool
def declared_separate(days: int) -> bool:
    return days <= 3
def missed_payment_copy(days: int) -> bool:
    """The same payment policy copied into another channel."""
    return days <= 3
def chart_preview(days: int) -> bool:
    """An independent chart rendering window, not a payment eligibility policy."""
    return days <= 3
'''

RULE = '''from flowguard.intent import rule, row, distinct
OWNER = 'grace'
@rule('GRACE', decides='payment eligibility', fields={'days':int},
      source='doc POLICY.md "Late payments have a three day grace."', anchor=OWNER)
def GRACE(days):
    return days <= 3
GRACE.rows(row(days=4, expect=False, why='fourth day refused'))
distinct('grace','preview',why='payment eligibility and a chart display have different roles',
         source='assumed: independent business and display roles')
'''


def project(tmp_path, *, flow_only=False, wildcard=False):
    root = tmp_path/'project';root.mkdir()
    (root/'app.py').write_text(APP)
    (root/'POLICY.md').write_text('Late payments have a three day grace.\n')
    (root/'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["POLICY.md"]\n')
    folder=root/'tests/intent';folder.mkdir(parents=True)
    (root/'tests/test_app.py').write_text('''from app import owner
import pytest
# flowguard: event case(days: int) calibrated_by=tests/test_app.py::test_allowed[2]
@pytest.mark.parametrize('days',[2])
def test_allowed(days: int):
    assert owner(days) == (days <= 3)
''')
    body=RULE
    if flow_only:
        body=body.replace(', anchor=OWNER','')
        body += '''
from flowguard.intent import flow,Node as N,Read as R,Relation as Rel
POINTS=(N('scenario','case'),N('answer','grace',phase='return'))
flow('CASE_MODEL',source='assumed: explicit test scenario and actual return',nodes=POINTS,
     edges=(('scenario','answer'),),
     relations=(Rel(GRACE,{'days':R('scenario','arg.days')},R('answer'),on='answer'),))
'''
        if wildcard:body=body.replace('from flowguard.intent import flow,Node as N,Read as R,Relation as Rel',
                                      'from flowguard.intent import *\nN=Node\nR=Read\nRel=Relation')
    (folder/'policy.py').write_text(body)
    return root,load_config(root)


def test_direct_rule_show_finds_actual_source_and_calibration_without_import(tmp_path,capsys):
    root,cfg=project(tmp_path)
    path=cfg.intent/'policy.py';path.write_text('raise RuntimeError("navigation must not execute project intent")\n'+path.read_text())
    facts=cache.scan(cfg)
    assert facts['rules']['GRACE']['anchors']==['grace']
    assert cli.show(cfg,'GRACE')==0
    text=capsys.readouterr().out
    assert 'anchor grace -> app:owner app.py:2' in text
    assert 'calibrated_by=tests/test_app.py::test_allowed' in text
    assert 'unbound candidate app:missed_payment_copy app.py:10:' in text
    assert 'unbound candidate app:chart_preview app.py:13:' in text
    assert 'unbound candidate app:declared_copy ' not in text
    assert 'unbound candidate app:declared_separate ' not in text


def test_flow_relation_only_rule_and_flow_show_both_resolve_their_nodes(tmp_path,capsys):
    root,cfg=project(tmp_path,flow_only=True)
    facts=cache.scan(cfg)
    assert facts['rules']['GRACE']['homes']==[]
    assert set(facts['rules']['GRACE']['anchors'])=={'grace','case'}
    assert facts['rules']['GRACE']['flows']==['CASE_MODEL']
    assert cli.show(cfg,'GRACE')==0
    text=capsys.readouterr().out
    assert 'via flow CASE_MODEL' in text and 'app:owner app.py:2' in text
    assert 'tests/test_app.py::test_allowed[2]' in text
    assert cli.show(cfg,'CASE_MODEL')==0
    model=capsys.readouterr().out
    assert 'anchor grace' in model and 'anchor case' in model


def test_flow_constructor_wildcard_aliases_reuse_the_loader_alias_owner(tmp_path):
    _,cfg=project(tmp_path,flow_only=True,wildcard=True)
    facts=cache.scan(cfg)
    assert set(facts['rules']['GRACE']['anchors'])=={'grace','case'}
    assert facts['rules']['CASE_MODEL']['navigation_unknown']==[]


def test_imported_rule_alias_and_literal_node_alias_are_resolved_without_import(tmp_path):
    _,cfg=project(tmp_path)
    path=cfg.intent/'policy.py';path.write_text('raise RuntimeError("never import")\n'+RULE)
    (cfg.intent/'relations.py').write_text('''from .policy import GRACE as payment
from flowguard import intent as fg
SOURCE='case'
NODES=(fg.Node('source',SOURCE),fg.Node('destination','grace'))
fg.flow('IMPORTED',source='assumed: source navigation',nodes=NODES,
    relations=(fg.Relation(payment,{'days':fg.Read('source','arg.days')},fg.Read('destination')),))
''')
    facts=cache.scan(cfg)
    assert set(facts['rules']['GRACE']['anchors'])=={'grace','case'}
    assert facts['rules']['GRACE']['flows']==['IMPORTED']
    assert facts['rules']['IMPORTED']['navigation_unknown']==[]


def test_unresolved_flow_navigation_is_information_not_a_new_load_gate(tmp_path):
    _,cfg=project(tmp_path,flow_only=True)
    path=cfg.intent/'policy.py'
    path.write_text(path.read_text().replace("R('answer')","R('absent')")
                    .replace("{'days':R('scenario','arg.days')}",'read_inputs()'))
    facts=cache.scan(cfg)
    assert facts['errors']==[]
    unknown=facts['rules']['CASE_MODEL']['navigation_unknown']
    assert 'reading node: absent' in unknown
    assert 'input mapping: read_inputs()' in unknown


def test_short_source_hints_are_globally_capped_and_full_keeps_all(tmp_path,capsys):
    root,cfg=project(tmp_path)
    (root/'app.py').write_text(APP[:APP.index('# flowguard: sensor grace',1)] +
        ''.join(f'def copy_{i}(days: int)->bool:\n    return days <= 3\n'for i in range(7)))
    # No separate declaration remains in this source; keep only the actual rule.
    path=cfg.intent/'policy.py';path.write_text(RULE.split('distinct(',1)[0])
    assert cli.show(cfg,'GRACE')==0
    short=capsys.readouterr().out
    assert short.count('unbound candidate ')==5 and '2 more source candidates' in short
    assert cli.show(cfg,'GRACE',full=True)==0
    full=capsys.readouterr().out
    assert full.count('unbound candidate ')==7


def test_red_and_grey_cached_findings_remain_in_short_show(tmp_path,capsys,monkeypatch):
    _,cfg=project(tmp_path)
    data=cache.read(cfg)
    messages=[f'precise red {i}'for i in range(12)]+[f'precise grey {i}'for i in range(12)]
    data['results']={'GRACE':{'items':{'reading':{'verdict':'red','red':messages[:12],'grey':messages[12:],'info':[]}}}}
    monkeypatch.setattr(cache,'read',lambda _:data)
    assert cli.show(cfg,'GRACE')==0
    text=capsys.readouterr().out
    assert all(message in text for message in messages)


def test_unmodelled_anchor_is_an_information_pointer_not_a_failure(tmp_path,capsys):
    root=tmp_path/'project';root.mkdir();(root/'app.py').write_text(APP[:APP.index('# flowguard: sensor grace',1)])
    cfg=load_config(root)
    assert cli.show(cfg,'grace')==0
    assert 'info: not referenced by a current model: grace' in capsys.readouterr().out
    with closing(build(root,root/'outside-map.sqlite')) as graph:index=anchors.collect(graph)
    _,lines,red=cli.anchor_checks(cfg,index=index)
    assert not red and any(line.startswith('info: anchors not referenced')for line in lines)


def test_dynamic_navigation_ref_stays_unknown_without_becoming_a_load_failure(tmp_path,capsys):
    _,cfg=project(tmp_path)
    path=cfg.intent/'policy.py';path.write_text(RULE.replace('anchor=OWNER','anchor=choose_anchor()'))
    facts=cache.scan(cfg)
    assert facts['errors']==[]
    assert facts['rules']['GRACE']['anchors']==['unresolved:choose_anchor()']
    assert cli.show(cfg,'GRACE')==0
    assert 'navigation unknown: unresolved:choose_anchor()' in capsys.readouterr().out


def test_actual_state_reading_counts_as_a_model_reference(tmp_path):
    root,cfg=project(tmp_path,flow_only=True)
    path=root/'app.py'
    path.write_text(path.read_text()+'''\n# flowguard: states Work.status = new | ready
class Work:
    status = 'new'
''')
    intent=cfg.intent/'policy.py'
    intent.write_text(intent.read_text().replace("R('answer')", "R('answer','state.Work.status',equals='ready')"))
    facts=cache.scan(cfg)
    assert 'Work.status' in facts['rules']['GRACE']['anchors']
    assert 'Work.status' in facts['rules']['CASE_MODEL']['anchors']
    with closing(build(root,root/'outside-map.sqlite')) as graph:index=anchors.collect(graph)
    assert 'Work.status' not in cli._unmodelled(index,facts)


def test_missing_plugin_counts_direct_anchors_without_executing_intent(tmp_path):
    root,cfg=project(tmp_path)
    path=cfg.intent/'policy.py'
    path.write_text('raise AssertionError("diagnostics must not execute intent")\n'+path.read_text())
    facts=cache.scan(cfg)
    declared,unresolved=cache.declaration_names(cfg,facts)
    assert len([name for name in declared if name.startswith('GRACE[')])==5
    assert not any(name.endswith(':live]') for name in declared)
    declared,unresolved=cache.declaration_names(cfg,facts,deep=True)
    assert len([name for name in declared if name.startswith('GRACE[')])==7
    assert unresolved==[]
    assert 'GRACE[app.owner:cells]' in declared and 'GRACE[app.declared_copy:live]' in declared
