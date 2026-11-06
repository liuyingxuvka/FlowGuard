"""The ordinary AI path stays short, honest and executable on a fresh project."""
from pathlib import Path
import uuid
import tomllib

import pytest

from flowguard.intent import cache, cli
from flowguard.intent.config import load_config


def project(tmp_path, wrong=False):
    root = tmp_path / ('p' + uuid.uuid4().hex)
    root.mkdir()
    name = root.name
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (root / 'policy.txt').write_text('At most three days.\n')
    (root / (name + '.py')).write_text('def accept(days):\n    return days <= ' + ('4' if wrong else '3') + '\n')
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    (folder / 'policy.py').write_text(f'''from flowguard.intent import rule,row
@rule('LIMIT',decides='acceptance',fields={{'days':int}},source='doc policy.txt "At most three days."')
def LIMIT(days):
    """The fourth day must stay refused across later sessions."""
    return days <= 3
LIMIT.rows(row(days=4,expect=False,why='a corrected fourth-day regression'))
@LIMIT.home('{name}:accept')
def home(c,fn): return fn(c.days)
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
    assert cli.check(load_config(tmp_path)) == 0
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


def test_init_is_idempotent_and_merges_existing_plugin_and_project_rules(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'tests/conftest.py').write_text('pytest_plugins = ["pytester"]\n')
    (root / 'AGENTS.md').write_text('Keep this project rule.\n\n## FlowGuard rules for the project agent\nOld model workflow.\n\n## Other rules\nKeep these too.\n')
    assert cli.init(cfg) == 0
    first = {name: (root / name).read_bytes() for name in ['tests/conftest.py', 'AGENTS.md', '.flowguard/ci.yml']}
    assert cli.init(cfg) == 0
    assert first == {name: (root / name).read_bytes() for name in first}
    assert 'pytester' in (root / 'tests/conftest.py').read_text()
    assert 'flowguard.intent.plugin' in (root / 'tests/conftest.py').read_text()
    agents = (root / 'AGENTS.md').read_text()
    assert 'Old model workflow' not in agents
    assert 'Keep this project rule' in agents and 'Keep these too' in agents
    assert 'fetch-depth: 0' in (root / '.flowguard/ci.yml').read_text()


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


def test_check_uses_real_pytest_items_and_finds_the_regression(tmp_path, capsys):
    _, cfg = project(tmp_path, wrong=True)
    cli.init(cfg)
    capsys.readouterr()
    assert cli.check(cfg) == 1
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
    assert cli.check(cfg) == 1
    assert 'Skipped' in capsys.readouterr().out
    assert cli.screen(cfg) == 0  # A screen reports cached facts; check owns execution status.
    assert 'last check load' in capsys.readouterr().out


def test_show_short_function_name_is_an_exact_owner_candidate(tmp_path, capsys):
    root, cfg = project(tmp_path)
    (root / 'short.py').write_text('def f(x): return x > 2\n')
    assert cli.show(cfg, 'f') == 0
    assert 'short:f' in capsys.readouterr().out


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
