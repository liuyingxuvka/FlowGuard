"""The 4.3 interfaces: the last run's lines in the cache, `show --last`, `show rules` over
the catalog, the new finding fields and the session's comparison commit on the engine."""
from contextlib import closing
from dataclasses import asdict
import json

from flowguard.intent import cache, cli, sources
from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.health import Issue
from flowguard.intent.loader import load
from flowguard.intent.signals import Line
from flowguard.structure.store import connect
from tests.intent_engine.test_plugin import run
from tests.intent_engine.test_static_check import _commit


def test_the_last_run_round_trips_through_the_cache_meta_and_is_none_before_any_run(tmp_path):
    cfg = load_config(tmp_path)
    assert cache.read_last(cfg) is None                     # no cache at all
    cfg.cache.mkdir(parents=True)
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.put_meta(con, 'task_baseline', json.dumps({'commit': '0' * 40}))
    assert cache.read_last(cfg) is None                     # a cache without the key
    payload = dict(stamp=1.5, run='check --static', baseline='abc', baseline_kind='task', title='FlowGuard 4.2 (since abc)',
                   seconds=0.25, lines=[asdict(Line('red', 'pair:A>B', 'm:f', 'together A: caf\u00e9.py:f writes A', 'also write B',
                                                    ('caf\u00e9.py:f',), ('detail',)))], ignored=2, deprecated=['owner writers='])
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
        cache.save_last(con, dict(stamp=1.0, run='pytest', baseline='a' * 40, baseline_kind='task', seconds=0.5,
                                  title='FlowGuard 4.2 (since aaaaaaa): 1 red, 2 not compared; 0.5 s',
                                  lines=[asdict(line) for line in lines], ignored=2, deprecated=['sensor', 'owner writers='],
                                  hidden=[dict(feature='old-value leads', text='old values 14 remain in 4 decisions'),
                                          dict(feature='', text='STANDING copies changed; rule GRACE is unchanged')],
                                  compared=['K0 (knobs.py:2): 2 inputs compared, none differs']))
    assert cli.main(['--root', root, 'show', '--last']) == 0
    # No budget and no shortening: every line, its paths in full, its detail indented under it.
    assert capsys.readouterr().out.splitlines() == [
        'FlowGuard 4.2 (since aaaaaaa): 1 red, 2 not compared; 0.5 s',
        'red: together A: src/deep/a.py:f writes A without B -> also write B in f', '    JS/TS calls resolved by name',
        'not compared: N -> not a failure', '    uses attribute close', 'not compared: M -> not a failure', '    uses attribute close',
        'ignored: 2 (act = "ignore")', 'deprecated features used (5.0): sensor, owner writers=',
        'compared, unchanged:', '    K0 (knobs.py:2): 2 inputs compared, none differs',
        'deprecated leads (5.0):', '    old-value leads: old values 14 remain in 4 decisions',
        '    STANDING copies changed; rule GRACE is unchanged']
    assert cli.main(['--root', root, 'show', '--last', 'NAME']) == 2
    assert 'show --last takes no NAME' in capsys.readouterr().err
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
