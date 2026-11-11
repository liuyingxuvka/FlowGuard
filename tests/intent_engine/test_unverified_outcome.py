"""Grey is "unverified", never "passed" (design 4.3).

- A grey intent item has its own pytest outcome: `U` with -q, `UNVERIFIED` with -v, `N unverified` in the
  summary; the exit status does not change, and no warning, skip or xfail is involved.
- A changed function that can no longer be compared in the sealed environment is `not compared` with its
  reason, never a failure (design 4.5, 6.4); an `[unverified]` reason in `.flowguard/ledger.toml` is
  still checked.
- `check --all`: a grey rule that quotes the owner's words fails unless `[unverified]` lists it.
"""
from pathlib import Path
import subprocess
import sys
import textwrap

from flowguard.intent import ledger
from tests.intent_engine._cli_fixture import display_text

SOURCE = str(Path(__file__).resolve().parents[2])
REASON = '这个判断现在会写审计文件，回放会被拦住；它由 test_standing 的断言守住，不再回放比较'


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _project(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n', encoding='utf-8')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n', encoding='utf-8')
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n', encoding='utf-8')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    return root


def _pytest(root, *options, env=None):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-p', 'no:cacheprovider', *options],
                            cwd=root, capture_output=True, text=True, timeout=180, env=env)
    return result, display_text(result)


def _cli(root, *arguments):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '--root', str(root), *arguments],
                            cwd=root, capture_output=True, text=True, timeout=300)
    return result, display_text(result)


ASSUMED = {
    'policy.py': '''
        # flowguard: sensor LIMIT
        def limit(days: int) -> bool:
            return days <= 3
    ''',
    'tests/test_policy.py': '''
        from policy import limit
        def test_limit():
            assert limit(2) is True
    ''',
    'tests/intent/limit.py': '''
        from flowguard.intent import rule, row
        @rule("LIMIT_RULE", decides="limit", fields={"days": int}, source="assumed: at most three days", anchor="LIMIT")
        def LIMIT_RULE(days):
            return days <= 3
        LIMIT_RULE.rows(row(days=4, expect=False, why="the fourth day stays refused"))
    ''',
}


def test_a_grey_intent_item_is_unverified_even_with_warnings_as_errors(tmp_path):
    root = _project(tmp_path / 'p', ASSUMED)
    quiet, text = _pytest(root, '-q', '-W', 'error')
    assert quiet.returncode == 0, text
    progress = text.splitlines()[0]
    assert 'U' in progress and 'F' not in progress and 's' not in progress.lower().replace('u', ''), text
    assert '1 unverified' in text and 'warning' not in text.lower() and 'skipped' not in text and 'xfail' not in text, text
    verbose, text = _pytest(root, '-v', '-W', 'error')
    assert verbose.returncode == 0, text
    line = next(line for line in text.splitlines() if 'LIMIT_RULE[rules]' in line)
    assert 'UNVERIFIED' in line and 'PASSED' not in line, line
    assert all('PASSED' in line for line in text.splitlines() if '::' in line and 'LIMIT_RULE[rules]' not in line
               and line.startswith('tests/')), text


STANDING = {
    'policy.py': '''
        # flowguard: sensor STANDING
        def standing(days: int) -> bool:
            return days <= 3
    ''',
    'tests/test_policy.py': '''
        from policy import standing
        def test_standing(tmp_path, monkeypatch):
            monkeypatch.chdir(tmp_path)
            assert standing(2) is True
    ''',
}


def test_a_new_write_is_not_compared_and_an_unverified_reason_is_still_checked(tmp_path):
    root = _project(tmp_path / 'p', STANDING)
    policy = root / 'policy.py'
    policy.write_text(policy.read_text(encoding='utf-8').replace('    return days <= 3', '    open("audit.log", "a").close()\n    return days <= 3'), encoding='utf-8')
    result, text = _pytest(root, '-q')
    # The sealed environment refuses the write before it runs: not compared, with its reason, not a failure.
    assert result.returncode == 0 and '2 passed' in text and 'red: ' not in text, text
    assert 'unverified: STANDING（policy.py:2）：uses attribute close' in text, text
    assert not (root / 'audit.log').exists()
    # A reason too short is red in the ledger's own check; a real reason is accepted.
    (root / ledger.LEDGER).parent.mkdir(exist_ok=True)
    (root / ledger.LEDGER).write_text('[unverified]\nSTANDING = "不再回放"\n', encoding='utf-8')
    short, text = _pytest(root, '-q')
    assert short.returncode == 1 and '[unverified] item "STANDING": reason has' in text, text
    (root / ledger.LEDGER).write_text('[unverified]\nSTANDING = ' + ledger._quote(REASON) + '\n', encoding='utf-8')
    listed, text = _pytest(root, '-q')
    assert listed.returncode == 0 and 'red: ' not in text, text


