"""Execute one OpenSpec verification owner and project only that owner's status."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


def selected_check_passed(payload: Mapping[str, Any], check_id: str) -> bool:
    """Return true only for one exact passing check with no blocking issue."""

    issues = payload.get("issues", ())
    if not isinstance(issues, list) or any(
        isinstance(issue, Mapping) and issue.get("level") == "blocking"
        for issue in issues
    ):
        return False
    checks = payload.get("checks", ())
    if not isinstance(checks, list):
        return False
    selected = [
        check
        for check in checks
        if isinstance(check, Mapping) and check.get("id") == check_id
    ]
    return len(selected) == 1 and selected[0].get("status") == "passed"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--change", required=True)
    parser.add_argument("--check", required=True)
    parser.add_argument("--mode", choices=("focused", "full"), default="full")
    parser.add_argument("--node", required=True)
    parser.add_argument("--openspec-js", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = [
        str(Path(args.node)),
        str(Path(args.openspec_js)),
        "verify",
        args.change,
        "--check",
        args.check,
        "--mode",
        args.mode,
        "--json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    try:
        payload = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        return 1
    return 0 if isinstance(payload, Mapping) and selected_check_passed(payload, args.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())
