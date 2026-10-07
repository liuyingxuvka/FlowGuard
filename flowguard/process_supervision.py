"""Cross-platform containment and terminality for validation producers.

The supervisor treats stdout, a root PID, and root-process exit as diagnostics,
not completion proof. A command is terminal only when the contained process
set is empty after normal exit or bounded termination.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence


TERMINAL_ARTIFACT_SCHEMA = "flowguard.supervised_command_terminal.v2"
_SUPERVISION_ATTESTATION_KEY = os.urandom(32)


@dataclass(frozen=True)
class SupervisedCommandResult:
    command: tuple[str, ...]
    cwd: str
    episode_token: str
    started_at_epoch: float
    finished_at_epoch: float
    exit_code: int | None
    # The ordinary entry point returns text.  The byte entry point deliberately
    # keeps these fields as bytes so NUL-delimited Git paths and non-UTF-8
    # diagnostics never pass through a lossy decode/re-encode cycle.
    stdout: str | bytes
    stderr: str | bytes
    terminal_reason: str
    timed_out: bool
    cancelled: bool
    interrupted: bool
    termination_stage: str
    cleanup_confirmed: bool
    descendant_process_ids: tuple[int, ...]
    root_process_id: int | None = None
    root_process_running: bool = False
    containment_query_succeeded: bool = True
    contained_process_ids_before_cleanup: tuple[int, ...] = ()
    _producer_attestation: str = field(default="", repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return (
            _is_authentic_supervised_result(self)
            and self.exit_code == 0
            and self.cleanup_confirmed
            and not self.root_process_running
            and self.containment_query_succeeded
            and not self.descendant_process_ids
            and self.terminal_reason == "process_exit"
            and not self.timed_out
            and not self.cancelled
            and not self.interrupted
        )

    def to_dict(self) -> dict[str, Any]:
        def stream_value(value: str | bytes) -> str | dict[str, str]:
            if isinstance(value, bytes):
                return {
                    "encoding": "base64",
                    "data": base64.b64encode(value).decode("ascii"),
                }
            return value

        return {
            "schema_version": TERMINAL_ARTIFACT_SCHEMA,
            "command": list(self.command),
            "cwd": self.cwd,
            "episode_token": self.episode_token,
            "started_at_epoch": self.started_at_epoch,
            "finished_at_epoch": self.finished_at_epoch,
            "exit_code": self.exit_code,
            "stdout": stream_value(self.stdout),
            "stderr": stream_value(self.stderr),
            "terminal_reason": self.terminal_reason,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "interrupted": self.interrupted,
            "termination_stage": self.termination_stage,
            "cleanup_confirmed": self.cleanup_confirmed,
            "root_process_id": self.root_process_id,
            "root_process_running": self.root_process_running,
            "containment_query_succeeded": self.containment_query_succeeded,
            "contained_process_ids_before_cleanup": list(
                self.contained_process_ids_before_cleanup
            ),
            "descendant_process_ids": list(self.descendant_process_ids),
            "status": "pass" if self.ok else "blocked",
            "claim_boundary": (
                "This artifact proves one contained command episode reached a "
                "terminal process-tree state. It does not prove command semantics."
            ),
        }


def _stream_bytes(value: str | bytes) -> bytes:
    """Return the exact logical stream bytes used by the attestation."""

    return value if isinstance(value, bytes) else value.encode("utf-8")


def _attestation_payload(result: SupervisedCommandResult) -> bytes:
    return json.dumps(
        {
            "command": list(result.command),
            "cwd": result.cwd,
            "episode_token": result.episode_token,
            "started_at_epoch": result.started_at_epoch,
            "finished_at_epoch": result.finished_at_epoch,
            "exit_code": result.exit_code,
            "stdout_sha256": hashlib.sha256(_stream_bytes(result.stdout)).hexdigest(),
            "stderr_sha256": hashlib.sha256(_stream_bytes(result.stderr)).hexdigest(),
            "terminal_reason": result.terminal_reason,
            "timed_out": result.timed_out,
            "cancelled": result.cancelled,
            "interrupted": result.interrupted,
            "termination_stage": result.termination_stage,
            "cleanup_confirmed": result.cleanup_confirmed,
            "descendant_process_ids": list(result.descendant_process_ids),
            "root_process_id": result.root_process_id,
            "root_process_running": result.root_process_running,
            "containment_query_succeeded": result.containment_query_succeeded,
            "contained_process_ids_before_cleanup": list(
                result.contained_process_ids_before_cleanup
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _attest_supervised_result(
    result: SupervisedCommandResult,
) -> SupervisedCommandResult:
    attestation = hmac.new(
        _SUPERVISION_ATTESTATION_KEY,
        _attestation_payload(result),
        hashlib.sha256,
    ).hexdigest()
    return replace(result, _producer_attestation=attestation)


def _is_authentic_supervised_result(result: SupervisedCommandResult) -> bool:
    if not result._producer_attestation:
        return False
    expected = hmac.new(
        _SUPERVISION_ATTESTATION_KEY,
        _attestation_payload(result),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(result._producer_attestation, expected)


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

    def assign(self, process: subprocess.Popen[Any]) -> None:
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

    def assign_process_id(self, process_id: int) -> bool:
        """Adopt one already-running descendant into this supervision job.

        On Windows the venv ``python.exe`` launcher can create the real
        ``python3.x.exe`` child just after ``Popen`` returns.  Assigning the
        launcher alone therefore does not contain the command's actual
        process tree.  The supervisor adopts only the exact PIDs observed in
        the bounded launch snapshot; a process that exited or cannot be
        opened is simply left to the normal tree observation path.
        """

        if self.handle is None or not int(process_id):
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        open_process.restype = wintypes.HANDLE
        assign = kernel32.AssignProcessToJobObject
        assign.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        assign.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        # PROCESS_TERMINATE | PROCESS_SET_QUOTA are the documented minimum
        # rights for AssignProcessToJobObject.
        handle = open_process(0x0001 | 0x0200, False, int(process_id))
        if not handle:
            return False
        try:
            return bool(
                assign(
                    wintypes.HANDLE(self.handle),
                    wintypes.HANDLE(handle),
                )
            )
        finally:
            close_handle(handle)

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


_WINDOWS_ERROR_INVALID_HANDLE = 6
_WINDOWS_ERROR_NO_MORE_FILES = 18
_WINDOWS_ERROR_INVALID_PARAMETER = 87
_WINDOWS_ERROR_NOT_FOUND = 1168


def _windows_process_creation_time(process_id: int) -> tuple[int | None, str]:
    """Return one process instance identity, distinguishing gone from unknown.

    A PID is reusable.  Process-tree cleanup may only act on a PID whose
    creation time was observed, and a denied/failed identity query must remain
    unknown rather than being treated as an empty process set.
    """

    if os.name != "nt":
        return None, "gone"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    # Query the exact instance and its kernel terminal state through one
    # handle. A Toolhelp row and creation/exit timestamps alone can outlive
    # the process's signaled terminal state.
    handle = open_process(0x1000 | 0x00100000, False, int(process_id))
    if not handle:
        error = ctypes.get_last_error()
        if error in {
            _WINDOWS_ERROR_INVALID_HANDLE,
            _WINDOWS_ERROR_INVALID_PARAMETER,
            _WINDOWS_ERROR_NOT_FOUND,
        }:
            return None, "gone"
        return None, "unknown"
    try:
        return _windows_process_creation_time_from_handle(kernel32, handle)
    finally:
        close_handle(handle)


def _windows_process_creation_time_from_handle(
    kernel32: Any,
    handle: wintypes.HANDLE,
) -> tuple[int | None, str]:
    """Read an instance identity from an already-open process handle."""

    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    get_times = kernel32.GetProcessTimes
    get_times.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    get_times.restype = wintypes.BOOL
    wait = kernel32.WaitForSingleObject
    wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait.restype = wintypes.DWORD
    state = int(wait(handle, 0))
    if state == 0:  # WAIT_OBJECT_0: this retained instance has exited.
        return None, "gone"
    if state != 0x00000102:  # WAIT_TIMEOUT is the only known live state.
        return None, "unknown"
    if not get_times(
        handle,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        error = ctypes.get_last_error()
        if error in {
            _WINDOWS_ERROR_INVALID_HANDLE,
            _WINDOWS_ERROR_INVALID_PARAMETER,
            _WINDOWS_ERROR_NOT_FOUND,
        }:
            return None, "gone"
        return None, "unknown"
    value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
    # A retained process object can still answer GetProcessTimes after exit.
    # Its creation identity is then known, but it is not a live descendant.
    if int(exit_time.dwHighDateTime) or int(exit_time.dwLowDateTime):
        return None, "gone"
    # The process may have exited during GetProcessTimes. Confirm the live
    # state after reading identity, without observing or terminating a new PID.
    state = int(wait(handle, 0))
    if state == 0:
        return None, "gone"
    if state != 0x00000102:
        return None, "unknown"
    return value, "ok"


class _WindowsProcessInstances:
    """Hold exact owned instances until this episode ends, preventing PID reuse.

    The Popen root handle is borrowed. Other query/synchronize handles are
    closed here. A signaled retained parent still has an authenticated birth
    identity and can lead to a live orphan; signaled does not mean unknown.
    """

    def __init__(self, process: subprocess.Popen[Any]) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.root_process_id = int(process.pid)
        self.handles: dict[int, Any] = {self.root_process_id: process._handle}
        self.owned_creation_times: dict[int, int] = {}
        self.parents: dict[int, tuple[int, str]] = {}
        creation, status = self.identity(self.root_process_id)
        if creation is not None and status != "unknown":
            self.owned_creation_times[self.root_process_id] = creation

    def identity(self, process_id: int) -> tuple[int | None, str]:
        kernel = self.kernel
        if process_id not in self.handles:
            open_process = kernel.OpenProcess
            open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            open_process.restype = wintypes.HANDLE
            handle = open_process(0x1000 | 0x00100000, False, process_id)
            if not handle:
                return (None, "gone") if ctypes.get_last_error() in {
                    _WINDOWS_ERROR_INVALID_HANDLE, _WINDOWS_ERROR_INVALID_PARAMETER,
                    _WINDOWS_ERROR_NOT_FOUND,
                } else (None, "unknown")
            self.handles[process_id] = handle
        handle = self.handles[process_id]
        creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        get_times = kernel.GetProcessTimes
        get_times.argtypes = (wintypes.HANDLE, *(ctypes.POINTER(wintypes.FILETIME) for _ in range(4)))
        get_times.restype = wintypes.BOOL
        if not get_times(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                         ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return None, "unknown"
        value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        wait = kernel.WaitForSingleObject
        wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait.restype = wintypes.DWORD
        state = int(wait(handle, 0))
        if state == 0:
            return value, "gone"
        if state == 0x102:
            return value, "ok"
        return None, "unknown"

    def admit(self, process_id: int, parent: int, executable: str, creation: int) -> None:
        self.owned_creation_times[process_id] = creation
        self.parents[process_id] = (parent, executable)

    def parent_process_id(self, process_id: int) -> int | None:
        """Read ancestry from the same retained child instance, not its PID."""
        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = (
                ("ExitStatus", wintypes.LONG),
                ("PebBaseAddress", ctypes.c_void_p),
                ("AffinityMask", ctypes.c_size_t),
                ("BasePriority", wintypes.LONG),
                ("UniqueProcessId", ctypes.c_size_t),
                ("InheritedFromUniqueProcessId", ctypes.c_size_t),
            )
        query = ctypes.WinDLL("ntdll").NtQueryInformationProcess
        query.argtypes = (wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p,
                          wintypes.ULONG, ctypes.POINTER(wintypes.ULONG))
        query.restype = wintypes.LONG
        information = PROCESS_BASIC_INFORMATION()
        returned = wintypes.ULONG()
        status = int(query(self.handles[process_id], 0, ctypes.byref(information),
                           ctypes.sizeof(information), ctypes.byref(returned)))
        if status < 0 or int(information.UniqueProcessId) != process_id:
            return None
        return int(information.InheritedFromUniqueProcessId)

    def discard(self, process_id: int) -> None:
        if process_id == self.root_process_id or process_id in self.owned_creation_times:
            return
        handle = self.handles.pop(process_id, None)
        if handle is not None:
            close = self.kernel.CloseHandle
            close.argtypes = (wintypes.HANDLE,)
            close.restype = wintypes.BOOL
            close(handle)

    def close(self) -> None:
        close = self.kernel.CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close.restype = wintypes.BOOL
        for process_id, handle in self.handles.items():
            if process_id != self.root_process_id:
                close(handle)
        self.handles.clear()


def _identity_bound_windows_tree(
    root_process_id: int,
    parent_by_pid: Mapping[int, int],
    executable_by_pid: Mapping[int, str],
    instances: _WindowsProcessInstances,
    *,
    creation_by_pid: Mapping[int, int],
) -> dict[int, tuple[int, str, int]] | None:
    """Expand one process-table snapshot only through authenticated parents."""
    parent_to_children: dict[int, list[int]] = {}
    for pid, parent in parent_by_pid.items():
        parent_to_children.setdefault(parent, []).append(pid)
    pending = list(instances.owned_creation_times)
    if root_process_id not in pending:
        return None
    seen: set[int] = set()
    descendants: dict[int, tuple[int, str, int]] = {}
    while pending:
        parent = pending.pop(0)
        if parent in seen:
            continue
        seen.add(parent)
        parent_creation, parent_status = instances.identity(parent)
        expected_parent = instances.owned_creation_times[parent]
        if parent_status == "unknown" or parent_creation is None:
            return None
        if parent_creation != expected_parent:
            # A different parent instance cannot grant ownership to its kids.
            continue
        if parent != root_process_id and parent_status == "ok":
            old_parent, executable = instances.parents[parent]
            descendants[parent] = (old_parent, executable, parent_creation)
        for pid in parent_to_children.get(parent, ()):
            if pid == root_process_id or pid in seen:
                continue
            snapshot_creation = creation_by_pid.get(pid)
            if type(snapshot_creation) is not int or snapshot_creation <= 0:
                return None
            # A reused parent PID retains foreign, sometimes protected,
            # children in the system table. Their known earlier birth rules
            # out this episode before OpenProcess can fail on that foreign
            # instance. Snapshot ancestry alone never admits a new child.
            if snapshot_creation < parent_creation:
                continue
            creation, status = instances.identity(pid)
            if status == "unknown":
                return None
            if creation is None:
                # A gone, unobserved intermediate has no birth authority.
                # If it has children, their ownership is still unknown.
                if parent_to_children.get(pid):
                    return None
                continue
            if creation != snapshot_creation:
                # The PID changed between the coherent table and retained
                # handle. This observation cannot confirm the child tree.
                return None
            expected = instances.owned_creation_times.get(pid)
            if creation < parent_creation or (expected is not None and creation != expected):
                instances.discard(pid)
                continue
            actual_parent = instances.parent_process_id(pid)
            if actual_parent is None:
                return None
            if actual_parent != parent:
                # The Toolhelp row belonged to a different child instance,
                # replaced before its query handle could be retained.
                instances.discard(pid)
                continue
            executable = executable_by_pid.get(pid, "")
            instances.admit(pid, parent, executable, creation)
            pending.append(pid)
    # Query each retained owned instance at the decision point. This is one
    # immediate identity observation, not waiting for a live orphan to exit.
    current: dict[int, tuple[int, str, int]] = {}
    for pid, row in descendants.items():
        creation, status = instances.identity(pid)
        if status == "unknown" or creation is None:
            return None
        if status == "ok" and creation == row[2]:
            current[pid] = row
    return current


class _WindowsUnicodeString(ctypes.Structure):
    _fields_ = (
        ("Length", ctypes.c_uint16),
        ("MaximumLength", ctypes.c_uint16),
        ("Buffer", ctypes.c_void_p),
    )


class _WindowsSystemProcessPrefix(ctypes.Structure):
    # SystemProcessInformation's documented reserved prefix includes the
    # native CreateTime field. Use fixed-width integers for both Windows ABIs.
    _fields_ = (
        ("NextEntryOffset", ctypes.c_uint32),
        ("NumberOfThreads", ctypes.c_uint32),
        ("ReservedBeforeBirth", ctypes.c_byte * 24),
        ("CreateTime", ctypes.c_int64),
        ("UserTime", ctypes.c_int64),
        ("KernelTime", ctypes.c_int64),
        ("ImageName", _WindowsUnicodeString),
        ("BasePriority", ctypes.c_int32),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
    )


def _parse_windows_system_process_information(
    buffer: Any,
    used: int,
) -> dict[int, tuple[int, str, int]] | None:
    """Decode bounded, coherent PID/parent/birth rows; malformed is unknown."""
    prefix = _WindowsSystemProcessPrefix
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    expected_layout = {8: (96, 80, 88), 4: (80, 68, 72)}.get(pointer_size)
    if (
        expected_layout is None
        or prefix.CreateTime.offset != 32
        or (ctypes.sizeof(prefix), prefix.UniqueProcessId.offset,
            prefix.InheritedFromUniqueProcessId.offset) != expected_layout
        or not 0 < used <= ctypes.sizeof(buffer)
    ):
        return None
    base = ctypes.addressof(buffer)
    offset = 0
    rows: dict[int, tuple[int, str, int]] = {}
    try:
        while True:
            if offset + ctypes.sizeof(prefix) > used:
                return None
            row = prefix.from_buffer(buffer, offset)
            pid = int(row.UniqueProcessId or 0)
            parent = int(row.InheritedFromUniqueProcessId or 0)
            if pid in rows:
                return None
            image = row.ImageName
            name = ""
            if image.Length:
                address = int(image.Buffer or 0)
                if (image.Length % 2 or image.Length > image.MaximumLength
                    or not base <= address <= base + used - image.Length):
                    return None
                name = ctypes.string_at(address, image.Length).decode("utf-16-le")
            rows[pid] = (parent, name, int(row.CreateTime))
            advance = int(row.NextEntryOffset)
            if advance == 0:
                return rows
            if advance < ctypes.sizeof(prefix) or advance % pointer_size:
                return None
            offset += advance
    except (ValueError, UnicodeError, OverflowError):
        return None


def _windows_system_process_snapshot() -> dict[int, tuple[int, str, int]] | None:
    """Read SystemProcessInformation once, with a bounded buffer and ABI check."""
    if os.name != "nt":
        return None
    try:
        query = ctypes.WinDLL("ntdll").NtQuerySystemInformation
    except OSError:
        return None
    query.argtypes = (ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                      ctypes.POINTER(ctypes.c_uint32))
    query.restype = ctypes.c_int32
    size = 65536
    for _ in range(9):
        if size > 16 * 1024 * 1024:
            return None
        buffer = ctypes.create_string_buffer(size)
        returned = ctypes.c_uint32()
        try:
            status = int(query(5, buffer, size, ctypes.byref(returned))) & 0xffffffff
        except OSError:
            return None
        if status == 0xc0000004:  # STATUS_INFO_LENGTH_MISMATCH
            size = max(size * 2, int(returned.value) + 10240)
            continue
        if status != 0:
            return None
        rows = _parse_windows_system_process_information(buffer, int(returned.value))
        if rows is None:
            return None
        # Check the actual native layout against our live instance, using the
        # same handle birth API that authenticates owned processes below.
        self_birth, self_status = _windows_process_creation_time(os.getpid())
        self_row = rows.get(os.getpid())
        if self_status != "ok" or self_row is None or self_row[2] != self_birth:
            return None
        return rows
    return None


def _windows_process_tree_snapshot(
    root_process_id: int | None,
    *,
    instances: _WindowsProcessInstances | None = None,
) -> dict[int, tuple[int, str, int]] | None:
    """Return descendant PID -> (parent PID, executable, creation time).

    ``None`` means the process table or an instance identity could not be
    confirmed.  An empty mapping is a confirmed snapshot with no descendants.
    """

    if os.name != "nt" or root_process_id is None:
        return {}
    rows = _windows_system_process_snapshot()
    if rows is None:
        return None
    parent_by_pid = {pid: row[0] for pid, row in rows.items() if pid}
    executable_by_pid = {pid: row[1] for pid, row in rows.items() if pid}
    creation_by_pid = {pid: row[2] for pid, row in rows.items() if pid}

    if instances is None:
        # A nonempty ancestry needs an original instance authority. Do not
        # turn a bare PID into ownership, including private callers/tests.
        return None if int(root_process_id) in parent_by_pid.values() else {}
    return _identity_bound_windows_tree(
        int(root_process_id), parent_by_pid, executable_by_pid, instances,
        creation_by_pid=creation_by_pid,
    )


def _terminate_windows_process_ids(
    process_ids: Sequence[int],
    *,
    cleanup_deadline: float,
    expected_creation_times: Mapping[int, int] | None = None,
) -> None:
    """Terminate and await exact observed instances within one cleanup deadline."""

    if os.name != "nt":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    terminate = kernel32.TerminateProcess
    terminate.argtypes = (wintypes.HANDLE, wintypes.UINT)
    terminate.restype = wintypes.BOOL
    wait = kernel32.WaitForSingleObject
    wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    expected = {
        int(process_id): int(creation_time)
        for process_id, creation_time in (expected_creation_times or {}).items()
    }
    for process_id in sorted(set(int(item) for item in process_ids if int(item))):
        # A bare PID grants no termination authority. Job-owned members without
        # an observed birth remain covered by the separate Job termination path.
        if process_id not in expected:
            continue
        handle = open_process(0x0001 | 0x1000 | 0x00100000, False, process_id)
        if not handle:
            continue
        try:
            current_creation, status = _windows_process_creation_time_from_handle(
                kernel32,
                handle,
            )
            if status != "ok" or current_creation != expected[process_id]:
                continue
            if terminate(handle, 1):
                # TerminateProcess is asynchronous. Keep this same authenticated
                # handle open until its bounded wait finishes; never reopen by
                # PID or renew the deadline for another member. Timeout/unknown
                # does not establish cleanup: final tree observations still own
                # the terminal verdict below.
                remaining_ms = min(
                    0xfffffffe,
                    max(0, int((cleanup_deadline - time.monotonic()) * 1000)),
                )
                wait(handle, remaining_ms)
        finally:
            close_handle(handle)


def _adopt_windows_launch_descendants(
    job: _WindowsJob,
    root_process_id: int | None,
    *,
    observation_seconds: float = 0.1,
    instances: _WindowsProcessInstances | None = None,
) -> dict[int, tuple[int, str, int]] | None:
    """Adopt launcher/runtime descendants during one bounded launch window.

    Windows Python launchers commonly materialize the real interpreter a few
    milliseconds after ``Popen`` returns.  A single immediate snapshot misses
    that process, while treating every post-exit parent-table PID as an
    orphan creates false failures because the launcher is not the semantic
    command root.  This short, finite observation window attaches each exact
    descendant to the existing Job Object; later children then inherit the
    same containment and the normal job query remains authoritative.
    """

    if os.name != "nt" or root_process_id is None:
        return {}
    deadline = time.monotonic() + max(0.0, observation_seconds)
    observed: dict[int, tuple[int, str, int]] = {}
    while True:
        current = _windows_process_tree_snapshot(root_process_id, instances=instances)
        if current is None:
            return None
        for process_id, entry in current.items():
            if process_id not in observed:
                job.assign_process_id(process_id)
                observed[process_id] = entry
        if time.monotonic() >= deadline:
            break
        time.sleep(0.01)
    return observed


def _windows_process_tree_observation(
    root_process_id: int | None,
    observed_process_ids: Sequence[int],
    *,
    instances: _WindowsProcessInstances | None = None,
) -> dict[int, tuple[int, str, int]] | None:
    """Take one current snapshot from the root and remembered intermediates.

    A launcher can exit while a detached grandchild remains.  Querying every
    remembered intermediate PID keeps that orphan reachable in the bounded
    observation window.  The caller treats ``None`` as an unknown query and
    never turns it into a clean empty tree.
    """

    if os.name != "nt" or root_process_id is None:
        return {}
    # The retained instance forest covers remembered intermediates in one
    # table observation. Never rescan an old PID as an unrelated new parent.
    if instances is None and observed_process_ids:
        return None
    return _windows_process_tree_snapshot(root_process_id, instances=instances)


def _confirmed_windows_process_ids(
    snapshot: Mapping[int, tuple[int, str, int]],
    expected_creation_times: Mapping[int, int],
    reused_process_ids: Sequence[int] = (),
) -> tuple[int, ...]:
    """Keep only current rows matching the originally observed PID instance."""

    reused = {int(process_id) for process_id in reused_process_ids}
    expected = {int(process_id): int(value) for process_id, value in expected_creation_times.items()}
    return tuple(
        sorted(
            int(process_id)
            for process_id, (_parent, _executable, creation_time) in snapshot.items()
            if int(process_id) not in reused
            and expected.get(int(process_id)) == int(creation_time)
        )
    )


def _terminal_process_tree_observation(
    job: _WindowsJob,
    group_id: int | None,
    process: subprocess.Popen[Any] | None,
    observed_process_ids: Sequence[int],
    *,
    observation_seconds: float,
    instances: _WindowsProcessInstances | None = None,
) -> tuple[tuple[int, ...] | None, dict[int, tuple[int, str, int]] | None, bool]:
    """Reobserve an unknown terminal query inside the same command episode.

    Known live roots/descendants are never retried into success here.  Only
    query uncertainty gets a finite observation window; no command, job or
    termination owner is started again.  Exhausted uncertainty stays unknown.
    """
    deadline = time.monotonic() + max(0.0, observation_seconds)
    while True:
        contained = _contained_process_ids(job, group_id)
        snapshot = _windows_process_tree_observation(
            process.pid if process is not None else None, observed_process_ids, instances=instances
        )
        root_running = process is not None and process.poll() is None
        if contained is not None and snapshot is not None:
            return contained, snapshot, root_running
        if (root_running
                or _descendant_process_ids(contained, process.pid if process is not None else None)
                or snapshot):
            return contained, snapshot, root_running
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return contained, snapshot, root_running
        time.sleep(min(0.01, remaining))


def _descendant_process_ids(
    contained_process_ids: tuple[int, ...] | None,
    root_process_id: int | None,
) -> tuple[int, ...] | None:
    """Return true descendants, excluding a transiently retained root PID."""

    if contained_process_ids is None:
        return None
    return tuple(
        process_id
        for process_id in contained_process_ids
        if root_process_id is None or process_id != root_process_id
    )


def _tree_blocking_process_ids(
    contained_process_ids: tuple[int, ...] | None,
    process: subprocess.Popen[str],
) -> tuple[int, ...] | None:
    descendants = _descendant_process_ids(contained_process_ids, process.pid)
    if descendants is None:
        return None
    if process.poll() is None:
        return tuple(sorted(set((*descendants, process.pid))))
    return descendants


def _wait_for_tree_exit(
    job: _WindowsJob,
    group_id: int | None,
    process: subprocess.Popen[str],
    timeout_seconds: float,
) -> tuple[int, ...] | None:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        process_ids = _tree_blocking_process_ids(
            _contained_process_ids(job, group_id),
            process,
        )
        if process_ids is None or not process_ids:
            return process_ids
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return process_ids
        time.sleep(min(0.05, remaining))


def _clean_windows_observed_descendants(
    process_ids: Sequence[int],
    *,
    root_process_id: int,
    observed_process_ids: set[int],
    expected_creation_times: Mapping[int, int],
    instances: _WindowsProcessInstances | None,
    record_snapshot: Callable[[Mapping[int, tuple[int, str, int]]], None],
    cleanup_deadline: float,
) -> None:
    """Clean newly authenticated instances once, before the final verdict."""

    if os.name != "nt":
        return
    attempted = {
        (int(pid), int(expected_creation_times[pid]))
        for pid in process_ids if pid in expected_creation_times
    }
    _terminate_windows_process_ids(
        process_ids, expected_creation_times=expected_creation_times,
        cleanup_deadline=cleanup_deadline,
    )
    while time.monotonic() < cleanup_deadline:
        snapshot = _windows_process_tree_observation(
            root_process_id, observed_process_ids, instances=instances,
        )
        if snapshot is None:
            return
        record_snapshot(snapshot)
        current_ids = _confirmed_windows_process_ids(snapshot, expected_creation_times)
        new_ids = tuple(
            pid for pid in current_ids
            if (pid, int(expected_creation_times[pid])) not in attempted
        )
        if not new_ids or time.monotonic() >= cleanup_deadline:
            return
        attempted.update((pid, int(expected_creation_times[pid])) for pid in new_ids)
        _terminate_windows_process_ids(
            new_ids, expected_creation_times=expected_creation_times,
            cleanup_deadline=cleanup_deadline,
        )


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
    process: subprocess.Popen[Any],
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


def _run_supervised_core(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout_seconds: float,
    grace_seconds: float = 3.0,
    environment: Mapping[str, str] | None = None,
    cancel_event: Any | None = None,
    input_bytes: bytes | None = None,
    use_stdin_pipe: bool = False,
    preserve_bytes: bool = False,
) -> SupervisedCommandResult:
    """Run one command under the shared bounded process-tree contract.

    The process lifecycle is intentionally implemented once.  Text and byte
    callers differ only in whether stdin is a closed pipe and whether the
    captured streams are decoded after the process tree reaches terminality.
    """

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
        "env": dict(environment) if environment is not None else None,
    }
    if not preserve_bytes:
        # Keep the historical text API's universal-newline behavior.  The byte
        # path below intentionally omits this wrapper so raw NUL/non-UTF-8
        # bytes remain untouched.
        popen_kwargs.update(
            {
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            }
        )
    if use_stdin_pipe:
        # A byte query must receive EOF when no input is supplied.  This keeps
        # a Git child that accidentally reads stdin inside the same timeout
        # boundary instead of inheriting the supervisor's console.
        popen_kwargs["stdin"] = subprocess.PIPE
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process: subprocess.Popen[Any] | None = None
    process_instances: _WindowsProcessInstances | None = None
    stdout = b""
    stderr = b""
    timed_out = False
    cancelled = False
    interrupted = False
    stage = "none"
    reason = "process_exit"
    group_id: int | None = None
    communicated = False
    communication_started = False
    observed_process_tree_ids: set[int] = set()
    observed_process_tree_executables: dict[int, str] = {}
    observed_process_tree_creation_times: dict[int, int] = {}
    reused_process_ids: set[int] = set()
    process_tree_query_failed = False

    def record_process_tree_snapshot(
        snapshot: Mapping[int, tuple[int, str, int]],
    ) -> None:
        """Remember only one PID instance throughout this command episode."""

        for process_id, (_parent, executable, creation_time) in snapshot.items():
            previous = observed_process_tree_creation_times.get(process_id)
            if previous is not None and previous != creation_time:
                # The PID was reused after the originally observed process
                # exited.  It is never safe to terminate the new instance.
                reused_process_ids.add(process_id)
                continue
            observed_process_tree_ids.add(process_id)
            observed_process_tree_creation_times[process_id] = creation_time
            observed_process_tree_executables[process_id] = executable

    def live_observed_process_ids(
        snapshot: Mapping[int, tuple[int, str, int]],
    ) -> set[int]:
        """Filter one current snapshot to the original PID instances."""

        return set(
            _confirmed_windows_process_ids(
                snapshot,
                observed_process_tree_creation_times,
                reused_process_ids,
            )
        )

    try:
        try:
            process = subprocess.Popen(
                command,
                **popen_kwargs,
            )
            if os.name == "nt":
                job.assign(process)
                process_instances = _WindowsProcessInstances(process)
                # Adopt the short-lived launcher/runtime chain before waiting
                # for output.  This keeps the Job Object authoritative for
                # both ordinary commands and detached descendants without
                # adding a retry or second execution path.
                launch_snapshot = _adopt_windows_launch_descendants(
                    job,
                    process.pid,
                    instances=process_instances,
                )
                if launch_snapshot is None:
                    process_tree_query_failed = True
                else:
                    record_process_tree_snapshot(launch_snapshot)
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
                    if use_stdin_pipe:
                        # After TimeoutExpired, communicate() must be resumed
                        # without sending the input a second time.  Keeping
                        # this state in the shared core also makes byte-mode
                        # timeout cleanup follow the text-mode process path.
                        if communication_started:
                            stdout, stderr = process.communicate(
                                timeout=min(0.2, remaining),
                            )
                        else:
                            communication_started = True
                            stdout, stderr = process.communicate(
                                input=input_bytes,
                                timeout=min(0.2, remaining),
                            )
                    else:
                        stdout, stderr = process.communicate(
                            timeout=min(0.2, remaining)
                        )
                    communicated = True
                    break
                except subprocess.TimeoutExpired:
                    snapshot = _windows_process_tree_observation(
                        process.pid,
                        observed_process_tree_ids,
                        instances=process_instances,
                    )
                    if snapshot is None:
                        process_tree_query_failed = True
                    else:
                        record_process_tree_snapshot(snapshot)
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
                _wait_for_tree_exit(
                    job,
                    group_id,
                    process,
                    max(1.0, grace_seconds),
                )
            raise

        observed_before_cleanup = _contained_process_ids(job, group_id)
        descendants_before_cleanup_raw = _descendant_process_ids(
            observed_before_cleanup,
            process.pid if process is not None else None,
        )
        # The Job Object normally contains the complete tree.  On Windows a
        # child can be spawned in the small interval between Popen returning
        # and AssignProcessToJobObject, so supplement the job observation with
        # one parent-table snapshot before deciding that a clean root exit is
        # terminal.
        process_tree_before_snapshot = _windows_process_tree_observation(
            process.pid if process is not None else None,
            observed_process_tree_ids,
            instances=process_instances,
        )
        if process_tree_before_snapshot is None:
            process_tree_query_failed = True
            process_tree_before_snapshot = {}
        else:
            record_process_tree_snapshot(process_tree_before_snapshot)
        observed_descendant_ids = set(descendants_before_cleanup_raw or ())
        observed_descendant_ids.update(
            live_observed_process_ids(process_tree_before_snapshot)
        )
        descendants_before_cleanup = tuple(sorted(observed_descendant_ids))
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
            or process_tree_query_failed
        ):
            stage = "terminate"
            graceful_requested = _request_tree_termination(
                process,
                group_id,
            )
            remaining_ids = _tree_blocking_process_ids(
                observed_before_cleanup,
                process,
            )
            if graceful_requested:
                remaining_ids = _wait_for_tree_exit(
                    job,
                    group_id,
                    process,
                    grace_seconds,
                )
            remaining_snapshot = _windows_process_tree_observation(
                process.pid if process is not None else None,
                observed_process_tree_ids,
                instances=process_instances,
            )
            if remaining_snapshot is None:
                process_tree_query_failed = True
                remaining_observed_ids: set[int] = set()
            else:
                record_process_tree_snapshot(remaining_snapshot)
                remaining_observed_ids = live_observed_process_ids(remaining_snapshot)
            if remaining_ids is not None:
                remaining_ids = tuple(
                    sorted(set(remaining_ids) | remaining_observed_ids)
                )
            # A descendant missed by job attachment is not covered by the
            # Job Object termination call.  Terminate the exact parent-table
            # descendants we observed, then take the normal final zero-tree
            # observation below.
            cleanup_deadline = time.monotonic() + max(1.0, grace_seconds)
            _clean_windows_observed_descendants(
                tuple(sorted(set(descendants_before_cleanup) | remaining_observed_ids)),
                root_process_id=process.pid,
                observed_process_ids=observed_process_tree_ids,
                expected_creation_times=observed_process_tree_creation_times,
                instances=process_instances,
                record_snapshot=record_process_tree_snapshot,
                cleanup_deadline=cleanup_deadline,
            )
            if (
                remaining_ids is None
                or bool(remaining_ids)
            ):
                stage = "force_kill"
                _force_kill_tree(process, job, group_id)
                _wait_for_tree_exit(
                    job,
                    group_id,
                    process,
                    max(0.0, cleanup_deadline - time.monotonic()),
                )

            if not communicated:
                try:
                    if use_stdin_pipe:
                        if communication_started:
                            stdout, stderr = process.communicate(
                                timeout=max(1.0, grace_seconds),
                            )
                        else:
                            communication_started = True
                            stdout, stderr = process.communicate(
                                input=input_bytes,
                                timeout=max(1.0, grace_seconds),
                            )
                    else:
                        stdout, stderr = process.communicate(
                            timeout=max(1.0, grace_seconds)
                        )
                    communicated = True
                except (OSError, subprocess.TimeoutExpired):
                    pass

        # A transient observation failure during launch or while the command
        # was running is enough to take the conservative termination path, but
        # it must not poison a later, successful terminal observation.  The
        # terminal state is fail-closed only when the final containment query
        # or final parent-table snapshot is still unknown.
        observed_descendants, final_snapshot, root_process_running = (
            _terminal_process_tree_observation(
                job, group_id, process, observed_process_tree_ids,
                observation_seconds=max(0.0, min(1.0, grace_seconds)),
                instances=process_instances,
            )
        )
        descendant_query = _descendant_process_ids(
            observed_descendants,
            process.pid if process is not None else None,
        )
        final_descendant_ids = set(descendant_query or ())
        final_process_tree_query_failed = False
        if final_snapshot is None:
            final_process_tree_query_failed = True
        else:
            record_process_tree_snapshot(final_snapshot)
            final_descendant_ids.update(live_observed_process_ids(final_snapshot))
        descendants = tuple(sorted(final_descendant_ids))
        cleanup_confirmed = (
            observed_descendants is not None
            and not final_process_tree_query_failed
            and not root_process_running
            and not descendants
        )
        exit_code = process.returncode if process is not None else None
        if not cleanup_confirmed:
            reason = "cleanup_unconfirmed"
        finished = time.time()
        if preserve_bytes:
            stdout_value: str | bytes = stdout
            stderr_value: str | bytes = stderr
        else:
            stdout_value = (
                stdout
                if isinstance(stdout, str)
                else stdout.decode("utf-8", errors="replace")
            )
            stderr_value = (
                stderr
                if isinstance(stderr, str)
                else stderr.decode("utf-8", errors="replace")
            )
        result = SupervisedCommandResult(
            command=tuple(str(item) for item in command),
            cwd=str(root),
            episode_token=episode,
            started_at_epoch=started,
            finished_at_epoch=finished,
            exit_code=exit_code,
            stdout=stdout_value,
            stderr=stderr_value,
            terminal_reason=reason,
            timed_out=timed_out,
            cancelled=cancelled,
            interrupted=interrupted,
            termination_stage=stage,
            cleanup_confirmed=cleanup_confirmed,
            descendant_process_ids=descendants,
            root_process_id=process.pid if process is not None else None,
            root_process_running=root_process_running,
            containment_query_succeeded=(
                observed_descendants is not None
                and not final_process_tree_query_failed
            ),
            contained_process_ids_before_cleanup=(
                observed_before_cleanup or ()
            ),
        )
        return _attest_supervised_result(result)
    finally:
        try:
            if process_instances is not None:
                process_instances.close()
        finally:
            job.close()


def run_supervised(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout_seconds: float,
    grace_seconds: float = 3.0,
    environment: Mapping[str, str] | None = None,
    cancel_event: Any | None = None,
) -> SupervisedCommandResult:
    """Run one command with the existing text-capture API."""

    return _run_supervised_core(
        command,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        grace_seconds=grace_seconds,
        environment=environment,
        cancel_event=cancel_event,
    )


def run_supervised_bytes(
    command: Sequence[str],
    *,
    cwd: str | Path,
    input_bytes: bytes | None = None,
    timeout_seconds: float = 30.0,
    grace_seconds: float = 3.0,
    environment: Mapping[str, str] | None = None,
    cancel_event: Any | None = None,
) -> SupervisedCommandResult:
    """Run one command while preserving stdout/stderr as exact bytes.

    This is the byte-preserving companion to :func:`run_supervised`.  It uses
    the same process-tree containment, timeout, cancellation, and cleanup
    logic and therefore cannot create a second kill/retry path.
    """

    if input_bytes is not None and not isinstance(input_bytes, bytes):
        raise TypeError("supervised byte input must be bytes or None")
    return _run_supervised_core(
        command,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        grace_seconds=grace_seconds,
        environment=environment,
        cancel_event=cancel_event,
        input_bytes=input_bytes,
        use_stdin_pipe=True,
        preserve_bytes=True,
    )


__all__ = [
    "SupervisedCommandResult",
    "TERMINAL_ARTIFACT_SCHEMA",
    "run_supervised",
    "run_supervised_bytes",
    "write_terminal_artifact",
]
