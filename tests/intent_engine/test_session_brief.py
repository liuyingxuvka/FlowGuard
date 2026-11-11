"""Task memory stays in existing SQLite; the brief never pretends a cache is fresh."""
from contextlib import closing
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

import pytest

from flowguard import __version__
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


VERSION = '.'.join(__version__.split('.')[:2])


def brief_head(baseline, note=''):
    """The brief's first line: the version, the baseline and its note (design 4.7)."""
    return f'FlowGuard {VERSION} brief, baseline {baseline[:12]}' + (f'; {note}' if note else '')


def rules_toml(root, rules):
    """`.flowguard/rules.toml` with these (id, text, source) rules."""
    (root / '.flowguard').mkdir(exist_ok=True)
    (root / '.flowguard/rules.toml').write_text(''.join(f'[rule.{identifier}]\ntext = "{text}"\nsource = \'{source}\'\n\n'
                                                       for identifier, text, source in rules), encoding='utf-8')


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
    now = git(root, 'rev-parse', 'HEAD')
    assert cache.remember_baseline(cfg, new_task=True) == (now, (
        f'baseline: new task from HEAD {now[:12]} (was {head[:12]}, 1 commit before HEAD: those changes are no longer '
        f'compared; compare them once with python -m pytest --flowguard-base {head[:12]})'))
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
    # The note says why the baseline is where it is, on the first line (design 4.7: the baseline is one line).
    assert lines == [brief_head(start, 'task start, 2 commits before HEAD; next task: python -m flowguard new-task')], lines
    assert cache.session_baseline(cfg) == start             # what the task changed stays reported
    assert cli.main(['--root', str(root), 'new-task']) == 0
    head = git(root, 'rev-parse', 'HEAD')
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == brief_head(head, (
        f'new task from HEAD {head[:12]} (was {start[:12]}, 2 commits before HEAD: those changes are no longer '
        f'compared; compare them once with python -m pytest --flowguard-base {start[:12]})')), lines
    assert cache.session_baseline(cfg) == head
    # Run again at the same commit (after a loss of context), it replaces nothing.
    assert cli.main(['--root', str(root), 'new-task']) == 0
    assert capsys.readouterr().out.splitlines()[0] == brief_head(head, f'new task from HEAD {head[:12]}')
    # A recorded commit HEAD does not descend from (another branch, rewritten history) is not this task's start.
    git(root, 'checkout', '--quiet', '-b', 'other', start)
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == brief_head(start, f'recorded {head[:12]} is not an ancestor of HEAD; the task starts at HEAD'), lines
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
    rules_toml(root, [('limit', 'The fourth day stays refused.', 'doc SPEC.txt "The fourth day stays refused."')])
    def forbidden(*args, **kwargs):
        raise AssertionError('brief must not rebuild the map')
    monkeypatch.setattr(cli,'build',forbidden)
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [brief_head(git(root, 'rev-parse', 'HEAD')), 'rule.limit: The fourth day stays refused.'], lines
    assert cache.session_baseline(cfg) == git(root,'rev-parse','HEAD')


def test_red_overflow_is_counted_and_cached_green_is_not_claimed_current(tmp_path, capsys):
    _, cfg = project(tmp_path, rules=15)
    result(cfg, messages=[f'wrong case {n}' for n in range(20)])
    cli.screen(cfg)
    lines = capsys.readouterr().out.splitlines()
    # The brief names no intent rule: the last check's reds are one count, with the command that lists them.
    assert lines[1:] == ['20 still red: python -m flowguard show --last'], lines
    assert 'No disagreement' not in '\n'.join(lines)
    result(cfg,verdict='ok')
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert 'green' not in output and 'No disagreement' not in output


def test_load_failure_remains_visible_even_without_a_current_rule_id(tmp_path, capsys):
    _, cfg = project(tmp_path)
    result(cfg, rule='__load__',kind='load',messages=['Skipped: declaration missing'])
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[-1] == '1 still red: python -m flowguard show --last'


