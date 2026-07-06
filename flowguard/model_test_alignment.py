"""Model obligation, code contract, and test evidence alignment helpers.

Model-Test Alignment reviews whether explicit FlowGuard model obligations,
code external contracts, and ordinary test evidence describe the same
behavioral surface. Full confidence requires all three by default. It
intentionally does not read TestMesh, StructureMesh, or ModelMesh reports.
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .model_similarity import SimilarityHandoff, normalize_similarity_handoff
from .obligation_family import (
    ObligationFamily,
    ObligationFamilyEvidence,
    ObligationFamilyParityFinding,
    review_obligation_family_parity,
)
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes
from .runtime_path import (
    RuntimeNodeContract,
    RuntimeNodeObservation,
    RuntimePathAlignmentPlan,
    RuntimePathRun,
    review_runtime_path_alignment,
)
from .test_reuse import (
    TestResultReuseTicket,
    coerce_test_result_reuse_ticket,
    test_result_reuse_gap_codes,
)


TEST_STATUS_PASSED = "passed"
TEST_STATUS_FAILED = "failed"
TEST_STATUS_TIMEOUT = "timeout"
TEST_STATUS_SKIPPED = "skipped"
TEST_STATUS_NOT_RUN = "not_run"
TEST_STATUS_RUNNING = "running"
TEST_STATUS_ERROR = "error"

PASSING_STATUSES = {TEST_STATUS_PASSED}
NON_PASSING_STATUSES = {
    TEST_STATUS_FAILED,
    TEST_STATUS_TIMEOUT,
    TEST_STATUS_SKIPPED,
    TEST_STATUS_NOT_RUN,
    TEST_STATUS_RUNNING,
    TEST_STATUS_ERROR,
}

TEST_KIND_HAPPY_PATH = "happy_path"
TEST_KIND_FAILURE_PATH = "failure_path"
TEST_KIND_EDGE_PATH = "edge_path"
TEST_KIND_NEGATIVE_PATH = "negative_path"
TEST_KIND_REPLAY = "replay"

TEST_EVIDENCE_ROLE_PRIMARY = "primary"
TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH = "primary_edge_path"
TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL = "leaf_matrix_cell"
TEST_EVIDENCE_ROLE_TRANSITION_CELL = "transition_cell"
TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT = "supporting_contract"
TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE = "integration_smoke"
PRIMARY_TEST_EVIDENCE_ROLES = {
    TEST_EVIDENCE_ROLE_PRIMARY,
    TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH,
}
ALLOWED_TEST_EVIDENCE_ROLES = PRIMARY_TEST_EVIDENCE_ROLES | {
    TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL,
    TEST_EVIDENCE_ROLE_TRANSITION_CELL,
    TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT,
    TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE,
}

TEST_CLOSURE_ROLE_UNSPECIFIED = ""
TEST_CLOSURE_ROLE_OBSERVED_REGRESSION = "observed_regression"
TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED = "same_class_generalized"
TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION = "counterexample_regression"
TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY = "known_bad_replay"
MODEL_MISS_DEFAULT_CLOSURE_ROLES = (
    TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
    TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
)
TARGET_AWARE_CLOSURE_ROLES = (
    TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
    TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
)

TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT = "external_contract"
TEST_ASSERTION_SCOPE_INTERNAL_PATH = "internal_path"
TEST_ASSERTION_SCOPE_MIXED = "mixed"
TEST_ASSERTION_SCOPE_UNKNOWN = "unknown"

ARTIFACT_PAYLOAD_STATUS_ACCEPTED = "accepted"
ARTIFACT_PAYLOAD_STATUS_REJECTED = "rejected"

ARTIFACT_PAYLOAD_METHOD_AUTOMATED_TEST = "automated_test"
ARTIFACT_PAYLOAD_METHOD_BROWSER = "browser"
ARTIFACT_PAYLOAD_METHOD_DESKTOP = "desktop"
ARTIFACT_PAYLOAD_METHOD_MANUAL = "manual"
ARTIFACT_PAYLOAD_METHOD_REPLAY = "replay"

CODE_CONTRACT_ROLE_OWNER = "owner"
CODE_CONTRACT_ROLE_HELPER = "helper"
CODE_CONTRACT_ROLE_ADAPTER = "adapter"
CODE_CONTRACT_ROLE_FACADE = "facade"
CODE_CONTRACT_ROLE_READ_ONLY = "read_only"

SIDE_EFFECT_CALL_PREFIXES = (
    "write",
    "save",
    "publish",
    "send",
    "emit",
    "delete",
    "create",
    "update",
    "insert",
    "post",
    "put",
    "patch",
    "commit",
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _tuple_set(values: Sequence[str]) -> set[str]:
    return {str(value) for value in values}


def _unique_sorted(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class ClosureEvidenceTarget:
    """One concrete bad-case or closure target that test evidence must replay."""

    target_id: str
    closure_evidence_role: str = TEST_CLOSURE_ROLE_UNSPECIFIED
    source_kind: str = ""
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", str(self.target_id))
        object.__setattr__(self, "closure_evidence_role", str(self.closure_evidence_role))
        object.__setattr__(self, "source_kind", str(self.source_kind))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "closure_evidence_role": self.closure_evidence_role,
            "source_kind": self.source_kind,
            "required": self.required,
            "description": self.description,
        }


def _coerce_closure_evidence_target(
    target: ClosureEvidenceTarget | Mapping[str, Any],
) -> ClosureEvidenceTarget:
    if isinstance(target, ClosureEvidenceTarget):
        return target
    return ClosureEvidenceTarget(**dict(target))


@dataclass(frozen=True)
class ModelObligation:
    """One scenario, invariant, hazard, transition, or contract the model owns."""

    obligation_id: str
    obligation_type: str = "scenario"
    description: str = ""
    required: bool = True
    required_test_kinds: tuple[str, ...] = ()
    risk_level: str = "normal"
    allow_shared_evidence: bool = False
    allow_shared_implementation: bool = False
    external_inputs: tuple[str, ...] = ()
    external_outputs: tuple[str, ...] = ()
    state_reads: tuple[str, ...] = ()
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    error_paths: tuple[str, ...] = ()
    exact_external_contract: bool = False
    model_miss_origin: bool = False
    requires_same_class_test_evidence: bool = False
    required_closure_evidence_roles: tuple[str, ...] = ()
    required_closure_targets: tuple[ClosureEvidenceTarget | Mapping[str, Any], ...] = ()
    required_runtime_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "obligation_type", str(self.obligation_type))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "required_test_kinds", _as_tuple(self.required_test_kinds))
        object.__setattr__(self, "risk_level", str(self.risk_level))
        object.__setattr__(self, "external_inputs", _as_tuple(self.external_inputs))
        object.__setattr__(self, "external_outputs", _as_tuple(self.external_outputs))
        object.__setattr__(self, "state_reads", _as_tuple(self.state_reads))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "error_paths", _as_tuple(self.error_paths))
        closure_targets = tuple(
            _coerce_closure_evidence_target(target)
            for target in self.required_closure_targets
        )
        object.__setattr__(self, "required_closure_targets", closure_targets)
        closure_roles = list(_as_tuple(self.required_closure_evidence_roles))
        closure_roles.extend(
            target.closure_evidence_role
            for target in closure_targets
            if target.required and target.closure_evidence_role
        )
        if self.requires_same_class_test_evidence and not closure_roles:
            closure_roles.extend(MODEL_MISS_DEFAULT_CLOSURE_ROLES)
        object.__setattr__(self, "required_closure_evidence_roles", _unique_sorted(closure_roles))
        object.__setattr__(self, "required_runtime_node_ids", _as_tuple(self.required_runtime_node_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "obligation_type": self.obligation_type,
            "description": self.description,
            "required": self.required,
            "required_test_kinds": list(self.required_test_kinds),
            "risk_level": self.risk_level,
            "allow_shared_evidence": self.allow_shared_evidence,
            "allow_shared_implementation": self.allow_shared_implementation,
            "external_inputs": list(self.external_inputs),
            "external_outputs": list(self.external_outputs),
            "state_reads": list(self.state_reads),
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "error_paths": list(self.error_paths),
            "exact_external_contract": self.exact_external_contract,
            "model_miss_origin": self.model_miss_origin,
            "requires_same_class_test_evidence": self.requires_same_class_test_evidence,
            "required_closure_evidence_roles": list(self.required_closure_evidence_roles),
            "required_closure_targets": [target.to_dict() for target in self.required_closure_targets],
            "required_runtime_node_ids": list(self.required_runtime_node_ids),
        }


@dataclass(frozen=True)
class CodeContract:
    """One code surface's externally visible contract for model-backed behavior."""

    code_contract_id: str
    path: str = ""
    symbol: str = ""
    surface_type: str = "function"
    role: str = CODE_CONTRACT_ROLE_OWNER
    implements_obligations: tuple[str, ...] = ()
    external_inputs: tuple[str, ...] = ()
    external_outputs: tuple[str, ...] = ()
    state_reads: tuple[str, ...] = ()
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    error_paths: tuple[str, ...] = ()
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "symbol", str(self.symbol))
        object.__setattr__(self, "surface_type", str(self.surface_type))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "implements_obligations", _as_tuple(self.implements_obligations))
        object.__setattr__(self, "external_inputs", _as_tuple(self.external_inputs))
        object.__setattr__(self, "external_outputs", _as_tuple(self.external_outputs))
        object.__setattr__(self, "state_reads", _as_tuple(self.state_reads))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "error_paths", _as_tuple(self.error_paths))

    def is_owner(self) -> bool:
        return self.role == CODE_CONTRACT_ROLE_OWNER

    def to_dict(self) -> dict[str, Any]:
        return {
            "code_contract_id": self.code_contract_id,
            "path": self.path,
            "symbol": self.symbol,
            "surface_type": self.surface_type,
            "role": self.role,
            "implements_obligations": list(self.implements_obligations),
            "external_inputs": list(self.external_inputs),
            "external_outputs": list(self.external_outputs),
            "state_reads": list(self.state_reads),
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "error_paths": list(self.error_paths),
            "required": self.required,
        }


@dataclass(frozen=True)
class PythonCodeContractEvidence:
    """Conservative AST evidence extracted from one Python code contract surface."""

    code_contract_id: str
    path: str = ""
    symbol: str = ""
    found: bool = False
    parameters: tuple[str, ...] = ()
    returns_value: bool = False
    return_values: tuple[str, ...] = ()
    raised_errors: tuple[str, ...] = ()
    state_reads: tuple[str, ...] = ()
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    parse_error: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "symbol", str(self.symbol))
        object.__setattr__(self, "parameters", _as_tuple(self.parameters))
        object.__setattr__(self, "return_values", _as_tuple(self.return_values))
        object.__setattr__(self, "raised_errors", _as_tuple(self.raised_errors))
        object.__setattr__(self, "state_reads", _as_tuple(self.state_reads))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "calls", _as_tuple(self.calls))
        object.__setattr__(self, "parse_error", str(self.parse_error))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code_contract_id": self.code_contract_id,
            "path": self.path,
            "symbol": self.symbol,
            "found": self.found,
            "parameters": list(self.parameters),
            "returns_value": self.returns_value,
            "return_values": list(self.return_values),
            "raised_errors": list(self.raised_errors),
            "state_reads": list(self.state_reads),
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "calls": list(self.calls),
            "parse_error": self.parse_error,
        }


@dataclass(frozen=True)
class PythonTestAssertionEvidence:
    """Conservative AST evidence extracted from one Python test function."""

    evidence_id: str
    path: str = ""
    test_name: str = ""
    found: bool = False
    called_code_contracts: tuple[str, ...] = ()
    assert_count: int = 0
    assertion_scope: str = TEST_ASSERTION_SCOPE_UNKNOWN
    calls: tuple[str, ...] = ()
    parse_error: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "test_name", str(self.test_name))
        object.__setattr__(self, "called_code_contracts", _as_tuple(self.called_code_contracts))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "calls", _as_tuple(self.calls))
        object.__setattr__(self, "parse_error", str(self.parse_error))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "path": self.path,
            "test_name": self.test_name,
            "found": self.found,
            "called_code_contracts": list(self.called_code_contracts),
            "assert_count": self.assert_count,
            "assertion_scope": self.assertion_scope,
            "calls": list(self.calls),
            "parse_error": self.parse_error,
        }


@dataclass(frozen=True)
class TestEvidence:
    """Plain evidence from one test, command, replay, or manual validation."""

    __test__ = False

    evidence_id: str
    test_name: str = ""
    path: str = ""
    command: str = ""
    result_status: str = TEST_STATUS_NOT_RUN
    evidence_current: bool = True
    test_kind: str = TEST_KIND_HAPPY_PATH
    covered_obligations: tuple[str, ...] = ()
    covered_code_contracts: tuple[str, ...] = ()
    assertion_scope: str = TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT
    evidence_role: str = TEST_EVIDENCE_ROLE_PRIMARY
    evidence_target_id: str = ""
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    result_reused: bool = False
    reuse_ticket: TestResultReuseTicket | Mapping[str, Any] | None = None
    stale_reasons: tuple[str, ...] = ()
    overclaims_model_confidence: bool = False
    closure_evidence_role: str = TEST_CLOSURE_ROLE_UNSPECIFIED

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "test_name", str(self.test_name))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "test_kind", str(self.test_kind))
        object.__setattr__(self, "covered_obligations", _as_tuple(self.covered_obligations))
        object.__setattr__(self, "covered_code_contracts", _as_tuple(self.covered_code_contracts))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "evidence_role", str(self.evidence_role))
        object.__setattr__(self, "evidence_target_id", str(self.evidence_target_id))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "result_reused", bool(self.result_reused))
        object.__setattr__(self, "reuse_ticket", coerce_test_result_reuse_ticket(self.reuse_ticket))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))
        object.__setattr__(self, "closure_evidence_role", str(self.closure_evidence_role))

    def has_current_pass(self) -> bool:
        return self.result_status in PASSING_STATUSES and self.evidence_current

    def has_external_contract_assertion(self) -> bool:
        return self.assertion_scope in {
            TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            TEST_ASSERTION_SCOPE_MIXED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "test_name": self.test_name,
            "path": self.path,
            "command": self.command,
            "result_status": self.result_status,
            "evidence_current": self.evidence_current,
            "test_kind": self.test_kind,
            "covered_obligations": list(self.covered_obligations),
            "covered_code_contracts": list(self.covered_code_contracts),
            "assertion_scope": self.assertion_scope,
            "evidence_role": self.evidence_role,
            "evidence_target_id": self.evidence_target_id,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "result_reused": self.result_reused,
            "reuse_ticket": self.reuse_ticket.to_dict() if self.reuse_ticket else None,
            "stale_reasons": list(self.stale_reasons),
            "overclaims_model_confidence": self.overclaims_model_confidence,
            "closure_evidence_role": self.closure_evidence_role,
        }


