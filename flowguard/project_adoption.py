"""Project-local FlowGuard adoption and version gate helpers."""

from __future__ import annotations

import importlib.metadata
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # pragma: no cover - Python 3.10 fallback
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from .adoption import append_jsonl, append_markdown_log, make_adoption_log_entry
from .artifact_upgrade import ArtifactUpgradeReport, review_artifact_upgrades
from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable
from .schema import SCHEMA_VERSION


FLOWGUARD_REPOSITORY_URL = "https://github.com/liuyingxuvka/FlowGuard"
FLOWGUARD_AGENTS_BEGIN = "<!-- BEGIN FLOWGUARD PROJECT RULES -->"
FLOWGUARD_AGENTS_END = "<!-- END FLOWGUARD PROJECT RULES -->"
FLOWGUARD_PROJECT_MANIFEST = ".flowguard/project.toml"
FLOWGUARD_PROJECT_LOG = ".flowguard/adoption_log.jsonl"
FLOWGUARD_PROJECT_MARKDOWN_LOG = "docs/flowguard_adoption_log.md"

PROJECT_ADOPTION_ACTION_AUDIT = "audit"
PROJECT_ADOPTION_ACTION_ADOPT = "adopt"
PROJECT_ADOPTION_ACTION_UPGRADE = "upgrade"

PROJECT_ADOPTION_STATUS_PASS = "pass"
PROJECT_ADOPTION_STATUS_PASS_WITH_GAPS = "pass_with_gaps"
PROJECT_ADOPTION_STATUS_BLOCKED = "blocked"


