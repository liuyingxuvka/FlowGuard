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

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Iterable, Mapping, Sequence

from .export import to_json_text, to_jsonable


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
CONTRACT_MUTATION_ANALOGOUS_DEFECT = "analogous_defect"
CONTRACT_MUTATION_CARTESIAN_COMBINATION = "cartesian_combination"

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

CONTRACT_MODEL_LEVEL_ROOT = "root"
CONTRACT_MODEL_LEVEL_PARENT = "parent"
CONTRACT_MODEL_LEVEL_CHILD = "child"
CONTRACT_MODEL_LEVEL_LEAF = "leaf"

CONTRACT_COVERAGE_STATUS_COVERED = "covered"
CONTRACT_COVERAGE_STATUS_SCOPED = "scoped"
CONTRACT_COVERAGE_STATUS_BLOCKED = "blocked"
CONTRACT_COVERAGE_STATUS_IN_PROGRESS = "in_progress"

DEFAULT_CARTESIAN_CASE_LIMIT = 100_000

_BROAD_CLAIMS = {"done", "release", "publish", "production", "full"}

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
        CONTRACT_MUTATION_ANALOGOUS_DEFECT,
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
    CONTRACT_MUTATION_ANALOGOUS_DEFECT: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values if str(value))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _case_id(*parts: str) -> str:
    return ":".join(str(part).replace(" ", "_") for part in parts if str(part))


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
        if self.mutation_type == CONTRACT_MUTATION_ANALOGOUS_DEFECT:
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
    oracle_status: str = CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

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
        object.__setattr__(self, "oracle_status", str(self.oracle_status))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

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
            "oracle_status": self.oracle_status,
            "description": self.description,
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
            "metadata": to_jsonable(dict(self.metadata)),
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
    require_model_coverage_receipt: bool = False
    cartesian_case_limit: int = DEFAULT_CARTESIAN_CASE_LIMIT

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
        object.__setattr__(self, "require_model_coverage_receipt", bool(self.require_model_coverage_receipt))
        object.__setattr__(self, "cartesian_case_limit", int(self.cartesian_case_limit))

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
            "require_model_coverage_receipt": self.require_model_coverage_receipt,
            "cartesian_case_limit": self.cartesian_case_limit,
        }


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
    missing_oracle_case_ids: tuple[str, ...] = ()
    model_gap_dimension_ids: tuple[str, ...] = ()
    summary: str = ""
    combination_cases: tuple[ContractCombinationCase, ...] = ()
    coverage_shards: tuple[ContractCoverageShard, ...] = ()
    coverage_receipts: tuple[ModelContractCoverageReceipt, ...] = ()
    required_coverage_receipt_ids: tuple[str, ...] = ()

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
            "required_composite_handoff_acceptance_ids": list(
                self.required_composite_handoff_acceptance_ids
            ),
            "missing_oracle_case_ids": list(self.missing_oracle_case_ids),
            "model_gap_dimension_ids": list(self.model_gap_dimension_ids),
            "summary": self.summary,
            "combination_cases": [case.to_dict() for case in self.combination_cases],
            "coverage_shards": [shard.to_dict() for shard in self.coverage_shards],
            "coverage_receipts": [receipt.to_dict() for receipt in self.coverage_receipts],
            "required_coverage_receipt_ids": list(self.required_coverage_receipt_ids),
            "required_combination_case_ids": list(self.required_combination_case_ids),
            "required_coverage_shard_ids": list(self.required_coverage_shard_ids),
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
    return tuple(axes), tuple(findings)


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
            metadata={
                "plan_id": plan.plan_id,
                "model_level": plan.model_level,
                "required_coverage_receipt_ids": list(plan.required_coverage_receipt_ids),
            },
        )
    )
    return tuple(receipts)


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


def review_contract_exhaustion(plan: ContractExhaustionPlan) -> ContractExhaustionReport:
    """Generate contract bad cases and verify each has a model-owned reaction."""

    findings: list[ContractExhaustionFinding] = []
    generated_cases: list[ContractMutationCase] = list(plan.seed_cases)
    combination_cases: list[ContractCombinationCase] = []
    coverage_shards: list[ContractCoverageShard] = list(plan.coverage_shards)

    if not plan.dimensions and not plan.seed_cases and not plan.interaction_groups:
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
    coverage_findings = _coverage_receipt_findings(plan, coverage_receipts, coverage_shards_tuple)
    findings.extend(coverage_findings)

    required_route_case_ids = _route_case_ids(generated_cases_tuple)
    composite_handoff_acceptances = _composite_handoff_acceptances(generated_cases_tuple)
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
        missing_oracle_case_ids=_unique(missing_oracle_case_ids),
        model_gap_dimension_ids=_unique(model_gap_dimension_ids),
        combination_cases=combination_cases_tuple,
        coverage_shards=coverage_shards_tuple,
        coverage_receipts=coverage_receipts,
        required_coverage_receipt_ids=(
            plan.required_coverage_receipt_ids
            or tuple(receipt.receipt_id for receipt in coverage_receipts)
        ),
        summary=(
            "matrix ready; broad chain confidence still requires composite handoff closure"
            if ok and not findings and composite_handoff_acceptances
            else "all generated contract cases have a declared reaction"
            if ok and not findings
            else "contract exhaustion needs route/model closure before broad confidence"
        ),
    )


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
                mutation_type=CONTRACT_MUTATION_ANALOGOUS_DEFECT,
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
    "CONTRACT_MUTATION_ANALOGOUS_DEFECT",
    "CONTRACT_MUTATION_CARTESIAN_COMBINATION",
    "CONTRACT_MUTATION_CONFLICTING_PAYLOAD",
    "CONTRACT_MUTATION_EMPTY_VALUE",
    "CONTRACT_MUTATION_MALFORMED_INPUT",
    "CONTRACT_MUTATION_MISSING_BODY",
    "CONTRACT_MUTATION_MISSING_EVIDENCE_FILE",
    "CONTRACT_MUTATION_MISSING_REQUIRED_FIELD",
    "CONTRACT_MUTATION_PATH_MISMATCH",
    "CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA",
    "CONTRACT_MUTATION_SCENARIO_CHALLENGE",
    "CONTRACT_MUTATION_STALE_CHILD_EVIDENCE",
    "CONTRACT_MUTATION_STALE_EVIDENCE",
    "CONTRACT_MUTATION_TRANSITION_REPLAY",
    "CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE",
    "CONTRACT_MUTATION_UNKNOWN_ENUM",
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
    "ContractAxis",
    "ContractCombinationCase",
    "ContractCoverageShard",
    "ContractDimension",
    "ContractExhaustionFinding",
    "ContractExhaustionPlan",
    "ContractExhaustionReport",
    "ContractInteractionGroup",
    "ContractMutationCase",
    "ContractOracle",
    "ModelContractCoverageReceipt",
    "artifact_payload_cases_to_contract_cases",
    "contract_exhaustion_to_composite_handoff_acceptance_ids",
    "contract_exhaustion_to_coverage_receipt_ids",
    "contract_exhaustion_to_model_obligations",
    "contract_exhaustion_to_risk_gate_ids",
    "contract_exhaustion_to_test_mesh_cell_ids",
    "contract_exhaustion_to_test_mesh_shard_ids",
    "family_bad_case_seed_to_contract_cases",
    "model_mesh_closure_to_contract_cases",
    "review_contract_exhaustion",
    "scenario_matrix_to_contract_cases",
    "state_closure_cases_to_contract_cases",
    "transition_coverage_to_contract_cases",
)
