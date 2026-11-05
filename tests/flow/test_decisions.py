"""Decision integrity and actual staged-byte policy, without a CLI/scheduler."""
from copy import deepcopy
import json

import pytest

from flowguard.flow import Model, need
from flowguard.flow.checks import fingerprint
from flowguard.flow.decisions import (DIRECTORY, evaluate_decision, read_decision, record_decision,
                                      rule_contradiction)
from flowguard.flow.commit_ready import commit_ready, index_inputs
from flowguard.flow.parts import ENGINE_DIGEST
from flowguard.map.common import content_digest
from flowguard.flow.explore import Bounds, explore
from flowguard.map.common import MapError
from flowguard.map.requests import retire_request, store_request


def entry(kind='RULE CONTRADICTION'):
    return dict(id=fingerprint(kind, 'rules', 'closed_rule / open_rule', ['R1', 'R2']), kind=kind, model='rules', subject='closed_rule / open_rule',
                subject_terms=['open_rule', 'closed_rule'], sources=['R1', 'R2'])


def owner_requests(project):
    project.request('R1', 'Keep open_rule enabled.\n')
    project.request('R2', 'Keep closed_rule enabled.\n')


def graph():
    model = Model('rules')
    model.field('open', (False, True), False)
    @model.action()
    def toggle(s):
        s['open'] = not s['open']
    model.always('open_rule', lambda s: s['open'], source='R1')
    model.always('closed_rule', lambda s: not s['open'], source='R2')
    return explore(model)


def proof_part(project):
    """Run/store the actual core producer; no row object authorizes a decision."""
    from flowguard.flow.parts import core_part, PartSpec, PartContext
    from flowguard.flow import jobs, diagram
    from flowguard.flow.project import cache_dir, write_conflicts, conflict_entry
    from flowguard.flow.checks import Finding
    path = project.flow('rules', "from flowguard.flow import Model\nm = Model('rules')\nm.field('open', (False,True), False)\n@m.action()\ndef toggle(s):\n    s['open'] = not s['open']\nm.always('open_rule', lambda s:s['open'], source='R1')\nm.always('closed_rule', lambda s:not s['open'], source='R2')\nMODEL=m\n")
    spec = PartSpec('core','rules', (('max_states',200000),))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(diagram, 'conflict_pictures', lambda *args: [])
        part = core_part(PartContext(project.root,spec,path,cache_dir(project.root)))
    jobs.store(project.root, part)
    write_conflicts(project.root, dict(engine=ENGINE_DIGEST, conflicts=[conflict_entry(Finding.from_json(f)) for f in part.findings if f['cls']=='conflict'],
                    models={'rules':dict(core=dict(digest=part.digest, planned=jobs.Planned(spec,'.flowguard/flow/rules.py').to_json()))}))
    return part


def test_actual_rule_predicates_establish_finite_contradiction(project):
    owner_requests(project)
    evidence = proof_part(project)
    event = record_decision(project.root, entry(), provisional='Keep the reversible current choice for now.', evidence=evidence)
    result = evaluate_decision(project.root, entry(), event['id'])
    assert result == dict(id=event['id'], outcome='provisional', open=True, code_fixed=False, commit_allowed=True,
                         label='AI temporary decision, owner to confirm')
    assert read_decision(project.root, event['id']) == event


def test_decision_is_write_once_and_does_not_modify_conflict(project):
    owner_requests(project)
    conflict = entry(); before = deepcopy(conflict)
    event = record_decision(project.root, conflict, owner='Keep open_rule enabled.', request='R1')
    assert conflict == before
    with pytest.raises(MapError, match='immutable'):
        record_decision(project.root, conflict, owner='Keep open_rule enabled.', request='R1')
    path = project.root / DIRECTORY / (event['id'] + '.json')
    path.write_text(path.read_text().replace('open_rule', 'another_rule'))
    with pytest.raises(MapError, match='decision_edited'):
        evaluate_decision(project.root, conflict, event['id'])


