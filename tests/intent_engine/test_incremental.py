"""Changes that must invalidate evidence, and changes that must stay quiet."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import textwrap
import uuid

from flowguard.intent import cache, deps, history
from flowguard.intent.config import load_config
from flowguard.intent.loader import load
from flowguard.intent.engine import Engine
from flowguard.structure import build


def git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True).stdout.decode().strip()


def fixture(tmp_path, body='return x <= LIMIT', helper=False):
    root = tmp_path / ('p' + uuid.uuid4().hex)
    root.mkdir()
    name = root.name
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (root / 'policy.txt').write_text('The limit is three.\n')
    (root / (name + '.py')).write_text('LIMIT=3\ndef accept(x):\n    ' + body + '\ndef unrelated(x):\n    return x + 1\n')
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    intent = f'''from flowguard.intent import rule,row
@rule('LIMIT',decides='allowed',fields={{'x':int}},source='doc policy.txt "The limit is three."')
def LIMIT(x): return x <= 3
LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))
@LIMIT.home('{name}:accept')
def home(c,fn): return fn(c.x)
'''
    if helper:
        (root / 'tests/__init__.py').write_text('')
        (root / 'tests/support.py').write_text('from tests.deep import OFFSET\ndef value(x): return x + OFFSET\n')
        (root / 'tests/deep.py').write_text('OFFSET=0\n')
        intent = 'from tests.support import value\n' + intent.replace('fn(c.x)', 'fn(value(c.x))')
    (folder / 'limit.py').write_text(intent)
    cfg = load_config(root)
    return root, cfg, name


def execute(cfg):
    model = load(cfg)
    assert not model.errors, model.errors
    rule = model.rules['LIMIT']
    engine = Engine(model)
    result = engine.run_home(rule, rule.homes[0], 'cells')
    graph = build(cfg.root, roots=cfg.roots)
    saved = deps.record(cfg, model, rule, [result], graph)
    return model, graph, saved, result


def test_repeated_import_path_does_not_change_engine_but_a_package_upgrade_does(tmp_path, monkeypatch):
    _, cfg, _ = fixture(tmp_path)
    packages = tmp_path / 'packages'
    metadata = packages / 'fg_test_dependency-1.0.dist-info' / 'METADATA'
    metadata.parent.mkdir(parents=True)
    metadata.write_text('Metadata-Version: 2.1\nName: fg-test-dependency\nVersion: 1.0\n')
    installed = deps.site.getsitepackages()
    monkeypatch.setattr(deps.site, 'getsitepackages', lambda: [*installed, str(packages)])
    monkeypatch.syspath_prepend(str(packages))
    with closing(build(cfg.root)) as graph:
        before = deps.Now(cfg, graph)('engine:')
        # CLI bootstrap and a nested pytest can expose the same metadata twice.
        monkeypatch.syspath_prepend(str(packages))
        assert deps.Now(cfg, graph)('engine:') == before
        vendor = packages / 'build_vendor' / 'fg_test_vendor-3.0.dist-info'
        vendor.mkdir(parents=True)
        (vendor / 'METADATA').write_text('Metadata-Version: 2.1\nName: fg-test-vendor\nVersion: 3.0\n')
        monkeypatch.syspath_prepend(str(vendor.parent))
        assert deps.Now(cfg, graph)('engine:') == before
        metadata.write_text('Metadata-Version: 2.1\nName: fg-test-dependency\nVersion: 2.0\n')
        assert deps.stale({'dependencies': {'engine:': before}}, deps.Now(cfg, graph)) == ['engine:']


def test_enabled_user_site_package_versions_are_part_of_the_engine_identity(tmp_path, monkeypatch):
    _, cfg, _ = fixture(tmp_path)
    usersite = tmp_path / 'user_site'
    metadata = usersite / 'fg_user_dependency-1.0.dist-info' / 'METADATA'
    metadata.parent.mkdir(parents=True)
    def version(value):
        metadata.write_text(f'Metadata-Version: 2.1\nName: fg-user-dependency\nVersion: {value}\n')
    version('1.0')
    monkeypatch.setattr(deps.site, 'getusersitepackages', lambda: str(usersite))
    monkeypatch.setattr(deps.site, 'ENABLE_USER_SITE', True)
    before = deps.Now(cfg, None)('engine:')
    version('2.0')
    assert deps.Now(cfg, None)('engine:') != before
    monkeypatch.setattr(deps.site, 'ENABLE_USER_SITE', False)
    disabled = deps.Now(cfg, None)('engine:')
    version('3.0')
    assert deps.Now(cfg, None)('engine:') == disabled


def test_fresh_screen_is_ast_only_and_preserves_object_references(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    path = cfg.intent / 'limit.py'
    path.write_text('raise RuntimeError("must never execute")\n' + path.read_text() + '''
@rule('PARENT',decides='parent',fields={'allowed':bool},source='assumed: test',uses=[LIMIT])
def PARENT(allowed): return allowed
''')
    summary = cache.read(cfg)['summary']
    assert summary['rules']['PARENT']['uses'] == ['LIMIT']
    assert summary['rules']['LIMIT']['rows'] == 1
    assert not summary['errors']


def test_unresolved_reference_is_not_silently_dropped(tmp_path):
    _, cfg, _ = fixture(tmp_path)
    path = cfg.intent / 'limit.py'
    path.write_text(path.read_text().replace("fields={'x':int}", "fields={'x':int}, uses=[UNKNOWN]"))
    assert cache.scan(cfg)['rules']['LIMIT']['uses'] == ['unresolved:UNKNOWN']


def test_static_summary_reuses_sdk_alias_owner_for_rules_and_rows(tmp_path):
    _, cfg, _ = fixture(tmp_path)
    path = cfg.intent / 'limit.py'
    text = path.read_text().replace('from flowguard.intent import rule,row', 'import flowguard.intent as fg').replace('@rule(', '@fg.rule(').replace('row(x=', 'fg.row(x=')
    path.write_text(text)
    summary = cache.scan(cfg)
    assert not summary['errors']
    assert summary['rules']['LIMIT']['rows'] == 1
    assert summary['rules']['LIMIT']['fields'] == {'x': 'int'}


def test_literal_inline_starred_rows_are_preserved_and_unknown_registration_is_visible(tmp_path):
    _, cfg, _ = fixture(tmp_path)
    path = cfg.intent / 'limit.py'
    original = path.read_text()
    path.write_text(original.replace("LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))", "LIMIT.rows(*[row(x=4,expect=False,why='fixed fourth value')])"))
    assert cache.scan(cfg)['rules']['LIMIT']['rows'] == 1
    path.write_text(original.replace("LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))", 'LIMIT.rows(*unknown_rows())'))
    assert any('registration unresolved' in error['msg'] for error in cache.scan(cfg)['errors'])


def test_distinct_names_object_ids_without_executing_intent(tmp_path):
    _, cfg, _ = fixture(tmp_path)
    path = cfg.intent / 'limit.py'
    path.write_text('raise RuntimeError("never execute")\n' + path.read_text() + "\nfrom flowguard.intent import distinct as separate\nseparate(LIMIT,'sample:other',why='different policy',source='assumed: another rule')\n")
    assert cache.scan(cfg)['distincts'] == [dict(a='LIMIT', b='sample:other', why='different policy', source='assumed: another rule')]


def test_same_sqlite_keeps_latest_failed_attempt_and_previous_complete_results(tmp_path):
    _, cfg, _ = fixture(tmp_path)
    graph = build(cfg.root)
    graph.con.execute('CREATE TABLE result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
    graph.con.execute('INSERT INTO result VALUES(?,?,?,?,?)', ('intent::LIMIT[cells]', 'LIMIT', 'ok', '{"verdict":"ok"}', 1))
    for name, value in [('intent_collection', {'sentinel': 'ok', 'stamp': 1}), ('intent_attempt', {'sentinel': 'failed', 'stamp': 2})]:
        graph.con.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (name, json.dumps(value)))
    cache.save_dependencies(graph.con, {'LIMIT': {'dependencies': {'file:policy.txt': 'old'}, 'reasons': []}})
    graph.con.commit()
    graph.close()
    result = cache.read(cfg)
    assert result['attempt']['sentinel'] == 'failed'
    assert result['collection']['sentinel'] == 'ok'
    assert result['results']['LIMIT']['items']['intent::LIMIT[cells]']['verdict'] == 'ok'
    assert result['deps']['LIMIT']['dependencies']['file:policy.txt'] == 'old'


def test_unchanged_and_unrelated_function_body_do_not_rerun(tmp_path):
    root, cfg, module = fixture(tmp_path)
    model, graph, saved, result = execute(cfg)
    assert not saved['reasons']
    assert deps.stale(saved, deps.Now(cfg, graph)) == []
    path = root / (module + '.py')
    path.write_text(path.read_text().replace('return x + 1', 'return x + 99'))
    graph.close()
    graph = build(root)
    assert deps.stale(saved, deps.Now(cfg, graph)) == []
    graph.close()


def test_home_constant_and_document_changes_invalidate(tmp_path):
    root, cfg, module = fixture(tmp_path)
    _, graph, saved, _ = execute(cfg)
    (root / 'policy.txt').write_text('The limit is four.\n')
    assert 'file:policy.txt' in deps.stale(saved, deps.Now(cfg, graph))
    (root / 'policy.txt').write_text('The limit is three.\n')
    path = root / (module + '.py')
    path.write_text(path.read_text().replace('LIMIT=3', 'LIMIT=4'))
    graph.close()
    graph = build(root)
    assert any(key.startswith(('module:', 'node:')) for key in deps.stale(saved, deps.Now(cfg, graph)))
    graph.close()


def test_transitive_test_helper_is_hashed(tmp_path):
    # The public declarations need not execute for the dependency scanner to
    # preserve imports of test-side builders and their own imports.
    root, cfg, _ = fixture(tmp_path)
    helper = root / 'tests/support.py'
    helper.write_text('from tests.deep import OFFSET\n')
    deep = root / 'tests/deep.py'
    deep.write_text('OFFSET=0\n')
    model, graph, saved, result = execute(cfg)
    path = cfg.intent / 'limit.py'
    path.write_text('from tests.support import OFFSET\n' + path.read_text())
    saved = deps.record(cfg, model, model.rules['LIMIT'], [result], graph)
    assert 'file:tests/deep.py' in saved['dependencies']
    deep.write_text('OFFSET=1\n')
    assert 'file:tests/deep.py' in deps.stale(saved, deps.Now(cfg, graph))
    graph.close()


def test_module_initializer_function_is_part_of_module_identity(tmp_path):
    path = tmp_path / 'module.py'
    path.write_text('def compute(): return 3\nLIMIT=compute()\ndef unused(): return 1\n')
    before = deps.module_digest(path)
    path.write_text(path.read_text().replace('unused(): return 1', 'unused(): return 2'))
    assert deps.module_digest(path) == before
    path.write_text(path.read_text().replace('compute(): return 3', 'compute(): return 4'))
    assert deps.module_digest(path) != before


def test_rule_and_row_removal_compare_git_not_last_cache(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    base = git(root, 'rev-parse', 'HEAD')
    path = cfg.intent / 'limit.py'
    original = path.read_text()
    path.write_text(original.replace("LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))\n", ''))
    assert any('row removed' in line for line in history.check(cfg, base))
    path.unlink()
    assert any('rule removed' in line for line in history.check(cfg, base))
    path.write_text(original.replace("why='fixed fourth value'", "why='fixed fourth value', retired='requirement replaced'"))
    assert history.check(cfg, base) == []


def test_default_history_protects_a_row_in_the_first_committed_tree(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'first accepted case')
    path = cfg.intent / 'limit.py'
    path.write_text(path.read_text().replace("LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))\n", ''))
    assert any('row removed' in line for line in history.check(cfg))


def test_marked_test_loss_is_visible(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    test = root / 'tests/test_guard.py'
    test.write_text("import pytest\n@pytest.mark.rule('LIMIT')\ndef test_guard(): assert True\n")
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    base = git(root, 'rev-parse', 'HEAD')
    test.write_text(test.read_text().replace('assert True', "pytest.skip('lost')"))
    assert any('guard lost' in line for line in history.check(cfg, base))


def test_old_failure_and_new_success_proves_only_a_real_previous_home(tmp_path):
    root, cfg, module = fixture(tmp_path, 'return x <= 4')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'old boundary bug')
    base = git(root, 'rev-parse', 'HEAD')
    (root / (module + '.py')).write_text('LIMIT=3\ndef accept(x): return x <= LIMIT\n')
    model = load(cfg)
    result = history.proven(cfg, model.rules['LIMIT'], model.rules['LIMIT'].live_rows[0], base)
    assert result['status'] == 'proven', result
    assert 'actual' in result['homes'][0]


def test_a_still_broken_current_row_cannot_be_proven(tmp_path):
    root, cfg, _ = fixture(tmp_path, 'return x <= 4')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'old bug still present')
    model = load(cfg)
    result = history.proven(cfg, model.rules['LIMIT'], model.rules['LIMIT'].live_rows[0], 'HEAD')
    assert result['status'] == 'unknown' and 'current row does not pass' in result['reason']


def test_old_missing_external_dependency_is_unknown_not_proven(tmp_path):
    root, cfg, module = fixture(tmp_path, "__import__('dependency_not_installed_in_any_environment'); return x <= 4")
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'old environment-dependent code')
    base = git(root, 'rev-parse', 'HEAD')
    (root / (module + '.py')).write_text('def accept(x): return x <= 3\n')
    model = load(cfg)
    result = history.proven(cfg, model.rules['LIMIT'], model.rules['LIMIT'].live_rows[0], base)
    assert result['status'] == 'unknown', result


def test_a_home_absent_previously_is_new_code_not_proven(tmp_path):
    root, cfg, module = fixture(tmp_path)
    path = root / (module + '.py')
    path.write_text('LIMIT=3\n')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'before the home existed')
    base = git(root, 'rev-parse', 'HEAD')
    path.write_text('def accept(x): return x <= 3\n')
    model = load(cfg)
    result = history.proven(cfg, model.rules['LIMIT'], model.rules['LIMIT'].live_rows[0], base)
    assert result['status'] == 'new code', result


def test_literal_data_input_changes_invalidate(tmp_path):
    root, cfg, module = fixture(tmp_path, "return x <= int(Path('limit.txt').read_text())")
    path = root / (module + '.py')
    path.write_text('from pathlib import Path\n' + path.read_text())
    (root / 'limit.txt').write_text('3')
    model = load(cfg)
    graph = build(root)
    saved = deps.record(cfg, model, model.rules['LIMIT'], [], graph)
    assert not saved['reasons']
    assert 'file:limit.txt' in saved['dependencies']
    (root / 'limit.txt').write_text('4')
    assert 'file:limit.txt' in deps.stale(saved, deps.Now(cfg, graph))
    graph.close()


def test_unresolved_data_paths_do_not_reuse_a_green_result(tmp_path):
    root, cfg, module = fixture(tmp_path, "return Path(str(x)+'.txt').read_text()")
    path = root / (module + '.py')
    path.write_text('from pathlib import Path\n' + path.read_text())
    model = load(cfg)
    graph = build(root)
    saved = deps.record(cfg, model, model.rules['LIMIT'], [], graph)
    assert any('dynamic or external data read' in reason for reason in saved['reasons'])
    assert deps.stale(saved, deps.Now(cfg, graph)) == ['no complete reusable result']
    graph.close()


def test_green_star_keeps_row_and_home_changes_in_the_same_moment(tmp_path):
    root, cfg, module = fixture(tmp_path)
    rule_file = cfg.intent / 'limit.py'
    declarations = rule_file.read_text()
    rule_file.unlink()
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'home predates the independent rule')
    rule_file.write_text(declarations)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'add a rule against established code')
    path = root / (module + '.py')
    path.write_text(path.read_text().replace('return x <= LIMIT', 'return x < 4'))
    model = load(cfg)
    assert not history.self_confirmed(cfg, model.rules['LIMIT'], Engine(model))['pending']


def test_green_star_persists_through_unrelated_commits_and_why_only_edits(tmp_path):
    root, cfg, module = fixture(tmp_path)
    rule_file = cfg.intent / 'limit.py'
    declarations = rule_file.read_text()
    rule_file.unlink()
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'before the pair')
    rule_file.write_text(declarations)
    path = root / (module + '.py')
    path.write_text(path.read_text().replace('return x <= LIMIT', 'return x < 4'))
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'row and home changed together')
    (root / 'unrelated.md').write_text('An unrelated edit is not independent confirmation.\n')
    rule_file.write_text(declarations.replace('fixed fourth value', 'same case with clearer words'))
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'unrelated note and clearer row reason')
    model = load(cfg)
    result = history.self_confirmed(cfg, model.rules['LIMIT'], Engine(model))
    assert result['pending'] and result['changed_homes'] == [module + ':accept']


def test_proven_evidence_survives_reason_edits_but_not_a_changed_expected_answer(tmp_path):
    root, cfg, module = fixture(tmp_path, 'return x <= 4')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'previous boundary bug')
    base = git(root, 'rev-parse', 'HEAD')
    (root / (module + '.py')).write_text('def accept(x): return x <= 3\n')
    model = load(cfg)
    rule = model.rules['LIMIT']
    proof = history.proven(cfg, rule, rule.live_rows[0], base)
    assert proof['status'] == 'proven' and proof['base'] == base
    graph = build(root)
    graph.con.execute('CREATE TABLE result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
    graph.con.execute('INSERT INTO result VALUES(?,?,?,?,?)', ('LIMIT[rules]', 'LIMIT', 'ok', json.dumps({'proven_rows': [proof]}), 1))
    graph.con.commit()
    graph.close()
    assert history.confirmation(cfg, rule)['cleared']
    path = cfg.intent / 'limit.py'
    path.write_text(path.read_text().replace('fixed fourth value', 'clearer words for the same case'))
    assert history.confirmation(cfg, load(cfg).rules['LIMIT'])['cleared']
    path.write_text(path.read_text().replace('expect=False', 'expect=True'))
    assert not history.confirmation(cfg, load(cfg).rules['LIMIT'])['cleared']


def test_entered_or_marked_tests_are_not_observed_case_confirmation(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    model = load(cfg)
    graph = build(root)
    graph.con.execute('CREATE TABLE result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
    graph.con.execute('INSERT INTO result VALUES(?,?,?,?,?)', ('LIMIT[cells]', 'LIMIT', 'ok', json.dumps({'footprint': ['sample:accept'], 'marked': True}), 1))
    graph.con.commit()
    graph.close()
    assert not history.confirmation(cfg, model.rules['LIMIT'])['cleared']


def test_saving_proof_does_not_create_a_fake_pass_or_erase_an_older_valid_proof(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    model = load(cfg)
    rule = model.rules['LIMIT']
    graph = build(root)
    graph.con.execute('CREATE TABLE result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
    signature = history.current_row_signature(rule, rule.live_rows[0])
    proof = dict(status='proven', signature=signature, base='a' * 40, homes=[])
    assert not cache.save_proven(graph.con, rule, [proof])
    assert graph.con.execute('SELECT COUNT(*) FROM result').fetchone()[0] == 0
    graph.con.execute('INSERT INTO result VALUES(?,?,?,?,?)', ('LIMIT[rules]', 'LIMIT', 'red', json.dumps({'kind': 'rules', 'verdict': 'red'}), 1))
    assert cache.save_proven(graph.con, rule, [proof])
    assert cache.save_proven(graph.con, rule, [dict(status='regression', signature=signature, base='b' * 40)])
    verdict, encoded = graph.con.execute('SELECT verdict,payload FROM result').fetchone()
    assert verdict == 'red' and json.loads(encoded)['verdict'] == 'red'
    assert json.loads(encoded)['proven_rows'] == [proof]
    graph.close()


def test_pytest_pythonpath_helper_dependencies_use_the_maps_detected_roots(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    tag = root.name
    helpers = root / 'builder_path'
    helpers.mkdir()
    (helpers / f'support_{tag}.py').write_text(f'from values_{tag} import OFFSET\ndef value(x): return x + OFFSET\n')
    deep = helpers / f'values_{tag}.py'
    deep.write_text('OFFSET=0\n')
    project = root / 'pyproject.toml'
    project.write_text(project.read_text() + '\n[tool.pytest.ini_options]\npythonpath=["builder_path"]\n')
    intent = cfg.intent / 'limit.py'
    intent.write_text(f'from support_{tag} import value\n' + intent.read_text().replace('fn(c.x)', 'fn(value(c.x))'))
    model, graph, saved, result = execute(cfg)
    assert not saved['reasons']
    assert any(key.endswith('builder_path/' + deep.name) for key in saved['dependencies'])
    deep.write_text('OFFSET=1\n')
    graph.close()
    graph = build(root)
    assert deps.stale(saved, deps.Now(cfg, graph))
    graph.close()


def test_rewriting_an_sdk_alias_does_not_look_like_deleting_a_marked_test(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    path = cfg.intent / 'limit.py'
    direct = path.read_text()
    path.write_text(direct.replace('from flowguard.intent import rule,row', 'import flowguard.intent as fg\nfrom flowguard.intent import row').replace('@rule(', '@fg.rule('))
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'qualified SDK rule')
    path.write_text(direct)
    assert history.check(cfg, 'HEAD') == []


def test_an_inactive_platform_skipif_does_not_erase_a_marked_guard(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    path = root / 'tests/test_guard.py'
    original = "import pytest as p\n@p.mark.rule('LIMIT')\ndef test_guard(): assert True\n"
    path.write_text(original)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'actual marked guard')
    path.write_text(original.replace('def test_guard()', "@p.mark.skipif(False, reason='platform condition is inactive')\ndef test_guard()"))
    assert history.check(cfg, 'HEAD') == []
    for body in ("\n if False: p.skip('not reached')\n assert True", "p.importorskip('math'); assert True"):
        path.write_text(original.replace('assert True', body))
        assert history.check(cfg, 'HEAD') == []
    for marker in ("@p.mark.skip(reason='disabled')", "@p.mark.skipif(True, reason='disabled')"):
        path.write_text(original.replace('def test_guard()', marker + '\ndef test_guard()'))
        assert any('guard lost' in message for message in history.check(cfg, 'HEAD'))


def test_a_known_module_with_an_unresolved_import_has_a_conservative_test_dependency(tmp_path):
    root, cfg, name = fixture(tmp_path)
    source = root / (name + '.py')
    source.write_text(source.read_text() + f'\ndef optional():\n    from {name} import no_such_export\n    return no_such_export\n')
    (root / 'tests/test_actual.py').write_text(f'from {name} import accept\ndef test_actual(): assert accept(2)\n')
    with closing(build(root)) as graph:
        records = deps.test_dependencies(cfg, graph)
        assert '<unresolved>' in records['tests/test_actual.py']
        assert None not in records['tests/test_actual.py']
        model = load(cfg)
        result = deps.record(cfg, model, model.rules['LIMIT'], [], graph)
        assert any('unresolved import' in reason for reason in result['reasons'])


def test_trace_storage_shares_large_static_sets_and_keeps_old_refs_stale(tmp_path):
    root = tmp_path / 'normalized'
    root.mkdir()
    source = root / 'app.py'
    source.write_text('VALUE = 1\n')
    cfg = load_config(root)
    shared = {'file:absent/dep' + str(n) + '.py': 'gone' for n in range(5000)}
    shared['file:app.py'] = deps.file_digest(source)
    tests = ['tests/test_actual.py::test_case[' + str(n) + ']' for n in range(120)]
    with closing(build(root)) as graph:
        cache.save_trace_signatures(graph.con, ((test, dict(static=shared, observed={}, unknown=False)) for test in tests))
        graph.con.commit()
        first = cache.read(cfg)['traces']
        assert len(first) == len(tests)
        assert len(json.dumps(first)) < 100_000
        current_snapshot = deps.Now(cfg, graph)
        assert all(not deps.trace_changes(record, current_snapshot) for record in first.values())
        cache.save_trace_signatures(graph.con, ((test, dict(static=shared, observed={}, unknown=False)) for test in tests))
        graph.con.commit()
        size = graph.con.execute('PRAGMA page_count').fetchone()[0] * graph.con.execute('PRAGMA page_size').fetchone()[0]
        repeated_json = len(json.dumps(dict(dependencies=shared))) * len(tests)
        assert size < repeated_json // 10
        source.write_text('VALUE = 2\n')
        changed_snapshot = deps.Now(cfg, graph)
        assert all(deps.trace_changes(record, changed_snapshot) for record in first.values())
        new = dict(shared, **{'file:app.py': deps.file_digest(source)})
        cache.save_trace_signatures(graph.con, {tests[0]: dict(static=new, observed={}, unknown=False)}, drop=tests[1:])
        graph.con.commit()
        current = cache.read(cfg)['traces']
        assert list(current) == [tests[0]]
        assert not deps.trace_changes(current[tests[0]], deps.Now(cfg, graph))
        assert deps.trace_changes(first[tests[0]], deps.Now(cfg, graph)), 'a reclaimed group cannot become a different fresh identity'


def test_legacy_trace_json_is_not_loaded_or_treated_as_current(tmp_path):
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    with sqlite3.connect(cfg.cache / 'map.sqlite') as con:
        con.execute('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT)')
        con.execute('INSERT INTO meta VALUES(?,?)', ('intent_trace_signatures', 'unpublished-old-format-not-json'))
    assert cache.read(cfg)['traces'] == {}
