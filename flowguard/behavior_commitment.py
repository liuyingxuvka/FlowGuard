"""Project-level behavior commitment coverage ledger.

The ledger is the upstream account book for user-visible or externally
reliable behavior. It answers "what behavior did we promise and who owns it?"
Path-sensitive rows then hand off to Primary Path Authority for the stricter
"one runtime path, no automatic alternate success" rule.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_exhaustion import (
    CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    ContractAxis,
    ContractCoverageUniverse,
    ContractExhaustionPlan,
    ContractInteractionGroup,
    ContractOracle,
)
from .export import to_jsonable
from .behavior_plane import (
    BCL_BEHAVIOR_PLANES,
    BCL_PLANE_AGENT_OPERATION,
    BCL_PLANE_DEVELOPMENT_PROCESS,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_PLANE_UNCLASSIFIED,
)
from .schema import SCHEMA_VERSION
from .primary_path_authority import (
    PPA_CONFIDENCE_BLOCKED,
    PPA_CONFIDENCE_FULL,
    PPA_DECISION_BLOCKED,
    PPA_DECISION_GREEN,
    PPA_RISK_GATE_AUTHORITY,
    PPA_RISK_GATE_CARTESIAN_COVERAGE,
    PRIMARY_PATH_ROUTE_ID,
    PrimaryPathAuthorityReport,
)


BEHAVIOR_COMMITMENT_ROUTE_ID = "behavior_commitment_ledger"
BEHAVIOR_COMMITMENT_ORACLE_ID = "behavior_commitment_coverage_must_block"

BCL_SCOPE_ROUTINE = "routine"
BCL_SCOPE_DONE = "done"
BCL_SCOPE_RELEASE = "release"
BCL_SCOPE_PUBLISH = "publish"
BCL_SCOPE_PRODUCTION = "production"
BCL_SCOPE_ARCHIVE = "archive"
BCL_SCOPE_FULL = "full"
BCL_BROAD_CLAIM_SCOPES = {
    BCL_SCOPE_DONE,
    BCL_SCOPE_RELEASE,
    BCL_SCOPE_PUBLISH,
    BCL_SCOPE_PRODUCTION,
    BCL_SCOPE_ARCHIVE,
    BCL_SCOPE_FULL,
}

BCL_DECISION_GREEN = "behavior_commitment_coverage_green"
BCL_DECISION_SCOPED = "behavior_commitment_coverage_scoped"
BCL_DECISION_BLOCKED = "behavior_commitment_coverage_blocked"
BCL_CONFIDENCE_FULL = "full"
BCL_CONFIDENCE_SCOPED = "scoped"
BCL_CONFIDENCE_BLOCKED = "blocked"

BCL_SEVERITY_BLOCKER = "blocker"
BCL_SEVERITY_WARNING = "warning"

BCL_COMMITMENT_PUBLIC_API = "public_api"
BCL_COMMITMENT_CLI = "cli"
BCL_COMMITMENT_UI = "ui"
BCL_COMMITMENT_SKILL = "skill"
BCL_COMMITMENT_WORKFLOW = "workflow"
BCL_COMMITMENT_DOC = "doc"
BCL_COMMITMENT_RELEASE = "release"
BCL_COMMITMENT_PROCESS = "process"
BCL_COMMITMENT_KINDS = (
    BCL_COMMITMENT_PUBLIC_API,
    BCL_COMMITMENT_CLI,
    BCL_COMMITMENT_UI,
    BCL_COMMITMENT_SKILL,
    BCL_COMMITMENT_WORKFLOW,
    BCL_COMMITMENT_DOC,
    BCL_COMMITMENT_RELEASE,
    BCL_COMMITMENT_PROCESS,
)

BCL_ACTOR_END_USER = "end_user"
BCL_ACTOR_EXTERNAL_SYSTEM = "external_system"
BCL_ACTOR_APPLICATION = "application"
BCL_ACTOR_AI_AGENT = "ai_agent"
BCL_ACTOR_DEVELOPER = "developer"
BCL_ACTOR_AUTOMATION = "automation"
BCL_ACTOR_KINDS = (
    BCL_ACTOR_END_USER,
    BCL_ACTOR_EXTERNAL_SYSTEM,
    BCL_ACTOR_APPLICATION,
    BCL_ACTOR_AI_AGENT,
    BCL_ACTOR_DEVELOPER,
    BCL_ACTOR_AUTOMATION,
)

BCL_RELATION_DEPENDS_ON = "depends_on"
BCL_RELATION_INVOKES = "invokes"
BCL_RELATION_VALIDATES = "validates"
BCL_RELATION_GOVERNS = "governs"
BCL_RELATION_REQUIRES_EVIDENCE_FROM = "requires_evidence_from"
BCL_RELATION_TYPES = (
    BCL_RELATION_DEPENDS_ON,
    BCL_RELATION_INVOKES,
    BCL_RELATION_VALIDATES,
    BCL_RELATION_GOVERNS,
    BCL_RELATION_REQUIRES_EVIDENCE_FROM,
)

BCL_LOOKUP_STATUS_PERFORMED = "performed"
BCL_LOOKUP_STATUS_NOT_APPLICABLE = "not_applicable"
BCL_LOOKUP_STATUS_BLOCKED = "blocked"
BCL_LOOKUP_STATUSES = (
    BCL_LOOKUP_STATUS_PERFORMED,
    BCL_LOOKUP_STATUS_NOT_APPLICABLE,
    BCL_LOOKUP_STATUS_BLOCKED,
)

BCL_HIT_ROLE_PRIMARY = "primary"
BCL_HIT_ROLE_INVOKED_TARGET = "invoked_target"
BCL_HIT_ROLE_VALIDATION_TARGET = "validation_target"
BCL_HIT_ROLE_GOVERNING_PROCESS = "governing_process"
BCL_HIT_ROLE_EVIDENCE_SOURCE = "evidence_source"
BCL_HIT_ROLES = (
    BCL_HIT_ROLE_PRIMARY,
    BCL_HIT_ROLE_INVOKED_TARGET,
    BCL_HIT_ROLE_VALIDATION_TARGET,
    BCL_HIT_ROLE_GOVERNING_PROCESS,
    BCL_HIT_ROLE_EVIDENCE_SOURCE,
)

BCL_LEDGER_ARTIFACT_TYPE = "flowguard_behavior_commitment_ledger"
BCL_LEDGER_FORMAT_VERSION = "1"

BCL_SOURCE_CODE = "code"
BCL_SOURCE_API = "api"
BCL_SOURCE_CLI = "cli"
BCL_SOURCE_UI = "ui"
BCL_SOURCE_DOC = "doc"
BCL_SOURCE_SKILL = "skill"
BCL_SOURCE_TEST = "test"
BCL_SOURCE_OPENSPEC = "openspec"
BCL_SOURCE_RELEASE = "release"
BCL_SOURCE_PROCESS = "process"
BCL_SOURCE_KINDS = (
    BCL_SOURCE_CODE,
    BCL_SOURCE_API,
    BCL_SOURCE_CLI,
    BCL_SOURCE_UI,
    BCL_SOURCE_DOC,
    BCL_SOURCE_SKILL,
    BCL_SOURCE_TEST,
    BCL_SOURCE_OPENSPEC,
    BCL_SOURCE_RELEASE,
    BCL_SOURCE_PROCESS,
)

BCL_EVIDENCE_CURRENT_PASS = "current_pass"
BCL_EVIDENCE_MISSING = "missing"
BCL_EVIDENCE_STALE = "stale"
BCL_EVIDENCE_PROGRESS_ONLY = "progress_only"
BCL_EVIDENCE_SKIPPED = "skipped"
BCL_EVIDENCE_BLOCKED = "blocked"
BCL_EVIDENCE_STATES = (
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_EVIDENCE_MISSING,
    BCL_EVIDENCE_STALE,
    BCL_EVIDENCE_PROGRESS_ONLY,
    BCL_EVIDENCE_SKIPPED,
    BCL_EVIDENCE_BLOCKED,
)

BCL_CHANGE_BOOTSTRAP_LEDGER = "bootstrap_ledger"
BCL_CHANGE_ADD_BEHAVIOR = "add_behavior"
BCL_CHANGE_CHANGE_BEHAVIOR = "change_behavior"
BCL_CHANGE_REMOVE_OR_REPLACE_BEHAVIOR = "remove_or_replace_behavior"
BCL_CHANGE_COVERAGE_GAP_BACKFILL = "coverage_gap_backfill"
BCL_CHANGE_MODEL_MISS_CHECK = "model_miss_check"
BCL_CHANGE_MODES = (
    BCL_CHANGE_BOOTSTRAP_LEDGER,
    BCL_CHANGE_ADD_BEHAVIOR,
    BCL_CHANGE_CHANGE_BEHAVIOR,
    BCL_CHANGE_REMOVE_OR_REPLACE_BEHAVIOR,
    BCL_CHANGE_COVERAGE_GAP_BACKFILL,
    BCL_CHANGE_MODEL_MISS_CHECK,
)

BCL_SOURCE_FRESHNESS_CURRENT = "current"
BCL_SOURCE_FRESHNESS_CHANGED = "changed_since_ledger"
BCL_SOURCE_FRESHNESS_MISSING = "missing_source"
BCL_SOURCE_FRESHNESS_UNCHECKED = "unchecked_source"
BCL_SOURCE_FRESHNESS_STATES = (
    BCL_SOURCE_FRESHNESS_CURRENT,
    BCL_SOURCE_FRESHNESS_CHANGED,
    BCL_SOURCE_FRESHNESS_MISSING,
    BCL_SOURCE_FRESHNESS_UNCHECKED,
)

BCL_REPLACEMENT_ACTIVE = "active"
BCL_REPLACEMENT_DEPRECATED = "deprecated"
BCL_REPLACEMENT_REPLACED = "replaced"
BCL_REPLACEMENT_REMOVED_SCOPED_OUT = "removed_scoped_out"
BCL_REPLACEMENT_STATES = (
    BCL_REPLACEMENT_ACTIVE,
    BCL_REPLACEMENT_DEPRECATED,
    BCL_REPLACEMENT_REPLACED,
    BCL_REPLACEMENT_REMOVED_SCOPED_OUT,
)

BCL_MODEL_SYNC_OWNER_CURRENT = "owner_model_current"
BCL_MODEL_SYNC_OWNER_MISSING = "owner_model_missing"
BCL_MODEL_SYNC_OWNER_STALE = "owner_model_stale"
BCL_MODEL_SYNC_SIBLING_UNCHECKED = "sibling_unchecked"
BCL_MODEL_SYNC_CHILD_NEEDED = "child_model_needed"
BCL_MODEL_SYNC_STATES = (
    BCL_MODEL_SYNC_OWNER_CURRENT,
    BCL_MODEL_SYNC_OWNER_MISSING,
    BCL_MODEL_SYNC_OWNER_STALE,
    BCL_MODEL_SYNC_SIBLING_UNCHECKED,
    BCL_MODEL_SYNC_CHILD_NEEDED,
)

BCL_TEST_MESH_SHARD_CURRENT = "shard_current"
BCL_TEST_MESH_SHARD_MISSING = "shard_missing"
BCL_TEST_MESH_PROGRESS_ONLY = "progress_only"
BCL_TEST_MESH_STALE = "stale"
BCL_TEST_MESH_RELEASE_ONLY = "release_only"
BCL_TEST_MESH_STATES = (
    BCL_TEST_MESH_SHARD_CURRENT,
    BCL_TEST_MESH_SHARD_MISSING,
    BCL_TEST_MESH_PROGRESS_ONLY,
    BCL_TEST_MESH_STALE,
    BCL_TEST_MESH_RELEASE_ONLY,
)

BCL_MISS_ORIGIN_NONE = "no_miss"
BCL_MISS_ORIGIN_OBSERVED = "observed_model_miss"
BCL_MISS_ORIGIN_SAME_CLASS_SEED = "same_class_seed"
BCL_MISS_ORIGIN_RECURRING_FAMILY = "recurring_family"
BCL_MISS_ORIGIN_STATES = (
    BCL_MISS_ORIGIN_NONE,
    BCL_MISS_ORIGIN_OBSERVED,
    BCL_MISS_ORIGIN_SAME_CLASS_SEED,
    BCL_MISS_ORIGIN_RECURRING_FAMILY,
)

BCL_PPA_NOT_REQUIRED = "not_required"
BCL_PPA_MISSING = "ppa_missing"
BCL_PPA_PASSED = "ppa_passed"
BCL_PPA_BLOCKED = "ppa_blocked"
BCL_PPA_RESULTS = (
    BCL_PPA_NOT_REQUIRED,
    BCL_PPA_MISSING,
    BCL_PPA_PASSED,
    BCL_PPA_BLOCKED,
)

BCL_RISK_GATE_COVERAGE = "behavior_commitment_coverage"
BCL_RISK_GATE_CARTESIAN_COVERAGE = "behavior_commitment_cartesian_coverage"

BCL_EXTERNAL_DIFFERENCE_PRECONDITION = "precondition"
BCL_EXTERNAL_DIFFERENCE_TERMINAL = "terminal"
BCL_EXTERNAL_DIFFERENCE_STATE_WRITE = "state_write"
BCL_EXTERNAL_DIFFERENCE_SIDE_EFFECT = "side_effect"
BCL_EXTERNAL_DIFFERENCE_FAILURE_BOUNDARY = "failure_boundary"
BCL_EXTERNAL_DIFFERENCE_PUBLIC_SURFACE = "public_surface"
BCL_EXTERNAL_DIFFERENCE_KINDS = (
    BCL_EXTERNAL_DIFFERENCE_PRECONDITION,
    BCL_EXTERNAL_DIFFERENCE_TERMINAL,
    BCL_EXTERNAL_DIFFERENCE_STATE_WRITE,
    BCL_EXTERNAL_DIFFERENCE_SIDE_EFFECT,
    BCL_EXTERNAL_DIFFERENCE_FAILURE_BOUNDARY,
    BCL_EXTERNAL_DIFFERENCE_PUBLIC_SURFACE,
)


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _metadata(values: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(values or {})


def _coerce_surface(value: "BehaviorSourceSurface | Mapping[str, Any]") -> "BehaviorSourceSurface":
    if isinstance(value, BehaviorSourceSurface):
        return value
    return BehaviorSourceSurface(**dict(value))


def _coerce_commitment(value: "BehaviorCommitment | Mapping[str, Any]") -> "BehaviorCommitment":
    if isinstance(value, BehaviorCommitment):
        return value
    return BehaviorCommitment(**dict(value))


def _coerce_path_binding(value: "BehaviorPathAuthorityBinding | Mapping[str, Any] | None") -> "BehaviorPathAuthorityBinding":
    if value is None:
        return BehaviorPathAuthorityBinding()
    if isinstance(value, BehaviorPathAuthorityBinding):
        return value
    data = dict(value)
    former_fields = {
        "legacy_primary_path_ids",
        "primary_path_ids",
        "legacy_plural_migrated",
        "primary_path_migration_ambiguous",
    }
    present = sorted(former_fields.intersection(data))
    metadata = data.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("legacy_primary_path_ids"):
        present.append("metadata.legacy_primary_path_ids")
    if present:
        raise ValueError(
            "former path-authority fields are not accepted; author primary_path_id directly: "
            + ", ".join(present)
        )
    return BehaviorPathAuthorityBinding(**data)


def _coerce_evidence(value: "BehaviorEvidenceBinding | Mapping[str, Any] | None") -> "BehaviorEvidenceBinding":
    if value is None:
        return BehaviorEvidenceBinding()
    if isinstance(value, BehaviorEvidenceBinding):
        return value
    return BehaviorEvidenceBinding(**dict(value))


def _coerce_external_difference(
    value: "BehaviorExternalDifference | Mapping[str, Any]",
) -> "BehaviorExternalDifference":
    if isinstance(value, BehaviorExternalDifference):
        return value
    return BehaviorExternalDifference(**dict(value))


@dataclass(frozen=True)
class BehaviorSourceSurface:
    """A source surface that promises or exposes behavior."""

    surface_id: str
    surface_kind: str = BCL_SOURCE_CODE
    label: str = ""
    source_ref: str = ""
    commitment_ids: tuple[str, ...] = ()
    business_intent_ids: tuple[str, ...] = ()
    primary_path_id: str = ""
    delegates_to_primary_path: bool = False
    similarity_relation_ids: tuple[str, ...] = ()
    similarity_obligation_ids: tuple[str, ...] = ()
    freshness_state: str = BCL_SOURCE_FRESHNESS_CURRENT
    in_scope: bool = True
    scoped_out_reason: str = ""
    owner: str = ""
    validation_boundary: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "surface_kind", str(self.surface_kind or BCL_SOURCE_CODE))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "source_ref", str(self.source_ref))
        object.__setattr__(self, "commitment_ids", _as_tuple(self.commitment_ids))
        object.__setattr__(self, "business_intent_ids", _as_tuple(self.business_intent_ids))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "delegates_to_primary_path", bool(self.delegates_to_primary_path))
        object.__setattr__(self, "similarity_relation_ids", _as_tuple(self.similarity_relation_ids))
        object.__setattr__(self, "similarity_obligation_ids", _as_tuple(self.similarity_obligation_ids))
        object.__setattr__(self, "freshness_state", str(self.freshness_state or BCL_SOURCE_FRESHNESS_CURRENT))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "validation_boundary", str(self.validation_boundary))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def has_scoped_disposition(self) -> bool:
        return bool(self.scoped_out_reason and self.owner and self.validation_boundary and self.rationale)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "label": self.label,
            "source_ref": self.source_ref,
            "commitment_ids": list(self.commitment_ids),
            "business_intent_ids": list(self.business_intent_ids),
            "primary_path_id": self.primary_path_id,
            "delegates_to_primary_path": self.delegates_to_primary_path,
            "similarity_relation_ids": list(self.similarity_relation_ids),
            "similarity_obligation_ids": list(self.similarity_obligation_ids),
            "freshness_state": self.freshness_state,
            "in_scope": self.in_scope,
            "scoped_out_reason": self.scoped_out_reason,
            "owner": self.owner,
            "validation_boundary": self.validation_boundary,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorExternalDifference:
    """Typed, externally observable difference that licenses a variant intent."""

    difference_id: str
    difference_kind: str
    baseline_value: str = ""
    variant_value: str = ""
    evidence_ids: tuple[str, ...] = ()
    evidence_current: bool = True
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "difference_id", str(self.difference_id))
        object.__setattr__(self, "difference_kind", str(self.difference_kind))
        object.__setattr__(self, "baseline_value", str(self.baseline_value))
        object.__setattr__(self, "variant_value", str(self.variant_value))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "evidence_current", bool(self.evidence_current))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def complete(self) -> bool:
        return bool(
            self.difference_id
            and self.difference_kind in BCL_EXTERNAL_DIFFERENCE_KINDS
            and self.baseline_value
            and self.variant_value
            and self.baseline_value != self.variant_value
            and self.evidence_ids
            and self.evidence_current
            and self.rationale
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "difference_id": self.difference_id,
            "difference_kind": self.difference_kind,
            "baseline_value": self.baseline_value,
            "variant_value": self.variant_value,
            "evidence_ids": list(self.evidence_ids),
            "evidence_current": self.evidence_current,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorEvidenceBinding:
    """Evidence ids that prove one behavior commitment."""

    model_obligation_ids: tuple[str, ...] = ()
    code_contract_ids: tuple[str, ...] = ()
    test_evidence_ids: tuple[str, ...] = ()
    proof_artifact_ids: tuple[str, ...] = ()
    risk_gate_ids: tuple[str, ...] = ()
    coverage_case_ids: tuple[str, ...] = ()
    coverage_shard_ids: tuple[str, ...] = ()
    coverage_receipt_ids: tuple[str, ...] = ()
    evidence_state: str = BCL_EVIDENCE_MISSING
    test_mesh_state: str = BCL_TEST_MESH_SHARD_CURRENT
    current: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_obligation_ids", _as_tuple(self.model_obligation_ids))
        object.__setattr__(self, "code_contract_ids", _as_tuple(self.code_contract_ids))
        object.__setattr__(self, "test_evidence_ids", _as_tuple(self.test_evidence_ids))
        object.__setattr__(self, "proof_artifact_ids", _as_tuple(self.proof_artifact_ids))
        object.__setattr__(self, "risk_gate_ids", _as_tuple(self.risk_gate_ids))
        object.__setattr__(self, "coverage_case_ids", _as_tuple(self.coverage_case_ids))
        object.__setattr__(self, "coverage_shard_ids", _as_tuple(self.coverage_shard_ids))
        object.__setattr__(self, "coverage_receipt_ids", _as_tuple(self.coverage_receipt_ids))
        object.__setattr__(self, "evidence_state", str(self.evidence_state or BCL_EVIDENCE_MISSING))
        object.__setattr__(self, "test_mesh_state", str(self.test_mesh_state or BCL_TEST_MESH_SHARD_CURRENT))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def has_current_pass(self) -> bool:
        return self.current and self.evidence_state == BCL_EVIDENCE_CURRENT_PASS

    def has_required_links(self) -> bool:
        return bool(self.model_obligation_ids and self.code_contract_ids and self.test_evidence_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_obligation_ids": list(self.model_obligation_ids),
            "code_contract_ids": list(self.code_contract_ids),
            "test_evidence_ids": list(self.test_evidence_ids),
            "proof_artifact_ids": list(self.proof_artifact_ids),
            "risk_gate_ids": list(self.risk_gate_ids),
            "coverage_case_ids": list(self.coverage_case_ids),
            "coverage_shard_ids": list(self.coverage_shard_ids),
            "coverage_receipt_ids": list(self.coverage_receipt_ids),
            "evidence_state": self.evidence_state,
            "test_mesh_state": self.test_mesh_state,
            "current": self.current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorLookupBinding:
    """Stable, bounded clues used to recall one registered commitment."""

    task_terms: tuple[str, ...] = ()
    path_patterns: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    error_signatures: tuple[str, ...] = ()
    workflow_families: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_terms", _as_tuple(self.task_terms))
        object.__setattr__(self, "path_patterns", _as_tuple(self.path_patterns))
        object.__setattr__(self, "tool_ids", _as_tuple(self.tool_ids))
        object.__setattr__(self, "error_signatures", _as_tuple(self.error_signatures))
        object.__setattr__(self, "workflow_families", _as_tuple(self.workflow_families))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_terms": list(self.task_terms),
            "path_patterns": list(self.path_patterns),
            "tool_ids": list(self.tool_ids),
            "error_signatures": list(self.error_signatures),
            "workflow_families": list(self.workflow_families),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorCommitmentRelation:
    """One typed same-plane or cross-plane commitment relationship."""

    target_commitment_id: str
    relation_type: str = BCL_RELATION_DEPENDS_ON
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_commitment_id", str(self.target_commitment_id))
        object.__setattr__(self, "relation_type", str(self.relation_type or BCL_RELATION_DEPENDS_ON))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_commitment_id": self.target_commitment_id,
            "relation_type": self.relation_type,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def _coerce_lookup_binding(
    value: BehaviorLookupBinding | Mapping[str, Any] | None,
) -> BehaviorLookupBinding:
    if value is None:
        return BehaviorLookupBinding()
    if isinstance(value, BehaviorLookupBinding):
        return value
    return BehaviorLookupBinding(**dict(value))


def _coerce_relation(
    value: BehaviorCommitmentRelation | Mapping[str, Any],
) -> BehaviorCommitmentRelation:
    if isinstance(value, BehaviorCommitmentRelation):
        return value
    return BehaviorCommitmentRelation(**dict(value))


def behavior_commitment_relation_allowed(
    source_plane: str,
    target_plane: str,
    relation_type: str,
) -> bool:
    """Return whether the declared relation preserves plane ownership."""

    source = str(source_plane)
    target = str(target_plane)
    relation = str(relation_type)
    if source == target and source in BCL_BEHAVIOR_PLANES:
        return relation in {
            BCL_RELATION_DEPENDS_ON,
            BCL_RELATION_INVOKES,
            BCL_RELATION_VALIDATES,
        }
    if source == BCL_PLANE_AGENT_OPERATION and target == BCL_PLANE_PRODUCT_RUNTIME:
        return relation in {BCL_RELATION_INVOKES, BCL_RELATION_VALIDATES}
    if source == BCL_PLANE_DEVELOPMENT_PROCESS and target in {
        BCL_PLANE_AGENT_OPERATION,
        BCL_PLANE_PRODUCT_RUNTIME,
    }:
        return relation in {
            BCL_RELATION_GOVERNS,
            BCL_RELATION_VALIDATES,
            BCL_RELATION_REQUIRES_EVIDENCE_FROM,
        }
    return False


@dataclass(frozen=True)
class BehaviorPathAuthorityBinding:
    """PPA binding for a path-sensitive behavior commitment."""

    path_sensitive: bool = False
    business_intent: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    ppa_report_id: str = ""
    ppa_decision: str = ""
    ppa_confidence: str = ""
    ppa_ok: bool | None = None
    primary_path_id: str = ""
    fallback_candidate_ids: tuple[str, ...] = ()
    ppa_coverage_receipt_ids: tuple[str, ...] = ()
    ppa_coverage_shard_ids: tuple[str, ...] = ()
    ppa_risk_gate_ids: tuple[str, ...] = ()
    scoped_out_reason: str = ""
    evidence_refs: tuple[str, ...] = ()
    runtime_observation_ids: tuple[str, ...] = ()
    proof_artifact_ids: tuple[str, ...] = ()
    evidence_current: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_sensitive", bool(self.path_sensitive))
        object.__setattr__(self, "business_intent", str(self.business_intent))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "ppa_report_id", str(self.ppa_report_id))
        object.__setattr__(self, "ppa_decision", str(self.ppa_decision))
        object.__setattr__(self, "ppa_confidence", str(self.ppa_confidence))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "fallback_candidate_ids", _as_tuple(self.fallback_candidate_ids))
        object.__setattr__(self, "ppa_coverage_receipt_ids", _as_tuple(self.ppa_coverage_receipt_ids))
        object.__setattr__(self, "ppa_coverage_shard_ids", _as_tuple(self.ppa_coverage_shard_ids))
        object.__setattr__(self, "ppa_risk_gate_ids", _as_tuple(self.ppa_risk_gate_ids))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "runtime_observation_ids", _as_tuple(self.runtime_observation_ids))
        object.__setattr__(self, "proof_artifact_ids", _as_tuple(self.proof_artifact_ids))
        object.__setattr__(self, "evidence_current", bool(self.evidence_current))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def has_ppa_evidence(self) -> bool:
        return bool(
            self.ppa_report_id
            or self.ppa_decision
            or self.ppa_coverage_receipt_ids
            or self.ppa_risk_gate_ids
            or self.evidence_refs
            or self.runtime_observation_ids
            or self.proof_artifact_ids
        )

    def ppa_blocked(self) -> bool:
        return (
            self.ppa_ok is False
            or self.ppa_decision == PPA_DECISION_BLOCKED
            or self.ppa_confidence == PPA_CONFIDENCE_BLOCKED
        )

    def ppa_passed(self) -> bool:
        return bool(
            self.ppa_ok is True
            and self.ppa_decision == PPA_DECISION_GREEN
            and self.ppa_confidence == PPA_CONFIDENCE_FULL
            and self.primary_path_id
            and self.business_intent_id
            and self.behavior_commitment_id
            and self.runtime_observation_ids
            and self.proof_artifact_ids
            and self.evidence_current
        )

    def ppa_result(self) -> str:
        if not self.path_sensitive:
            return BCL_PPA_NOT_REQUIRED
        if self.ppa_blocked():
            return BCL_PPA_BLOCKED
        if not self.has_ppa_evidence():
            return BCL_PPA_MISSING
        if self.ppa_passed():
            return BCL_PPA_PASSED
        return BCL_PPA_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_sensitive": self.path_sensitive,
            "business_intent": self.business_intent,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "ppa_report_id": self.ppa_report_id,
            "ppa_decision": self.ppa_decision,
            "ppa_confidence": self.ppa_confidence,
            "ppa_ok": self.ppa_ok,
            "primary_path_id": self.primary_path_id,
            "fallback_candidate_ids": list(self.fallback_candidate_ids),
            "ppa_coverage_receipt_ids": list(self.ppa_coverage_receipt_ids),
            "ppa_coverage_shard_ids": list(self.ppa_coverage_shard_ids),
            "ppa_risk_gate_ids": list(self.ppa_risk_gate_ids),
            "scoped_out_reason": self.scoped_out_reason,
            "evidence_refs": list(self.evidence_refs),
            "runtime_observation_ids": list(self.runtime_observation_ids),
            "proof_artifact_ids": list(self.proof_artifact_ids),
            "evidence_current": self.evidence_current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def behavior_path_binding_from_primary_path_report(
    report: PrimaryPathAuthorityReport,
    *,
    business_intent: str = "",
    business_intent_id: str = "",
    behavior_commitment_id: str = "",
    ppa_report_id: str | None = None,
    path_sensitive: bool = True,
    evidence_refs: Sequence[str] | None = None,
) -> BehaviorPathAuthorityBinding:
    """Create a ledger path binding from a PPA report."""

    return BehaviorPathAuthorityBinding(
        path_sensitive=path_sensitive,
        business_intent=business_intent,
        business_intent_id=business_intent_id or report.business_intent_id,
        behavior_commitment_id=behavior_commitment_id or report.behavior_commitment_id,
        ppa_report_id=ppa_report_id or report.plan_id,
        ppa_decision=report.decision,
        ppa_confidence=report.confidence,
        ppa_ok=report.ok,
        primary_path_id=report.primary_path_id,
        fallback_candidate_ids=report.fallback_candidate_ids,
        ppa_coverage_receipt_ids=report.coverage_receipt_ids,
        ppa_coverage_shard_ids=report.coverage_shard_ids,
        ppa_risk_gate_ids=report.risk_gate_ids,
        evidence_refs=evidence_refs or (report.plan_id,),
        runtime_observation_ids=report.runtime_observation_ids,
        proof_artifact_ids=report.proof_artifact_ids,
        evidence_current=report.evidence_current,
    )


@dataclass(frozen=True)
class BehaviorCommitment:
    """One external behavior promise and its single primary model owner."""

    commitment_id: str
    business_intent_id: str = ""
    label: str = ""
    commitment_kind: str = BCL_COMMITMENT_WORKFLOW
    behavior_plane: str = ""
    actor_kind: str = ""
    actor: str = ""
    trigger: str = ""
    expected_result: str = ""
    failure_boundary: str = ""
    preconditions: tuple[str, ...] = ()
    expected_terminal: str = ""
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    variant_of_business_intent_id: str = ""
    external_differences: tuple[BehaviorExternalDifference | Mapping[str, Any], ...] = ()
    similarity_relation_ids: tuple[str, ...] = ()
    similarity_obligation_ids: tuple[str, ...] = ()
    surface_delegation_only: bool = False
    source_surface_ids: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    primary_owner_model_id: str = ""
    supporting_model_ids: tuple[str, ...] = ()
    child_model_ids: tuple[str, ...] = ()
    relations: tuple[BehaviorCommitmentRelation | Mapping[str, Any], ...] = ()
    lookup_binding: BehaviorLookupBinding | Mapping[str, Any] | None = None
    excluded_behavior_ids: tuple[str, ...] = ()
    replacement_state: str = BCL_REPLACEMENT_ACTIVE
    model_sync_state: str = BCL_MODEL_SYNC_OWNER_CURRENT
    miss_origin_state: str = BCL_MISS_ORIGIN_NONE
    path_authority: BehaviorPathAuthorityBinding | Mapping[str, Any] | None = None
    evidence: BehaviorEvidenceBinding | Mapping[str, Any] | None = None
    in_scope: bool = True
    scoped_out_reason: str = ""
    owner: str = ""
    validation_boundary: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", str(self.commitment_id))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "commitment_kind", str(self.commitment_kind or BCL_COMMITMENT_WORKFLOW))
        object.__setattr__(self, "behavior_plane", str(self.behavior_plane))
        object.__setattr__(self, "actor_kind", str(self.actor_kind))
        object.__setattr__(self, "actor", str(self.actor))
        object.__setattr__(self, "trigger", str(self.trigger))
        object.__setattr__(self, "expected_result", str(self.expected_result))
        object.__setattr__(self, "failure_boundary", str(self.failure_boundary))
        object.__setattr__(self, "preconditions", _as_tuple(self.preconditions))
        object.__setattr__(self, "expected_terminal", str(self.expected_terminal))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "variant_of_business_intent_id", str(self.variant_of_business_intent_id))
        object.__setattr__(
            self,
            "external_differences",
            tuple(_coerce_external_difference(item) for item in self.external_differences),
        )
        object.__setattr__(self, "similarity_relation_ids", _as_tuple(self.similarity_relation_ids))
        object.__setattr__(self, "similarity_obligation_ids", _as_tuple(self.similarity_obligation_ids))
        object.__setattr__(self, "surface_delegation_only", bool(self.surface_delegation_only))
        object.__setattr__(self, "source_surface_ids", _as_tuple(self.source_surface_ids))
        object.__setattr__(self, "source_refs", _as_tuple(self.source_refs))
        object.__setattr__(self, "primary_owner_model_id", str(self.primary_owner_model_id))
        object.__setattr__(self, "supporting_model_ids", _as_tuple(self.supporting_model_ids))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "relations", tuple(_coerce_relation(item) for item in self.relations))
        object.__setattr__(self, "lookup_binding", _coerce_lookup_binding(self.lookup_binding))
        object.__setattr__(self, "excluded_behavior_ids", _as_tuple(self.excluded_behavior_ids))
        object.__setattr__(self, "replacement_state", str(self.replacement_state or BCL_REPLACEMENT_ACTIVE))
        object.__setattr__(self, "model_sync_state", str(self.model_sync_state or BCL_MODEL_SYNC_OWNER_CURRENT))
        object.__setattr__(self, "miss_origin_state", str(self.miss_origin_state or BCL_MISS_ORIGIN_NONE))
        object.__setattr__(self, "path_authority", _coerce_path_binding(self.path_authority))
        object.__setattr__(self, "evidence", _coerce_evidence(self.evidence))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "validation_boundary", str(self.validation_boundary))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def has_scoped_disposition(self) -> bool:
        return bool(self.scoped_out_reason and self.owner and self.validation_boundary and self.rationale)

    def source_bound(self) -> bool:
        return bool(self.source_surface_ids or self.source_refs)

    def active_external_commitment(self) -> bool:
        return bool(
            self.in_scope
            and self.replacement_state == BCL_REPLACEMENT_ACTIVE
            and not self.surface_delegation_only
        )

    def exact_external_semantics_key(self) -> tuple[Any, ...]:
        """Return the typed external semantics used to detect duplicate promises."""

        return (
            self.behavior_plane,
            self.actor_kind,
            self.actor.strip().lower(),
            self.trigger.strip().lower(),
            tuple(sorted(item.strip().lower() for item in self.preconditions)),
            (self.expected_terminal or self.expected_result).strip().lower(),
            self.failure_boundary.strip().lower(),
            tuple(sorted(item.strip().lower() for item in self.state_writes)),
            tuple(sorted(item.strip().lower() for item in self.side_effects)),
        )

    def typed_variant_complete(self) -> bool:
        return bool(
            self.variant_of_business_intent_id
            and self.business_intent_id
            and self.business_intent_id != self.variant_of_business_intent_id
            and self.external_differences
            and all(item.complete() for item in self.external_differences)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "business_intent_id": self.business_intent_id,
            "label": self.label,
            "commitment_kind": self.commitment_kind,
            "behavior_plane": self.behavior_plane,
            "actor_kind": self.actor_kind,
            "actor": self.actor,
            "trigger": self.trigger,
            "expected_result": self.expected_result,
            "failure_boundary": self.failure_boundary,
            "preconditions": list(self.preconditions),
            "expected_terminal": self.expected_terminal,
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "variant_of_business_intent_id": self.variant_of_business_intent_id,
            "external_differences": [item.to_dict() for item in self.external_differences],
            "similarity_relation_ids": list(self.similarity_relation_ids),
            "similarity_obligation_ids": list(self.similarity_obligation_ids),
            "surface_delegation_only": self.surface_delegation_only,
            "source_surface_ids": list(self.source_surface_ids),
            "source_refs": list(self.source_refs),
            "primary_owner_model_id": self.primary_owner_model_id,
            "supporting_model_ids": list(self.supporting_model_ids),
            "child_model_ids": list(self.child_model_ids),
            "relations": [relation.to_dict() for relation in self.relations],
            "lookup_binding": self.lookup_binding.to_dict(),
            "excluded_behavior_ids": list(self.excluded_behavior_ids),
            "replacement_state": self.replacement_state,
            "model_sync_state": self.model_sync_state,
            "miss_origin_state": self.miss_origin_state,
            "path_authority": self.path_authority.to_dict(),
            "evidence": self.evidence.to_dict(),
            "in_scope": self.in_scope,
            "scoped_out_reason": self.scoped_out_reason,
            "owner": self.owner,
            "validation_boundary": self.validation_boundary,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorCommitmentLedger:
    """Full behavior commitment boundary for a project or work package."""

    ledger_id: str
    project_boundary: str = ""
    current_revision: str = ""
    commitments: tuple[BehaviorCommitment | Mapping[str, Any], ...] = ()
    source_surfaces: tuple[BehaviorSourceSurface | Mapping[str, Any], ...] = ()
    expected_commitment_ids: tuple[str, ...] = ()
    expected_business_intent_ids: tuple[str, ...] = ()
    claim_scope: str = BCL_SCOPE_ROUTINE
    change_mode: str = BCL_CHANGE_BOOTSTRAP_LEDGER
    require_current_evidence: bool = False
    require_risk_gates_for_broad_claim: bool = True
    owner: str = ""
    validation_boundary: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger_id", str(self.ledger_id))
        object.__setattr__(self, "project_boundary", str(self.project_boundary))
        object.__setattr__(self, "current_revision", str(self.current_revision))
        object.__setattr__(self, "commitments", tuple(_coerce_commitment(item) for item in self.commitments))
        object.__setattr__(self, "source_surfaces", tuple(_coerce_surface(item) for item in self.source_surfaces))
        object.__setattr__(self, "expected_commitment_ids", _as_tuple(self.expected_commitment_ids))
        object.__setattr__(self, "expected_business_intent_ids", _as_tuple(self.expected_business_intent_ids))
        object.__setattr__(self, "claim_scope", str(self.claim_scope or BCL_SCOPE_ROUTINE))
        object.__setattr__(self, "change_mode", str(self.change_mode or BCL_CHANGE_BOOTSTRAP_LEDGER))
        object.__setattr__(self, "require_current_evidence", bool(self.require_current_evidence))
        object.__setattr__(self, "require_risk_gates_for_broad_claim", bool(self.require_risk_gates_for_broad_claim))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "validation_boundary", str(self.validation_boundary))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def broad_claim(self) -> bool:
        return self.claim_scope in BCL_BROAD_CLAIM_SCOPES

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "project_boundary": self.project_boundary,
            "current_revision": self.current_revision,
            "commitments": [commitment.to_dict() for commitment in self.commitments],
            "source_surfaces": [surface.to_dict() for surface in self.source_surfaces],
            "expected_commitment_ids": list(self.expected_commitment_ids),
            "expected_business_intent_ids": list(self.expected_business_intent_ids),
            "claim_scope": self.claim_scope,
            "change_mode": self.change_mode,
            "require_current_evidence": self.require_current_evidence,
            "require_risk_gates_for_broad_claim": self.require_risk_gates_for_broad_claim,
            "owner": self.owner,
            "validation_boundary": self.validation_boundary,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def behavior_commitment_ledger_to_mapping(
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
) -> dict[str, Any]:
    """Return the canonical machine-readable ledger envelope."""

    normalized = (
        ledger
        if isinstance(ledger, BehaviorCommitmentLedger)
        else behavior_commitment_ledger_from_mapping(ledger)
    )
    return {
        "artifact_type": BCL_LEDGER_ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "format_version": BCL_LEDGER_FORMAT_VERSION,
        "ledger": normalized.to_dict(),
    }


def behavior_commitment_ledger_from_mapping(
    value: BehaviorCommitmentLedger | Mapping[str, Any],
) -> BehaviorCommitmentLedger:
    """Load a runtime ledger from the canonical envelope or direct current shape."""

    if isinstance(value, BehaviorCommitmentLedger):
        return value
    data = dict(value)
    if "ledger" in data:
        artifact_type = str(data.get("artifact_type", ""))
        if artifact_type != BCL_LEDGER_ARTIFACT_TYPE:
            raise ValueError(
                f"behavior commitment ledger artifact_type must be {BCL_LEDGER_ARTIFACT_TYPE!r}"
            )
        format_version = str(data.get("format_version", ""))
        if format_version != BCL_LEDGER_FORMAT_VERSION:
            raise ValueError(
                f"unsupported behavior commitment ledger format_version {format_version!r}"
            )
        payload = data.get("ledger")
        if not isinstance(payload, Mapping):
            raise ValueError("behavior commitment ledger envelope has no mapping payload")
        data = dict(payload)
    return BehaviorCommitmentLedger(**data)


def behavior_commitment_ledger_fingerprint(
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
) -> str:
    """Return a stable content identity for freshness and lookup evidence."""

    payload = behavior_commitment_ledger_to_mapping(ledger)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_behavior_commitment_ledger(path: str | Path) -> BehaviorCommitmentLedger:
    """Load one canonical JSON ledger without executing project Python."""

    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("behavior commitment ledger JSON root must be a mapping")
    return behavior_commitment_ledger_from_mapping(data)


def write_behavior_commitment_ledger(
    path: str | Path,
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
) -> Path:
    """Atomically write the canonical JSON ledger and return its path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = behavior_commitment_ledger_to_mapping(ledger)
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(target)
    return target


