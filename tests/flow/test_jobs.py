"""The job system (jobs.py, worker.py) and what the core part records for the caller of
`check`, which runs no model code: the facts for overlap warnings and object names, the
unreduced verification of `--full`, the plan, the cache lookup by content digest, the
watchdog's pipe rule and the locks."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

from flowguard.flow import jobs
from flowguard.flow.model import load_model
from flowguard.flow.parts import PartContext, run_part
from flowguard.flow.project import cache_dir, overlap_views, overlaps

from checkrun import REPO, descendants, gone, wait_until
from conftest import DATA

KIT = DATA / "kit"


def running(run) -> bool:
    status = jobs.read_json(run / "status.json")
    return status is not None and status["state"] == "running"


def core(project, name, **options):
    path = project.root / ".flowguard/flow" / f"{name}.py"
    [item] = [p for p in jobs.plan(project.root, [path], full=options.pop("full", False)) if p.spec.kind == "core"]
    return run_part(PartContext(project.root, item.spec, path, cache_dir(project.root))), item


def test_the_core_part_records_covers_fields_and_objects(project):
    project.kit().flow_from(KIT / "workshop.py")
    result, _ = core(project, "workshop")
    assert result.info["covers"] == ["counter/core.py:Counter"]
    assert result.info["families"] == ["branch", "cond", "rentals"]
    assert result.info["objects"] == {"tool": ["T1", "T2"]}
    assert "symmetry" not in result.info


def test_overlaps_from_recorded_facts_equal_overlaps_from_loaded_models(project):
    project.kit().flow_from(KIT / "workshop.py")
    project.flow("maintenance", (KIT / "workshop.py").read_text())
    flow = project.root / ".flowguard/flow"
    loaded = [load_model(flow / f"{n}.py", project.root) for n in ("workshop", "maintenance")]
    facts = []
    for name in ("workshop", "maintenance"):
        info = core(project, name)[0].info
        facts.append((name, info["families"], info["covers"]))
    assert [f.to_json() for f in overlap_views(facts)] == [f.to_json() for f in overlaps(loaded)]


def test_full_plans_the_unreduced_verification_in_the_core_part(project):
    project.kit().flow_from(KIT / "workshop.py")
    path = project.root / ".flowguard/flow/workshop.py"
    assert [(p.spec.kind, dict(p.spec.options)) for p in jobs.plan(project.root, [path])] == [
        ("core", {"max_states": 200_000}), ("routes", {"max_states": 200_000})]
    assert [(p.spec.kind, dict(p.spec.options)) for p in jobs.plan(project.root, [path], full=True)] == [
        ("core", {"max_states": 200_000, "verify_symmetry": True}), ("routes", {"max_states": 200_000}),
        ("mutate", {"max_states": 200_000})]
    result, _ = core(project, "workshop", full=True)
    assert result.info["symmetry"] == {"verified": True, "text": "symmetry verified (324 states unreduced)"}


@pytest.mark.parametrize("file_reference", [False, True])
def test_a_hit_needs_the_same_file_contents_and_every_written_file(project, file_reference):
    project.kit().flow_from(KIT / "workshop.py")
    path = project.root / ".flowguard/flow/workshop.py"
    if file_reference:
        path.write_text(path.read_text().replace("counter.config:Config", "counter/config.py:Config"))
    item, _ = jobs.plan(project.root, [path])                # core, routes
    assert jobs.lookup(project.root, item) is None          # no manifest yet
    result, _ = core(project, "workshop")
    jobs.store(project.root, result)
    assert jobs.lookup(project.root, item) == result
    config = project.root / "counter/config.py"
    text = config.read_text()
    config.write_text(text + "# changed\n")
    assert jobs.lookup(project.root, item) is None          # a file the load read changed
    config.write_text(text)
    assert jobs.lookup(project.root, item) == result
    stored = jobs.parts_dir(project.root) / f"{result.digest}.json"
    data = json.loads(stored.read_text())
    data["writes"] = [".flowguard/cache/flow/pictures/workshop-x.svg"]
    stored.write_text(json.dumps(data))
    assert jobs.lookup(project.root, item) is None          # a picture it wrote is missing


@pytest.mark.parametrize("file_reference", [False, True])
def test_python_source_newlines_do_not_change_a_cached_part(project, file_reference):
    project.kit().flow_from(KIT / "workshop.py")
    path = project.root / ".flowguard/flow/workshop.py"
    if file_reference:
        path.write_text(path.read_text().replace("counter.config:Config", "counter/config.py:Config"))
    item, _ = jobs.plan(project.root, [path])
    result, _ = core(project, "workshop")
    jobs.store(project.root, result)
    config = project.root / "counter/config.py"
    original = config.read_bytes().replace(b"\r\n", b"\n")
    config.write_bytes(original.replace(b"\n", b"\r\n"))
    assert jobs.lookup(project.root, item) == result


def test_guardian_publishes_lease_expiry_before_native_termination(tmp_path, monkeypatch):
    from flowguard.flow import _process
    job = tmp_path / "job"
    job.mkdir()
    jobs.write_json(job / "status.json", {"state": "running", "reason": None, "current": {"kind": "core"}})
    jobs.write_json(job / "lease.json", {"until_ms": 0, "pid": 42})
    observed = {}
    alive = [True]

    class NativeJob:
        def CloseHandle(self, handle):
            observed.update(jobs.read_json(job / "status.json"))
            alive[0] = False

    monkeypatch.setattr(_process, "_job_for", lambda worker: (NativeJob(), 123))
    monkeypatch.setattr(_process, "windows_pid_alive", lambda pid: alive[0])
    _process._guard(job, 41, 42, None)
    assert observed["state"] == "stopped" and observed["current"] is None
    assert observed["reason"] == "lease expired: nobody waits for the result"


def test_the_plan_digest_names_the_command_not_the_contents(project):
    project.kit().flow_from(KIT / "workshop.py")
    path = project.root / ".flowguard/flow/workshop.py"
    one = jobs.plan_digest(project.root, jobs.plan(project.root, [path]))
    path.write_text(path.read_text() + "\n# edited\n")
    assert jobs.plan_digest(project.root, jobs.plan(project.root, [path])) == one
    assert jobs.plan_digest(project.root, jobs.plan(project.root, [path], max_states=10)) != one


# ---------------------------------------------------------------------- workers and locks
ENDLESS = '''
import time
from flowguard.flow import Model, need
m = Model("endless")
m.field("n", range(0, 100000), 0)

@m.action()
def tick(s):
    time.sleep(0.01)
    need(s["n"] < 99999, "at the end")
    s["n"] += 1
MODEL = m
'''


def test_the_watchdog_stops_a_worker_whose_pipe_closes_without_a_lease(project):
    """The pipe rule alone (the kernel's parent-death signal cannot fire: the test lives)."""
    path = project.flow("endless", ENDLESS)
    planned = jobs.plan(project.root, [path])
    job = jobs._ensure_job(project.root.resolve(), planned)
    assert wait_until(lambda: running(job.dir), 10) is not None
    pid = job.pid()
    job.release()                                      # EOF, no "L" message
    assert wait_until(lambda: gone(pid), 3) is not None
    assert jobs.read_json(job.dir / "status.json")["reason"] == "the caller is gone"


def test_a_lock_is_free_as_soon_as_its_holder_dies(tmp_path):
    from flowguard.flow.jobs import Lock
    lock_path = tmp_path / "locks" / "x.lock"
    code = ("import sys, time; from flowguard.flow.jobs import Lock; "
            f"l = Lock({str(lock_path)!r}); l.acquire(); print('held', flush=True); time.sleep(60)")
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True,
                              env={**os.environ, "PYTHONPATH": str(REPO)})
    assert holder.stdout.readline().strip() == "held"
    mine = Lock(lock_path)
    assert mine.acquire(blocking=False) is False
    assert lock_path.read_text().strip() == str(holder.pid)
    holder.kill()
    holder.wait()
    assert mine.acquire(blocking=False) is True
    mine.release()


