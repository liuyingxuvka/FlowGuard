from flowguard.flow.fallback import find_sites, classify, record_tests, disable_probe
from fallback_helpers import _program


def test_empty_alternate_negative_proof_requires_every_actual_invocation(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, """def choose(empty):
    relevant=[]
    fallback=[] if empty else 0
    return relevant or fallback
""", """import subprocess
import sys
from app import choose
def test_choose():
    subprocess.run([sys.executable,'-c','pass'],check=True)
    assert choose(True) == []
    assert choose(False) == 0
""")
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'or-call']
    assert result['recording']['pytest_exitcode'] == 0 and result['capture_status'] == 'unknown'
    assert item['observation_scope']['completed_calls'] == item['observation_scope']['site_executions'] == 2
    observations = item['name_observations']
    assert len({event['call_token'] for event in observations}) == 2
    assert {event['name_truth']['fallback']['type'] for event in observations} == {'builtins:list', 'builtins:int'}
    assert item['classification'] == 'UNKNOWN' and not item['negative_scope_complete'], item
    assert not result['conflicts'] and not result['probes']


def test_operation_index_preserves_actual_raw_evidence_and_partial_scope(tmp_path):
    import json
    from flowguard.flow.fallback import _index_recordings
    source = '''def primary(value):
    return value
def backup():
    return 7
def load(value):
    return primary(value) or backup()
def visible():
    try:
        raise ValueError('visible failure')
    except ValueError:
        raise
def unused():
    try:
        return 3
    except ValueError:
        return 4
'''
    _program(tmp_path, source, 'import pytest\nfrom app import load, visible\ndef test_load():\n    assert load(2) == 2\n    assert load(None) == 7\ndef test_visible():\n    with pytest.raises(ValueError): visible()\n')
    captured = record_tests(tmp_path)
    original = json.dumps(captured, sort_keys=True)
    indexed = _index_recordings(captured['recordings'])
    for status in ('current', 'unknown'):
        for site in find_sites('app.py', source):
            raw = classify(site, captured['recordings'], capture_status=status, test_scope=captured['test_scope'])
            fast = classify(site, indexed, capture_status=status, test_scope=captured['test_scope'])
            assert fast == raw
    assert json.dumps(captured, sort_keys=True) == original


def test_cli_failure_does_not_replace_empty_route_or_unrelated_return_evidence(tmp_path):
    from flowguard.flow.fallback import analyze
    for name, source, expected in (
        ('empty', 'def load():\n    relevant = []\n    fallback = []\n    return relevant or fallback\n', 'DEAD'),
        ('unrelated', 'def primary():\n    raise ValueError("hidden")\ndef load():\n    try:\n        return primary()\n    except ValueError:\n        return 7\n', 'UNKNOWN'),
    ):
        root = tmp_path / name
        root.mkdir()
        _program(root, source + 'def main():\n    load()\n    return 2\n',
                 'from app import main\ndef test_main():\n    assert main() == 2\n')
        (root / 'pyproject.toml').write_text('[project]\nname="cli-fixture"\nversion="0.0.0"\n[project.scripts]\ncli-fixture="app:main"\n')
        result = analyze(root)
        [item] = [row for row in result['sites'] if row['site']['function'] == 'load']
        assert item['classification'] == expected, item
        assert not result['conflicts'] and not result['probes']


def test_direct_input_coalescing_is_counted_but_reassigned_input_is_a_real_route(tmp_path):
    from flowguard.flow.fallback import analyze
    default = tmp_path / 'default'
    default.mkdir()
    _program(default, 'def date(*, source_date, year):\n    return source_date or year\n',
             'from app import date\ndef test_date():\n    assert date(source_date="2026-01-01", year="2026") == "2026-01-01"\ndef test_year():\n    assert date(source_date="", year="2026") == "2026"\n')
    result = analyze(default)
    assert not result['conflicts'], result['conflicts']
    assert result['counts']['input_defaults'] == 1
    computed = tmp_path / 'computed'
    computed.mkdir()
    _program(computed, 'def load(relevant):\n    relevant = []\n    fallback = [7]\n    return relevant or fallback\n',
             'from app import load\ndef test_load():\n    assert load("input replaced by computation") == [7]\n')
    [masked] = analyze(computed)['conflicts']
    assert masked['classification'] == 'MASKING'
    assert masked['probe_confirmed'] == ['tests/test_app.py::test_load']


