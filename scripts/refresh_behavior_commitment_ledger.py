"""Refresh the stored behavior-ledger source identities for the current tree.

This command deliberately changes only content fingerprints, expanded member
paths, and the derived source-inventory identity. It never invents, removes,
or reclassifies a behavior commitment. The resulting ledger remains subject
to the native behavior-ledger check and its known-bad proofs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh current source identities in one FlowGuard behavior ledger"
    )
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument(
        "--ledger",
        default=".flowguard/behavior_commitment_ledger/ledger.json",
        help="ledger path relative to --root",
    )
    parser.add_argument("--write", action="store_true", help="write the refreshed ledger")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from flowguard import (  # noqa: PLC0415
        audit_behavior_commitment_source_inventory,
        load_behavior_commitment_ledger,
        refresh_behavior_commitment_source_inventory,
    )

    ledger_path = (root / args.ledger).resolve()
    ledger = load_behavior_commitment_ledger(ledger_path)
    audit = audit_behavior_commitment_source_inventory(ledger, root)
    if any(
        finding.code
        in {
            "source_surface_missing",
            "source_surface_unreadable",
            "source_surface_invalid_ref",
            "source_surface_glob_empty",
        }
        for finding in audit.findings
    ):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "ok": False,
                    "findings": [finding.to_dict() for finding in audit.findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    refreshed = refresh_behavior_commitment_source_inventory(ledger, root)
    payload = refreshed.to_dict()
    if args.write:
        ledger_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "status": "pass",
                "ok": True,
                "mode": "write" if args.write else "check",
                "ledger": ledger_path.as_posix(),
                "source_inventory_fingerprint": refreshed.source_inventory_fingerprint,
                "source_inventory_revision": refreshed.source_inventory_revision,
                "source_inventory_evidence_ids": list(
                    refreshed.source_inventory_evidence_ids
                ),
                "written": bool(args.write),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
