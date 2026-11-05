"""Finite actual Model/explore counterexamples for composition semantics."""
import pytest

from flowguard.flow import Model, need
from flowguard.flow.compose import analyze, boundary, compose
from flowguard.flow.explore import Bounds, explore
from flowguard.flow.model import Loaded, ModelError, load_model, named_sources, vary_setting
from flowguard.flow.checks import check_model


def features(*, want_before=True):
    inventory = Model('inventory')
    tools = inventory.objects('tool', 'T1')
    inventory.field('available', (False, True), True, over=tools, source='R1')
    @inventory.action(t=tools, source='R1')
    def reserve(s, t):
        need(s['available', t])
        s['available', t] = False
    loans = Model('loans')
    available = loans.foreign(inventory, 'available')
    loans.field('borrowed', (False, True), False, over=tools, source='R2')
    @loans.action(t=tools, source='R2')
    def reserve(s, t):
        need(available(s, t) == want_before)
        s['borrowed', t] = True
    return inventory, loans


def test_synchronized_guards_read_prestate_not_an_earlier_participants_write():
    inventory, loans = features()
    model = compose('checkout', inventory, loans, kind='tool', features=True)
    graph = explore(model)
    assert graph.complete and not graph.errors and len(graph.states) == 2
    assert dict(zip(graph.keys, graph.states[1])) == {('available', 'T1'): False, ('borrowed', 'T1'): True}


def test_a_guard_cannot_be_made_true_by_an_earlier_participants_write():
    inventory, loans = features(want_before=False)
    model = compose('checkout', inventory, loans, kind='tool', features=True)
    graph = explore(model)
    assert graph.complete and not graph.errors and len(graph.states) == 1
    assert graph.refusals[-1 - graph.out[0][0]].source == 'R2'


def test_refused_nested_call_discards_the_callers_staged_effects():
    inventory, loans = features()
    loans.actions.clear()
    loans._calls = None
    @loans.action(t=loans.kinds['tool'], source='R2')
    def checkout(s, t):
        s['borrowed', t] = True
        inventory.call(s, 'reserve', t)
    model = compose('checkout', inventory, loans, kind='tool')
    graph = explore(model)
    assert graph.complete and not graph.errors
    all_states = [dict(zip(graph.keys, state)) for state in graph.states]
    assert {tuple(row.values()) for row in all_states} == {(True, False), (False, False), (False, True)}
    assert any(refusal.source == 'R1' for refusal in graph.refusals)


def test_foreign_fields_are_fixed_and_reported_when_the_owner_is_absent():
    inventory, loans = features()
    graph = explore(loans)
    assert graph.complete and not graph.errors
    assert {tuple(state) for state in graph.states} == {(False,), (True,)}
    assert boundary(loans) == [{'model': 'loans', 'owner': 'inventory', 'field': 'available',
                               'mode': 'fixed at owner start'}]
    linked = compose('linked', inventory, loans, kind='tool')
    assert boundary(linked)[0]['mode'] == 'owner model'


def pair(*, disagree=False, different_domain=False):
    result = []
    for name in ['inventory', 'inspection']:
        model = Model(name)
        tools = model.objects('tool', 'T1')
        domain = (False, True, 'unknown') if different_domain and result else (False, True)
        model.field('ready', domain, False, over=tools)
        value = False if disagree and result else True
        def make_action(value):
            def ready(s, t):
                s['ready', t] = value
            return ready
        model.action(t=tools)(make_action(value))
        result.append(model)
    return result


def test_overlapping_views_require_one_owner_and_matching_domains():
    first, second = pair()
    with pytest.raises(ModelError, match='overlapping views'):
        compose('bad', first, second, kind='tool')
    with pytest.raises(ModelError, match='overlapping views'):
        compose('bad', first, second, kind='tool', features=True)
    with pytest.raises(ModelError, match='outside this composition'):
        compose('bad', first, second, kind='tool', features=True, owners={'ready': 'missing'})
    first, second = pair(different_domain=True)
    with pytest.raises(ModelError, match='different domains'):
        compose('bad', first, second, kind='tool', features=True, owners={'ready': first})


