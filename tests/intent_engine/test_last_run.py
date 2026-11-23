"""The 4.3 interfaces: the last run's lines in the cache, `show --last`, `show rules` over
the catalog, the new finding fields and the session's comparison commit on the engine."""
from contextlib import closing
from dataclasses import asdict
import json
import time

from flowguard import __version__
from flowguard.intent import cache, cli, sources
from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.health import Issue
from flowguard.intent.loader import load
from flowguard.intent.signals import Line
from flowguard.structure.store import connect
from tests.intent_engine.test_plugin import run
from tests.intent_engine import _cli_fixture
from tests.intent_engine.test_static_check import _commit, _static, _write


def test_the_last_run_round_trips_through_the_cache_meta_and_is_none_before_any_run(tmp_path):
    cfg = load_config(tmp_path)
    assert cache.read_last(cfg) is None                     # no cache at all
    cfg.cache.mkdir(parents=True)
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.put_meta(con, 'task_baseline', json.dumps({'commit': '0' * 40}))
    assert cache.read_last(cfg) is None                     # a cache without the key
    payload = dict(scope='repo', version='5.1.0', stamp=1.5, run='check --static', baseline='abc', baseline_kind='task',
                   title='FlowGuard 4.2 (since abc)', seconds=0.25, pytest=None,
                   lines=[asdict(Line('red', 'pair:A>B', 'm:f', 'together A: caf\u00e9.py:f writes A', 'also write B',
                                      ('caf\u00e9.py:f',), ('detail',)))], ignored=2, compared=[])
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, payload)
    assert cache.read_last(cfg) == json.loads(json.dumps(payload))
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, dict(payload, lines=[]))       # the next run replaces it
    assert cache.read_last(cfg)['lines'] == []


def test_show_last_prints_every_line_and_the_catalog_queries_read_the_catalog_and_leave_every_other_show_alone(tmp_path, capsys):
    root = str(tmp_path)
    assert cli.main(['--root', root, 'show', '--last']) == 0
    assert capsys.readouterr().out == 'FlowGuard: no last run recorded\n'
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    lines = [Line('red', 'pair:A>B', 'm:f', 'together A: src/deep/a.py:f writes A without B', 'also write B in f', ('src/deep/a.py:f',),
                  ('JS/TS calls resolved by name',)),
             *(Line('not compared', f'not compared:{name}', '', name, 'not a failure', (), ('uses attribute close',)) for name in 'NM')]
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, dict(scope='repo', version='5.1.0', stamp=1.0, run='pytest', baseline='a' * 40, baseline_kind='task',
                                  seconds=0.5, pytest=dict(exit=1, failed=2, errors=1, stopped=''),
                                  title='FlowGuard 4.2 (since aaaaaaa): 1 red, 2 not compared; 0.5 s',
                                  lines=[asdict(line) for line in lines], ignored=2,
                                  compared=['K0 (knobs.py:2): 2 inputs compared, none differs']))
    assert cli.main(['--root', root, 'show', '--last']) == 0
    # No budget and no shortening: every line, its paths in full, its detail indented under it.
    assert capsys.readouterr().out.splitlines() == [
        f'FlowGuard 5.1.0 last run: pytest at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1.0))}',
        'pytest: exit 1, 2 failed, 1 error',         # pytest's own outcome: the first line counts agreements
        'FlowGuard 4.2 (since aaaaaaa): 1 red, 2 not compared; 0.5 s',
        'red: together A: src/deep/a.py:f writes A without B -> also write B in f', '    JS/TS calls resolved by name',
        '    finding pair:A>B',          # the name known add takes; a line that is no finding has none
        'not compared: N -> not a failure', '    uses attribute close', 'not compared: M -> not a failure', '    uses attribute close',
        'ignored: 2 (act = "ignore")',
        'compared, unchanged:', '    K0 (knobs.py:2): 2 inputs compared, none differs']
    assert cli.main(['--root', root, 'show', '--last', 'NAME']) == 2
    assert 'show --last takes no NAME' in capsys.readouterr().err
    # A run in which no entry ignored anything says nothing of ignoring.
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, dict(cache.read_last(cfg), ignored=0, compared=[]))
    assert cli.main(['--root', root, 'show', '--last']) == 0
    shown = capsys.readouterr().out.splitlines()
    assert shown[1:] == ['pytest: exit 1, 2 failed, 1 error', 'FlowGuard 4.2 (since aaaaaaa): 1 red, 2 not compared; 0.5 s',
                         'red: together A: src/deep/a.py:f writes A without B -> also write B in f', '    JS/TS calls resolved by name',
                         '    finding pair:A>B', 'not compared: N -> not a failure', '    uses attribute close', 'not compared: M -> not a failure',
                         '    uses attribute close'], shown
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/known.toml').write_text('[known.x]\n', encoding='utf-8')
    # An entry without its keys is an input problem: show lists it and fails; a name the catalog lacks fails too.
    assert cli.main(['--root', root, 'show', 'rules']) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0] == 'FlowGuard rules: 0 in .flowguard/rules.toml, 0 known in .flowguard/known.toml, 1 input problems', out
    assert 'input known-entry:known.x: .flowguard/known.toml:known.x missing sites; missing why; missing act -> ' in out, out
    for query, file in (('rule.english-skill', 'rules'), ('known.percent-scale', 'known')):
        assert cli.main(['--root', root, 'show', query]) == 1
        assert capsys.readouterr().out == f'{query} is not in .flowguard/{file}.toml: python -m flowguard show rules lists every entry\n'
    (tmp_path / '.flowguard/rules.toml').write_text('[rule.x]\n', encoding='utf-8')
    assert cli.main(['--root', root, 'show', 'rule.x']) == 1
    assert 'input rules-entry:rule.x: .flowguard/rules.toml:rule.x missing text; missing source -> ' in capsys.readouterr().out
    # Any other query still needs a name and finds rules, functions and words as before.
    assert cli.main(['--root', root, 'show']) == 2
    assert 'show needs a rule, function, request id or words' in capsys.readouterr().err