CHILD = """
import subprocess, sys, threading, time
from flowguard.flow import jobs
if sys.platform == "win32":
    from flowguard.flow._process import start_guardian
    from pathlib import Path
    import tempfile, os
    start_guardian(Path(tempfile.mkdtemp()), os.getppid())
threading.Thread(target=time.sleep, args=(60,), daemon=True).start()     # a worker runs a watchdog thread
child = subprocess.Popen(jobs.ending_with_this_process([sys.executable, "-c", "import time; time.sleep(60)"]),
                         start_new_session=True)
print(child.pid, flush=True)
time.sleep(60)
"""


def test_a_child_started_by_a_worker_ends_with_it():
    """G6: a process a worker starts in its own session (the picture renderer) gets SIGTERM
    from the kernel when the worker dies, however it dies."""
    parent = subprocess.Popen([sys.executable, "-c", CHILD], stdout=subprocess.PIPE, text=True,
                              env={**os.environ, "PYTHONPATH": str(REPO)})
    child = int(parent.stdout.readline())
    assert not gone(child)
    parent.kill()
    parent.wait()
    assert wait_until(lambda: gone(child), 3) is not None


def test_the_renderer_is_started_without_a_preexec_fn(monkeypatch):
    """#8 (round 2): the worker runs a watchdog thread, and Python documents preexec_fn as
    unsafe in a process with threads (the child can deadlock before exec). The renderer is
    started through a small launcher that arms the parent-death signal itself."""
    from flowguard.flow import diagram
    seen = {}

    class Stop(Exception):
        pass

    def fake(argv, **kw):
        seen.update(kw, argv=argv)
        raise Stop()
    monkeypatch.setattr(diagram.shutil, "which", lambda name: "/usr/bin/node")
    monkeypatch.setattr(diagram.subprocess, "Popen", fake)
    with pytest.raises(Stop):
        diagram.render_files([("flowchart LR\n  a --> b", "/tmp/x")])
    assert "preexec_fn" not in seen and seen["start_new_session"] is True
    if sys.platform.startswith("linux"):
        assert seen["argv"][:2] == [sys.executable, "-I"] and "/usr/bin/node" in seen["argv"]


