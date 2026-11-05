"""Private S2 history foundation: preserved evidence, not CLI/native completion."""
from copy import deepcopy
import json

import pytest

from flowguard.flow import history
from flowguard.flow.checks import CONFLICT, make_finding
from flowguard.flow.project import (ConflictsUnreadable, compare_conflict, conflict_entry,
                                    read_conflicts, write_conflicts)


def observation(**changes):
    result = dict(receipt="model-check-1", finished=True, loaded=True, complete=True, errors=0,
                  scope=dict(model="repair", members=["repair"], bounds={"tool": 2},
                             starts=["initial", "saved:v1"], coverage={"anchor": ["app:Repair"],
                             "field:state": ["broken", "ready"], "actions": ["break", "repair"]}),
                  obligations=[dict(id="only_main", kind="guard", sources=["R1"],
                                    definition=history.definition_digest("need(at_main)\n"), cases=None,
                                    dependencies={"semantics.py": history.definition_digest("same dependencies\n")})],
                  replay="not_run")
    result.update(changes)
    return result


def finding(path=()):
    return make_finding("STUCK", CONFLICT, "repair", "state = broken", "the tool is stuck",
                        sources=["R1"], path=path)


def entry():
    return conflict_entry(finding(), observation=observation())


def assess(current, original=None):
    return compare_conflict(original or entry(), current)["history"]["latest"]


def codes(result):
    return {row["code"] for row in result["reasons"]}


@pytest.mark.parametrize("replay", ["gone", "reproduced", "unknown", "not_run"])
def test_a_capped_model_never_closes_even_when_the_stored_replay_is_gone(replay):
    result = assess(observation(complete=False, replay=replay))
    assert result["outcome"] == "retain"
    assert "model_exploration_incomplete" in codes(result)


@pytest.mark.parametrize("changes", [dict(finished=False), dict(loaded=False), dict(errors=1)])
def test_finished_replay_or_failed_load_is_not_complete_model_exploration(changes):
    assert "model_exploration_incomplete" in codes(assess(observation(**changes)))


def test_a_current_reproducing_condition_cannot_be_an_absence_candidate():
    result = assess(observation(replay="reproduced"))
    assert result["outcome"] == "retain"
    assert "condition_reproduced" in codes(result)


@pytest.mark.parametrize("dimension", ["members", "bounds", "starts", "anchor", "field:state", "actions"])
def test_smaller_or_different_scope_retains_the_original_evidence(dimension):
    old = entry()
    current = observation(receipt="smaller-clean-model")
    scope = current["scope"]
    if dimension == "members":
        scope[dimension] = []
    elif dimension == "bounds":
        scope[dimension]["tool"] = 1
    elif dimension == "starts":
        scope[dimension].remove("saved:v1")
    elif dimension == "anchor":
        del scope["coverage"]["anchor"]
    else:
        scope["coverage"][dimension].pop()
    original = deepcopy(old)
    compared = compare_conflict(old, current)
    assert compared["history"]["latest"]["outcome"] == "retain"
    assert compared["history"]["latest"]["reasons"]
    assert compared["history"]["baseline"] == original["history"]["baseline"]
    assert old == original


def test_unknown_scope_and_legacy_record_cannot_become_an_empty_success():
    assert codes(assess(observation(scope=None))) == {"scope_unknown"}
    legacy = conflict_entry(finding())
    compared = compare_conflict(legacy, observation())
    assert compared["history"]["baseline"]["scope"] is None
    assert compared["history"]["latest"]["outcome"] == "retain"
    assert "scope_unknown" in codes(compared["history"]["latest"])


@pytest.mark.parametrize("change", ["deleted", "source_removed", "unknown"])
def test_a_sourced_obligation_cannot_disappear_with_the_failure(change):
    current = observation()
    if change == "deleted":
        current["obligations"] = []
    elif change == "source_removed":
        current["obligations"][0]["sources"] = []
    else:
        current["obligations"] = None
    result = assess(current)
    assert result["outcome"] == "retain"
    assert any("obligation" in code for code in codes(result))


def test_missing_original_source_descriptors_are_not_an_explicit_empty_contract():
    original = conflict_entry(finding(), observation=observation(obligations=[]))
    result = assess(observation(obligations=[]), original)
    assert result["outcome"] == "retain"
    assert codes(result) == {"source_obligations_unknown"}


def test_an_added_repair_is_a_scope_extension_not_a_reason_to_require_owner_approval():
    current = observation(receipt="complete-with-new-repair")
    current["scope"]["coverage"]["actions"].append("return_to_main")
    result = assess(current)
    assert result["outcome"] == "model_absent" and result["reasons"] == []
    assert result["claim"] == "model_only"
    assert result["native"] == "not_evaluated" and result["regression"] == "not_recorded"


