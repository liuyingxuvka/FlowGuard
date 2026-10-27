from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import pytest
from pathlib import Path

import flowguard.pytest_shards_cli as shard_runner


def test_pytest_shard_runner_has_one_absolute_invocation_deadline(tmp_path, monkeypatch):
    """A spent invocation budget blocks before collection and never retries."""

    calls = []

    def unexpected_process(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("the absolute deadline must prevent a producer")

    monkeypatch.setattr(shard_runner, "_run_process", unexpected_process)
    args = argparse.Namespace(
        root=str(tmp_path),
        shards=2,
        collect_timeout=1.0,
        shard_timeout=1.0,
        run_timeout=1e-12,
        parallel_shards=2,
        json=True,
    )

    exit_code, payload = shard_runner.run(args)

    assert exit_code == 70
    assert payload["status"] == "blocked"
    assert payload["deadline"]["remaining_seconds"] == 0.0
    assert calls == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup")
@pytest.mark.parametrize("parent_exits", [False, True])
def test_process_owner_cleans_children_even_after_parent_exit(tmp_path, parent_exits):
    from _fg_helpers import process_cleanup_case
    process_cleanup_case(tmp_path,parent_exits)


def test_default_output_is_a_short_summary(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    (root / "test_one.py").write_text("def test_one():\n    assert True\n")
    monkeypatch.setenv("PYTHONPATH", str(Path(shard_runner.__file__).resolve().parents[1]))
    command = ["--root", str(root), "--shards", "1", "--parallel-shards", "1"]
    monkeypatch.setenv("FLOWGUARD_PYTEST_SHARDS_DIR", str(tmp_path / "summary"))
    assert shard_runner.main(command) == 0
    out = capsys.readouterr().out
    assert out.startswith("balance: duration record covers 0 of 1 tests;") and "status: pass  executed 1 of 1" in out
    assert out.count("status: pass") == 1
    monkeypatch.setenv("FLOWGUARD_PYTEST_SHARDS_DIR", str(tmp_path / "full"))
    assert shard_runner.main([*command, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


@pytest.mark.skipif(os.name == "nt", reason="POSIX session ownership")
@pytest.mark.parametrize("case", ["normal", "outer_timeout", "inner_timeout", "orphan_nested"])
def test_nested_process_helpers_share_one_finite_owner(tmp_path, case):
    from flowguard.map.runner import run_isolated_process
    record = tmp_path / "inner.json"
    delay = 0 if case == "normal" else 30
    inner = ("import json,os,time;from pathlib import Path;"
             f"Path({str(record)!r}).write_text(json.dumps([os.getpid(),os.getpgrp(),os.getsid(0),int(os.environ['_FLOWGUARD_PROCESS_OWNER'].split(':')[1])]));"
             f"print('nested-ok',flush=True);time.sleep({delay})")
    outer = ("import os,sys;from pathlib import Path;"
             "from flowguard.map.runner import run_isolated_process;"
             f"p,t,c=run_isolated_process([sys.executable,'-c',{inner!r}],"
             "cwd=Path.cwd(),env=dict(os.environ),"
             f"timeout={.3 if case == 'inner_timeout' else 20});"
             "raise SystemExit(p.returncode)")
    if case == "orphan_nested":
        worker = "import time;time.sleep(.15);" + outer
        outer = "import subprocess,sys;subprocess.Popen([sys.executable,'-c'," + repr(worker) + "])"
    env = dict(os.environ, PYTHONPATH=str(Path(shard_runner.__file__).resolve().parents[1]))
    # A foreign/stale marker must not make this outside coordinator join or
    # kill its caller's group. The bootstrap installs the actual child owner.
    env["_FLOWGUARD_PROCESS_OWNER"] = "1:1:1"
    result, timed_out, cleaned = run_isolated_process(
        [sys.executable, "-c", outer], cwd=tmp_path, env=env,
        timeout=.8 if case in {"outer_timeout", "orphan_nested"} else 3,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid, group, session, owner_session = json.loads(record.read_text())
    assert session == owner_session and session != pid  # a nested group stays in its owned session
    assert cleaned
    assert timed_out == (case in {"outer_timeout", "orphan_nested"})
    assert (result.returncode == 0) == (case == "normal")
    try:
        assert Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] in {"Z", "X"}
    except FileNotFoundError:
        pass


@pytest.mark.skipif(os.name == "nt", reason="POSIX session ownership")
def test_nested_timeout_kills_only_its_own_child(tmp_path):
    from flowguard.map.runner import run_isolated_process
    outer = ("import os,sys;from pathlib import Path;"
             "from flowguard.map.runner import run_isolated_process;"
             "p,t,c=run_isolated_process([sys.executable,'-c','import time;time.sleep(30)'],"
             "cwd=Path.cwd(),env=dict(os.environ),timeout=.3);"
             "print('outer-survived',p.returncode,t,flush=True)")
    env = dict(os.environ, PYTHONPATH=str(Path(shard_runner.__file__).resolve().parents[1]))
    result, timed_out, cleaned = run_isolated_process(
        [sys.executable, "-c", outer], cwd=tmp_path, env=env, timeout=10,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert not timed_out and cleaned
    assert result.returncode == 0 and "outer-survived 124 True" in result.stdout


def test_inaccessible_process_inventory_does_not_claim_cleanup(monkeypatch):
    from flowguard.map import runner
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.Path, "iterdir", lambda self: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(runner.os, "killpg", lambda *args: None)
    assert runner._group_active(12345)


def test_release_runs_the_whole_suite_in_shards(tmp_path):
    """Whole-suite nodes run once per shard invocation; TESTED_BY remains a separate phase."""
    from collections import Counter

    from flowguard.templates import validator_template_files, write_template_files

    root = tmp_path / "project"
    root.mkdir()
    (root / "shop").mkdir()
    log = tmp_path / "executions.jsonl"
    (root / "shop/orders.py").write_text(
        "def place(order_id, amount):\n"
        "    if not isinstance(order_id, str) or not order_id or len(order_id) > 80 or not isinstance(amount, int):\n"
        "        raise ValueError('bad input')\n"
        "    return 'placed'\n", encoding="utf-8")
    tests = root / "shop/test_orders.py"
    tests.write_text(
        "import json\nimport os\nfrom pathlib import Path\nimport pytest\nfrom shop.orders import place\n\n"
        "def record():\n"
        "    phase = 'suite' if os.environ.get('FLOWGUARD_PYTEST_SHARD_NODEIDS') else 'binding'\n"
        "    node = os.environ['PYTEST_CURRENT_TEST'].rsplit(' (', 1)[0]\n"
        "    with Path(os.environ['FLOWGUARD_RELEASE_TEST_LOG']).open('a', encoding='utf-8') as stream:\n"
        "        stream.write(json.dumps({'phase': phase, 'node': node}) + '\\n')\n\n"
        "def test_place_rejects_bad_input():\n"
        "    record()\n"
        "    assert place('o1', 5) == 'placed'\n"
        "    for order_id, amount in ((None, 5), ('', 5), ('o1', None)):\n"
        "        with pytest.raises(ValueError):\n            place(order_id, amount)\n\n"
        "def test_first():\n    record()\n    assert place('o2', 6) == 'placed'\n\n"
        "def test_second():\n    record()\n    assert place('o3', 7) == 'placed'\n\n"
        "def test_third():\n    record()\n    assert place('o4', 8) == 'placed'\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    files = validator_template_files()
    write_template_files(root, files)
    for file in files:
        path = root / file.path
        source = path.read_text(encoding="utf-8").replace("REPLACE_ME", "shop")
        path.write_text(source, encoding="utf-8")
    data = {"schema": "flowguard.map.v1", "project": "release-shards", "components": [{
        "id": "orders", "summary": "Validate order inputs", "responsibilities": ["reject invalid order inputs"],
        "files": ["shop/orders.py"], "entrypoints": ["shop/orders.py:place"],
        "tests": ["shop/test_orders.py"], "models": [files[0].path], "depends_on": [], "status": "draft"}]}
    map_path = root / ".flowguard/map.json"
    map_path.write_text(json.dumps(data), encoding="utf-8")
    env = os.environ.copy()
    for control in ("FLOWGUARD_PYTEST_COLLECTION_NODEIDS", "FLOWGUARD_PYTEST_SHARD_NODEIDS",
                    "FLOWGUARD_PYTEST_SHARD_COLLECTION", "FLOWGUARD_PYTEST_NODEIDS"):
        env.pop(control, None)
    env["PYTHONPATH"] = str(Path(shard_runner.__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    env["FLOWGUARD_RELEASE_TEST_LOG"] = str(log)

    def invoke(*args):
        return subprocess.run([sys.executable, "-m", "flowguard", *args, "--root", str(root)],
                              cwd=root, env=env, text=True, capture_output=True, check=False)

    confirmed = subprocess.run([sys.executable, "-m", "flowguard", "map", "--root", str(root), "confirm", "all"],
                               cwd=root, env=env, text=True, capture_output=True, check=False)
    assert confirmed.returncode == 0, confirmed.stdout + confirmed.stderr
    expected = {"shop/test_orders.py::" + name for name in (
        "test_place_rejects_bad_input", "test_first", "test_second", "test_third")}
    bound = "shop/test_orders.py::test_place_rejects_bad_input"

    def records():
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def assert_phases():
        observed = records()
        assert Counter(row["node"] for row in observed if row["phase"] == "suite") == Counter(expected)
        # The real bound test calls place under testreach, separately from its one whole-suite call.
        assert Counter(row["node"] for row in observed if row["phase"] == "binding") == Counter({bound: 1})

    env["FLOWGUARD_PYTEST_SHARDS_DIR"] = str(tmp_path / "suite-pass")
    passed = invoke("release", "--shards", "2")
    output = passed.stdout + passed.stderr
    assert passed.returncode == 0, output
    assert "suite: status: pass  executed 4 of 4" in output and "verify: PASS" in output
    assert output.index("suite: ") < output.index("verify: PASS")
    assert_phases()
    aggregate = json.loads((tmp_path / "suite-pass/aggregate.json").read_text(encoding="utf-8"))
    assert aggregate["partition"]["exact_union"] and aggregate["partition"]["disjoint"]
    assert set(aggregate["pytest_execution"]["node_ids"]) == expected
    assert aggregate["executed_count"] == 4 and aggregate["pytest_execution"]["selected"] == 4

    tests.write_text(tests.read_text(encoding="utf-8").replace(
        "assert place('o4', 8) == 'placed'", "assert place('o4', 8) == 'wrong'"), encoding="utf-8")
    log.write_text("", encoding="utf-8")
    env["FLOWGUARD_PYTEST_SHARDS_DIR"] = str(tmp_path / "suite-fail")
    failed = invoke("release", "--shards", "2")
    output = failed.stdout + failed.stderr
    assert failed.returncode == 1, output
    assert "suite: status: fail  executed 4 of 4" in output and "verify: FAIL" in output
    assert_phases()
    aggregate = json.loads((tmp_path / "suite-fail/aggregate.json").read_text(encoding="utf-8"))
    assert aggregate["pytest_execution"]["failed"] == 1 and aggregate["executed_count"] == 4

    data = json.loads(map_path.read_text(encoding="utf-8"))
    data["components"][0]["status"] = "draft"
    map_path.write_text(json.dumps(data), encoding="utf-8")
    log.write_text("", encoding="utf-8")
    env["FLOWGUARD_PYTEST_SHARDS_DIR"] = str(tmp_path / "suite-not-run")
    blocked = invoke("release", "--shards", "2")
    output = blocked.stdout + blocked.stderr
    assert blocked.returncode == 1, output
    assert "suite: not run (fix the failures above first)" in output and "verify: FAIL" in output
    assert not (tmp_path / "suite-not-run").exists()
    assert all(row["phase"] == "binding" for row in records())

    from contextlib import redirect_stdout,redirect_stderr
    from io import StringIO
    from unittest.mock import patch
    from flowguard.__main__ import main
    direct_dir=tmp_path/'suite-direct-blocked'
    direct=StringIO()
    log.write_text('',encoding='utf-8')
    with patch.dict(os.environ,{'FLOWGUARD_RELEASE_TEST_LOG':str(log),'FLOWGUARD_PYTEST_SHARDS_DIR':str(direct_dir)}):
        with redirect_stdout(direct),redirect_stderr(direct):code=main(['release','--root',str(root),'--shards','2'])
    assert code==1 and 'suite: not run (fix the failures above first)' in direct.getvalue(),direct.getvalue()
    assert not direct_dir.exists() and all(row['phase']=='binding' for row in records())


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux nested process-group ownership')
def test_process_owner_cleans_nested_children_after_parent_exit(tmp_path):
    from flowguard.map.runner import run_isolated_process
    helper_root=Path(__file__).parent
    env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(helper_root),str(helper_root.parent)]))
    command="from pathlib import Path;import sys;from _fg_helpers import process_cleanup_case;process_cleanup_case(Path(sys.argv[1]),True)"
    result,timed_out,cleaned=run_isolated_process([sys.executable,'-c',command,str(tmp_path)],cwd=tmp_path,env=env,timeout=10,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert cleaned and not timed_out
    assert result.returncode==0,result.stderr


def _duration_project(root,cases=2):
    root.mkdir(parents=True,exist_ok=True);(root/'tests').mkdir(exist_ok=True)
    for name in ('one','two'):
        (root/'tests'/('test_'+name+'.py')).write_text('import pytest\n@pytest.mark.parametrize("value",range('+str(cases)+'))\ndef test_value(value): assert value>=0\n')
    return shard_runner.build_parser().parse_args(['--root',str(root),'--shards','2'])


def test_no_partial_or_corrupt_record_uses_the_hash_line(tmp_path):
    args=_duration_project(tmp_path,cases=25)
    code,first=shard_runner.run(args)
    assert code==0 and first['balance']=='hash'
    assert 'duration record covers 0 of 50 tests; hash partition this run' in shard_runner._summary(first)
    path=tmp_path/'.flowguard/cache/test-durations.json';record=json.loads(path.read_text())
    for node in list(record['seconds'])[:3]:record['seconds'].pop(node)  # 6 percent unknown
    path.write_text(json.dumps(record));code,partial=shard_runner.run(args)
    assert code==0 and partial['balance']=='hash' and 'covers 47 of 50 tests' in shard_runner._summary(partial)
    path.write_text('{bad record');code,corrupt=shard_runner.run(args)
    assert code==0 and corrupt['balance']=='hash'
    record=json.loads(path.read_text())
    for node in list(record['seconds'])[:2]:record['seconds'].pop(node)
    path.write_text(json.dumps(record));code,nearly_full=shard_runner.run(args)
    assert code==0 and nearly_full['balance']=='seconds'
    assert nearly_full['partition']['algorithm']=='subtree-lpt-v2'


def test_moved_test_file_keeps_its_weights(tmp_path):
    from flowguard.map.testtree import duration_weights
    args=_duration_project(tmp_path)
    assert shard_runner.run(args)[0]==0
    path=tmp_path/'.flowguard/cache/test-durations.json';record=json.loads(path.read_text())
    original='tests/test_one.py::test_value[0]';record['seconds'][original]=3.0
    record['seconds']['tests/test_two.py::test_value[0]']=.5
    path.write_text(json.dumps(record))
    (tmp_path/'tests/test_one.py').rename(tmp_path/'tests/test_renamed.py')
    renamed='tests/test_renamed.py::test_value[0]'
    assert duration_weights(tmp_path,[renamed])[renamed]==3.0
    code,payload=shard_runner.run(args)
    assert code==0 and payload['balance']=='seconds' and payload['partition']['exact_union']


def test_entry_of_a_changed_file_is_ignored(tmp_path):
    from flowguard.map.testtree import duration_weights
    args=_duration_project(tmp_path)
    assert shard_runner.run(args)[0]==0
    path=tmp_path/'tests/test_one.py';path.write_text(path.read_text()+'# source changed\n')
    node='tests/test_one.py::test_value[0]'
    assert node not in duration_weights(tmp_path,[node])
    code,payload=shard_runner.run(args)
    assert code==0 and payload['balance']=='hash' and 'covers 2 of 4 tests' in shard_runner._summary(payload)


def test_record_is_written_after_a_run_and_not_when_blocked(tmp_path):
    args=_duration_project(tmp_path)
    code,payload=shard_runner.run(args)
    assert code==0 and payload['balance']=='hash'
    path=tmp_path/'.flowguard/cache/test-durations.json';record=json.loads(path.read_text())
    assert record['schema']=='flowguard.test_durations.v1' and len(record['files'])==2 and len(record['seconds'])==4
    assert all(value>=0 for value in record['seconds'].values())
    before=(path.read_bytes(),path.stat().st_mtime_ns)
    (tmp_path/'tests/test_bad.py').write_text('def test_bad(:\n')
    code,blocked=shard_runner.run(args)
    assert code==70 and blocked['status']=='blocked'
    assert (path.read_bytes(),path.stat().st_mtime_ns)==before


def test_suite_fails_when_one_shard_fails(tmp_path):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    target__target_life_cycle_fixture_helpers('_testtree_fixture')['runner_fixture'](tmp_path)
    (tmp_path/'tests/test_one.py').write_text('def test_a(): assert False\ndef test_b(): assert True\n')
    code,payload=shard_runner.run(shard_runner.build_parser().parse_args(['--root',str(tmp_path),'--shards','2']))
    assert code!=0 and payload['status']=='fail'
    assert any(row['status']=='fail' for row in payload['shards'])
    assert payload['pytest_execution']['failed']==1


@pytest.mark.parametrize('case,expected',(('all_pass','pass'),('one_fails','fail'),('one_skips','partial')))
def test_one_shard_status_follows_its_tests(tmp_path,case,expected):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    row,projection,nodes=target__target_life_cycle_fixture_helpers('_shard_fixture')['one_shard'](tmp_path,case)
    assert row['status']==expected
    assert row['executed_count']==len(nodes)
    assert projection['failed']==int(case=='one_fails')


def test_one_shard_past_its_deadline_is_a_timeout(tmp_path):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    row,projection,nodes=target__target_life_cycle_fixture_helpers('_shard_fixture')['one_shard'](tmp_path,'past_deadline')
    assert row['status']=='blocked' and row['deadline_exhausted']
    assert row['executed_count']==0 and projection is None
    assert not Path(row['stdout_path']).exists()


def test_one_shard_runs_exactly_its_nodes(tmp_path):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    row,projection,nodes=target__target_life_cycle_fixture_helpers('_shard_fixture')['one_shard'](tmp_path,'all_pass')
    assert row['status']=='pass' and row['exact_selection']
    assert row['requested_count']==row['selected_count']==row['executed_count']==len(nodes)
    assert set(projection['node_ids'])==set(nodes)