def test_shared_feature_effects_agree_or_form_a_model_error_without_partial_commit():
    first, second = pair()
    graph = explore(compose('good', first, second, kind='tool', features=True, owners={'ready': first}))
    assert graph.complete and not graph.errors and len(graph.states) == 2
    first, second = pair(disagree=True)
    graph = explore(compose('bad', first, second, kind='tool', features=True, owners={'ready': first}))
    assert not graph.complete and graph.errors and len(graph.states) == 1
    assert 'inconsistent shared field effects' in graph.errors[0].text
    first, second = pair()
    summary = analyze(compose('good', first, second, kind='tool', features=True,
                              owners={'ready': first})).summary()
    assert summary['ownership'] == [{'field': 'ready[T1]', 'owner': 'inventory', 'views': ['inspection']}]
    assert summary['synchronizes'] == {'ready': ['inventory.ready', 'inspection.ready']}


def test_child_operation_rules_apply_to_the_whole_joint_step():
    inventory, loans = features()
    inventory.only_when('unused before reserve', 'reserve', lambda s, t: False, source='R3')
    inventory.after('available became reserved', 'reserve',
                    lambda before, after, t: before['available', t] and not after['available', t], source='R4')
    loans.actions.clear()
    loans._calls = None
    @loans.action(t=loans.kinds['tool'], source='R2')
    def checkout(s, t):
        inventory.call(s, 'reserve', t)
        s['borrowed', t] = True
    report = check_model(Loaded(compose('joint', inventory, loans, kind='tool'), ()), explain=False)
    broken = [finding for finding in report.findings if finding.kind == 'BROKEN']
    assert any('unused before reserve' in finding.subject for finding in broken)
    assert not any('available became reserved' in finding.subject for finding in broken)


def test_a_composition_of_compositions_preserves_nested_foreign_calls():
    inventory, loans = features()
    loans.actions.clear()
    @loans.action(t=loans.kinds['tool'])
    def checkout(s, t):
        inventory.call(s, 'reserve', t)
        s['borrowed', t] = True
    first = compose('lending', inventory, loans, kind='tool')
    inspection = Model('inspection')
    tools = inspection.objects('tool', 'T1')
    inspection.field('inspected', (False, True), False, over=tools)
    @inspection.action(t=tools)
    def inspect(s, t):
        s['inspected', t] = True
    audit = Model('audit')
    tools = audit.objects('tool', 'T1')
    audit.field('logged', (False, True), False, over=tools)
    @audit.action(t=tools)
    def log(s, t):
        s['logged', t] = True
    second = compose('service', inspection, audit, kind='tool')
    nested = explore(compose('all', first, second, kind='tool'))
    flat = explore(compose('all', inventory, loans, inspection, audit, kind='tool'))
    assert nested.complete and flat.complete and not nested.errors
    states = lambda graph: {tuple(sorted(zip(map(repr, graph.keys), state))) for state in graph.states}
    assert states(nested) == states(flat)


def test_constructing_a_composition_never_runs_actions_or_explores():
    model = Model('construction')
    tools = model.objects('tool', 'T1')
    model.field('ready', (False, True), False, over=tools)
    @model.action(t=tools)
    def do_not_run(s, t):
        raise AssertionError('construction executed a model action')
    result = compose('light', model, kind='tool')
    assert len(result.actions) == 1 and result.init_state() == (False,)


@pytest.mark.parametrize('overwrite',[False,True])
def test_one_participant_keeps_sequential_reads_and_its_final_write(overwrite):
    def build():
        model=Model('ordinary')
        items=model.objects('item','I1')
        model.field('n',(0,1,2),0,over=items)
        @model.action(i=items)
        def update(state,i):
            need(state['n',i]==0)
            state['n',i]=1
            state['n',i]=2 if overwrite else state['n',i]+1
        return model
    plain=explore(build(),reduce=False)
    joint=explore(compose('joint',build(),kind='item'),reduce=False)
    assert plain.complete and joint.complete and not joint.errors
    assert plain.states==joint.states==[(0,),(2,)]


