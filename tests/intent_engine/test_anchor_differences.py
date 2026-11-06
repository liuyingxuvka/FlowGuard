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
    assert D.render(result) == 'grace: days=4–7: F → T\n共 3 类，变 1 类'


def test_pure_refactor_has_zero_behavior_changes():
    _, result = compare(before, refactored, {'days': int})
    assert result['complete'] and result['changed'] == 0
    assert D.render(result) == '共 2 类，变 0 类'


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
    assert {region.label for region in part.regions} == {'days=3', 'not (days == 3)'}


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
    assert '比较未完成，已证变化 0 类' in D.render(result)
    assert '共 3 类，变 0 类' not in D.render(result)


def test_partial_observations_keep_a_proven_change_and_unknown_classes():
    part = D.joint_partition(view(before, {'days': int}), view(after, {'days': int}))
    unknown = SimpleNamespace(status='grey', value=None, reasons=('native case unavailable',))
    result = D._result('grace', part, [observation(False), unknown, observation(True)],
                       [observation(True), observation(True), observation(True)])
    assert result['status'] == 'grey' and not result['complete']
    assert (result['total'], result['checked'], result['unknown'], result['changed']) == (3, 2, 1, 1)
    assert '候选 3 类，已比较 2 类；比较未完成，已证变化 1 类' in D.render(result)


def test_short_output_caps_changed_lines_without_losing_the_total():
    report = dict(changes=[dict(anchor='point', region=f'n={i}', before='F', after='T') for i in range(30)],
                  total=31, changed=30, complete=True, reasons=[])
    lines = D.render(report, limit=100).splitlines()
    assert len(lines) == 11 and lines[-1] == '共 31 类，变 30 类'


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


def test_large_automatic_domain_is_deferred_without_truncating_explicit_check(tmp_path):
    names = [f'flag{i}' for i in range(10)]
    parameters = ', '.join(f'{name}: bool' for name in names)
    comment = ', '.join(f'{name}: 1' for name in names)
    code = (f'# flowguard: sensor many({comment}) -> allowed: bool\n'
            f'def allowed({parameters}) -> bool:\n    return ' + ' and '.join(names) + '\n')
    root = tmp_path / 'large_domain'
    repository(root, code)
    (root / 'decision.py').write_text(code.replace(' and '.join(names), 'False'))
    automatic = D.changed(root, automatic=True)
    assert automatic['deferred'] and not automatic['complete']
    assert automatic['total'] == 0 and '1024' in ' '.join(automatic['reasons'])
    explicit = D.changed(root)
    assert explicit['complete'] and explicit['total'] == 1024 and explicit['changed'] == 1, explicit


def test_real_old_and_working_children_observe_the_union_boundary(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'decision.py').write_text(GRACE.replace('<= 3', '<= 7'))
    report = D.changed(root)
    assert report['status'] == 'ok', report
    assert report['total'] == 3 and report['changed'] == 1 and report['selected'] == 1
    assert report['changes'][0]['region'] == 'days=4–7'


def test_unrelated_same_file_function_is_not_a_changed_anchor(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+'\ndef unrelated(): return 10\n')
    (root/'decision.py').write_text(GRACE+'\ndef unrelated(): return 20\n')
    report = D.changed(root)
    assert report['status'] == 'ok' and report['selected'] == 0 and report['total'] == 0, report


def test_no_source_change_does_not_add_a_new_unknown_helper_check(tmp_path):
    root = tmp_path/'project'
    source = '''import unknown_external_dependency
# flowguard: sensor eligibility(active: 1) -> allowed: bool
def allowed(active: bool) -> bool:
    return unknown_external_dependency.calculate(active)
'''
    repository(root, source)
    report = D.changed(root)
    assert report['selected'] == 0 and report['reasons'] == [] and report['total'] == 0, report
    assert report['snapshot']['archive_bytes'] == 0
    assert 'no behavior comparison attempted' in report['scope']


def test_helper_only_edit_is_selected_without_reusing_a_parent_import(tmp_path):
    root = tmp_path/'project'
    source = '''def helper(active: bool) -> bool:
    return active
# flowguard: sensor eligibility(active: 1) -> allowed: bool
def allowed(active: bool) -> bool:
    return helper(active)
'''
    repository(root, source)
    (root/'decision.py').write_text(source.replace('return active', 'return not active', 1))
    report = D.changed(root)
    assert report['selected'] == 1 and report['changed'] == 2, report


def test_same_present_anchors_compare_through_the_same_executor(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('sensor grace', 'sensor other').replace('def allowed', 'def other').replace('<= 3', '<= 7'))
    report = D.compare(root, 'grace', 'other')
    assert report['status'] == 'red' and report['changed'] == 1 and report['total'] == 3, report


