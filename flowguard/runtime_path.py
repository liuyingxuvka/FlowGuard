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
    expected_terminal: str = ""
    primary_path_id: str = ""
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
        object.__setattr__(self, "expected_terminal", str(self.expected_terminal))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
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
            "expected_terminal": self.expected_terminal,
            "primary_path_id": self.primary_path_id,
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
    primary_path_id: str = ""
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
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
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
            ("primary_path", self.primary_path_id),
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
            "primary_path_id": self.primary_path_id,
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
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "observations": [observation.to_dict() for observation in self.observations],
            "source_evidence_id": self.source_evidence_id,
            "result_status": self.result_status,
            "current": self.current,
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
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
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
