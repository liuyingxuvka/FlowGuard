"""The job system behind `check` and `show` (design 7.4, 7.5).

A plan is a list of parts (kind, model, options). A part is a hit when its result is in
the cache under the content digest of every file its model's last load read (the model's
manifest): recomputation keyed by input, never a verdict cache. Every other part runs in
one worker process (`worker.py`), never in the caller, so the caller only hashes files
and waits; it returns with every result, or after `wait` seconds with RUNNING.

Liveness (one rule, enforced by the worker): the worker runs only while its spawning
caller holds the pipe open, or while the lease in `lease.json` has not expired.
- The spawning caller that returns RUNNING writes `L <until>` on the pipe and waits (at
  most ACK_WAIT) until the worker has written that lease and acknowledged it.
- A resumed call (the same command) attaches to the live worker of its plan and rewrites
  the lease every LEASE_BEAT seconds to now + LEASE_SPAN; returning RUNNING it sets the
  lease to now + keep. A caller that is killed stops renewing, and the worker stops.

Cache layout under `.flowguard/cache/flow/`: `parts/<digest>.json` (results),
`manifests/<model>.json` (reads of the last load), `locks/<part id>.lock` (one worker
per part), `jobs/<plan digest>/current.json` naming the latest run directory
`jobs/<plan digest>/<run>/` (plan.json, worker.json, status.json, lease.json, log).
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .explore import Bounds
from .parts import ENGINE_DIGEST, PartResult, PartSpec, kinds, part_digest
from .project import _atomic_write, cache_dir, file_digest, read_manifest, write_manifest

LEASE_BEAT = 1.0                 # a waiting resume caller renews the lease this often
LEASE_SPAN = 3.0                 # ... for this long
ACK_WAIT = 1.0                   # the RUNNING handshake waits at most this long
POLL = 0.1                       # how often a waiting caller looks at the cache and the worker
WORKER_MODULE = f"{__package__}.worker"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]      # the directory holding `flowguard/`


# ---------------------------------------------------------------------- places
def parts_dir(root) -> Path:
    return cache_dir(root) / "parts"


def jobs_dir(root) -> Path:
    return cache_dir(root) / "jobs"


def locks_dir(root) -> Path:
    return cache_dir(root) / "locks"


def _sha(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------- plan
@dataclass(frozen=True)
class Planned:
    spec: PartSpec
    path: str                     # the model file, posix, relative to the root

    @property
    def id(self) -> str:
        """The part's identity without its content (lock and status key)."""
        return _sha([self.spec.kind, self.spec.model, [list(o) for o in self.spec.options]])[:20]

    @property
    def label(self) -> str:
        return self.spec.model if self.spec.kind == "core" else f"{self.spec.model} {self.spec.kind}"

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.spec.kind, "model": self.spec.model,
                "options": [list(o) for o in self.spec.options], "path": self.path}

    @staticmethod
    def from_json(d: dict) -> "Planned":
        return Planned(PartSpec(d["kind"], d["model"], tuple(tuple(o) for o in d["options"])), d["path"])


def plan(root, paths, *, full: bool = False, max_states: int = Bounds().max_states) -> list[Planned]:
    """Every registered part kind for every model (full-only kinds with full); with full
    the core part also verifies the renaming against an unreduced search."""
    root = Path(root).resolve()
    out = []
    for path in paths:
        rel = Path(path).resolve().relative_to(root).as_posix()
        for kind in kinds(full):
            options = [("max_states", max_states)]
            if kind == "core" and full:
                options.append(("verify_symmetry", True))
            out.append(Planned(PartSpec(kind, Path(path).stem, tuple(sorted(options))), rel))
    return out


def plan_digest(root, planned: list[Planned]) -> str:
    """The identity of one command: engine, root and parts (not the file contents; a job
    whose inputs changed is replaced, see _ensure_job)."""
    return _sha([ENGINE_DIGEST, str(Path(root).resolve()), [p.to_json() for p in planned]])[:24]


# ---------------------------------------------------------------------- cache
def expected_digest(root, item: Planned) -> str | None:
    """The digest the part has for the files as they are now (None: never loaded)."""
    reads = read_manifest(root, item.spec.model)
    if reads is None:
        return None
    return part_digest(root, item.spec, reads)


def lookup(root, item: Planned) -> PartResult | None:
    """The finished result for the current file contents, or None (a miss)."""
    digest = expected_digest(root, item)
    if digest is None:
        return None
    path = parts_dir(root) / f"{digest}.json"
    if not path.is_file():
        return None
    result = PartResult.from_json(json.loads(path.read_text(encoding="utf-8")))
    if result.kind != item.spec.kind or result.model != item.spec.model:
        return None
    if any(not (Path(root) / w).exists() for w in result.writes):
        return None
    return result


def store(root, result: PartResult) -> None:
    """Keep a finished result under its digest, then point the model's manifest at its reads."""
    _atomic_write(parts_dir(root) / f"{result.digest}.json",
                  json.dumps(result.to_json(), sort_keys=True, ensure_ascii=False) + "\n")
    write_manifest(root, result.model, result.reads)


