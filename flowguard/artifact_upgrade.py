"""Deterministic upgrade scanning for older FlowGuard artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .behavior_commitment import (
    BCL_ACTOR_KINDS,
    BCL_BEHAVIOR_PLANES,
    BCL_LEDGER_ARTIFACT_TYPE,
    BCL_LEDGER_FORMAT_VERSION,
    BCL_RELATION_DEPENDS_ON,
    behavior_commitment_ledger_from_mapping,
    behavior_commitment_ledger_to_mapping,
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
_LEGACY_BCL_SHAPE_ID = "flowguard.bcl.legacy.56083c1e"
# Exact `to_dict()` field sets from the final pre-migration producer commit
# 56083c1e47602654089e05701e9f5b42cce6c9a1. That producer emitted every
# listed key; none of these fields is optional in its serialized JSON shape.
_BCL_ENVELOPE_FIELDS = frozenset(
    {"artifact_type", "schema_version", "format_version", "ledger"}
)
_LEGACY_BCL_LEDGER_FIELDS = frozenset(
    {
        "ledger_id",
        "project_boundary",
        "current_revision",
        "commitments",
        "source_surfaces",
        "expected_commitment_ids",
        "claim_scope",
        "change_mode",
        "require_current_evidence",
        "require_risk_gates_for_broad_claim",
        "owner",
        "validation_boundary",
        "rationale",
        "metadata",
    }
)
_LEGACY_BCL_COMMITMENT_FIELDS = frozenset(
    {
        "commitment_id",
        "label",
        "commitment_kind",
        "actor",
        "trigger",
        "expected_result",
        "failure_boundary",
        "source_surface_ids",
        "source_refs",
        "primary_owner_model_id",
        "supporting_model_ids",
        "child_model_ids",
        "dependency_commitment_ids",
        "excluded_behavior_ids",
        "replacement_state",
        "model_sync_state",
        "miss_origin_state",
        "path_authority",
        "evidence",
        "in_scope",
        "scoped_out_reason",
        "owner",
        "validation_boundary",
        "rationale",
        "metadata",
    }
)
_LEGACY_BCL_SOURCE_SURFACE_FIELDS = frozenset(
    {
        "surface_id",
        "surface_kind",
        "label",
        "source_ref",
        "commitment_ids",
        "freshness_state",
        "in_scope",
        "scoped_out_reason",
        "owner",
        "validation_boundary",
        "rationale",
        "metadata",
    }
)
_LEGACY_BCL_EVIDENCE_FIELDS = frozenset(
    {
        "model_obligation_ids",
        "code_contract_ids",
        "test_evidence_ids",
        "proof_artifact_ids",
        "risk_gate_ids",
        "coverage_case_ids",
        "coverage_shard_ids",
        "coverage_receipt_ids",
        "evidence_state",
        "test_mesh_state",
        "current",
        "metadata",
    }
)
_LEGACY_BCL_PATH_AUTHORITY_FIELDS = frozenset(
    {
        "path_sensitive",
        "business_intent",
        "ppa_report_id",
        "ppa_decision",
        "ppa_confidence",
        "ppa_ok",
        "primary_path_ids",
        "fallback_candidate_ids",
        "ppa_coverage_receipt_ids",
        "ppa_coverage_shard_ids",
        "ppa_risk_gate_ids",
        "scoped_out_reason",
        "evidence_refs",
        "metadata",
    }
)


@dataclass(frozen=True)
class FlowGuardJsonArtifactRegistration:
    """Exact current-only producer shape for one FlowGuard JSON artifact."""

    artifact_type: str
    version_field: str
    current_versions: frozenset[str]
    allowed_fields: frozenset[str]
    field_types: tuple[tuple[str, type], ...]
    required_values: tuple[tuple[str, str], ...] = ()


_FLOWGUARD_JSON_ARTIFACT_REGISTRY: Mapping[
    str, FlowGuardJsonArtifactRegistration
] = MappingProxyType(
    {
        artifact_type: FlowGuardJsonArtifactRegistration(
            artifact_type=artifact_type,
            version_field="schema_version",
            current_versions=frozenset({SCHEMA_VERSION}),
            allowed_fields=frozenset(
                {
                    "schema_version",
                    "artifact_type",
                    "created_by",
                    "model_name",
                    "scenario_name",
                    "trace_id",
                    "payload",
                }
            ),
            field_types=(
                ("schema_version", str),
                ("artifact_type", str),
                ("created_by", str),
                ("model_name", str),
                ("scenario_name", str),
                ("trace_id", str),
            ),
            required_values=(("created_by", "flowguard"),),
        )
        for artifact_type in ("report", "trace")
    }
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


def _explicit_migration_value(commitment: Mapping[str, Any], name: str) -> str:
    metadata = commitment.get("metadata")
    if isinstance(metadata, Mapping):
        return str(metadata.get(name, "")).strip()
    return ""


def _explicit_legacy_plane_actor(
    commitment: Mapping[str, Any],
) -> tuple[str, str, tuple[str, ...]]:
    """Read one evidence-bound AI migration disposition from legacy metadata."""

    reasons: list[str] = []
    plane = ""
    actor_kind = ""
    explicit_plane = _explicit_migration_value(commitment, "migration_behavior_plane")
    explicit_actor = _explicit_migration_value(commitment, "migration_actor_kind")
    if explicit_plane in BCL_BEHAVIOR_PLANES:
        plane = explicit_plane
        reasons.append("explicit_migration_behavior_plane")
    if explicit_actor in BCL_ACTOR_KINDS:
        actor_kind = explicit_actor
        reasons.append("explicit_migration_actor_kind")
    return plane, actor_kind, tuple(reasons)


def _is_json_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _has_exact_legacy_evidence_shape(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != _LEGACY_BCL_EVIDENCE_FIELDS:
        return False
    list_fields = _LEGACY_BCL_EVIDENCE_FIELDS - {
        "evidence_state",
        "test_mesh_state",
        "current",
        "metadata",
    }
    return (
        all(_is_json_string_list(value[field]) for field in list_fields)
        and isinstance(value["evidence_state"], str)
        and isinstance(value["test_mesh_state"], str)
        and isinstance(value["current"], bool)
        and isinstance(value["metadata"], Mapping)
    )


def _has_exact_legacy_path_authority_shape(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != _LEGACY_BCL_PATH_AUTHORITY_FIELDS:
        return False
    string_fields = {
        "business_intent",
        "ppa_report_id",
        "ppa_decision",
        "ppa_confidence",
        "scoped_out_reason",
    }
    list_fields = {
        "primary_path_ids",
        "fallback_candidate_ids",
        "ppa_coverage_receipt_ids",
        "ppa_coverage_shard_ids",
        "ppa_risk_gate_ids",
        "evidence_refs",
    }
    return (
        isinstance(value["path_sensitive"], bool)
        and all(isinstance(value[field], str) for field in string_fields)
        and (
            value["ppa_ok"] is None
            or isinstance(value["ppa_ok"], bool)
        )
        and all(_is_json_string_list(value[field]) for field in list_fields)
        and isinstance(value["metadata"], Mapping)
    )


def _has_exact_legacy_source_surface_shape(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != _LEGACY_BCL_SOURCE_SURFACE_FIELDS:
        return False
    string_fields = _LEGACY_BCL_SOURCE_SURFACE_FIELDS - {
        "commitment_ids",
        "in_scope",
        "metadata",
    }
    return (
        all(isinstance(value[field], str) for field in string_fields)
        and _is_json_string_list(value["commitment_ids"])
        and isinstance(value["in_scope"], bool)
        and isinstance(value["metadata"], Mapping)
    )


def _has_exact_legacy_commitment_shape(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != _LEGACY_BCL_COMMITMENT_FIELDS:
        return False
    string_fields = _LEGACY_BCL_COMMITMENT_FIELDS - {
        "source_surface_ids",
        "source_refs",
        "supporting_model_ids",
        "child_model_ids",
        _LEGACY_BCL_DEPENDENCY_FIELD,
        "excluded_behavior_ids",
        "path_authority",
        "evidence",
        "in_scope",
        "metadata",
    }
    list_fields = {
        "source_surface_ids",
        "source_refs",
        "supporting_model_ids",
        "child_model_ids",
        _LEGACY_BCL_DEPENDENCY_FIELD,
        "excluded_behavior_ids",
    }
    return (
        all(isinstance(value[field], str) for field in string_fields)
        and all(_is_json_string_list(value[field]) for field in list_fields)
        and _has_exact_legacy_path_authority_shape(value["path_authority"])
        and _has_exact_legacy_evidence_shape(value["evidence"])
        and isinstance(value["in_scope"], bool)
        and isinstance(value["metadata"], Mapping)
    )


def _has_exact_legacy_behavior_ledger_shape(data: Mapping[str, Any]) -> bool:
    if set(data) != _LEGACY_BCL_LEDGER_FIELDS:
        return False
    string_fields = _LEGACY_BCL_LEDGER_FIELDS - {
        "commitments",
        "source_surfaces",
        "expected_commitment_ids",
        "require_current_evidence",
        "require_risk_gates_for_broad_claim",
        "metadata",
    }
    commitments = data["commitments"]
    source_surfaces = data["source_surfaces"]
    return (
        all(isinstance(data[field], str) for field in string_fields)
        and isinstance(commitments, list)
        and all(_has_exact_legacy_commitment_shape(row) for row in commitments)
        and isinstance(source_surfaces, list)
        and all(
            _has_exact_legacy_source_surface_shape(surface)
            for surface in source_surfaces
        )
        and _is_json_string_list(data["expected_commitment_ids"])
        and isinstance(data["require_current_evidence"], bool)
        and isinstance(data["require_risk_gates_for_broad_claim"], bool)
        and isinstance(data["metadata"], Mapping)
    )


def _looks_like_behavior_ledger_mapping(data: Mapping[str, Any]) -> bool:
    if str(data.get("artifact_type", "")) == BCL_LEDGER_ARTIFACT_TYPE:
        return True
    if "artifact_type" in data or "ledger" in data:
        return False
    return _has_exact_legacy_behavior_ledger_shape(data)


def _current_behavior_ledger_envelope_findings(
    data: Mapping[str, Any],
) -> tuple[str, ...]:
    findings: list[str] = []
    actual_fields = set(data)
    if actual_fields != _BCL_ENVELOPE_FIELDS:
        missing = sorted(_BCL_ENVELOPE_FIELDS - actual_fields)
        extra = sorted(actual_fields - _BCL_ENVELOPE_FIELDS)
        if missing:
            findings.append(f"missing_fields:{','.join(missing)}")
        if extra:
            findings.append(f"extra_fields:{','.join(extra)}")
    if data.get("artifact_type") != BCL_LEDGER_ARTIFACT_TYPE:
        findings.append("artifact_type_not_current")
    if data.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_not_current")
    if data.get("format_version") != BCL_LEDGER_FORMAT_VERSION:
        findings.append("format_version_not_current")
    if findings:
        return tuple(findings)
    try:
        normalized = behavior_commitment_ledger_from_mapping(data)
        canonical = behavior_commitment_ledger_to_mapping(normalized)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return (f"current_payload_invalid:{type(exc).__name__}",)
    if canonical != dict(data):
        return ("current_payload_not_exact_canonical_shape",)
    return ()


def _materialize_current_path_authority(
    legacy: Mapping[str, Any],
    *,
    commitment_id: str,
) -> dict[str, Any]:
    primary_path_ids = list(legacy["primary_path_ids"])
    metadata = dict(legacy["metadata"])
    if primary_path_ids:
        metadata["historical_primary_path_migration"] = {
            "source_shape_id": _LEGACY_BCL_SHAPE_ID,
            "source_field": "primary_path_ids",
        }
    return {
        "path_sensitive": legacy["path_sensitive"],
        "business_intent": legacy["business_intent"],
        "business_intent_id": "",
        "behavior_commitment_id": commitment_id,
        "ppa_report_id": legacy["ppa_report_id"],
        "ppa_decision": legacy["ppa_decision"],
        "ppa_confidence": legacy["ppa_confidence"],
        "ppa_ok": legacy["ppa_ok"],
        "primary_path_id": primary_path_ids[0] if primary_path_ids else "",
        "fallback_candidate_ids": list(legacy["fallback_candidate_ids"]),
        "ppa_coverage_receipt_ids": list(legacy["ppa_coverage_receipt_ids"]),
        "ppa_coverage_shard_ids": list(legacy["ppa_coverage_shard_ids"]),
        "ppa_risk_gate_ids": list(legacy["ppa_risk_gate_ids"]),
        "scoped_out_reason": legacy["scoped_out_reason"],
        "evidence_refs": list(legacy["evidence_refs"]),
        "runtime_observation_ids": [],
        "proof_artifact_ids": [],
        "evidence_current": False,
        "metadata": metadata,
    }


def _materialize_current_commitment(row: Mapping[str, Any]) -> dict[str, Any]:
    commitment_id = str(row["commitment_id"])
    metadata = dict(row["metadata"])
    metadata.pop("migration_behavior_plane", None)
    metadata.pop("migration_actor_kind", None)
    return {
        "commitment_id": commitment_id,
        "business_intent_id": "",
        "label": row["label"],
        "commitment_kind": row["commitment_kind"],
        "behavior_plane": row["behavior_plane"],
        "actor_kind": row["actor_kind"],
        "actor": row["actor"],
        "trigger": row["trigger"],
        "expected_result": row["expected_result"],
        "failure_boundary": row["failure_boundary"],
        "preconditions": [],
        "expected_terminal": "",
        "state_writes": [],
        "side_effects": [],
        "variant_of_business_intent_id": "",
        "external_differences": [],
        "similarity_relation_ids": [],
        "similarity_obligation_ids": [],
        "surface_delegation_only": False,
        "source_surface_ids": list(row["source_surface_ids"]),
        "source_refs": list(row["source_refs"]),
        "primary_owner_model_id": row["primary_owner_model_id"],
        "supporting_model_ids": list(row["supporting_model_ids"]),
        "child_model_ids": list(row["child_model_ids"]),
        "relations": [dict(relation) for relation in row["relations"]],
        "lookup_binding": {
            "task_terms": [],
            "path_patterns": [],
            "tool_ids": [],
            "error_signatures": [],
            "workflow_families": [],
            "metadata": {},
        },
        "excluded_behavior_ids": list(row["excluded_behavior_ids"]),
        "replacement_state": row["replacement_state"],
        "model_sync_state": row["model_sync_state"],
        "miss_origin_state": row["miss_origin_state"],
        "path_authority": _materialize_current_path_authority(
            row["path_authority"],
            commitment_id=commitment_id,
        ),
        "evidence": {
            key: list(value) if isinstance(value, list) else dict(value)
            if key == "metadata"
            else value
            for key, value in row["evidence"].items()
        },
        "in_scope": row["in_scope"],
        "scoped_out_reason": row["scoped_out_reason"],
        "owner": row["owner"],
        "validation_boundary": row["validation_boundary"],
        "rationale": row["rationale"],
        "metadata": metadata,
    }


def _materialize_current_source_surface(
    legacy: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "surface_id": legacy["surface_id"],
        "surface_kind": legacy["surface_kind"],
        "label": legacy["label"],
        "source_ref": legacy["source_ref"],
        "commitment_ids": list(legacy["commitment_ids"]),
        "business_intent_ids": [],
        "primary_path_id": "",
        "delegates_to_primary_path": False,
        "similarity_relation_ids": [],
        "similarity_obligation_ids": [],
        "freshness_state": legacy["freshness_state"],
        "in_scope": legacy["in_scope"],
        "scoped_out_reason": legacy["scoped_out_reason"],
        "owner": legacy["owner"],
        "validation_boundary": legacy["validation_boundary"],
        "rationale": legacy["rationale"],
        "metadata": dict(legacy["metadata"]),
    }


def upgrade_behavior_commitment_ledger_mapping(
    value: Mapping[str, Any],
) -> BehaviorLedgerMigrationResult:
    """Upgrade official JSON/mapping BCL input without executing Python.

    Classification is deliberately conservative.  Ambiguous workflow or doc
    rows and cross-plane legacy dependencies produce manual findings and no
    partially upgraded authority.
    """

    original = dict(value)
    is_envelope = (
        "ledger" in original
        or str(original.get("artifact_type", "")) == BCL_LEDGER_ARTIFACT_TYPE
    )
    if is_envelope:
        envelope_findings = _current_behavior_ledger_envelope_findings(original)
        if envelope_findings:
            return BehaviorLedgerMigrationResult(
                ARTIFACT_UPGRADE_STATUS_BLOCKED,
                findings=(
                    BehaviorLedgerMigrationFinding(
                        "behavior_ledger_envelope_not_exact_current",
                        "The ledger envelope is not the exact current canonical producer shape.",
                        metadata={"findings": list(envelope_findings)},
                    ),
                ),
            )
        return BehaviorLedgerMigrationResult(
            ARTIFACT_UPGRADE_STATUS_UNCHANGED,
            mapping=original,
            migrated_commitment_ids=tuple(
                str(row.get("commitment_id", ""))
                for row in original["ledger"]["commitments"]
                if isinstance(row, Mapping)
            ),
        )
    if not _has_exact_legacy_behavior_ledger_shape(original):
        return BehaviorLedgerMigrationResult(
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            findings=(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_legacy_shape_unregistered",
                    "The mapping is not the exact historical FlowGuard ledger producer shape.",
                ),
            ),
        )
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
    findings: list[BehaviorLedgerMigrationFinding] = []
    migrated_rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    classification_reasons: dict[str, tuple[str, ...]] = {}
    if "behavior_plane_migration" in ledger["metadata"]:
        findings.append(
            BehaviorLedgerMigrationFinding(
                "behavior_ledger_migration_metadata_collision",
                "Historical ledger metadata already owns the current migration provenance key.",
                metadata={"key": "behavior_plane_migration"},
            )
        )
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
        plane, actor_kind, reasons = _explicit_legacy_plane_actor(row)
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
        primary_path_ids = row["path_authority"]["primary_path_ids"]
        path_metadata = row["path_authority"]["metadata"]
        if "legacy_primary_path_ids" in path_metadata:
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_retired_path_metadata_residual",
                    "Retired legacy_primary_path_ids metadata requires an explicit current disposition before migration.",
                    commitment_id=commitment_id,
                )
            )
        if primary_path_ids and "historical_primary_path_migration" in path_metadata:
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_path_migration_metadata_collision",
                    "Historical path metadata already owns the current migration provenance key.",
                    commitment_id=commitment_id,
                    metadata={"key": "historical_primary_path_migration"},
                )
            )
        if len(primary_path_ids) > 1:
            findings.append(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_primary_path_requires_manual_classification",
                    "Multiple historical primary_path_ids cannot be reduced to one current primary path without explicit evidence.",
                    commitment_id=commitment_id,
                    metadata={"primary_path_ids": list(primary_path_ids)},
                )
            )
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

    metadata = dict(ledger.get("metadata") or {})
    metadata["behavior_plane_migration"] = {
        "source_format": str(original.get("format_version", "legacy_mapping")),
        "source_shape_id": _LEGACY_BCL_SHAPE_ID,
        "classification_reasons": {
            key: list(values) for key, values in sorted(classification_reasons.items())
        },
    }
    current_ledger = {
        "ledger_id": ledger["ledger_id"],
        "project_boundary": ledger["project_boundary"],
        "current_revision": ledger["current_revision"],
        "commitments": [
            _materialize_current_commitment(row) for row in migrated_rows
        ],
        "source_surfaces": [
            _materialize_current_source_surface(surface)
            for surface in ledger["source_surfaces"]
        ],
        "expected_commitment_ids": list(ledger["expected_commitment_ids"]),
        "expected_business_intent_ids": [],
        "claim_scope": ledger["claim_scope"],
        "change_mode": ledger["change_mode"],
        "require_current_evidence": ledger["require_current_evidence"],
        "require_risk_gates_for_broad_claim": ledger[
            "require_risk_gates_for_broad_claim"
        ],
        "owner": ledger["owner"],
        "validation_boundary": ledger["validation_boundary"],
        "rationale": ledger["rationale"],
        "metadata": metadata,
    }
    upgraded_candidate = {
        "artifact_type": BCL_LEDGER_ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "format_version": BCL_LEDGER_FORMAT_VERSION,
        "ledger": current_ledger,
    }
    try:
        upgraded = behavior_commitment_ledger_to_mapping(
            behavior_commitment_ledger_from_mapping(upgraded_candidate)
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return BehaviorLedgerMigrationResult(
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            findings=(
                BehaviorLedgerMigrationFinding(
                    "behavior_ledger_current_materialization_failed",
                    "The exact historical ledger could not be materialized as one current canonical envelope.",
                    metadata={"error_type": type(exc).__name__},
                ),
            ),
        )
    return BehaviorLedgerMigrationResult(
        ARTIFACT_UPGRADE_STATUS_UPGRADED,
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
            metadata={
                "legacy_shape_id": (
                    _LEGACY_BCL_SHAPE_ID
                    if migration.status == ARTIFACT_UPGRADE_STATUS_UPGRADED
                    else ""
                ),
                "migrated_commitment_ids": list(migration.migrated_commitment_ids),
            },
        )
    registration = _registered_flowguard_json_artifact(data)
    if registration is None:
        return None

    shape_findings = _registration_shape_findings(data, registration)
    if shape_findings:
        return ArtifactUpgradeItem(
            rel_path,
            "registered_json_artifact",
            ARTIFACT_UPGRADE_STATUS_BLOCKED,
            detected_shape="malformed_registered_artifact",
            message="registered FlowGuard artifact does not match its exact producer shape",
            metadata={
                "artifact_type": registration.artifact_type,
                "version_field": registration.version_field,
                "findings": list(shape_findings),
            },
        )
    schema_version = data[registration.version_field]
    if schema_version in registration.current_versions:
        return ArtifactUpgradeItem(
            rel_path,
            "registered_json_artifact",
            ARTIFACT_UPGRADE_STATUS_UNCHANGED,
            detected_shape=f"schema_version:{schema_version}",
            message="registered FlowGuard artifact already uses the current schema",
            metadata={
                "artifact_type": registration.artifact_type,
                "version_field": registration.version_field,
                "current_versions": sorted(registration.current_versions),
            },
        )

    return ArtifactUpgradeItem(
        rel_path,
        "registered_json_artifact",
        ARTIFACT_UPGRADE_STATUS_BLOCKED,
        detected_shape=f"schema_version:{schema_version}",
        message=(
            "registered FlowGuard artifact version has no evidence-bound migration"
        ),
        metadata={
            "artifact_type": registration.artifact_type,
            "version_field": registration.version_field,
            "current_versions": sorted(registration.current_versions),
        },
    )


def _registered_flowguard_json_artifact(
    data: Mapping[str, Any],
) -> FlowGuardJsonArtifactRegistration | None:
    artifact_type = str(data.get("artifact_type", ""))
    return _FLOWGUARD_JSON_ARTIFACT_REGISTRY.get(artifact_type)


def _registration_shape_findings(
    data: Mapping[str, Any],
    registration: FlowGuardJsonArtifactRegistration,
) -> tuple[str, ...]:
    findings: list[str] = []
    actual_fields = set(data)
    missing = sorted(registration.allowed_fields - actual_fields)
    extra = sorted(actual_fields - registration.allowed_fields)
    if missing:
        findings.append(f"missing_fields:{','.join(missing)}")
    if extra:
        findings.append(f"extra_fields:{','.join(extra)}")
    for field, expected_type in registration.field_types:
        if field in data and not isinstance(data[field], expected_type):
            findings.append(
                f"field_type:{field}:{type(data[field]).__name__}!={expected_type.__name__}"
            )
    for field, expected in registration.required_values:
        if field in data and data[field] != expected:
            findings.append(f"field_value:{field}:{data[field]!r}!={expected!r}")
    return tuple(findings)


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