def test_only_the_rule_text_is_displayed_never_archive_words_and_archive_bytes_are_unchanged(tmp_path, capsys):
    phrase = 'The fourth day stays refused.'
    root, cfg = project(tmp_path, source='owner RSource',quote=phrase)
    raw = b'Unrelated private fixture preface.\r\n'+phrase.encode()+b'\nOther unrelated fixture discussion.\n'
    store_request(root,raw,identifier='RSource')
    rules_toml(root, [('fourth-day', 'A fourth day is refused.', f'RSource "{phrase}"')])
    git(root,'add','.flowguard'); git(root,'commit','--quiet','-m','fixture original words')
    result(cfg,messages=['days=4: expected False, actual True'])
    assert cli.screen(cfg) == 0
    output = capsys.readouterr().out
    assert 'rule.fourth-day: A fourth day is refused.' in output and phrase not in output
    assert 'Unrelated private fixture preface' not in output and 'Other unrelated' not in output
    assert (root/'.flowguard/requests/RSource.md').read_bytes() == raw
    summary = cache.scan(cfg)
    assert summary['rules']['R0']['quote'] == phrase


def test_forged_phrase_is_not_printed_as_owner_source(tmp_path, capsys):
    root, cfg = project(tmp_path,source='owner RSource',quote='A phrase absent from the original.')
    store_request(root,b'The fourth day stays refused.\n',identifier='RSource')
    rules_toml(root, [('fourth-day', 'A fourth day is refused.', 'RSource "A phrase absent from the original."')])
    git(root,'add','.flowguard'); git(root,'commit','--quiet','-m','fixture original words')
    result(cfg,messages=['actual code violates the rule'])
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert 'A phrase absent from the original.' not in output
    assert cli.show(cfg, 'rule.fourth-day') == 0
    assert '(does not hold: "A phrase absent from the original." is not in RSource -> quote the stored words exactly)' \
        in capsys.readouterr().out



def test_existing_cache_in_a_space_hash_and_unicode_path_is_read_normally(tmp_path, capsys):
    root, cfg = project(tmp_path)
    head = cache.session_baseline(cfg, remember=True)
    moved = root.rename(tmp_path / 'project # 空格')
    cfg = load_config(moved)
    assert cache.session_baseline(cfg) == head
    assert cli.screen(cfg) == 0
    assert head[:12] in capsys.readouterr().out


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
    assert output.splitlines()[-1] == '2 still red: python -m flowguard show --last', output
    # The legacy folder is added to pytest's own list: pytest no longer collects it, so its old failure is gone.
    (root / 'pyproject.toml').write_text((root / 'pyproject.toml').read_text()
                                         + '\n[tool.pytest.ini_options]\nnorecursedirs = [".*", "node_modules", "legacy"]\n')
    cli.screen(cfg)
    output = capsys.readouterr().out
    assert output.splitlines()[-1] == '1 still red: python -m flowguard show --last', output
    from flowguard.intent import deps
    scope = deps.test_scope(load_config(root))
    assert not scope('tests/legacy/test_old_binding.py') and scope('tests/test_current.py')


SOURCE = str(Path(__file__).resolve().parents[2])


def _run(root, *arguments, pytest_run=False):
    """`python -m flowguard ...` or, with `pytest_run`, ordinary pytest in `root`, this checkout first on the path."""
    from tests.intent_engine._cli_fixture import display_text
    call = ('import pytest; raise SystemExit(pytest.main(sys.argv[1:]))' if pytest_run else
            'from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))')
    options = ('-q', '-p', 'no:cacheprovider') if pytest_run else ('--root', str(root))
    result = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv.pop(1)); ' + call, SOURCE,
                             *options, *arguments], cwd=root, capture_output=True, text=True, timeout=180)
    return result.returncode, display_text(result)


def _plain(tmp_path):
    """A project as the README starts one: `flowguard init`, a commit, then ordinary pytest."""
    root = tmp_path / 'plain'
    root.mkdir()
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 3\n')
    (root / 'tests').mkdir()
    (root / 'tests/test_app.py').write_text('from app import eligible\n\n\ndef test_limit():\n'
                                           '    assert eligible(3) in (True, False) and eligible(4) in (True, False)\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n')
    git(root, 'init', '--quiet', '-b', 'main')
    git(root, 'config', 'user.name', 'FlowGuard test fixture')
    git(root, 'config', 'user.email', 'flowguard-fixture@example.invalid')
    code, text = _run(root, 'init')
    assert code == 0, text
    git(root, 'add', '.')
    git(root, 'commit', '--quiet', '-m', 'fixture baseline')
    return root, load_config(root)


