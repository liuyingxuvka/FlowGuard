"""Real public commands after retiring the map/target runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
FLOW = '''from flowguard.flow import Model, need
m=Model("delivery")
m.field("done", (False,True), False)
@m.action()
def finish(s):
    need(not s["done"])
    s["done"]=True
m.terminal("done", (True,))
MODEL=m
'''


def run(root, *args, raw=None):
    environment = {**os.environ, 'PYTHONPATH': str(REPO)}
    environment.pop('CLAUDECODE', None)
    environment.pop('CLAUDE_CODE_SESSION_ID', None)
    return subprocess.run([sys.executable, '-m', 'flowguard', *args], cwd=root,
                          input=raw, capture_output=True, env=environment, timeout=90)


def setup(root, *, broken=False):
    folder = root / '.flowguard/flow'
    folder.mkdir(parents=True)
    (folder / 'delivery.py').write_text(FLOW.replace('m.terminal("done", (True,))\n', '') if broken else FLOW)


def test_public_routes_do_not_import_retired_command_owners(tmp_path):
    script = '''import importlib.abc,sys
class Retired(importlib.abc.MetaPathFinder):
    def find_spec(self,name,path=None,target=None):
        if name in {"flowguard.map.cli","flowguard.map.proof","flowguard.map.target","flowguard.map.targetfile","flowguard.map.plan","flowguard.map.impact_history"}:
            raise AssertionError("retired command owner imported: "+name)
sys.meta_path.insert(0,Retired())
from flowguard.__main__ import main
assert main(["--help"])==0
for name in ["map","target","read","change"]:
    assert main([name])==2
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': str(REPO)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'map <command>' not in result.stdout


def test_adoption_is_the_only_template_and_preserves_existing_owner_files(tmp_path):
    listed = run(tmp_path, 'template', '--list')
    assert listed.returncode == 0 and listed.stdout.strip() == b'adoption'
    written = run(tmp_path, 'template', 'adoption', '--write', str(tmp_path))
    assert written.returncode == 0, written.stderr
    rules = (tmp_path / 'AGENTS.md').read_text()
    assert 'check MODEL' in rules and 'affected checks' in rules
    assert all(old not in rules for old in ['.flowguard/models', 'target', 'legacy map', 'map scan'])
    assert (tmp_path / 'CLAUDE.md').read_text() == '@AGENTS.md\n'
    (tmp_path / 'AGENTS.md').write_text('Owner instruction, keep it.\n')
    assert run(tmp_path, 'template', 'adoption', '--write', str(tmp_path), '--force').returncode == 0
    assert (tmp_path / 'AGENTS.md').read_text() == 'Owner instruction, keep it.\n'
    assert run(tmp_path, 'template', 'behaviour').returncode == 2


def test_status_and_where_ignore_retired_map_target_files_and_do_not_execute_code(tmp_path):
    folder = tmp_path / '.flowguard/target'
    folder.mkdir(parents=True)
    (folder / 'target.json').write_text('{bad legacy state')
    (tmp_path / '.flowguard/map.json').write_text('{bad retired map')
    (tmp_path / 'app.py').write_text('raise AssertionError("source was executed")\ndef do_work(): return 7\n')
    result = run(tmp_path, 'status', '--root', str(tmp_path), '--json')
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert not {'change', 'plan', 'other_changes', 'since_release', 'verdicts'} & data.keys()
    where = run(tmp_path, 'where', 'do_work', '--root', str(tmp_path), '--json')
    assert where.returncode == 0 and b'do_work' in where.stdout, where.stderr


def test_request_bytes_and_nongit_original_snapshot_are_preserved(tmp_path):
    raw = '原文\r\nSecond line.\r\n'.encode()
    result = run(tmp_path, 'req', 'add', '-', '--id', 'R1', '--root', str(tmp_path), raw=raw)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / '.flowguard/requests/R1.md').read_bytes() == raw
    # Current bytes with no independent original fact must not become a baseline.
    (tmp_path / '.flowguard/requests/R2.md').write_text('Unverified current bytes.\n')
    released = run(tmp_path, 'release', '--root', str(tmp_path), '--json')
    assert released.returncode == 0, released.stderr
    from flowguard.map.records import RELEASE_DIR
    saved = json.loads((tmp_path / RELEASE_DIR / 'records.json').read_text())
    assert saved['files']['.flowguard/requests/R1.md'] == hashlib.sha256(raw).hexdigest()
    assert '.flowguard/requests/R2.md' not in saved['files']


def test_release_without_shards_checks_flows_without_collecting_pytest(tmp_path):
    setup(tmp_path)
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_unwanted.py').write_text('raise AssertionError("suite collected without --shards")\n')
    released = run(tmp_path, 'release', '--root', str(tmp_path), '--json')
    assert released.returncode == 0, released.stderr
    data = json.loads(released.stdout)
    assert data['verdict'] == 'PASS' and data['scope']['suite'] == 'not requested'


def test_flow_failure_blocks_explicit_suite_and_snapshot(tmp_path):
    setup(tmp_path, broken=True)
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_suite.py').write_text('from pathlib import Path\ndef test_once():\n    Path("suite_ran").write_text("ran")\n')
    released = run(tmp_path, 'release', '--root', str(tmp_path), '--shards', '1', '--json')
    assert released.returncode == 1, released.stderr
    data = json.loads(released.stdout)
    assert data['verdict'] == 'FAIL' and data['scope']['suite'] == 'not run'
    assert not (tmp_path / 'suite_ran').exists()


def test_one_suite_owner_runs_once_and_a_real_test_failure_blocks_release(tmp_path):
    setup(tmp_path)
    (tmp_path / 'tests').mkdir()
    path = tmp_path / 'tests/test_suite.py'
    path.write_text('from pathlib import Path\ndef test_once():\n    with Path("count.txt").open("a") as f: f.write("once\\n")\n')
    first = run(tmp_path, 'release', '--root', str(tmp_path), '--shards', '1', '--json')
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)['scope']['suite'] == 'passed'
    assert (tmp_path / 'count.txt').read_text() == 'once\n'
    from flowguard.map.records import RELEASE_DIR
    snapshot = (tmp_path / RELEASE_DIR / 'records.json').read_bytes()
    path.write_text('def test_failure():\n    assert False, "actual suite failure"\n')
    second = run(tmp_path, 'release', '--root', str(tmp_path), '--shards', '1', '--json')
    assert second.returncode == 1, second.stderr
    assert any(row['code'] == 'suite_failed' for row in json.loads(second.stdout)['codes'])
    assert (tmp_path / RELEASE_DIR / 'records.json').read_bytes() == snapshot


def test_unreadable_conflict_record_stops_release_without_overwriting_it(tmp_path):
    setup(tmp_path)
    path = tmp_path / '.flowguard/conflicts.json'
    path.write_text('<<<<<<< HEAD\n')
    released = run(tmp_path, 'release', '--root', str(tmp_path), '--shards', '1', '--json')
    assert released.returncode == 2
    assert json.loads(released.stdout)['verdict'] == 'FAIL'
    assert path.read_text() == '<<<<<<< HEAD\n'


def test_status_prints_running_and_the_actual_resume_route(tmp_path):
    setup(tmp_path)
    path = tmp_path / '.flowguard/flow/delivery.py'
    path.write_text('import time\ntime.sleep(0.5)\n' + FLOW)
    pending = run(tmp_path, 'status', '--root', str(tmp_path), '--wait', '0')
    assert pending.returncode == 0, pending.stderr
    assert b'RUNNING: changed model checks; resume with:' in pending.stdout
    resumed = run(tmp_path, 'check', '--root', str(tmp_path), '--wait', '10', '--json')
    assert resumed.returncode == 0 and json.loads(resumed.stdout)['running'] is None, resumed.stdout + resumed.stderr