def test_the_leads_only_show_last_kept_are_gone_since_5_0(tmp_path):
    """5.0 removed the leads 4.3 kept for `show --last` under `deprecated leads (5.0)`: an old value still spelled
    elsewhere, a function whose old body an unchanged function still has, a label spelled a new way. A change that
    made each of them gives no line, keeps no list of them, and show --last has no such section."""
    _commit(tmp_path, {'limits.py': 'GRACE_DAYS = 14\n', 'reminders.py': 'def remind(days):\n    return days > 14\n',
                       'fees.py': 'def late_fee(days, rate):\n    return (days - 3) * rate if days > 3 else 0\n',
                       'legacy.py': 'def late_charge(days, rate):\n    return (days - 3) * rate if days > 3 else 0\n',
                       'labels.py': "def home(kind):\n    return kind == 'My Organization'\n"})
    _write(tmp_path, {'limits.py': 'GRACE_DAYS = 21\n', 'fees.py': 'def late_fee(days, rate):\n    return (days - 5) * rate if days > 5 else 0\n',
                      'view.py': "def title(kind):\n    return 'My organization' if kind else ''\n"})
    code, text = _static(tmp_path)
    assert code == 0 and _cli_fixture.block(text)[1:] == [], text
    last = cache.read_last(load_config(tmp_path))
    assert sorted(last) == ['baseline', 'baseline_kind', 'compared', 'ignored', 'lines', 'pytest', 'run', 'scope', 'seconds',
                            'stamp', 'title', 'version'], last
    shown = _cli_fixture.last(tmp_path).splitlines()
    assert shown[1:] == [last['title']], shown


