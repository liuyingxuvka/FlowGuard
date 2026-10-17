"""Runtime evidence for finite ContractExhaustionMesh case inventories.

``contract_exhaustion`` owns the declaration and generation of finite cases.
This module owns only the narrow boundary after a native execution owner has
collected terminal rows for those cases.  It reconciles those rows with the
exact generated case inventory and never starts a target process, invents a
result, or treats a synthetic ``ContractFaultProfile`` as live evidence.

The native adapter supplies ``result_rows`` and ``reused_rows`` after its own
runner has produced or independently verified the corresponding artifacts.
Missing, orphaned, conflicting, or fingerprint-free rows remain visible and
block a complete claim.  Static generation and runtime execution therefore
remain separate artifacts while sharing one finite case identity boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract_exhaustion import ContractExhaustionReport
from .portable_model import canonical_identity, canonical_json_bytes
from .proof_artifact import (
    ProofArtifactRef,
    is_sha256_fingerprint,
    proof_artifact_integrity_gap_codes,
)


CONTRACT_RUNTIME_EVIDENCE_SCHEMA = "flowguard.contract_runtime_evidence.v1"

CONTRACT_RUNTIME_EXECUTION_EXECUTED = "executed"
CONTRACT_RUNTIME_EXECUTION_REUSED = "reused"
CONTRACT_RUNTIME_EXECUTION_NOT_RUN = "not_run"
CONTRACT_RUNTIME_EXECUTION_STATES = (
    CONTRACT_RUNTIME_EXECUTION_EXECUTED,
    CONTRACT_RUNTIME_EXECUTION_REUSED,
    CONTRACT_RUNTIME_EXECUTION_NOT_RUN,
)

CONTRACT_RUNTIME_OUTCOME_PASSED = "passed"
CONTRACT_RUNTIME_OUTCOME_FAILED = "failed"
CONTRACT_RUNTIME_OUTCOME_SKIPPED = "skipped"
CONTRACT_RUNTIME_OUTCOME_XFAILED = "xfailed"
CONTRACT_RUNTIME_OUTCOME_XPASSED = "xpassed"
CONTRACT_RUNTIME_OUTCOME_NOT_RUN = "not_run"
CONTRACT_RUNTIME_OUTCOMES = (
    CONTRACT_RUNTIME_OUTCOME_PASSED,
    CONTRACT_RUNTIME_OUTCOME_FAILED,
    CONTRACT_RUNTIME_OUTCOME_SKIPPED,
    CONTRACT_RUNTIME_OUTCOME_XFAILED,
    CONTRACT_RUNTIME_OUTCOME_XPASSED,
    CONTRACT_RUNTIME_OUTCOME_NOT_RUN,
)

CONTRACT_RUNTIME_FINDING_SEVERITIES = ("info", "warning", "blocker")
CONTRACT_RUNTIME_COUNT_FIELDS = (
    "planned_count",
    "selected_count",
    "explicitly_not_selected_count",
    "executed_count",
    "reused_count",
    "not_run_count",
    "passed_count",
    "failed_count",
    "skipped_count",
    "xfailed_count",
    "xpassed_count",
)

_COMPLETE_CLAIM_BOUNDARIES = frozenset(
    {"declared_complete", "release", "publish", "production", "full"}
)


class ContractRuntimeEvidenceError(ValueError):
    """Raised when a contract runtime artifact is not current canonical shape."""


def _text(value: Any, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ContractRuntimeEvidenceError(f"{context} must be {qualifier}")
    return value


def _strings(
    value: Any,
    *,
    context: str,
    allow_duplicates: bool = False,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ContractRuntimeEvidenceError(f"{context} must be an array")
    result = tuple(
        _text(item, context=f"{context}[]", allow_empty=allow_empty)
        for item in value
    )
    if not allow_duplicates and len(result) != len(set(result)):
        raise ContractRuntimeEvidenceError(f"{context} contains duplicate values")
    return result


def _strict_object(
    value: Any,
    *,
    context: str,
    required: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractRuntimeEvidenceError(f"{context} must be an object")
    if set(value) != set(required):
        difference = sorted(set(value) ^ set(required))
        raise ContractRuntimeEvidenceError(
            f"{context} fields differ from the current schema: {difference}"
        )
    return value


def _normalize_ids(
    values: Sequence[str],
    *,
    context: str,
    allow_duplicates: bool = False,
) -> tuple[str, ...]:
    result = tuple(_text(value, context=f"{context}[]") for value in values)
    if not allow_duplicates and len(result) != len(set(result)):
        raise ContractRuntimeEvidenceError(f"{context} contains duplicate values")
    return result


def _normalize_counts(value: Mapping[str, Any] | None) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractRuntimeEvidenceError("declared_parent_counts must be an object")
    result: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key not in CONTRACT_RUNTIME_COUNT_FIELDS:
            raise ContractRuntimeEvidenceError(
                f"unknown declared parent count field: {raw_key}"
            )
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
            raise ContractRuntimeEvidenceError(
                f"declared parent count {raw_key} must be a non-negative integer"
            )
        result[key] = int(raw_value)
    return result


@dataclass(frozen=True)
class ContractRuntimeResult:
    """One native terminal result row before it is bound to a contract case."""

    outcome: str
    reason: str = ""
    result_fingerprint: str = ""
    observed_status: str = ""
    producer_receipt_id: str = ""
    result_path: str = ""
    producer_receipt_fingerprint: str = ""
    producer_receipt_path: str = ""
    reuse_identity: str = ""
    source_fingerprint: str = ""
    model_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    terminal_state: str = ""
    cleanup_state: str = ""
    cleanup_verified: bool | None = None

    def __post_init__(self) -> None:
        outcome = _text(self.outcome, context="contract_runtime_result.outcome")
        if outcome not in CONTRACT_RUNTIME_OUTCOMES:
            raise ContractRuntimeEvidenceError(f"unknown contract runtime outcome: {outcome}")
        object.__setattr__(self, "outcome", outcome)
        for name in (
            "reason",
            "result_fingerprint",
            "observed_status",
            "producer_receipt_id",
            "result_path",
            "producer_receipt_fingerprint",
            "producer_receipt_path",
            "reuse_identity",
            "source_fingerprint",
            "model_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
            "terminal_state",
            "cleanup_state",
        ):
            _text(
                getattr(self, name),
                context=f"contract_runtime_result.{name}",
                allow_empty=True,
            )
        if outcome == CONTRACT_RUNTIME_OUTCOME_NOT_RUN:
            if (
                self.result_fingerprint
                or self.producer_receipt_id
                or self.producer_receipt_fingerprint
                or self.result_path
                or self.producer_receipt_path
            ):
                raise ContractRuntimeEvidenceError(
                    "a not_run contract runtime result cannot carry an artifact or receipt"
                )
        elif not self.result_fingerprint.strip():
            raise ContractRuntimeEvidenceError(
                f"contract runtime outcome {outcome} requires a result fingerprint"
            )
        if outcome != CONTRACT_RUNTIME_OUTCOME_PASSED and not self.reason.strip():
            raise ContractRuntimeEvidenceError(
                f"contract runtime outcome {outcome} requires a reason"
            )
        if self.cleanup_verified is not None and not isinstance(self.cleanup_verified, bool):
            raise ContractRuntimeEvidenceError("contract_runtime_result.cleanup_verified must be boolean or null")

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "result_fingerprint": self.result_fingerprint,
            "observed_status": self.observed_status,
            "producer_receipt_id": self.producer_receipt_id,
            "result_path": self.result_path,
            "producer_receipt_fingerprint": self.producer_receipt_fingerprint,
            "producer_receipt_path": self.producer_receipt_path,
            "reuse_identity": self.reuse_identity,
            "source_fingerprint": self.source_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "terminal_state": self.terminal_state,
            "cleanup_state": self.cleanup_state,
            "cleanup_verified": self.cleanup_verified,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ContractRuntimeResult":
        fields = (
            "outcome",
            "reason",
            "result_fingerprint",
            "observed_status",
            "producer_receipt_id",
            "result_path",
            "producer_receipt_fingerprint",
            "producer_receipt_path",
            "reuse_identity",
            "source_fingerprint",
            "model_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
            "terminal_state",
            "cleanup_state",
            "cleanup_verified",
        )
        if not isinstance(value, Mapping):
            raise ContractRuntimeEvidenceError("contract runtime result must be an object")
        unknown = set(value) - set(fields)
        if unknown:
            raise ContractRuntimeEvidenceError(f"contract runtime result contains unknown fields: {sorted(unknown)}")
        data = {name: value.get(name, "" if name != "cleanup_verified" else None) for name in fields}
        return cls(**data)


@dataclass(frozen=True)
class ContractRuntimeCaseEvidence:
    """One exact generated contract case and its native execution state."""

    case_id: str
    required: bool
    model_id: str
    interaction_group_id: str
    generation_kind: str
    expected_status: str
    planned: bool
    selected: bool
    execution_status: str
    outcome: str
    reason: str = ""
    result_fingerprint: str = ""
    observed_status: str = ""
    producer_receipt_id: str = ""
    result_path: str = ""
    producer_receipt_fingerprint: str = ""
    producer_receipt_path: str = ""
    reuse_identity: str = ""
    source_fingerprint: str = ""
    model_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    terminal_state: str = ""
    cleanup_state: str = ""
    cleanup_verified: bool | None = None

    def __post_init__(self) -> None:
        _text(self.case_id, context="contract_runtime_case.case_id")
        if not isinstance(self.required, bool):
            raise ContractRuntimeEvidenceError("contract_runtime_case.required must be boolean")
        if not isinstance(self.planned, bool):
            raise ContractRuntimeEvidenceError("contract_runtime_case.planned must be boolean")
        if not isinstance(self.selected, bool):
            raise ContractRuntimeEvidenceError("contract_runtime_case.selected must be boolean")
        for name in (
            "model_id",
            "interaction_group_id",
            "generation_kind",
            "expected_status",
            "reason",
            "result_fingerprint",
            "observed_status",
            "producer_receipt_id",
            "result_path",
            "producer_receipt_fingerprint",
            "producer_receipt_path",
            "reuse_identity",
            "source_fingerprint",
            "model_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
            "terminal_state",
            "cleanup_state",
        ):
            _text(
                getattr(self, name),
                context=f"contract_runtime_case.{name}",
                allow_empty=True,
            )
        status = _text(
            self.execution_status,
            context=f"contract_runtime_case:{self.case_id}.execution_status",
        )
        outcome = _text(
            self.outcome,
            context=f"contract_runtime_case:{self.case_id}.outcome",
        )
        if status not in CONTRACT_RUNTIME_EXECUTION_STATES:
            raise ContractRuntimeEvidenceError(f"unknown contract runtime execution state: {status}")
        if outcome not in CONTRACT_RUNTIME_OUTCOMES:
            raise ContractRuntimeEvidenceError(f"unknown contract runtime outcome: {outcome}")
        object.__setattr__(self, "execution_status", status)
        object.__setattr__(self, "outcome", outcome)
        if self.cleanup_verified is not None and not isinstance(self.cleanup_verified, bool):
            raise ContractRuntimeEvidenceError("contract_runtime_case.cleanup_verified must be boolean or null")

        if not self.planned and (self.selected or status != CONTRACT_RUNTIME_EXECUTION_NOT_RUN):
            raise ContractRuntimeEvidenceError(
                f"unplanned contract case {self.case_id} cannot be selected or executed"
            )
        if not self.selected and status != CONTRACT_RUNTIME_EXECUTION_NOT_RUN:
            raise ContractRuntimeEvidenceError(
                f"unselected contract case {self.case_id} cannot be executed or reused"
            )
        if status == CONTRACT_RUNTIME_EXECUTION_NOT_RUN and outcome != CONTRACT_RUNTIME_OUTCOME_NOT_RUN:
            raise ContractRuntimeEvidenceError(
                f"not_run contract case {self.case_id} must have not_run outcome"
            )
        if status == CONTRACT_RUNTIME_EXECUTION_NOT_RUN and (
            self.result_fingerprint
            or self.producer_receipt_id
            or self.producer_receipt_fingerprint
            or self.result_path
            or self.producer_receipt_path
        ):
            raise ContractRuntimeEvidenceError(
                f"not_run contract case {self.case_id} cannot carry an artifact or receipt"
            )
        if status != CONTRACT_RUNTIME_EXECUTION_NOT_RUN and outcome == CONTRACT_RUNTIME_OUTCOME_NOT_RUN:
            raise ContractRuntimeEvidenceError(
                f"contract case {self.case_id} has execution evidence without a terminal outcome"
            )
        if status != CONTRACT_RUNTIME_EXECUTION_NOT_RUN and not self.result_fingerprint.strip():
            raise ContractRuntimeEvidenceError(
                f"executed contract case {self.case_id} requires a result fingerprint"
            )
        # Missing reuse identities are reconciled as typed blockers below;
        # they must not disappear through an exception or a synthetic pass.
        if outcome != CONTRACT_RUNTIME_OUTCOME_PASSED and not self.reason.strip():
            raise ContractRuntimeEvidenceError(
                f"contract runtime outcome {outcome} for {self.case_id} requires a reason"
            )

    @property
    def executed(self) -> bool:
        return self.execution_status == CONTRACT_RUNTIME_EXECUTION_EXECUTED

    @property
    def reused(self) -> bool:
        return self.execution_status == CONTRACT_RUNTIME_EXECUTION_REUSED

    @property
    def not_run(self) -> bool:
        return self.execution_status == CONTRACT_RUNTIME_EXECUTION_NOT_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "required": self.required,
            "model_id": self.model_id,
            "interaction_group_id": self.interaction_group_id,
            "generation_kind": self.generation_kind,
            "expected_status": self.expected_status,
            "planned": self.planned,
            "selected": self.selected,
            "execution_status": self.execution_status,
            "executed": self.executed,
            "reused": self.reused,
            "not_run": self.not_run,
            "outcome": self.outcome,
            "reason": self.reason,
            "result_fingerprint": self.result_fingerprint,
            "observed_status": self.observed_status,
            "producer_receipt_id": self.producer_receipt_id,
            "result_path": self.result_path,
            "producer_receipt_fingerprint": self.producer_receipt_fingerprint,
            "producer_receipt_path": self.producer_receipt_path,
            "reuse_identity": self.reuse_identity,
            "source_fingerprint": self.source_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "terminal_state": self.terminal_state,
            "cleanup_state": self.cleanup_state,
            "cleanup_verified": self.cleanup_verified,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ContractRuntimeCaseEvidence":
        fields = (
            "case_id",
            "required",
            "model_id",
            "interaction_group_id",
            "generation_kind",
            "expected_status",
            "planned",
            "selected",
            "execution_status",
            "executed",
            "reused",
            "not_run",
            "outcome",
            "reason",
            "result_fingerprint",
            "observed_status",
            "producer_receipt_id",
            "result_path",
            "producer_receipt_fingerprint",
            "producer_receipt_path",
            "reuse_identity",
            "source_fingerprint",
            "model_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
            "terminal_state",
            "cleanup_state",
            "cleanup_verified",
        )
        data = _strict_object(value, context="contract runtime case", required=fields)
        case = cls(
            case_id=data["case_id"],
            required=data["required"],
            model_id=data["model_id"],
            interaction_group_id=data["interaction_group_id"],
            generation_kind=data["generation_kind"],
            expected_status=data["expected_status"],
            planned=data["planned"],
            selected=data["selected"],
            execution_status=data["execution_status"],
            outcome=data["outcome"],
            reason=data["reason"],
            result_fingerprint=data["result_fingerprint"],
            observed_status=data["observed_status"],
            producer_receipt_id=data["producer_receipt_id"],
            result_path=data["result_path"],
            producer_receipt_fingerprint=data["producer_receipt_fingerprint"],
            producer_receipt_path=data["producer_receipt_path"],
            reuse_identity=data["reuse_identity"],
            source_fingerprint=data["source_fingerprint"],
            model_fingerprint=data["model_fingerprint"],
            toolchain_fingerprint=data["toolchain_fingerprint"],
            environment_fingerprint=data["environment_fingerprint"],
            terminal_state=data["terminal_state"],
            cleanup_state=data["cleanup_state"],
            cleanup_verified=data["cleanup_verified"],
        )
        if (
            data["executed"] is not case.executed
            or data["reused"] is not case.reused
            or data["not_run"] is not case.not_run
        ):
            raise ContractRuntimeEvidenceError(
                f"derived execution fields mismatch for contract case {case.case_id}"
            )
        return case


@dataclass(frozen=True)
class ContractRuntimeFinding:
    """One finite-case execution reconciliation gap."""

    code: str
    message: str
    severity: str = "blocker"
    case_id: str = ""

    def __post_init__(self) -> None:
        _text(self.code, context="contract_runtime_finding.code")
        _text(self.message, context="contract_runtime_finding.message")
        if self.severity not in CONTRACT_RUNTIME_FINDING_SEVERITIES:
            raise ContractRuntimeEvidenceError(
                f"unknown contract runtime finding severity: {self.severity}"
            )
        _text(self.case_id, context="contract_runtime_finding.case_id", allow_empty=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "case_id": self.case_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ContractRuntimeFinding":
        fields = ("code", "message", "severity", "case_id")
        data = _strict_object(value, context="contract runtime finding", required=fields)
        return cls(**{name: data[name] for name in fields})


def _count_projection(cases: Sequence[ContractRuntimeCaseEvidence]) -> dict[str, int]:
    planned = tuple(item for item in cases if item.planned)
    return {
        "planned_count": len(planned),
        "selected_count": sum(item.selected for item in planned),
        "explicitly_not_selected_count": sum(not item.selected for item in planned),
        "executed_count": sum(item.executed for item in planned),
        "reused_count": sum(item.reused for item in planned),
        "not_run_count": sum(item.not_run for item in planned),
        "passed_count": sum(item.outcome == CONTRACT_RUNTIME_OUTCOME_PASSED for item in planned),
        "failed_count": sum(item.outcome == CONTRACT_RUNTIME_OUTCOME_FAILED for item in planned),
        "skipped_count": sum(item.outcome == CONTRACT_RUNTIME_OUTCOME_SKIPPED for item in planned),
        "xfailed_count": sum(item.outcome == CONTRACT_RUNTIME_OUTCOME_XFAILED for item in planned),
        "xpassed_count": sum(item.outcome == CONTRACT_RUNTIME_OUTCOME_XPASSED for item in planned),
    }


def contract_exhaustion_report_fingerprint(report: ContractExhaustionReport) -> str:
    """Return the current static report identity consumed by runtime evidence."""

    if not isinstance(report, ContractExhaustionReport):
        raise ContractRuntimeEvidenceError("report must be a ContractExhaustionReport")
    return canonical_identity({"contract_exhaustion_report": report.to_dict()})


@dataclass(frozen=True)
class ContractRuntimeEvidenceReport:
    """Exact runtime reconciliation for one finite contract-case inventory."""

    execution_id: str
    plan_id: str
    contract_report_fingerprint: str
    coverage_universe_id: str
    coverage_universe_fingerprint: str
    requested_case_ids: tuple[str, ...]
    required_case_ids: tuple[str, ...]
    cases: tuple[ContractRuntimeCaseEvidence, ...]
    findings: tuple[ContractRuntimeFinding, ...]
    claim_boundary: str
    execution_owner_id: str = ""
    environment_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    command: tuple[str, ...] = ()
    declared_parent_counts: Mapping[str, int] | None = None
    declared_parent_status: str = ""

    def __post_init__(self) -> None:
        _text(self.execution_id, context="contract_runtime_evidence.execution_id")
        _text(self.plan_id, context="contract_runtime_evidence.plan_id")
        _text(
            self.contract_report_fingerprint,
            context="contract_runtime_evidence.contract_report_fingerprint",
        )
        _text(
            self.coverage_universe_id,
            context="contract_runtime_evidence.coverage_universe_id",
            allow_empty=True,
        )
        _text(
            self.coverage_universe_fingerprint,
            context="contract_runtime_evidence.coverage_universe_fingerprint",
            allow_empty=True,
        )
        object.__setattr__(
            self,
            "requested_case_ids",
            _normalize_ids(self.requested_case_ids, context="requested_case_ids"),
        )
        object.__setattr__(
            self,
            "required_case_ids",
            _normalize_ids(self.required_case_ids, context="required_case_ids"),
        )
        if not isinstance(self.cases, tuple):
            object.__setattr__(self, "cases", tuple(self.cases))
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "cases",
            tuple(sorted(self.cases, key=lambda item: item.case_id)),
        )
        object.__setattr__(
            self,
            "findings",
            tuple(
                sorted(
                    self.findings,
                    key=lambda item: (item.severity, item.code, item.case_id, item.message),
                )
            ),
        )
        _text(self.claim_boundary, context="contract_runtime_evidence.claim_boundary")
        for name in (
            "execution_owner_id",
            "environment_fingerprint",
            "toolchain_fingerprint",
            "declared_parent_status",
        ):
            _text(
                getattr(self, name),
                context=f"contract_runtime_evidence.{name}",
                allow_empty=True,
            )
        object.__setattr__(self, "command", tuple(str(item) for item in self.command))
        object.__setattr__(self, "declared_parent_counts", _normalize_counts(self.declared_parent_counts))
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ContractRuntimeEvidenceError("contract runtime evidence contains duplicate cases")
        if not set(self.required_case_ids).issubset(set(case_ids)):
            raise ContractRuntimeEvidenceError(
                "required contract case ids must be present in the case evidence rows"
            )
        counts = _count_projection(self.cases)
        if counts["planned_count"] != counts["executed_count"] + counts["reused_count"] + counts["not_run_count"]:
            raise ContractRuntimeEvidenceError(
                "contract runtime evidence planned/executed/reused/not_run accounting is inconsistent"
            )
        if counts["planned_count"] != counts["selected_count"] + counts["explicitly_not_selected_count"]:
            raise ContractRuntimeEvidenceError(
                "contract runtime evidence planned/selected/explicitly_not_selected accounting is inconsistent"
            )

    @property
    def counts(self) -> dict[str, int]:
        return _count_projection(self.cases)

    @property
    def ok(self) -> bool:
        return not any(item.severity == "blocker" for item in self.findings)

    @property
    def status(self) -> str:
        return "complete" if self.ok else "blocked"

    @property
    def fingerprint(self) -> str:
        return canonical_identity(self._identity_payload())

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": CONTRACT_RUNTIME_EVIDENCE_SCHEMA,
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "contract_report_fingerprint": self.contract_report_fingerprint,
            "coverage_universe_id": self.coverage_universe_id,
            "coverage_universe_fingerprint": self.coverage_universe_fingerprint,
            "requested_case_ids": list(self.requested_case_ids),
            "required_case_ids": list(self.required_case_ids),
            "cases": [item.to_dict() for item in self.cases],
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
            "execution_owner_id": self.execution_owner_id,
            "environment_fingerprint": self.environment_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "command": list(self.command),
            "declared_parent_counts": dict(self.declared_parent_counts or {}),
            "declared_parent_status": self.declared_parent_status,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._identity_payload(),
            "status": self.status,
            "ok": self.ok,
            "counts": self.counts,
            "fingerprint": self.fingerprint,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False) + "\n"

    def format_text(self) -> str:
        lines = [
            "=== flowguard contract runtime evidence ===",
            f"execution_id: {self.execution_id}",
            f"plan_id: {self.plan_id}",
            f"status: {self.status}",
            f"claim_boundary: {self.claim_boundary}",
            f"cases: {self.counts['planned_count']}",
        ]
        for finding in self.findings:
            target = finding.case_id or "-"
            lines.append(f"- {finding.severity}: {finding.code} [{target}] {finding.message}")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, value: Any) -> "ContractRuntimeEvidenceReport":
        fields = (
            "schema_version",
            "execution_id",
            "plan_id",
            "contract_report_fingerprint",
            "coverage_universe_id",
            "coverage_universe_fingerprint",
            "requested_case_ids",
            "required_case_ids",
            "cases",
            "findings",
            "claim_boundary",
            "execution_owner_id",
            "environment_fingerprint",
            "toolchain_fingerprint",
            "command",
            "declared_parent_counts",
            "declared_parent_status",
            "status",
            "ok",
            "counts",
            "fingerprint",
        )
        data = _strict_object(value, context="contract runtime evidence", required=fields)
        if data["schema_version"] != CONTRACT_RUNTIME_EVIDENCE_SCHEMA:
            raise ContractRuntimeEvidenceError("contract runtime evidence schema is not current")
        for name in ("requested_case_ids", "required_case_ids", "cases", "findings", "command"):
            if not isinstance(data[name], list):
                raise ContractRuntimeEvidenceError(f"contract_runtime_evidence.{name} must be an array")
        report = cls(
            execution_id=data["execution_id"],
            plan_id=data["plan_id"],
            contract_report_fingerprint=data["contract_report_fingerprint"],
            coverage_universe_id=data["coverage_universe_id"],
            coverage_universe_fingerprint=data["coverage_universe_fingerprint"],
            requested_case_ids=_strings(data["requested_case_ids"], context="requested_case_ids"),
            required_case_ids=_strings(data["required_case_ids"], context="required_case_ids"),
            cases=tuple(ContractRuntimeCaseEvidence.from_dict(item) for item in data["cases"]),
            findings=tuple(ContractRuntimeFinding.from_dict(item) for item in data["findings"]),
            claim_boundary=data["claim_boundary"],
            execution_owner_id=data["execution_owner_id"],
            environment_fingerprint=data["environment_fingerprint"],
            toolchain_fingerprint=data["toolchain_fingerprint"],
            command=_strings(data["command"], context="command", allow_duplicates=True, allow_empty=True),
            declared_parent_counts=data["declared_parent_counts"],
            declared_parent_status=data["declared_parent_status"],
        )
        if report.status != data["status"] or report.ok is not data["ok"]:
            raise ContractRuntimeEvidenceError("contract runtime status projection mismatch")
        if report.counts != data["counts"]:
            raise ContractRuntimeEvidenceError("contract runtime count projection mismatch")
        if report.fingerprint != data["fingerprint"]:
            raise ContractRuntimeEvidenceError("contract runtime evidence fingerprint mismatch")
        return report


def _coerce_result(value: Any, *, context: str) -> ContractRuntimeResult:
    if isinstance(value, ContractRuntimeResult):
        return value
    if not isinstance(value, Mapping):
        raise ContractRuntimeEvidenceError(f"{context} must be a ContractRuntimeResult or object")
    return ContractRuntimeResult.from_dict(value)


def _normalize_rows(value: Mapping[str, Any] | None, *, context: str) -> dict[str, ContractRuntimeResult]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractRuntimeEvidenceError(f"{context} must be an object keyed by case id")
    result: dict[str, ContractRuntimeResult] = {}
    for raw_case_id, raw_result in value.items():
        case_id = _text(raw_case_id, context=f"{context} case id")
        if case_id in result:
            raise ContractRuntimeEvidenceError(f"{context} contains duplicate case id: {case_id}")
        result[case_id] = _coerce_result(raw_result, context=f"{context}[{case_id}]")
    return result


def _append_finding(
    findings: list[ContractRuntimeFinding],
    code: str,
    message: str,
    *,
    severity: str = "blocker",
    case_id: str = "",
) -> None:
    findings.append(
        ContractRuntimeFinding(
            code=code,
            message=message,
            severity=severity,
            case_id=case_id,
        )
    )


def _result_integrity_findings(
    result: ContractRuntimeResult,
    *,
    execution_status: str,
    case_id: str,
    findings: list[ContractRuntimeFinding],
    require_verifiable_material: bool,
    report_execution_owner_id: str,
    report_environment_fingerprint: str,
    report_toolchain_fingerprint: str,
    report_command: Sequence[str],
) -> None:
    """Verify result/receipt material before projecting a contract case."""

    if execution_status not in {
        CONTRACT_RUNTIME_EXECUTION_EXECUTED,
        CONTRACT_RUNTIME_EXECUTION_REUSED,
    }:
        return

    if not is_sha256_fingerprint(result.result_fingerprint):
        _append_finding(
            findings,
            "contract_result_fingerprint_invalid",
            "contract runtime result fingerprint is not a canonical SHA-256 digest",
            case_id=case_id,
        )
    if execution_status == CONTRACT_RUNTIME_EXECUTION_REUSED:
        if not result.producer_receipt_id.strip():
            _append_finding(
                findings,
                "contract_reuse_producer_receipt_missing",
                "reused contract case has no producer receipt identity",
                case_id=case_id,
            )
        if not result.producer_receipt_fingerprint.strip():
            _append_finding(
                findings,
                "contract_reuse_receipt_fingerprint_missing",
                "reused contract case has no producer receipt canonical fingerprint",
                case_id=case_id,
            )
        elif not is_sha256_fingerprint(result.producer_receipt_fingerprint):
            _append_finding(
                findings,
                "contract_reuse_receipt_fingerprint_invalid",
                "reused contract producer receipt fingerprint is not canonical",
                case_id=case_id,
            )
        if not result.reuse_identity.strip():
            _append_finding(
                findings,
                "contract_reuse_identity_missing",
                "reused contract case has no frozen reuse identity",
                case_id=case_id,
            )

    if result.cleanup_verified is False or result.cleanup_state.casefold() in {
        "cleanup-unconfirmed",
        "unconfirmed",
        "unknown",
        "timeout",
    }:
        _append_finding(
            findings,
            "contract_cleanup_unconfirmed",
            "contract execution cleanup was not confirmed",
            case_id=case_id,
        )

    if not require_verifiable_material:
        return

    artifact = ProofArtifactRef(
        artifact_id=f"contract-case:{case_id}",
        producer_route="contract_runtime_evidence",
        command=" ".join(str(item) for item in (report_command or ("contract-runtime", case_id))),
        result_path=result.result_path,
        result_status="passed" if result.outcome == CONTRACT_RUNTIME_OUTCOME_PASSED else result.outcome,
        exit_code=0 if result.outcome == CONTRACT_RUNTIME_OUTCOME_PASSED else 1,
        started_at="1970-01-01T00:00:00+00:00",
        finished_at="1970-01-01T00:00:01+00:00",
        subject_id=case_id,
        subject_fingerprint=result.source_fingerprint or "sha256:" + "0" * 64,
        artifact_fingerprints={"result": result.result_fingerprint},
        assertion_scope="external_contract",
        receipt_id=result.producer_receipt_id,
        receipt_path=result.producer_receipt_path,
        receipt_fingerprint=result.producer_receipt_fingerprint,
        execution_owner_id=(
            ""
            if execution_status == CONTRACT_RUNTIME_EXECUTION_REUSED
            else report_execution_owner_id
        ),
        source_fingerprint=result.source_fingerprint,
        model_fingerprint=result.model_fingerprint,
        toolchain_fingerprint=result.toolchain_fingerprint or report_toolchain_fingerprint,
        environment_fingerprint=result.environment_fingerprint or report_environment_fingerprint,
        result_fingerprint=result.result_fingerprint,
        terminal_state=result.terminal_state,
        cleanup_state=result.cleanup_state,
        cleanup_verified=result.cleanup_verified,
    )
    for code, message in proof_artifact_integrity_gap_codes(
        artifact,
        expected_receipt_id=result.producer_receipt_id,
        expected_owner_id=(
            ""
            if execution_status == CONTRACT_RUNTIME_EXECUTION_REUSED
            else report_execution_owner_id
        ),
        expected_source_fingerprint=result.source_fingerprint,
        expected_model_fingerprint=result.model_fingerprint,
        expected_toolchain_fingerprint=result.toolchain_fingerprint or report_toolchain_fingerprint,
        expected_environment_fingerprint=result.environment_fingerprint or report_environment_fingerprint,
        expected_result_fingerprint=result.result_fingerprint,
        expected_reuse_identity=(
            result.reuse_identity
            if execution_status == CONTRACT_RUNTIME_EXECUTION_REUSED
            else ""
        ),
        require_receipt=True,
        require_cleanup_confirmation=True,
    ):
        _append_finding(findings, code, message, case_id=case_id)


def reconcile_contract_exhaustion_execution(
    report: ContractExhaustionReport,
    *,
    execution_id: str,
    result_rows: Mapping[str, Any] | None = None,
    reused_rows: Mapping[str, Any] | None = None,
    requested_case_ids: Sequence[str] | None = None,
    claim_boundary: str = "declared_complete",
    execution_owner_id: str = "",
    environment_fingerprint: str = "",
    toolchain_fingerprint: str = "",
    command: Sequence[str] = (),
    declared_parent_counts: Mapping[str, Any] | None = None,
    declared_parent_status: str = "",
    require_verifiable_material: bool = False,
) -> ContractRuntimeEvidenceReport:
    """Reconcile native terminal rows with one finite contract report.

    The function consumes results; it does not call pytest, a provider, or a
    target application.  ``None`` for ``requested_case_ids`` selects every
    required generated case.  Passing an explicit sequence is an execution
    owner's declaration, so omitted required cases become visible blockers.
    """

    if not isinstance(report, ContractExhaustionReport):
        raise ContractRuntimeEvidenceError("report must be a ContractExhaustionReport")
    claim_boundary = _text(claim_boundary, context="claim_boundary")
    result_rows_normalized = _normalize_rows(result_rows, context="result_rows")
    reused_rows_normalized = _normalize_rows(reused_rows, context="reused_rows")
    findings: list[ContractRuntimeFinding] = []

    if not report.ok:
        _append_finding(
            findings,
            "contract_report_not_ready",
            "static ContractExhaustionReport contains blockers and cannot support runtime completion",
        )
    if claim_boundary in _COMPLETE_CLAIM_BOUNDARIES and report.coverage_universe is None:
        _append_finding(
            findings,
            "contract_coverage_universe_missing",
            "a complete contract runtime claim requires the static finite coverage universe",
        )

    # generated_cases is the canonical case source.  A combination projection
    # may add an id in a handoff report; retain it as an inventory row rather
    # than silently dropping it, while exposing a projection mismatch.
    specs: dict[str, dict[str, Any]] = {}
    ordered_case_ids: list[str] = []
    for case in report.generated_cases:
        if case.case_id in specs:
            _append_finding(
                findings,
                "duplicate_contract_case_inventory",
                "static report contains the same generated contract case more than once",
                case_id=case.case_id,
            )
            continue
        specs[case.case_id] = {
            "required": bool(case.required),
            "model_id": case.model_id,
            "interaction_group_id": case.interaction_group_id,
            "generation_kind": case.generation_kind,
            "expected_status": case.expected_status,
        }
        ordered_case_ids.append(case.case_id)
    for combination in report.combination_cases:
        current = specs.get(combination.case_id)
        if current is None:
            specs[combination.case_id] = {
                "required": True,
                "model_id": combination.model_id,
                "interaction_group_id": combination.interaction_group_id,
                "generation_kind": "local_cartesian",
                "expected_status": combination.expected_status,
            }
            ordered_case_ids.append(combination.case_id)
            continue
        if (
            current["model_id"] != combination.model_id
            or current["interaction_group_id"] != combination.interaction_group_id
        ):
            _append_finding(
                findings,
                "contract_case_projection_mismatch",
                "combination projection disagrees with its generated contract case",
                case_id=combination.case_id,
            )

    required_case_ids = tuple(
        case_id for case_id in ordered_case_ids if specs[case_id]["required"]
    )
    requested_raw = required_case_ids if requested_case_ids is None else tuple(requested_case_ids)
    requested = _normalize_ids(
        requested_raw,
        context="requested_case_ids",
        allow_duplicates=True,
    )
    requested_unique: list[str] = []
    for case_id in requested:
        if case_id in requested_unique:
            _append_finding(
                findings,
                "duplicate_requested_contract_case",
                "native execution request repeats one contract case id",
                case_id=case_id,
            )
            continue
        requested_unique.append(case_id)
        if case_id not in specs:
            _append_finding(
                findings,
                "requested_contract_case_not_in_inventory",
                "native execution request names a case absent from the static contract report",
                case_id=case_id,
            )
    requested_set = set(requested_unique)

    for case_id in result_rows_normalized:
        if case_id not in specs:
            _append_finding(
                findings,
                "result_contract_case_not_in_inventory",
                "executed result row has no matching generated contract case",
                case_id=case_id,
            )
    for case_id in reused_rows_normalized:
        if case_id not in specs:
            _append_finding(
                findings,
                "reused_contract_case_not_in_inventory",
                "reused result row has no matching generated contract case",
                case_id=case_id,
            )

    cases: list[ContractRuntimeCaseEvidence] = []
    for case_id in ordered_case_ids:
        spec = specs[case_id]
        selected = case_id in requested_set
        result = result_rows_normalized.get(case_id)
        reused = reused_rows_normalized.get(case_id)
        if not selected:
            if result is not None or reused is not None:
                _append_finding(
                    findings,
                    "result_for_not_selected_contract_case",
                    "a native result row was supplied for a contract case explicitly not selected",
                    case_id=case_id,
                )
            case = ContractRuntimeCaseEvidence(
                case_id=case_id,
                required=spec["required"],
                model_id=spec["model_id"],
                interaction_group_id=spec["interaction_group_id"],
                generation_kind=spec["generation_kind"],
                expected_status=spec["expected_status"],
                planned=True,
                selected=False,
                execution_status=CONTRACT_RUNTIME_EXECUTION_NOT_RUN,
                outcome=CONTRACT_RUNTIME_OUTCOME_NOT_RUN,
                reason="contract case was explicitly not selected by the native execution owner",
            )
            if spec["required"]:
                _append_finding(
                    findings,
                    "required_contract_case_not_selected",
                    "required generated contract case was not selected for execution",
                    case_id=case_id,
                )
            cases.append(case)
            continue

        if result is not None and reused is not None:
            _append_finding(
                findings,
                "duplicate_contract_result_source",
                "one contract case has both executed and reused result rows",
                case_id=case_id,
            )
            cases.append(
                ContractRuntimeCaseEvidence(
                    case_id=case_id,
                    required=spec["required"],
                    model_id=spec["model_id"],
                    interaction_group_id=spec["interaction_group_id"],
                    generation_kind=spec["generation_kind"],
                    expected_status=spec["expected_status"],
                    planned=True,
                    selected=True,
                    execution_status=CONTRACT_RUNTIME_EXECUTION_NOT_RUN,
                    outcome=CONTRACT_RUNTIME_OUTCOME_NOT_RUN,
                    reason="executed and reused result sources conflict",
                )
            )
            continue

        source = result if result is not None else reused
        execution_status = (
            CONTRACT_RUNTIME_EXECUTION_EXECUTED
            if result is not None
            else CONTRACT_RUNTIME_EXECUTION_REUSED
            if reused is not None
            else CONTRACT_RUNTIME_EXECUTION_NOT_RUN
        )
        if source is None:
            case = ContractRuntimeCaseEvidence(
                case_id=case_id,
                required=spec["required"],
                model_id=spec["model_id"],
                interaction_group_id=spec["interaction_group_id"],
                generation_kind=spec["generation_kind"],
                expected_status=spec["expected_status"],
                planned=True,
                selected=True,
                execution_status=CONTRACT_RUNTIME_EXECUTION_NOT_RUN,
                outcome=CONTRACT_RUNTIME_OUTCOME_NOT_RUN,
                reason="selected contract case has no terminal native result row",
            )
            _append_finding(
                findings,
                "contract_case_not_run",
                case.reason,
                severity="blocker" if spec["required"] or claim_boundary in _COMPLETE_CLAIM_BOUNDARIES else "warning",
                case_id=case_id,
            )
            cases.append(case)
            continue

        if source.outcome == CONTRACT_RUNTIME_OUTCOME_NOT_RUN:
            _append_finding(
                findings,
                "terminal_contract_result_is_not_run",
                "a selected result source declares not_run instead of a terminal executed/reused outcome",
                case_id=case_id,
            )
            case = ContractRuntimeCaseEvidence(
                case_id=case_id,
                required=spec["required"],
                model_id=spec["model_id"],
                interaction_group_id=spec["interaction_group_id"],
                generation_kind=spec["generation_kind"],
                expected_status=spec["expected_status"],
                planned=True,
                selected=True,
                execution_status=CONTRACT_RUNTIME_EXECUTION_NOT_RUN,
                outcome=CONTRACT_RUNTIME_OUTCOME_NOT_RUN,
                reason=source.reason or "native result source did not complete",
            )
            cases.append(case)
            continue

        _result_integrity_findings(
            source,
            execution_status=execution_status,
            case_id=case_id,
            findings=findings,
            require_verifiable_material=require_verifiable_material,
            report_execution_owner_id=execution_owner_id,
            report_environment_fingerprint=environment_fingerprint,
            report_toolchain_fingerprint=toolchain_fingerprint,
            report_command=command,
        )

        if (
            spec["expected_status"]
            and source.observed_status
            and spec["expected_status"] != source.observed_status
        ):
            _append_finding(
                findings,
                "contract_oracle_status_mismatch",
                "observed native oracle status differs from the generated case expectation",
                case_id=case_id,
            )
        case = ContractRuntimeCaseEvidence(
            case_id=case_id,
            required=spec["required"],
            model_id=spec["model_id"],
            interaction_group_id=spec["interaction_group_id"],
            generation_kind=spec["generation_kind"],
            expected_status=spec["expected_status"],
            planned=True,
            selected=True,
            execution_status=execution_status,
            outcome=source.outcome,
            reason=source.reason,
            result_fingerprint=source.result_fingerprint,
            observed_status=source.observed_status,
            producer_receipt_id=source.producer_receipt_id,
            result_path=source.result_path,
            producer_receipt_fingerprint=source.producer_receipt_fingerprint,
            producer_receipt_path=source.producer_receipt_path,
            reuse_identity=source.reuse_identity,
            source_fingerprint=source.source_fingerprint,
            model_fingerprint=source.model_fingerprint,
            toolchain_fingerprint=source.toolchain_fingerprint,
            environment_fingerprint=source.environment_fingerprint,
            terminal_state=source.terminal_state,
            cleanup_state=source.cleanup_state,
            cleanup_verified=source.cleanup_verified,
        )
        if case.outcome != CONTRACT_RUNTIME_OUTCOME_PASSED:
            _append_finding(
                findings,
                f"contract_case_{case.outcome}",
                case.reason,
                severity="blocker" if spec["required"] and claim_boundary in _COMPLETE_CLAIM_BOUNDARIES else "warning",
                case_id=case_id,
            )
        cases.append(case)

    has_execution = any(case.executed or case.reused for case in cases)
    if has_execution and not execution_owner_id.strip():
        _append_finding(
            findings,
            "execution_owner_missing",
            "executed contract evidence requires the native execution owner identity",
        )
    if has_execution and not tuple(command):
        _append_finding(
            findings,
            "execution_command_missing",
            "executed contract evidence requires the native command identity",
        )

    preliminary = ContractRuntimeEvidenceReport(
        execution_id=execution_id,
        plan_id=report.plan_id,
        contract_report_fingerprint=contract_exhaustion_report_fingerprint(report),
        coverage_universe_id=report.coverage_universe.universe_id if report.coverage_universe else "",
        coverage_universe_fingerprint=(
            canonical_identity(report.coverage_universe.to_dict())
            if report.coverage_universe is not None
            else ""
        ),
        requested_case_ids=tuple(requested_unique),
        required_case_ids=required_case_ids,
        cases=tuple(cases),
        findings=tuple(findings),
        claim_boundary=claim_boundary,
        execution_owner_id=execution_owner_id,
        environment_fingerprint=environment_fingerprint,
        toolchain_fingerprint=toolchain_fingerprint,
        command=tuple(command),
        declared_parent_counts=declared_parent_counts,
        declared_parent_status=declared_parent_status,
    )

    final_findings = list(preliminary.findings)
    for field, expected in preliminary.declared_parent_counts.items():
        actual = preliminary.counts[field]
        if actual != expected:
            final_findings.append(
                ContractRuntimeFinding(
                    code="parent_case_count_mismatch",
                    message=f"parent declared {field}={expected}, but cases reconcile to {actual}",
                    severity="blocker",
                )
            )
    parent_status = preliminary.declared_parent_status.strip().lower()
    if parent_status in {"pass", "passed", "green"} and any(
        case.planned and (case.outcome != CONTRACT_RUNTIME_OUTCOME_PASSED or not case.selected)
        for case in preliminary.cases
    ):
        final_findings.append(
            ContractRuntimeFinding(
                code="parent_case_status_mismatch",
                message="parent reports pass while one planned contract case is not a selected pass",
                severity="blocker",
            )
        )
    if final_findings != list(preliminary.findings):
        preliminary = ContractRuntimeEvidenceReport(
            execution_id=preliminary.execution_id,
            plan_id=preliminary.plan_id,
            contract_report_fingerprint=preliminary.contract_report_fingerprint,
            coverage_universe_id=preliminary.coverage_universe_id,
            coverage_universe_fingerprint=preliminary.coverage_universe_fingerprint,
            requested_case_ids=preliminary.requested_case_ids,
            required_case_ids=preliminary.required_case_ids,
            cases=preliminary.cases,
            findings=tuple(final_findings),
            claim_boundary=preliminary.claim_boundary,
            execution_owner_id=preliminary.execution_owner_id,
            environment_fingerprint=preliminary.environment_fingerprint,
            toolchain_fingerprint=preliminary.toolchain_fingerprint,
            command=preliminary.command,
            declared_parent_counts=preliminary.declared_parent_counts,
            declared_parent_status=preliminary.declared_parent_status,
        )
    return preliminary


def serialize_contract_runtime_evidence(report: ContractRuntimeEvidenceReport) -> bytes:
    """Return canonical UTF-8 bytes without writing an artifact."""

    return canonical_json_bytes(report.to_dict())


def write_contract_runtime_evidence(
    report: ContractRuntimeEvidenceReport,
    path: str | Path,
) -> Path:
    """Explicitly write one canonical runtime contract evidence artifact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_contract_runtime_evidence(report) + b"\n")
    return target


