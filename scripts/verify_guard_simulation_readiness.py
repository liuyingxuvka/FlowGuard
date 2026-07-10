"""Verify FlowGuard package, skill controls, and installed-skill readiness."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import shlex
import subprocess
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.skill_suite import FLOWGUARD_REQUIRED_MEMBER_FILES, SkillSuiteReport, validate_skill_suite


HOME_SKILLS = Path.home() / ".codex" / "skills"
def _project_version(root: Path) -> str:
    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("could not read project version")


def _display_path(path: Path, root: Path, installed_root: Path) -> str:
    resolved = path.resolve()
    try:
        return "$FLOWGUARD_ROOT/" + resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        pass
    try:
        return "$CODEX_HOME/skills/" + resolved.relative_to(installed_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _run(args: list[str], cwd: Path, *, root: Path, installed_root: Path) -> dict[str, object]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    return {
        "args": ["python", *args[1:]] if args and Path(args[0]).name.startswith("python") else args,
        "cwd": _display_path(cwd, root, installed_root),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _check_version(root: Path, installed_root: Path) -> dict[str, object]:
    module = importlib.import_module("flowguard")
    module_path = Path(module.__file__).resolve()
    metadata_version = importlib.metadata.version("flowguard")
    ok = metadata_version == _project_version(root) and module.SCHEMA_VERSION == "1.0" and root.resolve() in module_path.parents
    return {
        "check": "version_import_path",
        "ok": ok,
        "metadata_version": metadata_version,
        "project_version": _project_version(root),
        "schema_version": module.SCHEMA_VERSION,
        "module_path": _display_path(module_path, root, installed_root),
    }


def _skill_dirs(root: Path, report: SkillSuiteReport) -> tuple[Path, ...]:
    return tuple(root / ".agents" / "skills" / skill_id for skill_id in report.declared_member_ids)


def _check_skillguard(root: Path, installed_root: Path, report: SkillSuiteReport) -> dict[str, object]:
    runs: list[dict[str, object]] = []
    for skill_dir in _skill_dirs(root, report):
        manifest_path = skill_dir / ".skillguard" / "check_manifest.json"
        if not manifest_path.is_file():
            runs.append(
                {
                    "args": ["python", ".skillguard/check.py"],
                    "cwd": _display_path(skill_dir, root, installed_root),
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "required generated check manifest is missing",
                }
            )
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for declared in manifest.get("checks", []):
            command = shlex.split(str(declared.get("command") or ""), posix=False)
            if not command or Path(command[0]).name.lower() not in {"python", "python.exe"}:
                runs.append(
                    {
                        "check_id": declared.get("check_id"),
                        "args": command,
                        "cwd": _display_path(skill_dir, root, installed_root),
                        "exit_code": None,
                        "stdout": "",
                        "stderr": "generated check command is missing or does not use python",
                    }
                )
                continue
            run = _run([sys.executable, *command[1:]], skill_dir, root=root, installed_root=installed_root)
            run["check_id"] = declared.get("check_id")
            runs.append(run)
    return {
        "check": "source_skillguard",
        "ok": report.ok and all(run["exit_code"] == 0 for run in runs),
        "inventory_hash": report.inventory_hash,
        "member_ids": list(report.declared_member_ids),
        "inventory_findings": [finding.to_dict() for finding in report.findings],
        "runs": runs,
    }


def _check_installed_sync(root: Path, installed_root: Path, report: SkillSuiteReport) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for skill_id in report.declared_member_ids:
        source_skill = root / ".agents" / "skills" / skill_id
        installed_skill = installed_root / skill_id
        for relative in FLOWGUARD_REQUIRED_MEMBER_FILES:
            source = source_skill / relative
            installed = installed_skill / relative
            rows.append(
                {
                    "member_id": skill_id,
                    "relative_path": relative,
                    "source": _display_path(source, root, installed_root),
                    "installed": _display_path(installed, root, installed_root),
                    "ok": source.is_file() and installed.is_file() and _sha256(source) == _sha256(installed),
                }
            )
    return {
        "check": "installed_skill_sync",
        "ok": bool(rows) and all(row["ok"] for row in rows),
        "inventory_hash": report.inventory_hash,
        "member_ids": list(report.declared_member_ids),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="verify FlowGuard simulation readiness")
    parser.add_argument("--root", default=str(SCRIPT_ROOT), help="FlowGuard repository root")
    parser.add_argument("--installed-root", default=str(HOME_SKILLS), help="Installed Codex skills root")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    installed_root = Path(args.installed_root).resolve()
    suite_report = validate_skill_suite(root)
    checks = [
        _check_version(root, installed_root),
        {"check": "suite_inventory", **suite_report.to_dict()},
        _check_skillguard(root, installed_root, suite_report),
        _check_installed_sync(root, installed_root, suite_report),
    ]
    ok = all(bool(check["ok"]) for check in checks)
    payload = {
        "artifact_type": "flowguard_guard_simulation_readiness",
        "ok": ok,
        "status": "pass" if ok else "blocked",
        "inventory_hash": suite_report.inventory_hash,
        "member_ids": list(suite_report.declared_member_ids),
        "checks": checks,
        "claim_boundary": "Readiness requires current suite controls and installed-file parity; this command does not prove release publication or future AI behavior.",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("status: pass" if ok else "status: blocked")
        print(f"members: {len(suite_report.declared_member_ids)}")
        print(f"inventory_hash: {suite_report.inventory_hash}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
