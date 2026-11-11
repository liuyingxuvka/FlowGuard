"""A changed boundary is a class, rather than a collection of sampled points."""
from types import SimpleNamespace
import subprocess
import sys

from flowguard.intent import cells as C
from flowguard.intent import differences as D


def before(days):
    return days <= 3


def after(days):
    return days <= 7


def only_zero(days):
    return not days


def optional_before(days):
    if days is None:
        return False
    return days <= 3


def optional_after(days):
    if days is None:
        return False
    return days <= 7


def refactored(days):
    if days <= 3:
        return True
    return False


def original_flag(days, active):
    return days <= 3 and active


def unintended_flag(days, active):
    return days <= 7 or active


def equal_three(days):
    return days == 3


def only_active(active):
    return bool(active)


def flipped(active):
    return not active


def product(a, b):
    return a * b > 3


def linear_before(a, b):
    return a + b <= 3


def linear_after(a, b):
    return a + b <= 7


def view(fn, fields):
    kinds = {name: C.kind_of(kind) for name, kind in fields.items()}
    return SimpleNamespace(kinds=kinds, reading=C.read_predicate(fn, kinds),
                           issues=(), node=C.func_ast(fn), literal_globals={})


def observation(value):
    return SimpleNamespace(status='ok', value=value, reasons=())


def compare(fn, other, fields):
    part = D.joint_partition(view(fn, fields), view(other, fields))
    old = [observation(fn(**region.inputs)) for region in part.regions]
    new = [observation(other(**region.inputs)) for region in part.regions]
    return part, D._result('grace', part, old, new)


def test_union_boundary_runs_one_representative_for_four_to_seven():
    part, result = compare(before, after, {'days': int})
    assert part.complete and part.representative_points > len(part.regions)
    assert len(part.regions) == result['total'] == 3
    assert result['changed'] == 1
    assert result['changes'] == [dict(anchor='grace', region='days=4–7',
                                      witness={'days': '4'}, before='F', after='T')]
    assert D.render(result) == 'grace：total 3 classes，changed 1 classes\ndays=4–7; function result F → T(example: days=4）'


def test_pure_refactor_has_zero_behavior_changes():
    _, result = compare(before, refactored, {'days': int})
    assert result['complete'] and result['changed'] == 0
    assert D.render(result) == 'total 2 classes，changed 0 classes'


def test_old_numeric_truth_test_is_part_of_the_joint_partition():
    part, result = compare(only_zero, after, {'days': int})
    assert part.complete and result['changed'] >= 1
    assert {(only_zero(**r.inputs), after(**r.inputs)) for r in part.regions} == {(True, True), (False, True), (False, False)}


def test_optional_absence_keeps_its_own_class_without_evaluating_a_guarded_atom():
    part, result = compare(optional_before, optional_after, {'days': int | None})
    assert part.complete and result['total'] == 4 and result['changed'] == 1
    assert result['changes'][0]['region'] == 'days=4–7'


def test_extra_boolean_edit_is_visible_and_labels_keep_its_identity():
    part, result = compare(original_flag, unintended_flag, {'days': int, 'active': bool})
    assert part.complete and result['total'] == 6
    assert result['changed'] == 4
    labels = [change['region'] for change in result['changes']]
    assert any('active=T' in label for label in labels)
    assert any('active=F' in label for label in labels)


def test_disconnected_class_is_not_presented_as_a_continuous_interval():
    part = D.joint_partition(view(equal_three, {'days': int}), view(equal_three, {'days': int}))
    assert part.complete and len(part.regions) == 2
    assert {region.label for region in part.regions} == {'days=3', 'days≠3'}


def test_finite_input_keeps_its_actual_domain_despite_an_internal_call():
    part, result = compare(only_active, flipped, {'active': bool})
    assert part.complete and result['total'] == result['changed'] == 2


def test_unknown_nonlinear_predicate_is_still_a_grey_grid():
    part, result = compare(product, product, {'a': int, 'b': int})
    assert not part.complete and result['status'] == 'grey'
    assert result['changed'] == 0 and result['reasons']
    assert len(part.regions) == part.representative_points


def test_old_new_linear_planes_share_one_partition():
    part, result = compare(linear_before, linear_after, {'a': int, 'b': int})
    assert part.complete and len(part.regions) == 3
    assert result['changed'] == 1
    represented = {(linear_before(**region.inputs), linear_after(**region.inputs)) for region in part.regions}
    oracle = {(a+b <= 3, a+b <= 7) for a in range(-5, 9) for b in range(-5, 9)}
    assert represented == oracle == {(True, True), (False, True), (False, False)}