def _reported_title(text, title, *, timed=True):
    """The first FlowGuard line keeps the exact baseline and mandatory own timer."""
    headers = [line for line in text.splitlines() if line.startswith(('FlowGuard（', 'FlowGuard('))]
    assert len(headers) == 1, text
    if not timed:  # CLI header unification is a later stage; keep its exact baseline text now.
        assert headers == [title], text
        return
    match = re.fullmatch(re.escape(title) + r'; ([0-9]+(?:\.[0-9]+)?) s', headers[0])
    assert match is not None, text
    seconds = float(match.group(1))
    assert math.isfinite(seconds) and seconds >= 0, text


def test_the_first_pytest_run_records_the_task_baseline_and_commits_during_the_task_keep_it(tmp_path):
    root, cfg = _plain(tmp_path)
    start = git(root, 'rev-parse', 'HEAD')
    code, text = _run(root, '--flowguard-base=HEAD', pytest_run=True)
    assert code == 0 and cache.task_baseline(cfg) == (start, 'HEAD'), text    # an explicit baseline records nothing
    _reported_title(text, f'FlowGuard（since --flowguard-base {start[:7]}）')
    code, text = _run(root, pytest_run=True)
    # Even an unchanged first run prints its baseline and own timer; HEAD is recorded.
    assert code == 0, text
    _reported_title(text, f'FlowGuard（since task start {start[:7]}）')
    assert cache.task_baseline(cfg) == (start, 'task')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 4\n')
    git(root, 'commit', '--quiet', '-am', 'fixture change committed during the task')
    code, text = _run(root, pytest_run=True)
    assert code == 0, text
    lines = text.splitlines()
    # not HEAD against HEAD; the commit since the start is named, with the next task's step
    _reported_title(text, f'FlowGuard（since task start {start[:7]}, commits before HEAD: 1; first run python -m flowguard new-task for a new task)')
    assert any(line.startswith('changed: LIMIT（app.py:2）') and 'days=4; function result False → True' in line for line in lines), text
    assert cache.task_baseline(cfg) == (start, 'task')
    # The next task starts at HEAD: the committed change is no longer this task's.
    code, text = _run(root, 'new-task')
    assert code == 0, text
    head = git(root, 'rev-parse', 'HEAD')
    assert cache.task_baseline(cfg) == (head, 'task') and head != start
    code, text = _run(root, pytest_run=True)
    assert code == 0, text
    _reported_title(text, f'FlowGuard（since task start {head[:7]}）')
    # A fresh clone (an empty cache, as in CI) compares with its HEAD on its first run and changes nothing.
    clone = tmp_path / 'clone'
    subprocess.run(['git', 'clone', '--quiet', str(root), str(clone)], check=True, capture_output=True, timeout=60)
    assert cache.task_baseline(load_config(clone)) == (head, 'HEAD')
    code, text = _run(clone, pytest_run=True)
    assert code == 0, text
    _reported_title(text, f'FlowGuard（since task start {head[:7]}）')
    assert cache.task_baseline(load_config(clone)) == (head, 'task')


def _folder(tmp_path, name):
    (tmp_path / name).mkdir()
    return tmp_path / name


def test_check_and_check_static_record_the_task_baseline_unless_base_names_one(tmp_path):
    root, cfg = project(tmp_path, rules=0)
    head = git(root, 'rev-parse', 'HEAD')
    for command in (('check', '--static', '--base', 'HEAD'), ('check', '--base', 'HEAD')):
        code, text = _run(root, *command)
        assert code == 0 and cache.task_baseline(cfg) == (head, 'HEAD'), (command, text)     # --base records nothing
    code, text = _run(root, 'check', '--static')
    assert code == 0 and cache.task_baseline(cfg) == (head, 'task'), text
    root, cfg = project(_folder(tmp_path, 'second'), rules=0)
    code, text = _run(root, 'check')
    assert code == 0 and cache.task_baseline(cfg) == (git(root, 'rev-parse', 'HEAD'), 'task'), text
    # Without a commit there is no HEAD to record.
    root, cfg = project(_folder(tmp_path, 'unborn'), versioned=False, rules=0)
    git(root, 'init', '--quiet')
    code, text = _run(root, 'check', '--static')
    assert code == 0 and cache.task_baseline(cfg) == (None, None), text


