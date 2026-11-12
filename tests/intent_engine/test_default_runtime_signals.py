"""Round-19 fixed examples, exercised through ordinary project pytest runs.

Each fixture commits the original source before editing it. The project's own
assertions keep passing; observations must reveal the independent difference.
"""
from pathlib import Path
import json
import sqlite3
import re
import subprocess
import sys
import textwrap

from tests.intent_engine._cli_fixture import display_text as _text, last as _last


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                          capture_output=True, text=True, timeout=10).stdout


def _project(root, source, test, *, rule=None):
    (root / 'tests').mkdir(parents=True)
    (root / 'policy.py').write_text(textwrap.dedent(source).lstrip(), encoding='utf-8')
    (root / 'tests/test_case.py').write_text(textwrap.dedent(test).lstrip(), encoding='utf-8')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\ntestpaths=["tests"]\n'
                                       + ('[tool.flowguard]\nauthority_docs=["policy.txt"]\n' if rule else ''))
    if rule:
        (root / 'policy.txt').write_text('At most three days.\n', encoding='utf-8')
        (root / 'tests/intent').mkdir()
        (root / 'tests/intent/decisions.py').write_text(textwrap.dedent(rule).lstrip(), encoding='utf-8')
        (root / 'tests/test_flowguard_intent.py').write_text(
            'def test_flowguard_intent(request):\n'
            '    from flowguard.intent.plugin import sentinel\n'
            '    sentinel(request.config)\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture baseline')
    return root / 'policy.py'


def _run(root, *options):
    source = str(Path(__file__).resolve().parents[2])
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    return subprocess.run([sys.executable, '-c', bootstrap, source, '-q', '-p', 'flowguard.intent.plugin', *options],
                          cwd=root, capture_output=True, text=True, timeout=30)


