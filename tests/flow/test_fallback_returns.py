"""Returned failure values and actual CLI reporting contracts."""

from flowguard.flow.fallback import find_sites, classify
from fallback_helpers import _program


def test_structured_failure_requires_actual_return_fields_and_observed_receiver(tmp_path):
    from flowguard.flow.fallback import analyze
    for name, tail, test, expected in (
        ("visible", 'return {"status": "failed", "exit_code": 2}',
         'result = load()\n    assert result["exit_code"] == 2', "VISIBLE"),
        ("direct", 'return {"status": "failed", "exit_code": 2}',
         'assert load()["exit_code"] == 2', "VISIBLE"),
        ("status_and", 'return {"status": "failed", "exit_code": 2}',
         'result = load()\n    assert result["status"] == "failed" and result["exit_code"] == 2', "VISIBLE"),
        ("status_or", 'return {"status": "failed", "exit_code": 2}',
         'result = load()\n    assert result["status"] == "failed" or result["exit_code"] == 2', "VISIBLE"),
        ("mutated", 'return {"status": "failed", "exit_code": 2}',
         'result = load()\n    result["status"] = "passed"\n    assert result["exit_code"] == 2', "UNKNOWN"),
        ("error_only", 'return {"error": "not a success contract"}',
         'assert load()["error"] == "not a success contract"', "MASKING"),
        ("report", 'return dict(caught=True, error=str(problem))',
         'assert load()["caught"] is True', "UNKNOWN"),
    ):
        root = tmp_path / name
        root.mkdir()
        _program(root, 'def broken():\n    raise ValueError("broken")\ndef load():\n    try:\n        return broken()\n    except ValueError as problem:\n        ' + tail + '\n',
                 'from app import load\ndef test_load():\n    ' + test + '\n')
        result = analyze(root)
        [item] = [row for row in result['sites'] if row['site']['kind'] == 'handler']
        assert item['classification'] == expected, item
        if expected != "MASKING":
            assert not result['conflicts'] and not result['probes']
        if expected == "VISIBLE":
            assert item['structured_returns'][0]['return_fields']['exit_code']['value'] == 2
    ignored = tmp_path / 'ignored'
    ignored.mkdir()
    _program(ignored, 'def broken():\n    raise ValueError("broken")\ndef load():\n    try:\n        return broken()\n    except ValueError:\n        return {"status":"failed","exit_code":2}\ndef main():\n    load()\n    return 0\n',
             'from app import main\ndef test_main():\n    assert main() == 0\n')
    (ignored / 'pyproject.toml').write_text('[project]\nname="structured-cli"\nversion="0.0.0"\n[project.scripts]\nstructured-cli="app:main"\n')
    [masked] = analyze(ignored)['conflicts']
    assert masked['classification'] == 'MASKING'
    assert masked['probe_confirmed'] == ['tests/test_app.py::test_main']


def test_structured_failure_assertion_does_not_admit_implicit_truth_callbacks(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, """def broken():
    raise ValueError('broken')
def load():
    try:
        return broken()
    except ValueError:
        return {'status':'failed','exit_code':2}
""", """from app import load
def test_load():
    result = None
    class Mutator:
        def __bool__(self):
            result['status'] = 'passed'
            return True
    mutator = Mutator()
    result = load()
    assert mutator and result['exit_code'] == 2
""")
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'handler']
    assert result['recording']['pytest_exitcode'] == 0
    assert any(event['function'].endswith('Mutator.__bool__')
               for row in result['recording']['recordings'] for event in row['observer_events'])
    assert item['classification'] == 'UNKNOWN', item
    assert not result['conflicts'] and not result['probes']


