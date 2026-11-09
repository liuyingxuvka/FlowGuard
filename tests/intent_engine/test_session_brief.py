"""Task memory stays in existing SQLite; the brief never pretends a cache is fresh."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess

import pytest

from flowguard.intent import cache, cli
from flowguard.intent.config import load_config
from flowguard.map.common import MapError
from flowguard.map.requests import store_request
from flowguard.structure import build


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def project(tmp_path, *, versioned=True, rules=1, source='assumed: unconfirmed requirement', quote=None):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root / 'SPEC.txt').write_text('The fourth day stays refused.\n')
    (root / 'app.py').write_text('def eligible(days: int): return days <= 3\n')
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    code = 'from flowguard.intent import rule\n'
    for n in range(rules):
        code += f"@rule('R{n}',decides='limit{n}',fields={{'days':int}},source={source!r},quote={quote!r})\ndef rule{n}(days): return days <= 3\n"
    (folder / 'policy.py').write_text(code)
    (root / '.gitignore').write_text('.flowguard/cache/\n')
    if versioned:
        git(root, 'init', '--quiet')
        git(root, 'config', 'user.name', 'FlowGuard test fixture')
        git(root, 'config', 'user.email', 'flowguard-fixture@example.invalid')
        git(root, 'add', '.')
        git(root, 'commit', '--quiet', '-m', 'fixture baseline')
    return root, load_config(root)


def result(cfg, *, rule='R0', verdict='red', messages=(), kind='rules'):
    cache.session_baseline(cfg, remember=True)
    path = cfg.cache / 'map.sqlite'
    with closing(sqlite3.connect(path)) as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
        payload = dict(kind=kind, verdict=verdict, red=list(messages), grey=[], info=[])
        con.execute('INSERT OR REPLACE INTO result VALUES(?,?,?,?,?)', ('item:'+rule,rule,verdict,json.dumps(payload),1.0))


def test_baseline_read_does_not_create_storage_and_start_records_actual_head(tmp_path):
    root, cfg = project(tmp_path)
    head = git(root, 'rev-parse', 'HEAD')
    assert len(head) == 40
    assert cache.session_baseline(cfg) == head
    assert not cfg.cache.exists()
    assert cache.session_baseline(cfg, remember=True) == head
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as con:
        assert json.loads(con.execute("SELECT v FROM meta WHERE k='task_baseline'").fetchone()[0]) == {'commit': head}
    (root / 'app.py').write_text('def eligible(days: int): return days <= 4\n')
    git(root,'add','app.py'); git(root,'commit','--quiet','-m','fixture change')
    assert cache.session_baseline(cfg) == head
    # A commit made during the task keeps the task's baseline; only new-task moves it to HEAD.
    assert cache.session_baseline(cfg, remember=True) == head
    assert cache.remember_baseline(cfg, new_task=True) == (git(root,'rev-parse','HEAD'),
                                                           f'baseline: new task from HEAD {git(root,"rev-parse","HEAD")[:12]} (was {head[:12]})')
    assert cache.session_baseline(cfg) == git(root,'rev-parse','HEAD') != head


def test_brief_keeps_the_task_baseline_across_commits_and_new_task_starts_the_next(tmp_path, capsys):
    root, cfg = project(tmp_path)
    start = git(root, 'rev-parse', 'HEAD')
    assert cli.screen(cfg) == 0 and f'baseline {start[:12]}' in capsys.readouterr().out
    for days in (4, 5):
        (root / 'app.py').write_text(f'def eligible(days: int): return days <= {days}\n')
        git(root, 'commit', '--quiet', '-am', f'fixture change {days}')
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert f'baseline {start[:12]}' in lines[0], lines
    assert lines[1] == 'baseline: task start, 2 commits before HEAD; next task: python -m flowguard new-task', lines
    assert cache.session_baseline(cfg) == start             # what the task changed stays reported
    assert cli.main(['--root', str(root), 'new-task']) == 0
    head = git(root, 'rev-parse', 'HEAD')
    lines = capsys.readouterr().out.splitlines()
    assert f'baseline {head[:12]}' in lines[0] and lines[1] == f'baseline: new task from HEAD {head[:12]} (was {start[:12]})', lines
    assert cache.session_baseline(cfg) == head
    # A recorded commit HEAD does not descend from (another branch, rewritten history) is not this task's start.
    git(root, 'checkout', '--quiet', '-b', 'other', start)
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == f'baseline: recorded {head[:12]} is not an ancestor of HEAD; the task starts at HEAD', lines
    assert cache.session_baseline(cfg) == start


def test_baseline_schema_is_compatible_with_first_and_warm_map_builds(tmp_path):
    root, cfg = project(tmp_path)
    baseline = cache.session_baseline(cfg, remember=True)
    for _ in range(2):
        with closing(build(root, workers=1)) as graph:
            assert graph.node('app:eligible') is not None
            assert json.loads(graph.con.execute("SELECT v FROM meta WHERE k='task_baseline'").fetchone()[0])['commit'] == baseline
        assert cache.session_baseline(cfg) == baseline


def test_existing_sqlite_tables_survive_baseline_schema_initialization(tmp_path):
    root, cfg = project(tmp_path)
    cfg.cache.mkdir(parents=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as con, con:
        con.execute('CREATE TABLE earlier(value TEXT)')
        con.execute("INSERT INTO earlier VALUES('preserve')")
    assert cache.session_baseline(cfg) == git(root,'rev-parse','HEAD')
    cache.session_baseline(cfg, remember=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as con:
        assert con.execute('SELECT value FROM earlier').fetchall() == [('preserve',)]


@pytest.mark.parametrize('stored', ['broken json', '{"commit":"deadbeef"}', '[]'])
def test_invalid_stored_baseline_is_an_error_not_silent_head_fallback(tmp_path, stored):
    _, cfg = project(tmp_path)
    cache.session_baseline(cfg, remember=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as con, con:
        con.execute("UPDATE meta SET v=? WHERE k='task_baseline'", (stored,))
    with pytest.raises(MapError, match='task baseline could not be read'):
        cache.session_baseline(cfg)


def test_non_git_and_unborn_git_projects_do_not_get_an_invented_baseline(tmp_path):
    root, cfg = project(tmp_path, versioned=False)
    assert cache.session_baseline(cfg) is None
    assert cache.session_baseline(cfg, remember=True) is None
    assert not cfg.cache.exists()
    git(root,'init','--quiet')
    assert cache.session_baseline(cfg, remember=True) is None
    assert not cfg.cache.exists()


def test_brief_does_not_build_map_or_execute_project_and_records_session_start(tmp_path, monkeypatch, capsys):
    root, cfg = project(tmp_path)
    path = cfg.intent / 'policy.py'
    path.write_text('raise RuntimeError("must never execute the brief")\n'+path.read_text())
    def forbidden(*args, **kwargs):
        raise AssertionError('brief must not rebuild the map')
    monkeypatch.setattr(cli,'build',forbidden)
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert 1 <= len(lines) <= 10 and all(len(line) <= 100 for line in lines)
    assert 'no results yet' in '\n'.join(lines) and 'assumed / unconfirmed' in '\n'.join(lines)
    assert cache.session_baseline(cfg) == git(root,'rev-parse','HEAD')


def test_red_overflow_is_counted_and_cached_green_is_not_claimed_current(tmp_path, capsys):
    _, cfg = project(tmp_path, rules=15)
    result(cfg, messages=[f'wrong case {n}' for n in range(20)])
    cli.screen(cfg)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 10 and all(len(line) <= 100 for line in lines)
    assert '20 red (parse / last check)' in lines[0]
    assert 'more lines (12 red)' in lines[-1]
    assert 'No disagreement' not in '\n'.join(lines)
    result(cfg,verdict='ok')
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert 'green' not in output and 'No disagreement' not in output


def test_load_failure_remains_visible_even_without_a_current_rule_id(tmp_path, capsys):
    _, cfg = project(tmp_path)
    result(cfg, rule='__load__',kind='load',messages=['Skipped: declaration missing'])
    assert cli.screen(cfg) == 0
    assert 'last check load' in capsys.readouterr().out


def test_only_cited_owner_phrase_is_displayed_and_archive_bytes_are_unchanged(tmp_path, capsys):
    phrase = 'The fourth day stays refused.'
    root, cfg = project(tmp_path, source='owner RSource',quote=phrase)
    raw = b'Unrelated private fixture preface.\r\n'+phrase.encode()+b'\nOther unrelated fixture discussion.\n'
    store_request(root,raw,identifier='RSource')
    git(root,'add','.flowguard/requests'); git(root,'commit','--quiet','-m','fixture original words')
    result(cfg,messages=['days=4: expected False, actual True'])
    assert cli.screen(cfg) == 0
    output = capsys.readouterr().out
    assert phrase in output and 'RSource' in output
    assert 'Unrelated private fixture preface' not in output and 'Other unrelated' not in output
    assert (root/'.flowguard/requests/RSource.md').read_bytes() == raw
    summary = cache.scan(cfg)
    assert summary['rules']['R0']['quote'] == phrase


def test_forged_phrase_is_not_printed_as_owner_source(tmp_path, capsys):
    root, cfg = project(tmp_path,source='owner RSource',quote='A phrase absent from the original.')
    store_request(root,b'The fourth day stays refused.\n',identifier='RSource')
    git(root,'add','.flowguard/requests'); git(root,'commit','--quiet','-m','fixture original words')
    result(cfg,messages=['actual code violates the rule'])
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert 'owner quote unconfirmed' in output
    assert 'A phrase absent from the original.' not in output



def test_existing_cache_in_a_space_hash_and_unicode_path_is_read_normally(tmp_path, capsys):
    root, cfg = project(tmp_path)
    head = cache.session_baseline(cfg, remember=True)
    moved = root.rename(tmp_path / 'project # 空格')
    cfg = load_config(moved)
    assert cache.session_baseline(cfg) == head
    assert cli.screen(cfg) == 0
    assert head[:12] in capsys.readouterr().out


def test_interrupted_last_attempt_remains_an_unfinished_item(tmp_path, capsys):
    _, cfg = project(tmp_path)
    cache.session_baseline(cfg, remember=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as con, con:
        con.execute('INSERT INTO meta VALUES(?,?)', ('intent_attempt',json.dumps({'exit':2})))
    cli.screen(cfg)
    assert 'last check exit 2' in capsys.readouterr().out


def test_brief_drops_failed_readings_of_folders_norecursedirs_keeps_pytest_out_of(tmp_path, capsys):
    root, cfg = project(tmp_path)
    cache.session_baseline(cfg, remember=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS reading(test TEXT PRIMARY KEY, outcome TEXT, kind TEXT, reason TEXT, '
                    'phase TEXT, seconds REAL, stamp REAL)')
        for test in ('tests/legacy/test_old_binding.py', 'tests/test_current.py'):
            con.execute('INSERT INTO reading VALUES(?,?,?,?,?,?,?)', (test, 'failed', 'test', 'collection', 'collect', 0.0, 1.0))
    for test in ('tests/legacy/test_old_binding.py', 'tests/test_current.py'):
        (root / test).parent.mkdir(parents=True, exist_ok=True)
        (root / test).write_text('def test_value(): pass\n')
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert 'tests/legacy/test_old_binding.py' in output and 'tests/test_current.py' in output, output
    # The legacy folder is added to pytest's own list: pytest no longer collects it, so its old failure is gone.
    (root / 'pyproject.toml').write_text((root / 'pyproject.toml').read_text()
                                         + '\n[tool.pytest.ini_options]\nnorecursedirs = [".*", "node_modules", "legacy"]\n')
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert 'tests/legacy/test_old_binding.py' not in output and 'red last check test tests/test_current.py' in output, output
    from flowguard.intent import deps
    scope = deps.test_scope(load_config(root))
    assert not scope('tests/legacy/test_old_binding.py') and scope('tests/test_current.py')