def test_named_or_keeps_actual_empty_alternate_attempts_dead_in_the_selected_scope(tmp_path):
    from flowguard.flow.fallback import analyze
    source = '''def choose(case):
    relevant = []
    fallback = []
    if case == 'primary':
        relevant.append(1)
    if case == 'alternate':
        fallback.append(2)
    values = relevant or fallback
    if values:
        return values
    return []
'''
    _program(tmp_path, source, '''from app import choose
def test_primary():
    assert choose('primary') == [1]
def test_empty():
    assert choose('empty') == []
def test_alternate():
    assert choose('alternate') == [2]
''')
    [site] = [site for site in find_sites('app.py', source) if site.kind == 'or-call']
    assert site.truth_names == ('relevant', 'fallback')
    partial = analyze(tmp_path, nodeids=['tests/test_app.py::test_primary', 'tests/test_app.py::test_empty'])
    [dead] = [row for row in partial['sites'] if row['site']['id'] == site.id]
    assert dead['classification'] == 'DEAD', dead
    assert dead['alternate_reached'] == ['tests/test_app.py::test_empty']
    assert not dead['alternate'] and dead['negative_scope_complete']
    expanded = analyze(tmp_path)
    [needed] = [row for row in expanded['sites'] if row['site']['id'] == site.id]
    # As for call-valued OR, a confirmed disabled fallback takes MASKING
    # precedence while preserving both observed input-dependent services.
    assert needed['classification'] == 'MASKING', needed
    assert needed['primary'] == ['tests/test_app.py::test_primary']
    assert needed['alternate'] == needed['probe_confirmed'] == ['tests/test_app.py::test_alternate']


def test_named_empty_alternate_dead_scope_excludes_unobserved_child_calls(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def choose():\n    relevant=[]\n    fallback=[]\n    return relevant or fallback\n',
             'import subprocess\nimport sys\nfrom app import choose\ndef test_choose():\n    subprocess.run([sys.executable,"-c","pass"],check=True)\n    assert choose() == []\n')
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'or-call']
    assert result['capture_status'] == 'unknown'
    assert item['classification'] == 'DEAD'
    assert item['scope'] == 'completed observed invocations only'
    scope = item['observation_scope']
    assert scope['calls'] == scope['completed_calls'] == scope['site_executions'] == 1
    assert scope['alternate_attempt_tests'] == 1 and scope['alternate_served_tests'] == 0
    assert not scope['selected_test_scope_complete'] and scope['limits']
    assert not result['conflicts'] and not result['probes']


def test_named_or_masking_requires_the_actual_selected_disable_probe(tmp_path):
    from flowguard.flow.fallback import analyze
    source = 'def choose():\n    relevant = None\n    fallback = [7]\n    return relevant or fallback\n'
    _program(tmp_path, source, 'from app import choose\ndef test_choose():\n    assert choose() == [7]\ndef test_unrelated():\n    assert True\n')
    [masked] = [row for row in analyze(tmp_path)['conflicts'] if row['site']['kind'] == 'or-call']
    assert masked['classification'] == 'MASKING'
    assert masked['probe_confirmed'] == ['tests/test_app.py::test_choose']
    assert masked['primary_failures'][0]['name_truth']['relevant']['truth'] is False
    assert (tmp_path / 'app.py').read_text() == source


def test_named_or_never_calls_custom_truth_or_treats_boolean_values_as_routes(tmp_path):
    from flowguard.flow.fallback import analyze
    source = '''class Dangerous:
    def __bool__(self):
        raise AssertionError('the observer called application truth')
def choose():
    relevant = []
    fallback = Dangerous()
    return relevant or fallback
def flags(left, right):
    return left or right
'''
    _program(tmp_path, source, 'from app import choose, Dangerous, flags\ndef test_choose():\n    assert isinstance(choose(), Dangerous)\ndef test_flags():\n    assert flags(False, True) is True\n')
    result = analyze(tmp_path)
    assert result['recording']['pytest_exitcode'] == 0
    assert not result['conflicts']
    assert {row['classification'] for row in result['sites'] if row['site']['kind'] == 'or-call'} == {'UNKNOWN'}


def test_static_candidates_are_not_confirmed_failures():
    source = '''def load(data):
    try:
        return primary(data)
    except ValueError:
        return backup(data)
'''
    site, = find_sites("app.py", source)
    assert site.kind == "handler"
    assert classify(site, [], capture_status="missing")["classification"] == "UNKNOWN"
    assert classify(site, [], capture_status="current")["classification"] == "UNKNOWN"


