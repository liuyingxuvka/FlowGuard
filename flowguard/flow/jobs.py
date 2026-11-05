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
- A worker that ends before every result is in is reported by the waiting call as it is
  (died, failed, stopped), with its run's log; the call never starts another worker, and
  when the worker died with its death notice (its whole group killed) the call writes that
  it died. A worker that died or failed while it lingered (no call waited) is reported the
  same way by the next call of the command, which starts no worker either; once an end
  has been told, the call after it starts afresh. A worker stopped by the liveness rule
  (nobody resumed it within --keep, or its caller died) ended as designed and is simply
  started again. A run replaced on purpose (a newer check found the model files changed) says so
  in its status and keeps its directory: a call still waiting on it reports "not finished:
  the model files changed" with the command that resumes, never an internal error.

Cache layout under `.flowguard/cache/flow/`: `parts/<digest>.json` (results),
`manifests/<model UTF-8 hex>/<kind UTF-8 hex>.json` (each part's last reads), `locks/<part id>.lock` (one worker
per part), `jobs/<plan digest>/current.json` naming the latest run directory
`jobs/<plan digest>/<run>/` (plan.json, worker.json, status.json, lease.json, log).
"""
from __future__ import annotations

import ctypes
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

from ._process import lock_file, read_text, spawn_worker, terminate_group, unlock_file, windows_pid_alive
from .explore import Bounds
from .parts import ENGINE_DIGEST, PartResult, PartSpec, kinds, part_digest
from .history import pack_entries, unpack_entries, pack_wire, unpack_wire
from .project import FLOW_DIR, ProjectError, _atomic_write, cache_dir, file_digest, read_manifest, write_manifest

LEASE_BEAT = 1.0                 # a waiting resume caller renews the lease this often
LEASE_SPAN = 3.0                 # ... for this long
ACK_WAIT = 1.0                   # the RUNNING handshake waits at most this long
POLL = 0.1                       # how often a waiting caller looks at the cache and the worker
NOTICE_WAIT = 1.0                # a dead worker's death notice is waited for at most this long
KEEP_DEAD = 3                    # the newest runs that failed or died keep their directory (and log)
PR_SET_PDEATHSIG = 1
WORKER_MODULE = f"{__package__}.worker"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]      # the directory holding `flowguard/`
UNSUPPORTED_PLATFORM = "flow-model checks currently support Linux and Windows"


def platform_problem() -> str | None:
    """The execution boundary; importing flow views remains portable."""
    return None if sys.platform.startswith("linux") or sys.platform == "win32" else UNSUPPORTED_PLATFORM


def require_supported() -> None:
    problem = platform_problem()
    if problem is not None:
        raise ProjectError(problem)


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


def set_parent_death_signal(sig: int) -> None:
    """Linux: the kernel sends sig to this process when the thread that started it ends
    (0 clears it)."""
    if not sys.platform.startswith("linux"):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, sig, 0, 0, 0) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


_ARM = ("import ctypes, os, sys\n"
        "ctypes.CDLL(None, use_errno=True).prctl(1, int(sys.argv[2]), 0, 0, 0)\n"
        "if os.getppid() != int(sys.argv[1]):\n"
        "    os._exit(1)\n"
        "os.execv(sys.argv[3], sys.argv[3:])\n")


def ending_with_this_process(argv: list[str], sig: int = signal.SIGTERM) -> list[str]:
    """The command line for a child the worker starts in its own session (the picture
    renderer): on Linux a small launcher first asks the kernel to send it sig when this
    process dies (PR_SET_PDEATHSIG, kept across exec), checks that this process still
    lives, then runs argv in its place. No preexec_fn: the worker runs a watchdog thread,
    and code run between fork and exec in a threaded process can deadlock."""
    if not sys.platform.startswith("linux"):
        return list(argv)
    return [sys.executable, "-I", "-c", _ARM, str(os.getpid()), str(int(sig)), *argv]


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


def plan(root, paths, *, full: bool = False, max_states: int = Bounds().max_states,
         stored: dict | None = None, tests=None) -> list[Planned]:
    """Every registered part kind for every model (full-only kinds with full); with full
    the core part also verifies the renaming against an unreduced search. stored (the
    previous conflicts.json): a model with kept conflicts that have a path gets a replay
    part too, so a capped check can tell which of them still reproduce."""
    root = Path(root).resolve()
    kept = {}
    prior = {}
    # Closed source-bound replacements still revalidate their finite relation
    # against the current canonical core, after open native_stored is dropped.
    comparisons = {entry['model'] for entry in (stored or {}).get('closed', [])
                   if entry.get('closure', {}).get('kind') == 'requirement_changed'}
    for c in (stored or {}).get("conflicts", []):
        prior.setdefault(c["model"], []).append(c)
        if "replay" in c:
            kept.setdefault(c["model"], []).append(c)
    out = []
    for path in paths:
        rel = Path(path).resolve().relative_to(root).as_posix()
        model = Path(path).stem
        core = None
        for kind in kinds(full):
            options = [("max_states", max_states)]
            if kind == "core" and full:
                options.append(("verify_symmetry", True))
            if kind == 'core' and model in comparisons:
                options.append(('finite_comparison', True))
            retained = False
            if kind == 'core' and model in prior:
                saved = (stored or {}).get('models', {}).get(model, {}).get('core')
                if saved:
                    previous_item = Planned.from_json(saved['planned'])
                    same_bound = previous_item.spec.option('max_states', Bounds().max_states) == max_states
                    enough = not full or previous_item.spec.option('verify_symmetry', False)
                    old_decisions = {entry['id']:entry['history']['decision_refs']
                        for entry in unpack_entries(previous_item.spec.option('native_stored','[]'))
                        if entry.get('history', {}).get('decision_refs')}
                    live_decisions = {entry['id']:entry['history']['decision_refs']
                        for entry in prior[model] if entry.get('history', {}).get('decision_refs')}
                    if same_bound and enough and old_decisions == live_decisions and lookup(root, previous_item, recorded_digest=saved['digest']) is not None:
                        # Adding the newly found conflict to its history is not a
                        # source edit. Reuse this actual current recipe; after an
                        # input edit, run with the retained original conditions.
                        options = list(previous_item.spec.options)
                        retained = True
            if kind == "core" and model in prior and not retained:
                entries = []
                for entry in prior[model]:
                    saved = {key: entry[key] for key in ("id", "kind", "model", "subject", "sources", "subject_terms", "model_name", "path", "replay", "detail", "native_confirmation")
                             if key in entry}
                    if "history" in entry:
                        saved["history"] = {**entry["history"], "latest": None,
                                            "native_refs": []}
                    entries.append(saved)
                options.append(("native_stored", pack_entries(sorted(entries, key=lambda e: e["id"]))))
            out.append(Planned(PartSpec(kind, model, tuple(sorted(options))), rel))
            core = out[-1] if kind == "core" else core
        hit = lookup(root, core) if core is not None else None
        if hit is not None and hit.complete and hit.info.get("loaded") and not any(
                d["kind"] == "MODEL ERROR" for d in hit.findings):
            continue                              # a complete exploration decides: nothing to replay
        if model in kept:
            entries = json.dumps([{key:c[key] for key in ('id', 'path', 'replay') if key in c}
                                 for c in sorted(kept[model], key=lambda c: c['id'])], sort_keys=True)
            out.append(Planned(PartSpec("replay", model, (("max_states", max_states), ("stored", entries))), rel))
    if tests:
        from .codeaudit import spec
        out.append(Planned(spec(root, tests), '.'))
    return out


def plan_digest(root, planned: list[Planned]) -> str:
    """The identity of one command: engine, root and parts (not the file contents; a job
    whose inputs changed is replaced, see _ensure_job)."""
    return _sha([ENGINE_DIGEST, str(Path(root).resolve()), [p.to_json() for p in planned]])[:24]


# ---------------------------------------------------------------------- cache
def expected_digest(root, item: Planned) -> str | None:
    """The digest the part has for the files as they are now (None: never loaded)."""
    reads = read_manifest(root, item.spec.model, kind=item.spec.kind)
    if reads is None:
        return None
    return part_digest(root, item.spec, reads)


def lookup(root, item: Planned, *, named_digest=None, recorded_digest=None) -> PartResult | None:
    """The finished result for the current file contents, or None (a miss)."""
    digest = recorded_digest if recorded_digest is not None else expected_digest(root, item)
    if digest is None:
        return None
    path = parts_dir(root) / f"{digest}.json"
    if not path.is_file():
        return None
    result = PartResult.from_json(read_json(path))
    if result.kind != item.spec.kind or result.model != item.spec.model:
        return None
    if recorded_digest is not None and part_digest(root, item.spec, result.reads) != recorded_digest:
        return None
    native = result.info.get("native", {})
    just_finished_unknown = (named_digest == digest and
                             (not result.complete or native.get('status') == 'unknown' or result.info.get('reusable') is False))
    if item.spec.kind == 'code-audit':
        from .codeaudit import current, source_files
        # A worker may finish an honest UNKNOWN with non-reusable native inputs.
        # Consume its named result for this run; it is never a reusable clean hit.
        just_finished_unknown &= result.info.get('inventory') == source_files(root)
        if not current(root, result) and not just_finished_unknown:
            return None
    if any(not (Path(root) / w).exists() for w in result.writes):
        return None
    if native.get("bound"):
        from ..native.inputs import footprint_evidence
        if not native.get("footprints") or any(footprint_evidence(row).status != "current"
                                               for row in native["footprints"]):
            if just_finished_unknown:
                return result
            return None
    return result


def store(root, result: PartResult) -> None:
    """Keep a finished result under its digest, then point that model/part manifest at its reads."""
    _atomic_write(parts_dir(root) / f"{result.digest}.json",
                  json.dumps(pack_wire(result.to_json()), sort_keys=True, ensure_ascii=False) + "\n")
    write_manifest(root, result.model, result.reads, kind=result.kind)


def inputs_of(root, planned: list[Planned]) -> dict:
    """The files a plan is known to read now (model files and manifests) with their digests."""
    files = set()
    for item in planned:
        files.add(item.path)
        if item.spec.kind == 'code-audit':
            files.update(item.spec.option('inventory', ()))
        files.update(read_manifest(root, item.spec.model, kind=item.spec.kind) or [])
    return {rel: file_digest(root, rel) for rel in sorted(files)}


# ---------------------------------------------------------------------- locks and processes
class Lock:
    """An exclusive native file lock: held exactly while its holder lives, so a lock
    of a killed process is free at once. The file records the holder's pid."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.fd = None

    def acquire(self, blocking: bool = True) -> bool:
        require_supported()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            acquired = lock_file(fd, blocking)
        except BaseException:
            os.close(fd)
            raise
        if not acquired:
            os.close(fd)
            return False
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        self.fd = fd
        return True

    def release(self) -> None:
        if self.fd is not None:
            unlock_file(self.fd)
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def pid_alive(pid: int) -> bool:
    """Whether a process runs (an exited child of ours is reaped first, and an exited
    process nobody has reaped yet, a zombie, counts as gone)."""
    if os.name == "nt":
        return windows_pid_alive(pid)
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
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True                               # no /proc (not Linux): kill(0) decides


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return unpack_wire(json.loads(read_text(path)))


