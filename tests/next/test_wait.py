"""FG-814 wait contract and liveness: `check --wait` returns RUNNING with a resume command
inside its wait; the resume reuses finished parts and the running worker; a worker whose
caller is killed (spawning or resumed) stops within seconds; a lease ends it; a job whose
inputs changed is replaced; a failing worker is an internal error."""
from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

from checkrun import gone, group_gone, run_check, start_check, wait_until

SLOW = '''
"""Each step takes a while (a test of the wait contract)."""
import time
from flowguard._next import Model, need

m = Model("slow")
m.field("n", range(0, STEPS), 0)

@m.action()
def tick(s):
    time.sleep(DELAY)
    need(s["n"] < STEPS - 1, "at the end")
    s["n"] += 1

@m.action()
def reset(s):
    need(s["n"] == STEPS - 1, "not at the end")
    s["n"] = 0
MODEL = m
'''

FAST = '''
import os
from flowguard._next import Model
if os.environ.get("FG_TEST_PIDS"):
    with open(os.environ["FG_TEST_PIDS"], "a") as fh:
        fh.write(f"{os.getpid()}\\n")
m = Model("fast")
m.field("on", [False, True], False)

@m.action()
def flip(s):
    s["on"] = not s["on"]
MODEL = m
'''


def slow(project, name="slow", steps=40, delay=0.15):
    """steps * delay seconds of exploring (each state tries tick once)."""
    return project.flow(name, SLOW.replace("STEPS", str(steps)).replace("DELAY", str(delay)))


def jobs_of(root) -> list[Path]:
    """The run directories of every plan, newest last."""
    base = Path(root) / ".flowguard/cache/flow/jobs"
    runs = []
    for plan in base.iterdir() if base.is_dir() else []:
        if plan.is_dir():
            runs += [r for r in plan.iterdir() if r.is_dir()]
    return sorted(runs, key=lambda r: r.name)