def test_original_model_correction_is_explained_without_claiming_a_code_fix(project):
    from flowguard.flow.checks import check_model
    from flowguard.flow.model import load_model

    project.kit()  # Existing genuine kit request bytes; no new owner words invented here.
    template = '''
from flowguard.flow import Model, need
m = Model("repair")
m.field("state", ["broken", "ready"], "broken", source="R6")
@m.action(source="R10")
def repair(s):
    need(True, "at main", source="R10")
    s["state"] = EFFECT
m.terminal("state", ["ready"], source="R6")
MODEL = m
'''
    before = project.flow("repair", template.replace("EFFECT", '"broken"'))
    old_report = check_model(load_model(before, project.root))
    failure = next(f for f in old_report.findings if f.cls == CONFLICT and f.kind == "NEVER REACHED")
    old_observation = observation()
    old_observation["scope"].update(bounds={}, starts=["initial"], coverage={
        "field:state": ["broken", "ready"], "actions": ["repair"]})
    old_observation["obligations"][0]["sources"] = ["R10"]
    old_observation["obligations"].append(dict(id="ready", kind="value", sources=["R6"],
        definition=history.definition_digest('state = ["broken", "ready"]\n'), cases=None,
        dependencies={"semantics.py":history.definition_digest("same dependencies\n")}))
    original = conflict_entry(failure, observation=old_observation)
    corrected = project.flow("repair", template.replace("EFFECT", '"ready"'))
    fixed_model = check_model(load_model(corrected, project.root))
    assert fixed_model.reach["complete"] and not any(f.id == failure.id for f in fixed_model.findings)
    current = deepcopy(old_observation)
    current.update(receipt="corrected-model", note="Existing R6/R10: corrected model effect to ready; no code changed.")
    result = assess(current, original)
    assert result["outcome"] == "model_absent"
    assert result["note"] == current["note"]
    assert result["claim"] == "model_only"


def test_source_edit_alone_invalidates_semantics_but_is_not_a_weakening_verdict():
    current = observation()
    current["obligations"][0]["definition"] = history.definition_digest("need(at_main is True)\n")
    result = assess(current)
    assert codes(result) == {"obligation_relation_unknown"}
    assert result["changes"] == [dict(code="definition_changed", subject="only_main")]
    assert "sourced_obligation_weakened" not in codes(result)


@pytest.mark.parametrize("same_definition", [False, True])
def test_finite_behavioral_weakening_is_detected_even_if_a_helper_changed(same_definition):
    original = observation()
    original["obligations"][0]["cases"] = {"at_main": True, "at_branch": False}
    old = conflict_entry(finding(), observation=original)
    current = deepcopy(original)
    current["receipt"] = "weakened-model"
    if not same_definition:
        current["obligations"][0]["definition"] = history.definition_digest("need(True)\n")
    current["obligations"][0]["cases"]["at_branch"] = True
    assert "sourced_obligation_weakened" in codes(assess(current, old))


def test_equivalent_finite_obligation_correction_needs_no_fresh_request():
    original = observation()
    original["obligations"][0]["cases"] = {"at_main": True, "at_branch": False}
    old = conflict_entry(finding(), observation=original)
    current = deepcopy(original)
    current["obligations"][0]["definition"] = history.definition_digest("need(at_main is True)\n")
    result = assess(current, old)
    assert result["outcome"] == "model_absent"
    assert result["changes"] and result["reasons"] == []


def test_rediscovery_changes_the_witness_but_preserves_baseline_and_future_references():
    old = entry()
    old["history"]["native_refs"] = ["native-pending-1"]
    old["history"]["decision_refs"] = ["immutable-decision-1"]
    original = deepcopy(old)
    fresh = conflict_entry(finding(["another_path()"]), observation=observation(receipt="new-check"), previous=old)
    assert fresh["id"] == old["id"]
    assert fresh["history"] == old["history"] and old == original
    candidate = compare_conflict(fresh, observation())
    assert candidate["history"]["latest"]["claim"] == "model_only"  # references are not proof


def test_a_forged_same_id_cannot_transfer_another_models_baseline():
    original = entry()
    forged = deepcopy(original)
    forged["model"] = "other"
    with pytest.raises(history.HistoryError, match="identity fields"):
        history.bind(forged, previous=original)


