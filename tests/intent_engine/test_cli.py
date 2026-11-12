"""The ordinary AI path stays short, honest and executable on a fresh project."""
import ast
import os
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
    (root / '.flowguard').mkdir()
    (root / '.flowguard/rules.toml').write_text('[rule.three-days]\ntext = "A loan lasts at most three days."\n'
                                                'source = \'doc policy.txt "At most three days."\'\n', encoding='utf-8')
    assert cli.screen(cfg) == 0
    text = capsys.readouterr().out
    # The rules in force are those of rules.toml (design 4.4); the intent rule that checks one is not listed.
    assert text.splitlines()[1:] == ['rule.three-days: A loan lasts at most three days.'], text


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


def test_every_command_has_a_description_in_the_help(capsys, monkeypatch):
    # Round 22 F4: `--help` described only new-task and ledger; the other nine were bare names in the choice list.
    import re
    monkeypatch.setenv('COLUMNS', '100')        # argparse wraps at the terminal's width: the same lines in any terminal
    with pytest.raises(SystemExit) as stopped:
        cli.main(['--help'])
    text = capsys.readouterr().out
    assert stopped.value.code == 0
    commands = re.search(r'^  \{([\w,-]+)\}$', text, re.M)[1].split(',')
    assert set(commands) == {'new-task', 'check', 'show', 'req', 'ledger', 'init'}, text
    for command in commands:
        assert re.search(rf'^    {re.escape(command)} +\w', text, re.M), (command, text)


@pytest.mark.parametrize('command', ['anchor', 'model', 'try', 'watch', 'compare'])
def test_deprecated_commands_stay_callable_but_out_of_the_top_level_help(command, capsys):
    with pytest.raises(SystemExit) as stopped:
        cli.main([command, '--help'])
    text = capsys.readouterr()
    assert stopped.value.code == 0
    assert 'usage: flowguard ' + command in text.out
    assert 'deprecated:' in text.err and '5.0' in text.err


@pytest.mark.parametrize('command', ['status', 'where'])
def test_old_project_commands_only_point_to_the_current_task_entry(command, capsys):
    assert cli.main([command]) == 0
    assert capsys.readouterr().out == 'this is a FlowGuard 0.7x command; here run python -m flowguard new-task\n'


def test_full_check_assembles_static_findings_once_across_pytest_and_cli(tmp_path):
    _, cfg = project(tmp_path)
    cli.init(cfg)
    assert cli_fixture.check(cfg, everything=True, before_main='''
from flowguard.intent import owners
_static = owners.static_findings
_calls = []
def counted(*args, **kwargs):
    _calls.append(1)
    return _static(*args, **kwargs)
owners.static_findings = counted
_main = cli.main
def checked_main(*args, **kwargs):
    result = _main(*args, **kwargs)
    assert len(_calls) == 1, f'static findings computed {len(_calls)} times'
    return result
cli.main = checked_main
''') == 0


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


# The base on a line of its own: under GitHub's `bash -eo pipefail` a failed merge-base fails the step (round 22
# F3 review: inside "$(...)" it gave `--base ""`, and the step passed without comparing anything).
STATIC_RUN = '''- run: |
    base=$(git merge-base HEAD "origin/${GITHUB_BASE_REF:-main}")
    python -m flowguard check --static --base "$base"
  shell: bash
'''


@pytest.mark.skipif(os.name == 'nt', reason='GitHub runs the step in bash; a POSIX bash stands in for it')
def test_the_static_ci_step_fails_where_the_default_branch_cannot_be_found(tmp_path):
    import subprocess
    import sys
    root = tmp_path / 'web'
    root.mkdir()
    for command in (['init', '-q', '-b', 'master'], ['-c', 'user.name=t', '-c', 'user.email=t@example.invalid',
                                                     'commit', '-q', '--allow-empty', '-m', 'base']):
        subprocess.run(['git', '-C', str(root), *command], check=True, capture_output=True)
    step = cli.CI_STATIC.partition('- run: ')[2].partition('  shell: bash')[0]      # the step init writes
    script = '\n'.join(line[4:] for line in step.splitlines()[1:]) if step.startswith('|') else step
    path = os.pathsep.join([str(Path(sys.executable).parent), os.environ['PATH']])   # `python` is this one
    ran = subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', script], cwd=root,
                         capture_output=True, text=True, timeout=60, env=dict(os.environ, GITHUB_BASE_REF='', PATH=path))
    assert ran.returncode != 0 and 'origin/main' in ran.stderr and 'FlowGuard' not in ran.stdout, ran


