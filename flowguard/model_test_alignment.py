"""Model obligation, code contract, and test evidence alignment helpers.

Model-Test Alignment reviews whether explicit FlowGuard model obligations,
optional code external contracts, and ordinary test evidence describe the same
behavioral surface. It intentionally does not read TestMesh, StructureMesh, or
ModelMesh reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


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

TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT = "external_contract"
TEST_ASSERTION_SCOPE_INTERNAL_PATH = "internal_path"
TEST_ASSERTION_SCOPE_MIXED = "mixed"
TEST_ASSERTION_SCOPE_UNKNOWN = "unknown"

CODE_CONTRACT_ROLE_OWNER = "owner"
CODE_CONTRACT_ROLE_HELPER = "helper"
CODE_CONTRACT_ROLE_ADAPTER = "adapter"
CODE_CONTRACT_ROLE_FACADE = "facade"
CODE_CONTRACT_ROLE_READ_ONLY = "read_only"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _tuple_set(values: Sequence[str]) -> set[str]:
    return {str(value) for value in values}


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
    stale_reasons: tuple[str, ...] = ()
    overclaims_model_confidence: bool = False

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
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))

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
            "stale_reasons": list(self.stale_reasons),
            "overclaims_model_confidence": self.overclaims_model_confidence,
        }


@dataclass(frozen=True)
class ModelTestAlignmentPlan:
    """A direct model-obligation, code-contract, and test-evidence review plan."""

    model_id: str
    obligations: tuple[ModelObligation, ...] = ()
    code_contracts: tuple[CodeContract, ...] = ()
    test_evidence: tuple[TestEvidence, ...] = ()
    require_code_contracts: bool = False
    allow_orphan_tests: bool = False
    allow_orphan_code_contracts: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "code_contracts", tuple(self.code_contracts))
        object.__setattr__(self, "test_evidence", tuple(self.test_evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "obligations": [obligation.to_dict() for obligation in self.obligations],
            "code_contracts": [contract.to_dict() for contract in self.code_contracts],
            "test_evidence": [evidence.to_dict() for evidence in self.test_evidence],
            "require_code_contracts": self.require_code_contracts,
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


def _coverage_findings(
    obligations_by_id: Mapping[str, ModelObligation],
    passing_by_obligation: Mapping[str, Sequence[TestEvidence]],
    code_contracts_by_id: Mapping[str, CodeContract],
    passing_by_code_contract: Mapping[str, Sequence[TestEvidence]],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    for obligation_id, obligation in obligations_by_id.items():
        passing = tuple(passing_by_obligation.get(obligation_id, ()))
        if obligation.required and not passing:
            findings.append(
                ModelTestAlignmentFinding(
                    "missing_test_evidence",
                    f"model obligation {obligation_id} has no current passing test evidence",
                    obligation_id=obligation_id,
                    metadata=obligation.to_dict(),
                )
            )
            continue

        kinds_present = {evidence.test_kind for evidence in passing}
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
                evidence_by_kind.setdefault(evidence.test_kind, []).append(evidence)
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


__all__ = [
    "CODE_CONTRACT_ROLE_ADAPTER",
    "CODE_CONTRACT_ROLE_FACADE",
    "CODE_CONTRACT_ROLE_HELPER",
    "CODE_CONTRACT_ROLE_OWNER",
    "CODE_CONTRACT_ROLE_READ_ONLY",
    "CodeContract",
    "ModelObligation",
    "ModelTestAlignmentFinding",
    "ModelTestAlignmentPlan",
    "ModelTestAlignmentReport",
    "TestEvidence",
    "TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT",
    "TEST_ASSERTION_SCOPE_INTERNAL_PATH",
    "TEST_ASSERTION_SCOPE_MIXED",
    "TEST_ASSERTION_SCOPE_UNKNOWN",
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
    "review_model_test_alignment",
]