def test_history_stays_in_the_existing_deterministic_conflict_record(project):
    compared = compare_conflict(entry(), observation(complete=False, replay="gone"))
    data = dict(conflicts=[compared], unknown=["repair"])
    write_conflicts(project.root, data)
    path = project.root / ".flowguard/conflicts.json"
    first = path.read_bytes()
    restored = read_conflicts(project.root)
    assert restored["conflicts"][0] == compared
    write_conflicts(project.root, restored)
    assert path.read_bytes() == first
    assert not (project.root / ".flowguard/history.json").exists()


@pytest.mark.parametrize("corrupt", ["scope", "scope_model", "obligations", "claim", "refs", "version"])
def test_bad_nested_evidence_is_unreadable_not_silently_empty(project, corrupt):
    row = compare_conflict(entry(), observation())
    h = row["history"]
    if corrupt == "scope":
        h["baseline"]["scope"]["coverage"] = {}
    elif corrupt == "scope_model":
        h["baseline"]["scope"]["model"] = "another"
    elif corrupt == "obligations":
        h["baseline"]["obligations"][0]["cases"] = {"branch": "allowed"}
    elif corrupt == "claim":
        h["latest"]["claim"] = "code_fixed"
    elif corrupt == "refs":
        h["decision_refs"] = [False]
    else:
        h["version"] = True
    path = project.root / ".flowguard/conflicts.json"
    path.write_text(json.dumps(dict(conflicts=[row])), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ConflictsUnreadable, match="history"):
        read_conflicts(project.root)
    assert path.read_bytes() == before


def test_lf_crlf_and_input_order_do_not_change_definition_or_scope_identity():
    assert history.definition_digest("need(at_main)\n") == history.definition_digest("need(at_main)\r\n")
    current = observation()
    current["scope"]["starts"].reverse()
    current["scope"]["coverage"]["actions"].reverse()
    assert assess(current)["outcome"] == "model_absent"


def test_changed_helper_cannot_use_unchanged_guard_text_as_semantic_proof(project):
    from flowguard.flow.checks import check_model
    from flowguard.flow.model import load_model
    template = '''
from flowguard.flow import Model, need
def permitted(s):
    return HELPER
m = Model('repair')
m.field('place', ['branch', 'main'], 'branch')
m.field('state', ['broken', 'ready'], 'broken')
@m.action(source='R1')
def repair(s):
    need(permitted(s), 'repair at main', source='R1')
    s['state'] = 'ready'
m.progress('repair stays reachable', lambda s: s['state']=='broken', lambda s: s['state']=='ready', source='R1')
MODEL=m
'''
    path = project.flow('repair', template.replace('HELPER', 's["place"] == "main"'))
    before = check_model(load_model(path, project.root))
    failure = next(f for f in before.findings if f.cls == CONFLICT and f.kind == 'STUCK')
    old = observation()
    old['scope'] = dict(model='repair', members=['repair'], bounds={}, starts=['initial'], coverage={
        'field:place':['branch','main'], 'field:state':['broken','ready'], 'actions':['repair']})
    old['obligations'] = [dict(id='guard',kind='guard',sources=['R1'],
        definition=history.definition_digest('need(permitted(s), source="R1")'),cases=None)]
    original = conflict_entry(failure, observation=old)
    project.flow('repair', template.replace('HELPER', 'True'))
    after = check_model(load_model(path, project.root))
    assert before.reach['complete'] and after.reach['complete']
    assert not any(f.id == failure.id for f in after.findings)
    result = compare_conflict(original, {**old, 'receipt':'after-helper-change'})['history']['latest']
    assert result['outcome'] == 'retain'
    assert 'obligation_relation_unknown' in codes(result)


def test_semantic_dependency_change_needs_finite_relation_not_only_own_definition():
    old = entry()
    current = observation(receipt='helper-changed')
    current['obligations'][0]['dependencies']['semantics.py'] = history.definition_digest('different helper\n')
    result = assess(current, old)
    assert 'obligation_relation_unknown' in codes(result)
    assert 'sourced_obligation_weakened' not in codes(result)
    # Finite equivalent behavior proves preservation without new owner words.
    old['history']['baseline']['obligations'][0]['cases'] = {'branch':False, 'main':True}
    current['obligations'][0]['cases'] = {'branch':False, 'main':True}
    assert assess(current, old)['outcome'] == 'model_absent'


