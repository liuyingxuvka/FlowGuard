"""Workflow step contracts for receipt-gated FlowGuard traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .core import FrozenMetadata, Invariant, InvariantResult, freeze_metadata
from .export import to_json_text, to_jsonable
from .trace import Trace, TraceStep


STEP_SKIP_FORBIDDEN = "forbidden"
STEP_SKIP_ALLOWED_WITH_REASON = "allowed_with_reason"
STEP_SKIP_ALLOWED = "allowed"

STEP_SKIP_POLICIES = (
    STEP_SKIP_FORBIDDEN,
    STEP_SKIP_ALLOWED_WITH_REASON,
    STEP_SKIP_ALLOWED,
)

STEP_METADATA_STEP_IDS = "step_contract_ids"
STEP_METADATA_PRODUCED_RECEIPTS = "step_contract_produced_receipts"
STEP_METADATA_INVALIDATED_RECEIPTS = "step_contract_invalidated_receipts"
STEP_METADATA_SKIPPED_STEP_IDS = "step_contract_skipped_step_ids"
STEP_METADATA_CLAIM_LABELS = "step_contract_claim_labels"
STEP_METADATA_RUNTIME_NODE_IDS = "runtime_node_ids"

STEP_CONTRACT_METADATA_KEYS = (
    STEP_METADATA_STEP_IDS,
    STEP_METADATA_PRODUCED_RECEIPTS,
    STEP_METADATA_INVALIDATED_RECEIPTS,
    STEP_METADATA_SKIPPED_STEP_IDS,
    STEP_METADATA_CLAIM_LABELS,
    STEP_METADATA_RUNTIME_NODE_IDS,
)


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _metadata_map(metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, Mapping):
        return {str(key): value for key, value in metadata.items()}
    return {str(key): value for key, value in metadata}


def _metadata_values(metadata: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(str(item) for item in value if str(item)))
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


@dataclass(frozen=True)
class WorkflowStepContract:
    """One required workflow step and the receipts it needs or produces."""

    step_id: str
    completion_labels: tuple[str, ...] = ()
    requires_receipts: tuple[str, ...] = ()
    produces_receipts: tuple[str, ...] = ()
    invalidates_receipts: tuple[str, ...] = ()
    required_for_claims: tuple[str, ...] = ()
    skip_policy: str = STEP_SKIP_FORBIDDEN
    description: str = ""
    evidence_kind: str = "workflow_step"
    required_test_kinds: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    code_contract_ids: tuple[str, ...] = ()
    runtime_node_ids: tuple[str, ...] = ()
    release_required: bool = False
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        step_id = str(self.step_id)
        if not step_id:
            raise ValueError("step_id is required")
        completion_labels = _as_tuple(self.completion_labels) or (step_id,)
        skip_policy = str(self.skip_policy or STEP_SKIP_FORBIDDEN)
        if skip_policy not in STEP_SKIP_POLICIES:
            raise ValueError(f"skip_policy must be one of {STEP_SKIP_POLICIES!r}")
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "completion_labels", completion_labels)
        object.__setattr__(self, "requires_receipts", _as_tuple(self.requires_receipts))
        object.__setattr__(self, "produces_receipts", _as_tuple(self.produces_receipts))
        object.__setattr__(self, "invalidates_receipts", _as_tuple(self.invalidates_receipts))
        object.__setattr__(self, "required_for_claims", _as_tuple(self.required_for_claims))
        object.__setattr__(self, "skip_policy", skip_policy)
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "evidence_kind", str(self.evidence_kind or "workflow_step"))
        object.__setattr__(self, "required_test_kinds", _as_tuple(self.required_test_kinds))
        object.__setattr__(self, "artifact_ids", _as_tuple(self.artifact_ids))
        object.__setattr__(self, "code_contract_ids", _as_tuple(self.code_contract_ids))
        object.__setattr__(self, "runtime_node_ids", _as_tuple(self.runtime_node_ids))
        object.__setattr__(self, "release_required", bool(self.release_required))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def completion_receipts(self) -> tuple[str, ...]:
        """Receipts that prove this contract's step is complete."""

        return self.produces_receipts or (self.step_id,)

    def matches_step(self, step: TraceStep) -> bool:
        metadata = _metadata_map(step.metadata)
        return step.label in self.completion_labels or self.step_id in _metadata_values(
            metadata,
            STEP_METADATA_STEP_IDS,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "completion_labels": list(self.completion_labels),
            "requires_receipts": list(self.requires_receipts),
            "produces_receipts": list(self.produces_receipts),
            "completion_receipts": list(self.completion_receipts),
            "invalidates_receipts": list(self.invalidates_receipts),
            "required_for_claims": list(self.required_for_claims),
            "skip_policy": self.skip_policy,
            "description": self.description,
            "evidence_kind": self.evidence_kind,
            "required_test_kinds": list(self.required_test_kinds),
            "artifact_ids": list(self.artifact_ids),
            "code_contract_ids": list(self.code_contract_ids),
            "runtime_node_ids": list(self.runtime_node_ids),
            "release_required": self.release_required,
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class StepContractFinding:
    """One workflow step contract violation or visible skip."""

    code: str
    message: str
    step_index: int = 0
    step_id: str = ""
    receipt_id: str = ""
    claim_label: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "step_index", int(self.step_index))
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "claim_label", str(self.claim_label))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "step_index": self.step_index,
            "step_id": self.step_id,
            "receipt_id": self.receipt_id,
            "claim_label": self.claim_label,
            "metadata": to_jsonable(self.metadata),
        }

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class StepContractReport:
    """Structured result of reviewing one trace against workflow step contracts."""

    ok: bool
    findings: tuple[StepContractFinding, ...] = ()
    current_receipts: tuple[str, ...] = ()
    stale_receipts: tuple[str, ...] = ()
    skipped_step_ids: tuple[str, ...] = ()
    first_failed_step_index: int | None = None
    summary: str = ""

    def __post_init__(self) -> None:
        findings = tuple(self.findings)
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "current_receipts", _unique(sorted(self.current_receipts)))
        object.__setattr__(self, "stale_receipts", _unique(sorted(self.stale_receipts)))
        object.__setattr__(self, "skipped_step_ids", _unique(self.skipped_step_ids))
        if self.first_failed_step_index is None:
            first_failed = next((finding.step_index for finding in findings), None)
            object.__setattr__(self, "first_failed_step_index", first_failed)
        object.__setattr__(self, "summary", str(self.summary or _step_contract_summary(self)))

    def format_text(self, max_findings: int = 8) -> str:
        lines = [
            f"status: {'OK' if self.ok else 'VIOLATION'}",
            self.summary,
            f"current_receipts: {self.current_receipts!r}",
        ]
        if self.stale_receipts:
            lines.append(f"stale_receipts: {self.stale_receipts!r}")
        if self.skipped_step_ids:
            lines.append(f"skipped_step_ids: {self.skipped_step_ids!r}")
        for finding in self.findings[:max_findings]:
            lines.append(f"- {finding.code}: {finding.message}")
        if len(self.findings) > max_findings:
            lines.append(f"- ... {len(self.findings) - max_findings} more")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "current_receipts": list(self.current_receipts),
            "stale_receipts": list(self.stale_receipts),
            "skipped_step_ids": list(self.skipped_step_ids),
            "first_failed_step_index": self.first_failed_step_index,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return to_json_text(self.to_dict(), indent=indent)