def test_a_detached_head_or_a_collect_only_session_records_no_task_baseline(tmp_path):
    """A tag or an older commit checked out (a bisect step, a CI checkout) and IDE test discovery are no task's first
    run: recording there would make every later commit on the branch this task's change."""
    root, cfg = _plain(tmp_path)
    older = git(root, 'rev-parse', 'HEAD')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 4\n')
    git(root, 'commit', '--quiet', '-am', 'fixture change on main')
    head = git(root, 'rev-parse', 'HEAD')
    git(root, 'checkout', '--quiet', '--detach', older)
    for arguments in ((), ('--collect-only',)):
        code, text = _run(root, *arguments, pytest_run=True)
        assert code == 0 and cache.task_baseline(cfg) == (older, 'HEAD'), (arguments, text)
    code, text = _run(root, 'check', '--static')
    assert code == 0 and cache.task_baseline(cfg) == (older, 'HEAD'), text
    git(root, 'checkout', '--quiet', 'main')
    code, text = _run(root, '--collect-only', pytest_run=True)
    assert code == 0 and cache.task_baseline(cfg) == (head, 'HEAD'), text        # discovery on the branch neither
    code, text = _run(root, pytest_run=True)
    assert code == 0 and cache.task_baseline(cfg) == (head, 'task'), text
    _reported_title(text, f'FlowGuard（since task start {head[:7]}）')


def test_runs_on_a_commit_outside_the_task_never_move_its_baseline(tmp_path):
    """IDE test discovery, the tests or a check on a release branch or an older commit compare with the task start
    and leave it recorded: back on the task's branch its committed change is reported, against the task start."""
    root, cfg = _plain(tmp_path)
    older = git(root, 'rev-parse', 'HEAD')
    git(root, 'checkout', '--quiet', '-b', 'release')
    (root / 'RELEASE.txt').write_text('a release branch forked before the task\n')
    git(root, 'add', 'RELEASE.txt')
    git(root, 'commit', '--quiet', '-m', 'fixture release commit')
    git(root, 'checkout', '--quiet', 'main')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 5\n')
    git(root, 'commit', '--quiet', '-am', 'fixture change of the previous task')
    code, text = _run(root, 'new-task')
    assert code == 0, text
    start = git(root, 'rev-parse', 'HEAD')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 4\n')
    git(root, 'commit', '--quiet', '-am', 'fixture change committed during the task')

    def reported_against_the_task_start():
        code, text = _run(root, pytest_run=True)
        lines = text.splitlines()
        assert code == 0, text
        _reported_title(text, f'FlowGuard（since task start {start[:7]}, commits before HEAD: 1; first run python -m flowguard new-task for a new task)')
        # Only 3 and 4 were really called: changing <=5 to <=4 changes neither result.
        assert not any(line.startswith('changed: ') for line in lines), text
        assert cache.task_baseline(cfg) == (start, 'task')

    reported_against_the_task_start()
    runs = {'release': [('--collect-only',), (), ('check', '--static'), ('check',)], older: [()]}
    for commit, arguments in runs.items():
        git(root, 'checkout', '--quiet', commit)        # the start is not an ancestor of HEAD here
        for argument in arguments:
            code, text = _run(root, *argument, pytest_run=argument[:1] != ('check',))
            assert code == 0 and cache.task_baseline(cfg) == (start, 'task'), (commit, argument, text)
        git(root, 'checkout', '--quiet', 'main')
        reported_against_the_task_start()
    # The brief moves it there and says why; the next task starts with new-task.
    git(root, 'checkout', '--quiet', 'release')
    code, text = _run(root)
    assert code == 0 and 'is not an ancestor of HEAD; the task starts at HEAD' in text, text
    assert cache.task_baseline(cfg) == (git(root, 'rev-parse', 'HEAD'), 'task')