def test_same_file_other_function_exception_cannot_confirm_masking():
    source = '''def load():
    try:
        return primary()
    except ValueError:
        return backup()
'''
    site, = find_sites("app.py", source)
    row = {"test": "tests/test_app.py::test_load", "pytest_outcome": "passed", "observer_events": [
        {"path": "app.py", "function": "other", "line": 3, "kind": "exception", "call_token": 1},
        {"path": "app.py", "function": "load", "line": 5, "kind": "statement", "call_token": 2},
        {"path": "app.py", "function": "load", "line": 5, "kind": "return", "call_token": 2}]}
    result = classify(site, [row], capture_status="current")
    assert result["classification"] != "MASKING"


def test_unknown_capture_never_claims_unreached_route():
    site, = find_sites("app.py", "def read(row):\n    return row.get('missing', 3)\n")
    assert site.kind == "input-default"
    assert classify(site, [], capture_status="unknown")["classification"] == "UNKNOWN"


def test_caller_optional_none_is_not_an_implementation_switch():
    assert not find_sites("app.py", "def read(value=None):\n    if value is None:\n        value = compute()\n    return value\n")


def test_bare_pass_is_detected_but_a_propagated_failure_is_visible(tmp_path):
    source = 'def read():\n    try:\n        raise ValueError("visible")\n    except:\n        raise\n'
    _program(tmp_path, source, 'import pytest\nfrom app import read\ndef test_read():\n    with pytest.raises(ValueError): read()\n')
    site, = find_sites("app.py", source)
    result = record_tests(tmp_path)
    assert classify(site, result["recordings"], capture_status=result["capture_status"])["classification"] == "VISIBLE"


def test_real_primary_failure_and_private_disable_probe(tmp_path):
    source = '''def primary():
    raise ValueError("broken primary")

def load():
    try:
        return primary()
    except ValueError:
        return 7
'''
    (tmp_path / "app.py").write_text(source)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_app.py").write_text("from app import load\ndef test_load():\n    assert load() == 7\n")
    site, = find_sites("app.py", source)
    baseline = record_tests(tmp_path)
    assert baseline["pytest_exitcode"] == 0
    initial = classify(site, baseline["recordings"], capture_status=baseline["capture_status"])
    assert initial["primary_failed"]
    assert initial["classification"] == "UNKNOWN"
    probe = disable_probe(tmp_path, site, initial["primary_failed"])
    assert probe["pytest_exitcode"] == 1
    final = classify(site, baseline["recordings"], capture_status=baseline["capture_status"], probe=probe)
    assert final["classification"] == "MASKING"
    assert (tmp_path / "app.py").read_text() == source


def test_same_line_or_uses_actual_false_return_and_selected_backup(tmp_path):
    source = '''def primary():
    return None
def backup():
    return 7
def load():
    return primary() or backup()
'''
    (tmp_path / "app.py").write_text(source)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_app.py").write_text("from app import load\ndef test_load():\n    assert load() == 7\n")
    site, = find_sites("app.py", source)
    baseline = record_tests(tmp_path)
    initial = classify(site, baseline["recordings"], capture_status=baseline["capture_status"])
    assert initial["primary_failed"]
    probe = disable_probe(tmp_path, site, initial["primary_failed"])
    assert classify(site, baseline["recordings"], capture_status=baseline["capture_status"],
                    probe=probe)["classification"] == "MASKING"


def test_live_route_authorization_is_revalidated_not_a_boolean(project):
    from flowguard.map.requests import retire_request
    from flowguard.map.mapfile import MapError
    import pytest
    source = 'def load():\n    try:\n        raise ValueError("old format")\n    except ValueError:\n        return 7\n'
    _program(project.root, source, 'from app import load\ndef test_load():\n    assert load() == 7\n')
    site, = find_sites("app.py", source)
    project.request("R1", "load may use the backup route for old files.\n")
    authorization = {"request": "R1", "quote": "load may use the backup route for old files."}
    rows = record_tests(project.root)["recordings"]
    assert classify(site, rows, capture_status="current", authorization=authorization,
                    root=project.root)["classification"] == "DECLARED"
    retire_request(project.root, "R1")
    with pytest.raises(MapError, match="retired"):
        classify(site, rows, capture_status="current", authorization=authorization, root=project.root)
    with pytest.raises(ValueError, match="stored request"):
        classify(site, rows, capture_status="current", authorization=True, root=project.root)