def _step_contract_summary(report: StepContractReport) -> str:
    status = "ok" if report.ok else "violations"
    return (
        f"{status}: findings={len(report.findings)} "
        f"current_receipts={len(report.current_receipts)} "
        f"stale_receipts={len(report.stale_receipts)}"
    )


def step_contract_metadata(
    step_contract_id: str | None = None,
    *,
    step_ids: Sequence[str] = (),
    produced_receipts: Sequence[str] = (),
    invalidated_receipts: Sequence[str] = (),
    skipped_step_ids: Sequence[str] = (),
    claim_labels: Sequence[str] = (),
    runtime_node_ids: Sequence[str] = (),
) -> dict[str, tuple[str, ...]]:
    """Build trace or replay metadata for workflow step contract checks."""

    ids = _unique(((step_contract_id,) if step_contract_id else ()) + tuple(step_ids))
    metadata: dict[str, tuple[str, ...]] = {}
    if ids:
        metadata[STEP_METADATA_STEP_IDS] = ids
    produced = _unique(produced_receipts)
    if produced:
        metadata[STEP_METADATA_PRODUCED_RECEIPTS] = produced
    invalidated = _unique(invalidated_receipts)
    if invalidated:
        metadata[STEP_METADATA_INVALIDATED_RECEIPTS] = invalidated
    skipped = _unique(skipped_step_ids)
    if skipped:
        metadata[STEP_METADATA_SKIPPED_STEP_IDS] = skipped
    claims = _unique(claim_labels)
    if claims:
        metadata[STEP_METADATA_CLAIM_LABELS] = claims
    runtime_nodes = _unique(runtime_node_ids)
    if runtime_nodes:
        metadata[STEP_METADATA_RUNTIME_NODE_IDS] = runtime_nodes
    return metadata


