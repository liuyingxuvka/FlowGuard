"""The ordinary AI path stays short, honest and executable on a fresh project."""
import ast
from pathlib import Path
import uuid
import tomllib

import pytest

from tests.intent_engine import _cli_fixture as cli_fixture

from flowguard.intent import cache, cli
from flowguard.intent.config import load_config
from tests.intent_engine._source_fixture import annotate


def project(tmp_path, wrong=False):
    root = tmp_path / ('p' + uuid.uuid4().hex)
    root.mkdir()
    name = root.name
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (root / 'policy.txt').write_text('At most three days.\n')
    (root / (name + '.py')).write_text(annotate('def accept(days):\n    return days <= ' + ('4' if wrong else '3') + '\n','accept','LIMIT',{'days':'int'}))
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    (folder / 'policy.py').write_text(f'''from flowguard.intent import rule,row
@rule('LIMIT',decides='acceptance',fields={{'days':int}},anchor='LIMIT',source='doc policy.txt "At most three days."')
def LIMIT(days):
    """The fourth day must stay refused across later sessions."""
    return days <= 3
LIMIT.rows(row(days=4,expect=False,why='a corrected fourth-day regression'))
''')
    return root, load_config(root)


def test_a_fresh_screen_lists_rules_without_executing_them(tmp_path, capsys):
    root, cfg = project(tmp_path)
    path = cfg.intent / 'policy.py'
    path.write_text('raise RuntimeError("screen must not execute this")\n' + path.read_text())
    assert cli.screen(cfg) == 0
    text = capsys.readouterr().out
    assert 'LIMIT' in text and 'no results yet' in text
    assert len(text.splitlines()) <= 40


def test_no_rules_is_one_quiet_line_without_building_a_map(tmp_path, capsys, monkeypatch):
    (tmp_path / 'app.py').write_text('def value(): return 1\n')
    def unused_map(*args, **kwargs):
        raise AssertionError('no intent should not parse the full project')
    monkeypatch.setattr(cli, 'build', unused_map)
    assert cli.screen(load_config(tmp_path)) == 0
    assert len(capsys.readouterr().out.splitlines()) == 1
    assert cli_fixture.check(load_config(tmp_path), before_main="""
from flowguard.intent import cli

def unused_map(*args, **kwargs):
    raise AssertionError('no intent should not parse the full project')

cli.build = unused_map
""") == 0
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_output_limit_keeps_whole_decisive_red_lines_and_counts_the_rest(tmp_path):
    _, cfg = project(tmp_path)
    data = cache.read(cfg)
    expected = 'LIMIT exact values: rule True, code False -> correct the home'
    data['results'] = {'LIMIT': {'items': {'one': dict(verdict='red', red=[expected + str(n) for n in range(50)], grey=[], info=[])}}}
    output = cli.render(cfg, data, check=True)
    assert len(output) <= 20
    assert expected + '0' in output[2]
    assert 'more lines' in output[-1] and 'red' in output[-1]


def test_every_command_has_a_description_in_the_help(capsys):
    # Round 22 F4: `--help` described only new-task and ledger; the other nine were bare names in the choice list.
    import re
    with pytest.raises(SystemExit) as stopped:
        cli.main(['--help'])
    text = capsys.readouterr().out
    assert stopped.value.code == 0
    commands = re.search(r'^  \{([\w,-]+)\}$', text, re.M)[1].split(',')
    assert len(commands) == 11 and {'check', 'show', 'init', 'req'} <= set(commands), text
    for command in commands:
        assert re.search(rf'^    {re.escape(command)} +\w', text, re.M), (command, text)


def test_init_is_idempotent_and_merges_existing_plugin_and_project_rules(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'tests/conftest.py').write_text('pytest_plugins = ["pytester"]\n')
    (root / 'AGENTS.md').write_text('Keep this project rule.\n\n## FlowGuard rules for the project agent\nOld model workflow.\n\n## Other rules\nKeep these too.\n')
    assert cli.init(cfg) == 0
    first = {name: (root / name).read_bytes() for name in ['tests/conftest.py', 'AGENTS.md', '.flowguard/ci.yml']}
    assert cli.init(cfg) == 0
    assert first == {name: (root / name).read_bytes() for name in first}
    assert 'pytester' in (root / 'tests/conftest.py').read_text()
    # registered once, in pytest's addopts (it loads before any conftest), not a second time in conftest.py
    assert 'flowguard.intent.plugin' not in (root / 'tests/conftest.py').read_text()
    assert '-p flowguard.intent.plugin' in tomllib.loads((root / 'pyproject.toml').read_text())['tool']['pytest']['ini_options']['addopts']
    agents = (root / 'AGENTS.md').read_text()
    assert 'Old model workflow' not in agents
    assert 'Keep this project rule' in agents and 'Keep these too' in agents
    assert 'fetch-depth: 0' in (root / '.flowguard/ci.yml').read_text()