def test_check_refuses_an_empty_base(tmp_path, capsys):
    root, cfg = project(tmp_path)
    for options in (['--static'], []):
        assert cli_fixture.main(['--root', str(root), 'check', *options, '--base', '']) == 2
        err = capsys.readouterr().err
        assert '--base' in err and 'commit' in err, err


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
    assert fragment.endswith(STATIC_RUN), fragment
    assert 'not called main' in fragment, fragment          # the comment says what to change
    assert cli.init(load_config(web)) == 0 and (web / '.flowguard/ci.yml').read_text() == fragment
    # Python tests of the project's own beside package.json: pytest runs them, the Python fragment stays.
    (web / 'tests').mkdir(exist_ok=True)
    (web / 'tests/test_limit.py').write_text('def test_limit():\n    assert True\n')
    assert cli.init(load_config(web)) == 0 and (web / '.flowguard/ci.yml').read_text() == PYTHON_CI


def test_a_virtual_environment_beside_package_json_holds_no_test_of_the_project(tmp_path):
    # Round 22 F3 review: a venv folder (pyvenv.cfg) with a package's tests made a TS project look like one with
    # Python tests of its own, so init wrote the pytest fragment; pytest itself never enters a venv (`_in_venv`).
    # The project's own norecursedirs replaces pytest's list, which would have kept a folder named venv out.
    web = tmp_path / 'web'
    (web / 'env/lib/python3.12/site-packages/somepkg/tests').mkdir(parents=True)
    (web / 'env/pyvenv.cfg').write_text('home = /usr/bin\n')
    (web / 'env/lib/python3.12/site-packages/somepkg/tests/test_x.py').write_text('def test_x():\n    assert True\n')
    (web / 'package.json').write_text('{"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n')
    (web / 'pyproject.toml').write_text('[tool.pytest.ini_options]\nnorecursedirs = ["build"]\n')
    assert cli.init(load_config(web)) == 0
    assert (web / '.flowguard/ci.yml').read_text().endswith(STATIC_RUN)


def test_a_conda_environment_or_a_folder_that_cannot_be_entered_holds_no_test_of_the_project(tmp_path, monkeypatch):
    # Round 22 F3, second review: a folder init may not enter (a database volume of another user) made
    # own_python_tests raise PermissionError, and init stopped; a conda environment (conda-meta/history, no
    # pyvenv.cfg) was walked into. pytest's `_in_venv` takes the first for no environment and reads the second as one.
    from flowguard.intent import deps
    web = tmp_path / 'web'
    for folder in ('conda', 'locked'):
        (web / folder / 'pkgs/tests').mkdir(parents=True)
        (web / folder / 'pkgs/tests/test_x.py').write_text('def test_x():\n    assert True\n')
    (web / 'conda/conda-meta').mkdir()
    (web / 'conda/conda-meta/history').write_text('==> 2024-05-01 12:00:00 <==\n')
    (web / 'package.json').write_text('{"name": "web", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n')
    (web / 'pyproject.toml').write_text('[tool.pytest.ini_options]\nnorecursedirs = ["build", "locked"]\n')
    assert cli.init(load_config(web)) == 0
    assert (web / '.flowguard/ci.yml').read_text().endswith(STATIC_RUN)
    # What a user without access to locked/ meets (root reads past a mode of 000): looking inside it is refused.
    (web / 'pyproject.toml').write_text('[tool.pytest.ini_options]\nnorecursedirs = ["build"]\n')
    cfg = load_config(web)
    is_file = Path.is_file
    def refused(path):
        if 'locked' in path.parts[len(web.parts):]:
            raise PermissionError(13, 'Permission denied', str(path))
        return is_file(path)
    monkeypatch.setattr(Path, 'is_file', refused)
    assert deps.own_python_tests(cfg) is False


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