def test_the_brief_on_a_detached_head_neither_moves_nor_records_the_task_baseline(tmp_path, capsys):
    """A tag or an older commit looked at during a task is no task's start; new-task stays the explicit way there."""
    root, cfg = project(tmp_path)
    branch, first = git(root, 'symbolic-ref', '--short', 'HEAD'), git(root, 'rev-parse', 'HEAD')

    def brief(**options):
        assert cli.screen(cfg, **options) == 0
        return capsys.readouterr().out.splitlines()[0].partition('; ')[2]

    detached = 'HEAD is detached, so the brief records nothing ({}); python -m flowguard new-task starts a task here'
    git(root, 'checkout', '--quiet', '--detach')
    assert brief() == detached.format('HEAD stands in') and cache.task_baseline(cfg) == (first, 'HEAD')
    assert brief(new_task=True) == f'new task from HEAD {first[:12]}' and cache.task_baseline(cfg) == (first, 'task')
    git(root, 'checkout', '--quiet', branch)
    for days in (4, 5):
        (root / 'app.py').write_text(f'def eligible(days: int): return days <= {days}\n')
        git(root, 'commit', '--quiet', '-am', f'fixture change {days}')
    start = git(root, 'rev-parse', 'HEAD~1')
    git(root, 'checkout', '--quiet', '--detach', 'HEAD~1')
    brief(new_task=True)                                    # the task starts at the first change
    git(root, 'checkout', '--quiet', '--detach', first)     # HEAD does not descend from the start here
    assert brief() == detached.format(f'the task baseline stays at {start[:12]}, which HEAD does not descend from'), start
    assert cache.task_baseline(cfg) == (start, 'task')
    git(root, 'checkout', '--quiet', '--detach', branch)
    assert brief() == detached.format(f'the task baseline stays at {start[:12]}, 1 commit before HEAD')
    git(root, 'checkout', '--quiet', branch)
    assert brief() == 'task start, 1 commit before HEAD; next task: python -m flowguard new-task'
    assert cache.task_baseline(cfg) == (start, 'task')


_HANDLER = 'def parse(text):\n    try:\n        return int(text)\n    except ValueError:\n        return 0\n'


def _ledgered(tmp_path):
    """`_plain` with a fallback ledger, so a new handler is red in pytest, `check` and `check --static` alike."""
    root, cfg = _plain(tmp_path)
    code, text = _run(root, 'ledger', 'init')
    assert code == 0, text
    git(root, 'add', '.')
    git(root, 'commit', '--quiet', '-m', 'fixture ledger')
    return root, cfg


_RUNS = (((), True), (('check', '--static'), False), (('check',), False))


def test_the_title_of_every_run_says_how_far_the_task_start_lies_before_head(tmp_path):
    """A task start that commits have moved past (an agent that never runs new-task, a 4.1 rules block) is named
    with its distance and the next task's step, so earlier tasks' changes are not taken for this one's."""
    root, cfg = _ledgered(tmp_path)
    start = git(root, 'rev-parse', 'HEAD')
    code, text = _run(root, 'check', '--static')
    assert code == 0 and cache.task_baseline(cfg) == (start, 'task'), text
    for days in (4, 5):
        (root / 'app.py').write_text(f'# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= {days}\n')
        git(root, 'commit', '--quiet', '-am', f'fixture task {days}')
    (root / 'parse.py').write_text(_HANDLER)
    title = f'FlowGuard（since task start {start[:7]}, commits before HEAD: 2; first run python -m flowguard new-task for a new task)'
    for arguments, pytest_run in _RUNS:
        code, text = _run(root, *arguments, pytest_run=pytest_run)
        assert code == 1, (arguments, text)
        _reported_title(text, title, timed=pytest_run)
    code, text = _run(root, 'new-task')
    head = git(root, 'rev-parse', 'HEAD')
    assert code == 0 and cache.task_baseline(cfg) == (head, 'task'), text
    for arguments, pytest_run in _RUNS:
        code, text = _run(root, *arguments, pytest_run=pytest_run)
        assert code == 1, (arguments, text)
        _reported_title(text, f'FlowGuard（since task start {head[:7]}）', timed=pytest_run)


def test_check_and_check_static_title_head_standing_in_on_a_detached_head_as_pytest_does(tmp_path):
    root, cfg = _ledgered(tmp_path)
    head = git(root, 'rev-parse', 'HEAD')
    git(root, 'checkout', '--quiet', '--detach')
    (root / 'parse.py').write_text(_HANDLER)
    for arguments, pytest_run in _RUNS:
        code, text = _run(root, *arguments, pytest_run=pytest_run)
        assert code == 1, (arguments, text)
        _reported_title(text, f'FlowGuard（since HEAD {head[:7]}）', timed=pytest_run)
        assert cache.task_baseline(cfg) == (head, 'HEAD'), arguments          # nothing recorded: HEAD stands in


