"""Model obligation, code contract, and test evidence alignment helpers.

Model-Test Alignment reviews whether explicit FlowGuard model obligations,
optional code external contracts, and ordinary test evidence describe the same
behavioral surface. It intentionally does not read TestMesh, StructureMesh, or
ModelMesh reports.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes


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
TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT = "supporting_contract"
TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE = "integration_smoke"
PRIMARY_TEST_EVIDENCE_ROLES = {
    TEST_EVIDENCE_ROLE_PRIMARY,
    TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH,
}
ALLOWED_TEST_EVIDENCE_ROLES = PRIMARY_TEST_EVIDENCE_ROLES | {
    TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL,
    TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT,
    TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE,
}

TEST_CLOSURE_ROLE_UNSPECIFIED = ""
TEST_CLOSURE_ROLE_OBSERVED_REGRESSION = "observed_regression"
TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED = "same_class_generalized"
MODEL_MISS_DEFAULT_CLOSURE_ROLES = (
    TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
    TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
)

TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT = "external_contract"
TEST_ASSERTION_SCOPE_INTERNAL_PATH = "internal_path"
TEST_ASSERTION_SCOPE_MIXED = "mixed"
TEST_ASSERTION_SCOPE_UNKNOWN = "unknown"

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


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _final_name(name: str) -> str:
    return name.rsplit(".", 1)[-1] if name else ""


def _symbol_matches_call(symbol: str, call_name: str) -> bool:
    if not symbol or not call_name:
        return False
    return call_name == symbol or _final_name(call_name) == _final_name(symbol)


def _literal_name(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _final_name(_call_name(node.func))
    return ""


def _subscript_key(node: ast.Subscript) -> str:
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return ""


def _target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    if isinstance(node, ast.Subscript):
        key = _subscript_key(node)
        return (key,) if key else ()
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_target_names(element))
        return tuple(names)
    return ()


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
        closure_roles = _as_tuple(self.required_closure_evidence_roles)
        if self.requires_same_class_test_evidence and not closure_roles:
            closure_roles = MODEL_MISS_DEFAULT_CLOSURE_ROLES
        object.__setattr__(self, "required_closure_evidence_roles", closure_roles)

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
class ModelTestAlignmentPlan:
    """A direct model-obligation, code-contract, and test-evidence review plan."""

    model_id: str
    obligations: tuple[ModelObligation, ...] = ()
    code_contracts: tuple[CodeContract, ...] = ()
    test_evidence: tuple[TestEvidence, ...] = ()
    boundary_contracts: tuple[CodeBoundaryContract, ...] = ()
    boundary_observations: tuple[CodeBoundaryObservation, ...] = ()
    require_code_contracts: bool = False
    require_proof_artifacts: bool = False
    allow_orphan_tests: bool = False
    allow_orphan_code_contracts: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "code_contracts", tuple(self.code_contracts))
        object.__setattr__(self, "test_evidence", tuple(self.test_evidence))
        object.__setattr__(self, "boundary_contracts", tuple(self.boundary_contracts))
        object.__setattr__(self, "boundary_observations", tuple(self.boundary_observations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "obligations": [obligation.to_dict() for obligation in self.obligations],
            "code_contracts": [contract.to_dict() for contract in self.code_contracts],
            "test_evidence": [evidence.to_dict() for evidence in self.test_evidence],
            "boundary_contracts": [contract.to_dict() for contract in self.boundary_contracts],
            "boundary_observations": [observation.to_dict() for observation in self.boundary_observations],
            "require_code_contracts": self.require_code_contracts,
            "require_proof_artifacts": self.require_proof_artifacts,
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
class ModelTestAlignmentReport:
    """Structured outcome of a model-test alignment review."""

    ok: bool
    model_id: str
    decision: str
    findings: tuple[ModelTestAlignmentFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: model={self.model_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard model-test alignment review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"model: {self.model_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
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
        ("obligation_too_coarse_for_primary_evidence", "child_model_split_required"),
        ("leaf_matrix_cell_target_missing", "leaf_matrix_cell_target_required"),
        ("supporting_evidence_target_missing", "supporting_evidence_target_required"),
        ("primary_edge_role_kind_mismatch", "invalid_alignment_plan"),
        ("invalid_test_evidence_role", "invalid_alignment_plan"),
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

    if not code_contracts_by_id and not plan.require_code_contracts:
        return findings

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
            evidence.evidence_role == TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT
            and not evidence.evidence_target_id
            and not evidence.covered_code_contracts
        ):
            findings.append(
                ModelTestAlignmentFinding(
                    "supporting_evidence_target_missing",
                    f"supporting evidence {evidence.evidence_id} must name the child obligation, code contract, or boundary it supports",
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
            if obligation_id not in obligations_by_id:
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
        if code_contracts_by_id and evidence.covered_obligations and not evidence.covered_code_contracts:
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
            implemented_obligations: set[str] = set()
            for code_contract_id in evidence.covered_code_contracts:
                contract = code_contracts_by_id.get(code_contract_id)
                if contract is not None:
                    implemented_obligations.update(contract.implements_obligations)
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
    }


def _closure_role_finding_code(role: str) -> str:
    if role == TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED:
        return "missing_same_class_test_evidence"
    if role == TEST_CLOSURE_ROLE_OBSERVED_REGRESSION:
        return "missing_observed_regression_test_evidence"
    return "missing_model_miss_closure_test_evidence"


def _closure_role_label(role: str) -> str:
    if role == TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED:
        return "same-class generalized"
    if role == TEST_CLOSURE_ROLE_OBSERVED_REGRESSION:
        return "observed regression"
    return role or "unspecified closure"


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
            evidence for evidence in passing if _counts_as_obligation_coverage(evidence)
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

    obligations_by_id, findings = _obligation_index(plan)
    code_contracts_by_id, code_contract_findings = _code_contract_index(plan)
    findings.extend(code_contract_findings)
    findings.extend(_code_contract_findings(plan, obligations_by_id, code_contracts_by_id))
    findings.extend(_evidence_findings(plan, obligations_by_id, code_contracts_by_id))
    if plan.boundary_contracts or plan.boundary_observations:
        boundary_report = review_code_boundary_conformance(
            plan.boundary_contracts,
            plan.boundary_observations,
            plan.code_contracts,
        )
        findings.extend(_boundary_findings_as_alignment_findings(boundary_report))
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
    blockers = _blocker_findings(findings)
    return ModelTestAlignmentReport(
        ok=not blockers,
        model_id=plan.model_id,
        decision=_decision_for_findings(findings),
        findings=tuple(findings),
    )


def _function_candidates(tree: ast.AST, symbol: str) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    parts = tuple(part for part in symbol.split(".") if part)
    if not parts:
        return ()
    target_name = parts[-1]
    class_name = parts[-2] if len(parts) >= 2 else ""
    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != target_name:
            continue
        if not class_name:
            candidates.append(node)
            continue
        parent = getattr(node, "_flowguard_parent", None)
        if isinstance(parent, ast.ClassDef) and parent.name == class_name:
            candidates.append(node)
    return tuple(candidates)


def _attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_flowguard_parent", parent)


def _parse_python_source(path: str, source_text: str) -> ast.AST | str:
    try:
        tree = ast.parse(source_text, filename=path or "<flowguard-source>")
    except SyntaxError as exc:
        return f"{exc.__class__.__name__}: {exc.msg}"
    _attach_parents(tree)
    return tree


def _extract_code_evidence_from_function(
    contract: CodeContract,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> PythonCodeContractEvidence:
    args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    parameters = [arg.arg for arg in args if arg.arg not in {"self", "cls"}]
    calls: list[str] = []
    side_effects: list[str] = []
    state_reads: list[str] = []
    state_writes: list[str] = []
    return_values: list[str] = []
    raised_errors: list[str] = []
    declared_side_effects = set(contract.side_effects)

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name:
                calls.append(name)
                final = _final_name(name)
                if final in declared_side_effects or any(final.startswith(prefix) for prefix in SIDE_EFFECT_CALL_PREFIXES):
                    side_effects.append(final)
        elif isinstance(child, ast.Return):
            if child.value is not None:
                literal = _literal_name(child.value)
                if literal:
                    return_values.append(literal)
        elif isinstance(child, ast.Raise):
            if child.exc is not None:
                raised = _literal_name(child.exc)
                if raised:
                    raised_errors.append(raised)
        elif isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = []
            if isinstance(child, ast.Assign):
                targets = list(child.targets)
            else:
                targets = [child.target]
            for target in targets:
                state_writes.extend(_target_names(target))
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            state_reads.append(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
            state_reads.append(child.attr)
        elif isinstance(child, ast.Subscript) and isinstance(child.ctx, ast.Load):
            key = _subscript_key(child)
            if key:
                state_reads.append(key)

    return PythonCodeContractEvidence(
        code_contract_id=contract.code_contract_id,
        path=contract.path,
        symbol=contract.symbol,
        found=True,
        parameters=_unique_sorted(parameters),
        returns_value=bool(return_values) or any(isinstance(child, ast.Return) and child.value is not None for child in ast.walk(node)),
        return_values=_unique_sorted(return_values),
        raised_errors=_unique_sorted(raised_errors),
        state_reads=_unique_sorted(state_reads),
        state_writes=_unique_sorted(state_writes),
        side_effects=_unique_sorted(side_effects),
        calls=_unique_sorted(calls),
    )


def audit_python_code_contracts(
    code_contracts: Sequence[CodeContract],
    source_by_path: Mapping[str, str],
) -> tuple[PythonCodeContractEvidence, ...]:
    """Extract conservative AST evidence for declared Python code contracts.

    This is a structural audit, not a full semantic proof. It detects stable
    source facts such as function presence, parameters, return statements,
    raises, assignments, and risky side-effect-looking calls.
    """

    parsed_by_path: dict[str, ast.AST | str] = {}
    evidence: list[PythonCodeContractEvidence] = []
    for contract in code_contracts:
        source_text = source_by_path.get(contract.path)
        if source_text is None:
            evidence.append(
                PythonCodeContractEvidence(
                    contract.code_contract_id,
                    path=contract.path,
                    symbol=contract.symbol,
                    parse_error="source path not supplied",
                )
            )
            continue
        parsed = parsed_by_path.get(contract.path)
        if parsed is None:
            parsed = _parse_python_source(contract.path, source_text)
            parsed_by_path[contract.path] = parsed
        if isinstance(parsed, str):
            evidence.append(
                PythonCodeContractEvidence(
                    contract.code_contract_id,
                    path=contract.path,
                    symbol=contract.symbol,
                    parse_error=parsed,
                )
            )
            continue
        candidates = _function_candidates(parsed, contract.symbol)
        if not candidates:
            evidence.append(
                PythonCodeContractEvidence(
                    contract.code_contract_id,
                    path=contract.path,
                    symbol=contract.symbol,
                )
            )
            continue
        evidence.append(_extract_code_evidence_from_function(contract, candidates[0]))
    return tuple(evidence)


def _find_test_function(tree: ast.AST, test_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_name:
            return node
    return None


def _assertion_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        elif isinstance(child, ast.Call):
            final = _final_name(_call_name(child.func))
            if final.startswith("assert") or final in {
                "assertEqual",
                "assertNotEqual",
                "assertTrue",
                "assertFalse",
                "assertIn",
                "assertNotIn",
                "assertRaises",
            }:
                count += 1
    return count


def _extract_test_evidence_from_function(
    evidence: TestEvidence,
    code_contracts_by_id: Mapping[str, CodeContract],
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> PythonTestAssertionEvidence:
    calls = _unique_sorted([_call_name(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)])
    called_contracts: list[str] = []
    for code_contract_id in evidence.covered_code_contracts:
        contract = code_contracts_by_id.get(code_contract_id)
        if contract is None:
            continue
        if any(_symbol_matches_call(contract.symbol, call) for call in calls):
            called_contracts.append(code_contract_id)
    assert_count = _assertion_count(node)
    if called_contracts and assert_count:
        assertion_scope = TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT
    elif assert_count:
        assertion_scope = TEST_ASSERTION_SCOPE_INTERNAL_PATH
    else:
        assertion_scope = TEST_ASSERTION_SCOPE_UNKNOWN
    return PythonTestAssertionEvidence(
        evidence_id=evidence.evidence_id,
        path=evidence.path,
        test_name=evidence.test_name,
        found=True,
        called_code_contracts=_unique_sorted(called_contracts),
        assert_count=assert_count,
        assertion_scope=assertion_scope,
        calls=calls,
    )


def audit_python_test_assertions(
    test_evidence: Sequence[TestEvidence],
    code_contracts: Sequence[CodeContract],
    source_by_path: Mapping[str, str],
) -> tuple[PythonTestAssertionEvidence, ...]:
    """Extract conservative AST evidence for Python tests that claim contracts."""

    contracts_by_id = {contract.code_contract_id: contract for contract in code_contracts}
    parsed_by_path: dict[str, ast.AST | str] = {}
    result: list[PythonTestAssertionEvidence] = []
    for evidence in test_evidence:
        source_text = source_by_path.get(evidence.path)
        if source_text is None:
            result.append(
                PythonTestAssertionEvidence(
                    evidence.evidence_id,
                    path=evidence.path,
                    test_name=evidence.test_name,
                    parse_error="source path not supplied",
                )
            )
            continue
        parsed = parsed_by_path.get(evidence.path)
        if parsed is None:
            parsed = _parse_python_source(evidence.path, source_text)
            parsed_by_path[evidence.path] = parsed
        if isinstance(parsed, str):
            result.append(
                PythonTestAssertionEvidence(
                    evidence.evidence_id,
                    path=evidence.path,
                    test_name=evidence.test_name,
                    parse_error=parsed,
                )
            )
            continue
        test_name = evidence.test_name or evidence.evidence_id
        node = _find_test_function(parsed, test_name)
        if node is None:
            result.append(PythonTestAssertionEvidence(evidence.evidence_id, path=evidence.path, test_name=test_name))
            continue
        result.append(_extract_test_evidence_from_function(evidence, contracts_by_id, node))
    return tuple(result)


def _source_audit_decision(findings: Sequence[ContractSourceAuditFinding]) -> str:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        return "python_contract_source_audit_green"
    priority = (
        "source_contract_parse_error",
        "source_contract_missing_symbol",
        "source_contract_missing_input",
        "source_contract_missing_output",
        "source_contract_missing_state_write",
        "source_contract_missing_side_effect",
        "source_contract_extra_side_effect",
        "source_test_parse_error",
        "source_test_missing",
        "source_test_missing_code_contract_call",
        "source_test_missing_external_assertion",
        "source_test_internal_path_only",
    )
    codes = {finding.code for finding in blockers}
    for code in priority:
        if code in codes:
            return code
    return "python_contract_source_audit_blocked"


def review_python_contract_source_audit(
    code_contracts: Sequence[CodeContract],
    test_evidence: Sequence[TestEvidence],
    code_evidence: Sequence[PythonCodeContractEvidence],
    test_assertions: Sequence[PythonTestAssertionEvidence],
) -> ContractSourceAuditReport:
    """Review conservative Python source evidence against declared contracts."""

    code_contracts_by_id = {contract.code_contract_id: contract for contract in code_contracts}
    code_evidence_by_id = {evidence.code_contract_id: evidence for evidence in code_evidence}
    test_assertions_by_id = {evidence.evidence_id: evidence for evidence in test_assertions}
    findings: list[ContractSourceAuditFinding] = []

    for contract in code_contracts:
        evidence = code_evidence_by_id.get(contract.code_contract_id)
        if evidence is None:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_symbol",
                    f"code contract {contract.code_contract_id} has no source audit evidence",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata=contract.to_dict(),
                )
            )
            continue
        if evidence.parse_error:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_parse_error",
                    f"code contract {contract.code_contract_id} source could not be parsed: {evidence.parse_error}",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        if not evidence.found:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_symbol",
                    f"code contract {contract.code_contract_id} symbol {contract.symbol} was not found",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        missing_inputs = _tuple_set(contract.external_inputs) - _tuple_set(evidence.parameters)
        if missing_inputs:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_input",
                    f"source for {contract.code_contract_id} is missing declared external inputs",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"missing": sorted(missing_inputs), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        if contract.external_outputs and not evidence.returns_value:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_output",
                    f"source for {contract.code_contract_id} has no return value for declared external outputs",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        missing_state_writes = _tuple_set(contract.state_writes) - _tuple_set(evidence.state_writes)
        if missing_state_writes:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_state_write",
                    f"source for {contract.code_contract_id} is missing declared state writes",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"missing": sorted(missing_state_writes), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        missing_side_effects = _tuple_set(contract.side_effects) - _tuple_set(evidence.side_effects)
        if missing_side_effects:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_side_effect",
                    f"source for {contract.code_contract_id} is missing declared side effects",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"missing": sorted(missing_side_effects), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        extra_side_effects = _tuple_set(evidence.side_effects) - _tuple_set(contract.side_effects)
        if extra_side_effects:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_extra_side_effect",
                    f"source for {contract.code_contract_id} has side-effect-looking calls not declared by the code contract",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"extra": sorted(extra_side_effects), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )

    for evidence in test_evidence:
        assertion = test_assertions_by_id.get(evidence.evidence_id)
        if assertion is None:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing",
                    f"test evidence {evidence.evidence_id} has no source audit evidence",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        if assertion.parse_error:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_parse_error",
                    f"test evidence {evidence.evidence_id} source could not be parsed: {assertion.parse_error}",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata=assertion.to_dict(),
                )
            )
            continue
        if not assertion.found:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing",
                    f"test evidence {evidence.evidence_id} function {assertion.test_name} was not found",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata=assertion.to_dict(),
                )
            )
            continue
        missing_calls = _tuple_set(evidence.covered_code_contracts) - _tuple_set(assertion.called_code_contracts)
        if missing_calls:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing_code_contract_call",
                    f"test evidence {evidence.evidence_id} does not call declared code contract symbols",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata={"missing": sorted(missing_calls), "assertion": assertion.to_dict(), "evidence": evidence.to_dict()},
                )
            )
        if evidence.covered_code_contracts and assertion.assert_count <= 0:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing_external_assertion",
                    f"test evidence {evidence.evidence_id} calls no assertion for the external contract",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata={"assertion": assertion.to_dict(), "evidence": evidence.to_dict()},
                )
            )
        if evidence.covered_code_contracts and assertion.assertion_scope in {
            TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            TEST_ASSERTION_SCOPE_UNKNOWN,
        }:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_internal_path_only",
                    f"test evidence {evidence.evidence_id} source does not prove the external contract boundary",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata={"assertion": assertion.to_dict(), "evidence": evidence.to_dict()},
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    return ContractSourceAuditReport(
        ok=not blockers,
        decision=_source_audit_decision(findings),
        findings=tuple(findings),
        code_evidence=tuple(code_evidence),
        test_evidence=tuple(test_assertions),
    )


__all__ = [
    "CODE_CONTRACT_ROLE_ADAPTER",
    "CODE_CONTRACT_ROLE_FACADE",
    "CODE_CONTRACT_ROLE_HELPER",
    "CODE_CONTRACT_ROLE_OWNER",
    "CODE_CONTRACT_ROLE_READ_ONLY",
    "CodeBoundaryConformanceReport",
    "CodeBoundaryContract",
    "CodeBoundaryFinding",
    "CodeBoundaryObservation",
    "CodeContract",
    "ContractSourceAuditFinding",
    "ContractSourceAuditReport",
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
    "TEST_CLOSURE_ROLE_UNSPECIFIED",
    "TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE",
    "TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL",
    "TEST_EVIDENCE_ROLE_PRIMARY",
    "TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH",
    "TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT",
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
    "review_code_boundary_conformance",
    "review_python_contract_source_audit",
    "review_model_test_alignment",
]