def write_json(path: Path, data: dict) -> None:
    _atomic_write(path, json.dumps(pack_wire(data), sort_keys=True) + "\n")


# ---------------------------------------------------------------------- one job, seen from a caller
class _Job:
    """The worker of one plan, as the waiting caller holds it: spawned by this call (it
    holds the pipe) or attached to (it renews the lease)."""

    def __init__(self, directory: Path):
        self.dir = directory
        self.proc = None              # spawned here
        self.pipe = None              # our end of the pipe (spawned here)
        self.beat = None              # heartbeat thread (attached to a live worker)
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

    def ended(self, root: Path) -> tuple[str, str]:
        """Why the worker ended before every result was in, as the caller reports it:
        ("changed", why) when the model files changed under it (a newer check replaced the
        run, or it finished on the old files), else ("failed", why) with the run's log. A
        worker killed together with its death notice (its whole process group) leaves the
        status saying running: the caller, which saw it go, writes that it died."""
        deadline = time.monotonic() + NOTICE_WAIT
        status = self.status() or {}
        while status.get("state", "running") == "running" and time.monotonic() < deadline:
            time.sleep(0.02)                      # the death notice of worker.py is on its way
            status = self.status() or {}
        if status.get("state", "running") == "running" and not self.alive():
            status.update(state="died", current=None,
                          reason="it ended without a word, its death notice with it: its whole process "
                                 "group was killed")
            write_json(self.dir / "status.json", status)
        state, reason = status.get("state"), status.get("reason")
        log = f"log: {(self.dir / 'log').relative_to(root).as_posix()}"
        if state == "replaced":
            return "changed", "the model files changed while this check waited, and a newer check took over"
        if state == "done":                       # it finished the plan, but the files changed meanwhile
            return "changed", "the model files changed while the check ran"
        if state in ("failed", "stopped"):
            return "failed", f"the worker {state}" + (f": {reason}" if reason else "") + f" ({log})"
        how = ""
        if self.proc is not None and self.proc.returncode is not None and self.proc.returncode < 0:
            how = f" (killed by {signal.Signals(-self.proc.returncode).name})"
        elif reason:
            how = f" ({reason})"
        return "failed", f"the worker (pid {self.pid()}) died before it finished{how} ({log})"

    def reported(self) -> None:
        """The run's end has been told to a caller: the next check of the plan starts afresh."""
        status = self.status() or {}
        status["reported"] = True
        write_json(self.dir / "status.json", status)

    # -- starting
    @staticmethod
    def spawn(root: Path, planned: list[Planned], plan_dir: Path) -> "_Job":
        """A new worker in a new run directory of the plan; earlier runs whose worker ended
        normally are removed, the newest that failed or died are kept with their log (a run
        directory is only ever written by its own worker)."""
        plan_dir.mkdir(parents=True, exist_ok=True)
        dead = []
        for old in sorted(p for p in plan_dir.iterdir() if p.is_dir()):
            pid = (read_json(old / "worker.json") or {}).get("pid")
            if pid is not None and pid_alive(pid):
                continue
            _say_died(old)
            if ((read_json(old / "status.json") or {}).get("state")) in ("failed", "died", "replaced", "running",
                                                                           None):
                dead.append(old)                  # its log tells what happened: kept for a while
            else:
                shutil.rmtree(old)
        for old in dead[:-KEEP_DEAD]:
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
            job.proc = spawn_worker(
                [sys.executable, "-m", WORKER_MODULE, str(directory), str(r), str(os.getpid())],
                r, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, env=env, cwd=str(root))
        os.close(r)
        job.pipe = w
        write_json(directory / "worker.json", {"pid": job.proc.pid})
        write_json(plan_dir / "current.json", {"run": directory.name})
        return job

    @staticmethod
    def ended_run(directory: Path) -> "_Job":
        """A run whose worker ended badly while no call waited on it (it lingered after a
        RUNNING return): this call reports that end instead of starting a worker."""
        return _Job(directory)

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
        if self.beat is None and not self.spawned:
            return                                # an ended run: nothing waits on it
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
        elif self.beat is not None:
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
    """Kill the worker of a run whose inputs changed (it leads its own process group) and
    say so in its status: it was replaced on purpose, nothing went wrong in it. The run
    keeps its directory and log, so a check still waiting on it reads why it ended."""
    pid = worker_pid(run)
    try:
        terminate_group(pid)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 2.0
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    status = read_json(run / "status.json") or {}
    status.update(state="replaced", current=None, reason="the model files changed: a newer check took over")
    write_json(run / "status.json", status)