def test_a_grey_that_the_baseline_shares_is_not_a_lost_observation(tmp_path):
    files = dict(STANDING, **{'policy.py': textwrap.dedent(STANDING['policy.py']).replace(
        '    return days <= 3', '    open("audit.log", "a").close()\n    return days <= 3')})
    root = _project(tmp_path / 'p', files)
    policy = root / 'policy.py'
    policy.write_text(policy.read_text(encoding='utf-8').replace('days <= 3', 'days <= 4'), encoding='utf-8')
    result, text = _pytest(root, '-q')
    assert result.returncode == 0 and 'red: ' not in text, text
    assert 'unverified: STANDING（policy.py:2）：uses attribute close' in text, text


def test_check_all_fails_a_grey_rule_quoting_the_owner_unless_it_is_listed(tmp_path):
    files = {
        'policy.py': '''
            import json
            # flowguard: sensor LIMIT
            def limit(days: int) -> bool:
                return days <= json.loads("3")
        ''',
        'tests/test_policy.py': '''
            from policy import limit
            def test_limit():
                assert limit(2) is True
        ''',
        'tests/intent/limit.py': '''
            from flowguard.intent import rule, row
            @rule("LIMIT_RULE", decides="limit", fields={"days": int}, source="owner R1: 最多三天", anchor="LIMIT")
            def LIMIT_RULE(days):
                return days <= 3
            LIMIT_RULE.rows(row(days=4, expect=False, why="the fourth day stays refused"))
        ''',
    }
    root = _project(tmp_path / 'p', files)
    (tmp_path / 'owner.txt').write_text('宽限期最多三天，过了就不允许。\n', encoding='utf-8')
    stored, text = _cli(root, 'req', 'add', str(tmp_path / 'owner.txt'), '--id', 'R1')
    assert stored.returncode == 0, text
    (root / 'tests/intent/limit.py').write_text((root / 'tests/intent/limit.py').read_text(encoding='utf-8').replace(
        'owner R1: 最多三天', 'owner R1: 宽限期最多三天'), encoding='utf-8')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'owner words')
    checked, text = _cli(root, 'check', '--all')
    assert checked.returncode == 1, text
    assert 'red: LIMIT_RULE：rule cites original words from the owner (R1), but is now grey (unverified): module initialization of json is not proved pure' in text, text
    assert f'[unverified] section, write a reason: LIMIT_RULE = ' in text, text
    (root / ledger.LEDGER).parent.mkdir(exist_ok=True)
    (root / ledger.LEDGER).write_text('[unverified]\nLIMIT_RULE = ' + ledger._quote(
        '这个判断读 json 配置，模块导入证明不了纯；由 test_limit 和回归行守住') + '\n', encoding='utf-8')
    listed, text = _cli(root, 'check', '--all')
    assert listed.returncode == 0, text
    assert 'rule cites original words from the owner' not in text, text


def test_a_grey_mutation_probe_alone_does_not_make_an_owner_rule_unverified(tmp_path):
    # --deep adds a `live` mutation item; it cannot call a `fields` anchor directly, yet the rule was checked.
    from flowguard.intent.cli import _owner_rules_unverified
    from flowguard.intent.config import load_config
    cfg = load_config(tmp_path)
    rules = {'LIMIT': dict(source='owner R1: limit', decides='limit')}
    checked = dict(kind='cells', verdict='ok', grey=[])
    probe = dict(kind='live', verdict='grey', grey=['live mutation needs a directly callable anchor'])
    data = dict(summary=dict(rules=rules), results=dict(LIMIT=dict(items={'cells': checked, 'live': probe})))
    assert _owner_rules_unverified(cfg, data) == []
    grey = dict(kind='cells', verdict='grey', grey=['field days could not be read'])
    data['results']['LIMIT']['items']['cells'] = grey
    assert len(_owner_rules_unverified(cfg, data)) == 1