def test_a_recorded_task_start_this_repository_lacks_is_named_and_compares_nothing(tmp_path):
    """A shallow clone, history rewritten and collected, or a cache another clone left: no run compares silently
    with nothing, nor stops on Git's error; the brief or new-task starts the task at HEAD."""
    from flowguard.intent import vitest
    root, cfg = _plain(tmp_path)
    code, text = _run(root, pytest_run=True)
    assert code == 0 and cache.task_baseline(cfg)[1] == 'task', text
    gone = 'b' * 40
    cache._record_baseline(cfg, gone)
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 4\n')
    title = f'FlowGuard(recorded task baseline {gone[:7]} is not in this repository: old/new comparison is off; first run python -m flowguard new-task)'
    for arguments, pytest_run in _RUNS:
        code, text = _run(root, *arguments, pytest_run=pytest_run)
        assert code == 0 and 'changed: ' not in text, (arguments, text)
        _reported_title(text, title, timed=pytest_run)
        assert cache.task_baseline(cfg) == (gone, 'missing') and cache.session_baseline(cfg) is None, arguments
    prepared = vitest.prepare(root)
    seconds = prepared.pop('seconds')
    assert type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0
    assert prepared == dict(status='off', reason=f'recorded task baseline {gone[:7]} is not in this repository: execution comparison is off; '
                                                'first run python -m flowguard new-task')
    code, text = _run(root)
    assert code == 0 and text.splitlines()[0].endswith(f'; recorded {gone[:12]} is not in this repository; the task starts at HEAD'), text
    head = git(root, 'rev-parse', 'HEAD')
    assert cache.task_baseline(cfg) == (head, 'task')
    code, text = _run(root, pytest_run=True)
    assert code == 0 and 'changed: LIMIT（app.py:2）' in text, text
    _reported_title(text, f'FlowGuard（since task start {head[:7]}）')


def test_ledger_check_names_a_recorded_task_start_this_repository_lacks(tmp_path):
    """Old ledger entries are vouched for by `ledger init`'s record or the task start's ledger. A clone without the
    record (a teammate ran `ledger init`) and without the start commit says which commit it lacks and the next step,
    as the title of pytest, `check` and `check --static` does, instead of only "the baseline has no ledger"."""
    from flowguard.intent import ledger
    root, cfg = _plain(tmp_path)
    (root / 'parse.py').write_text(_HANDLER)
    code, text = _run(root, 'ledger', 'init')
    assert code == 0, text
    git(root, 'add', '.')
    git(root, 'commit', '--quiet', '-m', 'fixture ledger')
    (cfg.cache / ledger.INIT_RECORD).unlink()
    gone = 'b' * 40
    cache._record_baseline(cfg, gone)
    title = f'FlowGuard(recorded task baseline {gone[:7]} is not in this repository: old/new comparison is off; first run python -m flowguard new-task)'
    code, text = _run(root, 'ledger', 'check')
    assert code == 0 and text.splitlines() == [
        title, 'FlowGuard fallback ledger: 1 entries (1 legacy), 1 code handlers; 0 red, 1 unverified',
        'not checked: 1 legacy entries are unverified: the baseline contains neither a ledger nor a ledger init record'], text
    (root / ledger.LEDGER).unlink()                 # whether the start had a ledger is not known either
    code, text = _run(root, 'ledger', 'check')
    assert code == 0 and text.splitlines()[0] == title and 'no .flowguard/ledger.toml' in text, text
    git(root, 'checkout', '--quiet', '--', ledger.LEDGER)
    assert _run(root, 'new-task')[0] == 0           # the task starts at HEAD, whose ledger vouches for the old entry
    code, text = _run(root, 'ledger', 'check')
    assert code == 0 and text.splitlines() == ['FlowGuard fallback ledger: 1 entries (1 legacy), 1 code handlers; 0 red, 0 unverified'], text


def test_new_task_says_to_compare_the_dropped_commits_with_the_command_the_project_runs(tmp_path, capsys):
    # Round 22 F3: in a TS project (its tests run with npm, pytest finds no test of its own) new-task told the AI
    # to compare the commits it stops comparing with pytest, which runs nothing there; check --static does.
    root = tmp_path / 'web'
    files = {'package.json': '{"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n',
             'src/limit.ts': 'export function limit(days: number) { return days <= 3; }\n', '.gitignore': '.flowguard/cache/\n',
             # init writes FlowGuard's own sentinel into every project; it is not a test of the project
             'tests/test_flowguard_intent.py': cli.SENTINEL}
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    git(root, 'init', '--quiet')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '--quiet', '-m', 'start')
    cfg = load_config(root)
    start = git(root, 'rev-parse', 'HEAD')
    assert cli.main(['--root', str(root), 'new-task']) == 0
    (root / 'src/limit.ts').write_text('export function limit(days: number) { return days <= 4; }\n')
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '--quiet', '-am', 'change')
    capsys.readouterr()
    assert cli.main(['--root', str(root), 'new-task']) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith(
        f'compare them once with python -m flowguard check --static --base {start[:12]})')
    # A project that also has Python tests of its own runs pytest: the comparison stays pytest's.
    (root / 'tests/test_limit.py').write_text('def test_limit():\n    assert True\n')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '--quiet', '-m', 'python test')
    head = git(root, 'rev-parse', 'HEAD')
    assert cli.main(['--root', str(root), 'new-task']) == 0 and cache.session_baseline(cfg) == head
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '--quiet', '--allow-empty', '-m', 'next')
    capsys.readouterr()
    assert cli.main(['--root', str(root), 'new-task']) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith(f'compare them once with python -m pytest --flowguard-base {head[:12]})')


