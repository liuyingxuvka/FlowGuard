"""Contract-driven bad-case generation and closure routing.

ContractExhaustionMesh is the thin common layer for "what else can fail here?"
questions.  Existing routes still own their domains: StateClosure declares
finite state/input boundaries, ScenarioMatrix declares executable sequences,
ObligationFamily declares same-class sibling surfaces, ArtifactPayload declares
file/work-package cases, and ModelMesh/TestMesh close the evidence graph.

This module turns those route-owned declarations into one normalized shape:
dimension -> generated bad case -> oracle -> required downstream route.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ._normalization import (
    nonempty_string_sequence as _as_tuple,
    unique_strings as _unique,
)
from .export import to_json_text, to_jsonable
from .canonical_relation import (
    CanonicalRelation,
    CanonicalRelationHandoff,
    normalize_canonical_relation_handoff,
)
from .model_authority import (
    boundary_topology_fingerprint,
    canonical_fingerprint,
)


CONTRACT_EXHAUSTION_ROUTE = "contract_exhaustion_mesh"

CONTRACT_EXHAUSTION_DECISION_READY = "contract_exhaustion_ready"
CONTRACT_EXHAUSTION_DECISION_SCOPED = "contract_exhaustion_scoped_confidence"
CONTRACT_EXHAUSTION_DECISION_BLOCKED = "contract_exhaustion_blocked"

CONTRACT_EXHAUSTION_CONFIDENCE_FULL = "full"
CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED = "scoped"
CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED = "blocked"

CONTRACT_EXHAUSTION_FINDING_INFO = "info"
CONTRACT_EXHAUSTION_FINDING_GAP = "confidence_gap"
CONTRACT_EXHAUSTION_FINDING_BLOCKER = "blocker"

CONTRACT_DIMENSION_FIELD = "field"
CONTRACT_DIMENSION_STATE = "state"
CONTRACT_DIMENSION_INPUT = "input"
CONTRACT_DIMENSION_PAYLOAD = "payload"
CONTRACT_DIMENSION_EVIDENCE = "evidence"
CONTRACT_DIMENSION_TRANSITION = "transition"
CONTRACT_DIMENSION_PARENT_CHILD = "parent_child"
CONTRACT_DIMENSION_SAME_CLASS = "same_class"
CONTRACT_DIMENSION_LOOP = "loop"

CONTRACT_MUTATION_MISSING_REQUIRED_FIELD = "missing_required_field"
CONTRACT_MUTATION_EMPTY_VALUE = "empty_value"
CONTRACT_MUTATION_WRONG_TYPE = "wrong_type"
CONTRACT_MUTATION_UNKNOWN_ENUM = "unknown_enum"
CONTRACT_MUTATION_MALFORMED_INPUT = "malformed_input"
CONTRACT_MUTATION_MISSING_BODY = "missing_body"
CONTRACT_MUTATION_MISSING_EVIDENCE_FILE = "missing_evidence_file"
CONTRACT_MUTATION_STALE_EVIDENCE = "stale_evidence"
CONTRACT_MUTATION_PATH_MISMATCH = "path_mismatch"
CONTRACT_MUTATION_CONFLICTING_PAYLOAD = "conflicting_payload"
CONTRACT_MUTATION_STALE_CHILD_EVIDENCE = "stale_child_evidence"
CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE = "unconsumed_child_evidence"
CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA = "repeat_without_delta"
CONTRACT_MUTATION_TRANSITION_REPLAY = "transition_replay"
CONTRACT_MUTATION_SCENARIO_CHALLENGE = "scenario_challenge"
CONTRACT_MUTATION_SAME_CLASS_CASE = "same_class_case"
CONTRACT_MUTATION_CARTESIAN_COMBINATION = "cartesian_combination"
CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER = "omitted_family_member"
CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE = "omitted_reduction_candidate"
CONTRACT_MUTATION_RELATION_MATERIALIZATION = "relation_materialization"
CONTRACT_MUTATION_UNMATERIALIZED_RELATION_ID = "unmaterialized_relation_id"

CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT = "reject_before_side_effect"
CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM = "block_before_downstream"
CONTRACT_ORACLE_REISSUE_WITH_REPAIR_INFO = "reissue_with_repair_info"
CONTRACT_ORACLE_MARK_STALE = "mark_stale"
CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK = "no_delta_loop_block"
CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW = "needs_human_review"
CONTRACT_ORACLE_SCOPED_CONFIDENCE = "scoped_confidence"
CONTRACT_ORACLE_PASS_ALLOWED = "pass_allowed"

CONTRACT_ROUTE_FIELD_LIFECYCLE = "field_lifecycle_mesh"
CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
CONTRACT_ROUTE_TEST_MESH = "test_mesh"
CONTRACT_ROUTE_MODEL_MESH = "model_mesh"
CONTRACT_ROUTE_OBLIGATION_FAMILY = "obligation_family_parity"
CONTRACT_ROUTE_MODEL_MISS_REVIEW = "model_miss_review"
CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER = "risk_evidence_ledger"

CONTRACT_GENERATION_SINGLE_DIMENSION = "single_dimension"
CONTRACT_GENERATION_LOCAL_CARTESIAN = "local_cartesian"
CONTRACT_GENERATION_PARENT_INTERFACE = "parent_interface_cartesian"

# ``full`` and ``release`` are intentionally the only scopes that make the
# finite product contract a hard gate.  Routine/design callers can continue
# to use the older scoped behaviour while they assemble a model-local plan.
CONTRACT_STRICT_CLAIM_SCOPES = {
    "full",
    "release",
    "whole_domain",
    "whole-domain",
    "whole_system",
    "whole-system",
    "parent_confidence",
    "parent-confidence",
}

CONTRACT_MODEL_LEVEL_ROOT = "root"
CONTRACT_MODEL_LEVEL_PARENT = "parent"
CONTRACT_MODEL_LEVEL_CHILD = "child"
CONTRACT_MODEL_LEVEL_LEAF = "leaf"

CONTRACT_COVERAGE_STATUS_COVERED = "covered"
CONTRACT_COVERAGE_STATUS_SCOPED = "scoped"
CONTRACT_COVERAGE_STATUS_BLOCKED = "blocked"
CONTRACT_COVERAGE_STATUS_IN_PROGRESS = "in_progress"

DEFAULT_CARTESIAN_CASE_LIMIT = 100_000

_BROAD_CLAIMS = {
    "done",
    "release",
    "publish",
    "production",
    "full",
    "whole_domain",
    "whole-domain",
    "whole_system",
    "whole-system",
    "parent_confidence",
    "parent-confidence",
}
_ACTIONABLE_ORACLE_STATUSES = {
    CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_ORACLE_REISSUE_WITH_REPAIR_INFO,
    CONTRACT_ORACLE_MARK_STALE,
    CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK,
}

_DIMENSION_DEFAULT_MUTATIONS: dict[str, tuple[str, ...]] = {
    CONTRACT_DIMENSION_FIELD: (
        CONTRACT_MUTATION_MISSING_REQUIRED_FIELD,
        CONTRACT_MUTATION_EMPTY_VALUE,
        CONTRACT_MUTATION_WRONG_TYPE,
    ),
    CONTRACT_DIMENSION_STATE: (
        CONTRACT_MUTATION_UNKNOWN_ENUM,
        CONTRACT_MUTATION_MALFORMED_INPUT,
    ),
    CONTRACT_DIMENSION_INPUT: (
        CONTRACT_MUTATION_UNKNOWN_ENUM,
        CONTRACT_MUTATION_MALFORMED_INPUT,
    ),
    CONTRACT_DIMENSION_PAYLOAD: (
        CONTRACT_MUTATION_MISSING_BODY,
        CONTRACT_MUTATION_MALFORMED_INPUT,
        CONTRACT_MUTATION_CONFLICTING_PAYLOAD,
    ),
    CONTRACT_DIMENSION_EVIDENCE: (
        CONTRACT_MUTATION_MISSING_EVIDENCE_FILE,
        CONTRACT_MUTATION_STALE_EVIDENCE,
        CONTRACT_MUTATION_PATH_MISMATCH,
    ),
    CONTRACT_DIMENSION_TRANSITION: (
        CONTRACT_MUTATION_TRANSITION_REPLAY,
    ),
    CONTRACT_DIMENSION_PARENT_CHILD: (
        CONTRACT_MUTATION_STALE_CHILD_EVIDENCE,
        CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE,
    ),
    CONTRACT_DIMENSION_SAME_CLASS: (
        CONTRACT_MUTATION_SAME_CLASS_CASE,
    ),
    CONTRACT_DIMENSION_LOOP: (
        CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA,
    ),
}

_MUTATION_DEFAULT_ORACLE: dict[str, str] = {
    CONTRACT_MUTATION_MISSING_REQUIRED_FIELD: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_EMPTY_VALUE: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_WRONG_TYPE: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_UNKNOWN_ENUM: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_MALFORMED_INPUT: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_MISSING_BODY: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_MISSING_EVIDENCE_FILE: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_STALE_EVIDENCE: CONTRACT_ORACLE_MARK_STALE,
    CONTRACT_MUTATION_PATH_MISMATCH: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_CONFLICTING_PAYLOAD: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_STALE_CHILD_EVIDENCE: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA: CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK,
    CONTRACT_MUTATION_TRANSITION_REPLAY: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_SCENARIO_CHALLENGE: CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW,
    CONTRACT_MUTATION_SAME_CLASS_CASE: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
}


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _metadata_values(metadata: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    values: list[str] = []
    for key in keys:
        raw = metadata.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
            values.extend(str(item) for item in raw if str(item))
        else:
            values.append(str(raw))
    return _unique(values)


def _case_id(*parts: str) -> str:
    return ":".join(str(part).replace(" ", "_") for part in parts if str(part))


def _product_cardinality(axis_values: Iterable[Sequence[Any]]) -> int:
    """Compute a finite product cardinality without materialising its rows."""

    cardinality = 1
    for values in axis_values:
        cardinality *= len(tuple(values))
    return cardinality


@dataclass(frozen=True)
class ContractDimension:
    """One declared finite contract boundary that can produce bad cases."""

    dimension_id: str
    dimension_type: str
    source_route: str = ""
    owner_model_id: str = ""
    required: bool = True
    finite: bool = True
    values: tuple[str, ...] = ()
    mutation_types: tuple[str, ...] = ()
    field_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    producer: str = ""
    consumer: str = ""
    currentness_rule: str = ""
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension_id", str(self.dimension_id))
        object.__setattr__(self, "dimension_type", str(self.dimension_type))
        object.__setattr__(self, "source_route", str(self.source_route))
        object.__setattr__(self, "owner_model_id", str(self.owner_model_id))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "finite", bool(self.finite))
        object.__setattr__(self, "values", _as_tuple(self.values))
        object.__setattr__(self, "mutation_types", _as_tuple(self.mutation_types))
        object.__setattr__(self, "field_refs", _as_tuple(self.field_refs))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "producer", str(self.producer))
        object.__setattr__(self, "consumer", str(self.consumer))
        object.__setattr__(self, "currentness_rule", str(self.currentness_rule))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def default_mutations(self) -> tuple[str, ...]:
        if self.mutation_types:
            return self.mutation_types
        return _DIMENSION_DEFAULT_MUTATIONS.get(
            self.dimension_type,
            (
                CONTRACT_MUTATION_MISSING_REQUIRED_FIELD,
                CONTRACT_MUTATION_MALFORMED_INPUT,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "dimension_type": self.dimension_type,
            "source_route": self.source_route,
            "owner_model_id": self.owner_model_id,
            "required": self.required,
            "finite": self.finite,
            "values": list(self.values),
            "mutation_types": list(self.mutation_types),
            "field_refs": list(self.field_refs),
            "evidence_refs": list(self.evidence_refs),
            "producer": self.producer,
            "consumer": self.consumer,
            "currentness_rule": self.currentness_rule,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractOracle:
    """The runtime/model reaction expected for one generated bad case."""

    oracle_id: str
    expected_status: str
    expected_message_fields: tuple[str, ...] = ()
    forbidden_downstream_steps: tuple[str, ...] = ()
    required_repair_fields: tuple[str, ...] = ()
    allowed_side_effects: tuple[str, ...] = ()
    disallowed_side_effects: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "oracle_id", str(self.oracle_id))
        object.__setattr__(self, "expected_status", str(self.expected_status))
        object.__setattr__(self, "expected_message_fields", _as_tuple(self.expected_message_fields))
        object.__setattr__(self, "forbidden_downstream_steps", _as_tuple(self.forbidden_downstream_steps))
        object.__setattr__(self, "required_repair_fields", _as_tuple(self.required_repair_fields))
        object.__setattr__(self, "allowed_side_effects", _as_tuple(self.allowed_side_effects))
        object.__setattr__(self, "disallowed_side_effects", _as_tuple(self.disallowed_side_effects))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "expected_status": self.expected_status,
            "expected_message_fields": list(self.expected_message_fields),
            "forbidden_downstream_steps": list(self.forbidden_downstream_steps),
            "required_repair_fields": list(self.required_repair_fields),
            "allowed_side_effects": list(self.allowed_side_effects),
            "disallowed_side_effects": list(self.disallowed_side_effects),
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractMutationCase:
    """One generated or imported bad case that must be tested or blocked."""

    case_id: str
    dimension_id: str = ""
    mutation_type: str = ""
    source_route: str = ""
    source_case_id: str = ""
    required: bool = True
    oracle_id: str = ""
    input_delta: Mapping[str, Any] = field(default_factory=dict)
    expected_status: str = ""
    family_id: str = ""
    member_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    required_routes: tuple[str, ...] = ()
    required_test_cell_id: str = ""
    risk_gate_id: str = ""
    freshness_scope: str = ""
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    dimension_ids: tuple[str, ...] = ()
    axis_case_ids: tuple[str, ...] = ()
    interaction_group_id: str = ""
    combination_order: int = 0
    coverage_shard_id: str = ""
    model_id: str = ""
    parent_model_id: str = ""
    generation_kind: str = CONTRACT_GENERATION_SINGLE_DIMENSION

    def __post_init__(self) -> None:
        mutation_type = str(self.mutation_type)
        expected_status = str(self.expected_status or _MUTATION_DEFAULT_ORACLE.get(mutation_type, ""))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "dimension_id", str(self.dimension_id))
        object.__setattr__(self, "mutation_type", mutation_type)
        object.__setattr__(self, "source_route", str(self.source_route))
        object.__setattr__(self, "source_case_id", str(self.source_case_id))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "oracle_id", str(self.oracle_id))
        object.__setattr__(self, "input_delta", dict(self.input_delta or {}))
        object.__setattr__(self, "expected_status", expected_status)
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "required_routes", _as_tuple(self.required_routes))
        object.__setattr__(self, "required_test_cell_id", str(self.required_test_cell_id))
        object.__setattr__(self, "risk_gate_id", str(self.risk_gate_id))
        object.__setattr__(self, "freshness_scope", str(self.freshness_scope))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        object.__setattr__(self, "dimension_ids", _as_tuple(self.dimension_ids))
        object.__setattr__(self, "axis_case_ids", _as_tuple(self.axis_case_ids))
        object.__setattr__(self, "interaction_group_id", str(self.interaction_group_id))
        object.__setattr__(self, "combination_order", int(self.combination_order))
        object.__setattr__(self, "coverage_shard_id", str(self.coverage_shard_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "generation_kind", str(self.generation_kind))

    def routes(self) -> tuple[str, ...]:
        if self.required_routes:
            return self.required_routes
        if self.mutation_type in {
            CONTRACT_MUTATION_MISSING_EVIDENCE_FILE,
            CONTRACT_MUTATION_STALE_EVIDENCE,
            CONTRACT_MUTATION_PATH_MISMATCH,
            CONTRACT_MUTATION_CONFLICTING_PAYLOAD,
            CONTRACT_MUTATION_MISSING_BODY,
        }:
            return (
                CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                CONTRACT_ROUTE_TEST_MESH,
                CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
            )
        if self.mutation_type in {
            CONTRACT_MUTATION_STALE_CHILD_EVIDENCE,
            CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE,
            CONTRACT_MUTATION_TRANSITION_REPLAY,
        }:
            return (
                CONTRACT_ROUTE_MODEL_MESH,
                CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                CONTRACT_ROUTE_TEST_MESH,
            )
        if self.mutation_type == CONTRACT_MUTATION_SAME_CLASS_CASE:
            return (
                CONTRACT_ROUTE_OBLIGATION_FAMILY,
                CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                CONTRACT_ROUTE_TEST_MESH,
            )
        if self.mutation_type == CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA:
            return (
                CONTRACT_ROUTE_MODEL_MESH,
                CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                CONTRACT_ROUTE_TEST_MESH,
            )
        if self.mutation_type == CONTRACT_MUTATION_CARTESIAN_COMBINATION:
            return (
                CONTRACT_ROUTE_MODEL_MESH,
                CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                CONTRACT_ROUTE_TEST_MESH,
                CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
            )
        return (
            CONTRACT_ROUTE_FIELD_LIFECYCLE,
            CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "dimension_id": self.dimension_id,
            "mutation_type": self.mutation_type,
            "source_route": self.source_route,
            "source_case_id": self.source_case_id,
            "required": self.required,
            "oracle_id": self.oracle_id,
            "input_delta": to_jsonable(dict(self.input_delta)),
            "expected_status": self.expected_status,
            "family_id": self.family_id,
            "member_id": self.member_id,
            "evidence_refs": list(self.evidence_refs),
            "required_routes": list(self.required_routes),
            "resolved_routes": list(self.routes()),
            "required_test_cell_id": self.required_test_cell_id,
            "risk_gate_id": self.risk_gate_id,
            "freshness_scope": self.freshness_scope,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
            "dimension_ids": list(self.dimension_ids),
            "axis_case_ids": list(self.axis_case_ids),
            "interaction_group_id": self.interaction_group_id,
            "combination_order": self.combination_order,
            "coverage_shard_id": self.coverage_shard_id,
            "model_id": self.model_id,
            "parent_model_id": self.parent_model_id,
            "generation_kind": self.generation_kind,
        }


@dataclass(frozen=True)
class ContractExhaustionFinding:
    """One model gap, missing oracle, or blocked contract expansion."""

    code: str
    message: str
    severity: str = CONTRACT_EXHAUSTION_FINDING_BLOCKER
    dimension_id: str = ""
    case_id: str = ""
    action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "dimension_id", str(self.dimension_id))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "dimension_id": self.dimension_id,
            "case_id": self.case_id,
            "action": self.action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class CompositeHandoffAcceptance:
    """Independent acceptance item for a multi-route case handoff."""

    acceptance_id: str
    case_id: str
    route_ids: tuple[str, ...]
    required: bool = True
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "acceptance_id", str(self.acceptance_id))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "route_ids", _as_tuple(self.route_ids))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "acceptance_id": self.acceptance_id,
            "case_id": self.case_id,
            "route_ids": list(self.route_ids),
            "required": self.required,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class CompositeHandoffResult:
    """Terminal result for one :class:`CompositeHandoffAcceptance` obligation.

    The obligation and its result deliberately have different identities.  A
    generated handoff item only says which routes must be exercised; it is not
    evidence that those routes were exercised successfully.  Broad claims
    therefore consume this result, never the obligation object itself.
    """

    result_id: str
    acceptance_id: str
    status: str = CONTRACT_COVERAGE_STATUS_COVERED
    current: bool = True
    result_fingerprint: str = ""
    covered_route_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", str(self.result_id))
        object.__setattr__(self, "acceptance_id", str(self.acceptance_id))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "result_fingerprint", str(self.result_fingerprint))
        object.__setattr__(self, "covered_route_ids", _as_tuple(self.covered_route_ids))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        if not self.result_fingerprint:
            object.__setattr__(
                self,
                "result_fingerprint",
                canonical_fingerprint(self.identity_payload()),
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "acceptance_id": self.acceptance_id,
            "status": self.status,
            "current": self.current,
            "covered_route_ids": list(self.covered_route_ids),
            "evidence_ids": list(self.evidence_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }

    def complete(self, *, expected_acceptance_id: str = "") -> bool:
        return bool(
            self.result_id
            and self.acceptance_id
            and (not expected_acceptance_id or self.acceptance_id == expected_acceptance_id)
            and self.status == CONTRACT_COVERAGE_STATUS_COVERED
            and self.current
            and self.evidence_ids
            and self.result_fingerprint == canonical_fingerprint(self.identity_payload())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "acceptance_id": self.acceptance_id,
            "status": self.status,
            "current": self.current,
            "result_fingerprint": self.result_fingerprint,
            "covered_route_ids": list(self.covered_route_ids),
            "evidence_ids": list(self.evidence_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractAxis:
    """One finite axis inside a model-local Cartesian bad-case group."""

    axis_id: str
    model_id: str = ""
    dimension_ids: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    mutation_types: tuple[str, ...] = ()
    required: bool = True
    source_route: str = ""
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # The axis identity is content addressed.  Keeping this at the axis
    # boundary (rather than only on the generated product) lets a leaf or a
    # parent reject a stale/foreign axis before it can influence a product
    # denominator.  It is appended after the historical fields so existing
    # positional callers retain their meaning.
    axis_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "axis_id", str(self.axis_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "dimension_ids", _as_tuple(self.dimension_ids))
        object.__setattr__(self, "values", _as_tuple(self.values))
        object.__setattr__(self, "mutation_types", _as_tuple(self.mutation_types))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "source_route", str(self.source_route))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        supplied = str(self.axis_fingerprint)
        object.__setattr__(
            self,
            "axis_fingerprint",
            supplied or canonical_fingerprint(self.identity_payload()),
        )

    def identity_payload(self) -> dict[str, Any]:
        """Return the canonical axis content without its self-fingerprint."""

        return {
            "axis_id": self.axis_id,
            "model_id": self.model_id,
            "dimension_ids": list(self.dimension_ids),
            "values": list(self.values),
            "mutation_types": list(self.mutation_types),
            "required": self.required,
            "source_route": self.source_route,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    @property
    def fingerprint(self) -> str:
        """Compatibility/readability alias for the canonical axis fingerprint."""

        return self.axis_fingerprint

    def is_self_consistent(self) -> bool:
        return bool(
            self.axis_id
            and self.axis_fingerprint
            and self.axis_fingerprint == canonical_fingerprint(self.identity_payload())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis_id": self.axis_id,
            "model_id": self.model_id,
            "dimension_ids": list(self.dimension_ids),
            "values": list(self.values),
            "mutation_types": list(self.mutation_types),
            "required": self.required,
            "source_route": self.source_route,
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
            "axis_fingerprint": self.axis_fingerprint,
        }


@dataclass(frozen=True)
class ContractProductSignature:
    """Canonical identity of one model-local finite Cartesian product.

    The signature is derived from the model, ordered axes and their values,
    expected cardinality, and partition/shard identity.  Consumers must bind
    the signature to the same group; a count alone is not a coverage proof.
    """

    signature_id: str
    model_id: str
    interaction_group_id: str
    axis_ids: tuple[str, ...] = ()
    axis_value_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    expected_cardinality: int = 0
    partition_revision: str = ""
    generation_kind: str = CONTRACT_GENERATION_LOCAL_CARTESIAN
    shard_plan_fingerprint: str = ""
    fingerprint: str = ""
    # Appended for source compatibility with the original signature shape.
    # Every generated signature now carries the identity of each axis in
    # addition to its value ids.
    axis_fingerprints: Mapping[str, str] = field(default_factory=dict)
    parent_interface_contract_id: str = ""
    refinement_contract_id: str = ""
    interface_model_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "signature_id", str(self.signature_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "interaction_group_id", str(self.interaction_group_id))
        object.__setattr__(self, "axis_ids", _as_tuple(self.axis_ids))
        object.__setattr__(
            self,
            "axis_value_ids",
            {
                str(axis_id): _as_tuple(values)
                for axis_id, values in sorted(
                    dict(self.axis_value_ids).items(), key=lambda item: str(item[0])
                )
            },
        )
        object.__setattr__(self, "expected_cardinality", int(self.expected_cardinality))
        object.__setattr__(self, "partition_revision", str(self.partition_revision))
        object.__setattr__(self, "generation_kind", str(self.generation_kind))
        object.__setattr__(self, "shard_plan_fingerprint", str(self.shard_plan_fingerprint))
        object.__setattr__(
            self,
            "axis_fingerprints",
            {
                str(axis_id): str(fingerprint)
                for axis_id, fingerprint in sorted(
                    dict(self.axis_fingerprints).items(), key=lambda item: str(item[0])
                )
            },
        )
        object.__setattr__(
            self,
            "parent_interface_contract_id",
            str(self.parent_interface_contract_id),
        )
        object.__setattr__(self, "refinement_contract_id", str(self.refinement_contract_id))
        object.__setattr__(self, "interface_model_ids", _as_tuple(self.interface_model_ids))
        supplied = str(self.fingerprint)
        object.__setattr__(
            self,
            "fingerprint",
            supplied or canonical_fingerprint(self.identity_payload()),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "signature_id": self.signature_id,
            "model_id": self.model_id,
            "interaction_group_id": self.interaction_group_id,
            "axis_ids": list(self.axis_ids),
            "axis_value_ids": {
                axis_id: list(values) for axis_id, values in self.axis_value_ids.items()
            },
            "axis_fingerprints": dict(self.axis_fingerprints),
            "expected_cardinality": self.expected_cardinality,
            "partition_revision": self.partition_revision,
            "generation_kind": self.generation_kind,
            "shard_plan_fingerprint": self.shard_plan_fingerprint,
            "parent_interface_contract_id": self.parent_interface_contract_id,
            "refinement_contract_id": self.refinement_contract_id,
            "interface_model_ids": list(self.interface_model_ids),
        }

    def is_self_consistent(self) -> bool:
        return bool(
            self.signature_id
            and self.model_id
            and self.interaction_group_id
            and self.axis_ids
            and all(axis_id in self.axis_value_ids for axis_id in self.axis_ids)
            and len(self.axis_ids) == len(set(self.axis_ids))
            and set(self.axis_value_ids) == set(self.axis_ids)
            and set(self.axis_fingerprints) == set(self.axis_ids)
            and all(self.axis_fingerprints.get(axis_id) for axis_id in self.axis_ids)
            and all(self.axis_value_ids.get(axis_id) for axis_id in self.axis_ids)
            and self.expected_cardinality > 0
            and self.expected_cardinality
            == _product_cardinality(
                self.axis_value_ids.get(axis_id, ()) for axis_id in self.axis_ids
            )
            and (
                self.generation_kind != CONTRACT_GENERATION_PARENT_INTERFACE
                or (
                    self.parent_interface_contract_id
                    and self.refinement_contract_id
                    and self.interface_model_ids
                )
            )
            and self.fingerprint == canonical_fingerprint(self.identity_payload())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class ContractInteractionGroup:
    """A finite set of axes that must be combined within one model boundary."""

    group_id: str
    model_id: str = ""
    axis_ids: tuple[str, ...] = ()
    dimension_ids: tuple[str, ...] = ()
    generation_kind: str = CONTRACT_GENERATION_LOCAL_CARTESIAN
    required_routes: tuple[str, ...] = ()
    required: bool = True
    max_combinations: int | None = None
    oracle_id: str = ""
    oracle_status: str = CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    product_signature: ContractProductSignature | Mapping[str, Any] | None = None
    # A cross-model product is valid only as a typed parent-interface product.
    # These fields are explicit so a metadata-only declaration cannot silently
    # become an interface contract.  They are appended to preserve existing
    # positional construction.
    parent_interface_contract_id: str = ""
    refinement_contract_id: str = ""
    interface_model_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", str(self.group_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "axis_ids", _as_tuple(self.axis_ids))
        object.__setattr__(self, "dimension_ids", _as_tuple(self.dimension_ids))
        object.__setattr__(self, "generation_kind", str(self.generation_kind))
        object.__setattr__(self, "required_routes", _as_tuple(self.required_routes))
        object.__setattr__(self, "required", bool(self.required))
        if self.max_combinations is not None:
            object.__setattr__(self, "max_combinations", int(self.max_combinations))
        object.__setattr__(self, "oracle_id", str(self.oracle_id))
        object.__setattr__(self, "oracle_status", str(self.oracle_status))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        metadata = dict(self.metadata)
        object.__setattr__(
            self,
            "parent_interface_contract_id",
            str(
                self.parent_interface_contract_id
                or metadata.get("parent_interface_contract_id", "")
                or metadata.get("interface_contract_id", "")
            ),
        )
        object.__setattr__(
            self,
            "refinement_contract_id",
            str(
                self.refinement_contract_id
                or metadata.get("refinement_contract_id", "")
                or metadata.get("refinement_id", "")
            ),
        )
        interface_model_ids = self.interface_model_ids or metadata.get(
            "interface_model_ids", ()
        )
        object.__setattr__(self, "interface_model_ids", _as_tuple(interface_model_ids))
        signature = self.product_signature
        if signature is not None and not isinstance(signature, ContractProductSignature):
            if isinstance(signature, Mapping):
                signature = ContractProductSignature(
                    signature_id=str(signature.get("signature_id", "")),
                    model_id=str(signature.get("model_id", "")),
                    interaction_group_id=str(signature.get("interaction_group_id", "")),
                    axis_ids=signature.get("axis_ids", ()),
                    axis_value_ids=signature.get("axis_value_ids", {}),
                    expected_cardinality=signature.get("expected_cardinality", 0),
                    partition_revision=str(signature.get("partition_revision", "")),
                    generation_kind=str(
                        signature.get("generation_kind", CONTRACT_GENERATION_LOCAL_CARTESIAN)
                    ),
                    shard_plan_fingerprint=str(signature.get("shard_plan_fingerprint", "")),
                    fingerprint=str(signature.get("fingerprint", "")),
                    axis_fingerprints=signature.get("axis_fingerprints", {}),
                    parent_interface_contract_id=str(
                        signature.get("parent_interface_contract_id", "")
                    ),
                    refinement_contract_id=str(signature.get("refinement_contract_id", "")),
                    interface_model_ids=signature.get("interface_model_ids", ()),
                )
            else:
                raise TypeError("product_signature must be a ContractProductSignature or mapping")
        object.__setattr__(self, "product_signature", signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "model_id": self.model_id,
            "axis_ids": list(self.axis_ids),
            "dimension_ids": list(self.dimension_ids),
            "generation_kind": self.generation_kind,
            "required_routes": list(self.required_routes),
            "required": self.required,
            "max_combinations": self.max_combinations,
            "oracle_id": self.oracle_id,
            "oracle_status": self.oracle_status,
            "description": self.description,
            "parent_interface_contract_id": self.parent_interface_contract_id,
            "refinement_contract_id": self.refinement_contract_id,
            "interface_model_ids": list(self.interface_model_ids),
            "product_signature": (
                self.product_signature.to_dict() if self.product_signature is not None else None
            ),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractCoverageShard:
    """One deterministic slice of generated Cartesian combination cases."""

    shard_id: str
    model_id: str = ""
    interaction_group_id: str = ""
    case_ids: tuple[str, ...] = ()
    complete: bool = True
    total_combinations: int = 0
    generated_count: int = 0
    skipped_count: int = 0
    status: str = CONTRACT_COVERAGE_STATUS_COVERED
    metadata: Mapping[str, Any] = field(default_factory=dict)
    product_signature: str = ""
    axis_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "shard_id", str(self.shard_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "interaction_group_id", str(self.interaction_group_id))
        object.__setattr__(self, "case_ids", _as_tuple(self.case_ids))
        object.__setattr__(self, "complete", bool(self.complete))
        object.__setattr__(self, "total_combinations", int(self.total_combinations))
        object.__setattr__(self, "generated_count", int(self.generated_count))
        object.__setattr__(self, "skipped_count", int(self.skipped_count))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "product_signature", str(self.product_signature))
        object.__setattr__(self, "axis_ids", _as_tuple(self.axis_ids))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "model_id": self.model_id,
            "interaction_group_id": self.interaction_group_id,
            "case_ids": list(self.case_ids),
            "complete": self.complete,
            "total_combinations": self.total_combinations,
            "generated_count": self.generated_count,
            "skipped_count": self.skipped_count,
            "status": self.status,
            "product_signature": self.product_signature,
            "axis_ids": list(self.axis_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractCombinationCase:
    """Human-readable view of a generated Cartesian combination case."""

    case_id: str
    model_id: str = ""
    interaction_group_id: str = ""
    axis_case_ids: tuple[str, ...] = ()
    dimension_ids: tuple[str, ...] = ()
    coverage_shard_id: str = ""
    expected_status: str = CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM
    required_routes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "interaction_group_id", str(self.interaction_group_id))
        object.__setattr__(self, "axis_case_ids", _as_tuple(self.axis_case_ids))
        object.__setattr__(self, "dimension_ids", _as_tuple(self.dimension_ids))
        object.__setattr__(self, "coverage_shard_id", str(self.coverage_shard_id))
        object.__setattr__(self, "expected_status", str(self.expected_status))
        object.__setattr__(self, "required_routes", _as_tuple(self.required_routes))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "model_id": self.model_id,
            "interaction_group_id": self.interaction_group_id,
            "axis_case_ids": list(self.axis_case_ids),
            "dimension_ids": list(self.dimension_ids),
            "coverage_shard_id": self.coverage_shard_id,
            "expected_status": self.expected_status,
            "required_routes": list(self.required_routes),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class NativeChildEvidenceBinding:
    """Canonical binding from a model-coverage child to a native EvidenceReceipt.

    ``ModelContractCoverageReceipt`` is a planning/report object and is not a
    substitute for the target-owned immutable ``EvidenceReceipt``.  In a
    strict claim, every required child coverage id must name exactly one of
    these bindings.  The native receipt is then loaded from the canonical
    store and independently verified; callers cannot satisfy the parent by
    supplying only an id or an aggregate status.
    """

    coverage_receipt_id: str
    evidence_receipt_id: str
    model_id: str
    owner_id: str
    parent_model_id: str
    subject_id: str
    claim_scope: str
    obligation_ids: tuple[str, ...] = ()
    expected_receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        for name in (
            "coverage_receipt_id",
            "evidence_receipt_id",
            "model_id",
            "owner_id",
            "parent_model_id",
            "subject_id",
            "claim_scope",
            "expected_receipt_fingerprint",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "obligation_ids", _as_tuple(self.obligation_ids))

    def complete(self) -> bool:
        return bool(
            self.coverage_receipt_id
            and self.evidence_receipt_id
            and self.model_id
            and self.owner_id
            and self.parent_model_id
            and self.subject_id
            and self.claim_scope
            and self.obligation_ids
            and self.expected_receipt_fingerprint
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NativeChildEvidenceBinding":
        return cls(
            coverage_receipt_id=str(data.get("coverage_receipt_id", "")),
            evidence_receipt_id=str(data.get("evidence_receipt_id", "")),
            model_id=str(data.get("model_id", "")),
            owner_id=str(data.get("owner_id", "")),
            parent_model_id=str(data.get("parent_model_id", "")),
            subject_id=str(data.get("subject_id", "")),
            claim_scope=str(data.get("claim_scope", "")),
            obligation_ids=_as_tuple(data.get("obligation_ids", ())),
            expected_receipt_fingerprint=str(data.get("expected_receipt_fingerprint", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_receipt_id": self.coverage_receipt_id,
            "evidence_receipt_id": self.evidence_receipt_id,
            "model_id": self.model_id,
            "owner_id": self.owner_id,
            "parent_model_id": self.parent_model_id,
            "subject_id": self.subject_id,
            "claim_scope": self.claim_scope,
            "obligation_ids": list(self.obligation_ids),
            "expected_receipt_fingerprint": self.expected_receipt_fingerprint,
        }


@dataclass(frozen=True)
class ModelContractCoverageReceipt:
    """Receipt proving one model's generated contract combinations were closed."""

    receipt_id: str
    model_id: str
    parent_model_id: str = ""
    status: str = CONTRACT_COVERAGE_STATUS_COVERED
    confidence: str = CONTRACT_EXHAUSTION_CONFIDENCE_FULL
    current: bool = True
    covered_case_ids: tuple[str, ...] = ()
    shard_ids: tuple[str, ...] = ()
    interaction_group_ids: tuple[str, ...] = ()
    required_child_receipt_ids: tuple[str, ...] = ()
    consumed_child_receipt_ids: tuple[str, ...] = ()
    missing_case_ids: tuple[str, ...] = ()
    blocked_case_ids: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    product_signature: str = ""
    owner_id: str = ""
    claim_scope: str = ""
    native_child_evidence_bindings: tuple[NativeChildEvidenceBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "covered_case_ids", _as_tuple(self.covered_case_ids))
        object.__setattr__(self, "shard_ids", _as_tuple(self.shard_ids))
        object.__setattr__(self, "interaction_group_ids", _as_tuple(self.interaction_group_ids))
        object.__setattr__(self, "required_child_receipt_ids", _as_tuple(self.required_child_receipt_ids))
        object.__setattr__(self, "consumed_child_receipt_ids", _as_tuple(self.consumed_child_receipt_ids))
        object.__setattr__(self, "missing_case_ids", _as_tuple(self.missing_case_ids))
        object.__setattr__(self, "blocked_case_ids", _as_tuple(self.blocked_case_ids))
        object.__setattr__(self, "finding_codes", _as_tuple(self.finding_codes))
        object.__setattr__(self, "product_signature", str(self.product_signature))
        object.__setattr__(self, "owner_id", str(self.owner_id))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(
            self,
            "native_child_evidence_bindings",
            tuple(
                item
                if isinstance(item, NativeChildEvidenceBinding)
                else NativeChildEvidenceBinding.from_dict(item)
                for item in self.native_child_evidence_bindings
            ),
        )
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def complete(self) -> bool:
        return (
            self.status == CONTRACT_COVERAGE_STATUS_COVERED
            and self.confidence == CONTRACT_EXHAUSTION_CONFIDENCE_FULL
            and self.current
            and not self.missing_case_ids
            and not self.blocked_case_ids
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "model_id": self.model_id,
            "parent_model_id": self.parent_model_id,
            "status": self.status,
            "confidence": self.confidence,
            "current": self.current,
            "covered_case_ids": list(self.covered_case_ids),
            "shard_ids": list(self.shard_ids),
            "interaction_group_ids": list(self.interaction_group_ids),
            "required_child_receipt_ids": list(self.required_child_receipt_ids),
            "consumed_child_receipt_ids": list(self.consumed_child_receipt_ids),
            "missing_case_ids": list(self.missing_case_ids),
            "blocked_case_ids": list(self.blocked_case_ids),
            "finding_codes": list(self.finding_codes),
            "product_signature": self.product_signature,
            "owner_id": self.owner_id,
            "claim_scope": self.claim_scope,
            "native_child_evidence_bindings": [
                item.to_dict() for item in self.native_child_evidence_bindings
            ],
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractCoverageExclusion:
    """Explicitly scoped item omitted from a coverage universe."""

    item_kind: str
    item_id: str
    reason: str
    owner_route: str
    source_ref: str = ""
    expires_when: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_kind", str(self.item_kind))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "source_ref", str(self.source_ref))
        object.__setattr__(self, "expires_when", str(self.expires_when))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def complete(self) -> bool:
        return bool(self.item_kind and self.item_id and self.reason and self.owner_route)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_kind": self.item_kind,
            "item_id": self.item_id,
            "reason": self.reason,
            "owner_route": self.owner_route,
            "source_ref": self.source_ref,
            "expires_when": self.expires_when,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ContractCoverageUniverse:
    """The declared finite universe a contract-exhaustion report claims to cover."""

    universe_id: str
    claim_scope: str = ""
    source_refs: tuple[str, ...] = ()
    required_dimension_ids: tuple[str, ...] = ()
    required_axis_ids: tuple[str, ...] = ()
    required_interaction_group_ids: tuple[str, ...] = ()
    required_payload_contract_ids: tuple[str, ...] = ()
    required_boundary_ids: tuple[str, ...] = ()
    required_case_ids: tuple[str, ...] = ()
    required_coverage_receipt_ids: tuple[str, ...] = ()
    required_product_signature_ids: tuple[str, ...] = ()
    required_family_member_ids: tuple[str, ...] = ()
    required_reduction_candidate_ids: tuple[str, ...] = ()
    required_relation_ids: tuple[str, ...] = ()
    exclusions: tuple[ContractCoverageExclusion, ...] = ()
    require_full_product: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # A global coverage universe may be proved by a finite set of disjoint
    # model-local products plus explicit parent/interface handoffs.  Keep the
    # historical ``require_full_product`` switch for callers that really need
    # one monolithic product, while allowing route owners to declare the
    # partitioned form explicitly instead of being forced to materialize a
    # huge cross-model Cartesian table.
    allow_partitioned_product: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "universe_id", str(self.universe_id))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "source_refs", _as_tuple(self.source_refs))
        object.__setattr__(self, "required_dimension_ids", _as_tuple(self.required_dimension_ids))
        object.__setattr__(self, "required_axis_ids", _as_tuple(self.required_axis_ids))
        object.__setattr__(
            self,
            "required_interaction_group_ids",
            _as_tuple(self.required_interaction_group_ids),
        )
        object.__setattr__(
            self,
            "required_payload_contract_ids",
            _as_tuple(self.required_payload_contract_ids),
        )
        object.__setattr__(self, "required_boundary_ids", _as_tuple(self.required_boundary_ids))
        object.__setattr__(self, "required_case_ids", _as_tuple(self.required_case_ids))
        object.__setattr__(
            self,
            "required_coverage_receipt_ids",
            _as_tuple(self.required_coverage_receipt_ids),
        )
        object.__setattr__(
            self,
            "required_product_signature_ids",
            _as_tuple(self.required_product_signature_ids),
        )
        object.__setattr__(self, "required_family_member_ids", _as_tuple(self.required_family_member_ids))
        object.__setattr__(
            self,
            "required_reduction_candidate_ids",
            _as_tuple(self.required_reduction_candidate_ids),
        )
        object.__setattr__(self, "required_relation_ids", _as_tuple(self.required_relation_ids))
        object.__setattr__(self, "exclusions", tuple(self.exclusions))
        object.__setattr__(self, "require_full_product", bool(self.require_full_product))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        object.__setattr__(self, "allow_partitioned_product", bool(self.allow_partitioned_product))

    def excluded(self, item_kind: str, item_id: str) -> bool:
        return any(
            exclusion.item_kind == item_kind
            and exclusion.item_id == item_id
            and exclusion.complete()
            for exclusion in self.exclusions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_id": self.universe_id,
            "claim_scope": self.claim_scope,
            "source_refs": list(self.source_refs),
            "required_dimension_ids": list(self.required_dimension_ids),
            "required_axis_ids": list(self.required_axis_ids),
            "required_interaction_group_ids": list(self.required_interaction_group_ids),
            "required_payload_contract_ids": list(self.required_payload_contract_ids),
            "required_boundary_ids": list(self.required_boundary_ids),
            "required_case_ids": list(self.required_case_ids),
            "required_coverage_receipt_ids": list(self.required_coverage_receipt_ids),
            "required_product_signature_ids": list(self.required_product_signature_ids),
            "required_family_member_ids": list(self.required_family_member_ids),
            "required_reduction_candidate_ids": list(self.required_reduction_candidate_ids),
            "required_relation_ids": list(self.required_relation_ids),
            "exclusions": [exclusion.to_dict() for exclusion in self.exclusions],
            "require_full_product": self.require_full_product,
            "metadata": to_jsonable(dict(self.metadata)),
            "allow_partitioned_product": self.allow_partitioned_product,
        }


