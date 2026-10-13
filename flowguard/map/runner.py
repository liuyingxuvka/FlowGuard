"""Run a model check function directly and turn its result into a process exit code.

Used by runner-style models (``run_checks.py`` next to a ``model.py``):

    from flowguard.map.runner import run_owner
    if __name__ == "__main__":
        raise SystemExit(run_owner(main))

Accepted results: an int exit code, None (= 0), an object with ``.ok``,
a dict with ``exit_code`` / ``ok`` / ``results``, or a sequence of results
that each have ``.ok`` or ``["ok"]``.  Anything else is reported and fails.
"""

from __future__ import annotations

import sys
from typing import Any, Callable


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
        return 0
    if isinstance(result, dict):
        if "exit_code" in result:
            return int(result["exit_code"])
        if "ok" in result:
            return 0 if result["ok"] else 1
        if "results" in result:
            return 0 if all(_ok(r) for r in result["results"]) else 1
    if hasattr(result, "ok"):
        return 0 if result.ok else 1
    if isinstance(result, (list, tuple)):
        return 0 if result and all(_ok(r) for r in result) else 1
    print(f"run_owner: unsupported result type {type(result).__name__}", file=sys.stderr)
    return 3


def run_owner(check: Callable[[], Any]) -> int:
    return exit_code_of(check())
