"""Behavior-level software blueprint and static-readiness review.

The APIs in this module are project-neutral and pure.  They distinguish an
accepted behavior contract, a prepared checker design, current execution
evidence. Candidate discovery never accepts
source-derived semantics and no readiness review starts a process or writes a
target project.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from .implementation_blueprint import BlueprintResourceReference


BEHAVIOR_BLUEPRINT_SCHEMA = "flowguard.behavior_blueprint.v3"
RESOURCE_INVENTORY_SCHEMA = "flowguard.project_resource_inventory.v2"
INTENT_INVENTORY_SCHEMA = "flowguard.project_intent_inventory.v2"
STATIC_BLUEPRINT_READINESS_SCHEMA = "flowguard.static_blueprint_readiness.v1"
NORMALIZED_PROJECTION_SCHEMA = "flowguard.normalized_blueprint_projection.v2"
CANDIDATE_BLUEPRINT_SCHEMA = "flowguard.candidate_blueprint.v2"

BEHAVIOR_DIMENSIONS = (
    "input",
    "state",
    "output",
    "effect",
    "error",
    "decision",
    "order",
    "retry",
    "timeout",
    "completion",
)
DIMENSION_DISPOSITIONS = frozenset({"modeled", "not_applicable"})
EXECUTION_DISPOSITIONS = frozenset(
    {"pass", "fail", "not_run", "blocked", "not_applicable"}
)
TEST_NODE_DISPOSITIONS = frozenset(
    {
        "behavior_coverage",
        "cross_owner_integration",
        "supporting",
        "duplicate",
        "scoped_out",
        "blocked",
    }
)
RESOURCE_CATEGORIES = (
    "build",
    "runtime",
    "dependency",
    "configuration",
    "schema",
    "data",
    "asset",
    "migration",
    "external_service",
    "behavioral_oracle",
)
RESOURCE_DISPOSITIONS = frozenset({"current", "external", "scoped_out", "blocked"})
TERMINAL_ASSERTION_CALL_NAMES = frozenset(
    {"assert_called_once", "assert_called_once_with", "assert_not_called"}
)
INTENT_DISPOSITIONS = frozenset(
    {"accepted", "superseded", "rejected", "scoped_out", "blocked"}
)
READINESS_STATUSES = frozenset({"ready", "incomplete", "stale", "blocked"})


class SoftwareBlueprintReadinessError(ValueError):
    """Raised when a behavior blueprint payload is ambiguous or self-licensing."""


def _tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _pairs(values: Mapping[str, str] | Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    rows = values.items() if isinstance(values, Mapping) else values
    return tuple(sorted((str(key), str(value)) for key, value in rows))


def _fingerprint(value: Any) -> str:
    fingerprint, _logical_bytes = _canonical_fingerprint_and_size(value)
    return fingerprint


def _canonical_fingerprint_and_size(value: Any) -> tuple[str, int]:
    """Hash canonical JSON incrementally without retaining its full text."""

    digest = hashlib.sha256()
    logical_bytes = 0
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    for chunk in encoder.iterencode(value):
        encoded = chunk.encode("utf-8")
        digest.update(encoded)
        logical_bytes += len(encoded)
    return f"sha256:{digest.hexdigest()}", logical_bytes


@dataclass(frozen=True)
class ReadinessFinding:
    code: str
    message: str
    member_ids: tuple[str, ...] = ()
    severity: str = "incomplete"

    def __post_init__(self) -> None:
        if self.severity not in {"incomplete", "stale", "blocked"}:
            raise SoftwareBlueprintReadinessError("invalid readiness finding severity")
        object.__setattr__(self, "member_ids", _tuple(self.member_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "member_ids": list(self.member_ids),
            "severity": self.severity,
        }


@dataclass(frozen=True)
class BehaviorDimensionContract:
    dimension: str
    disposition: str
    semantics: str
    rationale: str
    provenance_fingerprints: tuple[tuple[str, str], ...]
    semantic_rule_ids: tuple[str, ...]
    applicability_surface_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.dimension not in BEHAVIOR_DIMENSIONS:
            raise SoftwareBlueprintReadinessError(f"unknown behavior dimension: {self.dimension}")
        if self.disposition not in DIMENSION_DISPOSITIONS:
            raise SoftwareBlueprintReadinessError("unknown behavior dimension disposition")
        if not self.semantics.strip() or not self.rationale.strip():
            raise SoftwareBlueprintReadinessError("behavior dimension requires semantics and rationale")
        object.__setattr__(self, "provenance_fingerprints", _pairs(self.provenance_fingerprints))
        if not self.provenance_fingerprints:
            raise SoftwareBlueprintReadinessError("behavior dimension requires independent provenance")
        object.__setattr__(self, "semantic_rule_ids", _tuple(self.semantic_rule_ids))
        object.__setattr__(
            self,
            "applicability_surface_ids",
            _tuple(self.applicability_surface_ids),
        )
        if not self.semantic_rule_ids or not self.applicability_surface_ids:
            raise SoftwareBlueprintReadinessError(
                "behavior dimension requires exact rule and applicability identities"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "disposition": self.disposition,
            "semantics": self.semantics,
            "rationale": self.rationale,
            "provenance_fingerprints": dict(self.provenance_fingerprints),
            "semantic_rule_ids": list(self.semantic_rule_ids),
            "applicability_surface_ids": list(self.applicability_surface_ids),
        }


@dataclass(frozen=True)
class BehaviorBlockContract:
    behavior_block_id: str
    implementation_surface_id: str
    model_element_id: str
    owner_contract_id: str
    owner_id: str
    function_relation: str
    dimensions: tuple[BehaviorDimensionContract, ...]
    semantic_spec_ids: tuple[str, ...]
    oracle_ids: tuple[str, ...]
    portable_binding_ids: tuple[str, ...]
    protected_failure_ids: tuple[str, ...]
    accepted: bool
    acceptance_evidence_fingerprints: tuple[tuple[str, str], ...]
    source_fingerprint: str

    def __post_init__(self) -> None:
        identities = (
            self.behavior_block_id,
            self.implementation_surface_id,
            self.model_element_id,
            self.owner_contract_id,
            self.owner_id,
            self.source_fingerprint,
        )
        if not all(identities):
            raise SoftwareBlueprintReadinessError("behavior block identity is incomplete")
        if self.function_relation != "Input x State -> Set(Output x State)":
            raise SoftwareBlueprintReadinessError("behavior block relation is not canonical")
        object.__setattr__(self, "dimensions", tuple(sorted(self.dimensions, key=lambda row: row.dimension)))
        observed = tuple(row.dimension for row in self.dimensions)
        if set(observed) != set(BEHAVIOR_DIMENSIONS) or len(observed) != len(BEHAVIOR_DIMENSIONS):
            raise SoftwareBlueprintReadinessError("behavior block does not close every canonical dimension")
        object.__setattr__(self, "semantic_spec_ids", _tuple(self.semantic_spec_ids))
        object.__setattr__(self, "oracle_ids", _tuple(self.oracle_ids))
        object.__setattr__(self, "portable_binding_ids", _tuple(self.portable_binding_ids))
        object.__setattr__(self, "protected_failure_ids", _tuple(self.protected_failure_ids))
        if not self.semantic_spec_ids or not self.oracle_ids or not self.portable_binding_ids:
            raise SoftwareBlueprintReadinessError(
                "behavior block requires semantic, oracle, and portable binding identities"
            )
        if any(
            self.implementation_surface_id not in row.applicability_surface_ids
            for row in self.dimensions
        ):
            raise SoftwareBlueprintReadinessError(
                "behavior dimension applicability does not include its exact surface"
            )
        object.__setattr__(
            self,
            "acceptance_evidence_fingerprints",
            _pairs(self.acceptance_evidence_fingerprints),
        )
        if self.accepted and not self.acceptance_evidence_fingerprints:
            raise SoftwareBlueprintReadinessError("accepted behavior block requires independent acceptance evidence")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "behavior_block_id": self.behavior_block_id,
            "implementation_surface_id": self.implementation_surface_id,
            "model_element_id": self.model_element_id,
            "owner_contract_id": self.owner_contract_id,
            "owner_id": self.owner_id,
            "function_relation": self.function_relation,
            "dimensions": [row.to_dict() for row in self.dimensions],
            "semantic_spec_ids": list(self.semantic_spec_ids),
            "oracle_ids": list(self.oracle_ids),
            "portable_binding_ids": list(self.portable_binding_ids),
            "protected_failure_ids": list(self.protected_failure_ids),
            "accepted": self.accepted,
            "acceptance_evidence_fingerprints": dict(self.acceptance_evidence_fingerprints),
            "source_fingerprint": self.source_fingerprint,
        }


@dataclass(frozen=True)
class SupportingSurfaceRelation:
    supporting_surface_id: str
    behavior_block_id: str
    relation_kind: str
    evidence_id: str
    evidence_fingerprint: str
    rationale: str

    def __post_init__(self) -> None:
        if self.relation_kind not in {"calls", "delegates", "reads_for", "writes_for"}:
            raise SoftwareBlueprintReadinessError("supporting relation kind is not current")
        if not all(
            (
                self.supporting_surface_id,
                self.behavior_block_id,
                self.evidence_id,
                self.evidence_fingerprint,
                self.rationale.strip(),
            )
        ):
            raise SoftwareBlueprintReadinessError("supporting relation identity is incomplete")

    def to_dict(self) -> dict[str, str]:
        return {
            "supporting_surface_id": self.supporting_surface_id,
            "behavior_block_id": self.behavior_block_id,
            "relation_kind": self.relation_kind,
            "evidence_id": self.evidence_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class PortableBehaviorBinding:
    binding_id: str
    behavior_block_id: str
    portable_model_id: str
    portable_model_fingerprint: str
    implementation_fingerprint: str
    transition_ids: tuple[str, ...]
    property_ids: tuple[str, ...]
    invariant_ids: tuple[str, ...]
    input_field_mappings: tuple[tuple[str, str], ...]
    output_field_mappings: tuple[tuple[str, str], ...]
    state_field_mappings: tuple[tuple[str, str], ...]
    assumption_ids: tuple[str, ...]
    guarantee_ids: tuple[str, ...]
    protected_failure_ids: tuple[str, ...]
    provider_fingerprints: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not all(
            (
                self.binding_id,
                self.behavior_block_id,
                self.portable_model_id,
                self.portable_model_fingerprint,
                self.implementation_fingerprint,
            )
        ):
            raise SoftwareBlueprintReadinessError(
                "portable behavior binding identity is incomplete"
            )
        object.__setattr__(self, "transition_ids", _tuple(self.transition_ids))
        object.__setattr__(self, "property_ids", _tuple(self.property_ids))
        object.__setattr__(self, "invariant_ids", _tuple(self.invariant_ids))
        object.__setattr__(self, "assumption_ids", _tuple(self.assumption_ids))
        object.__setattr__(self, "guarantee_ids", _tuple(self.guarantee_ids))
        object.__setattr__(
            self, "protected_failure_ids", _tuple(self.protected_failure_ids)
        )
        object.__setattr__(self, "input_field_mappings", _pairs(self.input_field_mappings))
        object.__setattr__(self, "output_field_mappings", _pairs(self.output_field_mappings))
        object.__setattr__(self, "state_field_mappings", _pairs(self.state_field_mappings))
        object.__setattr__(self, "provider_fingerprints", _pairs(self.provider_fingerprints))
        if (
            not self.property_ids
            or not self.invariant_ids
            or not self.guarantee_ids
            or not self.provider_fingerprints
        ):
            raise SoftwareBlueprintReadinessError(
                "portable behavior binding requires properties, guarantees, and provider evidence"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "behavior_block_id": self.behavior_block_id,
            "portable_model_id": self.portable_model_id,
            "portable_model_fingerprint": self.portable_model_fingerprint,
            "implementation_fingerprint": self.implementation_fingerprint,
            "transition_ids": list(self.transition_ids),
            "property_ids": list(self.property_ids),
            "invariant_ids": list(self.invariant_ids),
            "input_field_mappings": dict(self.input_field_mappings),
            "output_field_mappings": dict(self.output_field_mappings),
            "state_field_mappings": dict(self.state_field_mappings),
            "assumption_ids": list(self.assumption_ids),
            "guarantee_ids": list(self.guarantee_ids),
            "protected_failure_ids": list(self.protected_failure_ids),
            "provider_fingerprints": dict(self.provider_fingerprints),
        }


@dataclass(frozen=True)
class BehaviorCaseContract:
    case_id: str
    behavior_block_id: str
    case_kind: str
    input_values: tuple[tuple[str, str], ...]
    initial_state: tuple[tuple[str, str], ...]
    expected_output: tuple[tuple[str, str], ...]
    expected_state: tuple[tuple[str, str], ...]
    expected_effects: tuple[str, ...]
    expected_errors: tuple[str, ...]
    oracle_id: str
    case_evidence_id: str
    case_evidence_fingerprint: str
    value_mode: str
    protected_failure_ids: tuple[str, ...] = ()
    parameter_case_id: str = ""

    def __post_init__(self) -> None:
        if self.case_kind not in {"good", "bad", "boundary"}:
            raise SoftwareBlueprintReadinessError("unknown behavior case kind")
        if not all(
            (
                self.case_id,
                self.behavior_block_id,
                self.oracle_id,
                self.case_evidence_id,
                self.case_evidence_fingerprint,
            )
        ):
            raise SoftwareBlueprintReadinessError("behavior case identity is incomplete")
        if self.value_mode not in {"literal", "symbolic_contract"}:
            raise SoftwareBlueprintReadinessError("behavior case value mode is not current")
        object.__setattr__(self, "input_values", _pairs(self.input_values))
        object.__setattr__(self, "initial_state", _pairs(self.initial_state))
        object.__setattr__(self, "expected_output", _pairs(self.expected_output))
        object.__setattr__(self, "expected_state", _pairs(self.expected_state))
        object.__setattr__(self, "expected_effects", _tuple(self.expected_effects))
        object.__setattr__(self, "expected_errors", _tuple(self.expected_errors))
        object.__setattr__(self, "protected_failure_ids", _tuple(self.protected_failure_ids))
        object.__setattr__(self, "parameter_case_id", str(self.parameter_case_id))
        if self.case_kind == "bad" and not (
            self.expected_errors or self.protected_failure_ids
        ):
            raise SoftwareBlueprintReadinessError(
                "bad behavior case requires an error or protected failure"
            )
        serialized_values = tuple(
            value
            for rows in (
                self.input_values,
                self.initial_state,
                self.expected_output,
                self.expected_state,
            )
            for _key, value in rows
        )
        if any(
            "owner-defined" in value.strip().lower()
            or value.strip().lower() in {"todo", "tbd", "placeholder"}
            or value.strip().lower().startswith(("todo:", "tbd:", "placeholder:"))
            for value in serialized_values
        ):
            raise SoftwareBlueprintReadinessError(
                "behavior case contains a placeholder instead of an exact value or rule"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "behavior_block_id": self.behavior_block_id,
            "case_kind": self.case_kind,
            "input_values": dict(self.input_values),
            "initial_state": dict(self.initial_state),
            "expected_output": dict(self.expected_output),
            "expected_state": dict(self.expected_state),
            "expected_effects": list(self.expected_effects),
            "expected_errors": list(self.expected_errors),
            "oracle_id": self.oracle_id,
            "case_evidence_id": self.case_evidence_id,
            "case_evidence_fingerprint": self.case_evidence_fingerprint,
            "value_mode": self.value_mode,
            "protected_failure_ids": list(self.protected_failure_ids),
            "parameter_case_id": self.parameter_case_id,
        }


@dataclass(frozen=True)
class BehaviorCoverageEdge:
    coverage_id: str
    behavior_block_id: str
    implementation_surface_id: str
    model_obligation_id: str
    semantic_spec_id: str
    owner_contract_id: str
    test_node_id: str
    oracle_member_id: str
    oracle_member_fingerprint: str
    case_id: str
    covered_dimensions: tuple[str, ...]
    evidence_role: str
    oracle_id: str

    def __post_init__(self) -> None:
        required = (
            self.coverage_id,
            self.behavior_block_id,
            self.implementation_surface_id,
            self.model_obligation_id,
            self.semantic_spec_id,
            self.owner_contract_id,
            self.test_node_id,
            self.oracle_member_id,
            self.oracle_member_fingerprint,
            self.case_id,
            self.evidence_role,
            self.oracle_id,
        )
        if not all(required):
            raise SoftwareBlueprintReadinessError("behavior coverage identity is incomplete")
        object.__setattr__(self, "covered_dimensions", _tuple(self.covered_dimensions))
        if not self.covered_dimensions or set(self.covered_dimensions) - set(BEHAVIOR_DIMENSIONS):
            raise SoftwareBlueprintReadinessError("behavior coverage dimensions are invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_id": self.coverage_id,
            "behavior_block_id": self.behavior_block_id,
            "implementation_surface_id": self.implementation_surface_id,
            "model_obligation_id": self.model_obligation_id,
            "semantic_spec_id": self.semantic_spec_id,
            "owner_contract_id": self.owner_contract_id,
            "test_node_id": self.test_node_id,
            "oracle_member_id": self.oracle_member_id,
            "oracle_member_fingerprint": self.oracle_member_fingerprint,
            "case_id": self.case_id,
            "covered_dimensions": list(self.covered_dimensions),
            "evidence_role": self.evidence_role,
            "oracle_id": self.oracle_id,
        }


@dataclass(frozen=True)
class CoverageExecutionEvidence:
    coverage_id: str
    execution_owner_id: str
    disposition: str
    receipt_id: str = ""
    receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.coverage_id or not self.execution_owner_id:
            raise SoftwareBlueprintReadinessError(
                "coverage execution identity is incomplete"
            )
        if self.disposition not in EXECUTION_DISPOSITIONS:
            raise SoftwareBlueprintReadinessError(
                "unknown coverage execution disposition"
            )
        if self.disposition == "pass" and not (
            self.receipt_id and self.receipt_fingerprint
        ):
            raise SoftwareBlueprintReadinessError(
                "passing coverage execution requires an exact terminal receipt"
            )
        if self.disposition != "pass" and (self.receipt_id or self.receipt_fingerprint):
            raise SoftwareBlueprintReadinessError(
                "non-pass coverage execution cannot carry a passing receipt"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "coverage_id": self.coverage_id,
            "execution_owner_id": self.execution_owner_id,
            "disposition": self.disposition,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
        }


@dataclass(frozen=True)
class DelegatedAssertionHelper:
    """Explicit test helper whose call graph must reach real oracle members."""

    helper_id: str
    test_node_id: str
    source_fingerprint: str
    callee_member_ids: tuple[str, ...]
    terminal_member_fingerprints: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.helper_id or not self.test_node_id or not self.source_fingerprint:
            raise SoftwareBlueprintReadinessError(
                "delegated assertion helper identity is incomplete"
            )
        object.__setattr__(self, "callee_member_ids", _tuple(self.callee_member_ids))
        object.__setattr__(
            self,
            "terminal_member_fingerprints",
            _pairs(self.terminal_member_fingerprints),
        )
        if not self.callee_member_ids and not self.terminal_member_fingerprints:
            raise SoftwareBlueprintReadinessError(
                "delegated assertion helper requires a terminal call path"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "helper_id": self.helper_id,
            "test_node_id": self.test_node_id,
            "source_fingerprint": self.source_fingerprint,
            "callee_member_ids": list(self.callee_member_ids),
            "terminal_member_fingerprints": dict(
                self.terminal_member_fingerprints
            ),
        }


@dataclass(frozen=True)
class ProjectTestNodeDisposition:
    test_node_id: str
    disposition: str
    owner_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if self.disposition not in TEST_NODE_DISPOSITIONS:
            raise SoftwareBlueprintReadinessError("unknown project test-node disposition")
        if not self.test_node_id or not self.rationale.strip():
            raise SoftwareBlueprintReadinessError("test-node disposition is incomplete")
        object.__setattr__(self, "owner_ids", _tuple(self.owner_ids))
        object.__setattr__(self, "coverage_ids", _tuple(self.coverage_ids))
        if self.disposition in {"behavior_coverage", "cross_owner_integration"} and not self.coverage_ids:
            raise SoftwareBlueprintReadinessError("coverage disposition requires exact coverage ids")

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_node_id": self.test_node_id,
            "disposition": self.disposition,
            "owner_ids": list(self.owner_ids),
            "coverage_ids": list(self.coverage_ids),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ProjectResourceMember:
    member_id: str
    category: str
    category_disposition: str
    category_evidence_fingerprint: str
    resource_reference: BlueprintResourceReference | None
    rationale: str

    def __post_init__(self) -> None:
        if self.category not in RESOURCE_CATEGORIES:
            raise SoftwareBlueprintReadinessError(f"unknown resource category: {self.category}")
        if self.category_disposition not in RESOURCE_DISPOSITIONS:
            raise SoftwareBlueprintReadinessError("unknown resource disposition")
        if not self.member_id or not self.category_evidence_fingerprint or not self.rationale.strip():
            raise SoftwareBlueprintReadinessError("resource member identity is incomplete")
        if self.category_disposition == "blocked":
            if self.resource_reference is not None:
                raise SoftwareBlueprintReadinessError(
                    "blocked category member cannot claim a canonical resource reference"
                )
            return
        if self.resource_reference is None:
            raise SoftwareBlueprintReadinessError(
                "non-blocked category member requires the canonical resource reference"
            )
        if self.member_id != self.resource_reference.resource_id:
            raise SoftwareBlueprintReadinessError(
                "resource category member identity must equal the canonical resource identity"
            )
        if self.category_disposition != self.resource_reference.disposition:
            raise SoftwareBlueprintReadinessError(
                "resource category disposition must preserve the canonical lifecycle disposition"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "category": self.category,
            "category_disposition": self.category_disposition,
            "category_evidence_fingerprint": self.category_evidence_fingerprint,
            "resource_reference": (
                self.resource_reference.to_dict() if self.resource_reference else None
            ),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ProjectResourceInventory:
    inventory_id: str
    boundary_fingerprint: str
    members: tuple[ProjectResourceMember, ...]
    discovery_fingerprints: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.inventory_id or not self.boundary_fingerprint:
            raise SoftwareBlueprintReadinessError("resource inventory identity is incomplete")
        object.__setattr__(self, "members", tuple(sorted(self.members, key=lambda row: row.member_id)))
        ids = tuple(row.member_id for row in self.members)
        if len(ids) != len(set(ids)):
            raise SoftwareBlueprintReadinessError("resource inventory contains duplicate members")
        object.__setattr__(self, "discovery_fingerprints", _pairs(self.discovery_fingerprints))
        if not self.discovery_fingerprints:
            raise SoftwareBlueprintReadinessError("resource inventory requires independent discovery evidence")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    @property
    def complete(self) -> bool:
        return set(row.category for row in self.members) == set(RESOURCE_CATEGORIES) and all(
            row.category_disposition != "blocked" for row in self.members
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RESOURCE_INVENTORY_SCHEMA,
            "inventory_id": self.inventory_id,
            "boundary_fingerprint": self.boundary_fingerprint,
            "members": [row.to_dict() for row in self.members],
            "discovery_fingerprints": dict(self.discovery_fingerprints),
        }


@dataclass(frozen=True)
class ProjectIntentContribution:
    contribution_id: str
    source_kind: str
    source_id: str
    source_fingerprint: str
    disposition: str
    target_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if self.disposition not in INTENT_DISPOSITIONS:
            raise SoftwareBlueprintReadinessError("unknown intent disposition")
        if not all((self.contribution_id, self.source_kind, self.source_id, self.source_fingerprint)):
            raise SoftwareBlueprintReadinessError("intent contribution identity is incomplete")
        if not self.rationale.strip():
            raise SoftwareBlueprintReadinessError("intent contribution requires rationale")
        object.__setattr__(self, "target_ids", _tuple(self.target_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contribution_id": self.contribution_id,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_fingerprint": self.source_fingerprint,
            "disposition": self.disposition,
            "target_ids": list(self.target_ids),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class NoDeclaredIntentRationale:
    rationale_id: str
    evidence_fingerprints: tuple[tuple[str, str], ...]
    rationale: str

    def __post_init__(self) -> None:
        if not self.rationale_id or not self.rationale.strip():
            raise SoftwareBlueprintReadinessError("no-intent rationale identity is incomplete")
        object.__setattr__(self, "evidence_fingerprints", _pairs(self.evidence_fingerprints))
        if not self.evidence_fingerprints:
            raise SoftwareBlueprintReadinessError("no-intent rationale requires evidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rationale_id": self.rationale_id,
            "evidence_fingerprints": dict(self.evidence_fingerprints),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ProjectIntentInventory:
    inventory_id: str
    subject_revision: str
    canonical_review_fingerprint: str
    contributions: tuple[ProjectIntentContribution, ...]
    no_declared_intent: NoDeclaredIntentRationale | None = None

    def __post_init__(self) -> None:
        if not (
            self.inventory_id
            and self.subject_revision
            and self.canonical_review_fingerprint
        ):
            raise SoftwareBlueprintReadinessError("intent inventory identity is incomplete")
        object.__setattr__(
            self,
            "contributions",
            tuple(sorted(self.contributions, key=lambda row: row.contribution_id)),
        )
        ids = tuple(row.contribution_id for row in self.contributions)
        if len(ids) != len(set(ids)):
            raise SoftwareBlueprintReadinessError("intent inventory contains duplicate contributions")
        if self.contributions and self.no_declared_intent is not None:
            raise SoftwareBlueprintReadinessError("intent contributions and no-intent rationale are exclusive")

    @property
    def complete(self) -> bool:
        if self.contributions:
            return all(row.disposition != "blocked" for row in self.contributions)
        return self.no_declared_intent is not None

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INTENT_INVENTORY_SCHEMA,
            "inventory_id": self.inventory_id,
            "subject_revision": self.subject_revision,
            "canonical_review_fingerprint": self.canonical_review_fingerprint,
            "contributions": [row.to_dict() for row in self.contributions],
            "no_declared_intent": (
                self.no_declared_intent.to_dict() if self.no_declared_intent else None
            ),
        }


@dataclass(frozen=True)
class BehaviorBlueprintReport:
    inventory_fingerprint: str
    required_behavior_surface_ids: tuple[str, ...]
    supporting_surface_ids: tuple[str, ...]
    contracts: tuple[BehaviorBlockContract, ...]
    portable_bindings: tuple[PortableBehaviorBinding, ...]
    case_contracts: tuple[BehaviorCaseContract, ...]
    supporting_relations: tuple[SupportingSurfaceRelation, ...]
    coverage_edges: tuple[BehaviorCoverageEdge, ...]
    coverage_execution_evidence: tuple[CoverageExecutionEvidence, ...]
    test_node_dispositions: tuple[ProjectTestNodeDisposition, ...]
    findings: tuple[ReadinessFinding, ...]
    owner_structure_status: str
    behavior_closure_status: str

    def __post_init__(self) -> None:
        for name in ("owner_structure_status", "behavior_closure_status"):
            if getattr(self, name) not in {"complete", "incomplete", "stale", "blocked"}:
                raise SoftwareBlueprintReadinessError("invalid behavior blueprint status")
        for name in ("required_behavior_surface_ids", "supporting_surface_ids"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        object.__setattr__(self, "contracts", tuple(sorted(self.contracts, key=lambda row: row.behavior_block_id)))
        object.__setattr__(self, "portable_bindings", tuple(sorted(self.portable_bindings, key=lambda row: row.binding_id)))
        object.__setattr__(self, "case_contracts", tuple(sorted(self.case_contracts, key=lambda row: row.case_id)))
        object.__setattr__(self, "supporting_relations", tuple(sorted(self.supporting_relations, key=lambda row: row.supporting_surface_id)))
        object.__setattr__(self, "coverage_edges", tuple(sorted(self.coverage_edges, key=lambda row: row.coverage_id)))
        object.__setattr__(self, "coverage_execution_evidence", tuple(sorted(self.coverage_execution_evidence, key=lambda row: row.coverage_id)))
        object.__setattr__(self, "test_node_dispositions", tuple(sorted(self.test_node_dispositions, key=lambda row: row.test_node_id)))
        object.__setattr__(self, "findings", tuple(self.findings))

    @cached_property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    @property
    def complete(self) -> bool:
        return self.owner_structure_status == "complete" and self.behavior_closure_status == "complete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BEHAVIOR_BLUEPRINT_SCHEMA,
            "inventory_fingerprint": self.inventory_fingerprint,
            "required_behavior_surface_ids": list(self.required_behavior_surface_ids),
            "supporting_surface_ids": list(self.supporting_surface_ids),
            "contracts": [row.to_dict() for row in self.contracts],
            "portable_bindings": [row.to_dict() for row in self.portable_bindings],
            "case_contracts": [row.to_dict() for row in self.case_contracts],
            "supporting_relations": [row.to_dict() for row in self.supporting_relations],
            "coverage_edges": [row.to_dict() for row in self.coverage_edges],
            "coverage_execution_evidence": [row.to_dict() for row in self.coverage_execution_evidence],
            "test_node_dispositions": [row.to_dict() for row in self.test_node_dispositions],
            "findings": [row.to_dict() for row in self.findings],
            "owner_structure_status": self.owner_structure_status,
            "behavior_closure_status": self.behavior_closure_status,
        }


def _status(findings: Sequence[ReadinessFinding]) -> str:
    severities = {row.severity for row in findings}
    if "blocked" in severities:
        return "blocked"
    if "stale" in severities:
        return "stale"
    if findings:
        return "incomplete"
    return "complete"


def review_behavior_blueprint(
    *,
    inventory_fingerprint: str,
    required_behavior_surface_ids: Sequence[str],
    supporting_surface_ids: Sequence[str],
    contracts: Sequence[BehaviorBlockContract],
    portable_bindings: Sequence[PortableBehaviorBinding],
    case_contracts: Sequence[BehaviorCaseContract],
    supporting_relations: Sequence[SupportingSurfaceRelation],
    coverage_edges: Sequence[BehaviorCoverageEdge],
    coverage_execution_evidence: Sequence[CoverageExecutionEvidence],
    test_node_dispositions: Sequence[ProjectTestNodeDisposition],
    required_test_node_ids: Sequence[str],
    test_nodes: Sequence[Any] = (),
    native_member_fingerprints: Mapping[str, str] | None = None,
    planned_checker_fingerprints: Mapping[str, str] | None = None,
    delegated_assertion_helpers: Sequence[DelegatedAssertionHelper] = (),
    delegated_helper_fingerprints: Mapping[str, str] | None = None,
    expected_portable_fingerprints: Mapping[str, str] | None = None,
    expected_portable_members: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    supporting_surface_fingerprints: Mapping[str, str] | None = None,
) -> BehaviorBlueprintReport:
    """Check exact behavior, helper, coverage, and test-node denominators."""

    required = set(required_behavior_surface_ids)
    supporting = set(supporting_surface_ids)
    findings: list[ReadinessFinding] = []
    contract_by_surface: dict[str, list[BehaviorBlockContract]] = {}
    contract_by_id: dict[str, BehaviorBlockContract] = {}
    for contract in contracts:
        contract_by_surface.setdefault(contract.implementation_surface_id, []).append(contract)
        if contract.behavior_block_id in contract_by_id:
            findings.append(ReadinessFinding("duplicate_behavior_block", "behavior block id has more than one owner", (contract.behavior_block_id,), "blocked"))
        contract_by_id[contract.behavior_block_id] = contract
    missing = sorted(required - set(contract_by_surface))
    if missing:
        findings.append(ReadinessFinding("behavior_contract_missing", "behavior-bearing surfaces lack exact contracts", tuple(missing)))
    duplicates = sorted(key for key, values in contract_by_surface.items() if len(values) != 1)
    if duplicates:
        findings.append(ReadinessFinding("duplicate_behavior_owner", "behavior-bearing surfaces have duplicate contracts", tuple(duplicates), "blocked"))
    unresolved = sorted(contract.implementation_surface_id for contract in contracts if not contract.accepted)
    if unresolved:
        findings.append(ReadinessFinding("behavior_contract_unaccepted", "candidate/source-derived behavior contracts are not accepted", tuple(unresolved)))
    circular = sorted(
        contract.implementation_surface_id
        for contract in contracts
        if contract.accepted
        and contract.acceptance_evidence_fingerprints
        and all(
            role.startswith("source-observation")
            for role, _fingerprint_value in contract.acceptance_evidence_fingerprints
        )
    )
    if circular:
        findings.append(
            ReadinessFinding(
                "same_source_semantic_oracle_circularity",
                "implementation source is the sole semantic and oracle basis",
                tuple(circular),
            )
        )
    unlicensed_dimensions = tuple(
        f"{contract.behavior_block_id}:{dimension.dimension}"
        for contract in contracts
        for dimension in contract.dimensions
        if "missing-independent-owner-rule" in dimension.semantics
    )
    if unlicensed_dimensions:
        findings.append(
            ReadinessFinding(
                "behavior_dimension_semantic_missing",
                "observed behavior dimension lacks an independent owner rule",
                unlicensed_dimensions,
            )
        )

    signature_groups: dict[tuple[tuple[str, str, str], ...], list[BehaviorBlockContract]] = {}
    for contract in contracts:
        signature = tuple(
            (row.dimension, row.disposition, row.semantics)
            for row in contract.dimensions
        )
        signature_groups.setdefault(signature, []).append(contract)
    generic_reuse: list[str] = []
    for rows in signature_groups.values():
        if len(rows) < 2:
            continue
        surface_ids = {row.implementation_surface_id for row in rows}
        for contract in rows:
            if any(
                not surface_ids.issubset(set(dimension.applicability_surface_ids))
                for dimension in contract.dimensions
            ):
                generic_reuse.extend(row.behavior_block_id for row in rows)
                break
    if generic_reuse:
        findings.append(
            ReadinessFinding(
                "generic_semantics_reused_across_blocks",
                "identical behavior semantics lack one explicit shared rule and exact applicability set",
                tuple(generic_reuse),
            )
        )

    portable_by_id: dict[str, PortableBehaviorBinding] = {}
    portable_by_block: dict[str, list[PortableBehaviorBinding]] = {}
    expected_portable = dict(expected_portable_fingerprints or {})
    expected_members = {
        str(model_id): {
            str(kind): {str(member_id) for member_id in member_ids}
            for kind, member_ids in dict(catalog).items()
        }
        for model_id, catalog in dict(expected_portable_members or {}).items()
    }
    for binding in portable_bindings:
        if binding.binding_id in portable_by_id:
            findings.append(
                ReadinessFinding(
                    "duplicate_portable_behavior_binding",
                    "portable behavior binding id is duplicated",
                    (binding.binding_id,),
                    "blocked",
                )
            )
        portable_by_id[binding.binding_id] = binding
        portable_by_block.setdefault(binding.behavior_block_id, []).append(binding)
        expected = expected_portable.get(binding.portable_model_id)
        if expected is not None and expected != binding.portable_model_fingerprint:
            findings.append(
                ReadinessFinding(
                    "portable_behavior_binding_stale",
                    "portable behavior binding does not match current model authority",
                    (binding.binding_id,),
                    "stale",
                )
            )
        catalog = expected_members.get(binding.portable_model_id)
        if expected_members and catalog is None:
            findings.append(
                ReadinessFinding(
                    "portable_member_catalog_missing",
                    "portable binding has no independent current member catalog",
                    (binding.portable_model_id,),
                    "blocked",
                )
            )
        if catalog is not None:
            actual_members = {
                "transition_ids": set(binding.transition_ids),
                "property_ids": set(binding.property_ids),
                "invariant_ids": set(binding.invariant_ids),
                "input_field_ids": {
                    member_id for _field, member_id in binding.input_field_mappings
                },
                "output_field_ids": {
                    member_id for _field, member_id in binding.output_field_mappings
                },
                "state_field_ids": {
                    member_id for _field, member_id in binding.state_field_mappings
                },
                "assumption_ids": set(binding.assumption_ids),
                "guarantee_ids": set(binding.guarantee_ids),
            }
            for member_kind, actual_ids in actual_members.items():
                declared_ids = catalog.get(member_kind, set())
                unknown_ids = actual_ids - declared_ids
                missing_ids = declared_ids - actual_ids
                if unknown_ids:
                    findings.append(
                        ReadinessFinding(
                            "portable_member_unknown",
                            "portable binding references members absent from the exact model catalog",
                            tuple(sorted(unknown_ids)),
                            "blocked",
                        )
                    )
                if missing_ids:
                    findings.append(
                        ReadinessFinding(
                            "portable_member_unbound",
                            "declared portable members are not bound to the behavior block",
                            tuple(sorted(missing_ids)),
                        )
                    )
    for contract in contracts:
        rows = portable_by_block.get(contract.behavior_block_id, ())
        observed_ids = {row.binding_id for row in rows}
        if not rows or set(contract.portable_binding_ids) != observed_ids:
            findings.append(
                ReadinessFinding(
                    "portable_behavior_binding_missing",
                    "behavior block lacks its exact declared portable binding inventory",
                    (contract.behavior_block_id,),
                )
            )
        elif any(
            row.implementation_fingerprint != contract.source_fingerprint
            for row in rows
        ):
            findings.append(
                ReadinessFinding(
                    "portable_implementation_binding_stale",
                    "portable behavior binding targets another implementation fingerprint",
                    (contract.behavior_block_id,),
                    "stale",
                )
            )
        elif any(
            set(row.protected_failure_ids) != set(contract.protected_failure_ids)
            for row in rows
        ):
            findings.append(
                ReadinessFinding(
                    "portable_failure_boundary_mismatch",
                    "portable behavior binding does not preserve the exact protected failures",
                    (contract.behavior_block_id,),
                    "blocked",
                )
            )

    case_by_id: dict[str, BehaviorCaseContract] = {}
    cases_by_block: dict[str, list[BehaviorCaseContract]] = {}
    for case in case_contracts:
        if case.case_id in case_by_id:
            findings.append(
                ReadinessFinding(
                    "duplicate_behavior_case",
                    "behavior case id is duplicated",
                    (case.case_id,),
                    "blocked",
                )
            )
        case_by_id[case.case_id] = case
        cases_by_block.setdefault(case.behavior_block_id, []).append(case)
    for contract in contracts:
        rows = cases_by_block.get(contract.behavior_block_id, ())
        kinds = {row.case_kind for row in rows}
        if not {"good", "boundary"}.issubset(kinds):
            findings.append(
                ReadinessFinding(
                    "behavior_case_design_missing",
                    "behavior block requires concrete good and boundary case contracts",
                    (contract.behavior_block_id,),
                )
            )
        covered_failures = {
            failure_id
            for row in rows
            if row.case_kind == "bad"
            for failure_id in row.protected_failure_ids
        }
        missing_failures = set(contract.protected_failure_ids) - covered_failures
        if missing_failures:
            findings.append(
                ReadinessFinding(
                    "protected_failure_case_missing",
                    "protected failures lack exact bad-case contracts",
                    tuple(sorted(missing_failures)),
                )
            )

    relation_by_surface: dict[str, list[SupportingSurfaceRelation]] = {}
    for relation in supporting_relations:
        relation_by_surface.setdefault(relation.supporting_surface_id, []).append(relation)
        if relation.behavior_block_id not in contract_by_id:
            findings.append(ReadinessFinding("supporting_owner_missing", "supporting surface points to an unknown behavior block", (relation.supporting_surface_id,), "blocked"))
        expected_fingerprint = dict(supporting_surface_fingerprints or {}).get(
            relation.supporting_surface_id
        )
        if expected_fingerprint is not None and expected_fingerprint != relation.evidence_fingerprint:
            findings.append(
                ReadinessFinding(
                    "supporting_ownership_edge_stale",
                    "supporting ownership evidence does not match the current surface",
                    (relation.supporting_surface_id,),
                    "stale",
                )
            )
    orphan = sorted(supporting - set(relation_by_surface))
    if orphan:
        findings.append(ReadinessFinding("orphan_supporting_surface", "supporting surfaces lack one behavior owner", tuple(orphan)))
    multi = sorted(key for key, values in relation_by_surface.items() if len(values) != 1)
    if multi:
        findings.append(ReadinessFinding("duplicate_supporting_owner", "supporting surfaces have more than one behavior owner", tuple(multi), "blocked"))

    coverage_by_block: dict[str, set[str]] = {}
    coverage_ids: set[str] = set()
    test_node_by_id = {str(row.node_id): row for row in test_nodes}
    oracle_member_owner: dict[str, str] = {}
    oracle_member_fingerprints = dict(native_member_fingerprints or {})
    for member_id, member_fingerprint in dict(
        planned_checker_fingerprints or {}
    ).items():
        current = oracle_member_fingerprints.get(str(member_id))
        if current is not None and current != str(member_fingerprint):
            findings.append(
                ReadinessFinding(
                    "planned_checker_identity_conflict",
                    "planned checker identity conflicts with a current evidence member",
                    (str(member_id),),
                    "blocked",
                )
            )
        oracle_member_fingerprints[str(member_id)] = str(member_fingerprint)
    for node in test_nodes:
        for assertion in node.assertions:
            oracle_member_owner[str(assertion.assertion_id)] = str(node.node_id)
            oracle_member_fingerprints[str(assertion.assertion_id)] = str(
                assertion.structure_fingerprint
            )
    helper_by_id: dict[str, DelegatedAssertionHelper] = {}
    helper_expected = dict(delegated_helper_fingerprints or {})
    for helper in delegated_assertion_helpers:
        if helper.helper_id in helper_by_id:
            findings.append(
                ReadinessFinding(
                    "duplicate_delegated_assertion_helper",
                    "delegated assertion helper id is duplicated",
                    (helper.helper_id,),
                    "blocked",
                )
            )
        helper_by_id[helper.helper_id] = helper
        expected = helper_expected.get(helper.helper_id)
        if expected is not None and expected != helper.source_fingerprint:
            findings.append(
                ReadinessFinding(
                    "delegated_assertion_helper_stale",
                    "delegated assertion helper source fingerprint is stale",
                    (helper.helper_id,),
                    "stale",
                )
            )
        for terminal_id, terminal_fingerprint in helper.terminal_member_fingerprints:
            current_terminal = oracle_member_fingerprints.get(terminal_id)
            if current_terminal is not None and current_terminal != terminal_fingerprint:
                findings.append(
                    ReadinessFinding(
                        "delegated_assertion_terminal_stale",
                        "delegated helper terminal member conflicts with current evidence",
                        (helper.helper_id, terminal_id),
                        "stale",
                    )
                )
            else:
                oracle_member_fingerprints[terminal_id] = terminal_fingerprint

    terminal_member_ids = set(oracle_member_fingerprints)
    helper_state: dict[str, bool] = {}

    def helper_reaches_terminal(helper_id: str, stack: tuple[str, ...] = ()) -> bool:
        if helper_id in helper_state:
            return helper_state[helper_id]
        if helper_id in stack:
            findings.append(
                ReadinessFinding(
                    "delegated_assertion_helper_cycle",
                    "delegated assertion helper call graph contains a cycle",
                    stack + (helper_id,),
                    "blocked",
                )
            )
            helper_state[helper_id] = False
            return False
        helper = helper_by_id[helper_id]
        reaches_terminal = False
        valid = True
        for callee_id in helper.callee_member_ids:
            if callee_id in terminal_member_ids:
                reaches_terminal = True
            elif callee_id in helper_by_id:
                child_ok = helper_reaches_terminal(
                    callee_id, stack + (helper_id,)
                )
                reaches_terminal = reaches_terminal or child_ok
                valid = valid and child_ok
            else:
                findings.append(
                    ReadinessFinding(
                        "delegated_assertion_terminal_missing",
                        "delegated assertion helper reaches an unknown member",
                        (helper_id, callee_id),
                        "blocked",
                    )
                )
                valid = False
        helper_state[helper_id] = valid and reaches_terminal
        return helper_state[helper_id]

    for helper_id, helper in helper_by_id.items():
        if helper_reaches_terminal(helper_id):
            oracle_member_fingerprints[helper_id] = helper.source_fingerprint
            oracle_member_owner[helper_id] = helper.test_node_id

    registered_helper_names = {
        name
        for helper_id in helper_by_id
        for name in (helper_id, helper_id.rsplit(".", 1)[-1])
    }
    unregistered_assert_helpers = tuple(
        sorted(
            {
                call
                for node in test_nodes
                for call in getattr(node, "calls", ())
                if call.rsplit(".", 1)[-1].startswith("assert_")
                and call.rsplit(".", 1)[-1] not in TERMINAL_ASSERTION_CALL_NAMES
                and call not in registered_helper_names
                and call.rsplit(".", 1)[-1] not in registered_helper_names
            }
        )
    )
    if unregistered_assert_helpers:
        findings.append(
            ReadinessFinding(
                "unregistered_assertion_helper",
                "assert-like helper calls require an explicit current delegation graph",
                unregistered_assert_helpers,
            )
        )
    checker_scopes: dict[str, set[tuple[str, str]]] = {}
    case_evidence_scopes: dict[str, set[tuple[str, str]]] = {}
    parameter_case_ids_by_node = {
        str(node.node_id): {
            str(case_id)
            for marker in getattr(node, "parameterization_markers", ())
            for case_id in getattr(marker, "case_ids", ())
        }
        for node in test_nodes
    }
    for row in coverage_edges:
        if row.coverage_id in coverage_ids:
            findings.append(ReadinessFinding("duplicate_coverage_id", "behavior coverage id is duplicated", (row.coverage_id,), "blocked"))
        coverage_ids.add(row.coverage_id)
        if row.behavior_block_id not in contract_by_id:
            findings.append(ReadinessFinding("coverage_behavior_missing", "coverage references an unknown behavior block", (row.coverage_id,), "blocked"))
            continue
        if row.implementation_surface_id != contract_by_id[row.behavior_block_id].implementation_surface_id:
            findings.append(ReadinessFinding("false_surface_coverage", "coverage surface differs from its behavior contract", (row.coverage_id,), "blocked"))
        contract = contract_by_id[row.behavior_block_id]
        if row.semantic_spec_id not in contract.semantic_spec_ids:
            findings.append(ReadinessFinding("coverage_semantic_mismatch", "coverage references another semantic specification", (row.coverage_id,), "blocked"))
        if row.oracle_id not in contract.oracle_ids:
            findings.append(ReadinessFinding("coverage_oracle_mismatch", "coverage references another behavior oracle", (row.coverage_id,), "blocked"))
        case = case_by_id.get(row.case_id)
        if case is None or case.behavior_block_id != row.behavior_block_id:
            findings.append(ReadinessFinding("coverage_case_missing", "coverage references no exact case for its behavior block", (row.coverage_id,), "blocked"))
        elif case.oracle_id != row.oracle_id:
            findings.append(ReadinessFinding("coverage_case_oracle_mismatch", "coverage case and edge use different oracles", (row.coverage_id,), "blocked"))
        elif case.case_evidence_id not in oracle_member_fingerprints:
            findings.append(
                ReadinessFinding(
                    "case_evidence_member_missing",
                    "behavior case references no current assertion or native-check member",
                    (case.case_id,),
                    "blocked",
                )
            )
        elif (
            oracle_member_fingerprints[case.case_evidence_id]
            != case.case_evidence_fingerprint
        ):
            findings.append(
                ReadinessFinding(
                    "case_evidence_member_stale",
                    "behavior case evidence fingerprint is stale",
                    (case.case_id,),
                    "stale",
                )
            )
        if case is not None:
            case_evidence_scopes.setdefault(case.case_evidence_id, set()).add(
                (case.case_id, case.parameter_case_id)
            )
            if row.evidence_role == "planned_checker":
                if case.parameter_case_id != case.case_id:
                    findings.append(
                        ReadinessFinding(
                            "planned_checker_parameter_case_missing",
                            "planned checker case lacks its exact parameter-case identity",
                            (case.case_id,),
                            "blocked",
                        )
                    )
            elif case.parameter_case_id:
                declared_parameter_cases = parameter_case_ids_by_node.get(
                    row.test_node_id, set()
                )
                if (
                    declared_parameter_cases
                    and case.parameter_case_id not in declared_parameter_cases
                ):
                    findings.append(
                        ReadinessFinding(
                            "coverage_parameter_case_missing",
                            "coverage names a parameter case absent from its current test node",
                            (row.coverage_id, case.parameter_case_id),
                            "blocked",
                        )
                    )
        member_fingerprint = oracle_member_fingerprints.get(row.oracle_member_id)
        if member_fingerprint is None:
            findings.append(ReadinessFinding("coverage_oracle_member_missing", "coverage references no real assertion or native-check member", (row.coverage_id,), "blocked"))
        elif member_fingerprint != row.oracle_member_fingerprint:
            findings.append(ReadinessFinding("coverage_oracle_member_stale", "coverage oracle member fingerprint is stale", (row.coverage_id,), "stale"))
        member_owner = oracle_member_owner.get(row.oracle_member_id)
        if member_owner is not None and member_owner != row.test_node_id:
            findings.append(ReadinessFinding("coverage_cross_test_member", "assertion belongs to another test node", (row.coverage_id,), "blocked"))
        if row.test_node_id not in test_node_by_id and row.test_node_id not in dict(native_member_fingerprints or {}):
            findings.append(ReadinessFinding("coverage_test_node_missing", "coverage references no real test node or native check", (row.coverage_id,), "blocked"))
        if len(row.covered_dimensions) != 1:
            findings.append(
                ReadinessFinding(
                    "coverage_dimension_scope_ambiguous",
                    "one checker edge must own exactly one behavior dimension",
                    (row.coverage_id,),
                    "blocked",
                )
            )
        for dimension in row.covered_dimensions:
            checker_scopes.setdefault(row.oracle_member_id, set()).add(
                (row.case_id, dimension)
            )
        coverage_by_block.setdefault(row.behavior_block_id, set()).update(row.covered_dimensions)
    reused_checkers = tuple(
        sorted(
            checker_id
            for checker_id, scopes in checker_scopes.items()
            if len(scopes) > 1
        )
    )
    if reused_checkers:
        findings.append(
            ReadinessFinding(
                "checker_scope_ambiguous",
                "one checker member is reused across distinct case or dimension scopes",
                reused_checkers,
                "blocked",
            )
        )
    ambiguous_case_evidence = tuple(
        sorted(
            evidence_id
            for evidence_id, scopes in case_evidence_scopes.items()
            if len(scopes) > 1
            and not all(parameter_case_id for _case_id, parameter_case_id in scopes)
        )
    )
    if ambiguous_case_evidence:
        findings.append(
            ReadinessFinding(
                "case_checker_scope_ambiguous",
                "one case checker is reused without exact parameter-case identities",
                ambiguous_case_evidence,
                "blocked",
            )
        )
    uncovered: list[str] = []
    for contract in contracts:
        missing_dimensions = set(BEHAVIOR_DIMENSIONS) - coverage_by_block.get(contract.behavior_block_id, set())
        uncovered.extend(f"{contract.behavior_block_id}:{dimension}" for dimension in sorted(missing_dimensions))
    if uncovered:
        findings.append(ReadinessFinding("behavior_test_design_missing", "behavior blocks lack exact dimension-level checker designs", tuple(uncovered)))

    execution_by_coverage: dict[str, list[CoverageExecutionEvidence]] = {}
    for row in coverage_execution_evidence:
        execution_by_coverage.setdefault(row.coverage_id, []).append(row)
        if row.coverage_id not in coverage_ids:
            findings.append(ReadinessFinding("execution_unknown_coverage", "execution evidence references unknown coverage", (row.coverage_id,), "blocked"))
    missing_execution = sorted(coverage_ids - set(execution_by_coverage))
    if missing_execution:
        findings.append(ReadinessFinding("coverage_execution_disposition_missing", "formal coverage edges lack explicit execution disposition", tuple(missing_execution)))
    duplicate_execution = sorted(key for key, values in execution_by_coverage.items() if len(values) != 1)
    if duplicate_execution:
        findings.append(ReadinessFinding("coverage_execution_duplicate", "coverage edges have duplicate execution dispositions", tuple(duplicate_execution), "blocked"))

    disposition_by_node: dict[str, list[ProjectTestNodeDisposition]] = {}
    for row in test_node_dispositions:
        disposition_by_node.setdefault(row.test_node_id, []).append(row)
        unknown = set(row.coverage_ids) - coverage_ids
        if unknown:
            findings.append(ReadinessFinding("test_disposition_unknown_coverage", "test disposition references unknown coverage", tuple(sorted(unknown)), "blocked"))
    missing_nodes = sorted(set(required_test_node_ids) - set(disposition_by_node))
    if missing_nodes:
        findings.append(ReadinessFinding("test_node_unbound", "required project test nodes lack terminal disposition", tuple(missing_nodes)))
    duplicate_nodes = sorted(key for key, values in disposition_by_node.items() if len(values) != 1)
    if duplicate_nodes:
        findings.append(ReadinessFinding("test_node_duplicate_disposition", "test nodes have multiple dispositions", tuple(duplicate_nodes), "blocked"))
    blocked_nodes = sorted(row.test_node_id for row in test_node_dispositions if row.disposition == "blocked")
    if blocked_nodes:
        findings.append(ReadinessFinding("test_node_blocked", "required project test nodes remain blocked", tuple(blocked_nodes), "blocked"))

    behavior_status = _status(findings)
    return BehaviorBlueprintReport(
        inventory_fingerprint=inventory_fingerprint,
        required_behavior_surface_ids=tuple(required_behavior_surface_ids),
        supporting_surface_ids=tuple(supporting_surface_ids),
        contracts=tuple(contracts),
        portable_bindings=tuple(portable_bindings),
        case_contracts=tuple(case_contracts),
        supporting_relations=tuple(supporting_relations),
        coverage_edges=tuple(coverage_edges),
        coverage_execution_evidence=tuple(coverage_execution_evidence),
        test_node_dispositions=tuple(test_node_dispositions),
        findings=tuple(findings),
        owner_structure_status=("blocked" if any(row.severity == "blocked" and row.code in {"duplicate_behavior_owner", "duplicate_supporting_owner"} for row in findings) else "complete"),
        behavior_closure_status=behavior_status,
    )


@dataclass(frozen=True)
class StaticBlueprintReadinessReport:
    blueprint_fingerprint: str
    behavior_report_fingerprint: str
    resource_inventory_fingerprint: str
    intent_inventory_fingerprint: str
    topology_fingerprint: str
    normalized_projection_fingerprint: str
    status: str
    deepest_proven_layer: str
    first_gap: str
    findings: tuple[ReadinessFinding, ...]

    def __post_init__(self) -> None:
        if self.status not in READINESS_STATUSES:
            raise SoftwareBlueprintReadinessError("invalid static blueprint readiness status")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STATIC_BLUEPRINT_READINESS_SCHEMA,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "behavior_report_fingerprint": self.behavior_report_fingerprint,
            "resource_inventory_fingerprint": self.resource_inventory_fingerprint,
            "intent_inventory_fingerprint": self.intent_inventory_fingerprint,
            "topology_fingerprint": self.topology_fingerprint,
            "normalized_projection_fingerprint": self.normalized_projection_fingerprint,
            "status": self.status,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_gap": self.first_gap,
            "gap_count": len(self.findings),
            "findings": [row.to_dict() for row in self.findings],
            "claim_boundary": (
                "This is a pure static blueprint-readiness decision; it does not execute "
                "providers, validators, or target-system actions."
            ),
        }


def review_static_blueprint_readiness(
    *,
    blueprint_fingerprint: str,
    behavior_report: BehaviorBlueprintReport,
    resource_inventory: ProjectResourceInventory,
    intent_inventory: ProjectIntentInventory,
    topology_fingerprint: str,
    normalized_projection_fingerprint: str,
    expected_identities: Mapping[str, str] | None = None,
    topology_findings: Sequence[ReadinessFinding] = (),
) -> StaticBlueprintReadinessReport:
    """Return every known static blueprint gap without executing external work."""

    findings = list(behavior_report.findings)
    findings.extend(topology_findings)
    if not resource_inventory.complete:
        missing_categories = set(RESOURCE_CATEGORIES) - {row.category for row in resource_inventory.members}
        blocked = {row.member_id for row in resource_inventory.members if row.category_disposition == "blocked"}
        findings.append(ReadinessFinding("resource_inventory_incomplete", "resource denominator is missing or blocked", tuple(sorted(missing_categories | blocked)), "blocked" if blocked else "incomplete"))
    if not intent_inventory.complete:
        findings.append(ReadinessFinding("intent_inventory_incomplete", "current intent lineage has no terminal contribution or evidence-bound no-intent rationale", (intent_inventory.inventory_id,)))
    if not topology_fingerprint:
        findings.append(ReadinessFinding("topology_missing", "affected model topology fingerprint is missing"))
    if not normalized_projection_fingerprint:
        findings.append(ReadinessFinding("normalized_projection_missing", "canonical normalized projection fingerprint is missing"))
    current = {
        "behavior_report": behavior_report.fingerprint,
        "resource_inventory": resource_inventory.fingerprint,
        "intent_inventory": intent_inventory.fingerprint,
        "topology": topology_fingerprint,
        "normalized_projection": normalized_projection_fingerprint,
    }
    for identity, expected in sorted((expected_identities or {}).items()):
        if current.get(identity) != expected:
            findings.append(ReadinessFinding("readiness_identity_stale", f"{identity} does not match the expected current identity", (identity,), "stale"))
    status = _status(findings)
    if status == "complete":
        status = "ready"
    if behavior_report.owner_structure_status != "complete":
        deepest = "inventory"
    elif behavior_report.behavior_closure_status != "complete":
        deepest = "owner_structure"
    elif not resource_inventory.complete:
        deepest = "behavior_blocks"
    elif not intent_inventory.complete:
        deepest = "resource_inventory"
    else:
        deepest = "static_blueprint"
    first_gap = findings[0].code if findings else ""
    return StaticBlueprintReadinessReport(
        blueprint_fingerprint=blueprint_fingerprint,
        behavior_report_fingerprint=behavior_report.fingerprint,
        resource_inventory_fingerprint=resource_inventory.fingerprint,
        intent_inventory_fingerprint=intent_inventory.fingerprint,
        topology_fingerprint=topology_fingerprint,
        normalized_projection_fingerprint=normalized_projection_fingerprint,
        status=status,
        deepest_proven_layer=deepest,
        first_gap=first_gap,
        findings=tuple(findings),
    )


@dataclass(frozen=True)
class NormalizedBlueprintProjection:
    blueprint_fingerprint: str
    logical_fingerprint: str
    object_fingerprints: tuple[tuple[str, str], ...]
    shard_fingerprints: tuple[tuple[str, str], ...]
    shard_member_ids: tuple[tuple[str, tuple[str, ...]], ...]
    logical_bytes: int
    physical_bytes: int
    source_projection_bytes: int
    repeated_reference_bytes_avoided: int

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": NORMALIZED_PROJECTION_SCHEMA,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "object_fingerprints": dict(self.object_fingerprints),
            "shard_fingerprints": dict(self.shard_fingerprints),
            "shard_member_ids": {
                shard_id: list(member_ids)
                for shard_id, member_ids in self.shard_member_ids
            },
            "logical_bytes": self.logical_bytes,
            "physical_bytes": self.physical_bytes,
            "source_projection_bytes": self.source_projection_bytes,
            "repeated_reference_bytes_avoided": self.repeated_reference_bytes_avoided,
            "physical_to_source_ratio": (
                round(self.physical_bytes / self.source_projection_bytes, 6)
                if self.source_projection_bytes
                else 0.0
            ),
        }


def normalize_behavior_blueprint(
    *,
    blueprint_fingerprint: str,
    behavior_report: BehaviorBlueprintReport,
    shared_objects: Mapping[str, Any],
    shard_size: int = 256,
    source_projection: Any | None = None,
) -> NormalizedBlueprintProjection:
    """Store logical shared objects once and shard only reference rows."""

    if shard_size < 1:
        raise SoftwareBlueprintReadinessError("shard_size must be positive")
    object_rows = tuple(
        sorted((str(key), _fingerprint(value)) for key, value in shared_objects.items())
    )
    coverage = [row.to_dict() for row in behavior_report.coverage_edges]
    shard_rows: list[tuple[str, str]] = []
    shard_members: list[tuple[str, tuple[str, ...]]] = []
    for index in range(0, len(coverage), shard_size):
        members = coverage[index : index + shard_size]
        shard_id = f"coverage:{index // shard_size:05d}"
        shard_rows.append((shard_id, _fingerprint(members)))
        shard_members.append(
            (shard_id, tuple(str(member["coverage_id"]) for member in members))
        )
    del coverage
    logical_payload = {
        "behavior_report": behavior_report.to_dict(),
        "shared_objects": {key: shared_objects[key] for key, _value in object_rows},
    }
    logical_fingerprint, logical_bytes = _canonical_fingerprint_and_size(
        logical_payload
    )
    source_bytes = (
        logical_bytes
        if source_projection is None
        else _canonical_fingerprint_and_size(source_projection)[1]
    )
    del logical_payload
    physical_payload = {
        "contracts": [row.to_dict() for row in behavior_report.contracts],
        "portable_bindings": [row.to_dict() for row in behavior_report.portable_bindings],
        "case_contracts": [row.to_dict() for row in behavior_report.case_contracts],
        "supporting_relations": [row.to_dict() for row in behavior_report.supporting_relations],
        "coverage_execution_evidence": [
            row.to_dict() for row in behavior_report.coverage_execution_evidence
        ],
        "coverage_shards": dict(shard_rows),
        "coverage_shard_members": {
            shard_id: list(member_ids) for shard_id, member_ids in shard_members
        },
        "objects": dict(object_rows),
    }
    _physical_fingerprint, physical_bytes = _canonical_fingerprint_and_size(
        physical_payload
    )
    del physical_payload
    return NormalizedBlueprintProjection(
        blueprint_fingerprint=blueprint_fingerprint,
        logical_fingerprint=logical_fingerprint,
        object_fingerprints=object_rows,
        shard_fingerprints=tuple(shard_rows),
        shard_member_ids=tuple(shard_members),
        logical_bytes=logical_bytes,
        physical_bytes=physical_bytes,
        source_projection_bytes=source_bytes,
        repeated_reference_bytes_avoided=max(0, source_bytes - physical_bytes),
    )

@dataclass(frozen=True)
class AffectedBlueprintNeighborhood:
    logical_fingerprint: str
    behavior_block_ids: tuple[str, ...]
    implementation_surface_ids: tuple[str, ...]
    supporting_surface_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    test_node_ids: tuple[str, ...]
    shared_objects: tuple[tuple[str, Any], ...]
    shard_ids: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_fingerprint": self.logical_fingerprint,
            "behavior_block_ids": list(self.behavior_block_ids),
            "implementation_surface_ids": list(self.implementation_surface_ids),
            "supporting_surface_ids": list(self.supporting_surface_ids),
            "coverage_ids": list(self.coverage_ids),
            "test_node_ids": list(self.test_node_ids),
            "shared_objects": dict(self.shared_objects),
            "shard_ids": list(self.shard_ids),
        }


def load_affected_behavior_neighborhood(
    projection: NormalizedBlueprintProjection,
    behavior_report: BehaviorBlueprintReport,
    shared_objects: Mapping[str, Any],
    *,
    affected_surface_ids: Iterable[str] = (),
    affected_behavior_block_ids: Iterable[str] = (),
) -> AffectedBlueprintNeighborhood:
    """Load only behavior/reference shards reachable from the affected identities."""

    expected_objects = dict(projection.object_fingerprints)
    supplied_objects = {str(object_id): value for object_id, value in shared_objects.items()}
    surface_ids = {str(value) for value in affected_surface_ids}
    block_ids = {str(value) for value in affected_behavior_block_ids}
    for contract in behavior_report.contracts:
        if contract.implementation_surface_id in surface_ids:
            block_ids.add(contract.behavior_block_id)
    for relation in behavior_report.supporting_relations:
        if relation.supporting_surface_id in surface_ids:
            block_ids.add(relation.behavior_block_id)
    known_block_ids = {row.behavior_block_id for row in behavior_report.contracts}
    unknown = sorted(block_ids - known_block_ids)
    if unknown:
        raise SoftwareBlueprintReadinessError(
            "affected loading references unknown behavior blocks: " + ", ".join(unknown)
        )
    selected_contracts = tuple(
        row for row in behavior_report.contracts if row.behavior_block_id in block_ids
    )
    selected_relations = tuple(
        row
        for row in behavior_report.supporting_relations
        if row.behavior_block_id in block_ids
    )
    selected_coverage = tuple(
        row
        for row in behavior_report.coverage_edges
        if row.behavior_block_id in block_ids
    )
    coverage_ids = {row.coverage_id for row in selected_coverage}
    selected_dispositions = tuple(
        row
        for row in behavior_report.test_node_dispositions
        if set(row.coverage_ids) & coverage_ids
    )
    referenced_object_ids: set[str] = set()
    for row in selected_contracts:
        referenced_object_ids.update(row.semantic_spec_ids)
        referenced_object_ids.update(row.oracle_ids)
        referenced_object_ids.update(row.portable_binding_ids)
        referenced_object_ids.add(row.owner_id)
        referenced_object_ids.add(row.owner_contract_id)
        referenced_object_ids.add(
            f"topology-index:{row.model_element_id}"
        )
        referenced_object_ids.add(
            f"model-test-alignment-owner:{row.model_element_id}"
        )
    for row in selected_coverage:
        referenced_object_ids.update(
            {
                row.semantic_spec_id,
                row.oracle_id,
                row.test_node_id,
                row.oracle_member_id,
                row.case_id,
            }
        )
    for row in behavior_report.coverage_execution_evidence:
        if row.coverage_id in coverage_ids:
            referenced_object_ids.update(
                object_id
                for object_id in (row.receipt_id,)
                if object_id
            )
    referenced_object_ids.update(row.test_node_id for row in selected_dispositions)
    topology_index_ids = tuple(
        sorted(
            object_id
            for object_id in referenced_object_ids
            if object_id.startswith("topology-index:")
        )
    )
    for index_id in topology_index_ids:
        if index_id not in expected_objects or index_id not in supplied_objects:
            continue
        index_value = supplied_objects[index_id]
        if _fingerprint(index_value) != expected_objects[index_id]:
            continue
        if isinstance(index_value, Mapping):
            node_object_id = str(index_value.get("node_object_id", ""))
            if node_object_id:
                referenced_object_ids.add(node_object_id)
            referenced_object_ids.update(
                str(object_id)
                for object_id in index_value.get("relation_object_ids", ())
                if str(object_id)
            )
    required_object_ids = referenced_object_ids & set(expected_objects)
    missing = sorted(required_object_ids - set(supplied_objects))
    stale = sorted(
        object_id
        for object_id in required_object_ids & set(supplied_objects)
        if _fingerprint(supplied_objects[object_id]) != expected_objects[object_id]
    )
    if missing or stale:
        raise SoftwareBlueprintReadinessError(
            "affected loading requires exact current referenced objects: "
            + ", ".join((*missing, *stale))
        )
    selected_objects = tuple(
        (object_id, supplied_objects[object_id])
        for object_id in sorted(required_object_ids)
    )
    selected_shards = tuple(
        shard_id
        for shard_id, member_ids in projection.shard_member_ids
        if set(member_ids) & coverage_ids
    )
    return AffectedBlueprintNeighborhood(
        logical_fingerprint=projection.logical_fingerprint,
        behavior_block_ids=tuple(sorted(block_ids)),
        implementation_surface_ids=tuple(
            sorted(row.implementation_surface_id for row in selected_contracts)
        ),
        supporting_surface_ids=tuple(
            sorted(row.supporting_surface_id for row in selected_relations)
        ),
        coverage_ids=tuple(sorted(coverage_ids)),
        test_node_ids=tuple(sorted(row.test_node_id for row in selected_dispositions)),
        shared_objects=selected_objects,
        shard_ids=selected_shards,
    )


@dataclass(frozen=True)
class CandidateBlueprint:
    inventory_fingerprint: str
    target_kind: str
    observation_provider_ids: tuple[str, ...]
    behavior_contracts: tuple[BehaviorBlockContract, ...]
    unresolved_ids: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "blocked" if self.blockers else ("incomplete" if self.unresolved_ids else "ready")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CANDIDATE_BLUEPRINT_SCHEMA,
            "inventory_fingerprint": self.inventory_fingerprint,
            "target_kind": self.target_kind,
            "observation_provider_ids": list(self.observation_provider_ids),
            "behavior_contracts": [row.to_dict() for row in self.behavior_contracts],
            "unresolved_ids": list(self.unresolved_ids),
            "blockers": list(self.blockers),
            "status": self.status,
            "claim_boundary": (
                "Candidate discovery is read-only. Source-derived ownership and semantics remain "
                "unresolved until independently accepted."
            ),
        }


def generate_candidate_blueprint(
    implementation_inventory: Any,
    *,
    target_kind: str = "software",
    observation_provider_ids: Sequence[str] = (),
) -> CandidateBlueprint:
    """Create unresolved provider-derived behavior candidates for one target."""

    inventory_fingerprint = str(getattr(implementation_inventory, "inventory_fingerprint", ""))
    provider_ids = _tuple(
        tuple(observation_provider_ids)
        or tuple(
            str(getattr(surface, "discovery_adapter_id", ""))
            for surface in getattr(implementation_inventory, "surfaces", ())
            if str(getattr(surface, "discovery_adapter_id", ""))
        )
    )
    if not provider_ids:
        return CandidateBlueprint(
            inventory_fingerprint=inventory_fingerprint,
            target_kind=target_kind,
            observation_provider_ids=(),
            behavior_contracts=(),
            unresolved_ids=(),
            blockers=(
                f"missing observation provider for target kind: {target_kind}",
            ),
        )
    contracts: list[BehaviorBlockContract] = []
    for surface in getattr(implementation_inventory, "surfaces", ()):
        possible_behavior = bool(getattr(surface, "behavior_bearing", False)) or (
            str(getattr(surface, "surface_kind", ""))
            in {"class", "function", "method", "entrypoint"}
        )
        if not possible_behavior:
            continue
        surface_id = str(surface.surface_id)
        dimensions = tuple(
            BehaviorDimensionContract(
                dimension=dimension,
                disposition="modeled" if dimension in {"input", "output", "error", "completion"} else "not_applicable",
                semantics=(
                    f"candidate inferred from {surface.path}#{surface.symbol}; independent semantics required"
                ),
                rationale="source discovery can locate a possible behavior boundary but cannot accept it",
                provenance_fingerprints=(("source-observation", str(surface.content_fingerprint)),),
                semantic_rule_ids=(f"candidate-rule:{surface_id}:{dimension}",),
                applicability_surface_ids=(surface_id,),
            )
            for dimension in BEHAVIOR_DIMENSIONS
        )
        contracts.append(
            BehaviorBlockContract(
                behavior_block_id=f"candidate-behavior:{surface_id}",
                implementation_surface_id=surface_id,
                model_element_id=f"candidate-model:{surface_id}",
                owner_contract_id=f"candidate-owner:{surface_id}",
                owner_id="candidate:unresolved",
                function_relation="Input x State -> Set(Output x State)",
                dimensions=dimensions,
                semantic_spec_ids=(f"candidate-semantic:{surface_id}",),
                oracle_ids=(f"candidate-oracle:{surface_id}",),
                portable_binding_ids=(f"candidate-portable:{surface_id}",),
                protected_failure_ids=(),
                accepted=False,
                acceptance_evidence_fingerprints=(),
                source_fingerprint=str(surface.content_fingerprint),
            )
        )
    unresolved_ids = tuple(row.behavior_block_id for row in contracts)
    if not unresolved_ids:
        unresolved_ids = ("candidate:behavior-denominator-empty",)
    return CandidateBlueprint(
        inventory_fingerprint=inventory_fingerprint,
        target_kind=target_kind,
        observation_provider_ids=provider_ids,
        behavior_contracts=tuple(contracts),
        unresolved_ids=unresolved_ids,
        blockers=(),
    )


__all__ = [
    "BEHAVIOR_BLUEPRINT_SCHEMA",
    "BEHAVIOR_DIMENSIONS",
    "CANDIDATE_BLUEPRINT_SCHEMA",
    "INTENT_INVENTORY_SCHEMA",
    "NORMALIZED_PROJECTION_SCHEMA",
    "STATIC_BLUEPRINT_READINESS_SCHEMA",
    "RESOURCE_CATEGORIES",
    "RESOURCE_INVENTORY_SCHEMA",
    "BehaviorBlockContract",
    "BehaviorBlueprintReport",
    "BehaviorCaseContract",
    "BehaviorCoverageEdge",
    "BehaviorDimensionContract",
    "CoverageExecutionEvidence",
    "DelegatedAssertionHelper",
    "CandidateBlueprint",
    "AffectedBlueprintNeighborhood",
    "NoDeclaredIntentRationale",
    "NormalizedBlueprintProjection",
    "ProjectIntentContribution",
    "ProjectIntentInventory",
    "ProjectResourceInventory",
    "ProjectResourceMember",
    "ProjectTestNodeDisposition",
    "PortableBehaviorBinding",
    "ReadinessFinding",
    "StaticBlueprintReadinessReport",
    "SoftwareBlueprintReadinessError",
    "SupportingSurfaceRelation",
    "generate_candidate_blueprint",
    "load_affected_behavior_neighborhood",
    "normalize_behavior_blueprint",
    "review_behavior_blueprint",
    "review_static_blueprint_readiness",
]