@dataclass(frozen=True)
class _PartitionedProductVerificationContext:
    """Invocation-local, authority-derived denominator for partitioned claims."""

    boundary_source_id: str
    boundary_source_fingerprint: str
    model_authority_head_fingerprint: str
    topology_fingerprint: str
    canonical_relation_handoff: CanonicalRelationHandoff
    required_groups: tuple[ContractInteractionGroup, ...] = ()
    required_axes: tuple[ContractAxis, ...] = ()
    group_relation_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "boundary_source_id",
            "boundary_source_fingerprint",
            "model_authority_head_fingerprint",
            "topology_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"partition verification context requires {field_name}")
            object.__setattr__(self, field_name, value)
        handoff = normalize_canonical_relation_handoff(self.canonical_relation_handoff)
        if handoff is None:
            raise ValueError(
                "partition verification context requires canonical relation handoff"
            )
        object.__setattr__(self, "canonical_relation_handoff", handoff)
        groups = tuple(
            group
            if isinstance(group, ContractInteractionGroup)
            else ContractInteractionGroup(**dict(group))
            for group in self.required_groups
        )
        group_ids = tuple(group.group_id for group in groups)
        if not groups or len(set(group_ids)) != len(group_ids):
            raise ValueError(
                "partition verification context requires unique required groups"
            )
        object.__setattr__(self, "required_groups", groups)
        axes = tuple(
            axis
            if isinstance(axis, ContractAxis)
            else ContractAxis(**dict(axis))
            for axis in self.required_axes
        )
        axis_ids = tuple(axis.axis_id for axis in axes)
        if len(axis_ids) != len(set(axis_ids)):
            raise ValueError(
                "partition verification context requires unique required axes"
            )
        if any(not axis.is_self_consistent() for axis in axes):
            raise ValueError(
                "partition verification context requires self-consistent axes"
            )
        if axes and any(
            axis_id not in set(axis_ids)
            for group in groups
            for axis_id in group.axis_ids
        ):
            raise ValueError(
                "partition verification context group references an unknown accepted axis"
            )
        object.__setattr__(self, "required_axes", axes)
        relation_map = {
            str(group_id): _as_tuple(relation_ids)
            for group_id, relation_ids in dict(self.group_relation_ids).items()
        }
        if set(relation_map) != set(group_ids) or any(
            not relation_ids for relation_ids in relation_map.values()
        ):
            raise ValueError(
                "partition verification context group relation bindings are incomplete"
            )
        object.__setattr__(self, "group_relation_ids", relation_map)