# ---- the 4.3 brief: rules.toml, known.toml and what the last run left (design 4.7, at most 8 lines) -------------

def _known(root, entries):
    (root / '.flowguard').mkdir(exist_ok=True)
    (root / '.flowguard/known.toml').write_text(''.join(
        f'[known.{identifier}]\nsites = ["app.py:eligible"]\nwhy = "{why}"\nact = "{act}"\n'
        + (f'ask = "{why}?"\n' if act == 'ask' else '') + (f'asked = "{asked}"\n' if asked else '') + '\n'
        for identifier, act, why, asked in entries), encoding='utf-8')


def test_the_brief_lists_the_first_rules_in_file_order_and_counts_the_rest(tmp_path, capsys):
    root, cfg = project(tmp_path, rules=0)
    rules_toml(root, [(f'r{n}', f'Rule number {n}.', 'doc SPEC.txt "The fourth day stays refused."') for n in range(6)])
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:] == ['rule.r0: Rule number 0.', 'rule.r1: Rule number 1.', 'rule.r2: Rule number 2.',
                         'rule.r3: Rule number 3; +2 more: python -m flowguard show rules'], lines


def test_the_brief_names_what_the_owner_must_decide_first_and_never_an_ignored_entry(tmp_path, capsys):
    root, cfg = project(tmp_path, rules=0)
    _known(root, [('deferred', 'leave', 'a deferred matter', ''), ('asked', 'ask', 'an asked question', '2026-11-12'),
                  ('noise', 'ignore', 'a false structure finding', ''), ('wrong', 'fix', 'a clear error', ''),
                  ('open', 'ask', 'an open question', '')])
    (root / '.flowguard/known.toml').write_text((root / '.flowguard/known.toml').read_text().replace(
        'why = "a false structure finding"', 'why = "a false structure finding"\nfinding = "delete:Order"'), encoding='utf-8')
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    # ask (not asked yet), then fix, then leave, then ask (asked); two at most, the rest counted.
    assert lines[1:] == ['known.open: ask owner: an open question?',
                         'known.wrong: fix: a clear error; +2 more: python -m flowguard show rules'], lines
    _known(root, [('asked', 'ask', 'an asked question', '2026-11-12'), ('deferred', 'leave', 'a deferred matter', '')])
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[1:] == ['known.deferred: leave it: a deferred matter',
                                                       'known.asked: asked on 2026-11-12; leave it until the owner answers: an asked question?']


def test_the_brief_stays_within_eight_lines_with_every_part_present(tmp_path, capsys):
    root, cfg = project(tmp_path, rules=1)
    rules_toml(root, [(f'r{n}', f'Rule number {n}.', 'doc SPEC.txt "The fourth day stays refused."') for n in range(9)])
    _known(root, [(f'k{n}', 'ask', f'question {n}', '') for n in range(4)])
    (root / '.flowguard/rules.toml').write_text((root / '.flowguard/rules.toml').read_text() + '[rule.bad]\ntext = "x"\n',
                                                encoding='utf-8')
    result(cfg, messages=['days=4: expected False, actual True'])
    assert cli.screen(cfg) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 8, lines
    assert [line.partition(':')[0] for line in lines[1:5]] == ['rule.r0', 'rule.r1', 'rule.r2', 'rule.r3']
    assert lines[4].endswith('; +5 more: python -m flowguard show rules') and lines[6].endswith('; +2 more: python -m flowguard show rules')
    assert lines[7] == ('1 still red: python -m flowguard show --last; 1 invalid entries in .flowguard/rules.toml or '
                        'known.toml: python -m flowguard show rules'), lines


