"""One-line relation templates are ordinary Flows checked by the existing flow checks (design 4.8)."""
import importlib.util
import sys
import uuid

import pytest

from flowguard.intent import api, checks, guarded_by, precedes, transitions
from flowguard.intent.anchors import collect_sources
from flowguard.intent.flow import Capture, Event, Flow, check_flow, runtime_check, template_lines, template_text


SOURCE = '''# flowguard: states Job.status = new | saved | published
class Job:
    def __init__(self):
        self.status = 'new'

# flowguard: event SAVED
def save(job: Job):
    job.status = 'saved'

# flowguard: event PUBLISHED
def publish(job: Job):
    job.status = 'published'

# flowguard: event RESET
def reset(job: Job):
    job.status = 'new'

# flowguard: event PERMISSION_OK
def permitted(job: Job):
    return True

# flowguard: event UPDATE_RECORD
def update(job: Job):
    return job
'''


def _source(tmp_path):
    name = 'template_case_' + uuid.uuid4().hex
    path = tmp_path / (name + '.py')
    path.write_text(SOURCE)
    index = collect_sources(tmp_path, [(path.name, name)])
    assert not [issue for issue in index.issues if issue.level == 'red'], index.issues
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return index, module


@pytest.fixture(autouse=True)
def _declared():
    api.DECLARED.clear()      # declarations another test left behind are not this test's
    yield
    api.DECLARED.clear()


def _events(tmp_path, index, *cases):
    events = []
    for name, steps in cases:
        with Capture(tmp_path, index, name) as captured:
            steps()
        events.extend(captured.events)
    return events


def test_templates_are_flows_with_one_line_each_and_no_second_checker():
    model = precedes('SAVED', 'PUBLISHED')
    assert isinstance(model, Flow) and api.DECLARED == [model] and model.id == 'PRECEDES_SAVED_PUBLISHED'
    assert model.source == "assumed: precedes('SAVED', 'PUBLISHED')"
    assert {node.reference for node in model.nodes} == {'SAVED', 'PUBLISHED'}
    assert not hasattr(api, 'same') and not hasattr(api, 'single_writer')
    guarded = guarded_by('PERMISSION_OK', 'UPDATE_RECORD', source='doc rules.md "check before every update"')
    assert ('action', 'action') not in guarded.edges and guarded.source.startswith('doc ')
    states = transitions('Job.status', new={'saved'}, saved={'published'})
    assert [(t.state, t.before, t.after, t.on) for t in states.transitions] == [
        ('Job.status', 'new', 'saved', '*'), ('Job.status', 'saved', 'published', '*')]
    assert states.nodes == ()
    scenario = checks('FEE', 'FEE_CASE', days='arg.days')
    relation = scenario.relations[0]
    assert relation.rule == 'FEE' and relation.inputs['days'].field == 'arg.days' and relation.actual.node == 'actual'
    assert [node.reference for node in scenario.nodes] == ['FEE_CASE', 'FEE'] and scenario.starts == {'case'}


def test_precedes_is_red_for_a_path_that_starts_with_the_later_anchor(tmp_path):
    index, m = _source(tmp_path)
    model = precedes('SAVED', 'PUBLISHED')
    job = m.Job
    good = _events(tmp_path, index, ('saved first', lambda: (m.save(job()), m.publish(job()))))
    result = runtime_check(model, good, index)
    assert result['verdict'] == 'ok', result
    assert not [reason for reason in result['grey'] if 'unobserved edge' in reason]   # template-added edges stay quiet
    bad = _events(tmp_path, index, ('published first', lambda: (m.publish(job()), m.save(job()))))
    red = runtime_check(model, bad, index)['red']
    assert red == ['published first: runtime starts at then, outside declared entries'], red


def test_guarded_by_needs_the_guard_before_every_action(tmp_path):
    index, m = _source(tmp_path)
    model = guarded_by('PERMISSION_OK', 'UPDATE_RECORD')
    job = m.Job()
    once = _events(tmp_path, index, ('guarded', lambda: (m.permitted(job), m.update(job), m.permitted(job), m.update(job))))
    assert runtime_check(model, once, index)['verdict'] == 'ok'
    twice = _events(tmp_path, index, ('second update unguarded', lambda: (m.permitted(job), m.update(job), m.update(job))))
    assert runtime_check(model, twice, index)['red'] == [
        'second update unguarded: runtime path action -> action is not allowed']


