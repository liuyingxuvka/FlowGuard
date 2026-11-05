"""`python -m flowguard.flow.worker JOBDIR PIPE_FD CALLER_PID`: runs the parts of one
job one after another and keeps their results in the cache (jobs.py).

It runs only while someone waits for it (the liveness rule of jobs.py): while the
spawning caller holds the pipe open, or while the lease in `lease.json` has not expired.
A watchdog thread checks this every half second; when it fails, the worker writes
`stopped (<reason>)` to its status and kills its own process group. On Linux the kernel
also kills it when the spawning caller dies (PR_SET_PDEATHSIG) until that caller hands it
a lease, so a killed caller stops it even when the thread cannot run. The kernel keeps
that setting per thread, so the watchdog thread arms and clears it on itself.

A worker killed that way cannot write its status, so it forks a death notice first: a
process that waits for the worker's end and turns a status still saying `running` into
`died`. The caller never starts a second worker for the same call: it reports the death
with the run's log (jobs.py). Children the worker starts (the picture renderer) run in
their own session and get SIGTERM from the kernel when the worker dies.

Windows uses an independent native Job Object guardian for the same pipe/lease rule.
It owns the worker and its descendants even while model code holds the worker's GIL;
a RUNNING handoff is consumed before caller EOF is judged.
"""
from __future__ import annotations

import os
from contextlib import nullcontext
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

from ._process import pipe_ready, start_guardian, terminate_group, worker_pipe
from .jobs import (Lock, Planned, locks_dir, lookup, now_ms, platform_problem, read_json, set_parent_death_signal, store,
                   write_json)
from .parts import ENGINE_DIGEST, PartContext, run_part
from .project import cache_dir

WATCH = 0.5                      # the watchdog's period
STATUS_EVERY = 1.0               # progress is written at most this often


def death_notice(jobdir: Path, caller: int, pipe_fd: int | None = None) -> None:
    """Fork the one process that outlives the worker by a moment: it waits until the
    worker's end of a pipe closes (the kernel closes it however the worker dies, even by
    SIGKILL), then, if the status still says running, writes that the worker died, ends
    what is left of the worker's process group and exits. It runs no part and holds no
    lock, so it is the only route by which a killed worker's status is corrected."""
    if os.name == "nt":
        start_guardian(jobdir, caller, pipe_fd)
        return
    r, w = os.pipe()
    pid = os.fork()
    if pid:                                       # the worker keeps the write end until it ends
        os.close(r)
        return
    os.close(w)
    try:
        while os.read(r, 1):
            pass
        status = read_json(jobdir / "status.json") or {}
        if status.get("state", "running") == "running":
            status.update(state="died", current=None,
                          reason="the worker ended without saying why: it was killed (a signal or the "
                                 "kernel, when its caller died)")
            write_json(jobdir / "status.json", status)
        terminate_group(os.getpgrp())
    finally:
        os._exit(0)


