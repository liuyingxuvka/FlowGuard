"""Cross-platform containment and terminality for validation producers.

The supervisor treats stdout, a root PID, and root-process exit as diagnostics,
not completion proof. A command is terminal only when the contained process
set is empty after normal exit or bounded termination.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Mapping, Sequence


TERMINAL_ARTIFACT_SCHEMA = "flowguard.supervised_command_terminal.v1"


@dataclass(frozen=True)
class SupervisedCommandResult:
    command: tuple[str, ...]
    cwd: str
    episode_token: str
    started_at_epoch: float
    finished_at_epoch: float
    exit_code: int | None
    stdout: str
    stderr: str
    terminal_reason: str
    timed_out: bool
    cancelled: bool
    interrupted: bool
    termination_stage: str
    cleanup_confirmed: bool
    descendant_process_ids: tuple[int, ...]

    @property
    def ok(self) -> bool:
        return (
            self.exit_code == 0
            and self.cleanup_confirmed
            and self.terminal_reason == "process_exit"
            and not self.timed_out
            and not self.cancelled
            and not self.interrupted
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TERMINAL_ARTIFACT_SCHEMA,
            "command": list(self.command),
            "cwd": self.cwd,
            "episode_token": self.episode_token,
            "started_at_epoch": self.started_at_epoch,
            "finished_at_epoch": self.finished_at_epoch,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "terminal_reason": self.terminal_reason,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "interrupted": self.interrupted,
            "termination_stage": self.termination_stage,
            "cleanup_confirmed": self.cleanup_confirmed,
            "descendant_process_ids": list(self.descendant_process_ids),
            "status": "pass" if self.ok else "blocked",
            "claim_boundary": (
                "This artifact proves one contained command episode reached a "
                "terminal process-tree state. It does not prove command semantics."
            ),
        }


def _episode_token(
    command: Sequence[str],
    cwd: Path,
    started_at_epoch: float,
) -> str:
    payload = json.dumps(
        {
            "command": list(command),
            "cwd": str(cwd),
            "started_at_epoch": started_at_epoch,
            "supervisor_process_id": os.getpid(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "episode:" + hashlib.sha256(payload).hexdigest()


def write_terminal_artifact(
    path: str | Path,
    result: SupervisedCommandResult,
) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    content = (
        json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, target)
    return target


class _WindowsJob:
    def __init__(self) -> None:
        self.handle: int | None = None
        if os.name != "nt":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = (
            ctypes.c_void_p,
            wintypes.LPCWSTR,
        )
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        kernel32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        if not kernel32.SetInformationJobObject(
            handle,
            9,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OSError(error, "SetInformationJobObject failed")
        self.handle = int(handle)

    def assign(self, process: subprocess.Popen[str]) -> None:
        if self.handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.AssignProcessToJobObject.argtypes = (
            wintypes.HANDLE,
            wintypes.HANDLE,
        )
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        if not kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(self.handle),
            wintypes.HANDLE(int(process._handle)),  # type: ignore[attr-defined]
        ):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

    def terminate(self) -> None:
        if self.handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.TerminateJobObject.argtypes = (
            wintypes.HANDLE,
            wintypes.UINT,
        )
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        if not kernel32.TerminateJobObject(wintypes.HANDLE(self.handle), 1):
            raise OSError(ctypes.get_last_error(), "TerminateJobObject failed")

    def active_process_ids(self) -> tuple[int, ...] | None:
        if self.handle is None:
            return ()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.QueryInformationJobObject.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        size = 4096
        while size <= 1024 * 1024:
            buffer = ctypes.create_string_buffer(size)
            returned = wintypes.DWORD()
            if kernel32.QueryInformationJobObject(
                wintypes.HANDLE(self.handle),
                3,
                buffer,
                size,
                ctypes.byref(returned),
            ):
                count = ctypes.c_ulong.from_buffer(
                    buffer,
                    ctypes.sizeof(wintypes.DWORD),
                ).value
                offset = ctypes.sizeof(wintypes.DWORD) * 2
                array = (ctypes.c_size_t * count).from_buffer(buffer, offset)
                return tuple(sorted(int(item) for item in array if int(item)))
            if ctypes.get_last_error() not in {122, 234}:
                break
            size *= 2
        return None

    def close(self) -> None:
        if self.handle is not None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle(wintypes.HANDLE(self.handle))
            self.handle = None


def _posix_group_process_ids(group_id: int) -> tuple[int, ...]:
    proc = Path("/proc")
    if not proc.is_dir():
        return ()
    found: list[int] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text(encoding="utf-8").split()
            if len(fields) > 4 and int(fields[4]) == group_id:
                found.append(int(entry.name))
        except (OSError, ValueError):
            continue
    return tuple(sorted(found))


def _contained_process_ids(
    job: _WindowsJob,
    group_id: int | None,
) -> tuple[int, ...] | None:
    if os.name == "nt":
        return job.active_process_ids()
    if group_id is None:
        return ()
    return _posix_group_process_ids(group_id)


def _wait_for_contained_exit(
    job: _WindowsJob,
    group_id: int | None,
    timeout_seconds: float,
) -> tuple[int, ...] | None:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        process_ids = _contained_process_ids(job, group_id)
        if process_ids is None or not process_ids:
            return process_ids
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return process_ids
        time.sleep(min(0.05, remaining))


def _request_tree_termination(
    process: subprocess.Popen[str],
    group_id: int | None,
) -> bool:
    try:
        if os.name == "nt":
            if process.poll() is not None:
                return False
            process.send_signal(signal.CTRL_BREAK_EVENT)
        elif group_id is not None:
            os.killpg(group_id, signal.SIGTERM)
        else:
            process.terminate()
    except (OSError, ValueError):
        return False
    return True


def _force_kill_tree(
    process: subprocess.Popen[str],
    job: _WindowsJob,
    group_id: int | None,
) -> None:
    if os.name == "nt":
        try:
            job.terminate()
        except OSError:
            pass
    elif group_id is not None:
        try:
            os.killpg(group_id, signal.SIGKILL)
        except OSError:
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def run_supervised(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout_seconds: float,
    grace_seconds: float = 3.0,
    environment: Mapping[str, str] | None = None,
    cancel_event: Any | None = None,
) -> SupervisedCommandResult:
    """Run one command under a bounded process-tree terminality contract."""

    if not command:
        raise ValueError("supervised command must be non-empty")
    if timeout_seconds <= 0 or grace_seconds < 0:
        raise ValueError("supervised timeout must be positive and grace non-negative")
    root = Path(cwd).resolve()
    started = time.time()
    started_monotonic = time.monotonic()
    episode = _episode_token(command, root, started)
    job = _WindowsJob()
    popen_kwargs: dict[str, Any] = {
        "cwd": root,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": dict(environment) if environment is not None else None,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    timed_out = False
    cancelled = False
    interrupted = False
    stage = "none"
    reason = "process_exit"
    group_id: int | None = None
    communicated = False
    try:
        try:
            process = subprocess.Popen(tuple(command), **popen_kwargs)
            if os.name == "nt":
                job.assign(process)
            else:
                group_id = os.getpgid(process.pid)
            deadline = started_monotonic + timeout_seconds
            while True:
                if cancel_event is not None and bool(cancel_event.is_set()):
                    cancelled = True
                    reason = "cancelled"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    reason = "timeout"
                    break
                try:
                    stdout, stderr = process.communicate(
                        timeout=min(0.2, remaining)
                    )
                    communicated = True
                    break
                except subprocess.TimeoutExpired:
                    continue
        except KeyboardInterrupt:
            interrupted = True
            reason = "keyboard_interrupt"
        except BaseException:
            if process is not None:
                _force_kill_tree(process, job, group_id)
                try:
                    process.communicate(timeout=max(1.0, grace_seconds))
                except (OSError, subprocess.TimeoutExpired):
                    pass
                _wait_for_contained_exit(
                    job,
                    group_id,
                    max(1.0, grace_seconds),
                )
            raise

        observed_before_cleanup = _contained_process_ids(job, group_id)
        descendants_before_cleanup = (
            ()
            if observed_before_cleanup is None
            else observed_before_cleanup
        )
        abnormal = timed_out or cancelled or interrupted
        root_running = process is not None and process.poll() is None
        orphaned_descendants = (
            process is not None
            and not abnormal
            and not root_running
            and bool(descendants_before_cleanup)
        )
        if orphaned_descendants:
            reason = "descendants_after_root_exit"

        if process is not None and (
            abnormal
            or root_running
            or observed_before_cleanup is None
            or descendants_before_cleanup
        ):
            stage = "terminate"
            graceful_requested = _request_tree_termination(
                process,
                group_id,
            )
            remaining_ids = observed_before_cleanup
            if graceful_requested:
                remaining_ids = _wait_for_contained_exit(
                    job,
                    group_id,
                    grace_seconds,
                )
            if (
                process.poll() is None
                or remaining_ids is None
                or bool(remaining_ids)
            ):
                stage = "force_kill"
                _force_kill_tree(process, job, group_id)
                _wait_for_contained_exit(
                    job,
                    group_id,
                    max(1.0, grace_seconds),
                )

            if not communicated:
                try:
                    stdout, stderr = process.communicate(
                        timeout=max(1.0, grace_seconds)
                    )
                    communicated = True
                except (OSError, subprocess.TimeoutExpired):
                    pass

        observed_descendants = _contained_process_ids(job, group_id)
        descendants = (
            ()
            if observed_descendants is None
            else observed_descendants
        )
        cleanup_confirmed = (
            observed_descendants is not None
            and not descendants
        )
        if process is not None and process.poll() is None:
            cleanup_confirmed = False
            descendants = tuple(
                sorted(set(descendants + (process.pid,)))
            )
        exit_code = process.returncode if process is not None else None
        if not cleanup_confirmed:
            reason = "cleanup_unconfirmed"
        finished = time.time()
        return SupervisedCommandResult(
            command=tuple(str(item) for item in command),
            cwd=str(root),
            episode_token=episode,
            started_at_epoch=started,
            finished_at_epoch=finished,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            terminal_reason=reason,
            timed_out=timed_out,
            cancelled=cancelled,
            interrupted=interrupted,
            termination_stage=stage,
            cleanup_confirmed=cleanup_confirmed,
            descendant_process_ids=descendants,
        )
    finally:
        job.close()


__all__ = [
    "SupervisedCommandResult",
    "TERMINAL_ARTIFACT_SCHEMA",
    "run_supervised",
    "write_terminal_artifact",
]
