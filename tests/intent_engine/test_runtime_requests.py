"""Optional views borrow real tests and cannot replace their inputs or verdicts."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from tests.intent_engine.test_default_runtime_signals import _project, _text

SOURCE = str(Path(__file__).resolve().parents[2])


def _embedded(root, script, *options):
    boot = 'import sys\nsys.path.insert(0,sys.argv.pop(1))\n' + script
    return subprocess.run([sys.executable, '-c', boot, SOURCE, '-q', '-p',
                           'flowguard.intent.plugin', *options], cwd=root,
                          capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize('values,expected,reason', [({'x': 4}, False, ''), ({'label': 'wrong'}, None, 'context')])
def test_requested_points_do_not_replace_the_real_test_context(tmp_path, values, expected, reason):
    _project(tmp_path, '''
        # flowguard: sensor PERMIT(x: count; label) -> answer: bool
        def permit(x: int, label: str) -> bool:
            return label == 'ok' and x <= 3
    ''', '''
        from policy import permit
        def test_native():
            assert permit(0, 'ok') is True
    ''')
    result = _embedded(tmp_path, '''import pytest,json
from flowguard.intent.plugin import try_reading
with try_reading('policy:permit','PERMIT',VALUES) as request:
    result=pytest.main(sys.argv[1:])
print('REQUEST='+json.dumps(dict(reasons=request['reasons'],rows=[row for reading in request['readings'] for row in reading.rows])))
raise SystemExit(result)
'''.replace('VALUES', repr(values)))
    assert result.returncode == 0, _text(result)
    assert '1 passed' in result.stdout, _text(result)
    request = json.loads(result.stdout.split('REQUEST=', 1)[1])
    if reason:
        assert any(reason in message for message in request['reasons']), request
    else:
        assert not request['reasons'], request
        assert any(inputs.get('x') == 4 and actual is expected for inputs, actual in request['rows']), request


def test_explicit_bad_base_is_rejected_before_any_business_test(tmp_path):
    _project(tmp_path, 'def permit(x: int): return x <= 3\n', '''
        from pathlib import Path
        def test_native():
            Path('executed').touch()
    ''')
    result = _embedded(tmp_path, 'import pytest\nraise SystemExit(pytest.main(sys.argv[1:]))\n',
                       '--flowguard-base=definitely-not-a-commit')
    assert result.returncode != 0, _text(result)
    assert not (tmp_path / 'executed').exists()
    assert 'INTERNALERROR' not in result.stdout, _text(result)


@pytest.mark.parametrize('error', ['OSError', 'ValueError'])
def test_optional_display_failure_preserves_a_committed_real_rule_failure(tmp_path, error):
    policy = _project(tmp_path, '# flowguard: sensor STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
                      'from policy import standing\ndef test_native():\n    assert standing(0) is True\n', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days): return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='four remains refused'))
    ''')
    policy.write_text(policy.read_text().replace('days <= 3', 'days <= 4'))
    result = _embedded(tmp_path, '''import pytest
from flowguard.intent import differences
def broken(*args,**kwargs): raise ERROR('closed output')
differences.display=broken
raise SystemExit(pytest.main(sys.argv[1:]))
'''.replace('ERROR', error), 'tests/test_case.py')
    assert result.returncode == 1, _text(result)
    assert 'INTERNALERROR' not in result.stdout, _text(result)
    with sqlite3.connect(tmp_path / '.flowguard/cache/map.sqlite') as con:
        payload = json.loads(con.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])
        attempt = json.loads(con.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
    assert attempt['exit'] == 1 and payload['display_unavailable'] == error
    assert any('STANDING_RULE' in message and 'days=4' in message and 'code True' in message
               for message in payload['items']['red']), payload


def test_unknown_payload_types_do_not_invoke_their_string_or_class_hooks():
    from flowguard.intent.plugin import observation_payload
    class Meta(type):
        def __getattribute__(cls, name):
            if name in ('__module__', '__qualname__', '__dict__'):
                raise AssertionError('metadata getter must not run')
            return super().__getattribute__(name)
        def __eq__(cls, other):
            raise AssertionError('class equality must not run')
    class Hostile(metaclass=Meta):
        __module__ = object()
        def __repr__(self):
            raise AssertionError('repr must not run')
        def __str__(self):
            raise AssertionError('str must not run')
    payload = observation_payload({'context': Hostile()})
    assert payload['context']['unverified_type'].startswith('?.')
    assert payload['context']['unverified_type'].endswith('Hostile')