PYTHON_CI = '''# Merge these steps into the project CI after installing FlowGuard.
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: python -m flowguard check --all --deep
'''


def test_init_writes_a_ci_fragment_that_runs_the_checks_the_project_can_run(tmp_path, capsys):
    # Round 22 F3: a TS project got `check --all --deep`, which runs pytest (nothing of the project's there), and
    # in CI compared nothing: a detached checkout's task start is HEAD. Its fragment runs check --static against
    # where the branch left the default branch.
    root, cfg = project(tmp_path)
    assert cli.init(cfg) == 0
    assert (root / '.flowguard/ci.yml').read_text() == PYTHON_CI          # a Python project: as before
    web = tmp_path / 'web'
    (web / 'src').mkdir(parents=True)
    (web / 'package.json').write_text('{"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n')
    (web / 'src/limit.ts').write_text('export function limit(days: number) { return days <= 3; }\n')
    assert cli.init(load_config(web)) == 0
    fragment = (web / '.flowguard/ci.yml').read_text()
    assert 'fetch-depth: 0' in fragment and 'check --all' not in fragment and '--deep' not in fragment, fragment
    assert ('- run: python -m flowguard check --static --base "$(git merge-base HEAD origin/${GITHUB_BASE_REF:-main})"\n'
            '  shell: bash\n') in fragment, fragment
    assert 'not called main' in fragment, fragment          # the comment says what to change
    assert cli.init(load_config(web)) == 0 and (web / '.flowguard/ci.yml').read_text() == fragment
    # Python tests of the project's own beside package.json: pytest runs them, the Python fragment stays.
    (web / 'tests').mkdir(exist_ok=True)
    (web / 'tests/test_limit.py').write_text('def test_limit():\n    assert True\n')
    assert cli.init(load_config(web)) == 0 and (web / '.flowguard/ci.yml').read_text() == PYTHON_CI


def test_init_registers_the_plugin_once_and_removes_the_conftest_line_an_older_init_wrote(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'tests').mkdir(exist_ok=True)
    (root / 'tests/conftest.py').write_text('\n\npytest_plugins = ["flowguard.intent.plugin"]\n')
    assert cli.init(cfg) == 0
    assert not (root / 'tests/conftest.py').exists()            # it held nothing but that line
    (root / 'tests/conftest.py').write_text('import os\n\npytest_plugins = ["flowguard.intent.plugin"]\n')
    assert cli.init(cfg) == 0
    assert (root / 'tests/conftest.py').read_text() == 'import os\n'
    # With pytest.ini, pytest never reads pyproject.toml's options: the conftest registration is the one.
    other, other_cfg = project(tmp_path)
    (other / 'pytest.ini').write_text('[pytest]\ntestpaths = tests\n')
    assert cli.init(other_cfg) == 0
    assert 'ini_options' not in (other / 'pyproject.toml').read_text()
    assert (other / 'tests/conftest.py').read_text().strip() == 'pytest_plugins = ["flowguard.intent.plugin"]'
    assert cli_fixture.main(['--root', str(other), 'check']) == 0     # the plugin runs once from conftest.py


def test_init_with_pytest_toml_registers_the_plugin_where_pytest_reads_it(tmp_path, capsys):
    # pytest 9 reads pytest.toml before pyproject.toml: options in pyproject.toml are never read there, so the
    # registration that loads the plugin is the conftest line, as with pytest.ini.
    root, cfg = project(tmp_path)
    (root / 'pytest.toml').write_text('[pytest]\ntestpaths = ["tests"]\n')
    assert cli.init(cfg) == 0
    assert 'ini_options' not in (root / 'pyproject.toml').read_text()
    assert (root / 'tests/conftest.py').read_text().strip() == 'pytest_plugins = ["flowguard.intent.plugin"]'
    assert cli_fixture.main(['--root', str(root), 'check']) == 0     # the sentinel finds the plugin loaded


