"""Three short native backend controls; draft only until FG705 source authorization."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

from flowguard.behave import jobs
from flowguard.map.common import child_import_path

ENGINE_ROOT = Path(__file__).resolve().parents[2]
PROGRAM = '''from pathlib import Path
class Refusal(Exception): pass
class Program:
    def __init__(self):
        self._units = []
        self._value = 0
        self._data = Path(__file__).with_name("data.txt").read_text()
    def add_unit(self, unit_id, name): self._units.append(unit_id)
    def units(self): return list(self._units)
    def advance(self, unit_id): self._value += 1
    def value(self, unit_id): return self._value
    def status(self, unit_id): return "ready" if self._value else "new"
'''


def execute(job, writer, deadline):
    parameters = job.data["inputs"]["request"]["parameters"]
    for name in job.planned:
        if writer.load_slice(name) is not None:
            continue
        if name == "second":
            while not Path(parameters["gate"]).exists():
                if deadline is not None and time.monotonic() >= deadline:
                    return
                time.sleep(.005)
        if deadline is not None and time.monotonic() >= deadline:
            return
        if sys.version_info >= (3, 12):
            from flowguard.behave.project import replay
            from flowguard.behave.skeleton import derive
            facts = replay(derive(job.snapshot / "src"), [], {"world": "small"}, operation="explore",
                           options={"steps": 1, "node_cap": 8, "alphabet_cap": 16})
            producer = {"pid": facts["execution"]["child_pid"], "kind": "native"}
        else:
            from flowguard.behave.inputs import file_stamp
            path = job.snapshot / "src/data.txt"
            facts = {"data": path.read_text(), "footprint": {"reusable": True,
                     "files": {str(path): file_stamp(path)}, "directories": {}, "untracked": []}}
            producer = {"pid": os.getpid(), "kind": "source-read"}
        with Path(parameters["events"]).open("a") as stream:
            stream.write(json.dumps({"slice": name, **producer}) + "\n")
        writer.save_slice(name, facts)


def worker(path):
    jobs.serve(jobs.open_job(path), execute)


def request(tmp_path):
    return {"operation": "two native fact slices", "slices": ["first", "second"],
            "bases": [], "parameters": {"gate": str(tmp_path / "continue"), "events": str(tmp_path / "events")}}


def prepare(root, request):
    if sys.version_info < (3, 12):
        return jobs.prepare(root, files=["src/program.py", "src/data.txt"], request=request)
    from flowguard.behave.project import replay
    from flowguard.behave.skeleton import derive
    observed = replay(derive(root / "src"), [], {"world": "small"})
    return jobs.prepare(root, files=["src/program.py", "src/data.txt"], directories=["src"], request=request,
                        directory_uses=observed["footprint"]["directory_uses"])


def call(job, *, wait=.05, foreground=False):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(child_import_path(ENGINE_ROOT, {})),
               PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    argv = [sys.executable, "-c", "import runpy,sys;runpy.run_path(sys.argv[1])['worker'](sys.argv[2])",
            str(Path(__file__).resolve()), str(job.path)]
    return jobs.run_or_attach(job, execute=execute, worker_command=argv, env=env, wait=wait, foreground=foreground)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    (root / "src").mkdir(parents=True)
    (root / "src/program.py").write_text(PROGRAM)
    (root / "src/data.txt").write_text("frozen original data")
    for args in (("init", "-q"), ("config", "user.name", "Fixture"),
                 ("config", "user.email", "fixture@example.invalid"), ("add", "src"), ("commit", "-qm", "base")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    # Both worktrees use Git's actual materialization order, part of their input identity.
    shutil.rmtree(root / "src")
    subprocess.run(["git", "-C", str(root), "checkout", "HEAD", "--", "src"], check=True, capture_output=True)
    return root


def await_first(job):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        view = jobs._view(job)
        if view["done"] == ["first"]:
            return view
        time.sleep(.01)
    pytest.fail("native first slice did not finish")


def test_same_content_worktrees_attach_and_keep_the_original_snapshot(source, tmp_path):
    peer = tmp_path / "peer"
    subprocess.run(["git", "-C", str(source), "worktree", "add", "--detach", str(peer), "HEAD"],
                   check=True, capture_output=True)
    parameters = request(tmp_path)
    left, right = prepare(source, parameters), prepare(peer, parameters)
    assert left.key == right.key and left.path == right.path
    started = time.monotonic()
    assert not call(left)["complete"]
    assert time.monotonic() - started < 2
    first = await_first(left)
    assert not call(right)["complete"]
    assert jobs._view(left)["owner"] == first["owner"]
    (source / "src/data.txt").write_text("edited while original job runs")
    assert not left.matches(source) and left.matches(peer)
    assert (left.snapshot / "src/data.txt").read_text() == "frozen original data"
    assert prepare(source, parameters).key != left.key
    Path(parameters["parameters"]["gate"]).touch()
    assert call(right, wait=None)["complete"]
    events = [json.loads(line) for line in Path(parameters["parameters"]["events"]).read_text().splitlines()]
    assert [row["slice"] for row in events] == ["first", "second"]
    if sys.version_info >= (3, 12):
        assert all(row["kind"] == "native" for row in events)
        assert len({row["pid"] for row in events}) == 2
    else:
        assert all(row["kind"] == "source-read" and row["pid"] == first["owner"] for row in events)


def test_dead_worker_lock_is_released_and_foreground_reuses_completed_native_slice(source, tmp_path):
    parameters = request(tmp_path)
    job = prepare(source, parameters)
    call(job)
    first = await_first(job)
    original = (job.path / "slices" / (jobs._key("first") + ".json")).read_bytes()
    os.kill(first["owner"], signal.SIGTERM if os.name == "nt" else signal.SIGKILL)
    deadline = time.monotonic() + 3
    while jobs._busy(job) and time.monotonic() < deadline:
        time.sleep(.01)
    assert not jobs._busy(job)
    Path(parameters["parameters"]["gate"]).touch()
    assert call(job, wait=None)["complete"]  # dead-owner path automatically runs foreground
    assert (job.path / "slices" / (jobs._key("first") + ".json")).read_bytes() == original
    assert [json.loads(line)["slice"] for line in Path(parameters["parameters"]["events"]).read_text().splitlines()] == ["first", "second"]


def test_slice_reuse_revalidates_inputs_and_never_stores_a_verdict(source, tmp_path):
    parameters = request(tmp_path)
    Path(parameters["parameters"]["gate"]).touch()
    job = prepare(source, parameters)
    assert call(job, wait=None, foreground=True)["complete"]
    events = Path(parameters["parameters"]["events"]).read_bytes()
    assert call(job, wait=None)["complete"]
    assert Path(parameters["parameters"]["events"]).read_bytes() == events
    (source / "src/new_fixture.txt").write_text("new directory input")
    assert prepare(source, parameters).key == job.key  # No declared/observed consumer reads this file.
    (source / "src/data.txt").write_text("changed actual data")
    assert prepare(source, parameters).key != job.key
    assert not job.matches(source)
    writer = jobs.Writer(job)
    facts = writer.load_slice("first")
    for field in ("verdict", "judgment"):
        with pytest.raises(ValueError, match="verdict"):
            writer.save_slice("first", {**facts, field: "current J / CLEAR"})
    (job.snapshot / "src/data.txt").write_text("modified frozen input")
    assert writer.load_slice("first") is None
    assert not writer.finish()
