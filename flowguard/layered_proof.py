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

from ._normalization import string_sequence as _as_tuple
from .contract_exhaustion import (
    CONTRACT_GENERATION_LOCAL_CARTESIAN,
    ContractProductSignature,
)
from .export import to_jsonable
from .model_path_quality import (
    PathQualityMaterialReview,
    PathQualityResult,
    PathQualitySubject,
    normalize_path_quality_material,
    path_quality_result_set_fingerprint,
    review_path_quality_material,
)
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes
from .recursive_hierarchy import is_verified_subtree_receipt


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
    model_fingerprint: str = ""
    evidence_id: str = ""
    evidence_status: str = PROOF_STATUS_PASSED
    evidence_current: bool = True
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
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
    owner_id: str = ""
    parent_model_id: str = ""
    claim_scope: str = ""
    subtree_receipt_id: str = ""
    subtree_receipt_fingerprint: str = ""
    subtree_receipt: Any | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "model_fingerprint", str(self.model_fingerprint))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_status", str(self.evidence_status))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
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
        object.__setattr__(self, "owner_id", str(self.owner_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "subtree_receipt_id", str(self.subtree_receipt_id))
        object.__setattr__(
            self,
            "subtree_receipt_fingerprint",
            str(self.subtree_receipt_fingerprint),
        )

    def has_current_pass(self) -> bool:
        return self.evidence_status in PASSING_PROOF_STATUSES and self.evidence_current

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_model_id": self.child_model_id,
            "model_fingerprint": self.model_fingerprint,
            "evidence_id": self.evidence_id,
            "evidence_status": self.evidence_status,
            "evidence_current": self.evidence_current,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
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
            "owner_id": self.owner_id,
            "parent_model_id": self.parent_model_id,
            "claim_scope": self.claim_scope,
            "subtree_receipt_id": self.subtree_receipt_id,
            "subtree_receipt_fingerprint": self.subtree_receipt_fingerprint,
            "subtree_receipt": (
                self.subtree_receipt.to_dict()
                if hasattr(self.subtree_receipt, "to_dict")
                else to_jsonable(self.subtree_receipt)
            ),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ChildReattachmentProof:
    """Parent expectations for one child handoff."""

    child_model_id: str
    consumed_evidence_id: str = ""
    consumed_model_fingerprint: str = ""
    consumed_owner_id: str = ""
    consumed_parent_model_id: str = ""
    consumed_claim_scope: str = ""
    consumed_obligation_ids: tuple[str, ...] = ()
    consumed_subtree_receipt_id: str = ""
    consumed_subtree_receipt_fingerprint: str = ""
    consumed_path_quality_result_fingerprint: str = ""
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
        object.__setattr__(self, "consumed_model_fingerprint", str(self.consumed_model_fingerprint))
        object.__setattr__(self, "consumed_owner_id", str(self.consumed_owner_id))
        object.__setattr__(self, "consumed_parent_model_id", str(self.consumed_parent_model_id))
        object.__setattr__(self, "consumed_claim_scope", str(self.consumed_claim_scope))
        object.__setattr__(self, "consumed_obligation_ids", _as_tuple(self.consumed_obligation_ids))
        object.__setattr__(self, "consumed_subtree_receipt_id", str(self.consumed_subtree_receipt_id))
        object.__setattr__(
            self,
            "consumed_subtree_receipt_fingerprint",
            str(self.consumed_subtree_receipt_fingerprint),
        )
        object.__setattr__(
            self,
            "consumed_path_quality_result_fingerprint",
            str(self.consumed_path_quality_result_fingerprint),
        )
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
            "consumed_model_fingerprint": self.consumed_model_fingerprint,
            "consumed_owner_id": self.consumed_owner_id,
            "consumed_parent_model_id": self.consumed_parent_model_id,
            "consumed_claim_scope": self.consumed_claim_scope,
            "consumed_obligation_ids": list(self.consumed_obligation_ids),
            "consumed_subtree_receipt_id": self.consumed_subtree_receipt_id,
            "consumed_subtree_receipt_fingerprint": self.consumed_subtree_receipt_fingerprint,
            "consumed_path_quality_result_fingerprint": (
                self.consumed_path_quality_result_fingerprint
            ),
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
    runtime_node_ids: tuple[str, ...] = ()
    runtime_path_evidence_ids: tuple[str, ...] = ()
    evidence_status: str = PROOF_STATUS_PASSED
    evidence_current: bool = True
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
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
        object.__setattr__(self, "runtime_node_ids", _as_tuple(self.runtime_node_ids))
        object.__setattr__(self, "runtime_path_evidence_ids", _as_tuple(self.runtime_path_evidence_ids))
        object.__setattr__(self, "evidence_status", str(self.evidence_status))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
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
            "runtime_node_ids": list(self.runtime_node_ids),
            "runtime_path_evidence_ids": list(self.runtime_path_evidence_ids),
            "evidence_status": self.evidence_status,
            "evidence_current": self.evidence_current,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
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
    degenerate_boundary_disposition: str = ""
    scoped_exemption: str = ""
    evidence_current: bool = True
    # ``product_signature`` remains the compact fingerprint used by older
    # callers.  New callers may provide the full ContractProductSignature (or
    # the explicit canonical_product_signature field); the reviewer always
    # compares that typed identity to a kernel-derived signature.
    product_signature: str | ContractProductSignature | Mapping[str, Any] = ""
    canonical_product: tuple[str, ...] = ()
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # Explicit input/state axis identities and their content fingerprints.  A
    # matrix with no supplied ids gets the stable ``input``/``state`` ids so
    # existing one-input/one-state fixtures remain source compatible while
    # still receiving a deterministic kernel-owned fingerprint.
    input_axis_id: str = ""
    state_axis_id: str = ""
    input_axis_fingerprint: str = ""
    state_axis_fingerprint: str = ""
    axis_fingerprints: Mapping[str, str] = field(default_factory=dict)
    canonical_product_signature: ContractProductSignature | Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "leaf_model_id", str(self.leaf_model_id))
        object.__setattr__(self, "matrix_id", str(self.matrix_id))
        object.__setattr__(self, "input_cases", _as_tuple(self.input_cases))
        object.__setattr__(self, "state_cases", _as_tuple(self.state_cases))
        object.__setattr__(self, "expected_cell_ids", _as_tuple(self.expected_cell_ids))
        object.__setattr__(self, "cells", tuple(self.cells))
        object.__setattr__(self, "degenerate_boundary_disposition", str(self.degenerate_boundary_disposition).strip())
        object.__setattr__(self, "scoped_exemption", str(self.scoped_exemption))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "canonical_product", _as_tuple(self.canonical_product))
        # Normalize a typed/mapping product supplied through either field.  A
        # supplied stale fingerprint is intentionally retained for review;
        # construction must not silently repair evidence supplied by a
        # caller.
        supplied_product = self.product_signature
        supplied_canonical = self.canonical_product_signature
        if supplied_canonical is None and isinstance(
            supplied_product, (ContractProductSignature, Mapping)
        ):
            supplied_canonical = _coerce_leaf_product_signature(supplied_product)
            supplied_product = supplied_canonical.fingerprint if supplied_canonical else ""
        elif supplied_canonical is not None:
            supplied_canonical = _coerce_leaf_product_signature(supplied_canonical)
        object.__setattr__(self, "canonical_product_signature", supplied_canonical)
        object.__setattr__(self, "product_signature", str(supplied_product or ""))

        raw_axis_fingerprints = {
            str(axis_id): str(fingerprint)
            for axis_id, fingerprint in dict(self.axis_fingerprints).items()
        }
        input_axis_id = str(self.input_axis_id or "")
        state_axis_id = str(self.state_axis_id or "")
        if not input_axis_id:
            input_axis_id = next(
                (
                    candidate
                    for candidate in ("input", "input_axis")
                    if candidate in raw_axis_fingerprints
                ),
                "input",
            )
        if not state_axis_id:
            state_axis_id = next(
                (
                    candidate
                    for candidate in ("state", "state_axis")
                    if candidate in raw_axis_fingerprints
                ),
                "state",
            )
        # A supplied canonical signature can carry the axis ids.  Use those
        # only when the matrix did not name ids itself; values remain owned by
        # this matrix's input_cases/state_cases and are checked below.
        if supplied_canonical is not None:
            signature_axis_ids = tuple(supplied_canonical.axis_ids)
            if not self.input_axis_id and signature_axis_ids:
                input_axis_id = signature_axis_ids[0]
            if not self.state_axis_id and len(signature_axis_ids) > 1:
                state_axis_id = signature_axis_ids[1]
        object.__setattr__(self, "input_axis_id", input_axis_id)
        object.__setattr__(self, "state_axis_id", state_axis_id)

        if self.input_cases:
            raw_axis_fingerprints.setdefault(
                input_axis_id,
                str(self.input_axis_fingerprint)
                or _leaf_axis_fingerprint(
                    self.leaf_model_id, input_axis_id, "input", self.input_cases
                ),
            )
        if self.state_cases:
            raw_axis_fingerprints.setdefault(
                state_axis_id,
                str(self.state_axis_fingerprint)
                or _leaf_axis_fingerprint(
                    self.leaf_model_id, state_axis_id, "state", self.state_cases
                ),
            )
        # Explicit singular fields override a map entry, which makes stale
        # singular declarations observable rather than silently discarded.
        if self.input_axis_fingerprint:
            raw_axis_fingerprints[input_axis_id] = str(self.input_axis_fingerprint)
        if self.state_axis_fingerprint:
            raw_axis_fingerprints[state_axis_id] = str(self.state_axis_fingerprint)
        object.__setattr__(self, "axis_fingerprints", dict(sorted(raw_axis_fingerprints.items())))
        object.__setattr__(
            self,
            "input_axis_fingerprint",
            str(raw_axis_fingerprints.get(input_axis_id, "")),
        )
        object.__setattr__(
            self,
            "state_axis_fingerprint",
            str(raw_axis_fingerprints.get(state_axis_id, "")),
        )
        if self.input_cases and self.state_cases:
            canonical_product = _cartesian_cell_ids(self.input_cases, self.state_cases)
            if not self.canonical_product:
                object.__setattr__(self, "canonical_product", canonical_product)
            expected_product_signature = _canonical_leaf_product_signature(self)
            if self.canonical_product_signature is None:
                object.__setattr__(
                    self,
                    "canonical_product_signature",
                    expected_product_signature,
                )
            if not self.product_signature:
                object.__setattr__(
                    self,
                    "product_signature",
                    expected_product_signature.fingerprint,
                )

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
            "degenerate_boundary_disposition": self.degenerate_boundary_disposition,
            "scoped_exemption": self.scoped_exemption,
            "evidence_current": self.evidence_current,
            "product_signature": self.product_signature,
            "canonical_product": list(self.canonical_product),
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
            "input_axis_id": self.input_axis_id,
            "state_axis_id": self.state_axis_id,
            "input_axis_fingerprint": self.input_axis_fingerprint,
            "state_axis_fingerprint": self.state_axis_fingerprint,
            "axis_fingerprints": dict(self.axis_fingerprints),
            "canonical_product_signature": (
                self.canonical_product_signature.to_dict()
                if self.canonical_product_signature is not None
                else None
            ),
        }


