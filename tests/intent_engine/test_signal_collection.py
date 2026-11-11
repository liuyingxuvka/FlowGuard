"""CLI batching keeps one signal view and a caller-selected historical base."""
import json
from pathlib import Path
import subprocess
import sys

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
    assert [(change['region'], change['witness']['x']) for change in permit['changes']] == [('x=4–5', '4')]
    assert permit['cause']['before'] == 3 and permit['cause']['after'] == 5


def test_explicit_ordinary_selection_keeps_the_bound_rule_counterexample(tmp_path):
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
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p',
                            'flowguard.intent.plugin', 'tests/test_case.py'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    text = _text(result)
    assert result.returncode == 1, text
    assert 'STANDING_RULE' in text and 'days=4' in text, text
    assert 'At most three days.' in text, text
    assert '1 passed' in result.stdout, text


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
    assert 'permit' in text and 'unanchored' in text, text
    assert 'comparison incomplete' in text and 'binding' in text, text
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
    ''')
    policy.write_text(policy.read_text().replace('LIMIT = 3', 'LIMIT = 4'))
    from tests.intent_engine.test_default_runtime_signals import _run
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    assert 'permit' in text and 'unanchored' in text and 'x=4' in text, text
    assert 'LIMIT 3' in text and 'policy.py:1' in text, text


def test_unchanged_source_still_checks_a_bound_rule_in_the_real_context(tmp_path):
    _project(tmp_path, '\n# flowguard: sensor STANDING\ndef standing(days: int) -> bool:\n    return True\n',
             '\nfrom policy import standing\ndef test_native():\n    assert standing(0) is True\n', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p',
                            'flowguard.intent.plugin', 'tests/test_case.py'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    text = _text(result)
    assert result.returncode == 1, text
    assert 'STANDING_RULE' in text and 'days=4' in text and 'At most three days.' in text, text
    assert '1 passed' in result.stdout, text


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