def test_without_a_catalog_file_show_rules_and_rule_names_find_what_they_found_before(tmp_path, capsys):
    _commit(tmp_path, {'app/__init__.py': '', 'app/pricing.py': """
        class Rules:
            def apply(self, x):
                return x

        def rules():
            return Rules()
    """, 'db/schema.sql': 'CREATE TABLE rule (id INTEGER PRIMARY KEY, name TEXT);\n', 'app/store.py': """
        def rename(con):
            con.execute("UPDATE rule SET name = 'x' WHERE id = 1")
    """})
    root = str(tmp_path)
    assert cli.main(['--root', root, 'show', 'rules']) == 0
    out = capsys.readouterr().out
    assert 'rules app/pricing.py:' in out and 'FlowGuard: no' not in out, out
    assert cli.main(['--root', root, 'show', 'rule.name']) == 0
    out = capsys.readouterr().out
    assert 'app/store.py:2 rename (sql:update)' in out and 'FlowGuard: no' not in out, out
    # A catalog file present: these names are the catalog's.
    (tmp_path / '.flowguard/rules.toml').write_text('[rule.name]\n', encoding='utf-8')
    assert cli.main(['--root', root, 'show', 'rule.name']) == 1
    out = capsys.readouterr().out
    assert 'input rules-entry:rule.name: ' in out and 'app/store.py' not in out, out


def test_the_catalog_is_empty_without_its_files_and_reads_them_when_present(tmp_path):
    cfg = load_config(tmp_path)
    assert sources.catalog(cfg) == sources.Catalog() == sources.Catalog({}, {}, [])
    assert sources.catalog_files(cfg) == []
    (tmp_path / '.flowguard').mkdir()
    (tmp_path / '.flowguard/rules.toml').write_text('[rule.x]\ntext = "x"\n', encoding='utf-8')
    assert sources.catalog_files(cfg) == ['.flowguard/rules.toml']
    found = sources.catalog(cfg)
    assert found.rules == {} and [issue.name for issue in found.issues] == ['rules-entry:rule.x'], found


def test_the_new_finding_fields_default_to_nothing_and_the_engine_has_no_baseline_of_its_own(tmp_path):
    issue = Issue('pair:A>B', 2, 'pair A', 'text', 'step')
    assert (issue.family, issue.subject, issue.parts, issue.fresh, issue.detail) == ('', '', (), frozenset(), ())
    assert sources.Known('k', ('a.py:f',), 'why', 'leave').nodes == frozenset()
    assert Engine(load(load_config(tmp_path))).baseline is None


def test_the_pytest_session_gives_the_engine_its_comparison_commit(tmp_path):
    _commit(tmp_path, {'tests/test_engine_baseline.py': '''
        import subprocess

        def test_engine_baseline(request):
            state = request.config._flowguard_intent
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
            assert len(head) == 40 and state.engine.baseline == state.observations.runtime.baseline == head
    '''})
    result = run(tmp_path, 'tests/test_engine_baseline.py')
    assert result.returncode == 0 and '1 passed' in result.stdout, result.stdout + result.stderr


def test_every_pytest_run_that_prints_a_block_keeps_it_for_show_last(tmp_path):
    """show --last never prints an earlier run as the last one: a run that selects no test prints its block and keeps
    it, and show --last says which run it was and when."""
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import block, last
    policy = _project(tmp_path, '''
        # flowguard: same LIMIT
        def chart(days: int) -> bool:
            return days <= 3
        # flowguard: same LIMIT
        def calendar(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import chart, calendar
        def test_limit():
            assert chart(1) and calendar(1)
    ''')
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 4', 1))
    red = _run(tmp_path)
    assert red.returncode == 1 and block(red)[1].startswith('red: same LIMIT'), red.stdout
    nothing = _run(tmp_path, '-k', 'nothing_matches')
    assert nothing.returncode == 5, nothing.stdout + nothing.stderr
    shown = last(tmp_path).splitlines()
    assert shown[0].startswith(f'FlowGuard {__version__} last run: pytest at ') and shown[1] == 'pytest: exit 5, 0 failed', shown
    untimed = lambda title: title.rpartition('; ')[0]
    assert untimed(shown[2]) == untimed(block(nothing)[0]) and not any(line.startswith('red: ') for line in shown), (shown, nothing.stdout)


