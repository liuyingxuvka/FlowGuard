"""Grey is "unverified", never "passed" (design 4.3).

- A grey intent item has its own pytest outcome: `U` with -q, `UNVERIFIED` with -v, `N unverified` in the
  summary; the exit status does not change, and no warning, skip or xfail is involved.
- An anchor or rule that the baseline code observes in the same context and the current code turns grey
  fails the run, with two ways out: restore the observation, or list a reason under `[unverified]` in
  `.flowguard/ledger.toml`.
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
        path.write_text(textwrap.dedent(text).lstrip())
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n')
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    return root


def _pytest(root, *options):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-p', 'no:cacheprovider', *options],
                            cwd=root, capture_output=True, text=True, timeout=180)
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


def test_a_new_write_that_loses_the_baseline_observation_fails_with_two_ways_out(tmp_path):
    root = _project(tmp_path / 'p', STANDING)
    policy = root / 'policy.py'
    policy.write_text(policy.read_text().replace('    return days <= 3', '    open("audit.log", "a").close()\n    return days <= 3'))
    result, text = _pytest(root, '-q')
    assert result.returncode == 1 and '2 passed' in text, text
    assert '未验证' not in text, text                 # the lost observation is red, not also listed as grey
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith('红  观察丢失 STANDING：'))
    assert 'policy.py:2 在 tests/test_policy.py::test_standing 里，基准代码能比较，现在是灰' in lines[index], lines[index]
    assert 'policy.py:3 open("audit.log", "a").close()：写文件 audit.log' in lines[index], lines[index]
    assert lines[index + 1].startswith('    恢复可观察：'), lines
    assert lines[index + 2].endswith('；还没有这个文件时先运行 python -m flowguard ledger init：'), lines
    assert lines[index + 3:index + 5] == ['    [unverified]', '    STANDING = ' + ledger._quote(ledger.PLACEHOLDER_UNVERIFIED)], lines
    # A reason too short is red in the ledger's own check; a real reason keeps it unverified, not failed.
    (root / ledger.LEDGER).parent.mkdir(exist_ok=True)
    (root / ledger.LEDGER).write_text('[unverified]\nSTANDING = "不再回放"\n')
    short, text = _pytest(root, '-q')
    assert short.returncode == 1 and '[unverified] 里的 "STANDING"：理由只有' in text, text
    (root / ledger.LEDGER).write_text('[unverified]\nSTANDING = ' + ledger._quote(REASON) + '\n')
    listed, text = _pytest(root, '-q')
    assert listed.returncode == 0, text
    assert '观察丢失' not in text and f'STANDING（policy.py:2）：已登记不回放：{REASON}' in text, text


def test_a_grey_that_the_baseline_shares_is_not_a_lost_observation(tmp_path):
    files = dict(STANDING, **{'policy.py': textwrap.dedent(STANDING['policy.py']).replace(
        '    return days <= 3', '    open("audit.log", "a").close()\n    return days <= 3')})
    root = _project(tmp_path / 'p', files)
    policy = root / 'policy.py'
    policy.write_text(policy.read_text().replace('days <= 3', 'days <= 4'))
    result, text = _pytest(root, '-q')
    assert result.returncode == 0 and '观察丢失' not in text, text
    assert '未验证' in text and '写文件 audit.log' in text, text


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
    (root / 'tests/intent/limit.py').write_text((root / 'tests/intent/limit.py').read_text().replace(
        'owner R1: 最多三天', 'owner R1: 宽限期最多三天'))
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'owner words')
    checked, text = _cli(root, 'check', '--all')
    assert checked.returncode == 1, text
    assert '红  LIMIT_RULE：规则有主人原话出处（R1），现在是灰（未验证）：module initialization of json is not proved pure' in text, text
    assert f'[unverified] 段写一句理由：LIMIT_RULE = ' in text, text
    (root / ledger.LEDGER).parent.mkdir(exist_ok=True)
    (root / ledger.LEDGER).write_text('[unverified]\nLIMIT_RULE = ' + ledger._quote(
        '这个判断读 json 配置，模块导入证明不了纯；由 test_limit 和回归行守住') + '\n')
    listed, text = _cli(root, 'check', '--all')
    assert listed.returncode == 0, text
    assert '规则有主人原话出处' not in text, text