def _coerce_leaf_product_signature(
    value: ContractProductSignature | Mapping[str, Any] | None,
) -> ContractProductSignature | None:
    """Normalize the typed product signature accepted by a leaf matrix."""

    if value is None:
        return None
    if isinstance(value, ContractProductSignature):
        return value
    if isinstance(value, Mapping):
        return ContractProductSignature(
            signature_id=str(value.get("signature_id", "")),
            model_id=str(value.get("model_id", "")),
            interaction_group_id=str(value.get("interaction_group_id", "")),
            axis_ids=value.get("axis_ids", ()),
            axis_value_ids=value.get("axis_value_ids", {}),
            expected_cardinality=value.get("expected_cardinality", 0),
            partition_revision=str(value.get("partition_revision", "")),
            generation_kind=str(
                value.get("generation_kind", CONTRACT_GENERATION_LOCAL_CARTESIAN)
            ),
            shard_plan_fingerprint=str(value.get("shard_plan_fingerprint", "")),
            fingerprint=str(value.get("fingerprint", "")),
            axis_fingerprints=value.get("axis_fingerprints", {}),
            parent_interface_contract_id=str(
                value.get("parent_interface_contract_id", "")
            ),
            refinement_contract_id=str(value.get("refinement_contract_id", "")),
            interface_model_ids=value.get("interface_model_ids", ()),
        )
    raise TypeError(
        "canonical_product_signature must be a ContractProductSignature or mapping"
    )