def partition_context_from_accepted_authority(
    authority_state: Any,
    *,
    model_id: str = "",
) -> _PartitionedProductVerificationContext:
    """Derive the partition denominator from one accepted model authority.

    ``ContractExhaustionMesh`` must never manufacture a boundary from the
    caller's plan.  The only accepted source is the current authority state
    resolved by :mod:`flowguard.model_authority_store`, which carries the
    immutable head, observed snapshot, and accepted revision set together.
    This adapter intentionally uses the state attributes instead of importing
    the store's concrete class, keeping the contract module independent of
    the store implementation while still rejecting an unaccepted/legacy
    state.
    """

    if authority_state is None:
        raise ValueError("accepted authority state is required")
    head = getattr(authority_state, "head", None)
    snapshot = getattr(authority_state, "snapshot", None)
    accepted_revision = getattr(authority_state, "accepted_revision", None)
    if head is None or snapshot is None or accepted_revision is None:
        raise ValueError(
            "partition denominator requires a current accepted authority head, snapshot, and revision"
        )
    if str(getattr(accepted_revision, "status", "")) != "accepted":
        raise ValueError("partition denominator requires an accepted revision set")
    transition_kind = str(getattr(authority_state, "transition_kind", ""))
    if transition_kind not in {"activation", "rollback"}:
        raise ValueError(
            "partition denominator requires a typed activation or rollback authority transition"
        )

    head_fingerprint = str(getattr(head, "fingerprint", "")).strip()
    head_snapshot_fingerprint = str(
        getattr(head, "snapshot_fingerprint", "")
    ).strip()
    snapshot_fingerprint = str(getattr(snapshot, "fingerprint", "")).strip()
    if not head_fingerprint or not head_snapshot_fingerprint or not snapshot_fingerprint:
        raise ValueError("accepted authority identity is incomplete")
    if head_snapshot_fingerprint != snapshot_fingerprint:
        raise ValueError("accepted authority head does not name the supplied snapshot")
    accepted_revision_fingerprint = str(
        getattr(accepted_revision, "fingerprint", "")
    ).strip()
    head_revision_fingerprint = str(
        getattr(head, "accepted_revision_set_fingerprint", "")
    ).strip()
    if (
        accepted_revision_fingerprint
        and head_revision_fingerprint
        and accepted_revision_fingerprint != head_revision_fingerprint
    ):
        raise ValueError("accepted revision does not match the authority head")

    # The candidate plan is not an accepted denominator.  The only source of
    # groups/axes/product identities is the content-addressed contract loaded
    # by the current authority state.  Older heads intentionally have no
    # contract and therefore remain scoped/blocked for broad partitioned
    # claims.
    accepted_contract = getattr(
        authority_state,
        "accepted_boundary_contract",
        None,
    )
    if accepted_contract is None:
        raise ValueError(
            "partition denominator requires an accepted boundary contract"
        )
    contract_snapshot_fingerprint = str(
        getattr(accepted_contract, "snapshot_fingerprint", "")
    ).strip()
    contract_revision_fingerprint = str(
        getattr(accepted_contract, "accepted_revision_set_fingerprint", "")
    ).strip()
    if contract_snapshot_fingerprint and contract_snapshot_fingerprint != snapshot_fingerprint:
        raise ValueError(
            "accepted boundary contract does not match the authority snapshot"
        )
    if (
        accepted_revision_fingerprint
        and contract_revision_fingerprint
        and contract_revision_fingerprint != accepted_revision_fingerprint
    ):
        raise ValueError(
            "accepted boundary contract does not match the accepted revision"
        )
    contract_model_id = str(getattr(accepted_contract, "model_id", "")).strip()
    if not contract_model_id:
        raise ValueError("accepted boundary contract model identity is incomplete")
    if model_id and contract_model_id != str(model_id).strip():
        raise ValueError(
            "accepted boundary contract belongs to a different model"
        )
    model_id = model_id or contract_model_id

    lifecycle = str(getattr(snapshot, "lifecycle", "")).strip()
    subject_lane = str(getattr(snapshot, "subject_lane", "")).strip()
    if lifecycle != "active" or subject_lane != "observed_implementation":
        raise ValueError(
            "partition denominator requires an active observed implementation snapshot"
        )
    coverage = getattr(snapshot, "coverage", None)
    if coverage is None or not bool(getattr(coverage, "complete", False)):
        raise ValueError(
            "partition denominator requires a complete accepted authority coverage universe"
        )
    if tuple(getattr(snapshot, "unresolved_gap_ids", ())) or str(
        getattr(snapshot, "coverage_status", "")
    ) != "complete_within_declared_boundary":
        raise ValueError(
            "partition denominator cannot be derived from an authority with unresolved gaps"
        )

    try:
        axes = tuple(
            axis
            if isinstance(axis, ContractAxis)
            else ContractAxis(**dict(axis))
            for axis in getattr(accepted_contract, "axis_payloads", ())
        )
        groups = tuple(
            group
            if isinstance(group, ContractInteractionGroup)
            else ContractInteractionGroup(**dict(group))
            for group in getattr(accepted_contract, "interaction_group_payloads", ())
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"accepted boundary contract has invalid axis/group payloads: {exc}"
        ) from exc
    if not axes:
        raise ValueError("accepted boundary contract requires finite axes")
    if any(not axis.is_self_consistent() for axis in axes):
        raise ValueError("accepted boundary contract contains a stale axis")
    if not groups:
        raise ValueError("accepted boundary contract requires interaction groups")
    group_ids = tuple(str(group.group_id) for group in groups)
    if len(set(group_ids)) != len(group_ids):
        raise ValueError("partition denominator requires unique interaction groups")
    if any(
        not isinstance(group.product_signature, ContractProductSignature)
        or not group.product_signature.is_self_consistent()
        for group in groups
    ):
        raise ValueError(
            "accepted boundary contract requires self-consistent product signatures"
        )
    accepted_axis_ids = {axis.axis_id for axis in axes}
    if any(
        not set(group.axis_ids) <= accepted_axis_ids
        for group in groups
    ):
        raise ValueError(
            "accepted boundary contract group references an unknown axis"
        )

    def _endpoint_model_id(endpoint: Any) -> str:
        endpoint_id = str(getattr(endpoint, "endpoint_id", ""))
        endpoint_kind = str(getattr(endpoint, "endpoint_kind", ""))
        if endpoint_kind == "model_instance":
            return endpoint_id.removeprefix("model:")
        return ""

    def _canonical_relation(relation: Any) -> CanonicalRelation:
        evidence_ids = tuple(
            str(item).strip()
            for item in getattr(relation, "evidence_fingerprints", ())
            if str(item).strip()
        )
        if not evidence_ids:
            raise ValueError(
                f"accepted authority relation {getattr(relation, 'relation_id', '')!r} has no evidence fingerprint"
            )
        source = getattr(relation, "source", None)
        target = getattr(relation, "target", None)
        if source is None or target is None:
            raise ValueError("accepted authority relation has incomplete endpoints")
        return CanonicalRelation(
            relation_id=str(relation.relation_id),
            relation_type=str(relation.kind),
            source_endpoint_kind=str(source.endpoint_kind),
            source_endpoint_id=str(source.endpoint_id),
            target_endpoint_kind=str(target.endpoint_kind),
            target_endpoint_id=str(target.endpoint_id),
            source_ids=evidence_ids,
            metadata={
                "authority_snapshot_fingerprint": snapshot_fingerprint,
                "authority_head_fingerprint": head_fingerprint,
            },
        )

    model_relations = tuple(getattr(snapshot, "relations", ()))
    if not model_relations:
        raise ValueError("accepted authority snapshot has no topology relations")
    canonical_relations = tuple(_canonical_relation(relation) for relation in model_relations)

    accepted_relation_map = getattr(accepted_contract, "group_relation_ids", {})
    if not isinstance(accepted_relation_map, Mapping):
        raise ValueError("accepted boundary contract relation bindings are invalid")
    current_relation_ids = {
        str(relation.relation_id) for relation in model_relations
    }
    if set(accepted_relation_map) != set(group_ids):
        raise ValueError(
            "accepted boundary contract relation bindings do not cover every group"
        )
    group_relation_ids: dict[str, tuple[str, ...]] = {}
    all_required_model_ids = {str(model_id).strip()} - {""}
    for group in groups:
        group_owner_model_id = str(group.model_id or model_id).strip()
        group_model_ids = {
            group_owner_model_id,
            *(
                str(interface_model_id).strip()
                for interface_model_id in group.interface_model_ids
            ),
        } - {""}
        all_required_model_ids.update(group_model_ids)
        selected = tuple(
            str(relation_id).strip()
            for relation_id in accepted_relation_map.get(group.group_id, ())
            if str(relation_id).strip()
        )
        if not selected:
            raise ValueError(
                f"accepted boundary contract has no topology relation for interaction group {group.group_id!r}"
            )
        if len(selected) != len(set(selected)):
            raise ValueError(
                f"accepted boundary contract repeats a relation for interaction group {group.group_id!r}"
            )
        if not set(selected) <= current_relation_ids:
            raise ValueError(
                f"accepted boundary contract references an unmaterialized relation for interaction group {group.group_id!r}"
            )
        group_relation_ids[str(group.group_id)] = selected

    selected_relation_ids = tuple(
        dict.fromkeys(
            relation_id
            for group_id in group_ids
            for relation_id in group_relation_ids[group_id]
        )
    )
    selected_relation_set = set(selected_relation_ids)
    handoff_relations = tuple(
        relation for relation in canonical_relations if relation.relation_id in selected_relation_set
    )
    if {relation.relation_id for relation in handoff_relations} != selected_relation_set:
        raise ValueError("accepted authority relation denominator is not materialized")
    topology_fingerprint = boundary_topology_fingerprint(
        tuple(getattr(snapshot, "model_instances", ())),
        canonical_relations,
    )
    accepted_topology_fingerprint = str(
        getattr(accepted_contract, "topology_fingerprint", "")
    ).strip()
    if accepted_topology_fingerprint != topology_fingerprint:
        raise ValueError(
            "accepted boundary contract topology fingerprint is stale"
        )
    boundary_source_id = str(getattr(coverage, "boundary_id", "")).strip()
    boundary_source_fingerprint = str(getattr(coverage, "fingerprint", "")).strip()
    if not boundary_source_id or not boundary_source_fingerprint:
        raise ValueError("accepted authority coverage boundary identity is incomplete")
    handoff = CanonicalRelationHandoff(
        relations=handoff_relations,
        affected_model_ids=tuple(sorted(all_required_model_ids)),
        evidence_current=True,
        metadata={
            "boundary_source_id": boundary_source_id,
            "boundary_source_fingerprint": boundary_source_fingerprint,
            "authority_snapshot_fingerprint": snapshot_fingerprint,
            "authority_head_fingerprint": head_fingerprint,
            "accepted_revision_fingerprint": accepted_revision_fingerprint,
            "topology_fingerprint": topology_fingerprint,
        },
    )
    return _PartitionedProductVerificationContext(
        boundary_source_id=boundary_source_id,
        boundary_source_fingerprint=boundary_source_fingerprint,
        model_authority_head_fingerprint=head_fingerprint,
        topology_fingerprint=topology_fingerprint,
        canonical_relation_handoff=handoff,
        required_groups=groups,
        required_axes=axes,
        group_relation_ids=group_relation_ids,
    )


def _partitioned_product_findings(
    plan: "ContractExhaustionPlan",
    context: _PartitionedProductVerificationContext | None,
    combination_cases: Sequence[ContractCombinationCase],
    coverage_receipts: Sequence[ModelContractCoverageReceipt],
) -> tuple[ContractExhaustionFinding, ...]:
    """Check the independently derived denominator for a partitioned claim."""

    universe = plan.coverage_universe
    if universe is None or not universe.allow_partitioned_product:
        return ()
    if context is None:
        return (
            _finding(
                "partition_boundary_verification_missing",
                "partitioned coverage has no authority-derived boundary denominator",
                severity=(
                    CONTRACT_EXHAUSTION_FINDING_BLOCKER
                    if plan.claim_scope in _BROAD_CLAIMS
                    else CONTRACT_EXHAUSTION_FINDING_GAP
                ),
                action=(
                    "supply the current boundary/topology context or narrow the claim "
                    "to scoped composition"
                ),
            ),
        )

    findings: list[ContractExhaustionFinding] = []
    metadata = dict(plan.metadata)
    expected_identity = {
        "boundary_source_fingerprint": metadata.get("boundary_source_fingerprint"),
        "model_authority_head_fingerprint": metadata.get(
            "model_authority_head_fingerprint"
        ),
        "topology_fingerprint": metadata.get("topology_fingerprint"),
    }
    actual_identity = {
        "boundary_source_fingerprint": context.boundary_source_fingerprint,
        "model_authority_head_fingerprint": context.model_authority_head_fingerprint,
        "topology_fingerprint": context.topology_fingerprint,
    }
    mismatches = {
        key: {"expected": value, "actual": actual_identity[key]}
        for key, value in expected_identity.items()
        if value and str(value) != actual_identity[key]
    }
    if mismatches or not context.canonical_relation_handoff.evidence_current:
        findings.append(
            _finding(
                "partition_boundary_stale",
                "partition boundary or canonical relation handoff is not current for the plan",
                action="rebuild the authority-derived partition context for the current head",
                metadata={"mismatches": mismatches},
            )
        )

    required_relations = {
        relation_id
        for relation_ids in context.group_relation_ids.values()
        for relation_id in relation_ids
    }
    omitted_relations = sorted(
        required_relations - set(universe.required_relation_ids)
    )
    if omitted_relations:
        findings.append(
            _finding(
                "partition_required_relation_omitted",
                "partition universe omits an authority-derived relation in the coupling denominator",
                action="declare every required relation or narrow the claim",
                metadata={"relation_ids": omitted_relations},
            )
        )
    expected_group_ids = {group.group_id for group in context.required_groups}
    omitted_groups = sorted(
        expected_group_ids - set(universe.required_interaction_group_ids)
    )
    if omitted_groups:
        findings.append(
            _finding(
                "partition_required_group_omitted",
                "partition universe omits an authority-derived interaction group",
                action="declare every required interaction group or narrow the claim",
                metadata={"group_ids": omitted_groups},
            )
        )

    declared_groups = {group.group_id: group for group in plan.interaction_groups}
    declared_axes = {axis.axis_id: axis for axis in plan.axes}
    handoff_relation_ids = set(context.canonical_relation_handoff.relation_ids)
    handoff_relations = {
        relation.relation_id: relation
        for relation in context.canonical_relation_handoff.relations
    }
    combination_cases_by_id = {
        case.case_id: case for case in combination_cases
    }

    def _relation_model_ids(relation: CanonicalRelation) -> set[str]:
        model_ids: set[str] = set()
        for endpoint_kind, endpoint_id in (
            (relation.source_endpoint_kind, relation.source_endpoint_id),
            (relation.target_endpoint_kind, relation.target_endpoint_id),
        ):
            endpoint_text = str(endpoint_id)
            if endpoint_kind in {"model", "model_instance"} or endpoint_text.startswith(
                "model:"
            ):
                model_ids.add(endpoint_text.removeprefix("model:"))
        return model_ids

    accepted_group_axis_ids = {
        axis_id
        for group in context.required_groups
        for axis_id in group.axis_ids
    }
    for expected_axis in context.required_axes:
        if expected_axis.axis_id not in accepted_group_axis_ids:
            continue
        actual_axis = declared_axes.get(expected_axis.axis_id)
        if actual_axis is None or actual_axis.axis_fingerprint != expected_axis.axis_fingerprint:
            findings.append(
                _finding(
                    "partition_axis_boundary_mismatch",
                    "declared axis does not match the accepted finite axis boundary",
                    action="bind the candidate axis to the exact accepted values and identity",
                    metadata={
                        "axis_id": expected_axis.axis_id,
                        "accepted_axis_fingerprint": expected_axis.axis_fingerprint,
                        "declared_axis_fingerprint": (
                            actual_axis.axis_fingerprint if actual_axis is not None else ""
                        ),
                    },
                )
            )

    for expected_group in context.required_groups:
        actual_group = declared_groups.get(expected_group.group_id)
        if actual_group is None or any(
            getattr(actual_group, field_name) != getattr(expected_group, field_name)
            for field_name in (
                "axis_ids",
                "interface_model_ids",
                "parent_interface_contract_id",
                "refinement_contract_id",
                "generation_kind",
            )
        ):
            findings.append(
                _finding(
                    "partition_group_boundary_mismatch",
                    "declared interaction group does not match the accepted boundary group",
                    action="bind the candidate group to the exact accepted axes, interfaces, and contracts",
                    metadata={"group_id": expected_group.group_id},
                )
            )
            continue
        expected_model_ids = {
            str(expected_group.model_id).removeprefix("model:").strip(),
            *(
                str(interface_model_id).removeprefix("model:").strip()
                for interface_model_id in expected_group.interface_model_ids
            ),
        } - {""}
        for relation_id in context.group_relation_ids[expected_group.group_id]:
            materialized_groups = set(plan.relation_materializations.get(relation_id, ()))
            relation = handoff_relations.get(relation_id)
            if (
                relation_id not in handoff_relation_ids
                or expected_group.group_id not in materialized_groups
            ):
                findings.append(
                    _finding(
                        "partition_relation_materialization_missing",
                        "partition interaction group is not materialized by its accepted relation",
                        action="materialize the exact relation/group handoff before claiming global coverage",
                        metadata={
                            "group_id": expected_group.group_id,
                            "relation_id": relation_id,
                        },
                    )
                )
            elif expected_model_ids and not (
                expected_model_ids & _relation_model_ids(relation)
            ):
                findings.append(
                    _finding(
                        "partition_group_boundary_mismatch",
                        "accepted relation does not bind the declared interaction group's model boundary",
                        action="bind each interaction group only to its exact accepted model/interface relation",
                        metadata={
                            "group_id": expected_group.group_id,
                            "relation_id": relation_id,
                            "expected_model_ids": sorted(expected_model_ids),
                            "relation_model_ids": sorted(_relation_model_ids(relation)),
                        },
                    )
                )
        expected_signature = expected_group.product_signature
        actual_signature = None
        if isinstance(expected_signature, ContractProductSignature):
            try:
                actual_axes = tuple(
                    declared_axes[axis_id] for axis_id in actual_group.axis_ids
                )
                actual_signature = build_contract_product_signature(
                    plan,
                    actual_group,
                    axes=actual_axes,
                )
            except (KeyError, TypeError, ValueError):
                actual_signature = None
            if (
                actual_signature is None
                or actual_signature.fingerprint != expected_signature.fingerprint
            ):
                findings.append(
                    _finding(
                        "partition_product_signature_mismatch",
                        "declared interaction-group product does not match the accepted coupling denominator",
                        action="regenerate the candidate product from the accepted axes and partition revision",
                        metadata={
                            "group_id": expected_group.group_id,
                            "accepted_product_signature": expected_signature.to_dict(),
                            "declared_product_signature": (
                                actual_signature.to_dict()
                                if actual_signature is not None
                                else None
                            ),
                        },
                    )
                )
        receipts = [
            receipt
            for receipt in coverage_receipts
            if expected_group.group_id in receipt.interaction_group_ids
        ]
        if isinstance(expected_group.product_signature, ContractProductSignature):
            expected_cardinality = expected_group.product_signature.expected_cardinality
        elif isinstance(actual_group.product_signature, ContractProductSignature):
            expected_cardinality = actual_group.product_signature.expected_cardinality
        elif isinstance(actual_group.product_signature, Mapping):
            expected_cardinality = int(actual_group.product_signature.get("expected_cardinality", 0))
        else:
            expected_cardinality = 0
        expected_case_ids = tuple(
            case.case_id
            for case in combination_cases
            if case.interaction_group_id == expected_group.group_id
        )
        expected_case_set = set(expected_case_ids)
        receipt_cell_gaps: list[dict[str, Any]] = []
        for receipt in receipts:
            receipt_case_ids = tuple(
                case_id
                for case_id in receipt.covered_case_ids
                if (
                    combination_cases_by_id.get(case_id) is None
                    or combination_cases_by_id[case_id].interaction_group_id
                    == expected_group.group_id
                )
            )
            receipt_case_set = set(receipt_case_ids)
            receipt_unknown_ids = tuple(
                sorted(
                    case_id
                    for case_id in receipt_case_set
                    if case_id not in combination_cases_by_id
                )
            )
            receipt_missing_ids = tuple(sorted(expected_case_set - receipt_case_set))
            receipt_duplicate_ids = tuple(
                sorted(
                    case_id
                    for case_id, count in Counter(receipt_case_ids).items()
                    if count > 1
                )
            )
            if receipt_missing_ids or receipt_unknown_ids or receipt_duplicate_ids:
                receipt_cell_gaps.append(
                    {
                        "receipt_id": receipt.receipt_id,
                        "missing_case_ids": list(receipt_missing_ids),
                        "foreign_case_ids": list(receipt_unknown_ids),
                        "duplicate_case_ids": list(receipt_duplicate_ids),
                    }
                )
        covered_case_ids = tuple(
            case_id
            for receipt in receipts
            for case_id in receipt.covered_case_ids
            if (
                combination_cases_by_id.get(case_id) is None
                or combination_cases_by_id[case_id].interaction_group_id
                == expected_group.group_id
            )
        )
        expected_case_set = set(expected_case_ids)
        covered_case_set = set(covered_case_ids)
        missing_case_ids = tuple(sorted(expected_case_set - covered_case_set))
        foreign_case_ids = tuple(sorted(covered_case_set - expected_case_set))
        covered_case_counts = Counter(covered_case_ids)
        duplicate_case_ids = tuple(
            sorted(
                case_id
                for case_id, count in covered_case_counts.items()
                if count > 1
            )
        )
        covered_count = len(covered_case_set)
        if not receipts or any(not receipt.complete() for receipt in receipts) or (
            expected_cardinality and covered_count < expected_cardinality
        ) or missing_case_ids or foreign_case_ids or duplicate_case_ids or receipt_cell_gaps:
            findings.append(
                _finding(
                    "partition_group_coverage_incomplete",
                    "partition interaction group lacks a current complete finite coverage receipt",
                    action="execute every required finite cell and bind the parent receipt",
                    metadata={
                        "group_id": expected_group.group_id,
                        "expected_cardinality": expected_cardinality,
                        "covered_count": covered_count,
                        "missing_case_ids": list(missing_case_ids),
                        "foreign_case_ids": list(foreign_case_ids),
                        "duplicate_case_ids": list(duplicate_case_ids),
                        "receipt_cell_gaps": receipt_cell_gaps,
                        "combination_case_count": sum(
                            1
                            for case in combination_cases
                            if case.interaction_group_id == expected_group.group_id
                        ),
                    },
                )
            )
    return tuple(findings)