@dataclass(frozen=True)
class ProjectAdoptionFinding:
    """One finding from project adoption audit/adopt/upgrade work."""

    severity: str
    category: str
    message: str
    recommendation: str = ""
    file_path: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity).lower()
        if severity not in {"info", "warning", "blocked"}:
            raise ValueError("severity must be info, warning, or blocked")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "category", str(self.category))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "recommendation", str(self.recommendation or ""))
        object.__setattr__(self, "file_path", str(self.file_path or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "recommendation": self.recommendation,
            "file_path": self.file_path,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ProjectAdoptionReport:
    """Structured report for a project adoption command."""

    root: str
    action: str
    installed_package_version: str
    schema_version: str
    manifest_package_version: str = ""
    manifest_schema_version: str = ""
    findings: tuple[ProjectAdoptionFinding, ...] = ()
    written_files: tuple[str, ...] = ()
    artifact_upgrade_report: ArtifactUpgradeReport | None = None

    @property
    def ok(self) -> bool:
        return not any(finding.severity == "blocked" for finding in self.findings)

    @property
    def status(self) -> str:
        if not self.ok:
            return PROJECT_ADOPTION_STATUS_BLOCKED
        if self.findings:
            return PROJECT_ADOPTION_STATUS_PASS_WITH_GAPS
        return PROJECT_ADOPTION_STATUS_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_project_adoption_report",
            "root": self.root,
            "action": self.action,
            "ok": self.ok,
            "status": self.status,
            "repository": FLOWGUARD_REPOSITORY_URL,
            "installed_package_version": self.installed_package_version,
            "schema_version": self.schema_version,
            "manifest_package_version": self.manifest_package_version,
            "manifest_schema_version": self.manifest_schema_version,
            "written_files": list(self.written_files),
            "findings": [finding.to_dict() for finding in self.findings],
            "artifact_upgrade_report": (
                self.artifact_upgrade_report.to_dict()
                if self.artifact_upgrade_report is not None
                else None
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== flowguard project adoption ===",
            f"action: {self.action}",
            f"status: {self.status}",
            f"repository: {FLOWGUARD_REPOSITORY_URL}",
            f"installed_package_version: {self.installed_package_version}",
            f"schema_version: {self.schema_version}",
        ]
        if self.manifest_package_version:
            lines.append(f"manifest_package_version: {self.manifest_package_version}")
        if self.written_files:
            lines.append("written_files:")
            lines.extend(f"- {path}" for path in self.written_files)
        if self.artifact_upgrade_report is not None:
            lines.extend(
                [
                    "",
                    "artifact_upgrade:",
                    f"  status: {'pass' if self.artifact_upgrade_report.ok else 'blocked'}",
                    f"  summary: {self.artifact_upgrade_report.summary}",
                ]
            )
        for finding in self.findings:
            lines.extend(
                [
                    "",
                    f"{finding.severity.upper()}: {finding.category}",
                    f"message: {finding.message}",
                ]
            )
            if finding.file_path:
                lines.append(f"file: {finding.file_path}")
            if finding.recommendation:
                lines.append(f"recommendation: {finding.recommendation}")
        return "\n".join(lines)


def installed_flowguard_package_version() -> str:
    """Return the installed FlowGuard package version, or an empty string."""

    try:
        return importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        return ""


def current_project_manifest_text(
    *,
    package_version: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    verified_by: str = "FlowGuard project-adopt",
) -> str:
    """Build the canonical `.flowguard/project.toml` text."""

    package = package_version if package_version is not None else installed_flowguard_package_version()
    verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return (
        "[flowguard]\n"
        f'repository = "{FLOWGUARD_REPOSITORY_URL}"\n'
        f'adopted_package_version = "{package}"\n'
        f'schema_version = "{schema_version}"\n'
        f'last_verified_at = "{verified_at}"\n'
        f'last_verified_by = "{verified_by}"\n'
        'agents_path = "AGENTS.md"\n'
        "\n"
        "[policy]\n"
        "upgrade_when_installed_version_is_newer = true\n"
        "latest_schema_first = true\n"
        "upgrade_existing_artifacts_when_project_version_is_older = true\n"
        "require_adoption_log = true\n"
        "require_model_update_for_behavior_changes = true\n"
    )


def build_flowguard_agents_block(
    *,
    package_version: str | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    """Build the managed AGENTS.md block for target projects."""

    package = package_version if package_version is not None else installed_flowguard_package_version()
    return f"""{FLOWGUARD_AGENTS_BEGIN}
## FlowGuard Project Rules

This project uses FlowGuard for non-trivial maintenance, feature work, bug
fixes, refactors, tests, release work, project upgrades, and evidence-sensitive
process changes.

FlowGuard repository:
{FLOWGUARD_REPOSITORY_URL}

Project FlowGuard record:
- Manifest: `{FLOWGUARD_PROJECT_MANIFEST}`
- Machine log: `{FLOWGUARD_PROJECT_LOG}`
- Human log: `{FLOWGUARD_PROJECT_MARKDOWN_LOG}`

Current adoption record:
- FlowGuard package version: `{package}`
- FlowGuard schema version: `{schema_version}`

Before non-trivial work:
1. Verify the real package:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
2. Check the installed package version:
   `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
3. Audit the project record:
   `python -m flowguard project-audit --root .`
4. Compare the installed version with `{FLOWGUARD_PROJECT_MANIFEST}`.
5. If the installed version is newer, run:
   `python -m flowguard project-upgrade --root .`
   This updates the project record and scans existing FlowGuard artifacts,
   model evidence, tests, docs, and guidance for deterministic upgrades into
   the current FlowGuard shape. Use `--records-only` only when intentionally
   scoping out artifact/model/test upgrade scanning.
   Then rerun affected models/tests before broad confidence and record the result.
6. If the installed version is older than the project record, stop and upgrade
   the local FlowGuard toolchain before claiming FlowGuard confidence.

FlowGuard runtime guidance is latest-schema-first: old artifacts may be
detected and upgraded at project/tool boundaries, but normal route logic should
not preserve long-lived compatibility branches for obsolete fields, aliases, or
wrappers.

Default replacement means dispose the old path, old field, alias, wrapper, or
fallback unless compatibility or preservation is explicitly requested. If
compatibility is explicit, record the preserved surface, compatibility intent,
and current evidence; otherwise delete, block, migrate, delegate, repair, or
scope it out with a concrete reason.

Field-bearing work should use or update FieldLifecycleMesh: high-level behavior
models include behavior-bearing fields, while child/leaf field rows account all
discovered fields and record owner, readers, writers, projection, lifecycle,
and old-field disposition.

UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.

After non-trivial FlowGuard-managed work, run or record a maintenance scan when
changed artifacts, skipped routes, stale evidence, or split/reduction signals
may require an owning route such as Model-Test Alignment,
DevelopmentProcessFlow, Architecture Reduction, StructureMesh, ModelMesh,
TestMesh, or AgentWorkflowRehearsal.

Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.
{FLOWGUARD_AGENTS_END}"""


def update_agents_text(existing_text: str, managed_block: str) -> str:
    """Insert or replace the managed FlowGuard AGENTS block."""

    if FLOWGUARD_AGENTS_BEGIN in existing_text and FLOWGUARD_AGENTS_END in existing_text:
        pattern = re.compile(
            re.escape(FLOWGUARD_AGENTS_BEGIN)
            + r".*?"
            + re.escape(FLOWGUARD_AGENTS_END),
            re.DOTALL,
        )
        return pattern.sub(managed_block, existing_text, count=1)
    if not existing_text.strip():
        return managed_block + "\n"
    return existing_text.rstrip() + "\n\n" + managed_block + "\n"


def audit_project_adoption(root: str | Path = ".") -> ProjectAdoptionReport:
    """Read-only audit of target-project FlowGuard adoption/version records."""

    root_path = Path(root).resolve()
    package_version = installed_flowguard_package_version()
    manifest = _read_manifest(root_path / FLOWGUARD_PROJECT_MANIFEST)
    manifest_package = str(manifest.get("adopted_package_version", ""))
    manifest_schema = str(manifest.get("schema_version", ""))
    findings = _audit_findings(root_path, package_version, manifest, manifest_package, manifest_schema)
    return ProjectAdoptionReport(
        root=str(root_path),
        action=PROJECT_ADOPTION_ACTION_AUDIT,
        installed_package_version=package_version,
        schema_version=SCHEMA_VERSION,
        manifest_package_version=manifest_package,
        manifest_schema_version=manifest_schema,
        findings=tuple(findings),
    )


def adopt_project(
    root: str | Path = ".",
    *,
    verified_by: str = "FlowGuard project-adopt",
) -> ProjectAdoptionReport:
    """Write target-project FlowGuard AGENTS, manifest, and adoption logs."""

    return _write_project_adoption(root, action=PROJECT_ADOPTION_ACTION_ADOPT, verified_by=verified_by)


def upgrade_project(
    root: str | Path = ".",
    *,
    verified_by: str = "FlowGuard project-upgrade",
    records_only: bool = False,
) -> ProjectAdoptionReport:
    """Explicitly update target-project FlowGuard records to the installed version."""

    return _write_project_adoption(
        root,
        action=PROJECT_ADOPTION_ACTION_UPGRADE,
        verified_by=verified_by,
        records_only=records_only,
    )


def _write_project_adoption(
    root: str | Path,
    *,
    action: str,
    verified_by: str,
    records_only: bool = False,
) -> ProjectAdoptionReport:
    root_path = Path(root).resolve()
    package_version = installed_flowguard_package_version()
    manifest_path = root_path / FLOWGUARD_PROJECT_MANIFEST
    manifest = _read_manifest(manifest_path)
    manifest_package = str(manifest.get("adopted_package_version", ""))
    manifest_schema = str(manifest.get("schema_version", ""))
    preflight_findings = _audit_findings(root_path, package_version, manifest, manifest_package, manifest_schema)
    blocked = [finding for finding in preflight_findings if finding.severity == "blocked"]
    if blocked:
        return ProjectAdoptionReport(
            root=str(root_path),
            action=action,
            installed_package_version=package_version,
            schema_version=SCHEMA_VERSION,
            manifest_package_version=manifest_package,
            manifest_schema_version=manifest_schema,
            findings=tuple(blocked),
        )

    artifact_upgrade_report: ArtifactUpgradeReport | None = None
    upgrade_needed = _project_upgrade_scan_needed(package_version, manifest_package, manifest_schema)
    if action == PROJECT_ADOPTION_ACTION_UPGRADE and upgrade_needed and not records_only:
        artifact_upgrade_report = review_artifact_upgrades(root_path, apply=True)

    agents_path = root_path / "AGENTS.md"
    existing_agents = _read_text(agents_path)
    agents_block = build_flowguard_agents_block(package_version=package_version, schema_version=SCHEMA_VERSION)
    updated_agents = update_agents_text(existing_agents, agents_block)

    written: list[str] = []
    if updated_agents != existing_agents:
        agents_path.write_text(updated_agents, encoding="utf-8")
        written.append(str(agents_path))

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_text = current_project_manifest_text(
        package_version=package_version,
        schema_version=SCHEMA_VERSION,
        verified_by=verified_by,
    )
    if _read_text(manifest_path) != manifest_text:
        manifest_path.write_text(manifest_text, encoding="utf-8")
        written.append(str(manifest_path))

    log_jsonl = root_path / FLOWGUARD_PROJECT_LOG
    log_markdown = root_path / FLOWGUARD_PROJECT_MARKDOWN_LOG
    log_entry = make_adoption_log_entry(
        task_id=f"flowguard-project-{action}",
        project=root_path.name,
        task_summary=f"FlowGuard project {action} record update",
        trigger_reason="target project uses FlowGuard and needs durable AGENTS/version records",
        status="completed",
        findings=(
            f"FlowGuard repository recorded: {FLOWGUARD_REPOSITORY_URL}",
            f"FlowGuard package version recorded: {package_version}",
            f"FlowGuard schema version recorded: {SCHEMA_VERSION}",
            *(
                (f"Artifact upgrade scan: {artifact_upgrade_report.summary}",)
                if artifact_upgrade_report is not None
                else ()
            ),
        ),
        skipped_steps=(
            "Project adoption record does not replace executable model checks, tests, replay, or closure evidence.",
            *(
                ("Artifact/model/test upgrade scan was scoped out by records-only mode.",)
                if action == PROJECT_ADOPTION_ACTION_UPGRADE and records_only
                else ()
            ),
        ),
        next_actions=(
            "Rerun affected FlowGuard models/tests before broad completion claims when behavior, tests, or version records change.",
        ),
    )
    append_jsonl(log_jsonl, log_entry)
    append_markdown_log(log_markdown, log_entry)
    written.extend((str(log_jsonl), str(log_markdown)))

    findings = [
        finding
        for finding in preflight_findings
        if finding.category not in {"missing_agents_block", "missing_project_manifest", "project_flowguard_upgrade_available"}
    ]
    if action == PROJECT_ADOPTION_ACTION_UPGRADE and records_only:
        findings.append(
            ProjectAdoptionFinding(
                "warning",
                "artifact_upgrade_scan_scoped_out",
                "Artifact/model/test upgrade scanning was scoped out by records-only mode.",
                "Run project-upgrade without --records-only or run artifact-upgrade before broad confidence claims.",
            )
        )
    if artifact_upgrade_report is not None and not artifact_upgrade_report.ok:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "artifact_upgrade_blocked",
                "Artifact/model/test upgrade scan found blocked items.",
                "Review blocked paths before claiming the project is current.",
                metadata={"blocked_paths": artifact_upgrade_report.blocked_paths},
            )
        )
    findings.append(
        ProjectAdoptionFinding(
            "info",
            "adoption_record_written",
            "FlowGuard project AGENTS block, manifest, and adoption log were written or refreshed.",
            "Run affected model/test validation before broad confidence claims.",
        )
    )
    return ProjectAdoptionReport(
        root=str(root_path),
        action=action,
        installed_package_version=package_version,
        schema_version=SCHEMA_VERSION,
        manifest_package_version=package_version,
        manifest_schema_version=SCHEMA_VERSION,
        findings=tuple(findings),
        written_files=tuple(written),
        artifact_upgrade_report=artifact_upgrade_report,
    )


def _project_upgrade_scan_needed(package_version: str, manifest_package: str, manifest_schema: str) -> bool:
    if manifest_schema and manifest_schema != SCHEMA_VERSION:
        return True
    if manifest_package and package_version:
        comparison = compare_versions(package_version, manifest_package)
        return comparison is not None and comparison > 0
    return False


def _audit_findings(
    root_path: Path,
    package_version: str,
    manifest: dict[str, Any],
    manifest_package: str,
    manifest_schema: str,
) -> list[ProjectAdoptionFinding]:
    findings: list[ProjectAdoptionFinding] = []
    agents_path = root_path / "AGENTS.md"
    agents_text = _read_text(agents_path)
    if not agents_text or FLOWGUARD_AGENTS_BEGIN not in agents_text or FLOWGUARD_AGENTS_END not in agents_text:
        findings.append(
            ProjectAdoptionFinding(
                "warning",
                "missing_agents_block",
                "target project does not have a managed FlowGuard AGENTS.md block",
                "Run `python -m flowguard project-adopt --root .` before non-trivial FlowGuard work.",
                str(agents_path),
            )
        )
    if not manifest:
        findings.append(
            ProjectAdoptionFinding(
                "warning",
                "missing_project_manifest",
                "target project does not have .flowguard/project.toml",
                "Run `python -m flowguard project-adopt --root .` to record the adopted FlowGuard version.",
                str(root_path / FLOWGUARD_PROJECT_MANIFEST),
            )
        )
    if not package_version:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "flowguard_package_unavailable",
                "the real FlowGuard package version could not be found",
                f"Install or connect FlowGuard from {FLOWGUARD_REPOSITORY_URL}.",
            )
        )
    if manifest and str(manifest.get("repository", "")) != FLOWGUARD_REPOSITORY_URL:
        findings.append(
            ProjectAdoptionFinding(
                "warning",
                "repository_url_mismatch",
                "project manifest does not point to the canonical FlowGuard repository",
                f"Use {FLOWGUARD_REPOSITORY_URL}.",
                str(root_path / FLOWGUARD_PROJECT_MANIFEST),
            )
        )
    if manifest_schema and manifest_schema != SCHEMA_VERSION:
        findings.append(
            ProjectAdoptionFinding(
                "warning",
                "schema_version_mismatch",
                "project manifest schema version differs from the installed FlowGuard schema",
                "Run project-upgrade and rerun affected model/test evidence before broad confidence claims.",
                str(root_path / FLOWGUARD_PROJECT_MANIFEST),
                {"manifest_schema_version": manifest_schema, "installed_schema_version": SCHEMA_VERSION},
            )
        )
    if manifest_package and package_version:
        comparison = compare_versions(package_version, manifest_package)
        if comparison is None:
            findings.append(
                ProjectAdoptionFinding(
                    "warning",
                    "unknown_flowguard_version_comparison",
                    "could not compare installed FlowGuard package version with the project manifest",
                    "Review package release notes and update the project manifest manually if needed.",
                    str(root_path / FLOWGUARD_PROJECT_MANIFEST),
                    {"installed_package_version": package_version, "manifest_package_version": manifest_package},
                )
            )
        elif comparison < 0:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "installed_flowguard_older",
                    "installed FlowGuard package is older than the project-recorded version",
                    "Upgrade the local FlowGuard toolchain before claiming FlowGuard confidence.",
                    str(root_path / FLOWGUARD_PROJECT_MANIFEST),
                    {"installed_package_version": package_version, "manifest_package_version": manifest_package},
                )
            )
        elif comparison > 0:
            findings.append(
                ProjectAdoptionFinding(
                    "warning",
                    "project_flowguard_upgrade_available",
                    "installed FlowGuard package is newer than the project-recorded version",
                    "Run project-upgrade, check release notes/changelog, and rerun affected model/test evidence before broad confidence.",
                    str(root_path / FLOWGUARD_PROJECT_MANIFEST),
                    {"installed_package_version": package_version, "manifest_package_version": manifest_package},
                )
            )
    return findings


