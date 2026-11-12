"""Changes that must invalidate evidence, and changes that must stay quiet."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import textwrap
import uuid

import pytest

from flowguard.intent import cache, deps, history
from flowguard.intent.config import load_config
from flowguard.intent.loader import load
from flowguard.intent.engine import Engine
from flowguard.structure import build
from tests.intent_engine._source_fixture import annotate, scenario, source_engine, source_sessions


def git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True).stdout.decode().strip()


def fixture(tmp_path, body='return x <= LIMIT', helper=False):
    root = tmp_path / ('p' + uuid.uuid4().hex)
    root.mkdir()
    name = root.name
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (root / 'policy.txt').write_text('The limit is three.\n')
    code='LIMIT=3\ndef accept(x):\n    '+body+'\ndef unrelated(x):\n    return x + 1\n'
    (root / (name + '.py')).write_text(annotate(code,'accept','LIMIT',{'x':'int'}))
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    intent = f'''from flowguard.intent import rule,row
@rule('LIMIT',decides='allowed',fields={{'x':int}},anchor='LIMIT',source='doc policy.txt "The limit is three."')
def LIMIT(x): return x <= 3
LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))
'''
    if helper:
        (root / 'tests/__init__.py').write_text('')
        (root / 'tests/support.py').write_text('from tests.deep import OFFSET\ndef value(x): return x + OFFSET\n')
        (root / 'tests/deep.py').write_text('OFFSET=0\n')
        code, intent = scenario(root, name, code, intent.replace(",anchor='LIMIT'", ''),
            rule='LIMIT', target='accept', parameters={'x': 'int'}, source_parameters={'x': 'int'},
            body='from tests.support import value\nanswer=app.accept(value(x))\nassert type(answer) is bool')
        (root / (name + '.py')).write_text(code)
    (folder / 'limit.py').write_text(intent)
    cfg = load_config(root)
    return root, cfg, name


def execute(cfg):
    model = load(cfg)
    assert not model.errors, model.errors
    rule = model.rules['LIMIT']
    engine = source_engine(model)
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


def test_unchanged_reuses_but_same_file_body_changes_invalidate(tmp_path):
    root, cfg, module = fixture(tmp_path)
    model, graph, saved, result = execute(cfg)
    assert not saved['reasons']
    assert deps.stale(saved, deps.Now(cfg, graph)) == []
    path = root / (module + '.py')
    path.write_text(path.read_text().replace('return x + 1', 'return x + 99'))
    graph.close()
    graph = build(root)
    assert 'file:' + module + '.py' in deps.stale(saved, deps.Now(cfg, graph))
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
    stale = deps.record(cfg, model, model.rules['LIMIT'], [result], graph)
    assert stale['reasons'], 'new source bytes cannot grant closure from the old Map'
    graph.close()
    graph = build(root, roots=cfg.roots)
    saved = deps.record(cfg, model, model.rules['LIMIT'], [result], graph)
    assert 'file:tests/deep.py' in saved['dependencies']
    deep.write_text('OFFSET=1\n')
    assert 'file:tests/deep.py' in deps.stale(saved, deps.Now(cfg, graph))
    graph.close()


def test_module_initializer_function_is_part_of_module_identity(tmp_path):
    path = tmp_path / 'module.py'
    path.write_text('def compute(): return 3\nLIMIT=compute()\ndef unused(): return 1\n')
    before = deps.file_digest(path)
    path.write_text(path.read_text().replace('unused(): return 1', 'unused(): return 2'))
    changed = deps.file_digest(path)
    assert changed != before, 'file-grained identity includes every function body'
    path.write_text(path.read_text().replace('compute(): return 3', 'compute(): return 4'))
    assert deps.file_digest(path) != changed


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


def test_default_history_keeps_the_task_baseline_after_later_commits(tmp_path):
    root, cfg, _ = fixture(tmp_path)
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'accepted regression')
    baseline = cache.task_start(cfg, record=True)[0]
    path = cfg.intent / 'limit.py'
    path.write_text(path.read_text().replace("LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))\n", ''))
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'remove the accepted row')
    (root / 'note.txt').write_text('an unrelated later commit\n')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'record an unrelated note')
    assert cache.session_baseline(cfg) == baseline
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
    (root / (module + '.py')).write_text(annotate('LIMIT=3\ndef accept(x): return x <= LIMIT\n','accept','LIMIT',{'x':'int'}))
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
    (root / (module + '.py')).write_text(annotate('def accept(x): return x <= 3\n','accept','LIMIT',{'x':'int'}))
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
    path.write_text(annotate('def accept(x): return x <= 3\n','accept','LIMIT',{'x':'int'}))
    model = load(cfg)
    result = history.proven(cfg, model.rules['LIMIT'], model.rules['LIMIT'].live_rows[0], base)
    assert result['status'] == 'new code', result


# The old module's constants are folded as the sealed environments fold theirs (design 4.5, features.fold_step): an
# exponent outside -64..64, a number above 2**256 or a text over 10,000 characters is never computed. The first two
# cases hung and ran out of memory; the others folded although past a bound.
@pytest.mark.parametrize('constant, why', [
    ('BIG = 10 ** 10 ** 10', 'exponent 10000000000 is above 64'),
    ("BIG = 'x' * 10 ** 10", 'text is longer than 10000 characters'),
    ('BIG = 2 ** 65', 'exponent 65 is above 64'),
    ('BIG = 4 ** 64 * 2 ** 64 * 2 ** 64 * 2', 'result is above 2**256'),
    ("BIG = 'x' * 10_001", 'text is longer than 10000 characters'),
    ("BIG = ('x' * 5000) + ('y' * 5001)", 'text is longer than 10000 characters'),
    ('BIG = [0] * 10 ** 10', 'cannot fold list * int'),
])
def test_an_old_constant_past_a_folding_bound_is_not_computed_and_says_why(tmp_path, constant, why):
    root, cfg, module = fixture(tmp_path)
    path = root / (module + '.py')
    path.write_text(f'LIMIT=3\n{constant}\n')
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'before the home existed')
    base = git(root, 'rev-parse', 'HEAD')
    path.write_text(annotate('def accept(x): return x <= 3\n', 'accept', 'LIMIT', {'x': 'int'}))
    model = load(cfg)
    result = history.proven(cfg, model.rules['LIMIT'], model.rules['LIMIT'].live_rows[0], base)
    assert result['status'] == 'unknown' and [home['reason'] for home in result['homes']] == [
        f'old dynamic function binding cannot be restored: old constant BIG is not folded: {why}'], result


def test_old_constants_within_the_folding_bounds_still_fold(tmp_path):
    root, cfg, module = fixture(tmp_path)
    path = root / (module + '.py')
    path.write_text("LIMIT=3\nFACTOR = 10 ** LIMIT\nTOP = 2 ** 64 * 2 ** 64 * 2 ** 64 * 2 ** 64\nNAME = 'x' * 10_000\n"
                    "SHARE = -LIMIT / 4\nTABLE = {'a': (FACTOR, -LIMIT), 'b': [NAME, SHARE, TOP // FACTOR % 7]}\n")
    git(root, 'init', '-q')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'before the home existed')
    base = git(root, 'rev-parse', 'HEAD')
    path.write_text(annotate('def accept(x): return x <= 3\n', 'accept', 'LIMIT', {'x': 'int'}))
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
    assert saved['reasons']
    assert deps.stale(saved, deps.Now(cfg, graph)), 'an unclosed data input cannot reuse a green result'
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
    (root / (module + '.py')).write_text(annotate('def accept(x): return x <= 3\n','accept','LIMIT',{'x':'int'}))
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
    root, cfg, module = fixture(tmp_path)
    tag = root.name
    helpers = root / 'builder_path'
    helpers.mkdir()
    (helpers / f'support_{tag}.py').write_text(f'from values_{tag} import OFFSET\ndef value(x): return x + OFFSET\n')
    deep = helpers / f'values_{tag}.py'
    deep.write_text('OFFSET=0\n')
    project = root / 'pyproject.toml'
    project.write_text(project.read_text() + '\n[tool.pytest.ini_options]\npythonpath=["builder_path"]\n')
    intent = cfg.intent / 'limit.py'
    source = root / (module + '.py')
    original_code = ''.join(line for line in source.read_text().splitlines(True)
                            if not line.lstrip().startswith('# flowguard:'))
    # The scenario test runs once, at the boundary x=3; a scenario is observed only at the input it ran with.
    code, declarations = scenario(root, module, original_code, intent.read_text().replace(",anchor='LIMIT'", ''),
        rule='LIMIT', target='accept', parameters={'x': 'int'}, source_parameters={'x': 'int'}, defaults={'x': '3'},
        body=f'from support_{tag} import value\nanswer=app.accept(value(x))\nassert type(answer) is bool')
    source.write_text(code)
    intent.write_text(declarations)
    model, graph, saved, result = execute(cfg)
    assert not saved['reasons']
    assert any(key.endswith('builder_path/' + deep.name) for key in saved['dependencies'])
    deep.write_text('OFFSET=1\n')
    graph.close()
    graph = build(root)
    assert deps.stale(saved, deps.Now(cfg, graph))
    graph.close()
    # The logical case reaches the test-side helper before the real decision.
    # Replacing the production argument directly would erase this regression.
    _, changed_graph, _, changed = execute(load_config(root))
    assert changed['verdict'] == 'red', changed
    changed_graph.close()


def test_history_reads_the_baseline_from_the_project_root_below_the_repository_top_folder(tmp_path):
    """The project is a folder of a larger repository (a monorepo's app/): its intent and test files at the baseline
    are read from the project's root (a bare `git show rev:tests/x.py` reads from the top folder and is refused), so
    a removed row and a lost guard are found there too, and check runs instead of stopping on Git's refusal."""
    (tmp_path / 'repo').mkdir()
    root, cfg, _ = fixture(tmp_path / 'repo')
    test = root / 'tests/test_guard.py'
    test.write_text("import pytest\n@pytest.mark.rule('LIMIT')\ndef test_guard(): assert True\n")
    top = root.parent
    git(top, 'init', '-q')
    git(top, 'add', '.')
    git(top, 'commit', '-qm', 'baseline')
    assert history.check(cfg, 'HEAD') == []
    test.write_text(test.read_text().replace('assert True', "pytest.skip('lost')"))
    path = cfg.intent / 'limit.py'
    path.write_text(path.read_text().replace("LIMIT.rows(row(x=4,expect=False,why='fixed fourth value'))\n", ''))
    found = history.check(cfg, 'HEAD')
    assert any('row removed' in line for line in found) and any('guard lost' in line for line in found), found


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


def test_unresolved_import_keeps_the_whole_file_dependency_unknown(tmp_path):
    root, cfg, name = fixture(tmp_path)
    source = root / (name + '.py')
    source.write_text(source.read_text() + f'\ndef optional():\n    from {name} import no_such_export\n    return no_such_export\n')
    (root / 'tests/test_actual.py').write_text(f'from {name} import accept\ndef test_actual(): assert accept(2)\n')
    with closing(build(root)) as graph:
        records = deps.test_dependencies(cfg, graph)
        # The one file-level reader does not claim the former per-call scope.
        assert '<unresolved>' in records['tests/test_actual.py']
        assert None not in records['tests/test_actual.py']
        model = load(cfg)
        result = deps.record(cfg, model, model.rules['LIMIT'], [], graph)
        assert any('unresolved import' in reason for reason in result['reasons'])


@pytest.mark.parametrize('where', ['reachable', 'module'])
def test_an_unresolved_import_remains_unknown_when_it_can_execute(tmp_path, where):
    from test_plugin import run
    root, cfg, name = fixture(tmp_path)
    source = root / (name + '.py')
    if where == 'reachable':
        source.write_text(source.read_text() + f'\ndef optional():\n    from {name} import no_such_export\n    return no_such_export\n')
        test = f'from {name} import optional\ndef test_actual(): optional()\n'
    else:
        source.write_text(source.read_text() + f'\nfrom {name} import no_such_export\n')
        test = f'from {name} import accept\ndef test_actual(): assert accept(2)\n'
    (root / 'tests/test_actual.py').write_text(test)
    with closing(build(root)) as graph:
        assert '<unresolved>' in deps.test_dependencies(cfg, graph)['tests/test_actual.py']
    result = run(root, 'tests/test_actual.py')
    assert result.returncode != 0 and 'no_such_export' in result.stdout + result.stderr


def test_legacy_trace_json_is_not_loaded_or_treated_as_current(tmp_path):
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    with sqlite3.connect(cfg.cache / 'map.sqlite') as con:
        con.execute('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT)')
        con.execute('INSERT INTO meta VALUES(?,?)', ('intent_trace_signatures', 'unpublished-old-format-not-json'))
    assert cache.read(cfg)['traces'] == {}
