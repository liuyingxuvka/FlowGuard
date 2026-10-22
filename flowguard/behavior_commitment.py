"""Project-level behavior commitment coverage ledger.

The ledger is the upstream account book for user-visible or externally
reliable behavior. It answers "what behavior did we promise and who owns it?"
Path-sensitive rows then hand off to Primary Path Authority for the stricter
"one runtime path, no automatic alternate success" rule.

Model kit: ``add_commitment``, ``retire_commitment``, ``add_path`` and
``retire_path`` are plan edits, ``behavior_commitment_explorer`` explores them
with the ledger review, a static scan of the real tests and the primary-path
review as invariants, and ``behavior_commitment_code_facts`` compares the
target plan with the code.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._normalization import string_tuple as _as_tuple

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
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_BEHAVIOR_NO_OP,
    PPA_DISPOSITION_DELEGATE_TO_PRIMARY,
    PPA_DISPOSITION_DELETE,
    PPA_DISPOSITION_PRESERVE_FACADE,
    PPA_TRIGGER_NEVER,
    PRIMARY_PATH_ROUTE_ID,
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    review_primary_path_authority,
)


BEHAVIOR_COMMITMENT_ROUTE_ID = "behavior_commitment_ledger"

# Model subject lanes (plain vocabulary; the same strings the models use).
SUBJECT_NORMATIVE_TARGET = "normative_target"
SUBJECT_LANES = frozenset({"observed_implementation", SUBJECT_NORMATIVE_TARGET, "counterfactual_experiment"})
BEHAVIOR_COMMITMENT_ORACLE_ID = "behavior_commitment_coverage_must_block"

BCL_SOURCE_FILE_AGGREGATE_SCHEMA = "flowguard.behavior-source-file-aggregate.v1"
BCL_SOURCE_INVENTORY_SCHEMA = "flowguard.behavior-source-inventory.v1"
BCL_LIVE_SOURCE_IDENTITY_METADATA_KEY = "live_source_identity"
BCL_BEHAVIOR_INVENTORY_SCHEMA = "flowguard.independent-behavior-inventory.v2"

# The independent behavior denominator is intentionally stricter than the
# historical BCL source-surface ledger.  Historical specifications remain
# provenance only; one of these dispositions must state how the current
# effective intent treats that source.
BCL_INTENT_DISPOSITION_ACCEPTED_CURRENT = "accepted_current"
BCL_INTENT_DISPOSITION_SUPERSEDED = "superseded"
BCL_INTENT_DISPOSITION_MERGED = "merged"
BCL_INTENT_DISPOSITION_RETIRED = "retired"
BCL_INTENT_DISPOSITION_REJECTED = "rejected"
BCL_INTENT_DISPOSITION_UNRESOLVED = "unresolved"
BCL_INTENT_DISPOSITIONS = (
    BCL_INTENT_DISPOSITION_ACCEPTED_CURRENT,
    BCL_INTENT_DISPOSITION_SUPERSEDED,
    BCL_INTENT_DISPOSITION_MERGED,
    BCL_INTENT_DISPOSITION_RETIRED,
    BCL_INTENT_DISPOSITION_REJECTED,
    BCL_INTENT_DISPOSITION_UNRESOLVED,
)

BCL_LIFECYCLE_LANES = (
    "happy_path",
    "boundary",
    "negative",
    "fault",
    "recovery",
    "cleanup",
    "idempotency",
    "repeated",
    "interruption",
    "runtime",
    "ui",
    "consumer",
    "installation",
    "platform",
    "release",
    "observed_miss_backfeed",
)
BCL_LIFECYCLE_REQUIRED = "required_and_covered"
BCL_LIFECYCLE_NOT_APPLICABLE = "verified_not_applicable"

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

from .behavior_plane import (  # noqa: E402
    BCL_LOOKUP_STATUS_BLOCKED, BCL_LOOKUP_STATUS_FALLBACK,
    BCL_LOOKUP_STATUS_NOT_APPLICABLE, BCL_LOOKUP_STATUS_PERFORMED,
)
BCL_LOOKUP_STATUSES = (
    BCL_LOOKUP_STATUS_PERFORMED,
    BCL_LOOKUP_STATUS_NOT_APPLICABLE,
    BCL_LOOKUP_STATUS_FALLBACK,
    BCL_LOOKUP_STATUS_BLOCKED,
)

from .behavior_plane import BCL_HIT_ROLE_PRIMARY  # noqa: E402
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
BCL_SOURCE_FIELD = "field"
BCL_SOURCE_DOC = "doc"
BCL_SOURCE_SKILL = "skill"
BCL_SOURCE_TEST = "test"
BCL_SOURCE_WORK_CONTEXT = "work_context"
BCL_SOURCE_RELEASE = "release"
BCL_SOURCE_PROCESS = "process"
BCL_SOURCE_KINDS = (
    BCL_SOURCE_CODE,
    BCL_SOURCE_API,
    BCL_SOURCE_CLI,
    BCL_SOURCE_UI,
    BCL_SOURCE_FIELD,
    BCL_SOURCE_DOC,
    BCL_SOURCE_SKILL,
    BCL_SOURCE_TEST,
    BCL_SOURCE_WORK_CONTEXT,
    BCL_SOURCE_RELEASE,
    BCL_SOURCE_PROCESS,
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

BCL_SOURCE_AUTHORITY_NORMATIVE = "normative"
BCL_SOURCE_AUTHORITY_OBSERVED = "observed"
BCL_SOURCE_AUTHORITY_SUPPORTING = "supporting"
BCL_SOURCE_AUTHORITY_HISTORICAL = "historical"
BCL_SOURCE_AUTHORITY_ROLES = (
    BCL_SOURCE_AUTHORITY_NORMATIVE,
    BCL_SOURCE_AUTHORITY_OBSERVED,
    BCL_SOURCE_AUTHORITY_SUPPORTING,
    BCL_SOURCE_AUTHORITY_HISTORICAL,
)

BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT = "external_normative_contract"
BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR = "observed_external_behavior"
BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION = "implementation"
BCL_SOURCE_CLASSIFICATION_TEST = "test"
BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE = "generated_evidence"
BCL_SOURCE_CLASSIFICATIONS = (
    BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT,
    BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR,
    BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
    BCL_SOURCE_CLASSIFICATION_TEST,
    BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE,
)

BCL_DISPOSITION_MODELED = "modeled"
BCL_DISPOSITION_DELEGATED = "delegated"
BCL_DISPOSITION_SCOPED = "scoped"
BCL_COVERAGE_DISPOSITIONS = (
    BCL_DISPOSITION_MODELED,
    BCL_DISPOSITION_DELEGATED,
    BCL_DISPOSITION_SCOPED,
)

# Independent behavior inventories use more explicit disposition names than
# the historical source-surface dispositions above.  These values belong only
# to the independent inventory; the old BCL source-surface constants remain
# unchanged and are not accepted as inventory values.
BCL_BEHAVIOR_DISPOSITION_MODELED = "modeled"
BCL_BEHAVIOR_DISPOSITION_DELEGATED = "delegated_to_named_owner"
BCL_BEHAVIOR_DISPOSITION_SCOPED = "explicitly_out_of_scope_with_reason"
BCL_BEHAVIOR_DISPOSITION_BLOCKED = "blocked_gap"
BCL_BEHAVIOR_INVENTORY_DISPOSITIONS = (
    BCL_BEHAVIOR_DISPOSITION_MODELED,
    BCL_BEHAVIOR_DISPOSITION_DELEGATED,
    BCL_BEHAVIOR_DISPOSITION_SCOPED,
    BCL_BEHAVIOR_DISPOSITION_BLOCKED,
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


def _metadata(values: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(values or {})


def _coerce_surface(value: "BehaviorSourceSurface | Mapping[str, Any]") -> "BehaviorSourceSurface":
    if isinstance(value, BehaviorSourceSurface):
        return value
    return BehaviorSourceSurface(**dict(value))


def _coerce_behavior_inventory(
    value: "BehaviorInventory | Mapping[str, Any] | None",
) -> "BehaviorInventory | None":
    if value is None or isinstance(value, BehaviorInventory):
        return value
    data = dict(value)
    expected_fingerprint = data.pop("fingerprint", None)
    schema_version = data.pop("schema_version", BCL_BEHAVIOR_INVENTORY_SCHEMA)
    if schema_version != BCL_BEHAVIOR_INVENTORY_SCHEMA:
        raise ValueError(
            f"unsupported behavior inventory schema_version {schema_version!r}"
        )
    result = BehaviorInventory(**data)
    if expected_fingerprint is not None and expected_fingerprint != result.fingerprint:
        raise ValueError("behavior inventory fingerprint is stale")
    return result


def _coerce_commitment(value: "BehaviorCommitment | Mapping[str, Any]") -> "BehaviorCommitment":
    if isinstance(value, BehaviorCommitment):
        return value
    return BehaviorCommitment(**{k: v for k, v in dict(value).items() if k != "path_authority"})  # retired key




def _coerce_external_difference(
    value: "BehaviorExternalDifference | Mapping[str, Any]",
) -> "BehaviorExternalDifference":
    if isinstance(value, BehaviorExternalDifference):
        return value
    data = dict(value)
    data.pop("evidence_current", None)  # one retired nested mapping key
    return BehaviorExternalDifference(**data)


@dataclass(frozen=True)
class BehaviorSourceSurface:
    """A source surface that promises or exposes behavior."""

    surface_id: str
    surface_kind: str = BCL_SOURCE_CODE
    label: str = ""
    source_ref: str = ""
    source_system_id: str = ""
    native_artifact_id: str = ""
    content_fingerprint: str = ""
    inventory_revision: str = ""
    discovery_evidence_ids: tuple[str, ...] = ()
    source_authority_role: str = BCL_SOURCE_AUTHORITY_NORMATIVE
    source_classification: str = BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT
    declared_semantics_fingerprint: str = ""
    coverage_disposition: str = BCL_DISPOSITION_MODELED
    delegated_owner_inventory_id: str = ""
    delegation_relation_type: str = ""
    native_evidence_ids: tuple[str, ...] = ()
    commitment_ids: tuple[str, ...] = ()
    business_intent_ids: tuple[str, ...] = ()
    primary_path_id: str = ""
    delegates_to_primary_path: bool = False
    canonical_relation_ids: tuple[str, ...] = ()
    relation_obligation_ids: tuple[str, ...] = ()
    similarity_obligation_ids: tuple[str, ...] = ()
    similarity_relation_ids: tuple[str, ...] = ()
    freshness_state: str = BCL_SOURCE_FRESHNESS_UNCHECKED
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
        object.__setattr__(self, "source_system_id", str(self.source_system_id))
        object.__setattr__(self, "native_artifact_id", str(self.native_artifact_id))
        object.__setattr__(self, "content_fingerprint", str(self.content_fingerprint))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(
            self,
            "discovery_evidence_ids",
            _as_tuple(self.discovery_evidence_ids),
        )
        object.__setattr__(
            self,
            "source_authority_role",
            str(self.source_authority_role or BCL_SOURCE_AUTHORITY_NORMATIVE),
        )
        object.__setattr__(
            self,
            "source_classification",
            str(
                self.source_classification
                or BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT
            ),
        )
        object.__setattr__(
            self,
            "declared_semantics_fingerprint",
            str(self.declared_semantics_fingerprint),
        )
        object.__setattr__(
            self,
            "coverage_disposition",
            str(self.coverage_disposition or BCL_DISPOSITION_MODELED),
        )
        object.__setattr__(
            self,
            "delegated_owner_inventory_id",
            str(self.delegated_owner_inventory_id),
        )
        object.__setattr__(
            self,
            "delegation_relation_type",
            str(self.delegation_relation_type),
        )
        object.__setattr__(
            self,
            "native_evidence_ids",
            _as_tuple(self.native_evidence_ids),
        )
        object.__setattr__(self, "commitment_ids", _as_tuple(self.commitment_ids))
        object.__setattr__(self, "business_intent_ids", _as_tuple(self.business_intent_ids))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "delegates_to_primary_path", bool(self.delegates_to_primary_path))
        object.__setattr__(self, "canonical_relation_ids", _as_tuple(self.canonical_relation_ids))
        object.__setattr__(self, "relation_obligation_ids", _as_tuple(self.relation_obligation_ids))
        object.__setattr__(self, "similarity_obligation_ids", _as_tuple(self.similarity_obligation_ids))
        object.__setattr__(self, "similarity_relation_ids", _as_tuple(self.similarity_relation_ids))
        object.__setattr__(
            self,
            "freshness_state",
            str(self.freshness_state or BCL_SOURCE_FRESHNESS_UNCHECKED),
        )
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "validation_boundary", str(self.validation_boundary))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def has_scoped_disposition(self) -> bool:
        return bool(self.scoped_out_reason and self.owner and self.validation_boundary and self.rationale)

    def licenses_external_commitment(self, commitment_id: str = "") -> bool:
        """Return whether this row is current normative authority for a commitment."""

        return bool(
            self.in_scope
            and self.freshness_state == BCL_SOURCE_FRESHNESS_CURRENT
            and self.source_classification
            == BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT
            and self.source_authority_role == BCL_SOURCE_AUTHORITY_NORMATIVE
            and self.coverage_disposition == BCL_DISPOSITION_MODELED
            and (not commitment_id or commitment_id in self.commitment_ids)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "label": self.label,
            "source_ref": self.source_ref,
            "source_system_id": self.source_system_id,
            "native_artifact_id": self.native_artifact_id,
            "content_fingerprint": self.content_fingerprint,
            "inventory_revision": self.inventory_revision,
            "discovery_evidence_ids": list(self.discovery_evidence_ids),
            "source_authority_role": self.source_authority_role,
            "source_classification": self.source_classification,
            "declared_semantics_fingerprint": self.declared_semantics_fingerprint,
            "coverage_disposition": self.coverage_disposition,
            "delegated_owner_inventory_id": self.delegated_owner_inventory_id,
            "delegation_relation_type": self.delegation_relation_type,
            "native_evidence_ids": list(self.native_evidence_ids),
            "commitment_ids": list(self.commitment_ids),
            "business_intent_ids": list(self.business_intent_ids),
            "primary_path_id": self.primary_path_id,
            "delegates_to_primary_path": self.delegates_to_primary_path,
            "canonical_relation_ids": list(self.canonical_relation_ids),
            "relation_obligation_ids": list(self.relation_obligation_ids),
            "similarity_obligation_ids": list(self.similarity_obligation_ids),
            "similarity_relation_ids": list(self.similarity_relation_ids),
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
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "difference_id", str(self.difference_id))
        object.__setattr__(self, "difference_kind", str(self.difference_kind))
        object.__setattr__(self, "baseline_value", str(self.baseline_value))
        object.__setattr__(self, "variant_value", str(self.variant_value))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
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
            and self.rationale
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "difference_id": self.difference_id,
            "difference_kind": self.difference_kind,
            "baseline_value": self.baseline_value,
            "variant_value": self.variant_value,
            "evidence_ids": list(self.evidence_ids),
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class BehaviorInventoryItem:
    """One independently discovered external behavior denominator member.

    The discovery owner supplies these rows independently of BCL commitment
    rows and test inventories.  BCL only reconciles each row to one typed
    disposition and preserves its external success, error, and recovery
    semantics for downstream model/test alignment.
    """

    behavior_id: str
    source_kind: str
    source_ref: str
    source_fingerprint: str
    public_surface: str
    intent: str
    success: str
    errors: tuple[str, ...]
    recovery: tuple[str, ...]
    owner: str
    disposition: str
    intent_source_refs: tuple[str, ...] = ()
    intent_disposition: str = BCL_INTENT_DISPOSITION_ACCEPTED_CURRENT
    function_id: str = ""
    route_id: str = ""
    obligation_ids: tuple[str, ...] = ()
    required_check_ids: tuple[str, ...] = ()
    test_refs: tuple[str, ...] = ()
    evidence_subject_ids: tuple[str, ...] = ()
    oracle_ids: tuple[str, ...] = ()
    failure_case_ids: tuple[str, ...] = ()
    recovery_case_ids: tuple[str, ...] = ()
    current_intent_fingerprint: str = ""
    lifecycle_envelope: Mapping[str, Any] = field(default_factory=dict)
    commitment_id: str = ""
    model_owner_id: str = ""
    delegated_owner_inventory_id: str = ""
    delegation_relation_type: str = ""
    scoped_out_reason: str = ""
    blocked_gap_reason: str = ""
    validation_boundary: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "behavior_id",
            "source_kind",
            "source_ref",
            "source_fingerprint",
            "public_surface",
            "intent",
            "success",
            "owner",
            "disposition",
        ):
            value = str(getattr(self, name))
            if not value.strip():
                raise ValueError(f"behavior inventory {name} must be non-empty")
            object.__setattr__(self, name, value)
        if (
            not self.source_fingerprint.startswith("sha256:")
            or not self.source_fingerprint[7:].strip()
        ):
            raise ValueError(
                "behavior inventory source_fingerprint must be a sha256 identity"
            )
        object.__setattr__(
            self,
            "intent_source_refs",
            _as_tuple(self.intent_source_refs),
        )
        object.__setattr__(
            self,
            "intent_disposition",
            str(self.intent_disposition or BCL_INTENT_DISPOSITION_UNRESOLVED),
        )
        if self.intent_disposition not in BCL_INTENT_DISPOSITIONS:
            raise ValueError(
                "behavior inventory intent_disposition must be one of "
                + ", ".join(BCL_INTENT_DISPOSITIONS)
            )
        for name in (
            "function_id",
            "route_id",
            "current_intent_fingerprint",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        for name in (
            "obligation_ids",
            "required_check_ids",
            "test_refs",
            "evidence_subject_ids",
            "oracle_ids",
            "failure_case_ids",
            "recovery_case_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        envelope = dict(self.lifecycle_envelope or {})
        object.__setattr__(self, "lifecycle_envelope", envelope)
        disposition = str(self.disposition)
        if disposition not in BCL_BEHAVIOR_INVENTORY_DISPOSITIONS:
            raise ValueError(
                "behavior inventory disposition must be modeled, "
                "delegated_to_named_owner, explicitly_out_of_scope_with_reason, "
                "or blocked_gap"
            )
        object.__setattr__(self, "disposition", disposition)
        for name in ("errors", "recovery"):
            values = _as_tuple(getattr(self, name))
            if not values or any(not value.strip() for value in values):
                raise ValueError(
                    f"behavior inventory {name} must contain an explicit outcome or not-applicable reason"
                )
            object.__setattr__(self, name, values)
        for name in (
            "commitment_id",
            "model_owner_id",
            "delegated_owner_inventory_id",
            "delegation_relation_type",
            "scoped_out_reason",
            "blocked_gap_reason",
            "validation_boundary",
            "rationale",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": BCL_BEHAVIOR_INVENTORY_SCHEMA,
            "behavior_id": self.behavior_id,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "source_fingerprint": self.source_fingerprint,
            "public_surface": self.public_surface,
            "intent": self.intent,
            "intent_source_refs": list(self.intent_source_refs),
            "intent_disposition": self.intent_disposition,
            "function_id": self.function_id,
            "route_id": self.route_id,
            "obligation_ids": list(self.obligation_ids),
            "required_check_ids": list(self.required_check_ids),
            "test_refs": list(self.test_refs),
            "evidence_subject_ids": list(self.evidence_subject_ids),
            "oracle_ids": list(self.oracle_ids),
            "failure_case_ids": list(self.failure_case_ids),
            "recovery_case_ids": list(self.recovery_case_ids),
            "current_intent_fingerprint": self.current_intent_fingerprint,
            "lifecycle_envelope": to_jsonable(dict(self.lifecycle_envelope)),
            "success": self.success,
            "errors": list(self.errors),
            "recovery": list(self.recovery),
            "owner": self.owner,
            "disposition": self.disposition,
            "commitment_id": self.commitment_id,
            "model_owner_id": self.model_owner_id,
            "delegated_owner_inventory_id": self.delegated_owner_inventory_id,
            "delegation_relation_type": self.delegation_relation_type,
            "scoped_out_reason": self.scoped_out_reason,
            "blocked_gap_reason": self.blocked_gap_reason,
            "validation_boundary": self.validation_boundary,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    @property
    def fingerprint(self) -> str:
        return _canonical_sha256(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}


def _coerce_behavior_inventory_item(
    value: "BehaviorInventoryItem | Mapping[str, Any]",
) -> "BehaviorInventoryItem":
    if isinstance(value, BehaviorInventoryItem):
        return value
    data = dict(value)
    expected_fingerprint = data.pop("fingerprint", None)
    schema_version = data.pop("schema_version", BCL_BEHAVIOR_INVENTORY_SCHEMA)
    if schema_version != BCL_BEHAVIOR_INVENTORY_SCHEMA:
        raise ValueError(
            f"unsupported behavior inventory item schema_version {schema_version!r}"
        )
    result = BehaviorInventoryItem(**data)
    if expected_fingerprint is not None and expected_fingerprint != result.fingerprint:
        raise ValueError("behavior inventory item fingerprint is stale")
    return result


@dataclass(frozen=True)
class BehaviorInventory:
    """The independently discovered expected behavior denominator."""

    inventory_id: str
    project_boundary: str
    current_revision: str
    discovery_owner: str
    discovery_fingerprint: str
    discovery_evidence_ids: tuple[str, ...]
    expected_behavior_ids: tuple[str, ...]
    items: tuple[BehaviorInventoryItem | Mapping[str, Any], ...]
    claim_boundary: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "inventory_id",
            "project_boundary",
            "current_revision",
            "discovery_owner",
            "discovery_fingerprint",
            "claim_boundary",
        ):
            value = str(getattr(self, name))
            if not value.strip():
                raise ValueError(f"behavior inventory {name} must be non-empty")
            object.__setattr__(self, name, value)
        if (
            not self.discovery_fingerprint.startswith("sha256:")
            or not self.discovery_fingerprint[7:].strip()
        ):
            raise ValueError(
                "behavior inventory discovery_fingerprint must be a sha256 identity"
            )
        evidence_ids = _as_tuple(self.discovery_evidence_ids)
        expected_ids = _as_tuple(self.expected_behavior_ids)
        if not evidence_ids or any(not item.strip() for item in evidence_ids):
            raise ValueError("behavior inventory requires discovery evidence")
        if not expected_ids or any(not item.strip() for item in expected_ids):
            raise ValueError("behavior inventory requires expected behavior ids")
        object.__setattr__(self, "discovery_evidence_ids", evidence_ids)
        object.__setattr__(self, "expected_behavior_ids", expected_ids)
        object.__setattr__(
            self,
            "items",
            tuple(
                sorted(
                    (_coerce_behavior_inventory_item(item) for item in self.items),
                    key=lambda item: item.behavior_id,
                )
            ),
        )
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": BCL_BEHAVIOR_INVENTORY_SCHEMA,
            "inventory_id": self.inventory_id,
            "project_boundary": self.project_boundary,
            "current_revision": self.current_revision,
            "discovery_owner": self.discovery_owner,
            "discovery_fingerprint": self.discovery_fingerprint,
            "discovery_evidence_ids": list(self.discovery_evidence_ids),
            "expected_behavior_ids": list(self.expected_behavior_ids),
            "items": [item.to_dict() for item in self.items],
            "claim_boundary": self.claim_boundary,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    @property
    def fingerprint(self) -> str:
        return _canonical_sha256(self.identity_payload())

    @property
    def behavior_ids(self) -> tuple[str, ...]:
        return tuple(item.behavior_id for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}


@dataclass(frozen=True)
class BehaviorInventoryReport:
    """Reconciliation result for one independent behavior denominator."""

    ok: bool
    inventory_id: str
    inventory_fingerprint: str
    expected_behavior_ids: tuple[str, ...] = ()
    actual_behavior_ids: tuple[str, ...] = ()
    missing_behavior_ids: tuple[str, ...] = ()
    unexpected_behavior_ids: tuple[str, ...] = ()
    findings: tuple["BehaviorCommitmentFinding", ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "expected_behavior_ids",
            "actual_behavior_ids",
            "missing_behavior_ids",
            "unexpected_behavior_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "findings", tuple(self.findings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "inventory_id": self.inventory_id,
            "inventory_fingerprint": self.inventory_fingerprint,
            "expected_behavior_ids": list(self.expected_behavior_ids),
            "actual_behavior_ids": list(self.actual_behavior_ids),
            "missing_behavior_ids": list(self.missing_behavior_ids),
            "unexpected_behavior_ids": list(self.unexpected_behavior_ids),
            "findings": [finding.to_dict() for finding in self.findings],
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
    canonical_relation_ids: tuple[str, ...] = ()
    relation_obligation_ids: tuple[str, ...] = ()
    similarity_obligation_ids: tuple[str, ...] = ()
    similarity_relation_ids: tuple[str, ...] = ()
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
    in_scope: bool = True
    scoped_out_reason: str = ""
    owner: str = ""
    validation_boundary: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    entrypoints: tuple[str, ...] = ()      # 'path:Symbol' of the code that keeps the promise
    tests: tuple[str, ...] = ()            # 'tests/x.py:test_name' of the tests that guard it

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
        object.__setattr__(self, "canonical_relation_ids", _as_tuple(self.canonical_relation_ids))
        object.__setattr__(self, "relation_obligation_ids", _as_tuple(self.relation_obligation_ids))
        object.__setattr__(self, "similarity_obligation_ids", _as_tuple(self.similarity_obligation_ids))
        object.__setattr__(self, "similarity_relation_ids", _as_tuple(self.similarity_relation_ids))
        object.__setattr__(self, "surface_delegation_only", bool(self.surface_delegation_only))
        object.__setattr__(self, "source_surface_ids", _as_tuple(self.source_surface_ids))
        object.__setattr__(self, "source_refs", _as_tuple(self.source_refs))
        object.__setattr__(self, "entrypoints", _as_tuple(self.entrypoints))
        object.__setattr__(self, "tests", _as_tuple(self.tests))
        object.__setattr__(self, "primary_owner_model_id", str(self.primary_owner_model_id))
        object.__setattr__(self, "supporting_model_ids", _as_tuple(self.supporting_model_ids))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "relations", tuple(_coerce_relation(item) for item in self.relations))
        object.__setattr__(self, "lookup_binding", _coerce_lookup_binding(self.lookup_binding))
        object.__setattr__(self, "excluded_behavior_ids", _as_tuple(self.excluded_behavior_ids))
        object.__setattr__(self, "replacement_state", str(self.replacement_state or BCL_REPLACEMENT_ACTIVE))
        object.__setattr__(self, "model_sync_state", str(self.model_sync_state or BCL_MODEL_SYNC_OWNER_CURRENT))
        object.__setattr__(self, "miss_origin_state", str(self.miss_origin_state or BCL_MISS_ORIGIN_NONE))
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
            "canonical_relation_ids": list(self.canonical_relation_ids),
            "relation_obligation_ids": list(self.relation_obligation_ids),
            "similarity_obligation_ids": list(self.similarity_obligation_ids),
            "similarity_relation_ids": list(self.similarity_relation_ids),
            "surface_delegation_only": self.surface_delegation_only,
            "source_surface_ids": list(self.source_surface_ids),
            "source_refs": list(self.source_refs),
            "entrypoints": list(self.entrypoints),
            "tests": list(self.tests),
            "primary_owner_model_id": self.primary_owner_model_id,
            "supporting_model_ids": list(self.supporting_model_ids),
            "child_model_ids": list(self.child_model_ids),
            "relations": [relation.to_dict() for relation in self.relations],
            "lookup_binding": self.lookup_binding.to_dict(),
            "excluded_behavior_ids": list(self.excluded_behavior_ids),
            "replacement_state": self.replacement_state,
            "model_sync_state": self.model_sync_state,
            "miss_origin_state": self.miss_origin_state,
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
    subject_lane: str = SUBJECT_NORMATIVE_TARGET
    expected_source_surface_ids: tuple[str, ...] = ()
    source_inventory_revision: str = ""
    source_inventory_fingerprint: str = ""
    source_inventory_evidence_ids: tuple[str, ...] = ()
    require_complete_source_inventory: bool = False
    independent_behavior_inventory: BehaviorInventory | Mapping[str, Any] | None = None
    require_complete_behavior_inventory: bool = False
    expected_commitment_ids: tuple[str, ...] = ()
    expected_business_intent_ids: tuple[str, ...] = ()
    claim_scope: str = BCL_SCOPE_ROUTINE
    change_mode: str = BCL_CHANGE_CHANGE_BEHAVIOR
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
        object.__setattr__(self, "subject_lane", str(self.subject_lane))
        object.__setattr__(
            self,
            "expected_source_surface_ids",
            _as_tuple(self.expected_source_surface_ids),
        )
        object.__setattr__(
            self,
            "source_inventory_revision",
            str(self.source_inventory_revision),
        )
        object.__setattr__(
            self,
            "source_inventory_fingerprint",
            str(self.source_inventory_fingerprint),
        )
        object.__setattr__(
            self,
            "source_inventory_evidence_ids",
            _as_tuple(self.source_inventory_evidence_ids),
        )
        object.__setattr__(
            self,
            "require_complete_source_inventory",
            bool(self.require_complete_source_inventory),
        )
        object.__setattr__(
            self,
            "independent_behavior_inventory",
            _coerce_behavior_inventory(self.independent_behavior_inventory),
        )
        object.__setattr__(
            self,
            "require_complete_behavior_inventory",
            bool(self.require_complete_behavior_inventory),
        )
        object.__setattr__(self, "expected_commitment_ids", _as_tuple(self.expected_commitment_ids))
        object.__setattr__(self, "expected_business_intent_ids", _as_tuple(self.expected_business_intent_ids))
        object.__setattr__(self, "claim_scope", str(self.claim_scope or BCL_SCOPE_ROUTINE))
        object.__setattr__(
            self,
            "change_mode",
            str(self.change_mode or BCL_CHANGE_CHANGE_BEHAVIOR),
        )
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
            "subject_lane": self.subject_lane,
            "expected_source_surface_ids": list(self.expected_source_surface_ids),
            "source_inventory_revision": self.source_inventory_revision,
            "source_inventory_fingerprint": self.source_inventory_fingerprint,
            "source_inventory_evidence_ids": list(self.source_inventory_evidence_ids),
            "require_complete_source_inventory": self.require_complete_source_inventory,
            "independent_behavior_inventory": (
                self.independent_behavior_inventory.to_dict()
                if self.independent_behavior_inventory is not None
                else None
            ),
            "require_complete_behavior_inventory": self.require_complete_behavior_inventory,
            "expected_commitment_ids": list(self.expected_commitment_ids),
            "expected_business_intent_ids": list(self.expected_business_intent_ids),
            "claim_scope": self.claim_scope,
            "change_mode": self.change_mode,
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
    is_envelope = "ledger" in data
    if is_envelope:
        expected_envelope_fields = {
            "artifact_type",
            "schema_version",
            "format_version",
            "ledger",
        }
        if set(data) != expected_envelope_fields:
            raise ValueError(
                "behavior commitment ledger envelope must use the exact current field set"
            )
        artifact_type = str(data.get("artifact_type", ""))
        if artifact_type != BCL_LEDGER_ARTIFACT_TYPE:
            raise ValueError(
                f"behavior commitment ledger artifact_type must be {BCL_LEDGER_ARTIFACT_TYPE!r}"
            )
        schema_version = str(data.get("schema_version", ""))
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported behavior commitment ledger schema_version {schema_version!r}"
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
    # One-time removal of known retired fields; all other canonical checks stay strict.
    for key in ("require_current_evidence", "require_risk_gates_for_broad_claim"):
        data.pop(key, None)
    if isinstance(data.get("commitments"), list):
        commitments = []
        for item in data["commitments"]:
            if not isinstance(item, Mapping):
                commitments.append(item)
                continue
            row = dict(item)
            row.pop("evidence", None)
            if isinstance(row.get("external_differences"), list):
                differences = []
                for difference in row["external_differences"]:
                    if isinstance(difference, Mapping):
                        difference = dict(difference)
                        difference.pop("evidence_current", None)
                    differences.append(difference)
                row["external_differences"] = differences
            commitments.append(row)
        data["commitments"] = commitments
    normalized = BehaviorCommitmentLedger(**data)
    if normalized.to_dict() != data:
        source = "envelope payload" if is_envelope else "direct mapping"
        raise ValueError(
            f"behavior commitment ledger {source} must use the exact current canonical shape"
        )
    return normalized


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
    missing_source_surface_ids: tuple[str, ...] = ()
    unexpected_source_surface_ids: tuple[str, ...] = ()
    unmapped_surface_ids: tuple[str, ...] = ()
    extra_commitment_ids: tuple[str, ...] = ()
    required_risk_gate_ids: tuple[str, ...] = ()
    coverage_case_ids: tuple[str, ...] = ()
    coverage_shard_ids: tuple[str, ...] = ()
    behavior_inventory_id: str = ""
    behavior_inventory_fingerprint: str = ""
    missing_behavior_ids: tuple[str, ...] = ()
    unexpected_behavior_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_commitment_ids", _as_tuple(self.covered_commitment_ids))
        object.__setattr__(self, "covered_business_intent_ids", _as_tuple(self.covered_business_intent_ids))
        object.__setattr__(self, "missing_business_intent_ids", _as_tuple(self.missing_business_intent_ids))
        object.__setattr__(
            self,
            "missing_source_surface_ids",
            _as_tuple(self.missing_source_surface_ids),
        )
        object.__setattr__(
            self,
            "unexpected_source_surface_ids",
            _as_tuple(self.unexpected_source_surface_ids),
        )
        object.__setattr__(self, "unmapped_surface_ids", _as_tuple(self.unmapped_surface_ids))
        object.__setattr__(self, "extra_commitment_ids", _as_tuple(self.extra_commitment_ids))
        object.__setattr__(self, "required_risk_gate_ids", _as_tuple(self.required_risk_gate_ids))
        object.__setattr__(self, "coverage_case_ids", _as_tuple(self.coverage_case_ids))
        object.__setattr__(self, "coverage_shard_ids", _as_tuple(self.coverage_shard_ids))
        object.__setattr__(self, "behavior_inventory_id", str(self.behavior_inventory_id))
        object.__setattr__(
            self,
            "behavior_inventory_fingerprint",
            str(self.behavior_inventory_fingerprint),
        )
        object.__setattr__(self, "missing_behavior_ids", _as_tuple(self.missing_behavior_ids))
        object.__setattr__(self, "unexpected_behavior_ids", _as_tuple(self.unexpected_behavior_ids))
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
            f"missing_source_surfaces: {len(self.missing_source_surface_ids)}",
            f"unexpected_source_surfaces: {len(self.unexpected_source_surface_ids)}",
            f"unmapped_surfaces: {len(self.unmapped_surface_ids)}",
            f"extra_commitments: {len(self.extra_commitment_ids)}",
            f"missing_behaviors: {len(self.missing_behavior_ids)}",
            f"unexpected_behaviors: {len(self.unexpected_behavior_ids)}",
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
            "missing_source_surface_ids": list(self.missing_source_surface_ids),
            "unexpected_source_surface_ids": list(self.unexpected_source_surface_ids),
            "unmapped_surface_ids": list(self.unmapped_surface_ids),
            "extra_commitment_ids": list(self.extra_commitment_ids),
            "required_risk_gate_ids": list(self.required_risk_gate_ids),
            "coverage_case_ids": list(self.coverage_case_ids),
            "coverage_shard_ids": list(self.coverage_shard_ids),
            "behavior_inventory_id": self.behavior_inventory_id,
            "behavior_inventory_fingerprint": self.behavior_inventory_fingerprint,
            "missing_behavior_ids": list(self.missing_behavior_ids),
            "unexpected_behavior_ids": list(self.unexpected_behavior_ids),
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


def review_independent_behavior_inventory(
    inventory: BehaviorInventory | Mapping[str, Any],
    *,
    ledger: BehaviorCommitmentLedger | Mapping[str, Any] | None = None,
) -> BehaviorInventoryReport:
    """Reconcile an independently discovered behavior denominator.

    The expected id list and discovery identity are caller-supplied evidence;
    this function never derives them from BCL commitment rows or tests.  When
    a ledger is supplied, it only checks the typed handoff for modeled rows
    and rejects an inventory that reuses the ledger's own identity as its
    discovery authority.
    """

    normalized = _coerce_behavior_inventory(inventory)
    if normalized is None:
        raise ValueError("independent behavior inventory cannot be null")
    normalized_ledger = (
        None
        if ledger is None
        else behavior_commitment_ledger_from_mapping(ledger)
    )
    findings: list[BehaviorCommitmentFinding] = []
    expected_ids = tuple(normalized.expected_behavior_ids)
    actual_ids = tuple(item.behavior_id for item in normalized.items)
    duplicate_expected = tuple(
        sorted(
            item_id
            for item_id in set(expected_ids)
            if expected_ids.count(item_id) > 1
        )
    )
    duplicate_actual = tuple(
        sorted(
            item_id
            for item_id in set(actual_ids)
            if actual_ids.count(item_id) > 1
        )
    )
    if duplicate_expected:
        findings.append(
            _finding(
                "behavior_inventory_expected_duplicate_id",
                "independent behavior inventory expected ids must be unique",
                metadata={"behavior_ids": list(duplicate_expected)},
            )
        )
    if duplicate_actual:
        findings.append(
            _finding(
                "behavior_inventory_duplicate_id",
                "independent behavior inventory contains duplicate materialized ids",
                metadata={"behavior_ids": list(duplicate_actual)},
            )
        )
    missing_ids = tuple(sorted(set(expected_ids) - set(actual_ids)))
    unexpected_ids = tuple(sorted(set(actual_ids) - set(expected_ids)))
    for behavior_id in missing_ids:
        findings.append(
            _finding(
                "behavior_inventory_expected_item_missing",
                "independent expected behavior is absent from the materialized inventory",
                metadata={"behavior_id": behavior_id},
            )
        )
    for behavior_id in unexpected_ids:
        findings.append(
            _finding(
                "behavior_inventory_unexpected_item",
                "materialized behavior is outside the independent expected denominator",
                metadata={"behavior_id": behavior_id},
            )
        )
    if normalized.inventory_id == (normalized_ledger.ledger_id if normalized_ledger else ""):
        findings.append(
            _finding(
                "behavior_inventory_authority_collision",
                "independent behavior inventory must have an authority identity distinct from the BCL ledger",
            )
        )
    if normalized_ledger is not None:
        ledger_fingerprint = behavior_commitment_ledger_fingerprint(normalized_ledger)
        if normalized.discovery_fingerprint == f"sha256:{ledger_fingerprint}":
            findings.append(
                _finding(
                    "behavior_inventory_discovery_not_independent",
                    "independent behavior discovery fingerprint cannot reuse the BCL ledger fingerprint",
                )
            )
    commitment_by_id = {
        commitment.commitment_id: commitment for commitment in normalized_ledger.commitments
    } if normalized_ledger is not None else {}
    for item in normalized.items:
        if not item.intent_source_refs:
            findings.append(
                _finding(
                    "behavior_inventory_intent_source_missing",
                    "every behavior must retain at least one explicit intent provenance reference",
                    metadata={"behavior_id": item.behavior_id},
                )
            )
        if item.intent_disposition == BCL_INTENT_DISPOSITION_UNRESOLVED:
            findings.append(
                _finding(
                    "behavior_inventory_intent_unresolved",
                    "an unresolved historical/current intent disposition blocks the inventory",
                    metadata={"behavior_id": item.behavior_id},
                )
            )
        if (
            not item.current_intent_fingerprint.startswith("sha256:")
            or not item.current_intent_fingerprint[7:].strip()
        ):
            findings.append(
                _finding(
                    "behavior_inventory_current_intent_identity_missing",
                    "every behavior must bind the current effective intent fingerprint",
                    metadata={"behavior_id": item.behavior_id},
                )
            )
        if item.intent_disposition == BCL_INTENT_DISPOSITION_ACCEPTED_CURRENT:
            if not item.function_id and not item.route_id:
                findings.append(
                    _finding(
                        "behavior_inventory_function_route_missing",
                        "accepted current behavior requires a function or route identity",
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
            required_links = (
                ("obligation_ids", item.obligation_ids),
                ("required_check_ids", item.required_check_ids),
                ("test_refs", item.test_refs),
                ("evidence_subject_ids", item.evidence_subject_ids),
                ("oracle_ids", item.oracle_ids),
                ("failure_case_ids", item.failure_case_ids),
                ("recovery_case_ids", item.recovery_case_ids),
            )
            for field_name, values in required_links:
                if not values:
                    findings.append(
                        _finding(
                            "behavior_inventory_required_link_missing",
                            f"accepted current behavior requires non-empty {field_name}",
                            metadata={
                                "behavior_id": item.behavior_id,
                                "field": field_name,
                            },
                        )
                    )
            envelope = item.lifecycle_envelope
            missing_lanes = tuple(
                lane for lane in BCL_LIFECYCLE_LANES if lane not in envelope
            )
            unknown_lanes = tuple(
                sorted(set(envelope) - set(BCL_LIFECYCLE_LANES))
            )
            if missing_lanes or unknown_lanes:
                findings.append(
                    _finding(
                        "behavior_inventory_lifecycle_envelope_incomplete",
                        "accepted current behavior must account for every lifecycle lane",
                        metadata={
                            "behavior_id": item.behavior_id,
                            "missing_lanes": list(missing_lanes),
                            "unknown_lanes": list(unknown_lanes),
                        },
                    )
                )
            else:
                invalid_lanes = []
                for lane in BCL_LIFECYCLE_LANES:
                    value = envelope.get(lane)
                    if not isinstance(value, Mapping):
                        invalid_lanes.append(lane)
                        continue
                    status = str(value.get("status", ""))
                    if status not in (
                        BCL_LIFECYCLE_REQUIRED,
                        BCL_LIFECYCLE_NOT_APPLICABLE,
                    ):
                        invalid_lanes.append(lane)
                if invalid_lanes:
                    findings.append(
                        _finding(
                            "behavior_inventory_lifecycle_lane_invalid",
                            "each lifecycle lane must be covered or have a verifier-backed not-applicable disposition",
                            metadata={
                                "behavior_id": item.behavior_id,
                                "lanes": sorted(invalid_lanes),
                            },
                        )
                    )
        if item.disposition == BCL_DISPOSITION_MODELED:
            if not item.commitment_id:
                findings.append(
                    _finding(
                        "behavior_inventory_modeled_commitment_missing",
                        "modeled independent behavior requires one BCL commitment id",
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
            elif normalized_ledger is not None and item.commitment_id not in commitment_by_id:
                findings.append(
                    _finding(
                        "behavior_inventory_modeled_commitment_unknown",
                        "modeled independent behavior names a commitment outside the current BCL",
                        commitment_id=item.commitment_id,
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
            if not item.model_owner_id:
                findings.append(
                    _finding(
                        "behavior_inventory_modeled_owner_missing",
                        "modeled independent behavior requires one exact primary model owner",
                        commitment_id=item.commitment_id,
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
        elif item.disposition == BCL_BEHAVIOR_DISPOSITION_DELEGATED:
            if not item.delegated_owner_inventory_id or not item.delegation_relation_type:
                findings.append(
                    _finding(
                        "behavior_inventory_delegated_owner_incomplete",
                        "delegated independent behavior requires a named native owner inventory and typed relation",
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
        elif item.disposition == BCL_BEHAVIOR_DISPOSITION_SCOPED:
            if not item.scoped_out_reason or not item.validation_boundary or not item.rationale:
                findings.append(
                    _finding(
                        "behavior_inventory_out_of_scope_disposition_incomplete",
                        "out-of-scope independent behavior requires reason, owner boundary, and rationale",
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
        elif item.disposition == BCL_BEHAVIOR_DISPOSITION_BLOCKED:
            findings.append(
                _finding(
                    "behavior_inventory_blocked_gap",
                    "independent behavior remains a visible blocked gap until its native owner closes it",
                    metadata={"behavior_id": item.behavior_id},
                )
            )
            if not item.blocked_gap_reason or not item.validation_boundary or not item.rationale:
                findings.append(
                    _finding(
                        "behavior_inventory_blocked_gap_incomplete",
                        "blocked behavior gap requires an explicit reason, owner boundary, and rationale",
                        metadata={"behavior_id": item.behavior_id},
                    )
                )
    return BehaviorInventoryReport(
        ok=not findings,
        inventory_id=normalized.inventory_id,
        inventory_fingerprint=normalized.fingerprint,
        expected_behavior_ids=expected_ids,
        actual_behavior_ids=actual_ids,
        missing_behavior_ids=missing_ids,
        unexpected_behavior_ids=unexpected_ids,
        findings=tuple(findings),
    )


_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[/\\]")
_GLOB_MAGIC = frozenset("*?[")
_LIVE_SOURCE_RESOLUTION_CODES = frozenset(
    {
        "source_surface_ref_missing",
        "source_surface_ref_unsafe",
        "source_surface_glob_empty",
        "source_surface_glob_unbounded",
        "source_surface_anchor_missing",
        "source_surface_member_duplicate",
    }
)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _review_source_classification(
    surface: BehaviorSourceSurface,
    findings: list[BehaviorCommitmentFinding],
) -> None:
    """Keep physical source type separate from its authority participation."""

    if surface.source_classification not in BCL_SOURCE_CLASSIFICATIONS:
        findings.append(
            _finding(
                "source_surface_classification_invalid",
                "expected source item must be classified as an external normative contract, observed external behavior, implementation, test, or generated evidence",
                surface_id=surface.surface_id,
            )
        )
        return
    if (
        surface.source_classification
        == BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT
        and surface.source_authority_role != BCL_SOURCE_AUTHORITY_NORMATIVE
    ):
        findings.append(
            _finding(
                "source_surface_classification_role_mismatch",
                "an external normative contract must use the normative authority role",
                surface_id=surface.surface_id,
            )
        )
    elif (
        surface.source_classification
        == BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR
        and surface.source_authority_role != BCL_SOURCE_AUTHORITY_OBSERVED
    ):
        findings.append(
            _finding(
                "source_surface_classification_role_mismatch",
                "observed external behavior must use the observed authority role",
                surface_id=surface.surface_id,
            )
        )
    elif (
        surface.source_classification
        in {
            BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
            BCL_SOURCE_CLASSIFICATION_TEST,
            BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE,
        }
        and surface.source_authority_role
        not in {
            BCL_SOURCE_AUTHORITY_SUPPORTING,
            BCL_SOURCE_AUTHORITY_HISTORICAL,
        }
    ):
        findings.append(
            _finding(
                "source_surface_classification_role_mismatch",
                "implementation, test, and generated evidence may be supporting or historical evidence but cannot be normative or observed external authority",
                surface_id=surface.surface_id,
            )
        )
    if (
        surface.source_classification
        in {
            BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION,
            BCL_SOURCE_CLASSIFICATION_TEST,
            BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE,
        }
        and surface.coverage_disposition == BCL_DISPOSITION_MODELED
    ):
        findings.append(
            _finding(
                "source_surface_non_contract_authority_forbidden",
                "implementation, test, and generated evidence cannot license an external behavior commitment; bind them through blueprint and native evidence inventories",
                surface_id=surface.surface_id,
            )
        )


def _review_complete_source_identity(
    surface: BehaviorSourceSurface,
    ledger: BehaviorCommitmentLedger,
    findings: list[BehaviorCommitmentFinding],
) -> None:
    """Require one exact identity and one non-overlapping coverage disposition."""

    required_values = {
        "source_system_id": surface.source_system_id,
        "native_artifact_id": surface.native_artifact_id,
        "content_fingerprint": surface.content_fingerprint,
        "inventory_revision": surface.inventory_revision,
        "declared_semantics_fingerprint": surface.declared_semantics_fingerprint,
    }
    missing = tuple(
        field_name
        for field_name, value in required_values.items()
        if not str(value)
    )
    if missing:
        findings.append(
            _finding(
                "source_surface_identity_incomplete",
                "expected source item is missing stable native, content, inventory, or semantic identity",
                surface_id=surface.surface_id,
                metadata={"missing_fields": list(missing)},
            )
        )
    if surface.content_fingerprint and not surface.content_fingerprint.startswith(
        "sha256:"
    ):
        findings.append(
            _finding(
                "source_surface_content_fingerprint_invalid",
                "source content identity must use a sha256 fingerprint",
                surface_id=surface.surface_id,
            )
        )
    if (
        surface.declared_semantics_fingerprint
        and not surface.declared_semantics_fingerprint.startswith("sha256:")
    ):
        findings.append(
            _finding(
                "source_surface_semantics_fingerprint_invalid",
                "source semantic identity must use a sha256 fingerprint",
                surface_id=surface.surface_id,
            )
        )
    if surface.inventory_revision != ledger.source_inventory_revision:
        findings.append(
            _finding(
                "source_surface_inventory_revision_stale",
                "source row does not match the current immutable inventory revision",
                surface_id=surface.surface_id,
                metadata={
                    "surface_revision": surface.inventory_revision,
                    "ledger_revision": ledger.source_inventory_revision,
                },
            )
        )
    if not surface.discovery_evidence_ids:
        findings.append(
            _finding(
                "source_surface_discovery_evidence_missing",
                "expected source item requires current discovery evidence",
                surface_id=surface.surface_id,
            )
        )
    if surface.source_authority_role not in BCL_SOURCE_AUTHORITY_ROLES:
        findings.append(
            _finding(
                "source_surface_authority_role_invalid",
                "expected source item must declare a normative, observed, supporting, or historical role",
                surface_id=surface.surface_id,
            )
        )
    _review_source_classification(surface, findings)
    if surface.coverage_disposition not in BCL_COVERAGE_DISPOSITIONS:
        findings.append(
            _finding(
                "source_surface_disposition_invalid",
                "expected source item must have exactly one modeled, delegated, or scoped disposition",
                surface_id=surface.surface_id,
            )
        )
        return

    modeled_fields = bool(surface.commitment_ids)
    delegated_fields = bool(
        surface.delegated_owner_inventory_id
        or surface.delegation_relation_type
        or surface.native_evidence_ids
    )
    scoped_fields = surface.has_scoped_disposition()
    if surface.coverage_disposition == BCL_DISPOSITION_MODELED:
        if len(surface.commitment_ids) != 1 or delegated_fields or scoped_fields:
            findings.append(
                _finding(
                    "source_surface_modeled_disposition_incomplete",
                    "modeled disposition needs exactly one commitment and no delegated or scoped success path",
                    surface_id=surface.surface_id,
                )
            )
    elif surface.coverage_disposition == BCL_DISPOSITION_DELEGATED:
        if (
            modeled_fields
            or scoped_fields
            or not surface.delegated_owner_inventory_id
            or not surface.delegation_relation_type
            or not surface.native_evidence_ids
        ):
            findings.append(
                _finding(
                    "source_surface_delegated_disposition_incomplete",
                    "delegated disposition needs one native owner, typed relation, and native evidence only",
                    surface_id=surface.surface_id,
                )
            )
    elif surface.coverage_disposition == BCL_DISPOSITION_SCOPED:
        if (
            surface.in_scope
            or modeled_fields
            or delegated_fields
            or not scoped_fields
        ):
            findings.append(
                _finding(
                    "source_surface_scoped_disposition_incomplete",
                    "scoped disposition needs owner, reason, boundary, and rationale only",
                    surface_id=surface.surface_id,
                )
            )


def _commitment_anchor_findings(ledger: BehaviorCommitmentLedger, project_root: Any) -> list[BehaviorCommitmentFinding]:
    """Each in-scope commitment names the code entrypoint that keeps it and the tests that guard it."""
    from .map.check import anchor_problems

    active = [commitment for commitment in ledger.commitments if commitment.in_scope]
    problems = anchor_problems(project_root, [anchor for c in active for anchor in (*c.entrypoints, *c.tests)])
    findings: list[BehaviorCommitmentFinding] = []
    for commitment in active:
        if not commitment.entrypoints:
            findings.append(_finding("commitment_entrypoint_unanchored",
                                     "name the code entrypoint that keeps this promise in entrypoints ('path:Symbol')",
                                     commitment_id=commitment.commitment_id))
        if not commitment.tests:
            findings.append(_finding("commitment_test_unanchored",
                                     "name the tests that guard this promise in tests ('tests/x.py:test_name')",
                                     commitment_id=commitment.commitment_id))
        for anchor in (*commitment.entrypoints, *commitment.tests):
            if anchor in problems:
                findings.append(_finding("commitment_anchor_missing", problems[anchor],
                                         commitment_id=commitment.commitment_id, metadata={"anchor": anchor}))
    return findings


def review_behavior_commitment_ledger(
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
    *,
    project_root: Any = None,
) -> BehaviorCommitmentCoverageReport:
    """Review the declared promises, their sources, owners and tests.

    With ``project_root`` each in-scope commitment must also name its entrypoint and tests as anchors
    that exist in the real code (``commitment_entrypoint_unanchored``, ``commitment_test_unanchored``,
    ``commitment_anchor_missing``).
    """

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
    if ledger.subject_lane not in SUBJECT_LANES:
        findings.append(
            _finding(
                "ledger_subject_lane_invalid",
                "ledger must bind exactly one current model-system subject lane",
                metadata={"subject_lane": ledger.subject_lane},
            )
        )

    complete_inventory_required = bool(
        ledger.require_complete_source_inventory
        or ledger.change_mode
        in {
            BCL_CHANGE_BOOTSTRAP_LEDGER,
            BCL_CHANGE_COVERAGE_GAP_BACKFILL,
        }
    )
    if complete_inventory_required:
        if not ledger.expected_source_surface_ids:
            findings.append(
                _finding(
                    "expected_source_inventory_missing",
                    "broad coverage requires an independently derived expected source inventory",
                )
            )
        if len(set(ledger.expected_source_surface_ids)) != len(
            ledger.expected_source_surface_ids
        ):
            findings.append(
                _finding(
                    "expected_source_inventory_duplicate_id",
                    "expected source inventory contains duplicate identities",
                )
            )
        if not ledger.source_inventory_revision:
            findings.append(
                _finding(
                    "source_inventory_revision_missing",
                    "complete source inventory requires one immutable revision",
                )
            )
        if not ledger.source_inventory_fingerprint.startswith("sha256:"):
            findings.append(
                _finding(
                    "source_inventory_fingerprint_missing",
                    "complete source inventory requires one content fingerprint",
                )
            )
        if not ledger.source_inventory_evidence_ids:
            findings.append(
                _finding(
                    "source_inventory_evidence_missing",
                    "complete source inventory requires current discovery evidence",
                )
            )

    behavior_inventory_report: BehaviorInventoryReport | None = None
    if ledger.independent_behavior_inventory is None:
        if ledger.require_complete_behavior_inventory:
            findings.append(
                _finding(
                    "independent_behavior_inventory_missing",
                    "complete behavior coverage requires an independently discovered behavior inventory",
                )
            )
    else:
        behavior_inventory_report = review_independent_behavior_inventory(
            ledger.independent_behavior_inventory,
            ledger=ledger,
        )
        findings.extend(behavior_inventory_report.findings)

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

    expected_surface_ids = set(ledger.expected_source_surface_ids)
    actual_surface_ids = set(surface_by_id)
    missing_source_surface_ids = tuple(
        sorted(expected_surface_ids - actual_surface_ids)
    )
    unexpected_source_surface_ids = tuple(
        sorted(actual_surface_ids - expected_surface_ids)
    )
    if complete_inventory_required:
        for surface_id in missing_source_surface_ids:
            findings.append(
                _finding(
                    "expected_source_surface_missing",
                    "expected source item has no modeled, delegated, or scoped disposition",
                    surface_id=surface_id,
                )
            )
        for surface_id in unexpected_source_surface_ids:
            findings.append(
                _finding(
                    "unexpected_source_surface",
                    "ledger contains a source row outside the immutable expected inventory",
                    surface_id=surface_id,
                )
            )

    normative_by_intent: dict[str, set[str]] = {}
    observed_by_intent: dict[str, set[str]] = {}
    for surface in ledger.source_surfaces:
        if complete_inventory_required:
            _review_complete_source_identity(surface, ledger, findings)
        target = (
            normative_by_intent
            if surface.source_classification
            == BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT
            and surface.source_authority_role == BCL_SOURCE_AUTHORITY_NORMATIVE
            else observed_by_intent
            if surface.source_classification
            == BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR
            and surface.source_authority_role == BCL_SOURCE_AUTHORITY_OBSERVED
            else None
        )
        if target is not None and surface.declared_semantics_fingerprint:
            for intent_id in surface.business_intent_ids:
                target.setdefault(intent_id, set()).add(
                    surface.declared_semantics_fingerprint
                )
    for intent_id, fingerprints in normative_by_intent.items():
        if len(fingerprints) > 1:
            findings.append(
                _finding(
                    "incompatible_normative_sources",
                    "current normative sources disagree for one exact business intent",
                    commitment_id=intent_id,
                    metadata={"semantic_fingerprints": sorted(fingerprints)},
                )
            )
        observed = observed_by_intent.get(intent_id, set())
        if observed and not observed.issubset(fingerprints):
            findings.append(
                _finding(
                    "normative_observed_mismatch",
                    "observed behavior differs from the normative source and requires the existing miss or repair route",
                    commitment_id=intent_id,
                    metadata={
                        "normative_fingerprints": sorted(fingerprints),
                        "observed_fingerprints": sorted(observed),
                    },
                )
            )

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
    covered_commitment_ids: list[str] = []

    for commitment in ledger.commitments:
        _review_commitment(
            commitment,
            surface_by_id,
            commitment_by_id,
            ledger,
            findings,
            extra_commitment_ids,
        )
    if project_root is not None:
        findings.extend(_commitment_anchor_findings(ledger, project_root))

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
        missing_source_surface_ids=missing_source_surface_ids,
        unexpected_source_surface_ids=unexpected_source_surface_ids,
        unmapped_surface_ids=tuple(dict.fromkeys(unmapped_surface_ids)),
        extra_commitment_ids=tuple(dict.fromkeys(extra_commitment_ids)),
        behavior_inventory_id=(
            behavior_inventory_report.inventory_id
            if behavior_inventory_report is not None
            else ""
        ),
        behavior_inventory_fingerprint=(
            behavior_inventory_report.inventory_fingerprint
            if behavior_inventory_report is not None
            else ""
        ),
        missing_behavior_ids=(
            behavior_inventory_report.missing_behavior_ids
            if behavior_inventory_report is not None
            else ()
        ),
        unexpected_behavior_ids=(
            behavior_inventory_report.unexpected_behavior_ids
            if behavior_inventory_report is not None
            else ()
        ),
    )


def _review_surface(
    surface: BehaviorSourceSurface,
    commitment_by_id: Mapping[str, BehaviorCommitment],
    findings: list[BehaviorCommitmentFinding],
    unmapped_surface_ids: list[str],
    *,
    stable_identity_required: bool = False,
) -> None:
    if not stable_identity_required:
        _review_source_classification(surface, findings)
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
    if (
        surface.coverage_disposition == BCL_DISPOSITION_MODELED
        and not surface.commitment_ids
    ):
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


def _review_commitment(
    commitment: BehaviorCommitment,
    surface_by_id: Mapping[str, BehaviorSourceSurface],
    commitment_by_id: Mapping[str, BehaviorCommitment],
    ledger: BehaviorCommitmentLedger,
    findings: list[BehaviorCommitmentFinding],
    extra_commitment_ids: list[str],
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
    if ledger.broad_claim() or ledger.require_complete_source_inventory:
        normative_surface_ids = tuple(
            surface_id
            for surface_id in commitment.source_surface_ids
            if surface_id in surface_by_id
            and surface_by_id[surface_id].licenses_external_commitment(
                commitment.commitment_id
            )
        )
        if not normative_surface_ids:
            findings.append(
                _finding(
                    "commitment_current_normative_source_missing",
                    "broad commitment coverage requires a current external normative contract; observed behavior, implementation, tests, and generated evidence cannot license the promise",
                    commitment_id=commitment.commitment_id,
                    metadata={
                        "source_surface_ids": list(commitment.source_surface_ids),
                    },
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
    if ledger.broad_claim():
        _review_change_lifecycle(commitment, findings)



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
    if commitment.miss_origin_state != BCL_MISS_ORIGIN_NONE:
        if commitment.model_sync_state != BCL_MODEL_SYNC_OWNER_CURRENT:
            findings.append(
                _finding(
                    "commitment_model_miss_backfeed_incomplete",
                    "model-miss backfeed must map to the existing commitment and current owner model",
                    commitment_id=commitment.commitment_id,
                    metadata={"commitment": commitment.to_dict()},
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
            "source_classification",
            model_id=model_id,
            values=BCL_SOURCE_CLASSIFICATIONS,
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
        ContractAxis(
            "source_authority_participation",
            model_id=model_id,
            values=BCL_SOURCE_AUTHORITY_ROLES,
            source_route=BEHAVIOR_COMMITMENT_ROUTE_ID,
        ),
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
            "migration_state",
            model_id=model_id,
            values=("current_shape", "legacy_same_plane", "legacy_ambiguous", "custom_python_blocked", "dual_authority_blocked"),
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
            values=("singular", "legacy_plural_one", "legacy_plural_many", "singular_plural_conflict"),
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

    routes = ("model_test_alignment", "test_mesh")
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
            "source_classification_authority",
            model_id=model_id,
            axis_ids=(
                "source_classification",
                "source_authority_participation",
                "source_mapping_state",
            ),
            required_routes=routes + ("model_test_alignment", "test_mesh"),
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "single_owner_evidence",
            model_id=model_id,
            axis_ids=("commitment_kind", "owner_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "relation_and_release_gate",
            model_id=model_id,
            axis_ids=("relation_state", "release_gate_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "cross_plane_relation",
            model_id=model_id,
            axis_ids=("behavior_plane", "relation_type", "relation_target_plane"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "lookup_migration_state",
            model_id=model_id,
            axis_ids=("behavior_plane", "lookup_binding_state", "migration_state"),
            required_routes=routes,
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
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "model_miss_backfeed",
            model_id=model_id,
            axis_ids=("miss_origin_state", "model_sync_state"),
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
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=BEHAVIOR_COMMITMENT_ORACLE_ID,
        ),
        ContractInteractionGroup(
            "singular_primary_path_migration",
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
            required_routes=routes + (PRIMARY_PATH_ROUTE_ID,),
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
        require_full_product=True,
        allow_partitioned_product=True,
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
    """Build the canonical finite ContractExhaustionMesh plan for this route."""

    plan = ContractExhaustionPlan(
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
        required_route_ids=("model_test_alignment", "test_mesh", PRIMARY_PATH_ROUTE_ID),
        require_coverage_universe=True,
        metadata={
            # ContractExhaustionMesh owns finite matrix generation here.  The
            # acceptance ids remain required downstream obligations; terminal
            # CompositeHandoffResult records are produced by the consuming
            # route owners, not fabricated during matrix review.
            "composite_handoff_results_deferred": True,
        },
        coverage_universe=default_behavior_commitment_coverage_universe(model_id=model_id, claim_scope=claim_scope),
    )
    return plan


def behavior_commitment_risk_gate_ids(report: BehaviorCommitmentCoverageReport) -> tuple[str, ...]:
    """Return the risk gate ids a broad claim should preserve for this report."""

    base = (
        f"risk_gate:{BCL_RISK_GATE_COVERAGE}:{report.ledger_id}",
        f"risk_gate:{BCL_RISK_GATE_CARTESIAN_COVERAGE}:{report.ledger_id}",
    )
    return tuple(dict.fromkeys(base + report.required_risk_gate_ids))


# Model kit: the plan grows or shrinks by commitments and paths; the ledger review, a static scan of the real
# tests and the primary-path review are the invariants.
@dataclass(frozen=True)
class BehaviorPlan:
    """What a behavior-commitment model explores: the promise ledger and, for its path-sensitive promises,
    the primary-path authority plan.  Either part may be None."""

    ledger: BehaviorCommitmentLedger | None = None
    authority: PrimaryPathAuthorityPlan | None = None


def _ledger_of(plan: Any) -> BehaviorCommitmentLedger | None:
    return plan if isinstance(plan, BehaviorCommitmentLedger) else getattr(plan, "ledger", None)


def _authority_of(plan: Any) -> PrimaryPathAuthorityPlan | None:
    return plan if isinstance(plan, PrimaryPathAuthorityPlan) else getattr(plan, "authority", None)


def _with_ledger(plan: Any, ledger: BehaviorCommitmentLedger) -> Any:
    return ledger if isinstance(plan, BehaviorCommitmentLedger) else replace(plan, ledger=ledger)


def _with_authority(plan: Any, authority: PrimaryPathAuthorityPlan) -> Any:
    return authority if isinstance(plan, PrimaryPathAuthorityPlan) else replace(plan, authority=authority)


def _put(items: tuple, item: Any, key) -> tuple:
    """Replace the item with the same key in place, or append it."""
    if any(key(existing) == key(item) for existing in items):
        return tuple(item if key(existing) == key(item) else existing for existing in items)
    return items + (item,)


def _registered(expected: tuple[str, ...], new: Sequence[str]) -> tuple[str, ...]:
    """An expected inventory the plan already keeps also lists the new ids; an empty one stays empty."""
    return tuple(dict.fromkeys((*expected, *(value for value in new if value)))) if expected else expected


def add_commitment(plan: Any, commitment: BehaviorCommitment | str, *surfaces: BehaviorSourceSurface) -> Any:
    """Plan edit for a behavior-commitment model: add a promise (or replace the one with the same id).

    ``commitment`` is a ``BehaviorCommitment`` or the id of one already in the ledger (to map more surfaces,
    such as an alias or a second UI, to it).  Each surface is added (or replaces the one with the same id) and
    linked both ways with the commitment.  Expected inventories the ledger already keeps also list the new ids.
    """
    ledger = _ledger_of(plan)
    if isinstance(commitment, str):
        commitment = next(c for c in ledger.commitments if c.commitment_id == commitment)
    commitment = _coerce_commitment(commitment)
    linked = []
    for surface in map(_coerce_surface, surfaces):
        linked.append(replace(
            surface, commitment_ids=tuple(dict.fromkeys((*surface.commitment_ids, commitment.commitment_id))),
            business_intent_ids=tuple(dict.fromkeys((*surface.business_intent_ids, commitment.business_intent_id)))
            if commitment.business_intent_id else surface.business_intent_ids))
    commitment = replace(commitment, source_surface_ids=tuple(dict.fromkeys(
        (*commitment.source_surface_ids, *(surface.surface_id for surface in linked)))))
    sources = ledger.source_surfaces
    for surface in linked:
        sources = _put(sources, surface, lambda s: s.surface_id)
    return _with_ledger(plan, replace(
        ledger, commitments=_put(ledger.commitments, commitment, lambda c: c.commitment_id), source_surfaces=sources,
        expected_commitment_ids=_registered(ledger.expected_commitment_ids, [commitment.commitment_id]),
        expected_business_intent_ids=_registered(ledger.expected_business_intent_ids, [commitment.business_intent_id]),
        expected_source_surface_ids=_registered(ledger.expected_source_surface_ids, [s.surface_id for s in linked])))


def retire_commitment(plan: Any, commitment_id: str, reason: str, *, owner: str = "",
                      replacement_commitment_id: str = "") -> Any:
    """Plan edit: a promise leaves service.

    The commitment stays in the ledger, out of scope with a closing disposition: removed, or replaced by
    ``replacement_commitment_id``.  Its intent leaves the expected intents unless another active commitment
    keeps it, and surfaces that map only to it leave scope (disposition ``scoped``) with the same reason.
    Each disposition takes ``owner`` (default: the item's, the commitment's or the ledger's owner), the item's
    or the commitment's validation boundary, and the item's rationale (default: ``reason``).
    """
    ledger = _ledger_of(plan)
    old = next(c for c in ledger.commitments if c.commitment_id == commitment_id)

    def closed(item):
        return replace(item, in_scope=False, scoped_out_reason=reason,
                       owner=owner or item.owner or old.owner or ledger.owner,
                       validation_boundary=item.validation_boundary or old.validation_boundary or ledger.validation_boundary,
                       rationale=item.rationale or reason)

    retired = replace(closed(old), replacement_state=BCL_REPLACEMENT_REPLACED if replacement_commitment_id
                      else BCL_REPLACEMENT_REMOVED_SCOPED_OUT,
                      metadata=dict(old.metadata, replacement_commitment_id=replacement_commitment_id)
                      if replacement_commitment_id else old.metadata)
    commitments = tuple(retired if c.commitment_id == commitment_id else c for c in ledger.commitments)
    kept = {c.business_intent_id for c in commitments if c.active_external_commitment()}
    surfaces = tuple(replace(closed(s), coverage_disposition=BCL_DISPOSITION_SCOPED, commitment_ids=())
                     if s.in_scope and set(s.commitment_ids) == {commitment_id} else s for s in ledger.source_surfaces)
    return _with_ledger(plan, replace(
        ledger, commitments=commitments, source_surfaces=surfaces,
        expected_business_intent_ids=tuple(i for i in ledger.expected_business_intent_ids
                                           if i != old.business_intent_id or i in kept)))


def add_path(plan: Any, path: PrimaryPathContract | FallbackPathCandidate) -> Any:
    """Plan edit: add a primary path or another path to the same result (or replace the one with the same id).

    A ``PrimaryPathContract`` that names ``replaces_primary_path_id`` replaces that primary path.  Expected
    inventories the authority plan already keeps also list the new ids.
    """
    authority = _authority_of(plan)
    if isinstance(path, PrimaryPathContract):
        kept = tuple(p for p in authority.primary_paths if p.business_path_id != path.replaces_primary_path_id
                     or p.business_path_id == path.business_path_id)
        authority = replace(
            authority, primary_paths=_put(kept, path, lambda p: p.business_path_id),
            expected_business_intent_ids=_registered(authority.expected_business_intent_ids, [path.business_intent_id]),
            expected_surface_ids=_registered(authority.expected_surface_ids, path.source_surface_ids))
    else:
        authority = replace(
            authority, fallback_candidates=_put(authority.fallback_candidates, path, lambda c: c.candidate_path_id),
            expected_candidate_ids=_registered(authority.expected_candidate_ids, [path.candidate_path_id]),
            expected_surface_ids=_registered(authority.expected_surface_ids, [path.source_surface_id]))
    return _with_authority(plan, authority)


def retire_path(plan: Any, path_id: str, reason: str, disposition: str = PPA_DISPOSITION_DELETE) -> Any:
    """Plan edit: another path to the same result leaves service.

    The candidate keeps its inventory row with a closing ``disposition`` (default ``delete``), out of scope with
    ``reason``; it no longer runs or returns success when the primary path fails.  A primary path is retired by
    adding its replacement (``add_path`` with ``replaces_primary_path_id``).
    """
    authority = _authority_of(plan)
    if any(p.business_path_id == path_id for p in authority.primary_paths):
        raise ValueError(f"{path_id} is a primary path: add its replacement with add_path(replaces_primary_path_id=...)")
    return _with_authority(plan, replace(authority, fallback_candidates=tuple(
        replace(c, disposition=disposition, in_scope=False, scoped_out_reason=reason, candidate_trigger=PPA_TRIGGER_NEVER,
                candidate_behavior=PPA_BEHAVIOR_NO_OP, invokes_on_primary_failure=False,
                returns_success_after_primary_failure=False)
        if c.candidate_path_id == path_id else c for c in authority.fallback_candidates)))


def _file_of(anchor: str) -> str:
    return anchor.partition(":")[0]


def _test_touch_problems(commitment: BehaviorCommitment, facts: Any, seen: dict) -> list[str]:
    """Static: every entrypoint is imported or called by one of the commitment's test files and every test file
    imports or calls one of its entrypoints.  Missing files are left to the anchor check."""
    entries = [e for e in dict.fromkeys(commitment.entrypoints) if ":" in e and (facts.root / _file_of(e)).is_file()]
    files = [f for f in dict.fromkeys(map(_file_of, commitment.tests)) if (facts.root / f).is_file()]
    if not entries or not files:
        return []
    for entry in entries:
        for test_file in files:
            if (entry, test_file) not in seen:
                seen[entry, test_file] = bool(facts.symbol_references(entry, [test_file]))
    idle = [f for f in files if not any(seen[e, f] for e in entries)]
    problems = [f"{f} never imports or calls {', '.join(entries)}" for f in idle]
    if len(idle) < len(files):
        problems += [f"no test of {commitment.commitment_id} imports or calls {e} (tests: {', '.join(files)})"
                     for e in entries if not any(seen[e, f] for f in files)]
    return problems


def _test_touch_report(ledger: BehaviorCommitmentLedger, facts: Any, seen: dict) -> BehaviorCommitmentCoverageReport:
    findings = tuple(_finding("commitment_test_misses_entrypoint", problem, commitment_id=c.commitment_id)
                     for c in ledger.commitments if c.in_scope for problem in _test_touch_problems(c, facts, seen))
    return BehaviorCommitmentCoverageReport(
        ok=not findings, ledger_id=ledger.ledger_id, findings=findings,
        decision=BCL_DECISION_BLOCKED if findings else BCL_DECISION_GREEN,
        confidence=BCL_CONFIDENCE_BLOCKED if findings else BCL_CONFIDENCE_FULL)


def behavior_commitment_explorer(initial, edits, *, explore=None, max_sequence_length: int = 2, root=None):
    """Behavior-commitment model: named edits add or retire commitments and paths; every plan reached must pass.

    The plan is a ``BehaviorCommitmentLedger``, a ``PrimaryPathAuthorityPlan`` or a ``BehaviorPlan`` holding both.
    Invariants for a ledger: ``behavior_commitment_review_accepts`` (``review_behavior_commitment_ledger`` with
    the project root, so entrypoint and test anchors must exist) and ``commitment_tests_touch_entrypoints`` (a
    static scan of the real tests under ``root``, default the current directory: each test file of a commitment
    imports or calls one of its entrypoints, and each entrypoint is imported or called by one of its test
    files).  For an authority plan: ``primary_path_authority_review_accepts`` (``review_primary_path_authority``).
    """
    from .kit import plan_explorer
    from .map.facts import CodeFacts

    sample, facts, seen = initial(), CodeFacts(root), {}
    reviews: dict[str, Any] = {}
    if _ledger_of(sample) is not None:
        reviews["behavior_commitment_review_accepts"] = lambda plan: review_behavior_commitment_ledger(
            _ledger_of(plan), project_root=facts.root)
        reviews["commitment_tests_touch_entrypoints"] = lambda plan: _test_touch_report(_ledger_of(plan), facts, seen)
    if _authority_of(sample) is not None:
        reviews["primary_path_authority_review_accepts"] = lambda plan: review_primary_path_authority(_authority_of(plan))
    if not reviews:
        raise ValueError("a behavior-commitment model needs a ledger, a primary-path authority plan or both")
    (name, review), *others = reviews.items()
    return plan_explorer(initial, edits, review, explore=explore, invariant_name=name,
                         max_sequence_length=max_sequence_length, extra_reviews=dict(others))


def _names_code(value: str) -> bool:
    from .map.common import SOURCE_EXTS

    return ":" in value and Path(_file_of(value)).suffix in SOURCE_EXTS


def behavior_commitment_code_facts(plan: Any, *, anchors=(), root=None):
    """Compare a behavior plan with the real code (static code facts, nothing is executed).

    * ledger: every in-scope commitment names its entrypoints and tests, they exist, its test files import or
      call its entrypoints (both ways, as in ``behavior_commitment_explorer``);
    * authority plan: a primary entrypoint that names code ('path:Symbol') exists; a path candidate that names
      code is gone when its disposition is ``delete`` and exists otherwise, and one that delegates to the
      primary path imports or calls the primary entrypoint;
    * every anchor exists.
    """
    from .map.check import anchor_problems
    from .map.facts import CodeFacts

    facts, seen = CodeFacts(root), {}
    if anchors:
        facts.anchors_exist(anchors)
    ledger, authority = _ledger_of(plan), _authority_of(plan)
    for commitment in (c for c in (ledger.commitments if ledger else ()) if c.in_scope):
        cid, named = commitment.commitment_id, tuple(dict.fromkeys((*commitment.entrypoints, *commitment.tests)))
        facts.check(f"{cid} names its entrypoints and tests", bool(commitment.entrypoints and commitment.tests),
                    "entrypoints or tests is empty")
        problems = anchor_problems(facts.root, list(named))
        for anchor in named:
            facts.check(f"{cid}: {anchor} exists", anchor not in problems, problems.get(anchor, ""))
        touch = _test_touch_problems(commitment, facts, seen)
        facts.check(f"{cid}: its tests import or call its entrypoints", not touch, "; ".join(touch))
    if authority is not None:
        named = [p.primary_entrypoint_id for p in authority.primary_paths if _names_code(p.primary_entrypoint_id)]
        named += [c.candidate_path_id for c in authority.fallback_candidates if _names_code(c.candidate_path_id)]
        problems = anchor_problems(facts.root, named)
        primary = {p.business_path_id: p.primary_entrypoint_id for p in authority.primary_paths}
        for path in authority.primary_paths:
            if _names_code(path.primary_entrypoint_id):
                facts.check(f"primary path {path.business_path_id}: {path.primary_entrypoint_id} exists",
                            path.primary_entrypoint_id not in problems, problems.get(path.primary_entrypoint_id, ""))
        for candidate in authority.fallback_candidates:
            anchor = candidate.candidate_path_id
            if not _names_code(anchor):
                continue
            if candidate.disposition == PPA_DISPOSITION_DELETE:
                facts.check(f"{anchor} is gone (disposition delete)", anchor in problems, f"{anchor} still exists")
                continue
            if not facts.check(f"{anchor} exists", anchor not in problems, problems.get(anchor, "")):
                continue
            target = primary.get(candidate.delegates_to_path_id or candidate.fallback_for_path_id, "")
            if (candidate.candidate_behavior == PPA_BEHAVIOR_DELEGATE_TO_PRIMARY
                    or candidate.disposition in (PPA_DISPOSITION_DELEGATE_TO_PRIMARY, PPA_DISPOSITION_PRESERVE_FACADE)) \
                    and _names_code(target) and target not in problems:
                own = _file_of(anchor) == _file_of(target)
                calls = (len(facts.references(target.partition(":")[2].split(".")[-1], [_file_of(anchor)])) > 1 if own
                         else bool(facts.symbol_references(target, [_file_of(anchor)])))
                facts.check(f"{anchor} delegates to the primary path {target}", calls,
                            f"{_file_of(anchor)} never imports or calls {target}")
    return facts.report()


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
    "BCL_DISPOSITION_DELEGATED",
    "BCL_DISPOSITION_MODELED",
    "BCL_DISPOSITION_SCOPED",
    "BCL_COVERAGE_DISPOSITIONS",
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
    "BCL_LOOKUP_STATUS_FALLBACK",
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
    "BCL_BEHAVIOR_INVENTORY_SCHEMA",
    "BCL_INTENT_DISPOSITION_ACCEPTED_CURRENT",
    "BCL_INTENT_DISPOSITION_SUPERSEDED",
    "BCL_INTENT_DISPOSITION_MERGED",
    "BCL_INTENT_DISPOSITION_RETIRED",
    "BCL_INTENT_DISPOSITION_REJECTED",
    "BCL_INTENT_DISPOSITION_UNRESOLVED",
    "BCL_INTENT_DISPOSITIONS",
    "BCL_LIFECYCLE_LANES",
    "BCL_LIFECYCLE_REQUIRED",
    "BCL_LIFECYCLE_NOT_APPLICABLE",
    "BCL_BEHAVIOR_DISPOSITION_MODELED",
    "BCL_BEHAVIOR_DISPOSITION_DELEGATED",
    "BCL_BEHAVIOR_DISPOSITION_SCOPED",
    "BCL_BEHAVIOR_DISPOSITION_BLOCKED",
    "BCL_BEHAVIOR_INVENTORY_DISPOSITIONS",
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
    "BCL_SOURCE_AUTHORITY_HISTORICAL",
    "BCL_SOURCE_AUTHORITY_NORMATIVE",
    "BCL_SOURCE_AUTHORITY_OBSERVED",
    "BCL_SOURCE_AUTHORITY_ROLES",
    "BCL_SOURCE_AUTHORITY_SUPPORTING",
    "BCL_SOURCE_CLI",
    "BCL_SOURCE_CLASSIFICATION_EXTERNAL_NORMATIVE_CONTRACT",
    "BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE",
    "BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION",
    "BCL_SOURCE_CLASSIFICATION_OBSERVED_EXTERNAL_BEHAVIOR",
    "BCL_SOURCE_CLASSIFICATION_TEST",
    "BCL_SOURCE_CLASSIFICATIONS",
    "BCL_SOURCE_CODE",
    "BCL_SOURCE_DOC",
    "BCL_SOURCE_FRESHNESS_CHANGED",
    "BCL_SOURCE_FRESHNESS_CURRENT",
    "BCL_SOURCE_FRESHNESS_MISSING",
    "BCL_SOURCE_FRESHNESS_STATES",
    "BCL_SOURCE_FRESHNESS_UNCHECKED",
    "BCL_SOURCE_FILE_AGGREGATE_SCHEMA",
    "BCL_SOURCE_INVENTORY_SCHEMA",
    "BCL_LIVE_SOURCE_IDENTITY_METADATA_KEY",
    "BCL_SOURCE_FIELD",
    "BCL_SOURCE_KINDS",
    "BCL_SOURCE_WORK_CONTEXT",
    "BCL_SOURCE_PROCESS",
    "BCL_SOURCE_RELEASE",
    "BCL_SOURCE_SKILL",
    "BCL_SOURCE_TEST",
    "BCL_SOURCE_UI",
    "BEHAVIOR_COMMITMENT_ORACLE_ID",
    "BEHAVIOR_COMMITMENT_ROUTE_ID",
    "BehaviorCommitment",
    "BehaviorCommitmentRelation",
    "BehaviorCommitmentCoverageReport",
    "BehaviorCommitmentFinding",
    "BehaviorCommitmentLedger",
    "BehaviorInventoryItem",
    "BehaviorInventory",
    "BehaviorInventoryReport",
    "BehaviorExternalDifference",
    "BehaviorLookupBinding",
    "BehaviorPlan",
    "BehaviorSourceSurface",
    "behavior_commitment_contract_exhaustion_plan",
    "behavior_commitment_ledger_fingerprint",
    "behavior_commitment_ledger_from_mapping",
    "behavior_commitment_ledger_to_mapping",
    "behavior_commitment_relation_allowed",
    "behavior_commitment_risk_gate_ids",
    "default_behavior_commitment_axes",
    "default_behavior_commitment_coverage_universe",
    "default_behavior_commitment_interaction_groups",
    "load_behavior_commitment_ledger",
    "review_independent_behavior_inventory",
    "review_behavior_commitment_ledger",
    "write_behavior_commitment_ledger",
    "add_commitment",
    "add_path",
    "behavior_commitment_code_facts",
    "behavior_commitment_explorer",
    "retire_commitment",
    "retire_path",
]