def _leaf_axis_fingerprint(
    leaf_model_id: str,
    axis_id: str,
    axis_kind: str,
    cases: Sequence[str],
) -> str:
    """Derive the only supported fingerprint for a leaf finite axis."""

    from .model_authority import canonical_fingerprint

    return canonical_fingerprint(
        {
            "leaf_model_id": str(leaf_model_id),
            "axis_id": str(axis_id),
            "axis_kind": str(axis_kind),
            "cases": list(cases),
        }
    )


def _canonical_leaf_product_signature(
    matrix: LeafBoundaryMatrix,
) -> ContractProductSignature:
    """Build a typed product identity from the matrix's finite axes only."""

    axis_ids = (matrix.input_axis_id, matrix.state_axis_id)
    return ContractProductSignature(
        signature_id=f"contract_product:{matrix.leaf_model_id}:{matrix.matrix_id or 'leaf'}",
        model_id=matrix.leaf_model_id,
        interaction_group_id=matrix.matrix_id or f"{matrix.leaf_model_id}:leaf",
        axis_ids=axis_ids,
        axis_value_ids={
            matrix.input_axis_id: tuple(matrix.input_cases),
            matrix.state_axis_id: tuple(matrix.state_cases),
        },
        expected_cardinality=len(matrix.input_cases) * len(matrix.state_cases),
        partition_revision=str(
            matrix.metadata.get("partition_revision", "")
            if isinstance(matrix.metadata, Mapping)
            else ""
        ),
        generation_kind=CONTRACT_GENERATION_LOCAL_CARTESIAN,
        shard_plan_fingerprint=str(
            matrix.metadata.get("shard_plan_fingerprint", "")
            if isinstance(matrix.metadata, Mapping)
            else ""
        ),
        axis_fingerprints={
            matrix.input_axis_id: matrix.input_axis_fingerprint,
            matrix.state_axis_id: matrix.state_axis_fingerprint,
        },
    )


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
    require_proof_artifacts: bool = False
    allow_scoped_leaf_exemptions: bool = False
    claim_scope: str = "full"
    rationale: str = ""
    required_path_quality_model_ids: tuple[str, ...] = ()
    path_quality_subjects: tuple[PathQualitySubject | Mapping[str, Any], ...] = ()
    path_quality_results: tuple[PathQualityResult | Mapping[str, Any], ...] = ()
    path_quality_currentness_id: str = ""
    path_quality_result_set_fingerprint: str = ""
    subtree_receipts: tuple[Any, ...] = ()
    strict: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", str(self.proof_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "parent_items", tuple(self.parent_items))
        object.__setattr__(self, "child_contracts", tuple(self.child_contracts))
        object.__setattr__(self, "reattachment_proofs", tuple(self.reattachment_proofs))
        object.__setattr__(self, "leaf_matrices", tuple(self.leaf_matrices))
        object.__setattr__(self, "subtree_receipts", tuple(self.subtree_receipts))
        if self.strict is not None:
            object.__setattr__(self, "strict", bool(self.strict))
        object.__setattr__(self, "allowed_shared_responsibilities", _as_tuple(self.allowed_shared_responsibilities))
        object.__setattr__(self, "allowed_shared_functions", _as_tuple(self.allowed_shared_functions))
        object.__setattr__(self, "allowed_shared_state", _as_tuple(self.allowed_shared_state))
        object.__setattr__(self, "allowed_shared_side_effects", _as_tuple(self.allowed_shared_side_effects))
        object.__setattr__(self, "allowed_shared_invariants", _as_tuple(self.allowed_shared_invariants))
        object.__setattr__(self, "allowed_shared_risk_classes", _as_tuple(self.allowed_shared_risk_classes))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "rationale", str(self.rationale))
        required_models, subjects, results = normalize_path_quality_material(
            self.required_path_quality_model_ids,
            self.path_quality_subjects,
            self.path_quality_results,
        )
        result_set_fingerprint = (
            path_quality_result_set_fingerprint(required_models, subjects, results)
            if required_models or subjects or results
            else ""
        )
        supplied_result_set_fingerprint = str(self.path_quality_result_set_fingerprint)
        if (
            supplied_result_set_fingerprint
            and supplied_result_set_fingerprint != result_set_fingerprint
        ):
            raise ValueError("layered proof path-quality result set fingerprint is stale")
        object.__setattr__(self, "required_path_quality_model_ids", required_models)
        object.__setattr__(self, "path_quality_subjects", subjects)
        object.__setattr__(self, "path_quality_results", results)
        object.__setattr__(
            self,
            "path_quality_currentness_id",
            str(self.path_quality_currentness_id),
        )
        object.__setattr__(
            self,
            "path_quality_result_set_fingerprint",
            result_set_fingerprint,
        )

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
            "require_proof_artifacts": self.require_proof_artifacts,
            "allow_scoped_leaf_exemptions": self.allow_scoped_leaf_exemptions,
            "claim_scope": self.claim_scope,
            "rationale": self.rationale,
            "required_path_quality_model_ids": list(self.required_path_quality_model_ids),
            "path_quality_subjects": [
                subject.to_dict() for subject in self.path_quality_subjects
            ],
            "path_quality_results": [
                result.to_compact_dict() for result in self.path_quality_results
            ],
            "path_quality_currentness_id": self.path_quality_currentness_id,
            "path_quality_result_set_fingerprint": (
                self.path_quality_result_set_fingerprint
            ),
            "subtree_receipts": [
                receipt.to_dict() if hasattr(receipt, "to_dict") else to_jsonable(receipt)
                for receipt in self.subtree_receipts
            ],
            "strict": self.is_strict(),
        }

    def is_strict(self) -> bool:
        """Whether this plan makes declaration-only shortcuts unavailable."""

        # Broad scopes are hard gates.  An explicit ``strict=False`` may opt a
        # routine/design plan out of strict checks, but it must not downgrade
        # a full/release/whole-domain/system claim and thereby reopen the
        # caller-denominator shortcut.
        broad_scope = self.claim_scope in {
            "full",
            "release",
            "whole_domain",
            "whole-domain",
            "whole_system",
            "whole-system",
            "parent_confidence",
            "parent-confidence",
        }
        if broad_scope:
            return True
        if self.strict is not None:
            return bool(self.strict)
        return False


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
    path_quality_result_set_fingerprint: str = ""
    path_quality_verified_model_ids: tuple[str, ...] = ()
    path_quality_blocked_model_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", str(self.proof_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "path_quality_result_set_fingerprint",
            str(self.path_quality_result_set_fingerprint),
        )
        object.__setattr__(
            self,
            "path_quality_verified_model_ids",
            _as_tuple(self.path_quality_verified_model_ids),
        )
        object.__setattr__(
            self,
            "path_quality_blocked_model_ids",
            _as_tuple(self.path_quality_blocked_model_ids),
        )
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
            "path_quality_result_set_fingerprint": (
                self.path_quality_result_set_fingerprint
            ),
            "path_quality_verified_model_ids": list(
                self.path_quality_verified_model_ids
            ),
            "path_quality_blocked_model_ids": list(
                self.path_quality_blocked_model_ids
            ),
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
        if plan.require_proof_artifacts:
            for code, message in proof_artifact_gap_codes(
                child.proof_artifact,
                declared_status=child.evidence_status,
                required_obligation_ids=child.responsibilities or child.functions_owned,
                require_result_path=True,
                require_fingerprints=True,
                require_external_scope=True,
            ):
                findings.append(
                    LayeredBoundaryFinding(
                        f"child_{code}",
                        message,
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


def _subtree_receipt_findings(plan: LayeredBoundaryProofPlan) -> list[LayeredBoundaryFinding]:
    """Require a verified, exact child subtree receipt for every non-leaf.

    A plain ``passed``/``current`` child row is intentionally insufficient in
    strict full/release plans.  The receipt is checked by identity as well as
    status so a receipt from another model, owner, parent, scope, or
    obligation set cannot be reattached accidentally.
    """

    if not plan.is_strict():
        return []
    findings: list[LayeredBoundaryFinding] = []
    receipt_by_id = {
        str(getattr(receipt, "receipt_id", "") or (receipt.get("receipt_id", "") if isinstance(receipt, Mapping) else "")): receipt
        for receipt in plan.subtree_receipts
    }

    def value(receipt: Any, name: str, default: Any = "") -> Any:
        if isinstance(receipt, Mapping):
            return receipt.get(name, default)
        return getattr(receipt, name, default)

    for child in plan.child_contracts:
        if not child.owner_id:
            findings.append(
                LayeredBoundaryFinding(
                    "child_owner_id_missing",
                    "strict child proof must name its single owner id",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                )
            )
        if not child.model_fingerprint:
            findings.append(
                LayeredBoundaryFinding(
                    "child_model_fingerprint_missing",
                    "strict child proof must freeze the model fingerprint",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                )
            )
        if child.parent_model_id and child.parent_model_id != plan.parent_model_id:
            findings.append(
                LayeredBoundaryFinding(
                    "child_parent_model_mismatch",
                    "child proof names a different parent model",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={"expected": plan.parent_model_id, "actual": child.parent_model_id},
                )
            )
        if child.claim_scope and child.claim_scope != plan.claim_scope:
            findings.append(
                LayeredBoundaryFinding(
                    "child_claim_scope_mismatch",
                    "child proof claim scope differs from the parent proof scope",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={"expected": plan.claim_scope, "actual": child.claim_scope},
                )
            )
        if child.is_leaf:
            continue
        receipt = child.subtree_receipt
        if receipt is None and child.subtree_receipt_id:
            receipt = receipt_by_id.get(child.subtree_receipt_id)
        if receipt is None:
            findings.append(
                LayeredBoundaryFinding(
                    "child_subtree_receipt_missing",
                    "strict non-leaf child must consume a verified subtree receipt",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                )
            )
            continue
        if not is_verified_subtree_receipt(receipt):
            findings.append(
                LayeredBoundaryFinding(
                    "child_subtree_receipt_not_verified",
                    "non-leaf child receipt is not a verified terminal receipt",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={"receipt": to_jsonable(receipt)},
                )
            )
        expected_values = {
            "receipt_id": child.subtree_receipt_id,
            "fingerprint": child.subtree_receipt_fingerprint,
            "model_id": child.child_model_id,
            "model_fingerprint": child.model_fingerprint,
            "owner_id": child.owner_id,
            "parent_model_id": plan.parent_model_id,
            "claim_scope": plan.claim_scope,
            "obligation_ids": tuple(child.responsibilities),
        }
        for name, expected in expected_values.items():
            if not expected:
                continue
            actual = value(receipt, name, ()) if name == "obligation_ids" else value(receipt, name, "")
            actual_values = _as_tuple(actual) if name == "obligation_ids" else str(actual)
            if actual_values != expected:
                findings.append(
                    LayeredBoundaryFinding(
                        f"child_subtree_receipt_{name}_mismatch",
                        f"child subtree receipt {name} does not match the exact parent contract",
                        parent_model_id=plan.parent_model_id,
                        child_model_id=child.child_model_id,
                        metadata={"expected": expected, "actual": actual_values},
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


def _path_quality_review(plan: LayeredBoundaryProofPlan) -> PathQualityMaterialReview:
    children = {child.child_model_id: child for child in plan.child_contracts}
    expected_model_fingerprints = {
        model_id: children[model_id].model_fingerprint
        for model_id in plan.required_path_quality_model_ids
        if model_id in children and children[model_id].model_fingerprint
    }
    return review_path_quality_material(
        plan.required_path_quality_model_ids,
        plan.path_quality_subjects,
        plan.path_quality_results,
        expected_currentness_id=plan.path_quality_currentness_id,
        expected_model_fingerprints=expected_model_fingerprints,
        require_exact_currentness=bool(plan.required_path_quality_model_ids),
        require_exact_model_fingerprints=bool(plan.required_path_quality_model_ids),
    )


def _path_quality_findings(
    plan: LayeredBoundaryProofPlan,
    review: PathQualityMaterialReview,
) -> list[LayeredBoundaryFinding]:
    findings = [
        LayeredBoundaryFinding(
            gap.code,
            "required child path-quality material is not exact-current and closed",
            parent_model_id=plan.parent_model_id,
            child_model_id=gap.model_id,
            metadata={
                "path_quality_gap": gap.to_dict(),
                "path_quality_material": review.to_compact_dict(),
            },
        )
        for gap in review.gaps
    ]
    subjects_by_model = {
        subject.model_id: subject for subject in review.subjects
    }
    results_by_subject = {
        result.subject_fingerprint: result for result in review.results
    }
    proofs_by_child = {
        proof.child_model_id: proof for proof in plan.reattachment_proofs
    }
    for model_id in review.required_model_ids:
        subject = subjects_by_model.get(model_id)
        result = (
            results_by_subject.get(subject.fingerprint)
            if subject is not None
            else None
        )
        proof = proofs_by_child.get(model_id)
        if proof is None:
            findings.append(
                LayeredBoundaryFinding(
                    "child_reattachment_path_quality_result_missing",
                    "parent layered proof does not consume this required child path-quality result",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=model_id,
                )
            )
        elif result is None or (
            proof.consumed_path_quality_result_fingerprint != result.fingerprint
        ):
            findings.append(
                LayeredBoundaryFinding(
                    "child_reattachment_path_quality_result_stale",
                    "parent layered proof consumed a missing, stale, or foreign child path-quality result",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=model_id,
                    metadata={
                        "expected_result_fingerprint": (
                            result.fingerprint if result is not None else ""
                        ),
                        "consumed_result_fingerprint": (
                            proof.consumed_path_quality_result_fingerprint
                        ),
                    },
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

    explicit_degenerate = _leaf_degenerate_is_allowed(plan, matrix)
    if plan.is_strict():
        if not matrix.input_cases or not matrix.state_cases:
            if explicit_degenerate:
                findings.append(
                    LayeredBoundaryFinding(
                        "leaf_matrix_degenerate_boundary_scoped",
                        "leaf proof uses an explicitly declared degenerate boundary disposition and remains scoped",
                        severity="warning",
                        parent_model_id=plan.parent_model_id,
                        child_model_id=child.child_model_id,
                        metadata=matrix.to_dict(),
                    )
                )
            else:
                findings.append(
                    LayeredBoundaryFinding(
                        "leaf_matrix_canonical_axes_missing",
                        "full or release leaf proof requires non-empty input and state axes generated by the kernel",
                        parent_model_id=plan.parent_model_id,
                        child_model_id=child.child_model_id,
                        metadata=matrix.to_dict(),
                    )
                )
        else:
            findings.extend(_leaf_axis_findings(plan, child, matrix))
            findings.extend(_leaf_product_signature_findings(plan, child, matrix))

    declared_expected_cell_ids = _effective_expected_cell_ids(matrix)
    expected_cell_ids = declared_expected_cell_ids
    canonical_expected_cell_ids: tuple[str, ...] = ()
    if matrix.input_cases and matrix.state_cases:
        canonical_expected_cell_ids = _cartesian_cell_ids(
            matrix.input_cases,
            matrix.state_cases,
        )
        if matrix.canonical_product and tuple(matrix.canonical_product) != canonical_expected_cell_ids:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_matrix_canonical_product_mismatch",
                    "leaf canonical product does not match the Input x State axes",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={
                        "expected": canonical_expected_cell_ids,
                        "actual": matrix.canonical_product,
                        "matrix": matrix.to_dict(),
                    },
                )
            )
        # In a strict full/release claim the kernel-derived product is the
        # denominator.  A caller-supplied expected list remains a diagnostic
        # comparison only and cannot shrink or expand the covered universe.
        if plan.is_strict():
            expected_cell_ids = canonical_expected_cell_ids
    if plan.is_strict() and matrix.input_cases and matrix.state_cases:
        if matrix.expected_cell_ids and tuple(matrix.expected_cell_ids) != canonical_expected_cell_ids:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_matrix_expected_cells_not_canonical",
                    "full or release leaf proof cannot use a self-reported denominator outside the canonical Input x State product",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={
                        "expected_cell_ids": list(matrix.expected_cell_ids),
                        "canonical_expected_cell_ids": list(canonical_expected_cell_ids),
                        "matrix": matrix.to_dict(),
                    },
                )
            )
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

    # Compare an explicitly supplied denominator against the canonical
    # product, while using the canonical product itself for strict coverage.
    findings.extend(
        _cartesian_matrix_findings(
            plan,
            child,
            matrix,
            declared_expected_cell_ids,
            allow_degenerate=explicit_degenerate,
        )
    )
    cell_ids = set(cell_id_counts)
    missing_cells = tuple(sorted(set(expected_cell_ids) - cell_ids))
    # Keep the historical ``leaf_matrix_missing_cell`` diagnostic for an
    # explicitly supplied denominator as well.  In a strict proof the
    # canonical Input x State product is the authoritative denominator, but
    # a caller-declared cell that is absent from the evidence is still a
    # useful concrete gap (and must not disappear merely because the caller
    # also declared an extra/non-canonical cell).
    declared_missing_cells = tuple(sorted(set(declared_expected_cell_ids) - cell_ids))
    missing_cells = tuple(sorted(set(missing_cells) | set(declared_missing_cells)))
    if missing_cells:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_missing_cell",
                "leaf boundary matrix is missing expected Input x State cells",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={
                    "missing_cells": missing_cells,
                    "canonical_missing_cells": tuple(
                        sorted(set(expected_cell_ids) - cell_ids)
                    ),
                    "declared_missing_cells": declared_missing_cells,
                    "matrix": matrix.to_dict(),
                },
            )
        )
    if (
        plan.is_strict()
        and canonical_expected_cell_ids
        and matrix.expected_cell_ids
        and tuple(matrix.expected_cell_ids) != canonical_expected_cell_ids
    ):
        caller_missing_cells = tuple(
            sorted(set(matrix.expected_cell_ids) - cell_ids)
        )
        if caller_missing_cells:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_matrix_declared_cell_missing",
                    "caller-supplied expected cells are incomplete; canonical coverage remains kernel-derived",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={
                        "declared_missing_cells": caller_missing_cells,
                        "canonical_expected_cell_ids": list(canonical_expected_cell_ids),
                        "matrix": matrix.to_dict(),
                    },
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
        if plan.require_proof_artifacts:
            for code, message in proof_artifact_gap_codes(
                cell.proof_artifact,
                declared_status=cell.evidence_status,
                required_obligation_ids=cell.evidence_ids,
                require_result_path=True,
                require_fingerprints=True,
                require_external_scope=True,
            ):
                findings.append(
                    LayeredBoundaryFinding(
                        f"leaf_cell_{code}",
                        message,
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
        if cell.runtime_node_ids and not cell.runtime_path_evidence_ids:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_cell_missing_runtime_path_evidence",
                    "leaf boundary cell declares runtime nodes but has no runtime path evidence id",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    cell_id=cell.cell_id,
                    metadata=cell.to_dict(),
                )
            )
        _add_cell_overflow_findings(findings, plan, child, cell)
    return findings


