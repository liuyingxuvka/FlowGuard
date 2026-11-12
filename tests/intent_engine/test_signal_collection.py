"""CLI batching keeps one signal view and a caller-selected historical base."""
import json
from pathlib import Path
import re
import subprocess
import sys

from tests.intent_engine._cli_fixture import block, last
from tests.intent_engine.test_default_runtime_signals import _project, _git, _text


SOURCE = str(Path(__file__).resolve().parents[2])


def test_signal_collector_suppresses_only_the_product_view_and_honors_explicit_base(tmp_path):
    policy = _project(tmp_path, '''
        # flowguard: sensor PERMIT
        def permit(x: int) -> bool:
            return x <= 3
    ''', '''
        from policy import permit
        def test_native():
            assert permit(0) is True
            assert permit(4) is True
    ''')
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    policy.write_text(policy.read_text().replace('x <= 3', 'x <= 4'))
    _git(tmp_path, 'add', 'policy.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'next threshold')
    policy.write_text(policy.read_text().replace('x <= 4', 'x <= 5'))
    bootstrap = '''import json,sys
sys.path.insert(0,sys.argv.pop(1))
import pytest
from flowguard.intent.plugin import collect_signals
with collect_signals() as reports:
    result=pytest.main(sys.argv[1:])
print('COLLECTED_SIGNALS='+json.dumps(reports,ensure_ascii=True))
raise SystemExit(result)
'''
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p',
                             'flowguard.intent.plugin', '--flowguard-base', base], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, _text(result)
    assert '1 passed' in result.stdout, _text(result)
    prefix, encoded = result.stdout.split('COLLECTED_SIGNALS=', 1)
    assert 'candidate' not in _text(subprocess.CompletedProcess([], 0, prefix, result.stderr)), prefix
    reports = json.loads(encoded)
    assert len(reports) == 1 and reports[0]['source_changed'] is True
    permit = next(item for item in reports[0]['items'] if item['name'] == 'PERMIT')
    # Against the explicit base (x <= 3) the recorded x=4 changed; against HEAD (x <= 4) it would not have.
    assert permit['changed'] == [[{'x': 4}, False, True]] and permit['total'] == 2, permit


def test_the_bound_rule_counterexample_is_reported_by_its_intent_items_not_an_ordinary_selection(tmp_path):
    policy = _project(tmp_path, '''
        # flowguard: sensor STANDING
        def standing(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import standing
        def test_native():
            assert standing(0) is True
    ''', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    policy.write_text(policy.read_text().replace('days <= 3', 'days <= 4'))
    _assert_rule_red_only_with_its_items(tmp_path)


def _assert_rule_red_only_with_its_items(tmp_path):
    """The rule's row days=4 is not a call any ordinary test makes. An ordinary selection does not replay the
    anchor at the rule's rows (4.5), so it claims nothing about the rule; the rule's own items report it."""
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    selected = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p',
                              'flowguard.intent.plugin', 'tests/test_case.py'], cwd=tmp_path,
                              capture_output=True, text=True, timeout=30)
    text = _text(selected)
    assert selected.returncode == 0 and '1 passed' in selected.stdout, text
    assert not re.search(r'STANDING_RULE[^\n]*(?:passed|verified|ok)', text), text
    complete = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'flowguard.intent.plugin'],
                              cwd=tmp_path, capture_output=True, text=True, timeout=60)
    text = _text(complete)
    assert complete.returncode == 1, text
    red, = [line for line in block(complete) if line.startswith('red: ')]
    assert red.startswith('red: rule STANDING_RULE: days=4 -> rule False, code True at policy.py:standing (') and red.endswith(
        ' cells disagree) (+1 more) -> change the code so policy.py:standing follows rule STANDING_RULE'), text
    assert '    STANDING_RULE source: At most three days.' in last(tmp_path).splitlines()
    assert 'FAILED tests/intent/decisions.py::STANDING_RULE' in text, text


def test_changed_import_binding_is_not_silent_when_the_unanchored_body_is_unchanged(tmp_path):
    policy = _project(tmp_path, '''
        from helper import before as decide
        def permit(x: int) -> bool:
            return decide(x)
    ''', '''
        from policy import permit
        def test_native():
            assert permit(0) is True
    ''')
    (tmp_path / 'helper.py').write_text('def before(x): return x <= 4\ndef after(x): return x <= 3\n')
    _git(tmp_path, 'add', 'helper.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'helper baseline')
    policy.write_text(policy.read_text().replace('before as decide', 'after as decide'))
    from tests.intent_engine.test_default_runtime_signals import _run
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    assert 'not compared: permit (policy.py:2) (uses unavailable binding decide) -> not a failure' in block(result), text
    assert 'total 0 classes，changed 0 classes' not in text, text


def test_changed_global_constant_selects_an_unchanged_unanchored_function(tmp_path):
    policy = _project(tmp_path, '''
        LIMIT = 3
        def permit(x: int) -> bool:
            return x <= LIMIT
    ''', '''
        from policy import permit
        def test_native():
            assert permit(0) is True
            assert permit(4) is True
    ''')
    policy.write_text(policy.read_text().replace('LIMIT = 3', 'LIMIT = 4'))
    from tests.intent_engine.test_default_runtime_signals import _run
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    assert ('changed: permit (policy.py:2): (x=4) was False, now True; 1/2 inputs differ -> if you meant it, say so'
            in block(result)), text
    assert '    no flowguard comment: compared because its code changed' in last(tmp_path).splitlines()


def test_unchanged_source_bound_rule_is_checked_by_its_intent_items(tmp_path):
    _project(tmp_path, '\n# flowguard: sensor STANDING\ndef standing(days: int) -> bool:\n    return True\n',
             '\nfrom policy import standing\ndef test_native():\n    assert standing(0) is True\n', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    _assert_rule_red_only_with_its_items(tmp_path)


def test_no_git_baseline_cannot_turn_an_ordinary_call_into_a_source_lookup_error(tmp_path):
    _project(tmp_path, '''
        # flowguard: sensor STANDING
        def standing(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import standing
        def test_native():
            assert standing(0) is True
    ''', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    (tmp_path / '.git').rename(tmp_path.with_name(tmp_path.name + '-git-baseline'))
    assert not (tmp_path / '.git').exists()
    from tests.intent_engine.test_default_runtime_signals import _run
    result = _run(tmp_path)
    assert result.returncode == 0, _text(result)
    assert 'passed' in result.stdout and 'INTERNALERROR' not in result.stdout, _text(result)