def test_a_reached_primary_does_not_make_its_unreached_handler_unknown(tmp_path):
    source = 'def load():\n    try:\n        return 7\n    except ValueError:\n        return 8\n'
    _program(tmp_path, source, 'from app import load\ndef test_load():\n    assert load() == 7\n')
    site, = find_sites('app.py', source)
    result = record_tests(tmp_path)
    assert classify(site, result['recordings'], capture_status=result['capture_status'], test_scope=result['test_scope'])['classification'] == 'DEAD'


def test_an_entered_reraising_handler_is_visible(tmp_path):
    source = 'def load():\n    try:\n        raise ValueError("visible")\n    except ValueError:\n        raise\n'
    _program(tmp_path, source, 'import pytest\nfrom app import load\ndef test_load():\n    with pytest.raises(ValueError): load()\n')
    site, = find_sites('app.py', source)
    result = record_tests(tmp_path)
    assert classify(site, result['recordings'], capture_status=result['capture_status'])['classification'] == 'VISIBLE'


def test_structural_near_copy_routes_need_actual_results_from_both(tmp_path):
    source = '''def price(rate, days):
    cost = multiply(rate, days)
    return cost * 80 // 100

def quote(rate, days):
    amount = multiply(rate, days)
    return -(-amount * 80 // 100)

def multiply(a, b): return a * b
'''
    _program(tmp_path, source, 'from app import price, quote\ndef test_price():\n    assert price(3, 1) == 2\ndef test_quote():\n    assert quote(3, 1) == 3\n')
    sites = [site for site in find_sites('app.py', source) if site.kind == 'duplicate']
    assert len(sites) == 1
    result = record_tests(tmp_path)
    classified = classify(sites[0], result['recordings'], capture_status=result['capture_status'])
    assert classified['classification'] == 'BOTH'
    assert classified['primary'] and classified['alternate']


def test_scan_analyze_records_once_and_probes_only_reaching_passing_tests(tmp_path, monkeypatch):
    from flowguard.flow import fallback
    source = 'def load():\n    try:\n        raise ValueError("primary broke")\n    except ValueError:\n        return 7\n'
    _program(tmp_path, source, '''from app import load
+def test_pass():
+    assert load() == 7
+def test_already_failing():
+    assert load() == 8
+def test_unrelated():
+    assert True
+'''.replace('+', ''))
    original, calls = fallback.record_tests, []
    def observed(root, nodeids=None, **kwargs):
        calls.append(nodeids)
        return original(root, nodeids, **kwargs)
    monkeypatch.setattr(fallback, 'record_tests', observed)
    result = fallback.analyze(tmp_path)
    assert calls == [None, ['tests/test_app.py::test_pass']]
    assert [row['classification'] for row in result['conflicts']] == ['MASKING']
    assert result['conflicts'][0]['primary_failures'][0]['exception']['message'] == 'primary broke'
    assert (tmp_path / 'app.py').read_text() == source


def test_skipped_test_scope_is_unknown_not_empty_dead(tmp_path):
    _program(tmp_path, 'def load(): return 1\n', 'import sys, pytest\n@pytest.mark.skipif(sys.platform != "unavailable", reason="scope deliberately absent")\ndef test_unavailable():\n    assert False\n')
    assert record_tests(tmp_path)['capture_status'] == 'unknown'


def test_stale_source_refuses_probe_before_execution(tmp_path, monkeypatch):
    from flowguard.flow import fallback
    import pytest
    source = 'def load():\n    try:\n        raise ValueError("old")\n    except ValueError:\n        return 7\n'
    _program(tmp_path, source, 'from app import load\ndef test_load():\n    assert load() == 7\n')
    site, = find_sites('app.py', source)
    (tmp_path / 'app.py').write_text(source.replace('"old"', '"changed"'))
    monkeypatch.setattr(fallback, 'record_tests', lambda *args, **kwargs: pytest.fail('a stale probe executed'))
    with pytest.raises(ValueError, match='source changed'):
        disable_probe(tmp_path, site, ['tests/test_app.py::test_load'])


def test_defaults_are_aggregate_counts_and_not_conflicts(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def read(row): return row.get("value", 7)\n', 'from app import read\ndef test_read():\n    assert read({}) == 7\n')
    result = analyze(tmp_path)
    assert not result['conflicts']
    assert result['counts']['input_defaults'] == 1


def test_none_result_switch_is_confirmed_through_the_same_probe(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def primary(): return None
def backup(): return 7
def load():
    value = primary()
    if value is None:
        return backup()
    return value
''', 'from app import load\ndef test_load():\n    assert load() == 7\n')
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'none-switch']
    assert item['classification'] == 'MASKING'
    assert item['primary_failures'][0]['result'] == {'status': 'current', 'value': None}


def test_same_basename_on_an_unresolved_receiver_cannot_confirm_or_masking(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''class Other:
    def primary(self): return None
def backup(): return 7
def load():
    other = Other()
    return other.primary() or backup()
''', 'from app import load\ndef test_load():\n    assert load() == 7\n')
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'or-call']
    assert item['classification'] == 'UNKNOWN'
    assert not result['probes']


