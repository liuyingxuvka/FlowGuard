"""Runtime path evidence helpers for model/code alignment.

Runtime path evidence records the real code route taken through named model
nodes. It is intentionally a helper layer: the executable model still owns the
behavioral contract, while this module checks whether observed code paths can
support model, parent mesh, runtime gateway, or closure claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .proof_artifact import (
    ProofArtifactRef,
    coerce_proof_artifact_ref,
    proof_artifact_gap_codes,
)


RUNTIME_PATH_STATUS_PASSED = "passed"
RUNTIME_PATH_STATUS_FAILED = "failed"
RUNTIME_PATH_STATUS_SKIPPED = "skipped"
RUNTIME_PATH_STATUS_STALE = "stale"
RUNTIME_PATH_STATUS_NOT_RUN = "not_run"
RUNTIME_PATH_STATUS_RUNNING = "running"
RUNTIME_PATH_STATUS_ERROR = "error"

PASSING_RUNTIME_PATH_STATUSES = {RUNTIME_PATH_STATUS_PASSED}
NON_PASSING_RUNTIME_PATH_STATUSES = {
    RUNTIME_PATH_STATUS_FAILED,
    RUNTIME_PATH_STATUS_SKIPPED,
    RUNTIME_PATH_STATUS_STALE,
    RUNTIME_PATH_STATUS_NOT_RUN,
    RUNTIME_PATH_STATUS_RUNNING,
    RUNTIME_PATH_STATUS_ERROR,
}

RUNTIME_PATH_ASSERTION_SCOPE_EXTERNAL_CONTRACT = "external_contract"
RUNTIME_PATH_ASSERTION_SCOPE_INTERNAL_PATH = "internal_path"
RUNTIME_PATH_ASSERTION_SCOPE_MIXED = "mixed"
RUNTIME_PATH_ASSERTION_SCOPE_UNKNOWN = "unknown"

EXTERNAL_RUNTIME_PATH_SCOPES = {
    RUNTIME_PATH_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    RUNTIME_PATH_ASSERTION_SCOPE_MIXED,
}

RUNTIME_PATH_DECISION_GREEN = "runtime_path_alignment_green"
RUNTIME_PATH_DECISION_SCOPED = "runtime_path_alignment_scoped"
RUNTIME_PATH_DECISION_BLOCKED = "runtime_path_alignment_blocked"

RUNTIME_PATH_CONFIDENCE_FULL = "full"
RUNTIME_PATH_CONFIDENCE_SCOPED = "scoped"
RUNTIME_PATH_CONFIDENCE_BLOCKED = "blocked"


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values)


def _metadata(values: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(values or {})


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class RuntimeNodeContract:
    """One modeled node that a real-code path must emit or observe."""

    node_id: str
    model_id: str = ""
    model_path: str = ""
    child_model_id: str = ""
    leaf_model_id: str = ""
    model_obligation_id: str = ""
    code_contract_id: str = ""
    boundary_id: str = ""
    input_case: str = ""
    state_case: str = ""
    business_path_id: str = ""
    business_intent: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    expected_terminal: str = ""
    primary_path_id: str = ""
    surface_id: str = ""
    candidate_id: str = ""
    surface_role: str = "owner"
    delegates_to_primary_path_id: str = ""
    delegation_evidence_id: str = ""
    delegation_evidence_current: bool = False
    delegation_only: bool = False
    require_no_fallback: bool = False
    required: bool = True
    ordered: bool = True
    sequence_index: int | None = None
    allowed_outputs: tuple[str, ...] = ()
    allowed_next_states: tuple[str, ...] = ()
    allowed_state_writes: tuple[str, ...] = ()
    allowed_side_effects: tuple[str, ...] = ()
    allowed_error_paths: tuple[str, ...] = ()
    required_observation_ids: tuple[str, ...] = ()
    exact: bool = True
    requires_gateway_binding: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        node_id = str(self.node_id)
        if not node_id:
            raise ValueError("node_id is required")
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_path", str(self.model_path))
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "leaf_model_id", str(self.leaf_model_id))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "boundary_id", str(self.boundary_id))
        object.__setattr__(self, "input_case", str(self.input_case))
        object.__setattr__(self, "state_case", str(self.state_case))
        object.__setattr__(self, "business_path_id", str(self.business_path_id))
        object.__setattr__(self, "business_intent", str(self.business_intent))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "expected_terminal", str(self.expected_terminal))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "surface_role", str(self.surface_role or "owner"))
        object.__setattr__(self, "delegates_to_primary_path_id", str(self.delegates_to_primary_path_id))
        object.__setattr__(self, "delegation_evidence_id", str(self.delegation_evidence_id))
        object.__setattr__(self, "delegation_evidence_current", bool(self.delegation_evidence_current))
        object.__setattr__(self, "delegation_only", bool(self.delegation_only))
        object.__setattr__(self, "require_no_fallback", bool(self.require_no_fallback))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "ordered", bool(self.ordered))
        if self.sequence_index is not None:
            object.__setattr__(self, "sequence_index", int(self.sequence_index))
        object.__setattr__(self, "allowed_outputs", _as_tuple(self.allowed_outputs))
        object.__setattr__(self, "allowed_next_states", _as_tuple(self.allowed_next_states))
        object.__setattr__(self, "allowed_state_writes", _as_tuple(self.allowed_state_writes))
        object.__setattr__(self, "allowed_side_effects", _as_tuple(self.allowed_side_effects))
        object.__setattr__(self, "allowed_error_paths", _as_tuple(self.allowed_error_paths))
        object.__setattr__(self, "required_observation_ids", _as_tuple(self.required_observation_ids))
        object.__setattr__(self, "exact", bool(self.exact))
        object.__setattr__(self, "requires_gateway_binding", bool(self.requires_gateway_binding))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "model_id": self.model_id,
            "model_path": self.model_path,
            "child_model_id": self.child_model_id,
            "leaf_model_id": self.leaf_model_id,
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "boundary_id": self.boundary_id,
            "input_case": self.input_case,
            "state_case": self.state_case,
            "business_path_id": self.business_path_id,
            "business_intent": self.business_intent,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "expected_terminal": self.expected_terminal,
            "primary_path_id": self.primary_path_id,
            "surface_id": self.surface_id,
            "candidate_id": self.candidate_id,
            "surface_role": self.surface_role,
            "delegates_to_primary_path_id": self.delegates_to_primary_path_id,
            "delegation_evidence_id": self.delegation_evidence_id,
            "delegation_evidence_current": self.delegation_evidence_current,
            "delegation_only": self.delegation_only,
            "require_no_fallback": self.require_no_fallback,
            "required": self.required,
            "ordered": self.ordered,
            "sequence_index": self.sequence_index,
            "allowed_outputs": list(self.allowed_outputs),
            "allowed_next_states": list(self.allowed_next_states),
            "allowed_state_writes": list(self.allowed_state_writes),
            "allowed_side_effects": list(self.allowed_side_effects),
            "allowed_error_paths": list(self.allowed_error_paths),
            "required_observation_ids": list(self.required_observation_ids),
            "exact": self.exact,
            "requires_gateway_binding": self.requires_gateway_binding,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class RuntimeNodeObservation:
    """One emitted or collected runtime observation for a modeled node."""

    observation_id: str
    node_id: str
    run_id: str = ""
    model_id: str = ""
    model_path: str = ""
    child_model_id: str = ""
    leaf_model_id: str = ""
    model_obligation_id: str = ""
    code_contract_id: str = ""
    boundary_id: str = ""
    input_case: str = ""
    state_case: str = ""
    business_path_id: str = ""
    business_intent: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    surface_id: str = ""
    candidate_id: str = ""
    surface_role: str = "owner"
    delegates_to_primary_path_id: str = ""
    delegation_evidence_id: str = ""
    delegation_evidence_current: bool = False
    delegation_observed: bool = False
    independent_business_success: bool = False
    fallback_path_id: str = ""
    primary_failure_id: str = ""
    fallback_invoked: bool = False
    fallback_returned_success: bool = False
    sequence_index: int | None = None
    accepted: bool = True
    observed_output: str = ""
    observed_next_state: str = ""
    observed_terminal: str = ""
    observed_state_writes: tuple[str, ...] = ()
    observed_side_effects: tuple[str, ...] = ()
    observed_error_path: str = ""
    gateway_id: str = ""
    result_status: str = RUNTIME_PATH_STATUS_PASSED
    evidence_current: bool = True
    evidence_id: str = ""
    assertion_scope: str = RUNTIME_PATH_ASSERTION_SCOPE_EXTERNAL_CONTRACT
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    progress_message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        observation_id = str(self.observation_id)
        if not observation_id:
            raise ValueError("observation_id is required")
        node_id = str(self.node_id)
        if not node_id:
            raise ValueError("node_id is required")
        object.__setattr__(self, "observation_id", observation_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "run_id", str(self.run_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_path", str(self.model_path))
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "leaf_model_id", str(self.leaf_model_id))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "boundary_id", str(self.boundary_id))
        object.__setattr__(self, "input_case", str(self.input_case))
        object.__setattr__(self, "state_case", str(self.state_case))
        object.__setattr__(self, "business_path_id", str(self.business_path_id))
        object.__setattr__(self, "business_intent", str(self.business_intent))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "surface_role", str(self.surface_role or "owner"))
        object.__setattr__(self, "delegates_to_primary_path_id", str(self.delegates_to_primary_path_id))
        object.__setattr__(self, "delegation_evidence_id", str(self.delegation_evidence_id))
        object.__setattr__(self, "delegation_evidence_current", bool(self.delegation_evidence_current))
        object.__setattr__(self, "delegation_observed", bool(self.delegation_observed))
        object.__setattr__(self, "independent_business_success", bool(self.independent_business_success))
        object.__setattr__(self, "fallback_path_id", str(self.fallback_path_id))
        object.__setattr__(self, "primary_failure_id", str(self.primary_failure_id))
        object.__setattr__(self, "fallback_invoked", bool(self.fallback_invoked))
        object.__setattr__(self, "fallback_returned_success", bool(self.fallback_returned_success))
        if self.sequence_index is not None:
            object.__setattr__(self, "sequence_index", int(self.sequence_index))
        object.__setattr__(self, "accepted", bool(self.accepted))
        object.__setattr__(self, "observed_output", str(self.observed_output))
        object.__setattr__(self, "observed_next_state", str(self.observed_next_state))
        object.__setattr__(self, "observed_terminal", str(self.observed_terminal))
        object.__setattr__(self, "observed_state_writes", _as_tuple(self.observed_state_writes))
        object.__setattr__(self, "observed_side_effects", _as_tuple(self.observed_side_effects))
        object.__setattr__(self, "observed_error_path", str(self.observed_error_path))
        object.__setattr__(self, "gateway_id", str(self.gateway_id))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "evidence_current", bool(self.evidence_current))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "progress_message", str(self.progress_message))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def has_current_pass(self) -> bool:
        return self.result_status in PASSING_RUNTIME_PATH_STATUSES and self.evidence_current

    def has_external_scope(self) -> bool:
        return self.assertion_scope in EXTERNAL_RUNTIME_PATH_SCOPES

    def evidence_key(self) -> str:
        return self.evidence_id or self.observation_id

    def format_progress_line(self) -> str:
        """Return one parseable progress line that names the compared model."""

        parts = [
            "flowguard.runtime_path",
            f"model={self.model_id or '(unknown)'}",
            f"node={self.node_id}",
            f"run={self.run_id or '(none)'}",
            f"status={self.result_status}",
        ]
        optional = (
            ("model_path", self.model_path),
            ("child_model", self.child_model_id),
            ("leaf_model", self.leaf_model_id),
            ("obligation", self.model_obligation_id),
            ("code_contract", self.code_contract_id),
            ("boundary", self.boundary_id),
            ("input_case", self.input_case),
            ("state_case", self.state_case),
            ("business_path", self.business_path_id),
            ("business_intent", self.business_intent),
            ("business_intent_id", self.business_intent_id),
            ("behavior_commitment_id", self.behavior_commitment_id),
            ("primary_path", self.primary_path_id),
            ("surface", self.surface_id),
            ("candidate", self.candidate_id),
            ("fallback_path", self.fallback_path_id),
            ("primary_failure", self.primary_failure_id),
            ("evidence", self.evidence_key()),
            ("progress", self.progress_message),
        )
        for key, value in optional:
            if value:
                parts.append(f"{key}={value}")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "node_id": self.node_id,
            "run_id": self.run_id,
            "model_id": self.model_id,
            "model_path": self.model_path,
            "child_model_id": self.child_model_id,
            "leaf_model_id": self.leaf_model_id,
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "boundary_id": self.boundary_id,
            "input_case": self.input_case,
            "state_case": self.state_case,
            "business_path_id": self.business_path_id,
            "business_intent": self.business_intent,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "surface_id": self.surface_id,
            "candidate_id": self.candidate_id,
            "surface_role": self.surface_role,
            "delegates_to_primary_path_id": self.delegates_to_primary_path_id,
            "delegation_evidence_id": self.delegation_evidence_id,
            "delegation_evidence_current": self.delegation_evidence_current,
            "delegation_observed": self.delegation_observed,
            "independent_business_success": self.independent_business_success,
            "fallback_path_id": self.fallback_path_id,
            "primary_failure_id": self.primary_failure_id,
            "fallback_invoked": self.fallback_invoked,
            "fallback_returned_success": self.fallback_returned_success,
            "sequence_index": self.sequence_index,
            "accepted": self.accepted,
            "observed_output": self.observed_output,
            "observed_next_state": self.observed_next_state,
            "observed_terminal": self.observed_terminal,
            "observed_state_writes": list(self.observed_state_writes),
            "observed_side_effects": list(self.observed_side_effects),
            "observed_error_path": self.observed_error_path,
            "gateway_id": self.gateway_id,
            "result_status": self.result_status,
            "evidence_current": self.evidence_current,
            "evidence_id": self.evidence_id,
            "assertion_scope": self.assertion_scope,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "progress_message": self.progress_message,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class RuntimePathRun:
    """One concrete run containing ordered runtime node observations."""

    run_id: str
    observations: tuple[RuntimeNodeObservation, ...] = ()
    source_evidence_id: str = ""
    result_status: str = RUNTIME_PATH_STATUS_PASSED
    current: bool = True
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    inventory_revision: str = ""
    covered_surface_ids: tuple[str, ...] = ()
    covered_candidate_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        run_id = str(self.run_id)
        if not run_id:
            raise ValueError("run_id is required")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(
            self,
            "observations",
            tuple(
                item
                if isinstance(item, RuntimeNodeObservation)
                else RuntimeNodeObservation(**item)
                for item in self.observations
            ),
        )
        object.__setattr__(self, "source_evidence_id", str(self.source_evidence_id))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "covered_surface_ids", _as_tuple(self.covered_surface_ids))
        object.__setattr__(self, "covered_candidate_ids", _as_tuple(self.covered_candidate_ids))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "observations": [observation.to_dict() for observation in self.observations],
            "source_evidence_id": self.source_evidence_id,
            "result_status": self.result_status,
            "current": self.current,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "inventory_revision": self.inventory_revision,
            "covered_surface_ids": list(self.covered_surface_ids),
            "covered_candidate_ids": list(self.covered_candidate_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }

    def format_progress_lines(self) -> str:
        return "\n".join(observation.format_progress_line() for observation in self.observations)


@dataclass(frozen=True)
class RuntimePathAlignmentPlan:
    """Plan for checking modeled runtime nodes against real-code observations."""

    plan_id: str
    model_id: str = ""
    node_contracts: tuple[RuntimeNodeContract, ...] = ()
    observations: tuple[RuntimeNodeObservation, ...] = ()
    runs: tuple[RuntimePathRun, ...] = ()
    require_exact_path: bool = False
    require_proof_artifacts: bool = False
    allow_uncontracted_nodes: bool = False
    claim_scope: str = RUNTIME_PATH_CONFIDENCE_FULL
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    inventory_revision: str = ""
    expected_surface_ids: tuple[str, ...] = ()
    expected_candidate_ids: tuple[str, ...] = ()
    scoped_surface_reasons: Mapping[str, str] = field(default_factory=dict)
    scoped_candidate_reasons: Mapping[str, str] = field(default_factory=dict)
    require_complete_inventory: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        plan_id = str(self.plan_id)
        if not plan_id:
            raise ValueError("plan_id is required")
        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(
            self,
            "node_contracts",
            tuple(
                item
                if isinstance(item, RuntimeNodeContract)
                else RuntimeNodeContract(**item)
                for item in self.node_contracts
            ),
        )
        object.__setattr__(
            self,
            "observations",
            tuple(
                item
                if isinstance(item, RuntimeNodeObservation)
                else RuntimeNodeObservation(**item)
                for item in self.observations
            ),
        )
        object.__setattr__(
            self,
            "runs",
            tuple(item if isinstance(item, RuntimePathRun) else RuntimePathRun(**item) for item in self.runs),
        )
        object.__setattr__(self, "require_exact_path", bool(self.require_exact_path))
        object.__setattr__(self, "require_proof_artifacts", bool(self.require_proof_artifacts))
        object.__setattr__(self, "allow_uncontracted_nodes", bool(self.allow_uncontracted_nodes))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "expected_surface_ids", _as_tuple(self.expected_surface_ids))
        object.__setattr__(self, "expected_candidate_ids", _as_tuple(self.expected_candidate_ids))
        object.__setattr__(
            self,
            "scoped_surface_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_surface_reasons).items()},
        )
        object.__setattr__(
            self,
            "scoped_candidate_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_candidate_reasons).items()},
        )
        object.__setattr__(self, "require_complete_inventory", bool(self.require_complete_inventory))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def all_observations(self) -> tuple[RuntimeNodeObservation, ...]:
        run_observations: list[RuntimeNodeObservation] = []
        for run in self.runs:
            run_observations.extend(run.observations)
        return tuple(self.observations) + tuple(run_observations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "model_id": self.model_id,
            "node_contracts": [contract.to_dict() for contract in self.node_contracts],
            "observations": [observation.to_dict() for observation in self.observations],
            "runs": [run.to_dict() for run in self.runs],
            "require_exact_path": self.require_exact_path,
            "require_proof_artifacts": self.require_proof_artifacts,
            "allow_uncontracted_nodes": self.allow_uncontracted_nodes,
            "claim_scope": self.claim_scope,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "inventory_revision": self.inventory_revision,
            "expected_surface_ids": list(self.expected_surface_ids),
            "expected_candidate_ids": list(self.expected_candidate_ids),
            "scoped_surface_reasons": to_jsonable(dict(self.scoped_surface_reasons)),
            "scoped_candidate_reasons": to_jsonable(dict(self.scoped_candidate_reasons)),
            "require_complete_inventory": self.require_complete_inventory,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class RuntimePathFinding:
    """One runtime path evidence gap."""

    code: str
    message: str
    severity: str = "blocker"
    node_id: str = ""
    observation_id: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "node_id", str(self.node_id))
        object.__setattr__(self, "observation_id", str(self.observation_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "node_id": self.node_id,
            "observation_id": self.observation_id,
            "evidence_id": self.evidence_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class RuntimePathAlignmentReport:
    """Structured outcome of runtime path evidence review."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    findings: tuple[RuntimePathFinding, ...] = ()
    checked_contracts: int = 0
    checked_observations: int = 0
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    inventory_revision: str = ""
    covered_surface_ids: tuple[str, ...] = ()
    scoped_surface_ids: tuple[str, ...] = ()
    missing_surface_ids: tuple[str, ...] = ()
    covered_candidate_ids: tuple[str, ...] = ()
    scoped_candidate_ids: tuple[str, ...] = ()
    missing_candidate_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "covered_surface_ids", _as_tuple(self.covered_surface_ids))
        object.__setattr__(self, "scoped_surface_ids", _as_tuple(self.scoped_surface_ids))
        object.__setattr__(self, "missing_surface_ids", _as_tuple(self.missing_surface_ids))
        object.__setattr__(self, "covered_candidate_ids", _as_tuple(self.covered_candidate_ids))
        object.__setattr__(self, "scoped_candidate_ids", _as_tuple(self.scoped_candidate_ids))
        object.__setattr__(self, "missing_candidate_ids", _as_tuple(self.missing_candidate_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                (
                    f"{status}: runtime_path_alignment plan={self.plan_id} "
                    f"contracts={self.checked_contracts} "
                    f"observations={self.checked_observations} "
                    f"findings={len(self.findings)}"
                ),
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard runtime path alignment ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"contracts: {self.checked_contracts}",
            f"observations: {self.checked_observations}",
            f"business_intent_id: {self.business_intent_id or '(missing)'}",
            f"behavior_commitment_id: {self.behavior_commitment_id or '(missing)'}",
            f"primary_path_id: {self.primary_path_id or '(missing)'}",
            f"covered_surfaces: {', '.join(self.covered_surface_ids) or '(none)'}",
            f"covered_candidates: {', '.join(self.covered_candidate_ids) or '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"node: {finding.node_id or '(none)'}",
                    f"observation: {finding.observation_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
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
            "checked_contracts": self.checked_contracts,
            "checked_observations": self.checked_observations,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "inventory_revision": self.inventory_revision,
            "covered_surface_ids": list(self.covered_surface_ids),
            "scoped_surface_ids": list(self.scoped_surface_ids),
            "missing_surface_ids": list(self.missing_surface_ids),
            "covered_candidate_ids": list(self.covered_candidate_ids),
            "scoped_candidate_ids": list(self.scoped_candidate_ids),
            "missing_candidate_ids": list(self.missing_candidate_ids),
            "summary": self.summary,
        }


class RuntimePathRecorder:
    """Small recorder for tests or harnesses that emit runtime path observations."""

    def __init__(self, run_id: str, *, metadata: Mapping[str, Any] | None = None) -> None:
        run_id = str(run_id)
        if not run_id:
            raise ValueError("run_id is required")
        self.run_id = run_id
        self.metadata = _metadata(metadata)
        self._observations: list[RuntimeNodeObservation] = []

    @property
    def observations(self) -> tuple[RuntimeNodeObservation, ...]:
        return tuple(self._observations)

    def record(self, node_id: str, **kwargs: Any) -> RuntimeNodeObservation:
        sequence_index = len(self._observations)
        observation_id = str(kwargs.pop("observation_id", "") or f"{self.run_id}:{sequence_index}:{node_id}")
        run_id = str(kwargs.pop("run_id", "") or self.run_id)
        if "sequence_index" not in kwargs:
            kwargs["sequence_index"] = sequence_index
        observation = RuntimeNodeObservation(
            observation_id=observation_id,
            node_id=node_id,
            run_id=run_id,
            **kwargs,
        )
        self._observations.append(observation)
        return observation

    def to_run(self, **kwargs: Any) -> RuntimePathRun:
        return RuntimePathRun(
            run_id=self.run_id,
            observations=tuple(self._observations),
            metadata=self.metadata,
            **kwargs,
        )

    def format_progress_lines(self) -> str:
        return "\n".join(observation.format_progress_line() for observation in self._observations)


def _runtime_authority_values(
    plan: RuntimePathAlignmentPlan,
) -> tuple[str, str, str]:
    values: list[str] = []
    for attr in ("business_intent_id", "behavior_commitment_id", "primary_path_id"):
        plan_value = str(getattr(plan, attr))
        contract_values = _unique(
            tuple(
                str(getattr(contract, attr))
                for contract in plan.node_contracts
                if contract.required and str(getattr(contract, attr))
            )
        )
        values.append(plan_value or (contract_values[0] if len(contract_values) == 1 else ""))
    return tuple(values)  # type: ignore[return-value]


def _review_runtime_authority(
    plan: RuntimePathAlignmentPlan,
    observations: tuple[RuntimeNodeObservation, ...],
    findings: list[RuntimePathFinding],
) -> tuple[str, str, str]:
    expected_values = _runtime_authority_values(plan)
    attrs = ("business_intent_id", "behavior_commitment_id", "primary_path_id")
    broad_claim = plan.claim_scope == RUNTIME_PATH_CONFIDENCE_FULL
    for attr, expected in zip(attrs, expected_values):
        if broad_claim and not expected:
            findings.append(
                RuntimePathFinding(
                    f"runtime_path_{attr}_missing",
                    f"broad runtime path confidence requires stable {attr}",
                    metadata={"plan_id": plan.plan_id, "claim_scope": plan.claim_scope},
                )
            )
            continue
        if not expected:
            continue
        plan_value = str(getattr(plan, attr))
        if plan_value and plan_value != expected:
            findings.append(
                RuntimePathFinding(
                    f"runtime_path_{attr}_mismatch",
                    f"runtime path plan {attr} does not match the selected authority",
                    metadata={"expected": expected, "actual": plan_value},
                )
            )
        for contract in plan.node_contracts:
            if not contract.required:
                continue
            actual = str(getattr(contract, attr))
            if not actual:
                findings.append(
                    RuntimePathFinding(
                        f"runtime_node_{attr}_missing",
                        f"required runtime node {contract.node_id!r} omits stable {attr}",
                        node_id=contract.node_id,
                        metadata={"expected": expected, "contract": contract.to_dict()},
                    )
                )
            elif actual != expected:
                findings.append(
                    RuntimePathFinding(
                        f"runtime_node_{attr}_mismatch",
                        f"required runtime node {contract.node_id!r} uses a different {attr}",
                        node_id=contract.node_id,
                        metadata={"expected": expected, "actual": actual},
                    )
                )
        for observation in observations:
            actual = str(getattr(observation, attr))
            if not actual:
                findings.append(
                    RuntimePathFinding(
                        f"runtime_observation_{attr}_missing",
                        f"runtime observation {observation.observation_id!r} omits stable {attr}",
                        node_id=observation.node_id,
                        observation_id=observation.observation_id,
                        evidence_id=observation.evidence_key(),
                        metadata={"expected": expected},
                    )
                )
            elif actual != expected:
                findings.append(
                    RuntimePathFinding(
                        f"runtime_observation_{attr}_mismatch",
                        f"runtime observation {observation.observation_id!r} uses a different {attr}",
                        node_id=observation.node_id,
                        observation_id=observation.observation_id,
                        evidence_id=observation.evidence_key(),
                        metadata={"expected": expected, "actual": actual},
                    )
                )
        for run in plan.runs:
            actual = str(getattr(run, attr))
            if not actual:
                findings.append(
                    RuntimePathFinding(
                        f"runtime_run_{attr}_missing",
                        f"runtime path run {run.run_id!r} omits stable {attr}",
                        evidence_id=run.source_evidence_id or run.run_id,
                        metadata={"expected": expected, "run": run.to_dict()},
                    )
                )
            elif actual != expected:
                findings.append(
                    RuntimePathFinding(
                        f"runtime_run_{attr}_mismatch",
                        f"runtime path run {run.run_id!r} uses a different {attr}",
                        evidence_id=run.source_evidence_id or run.run_id,
                        metadata={"expected": expected, "actual": actual},
                    )
                )
    for run in plan.runs:
        if not run.current or run.result_status not in PASSING_RUNTIME_PATH_STATUSES:
            findings.append(
                RuntimePathFinding(
                    "runtime_path_run_not_current_pass",
                    f"runtime path run {run.run_id!r} is not current passing evidence",
                    evidence_id=run.source_evidence_id or run.run_id,
                    metadata=run.to_dict(),
                )
            )
        if plan.inventory_revision and run.inventory_revision != plan.inventory_revision:
            findings.append(
                RuntimePathFinding(
                    "runtime_path_inventory_revision_mismatch",
                    f"runtime path run {run.run_id!r} does not match inventory revision",
                    evidence_id=run.source_evidence_id or run.run_id,
                    metadata={"expected": plan.inventory_revision, "actual": run.inventory_revision},
                )
            )
    return expected_values


def _review_runtime_inventory(
    plan: RuntimePathAlignmentPlan,
    observations: tuple[RuntimeNodeObservation, ...],
    findings: list[RuntimePathFinding],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    expected_surfaces = _unique(plan.expected_surface_ids)
    expected_candidates = _unique(plan.expected_candidate_ids)
    scoped_surfaces = set(plan.scoped_surface_reasons)
    scoped_candidates = set(plan.scoped_candidate_reasons)
    inventory_claimed = bool(plan.require_complete_inventory or expected_surfaces or expected_candidates)
    if inventory_claimed and not plan.inventory_revision:
        findings.append(
            RuntimePathFinding(
                "runtime_path_inventory_revision_missing",
                "runtime surface/candidate inventory requires an explicit revision",
                metadata={"plan_id": plan.plan_id},
            )
        )
    if plan.require_complete_inventory and not (expected_surfaces or expected_candidates):
        findings.append(
            RuntimePathFinding(
                "missing_expected_runtime_inventory",
                "complete runtime inventory was requested without expected surface or candidate ids",
                metadata={"plan_id": plan.plan_id},
            )
        )
    for item_id, reason in (*plan.scoped_surface_reasons.items(), *plan.scoped_candidate_reasons.items()):
        if not reason:
            findings.append(
                RuntimePathFinding(
                    "runtime_inventory_scoped_reason_missing",
                    "runtime inventory disposition requires a reason",
                    metadata={"item_id": item_id},
                )
            )

    contracts_by_surface = {
        contract.surface_id: contract
        for contract in plan.node_contracts
        if contract.surface_id
    }
    contracts_by_candidate = {
        contract.candidate_id: contract
        for contract in plan.node_contracts
        if contract.candidate_id
    }
    passing = tuple(
        observation
        for observation in observations
        if observation.has_current_pass() and observation.has_external_scope()
    )
    observed_surfaces = {observation.surface_id for observation in passing if observation.surface_id}
    observed_candidates = {observation.candidate_id for observation in passing if observation.candidate_id}
    covered_surfaces: list[str] = []
    missing_surfaces: list[str] = []
    for surface_id in expected_surfaces:
        if surface_id in scoped_surfaces:
            continue
        if surface_id not in contracts_by_surface:
            missing_surfaces.append(surface_id)
            findings.append(
                RuntimePathFinding(
                    "expected_runtime_surface_contract_missing",
                    f"expected runtime surface {surface_id!r} has no runtime node contract",
                    metadata={"surface_id": surface_id, "inventory_revision": plan.inventory_revision},
                )
            )
        elif surface_id not in observed_surfaces:
            missing_surfaces.append(surface_id)
            findings.append(
                RuntimePathFinding(
                    "expected_runtime_surface_observation_missing",
                    f"expected runtime surface {surface_id!r} has no current passing observation",
                    metadata={"surface_id": surface_id, "inventory_revision": plan.inventory_revision},
                )
            )
        else:
            covered_surfaces.append(surface_id)
    covered_candidates: list[str] = []
    missing_candidates: list[str] = []
    for candidate_id in expected_candidates:
        if candidate_id in scoped_candidates:
            continue
        if candidate_id not in contracts_by_candidate or candidate_id not in observed_candidates:
            missing_candidates.append(candidate_id)
            findings.append(
                RuntimePathFinding(
                    "expected_runtime_candidate_unaccounted",
                    f"expected runtime candidate {candidate_id!r} lacks current contract/observation evidence",
                    metadata={"candidate_id": candidate_id, "inventory_revision": plan.inventory_revision},
                )
            )
        else:
            covered_candidates.append(candidate_id)
    if plan.require_complete_inventory:
        for surface_id in sorted(set(contracts_by_surface) - set(expected_surfaces) - scoped_surfaces):
            findings.append(
                RuntimePathFinding(
                    "unexpected_runtime_surface",
                    f"runtime surface {surface_id!r} is outside the complete expected inventory",
                    metadata={"surface_id": surface_id},
                )
            )
        for candidate_id in sorted(set(contracts_by_candidate) - set(expected_candidates) - scoped_candidates):
            findings.append(
                RuntimePathFinding(
                    "unexpected_runtime_candidate",
                    f"runtime candidate {candidate_id!r} is outside the complete expected inventory",
                    metadata={"candidate_id": candidate_id},
                )
            )
    return (
        _unique(covered_surfaces),
        _unique(tuple(sorted(scoped_surfaces & set(expected_surfaces)))),
        _unique(missing_surfaces),
        _unique(covered_candidates),
        _unique(tuple(sorted(scoped_candidates & set(expected_candidates)))),
        _unique(missing_candidates),
    )


def review_runtime_path_alignment(
    plan: RuntimePathAlignmentPlan | Mapping[str, Any],
) -> RuntimePathAlignmentReport:
    """Review whether real-code observations satisfy runtime node contracts."""

    plan = plan if isinstance(plan, RuntimePathAlignmentPlan) else RuntimePathAlignmentPlan(**plan)
    observations = plan.all_observations()
    contracts_by_node: dict[str, list[RuntimeNodeContract]] = {}
    for contract in plan.node_contracts:
        contracts_by_node.setdefault(contract.node_id, []).append(contract)

    findings: list[RuntimePathFinding] = []
    for node_id, contracts in sorted(contracts_by_node.items()):
        if len(contracts) > 1:
            findings.append(
                RuntimePathFinding(
                    "duplicate_runtime_node_contract",
                    f"runtime node {node_id!r} has multiple contracts",
                    node_id=node_id,
                    metadata={"contracts": [contract.to_dict() for contract in contracts]},
                )
            )

    observations_by_node: dict[str, list[RuntimeNodeObservation]] = {}
    for observation in observations:
        observations_by_node.setdefault(observation.node_id, []).append(observation)
        if observation.node_id not in contracts_by_node and not plan.allow_uncontracted_nodes:
            findings.append(
                RuntimePathFinding(
                    "uncontracted_runtime_node_observed",
                    f"runtime observation {observation.observation_id!r} emitted undeclared node {observation.node_id!r}",
                    node_id=observation.node_id,
                    observation_id=observation.observation_id,
                    evidence_id=observation.evidence_key(),
                    metadata=observation.to_dict(),
                )
            )
        _review_observation_status(observation, findings)

    for contract in plan.node_contracts:
        node_observations = tuple(observations_by_node.get(contract.node_id, ()))
        _review_contract_observations(contract, node_observations, findings, plan=plan)

    if plan.require_exact_path:
        _review_exact_path(plan.node_contracts, observations, findings)

    authority_values = _review_runtime_authority(plan, observations, findings)
    inventory_values = _review_runtime_inventory(plan, observations, findings)

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if blockers:
        decision = RUNTIME_PATH_DECISION_BLOCKED
        confidence = RUNTIME_PATH_CONFIDENCE_BLOCKED
    elif any(finding.severity == "warning" for finding in findings) or plan.claim_scope != RUNTIME_PATH_CONFIDENCE_FULL:
        decision = RUNTIME_PATH_DECISION_SCOPED
        confidence = RUNTIME_PATH_CONFIDENCE_SCOPED
    else:
        decision = RUNTIME_PATH_DECISION_GREEN
        confidence = RUNTIME_PATH_CONFIDENCE_FULL

    return RuntimePathAlignmentReport(
        ok=not blockers,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        checked_contracts=len(plan.node_contracts),
        checked_observations=len(observations),
        business_intent_id=authority_values[0],
        behavior_commitment_id=authority_values[1],
        primary_path_id=authority_values[2],
        inventory_revision=plan.inventory_revision,
        covered_surface_ids=inventory_values[0],
        scoped_surface_ids=inventory_values[1],
        missing_surface_ids=inventory_values[2],
        covered_candidate_ids=inventory_values[3],
        scoped_candidate_ids=inventory_values[4],
        missing_candidate_ids=inventory_values[5],
    )


def _review_observation_status(
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    if observation.fallback_invoked and observation.fallback_returned_success:
        findings.append(
            RuntimePathFinding(
                "runtime_path_silent_fallback",
                "runtime observation shows fallback invocation returning success after primary failure",
                node_id=observation.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=observation.to_dict(),
            )
        )
    if not observation.has_current_pass():
        findings.append(
            RuntimePathFinding(
                "runtime_node_observation_not_current_pass",
                f"runtime observation {observation.observation_id!r} is not current passing evidence",
                node_id=observation.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=observation.to_dict(),
            )
        )
    if not observation.has_external_scope():
        findings.append(
            RuntimePathFinding(
                "runtime_node_internal_path_only",
                f"runtime observation {observation.observation_id!r} does not exercise the external contract",
                node_id=observation.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=observation.to_dict(),
            )
        )


def _review_contract_observations(
    contract: RuntimeNodeContract,
    observations: tuple[RuntimeNodeObservation, ...],
    findings: list[RuntimePathFinding],
    *,
    plan: RuntimePathAlignmentPlan,
) -> None:
    passing = tuple(
        observation
        for observation in observations
        if observation.has_current_pass() and observation.has_external_scope()
    )
    if contract.required and not passing:
        findings.append(
            RuntimePathFinding(
                "runtime_node_missing_observation",
                f"runtime node {contract.node_id!r} has no current passing external observation",
                node_id=contract.node_id,
                metadata=contract.to_dict(),
            )
        )
        return

    if contract.required_observation_ids:
        present = {observation.observation_id for observation in passing}
        missing = tuple(value for value in contract.required_observation_ids if value not in present)
        if missing:
            findings.append(
                RuntimePathFinding(
                    "missing_required_runtime_observation_id",
                    f"runtime node {contract.node_id!r} is missing required observation ids",
                    node_id=contract.node_id,
                    metadata={"missing": list(missing), "contract": contract.to_dict()},
                )
            )

    for observation in passing:
        _review_binding(contract, observation, findings)
        _review_behavior(contract, observation, findings)
        _review_facade_delegation(contract, observation, findings)
        if contract.require_no_fallback and observation.fallback_invoked:
            findings.append(
                RuntimePathFinding(
                    "runtime_path_fallback_invoked",
                    f"runtime node {contract.node_id!r} invoked a fallback path despite no-fallback contract",
                    node_id=contract.node_id,
                    observation_id=observation.observation_id,
                    evidence_id=observation.evidence_key(),
                    metadata={"contract": contract.to_dict(), "observation": observation.to_dict()},
                )
            )
        if contract.requires_gateway_binding and not observation.gateway_id:
            findings.append(
                RuntimePathFinding(
                    "missing_runtime_gateway_binding",
                    f"runtime node {contract.node_id!r} requires a runtime gateway binding",
                    node_id=contract.node_id,
                    observation_id=observation.observation_id,
                    evidence_id=observation.evidence_key(),
                    metadata={"contract": contract.to_dict(), "observation": observation.to_dict()},
                )
            )
        if plan.require_proof_artifacts:
            _review_proof_artifact(contract, observation, findings)


def _review_binding(
    contract: RuntimeNodeContract,
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    checks = (
        ("model_id", "runtime_node_model_mismatch"),
        ("child_model_id", "runtime_node_child_model_mismatch"),
        ("leaf_model_id", "runtime_node_leaf_model_mismatch"),
        ("model_obligation_id", "runtime_node_obligation_mismatch"),
        ("code_contract_id", "runtime_node_code_contract_mismatch"),
        ("boundary_id", "runtime_node_boundary_mismatch"),
        ("input_case", "runtime_node_input_case_mismatch"),
        ("state_case", "runtime_node_state_case_mismatch"),
        ("surface_id", "runtime_node_surface_mismatch"),
        ("candidate_id", "runtime_node_candidate_mismatch"),
    )
    for attr, code in checks:
        expected = getattr(contract, attr)
        actual = getattr(observation, attr)
        if expected and actual and expected != actual:
            findings.append(
                RuntimePathFinding(
                    code,
                    f"runtime node {contract.node_id!r} {attr} does not match",
                    node_id=contract.node_id,
                    observation_id=observation.observation_id,
                    evidence_id=observation.evidence_key(),
                    metadata={"expected": expected, "actual": actual},
                )
            )
    business_checks = (
        (
            "business_path_id",
            "runtime_node_business_path_mismatch",
            "runtime_node_business_path_missing",
        ),
        (
            "business_intent",
            "runtime_node_business_intent_mismatch",
            "runtime_node_business_intent_missing",
        ),
        (
            "primary_path_id",
            "runtime_node_primary_path_mismatch",
            "runtime_node_primary_path_missing",
        ),
        (
            "business_intent_id",
            "runtime_node_business_intent_id_mismatch",
            "runtime_node_business_intent_id_missing",
        ),
        (
            "behavior_commitment_id",
            "runtime_node_behavior_commitment_id_mismatch",
            "runtime_node_behavior_commitment_id_missing",
        ),
    )
    for attr, mismatch_code, missing_code in business_checks:
        expected = getattr(contract, attr)
        actual = getattr(observation, attr)
        if expected and not actual:
            findings.append(
                RuntimePathFinding(
                    missing_code,
                    f"runtime node {contract.node_id!r} does not bind required {attr}",
                    node_id=contract.node_id,
                    observation_id=observation.observation_id,
                    evidence_id=observation.evidence_key(),
                    metadata={"expected": expected},
                )
            )
        elif expected and actual and expected != actual:
            findings.append(
                RuntimePathFinding(
                    mismatch_code,
                    f"runtime node {contract.node_id!r} {attr} does not match",
                    node_id=contract.node_id,
                    observation_id=observation.observation_id,
                    evidence_id=observation.evidence_key(),
                    metadata={"expected": expected, "actual": actual},
                )
            )


def _review_facade_delegation(
    contract: RuntimeNodeContract,
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    if contract.surface_role == "owner":
        return
    metadata = {"contract": contract.to_dict(), "observation": observation.to_dict()}
    if not contract.delegation_only:
        findings.append(
            RuntimePathFinding(
                "runtime_facade_not_delegation_only",
                f"runtime facade {contract.node_id!r} is not declared as delegation-only",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=metadata,
            )
        )
    if (
        not contract.delegates_to_primary_path_id
        or contract.delegates_to_primary_path_id != contract.primary_path_id
    ):
        findings.append(
            RuntimePathFinding(
                "runtime_facade_primary_path_delegation_mismatch",
                f"runtime facade {contract.node_id!r} does not delegate to the selected primary path",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=metadata,
            )
        )
    if not contract.delegation_evidence_id or not contract.delegation_evidence_current:
        findings.append(
            RuntimePathFinding(
                "runtime_facade_delegation_evidence_stale",
                f"runtime facade {contract.node_id!r} lacks current delegation contract evidence",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=metadata,
            )
        )
    if (
        not observation.delegation_observed
        or observation.delegates_to_primary_path_id != contract.primary_path_id
    ):
        findings.append(
            RuntimePathFinding(
                "runtime_facade_delegation_not_observed",
                f"runtime facade {contract.node_id!r} did not reach the selected primary path",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=metadata,
            )
        )
    if not observation.delegation_evidence_id or not observation.delegation_evidence_current:
        findings.append(
            RuntimePathFinding(
                "runtime_facade_observation_stale",
                f"runtime facade {contract.node_id!r} lacks current delegation observation evidence",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=metadata,
            )
        )
    if observation.independent_business_success or observation.fallback_returned_success:
        findings.append(
            RuntimePathFinding(
                "runtime_facade_alternate_success",
                f"runtime facade {contract.node_id!r} returned independent business success",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata=metadata,
            )
        )
def _review_behavior(
    contract: RuntimeNodeContract,
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    if not contract.exact:
        return
    if contract.allowed_outputs and observation.observed_output and observation.observed_output not in contract.allowed_outputs:
        _behavior_finding("runtime_node_output_mismatch", "output", contract, observation, findings)
    if (
        contract.allowed_next_states
        and observation.observed_next_state
        and observation.observed_next_state not in contract.allowed_next_states
    ):
        _behavior_finding("runtime_node_next_state_mismatch", "next_state", contract, observation, findings)
    if contract.expected_terminal and not observation.observed_terminal:
        findings.append(
            RuntimePathFinding(
                "runtime_node_business_terminal_missing",
                f"runtime node {contract.node_id!r} does not report the expected business terminal",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata={"expected_terminal": contract.expected_terminal},
            )
        )
    elif contract.expected_terminal and observation.observed_terminal and contract.expected_terminal != observation.observed_terminal:
        _behavior_finding("runtime_node_business_terminal_mismatch", "business_terminal", contract, observation, findings)
    _extra_tuple_items(
        "runtime_node_state_write_mismatch",
        "state writes",
        contract.allowed_state_writes,
        observation.observed_state_writes,
        contract,
        observation,
        findings,
    )
    _extra_tuple_items(
        "runtime_node_side_effect_mismatch",
        "side effects",
        contract.allowed_side_effects,
        observation.observed_side_effects,
        contract,
        observation,
        findings,
    )
    if (
        contract.allowed_error_paths
        and observation.observed_error_path
        and observation.observed_error_path not in contract.allowed_error_paths
    ):
        _behavior_finding("runtime_node_error_path_mismatch", "error_path", contract, observation, findings)


def _behavior_finding(
    code: str,
    field_name: str,
    contract: RuntimeNodeContract,
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    findings.append(
        RuntimePathFinding(
            code,
            f"runtime node {contract.node_id!r} observed {field_name} is outside the modeled contract",
            node_id=contract.node_id,
            observation_id=observation.observation_id,
            evidence_id=observation.evidence_key(),
            metadata={"contract": contract.to_dict(), "observation": observation.to_dict()},
        )
    )


def _extra_tuple_items(
    code: str,
    label: str,
    allowed: tuple[str, ...],
    observed: tuple[str, ...],
    contract: RuntimeNodeContract,
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    if not allowed:
        return
    extra = tuple(value for value in observed if value not in allowed)
    if extra:
        findings.append(
            RuntimePathFinding(
                code,
                f"runtime node {contract.node_id!r} observed unexpected {label}",
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata={
                    "expected_allowed": list(allowed),
                    "observed": list(observed),
                    "extra": list(_unique(extra)),
                },
            )
        )


def _review_proof_artifact(
    contract: RuntimeNodeContract,
    observation: RuntimeNodeObservation,
    findings: list[RuntimePathFinding],
) -> None:
    gaps = proof_artifact_gap_codes(
        observation.proof_artifact,
        declared_status=observation.result_status,
        required_obligation_ids=(contract.model_obligation_id,) if contract.model_obligation_id else (),
        require_result_path=True,
        require_external_scope=True,
    )
    for code, message in gaps:
        findings.append(
            RuntimePathFinding(
                code,
                message,
                node_id=contract.node_id,
                observation_id=observation.observation_id,
                evidence_id=observation.evidence_key(),
                metadata={"contract": contract.to_dict(), "observation": observation.to_dict()},
            )
        )


def _review_exact_path(
    contracts: tuple[RuntimeNodeContract, ...],
    observations: tuple[RuntimeNodeObservation, ...],
    findings: list[RuntimePathFinding],
) -> None:
    ordered_contracts = tuple(
        sorted(
            (contract for contract in contracts if contract.required and contract.ordered),
            key=lambda contract: (
                contract.sequence_index if contract.sequence_index is not None else 10**9,
                contract.node_id,
            ),
        )
    )
    expected_node_ids = tuple(contract.node_id for contract in ordered_contracts)
    if not expected_node_ids:
        return

    first_position: dict[str, int] = {}
    for position, observation in enumerate(observations):
        if observation.has_current_pass() and observation.node_id not in first_position:
            first_position[observation.node_id] = (
                observation.sequence_index if observation.sequence_index is not None else position
            )

    observed_order = tuple(node_id for node_id in expected_node_ids if node_id in first_position)
    if observed_order != expected_node_ids:
        findings.append(
            RuntimePathFinding(
                "runtime_path_missing_ordered_node",
                "runtime path does not contain every required ordered node",
                metadata={"expected_order": list(expected_node_ids), "observed_order": list(observed_order)},
            )
        )
        return

    observed_positions = [first_position[node_id] for node_id in expected_node_ids]
    if observed_positions != sorted(observed_positions):
        findings.append(
            RuntimePathFinding(
                "runtime_path_order_mismatch",
                "runtime path observations are not in the modeled node order",
                metadata={"expected_order": list(expected_node_ids), "positions": observed_positions},
            )
        )


__all__ = [
    "EXTERNAL_RUNTIME_PATH_SCOPES",
    "NON_PASSING_RUNTIME_PATH_STATUSES",
    "PASSING_RUNTIME_PATH_STATUSES",
    "RUNTIME_PATH_ASSERTION_SCOPE_EXTERNAL_CONTRACT",
    "RUNTIME_PATH_ASSERTION_SCOPE_INTERNAL_PATH",
    "RUNTIME_PATH_ASSERTION_SCOPE_MIXED",
    "RUNTIME_PATH_ASSERTION_SCOPE_UNKNOWN",
    "RUNTIME_PATH_CONFIDENCE_BLOCKED",
    "RUNTIME_PATH_CONFIDENCE_FULL",
    "RUNTIME_PATH_CONFIDENCE_SCOPED",
    "RUNTIME_PATH_DECISION_BLOCKED",
    "RUNTIME_PATH_DECISION_GREEN",
    "RUNTIME_PATH_DECISION_SCOPED",
    "RUNTIME_PATH_STATUS_ERROR",
    "RUNTIME_PATH_STATUS_FAILED",
    "RUNTIME_PATH_STATUS_NOT_RUN",
    "RUNTIME_PATH_STATUS_PASSED",
    "RUNTIME_PATH_STATUS_RUNNING",
    "RUNTIME_PATH_STATUS_SKIPPED",
    "RUNTIME_PATH_STATUS_STALE",
    "RuntimeNodeContract",
    "RuntimeNodeObservation",
    "RuntimePathAlignmentPlan",
    "RuntimePathAlignmentReport",
    "RuntimePathFinding",
    "RuntimePathRecorder",
    "RuntimePathRun",
    "review_runtime_path_alignment",
]