def inputs_of(root, planned: list[Planned]) -> dict:
    """The files a plan is known to read now (model files and manifests) with their digests."""
    files = set()
    for item in planned:
        files.add(item.path)
        files.update(read_manifest(root, item.spec.model) or [])
    return {rel: file_digest(root, rel) for rel in sorted(files)}


# ---------------------------------------------------------------------- locks and processes
class Lock:
    """An exclusive lock on a file (flock): held exactly while its holder lives, so a lock
    of a killed process is free at once. The file records the holder's pid."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.fd = None

    def acquire(self, blocking: bool = True) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError as err:
            os.close(fd)
            if err.errno in (errno.EAGAIN, errno.EACCES):
                return False
            raise
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        self.fd = fd
        return True

    def release(self) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def pid_alive(pid: int) -> bool:
    """Whether a process runs (an exited child of ours is reaped first, so it counts as gone)."""
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    _atomic_write(path, json.dumps(data, sort_keys=True) + "\n")


# ---------------------------------------------------------------------- one job, seen from a caller
class _Job:
    """The worker of one plan, as the waiting caller holds it: spawned by this call (it
    holds the pipe) or attached to (it renews the lease)."""

    def __init__(self, directory: Path):
        self.dir = directory
        self.proc = None              # spawned here
        self.pipe = None              # our end of the pipe (spawned here)
        self.beat = None              # heartbeat thread (attached)
        self.stop_beat = threading.Event()

    # -- what the worker says
    def status(self) -> dict | None:
        return read_json(self.dir / "status.json")

    def pid(self) -> int | None:
        if self.proc is not None:
            return self.proc.pid
        return worker_pid(self.dir)

    def alive(self) -> bool:
        if self.proc is not None:
            return self.proc.poll() is None
        pid = self.pid()
        return pid is not None and pid_alive(pid)

    @property
    def spawned(self) -> bool:
        return self.proc is not None

    # -- starting
    @staticmethod
    def spawn(root: Path, planned: list[Planned], plan_dir: Path) -> "_Job":
        """A new worker in a new run directory of the plan; earlier runs whose worker has
        ended are removed (a run directory is only ever written by its own worker)."""
        plan_dir.mkdir(parents=True, exist_ok=True)
        for old in sorted(p for p in plan_dir.iterdir() if p.is_dir()):
            pid = (read_json(old / "worker.json") or {}).get("pid")
            if pid is None or not pid_alive(pid):
                shutil.rmtree(old)
        directory = plan_dir / f"{now_ms()}-{os.getpid()}"
        directory.mkdir()
        write_json(directory / "plan.json", {"engine": ENGINE_DIGEST, "root": str(root),
                                             "parts": [p.to_json() for p in planned],
                                             "inputs": inputs_of(root, planned), "caller": os.getpid()})
        job = _Job(directory)
        r, w = os.pipe()
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(PACKAGE_ROOT)] + [p for p in [env.get("PYTHONPATH")] if p])
        with open(directory / "log", "ab") as log:
            job.proc = subprocess.Popen(
                [sys.executable, "-m", WORKER_MODULE, str(directory), str(r), str(os.getpid())],
                pass_fds=(r,), start_new_session=True, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, env=env, cwd=str(root))
        os.close(r)
        job.pipe = w
        write_json(directory / "worker.json", {"pid": job.proc.pid})
        write_json(plan_dir / "current.json", {"run": directory.name})
        return job

    @staticmethod
    def attach(directory: Path) -> "_Job":
        job = _Job(directory)
        job._renew(LEASE_SPAN)
        job.beat = threading.Thread(target=job._heartbeat, name="flowguard-lease", daemon=True)
        job.beat.start()
        return job

    def _renew(self, seconds: float) -> None:
        write_json(self.dir / "lease.json", {"until_ms": now_ms() + int(seconds * 1000), "pid": os.getpid()})

    def _heartbeat(self) -> None:
        while not self.stop_beat.wait(LEASE_BEAT):
            self._renew(LEASE_SPAN)

    # -- ending this call
    def linger(self, keep: float) -> None:
        """A normal RUNNING return: leave the worker alive for keep seconds."""
        if self.spawned:
            until = now_ms() + int(keep * 1000)
            os.write(self.pipe, f"L {until}\n".encode())
            deadline = time.monotonic() + ACK_WAIT
            while time.monotonic() < deadline and self.proc.poll() is None:
                st = self.status()
                if st is not None and st.get("lease_ms") == until:
                    break
                time.sleep(0.02)
            os.close(self.pipe)
            self.pipe = None
        else:
            self.stop_beat.set()
            self.beat.join()
            self._renew(keep)

    def release(self) -> None:
        """Every result is in (or this call failed): the worker is not waited for any more."""
        if self.spawned:
            if self.pipe is not None:
                os.close(self.pipe)
                self.pipe = None
            self.proc.poll()
        else:
            self.stop_beat.set()
            self.beat.join()


def worker_pid(directory: Path) -> int | None:
    """The pid of a run's worker, written by the caller that spawned it."""
    data = read_json(Path(directory) / "worker.json")
    return data["pid"] if data else None


