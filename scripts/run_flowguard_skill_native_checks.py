"""Verify current model-owned native evidence without executing model checks."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from flowguard.skill_native_checks import run_native_skill_check


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--member", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--completion-run-manifest", required=True)
    parser.add_argument("--model-receipt-dir", required=True)
    parser.add_argument("--validation-receipt-dir", required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    selected = tuple(args.member) if args.member else ("flowguard",)
    if selected != ("flowguard",):
        payload = {"status": "invalid_input", "ok": False,
                   "blockers": ["exact_registered_native_member_required"], "results": []}
        code = 2
    else:
        try:
            result = run_native_skill_check(args.root, "flowguard",
                output_directory=args.model_receipt_dir,
                completion_run_manifest=args.completion_run_manifest,
                model_receipt_dir=args.model_receipt_dir,
                owner_plan_path=Path(args.output_dir).resolve().parent / "owner-plan.json",
                validation_receipt_dir=args.validation_receipt_dir)
            payload = {"artifact_type": "flowguard_skill_native_model_consumption",
                       "status": "pass", "ok": True, "results": [result.to_dict()],
                       "producer_invocations": 0, "blockers": []}
            code = 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            payload = {"artifact_type": "flowguard_skill_native_model_consumption",
                       "status": "blocked", "ok": False, "results": [],
                       "producer_invocations": 0, "blockers": [str(exc)]}
            code = 1
    print(json.dumps(payload, sort_keys=True, indent=2) if args.json
          else "status: " + payload["status"])
    return code

if __name__ == "__main__":
    raise SystemExit(main())