def _leaf_degenerate_is_allowed(
    plan: LayeredBoundaryProofPlan,
    matrix: LeafBoundaryMatrix,
) -> bool:
    """Whether a strict leaf has an explicit, scoped degenerate boundary."""

    return bool(
        plan.is_strict()
        and plan.allow_scoped_leaf_exemptions
        and matrix.degenerate_boundary_disposition.startswith("degenerate:")
        and matrix.scoped_exemption
    )


def _leaf_axis_findings(
    plan: LayeredBoundaryProofPlan,
    child: ChildProofContract,
    matrix: LeafBoundaryMatrix,
) -> list[LayeredBoundaryFinding]:
    """Validate the two kernel-owned finite axis identities for a leaf."""

    findings: list[LayeredBoundaryFinding] = []
    if not matrix.input_cases or not matrix.state_cases:
        return findings
    expected = {
        matrix.input_axis_id: _leaf_axis_fingerprint(
            matrix.leaf_model_id,
            matrix.input_axis_id,
            "input",
            matrix.input_cases,
        ),
        matrix.state_axis_id: _leaf_axis_fingerprint(
            matrix.leaf_model_id,
            matrix.state_axis_id,
            "state",
            matrix.state_cases,
        ),
    }
    if matrix.input_axis_id == matrix.state_axis_id:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_duplicate_axis",
                "leaf input and state axes must be distinct finite axes",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"axis_id": matrix.input_axis_id, "matrix": matrix.to_dict()},
            )
        )
    actual = dict(matrix.axis_fingerprints)
    for axis_id, expected_fingerprint in expected.items():
        supplied = str(actual.get(axis_id, ""))
        if not supplied:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_matrix_axis_fingerprint_missing",
                    "leaf finite axis has no content fingerprint",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={
                        "axis_id": axis_id,
                        "expected": expected_fingerprint,
                        "matrix": matrix.to_dict(),
                    },
                )
            )
        elif supplied != expected_fingerprint:
            findings.append(
                LayeredBoundaryFinding(
                    "leaf_matrix_axis_fingerprint_mismatch",
                    "leaf finite axis fingerprint does not match its declared cases",
                    parent_model_id=plan.parent_model_id,
                    child_model_id=child.child_model_id,
                    metadata={
                        "axis_id": axis_id,
                        "expected": expected_fingerprint,
                        "actual": supplied,
                        "matrix": matrix.to_dict(),
                    },
                )
            )
    extra_axis_ids = tuple(sorted(set(actual) - set(expected)))
    if extra_axis_ids:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_foreign_axis",
                "leaf boundary matrix declares an axis outside its input/state finite boundary",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"axis_ids": extra_axis_ids, "matrix": matrix.to_dict()},
            )
        )
    return findings