def _last_run(cfg, baseline, lines):
    from dataclasses import asdict
    from flowguard.intent.signals import Line
    from flowguard.structure.store import connect
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        cache.save_last(con, dict(run='check --static', baseline=baseline, baseline_kind='task',
                                  lines=[asdict(Line(*line)) for line in lines]))


def test_new_task_says_which_reds_of_the_previous_task_are_before_now(tmp_path, capsys):
    root, cfg = project(tmp_path, rules=0)
    (root / 'other.py').write_text('def write(): pass\n')
    git(root, 'add', '.'); git(root, 'commit', '--quiet', '-m', 'fixture other file')
    start = cache.session_baseline(cfg, remember=True)
    _last_run(cfg, start, [('red', 'pair:Order.total>Order.tax', 'app:eligible', 'together Order.total: ...', 'also write', ('app.py:eligible',)),
                    ('red', 'values:Order.status', 'other:write', 'values Order.status: ...', 'use one', ('other.py:write',)),
                    ('red', 'rules-entry:rule.x', '', 'rule.x: ...', 'correct it', ('.flowguard/rules.toml:rule.x',)),
                    ('before', 'pair:Order.a>Order.b', 'app:eligible', 'together Order.a', 'leave it', ('app.py:eligible',))])
    # Within the task the last run's reds still stand.
    assert cli.screen(cfg) == 0
    assert capsys.readouterr().out.splitlines()[-1] == '2 still red: python -m flowguard show --last'
    # The next task's baseline makes a red whose files are clean against HEAD old: before; a dirty one stays red.
    (root / 'app.py').write_text('def eligible(days: int): return days <= 3  # committed\n')
    git(root, 'commit', '--quiet', '-am', 'the previous task')
    (root / 'other.py').write_text('def write(): return 1\n')
    assert cli.main(['--root', str(root), 'new-task']) == 0
    moved = ('1 red from the previous task are now before; 1 still red: python -m flowguard show --last')
    assert capsys.readouterr().out.splitlines()[-1] == moved
    # The brief says so until the next run records its own lines (a brief after a loss of context, new-task again).
    assert cli.screen(cfg) == 0 and capsys.readouterr().out.splitlines()[-1] == moved
    assert cli.main(['--root', str(root), 'new-task']) == 0 and capsys.readouterr().out.splitlines()[-1] == moved
    _last_run(cfg, cache.session_baseline(cfg), [('red', 'values:Order.status', 'other:write', 'values Order.status: ...',
                                                  'use one', ('other.py:write',))])
    assert cli.screen(cfg) == 0 and capsys.readouterr().out.splitlines()[-1] == '1 still red: python -m flowguard show --last'


def test_new_task_keeps_every_red_no_baseline_moves_and_one_without_places(tmp_path, capsys):
    root, cfg = project(tmp_path, rules=0)
    start = cache.session_baseline(cfg, remember=True)
    _last_run(cfg, start, [
        ('red', 'pair:Order.total>Order.tax', 'app:eligible', 'together Order.total: ...', 'also write', ('app.py:eligible',)),
        ('red', 'ledger:app.py:eligible:Exception', '', 'ledger app.py: ...', 'add the entry', ()),     # no places
        ('red', 'input:comment', '', 'comment app.py:1: ...', 'correct it', ('app.py:1',)),           # no baseline moves it
        ('red', 'rule:LIMIT', 'LIMIT', 'rule LIMIT: ...', 'fix', ('tests/intent/policy.py:LIMIT',)),  # the intent cache's
        ('red', 'rules-entry:rule.x', '', 'rule.x: ...', 'correct it', ('.flowguard/rules.toml:rule.x',)),   # the catalog's
        ('red', 'input:load', '', 'load tests/intent/policy.py:3: ...', 'correct it', ('tests/intent/policy.py:3',))])
    (root / 'app.py').write_text('def eligible(days: int): return days <= 3  # committed\n')
    git(root, 'commit', '--quiet', '-am', 'the previous task')
    assert cli.main(['--root', str(root), 'new-task']) == 0
    # The pair's file is clean: before. The ledger red names no place and the comment's red is no baseline's: still
    # red. The rule's red, the invalid entry and the load error are counted where they are read now (none here).
    assert capsys.readouterr().out.splitlines()[-1] == (
        '1 red from the previous task are now before; 2 still red: python -m flowguard show --last')