def test_composition_preserves_the_shipped_parcel_increment_then_expiry(tmp_path):
    from pathlib import Path
    import re
    guide=Path(__file__).parents[2]/'flowguard/flow/HOWTO.md'
    code=next(block for block in re.findall(r'```python\n(.*?)```',guide.read_text(encoding='utf-8'),re.S)
              if 'MODEL = m' in block)
    path=tmp_path/'parcels.py';path.write_text(code,encoding='utf-8')
    plain=explore(load_model(path,tmp_path).model,reduce=False)
    joint=explore(compose('joint',load_model(path,tmp_path).model,kind='parcel'),reduce=False)
    assert plain.complete and joint.complete and not joint.errors
    states=lambda graph:{tuple(sorted(zip(map(repr,graph.keys),state))) for state in graph.states}
    assert states(plain)==states(joint)
    assert len(plain.states)==len(joint.states)>1


@pytest.mark.parametrize('disagree',[False,True])
def test_shared_effects_compare_each_participants_final_assignment(disagree):
    first,second=pair()
    for model,final in ((first,True),(second,not disagree)):
        model.actions.clear()
        def make_action(final):
            def ready(state,t):
                state['ready',t]=False
                state['ready',t]=final
            return ready
        model.action(t=model.kinds['tool'])(make_action(final))
    graph=explore(compose('joint',first,second,kind='tool',features=True,owners={'ready':first}))
    if disagree:
        assert not graph.complete and len(graph.states)==1
        assert 'inconsistent shared field effects' in graph.errors[0].text
    else:
        assert graph.complete and not graph.errors and graph.states==[(False,),(True,)]


def lifecycle(size=2):
    stock = Model('stock')
    tools = stock.objects('tool', *('T' + str(i + 1) for i in range(size)))
    stock.field('exists', (False, True), True, over=tools, source='R-remove')
    stock.terminal('exists', (False,), source='R-remove')
    @stock.action(t=tools, source='R-remove')
    def remove(s, t):
        s['exists', t] = False
    use = Model('use')
    exists = use.foreign(stock, 'exists')
    use.field('used', (False, True), False, over=tools, source='R-use')
    use.terminal('used', (True,), source='R-use')
    @use.action(t=tools, source='R-use')
    def use_tool(s, t):
        s['used', t] = True
    use.always('no use after removal',
               lambda s: all(not s['used', t] or exists(s, t) for t in tools),
               source='R-use')
    return stock, use


def test_joint_lifecycle_counterexample_retains_both_actual_request_sources():
    stock, use = lifecycle(1)
    assert not any(f.kind == 'BROKEN' for f in check_model(Loaded(use, ()), explain=False).findings)
    result = analyze(compose('joint', stock, use, kind='tool'))
    broken = [f for f in result.report.findings if f.kind == 'BROKEN']
    assert result.report.graph.complete and result.projection['verified']
    assert len(broken) == 1 and set(broken[0].sources) == {'R-remove', 'R-use'}
    assert len(broken[0].path) == 2


def test_dependency_closure_keeps_nonobject_guards_and_drops_independent_state():
    inventory, loans = features()
    inventory.field('enabled', (False, True), True)
    original = inventory.actions[0]
    def reserve(s, t):
        need(s['enabled'])
        return original.fn(s, t)
    inventory.actions.clear()
    inventory.action(t=inventory.kinds['tool'])(reserve)
    inventory._calls = None
    telemetry = Model('telemetry')
    telemetry.field('ping', (False, True), False)
    @telemetry.action()
    def ping(s):
        s['ping'] = not s['ping']
    result = analyze(compose('joint', inventory, loans, telemetry, kind='tool'), reduce=False)
    assert result.projection['verified']
    assert result.projection['fields_before'] == 4 and result.projection['fields_after'] == 3
    assert 'enabled' in result.report.graph.keys and 'ping' not in result.report.graph.keys
    assert len(result.report.graph.states) == 4


def test_symmetry_and_real_one_extra_object_probe_report_the_finite_boundary():
    result = analyze(compose('joint', *lifecycle(2), kind='tool'),
                     one_more=lambda: compose('joint', *lifecycle(3), kind='tool'))
    assert result.symmetry['used'] and result.symmetry['verified'] is True
    assert result.one_more['objects'] == {'tool': 3}
    assert result.one_more['complete'] and result.one_more['changed'] is False
    assert 'finite' in result.one_more['boundary']