def test_opaque_returned_mapping_cannot_be_inferred_to_be_fallback_success(tmp_path):
    from copy import deepcopy
    from flowguard.flow.fallback import analyze
    _program(tmp_path, """class Failure(dict):
    pass
def broken():
    raise ValueError('broken')
def load():
    try:
        return broken()
    except ValueError:
        return Failure(status='failed',exit_code=2)
""", """from app import load
def test_load():
    result=load()
    assert result['exit_code']==2
""")
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'handler']
    assert result['recording']['pytest_exitcode'] == 0
    returned = next(event for row in result['recording']['recordings'] for event in row['observer_events']
                    if event['function'] == 'load' and event['kind'] == 'return')
    assert returned['return_kind'] == 'other' and returned['result']['status'] == 'unknown'
    assert all(fact['status'] == 'unknown' for fact in returned['return_fields'].values())
    assert item['classification'] == 'UNKNOWN', item
    assert not result['conflicts'] and not result['probes']
    old_rows = deepcopy(result['recording']['recordings'])
    for row in old_rows:
        for event in row['observer_events']:
            event.pop('return_kind', None)
    [site] = [site for site in find_sites('app.py', (tmp_path/'app.py').read_text()) if site.kind == 'handler']
    legacy = classify(site, old_rows, capture_status=result['capture_status'],
                      test_scope=result['recording']['test_scope'])
    assert legacy['classification'] == 'UNKNOWN' and not legacy['probe_tests']


def test_packaged_cli_failure_code_is_visible_but_zero_exit_still_masks(tmp_path):
    from flowguard.flow.fallback import analyze
    for exit_code in (2, 0):
        root = tmp_path / str(exit_code)
        root.mkdir()
        expected_output = "invalid input\n" if exit_code else ""
        _program(root, '''def primary():
    raise ValueError('invalid input')
def report(problem):
    print(str(problem))
    return 2
def run():
    try:
        return primary()
    except ValueError as problem:
        return report(problem)
def main():
    code = run()
    return EXIT_CODE
'''.replace('EXIT_CODE', 'code' if exit_code else '0').replace('print(str(problem))', 'print(str(problem))' if exit_code else 'pass'),
            f'from app import main\ndef test_main(capsys):\n    assert main() == {exit_code}\n    assert capsys.readouterr().out == {expected_output!r}\n')
        (root / 'pyproject.toml').write_text('[project]\nname="cli-fixture"\nversion="0.0.0"\n[project.scripts]\ncli-fixture="app:main"\n')
        result = analyze(root)
        [item] = [row for row in result['sites'] if row['site']['kind'] == 'handler']
        assert item['classification'] == ('VISIBLE' if exit_code else 'MASKING'), item
        if exit_code:
            assert item['cli_returns'][0]['result']['value'] == 2
            assert not result['probes']
        else:
            assert item['probe_confirmed'] == ['tests/test_app.py::test_main']


def test_non_cli_numeric_fallback_is_not_licensed_by_its_value_or_error_name(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def primary():\n    raise ValueError("broken")\ndef input_error(problem):\n    return 2\ndef load():\n    try:\n        return primary()\n    except ValueError as problem:\n        return input_error(problem)\n',
             'from app import load\ndef test_load():\n    assert load() == 2\n')
    [item] = analyze(tmp_path)['conflicts']
    assert item['classification'] == 'MASKING'
    assert not item['cli_returns']
    assert item['probe_confirmed'] == ['tests/test_app.py::test_load']


def test_a_cli_with_an_unresolved_exit_result_stays_unknown(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'class ExitResult: pass\ndef primary():\n    raise ValueError("broken")\ndef report(problem):\n    return ExitResult()\ndef main():\n    try:\n        return primary()\n    except ValueError as problem:\n        return report(problem)\n',
             'from app import main, ExitResult\ndef test_main():\n    assert isinstance(main(), ExitResult)\n')
    (tmp_path / 'pyproject.toml').write_text('[project]\nname="cli-fixture"\nversion="0.0.0"\n[project.scripts]\ncli-fixture="app:main"\n')
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'handler']
    assert item['classification'] == 'UNKNOWN', item
    assert not result['conflicts'] and not result['probes']
