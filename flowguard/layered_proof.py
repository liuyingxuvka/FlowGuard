"""Layered model-boundary proof helpers.

The helper in this module does not execute tests or inspect production code.
Project adapters collect model, code-boundary, and test evidence, then pass the
structured rows here to review whether parent model confidence is supported by
child coverage, child disjointness, child reattachment, and leaf boundary
matrix evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


PROOF_STATUS_PASSED = "passed"
PROOF_STATUS_FAILED = "failed"
PROOF_STATUS_SKIPPED = "skipped"
PROOF_STATUS_STALE = "stale"
PROOF_STATUS_NOT_RUN = "not_run"
PROOF_STATUS_RUNNING = "running"
PROOF_STATUS_PROGRESS_ONLY = "progress_only"
PROOF_STATUS_ERROR = "error"
PASSING_PROOF_STATUSES = {PROOF_STATUS_PASSED}
NON_PASSING_PROOF_STATUSES = {
    PROOF_STATUS_FAILED,
    PROOF_STATUS_SKIPPED,
    PROOF_STATUS_STALE,
    PROOF_STATUS_NOT_RUN,
    PROOF_STATUS_RUNNING,
    PROOF_STATUS_PROGRESS_ONLY,
    PROOF_STATUS_ERROR,
}

ASSERTION_SCOPE_EXTERNAL_CONTRACT = "external_contract"
ASSERTION_SCOPE_MIXED = "mixed"
ASSERTION_SCOPE_INTERNAL_PATH = "internal_path"
ASSERTION_SCOPE_UNKNOWN = "unknown"
EXTERNAL_ASSERTION_SCOPES = {
    ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    ASSERTION_SCOPE_MIXED,
}

PROOF_OWNER_CHILD = "child"
PROOF_OWNER_PARENT = "parent"
PROOF_OWNER_READ_ONLY = "read_only"
PROOF_OWNER_OUT_OF_SCOPE = "out_of_scope"
PROOF_OWNER_SHARED_KERNEL = "shared_kernel"
PROOF_OWNER_BRIDGE = "bridge"
OWNING_PARENT_ITEM_MODES = {
    PROOF_OWNER_CHILD,
    PROOF_OWNER_PARENT,
    PROOF_OWNER_SHARED_KERNEL,
    PROOF_OWNER_BRIDGE,
}
ALLOWED_PARENT_ITEM_MODES = OWNING_PARENT_ITEM_MODES | {
    PROOF_OWNER_READ_ONLY,
    PROOF_OWNER_OUT_OF_SCOPE,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _missing(expected: Sequence[str], actual: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(expected) - set(actual)))


def _extra(allowed: Sequence[str], actual: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(actual) - set(allowed)))


@dataclass(frozen=True)
class ParentCoverageItem:
    """One parent responsibility that must be covered or explicitly scoped out."""

    item_id: str
    item_type: str = "responsibility"
    owner_model_id: str = ""
    owner_kind: str = PROOF_OWNER_CHILD
    description: str = ""
    allowed_shared_with: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "owner_model_id", str(self.owner_model_id))
        object.__setattr__(self, "owner_kind", str(self.owner_kind))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "allowed_shared_with", _as_tuple(self.allowed_shared_with))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "owner_model_id": self.owner_model_id,
            "owner_kind": self.owner_kind,
            "description": self.description,
            "allowed_shared_with": list(self.allowed_shared_with),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ChildProofContract:
    """Current child model contract consumed by parent proof."""

    child_model_id: str
    evidence_id: str = ""
    evidence_status: str = PROOF_STATUS_PASSED
    evidence_current: bool = True
    responsibilities: tuple[str, ...] = ()
    functions_owned: tuple[str, ...] = ()
    inputs_accepted: tuple[str, ...] = ()
    outputs_emitted: tuple[str, ...] = ()
    state_owned: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()
    invariants_owned: tuple[str, ...] = ()
    risk_classes: tuple[str, ...] = ()
    contracts_out: tuple[str, ...] = ()
    is_leaf: bool = False
    leaf_matrix_id: str = ""
    split_required: bool = False
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_status", str(self.evidence_status))
        object.__setattr__(self, "responsibilities", _as_tuple(self.responsibilities))
        object.__setattr__(self, "functions_owned", _as_tuple(self.functions_owned))
        object.__setattr__(self, "inputs_accepted", _as_tuple(self.inputs_accepted))
        object.__setattr__(self, "outputs_emitted", _as_tuple(self.outputs_emitted))
        object.__setattr__(self, "state_owned", _as_tuple(self.state_owned))
        object.__setattr__(self, "side_effects_owned", _as_tuple(self.side_effects_owned))
        object.__setattr__(self, "invariants_owned", _as_tuple(self.invariants_owned))
        object.__setattr__(self, "risk_classes", _as_tuple(self.risk_classes))
        object.__setattr__(self, "contracts_out", _as_tuple(self.contracts_out))
        object.__setattr__(self, "leaf_matrix_id", str(self.leaf_matrix_id))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_current_pass(self) -> bool:
        return self.evidence_status in PASSING_PROOF_STATUSES and self.evidence_current

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_model_id": self.child_model_id,
            "evidence_id": self.evidence_id,
            "evidence_status": self.evidence_status,
            "evidence_current": self.evidence_current,
            "responsibilities": list(self.responsibilities),
            "functions_owned": list(self.functions_owned),
            "inputs_accepted": list(self.inputs_accepted),
            "outputs_emitted": list(self.outputs_emitted),
            "state_owned": list(self.state_owned),
            "side_effects_owned": list(self.side_effects_owned),
            "invariants_owned": list(self.invariants_owned),
            "risk_classes": list(self.risk_classes),
            "contracts_out": list(self.contracts_out),
            "is_leaf": self.is_leaf,
            "leaf_matrix_id": self.leaf_matrix_id,
            "split_required": self.split_required,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ChildReattachmentProof:
    """Parent expectations for one child handoff."""

    child_model_id: str
    consumed_evidence_id: str = ""
    expected_inputs: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    expected_state_owned: tuple[str, ...] = ()
    expected_side_effects_owned: tuple[str, ...] = ()
    expected_contracts_out: tuple[str, ...] = ()
    allow_extra_inputs: bool = False
    allow_extra_outputs: bool = False
    allow_extra_state_owned: bool = False
    allow_extra_side_effects: bool = False
    allow_extra_contracts_out: bool = False
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "consumed_evidence_id", str(self.consumed_evidence_id))
        object.__setattr__(self, "expected_inputs", _as_tuple(self.expected_inputs))
        object.__setattr__(self, "expected_outputs", _as_tuple(self.expected_outputs))
        object.__setattr__(self, "expected_state_owned", _as_tuple(self.expected_state_owned))
        object.__setattr__(self, "expected_side_effects_owned", _as_tuple(self.expected_side_effects_owned))
        object.__setattr__(self, "expected_contracts_out", _as_tuple(self.expected_contracts_out))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_model_id": self.child_model_id,
            "consumed_evidence_id": self.consumed_evidence_id,
            "expected_inputs": list(self.expected_inputs),
            "expected_outputs": list(self.expected_outputs),
            "expected_state_owned": list(self.expected_state_owned),
            "expected_side_effects_owned": list(self.expected_side_effects_owned),
            "expected_contracts_out": list(self.expected_contracts_out),
            "allow_extra_inputs": self.allow_extra_inputs,
            "allow_extra_outputs": self.allow_extra_outputs,
            "allow_extra_state_owned": self.allow_extra_state_owned,
            "allow_extra_side_effects": self.allow_extra_side_effects,
            "allow_extra_contracts_out": self.allow_extra_contracts_out,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LeafBoundaryMatrixCell:
    """One finite `Input x State` boundary row for a leaf model."""

    cell_id: str
    input_case: str
    state_case: str
    expected_outputs: tuple[str, ...] = ()
    observed_outputs: tuple[str, ...] = ()
    expected_next_states: tuple[str, ...] = ()
    observed_next_states: tuple[str, ...] = ()
    expected_state_writes: tuple[str, ...] = ()
    observed_state_writes: tuple[str, ...] = ()
    expected_side_effects: tuple[str, ...] = ()
    observed_side_effects: tuple[str, ...] = ()
    expected_error_paths: tuple[str, ...] = ()
    observed_error_paths: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_status: str = PROOF_STATUS_PASSED
    evidence_current: bool = True
    assertion_scope: str = "external_contract"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_id", str(self.cell_id))
        object.__setattr__(self, "input_case", str(self.input_case))
        object.__setattr__(self, "state_case", str(self.state_case))
        object.__setattr__(self, "expected_outputs", _as_tuple(self.expected_outputs))
        object.__setattr__(self, "observed_outputs", _as_tuple(self.observed_outputs))
        object.__setattr__(self, "expected_next_states", _as_tuple(self.expected_next_states))
        object.__setattr__(self, "observed_next_states", _as_tuple(self.observed_next_states))
        object.__setattr__(self, "expected_state_writes", _as_tuple(self.expected_state_writes))
        object.__setattr__(self, "observed_state_writes", _as_tuple(self.observed_state_writes))
        object.__setattr__(self, "expected_side_effects", _as_tuple(self.expected_side_effects))
        object.__setattr__(self, "observed_side_effects", _as_tuple(self.observed_side_effects))
        object.__setattr__(self, "expected_error_paths", _as_tuple(self.expected_error_paths))
        object.__setattr__(self, "observed_error_paths", _as_tuple(self.observed_error_paths))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "evidence_status", str(self.evidence_status))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_current_pass(self) -> bool:
        return self.evidence_status in PASSING_PROOF_STATUSES and self.evidence_current

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "input_case": self.input_case,
            "state_case": self.state_case,
            "expected_outputs": list(self.expected_outputs),
            "observed_outputs": list(self.observed_outputs),
            "expected_next_states": list(self.expected_next_states),
            "observed_next_states": list(self.observed_next_states),
            "expected_state_writes": list(self.expected_state_writes),
            "observed_state_writes": list(self.observed_state_writes),
            "expected_side_effects": list(self.expected_side_effects),
            "observed_side_effects": list(self.observed_side_effects),
            "expected_error_paths": list(self.expected_error_paths),
            "observed_error_paths": list(self.observed_error_paths),
            "evidence_ids": list(self.evidence_ids),
            "evidence_status": self.evidence_status,
            "evidence_current": self.evidence_current,
            "assertion_scope": self.assertion_scope,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class LeafBoundaryMatrix:
    """Complete boundary matrix evidence for one leaf model."""

    leaf_model_id: str
    matrix_id: str = ""
    input_cases: tuple[str, ...] = ()
    state_cases: tuple[str, ...] = ()
    expected_cell_ids: tuple[str, ...] = ()
    cells: tuple[LeafBoundaryMatrixCell, ...] = ()
    finite: bool = True
    complete: bool = True
    too_large_for_leaf: bool = False
    split_required: bool = False
    scoped_exemption: str = ""
    evidence_current: bool = True
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "leaf_model_id", str(self.leaf_model_id))
        object.__setattr__(self, "matrix_id", str(self.matrix_id))
        object.__setattr__(self, "input_cases", _as_tuple(self.input_cases))
        object.__setattr__(self, "state_cases", _as_tuple(self.state_cases))
        object.__setattr__(self, "expected_cell_ids", _as_tuple(self.expected_cell_ids))
        object.__setattr__(self, "cells", tuple(self.cells))
        object.__setattr__(self, "scoped_exemption", str(self.scoped_exemption))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaf_model_id": self.leaf_model_id,
            "matrix_id": self.matrix_id,
            "input_cases": list(self.input_cases),
            "state_cases": list(self.state_cases),
            "expected_cell_ids": list(self.expected_cell_ids),
            "cells": [cell.to_dict() for cell in self.cells],
            "finite": self.finite,
            "complete": self.complete,
            "too_large_for_leaf": self.too_large_for_leaf,
            "split_required": self.split_required,
            "scoped_exemption": self.scoped_exemption,
            "evidence_current": self.evidence_current,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LayeredBoundaryProofPlan:
    """A parent-to-leaf model proof chain."""

    proof_id: str
    parent_model_id: str
    parent_items: tuple[ParentCoverageItem, ...] = ()
    child_contracts: tuple[ChildProofContract, ...] = ()
    reattachment_proofs: tuple[ChildReattachmentProof, ...] = ()
    leaf_matrices: tuple[LeafBoundaryMatrix, ...] = ()
    allowed_shared_responsibilities: tuple[str, ...] = ()
    allowed_shared_functions: tuple[str, ...] = ()
    allowed_shared_state: tuple[str, ...] = ()
    allowed_shared_side_effects: tuple[str, ...] = ()
    allowed_shared_invariants: tuple[str, ...] = ()
    allowed_shared_risk_classes: tuple[str, ...] = ()
    require_leaf_matrix_for_leaf_children: bool = True
    allow_scoped_leaf_exemptions: bool = False
    claim_scope: str = "full"
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", str(self.proof_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "parent_items", tuple(self.parent_items))
        object.__setattr__(self, "child_contracts", tuple(self.child_contracts))
        object.__setattr__(self, "reattachment_proofs", tuple(self.reattachment_proofs))
        object.__setattr__(self, "leaf_matrices", tuple(self.leaf_matrices))
        object.__setattr__(self, "allowed_shared_responsibilities", _as_tuple(self.allowed_shared_responsibilities))
        object.__setattr__(self, "allowed_shared_functions", _as_tuple(self.allowed_shared_functions))
        object.__setattr__(self, "allowed_shared_state", _as_tuple(self.allowed_shared_state))
        object.__setattr__(self, "allowed_shared_side_effects", _as_tuple(self.allowed_shared_side_effects))
        object.__setattr__(self, "allowed_shared_invariants", _as_tuple(self.allowed_shared_invariants))
        object.__setattr__(self, "allowed_shared_risk_classes", _as_tuple(self.allowed_shared_risk_classes))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "parent_model_id": self.parent_model_id,
            "parent_items": [item.to_dict() for item in self.parent_items],
            "child_contracts": [child.to_dict() for child in self.child_contracts],
            "reattachment_proofs": [proof.to_dict() for proof in self.reattachment_proofs],
            "leaf_matrices": [matrix.to_dict() for matrix in self.leaf_matrices],
            "allowed_shared_responsibilities": list(self.allowed_shared_responsibilities),
            "allowed_shared_functions": list(self.allowed_shared_functions),
            "allowed_shared_state": list(self.allowed_shared_state),
            "allowed_shared_side_effects": list(self.allowed_shared_side_effects),
            "allowed_shared_invariants": list(self.allowed_shared_invariants),
            "allowed_shared_risk_classes": list(self.allowed_shared_risk_classes),
            "require_leaf_matrix_for_leaf_children": self.require_leaf_matrix_for_leaf_children,
            "allow_scoped_leaf_exemptions": self.allow_scoped_leaf_exemptions,
            "claim_scope": self.claim_scope,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LayeredBoundaryFinding:
    """One layered proof gap."""

    code: str
    message: str
    severity: str = "blocker"
    parent_model_id: str = ""
    child_model_id: str = ""
    item_id: str = ""
    cell_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "cell_id", str(self.cell_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "parent_model_id": self.parent_model_id,
            "child_model_id": self.child_model_id,
            "item_id": self.item_id,
            "cell_id": self.cell_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class LayeredBoundaryProofReport:
    """Structured result for a layered boundary proof review."""

    ok: bool
    proof_id: str
    parent_model_id: str
    decision: str
    findings: tuple[LayeredBoundaryFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", str(self.proof_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: layered_boundary_proof parent={self.parent_model_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard layered boundary proof ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"proof: {self.proof_id}",
            f"parent: {self.parent_model_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"child: {finding.child_model_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"cell: {finding.cell_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "proof_id": self.proof_id,
            "parent_model_id": self.parent_model_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _coverage_findings(plan: LayeredBoundaryProofPlan) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    child_ids = {child.child_model_id for child in plan.child_contracts}
    owners_by_item: dict[str, list[ParentCoverageItem]] = {}
    for item in plan.parent_items:
        if item.owner_kind not in ALLOWED_PARENT_ITEM_MODES:
            findings.append(
                LayeredBoundaryFinding(
                    "invalid_parent_item_owner_kind",
                    "parent coverage item uses an unknown owner kind",
                    parent_model_id=plan.parent_model_id,
                    item_id=item.item_id,
                    metadata=item.to_dict(),
                )
            )
        if item.owner_kind == PROOF_OWNER_CHILD:
            if not item.owner_model_id:
                findings.append(
                    LayeredBoundaryFinding(
                        "parent_coverage_gap",
                        "parent responsibility has no child owner",
                        parent_model_id=plan.parent_model_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
            elif item.owner_model_id not in child_ids:
                findings.append(
                    LayeredBoundaryFinding(
                        "unknown_child_owner",
                        "parent responsibility is assigned to an unregistered child",
                        parent_model_id=plan.parent_model_id,
                        child_model_id=item.owner_model_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        if item.owner_kind == PROOF_OWNER_OUT_OF_SCOPE and not item.rationale:
            findings.append(
                LayeredBoundaryFinding(
                    "out_of_scope_without_rationale",
                    "out-of-scope parent responsibility must explain its boundary",
                    parent_model_id=plan.parent_model_id,
                    item_id=item.item_id,
                    metadata=item.to_dict(),
                )
            )
        if item.owner_kind in OWNING_PARENT_ITEM_MODES:
            owners_by_item.setdefault(item.item_id, []).append(item)

    allowed_shared = set(plan.allowed_shared_responsibilities)
    for item_id, owners in sorted(owners_by_item.items()):
        owner_ids = {
            item.owner_model_id or plan.parent_model_id
            for item in owners
        }
        if len(owner_ids) <= 1:
            continue
        item_allowed = item_id in allowed_shared or all(
            bool(item.allowed_shared_with) for item in owners
        )
        if not item_allowed:
            findings.append(
                LayeredBoundaryFinding(
                    "parent_item_illegal_overlap",
                    "parent responsibility has multiple owners without an allowed shared boundary",
                    parent_model_id=plan.parent_model_id,
                    item_id=item_id,
                    metadata={"owners": sorted(owner_ids)},
                )
            )
    return findings


def _duplicate_child_field_findings(
    plan: LayeredBoundaryProofPlan,
    *,
    field_name: str,
    allowed: Sequence[str],
    code: str,
    noun: str,
) -> list[LayeredBoundaryFinding]:
    owners: dict[str, list[str]] = {}
    for child in plan.child_contracts:
        for value in getattr(child, field_name):
            owners.setdefault(value, []).append(child.child_model_id)
    findings: list[LayeredBoundaryFinding] = []
    allowed_set = set(allowed)
    for value, owner_ids in sorted(owners.items()):
        unique_owners = tuple(sorted(set(owner_ids)))
        if len(unique_owners) > 1 and value not in allowed_set:
            findings.append(
                LayeredBoundaryFinding(
                    code,
                    f"{noun} is owned by multiple child models without an allowed shared boundary",
                    parent_model_id=plan.parent_model_id,
                    item_id=value,
                    metadata={"owners": unique_owners},
                )
            )
    return findings


def _child_evidence_findings(plan: LayeredBoundaryProofPlan) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    for child in plan.child_contracts:
        if not child.evidence_id:
            findings.append(
                LayeredBoundaryFinding(
                    "child_missing_evidence_id",
                    "child model has no evidence id for parent consumption",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata=child.to_dict(),
                )
            )
        if not child.has_current_pass():
            findings.append(
                LayeredBoundaryFinding(
                    "child_evidence_not_current_pass",
                    "child evidence is stale, skipped, not run, running, progress-only, or failed",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata=child.to_dict(),
                )
            )
        if child.split_required:
            findings.append(
                LayeredBoundaryFinding(
                    "child_split_required",
                    "child model is too large or mixed to act as a proven boundary",
                    severity="refactor",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata=child.to_dict(),
                )
            )
    return findings


def _reattachment_findings(plan: LayeredBoundaryProofPlan) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    children = {child.child_model_id: child for child in plan.child_contracts}
    proofs = {proof.child_model_id: proof for proof in plan.reattachment_proofs}
    for child in plan.child_contracts:
        proof = proofs.get(child.child_model_id)
        if proof is None:
            findings.append(
                LayeredBoundaryFinding(
                    "child_reattachment_missing",
                    "parent has not recorded a reattachment proof for this child",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata=child.to_dict(),
                )
            )
            continue
        if proof.consumed_evidence_id != child.evidence_id:
            findings.append(
                LayeredBoundaryFinding(
                    "child_reattachment_stale_evidence",
                    "parent consumed child evidence id does not match the current child evidence id",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={"child": child.to_dict(), "reattachment": proof.to_dict()},
                )
            )

        _add_set_findings(
            findings,
            plan=plan,
            child=child,
            proof=proof,
            expected=proof.expected_inputs,
            actual=child.inputs_accepted,
            allow_extra=proof.allow_extra_inputs,
            missing_code="child_reattachment_missing_input",
            extra_code="child_reattachment_extra_input",
            noun="input",
        )
        _add_set_findings(
            findings,
            plan=plan,
            child=child,
            proof=proof,
            expected=proof.expected_outputs,
            actual=child.outputs_emitted,
            allow_extra=proof.allow_extra_outputs,
            missing_code="child_reattachment_missing_output",
            extra_code="child_reattachment_extra_output",
            noun="output",
        )
        _add_set_findings(
            findings,
            plan=plan,
            child=child,
            proof=proof,
            expected=proof.expected_state_owned,
            actual=child.state_owned,
            allow_extra=proof.allow_extra_state_owned,
            missing_code="child_reattachment_missing_state_owner",
            extra_code="child_reattachment_extra_state_owner",
            noun="state owner",
        )
        _add_set_findings(
            findings,
            plan=plan,
            child=child,
            proof=proof,
            expected=proof.expected_side_effects_owned,
            actual=child.side_effects_owned,
            allow_extra=proof.allow_extra_side_effects,
            missing_code="child_reattachment_missing_side_effect",
            extra_code="child_reattachment_extra_side_effect",
            noun="side effect",
        )
        _add_set_findings(
            findings,
            plan=plan,
            child=child,
            proof=proof,
            expected=proof.expected_contracts_out,
            actual=child.contracts_out,
            allow_extra=proof.allow_extra_contracts_out,
            missing_code="child_reattachment_missing_contract",
            extra_code="child_reattachment_extra_contract",
            noun="contract",
        )

    for proof in plan.reattachment_proofs:
        if proof.child_model_id not in children:
            findings.append(
                LayeredBoundaryFinding(
                    "child_reattachment_unknown_child",
                    "reattachment proof names an unregistered child model",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=proof.child_model_id,
                    metadata=proof.to_dict(),
                )
            )
    return findings


def _add_set_findings(
    findings: list[LayeredBoundaryFinding],
    *,
    plan: LayeredBoundaryProofPlan,
    child: ChildProofContract,
    proof: ChildReattachmentProof,
    expected: Sequence[str],
    actual: Sequence[str],
    allow_extra: bool,
    missing_code: str,
    extra_code: str,
    noun: str,
) -> None:
    missing_values = _missing(expected, actual)
    if missing_values:
        findings.append(
            LayeredBoundaryFinding(
                missing_code,
                f"child no longer provides parent-expected {noun}",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"missing": missing_values, "reattachment": proof.to_dict(), "child": child.to_dict()},
            )
        )
    extra_values = _extra(expected, actual)
    if extra_values and not allow_extra:
        findings.append(
            LayeredBoundaryFinding(
                extra_code,
                f"child exposes {noun} outside the parent handoff",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"extra": extra_values, "reattachment": proof.to_dict(), "child": child.to_dict()},
            )
        )


def _leaf_matrix_findings(plan: LayeredBoundaryProofPlan) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    matrices = {matrix.leaf_model_id: matrix for matrix in plan.leaf_matrices}
    child_ids = {child.child_model_id for child in plan.child_contracts}
    for matrix in plan.leaf_matrices:
        if matrix.leaf_model_id not in child_ids:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_matrix_unknown_child",
                    "leaf matrix names an unregistered child model",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=matrix.leaf_model_id,
                    metadata=matrix.to_dict(),
                )
            )

    for child in plan.child_contracts:
        if not child.is_leaf:
            continue
        matrix = matrices.get(child.child_model_id)
        if matrix is None:
            if plan.require_leaf_matrix_for_leaf_children:
                findings.append(
                    LayeredBoundaryFinding(
                        "leaf_matrix_missing",
                        "leaf child has no boundary matrix proof",
                        parent_model_id=plan.parent_model_id,
                        child_model_id=child.child_model_id,
                        metadata=child.to_dict(),
                    )
                )
            continue
        findings.extend(_review_one_leaf_matrix(plan, child, matrix))
    return findings


def _review_one_leaf_matrix(
    plan: LayeredBoundaryProofPlan,
    child: ChildProofContract,
    matrix: LeafBoundaryMatrix,
) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    if not matrix.evidence_current:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_stale",
                "leaf boundary matrix evidence is stale",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata=matrix.to_dict(),
            )
        )
    if not matrix.finite or matrix.too_large_for_leaf or matrix.split_required:
        severity = "warning" if plan.allow_scoped_leaf_exemptions and matrix.scoped_exemption else "refactor"
        findings.append(
            LayeredBoundaryFinding(
                "leaf_split_required",
                "leaf boundary matrix is not small enough for complete finite proof",
                severity=severity,
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata=matrix.to_dict(),
            )
        )
    if not matrix.complete:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_incomplete",
                "leaf boundary matrix is marked incomplete",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata=matrix.to_dict(),
            )
        )

    expected_cell_ids = _effective_expected_cell_ids(matrix)
    cell_id_counts: dict[str, int] = {}
    for cell in matrix.cells:
        cell_id_counts[cell.cell_id] = cell_id_counts.get(cell.cell_id, 0) + 1
    duplicate_cells = tuple(sorted(cell_id for cell_id, count in cell_id_counts.items() if count > 1))
    if duplicate_cells:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_duplicate_cell",
                "leaf boundary matrix declares the same Input x State cell more than once",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"duplicate_cells": duplicate_cells, "matrix": matrix.to_dict()},
            )
        )

    findings.extend(_cartesian_matrix_findings(plan, child, matrix, expected_cell_ids))
    cell_ids = set(cell_id_counts)
    missing_cells = tuple(sorted(set(expected_cell_ids) - cell_ids))
    if missing_cells:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_missing_cell",
                "leaf boundary matrix is missing expected Input x State cells",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"missing_cells": missing_cells, "matrix": matrix.to_dict()},
            )
        )
    unexpected_cells = tuple(sorted(cell_ids - set(expected_cell_ids)))
    if unexpected_cells:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_unexpected_cell",
                "leaf boundary matrix contains Input x State cells outside the declared finite boundary",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"unexpected_cells": unexpected_cells, "matrix": matrix.to_dict()},
            )
        )
    for cell in matrix.cells:
        if not cell.has_current_pass():
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_cell_evidence_not_current_pass",
                    "leaf boundary cell evidence is stale, skipped, not run, running, progress-only, or failed",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    cell_id=cell.cell_id,
                    metadata=cell.to_dict(),
                )
            )
        if cell.assertion_scope not in EXTERNAL_ASSERTION_SCOPES:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_cell_internal_path_only",
                    "leaf boundary cell evidence does not prove the external contract boundary",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    cell_id=cell.cell_id,
                    metadata=cell.to_dict(),
                )
            )
        if not cell.evidence_ids:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_cell_missing_evidence_id",
                    "leaf boundary cell has no test or replay evidence id",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    cell_id=cell.cell_id,
                    metadata=cell.to_dict(),
                )
            )
        _add_cell_overflow_findings(findings, plan, child, cell)
    return findings


def _cartesian_cell_ids(input_cases: Sequence[str], state_cases: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"{input_case}:{state_case}" for input_case in input_cases for state_case in state_cases)


def _effective_expected_cell_ids(matrix: LeafBoundaryMatrix) -> tuple[str, ...]:
    if matrix.expected_cell_ids:
        return matrix.expected_cell_ids
    if matrix.input_cases and matrix.state_cases:
        return _cartesian_cell_ids(matrix.input_cases, matrix.state_cases)
    return ()


def _cartesian_matrix_findings(
    plan: LayeredBoundaryProofPlan,
    child: ChildProofContract,
    matrix: LeafBoundaryMatrix,
    expected_cell_ids: Sequence[str],
) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    if bool(matrix.input_cases) != bool(matrix.state_cases):
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_missing_cartesian_axis",
                "leaf boundary matrix must declare both input cases and state cases for Cartesian proof",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata=matrix.to_dict(),
            )
        )
        return findings
    if not matrix.input_cases and not matrix.state_cases:
        return findings

    cartesian_ids = _cartesian_cell_ids(matrix.input_cases, matrix.state_cases)
    missing_from_declared = tuple(sorted(set(cartesian_ids) - set(expected_cell_ids)))
    extra_declared = tuple(sorted(set(expected_cell_ids) - set(cartesian_ids)))
    if missing_from_declared or extra_declared:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_not_cartesian",
                "leaf boundary matrix expected cells do not match the declared Input x State Cartesian product",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={
                    "missing_from_declared": missing_from_declared,
                    "extra_declared": extra_declared,
                    "cartesian_cell_ids": cartesian_ids,
                    "matrix": matrix.to_dict(),
                },
            )
        )
    return findings


def _add_cell_overflow_findings(
    findings: list[LayeredBoundaryFinding],
    plan: LayeredBoundaryProofPlan,
    child: ChildProofContract,
    cell: LeafBoundaryMatrixCell,
) -> None:
    checks = (
        ("leaf_cell_missing_output", "leaf_cell_extra_output", "output", cell.expected_outputs, cell.observed_outputs),
        ("leaf_cell_missing_next_state", "leaf_cell_extra_next_state", "next state", cell.expected_next_states, cell.observed_next_states),
        ("leaf_cell_missing_state_write", "leaf_cell_extra_state_write", "state write", cell.expected_state_writes, cell.observed_state_writes),
        ("leaf_cell_missing_side_effect", "leaf_cell_extra_side_effect", "side effect", cell.expected_side_effects, cell.observed_side_effects),
        ("leaf_cell_missing_error_path", "leaf_cell_extra_error_path", "error path", cell.expected_error_paths, cell.observed_error_paths),
    )
    for missing_code, extra_code, noun, expected, actual in checks:
        missing_values = _missing(expected, actual)
        if missing_values:
            findings.append(
                LayeredBoundaryFinding(
                    missing_code,
                    f"leaf boundary cell did not observe declared {noun}",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    cell_id=cell.cell_id,
                    metadata={"missing": missing_values, "cell": cell.to_dict()},
                )
            )
        extra_values = _extra(expected, actual)
        if extra_values:
            findings.append(
                LayeredBoundaryFinding(
                    extra_code,
                    f"leaf boundary cell observed {noun} outside the declared allowance",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    cell_id=cell.cell_id,
                    metadata={"extra": extra_values, "cell": cell.to_dict()},
                )
            )


def _decision_for_findings(findings: Sequence[LayeredBoundaryFinding]) -> str:
    blockers = [finding for finding in findings if finding.severity in {"blocker", "refactor"}]
    if not blockers:
        return "layered_boundary_proof_green"
    priority = (
        ("parent_coverage_gap", "parent_coverage_gap_blocked"),
        ("unknown_child_owner", "parent_coverage_gap_blocked"),
        ("parent_item_illegal_overlap", "child_disjointness_blocked"),
        ("child_overlap_", "child_disjointness_blocked"),
        ("child_reattachment_", "child_reattachment_required"),
        ("child_evidence_not_current_pass", "child_evidence_not_current"),
        ("child_missing_evidence_id", "child_evidence_not_current"),
        ("leaf_split_required", "leaf_split_required"),
        ("child_split_required", "child_split_required"),
        ("leaf_matrix_missing", "leaf_boundary_matrix_required"),
        ("leaf_matrix_missing_cartesian_axis", "leaf_boundary_matrix_required"),
        ("leaf_matrix_not_cartesian", "leaf_boundary_matrix_required"),
        ("leaf_matrix_duplicate_cell", "leaf_boundary_matrix_required"),
        ("leaf_matrix_missing_cell", "leaf_boundary_matrix_required"),
        ("leaf_matrix_unexpected_cell", "leaf_boundary_matrix_required"),
        ("leaf_matrix_incomplete", "leaf_boundary_matrix_required"),
        ("leaf_cell_missing_", "leaf_boundary_underflow"),
        ("leaf_cell_extra_", "leaf_boundary_overflow"),
        ("leaf_cell_internal_path_only", "leaf_evidence_not_current"),
        ("leaf_cell_evidence_not_current_pass", "leaf_evidence_not_current"),
        ("leaf_cell_missing_evidence_id", "leaf_evidence_not_current"),
        ("leaf_matrix_stale", "leaf_evidence_not_current"),
    )
    codes = [finding.code for finding in blockers]
    for pattern, decision in priority:
        if any(code.startswith(pattern) for code in codes):
            return decision
    return "layered_boundary_proof_blocked"


def review_layered_boundary_proof(plan: LayeredBoundaryProofPlan) -> LayeredBoundaryProofReport:
    """Review parent/child/leaf proof closure without running project tests."""

    findings: list[LayeredBoundaryFinding] = []
    findings.extend(_coverage_findings(plan))
    findings.extend(_duplicate_child_field_findings(
        plan,
        field_name="responsibilities",
        allowed=plan.allowed_shared_responsibilities,
        code="child_overlap_responsibility",
        noun="responsibility",
    ))
    findings.extend(_duplicate_child_field_findings(
        plan,
        field_name="functions_owned",
        allowed=plan.allowed_shared_functions,
        code="child_overlap_function",
        noun="function",
    ))
    findings.extend(_duplicate_child_field_findings(
        plan,
        field_name="state_owned",
        allowed=plan.allowed_shared_state,
        code="child_overlap_state",
        noun="state",
    ))
    findings.extend(_duplicate_child_field_findings(
        plan,
        field_name="side_effects_owned",
        allowed=plan.allowed_shared_side_effects,
        code="child_overlap_side_effect",
        noun="side effect",
    ))
    findings.extend(_duplicate_child_field_findings(
        plan,
        field_name="invariants_owned",
        allowed=plan.allowed_shared_invariants,
        code="child_overlap_invariant",
        noun="invariant",
    ))
    findings.extend(_duplicate_child_field_findings(
        plan,
        field_name="risk_classes",
        allowed=plan.allowed_shared_risk_classes,
        code="child_overlap_risk_class",
        noun="risk class",
    ))
    findings.extend(_child_evidence_findings(plan))
    findings.extend(_reattachment_findings(plan))
    findings.extend(_leaf_matrix_findings(plan))

    blockers = tuple(finding for finding in findings if finding.severity in {"blocker", "refactor"})
    decision = _decision_for_findings(findings)
    return LayeredBoundaryProofReport(
        ok=not blockers,
        proof_id=plan.proof_id,
        parent_model_id=plan.parent_model_id,
        decision=decision,
        findings=tuple(findings),
    )


__all__ = [
    "ALLOWED_PARENT_ITEM_MODES",
    "ChildProofContract",
    "ChildReattachmentProof",
    "LeafBoundaryMatrix",
    "LeafBoundaryMatrixCell",
    "LayeredBoundaryFinding",
    "LayeredBoundaryProofPlan",
    "LayeredBoundaryProofReport",
    "NON_PASSING_PROOF_STATUSES",
    "OWNING_PARENT_ITEM_MODES",
    "PASSING_PROOF_STATUSES",
    "PROOF_OWNER_BRIDGE",
    "PROOF_OWNER_CHILD",
    "PROOF_OWNER_OUT_OF_SCOPE",
    "PROOF_OWNER_PARENT",
    "PROOF_OWNER_READ_ONLY",
    "PROOF_OWNER_SHARED_KERNEL",
    "PROOF_STATUS_ERROR",
    "PROOF_STATUS_FAILED",
    "PROOF_STATUS_NOT_RUN",
    "PROOF_STATUS_PASSED",
    "PROOF_STATUS_PROGRESS_ONLY",
    "PROOF_STATUS_RUNNING",
    "PROOF_STATUS_SKIPPED",
    "PROOF_STATUS_STALE",
    "ParentCoverageItem",
    "review_layered_boundary_proof",
]