def test_recursive_invocations_do_not_share_primary_failure_or_return(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load(depth):
    try:
        if depth:
            raise ValueError("outer failed")
        return 2
    except ValueError:
        return load(0)
''', 'from app import load\ndef test_load():\n    assert load(1) == 2\n')
    [item] = analyze(tmp_path)['conflicts']
    assert item['classification'] == 'MASKING'
    tokens = {e['call_token'] for e in item['primary_failures']}
    assert len(tokens) == 1


def test_a_probe_exception_caught_before_an_unrelated_assertion_cannot_confirm(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load():
    try:
        raise ValueError("primary")
    except ValueError:
        return 7
''', '''from app import load
def test_load():
    value = 0
    try:
        value = load()
    except RuntimeError:
        pass
    assert value == 7
''')
    result = analyze(tmp_path)
    assert result['sites'][0]['classification'] == 'UNKNOWN'
    assert not result['conflicts']


def test_probe_preserves_normalized_source_identity_across_crlf(tmp_path):
    source = 'def load():\n    try:\n        raise ValueError("primary")\n    except ValueError:\n        return 7\n'
    _program(tmp_path, source, 'from app import load\ndef test_load():\n    assert load() == 7\n')
    site, = find_sites('app.py', source)
    (tmp_path / 'app.py').write_bytes(source.replace('\n', '\r\n').encode())
    result = disable_probe(tmp_path, site, ['tests/test_app.py::test_load'])
    assert result['capture_status'] == 'current' and result['pytest_exitcode'] == 1


def test_missing_source_during_native_capture_remains_unknown(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def read():\n    try:\n        return 1\n    except Exception:\n        return 2\n', '''from pathlib import Path
import app
def test_read():
    assert app.read() == 1
    Path(app.__file__).unlink()
''')
    result = analyze(tmp_path)
    assert result['capture_status'] == 'unknown'
    assert result['errors'] and all(row['classification'] == 'UNKNOWN' for row in result['sites'])


def test_private_probe_rejects_project_symlink_before_running(tmp_path, monkeypatch):
    from flowguard.flow import fallback
    import pytest
    source = 'def load():\n    try:\n        raise ValueError("primary")\n    except ValueError:\n        return 7\n'
    _program(tmp_path, source, 'from app import load\ndef test_load():\n    assert load() == 7\n')
    external = tmp_path.parent / 'private-external.py'
    external.write_text('UNTOUCHED = True\n')
    # The path check is exercised without requiring symlink creation privileges.
    actual = type(tmp_path).is_symlink
    monkeypatch.setattr(type(tmp_path), 'is_symlink', lambda path: path.name == 'external.py' or actual(path))
    (tmp_path / 'external.py').write_text('UNTOUCHED = True\n')
    site, = find_sites('app.py', source)
    monkeypatch.setattr(fallback, 'record_tests', lambda *args, **kwargs: pytest.fail('unsafe private copy executed'))
    with pytest.raises(ValueError, match='symlink'):
        disable_probe(tmp_path, site, ['tests/test_app.py::test_load'])
    assert external.read_text() == 'UNTOUCHED = True\n'


def test_error_reporting_is_not_a_successful_fallback_just_because_test_passes(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''messages = []
def load():
    try:
        raise ValueError("visible to user")
    except ValueError as error:
        messages.append(str(error))
        return None
''', 'from app import load, messages\ndef test_load():\n    assert load() is None\n    assert messages == ["visible to user"]\n')
    result = analyze(tmp_path)
    assert not result['conflicts']
    assert result['sites'][0]['classification'] == 'UNKNOWN'


def test_exception_status_return_is_not_assumed_to_mean_success(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load():
    try:
        raise SystemExit(2)
    except SystemExit as stop:
        return stop.code
''', 'from app import load\ndef test_load():\n    assert load() == 2\n')
    result = analyze(tmp_path)
    assert not result['conflicts']


def test_logging_before_a_real_alternate_does_not_hide_masking(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def backup(): return 7
def load():
    try:
        raise ValueError("broken primary")
    except ValueError as error:
        print(error)
        return backup()
''', 'from app import load\ndef test_load():\n    assert load() == 7\n')
    assert analyze(tmp_path)['conflicts'][0]['classification'] == 'MASKING'