# The options pytest-xdist 3 sets before any pytest_configure (xdist/plugin.py pytest_cmdline_main and
# xdist/remote.py): `dist` with `tx` on the controller, `workerinput` on a worker. The stand-in is the
# same interface without the package, so the refusal is exercised whether or not xdist is installed.
XDIST_STAND_IN = '''
import pytest

def pytest_addoption(parser):
    group = parser.getgroup('xdist stand-in')
    group._addoption('-n', '--numprocesses', dest='numprocesses', type=int, default=None)
    group.addoption('--dist', dest='dist', default='no')
    group.addoption('--tx', dest='tx', action='append', default=[])
    group.addoption('--as-worker', dest='as_worker', action='store_true', default=False)

@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    if config.option.numprocesses:
        if config.option.dist == 'no':
            config.option.dist = 'load'
        config.option.tx = ['popen'] * config.option.numprocesses
    if config.option.as_worker:
        config.workerinput = {'workerid': 'gw0'}
'''

REFUSED = 'FlowGuard judges a test session in one pytest process: pytest-xdist workers'


COPIES = {
    'policy.py': '''
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days <= 3
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days <= 3
    ''',
    'tests/test_policy.py': '''
        from policy import preview, standing
        def test_standing():
            assert standing(2) is True and preview(2) is True
    ''',
}


def _red_project(root):
    """A session red no failed test carries: one of two agreeing copies changes, so they disagree at 4."""
    root = _project(root, COPIES)
    policy = root / 'policy.py'
    policy.write_text(policy.read_text(encoding='utf-8').replace('    return days <= 3', '    return days <= 4', 1), encoding='utf-8')
    return root


def _ran(text):
    import re
    return re.search(r'\d+ (passed|failed|unverified)', text) is not None


def test_distributed_workers_are_refused_before_a_red_can_be_lost(tmp_path):
    import os
    root = _red_project(tmp_path / 'p')
    plugins = tmp_path / 'plugins'                       # outside the project: not project code
    plugins.mkdir()
    (plugins / 'xdist_stand_in.py').write_text(XDIST_STAND_IN, encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(plugins), os.environ.get('PYTHONPATH')])))
    stand_in = ('-q', '-p', 'no:xdist', '-p', 'xdist_stand_in')
    plain, text = _pytest(root, *stand_in, env=env)
    assert plain.returncode == 1 and 'red: same-name anchor STANDING' in text, text
    for options in (['-n', '2'], ['--dist', 'load', '--tx', 'popen'], ['--as-worker']):
        refused, text = _pytest(root, *stand_in, *options, env=env)
        assert refused.returncode == 4 and REFUSED in text, (options, text)
        assert not _ran(text) and 'red: ' not in text, (options, text)
    for options in (['-n', '0'], ['--dist', 'load'], ['-n', '2', '--collect-only']):   # no worker starts
        single, text = _pytest(root, *stand_in, *options, env=env)
        assert REFUSED not in text, (options, text)
        assert single.returncode == (0 if '--collect-only' in options else 1), (options, text)
        assert '--collect-only' in options or 'red: same-name anchor STANDING' in text, (options, text)


def test_dash_n_two_never_ends_as_a_passed_run_with_or_without_xdist(tmp_path):
    # With pytest-xdist installed FlowGuard refuses the workers; without it pytest refuses `-n` itself.
    # Either way the session red cannot end as `2 passed` with exit 0.
    import importlib.util
    root = _red_project(tmp_path / 'p')
    result, text = _pytest(root, '-q', '-n', '2')
    assert result.returncode == 4 and not _ran(text), text
    if importlib.util.find_spec('xdist') is not None:
        assert REFUSED in text, text
    else:
        assert 'unrecognized arguments: -n' in text, text


def _junit(path):
    import xml.etree.ElementTree as ET
    suite = ET.parse(path).getroot().find('testsuite')
    cases = {case.get('classname') + '::' + case.get('name'): case for case in suite.iter('testcase')}
    properties = {name: {(item.get('name'), item.get('value')) for item in case.iter('property')} for name, case in cases.items()}
    return suite, cases, properties