@dataclass(frozen=True)
class ContractFaultProfile:
    """Generic synthetic bad-submitter profile derived from a contract case."""

    profile_id: str
    source_case_id: str
    mutation_type: str = ""
    contract_path: str = ""
    expected_status: str = ""
    expected_message_fields: tuple[str, ...] = ()
    required_repair_fields: tuple[str, ...] = ()
    retry_class: str = ""
    synthetic_only: bool = True
    live_completion_allowed: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", str(self.profile_id))
        object.__setattr__(self, "source_case_id", str(self.source_case_id))
        object.__setattr__(self, "mutation_type", str(self.mutation_type))
        object.__setattr__(self, "contract_path", str(self.contract_path))
        object.__setattr__(self, "expected_status", str(self.expected_status))
        object.__setattr__(self, "expected_message_fields", _as_tuple(self.expected_message_fields))
        object.__setattr__(self, "required_repair_fields", _as_tuple(self.required_repair_fields))
        object.__setattr__(self, "retry_class", str(self.retry_class))
        object.__setattr__(self, "synthetic_only", bool(self.synthetic_only))
        object.__setattr__(self, "live_completion_allowed", bool(self.live_completion_allowed))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "source_case_id": self.source_case_id,
            "mutation_type": self.mutation_type,
            "contract_path": self.contract_path,
            "expected_status": self.expected_status,
            "expected_message_fields": list(self.expected_message_fields),
            "required_repair_fields": list(self.required_repair_fields),
            "retry_class": self.retry_class,
            "synthetic_only": self.synthetic_only,
            "live_completion_allowed": self.live_completion_allowed,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ObservedProblemBackfeed:
    """A real miss that must map back into canonical generated coverage."""

    problem_id: str
    observed_failure: str = ""
    failure_mode: str = ""
    affected_dimension_ids: tuple[str, ...] = ()
    affected_axis_ids: tuple[str, ...] = ()
    affected_interaction_group_ids: tuple[str, ...] = ()
    affected_payload_contract_ids: tuple[str, ...] = ()
    affected_boundary_ids: tuple[str, ...] = ()
    matched_case_ids: tuple[str, ...] = ()
    matched_combination_case_ids: tuple[str, ...] = ()
    matched_coverage_receipt_ids: tuple[str, ...] = ()
    same_class_case_ids: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", str(self.problem_id))
        object.__setattr__(self, "observed_failure", str(self.observed_failure))
        object.__setattr__(self, "failure_mode", str(self.failure_mode))
        object.__setattr__(self, "affected_dimension_ids", _as_tuple(self.affected_dimension_ids))
        object.__setattr__(self, "affected_axis_ids", _as_tuple(self.affected_axis_ids))
        object.__setattr__(
            self,
            "affected_interaction_group_ids",
            _as_tuple(self.affected_interaction_group_ids),
        )
        object.__setattr__(
            self,
            "affected_payload_contract_ids",
            _as_tuple(self.affected_payload_contract_ids),
        )
        object.__setattr__(self, "affected_boundary_ids", _as_tuple(self.affected_boundary_ids))
        object.__setattr__(self, "matched_case_ids", _as_tuple(self.matched_case_ids))
        object.__setattr__(
            self,
            "matched_combination_case_ids",
            _as_tuple(self.matched_combination_case_ids),
        )
        object.__setattr__(
            self,
            "matched_coverage_receipt_ids",
            _as_tuple(self.matched_coverage_receipt_ids),
        )
        object.__setattr__(self, "same_class_case_ids", _as_tuple(self.same_class_case_ids))
        object.__setattr__(self, "source_refs", _as_tuple(self.source_refs))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "observed_failure": self.observed_failure,
            "failure_mode": self.failure_mode,
            "affected_dimension_ids": list(self.affected_dimension_ids),
            "affected_axis_ids": list(self.affected_axis_ids),
            "affected_interaction_group_ids": list(self.affected_interaction_group_ids),
            "affected_payload_contract_ids": list(self.affected_payload_contract_ids),
            "affected_boundary_ids": list(self.affected_boundary_ids),
            "matched_case_ids": list(self.matched_case_ids),
            "matched_combination_case_ids": list(self.matched_combination_case_ids),
            "matched_coverage_receipt_ids": list(self.matched_coverage_receipt_ids),
            "same_class_case_ids": list(self.same_class_case_ids),
            "source_refs": list(self.source_refs),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ObservedProblemBackfeedReport:
    """Review result for observed problems backfed into the generated matrix."""

    ok: bool
    decision: str
    checked_problem_count: int = 0
    mapped_problem_ids: tuple[str, ...] = ()
    unmapped_problem_ids: tuple[str, ...] = ()
    findings: tuple[ContractExhaustionFinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "checked_problem_count", int(self.checked_problem_count))
        object.__setattr__(self, "mapped_problem_ids", _as_tuple(self.mapped_problem_ids))
        object.__setattr__(self, "unmapped_problem_ids", _as_tuple(self.unmapped_problem_ids))
        object.__setattr__(self, "findings", tuple(self.findings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "checked_problem_count": self.checked_problem_count,
            "mapped_problem_ids": list(self.mapped_problem_ids),
            "unmapped_problem_ids": list(self.unmapped_problem_ids),
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class ContractExhaustionPlan:
    """A normalized contract-exhaustion request."""

    plan_id: str
    dimensions: tuple[ContractDimension, ...] = ()
    seed_cases: tuple[ContractMutationCase, ...] = ()
    oracles: tuple[ContractOracle, ...] = ()
    claim_scope: str = "routine"
    require_oracles_for_required_cases: bool = True
    source_model_ids: tuple[str, ...] = ()
    source_bug_refs: tuple[str, ...] = ()
    generation_policy: str = "bounded"
    allow_unbounded_scoped: bool = True
    required_route_ids: tuple[str, ...] = ()
    require_composite_handoff_acceptance: bool = True
    # Generating a composite handoff is a planning obligation.  Broad claims
    # always require the independently produced terminal result as an
    # execution gate; the explicit flag remains in the wire shape for narrow
    # callers that opt into the same check before broad admission.
    require_composite_handoff_results: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    model_id: str = ""
    parent_model_id: str = ""
    model_level: str = ""
    axes: tuple[ContractAxis, ...] = ()
    interaction_groups: tuple[ContractInteractionGroup, ...] = ()
    coverage_shards: tuple[ContractCoverageShard, ...] = ()
    coverage_receipts: tuple[ModelContractCoverageReceipt, ...] = ()
    required_coverage_receipt_ids: tuple[str, ...] = ()
    required_child_receipt_ids: tuple[str, ...] = ()
    consumed_child_receipt_ids: tuple[str, ...] = ()
    composite_handoff_results: tuple[CompositeHandoffResult | Mapping[str, Any], ...] = ()
    require_model_coverage_receipt: bool = False
    cartesian_case_limit: int = DEFAULT_CARTESIAN_CASE_LIMIT
    coverage_universe: ContractCoverageUniverse | None = None
    require_coverage_universe: bool = False
    require_actionable_oracle_feedback: bool = False
    observed_problem_backfeed: tuple[ObservedProblemBackfeed, ...] = ()
    inventory_revision: str = ""
    inventory_current: bool = True
    expected_family_member_ids: tuple[str, ...] = ()
    materialized_family_member_ids: tuple[str, ...] = ()
    scoped_family_member_reasons: Mapping[str, str] = field(default_factory=dict)
    require_family_inventory: bool = False
    expected_reduction_candidate_ids: tuple[str, ...] = ()
    materialized_reduction_candidate_ids: tuple[str, ...] = ()
    scoped_reduction_candidate_reasons: Mapping[str, str] = field(default_factory=dict)
    require_reduction_inventory: bool = False
    canonical_relation_handoff: CanonicalRelationHandoff | Mapping[str, Any] | None = None
    relation_materializations: Mapping[str, Sequence[str]] = field(default_factory=dict)
    scoped_relation_reasons: Mapping[str, str] = field(default_factory=dict)
    # Strict parent coverage resolution is deliberately explicit.  The plan
    # supplies a canonical receipt store and independently derived verifier
    # contexts; if either is absent, full/release parent claims block rather
    # than falling back to the report's child-id set.
    native_receipt_store_repository_root: str = ""
    native_receipt_store_output_directory: str = ""
    native_receipt_verification_contexts: Mapping[str, Any] = field(default_factory=dict)
    # Invocation-local authority denominator.  It is intentionally not part
    # of the serialized plan identity; the handoff, fingerprints, and
    # materialization rows below are the persisted proof inputs.
    partition_context: _PartitionedProductVerificationContext | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "dimensions", tuple(self.dimensions))
        object.__setattr__(self, "seed_cases", tuple(self.seed_cases))
        object.__setattr__(self, "oracles", tuple(self.oracles))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "source_model_ids", _as_tuple(self.source_model_ids))
        object.__setattr__(self, "source_bug_refs", _as_tuple(self.source_bug_refs))
        object.__setattr__(self, "generation_policy", str(self.generation_policy))
        object.__setattr__(self, "allow_unbounded_scoped", bool(self.allow_unbounded_scoped))
        object.__setattr__(self, "required_route_ids", _as_tuple(self.required_route_ids))
        object.__setattr__(
            self,
            "require_composite_handoff_acceptance",
            bool(self.require_composite_handoff_acceptance),
        )
        object.__setattr__(
            self,
            "require_composite_handoff_results",
            bool(
                self.require_composite_handoff_results
                or self.claim_scope in _BROAD_CLAIMS
            ),
        )
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "model_level", str(self.model_level))
        object.__setattr__(self, "axes", tuple(self.axes))
        object.__setattr__(self, "interaction_groups", tuple(self.interaction_groups))
        object.__setattr__(self, "coverage_shards", tuple(self.coverage_shards))
        object.__setattr__(self, "coverage_receipts", tuple(self.coverage_receipts))
        object.__setattr__(self, "required_coverage_receipt_ids", _as_tuple(self.required_coverage_receipt_ids))
        object.__setattr__(self, "required_child_receipt_ids", _as_tuple(self.required_child_receipt_ids))
        object.__setattr__(self, "consumed_child_receipt_ids", _as_tuple(self.consumed_child_receipt_ids))
        object.__setattr__(
            self,
            "composite_handoff_results",
            tuple(
                result
                if isinstance(result, CompositeHandoffResult)
                else CompositeHandoffResult(
                    result_id=str(result.get("result_id", "")),
                    acceptance_id=str(result.get("acceptance_id", "")),
                    status=str(result.get("status", CONTRACT_COVERAGE_STATUS_COVERED)),
                    current=bool(result.get("current", True)),
                    result_fingerprint=str(result.get("result_fingerprint", "")),
                    covered_route_ids=result.get("covered_route_ids", ()),
                    evidence_ids=result.get("evidence_ids", ()),
                    metadata=result.get("metadata", {}),
                )
                for result in self.composite_handoff_results
            ),
        )
        object.__setattr__(self, "require_model_coverage_receipt", bool(self.require_model_coverage_receipt))
        object.__setattr__(self, "cartesian_case_limit", int(self.cartesian_case_limit))
        object.__setattr__(self, "coverage_universe", self.coverage_universe)
        object.__setattr__(self, "require_coverage_universe", bool(self.require_coverage_universe))
        object.__setattr__(
            self,
            "require_actionable_oracle_feedback",
            bool(self.require_actionable_oracle_feedback),
        )
        object.__setattr__(
            self,
            "observed_problem_backfeed",
            tuple(self.observed_problem_backfeed),
        )
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "inventory_current", bool(self.inventory_current))
        object.__setattr__(self, "expected_family_member_ids", _as_tuple(self.expected_family_member_ids))
        object.__setattr__(
            self,
            "materialized_family_member_ids",
            _as_tuple(self.materialized_family_member_ids),
        )
        object.__setattr__(
            self,
            "scoped_family_member_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_family_member_reasons).items()},
        )
        object.__setattr__(self, "require_family_inventory", bool(self.require_family_inventory))
        object.__setattr__(
            self,
            "expected_reduction_candidate_ids",
            _as_tuple(self.expected_reduction_candidate_ids),
        )
        object.__setattr__(
            self,
            "materialized_reduction_candidate_ids",
            _as_tuple(self.materialized_reduction_candidate_ids),
        )
        object.__setattr__(
            self,
            "scoped_reduction_candidate_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_reduction_candidate_reasons).items()},
        )
        object.__setattr__(self, "require_reduction_inventory", bool(self.require_reduction_inventory))
        object.__setattr__(
            self,
            "canonical_relation_handoff",
            normalize_canonical_relation_handoff(self.canonical_relation_handoff),
        )
        object.__setattr__(
            self,
            "relation_materializations",
            {str(key): _as_tuple(value) for key, value in dict(self.relation_materializations).items()},
        )
        object.__setattr__(
            self,
            "scoped_relation_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_relation_reasons).items()},
        )
        object.__setattr__(
            self,
            "native_receipt_store_repository_root",
            str(self.native_receipt_store_repository_root),
        )
        object.__setattr__(
            self,
            "native_receipt_store_output_directory",
            str(self.native_receipt_store_output_directory),
        )
        object.__setattr__(
            self,
            "native_receipt_verification_contexts",
            {str(key): value for key, value in dict(self.native_receipt_verification_contexts).items()},
        )
        if self.partition_context is not None and not isinstance(
            self.partition_context,
            _PartitionedProductVerificationContext,
        ):
            object.__setattr__(
                self,
                "partition_context",
                _PartitionedProductVerificationContext(**dict(self.partition_context)),
            )

    def oracle_ids(self) -> set[str]:
        return {oracle.oracle_id for oracle in self.oracles}

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "dimensions": [dimension.to_dict() for dimension in self.dimensions],
            "seed_cases": [case.to_dict() for case in self.seed_cases],
            "oracles": [oracle.to_dict() for oracle in self.oracles],
            "claim_scope": self.claim_scope,
            "require_oracles_for_required_cases": self.require_oracles_for_required_cases,
            "source_model_ids": list(self.source_model_ids),
            "source_bug_refs": list(self.source_bug_refs),
            "generation_policy": self.generation_policy,
            "allow_unbounded_scoped": self.allow_unbounded_scoped,
            "required_route_ids": list(self.required_route_ids),
            "require_composite_handoff_acceptance": self.require_composite_handoff_acceptance,
            "require_composite_handoff_results": self.require_composite_handoff_results,
            "metadata": to_jsonable(dict(self.metadata)),
            "model_id": self.model_id,
            "parent_model_id": self.parent_model_id,
            "model_level": self.model_level,
            "axes": [axis.to_dict() for axis in self.axes],
            "interaction_groups": [group.to_dict() for group in self.interaction_groups],
            "coverage_shards": [shard.to_dict() for shard in self.coverage_shards],
            "coverage_receipts": [receipt.to_dict() for receipt in self.coverage_receipts],
            "required_coverage_receipt_ids": list(self.required_coverage_receipt_ids),
            "required_child_receipt_ids": list(self.required_child_receipt_ids),
            "consumed_child_receipt_ids": list(self.consumed_child_receipt_ids),
            "composite_handoff_results": [
                result.to_dict() for result in self.composite_handoff_results
            ],
            "require_model_coverage_receipt": self.require_model_coverage_receipt,
            "cartesian_case_limit": self.cartesian_case_limit,
            "coverage_universe": (
                self.coverage_universe.to_dict()
                if self.coverage_universe is not None
                else None
            ),
            "require_coverage_universe": self.require_coverage_universe,
            "require_actionable_oracle_feedback": self.require_actionable_oracle_feedback,
            "observed_problem_backfeed": [
                problem.to_dict()
                for problem in self.observed_problem_backfeed
            ],
            "inventory_revision": self.inventory_revision,
            "inventory_current": self.inventory_current,
            "expected_family_member_ids": list(self.expected_family_member_ids),
            "materialized_family_member_ids": list(self.materialized_family_member_ids),
            "scoped_family_member_reasons": to_jsonable(dict(self.scoped_family_member_reasons)),
            "require_family_inventory": self.require_family_inventory,
            "expected_reduction_candidate_ids": list(self.expected_reduction_candidate_ids),
            "materialized_reduction_candidate_ids": list(self.materialized_reduction_candidate_ids),
            "scoped_reduction_candidate_reasons": to_jsonable(dict(self.scoped_reduction_candidate_reasons)),
            "require_reduction_inventory": self.require_reduction_inventory,
            "canonical_relation_handoff": self.canonical_relation_handoff.to_dict() if self.canonical_relation_handoff else None,
            "relation_materializations": {
                key: list(values) for key, values in self.relation_materializations.items()
            },
            "scoped_relation_reasons": to_jsonable(dict(self.scoped_relation_reasons)),
            "native_receipt_store_repository_root": self.native_receipt_store_repository_root,
            "native_receipt_store_output_directory": self.native_receipt_store_output_directory,
            "native_receipt_verification_context_ids": sorted(
                self.native_receipt_verification_contexts
            ),
        }


def bind_partition_context_to_plan(
    plan: ContractExhaustionPlan,
    *,
    authority_state: Any | None = None,
    partition_context: _PartitionedProductVerificationContext | None = None,
) -> ContractExhaustionPlan:
    """Bind one accepted authority denominator to a finite matrix plan.

    The helper is used by the BCL and PPA plan builders.  It copies only the
    exact authority identities and relation/group materializations needed by
    the plan; it never fabricates a boundary when no accepted state is given.
    Existing caller-supplied identities are retained so a stale or foreign
    handoff remains visible to the hard gate instead of being overwritten.
    """

    if authority_state is not None and partition_context is not None:
        raise ValueError("supply authority_state or partition_context, not both")
    context = partition_context
    if context is None and authority_state is not None:
        context = partition_context_from_accepted_authority(
            authority_state,
            model_id=plan.model_id,
        )
    if context is None:
        return plan
    relation_ids = tuple(
        dict.fromkeys(
            relation_id
            for group_id in sorted(context.group_relation_ids)
            for relation_id in context.group_relation_ids[group_id]
        )
    )
    relation_materializations = {
        str(key): _as_tuple(value)
        for key, value in plan.relation_materializations.items()
    }
    groups_for_relation: dict[str, list[str]] = {}
    for group_id, group_relation_ids in context.group_relation_ids.items():
        for relation_id in group_relation_ids:
            groups_for_relation.setdefault(str(relation_id), []).append(str(group_id))
    for relation_id, group_ids in groups_for_relation.items():
        relation_materializations.setdefault(relation_id, tuple(dict.fromkeys(group_ids)))

    metadata = dict(plan.metadata)
    metadata.setdefault(
        "boundary_source_id",
        context.boundary_source_id,
    )
    metadata.setdefault(
        "boundary_source_fingerprint",
        context.boundary_source_fingerprint,
    )
    metadata.setdefault(
        "model_authority_head_fingerprint",
        context.model_authority_head_fingerprint,
    )
    metadata.setdefault("topology_fingerprint", context.topology_fingerprint)
    universe = plan.coverage_universe
    if universe is not None:
        universe_metadata = dict(universe.metadata)
        universe_metadata.setdefault(
            "boundary_source_id",
            context.boundary_source_id,
        )
        universe_metadata.setdefault(
            "boundary_source_fingerprint",
            context.boundary_source_fingerprint,
        )
        universe_metadata.setdefault(
            "model_authority_head_fingerprint",
            context.model_authority_head_fingerprint,
        )
        universe_metadata.setdefault("topology_fingerprint", context.topology_fingerprint)
        universe = replace(
            universe,
            required_relation_ids=(
                universe.required_relation_ids or relation_ids
            ),
            metadata=universe_metadata,
        )
    return replace(
        plan,
        metadata=metadata,
        coverage_universe=universe,
        # Keep the invocation-local accepted handoff in ``partition_context``.
        # A route that already owns a canonical relation inventory may retain
        # its explicit plan handoff; the authority denominator itself must not
        # silently turn every topology edge into a new mutation case.
        canonical_relation_handoff=plan.canonical_relation_handoff,
        relation_materializations=relation_materializations,
        inventory_revision=(
            plan.inventory_revision
            or f"authority:{context.model_authority_head_fingerprint}"
        ),
        partition_context=context,
    )