def _observations(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        row = connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()
    assert row is not None
    return json.loads(row[0])['items']


def _has_change(text):
    return bool(re.search(r'→|->|(?:change|变)', text, re.I))


def test_fixed_1_a_database_call_is_not_compared_and_never_claims_a_complete_green(tmp_path, capsys):
    policy = _project(tmp_path, '''
        import sqlite3
        # flowguard: sensor AVAILABLE(stock: count, reserved: count; db, item_id) -> allowed: bool
        def can_hire(db: sqlite3.Connection, item_id: int, stock: int, reserved: int) -> bool:
            db.execute('SELECT id FROM inventory WHERE id=?', (item_id,)).fetchone()
            return stock > reserved
    ''', '''
        import sqlite3
        from policy import can_hire
        def test_native():
            with sqlite3.connect(':memory:') as db:
                db.execute('CREATE TABLE inventory(id INTEGER)')
                db.execute('INSERT INTO inventory VALUES (7)')
                assert can_hire(db, 7, 4, 2) is True
    ''')
    original = policy.read_text()
    policy.write_text(original.replace('stock > reserved', 'stock >= reserved'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    # The connection argument is not JSON: the call is not compared, and says why (4.5, 6.4).
    assert 'not compared: AVAILABLE (no comparable JSON result) -> not a failure' in text.splitlines(), text
    assert not re.search(r'changed:.*AVAILABLE|AVAILABLE.*classes', text), text
    assert not [item for item in _observations(tmp_path)['items'] if item.get('name') == 'AVAILABLE'], text
    policy.write_text(original)
    reverted = _run(tmp_path)
    assert reverted.returncode == 0, _text(reverted)
    assert 'AVAILABLE' not in _text(reverted), _text(reverted)
    assert _observations(tmp_path)['source_changed'] is False
    assert not _observations(tmp_path)['items']
    compared = _run(tmp_path, '--flowguard-base', 'HEAD')
    compared_text = _text(compared)
    assert compared.returncode == 0, compared_text
    # Nothing changed against HEAD, so nothing is due for a comparison and nothing claims one.
    assert 'AVAILABLE' not in compared_text and not re.search(r'classes，changed', compared_text), compared_text
    report = _observations(tmp_path)
    assert report['source_changed'] is False and report['comparison_requested'] is True
    assert not [item for item in report['items'] if item.get('name') == 'AVAILABLE'], report
    from tests.intent_engine._cli_fixture import main as cli_main
    capsys.readouterr()
    assert cli_main(['--root', str(tmp_path), 'check', '--all', '--base', 'HEAD'], cwd=tmp_path) == 0
    cli_text = _text(capsys.readouterr().out)
    assert not re.search(r'AVAILABLE[^\n]*classes|classes，changed', cli_text), cli_text
    cli_report = _observations(tmp_path)
    assert cli_report['comparison_requested'] and cli_report['source_changed'] is False
    assert not [item for item in cli_report['items'] if item.get('name') == 'AVAILABLE'], cli_report


def test_fixed_2_database_writes_stay_grey_without_replaying_the_effect(tmp_path):
    policy = _project(tmp_path, '''
        import sqlite3
        # flowguard: sensor COUNTED
        def hire_count(db: sqlite3.Connection, stock: int, reserved: int) -> int:
            db.execute('UPDATE calls SET n=n+1')
            return db.execute('SELECT n FROM calls').fetchone()[0]
    ''', '''
        import sqlite3
        from policy import hire_count
        def test_native():
            with sqlite3.connect(':memory:') as db:
                db.execute('CREATE TABLE calls(n INTEGER)')
                db.execute('INSERT INTO calls VALUES (0)')
                assert hire_count(db, 2, 1) == 1
                assert db.execute('SELECT n FROM calls').fetchone()[0] == 1
    ''')
    policy.write_text(policy.read_text().replace("fetchone()[0]", "fetchone()[0] + 0"))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    assert 'not compared: COUNTED (no comparable JSON result) -> not a failure' in text.splitlines(), text


def test_fixed_3_old_function_uses_old_module_constant_on_the_recorded_call(tmp_path):
    policy = _project(tmp_path, '''
        GRACE_DAYS = 3
        # flowguard: sensor STANDING
        def standing(days: int, suspended: bool, owed: int) -> bool:
            return days <= GRACE_DAYS and not suspended and owed <= 20
    ''', '''
        from policy import standing
        def test_native():
            assert standing(0, False, 0) is True
            assert standing(5, False, 0) in (True, False)
    ''')
    policy.write_text(policy.read_text().replace('GRACE_DAYS = 3', 'GRACE_DAYS = 7'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    # The baseline runs with its own GRACE_DAYS = 3, the current source with 7: only days=5 differs.
    assert ('changed: STANDING (policy.py:3): (days=5, suspended=False, owed=0) was False, now True; 1/2 inputs differ '
            '-> if you meant it, say so') in text.splitlines(), text
    item = next(item for item in _observations(tmp_path)['items'] if item.get('name') == 'STANDING')
    assert item['changed'] == [[{'days': 5, 'suspended': False, 'owed': 0}, False, True]], item


def test_fixed_4_changed_function_needs_no_anchor_to_report_member_changes(tmp_path):
    policy = _project(tmp_path, '''
        def late_fee(days: int, member: bool) -> int:
            return max(0, days - 3) if member else days
    ''', '''
        from policy import late_fee
        def test_native():
            assert late_fee(0, False) == 0
            assert late_fee(5, True) in (2, 3)
    ''')
    policy.write_text(policy.read_text().replace('days - 3', 'days - 2'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    assert ('changed: late_fee (policy.py:1): (days=5, member=True) was 2, now 3; 1/2 inputs differ '
            '-> if you meant it, say so') in text.splitlines(), text
    # It has no flowguard comment: compared because its own code changed.
    assert '    no flowguard comment: compared because its code changed' in _last(tmp_path).splitlines()
    item = next(item for item in _observations(tmp_path)['items'] if item.get('name') == 'late_fee')
    assert item['unanchored'] and item['changed'] == [[{'days': 5, 'member': True}, 2, 3]], item


def test_fixed_5_passing_release_test_reports_the_changed_decision_and_records_its_real_path(tmp_path):
    policy = _project(tmp_path, '''
        # flowguard: sensor NEEDS_SAVE
        def needs_save(payload: str) -> bool:
            return bool(payload)
        # flowguard: event SAVED
        def save(payload: str) -> None:
            pass
        # flowguard: event PUBLISHED
        def publish(payload: str) -> bool:
            return True
        # flowguard: event ENTER
        def release(payload: str) -> bool:
            if needs_save(payload):
                save(payload)
            return publish(payload)
    ''', '''
        from policy import release
        def test_release():
            assert release('document') is True
    ''')
    policy.write_text(policy.read_text().replace('return bool(payload)', 'return False'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    assert ("changed: NEEDS_SAVE (policy.py:2): (payload='document') was True, now False; 1/1 inputs differ "
            '-> if you meant it, say so') in text.splitlines(), text
    # The test is not run again with the old code (6.5): no old path, only the real current one.
    assert 'became' not in text, text
    with sqlite3.connect(tmp_path / '.flowguard/cache/map.sqlite') as connection:
        payload = json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])
    calls = [event['anchor'] for event in payload['events']
             if event['case'] == 'tests/test_case.py::test_release' and event['phase'] == 'call']
    assert calls == ['ENTER', 'NEEDS_SAVE', 'PUBLISHED'], payload['events']


def test_fixed_6_same_name_copies_disagree_on_a_real_shared_input(tmp_path):
    policy = _project(tmp_path, '''
        # flowguard: sensor STANDING
        def standing(days: int) -> bool:
            return days <= 3
        # flowguard: sensor STANDING
        def preview(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import standing, preview
        def test_native():
            assert standing(0) is True
            assert preview(0) is True
    ''')
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 7', 1))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 1, text
    assert '1 passed' in result.stdout, text
    # The witness comes from the union of the recorded call (0), its neighbours and the copies' constants.
    assert [line for line in text.splitlines() if line.startswith('red: ')] == [
        'red: same STANDING: on days=7: policy.py:standing returns True, policy.py:preview returns False '
        '-> decide which copy is right, then make the other agree'], text


def test_fixed_7_rule_failure_preserves_its_independent_source_sentence(tmp_path):
    policy = _project(tmp_path, '''
        # flowguard: sensor STANDING
        def standing(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import standing
        def test_native():
            assert standing(0) is True
    ''', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 4'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 1, text
    assert [line for line in text.splitlines() if line.startswith('red: ')] == [
        'red: rule STANDING_RULE: days=4 -> rule F, code True at policy.py:standing (1 of 6 cells disagree) (+1 more) '
        '-> change the code so policy.py:standing follows rule STANDING_RULE'], text
    # The owner's sentence is the red's detail, which show --last prints under it.
    assert '    STANDING_RULE source: At most three days.' in _last(tmp_path).splitlines()


def test_fixed_8_old_values_in_four_copies_include_large_function_interiors(tmp_path):
    source = '''def owner(days: int) -> bool:
    return days <= 14
def preview(days: int) -> bool:
    return days <= 14
def renewal(days: int) -> bool:
    return days <= 14
'''
    for name in ('booking', 'delivery'):
        source += '\ndef '+name+'(days: int) -> bool:\n'
        source += ''.join(f'    work_{number} = {number}\n' for number in range(20))
        source += '    if days <= 14:\n        return True\n'
        source += ''.join(f'    later_{number} = {number}\n' for number in range(20))
        source += '    return False\n'
    policy = _project(tmp_path, source, '''
        from policy import owner, preview, renewal, booking, delivery
        def test_native():
            assert owner(0) and preview(0) and renewal(0) and booking(0) and delivery(0)
    ''')
    changed = policy.read_text().replace('return days <= 14', 'return days <= 21', 1)
    policy.write_text(changed)
    locations = [f'policy.py:{number}' for number, line in enumerate(changed.splitlines(), 1) if 'days <= 14' in line]
    assert len(locations) == 4
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    # A 5.0-deprecated heuristic: no line of the block, the lead only in show --last.
    assert 'old values' not in text and 'deprecated: old-value leads goes in 5.0 -> do not use it' in result.stderr.splitlines(), text
    last = _last(tmp_path).splitlines()
    leads = last[last.index('deprecated leads (5.0):') + 1:]
    lead = next(line for line in leads if 'old values 14 remain in 4 decisions' in line)
    assert all(location in lead for location in locations), last


def test_fixed_9_reused_connection_calls_run_once_each_and_are_not_compared(tmp_path):
    policy = _project(tmp_path, '''
        import sqlite3
        GRACE_DAYS = 3
        # flowguard: sensor STANDING
        def standing(db: sqlite3.Connection, days: int) -> bool:
            debt = db.execute('SELECT amount FROM obligations').fetchone()
            if debt is None:
                return True
            return days <= GRACE_DAYS
    ''', '''
        import sqlite3
        from policy import standing
        def test_native():
            with sqlite3.connect(':memory:') as db:
                db.execute('CREATE TABLE obligations(amount INTEGER)')
                assert standing(db, 0) is True
                db.execute('INSERT INTO obligations VALUES (1)')
                assert standing(db, 0) is True
                assert db.execute('SELECT count(*) FROM obligations').fetchone()[0] == 1
    ''')
    policy.write_text(policy.read_text().replace('GRACE_DAYS = 3', 'GRACE_DAYS = 7'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and '1 passed' in result.stdout, text   # the project's own row count holds
    assert 'not compared: STANDING (no comparable JSON result) -> not a failure' in text.splitlines(), text
    assert not re.search(r'changed:.*STANDING|STANDING[^\n]*classes', text), text
    report = _observations(tmp_path)
    assert not [item for item in report['items'] if item.get('name') == 'STANDING'], report


def test_late_imported_sensor_is_observed_without_eagerly_importing_its_module(tmp_path):
    policy = _project(tmp_path, '''
        GRACE_DAYS = 3
        # flowguard: sensor LATE_STANDING
        def standing(days: int) -> bool:
            return days <= GRACE_DAYS
    ''', '''
        import sys
        def test_native():
            assert 'policy' not in sys.modules
            from policy import standing
            assert standing(0) is True
            assert standing(5) is True
    ''')
    policy.write_text(policy.read_text().replace('GRACE_DAYS = 3', 'GRACE_DAYS = 7'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    assert ('changed: LATE_STANDING (policy.py:3): (days=5) was False, now True; 1/2 inputs differ '
            '-> if you meant it, say so') in text.splitlines(), text


def test_same_name_database_copies_are_compared_in_the_same_real_context(tmp_path):
    policy = _project(tmp_path, '''
        import sqlite3
        GRACE_DAYS = 3
        # flowguard: sensor STANDING
        def standing(db: sqlite3.Connection, days: int) -> bool:
            debt = db.execute('SELECT amount FROM obligations').fetchone()
            return debt is None or days <= GRACE_DAYS
        # flowguard: sensor STANDING
        def preview(db: sqlite3.Connection, days: int) -> bool:
            debt = db.execute('SELECT amount FROM obligations').fetchone()
            return debt is None or days <= GRACE_DAYS
    ''', '''
        import sqlite3
        from policy import standing, preview
        def test_native():
            with sqlite3.connect(':memory:') as clear, sqlite3.connect(':memory:') as owing:
                clear.execute('CREATE TABLE obligations(amount INTEGER)')
                owing.execute('CREATE TABLE obligations(amount INTEGER)')
                owing.execute('INSERT INTO obligations VALUES (1)')
                assert standing(clear, 9) is True
                assert preview(owing, 9) is False
    ''')
    policy.write_text(policy.read_text().replace('GRACE_DAYS = 3', 'GRACE_DAYS = 7'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    assert 'STANDING' in text, text
    assert not re.search(r'^red: |STANDING[^\n]*(?:disagree|inconsistent)', text, re.I | re.M), text


def test_same_name_copy_union_finds_a_baseline_disagreement_and_reports_it_as_before(tmp_path):
    policy = _project(tmp_path, '''
        # flowguard: sensor STANDING
        def owner(days: int) -> bool:
            return False
        # flowguard: sensor STANDING
        def peer(days: int) -> bool:
            return days == 91
    ''', '''
        from policy import owner, peer
        def test_native():
            assert owner(0) is False
            assert peer(0) is False
    ''')
    result = _run(tmp_path)
    text = _text(result)
    # 91, a constant of one copy, is in the compared union; the copies already disagreed there at the
    # baseline, so it is `before`, not red (4.5), and the run passes. A before line needs the change to touch a
    # copy's file (4.7): untouched, the old disagreement says nothing.
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    assert not any(line.startswith(('red: ', 'before: ')) for line in text.splitlines()), text
    policy.write_text(policy.read_text() + '# a documentation-only edit\n')
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    assert [line for line in text.splitlines() if line.startswith(('red: ', 'before: '))] == [
        'before: same STANDING disagreed at task start on days=91: policy.py:owner returns False, policy.py:peer returns True '
        '-> leave it unless your task is about it'], text


def test_fixture_constant_override_never_enters_the_sealed_comparison(tmp_path):
    policy = _project(tmp_path, '''
        LIMIT = 3
        # flowguard: sensor LIMIT_BOUNDARY
        def allowed(days: int) -> bool:
            return days > LIMIT
    ''', '''
        import policy
        def test_native(monkeypatch):
            monkeypatch.setattr(policy, 'LIMIT', 100)
            assert policy.allowed(0) is False
            assert policy.allowed(5) is False
            assert policy.LIMIT == 100
    ''')
    policy.write_text(policy.read_text().replace('LIMIT = 3', 'LIMIT = 7')
                      .replace('days > LIMIT', 'days >= LIMIT'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    # Each version runs on its own source constant (3, then 7), never the fixture's live 100:
    # days=5 was allowed by the baseline and is refused now, though the real call (LIMIT 100) refused it.
    assert ('changed: LIMIT_BOUNDARY (policy.py:3): (days=5) was True, now False; 1/2 inputs differ '
            '-> if you meant it, say so') in text.splitlines(), text
    assert not re.search(r'days\s*[=:]\s*100', text), text
    item = next(item for item in _observations(tmp_path)['items'] if item.get('name') == 'LIMIT_BOUNDARY')
    assert item['changed'] == [[{'days': 5}, True, False]] and item['total'] == 2, item
