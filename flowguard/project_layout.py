"""Strict, human-readable layout governance for a target project's ``.flowguard``.

The project control plane is intentionally split by *role*, not by the order in
which historical checks happened to create files.  This module is read-only:
it audits the current directory and emits a direct-current repair plan, but it
never moves, copies, deletes, or silently reads an older layout.

The layout manifest is deliberately a small TOML document so a person can
understand it without opening the Python package.  Every current FlowGuard
project must use this layout: an unknown entry, a retired name such as
``dna_audit`` or ``tmp``, a path role collision, or a stale manifest blocks the
project.  A maintainer/AI must directly classify and rewrite an old target into
the current layout before retrying; this module never performs that rewrite and
there is no opt-in, compatibility reader, or automatic migration path.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping

from .observation_metrics import InvocationMetrics
from .runtime_artifacts import (
    classify_runtime_artifact,
    is_governed_source_in_runtime_cache,
    is_non_authority_path,
)


PROJECT_LAYOUT_SCHEMA = "flowguard.project_layout.v3"
PROJECT_LAYOUT_VERSION = 3
PROJECT_LAYOUT_INVENTORY_SCHEMA = "flowguard.project_layout_shape.v1"
PROJECT_LAYOUT_MANIFEST = ".flowguard/layout.toml"
PROJECT_LAYOUT_CLAIM_BOUNDARY = (
    "This audit proves only the exact .flowguard role layout, manifest identity, "
    "and direct-current naming boundary. It does not prove model semantics, "
    "tests, execution, installation, release, or business behavior."
)

# These are the only role roots a current target project may use.  The names
# describe what a human will find there; the word DNA is intentionally absent.
CANONICAL_ROLE_ROOTS: tuple[tuple[str, str], ...] = (
    ("behavior", "current_effective_intent_and_behavior_contracts"),
    ("models", "current_executable_model_authority"),
    ("structure", "surface_ownership_and_code_binding_maps"),
    ("verification", "test_and_check_definitions"),
    ("evidence", "immutable_execution_evidence"),
    ("history", "explicit_historical_context"),
)
CANONICAL_ROLE_ROOT_NAMES = frozenset(name for name, _ in CANONICAL_ROLE_ROOTS)
# Historical and transient material is deliberately not current authority.
# It may contain long receipt paths or tool-specific names that are valid as
# provenance but cannot affect the current model/verification layout.  Keep the
# complete contents opaque: the evidence/history owners validate their own
# pointers and payloads, while this module only proves that the two containers
# exist in the right role roots.
OPAQUE_ROLE_ROOTS = frozenset({"evidence", "history"})
CANONICAL_FILES: Mapping[str, str] = {
    "project.toml": "project_identity_and_policy",
    "layout.toml": "layout_authority",
    "adoption_log.jsonl": "process_log",
    "README.md": "human_navigation_only",
}

# A name that looks descriptive in an old checkout is not allowed to become a
# second authority in a current checkout.  Keep this list explicit and small;
# generic words such as ``reports`` are not rejected unless they occur in a
# forbidden position.
RETIRED_LAYOUT_COMPONENTS = frozenset(
    {
        "dna",
        "dna_audit",
        "software_dna",
        "portable_dna",
        "tmp",
        "temp",
        "run_artifacts",
        "materialization",
        "bundle",
        "bundles",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".hypothesis",
        "cache",
        "caches",
    }
)
BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})
NON_AUTHORITY_ROLES = frozenset({"evidence", "history"})
CURRENT_AUTHORITY_ROLES = frozenset(
    name for name in CANONICAL_ROLE_ROOT_NAMES if name not in NON_AUTHORITY_ROLES
)
# Python package markers such as ``__init__.py`` are legitimate current
# content.  A leading dot remains disallowed so hidden temporary files cannot
# silently become part of the current control plane.
_SAFE_COMPONENT_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9._-]*|[A-Za-z0-9][A-Za-z0-9._-]*)$")
_OWNER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SHA256_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# ``project.toml`` is intentionally the only current project/adoption record.
# Keep this small gate in the layout owner so a caller cannot read a valid
# shape and then silently fall back to an alternate project or model pointer.
# The full semantic authority audit remains owned by model_authority_store.
_PROJECT_MANIFEST_REQUIRED_FIELDS = frozenset(
    {
        "repository",
        "adopted_package_version",
        "schema_version",
        "last_verified_at",
        "last_verified_by",
        "agents_path",
    }
)
_MODEL_AUTHORITY_REQUIRED_FIELDS = frozenset(
    {
        "system_id",
        "observed_snapshot_path",
        "observed_snapshot_fingerprint",
        "subject_revision",
        "coverage_status",
        "generation",
        "accepted_revision_set_fingerprint",
        "previous_snapshot_fingerprint",
        "activation_receipt_fingerprint",
        "head_fingerprint",
    }
)


@dataclass(frozen=True)
class ProjectLayoutFinding:
    """One deterministic layout finding."""

    severity: str
    code: str
    path: str = ""
    message: str = ""
    recommendation: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in {"info", "warning", "blocked"}:
            raise ValueError("severity must be info, warning, or blocked")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "recommendation": self.recommendation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LayoutObservation:
    """One guarded, invocation-local shape observation of ``.flowguard``.

    The observation contains paths and entry kinds only.  It deliberately has
    no member-content fingerprints; governed source identity is owned by the
    model/validation routes that consume the relevant files.
    """

    root: str
    paths: tuple[Path, ...] = ()
    traversal_findings: tuple[ProjectLayoutFinding, ...] = ()


@dataclass(frozen=True)
class ProjectLayoutReport:
    """Read-only result for the target project's current layout."""

    root: str
    flowguard_root: str
    status: str
    schema: str = PROJECT_LAYOUT_SCHEMA
    layout_version: int | None = None
    manifest_fingerprint: str = ""
    project_identity: str = ""
    inventory_fingerprint: str = ""
    observed_entries: tuple[str, ...] = ()
    role_counts: Mapping[str, int] = field(default_factory=dict)
    findings: tuple[ProjectLayoutFinding, ...] = ()
    claim_boundary: str = PROJECT_LAYOUT_CLAIM_BOUNDARY
    metrics: Mapping[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "pass" and not any(
            finding.severity == "blocked" for finding in self.findings
        )

    @property
    def blockers(self) -> tuple[ProjectLayoutFinding, ...]:
        return tuple(
            finding for finding in self.findings if finding.severity == "blocked"
        )

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.ok:
            return ()
        return (
            "Stop before reading old layout paths as current authority.",
            "Manually classify every blocked entry into one current role or an explicit retirement/history record.",
            "Create a new current .flowguard/layout.toml and rebuild affected model, contract, test, and evidence identities.",
            "Rerun project-layout-audit before project-audit, model work, or execution claims.",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_project_layout_report",
            "schema": self.schema,
            "root": self.root,
            "flowguard_root": self.flowguard_root,
            "status": self.status,
            "ok": self.ok,
            "layout_version": self.layout_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "project_identity": self.project_identity,
            "inventory_fingerprint": self.inventory_fingerprint,
            "observed_entries": list(self.observed_entries),
            "role_counts": dict(sorted(self.role_counts.items())),
            "findings": [finding.to_dict() for finding in self.findings],
            "blockers": [finding.to_dict() for finding in self.blockers],
            "next_actions": list(self.next_actions),
            "claim_boundary": self.claim_boundary,
            "metrics": dict(self.metrics),
        }

    def to_json_text(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            f"FlowGuard project layout: {self.status}",
            f"root: {self.root}",
            f"layout version: {self.layout_version if self.layout_version is not None else 'unknown'}",
            f"project identity: {self.project_identity or 'unknown'}",
            f"entries: {len(self.observed_entries)}",
        ]
        if self.role_counts:
            lines.append("roles:")
            lines.extend(
                f"  - {role}: {count}" for role, count in sorted(self.role_counts.items())
            )
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                suffix = f" [{finding.path}]" if finding.path else ""
                lines.append(f"  - {finding.severity}: {finding.code}{suffix}: {finding.message}")
        if self.next_actions:
            lines.append("next actions:")
            lines.extend(f"  - {action}" for action in self.next_actions)
        lines.append(f"claim boundary: {self.claim_boundary}")
        return "\n".join(lines)


def current_layout_manifest_text(
    root: str | Path | None = None, *, project_identity: str | None = None
) -> str:
    """Return the exact current manifest text for a direct manual rewrite.

    Supplying ``root`` emits the complete role-shape inventory for that
    target.  The rows contain only path, role, and entry kind; content
    currentness belongs to the owning model/validation route.  Omitting the
    root emits an empty deferred inventory for a brand-new scaffold.
    """

    root_path = Path(root).resolve() if root is not None else None
    flowguard_root = root_path / ".flowguard" if root_path is not None else None
    members, inventory_fingerprint, role_fingerprints = (
        _layout_inventory(flowguard_root)
        if flowguard_root is not None and flowguard_root.is_dir()
        else ((), _canonical_json_fingerprint([]), {})
    )
    identity = (
        str(project_identity)
        if project_identity is not None
        else (_project_identity(root_path) if root_path is not None else "")
    )
    identity_fingerprint = (
        _canonical_json_fingerprint({"project_identity": identity}) if identity else ""
    )
    authority_pointer, authority_fingerprint = (
        _model_authority_metadata(root_path) if root_path is not None else ("", "")
    )
    mode = "exact" if root_path is not None else "deferred"
    role_fingerprints = {
        role: role_fingerprints.get(role, _canonical_json_fingerprint([]))
        for role in sorted(CANONICAL_ROLE_ROOT_NAMES)
    }
    lines = [
        "[flowguard_layout]",
        f'schema = {json.dumps(PROJECT_LAYOUT_SCHEMA)}',
        f"version = {PROJECT_LAYOUT_VERSION}",
        'authority = "current"',
        'canonical_root = ".flowguard"',
        f'project_identity = {json.dumps(identity)}',
        f'project_identity_fingerprint = {json.dumps(identity_fingerprint)}',
        f'model_authority_pointer = {json.dumps(authority_pointer)}',
        f'model_authority_fingerprint = {json.dumps(authority_fingerprint)}',
        "non_authority_roots = " + json.dumps(sorted(NON_AUTHORITY_ROLES)),
        "",
        "[roots]",
    ]
    for name, role in CANONICAL_ROLE_ROOTS:
        lines.append(f'{name.replace("-", "_")} = "{name}"  # {role}')
    lines.extend(["", "[role_authority]"])
    for name, _role in CANONICAL_ROLE_ROOTS:
        state = "non_authority" if name in NON_AUTHORITY_ROLES else "current"
        lines.append(f'{name.replace("-", "_")} = "{state}"')
    lines.extend(
        [
            "",
            "[inventory]",
            f'schema = {json.dumps(PROJECT_LAYOUT_INVENTORY_SCHEMA)}',
            f'mode = {json.dumps(mode)}',
            f'fingerprint = {json.dumps(inventory_fingerprint)}',
            f"member_count = {len(members)}",
            "role_fingerprints = {"
            + ", ".join(
                f'{role} = {json.dumps(role_fingerprints[role])}'
                for role in sorted(role_fingerprints)
            )
            + "}",
        ]
    )
    if not members:
        # TOML needs an explicit empty array so the current parser can
        # distinguish an intentionally empty shape from an obsolete manifest
        # that omitted the inventory member field altogether.
        lines.append("members = []")
    for member in members:
        lines.extend(
            [
                "",
                "[[inventory.members]]",
                f'path = {json.dumps(member["path"])}',
                f'role = {json.dumps(member["role"])}',
                f'kind = {json.dumps(member["kind"])}',
            ]
        )
    return "\n".join(lines) + "\n"


def current_layout_readme_text() -> str:
    """Return the generated navigation note for a current target layout.

    The note is descriptive only.  It is never model, contract, receipt, or
    other authority, and editing it cannot make a stale layout current.
    """

    lines = [
        "# FlowGuard project control plane",
        "",
        "This directory is the current FlowGuard control plane. The folder name",
        "`software_dna`/`DNA` is intentionally not used: completion is a claim",
        "made from separate current evidence, not a directory containing it.",
        "",
        "| Folder | Meaning |",
        "| --- | --- |",
    ]
    for name, role in CANONICAL_ROLE_ROOTS:
        lines.append(f"| `{name}/` | {role.replace('_', ' ')} |")
    lines.extend(
        [
            "",
            "The six role folders are allowed destinations and are created only",
            "when an artifact owns that role; an empty project need not contain",
            "empty role folders. Required artifacts are checked by their native",
            "model/check owner, not by an empty-directory rule.",
            "",
            "`evidence/` is immutable proof and `history/` is provenance only.",
            "A controlled `work/flowguard/<task-id>/` workspace may remain during",
            "work, but it is excluded from layout/source/release authority and is",
            "only explicitly reclaimable. `models/authority/staging/` has the same",
            "candidate-only boundary; it cannot become current authority by naming",
            "alone. Do not hide arbitrary source files under a temporary-looking",
            "directory.",
            "",
            "This navigation file is not evidence and is not used to bypass any",
            "layout, model, receipt, consumer, or release gate.",
            "",
        ]
    )
    return "\n".join(lines)


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_json_fingerprint(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _project_identity(root_path: Path) -> str:
    """Return the stable local project identity without reading model authority."""

    manifest_path = root_path / ".flowguard" / "project.toml"
    try:
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        flowguard_section = payload.get("flowguard")
        if isinstance(flowguard_section, Mapping):
            repository = str(flowguard_section.get("repository", "")).strip()
            if repository:
                return repository
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        pass
    return root_path.name


def _model_authority_metadata(root_path: Path) -> tuple[str, str]:
    """Read only the pointer identity needed by the layout contract.

    The layout gate never validates or consumes the pointed-to model.  It only
    records the current pointer and a stable fingerprint of that pointer. The
    mutable snapshot/revision/head fields belong to the model-authority store;
    including them here would make every legitimate activation rewrite the
    layout and create a model/layout freshness cycle.
    """

    manifest_path = root_path / ".flowguard" / "project.toml"
    try:
        raw = manifest_path.read_bytes()
        payload = tomllib.loads(raw.decode("utf-8"))
        section = payload.get("model_authority")
        if not isinstance(section, Mapping):
            return "", ""
        pointer = ".flowguard/project.toml#model_authority"
        return pointer, _canonical_json_fingerprint({"pointer": pointer})
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return "", ""


def _layout_inventory(
    flowguard_root: Path,
    *,
    observation: LayoutObservation | None = None,
    metrics: InvocationMetrics | None = None,
) -> tuple[tuple[dict[str, str], ...], str, dict[str, str]]:
    """Build the current role *shape* inventory without reading member bytes.

    Control-plane files are governed by their own pointers and are not
    recursive role members.  The one guarded path observation is reused by the
    audit and inventory reconciliation, so layout work never hashes every
    evidence/report file merely to prove where it lives.
    """

    if not flowguard_root.is_dir():
        return (), _canonical_json_fingerprint([]), {}
    if observation is None:
        paths, traversal_findings = _walk_layout_entries(flowguard_root, metrics=metrics)
        observation = LayoutObservation(
            root=str(flowguard_root),
            paths=paths,
            traversal_findings=tuple(traversal_findings),
        )
    rows: list[dict[str, str]] = []
    observed_relative_paths = tuple(
        path.relative_to(flowguard_root).as_posix() for path in observation.paths
    )
    runtime_only_dirs = _runtime_only_layout_directories(observed_relative_paths)
    for path in observation.paths:
        rel = path.relative_to(flowguard_root).as_posix()
        # Known working artifacts are intentionally observed for diagnostics,
        # but never participate in current layout shape or role fingerprints.
        # This keeps a generated cache or candidate staging file from making
        # the current manifest stale while preserving every byte on disk.
        try:
            if (
                rel in runtime_only_dirs
                or is_non_authority_path(f".flowguard/{rel}")
                or _is_model_authority_control_plane_member(rel)
            ):
                continue
        except ValueError:
            # The guarded walker/inspector owns path-name safety findings.  Do
            # not silently classify an unsafe spelling as a working artifact.
            pass
        parts = Path(rel).parts
        if not parts or parts[0] not in CANONICAL_ROLE_ROOT_NAMES:
            continue
        role = parts[0]
        try:
            redirected = _path_is_reparse_or_symlink(path)
        except OSError:
            redirected = True
        if redirected:
            kind = "reparse"
        else:
            try:
                kind = "directory" if path.is_dir() else "file"
            except OSError:
                kind = "unreadable"
        rows.append({"path": rel, "role": role, "kind": kind})
        if metrics is not None:
            metrics.inc("shape_entries_observed")
    frozen_rows = tuple(sorted(rows, key=lambda row: row["path"]))
    role_fingerprints: dict[str, str] = {}
    for role in sorted(CANONICAL_ROLE_ROOT_NAMES):
        role_rows = [row for row in frozen_rows if row["role"] == role]
        role_fingerprints[role] = _canonical_json_fingerprint(role_rows)
    return frozen_rows, _canonical_json_fingerprint(frozen_rows), role_fingerprints


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _finding(
    code: str,
    *,
    path: str = "",
    message: str,
    recommendation: str,
    metadata: Mapping[str, Any] | None = None,
    severity: str = "blocked",
) -> ProjectLayoutFinding:
    return ProjectLayoutFinding(
        severity=severity,
        code=code,
        path=path,
        message=message,
        recommendation=recommendation,
        metadata=metadata or {},
    )


def _sha256_file(path: Path) -> str:
    """Hash one already-validated regular file without loading it in memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _model_snapshot_file_fingerprint(path: Path) -> str:
    """Return the identity used by a content-addressed model snapshot.

    Ordinary layout fixtures and legacy human-authored snapshots are validated
    by their raw file digest.  A current ``ModelSystemSnapshot`` is different:
    its filename and project pointer use the snapshot's canonical identity
    fingerprint, while pretty-printed JSON (and Windows line endings) are only
    its serialization.  Parse and validate that typed artifact when possible,
    falling back to the raw digest for non-model fixture files so the layout
    audit remains useful without becoming a second model-authority reader.
    """

    raw_fingerprint = _sha256_file(path)
    try:
        from .model_authority import ModelSystemSnapshot

        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshot = ModelSystemSnapshot.from_dict(payload)
    except (OSError, UnicodeError, TypeError, ValueError, KeyError):
        return raw_fingerprint
    return snapshot.fingerprint


def _normalize_relative_pointer(value: Any) -> str | None:
    """Normalize a manifest pointer while rejecting escapes and rooted paths."""

    raw = str(value or "").strip()
    posix = PurePosixPath(raw.replace("\\", "/"))
    windows = PureWindowsPath(raw)
    if (
        not raw
        or raw.startswith(("/", "\\"))
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
    ):
        return None
    return posix.as_posix()


def _light_project_control_plane_findings(
    root_path: Path,
    *,
    layout_header: Mapping[str, Any] | None = None,
) -> list[ProjectLayoutFinding]:
    """Apply the cheap project/adoption/sole-pointer gate.

    This deliberately validates only the identity-bearing control-plane
    records.  Full model semantics, accepted revision checks, and snapshot
    payload validation remain owned by ``model_authority_store``.  A newly
    adopted project may legitimately have no model authority yet; once an
    authority section is declared, its one content-addressed snapshot pointer
    and the adoption record become hard requirements.
    """

    findings: list[ProjectLayoutFinding] = []
    flowguard_root = root_path / ".flowguard"
    project_path = flowguard_root / "project.toml"
    project_rel = ".flowguard/project.toml"

    try:
        project_exists = project_path.exists() or project_path.is_symlink()
    except OSError as exc:
        findings.append(
            _finding(
                "layout_project_manifest_unreadable",
                path=project_rel,
                message=f"The current project manifest cannot be inspected safely: {exc}",
                recommendation="Repair the regular .flowguard/project.toml and rerun the audit; do not consult an alternate project record.",
            )
        )
        return findings
    if not project_exists:
        findings.append(
            _finding(
                "layout_project_manifest_missing",
                path=project_rel,
                message="The current .flowguard project manifest is missing.",
                recommendation="Create one current project.toml before using this layout as project or model authority; do not read a historical manifest.",
            )
        )
        return findings
    try:
        if _path_is_reparse_or_symlink(project_path):
            findings.append(
                _finding(
                    "layout_project_manifest_reparse_or_symlink",
                    path=project_rel,
                    message="The current project manifest is a symlink, junction, or other reparse point.",
                    recommendation="Replace it with one manually owned regular project.toml and rebuild the current project identity.",
                )
            )
            return findings
        if not project_path.is_file():
            findings.append(
                _finding(
                    "layout_project_manifest_not_file",
                    path=project_rel,
                    message="The current project manifest is not a regular file.",
                    recommendation="Replace it with one regular .flowguard/project.toml; do not use a directory or alternate path as project authority.",
                )
            )
            return findings
        project_payload = tomllib.loads(project_path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        findings.append(
            _finding(
                "layout_project_manifest_invalid",
                path=project_rel,
                message=f"The current project manifest cannot be parsed: {exc}",
                recommendation="Rewrite .flowguard/project.toml in the current direct format and rerun the audit.",
            )
        )
        return findings
    if not isinstance(project_payload, Mapping):
        findings.append(
            _finding(
                "layout_project_manifest_invalid",
                path=project_rel,
                message="The current project manifest must be a TOML table.",
                recommendation="Rewrite .flowguard/project.toml as a TOML table with flowguard and adoption policy records.",
            )
        )
        return findings

    flowguard_section = project_payload.get("flowguard")
    policy_section = project_payload.get("policy")
    authority_section = project_payload.get("model_authority")
    if not isinstance(flowguard_section, Mapping):
        findings.append(
            _finding(
                "layout_project_section_missing",
                path=project_rel,
                message="The current project manifest has no [flowguard] identity table.",
                recommendation="Rewrite the direct current project record with one [flowguard] table; do not infer identity from a fallback file.",
            )
        )
        flowguard_section = {}

    # A schema-only [flowguard] table is the existing lightweight scaffold
    # contract.  Full adoption records opt into the stricter project/policy
    # checks through an adopted version, a policy table, or model authority.
    adopted = bool(
        str(flowguard_section.get("adopted_package_version", "")).strip()
        or isinstance(policy_section, Mapping)
        or isinstance(authority_section, Mapping)
    )
    if adopted:
        missing_fields = sorted(
            field_name
            for field_name in _PROJECT_MANIFEST_REQUIRED_FIELDS
            if not isinstance(flowguard_section.get(field_name), str)
            or not str(flowguard_section.get(field_name)).strip()
        )
        if missing_fields:
            findings.append(
                _finding(
                    "layout_project_identity_incomplete",
                    path=project_rel,
                    message="The adopted project manifest is missing one or more required identity fields.",
                    recommendation="Restore the complete current project/adoption record before relying on this layout.",
                    metadata={"missing_fields": missing_fields},
                )
            )
        if not isinstance(policy_section, Mapping):
            findings.append(
                _finding(
                    "layout_adoption_policy_missing",
                    path=project_rel,
                    message="An adopted project must declare one [policy] table.",
                    recommendation="Restore the current adoption policy table; do not infer policy from an older manifest.",
                )
            )
        elif policy_section.get("require_adoption_log") is not True:
            findings.append(
                _finding(
                    "layout_adoption_policy_invalid",
                    path=project_rel,
                    message="The adopted project must explicitly require its current adoption log.",
                    recommendation="Set policy.require_adoption_log = true in the current project record.",
                    metadata={"observed": policy_section.get("require_adoption_log")},
                )
            )

    # Initial project adoption writes the log immediately after its post-write
    # layout audit.  That one bootstrap state has no model authority yet and
    # is therefore allowed to be temporarily log-less.  A minimal scaffold
    # still needs the log path, but its historical empty-file fixture remains
    # compatible.  A full adopted project becomes content-gated once it
    # exposes the sole model-authority section.
    bootstrap_without_authority = adopted and not isinstance(authority_section, Mapping)
    adoption_log_required = not bootstrap_without_authority
    adoption_log_content_required = adopted and isinstance(authority_section, Mapping)
    adoption_log_path = flowguard_root / "adoption_log.jsonl"
    adoption_log_rel = ".flowguard/adoption_log.jsonl"
    try:
        adoption_log_exists = adoption_log_path.exists() or adoption_log_path.is_symlink()
    except OSError as exc:
        findings.append(
            _finding(
                "layout_adoption_log_unreadable",
                path=adoption_log_rel,
                message=f"The current adoption log cannot be inspected safely: {exc}",
                recommendation="Repair the regular current adoption log and rerun the audit; do not consult a fallback log.",
            )
        )
        adoption_log_exists = False
    if not adoption_log_exists:
        if adoption_log_required:
            findings.append(
                _finding(
                    "layout_adoption_log_missing",
                    path=adoption_log_rel,
                    message="The current adoption log is missing.",
                    recommendation="Restore one current .flowguard/adoption_log.jsonl before claiming project currentness.",
                )
            )
    else:
        try:
            if _path_is_reparse_or_symlink(adoption_log_path):
                findings.append(
                    _finding(
                        "layout_adoption_log_reparse_or_symlink",
                        path=adoption_log_rel,
                        message="The current adoption log is a symlink, junction, or other reparse point.",
                        recommendation="Replace it with one manually owned regular adoption_log.jsonl; do not follow the redirected log.",
                    )
                )
            elif not adoption_log_path.is_file():
                findings.append(
                    _finding(
                        "layout_adoption_log_not_file",
                        path=adoption_log_rel,
                        message="The current adoption log is not a regular file.",
                        recommendation="Replace it with one regular .flowguard/adoption_log.jsonl; do not use a directory as the adoption record.",
                    )
                )
            elif adoption_log_content_required and adoption_log_path.stat().st_size == 0:
                findings.append(
                    _finding(
                        "layout_adoption_log_empty",
                        path=adoption_log_rel,
                        message="The adopted project adoption log is empty.",
                        recommendation="Append the current adoption record before relying on project currentness.",
                    )
                )
        except OSError as exc:
            findings.append(
                _finding(
                    "layout_adoption_log_unreadable",
                    path=adoption_log_rel,
                    message=f"The current adoption log cannot be inspected safely: {exc}",
                    recommendation="Repair the regular current adoption log and rerun the audit; do not consult a fallback log.",
                )
            )

    # The model authority section is optional during initial adoption, but
    # once present it must be the one exact current section and its declared
    # snapshot must be an in-root regular file with matching bytes.
    if authority_section is None:
        declared_pointer = ""
        if isinstance(layout_header, Mapping):
            declared_pointer = str(layout_header.get("model_authority_pointer", "")).strip()
        if declared_pointer:
            findings.append(
                _finding(
                    "layout_model_authority_missing",
                    path=project_rel,
                    message="The layout declares a model-authority pointer but project.toml has no sole [model_authority] section.",
                    recommendation="Restore one current model-authority section and rebuild the layout identity; do not follow a detached pointer.",
                )
            )
        return findings
    if not isinstance(authority_section, Mapping):
        findings.append(
            _finding(
                "layout_model_authority_schema_mismatch",
                path=project_rel,
                message="The sole model-authority record must be a TOML table.",
                recommendation="Rewrite one exact [model_authority] table in project.toml; do not add an alternate pointer section.",
            )
        )
        return findings
    observed_keys = {str(key) for key in authority_section}
    if observed_keys != _MODEL_AUTHORITY_REQUIRED_FIELDS:
        findings.append(
            _finding(
                "layout_model_authority_schema_mismatch",
                path=project_rel,
                message="The sole model-authority section has missing or alternate pointer fields.",
                recommendation="Keep exactly the current model-authority field set and rebuild its identity; do not retain a parallel pointer.",
                metadata={
                    "missing_fields": sorted(_MODEL_AUTHORITY_REQUIRED_FIELDS - observed_keys),
                    "unknown_fields": sorted(observed_keys - _MODEL_AUTHORITY_REQUIRED_FIELDS),
                },
            )
        )

    string_fields = _MODEL_AUTHORITY_REQUIRED_FIELDS - {"generation"}
    for field_name in sorted(string_fields):
        value = authority_section.get(field_name)
        if not isinstance(value, str) or (field_name != "previous_snapshot_fingerprint" and not value.strip()):
            findings.append(
                _finding(
                    "layout_model_authority_field_invalid",
                    path=project_rel,
                    message=f"model_authority.{field_name} must be a non-empty TOML string.",
                    recommendation="Restore the exact current model-authority field value and rebuild the pointer identity.",
                    metadata={"field": field_name},
                )
            )
    generation = authority_section.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
    ):
        findings.append(
            _finding(
                "layout_model_authority_field_invalid",
                path=project_rel,
                message="model_authority.generation must be a TOML integer.",
                recommendation="Restore the current integer generation in the sole model-authority section.",
                metadata={"field": "generation"},
            )
        )
    for field_name in (
        "observed_snapshot_fingerprint",
        "accepted_revision_set_fingerprint",
        "activation_receipt_fingerprint",
        "head_fingerprint",
    ):
        value = authority_section.get(field_name)
        if isinstance(value, str) and not _SHA256_FINGERPRINT_RE.fullmatch(value):
            findings.append(
                _finding(
                    "layout_model_authority_fingerprint_invalid",
                    path=project_rel,
                    message=f"model_authority.{field_name} is not a canonical sha256 fingerprint.",
                    recommendation="Rebuild the current model-authority identity from its accepted source and snapshot.",
                    metadata={"field": field_name},
                )
            )
    previous_fingerprint = authority_section.get("previous_snapshot_fingerprint")
    if isinstance(previous_fingerprint, str) and previous_fingerprint and not _SHA256_FINGERPRINT_RE.fullmatch(previous_fingerprint):
        findings.append(
            _finding(
                "layout_model_authority_fingerprint_invalid",
                path=project_rel,
                message="model_authority.previous_snapshot_fingerprint is not empty or a canonical sha256 fingerprint.",
                recommendation="Restore the predecessor snapshot fingerprint or explicitly use the empty bootstrap value.",
                metadata={"field": "previous_snapshot_fingerprint"},
            )
        )

    pointer_value = authority_section.get("observed_snapshot_path")
    normalized_pointer = _normalize_relative_pointer(pointer_value)
    if normalized_pointer is None:
        findings.append(
            _finding(
                "layout_model_authority_pointer_invalid",
                path=project_rel,
                message="The sole observed_snapshot_path must be repository-relative and cannot escape the project root.",
                recommendation="Rewrite the current relative snapshot pointer; absolute, rooted, and parent-traversing paths are blocked.",
            )
        )
        return findings
    pointer_classification = _layout_runtime_classification(normalized_pointer)
    if pointer_classification is not None:
        findings.append(
            _finding(
                "layout_model_authority_pointer_working_path",
                path=normalized_pointer,
                message="The current model-authority pointer cannot target a working, staged, cached, or opaque path.",
                recommendation="Point current authority only at the content-addressed snapshot under models/authority/snapshots; keep candidate/staging bytes non-authoritative.",
                metadata={"kind": pointer_classification.kind},
            )
        )
        return findings

    snapshot_path = root_path / Path(*PurePosixPath(normalized_pointer).parts)
    cursor = root_path
    path_safe = True
    for component in PurePosixPath(normalized_pointer).parts:
        cursor = cursor / component
        try:
            if (cursor.exists() or cursor.is_symlink()) and _path_is_reparse_or_symlink(cursor):
                findings.append(
                    _finding(
                        "layout_model_authority_snapshot_reparse_or_symlink",
                        path=normalized_pointer,
                        message="The sole model snapshot pointer traverses a symlink, junction, or other reparse point.",
                        recommendation="Replace every pointer path component with a manually owned regular path and rebuild the authority identity.",
                    )
                )
                path_safe = False
                break
        except OSError as exc:
            findings.append(
                _finding(
                    "layout_model_authority_snapshot_unreadable",
                    path=normalized_pointer,
                    message=f"The sole model snapshot path cannot be inspected safely: {exc}",
                    recommendation="Repair the current regular snapshot path and rerun the audit; do not consult an alternate snapshot.",
                )
            )
            path_safe = False
            break
    if not path_safe:
        return findings
    try:
        snapshot_exists = snapshot_path.exists() or snapshot_path.is_symlink()
        if not snapshot_exists:
            findings.append(
                _finding(
                    "layout_model_authority_snapshot_missing",
                    path=normalized_pointer,
                    message="The sole model snapshot pointer does not resolve to a current file.",
                    recommendation="Restore the exact content-addressed snapshot before relying on model authority.",
                )
            )
            return findings
        if _path_is_reparse_or_symlink(snapshot_path):
            findings.append(
                _finding(
                    "layout_model_authority_snapshot_reparse_or_symlink",
                    path=normalized_pointer,
                    message="The sole model snapshot is a symlink, junction, or other reparse point.",
                    recommendation="Replace it with the manually owned content-addressed snapshot; do not follow the redirected target.",
                )
            )
            return findings
        if not snapshot_path.is_file():
            findings.append(
                _finding(
                    "layout_model_authority_snapshot_not_file",
                    path=normalized_pointer,
                    message="The sole model snapshot pointer does not resolve to a regular file.",
                    recommendation="Restore one regular content-addressed snapshot file and rebuild the current authority identity.",
                )
            )
            return findings
        live_fingerprint = _model_snapshot_file_fingerprint(snapshot_path)
    except OSError as exc:
        findings.append(
            _finding(
                "layout_model_authority_snapshot_unreadable",
                path=normalized_pointer,
                message=f"The sole model snapshot cannot be read safely: {exc}",
                recommendation="Repair the current regular snapshot and rerun the audit; do not consult an alternate snapshot.",
            )
        )
        return findings
    declared_fingerprint = authority_section.get("observed_snapshot_fingerprint")
    if isinstance(declared_fingerprint, str) and _SHA256_FINGERPRINT_RE.fullmatch(declared_fingerprint):
        if live_fingerprint != declared_fingerprint:
            findings.append(
                _finding(
                    "layout_model_authority_snapshot_fingerprint_stale",
                    path=normalized_pointer,
                    message="The sole model snapshot bytes do not match observed_snapshot_fingerprint.",
                    recommendation="Rebuild the current model authority from the exact content-addressed snapshot; do not accept stale evidence.",
                    metadata={"expected": declared_fingerprint, "observed": live_fingerprint},
                )
            )
    return findings


def _parse_manifest(
    path: Path, *, root_path: Path | None = None
) -> tuple[dict[str, Any] | None, list[ProjectLayoutFinding]]:
    findings: list[ProjectLayoutFinding] = []
    try:
        if (path.exists() or path.is_symlink()) and _path_is_reparse_or_symlink(path):
            return None, [
                _finding(
                    "layout_reparse_or_symlink",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The current layout manifest is a symlink, junction, or other reparse point.",
                    recommendation="Replace it with one manually owned regular manifest and rebuild the layout identity.",
                )
            ]
    except OSError as exc:
        return None, [
            _finding(
                "layout_entry_unreadable",
                path=PROJECT_LAYOUT_MANIFEST,
                message=f"The current layout manifest identity cannot be inspected safely: {exc}",
                recommendation="Repair the regular manifest and rerun the audit; do not consult an alternate path.",
            )
        ]
    if not path.is_file():
        return None, [
            _finding(
                "layout_manifest_missing",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The current .flowguard layout manifest is missing.",
                recommendation="Manually reorganize the target into the current role roots and create a new layout.toml; do not reuse an old layout reader.",
            )
        ]
    try:
        raw = path.read_bytes()
        payload = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return None, [
            _finding(
                "layout_manifest_invalid",
                path=PROJECT_LAYOUT_MANIFEST,
                message=f"The current layout manifest cannot be parsed: {exc}",
                recommendation="Rewrite the manifest in the current schema and rerun this audit.",
            )
        ]
    if not isinstance(payload, dict):
        findings.append(
            _finding(
                "layout_manifest_invalid",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The layout manifest root must be a TOML table.",
                recommendation="Rewrite the manifest with [flowguard_layout] and [roots] tables.",
            )
        )
        return None, findings
    if root_path is not None:
        layout_header = payload.get("flowguard_layout")
        findings.extend(
            _light_project_control_plane_findings(
                root_path,
                layout_header=layout_header if isinstance(layout_header, Mapping) else None,
            )
        )
    expected_sections = {"flowguard_layout", "roots", "role_authority", "inventory"}
    if set(payload) != expected_sections:
        findings.append(
            _finding(
                "layout_manifest_unknown_section",
                path=PROJECT_LAYOUT_MANIFEST,
                message=f"Manifest sections must be exactly {sorted(expected_sections)}.",
                recommendation="Remove obsolete sections and manually rebuild the current manifest.",
                metadata={"observed_sections": sorted(payload)},
            )
        )
        return payload, findings
    header = payload.get("flowguard_layout")
    roots = payload.get("roots")
    role_authority = payload.get("role_authority")
    inventory = payload.get("inventory")
    if not all(
        isinstance(value, dict)
        for value in (header, roots, role_authority, inventory)
    ):
        findings.append(
            _finding(
                "layout_manifest_invalid",
                path=PROJECT_LAYOUT_MANIFEST,
                message="flowguard_layout, roots, role_authority, and inventory must be TOML tables.",
                recommendation="Rewrite the manifest with the current v2 table structure.",
            )
        )
        return payload, findings
    expected_header_keys = {
        "schema",
        "version",
        "authority",
        "canonical_root",
        "project_identity",
        "project_identity_fingerprint",
        "model_authority_pointer",
        "model_authority_fingerprint",
        "non_authority_roots",
    }
    if set(header) != expected_header_keys:
        findings.append(
            _finding(
                "layout_manifest_unknown_key",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The flowguard_layout table must contain the complete current identity contract.",
                recommendation="Remove the old keys and manually write the current schema.",
                metadata={"observed_keys": sorted(header)},
            )
        )
    expected_role_authority_keys = set(CANONICAL_ROLE_ROOT_NAMES)
    if set(role_authority) != expected_role_authority_keys:
        findings.append(
            _finding(
                "layout_manifest_role_authority_set_mismatch",
                path=PROJECT_LAYOUT_MANIFEST,
                message="Every current role needs exactly one explicit authority disposition.",
                recommendation="Rewrite role_authority with all nine role names and no aliases.",
                metadata={"expected": sorted(expected_role_authority_keys), "observed": sorted(role_authority)},
            )
        )
    expected_inventory_keys = {"schema", "mode", "fingerprint", "member_count", "role_fingerprints", "members"}
    if set(inventory) != expected_inventory_keys:
        findings.append(
            _finding(
                "layout_manifest_inventory_schema_mismatch",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The inventory table must contain schema, mode, member count, fingerprints, and members.",
                recommendation="Rebuild the current role-member inventory directly from the target tree.",
                metadata={"expected": sorted(expected_inventory_keys), "observed": sorted(inventory)},
            )
        )
    expected_root_keys = {name.replace("-", "_") for name in CANONICAL_ROLE_ROOT_NAMES}
    if set(roots) != expected_root_keys:
        findings.append(
            _finding(
                "layout_manifest_root_set_mismatch",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The manifest must declare every current role root exactly once.",
                recommendation="Manually rebuild the role map; do not infer missing roots from old directories.",
                metadata={"expected": sorted(expected_root_keys), "observed": sorted(roots)},
            )
        )
    declared_paths: dict[str, list[str]] = {}
    for role_key, declared_path in roots.items():
        if isinstance(declared_path, str):
            declared_paths.setdefault(declared_path.casefold(), []).append(role_key)
    duplicate_paths = {
        path: tuple(sorted(role_keys))
        for path, role_keys in sorted(declared_paths.items())
        if len(role_keys) > 1
    }
    if duplicate_paths:
        findings.append(
            _finding(
                "layout_manifest_duplicate_role",
                path=PROJECT_LAYOUT_MANIFEST,
                message="Two or more current roles resolve to the same directory identity.",
                recommendation="Assign every current role one distinct canonical root and rebuild affected identities; do not share or alias roots.",
                metadata={"duplicates": duplicate_paths},
            )
        )
    if header.get("schema") != PROJECT_LAYOUT_SCHEMA:
        findings.append(
            _finding(
                "layout_manifest_schema_stale",
                path=PROJECT_LAYOUT_MANIFEST,
                message=f"Layout schema must be {PROJECT_LAYOUT_SCHEMA}.",
                recommendation="Rewrite the manifest against the current FlowGuard layout schema.",
            )
        )
    if header.get("version") != PROJECT_LAYOUT_VERSION:
        findings.append(
            _finding(
                "layout_manifest_version_stale",
                path=PROJECT_LAYOUT_MANIFEST,
                message=f"Layout version must be {PROJECT_LAYOUT_VERSION}.",
                recommendation="Perform a direct manual layout upgrade and create a new current manifest.",
                metadata={"observed_version": header.get("version")},
            )
        )
    if header.get("authority") != "current" or header.get("canonical_root") != ".flowguard":
        findings.append(
            _finding(
                "layout_manifest_not_current",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The manifest is not marked as the sole current .flowguard layout authority.",
                recommendation="Create one current manifest; do not retain a parallel or fallback layout authority.",
            )
        )
    expected_values = {name.replace("-", "_"): name for name in CANONICAL_ROLE_ROOT_NAMES}
    for key, expected in sorted(expected_values.items()):
        if roots.get(key) != expected:
            findings.append(
                _finding(
                    "layout_manifest_root_identity_mismatch",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message=f"Role {key} must point to .flowguard/{expected}.",
                    recommendation="Repair the root mapping manually and regenerate all affected current identities.",
                    metadata={"role": key, "expected": expected, "observed": roots.get(key)},
                )
            )
    if header.get("authority") != "current" or header.get("canonical_root") != ".flowguard":
        findings.append(
            _finding(
                "layout_manifest_not_current",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The manifest is not marked as the sole current .flowguard layout authority.",
                recommendation="Create one current manifest; do not retain a parallel or fallback layout authority.",
            )
        )
    if root_path is not None:
        expected_identity = _project_identity(root_path)
        if header.get("project_identity") != expected_identity:
            findings.append(
                _finding(
                    "layout_project_identity_mismatch",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The layout project identity does not match the current project manifest/root identity.",
                    recommendation="Rewrite the current layout identity and rebuild affected model, test, installation, and receipt identities.",
                    metadata={"expected": expected_identity, "observed": header.get("project_identity")},
                )
            )
        expected_identity_fingerprint = _canonical_json_fingerprint({"project_identity": expected_identity})
        if header.get("project_identity_fingerprint") != expected_identity_fingerprint:
            findings.append(
                _finding(
                    "layout_project_identity_fingerprint_stale",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The project identity fingerprint is stale or forged.",
                    recommendation="Rebuild the current layout identity directly from the current project root.",
                )
            )
        expected_pointer, expected_pointer_fingerprint = _model_authority_metadata(root_path)
        if header.get("model_authority_pointer", "") != expected_pointer or header.get("model_authority_fingerprint", "") != expected_pointer_fingerprint:
            findings.append(
                _finding(
                    "layout_model_authority_pointer_stale",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The layout model-authority pointer identity no longer matches the current project manifest.",
                    recommendation="Rebuild the current layout and model-authority identities together; do not read the old pointer.",
                    metadata={"expected_pointer": expected_pointer, "observed_pointer": header.get("model_authority_pointer", "")},
                )
            )
    expected_non_authority = sorted(NON_AUTHORITY_ROLES)
    if sorted(header.get("non_authority_roots", [])) != expected_non_authority:
        findings.append(
            _finding(
                "layout_non_authority_declaration_mismatch",
                path=PROJECT_LAYOUT_MANIFEST,
                message="History, work, audits, and projections must be explicitly declared non-authority roots.",
                recommendation="Rewrite the current role authority declarations; do not use these roots as fallback authority.",
            )
        )
    for role in sorted(CANONICAL_ROLE_ROOT_NAMES):
        expected_state = "non_authority" if role in NON_AUTHORITY_ROLES else "current"
        if role_authority.get(role) != expected_state:
            findings.append(
                _finding(
                    "layout_role_authority_mismatch",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message=f"Role {role} must be declared {expected_state}.",
                    recommendation="Rewrite the role authority table and rebuild affected identities.",
                    metadata={"role": role, "expected": expected_state, "observed": role_authority.get(role)},
                )
            )
    if inventory.get("schema") != PROJECT_LAYOUT_INVENTORY_SCHEMA:
        findings.append(
            _finding(
                "layout_inventory_schema_stale",
                path=PROJECT_LAYOUT_MANIFEST,
                message=f"Inventory schema must be {PROJECT_LAYOUT_INVENTORY_SCHEMA}.",
                recommendation="Rebuild the current member inventory directly; no historical inventory reader exists.",
            )
        )
    if inventory.get("mode") not in {"exact", "deferred"}:
        findings.append(
            _finding(
                "layout_inventory_mode_invalid",
                path=PROJECT_LAYOUT_MANIFEST,
                message="Inventory mode must be exact or deferred.",
                recommendation="Rewrite the inventory in the current direct format.",
            )
        )
    return payload, findings


def _component_is_retired(component: str) -> bool:
    return component.casefold() in RETIRED_LAYOUT_COMPONENTS


def _path_is_reparse_or_symlink(path: Path) -> bool:
    """Return whether ``path`` can redirect traversal outside its owned role.

    ``Path.is_symlink()`` is not sufficient on Windows because directory
    junctions are reparse points without necessarily presenting as ordinary
    symbolic links.  ``lstat`` keeps this check read-only and inspects the link
    itself rather than its target.
    """

    if path.is_symlink():
        return True
    attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & reparse_mask)


def _layout_runtime_classification(relative: str):
    """Classify one path relative to ``.flowguard`` without hiding bad names."""

    try:
        return classify_runtime_artifact(
            relative
            if relative.replace("\\", "/").startswith(".flowguard/")
            else f".flowguard/{relative}"
        )
    except ValueError:
        return None


def _is_non_authority_layout_member(relative: str) -> bool:
    classification = _layout_runtime_classification(relative)
    return classification is not None and classification.non_authority


def _is_model_authority_control_plane_member(relative: str) -> bool:
    """Return whether a generated authority payload is governed by its pointer.

    Snapshot, revision, activation, bootstrap, and rollback bytes are
    content-addressed control-plane outputs. Their own authority store and
    the release-tree owner validate the exact pointed-to paths; they are not
    executable layout members. Keeping these payload names out of the shape
    inventory prevents every legitimate model activation from invalidating
    the layout and then recursively invalidating the model identity again.
    ``models/authority`` itself remains a current structural member, and
    ``staging`` continues to use the explicit non-authority/runtime boundary.
    """

    parts = PurePosixPath(str(relative).replace("\\", "/")).parts
    return (
        len(parts) >= 3
        and parts[0] == "models"
        and parts[1] == "authority"
        and parts[2]
        in {
            "snapshots", "revisions", "activations", "bootstraps", "rollbacks",
            "rollback-contracts", "boundary-contracts",
        }
    )


def _runtime_only_layout_directories(relative_paths: Iterable[str]) -> frozenset[str]:
    """Find structural parents created solely for a known working root.

    ``models/authority`` is a legitimate current directory when it contains
    snapshots/revisions, but it should not appear in the shape merely because
    an otherwise empty authority tree contains ``staging/``.  The parent is
    excluded only when every observed descendant is already classified as
    non-authority material.
    """

    normalized = tuple(
        str(relative).replace("\\", "/").rstrip("/")
        for relative in relative_paths
        if str(relative)
    )
    candidates = {"models/authority"}
    return frozenset(
        candidate
        for candidate in candidates
        if candidate in normalized
        and any(item.startswith(candidate + "/") for item in normalized)
        and all(
            _is_non_authority_layout_member(item)
            for item in normalized
            if item.startswith(candidate + "/")
        )
    )


def _walk_layout_entries(
    flowguard_root: Path,
    *,
    metrics: InvocationMetrics | None = None,
) -> tuple[tuple[Path, ...], list[ProjectLayoutFinding]]:
    """Collect entries deterministically without following redirected roots."""

    if metrics is not None:
        metrics.inc("directory_walk_count")
    entries: list[Path] = []
    findings: list[ProjectLayoutFinding] = []
    pending: list[Path] = [flowguard_root]
    while pending:
        parent = pending.pop()
        if parent != flowguard_root:
            try:
                parent_rel = _relative(parent, flowguard_root)
                parent_role = Path(parent_rel).parts[0] if parent_rel else ""
            except Exception:
                parent_role = ""
            if parent_role in OPAQUE_ROLE_ROOTS:
                # Evidence and history are non-authority payload containers.
                # Do not enumerate their children: adding a receipt, report,
                # quarantine item, or historical directory must not invalidate
                # the lightweight layout shape.  Their own lifecycle/audit
                # owners remain responsible for pointer and payload checks.
                continue
        try:
            children = sorted(
                parent.iterdir(),
                key=lambda child: (child.name.casefold(), child.name),
            )
        except OSError as exc:
            rel = ".flowguard" if parent == flowguard_root else _relative(parent, flowguard_root)
            findings.append(
                _finding(
                    "layout_entry_unreadable",
                    path=rel,
                    message=f"The layout entry cannot be inspected safely: {exc}",
                    recommendation="Repair the current regular path and rerun the audit; do not consult an alternate layout root.",
                )
            )
            continue

        child_directories: list[Path] = []
        for child in children:
            entries.append(child)
            if metrics is not None:
                metrics.inc("entries_observed")
            try:
                redirected = _path_is_reparse_or_symlink(child)
            except OSError as exc:
                findings.append(
                    _finding(
                        "layout_entry_unreadable",
                        path=_relative(child, flowguard_root),
                        message=f"The layout entry identity cannot be inspected safely: {exc}",
                        recommendation="Repair the current regular path and rerun the audit; do not consult an alternate layout root.",
                    )
                )
                continue
            if redirected:
                # The entry itself remains in the denominator and is reported
                # by _inspect_entries, but its target is never traversed.
                continue
            try:
                if child.is_dir():
                    child_directories.append(child)
                elif metrics is not None:
                    metrics.inc("files_observed")
            except OSError as exc:
                findings.append(
                    _finding(
                        "layout_entry_unreadable",
                        path=_relative(child, flowguard_root),
                        message=f"The layout entry type cannot be inspected safely: {exc}",
                        recommendation="Repair the current regular path and rerun the audit; do not consult an alternate layout root.",
                    )
                )
        pending.extend(reversed(child_directories))

    return (
        tuple(sorted(entries, key=lambda path: _relative(path, flowguard_root))),
        findings,
    )


def _inspect_entries(
    flowguard_root: Path,
    *,
    observation: LayoutObservation | None = None,
    metrics: InvocationMetrics | None = None,
) -> tuple[tuple[str, ...], dict[str, int], list[ProjectLayoutFinding]]:
    entries: list[str] = []
    role_counts: dict[str, int] = {}
    findings: list[ProjectLayoutFinding] = []
    try:
        root_exists = flowguard_root.exists() or flowguard_root.is_symlink()
    except OSError as exc:
        return (), {}, [
            _finding(
                "layout_entry_unreadable",
                path=".flowguard",
                message=f"The .flowguard root identity cannot be inspected safely: {exc}",
                recommendation="Repair the current regular directory and rerun the audit; do not consult an alternate root.",
            )
        ]
    if not root_exists:
        return (), {}, [
            _finding(
                "flowguard_directory_missing",
                message="The target has no .flowguard directory.",
                recommendation="Adopt FlowGuard first; this audit never creates a project control plane.",
            )
        ]
    try:
        if _path_is_reparse_or_symlink(flowguard_root):
            return (), {}, [
                _finding(
                    "layout_reparse_or_symlink",
                    path=".flowguard",
                    message="The .flowguard root is a symlink, junction, or other reparse point.",
                    recommendation="Replace it with one manually owned regular directory and rebuild all current layout identities.",
                )
            ]
    except OSError as exc:
        return (), {}, [
            _finding(
                "layout_entry_unreadable",
                path=".flowguard",
                message=f"The .flowguard root identity cannot be inspected safely: {exc}",
                recommendation="Repair the current regular directory and rerun the audit; do not consult an alternate root.",
            )
        ]
    if not flowguard_root.is_dir():
        return (), {}, [
            _finding(
                "flowguard_directory_not_directory",
                path=".flowguard",
                message="The .flowguard control-plane root is not a regular directory.",
                recommendation="Create one manually owned regular .flowguard directory; do not read an alternate path.",
            )
        ]

    # Role roots are semantic destinations, not a mandatory set of empty
    # directories.  A current project may materialize only the roots that own
    # an artifact; the owning model/check gate remains responsible for proving
    # required files.  This keeps adoption and light preflight cheap without
    # weakening path safety for roots that are present.
    for root_name, role in CANONICAL_ROLE_ROOTS:
        role_root = flowguard_root / root_name
        try:
            if role_root.exists() or role_root.is_symlink():
                if not _path_is_reparse_or_symlink(role_root) and not role_root.is_dir():
                    findings.append(
                        _finding(
                            "canonical_role_root_not_directory",
                            path=root_name,
                            message=f"Current role root '{root_name}' is not a regular directory.",
                            recommendation="Replace it with the exact regular role directory and rebuild affected identities.",
                            metadata={"role": role},
                        )
                    )
            # A missing root is valid when no current artifact owns that role.
            # Do not create it here and do not consult an older destination.
        except OSError as exc:
            findings.append(
                _finding(
                    "layout_entry_unreadable",
                    path=root_name,
                    message=f"Required role root '{root_name}' cannot be inspected safely: {exc}",
                    recommendation="Repair the current regular path and rerun the audit; do not consult an alternate root.",
                    metadata={"role": role},
                )
            )

    if observation is None:
        paths, traversal_findings = _walk_layout_entries(flowguard_root, metrics=metrics)
    else:
        paths, traversal_findings = observation.paths, list(observation.traversal_findings)
    findings.extend(traversal_findings)
    runtime_paths: list[str] = []
    runtime_kinds: dict[str, int] = {}
    runtime_only_dirs = _runtime_only_layout_directories(
        tuple(path.relative_to(flowguard_root).as_posix() for path in paths)
    )
    for path in paths:
        rel = _relative(path, flowguard_root)
        try:
            redirected = _path_is_reparse_or_symlink(path)
        except OSError:
            # _walk_layout_entries already emitted a blocking unreadable row.
            redirected = False
        try:
            is_directory = False if redirected else path.is_dir()
        except OSError:
            # _walk_layout_entries already emitted a blocking unreadable row.
            is_directory = False
        entries.append(rel + ("/" if is_directory else ""))
        if redirected:
            findings.append(
                _finding(
                    "layout_reparse_or_symlink",
                    path=rel,
                    message="Symlinks, junctions, and other reparse-point entries cannot define current authority.",
                    recommendation="Replace the link with a manually owned regular path and rebuild affected identities.",
                )
            )
        path_name_safe = all(
            _SAFE_COMPONENT_RE.fullmatch(component)
            for component in Path(rel).parts
        )
        if not path_name_safe:
            findings.append(
                _finding(
                    "layout_path_name_invalid",
                    path=rel,
                    message="A layout path contains a name outside the current portable naming grammar.",
                    recommendation="Rename the path manually and rebuild the affected current manifest/identities.",
                )
            )
        # Path safety is checked before classification.  In particular, a
        # reparse point named ``__pycache__`` is still a hard blocker and is
        # never made harmless by the runtime-artifact filter.
        classification = (
            None if redirected or not path_name_safe else _layout_runtime_classification(rel)
        )
        if classification is not None:
            # Evidence/history roots are already intentionally opaque and
            # have long-standing zero-finding semantics.  Only working/cache
            # observations need the aggregated informational reminder.
            if classification.kind not in {"opaque_evidence", "opaque_history"}:
                runtime_paths.append(rel)
                runtime_kinds[classification.kind] = (
                    runtime_kinds.get(classification.kind, 0) + 1
                )
            if is_governed_source_in_runtime_cache(f".flowguard/{rel}"):
                findings.append(
                    _finding(
                        "layout_runtime_governed_source",
                        path=rel,
                        message="A source-like .py/.json/.toml file cannot be hidden inside a Python runtime cache.",
                        recommendation="Classify the file under its owning current role or keep only generated cache bytes; do not use a runtime directory to bypass governance.",
                        metadata={"kind": classification.kind},
                    )
                )
            # Known runtime/staging/evidence paths are not current layout
            # members.  The single aggregated informational finding below is
            # the only reminder; no cleanup is performed by an audit.
            continue
        for component in Path(rel).parts:
            if _component_is_retired(component):
                findings.append(
                    _finding(
                        "retired_layout_name",
                        path=rel,
                        message=f"Retired or ambiguous layout component '{component}' is present.",
                        recommendation="Move the material manually to one current role or record an explicit retirement/history disposition; no fallback reader exists.",
                        metadata={"component": component},
                    )
                )
            if component.casefold() in {
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                ".tox",
                ".nox",
                ".hypothesis",
                "cache",
                "caches",
            }:
                findings.append(
                    _finding(
                        "layout_tool_cache",
                        path=rel,
                        message=f"Tool cache or bytecode directory '{component}' cannot be part of the current layout.",
                        recommendation="Classify the material under a current role or record an explicit retirement/history disposition; audit does not delete or relocate working bytes.",
                        metadata={"component": component},
                    )
                )
        first = Path(rel).parts[0] if Path(rel).parts else ""
        if first in CANONICAL_ROLE_ROOT_NAMES:
            role = dict(CANONICAL_ROLE_ROOTS)[first]
            if rel not in runtime_only_dirs and not _is_non_authority_layout_member(rel):
                role_counts[role] = role_counts.get(role, 0) + 1
            name_lower = Path(rel).name.casefold()
            if first == "evidence" and len(Path(rel).parts) == 2 and (
                name_lower in {"model.py", "model.toml", "model-authority.json", "model-system.json"}
            ):
                findings.append(
                    _finding(
                        "layout_role_authority_mismatch",
                        path=rel,
                        message="A model/authority-looking artifact is under the evidence role.",
                        recommendation="Place current model authority under models and keep evidence as immutable proof only; rebuild affected identities.",
                        metadata={"role": first},
                    )
                )
            if first == "models" and len(Path(rel).parts) == 2 and (
                name_lower.startswith("receipt") or name_lower.endswith("-evidence.json")
            ):
                findings.append(
                    _finding(
                        "layout_role_authority_mismatch",
                        path=rel,
                        message="A receipt/evidence-looking artifact is under the models role.",
                        recommendation="Place immutable proof under evidence and rebuild affected identities; do not let it become model authority.",
                        metadata={"role": first},
                    )
                )
            if first == "structure" and len(Path(rel).parts) >= 3 and Path(rel).parts[1] == "owners":
                owner = Path(rel).parts[2]
                if not _OWNER_ID_RE.fullmatch(owner):
                    findings.append(
                        _finding(
                            "owner_path_invalid",
                            path=rel,
                            message="Owner directories under structure/owners must use a stable lowercase owner id.",
                            recommendation="Rename the owner path manually and rebind its contracts/tests/evidence.",
                        )
                    )
        elif rel in CANONICAL_FILES:
            role_counts[CANONICAL_FILES[rel]] = role_counts.get(CANONICAL_FILES[rel], 0) + 1
        else:
            # Every direct child must be a declared role root or canonical file.
            # Nested content is allowed only below a declared role root.
            if len(Path(rel).parts) == 1:
                findings.append(
                    _finding(
                        "unregistered_layout_entry",
                        path=rel,
                        message="This top-level .flowguard entry has no declared current role.",
                        recommendation="Place it under one current role root or give it an explicit historical/retired disposition before continuing.",
                    )
                )
    if runtime_paths:
        findings.append(
            _finding(
                "layout_runtime_artifact",
                message=(
                    "Known working/runtime artifacts are preserved on disk but "
                    "excluded from current layout identity, source identity, and release projection."
                ),
                recommendation=(
                    "No cleanup is required for layout currentness; reclaim these bytes only through an explicit, separately authorized cleanup."
                ),
                severity="info",
                metadata={
                    "kinds": dict(sorted(runtime_kinds.items())),
                    "paths": tuple(sorted(runtime_paths)),
                    "count": len(runtime_paths),
                },
            )
        )
    # Detect direct files under .flowguard that are old owner/model/check material.
    for path in (entry for entry in paths if entry.parent == flowguard_root):
        if path.name in CANONICAL_FILES or path.name in CANONICAL_ROLE_ROOT_NAMES:
            continue
        try:
            if _path_is_reparse_or_symlink(path):
                continue
            is_file = path.is_file()
        except OSError:
            # A blocking unreadable row was already emitted above.
            continue
        if is_file:
            findings.append(
                _finding(
                    "legacy_flat_artifact",
                    path=path.name,
                    message="A direct .flowguard file is not one of the three current control-plane records.",
                    recommendation="Assign it to behavior/models/structure/verification/evidence/history manually (audits and projections belong under their owning evidence/structure path, transient work stays outside .flowguard); do not keep a flat compatibility path.",
                )
            )
    return tuple(entries), role_counts, findings


def _inventory_findings(
    *,
    root_path: Path,
    flowguard_root: Path,
    manifest: Mapping[str, Any] | None,
    observation: LayoutObservation | None = None,
    metrics: InvocationMetrics | None = None,
) -> tuple[str, list[ProjectLayoutFinding]]:
    """Reconcile the declared shape rows with the current tree."""

    if not isinstance(manifest, Mapping):
        return "", []
    inventory = manifest.get("inventory")
    if not isinstance(inventory, Mapping):
        return "", []
    actual_members, actual_fingerprint, actual_role_fingerprints = _layout_inventory(
        flowguard_root, observation=observation, metrics=metrics
    )
    findings: list[ProjectLayoutFinding] = []
    raw_members = inventory.get("members")
    members: list[dict[str, str]] = []
    if isinstance(raw_members, list):
        for index, member in enumerate(raw_members):
            if not isinstance(member, Mapping):
                findings.append(
                    _finding(
                        "layout_inventory_member_invalid",
                        path=PROJECT_LAYOUT_MANIFEST,
                        message=f"Inventory member {index} is not a table.",
                        recommendation="Rebuild the exact current role-member inventory directly from disk.",
                    )
                )
                continue
            if set(member) != {"path", "role", "kind"}:
                findings.append(
                    _finding(
                        "layout_inventory_member_schema_mismatch",
                        path=PROJECT_LAYOUT_MANIFEST,
                        message=f"Inventory member {index} has obsolete or missing keys.",
                        recommendation="Rebuild the shape inventory using path, role, and kind only.",
                        metadata={"observed_keys": sorted(member)},
                    )
                )
                continue
            members.append(
                {
                    "path": str(member.get("path", "")),
                    "role": str(member.get("role", "")),
                    "kind": str(member.get("kind", "")),
                }
            )
    else:
        findings.append(
            _finding(
                "layout_inventory_members_missing",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The current inventory has no members array.",
                recommendation="Rebuild the current manifest with an exact role-member inventory.",
            )
        )
    # Older manifests may have been generated before working-artifact
    # exclusion was introduced.  Treat only the explicitly recognized runtime
    # roots/files as non-authority on both sides of reconciliation; arbitrary
    # ``tmp``/``stage``-looking names remain governed members and are never
    # hidden by this compatibility projection.
    declared_members = tuple(
        sorted(
            (row for row in members if not _is_non_authority_layout_member(row["path"])),
            key=lambda row: row["path"],
        )
    )
    declared_role_fingerprints = {
        role: _canonical_json_fingerprint(
            [row for row in declared_members if row["role"] == role]
        )
        for role in sorted(CANONICAL_ROLE_ROOT_NAMES)
    }
    declared_inventory_fingerprint = _canonical_json_fingerprint(declared_members)
    actual_members = tuple(sorted(actual_members, key=lambda row: row["path"]))
    declared_by_case: dict[str, list[str]] = {}
    for row in declared_members:
        declared_by_case.setdefault(row["path"].casefold(), []).append(row["path"])
    path_collisions = {
        key: tuple(sorted(values))
        for key, values in declared_by_case.items()
        if len(values) > 1
    }
    if path_collisions:
        findings.append(
            _finding(
                "layout_inventory_path_collision",
                path=PROJECT_LAYOUT_MANIFEST,
                message="The inventory declares multiple current members for one path identity.",
                recommendation="Keep one canonical path per current role and rebuild all affected identities.",
                metadata={"collisions": path_collisions},
            )
        )
    role_by_path = {row["path"]: row["role"] for row in declared_members}
    for row in declared_members:
        first = Path(row["path"]).parts[0] if Path(row["path"]).parts else ""
        if first != row["role"]:
            findings.append(
                _finding(
                    "layout_inventory_role_mismatch",
                    path=row["path"],
                    message="An inventory member is assigned to a role different from its canonical root.",
                    recommendation="Rewrite the member row with the exact current role root; do not alias it.",
                    metadata={"expected_role": first, "observed_role": row["role"]},
                )
            )
    if inventory.get("mode") == "deferred":
        non_root_members = [
            row for row in actual_members if len(Path(row["path"]).parts) > 1
        ]
        if non_root_members:
            findings.append(
                _finding(
                    "layout_inventory_deferred_with_members",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="A deferred scaffold inventory cannot govern a populated current project.",
                    recommendation="Directly regenerate the exact member inventory before reading model, test, or evidence authority.",
                    metadata={"extra_member_count": len(non_root_members)},
                )
            )
    elif inventory.get("mode") == "exact":
        if declared_members != actual_members:
            declared_paths = {row["path"] for row in declared_members}
            actual_paths = {row["path"] for row in actual_members}
            findings.append(
                _finding(
                    "layout_inventory_conservation_mismatch",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The current shape inventory does not equal the observed role-member set.",
                    recommendation="Rebuild the current layout manifest directly from the current tree; old receipts become stale.",
                    metadata={
                        "missing_members": sorted(actual_paths - declared_paths),
                        "extra_members": sorted(declared_paths - actual_paths),
                    },
                )
            )
        if declared_inventory_fingerprint != actual_fingerprint:
            findings.append(
                _finding(
                    "layout_inventory_fingerprint_stale",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The declared role-member inventory fingerprint is stale.",
                    recommendation="Regenerate the current inventory and rebuild affected identities.",
                    metadata={
                        "expected": actual_fingerprint,
                        "observed": inventory.get("fingerprint"),
                        "normalized_observed": declared_inventory_fingerprint,
                    },
                )
            )
        if len(declared_members) != len(actual_members):
            findings.append(
                _finding(
                    "layout_inventory_count_mismatch",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="The declared inventory member count is stale.",
                    recommendation="Regenerate the current inventory before continuing.",
                    metadata={
                        "expected": len(actual_members),
                        "observed": inventory.get("member_count"),
                        "normalized_observed": len(declared_members),
                    },
                )
            )
        declared_roles = inventory.get("role_fingerprints")
        if not isinstance(declared_roles, Mapping) or declared_role_fingerprints != actual_role_fingerprints:
            findings.append(
                _finding(
                    "layout_role_fingerprint_stale",
                    path=PROJECT_LAYOUT_MANIFEST,
                    message="One or more current role fingerprints are stale.",
                    recommendation="Regenerate the direct current role inventory and rebuild affected model/test/receipt identities.",
                    metadata={
                        "expected": actual_role_fingerprints,
                        "observed": dict(declared_roles or {}),
                        "normalized_observed": declared_role_fingerprints,
                    },
                )
            )
    return actual_fingerprint, findings


def audit_project_layout(
    root: str | Path = ".",
    *,
    metrics: InvocationMetrics | None = None,
) -> ProjectLayoutReport:
    """Audit one target project's current ``.flowguard`` layout read-only."""

    metrics = metrics or InvocationMetrics()
    root_path = Path(root).resolve()
    flowguard_root = root_path / ".flowguard"
    manifest_path = flowguard_root / "layout.toml"
    with metrics.phase("layout_manifest_parse"):
        _manifest, manifest_findings = _parse_manifest(manifest_path, root_path=root_path)
    manifest_fingerprint = ""
    if _manifest is not None:
        try:
            manifest_bytes = manifest_path.read_bytes()
            metrics.inc("content_hash_read_count")
            metrics.inc("content_bytes_hashed", len(manifest_bytes))
            manifest_fingerprint = _sha256_bytes(manifest_bytes)
        except OSError:
            manifest_fingerprint = ""
    observation = LayoutObservation(root=str(flowguard_root))
    try:
        if flowguard_root.is_dir() and not _path_is_reparse_or_symlink(flowguard_root):
            paths, traversal_findings = _walk_layout_entries(
                flowguard_root, metrics=metrics
            )
            observation = LayoutObservation(
                root=str(flowguard_root),
                paths=paths,
                traversal_findings=tuple(traversal_findings),
            )
    except OSError:
        # _inspect_entries emits the authoritative unreadable/reparse finding.
        observation = LayoutObservation(root=str(flowguard_root))
    with metrics.phase("layout_shape_inspection"):
        entries, role_counts, entry_findings = _inspect_entries(
            flowguard_root, observation=observation, metrics=metrics
        )
    with metrics.phase("layout_shape_reconciliation"):
        inventory_fingerprint, inventory_findings = _inventory_findings(
            root_path=root_path,
            flowguard_root=flowguard_root,
            manifest=_manifest,
            observation=observation,
            metrics=metrics,
        )
    findings = tuple(
        sorted(
            (*manifest_findings, *entry_findings, *inventory_findings),
            key=lambda finding: (finding.severity, finding.code, finding.path),
        )
    )
    status = "blocked" if any(finding.severity == "blocked" for finding in findings) else "pass"
    layout_version: int | None = None
    if _manifest and isinstance(_manifest.get("flowguard_layout"), Mapping):
        value = _manifest["flowguard_layout"].get("version")
        if isinstance(value, int) and not isinstance(value, bool):
            layout_version = value
    return ProjectLayoutReport(
        root=str(root_path),
        flowguard_root=str(flowguard_root),
        status=status,
        layout_version=layout_version,
        manifest_fingerprint=manifest_fingerprint,
        project_identity=_project_identity(root_path),
        inventory_fingerprint=inventory_fingerprint,
        observed_entries=entries,
        role_counts=role_counts,
        findings=findings,
        metrics=metrics.snapshot(),
    )


__all__ = [
    "CANONICAL_FILES",
    "CANONICAL_ROLE_ROOTS",
    "PROJECT_LAYOUT_CLAIM_BOUNDARY",
    "PROJECT_LAYOUT_MANIFEST",
    "PROJECT_LAYOUT_SCHEMA",
    "PROJECT_LAYOUT_VERSION",
    "LayoutObservation",
    "ProjectLayoutFinding",
    "ProjectLayoutReport",
    "audit_project_layout",
    "current_layout_manifest_text",
    "current_layout_readme_text",
]
