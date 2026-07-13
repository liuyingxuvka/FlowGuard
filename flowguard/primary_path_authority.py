"""Primary runtime authority checks for no-fallback FlowGuard workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from .proof_artifact import (
    ProofArtifactRef,
    coerce_proof_artifact_ref,
    proof_artifact_gap_codes,
)


PRIMARY_PATH_ROUTE_ID = "primary_path_authority"
PPA_CONTRACT_ORACLE_PRIMARY_FAILURE = "primary_path_failure_must_not_fallback"

PPA_CLAIM_SCOPE_ROUTINE = "routine"
PPA_CLAIM_SCOPE_DONE = "done"
PPA_CLAIM_SCOPE_RELEASE = "release"
PPA_CLAIM_SCOPE_PUBLISH = "publish"
PPA_CLAIM_SCOPE_PRODUCTION = "production"
PPA_CLAIM_SCOPE_ARCHIVE = "archive"
PPA_CLAIM_SCOPE_FULL = "full"
PPA_BROAD_CLAIM_SCOPES = {
    PPA_CLAIM_SCOPE_DONE,
    PPA_CLAIM_SCOPE_RELEASE,
    PPA_CLAIM_SCOPE_PUBLISH,
    PPA_CLAIM_SCOPE_PRODUCTION,
    PPA_CLAIM_SCOPE_ARCHIVE,
    PPA_CLAIM_SCOPE_FULL,
}

PPA_AUTHORITY_PRIMARY = "primary"
PPA_AUTHORITY_EXTERNAL_FACADE = "external_facade"
PPA_AUTHORITY_MANUAL_RECOVERY = "manual_recovery"
PPA_AUTHORITY_MIGRATION_ONLY = "migration_only"
PPA_AUTHORITY_FALLBACK_CANDIDATE = "fallback_candidate"
PPA_AUTHORITY_ROLES = {
    PPA_AUTHORITY_PRIMARY,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_AUTHORITY_MANUAL_RECOVERY,
    PPA_AUTHORITY_MIGRATION_ONLY,
    PPA_AUTHORITY_FALLBACK_CANDIDATE,
}

PPA_FAILURE_POLICY_FAIL_CLOSED = "fail_closed"
PPA_FAILURE_POLICY_RETRY_SAME_PATH_ONLY = "retry_same_path_only"
PPA_FAILURE_POLICY_MANUAL_RECOVERY_ONLY = "manual_recovery_only"
PPA_FAILURE_POLICY_EXTERNAL_FACADE_TO_PRIMARY = "external_facade_to_primary"
PPA_FAILURE_POLICIES = {
    PPA_FAILURE_POLICY_FAIL_CLOSED,
    PPA_FAILURE_POLICY_RETRY_SAME_PATH_ONLY,
    PPA_FAILURE_POLICY_MANUAL_RECOVERY_ONLY,
    PPA_FAILURE_POLICY_EXTERNAL_FACADE_TO_PRIMARY,
}

PPA_CANDIDATE_NONE = "none"
PPA_CANDIDATE_LEGACY_PATH = "legacy_path"
PPA_CANDIDATE_ALIAS = "alias"
PPA_CANDIDATE_WRAPPER = "wrapper"
PPA_CANDIDATE_COMPATIBILITY_FACADE = "compatibility_facade"
PPA_CANDIDATE_HELPER_ROUTE = "helper_route"
PPA_CANDIDATE_OLD_FIELD = "old_field"
PPA_CANDIDATE_BACKUP_CACHE = "backup_cache"
PPA_CANDIDATE_MANUAL_RECOVERY = "manual_recovery"
PPA_CANDIDATE_MIGRATION_PATH = "migration_path"
PPA_CANDIDATE_UNKNOWN = "unknown"
PPA_CANDIDATE_SURFACES = {
    PPA_CANDIDATE_NONE,
    PPA_CANDIDATE_LEGACY_PATH,
    PPA_CANDIDATE_ALIAS,
    PPA_CANDIDATE_WRAPPER,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_CANDIDATE_HELPER_ROUTE,
    PPA_CANDIDATE_OLD_FIELD,
    PPA_CANDIDATE_BACKUP_CACHE,
    PPA_CANDIDATE_MANUAL_RECOVERY,
    PPA_CANDIDATE_MIGRATION_PATH,
}

PPA_TRIGGER_NEVER = "never"
PPA_TRIGGER_EXPLICIT_USER_CHOICE = "explicit_user_choice"
PPA_TRIGGER_MANUAL_OPERATOR_ACTION = "manual_operator_action"
PPA_TRIGGER_PRIMARY_FAILURE = "primary_failure"
PPA_TRIGGER_MISSING_FIELD = "missing_field"
PPA_TRIGGER_PARSE_ERROR = "parse_error"
PPA_TRIGGER_TIMEOUT = "timeout"
PPA_TRIGGER_UNKNOWN_ROUTE = "unknown_route"
PPA_AUTO_TRIGGERS = {
    PPA_TRIGGER_PRIMARY_FAILURE,
    PPA_TRIGGER_MISSING_FIELD,
    PPA_TRIGGER_PARSE_ERROR,
    PPA_TRIGGER_TIMEOUT,
    PPA_TRIGGER_UNKNOWN_ROUTE,
}

PPA_BEHAVIOR_NO_OP = "no_op"
PPA_BEHAVIOR_DELEGATE_TO_PRIMARY = "delegate_to_primary"
PPA_BEHAVIOR_READ_STATE = "read_state"
PPA_BEHAVIOR_WRITE_STATE = "write_state"
PPA_BEHAVIOR_EMIT_SIDE_EFFECT = "emit_side_effect"
PPA_BEHAVIOR_RETURN_SUCCESS = "return_success"
PPA_BEHAVIOR_MUTATE_TERMINAL = "mutate_terminal"
PPA_BUSINESS_LOGIC_BEHAVIORS = {
    PPA_BEHAVIOR_READ_STATE,
    PPA_BEHAVIOR_WRITE_STATE,
    PPA_BEHAVIOR_EMIT_SIDE_EFFECT,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_BEHAVIOR_MUTATE_TERMINAL,
}

PPA_DISPOSITION_DELETE = "delete"
PPA_DISPOSITION_BLOCK = "block"
PPA_DISPOSITION_MIGRATE = "migrate"
PPA_DISPOSITION_DELEGATE_TO_PRIMARY = "delegate_to_primary"
PPA_DISPOSITION_PRESERVE_FACADE = "preserve_facade"
PPA_DISPOSITION_MANUAL_ONLY = "manual_only"
PPA_DISPOSITION_SCOPE_OUT = "scope_out"
PPA_DISPOSITION_UNKNOWN = "unknown"
PPA_DISPOSITIONS = {
    PPA_DISPOSITION_DELETE,
    PPA_DISPOSITION_BLOCK,
    PPA_DISPOSITION_MIGRATE,
    PPA_DISPOSITION_DELEGATE_TO_PRIMARY,
    PPA_DISPOSITION_PRESERVE_FACADE,
    PPA_DISPOSITION_MANUAL_ONLY,
    PPA_DISPOSITION_SCOPE_OUT,
    PPA_DISPOSITION_UNKNOWN,
}

PPA_EVIDENCE_CURRENT_PASS = "current_pass"
PPA_EVIDENCE_MISSING = "missing"
PPA_EVIDENCE_STALE = "stale"
PPA_EVIDENCE_SKIPPED = "skipped"
PPA_EVIDENCE_PROGRESS_ONLY = "progress_only"
PPA_EVIDENCE_RELEASE_ONLY = "release_only"

PPA_DECISION_GREEN = "primary_path_authority_green"
PPA_DECISION_SCOPED = "primary_path_authority_scoped"
PPA_DECISION_BLOCKED = "primary_path_authority_blocked"
PPA_CONFIDENCE_FULL = "full"
PPA_CONFIDENCE_SCOPED = "scoped"
PPA_CONFIDENCE_BLOCKED = "blocked"

PPA_RISK_GATE_AUTHORITY = "primary_path_authority"
PPA_RISK_GATE_CARTESIAN_COVERAGE = "primary_path_authority_cartesian_coverage"

PPA_DEFAULT_BUSINESS_INTENTS = (
    "read_state",
    "write_state",
    "emit_side_effect",
    "validate_contract",
    "migrate_data",
    "public_api_call",
)
PPA_DEFAULT_PRIMARY_RESULTS = (
    "success",
    "visible_error",
    "exception",
    "partial_failure",
    "timeout",
    "stale_state",
    "terminal_replay",
)
PPA_DEFAULT_CANDIDATE_TRIGGERS = (
    PPA_TRIGGER_NEVER,
    PPA_TRIGGER_EXPLICIT_USER_CHOICE,
    PPA_TRIGGER_MANUAL_OPERATOR_ACTION,
    PPA_TRIGGER_PRIMARY_FAILURE,
    PPA_TRIGGER_MISSING_FIELD,
    PPA_TRIGGER_PARSE_ERROR,
    PPA_TRIGGER_TIMEOUT,
    PPA_TRIGGER_UNKNOWN_ROUTE,
)
PPA_DEFAULT_CANDIDATE_BEHAVIORS = (
    PPA_BEHAVIOR_NO_OP,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_BEHAVIOR_READ_STATE,
    PPA_BEHAVIOR_WRITE_STATE,
    PPA_BEHAVIOR_EMIT_SIDE_EFFECT,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_BEHAVIOR_MUTATE_TERMINAL,
)
PPA_DEFAULT_EVIDENCE_STATES = (
    PPA_EVIDENCE_CURRENT_PASS,
    PPA_EVIDENCE_MISSING,
    PPA_EVIDENCE_STALE,
    PPA_EVIDENCE_SKIPPED,
    PPA_EVIDENCE_PROGRESS_ONLY,
    PPA_EVIDENCE_RELEASE_ONLY,
)


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _metadata(values: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(values or {})


@dataclass(frozen=True)
class PrimaryPathContract:
    """One primary runtime authority for one business intent."""

    business_path_id: str
    business_intent: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_entrypoint_id: str = ""
    owner_model_id: str = ""
    owner_code_contract_id: str = ""
    expected_terminal: str = ""
    preconditions: tuple[str, ...] = ()
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    failure_policy: str = PPA_FAILURE_POLICY_FAIL_CLOSED
    allowed_error_state_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    runtime_evidence_state: str = ""
    runtime_observation_ids: tuple[str, ...] = ()
    required_obligation_ids: tuple[str, ...] = ()
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    source_surface_ids: tuple[str, ...] = ()
    replaces_primary_path_id: str = ""
    old_primary_path_disposition: str = ""
    replacement_evidence_ids: tuple[str, ...] = ()
    authority_role: str = PPA_AUTHORITY_PRIMARY
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "business_path_id", str(self.business_path_id))
        object.__setattr__(self, "business_intent", str(self.business_intent))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_entrypoint_id", str(self.primary_entrypoint_id))
        object.__setattr__(self, "owner_model_id", str(self.owner_model_id))
        object.__setattr__(self, "owner_code_contract_id", str(self.owner_code_contract_id))
        object.__setattr__(self, "expected_terminal", str(self.expected_terminal))
        object.__setattr__(self, "preconditions", _as_tuple(self.preconditions))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "failure_policy", str(self.failure_policy))
        object.__setattr__(self, "allowed_error_state_ids", _as_tuple(self.allowed_error_state_ids))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "runtime_evidence_state", str(self.runtime_evidence_state))
        object.__setattr__(self, "runtime_observation_ids", _as_tuple(self.runtime_observation_ids))
        object.__setattr__(self, "required_obligation_ids", _as_tuple(self.required_obligation_ids))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "source_surface_ids", _as_tuple(self.source_surface_ids))
        object.__setattr__(self, "replaces_primary_path_id", str(self.replaces_primary_path_id))
        object.__setattr__(self, "old_primary_path_disposition", str(self.old_primary_path_disposition))
        object.__setattr__(self, "replacement_evidence_ids", _as_tuple(self.replacement_evidence_ids))
        object.__setattr__(self, "authority_role", str(self.authority_role or PPA_AUTHORITY_PRIMARY))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def identity_key(self) -> tuple[str, str]:
        intent_id = self.business_intent_id.strip().lower()
        if not intent_id:
            intent_id = self.business_intent.strip().lower()
        return (intent_id, "exact_business_intent")

    def complete(self) -> bool:
        return bool(
            self.business_path_id
            and (self.business_intent_id or self.business_intent)
            and self.primary_entrypoint_id
            and self.owner_model_id
            and self.owner_code_contract_id
            and self.expected_terminal
            and self.failure_policy in PPA_FAILURE_POLICIES
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "business_path_id": self.business_path_id,
            "business_intent": self.business_intent,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_entrypoint_id": self.primary_entrypoint_id,
            "owner_model_id": self.owner_model_id,
            "owner_code_contract_id": self.owner_code_contract_id,
            "expected_terminal": self.expected_terminal,
            "preconditions": list(self.preconditions),
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "failure_policy": self.failure_policy,
            "allowed_error_state_ids": list(self.allowed_error_state_ids),
            "evidence_ids": list(self.evidence_ids),
            "runtime_evidence_state": self.runtime_evidence_state,
            "runtime_observation_ids": list(self.runtime_observation_ids),
            "required_obligation_ids": list(self.required_obligation_ids),
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "source_surface_ids": list(self.source_surface_ids),
            "replaces_primary_path_id": self.replaces_primary_path_id,
            "old_primary_path_disposition": self.old_primary_path_disposition,
            "replacement_evidence_ids": list(self.replacement_evidence_ids),
            "authority_role": self.authority_role,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FallbackPathCandidate:
    """A non-primary surface that might become alternate runtime authority."""

    candidate_path_id: str
    fallback_for_path_id: str = ""
    business_intent: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    source_surface_id: str = ""
    delegates_to_path_id: str = ""
    expected_terminal: str = ""
    runtime_observation_ids: tuple[str, ...] = ()
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    candidate_surface: str = PPA_CANDIDATE_UNKNOWN
    candidate_trigger: str = PPA_TRIGGER_NEVER
    candidate_behavior: str = PPA_BEHAVIOR_NO_OP
    invokes_on_primary_failure: bool = False
    returns_success_after_primary_failure: bool = False
    shares_business_intent: bool = True
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    classification: str = PPA_AUTHORITY_FALLBACK_CANDIDATE
    disposition: str = PPA_DISPOSITION_UNKNOWN
    evidence_refs: tuple[str, ...] = ()
    in_scope: bool = True
    scoped_out_reason: str = ""
    compatibility_intent: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_path_id", str(self.candidate_path_id))
        object.__setattr__(self, "fallback_for_path_id", str(self.fallback_for_path_id))
        object.__setattr__(self, "business_intent", str(self.business_intent))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "source_surface_id", str(self.source_surface_id))
        object.__setattr__(self, "delegates_to_path_id", str(self.delegates_to_path_id))
        object.__setattr__(self, "expected_terminal", str(self.expected_terminal))
        object.__setattr__(self, "runtime_observation_ids", _as_tuple(self.runtime_observation_ids))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "candidate_surface", str(self.candidate_surface or PPA_CANDIDATE_UNKNOWN))
        object.__setattr__(self, "candidate_trigger", str(self.candidate_trigger or PPA_TRIGGER_NEVER))
        object.__setattr__(self, "candidate_behavior", str(self.candidate_behavior or PPA_BEHAVIOR_NO_OP))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "classification", str(self.classification or PPA_AUTHORITY_FALLBACK_CANDIDATE))
        object.__setattr__(self, "disposition", str(self.disposition or PPA_DISPOSITION_UNKNOWN))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "compatibility_intent", str(self.compatibility_intent))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def auto_invoked(self) -> bool:
        return self.invokes_on_primary_failure or self.candidate_trigger in PPA_AUTO_TRIGGERS

    def has_business_logic(self) -> bool:
        return bool(
            self.state_writes
            or self.side_effects
            or self.candidate_behavior in PPA_BUSINESS_LOGIC_BEHAVIORS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_path_id": self.candidate_path_id,
            "fallback_for_path_id": self.fallback_for_path_id,
            "business_intent": self.business_intent,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "source_surface_id": self.source_surface_id,
            "delegates_to_path_id": self.delegates_to_path_id,
            "expected_terminal": self.expected_terminal,
            "runtime_observation_ids": list(self.runtime_observation_ids),
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "candidate_surface": self.candidate_surface,
            "candidate_trigger": self.candidate_trigger,
            "candidate_behavior": self.candidate_behavior,
            "invokes_on_primary_failure": self.invokes_on_primary_failure,
            "returns_success_after_primary_failure": self.returns_success_after_primary_failure,
            "shares_business_intent": self.shares_business_intent,
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "classification": self.classification,
            "disposition": self.disposition,
            "evidence_refs": list(self.evidence_refs),
            "in_scope": self.in_scope,
            "scoped_out_reason": self.scoped_out_reason,
            "compatibility_intent": self.compatibility_intent,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PrimaryPathAuthorityPlan:
    """Plan for checking primary runtime authority and fallback disposition."""

    plan_id: str
    primary_paths: tuple[PrimaryPathContract, ...] = ()
    fallback_candidates: tuple[FallbackPathCandidate, ...] = ()
    claim_scope: str = PPA_CLAIM_SCOPE_ROUTINE
    require_cartesian_coverage: bool = False
    coverage_case_ids: tuple[str, ...] = ()
    coverage_shard_ids: tuple[str, ...] = ()
    coverage_receipt_ids: tuple[str, ...] = ()
    risk_gate_ids: tuple[str, ...] = ()
    expected_business_intents: tuple[str, ...] = ()
    expected_business_intent_ids: tuple[str, ...] = ()
    expected_candidate_ids: tuple[str, ...] = ()
    expected_surface_ids: tuple[str, ...] = ()
    inventory_revision: str = ""
    inventory_evidence_ids: tuple[str, ...] = ()
    preflight_id: str = ""
    behavior_commitment_ledger_id: str = ""
    existing_current_path_ids: tuple[str, ...] = ()
    require_complete_candidate_inventory: bool = False
    require_material_runtime_evidence: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(
            self,
            "primary_paths",
            tuple(item if isinstance(item, PrimaryPathContract) else PrimaryPathContract(**item) for item in self.primary_paths),
        )
        object.__setattr__(
            self,
            "fallback_candidates",
            tuple(
                item if isinstance(item, FallbackPathCandidate) else FallbackPathCandidate(**item)
                for item in self.fallback_candidates
            ),
        )
        object.__setattr__(self, "claim_scope", str(self.claim_scope or PPA_CLAIM_SCOPE_ROUTINE))
        object.__setattr__(self, "require_cartesian_coverage", bool(self.require_cartesian_coverage))
        object.__setattr__(self, "coverage_case_ids", _as_tuple(self.coverage_case_ids))
        object.__setattr__(self, "coverage_shard_ids", _as_tuple(self.coverage_shard_ids))
        object.__setattr__(self, "coverage_receipt_ids", _as_tuple(self.coverage_receipt_ids))
        object.__setattr__(self, "risk_gate_ids", _as_tuple(self.risk_gate_ids))
        object.__setattr__(self, "expected_business_intents", _as_tuple(self.expected_business_intents))
        object.__setattr__(self, "expected_business_intent_ids", _as_tuple(self.expected_business_intent_ids))
        object.__setattr__(self, "expected_candidate_ids", _as_tuple(self.expected_candidate_ids))
        object.__setattr__(self, "expected_surface_ids", _as_tuple(self.expected_surface_ids))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "inventory_evidence_ids", _as_tuple(self.inventory_evidence_ids))
        object.__setattr__(self, "preflight_id", str(self.preflight_id))
        object.__setattr__(self, "behavior_commitment_ledger_id", str(self.behavior_commitment_ledger_id))
        object.__setattr__(self, "existing_current_path_ids", _as_tuple(self.existing_current_path_ids))
        object.__setattr__(self, "require_complete_candidate_inventory", bool(self.require_complete_candidate_inventory))
        object.__setattr__(self, "require_material_runtime_evidence", bool(self.require_material_runtime_evidence))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def broad_claim(self) -> bool:
        return self.claim_scope in PPA_BROAD_CLAIM_SCOPES

    def coverage_required(self) -> bool:
        return self.require_cartesian_coverage or self.broad_claim()

    def material_authority_required(self) -> bool:
        return bool(
            self.require_material_runtime_evidence
            or self.broad_claim()
            or self.expected_business_intent_ids
            or self.expected_candidate_ids
            or self.expected_surface_ids
            or self.inventory_revision
            or self.inventory_evidence_ids
            or self.preflight_id
            or self.behavior_commitment_ledger_id
            or self.existing_current_path_ids
        )

    def complete_inventory_required(self) -> bool:
        return self.require_complete_candidate_inventory or self.material_authority_required()

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "primary_paths": [path.to_dict() for path in self.primary_paths],
            "fallback_candidates": [candidate.to_dict() for candidate in self.fallback_candidates],
            "claim_scope": self.claim_scope,
            "require_cartesian_coverage": self.require_cartesian_coverage,
            "coverage_case_ids": list(self.coverage_case_ids),
            "coverage_shard_ids": list(self.coverage_shard_ids),
            "coverage_receipt_ids": list(self.coverage_receipt_ids),
            "risk_gate_ids": list(self.risk_gate_ids),
            "expected_business_intents": list(self.expected_business_intents),
            "expected_business_intent_ids": list(self.expected_business_intent_ids),
            "expected_candidate_ids": list(self.expected_candidate_ids),
            "expected_surface_ids": list(self.expected_surface_ids),
            "inventory_revision": self.inventory_revision,
            "inventory_evidence_ids": list(self.inventory_evidence_ids),
            "preflight_id": self.preflight_id,
            "behavior_commitment_ledger_id": self.behavior_commitment_ledger_id,
            "existing_current_path_ids": list(self.existing_current_path_ids),
            "require_complete_candidate_inventory": self.require_complete_candidate_inventory,
            "require_material_runtime_evidence": self.require_material_runtime_evidence,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PrimaryPathAuthorityFinding:
    """One primary path authority gap."""

    code: str
    message: str
    severity: str = "blocker"
    path_id: str = ""
    candidate_path_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity or "blocker"))
        object.__setattr__(self, "path_id", str(self.path_id))
        object.__setattr__(self, "candidate_path_id", str(self.candidate_path_id))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "path_id": self.path_id,
            "candidate_path_id": self.candidate_path_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PrimaryPathAuthorityReport:
    """Structured primary path authority review result."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    findings: tuple[PrimaryPathAuthorityFinding, ...] = ()
    primary_path_id: str = ""
    primary_path_ids: tuple[str, ...] = ()
    business_intent_id: str = ""
    business_intent_ids: tuple[str, ...] = ()
    behavior_commitment_id: str = ""
    behavior_commitment_ids: tuple[str, ...] = ()
    fallback_candidate_ids: tuple[str, ...] = ()
    missing_candidate_ids: tuple[str, ...] = ()
    covered_surface_ids: tuple[str, ...] = ()
    missing_surface_ids: tuple[str, ...] = ()
    runtime_observation_ids: tuple[str, ...] = ()
    proof_artifact_ids: tuple[str, ...] = ()
    evidence_current: bool = False
    coverage_case_ids: tuple[str, ...] = ()
    coverage_shard_ids: tuple[str, ...] = ()
    coverage_receipt_ids: tuple[str, ...] = ()
    risk_gate_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "primary_path_ids", _as_tuple(self.primary_path_ids))
        if not self.primary_path_id and len(self.primary_path_ids) == 1:
            object.__setattr__(self, "primary_path_id", self.primary_path_ids[0])
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "business_intent_ids", _as_tuple(self.business_intent_ids))
        if not self.business_intent_id and len(self.business_intent_ids) == 1:
            object.__setattr__(self, "business_intent_id", self.business_intent_ids[0])
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "behavior_commitment_ids", _as_tuple(self.behavior_commitment_ids))
        if not self.behavior_commitment_id and len(self.behavior_commitment_ids) == 1:
            object.__setattr__(self, "behavior_commitment_id", self.behavior_commitment_ids[0])
        object.__setattr__(self, "fallback_candidate_ids", _as_tuple(self.fallback_candidate_ids))
        object.__setattr__(self, "missing_candidate_ids", _as_tuple(self.missing_candidate_ids))
        object.__setattr__(self, "covered_surface_ids", _as_tuple(self.covered_surface_ids))
        object.__setattr__(self, "missing_surface_ids", _as_tuple(self.missing_surface_ids))
        object.__setattr__(self, "runtime_observation_ids", _as_tuple(self.runtime_observation_ids))
        object.__setattr__(self, "proof_artifact_ids", _as_tuple(self.proof_artifact_ids))
        object.__setattr__(self, "evidence_current", bool(self.evidence_current))
        object.__setattr__(self, "coverage_case_ids", _as_tuple(self.coverage_case_ids))
        object.__setattr__(self, "coverage_shard_ids", _as_tuple(self.coverage_shard_ids))
        object.__setattr__(self, "coverage_receipt_ids", _as_tuple(self.coverage_receipt_ids))
        object.__setattr__(self, "risk_gate_ids", _as_tuple(self.risk_gate_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: plan={self.plan_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard primary path authority ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"primary_paths: {len(self.primary_path_ids)}",
            f"fallback_candidates: {len(self.fallback_candidate_ids)}",
            f"coverage_receipts: {len(self.coverage_receipt_ids)}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"path: {finding.path_id or '(none)'}",
                    f"candidate: {finding.candidate_path_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "primary_path_id": self.primary_path_id,
            "primary_path_ids": list(self.primary_path_ids),
            "business_intent_id": self.business_intent_id,
            "business_intent_ids": list(self.business_intent_ids),
            "behavior_commitment_id": self.behavior_commitment_id,
            "behavior_commitment_ids": list(self.behavior_commitment_ids),
            "fallback_candidate_ids": list(self.fallback_candidate_ids),
            "missing_candidate_ids": list(self.missing_candidate_ids),
            "covered_surface_ids": list(self.covered_surface_ids),
            "missing_surface_ids": list(self.missing_surface_ids),
            "runtime_observation_ids": list(self.runtime_observation_ids),
            "proof_artifact_ids": list(self.proof_artifact_ids),
            "evidence_current": self.evidence_current,
            "coverage_case_ids": list(self.coverage_case_ids),
            "coverage_shard_ids": list(self.coverage_shard_ids),
            "coverage_receipt_ids": list(self.coverage_receipt_ids),
            "risk_gate_ids": list(self.risk_gate_ids),
            "summary": self.summary,
        }


def _finding(
    code: str,
    message: str,
    *,
    path_id: str = "",
    candidate_path_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> PrimaryPathAuthorityFinding:
    return PrimaryPathAuthorityFinding(
        code,
        message,
        severity=severity,
        path_id=path_id,
        candidate_path_id=candidate_path_id,
        metadata=metadata or {},
    )


def review_primary_path_authority(
    plan: PrimaryPathAuthorityPlan | Mapping[str, Any],
) -> PrimaryPathAuthorityReport:
    """Review no-fallback authority for path-sensitive FlowGuard claims."""

    plan = plan if isinstance(plan, PrimaryPathAuthorityPlan) else PrimaryPathAuthorityPlan(**plan)
    findings: list[PrimaryPathAuthorityFinding] = []
    material_required = plan.material_authority_required()

    if not plan.primary_paths:
        findings.append(_finding("missing_primary_authority", "no primary path contract is declared"))

    seen_keys: dict[tuple[str, str], PrimaryPathContract] = {}
    for path in plan.primary_paths:
        if not path.business_path_id:
            findings.append(_finding("missing_business_path_id", "primary path contract must name a business path id", metadata=path.to_dict()))
        if not path.complete():
            findings.append(
                _finding(
                    "primary_path_contract_incomplete",
                    "primary path contract must name primary entrypoint, owner model, owner code contract, and known failure policy",
                    path_id=path.business_path_id,
                    metadata=path.to_dict(),
                )
            )
        if path.authority_role != PPA_AUTHORITY_PRIMARY:
            findings.append(
                _finding(
                    "primary_path_role_not_primary",
                    "primary path contract must be classified as primary authority",
                    path_id=path.business_path_id,
                    metadata=path.to_dict(),
                )
            )
        key = path.identity_key()
        if key in seen_keys:
            findings.append(
                _finding(
                    "duplicate_primary_runtime_authority",
                    "business intent has more than one primary runtime authority",
                    path_id=path.business_path_id,
                    metadata={"first": seen_keys[key].to_dict(), "duplicate": path.to_dict()},
                )
            )
        seen_keys[key] = path
        if material_required:
            missing_identity_fields = tuple(
                field_name
                for field_name in (
                    "business_intent_id",
                    "behavior_commitment_id",
                )
                if not getattr(path, field_name)
            )
            if missing_identity_fields:
                findings.append(
                    _finding(
                        "primary_path_stable_identity_missing",
                        "material primary-path authority requires stable business-intent and commitment ids",
                        path_id=path.business_path_id,
                        metadata={"missing_fields": list(missing_identity_fields)},
                    )
                )
            if not path.source_surface_ids:
                findings.append(
                    _finding(
                        "primary_path_source_surface_missing",
                        "material primary-path authority must identify the public surfaces owned by the path",
                        path_id=path.business_path_id,
                    )
                )
            evidence_gaps = list(
                proof_artifact_gap_codes(
                    path.proof_artifact,
                    declared_status="passed" if path.runtime_evidence_state == PPA_EVIDENCE_CURRENT_PASS else "",
                    required_obligation_ids=path.required_obligation_ids,
                    require_result_path=True,
                    require_fingerprints=True,
                    require_external_scope=True,
                )
            )
            if path.runtime_evidence_state != PPA_EVIDENCE_CURRENT_PASS:
                evidence_gaps.append(
                    ("runtime_evidence_state_not_current_pass", path.runtime_evidence_state or "missing")
                )
            if not path.runtime_observation_ids:
                evidence_gaps.append(("runtime_observation_missing", "no runtime observation ids"))
            if not path.required_obligation_ids:
                evidence_gaps.append(("runtime_obligation_missing", "no required obligation ids"))
            elif path.proof_artifact is not None and not set(path.required_obligation_ids).issubset(
                path.proof_artifact.covered_obligation_ids
            ):
                evidence_gaps.append(
                    ("runtime_obligation_coverage_incomplete", "proof artifact does not cover every required obligation")
                )
            if evidence_gaps:
                findings.append(
                    _finding(
                        "primary_path_runtime_evidence_not_current",
                        "primary-path authority lacks a current external runtime observation and proof artifact",
                        path_id=path.business_path_id,
                        metadata={"gaps": [list(item) for item in evidence_gaps]},
                    )
                )
            if plan.existing_current_path_ids and path.business_path_id not in plan.existing_current_path_ids:
                replacement_complete = bool(
                    path.replaces_primary_path_id in plan.existing_current_path_ids
                    and path.old_primary_path_disposition in PPA_DISPOSITIONS
                    and path.old_primary_path_disposition != PPA_DISPOSITION_UNKNOWN
                    and path.replacement_evidence_ids
                )
                if not replacement_complete:
                    findings.append(
                        _finding(
                            "existing_primary_path_not_reused",
                            "an equivalent current primary path exists; selecting another path requires explicit replacement disposition and evidence",
                            path_id=path.business_path_id,
                            metadata={"existing_current_path_ids": list(plan.existing_current_path_ids)},
                        )
                    )

    declared_intents = {path.business_intent for path in plan.primary_paths if path.business_intent}
    for expected in plan.expected_business_intents:
        if expected not in declared_intents:
            findings.append(
                _finding(
                    "expected_business_intent_missing_primary",
                    "expected business intent has no primary runtime authority",
                    metadata={"business_intent": expected},
                )
            )

    declared_intent_ids = {
        path.business_intent_id for path in plan.primary_paths if path.business_intent_id
    }
    for expected in plan.expected_business_intent_ids:
        if expected not in declared_intent_ids:
            findings.append(
                _finding(
                    "expected_business_intent_id_missing_primary",
                    "expected stable business intent has no primary runtime authority",
                    metadata={"business_intent_id": expected},
                )
            )

    primary_path_by_id = {
        path.business_path_id: path for path in plan.primary_paths if path.business_path_id
    }
    seen_candidate_ids: set[str] = set()
    seen_surface_owners: dict[str, str] = {
        surface_id: path.business_path_id
        for path in plan.primary_paths
        for surface_id in path.source_surface_ids
    }
    for candidate in plan.fallback_candidates:
        _review_candidate(candidate, findings, material_required=material_required)
        if not candidate.candidate_path_id:
            findings.append(
                _finding(
                    "fallback_candidate_path_id_missing",
                    "candidate inventory row must name a stable candidate path id",
                )
            )
        elif candidate.candidate_path_id in seen_candidate_ids:
            findings.append(
                _finding(
                    "duplicate_primary_path_candidate_id",
                    "candidate inventory contains the same candidate path id more than once",
                    candidate_path_id=candidate.candidate_path_id,
                )
            )
        seen_candidate_ids.add(candidate.candidate_path_id)
        primary = primary_path_by_id.get(candidate.fallback_for_path_id)
        if candidate.in_scope and primary is None:
            findings.append(
                _finding(
                    "fallback_candidate_primary_path_unknown",
                    "candidate points to a primary path that is not declared in the authority plan",
                    path_id=candidate.fallback_for_path_id,
                    candidate_path_id=candidate.candidate_path_id,
                )
            )
        if material_required and primary is not None:
            if candidate.business_intent_id != primary.business_intent_id:
                findings.append(
                    _finding(
                        "fallback_candidate_intent_mismatch",
                        "candidate and primary path disagree on stable business intent identity",
                        path_id=primary.business_path_id,
                        candidate_path_id=candidate.candidate_path_id,
                    )
                )
            if candidate.behavior_commitment_id != primary.behavior_commitment_id:
                findings.append(
                    _finding(
                        "fallback_candidate_commitment_mismatch",
                        "candidate and primary path disagree on behavior commitment identity",
                        path_id=primary.business_path_id,
                        candidate_path_id=candidate.candidate_path_id,
                    )
                )
        if candidate.source_surface_id:
            existing_owner = seen_surface_owners.get(candidate.source_surface_id)
            if existing_owner and existing_owner != candidate.candidate_path_id:
                findings.append(
                    _finding(
                        "duplicate_primary_path_surface_id",
                        "one public surface is claimed by more than one primary or candidate path inventory row",
                        candidate_path_id=candidate.candidate_path_id,
                        metadata={"first_owner": existing_owner, "surface_id": candidate.source_surface_id},
                    )
                )
            seen_surface_owners[candidate.source_surface_id] = candidate.candidate_path_id

    candidate_ids = {
        candidate.candidate_path_id for candidate in plan.fallback_candidates if candidate.candidate_path_id
    }
    missing_candidate_ids = tuple(
        candidate_id for candidate_id in plan.expected_candidate_ids if candidate_id not in candidate_ids
    )
    for candidate_id in missing_candidate_ids:
        findings.append(
            _finding(
                "expected_primary_path_candidate_missing",
                "expected same-intent path candidate is absent from the complete candidate inventory",
                candidate_path_id=candidate_id,
            )
        )

    covered_surface_ids = tuple(
        dict.fromkeys(
            [surface_id for path in plan.primary_paths for surface_id in path.source_surface_ids]
            + [candidate.source_surface_id for candidate in plan.fallback_candidates if candidate.source_surface_id]
        )
    )
    missing_surface_ids = tuple(
        surface_id for surface_id in plan.expected_surface_ids if surface_id not in covered_surface_ids
    )
    for surface_id in missing_surface_ids:
        findings.append(
            _finding(
                "expected_primary_path_surface_missing",
                "expected same-intent public surface is absent from the authority inventory",
                candidate_path_id=surface_id,
            )
        )
    if plan.complete_inventory_required():
        for field_name, present in (
            ("inventory_revision", bool(plan.inventory_revision)),
            ("inventory_evidence_ids", bool(plan.inventory_evidence_ids)),
            ("preflight_id", bool(plan.preflight_id)),
            ("behavior_commitment_ledger_id", bool(plan.behavior_commitment_ledger_id)),
            ("expected_business_intent_ids", bool(plan.expected_business_intent_ids)),
            ("expected_surface_ids", bool(plan.expected_surface_ids)),
        ):
            if not present:
                findings.append(
                    _finding(
                        "primary_path_inventory_material_missing",
                        "complete primary-path inventory is missing a required discovery or ownership reference",
                        metadata={"missing_field": field_name},
                    )
                )

    if plan.coverage_required():
        if not plan.coverage_receipt_ids:
            findings.append(
                _finding(
                    "primary_path_cartesian_coverage_missing",
                    "broad primary-path authority claim requires current Cartesian coverage receipt ids",
                )
            )
        if not plan.coverage_shard_ids:
            findings.append(
                _finding(
                    "primary_path_coverage_shards_missing",
                    "broad primary-path authority claim requires TestMesh-owned coverage shard ids",
                )
            )
        if not plan.risk_gate_ids:
            findings.append(
                _finding(
                    "primary_path_risk_gate_missing",
                    "broad primary-path authority claim requires Risk Evidence Ledger gate ids",
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if blockers:
        decision = PPA_DECISION_BLOCKED
        confidence = PPA_CONFIDENCE_BLOCKED
    elif findings:
        decision = PPA_DECISION_SCOPED
        confidence = PPA_CONFIDENCE_SCOPED
    else:
        decision = PPA_DECISION_GREEN
        confidence = PPA_CONFIDENCE_FULL

    return PrimaryPathAuthorityReport(
        ok=not blockers,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        primary_path_id=plan.primary_paths[0].business_path_id if len(plan.primary_paths) == 1 else "",
        primary_path_ids=tuple(path.business_path_id for path in plan.primary_paths),
        business_intent_id=plan.primary_paths[0].business_intent_id if len(plan.primary_paths) == 1 else "",
        business_intent_ids=tuple(
            dict.fromkeys(path.business_intent_id for path in plan.primary_paths if path.business_intent_id)
        ),
        behavior_commitment_id=plan.primary_paths[0].behavior_commitment_id if len(plan.primary_paths) == 1 else "",
        behavior_commitment_ids=tuple(
            dict.fromkeys(path.behavior_commitment_id for path in plan.primary_paths if path.behavior_commitment_id)
        ),
        fallback_candidate_ids=tuple(candidate.candidate_path_id for candidate in plan.fallback_candidates),
        missing_candidate_ids=missing_candidate_ids,
        covered_surface_ids=covered_surface_ids,
        missing_surface_ids=missing_surface_ids,
        runtime_observation_ids=tuple(
            dict.fromkeys(
                observation_id
                for path in plan.primary_paths
                for observation_id in path.runtime_observation_ids
            )
        ),
        proof_artifact_ids=tuple(
            path.proof_artifact.artifact_id
            for path in plan.primary_paths
            if path.proof_artifact is not None
        ),
        evidence_current=bool(material_required and not blockers),
        coverage_case_ids=plan.coverage_case_ids,
        coverage_shard_ids=plan.coverage_shard_ids,
        coverage_receipt_ids=plan.coverage_receipt_ids,
        risk_gate_ids=plan.risk_gate_ids,
    )


def _review_candidate(
    candidate: FallbackPathCandidate,
    findings: list[PrimaryPathAuthorityFinding],
    *,
    material_required: bool = False,
) -> None:
    metadata = candidate.to_dict()
    if not candidate.in_scope:
        if not candidate.scoped_out_reason:
            findings.append(
                _finding(
                    "fallback_candidate_scoped_without_reason",
                    "out-of-scope fallback candidate must explain why it cannot affect the claim",
                    candidate_path_id=candidate.candidate_path_id,
                    metadata=metadata,
                )
            )
        return
    if material_required:
        missing_fields = tuple(
            field_name
            for field_name in (
                "business_intent_id",
                "behavior_commitment_id",
                "source_surface_id",
            )
            if not getattr(candidate, field_name)
        )
        if missing_fields:
            findings.append(
                _finding(
                    "fallback_candidate_stable_identity_missing",
                    "material candidate inventory requires stable intent, commitment, and source-surface identity",
                    candidate_path_id=candidate.candidate_path_id,
                    metadata={"missing_fields": list(missing_fields)},
                )
            )
    if candidate.candidate_surface not in PPA_CANDIDATE_SURFACES:
        findings.append(
            _finding(
                "fallback_candidate_unknown_surface",
                "fallback candidate uses an unknown surface type",
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if candidate.classification not in PPA_AUTHORITY_ROLES:
        findings.append(
            _finding(
                "fallback_candidate_unknown_classification",
                "fallback candidate uses an unknown authority classification",
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if candidate.disposition not in PPA_DISPOSITIONS or candidate.disposition == PPA_DISPOSITION_UNKNOWN:
        findings.append(
            _finding(
                "fallback_candidate_unknown_disposition",
                "fallback candidate disposition is unknown",
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if (
        candidate.shares_business_intent
        and candidate.auto_invoked()
        and candidate.returns_success_after_primary_failure
    ):
        findings.append(
            _finding(
                "primary_failure_masked_by_fallback_success",
                "primary path failure is masked by automatic alternate success",
                path_id=candidate.fallback_for_path_id,
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if (
        candidate.shares_business_intent
        and (
            candidate.returns_success_after_primary_failure
            or candidate.candidate_behavior == PPA_BEHAVIOR_RETURN_SUCCESS
        )
        and candidate.candidate_behavior != PPA_BEHAVIOR_DELEGATE_TO_PRIMARY
    ):
        findings.append(
            _finding(
                "parallel_same_intent_success_path",
                "same-intent candidate can return independent business success instead of delegating to the primary path",
                path_id=candidate.fallback_for_path_id,
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if (
        candidate.classification == PPA_AUTHORITY_MANUAL_RECOVERY
        or candidate.candidate_surface == PPA_CANDIDATE_MANUAL_RECOVERY
    ) and candidate.auto_invoked():
        findings.append(
            _finding(
                "manual_recovery_auto_invoked",
                "manual recovery surface is automatically invoked",
                path_id=candidate.fallback_for_path_id,
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if (
        candidate.classification == PPA_AUTHORITY_EXTERNAL_FACADE
        or candidate.candidate_surface == PPA_CANDIDATE_COMPATIBILITY_FACADE
    ):
        if candidate.disposition != PPA_DISPOSITION_PRESERVE_FACADE:
            findings.append(
                _finding(
                    "facade_disposition_not_preserve_facade",
                    "external compatibility facade must use preserve_facade disposition",
                    candidate_path_id=candidate.candidate_path_id,
                    metadata=metadata,
                )
            )
        if not candidate.compatibility_intent:
            findings.append(
                _finding(
                    "facade_missing_compatibility_intent",
                    "external compatibility facade must state the external compatibility intent",
                    candidate_path_id=candidate.candidate_path_id,
                    metadata=metadata,
                )
            )
        if candidate.has_business_logic() and candidate.candidate_behavior != PPA_BEHAVIOR_DELEGATE_TO_PRIMARY:
            findings.append(
                _finding(
                    "facade_contains_business_logic",
                    "compatibility facade contains business behavior instead of delegating to the primary path",
                    candidate_path_id=candidate.candidate_path_id,
                    metadata=metadata,
                )
            )
        if material_required and candidate.delegates_to_path_id != candidate.fallback_for_path_id:
            findings.append(
                _finding(
                    "facade_primary_delegation_mismatch",
                    "compatibility facade must name the exact primary path it delegates to",
                    path_id=candidate.fallback_for_path_id,
                    candidate_path_id=candidate.candidate_path_id,
                    metadata=metadata,
                )
            )
    if candidate.candidate_surface in {PPA_CANDIDATE_OLD_FIELD, PPA_CANDIDATE_BACKUP_CACHE} and (
        candidate.candidate_trigger in {PPA_TRIGGER_MISSING_FIELD, PPA_TRIGGER_PRIMARY_FAILURE}
        and candidate.returns_success_after_primary_failure
    ):
        findings.append(
            _finding(
                "old_field_or_backup_cache_masks_primary_failure",
                "old field or backup cache returns success after primary field/path failure",
                path_id=candidate.fallback_for_path_id,
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )
    if candidate.disposition in {PPA_DISPOSITION_PRESERVE_FACADE, PPA_DISPOSITION_MANUAL_ONLY} and not candidate.evidence_refs:
        findings.append(
            _finding(
                "fallback_candidate_evidence_missing",
                "preserved facade or manual-only surface requires current evidence refs",
                candidate_path_id=candidate.candidate_path_id,
                metadata=metadata,
            )
        )


def default_primary_path_authority_axes(
    *,
    model_id: str = PRIMARY_PATH_ROUTE_ID,
) -> tuple[ContractAxis, ...]:
    """Return the finite axes for model-scoped primary-path coverage."""

    return (
        ContractAxis("business_intent", model_id=model_id, values=PPA_DEFAULT_BUSINESS_INTENTS, source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis("primary_result", model_id=model_id, values=PPA_DEFAULT_PRIMARY_RESULTS, source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis("candidate_surface", model_id=model_id, values=tuple(sorted(PPA_CANDIDATE_SURFACES)), source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis("candidate_trigger", model_id=model_id, values=PPA_DEFAULT_CANDIDATE_TRIGGERS, source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis("candidate_behavior", model_id=model_id, values=PPA_DEFAULT_CANDIDATE_BEHAVIORS, source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis("disposition", model_id=model_id, values=tuple(sorted(PPA_DISPOSITIONS)), source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis("evidence_state", model_id=model_id, values=PPA_DEFAULT_EVIDENCE_STATES, source_route=PRIMARY_PATH_ROUTE_ID),
        ContractAxis(
            "business_intent_identity",
            model_id=model_id,
            values=("stable_match", "missing", "mismatch", "duplicate"),
            source_route=PRIMARY_PATH_ROUTE_ID,
        ),
        ContractAxis(
            "primary_path_selection",
            model_id=model_id,
            values=("reuse_current", "wrong_equivalent_path", "explicit_replacement"),
            source_route=PRIMARY_PATH_ROUTE_ID,
        ),
        ContractAxis(
            "candidate_inventory_state",
            model_id=model_id,
            values=("complete", "candidate_omitted", "surface_omitted", "scoped_with_evidence"),
            source_route=PRIMARY_PATH_ROUTE_ID,
        ),
        ContractAxis(
            "runtime_proof_state",
            model_id=model_id,
            values=("current_material", "stale", "missing", "progress_only"),
            source_route=PRIMARY_PATH_ROUTE_ID,
        ),
    )


def default_primary_path_authority_interaction_groups(
    *,
    model_id: str = PRIMARY_PATH_ROUTE_ID,
    max_combinations: int = 10000,
) -> tuple[ContractInteractionGroup, ...]:
    """Return default Cartesian groups for no-fallback coverage."""

    routes = ("primary_path_authority", "model_test_alignment", "test_mesh_maintenance", "risk_evidence_ledger")
    return (
        ContractInteractionGroup(
            "core_no_fallback",
            model_id=model_id,
            axis_ids=("business_intent", "primary_result", "candidate_surface", "candidate_trigger", "candidate_behavior"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "compatibility_disposition",
            model_id=model_id,
            axis_ids=("candidate_surface", "disposition", "evidence_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "field_fallback",
            model_id=model_id,
            axis_ids=("business_intent", "primary_result", "candidate_surface", "candidate_trigger", "disposition"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "facade_boundary",
            model_id=model_id,
            axis_ids=("candidate_surface", "candidate_behavior", "disposition"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "release_evidence",
            model_id=model_id,
            axis_ids=("business_intent", "candidate_surface", "evidence_state", "disposition"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "stable_intent_authority",
            model_id=model_id,
            axis_ids=("business_intent_identity", "primary_path_selection", "candidate_inventory_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "material_runtime_proof",
            model_id=model_id,
            axis_ids=("business_intent_identity", "runtime_proof_state", "evidence_state"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
        ContractInteractionGroup(
            "parallel_success_and_omission",
            model_id=model_id,
            axis_ids=("primary_path_selection", "candidate_inventory_state", "candidate_behavior", "candidate_trigger"),
            required_routes=routes,
            max_combinations=max_combinations,
            oracle_id=PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
        ),
    )


def default_primary_path_authority_coverage_universe(
    *,
    model_id: str = PRIMARY_PATH_ROUTE_ID,
    claim_scope: str = PPA_CLAIM_SCOPE_FULL,
) -> ContractCoverageUniverse:
    """Return the finite coverage universe for primary-path authority."""

    axes = default_primary_path_authority_axes(model_id=model_id)
    groups = default_primary_path_authority_interaction_groups(model_id=model_id)
    return ContractCoverageUniverse(
        f"primary_path_authority:{model_id}",
        claim_scope=claim_scope,
        required_axis_ids=tuple(axis.axis_id for axis in axes),
        required_interaction_group_ids=tuple(group.group_id for group in groups),
        required_coverage_receipt_ids=(f"contract_coverage:{model_id}",),
        require_full_product=True,
        metadata={"owner_route": PRIMARY_PATH_ROUTE_ID},
    )


def primary_path_authority_contract_exhaustion_plan(
    plan_id: str = "primary-path-authority-coverage",
    *,
    model_id: str = PRIMARY_PATH_ROUTE_ID,
    claim_scope: str = PPA_CLAIM_SCOPE_FULL,
    max_combinations: int = 10000,
) -> ContractExhaustionPlan:
    """Build the canonical ContractExhaustionMesh plan for this route."""

    return ContractExhaustionPlan(
        plan_id,
        model_id=model_id,
        axes=default_primary_path_authority_axes(model_id=model_id),
        interaction_groups=default_primary_path_authority_interaction_groups(
            model_id=model_id,
            max_combinations=max_combinations,
        ),
        oracles=(
            ContractOracle(
                PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
                CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
                expected_message_fields=(
                    "business_intent",
                    "primary_path_id",
                    "primary_failure_id",
                    "blocked_fallback_path_id",
                    "repair_action",
                ),
                forbidden_downstream_steps=("fallback_success", "alternate_terminal_success"),
                required_repair_fields=(
                    "primary_entrypoint_id",
                    "owner_model_id",
                    "owner_code_contract_id",
                    "runtime_observation_id",
                ),
                disallowed_side_effects=("fallback_success_state", "silent_terminal_success"),
                description="Primary failure must be exposed and repaired on the primary path, not masked by fallback success.",
            ),
        ),
        claim_scope=claim_scope,
        required_route_ids=("model_test_alignment", "test_mesh_maintenance", "risk_evidence_ledger"),
        require_model_coverage_receipt=True,
        require_coverage_universe=True,
        coverage_universe=default_primary_path_authority_coverage_universe(
            model_id=model_id,
            claim_scope=claim_scope,
        ),
    )


__all__ = [
    "PPA_AUTHORITY_EXTERNAL_FACADE",
    "PPA_AUTHORITY_FALLBACK_CANDIDATE",
    "PPA_AUTHORITY_MANUAL_RECOVERY",
    "PPA_AUTHORITY_MIGRATION_ONLY",
    "PPA_AUTHORITY_PRIMARY",
    "PPA_AUTHORITY_ROLES",
    "PPA_BEHAVIOR_DELEGATE_TO_PRIMARY",
    "PPA_BEHAVIOR_EMIT_SIDE_EFFECT",
    "PPA_BEHAVIOR_MUTATE_TERMINAL",
    "PPA_BEHAVIOR_NO_OP",
    "PPA_BEHAVIOR_READ_STATE",
    "PPA_BEHAVIOR_RETURN_SUCCESS",
    "PPA_BEHAVIOR_WRITE_STATE",
    "PPA_BROAD_CLAIM_SCOPES",
    "PPA_CANDIDATE_ALIAS",
    "PPA_CANDIDATE_BACKUP_CACHE",
    "PPA_CANDIDATE_COMPATIBILITY_FACADE",
    "PPA_CANDIDATE_HELPER_ROUTE",
    "PPA_CANDIDATE_LEGACY_PATH",
    "PPA_CANDIDATE_MANUAL_RECOVERY",
    "PPA_CANDIDATE_MIGRATION_PATH",
    "PPA_CANDIDATE_NONE",
    "PPA_CANDIDATE_OLD_FIELD",
    "PPA_CANDIDATE_SURFACES",
    "PPA_CANDIDATE_UNKNOWN",
    "PPA_CANDIDATE_WRAPPER",
    "PPA_CLAIM_SCOPE_ARCHIVE",
    "PPA_CLAIM_SCOPE_DONE",
    "PPA_CLAIM_SCOPE_FULL",
    "PPA_CLAIM_SCOPE_PRODUCTION",
    "PPA_CLAIM_SCOPE_PUBLISH",
    "PPA_CLAIM_SCOPE_RELEASE",
    "PPA_CLAIM_SCOPE_ROUTINE",
    "PPA_CONFIDENCE_BLOCKED",
    "PPA_CONFIDENCE_FULL",
    "PPA_CONFIDENCE_SCOPED",
    "PPA_CONTRACT_ORACLE_PRIMARY_FAILURE",
    "PPA_DECISION_BLOCKED",
    "PPA_DECISION_GREEN",
    "PPA_DECISION_SCOPED",
    "PPA_DISPOSITION_BLOCK",
    "PPA_DISPOSITION_DELEGATE_TO_PRIMARY",
    "PPA_DISPOSITION_DELETE",
    "PPA_DISPOSITION_MANUAL_ONLY",
    "PPA_DISPOSITION_MIGRATE",
    "PPA_DISPOSITION_PRESERVE_FACADE",
    "PPA_DISPOSITION_SCOPE_OUT",
    "PPA_DISPOSITION_UNKNOWN",
    "PPA_DISPOSITIONS",
    "PPA_FAILURE_POLICIES",
    "PPA_FAILURE_POLICY_EXTERNAL_FACADE_TO_PRIMARY",
    "PPA_FAILURE_POLICY_FAIL_CLOSED",
    "PPA_FAILURE_POLICY_MANUAL_RECOVERY_ONLY",
    "PPA_FAILURE_POLICY_RETRY_SAME_PATH_ONLY",
    "PPA_RISK_GATE_AUTHORITY",
    "PPA_RISK_GATE_CARTESIAN_COVERAGE",
    "PPA_TRIGGER_EXPLICIT_USER_CHOICE",
    "PPA_TRIGGER_MANUAL_OPERATOR_ACTION",
    "PPA_TRIGGER_MISSING_FIELD",
    "PPA_TRIGGER_NEVER",
    "PPA_TRIGGER_PARSE_ERROR",
    "PPA_TRIGGER_PRIMARY_FAILURE",
    "PPA_TRIGGER_TIMEOUT",
    "PPA_TRIGGER_UNKNOWN_ROUTE",
    "PRIMARY_PATH_ROUTE_ID",
    "FallbackPathCandidate",
    "PrimaryPathAuthorityFinding",
    "PrimaryPathAuthorityPlan",
    "PrimaryPathAuthorityReport",
    "PrimaryPathContract",
    "default_primary_path_authority_axes",
    "default_primary_path_authority_coverage_universe",
    "default_primary_path_authority_interaction_groups",
    "primary_path_authority_contract_exhaustion_plan",
    "review_primary_path_authority",
]
