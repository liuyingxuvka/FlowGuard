"""The ordinary CLI uses existing receipts, selected comparisons and bounded walks."""
import json
import pytest

from checkrun import run_check


APP = '''
class Program:
    def __init__(self):
        self.n = 0
    def up(self):
        self.n = 1
    def down(self):
        self.n = 0
'''

MODEL = '''
from flowguard.flow import Model
from flowguard.flow.adapter import fields
m = Model("NAME", covers=["NAME.py:Program"])
m.field("n", (0, 1), 0)
@m.action()
def up(s):
    s["n"] = 1
@m.action()
def down(s):
    s["n"] = 0
m.bind_adapter({"system":"NAME:Program", "classes":["NAME:Program"]},
    state=lambda snapshot:fields(snapshot,names=("n",)), operations={"up":"up","down":"down"})
MODEL=m
'''


def setup(project):
    project.file('.gitignore', '.flowguard/cache/\n.flowguard/conflicts.json\n__pycache__/\n')
    for name in ('left', 'right'):
        project.file(name + '.py', APP)
        project.flow(name, MODEL.replace('NAME', name))
    project.commit()


def receipt(project, name):
    record = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    digest = record['models'][name]['core']['digest']
    return json.loads((project.root / '.flowguard/cache/flow/parts' / (digest + '.json')).read_text())


def test_ordinary_cli_walks_only_changed_module_and_compares_changed_operation(project):
    setup(project)
    first = run_check(project.root, '--json')
    assert first.code == 0, first.out + first.err
    before = receipt(project, 'right')
    right = project.root / 'right.py'
    original = right.read_text()
    left = project.root / 'left.py'
    left.write_text(left.read_text().replace('self.n = 1', 'self.n = int(True)'))
    second = run_check(project.root, '--json')
    assert second.code == 0, second.out + second.err
    changed = receipt(project, 'left')['info']['native']
    assert [row['operation'] for row in changed['operation_coverage']['witnesses']] == ['up']
    assert changed['walk']['seed'] == 0 and changed['walk']['step_budget'] == 64
    assert len(changed['walk']['inputs']) == 64
    assert receipt(project, 'right')['digest'] == before['digest']
    assert all(row['cached'] for row in second.data['parts'] if row['model'] == 'right')
    assert right.read_text() == original
    third = run_check(project.root, '--json')
    assert third.code == 0 and all(row['cached'] for row in third.data['parts'])


def test_test_selection_uses_existing_static_dependency_closure(project):
    setup(project)
    project.file('consumer.py', 'from left import Program\ndef value():\n    return Program().n\n')
    project.file('tests/test_left.py', 'from consumer import value\ndef test_value():\n    assert value() == 0\n')
    project.file('tests/test_right.py', 'from right import Program\ndef test_value():\n    raise AssertionError("unaffected test must not execute")\n')
    project.commit('test selection input')
    left = project.root / 'left.py'
    left.write_text(left.read_text() + '\n# changed\n')
    result = run_check(project.root, '--json')
    assert result.code == 0, result.out + result.err
    assert any(row['kind'] == 'code-audit' for row in result.data['parts'])
    record = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    assert record['code_audit']['tests'] == ['tests/test_left.py']


def test_known_never_does_not_repeat_setting_search_but_new_never_does(project, monkeypatch):
    from flowguard.flow.checks import _Run, check_model
    from flowguard.flow.model import load_model
    path = project.flow('unreached', '''
from flowguard.flow import Model, need
m=Model('unreached')
m.setting('limit', 0)
m.field('n', (0, 1), 0)
@m.action()
def old(s):
    need(False, 'old impossible')
@m.action()
def fresh(s):
    need(False, 'new impossible')
MODEL=m
''')
    old = next(f.to_json() for f in check_model(load_model(path, project.root)).findings if f.subject == 'action old')
    seen = []
    original = _Run.explanations
    def record(self, missing, reach_missing):
        seen.extend(self.never_subject(item) for item in missing)
        return original(self, missing, reach_missing)
    monkeypatch.setattr(_Run, 'explanations', record)
    report = check_model(load_model(path, project.root), known_never=(old,))
    assert 'action old' not in seen and 'action fresh' in seen
    old = next(f for f in report.findings if f.subject == 'action old')
    assert old.detail['explained'] is None and 'not repeated' in old.detail['explanation_status']