@dataclass(frozen=True)
class CodeBoundaryContract:
    """Runtime boundary contract for one model-backed code surface."""

    boundary_id: str
    code_contract_id: str = ""
    model_obligation_id: str = ""
    allowed_inputs: tuple[str, ...] = ()
    rejected_inputs: tuple[str, ...] = ()
    allowed_outputs: tuple[str, ...] = ()
    allowed_state_writes: tuple[str, ...] = ()
    allowed_side_effects: tuple[str, ...] = ()
    allowed_error_paths: tuple[str, ...] = ()
    exact: bool = True
    input_gate_required: bool = True
    required: bool = True
    required_observation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "boundary_id", str(self.boundary_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "allowed_inputs", _as_tuple(self.allowed_inputs))
        object.__setattr__(self, "rejected_inputs", _as_tuple(self.rejected_inputs))
        object.__setattr__(self, "allowed_outputs", _as_tuple(self.allowed_outputs))
        object.__setattr__(self, "allowed_state_writes", _as_tuple(self.allowed_state_writes))
        object.__setattr__(self, "allowed_side_effects", _as_tuple(self.allowed_side_effects))
        object.__setattr__(self, "allowed_error_paths", _as_tuple(self.allowed_error_paths))
        object.__setattr__(self, "required_observation_ids", _as_tuple(self.required_observation_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "code_contract_id": self.code_contract_id,
            "model_obligation_id": self.model_obligation_id,
            "allowed_inputs": list(self.allowed_inputs),
            "rejected_inputs": list(self.rejected_inputs),
            "allowed_outputs": list(self.allowed_outputs),
            "allowed_state_writes": list(self.allowed_state_writes),
            "allowed_side_effects": list(self.allowed_side_effects),
            "allowed_error_paths": list(self.allowed_error_paths),
            "exact": self.exact,
            "input_gate_required": self.input_gate_required,
            "required": self.required,
            "required_observation_ids": list(self.required_observation_ids),
        }


@dataclass(frozen=True)
class CodeBoundaryObservation:
    """Real-code observation collected by a boundary test, replay, or harness."""

    observation_id: str
    boundary_id: str
    input_case: str = ""
    accepted: bool = True
    observed_output: str = ""
    observed_state_writes: tuple[str, ...] = ()
    observed_side_effects: tuple[str, ...] = ()
    observed_error_path: str = ""
    result_status: str = TEST_STATUS_PASSED
    evidence_current: bool = True
    evidence_id: str = ""
    assertion_scope: str = TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", str(self.observation_id))
        object.__setattr__(self, "boundary_id", str(self.boundary_id))
        object.__setattr__(self, "input_case", str(self.input_case))
        object.__setattr__(self, "observed_output", str(self.observed_output))
        object.__setattr__(self, "observed_state_writes", _as_tuple(self.observed_state_writes))
        object.__setattr__(self, "observed_side_effects", _as_tuple(self.observed_side_effects))
        object.__setattr__(self, "observed_error_path", str(self.observed_error_path))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_current_pass(self) -> bool:
        return self.result_status in PASSING_STATUSES and self.evidence_current

    def has_external_boundary_assertion(self) -> bool:
        return self.assertion_scope in {
            TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            TEST_ASSERTION_SCOPE_MIXED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "boundary_id": self.boundary_id,
            "input_case": self.input_case,
            "accepted": self.accepted,
            "observed_output": self.observed_output,
            "observed_state_writes": list(self.observed_state_writes),
            "observed_side_effects": list(self.observed_side_effects),
            "observed_error_path": self.observed_error_path,
            "result_status": self.result_status,
            "evidence_current": self.evidence_current,
            "evidence_id": self.evidence_id,
            "assertion_scope": self.assertion_scope,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class CodeBoundaryFinding:
    """One runtime code-boundary conformance gap."""

    code: str
    message: str
    severity: str = "blocker"
    boundary_id: str = ""
    observation_id: str = ""
    code_contract_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "boundary_id", str(self.boundary_id))
        object.__setattr__(self, "observation_id", str(self.observation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "boundary_id": self.boundary_id,
            "observation_id": self.observation_id,
            "code_contract_id": self.code_contract_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class CodeBoundaryConformanceReport:
    """Structured result of checking real-code observations against a boundary."""

    ok: bool
    decision: str
    findings: tuple[CodeBoundaryFinding, ...] = ()
    checked_boundaries: int = 0
    checked_observations: int = 0
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                (
                    f"{status}: code_boundary_conformance "
                    f"boundaries={self.checked_boundaries} "
                    f"observations={self.checked_observations} "
                    f"findings={len(self.findings)}"
                ),
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard code boundary conformance ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            f"boundaries: {self.checked_boundaries}",
            f"observations: {self.checked_observations}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"boundary: {finding.boundary_id or '(none)'}",
                    f"code_contract: {finding.code_contract_id or '(none)'}",
                    f"observation: {finding.observation_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "checked_boundaries": self.checked_boundaries,
            "checked_observations": self.checked_observations,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ArtifactPayloadCase:
    """One synthetic or real payload case required for an artifact-like surface."""

    case_id: str
    description: str = ""
    expected_status: str = ARTIFACT_PAYLOAD_STATUS_ACCEPTED
    required: bool = True
    expected_output: str = ""
    expected_error_path: str = ""
    expected_state_writes: tuple[str, ...] = ()
    expected_side_effects: tuple[str, ...] = ()
    round_trip_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "expected_status", str(self.expected_status))
        object.__setattr__(self, "expected_output", str(self.expected_output))
        object.__setattr__(self, "expected_error_path", str(self.expected_error_path))
        object.__setattr__(self, "expected_state_writes", _as_tuple(self.expected_state_writes))
        object.__setattr__(self, "expected_side_effects", _as_tuple(self.expected_side_effects))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "expected_status": self.expected_status,
            "required": self.required,
            "expected_output": self.expected_output,
            "expected_error_path": self.expected_error_path,
            "expected_state_writes": list(self.expected_state_writes),
            "expected_side_effects": list(self.expected_side_effects),
            "round_trip_required": self.round_trip_required,
        }


def _coerce_payload_case(case: ArtifactPayloadCase | Mapping[str, Any]) -> ArtifactPayloadCase:
    if isinstance(case, ArtifactPayloadCase):
        return case
    return ArtifactPayloadCase(**dict(case))


@dataclass(frozen=True)
class ArtifactPayloadContract:
    """Validation contract for import/export files, generated packs, or AI work packages."""

    payload_contract_id: str
    model_obligation_id: str = ""
    code_contract_id: str = ""
    payload_surface: str = ""
    payload_kind: str = ""
    cases: tuple[ArtifactPayloadCase, ...] = ()
    required: bool = True
    exact: bool = True
    allow_scoped_cases: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload_contract_id", str(self.payload_contract_id))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "payload_surface", str(self.payload_surface))
        object.__setattr__(self, "payload_kind", str(self.payload_kind))
        object.__setattr__(self, "cases", tuple(_coerce_payload_case(case) for case in self.cases))

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_contract_id": self.payload_contract_id,
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "payload_surface": self.payload_surface,
            "payload_kind": self.payload_kind,
            "cases": [case.to_dict() for case in self.cases],
            "required": self.required,
            "exact": self.exact,
            "allow_scoped_cases": self.allow_scoped_cases,
        }


@dataclass(frozen=True)
class ArtifactPayloadEvidence:
    """Observed result for one artifact payload case."""

    evidence_id: str
    payload_contract_id: str
    case_id: str = ""
    method: str = ARTIFACT_PAYLOAD_METHOD_AUTOMATED_TEST
    result_status: str = TEST_STATUS_PASSED
    evidence_current: bool = True
    assertion_scope: str = TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT
    observed_status: str = ""
    observed_output: str = ""
    observed_error_path: str = ""
    observed_state_writes: tuple[str, ...] = ()
    observed_side_effects: tuple[str, ...] = ()
    round_trip_ok: bool = False
    evidence_ref: str = ""
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "payload_contract_id", str(self.payload_contract_id))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "method", str(self.method))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "observed_status", str(self.observed_status))
        object.__setattr__(self, "observed_output", str(self.observed_output))
        object.__setattr__(self, "observed_error_path", str(self.observed_error_path))
        object.__setattr__(self, "observed_state_writes", _as_tuple(self.observed_state_writes))
        object.__setattr__(self, "observed_side_effects", _as_tuple(self.observed_side_effects))
        object.__setattr__(self, "evidence_ref", str(self.evidence_ref))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_current_pass(self) -> bool:
        return self.result_status in PASSING_STATUSES and self.evidence_current

    def has_external_payload_assertion(self) -> bool:
        return self.assertion_scope in {
            TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            TEST_ASSERTION_SCOPE_MIXED,
        }

    def has_current_external_pass(self) -> bool:
        return self.has_current_pass() and self.has_external_payload_assertion()

    def has_structured_manual_record(self) -> bool:
        if self.method != ARTIFACT_PAYLOAD_METHOD_MANUAL:
            return True
        has_observation = any(
            (
                self.observed_status,
                self.observed_output,
                self.observed_error_path,
                self.observed_state_writes,
                self.observed_side_effects,
            )
        )
        return bool(self.evidence_ref or self.proof_artifact) and bool(self.case_id) and has_observation

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "payload_contract_id": self.payload_contract_id,
            "case_id": self.case_id,
            "method": self.method,
            "result_status": self.result_status,
            "evidence_current": self.evidence_current,
            "assertion_scope": self.assertion_scope,
            "observed_status": self.observed_status,
            "observed_output": self.observed_output,
            "observed_error_path": self.observed_error_path,
            "observed_state_writes": list(self.observed_state_writes),
            "observed_side_effects": list(self.observed_side_effects),
            "round_trip_ok": self.round_trip_ok,
            "evidence_ref": self.evidence_ref,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArtifactPayloadFinding:
    """One artifact payload contract, case, or evidence gap."""

    code: str
    message: str
    severity: str = "blocker"
    payload_contract_id: str = ""
    case_id: str = ""
    evidence_id: str = ""
    model_obligation_id: str = ""
    code_contract_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "payload_contract_id", str(self.payload_contract_id))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "payload_contract_id": self.payload_contract_id,
            "case_id": self.case_id,
            "evidence_id": self.evidence_id,
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArtifactPayloadValidationReport:
    """Structured result of checking artifact payload evidence against contracts."""

    ok: bool
    decision: str
    findings: tuple[ArtifactPayloadFinding, ...] = ()
    checked_contracts: int = 0
    checked_cases: int = 0
    checked_evidence: int = 0
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                (
                    f"{status}: artifact_payload_validation "
                    f"contracts={self.checked_contracts} "
                    f"cases={self.checked_cases} "
                    f"evidence={self.checked_evidence} "
                    f"findings={len(self.findings)}"
                ),
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard artifact payload validation ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            f"contracts: {self.checked_contracts}",
            f"cases: {self.checked_cases}",
            f"evidence: {self.checked_evidence}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"payload_contract: {finding.payload_contract_id or '(none)'}",
                    f"case: {finding.case_id or '(none)'}",
                    f"code_contract: {finding.code_contract_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "checked_contracts": self.checked_contracts,
            "checked_cases": self.checked_cases,
            "checked_evidence": self.checked_evidence,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ModelTestAlignmentPlan:
    """A direct model-obligation, code-contract, and test-evidence review plan."""

    model_id: str
    obligations: tuple[ModelObligation, ...] = ()
    code_contracts: tuple[CodeContract, ...] = ()
    test_evidence: tuple[TestEvidence, ...] = ()
    obligation_families: tuple[ObligationFamily, ...] = ()
    family_evidence: tuple[ObligationFamilyEvidence, ...] = ()
    boundary_contracts: tuple[CodeBoundaryContract, ...] = ()
    boundary_observations: tuple[CodeBoundaryObservation, ...] = ()
    payload_contracts: tuple[ArtifactPayloadContract, ...] = ()
    payload_evidence: tuple[ArtifactPayloadEvidence, ...] = ()
    runtime_node_contracts: tuple[RuntimeNodeContract, ...] = ()
    runtime_node_observations: tuple[RuntimeNodeObservation, ...] = ()
    runtime_path_runs: tuple[RuntimePathRun, ...] = ()
    source_audit_reports: tuple[Any, ...] = ()
    field_lifecycle_reports: tuple[Any, ...] = ()
    field_lifecycle_projections: tuple[Any, ...] = ()
    similarity_handoff: SimilarityHandoff | Mapping[str, Any] | None = None
    require_proof_artifacts: bool = False
    require_runtime_path_evidence: bool = False
    require_source_audit: bool = False
    allow_orphan_tests: bool = False
    allow_orphan_code_contracts: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "code_contracts", tuple(self.code_contracts))
        object.__setattr__(self, "test_evidence", tuple(self.test_evidence))
        object.__setattr__(self, "obligation_families", tuple(self.obligation_families))
        object.__setattr__(self, "family_evidence", tuple(self.family_evidence))
        object.__setattr__(self, "boundary_contracts", tuple(self.boundary_contracts))
        object.__setattr__(self, "boundary_observations", tuple(self.boundary_observations))
        object.__setattr__(
            self,
            "payload_contracts",
            tuple(
                contract
                if isinstance(contract, ArtifactPayloadContract)
                else ArtifactPayloadContract(**contract)
                for contract in self.payload_contracts
            ),
        )
        object.__setattr__(
            self,
            "payload_evidence",
            tuple(
                evidence
                if isinstance(evidence, ArtifactPayloadEvidence)
                else ArtifactPayloadEvidence(**evidence)
                for evidence in self.payload_evidence
            ),
        )
        object.__setattr__(
            self,
            "runtime_node_contracts",
            tuple(
                item
                if isinstance(item, RuntimeNodeContract)
                else RuntimeNodeContract(**item)
                for item in self.runtime_node_contracts
            ),
        )
        object.__setattr__(
            self,
            "runtime_node_observations",
            tuple(
                item
                if isinstance(item, RuntimeNodeObservation)
                else RuntimeNodeObservation(**item)
                for item in self.runtime_node_observations
            ),
        )
        object.__setattr__(
            self,
            "runtime_path_runs",
            tuple(item if isinstance(item, RuntimePathRun) else RuntimePathRun(**item) for item in self.runtime_path_runs),
        )
        object.__setattr__(self, "source_audit_reports", tuple(self.source_audit_reports))
        object.__setattr__(self, "field_lifecycle_reports", tuple(self.field_lifecycle_reports))
        object.__setattr__(self, "field_lifecycle_projections", tuple(self.field_lifecycle_projections))
        object.__setattr__(self, "similarity_handoff", normalize_similarity_handoff(self.similarity_handoff))
        object.__setattr__(self, "require_source_audit", bool(self.require_source_audit))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "obligations": [obligation.to_dict() for obligation in self.obligations],
            "code_contracts": [contract.to_dict() for contract in self.code_contracts],
            "test_evidence": [evidence.to_dict() for evidence in self.test_evidence],
            "obligation_families": [family.to_dict() for family in self.obligation_families],
            "family_evidence": [evidence.to_dict() for evidence in self.family_evidence],
            "boundary_contracts": [contract.to_dict() for contract in self.boundary_contracts],
            "boundary_observations": [observation.to_dict() for observation in self.boundary_observations],
            "payload_contracts": [contract.to_dict() for contract in self.payload_contracts],
            "payload_evidence": [evidence.to_dict() for evidence in self.payload_evidence],
            "runtime_node_contracts": [contract.to_dict() for contract in self.runtime_node_contracts],
            "runtime_node_observations": [
                observation.to_dict() for observation in self.runtime_node_observations
            ],
            "runtime_path_runs": [run.to_dict() for run in self.runtime_path_runs],
            "source_audit_reports": [
                report.to_dict() if hasattr(report, "to_dict") else to_jsonable(report)
                for report in self.source_audit_reports
            ],
            "field_lifecycle_reports": [
                report.to_dict() if hasattr(report, "to_dict") else to_jsonable(report)
                for report in self.field_lifecycle_reports
            ],
            "field_lifecycle_projections": [
                projection.to_dict() if hasattr(projection, "to_dict") else to_jsonable(projection)
                for projection in self.field_lifecycle_projections
            ],
            "similarity_handoff": self.similarity_handoff.to_dict()
            if self.similarity_handoff
            else None,
            "require_proof_artifacts": self.require_proof_artifacts,
            "require_runtime_path_evidence": self.require_runtime_path_evidence,
            "require_source_audit": self.require_source_audit,
            "allow_orphan_tests": self.allow_orphan_tests,
            "allow_orphan_code_contracts": self.allow_orphan_code_contracts,
        }