@pytest.mark.parametrize('kind', ['STUCK', 'NEVER REACHED', 'MODEL DRIFT', 'SECOND ROUTE'])
def test_provisional_refuses_bug_drift_or_unproved_other_kind(project, kind):
    owner_requests(project)
    with pytest.raises(MapError, match='provisional_not_allowed|decision_drift'):
        record_decision(project.root, entry(kind), provisional='Please defer', evidence=proof_part(project))


def test_offered_refused_label_alone_has_no_temporary_eligibility(project):
    owner_requests(project)
    with pytest.raises(MapError, match='evidence_missing'):
        record_decision(project.root, entry('CONTRADICTION'), provisional='Both sources were listed', evidence=dict(eligible=True))


@pytest.mark.parametrize('quote,request_id,match', [
    ('Keep missing_rule enabled.', 'R1', 'quote_not_in_request'),
    ('Keep open_rule enabled.', 'R99', 'request_unknown'),
    ('The weather is sunny.', 'R3', 'quote_subject_mismatch'),
    ('...', 'R1', 'quote_not_in_request'),
])
def test_missing_unrelated_or_empty_owner_quote_refused(project, quote, request_id, match):
    owner_requests(project); project.request('R3', 'The weather is sunny.\n')
    with pytest.raises(MapError, match=match):
        record_decision(project.root, entry(), owner=quote, request=request_id)


def test_literal_subject_does_not_accept_substring_or_topic_similarity(project):
    owner_requests(project); project.request('R3', 'Keep open_rule_backup enabled.\n')
    with pytest.raises(MapError, match='subject_mismatch'):
        record_decision(project.root, entry(), owner='Keep open_rule_backup enabled.', request='R3')


def test_validated_glossary_matches_owner_words_and_revalidates(project):
    owner_requests(project)
    project.request('R3', '保留营业规则。\n')
    store_request(project.root, '营业规则 = open_rule\n'.encode(), identifier='G1', kind='glossary')
    event = record_decision(project.root, entry(), owner='保留营业规则。', request='R3')
    assert event['authority']['glossaries'][0]['id'] == 'G1'
    assert evaluate_decision(project.root, entry(), event['id'])['commit_allowed']
    retire_request(project.root, 'G1')
    with pytest.raises(MapError, match='subject_mismatch|authority_changed'):
        evaluate_decision(project.root, entry(), event['id'])


def test_retired_or_edited_request_cannot_authorize_stored_decision(project):
    owner_requests(project)
    event = record_decision(project.root, entry(), owner='Keep open_rule enabled.', request='R1')
    retire_request(project.root, 'R1')
    with pytest.raises(MapError, match='request_retired'):
        evaluate_decision(project.root, entry(), event['id'])


def test_edited_request_cannot_authorize_decision(project):
    owner_requests(project)
    event = record_decision(project.root, entry(), owner='Keep open_rule enabled.', request='R1')
    (project.root / '.flowguard/requests/R1.md').write_text('Keep open_rule disabled.\n')
    with pytest.raises(MapError, match='owner_text_edited'):
        evaluate_decision(project.root, entry(), event['id'])


def test_ambiguous_quote_requires_request_and_nonrequest_text_is_refused(project):
    owner_requests(project); project.request('R3', 'Keep open_rule enabled.\n')
    with pytest.raises(MapError, match='ambiguous'):
        record_decision(project.root, entry(), owner='Keep open_rule enabled.')
    assert record_decision(project.root, entry(), owner='Keep open_rule enabled.', request='R3')['authority']['id'] == 'R3'
    store_request(project.root, b'open_rule = open_rule\n', identifier='G1', kind='glossary')
    with pytest.raises(MapError, match='owner_quote_kind'):
        record_decision(project.root, entry(), owner='open_rule', request='G1')