def test_other_calls_in_the_same_invocation_do_not_belong_to_this_or_site(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def primary(value): return value
def backup(): return 7
def load():
    value = primary(2) or backup()
    primary(None)
    backup()
    return value
''', 'from app import load\ndef test_load():\n    assert load() == 2\n')
    [item] = [row for row in analyze(tmp_path)['sites'] if row['site']['kind'] == 'or-call']
    assert item['classification'] == 'DEAD'
    assert not item['primary_failures'] and not item['alternate_reached']


def test_none_switch_after_early_return_and_expression_switch(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def primary(): return None
def backup(): return 7
def load():
    value = primary()
    if value is not None:
        return value
    return backup()
def expression():
    value = primary()
    return backup() if value is None else value
''', 'from app import load, expression\ndef test_load():\n    assert load() == 7\ndef test_expression():\n    assert expression() == 7\n')
    items = [row for row in analyze(tmp_path)['sites'] if row['site']['kind'] == 'none-switch']
    assert len(items) == 2 and all(row['classification'] == 'MASKING' for row in items)


def test_two_or_sites_on_one_physical_line_remain_unknown(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def primary(value): return value
def backup(): return 7
def load(value):
    first = primary(value) or backup(); second = primary(value) or backup()
    return first + second
''', 'from app import load\ndef test_primary():\n    assert load(2) == 4\ndef test_backup():\n    assert load(None) == 14\n')
    items = [row for row in analyze(tmp_path)['sites'] if row['site']['kind'] == 'or-call']
    assert len(items) == 2 and all(row['classification'] == 'UNKNOWN' for row in items)


def test_reported_exception_reassignment_is_not_a_visibility_waiver(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load():
    try:
        raise ValueError("primary broke")
    except ValueError as error:
        error = "ignore"
        print(error)
        return None
''', 'from app import load\ndef test_load():\n    assert load() is None\n')
    assert analyze(tmp_path)['conflicts'][0]['classification'] == 'MASKING'


def test_pytest_early_stop_cannot_claim_a_complete_dead_scope(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def load():\n    try:\n        return 1\n    except Exception:\n        return 2\n', '''from app import load
def test_first():
    assert False, "stop before the reaching test"
def test_second():
    assert load() == 1
''')
    (tmp_path / 'pytest.ini').write_text('[pytest]\naddopts = -x\n')
    result = analyze(tmp_path)
    assert result['capture_status'] == 'unknown'
    assert result['recording']['test_scope']['finished'] is False
    assert len(result['recording']['test_scope']['collected']) == 2
    assert all(row['classification'] == 'UNKNOWN' for row in result['sites'])


def test_selected_alternate_that_also_crashes_is_not_a_successful_or_fallback(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def primary(): return None
def backup(): raise ValueError("alternate also broke")
def load():
    try:
        return primary() or backup()
    except ValueError:
        return 7
''', 'from app import load\ndef test_load():\n    assert load() == 7\n')
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'or-call']
    assert item['classification'] == 'UNKNOWN'
    assert not item['probe_tests']


def test_native_recording_executes_subject_flowguard_not_cached_engine(tmp_path):
    subject = tmp_path / 'flowguard/map'
    subject.mkdir(parents=True)
    (subject.parent / '__init__.py').write_text('')
    (subject / '__init__.py').write_text('')
    (subject / 'common.py').write_text('def normalize_newlines(value):\n    return "actual subject"\n')
    tests = tmp_path / 'tests'
    tests.mkdir()
    (tests / 'test_subject.py').write_text('from flowguard.map.common import normalize_newlines\ndef test_subject():\n    assert normalize_newlines(None) == "actual subject"\n')
    result = record_tests(tmp_path)
    assert result['pytest_exitcode'] == 0
    assert result['capture_status'] == 'current'
    assert any(event['path'] == 'flowguard/map/common.py' and event['function'] == 'normalize_newlines'
               for row in result['recordings'] for event in row['observer_events'])


