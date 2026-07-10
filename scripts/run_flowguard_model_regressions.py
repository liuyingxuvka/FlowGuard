"""Run manifest-owned FlowGuard model regressions with bounded evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from flowguard.model_regressions import (
    ModelRegressionManifest,
    audit_manifest,
    run_manifest_regressions,
)


@dataclass(frozen=True)
class RunnerResult:
    """Compatibility result for callers that use a repository without a manifest."""

    path: str
    exit_code: int
    seconds: float
    stdout_tail: tuple[str, ...] = ()
    stderr_tail: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def discover_runners(root: str | Path = ".") -> tuple[Path, ...]:
    base = Path(root).resolve() / ".flowguard"
    return tuple(sorted(base.rglob("run_checks.py"))) if base.is_dir() else ()


def run_regressions(
    root: str | Path = ".",
    *,
    fail_fast: bool = False,
    tail_lines: int = 20,
) -> tuple[RunnerResult, ...]:
    """Preserve the pre-manifest helper for small external fixtures.

    Repository release execution goes through :func:`run_manifest_regressions`.
    """

    root_path = Path(root).resolve()
    rows: list[RunnerResult] = []
    for runner in discover_runners(root_path):
        started = time.monotonic()
        completed = subprocess.run(
            [sys.executable, str(runner)],
            cwd=root_path,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        rows.append(
            RunnerResult(
                path=runner.relative_to(root_path).as_posix(),
                exit_code=completed.returncode,
                seconds=round(time.monotonic() - started, 3),
                stdout_tail=tuple(completed.stdout.splitlines()[-tail_lines:]),
                stderr_tail=tuple(completed.stderr.splitlines()[-tail_lines:]),
            )
        )
        if fail_fast and completed.returncode:
            break
    return tuple(rows)


def _progress(payload: dict[str, object]) -> None:
    event = payload.get("event")
    model_id = payload.get("model_id")
    if event == "started":
        print(f"START {model_id} timeout={payload.get('timeout_seconds')}s", file=sys.stderr, flush=True)
    else:
        print(
            f"DONE  {model_id} status={payload.get('status')} seconds={payload.get('seconds')}",
            file=sys.stderr,
            flush=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--tier", choices=("fast", "focused", "full"), default="fast")
    parser.add_argument("--model", action="append", default=[], help="Exact id or glob; repeatable.")
    parser.add_argument("--shard", help="Stable shard in N/M form.")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=float, help="Override each child timeout in seconds.")
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest = ModelRegressionManifest.load(args.root)
        if args.audit_only:
            audit = audit_manifest(args.root, manifest)
            payload = {
                "schema_version": "flowguard.model_regression_audit.v1",
                **audit.to_dict(),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "\n".join(
                [f"status: {'pass' if audit.ok else 'blocked'}", f"registered: {len(audit.registered_model_ids)}"]
                + [f"error: {item}" for item in audit.errors]
            ))
            return 0 if audit.ok else 2
        cancel = threading.Event()
        report = run_manifest_regressions(
            args.root,
            tier=args.tier,
            model_patterns=args.model,
            shard=args.shard,
            jobs=args.jobs,
            timeout=args.timeout,
            output_dir=args.output_dir,
            cancel_event=cancel,
            progress=None if args.json else _progress,
        )
    except (ValueError, OSError) as exc:
        payload = {
            "schema_version": "flowguard.validation_result.v1",
            "command": "flowguard-model-regressions",
            "status": "invalid_input",
            "exit_code": 3,
            "message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"status: invalid_input\nerror: {exc}")
        return 3

    validation = report.to_validation_result()
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(validation.format_text(full=args.full))
    return validation.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
