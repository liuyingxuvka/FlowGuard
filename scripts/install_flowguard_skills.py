"""Install, author-sync, audit, uninstall, or compare the FlowGuard skill suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.distribution_sync import (
    PARITY_ROLE_AUTHOR_SOURCE,
    PARITY_ROLE_CONSUMER_DISTRIBUTION,
    author_sync_skill_suite,
    check_skill_suite,
    compare_configured_skill_trees,
    install_skill_suite,
    uninstall_skill_suite,
)


def _format_report(payload: dict[str, Any]) -> str:
    lines = [
        "=== FlowGuard skill distribution ===",
        f"action: {payload.get('action', 'parity')}",
        f"status: {payload.get('status', 'pass' if payload.get('ok') else 'blocked')}",
        f"target: {payload.get('target') or payload.get('source') or 'configured-trees'}",
    ]
    if "copied_files" in payload:
        changed = {
            *payload.get("copied_files", ()),
            *payload.get("removed_files", ()),
            *payload.get("adopted_files", ()),
            *payload.get("conflict_files", ()),
            *payload.get("extra_files", ()),
        }
        lines.extend(
            [
                f"members: {len(payload.get('authority_member_ids', ())) }",
                f"changed_files: {len(changed)}",
                f"copied: {len(payload.get('copied_files', ())) }",
                f"removed: {len(payload.get('removed_files', ())) }",
                f"adopted: {len(payload.get('adopted_files', ())) }",
                f"conflicts: {len(payload.get('conflict_files', ())) }",
                f"extras: {len(payload.get('extra_files', ())) }",
                f"explicit_exclusions: {len(payload.get('excluded_files', ())) }",
            ]
        )
        if payload.get("projection_role"):
            lines.append(
                "projection_role: "
                f"{payload.get('previous_projection_role') or 'none'} -> "
                f"{payload.get('projection_role')}"
            )
        if payload.get("transaction_status"):
            lines.append(f"transaction: {payload.get('transaction_status')}")
        if payload.get("preserved_paths"):
            lines.append(
                f"preserved_co_located_paths: {len(payload.get('preserved_paths', ()))}"
            )
    else:
        lines.append(f"configured_trees: {len(payload.get('inventories', {}))}")
    for finding in payload.get("findings", ())[:10]:
        lines.append(f"- {finding.get('code')}: {finding.get('relative_path') or finding.get('message')}")
    lines.append(f"claim_boundary: {payload.get('claim_boundary', '')}")
    return "\n".join(lines)


def _summary_payload(payload: dict[str, Any], *, full_report_path: str = "") -> dict[str, Any]:
    findings = list(payload.get("findings", ()))
    conflicts = list(payload.get("conflict_files", ()))
    extras = list(payload.get("extra_files", ()))
    issues = [
        {
            "source": "findings",
            "index": index,
            "code": str(item.get("code", "")),
            "message": str(item.get("message", "")),
            "relative_path": str(item.get("relative_path", "")),
        }
        for index, item in enumerate(findings)
        if isinstance(item, dict)
    ]
    issues.extend(
        {"source": "conflict_files", "index": index, "relative_path": str(item)}
        for index, item in enumerate(conflicts)
    )
    issues.extend(
        {"source": "extra_files", "index": index, "relative_path": str(item)}
        for index, item in enumerate(extras)
    )
    changed = {
        *payload.get("copied_files", ()),
        *payload.get("removed_files", ()),
        *payload.get("adopted_files", ()),
        *payload.get("conflict_files", ()),
        *payload.get("extra_files", ()),
    }
    return {
        "schema_version": "flowguard.skill_distribution_summary.v1",
        "source_schema_version": str(payload.get("schema_version", "")),
        "artifact_type": "flowguard_skill_distribution_summary",
        "action": payload.get("action", "parity"),
        "status": payload.get("status", "pass" if payload.get("ok") else "blocked"),
        "ok": bool(payload.get("ok", False)),
        "target": payload.get("target") or payload.get("source") or "configured-trees",
        "member_count": len(payload.get("authority_member_ids", ())),
        "changed_files_count": len(changed),
        "counts": {
            "copied": len(payload.get("copied_files", ())),
            "removed": len(payload.get("removed_files", ())),
            "adopted": len(payload.get("adopted_files", ())),
            "conflicts": len(conflicts),
            "extras": len(extras),
            "excluded": len(payload.get("excluded_files", ())),
            "configured_trees": len(payload.get("inventories", {})),
        },
        "dry_run": bool(payload.get("dry_run", False)),
        "projection_role": payload.get("projection_role", ""),
        "transaction_status": payload.get("transaction_status", ""),
        "copied_files": list(payload.get("copied_files", ()))[:10],
        "removed_files": list(payload.get("removed_files", ()))[:10],
        "adopted_files": list(payload.get("adopted_files", ()))[:10],
        "conflict_files": list(payload.get("conflict_files", ()))[:10],
        "extra_files": list(payload.get("extra_files", ()))[:10],
        "inventories": {
            str(name): {
                "member_count": int(value.get("member_count", 0)) if isinstance(value, dict) else 0,
                "file_count": len(value.get("files", ())) if isinstance(value, dict) and isinstance(value.get("files"), list) else 0,
            }
            for name, value in (payload.get("inventories", {}) or {}).items()
        }
        if isinstance(payload.get("inventories"), dict)
        else {},
        "issues": issues[:10],
        "truncated_count": max(0, len(issues) - min(10, len(issues))),
        "claim_boundary": payload.get("claim_boundary", ""),
        "full_report_path": full_report_path,
        "full_report_hint": "Use --full-output --output <path> to save the complete machine report." if not full_report_path else "",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("install", "author-sync", "check", "uninstall", "parity"),
    )
    parser.add_argument("--source", default=".", help="FlowGuard repository root or .agents/skills root")
    parser.add_argument(
        "--target",
        default=None,
        help="Explicit installed skills root or author-sync shadow skill root",
    )
    parser.add_argument("--codex-home", default=None, help="CODEX_HOME; the target is its skills directory")
    parser.add_argument("--formal", default=None, help="Optional formal-repository skill tree for parity")
    parser.add_argument("--shadow", default=None, help="Optional shadow-workspace skill tree for parity")
    parser.add_argument("--installed", default=None, help="Optional installed skill tree for parity")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan install, author-sync, or uninstall without writes",
    )
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Explicitly replace existing canonical source-owned paths and establish installer ownership",
    )
    parser.add_argument("--json", action="store_true", help="Emit stable machine-readable JSON")
    parser.add_argument("--output", help="Write the complete machine report to this file.")
    parser.add_argument(
        "--full-output",
        action="store_true",
        help="Require --output for the complete machine report; stdout remains a bounded summary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.full_output and not args.output:
        raise SystemExit("--full-output requires --output PATH")
    if args.adopt_existing and args.action != "install":
        raise SystemExit("--adopt-existing is valid only for the install action")
    if args.action == "install":
        report = install_skill_suite(
            args.source,
            args.target,
            codex_home=args.codex_home,
            dry_run=args.dry_run,
            adopt_existing=args.adopt_existing,
        )
        payload = report.to_dict()
    elif args.action == "author-sync":
        if args.codex_home is not None:
            raise SystemExit(
                "author-sync requires an explicit shadow --target and never uses --codex-home"
            )
        if args.target is None:
            raise SystemExit("author-sync requires an explicit shadow skill-root --target")
        report = author_sync_skill_suite(
            args.source,
            args.target,
            dry_run=args.dry_run,
        )
        payload = report.to_dict()
    elif args.action == "check":
        if args.dry_run:
            raise SystemExit("--dry-run is unnecessary for the read-only check action")
        report = check_skill_suite(args.source, args.target, codex_home=args.codex_home)
        payload = report.to_dict()
    elif args.action == "uninstall":
        report = uninstall_skill_suite(args.target, codex_home=args.codex_home, dry_run=args.dry_run)
        payload = report.to_dict()
    else:
        if args.dry_run:
            raise SystemExit("--dry-run is unnecessary for the read-only parity action")
        roots: dict[str, str] = {"source": args.source}
        root_roles: dict[str, str] = {"source": PARITY_ROLE_AUTHOR_SOURCE}
        for name in ("formal", "shadow", "installed"):
            value = getattr(args, name)
            if value:
                roots[name] = value
                root_roles[name] = (
                    PARITY_ROLE_CONSUMER_DISTRIBUTION
                    if name == "installed"
                    else PARITY_ROLE_AUTHOR_SOURCE
                )
        if len(roots) == 1:
            target = args.target
            if target is None and args.codex_home is not None:
                target = str(Path(args.codex_home).expanduser() / "skills")
            if target is None:
                raise SystemExit("parity requires a configured --formal, --shadow, --installed, --target, or --codex-home")
            roots["installed"] = target
            root_roles["installed"] = PARITY_ROLE_CONSUMER_DISTRIBUTION
        parity = compare_configured_skill_trees(roots, root_roles=root_roles)
        payload = parity.to_dict()
        payload["action"] = "parity"

    full_report_path = ""
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        full_report_path = str(output_path)
    if args.json:
        print(
            json.dumps(
                _summary_payload(payload, full_report_path=full_report_path),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(_format_report(payload))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