def test_transitions_reuse_the_states_comment_and_hold_at_every_anchored_call(tmp_path):
    index, m = _source(tmp_path)
    model = transitions('Job.status', new={'saved'}, saved={'published'})
    job = m.Job()
    events = _events(tmp_path, index, ('lifecycle', lambda: (m.save(job), m.publish(job))))
    result = check_flow(model, index, events)
    assert result['verdict'] == 'ok', result
    job = m.Job()
    events = _events(tmp_path, index, ('reset', lambda: (m.save(job), m.publish(job), m.reset(job))))
    red = runtime_check(model, events, index)['red']
    assert red == ["reset: Job.status actually changes 'published' -> 'new' at RESET, outside declared transitions"], red
    unseen = runtime_check(transitions('Job.status', new={'saved', 'published'}), [], index)
    assert "unobserved state transition Job.status: 'new' -> 'published' at *" in unseen['grey']
    outside = runtime_check(transitions('Job.status', new={'archived'}), [], index)
    assert "Job.status: transition 'new' -> 'archived' is outside declared states" in outside['red']


def test_model_draft_writes_template_lines_grouped_by_flow(tmp_path):
    index, m = _source(tmp_path)
    job = m.Job()
    events = _events(tmp_path, index, ('a', lambda: (m.save(job), m.publish(job))),
                     ('b', lambda: (m.permitted(job), m.update(job))))
    rows = template_lines(events)
    assert [(row['flow'], row['text']) for row in rows] == [
        ('PERMISSION_OK', 'precedes("PERMISSION_OK", "UPDATE_RECORD")'),
        ('SAVED', 'precedes("SAVED", "PUBLISHED")'),
        ('SAVED', 'transitions("Job.status", new={"saved"}, saved={"published"})')]
    assert rows[2]['kind'] == 'transitions' and rows[2]['kwargs'] == {'new': {'saved'}, 'saved': {'published'}}
    assert template_text(rows[2]['kind'], rows[2]['args'], rows[2]['kwargs']) == rows[2]['text']
    assert template_text('transitions', ('Job.status',), {'in progress': {'done'}}) == \
        'transitions("Job.status", **{"in progress": {"done"}})'
    assert template_text('checks', ('FEE', 'FEE_CASE'), {'days': 'arg.days'}) == 'checks("FEE", "FEE_CASE", days="arg.days")'
    exec(compile('\n'.join(row['text'] for row in rows), '<draft>', 'exec'),
         dict(precedes=precedes, transitions=transitions))
    assert len(api.DECLARED) == 3 and all(isinstance(item, Flow) for item in api.DECLARED)
    assert all(isinstance(event, Event) for event in events)


def test_the_static_scan_names_each_template_flow_as_the_loader_does(tmp_path):
    # check --all and the session brief read the static scan; a template must be in it with its source.
    from flowguard.intent import cache
    from flowguard.intent.config import load_config
    from flowguard.intent.loader import load
    folder = tmp_path / 'tests/intent'
    folder.mkdir(parents=True)
    (folder / 'flows.py').write_text(
        'from flowguard.intent import precedes, guarded_by, transitions, checks, rule\n'
        '@rule("FEE", decides="fee", fields={"days": int}, source="assumed: one fee", anchor="FEE_SITE")\n'
        'def FEE(days):\n    return days\n'
        'precedes("SAVED", "PUBLISHED", source="owner R1: 先保存再发布")\n'
        'guarded_by("PERMISSION_OK", "UPDATE_RECORD")\n'
        'transitions("Job.status", new={"saved"}, saved={"published"}, source="owner R2: 只能这样变")\n'
        'checks(FEE, "FEE_CASE", days="arg.days")\n', encoding='utf-8')
    cfg = load_config(tmp_path)
    model = load(cfg)
    assert not model.errors, model.errors
    summary = cache.scan(cfg)
    scanned = {identifier: rule['source'] for identifier, rule in summary['rules'].items() if rule['kind'] == 'flow'}
    assert scanned == {identifier: flow.source for identifier, flow in model.flows.items()}, scanned
    assert scanned['PRECEDES_SAVED_PUBLISHED'] == 'owner R1: 先保存再发布'
    assert summary['rules']['PRECEDES_SAVED_PUBLISHED']['anchors'] == ['SAVED', 'PUBLISHED']
    assert summary['rules']['CHECKS_FEE_FEE_CASE']['anchors'] == ['FEE_CASE', 'FEE_SITE']
    declared, _ = cache.declaration_names(cfg, summary)
    flows = {item.partition('::')[2] for item in model.declared_items() if item.endswith('[flow]')}
    assert len(flows) == 4 and flows == {item for item in declared if item.endswith('[flow]')}, declared
