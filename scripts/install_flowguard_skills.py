"""Install, audit, uninstall, or compare the complete FlowGuard skill suite."""

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
    ]
    if "copied_files" in payload:
        lines.extend(
            [
                f"copied: {len(payload.get('copied_files', ())) }",
                f"removed: {len(payload.get('removed_files', ())) }",
                f"adopted: {len(payload.get('adopted_files', ())) }",
                f"conflicts: {len(payload.get('conflict_files', ())) }",
                f"extras: {len(payload.get('extra_files', ())) }",
                f"explicit_exclusions: {len(payload.get('excluded_files', ())) }",
            ]
        )
    else:
        lines.append(f"configured_trees: {len(payload.get('inventories', {}))}")
    for finding in payload.get("findings", ())[:10]:
        lines.append(f"- {finding.get('code')}: {finding.get('relative_path') or finding.get('message')}")
    lines.append(f"claim_boundary: {payload.get('claim_boundary', '')}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "check", "uninstall", "parity"))
    parser.add_argument("--source", default=".", help="FlowGuard repository root or .agents/skills root")
    parser.add_argument("--target", default=None, help="Explicit installed skills root")
    parser.add_argument("--codex-home", default=None, help="CODEX_HOME; the target is its skills directory")
    parser.add_argument("--formal", default=None, help="Optional formal-repository skill tree for parity")
    parser.add_argument("--shadow", default=None, help="Optional shadow-workspace skill tree for parity")
    parser.add_argument("--installed", default=None, help="Optional installed skill tree for parity")
    parser.add_argument("--dry-run", action="store_true", help="Plan install or uninstall without writes")
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Explicitly replace existing canonical source-owned paths and establish installer ownership",
    )
    parser.add_argument("--json", action="store_true", help="Emit stable machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
        for name in ("formal", "shadow", "installed"):
            value = getattr(args, name)
            if value:
                roots[name] = value
        if len(roots) == 1:
            target = args.target
            if target is None and args.codex_home is not None:
                target = str(Path(args.codex_home).expanduser() / "skills")
            if target is None:
                raise SystemExit("parity requires a configured --formal, --shadow, --installed, --target, or --codex-home")
            roots["installed"] = target
        parity = compare_configured_skill_trees(roots)
        payload = parity.to_dict()
        payload["action"] = "parity"

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_format_report(payload))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