def test_observation_unknown_does_not_turn_into_zero_verified_changes():
    part = D.joint_partition(view(before, {'days': int}), view(after, {'days': int}))
    unknown = SimpleNamespace(status='grey', value=None, reasons=('test never entered the sensor',))
    result = D._result('grace', part, [unknown] * 3, [observation(True)] * 3)
    assert result['status'] == 'grey' and not result['complete']
    assert result['changed'] == 0
    assert result['checked'] == 0 and result['unknown'] == 3
    assert 'test never entered' in D.render(result)
    assert 'comparison incomplete; proven changed classes: 0' in D.render(result)
    assert 'total 3 classes，changed 0 classes' not in D.render(result)


def test_partial_observations_keep_a_proven_change_and_unknown_classes():
    part = D.joint_partition(view(before, {'days': int}), view(after, {'days': int}))
    unknown = SimpleNamespace(status='grey', value=None, reasons=('native case unavailable',))
    result = D._result('grace', part, [observation(False), unknown, observation(True)],
                       [observation(True), observation(True), observation(True)])
    assert result['status'] == 'grey' and not result['complete']
    assert (result['total'], result['checked'], result['unknown'], result['changed']) == (3, 2, 1, 1)
    assert 'candidate classes: 3; compared: 2; comparison incomplete; proven changed classes: 1' in D.render(result)


def test_short_output_caps_changed_lines_without_losing_the_total():
    report = dict(changes=[dict(anchor='point', region=f'n={i}', before='F', after='T') for i in range(30)],
                  total=31, changed=30, complete=True, reasons=[])
    lines = D.render(report, limit=100).splitlines()
    assert len(lines) <= 10 and 'total 31 classes，changed 30 classes' in lines[0]
    assert all(len(line) <= 100 for line in lines)


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout


def repository(root, source):
    root.mkdir()
    (root/'decision.py').write_text(source)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'initial')


GRACE = '''# flowguard: sensor grace(days: day) -> allowed: bool
def allowed(days: int) -> bool:
    return days <= 3
'''


def test_runtime_keeps_the_complete_1024_boolean_domain_without_an_automatic_budget(tmp_path):
    names = [f'flag{i}' for i in range(10)]
    parameters = ', '.join(f'{name}: bool' for name in names)
    code = f'def allowed({parameters}) -> bool:\n    return ' + ' and '.join(names) + '\n'
    root = tmp_path / 'large_domain'
    repository(root, code)
    (root / 'decision.py').write_text(code.replace(' and '.join(names), 'False'))
    runtime, reading = historical(root, {name: [False, True] for name in names})
    assert reading.status == reading.comparison_status == 'ok', reading
    assert len(reading.rows) == 1024 and len(reading.changed) == 1
    assert reading.changed[0][0] == dict.fromkeys(names, True)


def test_real_old_and_current_bodies_share_the_complete_union_partition(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'decision.py').write_text(GRACE.replace('<= 3', '<= 7'))
    partition = D.joint_partition(view(before, {'days': int}), view(after, {'days': int}))
    runtime, reading = historical(root, {'days': [r.inputs['days'] for r in partition.regions]})
    report = historical_result(reading, partition)
    assert report['status'] == 'ok' and report['complete'], report
    assert report['total'] == 3 and report['changed'] == 1
    assert report['changes'][0]['region'] == 'days=4–7'


def test_unrelated_same_file_edit_does_not_create_a_runtime_behavior_change(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+'\ndef unrelated(): return 10\n')
    (root/'decision.py').write_text(GRACE+'\ndef unrelated(): return 20\n')
    runtime, reading = historical(root, {'days': [0, 4]})
    assert reading.comparison_status == 'ok' and reading.rows and not reading.changed


def test_external_helper_replays_as_the_same_object_without_guessing_or_archiving(tmp_path, monkeypatch):
    from types import ModuleType
    dependency = ModuleType('unknown_external_dependency')
    dependency.calculate = lambda active: active
    monkeypatch.setitem(sys.modules, dependency.__name__, dependency)
    root = tmp_path/'project'
    source = 'import unknown_external_dependency\ndef allowed(active: bool):\n    return unknown_external_dependency.calculate(active)\n'
    repository(root, source)
    runtime, reading = historical(root, {'active': [False, True]})
    # The external helper is the same object for the current and the baseline code, so its replay under
    # the guard compares nothing it cannot see; no old version of it is guessed or archived.
    assert reading.status == 'ok' and reading.rows and not reading.changed
    assert 'unknown_external_dependency' not in str(runtime.patches)


