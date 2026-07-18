"""Compile or check the package-owned FlowGuard consumer-suite authority."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import tomllib
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.distribution_sync import (
    CONSUMER_SUITE_AUTHORITY_MANIFEST,
    build_consumer_suite_authority_bytes,
)
from flowguard.skill_suite import validate_skill_suite


def _project_version(root: Path) -> str:
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(payload.get("project", {}).get("version", "")).strip()
    if not version:
        raise ValueError("pyproject.toml does not declare project.version")
    return version


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="compile the deterministic packaged FlowGuard consumer authority"
    )
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write current authority")
    mode.add_argument("--check", action="store_true", help="fail when authority is stale")
    parser.add_argument("--json", action="store_true", help="print canonical JSON status")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    output = root / "flowguard" / CONSUMER_SUITE_AUTHORITY_MANIFEST
    try:
        suite = validate_skill_suite(root)
        if not suite.ok:
            raise ValueError(
                "author suite validation is blocked: "
                + ", ".join(finding.code for finding in suite.findings)
            )
        content = build_consumer_suite_authority_bytes(
            root,
            member_ids=suite.declared_member_ids,
            flowguard_version=_project_version(root),
        )
        current = output.read_bytes() if output.is_file() else None
        changed = current != content
        if args.write and changed:
            _write_atomic(output, content)
        ok = args.write or not changed
        result = {
            "artifact_type": "flowguard_consumer_suite_authority_compile",
            "ok": ok,
            "status": "pass" if ok else "blocked",
            "mode": "write" if args.write else "check",
            "root": str(root),
            "output": str(output),
            "changed": changed,
            "member_ids": list(suite.declared_member_ids),
            "member_count": len(suite.declared_member_ids),
            "error": "",
        }
    except (OSError, TypeError, ValueError) as exc:
        result = {
            "artifact_type": "flowguard_consumer_suite_authority_compile",
            "ok": False,
            "status": "blocked",
            "mode": "write" if args.write else "check",
            "root": str(root),
            "output": str(output),
            "changed": False,
            "member_ids": [],
            "member_count": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {result['status']}")
        print(f"mode: {result['mode']}")
        print(f"output: {result['output']}")
        print(f"changed: {str(result['changed']).lower()}")
        if result["error"]:
            print(f"error: {result['error']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