def test_junit_xml_marks_a_grey_item_and_writes_a_session_red_as_a_failed_testcase(tmp_path):
    root = _project(tmp_path / 'grey', ASSUMED)
    result, text = _pytest(root, '-q', f'--junitxml={tmp_path / "grey.xml"}')
    assert result.returncode == 0 and '1 unverified' in text, text
    suite, cases, properties = _junit(tmp_path / 'grey.xml')
    assert suite.get('failures') == '0' and 'flowguard::session' not in cases, cases
    assert properties['tests.intent.limit::LIMIT_RULE[rules]'] == {('flowguard_outcome', 'unverified')}, properties
    assert all(not found for name, found in properties.items() if name != 'tests.intent.limit::LIMIT_RULE[rules]'), properties
    # A session red exits 1 although every test passed: the XML has the same failed verdict.
    root = _red_project(tmp_path / 'red')
    result, text = _pytest(root, '-q', f'--junitxml={tmp_path / "red.xml"}')
    assert result.returncode == 1 and '2 passed' in text and 'red: same-name anchor STANDING' in text, text
    suite, cases, properties = _junit(tmp_path / 'red.xml')
    assert suite.get('failures') == '1', cases
    failure = cases['flowguard::session'].find('failure')
    assert failure is not None and 'red: same-name anchor STANDING' in failure.get('message'), failure
    assert 'days=4' in failure.text, failure.text
    assert all(case.find('failure') is None for name, case in cases.items() if name != 'flowguard::session'), cases


FLOW_DOCS = '''
    class Doc:
        def __init__(self):
            self.state = 'draft'

    # flowguard: event STORED
    def store(doc: Doc):
        doc.state = 'stored'

    # flowguard: event SHIPPED
    def ship(doc: Doc):
        doc.state = 'shipped'
'''


def _owner_flow(root, tmp_path, calls):
    files = {'docs_mod.py': FLOW_DOCS,
             'tests/test_docs.py': 'from docs_mod import Doc, store, ship\n\ndef test_cycle():\n    doc = Doc()\n'
                                   + ''.join(f'    {call}(doc)\n' for call in calls) + '    assert doc.state\n',
             'tests/intent/flows.py': '''
                 from flowguard.intent import precedes
                 ORDER = precedes("STORED", "SHIPPED", source="owner R1: 先存好再发出去")
             '''}
    root = _project(root, files)
    (tmp_path / 'owner.txt').write_text('先存好再发出去，不能跳过存。\n', encoding='utf-8')
    stored, text = _cli(root, 'req', 'add', str(tmp_path / 'owner.txt'), '--id', 'R1')
    assert stored.returncode == 0, text
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'owner words')
    return root


def test_a_flow_item_shows_the_verdict_of_the_events_it_was_judged_on(tmp_path):
    green = _owner_flow(tmp_path / 'green', tmp_path, ['store', 'ship'])
    result, text = _pytest(green, '-v', f'--junitxml={tmp_path / "green.xml"}')
    line = next(line for line in text.splitlines() if 'PRECEDES_STORED_SHIPPED[flow]' in line)
    assert result.returncode == 0 and 'PASSED' in line and 'UNVERIFIED' not in line, text
    assert 'unverified' not in text.splitlines()[-1], text
    assert not any(_junit(tmp_path / 'green.xml')[2].values())
    red = _owner_flow(tmp_path / 'red', tmp_path, ['ship', 'store'])
    result, text = _pytest(red, '-v', f'--junitxml={tmp_path / "red.xml"}')
    line = next(line for line in text.splitlines() if 'PRECEDES_STORED_SHIPPED[flow]' in line)
    assert result.returncode == 1 and 'FAILED' in line and 'UNVERIFIED' not in line, text
    assert '1 failed, 2 passed' in text.splitlines()[-1], text
    suite, cases, properties = _junit(tmp_path / 'red.xml')
    # The red is the Flow test's own failure; the session adds no second testcase for it.
    assert suite.get('failures') == '1' and cases['tests.intent.flows::PRECEDES_STORED_SHIPPED[flow]'].find('failure') is not None, cases


GATE = {
    'gate.py': '''
        class Answer:
            def __init__(self, ok):
                self.ok = ok
            def __bool__(self):
                return self.ok

        # flowguard: sensor GATE
        def gate(age: int):
            return age >= 18
    ''',
    'tests/test_gate.py': '''
        from gate import gate
        def test_gate():
            assert gate(30)
    ''',
}


def _change(root, name, old, new):
    path = root / name
    text = path.read_text(encoding='utf-8')
    assert old in text, (name, old)
    path.write_text(text.replace(old, new), encoding='utf-8')


