from pathlib import Path

from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load


def model(tmp_path, files, query):
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (tmp_path / 'policy.txt').write_text('Exception paths need review.\n')
    intent = tmp_path / 'tests/intent'
    intent.mkdir(parents=True)
    (intent / 'scope.py').write_text('from flowguard.intent import structure_rule\n'
        '@structure_rule("PATHS",source=\'doc policy.txt "Exception paths need review."\')\n'
        'def PATHS(graph):\n    return ' + query + '\n')
    for name, value in files.items():
        (tmp_path / name).write_text(value)
    return load(load_config(tmp_path))


def test_unsupported_query_cannot_certify_empty_foreign_exception_paths(tmp_path):
    m = model(tmp_path, {'service.ts': 'function read(){try { work(); } catch(e){return 0;}}'},
              'list(graph.handlers())')
    result = Engine(m).run_structure(m.structures['PATHS'])
    assert result['verdict'] == 'grey' and result['n'] == 0
    assert any('handlers query incomplete for typescript' in reason for reason in result['grey'])
    assert result['query_coverage']['issues'][0]['files'] == ['service.ts']


def test_explicit_native_scope_keeps_independent_python_contract_usable(tmp_path):
    m = model(tmp_path, {'service.ts': 'function read(){try { work(); } catch(e){return 0;}}',
                         'service.py': 'def read(): return 1\n'},
              'list(graph.handlers(language="python"))')
    result = Engine(m).run_structure(m.structures['PATHS'])
    assert result['verdict'] == 'ok' and result['query_coverage']['complete']


def test_parse_failure_is_not_a_proven_absence_of_forbidden_functions(tmp_path):
    m = model(tmp_path, {'service.ts': 'function broken( {'},
              '[n for n in graph.functions().values() if n["qual"] == "forbidden"]')
    result = Engine(m).run_structure(m.structures['PATHS'])
    assert result['verdict'] == 'grey'
    assert any('parse failed' in reason for reason in result['grey'])


def test_empty_predicate_does_not_certify_a_source_structure(tmp_path):
    m = model(tmp_path, {'service.ts': 'function read(){try { work(); } catch(e){return 0;}}'}, '[]')
    result = Engine(m).run_structure(m.structures['PATHS'])
    assert result['verdict'] == 'grey'
    assert any('queried no source facts' in reason for reason in result['grey'])
    assert not result['query_coverage']['complete']