def test_the_terminal_junit_and_show_last_give_one_run_the_same_first_line(tmp_path):
    """One time per run: FlowGuard's own work in the session, taken once after all of it (here a slow write of the
    session's readings, which a conftest of the project injects), in the block, junit's flowguard::session case and
    the run kept for show --last alike."""
    import xml.etree.ElementTree as ET
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import block, last
    policy = _project(tmp_path, '''
        # flowguard: same LIMIT
        def chart(days: int) -> bool:
            return days <= 3
        # flowguard: same LIMIT
        def calendar(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import chart, calendar
        def test_limit():
            assert chart(1) and calendar(1)
    ''')
    (tmp_path / 'tests/conftest.py').write_text('''
import time
from flowguard.intent import plugin
_readings = plugin._save_readings
def _slow(con, state):
    time.sleep(0.4)
    _readings(con, state)
plugin._save_readings = _slow
''', encoding='utf-8')
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 4', 1))
    result = _run(tmp_path, f'--junitxml={tmp_path / "junit.xml"}')
    assert result.returncode == 1, result.stdout + result.stderr
    title = block(result)[0]
    failures = [failure.text for failure in ET.parse(tmp_path / 'junit.xml').iter('failure')]
    assert [text.splitlines()[0] for text in failures] == [title], (failures, title)
    shown = last(tmp_path).splitlines()
    assert shown[1:3] == ['pytest: exit 1, 0 failed', title], (shown, title)
    assert float(title.rpartition('; ')[2].removesuffix(' s')) >= 0.4, title


def _slot(scope, stamp, lines=(), *, run='vitest', baseline='a' * 40, started=None):
    """A last run as `signals.last_run` keeps it, of slot `scope`, its lines given as Line fields."""
    payload = dict(scope=scope, version='5.1.0', stamp=stamp, run=run, baseline=baseline, baseline_kind='task', seconds=0.5,
                   title=f'FlowGuard 5.1 (since aaaaaaa): {sum(line[0] == "red" for line in lines)} red; 0.5 s', pytest=None,
                   lines=[asdict(Line(*line)) for line in lines], ignored=0, compared=[])
    return dict(payload, started=started) if started else payload


RED = ('red', 'same:WEB_LIMIT', 'web/src/a.ts:over', 'same WEB_LIMIT: on x=3: web/src/a.ts:over returns False, web/src/b.ts:enough '
       'returns True', 'decide which copy is right, then make the other agree', ('web/src/a.ts:over', 'web/src/b.ts:enough'))


def _package(root, folder):
    (root / folder).mkdir(parents=True, exist_ok=True)
    (root / folder / 'vitest.config.mjs').write_text('export default {};\n', encoding='utf-8')


def test_each_vitest_package_keeps_its_own_last_run_and_another_packages_pass_never_covers_its_red(tmp_path, capsys):
    """PTWF-3b: 5.0 kept one last run, which the next run replaced, so a red of web/ followed by a pass of api/ left the
    brief silent and `show --last` named neither package. pytest, check and check --static share the `repo` slot; each
    vitest package has its own, `show --last` prints every slot newest first with the full version, and the brief
    counts every slot's reds by the run that left them."""
    for folder in ('web', 'api'):
        _package(tmp_path, folder)
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, _slot('vitest:web', 10.0, [RED]))
        cache.save_last(con, _slot('vitest:api', 20.0))
        cache.save_last(con, _slot('repo', 5.0, run='check --static'))
    assert [run['scope'] for run in cache.read_runs(cfg)] == ['vitest:api', 'vitest:web', 'repo']
    assert cache.read_last(cfg)['run'] == 'check --static' and cache.read_last(cfg, 'vitest:web')['lines'][0]['kind'] == 'red'
    assert cli.main(['--root', str(tmp_path), 'show', '--last']) == 0
    at = lambda stamp: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp))
    assert capsys.readouterr().out.splitlines() == [
        f'FlowGuard 5.1.0 last run: vitest api/ at {at(20.0)}', 'FlowGuard 5.1 (since aaaaaaa): 0 red; 0.5 s',
        f'FlowGuard 5.1.0 last run: vitest web/ at {at(10.0)}', 'FlowGuard 5.1 (since aaaaaaa): 1 red; 0.5 s',
        'red: ' + RED[3] + ' -> ' + RED[4], '    finding same:WEB_LIMIT',
        f'FlowGuard 5.1.0 last run: check --static at {at(5.0)}', 'FlowGuard 5.1 (since aaaaaaa): 0 red; 0.5 s']
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[-1] == '1 red in the last run of web/: python -m flowguard show --last'
    # a red in the repo slot too: both runs are named, newest first
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, _slot('repo', 30.0, [('red', 'pair:A>B', 'm:f', 'together A: m.py:f writes A', 'also write B',
                                                   ('m.py:f',))], run='check --static'))
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[-1] == ('2 red in the last runs of check --static and web/: '
                                                        'python -m flowguard show --last')
    # a package whose config is gone is no longer read: its slot is dropped
    (tmp_path / 'web/vitest.config.mjs').unlink()
    assert [run['scope'] for run in cache.read_runs(cfg)] == ['repo', 'vitest:api']
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[-1] == '1 red in the last run: python -m flowguard show --last'