def capacity(size):
    fleet = Model('fleet')
    tools = fleet.objects('tool', *('T' + str(i + 1) for i in range(size)))
    fleet.field('active', (False, True), False, over=tools, source='R-capacity')
    fleet.terminal('active', (True,), source='R-capacity')
    @fleet.action(t=tools, source='R-capacity')
    def activate(s, t):
        s['active', t] = True
    fleet.always('at most two active tools', lambda s: sum(s.values()) <= 2, source='R-capacity')
    return compose('capacity', fleet, kind='tool')


def test_one_more_probe_detects_an_actual_third_object_conflict():
    result = analyze(capacity(2), one_more=lambda: capacity(3))
    assert result.one_more['complete'] and result.one_more['changed']
    assert any(item[0] == 'BROKEN' for item in result.one_more['added'])


def test_incomplete_scope_does_not_license_projection_or_stability():
    result = analyze(capacity(2), Bounds(max_states=1), one_more=lambda: capacity(3))
    assert not result.report.graph.complete and not result.projection['verified']
    assert result.one_more['complete'] is False and result.one_more['changed'] is None


def test_unavailable_interface_and_nonowner_only_effects_are_model_errors():
    inventory, loans = features()
    loans.actions.clear()
    @loans.action(t=loans.kinds['tool'])
    def checkout(s, t):
        inventory.call(s, 'reserve', t)
    alone = explore(loans)
    assert not alone.complete and 'needs compose()' in alone.errors[0].text
    first, second = pair()
    first.actions.clear()
    graph = explore(compose('bad', first, second, kind='tool', features=True, owners={'ready': first}))
    assert not graph.complete and len(graph.states) == 1
    assert 'did not write the proposed change' in graph.errors[0].text


def test_mapping_reads_are_observed_and_raw_dict_bypass_is_not_silently_projected():
    model = Model('mapping')
    tools = model.objects('tool', 'T1')
    model.field('ready', (False, True), False, over=tools)
    @model.action(t=tools)
    def mark(s, t):
        assert dict(s) == s.copy()
        s.update({('ready', t): not s.get(('ready', t))})
    result = analyze(compose('mapping', model, kind='tool'))
    assert result.report.graph.complete and result.projection['verified']
    model.actions.clear()
    model._calls = None
    @model.action(t=tools)
    def unsupported_bypass(s, t):
        dict.__setitem__(s, ('ready', t), True)
    result = analyze(compose('mapping', model, kind='tool'))
    assert not result.report.graph.complete and not result.projection['verified']


def test_feature_interface_cannot_bypass_another_participants_guard():
    first, second = pair()
    second.actions.clear()
    @second.action(t=second.kinds['tool'], source='R-feature')
    def ready(s, t):
        need(False, source='R-feature')
    joined = compose('joined', first, second, kind='tool', features=True, owners={'ready': first})
    caller = Model('caller')
    caller.field('called', (False, True), False)
    @caller.action(t=first.kinds['tool'])
    def ask(s, t):
        first.call(s, 'ready', t)
        s['called'] = True
    graph = explore(compose('nested', joined, caller, kind='tool'))
    assert graph.complete and not graph.errors and len(graph.states) == 1
    assert any(refusal.source == 'R-feature' for refusal in graph.refusals)


def test_existing_setting_variants_reach_original_actions_and_restore_them():
    inventory, loans = features()
    inventory.setting('enabled', True, vary=(False, True), source='R-config')
    original = inventory.actions[0]
    inventory.actions.clear()
    @inventory.action(t=inventory.kinds['tool'])
    def reserve(s, t):
        need(inventory.settings['enabled'])
        original.fn(s, t)
    model = compose('joint', inventory, loans, kind='tool')
    assert len(explore(model).states) == 4
    with vary_setting(model, 'inventory/enabled', False):
        assert inventory.settings['enabled'] is False
        assert len(explore(model).states) == 2
    assert inventory.settings['enabled'] is True
    assert model.settings['inventory/enabled'] is True
    assert 'R-config' in named_sources(model)


def test_component_setting_validity_and_explicit_second_routes_are_preserved():
    model = Model('worker', valid=lambda settings: settings['enabled'])
    tools = model.objects('tool', 'T1')
    model.field('done', (False, True), False, over=tools)
    model.setting('enabled', True)
    @model.action(t=tools)
    def first(s, t):
        s['done', t] = True
    @model.action(t=tools)
    def second(s, t):
        s['done', t] = True
    model.second_route('first', 'second', source='R-both', why='two supported routes')
    joined = compose('joint', model, kind='tool')
    assert joined.valid(joined.settings)
    with vary_setting(joined, 'worker/enabled', False):
        assert not joined.valid(joined.settings)
    assert joined.second_routes[0].actions == ('worker.first', 'worker.second')
    assert joined.second_routes[0].source == 'R-both'


