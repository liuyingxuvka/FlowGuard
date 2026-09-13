"""Run manifest-owned FlowGuard model regressions with bounded evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import types
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# The public ``flowguard`` package eagerly imports every route and helper so
# normal consumers get one complete API surface.  This manifest runner only
# needs the model-regression module and its relative dependencies; executing
# the public initializer here turns a bounded validation start into minutes of
# Windows file reads.  Install a package namespace with the same path, but no
# eager initializer, so the runner keeps source-relative imports and package
# identity while loading only the owned execution lane.
if "flowguard" not in sys.modules:
    _internal_package = types.ModuleType("flowguard")
    _internal_package.__path__ = [str(REPOSITORY_ROOT / "flowguard")]
    _internal_package.__package__ = "flowguard"
    sys.modules["flowguard"] = _internal_package

from flowguard.model_regressions import (
    ModelRegressionManifest,
    audit_manifest,
    resolve_current_full_model_regression_parent,
    run_manifest_regressions,
)


def _progress(payload: dict[str, object]) -> None:
    event = payload.get("event")
    model_id = payload.get("model_id")
    if event == "started":
        print(f"START {model_id} timeout={payload.get('timeout_seconds')}s", file=sys.stderr, flush=True)
    else:
        print(
            f"DONE  {model_id} status={payload.get('status')} seconds={payload.get('seconds')}",
            file=sys.stderr,
            flush=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--tier", choices=("fast", "focused", "full"), default="fast")
    parser.add_argument("--model", action="append", default=[], help="Exact id or glob; repeatable.")
    parser.add_argument("--shard", help="Stable shard in N/M form.")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=float, help="Override each child timeout in seconds.")
    parser.add_argument(
        "--model-parent-receipt",
        help=(
            "Exact current full-model parent artifact to verify read-only. "
            "When supplied, no model producer is launched and historical "
            "parent artifacts are never searched."
        ),
    )
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--receipt-dir",
        help=(
            "Content-addressed owner-receipt root for this execution. "
            "Use a fresh transaction directory when the default store "
            "contains a large historical backlog."
        ),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument(
        "--authority-kind",
        choices=("standalone", "child", "parent"),
        default="standalone",
        help=(
            "Authority kind for the retained terminal run. Full-suite model "
            "children use 'child'; standalone invocations keep the default."
        ),
    )
    parser.add_argument(
        "--parent-scope",
        default="",
        help="Normalized parent scope required when --authority-kind=child.",
    )
    parser.add_argument(
        "--require-executed-evidence",
        action="store_true",
        help=(
            "Require every native model runner to emit one explicit "
            "FLOWGUARD_EXECUTED_CASE_IDS JSON marker."
        ),
    )
    args = parser.parse_args(argv)

    try:
        manifest = ModelRegressionManifest.load(args.root)
        if args.audit_only:
            audit = audit_manifest(args.root, manifest)
            payload = {
                "schema_version": "flowguard.model_regression_audit.v1",
                **audit.to_dict(),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "\n".join(
                [f"status: {'pass' if audit.ok else 'blocked'}", f"registered: {len(audit.registered_model_ids)}"]
                + [f"error: {item}" for item in audit.errors]
            ))
            return 0 if audit.ok else 2
        if args.model_parent_receipt:
            if args.tier != "full" or args.model or args.shard:
                raise ValueError(
                    "--model-parent-receipt requires an unsharded full-tier selection"
                )
            current = resolve_current_full_model_regression_parent(
                args.root,
                receipt_dir=args.receipt_dir,
            )
            requested = Path(args.model_parent_receipt).expanduser().resolve()
            actual = Path(current.parent_artifact_path).resolve()
            root_path = Path(args.root).expanduser().resolve()
            if root_path not in requested.parents or requested.is_symlink():
                raise ValueError(
                    "--model-parent-receipt must be a non-symlink path inside --root"
                )
            if requested != actual:
                raise ValueError(
                    "--model-parent-receipt is not the typed current parent artifact: "
                    f"expected {actual}, got {requested}"
                )
            payload = {
                "schema_version": "flowguard.model_regression_parent_reuse.v1",
                "command": "flowguard-model-regressions",
                "status": "pass",
                "ok": True,
                "claim_scope": "full",
                "tier": "full",
                "parent_receipt_path": str(actual),
                "parent_receipt_fingerprint": current.parent_artifact_fingerprint,
                "selected_model_ids": [item.model_id for item in current.children],
                "executed_model_ids": [],
                "reused_model_ids": [item.model_id for item in current.children],
                "producer_invocations": 0,
                "native_producer_invocations": 0,
                "claim_boundary": (
                    "The exact typed current model parent and its child receipts "
                    "were independently verified; this invocation launched no "
                    "model producer."
                ),
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print("status: pass")
                print(f"parent_receipt_path: {actual}")
                print("producer_invocations: 0")
            return 0
        cancel = threading.Event()
        report = run_manifest_regressions(
            args.root,
            tier=args.tier,
            model_patterns=args.model,
            shard=args.shard,
            jobs=args.jobs,
            timeout=args.timeout,
            output_dir=args.output_dir,
            cancel_event=cancel,
            progress=None if args.json else _progress,
            receipt_dir=args.receipt_dir,
            require_executed_case_ids=args.require_executed_evidence,
            authority_kind=args.authority_kind,
            parent_scope=args.parent_scope,
        )
    except (ValueError, OSError) as exc:
        payload = {
            "schema_version": "flowguard.validation_result.v1",
            "command": "flowguard-model-regressions",
            "status": "invalid_input",
            "exit_code": 3,
            "message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"status: invalid_input\nerror: {exc}")
        return 3

    validation = report.to_validation_result()
    if args.json:
        result_path = Path(report.output_dir) / "report.json"
        result_sha256 = (
            "sha256:" + hashlib.sha256(result_path.read_bytes()).hexdigest()
            if result_path.is_file()
            else ""
        )
        print(
            validation.terminal_json_text(
                run_id=Path(report.output_dir).name,
                result_path=str(result_path),
                result_sha256=result_sha256,
            )
        )
    else:
        print(validation.format_text(full=args.full))
    return validation.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