@dataclass(frozen=True)
class ContractExhaustionReport:
    """Result of contract expansion and route handoff review."""

    plan_id: str
    ok: bool
    decision: str
    confidence: str
    generated_cases: tuple[ContractMutationCase, ...] = ()
    findings: tuple[ContractExhaustionFinding, ...] = ()
    required_route_case_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    composite_handoff_acceptances: tuple[CompositeHandoffAcceptance, ...] = ()
    composite_handoff_results: tuple[CompositeHandoffResult, ...] = ()
    missing_oracle_case_ids: tuple[str, ...] = ()
    model_gap_dimension_ids: tuple[str, ...] = ()
    summary: str = ""
    combination_cases: tuple[ContractCombinationCase, ...] = ()
    coverage_shards: tuple[ContractCoverageShard, ...] = ()
    product_signatures: tuple[ContractProductSignature, ...] = ()
    coverage_receipts: tuple[ModelContractCoverageReceipt, ...] = ()
    required_coverage_receipt_ids: tuple[str, ...] = ()
    coverage_universe: ContractCoverageUniverse | None = None
    contract_fault_profiles: tuple[ContractFaultProfile, ...] = ()
    observed_problem_backfeed_report: ObservedProblemBackfeedReport | None = None
    inventory_revision: str = ""
    omitted_family_member_ids: tuple[str, ...] = ()
    omitted_reduction_candidate_ids: tuple[str, ...] = ()
    materialized_relation_ids: tuple[str, ...] = ()
    unmaterialized_relation_ids: tuple[str, ...] = ()
    downstream_relation_obligation_ids: tuple[str, ...] = ()

    @property
    def required_mta_case_ids(self) -> tuple[str, ...]:
        return self.required_route_case_ids.get(CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT, ())

    @property
    def required_testmesh_case_ids(self) -> tuple[str, ...]:
        return self.required_route_case_ids.get(CONTRACT_ROUTE_TEST_MESH, ())

    @property
    def required_modelmesh_case_ids(self) -> tuple[str, ...]:
        return self.required_route_case_ids.get(CONTRACT_ROUTE_MODEL_MESH, ())

    @property
    def required_risk_case_ids(self) -> tuple[str, ...]:
        return self.required_route_case_ids.get(CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER, ())

    @property
    def required_composite_handoff_acceptance_ids(self) -> tuple[str, ...]:
        return tuple(
            acceptance.acceptance_id
            for acceptance in self.composite_handoff_acceptances
            if acceptance.required
        )

    @property
    def required_combination_case_ids(self) -> tuple[str, ...]:
        return tuple(case.case_id for case in self.combination_cases)

    @property
    def required_coverage_shard_ids(self) -> tuple[str, ...]:
        return tuple(shard.shard_id for shard in self.coverage_shards if shard.case_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "ok": self.ok,
            "decision": self.decision,
            "confidence": self.confidence,
            "generated_cases": [case.to_dict() for case in self.generated_cases],
            "findings": [finding.to_dict() for finding in self.findings],
            "required_route_case_ids": {
                route: list(case_ids)
                for route, case_ids in dict(self.required_route_case_ids).items()
            },
            "composite_handoff_acceptances": [
                acceptance.to_dict()
                for acceptance in self.composite_handoff_acceptances
            ],
            "composite_handoff_results": [
                result.to_dict() for result in self.composite_handoff_results
            ],
            "required_composite_handoff_acceptance_ids": list(
                self.required_composite_handoff_acceptance_ids
            ),
            "missing_oracle_case_ids": list(self.missing_oracle_case_ids),
            "model_gap_dimension_ids": list(self.model_gap_dimension_ids),
            "summary": self.summary,
            "combination_cases": [case.to_dict() for case in self.combination_cases],
            "coverage_shards": [shard.to_dict() for shard in self.coverage_shards],
            "product_signatures": [
                signature.to_dict() for signature in self.product_signatures
            ],
            "coverage_receipts": [receipt.to_dict() for receipt in self.coverage_receipts],
            "required_coverage_receipt_ids": list(self.required_coverage_receipt_ids),
            "required_combination_case_ids": list(self.required_combination_case_ids),
            "required_coverage_shard_ids": list(self.required_coverage_shard_ids),
            "coverage_universe": (
                self.coverage_universe.to_dict()
                if self.coverage_universe is not None
                else None
            ),
            "contract_fault_profiles": [
                profile.to_dict()
                for profile in self.contract_fault_profiles
            ],
            "observed_problem_backfeed_report": (
                self.observed_problem_backfeed_report.to_dict()
                if self.observed_problem_backfeed_report is not None
                else None
            ),
            "inventory_revision": self.inventory_revision,
            "omitted_family_member_ids": list(self.omitted_family_member_ids),
            "omitted_reduction_candidate_ids": list(self.omitted_reduction_candidate_ids),
            "materialized_relation_ids": list(self.materialized_relation_ids),
            "unmaterialized_relation_ids": list(self.unmaterialized_relation_ids),
            "downstream_relation_obligation_ids": list(self.downstream_relation_obligation_ids),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return to_json_text(self.to_dict(), indent=indent)

    def format_text(self) -> str:
        lines = [
            "=== flowguard contract exhaustion mesh ===",
            f"plan_id: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"generated_cases: {len(self.generated_cases)}",
            f"combination_cases: {len(self.combination_cases)}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        for receipt in self.coverage_receipts:
            lines.append(
                "coverage_receipt "
                f"{receipt.receipt_id}: model={receipt.model_id} "
                f"status={receipt.status} cases={len(receipt.covered_case_ids)}"
            )
        for shard in self.coverage_shards:
            lines.append(
                "coverage_shard "
                f"{shard.shard_id}: {shard.generated_count}/{shard.total_combinations} "
                f"status={shard.status}"
            )
        if self.coverage_universe is not None:
            lines.append(f"coverage_universe: {self.coverage_universe.universe_id}")
        if self.contract_fault_profiles:
            lines.append(f"contract_fault_profiles: {len(self.contract_fault_profiles)}")
        if self.observed_problem_backfeed_report is not None:
            lines.append(
                "observed_problem_backfeed: "
                f"{self.observed_problem_backfeed_report.decision} "
                f"mapped={len(self.observed_problem_backfeed_report.mapped_problem_ids)} "
                f"unmapped={len(self.observed_problem_backfeed_report.unmapped_problem_ids)}"
            )
        for route, case_ids in sorted(self.required_route_case_ids.items()):
            lines.append(f"route {route}: {', '.join(case_ids) if case_ids else '(none)'}")
        for acceptance in self.composite_handoff_acceptances:
            lines.append(
                "composite_handoff "
                f"{acceptance.acceptance_id}: {acceptance.case_id} -> "
                f"{', '.join(acceptance.route_ids)}"
            )
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                target = finding.case_id or finding.dimension_id or "-"
                lines.append(
                    f"- {finding.severity}: {finding.code} [{target}] {finding.message}"
                )
        return "\n".join(lines)


def _finding(
    code: str,
    message: str,
    *,
    severity: str = CONTRACT_EXHAUSTION_FINDING_BLOCKER,
    dimension_id: str = "",
    case_id: str = "",
    action: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> ContractExhaustionFinding:
    return ContractExhaustionFinding(
        code=code,
        message=message,
        severity=severity,
        dimension_id=dimension_id,
        case_id=case_id,
        action=action,
        metadata=metadata or {},
    )


def _case_for_dimension(dimension: ContractDimension, mutation_type: str) -> ContractMutationCase:
    return ContractMutationCase(
        case_id=_case_id("contract", dimension.dimension_id, mutation_type),
        dimension_id=dimension.dimension_id,
        mutation_type=mutation_type,
        source_route=dimension.source_route,
        source_case_id=dimension.dimension_id,
        required=dimension.required,
        input_delta={
            "dimension_type": dimension.dimension_type,
            "mutation_type": mutation_type,
            "field_refs": list(dimension.field_refs),
            "evidence_refs": list(dimension.evidence_refs),
        },
        family_id=str(dimension.metadata.get("family_id", "")),
        member_id=str(dimension.metadata.get("member_id", "")),
        evidence_refs=dimension.evidence_refs,
        required_routes=tuple(dimension.metadata.get("required_routes", ())),
        required_test_cell_id=str(dimension.metadata.get("required_test_cell_id", "")),
        risk_gate_id=str(dimension.metadata.get("risk_gate_id", "")),
        freshness_scope=dimension.currentness_rule,
        description=dimension.description
        or f"{dimension.dimension_id} must handle {mutation_type}",
        dimension_ids=(dimension.dimension_id,),
        model_id=dimension.owner_model_id,
        generation_kind=CONTRACT_GENERATION_SINGLE_DIMENSION,
        metadata={
            "owner_model_id": dimension.owner_model_id,
            "producer": dimension.producer,
            "consumer": dimension.consumer,
            **dict(dimension.metadata),
        },
    )


def _generated_cases_for_dimension(dimension: ContractDimension) -> tuple[ContractMutationCase, ...]:
    return tuple(_case_for_dimension(dimension, mutation) for mutation in dimension.default_mutations())


def _inventory_and_relation_cases(
    plan: ContractExhaustionPlan,
) -> tuple[
    tuple[ContractMutationCase, ...],
    tuple[ContractCoverageShard, ...],
    tuple[ContractExhaustionFinding, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    cases: list[ContractMutationCase] = []
    findings: list[ContractExhaustionFinding] = []
    omitted_family: list[str] = []
    omitted_candidates: list[str] = []
    materialized_relation: list[str] = []
    unmaterialized_relation: list[str] = []
    inventory_claimed = bool(
        plan.require_family_inventory
        or plan.expected_family_member_ids
        or plan.require_reduction_inventory
        or plan.expected_reduction_candidate_ids
        or plan.canonical_relation_handoff
    )
    if inventory_claimed and not plan.inventory_revision:
        findings.append(
            _finding(
                "contract_materialization_inventory_revision_missing",
                "family/reduction/canonical-relation materialization requires an explicit inventory revision",
                action="declare the current source inventory revision before generating completeness cases",
            )
        )
    if inventory_claimed and not plan.inventory_current:
        findings.append(
            _finding(
                "contract_materialization_inventory_stale",
                "family/reduction/canonical-relation materialization inventory is stale",
                action="refresh the owning inventories and regenerate materialization cases",
            )
        )
    for item_id, reason in (
        *plan.scoped_family_member_reasons.items(),
        *plan.scoped_reduction_candidate_reasons.items(),
        *plan.scoped_relation_reasons.items(),
    ):
        if not reason:
            findings.append(
                _finding(
                    "contract_materialization_scope_reason_missing",
                    "scoped materialization disposition requires a reason",
                    action="add a reason or materialize the expected item",
                    metadata={"item_id": item_id},
                )
            )
    broad = plan.claim_scope in _BROAD_CLAIMS
    if plan.require_family_inventory and not plan.expected_family_member_ids:
        findings.append(
            _finding(
                "expected_family_member_inventory_missing",
                "family completeness is claimed without an independent expected-member inventory",
                action="declare expected_family_member_ids or narrow the completeness claim",
            )
        )
    if broad and plan.materialized_family_member_ids and not plan.expected_family_member_ids:
        findings.append(
            _finding(
                "expected_family_member_inventory_missing",
                "broad family completeness cannot be inferred from only the materialized member rows",
                action="declare the independent expected family-member inventory",
            )
        )
    if plan.require_reduction_inventory and not plan.expected_reduction_candidate_ids:
        findings.append(
            _finding(
                "expected_reduction_candidate_inventory_missing",
                "candidate completeness is claimed without an independent expected-candidate inventory",
                action="declare expected_reduction_candidate_ids or narrow the completeness claim",
            )
        )
    if broad and plan.materialized_reduction_candidate_ids and not plan.expected_reduction_candidate_ids:
        findings.append(
            _finding(
                "expected_reduction_candidate_inventory_missing",
                "broad candidate completeness cannot be inferred from only materialized candidate rows",
                action="declare the independent expected reduction-candidate inventory",
            )
        )

    shard_id = _case_id("contract_shard", plan.model_id or plan.plan_id, "owner-materialization")

    def add_case(
        *,
        case_id: str,
        mutation_type: str,
        description: str,
        source_case_id: str,
        metadata: Mapping[str, Any],
        member_id: str = "",
    ) -> None:
        cases.append(
            ContractMutationCase(
                case_id=case_id,
                mutation_type=mutation_type,
                source_route=CONTRACT_EXHAUSTION_ROUTE,
                source_case_id=source_case_id,
                required=True,
                expected_status=CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
                member_id=member_id,
                required_routes=(CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT, CONTRACT_ROUTE_TEST_MESH),
                required_test_cell_id=case_id,
                coverage_shard_id=shard_id,
                model_id=plan.model_id,
                description=description,
                metadata={"inventory_revision": plan.inventory_revision, **dict(metadata)},
            )
        )

    materialized_family = set(plan.materialized_family_member_ids)
    scoped_family = set(plan.scoped_family_member_reasons)
    for member_id in plan.expected_family_member_ids:
        if member_id in materialized_family or member_id in scoped_family:
            continue
        omitted_family.append(member_id)
        case_id = _case_id("contract", "omitted_family_member", member_id)
        add_case(
            case_id=case_id,
            mutation_type=CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER,
            description=f"expected obligation-family member {member_id} is omitted",
            source_case_id=member_id,
            member_id=member_id,
            metadata={"expected_family_member_id": member_id},
        )
        findings.append(
            _finding(
                "expected_family_member_omitted",
                "expected obligation-family member is not materialized or scoped",
                case_id=case_id,
                action="materialize the family member or record an explicit scoped disposition",
                metadata={"member_id": member_id},
            )
        )

    materialized_candidates = set(plan.materialized_reduction_candidate_ids)
    scoped_candidates = set(plan.scoped_reduction_candidate_reasons)
    for candidate_id in plan.expected_reduction_candidate_ids:
        if candidate_id in materialized_candidates or candidate_id in scoped_candidates:
            continue
        omitted_candidates.append(candidate_id)
        case_id = _case_id("contract", "omitted_reduction_candidate", candidate_id)
        add_case(
            case_id=case_id,
            mutation_type=CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE,
            description=f"expected architecture-reduction candidate {candidate_id} is omitted",
            source_case_id=candidate_id,
            metadata={"expected_reduction_candidate_id": candidate_id},
        )
        findings.append(
            _finding(
                "expected_reduction_candidate_omitted",
                "expected architecture-reduction candidate is not materialized or scoped",
                case_id=case_id,
                action="materialize the candidate or record an explicit scoped disposition",
                metadata={"candidate_id": candidate_id},
            )
        )

    handoff = plan.canonical_relation_handoff
    if handoff is not None:
        if not handoff.evidence_current:
            findings.append(
                _finding(
                    "relation_materialization_evidence_stale",
                    "canonical relation handoff changed or is stale relative to generated cases",
                    action="refresh the canonical relation handoff and regenerate canonical cases",
                    metadata=handoff.to_dict(),
                )
            )
        for gap_id in handoff.gap_ids:
            findings.append(
                _finding(
                    "canonical_relation_gap_unresolved",
                    "canonical relation handoff contains an unresolved affected-owner gap",
                    action="resolve the gap under the current topology owner before broad closure",
                    metadata={"gap_id": gap_id, "handoff": handoff.to_dict()},
                )
            )
        typed_ids = (
            *((item_id, "relation") for item_id in handoff.relation_ids),
            *((item_id, "affected_model") for item_id in handoff.affected_model_ids),
            *((item_id, "test_obligation") for item_id in handoff.test_obligation_ids),
            *((item_id, "code_obligation") for item_id in handoff.code_obligation_ids),
        )
        for relation_id, relation_kind in typed_ids:
            materializations = tuple(plan.relation_materializations.get(relation_id, ()))
            if relation_id in plan.scoped_relation_reasons:
                continue
            if materializations:
                materialized_relation.append(relation_id)
                for item_id in materializations:
                    case_id = _case_id("contract", "relation", relation_id, item_id)
                    add_case(
                        case_id=case_id,
                        mutation_type=CONTRACT_MUTATION_RELATION_MATERIALIZATION,
                        description=f"canonical relation {relation_id} materializes affected item {item_id}",
                        source_case_id=relation_id,
                        metadata={
                            "relation_id": relation_id,
                            "relation_kind": relation_kind,
                            "materialized_item_id": item_id,
                            "relation_ids": (
                                (relation_id,) if relation_kind == "relation" else ()
                            ),
                            "relation_test_obligation_ids": (
                                (relation_id,) if relation_kind == "test_obligation" else ()
                            ),
                            "relation_code_obligation_ids": (
                                (relation_id,) if relation_kind == "code_obligation" else ()
                            ),
                            "affected_model_ids": (
                                (relation_id,) if relation_kind == "affected_model" else ()
                            ),
                        },
                    )
                continue
            unmaterialized_relation.append(relation_id)
            case_id = _case_id("contract", "unmaterialized_relation", relation_id)
            add_case(
                case_id=case_id,
                mutation_type=CONTRACT_MUTATION_UNMATERIALIZED_RELATION_ID,
                description=f"canonical relation id {relation_id} has no concrete affected item",
                source_case_id=relation_id,
                metadata={"relation_id": relation_id, "relation_kind": relation_kind},
            )
            findings.append(
                _finding(
                    "unmaterialized_relation_id",
                    "canonical relation handoff id has no canonical affected member/candidate case",
                    case_id=case_id,
                    action="bind the id to concrete affected items or record a scoped disposition",
                    metadata={"relation_id": relation_id, "relation_kind": relation_kind},
                )
            )

    shards: tuple[ContractCoverageShard, ...] = ()
    if cases:
        blocked = bool(omitted_family or omitted_candidates or unmaterialized_relation)
        shards = (
            ContractCoverageShard(
                shard_id=shard_id,
                model_id=plan.model_id,
                interaction_group_id="owner-materialization",
                case_ids=tuple(case.case_id for case in cases),
                complete=not blocked,
                total_combinations=len(cases),
                generated_count=len(cases),
                skipped_count=0,
                status=(
                    CONTRACT_COVERAGE_STATUS_BLOCKED
                    if blocked
                    else CONTRACT_COVERAGE_STATUS_COVERED
                ),
                metadata={"inventory_revision": plan.inventory_revision},
            ),
        )
    return (
        tuple(cases),
        shards,
        tuple(findings),
        _unique(omitted_family),
        _unique(omitted_candidates),
        _unique(materialized_relation),
        _unique(unmaterialized_relation),
    )


def _axis_tokens(
    axis: ContractAxis,
    dimensions_by_id: Mapping[str, ContractDimension],
) -> tuple[dict[str, Any], ...]:
    tokens: list[dict[str, Any]] = []
    if axis.values:
        for value in axis.values:
            tokens.append(
                {
                    "axis_id": axis.axis_id,
                    "case_id": _case_id(axis.axis_id, value),
                    "value": value,
                    "dimension_ids": axis.dimension_ids,
                    "mutation_type": "",
                }
            )
        return tuple(tokens)
    if axis.mutation_types:
        dimension_ids = axis.dimension_ids
        for mutation_type in axis.mutation_types:
            tokens.append(
                {
                    "axis_id": axis.axis_id,
                    "case_id": _case_id(axis.axis_id, mutation_type),
                    "value": mutation_type,
                    "dimension_ids": dimension_ids,
                    "mutation_type": mutation_type,
                }
            )
        return tuple(tokens)
    for dimension_id in axis.dimension_ids:
        dimension = dimensions_by_id.get(dimension_id)
        mutation_types = (
            dimension.default_mutations()
            if dimension is not None
            else (CONTRACT_MUTATION_MALFORMED_INPUT,)
        )
        for mutation_type in mutation_types:
            tokens.append(
                {
                    "axis_id": axis.axis_id,
                    "case_id": _case_id(axis.axis_id, dimension_id, mutation_type),
                    "value": mutation_type,
                    "dimension_ids": (dimension_id,),
                    "mutation_type": mutation_type,
                }
            )
    return tuple(tokens)


def _axis_from_dimension(dimension: ContractDimension, *, model_id: str) -> ContractAxis:
    return ContractAxis(
        axis_id=dimension.dimension_id,
        model_id=model_id or dimension.owner_model_id,
        dimension_ids=(dimension.dimension_id,),
        mutation_types=dimension.default_mutations(),
        required=dimension.required,
        source_route=dimension.source_route,
        description=dimension.description,
        metadata=dimension.metadata,
    )


def _axes_for_group(
    plan: ContractExhaustionPlan,
    group: ContractInteractionGroup,
    dimensions_by_id: Mapping[str, ContractDimension],
) -> tuple[tuple[ContractAxis, ...], tuple[ContractExhaustionFinding, ...]]:
    axes_by_id = {axis.axis_id: axis for axis in plan.axes}
    axes: list[ContractAxis] = []
    findings: list[ContractExhaustionFinding] = []
    if group.axis_ids:
        for axis_id in group.axis_ids:
            axis = axes_by_id.get(axis_id)
            if axis is None:
                findings.append(
                    _finding(
                        "contract_cartesian_axis_unknown",
                        "interaction group references an axis that is not declared",
                        severity=(
                            CONTRACT_EXHAUSTION_FINDING_BLOCKER
                            if group.required
                            else CONTRACT_EXHAUSTION_FINDING_GAP
                        ),
                        action="declare the axis or remove it from the interaction group",
                        metadata={"group_id": group.group_id, "axis_id": axis_id},
                    )
                )
                continue
            axes.append(axis)
    elif group.dimension_ids:
        for dimension_id in group.dimension_ids:
            dimension = dimensions_by_id.get(dimension_id)
            if dimension is None:
                findings.append(
                    _finding(
                        "contract_cartesian_dimension_unknown",
                        "interaction group references a dimension that is not declared",
                        severity=(
                            CONTRACT_EXHAUSTION_FINDING_BLOCKER
                            if group.required
                            else CONTRACT_EXHAUSTION_FINDING_GAP
                        ),
                        dimension_id=dimension_id,
                        action="declare the dimension or remove it from the interaction group",
                        metadata={"group_id": group.group_id},
                    )
                )
                continue
            axes.append(_axis_from_dimension(dimension, model_id=group.model_id or plan.model_id))
    else:
        findings.append(
            _finding(
                "contract_cartesian_group_empty",
                "interaction group declares no axes or dimensions, so no Cartesian boundary exists",
                severity=(
                    CONTRACT_EXHAUSTION_FINDING_BLOCKER
                    if group.required
                    else CONTRACT_EXHAUSTION_FINDING_GAP
                ),
                action="declare the model-local axes that should be combined",
                metadata={"group_id": group.group_id},
            )
        )
    expected_model_id = group.model_id or plan.model_id
    is_parent_interface = (
        group.generation_kind == CONTRACT_GENERATION_PARENT_INTERFACE
    )
    if is_parent_interface and (
        not group.parent_interface_contract_id or not group.refinement_contract_id
    ):
        findings.append(
            _finding(
                "contract_parent_interface_typed_contract_missing",
                "a parent-interface product requires an explicit parent-interface and refinement contract",
                severity=(
                    CONTRACT_EXHAUSTION_FINDING_BLOCKER
                    if group.required
                    else CONTRACT_EXHAUSTION_FINDING_GAP
                ),
                action=(
                    "bind parent_interface_contract_id and refinement_contract_id "
                    "before composing models"
                ),
                metadata={
                    "group_id": group.group_id,
                    "parent_interface_contract_id": group.parent_interface_contract_id,
                    "refinement_contract_id": group.refinement_contract_id,
                },
            )
        )
    declared_interface_models = set(group.interface_model_ids)
    if expected_model_id:
        for axis in axes:
            if axis.model_id and axis.model_id != expected_model_id:
                if not is_parent_interface:
                    findings.append(
                        _finding(
                            "contract_cartesian_axis_foreign_model",
                            "Cartesian axis belongs to a different model than its interaction group",
                            severity=(
                                CONTRACT_EXHAUSTION_FINDING_BLOCKER
                                if group.required
                                else CONTRACT_EXHAUSTION_FINDING_GAP
                            ),
                            action="bind every axis to the same model-local group owner",
                            metadata={
                                "group_id": group.group_id,
                                "group_model_id": expected_model_id,
                                "axis_id": axis.axis_id,
                                "axis_model_id": axis.model_id,
                            },
                        )
                    )
                elif axis.model_id not in declared_interface_models:
                    findings.append(
                        _finding(
                            "contract_parent_interface_axis_model_unbound",
                            "parent-interface product contains an axis from a model not named by its typed interface contract",
                            severity=(
                                CONTRACT_EXHAUSTION_FINDING_BLOCKER
                                if group.required
                                else CONTRACT_EXHAUSTION_FINDING_GAP
                            ),
                            action="include every foreign axis model in interface_model_ids",
                            metadata={
                                "group_id": group.group_id,
                                "group_model_id": expected_model_id,
                                "axis_id": axis.axis_id,
                                "axis_model_id": axis.model_id,
                                "interface_model_ids": sorted(declared_interface_models),
                            },
                        )
                    )
            if not axis.is_self_consistent():
                findings.append(
                    _finding(
                        "contract_cartesian_axis_fingerprint_invalid",
                        "Cartesian axis fingerprint does not match its declared finite axis content",
                        severity=(
                            CONTRACT_EXHAUSTION_FINDING_BLOCKER
                            if group.required
                            else CONTRACT_EXHAUSTION_FINDING_GAP
                        ),
                        action="regenerate the axis fingerprint from the canonical axis identity",
                        metadata={
                            "group_id": group.group_id,
                            "axis_id": axis.axis_id,
                            "axis_fingerprint": axis.axis_fingerprint,
                            "axis": axis.to_dict(),
                        },
                    )
                )
    return tuple(axes), tuple(findings)


def build_contract_product_signature(
    plan: ContractExhaustionPlan,
    group: ContractInteractionGroup,
    *,
    axes: Sequence[ContractAxis] | None = None,
    shard_plan_fingerprint: str = "",
) -> ContractProductSignature:
    """Build the canonical finite product identity for one interaction group.

    This helper is deliberately deterministic and side-effect free.  It is
    the only supported source for a model-local product signature; callers
    cannot reduce the denominator by supplying a shorter expected case list.
    """

    dimensions_by_id = {dimension.dimension_id: dimension for dimension in plan.dimensions}
    selected_axes = tuple(axes) if axes is not None else _axes_for_group(plan, group, dimensions_by_id)[0]
    model_id = group.model_id or plan.model_id
    axis_value_ids: dict[str, tuple[str, ...]] = {}
    cardinality = 1
    for axis in selected_axes:
        tokens = _axis_tokens(axis, dimensions_by_id)
        ids = tuple(str(token["case_id"]) for token in tokens)
        axis_value_ids[axis.axis_id] = ids
        cardinality *= len(ids)
    interface_model_ids = tuple(
        _unique(
            axis.model_id
            for axis in selected_axes
            if axis.model_id and axis.model_id != model_id
        )
    )
    return ContractProductSignature(
        signature_id=_case_id("contract_product", model_id or plan.plan_id, group.group_id),
        model_id=model_id,
        interaction_group_id=group.group_id,
        axis_ids=tuple(axis.axis_id for axis in selected_axes),
        axis_value_ids=axis_value_ids,
        expected_cardinality=cardinality if selected_axes else 0,
        partition_revision=str(
            plan.metadata.get("partition_revision", plan.inventory_revision)
            if isinstance(plan.metadata, Mapping)
            else plan.inventory_revision
        ),
        generation_kind=group.generation_kind,
        shard_plan_fingerprint=str(shard_plan_fingerprint),
        axis_fingerprints={
            axis.axis_id: axis.axis_fingerprint for axis in selected_axes
        },
        parent_interface_contract_id=group.parent_interface_contract_id,
        refinement_contract_id=group.refinement_contract_id,
        interface_model_ids=group.interface_model_ids or interface_model_ids,
    )


def _generated_cases_for_interaction_group(
    plan: ContractExhaustionPlan,
    group: ContractInteractionGroup,
    dimensions_by_id: Mapping[str, ContractDimension],
) -> tuple[
    tuple[ContractMutationCase, ...],
    tuple[ContractCombinationCase, ...],
    ContractCoverageShard | None,
    tuple[ContractExhaustionFinding, ...],
]:
    findings: list[ContractExhaustionFinding] = []
    model_id = group.model_id or plan.model_id
    if not model_id:
        findings.append(
            _finding(
                "contract_cartesian_model_id_missing",
                "Cartesian interaction group must name the model whose finite boundary is being exhausted",
                severity=(
                    CONTRACT_EXHAUSTION_FINDING_BLOCKER
                    if group.required
                    else CONTRACT_EXHAUSTION_FINDING_GAP
                ),
                action="set ContractExhaustionPlan.model_id or ContractInteractionGroup.model_id",
                metadata={"group_id": group.group_id},
            )
        )
    axes, axis_findings = _axes_for_group(plan, group, dimensions_by_id)
    findings.extend(axis_findings)

    if plan.model_id and group.model_id and plan.model_id != group.model_id:
        findings.append(
            _finding(
                "contract_cartesian_group_foreign_model",
                "interaction group belongs to a different model than its exhaustion plan",
                severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                action="use one model-local ContractExhaustionPlan per interaction group",
                metadata={
                    "plan_model_id": plan.model_id,
                    "group_model_id": group.model_id,
                    "group_id": group.group_id,
                },
            )
        )

    strict_product = plan.claim_scope in CONTRACT_STRICT_CLAIM_SCOPES
    if strict_product and not axes:
        findings.append(
            _finding(
                "contract_cartesian_product_axes_missing",
                "full or release Cartesian claims must derive a non-empty product from explicit axes",
                severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                action="declare non-empty model-local axes and an interaction group",
                metadata={"group_id": group.group_id, "model_id": model_id},
            )
        )

    product_signature = build_contract_product_signature(plan, group, axes=axes)
    if strict_product and not product_signature.is_self_consistent():
        findings.append(
            _finding(
                "contract_cartesian_product_signature_invalid",
                "full or release Cartesian claims require a self-consistent canonical product signature",
                severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                action="generate the signature through build_contract_product_signature",
                metadata={"group_id": group.group_id, "signature": product_signature.to_dict()},
            )
        )
    if group.product_signature is not None:
        supplied_signature = group.product_signature
        if not supplied_signature.is_self_consistent():
            findings.append(
                _finding(
                    "contract_cartesian_product_signature_invalid",
                    "supplied interaction-group product signature is not self-consistent",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="regenerate the interaction-group product signature",
                    metadata={"group_id": group.group_id, "signature": supplied_signature.to_dict()},
                )
            )
        elif supplied_signature.fingerprint != product_signature.fingerprint:
            findings.append(
                _finding(
                    "contract_cartesian_product_signature_mismatch",
                    "interaction-group product signature does not match the canonical axis product",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="refresh the group signature after changing any axis or partition input",
                    metadata={
                        "group_id": group.group_id,
                        "expected": product_signature.to_dict(),
                        "actual": supplied_signature.to_dict(),
                    },
                )
            )

    token_sets: list[tuple[dict[str, Any], ...]] = []
    for axis in axes:
        tokens = _axis_tokens(axis, dimensions_by_id)
        if not tokens:
            findings.append(
                _finding(
                    "contract_cartesian_axis_empty",
                    "Cartesian axis has no values, mutations, or dimension-derived cases",
                    severity=(
                        CONTRACT_EXHAUSTION_FINDING_BLOCKER
                        if axis.required and group.required
                        else CONTRACT_EXHAUSTION_FINDING_GAP
                    ),
                    action="declare finite values, mutation_types, or dimension_ids for the axis",
                    metadata={"group_id": group.group_id, "axis_id": axis.axis_id},
                )
            )
            continue
        token_sets.append(tokens)

    if not token_sets:
        return (), (), None, tuple(findings)

    total_combinations = 1
    for tokens in token_sets:
        total_combinations *= len(tokens)

    limit = group.max_combinations if group.max_combinations is not None else plan.cartesian_case_limit
    generated_limit = max(0, int(limit))
    if total_combinations > generated_limit:
        findings.append(
            _finding(
                "contract_cartesian_case_limit_exceeded",
                "Cartesian interaction group has more combinations than this run is allowed to close",
                severity=(
                    CONTRACT_EXHAUSTION_FINDING_BLOCKER
                    if group.required
                    else CONTRACT_EXHAUSTION_FINDING_GAP
                ),
                action="split the model, shard the group, or raise the explicit run limit with evidence",
                metadata={
                    "group_id": group.group_id,
                    "model_id": model_id,
                    "total_combinations": total_combinations,
                    "generated_limit": generated_limit,
                },
            )
        )

    shard_id = _case_id("contract_shard", model_id or plan.plan_id, group.group_id)
    mutation_cases: list[ContractMutationCase] = []
    combination_cases: list[ContractCombinationCase] = []
    generated_count = min(total_combinations, generated_limit)
    for index, token_product in enumerate(product(*token_sets)):
        if index >= generated_count:
            break
        axis_case_ids = tuple(str(token["case_id"]) for token in token_product)
        dimension_ids = _unique(
            dimension_id
            for token in token_product
            for dimension_id in token.get("dimension_ids", ())
        )
        input_delta = {
            "axis_cases": {
                str(token["axis_id"]): str(token["case_id"])
                for token in token_product
            },
            "axis_values": {
                str(token["axis_id"]): to_jsonable(token.get("value", ""))
                for token in token_product
            },
            "dimension_ids": list(dimension_ids),
            "interaction_group_id": group.group_id,
            "model_id": model_id,
        }
        case_id = _case_id("cartesian", model_id or plan.plan_id, group.group_id, str(index + 1))
        required_routes = group.required_routes or (
            CONTRACT_ROUTE_MODEL_MESH,
            CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
            CONTRACT_ROUTE_TEST_MESH,
            CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
        )
        mutation_cases.append(
            ContractMutationCase(
                case_id=case_id,
                dimension_id="|".join(dimension_ids),
                mutation_type=CONTRACT_MUTATION_CARTESIAN_COMBINATION,
                source_route=CONTRACT_EXHAUSTION_ROUTE,
                source_case_id=group.group_id,
                required=group.required,
                oracle_id=group.oracle_id,
                input_delta=input_delta,
                expected_status=group.oracle_status,
                required_routes=required_routes,
                required_test_cell_id=case_id,
                risk_gate_id=_case_id("contract_cartesian", case_id),
                description=group.description
                or f"{model_id or plan.plan_id} must handle Cartesian combination {group.group_id}",
                dimension_ids=dimension_ids,
                axis_case_ids=axis_case_ids,
                interaction_group_id=group.group_id,
                combination_order=index + 1,
                coverage_shard_id=shard_id,
                model_id=model_id,
                parent_model_id=plan.parent_model_id,
                generation_kind=group.generation_kind,
                metadata={
                    "axis_ids": [axis.axis_id for axis in axes],
                    "axis_case_ids": list(axis_case_ids),
                    "total_combinations": total_combinations,
                    "generated_limit": generated_limit,
                    **dict(group.metadata),
                },
            )
        )
        combination_cases.append(
            ContractCombinationCase(
                case_id=case_id,
                model_id=model_id,
                interaction_group_id=group.group_id,
                axis_case_ids=axis_case_ids,
                dimension_ids=dimension_ids,
                coverage_shard_id=shard_id,
                expected_status=group.oracle_status,
                required_routes=required_routes,
                metadata=input_delta,
            )
        )

    shard = ContractCoverageShard(
        shard_id=shard_id,
        model_id=model_id,
        interaction_group_id=group.group_id,
        case_ids=tuple(case.case_id for case in mutation_cases),
        complete=generated_count == total_combinations,
        total_combinations=total_combinations,
        generated_count=generated_count,
        skipped_count=max(0, total_combinations - generated_count),
        status=(
            CONTRACT_COVERAGE_STATUS_COVERED
            if generated_count == total_combinations
            else CONTRACT_COVERAGE_STATUS_SCOPED
        ),
        product_signature=product_signature.fingerprint,
        axis_ids=product_signature.axis_ids,
        metadata={
            "generation_kind": group.generation_kind,
            "axis_ids": [axis.axis_id for axis in axes],
        },
    )
    return tuple(mutation_cases), tuple(combination_cases), shard, tuple(findings)


def _coverage_receipts_for_report(
    plan: ContractExhaustionPlan,
    generated_cases: Sequence[ContractMutationCase],
    findings: Sequence[ContractExhaustionFinding],
    shards: Sequence[ContractCoverageShard],
) -> tuple[ModelContractCoverageReceipt, ...]:
    receipts = list(plan.coverage_receipts)
    if not (plan.require_model_coverage_receipt or plan.interaction_groups or plan.required_child_receipt_ids):
        return tuple(receipts)

    model_id = plan.model_id
    if not model_id and plan.interaction_groups:
        model_ids = _unique(group.model_id for group in plan.interaction_groups)
        model_id = model_ids[0] if len(model_ids) == 1 else ""
    case_ids = tuple(
        case.case_id
        for case in generated_cases
        if case.generation_kind
        in {CONTRACT_GENERATION_LOCAL_CARTESIAN, CONTRACT_GENERATION_PARENT_INTERFACE}
    )
    finding_codes = _unique(finding.code for finding in findings)
    blocking_case_ids = _unique(
        finding.case_id
        for finding in findings
        if finding.case_id and finding.severity == CONTRACT_EXHAUSTION_FINDING_BLOCKER
    )
    missing_case_ids = _unique(
        case.case_id
        for shard in shards
        if not shard.complete
        for case in generated_cases
        if case.coverage_shard_id == shard.shard_id
    )
    status = CONTRACT_COVERAGE_STATUS_COVERED
    confidence = CONTRACT_EXHAUSTION_CONFIDENCE_FULL
    if any(finding.severity == CONTRACT_EXHAUSTION_FINDING_BLOCKER for finding in findings):
        status = CONTRACT_COVERAGE_STATUS_BLOCKED
        confidence = CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED
    elif any(not shard.complete for shard in shards) or any(
        finding.severity == CONTRACT_EXHAUSTION_FINDING_GAP for finding in findings
    ):
        status = CONTRACT_COVERAGE_STATUS_SCOPED
        confidence = CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED
    receipt_id = _case_id("contract_coverage", model_id or plan.plan_id)
    product_signatures = tuple(
        sorted(
            {
                shard.product_signature
                for shard in shards
                if shard.product_signature
            }
        )
    )
    receipt_product_signature = (
        product_signatures[0]
        if len(product_signatures) == 1
        else canonical_fingerprint(product_signatures)
        if product_signatures
        else ""
    )
    receipts.append(
        ModelContractCoverageReceipt(
            receipt_id=receipt_id,
            model_id=model_id,
            parent_model_id=plan.parent_model_id,
            status=status,
            confidence=confidence,
            current=True,
            covered_case_ids=case_ids,
            shard_ids=tuple(shard.shard_id for shard in shards),
            interaction_group_ids=tuple(group.group_id for group in plan.interaction_groups),
            required_child_receipt_ids=plan.required_child_receipt_ids,
            consumed_child_receipt_ids=plan.consumed_child_receipt_ids,
            missing_case_ids=missing_case_ids,
            blocked_case_ids=blocking_case_ids,
            finding_codes=finding_codes,
            product_signature=receipt_product_signature,
            owner_id=str(plan.metadata.get("owner_id", model_id))
            if isinstance(plan.metadata, Mapping)
            else model_id,
            claim_scope=plan.claim_scope,
            metadata={
                "plan_id": plan.plan_id,
                "model_level": plan.model_level,
                "product_signatures": list(product_signatures),
                "required_coverage_receipt_ids": list(plan.required_coverage_receipt_ids),
            },
        )
    )
    return tuple(receipts)


def _product_signatures_for_report(
    plan: ContractExhaustionPlan,
    shards: Sequence[ContractCoverageShard],
) -> tuple[ContractProductSignature, ...]:
    """Return one canonical product signature for every declared group."""

    dimensions_by_id = {dimension.dimension_id: dimension for dimension in plan.dimensions}
    shard_by_group = {
        shard.interaction_group_id: shard
        for shard in shards
        if shard.interaction_group_id
    }
    signatures: list[ContractProductSignature] = []
    for group in plan.interaction_groups:
        axes, _ = _axes_for_group(plan, group, dimensions_by_id)
        shard = shard_by_group.get(group.group_id)
        signature = build_contract_product_signature(
            plan,
            group,
            axes=axes,
            shard_plan_fingerprint=(
                shard.product_signature if shard is not None else ""
            ),
        )
        # ``shard_plan_fingerprint`` is a plan identity, not the product hash
        # itself.  Rebuild the public signature without that self-reference so
        # the value remains stable when the shard receipt is emitted.
        if shard is not None:
            signature = build_contract_product_signature(plan, group, axes=axes)
        signatures.append(signature)
    return tuple(signatures)


def _native_child_evidence_findings(
    plan: ContractExhaustionPlan,
    receipt: ModelContractCoverageReceipt,
) -> tuple[ContractExhaustionFinding, ...]:
    """Resolve and independently verify native child receipts for a strict parent.

    ``ModelContractCoverageReceipt`` is intentionally not itself an execution
    receipt.  For a full/release/whole-domain parent, the required child
    coverage ids therefore have to map one-to-one to immutable
    ``EvidenceReceipt`` objects in the configured store.  The verifier is
    called with a caller-supplied, independently derived
    ``ReceiptVerificationContext``; missing context, a stale child, or any
    identity mismatch is a blocker.  There is no id-only or aggregate-status
    fallback.
    """

    strict = (
        plan.claim_scope in CONTRACT_STRICT_CLAIM_SCOPES
        or receipt.claim_scope in CONTRACT_STRICT_CLAIM_SCOPES
        or bool(plan.metadata.get("require_native_child_evidence", False))
    )
    required_ids = tuple(receipt.required_child_receipt_ids)
    if not strict or not required_ids:
        return ()

    findings: list[ContractExhaustionFinding] = []
    bindings = tuple(receipt.native_child_evidence_bindings)
    by_coverage: dict[str, NativeChildEvidenceBinding] = {}
    by_evidence: dict[str, NativeChildEvidenceBinding] = {}
    for binding in bindings:
        if binding.coverage_receipt_id in by_coverage:
            findings.append(
                _finding(
                    "contract_native_child_binding_duplicate",
                    "strict parent maps one coverage receipt id more than once",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "coverage_receipt_id": binding.coverage_receipt_id,
                    },
                )
            )
        if binding.evidence_receipt_id in by_evidence:
            findings.append(
                _finding(
                    "contract_native_evidence_receipt_duplicate",
                    "strict parent maps more than one child to the same native EvidenceReceipt",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "evidence_receipt_id": binding.evidence_receipt_id,
                    },
                )
            )
        by_coverage[binding.coverage_receipt_id] = binding
        by_evidence[binding.evidence_receipt_id] = binding

    required_set = set(required_ids)
    missing_binding_ids = tuple(sorted(required_set - set(by_coverage)))
    extra_binding_ids = tuple(sorted(set(by_coverage) - required_set))
    if missing_binding_ids or extra_binding_ids:
        findings.append(
            _finding(
                "contract_native_child_binding_set_mismatch",
                "strict parent must bind exactly every required child coverage receipt",
                metadata={
                    "receipt_id": receipt.receipt_id,
                    "missing_coverage_receipt_ids": list(missing_binding_ids),
                    "extra_coverage_receipt_ids": list(extra_binding_ids),
                },
            )
        )

    store_root = str(plan.native_receipt_store_repository_root).strip()
    store_output = str(plan.native_receipt_store_output_directory).strip()
    if not store_root and not store_output:
        findings.append(
            _finding(
                "contract_native_receipt_store_missing",
                "strict parent coverage requires a canonical native EvidenceReceipt store",
                metadata={"receipt_id": receipt.receipt_id},
            )
        )
        return tuple(findings)

    # Imports are local to keep the planning layer lightweight for routine
    # callers and to keep all native receipt semantics in the one verifier.
    from .evidence_receipts import (
        RECEIPT_STATUS_PASS,
        ReceiptVerificationContext,
        load_evidence_receipt,
        verify_evidence_receipt,
    )

    for coverage_id in required_ids:
        binding = by_coverage.get(coverage_id)
        if binding is None:
            continue
        if not binding.complete():
            findings.append(
                _finding(
                    "contract_native_child_binding_incomplete",
                    "strict parent child binding is missing a required canonical identity field",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": binding.evidence_receipt_id,
                    },
                )
            )
            continue
        if binding.parent_model_id != receipt.model_id:
            findings.append(
                _finding(
                    "contract_native_child_parent_mismatch",
                    "native child binding does not name the coverage receipt's parent model",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "coverage_receipt_id": coverage_id,
                        "expected_parent_model_id": receipt.model_id,
                        "actual_parent_model_id": binding.parent_model_id,
                    },
                )
            )
        if binding.model_id == receipt.model_id:
            findings.append(
                _finding(
                    "contract_native_parent_as_child",
                    "a strict parent coverage receipt cannot consume itself as a child",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "coverage_receipt_id": coverage_id,
                        "model_id": binding.model_id,
                    },
                )
            )
        try:
            native = load_evidence_receipt(
                binding.evidence_receipt_id,
                store_root or ".",
                output_directory=store_output or None,
            )
        except (OSError, ValueError, TypeError) as exc:
            findings.append(
                _finding(
                    "contract_native_evidence_receipt_missing",
                    "strict parent child binding does not resolve a readable canonical EvidenceReceipt",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": binding.evidence_receipt_id,
                        "error": str(exc),
                    },
                )
            )
            continue

        if native.receipt_id != binding.evidence_receipt_id:
            findings.append(
                _finding(
                    "contract_native_evidence_receipt_id_mismatch",
                    "loaded EvidenceReceipt id differs from the declared child binding",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "expected": binding.evidence_receipt_id,
                        "actual": native.receipt_id,
                    },
                )
            )
        if native.fingerprint != binding.expected_receipt_fingerprint:
            findings.append(
                _finding(
                    "contract_native_evidence_receipt_fingerprint_mismatch",
                    "loaded EvidenceReceipt fingerprint differs from the frozen child binding",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                        "expected": binding.expected_receipt_fingerprint,
                        "actual": native.fingerprint,
                    },
                )
            )

        native_metadata = dict(native.metadata)
        actual_model_id = str(native_metadata.get("model_id", ""))
        actual_owner_id = str(native_metadata.get("owner_id", ""))
        actual_parent_model_id = str(native_metadata.get("parent_model_id", ""))
        identity_checks = (
            ("model_id", binding.model_id, actual_model_id),
            ("owner_id", binding.owner_id, actual_owner_id),
            ("parent_model_id", binding.parent_model_id, actual_parent_model_id),
            ("subject_id", binding.subject_id, native.subject_id),
            ("claim_scope", binding.claim_scope, native.claim_scope),
        )
        for name, expected, actual in identity_checks:
            if not actual or expected != actual:
                findings.append(
                    _finding(
                        f"contract_native_child_{name}_mismatch",
                        f"native child EvidenceReceipt {name} does not match the exact binding",
                        metadata={
                            "coverage_receipt_id": coverage_id,
                            "evidence_receipt_id": native.receipt_id,
                            "expected": expected,
                            "actual": actual,
                        },
                    )
                )
        if set(native.covered_obligations) != set(binding.obligation_ids):
            findings.append(
                _finding(
                    "contract_native_child_obligation_mismatch",
                    "native child EvidenceReceipt does not cover the exact frozen obligations",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                        "expected": list(binding.obligation_ids),
                        "actual": list(native.covered_obligations),
                    },
                )
            )
        if native.result_status != RECEIPT_STATUS_PASS or native.exit_code != 0:
            findings.append(
                _finding(
                    "contract_native_child_not_terminal_pass",
                    "native child EvidenceReceipt is not an exit-code-zero terminal pass",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                        "result_status": native.result_status,
                        "exit_code": native.exit_code,
                    },
                )
            )
        if native.skipped_checks:
            findings.append(
                _finding(
                    "contract_native_child_skipped_checks",
                    "native child EvidenceReceipt contains skipped checks",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                        "skipped_checks": list(native.skipped_checks),
                    },
                )
            )
        if native.blockers:
            findings.append(
                _finding(
                    "contract_native_child_blockers",
                    "native child EvidenceReceipt contains blockers",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                        "blockers": list(native.blockers),
                    },
                )
            )

        context = plan.native_receipt_verification_contexts.get(binding.evidence_receipt_id)
        if not isinstance(context, ReceiptVerificationContext):
            findings.append(
                _finding(
                    "contract_native_child_verification_context_missing",
                    "strict parent child requires an independently derived ReceiptVerificationContext",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                    },
                )
            )
            continue
        result = verify_evidence_receipt(native, context)
        if not result.ok:
            findings.append(
                _finding(
                    "contract_native_child_verification_failed",
                    "native child EvidenceReceipt is not independently current and eligible",
                    metadata={
                        "coverage_receipt_id": coverage_id,
                        "evidence_receipt_id": native.receipt_id,
                        "status": result.status,
                        "current": result.current,
                        "eligible": result.eligible,
                        "finding_codes": list(result.finding_codes),
                    },
                )
            )

    return tuple(findings)


