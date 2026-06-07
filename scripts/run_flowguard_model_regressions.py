"""Run every present FlowGuard local model regression runner.

The public repository tracks some `.flowguard` models and a local checkout may
also contain ignored adoption models. This command treats every present
`run_checks.py` as release evidence and fails if any runner fails.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RunnerResult:
    path: str
    exit_code: int
    seconds: float
    stdout_tail: tuple[str, ...] = ()
    stderr_tail: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "exit_code": self.exit_code,
            "ok": self.ok,
            "seconds": self.seconds,
            "stdout_tail": list(self.stdout_tail),
            "stderr_tail": list(self.stderr_tail),
        }


def discover_runners(root: str | Path = ".") -> tuple[Path, ...]:
    root_path = Path(root).resolve()
    flowguard_dir = root_path / ".flowguard"
    if not flowguard_dir.is_dir():
        return ()
    return tuple(sorted(path for path in flowguard_dir.rglob("run_checks.py") if path.is_file()))


def _tail(text: str, *, lines: int) -> tuple[str, ...]:
    if lines <= 0:
        return ()
    return tuple(text.splitlines()[-lines:])


def run_regressions(
    root: str | Path = ".",
    *,
    fail_fast: bool = False,
    tail_lines: int = 20,
) -> tuple[RunnerResult, ...]:
    root_path = Path(root).resolve()
    results: list[RunnerResult] = []
    for runner in discover_runners(root_path):
        started = time.monotonic()
        completed = subprocess.run(
            [sys.executable, str(runner)],
            cwd=root_path,
            text=True,
            capture_output=True,
            check=False,
        )
        elapsed = round(time.monotonic() - started, 3)
        rel_path = runner.relative_to(root_path).as_posix()
        result = RunnerResult(
            path=rel_path,
            exit_code=completed.returncode,
            seconds=elapsed,
            stdout_tail=_tail(completed.stdout, lines=tail_lines),
            stderr_tail=_tail(completed.stderr, lines=tail_lines),
        )
        results.append(result)
        if fail_fast and not result.ok:
            break
    return tuple(results)


def build_report(results: Sequence[RunnerResult], *, root: str | Path) -> dict[str, object]:
    failed = [result for result in results if not result.ok]
    return {
        "artifact_type": "flowguard_model_regression_report",
        "root": str(Path(root).resolve()),
        "runner_count": len(results),
        "failed_count": len(failed),
        "ok": not failed,
        "results": [result.to_dict() for result in results],
    }


def format_report(report: dict[str, object]) -> str:
    lines = [
        "=== flowguard local model regressions ===",
        f"root: {report['root']}",
        f"runner_count: {report['runner_count']}",
        f"failed_count: {report['failed_count']}",
        f"status: {'pass' if report['ok'] else 'blocked'}",
    ]
    for item in report["results"]:
        assert isinstance(item, dict)
        lines.append(
            f"{'OK' if item['ok'] else 'FAIL'} {item['path']} "
            f"exit={item['exit_code']} seconds={item['seconds']}"
        )
        if not item["ok"]:
            stdout_tail = item.get("stdout_tail") or ()
            stderr_tail = item.get("stderr_tail") or ()
            if stdout_tail:
                lines.append("stdout_tail:")
                lines.extend(f"  {line}" for line in stdout_tail)
            if stderr_tail:
                lines.append("stderr_tail:")
                lines.extend(f"  {line}" for line in stderr_tail)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--json", action="store_true", help="Print a JSON report.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed runner.")
    parser.add_argument("--tail-lines", type=int, default=20, help="Output lines retained for failed runners.")
    args = parser.parse_args(argv)

    results = run_regressions(args.root, fail_fast=args.fail_fast, tail_lines=args.tail_lines)
    report = build_report(results, root=args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