def test_init_prints_the_norecursedirs_line_in_the_format_of_pytest_ini(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'pytest.ini').write_text('[pytest]\ntestpaths = tests\n')
    (root / 'tests/flowguard').mkdir(parents=True)
    (root / 'tests/flowguard/test_old.py').write_text('from flowguard.map.facts import load\n')
    capsys.readouterr()
    assert cli.init(cfg) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if 'norecursedirs = ' in line)
    # an INI file takes the patterns separated by spaces; a TOML list there would be one pattern
    assert 'set in pytest.ini (' in line and line.endswith(
        'norecursedirs = *.egg .* _darcs build CVS dist node_modules venv {arch} flowguard'), line


def test_init_names_test_files_of_an_older_flowguard_and_the_norecursedirs_line(tmp_path, capsys):
    root, cfg = project(tmp_path)
    legacy = root / 'tests/flowguard'
    legacy.mkdir(parents=True)
    for name in ('test_one.py', 'test_two.py'):
        (legacy / name).write_text('from flowguard.map.facts import load\n\ndef test_bound():\n    load()\n')
    (root / 'tests/test_ordinary.py').write_text('from flowguard.intent import rule\n\ndef test_value():\n    assert rule\n')
    capsys.readouterr()
    assert cli.init(cfg) == 0
    out = capsys.readouterr().out
    assert ('tests/flowguard/ holds 2 test files that import flowguard.map.facts, which this FlowGuard does not have '
            '(bindings of an older FlowGuard): pytest cannot collect them.') in out, out
    line = next(line for line in out.splitlines() if 'norecursedirs = ' in line)
    assert line.endswith('norecursedirs = ["*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}", '
                         '"flowguard"]'), line
    assert 'test_ordinary.py' not in out                         # flowguard.intent exists
    path = root / 'pyproject.toml'
    path.write_text(path.read_text().replace('[tool.pytest.ini_options]\n', '[tool.pytest.ini_options]\n' + line.partition(': ')[2] + '\n'))
    assert cli.init(cfg) == 0
    assert 'tests/flowguard/' not in capsys.readouterr().out     # pytest no longer goes there


@pytest.mark.parametrize('setting,expected', [
    ('addopts = "-q --strict-markers"', '-q --strict-markers -p flowguard.intent.plugin'),
    ('addopts = [\n "-q",\n "--strict-markers",\n]', ['-q', '--strict-markers', '-p', 'flowguard.intent.plugin']),
    ('', '-p flowguard.intent.plugin'),
])
def test_init_enables_early_project_plugin_without_losing_pytest_options(tmp_path, setting, expected):
    root, cfg = project(tmp_path)
    path = root / 'pyproject.toml'
    path.write_text(path.read_text() + '\n[tool.pytest.ini_options]\n' + setting + '\ntestpaths=["tests"]\n')
    assert cli.init(cfg) == 0
    first = path.read_bytes()
    ini = tomllib.loads(first.decode())['tool']['pytest']['ini_options']
    assert ini['addopts'] == expected
    assert ini['testpaths'] == ['tests']
    assert cli.init(cfg) == 0
    assert path.read_bytes() == first


def test_init_can_extend_a_final_pytest_table_without_a_trailing_newline(tmp_path):
    root, cfg = project(tmp_path)
    path = root / 'pyproject.toml'
    path.write_text(path.read_text().rstrip() + '\n[tool.pytest.ini_options]')
    assert cli.init(cfg) == 0
    first = path.read_bytes()
    assert tomllib.loads(first.decode())['tool']['pytest']['ini_options']['addopts'] == '-p flowguard.intent.plugin'
    assert cli.init(cfg) == 0
    assert path.read_bytes() == first


def test_a_violated_rule_has_the_next_step_of_pytest_in_every_check(tmp_path, capsys):
    # Round 22 F2: pytest said "改代码……；需求确实变了：先 req add……再改规则", while check added its own English
    # step to a red without one ("-> show the rule and correct its source, binding or regression rows"): on
    # the same line as pytest's step, and alone when check reused the rule's last result.
    import subprocess
    import sys
    root, cfg = project(tmp_path)
    policy = cfg.intent / 'policy.py'
    policy.write_text(policy.read_text().replace('row(days=4,expect=False', 'row(days=2,expect=False'))   # contradicts the rule
    cli.init(cfg)
    capsys.readouterr()
    steps = [f'    改代码，让 {root.name}.py:2 符合规则 LIMIT；',
             '    需求确实变了：先用 python -m flowguard req add 存下新的原话，再改规则 tests/intent/policy.py:2']
    def block(text):
        lines = text.splitlines()
        red = [index for index, line in enumerate(lines) if line.startswith('红：LIMIT：')]
        assert len(red) == 1 and 'show the rule' not in text and 'correct its source' not in text, text
        return lines[red[0]], lines[red[0] + 1:red[0] + 3]
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    ran = subprocess.run([sys.executable, '-c', bootstrap, cli_fixture.SOURCE, '-q'], cwd=root, capture_output=True, text=True, timeout=120)
    assert ran.returncode == 1, ran.stdout + ran.stderr
    line, after = block(ran.stdout)
    assert after == steps, ran.stdout
    for run in ('check reuses the result pytest saved', 'check again', 'check --all reruns the rule'):
        assert cli_fixture.check(cfg, everything=run.startswith('check --all')) == 1
        text = capsys.readouterr().out
        assert block(text)[1] == steps, (run, text)
    assert block(text)[0] == line, text            # pytest's finding, once, without a second step on it


