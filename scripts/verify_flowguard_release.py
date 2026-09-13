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
    ReleaseTarget,
    save_release_verification_receipt,
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
    parser.add_argument(
        "--target",
        required=True,
        help="Explicit target descriptor JSON. Required for target-neutral external releases.",
    )
    parser.add_argument(
        "--candidate-receipt",
        help="Immutable local-candidate receipt consumed by tag/published phases.",
    )
    parser.add_argument(
        "--output",
        help="Write the immutable verification receipt JSON to this path.",
    )
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
    target = ReleaseTarget.from_json(args.target)
    if args.phase in {RELEASE_PHASE_TAG, RELEASE_PHASE_PUBLISHED} and not args.candidate_receipt:
        raise SystemExit("--candidate-receipt is required for target-neutral tag/published verification")
    common["target"] = target
    if args.candidate_receipt:
        common["candidate_receipt"] = args.candidate_receipt
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
    if args.output:
        save_release_verification_receipt(receipt, args.output)
    print(
        json.dumps(receipt.to_dict(), indent=2, ensure_ascii=True)
        if args.json
        else receipt.format_text()
    )
    return 0 if receipt.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
