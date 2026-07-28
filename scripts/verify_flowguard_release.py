"""Verify FlowGuard local-candidate, tag, or published release receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.release_verification import (
    RELEASE_PHASE_LOCAL_CANDIDATE,
    RELEASE_PHASE_PUBLISHED,
    RELEASE_PHASE_TAG,
    RELEASE_PHASES,
    verify_local_candidate,
    verify_published_release,
    verify_tagged_release,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--phase", choices=RELEASE_PHASES, required=True)
    parser.add_argument("--version")
    parser.add_argument("--tag", help="Expected v-prefixed tag; must agree with --version.")
    parser.add_argument(
        "--parent-receipt",
        required=True,
        help="Exact validation-parent receipt id or canonical receipt JSON path.",
    )
    parser.add_argument(
        "--receipt-root",
        help="Validation-owner receipt root; defaults to .flowguard/evidence/validation-owners.",
    )
    parser.add_argument("--repository", help="Expected GitHub owner/repository for published verification.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    version = args.version
    if args.tag:
        if not args.tag.startswith("v") or len(args.tag) == 1:
            raise SystemExit("--tag must use the v-prefixed release form")
        tag_version = args.tag[1:]
        if version and version != tag_version:
            raise SystemExit("--tag and --version disagree")
        version = tag_version
    root = Path(args.root).resolve()
    receipt_root = (
        Path(args.receipt_root).expanduser().resolve()
        if args.receipt_root
        else root / ".flowguard" / "evidence" / "validation-owners"
    )
    common = {
        "parent_receipt": args.parent_receipt,
        "receipt_root": receipt_root,
        "version": version,
    }
    if args.phase == RELEASE_PHASE_LOCAL_CANDIDATE:
        receipt = verify_local_candidate(root, **common)
    elif args.phase == RELEASE_PHASE_TAG:
        receipt = verify_tagged_release(root, **common)
    elif args.phase == RELEASE_PHASE_PUBLISHED:
        receipt = verify_published_release(
            root,
            **common,
            repository=args.repository,
        )
    else:  # argparse owns the finite phase set.
        raise AssertionError(f"unhandled release phase: {args.phase}")
    print(
        json.dumps(receipt.to_dict(), indent=2, ensure_ascii=True)
        if args.json
        else receipt.format_text()
    )
    return 0 if receipt.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