def test_identity_and_kind_changes_do_not_transfer_decisions(project):
    owner_requests(project)
    event = record_decision(project.root, entry(), owner='Keep open_rule enabled.', request='R1')
    with pytest.raises(MapError, match='conflict_changed'):
        evaluate_decision(project.root, {**entry(), 'kind': 'STUCK'}, event['id'])
    assert evaluate_decision(project.root, entry(), event['id'])['outcome'] == 'owner_decided'


@pytest.mark.parametrize('kind', ['STUCK', 'NEVER REACHED'])
def test_owner_choice_does_not_claim_bug_fixed_or_waive_fix(project, kind):
    owner_requests(project)
    event = record_decision(project.root, entry(kind), owner='Keep open_rule enabled.', request='R1')
    result = evaluate_decision(project.root, entry(kind), event['id'])
    assert result['open'] and not result['code_fixed'] and not result['commit_allowed']
    assert result['label'] == 'owner choice recorded; model/code repair still required'
    for status, repair in [('unknown', 'model/code'), ('confirmed', 'code')]:
        confirmed = {**entry(kind), 'native_confirmation': {'status': status}}
        result = evaluate_decision(project.root, confirmed, event['id'])
        assert result['open'] and not result['code_fixed'] and not result['commit_allowed']
        assert result['label'] == f'owner choice recorded; {repair} repair still required'


def test_rule_proof_rejects_capped_empty_and_satisfiable_pair():
    g = graph(); g.complete = False
    with pytest.raises(MapError, match='complete'):
        rule_contradiction(g, ['open_rule', 'closed_rule'])
    g.complete = True
    with pytest.raises(MapError, match='not_contradictory'):
        rule_contradiction(g, ['open_rule', 'closed_rule'], condition={'open': 'not a modeled value'})
    g.model.rules[1] = g.model.rules[1].__class__(**{**g.model.rules[1].__dict__, 'pred': lambda s: True})
    with pytest.raises(MapError, match='not_contradictory'):
        rule_contradiction(g, ['open_rule', 'closed_rule'])


def receipt(project, *, unknown=False):
    # This is a computation-side observation of the bytes read, independent of
    # the policy's index reader. The fixture created app.py as a normal file.
    return dict(engine=ENGINE_DIGEST, models={'rules': dict(finished=True, unknown=unknown,
                     inputs={'app.py': dict(mode='100644', sha256=content_digest(project.root / 'app.py'))})})


def staged_project(project):
    project.file('app.py', 'value = 1\n'); project.commit()


def test_exact_index_receipt_permits_and_unstaged_bytes_do_not_change_commit(project):
    staged_project(project)
    checked = receipt(project)
    assert commit_ready(project.root, ['rules'], checked, [])['ready']
    project.file('app.py', 'value = 2\n')
    assert commit_ready(project.root, ['rules'], checked, [])['ready']
    project.git('add', 'app.py')
    result = commit_ready(project.root, ['rules'], checked, [])
    assert not result['ready'] and result['reasons'][0]['code'] == 'stale_index'


def test_running_missing_and_unknown_finished_remain_distinct(project):
    staged_project(project)
    assert commit_ready(project.root, ['rules'], None, [])['reasons'][0]['code'] == 'missing_result'
    assert commit_ready(project.root, ['rules'], receipt(project), [], running=['rules'])['reasons'][0]['code'] == 'running'
    result = commit_ready(project.root, ['rules'], receipt(project, unknown=True), [])
    assert result['ready'] and result['unknown'] == ['rules']
    incomplete = receipt(project); incomplete['models']['rules']['finished'] = False
    assert not commit_ready(project.root, ['rules'], incomplete, [])['ready']


def test_unrelated_old_conflict_does_not_block_and_affected_one_does(project):
    staged_project(project)
    old = {**entry('STUCK'), 'model': 'unrelated'}
    assert commit_ready(project.root, ['rules'], receipt(project), [old])['ready']
    result = commit_ready(project.root, ['rules'], receipt(project), [entry('STUCK')])
    assert not result['ready'] and result['reasons'][0]['code'] == 'unresolved_conflict'


