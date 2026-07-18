"""Local and published release verification for FlowGuard."""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from typing import Any, Callable, Sequence


REQUIRED_UNIFIED_CHILDREN = (
    "project_audit",
    "skill_suite_static",
    "skill_self_governance",
    "model_regressions_full",
    "pytest",
    "openspec_strict",
    "distribution_check",
    "distribution_parity",
)


@dataclass(frozen=True)
class ReleaseCheck:
    check_id: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class ReleaseVerificationReport:
    phase: str
    version: str
    tag: str
    checks: tuple[ReleaseCheck, ...]
    artifact_paths: tuple[str, ...] = ()
    release_url: str = ""
    claim_boundary: str = (
        "Local verification proves the current checkout, source-only release authority, and current unified "
        "evidence. Published verification additionally proves the immutable remote tag and asset-free GitHub Release."
    )

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(check.ok for check in self.checks)

    @property
    def status(self) -> str:
        return "pass" if self.ok else "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_release_verification",
            "schema_version": "flowguard.release_verification.v1",
            "phase": self.phase,
            "version": self.version,
            "tag": self.tag,
            "status": self.status,
            "ok": self.ok,
            "checks": [check.to_dict() for check in self.checks],
            "blockers": [check.check_id for check in self.checks if not check.ok],
            "artifact_paths": list(self.artifact_paths),
            "release_url": self.release_url,
            "claim_boundary": self.claim_boundary,
        }

    def format_text(self) -> str:
        lines = [
            "=== FlowGuard release verification ===",
            f"phase: {self.phase}",
            f"version: {self.version}",
            f"tag: {self.tag}",
            f"status: {self.status}",
        ]
        lines.extend(f"- {check.check_id}: {check.status} - {check.message}" for check in self.checks)
        if self.release_url:
            lines.append(f"release_url: {self.release_url}")
        lines.append(f"claim_boundary: {self.claim_boundary}")
        return "\n".join(lines)


CommandRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


