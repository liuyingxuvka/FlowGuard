"""Produce a fail-closed gap report for FlowGuard's public behavior surface.

This command consumes the explicit native behavior manifest and explicit
production declarations only.  It never scans tests or models and never turns
API or CLI names into semantic BehaviorInventory rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from flowguard.behavior_surface_audit import (
    IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
    audit_implementation_behavior_surface,
    build_public_behavior_surface_gap_report,
    compact_implementation_behavior_surface_audit,
    discover_implementation_behavior_surfaces,
)

try:
    # Tests import ``scripts`` as a namespace package from the repository root.
    from scripts.discover_behavior_inventory import (  # type: ignore[import-not-found]
        BehaviorDiscoveryError,
        load_discovery_manifest,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - direct script launch
    if not (exc.name or "").startswith("scripts"):
        raise
    from discover_behavior_inventory import BehaviorDiscoveryError, load_discovery_manifest


def _blocked_manifest(message: str) -> dict[str, Any]:
    return {
        "schema_version": "flowguard.native_behavior_discovery.v1",
        "status": "blocked",
        "claim_boundary": "manifest validation only",
        "findings": [{"code": "behavior_discovery_manifest_invalid", "message": message}],
    }


def _evidence_fingerprint(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("evidence_fingerprint", None)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _compact_public_report(
    result: dict[str, Any],
    *,
    output: Path,
    discovery: dict[str, Any] | None,
    surface_map: Path | None,
    surface_discovery: Path | None,
) -> dict[str, Any]:
    """Return a bounded terminal projection while retaining the full artifact."""

    compact: dict[str, Any] = {
        "schema_version": "flowguard.public_behavior_surface_gap_compact.v1",
        "claim_boundary": (
            "Bounded terminal projection only. The --output JSON artifact is "
            "the sole full current report authority."
        ),
        "artifact_ref": str(output.resolve()),
        "status": result.get("status"),
        "complete_public_surface_claim_licensed": bool(
            result.get("complete_public_surface_claim_licensed")
        ),
        "evidence_fingerprint": result.get("evidence_fingerprint", ""),
        "finding_count": len(result.get("findings", ()))
        if isinstance(result.get("findings"), list)
        else 0,
        "finding_code_counts": {},
    }
    finding_counts: dict[str, int] = {}
    for row in result.get("findings", ()) if isinstance(result.get("findings"), list) else ():
        if isinstance(row, dict):
            code = str(row.get("code", "")).strip() or "<missing>"
            finding_counts[code] = finding_counts.get(code, 0) + 1
    compact["finding_code_counts"] = dict(sorted(finding_counts.items()))
    if discovery is not None and isinstance(result.get("implementation_surface_audit"), dict):
        compact["implementation_surface_audit"] = (
            compact_implementation_behavior_surface_audit(
                discovery,
                result["implementation_surface_audit"],
                discovery_artifact=str(surface_discovery.resolve())
                if surface_discovery is not None
                else "",
                surface_map_artifact=str(surface_map.resolve())
                if surface_map is not None
                else "",
                full_artifact=str(output.resolve()),
            )
        )
    return compact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--authority-status",
        choices=("passed", "blocked", "stale", "not_run", "not_provided"),
        default="not_provided",
    )
    parser.add_argument(
        "--authority-reason",
        default="Attach a current selected-model read result before a broad current claim.",
    )
    parser.add_argument(
        "--surface-map",
        type=Path,
        default=None,
        help="Independently authored reverse implementation->intent/model/test map.",
    )
    parser.add_argument(
        "--surface-discovery",
        type=Path,
        default=None,
        help=(
            "Current merged source-only implementation-surface discovery JSON. "
            "Use the shard protocol when the root exceeds 5,000 rows."
        ),
    )
    parser.add_argument(
        "--full-output",
        action="store_true",
        help=(
            "Print the complete report in addition to writing --output. "
            "Default terminal output is a bounded summary."
        ),
    )
    parser.add_argument(
        "--reverse-profile",
        choices=("light", "full"),
        default="light",
        help=(
            "Currentness profile for the optional reverse audit. light reuses "
            "unchanged source pointers; full rereads every source file."
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        manifest_evidence = load_discovery_manifest(args.manifest, root=root)
    except (BehaviorDiscoveryError, ValueError, OSError) as exc:
        manifest_evidence = _blocked_manifest(str(exc))
    result = build_public_behavior_surface_gap_report(
        root=root,
        manifest_evidence=manifest_evidence,
        manifest_path=args.manifest,
        authority_status=args.authority_status,
        authority_reason=args.authority_reason,
    )
    # The declaration gap report remains backward-compatible and deliberately
    # does not turn declaration names into behavior rows.  When an explicit
    # reverse map is supplied, attach a second, production-source denominator
    # that checks every observed code/UI/CLI/config/effect/error/recovery/
    # placeholder surface back to intent, model owner, and test evidence.  A
    # supplied source observation is itself an explicit request for the
    # reverse direction.  Do not silently omit that audit merely because the
    # independently authored map is not available: the missing map must be
    # reported as a fail-closed blocker with the discovered denominator.
    if args.surface_map is not None or args.surface_discovery is not None:
        if args.surface_discovery is None:
            discovery = discover_implementation_behavior_surfaces(root)
        else:
            try:
                loaded_discovery = json.loads(
                    args.surface_discovery.read_text(encoding="utf-8")
                )
                if not isinstance(loaded_discovery, dict):
                    raise ValueError("surface discovery artifact must be an object")
                discovery = loaded_discovery
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                discovery = {
                    "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
                    "status": "blocked",
                    "surfaces": [],
                    "findings": [
                        {
                            "code": "implementation_surface_discovery_invalid",
                            "severity": "blocker",
                            "message": str(exc),
                        }
                    ],
                    "discovery_fingerprint": "",
                }
        result["implementation_surface_audit"] = audit_implementation_behavior_surface(
            root,
            args.surface_map,
            discovery=discovery,
            currentness_profile=args.reverse_profile,
        )
        if result["implementation_surface_audit"]["status"] != "passed":
            result["status"] = "blocked"
            result["complete_public_surface_claim_licensed"] = False
        result["evidence_fingerprint"] = _evidence_fingerprint(result)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    if args.full_output:
        print(payload, end="")
    else:
        print(
            json.dumps(
                _compact_public_report(
                    result,
                    output=args.output,
                    discovery=discovery
                    if isinstance(result.get("implementation_surface_audit"), dict)
                    else None,
                    surface_map=args.surface_map,
                    surface_discovery=args.surface_discovery,
                ),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
