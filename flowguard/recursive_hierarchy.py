"""Recursive ModelMesh proof over finite model and test subtrees.

The older hierarchy and layered-proof helpers review one direct parent
boundary at a time.  This module provides the small recursive composition
kernel that joins those local proofs.  It never expands a global state
Cartesian product: each node consumes the exact terminal receipts of its
direct children and proves only its own typed boundary.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .contract_exhaustion import (
    CONTRACT_GENERATION_LOCAL_CARTESIAN,
    ContractProductSignature,
)
from .export import to_jsonable
from .model_authority import canonical_fingerprint
from .native_case_protocol import (
    NativeCaseProtocolError,
    NativeCaseVerification,
    NativeModelCaseContract,
    NativeModelCaseResult,
    verify_native_model_cases,
)


# This is a direct replacement of the original, self-reported recursive
# receipt.  The schema is deliberately advanced when the authority fields are
# added: an old receipt must never be silently interpreted as a current one.
RECURSIVE_HIERARCHY_SCHEMA = "flowguard.recursive_hierarchy.v2"
RECURSIVE_STATUS_PASSED = "passed"
RECURSIVE_STATUS_FAILED = "failed"
RECURSIVE_STATUS_STALE = "stale"
RECURSIVE_CLAIM_SCOPES = {
    "full",
    "release",
    "whole_domain",
    "whole-domain",
    "whole_system",
    "whole-system",
    "parent_confidence",
    "parent-confidence",
}


def _text(value: Any) -> str:
    """Normalize a scalar without manufacturing a missing authority value."""

    return " ".join(str(value or "").split())


def _authority_fingerprint(value: Any) -> str:
    """Read a fingerprint from a scalar or an authority-head object.

    The recursive API accepts the already-resolved head fingerprint as its
    canonical wire value.  Accepting an object with a ``fingerprint``
    attribute is only a convenience for callers that already loaded the
    authoritative ``ModelAuthorityHead``; the value stored in the identity is
    always the exact fingerprint string, never the object representation.
    """

    if isinstance(value, Mapping) and value.get("fingerprint"):
        value = value["fingerprint"]
    elif value is not None and not isinstance(value, (str, bytes)):
        candidate = getattr(value, "fingerprint", None)
        if candidate:
            value = candidate
    return str(value or "").strip()


def _ids(value: Sequence[str] | str | None) -> tuple[str, ...]:
    """Canonicalize an ordered representation of a set while retaining dupes.

    Duplicate ids are retained intentionally so the review can report the
    structural error instead of silently collapsing it into a passing set.
    Sorting makes the canonical fingerprint independent of declaration order.
    """

    if value is None:
        return ()
    if isinstance(value, str):
        value = (value,)
    return tuple(sorted(str(item).strip() for item in value))


def _strict_mapping(value: Any, name: str, fields: Sequence[str]) -> dict[str, Any]:
    """Load one current-schema mapping without aliases or unknown keys."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    expected = set(fields)
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if unknown:
            details.append(f"unknown={','.join(unknown)}")
        raise ValueError(f"{name} has invalid fields ({'; '.join(details)})")
    return dict(value)


def _wire_sequence(value: Any, name: str) -> tuple[Any, ...]:
    """Require an actual JSON array/tuple instead of iterating a string."""

    if isinstance(value, (str, bytes)) or not isinstance(value, SequenceABC):
        raise ValueError(f"{name} must be an array")
    return tuple(value)


def _wire_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{name} must be an object")
    return value


def _wire_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def descendant_universe_fingerprint(model_ids: Sequence[str]) -> str:
    """Return the one canonical fingerprint for a computed descendant set.

    The caller supplies only a sequence of ids; the hierarchy reviewer is the
    authority that computes which ids belong to a node.  The helper is public
    so a receipt producer and a test fixture can use the same wire algorithm
    without duplicating it.
    """

    return canonical_fingerprint(
        {"descendant_model_ids": list(_ids(model_ids))}
    )


# Explicit name for code that wants to make the derivation step visible.
derive_descendant_universe_fingerprint = descendant_universe_fingerprint


def _leaf_axis_fingerprint(
    leaf_model_id: str,
    axis_id: str,
    axis_kind: str,
    cases: Sequence[str],
) -> str:
    """Derive a content fingerprint for one finite leaf axis.

    The axis values, rather than a caller-provided count, are the authority for
    the denominator.  Keeping the derivation here gives recursive hierarchy
    producers and reviewers one canonical algorithm and avoids importing the
    layered-proof adapter into the recursive core.
    """

    return canonical_fingerprint(
        {
            "leaf_model_id": _text(leaf_model_id),
            "axis_id": _text(axis_id),
            "axis_kind": _text(axis_kind),
            "cases": list(_as_tuple(cases)),
        }
    )


def _leaf_canonical_product(
    input_cases: Sequence[str], state_cases: Sequence[str]
) -> tuple[str, ...]:
    """Return the deterministic Input x State cell denominator."""

    return tuple(
        f"{input_case}:{state_case}"
        for input_case in _as_tuple(input_cases)
        for state_case in _as_tuple(state_cases)
    )


def _coerce_leaf_product_signature(
    value: ContractProductSignature | Mapping[str, Any] | None,
) -> ContractProductSignature | None:
    """Normalize a typed leaf product without repairing supplied evidence."""

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
        "leaf_contract_product_signature must be a ContractProductSignature or mapping"
    )


def build_recursive_leaf_product_signature(
    leaf_model_id: str,
    input_axis_id: str,
    input_cases: Sequence[str],
    state_axis_id: str,
    state_cases: Sequence[str],
    *,
    interaction_group_id: str = "",
    partition_revision: str = "",
    shard_plan_fingerprint: str = "",
) -> ContractProductSignature:
    """Build the kernel-owned product signature for one recursive leaf.

    This is a producer helper, not a validation shortcut: a reviewer still
    recomputes the signature from the node's declared axes and compares every
    field before admitting a broad hierarchy claim.
    """

    model_id = _text(leaf_model_id)
    input_id = _text(input_axis_id)
    state_id = _text(state_axis_id)
    input_values = _as_tuple(input_cases)
    state_values = _as_tuple(state_cases)
    group_id = _text(interaction_group_id) or f"{model_id}:leaf"
    return ContractProductSignature(
        signature_id=f"contract_product:{model_id}:{group_id}",
        model_id=model_id,
        interaction_group_id=group_id,
        axis_ids=(input_id, state_id),
        axis_value_ids={input_id: input_values, state_id: state_values},
        expected_cardinality=len(input_values) * len(state_values),
        partition_revision=_text(partition_revision),
        generation_kind=CONTRACT_GENERATION_LOCAL_CARTESIAN,
        shard_plan_fingerprint=_text(shard_plan_fingerprint),
        axis_fingerprints={
            input_id: _leaf_axis_fingerprint(model_id, input_id, "input", input_values),
            state_id: _leaf_axis_fingerprint(model_id, state_id, "state", state_values),
        },
    )


_AUTHORITY_FIELDS = (
    "partition_fingerprint",
    "descendant_universe_fingerprint",
    "model_authority_head_fingerprint",
    "toolchain_fingerprint",
    "environment_fingerprint",
)