def _say_died(run: Path) -> None:
    """A run whose worker is gone while its status still says running (its whole group,
    death notice included, was killed): its status says it died. A death notice still on
    its way (the status was written less than NOTICE_WAIT ago) is left to write it."""
    path = run / "status.json"
    status = read_json(path)
    if status is None or status.get("state") != "running":
        return
    if time.time() - path.stat().st_mtime < NOTICE_WAIT:
        return
    status.update(state="died", current=None,
                  reason="it ended without a word, its death notice with it: its whole process group was killed")
    write_json(path, status)


def _ended_unsaid(run: Path | None) -> bool:
    """The run's worker is gone and ended in a way no call has been told: it died or failed
    while it lingered after a RUNNING return. Not so: a run that finished, was replaced,
    stopped because nobody resumed it in time (the liveness rule), or died together with
    the caller that started it before that caller handed it a lease (the kernel's
    PDEATHSIG, the same rule)."""
    if run is None or not (run / "worker.json").is_file():
        return False
    status = read_json(run / "status.json") or {"state": "running"}
    state = status.get("state")
    if status.get("reported") or state in ("done", "replaced", "stopped"):
        return False
    if state == "died" and status.get("lease_ms") is None:
        caller = (read_json(run / "plan.json") or {}).get("caller")
        return caller is not None and pid_alive(caller)
    return True