def extract_step_contract_metadata(
    metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None,
) -> dict[str, tuple[str, ...]]:
    """Return normalized step-contract metadata keys from a metadata mapping."""

    mapping = _metadata_map(metadata)
    return {
        key: _metadata_values(mapping, key)
        for key in STEP_CONTRACT_METADATA_KEYS
        if _metadata_values(mapping, key)
    }


def review_step_contract_trace(
    trace: Trace,
    contracts: Sequence[WorkflowStepContract],
) -> StepContractReport:
    """Review a concrete trace against workflow step contracts."""

    active_contracts = tuple(contracts)
    if not active_contracts:
        return StepContractReport(ok=True, summary="no workflow step contracts provided")

    contracts_by_id = {contract.step_id: contract for contract in active_contracts}
    current_receipts: set[str] = set()
    stale_receipts: set[str] = set()
    skipped_step_ids: list[str] = []
    findings: list[StepContractFinding] = []

    for index, step in enumerate(trace.steps, start=1):
        metadata = _metadata_map(step.metadata)
        completed = tuple(contract for contract in active_contracts if contract.matches_step(step))
        skipped = _metadata_values(metadata, STEP_METADATA_SKIPPED_STEP_IDS)

        for step_id in skipped:
            skipped_step_ids.append(step_id)
            contract = contracts_by_id.get(step_id)
            if contract is None:
                continue
            if contract.skip_policy == STEP_SKIP_FORBIDDEN:
                findings.append(
                    StepContractFinding(
                        code="forbidden_step_skipped",
                        message=f"step {step_id!r} was skipped but skip_policy is forbidden",
                        step_index=index,
                        step_id=step_id,
                    )
                )
            elif contract.skip_policy == STEP_SKIP_ALLOWED_WITH_REASON and not step.reason:
                findings.append(
                    StepContractFinding(
                        code="step_skipped_without_reason",
                        message=f"step {step_id!r} was skipped without a reason",
                        step_index=index,
                        step_id=step_id,
                    )
                )

        for contract in completed:
            for receipt_id in contract.requires_receipts:
                if receipt_id in current_receipts:
                    continue
                findings.append(
                    StepContractFinding(
                        code="missing_prerequisite_receipt",
                        message=(
                            f"step {contract.step_id!r} requires current receipt "
                            f"{receipt_id!r}"
                        ),
                        step_index=index,
                        step_id=contract.step_id,
                        receipt_id=receipt_id,
                    )
                )

        invalidated = list(_metadata_values(metadata, STEP_METADATA_INVALIDATED_RECEIPTS))
        for contract in completed:
            invalidated.extend(contract.invalidates_receipts)
        for receipt_id in _unique(invalidated):
            if receipt_id in current_receipts:
                stale_receipts.add(receipt_id)
            current_receipts.discard(receipt_id)

        produced = list(_metadata_values(metadata, STEP_METADATA_PRODUCED_RECEIPTS))
        for contract in completed:
            produced.extend(contract.completion_receipts)
        for receipt_id in _unique(produced):
            current_receipts.add(receipt_id)
            stale_receipts.discard(receipt_id)

        claim_labels = set(_metadata_values(metadata, STEP_METADATA_CLAIM_LABELS))
        if step.label:
            claim_labels.add(step.label)
        for claim_label in sorted(claim_labels):
            for contract in active_contracts:
                if claim_label not in contract.required_for_claims:
                    continue
                for receipt_id in contract.completion_receipts:
                    if receipt_id in current_receipts:
                        continue
                    findings.append(
                        StepContractFinding(
                            code="missing_claim_receipt",
                            message=(
                                f"claim {claim_label!r} requires current receipt "
                                f"{receipt_id!r} from step {contract.step_id!r}"
                            ),
                            step_index=index,
                            step_id=contract.step_id,
                            receipt_id=receipt_id,
                            claim_label=claim_label,
                        )
                    )

    return StepContractReport(
        ok=not findings,
        findings=tuple(findings),
        current_receipts=tuple(sorted(current_receipts)),
        stale_receipts=tuple(sorted(stale_receipts)),
        skipped_step_ids=tuple(skipped_step_ids),
    )


