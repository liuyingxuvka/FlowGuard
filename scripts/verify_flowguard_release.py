"""Verify local or published FlowGuard release closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.release_verification import verify_local_release, verify_published_release


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--phase", choices=("local", "published"), required=True)
    parser.add_argument("--version")
    parser.add_argument("--tag", help="Expected v-prefixed tag; must agree with --version.")
    parser.add_argument("--evidence", help="Unified local release result.json.")
    parser.add_argument("--repository", help="Expected GitHub owner/repository for published verification.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    version = args.version
    if args.tag:
        tag_version = args.tag[1:] if args.tag.startswith("v") else args.tag
        if version and version != tag_version:
            raise SystemExit("--tag and --version disagree")
        version = tag_version
    if args.phase == "local":
        report = verify_local_release(args.root, version=version, evidence_path=args.evidence)
    else:
        report = verify_published_release(
            args.root,
            version=version,
            evidence_path=args.evidence,
            repository=args.repository,
        )
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=True) if args.json else report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