def test_unobserved_subject_subprocess_cannot_manufacture_dead_code(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def load():\n    try:\n        return 1\n    except Exception:\n        return 2\n', '''import subprocess, sys
def test_child():
    value = subprocess.check_output([sys.executable, "-c", "from app import load; print(load())"], text=True)
    assert value.strip() == "1"
''')
    result = analyze(tmp_path)
    assert result['capture_status'] == 'unknown'
    assert result['recording']['recordings'][0]['observer_gaps']
    assert all(row['classification'] == 'UNKNOWN' for row in result['sites'])


def test_unrelated_subprocess_gap_does_not_erase_a_confirmed_local_mask(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def load():\n    try:\n        raise ValueError("actual primary")\n    except ValueError:\n        return 7\n', '''import subprocess, sys
from app import load
def test_local():
    assert load() == 7
def test_other_cli():
    subprocess.check_call([sys.executable, "-c", "pass"])
''')
    result = analyze(tmp_path)
    assert result['capture_status'] == 'unknown'
    assert [row['classification'] for row in result['conflicts']] == ['MASKING']
    assert result['conflicts'][0]['probe_tests'] == ['tests/test_app.py::test_local']


def test_partial_scope_keeps_actual_both_and_visible_witnesses(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def scale(value): return value * 3
def price(value):
    amount = scale(value)
    return amount * 80 // 100
def quote(value):
    cost = scale(value)
    return -(-cost * 80 // 100)
def visible():
    try:
        raise ValueError("caller sees it")
    except ValueError:
        raise
''', '''import pytest, subprocess, sys
from app import price, quote, visible
def test_routes():
    assert price(1) == 2 and quote(1) == 3
def test_visible():
    with pytest.raises(ValueError): visible()
def test_other_cli():
    subprocess.check_call([sys.executable, "-c", "pass"])
''')
    result = analyze(tmp_path)
    assert result['capture_status'] == 'unknown'
    assert [row['classification'] for row in result['conflicts']] == ['BOTH']
    assert any(row['classification'] == 'VISIBLE' for row in result['sites'])
    assert all(not row['negative_scope_complete'] for row in result['sites'])