@dataclass(frozen=True)
class ModelTestAlignmentFinding:
    """One alignment gap, overlap, stale evidence, or overclaim."""

    code: str
    message: str
    severity: str = "blocker"
    obligation_id: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    code_contract_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "obligation_id": self.obligation_id,
            "evidence_id": self.evidence_id,
            "code_contract_id": self.code_contract_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelCodeTestBindingRow:
    """One visible closure row for a required model obligation."""

    model_obligation_id: str
    code_contract_id: str = ""
    test_evidence_id: str = ""
    status: str = "blocked"
    gaps: tuple[str, ...] = ()
    code_contract_ids: tuple[str, ...] = ()
    owner_code_contract_ids: tuple[str, ...] = ()
    code_paths: tuple[str, ...] = ()
    code_symbols: tuple[str, ...] = ()
    test_evidence_ids: tuple[str, ...] = ()
    boundary_contract_ids: tuple[str, ...] = ()
    boundary_observation_ids: tuple[str, ...] = ()
    runtime_node_ids: tuple[str, ...] = ()
    runtime_observation_ids: tuple[str, ...] = ()
    payload_contract_ids: tuple[str, ...] = ()
    field_projection_ids: tuple[str, ...] = ()
    source_audit_decision: str = ""
    open_gap_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "test_evidence_id", str(self.test_evidence_id))
        object.__setattr__(self, "status", str(self.status))
        code_contract_ids = _unique_sorted(
            tuple(self.code_contract_ids) + ((self.code_contract_id,) if self.code_contract_id else ())
        )
        test_evidence_ids = _unique_sorted(
            tuple(self.test_evidence_ids) + ((self.test_evidence_id,) if self.test_evidence_id else ())
        )
        open_gap_codes = _unique_sorted(tuple(self.open_gap_codes) + tuple(self.gaps))
        object.__setattr__(self, "code_contract_ids", code_contract_ids)
        object.__setattr__(self, "owner_code_contract_ids", _unique_sorted(self.owner_code_contract_ids))
        object.__setattr__(self, "code_paths", _unique_sorted(self.code_paths))
        object.__setattr__(self, "code_symbols", _unique_sorted(self.code_symbols))
        object.__setattr__(self, "test_evidence_ids", test_evidence_ids)
        object.__setattr__(self, "boundary_contract_ids", _unique_sorted(self.boundary_contract_ids))
        object.__setattr__(self, "boundary_observation_ids", _unique_sorted(self.boundary_observation_ids))
        object.__setattr__(self, "runtime_node_ids", _unique_sorted(self.runtime_node_ids))
        object.__setattr__(self, "runtime_observation_ids", _unique_sorted(self.runtime_observation_ids))
        object.__setattr__(self, "payload_contract_ids", _unique_sorted(self.payload_contract_ids))
        object.__setattr__(self, "field_projection_ids", _unique_sorted(self.field_projection_ids))
        object.__setattr__(self, "source_audit_decision", str(self.source_audit_decision))
        object.__setattr__(self, "open_gap_codes", open_gap_codes)
        object.__setattr__(self, "gaps", open_gap_codes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "test_evidence_id": self.test_evidence_id,
            "status": self.status,
            "gaps": list(self.gaps),
            "code_contract_ids": list(self.code_contract_ids),
            "owner_code_contract_ids": list(self.owner_code_contract_ids),
            "code_paths": list(self.code_paths),
            "code_symbols": list(self.code_symbols),
            "test_evidence_ids": list(self.test_evidence_ids),
            "boundary_contract_ids": list(self.boundary_contract_ids),
            "boundary_observation_ids": list(self.boundary_observation_ids),
            "runtime_node_ids": list(self.runtime_node_ids),
            "runtime_observation_ids": list(self.runtime_observation_ids),
            "payload_contract_ids": list(self.payload_contract_ids),
            "field_projection_ids": list(self.field_projection_ids),
            "source_audit_decision": self.source_audit_decision,
            "open_gap_codes": list(self.open_gap_codes),
        }


@dataclass(frozen=True)
class ModelTestAlignmentReport:
    """Structured outcome of a model-test alignment review."""

    ok: bool
    model_id: str
    decision: str
    findings: tuple[ModelTestAlignmentFinding, ...] = ()
    binding_rows: tuple[ModelCodeTestBindingRow, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "binding_rows", tuple(self.binding_rows))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: model={self.model_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10, max_binding_rows: int = 10) -> str:
        lines = [
            "=== flowguard model-test alignment review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"model: {self.model_id}",
            f"decision: {self.decision}",
            f"binding_rows: {len(self.binding_rows)}",
            f"findings: {len(self.findings)}",
        ]
        for row in self.binding_rows[:max_binding_rows]:
            lines.extend(
                [
                    "",
                    f"binding: {row.status}",
                    f"obligation: {row.model_obligation_id or '(none)'}",
                    f"code_contract: {row.code_contract_id or '(none)'}",
                    f"evidence: {row.test_evidence_id or '(none)'}",
                    f"code_paths: {', '.join(row.code_paths) if row.code_paths else '(none)'}",
                    f"code_symbols: {', '.join(row.code_symbols) if row.code_symbols else '(none)'}",
                    f"tests: {', '.join(row.test_evidence_ids) if row.test_evidence_ids else '(none)'}",
                    f"source_audit: {row.source_audit_decision or '(not required)'}",
                    f"gaps: {', '.join(row.gaps) if row.gaps else '(none)'}",
                ]
            )
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"obligation: {finding.obligation_id or '(none)'}",
                    f"code_contract: {finding.code_contract_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "model_id": self.model_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "binding_rows": [row.to_dict() for row in self.binding_rows],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ContractSourceAuditFinding:
    """One conservative source-audit finding for code or test evidence."""

    code: str
    message: str
    severity: str = "blocker"
    code_contract_id: str = ""
    evidence_id: str = ""
    path: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "code_contract_id": self.code_contract_id,
            "evidence_id": self.evidence_id,
            "path": self.path,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractSourceAuditReport:
    """Structured outcome of a conservative Python source contract audit."""

    ok: bool
    decision: str
    findings: tuple[ContractSourceAuditFinding, ...] = ()
    code_evidence: tuple[PythonCodeContractEvidence, ...] = ()
    test_evidence: tuple[PythonTestAssertionEvidence, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "code_evidence", tuple(self.code_evidence))
        object.__setattr__(self, "test_evidence", tuple(self.test_evidence))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard python contract source audit ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
            f"code_evidence: {len(self.code_evidence)}",
            f"test_evidence: {len(self.test_evidence)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"code_contract: {finding.code_contract_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"path: {finding.path or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "code_evidence": [evidence.to_dict() for evidence in self.code_evidence],
            "test_evidence": [evidence.to_dict() for evidence in self.test_evidence],
            "summary": self.summary,
        }


def _report_bool(report: Any, attr: str, default: bool = False) -> bool:
    if isinstance(report, Mapping):
        return bool(report.get(attr, default))
    return bool(getattr(report, attr, default))


def _report_str(report: Any, attr: str, default: str = "") -> str:
    if isinstance(report, Mapping):
        return str(report.get(attr, default))
    return str(getattr(report, attr, default))


def _report_sequence(report: Any, attr: str) -> tuple[Any, ...]:
    if isinstance(report, Mapping):
        return tuple(report.get(attr, ()) or ())
    return tuple(getattr(report, attr, ()) or ())


def _report_to_dict(report: Any) -> Mapping[str, Any]:
    if hasattr(report, "to_dict"):
        return report.to_dict()
    if isinstance(report, Mapping):
        return dict(report)
    return {"report": to_jsonable(report)}


def _item_id(item: Any, attr: str) -> str:
    if isinstance(item, Mapping):
        return str(item.get(attr, ""))
    return str(getattr(item, attr, ""))


def _source_audit_code_ids(reports: Sequence[Any], *, ok_only: bool = True) -> set[str]:
    ids: set[str] = set()
    for report in reports:
        if ok_only and not _report_bool(report, "ok"):
            continue
        for evidence in _report_sequence(report, "code_evidence"):
            code_contract_id = _item_id(evidence, "code_contract_id")
            if code_contract_id:
                ids.add(code_contract_id)
    return ids


def _source_audit_test_ids(reports: Sequence[Any], *, ok_only: bool = True) -> set[str]:
    ids: set[str] = set()
    for report in reports:
        if ok_only and not _report_bool(report, "ok"):
            continue
        for evidence in _report_sequence(report, "test_evidence"):
            evidence_id = _item_id(evidence, "evidence_id")
            if evidence_id:
                ids.add(evidence_id)
    return ids