def test_provisional_allows_exact_affected_commit_and_stays_open(project):
    owner_requests(project); staged_project(project)
    event = record_decision(project.root, entry(), provisional='Temporary current choice', evidence=proof_part(project))
    project.git('add', '.flowguard/decisions')
    result = commit_ready(project.root, ['rules'], receipt(project), [entry()], decisions={entry()['id']: [event['id']]})
    assert result['ready'] and result['decisions'][0]['open']


def test_index_inputs_use_common_lf_crlf_identity(project):
    staged_project(project)
    checked = receipt(project)
    (project.root / 'app.py').write_bytes(b'value = 1\r\n')
    project.git('-c', 'core.autocrlf=false', 'add', 'app.py')
    assert commit_ready(project.root, ['rules'], checked, [])['ready']


def test_read_only_policy_never_calls_job_runner(project, monkeypatch):
    from flowguard.flow import jobs
    staged_project(project); checked = receipt(project)
    def forbidden(*args, **kwargs):
        raise AssertionError('policy attempted computation')
    monkeypatch.setattr(jobs, 'plan', forbidden)
    assert commit_ready(project.root, ['rules'], checked, [])['ready']


def test_changed_engine_is_not_fresh_evidence(project):
    staged_project(project); checked = receipt(project); checked['engine'] = 'old-engine'
    result = commit_ready(project.root, ['rules'], checked, [])
    assert not result['ready'] and result['reasons'][0]['code'] == 'stale_engine'


def test_index_mode_and_removed_input_are_checked(project):
    staged_project(project); checked = receipt(project)
    project.git('update-index', '--chmod=+x', 'app.py')
    assert not commit_ready(project.root, ['rules'], checked, [])['ready']
    project.git('rm', '-f', 'app.py')
    assert not commit_ready(project.root, ['rules'], checked, [])['ready']


def test_wrong_model_or_missing_rule_source_cannot_borrow_provisional_proof(project):
    owner_requests(project)
    evidence = proof_part(project)
    for conflict in ({**entry(), 'model': 'other'}, {**entry(), 'sources': ['R1']}):
        with pytest.raises(MapError, match='evidence_mismatch|evidence_missing'):
            record_decision(project.root, conflict, provisional='borrowed', evidence=evidence)


def test_provisional_revalidates_both_live_sources(project):
    owner_requests(project)
    evidence = proof_part(project)
    event = record_decision(project.root, entry(), provisional='temporary', evidence=evidence)
    retire_request(project.root, 'R2')
    with pytest.raises(MapError, match='request_retired'):
        evaluate_decision(project.root, entry(), event['id'])


def test_only_whitespace_normalization_and_elision_change_quote_spelling(project):
    owner_requests(project)
    event = record_decision(project.root, entry(), owner='Keep   open_rule ... enabled.', request='R1')
    assert evaluate_decision(project.root, entry(), event['id'])['commit_allowed']


def test_provisional_rejects_an_owner_glossary_as_requirement_source(project):
    project.request('R1', 'Keep open_rule enabled.\n')
    store_request(project.root, b'closed = closed_rule\n', identifier='R2', kind='glossary')
    with pytest.raises(MapError, match='sources must be owner requests|provisional_not_allowed'):
        record_decision(project.root, entry(), provisional='Temporary', evidence=proof_part(project))


def test_rejected_decision_does_not_authorize_affected_commit(project):
    owner_requests(project); staged_project(project)
    event = record_decision(project.root, entry(), owner='Keep open_rule enabled.', request='R1')
    retire_request(project.root, 'R1')
    result = commit_ready(project.root, ['rules'], receipt(project), [entry()], decisions={entry()['id']: [event['id']]})
    assert not result['ready']
    assert {row['code'] for row in result['reasons']} == {'invalid_decision', 'unresolved_conflict'}


