"""Retained goals need explicit promises in the model of a shared-state change."""
from flowguard.flow.checks import CONFLICT, check_model
from flowguard.flow.model import load_model


PIPELINE = '''from flowguard.flow import Model, need
m = Model('upload and checkpoint')
m.field('phase', ['upload', 'checkpoint', 'complete'], 'upload')
m.field('uploaded', range(4), 0)
m.field('pending', range(3), 0)

@m.action()
def upload(s):
    need(s['phase'] == 'upload')
    s['uploaded'] = min(3, s['uploaded'] + 1)
    s['pending'] += 1
    if s['uploaded'] == 3:
        s['phase'] = 'complete'
    elif s['pending'] == 2:
        s['phase'] = 'checkpoint'

@m.action()
def checkpoint(s):
    need(s['phase'] == 'checkpoint')
    s['phase'] = 'upload'
    s['pending'] = 0
    RESET

PUBLISH
GOAL
MODEL = m
'''
GOAL = "m.reach('a complete upload remains possible', lambda s: s['phase'] == 'complete')"
PUBLISH = '''@m.action()
def publish(s):
    need(s['phase'] == 'complete')
    s['phase'] = 'upload'
    s['uploaded'] = s['pending'] = 0
'''


def pipeline(project, *, promised, preserve):
    code = PIPELINE.replace('RESET', 'pass' if preserve else "s['uploaded'] = 0")
    code = code.replace('PUBLISH', PUBLISH if preserve else '')
    path = project.flow('pipeline', code.replace('GOAL', GOAL if promised else ''))
    return check_model(load_model(path, project.root))


def test_clean_reduced_model_does_not_establish_an_omitted_goal(project):
    omitted = pipeline(project, promised=False, preserve=False)
    assert omitted.graph.complete
    assert not any(f.cls == CONFLICT for f in omitted.findings)
    assert any(f.cls == 'warning' and f.kind == 'NEVER REACHED' for f in omitted.findings)

    required = pipeline(project, promised=True, preserve=False)
    assert required.graph.complete
    assert any(f.cls == CONFLICT and f.kind == 'NEVER REACHED'
               and 'a complete upload remains possible' in f.subject for f in required.findings)


def test_checkpoint_can_preserve_the_existing_upload_goal(project):
    preserved = pipeline(project, promised=True, preserve=True)
    assert preserved.graph.complete
    assert not preserved.findings