def test_same_name_copies_disagree_without_any_intent_rule(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('def allowed', 'def copy').replace('<= 3', '<= 7'))
    report = D.agreements(root)
    assert report['status'] == 'red' and report['active'] and report['groups'] == 1, report
    assert report['selected'] == 1 and report['changed'] == 1 and report['total'] == 3
    assert report['changes'][0]['witness'] == {'days': '4'}
    assert 'decision:allowed ↔ decision:copy' in D.render(report)


def test_differently_named_sensors_are_not_forced_to_agree(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('sensor grace', 'sensor different').replace('def allowed', 'def copy').replace('<= 3', '<= 7'))
    report = D.agreements(root)
    assert report['status'] == 'ok' and not report['active'] and report['selected'] == 0, report
    assert report['total'] == 0 and report['changes'] == []


def test_three_copies_reuse_one_shared_index_and_cover_every_other_copy(tmp_path):
    from flowguard.intent.anchors import collect_sources
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('def allowed', 'def copy')
               +GRACE.replace('def allowed', 'def third').replace('<= 3', '<= 7'))
    index = collect_sources(root, [('decision.py', 'decision')])
    report = D.agreements(root, index=index)
    assert report['status'] == 'red' and report['groups'] == 1 and report['selected'] == 2, report
    assert report['changed'] == 1 and report['items'][1]['after_target'] == 'decision:third'


def test_same_sensor_schema_conflict_is_red_without_inventing_an_input_mapping(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE+GRACE.replace('def allowed', 'def copy').replace('days: day', 'days: hour'))
    report = D.agreements(root)
    assert report['status'] == 'red' and report['selected'] == 0 and not report['complete'], report
    assert 'conflicting roles' in ' '.join(report['reasons'])


def test_missing_old_anchor_is_not_reported_as_verified_zero_changes(tmp_path):
    root = tmp_path/'project'
    repository(root, 'def ordinary(): return True\n')
    (root/'decision.py').write_text(GRACE)
    report = D.changed(root)
    assert report['status'] == 'grey' and not report['complete'] and report['reasons']


def test_moving_and_renaming_a_function_with_the_same_anchor_is_a_refactor(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'decision.py').unlink()
    (root/'moved.py').write_text(GRACE.replace('def allowed', 'def permitted'))
    report = D.changed(root)
    assert report['status'] == 'ok' and report['selected'] == 1 and report['changed'] == 0, report
    assert report['items'][0]['before_target'] == 'decision:allowed'
    assert report['items'][0]['after_target'] == 'moved:permitted'


def test_old_project_named_flowguard_is_not_replaced_by_the_current_tool(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'flowguard').mkdir()
    (root/'flowguard/__init__.py').write_text('')
    (root/'decision.py').rename(root/'flowguard/decision.py')
    git(root, 'add', '-A')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'package')
    (root/'flowguard/decision.py').write_text(GRACE.replace('<= 3', '<= 7'))
    assert 'flowguard.decision' not in sys.modules
    report = D.changed(root)
    assert report['status'] == 'ok' and report['changed'] == 1, report
    assert report['items'][0]['before_target'] == 'flowguard.decision:allowed'
    assert 'flowguard.decision' not in sys.modules


def test_actual_raised_message_change_uses_the_remote_outcome_identity(tmp_path):
    root = tmp_path/'project'
    source = '''# flowguard: sensor refusal(active: 1) -> allowed: bool
def allowed(active: bool) -> bool:
    if active:
        raise ValueError('before')
    return False
'''
    repository(root, source)
    (root/'decision.py').write_text(source.replace("'before'", "'after'"))
    report = D.changed(root)
    assert report['status'] == 'ok' and report['changed'] == 1, report
    assert 'before' in report['changes'][0]['before'] and 'after' in report['changes'][0]['after']


def test_automatic_entry_defers_independent_calibration_without_running_tests(tmp_path):
    root = tmp_path/'project'
    source = GRACE.replace('-> allowed: bool', '-> allowed: bool calibrated_by=tests/test_actual.py::test_saved')
    repository(root, source)
    (root/'decision.py').write_text(source.replace('<= 3', '<= 7'))
    report = D.changed(root, automatic=True)
    assert report['deferred'] and not report['automatic_eligible'], report
    assert 'deferred to check' in ' '.join(report['reasons'])


def test_old_source_snapshot_does_not_export_unrelated_data_blobs(tmp_path):
    root = tmp_path/'project'
    repository(root, GRACE)
    (root/'original-observations.bin').write_bytes(b'original data' * (1024*1024))
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'data')
    (root/'decision.py').write_text(GRACE.replace('<= 3', '<= 7'))
    report = D.changed(root)
    assert report['status'] == 'ok' and report['changed'] == 1, report
    assert report['snapshot']['omitted_noncode_paths'] == 1
    assert report['snapshot']['archive_bytes'] < 20_000