def test_loading_composition_preserves_real_covered_setting_origin_checks(tmp_path):
    (tmp_path / 'app.py').write_text('from dataclasses import dataclass\n'
                                   '@dataclass\nclass Config:\n    limit: int = 2\n'
                                   'def allowed(n):\n    return n < Config().limit\n')
    path = tmp_path / 'joint.py'
    path.write_text('from flowguard.flow import Model\n'
                    'from flowguard.flow.compose import compose\n'
                    'a=Model("a", covers=["app.py"])\n'
                    'tools=a.objects("tool", "T1")\n'
                    'a.field("ready", (False, True), False, over=tools)\n'
                    'a.setting("limit", 9)\n'
                    'MODEL=compose("joint", a, kind="tool")\n')
    with pytest.raises(ModelError, match='settings not read from the code'):
        load_model(path, tmp_path)
    path.write_text(path.read_text().replace('a=Model("a", covers=["app.py"])',
                   'a=Model("a", covers=["app.py"], config="app:Config")').replace(
                   'a.setting("limit", 9)', 'a.setting("limit")'))
    loaded = load_model(path, tmp_path)
    assert loaded.model.settings['a/limit'] == 2
    assert loaded.model.setting_info['a/limit'].origin == 'code'
    assert 'app.py' in loaded.reads


def test_invalid_symmetry_cannot_be_presented_as_a_complete_stability_probe():
    def asymmetric(size):
        m = Model('asymmetric')
        tools = m.objects('tool', *('T' + str(i + 1) for i in range(size)))
        m.field('out', (False, True), False, over=tools)
        @m.action(t=tools)
        def lend(s, t):
            s['out', t] = True
        @m.action(t=tools)
        def back(s, t):
            need(t != 'T1')
            s['out', t] = False
        return compose('joint', m, kind='tool')
    result = analyze(asymmetric(2), one_more=lambda: asymmetric(3))
    assert result.symmetry['verified'] is False
    assert result.summary()['complete'] is False and result.summary()['finite_scope_complete']
    assert result.one_more['complete'] is False and result.one_more['changed'] is None


def test_closure_observes_rule_reads_after_its_first_already_broken_state():
    a=Model('a')
    tools=a.objects('tool','T1','T2')
    a.field('ready',(False,True),False,over=tools)
    @a.action(t=tools)
    def flip(s,t):
        s['ready',t]=not s['ready',t]
    b=Model('b')
    b.field('flag',(False,True),False)
    @b.action()
    def flag(s):
        s['flag']=not s['flag']
    imported=a.foreign(b,'flag')
    a.always('early failure still has later dependencies',
             lambda s:False if not any(s['ready',t] for t in tools) else imported(s))
    result=analyze(compose('joint',a,b,kind='tool'))
    assert result.projection['verified'] and 'flag' in result.report.graph.keys
    assert result.projection['fields_after']==3


def test_truth_must_be_symmetric_even_if_both_searches_find_the_same_rule_broken():
    a=Model('a')
    tools=a.objects('tool','T1','T2')
    a.field('ready',(False,True),False,over=tools)
    @a.action(t=tools)
    def flip(s,t):
        s['ready',t]=not s['ready',t]
    a.always('one selected tool stays unready',lambda s:not s['ready',tools[0]])
    result=analyze(compose('joint',a,kind='tool'))
    assert result.symmetry['verified'] is False
    assert 'rule truth' in result.symmetry['text'] and not result.complete


def test_a_nonowner_views_sourced_required_value_is_not_lost_in_the_shared_field():
    first,second=pair()
    first.actions.clear()
    second.actions.clear()
    second.fields.clear()
    second.field('ready',(False,True),False,over=second.kinds['tool'],value_sources={True:'R-required'})
    model=compose('joint',first,second,kind='tool',features=True,owners={'ready':first})
    result=analyze(model)
    assert any(f.kind=='NEVER REACHED' and f.cls=='conflict' and 'R-required' in f.sources
               for f in result.report.findings)
