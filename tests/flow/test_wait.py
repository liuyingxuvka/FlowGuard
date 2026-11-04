"""FG-814 wait contract and liveness: `check --wait` returns RUNNING with a resume command
inside its wait; the resume reuses finished parts and the running worker; a worker whose
caller is killed (spawning or resumed) stops within seconds; a lease ends it; a job whose
inputs changed is replaced; a failing worker is an internal error."""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from checkrun import gone, group_gone, run_check, start_check, wait_until

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
                               reason="S1a flow command waits exercise the Linux-owned worker")

SLOW = '''
"""Each step takes a while (a test of the wait contract)."""
import time
from flowguard.flow import Model, need

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
from flowguard.flow import Model
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
                           "resume with: python -m flowguard check --wait 1")
    assert "fast: complete, 2 states" in first.lines
    assert not (project.root / ".flowguard/conflicts.json").exists()     # RUNNING never writes it
    run, pid = worker_of(project.root)
    assert not gone(pid)
    assert read(run / "status.json")["lease_ms"] is not None          # the handshake was acknowledged

    again = run_check(project.root, "--wait", "1", "--json")
    assert again.seconds < 4 and again.code == 4
    data = again.data
    assert data["verdict"].startswith("RUNNING: 2 of 4 parts done (fast, fast routes)")
    assert data["resume"] == "python -m flowguard check --wait 1 --json"
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
    assert wait_until(lambda: not running(run), 5) is not None       # its status says it ended (G6)
    assert read(run / "status.json")["state"] in ("stopped", "died")


def test_a_worker_that_dies_is_reported_and_never_restarted(project):
    """G6: no hidden restart. A resumed call whose worker is killed says so with the dead
    run's log, starts no new worker, and the dead run's status no longer says running."""
    slow(project, "endless", steps=100000, delay=0.01)
    assert run_check(project.root, "--wait", "1").code == 4
    run, pid = worker_of(project.root)
    caller = start_check(project.root, "--wait", "60")
    assert wait_until(lambda: (read(run / "lease.json") or {}).get("pid") == caller.pid, 10) is not None
    os.kill(pid, signal.SIGKILL)
    out, _ = caller.communicate(timeout=30)
    assert caller.returncode == 2, out
    assert out.startswith(f"internal error: the worker (pid {pid}) died before it finished"), out
    assert len(out.splitlines()) == 1 and "(log: .flowguard/cache/flow/jobs/" in out
    assert (project.root / out.rsplit("(log: ", 1)[1].split(")", 1)[0]).is_file()
    assert jobs_of(project.root) == [run]                              # no second worker
    assert wait_until(lambda: read(run / "status.json")["state"] == "died", 5) is not None
    again = run_check(project.root, "--wait", "1", "--keep", "0")      # a new command starts afresh
    assert again.code == 4 and run.is_dir() and (run / "log").is_file()   # and keeps the dead run's log
    _, last = worker_of(project.root)
    assert wait_until(lambda: gone(last), 5) is not None                 # --keep 0: nothing is left running


def test_a_worker_killed_with_its_whole_group_is_said_to_have_died(project):
    """G6 round 2: kill -9 of the worker's process group takes its death notice with it; the
    waiting call, which saw the worker go, corrects the status (it no longer says running)."""
    slow(project, "endless", steps=100000, delay=0.01)
    assert run_check(project.root, "--wait", "1").code == 4
    run, pid = worker_of(project.root)
    caller = start_check(project.root, "--wait", "60")
    assert wait_until(lambda: (read(run / "lease.json") or {}).get("pid") == caller.pid, 10) is not None
    os.killpg(pid, signal.SIGKILL)
    out, _ = caller.communicate(timeout=30)
    assert caller.returncode == 2 and out.startswith(f"internal error: the worker (pid {pid}) died"), out
    status = read(run / "status.json")
    assert status["state"] == "died" and "process group" in status["reason"] and status["current"] is None
    assert jobs_of(project.root) == [run]


@pytest.mark.parametrize("whole_group", [True, False])
def test_a_lingering_worker_that_dies_is_reported_by_the_resume(project, whole_group):
    """G6 round 3: a worker that dies while it lingers after a RUNNING return (no call waits
    on it) is reported by the resume with the dead run's log; the resume starts no new
    worker, and the dead run's status no longer says running, even when its whole group
    (death notice included) was killed. The call after that one starts afresh."""
    slow(project, "endless", steps=100000, delay=0.01)
    assert run_check(project.root, "--wait", "1", "--keep", "120").code == 4
    run, pid = worker_of(project.root)
    assert wait_until(lambda: running(run) and read(run / "status.json")["lease_ms"] is not None, 5) is not None
    (os.killpg if whole_group else os.kill)(pid, signal.SIGKILL)
    assert wait_until(lambda: not Path(f"/proc/{pid}").exists(), 5) is not None   # reaped, not only a zombie
    time.sleep(0.5)                                    # the death notice, if any, has written
    again = run_check(project.root, "--wait", "2", "--keep", "0")
    assert again.code == 2, again.out
    assert again.first.startswith(f"internal error: the worker (pid {pid}) died before it finished"), again.out
    assert len(again.lines) == 1 and "(log: .flowguard/cache/flow/jobs/" in again.first
    assert jobs_of(project.root) == [run]                              # no second worker
    status = read(run / "status.json")
    assert status["state"] == "died" and status["current"] is None, status
    if whole_group:
        assert "process group" in status["reason"], status
    third = run_check(project.root, "--wait", "1", "--keep", "0")      # said once: a new command starts afresh
    assert third.code == 4, third.out
    assert len(jobs_of(project.root)) == 2 and (run / "log").is_file()


def test_a_worker_stopped_by_its_lease_is_started_again_without_a_word(project):
    """The other side: a worker that stopped because nobody resumed it within --keep ended
    as designed, so the next check simply starts a new one."""
    slow(project, "endless", steps=100000, delay=0.01)
    assert run_check(project.root, "--wait", "1", "--keep", "0").code == 4
    run, pid = worker_of(project.root)
    assert wait_until(lambda: gone(pid), 6) is not None
    assert read(run / "status.json")["state"] == "stopped"
    again = run_check(project.root, "--wait", "1", "--keep", "0")
    assert again.code == 4 and again.first.startswith("RUNNING: "), again.out


def test_a_waiting_check_whose_run_is_replaced_says_so_plainly(project):
    """G6 round 2 (#9): when another check replaces the run because a model file changed, a
    check that waited on the old run says that, with the command that resumes; it is no
    internal error and no death, and the old run keeps its directory and its log."""
    slow(project, "endless", steps=100000, delay=0.01)
    assert run_check(project.root, "--wait", "1").code == 4
    run, pid = worker_of(project.root)
    waiting = start_check(project.root, "--wait", "60")
    assert wait_until(lambda: (read(run / "lease.json") or {}).get("pid") == waiting.pid, 10) is not None
    slow(project, "endless", steps=5, delay=0.0)
    newer = run_check(project.root, "--wait", "20")
    assert newer.code == 0 and newer.first == "clean, complete", newer.out
    out, _ = waiting.communicate(timeout=30)
    assert waiting.returncode == 4, out
    assert out.startswith("RUNNING: not finished: the model files changed while this check waited, and a newer "
                          "check took over; resume with: python -m flowguard check --wait 60"), out
    assert "internal error" not in out and "died" not in out
    assert read(run / "status.json")["state"] == "replaced" and (run / "log").is_file()


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
    assert new != old and read(old_run / "status.json")["state"] == "replaced"   # said, with its log kept
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