def test_running_resume_reuses_finished_parts_then_reuses_current_recipe(project):
    project.file('.gitignore', '.flowguard/cache/\n.flowguard/conflicts.json\n__pycache__/\n')
    project.flow('a_fast', '''
from flowguard.flow import Model
m=Model('fast')
m.field('ready',(False,True),False)
@m.action()
def toggle(s):
    s['ready']=not s['ready']
MODEL=m
''')
    project.flow('z_slow', '''
import time
from flowguard.flow import Model, need
m=Model('slow')
m.field('n',range(80),0)
@m.action()
def tick(s):
    time.sleep(.01)
    need(s['n']<79,'end')
    s['n']+=1
m.terminal('n',(79,))
MODEL=m
''')
    project.commit()
    first = run_check(project.root, '--json', '--wait', '.7', '--keep', '10')
    assert first.code == 4 and first.data['resume'], first.out + first.err
    finished = {row['digest'] for row in first.data['parts'] if row['digest']}
    assert finished
    resumed = run_check(project.root, '--json', '--wait', '20', '--keep', '10')
    assert resumed.code == 0, resumed.out + resumed.err
    assert all(row['cached'] for row in resumed.data['parts'] if row['digest'] in finished)
    again = run_check(project.root, '--json')
    assert again.code == 0 and all(row['cached'] for row in again.data['parts'])


def test_walk_drift_is_a_shorter_replayed_condition(tmp_path):
    from test_adapter import bound
    from flowguard.flow.adapter import walk
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "production"
        ''', output='model')
    result = walk(graph, steps=32, seed=12)
    assert result.status == 'drift' and len(result.inputs) == 1
    assert result.witness == {'reproduced':True, 'strategy':'first failing prefix; exact condition replay',
                              'sampled_steps':32, 'steps':1}
    assert result.seed == 12 and result.step_budget == 32


def test_known_never_keeps_real_explanation_attribution_without_identity_flapping(project):
    from flowguard.flow.checks import check_model
    from flowguard.flow.model import load_model
    path = project.flow('setting', '''
from flowguard.flow import Model, need
m=Model('setting')
m.setting('limit',0,source='R2')
S=m.settings
m.field('n',(0,1),0)
@m.action(source='R1')
def advance(s):
    need(s['n'] < S['limit'],'at limit')
    s['n']=1
MODEL=m
''')
    before = check_model(load_model(path, project.root))
    old = next(f for f in before.findings if f.subject == 'action advance')
    assert old.sources == ('R1','R2')
    after = check_model(load_model(path, project.root), known_never=(old.to_json(),))
    current = next(f for f in after.findings if f.subject == old.subject)
    assert current.id == old.id and current.sources == old.sources
    assert current.detail['explained'] is None and current.detail['explanation_status']


def test_property_read_changes_select_its_native_operation(project):
    setup(project)
    source = project.file('left.py', '''
class Program:
    def __init__(self): self.n=0
    @property
    def zero(self): return 0
    def up(self): self.n=1
    def down(self): self.n=self.zero
