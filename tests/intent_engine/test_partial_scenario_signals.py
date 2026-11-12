"""Ordinary partial pytest checks actual scenario readings in an unchanged project."""
import json
import sqlite3
import textwrap

from tests.intent_engine._cli_fixture import last
from tests.intent_engine.test_default_runtime_signals import _git, _text
from tests.intent_engine.test_plugin import run


QUOTE = 'At most three is allowed.'


def project(root, *, projection=False, missing_read=False, skip_sensor=False,
            lower=False, broken_rule=False, forbid_contracts=False):
    (root / 'tests/intent').mkdir(parents=True)
    source = '''# flowguard: sensor OUTCOME(x: count) -> accepted: bool
def decide(x: int) -> bool:
    return x <= 4
'''
    parameters, field, predicate = 'x: int', "'x':int", 'x <= 3'
    fixture, decorators = '@pytest.fixture\ndef x(): return 4\n', ''
    test = 'def test_native(x: int):\n    answer=decide(x)\n    assert type(answer) is bool\n'
    actual = "Read('answer')"
    reading = "Read('case','arg.missing')" if missing_read else "Read('case','arg.x')"
    if projection:
        source = '''# flowguard: sensor OUTCOME(flag: bool) -> refusal: str | None
def decide(flag: bool) -> str | None:
    return None if flag else 'blocked'
'''
        parameters, field, predicate = 'flag: bool', "'flag':bool", 'flag'
        fixture, decorators = '', '@pytest.mark.parametrize("flag", [True,False])\n'
        test = "def test_native(flag: bool):\n    answer=decide(flag)\n    assert answer is None or type(answer) is str\n"
        actual, reading = "Read('answer',equals=None)", "Read('case','arg.flag')"
    elif skip_sensor:
        test = 'def test_native(x: int):\n    assert type(x < 0) is bool\n'
    if missing_read or skip_sensor:
        source = source.replace('x <= 4','x <= 3')
        fixture = fixture.replace('return 4','return 2')
    if broken_rule:
        predicate = '1 / 0'
    (root / 'policy.py').write_text(source,encoding='utf-8')
    (root / 'tests/test_native.py').write_text(
        'import pytest\nfrom policy import decide\n'+fixture+
        '# flowguard: event CASE('+parameters+')\n'+decorators+test,encoding='utf-8')
    rule = 'R_PROJECTED' if projection else 'R_LIMIT'
    name = 'flag' if projection else 'x'
    statement = 'A missing refusal means allowed.' if projection else QUOTE
    model = ',model='+repr(rule) if lower else ''
    (root / 'SPEC.txt').write_text(statement+'\n',encoding='utf-8')
    (root / 'tests/intent/decisions.py').write_text(textwrap.dedent(f'''\
        from flowguard.intent import rule,flow,Node,Read,Relation
        @rule({rule!r},decides='allowed',fields={{{field}}},source='doc SPEC.txt "{statement}"')
        def {rule}({name}): return {predicate}
        flow('SCENARIO',source='doc SPEC.txt "{statement}"',
             nodes=[Node('case','CASE',start=True,end={skip_sensor!r}),
                    Node('answer','OUTCOME',phase='return',caller='case',end=True{model})],
             edges=[('case','answer')],
             relations=[Relation({rule!r},{{{name!r}:{reading}}},{actual},on='answer')])
    '''),encoding='utf-8')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\ntestpaths=["tests"]\n'
        '[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n',encoding='utf-8')
    if forbid_contracts:
        (root / 'tests/conftest.py').write_text('''from pathlib import Path
from flowguard.intent.engine import Engine
def forbidden(*args, **kwargs):
    marker=Path('.flowguard/cache/forbidden-contract.txt')
    marker.parent.mkdir(parents=True,exist_ok=True)
    marker.write_text('full contract verification was attempted')
    raise AssertionError('partial scenario must not start full contract verification')
for name in ('contract_summary','_verified_witnesses','run_home','run_rules','independence'):
    setattr(Engine,name,forbidden)
''',encoding='utf-8')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n',encoding='utf-8')
    _git(root,'init','-q','-b','main')
    _git(root,'add','.')
    _git(root,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','unchanged source fixture')
    assert _git(root,'status','--porcelain') == ''
    return rule


def exercise(root, *, passed='1 passed'):
    # Only the native file is selected; no --all, no intent item, no source edit.
    result = run(root,'tests/test_native.py')
    text = _text(result)
    assert passed in result.stdout,text
    assert _git(root,'status','--porcelain') == ''
    cache = root / '.flowguard/cache/map.sqlite'
    assert cache.is_file(),text
    with sqlite3.connect(cache) as connection:
        metadata = dict(connection.execute('SELECT k,v FROM meta'))
    assert 'runtime_observations' in metadata,text
    payload = json.loads(metadata['runtime_observations'])
    report = payload['items']
    assert report['source_changed'] is False,report
    # Actual partial observations are not a receipt for the complete intent suite.
    assert 'intent_collection' not in metadata
    assert not json.loads(metadata['intent_attempt']).get('complete_collection')
    return result,text,report,payload['events'],reds(root)


def reds(root):
    """Each red line of the last run as `show --last` prints it, its detail joined to it."""
    found, current = [], None
    for line in last(root).splitlines():
        if line.startswith('    ') and current is not None:
            found[current] += ' ' + line.strip()
        else:
            current = len(found) if line.startswith('red: ') else None
            if current is not None:
                found.append(line)
    return found


def test_unchanged_partial_scenario_violation_reports_rule_and_original_quote(tmp_path):
    rule = project(tmp_path)
    result,text,report,events,red = exercise(tmp_path)
    assert any(e['anchor']=='CASE' and e['phase']=='call' and e['values']['x']==4 for e in events),events
    assert any(e['anchor']=='OUTCOME' and e['phase']=='return' and e['result'] is True for e in events),events
    assert result.returncode != 0,text
    assert rule in text and QUOTE in last(tmp_path),text            # the owner's words are the red's detail
    assert 'x=4' in text and 'False' in text and 'True' in text,text
    assert red,report
    witness = ' '.join(red).lower()
    assert 'false' in witness and 'true' in witness,report


def test_unchanged_partial_projection_keeps_real_none_and_string_without_false_red(tmp_path):
    project(tmp_path,projection=True)
    result,text,report,events,red = exercise(tmp_path,passed='2 passed')
    outcomes = [e['result'] for e in events if e['anchor']=='OUTCOME' and e['phase']=='return']
    assert len(outcomes)==2 and None in outcomes and 'blocked' in outcomes,events
    assert result.returncode == 0 and not red,text


def test_partial_scenario_missing_actual_input_reading_is_grey(tmp_path):
    project(tmp_path,missing_read=True)
    result,text,report,events,red = exercise(tmp_path)
    assert any(e['anchor']=='CASE' and e['phase']=='call' for e in events),events
    assert any(e['anchor']=='OUTCOME' and e['phase']=='return' for e in events),events
    grey = [item for item in report['items'] if item.get('status')=='grey']
    assert result.returncode == 0 and not red,text
    assert grey and 'arg.missing' in json.dumps(grey),report


def test_partial_scenario_unwalked_sensor_edge_is_grey(tmp_path):
    project(tmp_path,skip_sensor=True)
    result,text,report,events,red = exercise(tmp_path)
    assert any(e['anchor']=='CASE' and e['phase']=='call' for e in events),events
    assert not any(e['anchor']=='OUTCOME' for e in events),events
    grey = [item for item in report['items'] if item.get('status')=='grey']
    assert result.returncode == 0 and not red,text
    assert grey and 'unobserved edge' in json.dumps(grey),report


def test_actual_partial_violation_survives_an_unverified_lower_without_full_verification(tmp_path):
    rule = project(tmp_path,lower=True,forbid_contracts=True)
    result,text,report,events,red = exercise(tmp_path)
    assert any(e['anchor']=='OUTCOME' and e['phase']=='return' and e['result'] is True for e in events),events
    assert result.returncode != 0 and rule in text and QUOTE in last(tmp_path),text
    witness = ' '.join(red).lower()
    assert 'false' in witness and 'true' in witness,report
    assert not (tmp_path / '.flowguard/cache/forbidden-contract.txt').exists(),text
    assert 'partial scenario must not start full contract verification' not in text,text


def test_partial_rule_predicate_error_is_red_instead_of_an_invented_pass(tmp_path):
    rule = project(tmp_path,broken_rule=True)
    result,text,report,events,red = exercise(tmp_path)
    assert any(e['anchor']=='CASE' and e['phase']=='call' for e in events),events
    assert any(e['anchor']=='OUTCOME' and e['phase']=='return' and e['result'] is True for e in events),events
    assert result.returncode != 0 and rule in text,text
    reasons = ' '.join(red).lower()
    assert reasons and any(word in reasons for word in ('zero','division','predicate')),report