def test_a_result_that_is_no_longer_json_is_not_compared(tmp_path):
    root = _project(tmp_path / 'opaque', GATE)
    _change(root, 'gate.py', '    return age >= 18', '    return Answer(age >= 18)')
    result, text = _pytest(root, '-q')
    assert result.returncode == 0 and '2 passed' in text and 'red: ' not in text, text
    assert 'unverified: GATE：no comparable JSON result' in text, text
    # The baseline already returned the object: the same not-compared line, still no failure.
    shared = _project(tmp_path / 'shared', dict(GATE, **{'gate.py': textwrap.dedent(GATE['gate.py']).replace(
        '    return age >= 18', '    return Answer(age >= 18)')}))
    _change(shared, 'gate.py', 'age >= 18', 'age >= 21')
    result, text = _pytest(shared, '-q')
    assert result.returncode == 0 and 'red: ' not in text, text
    assert 'unverified: GATE：no comparable JSON result' in text, text


def test_a_call_that_became_a_generator_or_coroutine_is_not_compared(tmp_path):
    for name, function, call in (('generator', '    yield age >= 18', 'next(gate(30))'),
                                 ('coroutine', None, '__import__("asyncio").run(gate(30))')):
        root = _project(tmp_path / name, GATE)
        if function:
            _change(root, 'gate.py', '    return age >= 18', function)
        else:
            _change(root, 'gate.py', 'def gate(age: int):', 'async def gate(age: int):')
        _change(root, 'tests/test_gate.py', 'assert gate(30)', 'assert ' + call)
        result, text = _pytest(root, '-q')
        assert result.returncode == 0 and '2 passed' in text and 'red: ' not in text, (name, text)
        assert 'unverified: GATE：calibration async/generator is unsupported' in text, (name, text)
    # A test that never enters the generator: the same not-compared line.
    root = _project(tmp_path / 'unentered', GATE)
    _change(root, 'gate.py', '    return age >= 18', '    yield age >= 18')
    result, text = _pytest(root, '-q')
    assert result.returncode == 0 and 'observation lost' not in text, text
    assert 'unverified: GATE：calibration async/generator is unsupported' in text, text


def test_an_unanchored_changed_function_whose_replay_is_refused_is_listed_unverified(tmp_path):
    files = {
        'policy.py': '''
            def limit(days: int) -> bool:
                return days <= 3
        ''',
        'tests/test_policy.py': '''
            from policy import limit
            def test_limit(tmp_path, monkeypatch):
                monkeypatch.chdir(tmp_path)
                assert limit(2) is True
        ''',
    }
    root = _project(tmp_path / 'p', files)
    _change(root, 'policy.py', '    return days <= 3', '    open("audit.log", "a").close()\n    return days <= 3')
    result, text = _pytest(root, '-q')
    # Not an anchor or a rule: nothing is lost and nothing is red, but the grey is never quiet.
    assert result.returncode == 0 and 'observation lost' not in text and 'red: ' not in text, text
    assert 'unverified 1 items (not passed)' in text, text
    assert 'unverified: limit(unanchored, automatic)（policy.py:1）：uses attribute close' in text, text
    assert not (root / 'audit.log').exists()


def test_check_all_fails_a_grey_template_flow_quoting_the_owner(tmp_path):
    root = _owner_flow(tmp_path / 'p', tmp_path, [])       # no test stores or ships: the Flow stays grey
    checked, text = _cli(root, 'check', '--all')
    assert checked.returncode == 1, text
    assert 'red: PRECEDES_STORED_SHIPPED：rule cites original words from the owner (R1), but is now grey (unverified)' in text, text
    assert '[unverified] section, write a reason: PRECEDES_STORED_SHIPPED = ' in text, text
    brief, text = _cli(root)
    # The brief (design 4.7) lists the rules of rules.toml, not an unfinished intent item: check --all lists that.
    assert brief.returncode == 0 and text.startswith('FlowGuard ') and 'PRECEDES_STORED_SHIPPED' not in text, text
    (root / ledger.LEDGER).parent.mkdir(exist_ok=True)
    (root / ledger.LEDGER).write_text('[unverified]\nPRECEDES_STORED_SHIPPED = ' + ledger._quote(
        '测试还没有走到存和发这两步，顺序由 test_docs 之外的集成检查守住') + '\n', encoding='utf-8')
    listed, text = _cli(root, 'check', '--all')
    assert listed.returncode == 0 and 'rule cites original words from the owner' not in text, text