''')
    project.commit('property baseline')
    assert run_check(project.root, '--json', '--walk-steps', '0').code == 0
    before = receipt(project, 'right')['digest']
    source.write_text(source.read_text(encoding='utf-8').replace('return 0', 'return 1')
                      .replace('self.n=1', 'self.n=int(True)'), encoding='utf-8')
    result = run_check(project.root, '--json', '--walk-steps', '0')
    assert result.code == 1, result.out + result.err
    assert any(row['kind'] == 'MODEL DRIFT' for row in result.data['conflicts'])
    coverage = receipt(project, 'left')['info']['native']['operation_coverage']
    assert set(coverage['selected_operations']) == {'up', 'down'}
    assert receipt(project, 'right')['digest'] == before
    assert all(row['cached'] for row in result.data['parts'] if row['model'] == 'right')


@pytest.mark.parametrize('members,body,old,new', [
    ('    @property\n    def zero(self): return 0\n', 'self.n = self.zero',
     'return 0', 'return 1'),
    ('    @property\n    def zero(self): return self.n\n'
     '    @zero.setter\n    def zero(self, value): self.n = 0\n', 'self.zero = 99',
     'def zero(self, value): self.n = 0', 'def zero(self, value): self.n = 1'),
    ('    @property\n    def zero(self): return 0\n    alias = zero\n', 'self.n = self.alias',
     'return 0', 'return 1'),
    ('    @property\n    def zero(self): return 0\n', 'alias = self\n        self.n = alias.zero',
     'return 0', 'return 1'),
    ('    @property\n    def zero(self): return 0\n',
     'key = "zero"\n        self.n = getattr(self, key)', 'return 0', 'return 1'),
    ('    @property\n    def zero(self): return 0\n',
     'alias = (lambda value: value)(self)\n        self.n = alias.zero', 'return 0', 'return 1'),
])
def test_same_class_property_dependencies_keep_only_related_operations(project, members, body, old, new):
    from flowguard.flow.affected import _code
    from flowguard.flow.model import load_model
    setup(project)
    source = project.file('left.py', 'class Program:\n    def __init__(self): self.n=0\n' + members +
                          '    def up(self): self.n=1\n    def down(self):\n        ' + body + '\n')
    binding = load_model(project.root / '.flowguard/flow/left.py', project.root).model.adapter_binding
    before = _code(binding)
    source.write_text(source.read_text(encoding='utf-8').replace(old, new), encoding='utf-8')
    after = _code(binding)
    assert before is not None and after is not None
    assert before['down'] != after['down']
    assert before['up'] == after['up']


def test_deleted_import_runs_its_test_without_running_unrelated_test(project):
    setup(project)
    project.file('vanished.py', 'VALUE=0\n')
    project.file('consumer.py', 'from vanished import VALUE\ndef value(): return VALUE\n')
    project.file('tests/test_consumer.py', 'from consumer import value\ndef test_value(): assert value()==0\n')
    project.file('tests/test_unrelated.py', 'def test_unrelated(): raise AssertionError("must not run")\n')
    project.commit('deletion dependency baseline')
    (project.root / 'vanished.py').unlink()
    result = run_check(project.root, '--json')
    assert result.code != 0, result.out + result.err
    record = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    assert record['code_audit']['tests'] == ['tests/test_consumer.py']


@pytest.mark.parametrize('change', ['delete', 'staged_rename', 'unstaged_rename'])
def test_deleted_or_renamed_import_keeps_static_callers_selected(project, change):
    from flowguard.flow.affected import selected_tests
    setup(project)
    project.file('vanished.py', 'VALUE=0\n')
    project.file('consumer.py', 'from vanished import VALUE\ndef value(): return VALUE\n')
    project.file('tests/test_consumer.py', 'from consumer import value\ndef test_value(): assert value()==0\n')
    project.file('tests/test_unrelated.py', 'def test_unrelated(): raise AssertionError("must not run")\n')
    project.commit('import dependency baseline')
    if change == 'delete':
        (project.root / 'vanished.py').unlink()
    elif change == 'staged_rename':
        project.git('mv', 'vanished.py', 'renamed.py')
    else:
        (project.root / 'vanished.py').rename(project.root / 'renamed.py')
    assert selected_tests(project.root) == ['tests/test_consumer.py']


@pytest.mark.parametrize('change', ['deleted_module', 'untracked_test', 'tracked_test'])
def test_git_quoted_unicode_paths_keep_the_actual_test_scope(project, change):
    from flowguard.flow.affected import selected_tests
    setup(project)
    project.git('config', 'core.quotepath', 'true')
    if change == 'deleted_module':
        project.file('模块.py', 'VALUE=0\n')
        project.file('consumer.py', 'from 模块 import VALUE\ndef value(): return VALUE\n')
        name = 'tests/test_consumer.py'
        project.file(name, 'from consumer import value\ndef test_value(): assert value()==0\n')
        project.commit('unicode dependency baseline')
        (project.root / '模块.py').unlink()
    else:
        name = 'tests/test_模块.py'
        path = project.file(name, 'def test_value(): assert True\n')
        if change == 'tracked_test':
            project.commit('unicode test baseline')
            path.write_text('def test_value(): assert 1==1\n', encoding='utf-8')
    assert selected_tests(project.root) == [name]


@pytest.mark.parametrize('change', ['mixed', 'data_only', 'code_then_data', 'external_mixed', 'source_data_mixed'])
def test_real_data_inputs_survive_changed_operation_selection(project, change, tmp_path):
    setup(project)
    external = change == 'external_mixed'
    data = (tmp_path / 'external-value.txt') if external else project.root / 'value.txt'
    data.write_text('0', encoding='utf-8')
    reader = ('Path(' + repr(str(data)) + ')') if external else "Path(__file__).with_name('value.txt')"
    expression = reader + '.read_text()'
    if change == 'source_data_mixed':
        expression = "'self.n = int(True)' in Path(__file__).with_name('left.py').read_text()"
    project.file('helper.py', 'from pathlib import Path\ndef read_value(): return int(' + expression + ')\n')
    source = project.file('left.py', 'from helper import read_value\n' +
                          APP.replace(
                              '    def down(self):\n        self.n = 0',
                              '    def down(self):\n        self.n = read_value()'))
    project.commit('actual native data baseline')
    baseline = run_check(project.root, '--json', '--walk-steps', '0')
    assert baseline.code == 0, baseline.out + baseline.err
    unaffected = receipt(project, 'right')['digest']
    if change != 'data_only':
        source.write_text(source.read_text().replace('self.n = 1', 'self.n = int(True)'), encoding='utf-8')
    if change == 'code_then_data':
        code_only = run_check(project.root, '--json', '--walk-steps', '0')
        assert code_only.code == 0, code_only.out + code_only.err
        native = receipt(project, 'left')['info']['native']
        assert native['operation_coverage']['selected_operations'] == ['up']
        assert any(str(data) in row['files'] for row in native['footprints'])
        repeat = run_check(project.root, '--json', '--walk-steps', '0')
        assert repeat.code == 0 and all(row['cached'] for row in repeat.data['parts'])
    data.write_text('1', encoding='utf-8')
    result = run_check(project.root, '--json', '--walk-steps', '0')
    assert result.code == 1, result.out + result.err
    assert any(row['kind'] == 'MODEL DRIFT' for row in result.data['conflicts'])
    native = receipt(project, 'left')['info']['native']
    assert {row['operation'] for row in native['operation_coverage']['witnesses']} == {'up', 'down'}
    expected_input = source if change == 'source_data_mixed' else data
    assert any(str(expected_input) in row['files'] for row in native['footprints'])
    assert receipt(project, 'right')['digest'] == unaffected
    assert all(row['cached'] for row in result.data['parts'] if row['model'] == 'right')


def test_old_footprint_without_read_origin_does_not_exempt_changed_source(tmp_path):
    from flowguard.flow.affected import _inputs_beyond_code
    from flowguard.native.inputs import file_stamp, footprint_evidence
    source = tmp_path / 'app.py'
    source.write_text('VALUE=0\n', encoding='utf-8')
    old = {'reusable':True, 'files':{str(source):file_stamp(source)}, 'directories':{}}
    source.write_text('VALUE=int(False)\n', encoding='utf-8')
    covered = {str(source)}
    assert footprint_evidence(_inputs_beyond_code(old, covered)).status == 'stale'
    import_only = {**old, 'source_data_reads':{}}
    assert footprint_evidence(_inputs_beyond_code(import_only, covered)).status == 'current'
    actual_data_read = {**old, 'source_data_reads':{str(source):{'function':'down'}}}
    assert footprint_evidence(_inputs_beyond_code(actual_data_read, covered)).status == 'stale'


def test_changed_walk_recipe_records_the_new_actual_recipe_then_reuses_it(project):
    setup(project)
    assert run_check(project.root, '--json', '--walk-steps', '0', '--seed', '3').code == 0
    changed = run_check(project.root, '--json', '--walk-steps', '2', '--seed', '11')
    assert changed.code == 0, changed.out + changed.err
    assert all(not part['cached'] for part in changed.data['parts'] if part['kind'] == 'core')
    for name in ('left', 'right'):
        core = receipt(project, name)
        record = json.loads((project.root / '.flowguard/conflicts.json').read_text())
        options = dict(record['models'][name]['core']['planned']['options'])
        assert options['walk_steps'] == 2 and options['walk_seed'] == 11
        assert core['info']['native']['operation_coverage']['selected_operations'] == []
        assert 'walk' not in core['info']['native']  # Unchanged operations need no extra sampled work.
    repeat = run_check(project.root, '--json', '--walk-steps', '2', '--seed', '11')
    assert repeat.code == 0 and all(part['cached'] for part in repeat.data['parts'])


@pytest.mark.parametrize('after_code_edit', [False, True])
def test_missing_ledger_keeps_current_native_recipe_and_refreshes_only_changed_inputs(project, after_code_edit):
    from test_conflict_sessions import command
    from flowguard.flow.project import read_conflicts
    setup(project)
    source = project.file('left.py', 'from helper import read_value\n' + APP.replace(
        '    def down(self):\n        self.n = 0', '    def down(self):\n        self.n = read_value()'))
    project.file('helper.py', "from pathlib import Path\ndef read_value(): return int(Path(__file__).with_name('value.txt').read_text())\n")
    data_file = project.file('value.txt', '0')
    project.commit('missing record native input baseline')
    options = ('--json', '--walk-steps', '0', '--seed', '11')
    assert run_check(project.root, *options).code == 0
    if after_code_edit:
        source.write_text(source.read_text().replace('self.n = 1', 'self.n = int(True)'))
        changed = run_check(project.root, *options)
        assert changed.code == 0 and changed.data['models']['left']['native_operations'] == ['up']
    old = read_conflicts(project.root)
    from flowguard.flow.project import read_manifest
    for name in ('left', 'right'):
        actual = read_manifest(project.root, name, with_receipt=True)
        assert {key:actual[key] for key in ('planned', 'digest')} == old['models'][name]['core']
    ledger = project.root / '.flowguard/conflicts.json'
    ledger.unlink()
    jobs = project.root / '.flowguard/cache/flow/jobs'
    before_jobs = set(jobs.glob('*/*/plan.json'))
    current = command(project, 'status', '--json')
    assert current.returncode == 0, current.stdout + current.stderr
    assert json.loads(current.stdout)['flow_refresh']['refreshed'] == []
    assert not ledger.exists() and set(jobs.glob('*/*/plan.json')) == before_jobs
    data_file.write_text('1')
    stale = command(project, 'status', '--json')
    assert stale.returncode == 0, stale.stdout + stale.stderr
    assert json.loads(stale.stdout)['flow_refresh']['refreshed'] == ['left']
    observed = read_conflicts(project.root)
    assert set(observed['models']) == {'left'}
    assert any(entry['kind'] == 'MODEL DRIFT' for entry in observed['conflicts'])
    new_jobs = set(jobs.glob('*/*/plan.json')) - before_jobs
    assert new_jobs
    assert {part['model'] for path in new_jobs for part in json.loads(path.read_text())['parts']} == {'left'}