REQ_ADD = '    if requirements changed, first store the new owner words with python -m flowguard req add, then update rule tests/intent/policy.py:2'
LONGER = """@rule('LONGER',decides='acceptance',fields={'days':int},source='doc policy.txt "At most three days."')
def LONGER(days):
    return days <= 4
"""
# A rule that decides the fourth day over LIMIT, against LIMIT's own row there (`the decision of ... is`).
FOURTH = """@rule('FOURTH',decides='acceptance',fields={'days':int},overrides=('LIMIT',),source='doc policy.txt "At most three days."')
def FOURTH(days):
    return True if days == 4 else None
"""


# Round 22 F2, second review: `gap in` and `row X ... the decision of Y is ...` were sorted by reading the code only.
@pytest.mark.parametrize('kind', ['code', 'own row', 'conflict', 'gap', 'decision of'])
def test_a_violated_rule_has_the_next_step_of_its_kind_in_pytest_and_every_check(tmp_path, capsys, kind):
    # Round 22 F2: pytest said "改代码……；需求确实变了：先 req add……再改规则", while check added its own English
    # step to a red without one ("-> show the rule and correct its source, binding or regression rows"): on
    # the same line as pytest's step, and alone when check reused the rule's last result. The first fix gave
    # every rule red "改代码" (its review): a rule that contradicts its own row or another rule is not mended in
    # the code, which already agrees with it.
    import subprocess
    import sys
    root, cfg = project(tmp_path, wrong=kind == 'code')
    policy = cfg.intent / 'policy.py'
    if kind == 'own row':
        policy.write_text(policy.read_text().replace('row(days=4,expect=False', 'row(days=2,expect=False'))
    if kind == 'conflict':
        policy.write_text(policy.read_text() + LONGER)
    if kind == 'gap':          # a total rule that decides no negative day
        policy.write_text(policy.read_text().replace('"At most three days."\')', '"At most three days."\',total=True)')
                          .replace('    return days <= 3\n', '    return days <= 3 if days >= 0 else None\n'))
    if kind == 'decision of':  # the code agrees with what decides: only LIMIT's row is red
        policy.write_text(policy.read_text() + FOURTH)
        code = root / (root.name + '.py')
        code.write_text(code.read_text().replace('return days <= 3', 'return days <= 3 or days == 4'))
    # pytest prints the 4.3 block: one red line for the rule, its first step after ' -> ', every step in its detail
    # (show --last). `check` still prints the 4.2 lines with their indented steps until its lane moves to the block.
    steps = {'code': [f'change the code so {root.name}.py:accept follows rule LIMIT', REQ_ADD.strip()],
             'own row': ['correct regression rows or rule tests/intent/policy.py:2 so the rule and its regression rows agree', REQ_ADD.strip()],
             'conflict': ['rules LIMIT and LONGER conflict; choose one by asking the owner',
                          'when the owner decides, first store the exact owner words with python -m flowguard req add, then update rule tests/intent/policy.py:2'],
             'gap': ['add rules or regression rows at tests/intent/policy.py:2 so undecided cells have a rule result', REQ_ADD.strip()],
             'decision of': ['correct regression rows or rule tests/intent/policy.py:2 so the rule and its regression rows agree', REQ_ADD.strip()]}[kind]
    legacy = {'code': [f'    change the code so {root.name}.py:2 follows rule LIMIT; ', REQ_ADD],
              'own row': ['    correct regression rows or rule tests/intent/policy.py:2 so the rule and its regression rows agree; ', REQ_ADD],
              'conflict': ['    rules LIMIT and LONGER conflict; choose one by asking the owner; ',
                           '    when the owner decides, first store the exact owner words with python -m flowguard req add, then update rule tests/intent/policy.py:2'],
              'gap': ['    add rules or regression rows at tests/intent/policy.py:2 so undecided cells have a rule result; ', REQ_ADD],
              'decision of': ['    correct regression rows or rule tests/intent/policy.py:2 so the rule and its regression rows agree; ', REQ_ADD]}[kind]
    cli.init(cfg)
    capsys.readouterr()
    def block(text):
        lines = cli_fixture.display_text(text).splitlines()    # a console that cannot encode Chinese shows \uXXXX
        red = [index for index, line in enumerate(lines) if line.startswith('red: LIMIT：')]
        assert len(red) == 1 and 'show the rule' not in text and 'correct its source' not in text, text
        return lines[red[0]], lines[red[0] + 1:red[0] + 3]
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    ran = subprocess.run([sys.executable, '-c', bootstrap, cli_fixture.SOURCE, '-q'], cwd=root, capture_output=True, text=True, timeout=120)
    assert ran.returncode == 1, ran.stdout + ran.stderr
    reds = [line for line in cli_fixture.block(ran) if line.startswith('red: rule LIMIT: ')]
    assert len(reds) == 1 and 'show the rule' not in ran.stdout and 'correct its source' not in ran.stdout, ran.stdout
    assert reds[0].endswith(' -> ' + steps[0].replace('tests/intent/policy.py', 'policy.py')), reds
    shown = cli_fixture.last(root).splitlines()
    full = next(line for line in shown if line.startswith('red: rule LIMIT: '))
    detail = shown[shown.index(full) + 1:]
    assert ['    ' + step for step in steps] in [detail[index:index + 2] for index in range(len(detail))], shown
    assert kind not in ('gap', 'decision of') or ('gap in acceptance (total=True)' if kind == 'gap' else
                                                  'the decision of an overriding rule is T') in full, full
    lines = []
    for run in ('check reuses the result pytest saved', 'check again', 'check --all reruns the rule'):
        assert cli_fixture.check(cfg, everything=run.startswith('check --all')) == 1
        text = capsys.readouterr().out
        line, after = block(text)
        assert after == legacy, (run, text)
        lines.append(line)
    # The finding once in every check, without a second step on it; rerun, with the owner's words.
    assert lines[1] == lines[0] and lines[2].endswith('  LIMIT source: At most three days.'), lines


