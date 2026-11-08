"""Named anchor distinctions use existing declarations and real source observations."""
from flowguard.intent import calibration, differences
from flowguard.intent.api import Distinct


POLICY = 'The two eligibility decisions must remain separate.'
SOURCE = 'doc POLICY.md "'+POLICY+'"'


def project(tmp_path, *, second_limit=7, second_unit='day', second_output='allowed', same_name=False):
    root = tmp_path/'project'
    root.mkdir()
    (root/'POLICY.md').write_text(POLICY+'\n')
    (root/'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["POLICY.md"]\n')
    second_name = 'first' if same_name else 'second'
    (root/'decision.py').write_text(f'''# flowguard: sensor first(days: day) -> allowed: bool
def first(days: int) -> bool:
    return days <= 3
# flowguard: sensor {second_name}(days: {second_unit}) -> {second_output}: bool
def second(days: int) -> bool:
    return days <= {second_limit}
''')
    declaration = Distinct('first', 'second', POLICY, SOURCE, 1)
    declaration.file = 'tests/intent/policies.py'
    return root, declaration


def test_real_difference_supplies_a_joint_class_witness_for_distinct(tmp_path):
    root, declaration = project(tmp_path)
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'ok' and report['distinct_holds'] is True, report
    assert report['behavior_checked'] and report['complete'] and report['total'] == 3
    assert report['changed'] == 1 and report['changes'][0]['witness'] == {'days': '4'}
    assert report['why'] == POLICY and report['source'] == SOURCE and report['source_verified']


def test_distinct_broken_by_identical_actual_results_is_red(tmp_path):
    root, declaration = project(tmp_path, second_limit=3)
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'red' and report['distinct_holds'] is False, report
    assert report['behavior_checked'] and report['complete'] and report['total'] == 2
    assert report['changed'] == 0 and 'agree on every class' in ' '.join(report['reasons'])


def test_incompatible_units_do_not_trigger_an_invented_conversion_or_execution(tmp_path, monkeypatch):
    root, declaration = project(tmp_path, second_unit='hour')
    def forbidden(*args, **kwargs):
        raise AssertionError('incompatible quantities must not be executed as a common domain')
    monkeypatch.setattr(calibration, 'execute_many', forbidden)
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'grey' and not report['behavior_checked'], report
    assert 'units have no declared common input domain' in ' '.join(report['reasons'])


def test_explicit_different_roles_are_structural_separation_not_a_behavior_proof(tmp_path, monkeypatch):
    root, declaration = project(tmp_path, second_limit=3, second_output='review_required')
    def forbidden(*args, **kwargs):
        raise AssertionError('declared different output roles must not be forced into one comparison')
    monkeypatch.setattr(calibration, 'execute_many', forbidden)
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'ok' and report['distinct_holds'], report
    assert not report['behavior_checked'] and report['scope'] == 'declared-role-separation'
    assert report['source_verified'] and report['total'] == 0


def test_assumed_role_separation_remains_explicitly_provisional(tmp_path):
    root, declaration = project(tmp_path, second_output='review_required')
    declaration.source = 'assumed: the two output roles describe different decisions'
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'ok' and report['provisional'], report
    assert not report['source_verified'] and not report['behavior_checked']


def test_missing_original_source_keeps_an_observed_difference_unconfirmed(tmp_path):
    root, declaration = project(tmp_path)
    declaration.source = 'owner MissingOriginal'
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'grey' and not report['source_verified'] and not report['provisional'], report
    assert report['changed'] == 1 and report['distinct_holds'] is True
    assert 'missing' in ' '.join(report['reasons'])


def test_broken_distinct_keeps_the_missing_source_gap_in_its_report(tmp_path):
    root, declaration = project(tmp_path, second_limit=3)
    declaration.source = 'owner MissingOriginal'
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'red' and report['distinct_holds'] is False, report
    assert not report['complete'] and not report['source_verified']
    assert any('missing' in reason for reason in report['reasons'])


def test_real_targets_do_not_let_same_named_copies_escape_agreements(tmp_path):
    root, declaration = project(tmp_path, same_name=True)
    declaration.a, declaration.b = 'decision:first', 'decision:second'
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'red' and not report['behavior_checked'], report
    assert 'same sensor name cannot be distinct' in ' '.join(report['reasons'])
    agreement = differences.compare(root, 'decision:first', 'decision:second')
    assert agreement['status'] == 'red' and agreement['changed'] == 1


def test_all_same_name_source_copies_participate_in_a_distinct(tmp_path):
    root, declaration = project(tmp_path)
    with (root/'decision.py').open('a') as stream:
        stream.write('''# flowguard: sensor second(days: day) -> allowed: bool
def accidental_copy(days: int) -> bool:
    return days <= 3
''')
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'red' and report['selected'] == 2, report
    assert report['changed'] == 1
    assert any(item['after_target'] == 'decision:accidental_copy' and item['changed'] == 0 for item in report['items'])


def test_short_sensor_omitted_label_and_unit_are_not_a_proof_of_distinct_roles(tmp_path):
    root, declaration = project(tmp_path, second_limit=3)
    path = root / 'decision.py'
    path.write_text(path.read_text().replace('# flowguard: sensor first(days: day) -> allowed: bool',
                                            '# flowguard: sensor first'))
    report = differences.anchor_distinct(root, declaration)
    assert report['status'] == 'red' and report['distinct_holds'] is False, report
    assert report['behavior_checked'] and report['scope'] == 'joint-declared-input-classes'
    assert report['complete'] and report['changed'] == 0