@dataclass(frozen=True)
class RecursiveModelNode:
    """One node in an arbitrary-depth model hierarchy."""

    model_id: str
    owner_id: str = ""
    parent_model_id: str = ""
    model_fingerprint: str = ""
    obligation_ids: tuple[str, ...] = ()
    child_model_ids: tuple[str, ...] = ()
    claim_scope: str = ""
    subtree_receipt_id: str = ""
    subtree_receipt_fingerprint: str = ""
    leaf_product_signature: str | ContractProductSignature | Mapping[str, Any] = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # A recursive leaf carries the finite boundary that produced its local
    # product.  These are explicit wire fields so a parent cannot treat an
    # opaque product id as a denominator.
    leaf_input_axis_id: str = ""
    leaf_state_axis_id: str = ""
    leaf_input_cases: tuple[str, ...] = ()
    leaf_state_cases: tuple[str, ...] = ()
    leaf_axis_fingerprints: Mapping[str, str] = field(default_factory=dict)
    leaf_canonical_product: tuple[str, ...] = ()
    leaf_contract_product_signature: ContractProductSignature | Mapping[str, Any] | None = None
    leaf_degenerate_boundary_disposition: str = ""
    leaf_scoped_exemption: str = ""
    # Canonical recursive-authority fields.  The older parent/child spellings
    # above remain readable for the existing ModelMesh adapters, but these
    # fields are the only names emitted into the current wire identity.
    structural_parent_id: str = ""
    direct_child_ids: tuple[str, ...] = ()
    partition_fingerprint: str = ""
    descendant_universe_fingerprint: str = ""
    model_authority_head_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    schema_version: str = RECURSIVE_HIERARCHY_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _text(self.model_id))
        object.__setattr__(self, "owner_id", _text(self.owner_id))
        declared_parent = _text(self.parent_model_id)
        canonical_parent = _text(self.structural_parent_id)
        if declared_parent and canonical_parent and declared_parent != canonical_parent:
            raise ValueError(
                "recursive node parent_model_id and structural_parent_id disagree"
            )
        canonical_parent = canonical_parent or declared_parent
        # Preserve the old attribute as a read-compatible projection while
        # ensuring every internal consumer sees one exact structural parent.
        object.__setattr__(self, "structural_parent_id", canonical_parent)
        object.__setattr__(self, "parent_model_id", canonical_parent)
        object.__setattr__(self, "model_fingerprint", _text(self.model_fingerprint))
        object.__setattr__(self, "obligation_ids", _as_tuple(self.obligation_ids))
        declared_children = _as_tuple(self.child_model_ids)
        canonical_children = _ids(self.direct_child_ids)
        if declared_children and canonical_children and _ids(declared_children) != canonical_children:
            raise ValueError(
                "recursive node child_model_ids and direct_child_ids disagree"
            )
        canonical_children = canonical_children or _ids(declared_children)
        object.__setattr__(self, "direct_child_ids", canonical_children)
        object.__setattr__(self, "child_model_ids", canonical_children)
        object.__setattr__(self, "claim_scope", _text(self.claim_scope))
        object.__setattr__(self, "subtree_receipt_id", _text(self.subtree_receipt_id))
        object.__setattr__(self, "subtree_receipt_fingerprint", _text(self.subtree_receipt_fingerprint))
        supplied_leaf_signature = self.leaf_contract_product_signature
        legacy_leaf_signature = self.leaf_product_signature
        if supplied_leaf_signature is None and isinstance(
            legacy_leaf_signature, (ContractProductSignature, Mapping)
        ):
            supplied_leaf_signature = _coerce_leaf_product_signature(legacy_leaf_signature)
            legacy_leaf_signature = (
                supplied_leaf_signature.fingerprint if supplied_leaf_signature else ""
            )
        elif supplied_leaf_signature is not None:
            supplied_leaf_signature = _coerce_leaf_product_signature(supplied_leaf_signature)
        compact_leaf_signature = _text(legacy_leaf_signature)
        if not compact_leaf_signature and supplied_leaf_signature is not None:
            compact_leaf_signature = supplied_leaf_signature.fingerprint
        object.__setattr__(self, "leaf_product_signature", compact_leaf_signature)
        object.__setattr__(self, "leaf_contract_product_signature", supplied_leaf_signature)
        for name in _AUTHORITY_FIELDS:
            object.__setattr__(self, name, _authority_fingerprint(getattr(self, name)))
        object.__setattr__(self, "schema_version", _text(self.schema_version))
        if self.schema_version != RECURSIVE_HIERARCHY_SCHEMA:
            raise ValueError(
                f"recursive model node schema must be {RECURSIVE_HIERARCHY_SCHEMA}"
            )
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "leaf_input_axis_id", _text(self.leaf_input_axis_id))
        object.__setattr__(self, "leaf_state_axis_id", _text(self.leaf_state_axis_id))
        object.__setattr__(self, "leaf_input_cases", _as_tuple(self.leaf_input_cases))
        object.__setattr__(self, "leaf_state_cases", _as_tuple(self.leaf_state_cases))
        object.__setattr__(
            self,
            "leaf_axis_fingerprints",
            {
                str(axis_id): str(fingerprint)
                for axis_id, fingerprint in sorted(
                    dict(self.leaf_axis_fingerprints).items(),
                    key=lambda item: str(item[0]),
                )
            },
        )
        object.__setattr__(self, "leaf_canonical_product", _as_tuple(self.leaf_canonical_product))
        object.__setattr__(
            self,
            "leaf_degenerate_boundary_disposition",
            _text(self.leaf_degenerate_boundary_disposition),
        )
        object.__setattr__(self, "leaf_scoped_exemption", _text(self.leaf_scoped_exemption))

    @property
    def is_leaf(self) -> bool:
        return not self.direct_child_ids

    def identity_payload(self) -> dict[str, Any]:
        """Return the complete node identity used by recursive authority."""

        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "owner_id": self.owner_id,
            "structural_parent_id": self.structural_parent_id,
            "direct_child_ids": list(self.direct_child_ids),
            "model_fingerprint": self.model_fingerprint,
            "obligation_ids": list(self.obligation_ids),
            "claim_scope": self.claim_scope,
            "subtree_receipt_id": self.subtree_receipt_id,
            "subtree_receipt_fingerprint": self.subtree_receipt_fingerprint,
            "leaf_product_signature": self.leaf_product_signature,
            "leaf_input_axis_id": self.leaf_input_axis_id,
            "leaf_state_axis_id": self.leaf_state_axis_id,
            "leaf_input_cases": list(self.leaf_input_cases),
            "leaf_state_cases": list(self.leaf_state_cases),
            "leaf_axis_fingerprints": dict(self.leaf_axis_fingerprints),
            "leaf_canonical_product": list(self.leaf_canonical_product),
            "leaf_contract_product_signature": (
                self.leaf_contract_product_signature.to_dict()
                if self.leaf_contract_product_signature is not None
                else None
            ),
            "leaf_degenerate_boundary_disposition": self.leaf_degenerate_boundary_disposition,
            "leaf_scoped_exemption": self.leaf_scoped_exemption,
            "partition_fingerprint": self.partition_fingerprint,
            "descendant_universe_fingerprint": self.descendant_universe_fingerprint,
            "model_authority_head_fingerprint": self.model_authority_head_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "RecursiveModelNode":
        data = _strict_mapping(
            value,
            "recursive_model_node",
            (
                "schema_version",
                "model_id",
                "owner_id",
                "structural_parent_id",
                "direct_child_ids",
                "model_fingerprint",
                "obligation_ids",
                "claim_scope",
                "subtree_receipt_id",
                "subtree_receipt_fingerprint",
                "leaf_product_signature",
                "partition_fingerprint",
                "descendant_universe_fingerprint",
                "model_authority_head_fingerprint",
                "toolchain_fingerprint",
                "environment_fingerprint",
                "metadata",
                "leaf_input_axis_id",
                "leaf_state_axis_id",
                "leaf_input_cases",
                "leaf_state_cases",
                "leaf_axis_fingerprints",
                "leaf_canonical_product",
                "leaf_contract_product_signature",
                "leaf_degenerate_boundary_disposition",
                "leaf_scoped_exemption",
                "fingerprint",
            ),
        )
        result = cls(
            model_id=data["model_id"],
            owner_id=data["owner_id"],
            structural_parent_id=data["structural_parent_id"],
            direct_child_ids=_wire_sequence(data["direct_child_ids"], "recursive_model_node.direct_child_ids"),
            model_fingerprint=data["model_fingerprint"],
            obligation_ids=_wire_sequence(data["obligation_ids"], "recursive_model_node.obligation_ids"),
            claim_scope=data["claim_scope"],
            subtree_receipt_id=data["subtree_receipt_id"],
            subtree_receipt_fingerprint=data["subtree_receipt_fingerprint"],
            leaf_product_signature=data["leaf_product_signature"],
            partition_fingerprint=data["partition_fingerprint"],
            descendant_universe_fingerprint=data["descendant_universe_fingerprint"],
            model_authority_head_fingerprint=data["model_authority_head_fingerprint"],
            toolchain_fingerprint=data["toolchain_fingerprint"],
            environment_fingerprint=data["environment_fingerprint"],
            metadata=_wire_mapping(data["metadata"], "recursive_model_node.metadata"),
            leaf_input_axis_id=data["leaf_input_axis_id"],
            leaf_state_axis_id=data["leaf_state_axis_id"],
            leaf_input_cases=_wire_sequence(
                data["leaf_input_cases"], "recursive_model_node.leaf_input_cases"
            ),
            leaf_state_cases=_wire_sequence(
                data["leaf_state_cases"], "recursive_model_node.leaf_state_cases"
            ),
            leaf_axis_fingerprints=_wire_mapping(
                data["leaf_axis_fingerprints"],
                "recursive_model_node.leaf_axis_fingerprints",
            ),
            leaf_canonical_product=_wire_sequence(
                data["leaf_canonical_product"],
                "recursive_model_node.leaf_canonical_product",
            ),
            leaf_contract_product_signature=(
                None
                if data["leaf_contract_product_signature"] is None
                else _coerce_leaf_product_signature(
                    _wire_mapping(
                        data["leaf_contract_product_signature"],
                        "recursive_model_node.leaf_contract_product_signature",
                    )
                )
            ),
            leaf_degenerate_boundary_disposition=data[
                "leaf_degenerate_boundary_disposition"
            ],
            leaf_scoped_exemption=data["leaf_scoped_exemption"],
            schema_version=data["schema_version"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ValueError("stale recursive model node fingerprint")
        return result


@dataclass(frozen=True)
class VerifiedSubtreeReceipt:
    """Immutable terminal result consumed by a parent node.

    ``status`` and ``current`` are not accepted in isolation.  Verification
    requires the canonical identity fingerprint plus the exact model, owner,
    parent, scope, obligation, and direct-child receipt set.
    """

    receipt_id: str
    model_id: str
    owner_id: str
    parent_model_id: str = ""
    claim_scope: str = "full"
    model_fingerprint: str = ""
    obligation_ids: tuple[str, ...] = ()
    child_receipt_ids: tuple[str, ...] = ()
    descendant_model_ids: tuple[str, ...] = ()
    status: str = RECURSIVE_STATUS_PASSED
    current: bool = True
    terminal: bool = True
    fingerprint: str = ""
    result_fingerprint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = RECURSIVE_HIERARCHY_SCHEMA
    # Canonical authority bindings.  ``parent_model_id`` and
    # ``child_receipt_ids`` remain read-compatible projections for the two
    # existing adapters; the current identity uses the structural spellings
    # below and recursive review requires all of them.
    structural_parent_id: str = ""
    direct_child_ids: tuple[str, ...] = ()
    partition_fingerprint: str = ""
    descendant_universe_fingerprint: str = ""
    model_authority_head_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    # Leaf receipts repeat the kernel-owned finite boundary so the parent
    # consumes a receipt whose denominator is independently checkable. For a
    # non-leaf receipt these fields remain empty.
    leaf_product_signature: str = ""
    leaf_input_axis_id: str = ""
    leaf_state_axis_id: str = ""
    leaf_input_cases: tuple[str, ...] = ()
    leaf_state_cases: tuple[str, ...] = ()
    leaf_axis_fingerprints: Mapping[str, str] = field(default_factory=dict)
    leaf_canonical_product: tuple[str, ...] = ()
    leaf_contract_product_signature: ContractProductSignature | Mapping[str, Any] | None = None
    leaf_degenerate_boundary_disposition: str = ""
    leaf_scoped_exemption: str = ""
    # A parent must bind each direct child receipt to the exact content that it
    # consumed.  The id alone is not sufficient: an immutable receipt id can be
    # replayed with a different payload by a malformed/caller-authored plan.
    # This field is appended to preserve existing keyword/positional callers;
    # current-schema serialization below makes it mandatory on the wire.
    child_receipt_fingerprints: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "receipt_id",
            "model_id",
            "owner_id",
            "parent_model_id",
            "claim_scope",
            "model_fingerprint",
            "status",
            "result_fingerprint",
            "schema_version",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        declared_parent = _text(self.parent_model_id)
        canonical_parent = _text(self.structural_parent_id)
        if declared_parent and canonical_parent and declared_parent != canonical_parent:
            raise ValueError(
                "recursive receipt parent_model_id and structural_parent_id disagree"
            )
        canonical_parent = canonical_parent or declared_parent
        object.__setattr__(self, "structural_parent_id", canonical_parent)
        object.__setattr__(self, "parent_model_id", canonical_parent)
        object.__setattr__(self, "obligation_ids", _as_tuple(self.obligation_ids))
        object.__setattr__(self, "child_receipt_ids", _ids(self.child_receipt_ids))
        object.__setattr__(self, "direct_child_ids", _ids(self.direct_child_ids))
        object.__setattr__(self, "descendant_model_ids", _ids(self.descendant_model_ids))
        object.__setattr__(
            self,
            "child_receipt_fingerprints",
            {
                str(receipt_id): str(fingerprint).strip()
                for receipt_id, fingerprint in sorted(
                    dict(self.child_receipt_fingerprints).items(),
                    key=lambda item: str(item[0]),
                )
            },
        )
        # These are wire-level authority claims, not truthy display values.
        # Coercing strings such as ``"false"`` to ``True`` would let a
        # caller-authored receipt silently upgrade stale/non-terminal
        # evidence.  Keep the current schema strict and reject anything that
        # is not an actual JSON boolean.
        object.__setattr__(self, "current", _wire_bool(self.current, "recursive_subtree_receipt.current"))
        object.__setattr__(self, "terminal", _wire_bool(self.terminal, "recursive_subtree_receipt.terminal"))
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "leaf_product_signature", _text(self.leaf_product_signature))
        object.__setattr__(self, "leaf_input_axis_id", _text(self.leaf_input_axis_id))
        object.__setattr__(self, "leaf_state_axis_id", _text(self.leaf_state_axis_id))
        object.__setattr__(self, "leaf_input_cases", _as_tuple(self.leaf_input_cases))
        object.__setattr__(self, "leaf_state_cases", _as_tuple(self.leaf_state_cases))
        object.__setattr__(
            self,
            "leaf_axis_fingerprints",
            {
                str(axis_id): str(fingerprint)
                for axis_id, fingerprint in sorted(
                    dict(self.leaf_axis_fingerprints).items(),
                    key=lambda item: str(item[0]),
                )
            },
        )
        object.__setattr__(self, "leaf_canonical_product", _as_tuple(self.leaf_canonical_product))
        object.__setattr__(
            self,
            "leaf_contract_product_signature",
            _coerce_leaf_product_signature(self.leaf_contract_product_signature),
        )
        if not self.leaf_product_signature and self.leaf_contract_product_signature is not None:
            object.__setattr__(
                self,
                "leaf_product_signature",
                self.leaf_contract_product_signature.fingerprint,
            )
        object.__setattr__(
            self,
            "leaf_degenerate_boundary_disposition",
            _text(self.leaf_degenerate_boundary_disposition),
        )
        object.__setattr__(self, "leaf_scoped_exemption", _text(self.leaf_scoped_exemption))
        for name in _AUTHORITY_FIELDS:
            object.__setattr__(self, name, _authority_fingerprint(getattr(self, name)))
        if self.schema_version != RECURSIVE_HIERARCHY_SCHEMA:
            raise ValueError(
                f"verified subtree receipt schema must be {RECURSIVE_HIERARCHY_SCHEMA}"
            )
        supplied = _text(self.fingerprint)
        object.__setattr__(
            self,
            "fingerprint",
            supplied or canonical_fingerprint(self.identity_payload()),
        )

    @property
    def receipt_fingerprint(self) -> str:
        return self.fingerprint

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "model_id": self.model_id,
            "owner_id": self.owner_id,
            "structural_parent_id": self.structural_parent_id,
            "direct_child_ids": list(self.direct_child_ids),
            "claim_scope": self.claim_scope,
            "model_fingerprint": self.model_fingerprint,
            "obligation_ids": list(self.obligation_ids),
            "child_receipt_ids": list(self.child_receipt_ids),
            "child_receipt_fingerprints": dict(self.child_receipt_fingerprints),
            "descendant_model_ids": list(self.descendant_model_ids),
            "partition_fingerprint": self.partition_fingerprint,
            "descendant_universe_fingerprint": self.descendant_universe_fingerprint,
            "model_authority_head_fingerprint": self.model_authority_head_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "leaf_product_signature": self.leaf_product_signature,
            "leaf_input_axis_id": self.leaf_input_axis_id,
            "leaf_state_axis_id": self.leaf_state_axis_id,
            "leaf_input_cases": list(self.leaf_input_cases),
            "leaf_state_cases": list(self.leaf_state_cases),
            "leaf_axis_fingerprints": dict(self.leaf_axis_fingerprints),
            "leaf_canonical_product": list(self.leaf_canonical_product),
            "leaf_contract_product_signature": (
                self.leaf_contract_product_signature.to_dict()
                if self.leaf_contract_product_signature is not None
                else None
            ),
            "leaf_degenerate_boundary_disposition": self.leaf_degenerate_boundary_disposition,
            "leaf_scoped_exemption": self.leaf_scoped_exemption,
            "status": self.status,
            "current": self.current,
            "terminal": self.terminal,
            "result_fingerprint": self.result_fingerprint,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    def is_verified(
        self,
        *,
        require_authority: bool = False,
        expected_model_authority_head_fingerprint: str = "",
    ) -> bool:
        """Return whether this receipt is a self-consistent terminal result.

        The two older direct-boundary adapters still use the base structural
        check, which intentionally does not invent recursive authority data.
        ``review_recursive_hierarchy`` always passes ``require_authority=True``
        and supplies the current head.  Thus a recursive parent cannot be
        closed by a minimal local receipt, while an unrelated adapter does not
        get a fabricated partition or head through this class.
        """

        expected_head = _authority_fingerprint(
            expected_model_authority_head_fingerprint
        )
        authority_complete = all(
            bool(getattr(self, field_name)) for field_name in _AUTHORITY_FIELDS
        )
        child_receipt_ids = tuple(self.child_receipt_ids)
        child_receipt_fingerprints = dict(self.child_receipt_fingerprints)
        direct_child_ids = tuple(self.direct_child_ids)
        # A leaf has no child binding.  Every non-leaf must carry one
        # non-empty fingerprint for each (and only each) direct child receipt.
        # This check lives on the receipt itself as well as in the hierarchy
        # reviewer so adapters cannot promote a bare ``passed`` object.
        child_binding_complete = (
            (
                not direct_child_ids
                and not child_receipt_ids
                and not child_receipt_fingerprints
            )
            or (
                bool(direct_child_ids)
                and all(direct_child_ids)
                and len(direct_child_ids) == len(set(direct_child_ids))
                and len(child_receipt_ids) == len(direct_child_ids)
                and len(child_receipt_ids) == len(set(child_receipt_ids))
                and all(child_receipt_ids)
                and set(child_receipt_fingerprints) == set(child_receipt_ids)
                and all(child_receipt_fingerprints.values())
            )
        )
        return bool(
            self.schema_version == RECURSIVE_HIERARCHY_SCHEMA
            and self.receipt_id
            and self.model_id
            and self.owner_id
            and self.model_fingerprint
            and self.claim_scope
            and self.status == RECURSIVE_STATUS_PASSED
            and self.current
            and self.terminal
            and self.fingerprint == canonical_fingerprint(self.identity_payload())
            and child_binding_complete
            and (not require_authority or authority_complete)
            and (
                not expected_head
                or self.model_authority_head_fingerprint == expected_head
            )
        )

    def is_authority_verified(
        self, *, expected_model_authority_head_fingerprint: str = ""
    ) -> bool:
        """Strict recursive-authority verification used by post-order review."""

        return self.is_verified(
            require_authority=True,
            expected_model_authority_head_fingerprint=(
                expected_model_authority_head_fingerprint
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "VerifiedSubtreeReceipt":
        data = _strict_mapping(
            value,
            "verified_subtree_receipt",
            (
                "schema_version",
                "receipt_id",
                "model_id",
                "owner_id",
                "structural_parent_id",
                "direct_child_ids",
                "claim_scope",
                "model_fingerprint",
                "obligation_ids",
                "child_receipt_ids",
                "child_receipt_fingerprints",
                "descendant_model_ids",
                "partition_fingerprint",
                "descendant_universe_fingerprint",
                "model_authority_head_fingerprint",
                "toolchain_fingerprint",
                "environment_fingerprint",
                "leaf_product_signature",
                "leaf_input_axis_id",
                "leaf_state_axis_id",
                "leaf_input_cases",
                "leaf_state_cases",
                "leaf_axis_fingerprints",
                "leaf_canonical_product",
                "leaf_contract_product_signature",
                "leaf_degenerate_boundary_disposition",
                "leaf_scoped_exemption",
                "status",
                "current",
                "terminal",
                "result_fingerprint",
                "metadata",
                "fingerprint",
            ),
        )
        result = cls(
            receipt_id=data["receipt_id"],
            model_id=data["model_id"],
            owner_id=data["owner_id"],
            structural_parent_id=data["structural_parent_id"],
            direct_child_ids=_wire_sequence(data["direct_child_ids"], "verified_subtree_receipt.direct_child_ids"),
            claim_scope=data["claim_scope"],
            model_fingerprint=data["model_fingerprint"],
            obligation_ids=_wire_sequence(data["obligation_ids"], "verified_subtree_receipt.obligation_ids"),
            child_receipt_ids=_wire_sequence(data["child_receipt_ids"], "verified_subtree_receipt.child_receipt_ids"),
            child_receipt_fingerprints=_wire_mapping(
                data["child_receipt_fingerprints"],
                "verified_subtree_receipt.child_receipt_fingerprints",
            ),
            descendant_model_ids=_wire_sequence(data["descendant_model_ids"], "verified_subtree_receipt.descendant_model_ids"),
            partition_fingerprint=data["partition_fingerprint"],
            descendant_universe_fingerprint=data["descendant_universe_fingerprint"],
            model_authority_head_fingerprint=data["model_authority_head_fingerprint"],
            toolchain_fingerprint=data["toolchain_fingerprint"],
            environment_fingerprint=data["environment_fingerprint"],
            leaf_product_signature=data["leaf_product_signature"],
            leaf_input_axis_id=data["leaf_input_axis_id"],
            leaf_state_axis_id=data["leaf_state_axis_id"],
            leaf_input_cases=_wire_sequence(
                data["leaf_input_cases"], "verified_subtree_receipt.leaf_input_cases"
            ),
            leaf_state_cases=_wire_sequence(
                data["leaf_state_cases"], "verified_subtree_receipt.leaf_state_cases"
            ),
            leaf_axis_fingerprints=_wire_mapping(
                data["leaf_axis_fingerprints"],
                "verified_subtree_receipt.leaf_axis_fingerprints",
            ),
            leaf_canonical_product=_wire_sequence(
                data["leaf_canonical_product"],
                "verified_subtree_receipt.leaf_canonical_product",
            ),
            leaf_contract_product_signature=(
                None
                if data["leaf_contract_product_signature"] is None
                else _coerce_leaf_product_signature(
                    _wire_mapping(
                        data["leaf_contract_product_signature"],
                        "verified_subtree_receipt.leaf_contract_product_signature",
                    )
                )
            ),
            leaf_degenerate_boundary_disposition=data[
                "leaf_degenerate_boundary_disposition"
            ],
            leaf_scoped_exemption=data["leaf_scoped_exemption"],
            status=data["status"],
            current=_wire_bool(data["current"], "verified_subtree_receipt.current"),
            terminal=_wire_bool(data["terminal"], "verified_subtree_receipt.terminal"),
            result_fingerprint=data["result_fingerprint"],
            metadata=_wire_mapping(data["metadata"], "verified_subtree_receipt.metadata"),
            schema_version=data["schema_version"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ValueError("stale verified subtree receipt fingerprint")
        return result


@dataclass(frozen=True)
class RecursiveHierarchyPlan:
    """A complete rooted tree whose local proofs compose bottom-up."""

    hierarchy_id: str
    root_model_id: str
    nodes: tuple[RecursiveModelNode | Mapping[str, Any], ...] = ()
    receipts: tuple[VerifiedSubtreeReceipt | Mapping[str, Any], ...] = ()
    claim_scope: str = "full"
    strict: bool | None = None
    allow_scoped_leaf_exemptions: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    model_authority_head_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    schema_version: str = RECURSIVE_HIERARCHY_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "hierarchy_id", str(self.hierarchy_id))
        object.__setattr__(self, "root_model_id", str(self.root_model_id))
        object.__setattr__(
            self,
            "nodes",
            tuple(
                node
                if isinstance(node, RecursiveModelNode)
                else RecursiveModelNode.from_dict(node)
                for node in self.nodes
            ),
        )
        object.__setattr__(
            self,
            "receipts",
            tuple(
                receipt
                if isinstance(receipt, VerifiedSubtreeReceipt)
                else VerifiedSubtreeReceipt.from_dict(receipt)
                for receipt in self.receipts
            ),
        )
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        if self.strict is not None:
            object.__setattr__(
                self,
                "strict",
                _wire_bool(self.strict, "recursive_hierarchy_plan.strict"),
            )
        object.__setattr__(
            self,
            "allow_scoped_leaf_exemptions",
            _wire_bool(
                self.allow_scoped_leaf_exemptions,
                "recursive_hierarchy_plan.allow_scoped_leaf_exemptions",
            ),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(
            self,
            "model_authority_head_fingerprint",
            _authority_fingerprint(self.model_authority_head_fingerprint),
        )
        object.__setattr__(
            self,
            "toolchain_fingerprint",
            _authority_fingerprint(self.toolchain_fingerprint),
        )
        object.__setattr__(
            self,
            "environment_fingerprint",
            _authority_fingerprint(self.environment_fingerprint),
        )
        object.__setattr__(self, "schema_version", _text(self.schema_version))
        if self.schema_version != RECURSIVE_HIERARCHY_SCHEMA:
            raise ValueError(
                f"recursive hierarchy plan schema must be {RECURSIVE_HIERARCHY_SCHEMA}"
            )

    def is_strict(self) -> bool:
        # A caller may explicitly request strict checking for a routine
        # review, but cannot downgrade a broad claim with ``strict=False``.
        # This keeps full/release/whole-domain admission fail-closed.
        return bool(self.strict) or self.claim_scope in RECURSIVE_CLAIM_SCOPES

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hierarchy_id": self.hierarchy_id,
            "root_model_id": self.root_model_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "claim_scope": self.claim_scope,
            "strict": self.is_strict(),
            "allow_scoped_leaf_exemptions": self.allow_scoped_leaf_exemptions,
            "model_authority_head_fingerprint": self.model_authority_head_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "RecursiveHierarchyPlan":
        data = _strict_mapping(
            value,
            "recursive_hierarchy_plan",
            (
                "schema_version",
                "hierarchy_id",
                "root_model_id",
                "nodes",
                "receipts",
                "claim_scope",
                "strict",
                "allow_scoped_leaf_exemptions",
                "model_authority_head_fingerprint",
                "toolchain_fingerprint",
                "environment_fingerprint",
                "metadata",
                "fingerprint",
            ),
        )
        result = cls(
            hierarchy_id=data["hierarchy_id"],
            root_model_id=data["root_model_id"],
            nodes=tuple(
                RecursiveModelNode.from_dict(item)
                for item in _wire_sequence(data["nodes"], "recursive_hierarchy_plan.nodes")
            ),
            receipts=tuple(
                VerifiedSubtreeReceipt.from_dict(item)
                for item in _wire_sequence(data["receipts"], "recursive_hierarchy_plan.receipts")
            ),
            claim_scope=data["claim_scope"],
            strict=_wire_bool(data["strict"], "recursive_hierarchy_plan.strict"),
            allow_scoped_leaf_exemptions=_wire_bool(
                data["allow_scoped_leaf_exemptions"],
                "recursive_hierarchy_plan.allow_scoped_leaf_exemptions",
            ),
            metadata=_wire_mapping(data["metadata"], "recursive_hierarchy_plan.metadata"),
            model_authority_head_fingerprint=data["model_authority_head_fingerprint"],
            toolchain_fingerprint=data["toolchain_fingerprint"],
            environment_fingerprint=data["environment_fingerprint"],
            schema_version=data["schema_version"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ValueError("stale recursive hierarchy plan fingerprint")
        return result


@dataclass(frozen=True)
class RecursiveHierarchyFinding:
    code: str
    message: str
    severity: str = "blocker"
    model_id: str = ""
    receipt_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "model_id": self.model_id,
            "receipt_id": self.receipt_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class RecursiveHierarchyReport:
    ok: bool
    hierarchy_id: str
    root_model_id: str
    decision: str
    max_depth: int = 0
    leaf_model_ids: tuple[str, ...] = ()
    verified_receipt_ids: tuple[str, ...] = ()
    findings: tuple[RecursiveHierarchyFinding, ...] = ()
    terminal_receipt: VerifiedSubtreeReceipt | None = None
    summary: str = ""
    # Structural review and producer execution are separate claims.  The
    # original recursive API remains compatible (and can still be used for a
    # cheap structure-only pass), while callers that provide native case
    # results get an explicit, non-inferred execution projection.
    execution_verified_receipt_ids: tuple[str, ...] = ()
    native_case_verifications: Mapping[str, NativeCaseVerification] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "hierarchy_id", str(self.hierarchy_id))
        object.__setattr__(self, "root_model_id", str(self.root_model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "max_depth", int(self.max_depth))
        object.__setattr__(self, "leaf_model_ids", _as_tuple(self.leaf_model_ids))
        object.__setattr__(self, "verified_receipt_ids", _as_tuple(self.verified_receipt_ids))
        object.__setattr__(
            self,
            "execution_verified_receipt_ids",
            _as_tuple(self.execution_verified_receipt_ids),
        )
        object.__setattr__(
            self,
            "native_case_verifications",
            dict(self.native_case_verifications),
        )
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: recursive_hierarchy root={self.root_model_id} depth={self.max_depth} findings={len(self.findings)}",
            )

    @property
    def terminal_receipt_id(self) -> str:
        return self.terminal_receipt.receipt_id if self.terminal_receipt else ""

    @property
    def execution_verified(self) -> bool:
        """Whether this report proves execution of the whole requested tree.

        ``execution_verified_receipt_ids`` is a progress set: a child can be
        current while its root or a sibling is blocked.  The public summary
        therefore requires a clean report and the root's own terminal receipt.
        """

        if not self.ok or any(
            finding.severity == "blocker" for finding in self.findings
        ):
            return False
        terminal = self.terminal_receipt
        if terminal is None or terminal.model_id != self.root_model_id:
            return False
        if terminal.receipt_id not in set(self.execution_verified_receipt_ids):
            return False
        # The receipt-set is only a progress projection.  A caller must not
        # be able to manufacture the public root summary by copying a root
        # receipt id into that set: the root owner still needs an independently
        # verified native execution result from this invocation.
        root_verification = self.native_case_verifications.get(terminal.owner_id)
        return bool(root_verification is not None and root_verification.ok)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "hierarchy_id": self.hierarchy_id,
            "root_model_id": self.root_model_id,
            "decision": self.decision,
            "max_depth": self.max_depth,
            "leaf_model_ids": list(self.leaf_model_ids),
            "verified_receipt_ids": list(self.verified_receipt_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "terminal_receipt": (
                self.terminal_receipt.to_dict() if self.terminal_receipt else None
            ),
            "execution_verified_receipt_ids": list(
                self.execution_verified_receipt_ids
            ),
            "execution_verified": self.execution_verified,
            "native_case_verifications": {
                owner_id: verification.to_dict()
                for owner_id, verification in sorted(
                    self.native_case_verifications.items()
                )
            },
            "summary": self.summary,
        }

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard recursive hierarchy ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"hierarchy: {self.hierarchy_id}",
            f"root: {self.root_model_id}",
            f"depth: {self.max_depth}",
            f"leaves: {len(self.leaf_model_ids)}",
            f"verified_receipts: {len(self.verified_receipt_ids)}",
            f"execution_verified_receipts: {len(self.execution_verified_receipt_ids)}",
            f"decision: {self.decision}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(("", f"finding: {finding.code}", f"model: {finding.model_id or '(none)'}", f"message: {finding.message}"))
        return "\n".join(lines)


def _finding(
    code: str,
    message: str,
    *,
    severity: str = "blocker",
    model_id: str = "",
    receipt_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> RecursiveHierarchyFinding:
    return RecursiveHierarchyFinding(
        code,
        message,
        severity=severity,
        model_id=model_id,
        receipt_id=receipt_id,
        metadata=metadata or {},
    )


def _receipt_for_node(
    node: RecursiveModelNode,
    receipts_by_id: Mapping[str, VerifiedSubtreeReceipt],
) -> VerifiedSubtreeReceipt | None:
    receipt_id = node.subtree_receipt_id or f"subtree:{node.model_id}"
    return receipts_by_id.get(receipt_id)


def _declared_receipt_id(
    model_id: str,
    nodes_by_id: Mapping[str, RecursiveModelNode],
) -> str:
    """Return the child node's declared receipt identity.

    A parent proves that it consumed the receipt *declared by each child
    node*, not whichever receipt happens to be present in the receipt store.
    Resolving this from the node keeps custom/content-addressed receipt IDs
    intact and still gives a deterministic fallback for a missing child
    declaration so the structural finding remains visible.
    """

    child = nodes_by_id.get(model_id)
    if child is None:
        return f"subtree:{model_id}"
    return child.subtree_receipt_id or f"subtree:{model_id}"


def _leaf_product_findings(
    plan: RecursiveHierarchyPlan,
    node: RecursiveModelNode,
    receipt: VerifiedSubtreeReceipt | None,
) -> list[RecursiveHierarchyFinding]:
    """Validate a strict recursive leaf's kernel-owned finite denominator.

    The hierarchy reviewer computes the product from the concrete input/state
    axes.  Node and receipt declarations are compared to that result; neither
    a compact signature string nor a caller-supplied list can become the
    denominator by assertion alone.
    """

    if not node.is_leaf or not plan.is_strict():
        return []

    findings: list[RecursiveHierarchyFinding] = []
    disposition = node.leaf_degenerate_boundary_disposition
    degenerate_allowed = bool(
        plan.allow_scoped_leaf_exemptions
        and disposition.startswith("degenerate:")
        and node.leaf_scoped_exemption
    )
    if not node.leaf_input_cases or not node.leaf_state_cases:
        if degenerate_allowed:
            findings.append(
                _finding(
                    "leaf_degenerate_boundary_scoped",
                    "strict recursive leaf uses an explicit scoped degenerate boundary disposition",
                    model_id=node.model_id,
                    metadata={
                        "disposition": disposition,
                        "scoped_exemption": node.leaf_scoped_exemption,
                    },
                )
            )
        else:
            if not node.leaf_input_cases:
                findings.append(
                    _finding(
                        "leaf_input_axis_missing",
                        "strict recursive leaf has no finite input axis",
                        model_id=node.model_id,
                    )
                )
            if not node.leaf_state_cases:
                findings.append(
                    _finding(
                        "leaf_state_axis_missing",
                        "strict recursive leaf has no finite state axis",
                        model_id=node.model_id,
                    )
                )
            findings.append(
                _finding(
                    "leaf_denominator_missing",
                    "strict recursive leaf has no kernel-derived finite Input x State denominator",
                    model_id=node.model_id,
                )
            )
        return findings

    input_axis_id = node.leaf_input_axis_id
    state_axis_id = node.leaf_state_axis_id
    if not input_axis_id:
        findings.append(
            _finding(
                "leaf_input_axis_id_missing",
                "strict recursive leaf input axis has no stable id",
                model_id=node.model_id,
            )
        )
    if not state_axis_id:
        findings.append(
            _finding(
                "leaf_state_axis_id_missing",
                "strict recursive leaf state axis has no stable id",
                model_id=node.model_id,
            )
        )
    if input_axis_id and state_axis_id and input_axis_id == state_axis_id:
        findings.append(
            _finding(
                "leaf_axis_duplicate",
                "strict recursive leaf input and state axes must be distinct",
                model_id=node.model_id,
                metadata={"axis_id": input_axis_id},
            )
        )

    expected_axis_fingerprints = {
        input_axis_id: _leaf_axis_fingerprint(
            node.model_id, input_axis_id, "input", node.leaf_input_cases
        ),
        state_axis_id: _leaf_axis_fingerprint(
            node.model_id, state_axis_id, "state", node.leaf_state_cases
        ),
    }
    actual_axis_fingerprints = dict(node.leaf_axis_fingerprints)
    for axis_id, expected in expected_axis_fingerprints.items():
        if not axis_id:
            continue
        actual = str(actual_axis_fingerprints.get(axis_id, ""))
        if not actual:
            findings.append(
                _finding(
                    "leaf_axis_fingerprint_missing",
                    "strict recursive leaf axis has no content fingerprint",
                    model_id=node.model_id,
                    metadata={"axis_id": axis_id, "expected": expected},
                )
            )
        elif actual != expected:
            findings.append(
                _finding(
                    "leaf_axis_fingerprint_mismatch",
                    "strict recursive leaf axis fingerprint does not match its finite cases",
                    model_id=node.model_id,
                    metadata={"axis_id": axis_id, "expected": expected, "actual": actual},
                )
            )
    expected_axis_ids = {axis_id for axis_id in (input_axis_id, state_axis_id) if axis_id}
    foreign_axis_ids = tuple(sorted(set(actual_axis_fingerprints) - expected_axis_ids))
    if foreign_axis_ids:
        findings.append(
            _finding(
                "leaf_axis_foreign",
                "strict recursive leaf declares an axis outside its input/state boundary",
                model_id=node.model_id,
                metadata={"axis_ids": foreign_axis_ids},
            )
        )

    expected_product = _leaf_canonical_product(
        node.leaf_input_cases, node.leaf_state_cases
    )
    if not node.leaf_canonical_product:
        findings.append(
            _finding(
                "leaf_denominator_missing",
                "strict recursive leaf does not carry its kernel-derived cell denominator",
                model_id=node.model_id,
                metadata={"expected": expected_product},
            )
        )
    elif tuple(node.leaf_canonical_product) != expected_product:
        findings.append(
            _finding(
                "leaf_denominator_mismatch",
                "strict recursive leaf denominator differs from Input x State axes",
                model_id=node.model_id,
                metadata={
                    "expected": expected_product,
                    "actual": node.leaf_canonical_product,
                },
            )
        )

    metadata = node.metadata if isinstance(node.metadata, Mapping) else {}
    expected_signature = build_recursive_leaf_product_signature(
        node.model_id,
        input_axis_id,
        node.leaf_input_cases,
        state_axis_id,
        node.leaf_state_cases,
        interaction_group_id=str(metadata.get("interaction_group_id", "")),
        partition_revision=str(metadata.get("partition_revision", "")),
        shard_plan_fingerprint=str(metadata.get("shard_plan_fingerprint", "")),
    )
    actual_signature = node.leaf_contract_product_signature
    if actual_signature is None:
        findings.append(
            _finding(
                "leaf_product_signature_missing",
                "strict recursive leaf has no typed ContractProductSignature",
                model_id=node.model_id,
                metadata={"expected": expected_signature.to_dict()},
            )
        )
    else:
        if not actual_signature.is_self_consistent():
            findings.append(
                _finding(
                    "leaf_product_signature_invalid",
                    "strict recursive leaf product signature is not self-consistent",
                    model_id=node.model_id,
                    metadata={"actual": actual_signature.to_dict()},
                )
            )
        if actual_signature.identity_payload() != expected_signature.identity_payload():
            findings.append(
                _finding(
                    "leaf_product_signature_mismatch",
                    "strict recursive leaf product signature differs from the kernel-derived axes",
                    model_id=node.model_id,
                    metadata={
                        "expected": expected_signature.to_dict(),
                        "actual": actual_signature.to_dict(),
                    },
                )
            )
    if node.leaf_product_signature != expected_signature.fingerprint:
        findings.append(
            _finding(
                "leaf_product_signature_mismatch",
                "strict recursive leaf compact product signature is not the typed product fingerprint",
                model_id=node.model_id,
                metadata={
                    "expected": expected_signature.fingerprint,
                    "actual": node.leaf_product_signature,
                },
            )
        )

    if receipt is None:
        return findings

    # A leaf receipt is independently consumable evidence.  It must repeat
    # the exact boundary fields from the node; a parent cannot accept a node
    # declaration while the terminal receipt carries a different denominator.
    receipt_fields = (
        "leaf_product_signature",
        "leaf_input_axis_id",
        "leaf_state_axis_id",
        "leaf_input_cases",
        "leaf_state_cases",
        "leaf_axis_fingerprints",
        "leaf_canonical_product",
        "leaf_degenerate_boundary_disposition",
        "leaf_scoped_exemption",
    )
    for field_name in receipt_fields:
        expected_value = getattr(node, field_name)
        actual_value = getattr(receipt, field_name)
        if field_name in {
            "leaf_input_cases",
            "leaf_state_cases",
            "leaf_canonical_product",
        }:
            expected_value = _as_tuple(expected_value)
            actual_value = _as_tuple(actual_value)
        elif field_name == "leaf_axis_fingerprints":
            expected_value = dict(expected_value)
            actual_value = dict(actual_value)
        else:
            expected_value = str(expected_value)
            actual_value = str(actual_value)
        if actual_value != expected_value:
            findings.append(
                _finding(
                    f"leaf_receipt_{field_name}_mismatch",
                    "leaf receipt does not carry the exact node finite-boundary declaration",
                    model_id=node.model_id,
                    receipt_id=receipt.receipt_id,
                    metadata={"expected": expected_value, "actual": actual_value},
                )
            )
    receipt_signature = receipt.leaf_contract_product_signature
    if receipt_signature is None:
        findings.append(
            _finding(
                "leaf_receipt_product_signature_missing",
                "leaf terminal receipt has no typed product signature",
                model_id=node.model_id,
                receipt_id=receipt.receipt_id,
            )
        )
    elif not receipt_signature.is_self_consistent():
        findings.append(
            _finding(
                "leaf_receipt_product_signature_invalid",
                "leaf terminal receipt product signature is not self-consistent",
                model_id=node.model_id,
                receipt_id=receipt.receipt_id,
            )
        )
    elif receipt_signature.identity_payload() != expected_signature.identity_payload():
        findings.append(
            _finding(
                "leaf_receipt_product_signature_mismatch",
                "leaf terminal receipt product signature differs from the kernel-derived product",
                model_id=node.model_id,
                receipt_id=receipt.receipt_id,
                metadata={
                    "expected": expected_signature.to_dict(),
                    "actual": receipt_signature.to_dict(),
                },
            )
        )
    return findings


def is_verified_subtree_receipt(value: Any) -> bool:
    """Return ``True`` only for a canonical :class:`VerifiedSubtreeReceipt`.

    ModelMesh and layered-proof adapters may receive JSON mappings instead of
    the dataclass itself.  Reconstructing the typed receipt here makes the
    canonical fingerprint/schema check identical across all three surfaces;
    a generic object that merely reports ``passed``/``current`` is therefore
    never accepted as a subtree proof.
    """

    if isinstance(value, VerifiedSubtreeReceipt):
        return value.is_verified()
    if isinstance(value, Mapping):
        try:
            return VerifiedSubtreeReceipt.from_dict(value).is_verified()
        except (TypeError, ValueError):
            return False
    return False


def _group_native_rows(
    rows: Sequence[NativeModelCaseContract | NativeModelCaseResult]
    | Mapping[str, Sequence[NativeModelCaseContract | NativeModelCaseResult]]
    | None,
    *,
    row_type: type[NativeModelCaseContract] | type[NativeModelCaseResult],
) -> tuple[dict[str, tuple[Any, ...]], tuple[str, ...]]:
    """Group typed native rows by their declared owner without inference.

    A mapping is accepted as a convenience for callers that already partition
    rows by owner, but the row's own ``owner_id`` remains authoritative.  A
    mismatched mapping key is returned as a finding rather than silently
    moving the row to the key's owner.
    """

    if rows is None:
        return {}, ()
    groups: dict[str, list[Any]] = {}
    findings: list[str] = []
    if isinstance(rows, MappingABC):
        for declared_owner, raw_rows in rows.items():
            if isinstance(raw_rows, (str, bytes)) or not isinstance(
                raw_rows, SequenceABC
            ):
                findings.append(f"native_rows_not_array:{declared_owner}")
                continue
            for row in raw_rows:
                if not isinstance(row, row_type):
                    findings.append(f"native_row_type_invalid:{declared_owner}")
                    continue
                owner = str(row.owner_id)
                if owner != str(declared_owner):
                    findings.append(
                        f"native_owner_key_mismatch:{declared_owner}:{owner}"
                    )
                    continue
                groups.setdefault(owner, []).append(row)
    else:
        if isinstance(rows, (str, bytes)) or not isinstance(rows, SequenceABC):
            return {}, ("native_rows_not_array",)
        for row in rows:
            if not isinstance(row, row_type):
                findings.append("native_row_type_invalid")
                continue
            groups.setdefault(str(row.owner_id), []).append(row)
    return (
        {owner: tuple(values) for owner, values in groups.items()},
        tuple(sorted(set(findings))),
    )


def verify_recursive_native_execution(
    plan: RecursiveHierarchyPlan,
    contracts: Sequence[NativeModelCaseContract]
    | Mapping[str, Sequence[NativeModelCaseContract]]
    | None,
    results: Sequence[NativeModelCaseResult]
    | Mapping[str, Sequence[NativeModelCaseResult]]
    | None,
    *,
    raw_artifact_root: str | Path | None = None,
) -> Mapping[str, NativeCaseVerification]:
    """Verify native case receipts for every declared recursive owner.

    This helper is deliberately independent of hierarchy structure.  It only
    compares each owner's exact typed case contracts with producer-written
    results and validates raw-artifact identity.  ``review_recursive_hierarchy``
    uses its result to decide whether a structurally valid receipt may also be
    promoted as *executed* evidence.
    """

    contract_groups, contract_findings = _group_native_rows(
        contracts, row_type=NativeModelCaseContract
    )
    result_groups, result_findings = _group_native_rows(
        results, row_type=NativeModelCaseResult
    )
    available_case_keys = tuple(
        f"{owner_id}::{result.source_case_id}"
        for owner_id, owner_rows in sorted(result_groups.items())
        for result in owner_rows
    )
    owner_ids = {node.owner_id for node in plan.nodes if node.owner_id}
    verifications: dict[str, NativeCaseVerification] = {}
    for owner_id in sorted(owner_ids | set(contract_groups) | set(result_groups)):
        local_findings = [*contract_findings, *result_findings]
        owner_contracts = contract_groups.get(owner_id, ())
        owner_results = result_groups.get(owner_id, ())
        if not owner_contracts:
            local_findings.append("native_contracts_missing")
        if not owner_results:
            local_findings.append("native_results_missing")
        try:
            verification = verify_native_model_cases(
                owner_contracts,
                owner_results,
                raw_artifact_root=raw_artifact_root,
                available_case_keys=available_case_keys,
            )
        except (NativeCaseProtocolError, TypeError, ValueError) as exc:
            verification = NativeCaseVerification(
                ok=False,
                findings=(f"native_protocol_invalid:{type(exc).__name__}:{exc}",),
            )
        if local_findings:
            verification = NativeCaseVerification(
                ok=False,
                findings=tuple(
                    sorted(set((*verification.findings, *local_findings)))
                ),
                missing_case_ids=verification.missing_case_ids,
                foreign_case_ids=verification.foreign_case_ids,
                duplicate_case_ids=verification.duplicate_case_ids,
                unasserted_dimensions=verification.unasserted_dimensions,
                aggregate_case_ids=verification.aggregate_case_ids,
                leaf_case_ids=verification.leaf_case_ids,
                model_policy_pass=verification.model_policy_pass,
                implementation_boundary_pass=verification.implementation_boundary_pass,
            )
        verifications[owner_id] = verification
    return verifications


def review_recursive_hierarchy(
    plan: RecursiveHierarchyPlan,
    *,
    native_case_contracts: Sequence[NativeModelCaseContract]
    | Mapping[str, Sequence[NativeModelCaseContract]]
    | None = None,
    native_case_results: Sequence[NativeModelCaseResult]
    | Mapping[str, Sequence[NativeModelCaseResult]]
    | None = None,
    raw_artifact_root: str | Path | None = None,
    require_native_execution: bool = False,
) -> RecursiveHierarchyReport:
    """Review an arbitrary-depth hierarchy in post-order.

    The function is read-only.  It does not execute tests, emit evidence, or
    silently synthesize a passing receipt when a child proof is missing.
    """

    findings: list[RecursiveHierarchyFinding] = []
    strict = plan.is_strict()
    authority_pointer_mode = str(
        plan.metadata.get("authority_pointer_mode", "")
    ).strip().lower()
    authority_pointer_changed_raw = plan.metadata.get(
        "authority_pointer_changed_model_ids"
    )
    if isinstance(authority_pointer_changed_raw, str):
        authority_pointer_changed_values = (authority_pointer_changed_raw,)
    elif isinstance(authority_pointer_changed_raw, SequenceABC):
        authority_pointer_changed_values = tuple(authority_pointer_changed_raw)
    else:
        authority_pointer_changed_values = ()
    authority_pointer_changed = {
        str(item) for item in authority_pointer_changed_values if str(item)
    }
    pointer_reuse = authority_pointer_mode == "functional_reuse"
    if pointer_reuse and authority_pointer_changed_raw is None:
        findings.append(
            _finding(
                "authority_pointer_change_scope_missing",
                "functional pointer reuse must declare the affected model ids",
            )
        )
    elif authority_pointer_mode not in {"", "functional_reuse"}:
        findings.append(
            _finding(
                "authority_pointer_mode_unknown",
                "recursive hierarchy authority pointer mode is not current",
            )
        )
    native_execution_requested = bool(
        require_native_execution
        or native_case_contracts is not None
        or native_case_results is not None
    )
    native_verifications: Mapping[str, NativeCaseVerification] = {}
    if native_execution_requested:
        native_verifications = verify_recursive_native_execution(
            plan,
            native_case_contracts,
            native_case_results,
            raw_artifact_root=raw_artifact_root,
        )
    if strict and not plan.model_authority_head_fingerprint:
        findings.append(
            _finding(
                "model_authority_head_missing",
                "strict recursive hierarchy must declare the current model-authority head fingerprint",
            )
        )
    nodes_by_id: dict[str, RecursiveModelNode] = {}
    for node in plan.nodes:
        if not node.model_id:
            findings.append(_finding("model_id_missing", "recursive hierarchy node has no model id"))
            continue
        if node.model_id in nodes_by_id:
            findings.append(_finding("model_id_duplicate", "recursive hierarchy model id appears more than once", model_id=node.model_id))
        nodes_by_id[node.model_id] = node

    # Owner identity is a functional boundary, not a descriptive label.  A
    # duplicate owner would make two independently declared nodes share one
    # producer and invalidate the one-owner-per-node proof.
    owners: dict[str, list[str]] = {}
    for node in nodes_by_id.values():
        if node.owner_id:
            owners.setdefault(node.owner_id, []).append(node.model_id)
        child_ids = tuple(node.direct_child_ids)
        if len(child_ids) != len(set(child_ids)):
            findings.append(
                _finding(
                    "direct_child_ids_duplicate",
                    "recursive node direct-child set contains a duplicate id",
                    model_id=node.model_id,
                    metadata={"direct_child_ids": list(child_ids)},
                )
            )
    for owner_id, model_ids in sorted(owners.items()):
        if len(model_ids) > 1:
            findings.append(
                _finding(
                    "duplicate_owner",
                    "recursive hierarchy assigns one execution owner to multiple model nodes",
                    metadata={"owner_id": owner_id, "model_ids": sorted(model_ids)},
                )
            )

    root = nodes_by_id.get(plan.root_model_id)
    if root is None:
        findings.append(_finding("root_model_missing", "recursive hierarchy root is not declared", model_id=plan.root_model_id))

    receipts_by_id: dict[str, VerifiedSubtreeReceipt] = {}
    for receipt in plan.receipts:
        if not receipt.receipt_id:
            findings.append(_finding("receipt_id_missing", "subtree receipt has no stable id"))
            continue
        if receipt.receipt_id in receipts_by_id:
            findings.append(_finding("receipt_id_duplicate", "subtree receipt id appears more than once", receipt_id=receipt.receipt_id))
        receipts_by_id[receipt.receipt_id] = receipt

    # Structural checks are independent of receipt status.
    incoming: dict[str, list[str]] = {model_id: [] for model_id in nodes_by_id}
    for node in nodes_by_id.values():
        for child_id in node.direct_child_ids:
            child = nodes_by_id.get(child_id)
            if child is None:
                findings.append(_finding("child_model_missing", "node names a child model that is not declared", model_id=node.model_id, metadata={"child_model_id": child_id}))
                findings.append(_finding("child_model_foreign", "node names a child model outside the current hierarchy inventory", model_id=node.model_id, metadata={"child_model_id": child_id}))
                continue
            incoming.setdefault(child_id, []).append(node.model_id)
            if child.structural_parent_id != node.model_id:
                findings.append(_finding("child_parent_mismatch", "child parent_model_id does not match the containing node", model_id=child_id, metadata={"expected": node.model_id, "actual": child.parent_model_id}))
    if root is not None and root.parent_model_id:
        findings.append(_finding("root_parent_forbidden", "recursive hierarchy root cannot have a parent", model_id=root.model_id))
    for node in nodes_by_id.values():
        parents = incoming.get(node.model_id, [])
        if node.model_id == plan.root_model_id:
            continue
        if not parents and not node.structural_parent_id:
            findings.append(_finding("detached_model", "non-root model is detached from the hierarchy root", model_id=node.model_id))
        elif not parents and node.structural_parent_id:
            if node.structural_parent_id not in nodes_by_id:
                findings.append(_finding("parent_model_missing", "model names a parent that is not declared", model_id=node.model_id, metadata={"parent_model_id": node.structural_parent_id}))
            else:
                findings.append(_finding("structural_parent_not_reciprocated", "model structural parent does not declare the model as a direct child", model_id=node.model_id, metadata={"structural_parent_id": node.structural_parent_id}))
        elif len(parents) != 1:
            findings.append(_finding("multiple_parents", "model must have exactly one structural parent", model_id=node.model_id, metadata={"parents": parents}))
        elif node.structural_parent_id and node.structural_parent_id not in nodes_by_id:
            findings.append(_finding("parent_model_missing", "model names a parent that is not declared", model_id=node.model_id, metadata={"parent_model_id": node.structural_parent_id}))

    # An explicit enter/exit stack records cycles and reachability, and gives
    # a deterministic depth without making Python's call stack the hierarchy
    # depth limit.  A model tree is a finite input, but its depth is not a
    # product policy (and must not silently stop at five or at the interpreter
    # recursion limit).
    depths: dict[str, int] = {}
    visiting: set[str] = set()
    reachable: set[str] = set()

    def walk(model_id: str, depth: int) -> None:
        stack: list[tuple[str, int, bool]] = [(model_id, depth, False)]
        while stack:
            current_id, current_depth, exiting = stack.pop()
            if exiting:
                visiting.discard(current_id)
                continue
            if current_id in visiting:
                findings.append(
                    _finding(
                        "hierarchy_cycle",
                        "recursive model hierarchy contains a cycle",
                        model_id=current_id,
                    )
                )
                continue
            if current_id in reachable:
                continue
            node = nodes_by_id.get(current_id)
            if node is None:
                continue
            visiting.add(current_id)
            reachable.add(current_id)
            depths[current_id] = max(depths.get(current_id, 0), current_depth)
            stack.append((current_id, current_depth, True))
            # Preserve declaration order while using LIFO traversal.
            stack.extend(
                (child_id, current_depth + 1, False)
                for child_id in reversed(node.direct_child_ids)
            )

    if root is not None:
        walk(root.model_id, 0)
    for model_id in sorted(set(nodes_by_id) - reachable):
        findings.append(_finding("model_unreachable", "recursive hierarchy node is not reachable from the root", model_id=model_id))

    # Bottom-up closure.  Descendant sets are computed from the structure, not
    # trusted from a caller-provided receipt.
    descendants: dict[str, tuple[str, ...]] = {}
    verified_receipt_ids: list[str] = []
    execution_verified_receipt_ids: list[str] = []
    # Model ids, rather than receipt ids, are tracked here so a parent can
    # require the exact direct child node to have completed its own recursive
    # closure before the parent is promoted to ``verified``.  A passing receipt
    # on its own is not enough when that child has an unverified descendant.
    verified_model_ids: set[str] = set()
    execution_verified_model_ids: set[str] = set()
    consumed_receipt_ids: set[str] = set()
    leaf_ids: list[str] = []
    postorder_active: set[str] = set()
    postorder_seen: set[str] = set()

    def explicit_postorder(model_id: str) -> tuple[str, ...]:
        """Return one finite post-order without using Python recursion."""

        order: list[str] = []
        active: set[str] = set()
        seen: set[str] = set()
        work: list[tuple[str, bool]] = [(model_id, False)]
        while work:
            current_id, exiting = work.pop()
            node = nodes_by_id.get(current_id)
            if node is None:
                continue
            if exiting:
                active.discard(current_id)
                seen.add(current_id)
                order.append(current_id)
                continue
            if current_id in active:
                findings.append(
                    _finding(
                        "hierarchy_cycle",
                        "recursive model hierarchy contains a cycle",
                        model_id=current_id,
                    )
                )
                continue
            if current_id in seen:
                continue
            active.add(current_id)
            work.append((current_id, True))
            work.extend(
                (child_id, False)
                for child_id in reversed(node.direct_child_ids)
            )
        return tuple(order)

    def postorder(model_id: str) -> tuple[str, ...]:
        node = nodes_by_id.get(model_id)
        if node is None:
            return ()
        if model_id in postorder_active:
            findings.append(_finding("hierarchy_cycle", "recursive model hierarchy contains a cycle", model_id=model_id))
            return (model_id,)
        if model_id in postorder_seen:
            return descendants.get(model_id, (model_id,))
        postorder_active.add(model_id)
        child_descendants = [
            descendants.get(
                child_id,
                (child_id,) if child_id in nodes_by_id else (),
            )
            for child_id in node.direct_child_ids
        ]
        descendant_ids = tuple(sorted({node.model_id, *(item for values in child_descendants for item in values)}))
        descendants[node.model_id] = descendant_ids
        if node.is_leaf:
            leaf_ids.append(node.model_id)
        if not strict:
            postorder_active.remove(model_id)
            postorder_seen.add(model_id)
            return descendant_ids

        # The universe is derived strictly from the actual post-order node
        # walk.  A declared node value is an assertion to compare, never the
        # source of the denominator.
        expected_universe_fingerprint = descendant_universe_fingerprint(
            descendant_ids
        )
        for field_name in (
            "owner_id",
            "model_fingerprint",
            "claim_scope",
            "subtree_receipt_id",
        ):
            if not getattr(node, field_name):
                findings.append(
                    _finding(
                        f"node_{field_name}_missing",
                        f"strict recursive node has no {field_name}",
                        model_id=node.model_id,
                    )
                )
        if not node.obligation_ids:
            findings.append(
                _finding(
                    "node_obligation_ids_missing",
                    "strict recursive node has no model obligations",
                    model_id=node.model_id,
                )
            )
        if node.model_id != plan.root_model_id and not node.structural_parent_id:
            findings.append(
                _finding(
                    "node_structural_parent_id_missing",
                    "strict non-root recursive node has no structural parent",
                    model_id=node.model_id,
                )
            )
        if not node.partition_fingerprint:
            findings.append(
                _finding(
                    "node_partition_fingerprint_missing",
                    "strict recursive node has no partition fingerprint",
                    model_id=node.model_id,
                )
            )
        if not node.descendant_universe_fingerprint:
            findings.append(
                _finding(
                    "node_descendant_universe_fingerprint_missing",
                    "strict recursive node has no descendant-universe fingerprint",
                    model_id=node.model_id,
                )
            )
        elif node.descendant_universe_fingerprint != expected_universe_fingerprint:
            findings.append(
                _finding(
                    "node_descendant_universe_fingerprint_mismatch",
                    "node descendant-universe fingerprint is not derived from the actual post-order descendants",
                    model_id=node.model_id,
                    metadata={
                        "expected": expected_universe_fingerprint,
                        "actual": node.descendant_universe_fingerprint,
                    },
                )
            )
        if not node.model_authority_head_fingerprint:
            findings.append(
                _finding(
                    "node_model_authority_head_missing",
                    "strict recursive node has no model-authority head fingerprint",
                    model_id=node.model_id,
                )
            )
        elif plan.model_authority_head_fingerprint and node.model_authority_head_fingerprint != plan.model_authority_head_fingerprint:
            pointer_only_for_node = (
                pointer_reuse
                and node.model_id not in authority_pointer_changed
            )
            findings.append(
                _finding(
                    "node_model_authority_head_mismatch"
                    if not pointer_only_for_node
                    else "node_model_authority_pointer_advanced",
                    (
                        "node is bound to a different model-authority head than the current plan"
                        if not pointer_only_for_node
                        else "model-authority pointer advanced; node functional identity remains independently checked"
                    ),
                    severity="info" if pointer_only_for_node else "blocker",
                    model_id=node.model_id,
                    metadata={
                        "expected": plan.model_authority_head_fingerprint,
                        "actual": node.model_authority_head_fingerprint,
                        "affected_model_ids": sorted(authority_pointer_changed),
                    },
                )
            )
        for field_name in ("toolchain_fingerprint", "environment_fingerprint"):
            value = getattr(node, field_name)
            if not value:
                findings.append(
                    _finding(
                        f"node_{field_name}_missing",
                        f"strict recursive node has no {field_name}",
                        model_id=node.model_id,
                    )
                )
            else:
                expected_context = getattr(plan, field_name)
                if expected_context and value != expected_context:
                    findings.append(
                        _finding(
                            f"node_{field_name}_mismatch",
                            f"node {field_name} does not match the current hierarchy plan",
                            model_id=node.model_id,
                            metadata={"expected": expected_context, "actual": value},
                        )
                    )

        receipt = _receipt_for_node(node, receipts_by_id)
        expected_receipt_id = node.subtree_receipt_id or f"subtree:{node.model_id}"
        findings.extend(_leaf_product_findings(plan, node, receipt))
        native_owner_verification = native_verifications.get(node.owner_id)
        native_owner_ok = True
        if native_execution_requested:
            native_owner_ok = bool(
                native_owner_verification is not None
                and native_owner_verification.ok
            )
            if not native_owner_ok:
                findings.append(
                    _finding(
                        "native_case_execution_blocked",
                        "recursive subtree receipt cannot be promoted without exact current native case results",
                        model_id=node.model_id,
                        receipt_id=expected_receipt_id,
                        metadata={
                            "owner_id": node.owner_id,
                            "verification": (
                                native_owner_verification.to_dict()
                                if native_owner_verification is not None
                                else {"status": "blocked", "findings": ["native_owner_missing"]}
                            ),
                        },
                    )
                )
        if receipt is None:
            findings.append(_finding("subtree_receipt_missing", "strict hierarchy node has no terminal subtree receipt", model_id=node.model_id, receipt_id=expected_receipt_id))
            postorder_active.remove(model_id)
            postorder_seen.add(model_id)
            return descendant_ids
        consumed_receipt_ids.add(receipt.receipt_id)
        if not receipt.obligation_ids:
            findings.append(
                _finding(
                    "subtree_receipt_obligation_ids_missing",
                    "strict subtree receipt has no model obligations",
                    model_id=node.model_id,
                    receipt_id=receipt.receipt_id,
                )
            )
        receipt_head_expected = (
            ""
            if pointer_reuse and node.model_id not in authority_pointer_changed
            else plan.model_authority_head_fingerprint
        )
        if not receipt.is_authority_verified(
            expected_model_authority_head_fingerprint=receipt_head_expected
        ):
            findings.append(_finding("subtree_receipt_not_verified", "subtree receipt is not a verified terminal result", model_id=node.model_id, receipt_id=receipt.receipt_id, metadata={"receipt": receipt.to_dict()}))
        expected = {
            "receipt_id": expected_receipt_id,
            "model_id": node.model_id,
            "owner_id": node.owner_id,
            "structural_parent_id": node.structural_parent_id,
            "direct_child_ids": node.direct_child_ids,
            "claim_scope": node.claim_scope or plan.claim_scope,
            "model_fingerprint": node.model_fingerprint,
            "obligation_ids": node.obligation_ids,
            "child_receipt_ids": tuple(
                _declared_receipt_id(child_id, nodes_by_id)
                for child_id in node.direct_child_ids
            ),
            "child_receipt_fingerprints": {
                _declared_receipt_id(child_id, nodes_by_id): (
                    _receipt_for_node(nodes_by_id[child_id], receipts_by_id).fingerprint
                    if child_id in nodes_by_id
                    and _receipt_for_node(nodes_by_id[child_id], receipts_by_id) is not None
                    else ""
                )
                for child_id in node.direct_child_ids
            },
            "descendant_model_ids": descendant_ids,
            "partition_fingerprint": node.partition_fingerprint,
            "descendant_universe_fingerprint": expected_universe_fingerprint,
            "model_authority_head_fingerprint": (
                node.model_authority_head_fingerprint
                if pointer_reuse and node.model_id not in authority_pointer_changed
                else plan.model_authority_head_fingerprint
            ),
            "toolchain_fingerprint": node.toolchain_fingerprint,
            "environment_fingerprint": node.environment_fingerprint,
        }
        if node.subtree_receipt_fingerprint:
            expected["fingerprint"] = node.subtree_receipt_fingerprint
        for field_name, expected_value in expected.items():
            actual = getattr(receipt, field_name)
            if field_name in {"obligation_ids", "direct_child_ids", "child_receipt_ids", "descendant_model_ids"}:
                actual = _as_tuple(actual)
            elif field_name == "child_receipt_fingerprints":
                actual = {
                    str(receipt_id): str(fingerprint)
                    for receipt_id, fingerprint in dict(actual).items()
                }
            else:
                actual = str(actual)
            if actual != expected_value:
                findings.append(_finding(
                    f"subtree_receipt_{field_name}_mismatch",
                    f"subtree receipt {field_name} does not match the exact hierarchy node",
                    model_id=node.model_id,
                    receipt_id=receipt.receipt_id,
                    metadata={"expected": expected_value, "actual": actual},
                ))
        expected_child_receipt_ids = tuple(expected["child_receipt_ids"])
        actual_child_receipt_ids = tuple(receipt.child_receipt_ids)
        if len(expected_child_receipt_ids) != len(set(expected_child_receipt_ids)):
            findings.append(
                _finding(
                    "subtree_receipt_child_receipt_id_duplicate",
                    "parent subtree receipt maps more than one direct child to the same receipt id",
                    model_id=node.model_id,
                    receipt_id=receipt.receipt_id,
                    metadata={"child_receipt_ids": list(expected_child_receipt_ids)},
                )
            )
        expected_child_receipt_fingerprints = dict(expected["child_receipt_fingerprints"])
        for child_id in node.direct_child_ids:
            child_receipt_id = _declared_receipt_id(child_id, nodes_by_id)
            child_receipt = (
                _receipt_for_node(nodes_by_id[child_id], receipts_by_id)
                if child_id in nodes_by_id
                else None
            )
            if child_receipt is None or not child_receipt.fingerprint:
                findings.append(
                    _finding(
                        "subtree_receipt_child_receipt_fingerprint_missing",
                        "parent subtree receipt cannot bind a missing or fingerprint-less direct child receipt",
                        model_id=node.model_id,
                        receipt_id=receipt.receipt_id,
                        metadata={
                            "child_model_id": child_id,
                            "child_receipt_id": child_receipt_id,
                        },
                    )
                )

        # A parent receipt is only promoted after every direct child has been
        # promoted by this same post-order review.  This keeps a parent from
        # laundering a local ``passed`` result when a deeper child is missing,
        # stale, malformed, or otherwise blocked.
        unverified_children = tuple(
            child_id
            for child_id in node.direct_child_ids
            if child_id not in verified_model_ids
        )
        if unverified_children:
            findings.append(
                _finding(
                    "subtree_receipt_child_not_verified",
                    "parent subtree receipt cannot be verified until every direct child subtree is verified",
                    model_id=node.model_id,
                    receipt_id=receipt.receipt_id,
                    metadata={"child_model_ids": list(unverified_children)},
                )
            )
        # A receipt is a terminal proof of this node only when the node's own
        # structural and authority checks are clean as well.  Looking only
        # for receipt-tagged findings would let a locally passing receipt
        # promote a node whose model declaration is already blocked (for
        # example, a wrong parent, stale universe, or missing authority).
        node_has_blocking_findings = any(
            finding.model_id == node.model_id
            and finding.severity == "blocker"
            for finding in findings
        )
        if receipt.is_authority_verified(
            expected_model_authority_head_fingerprint=receipt_head_expected
        ) and not unverified_children and not node_has_blocking_findings:
            verified_receipt_ids.append(receipt.receipt_id)
            verified_model_ids.add(node.model_id)
            if native_execution_requested and native_owner_ok:
                # Native promotion is post-order as well: an aggregate owner
                # must consume only children that were themselves promoted by
                # the same native execution review.
                unverified_native_children = tuple(
                    child_id
                    for child_id in node.direct_child_ids
                    if child_id not in execution_verified_model_ids
                )
                if unverified_native_children:
                    findings.append(
                        _finding(
                            "native_child_execution_not_verified",
                            "native aggregate receipt cannot be promoted until every direct child has exact native evidence",
                            model_id=node.model_id,
                            receipt_id=receipt.receipt_id,
                            metadata={
                                "child_model_ids": list(unverified_native_children)
                            },
                        )
                    )
                else:
                    execution_verified_receipt_ids.append(receipt.receipt_id)
                    execution_verified_model_ids.add(node.model_id)
        postorder_active.remove(model_id)
        postorder_seen.add(model_id)
        return descendant_ids

    if root is not None:
        for model_id in explicit_postorder(root.model_id):
            postorder(model_id)
    if strict:
        for receipt_id in sorted(set(receipts_by_id) - consumed_receipt_ids):
            findings.append(_finding("subtree_receipt_unconsumed", "subtree receipt is not consumed by any declared model node", receipt_id=receipt_id))

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    terminal_receipt = None
    if root is not None:
        terminal_receipt = _receipt_for_node(root, receipts_by_id)
    return RecursiveHierarchyReport(
        ok=not blockers,
        hierarchy_id=plan.hierarchy_id,
        root_model_id=plan.root_model_id,
        decision="recursive_hierarchy_green" if not blockers else "recursive_hierarchy_blocked",
        max_depth=max(depths.values(), default=0),
        leaf_model_ids=tuple(sorted(set(leaf_ids))),
        verified_receipt_ids=tuple(sorted(set(verified_receipt_ids))),
        execution_verified_receipt_ids=tuple(
            sorted(set(execution_verified_receipt_ids))
        ),
        native_case_verifications=native_verifications,
        findings=tuple(findings),
        terminal_receipt=terminal_receipt,
    )


# Friendly aliases used by adapters that call the object a subtree proof.
ModelHierarchyNode = RecursiveModelNode
SubtreeReceipt = VerifiedSubtreeReceipt
RecursiveSubtreeReceipt = VerifiedSubtreeReceipt


__all__ = [
    "ModelHierarchyNode",
    "RECURSIVE_CLAIM_SCOPES",
    "RECURSIVE_HIERARCHY_SCHEMA",
    "RECURSIVE_STATUS_FAILED",
    "RECURSIVE_STATUS_PASSED",
    "RECURSIVE_STATUS_STALE",
    "build_recursive_leaf_product_signature",
    "derive_descendant_universe_fingerprint",
    "descendant_universe_fingerprint",
    "RecursiveHierarchyFinding",
    "RecursiveHierarchyPlan",
    "RecursiveHierarchyReport",
    "RecursiveModelNode",
    "RecursiveSubtreeReceipt",
    "SubtreeReceipt",
    "VerifiedSubtreeReceipt",
    "is_verified_subtree_receipt",
    "verify_recursive_native_execution",
    "review_recursive_hierarchy",
]
