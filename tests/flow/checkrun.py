"""Running `python -m flowguard check|show` in a subprocess, as the AI's tool call
does (stdout and stderr captured, so nothing inherits the caller's output), timed."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Run:
    code: int
    out: str
    err: str
    seconds: float

    @property
    def lines(self) -> list[str]:
        return self.out.splitlines()

    @property
    def first(self) -> str:
        return self.lines[0] if self.lines else ""

    @property
    def data(self) -> dict:
        lines = self.lines
        assert len(lines) == 1, self.out
        return json.loads(lines[0])


def env(seed=None) -> dict:
    e = {**os.environ, "PYTHONPATH": str(REPO)}
    e.pop("MV", None)
    if seed is not None:
        e["PYTHONHASHSEED"] = str(seed)
    return e


def command(*args) -> list[str]:
    return [sys.executable, "-m", "flowguard", *args]


def run_check(root, *args, timeout=120, seed=None, cwd=None) -> Run:
    start = time.monotonic()
    res = subprocess.run(command("check", *args), cwd=str(cwd or root), capture_output=True, text=True,
                         timeout=timeout, env=env(seed))
    return Run(res.returncode, res.stdout, res.stderr, time.monotonic() - start)


def start_check(root, *args) -> subprocess.Popen:
    return subprocess.Popen(command("check", *args), cwd=str(root), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env())


def gone(pid: int) -> bool:
    """The process no longer runs (a zombie counts as gone)."""
    if os.name == "nt":
        from flowguard.flow._process import windows_pid_alive
        return not windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text().rsplit(")", 1)[1].split()[0] == "Z"
        except (FileNotFoundError, ProcessLookupError):
            return True
    return False


def group_gone(pgid: int) -> bool:
    """No process of the group runs (zombies count as gone)."""
    if os.name == "nt":
        return gone(pgid) and not descendants(pgid)
    proc = Path("/proc")
    if proc.is_dir():
        for d in proc.iterdir():
            if d.name.isdigit():
                try:
                    fields = (d / "stat").read_text().rsplit(")", 1)[1].split()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if int(fields[2]) == pgid and fields[0] != "Z":
                    return False
        return True
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def kill(pid: int, *, whole_group=False) -> None:
    """Deliberately kill a caller/worker; a whole-tree kill also takes its guardian."""
    if os.name == "nt":
        if gone(pid):
            return
        if whole_group:
            targets = descendants(pid) | {pid}
            result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            if result.returncode and any(not gone(target) for target in targets):
                result.check_returncode()
        else:
            os.kill(pid, signal.SIGTERM)
    elif whole_group:
        os.killpg(pid, signal.SIGKILL)
    else:
        os.kill(pid, signal.SIGKILL)


def descendants(pid: int) -> set[int]:
    """Observe OS process ancestry independently of the job's saved status."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes as w
        class Entry(ctypes.Structure):
            _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
                        ("heap", ctypes.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                        ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD),
                        ("name", w.WCHAR * 260)]
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        api.CreateToolhelp32Snapshot.restype = w.HANDLE
        for name in ("Process32FirstW", "Process32NextW"):
            getattr(api, name).argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
            getattr(api, name).restype = w.BOOL
        api.CloseHandle.argtypes = [w.HANDLE]
        snapshot = api.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        parents, row = {}, Entry()
        row.size = ctypes.sizeof(row)
        try:
            more = api.Process32FirstW(snapshot, ctypes.byref(row))
            while more:
                parents[row.pid] = row.parent
                more = api.Process32NextW(snapshot, ctypes.byref(row))
            if ctypes.get_last_error() != 18:      # ERROR_NO_MORE_FILES is normal exhaustion
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(snapshot)
    else:
        parents = {}
        for path in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = path.read_text().rsplit(")", 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields[0] != "Z":
                parents[int(path.parent.name)] = int(fields[1])
    found, todo = set(), [pid]
    while todo:
        current = todo.pop()
        kids = {child for child, parent in parents.items() if parent == current} - found
        found.update(kids)
        todo.extend(kids)
    return found


def wait_until(predicate, timeout: float, step: float = 0.05) -> float | None:
    """Seconds until predicate() held, or None if it did not within timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if predicate():
            return time.monotonic() - start
        time.sleep(step)
    return None