def _source_audit_findings(
    plan: ModelTestAlignmentPlan,
    code_contracts_by_id: Mapping[str, CodeContract],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    reports = tuple(plan.source_audit_reports)
    if not plan.require_source_audit and not reports:
        return findings
    if plan.require_source_audit and not reports:
        findings.append(
            ModelTestAlignmentFinding(
                "missing_source_audit_report",
                "model-test alignment requires source audit evidence but no source audit report was supplied",
                metadata={"model_id": plan.model_id},
            )
        )
        return findings

    for report in reports:
        if not _report_bool(report, "ok"):
            findings.append(
                ModelTestAlignmentFinding(
                    "source_audit_blocked",
                    "source audit report is not green",
                    metadata={
                        "source_audit_decision": _report_str(report, "decision"),
                        "source_audit_report": _report_to_dict(report),
                    },
                )
            )

    if not plan.require_source_audit:
        return findings

    audited_code_ids = _source_audit_code_ids(reports)
    audited_test_ids = _source_audit_test_ids(reports)
    required_code_ids = {
        contract.code_contract_id
        for contract in code_contracts_by_id.values()
        if contract.required and contract.path and contract.symbol
    }
    required_test_ids = {
        evidence.evidence_id
        for evidence in plan.test_evidence
        if evidence.path and evidence.test_name and evidence.covered_code_contracts
    }
    for code_contract_id in sorted(required_code_ids - audited_code_ids):
        findings.append(
            ModelTestAlignmentFinding(
                "source_audit_missing_code_contract_coverage",
                f"required source audit does not cover code contract {code_contract_id}",
                code_contract_id=code_contract_id,
                metadata={"required_code_contract_ids": sorted(required_code_ids)},
            )
        )
    for evidence_id in sorted(required_test_ids - audited_test_ids):
        findings.append(
            ModelTestAlignmentFinding(
                "source_audit_missing_test_evidence_coverage",
                f"required source audit does not cover test evidence {evidence_id}",
                evidence_id=evidence_id,
                metadata={"required_test_evidence_ids": sorted(required_test_ids)},
            )
        )
    return findings


def _blocker_findings(
    findings: Sequence[ModelTestAlignmentFinding],
) -> tuple[ModelTestAlignmentFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(findings: Sequence[ModelTestAlignmentFinding]) -> str:
    blockers = _blocker_findings(findings)
    if not blockers:
        return "model_test_alignment_green"
    priority = [
        ("duplicate_model_obligation", "invalid_alignment_plan"),
        ("duplicate_code_contract", "invalid_alignment_plan"),
        ("missing_code_contract", "missing_code_contract"),
        ("code_contract_missing_behavior", "code_contract_missing_behavior"),
        ("code_contract_extra_behavior", "code_contract_extra_behavior"),
        ("missing_source_audit_report", "source_audit_required"),
        ("source_audit_blocked", "source_audit_blocked"),
        ("source_audit_missing_code_contract_coverage", "source_audit_incomplete"),
        ("source_audit_missing_test_evidence_coverage", "source_audit_incomplete"),
        ("duplicate_code_boundary", "code_boundary_conformance_failed"),
        ("unknown_code_boundary_contract_reference", "code_boundary_conformance_failed"),
        ("unknown_code_boundary_observation_reference", "code_boundary_conformance_failed"),
        ("boundary_missing_runtime_evidence", "code_boundary_conformance_failed"),
        ("boundary_missing_allowed_input_evidence", "code_boundary_conformance_failed"),
        ("boundary_missing_rejected_input_evidence", "code_boundary_conformance_failed"),
        ("boundary_forbidden_input_accepted", "code_boundary_conformance_failed"),
        ("boundary_unknown_input_accepted", "code_boundary_conformance_failed"),
        ("boundary_allowed_input_rejected", "code_boundary_conformance_failed"),
        ("boundary_extra_output", "code_boundary_conformance_failed"),
        ("boundary_extra_error_path", "code_boundary_conformance_failed"),
        ("boundary_extra_state_write", "code_boundary_conformance_failed"),
        ("boundary_extra_side_effect", "code_boundary_conformance_failed"),
        ("boundary_observation_not_passing", "code_boundary_conformance_failed"),
        ("boundary_observation_stale", "code_boundary_conformance_failed"),
        ("boundary_observation_internal_path_only", "code_boundary_conformance_failed"),
        ("duplicate_artifact_payload_contract", "artifact_payload_validation_failed"),
        ("duplicate_artifact_payload_case", "artifact_payload_validation_failed"),
        ("unknown_artifact_payload_obligation_reference", "artifact_payload_validation_failed"),
        ("unknown_artifact_payload_code_contract_reference", "artifact_payload_validation_failed"),
        ("unknown_artifact_payload_contract_reference", "artifact_payload_validation_failed"),
        ("unknown_artifact_payload_case_reference", "artifact_payload_validation_failed"),
        ("artifact_payload_contract_missing_cases", "artifact_payload_validation_failed"),
        ("artifact_payload_missing_case_evidence", "artifact_payload_validation_failed"),
        ("artifact_payload_evidence_not_passing", "artifact_payload_validation_failed"),
        ("artifact_payload_evidence_stale", "artifact_payload_validation_failed"),
        ("artifact_payload_evidence_internal_path_only", "artifact_payload_validation_failed"),
        ("artifact_payload_manual_evidence_unstructured", "artifact_payload_validation_failed"),
        ("artifact_payload_evidence_missing_execution_proof", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_status_mismatch", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_not_passing", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_nonzero_exit", "artifact_payload_validation_failed"),
        ("artifact_payload_stale_proof_artifact", "artifact_payload_validation_failed"),
        ("artifact_payload_progress_only_proof_artifact", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_route_gap_visible", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_missing_result_path", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_missing_obligation", "artifact_payload_validation_failed"),
        ("artifact_payload_proof_artifact_internal_path_only", "artifact_payload_validation_failed"),
        ("artifact_payload_status_mismatch", "artifact_payload_validation_failed"),
        ("artifact_payload_output_mismatch", "artifact_payload_validation_failed"),
        ("artifact_payload_error_path_mismatch", "artifact_payload_validation_failed"),
        ("artifact_payload_state_write_mismatch", "artifact_payload_validation_failed"),
        ("artifact_payload_side_effect_mismatch", "artifact_payload_validation_failed"),
        ("artifact_payload_round_trip_missing", "artifact_payload_validation_failed"),
        ("missing_runtime_path_contracts", "runtime_path_alignment_failed"),
        ("runtime_node_missing_observation", "runtime_path_alignment_failed"),
        ("runtime_node_observation_not_current_pass", "runtime_path_alignment_failed"),
        ("runtime_node_internal_path_only", "runtime_path_alignment_failed"),
        ("runtime_path_order_mismatch", "runtime_path_alignment_failed"),
        ("runtime_path_missing_ordered_node", "runtime_path_alignment_failed"),
        ("uncontracted_runtime_node_observed", "runtime_path_alignment_failed"),
        ("missing_proof_artifact", "runtime_path_alignment_failed"),
        ("obligation_too_coarse_for_primary_evidence", "child_model_split_required"),
        ("leaf_matrix_cell_target_missing", "leaf_matrix_cell_target_required"),
        ("supporting_evidence_target_missing", "supporting_evidence_target_required"),
        ("primary_edge_role_kind_mismatch", "invalid_alignment_plan"),
        ("invalid_test_evidence_role", "invalid_alignment_plan"),
        ("closure_evidence_target_missing", "closure_evidence_target_required"),
        ("missing_counterexample_regression_test", "missing_counterexample_regression_test"),
        ("missing_known_bad_replay_test", "missing_known_bad_replay_test"),
        ("missing_closure_target_test_evidence", "missing_closure_target_test_evidence"),
        ("model_miss_closure_evidence_internal_path_only", "test_checks_internal_path_only"),
        ("missing_same_class_test_evidence", "missing_same_class_test_evidence"),
        ("missing_observed_regression_test_evidence", "missing_observed_regression_test_evidence"),
        ("missing_test_evidence", "missing_test_evidence"),
        ("missing_code_contract_test_evidence", "missing_code_contract_test_evidence"),
        ("missing_required_test_kind", "missing_required_test_kind"),
        ("duplicate_code_contract_owner", "duplicate_code_contract_owner"),
        ("duplicate_test_evidence_owner", "duplicate_test_evidence_owner"),
        ("orphan_code_contract", "orphan_code_contract"),
        ("orphan_test_evidence", "orphan_test_evidence"),
        ("unknown_model_obligation_reference", "orphan_code_contract"),
        ("unknown_code_contract_reference", "orphan_test_evidence"),
        ("unknown_obligation_reference", "orphan_test_evidence"),
        ("test_not_bound_to_code_contract", "test_not_bound_to_code_contract"),
        ("test_checks_internal_path_only", "test_checks_internal_path_only"),
        ("model_code_test_binding_mismatch", "model_code_test_binding_mismatch"),
        ("test_evidence_not_passing", "test_evidence_not_passing"),
        ("stale_test_evidence", "stale_test_evidence"),
        ("test_overclaims_model_confidence", "test_overclaims_model_confidence"),
    ]
    codes = {finding.code for finding in blockers}
    for code, decision in priority:
        if code in codes:
            return decision
    return "model_test_alignment_blocked"


def _boundary_decision_for_findings(findings: Sequence[CodeBoundaryFinding]) -> str:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        return "code_boundary_conformance_green"
    priority = (
        "duplicate_code_boundary",
        "unknown_code_boundary_contract_reference",
        "unknown_code_boundary_observation_reference",
        "boundary_missing_runtime_evidence",
        "boundary_missing_allowed_input_evidence",
        "boundary_missing_rejected_input_evidence",
        "boundary_forbidden_input_accepted",
        "boundary_unknown_input_accepted",
        "boundary_allowed_input_rejected",
        "boundary_extra_output",
        "boundary_extra_error_path",
        "boundary_extra_state_write",
        "boundary_extra_side_effect",
        "boundary_observation_not_passing",
        "boundary_observation_stale",
        "boundary_observation_internal_path_only",
    )
    codes = {finding.code for finding in blockers}
    for code in priority:
        if code in codes:
            return code
    return "code_boundary_conformance_blocked"


def _boundary_contract_index(
    boundary_contracts: Sequence[CodeBoundaryContract],
) -> tuple[dict[str, CodeBoundaryContract], list[CodeBoundaryFinding]]:
    contracts_by_id: dict[str, CodeBoundaryContract] = {}
    findings: list[CodeBoundaryFinding] = []
    for contract in boundary_contracts:
        if contract.boundary_id in contracts_by_id:
            findings.append(
                CodeBoundaryFinding(
                    "duplicate_code_boundary",
                    f"code boundary {contract.boundary_id} is declared more than once",
                    boundary_id=contract.boundary_id,
                    code_contract_id=contract.code_contract_id,
                    metadata=contract.to_dict(),
                )
            )
            continue
        contracts_by_id[contract.boundary_id] = contract
    return contracts_by_id, findings


def _observations_by_boundary(
    observations: Sequence[CodeBoundaryObservation],
) -> dict[str, list[CodeBoundaryObservation]]:
    result: dict[str, list[CodeBoundaryObservation]] = {}
    for observation in observations:
        result.setdefault(observation.boundary_id, []).append(observation)
    return result


def _current_boundary_observations(
    observations: Sequence[CodeBoundaryObservation],
) -> tuple[CodeBoundaryObservation, ...]:
    return tuple(
        observation
        for observation in observations
        if observation.has_current_pass()
        and observation.has_external_boundary_assertion()
    )


def _boundary_observation_status_findings(
    observation: CodeBoundaryObservation,
    contract: CodeBoundaryContract | None,
) -> list[CodeBoundaryFinding]:
    findings: list[CodeBoundaryFinding] = []
    code_contract_id = contract.code_contract_id if contract is not None else ""
    if observation.result_status in NON_PASSING_STATUSES:
        findings.append(
            CodeBoundaryFinding(
                "boundary_observation_not_passing",
                f"boundary observation {observation.observation_id} status is {observation.result_status}",
                boundary_id=observation.boundary_id,
                observation_id=observation.observation_id,
                code_contract_id=code_contract_id,
                metadata=observation.to_dict(),
            )
        )
    if observation.result_status not in PASSING_STATUSES | NON_PASSING_STATUSES:
        findings.append(
            CodeBoundaryFinding(
                "boundary_observation_not_passing",
                f"boundary observation {observation.observation_id} has unknown status {observation.result_status}",
                boundary_id=observation.boundary_id,
                observation_id=observation.observation_id,
                code_contract_id=code_contract_id,
                metadata=observation.to_dict(),
            )
        )
    if not observation.evidence_current:
        findings.append(
            CodeBoundaryFinding(
                "boundary_observation_stale",
                f"boundary observation {observation.observation_id} is stale",
                boundary_id=observation.boundary_id,
                observation_id=observation.observation_id,
                code_contract_id=code_contract_id,
                metadata=observation.to_dict(),
            )
        )
    if not observation.has_external_boundary_assertion():
        findings.append(
            CodeBoundaryFinding(
                "boundary_observation_internal_path_only",
                f"boundary observation {observation.observation_id} does not prove the external code boundary",
                boundary_id=observation.boundary_id,
                observation_id=observation.observation_id,
                code_contract_id=code_contract_id,
                metadata=observation.to_dict(),
            )
        )
    return findings


def _boundary_extra_field_finding(
    *,
    code: str,
    field_name: str,
    extra: Sequence[str],
    contract: CodeBoundaryContract,
    observation: CodeBoundaryObservation,
) -> CodeBoundaryFinding:
    return CodeBoundaryFinding(
        code,
        f"boundary observation {observation.observation_id} has undeclared {field_name}",
        boundary_id=contract.boundary_id,
        observation_id=observation.observation_id,
        code_contract_id=contract.code_contract_id,
        metadata={
            "field": field_name,
            "extra": sorted(str(item) for item in extra),
            "boundary": contract.to_dict(),
            "observation": observation.to_dict(),
        },
    )


def _boundary_behavior_findings(
    contract: CodeBoundaryContract,
    observation: CodeBoundaryObservation,
) -> list[CodeBoundaryFinding]:
    findings: list[CodeBoundaryFinding] = []
    allowed_inputs = _tuple_set(contract.allowed_inputs)
    rejected_inputs = _tuple_set(contract.rejected_inputs)

    if observation.input_case in rejected_inputs and observation.accepted:
        findings.append(
            CodeBoundaryFinding(
                "boundary_forbidden_input_accepted",
                f"forbidden input {observation.input_case!r} was accepted by boundary {contract.boundary_id}",
                boundary_id=contract.boundary_id,
                observation_id=observation.observation_id,
                code_contract_id=contract.code_contract_id,
                metadata={"boundary": contract.to_dict(), "observation": observation.to_dict()},
            )
        )
    elif observation.input_case in allowed_inputs and not observation.accepted:
        findings.append(
            CodeBoundaryFinding(
                "boundary_allowed_input_rejected",
                f"allowed input {observation.input_case!r} was rejected by boundary {contract.boundary_id}",
                boundary_id=contract.boundary_id,
                observation_id=observation.observation_id,
                code_contract_id=contract.code_contract_id,
                metadata={"boundary": contract.to_dict(), "observation": observation.to_dict()},
            )
        )
    elif contract.exact and allowed_inputs and observation.input_case not in allowed_inputs | rejected_inputs:
        if observation.accepted:
            findings.append(
                CodeBoundaryFinding(
                    "boundary_unknown_input_accepted",
                    f"unknown input {observation.input_case!r} was accepted by exact boundary {contract.boundary_id}",
                    boundary_id=contract.boundary_id,
                    observation_id=observation.observation_id,
                    code_contract_id=contract.code_contract_id,
                    metadata={"boundary": contract.to_dict(), "observation": observation.to_dict()},
                )
            )

    if not contract.exact:
        return findings

    if observation.observed_output:
        allowed_outputs = _tuple_set(contract.allowed_outputs)
        if observation.observed_output not in allowed_outputs:
            findings.append(
                _boundary_extra_field_finding(
                    code="boundary_extra_output",
                    field_name="output",
                    extra=(observation.observed_output,),
                    contract=contract,
                    observation=observation,
                )
            )
    if observation.observed_error_path:
        allowed_errors = _tuple_set(contract.allowed_error_paths)
        if observation.observed_error_path not in allowed_errors:
            findings.append(
                _boundary_extra_field_finding(
                    code="boundary_extra_error_path",
                    field_name="error path",
                    extra=(observation.observed_error_path,),
                    contract=contract,
                    observation=observation,
                )
            )
    extra_writes = _tuple_set(observation.observed_state_writes) - _tuple_set(contract.allowed_state_writes)
    if extra_writes:
        findings.append(
            _boundary_extra_field_finding(
                code="boundary_extra_state_write",
                field_name="state writes",
                extra=sorted(extra_writes),
                contract=contract,
                observation=observation,
            )
        )
    extra_side_effects = _tuple_set(observation.observed_side_effects) - _tuple_set(contract.allowed_side_effects)
    if extra_side_effects:
        findings.append(
            _boundary_extra_field_finding(
                code="boundary_extra_side_effect",
                field_name="side effects",
                extra=sorted(extra_side_effects),
                contract=contract,
                observation=observation,
            )
        )
    return findings


def _boundary_required_evidence_findings(
    contract: CodeBoundaryContract,
    observations: Sequence[CodeBoundaryObservation],
) -> list[CodeBoundaryFinding]:
    findings: list[CodeBoundaryFinding] = []
    current_observations = _current_boundary_observations(observations)
    if contract.required and not current_observations:
        findings.append(
            CodeBoundaryFinding(
                "boundary_missing_runtime_evidence",
                f"code boundary {contract.boundary_id} has no current external-boundary observation",
                boundary_id=contract.boundary_id,
                code_contract_id=contract.code_contract_id,
                metadata=contract.to_dict(),
            )
        )
        return findings

    current_ids = {observation.observation_id for observation in current_observations}
    for observation_id in contract.required_observation_ids:
        if observation_id not in current_ids:
            findings.append(
                CodeBoundaryFinding(
                    "boundary_missing_runtime_evidence",
                    f"code boundary {contract.boundary_id} is missing required observation {observation_id}",
                    boundary_id=contract.boundary_id,
                    code_contract_id=contract.code_contract_id,
                    metadata={"required_observation_id": observation_id, "boundary": contract.to_dict()},
                )
            )

    for input_case in contract.allowed_inputs:
        accepted = any(
            observation.input_case == input_case and observation.accepted
            for observation in current_observations
        )
        if not accepted:
            findings.append(
                CodeBoundaryFinding(
                    "boundary_missing_allowed_input_evidence",
                    f"code boundary {contract.boundary_id} has no current accepted observation for allowed input {input_case!r}",
                    boundary_id=contract.boundary_id,
                    code_contract_id=contract.code_contract_id,
                    metadata={"input_case": input_case, "boundary": contract.to_dict()},
                )
            )

    if contract.input_gate_required:
        for input_case in contract.rejected_inputs:
            rejected = any(
                observation.input_case == input_case and not observation.accepted
                for observation in current_observations
            )
            if not rejected:
                findings.append(
                    CodeBoundaryFinding(
                        "boundary_missing_rejected_input_evidence",
                        f"code boundary {contract.boundary_id} has no current rejection observation for forbidden input {input_case!r}",
                        boundary_id=contract.boundary_id,
                        code_contract_id=contract.code_contract_id,
                        metadata={"input_case": input_case, "boundary": contract.to_dict()},
                    )
                )
    return findings


def review_code_boundary_conformance(
    boundary_contracts: Sequence[CodeBoundaryContract],
    boundary_observations: Sequence[CodeBoundaryObservation],
    code_contracts: Sequence[CodeContract] = (),
) -> CodeBoundaryConformanceReport:
    """Review runtime observations against declared model-backed code boundaries."""

    boundary_contracts_by_id, findings = _boundary_contract_index(boundary_contracts)
    observations_by_boundary = _observations_by_boundary(boundary_observations)
    code_contracts_by_id = {contract.code_contract_id: contract for contract in code_contracts}

    for contract in boundary_contracts_by_id.values():
        if code_contracts_by_id and contract.code_contract_id and contract.code_contract_id not in code_contracts_by_id:
            findings.append(
                CodeBoundaryFinding(
                    "unknown_code_boundary_contract_reference",
                    f"code boundary {contract.boundary_id} references unknown code contract {contract.code_contract_id}",
                    boundary_id=contract.boundary_id,
                    code_contract_id=contract.code_contract_id,
                    metadata=contract.to_dict(),
                )
            )
        observations = tuple(observations_by_boundary.get(contract.boundary_id, ()))
        findings.extend(_boundary_required_evidence_findings(contract, observations))

    for observation in boundary_observations:
        contract = boundary_contracts_by_id.get(observation.boundary_id)
        if contract is None:
            findings.append(
                CodeBoundaryFinding(
                    "unknown_code_boundary_observation_reference",
                    f"boundary observation {observation.observation_id} references unknown boundary {observation.boundary_id}",
                    boundary_id=observation.boundary_id,
                    observation_id=observation.observation_id,
                    metadata=observation.to_dict(),
                )
            )
            continue
        findings.extend(_boundary_observation_status_findings(observation, contract))
        if observation.has_current_pass() and observation.has_external_boundary_assertion():
            findings.extend(_boundary_behavior_findings(contract, observation))

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    return CodeBoundaryConformanceReport(
        ok=not blockers,
        decision=_boundary_decision_for_findings(findings),
        findings=tuple(findings),
        checked_boundaries=len(tuple(boundary_contracts)),
        checked_observations=len(tuple(boundary_observations)),
    )


def _boundary_findings_as_alignment_findings(
    report: CodeBoundaryConformanceReport,
) -> list[ModelTestAlignmentFinding]:
    return [
        ModelTestAlignmentFinding(
            finding.code,
            finding.message,
            severity=finding.severity,
            evidence_id=finding.observation_id,
            code_contract_id=finding.code_contract_id,
            metadata={
                "boundary_id": finding.boundary_id,
                "boundary_report_decision": report.decision,
                "boundary_finding": finding.to_dict(),
            },
        )
        for finding in report.findings
    ]


def _artifact_payload_decision_for_findings(findings: Sequence[ArtifactPayloadFinding]) -> str:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        return "artifact_payload_validation_green"
    priority = (
        "duplicate_artifact_payload_contract",
        "duplicate_artifact_payload_case",
        "unknown_artifact_payload_obligation_reference",
        "unknown_artifact_payload_code_contract_reference",
        "unknown_artifact_payload_contract_reference",
        "unknown_artifact_payload_case_reference",
        "artifact_payload_contract_missing_cases",
        "artifact_payload_missing_case_evidence",
        "artifact_payload_evidence_not_passing",
        "artifact_payload_evidence_stale",
        "artifact_payload_evidence_internal_path_only",
        "artifact_payload_manual_evidence_unstructured",
        "artifact_payload_evidence_missing_execution_proof",
        "artifact_payload_proof_artifact_status_mismatch",
        "artifact_payload_proof_artifact_not_passing",
        "artifact_payload_proof_artifact_nonzero_exit",
        "artifact_payload_stale_proof_artifact",
        "artifact_payload_progress_only_proof_artifact",
        "artifact_payload_proof_artifact_route_gap_visible",
        "artifact_payload_proof_artifact_missing_result_path",
        "artifact_payload_proof_artifact_missing_obligation",
        "artifact_payload_proof_artifact_internal_path_only",
        "artifact_payload_status_mismatch",
        "artifact_payload_output_mismatch",
        "artifact_payload_error_path_mismatch",
        "artifact_payload_state_write_mismatch",
        "artifact_payload_side_effect_mismatch",
        "artifact_payload_round_trip_missing",
    )
    codes = {finding.code for finding in blockers}
    for code in priority:
        if code in codes:
            return code
    return "artifact_payload_validation_blocked"


def _payload_finding(
    code: str,
    message: str,
    *,
    contract: ArtifactPayloadContract | None = None,
    case: ArtifactPayloadCase | None = None,
    evidence: ArtifactPayloadEvidence | None = None,
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> ArtifactPayloadFinding:
    payload_contract_id = ""
    model_obligation_id = ""
    code_contract_id = ""
    if contract is not None:
        payload_contract_id = contract.payload_contract_id
        model_obligation_id = contract.model_obligation_id
        code_contract_id = contract.code_contract_id
    if evidence is not None and not payload_contract_id:
        payload_contract_id = evidence.payload_contract_id
    case_id = case.case_id if case is not None else ""
    if evidence is not None and not case_id:
        case_id = evidence.case_id
    return ArtifactPayloadFinding(
        code,
        message,
        severity=severity,
        payload_contract_id=payload_contract_id,
        case_id=case_id,
        evidence_id=evidence.evidence_id if evidence is not None else "",
        model_obligation_id=model_obligation_id,
        code_contract_id=code_contract_id,
        metadata=metadata or {},
    )


def _artifact_payload_contract_index(
    payload_contracts: Sequence[ArtifactPayloadContract],
) -> tuple[dict[str, ArtifactPayloadContract], list[ArtifactPayloadFinding]]:
    contracts_by_id: dict[str, ArtifactPayloadContract] = {}
    findings: list[ArtifactPayloadFinding] = []
    for contract in payload_contracts:
        if contract.payload_contract_id in contracts_by_id:
            findings.append(
                _payload_finding(
                    "duplicate_artifact_payload_contract",
                    f"artifact payload contract {contract.payload_contract_id} is declared more than once",
                    contract=contract,
                    metadata=contract.to_dict(),
                )
            )
            continue
        contracts_by_id[contract.payload_contract_id] = contract
    return contracts_by_id, findings


def _artifact_payload_case_index(
    contract: ArtifactPayloadContract,
) -> tuple[dict[str, ArtifactPayloadCase], list[ArtifactPayloadFinding]]:
    cases_by_id: dict[str, ArtifactPayloadCase] = {}
    findings: list[ArtifactPayloadFinding] = []
    for case in contract.cases:
        if case.case_id in cases_by_id:
            findings.append(
                _payload_finding(
                    "duplicate_artifact_payload_case",
                    f"artifact payload contract {contract.payload_contract_id} declares case {case.case_id} more than once",
                    contract=contract,
                    case=case,
                    metadata={"contract": contract.to_dict(), "case": case.to_dict()},
                )
            )
            continue
        cases_by_id[case.case_id] = case
    return cases_by_id, findings


def _artifact_payload_evidence_by_contract(
    payload_evidence: Sequence[ArtifactPayloadEvidence],
) -> dict[str, list[ArtifactPayloadEvidence]]:
    result: dict[str, list[ArtifactPayloadEvidence]] = {}
    for evidence in payload_evidence:
        result.setdefault(evidence.payload_contract_id, []).append(evidence)
    return result


def _artifact_payload_status_findings(
    evidence: ArtifactPayloadEvidence,
    contract: ArtifactPayloadContract | None,
) -> list[ArtifactPayloadFinding]:
    findings: list[ArtifactPayloadFinding] = []
    if evidence.result_status in NON_PASSING_STATUSES:
        findings.append(
            _payload_finding(
                "artifact_payload_evidence_not_passing",
                f"artifact payload evidence {evidence.evidence_id} status is {evidence.result_status}",
                contract=contract,
                evidence=evidence,
                metadata=evidence.to_dict(),
            )
        )
    if evidence.result_status not in PASSING_STATUSES | NON_PASSING_STATUSES:
        findings.append(
            _payload_finding(
                "artifact_payload_evidence_not_passing",
                f"artifact payload evidence {evidence.evidence_id} has unknown status {evidence.result_status}",
                contract=contract,
                evidence=evidence,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.evidence_current:
        findings.append(
            _payload_finding(
                "artifact_payload_evidence_stale",
                f"artifact payload evidence {evidence.evidence_id} is stale",
                contract=contract,
                evidence=evidence,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.has_external_payload_assertion():
        findings.append(
            _payload_finding(
                "artifact_payload_evidence_internal_path_only",
                f"artifact payload evidence {evidence.evidence_id} does not prove the user-visible payload contract",
                contract=contract,
                evidence=evidence,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.has_structured_manual_record():
        findings.append(
            _payload_finding(
                "artifact_payload_manual_evidence_unstructured",
                f"manual artifact payload evidence {evidence.evidence_id} lacks a structured case observation and evidence reference",
                contract=contract,
                evidence=evidence,
                metadata=evidence.to_dict(),
            )
        )
    if evidence.has_current_external_pass():
        if not evidence.evidence_ref and evidence.proof_artifact is None:
            findings.append(
                _payload_finding(
                    "artifact_payload_evidence_missing_execution_proof",
                    f"artifact payload evidence {evidence.evidence_id} lacks a concrete execution proof for the real payload surface",
                    contract=contract,
                    evidence=evidence,
                    metadata=evidence.to_dict(),
                )
            )
        if evidence.proof_artifact is not None:
            required_obligations = ()
            if contract is not None and contract.model_obligation_id:
                required_obligations = (contract.model_obligation_id,)
            for code, message in proof_artifact_gap_codes(
                evidence.proof_artifact,
                declared_status=evidence.result_status,
                required_obligation_ids=required_obligations,
                require_result_path=True,
                require_external_scope=True,
            ):
                findings.append(
                    _payload_finding(
                        f"artifact_payload_{code}",
                        message,
                        contract=contract,
                        evidence=evidence,
                        metadata=evidence.to_dict(),
                    )
                )
    return findings


def _payload_sequence_mismatch_finding(
    *,
    code: str,
    field_name: str,
    expected: Sequence[str],
    observed: Sequence[str],
    contract: ArtifactPayloadContract,
    case: ArtifactPayloadCase,
    evidence: ArtifactPayloadEvidence,
) -> ArtifactPayloadFinding:
    return _payload_finding(
        code,
        f"artifact payload evidence {evidence.evidence_id} has mismatched {field_name}",
        contract=contract,
        case=case,
        evidence=evidence,
        metadata={
            "field": field_name,
            "expected": list(expected),
            "observed": list(observed),
            "contract": contract.to_dict(),
            "case": case.to_dict(),
            "evidence": evidence.to_dict(),
        },
    )


def _artifact_payload_behavior_findings(
    contract: ArtifactPayloadContract,
    case: ArtifactPayloadCase,
    evidence: ArtifactPayloadEvidence,
) -> list[ArtifactPayloadFinding]:
    findings: list[ArtifactPayloadFinding] = []
    if case.expected_status and evidence.observed_status != case.expected_status:
        findings.append(
            _payload_finding(
                "artifact_payload_status_mismatch",
                f"artifact payload evidence {evidence.evidence_id} observed status {evidence.observed_status!r}, expected {case.expected_status!r}",
                contract=contract,
                case=case,
                evidence=evidence,
                metadata={"contract": contract.to_dict(), "case": case.to_dict(), "evidence": evidence.to_dict()},
            )
        )
    if case.expected_output and evidence.observed_output != case.expected_output:
        findings.append(
            _payload_finding(
                "artifact_payload_output_mismatch",
                f"artifact payload evidence {evidence.evidence_id} observed output {evidence.observed_output!r}, expected {case.expected_output!r}",
                contract=contract,
                case=case,
                evidence=evidence,
                metadata={"contract": contract.to_dict(), "case": case.to_dict(), "evidence": evidence.to_dict()},
            )
        )
    elif contract.exact and evidence.observed_output and not case.expected_output:
        findings.append(
            _payload_finding(
                "artifact_payload_output_mismatch",
                f"artifact payload evidence {evidence.evidence_id} produced undeclared output",
                contract=contract,
                case=case,
                evidence=evidence,
                metadata={"contract": contract.to_dict(), "case": case.to_dict(), "evidence": evidence.to_dict()},
            )
        )
    if case.expected_error_path and evidence.observed_error_path != case.expected_error_path:
        findings.append(
            _payload_finding(
                "artifact_payload_error_path_mismatch",
                f"artifact payload evidence {evidence.evidence_id} observed error path {evidence.observed_error_path!r}, expected {case.expected_error_path!r}",
                contract=contract,
                case=case,
                evidence=evidence,
                metadata={"contract": contract.to_dict(), "case": case.to_dict(), "evidence": evidence.to_dict()},
            )
        )
    elif contract.exact and evidence.observed_error_path and not case.expected_error_path:
        findings.append(
            _payload_finding(
                "artifact_payload_error_path_mismatch",
                f"artifact payload evidence {evidence.evidence_id} produced undeclared error path",
                contract=contract,
                case=case,
                evidence=evidence,
                metadata={"contract": contract.to_dict(), "case": case.to_dict(), "evidence": evidence.to_dict()},
            )
        )
    expected_writes = _tuple_set(case.expected_state_writes)
    observed_writes = _tuple_set(evidence.observed_state_writes)
    if expected_writes - observed_writes or (contract.exact and observed_writes - expected_writes):
        findings.append(
            _payload_sequence_mismatch_finding(
                code="artifact_payload_state_write_mismatch",
                field_name="state writes",
                expected=sorted(expected_writes),
                observed=sorted(observed_writes),
                contract=contract,
                case=case,
                evidence=evidence,
            )
        )
    expected_side_effects = _tuple_set(case.expected_side_effects)
    observed_side_effects = _tuple_set(evidence.observed_side_effects)
    if expected_side_effects - observed_side_effects or (contract.exact and observed_side_effects - expected_side_effects):
        findings.append(
            _payload_sequence_mismatch_finding(
                code="artifact_payload_side_effect_mismatch",
                field_name="side effects",
                expected=sorted(expected_side_effects),
                observed=sorted(observed_side_effects),
                contract=contract,
                case=case,
                evidence=evidence,
            )
        )
    if case.round_trip_required and not evidence.round_trip_ok:
        findings.append(
            _payload_finding(
                "artifact_payload_round_trip_missing",
                f"artifact payload evidence {evidence.evidence_id} does not prove required round-trip behavior",
                contract=contract,
                case=case,
                evidence=evidence,
                metadata={"contract": contract.to_dict(), "case": case.to_dict(), "evidence": evidence.to_dict()},
            )
        )
    return findings


def _artifact_payload_required_case_findings(
    contract: ArtifactPayloadContract,
    cases_by_id: Mapping[str, ArtifactPayloadCase],
    evidence_items: Sequence[ArtifactPayloadEvidence],
) -> list[ArtifactPayloadFinding]:
    findings: list[ArtifactPayloadFinding] = []
    if contract.required and not contract.cases:
        findings.append(
            _payload_finding(
                "artifact_payload_contract_missing_cases",
                f"artifact payload contract {contract.payload_contract_id} declares no payload cases",
                contract=contract,
                metadata=contract.to_dict(),
            )
        )
        return findings

    current_external_passes = tuple(
        evidence
        for evidence in evidence_items
        if evidence.has_current_external_pass()
    )
    current_case_ids = {evidence.case_id for evidence in current_external_passes}
    for case in cases_by_id.values():
        if not case.required:
            continue
        if case.case_id not in current_case_ids:
            severity = "warning" if contract.allow_scoped_cases else "blocker"
            findings.append(
                _payload_finding(
                    "artifact_payload_missing_case_evidence",
                    f"artifact payload case {case.case_id} has no current external passing evidence",
                    contract=contract,
                    case=case,
                    severity=severity,
                    metadata={"contract": contract.to_dict(), "case": case.to_dict()},
                )
            )
    return findings


def review_artifact_payload_validation(
    payload_contracts: Sequence[ArtifactPayloadContract],
    payload_evidence: Sequence[ArtifactPayloadEvidence],
    code_contracts: Sequence[CodeContract] = (),
    model_obligations: Sequence[ModelObligation] = (),
) -> ArtifactPayloadValidationReport:
    """Review import/export or AI-work-package payload evidence against declared cases."""

    contracts_by_id, findings = _artifact_payload_contract_index(payload_contracts)
    evidence_by_contract = _artifact_payload_evidence_by_contract(payload_evidence)
    code_contracts_by_id = {contract.code_contract_id: contract for contract in code_contracts}
    obligations_by_id = {obligation.obligation_id: obligation for obligation in model_obligations}
    checked_cases = 0
    case_index_by_contract: dict[str, dict[str, ArtifactPayloadCase]] = {}

    for contract in contracts_by_id.values():
        cases_by_id, case_findings = _artifact_payload_case_index(contract)
        checked_cases += len(contract.cases)
        case_index_by_contract[contract.payload_contract_id] = cases_by_id
        findings.extend(case_findings)
        if (
            obligations_by_id
            and contract.model_obligation_id
            and contract.model_obligation_id not in obligations_by_id
        ):
            findings.append(
                _payload_finding(
                    "unknown_artifact_payload_obligation_reference",
                    f"artifact payload contract {contract.payload_contract_id} references unknown model obligation {contract.model_obligation_id}",
                    contract=contract,
                    metadata=contract.to_dict(),
                )
            )
        if (
            code_contracts_by_id
            and contract.code_contract_id
            and contract.code_contract_id not in code_contracts_by_id
        ):
            findings.append(
                _payload_finding(
                    "unknown_artifact_payload_code_contract_reference",
                    f"artifact payload contract {contract.payload_contract_id} references unknown code contract {contract.code_contract_id}",
                    contract=contract,
                    metadata=contract.to_dict(),
                )
            )
        findings.extend(
            _artifact_payload_required_case_findings(
                contract,
                cases_by_id,
                evidence_by_contract.get(contract.payload_contract_id, ()),
            )
        )

    for evidence in payload_evidence:
        contract = contracts_by_id.get(evidence.payload_contract_id)
        if contract is None:
            findings.append(
                _payload_finding(
                    "unknown_artifact_payload_contract_reference",
                    f"artifact payload evidence {evidence.evidence_id} references unknown contract {evidence.payload_contract_id}",
                    evidence=evidence,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        cases_by_id = case_index_by_contract.get(contract.payload_contract_id, {})
        case = cases_by_id.get(evidence.case_id)
        if case is None:
            findings.append(
                _payload_finding(
                    "unknown_artifact_payload_case_reference",
                    f"artifact payload evidence {evidence.evidence_id} references unknown case {evidence.case_id}",
                    contract=contract,
                    evidence=evidence,
                    metadata={"contract": contract.to_dict(), "evidence": evidence.to_dict()},
                )
            )
            findings.extend(_artifact_payload_status_findings(evidence, contract))
            continue
        findings.extend(_artifact_payload_status_findings(evidence, contract))
        if evidence.has_current_external_pass():
            findings.extend(_artifact_payload_behavior_findings(contract, case, evidence))

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    return ArtifactPayloadValidationReport(
        ok=not blockers,
        decision=_artifact_payload_decision_for_findings(findings),
        findings=tuple(findings),
        checked_contracts=len(tuple(payload_contracts)),
        checked_cases=checked_cases,
        checked_evidence=len(tuple(payload_evidence)),
    )


def _artifact_payload_findings_as_alignment_findings(
    report: ArtifactPayloadValidationReport,
) -> list[ModelTestAlignmentFinding]:
    return [
        ModelTestAlignmentFinding(
            finding.code,
            finding.message,
            severity=finding.severity,
            obligation_id=finding.model_obligation_id,
            evidence_id=finding.evidence_id,
            code_contract_id=finding.code_contract_id,
            metadata={
                "payload_contract_id": finding.payload_contract_id,
                "payload_case_id": finding.case_id,
                "artifact_payload_report_decision": report.decision,
                "artifact_payload_finding": finding.to_dict(),
            },
        )
        for finding in report.findings
    ]


def _runtime_path_contracts_for_plan(plan: ModelTestAlignmentPlan) -> tuple[RuntimeNodeContract, ...]:
    contracts = list(plan.runtime_node_contracts)
    declared = {
        (contract.node_id, contract.model_obligation_id)
        for contract in contracts
    }
    for obligation in plan.obligations:
        for node_id in obligation.required_runtime_node_ids:
            key = (node_id, obligation.obligation_id)
            if key in declared:
                continue
            contracts.append(
                RuntimeNodeContract(
                    node_id=node_id,
                    model_id=plan.model_id,
                    model_obligation_id=obligation.obligation_id,
                    required=True,
                )
            )
            declared.add(key)
    return tuple(contracts)


def _runtime_path_metadata_value(
    metadata: Mapping[str, Any],
    key: str,
) -> str:
    if key in metadata:
        return str(metadata[key])
    contract = metadata.get("contract")
    if isinstance(contract, Mapping) and key in contract:
        return str(contract[key])
    return ""


def _runtime_path_findings_as_alignment_findings(
    runtime_report,
) -> list[ModelTestAlignmentFinding]:
    return [
        ModelTestAlignmentFinding(
            finding.code,
            finding.message,
            severity=finding.severity,
            obligation_id=_runtime_path_metadata_value(finding.metadata, "model_obligation_id"),
            evidence_id=finding.evidence_id or finding.observation_id,
            code_contract_id=_runtime_path_metadata_value(finding.metadata, "code_contract_id"),
            metadata={
                "runtime_path_report_decision": runtime_report.decision,
                "runtime_path_finding": finding.to_dict(),
            },
        )
        for finding in runtime_report.findings
    ]


def _family_findings_as_alignment_findings(
    findings: Sequence[ObligationFamilyParityFinding],
) -> list[ModelTestAlignmentFinding]:
    return [
        ModelTestAlignmentFinding(
            finding.code,
            finding.message,
            severity=finding.severity,
            evidence_id=finding.evidence_id,
            metadata={
                "family_id": finding.family_id,
                "member_id": finding.member_id,
                "mechanism_id": finding.mechanism_id,
                "family_finding": finding.to_dict(),
            },
        )
        for finding in findings
    ]


def _field_lifecycle_projection_rows(plan: ModelTestAlignmentPlan) -> tuple[Any, ...]:
    rows: list[Any] = list(plan.field_lifecycle_projections)
    for report in plan.field_lifecycle_reports:
        rows.extend(getattr(report, "projections", ()))
    return tuple(rows)


def _field_lifecycle_findings(plan: ModelTestAlignmentPlan) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    for report in plan.field_lifecycle_reports:
        report_ok = bool(getattr(report, "ok", False))
        report_decision = str(getattr(report, "decision", ""))
        for finding in getattr(report, "findings", ()):
            severity = str(getattr(finding, "severity", "blocker"))
            if not report_ok and severity in {"gap", "blocker"}:
                severity = "blocker"
            elif severity == "gap":
                severity = "warning"
            metadata = finding.to_dict() if hasattr(finding, "to_dict") else to_jsonable(finding)
            obligation_id = ""
            field_id = str(getattr(finding, "field_id", ""))
            if field_id:
                obligation_id = f"field:{field_id}"
            findings.append(
                ModelTestAlignmentFinding(
                    f"field_lifecycle_{getattr(finding, 'code', 'finding')}",
                    str(getattr(finding, "message", "field lifecycle finding")),
                    severity=severity,
                    obligation_id=obligation_id,
                    metadata={
                        "field_lifecycle_decision": report_decision,
                        "field_lifecycle_finding": metadata,
                    },
                )
            )
    return findings


def _plan_with_field_lifecycle_projections(plan: ModelTestAlignmentPlan) -> ModelTestAlignmentPlan:
    projections = _field_lifecycle_projection_rows(plan)
    if not projections:
        return plan

    obligations = list(plan.obligations)
    code_contracts = list(plan.code_contracts)
    obligation_ids = {obligation.obligation_id for obligation in obligations}
    code_contract_ids = {contract.code_contract_id for contract in code_contracts}
    for projection in projections:
        to_obligation = getattr(projection, "to_model_obligation", None)
        if callable(to_obligation):
            obligation = to_obligation()
            if obligation is not None and obligation.obligation_id not in obligation_ids:
                obligations.append(obligation)
                obligation_ids.add(obligation.obligation_id)
        to_contract = getattr(projection, "to_code_contract", None)
        if callable(to_contract):
            contract = to_contract()
            if contract is not None and contract.code_contract_id not in code_contract_ids:
                code_contracts.append(contract)
                code_contract_ids.add(contract.code_contract_id)

    return replace(
        plan,
        obligations=tuple(obligations),
        code_contracts=tuple(code_contracts),
    )


def _obligation_index(plan: ModelTestAlignmentPlan) -> tuple[dict[str, ModelObligation], list[ModelTestAlignmentFinding]]:
    obligations_by_id: dict[str, ModelObligation] = {}
    findings: list[ModelTestAlignmentFinding] = []
    for obligation in plan.obligations:
        if obligation.obligation_id in obligations_by_id:
            findings.append(
                ModelTestAlignmentFinding(
                    "duplicate_model_obligation",
                    f"model obligation {obligation.obligation_id} is declared more than once",
                    obligation_id=obligation.obligation_id,
                    metadata=obligation.to_dict(),
                )
            )
            continue
        obligations_by_id[obligation.obligation_id] = obligation
    return obligations_by_id, findings


def _code_contract_index(plan: ModelTestAlignmentPlan) -> tuple[dict[str, CodeContract], list[ModelTestAlignmentFinding]]:
    contracts_by_id: dict[str, CodeContract] = {}
    findings: list[ModelTestAlignmentFinding] = []
    for contract in plan.code_contracts:
        if contract.code_contract_id in contracts_by_id:
            findings.append(
                ModelTestAlignmentFinding(
                    "duplicate_code_contract",
                    f"code contract {contract.code_contract_id} is declared more than once",
                    metadata=contract.to_dict(),
                    code_contract_id=contract.code_contract_id,
                )
            )
            continue
        contracts_by_id[contract.code_contract_id] = contract
    return contracts_by_id, findings


def _code_contracts_by_obligation(
    code_contracts_by_id: Mapping[str, CodeContract],
    obligations_by_id: Mapping[str, ModelObligation],
) -> dict[str, list[CodeContract]]:
    result: dict[str, list[CodeContract]] = {obligation_id: [] for obligation_id in obligations_by_id}
    for contract in code_contracts_by_id.values():
        if not contract.is_owner():
            continue
        for obligation_id in contract.implements_obligations:
            if obligation_id in result:
                result[obligation_id].append(contract)
    return result


def _contract_field_delta(
    obligation: ModelObligation,
    contract: CodeContract,
    field_name: str,
) -> tuple[set[str], set[str]]:
    expected = _tuple_set(getattr(obligation, field_name))
    actual = _tuple_set(getattr(contract, field_name))
    missing = expected - actual
    extra = actual - expected if obligation.exact_external_contract else set()
    return missing, extra


def _code_contract_findings(
    plan: ModelTestAlignmentPlan,
    obligations_by_id: Mapping[str, ModelObligation],
    code_contracts_by_id: Mapping[str, CodeContract],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    contracts_by_obligation = _code_contracts_by_obligation(code_contracts_by_id, obligations_by_id)

    for contract in code_contracts_by_id.values():
        if not contract.implements_obligations and contract.is_owner():
            severity = "warning" if plan.allow_orphan_code_contracts else "blocker"
            findings.append(
                ModelTestAlignmentFinding(
                    "orphan_code_contract",
                    f"code contract {contract.code_contract_id} is not bound to any model obligation",
                    severity=severity,
                    metadata=contract.to_dict(),
                    code_contract_id=contract.code_contract_id,
                )
            )
        for obligation_id in contract.implements_obligations:
            if obligation_id not in obligations_by_id:
                severity = "warning" if plan.allow_orphan_code_contracts else "blocker"
                findings.append(
                    ModelTestAlignmentFinding(
                        "unknown_model_obligation_reference",
                        f"code contract {contract.code_contract_id} references unknown model obligation {obligation_id}",
                        severity=severity,
                        obligation_id=obligation_id,
                        metadata=contract.to_dict(),
                        code_contract_id=contract.code_contract_id,
                    )
                )

    for obligation_id, obligation in obligations_by_id.items():
        owner_contracts = tuple(contracts_by_obligation.get(obligation_id, ()))
        if obligation.required and not owner_contracts:
            findings.append(
                ModelTestAlignmentFinding(
                    "missing_code_contract",
                    f"model obligation {obligation_id} has no code external contract owner",
                    obligation_id=obligation_id,
                    metadata=obligation.to_dict(),
                )
            )
            continue

        if len(owner_contracts) > 1 and not obligation.allow_shared_implementation:
            findings.append(
                ModelTestAlignmentFinding(
                    "duplicate_code_contract_owner",
                    f"model obligation {obligation_id} has multiple code contract owners",
                    obligation_id=obligation_id,
                    metadata={
                        "obligation": obligation.to_dict(),
                        "code_contract_ids": [contract.code_contract_id for contract in owner_contracts],
                    },
                )
            )

        for contract in owner_contracts:
            for field_name in (
                "external_inputs",
                "external_outputs",
                "state_reads",
                "state_writes",
                "side_effects",
                "error_paths",
            ):
                missing, extra = _contract_field_delta(obligation, contract, field_name)
                if missing:
                    findings.append(
                        ModelTestAlignmentFinding(
                            "code_contract_missing_behavior",
                            f"code contract {contract.code_contract_id} is missing {field_name} required by model obligation {obligation_id}",
                            obligation_id=obligation_id,
                            metadata={
                                "field": field_name,
                                "missing": sorted(missing),
                                "obligation": obligation.to_dict(),
                                "code_contract": contract.to_dict(),
                            },
                            code_contract_id=contract.code_contract_id,
                        )
                    )
                if extra:
                    findings.append(
                        ModelTestAlignmentFinding(
                            "code_contract_extra_behavior",
                            f"code contract {contract.code_contract_id} has extra {field_name} not declared by model obligation {obligation_id}",
                            obligation_id=obligation_id,
                            metadata={
                                "field": field_name,
                                "extra": sorted(extra),
                                "obligation": obligation.to_dict(),
                                "code_contract": contract.to_dict(),
                            },
                            code_contract_id=contract.code_contract_id,
                        )
                    )
    return findings


def _evidence_findings(
    plan: ModelTestAlignmentPlan,
    obligations_by_id: Mapping[str, ModelObligation],
    code_contracts_by_id: Mapping[str, CodeContract],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    for evidence in plan.test_evidence:
        if evidence.evidence_role not in ALLOWED_TEST_EVIDENCE_ROLES:
            findings.append(
                ModelTestAlignmentFinding(
                    "invalid_test_evidence_role",
                    f"test evidence {evidence.evidence_id} has unknown evidence role {evidence.evidence_role}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.evidence_role == TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH
            and evidence.test_kind != TEST_KIND_EDGE_PATH
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "primary_edge_role_kind_mismatch",
                    f"test evidence {evidence.evidence_id} is marked primary_edge_path but its test kind is {evidence.test_kind}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.evidence_role == TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL
            and not evidence.evidence_target_id
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "leaf_matrix_cell_target_missing",
                    f"leaf matrix-cell evidence {evidence.evidence_id} must name the cell it proves",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.evidence_role == TEST_EVIDENCE_ROLE_TRANSITION_CELL
            and not evidence.evidence_target_id
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "transition_cell_target_missing",
                    f"transition-cell evidence {evidence.evidence_id} must name the transition cell it proves",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.evidence_role == TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT
            and not evidence.evidence_target_id
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "supporting_evidence_target_missing",
                    f"supporting evidence {evidence.evidence_id} must name the child obligation, code contract, or boundary it supports",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.closure_evidence_role in TARGET_AWARE_CLOSURE_ROLES
            and not evidence.evidence_target_id
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "closure_evidence_target_missing",
                    f"test evidence {evidence.evidence_id} must name the counterexample or known-bad target it closes",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.closure_evidence_role
            and evidence.assertion_scope
            in {TEST_ASSERTION_SCOPE_INTERNAL_PATH, TEST_ASSERTION_SCOPE_UNKNOWN}
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "model_miss_closure_evidence_internal_path_only",
                    f"closure evidence {evidence.evidence_id} does not prove the external behavior boundary",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if not evidence.covered_obligations:
            severity = "warning" if plan.allow_orphan_tests else "blocker"
            findings.append(
                ModelTestAlignmentFinding(
                    "orphan_test_evidence",
                    f"test evidence {evidence.evidence_id} is not bound to any model obligation",
                    severity=severity,
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        for obligation_id in evidence.covered_obligations:
            obligation = obligations_by_id.get(obligation_id)
            if obligation is None:
                severity = "warning" if plan.allow_orphan_tests else "blocker"
                findings.append(
                    ModelTestAlignmentFinding(
                        "unknown_obligation_reference",
                        f"test evidence {evidence.evidence_id} references unknown model obligation {obligation_id}",
                        severity=severity,
                        obligation_id=obligation_id,
                        evidence_id=evidence.evidence_id,
                        metadata=evidence.to_dict(),
                    )
                )
            elif not _transition_cell_target_matches(evidence, obligation):
                findings.append(
                    ModelTestAlignmentFinding(
                        "transition_cell_target_mismatch",
                        f"transition-cell evidence {evidence.evidence_id} targets {evidence.evidence_target_id!r} but covers transition obligation {obligation_id}",
                        obligation_id=obligation_id,
                        evidence_id=evidence.evidence_id,
                        metadata={
                            "evidence": evidence.to_dict(),
                            "obligation": obligation.to_dict(),
                        },
                    )
                )
        for code_contract_id in evidence.covered_code_contracts:
            if code_contract_id not in code_contracts_by_id:
                severity = "warning" if plan.allow_orphan_tests else "blocker"
                findings.append(
                    ModelTestAlignmentFinding(
                        "unknown_code_contract_reference",
                        f"test evidence {evidence.evidence_id} references unknown code contract {code_contract_id}",
                        severity=severity,
                        evidence_id=evidence.evidence_id,
                        metadata=evidence.to_dict(),
                        code_contract_id=code_contract_id,
                    )
                )
        if evidence.covered_obligations and not evidence.covered_code_contracts:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_not_bound_to_code_contract",
                    f"test evidence {evidence.evidence_id} covers model obligations but no code external contract",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if (
            evidence.covered_code_contracts
            and evidence.assertion_scope
            in {TEST_ASSERTION_SCOPE_INTERNAL_PATH, TEST_ASSERTION_SCOPE_UNKNOWN}
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "test_checks_internal_path_only",
                    f"test evidence {evidence.evidence_id} does not prove the external code contract",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if evidence.covered_obligations and evidence.covered_code_contracts:
            covered_obligations = set(evidence.covered_obligations)
            implemented_by_contract: dict[str, set[str]] = {}
            for code_contract_id in evidence.covered_code_contracts:
                contract = code_contracts_by_id.get(code_contract_id)
                if contract is not None:
                    implemented_by_contract[code_contract_id] = set(contract.implements_obligations)
            implemented_obligations = set().union(*implemented_by_contract.values()) if implemented_by_contract else set()
            if implemented_obligations and not (covered_obligations & implemented_obligations):
                findings.append(
                    ModelTestAlignmentFinding(
                        "model_code_test_binding_mismatch",
                        f"test evidence {evidence.evidence_id} binds model obligations and code contracts that do not overlap",
                        evidence_id=evidence.evidence_id,
                        metadata={
                            "covered_obligations": sorted(covered_obligations),
                            "implemented_obligations": sorted(implemented_obligations),
                            "evidence": evidence.to_dict(),
                        },
                    )
                )
            for obligation_id in covered_obligations:
                if obligation_id not in obligations_by_id:
                    continue
                implementing_contract_ids = tuple(
                    code_contract_id
                    for code_contract_id, implemented in implemented_by_contract.items()
                    if obligation_id in implemented
                )
                if implemented_by_contract and not implementing_contract_ids:
                    findings.append(
                        ModelTestAlignmentFinding(
                            "model_code_test_binding_mismatch",
                            f"test evidence {evidence.evidence_id} covers model obligation {obligation_id} but none of its covered code contracts implement it",
                            obligation_id=obligation_id,
                            evidence_id=evidence.evidence_id,
                            metadata={
                                "covered_obligation": obligation_id,
                                "covered_code_contracts": list(evidence.covered_code_contracts),
                                "implemented_by_contract": {
                                    key: sorted(value) for key, value in implemented_by_contract.items()
                                },
                                "evidence": evidence.to_dict(),
                            },
                        )
                    )
        if evidence.result_status in NON_PASSING_STATUSES:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_evidence_not_passing",
                    f"test evidence {evidence.evidence_id} status is {evidence.result_status}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if evidence.result_status not in PASSING_STATUSES | NON_PASSING_STATUSES:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_evidence_not_passing",
                    f"test evidence {evidence.evidence_id} has unknown status {evidence.result_status}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if not evidence.evidence_current:
            findings.append(
                ModelTestAlignmentFinding(
                    "stale_test_evidence",
                    f"test evidence {evidence.evidence_id} is stale",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if evidence.result_reused or evidence.reuse_ticket is not None:
            for code, message in test_result_reuse_gap_codes(
                evidence.reuse_ticket,
                expected_evidence_id=evidence.evidence_id,
                required_obligation_ids=evidence.covered_obligations,
            ):
                findings.append(
                    ModelTestAlignmentFinding(
                        code,
                        message,
                        evidence_id=evidence.evidence_id,
                        metadata=evidence.to_dict(),
                    )
                )
            for code, message in proof_artifact_gap_codes(
                evidence.proof_artifact,
                declared_status=evidence.result_status,
                required_obligation_ids=evidence.covered_obligations,
                require_result_path=True,
                require_fingerprints=True,
                require_external_scope=bool(evidence.covered_code_contracts),
            ):
                findings.append(
                    ModelTestAlignmentFinding(
                        f"test_reuse_{code}",
                        message,
                        evidence_id=evidence.evidence_id,
                        metadata=evidence.to_dict(),
                    )
                )
        if plan.require_proof_artifacts:
            for code, message in proof_artifact_gap_codes(
                evidence.proof_artifact,
                declared_status=evidence.result_status,
                required_obligation_ids=evidence.covered_obligations,
                require_result_path=True,
                require_fingerprints=True,
                require_external_scope=bool(evidence.covered_code_contracts),
            ):
                findings.append(
                    ModelTestAlignmentFinding(
                        code.replace("proof_artifact", "test_proof_artifact"),
                        message,
                        evidence_id=evidence.evidence_id,
                        metadata=evidence.to_dict(),
                    )
                )
        if evidence.overclaims_model_confidence:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_overclaims_model_confidence",
                    f"test evidence {evidence.evidence_id} claims more model confidence than its obligation bindings prove",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
    return findings


def _passing_evidence_by_obligation(
    plan: ModelTestAlignmentPlan,
    obligations_by_id: Mapping[str, ModelObligation],
) -> dict[str, list[TestEvidence]]:
    result: dict[str, list[TestEvidence]] = {obligation_id: [] for obligation_id in obligations_by_id}
    for evidence in plan.test_evidence:
        if not evidence.has_current_pass():
            continue
        for obligation_id in evidence.covered_obligations:
            if obligation_id in result:
                result[obligation_id].append(evidence)
    return result


def _passing_external_evidence_by_code_contract(
    plan: ModelTestAlignmentPlan,
    code_contracts_by_id: Mapping[str, CodeContract],
) -> dict[str, list[TestEvidence]]:
    result: dict[str, list[TestEvidence]] = {code_contract_id: [] for code_contract_id in code_contracts_by_id}
    for evidence in plan.test_evidence:
        if not evidence.has_current_pass() or not evidence.has_external_contract_assertion():
            continue
        for code_contract_id in evidence.covered_code_contracts:
            if code_contract_id in result:
                result[code_contract_id].append(evidence)
    return result


def _is_primary_coverage_evidence(evidence: TestEvidence) -> bool:
    return evidence.evidence_role in PRIMARY_TEST_EVIDENCE_ROLES


def _is_primary_edge_evidence(evidence: TestEvidence) -> bool:
    return (
        evidence.evidence_role == TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH
        or (
            evidence.evidence_role == TEST_EVIDENCE_ROLE_PRIMARY
            and evidence.test_kind == TEST_KIND_EDGE_PATH
        )
    )


def _counts_as_obligation_coverage(evidence: TestEvidence) -> bool:
    return evidence.evidence_role in PRIMARY_TEST_EVIDENCE_ROLES | {
        TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL,
        TEST_EVIDENCE_ROLE_TRANSITION_CELL,
    }


def _expected_transition_cell_ids(obligation: ModelObligation) -> tuple[str, ...]:
    if obligation.obligation_type != "transition_coverage":
        return ()
    obligation_id = obligation.obligation_id
    if ":" in obligation_id:
        return (obligation_id.split(":", 1)[1], obligation_id)
    return (obligation_id,)


def _transition_cell_target_matches(evidence: TestEvidence, obligation: ModelObligation) -> bool:
    if evidence.evidence_role != TEST_EVIDENCE_ROLE_TRANSITION_CELL:
        return True
    expected = _expected_transition_cell_ids(obligation)
    if not expected:
        return True
    return evidence.evidence_target_id in expected


def _evidence_binds_obligation_to_code_contract(
    evidence: TestEvidence,
    obligation_id: str,
    obligation: ModelObligation,
    code_contracts_by_id: Mapping[str, CodeContract],
) -> bool:
    if not evidence.covered_code_contracts or not evidence.has_external_contract_assertion():
        return False
    if not _transition_cell_target_matches(evidence, obligation):
        return False
    for code_contract_id in evidence.covered_code_contracts:
        contract = code_contracts_by_id.get(code_contract_id)
        if contract is not None and obligation_id in contract.implements_obligations:
            return True
    return False


def _field_projection_id(projection: Any) -> str:
    for attr in ("projection_id", "field_id", "id"):
        value = getattr(projection, attr, "")
        if value:
            return str(value)
    if isinstance(projection, Mapping):
        for key in ("projection_id", "field_id", "id"):
            value = projection.get(key)
            if value:
                return str(value)
    return ""


def _binding_source_audit_decision(
    plan: ModelTestAlignmentPlan,
    contract_ids: Sequence[str],
    evidence_ids: Sequence[str],
) -> str:
    reports = tuple(plan.source_audit_reports)
    if not reports:
        return "missing_source_audit_report" if plan.require_source_audit else ""
    if any(not _report_bool(report, "ok") for report in reports):
        return "source_audit_blocked"
    audited_code_ids = _source_audit_code_ids(reports)
    audited_test_ids = _source_audit_test_ids(reports)
    missing_code = set(contract_ids) - audited_code_ids
    missing_test = set(evidence_ids) - audited_test_ids
    if missing_code or missing_test:
        return "source_audit_incomplete" if plan.require_source_audit else "source_audit_partial"
    return "source_audit_green"


def _binding_gap_codes(
    findings: Sequence[ModelTestAlignmentFinding],
    *,
    obligation_id: str,
    contract_ids: Sequence[str],
    evidence_ids: Sequence[str],
) -> tuple[str, ...]:
    contract_id_set = set(contract_ids)
    evidence_id_set = set(evidence_ids)
    codes: list[str] = []
    for finding in findings:
        if finding.severity != "blocker":
            continue
        if finding.obligation_id and finding.obligation_id == obligation_id:
            codes.append(finding.code)
        elif finding.code_contract_id and finding.code_contract_id in contract_id_set:
            codes.append(finding.code)
        elif finding.evidence_id and finding.evidence_id in evidence_id_set:
            codes.append(finding.code)
    return _unique_sorted(codes)


def _binding_rows(
    plan: ModelTestAlignmentPlan,
    obligations_by_id: Mapping[str, ModelObligation],
    code_contracts_by_id: Mapping[str, CodeContract],
    passing_by_obligation: Mapping[str, Sequence[TestEvidence]],
    findings: Sequence[ModelTestAlignmentFinding],
) -> tuple[ModelCodeTestBindingRow, ...]:
    contracts_by_obligation = _code_contracts_by_obligation(code_contracts_by_id, obligations_by_id)
    rows: list[ModelCodeTestBindingRow] = []
    field_projections = _field_lifecycle_projection_rows(plan)
    for obligation_id, obligation in obligations_by_id.items():
        if not obligation.required:
            continue
        owner_contracts = tuple(contracts_by_obligation.get(obligation_id, ()))
        if not owner_contracts:
            gap_codes = _binding_gap_codes(
                findings,
                obligation_id=obligation_id,
                contract_ids=(),
                evidence_ids=(),
            ) or ("missing_code_contract",)
            rows.append(
                ModelCodeTestBindingRow(
                    model_obligation_id=obligation_id,
                    status="blocked",
                    gaps=gap_codes,
                    source_audit_decision=_binding_source_audit_decision(plan, (), ()),
                    open_gap_codes=gap_codes,
                )
            )
            continue
        for contract in owner_contracts:
            locked_evidence = tuple(
                evidence
                for evidence in passing_by_obligation.get(obligation_id, ())
                if _counts_as_obligation_coverage(evidence)
                and contract.code_contract_id in evidence.covered_code_contracts
                and _evidence_binds_obligation_to_code_contract(
                    evidence,
                    obligation_id,
                    obligation,
                    code_contracts_by_id,
                )
            )
            contract_ids = (contract.code_contract_id,)
            evidence_ids = tuple(evidence.evidence_id for evidence in locked_evidence)
            boundary_contract_ids = tuple(
                boundary.boundary_id
                for boundary in plan.boundary_contracts
                if boundary.model_obligation_id == obligation_id
                or boundary.code_contract_id in contract_ids
            )
            boundary_observation_ids = tuple(
                observation.observation_id
                for observation in plan.boundary_observations
                if observation.boundary_id in boundary_contract_ids
            )
            runtime_node_ids = tuple(obligation.required_runtime_node_ids) + tuple(
                runtime_contract.node_id
                for runtime_contract in plan.runtime_node_contracts
                if runtime_contract.model_obligation_id == obligation_id
                or runtime_contract.code_contract_id in contract_ids
            )
            runtime_observation_ids = tuple(
                observation.observation_id
                for observation in plan.runtime_node_observations
                if observation.model_obligation_id == obligation_id
                or observation.code_contract_id in contract_ids
                or observation.node_id in runtime_node_ids
            )
            payload_contract_ids = tuple(
                payload.payload_contract_id
                for payload in plan.payload_contracts
                if payload.model_obligation_id == obligation_id
                or payload.code_contract_id in contract_ids
            )
            field_projection_ids = tuple(
                _field_projection_id(projection)
                for projection in field_projections
                if getattr(projection, "model_obligation_id", "") == obligation_id
                or getattr(projection, "code_contract_id", "") in contract_ids
            )
            source_audit_decision = _binding_source_audit_decision(
                plan,
                contract_ids,
                evidence_ids,
            )
            gap_codes = _binding_gap_codes(
                findings,
                obligation_id=obligation_id,
                contract_ids=contract_ids,
                evidence_ids=evidence_ids,
            )
            if locked_evidence:
                rows.append(
                    ModelCodeTestBindingRow(
                        model_obligation_id=obligation_id,
                        code_contract_id=contract.code_contract_id,
                        test_evidence_id=evidence_ids[0] if evidence_ids else "",
                        status="locked" if not gap_codes else "blocked",
                        gaps=gap_codes,
                        code_contract_ids=contract_ids,
                        owner_code_contract_ids=contract_ids,
                        code_paths=(contract.path,),
                        code_symbols=(contract.symbol,),
                        test_evidence_ids=evidence_ids,
                        boundary_contract_ids=boundary_contract_ids,
                        boundary_observation_ids=boundary_observation_ids,
                        runtime_node_ids=runtime_node_ids,
                        runtime_observation_ids=runtime_observation_ids,
                        payload_contract_ids=payload_contract_ids,
                        field_projection_ids=field_projection_ids,
                        source_audit_decision=source_audit_decision,
                        open_gap_codes=gap_codes,
                    )
                )
            else:
                if not gap_codes:
                    gap_codes = ("missing_code_contract_test_evidence",)
                rows.append(
                    ModelCodeTestBindingRow(
                        model_obligation_id=obligation_id,
                        code_contract_id=contract.code_contract_id,
                        status="blocked",
                        gaps=gap_codes,
                        code_contract_ids=contract_ids,
                        owner_code_contract_ids=contract_ids,
                        code_paths=(contract.path,),
                        code_symbols=(contract.symbol,),
                        boundary_contract_ids=boundary_contract_ids,
                        boundary_observation_ids=boundary_observation_ids,
                        runtime_node_ids=runtime_node_ids,
                        runtime_observation_ids=runtime_observation_ids,
                        payload_contract_ids=payload_contract_ids,
                        field_projection_ids=field_projection_ids,
                        source_audit_decision=source_audit_decision,
                        open_gap_codes=gap_codes,
                    )
                )
    return tuple(rows)


def _closure_role_finding_code(role: str) -> str:
    if role == TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION:
        return "missing_counterexample_regression_test"
    if role == TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY:
        return "missing_known_bad_replay_test"
    if role == TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED:
        return "missing_same_class_test_evidence"
    if role == TEST_CLOSURE_ROLE_OBSERVED_REGRESSION:
        return "missing_observed_regression_test_evidence"
    return "missing_model_miss_closure_test_evidence"


def _closure_role_label(role: str) -> str:
    if role == TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION:
        return "counterexample regression"
    if role == TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY:
        return "known-bad replay"
    if role == TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED:
        return "same-class generalized"
    if role == TEST_CLOSURE_ROLE_OBSERVED_REGRESSION:
        return "observed regression"
    return role or "unspecified closure"


def _closure_target_finding_code(target: ClosureEvidenceTarget) -> str:
    if target.closure_evidence_role == TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION:
        return "missing_counterexample_regression_test"
    if target.closure_evidence_role == TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY:
        return "missing_known_bad_replay_test"
    return "missing_closure_target_test_evidence"


def _coverage_findings(
    obligations_by_id: Mapping[str, ModelObligation],
    passing_by_obligation: Mapping[str, Sequence[TestEvidence]],
    code_contracts_by_id: Mapping[str, CodeContract],
    passing_by_code_contract: Mapping[str, Sequence[TestEvidence]],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    for obligation_id, obligation in obligations_by_id.items():
        passing = tuple(passing_by_obligation.get(obligation_id, ()))
        coverage_evidence = tuple(
            evidence
            for evidence in passing
            if _counts_as_obligation_coverage(evidence)
            and _transition_cell_target_matches(evidence, obligation)
            and _evidence_binds_obligation_to_code_contract(
                evidence,
                obligation_id,
                obligation,
                code_contracts_by_id,
            )
        )
        primary_edge = tuple(
            evidence for evidence in passing if _is_primary_edge_evidence(evidence)
        )
        if len(primary_edge) > 1:
            findings.append(
                ModelTestAlignmentFinding(
                    "obligation_too_coarse_for_primary_evidence",
                    f"model obligation {obligation_id} has multiple primary edge-path evidence owners; split child obligations or attach tests to leaf matrix cells",
                    obligation_id=obligation_id,
                    metadata={
                        "obligation": obligation.to_dict(),
                        "test_kind": TEST_KIND_EDGE_PATH,
                        "evidence_ids": [evidence.evidence_id for evidence in primary_edge],
                    },
                )
            )

        if obligation.required and not coverage_evidence:
            for target in obligation.required_closure_targets:
                if not target.required:
                    continue
                findings.append(
                    ModelTestAlignmentFinding(
                        _closure_target_finding_code(target),
                        (
                            f"model obligation {obligation_id} lacks current passing "
                            f"{_closure_role_label(target.closure_evidence_role)} "
                            f"test evidence for target {target.target_id!r}"
                        ),
                        obligation_id=obligation_id,
                        metadata={
                            "obligation": obligation.to_dict(),
                            "required_closure_target": target.to_dict(),
                        },
                    )
                )
            findings.append(
                ModelTestAlignmentFinding(
                    "missing_test_evidence",
                    f"model obligation {obligation_id} has no current passing test evidence",
                    obligation_id=obligation_id,
                    metadata=obligation.to_dict(),
                )
            )
            continue

        if obligation.model_miss_origin or obligation.required_closure_evidence_roles:
            for evidence in coverage_evidence:
                if evidence.closure_evidence_role and not evidence.has_external_contract_assertion():
                    findings.append(
                        ModelTestAlignmentFinding(
                            "model_miss_closure_evidence_internal_path_only",
                            f"model-miss closure evidence {evidence.evidence_id} does not prove the external behavior boundary",
                            obligation_id=obligation_id,
                            evidence_id=evidence.evidence_id,
                            metadata=evidence.to_dict(),
                        )
                    )
            externally_scoped_roles = {
                evidence.closure_evidence_role
                for evidence in coverage_evidence
                if evidence.closure_evidence_role
                and evidence.has_external_contract_assertion()
                and not evidence.overclaims_model_confidence
            }
            for role in obligation.required_closure_evidence_roles:
                if role not in externally_scoped_roles:
                    findings.append(
                        ModelTestAlignmentFinding(
                            _closure_role_finding_code(role),
                            f"model-miss obligation {obligation_id} lacks current passing {_closure_role_label(role)} test evidence",
                            obligation_id=obligation_id,
                            metadata={
                                "obligation": obligation.to_dict(),
                                "required_closure_role": role,
                                "roles_present": sorted(externally_scoped_roles),
                            },
                        )
                    )
            for target in obligation.required_closure_targets:
                if not target.required:
                    continue
                matching_target_evidence = tuple(
                    evidence
                    for evidence in coverage_evidence
                    if evidence.closure_evidence_role == target.closure_evidence_role
                    and evidence.evidence_target_id == target.target_id
                    and evidence.has_external_contract_assertion()
                    and not evidence.overclaims_model_confidence
                )
                if not matching_target_evidence:
                    findings.append(
                        ModelTestAlignmentFinding(
                            _closure_target_finding_code(target),
                            (
                                f"model obligation {obligation_id} lacks current passing "
                                f"{_closure_role_label(target.closure_evidence_role)} "
                                f"test evidence for target {target.target_id!r}"
                            ),
                            obligation_id=obligation_id,
                            metadata={
                                "obligation": obligation.to_dict(),
                                "required_closure_target": target.to_dict(),
                                "matching_roles_present": sorted(externally_scoped_roles),
                            },
                        )
                    )

        kinds_present = {evidence.test_kind for evidence in coverage_evidence}
        for required_kind in obligation.required_test_kinds:
            if required_kind not in kinds_present:
                findings.append(
                    ModelTestAlignmentFinding(
                        "missing_required_test_kind",
                        f"model obligation {obligation_id} lacks current passing {required_kind} test evidence",
                        obligation_id=obligation_id,
                        metadata={
                            "obligation": obligation.to_dict(),
                            "kinds_present": sorted(kinds_present),
                            "required_kind": required_kind,
                        },
                    )
                )

        if not obligation.allow_shared_evidence:
            evidence_by_kind: dict[str, list[TestEvidence]] = {}
            for evidence in passing:
                if not _is_primary_coverage_evidence(evidence):
                    continue
                duplicate_key = evidence.test_kind
                if obligation.required_closure_evidence_roles and evidence.closure_evidence_role:
                    duplicate_key = f"{evidence.test_kind}:{evidence.closure_evidence_role}"
                evidence_by_kind.setdefault(duplicate_key, []).append(evidence)
            for test_kind, same_kind in sorted(evidence_by_kind.items()):
                if len(same_kind) > 1:
                    findings.append(
                        ModelTestAlignmentFinding(
                            "duplicate_test_evidence_owner",
                            f"model obligation {obligation_id} has multiple current passing {test_kind} evidence owners",
                            obligation_id=obligation_id,
                            metadata={
                                "test_kind": test_kind,
                                "evidence_ids": [evidence.evidence_id for evidence in same_kind],
                            },
                        )
                    )

    for contract_id, contract in code_contracts_by_id.items():
        if not contract.required or not contract.is_owner():
            continue
        passing = tuple(passing_by_code_contract.get(contract_id, ()))
        if not passing:
            findings.append(
                ModelTestAlignmentFinding(
                    "missing_code_contract_test_evidence",
                    f"code contract {contract_id} has no current passing external-contract test evidence",
                    metadata=contract.to_dict(),
                    code_contract_id=contract_id,
                )
            )
    return findings


def review_model_test_alignment(plan: ModelTestAlignmentPlan) -> ModelTestAlignmentReport:
    """Review explicit model obligations against code contracts and test evidence."""

    field_lifecycle_findings = _field_lifecycle_findings(plan)
    plan = _plan_with_field_lifecycle_projections(plan)
    obligations_by_id, findings = _obligation_index(plan)
    findings = field_lifecycle_findings + findings
    code_contracts_by_id, code_contract_findings = _code_contract_index(plan)
    findings.extend(code_contract_findings)
    findings.extend(_code_contract_findings(plan, obligations_by_id, code_contracts_by_id))
    findings.extend(_evidence_findings(plan, obligations_by_id, code_contracts_by_id))
    findings.extend(_source_audit_findings(plan, code_contracts_by_id))
    if plan.boundary_contracts or plan.boundary_observations:
        boundary_report = review_code_boundary_conformance(
            plan.boundary_contracts,
            plan.boundary_observations,
            plan.code_contracts,
        )
        findings.extend(_boundary_findings_as_alignment_findings(boundary_report))
    if plan.payload_contracts or plan.payload_evidence:
        payload_report = review_artifact_payload_validation(
            plan.payload_contracts,
            plan.payload_evidence,
            plan.code_contracts,
            plan.obligations,
        )
        findings.extend(_artifact_payload_findings_as_alignment_findings(payload_report))
    runtime_path_contracts = _runtime_path_contracts_for_plan(plan)
    if (
        plan.require_runtime_path_evidence
        or runtime_path_contracts
        or plan.runtime_node_observations
        or plan.runtime_path_runs
    ):
        if plan.require_runtime_path_evidence and not runtime_path_contracts:
            findings.append(
                ModelTestAlignmentFinding(
                    "missing_runtime_path_contracts",
                    "model-test alignment requires runtime path evidence but declares no runtime node contracts",
                    metadata={"model_id": plan.model_id},
                )
            )
        runtime_report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                plan_id=f"{plan.model_id}:runtime-path",
                model_id=plan.model_id,
                node_contracts=runtime_path_contracts,
                observations=plan.runtime_node_observations,
                runs=plan.runtime_path_runs,
                require_proof_artifacts=plan.require_proof_artifacts,
                require_exact_path=True,
            )
        )
        findings.extend(_runtime_path_findings_as_alignment_findings(runtime_report))
    if plan.obligation_families or plan.family_evidence:
        family_report = review_obligation_family_parity(
            plan.obligation_families,
            plan.family_evidence,
        )
        findings.extend(_family_findings_as_alignment_findings(family_report.findings))
    similarity_handoff = plan.similarity_handoff
    same_family_relation_ids = similarity_handoff.same_family_relation_ids if similarity_handoff else ()
    similarity_maintenance_group_ids = similarity_handoff.maintenance_group_ids if similarity_handoff else ()
    similarity_test_obligation_ids = similarity_handoff.test_obligation_ids if similarity_handoff else ()
    evidence_duplicate_relation_ids = similarity_handoff.evidence_duplicate_relation_ids if similarity_handoff else ()
    if same_family_relation_ids and not plan.obligation_families:
        findings.append(
            ModelTestAlignmentFinding(
                "missing_similarity_family_evidence",
                "same-family model-similarity relations require obligation-family evidence or an explicit scoped family plan",
                metadata={"similarity_relation_ids": list(same_family_relation_ids)},
            )
        )
    if similarity_maintenance_group_ids and not (
        similarity_test_obligation_ids or plan.obligation_families
    ):
        findings.append(
            ModelTestAlignmentFinding(
                "missing_similarity_test_obligations",
                "similarity maintenance groups require shared and variant test obligations or obligation-family evidence before a broad maintenance claim",
                metadata={"similarity_maintenance_group_ids": list(similarity_maintenance_group_ids)},
            )
        )
    if evidence_duplicate_relation_ids and not (plan.test_evidence or plan.family_evidence):
        findings.append(
            ModelTestAlignmentFinding(
                "evidence_duplicate_without_alignment_evidence",
                "evidence-duplicate similarity relations require test or family evidence to prove the shared scope",
                metadata={"similarity_relation_ids": list(evidence_duplicate_relation_ids)},
            )
        )
    passing_by_obligation = _passing_evidence_by_obligation(plan, obligations_by_id)
    passing_by_code_contract = _passing_external_evidence_by_code_contract(plan, code_contracts_by_id)
    findings.extend(
        _coverage_findings(
            obligations_by_id,
            passing_by_obligation,
            code_contracts_by_id,
            passing_by_code_contract,
        )
    )
    binding_rows = _binding_rows(
        plan,
        obligations_by_id,
        code_contracts_by_id,
        passing_by_obligation,
        findings,
    )
    blockers = _blocker_findings(findings)
    return ModelTestAlignmentReport(
        ok=not blockers,
        model_id=plan.model_id,
        decision=_decision_for_findings(findings),
        findings=tuple(findings),
        binding_rows=binding_rows,
    )


def audit_python_code_contracts(
    code_contracts: Sequence[CodeContract],
    source_by_path: Mapping[str, str],
) -> tuple[PythonCodeContractEvidence, ...]:
    """Compatibility entrypoint for the source-audit split module."""

    from .model_test_alignment_source import audit_python_code_contracts as _audit

    return _audit(code_contracts, source_by_path)

def audit_python_test_assertions(
    test_evidence: Sequence[TestEvidence],
    code_contracts: Sequence[CodeContract],
    source_by_path: Mapping[str, str],
) -> tuple[PythonTestAssertionEvidence, ...]:
    """Compatibility entrypoint for the source-audit split module."""

    from .model_test_alignment_source import audit_python_test_assertions as _audit

    return _audit(test_evidence, code_contracts, source_by_path)


def review_python_contract_source_audit(
    code_contracts: Sequence[CodeContract],
    test_evidence: Sequence[TestEvidence],
    code_evidence: Sequence[PythonCodeContractEvidence],
    test_assertions: Sequence[PythonTestAssertionEvidence],
) -> ContractSourceAuditReport:
    """Compatibility entrypoint for the source-audit split module."""

    from .model_test_alignment_source import review_python_contract_source_audit as _review

    return _review(code_contracts, test_evidence, code_evidence, test_assertions)


__all__ = [
    "ARTIFACT_PAYLOAD_METHOD_AUTOMATED_TEST",
    "ARTIFACT_PAYLOAD_METHOD_BROWSER",
    "ARTIFACT_PAYLOAD_METHOD_DESKTOP",
    "ARTIFACT_PAYLOAD_METHOD_MANUAL",
    "ARTIFACT_PAYLOAD_METHOD_REPLAY",
    "ARTIFACT_PAYLOAD_STATUS_ACCEPTED",
    "ARTIFACT_PAYLOAD_STATUS_REJECTED",
    "ArtifactPayloadCase",
    "ArtifactPayloadContract",
    "ArtifactPayloadEvidence",
    "ArtifactPayloadFinding",
    "ArtifactPayloadValidationReport",
    "CODE_CONTRACT_ROLE_ADAPTER",
    "CODE_CONTRACT_ROLE_FACADE",
    "CODE_CONTRACT_ROLE_HELPER",
    "CODE_CONTRACT_ROLE_OWNER",
    "CODE_CONTRACT_ROLE_READ_ONLY",
    "ClosureEvidenceTarget",
    "CodeBoundaryConformanceReport",
    "CodeBoundaryContract",
    "CodeBoundaryFinding",
    "CodeBoundaryObservation",
    "CodeContract",
    "ContractSourceAuditFinding",
    "ContractSourceAuditReport",
    "ModelCodeTestBindingRow",
    "ModelObligation",
    "ModelTestAlignmentFinding",
    "ModelTestAlignmentPlan",
    "ModelTestAlignmentReport",
    "PythonCodeContractEvidence",
    "PythonTestAssertionEvidence",
    "TestEvidence",
    "TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT",
    "TEST_ASSERTION_SCOPE_INTERNAL_PATH",
    "TEST_ASSERTION_SCOPE_MIXED",
    "TEST_ASSERTION_SCOPE_UNKNOWN",
    "TEST_CLOSURE_ROLE_OBSERVED_REGRESSION",
    "TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED",
    "TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION",
    "TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY",
    "TEST_CLOSURE_ROLE_UNSPECIFIED",
    "TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE",
    "TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL",
    "TEST_EVIDENCE_ROLE_PRIMARY",
    "TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH",
    "TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT",
    "TEST_EVIDENCE_ROLE_TRANSITION_CELL",
    "TEST_KIND_EDGE_PATH",
    "TEST_KIND_FAILURE_PATH",
    "TEST_KIND_HAPPY_PATH",
    "TEST_KIND_NEGATIVE_PATH",
    "TEST_KIND_REPLAY",
    "TEST_STATUS_ERROR",
    "TEST_STATUS_FAILED",
    "TEST_STATUS_NOT_RUN",
    "TEST_STATUS_PASSED",
    "TEST_STATUS_RUNNING",
    "TEST_STATUS_SKIPPED",
    "TEST_STATUS_TIMEOUT",
    "audit_python_code_contracts",
    "audit_python_test_assertions",
    "review_artifact_payload_validation",
    "review_code_boundary_conformance",
    "review_python_contract_source_audit",
    "review_model_test_alignment",
]