def test_a_vitest_run_that_never_reported_says_so_above_its_packages_earlier_lines(tmp_path, capsys):
    """PTW-V2-2: the preparation notes the run's start in its package's slot and the report replaces the note, so a run
    killed before it reports (an outer `timeout`) says it did not report, above the lines of the package's run before;
    5.0 showed the static test's lines from inside the killed run as a finished `check --static` with 0 red."""
    _package(tmp_path, 'web')
    _package(tmp_path, 'api')
    cfg = load_config(tmp_path)
    cache.keep_last(cfg, _slot('vitest:web', 10.0, [RED]))
    cache.keep_last(cfg, started=('vitest:web', 15.0, 'vitest'))
    cache.keep_last(cfg, started=('vitest:api', 12.0, 'vitest'))         # api has no earlier run
    assert cli.main(['--root', str(tmp_path), 'show', '--last']) == 0
    at = lambda stamp: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp))
    assert capsys.readouterr().out.splitlines() == [
        f'FlowGuard 5.1.0 last run: vitest web/ at {at(10.0)}',
        f'a vitest run of web/ started at {at(15.0)} did not report; the lines below are from the run at {at(10.0)}',
        'FlowGuard 5.1 (since aaaaaaa): 1 red; 0.5 s', 'red: ' + RED[3] + ' -> ' + RED[4], '    finding same:WEB_LIMIT',
        f'FlowGuard {__version__}: a vitest run of api/ started at {at(12.0)} did not report; no earlier run of api/ is recorded']
    assert cli.screen(cfg) == 0      # the package's last reported reds still stand
    assert capsys.readouterr().out.splitlines()[-1] == '1 red in the last run of web/: python -m flowguard show --last'
    cache.keep_last(cfg, _slot('vitest:web', 20.0))           # the next run of web/ reports: the note is gone
    assert 'started' not in cache.read_last(cfg, 'vitest:web')
    assert cli.screen(cfg) == 0 and len(capsys.readouterr().out.splitlines()) == 1


def test_the_one_last_run_of_5_0_is_read_as_its_slot(tmp_path, capsys):
    """A 5.0.1 cache keeps one record under `last_lines`, without scope or version: a pytest, check or check --static
    run is the `repo` slot, printed as 5.0 printed it; a vitest run named no package, so it is read as `vitest` until the
    next vitest run of any package replaces it, as the next vitest run replaced it in 5.0."""
    _package(tmp_path, 'web')
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    old = json.loads(json.dumps({key: value for key, value in _slot('repo', 1.0, [RED], run='pytest').items()
                                 if key not in ('scope', 'version', 'pytest')}))
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.put_meta(con, 'last_lines', json.dumps(old))
    assert cache.read_runs(cfg) == [dict(old, scope='repo')]
    assert cli.main(['--root', str(tmp_path), 'show', '--last']) == 0
    assert capsys.readouterr().out.splitlines()[0] == f'FlowGuard last run: pytest at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1.0))}'
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.put_meta(con, 'last_lines', json.dumps(dict(old, run='vitest')))
    assert [run['scope'] for run in cache.read_runs(cfg)] == ['vitest']
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[-1] == '1 red in the last run of vitest: python -m flowguard show --last'
    cache.keep_last(cfg, _slot('vitest:web', 2.0))
    assert [run['scope'] for run in cache.read_runs(cfg)] == ['vitest:web']
    assert cli.screen(cfg) == 0 and len(capsys.readouterr().out.splitlines()) == 1


