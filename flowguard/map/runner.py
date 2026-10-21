"""Run a model check function directly and turn its result into a process exit code.

Used by runner-style models (``run_checks.py`` next to a ``model.py``):

    from flowguard.map.runner import run_owner
    if __name__ == "__main__":
        raise SystemExit(run_owner(main))

Accepted results: an int exit code, an object with ``.ok``,
a dict with ``exit_code`` / ``ok`` / ``results``, or a nonempty sequence of results
that each have ``.ok`` or ``["ok"]``.  Anything else is reported and fails.
"""

from __future__ import annotations

import sys
import json
import runpy
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


COMPLETION_LINE = "FLOWGUARD_RUNNER_DONE "
LOADED_LINE = "FLOWGUARD_LOADED "


# Internal process plumbing, excluded from semantic pytest environment identity.
PROCESS_OWNER_ENV = "_FLOWGUARD_PROCESS_OWNER"


def _group_active(group: int) -> bool:
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
                if int(fields[2]) == group and fields[0] not in {"Z", "X"}:
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
        return False
    except OSError:
        return True
    return True


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
        if (group == session == os.getpgrp() == os.getsid(0)
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
    """Run one finite owner; normal nested helpers share its POSIX session.

    The topmost coordinator remains outside the group and confirms cleanup,
    including after leader exit. A nested timeout terminates the whole owned
    leaf, including its local helper; the outside coordinator reports failure.
    Windows retains its bounded taskkill /T behavior.
    """
    inherited = _inherited_owner(env)
    child_env = dict(env)
    if os.name == "nt":
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        launched_command = command
    elif inherited is not None:
        options, launched_command = {}, command
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
    group = inherited if inherited is not None else process.pid
    timed_out = False
    output = error = None
    try:
        output, error = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
    lingering = os.name != "nt" and inherited is None and _group_active(group)
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
        elif inherited is not None:
            for pid in _descendants(process.pid):      # a nested helper never kills its owner's group
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        else:
            try:
                os.killpg(group, signal.SIGKILL)
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
        if os.name != "nt" and inherited is None:
            deadline = time.monotonic() + 1
            while _group_active(group) and time.monotonic() < deadline:
                time.sleep(.01)
            cleanup = cleanup and not _group_active(group)
    cleanup = cleanup and process.poll() is not None
    code = 124 if timed_out else (70 if lingering or not cleanup else process.returncode)
    return subprocess.CompletedProcess(command, code, output or "", error or ""), timed_out, cleanup


def _ok(item: Any) -> bool:
    if isinstance(item, dict):
        return bool(item.get("ok", item.get("status") in ("ok", "pass")))
    return bool(getattr(item, "ok", False))


def exit_code_of(result: Any) -> int:
    if isinstance(result, bool):
        return 0 if result else 1
    if isinstance(result, int):
        return result
    if result is None:
        print("run_owner: the check returned None; no checks completed", file=sys.stderr)
        return 3
    if isinstance(result, dict):
        if "exit_code" in result:
            return int(result["exit_code"])
        if "ok" in result:
            return 0 if result["ok"] else 1
        if "results" in result:
            return 0 if result["results"] and all(_ok(r) for r in result["results"]) else 1
    if hasattr(result, "ok"):
        return 0 if result.ok else 1
    if isinstance(result, (list, tuple)):
        return 0 if result and all(_ok(r) for r in result) else 1
    print(f"run_owner: unsupported result type {type(result).__name__}", file=sys.stderr)
    return 3


def run_owner(check: Callable[[], Any]) -> int:
    completed = 0
    previous = sys.getprofile()

    def observe(frame, event, result):
        nonlocal completed
        # Count actual completed check reports, not an integer returned by
        # main(). No line tracing, no nested test launch and no retained reports.
        if event == "return":
            if frame.f_code.co_name not in {"__init__", "__new__", "__post_init__", "_check_invariant"}:
                report = getattr(result, "model_report", result)
                if callable(getattr(report, "format_text", None)) and isinstance(getattr(report, "ok", None), bool):
                    completed += 1
                elif isinstance(result, dict) and isinstance(result.get("ok"), bool):
                    completed += 1
        if previous is not None:
            previous(frame, event, result)

    try:
        sys.setprofile(observe)
        result = check()
    finally:
        sys.setprofile(previous)
    code = exit_code_of(result)
    if not completed:
        print("run_owner: no FlowGuard checks completed; exit code alone proves nothing", file=sys.stderr)
        code = 3
    print(COMPLETION_LINE + json.dumps({"exit_code": code, "checked": completed}), flush=True)
    return code


def _probe_main() -> int:
    """Run a runner unchanged and disclose loaded project files to the proof owner."""
    path = Path(sys.argv[1]).resolve()
    root = Path.cwd().resolve()
    sys.argv = [str(path)]
    sys.path.insert(0, str(path.parent))
    code = 0
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        loaded = set()
        for module in list(sys.modules.values()):
            filename = getattr(module, "__file__", None)
            if filename:
                resolved = Path(filename).resolve()
                if resolved.is_relative_to(root):
                    loaded.add(resolved.relative_to(root).as_posix())
        sys.__stderr__.write(LOADED_LINE + json.dumps(sorted(loaded)) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(_probe_main())
