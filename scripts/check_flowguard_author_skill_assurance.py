"""Run FlowGuard's author-side 15-member SkillGuard assurance owner.

This is an internal full-validation producer, not a fourth public execution
profile.  Routine ``check_flowguard_skill_suite --scope light`` intentionally
does not invoke it; the existing ``skill_suite_light`` full child uses this
entry to keep author qualification in one owner.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.check_flowguard_skill_suite import (  # noqa: E402
    _print_light,
    _write_light_result,
    run_author_skill_assurance,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument(
        "--skillguard",
        default="all",
        help="'all' for installed SkillGuard or an explicit skillguard.py path",
    )
    parser.add_argument("--output-dir", help="Author assurance artifact directory")
    parser.add_argument(
        "--authority-kind",
        choices=("standalone", "child"),
        default="standalone",
        help="Authority kind for the retained diagnostic artifact",
    )
    parser.add_argument(
        "--parent-scope",
        default="",
        help="Parent scope identity when this is a full-validation child",
    )
    parser.add_argument("--json", action="store_true", help="Print stable machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_author_skill_assurance(
        Path(args.root).expanduser().resolve(),
        skillguard=args.skillguard,
    )
    payload["scope"] = "author_assurance"
    if args.output_dir:
        run_id, result_path, result_sha256 = _write_light_result(
            payload,
            args.output_dir,
            authority_kind=args.authority_kind,
            parent_scope=args.parent_scope,
        )
    else:
        run_id = result_path = result_sha256 = ""
    _print_light(
        payload,
        as_json=args.json,
        run_id=run_id,
        result_path=result_path,
        result_sha256=result_sha256,
    )
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

