"""OS process ownership for the shared flow worker, not a second job runner."""
from __future__ import annotations

import ctypes
import errno
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_LOCK_OFFSET = 64              # mandatory Windows lock stays beyond the readable PID text


def lock_file(fd: int, blocking: bool) -> bool:
    if os.name != "nt":
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError as err:
            if err.errno in (errno.EAGAIN, errno.EACCES):
                return False
            raise
        return True
    import msvcrt
    while True:
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError as err:
            if err.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            if not blocking:
                return False
            time.sleep(0.05)


def unlock_file(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def _kernel():
    """Declare pointer-width-correct Windows calls only on Windows."""
    from ctypes import wintypes as w
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    for name, args, result in (
        ("OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        ("WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD),
        ("CloseHandle", [w.HANDLE], w.BOOL),
        ("TerminateProcess", [w.HANDLE, w.UINT], w.BOOL),
        ("CreateJobObjectW", [ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
        ("SetInformationJobObject", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
        ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
        ("PeekNamedPipe", [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.c_void_p,
                           ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
        ("CreateFileW", [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD,
                         w.DWORD, w.HANDLE], w.HANDLE),
    ):
        fn = getattr(api, name)
        fn.argtypes, fn.restype = args, result
    return api


def read_text(path: Path) -> str:
    """Concurrent Windows readers allow the writer's atomic os.replace."""
    if os.name != "nt":
        return path.read_text(encoding="utf-8")
    import msvcrt
    api = _kernel()
    handle = api.CreateFileW(str(path), 0x80000000, 1 | 2 | 4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = str(path)
        raise error
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        api.CloseHandle(handle)
        raise
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        return stream.read()


def windows_pid_alive(pid: int) -> bool:
    api = _kernel()
    handle = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:                             # process no longer exists
            return False
        if error == 5:                              # an existing process we cannot inspect
            return True
        raise ctypes.WinError(error)
    try:
        state = api.WaitForSingleObject(handle, 0)
        if state == 0:
            return False
        if state == 258:
            return True
        raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(handle)


def terminate_group(pid: int) -> None:
    """On Windows the guardian closes its job after this terminates the worker."""
    if os.name != "nt":
        os.killpg(pid, signal.SIGKILL)
        return
    api = _kernel()
    handle = api.OpenProcess(0x0001, False, pid)      # PROCESS_TERMINATE
    if not handle:
        if ctypes.get_last_error() == 87:
            raise ProcessLookupError(pid)
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not api.TerminateProcess(handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(handle)


def worker_pipe(value: int) -> int:
    if os.name != "nt":
        return value
    import msvcrt
    return msvcrt.open_osfhandle(value, os.O_RDONLY | os.O_BINARY)


def pipe_ready(fd: int, seconds: float) -> bool:
    if os.name != "nt":
        import select
        return bool(select.select([fd], [], [], seconds)[0])
    import msvcrt
    from ctypes import wintypes as w
    api, available = _kernel(), w.DWORD()
    deadline = time.monotonic() + seconds
    while True:
        if not api.PeekNamedPipe(msvcrt.get_osfhandle(fd), None, 0, None,
                                 ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error == 109:                        # EOF: let the shared read loop consume it
                return True
            raise ctypes.WinError(error)
        if available.value:
            return True
        left = deadline - time.monotonic()
        if left <= 0:
            return False
        time.sleep(min(0.02, left))


def spawn_worker(argv: list[str], read_fd: int, **kwargs) -> subprocess.Popen:
    if os.name != "nt":
        return subprocess.Popen(argv, pass_fds=(read_fd,), start_new_session=True, **kwargs)
    import msvcrt
    handle = msvcrt.get_osfhandle(read_fd)
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": [handle]}
    os.set_handle_inheritable(handle, True)
    try:
        # argv's pipe position contains a CRT fd on POSIX and the inherited handle here.
        argv = [*argv[:-2], str(handle), argv[-1]]
        return subprocess.Popen(argv, startupinfo=startup, close_fds=True,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, **kwargs)
    finally:
        os.set_handle_inheritable(handle, False)


def start_guardian(jobdir: Path, caller: int, pipe_fd: int | None = None) -> None:
    """Native job ownership is armed before the worker runs any project code."""
    argv = [sys.executable, "-m", __name__, "guard", str(jobdir), str(os.getpid()),
            str(pipe_fd if pipe_fd is not None else -1), str(caller)]
    if pipe_fd is None:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        process = spawn_worker(argv, pipe_fd, stdin=subprocess.DEVNULL)
    ready = jobdir / "guardian.json"
    deadline = time.monotonic() + 5
    while not ready.is_file():
        if process.poll() is not None:
            raise RuntimeError(f"Windows worker guardian failed (exit {process.returncode}; see job log)")
        if time.monotonic() >= deadline:
            process.terminate()
            raise RuntimeError("Windows worker guardian did not establish process ownership")
        time.sleep(0.02)


def _job_for(worker: int):
    from ctypes import wintypes as w

    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", w.DWORD), ("min_working", ctypes.c_size_t),
                    ("max_working", ctypes.c_size_t), ("active", w.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]

    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", Counters), ("process_memory", ctypes.c_size_t),
                    ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                    ("peak_job", ctypes.c_size_t)]

    api = _kernel()
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = Extended()
        limits.basic.flags = 0x00002000              # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        handle = api.OpenProcess(0x0100 | 0x0001 | 0x00100000, False, worker)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not api.AssignProcessToJobObject(job, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(handle)
        return api, job
    except BaseException:
        api.CloseHandle(job)
        raise


def _guard(jobdir: Path, worker: int, caller: int, pipe: int | None) -> None:
    from .jobs import Lock, now_ms, read_json, write_json
    api, job = _job_for(worker)
    reason = None
    buffer = b""
    descriptor = worker_pipe(pipe) if pipe is not None else None

    def close_job():
        nonlocal job
        if job is not None:
            api.CloseHandle(job)
            job = None
    try:
        write_json(jobdir / "guardian.json", {"pid": os.getpid(), "worker": worker})
        while windows_pid_alive(worker):
            if descriptor is not None:
                if not pipe_ready(descriptor, 0.1):
                    continue
                message = os.read(descriptor, 4096)
                if message:
                    buffer += message
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        word, _, value = line.decode().partition(" ")
                        if word != "L":
                            raise ValueError(f"unknown message from the caller: {line!r}")
                        until = int(value)
                        write_json(jobdir / "lease.json", {"until_ms": until, "pid": caller})
                        with Lock(jobdir / "status.lock"):
                            status = read_json(jobdir / "status.json") or {}
                            status["lease_ms"] = until
                            write_json(jobdir / "status.json", status)
                    continue
                os.close(descriptor)
                descriptor = None
            lease = read_json(jobdir / "lease.json")
            if lease is None and (pipe is not None or not windows_pid_alive(caller)):
                reason = "the caller is gone"
                break
            if lease is not None and lease["until_ms"] <= now_ms():
                reason = "lease expired: nobody waits for the result"
                break
            time.sleep(0.1)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            if reason is not None:
                # Publish the cause before termination is observable. Hold the lock
                # through kernel termination so the worker cannot restore "running".
                with Lock(jobdir / "status.lock"):
                    status = read_json(jobdir / "status.json") or {}
                    if status.get("state", "running") == "running":
                        status.update(state="stopped", current=None, reason=reason)
                        write_json(jobdir / "status.json", status)
                    close_job()
                    while windows_pid_alive(worker):
                        time.sleep(0.01)
        finally:
            close_job()                            # every error still ends the owned tree
    while windows_pid_alive(worker):
        time.sleep(0.01)
    status = read_json(jobdir / "status.json") or {}
    if status.get("state", "running") == "running":
        status.update(state="stopped" if reason else "died", current=None,
                      reason=reason or "the worker ended without saying why: it was killed")
        write_json(jobdir / "status.json", status)


if __name__ == "__main__":
    _, directory, worker, pipe, caller = sys.argv[1:]
    _guard(Path(directory), int(worker), int(caller), int(pipe) if int(pipe) >= 0 else None)