def _command_runner(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    invocation = [executable or command[0], *command[1:]]
    try:
        return subprocess.run(
            invocation,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return subprocess.CompletedProcess(
            invocation,
            127,
            stdout="",
            stderr=str(error),
        )


def _check(check_id: str, ok: bool, message: str, **details: Any) -> ReleaseCheck:
    return ReleaseCheck(check_id, "pass" if ok else "fail", message, details)


def _project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _package_archives(root: Path, version: str) -> tuple[Path, ...]:
    dist = root / "dist"
    return tuple(sorted(dist.glob(f"flowguard-{version}*.whl"))) + tuple(
        sorted(dist.glob(f"flowguard-{version}.tar.gz"))
    )


def _latest_governed_source(root: Path) -> tuple[Path | None, int]:
    roots = (
        root / "flowguard",
        root / "scripts",
        root / "tests",
        root / "docs",
        root / "openspec" / "changes",
        root / "openspec" / "specs",
        root / ".agents" / "skills",
        root / ".skillguard" / "flowguard-suite",
        root / ".flowguard",
    )
    direct = (root / "pyproject.toml", root / "README.md", root / "CHANGELOG.md", root / "AGENTS.md")
    candidates: list[Path] = [path for path in direct if path.is_file()]
    for source_root in roots:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if (
                "/__pycache__/" in f"/{relative}/"
                or relative.startswith(".flowguard/evidence/")
                or relative.endswith(".pyc")
                or relative.endswith("/result.json")
                or (
                    relative.startswith("openspec/changes/")
                    and (
                        relative.endswith("/tasks.md")
                        or relative.endswith("/verification-report.json")
                    )
                )
                or "/reports/current_" in relative
                or "/ai_judgments/current_" in relative
                or "/evidence/current_" in relative
                or relative.endswith("skillguard_progress_ledger.jsonl")
            ):
                continue
            candidates.append(path)
    if not candidates:
        return None, 0
    latest = max(candidates, key=lambda path: path.stat().st_mtime_ns)
    return latest, latest.stat().st_mtime_ns


def verify_local_release(
    root: str | Path,
    *,
    version: str | None = None,
    evidence_path: str | Path | None = None,
    installed_version: str | None = None,
    schema_version: str | None = None,
    source_path: str | Path | None = None,
) -> ReleaseVerificationReport:
    root_path = Path(root).resolve()
    selected_version = version or _project_version(root_path)
    tag = f"v{selected_version}"
    checks: list[ReleaseCheck] = []

    manifest_path = root_path / ".flowguard" / "project.toml"
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    manifest_flowguard = manifest["flowguard"]
    manifest_version = str(
        manifest_flowguard.get("adopted_package_version")
        or manifest_flowguard.get("package_version")
        or ""
    )
    readme = (root_path / "README.md").read_text(encoding="utf-8")
    changelog = (root_path / "CHANGELOG.md").read_text(encoding="utf-8")
    project_version = _project_version(root_path)
    checks.append(
        _check(
            "release.version_alignment",
            project_version == selected_version
            and manifest_version == selected_version
            and selected_version in readme
            and (
                f"[{selected_version}]" in changelog
                or re.search(rf"(?m)^##\s+v?{re.escape(selected_version)}(?:\s|$)", changelog) is not None
            ),
            "package, project record, README, and changelog versions align",
            project_version=project_version,
            manifest_version=manifest_version,
        )
    )

    if installed_version is None:
        installed_version = importlib.metadata.version("flowguard")
    if schema_version is None or source_path is None:
        import flowguard

        schema_version = schema_version or str(flowguard.SCHEMA_VERSION)
        source_path = source_path or str(Path(flowguard.__file__).resolve())
    resolved_source = Path(source_path).resolve()
    checks.append(
        _check(
            "release.editable_install",
            installed_version == selected_version
            and schema_version == str(manifest_flowguard["schema_version"])
            and resolved_source.is_relative_to(root_path),
            "the active package matches the release version, schema, and formal source root",
            installed_version=installed_version,
            schema_version=schema_version,
            source_path=str(resolved_source),
        )
    )

    evidence = (
        Path(evidence_path).resolve()
        if evidence_path is not None
        else root_path / ".flowguard" / "evidence" / "release" / f"v{selected_version}-local" / "result.json"
    )
    evidence_payload: dict[str, Any] = {}
    if evidence.exists():
        evidence_payload = json.loads(evidence.read_text(encoding="utf-8"))
    child_status = {
        str(child.get("child_id")): str(child.get("status"))
        for child in evidence_payload.get("children", [])
    }
    evidence_ok = (
        evidence_payload.get("status") == "pass"
        and evidence_payload.get("broad_success") is True
        and not evidence_payload.get("blockers")
        and not evidence_payload.get("skipped_checks")
        and all(child_status.get(child_id) == "pass" for child_id in REQUIRED_UNIFIED_CHILDREN)
    )
    checks.append(
        _check(
            "release.local_evidence",
            evidence_ok,
            "the unified local gate has eight exact-pass children and no skipped checks",
            evidence_path=str(evidence),
            child_status=child_status,
        )
    )
    latest_source, latest_source_mtime = _latest_governed_source(root_path)
    evidence_mtime = evidence.stat().st_mtime_ns if evidence.exists() else 0
    checks.append(
        _check(
            "release.evidence_freshness",
            bool(evidence_mtime) and evidence_mtime >= latest_source_mtime,
            "the unified result is not older than any governed source, model, prompt, contract, test, or OpenSpec input",
            evidence_path=str(evidence),
            latest_source=str(latest_source) if latest_source else "",
        )
    )

    package_archives = _package_archives(root_path, selected_version)
    checks.append(
        _check(
            "release.source_only_authority",
            not package_archives,
            "the source tag is the sole release authority and no version-matching package archive is present",
            package_archives=[path.name for path in package_archives],
        )
    )
    return ReleaseVerificationReport(
        phase="local",
        version=selected_version,
        tag=tag,
        checks=tuple(checks),
        artifact_paths=(str(evidence),),
    )


def _parse_github_repository(remote_url: str) -> str:
    match = re.search(r"github\.com[/:]([^/\s]+/[^/\s]+?)(?:\.git)?$", remote_url.strip())
    return match.group(1) if match else ""


def _remote_tag_commit(output: str, tag: str) -> tuple[str, dict[str, str]]:
    refs: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            refs[fields[1]] = fields[0]
    tag_ref = f"refs/tags/{tag}"
    return refs.get(f"{tag_ref}^{{}}") or refs.get(tag_ref, ""), refs


def verify_published_release(
    root: str | Path,
    *,
    version: str | None = None,
    evidence_path: str | Path | None = None,
    repository: str | None = None,
    command_runner: CommandRunner = _command_runner,
) -> ReleaseVerificationReport:
    root_path = Path(root).resolve()
    local = verify_local_release(root_path, version=version, evidence_path=evidence_path)
    selected_version = local.version
    tag = local.tag
    checks = list(local.checks)

    remote_result = command_runner(("git", "remote", "get-url", "origin"), root_path)
    detected_repository = _parse_github_repository(remote_result.stdout) if remote_result.returncode == 0 else ""
    selected_repository = repository or detected_repository
    checks.append(
        _check(
            "release.github_repository",
            bool(selected_repository) and (not repository or repository == detected_repository),
            "the configured origin resolves to the expected GitHub repository",
            repository=selected_repository,
            origin=remote_result.stdout.strip(),
        )
    )

    local_tag = command_runner(("git", "rev-list", "-n", "1", tag), root_path)
    remote_tag = command_runner(
        ("git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}*"),
        root_path,
    )
    remote_commit, remote_refs = _remote_tag_commit(remote_tag.stdout, tag)
    local_commit = local_tag.stdout.strip()
    checks.append(
        _check(
            "release.remote_tag",
            local_tag.returncode == 0
            and remote_tag.returncode == 0
            and bool(local_commit)
            and local_commit == remote_commit,
            "the immutable remote tag resolves to the same commit as the local release tag",
            local_commit=local_commit,
            remote_commit=remote_commit,
            remote_refs=remote_refs,
        )
    )

    release_view = command_runner(
        (
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            selected_repository,
            "--json",
            "tagName,isDraft,isPrerelease,url,targetCommitish,assets,publishedAt",
        ),
        root_path,
    )
    release_payload: dict[str, Any] = {}
    if release_view.returncode == 0:
        try:
            release_payload = json.loads(release_view.stdout)
        except json.JSONDecodeError:
            release_payload = {}
    published_asset_names = {
        str(asset.get("name")) for asset in release_payload.get("assets", []) if asset.get("name")
    }
    release_ok = (
        release_payload.get("tagName") == tag
        and release_payload.get("isDraft") is False
        and bool(release_payload.get("publishedAt"))
        and not published_asset_names
    )
    checks.append(
        _check(
            "release.github_release",
            release_view.returncode == 0 and release_ok,
            "the GitHub Release is published, points at the source tag, and contains no package assets",
            assets=sorted(published_asset_names),
            is_prerelease=release_payload.get("isPrerelease"),
        )
    )
    return ReleaseVerificationReport(
        phase="published",
        version=selected_version,
        tag=tag,
        checks=tuple(checks),
        artifact_paths=local.artifact_paths,
        release_url=str(release_payload.get("url") or ""),
    )


__all__ = [
    "REQUIRED_UNIFIED_CHILDREN",
    "ReleaseCheck",
    "ReleaseVerificationReport",
    "verify_local_release",
    "verify_published_release",
]