RENDER = """
import sys
from pathlib import Path
from flowguard.flow import diagram
if sys.platform == "win32":
    from flowguard.flow._process import start_guardian
    import tempfile, os
    start_guardian(Path(tempfile.mkdtemp()), os.getppid())
text = "flowchart LR\\n" + "\\n".join(f'  n{i}["box {i}"] --> n{i + 1}' for i in range(60))
out = Path(sys.argv[1])
print("go", flush=True)
diagram.render_files([(text, out / f"p{i}") for i in range(40)])
"""


def _descendants(pid):
    return descendants(pid)


def test_the_picture_renderer_and_its_browser_end_with_the_worker(tmp_path):
    """G6: the renderer (node) and headless Chromium go when the process drawing dies."""
    parent = subprocess.Popen([sys.executable, "-c", RENDER, str(tmp_path)], stdout=subprocess.PIPE, text=True,
                              env={**os.environ, "PYTHONPATH": str(REPO)})
    assert parent.stdout.readline().strip() == "go"
    assert wait_until(lambda: len(_descendants(parent.pid)) >= 3, 20) is not None   # node and its browser
    kids = _descendants(parent.pid)
    parent.kill()
    parent.wait()
    assert wait_until(lambda: all(gone(k) for k in kids), 3) is not None


class _FakeJob:
    """A worker seen from the caller: its status names a part only after the caller has
    already found that part's result in the cache (the race of a status read just before
    the worker stores a result and says so)."""

    def __init__(self, directory, statuses):
        self.dir = directory
        self.statuses = list(statuses)

    def status(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def alive(self):
        return True

    def pid(self):
        return 4242

    def release(self):
        pass

    def linger(self, keep):
        pass


def test_a_replaced_run_cannot_accept_the_new_runs_complete_cache(project, monkeypatch):
    """The new worker can finish before an old waiting caller polls again."""
    path = project.flow("switch", '''
        from flowguard.flow import Model
        m = Model("switch")
        m.field("on", [False, True], False)
        @m.action()
        def flip(s):
            s["on"] = not s["on"]
        MODEL = m
        ''')
    planned = jobs.plan(project.root, [path])
    ready = {p.id: run_part(PartContext(project.root, p.spec, path, cache_dir(project.root)))
             for p in planned}

    class Replaced(_FakeJob):
        def alive(self):
            return False

        def ended(self, root):
            return "changed", "a newer check took over"

    replacement = Replaced(cache_dir(project.root) / "old", [{"state": "replaced", "parts": {}}])
    calls = []

    def lookup(root, item):
        calls.append(item.id)
        return None if len(calls) <= len(planned) else ready[item.id]

    monkeypatch.setattr(jobs, "lookup", lookup)
    monkeypatch.setattr(jobs, "_ensure_job", lambda *args: replacement)
    result = jobs.run(project.root, planned, wait=1, keep=0)
    assert all(result.results) and not result.finished
    assert result.changed == "a newer check took over" and result.failure is None


def test_a_part_found_between_two_status_reads_is_named_by_its_worker(project, monkeypatch):
    """The reporting race of the round-2 review: the caller read the status, the worker
    stored a part and named it in its status, then the caller found the part in the cache.
    The part was taken with no worker (--json: worker null, cached false) and never looked
    at again. The caller now names the worker that computed it."""
    project.kit().flow_from(KIT / "workshop.py")
    path = project.root / ".flowguard/flow/workshop.py"
    planned = jobs.plan(project.root, [path])
    results = {}
    for item in planned:                         # what the worker computes and stores
        results[item.id] = run_part(PartContext(project.root, item.spec, path, cache_dir(project.root)))
    entries = {item.id: {"digest": results[item.id].digest, "pid": 4242, "cached": False} for item in planned}
    lookups = []

    def lookup(root, item):
        lookups.append(item.id)
        return None if len(lookups) <= len(planned) else results[item.id]     # nothing before the job starts

    job_dir = jobs.jobs_dir(project.root) / "fake" / "run"
    job_dir.mkdir(parents=True)
    fake = _FakeJob(job_dir, [{"state": "running", "parts": {}}, {"state": "done", "parts": entries}])
    monkeypatch.setattr(jobs, "lookup", lookup)
    monkeypatch.setattr(jobs, "_ensure_job", lambda root, planned: fake)
    outcome = jobs.run(project.root, planned, wait=5, keep=0)
    assert outcome.finished
    assert outcome.workers == [4242] * len(planned) and outcome.cached == [False] * len(planned)


GOAL_RAISES = '''
from flowguard.flow import Model, need
m = Model("dial")
m.field("pos", range(0, 3), 0)

@m.action()
def up(s):
    need(s["pos"] < 2, "at the top")
    s["pos"] += 1

@m.action()
def down(s):
    need(s["pos"] > 0, "at the bottom")
    s["pos"] -= 1
m.progress("back to zero", when=lambda s: True, goal=lambda s: 1 / (s["pos"] - 1) and s["pos"] == 0)
MODEL = m
'''


def test_a_check_with_a_model_error_replays_the_stored_conflicts(project):
    """A complete search whose check met a model error (a progress goal that raises) closes
    nothing, so it must replay the stored conflicts like a capped one: the plan holds the
    replay part, and the kept reason comes from the replay, not "no stored path"."""
    path = project.flow("dial", GOAL_RAISES)
    [core_item] = [p for p in jobs.plan(project.root, [path]) if p.spec.kind == "core"]
    result = run_part(PartContext(project.root, core_item.spec, path, cache_dir(project.root)))
    assert result.complete and any(d["kind"] == "MODEL ERROR" for d in result.findings)
    jobs.store(project.root, result)
    stored = {"conflicts": [{"id": "C-000000000001", "kind": "STUCK", "model": "dial", "subject": "pos = 2",
                             "sources": [], "text": "x", "path": ["up()"], "replay": {"stuck": "value",
                                                                                     "key": "pos", "value": "1"}}]}
    kinds = [p.spec.kind for p in jobs.plan(project.root, [path], stored=stored)]
    assert "replay" in kinds, kinds
