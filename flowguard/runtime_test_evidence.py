"""Runtime pytest collection and leaf-result reconciliation.

``ProjectTestInventory`` is intentionally a static source inventory.  This
module is its execution-side companion: a native test adapter can pass the
exact node ids collected by pytest and the terminal reports observed for each
node, and FlowGuard will materialize concrete parameterized leaves without
turning a parent summary into child execution evidence.

The module does not import pytest or run a test process.  Process supervision,
receipt publication, and environment identity remain with the native
execution owner.  This boundary keeps collection/result reconciliation useful
to pytest adapters while keeping static inventory and runtime evidence as
separate artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping, Sequence

from .portable_model import canonical_identity, canonical_json_bytes
from .proof_artifact import (
    is_sha256_fingerprint,
    proof_artifact_integrity_gap_codes,
)
from .test_inventory import ProjectTestInventory, test_node_id


RUNTIME_TEST_EVIDENCE_SCHEMA = "flowguard.runtime_test_evidence.v1"

RUNTIME_TEST_EXECUTION_EXECUTED = "executed"
RUNTIME_TEST_EXECUTION_REUSED = "reused"
RUNTIME_TEST_EXECUTION_NOT_RUN = "not_run"
RUNTIME_TEST_EXECUTION_STATES = (
    RUNTIME_TEST_EXECUTION_EXECUTED,
    RUNTIME_TEST_EXECUTION_REUSED,
    RUNTIME_TEST_EXECUTION_NOT_RUN,
)

RUNTIME_TEST_OUTCOME_PASSED = "passed"
RUNTIME_TEST_OUTCOME_FAILED = "failed"
RUNTIME_TEST_OUTCOME_SKIPPED = "skipped"
RUNTIME_TEST_OUTCOME_XFAILED = "xfailed"
RUNTIME_TEST_OUTCOME_XPASSED = "xpassed"
RUNTIME_TEST_OUTCOME_NOT_RUN = "not_run"
RUNTIME_TEST_OUTCOMES = (
    RUNTIME_TEST_OUTCOME_PASSED,
    RUNTIME_TEST_OUTCOME_FAILED,
    RUNTIME_TEST_OUTCOME_SKIPPED,
    RUNTIME_TEST_OUTCOME_XFAILED,
    RUNTIME_TEST_OUTCOME_XPASSED,
    RUNTIME_TEST_OUTCOME_NOT_RUN,
)

RUNTIME_TEST_FINDING_SEVERITIES = ("info", "warning", "blocker")
RUNTIME_TEST_COUNT_FIELDS = (
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


class RuntimeTestEvidenceError(ValueError):
    """Raised when runtime test evidence is not current canonical shape."""


def _text(value: Any, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise RuntimeTestEvidenceError(f"{context} must be {qualifier}")
    return value


def _strings(
    value: Any,
    *,
    context: str,
    allow_duplicates: bool = False,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise RuntimeTestEvidenceError(f"{context} must be an array")
    result = tuple(
        _text(item, context=f"{context}[]", allow_empty=allow_empty)
        for item in value
    )
    if not allow_duplicates and len(result) != len(set(result)):
        raise RuntimeTestEvidenceError(f"{context} contains duplicate values")
    return result


def _strict_object(
    value: Any,
    *,
    context: str,
    required: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeTestEvidenceError(f"{context} must be an object")
    if set(value) != set(required):
        difference = sorted(set(value) ^ set(required))
        raise RuntimeTestEvidenceError(
            f"{context} fields differ from the current schema: {difference}"
        )
    return value


def _normalize_nodeid(value: Any, *, context: str) -> str:
    nodeid = _text(value, context=context).replace("\\", "/")
    try:
        # The static inventory owns the canonical pytest node-id validation.
        test_node_id(nodeid)
    except Exception as exc:
        raise RuntimeTestEvidenceError(f"{context} is not a valid pytest node id") from exc
    return nodeid


def _base_nodeid(nodeid: str) -> str:
    """Return a static node id for one concrete pytest parameter leaf."""

    return nodeid.split("[", 1)[0]


def _parameter_id(nodeid: str) -> str:
    if "[" not in nodeid:
        return ""
    return nodeid.split("[", 1)[1].rsplit("]", 1)[0]


def _matches_static(static_nodeid: str, concrete_nodeid: str) -> bool:
    return concrete_nodeid == static_nodeid or (
        concrete_nodeid.startswith(static_nodeid + "[")
    )


def _normalized_nodeids(
    values: Sequence[str],
    *,
    context: str,
) -> tuple[str, ...]:
    return tuple(
        _normalize_nodeid(value, context=f"{context}[]")
        for value in values
    )


def _finite_duration(value: Any, *, context: str) -> float | None:
    if value is None:
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeTestEvidenceError(f"{context} must be a finite number") from exc
    if not math.isfinite(duration) or duration < 0:
        raise RuntimeTestEvidenceError(f"{context} must be a finite non-negative number")
    return duration


@dataclass(frozen=True)
class RuntimeTestResult:
    """One native terminal result before it is bound to a runtime leaf."""

    outcome: str
    reason: str = ""
    duration_seconds: float | None = None
    # Native adapters may attach the exact output file and producer receipt.
    # These are deliberately carried to the leaf rather than inferred from a
    # parent summary.
    result_path: str = ""
    result_fingerprint: str = ""
    producer_receipt_id: str = ""
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
        outcome = _text(self.outcome, context="runtime_test_result.outcome")
        if outcome not in RUNTIME_TEST_OUTCOMES:
            raise RuntimeTestEvidenceError(f"unknown runtime test outcome: {outcome}")
        object.__setattr__(self, "outcome", outcome)
        _text(self.reason, context="runtime_test_result.reason", allow_empty=True)
        object.__setattr__(
            self,
            "duration_seconds",
            _finite_duration(
                self.duration_seconds,
                context="runtime_test_result.duration_seconds",
            ),
        )
        for name in (
            "result_path",
            "result_fingerprint",
            "producer_receipt_id",
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
            object.__setattr__(self, name, _text(getattr(self, name), context=f"runtime_test_result.{name}", allow_empty=True))
        if self.cleanup_verified is not None and not isinstance(self.cleanup_verified, bool):
            raise RuntimeTestEvidenceError("runtime_test_result.cleanup_verified must be boolean or null")
        if outcome != RUNTIME_TEST_OUTCOME_PASSED and not self.reason.strip():
            raise RuntimeTestEvidenceError(
                f"runtime test outcome {outcome} requires a reason"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "duration_seconds": self.duration_seconds,
            "result_path": self.result_path,
            "result_fingerprint": self.result_fingerprint,
            "producer_receipt_id": self.producer_receipt_id,
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
    def from_dict(cls, value: Any) -> "RuntimeTestResult":
        fields = (
            "outcome",
            "reason",
            "duration_seconds",
            "result_path",
            "result_fingerprint",
            "producer_receipt_id",
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
            raise RuntimeTestEvidenceError("runtime test result must be an object")
        unknown = set(value) - set(fields)
        if unknown:
            raise RuntimeTestEvidenceError(f"runtime test result contains unknown fields: {sorted(unknown)}")
        data = {name: value.get(name, "" if name != "cleanup_verified" else None) for name in fields}
        return cls(**data)


@dataclass(frozen=True)
class RuntimeTestLeafEvidence:
    """One exact collected pytest node, including parameterized cases."""

    pytest_nodeid: str
    planned: bool
    selected: bool
    execution_status: str
    outcome: str
    reason: str = ""
    duration_seconds: float | None = None
    result_path: str = ""
    result_fingerprint: str = ""
    producer_receipt_id: str = ""
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
        nodeid = _normalize_nodeid(
            self.pytest_nodeid,
            context="runtime_test_leaf.pytest_nodeid",
        )
        object.__setattr__(self, "pytest_nodeid", nodeid)
        if not isinstance(self.planned, bool):
            raise RuntimeTestEvidenceError("runtime_test_leaf.planned must be boolean")
        if not isinstance(self.selected, bool):
            raise RuntimeTestEvidenceError("runtime_test_leaf.selected must be boolean")
        execution_status = _text(
            self.execution_status,
            context=f"runtime_test_leaf:{nodeid}.execution_status",
        )
        if execution_status not in RUNTIME_TEST_EXECUTION_STATES:
            raise RuntimeTestEvidenceError(
                f"unknown runtime test execution status: {execution_status}"
            )
        object.__setattr__(self, "execution_status", execution_status)
        outcome = _text(
            self.outcome,
            context=f"runtime_test_leaf:{nodeid}.outcome",
        )
        if outcome not in RUNTIME_TEST_OUTCOMES:
            raise RuntimeTestEvidenceError(f"unknown runtime test outcome: {outcome}")
        object.__setattr__(self, "outcome", outcome)
        reason = _text(
            self.reason,
            context=f"runtime_test_leaf:{nodeid}.reason",
            allow_empty=True,
        )
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "duration_seconds",
            _finite_duration(
                self.duration_seconds,
                context=f"runtime_test_leaf:{nodeid}.duration_seconds",
            ),
        )
        for name in (
            "result_path",
            "result_fingerprint",
            "producer_receipt_id",
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
            object.__setattr__(self, name, _text(getattr(self, name), context=f"runtime_test_leaf:{nodeid}.{name}", allow_empty=True))
        if self.cleanup_verified is not None and not isinstance(self.cleanup_verified, bool):
            raise RuntimeTestEvidenceError(
                f"runtime_test_leaf:{nodeid}.cleanup_verified must be boolean or null"
            )
        if not self.planned:
            if self.selected or execution_status != RUNTIME_TEST_EXECUTION_NOT_RUN:
                raise RuntimeTestEvidenceError(
                    f"unplanned runtime leaf {nodeid} cannot be selected or executed"
                )
            if outcome != RUNTIME_TEST_OUTCOME_NOT_RUN:
                raise RuntimeTestEvidenceError(
                    f"unplanned runtime leaf {nodeid} cannot carry an outcome"
                )
        elif not self.selected:
            if execution_status != RUNTIME_TEST_EXECUTION_NOT_RUN:
                raise RuntimeTestEvidenceError(
                    f"deselected runtime leaf {nodeid} cannot be executed or reused"
                )
            if outcome != RUNTIME_TEST_OUTCOME_NOT_RUN:
                raise RuntimeTestEvidenceError(
                    f"deselected runtime leaf {nodeid} cannot carry an outcome"
                )

        if execution_status == RUNTIME_TEST_EXECUTION_NOT_RUN:
            if outcome != RUNTIME_TEST_OUTCOME_NOT_RUN:
                raise RuntimeTestEvidenceError(
                    f"not-run runtime leaf {nodeid} must have not_run outcome"
                )
        elif outcome == RUNTIME_TEST_OUTCOME_NOT_RUN:
            raise RuntimeTestEvidenceError(
                f"runtime leaf {nodeid} has execution evidence but no terminal outcome"
            )

        if outcome != RUNTIME_TEST_OUTCOME_PASSED and not reason.strip():
            raise RuntimeTestEvidenceError(
                f"runtime test outcome {outcome} for {nodeid} requires a reason"
            )

    @property
    def leaf_id(self) -> str:
        return test_node_id(self.pytest_nodeid)

    @property
    def base_pytest_nodeid(self) -> str:
        return _base_nodeid(self.pytest_nodeid)

    @property
    def parameter_id(self) -> str:
        return _parameter_id(self.pytest_nodeid)

    @property
    def executed(self) -> bool:
        return self.execution_status == RUNTIME_TEST_EXECUTION_EXECUTED

    @property
    def reused(self) -> bool:
        return self.execution_status == RUNTIME_TEST_EXECUTION_REUSED

    @property
    def not_run(self) -> bool:
        return self.execution_status == RUNTIME_TEST_EXECUTION_NOT_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "pytest_nodeid": self.pytest_nodeid,
            "leaf_id": self.leaf_id,
            "base_pytest_nodeid": self.base_pytest_nodeid,
            "parameter_id": self.parameter_id,
            "planned": self.planned,
            "selected": self.selected,
            "execution_status": self.execution_status,
            "executed": self.executed,
            "reused": self.reused,
            "not_run": self.not_run,
            "outcome": self.outcome,
            "reason": self.reason,
            "duration_seconds": self.duration_seconds,
            "result_path": self.result_path,
            "result_fingerprint": self.result_fingerprint,
            "producer_receipt_id": self.producer_receipt_id,
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
    def from_dict(cls, value: Any) -> "RuntimeTestLeafEvidence":
        fields = (
            "pytest_nodeid",
            "leaf_id",
            "base_pytest_nodeid",
            "parameter_id",
            "planned",
            "selected",
            "execution_status",
            "executed",
            "reused",
            "not_run",
            "outcome",
            "reason",
            "duration_seconds",
            "result_path",
            "result_fingerprint",
            "producer_receipt_id",
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
        data = _strict_object(value, context="runtime test leaf", required=fields)
        leaf = cls(
            pytest_nodeid=data["pytest_nodeid"],
            planned=data["planned"],
            selected=data["selected"],
            execution_status=data["execution_status"],
            outcome=data["outcome"],
            reason=data["reason"],
            duration_seconds=data["duration_seconds"],
            result_path=data["result_path"],
            result_fingerprint=data["result_fingerprint"],
            producer_receipt_id=data["producer_receipt_id"],
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
            data["leaf_id"] != leaf.leaf_id
            or data["base_pytest_nodeid"] != leaf.base_pytest_nodeid
            or data["parameter_id"] != leaf.parameter_id
            or data["executed"] is not leaf.executed
            or data["reused"] is not leaf.reused
            or data["not_run"] is not leaf.not_run
        ):
            raise RuntimeTestEvidenceError("runtime test leaf derived fields mismatch")
        return leaf


@dataclass(frozen=True)
class RuntimeTestFinding:
    """One reconciliation gap that remains visible to the parent gate."""

    code: str
    message: str
    severity: str = "blocker"
    pytest_nodeid: str = ""

    def __post_init__(self) -> None:
        _text(self.code, context="runtime_test_finding.code")
        _text(self.message, context="runtime_test_finding.message")
        if self.severity not in RUNTIME_TEST_FINDING_SEVERITIES:
            raise RuntimeTestEvidenceError(
                f"unknown runtime test finding severity: {self.severity}"
            )
        object.__setattr__(self, "pytest_nodeid", self.pytest_nodeid or "")
        if self.pytest_nodeid:
            object.__setattr__(
                self,
                "pytest_nodeid",
                _normalize_nodeid(
                    self.pytest_nodeid,
                    context="runtime_test_finding.pytest_nodeid",
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "pytest_nodeid": self.pytest_nodeid,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RuntimeTestFinding":
        fields = ("code", "message", "severity", "pytest_nodeid")
        data = _strict_object(value, context="runtime test finding", required=fields)
        return cls(**{name: data[name] for name in fields})


def _count_projection(leaves: Sequence[RuntimeTestLeafEvidence]) -> dict[str, int]:
    planned = tuple(item for item in leaves if item.planned)
    return {
        "planned_count": len(planned),
        "selected_count": sum(item.selected for item in planned),
        "explicitly_not_selected_count": sum(
            not item.selected for item in planned
        ),
        "executed_count": sum(item.executed for item in planned),
        "reused_count": sum(item.reused for item in planned),
        "not_run_count": sum(item.not_run for item in planned),
        "passed_count": sum(
            item.outcome == RUNTIME_TEST_OUTCOME_PASSED for item in planned
        ),
        "failed_count": sum(
            item.outcome == RUNTIME_TEST_OUTCOME_FAILED for item in planned
        ),
        "skipped_count": sum(
            item.outcome == RUNTIME_TEST_OUTCOME_SKIPPED for item in planned
        ),
        "xfailed_count": sum(
            item.outcome == RUNTIME_TEST_OUTCOME_XFAILED for item in planned
        ),
        "xpassed_count": sum(
            item.outcome == RUNTIME_TEST_OUTCOME_XPASSED for item in planned
        ),
    }


def _normalized_declared_counts(value: Mapping[str, Any] | None) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise RuntimeTestEvidenceError("declared_parent_counts must be an object")
    result: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key not in RUNTIME_TEST_COUNT_FIELDS:
            raise RuntimeTestEvidenceError(
                f"unknown declared parent count field: {raw_key}"
            )
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
            raise RuntimeTestEvidenceError(
                f"declared parent count {raw_key} must be a non-negative integer"
            )
        result[key] = int(raw_value)
    return result


@dataclass(frozen=True)
class RuntimeTestEvidenceReport:
    """Reconciled runtime leaves and parent-visible execution accounting."""

    execution_id: str
    inventory_id: str
    inventory_fingerprint: str
    requested_pytest_nodeids: tuple[str, ...]
    collected_pytest_nodeids: tuple[str, ...]
    deselected_pytest_nodeids: tuple[str, ...]
    unrelated_pytest_nodeids: tuple[str, ...]
    leaves: tuple[RuntimeTestLeafEvidence, ...]
    findings: tuple[RuntimeTestFinding, ...]
    claim_boundary: str
    execution_owner_id: str = ""
    environment_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    command: tuple[str, ...] = ()
    declared_parent_counts: Mapping[str, int] | None = None
    declared_parent_status: str = ""

    def __post_init__(self) -> None:
        _text(self.execution_id, context="runtime_test_evidence.execution_id")
        _text(self.inventory_id, context="runtime_test_evidence.inventory_id")
        _text(
            self.inventory_fingerprint,
            context="runtime_test_evidence.inventory_fingerprint",
        )
        object.__setattr__(
            self,
            "requested_pytest_nodeids",
            _normalized_nodeids(
                self.requested_pytest_nodeids,
                context="runtime_test_evidence.requested_pytest_nodeids",
            ),
        )
        object.__setattr__(
            self,
            "collected_pytest_nodeids",
            _normalized_nodeids(
                self.collected_pytest_nodeids,
                context="runtime_test_evidence.collected_pytest_nodeids",
            ),
        )
        object.__setattr__(
            self,
            "deselected_pytest_nodeids",
            _normalized_nodeids(
                self.deselected_pytest_nodeids,
                context="runtime_test_evidence.deselected_pytest_nodeids",
            ),
        )
        object.__setattr__(
            self,
            "unrelated_pytest_nodeids",
            _normalized_nodeids(
                self.unrelated_pytest_nodeids,
                context="runtime_test_evidence.unrelated_pytest_nodeids",
            ),
        )
        if not isinstance(self.leaves, tuple):
            object.__setattr__(self, "leaves", tuple(self.leaves))
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "leaves",
            tuple(sorted(self.leaves, key=lambda item: item.pytest_nodeid)),
        )
        object.__setattr__(
            self,
            "findings",
            tuple(
                sorted(
                    self.findings,
                    key=lambda item: (
                        item.severity,
                        item.code,
                        item.pytest_nodeid,
                        item.message,
                    ),
                )
            ),
        )
        object.__setattr__(self, "claim_boundary", _text(self.claim_boundary, context="runtime_test_evidence.claim_boundary"))
        for name in (
            "execution_owner_id",
            "environment_fingerprint",
            "toolchain_fingerprint",
            "declared_parent_status",
        ):
            _text(getattr(self, name), context=f"runtime_test_evidence.{name}", allow_empty=True)
        object.__setattr__(self, "command", tuple(str(item) for item in self.command))
        object.__setattr__(
            self,
            "declared_parent_counts",
            _normalized_declared_counts(self.declared_parent_counts),
        )

        nodeids = tuple(item.pytest_nodeid for item in self.leaves)
        if len(nodeids) != len(set(nodeids)):
            raise RuntimeTestEvidenceError("runtime test evidence contains duplicate leaves")
        if len(self.collected_pytest_nodeids) != len(set(self.collected_pytest_nodeids)):
            raise RuntimeTestEvidenceError("runtime test evidence contains duplicate collected node ids")
        if len(self.deselected_pytest_nodeids) != len(set(self.deselected_pytest_nodeids)):
            raise RuntimeTestEvidenceError("runtime test evidence contains duplicate deselected node ids")
        counts = _count_projection(self.leaves)
        if counts["planned_count"] != (
            counts["executed_count"]
            + counts["reused_count"]
            + counts["not_run_count"]
        ):
            raise RuntimeTestEvidenceError(
                "runtime test evidence planned/executed/reused/not_run accounting is inconsistent"
            )
        if counts["planned_count"] != (
            counts["selected_count"]
            + counts["explicitly_not_selected_count"]
        ):
            raise RuntimeTestEvidenceError(
                "runtime test evidence planned/selected/explicitly_not_selected accounting is inconsistent"
            )

    @property
    def counts(self) -> dict[str, int]:
        return _count_projection(self.leaves)

    @property
    def executed_case_ids(self) -> tuple[str, ...]:
        """Concrete native leaf identities that actually reached execution.

        The projection is derived only from reconciled concrete leaves.  It
        never expands a static parent node, trusts a parent count, or invents
        parameter IDs.  Reused leaves are intentionally excluded: callers
        that want the full current evidence set can use ``executed_or_reused``.
        """

        return tuple(
            leaf.pytest_nodeid
            for leaf in self.leaves
            if leaf.execution_status == RUNTIME_TEST_EXECUTION_EXECUTED
        )

    @property
    def executed_or_reused_case_ids(self) -> tuple[str, ...]:
        """Concrete leaf identities with either a native execution or reuse."""

        return tuple(
            leaf.pytest_nodeid
            for leaf in self.leaves
            if leaf.execution_status
            in {
                RUNTIME_TEST_EXECUTION_EXECUTED,
                RUNTIME_TEST_EXECUTION_REUSED,
            }
        )

    @property
    def execution_complete(self) -> bool:
        """Whether every planned leaf is a terminal native pass with no gaps."""

        return bool(
            self.leaves
            and self.counts["planned_count"] > 0
            and self.ok
            and all(
                leaf.planned
                and leaf.selected
                and leaf.execution_status
                == RUNTIME_TEST_EXECUTION_EXECUTED
                and leaf.outcome == RUNTIME_TEST_OUTCOME_PASSED
                for leaf in self.leaves
                if leaf.planned
            )
        )

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
            "schema_version": RUNTIME_TEST_EVIDENCE_SCHEMA,
            "execution_id": self.execution_id,
            "inventory_id": self.inventory_id,
            "inventory_fingerprint": self.inventory_fingerprint,
            "requested_pytest_nodeids": list(self.requested_pytest_nodeids),
            "collected_pytest_nodeids": list(self.collected_pytest_nodeids),
            "deselected_pytest_nodeids": list(self.deselected_pytest_nodeids),
            "unrelated_pytest_nodeids": list(self.unrelated_pytest_nodeids),
            "leaves": [item.to_dict() for item in self.leaves],
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

    @classmethod
    def from_dict(cls, value: Any) -> "RuntimeTestEvidenceReport":
        fields = (
            "schema_version",
            "execution_id",
            "inventory_id",
            "inventory_fingerprint",
            "requested_pytest_nodeids",
            "collected_pytest_nodeids",
            "deselected_pytest_nodeids",
            "unrelated_pytest_nodeids",
            "leaves",
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
        data = _strict_object(value, context="runtime test evidence", required=fields)
        if data["schema_version"] != RUNTIME_TEST_EVIDENCE_SCHEMA:
            raise RuntimeTestEvidenceError("runtime test evidence schema is not current")
        for name in (
            "requested_pytest_nodeids",
            "collected_pytest_nodeids",
            "deselected_pytest_nodeids",
            "unrelated_pytest_nodeids",
            "leaves",
            "findings",
            "command",
        ):
            if not isinstance(data[name], list):
                raise RuntimeTestEvidenceError(f"runtime_test_evidence.{name} must be an array")
        report = cls(
            execution_id=data["execution_id"],
            inventory_id=data["inventory_id"],
            inventory_fingerprint=data["inventory_fingerprint"],
            requested_pytest_nodeids=_strings(
                data["requested_pytest_nodeids"],
                context="requested_pytest_nodeids",
            ),
            collected_pytest_nodeids=_strings(
                data["collected_pytest_nodeids"],
                context="collected_pytest_nodeids",
            ),
            deselected_pytest_nodeids=_strings(
                data["deselected_pytest_nodeids"],
                context="deselected_pytest_nodeids",
            ),
            unrelated_pytest_nodeids=_strings(
                data["unrelated_pytest_nodeids"],
                context="unrelated_pytest_nodeids",
            ),
            leaves=tuple(RuntimeTestLeafEvidence.from_dict(item) for item in data["leaves"]),
            findings=tuple(RuntimeTestFinding.from_dict(item) for item in data["findings"]),
            claim_boundary=data["claim_boundary"],
            execution_owner_id=data["execution_owner_id"],
            environment_fingerprint=data["environment_fingerprint"],
            toolchain_fingerprint=data["toolchain_fingerprint"],
            command=_strings(data["command"], context="command", allow_duplicates=True, allow_empty=True),
            declared_parent_counts=data["declared_parent_counts"],
            declared_parent_status=data["declared_parent_status"],
        )
        if data["status"] != report.status or data["ok"] is not report.ok:
            raise RuntimeTestEvidenceError("runtime test evidence status projection mismatch")
        if data["counts"] != report.counts:
            raise RuntimeTestEvidenceError("runtime test evidence count projection mismatch")
        if data["fingerprint"] != report.fingerprint:
            raise RuntimeTestEvidenceError("runtime test evidence fingerprint mismatch")
        return report


def _coerce_result(value: Any, *, context: str) -> RuntimeTestResult:
    if isinstance(value, RuntimeTestResult):
        return value
    if isinstance(value, str):
        outcome = value
        reason = "pytest reported " + outcome
        return RuntimeTestResult(outcome=outcome, reason="" if outcome == "passed" else reason)
    if isinstance(value, Mapping):
        if "outcome" not in value:
            # Native pytest hooks commonly preserve phase outcomes under
            # ``setup``/``call``/``teardown`` rather than flattening them.
            # Normalize that shape through the same conservative classifier
            # used by direct report consumers.
            return classify_pytest_result(value)
        allowed = {
            "outcome",
            "reason",
            "duration_seconds",
            "result_path",
            "result_fingerprint",
            "producer_receipt_id",
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
        }
        unknown = set(value) - allowed
        if unknown:
            raise RuntimeTestEvidenceError(f"{context} contains unknown fields: {sorted(unknown)}")
        outcome = str(value["outcome"])
        reason = str(value.get("reason", ""))
        if outcome != RUNTIME_TEST_OUTCOME_PASSED and not reason.strip():
            reason = "pytest reported " + outcome
        return RuntimeTestResult(
            outcome=outcome,
            reason=reason,
            duration_seconds=value.get("duration_seconds"),
            result_path=value.get("result_path", ""),
            result_fingerprint=value.get("result_fingerprint", ""),
            producer_receipt_id=value.get("producer_receipt_id", ""),
            producer_receipt_fingerprint=value.get("producer_receipt_fingerprint", ""),
            producer_receipt_path=value.get("producer_receipt_path", ""),
            reuse_identity=value.get("reuse_identity", ""),
            source_fingerprint=value.get("source_fingerprint", ""),
            model_fingerprint=value.get("model_fingerprint", ""),
            toolchain_fingerprint=value.get("toolchain_fingerprint", ""),
            environment_fingerprint=value.get("environment_fingerprint", ""),
            terminal_state=value.get("terminal_state", ""),
            cleanup_state=value.get("cleanup_state", ""),
            cleanup_verified=value.get("cleanup_verified"),
        )
    raise RuntimeTestEvidenceError(f"{context} must be RuntimeTestResult, string, or object")


def classify_pytest_result(value: Any) -> RuntimeTestResult:
    """Normalize a pytest report row or phase-outcome mapping.

    Native plugins may pass a mapping such as ``{"setup": "passed",
    "call": "passed", "teardown": "passed"}`` plus ``wasxfail``.  A direct
    ``outcome`` mapping is accepted as well.  The helper is deliberately
    conservative: an unknown or incomplete row becomes a reasoned
    ``not_run`` result rather than a pass.
    """

    if isinstance(value, RuntimeTestResult):
        return value
    if isinstance(value, str):
        return _coerce_result(value, context="pytest result")

    def read(name: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(name, default)
        return getattr(value, name, default)

    direct = read("outcome", None)
    reason = read("reason", None)
    if reason is None:
        reason = read("longrepr", None)
    if reason is None:
        reason = read("message", "")
    reason_text = "" if reason is None else str(reason)
    duration = read("duration_seconds", read("duration", None))
    wasxfail = read("wasxfail", None)
    call_outcome = read("call", direct)
    if direct in RUNTIME_TEST_OUTCOMES and not wasxfail:
        if direct == RUNTIME_TEST_OUTCOME_PASSED:
            return RuntimeTestResult(direct, reason_text, duration)
        return RuntimeTestResult(direct, reason_text or f"pytest reported {direct}", duration)

    if wasxfail:
        xfail_reason = str(wasxfail) if wasxfail is not True else reason_text
        if str(call_outcome) == "passed":
            return RuntimeTestResult(
                RUNTIME_TEST_OUTCOME_XPASSED,
                "xfail unexpectedly passed: " + (xfail_reason or "unknown reason"),
                duration,
            )
        return RuntimeTestResult(
            RUNTIME_TEST_OUTCOME_XFAILED,
            xfail_reason or "pytest xfail expected failure",
            duration,
        )

    phase_values = [read(name, None) for name in ("setup", "call", "teardown")]
    if any(str(item) in {"failed", "error"} for item in phase_values if item is not None):
        return RuntimeTestResult(
            RUNTIME_TEST_OUTCOME_FAILED,
            reason_text or "pytest reported failed phase",
            duration,
        )
    if any(str(item) == "skipped" for item in phase_values if item is not None):
        return RuntimeTestResult(
            RUNTIME_TEST_OUTCOME_SKIPPED,
            reason_text or "pytest reported skipped phase",
            duration,
        )
    if str(call_outcome) == "passed":
        return RuntimeTestResult(RUNTIME_TEST_OUTCOME_PASSED, reason_text, duration)
    if direct == "not_passed":
        return RuntimeTestResult(
            RUNTIME_TEST_OUTCOME_FAILED,
            reason_text or "pytest reported not_passed",
            duration,
        )
    return RuntimeTestResult(
        RUNTIME_TEST_OUTCOME_NOT_RUN,
        reason_text or "pytest result row had no terminal call outcome",
        duration,
    )


def parse_pytest_collection_output(output: str) -> tuple[str, ...]:
    """Extract exact node ids from ``pytest --collect-only -q`` output.

    The parser is intentionally line-oriented and rejects duplicate node ids;
    warning/summary lines that do not validate as pytest node ids are ignored.
    A native adapter should still preserve the original stdout fingerprint in
    its own receipt.
    """

    if not isinstance(output, str):
        raise RuntimeTestEvidenceError("pytest collection output must be text")
    nodeids: list[str] = []
    for raw_line in output.splitlines():
        candidate = raw_line.strip()
        if not candidate or "::" not in candidate:
            continue
        try:
            nodeid = _normalize_nodeid(candidate, context="pytest collection line")
        except RuntimeTestEvidenceError:
            continue
        nodeids.append(nodeid)
    if len(nodeids) != len(set(nodeids)):
        raise RuntimeTestEvidenceError("pytest collection output contains duplicate node ids")
    return tuple(nodeids)


def _append_finding(
    findings: list[RuntimeTestFinding],
    code: str,
    message: str,
    *,
    severity: str = "blocker",
    pytest_nodeid: str = "",
) -> None:
    findings.append(
        RuntimeTestFinding(
            code=code,
            message=message,
            severity=severity,
            pytest_nodeid=pytest_nodeid,
        )
    )


def _result_integrity_findings(
    result: RuntimeTestResult,
    *,
    execution_status: str,
    nodeid: str,
    findings: list[RuntimeTestFinding],
    require_verifiable_material: bool,
    report_execution_owner_id: str,
    report_environment_fingerprint: str,
    report_toolchain_fingerprint: str,
    report_command: Sequence[str],
) -> None:
    """Attach independent material/receipt checks to one selected leaf."""

    executed_or_reused = execution_status in {
        RUNTIME_TEST_EXECUTION_EXECUTED,
        RUNTIME_TEST_EXECUTION_REUSED,
    }
    if not executed_or_reused:
        return

    if not result.result_fingerprint:
        _append_finding(
            findings,
            "runtime_test_result_fingerprint_missing",
            "executed runtime leaf has no immutable result fingerprint",
            pytest_nodeid=nodeid,
        )
    elif not is_sha256_fingerprint(result.result_fingerprint):
        _append_finding(
            findings,
            "runtime_test_result_fingerprint_invalid",
            "runtime leaf result fingerprint is not a canonical SHA-256 digest",
            pytest_nodeid=nodeid,
        )

    if execution_status == RUNTIME_TEST_EXECUTION_REUSED:
        if not result.producer_receipt_id.strip():
            _append_finding(
                findings,
                "runtime_test_reuse_producer_receipt_missing",
                "reused runtime leaf has no producer receipt identity",
                pytest_nodeid=nodeid,
            )
        if not result.producer_receipt_fingerprint.strip():
            _append_finding(
                findings,
                "runtime_test_reuse_receipt_fingerprint_missing",
                "reused runtime leaf has no producer receipt canonical fingerprint",
                pytest_nodeid=nodeid,
            )
        elif not is_sha256_fingerprint(result.producer_receipt_fingerprint):
            _append_finding(
                findings,
                "runtime_test_reuse_receipt_fingerprint_invalid",
                "reused runtime leaf producer receipt fingerprint is not canonical",
                pytest_nodeid=nodeid,
            )
        if not result.reuse_identity.strip():
            _append_finding(
                findings,
                "runtime_test_reuse_identity_missing",
                "reused runtime leaf has no frozen reuse identity",
                pytest_nodeid=nodeid,
            )

    if result.cleanup_verified is False or result.cleanup_state.casefold() in {
        "cleanup-unconfirmed",
        "unconfirmed",
        "unknown",
        "timeout",
    }:
        _append_finding(
            findings,
            "runtime_test_cleanup_unconfirmed",
            "runtime leaf cleanup was not confirmed after execution",
            pytest_nodeid=nodeid,
        )

    # Strict mode is used by DNA/release owners.  The reconciliation helper
    # remains usable for diagnostic collection, but no strict claim may rely
    # on a missing path, caller hash, or missing producer receipt.
    if not require_verifiable_material:
        return

    from .proof_artifact import ProofArtifactRef

    artifact = ProofArtifactRef(
        artifact_id=f"runtime-leaf:{nodeid}",
        producer_route="runtime_test_evidence",
        command=" ".join(str(item) for item in (report_command or ("pytest", nodeid))),
        result_path=result.result_path,
        result_status="passed" if result.outcome == RUNTIME_TEST_OUTCOME_PASSED else result.outcome,
        exit_code=0 if result.outcome in {RUNTIME_TEST_OUTCOME_PASSED, RUNTIME_TEST_OUTCOME_XFAILED} else 1,
        started_at="1970-01-01T00:00:00+00:00",
        finished_at="1970-01-01T00:00:01+00:00",
        subject_id=nodeid,
        subject_fingerprint=result.source_fingerprint or "sha256:" + "0" * 64,
        artifact_fingerprints={"result": result.result_fingerprint},
        assertion_scope="external_contract",
        receipt_id=result.producer_receipt_id,
        receipt_path=result.producer_receipt_path,
        receipt_fingerprint=result.producer_receipt_fingerprint,
        execution_owner_id=(
            ""
            if execution_status == RUNTIME_TEST_EXECUTION_REUSED
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
            if execution_status == RUNTIME_TEST_EXECUTION_REUSED
            else report_execution_owner_id
        ),
        expected_source_fingerprint=result.source_fingerprint,
        expected_model_fingerprint=result.model_fingerprint,
        expected_toolchain_fingerprint=result.toolchain_fingerprint or report_toolchain_fingerprint,
        expected_environment_fingerprint=result.environment_fingerprint or report_environment_fingerprint,
        expected_result_fingerprint=result.result_fingerprint,
        expected_reuse_identity=(
            result.reuse_identity
            if execution_status == RUNTIME_TEST_EXECUTION_REUSED
            else ""
        ),
        require_receipt=True,
        require_cleanup_confirmation=True,
        require_canonical_receipt=True,
    ):
        _append_finding(
            findings,
            code,
            message,
            pytest_nodeid=nodeid,
        )


def _normalize_result_row_keys(
    rows: Mapping[str, Any],
    *,
    context: str,
    findings: list[RuntimeTestFinding],
) -> dict[str, Any]:
    if not isinstance(rows, Mapping):
        raise RuntimeTestEvidenceError(f"{context} must be an object")
    normalized: dict[str, Any] = {}
    for raw_nodeid, value in rows.items():
        nodeid = _normalize_nodeid(raw_nodeid, context=f"{context} node id")
        if nodeid in normalized:
            _append_finding(
                findings,
                "duplicate_runtime_result_node",
                "result rows contain the same normalized pytest node id more than once",
                pytest_nodeid=nodeid,
            )
            continue
        normalized[nodeid] = value
    return normalized


def reconcile_pytest_execution(
    inventory: ProjectTestInventory,
    *,
    execution_id: str,
    collected_pytest_nodeids: Sequence[str],
    result_rows: Mapping[str, Any] | None = None,
    reused_rows: Mapping[str, Any] | None = None,
    requested_pytest_nodeids: Sequence[str] | None = None,
    deselected_pytest_nodeids: Sequence[str] = (),
    declared_parent_counts: Mapping[str, Any] | None = None,
    declared_parent_status: str = "",
    claim_boundary: str = "declared_complete",
    execution_owner_id: str = "",
    environment_fingerprint: str = "",
    toolchain_fingerprint: str = "",
    command: Sequence[str] = (),
    require_verifiable_material: bool = False,
) -> RuntimeTestEvidenceReport:
    """Reconcile static required nodes with concrete pytest leaves.

    ``requested_pytest_nodeids`` defaults to the static inventory's required
    nodes.  A static parameterized node matches every concrete node beginning
    with ``<nodeid>[``.  Missing collection, missing terminal reports,
    deselection, failures, skips, xfails, and xpasses remain visible.  A
    parent count/status supplied by an adapter is compared with the leaf
    projection; mismatches are blockers rather than silently trusted totals.
    """

    if not isinstance(inventory, ProjectTestInventory):
        raise RuntimeTestEvidenceError("inventory must be a ProjectTestInventory")
    requested = _normalized_nodeids(
        tuple(requested_pytest_nodeids or inventory.required_pytest_nodeids),
        context="requested_pytest_nodeids",
    )
    collected_raw = _normalized_nodeids(
        tuple(collected_pytest_nodeids),
        context="collected_pytest_nodeids",
    )
    deselected_raw = _normalized_nodeids(
        tuple(deselected_pytest_nodeids),
        context="deselected_pytest_nodeids",
    )
    findings: list[RuntimeTestFinding] = []
    result_rows = _normalize_result_row_keys(
        result_rows or {},
        context="result_rows",
        findings=findings,
    )
    reused_rows = _normalize_result_row_keys(
        reused_rows or {},
        context="reused_rows",
        findings=findings,
    )
    collected = tuple(dict.fromkeys(collected_raw))
    deselected = tuple(dict.fromkeys(deselected_raw))
    expected_static = set(inventory.required_pytest_nodeids)
    for nodeid in requested:
        if not any(
            _matches_static(static_nodeid, nodeid)
            or _base_nodeid(nodeid) == static_nodeid
            for static_nodeid in expected_static
        ):
            _append_finding(
                findings,
                "requested_node_not_in_static_inventory",
                "requested pytest node is absent from the static required inventory",
                pytest_nodeid=nodeid,
            )

    if len(collected_raw) != len(collected):
        _append_finding(
            findings,
            "duplicate_collected_node",
            "pytest collection emitted a duplicate concrete node id",
        )
    if len(deselected_raw) != len(deselected):
        _append_finding(
            findings,
            "duplicate_deselected_node",
            "pytest deselection emitted a duplicate concrete node id",
        )

    collected_set = set(collected)
    requested_keys = tuple(requested)
    leaves: dict[str, RuntimeTestLeafEvidence] = {}
    unrelated: list[str] = []

    def matching_requested(nodeid: str) -> bool:
        return any(_matches_static(item, nodeid) for item in requested_keys)

    def add_leaf(leaf: RuntimeTestLeafEvidence) -> None:
        if leaf.pytest_nodeid in leaves:
            _append_finding(
                findings,
                "duplicate_runtime_leaf",
                "runtime reconciliation attempted to materialize one leaf more than once",
                pytest_nodeid=leaf.pytest_nodeid,
            )
            return
        leaves[leaf.pytest_nodeid] = leaf

    for nodeid in collected:
        if not matching_requested(nodeid):
            unrelated.append(nodeid)
            add_leaf(
                RuntimeTestLeafEvidence(
                    pytest_nodeid=nodeid,
                    planned=False,
                    selected=False,
                    execution_status=RUNTIME_TEST_EXECUTION_NOT_RUN,
                    outcome=RUNTIME_TEST_OUTCOME_NOT_RUN,
                    reason="pytest collected a node outside the requested static selection",
                )
            )
            _append_finding(
                findings,
                "unrelated_collected_node",
                "pytest collection contains a node outside the requested static selection",
                pytest_nodeid=nodeid,
            )
            continue
        if nodeid in result_rows and nodeid in reused_rows:
            _append_finding(
                findings,
                "duplicate_runtime_result_source",
                "one concrete leaf has both executed and reused result rows",
                pytest_nodeid=nodeid,
            )
            result = RuntimeTestResult(
                RUNTIME_TEST_OUTCOME_NOT_RUN,
                "executed and reused result sources conflict",
            )
            execution_status = RUNTIME_TEST_EXECUTION_NOT_RUN
        elif nodeid in reused_rows:
            result = _coerce_result(reused_rows[nodeid], context=f"reused_rows[{nodeid}]")
            execution_status = RUNTIME_TEST_EXECUTION_REUSED
        elif nodeid in result_rows:
            result = _coerce_result(result_rows[nodeid], context=f"result_rows[{nodeid}]")
            execution_status = RUNTIME_TEST_EXECUTION_EXECUTED
        else:
            result = RuntimeTestResult(
                RUNTIME_TEST_OUTCOME_NOT_RUN,
                "pytest collected a selected leaf without a terminal result row",
            )
            execution_status = RUNTIME_TEST_EXECUTION_NOT_RUN
        _result_integrity_findings(
            result,
            execution_status=execution_status,
            nodeid=nodeid,
            findings=findings,
            require_verifiable_material=require_verifiable_material,
            report_execution_owner_id=execution_owner_id,
            report_environment_fingerprint=environment_fingerprint,
            report_toolchain_fingerprint=toolchain_fingerprint,
            report_command=command,
        )
        add_leaf(
            RuntimeTestLeafEvidence(
                pytest_nodeid=nodeid,
                planned=True,
                selected=True,
                execution_status=execution_status,
                outcome=result.outcome,
                reason=result.reason,
                duration_seconds=result.duration_seconds,
                result_path=result.result_path,
                result_fingerprint=result.result_fingerprint,
                producer_receipt_id=result.producer_receipt_id,
                producer_receipt_fingerprint=result.producer_receipt_fingerprint,
                producer_receipt_path=result.producer_receipt_path,
                reuse_identity=result.reuse_identity,
                source_fingerprint=result.source_fingerprint,
                model_fingerprint=result.model_fingerprint,
                toolchain_fingerprint=result.toolchain_fingerprint,
                environment_fingerprint=result.environment_fingerprint,
                terminal_state=result.terminal_state,
                cleanup_state=result.cleanup_state,
                cleanup_verified=result.cleanup_verified,
            )
        )

    for nodeid in deselected:
        if nodeid in collected_set:
            _append_finding(
                findings,
                "deselected_collected_node_conflict",
                "a node is reported as both collected and deselected",
                pytest_nodeid=nodeid,
            )
            continue
        if matching_requested(nodeid):
            add_leaf(
                RuntimeTestLeafEvidence(
                    pytest_nodeid=nodeid,
                    planned=True,
                    selected=False,
                    execution_status=RUNTIME_TEST_EXECUTION_NOT_RUN,
                    outcome=RUNTIME_TEST_OUTCOME_NOT_RUN,
                    reason="pytest deselected a requested leaf",
                )
            )
            continue
        unrelated.append(nodeid)
        add_leaf(
            RuntimeTestLeafEvidence(
                pytest_nodeid=nodeid,
                planned=False,
                selected=False,
                execution_status=RUNTIME_TEST_EXECUTION_NOT_RUN,
                outcome=RUNTIME_TEST_OUTCOME_NOT_RUN,
                reason="pytest deselected a node outside the requested static selection",
            )
        )
        _append_finding(
            findings,
            "unrelated_deselected_node",
            "pytest deselection contains a node outside the requested static selection",
            severity="warning",
            pytest_nodeid=nodeid,
        )

    for static_nodeid in requested:
        if any(_matches_static(static_nodeid, nodeid) for nodeid in leaves):
            continue
        add_leaf(
            RuntimeTestLeafEvidence(
                pytest_nodeid=static_nodeid,
                planned=True,
                selected=True,
                execution_status=RUNTIME_TEST_EXECUTION_NOT_RUN,
                outcome=RUNTIME_TEST_OUTCOME_NOT_RUN,
                reason="requested static node was not collected by pytest",
            )
        )

    known_result_keys = set(collected) | set(deselected)
    for nodeid in tuple(result_rows) + tuple(reused_rows):
        normalized = _normalize_nodeid(nodeid, context="result row node id")
        if normalized not in known_result_keys:
            _append_finding(
                findings,
                "result_node_not_collected",
                "a result row has no matching collected or deselected pytest leaf",
                pytest_nodeid=normalized,
            )

    has_execution = any(item.executed or item.reused for item in leaves.values())
    if has_execution and not execution_owner_id.strip():
        _append_finding(
            findings,
            "execution_owner_missing",
            "executed runtime evidence requires the native execution owner identity",
        )
    if has_execution and not tuple(command):
        _append_finding(
            findings,
            "execution_command_missing",
            "executed runtime evidence requires the native command identity",
        )

    # Every planned non-pass stays visible.  A targeted claim may retain a
    # warning for an expected xfail/skip, but declared-complete cannot consume
    # any non-pass or not-run leaf as full current evidence.
    nonpass_severity = "blocker" if claim_boundary == "declared_complete" else "warning"
    for leaf in leaves.values():
        if not leaf.planned:
            continue
        if leaf.not_run:
            _append_finding(
                findings,
                "runtime_test_leaf_not_run",
                leaf.reason,
                severity=nonpass_severity,
                pytest_nodeid=leaf.pytest_nodeid,
            )
        elif leaf.outcome == RUNTIME_TEST_OUTCOME_FAILED:
            _append_finding(
                findings,
                "runtime_test_leaf_failed",
                leaf.reason,
                pytest_nodeid=leaf.pytest_nodeid,
            )
        elif leaf.outcome == RUNTIME_TEST_OUTCOME_SKIPPED:
            _append_finding(
                findings,
                "runtime_test_leaf_skipped",
                leaf.reason,
                severity=nonpass_severity,
                pytest_nodeid=leaf.pytest_nodeid,
            )
        elif leaf.outcome == RUNTIME_TEST_OUTCOME_XFAILED:
            _append_finding(
                findings,
                "runtime_test_leaf_xfailed",
                leaf.reason,
                severity=nonpass_severity,
                pytest_nodeid=leaf.pytest_nodeid,
            )
        elif leaf.outcome == RUNTIME_TEST_OUTCOME_XPASSED:
            _append_finding(
                findings,
                "runtime_test_leaf_xpassed",
                leaf.reason,
                pytest_nodeid=leaf.pytest_nodeid,
            )

    report = RuntimeTestEvidenceReport(
        execution_id=execution_id,
        inventory_id=inventory.inventory_id,
        inventory_fingerprint=inventory.inventory_fingerprint,
        requested_pytest_nodeids=requested,
        collected_pytest_nodeids=collected,
        deselected_pytest_nodeids=deselected,
        unrelated_pytest_nodeids=tuple(unrelated),
        leaves=tuple(leaves.values()),
        findings=tuple(findings),
        claim_boundary=claim_boundary,
        execution_owner_id=execution_owner_id,
        environment_fingerprint=environment_fingerprint,
        toolchain_fingerprint=toolchain_fingerprint,
        command=tuple(command),
        declared_parent_counts=declared_parent_counts,
        declared_parent_status=declared_parent_status,
    )
    expected_counts = report.counts
    for field, expected in report.declared_parent_counts.items():
        if expected_counts[field] != expected:
            # ``RuntimeTestEvidenceReport`` is frozen, so this finding is
            # applied through a new report below.  The mismatch is intentionally
            # part of the canonical report rather than a caller-side warning.
            findings.append(
                RuntimeTestFinding(
                    code="parent_leaf_count_mismatch",
                    message=(
                        f"parent declared {field}={expected}, but concrete leaves "
                        f"reconcile to {expected_counts[field]}"
                    ),
                    severity="blocker",
                )
            )
    parent_status = report.declared_parent_status.strip().lower()
    if parent_status in {"pass", "passed", "green"} and any(
        item.planned and item.outcome != RUNTIME_TEST_OUTCOME_PASSED
        for item in report.leaves
    ):
        findings.append(
            RuntimeTestFinding(
                code="parent_leaf_status_mismatch",
                message="parent reports pass while one planned leaf is not passed",
                severity="blocker",
            )
        )
    if findings != list(report.findings):
        report = RuntimeTestEvidenceReport(
            execution_id=report.execution_id,
            inventory_id=report.inventory_id,
            inventory_fingerprint=report.inventory_fingerprint,
            requested_pytest_nodeids=report.requested_pytest_nodeids,
            collected_pytest_nodeids=report.collected_pytest_nodeids,
            deselected_pytest_nodeids=report.deselected_pytest_nodeids,
            unrelated_pytest_nodeids=report.unrelated_pytest_nodeids,
            leaves=report.leaves,
            findings=tuple(findings),
            claim_boundary=report.claim_boundary,
            execution_owner_id=report.execution_owner_id,
            environment_fingerprint=report.environment_fingerprint,
            toolchain_fingerprint=report.toolchain_fingerprint,
            command=report.command,
            declared_parent_counts=report.declared_parent_counts,
            declared_parent_status=report.declared_parent_status,
            # The strictness switch is an execution input and must be visible
            # in the report identity once a future schema carries it.  The
            # current v1 wire shape keeps it as an adapter-only gate.
        )
    return report


def serialize_runtime_test_evidence(report: RuntimeTestEvidenceReport) -> bytes:
    """Return canonical bytes without writing an artifact."""

    return canonical_json_bytes(report.to_dict())


def write_runtime_test_evidence(
    report: RuntimeTestEvidenceReport,
    path: str,
) -> str:
    """Explicitly write one runtime evidence artifact for a native owner."""

    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_runtime_test_evidence(report) + b"\n")
    return str(target)


def load_runtime_test_evidence(path: str) -> RuntimeTestEvidenceReport:
    from pathlib import Path

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeTestEvidenceError(f"cannot load runtime test evidence: {exc}") from exc
    return RuntimeTestEvidenceReport.from_dict(value)


__all__ = [
    "RUNTIME_TEST_EVIDENCE_SCHEMA",
    "RUNTIME_TEST_EXECUTION_EXECUTED",
    "RUNTIME_TEST_EXECUTION_REUSED",
    "RUNTIME_TEST_EXECUTION_NOT_RUN",
    "RUNTIME_TEST_EXECUTION_STATES",
    "RUNTIME_TEST_OUTCOME_PASSED",
    "RUNTIME_TEST_OUTCOME_FAILED",
    "RUNTIME_TEST_OUTCOME_SKIPPED",
    "RUNTIME_TEST_OUTCOME_XFAILED",
    "RUNTIME_TEST_OUTCOME_XPASSED",
    "RUNTIME_TEST_OUTCOME_NOT_RUN",
    "RUNTIME_TEST_OUTCOMES",
    "RUNTIME_TEST_FINDING_SEVERITIES",
    "RUNTIME_TEST_COUNT_FIELDS",
    "RuntimeTestEvidenceError",
    "RuntimeTestResult",
    "RuntimeTestLeafEvidence",
    "RuntimeTestFinding",
    "RuntimeTestEvidenceReport",
    "classify_pytest_result",
    "parse_pytest_collection_output",
    "reconcile_pytest_execution",
    "serialize_runtime_test_evidence",
    "write_runtime_test_evidence",
    "load_runtime_test_evidence",
]
