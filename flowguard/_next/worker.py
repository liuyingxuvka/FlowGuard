"""`python -m flowguard._next.worker JOBDIR PIPE_FD CALLER_PID`: runs the parts of one
job one after another and keeps their results in the cache (jobs.py).

It runs only while someone waits for it (the liveness rule of jobs.py): while the
spawning caller holds the pipe open, or while the lease in `lease.json` has not expired.
A watchdog thread checks this every half second; when it fails, the worker writes
`stopped (<reason>)` to its status and kills its own process group. On Linux the kernel
also kills it when the spawning caller dies (PR_SET_PDEATHSIG) until that caller hands it
a lease, so a killed caller stops it even when the thread cannot run. The kernel keeps
that setting per thread, so the watchdog thread arms and clears it on itself.
"""
from __future__ import annotations

import ctypes
import os
import select
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

from .jobs import Lock, Planned, locks_dir, lookup, now_ms, read_json, store, write_json
from .parts import ENGINE_DIGEST, PartContext, run_part
from .project import cache_dir

WATCH = 0.5                      # the watchdog's period
STATUS_EVERY = 1.0               # progress is written at most this often
PR_SET_PDEATHSIG = 1


def set_parent_death_signal(sig: int) -> None:
    """Linux: the kernel sends sig to this process when its parent dies (0 clears it)."""
    if not sys.platform.startswith("linux"):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, sig, 0, 0, 0) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


class Worker:
    def __init__(self, jobdir: Path, pipe_fd: int, caller: int):
        self.dir = Path(jobdir)
        self.pipe = pipe_fd
        self.caller = caller
        self.lock = threading.Lock()
        self.status = {"pid": os.getpid(), "state": "running", "reason": None, "parts": {},
                       "current": None, "lease_ms": None, "engine": ENGINE_DIGEST}
        self.last_write = 0.0
        self.buffer = b""
        self.armed = threading.Event()

    # -------------------------------------------------------------- status
    def write_status(self, **changes) -> None:
        with self.lock:
            self.status.update(changes)
            write_json(self.dir / "status.json", self.status)
            self.last_write = time.monotonic()

    def stop(self, reason: str) -> None:
        """The liveness rule failed: say why, then end the whole process group."""
        self.write_status(state="stopped", reason=reason, current=None)
        os.killpg(os.getpgrp(), signal.SIGKILL)

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
            ready, _, _ = select.select([self.pipe], [], [], WATCH)
            if not ready or self.read_pipe():
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
            set_parent_death_signal(signal.SIGKILL)
            if os.getppid() != self.caller:        # the caller died before the signal was armed
                self.stop("the caller is gone")
            self.armed.set()
            while True:
                self.watch_once()
        except BaseException:                      # the watchdog itself broke: stop rather than run unwatched
            self.write_status(state="failed", reason="watchdog: " + traceback.format_exc(limit=3).strip())
            os.killpg(os.getpgrp(), signal.SIGKILL)

    # -------------------------------------------------------------- work
    def progress(self, info: dict) -> None:
        with self.lock:
            self.status["current"] = info
            due = time.monotonic() - self.last_write >= STATUS_EVERY
        if due:
            self.write_status()

    def run(self) -> None:
        if os.getpgrp() != os.getpid():
            raise SystemExit("the worker must lead its own process group (start it through jobs.py)")
        self.write_status()
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
                store(root, result)
                self.done(item, result.digest, cached=False)
        self.write_status(state="done", current=None)

    def done(self, item: Planned, digest: str, cached: bool) -> None:
        with self.lock:
            self.status["parts"][item.id] = {"digest": digest, "pid": os.getpid(), "cached": cached}
        self.write_status()


def main(argv: list[str]) -> int:
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
