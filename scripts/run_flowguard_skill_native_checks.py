"""Execute declared FlowGuard skill-native checks and emit child receipts."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.evidence_receipts import (  # noqa: E402
    RECEIPT_STATUS_PASS,
    list_evidence_receipts,
    verify_evidence_receipt,
)
from flowguard.skill_native_checks import (  # noqa: E402
    build_current_native_receipt_context,
    prepare_native_suite_context,
    run_native_skill_check,
)
from flowguard.skill_self_governance import load_governance_requirements  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="FlowGuard repository root")
    parser.add_argument("--member", action="append", default=[], help="Skill id; repeat to select members")
    parser.add_argument("--output-dir", help="Explicit environment-local evidence directory")
    parser.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="One total invocation budget in seconds; each child receives only its remaining time",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue ordinary failed owners for diagnostics; cancellation, interruption, and unconfirmed cleanup still stop",
    )
    parser.add_argument(
        "--check-private-inventories",
        action="store_true",
        help="Include the author-only private inventory scan once in the shared suite observation",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only exact-current terminal-pass member receipts and execute every missing or stale member.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable terminal report")
    return parser


def _current_receipt_row(
    root: Path,
    skill_id: str,
    output_directory: str | None,
    *,
    receipts: tuple[object, ...] | None = None,
    suite_inventory_hash: str | None = None,
) -> dict[str, object] | None:
    """Return one exact-current reusable receipt without rescanning the store.

    The native run contains many members, but the receipt store is shared.  A
    resume pass must snapshot that store once and filter the in-memory rows;
    scanning the full directory once per member both inflated the freshness
    window and could exhaust the parent validation timeout before all owners
    were reached.
    """

    receipts = sorted(
        (
            receipt
            for receipt in (
                receipts
                if receipts is not None
                else list_evidence_receipts(root, output_directory=output_directory)
            )
            if receipt.subject_id == skill_id
        ),
        key=lambda receipt: (receipt.finished_at, receipt.receipt_id),
        reverse=True,
    )
    for receipt in receipts:
        context = build_current_native_receipt_context(
            receipt,
            root,
            suite_inventory_hash=suite_inventory_hash,
        )
        if context is None:
            continue
        verification = verify_evidence_receipt(receipt, context)
        if (
            not verification.ok
            or receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.claim_scope != "full"
        ):
            continue
        return {
            "skill_id": skill_id,
            "ok": True,
            "status": RECEIPT_STATUS_PASS,
            "disposition": "reuse_current",
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.fingerprint,
            "proof_path_token": receipt.metadata.get("proof_artifact_path_token", ""),
            "log_path_token": receipt.metadata.get("log_path_token", ""),
            "runs": [],
            "blockers": [],
        }
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    invocation_deadline = time.monotonic() + max(0.0, float(args.timeout))
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
    receipt_rows = (
        tuple(
            list_evidence_receipts(
                root,
                output_directory=args.output_dir,
                subject_ids=selected,
            )
        )
        if args.resume
        else None
    )
    # The suite inventory is a shared current input.  Observe it once and pass
    # the invocation-bound context to each owner; a member never receives a
    # caller-supplied bare hash as authority.
    suite_context = (
        prepare_native_suite_context(
            root,
            selected,
            check_private_inventories=args.check_private_inventories,
        )
        if time.monotonic() < invocation_deadline
        else None
    )
    suite_inventory_hash = suite_context.inventory_hash if suite_context is not None else None
    for index, skill_id in enumerate(selected, start=1):
        if time.monotonic() >= invocation_deadline:
            results.extend(
                {
                    "skill_id": pending,
                    "ok": False,
                    "status": "blocked",
                    "disposition": "not_run",
                    "blockers": ["native_checks_not_run_due_to_budget"],
                }
                for pending in selected[index - 1 :]
            )
            break
        reused = (
            _current_receipt_row(
                root,
                skill_id,
                args.output_dir,
                receipts=receipt_rows,
                suite_inventory_hash=suite_inventory_hash,
            )
            if args.resume
            else None
        )
        if reused is not None:
            print(f"[{index}/{len(selected)}] native check: {skill_id} (reuse_current)", file=sys.stderr, flush=True)
            results.append(reused)
            continue
        print(f"[{index}/{len(selected)}] native check: {skill_id} (execute)", file=sys.stderr, flush=True)
        try:
            results.append(
                run_native_skill_check(
                    root,
                    skill_id,
                    output_directory=args.output_dir,
                    timeout_seconds=args.timeout,
                    deadline=invocation_deadline,
                    keep_going=args.keep_going,
                    suite_context=suite_context,
                )
            )
        except Exception as exc:  # terminal report must survive one producer failure
            results.append(exc)
            print(f"[{index}/{len(selected)}] producer error: {skill_id}: {exc}", file=sys.stderr, flush=True)

        latest = results[-1]
        if isinstance(latest, Exception):
            latest_ok = False
            hard_stop = True
        elif isinstance(latest, dict):
            latest_ok = bool(latest.get("ok"))
            hard_stop = not latest_ok
        else:
            latest_ok = latest.ok
            hard_stop = (
                not latest.runs
                or any(
                    item.cancelled
                    or item.interrupted
                    or not item.cleanup_confirmed
                    for item in latest.runs
                )
            )
        if not latest_ok and (hard_stop or not args.keep_going):
            reason = "terminal" if hard_stop else "failure"
            results.extend(
                {
                    "skill_id": pending,
                    "ok": False,
                    "status": "blocked",
                    "disposition": "not_run",
                    "blockers": [f"native_checks_not_run_after_previous_{reason}"],
                }
                for pending in selected[index:]
            )
            break

    rows = []
    for skill_id, result in zip(selected, results):
        if isinstance(result, Exception):
            rows.append({"skill_id": skill_id, "ok": False, "status": "internal_error", "error": str(result)})
        elif isinstance(result, dict):
            rows.append(result)
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
        "executed_members": sum(item.get("disposition", "execute") == "execute" for item in rows),
        "reused_members": sum(item.get("disposition") == "reuse_current" for item in rows),
        "results": rows,
        "claim_boundary": (
            "Child receipts prove only each declared owner-specific native binding and its current contract inputs; "
            "the parent self-governance command must independently reload and consume all fifteen."
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