def review_native_child_evidence(
    receipt: ModelContractCoverageReceipt,
    *,
    claim_scope: str,
    receipt_store_repository_root: str = "",
    receipt_store_output_directory: str = "",
    verification_contexts: Mapping[str, Any] | None = None,
) -> tuple[ContractExhaustionFinding, ...]:
    """Review native child evidence for one strict model-coverage receipt.

    This public adapter lets ModelMesh invoke the same native verifier as the
    contract-exhaustion route without creating a second receipt framework.
    """

    plan = ContractExhaustionPlan(
        plan_id=f"native-child-evidence:{receipt.receipt_id}",
        model_id=receipt.model_id,
        claim_scope=str(claim_scope),
        native_receipt_store_repository_root=receipt_store_repository_root,
        native_receipt_store_output_directory=receipt_store_output_directory,
        native_receipt_verification_contexts=verification_contexts or {},
    )
    return _native_child_evidence_findings(plan, receipt)


def _coverage_receipt_findings(
    plan: ContractExhaustionPlan,
    receipts: Sequence[ModelContractCoverageReceipt],
    shards: Sequence[ContractCoverageShard],
) -> tuple[ContractExhaustionFinding, ...]:
    findings: list[ContractExhaustionFinding] = []
    receipts_by_id = {receipt.receipt_id: receipt for receipt in receipts}
    if (plan.require_model_coverage_receipt or plan.interaction_groups) and not plan.model_id and not any(
        receipt.model_id for receipt in receipts
    ):
        findings.append(
            _finding(
                "contract_coverage_model_id_missing",
                "model-scoped Cartesian coverage needs a model id before it can be consumed by ModelMesh",
                action="set the owning model_id on the plan, group, or receipt",
            )
        )
    for receipt_id in plan.required_coverage_receipt_ids:
        receipt = receipts_by_id.get(receipt_id)
        if receipt is None:
            findings.append(
                _finding(
                    "contract_coverage_receipt_missing",
                    "required model coverage receipt was not supplied or generated",
                    action="run the model-local Cartesian matrix and provide its receipt",
                    metadata={"receipt_id": receipt_id},
                )
            )
            continue
        if not receipt.complete():
            findings.append(
                _finding(
                    "contract_coverage_receipt_incomplete",
                    "model coverage receipt is not current, full-confidence, and complete",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="close missing/blocked cases or scope out the broad claim",
                    metadata={"receipt": receipt.to_dict()},
                )
            )
    for receipt in receipts:
        missing_child_receipts = tuple(
            receipt_id
            for receipt_id in receipt.required_child_receipt_ids
            if receipt_id not in receipt.consumed_child_receipt_ids
        )
        if missing_child_receipts:
            findings.append(
                _finding(
                    "contract_child_receipt_unconsumed",
                    "parent model coverage receipt does not consume every required child coverage receipt",
                    action="attach the latest child receipt ids to the parent coverage run",
                    metadata={
                        "receipt_id": receipt.receipt_id,
                        "model_id": receipt.model_id,
                        "missing_child_receipt_ids": list(missing_child_receipts),
                    },
                )
            )
        if not receipt.current:
            findings.append(
                _finding(
                    "contract_coverage_receipt_stale",
                    "model coverage receipt is stale",
                    action="rerun the model-local Cartesian matrix",
                    metadata={"receipt": receipt.to_dict()},
                )
            )
        findings.extend(_native_child_evidence_findings(plan, receipt))
    for shard in shards:
        if not shard.complete:
            findings.append(
                _finding(
                    "contract_coverage_shard_incomplete",
                    "coverage shard did not generate or close every combination in its interaction group",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="complete the shard, split it into explicit child shards, or narrow the claim",
                    metadata=shard.to_dict(),
                )
            )
    return tuple(findings)


def _route_case_ids(cases: Sequence[ContractMutationCase]) -> dict[str, tuple[str, ...]]:
    route_to_cases: dict[str, list[str]] = {}
    for case in cases:
        if not case.required:
            continue
        for route in case.routes():
            route_to_cases.setdefault(route, []).append(case.case_id)
    return {route: _unique(case_ids) for route, case_ids in route_to_cases.items()}


def _composite_handoff_acceptances(
    cases: Sequence[ContractMutationCase],
) -> tuple[CompositeHandoffAcceptance, ...]:
    acceptances: list[CompositeHandoffAcceptance] = []
    for case in cases:
        if not case.required:
            continue
        route_ids = case.routes()
        if len(route_ids) < 2:
            continue
        acceptances.append(
            CompositeHandoffAcceptance(
                acceptance_id=_case_id("composite_handoff", case.case_id),
                case_id=case.case_id,
                route_ids=route_ids,
                description=(
                    "single case matrix pass is not full-chain confidence; "
                    "all route handoffs must close this case"
                ),
                metadata={
                    "mutation_type": case.mutation_type,
                    "source_route": case.source_route,
                    "source_case_id": case.source_case_id,
                },
            )
        )
    return tuple(acceptances)


def _composite_native_evidence_findings(
    plan: ContractExhaustionPlan,
    acceptance: CompositeHandoffAcceptance,
    result: CompositeHandoffResult,
) -> tuple[ContractExhaustionFinding, ...]:
    """Independently verify every native receipt cited by a composite result.

    ``CompositeHandoffResult`` is a route-chain projection and intentionally
    contains only evidence ids.  The ids cannot license a broad claim by
    themselves: each one must resolve from the configured canonical
    EvidenceReceipt store and pass the native receipt verifier under an
    independently derived verification context.  This keeps the composite
    route from becoming a second evidence authority or from accepting a
    caller-authored ``current``/``pass`` flag.
    """

    evidence_ids = tuple(result.evidence_ids)
    if not evidence_ids:
        return ()

    findings: list[ContractExhaustionFinding] = []
    normalized_evidence_ids = tuple(str(evidence_id).strip() for evidence_id in evidence_ids)
    noncanonical_ids = tuple(
        sorted(
            {
                raw
                for raw, normalized in zip(evidence_ids, normalized_evidence_ids)
                if str(raw) != normalized
            }
        )
    )
    if noncanonical_ids:
        findings.append(
            _finding(
                "composite_handoff_evidence_id_noncanonical",
                "composite handoff evidence ids must not contain leading or trailing whitespace",
                metadata={
                    "acceptance_id": acceptance.acceptance_id,
                    "result_id": result.result_id,
                    "evidence_ids": list(noncanonical_ids),
                },
            )
        )
    duplicate_evidence_ids = tuple(
        sorted(
            evidence_id
            for evidence_id in set(normalized_evidence_ids)
            if normalized_evidence_ids.count(evidence_id) > 1
        )
    )
    if duplicate_evidence_ids:
        findings.append(
            _finding(
                "composite_handoff_evidence_duplicate",
                "a composite handoff result cites the same native evidence receipt more than once",
                metadata={
                    "acceptance_id": acceptance.acceptance_id,
                    "result_id": result.result_id,
                    "evidence_ids": list(duplicate_evidence_ids),
                },
            )
        )

    store_root = str(plan.native_receipt_store_repository_root).strip()
    store_output = str(plan.native_receipt_store_output_directory).strip()
    if not store_root and not store_output:
        findings.append(
            _finding(
                "composite_handoff_evidence_store_missing",
                "broad composite handoff evidence requires a configured canonical EvidenceReceipt store",
                metadata={
                    "acceptance_id": acceptance.acceptance_id,
                    "result_id": result.result_id,
                },
            )
        )
        return tuple(findings)

    # Keep native receipt semantics in the one canonical verifier.  The
    # planning layer only resolves ids and projects verifier findings.
    from .evidence_receipts import (
        RECEIPT_STATUS_PASS,
        ReceiptVerificationContext,
        load_evidence_receipt,
        verify_evidence_receipt,
    )

    for evidence_id in normalized_evidence_ids:
        if not evidence_id:
            findings.append(
                _finding(
                    "composite_handoff_evidence_id_missing",
                    "composite handoff result contains an empty native evidence id",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                    },
                )
            )
            continue

        # ``load_evidence_receipt`` accepts a path for low-level callers.  A
        # composite result is an id-only public contract, so do not allow a
        # path to escape the canonical store selected by this plan.
        candidate_path = Path(evidence_id)
        if (
            candidate_path.is_absolute()
            or candidate_path.exists()
            or "/" in evidence_id
            or "\\" in evidence_id
        ):
            findings.append(
                _finding(
                    "composite_handoff_evidence_path_forbidden",
                    "composite handoff evidence must name a canonical receipt id, not a filesystem path",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                    },
                )
            )
            continue

        try:
            native = load_evidence_receipt(
                evidence_id,
                store_root or ".",
                output_directory=store_output or None,
            )
        except (OSError, ValueError, TypeError) as exc:
            findings.append(
                _finding(
                    "composite_handoff_evidence_missing",
                    "composite handoff result does not resolve a readable canonical EvidenceReceipt",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                        "error": str(exc),
                    },
                )
            )
            continue

        if native.receipt_id != evidence_id:
            findings.append(
                _finding(
                    "composite_handoff_evidence_id_mismatch",
                    "loaded native EvidenceReceipt id differs from the cited composite evidence id",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "expected": evidence_id,
                        "actual": native.receipt_id,
                    },
                )
            )
        if native.result_status != RECEIPT_STATUS_PASS or native.exit_code != 0:
            findings.append(
                _finding(
                    "composite_handoff_evidence_not_terminal_pass",
                    "composite handoff evidence must be an exit-code-zero native pass",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                        "result_status": native.result_status,
                        "exit_code": native.exit_code,
                    },
                )
            )
        if native.skipped_checks:
            findings.append(
                _finding(
                    "composite_handoff_evidence_skipped_checks",
                    "composite handoff evidence contains skipped checks",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                        "skipped_checks": list(native.skipped_checks),
                    },
                )
            )
        if native.blockers:
            findings.append(
                _finding(
                    "composite_handoff_evidence_blockers",
                    "composite handoff evidence contains unresolved blockers",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                        "blockers": list(native.blockers),
                    },
                )
            )

        context = plan.native_receipt_verification_contexts.get(evidence_id)
        if not isinstance(context, ReceiptVerificationContext):
            findings.append(
                _finding(
                    "composite_handoff_evidence_verification_context_missing",
                    "composite handoff evidence requires an independently derived ReceiptVerificationContext",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                    },
                )
            )
            continue
        verification = verify_evidence_receipt(native, context)
        if not verification.ok:
            findings.append(
                _finding(
                    "composite_handoff_evidence_verification_failed",
                    "composite handoff evidence is not independently current and eligible",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_id": result.result_id,
                        "evidence_id": evidence_id,
                        "status": verification.status,
                        "current": verification.current,
                        "eligible": verification.eligible,
                        "finding_codes": list(verification.finding_codes),
                    },
                )
            )

    return tuple(findings)


