"""The 4.3 interfaces that print nothing yet: the last run's lines in the cache, `show --last`, `show rules`, the
empty catalog, the new finding fields and the session's comparison commit on the engine."""
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


def test_show_last_and_the_catalog_queries_print_one_line_and_leave_every_other_show_alone(tmp_path, capsys):
    root = str(tmp_path)
    assert cli.main(['--root', root, 'show', '--last']) == 0
    assert capsys.readouterr().out == 'FlowGuard: no last run recorded\n'
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, dict(lines=[]))
    assert cli.main(['--root', root, 'show', '--last']) == 0
    assert capsys.readouterr().out == 'FlowGuard: a last run is recorded, but this version does not print it yet\n'
    assert cli.main(['--root', root, 'show', '--last', 'NAME']) == 2
    assert 'show --last takes no NAME' in capsys.readouterr().err
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/known.toml').write_text('[known.x]\n', encoding='utf-8')
    for query in ('rules', 'rule.english-skill', 'known.percent-scale'):
        assert cli.main(['--root', root, 'show', query]) == 0
        assert capsys.readouterr().out == 'FlowGuard: this version does not read .flowguard/known.toml yet\n'
    (tmp_path / '.flowguard/rules.toml').write_text('[rule.x]\n', encoding='utf-8')
    assert cli.main(['--root', root, 'show', 'rules']) == 0
    assert capsys.readouterr().out == 'FlowGuard: this version does not read .flowguard/rules.toml or .flowguard/known.toml yet\n'
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
    assert cli.main(['--root', root, 'show', 'rule.name']) == 0
    assert capsys.readouterr().out == 'FlowGuard: this version does not read .flowguard/rules.toml yet\n'


def test_the_catalog_is_empty_with_or_without_its_files(tmp_path):
    cfg = load_config(tmp_path)
    assert sources.catalog(cfg) == sources.Catalog() == sources.Catalog({}, {}, [])
    assert sources.catalog_files(cfg) == []
    (tmp_path / '.flowguard').mkdir()
    (tmp_path / '.flowguard/rules.toml').write_text('[rule.x]\ntext = "x"\n', encoding='utf-8')
    assert sources.catalog_files(cfg) == ['.flowguard/rules.toml']
    assert sources.catalog(cfg) == sources.catalog(cfg, 'HEAD') == sources.Catalog()


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
