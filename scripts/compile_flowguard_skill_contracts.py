"""Compile or check all FlowGuard target-specific SkillGuard contracts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.skill_contracts import compile_skill_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="compile FlowGuard skill contracts")
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Write deterministic generated artifacts")
    mode.add_argument("--check", action="store_true", help="Fail when generated artifacts are missing or stale")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    report = compile_skill_suite(args.root, write=args.write)
    if args.json:
        print(report.to_json_text())
    else:
        print("status: pass" if report.ok else "status: blocked")
        print(f"members: {len(report.member_ids)}")
        print(f"written_files: {len(report.written_files)}")
        for finding in report.findings:
            print(f"finding: {finding.code}: {finding.skill_id}: {finding.message}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