def test_unstaged_decision_cannot_authorize_a_commit_that_would_lose_it(project):
    owner_requests(project); staged_project(project)
    event = record_decision(project.root, entry(), provisional='Temporary current choice', evidence=proof_part(project))
    result = commit_ready(project.root, ['rules'], receipt(project), [entry()], decisions={entry()['id']: [event['id']]})
    assert not result['ready']
    assert 'decision_not_staged' in {row['code'] for row in result['reasons']}


def test_manual_rule_rows_cannot_substitute_for_a_computation(project):
    from flowguard.flow.decisions import RuleContradiction
    owner_requests(project)
    proof_part(project)
    fake = RuleContradiction('rules', ('open_rule','closed_rule'), ('R1','R2'), (), ((True,False),(False,True)))
    with pytest.raises(MapError, match='evidence_missing'):
        record_decision(project.root, entry(), provisional='fake rows', evidence=fake)


def test_declared_compatible_state_prevents_provisional_even_when_unreachable():
    model = Model('consistent')
    model.field('n', (0,1), 0)
    @model.action()
    def keep(s):
        s['n'] = 0
    model.always('nonnegative', lambda s:s['n'] >= 0, source='R1')
    model.always('one', lambda s:s['n'] == 1, source='R2')
    with pytest.raises(MapError, match='not_contradictory'):
        rule_contradiction(explore(model), ['nonnegative','one'])


def test_immutable_authority_index_entry_must_be_a_regular_file(project):
    owner_requests(project); staged_project(project)
    event = record_decision(project.root, entry(), owner='Keep open_rule enabled.', request='R1')
    relative = (DIRECTORY / (event['id'] + '.json')).as_posix()
    project.git('add', relative)
    import subprocess
    blob = subprocess.check_output(['git','-C',str(project.root),'rev-parse', ':' + relative], text=True).strip()
    project.git('update-index','--cacheinfo', '120000,' + blob + ',' + relative)
    result = commit_ready(project.root, ['rules'], receipt(project), [entry()], decisions={entry()['id']:[event['id']]})
    assert not result['ready']
    assert 'decision_index_kind' in {row['code'] for row in result['reasons']}


def test_rule_classifier_filters_expected_ineligible_sources_but_does_not_swallow_predicate_errors(project):
    from dataclasses import replace
    from flowguard.flow.checks import check_model
    from flowguard.flow.descriptors import requested_rule_conflicts
    from flowguard.flow.model import ModelError, load_model
    owner_requests(project)
    path=project.flow('same_source',"""from flowguard.flow import Model
m=Model('same_source')
m.field('open',(False,True),False)
@m.action()
def flip(s):
    s['open']=not s['open']
m.always('open_rule',lambda s:s['open'],source='R1')
m.always('closed_rule',lambda s:not s['open'],source='R1')
MODEL=m
""")
    report=check_model(load_model(path,project.root))
    findings,proofs=requested_rule_conflicts(report)
    assert not proofs and [f.kind for f in findings].count('BROKEN')==2
    g=graph()
    def faulty(s):
        raise RuntimeError('injected contradiction judgment failure')
    g.model.rules[0]=replace(g.model.rules[0],pred=faulty)
    with pytest.raises(ModelError,match='injected contradiction judgment failure'):
        rule_contradiction(g,['open_rule','closed_rule'],required=False)


def test_non_source_inputs_keep_their_actual_binary_bytes(project):
    from flowguard.flow.descriptors import input_evidence
    staged_project(project)
    data=project.root/'payload.bin'
    data.write_bytes(b'\x00A\nB')
    project.git('add','payload.bin')
    checked=receipt(project)
    checked['models']['rules']['inputs'].update(input_evidence(project.root,['payload.bin']))
    data.write_bytes(b'\x00A\r\nB')
    project.git('add','payload.bin')
    result=commit_ready(project.root,['rules'],checked,[])
    assert not result['ready']
    assert result['reasons'][0]['code']=='stale_index'
