"""Execute declared FlowGuard skill-native checks and emit child receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.skill_native_checks import run_native_skill_check  # noqa: E402
from flowguard.skill_self_governance import load_governance_requirements  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="FlowGuard repository root")
    parser.add_argument("--member", action="append", default=[], help="Skill id; repeat to select members")
    parser.add_argument("--output-dir", help="Explicit environment-local evidence directory")
    parser.add_argument("--timeout", type=float, default=300.0, help="Per-native-command timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable terminal report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    canonical = tuple(item.subject_id for item in load_governance_requirements(root))
    selected = tuple(args.member) if args.member else canonical
    unknown = tuple(item for item in selected if item not in canonical)
    if unknown:
        payload = {
            "artifact_type": "flowguard_skill_native_check_run",
            "status": "invalid_input",
            "ok": False,
            "unknown_members": list(unknown),
            "results": [],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"invalid members: {', '.join(unknown)}")
        return 2

    results = []
    for index, skill_id in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] native check: {skill_id}", file=sys.stderr, flush=True)
        try:
            results.append(
                run_native_skill_check(
                    root,
                    skill_id,
                    output_directory=args.output_dir,
                    timeout_seconds=args.timeout,
                )
            )
        except Exception as exc:  # terminal report must survive one producer failure
            results.append(exc)
            print(f"[{index}/{len(selected)}] producer error: {skill_id}: {exc}", file=sys.stderr, flush=True)

    rows = []
    for skill_id, result in zip(selected, results):
        if isinstance(result, Exception):
            rows.append({"skill_id": skill_id, "ok": False, "status": "internal_error", "error": str(result)})
        else:
            rows.append(result.to_dict())
    ok = len(rows) == len(selected) and all(bool(item.get("ok")) for item in rows)
    payload = {
        "artifact_type": "flowguard_skill_native_check_run",
        "status": "pass" if ok else "fail",
        "ok": ok,
        "requested_members": list(selected),
        "passed_members": sum(bool(item.get("ok")) for item in rows),
        "total_members": len(selected),
        "results": rows,
        "claim_boundary": (
            "Child receipts prove only each declared owner-specific native binding and its current contract inputs; "
            "the parent self-governance command must independently reload and consume all seventeen."
        ),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(f"members: {payload['passed_members']}/{payload['total_members']}")
        for row in rows:
            if not row.get("ok"):
                print(f"finding: {row['skill_id']}: {row.get('status', 'fail')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