@dataclass(frozen=True)
class BehaviorCommitmentFinding:
    """One behavior ledger coverage gap."""

    code: str
    message: str
    severity: str = BCL_SEVERITY_BLOCKER
    commitment_id: str = ""
    surface_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity or BCL_SEVERITY_BLOCKER))
        object.__setattr__(self, "commitment_id", str(self.commitment_id))
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "commitment_id": self.commitment_id,
            "surface_id": self.surface_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorCommitmentCoverageReport:
    """Structured behavior commitment coverage result."""

    ok: bool
    ledger_id: str
    decision: str
    confidence: str
    findings: tuple[BehaviorCommitmentFinding, ...] = ()
    covered_commitment_ids: tuple[str, ...] = ()
    covered_business_intent_ids: tuple[str, ...] = ()
    missing_business_intent_ids: tuple[str, ...] = ()
    unmapped_surface_ids: tuple[str, ...] = ()
    extra_commitment_ids: tuple[str, ...] = ()
    path_sensitive_commitment_ids: tuple[str, ...] = ()
    ppa_blocked_commitment_ids: tuple[str, ...] = ()
    required_risk_gate_ids: tuple[str, ...] = ()
    coverage_case_ids: tuple[str, ...] = ()
    coverage_shard_ids: tuple[str, ...] = ()
    coverage_receipt_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_commitment_ids", _as_tuple(self.covered_commitment_ids))
        object.__setattr__(self, "covered_business_intent_ids", _as_tuple(self.covered_business_intent_ids))
        object.__setattr__(self, "missing_business_intent_ids", _as_tuple(self.missing_business_intent_ids))
        object.__setattr__(self, "unmapped_surface_ids", _as_tuple(self.unmapped_surface_ids))
        object.__setattr__(self, "extra_commitment_ids", _as_tuple(self.extra_commitment_ids))
        object.__setattr__(self, "path_sensitive_commitment_ids", _as_tuple(self.path_sensitive_commitment_ids))
        object.__setattr__(self, "ppa_blocked_commitment_ids", _as_tuple(self.ppa_blocked_commitment_ids))
        object.__setattr__(self, "required_risk_gate_ids", _as_tuple(self.required_risk_gate_ids))
        object.__setattr__(self, "coverage_case_ids", _as_tuple(self.coverage_case_ids))
        object.__setattr__(self, "coverage_shard_ids", _as_tuple(self.coverage_shard_ids))
        object.__setattr__(self, "coverage_receipt_ids", _as_tuple(self.coverage_receipt_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ledger={self.ledger_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == BCL_SEVERITY_BLOCKER)

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard behavior commitment ledger ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"ledger: {self.ledger_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"covered_commitments: {len(self.covered_commitment_ids)}",
            f"path_sensitive_commitments: {len(self.path_sensitive_commitment_ids)}",
            f"ppa_blocked_commitments: {len(self.ppa_blocked_commitment_ids)}",
            f"unmapped_surfaces: {len(self.unmapped_surface_ids)}",
            f"extra_commitments: {len(self.extra_commitment_ids)}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"commitment: {finding.commitment_id or '(none)'}",
                    f"surface: {finding.surface_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "ledger_id": self.ledger_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "covered_commitment_ids": list(self.covered_commitment_ids),
            "covered_business_intent_ids": list(self.covered_business_intent_ids),
            "missing_business_intent_ids": list(self.missing_business_intent_ids),
            "unmapped_surface_ids": list(self.unmapped_surface_ids),
            "extra_commitment_ids": list(self.extra_commitment_ids),
            "path_sensitive_commitment_ids": list(self.path_sensitive_commitment_ids),
            "ppa_blocked_commitment_ids": list(self.ppa_blocked_commitment_ids),
            "required_risk_gate_ids": list(self.required_risk_gate_ids),
            "coverage_case_ids": list(self.coverage_case_ids),
            "coverage_shard_ids": list(self.coverage_shard_ids),
            "coverage_receipt_ids": list(self.coverage_receipt_ids),
            "summary": self.summary,
        }


def _finding(
    code: str,
    message: str,
    *,
    commitment_id: str = "",
    surface_id: str = "",
    severity: str = BCL_SEVERITY_BLOCKER,
    metadata: Mapping[str, Any] | None = None,
) -> BehaviorCommitmentFinding:
    return BehaviorCommitmentFinding(
        code,
        message,
        severity=severity,
        commitment_id=commitment_id,
        surface_id=surface_id,
        metadata=metadata or {},
    )


def review_behavior_commitment_ledger(
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
) -> BehaviorCommitmentCoverageReport:
    """Review a project/work-package behavior commitment ledger."""

    ledger = behavior_commitment_ledger_from_mapping(ledger)
    findings: list[BehaviorCommitmentFinding] = []

    if not ledger.ledger_id:
        findings.append(_finding("ledger_missing_id", "ledger must name a stable id"))
    if not ledger.project_boundary:
        findings.append(_finding("ledger_missing_project_boundary", "ledger must describe the project or work boundary"))
    if not ledger.current_revision:
        findings.append(_finding("ledger_missing_current_revision", "ledger must record the current revision or evidence timestamp"))
    if not ledger.validation_boundary:
        findings.append(_finding("ledger_missing_validation_boundary", "ledger must record what validation boundary it covers"))
    if not ledger.rationale:
        findings.append(_finding("ledger_missing_rationale", "ledger must explain the behavior boundary rationale"))
    if not ledger.commitments:
        findings.append(_finding("ledger_missing_commitments", "ledger must include at least one behavior commitment"))
    if ledger.change_mode not in BCL_CHANGE_MODES:
        findings.append(
            _finding(
                "ledger_unknown_change_mode",
                "ledger change mode must classify bootstrap, add, change, replace/remove, gap backfill, or model-miss check work",
                metadata={"change_mode": ledger.change_mode},
            )
        )

    stable_identity_required = bool(
        ledger.broad_claim()
        or ledger.expected_business_intent_ids
        or any(commitment.business_intent_id for commitment in ledger.commitments)
        or any(surface.business_intent_ids for surface in ledger.source_surfaces)
    )

    commitment_by_id: dict[str, BehaviorCommitment] = {}
    active_commitment_by_intent_id: dict[str, BehaviorCommitment] = {}
    active_commitment_by_semantics: dict[tuple[Any, ...], BehaviorCommitment] = {}
    for commitment in ledger.commitments:
        if commitment.commitment_id in commitment_by_id:
            findings.append(
                _finding(
                    "duplicate_commitment_id",
                    f"commitment id {commitment.commitment_id!r} appears more than once",
                    commitment_id=commitment.commitment_id,
                )
            )
        commitment_by_id[commitment.commitment_id] = commitment
        if stable_identity_required and commitment.in_scope:
            if not commitment.business_intent_id:
                findings.append(
                    _finding(
                        "commitment_business_intent_id_missing",
                        "stable behavior coverage requires one exact business intent id per in-scope commitment",
                        commitment_id=commitment.commitment_id,
                    )
                )
            if not commitment.expected_terminal:
                findings.append(
                    _finding(
                        "commitment_expected_terminal_missing",
                        "stable behavior coverage requires an explicit externally observable terminal",
                        commitment_id=commitment.commitment_id,
                    )
                )
            if commitment.surface_delegation_only:
                findings.append(
                    _finding(
                        "delegate_commitment_forbidden",
                        "alias, adapter, wrapper, or compatibility delegation is a source surface, not a second behavior commitment",
                        commitment_id=commitment.commitment_id,
                    )
                )
            if commitment.variant_of_business_intent_id and not commitment.typed_variant_complete():
                findings.append(
                    _finding(
                        "typed_external_difference_incomplete",
                        "separate intent variant requires current typed external differences",
                        commitment_id=commitment.commitment_id,
                    )
                )
        if commitment.active_external_commitment() and commitment.business_intent_id:
            existing_intent = active_commitment_by_intent_id.get(commitment.business_intent_id)
            if existing_intent is not None:
                findings.append(
                    _finding(
                        "duplicate_exact_intent_commitment",
                        "one exact external business intent has more than one active behavior commitment",
                        commitment_id=commitment.commitment_id,
                        metadata={"first_commitment_id": existing_intent.commitment_id},
                    )
                )
            else:
                active_commitment_by_intent_id[commitment.business_intent_id] = commitment
            semantics_key = commitment.exact_external_semantics_key()
            existing_semantics = active_commitment_by_semantics.get(semantics_key)
            if existing_semantics is not None and (
                existing_semantics.business_intent_id != commitment.business_intent_id
            ):
                findings.append(
                    _finding(
                        "duplicate_external_semantics_commitment",
                        "different intent ids describe the same exact external semantics without a typed variant difference",
                        commitment_id=commitment.commitment_id,
                        metadata={"first_commitment_id": existing_semantics.commitment_id},
                    )
                )
            else:
                active_commitment_by_semantics[semantics_key] = commitment

    surface_by_id: dict[str, BehaviorSourceSurface] = {}
    for surface in ledger.source_surfaces:
        if surface.surface_id in surface_by_id:
            findings.append(
                _finding(
                    "duplicate_source_surface_id",
                    f"source surface id {surface.surface_id!r} appears more than once",
                    surface_id=surface.surface_id,
                )
            )
        surface_by_id[surface.surface_id] = surface

    for expected_id in ledger.expected_commitment_ids:
        if expected_id not in commitment_by_id:
            findings.append(
                _finding(
                    "expected_commitment_missing",
                    f"expected commitment {expected_id!r} is missing from the ledger",
                    commitment_id=expected_id,
                )
            )

    for expected_intent_id in ledger.expected_business_intent_ids:
        if expected_intent_id not in active_commitment_by_intent_id:
            findings.append(
                _finding(
                    "expected_business_intent_missing",
                    "expected exact business intent has no active commitment",
                    commitment_id=expected_intent_id,
                )
            )

    unmapped_surface_ids: list[str] = []
    for surface in ledger.source_surfaces:
        _review_surface(
            surface,
            commitment_by_id,
            findings,
            unmapped_surface_ids,
            stable_identity_required=stable_identity_required,
        )

    extra_commitment_ids: list[str] = []
    path_sensitive_commitment_ids: list[str] = []
    ppa_blocked_commitment_ids: list[str] = []
    covered_commitment_ids: list[str] = []
    required_risk_gate_ids: list[str] = []
    coverage_case_ids: list[str] = []
    coverage_shard_ids: list[str] = []
    coverage_receipt_ids: list[str] = []

    for commitment in ledger.commitments:
        _review_commitment(
            commitment,
            surface_by_id,
            commitment_by_id,
            ledger,
            findings,
            extra_commitment_ids,
            path_sensitive_commitment_ids,
            ppa_blocked_commitment_ids,
            required_risk_gate_ids,
            coverage_case_ids,
            coverage_shard_ids,
            coverage_receipt_ids,
        )

    blocked_commitments = {
        finding.commitment_id
        for finding in findings
        if finding.commitment_id and finding.severity == BCL_SEVERITY_BLOCKER
    }
    for commitment in ledger.commitments:
        if commitment.in_scope and commitment.commitment_id not in blocked_commitments:
            covered_commitment_ids.append(commitment.commitment_id)

    blockers = tuple(finding for finding in findings if finding.severity == BCL_SEVERITY_BLOCKER)
    covered_business_intent_ids = tuple(
        dict.fromkeys(
            commitment.business_intent_id
            for commitment in ledger.commitments
            if commitment.business_intent_id
            and commitment.commitment_id in covered_commitment_ids
        )
    )
    missing_business_intent_ids = tuple(
        intent_id
        for intent_id in ledger.expected_business_intent_ids
        if intent_id not in covered_business_intent_ids
    )
    if blockers:
        decision = BCL_DECISION_BLOCKED
        confidence = BCL_CONFIDENCE_BLOCKED
    elif findings:
        decision = BCL_DECISION_SCOPED
        confidence = BCL_CONFIDENCE_SCOPED
    else:
        decision = BCL_DECISION_GREEN
        confidence = BCL_CONFIDENCE_FULL

    return BehaviorCommitmentCoverageReport(
        ok=not blockers,
        ledger_id=ledger.ledger_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        covered_commitment_ids=tuple(dict.fromkeys(covered_commitment_ids)),
        covered_business_intent_ids=covered_business_intent_ids,
        missing_business_intent_ids=missing_business_intent_ids,
        unmapped_surface_ids=tuple(dict.fromkeys(unmapped_surface_ids)),
        extra_commitment_ids=tuple(dict.fromkeys(extra_commitment_ids)),
        path_sensitive_commitment_ids=tuple(dict.fromkeys(path_sensitive_commitment_ids)),
        ppa_blocked_commitment_ids=tuple(dict.fromkeys(ppa_blocked_commitment_ids)),
        required_risk_gate_ids=tuple(dict.fromkeys(required_risk_gate_ids)),
        coverage_case_ids=tuple(dict.fromkeys(coverage_case_ids)),
        coverage_shard_ids=tuple(dict.fromkeys(coverage_shard_ids)),
        coverage_receipt_ids=tuple(dict.fromkeys(coverage_receipt_ids)),
    )


def _review_surface(
    surface: BehaviorSourceSurface,
    commitment_by_id: Mapping[str, BehaviorCommitment],
    findings: list[BehaviorCommitmentFinding],
    unmapped_surface_ids: list[str],
    *,
    stable_identity_required: bool = False,
) -> None:
    if not surface.in_scope:
        if not surface.has_scoped_disposition():
            findings.append(
                _finding(
                    "scoped_out_behavior_missing_disposition",
                    "scoped-out source surface must record owner, reason, validation boundary, and rationale",
                    surface_id=surface.surface_id,
                    metadata={"surface": surface.to_dict()},
                )
            )
        return
    if surface.surface_kind not in BCL_SOURCE_KINDS:
        findings.append(
            _finding(
                "source_surface_unknown_kind",
                "source surface uses an unknown kind",
                surface_id=surface.surface_id,
                metadata={"surface": surface.to_dict()},
            )
        )
    if surface.freshness_state not in BCL_SOURCE_FRESHNESS_STATES:
        findings.append(
            _finding(
                "source_surface_unknown_freshness_state",
                "source surface uses an unknown freshness state",
                surface_id=surface.surface_id,
                metadata={"surface": surface.to_dict()},
            )
        )
    elif surface.freshness_state != BCL_SOURCE_FRESHNESS_CURRENT:
        findings.append(
            _finding(
                "source_surface_freshness_not_current",
                "broad behavior coverage requires current source-surface review",
                surface_id=surface.surface_id,
                metadata={"surface": surface.to_dict()},
            )
        )
    if not surface.commitment_ids:
        unmapped_surface_ids.append(surface.surface_id)
        findings.append(
            _finding(
                "source_surface_missing_commitment",
                "in-scope source surface does not map to any behavior commitment",
                surface_id=surface.surface_id,
                metadata={"surface": surface.to_dict()},
            )
            )
    if stable_identity_required and not surface.business_intent_ids:
        findings.append(
            _finding(
                "source_surface_business_intent_id_missing",
                "stable source inventory must map every in-scope surface to exact business intent ids",
                surface_id=surface.surface_id,
            )
        )
    if surface.delegates_to_primary_path and not surface.primary_path_id:
        findings.append(
            _finding(
                "delegating_surface_primary_path_missing",
                "delegating alias, adapter, wrapper, or compatibility surface must name the singular primary path",
                surface_id=surface.surface_id,
            )
        )
    for commitment_id in surface.commitment_ids:
        if commitment_id not in commitment_by_id:
            findings.append(
                _finding(
                    "source_surface_unknown_commitment",
                    f"source surface references unknown commitment {commitment_id!r}",
                    surface_id=surface.surface_id,
                    commitment_id=commitment_id,
                    metadata={"surface": surface.to_dict()},
                )
            )
            continue
        commitment = commitment_by_id[commitment_id]
        if (
            stable_identity_required
            and commitment.business_intent_id
            and commitment.business_intent_id not in surface.business_intent_ids
        ):
            findings.append(
                _finding(
                    "source_surface_business_intent_mismatch",
                    "source surface and mapped commitment disagree on exact business intent identity",
                    surface_id=surface.surface_id,
                    commitment_id=commitment_id,
                )
            )
        binding = commitment.path_authority
        if (
            surface.primary_path_id
            and binding.primary_path_id
            and surface.primary_path_id != binding.primary_path_id
        ):
            findings.append(
                _finding(
                    "source_surface_primary_path_mismatch",
                    "source surface points at a different primary path than its commitment",
                    surface_id=surface.surface_id,
                    commitment_id=commitment_id,
                )
            )


def _review_commitment(
    commitment: BehaviorCommitment,
    surface_by_id: Mapping[str, BehaviorSourceSurface],
    commitment_by_id: Mapping[str, BehaviorCommitment],
    ledger: BehaviorCommitmentLedger,
    findings: list[BehaviorCommitmentFinding],
    extra_commitment_ids: list[str],
    path_sensitive_commitment_ids: list[str],
    ppa_blocked_commitment_ids: list[str],
    required_risk_gate_ids: list[str],
    coverage_case_ids: list[str],
    coverage_shard_ids: list[str],
    coverage_receipt_ids: list[str],
) -> None:
    if not commitment.in_scope:
        if not commitment.has_scoped_disposition():
            findings.append(
                _finding(
                    "scoped_out_behavior_missing_disposition",
                    "scoped-out commitment must record owner, reason, validation boundary, and rationale",
                    commitment_id=commitment.commitment_id,
                    metadata={"commitment": commitment.to_dict()},
                )
            )
        return

    if commitment.commitment_kind not in BCL_COMMITMENT_KINDS:
        findings.append(
            _finding(
                "commitment_unknown_kind",
                "commitment uses an unknown kind",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.behavior_plane not in BCL_BEHAVIOR_PLANES:
        findings.append(
            _finding(
                "commitment_behavior_plane_missing_or_invalid",
                "commitment must declare product_runtime, agent_operation, or development_process",
                commitment_id=commitment.commitment_id,
                metadata={"behavior_plane": commitment.behavior_plane},
            )
        )
    if commitment.actor_kind not in BCL_ACTOR_KINDS:
        findings.append(
            _finding(
                "commitment_actor_kind_missing_or_invalid",
                "commitment must declare a supported structured actor kind",
                commitment_id=commitment.commitment_id,
                metadata={"actor_kind": commitment.actor_kind},
            )
        )
    if commitment.replacement_state not in BCL_REPLACEMENT_STATES:
        findings.append(
            _finding(
                "commitment_unknown_replacement_state",
                "commitment uses an unknown replacement state",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.model_sync_state not in BCL_MODEL_SYNC_STATES:
        findings.append(
            _finding(
                "commitment_unknown_model_sync_state",
                "commitment uses an unknown model-sync state",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.miss_origin_state not in BCL_MISS_ORIGIN_STATES:
        findings.append(
            _finding(
                "commitment_unknown_miss_origin_state",
                "commitment uses an unknown model-miss origin state",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    for field_name in ("label", "actor", "trigger", "expected_result", "failure_boundary", "validation_boundary", "rationale"):
        if not getattr(commitment, field_name):
            findings.append(
                _finding(
                    f"commitment_missing_{field_name}",
                    f"commitment must record {field_name}",
                    commitment_id=commitment.commitment_id,
                    metadata={"commitment": commitment.to_dict()},
                )
            )
    if not commitment.source_bound():
        extra_commitment_ids.append(commitment.commitment_id)
        findings.append(
            _finding(
                "commitment_missing_source_ref",
                "in-scope commitment has no source refs or source surface ids",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    for surface_id in commitment.source_surface_ids:
        if surface_id not in surface_by_id:
            findings.append(
                _finding(
                    "commitment_source_surface_unknown",
                    f"commitment references unknown source surface {surface_id!r}",
                    commitment_id=commitment.commitment_id,
                    surface_id=surface_id,
                    metadata={"commitment": commitment.to_dict()},
                )
            )
        elif commitment.commitment_id not in surface_by_id[surface_id].commitment_ids:
            findings.append(
                _finding(
                    "commitment_source_surface_not_bidirectional",
                    "commitment references a source surface that does not map back to the commitment",
                    commitment_id=commitment.commitment_id,
                    surface_id=surface_id,
                    metadata={"commitment": commitment.to_dict(), "surface": surface_by_id[surface_id].to_dict()},
                )
            )
    if not commitment.primary_owner_model_id:
        findings.append(
            _finding(
                "commitment_missing_primary_owner",
                "in-scope commitment must have exactly one primary owner model",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.primary_owner_model_id and commitment.primary_owner_model_id in {
        *commitment.supporting_model_ids,
        *commitment.child_model_ids,
    }:
        findings.append(
            _finding(
                "primary_owner_also_supporting",
                "primary owner model must not also be listed as supporting or child coverage",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    seen_relations: set[tuple[str, str]] = set()
    for relation in commitment.relations:
        relation_key = (relation.relation_type, relation.target_commitment_id)
        if relation_key in seen_relations:
            findings.append(
                _finding(
                    "commitment_relation_duplicate",
                    "commitment declares the same typed relation more than once",
                    commitment_id=commitment.commitment_id,
                    metadata={"relation": relation.to_dict()},
                )
            )
        seen_relations.add(relation_key)
        if relation.relation_type not in BCL_RELATION_TYPES:
            findings.append(
                _finding(
                    "commitment_relation_type_unknown",
                    "commitment relation uses an unknown type",
                    commitment_id=commitment.commitment_id,
                    metadata={"relation": relation.to_dict()},
                )
            )
            continue
        if relation.target_commitment_id == commitment.commitment_id:
            findings.append(
                _finding(
                    "commitment_relation_self_reference",
                    "commitment cannot relate to itself",
                    commitment_id=commitment.commitment_id,
                    metadata={"relation": relation.to_dict()},
                )
            )
            continue
        target = commitment_by_id.get(relation.target_commitment_id)
        if target is None:
            findings.append(
                _finding(
                    "commitment_relation_target_unknown",
                    f"commitment relation targets unknown commitment {relation.target_commitment_id!r}",
                    commitment_id=commitment.commitment_id,
                    metadata={"relation": relation.to_dict()},
                )
            )
            continue
        if commitment.behavior_plane != target.behavior_plane and not relation.rationale.strip():
            findings.append(
                _finding(
                    "commitment_cross_plane_relation_missing_rationale",
                    "cross-plane commitment relation must explain why the planes are connected",
                    commitment_id=commitment.commitment_id,
                    metadata={"relation": relation.to_dict(), "target_plane": target.behavior_plane},
                )
            )
        if not behavior_commitment_relation_allowed(
            commitment.behavior_plane,
            target.behavior_plane,
            relation.relation_type,
        ):
            findings.append(
                _finding(
                    "commitment_relation_plane_mismatch",
                    "commitment relation type is not allowed for the source and target planes",
                    commitment_id=commitment.commitment_id,
                    metadata={
                        "relation": relation.to_dict(),
                        "source_plane": commitment.behavior_plane,
                        "target_plane": target.behavior_plane,
                    },
                )
            )
    if ledger.require_current_evidence or ledger.broad_claim():
        if not commitment.evidence.has_current_pass():
            findings.append(
                _finding(
                    "commitment_current_evidence_missing",
                    "broad behavior claim requires current passing commitment evidence",
                    commitment_id=commitment.commitment_id,
                    metadata={"evidence": commitment.evidence.to_dict()},
                )
            )
        if not commitment.evidence.has_required_links():
            findings.append(
                _finding(
                    "commitment_evidence_links_missing",
                    "commitment evidence must bind model obligation, code contract, and test evidence ids",
                    commitment_id=commitment.commitment_id,
                    metadata={"evidence": commitment.evidence.to_dict()},
                )
            )
    if ledger.broad_claim() and ledger.require_risk_gates_for_broad_claim and not commitment.evidence.risk_gate_ids:
        findings.append(
            _finding(
                "commitment_risk_gate_missing",
                "broad behavior claim requires behavior commitment risk gate ids",
                commitment_id=commitment.commitment_id,
                metadata={"evidence": commitment.evidence.to_dict()},
            )
        )
    if ledger.broad_claim():
        _review_change_lifecycle(commitment, findings)

    if commitment.path_authority.path_sensitive and commitment.path_authority.primary_path_id:
        for surface_id in commitment.source_surface_ids:
            surface = surface_by_id.get(surface_id)
            if surface is None or not surface.in_scope:
                continue
            if not surface.primary_path_id:
                findings.append(
                    _finding(
                        "path_sensitive_source_surface_primary_path_missing",
                        "every in-scope surface for a path-sensitive commitment must map to the singular primary path",
                        commitment_id=commitment.commitment_id,
                        surface_id=surface_id,
                    )
                )

    _review_path_binding(commitment, findings, path_sensitive_commitment_ids, ppa_blocked_commitment_ids)
    required_risk_gate_ids.extend(commitment.evidence.risk_gate_ids)
    coverage_case_ids.extend(commitment.evidence.coverage_case_ids)
    coverage_shard_ids.extend(commitment.evidence.coverage_shard_ids)
    coverage_receipt_ids.extend(commitment.evidence.coverage_receipt_ids)
    required_risk_gate_ids.extend(commitment.path_authority.ppa_risk_gate_ids)
    coverage_shard_ids.extend(commitment.path_authority.ppa_coverage_shard_ids)
    coverage_receipt_ids.extend(commitment.path_authority.ppa_coverage_receipt_ids)


def _review_change_lifecycle(
    commitment: BehaviorCommitment,
    findings: list[BehaviorCommitmentFinding],
) -> None:
    if commitment.replacement_state == BCL_REPLACEMENT_REMOVED_SCOPED_OUT:
        findings.append(
            _finding(
                "commitment_removed_behavior_still_in_scope",
                "removed behavior must be scoped out with owner, reason, validation boundary, and rationale",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.replacement_state == BCL_REPLACEMENT_REPLACED and not (
        commitment.excluded_behavior_ids or commitment.metadata.get("replacement_commitment_id")
    ):
        findings.append(
            _finding(
                "commitment_replacement_disposition_missing",
                "replaced behavior must name the replacement commitment or excluded behavior ids",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.replacement_state in {
        BCL_REPLACEMENT_DEPRECATED,
        BCL_REPLACEMENT_REPLACED,
    } and not (commitment.owner and commitment.validation_boundary and commitment.rationale):
        findings.append(
            _finding(
                "commitment_lifecycle_disposition_missing",
                "deprecated or replaced behavior must record owner, validation boundary, and rationale",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.model_sync_state != BCL_MODEL_SYNC_OWNER_CURRENT:
        findings.append(
            _finding(
                "commitment_model_sync_not_current",
                "broad behavior coverage requires current owner-model and sibling/child-model review",
                commitment_id=commitment.commitment_id,
                metadata={"commitment": commitment.to_dict()},
            )
        )
    if commitment.evidence.test_mesh_state not in BCL_TEST_MESH_STATES:
        findings.append(
            _finding(
                "commitment_unknown_test_mesh_state",
                "commitment evidence uses an unknown TestMesh state",
                commitment_id=commitment.commitment_id,
                metadata={"evidence": commitment.evidence.to_dict()},
            )
        )
    elif commitment.evidence.test_mesh_state != BCL_TEST_MESH_SHARD_CURRENT:
        findings.append(
            _finding(
                "commitment_test_mesh_not_current",
                "broad behavior coverage requires current TestMesh shard evidence",
                commitment_id=commitment.commitment_id,
                metadata={"evidence": commitment.evidence.to_dict()},
            )
        )
    if commitment.miss_origin_state != BCL_MISS_ORIGIN_NONE:
        if commitment.model_sync_state != BCL_MODEL_SYNC_OWNER_CURRENT or not commitment.evidence.coverage_case_ids:
            findings.append(
                _finding(
                    "commitment_model_miss_backfeed_incomplete",
                    "model-miss backfeed must map to the existing commitment, current owner model, and same-class/DCAR coverage",
                    commitment_id=commitment.commitment_id,
                    metadata={"commitment": commitment.to_dict(), "evidence": commitment.evidence.to_dict()},
                )
            )


def _review_path_binding(
    commitment: BehaviorCommitment,
    findings: list[BehaviorCommitmentFinding],
    path_sensitive_commitment_ids: list[str],
    ppa_blocked_commitment_ids: list[str],
) -> None:
    binding = commitment.path_authority
    if not binding.path_sensitive:
        return
    path_sensitive_commitment_ids.append(commitment.commitment_id)
    if binding.business_intent_id != commitment.business_intent_id:
        findings.append(
            _finding(
                "commitment_primary_path_intent_mismatch",
                "PPA binding and behavior commitment must use the same stable business intent id",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )
    if binding.behavior_commitment_id != commitment.commitment_id:
        findings.append(
            _finding(
                "commitment_primary_path_commitment_mismatch",
                "PPA binding must point back to the exact behavior commitment it proves",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )
    if not binding.has_ppa_evidence():
        findings.append(
            _finding(
                "commitment_missing_primary_path_authority",
                "path-sensitive commitment must carry Primary Path Authority evidence",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )
    if binding.ppa_blocked() or (
        binding.has_ppa_evidence() and binding.ppa_result() != BCL_PPA_PASSED
    ):
        ppa_blocked_commitment_ids.append(commitment.commitment_id)
        findings.append(
            _finding(
                "commitment_primary_path_blocked",
                "Primary Path Authority blocks this path-sensitive commitment",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )
    if binding.has_ppa_evidence() and not binding.primary_path_id:
        findings.append(
            _finding(
                "commitment_primary_path_id_missing",
                "PPA binding must preserve one singular primary path id for the commitment",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )
    if binding.has_ppa_evidence() and not (
        binding.runtime_observation_ids
        and binding.proof_artifact_ids
        and binding.evidence_current
    ):
        findings.append(
            _finding(
                "commitment_primary_path_material_evidence_missing",
                "PPA binding must carry current runtime observations and proof artifact ids",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )
    if binding.has_ppa_evidence() and not binding.ppa_risk_gate_ids:
        findings.append(
            _finding(
                "commitment_primary_path_risk_gate_missing",
                "PPA binding must preserve downstream risk gate ids",
                commitment_id=commitment.commitment_id,
                metadata={"path_authority": binding.to_dict()},
            )
        )


def default_behavior_commitment_axes(
    *,
    model_id: str = BEHAVIOR_COMMITMENT_ROUTE_ID,
) -> tuple[ContractAxis, ...]:
    """Return finite axes for behavior-commitment Cartesian coverage."""

    return (
        ContractAxis("behavior_plane", model_id=model_id, values=BCL_BEHAVIOR_PLANES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("commitment_kind", model_id=model_id, values=BCL_COMMITMENT_KINDS, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("actor_kind", model_id=model_id, values=BCL_ACTOR_KINDS, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("source_kind", model_id=model_id, values=BCL_SOURCE_KINDS, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis(
            "source_mapping_state",
            model_id=model_id,
            values=("mapped", "source_surface_missing_commitment", "commitment_missing_source_ref", "not_bidirectional"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "owner_state",
            model_id=model_id,
            values=("primary_owner_present", "commitment_missing_primary_owner", "primary_owner_also_supporting"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis("evidence_state", model_id=model_id, values=BCL_EVIDENCE_STATES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("relation_type", model_id=model_id, values=BCL_RELATION_TYPES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("relation_target_plane", model_id=model_id, values=BCL_BEHAVIOR_PLANES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis(
            "relation_state",
            model_id=model_id,
            values=("relations_closed", "relation_target_unknown", "relation_plane_mismatch", "cross_plane_rationale_missing"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "lookup_binding_state",
            model_id=model_id,
            values=("binding_empty", "binding_structured", "binding_error_signature", "binding_stale"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "authority_shape_state",
            model_id=model_id,
            values=("current_shape", "former_dependency_rejected", "former_python_rejected", "former_json_rejected", "dual_authority_blocked"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "path_sensitivity",
            model_id=model_id,
            values=("not_path_sensitive", "path_sensitive"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis("ppa_result", model_id=model_id, values=BCL_PPA_RESULTS, source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis(
            "release_gate_state",
            model_id=model_id,
            values=(BCL_SCOPE_ROUTINE, BCL_SCOPE_DONE, BCL_SCOPE_RELEASE, BCL_SCOPE_PUBLISH, BCL_SCOPE_ARCHIVE, BCL_SCOPE_FULL),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis("change_mode", model_id=model_id, values=BCL_CHANGE_MODES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis(
            "source_freshness_state",
            model_id=model_id,
            values=BCL_SOURCE_FRESHNESS_STATES,
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis("replacement_state", model_id=model_id, values=BCL_REPLACEMENT_STATES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("model_sync_state", model_id=model_id, values=BCL_MODEL_SYNC_STATES, source_route=BEHAVIOR_COMMITMENT_ROUTE_ID),
        ContractAxis("test_mesh_state", model_id=model_id, values=BCL_TEST_MESH_STATES, source_route="test_mesh_maintenance"),
        ContractAxis("miss_origin_state", model_id=model_id, values=BCL_MISS_ORIGIN_STATES, source_route="model_miss_review"),
        ContractAxis(
            "exact_intent_identity_state",
            model_id=model_id,
            values=("stable_unique", "missing", "duplicate", "mismatch"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "external_semantics_state",
            model_id=model_id,
            values=("unique", "duplicate", "typed_variant", "variant_difference_incomplete"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "primary_path_binding_shape",
            model_id=model_id,
            values=("singular", "former_plural_rejected", "missing"),
            source_route=PRIMARY_PATH_ROUTE_ID,
        ),
        ContractAxis(
            "surface_authority_role",
            model_id=model_id,
            values=("commitment_owner", "delegate_to_primary", "delegate_as_commitment", "surface_omitted"),
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
    )


def default_behavior_commitment_interaction_groups(
    *,
    model_id: str = BEHAVIOR_COMMITMENT_ROUTE_ID,
    max_combinations: int = 10000,
) -> tuple[ContractInteractionGroup, ...]:
    """Return default finite interaction groups for ledger coverage."""

    routes = ("model_test_alignment", "test_mesh_maintenance", "risk_evidence_ledger")
    return (
        ContractInteractionGroup(
            "plane_kind_actor",
            model_id=model_id,
            axis_ids=("behavior_plane", "commitment_kind", "actor_kind"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "full_inventory_mapping",
            model_id=model_id,
            axis_ids=("commitment_kind", "source_kind", "source_mapping_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "single_owner_evidence",
            model_id=model_id,
            axis_ids=("commitment_kind", "owner_state", "evidence_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "relation_and_release_gate",
            model_id=model_id,
            axis_ids=("relation_state", "evidence_state", "release_gate_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "cross_plane_relation",
            model_id=model_id,
            axis_ids=("behavior_plane", "relation_type", "relation_target_plane"),
            required_routes=routes + ("existing_model_preflight",),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "lookup_authority_shape",
            model_id=model_id,
            axis_ids=("behavior_plane", "lookup_binding_state", "authority_shape_state"),
            required_routes=routes + ("existing_model_preflight", "development_process_flow"),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "path_sensitive_ppa_handoff",
            model_id=model_id,
            axis_ids=("path_sensitivity", "ppa_result", "release_gate_state"),
            required_routes=routes + (PRIMARY_PATH_ROUTE_ID,),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "change_mode_source_freshness",
            model_id=model_id,
            axis_ids=("change_mode", "source_kind", "source_freshness_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "replacement_model_sync",
            model_id=model_id,
            axis_ids=("change_mode", "replacement_state", "model_sync_state"),
            required_routes=routes + ("existing_model_preflight",),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "model_miss_backfeed",
            model_id=model_id,
            axis_ids=("miss_origin_state", "model_sync_state", "test_mesh_state"),
            required_routes=routes + ("model_miss_review", "contract_exhaustion_mesh"),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "model_miss_plane_backfeed",
            model_id=model_id,
            axis_ids=("behavior_plane", "miss_origin_state", "relation_state"),
            required_routes=routes + ("model_miss_review", "contract_exhaustion_mesh"),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "exact_intent_semantic_uniqueness",
            model_id=model_id,
            axis_ids=("exact_intent_identity_state", "external_semantics_state", "surface_authority_role"),
            required_routes=routes + ("existing_model_preflight",),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "singular_primary_path_current_shape",
            model_id=model_id,
            axis_ids=("exact_intent_identity_state", "primary_path_binding_shape", "ppa_result"),
            required_routes=routes + (PRIMARY_PATH_ROUTE_ID,),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "delegate_surface_not_commitment",
            model_id=model_id,
            axis_ids=("surface_authority_role", "source_mapping_state", "primary_path_binding_shape"),
            required_routes=routes + (PRIMARY_PATH_ROUTE_ID, "model_similarity_consolidation"),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
    )


def default_behavior_commitment_coverage_universe(
    *,
    model_id: str = BEHAVIOR_COMMITMENT_ROUTE_ID,
    claim_scope: str = BCL_SCOPE_FULL,
) -> ContractCoverageUniverse:
    """Return the finite coverage universe for behavior commitment coverage."""

    axes = default_behavior_commitment_axes(model_id=model_id)
    groups = default_behavior_commitment_interaction_groups(model_id=model_id)
    return ContractCoverageUniverse(
        f"behavior_commitment_ledger:{model_id}",
        claim_scope=claim_scope,
        required_axis_ids=tuple(axis.axis_id for axis in axes),
        required_interaction_group_ids=tuple(group.group_id for group in groups),
        required_coverage_receipt_ids=(f"contract_coverage:{model_id}",),
        require_full_product=True,
        metadata={
            "owner_route": BEHAVIOR_COMMITMENT_ROUTE_ID,
            "downstream_path_authority": PRIMARY_PATH_ROUTE_ID,
        },
    )


def behavior_commitment_contract_exhaustion_plan(
    plan_id: str = "behavior-commitment-coverage",
    *,
    model_id: str = BEHAVIOR_COMMITMENT_ROUTE_ID,
    claim_scope: str = BCL_SCOPE_FULL,
    max_combinations: int = 10000,
) -> ContractExhaustionPlan:
    """Build the canonical ContractExhaustionMesh plan for the ledger."""

    return ContractExhaustionPlan(
        plan_id,
        model_id=model_id,
        axes=default_behavior_commitment_axes(model_id=model_id),
        interaction_groups=default_behavior_commitment_interaction_groups(
            model_id=model_id,
            max_combinations=max_combinations,
        ),
        oracles=(
            ContractOracle(
                BEHAVIOR_COMMITMENT_ORACLE_ID,
                CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
                expected_message_fields=(
                    "commitment_id",
                    "source_surface_id",
                    "primary_owner_model_id",
                    "coverage_gap_code",
                    "repair_action",
                ),
                forbidden_downstream_steps=(
                    "claim_release_without_commitment_coverage",
                    "claim_full_without_ppa_for_path_sensitive_commitment",
                ),
                required_repair_fields=(
                    "ledger_id",
                    "commitment_id",
                    "owner_model_id",
                    "evidence_id",
                ),
                disallowed_side_effects=("alternate_success_path", "unregistered_behavior_claim"),
                description="Missing, extra, overlapping, stale, or PPA-blocked behavior commitments must block broad claims.",
            ),
        ),
        claim_scope=claim_scope,
        required_route_ids=("model_test_alignment", "test_mesh_maintenance", "risk_evidence_ledger", PRIMARY_PATH_ROUTE_ID),
        require_model_coverage_receipt=True,
        require_coverage_universe=True,
        coverage_universe=default_behavior_commitment_coverage_universe(model_id=model_id, claim_scope=claim_scope),
    )


def behavior_commitment_risk_gate_ids(report: BehaviorCommitmentCoverageReport) -> tuple[str, ...]:
    """Return the risk gate ids a broad claim should preserve for this report."""

    base = (
        f"risk_gate:{BCL_RISK_GATE_COVERAGE}:{report.ledger_id}",
        f"risk_gate:{BCL_RISK_GATE_CARTESIAN_COVERAGE}:{report.ledger_id}",
    )
    ppa = ()
    if report.path_sensitive_commitment_ids:
        ppa = (
            f"risk_gate:{PPA_RISK_GATE_AUTHORITY}:{report.ledger_id}",
            f"risk_gate:{PPA_RISK_GATE_CARTESIAN_COVERAGE}:{report.ledger_id}",
        )
    return tuple(dict.fromkeys(base + ppa + report.required_risk_gate_ids))


__all__ = [
    "BCL_ACTOR_AI_AGENT",
    "BCL_ACTOR_APPLICATION",
    "BCL_ACTOR_AUTOMATION",
    "BCL_ACTOR_DEVELOPER",
    "BCL_ACTOR_END_USER",
    "BCL_ACTOR_EXTERNAL_SYSTEM",
    "BCL_ACTOR_KINDS",
    "BCL_BROAD_CLAIM_SCOPES",
    "BCL_CHANGE_ADD_BEHAVIOR",
    "BCL_CHANGE_BOOTSTRAP_LEDGER",
    "BCL_CHANGE_CHANGE_BEHAVIOR",
    "BCL_CHANGE_COVERAGE_GAP_BACKFILL",
    "BCL_CHANGE_MODEL_MISS_CHECK",
    "BCL_CHANGE_MODES",
    "BCL_CHANGE_REMOVE_OR_REPLACE_BEHAVIOR",
    "BCL_COMMITMENT_CLI",
    "BCL_COMMITMENT_DOC",
    "BCL_COMMITMENT_KINDS",
    "BCL_COMMITMENT_PROCESS",
    "BCL_COMMITMENT_PUBLIC_API",
    "BCL_COMMITMENT_RELEASE",
    "BCL_COMMITMENT_SKILL",
    "BCL_COMMITMENT_UI",
    "BCL_COMMITMENT_WORKFLOW",
    "BCL_CONFIDENCE_BLOCKED",
    "BCL_CONFIDENCE_FULL",
    "BCL_CONFIDENCE_SCOPED",
    "BCL_DECISION_BLOCKED",
    "BCL_DECISION_GREEN",
    "BCL_DECISION_SCOPED",
    "BCL_EVIDENCE_BLOCKED",
    "BCL_EVIDENCE_CURRENT_PASS",
    "BCL_EVIDENCE_MISSING",
    "BCL_EVIDENCE_PROGRESS_ONLY",
    "BCL_EVIDENCE_SKIPPED",
    "BCL_EVIDENCE_STALE",
    "BCL_EVIDENCE_STATES",
    "BCL_EXTERNAL_DIFFERENCE_FAILURE_BOUNDARY",
    "BCL_EXTERNAL_DIFFERENCE_KINDS",
    "BCL_EXTERNAL_DIFFERENCE_PRECONDITION",
    "BCL_EXTERNAL_DIFFERENCE_PUBLIC_SURFACE",
    "BCL_EXTERNAL_DIFFERENCE_SIDE_EFFECT",
    "BCL_EXTERNAL_DIFFERENCE_STATE_WRITE",
    "BCL_EXTERNAL_DIFFERENCE_TERMINAL",
    "BCL_HIT_ROLE_EVIDENCE_SOURCE",
    "BCL_HIT_ROLE_GOVERNING_PROCESS",
    "BCL_HIT_ROLE_INVOKED_TARGET",
    "BCL_HIT_ROLE_PRIMARY",
    "BCL_HIT_ROLE_VALIDATION_TARGET",
    "BCL_HIT_ROLES",
    "BCL_LEDGER_ARTIFACT_TYPE",
    "BCL_LEDGER_FORMAT_VERSION",
    "BCL_LOOKUP_STATUSES",
    "BCL_LOOKUP_STATUS_BLOCKED",
    "BCL_LOOKUP_STATUS_NOT_APPLICABLE",
    "BCL_LOOKUP_STATUS_PERFORMED",
    "BCL_MISS_ORIGIN_NONE",
    "BCL_MISS_ORIGIN_OBSERVED",
    "BCL_MISS_ORIGIN_RECURRING_FAMILY",
    "BCL_MISS_ORIGIN_SAME_CLASS_SEED",
    "BCL_MISS_ORIGIN_STATES",
    "BCL_MODEL_SYNC_CHILD_NEEDED",
    "BCL_MODEL_SYNC_OWNER_CURRENT",
    "BCL_MODEL_SYNC_OWNER_MISSING",
    "BCL_MODEL_SYNC_OWNER_STALE",
    "BCL_MODEL_SYNC_SIBLING_UNCHECKED",
    "BCL_MODEL_SYNC_STATES",
    "BCL_PPA_BLOCKED",
    "BCL_PPA_MISSING",
    "BCL_PPA_NOT_REQUIRED",
    "BCL_PPA_PASSED",
    "BCL_PPA_RESULTS",
    "BCL_BEHAVIOR_PLANES",
    "BCL_PLANE_AGENT_OPERATION",
    "BCL_PLANE_DEVELOPMENT_PROCESS",
    "BCL_PLANE_PRODUCT_RUNTIME",
    "BCL_PLANE_UNCLASSIFIED",
    "BCL_RELATION_DEPENDS_ON",
    "BCL_RELATION_GOVERNS",
    "BCL_RELATION_INVOKES",
    "BCL_RELATION_REQUIRES_EVIDENCE_FROM",
    "BCL_RELATION_TYPES",
    "BCL_RELATION_VALIDATES",
    "BCL_REPLACEMENT_ACTIVE",
    "BCL_REPLACEMENT_DEPRECATED",
    "BCL_REPLACEMENT_REMOVED_SCOPED_OUT",
    "BCL_REPLACEMENT_REPLACED",
    "BCL_REPLACEMENT_STATES",
    "BCL_RISK_GATE_CARTESIAN_COVERAGE",
    "BCL_RISK_GATE_COVERAGE",
    "BCL_SCOPE_ARCHIVE",
    "BCL_SCOPE_DONE",
    "BCL_SCOPE_FULL",
    "BCL_SCOPE_PRODUCTION",
    "BCL_SCOPE_PUBLISH",
    "BCL_SCOPE_RELEASE",
    "BCL_SCOPE_ROUTINE",
    "BCL_SEVERITY_BLOCKER",
    "BCL_SEVERITY_WARNING",
    "BCL_SOURCE_API",
    "BCL_SOURCE_CLI",
    "BCL_SOURCE_CODE",
    "BCL_SOURCE_DOC",
    "BCL_SOURCE_FRESHNESS_CHANGED",
    "BCL_SOURCE_FRESHNESS_CURRENT",
    "BCL_SOURCE_FRESHNESS_MISSING",
    "BCL_SOURCE_FRESHNESS_STATES",
    "BCL_SOURCE_FRESHNESS_UNCHECKED",
    "BCL_SOURCE_KINDS",
    "BCL_SOURCE_OPENSPEC",
    "BCL_SOURCE_PROCESS",
    "BCL_SOURCE_RELEASE",
    "BCL_SOURCE_SKILL",
    "BCL_SOURCE_TEST",
    "BCL_SOURCE_UI",
    "BCL_TEST_MESH_PROGRESS_ONLY",
    "BCL_TEST_MESH_RELEASE_ONLY",
    "BCL_TEST_MESH_SHARD_CURRENT",
    "BCL_TEST_MESH_SHARD_MISSING",
    "BCL_TEST_MESH_STALE",
    "BCL_TEST_MESH_STATES",
    "BEHAVIOR_COMMITMENT_ORACLE_ID",
    "BEHAVIOR_COMMITMENT_ROUTE_ID",
    "BehaviorCommitment",
    "BehaviorCommitmentRelation",
    "BehaviorCommitmentCoverageReport",
    "BehaviorCommitmentFinding",
    "BehaviorCommitmentLedger",
    "BehaviorEvidenceBinding",
    "BehaviorExternalDifference",
    "BehaviorLookupBinding",
    "BehaviorPathAuthorityBinding",
    "BehaviorSourceSurface",
    "behavior_commitment_contract_exhaustion_plan",
    "behavior_commitment_ledger_fingerprint",
    "behavior_commitment_ledger_from_mapping",
    "behavior_commitment_ledger_to_mapping",
    "behavior_commitment_relation_allowed",
    "behavior_commitment_risk_gate_ids",
    "behavior_path_binding_from_primary_path_report",
    "default_behavior_commitment_axes",
    "default_behavior_commitment_coverage_universe",
    "default_behavior_commitment_interaction_groups",
    "load_behavior_commitment_ledger",
    "review_behavior_commitment_ledger",
    "write_behavior_commitment_ledger",
]
