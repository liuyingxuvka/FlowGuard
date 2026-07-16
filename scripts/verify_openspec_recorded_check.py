"""Verify one current check receipt from a completed OpenSpec full run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def verify_recorded_check(
    payload: Mapping[str, Any],
    check_id: str,
    *,
    root: Path,
) -> tuple[bool, str]:
    issues = payload.get("issues", ())
    if not isinstance(issues, list) or any(
        _mapping(issue) and issue.get("level") == "blocking" for issue in issues
    ):
        return False, "blocking_or_invalid_issues"
    run = _mapping(payload.get("run"))
    if (
        payload.get("status") != "pass"
        or not run
        or run.get("state") != "completed"
        or run.get("validation_mode") != "full"
    ):
        return False, "full_run_not_complete"
    selection = _mapping(run.get("selection"))
    selected_ids = selection.get("check_ids", ()) if selection else ()
    if not isinstance(selected_ids, list) or check_id not in selected_ids:
        return False, "check_not_selected"

    checks = payload.get("checks", ())
    if not isinstance(checks, list):
        return False, "checks_invalid"
    selected = [item for item in checks if _mapping(item) and item.get("id") == check_id]
    if len(selected) != 1:
        return False, "check_identity_not_unique"
    check = selected[0]
    receipt_id = check.get("receipt_id")
    if (
        check.get("status") != "passed"
        or check.get("accounting") not in {"executed", "reused", "aggregated"}
        or not isinstance(receipt_id, str)
        or not receipt_id
    ):
        return False, "check_not_current_pass"

    receipts = payload.get("receipts", ())
    if not isinstance(receipts, list):
        return False, "receipts_invalid"
    matches = [item for item in receipts if _mapping(item) and item.get("id") == receipt_id]
    if len(matches) != 1:
        return False, "receipt_identity_not_unique"
    receipt = matches[0]
    for field, check_field in (
        ("check_id", "id"),
        ("execution_key", "execution_key"),
        ("result_hash", "result_hash"),
    ):
        if receipt.get(field) != check.get(check_field):
            return False, f"receipt_{field}_mismatch"

    content_path = receipt.get("content_path")
    if not isinstance(content_path, str) or not content_path:
        return False, "receipt_content_path_missing"
    sidecar_path = (root / content_path).resolve()
    try:
        sidecar_path.relative_to(root.resolve())
    except ValueError:
        return False, "receipt_content_path_external"
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "receipt_sidecar_unreadable"
    sidecar_result = _mapping(sidecar.get("result")) if _mapping(sidecar) else None
    if (
        not sidecar_result
        or sidecar.get("receipt_id") != receipt_id
        or sidecar.get("execution_key") != check.get("execution_key")
        or sidecar.get("result_hash") != check.get("result_hash")
        or sidecar_result.get("status") != "passed"
    ):
        return False, "receipt_sidecar_mismatch"
    return True, "current_pass_receipt_verified"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", required=True)
    parser.add_argument("--check", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    report = (root / args.report).resolve()
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    ok, reason = verify_recorded_check(payload, args.check, root=root)
    print(json.dumps({"check_id": args.check, "ok": ok, "reason": reason}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