class Worker:
    def __init__(self, jobdir: Path, pipe_fd: int, caller: int):
        self.dir = Path(jobdir)
        self.pipe = worker_pipe(pipe_fd)
        self.caller = caller
        self.lock = threading.Lock()
        self.status = {"pid": os.getpid(), "state": "running", "reason": None, "parts": {},
                       "current": None, "lease_ms": None, "engine": ENGINE_DIGEST}
        self.last_write = 0.0
        self.buffer = b""
        self.armed = threading.Event()

    # -------------------------------------------------------------- status
    def write_status(self, **changes) -> None:
        guard_lock = Lock(self.dir / "status.lock") if os.name == "nt" else nullcontext()
        with self.lock, guard_lock:
            self.status.update(changes)
            if os.name == "nt" and (lease := read_json(self.dir / "lease.json")) is not None:
                self.status["lease_ms"] = lease["until_ms"]
            write_json(self.dir / "status.json", self.status)
            self.last_write = time.monotonic()

    def stop(self, reason: str) -> None:
        """The liveness rule failed: say why, then end the whole process group."""
        self.write_status(state="stopped", reason=reason, current=None)
        terminate_group(os.getpid())

    def fail(self, reason: str) -> None:
        self.write_status(state="failed", reason=reason, current=None)
        sys.exit(1)

    # -------------------------------------------------------------- liveness
    def read_pipe(self) -> bool:
        """Read what the caller wrote; False once the caller's end is closed."""
        data = os.read(self.pipe, 4096)
        if not data:
            os.close(self.pipe)
            self.pipe = None
            return False
        self.buffer += data
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            word, _, value = line.decode().partition(" ")
            if word != "L":
                raise ValueError(f"unknown message from the caller: {line!r}")
            until = int(value)
            set_parent_death_signal(0)            # the caller may now exit: the lease keeps us
            write_json(self.dir / "lease.json", {"until_ms": until, "pid": self.caller})
            self.write_status(lease_ms=until)
        return True

    def watch_once(self) -> None:
        """Alive while the spawning caller holds the pipe open or the lease is fresh."""
        if self.pipe is not None:
            if not pipe_ready(self.pipe, WATCH) or self.read_pipe():
                return
        else:
            time.sleep(WATCH)
        lease = read_json(self.dir / "lease.json")
        if lease is None:
            self.stop("the caller is gone")
        elif lease["until_ms"] <= now_ms():
            self.stop("lease expired: nobody waits for the result")

    def watchdog(self) -> None:
        try:
            # A caller that died before this is armed has closed its end of the pipe, so the
            # pipe rule below stops the worker at its first look; a caller that wrote its
            # lease and exited meanwhile has left "L" in the pipe, which keeps it.
            if os.name != "nt":
                set_parent_death_signal(signal.SIGKILL)
            self.armed.set()
            while True:
                self.watch_once()
        except BaseException:                      # the watchdog itself broke: stop rather than run unwatched
            self.write_status(state="failed", reason="watchdog: " + traceback.format_exc(limit=3).strip())
            terminate_group(os.getpid())

    # -------------------------------------------------------------- work
    def progress(self, info: dict) -> None:
        with self.lock:
            self.status["current"] = info
            due = time.monotonic() - self.last_write >= STATUS_EVERY
        if due:
            self.write_status()

    def run(self) -> None:
        if os.name != "nt" and os.getpgrp() != os.getpid():
            raise SystemExit("the worker must lead its own process group (start it through jobs.py)")
        self.write_status()
        death_notice(self.dir, self.caller, self.pipe)  # ownership before project code runs
        if os.name == "nt":
            os.close(self.pipe)                   # the independent guardian now owns the reader
            self.pipe = None
        else:
            threading.Thread(target=self.watchdog, name="flowguard-watchdog", daemon=True).start()
            self.armed.wait()
        plan = read_json(self.dir / "plan.json")
        if plan["engine"] != ENGINE_DIGEST:
            self.fail("the engine changed since the job was planned")
        root = Path(plan["root"])
        for entry in plan["parts"]:
            item = Planned.from_json(entry)
            self.write_status(current={"model": item.spec.model, "kind": item.spec.kind, "states": 0})
            with Lock(locks_dir(root) / f"{item.id}.lock"):
                hit = lookup(root, item)
                if hit is not None:
                    self.done(item, hit.digest, cached=True)
                    continue
                result = run_part(PartContext(root, item.spec, root / item.path, cache_dir(root),
                                              self.progress))
                store(root, result, planned=item)
                self.done(item, result.digest, cached=False)
        self.write_status(state="done", current=None)

    def done(self, item: Planned, digest: str, cached: bool) -> None:
        with self.lock:
            self.status["parts"][item.id] = {"digest": digest, "pid": os.getpid(), "cached": cached}
        self.write_status()


def main(argv: list[str]) -> int:
    problem = platform_problem()
    if problem is not None:
        print(problem)
        return 2
    jobdir, pipe_fd, caller = argv
    worker = Worker(Path(jobdir), int(pipe_fd), int(caller))
    try:
        worker.run()
    except Exception as err:                       # an internal error: reported to the caller, never retried
        on = worker.status["current"]
        where = f"part {on['kind']} of {on['model']}" if on else "the worker"
        worker.write_status(state="failed", reason=f"{where} raised {type(err).__name__}: {err}", current=None)
        raise                                      # the traceback goes to the job's log
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