def _hand(root):
    """PEMEL Studio's hand shape: tests/test_a.py fails, tests/test_b.py passes."""
    _commit(root, {'app/__init__.py': '', 'app/core.py': 'def f(x):\n    return x + 1\n',
                   'tests/test_a.py': 'from app.core import f\n\ndef test_x():\n    assert f(1) == 3\n',
                   'tests/test_b.py': 'from app.core import f\n\ndef test_b():\n    assert f(1) == 2\n',
                   'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\n'})


def test_a_failed_test_the_last_run_did_not_select_is_counted_as_such_and_show_last_lists_it(tmp_path, capsys):
    """PEMEL17-14: after `pytest` (test_a failed), `pytest tests/test_b.py`, a commit and new-task, 5.0's brief said
    `1 still red: python -m flowguard show --last`, and show --last printed only the last run, `0 red`: no route
    listed the failure, and an ordinary failed test was called red. The brief now counts it as a failed test with its
    id, from the readings it keeps (`cli._brief_reds`), and show --last lists each with its outcome, when it ran and
    whether the last pytest run selected it; a run of the test that passes clears it."""
    _hand(tmp_path)
    assert run(tmp_path).returncode == 1
    assert run(tmp_path, 'tests/test_b.py').returncode == 0
    _commit(tmp_path, {'notes.txt': 'x\n'})
    assert cli.main(['--root', str(tmp_path), 'new-task']) == 0
    brief = capsys.readouterr().out.splitlines()
    assert brief[-1] == '1 test failed when last run and has not run since: tests/test_a.py::test_x', brief
    assert not any('red' in line for line in brief[1:]), brief
    shown = _cli_fixture.last(tmp_path).splitlines()
    readings = cache.read(load_config(tmp_path))
    when = lambda stamp: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp))
    assert shown[:2] == [f'FlowGuard {__version__} last run: pytest at {when(readings["attempt"]["stamp"])}',
                         'pytest: exit 0, 0 failed'], shown
    assert shown[-2:] == ['tests that failed when last run and have not run since (the brief counts these):',
                          f'    tests/test_a.py::test_x: failed (call) at {when(readings["tests"]["tests/test_a.py::test_x"]["stamp"])}; '
                          f'not selected by the last pytest run, at {when(readings["attempt"]["stamp"])}'], shown
    assert run(tmp_path, 'tests/test_a.py').returncode == 1            # selected, failed again
    assert _cli_fixture.last(tmp_path).splitlines()[-1].endswith('; the last pytest run selected it')
    (tmp_path / 'tests/test_a.py').write_text('from app.core import f\n\ndef test_x():\n    assert f(1) == 2\n', encoding='utf-8')
    assert run(tmp_path, 'tests/test_a.py').returncode == 0
    assert cli.screen(load_config(tmp_path)) == 0 and len(capsys.readouterr().out.splitlines()) == 1
    assert 'tests that failed' not in _cli_fixture.last(tmp_path)


def test_show_last_carries_pytests_own_outcome_beside_the_agreement_counts(tmp_path):
    """PEMEL17-12: after `pytest -x` show --last said `0 red` with no exit status, failed count or early stop."""
    _hand(tmp_path)
    (tmp_path / 'tests/test_c.py').write_text('import pytest\n\n@pytest.fixture\ndef broken():\n    raise OSError("no display")\n\n'
                                              'def test_c(broken):\n    pass\n', encoding='utf-8')
    assert run(tmp_path, '-x', '-p', 'no:randomly').returncode == 1
    assert _cli_fixture.last(tmp_path).splitlines()[1] == 'pytest: exit 1, 1 failed, stopped early (-x)'
    assert run(tmp_path).returncode == 1
    assert _cli_fixture.last(tmp_path).splitlines()[1] == 'pytest: exit 1, 1 failed, 1 error'
    assert run(tmp_path, '--maxfail=2').returncode == 1
    assert _cli_fixture.last(tmp_path).splitlines()[1] == 'pytest: exit 1, 1 failed, 1 error, stopped early (--maxfail=2)'