def _composite_handoff_result_findings(
    plan: ContractExhaustionPlan,
    acceptances: Sequence[CompositeHandoffAcceptance],
) -> tuple[ContractExhaustionFinding, ...]:
    """Require terminal results separately from generated handoff obligations."""

    # The canonical BCL/PPA plans are finite-matrix producers.  They publish
    # one acceptance id per generated multi-route case for downstream
    # Model-Test Alignment, TestMesh, ModelMesh, and RiskLedger consumers, but
    # do not manufacture terminal route receipts while merely reviewing the
    # matrix.  Their metadata is an explicit phase boundary, not an implicit
    # success path: once a caller supplies terminal results, those results are
    # still validated below (and any unbound obligation remains visible).
    matrix_phase_deferred = bool(
        isinstance(plan.metadata, Mapping)
        and plan.metadata.get("composite_handoff_results_deferred") is True
        and not plan.composite_handoff_results
    )
    gate_required = bool(
        plan.require_composite_handoff_results
        or plan.claim_scope in _BROAD_CLAIMS
    )
    if matrix_phase_deferred:
        gate_required = False
    results_by_acceptance: dict[str, list[CompositeHandoffResult]] = {}
    findings: list[ContractExhaustionFinding] = []
    for result in plan.composite_handoff_results:
        results_by_acceptance.setdefault(result.acceptance_id, []).append(result)
    result_ids: dict[str, list[str]] = {}
    for result in plan.composite_handoff_results:
        result_ids.setdefault(result.result_id, []).append(result.acceptance_id)
    for result_id, acceptance_ids in sorted(result_ids.items()):
        if result_id and len(acceptance_ids) > 1:
            findings.append(
                _finding(
                    "composite_handoff_result_duplicate",
                    "one terminal composite handoff result identity is reused by multiple obligations",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="produce one uniquely identified result for each handoff obligation",
                    metadata={
                        "result_id": result_id,
                        "acceptance_ids": sorted(acceptance_ids),
                    },
                )
            )
    for acceptance in acceptances:
        results = tuple(results_by_acceptance.get(acceptance.acceptance_id, ()))
        if not results:
            if not gate_required:
                continue
            findings.append(
                _finding(
                    "composite_handoff_result_missing",
                    "claim has a handoff obligation but no independent terminal acceptance result",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="run the required routes and provide one current CompositeHandoffResult",
                    metadata={"acceptance": acceptance.to_dict()},
                )
            )
            continue
        if len(results) != 1:
            findings.append(
                _finding(
                    "composite_handoff_result_ambiguous",
                    "handoff obligation must have exactly one terminal acceptance result",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="remove duplicate results and retain the one exact current result",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "result_ids": [result.result_id for result in results],
                    },
                )
            )
            continue
        result = results[0]
        if not result.complete(expected_acceptance_id=acceptance.acceptance_id):
            findings.append(
                _finding(
                    "composite_handoff_result_incomplete",
                    "handoff acceptance result is not a current terminal evidence result",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="supply a passed, current result with canonical fingerprint and evidence ids",
                    metadata={
                        "acceptance": acceptance.to_dict(),
                        "result": result.to_dict(),
                    },
                )
            )
        missing_routes = tuple(sorted(set(acceptance.route_ids) - set(result.covered_route_ids)))
        if missing_routes:
            findings.append(
                _finding(
                    "composite_handoff_result_route_missing",
                    "terminal acceptance result does not cover every route in its handoff obligation",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="record exact result coverage for every required route",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "missing_route_ids": list(missing_routes),
                    },
                )
            )
        extra_routes = tuple(sorted(set(result.covered_route_ids) - set(acceptance.route_ids)))
        if extra_routes:
            findings.append(
                _finding(
                    "composite_handoff_result_route_foreign",
                    "terminal acceptance result covers a route outside its handoff obligation",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="remove foreign route ids and retain the exact acceptance route set",
                    metadata={
                        "acceptance_id": acceptance.acceptance_id,
                        "foreign_route_ids": list(extra_routes),
                    },
                )
            )
        findings.extend(
            _composite_native_evidence_findings(
                plan,
                acceptance,
                result,
            )
        )
    for acceptance_id, results in sorted(results_by_acceptance.items()):
        if acceptance_id not in {acceptance.acceptance_id for acceptance in acceptances}:
            findings.append(
                _finding(
                    "composite_handoff_result_unknown_obligation",
                    "terminal acceptance result names an unknown handoff obligation",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="bind the result to a generated CompositeHandoffAcceptance",
                    metadata={
                        "acceptance_id": acceptance_id,
                        "result_ids": [result.result_id for result in results],
                    },
                )
            )
    return tuple(findings)


def _decision(findings: Sequence[ContractExhaustionFinding]) -> tuple[str, str, bool]:
    if any(finding.severity == CONTRACT_EXHAUSTION_FINDING_BLOCKER for finding in findings):
        return (
            CONTRACT_EXHAUSTION_DECISION_BLOCKED,
            CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED,
            False,
        )
    if findings:
        return (
            CONTRACT_EXHAUSTION_DECISION_SCOPED,
            CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED,
            True,
        )
    return (
        CONTRACT_EXHAUSTION_DECISION_READY,
        CONTRACT_EXHAUSTION_CONFIDENCE_FULL,
        True,
    )


def _case_contract_path(case: ContractMutationCase) -> str:
    metadata = dict(case.metadata)
    values = _metadata_values(
        metadata,
        "contract_path",
        "field_path",
        "payload_path",
        "boundary_id",
        "code_boundary_id",
    )
    if values:
        return values[0]
    if case.dimension_id:
        return case.dimension_id
    if case.dimension_ids:
        return ".".join(case.dimension_ids)
    return case.case_id


def _retry_class_for_status(expected_status: str) -> str:
    if expected_status == CONTRACT_ORACLE_REISSUE_WITH_REPAIR_INFO:
        return "repair_and_resubmit"
    if expected_status == CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT:
        return "reject_and_repair"
    if expected_status == CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM:
        return "block_and_repair"
    if expected_status == CONTRACT_ORACLE_MARK_STALE:
        return "refresh_current_evidence"
    if expected_status == CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK:
        return "stop_repeat_and_escalate"
    return "none"


def _contract_fault_profiles_from_cases(
    cases: Sequence[ContractMutationCase],
    oracles: Sequence[ContractOracle],
) -> tuple[ContractFaultProfile, ...]:
    oracles_by_id = {oracle.oracle_id: oracle for oracle in oracles}
    profiles: list[ContractFaultProfile] = []
    for case in cases:
        oracle = oracles_by_id.get(case.oracle_id)
        expected_status = oracle.expected_status if oracle is not None else case.expected_status
        if not expected_status:
            continue
        profiles.append(
            ContractFaultProfile(
                profile_id=_case_id("contract_fault", case.case_id),
                source_case_id=case.case_id,
                mutation_type=case.mutation_type,
                contract_path=_case_contract_path(case),
                expected_status=expected_status,
                expected_message_fields=(
                    oracle.expected_message_fields
                    if oracle is not None
                    else _metadata_values(case.metadata, "expected_message_fields")
                ),
                required_repair_fields=(
                    oracle.required_repair_fields
                    if oracle is not None
                    else _metadata_values(case.metadata, "required_repair_fields")
                ),
                retry_class=_retry_class_for_status(expected_status),
                synthetic_only=True,
                live_completion_allowed=False,
                metadata={
                    "source_route": case.source_route,
                    "source_case_id": case.source_case_id,
                    "dimension_ids": list(case.dimension_ids),
                    "generation_kind": case.generation_kind,
                },
            )
        )
    return tuple(profiles)


def _coverage_universe_available_ids(
    plan: ContractExhaustionPlan,
    generated_cases: Sequence[ContractMutationCase],
    combination_cases: Sequence[ContractCombinationCase],
    coverage_receipts: Sequence[ModelContractCoverageReceipt],
) -> dict[str, set[str]]:
    payload_contract_ids: set[str] = set()
    boundary_ids: set[str] = set()
    for dimension in plan.dimensions:
        if dimension.dimension_type == CONTRACT_DIMENSION_PAYLOAD:
            payload_contract_ids.add(dimension.dimension_id)
        boundary_ids.add(dimension.dimension_id)
        payload_contract_ids.update(
            _metadata_values(dimension.metadata, "payload_contract_id", "payload_contract_ids")
        )
        boundary_ids.update(
            _metadata_values(dimension.metadata, "boundary_id", "boundary_ids", "code_boundary_id")
        )
    for axis in plan.axes:
        boundary_ids.add(axis.axis_id)
        boundary_ids.update(_metadata_values(axis.metadata, "boundary_id", "boundary_ids", "code_boundary_id"))
    for group in plan.interaction_groups:
        boundary_ids.add(group.group_id)
        boundary_ids.update(_metadata_values(group.metadata, "boundary_id", "boundary_ids", "code_boundary_id"))
    product_signatures = _product_signatures_for_report(plan, ())
    for case in generated_cases:
        boundary_ids.add(case.case_id)
        if case.dimension_id:
            boundary_ids.add(case.dimension_id)
        payload_contract_ids.update(
            _metadata_values(case.metadata, "payload_contract_id", "payload_contract_ids")
        )
        boundary_ids.update(
            _metadata_values(case.metadata, "boundary_id", "boundary_ids", "code_boundary_id")
        )
    return {
        "dimension": {dimension.dimension_id for dimension in plan.dimensions},
        "axis": {axis.axis_id for axis in plan.axes},
        "interaction_group": {group.group_id for group in plan.interaction_groups},
        "payload_contract": payload_contract_ids,
        "boundary": boundary_ids,
        "case": {case.case_id for case in generated_cases} | {case.case_id for case in combination_cases},
        "coverage_receipt": {receipt.receipt_id for receipt in coverage_receipts},
        "product_signature": {signature.signature_id for signature in product_signatures},
        "family_member": set(plan.materialized_family_member_ids),
        "reduction_candidate": set(plan.materialized_reduction_candidate_ids),
        "relation": {
            item_id
            for item_id, materializations in plan.relation_materializations.items()
            if materializations
        },
    }


def _coverage_universe_findings(
    plan: ContractExhaustionPlan,
    generated_cases: Sequence[ContractMutationCase],
    combination_cases: Sequence[ContractCombinationCase],
    coverage_receipts: Sequence[ModelContractCoverageReceipt],
) -> tuple[ContractExhaustionFinding, ...]:
    findings: list[ContractExhaustionFinding] = []
    universe = plan.coverage_universe
    if universe is None:
        if plan.require_coverage_universe or plan.claim_scope in _BROAD_CLAIMS:
            findings.append(
                _finding(
                    "coverage_universe_missing",
                    "broad contract-exhaustion claim has no declared coverage universe",
                    action=(
                        "declare ContractCoverageUniverse or narrow the claim to routine matrix confidence"
                    ),
                )
            )
        return tuple(findings)

    for exclusion in universe.exclusions:
        if not exclusion.complete():
            findings.append(
                _finding(
                    "coverage_universe_exclusion_incomplete",
                    "coverage-universe exclusion must name item kind, item id, reason, and owner route",
                    action="complete the exclusion or remove it from the coverage universe",
                    metadata={"universe_id": universe.universe_id, "exclusion": exclusion.to_dict()},
                )
            )

    available = _coverage_universe_available_ids(
        plan,
        generated_cases,
        combination_cases,
        coverage_receipts,
    )
    required_by_kind = {
        "dimension": universe.required_dimension_ids,
        "axis": universe.required_axis_ids,
        "interaction_group": universe.required_interaction_group_ids,
        "payload_contract": universe.required_payload_contract_ids,
        "boundary": universe.required_boundary_ids,
        "case": universe.required_case_ids,
        "coverage_receipt": universe.required_coverage_receipt_ids,
        "product_signature": universe.required_product_signature_ids,
        "family_member": universe.required_family_member_ids,
        "reduction_candidate": universe.required_reduction_candidate_ids,
        "relation": universe.required_relation_ids,
    }
    for item_kind, required_ids in required_by_kind.items():
        for item_id in required_ids:
            if item_id in available[item_kind] or universe.excluded(item_kind, item_id):
                continue
            findings.append(
                _finding(
                    "coverage_universe_item_missing",
                    "coverage universe names an item that is not present in the generated coverage",
                    action="project this item into ContractExhaustionMesh or add an explicit scoped exclusion",
                    metadata={
                        "universe_id": universe.universe_id,
                        "item_kind": item_kind,
                        "item_id": item_id,
                    },
                )
            )
    if (
        universe.require_full_product
        and universe.required_axis_ids
        and not universe.required_interaction_group_ids
        and not plan.interaction_groups
    ):
        findings.append(
            _finding(
                "coverage_universe_interaction_group_missing",
                "coverage universe requires finite axes but no interaction group declares their product",
                action="declare the model-local interaction group or scope out the product claim",
                metadata={"universe_id": universe.universe_id},
            )
        )
    if (
        universe.require_full_product
        and not universe.allow_partitioned_product
        and universe.required_axis_ids
    ):
        dimensions_by_id = {
            dimension.dimension_id: dimension for dimension in plan.dimensions
        }
        required_axis_set = set(universe.required_axis_ids)
        matching_groups: list[tuple[ContractInteractionGroup, ContractProductSignature]] = []
        for group in plan.interaction_groups:
            axes, _ = _axes_for_group(plan, group, dimensions_by_id)
            signature = build_contract_product_signature(plan, group, axes=axes)
            if set(signature.axis_ids) == required_axis_set:
                matching_groups.append((group, signature))
        if not matching_groups:
            findings.append(
                _finding(
                    "coverage_universe_full_product_group_missing",
                    "coverage universe requires one interaction group whose canonical signature contains every required axis",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="declare one model-local group with the exact required axis set",
                    metadata={
                        "universe_id": universe.universe_id,
                        "required_axis_ids": list(universe.required_axis_ids),
                        "declared_groups": [group.group_id for group in plan.interaction_groups],
                    },
                )
            )
        elif len(matching_groups) != 1:
            findings.append(
                _finding(
                    "coverage_universe_full_product_group_ambiguous",
                    "coverage universe full-product claim must bind exactly one interaction group signature",
                    severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                    action="split the declared axes into disjoint groups or select one exact product group",
                    metadata={
                        "universe_id": universe.universe_id,
                        "matching_group_ids": [group.group_id for group, _ in matching_groups],
                    },
                )
            )
        elif universe.required_product_signature_ids:
            available_signature_ids = {
                signature.signature_id for _, signature in matching_groups
            }
            missing_signatures = tuple(
                sorted(
                    set(universe.required_product_signature_ids)
                    - available_signature_ids
                    - {
                        exclusion.item_id
                        for exclusion in universe.exclusions
                        if exclusion.item_kind == "product_signature" and exclusion.complete()
                    }
                )
            )
            if missing_signatures:
                findings.append(
                    _finding(
                        "coverage_universe_product_signature_missing",
                        "coverage universe names a product signature that is not the exact generated group signature",
                        severity=CONTRACT_EXHAUSTION_FINDING_BLOCKER,
                        action="refresh required_product_signature_ids from the canonical interaction group",
                        metadata={
                            "universe_id": universe.universe_id,
                            "missing_signature_ids": list(missing_signatures),
                            "available_signature_ids": sorted(available_signature_ids),
                        },
                    )
                )
    return tuple(findings)


def _actionable_oracle_feedback_findings(
    plan: ContractExhaustionPlan,
    cases: Sequence[ContractMutationCase],
) -> tuple[ContractExhaustionFinding, ...]:
    if not (plan.require_actionable_oracle_feedback or plan.claim_scope in _BROAD_CLAIMS):
        return ()
    findings: list[ContractExhaustionFinding] = []
    oracles_by_id = {oracle.oracle_id: oracle for oracle in plan.oracles}
    for case in cases:
        if not case.required:
            continue
        oracle = oracles_by_id.get(case.oracle_id)
        expected_status = oracle.expected_status if oracle is not None else case.expected_status
        if expected_status not in _ACTIONABLE_ORACLE_STATUSES:
            continue
        if oracle is None:
            findings.append(
                _finding(
                    "contract_oracle_actionable_missing",
                    "actionable contract fault needs an explicit oracle with repair feedback fields",
                    case_id=case.case_id,
                    action="bind this case to a ContractOracle with expected_message_fields and required_repair_fields",
                )
            )
            continue
        if not oracle.expected_message_fields:
            findings.append(
                _finding(
                    "contract_oracle_feedback_fields_missing",
                    "actionable oracle does not name the feedback fields the receiver will see",
                    case_id=case.case_id,
                    action="add expected_message_fields to the ContractOracle",
                    metadata={"oracle_id": oracle.oracle_id},
                )
            )
        if not oracle.required_repair_fields:
            findings.append(
                _finding(
                    "contract_oracle_repair_fields_missing",
                    "actionable oracle does not name the fields required to repair the submission",
                    case_id=case.case_id,
                    action="add required_repair_fields to the ContractOracle",
                    metadata={"oracle_id": oracle.oracle_id},
                )
            )
    return tuple(findings)


def _observed_problem_backfeed_report(
    problems: Sequence[ObservedProblemBackfeed],
    generated_cases: Sequence[ContractMutationCase],
    combination_cases: Sequence[ContractCombinationCase],
    coverage_receipts: Sequence[ModelContractCoverageReceipt],
    coverage_universe: ContractCoverageUniverse | None,
) -> ObservedProblemBackfeedReport | None:
    if not problems:
        return None
    generated_case_ids = {case.case_id for case in generated_cases}
    combination_case_ids = {case.case_id for case in combination_cases}
    coverage_receipt_ids = {receipt.receipt_id for receipt in coverage_receipts}
    same_class_case_ids = {
        case.case_id
        for case in generated_cases
        if case.mutation_type == CONTRACT_MUTATION_SAME_CLASS_CASE or case.family_id
    }
    universe_dimension_ids = (
        set(coverage_universe.required_dimension_ids)
        if coverage_universe is not None
        else set()
    )
    findings: list[ContractExhaustionFinding] = []
    mapped: list[str] = []
    unmapped: list[str] = []
    for problem in problems:
        before_count = len(findings)
        if not problem.matched_case_ids and not problem.matched_combination_case_ids:
            findings.append(
                _finding(
                    "observed_problem_case_missing",
                    "observed problem is not mapped to any generated contract case",
                    action="add a ContractExhaustionMesh case or mark this as a new model gap",
                    metadata={"problem_id": problem.problem_id},
                )
            )
        for case_id in problem.matched_case_ids:
            if case_id not in generated_case_ids:
                findings.append(
                    _finding(
                        "observed_problem_case_unknown",
                        "observed problem references a case that was not generated by this report",
                        case_id=case_id,
                        action="regenerate the matrix or update the observed-problem mapping",
                        metadata={"problem_id": problem.problem_id},
                    )
                )
        for case_id in problem.matched_combination_case_ids:
            if case_id not in combination_case_ids:
                findings.append(
                    _finding(
                        "observed_problem_combination_case_unknown",
                        "observed problem references a Cartesian case that was not generated by this report",
                        case_id=case_id,
                        action="add the missing interaction group or update the mapping",
                        metadata={"problem_id": problem.problem_id},
                    )
                )
        if not problem.same_class_case_ids:
            findings.append(
                _finding(
                    "observed_problem_same_class_case_missing",
                    "observed problem has no same-class contract case proving the family was covered",
                    action="project the observed miss into a same-class ContractMutationCase",
                    metadata={"problem_id": problem.problem_id},
                )
            )
        for case_id in problem.same_class_case_ids:
            if case_id not in same_class_case_ids and case_id not in generated_case_ids:
                findings.append(
                    _finding(
                        "observed_problem_same_class_case_unknown",
                        "observed problem references a same-class case that is not in the generated matrix",
                        case_id=case_id,
                        action="generate the same-class case or update the backfeed row",
                        metadata={"problem_id": problem.problem_id},
                    )
                )
        if not problem.matched_coverage_receipt_ids:
            findings.append(
                _finding(
                    "observed_problem_receipt_missing",
                    "observed problem is not tied to a model coverage receipt",
                    action="run or attach the coverage receipt that now covers this miss",
                    metadata={"problem_id": problem.problem_id},
                )
            )
        for receipt_id in problem.matched_coverage_receipt_ids:
            if receipt_id not in coverage_receipt_ids:
                findings.append(
                    _finding(
                        "observed_problem_receipt_unknown",
                        "observed problem references a coverage receipt that is not present in this report",
                        action="attach the current receipt or rerun the coverage matrix",
                        metadata={"problem_id": problem.problem_id, "receipt_id": receipt_id},
                    )
                )
        for dimension_id in problem.affected_dimension_ids:
            if coverage_universe is not None and dimension_id not in universe_dimension_ids:
                findings.append(
                    _finding(
                        "observed_problem_dimension_outside_universe",
                        "observed problem names a dimension outside the declared coverage universe",
                        dimension_id=dimension_id,
                        action="add the dimension to the universe or record an explicit exclusion",
                        metadata={"problem_id": problem.problem_id},
                    )
                )
        if len(findings) == before_count:
            mapped.append(problem.problem_id)
        else:
            unmapped.append(problem.problem_id)
    decision, _, ok = _decision(findings)
    return ObservedProblemBackfeedReport(
        ok=ok,
        decision=decision,
        checked_problem_count=len(problems),
        mapped_problem_ids=_unique(mapped),
        unmapped_problem_ids=_unique(unmapped),
        findings=tuple(findings),
    )