def test_bare_swallowing_handler_is_confirmed_by_actual_probe(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def load():\n    try:\n        raise ValueError("hidden primary")\n    except:\n        pass\n', 'from app import load\ndef test_load():\n    assert load() is None\n')
    [item] = analyze(tmp_path)['conflicts']
    assert item['classification'] == 'MASKING'
    assert item['primary_failures'][0]['exception']['message'] == 'hidden primary'


def test_capture_engine_error_reaches_caller_instead_of_unknown_or_clean(tmp_path, monkeypatch):
    from flowguard.flow import fallback
    from flowguard.native.session import NativeEngineError
    import pytest
    _program(tmp_path, 'def load():\n    try:\n        raise ValueError("hidden")\n    except ValueError:\n        return 7\n', 'from app import load\ndef test_load():\n    assert load() == 7\n')
    def broken_probe(*args, **kwargs):
        raise NativeEngineError('injected capture defect', phase='observer')
    monkeypatch.setattr(fallback, 'disable_probe', broken_probe)
    with pytest.raises(NativeEngineError, match='injected capture defect'):
        fallback.analyze(tmp_path)


def test_ordinary_none_value_branches_are_not_two_implementations(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def show(value):\n    if value is None:\n        return\n    return value\n', 'from app import show\ndef test_none():\n    assert show(None) is None\ndef test_value():\n    assert show(3) == 3\n')
    result = analyze(tmp_path)
    assert not result['conflicts']


def test_none_guard_with_two_actual_implementations_can_be_both(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, 'def primary(): return 2\ndef backup(): return 7\ndef load(choice):\n    if choice is None:\n        return backup()\n    return primary()\n', 'from app import load\ndef test_primary():\n    assert load(True) == 2\ndef test_backup():\n    assert load(None) == 7\n')
    [item] = [row for row in analyze(tmp_path)['conflicts'] if row['site']['kind'] == 'none-switch']
    assert item['classification'] == 'BOTH'


def test_a_changed_test_file_invalidates_all_its_collected_nodeids(tmp_path):
    _program(tmp_path, 'def load(): return 1\n', '''from pathlib import Path
from app import load
def test_first():
    Path(__file__).write_text("def test_first(): pass\\ndef test_second(): pass\\n")
def test_second():
    assert load() == 1
''')
    result = record_tests(tmp_path)
    assert result['capture_status'] == 'unknown'
    assert all(row['binding_status'] == 'unknown' for row in result['recordings'])


def test_native_audit_capture_fault_cannot_become_unknown_collection(tmp_path, monkeypatch):
    from flowguard.native import session
    import pytest
    _program(tmp_path, 'def load(): return 1\n', 'from app import load\ndef test_load():\n    assert load() == 1\n')
    original = session.run_isolated_process
    control = '''from flowguard.native import session as native
original_record = native._Inputs.record
def broken_record(self, event, args, **kwargs):
    if event == "open" and str(args[0]).endswith("app.py"):
        raise RuntimeError("injected audit capture fault")
    return original_record(self, event, args, **kwargs)
native._Inputs.record = broken_record
'''
    def controlled(command, **kwargs):
        command = list(command)
        command[2] = control + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(session, 'run_isolated_process', controlled)
    with pytest.raises(session.NativeEngineError, match='injected audit capture fault'):
        record_tests(tmp_path)


def test_review_later_unrelated_failure_is_not_primary_propagation(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load():
    try:
        raise ValueError("swallowed primary")
    except ValueError:
        pass
    raise RuntimeError("unrelated later failure")
''', '''import pytest
from app import load
def test_load():
    with pytest.raises(RuntimeError, match="unrelated later failure"):
        load()
''')
    [item] = analyze(tmp_path)['sites']
    assert item['primary_failures'][0]['exception']['message'] == 'swallowed primary'
    assert item['classification'] == 'UNKNOWN'
    assert not item['visible']


def test_review_same_line_sibling_call_cannot_establish_both(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def primary(): return 2
def backup(): return 7
def load(extra):
    value = primary() or backup(); backup() if extra else 0
    return value
''', '''from app import load
def test_plain():
    assert load(False) == 2
def test_extra():
    assert load(True) == 2
''')
    result = analyze(tmp_path)
    [item] = [row for row in result['sites'] if row['site']['kind'] == 'or-call']
    assert item['classification'] == 'UNKNOWN'
    assert not result['conflicts']


def test_review_test_rewritten_during_import_has_unknown_binding(tmp_path):
    _program(tmp_path, 'def load(): return 1\n', '''from pathlib import Path
from app import load
Path(__file__).write_text("def test_first(): pass\\ndef test_second(): pass\\n")
def test_first():
    assert load() == 1
def test_second():
    assert load() == 1
''')
    result = record_tests(tmp_path)
    assert len(result['recordings']) == 2
    assert result['binding_status'] == 'unknown'
    assert result['capture_status'] == 'unknown'
    assert all(row['binding_status'] == 'unknown' for row in result['recordings'])


def test_review_collection_subprocess_gap_prevents_dead_claim(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load():
    try:
        raise ValueError("primary")
    except ValueError:
        return 7
''', 'def test_plain():\n    assert True\n')
    (tmp_path / 'tests/conftest.py').write_text('''import subprocess
import sys
from pathlib import Path
subprocess.run([sys.executable, "-c", "import app; app.load()"],
               cwd=Path(__file__).resolve().parents[1], check=True)
''')
    result = analyze(tmp_path)
    [item] = result['sites']
    assert result['capture_status'] == 'unknown'
    assert item['classification'] == 'UNKNOWN'
    assert not item['negative_scope_complete']


def test_collection_calls_are_retained_without_erasing_unrelated_dead_scope(tmp_path):
    from flowguard.flow.fallback import analyze
    _program(tmp_path, '''def load():
    try:
        raise ValueError("collection primary")
    except ValueError:
        return 7
def other():
    try:
        return 1
    except ValueError:
        return 2
''', '''from app import load, other
INITIAL = load()
def test_other():
    assert INITIAL == 7
    assert other() == 1
''')
    result = analyze(tmp_path)
    items = {row['site']['function']: row for row in result['sites'] if row['site']['kind'] == 'handler'}
    assert items['load']['classification'] == 'UNKNOWN'
    assert items['other']['classification'] == 'DEAD'
    events = result['recording']['test_scope']['unassigned_events']
    assert any(event.get('exception', {}).get('message') == 'collection primary' for event in events)
    assert not items['load']['probe_tests']
    assert result['counts']['unreached_handlers'] == 1


def test_function_default_calls_belong_to_the_enclosing_scope(tmp_path):
    from flowguard.flow.fallback import analyze
    source = '''def primary(): return None
def backup(): return 7
def load(value=primary() or backup()):
    return value
'''
    _program(tmp_path, source, 'from app import load\ndef test_load():\n    assert load() == 7\n')
    [item] = [row for row in analyze(tmp_path)['sites'] if row['site']['kind'] == 'or-call']
    assert item['site']['function'] == '<module>'
    assert item['classification'] == 'UNKNOWN'