def compile_step_contract_invariants(
    contracts: Sequence[WorkflowStepContract],
    *,
    name: str = "workflow_step_contracts",
) -> tuple[Invariant, ...]:
    """Compile workflow step contracts into Explorer-compatible invariants."""

    active_contracts = tuple(contracts)
    if not active_contracts:
        return ()

    def predicate(_state: Any, trace: Trace) -> InvariantResult:
        report = review_step_contract_trace(trace, active_contracts)
        if report.ok:
            return InvariantResult.pass_()
        finding = report.findings[0]
        return InvariantResult.fail(
            finding.message,
            {
                "finding_code": finding.code,
                "step_contract_id": finding.step_id,
                "receipt_id": finding.receipt_id,
                "claim_label": finding.claim_label,
            },
        )

    return (
        Invariant(
            name=name,
            description="Workflow step contracts: prerequisite receipts, invalidation, skips, and claim gates.",
            predicate=predicate,
        ),
    )


def step_contracts_to_validation_requirements(
    contracts: Sequence[WorkflowStepContract],
    *,
    requirement_prefix: str = "workflow_step",
    default_scope: str = "routine",
) -> tuple[Any, ...]:
    """Project step contracts into DevelopmentProcessFlow validation requirements."""

    from .development_process_flow import PROCESS_SCOPE_RELEASE, ValidationRequirement

    requirements = []
    for contract in contracts:
        claim_labels = contract.required_for_claims or ("step_complete",)
        for claim_label in claim_labels:
            scope = (
                PROCESS_SCOPE_RELEASE
                if contract.release_required or "release" in claim_label
                else default_scope
            )
            for receipt_id in contract.completion_receipts:
                requirements.append(
                    ValidationRequirement(
                        requirement_id=(
                            f"{requirement_prefix}:{contract.step_id}:{receipt_id}:{claim_label}"
                        ),
                        required_artifact_ids=contract.artifact_ids,
                        required_evidence_kinds=(contract.evidence_kind,),
                        scope=scope,
                        release_required=contract.release_required,
                        description=(
                            f"Workflow step {contract.step_id!r} must produce current "
                            f"receipt {receipt_id!r} before claim {claim_label!r}."
                        ),
                    )
                )
    return tuple(requirements)


def step_contracts_to_model_obligations(
    contracts: Sequence[WorkflowStepContract],
    *,
    obligation_prefix: str = "workflow_step",
) -> tuple[Any, ...]:
    """Project step contracts into Model-Test Alignment obligations."""

    from .model_test_alignment import ModelObligation

    obligations = []
    for contract in contracts:
        obligations.append(
            ModelObligation(
                obligation_id=f"{obligation_prefix}:{contract.step_id}",
                obligation_type="workflow_step",
                description=contract.description
                or f"Workflow step {contract.step_id!r} satisfies step-contract receipts.",
                required=True,
                required_test_kinds=contract.required_test_kinds,
                external_outputs=contract.completion_receipts,
                state_reads=contract.requires_receipts,
                state_writes=contract.completion_receipts,
                side_effects=contract.code_contract_ids,
            )
        )
    return tuple(obligations)


def step_contract_metadata_matches_rule():
    """Return a conformance rule comparing expected and observed step receipts."""

    from .conformance import ConformanceRule

    def check(expected_step: TraceStep, observed_step: Any) -> str | None:
        expected = extract_step_contract_metadata(expected_step.metadata)
        observed = extract_step_contract_metadata(getattr(observed_step, "metadata", None))
        if not expected and not observed:
            return None
        for key in STEP_CONTRACT_METADATA_KEYS:
            expected_values = tuple(sorted(expected.get(key, ())))
            observed_values = tuple(sorted(observed.get(key, ())))
            if expected_values == observed_values:
                continue
            return (
                f"step contract metadata mismatch for {key}: "
                f"expected {expected_values!r}, observed {observed_values!r}"
            )
        return None

    return ConformanceRule(
        name="step_contract_metadata_matches",
        description="Observed replay step-contract metadata equals expected trace metadata.",
        check=check,
    )


__all__ = [
    "STEP_CONTRACT_METADATA_KEYS",
    "STEP_METADATA_CLAIM_LABELS",
    "STEP_METADATA_INVALIDATED_RECEIPTS",
    "STEP_METADATA_PRODUCED_RECEIPTS",
    "STEP_METADATA_RUNTIME_NODE_IDS",
    "STEP_METADATA_SKIPPED_STEP_IDS",
    "STEP_METADATA_STEP_IDS",
    "STEP_SKIP_ALLOWED",
    "STEP_SKIP_ALLOWED_WITH_REASON",
    "STEP_SKIP_FORBIDDEN",
    "STEP_SKIP_POLICIES",
    "StepContractFinding",
    "StepContractReport",
    "WorkflowStepContract",
    "compile_step_contract_invariants",
    "extract_step_contract_metadata",
    "review_step_contract_trace",
    "step_contract_metadata",
    "step_contract_metadata_matches_rule",
    "step_contracts_to_model_obligations",
    "step_contracts_to_validation_requirements",
]
