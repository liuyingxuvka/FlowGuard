"""The public check route must use cached facts without changing their conclusion."""
from pathlib import Path
import os
import subprocess
import sys

import pytest

from tests.intent_engine import _cli_fixture as cli_fixture

from flowguard.intent import cache, cli
from flowguard.structure import build
from test_cli import project
from tests.intent_engine._source_fixture import source_sessions


def git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=control', '-c', 'user.email=control@example.invalid',
                           *arguments], check=True, capture_output=True).stdout.decode().strip()


# Keep the existing import for other test modules; the shared launcher owns the spy.
calls = cli_fixture.calls

@pytest.mark.parametrize('wrong,expected', [(False, 0), (True, 1)])
def test_unchanged_check_runs_zero_rules_and_preserves_a_cached_red(tmp_path, monkeypatch, capsys, wrong, expected):
    _, cfg = project(tmp_path, wrong=wrong)
    cli.init(cfg)
    assert cli_fixture.check(cfg) == expected
    before = cache.read(cfg)
    capsys.readouterr()
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == expected
    assert observed == []
    after = cache.read(cfg)
    assert after['results'] == before['results']
    assert after['collection'] == before['collection']
    assert after['attempt'] == before['attempt'], 'reuse must not manufacture a new complete run'
    text = capsys.readouterr().out
    assert len(text.splitlines()) <= 10
    assert '红：LIMIT' in text if wrong else text == ''


def test_since_selects_real_git_changes_even_after_current_cache_is_fresh(tmp_path, monkeypatch, capsys):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'existing decision')
    base = git(root, 'rev-parse', 'HEAD')
    source = root / (root.name + '.py')
    source.write_text(source.read_text().replace('days <= 3', 'not days > 3'))
    assert cli_fixture.check(cfg) == 0
    before = cache.read(cfg)['attempt']['stamp']
    capsys.readouterr()
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg, since=base) == 0
    assert len(observed) == 1 and '--flowguard-rules=LIMIT' in observed[0]
    checked = cache.read(cfg)['attempt']
    assert checked['stamp'] > before and checked['sentinel'] == 'ok' and checked['missing'] == []
    assert len(capsys.readouterr().out.splitlines()) <= 10
    assert cli_fixture.main(['--root', str(root), 'check', '--since', 'missing-control-revision']) == 2


def test_removing_the_last_rule_cannot_bypass_the_history_check(tmp_path, capsys):
    root, cfg = project(tmp_path)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'rule to preserve')
    (cfg.intent / 'policy.py').unlink()
    assert cli_fixture.check(cfg, since='HEAD') == 1
    assert 'rule removed without' in capsys.readouterr().out