def test_runtime_replays_old_and_current_helper_bodies_in_the_same_real_module(tmp_path):
    root = tmp_path/'project'
    source = 'def helper(active: bool) -> bool:\n    return active\ndef allowed(active: bool) -> bool:\n    return helper(active)\n'
    repository(root, source)
    (root/'decision.py').write_text(source.replace('return active', 'return not active', 1))
    runtime, reading = historical(root, {'active': [False, True]})
    assert reading.status == reading.comparison_status == 'ok' and len(reading.changed) == 2
    assert all(old is not new for inputs, old, new in reading.changed)


def test_same_present_anchors_compare_through_the_same_executor(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('sensor grace', 'sensor other').replace('def allowed', 'def other').replace('<= 3', '<= 7'))
    report = D.compare(root, 'grace', 'other')
    assert report['status'] == 'red' and report['changed'] == 1 and report['total'] == 3, report


def test_same_name_copies_compare_actual_callables_without_any_intent_rule(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('def allowed', 'def copy').replace('<= 3', '<= 7'))
    report = D.compare(root, 'decision:allowed', 'decision:copy')
    assert report['status'] == 'red' and report['selected'] == 1, report
    assert report['changed'] == 1 and report['total'] == 3
    assert report['changes'][0]['witness'] == {'days': '4'}
    assert 'decision:allowed ↔ decision:copy' in D.render(report)


def test_differently_named_sensors_keep_separate_identity_until_an_explicit_comparison(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('sensor grace', 'sensor different').replace('def allowed', 'def copy').replace('<= 3', '<= 7'))
    index = D._source_index(root)
    assert set(index.by_name) == {'grace', 'different'}
    assert not index.issues
    runtime, reading = historical(root, {'days': [0, 4]})
    assert reading.comparison_status == 'ok' and not reading.changed
    explicit = D.compare(root, 'grace', 'different')
    assert explicit['status'] == 'red' and explicit['changed'] == 1, explicit


def test_three_current_copies_cover_every_reference_pair_without_a_second_executor(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('def allowed', 'def copy')
               +GRACE.replace('def allowed', 'def third').replace('<= 3', '<= 7'))
    index = D._source_index(root)
    reference, second, third = sorted(index.by_name['grace'], key=lambda a: a.target)
    report = D._compare_pairs(root, [(reference, second), (reference, third)])
    assert report['status'] == 'red' and report['selected'] == 2, report
    assert report['changed'] == 1 and report['items'][1]['after_target'] == 'decision:third'


def test_same_sensor_schema_conflict_is_red_without_inventing_an_input_mapping(tmp_path, monkeypatch):
    from flowguard.intent import calibration
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('def allowed', 'def copy').replace('days: day', 'days: hour'))
    def forbidden(*args, **kwargs):
        raise AssertionError('conflicting units must not execute or invent a conversion')
    monkeypatch.setattr(calibration, 'execute_many', forbidden)
    report = D.compare(root, 'decision:allowed', 'decision:copy')
    assert report['status'] == 'red' and report['selected'] == 0 and not report['complete'], report
    assert 'signature or units' in ' '.join(report['reasons'])


def test_missing_old_function_is_not_reported_as_verified_zero_changes(tmp_path):
    root = tmp_path/'project'
    repository(root, 'def ordinary(): return True\n')
    (root/'decision.py').write_text(GRACE)
    runtime, reading = historical(root, {'days': [0, 4]})
    assert reading.status == 'ok' and reading.rows
    assert reading.comparison_status == 'grey' and reading.comparison_reasons and not reading.changed


def test_moving_and_renaming_has_current_readings_but_no_invented_historical_pair(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'decision.py').unlink()
    (root/'moved.py').write_text(GRACE.replace('def allowed', 'def permitted'))
    runtime, reading = historical(root, {'days': [0, 4]}, file='moved.py', qual='permitted')
    assert reading.status == 'ok' and reading.rows
    assert reading.comparison_status == 'grey' and reading.comparison_reasons
    assert not reading.changed


def test_foreign_project_named_flowguard_cannot_replace_the_active_sdk_or_claim_green(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'flowguard').mkdir()
    (root/'flowguard/__init__.py').write_text('')
    (root/'decision.py').rename(root/'flowguard/decision.py')
    (root/'flowguard/decision.py').write_text(GRACE+GRACE.replace('sensor grace', 'sensor copy').replace('def allowed', 'def copy').replace('<= 3', '<= 7'))
    sdk = sys.modules['flowguard']
    assert 'flowguard.decision' not in sys.modules
    report = D.compare(root, 'grace', 'copy')
    assert report['status'] == 'grey' and not report['complete'] and report['reasons'], report
    assert sys.modules['flowguard'] is sdk and 'flowguard.decision' not in sys.modules


