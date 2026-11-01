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

from flowguard._next import jobs
from flowguard._next.model import load_model
from flowguard._next.parts import PartContext, run_part
from flowguard._next.project import cache_dir, overlap_views, overlaps

from checkrun import REPO, gone, wait_until
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


def test_a_hit_needs_the_same_file_contents_and_every_written_file(project):
    project.kit().flow_from(KIT / "workshop.py")
    path = project.root / ".flowguard/flow/workshop.py"
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
from flowguard._next import Model, need
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
    from flowguard._next.jobs import Lock
    lock_path = tmp_path / "locks" / "x.lock"
    code = ("import sys, time; from flowguard._next.jobs import Lock; "
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
from flowguard._next import jobs
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
    from flowguard._next import diagram
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
from flowguard._next import diagram
text = "flowchart LR\\n" + "\\n".join(f'  n{i}["box {i}"] --> n{i + 1}' for i in range(60))
out = Path(sys.argv[1])
print("go", flush=True)
diagram.render_files([(text, out / f"p{i}") for i in range(40)])
"""


def _descendants(pid):
    parents = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                fields = open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields[0] != "Z":
                parents[int(d)] = int(fields[1])
    out, todo = set(), [pid]
    while todo:
        x = todo.pop()
        kids = [p for p, q in parents.items() if q == x and p not in out]
        out.update(kids)
        todo += kids
    return out


@pytest.mark.skipif(shutil.which("node") is None or not os.path.isdir("/proc"), reason="no node to draw with")
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