def test_check_uses_real_pytest_items_and_finds_the_regression(tmp_path, capsys):
    _, cfg = project(tmp_path, wrong=True)
    cli.init(cfg)
    capsys.readouterr()
    assert cli_fixture.check(cfg) == 1
    text = capsys.readouterr().out
    assert 'LIMIT' in text and 'rule F, code True' in text
    assert len(text.splitlines()) <= 20
    stored = cache.read(cfg)
    assert stored['attempt']['sentinel'] == 'ok'
    assert any(result['verdict'] == 'red' for result in stored['results']['LIMIT']['items'].values())


def test_a_load_error_does_not_fall_back_to_word_search(tmp_path, capsys):
    _, cfg = project(tmp_path)
    path = cfg.intent / 'policy.py'
    path.write_text(path.read_text().replace('row(days=4', 'row(days=int("4")'))
    assert cli.show(cfg, 'LIMIT') == 1
    text = capsys.readouterr().out
    assert 'red load' in text and 'must be a literal' in text


def test_a_skipped_declaration_is_a_visible_load_failure(tmp_path, capsys):
    _, cfg = project(tmp_path)
    path = cfg.intent / 'policy.py'
    path.write_text('import pytest\npytest.skip("missing declaration must fail")\n' + path.read_text())
    cli.init(cfg)
    capsys.readouterr()
    assert cli_fixture.check(cfg) == 1
    assert 'Skipped' in capsys.readouterr().out
    assert cli.screen(cfg) == 0  # A screen reports cached facts; check owns execution status.
    assert 'last check load' in capsys.readouterr().out


def test_show_short_function_name_is_an_exact_owner_candidate(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'short.py').write_text('def f(x): return x > 2\n')
    assert cli.show(cfg, 'f') == 0
    assert 'short:f' in capsys.readouterr().out


def test_show_import_alias_points_to_the_actual_source_owner(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'entry.py').write_text(f'from {root.name} import accept as permit\n')
    assert cli.show(cfg, 'permit') == 0
    text = capsys.readouterr().out
    assert f'entry:permit (entry.py) -> {root.name}:accept' in text
    source = root / (root.name + '.py')
    declaration = next(node for node in ast.parse(source.read_text()).body
                       if isinstance(node, ast.FunctionDef) and node.name == 'accept')
    assert f'{root.name}.py:{declaration.lineno}' in text


def test_short_show_retains_each_red_and_grey_reading(tmp_path, capsys):
    root, cfg = project(tmp_path, wrong=True)
    cli.init(cfg)
    assert cli_fixture.check(cfg, everything=True) == 1
    capsys.readouterr()
    saved = cache.read(cfg)['results']['LIMIT']['items']
    messages = [text for result in saved.values() for kind in ('red', 'grey') for text in result.get(kind, [])]
    assert messages
    assert cli.show(cfg, 'LIMIT') == 0
    short = capsys.readouterr().out
    assert cli.show(cfg, 'LIMIT', full=True) == 0
    full = capsys.readouterr().out
    assert all(message in short and message in full for message in messages)
    assert len(short.encode()) < len(full.encode())
    assert 'source: doc policy.txt' in short
    assert f'anchor LIMIT -> {root.name}:accept' in short


def test_foreign_source_navigation_displays_static_coverage_and_execution_boundary(tmp_path, capsys):
    (tmp_path / 'service.ts').write_text('export function accept(days: number) { return days <= 3; }\n')
    cfg = load_config(tmp_path)
    assert cli.show(cfg, 'accept') == 0
    text = capsys.readouterr().out
    assert 'typescript 1/1 parsed' in text
    assert 'static facts' in text and 'execution not verified' in text
    assert cli.show(cfg, draft='typescript/service.ts:accept') == 0
    text = capsys.readouterr().out
    assert 'no verified native-home execution adapter' in text
    assert 'build inputs and read the real result' not in text
