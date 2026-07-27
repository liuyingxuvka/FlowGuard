"""Check representative FlowGuard first-read prompt bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.prompt_budget import review_prompt_bundles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = review_prompt_bundles(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"bundles: {report['bundle_count']}")
        for route_id in report["failed_route_ids"]:
            print(f"blocked: {route_id}")
        print(f"claim_boundary: {report['claim_boundary']}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