def read(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.is_file() else None


def worker_of(root) -> tuple[Path, int]:
    run = jobs_of(root)[-1]
    return run, read(run / "worker.json")["pid"]


def running(run: Path) -> bool:
    st = read(run / "status.json")
    return st is not None and st["state"] == "running"


# ---------------------------------------------------------------------- RUNNING and resume
def test_running_returns_inside_the_wait_and_the_resume_reuses_the_worker(project):
    slow(project, steps=40, delay=0.15)                 # about 6 s
    project.flow("fast", FAST)
    first = run_check(project.root, "--wait", "1")
    assert first.seconds < 4 and first.code == 4
    assert first.first == ("RUNNING: 2 of 4 parts done (fast, fast routes); still exploring slow; "
                           "resume with: python -m flowguard._next check --wait 1")
    assert "fast: complete, 2 states" in first.lines
    assert not (project.root / ".flowguard/conflicts.json").exists()     # RUNNING never writes it
    run, pid = worker_of(project.root)
    assert not gone(pid)
    assert read(run / "status.json")["lease_ms"] is not None          # the handshake was acknowledged

    again = run_check(project.root, "--wait", "1", "--json")
    assert again.seconds < 4 and again.code == 4
    data = again.data
    assert data["verdict"].startswith("RUNNING: 2 of 4 parts done (fast, fast routes)")
    assert data["resume"] == "python -m flowguard._next check --wait 1 --json"
    assert data["running"]["worker"] == pid
    assert [p["cached"] for p in data["parts"]] == [True, True, False, False]   # fast core, routes; slow

    done = run_check(project.root, "--wait", "30", "--json")
    assert done.code == 0, done.out
    data = done.data
    assert data["verdict"] == "clean, complete" and data["resume"] is None
    parts = {(p["model"], p["kind"]): p for p in data["parts"]}
    assert parts["fast", "core"]["cached"] is True and parts["fast", "routes"]["cached"] is True
    assert parts["slow", "core"]["cached"] is False and parts["slow", "core"]["worker"] == pid   # the same worker
    assert parts["slow", "routes"]["worker"] == pid
    assert (project.root / ".flowguard/conflicts.json").is_file()
    assert wait_until(lambda: gone(pid), 5) is not None                # it ends by itself when done
    assert read(run / "status.json")["state"] == "done"
    cached = run_check(project.root, "--json")
    assert all(p["cached"] for p in cached.data["parts"]) and cached.seconds < 3


def test_progress_goes_to_stderr_after_two_seconds(project):
    slow(project, steps=40, delay=0.15)
    run = run_check(project.root, "--wait", "3")
    assert run.code == 4 and run.first.startswith("RUNNING: 0 of 2 parts done; still exploring slow")
    assert run.err.splitlines() == ["check: 0 of 2 parts done; exploring slow"]
    assert run.seconds < 6


def test_the_caller_never_runs_model_code(project, tmp_path):
    project.flow("fast", FAST)
    pids = tmp_path / "pids"
    caller = start_check(project.root, "--json")
    out, err = caller.communicate(timeout=60)
    assert caller.returncode == 0, out + err
    # the model was loaded, but not by the caller; FG_TEST_PIDS is not set there
    os.environ["FG_TEST_PIDS"] = str(pids)
    try:
        project.flow("fast", FAST + "\n# changed\n")
        caller = start_check(project.root, "--json")
        out, _ = caller.communicate(timeout=60)
    finally:
        del os.environ["FG_TEST_PIDS"]
    loaders = {int(x) for x in pids.read_text().split()}
    parts = json.loads(out)["parts"]                     # core and routes, both by the one worker
    assert [p["kind"] for p in parts] == ["core", "routes"]
    assert loaders == {p["worker"] for p in parts} and caller.pid not in loaders


# ---------------------------------------------------------------------- nobody waits: the worker stops
def test_killing_the_spawning_caller_stops_the_worker(project):
    slow(project, "endless", steps=100000, delay=0.01)
    caller = start_check(project.root, "--wait", "60")
    assert wait_until(lambda: jobs_of(project.root) and running(jobs_of(project.root)[-1]), 10) is not None
    run, pid = worker_of(project.root)
    os.kill(caller.pid, signal.SIGKILL)
    caller.wait()
    assert wait_until(lambda: gone(pid) and group_gone(pid), 5) is not None
    assert not (project.root / ".flowguard/conflicts.json").exists()


def test_killing_an_attached_resume_caller_stops_the_worker(project):
    slow(project, "endless", steps=100000, delay=0.01)
    first = run_check(project.root, "--wait", "1")
    assert first.code == 4
    run, pid = worker_of(project.root)
    caller = start_check(project.root, "--wait", "60")
    assert wait_until(lambda: (read(run / "lease.json") or {}).get("pid") == caller.pid, 10) is not None
    time.sleep(1.5)                                    # it renews the lease while it waits
    assert not gone(pid) and worker_of(project.root)[1] == pid
    os.kill(caller.pid, signal.SIGKILL)
    caller.wait()
    assert wait_until(lambda: gone(pid) and group_gone(pid), 5) is not None
    assert read(run / "status.json")["reason"] == "lease expired: nobody waits for the result"


def test_keep_bounds_how_long_running_work_waits_for_a_resume(project):
    slow(project, "endless", steps=100000, delay=0.01)
    first = run_check(project.root, "--wait", "1", "--keep", "2")
    assert first.code == 4
    returned = time.monotonic()
    run, pid = worker_of(project.root)
    time.sleep(1.0)
    assert not gone(pid)                               # the lease holds it for 2 s
    assert wait_until(lambda: gone(pid), 5) is not None
    assert time.monotonic() - returned < 2 + 3
    assert read(run / "status.json")["reason"] == "lease expired: nobody waits for the result"


def test_a_job_whose_inputs_changed_is_replaced(project):
    path = slow(project, "endless", steps=100000, delay=0.01)
    assert run_check(project.root, "--wait", "1").code == 4
    old_run, old = worker_of(project.root)
    slow(project, "endless", steps=5, delay=0.0)       # the AI made the model small
    run = run_check(project.root, "--wait", "20")
    assert run.code == 0 and run.first == "clean, complete"
    assert wait_until(lambda: gone(old), 3) is not None
    new_run, new = worker_of(project.root)
    assert new != old and not old_run.exists()         # its run directory went with it
    assert path.is_file()


# ---------------------------------------------------------------------- locks and failures
def test_a_worker_that_fails_is_an_internal_error(project):
    project.flow("fast", FAST)
    parts = project.root / ".flowguard/cache/flow/parts"
    parts.parent.mkdir(parents=True)
    parts.write_text("not a directory")                # storing the result must fail
    run = run_check(project.root, "--wait", "20")
    assert run.code == 2
    assert run.first.startswith("internal error: the worker failed: part core of fast raised FileExistsError")
    assert len(run.lines) == 1 and "(log: .flowguard/cache/flow/jobs/" in run.first
    log = project.root / run.first.rsplit("(log: ", 1)[1][:-1]
    assert "Traceback (most recent call last)" in log.read_text()
    assert not (project.root / ".flowguard/conflicts.json").exists()
