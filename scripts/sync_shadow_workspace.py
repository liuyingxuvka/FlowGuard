"""Synchronize a FlowGuard checkout into a local shadow workspace.

The default mode is intentionally non-destructive: it copies current source
sets over matching paths but does not delete files that only exist in the
shadow workspace. This preserves parallel-agent work while still keeping the
FlowGuard source, OpenSpec artifacts, tests, scripts, docs, and committed model
authority aligned. Environment-local runtime evidence remains local.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from flowguard.distribution_sync import (
    FLOWGUARD_EXPECTED_MEMBER_COUNT,
    build_consumer_suite_authority_bytes,
    load_consumer_suite_authority,
)

DEFAULT_SOURCE_SETS = (
    ".agents",
    ".skillguard",
    ".github",
    ".flowguard",
    "assets",
    "docs",
    "examples",
    "flowguard",
    "openspec",
    "scripts",
    "tests",
    "AGENTS.md",
    "CHANGELOG.md",
    "README.md",
    "pyproject.toml",
)

SKIP_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "flowguard.egg-info",
    "htmlcov",
    "tmp",
}

LOCAL_ONLY_PREFIXES = (
    (".flowguard", "evidence"),
)


@dataclass(frozen=True)
class SyncResult:
    copied_files: tuple[str, ...]
    skipped_paths: tuple[str, ...]
    dry_run: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "copied_files": list(self.copied_files),
            "copied_count": len(self.copied_files),
            "skipped_paths": list(self.skipped_paths),
            "dry_run": self.dry_run,
        }


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _is_local_only(relative_path: Path) -> bool:
    parts = relative_path.parts
    return any(
        parts[: len(prefix)] == prefix
        for prefix in LOCAL_ONLY_PREFIXES
    )


def _iter_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        if not _should_skip(Path(path.name)):
            yield path
        return
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            relative_child = child.relative_to(path)
            if child.is_file() and not _should_skip(relative_child):
                yield child


def sync_workspace(
    source: str | Path,
    target: str | Path,
    *,
    source_sets: Sequence[str] = DEFAULT_SOURCE_SETS,
    dry_run: bool = False,
) -> SyncResult:
    source_root = Path(source).resolve()
    target_root = Path(target).resolve()
    if source_root == target_root:
        raise ValueError("source and target must be different directories")
    if not source_root.is_dir():
        raise FileNotFoundError(f"source root does not exist: {source_root}")
    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped: list[str] = []
    for item in source_sets:
        source_path = source_root / item
        if not source_path.exists():
            skipped.append(item)
            continue
        for file_path in _iter_files(source_path):
            rel_path = file_path.relative_to(source_root)
            if _is_local_only(rel_path):
                continue
            destination = target_root / rel_path
            copied.append(rel_path.as_posix())
            if dry_run:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, destination)
    return SyncResult(copied_files=tuple(copied), skipped_paths=tuple(skipped), dry_run=dry_run)


def _run_python(target: Path, code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )


def install_editable(target: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        cwd=Path(target).resolve(),
        text=True,
        capture_output=True,
        check=False,
    )


def verify_shadow_skill_projection(target: str | Path) -> dict[str, object]:
    """Compare a shadow author projection to package-owned consumer authority."""

    workspace_root = Path(target).resolve()
    skill_root = workspace_root / ".agents" / "skills"
    try:
        authority = load_consumer_suite_authority()
    except (OSError, TypeError, ValueError) as exc:
        return {
            "ok": False,
            "authority_schema": "flowguard.consumer_suite_authority.v1",
            "authority_hash": "",
            "authority_member_ids": [],
            "authority_member_count": 0,
            "expected_member_count": FLOWGUARD_EXPECTED_MEMBER_COUNT,
            "reserved_extras": [],
            "unrelated_colocated_members": [],
            "findings": [
                {
                    "code": "shadow_consumer_authority_unavailable",
                    "relative_path": "flowguard/consumer-suite-authority.json",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ],
            "claim_boundary": (
                "Read-only shadow currentness only; no semantic validator or "
                "evidence producer was launched."
            ),
        }
    findings: list[dict[str, object]] = []
    unrelated_members: list[str] = []
    reserved_extras: list[str] = []

    if skill_root.is_dir():
        authority_ids = {member.casefold() for member in authority.member_ids}
        for member_id in authority.member_ids:
            if not (skill_root / member_id).is_dir():
                findings.append(
                    {
                        "code": "shadow_authority_member_missing",
                        "relative_path": member_id,
                        "message": "shadow is missing a package-authority member",
                    }
                )
        for child in sorted(skill_root.iterdir(), key=lambda path: path.name.casefold()):
            child_id = child.name.casefold()
            if child_id in authority_ids:
                continue
            if child_id == "flowguard" or child_id.startswith("flowguard-"):
                reserved_extras.append(child.name)
                findings.append(
                    {
                        "code": "shadow_reserved_flowguard_member_extra",
                        "relative_path": child.name,
                        "message": "shadow contains an undeclared FlowGuard-reserved member",
                    }
                )
            else:
                unrelated_members.append(child.name)
    else:
        findings.append(
            {
                "code": "shadow_skill_root_missing",
                "relative_path": ".agents/skills",
                "message": "shadow workspace has no canonical skill root",
            }
        )

    candidate: dict[str, object] | None = None
    if skill_root.is_dir():
        try:
            candidate = json.loads(
                build_consumer_suite_authority_bytes(
                    skill_root,
                    member_ids=authority.member_ids,
                    flowguard_version=authority.flowguard_version,
                )
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(
                {
                    "code": "shadow_consumer_projection_invalid",
                    "relative_path": ".agents/skills",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )

    expected_payload = authority.to_dict()
    if candidate is not None:
        expected_files = {
            str(row["relative_path"]): row
            for row in expected_payload["files"]
        }
        actual_files = {
            str(row["relative_path"]): row
            for row in candidate.get("files", ())
            if isinstance(row, dict) and row.get("relative_path")
        }
        for relative in sorted(expected_files.keys() - actual_files.keys()):
            findings.append(
                {
                    "code": "shadow_authority_file_missing",
                    "relative_path": relative,
                    "message": "shadow projection is missing a package-authority file",
                }
            )
        for relative in sorted(actual_files.keys() - expected_files.keys()):
            findings.append(
                {
                    "code": "shadow_authority_file_extra",
                    "relative_path": relative,
                    "message": "shadow projection contains a file absent from package authority",
                }
            )
        for relative in sorted(expected_files.keys() & actual_files.keys()):
            if actual_files[relative] != expected_files[relative]:
                findings.append(
                    {
                        "code": "shadow_authority_content_drift",
                        "relative_path": relative,
                        "message": "shadow file identity differs from package authority",
                    }
                )
        if tuple(candidate.get("member_ids", ())) != authority.member_ids:
            findings.append(
                {
                    "code": "shadow_authority_member_set_mismatch",
                    "relative_path": ".agents/skills",
                    "message": "shadow member set differs from package authority",
                }
            )
        for field in (
            "raw_tree_hash",
            "semantic_tree_hash",
            "authority_hash",
        ):
            if candidate.get(field) != expected_payload.get(field):
                findings.append(
                    {
                        "code": f"shadow_authority_{field}_mismatch",
                        "relative_path": ".agents/skills",
                        "message": f"shadow {field} differs from package authority",
                    }
                )

    return {
        "ok": not findings,
        "authority_schema": "flowguard.consumer_suite_authority.v1",
        "authority_hash": authority.authority_hash,
        "authority_member_ids": list(authority.member_ids),
        "authority_member_count": len(authority.member_ids),
        "expected_member_count": FLOWGUARD_EXPECTED_MEMBER_COUNT,
        "authority_raw_tree_hash": authority.raw_tree_hash,
        "authority_semantic_tree_hash": authority.semantic_tree_hash,
        "candidate_authority_hash": (
            None if candidate is None else candidate.get("authority_hash")
        ),
        "candidate_raw_tree_hash": (
            None if candidate is None else candidate.get("raw_tree_hash")
        ),
        "candidate_semantic_tree_hash": (
            None if candidate is None else candidate.get("semantic_tree_hash")
        ),
        "reserved_extras": reserved_extras,
        "unrelated_colocated_members": unrelated_members,
        "findings": findings,
        "claim_boundary": (
            "Read-only shadow currentness only; no semantic validator or "
            "evidence producer was launched."
        ),
    }


def verify_workspace(
    target: str | Path,
    *,
    expected_version: str,
    expected_schema: str = "1.0",
    helper_name: str = "default_flowguard_self_maintenance_plan",
) -> dict[str, object]:
    target_root = Path(target).resolve()
    code = (
        "import json, flowguard, importlib.metadata as m; "
        f"helper={helper_name!r}; "
        "print(json.dumps({"
        "'schema_version': flowguard.SCHEMA_VERSION, "
        "'package_version': getattr(flowguard, '__version__', None) or m.version('flowguard'), "
        "'source_path': flowguard.__file__, "
        "'helper_name': helper, "
        "'helper_available': hasattr(flowguard, helper)"
        "}))"
    )
    completed = _run_python(target_root, code)
    if completed.returncode != 0:
        return {
            "ok": False,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    payload = json.loads(completed.stdout)
    expected_source_fragment = str(target_root / "flowguard")
    mismatches: list[str] = []
    if payload["schema_version"] != expected_schema:
        mismatches.append("schema_version")
    if payload["package_version"] != expected_version:
        mismatches.append("package_version")
    if expected_source_fragment not in str(payload["source_path"]):
        mismatches.append("source_path")
    if not payload["helper_available"]:
        mismatches.append("helper_available")
    shadow_projection = verify_shadow_skill_projection(target_root)
    if not shadow_projection["ok"]:
        mismatches.append("shadow_consumer_authority")
    payload["ok"] = not mismatches
    payload["mismatches"] = mismatches
    payload["shadow_consumer_authority"] = shadow_projection
    return payload


def _read_project_version(source: Path) -> str:
    pyproject = source / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError(f"could not read version from {pyproject}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=".", help="Source FlowGuard checkout.")
    parser.add_argument("--target", required=True, help="Shadow workspace path.")
    parser.add_argument("--dry-run", action="store_true", help="List files without copying.")
    parser.add_argument("--install", action="store_true", help="Refresh editable install in the target workspace.")
    parser.add_argument("--verify", action="store_true", help="Verify target import/version/helper state.")
    parser.add_argument("--expected-version", default="", help="Expected FlowGuard package version.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args(argv)

    source_root = Path(args.source).resolve()
    target_root = Path(args.target).resolve()
    expected_version = args.expected_version or _read_project_version(source_root)
    sync_result = sync_workspace(source_root, target_root, dry_run=args.dry_run)

    install_result = None
    if args.install and not args.dry_run:
        install_result = install_editable(target_root)

    verification = None
    if args.verify and not args.dry_run:
        verification = verify_workspace(target_root, expected_version=expected_version)

    report: dict[str, object] = {
        "artifact_type": "flowguard_shadow_sync_report",
        "source": str(source_root),
        "target": str(target_root),
        "expected_version": expected_version,
        "sync": sync_result.to_dict(),
        "install": None
        if install_result is None
        else {
            "ok": install_result.returncode == 0,
            "returncode": install_result.returncode,
            "stdout_tail": install_result.stdout.splitlines()[-20:],
            "stderr_tail": install_result.stderr.splitlines()[-20:],
        },
        "verification": verification,
    }
    ok = True
    if install_result is not None and install_result.returncode != 0:
        ok = False
    if verification is not None and not verification.get("ok"):
        ok = False
    report["ok"] = ok

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=== flowguard shadow workspace sync ===")
        print(f"source: {source_root}")
        print(f"target: {target_root}")
        print(f"copied_count: {len(sync_result.copied_files)}")
        print(f"skipped_count: {len(sync_result.skipped_paths)}")
        print(f"status: {'pass' if ok else 'blocked'}")
        if verification is not None:
            print(f"verification: {'pass' if verification.get('ok') else 'blocked'}")
            print(f"source_path: {verification.get('source_path')}")
            print(f"package_version: {verification.get('package_version')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