def test_actual_raised_message_change_uses_the_native_outcome_identity(tmp_path):
    root = tmp_path/'project'
    source = "def allowed(active: bool) -> bool:\n    if active:\n        raise ValueError('before')\n    return False\n"
    repository(root, source)
    (root/'decision.py').write_text(source.replace("'before'", "'after'"))
    runtime, reading = historical(root, {'active': [False, True]})
    assert reading.comparison_status == 'ok' and len(reading.changed) == 1
    _, old, new = reading.changed[0]
    assert isinstance(old, C.Raised) and isinstance(new, C.Raised)
    assert type(old.error) is type(new.error) is ValueError
    assert str(old.error) == 'before' and str(new.error) == 'after'


def test_current_context_comparison_does_not_invent_an_independent_test_session(tmp_path, monkeypatch):
    from flowguard.intent.runtime import Runtime
    root = tmp_path/'project'
    source = GRACE.replace('-> allowed: bool', '-> allowed: bool calibrated_by=tests/test_actual.py::test_saved')
    repository(root, source+source.replace('sensor grace', 'sensor copy').replace('def allowed', 'def copy'))
    def forbidden(*args, **kwargs):
        raise AssertionError('debug comparison cannot create a fresh or nested test session')
    monkeypatch.setattr(Runtime, 'replay', forbidden)
    report = D.compare(root, 'grace', 'copy')
    assert report['status'] == 'grey' and not report['complete'], report
    assert 'same actual call context' in ' '.join(report['reasons'])


def test_runtime_git_blob_reads_never_export_unrelated_data_or_archive_the_tree(tmp_path, monkeypatch):
    from flowguard.map import common
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'original-observations.bin').write_bytes(b'original data' * (1024*1024))
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'data')
    (root/'decision.py').write_text(GRACE.replace('<= 3', '<= 7'))
    calls = []
    original = common.git_run
    def record(path, *args, **kwargs):
        calls.append(args)
        assert 'archive' not in args and not any('original-observations.bin' in str(arg) for arg in args)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(common, 'git_run', record)
    runtime, reading = historical(root, {'days': [0, 4, 8]})
    assert reading.comparison_status == 'ok' and len(reading.changed) == 1
    assert calls and set(runtime._sources) == {'decision.py'}
    assert sum(len(text) for text in runtime._sources.values() if text) < 20_000


def historical(root, axes, *, file='decision.py', qual='allowed'):
    import importlib.util
    from flowguard.intent.runtime import Runtime
    name = 'r19_difference_' + str(abs(hash(str(root))))
    spec = importlib.util.spec_from_file_location(name, root / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    fn = getattr(module, qual)
    runtime = Runtime(root)
    try:
        with runtime.hook(fn, axes=axes):
            fn(**{name: list(values)[0] for name, values in axes.items()})
        assert runtime.readings
        return runtime, runtime.readings[0]
    finally:
        sys.modules.pop(name, None)  # This test-only import is not a verified application import.



def historical_result(reading, partition):
    from flowguard.intent.anchors import Observation
    before, after = [], []
    for region in partition.regions:
        row = next(value for inputs, value in reading.rows if inputs == region.inputs)
        changed = next((old for inputs, old, now in reading.changed if inputs == region.inputs), row)
        after.append(Observation('ok', row))
        before.append(Observation(reading.comparison_status, changed, tuple(reading.comparison_reasons)))
    return D._result(reading.name, partition, before, after)


def test_current_short_and_full_same_name_comments_share_one_actual_domain(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE.replace('# flowguard: sensor grace(days: day) -> allowed: bool', '# flowguard: sensor grace')
               + GRACE.replace('def allowed', 'def copy').replace('<= 3', '<= 7'))
    report = D.compare(root, 'decision:allowed', 'decision:copy')
    assert report['status'] == 'red' and report['complete'], report
    assert report['total'] == 3 and report['changed'] == 1
    assert report['changes'][0]['region'] == 'days=4–7'


def test_current_exception_message_difference_uses_real_native_outcomes(tmp_path):
    root = tmp_path/'project'
    source = '''# flowguard: sensor first(active: 1) -> allowed: bool
 def first(active: bool) -> bool:
     if active:
         raise ValueError('before')
     return False
'''.replace('\n ', '\n')
    repository(root, source + source.replace('sensor first', 'sensor second').replace('def first', 'def second').replace("'before'", "'after'"))
    report = D.compare(root, 'first', 'second')
    assert report['status'] == 'red' and report['complete'] and report['changed'] == 1, report
    assert 'before' in report['changes'][0]['before'] and 'after' in report['changes'][0]['after']