def _ensure_job(root: Path, planned: list[Planned]) -> _Job:
    """The live worker of this plan, attached to; the run whose worker ended badly while no
    call waited, to report (never replaced without a word); or a new worker when there is
    none, the last one's end was told, or its inputs changed since it was planned."""
    pdig = plan_digest(root, planned)
    plan_dir = jobs_dir(root) / pdig
    with Lock(jobs_dir(root) / f"{pdig}.lock"):
        run = current_run(plan_dir)
        if _live(run):
            recorded = read_json(run / "plan.json")["inputs"]
            if {rel: file_digest(root, rel) for rel in recorded} == recorded:
                return _Job.attach(run)
            _stop_stale(run)
        elif _ended_unsaid(run):
            return _Job.ended_run(run)
        elif run is not None:
            status = read_json(run / 'status.json') or {}
            if status.get('state') == 'done' and not (run / 'results_read.json').exists():
                recorded = (read_json(run / 'plan.json') or {}).get('inputs', {})
                if recorded and all(file_digest(root, rel) == value for rel, value in recorded.items()):
                    return _Job.ended_run(run)
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
    changed: str | None = None    # the model files changed under the run: not finished, resume
    seconds: float = 0.0


def run(root, planned: list[Planned], *, wait: float, keep: float,
        progress: Callable[[int, int, dict | None], None] | None = None) -> Outcome:
    """Results for every planned part: hits from the cache, the rest from the plan's
    worker, waiting at most `wait` seconds. The caller never runs model code."""
    require_supported()
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
    running = False
    looked = None
    named_by = None                               # how long to wait for the worker to name the parts it stored
    try:
        while True:
            status = job.status() or {}
            alive = job.alive()
            marker = (job.dir, len(status.get("parts", {})), alive)
            if marker != looked:                  # the cache is read again only when the worker moved on
                looked = marker
                for i, item in enumerate(planned):
                    if results[i] is None:
                        named = status.get('parts', {}).get(item.id, {}).get('digest')
                        results[i] = lookup(root, item)
                        if results[i] is None and named is not None:
                            results[i] = lookup(root, item, named_digest=named)
            # A replacement may publish its results before this waiting caller observes
            # the old worker's death. Those results do not complete this run.
            if all(r is not None for r in results) and (job.status() or {}).get("state") == "replaced":
                out.changed = job.ended(root)[1]
                break
            if _name_workers(job, planned, results, cached, workers) and all(r is not None for r in results):
                out.finished = True
                break
            if all(r is not None for r in results):
                # the worker stores a part, then names it in its status: wait that moment, never longer
                named_by = named_by if named_by is not None else time.monotonic() + NOTICE_WAIT
                if not alive or time.monotonic() >= named_by:
                    out.finished = True
                    break
                time.sleep(0.02)
                continue
            if not alive:                         # it ended without every result: said, never restarted
                kind, why = job.ended(root)
                if kind == "changed":
                    out.changed = why
                else:
                    out.failure = why
                    job.reported()
                break
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
            if out.finished or out.changed is not None:
                write_json(job.dir / 'results_read.json', {'finished': True})
    out.seconds = time.monotonic() - start
    return out