def test_real_corrected_route_keeps_old_initial_projection_when_a_reason_field_is_added(project):
    from flowguard.flow.checks import check_model
    from flowguard.flow.descriptors import input_evidence, model_descriptor
    from flowguard.flow.explore import Bounds
    from flowguard.flow.model import load_model
    from flowguard.flow.regression import prepare_model_closures
    from flowguard.flow.routes import route_checks

    source = '''"""Selected return facts are per invocation; unsupported values remain explicit."""
from flowguard.flow import Model,need
m=Model('selected native return fields')
m.field('phase',('idle','reached','returned','raised'),'idle')
m.field('selected',(False,True),False)
m.field('facts',('absent','current','unknown'),'absent')
@m.action(selected=(False,True))
def reach(s,selected):
    need(s['phase']=='idle')
    s['phase']='reached';s['selected']=selected
@m.action(value=('scalar','complex','missing','raised'))
def finish(s,value):
    need(s['phase']=='reached')
    s['phase']='raised' if value=='raised' else 'returned'
    s['facts']='absent' if not s['selected'] else 'current' if value=='scalar' else 'unknown'
@m.action()
def next_invocation(s):
    need(s['phase'] in ('returned','raised'))
    s['phase']='idle';s['selected']=False;s['facts']='absent'
m.always('unselected invocations expose no fields',lambda s:s['selected'] or s['facts']=='absent')
m.always('current fields require a completed selected invocation',lambda s:s['facts']!='current' or (s['selected'] and s['phase']=='returned'))
MODEL=m
'''
    def computed(text):
        path = project.flow('return_fields', text)
        loaded = load_model(path, project.root)
        report = check_model(loaded)
        descriptor = model_descriptor(loaded, report, history.definition_digest(text),
                                      input_evidence(project.root, loaded.reads))
        current = observation(receipt=descriptor['receipt'], complete=report.graph.complete,
                              errors=len(report.graph.errors), scope=descriptor['scope'],
                              obligations=descriptor['obligations'])
        return path, loaded, report, descriptor, current

    path, _, before, _, old = computed(source)
    _, old_graph, routes = route_checks(path, project.root, Bounds())
    failure = next(f for f in routes.findings if f.kind == 'DUPLICATE ROUTE')
    assert old_graph.complete and before.graph.complete
    original = conflict_entry(failure, observation=old)
    fixed = source.replace("m.field('facts',('absent','current','unknown'),'absent')", "m.field('facts',('absent','current','unknown'),'absent')\nm.field('reason',('absent','current','unsupported','unavailable'),'absent')")
    fixed = fixed.replace("    s['facts']='absent' if not s['selected'] else 'current' if value=='scalar' else 'unknown'", "    s['facts']='absent' if not s['selected'] else 'current' if value=='scalar' else 'unknown'\n    s['reason']='absent' if not s['selected'] else 'current' if value=='scalar' else 'unsupported' if value=='complex' else 'unavailable'")
    fixed = fixed.replace("s['selected']=False;s['facts']='absent'", "s['selected']=False;s['facts']='absent';s['reason']='absent'")
    path, loaded, after, descriptor, current = computed(fixed)
    _, new_graph, new_routes = route_checks(path, project.root, Bounds())
    assert after.graph.complete and new_graph.complete
    assert failure.id not in {f.id for f in new_routes.findings}
    result = history.assess(original, current)
    assert result['outcome'] == 'model_absent', result
    closures, limits = prepare_model_closures(project.root, loaded, after, descriptor, [original])
    assert not limits and closures[original['id']]['regression']['passed']
    assert closures[original['id']]['boundary'] == 'model-only'
    assert original['history']['baseline']['scope'] == old['scope']


@pytest.mark.parametrize('initial, saved, removed', [
    ("initial:(('phase', 'idle'), ('reason', 'absent'), ('selected', False))", 'saved:v1', False),
    ("initial:(('phase', 'returned'), ('reason', 'absent'), ('selected', False))", 'saved:v1', True),
    ("initial:(('reason', 'absent'), ('selected', False))", 'saved:v1', True),
    ("initial:(('phase', 'idle'), ('reason', 'absent'), ('selected', 0))", 'saved:v1', True),
    ("initial:(('phase', 'idle'), ('reason', 'absent'), ('selected', False))", 'saved:v2', True),
])
def test_initial_extension_preserves_exact_old_values_and_saved_starts(initial, saved, removed):
    old = observation()
    old['scope']['starts'] = ["initial:(('phase', 'idle'), ('selected', False))", 'saved:v1']
    original = conflict_entry(finding(), observation=old)
    current = deepcopy(old)
    current['scope']['starts'] = [initial, saved]
    result = assess(current, original)
    assert ('start_removed' in codes(result)) is removed
    assert result['outcome'] == ('retain' if removed else 'model_absent')


