"""Deterministic upgrade scanning for older FlowGuard artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .behavior_commitment import (
    BCL_ACTOR_AI_AGENT,
    BCL_ACTOR_APPLICATION,
    BCL_ACTOR_AUTOMATION,
    BCL_ACTOR_DEVELOPER,
    BCL_ACTOR_END_USER,
    BCL_ACTOR_EXTERNAL_SYSTEM,
    BCL_ACTOR_KINDS,
    BCL_BEHAVIOR_PLANES,
    BCL_COMMITMENT_CLI,
    BCL_COMMITMENT_DOC,
    BCL_COMMITMENT_KINDS,
    BCL_COMMITMENT_PROCESS,
    BCL_COMMITMENT_PUBLIC_API,
    BCL_COMMITMENT_RELEASE,
    BCL_COMMITMENT_SKILL,
    BCL_COMMITMENT_UI,
    BCL_COMMITMENT_WORKFLOW,
    BCL_LEDGER_ARTIFACT_TYPE,
    BCL_LEDGER_FORMAT_VERSION,
    BCL_PLANE_AGENT_OPERATION,
    BCL_PLANE_DEVELOPMENT_PROCESS,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_RELATION_DEPENDS_ON,
)
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

_LEGACY_BCL_DEPENDENCY_FIELD = "dependency_commitment_ids"
_BCL_MIGRATION_RATIONALE = (
    "Migrated deterministically from legacy same-plane dependency_commitment_ids."
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


@dataclass(frozen=True)
class BehaviorLedgerMigrationFinding:
    """One ambiguity that prevents safe automatic ledger migration."""

    code: str
    message: str
    commitment_id: str = ""
    target_commitment_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "commitment_id", str(self.commitment_id))
        object.__setattr__(self, "target_commitment_id", str(self.target_commitment_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "commitment_id": self.commitment_id,
            "target_commitment_id": self.target_commitment_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorLedgerMigrationResult:
    """Pure migration result for one machine-readable legacy BCL mapping."""

    status: str
    mapping: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[BehaviorLedgerMigrationFinding, ...] = ()
    migrated_commitment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in ARTIFACT_UPGRADE_STATUSES:
            raise ValueError(f"unknown behavior-ledger migration status: {self.status!r}")
        object.__setattr__(self, "mapping", dict(self.mapping))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "migrated_commitment_ids",
            tuple(str(value) for value in self.migrated_commitment_ids),
        )

    @property
    def ok(self) -> bool:
        return self.status != ARTIFACT_UPGRADE_STATUS_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.ok,
            "mapping": to_jsonable(dict(self.mapping)),
            "findings": [finding.to_dict() for finding in self.findings],
            "migrated_commitment_ids": list(self.migrated_commitment_ids),
        }


def _normalized_actor_text(commitment: Mapping[str, Any]) -> str:
    return " ".join(
        str(commitment.get(name, "")).strip().lower()
        for name in ("actor", "owner", "label", "trigger")
    )


def _explicit_migration_value(commitment: Mapping[str, Any], name: str) -> str:
    direct = str(commitment.get(name, "")).strip()
    if direct:
        return direct
    metadata = commitment.get("metadata")
    if isinstance(metadata, Mapping):
        return str(metadata.get(name, "")).strip()
    return ""


def _infer_legacy_plane_actor(
    commitment: Mapping[str, Any],
) -> tuple[str, str, tuple[str, ...]]:
    """Infer only bounded, explainable legacy classifications."""

    reasons: list[str] = []
    plane = str(commitment.get("behavior_plane", "")).strip()
    actor_kind = str(commitment.get("actor_kind", "")).strip()
    explicit_plane = _explicit_migration_value(commitment, "migration_behavior_plane")
    explicit_actor = _explicit_migration_value(commitment, "migration_actor_kind")
    if not plane and explicit_plane in BCL_BEHAVIOR_PLANES:
        plane = explicit_plane
        reasons.append("explicit_migration_behavior_plane")
    if not actor_kind and explicit_actor in BCL_ACTOR_KINDS:
        actor_kind = explicit_actor
        reasons.append("explicit_migration_actor_kind")

    kind = str(commitment.get("commitment_kind", BCL_COMMITMENT_WORKFLOW)).strip()
    actor_text = _normalized_actor_text(commitment)
    if not plane:
        if kind in {BCL_COMMITMENT_UI, BCL_COMMITMENT_PUBLIC_API, BCL_COMMITMENT_CLI}:
            plane = BCL_PLANE_PRODUCT_RUNTIME
            reasons.append(f"commitment_kind:{kind}")
        elif kind == BCL_COMMITMENT_SKILL or any(
            token in actor_text for token in ("ai agent", "ai-agent", "codex", "agent operation")
        ):
            plane = BCL_PLANE_AGENT_OPERATION
            reasons.append("agent_actor_or_skill_kind")
        elif kind in {BCL_COMMITMENT_RELEASE, BCL_COMMITMENT_PROCESS} or any(
            token in actor_text
            for token in ("developer", "maintainer", "release automation", "ci automation")
        ):
            plane = BCL_PLANE_DEVELOPMENT_PROCESS
            reasons.append("development_actor_or_process_kind")
        elif any(token in actor_text for token in ("end user", "customer", "user")):
            plane = BCL_PLANE_PRODUCT_RUNTIME
            reasons.append("end_user_actor")

    if not actor_kind and plane:
        if plane == BCL_PLANE_AGENT_OPERATION:
            actor_kind = BCL_ACTOR_AI_AGENT
            reasons.append("actor_from_agent_plane")
        elif plane == BCL_PLANE_DEVELOPMENT_PROCESS:
            if any(token in actor_text for token in ("automation", " ci ", "bot")):
                actor_kind = BCL_ACTOR_AUTOMATION
            else:
                actor_kind = BCL_ACTOR_DEVELOPER
            reasons.append("actor_from_development_plane")
        elif plane == BCL_PLANE_PRODUCT_RUNTIME:
            if kind in {BCL_COMMITMENT_PUBLIC_API, BCL_COMMITMENT_CLI}:
                actor_kind = BCL_ACTOR_EXTERNAL_SYSTEM
            elif kind == BCL_COMMITMENT_UI:
                actor_kind = BCL_ACTOR_END_USER
            elif any(token in actor_text for token in ("application", "service")):
                actor_kind = BCL_ACTOR_APPLICATION
            else:
                actor_kind = BCL_ACTOR_END_USER
            reasons.append("actor_from_product_plane")

    return plane, actor_kind, tuple(reasons)


def _looks_like_behavior_ledger_mapping(data: Mapping[str, Any]) -> bool:
    if str(data.get("artifact_type", "")) == BCL_LEDGER_ARTIFACT_TYPE:
        return True
    return "ledger_id" in data and isinstance(data.get("commitments"), list)


def upgrade_behavior_commitment_ledger_mapping(
    value: Mapping[str, Any],
) -> BehaviorLedgerMigrationResult:
    """Upgrade official JSON/mapping BCL input without executing Python.

    Classification is deliberately conservative.  Ambiguous workflow or doc
    rows and cross-plane legacy dependencies produce manual findings and no
    partially upgraded authority.
    """

    original = dict(value)
    is_envelope = "ledger" in original
    if is_envelope:
        if str(original.get("artifact_type", "")) != BCL_LEDGER_ARTIFACT_TYPE:
            return BehaviorLedgerMigrationResult(
                ARTIFACT_UPGRADE_STATUS_BLOCKED,
                findings=(
                    BehaviorLedgerMigrationFinding(
                        "behavior_ledger_artifact_type_invalid",
                        "The ledger envelope has an unexpected artifact_type.",
                    ),
                ),
            )
        payload = original.get("ledger")
        if not isinstance(payload, Mapping):
            return BehaviorLedgerMigrationResult(
                ARTIFACT_UPGRADE_STATUS_BLOCKED,
                findings=(
                    BehaviorLedgerMigrationFinding(
                        "behavior_ledger_payload_missing",
                        "The ledger envelope does not contain a mapping payload.",
                    ),
                ),
            )
        ledger = dict(payload)
    else:
        ledger = dict(original)

    rows = ledger.get("commitments")
    if not isinstance(rows, list):
        return BehaviorLedgerMigrationResult(
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            findings=(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_commitments_missing",
                    "The legacy ledger has no commitment list.",
                ),
            ),
        )
    if (
        is_envelope
        and str(original.get("format_version", "")) == BCL_LEDGER_FORMAT_VERSION
        and all(
            isinstance(row, Mapping)
            and str(row.get("behavior_plane", "")) in BCL_BEHAVIOR_PLANES
            and str(row.get("actor_kind", "")) in BCL_ACTOR_KINDS
            and _LEGACY_BCL_DEPENDENCY_FIELD not in row
            for row in rows
        )
    ):
        return BehaviorLedgerMigrationResult(
            ARTIFACT_UPGRADE_STATUS_UNCHANGED,
            mapping=original,
            migrated_commitment_ids=tuple(
                str(row.get("commitment_id", "")) for row in rows if isinstance(row, Mapping)
            ),
        )

    findings: list[BehaviorLedgerMigrationFinding] = []
    migrated_rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    classification_reasons: dict[str, tuple[str, ...]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_commitment_not_mapping",
                    "Every legacy commitment must be a mapping.",
                )
            )
            continue
        row = dict(raw)
        commitment_id = str(row.get("commitment_id", ""))
        if not commitment_id:
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_commitment_id_missing",
                    "A legacy commitment has no stable commitment_id.",
                )
            )
            continue
        if commitment_id in by_id:
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_commitment_id_duplicate",
                    "A legacy commitment_id occurs more than once.",
                    commitment_id=commitment_id,
                )
            )
            continue
        plane, actor_kind, reasons = _infer_legacy_plane_actor(row)
        if plane not in BCL_BEHAVIOR_PLANES or actor_kind not in BCL_ACTOR_KINDS:
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_plane_actor_requires_manual_classification",
                    "The legacy commitment cannot be assigned safely to one execution plane and actor kind.",
                    commitment_id=commitment_id,
                    metadata={
                        "commitment_kind": str(row.get("commitment_kind", "")),
                        "inferred_plane": plane,
                        "inferred_actor_kind": actor_kind,
                    },
                )
            )
        else:
            row["behavior_plane"] = plane
            row["actor_kind"] = actor_kind
            classification_reasons[commitment_id] = reasons
        migrated_rows.append(row)
        by_id[commitment_id] = row

    for row in migrated_rows:
        commitment_id = str(row.get("commitment_id", ""))
        dependencies = row.get(_LEGACY_BCL_DEPENDENCY_FIELD, ())
        if isinstance(dependencies, str):
            dependencies = (dependencies,)
        if not isinstance(dependencies, Sequence):
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_dependencies_invalid",
                    "Legacy dependency_commitment_ids must be a sequence.",
                    commitment_id=commitment_id,
                )
            )
            continue
        relations = list(row.get("relations", ()))
        for target_id_raw in dependencies:
            target_id = str(target_id_raw)
            target = by_id.get(target_id)
            if target is None:
                findings.append(
                    BehaviorLedgerMigrationFinding(
                        "behavior_ledger_dependency_target_unknown",
                        "A legacy dependency target is not registered in the ledger.",
                        commitment_id=commitment_id,
                        target_commitment_id=target_id,
                    )
                )
                continue
            if row.get("behavior_plane") != target.get("behavior_plane"):
                findings.append(
                    BehaviorLedgerMigrationFinding(
                        "behavior_ledger_cross_plane_dependency_requires_typed_relation",
                        "A cross-plane legacy dependency needs an explicit typed relation and rationale.",
                        commitment_id=commitment_id,
                        target_commitment_id=target_id,
                        metadata={
                            "source_plane": row.get("behavior_plane", ""),
                            "target_plane": target.get("behavior_plane", ""),
                        },
                    )
                )
                continue
            if not any(
                isinstance(relation, Mapping)
                and str(relation.get("target_commitment_id", "")) == target_id
                and str(relation.get("relation_type", "")) == BCL_RELATION_DEPENDS_ON
                for relation in relations
            ):
                relations.append(
                    {
                        "target_commitment_id": target_id,
                        "relation_type": BCL_RELATION_DEPENDS_ON,
                        "rationale": _BCL_MIGRATION_RATIONALE,
                        "metadata": {"migration_source": _LEGACY_BCL_DEPENDENCY_FIELD},
                    }
                )
        row.pop(_LEGACY_BCL_DEPENDENCY_FIELD, None)
        row["relations"] = relations

    if findings:
        return BehaviorLedgerMigrationResult(
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            findings=tuple(findings),
        )

    ledger["commitments"] = migrated_rows
    metadata = dict(ledger.get("metadata") or {})
    metadata["behavior_plane_migration"] = {
        "source_format": str(original.get("format_version", "legacy_mapping")),
        "classification_reasons": {
            key: list(values) for key, values in sorted(classification_reasons.items())
        },
    }
    ledger["metadata"] = metadata
    upgraded = {
        "artifact_type": BCL_LEDGER_ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "format_version": BCL_LEDGER_FORMAT_VERSION,
        "ledger": ledger,
    }
    already_current = (
        is_envelope
        and str(original.get("format_version", "")) == BCL_LEDGER_FORMAT_VERSION
        and original == upgraded
    )
    return BehaviorLedgerMigrationResult(
        ARTIFACT_UPGRADE_STATUS_UNCHANGED if already_current else ARTIFACT_UPGRADE_STATUS_UPGRADED,
        mapping=upgraded,
        migrated_commitment_ids=tuple(str(row["commitment_id"]) for row in migrated_rows),
    )


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
    if _looks_like_behavior_ledger_mapping(data):
        migration = upgrade_behavior_commitment_ledger_mapping(data)
        if migration.status == ARTIFACT_UPGRADE_STATUS_BLOCKED:
            return ArtifactUpgradeItem(
                rel_path,
                "behavior_commitment_ledger",
                ARTIFACT_UPGRADE_STATUS_BLOCKED,
                detected_shape="legacy_behavior_commitment_ledger",
                replacement=f"{BCL_LEDGER_ARTIFACT_TYPE}:{BCL_LEDGER_FORMAT_VERSION}",
                message="behavior ledger migration needs explicit manual classification or typed relation evidence",
                metadata={"findings": [finding.to_dict() for finding in migration.findings]},
            )
        if apply and migration.status == ARTIFACT_UPGRADE_STATUS_UPGRADED:
            path.write_text(
                json.dumps(migration.mapping, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return ArtifactUpgradeItem(
            rel_path,
            "behavior_commitment_ledger",
            migration.status,
            detected_shape=(
                "current_behavior_commitment_ledger"
                if migration.status == ARTIFACT_UPGRADE_STATUS_UNCHANGED
                else "legacy_behavior_commitment_ledger"
            ),
            replacement=f"{BCL_LEDGER_ARTIFACT_TYPE}:{BCL_LEDGER_FORMAT_VERSION}",
            message=(
                "behavior ledger already uses the canonical execution-plane format"
                if migration.status == ARTIFACT_UPGRADE_STATUS_UNCHANGED
                else "behavior ledger was migrated without executing project Python"
            ),
            changed=apply and migration.status == ARTIFACT_UPGRADE_STATUS_UPGRADED,
            metadata={"migrated_commitment_ids": list(migration.migrated_commitment_ids)},
        )
    if not _looks_like_flowguard_json(data):
        return None

    schema_version = str(data.get("schema_version", ""))
    if schema_version and not _is_numeric_schema_version(schema_version):
        return ArtifactUpgradeItem(
            rel_path,
            "namespaced_json_artifact",
            ARTIFACT_UPGRADE_STATUS_UNCHANGED,
            detected_shape=f"schema_version:{schema_version}",
            message="namespaced artifact schema is owned by its producer and is not a FlowGuard envelope migration target",
        )
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
    schema_version = str(data.get("schema_version", ""))
    return (
        artifact_type.startswith("flowguard")
        or created_by == "flowguard"
        or _is_numeric_schema_version(schema_version)
    )


def _is_numeric_schema_version(value: str) -> bool:
    parts = value.split(".")
    return bool(value) and all(part.isdigit() for part in parts)


def _review_text_path(path: Path, *, rel_path: str, apply: bool) -> ArtifactUpgradeItem | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    if rel_path == "docs/flowguard_adoption_log.md":
        return _skipped_text_item(rel_path, "historical_adoption_log")

    if (
        rel_path == ".flowguard/behavior_commitment_ledger/model.py"
        and "load_behavior_commitment_ledger" not in text
        and ("BehaviorCommitment(" in text or "BehaviorCommitmentLedger(" in text)
    ):
        return ArtifactUpgradeItem(
            rel_path,
            "python_script",
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            detected_shape="embedded_python_behavior_ledger_inventory",
            replacement="canonical ledger.json plus thin loader",
            message=(
                "embedded Python behavior inventory is not executed by the upgrader; "
                "export or classify it into canonical JSON first"
            ),
        )

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
    "BehaviorLedgerMigrationFinding",
    "BehaviorLedgerMigrationResult",
    "review_artifact_upgrades",
    "upgrade_behavior_commitment_ledger_mapping",
]