def review_contract_exhaustion(
    plan: ContractExhaustionPlan,
    *,
    partition_context: _PartitionedProductVerificationContext | None = None,
) -> ContractExhaustionReport:
    """Generate contract bad cases and verify each has a model-owned reaction."""

    findings: list[ContractExhaustionFinding] = []
    partition_context = partition_context or plan.partition_context
    generated_cases: list[ContractMutationCase] = list(plan.seed_cases)
    combination_cases: list[ContractCombinationCase] = []
    coverage_shards: list[ContractCoverageShard] = list(plan.coverage_shards)
    materialization_values = _inventory_and_relation_cases(plan)
    generated_cases.extend(materialization_values[0])
    coverage_shards.extend(materialization_values[1])
    findings.extend(materialization_values[2])

    if (
        not plan.dimensions
        and not plan.seed_cases
        and not plan.interaction_groups
        and not materialization_values[0]
        and not (
            plan.expected_family_member_ids
            or plan.expected_reduction_candidate_ids
            or plan.canonical_relation_handoff
        )
    ):
        findings.append(
            _finding(
                "contract_boundary_missing",
                "contract exhaustion has no declared dimensions or seed bad cases",
                action="declare the finite contract boundary before claiming broad coverage",
            )
        )

    for dimension in plan.dimensions:
        if not dimension.finite:
            severity = CONTRACT_EXHAUSTION_FINDING_GAP
            if dimension.required and plan.claim_scope in _BROAD_CLAIMS and not plan.allow_unbounded_scoped:
                severity = CONTRACT_EXHAUSTION_FINDING_BLOCKER
            findings.append(
                _finding(
                    "contract_dimension_unbounded",
                    "dimension is not finite, so generated cases are scoped representatives",
                    severity=severity,
                    dimension_id=dimension.dimension_id,
                    action="split, bound, or explicitly scope this dimension",
            )
        )
        generated_cases.extend(_generated_cases_for_dimension(dimension))

    dimensions_by_id = {dimension.dimension_id: dimension for dimension in plan.dimensions}
    for group in plan.interaction_groups:
        cases, combos, shard, group_findings = _generated_cases_for_interaction_group(
            plan,
            group,
            dimensions_by_id,
        )
        generated_cases.extend(cases)
        combination_cases.extend(combos)
        if shard is not None:
            coverage_shards.append(shard)
        findings.extend(group_findings)

    generated_cases_tuple = tuple(generated_cases)
    combination_cases_tuple = tuple(combination_cases)
    coverage_shards_tuple = tuple(coverage_shards)
    oracle_ids = plan.oracle_ids()
    missing_oracle_case_ids: list[str] = []
    model_gap_dimension_ids: list[str] = []
    for case in generated_cases_tuple:
        has_oracle = bool(case.expected_status)
        if case.oracle_id:
            has_oracle = case.oracle_id in oracle_ids
            if not has_oracle:
                findings.append(
                    _finding(
                        "contract_oracle_unknown",
                        "case references an oracle id that is not declared in this plan",
                        case_id=case.case_id,
                        severity=(
                            CONTRACT_EXHAUSTION_FINDING_BLOCKER
                            if case.required
                            else CONTRACT_EXHAUSTION_FINDING_GAP
                        ),
                        action="add the oracle or change the case expected_status",
                    )
                )
        if plan.require_oracles_for_required_cases and case.required and not has_oracle:
            missing_oracle_case_ids.append(case.case_id)
            if case.dimension_id:
                model_gap_dimension_ids.append(case.dimension_id)
            findings.append(
                _finding(
                    "contract_oracle_missing",
                    "required generated bad case has no declared runtime/model reaction",
                    case_id=case.case_id,
                    dimension_id=case.dimension_id,
                    action="declare whether runtime rejects, blocks, reissues, marks stale, or scopes it",
                )
            )

    coverage_receipts = _coverage_receipts_for_report(
        plan,
        generated_cases_tuple,
        findings,
        coverage_shards_tuple,
    )
    product_signatures = _product_signatures_for_report(
        plan,
        coverage_shards_tuple,
    )
    coverage_findings = _coverage_receipt_findings(plan, coverage_receipts, coverage_shards_tuple)
    findings.extend(coverage_findings)
    universe_findings = _coverage_universe_findings(
        plan,
        generated_cases_tuple,
        combination_cases_tuple,
        coverage_receipts,
    )
    findings.extend(universe_findings)
    findings.extend(
        _partitioned_product_findings(
            plan,
            partition_context,
            combination_cases_tuple,
            coverage_receipts,
        )
    )
    actionable_findings = _actionable_oracle_feedback_findings(plan, generated_cases_tuple)
    findings.extend(actionable_findings)
    contract_fault_profiles = _contract_fault_profiles_from_cases(generated_cases_tuple, plan.oracles)
    backfeed_report = _observed_problem_backfeed_report(
        plan.observed_problem_backfeed,
        generated_cases_tuple,
        combination_cases_tuple,
        coverage_receipts,
        plan.coverage_universe,
    )
    if backfeed_report is not None:
        findings.extend(backfeed_report.findings)

    required_route_case_ids = _route_case_ids(generated_cases_tuple)
    composite_handoff_acceptances = _composite_handoff_acceptances(generated_cases_tuple)
    findings.extend(
        _composite_handoff_result_findings(
            plan,
            composite_handoff_acceptances,
        )
    )
    if (
        plan.require_composite_handoff_acceptance
        and plan.claim_scope in _BROAD_CLAIMS
        and any(case.required for case in generated_cases_tuple)
        and not composite_handoff_acceptances
    ):
        findings.append(
            _finding(
                "composite_handoff_acceptance_missing",
                "broad claim has generated cases but no independent composite handoff acceptance",
                action=(
                    "route each required case through a multi-route acceptance item "
                    "or narrow the claim to single-route matrix confidence"
                ),
            )
        )
    for route_id in plan.required_route_ids:
        if route_id not in required_route_case_ids:
            findings.append(
                _finding(
                    "required_route_without_case",
                    "plan requires a downstream route but no generated case feeds it",
                    severity=CONTRACT_EXHAUSTION_FINDING_GAP,
                    action="bind at least one required case to this route or remove the route claim",
                    metadata={"route_id": route_id},
                )
            )

    decision, confidence, ok = _decision(findings)
    return ContractExhaustionReport(
        plan_id=plan.plan_id,
        ok=ok,
        decision=decision,
        confidence=confidence,
        generated_cases=generated_cases_tuple,
        findings=tuple(findings),
        required_route_case_ids=required_route_case_ids,
        composite_handoff_acceptances=composite_handoff_acceptances,
        composite_handoff_results=tuple(plan.composite_handoff_results),
        missing_oracle_case_ids=_unique(missing_oracle_case_ids),
        model_gap_dimension_ids=_unique(model_gap_dimension_ids),
        combination_cases=combination_cases_tuple,
        coverage_shards=coverage_shards_tuple,
        product_signatures=product_signatures,
        coverage_receipts=coverage_receipts,
        required_coverage_receipt_ids=(
            plan.required_coverage_receipt_ids
            or (
                plan.coverage_universe.required_coverage_receipt_ids
                if plan.coverage_universe is not None
                else ()
            )
            or tuple(receipt.receipt_id for receipt in coverage_receipts)
        ),
        coverage_universe=plan.coverage_universe,
        contract_fault_profiles=contract_fault_profiles,
        observed_problem_backfeed_report=backfeed_report,
        inventory_revision=plan.inventory_revision,
        omitted_family_member_ids=materialization_values[3],
        omitted_reduction_candidate_ids=materialization_values[4],
        materialized_relation_ids=materialization_values[5],
        unmaterialized_relation_ids=materialization_values[6],
        downstream_relation_obligation_ids=_unique(
            f"contract_exhaustion:{case.case_id}"
            for case in materialization_values[0]
            if case.mutation_type
            in {
                CONTRACT_MUTATION_RELATION_MATERIALIZATION,
                CONTRACT_MUTATION_UNMATERIALIZED_RELATION_ID,
            }
        ),
        summary=(
            "matrix ready; broad chain confidence still requires composite handoff closure"
            if ok and not findings and composite_handoff_acceptances
            else "all generated contract cases have a declared reaction"
            if ok and not findings
            else "contract exhaustion needs route/model closure before broad confidence"
        ),
    )


def contract_fault_profiles_from_report(
    report: ContractExhaustionReport,
) -> tuple[ContractFaultProfile, ...]:
    """Return generic synthetic contract-fault profiles from a report."""

    if report.contract_fault_profiles:
        return report.contract_fault_profiles
    return _contract_fault_profiles_from_cases(report.generated_cases, ())


def review_observed_problem_backfeed(
    report: ContractExhaustionReport,
    observed_problems: Sequence[ObservedProblemBackfeed],
) -> ObservedProblemBackfeedReport:
    """Check that real observed misses map back to canonical generated cases."""

    backfeed_report = _observed_problem_backfeed_report(
        observed_problems,
        report.generated_cases,
        report.combination_cases,
        report.coverage_receipts,
        report.coverage_universe,
    )
    if backfeed_report is None:
        return ObservedProblemBackfeedReport(
            ok=True,
            decision=CONTRACT_EXHAUSTION_DECISION_READY,
        )
    return backfeed_report


def state_closure_cases_to_contract_cases(
    cases: Sequence[Any],
    *,
    source_route: str = "state_closure",
) -> tuple[ContractMutationCase, ...]:
    """Project StateClosureCase objects into ContractExhaustion cases."""

    result: list[ContractMutationCase] = []
    for case in cases:
        case_kind = str(getattr(case, "case_kind", ""))
        mutation_type = case_kind or CONTRACT_MUTATION_UNKNOWN_ENUM
        result.append(
            ContractMutationCase(
                case_id=_case_id("state_closure", getattr(case, "case_id", "")),
                dimension_id=str(getattr(case, "dimension_id", "")),
                mutation_type=mutation_type,
                source_route=source_route,
                source_case_id=str(getattr(case, "case_id", "")),
                input_delta={"value": to_jsonable(getattr(case, "value", None))},
                description=str(getattr(case, "description", "")),
                metadata=dict(getattr(case, "metadata", {}) or {}),
            )
        )
    return tuple(result)


def scenario_matrix_to_contract_cases(
    scenarios: Sequence[Any],
    *,
    source_route: str = "scenario_matrix",
) -> tuple[ContractMutationCase, ...]:
    """Project generated scenarios into ContractExhaustion bad/challenge cases."""

    result: list[ContractMutationCase] = []
    for scenario in scenarios:
        tags = tuple(str(tag) for tag in getattr(scenario, "tags", ()))
        expected = getattr(scenario, "expected", None)
        expected_status = str(getattr(expected, "expected_status", "") or CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW)
        result.append(
            ContractMutationCase(
                case_id=_case_id("scenario", getattr(scenario, "name", "")),
                mutation_type=CONTRACT_MUTATION_SCENARIO_CHALLENGE,
                source_route=source_route,
                source_case_id=str(getattr(scenario, "name", "")),
                expected_status=expected_status,
                input_delta={
                    "external_input_sequence": to_jsonable(
                        getattr(scenario, "external_input_sequence", ())
                    ),
                    "tags": list(tags),
                },
                required_routes=(
                    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                    CONTRACT_ROUTE_TEST_MESH,
                ),
                description=str(getattr(scenario, "description", "")),
                metadata={
                    "notes": str(getattr(scenario, "notes", "")),
                    "tags": list(tags),
                },
            )
        )
    return tuple(result)


def family_bad_case_seed_to_contract_cases(
    family: Any,
    seed: Any,
    *,
    source_route: str = "obligation_family_parity",
) -> tuple[ContractMutationCase, ...]:
    """Project same-class derived bad cases into ContractExhaustion cases."""

    from .obligation_family import derive_same_class_bad_cases

    result: list[ContractMutationCase] = []
    for case in derive_same_class_bad_cases(family, seed):
        result.append(
            ContractMutationCase(
                case_id=_case_id("same_class", case.case_id),
                mutation_type=CONTRACT_MUTATION_SAME_CLASS_CASE,
                source_route=source_route,
                source_case_id=case.source_case_id or case.case_id,
                expected_status=case.expected_status,
                family_id=case.family_id,
                member_id=case.member_id,
                required_routes=(
                    CONTRACT_ROUTE_OBLIGATION_FAMILY,
                    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                    CONTRACT_ROUTE_TEST_MESH,
                ),
                description=case.description,
                metadata={
                    "mechanism_id": case.mechanism_id,
                    "failure_mode": case.failure_mode,
                    "source_member_id": case.source_member_id,
                    "affected_model_ids": list(getattr(case, "affected_model_ids", ())),
                    "root_cause_dimension_ids": list(getattr(case, "root_cause_dimension_ids", ())),
                    "interaction_group_ids": list(getattr(case, "interaction_group_ids", ())),
                    "observed_combination_case_id": str(getattr(case, "observed_combination_case_id", "")),
                    "generated_combination_case_ids": list(getattr(case, "generated_combination_case_ids", ())),
                    "coverage_receipt_ids": list(getattr(case, "coverage_receipt_ids", ())),
                    **dict(case.metadata),
                },
            )
        )
    return tuple(result)


def artifact_payload_cases_to_contract_cases(
    payload_contract: Any,
    *,
    source_route: str = "artifact_payload",
) -> tuple[ContractMutationCase, ...]:
    """Project artifact payload contract cases into normalized bad cases."""

    result: list[ContractMutationCase] = []
    contract_id = str(getattr(payload_contract, "payload_contract_id", ""))
    for case in getattr(payload_contract, "cases", ()):
        expected_status = str(getattr(case, "expected_status", "") or "")
        mutation_type = (
            CONTRACT_MUTATION_CONFLICTING_PAYLOAD
            if expected_status == "rejected"
            else CONTRACT_MUTATION_MISSING_BODY
        )
        result.append(
            ContractMutationCase(
                case_id=_case_id("payload", contract_id, getattr(case, "case_id", "")),
                dimension_id=contract_id,
                mutation_type=mutation_type,
                source_route=source_route,
                source_case_id=str(getattr(case, "case_id", "")),
                required=bool(getattr(case, "required", True)),
                expected_status=(
                    CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM
                    if expected_status == "rejected"
                    else CONTRACT_ORACLE_PASS_ALLOWED
                ),
                input_delta={
                    "expected_output": str(getattr(case, "expected_output", "")),
                    "expected_error_path": str(getattr(case, "expected_error_path", "")),
                    "round_trip_required": bool(getattr(case, "round_trip_required", False)),
                },
                required_routes=(
                    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                    CONTRACT_ROUTE_TEST_MESH,
                    CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
                ),
                description=str(getattr(case, "description", "")),
                metadata={
                    "payload_contract_id": contract_id,
                    "payload_surface": str(getattr(payload_contract, "payload_surface", "")),
                    "payload_kind": str(getattr(payload_contract, "payload_kind", "")),
                },
            )
        )
    return tuple(result)


def transition_coverage_to_contract_cases(
    matrix: Any,
    *,
    source_route: str = "transition_coverage",
) -> tuple[ContractMutationCase, ...]:
    """Project TransitionCoverageMatrix cells into ContractExhaustion cases."""

    cells = matrix.required_cells() if hasattr(matrix, "required_cells") else getattr(matrix, "cells", ())
    result: list[ContractMutationCase] = []
    for cell in cells:
        result.append(
            ContractMutationCase(
                case_id=_case_id("transition", getattr(matrix, "matrix_id", ""), getattr(cell, "cell_id", "")),
                dimension_id=str(getattr(cell, "cell_id", "")),
                mutation_type=CONTRACT_MUTATION_TRANSITION_REPLAY,
                source_route=source_route,
                source_case_id=str(getattr(cell, "cell_id", "")),
                input_delta={
                    "source_state": str(getattr(cell, "source_state", "")),
                    "trigger": str(getattr(cell, "trigger", "")),
                    "target_state": str(getattr(cell, "target_state", "")),
                    "expected_output": str(getattr(cell, "expected_output", "")),
                },
                required_routes=(
                    CONTRACT_ROUTE_MODEL_MESH,
                    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                    CONTRACT_ROUTE_TEST_MESH,
                ),
                required_test_cell_id=str(getattr(cell, "cell_id", "")),
                description=str(getattr(cell, "rationale", "")),
                metadata={
                    "matrix_id": str(getattr(matrix, "matrix_id", "")),
                    "model_id": str(getattr(matrix, "model_id", "")),
                    "code_contract_id": str(getattr(cell, "code_contract_id", "")),
                    "runtime_node_id": str(getattr(cell, "runtime_node_id", "")),
                    "required_test_kinds": list(getattr(cell, "required_test_kinds", ())),
                },
            )
        )
    return tuple(result)


def model_mesh_closure_to_contract_cases(
    closure_model: Any,
    *,
    source_route: str = "model_mesh",
) -> tuple[ContractMutationCase, ...]:
    """Project parent/child closure handoffs into ContractExhaustion cases."""

    result: list[ContractMutationCase] = []
    parent_model_id = str(getattr(closure_model, "parent_model_id", ""))
    for transition in getattr(closure_model, "transitions", ()):
        mutation_type = (
            CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA
            if bool(getattr(transition, "loop", False))
            or tuple(getattr(transition, "repeat_input_tokens", ()))
            else CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE
        )
        result.append(
            ContractMutationCase(
                case_id=_case_id("mesh_closure", parent_model_id, getattr(transition, "transition_id", "")),
                dimension_id=str(getattr(transition, "transition_id", "")),
                mutation_type=mutation_type,
                source_route=source_route,
                source_case_id=str(getattr(transition, "transition_id", "")),
                input_delta={
                    "consumes": list(getattr(transition, "consumes", ())),
                    "emits": list(getattr(transition, "emits", ())),
                    "repeat_input_tokens": list(getattr(transition, "repeat_input_tokens", ())),
                },
                required_routes=(
                    CONTRACT_ROUTE_MODEL_MESH,
                    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                    CONTRACT_ROUTE_TEST_MESH,
                ),
                freshness_scope="latest_child_evidence",
                description=str(getattr(transition, "rationale", "")),
                metadata={
                    "parent_model_id": parent_model_id,
                    "consumer_model_id": str(getattr(transition, "consumer_model_id", "")),
                    "code_contract_id": str(getattr(transition, "code_contract_id", "")),
                    "runtime_node_id": str(getattr(transition, "runtime_node_id", "")),
                },
            )
        )
    return tuple(result)


def contract_exhaustion_to_model_obligations(report: ContractExhaustionReport) -> tuple[Any, ...]:
    """Project generated cases into Model-Test Alignment obligations."""

    from .model_test_alignment import (
        TEST_KIND_NEGATIVE_PATH,
        TEST_KIND_REPLAY,
        ModelObligation,
    )

    obligations: list[Any] = []
    for case in report.generated_cases:
        if CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT not in case.routes():
            continue
        required_test_kinds = (TEST_KIND_REPLAY,) if case.required_test_cell_id else (TEST_KIND_NEGATIVE_PATH,)
        external_inputs = tuple(
            value
            for value in (
                case.mutation_type,
                *case.axis_case_ids,
                case.interaction_group_id,
            )
            if str(value)
        )
        obligations.append(
            ModelObligation(
                f"contract_exhaustion:{case.case_id}",
                obligation_type=CONTRACT_EXHAUSTION_ROUTE,
                description=case.description or case.mutation_type,
                required=case.required,
                required_test_kinds=required_test_kinds,
                risk_level="high",
                external_inputs=external_inputs,
                external_outputs=(case.expected_status,),
                error_paths=(case.expected_status,),
                exact_external_contract=True,
                required_runtime_node_ids=tuple(
                    str(value)
                    for value in (
                        case.metadata.get("runtime_node_id", ""),
                    )
                    if str(value)
                ),
                relation_ids=_metadata_values(
                    case.metadata,
                    "relation_ids",
                ),
                relation_test_obligation_ids=_metadata_values(
                    case.metadata,
                    "relation_test_obligation_ids",
                ),
                relation_impacted_model_ids=_metadata_values(
                    case.metadata,
                    "affected_model_ids",
                ),
            )
        )
    return tuple(obligations)


def contract_exhaustion_to_test_mesh_cell_ids(report: ContractExhaustionReport) -> tuple[str, ...]:
    """Return required case ids that TestMesh must close with fresh evidence."""

    return report.required_testmesh_case_ids


def contract_exhaustion_to_test_mesh_shard_ids(report: ContractExhaustionReport) -> tuple[str, ...]:
    """Return Cartesian shard ids that TestMesh must close as child evidence."""

    return report.required_coverage_shard_ids


def contract_exhaustion_to_risk_gate_ids(report: ContractExhaustionReport) -> tuple[str, ...]:
    """Return required risk/evidence gate ids for ledger-style evidence checks."""

    return _unique(
        case.risk_gate_id or case.case_id
        for case in report.generated_cases
        if CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER in case.routes()
    )


def contract_exhaustion_to_composite_handoff_acceptance_ids(
    report: ContractExhaustionReport,
) -> tuple[str, ...]:
    """Return acceptance ids that must close before whole-chain confidence."""

    return report.required_composite_handoff_acceptance_ids


def contract_exhaustion_to_coverage_receipt_ids(report: ContractExhaustionReport) -> tuple[str, ...]:
    """Return model coverage receipt ids that parent ModelMesh/RiskLedger gates consume."""

    return _unique(receipt.receipt_id for receipt in report.coverage_receipts if receipt.receipt_id)


__all__ = (
    "CONTRACT_DIMENSION_EVIDENCE",
    "CONTRACT_DIMENSION_FIELD",
    "CONTRACT_DIMENSION_INPUT",
    "CONTRACT_DIMENSION_LOOP",
    "CONTRACT_DIMENSION_PARENT_CHILD",
    "CONTRACT_DIMENSION_PAYLOAD",
    "CONTRACT_DIMENSION_SAME_CLASS",
    "CONTRACT_DIMENSION_STATE",
    "CONTRACT_DIMENSION_TRANSITION",
    "CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED",
    "CONTRACT_EXHAUSTION_CONFIDENCE_FULL",
    "CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED",
    "CONTRACT_EXHAUSTION_DECISION_BLOCKED",
    "CONTRACT_EXHAUSTION_DECISION_READY",
    "CONTRACT_EXHAUSTION_DECISION_SCOPED",
    "CONTRACT_EXHAUSTION_FINDING_BLOCKER",
    "CONTRACT_EXHAUSTION_FINDING_GAP",
    "CONTRACT_EXHAUSTION_FINDING_INFO",
    "CONTRACT_EXHAUSTION_ROUTE",
    "CONTRACT_MUTATION_SAME_CLASS_CASE",
    "CONTRACT_MUTATION_CARTESIAN_COMBINATION",
    "CONTRACT_MUTATION_CONFLICTING_PAYLOAD",
    "CONTRACT_MUTATION_EMPTY_VALUE",
    "CONTRACT_MUTATION_MALFORMED_INPUT",
    "CONTRACT_MUTATION_MISSING_BODY",
    "CONTRACT_MUTATION_MISSING_EVIDENCE_FILE",
    "CONTRACT_MUTATION_MISSING_REQUIRED_FIELD",
    "CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER",
    "CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE",
    "CONTRACT_MUTATION_PATH_MISMATCH",
    "CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA",
    "CONTRACT_MUTATION_SCENARIO_CHALLENGE",
    "CONTRACT_MUTATION_RELATION_MATERIALIZATION",
    "CONTRACT_MUTATION_STALE_CHILD_EVIDENCE",
    "CONTRACT_MUTATION_STALE_EVIDENCE",
    "CONTRACT_MUTATION_TRANSITION_REPLAY",
    "CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE",
    "CONTRACT_MUTATION_UNKNOWN_ENUM",
    "CONTRACT_MUTATION_UNMATERIALIZED_RELATION_ID",
    "CONTRACT_MUTATION_WRONG_TYPE",
    "CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM",
    "CONTRACT_ORACLE_MARK_STALE",
    "CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW",
    "CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK",
    "CONTRACT_ORACLE_PASS_ALLOWED",
    "CONTRACT_ORACLE_REISSUE_WITH_REPAIR_INFO",
    "CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT",
    "CONTRACT_ORACLE_SCOPED_CONFIDENCE",
    "CONTRACT_GENERATION_LOCAL_CARTESIAN",
    "CONTRACT_GENERATION_PARENT_INTERFACE",
    "CONTRACT_GENERATION_SINGLE_DIMENSION",
    "CONTRACT_STRICT_CLAIM_SCOPES",
    "CONTRACT_MODEL_LEVEL_CHILD",
    "CONTRACT_MODEL_LEVEL_LEAF",
    "CONTRACT_MODEL_LEVEL_PARENT",
    "CONTRACT_MODEL_LEVEL_ROOT",
    "CONTRACT_COVERAGE_STATUS_BLOCKED",
    "CONTRACT_COVERAGE_STATUS_COVERED",
    "CONTRACT_COVERAGE_STATUS_IN_PROGRESS",
    "CONTRACT_COVERAGE_STATUS_SCOPED",
    "DEFAULT_CARTESIAN_CASE_LIMIT",
    "CONTRACT_ROUTE_FIELD_LIFECYCLE",
    "CONTRACT_ROUTE_MODEL_MESH",
    "CONTRACT_ROUTE_MODEL_MISS_REVIEW",
    "CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT",
    "CONTRACT_ROUTE_OBLIGATION_FAMILY",
    "CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER",
    "CONTRACT_ROUTE_TEST_MESH",
    "CompositeHandoffAcceptance",
    "CompositeHandoffResult",
    "ContractAxis",
    "ContractCombinationCase",
    "ContractCoverageExclusion",
    "ContractCoverageShard",
    "ContractCoverageUniverse",
    "ContractDimension",
    "ContractExhaustionFinding",
    "ContractExhaustionPlan",
    "ContractExhaustionReport",
    "ContractFaultProfile",
    "ContractInteractionGroup",
    "ContractMutationCase",
    "ContractOracle",
    "ContractProductSignature",
    "_PartitionedProductVerificationContext",
    "bind_partition_context_to_plan",
    "ModelContractCoverageReceipt",
    "NativeChildEvidenceBinding",
    "ObservedProblemBackfeed",
    "ObservedProblemBackfeedReport",
    "artifact_payload_cases_to_contract_cases",
    "build_contract_product_signature",
    "contract_fault_profiles_from_report",
    "contract_exhaustion_to_composite_handoff_acceptance_ids",
    "contract_exhaustion_to_coverage_receipt_ids",
    "contract_exhaustion_to_model_obligations",
    "contract_exhaustion_to_risk_gate_ids",
    "contract_exhaustion_to_test_mesh_cell_ids",
    "contract_exhaustion_to_test_mesh_shard_ids",
    "family_bad_case_seed_to_contract_cases",
    "model_mesh_closure_to_contract_cases",
    "review_contract_exhaustion",
    "partition_context_from_accepted_authority",
    "review_native_child_evidence",
    "review_observed_problem_backfeed",
    "scenario_matrix_to_contract_cases",
    "state_closure_cases_to_contract_cases",
    "transition_coverage_to_contract_cases",
)