def _read_manifest(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if not text:
        return {}
    if tomllib is not None:
        try:
            payload = tomllib.loads(text)
            flowguard_section = payload.get("flowguard", {})
            return dict(flowguard_section) if isinstance(flowguard_section, dict) else {}
        except Exception:
            return {}
    return _read_manifest_fallback(text)


def _read_manifest_fallback(text: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    in_flowguard = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_flowguard = line == "[flowguard]"
            continue
        if not in_flowguard or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def compare_versions(left: str, right: str) -> int | None:
    """Compare simple release versions. Return -1, 0, 1, or None if unknown."""

    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts is None or right_parts is None:
        return None
    length = max(len(left_parts), len(right_parts))
    padded_left = left_parts + (0,) * (length - len(left_parts))
    padded_right = right_parts + (0,) * (length - len(right_parts))
    if padded_left < padded_right:
        return -1
    if padded_left > padded_right:
        return 1
    return 0


def _version_parts(value: str) -> tuple[int, ...] | None:
    cleaned = str(value or "").strip().lstrip("vV")
    if not cleaned:
        return None
    pieces = re.split(r"[.\-+]", cleaned)
    numbers: list[int] = []
    for piece in pieces:
        if piece == "":
            continue
        if not piece.isdigit():
            return None
        numbers.append(int(piece))
    return tuple(numbers) if numbers else None


__all__ = [
    "FLOWGUARD_AGENTS_BEGIN",
    "FLOWGUARD_AGENTS_END",
    "FLOWGUARD_PROJECT_LOG",
    "FLOWGUARD_PROJECT_MANIFEST",
    "FLOWGUARD_PROJECT_MARKDOWN_LOG",
    "FLOWGUARD_REPOSITORY_URL",
    "PROJECT_ADOPTION_ACTION_ADOPT",
    "PROJECT_ADOPTION_ACTION_AUDIT",
    "PROJECT_ADOPTION_ACTION_UPGRADE",
    "PROJECT_ADOPTION_STATUS_BLOCKED",
    "PROJECT_ADOPTION_STATUS_PASS",
    "PROJECT_ADOPTION_STATUS_PASS_WITH_GAPS",
    "ProjectAdoptionFinding",
    "ProjectAdoptionReport",
    "adopt_project",
    "audit_project_adoption",
    "build_flowguard_agents_block",
    "compare_versions",
    "current_project_manifest_text",
    "installed_flowguard_package_version",
    "update_agents_text",
    "upgrade_project",
]
