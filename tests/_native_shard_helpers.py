"""Actual process and pytest fixtures, independent of a model registry."""
import os, sys, signal, time
from pathlib import Path
import pytest
from flowguard import pytest_shards_cli as shard_runner

def process_cleanup_case(tmp_path, parent_exits):
    pidfile = tmp_path / "child.pid"
    script = (
        "import subprocess,sys,time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"Path({str(pidfile)!r}).write_text(str(child.pid)); "
        + ("sys.exit(0)" if parent_exits else "time.sleep(30)")
    )
    result = shard_runner._run_process(
        [sys.executable, "-c", script], cwd=tmp_path, environment=dict(os.environ),
        stdout_path=tmp_path / "stdout", stderr_path=tmp_path / "stderr",
        timeout_seconds=.5,
    )
    pid = int(pidfile.read_text())
    try:
        if Path(f"/proc/{pid}/stat").exists():
            assert Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
        else:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        if parent_exits:
            assert result["exit_code"] == 0 and result["lingering_killed"] is True
        else:
            assert result["exit_code"] != 0
        assert result["timed_out"] is not parent_exits
        assert result["cleanup_confirmed"] is True
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

def runner_fixture(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'tests').mkdir(exist_ok=True)
    for name in ('one', 'two'):
        (root / ('tests/test_' + name + '.py')).write_text('def test_a(): assert True\ndef test_b(): assert True\n')
    return root

def one_shard(root,case):
    from flowguard.pytest_shards_cli import _run_one_shard
    root=runner_fixture(root)
    if case=='one_fails':(root/'tests/test_one.py').write_text('def test_a(): assert False\ndef test_b(): assert True\n')
    if case=='one_skips':(root/'tests/test_one.py').write_text('import pytest\ndef test_a(): pytest.skip("required")\ndef test_b(): assert True\n')
    nodes=('tests/test_one.py::test_a','tests/test_two.py::test_b')
    environment=dict(os.environ)
    for key in ('FLOWGUARD_PYTEST_COLLECTION_NODEIDS','FLOWGUARD_PYTEST_SHARD_NODEIDS','FLOWGUARD_PYTEST_SHARD_COLLECTION','FLOWGUARD_PYTEST_NODEIDS'):environment.pop(key,None)
    environment['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    environment['PYTHONDONTWRITEBYTECODE']='1'
    environment['PYTHONPATH']=os.pathsep.join(x for x in (str(root),environment.get('PYTHONPATH','')) if x)
    row,projection=_run_one_shard(root=root,environment=environment,shard_index=0,shard_nodeids=nodes,shard_timeout=20,deadline=time.monotonic()+(-1 if case=='past_deadline' else 30),output_root=root/'.flowguard/cache/one-shard')
    return row,projection,nodes
