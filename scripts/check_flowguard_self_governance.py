"""Check receipt-bound governance for all seventeen FlowGuard skills."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.skill_self_governance import (  # noqa: E402
    load_verification_contexts,
    run_skill_self_governance,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="FlowGuard repository root")
    parser.add_argument(
        "--contexts",
        help="JSON manifest of independently observed ReceiptVerificationContext values",
    )
    parser.add_argument("--output-directory", help="Explicit environment-local evidence directory")
    parser.add_argument("--json", action="store_true", help="Print the full canonical JSON report")
    parser.add_argument(
        "--no-save-parent-receipt",
        action="store_true",
        help="Do not save an eligible parent receipt after exact full closure",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    contexts = load_verification_contexts(args.contexts) if args.contexts else {}
    report = run_skill_self_governance(
        args.root,
        verification_contexts=contexts,
        output_directory=args.output_directory,
        save_parent_receipt=not args.no_save_parent_receipt,
    )
    print(report.to_json_text() if args.json else report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
