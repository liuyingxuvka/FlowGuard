"""Shared finite subprocess isolation for models, bound tests and shard execution.

Keep process-group ownership, descendant cleanup and timeout reporting in one
runtime. Legacy runner-model execution is retired.
"""
from __future__ import annotations

import sys
import os
import signal
import subprocess
import time
from pathlib import Path


# Internal process plumbing, excluded from semantic pytest environment identity.
PROCESS_OWNER_ENV = "_FLOWGUARD_PROCESS_OWNER"


def _group_active(group: int, *, session=False) -> bool:
    """Observe live owned members; inaccessible inventory is not clean proof."""
    uncertain = False
    if sys.platform.startswith("linux"):
        try:
            entries = list(Path("/proc").iterdir())
        except OSError:
            entries, uncertain = [], True
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[3 if session else 2]) == group and fields[0] not in {"Z", "X"}:
                    return True
            except (FileNotFoundError, ProcessLookupError):
                continue  # A process disappearing during observation is expected.
            except (OSError, ValueError, IndexError):
                uncertain = True
        if not uncertain:
            return False
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return uncertain if session else False
    except OSError:
        return True
    return True


def _kill_owned(group, *, session=False):
    """A Linux session owns nested groups too; the coordinator stays outside it."""
    groups={group}
    if session and sys.platform.startswith('linux'):
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                fields=(entry/'stat').read_text().rsplit(')',1)[1].split()
                if int(fields[3])==group:groups.add(int(fields[2]))
            except (OSError,ValueError,IndexError):continue
    for owned in groups:
        try:os.killpg(owned,signal.SIGKILL)
        except ProcessLookupError:pass


def _descendants(pid: int) -> list[int]:
    """Linux only: all transitive children of pid (empty elsewhere)."""
    if not sys.platform.startswith("linux"):
        return []
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            children.setdefault(int(fields[1]), []).append(int(entry.name))
        except (OSError, ValueError, IndexError):
            continue
    found, stack = [], [pid]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def _inherited_owner(environment: dict) -> int | None:
    """Accept only a marker matching this real, separately coordinated session."""
    if os.name == "nt":
        return None
    try:
        group, session, coordinator = map(int, environment.get(PROCESS_OWNER_ENV, "").split(":"))
        if (group == session == os.getsid(0)
                and (sys.platform.startswith("linux") or os.getpgrp()==group)
                and coordinator != os.getpid() and os.getsid(coordinator) != session):
            # Orphans remain owned by this session after its leader exits;
            # their PPID chain is deliberately not an ownership requirement.
            return group
    except (ValueError, OSError):
        pass
    return None


def run_isolated_process(command: list[str], *, cwd: Path, env: dict,
                         timeout: float, stdout=None, stderr=None,
                         encoding: str = "utf-8", errors: str = "replace"
                         ) -> tuple[subprocess.CompletedProcess, bool, bool]:
    """Run one finite owner; normal nested helpers share its POSIX session. On Linux each nested
    helper has its own process group, so its coordinator can also clean
    children after an ordinary parent exit. The outside owner kills every
    live group of the session at the outer deadline.

    The topmost coordinator remains outside the group and confirms cleanup,
    including after leader exit. A nested timeout terminates its own helper group; the outside
    coordinator still owns the complete session and its outer deadline.
    Windows retains its bounded taskkill /T behavior.
    """
    inherited = _inherited_owner(env)
    child_env = dict(env)
    if os.name == "nt":
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        launched_command = command
    elif inherited is not None:
        options, launched_command = ({"process_group":0} if sys.platform.startswith("linux") else {}), command
    else:
        options = {"start_new_session": True}
        # stdlib-only exec bootstrap: installs the actual session id after
        # setsid, preserves PID, argv, streams and the requested environment.
        bootstrap = ("import os,sys;os.environ[" + repr(PROCESS_OWNER_ENV) + "]="
                     "str(os.getpgrp())+':'+str(os.getsid(0))+':" + str(os.getpid())
                     + "';os.execvpe(sys.argv[1],sys.argv[1:],os.environ)")
        launched_command = [sys.executable, "-c", bootstrap, *command]
        child_env.pop(PROCESS_OWNER_ENV, None)
    process = subprocess.Popen(launched_command, cwd=cwd, env=child_env, stdout=stdout,
                               stderr=stderr, encoding=encoding, errors=errors, **options)
    nested_group = inherited is not None and sys.platform.startswith("linux")
    owns_session = inherited is None
    group = process.pid if owns_session or nested_group else inherited
    timed_out = False
    output = error = None
    try:
        output, error = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
    lingering = os.name != "nt" and (owns_session or nested_group) and _group_active(group,session=owns_session)
    cleanup = True
    if timed_out or lingering:
        if os.name == "nt":
            try:
                killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=5, check=False)
                cleanup = killed.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                cleanup = False
        elif inherited is not None and not nested_group:
            for pid in _descendants(process.pid):      # a nested helper never kills its owner's group
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        else:
            try:
                _kill_owned(group,session=owns_session)
            except ProcessLookupError:
                pass
            except OSError:
                cleanup = False
        try:
            process.kill()
        except OSError:
            pass
        try:
            output, error = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            cleanup = False
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        if os.name != "nt" and (owns_session or nested_group):
            deadline = time.monotonic() + 1
            while _group_active(group,session=owns_session) and time.monotonic() < deadline:
                try:_kill_owned(group,session=owns_session)
                except OSError:cleanup=False
                time.sleep(.01)
            cleanup = cleanup and not _group_active(group,session=owns_session)
    cleanup = cleanup and process.poll() is not None
    code = 124 if timed_out else (70 if not cleanup else process.returncode)
    completed = subprocess.CompletedProcess(command, code, output or "", error or "")
    completed.lingering_killed = bool(lingering)      # leftover background processes were killed; not a failure
    return completed, timed_out, cleanup