def test_a_red_that_is_no_rule_keeps_a_next_step_in_pytest_and_check(tmp_path, capsys):
    # Round 22 F2 review: with the rule steps only for rules, check printed a broken distinct with no step at all.
    import subprocess
    import sys
    (tmp_path / 'POLICY.md').write_text('The two eligibility decisions must remain separate.\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["POLICY.md"]\n')
    (tmp_path / 'decision.py').write_text('# flowguard: sensor first(days: day) -> allowed: bool\ndef first(days: int) -> bool:\n'
                                          '    return days <= 3\n# flowguard: sensor second(days: day) -> allowed: bool\n'
                                          'def second(days: int) -> bool:\n    return days <= 3\n')
    (tmp_path / 'tests/intent').mkdir(parents=True)
    (tmp_path / 'tests/intent/policies.py').write_text(
        "from flowguard.intent import distinct\ndistinct('first', 'second', why='The two eligibility decisions must remain "
        "separate.', source='doc POLICY.md \"The two eligibility decisions must remain separate.\"')\n")
    cfg = load_config(tmp_path)
    cli.init(cfg)
    capsys.readouterr()
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    ran = subprocess.run([sys.executable, '-c', bootstrap, cli_fixture.SOURCE, '-q'], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert cli_fixture.check(cfg) == 1
    for text in (ran.stdout, capsys.readouterr().out):
        lines = text.splitlines()
        index = next(index for index, line in enumerate(lines) if 'distinct broken: first and second agree' in line)
        assert ' -> ' in lines[index] or lines[index + 1:index + 2] and lines[index + 1].startswith('    '), text


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
    assert capsys.readouterr().out.splitlines()[-1] == '1 still red: python -m flowguard show --last'


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