def current_run(plan_dir: Path) -> Path | None:
    """The run directory of the plan's latest worker."""
    data = read_json(plan_dir / "current.json")
    return plan_dir / data["run"] if data else None


def _live(run: Path | None) -> bool:
    """The run's worker runs and has not ended (no status yet: it is starting)."""
    pid = worker_pid(run) if run is not None else None
    if pid is None or not pid_alive(pid):
        return False
    status = read_json(run / "status.json")
    return status is None or status["state"] == "running"


def _stop_stale(run: Path) -> None:
    """Kill the worker of a run whose inputs changed (it leads its own process group)."""
    pid = worker_pid(run)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 2.0
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.02)


def _ensure_job(root: Path, planned: list[Planned]) -> _Job:
    """The live worker of this plan, attached to; or a new one when there is none or its
    inputs changed since it was planned."""
    pdig = plan_digest(root, planned)
    plan_dir = jobs_dir(root) / pdig
    with Lock(jobs_dir(root) / f"{pdig}.lock"):
        run = current_run(plan_dir)
        if _live(run):
            recorded = read_json(run / "plan.json")["inputs"]
            if {rel: file_digest(root, rel) for rel in recorded} == recorded:
                return _Job.attach(run)
            _stop_stale(run)
        return _Job.spawn(root, planned, plan_dir)


# ---------------------------------------------------------------------- waiting
@dataclass
class Outcome:
    planned: list
    results: list                 # PartResult or None (not finished) per planned part
    cached: list                  # True: a hit before this call started any work
    workers: list                 # pid of the worker that computed the part, None if cached
    finished: bool                # every part has its result
    job: str | None = None        # the job directory (posix, relative to the root)
    worker: int | None = None     # the worker pid this call waited for
    current: dict | None = None   # what the worker is on when RUNNING: {"model", "kind", "states"}
    failure: str | None = None    # the worker failed (internal error), with where its log is
    seconds: float = 0.0


def run(root, planned: list[Planned], *, wait: float, keep: float,
        progress: Callable[[int, int, dict | None], None] | None = None) -> Outcome:
    """Results for every planned part: hits from the cache, the rest from the plan's
    worker, waiting at most `wait` seconds. The caller never runs model code."""
    root = Path(root).resolve()
    start = time.monotonic()
    deadline = start + wait
    n = len(planned)
    results = [lookup(root, p) for p in planned]
    cached = [r is not None for r in results]
    workers = [None] * n
    out = Outcome(planned, results, cached, workers, all(cached))
    if out.finished:
        out.seconds = time.monotonic() - start
        return out
    job = _ensure_job(root, planned)
    replaced_done = 0
    running = False
    looked = None
    try:
        while True:
            status = job.status() or {}
            alive = job.alive()
            marker = (job.dir, len(status.get("parts", {})), alive)
            if marker != looked:                  # the cache is read again only when the worker moved on
                looked = marker
                for i, item in enumerate(planned):
                    if results[i] is None:
                        results[i] = lookup(root, item)
                        entry = status.get("parts", {}).get(item.id)
                        if results[i] is not None and entry is not None:
                            workers[i] = entry["pid"]
            if all(r is not None for r in results):
                out.finished = True
                break
            if not alive:
                status = job.status() or {}
                state = status.get("state")
                if state == "failed" or (job.spawned and state != "done"):
                    log = (job.dir / "log").relative_to(root).as_posix()
                    out.failure = (f"the worker {state or 'exited before it started'}"
                                   f"{': ' + status['reason'] if status.get('reason') else ''} (log: {log})")
                    break
                if state == "done":           # it finished, but files changed meanwhile
                    replaced_done += 1
                    if replaced_done > 1:
                        out.failure = "the files changed while the check ran, twice; run it again"
                        break
                job.release()
                job = _ensure_job(root, planned)
                continue
            left = deadline - time.monotonic()
            if left <= 0:
                running = True
                out.current = status.get("current")
                break
            if progress is not None:
                progress(sum(r is not None for r in results), n, status.get("current"))
            time.sleep(min(POLL, left))
    finally:
        out.job = job.dir.relative_to(root).as_posix()
        out.worker = job.pid()
        if running:
            job.linger(keep)
        else:
            job.release()
    out.seconds = time.monotonic() - start
    return out


class Runner:
    """What `show` (diagram.show_main) calls to get part results under the same wait
    contract as `check`: runner(planned) -> Outcome."""

    def __init__(self, root, *, wait: float, keep: float, progress=None):
        self.root = Path(root).resolve()
        self.wait = wait
        self.keep = keep
        self.progress = progress

    def __call__(self, planned: list[Planned]) -> Outcome:
        return run(self.root, planned, wait=self.wait, keep=self.keep, progress=self.progress)