def test_plan_table_sharing_is_lossless_without_merging_history_records():
    first = entry()
    first['history']['baseline']['obligations'][0]['cases'] = {'left':True, 'right':False}
    second = deepcopy(first)
    second['id'] = 'another-conflict'
    second['sources'] = ['R2']
    second['history']['baseline']['receipt'] = 'another-real-baseline'
    second['history']['baseline']['scope']['bounds']['tool'] = 3
    second['history']['decision_refs'] = ['retained-owner-event']
    different = deepcopy(first)
    different['history']['baseline']['obligations'][0]['cases']['right'] = True
    original = [first, second, different]
    before = deepcopy(original)
    packed = history.pack_entries(original)
    wire = json.loads(packed)
    assert wire[1]['history']['baseline']['obligations'] == {'same_as':0}
    assert isinstance(wire[2]['history']['baseline']['obligations'], list)
    restored = history.unpack_entries(packed)
    assert restored == before and original == before
    assert restored[0]['history']['baseline']['obligations'] is restored[1]['history']['baseline']['obligations']
    assert restored[2]['history']['baseline']['obligations'] is not restored[0]['history']['baseline']['obligations']
    assert history.unpack_entries(json.dumps(original)) == original


@pytest.mark.parametrize('reference', [True, -1, 1, 2, 99, '0'])
def test_missing_or_invalid_plan_table_reference_never_becomes_empty_evidence(reference):
    first, second = entry(), entry()
    second['history']['baseline']['obligations'] = {'same_as':reference}
    with pytest.raises(history.HistoryError, match='reference'):
        history.unpack_entries(json.dumps([first, second]))


def test_a_plan_table_reference_needs_a_real_prior_table():
    first, second = entry(), entry()
    first['history']['baseline']['obligations'] = None
    second['history']['baseline']['obligations'] = {'same_as':0}
    with pytest.raises(history.HistoryError, match='actual table'):
        history.unpack_entries(json.dumps([first, second]))


def test_compact_wire_preserves_finite_facts_and_exact_opaque_recipe():
    cases = {('same finite state ' * 8) + str(i):bool(i % 2) for i in range(300)}
    records = [entry(), entry()]
    for row in records:
        row['history']['baseline']['obligations'][0]['cases'] = cases
    original = deepcopy(records)
    packed = history.pack_entries(records)
    assert history.unpack_entries(packed) == original and records == original
    marker = json.loads(packed)[0]['history']['baseline']['obligations'][0]['cases']
    assert marker['$flowguard_cases'] == 'zlib-base64-v1'
    option = ' \n ' + json.dumps(original, ensure_ascii=False) + ' \t '
    # The wire stores the opaque recipe, not a reserialized approximation of it.
    value = {'parts':[{'options':[['native_stored', option]]}]}
    before = deepcopy(value)
    wire = history.pack_wire(value)
    assert len(json.dumps(wire)) < len(json.dumps(value))
    assert history.unpack_wire(wire) == value == before
    assert history.unpack_wire(wire)['parts'][0]['options'][0][1] == option
    tiny = {'info':{'descriptor':{'obligations':[{'cases':{'x':True}}]}}}
    assert history.pack_wire(tiny) == tiny


@pytest.mark.parametrize('payload', ['not-base64!', 'eA=='])
def test_corrupt_compact_facts_are_not_empty_success(payload):
    wire = {'info':{'descriptor':{'obligations':[{'cases':{'$flowguard_cases':'zlib-base64-v1', 'data':payload}}]}}}
    with pytest.raises(history.HistoryError, match='compact cases'):
        history.unpack_wire(wire)


def test_old_literal_case_names_are_not_codec_tags():
    value = {'info':{'descriptor':{'obligations':[{'cases':{'$flowguard_cases':True, 'data':False}}]}}}
    assert history.unpack_wire(value) == value


@pytest.mark.parametrize('place', ['arguments', 'function_output'])
def test_native_business_values_are_not_internal_wire_tags(place):
    import base64
    import zlib
    option = {'$flowguard_option':'zlib-base64-v1',
              'data':base64.b64encode(zlib.compress('合法业务值'.encode())).decode()}
    cases = {'$flowguard_cases':'zlib-base64-v1',
             'data':base64.b64encode(zlib.compress(json.dumps({'客户自定义':{'amount':3}}).encode())).decode()}
    if place == 'arguments':
        run = {'inputs':[{'function':'accept', 'arguments':{'payload':['native_stored',option]},
                          'external_input':None}]}
    else:
        run = {'trace':{'steps':[{'function_output':{'obligations':[{'cases':cases}]}}]}}
    value = {'info':{'native':{'checks':{'check-1':run}}}}
    before = deepcopy(value)
    assert history.unpack_wire(history.pack_wire(value)) == value == before
