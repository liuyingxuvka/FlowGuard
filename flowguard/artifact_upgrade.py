"""Deterministic upgrade scanning for older FlowGuard artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .schema import SCHEMA_VERSION


ARTIFACT_UPGRADE_STATUS_UPGRADED = "upgraded"
ARTIFACT_UPGRADE_STATUS_UNCHANGED = "unchanged"
ARTIFACT_UPGRADE_STATUS_BLOCKED = "blocked"
ARTIFACT_UPGRADE_STATUS_SKIPPED = "skipped"

ARTIFACT_UPGRADE_STATUSES = {
    ARTIFACT_UPGRADE_STATUS_UPGRADED,
    ARTIFACT_UPGRADE_STATUS_UNCHANGED,
    ARTIFACT_UPGRADE_STATUS_BLOCKED,
    ARTIFACT_UPGRADE_STATUS_SKIPPED,
}

ARTIFACT_UPGRADE_TEXT_REPLACEMENTS = {
    "PlanIntakeSurface": "PlanIntakeRiskSurface",
    "PlanIntakeCompletenessFinding": "PlanIntakeFinding",
    "FalseNegativeBackpropagationCase": "FalseNegativeCase",
    "FlowGuardClaimFinding": "FlowGuardClaimChainFinding",
    "review_plan_mutation_results": "review_plan_mutations",
    "FunctionResult.state": "FunctionResult.new_state",
}

_DEFAULT_SCAN_DIRS = (
    ".flowguard",
    ".agents/skills",
    "docs",
    "examples",
    "scripts",
    "tests",
)
_TEXT_SUFFIXES = {".md", ".py", ".txt", ".rst"}
_JSON_SUFFIXES = {".json"}
_TOML_SUFFIXES = {".toml"}
_SCAN_SUFFIXES = _TEXT_SUFFIXES | _JSON_SUFFIXES | _TOML_SUFFIXES
_IGNORED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "flowguard.egg-info",
    "tmp",
}
_UNKNOWN_SCRIPT_MARKERS = (
    "legacy_flowguard_runtime_path",
    "old_flowguard_behavior",
    "flowguard_legacy_runtime_path",
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class ArtifactUpgradeItem:
    """One file or artifact considered by an upgrade scan."""

    path: str
    item_kind: str
    status: str
    detected_shape: str = ""
    replacement: str = ""
    message: str = ""
    changed: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = str(self.status)
        if status not in ARTIFACT_UPGRADE_STATUSES:
            raise ValueError(f"unknown artifact upgrade status: {status!r}")
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "item_kind", str(self.item_kind))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "detected_shape", str(self.detected_shape))
        object.__setattr__(self, "replacement", str(self.replacement))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "changed", bool(self.changed))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "item_kind": self.item_kind,
            "status": self.status,
            "detected_shape": self.detected_shape,
            "replacement": self.replacement,
            "message": self.message,
            "changed": self.changed,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArtifactUpgradeReport:
    """Summary of an artifact/schema upgrade scan."""

    root: str
    apply: bool = False
    items: tuple[ArtifactUpgradeItem, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", str(self.root))
        object.__setattr__(self, "items", tuple(self.items))
        if not self.summary:
            object.__setattr__(self, "summary", self._build_summary())

    @property
    def ok(self) -> bool:
        return not any(item.status == ARTIFACT_UPGRADE_STATUS_BLOCKED for item in self.items)

    @property
    def changed_files(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.items if item.changed)

    @property
    def blocked_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.items if item.status == ARTIFACT_UPGRADE_STATUS_BLOCKED)

    @property
    def upgraded_count(self) -> int:
        return sum(1 for item in self.items if item.status == ARTIFACT_UPGRADE_STATUS_UPGRADED)

    @property
    def blocked_count(self) -> int:
        return sum(1 for item in self.items if item.status == ARTIFACT_UPGRADE_STATUS_BLOCKED)

    @property
    def scanned_count(self) -> int:
        return len(self.items)

    def _build_summary(self) -> str:
        mode = "apply" if self.apply else "dry_run"
        return (
            f"{mode}: scanned={self.scanned_count} upgraded={self.upgraded_count} "
            f"blocked={self.blocked_count} changed={len(self.changed_files)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_artifact_upgrade_report",
            "ok": self.ok,
            "root": self.root,
            "apply": self.apply,
            "summary": self.summary,
            "scanned_count": self.scanned_count,
            "upgraded_count": self.upgraded_count,
            "blocked_count": self.blocked_count,
            "changed_files": list(self.changed_files),
            "blocked_paths": list(self.blocked_paths),
            "items": [item.to_dict() for item in self.items],
            "validation_note": (
                "Artifact upgrades do not replace executable model checks, "
                "tests, replay, or route-owner evidence."
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def format_text(self, max_items: int = 20) -> str:
        lines = [
            "=== flowguard artifact upgrade ===",
            f"status: {'pass' if self.ok else 'blocked'}",
            f"root: {self.root}",
            f"mode: {'apply' if self.apply else 'dry-run'}",
            f"summary: {self.summary}",
            "note: artifact upgrades do not replace executable model checks, tests, replay, or route-owner evidence.",
        ]
        for item in self.items[:max_items]:
            lines.extend(
                [
                    "",
                    f"- {item.status}: {item.path}",
                    f"  kind: {item.item_kind}",
                    f"  shape: {item.detected_shape or '(none)'}",
                    f"  message: {item.message}",
                ]
            )
            if item.replacement:
                lines.append(f"  replacement: {item.replacement}")
        if len(self.items) > max_items:
            lines.append(f"... {len(self.items) - max_items} more items")
        return "\n".join(lines)


def review_artifact_upgrades(
    root: str | Path = ".",
    *,
    apply: bool = False,
    include_dirs: Sequence[str] = _DEFAULT_SCAN_DIRS,
    paths: Sequence[str | Path] = (),
) -> ArtifactUpgradeReport:
    """Scan a repository for deterministic FlowGuard artifact upgrades."""

    root_path = Path(root).resolve()
    candidates = tuple(_candidate_paths(root_path, include_dirs=include_dirs, paths=paths))
    items: list[ArtifactUpgradeItem] = []
    for path in candidates:
        item = _review_path(path, root_path=root_path, apply=apply)
        if item is not None:
            items.append(item)
    return ArtifactUpgradeReport(root=str(root_path), apply=apply, items=tuple(items))


def _candidate_paths(
    root_path: Path,
    *,
    include_dirs: Sequence[str],
    paths: Sequence[str | Path],
):
    explicit = tuple(paths)
    if explicit:
        for path in explicit:
            resolved = Path(path)
            if not resolved.is_absolute():
                resolved = root_path / resolved
            if resolved.is_file() and _is_scannable(resolved, root_path=root_path):
                yield resolved
            elif resolved.is_dir():
                yield from _walk_scannable(resolved, root_path=root_path)
        return
    for name in include_dirs:
        directory = root_path / name
        if directory.is_dir():
            yield from _walk_scannable(directory, root_path=root_path)


def _walk_scannable(directory: Path, *, root_path: Path):
    for path in sorted(directory.rglob("*")):
        if path.is_file() and _is_scannable(path, root_path=root_path):
            yield path


def _is_scannable(path: Path, *, root_path: Path | None = None) -> bool:
    if path.suffix.lower() not in _SCAN_SUFFIXES:
        return False
    parts = path.parts
    if root_path is not None:
        try:
            parts = path.resolve().relative_to(root_path).parts
        except ValueError:
            parts = path.parts
    return not any(part in _IGNORED_PARTS for part in parts)


def _review_path(path: Path, *, root_path: Path, apply: bool) -> ArtifactUpgradeItem | None:
    suffix = path.suffix.lower()
    rel_path = _relative_path(path, root_path)
    if suffix in _JSON_SUFFIXES:
        return _review_json_path(path, rel_path=rel_path, apply=apply)
    if suffix in _TEXT_SUFFIXES:
        return _review_text_path(path, rel_path=rel_path, apply=apply)
    if suffix in _TOML_SUFFIXES:
        return _review_toml_path(path, rel_path=rel_path)
    return None


def _review_json_path(path: Path, *, rel_path: str, apply: bool) -> ArtifactUpgradeItem | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if not _looks_like_flowguard_json(data):
        return None

    schema_version = str(data.get("schema_version", ""))
    if schema_version == SCHEMA_VERSION:
        return ArtifactUpgradeItem(
            rel_path,
            "json_artifact",
            ARTIFACT_UPGRADE_STATUS_UNCHANGED,
            detected_shape=f"schema_version:{schema_version}",
            message="artifact already uses the current FlowGuard schema",
        )
    if "payload" not in data and data.get("artifact_type"):
        upgraded = dict(data)
        upgraded["schema_version"] = SCHEMA_VERSION
        if apply:
            path.write_text(json.dumps(upgraded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ArtifactUpgradeItem(
            rel_path,
            "json_artifact",
            ARTIFACT_UPGRADE_STATUS_UPGRADED,
            detected_shape=f"schema_version:{schema_version or 'missing'}",
            replacement=f"schema_version:{SCHEMA_VERSION}",
            message="FlowGuard JSON artifact schema marker was upgraded deterministically",
            changed=apply,
        )

    upgraded = dict(data)
    upgraded["schema_version"] = SCHEMA_VERSION
    if apply:
        path.write_text(json.dumps(upgraded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ArtifactUpgradeItem(
        rel_path,
        "json_artifact",
        ARTIFACT_UPGRADE_STATUS_UPGRADED,
        detected_shape=f"schema_version:{schema_version or 'missing'}",
        replacement=f"schema_version:{SCHEMA_VERSION}",
        message="FlowGuard artifact envelope schema was upgraded deterministically",
        changed=apply,
    )


def _looks_like_flowguard_json(data: Mapping[str, Any]) -> bool:
    artifact_type = str(data.get("artifact_type", ""))
    created_by = str(data.get("created_by", ""))
    return artifact_type.startswith("flowguard") or created_by == "flowguard" or "schema_version" in data


def _review_text_path(path: Path, *, rel_path: str, apply: bool) -> ArtifactUpgradeItem | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    if rel_path == "docs/flowguard_adoption_log.md":
        return _skipped_text_item(rel_path, "historical_adoption_log")

    unknown_markers = tuple(marker for marker in _UNKNOWN_SCRIPT_MARKERS if marker in text)
    if path.suffix.lower() == ".py" and unknown_markers:
        return ArtifactUpgradeItem(
            rel_path,
            "python_script",
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            detected_shape="unknown_behavior_script",
            message="behavior-bearing script contains an unknown legacy FlowGuard marker",
            metadata={"markers": list(unknown_markers)},
        )

    replacements = {
        old: new
        for old, new in ARTIFACT_UPGRADE_TEXT_REPLACEMENTS.items()
        if old in text
    }
    if not replacements:
        return None
    if rel_path.startswith(".flowguard/legacy_compatibility_cleanup/"):
        return _skipped_text_item(rel_path, "legacy_cleanup_self_model")
    if rel_path.startswith("tests/") and ("removed_aliases" in text or "assertNotIn" in text):
        return _skipped_text_item(rel_path, "negative_legacy_test")
    upgraded = text
    for old, new in replacements.items():
        upgraded = upgraded.replace(old, new)
    if apply and upgraded != text:
        path.write_text(upgraded, encoding="utf-8")
    return ArtifactUpgradeItem(
        rel_path,
        "text_reference" if path.suffix.lower() != ".py" else "python_script",
        ARTIFACT_UPGRADE_STATUS_UPGRADED,
        detected_shape="obsolete_api_aliases",
        replacement="current_route_first_api",
        message="known obsolete FlowGuard API aliases were replaced deterministically",
        changed=apply and upgraded != text,
        metadata={"replacements": replacements},
    )


def _skipped_text_item(rel_path: str, detected_shape: str) -> ArtifactUpgradeItem:
    return ArtifactUpgradeItem(
        rel_path,
        "text_reference",
        ARTIFACT_UPGRADE_STATUS_SKIPPED,
        detected_shape=detected_shape,
        message="historical or negative legacy evidence is preserved rather than rewritten",
    )


def _review_toml_path(path: Path, *, rel_path: str) -> ArtifactUpgradeItem | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if "schema_version" not in text or "flowguard" not in text.lower():
        return None
    if f'schema_version = "{SCHEMA_VERSION}"' in text:
        return ArtifactUpgradeItem(
            rel_path,
            "project_manifest",
            ARTIFACT_UPGRADE_STATUS_UNCHANGED,
            detected_shape=f"schema_version:{SCHEMA_VERSION}",
            message="project manifest already records the current FlowGuard schema",
        )
    return ArtifactUpgradeItem(
        rel_path,
        "project_manifest",
        ARTIFACT_UPGRADE_STATUS_SKIPPED,
        detected_shape="manifest_schema_mismatch",
        message="project manifest schema is updated by project-upgrade record handling",
    )


def _relative_path(path: Path, root_path: Path) -> str:
    try:
        return path.resolve().relative_to(root_path).as_posix()
    except ValueError:
        return str(path.resolve())


__all__ = [
    "ARTIFACT_UPGRADE_STATUS_BLOCKED",
    "ARTIFACT_UPGRADE_STATUS_SKIPPED",
    "ARTIFACT_UPGRADE_STATUS_UNCHANGED",
    "ARTIFACT_UPGRADE_STATUS_UPGRADED",
    "ARTIFACT_UPGRADE_STATUSES",
    "ARTIFACT_UPGRADE_TEXT_REPLACEMENTS",
    "ArtifactUpgradeItem",
    "ArtifactUpgradeReport",
    "review_artifact_upgrades",
]
