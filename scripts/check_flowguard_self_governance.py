"""Verify current receipt-bound governance of the registered FlowGuard member."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.skill_self_governance import (  # noqa: E402
    run_skill_self_governance,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="FlowGuard repository root")
    parser.add_argument("--output-directory", required=True, help="Exact canonical model receipt store")
    parser.add_argument("--output-dir", required=True, help="Retained full run child artifact directory")
    parser.add_argument("--completion-run-manifest", required=True)
    parser.add_argument("--model-receipt-dir", required=True)
    parser.add_argument("--validation-receipt-dir", required=True)
    parser.add_argument("--json", action="store_true", help="Print the full canonical JSON report")
    parser.add_argument(
        "--no-save-parent-receipt",
        action="store_true",
        help="Do not save an eligible parent receipt after exact full closure",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_skill_self_governance(
        args.root,
        output_directory=args.output_directory,
        save_parent_receipt=not args.no_save_parent_receipt,
        completion_run_manifest=args.completion_run_manifest,
        model_receipt_dir=args.model_receipt_dir,
        owner_plan_path=Path(args.output_dir).resolve().parent / "owner-plan.json",
        validation_receipt_dir=args.validation_receipt_dir,
    )
    print(report.to_json_text() if args.json else report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