def test_partial_ordinary_pytest_preserves_complete_collection_without_false_red(tmp_path):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    assert cli_fixture.check(cfg) == 0
    before = cache.read(cfg)['collection']
    test = root / 'tests/test_platform.py'
    test.write_text('import pytest\n@pytest.mark.skipif(True, reason="other platform")\ndef test_platform(): assert True\n')
    result = subprocess.run([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;raise SystemExit(pytest.main(sys.argv[1:]))',
        str(Path(cli.__file__).resolve().parents[2]), '-q', str(test)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    data = cache.read(cfg)
    assert data['attempt']['sentinel'] is None and data['attempt']['collected'] == 0
    assert data['collection'] == before
    assert not any('red collection' in line for line in cli.render(cfg, data))


@pytest.mark.parametrize('parameter_id', [None, 'a::b'])
def test_actual_dynamic_skip_is_guard_lost_only_for_a_true_rule_marker(tmp_path, capsys, parameter_id):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    test = root / ('tests/test_platform.py' if parameter_id is None else 'tests/test_platform[case].py')
    original = 'import pytest\nOTHER_PLATFORM=True\n@pytest.mark.skipif(OTHER_PLATFORM, reason="other platform")\ndef test_platform(): assert True\n'
    if parameter_id is not None:
        original = original.replace('@pytest.mark.skipif', f'@pytest.mark.parametrize("value", [{parameter_id!r}])\n@pytest.mark.skipif')
        original = original.replace('def test_platform():', 'def test_platform(value):')
    test.write_text(original)
    assert cli_fixture.check(cfg, everything=True) == 0
    capsys.readouterr()
    test.write_text(original.replace('@pytest.mark.skipif', '@pytest.mark.rule("LIMIT")\n@pytest.mark.skipif'))
    assert cli_fixture.check(cfg, everything=True) == 1
    assert 'guard lost' in capsys.readouterr().out


def test_a_new_corrected_row_attaches_real_old_code_proof_to_existing_result(tmp_path, capsys):
    root, cfg = project(tmp_path, wrong=True)
    intent = cfg.intent / 'policy.py'
    new = intent.read_text()
    intent.write_text('\n'.join(line for line in new.splitlines() if '.rows(' not in line) + '\n')
    cli.init(cfg)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'previous code accepted the fourth day')
    baseline = git(root, 'rev-parse', 'HEAD')
    source = root / (root.name + '.py')
    source.write_text(source.read_text().replace('days <= 4', 'days <= 3'))
    intent.write_text(new)
    assert cli_fixture.check(cfg) == 0
    data = cache.read(cfg)
    proofs = [proof for result in data['results']['LIMIT']['items'].values() for proof in result.get('proven_rows', [])]
    assert len(proofs) == 1 and proofs[0]['status'] == 'proven'
    assert proofs[0]['homes'][0]['actual'] == 'True'
    assert proofs[0]['base'] == baseline, 'old-code proof must name the real previous commit'
    assert len(capsys.readouterr().out.splitlines()) <= 10


def test_changed_source_selects_ordinary_pytest_after_a_screen_consumed_the_map_delta(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    test = root / 'tests/test_actual.py'
    test.write_text(f'from {root.name} import accept\ndef test_actual(): assert not accept(4)\n')
    assert cli_fixture.check(cfg) == 0
    assert cache.read(cfg)['tests']['tests/test_actual.py::test_actual']['outcome'] == 'passed'
    source = root / (root.name + '.py')
    timestamp = source.stat()
    source.write_text(source.read_text().replace('days <= 3', 'days <= 4'))
    # Reproduce the real same-size/same-timestamp bytecode collision deterministically.
    os.utime(source, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
    build(root).close()
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 1
    assert any('tests/test_actual.py::test_actual' in command or 'tests/test_actual.py' in command for command in observed)
    assert cache.read(cfg)['tests']['tests/test_actual.py::test_actual']['outcome'] == 'failed'


def test_static_transitive_helper_and_conftest_content_are_test_dependencies(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    helper = root / 'test_helper.py'
    helper.write_text('def value(): return 3\n')
    conftest = root / 'tests/conftest.py'
    conftest.write_text(conftest.read_text() + '\nimport pytest\nfrom test_helper import value\n@pytest.fixture\ndef supplied(): return value()\n')
    (root / 'tests/test_ordinary.py').write_text('def test_actual(supplied): assert supplied == 3\n')
    assert cli_fixture.check(cfg) == 0
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0
    # N1 keeps the original third-party pytest fixture initialization opaque.
    # Compare against its real no-op selection rather than silently calling it
    # closed; adding unrelated code must not expand the selected set or rules.
    assert len(observed) == 1
    baseline = list(observed[0])
    assert '--flowguard-rules=LIMIT' in baseline, 'an opaque fixture must recheck the shared rule scope'
    observed.clear()
    (root / 'unrelated.py').write_text('UNRELATED = 123\n')
    assert cli_fixture.check(cfg) == 0
    assert observed == [baseline], 'an unrelated module must not expand current selection'
    helper.write_text('def value(): return 42\n')
    build(root).close()
    assert cli_fixture.check(cfg) == 1
    assert any('tests/test_ordinary.py' in command for command in observed)
    assert cache.read(cfg)['tests']['tests/test_ordinary.py::test_actual']['outcome'] == 'failed'


def test_unresolved_import_rechecks_shared_scope_in_one_session(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    (root / 'tests/test_static.py').write_text('def test_static(): assert True\n')
    (root / 'tests/test_dynamic.py').write_text('import importlib\ndef test_dynamic(): assert importlib.import_module("json").loads("3") == 3\n')
    assert cli_fixture.check(cfg) == 0
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0
    assert len(observed) == 1
    assert 'tests/test_dynamic.py' in observed[0]
    assert 'tests/test_static.py' in observed[0], 'opaque input may affect another test in the shared Session'
    assert '--flowguard-rules=LIMIT' in observed[0]


def test_child_only_source_change_is_rechecked_without_global_footprints(tmp_path):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    child = root / 'worker.py'
    child.write_text('raise SystemExit(0)\n')
    # The retired child bootstrap no longer replaces standard timestamp-based module bytecode.
    # Execute the actual script path; its same-size/mtime change must still select this test.
    (root / 'tests/test_child.py').write_text('from subprocess import run as launch\nfrom pathlib import Path\nimport sys\ndef test_child(): assert launch([sys.executable, str(Path(__file__).resolve().parents[1] / "worker.py")]).returncode == 0\n')
    assert cli_fixture.check(cfg) == 0
    timestamp = child.stat()
    child.write_text('raise SystemExit(4)\n')
    os.utime(child, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
    build(root).close()
    assert cli_fixture.check(cfg) == 1
    assert cache.read(cfg)['tests']['tests/test_child.py::test_child']['outcome'] == 'failed'


def test_all_runs_real_pytest_even_without_intent(tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\n')
    (tmp_path / 'test_actual.py').write_text('def test_wrong(): assert False\n')
    from flowguard.intent.config import load_config
    assert cli_fixture.check(load_config(tmp_path), everything=True) == 1


def test_changed_dependency_rechecks_the_parent_in_one_real_pytest_session(tmp_path, monkeypatch, capsys):
    from test_composition import project as composed, CODE
    model, _, module = composed(tmp_path)
    cfg = model.cfg
    cli.init(cfg)
    assert cli_fixture.check(cfg) == 0
    capsys.readouterr()
    cached = cache.read(cfg)
    assert any(part.get('own_contract', {}).get('complete') for part in cached['results']['STANDING']['items'].values())
    source = cfg.root / (module + '.py')
    source.write_text(source.read_text().replace('if ended > 3:', 'if not ended <= 3:'))
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0
    assert len(observed) == 1
    # File-grained input identity includes the child's source for CHECKOUT too.
    # An old own_contract never cuts that changed dependency out of this Session.
    assert '--flowguard-rules=CHECKOUT,STANDING,STANDING_CHECKOUT' in observed[0]
    checked = cache.read(cfg)
    assert checked['attempt']['stamp'] > cached['attempt']['stamp']
    assert checked['results']['CHECKOUT']['items']
    assert capsys.readouterr().out == ''
    observed.clear()
    assert cli_fixture.check(cfg) == 0
    assert len(observed) == 1, 'the unclosed scenario must run rather than reuse an old partial result'
    assert '--flowguard-rules=CHECKOUT,STANDING,STANDING_CHECKOUT' in observed[0]
    observed.clear()
    assert cli_fixture.check(cfg, everything=True) == 0
    assert len(observed) == 1 and not any(str(arg).startswith('--flowguard-rules=') for arg in observed[0])


def test_states_are_rechecked_even_without_any_decision_rules(tmp_path):
    root, cfg = project(tmp_path)
    intent = cfg.intent / 'policy.py'
    intent.write_text(f'from flowguard.intent import states\nstates("{root.name}:Hire.status", ["open", "returned"], source="assumed: status vocabulary")\n')
    source = root / (root.name + '.py')
    source.write_text('class Hire:\n def open(self): self.status="open"\n')
    cli.init(cfg)
    assert cli_fixture.check(cfg) == 0
    source.write_text(source.read_text().replace('status="open"', 'status="held"'))
    assert cli_fixture.check(cfg) == 1
    assert 'code writes' in (cfg.cache / 'check-output.txt').read_text()


@pytest.mark.parametrize('changed', ['source', 'helper', 'test'])
def test_draft_navigation_does_not_claim_an_ordinary_trace_is_a_current_reading(tmp_path, capsys, changed):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    helper = root / 'support.py'
    helper.write_text(f'from {root.name} import accept\ndef allowed(): return accept(2)\n')
    test = root / 'tests/test_actual.py'
    test.write_text('from support import allowed\ndef test_actual(): assert allowed()\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    capsys.readouterr()
    target = root.name + ':accept'
    assert cli.show(cfg, draft=target) == 0
    current = capsys.readouterr().out
    assert 'source navigation: current Map identity' in current
    assert 'inputs: last observed' not in current
    assert not cache.read(cfg)['traces']
    path = root / (root.name + '.py') if changed == 'source' else helper if changed == 'helper' else test
    path.write_text(path.read_text() + '\n# changed version\n')
    assert cli.show(cfg, draft=target) == 0
    stale = capsys.readouterr().out
    assert 'source navigation: current Map identity' in stale
    assert 'inputs: last observed' not in stale
    assert not cache.read(cfg)['traces']


def test_direct_pytest_preserves_its_real_reading_without_a_draft_footprint(tmp_path, capsys):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    test = root / 'tests/test_actual.py'
    test.write_text(f'from {root.name} import accept\ndef test_actual(): assert accept(2)\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    capsys.readouterr()
    nodeid = 'tests/test_actual.py::test_actual'
    before = cache.read(cfg)
    assert before['tests'][nodeid]['outcome'] == 'passed'
    assert not before['traces']
    result = subprocess.run([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;raise SystemExit(pytest.main(sys.argv[1:]))',
        str(Path(cli.__file__).resolve().parents[2]), '-q', str(test)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    after = cache.read(cfg)
    assert after['tests'][nodeid]['outcome'] == 'passed'
    assert after['tests'][nodeid]['stamp'] > before['tests'][nodeid]['stamp']
    assert not after['traces']
    assert cli.show(cfg, draft=root.name + ':accept') == 0
    output = capsys.readouterr().out
    assert 'source navigation: current Map identity' in output
    assert 'inputs: last observed' not in output
