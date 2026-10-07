"""Produce the composed self-maintenance child of one full validation owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.blueprint_compact_projection import BlueprintCompactProjection
from flowguard.self_architecture_reduction import (
    build_flowguard_self_architecture_reduction_review,
)
from flowguard.self_blueprint import FlowGuardSelfBlueprintError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--model-receipt-dir")
    parser.add_argument("--require-executed-evidence", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        bundle, review = build_flowguard_self_architecture_reduction_review(
            args.root,
            require_executed_evidence=args.require_executed_evidence,
            model_receipt_dir=args.model_receipt_dir,
        )
        payload = BlueprintCompactProjection.self_qualification(bundle)
        payload["composed_self_maintenance_review"] = True
        payload["architecture_reduction_review"] = BlueprintCompactProjection.reduction(review)
        payload["composed_claim_boundary"] = (
            "Both bounded reviews consume one exact in-memory self-blueprint; "
            "no cache or target-system artifact is written."
        )
        code = 0 if bundle.ok and review.ok else 1
    except (FlowGuardSelfBlueprintError, OSError, ValueError) as exc:
        payload = {
            "ok": False,
            "status": "invalid",
            "findings": [{
                "code": "flowguard_self_blueprint_invalid",
                "message": str(exc),
                "member_ids": [],
                "severity": "blocked",
            }],
        }
        code = 2
    # The private producer always emits its machine-readable compact result.
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