def _name_workers(job, planned, results, cached, workers) -> bool:
    """Name the worker of every part found in the cache during this call, from the status
    read after the lookup (the worker stores a part, then names it: a status read before
    the lookup can miss it). True when every such part is named."""
    pending = [i for i, r in enumerate(results) if r is not None and not cached[i] and workers[i] is None]
    if not pending:
        return True
    parts = (job.status() or {}).get("parts", {})
    for i in pending:
        entry = parts.get(planned[i].id)
        if entry is not None:
            workers[i] = entry["pid"]
    return all(workers[i] is not None for i in pending)


class Running(Exception):
    """The parts a `show` asked for did not all finish within its wait (it returns RUNNING;
    the worker keeps its lease)."""

    def __init__(self, outcome: Outcome):
        super().__init__("running")
        self.outcome = outcome


class Failed(Exception):
    """The worker of a `show` failed (an internal error, with where its log is)."""


class Runner:
    """What `show` (diagram.show_main) calls to get part results under the same wait
    contract as `check`: runner(specs) -> one PartResult per spec. One deadline covers
    every call of one show; a call that does not finish by then raises Running."""

    def __init__(self, root, *, wait: float, keep: float, progress=None):
        self.root = Path(root).resolve()
        self.deadline = time.monotonic() + wait
        self.keep = keep
        self.progress = progress

    def __call__(self, specs: list[PartSpec]) -> list[PartResult]:
        planned = [Planned(spec, (FLOW_DIR / f"{spec.model}.py").as_posix()) for spec in specs]
        outcome = run(self.root, planned, wait=max(0.0, self.deadline - time.monotonic()), keep=self.keep,
                      progress=self.progress)
        if outcome.failure is not None:
            raise Failed(outcome.failure)
        if not outcome.finished:                  # still running, or the files changed under it
            raise Running(outcome)
        return outcome.results