def _leaf_product_signature_findings(
    plan: LayeredBoundaryProofPlan,
    child: ChildProofContract,
    matrix: LeafBoundaryMatrix,
) -> list[LayeredBoundaryFinding]:
    """Require a typed ContractProductSignature for a strict non-degenerate leaf."""

    if not matrix.input_cases or not matrix.state_cases:
        return []
    expected = _canonical_leaf_product_signature(matrix)
    actual = matrix.canonical_product_signature
    findings: list[LayeredBoundaryFinding] = []
    if actual is None:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_product_signature_missing",
                "strict leaf proof requires a typed canonical ContractProductSignature",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"expected": expected.to_dict(), "matrix": matrix.to_dict()},
            )
        )
        return findings
    if not actual.is_self_consistent():
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_product_signature_invalid",
                "leaf canonical ContractProductSignature is not self-consistent",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"expected": expected.to_dict(), "actual": actual.to_dict()},
            )
        )
    if actual.identity_payload() != expected.identity_payload():
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_product_signature_mismatch",
                "leaf product signature does not match the kernel-derived Input x State axes",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={"expected": expected.to_dict(), "actual": actual.to_dict()},
            )
        )
    if matrix.product_signature != expected.fingerprint:
        findings.append(
            LayeredBoundaryFinding(
                "leaf_matrix_product_signature_mismatch",
                "leaf compact product signature is not the canonical typed product fingerprint",
                parent_model_id=plan.parent_model_id,
                child_model_id=child.child_model_id,
                metadata={
                    "expected": expected.fingerprint,
                    "actual": matrix.product_signature,
                    "matrix": matrix.to_dict(),
                },
            )
        )
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
    *,
    allow_degenerate: bool = False,
) -> list[LayeredBoundaryFinding]:
    findings: list[LayeredBoundaryFinding] = []
    if bool(matrix.input_cases) != bool(matrix.state_cases):
        if allow_degenerate:
            return findings
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
        ("path_quality_", "path_quality_closure_required"),
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
        ("leaf_matrix_canonical_axes_missing", "leaf_boundary_matrix_required"),
        ("leaf_matrix_axis_fingerprint_missing", "leaf_boundary_matrix_required"),
        ("leaf_matrix_axis_fingerprint_mismatch", "leaf_boundary_matrix_required"),
        ("leaf_matrix_foreign_axis", "leaf_boundary_matrix_required"),
        ("leaf_matrix_duplicate_axis", "leaf_boundary_matrix_required"),
        ("leaf_matrix_product_signature_missing", "leaf_boundary_matrix_required"),
        ("leaf_matrix_product_signature_invalid", "leaf_boundary_matrix_required"),
        ("leaf_matrix_product_signature_mismatch", "leaf_boundary_matrix_required"),
        ("leaf_matrix_canonical_product_mismatch", "leaf_boundary_matrix_required"),
        ("leaf_matrix_missing_cartesian_axis", "leaf_boundary_matrix_required"),
        ("leaf_matrix_not_cartesian", "leaf_boundary_matrix_required"),
        ("leaf_matrix_duplicate_cell", "leaf_boundary_matrix_required"),
        ("leaf_matrix_missing_cell", "leaf_boundary_matrix_required"),
        ("leaf_matrix_unexpected_cell", "leaf_boundary_matrix_required"),
        ("leaf_matrix_incomplete", "leaf_boundary_matrix_required"),
        ("leaf_cell_missing_runtime_path_evidence", "leaf_evidence_not_current"),
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
    path_quality_review = _path_quality_review(plan)
    path_quality_findings = _path_quality_findings(plan, path_quality_review)
    findings.extend(path_quality_findings)
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
    findings.extend(_subtree_receipt_findings(plan))
    findings.extend(_reattachment_findings(plan))
    findings.extend(_leaf_matrix_findings(plan))

    path_quality_consumer_blocked = set(path_quality_review.blocked_model_ids)
    for finding in path_quality_findings:
        if finding.child_model_id in path_quality_review.required_model_ids:
            path_quality_consumer_blocked.add(finding.child_model_id)
        elif not finding.child_model_id:
            path_quality_consumer_blocked.update(path_quality_review.required_model_ids)
    path_quality_consumer_blocked_model_ids = tuple(
        sorted(path_quality_consumer_blocked)
    )
    blockers = tuple(finding for finding in findings if finding.severity in {"blocker", "refactor"})
    decision = _decision_for_findings(findings)
    return LayeredBoundaryProofReport(
        ok=not blockers,
        proof_id=plan.proof_id,
        parent_model_id=plan.parent_model_id,
        decision=decision,
        findings=tuple(findings),
        path_quality_result_set_fingerprint=(
            path_quality_review.result_set_fingerprint
            if (
                plan.required_path_quality_model_ids
                or plan.path_quality_subjects
                or plan.path_quality_results
            )
            else ""
        ),
        path_quality_verified_model_ids=tuple(
            model_id
            for model_id in path_quality_review.verified_model_ids
            if model_id not in set(path_quality_consumer_blocked_model_ids)
        ),
        path_quality_blocked_model_ids=path_quality_consumer_blocked_model_ids,
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
