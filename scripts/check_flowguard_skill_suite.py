"""Read-only current-authority audit for the seventeen FlowGuard skills.

This command does not run FlowGuard native tests, compile contracts, aggregate
release checks, or issue receipts. SkillGuard owns those actions. FlowGuard
only exposes its suite membership and asks the one current SkillGuard runtime
to verify the already-generated current contract trio.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.skill_suite import FLOWGUARD_SKILL_ROOT, validate_skill_suite


def _skillguard_cli(value: str) -> Path:
    if value != "current":
        return Path(value).expanduser().resolve()
    return Path.home() / ".codex" / "skills" / "skillguard" / "scripts" / "skillguard.py"


def _run(command: Sequence[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            tuple(str(item) for item in command),
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"command": list(command), "exit_code": 2, "stdout": "", "stderr": str(exc), "payload": None}
    payload: Mapping[str, Any] | None = None
    if completed.stdout.strip():
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, Mapping):
            payload = dict(decoded)
    return {
        "command": list(command),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "payload": payload,
    }


def run_current_suite(
    root: Path,
    *,
    skillguard: str = "current",
    members: Sequence[str] = (),
) -> dict[str, Any]:
    inventory = validate_skill_suite(root)
    selected = tuple(members) if members else inventory.declared_member_ids
    cli = _skillguard_cli(skillguard)
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    if not cli.is_file():
        blockers.append(f"current SkillGuard CLI is missing: {cli}")
    else:
        for skill_id in selected:
            target = root / FLOWGUARD_SKILL_ROOT / skill_id
            commands = {
                "contract": (
                    sys.executable,
                    str(cli),
                    "check-contract",
                    "--target",
                    str(target),
                    "--target-root",
                    str(root),
                    "--output",
                    "-",
                ),
            }
            results = {name: _run(command, root) for name, command in commands.items()}
            inventory_member = next((item for item in inventory.members if item.skill_id == skill_id), None)
            static_ok = bool(inventory_member and inventory_member.ok)
            contract_ok = results["contract"]["exit_code"] == 0 and (results["contract"]["payload"] or {}).get("decision") == "pass"
            rows.append(
                {
                    "skill_id": skill_id,
                    "ok": static_ok and contract_ok,
                    "static_ok": static_ok,
                    "contract_ok": contract_ok,
                    "results": results,
                }
            )

    ok = inventory.ok and not blockers and len(rows) == len(selected) and all(row["ok"] for row in rows)
    return {
        "artifact_type": "flowguard_skill_suite_current_authority_audit",
        "status": "pass" if ok else "blocked",
        "ok": ok,
        "inventory_hash": inventory.inventory_hash,
        "semantic_hash": inventory.semantic_hash,
        "requested_members": list(selected),
        "passed_members": sum(bool(row["ok"]) for row in rows),
        "total_members": len(selected),
        "inventory": inventory.to_dict(),
        "members": rows,
        "blockers": blockers,
        "skipped_checks": [],
        "claim_boundary": (
            "This is a read-only suite/current-contract audit. It executes no native or depth test, issues no receipt, "
            "and does not replace SkillGuard TestMesh or release evidence."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="FlowGuard repository root")
    parser.add_argument("--skill", action="append", default=[], help="Audit one declared member; repeatable")
    parser.add_argument(
        "--skillguard",
        default="current",
        help="Explicit current SkillGuard CLI path, or 'current' for the installed authority",
    )
    parser.add_argument("--json", action="store_true", help="Emit stable machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_current_suite(
        Path(args.root).expanduser().resolve(),
        skillguard=args.skillguard,
        members=tuple(args.skill),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(f"members: {payload['passed_members']}/{payload['total_members']}")
        for blocker in payload["blockers"]:
            print(f"blocker: {blocker}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