def load_contract_runtime_evidence(path: str | Path) -> ContractRuntimeEvidenceReport:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractRuntimeEvidenceError(f"cannot load contract runtime evidence: {exc}") from exc
    return ContractRuntimeEvidenceReport.from_dict(value)


__all__ = [
    "CONTRACT_RUNTIME_EVIDENCE_SCHEMA",
    "CONTRACT_RUNTIME_EXECUTION_EXECUTED",
    "CONTRACT_RUNTIME_EXECUTION_REUSED",
    "CONTRACT_RUNTIME_EXECUTION_NOT_RUN",
    "CONTRACT_RUNTIME_EXECUTION_STATES",
    "CONTRACT_RUNTIME_OUTCOME_PASSED",
    "CONTRACT_RUNTIME_OUTCOME_FAILED",
    "CONTRACT_RUNTIME_OUTCOME_SKIPPED",
    "CONTRACT_RUNTIME_OUTCOME_XFAILED",
    "CONTRACT_RUNTIME_OUTCOME_XPASSED",
    "CONTRACT_RUNTIME_OUTCOME_NOT_RUN",
    "CONTRACT_RUNTIME_OUTCOMES",
    "CONTRACT_RUNTIME_FINDING_SEVERITIES",
    "CONTRACT_RUNTIME_COUNT_FIELDS",
    "ContractRuntimeEvidenceError",
    "ContractRuntimeResult",
    "ContractRuntimeCaseEvidence",
    "ContractRuntimeFinding",
    "ContractRuntimeEvidenceReport",
    "contract_exhaustion_report_fingerprint",
    "reconcile_contract_exhaustion_execution",
    "serialize_contract_runtime_evidence",
    "write_contract_runtime_evidence",
    "load_contract_runtime_evidence",
]
