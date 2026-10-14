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
from pathlib import Path
from typing import Any, Callable


COMPLETION_LINE = "FLOWGUARD_RUNNER_DONE "
LOADED_LINE = "FLOWGUARD_LOADED "


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
