"""Finite bad-case generation and execution against a real function.

Oracle names describe required reactions.  Execution observes rejection; it
cannot by itself establish when an arbitrary function produced side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from itertools import product
from typing import Any, Iterable, Mapping, Sequence

from ._normalization import nonempty_string_sequence as _as_tuple, unique_strings as _unique
from .export import to_jsonable

CONTRACT_DIMENSION_FIELD = "field"
CONTRACT_DIMENSION_STATE = "state"
CONTRACT_DIMENSION_INPUT = "input"
CONTRACT_DIMENSION_PAYLOAD = "payload"
CONTRACT_DIMENSION_TRANSITION = "transition"
CONTRACT_DIMENSION_SAME_CLASS = "same_class"
CONTRACT_DIMENSION_LOOP = "loop"
CONTRACT_MUTATION_MISSING_REQUIRED_FIELD = "missing_required_field"
CONTRACT_MUTATION_EMPTY_VALUE = "empty_value"
CONTRACT_MUTATION_WRONG_TYPE = "wrong_type"
CONTRACT_MUTATION_UNKNOWN_ENUM = "unknown_enum"
CONTRACT_MUTATION_MALFORMED_INPUT = "malformed_input"
CONTRACT_MUTATION_MISSING_BODY = "missing_body"
CONTRACT_MUTATION_PATH_MISMATCH = "path_mismatch"
CONTRACT_MUTATION_CONFLICTING_PAYLOAD = "conflicting_payload"
CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA = "repeat_without_delta"
CONTRACT_MUTATION_TRANSITION_REPLAY = "transition_replay"
CONTRACT_MUTATION_SAME_CLASS_CASE = "same_class_case"
CONTRACT_MUTATION_CARTESIAN_COMBINATION = "cartesian_combination"
CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER = "omitted_family_member"
CONTRACT_MUTATION_OLD_SCHEMA_VERSION = "old_schema_version"
CONTRACT_MUTATION_CONFLICTING_IDENTITY = "conflicting_identity"
CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT = "reject_before_side_effect"
CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM = "block_before_downstream"
CONTRACT_ORACLE_REISSUE_WITH_REPAIR_INFO = "reissue_with_repair_info"
CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK = "no_delta_loop_block"
CONTRACT_ORACLE_PASS_ALLOWED = "pass_allowed"
CONTRACT_GENERATION_SINGLE_DIMENSION = "single_dimension"
CONTRACT_GENERATION_LOCAL_CARTESIAN = "local_cartesian"
DEFAULT_CARTESIAN_CASE_LIMIT = 100_000

_DIMENSION_DEFAULT_MUTATIONS = {
    CONTRACT_DIMENSION_FIELD: (CONTRACT_MUTATION_MISSING_REQUIRED_FIELD, CONTRACT_MUTATION_EMPTY_VALUE,
                               CONTRACT_MUTATION_WRONG_TYPE),
    CONTRACT_DIMENSION_STATE: (CONTRACT_MUTATION_UNKNOWN_ENUM, CONTRACT_MUTATION_MALFORMED_INPUT),
    CONTRACT_DIMENSION_INPUT: (CONTRACT_MUTATION_UNKNOWN_ENUM, CONTRACT_MUTATION_MALFORMED_INPUT,
                               CONTRACT_MUTATION_OLD_SCHEMA_VERSION, CONTRACT_MUTATION_CONFLICTING_IDENTITY),
    CONTRACT_DIMENSION_PAYLOAD: (CONTRACT_MUTATION_MISSING_BODY, CONTRACT_MUTATION_MALFORMED_INPUT,
                                 CONTRACT_MUTATION_CONFLICTING_PAYLOAD, CONTRACT_MUTATION_OLD_SCHEMA_VERSION,
                                 CONTRACT_MUTATION_CONFLICTING_IDENTITY),
    CONTRACT_DIMENSION_TRANSITION: (CONTRACT_MUTATION_TRANSITION_REPLAY,),
    CONTRACT_DIMENSION_SAME_CLASS: (CONTRACT_MUTATION_SAME_CLASS_CASE,),
    CONTRACT_DIMENSION_LOOP: (CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA,),
}
_MUTATION_DEFAULT_ORACLE = {
    CONTRACT_MUTATION_MISSING_REQUIRED_FIELD: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_EMPTY_VALUE: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_WRONG_TYPE: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_UNKNOWN_ENUM: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_MALFORMED_INPUT: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_MISSING_BODY: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_PATH_MISMATCH: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_CONFLICTING_PAYLOAD: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA: CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK,
    CONTRACT_MUTATION_TRANSITION_REPLAY: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_SAME_CLASS_CASE: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER: CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
    CONTRACT_MUTATION_OLD_SCHEMA_VERSION: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_MUTATION_CONFLICTING_IDENTITY: CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
}


def _normalize(record, strings=(), sequences=(), booleans=()):
    for name in strings:
        object.__setattr__(record, name, str(getattr(record, name)))
    for name in sequences:
        object.__setattr__(record, name, _as_tuple(getattr(record, name)))
    for name in booleans:
        object.__setattr__(record, name, bool(getattr(record, name)))
    if hasattr(record, "metadata"):
        object.__setattr__(record, "metadata", dict(record.metadata or {}))


def _record_dict(record):
    return to_jsonable({item.name: getattr(record, item.name) for item in fields(record)})


@dataclass(frozen=True)
class ContractDimension:
    dimension_id: str
    dimension_type: str
    owner_model_id: str = ""
    required: bool = True
    finite: bool = True
    values: tuple[str, ...] = ()
    mutation_types: tuple[str, ...] = ()
    field_refs: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("dimension_id", "dimension_type", "owner_model_id", "description"),
                   ("values", "mutation_types", "field_refs"), ("required", "finite"))

    def default_mutations(self) -> tuple[str, ...]:
        return self.mutation_types or _DIMENSION_DEFAULT_MUTATIONS.get(
            self.dimension_type, (CONTRACT_MUTATION_MISSING_REQUIRED_FIELD, CONTRACT_MUTATION_MALFORMED_INPUT))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class ContractOracle:
    oracle_id: str
    expected_status: str
    expected_message_fields: tuple[str, ...] = ()
    forbidden_downstream_steps: tuple[str, ...] = ()
    required_repair_fields: tuple[str, ...] = ()
    allowed_side_effects: tuple[str, ...] = ()
    disallowed_side_effects: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("oracle_id", "expected_status", "description"),
                   ("expected_message_fields", "forbidden_downstream_steps", "required_repair_fields",
                    "allowed_side_effects", "disallowed_side_effects"))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class ContractMutationCase:
    case_id: str
    dimension_id: str = ""
    mutation_type: str = ""
    source_case_id: str = ""
    required: bool = True
    oracle_id: str = ""
    input_delta: Mapping[str, Any] = field(default_factory=dict)
    expected_status: str = ""
    family_id: str = ""
    member_id: str = ""
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    dimension_ids: tuple[str, ...] = ()
    axis_case_ids: tuple[str, ...] = ()
    interaction_group_id: str = ""
    combination_order: int = 0
    model_id: str = ""
    generation_kind: str = CONTRACT_GENERATION_SINGLE_DIMENSION

    def __post_init__(self):
        _normalize(self, ("case_id", "dimension_id", "mutation_type", "source_case_id", "oracle_id",
                          "family_id", "member_id", "description", "interaction_group_id", "model_id",
                          "generation_kind"), ("dimension_ids", "axis_case_ids"), ("required",))
        object.__setattr__(self, "input_delta", dict(self.input_delta or {}))
        object.__setattr__(self, "expected_status", str(self.expected_status or
                           _MUTATION_DEFAULT_ORACLE.get(self.mutation_type, "")))
        object.__setattr__(self, "combination_order", int(self.combination_order))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class ContractAxis:
    axis_id: str
    model_id: str = ""
    dimension_ids: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    mutation_types: tuple[str, ...] = ()
    required: bool = True
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("axis_id", "model_id", "description"), ("dimension_ids", "values", "mutation_types"),
                   ("required",))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class ContractInteractionGroup:
    group_id: str
    model_id: str = ""
    axis_ids: tuple[str, ...] = ()
    dimension_ids: tuple[str, ...] = ()
    generation_kind: str = CONTRACT_GENERATION_LOCAL_CARTESIAN
    required: bool = True
    max_combinations: int | None = None
    oracle_id: str = ""
    oracle_status: str = CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        _normalize(self, ("group_id", "model_id", "generation_kind", "oracle_id", "oracle_status", "description"),
                   ("axis_ids", "dimension_ids"), ("required",))
        if self.max_combinations is not None:
            object.__setattr__(self, "max_combinations", int(self.max_combinations))

    def to_dict(self):
        return _record_dict(self)


@dataclass(frozen=True)
class ContractExhaustionPlan:
    plan_id: str
    dimensions: tuple[ContractDimension, ...] = ()
    seed_cases: tuple[ContractMutationCase, ...] = ()
    oracles: tuple[ContractOracle, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    model_id: str = ""
    axes: tuple[ContractAxis, ...] = ()
    interaction_groups: tuple[ContractInteractionGroup, ...] = ()
    cartesian_case_limit: int = DEFAULT_CARTESIAN_CASE_LIMIT
    expected_family_member_ids: tuple[str, ...] = ()
    materialized_family_member_ids: tuple[str, ...] = ()

    def __post_init__(self):
        _normalize(self, ("plan_id", "model_id"), ("expected_family_member_ids", "materialized_family_member_ids"))
        for name in ("dimensions", "seed_cases", "oracles", "axes", "interaction_groups"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "cartesian_case_limit", int(self.cartesian_case_limit))

    def oracle_ids(self):
        return tuple(oracle.oracle_id for oracle in self.oracles)

    def to_dict(self):
        return _record_dict(self)


def _case_id(*parts: str) -> str:
    return ":".join(str(part).replace(" ", "_") for part in parts if str(part))


def _product_cardinality(axis_values: Iterable[Sequence[Any]]) -> int:
    cardinality = 1
    for values in axis_values:
        cardinality *= len(tuple(values))
    return cardinality


def _indexed(items, attribute, noun):
    indexed = {}
    for item in items:
        identity = getattr(item, attribute)
        if not identity or identity in indexed:
            raise ValueError(f"{noun} id {identity!r} is empty or duplicated")
        indexed[identity] = item
    return indexed


def _case_for_dimension(dimension, mutation):
    # A business-named bad case (outside the built-in vocabulary) must be rejected by default.
    expected = "" if mutation in _MUTATION_DEFAULT_ORACLE else CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT
    return ContractMutationCase(
        _case_id("contract", dimension.dimension_id, mutation), dimension.dimension_id, mutation,
        source_case_id=dimension.dimension_id, required=dimension.required,
        input_delta={"dimension_type": dimension.dimension_type, "mutation_type": mutation,
                     "field_refs": list(dimension.field_refs)},
        family_id=str(dimension.metadata.get("family_id", "")), member_id=str(dimension.metadata.get("member_id", "")),
        description=dimension.description or f"{dimension.dimension_id} must handle {mutation}",
        metadata={"owner_model_id": dimension.owner_model_id, **dict(dimension.metadata)},
        dimension_ids=(dimension.dimension_id,), model_id=dimension.owner_model_id, expected_status=expected,
    )


def _axis_tokens(axis, dimensions):
    for identity in axis.dimension_ids:
        if identity not in dimensions:
            raise ValueError(f"axis {axis.axis_id!r} references unknown dimension {identity!r}")
    if axis.values:
        return tuple({"axis_id": axis.axis_id, "case_id": _case_id(axis.axis_id, value), "value": value,
                      "dimension_ids": axis.dimension_ids, "mutation_type": ""} for value in axis.values)
    if axis.mutation_types:
        return tuple({"axis_id": axis.axis_id, "case_id": _case_id(axis.axis_id, mutation), "value": mutation,
                      "dimension_ids": axis.dimension_ids, "mutation_type": mutation} for mutation in axis.mutation_types)
    return tuple({"axis_id": axis.axis_id, "case_id": _case_id(axis.axis_id, identity, mutation), "value": mutation,
                  "dimension_ids": (identity,), "mutation_type": mutation}
                 for identity in axis.dimension_ids for mutation in dimensions[identity].default_mutations())


def _axes_for_group(plan, group, dimensions, axes):
    owner = group.model_id or plan.model_id
    if group.model_id and plan.model_id and group.model_id != plan.model_id:
        raise ValueError(f"interaction group {group.group_id!r} belongs to foreign model {group.model_id!r}")
    resolved = []
    if group.axis_ids:
        for identity in group.axis_ids:
            if identity not in axes:
                raise ValueError(f"interaction group {group.group_id!r} references unknown axis {identity!r}")
            resolved.append(axes[identity])
    elif group.dimension_ids:
        for identity in group.dimension_ids:
            if identity not in dimensions:
                raise ValueError(f"interaction group {group.group_id!r} references unknown dimension {identity!r}")
            dimension = dimensions[identity]
            resolved.append(ContractAxis(identity, model_id=owner or dimension.owner_model_id,
                                         dimension_ids=(identity,), mutation_types=dimension.default_mutations(),
                                         required=dimension.required, description=dimension.description))
    if not resolved:
        raise ValueError(f"interaction group {group.group_id!r} has no finite axes")
    for axis in resolved:
        if owner and axis.model_id and axis.model_id != owner:
            raise ValueError(f"interaction group {group.group_id!r} has foreign axis {axis.axis_id!r} from {axis.model_id!r}")
    return tuple(resolved)


def _group_cases(plan, group, dimensions, axes):
    if group.generation_kind != CONTRACT_GENERATION_LOCAL_CARTESIAN:
        raise ValueError(f"interaction group {group.group_id!r} has unsupported generation kind {group.generation_kind!r}")
    resolved = _axes_for_group(plan, group, dimensions, axes)
    token_sets = []
    for axis in resolved:
        tokens = _axis_tokens(axis, dimensions)
        if not tokens:
            raise ValueError(f"axis {axis.axis_id!r} has no finite tokens")
        token_sets.append(tokens)
    count = _product_cardinality(token_sets)
    limit = group.max_combinations if group.max_combinations is not None else plan.cartesian_case_limit
    if count > limit or limit < 1:
        raise ValueError(f"interaction group {group.group_id!r} has {count} combinations, exceeding limit {limit}")
    for index, row in enumerate(product(*token_sets), 1):
        dimensions_used = _unique(identity for token in row for identity in token["dimension_ids"])
        axis_cases = tuple(token["case_id"] for token in row)
        owner = group.model_id or plan.model_id
        payload = {"axis_cases": {token["axis_id"]: token["case_id"] for token in row},
                   "axis_values": {token["axis_id"]: to_jsonable(token["value"]) for token in row},
                   "dimension_ids": list(dimensions_used), "interaction_group_id": group.group_id, "model_id": owner}
        yield ContractMutationCase(
            _case_id("cartesian", owner or plan.plan_id, group.group_id, str(index)),
            dimension_id="|".join(dimensions_used), mutation_type=CONTRACT_MUTATION_CARTESIAN_COMBINATION,
            source_case_id=group.group_id, required=group.required, oracle_id=group.oracle_id,
            input_delta=payload, expected_status=group.oracle_status,
            description=group.description or f"{owner or plan.plan_id} must handle Cartesian combination {group.group_id}",
            metadata={"axis_ids": [axis.axis_id for axis in resolved], "axis_case_ids": list(axis_cases),
                      "total_combinations": count, "generated_limit": limit, **dict(group.metadata)},
            dimension_ids=dimensions_used, axis_case_ids=axis_cases, interaction_group_id=group.group_id,
            combination_order=index, model_id=owner, generation_kind=group.generation_kind,
        )


def generate_contract_cases(plan: ContractExhaustionPlan) -> tuple[ContractMutationCase, ...]:
    """Generate every declared finite bad case, or reject an invalid boundary."""
    dimensions = _indexed(plan.dimensions, "dimension_id", "dimension")
    axes = _indexed(plan.axes, "axis_id", "axis")
    _indexed(plan.interaction_groups, "group_id", "interaction group")
    oracles = _indexed(plan.oracles, "oracle_id", "oracle")
    for dimension in plan.dimensions:
        if not dimension.finite:
            raise ValueError(f"dimension {dimension.dimension_id!r} is not finite")
    if not (plan.dimensions or plan.seed_cases or plan.interaction_groups or plan.expected_family_member_ids):
        raise ValueError(f"plan {plan.plan_id!r} has no finite boundary or seed cases")
    cases = list(plan.seed_cases)
    for dimension in plan.dimensions:
        cases.extend(_case_for_dimension(dimension, mutation) for mutation in dimension.default_mutations())
    materialized = set(plan.materialized_family_member_ids)
    for member in plan.expected_family_member_ids:
        if member not in materialized:
            cases.append(ContractMutationCase(
                _case_id("contract", CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER, member),
                mutation_type=CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER, source_case_id=member, member_id=member,
                input_delta={"member_id": member}, metadata={"expected_family_member_id": member}, model_id=plan.model_id,
            ))
    for group in plan.interaction_groups:
        cases.extend(_group_cases(plan, group, dimensions, axes))
    _indexed(cases, "case_id", "case")
    if not cases:
        raise ValueError(f"plan {plan.plan_id!r} generates no finite bad cases")
    resolved = []
    for case in cases:
        if case.oracle_id:
            if case.oracle_id not in oracles:
                raise ValueError(f"case {case.case_id!r} references unknown oracle {case.oracle_id!r}")
            oracle = oracles[case.oracle_id]
            if not oracle.expected_status.strip():
                raise ValueError(f"case {case.case_id!r} has no oracle or expected reaction")
            case = replace(case, expected_status=oracle.expected_status)
        elif not case.expected_status.strip():
            raise ValueError(f"case {case.case_id!r} has no oracle or expected reaction")
        resolved.append(case)
    return tuple(resolved)


def contract_exhaustion_features(plan: ContractExhaustionPlan, mutate):
    """Each generated case is a rejecting feature carrying its stable case id."""
    from .kit import Feature

    return tuple(Feature(case.case_id, True, apply=lambda valid, case_id=case.case_id: mutate(valid, case_id))
                 for case in generate_contract_cases(plan))


def execute_contract_features(features, call, valid, *, rejected=None, rejects=(ValueError, TypeError),
                              max_features: int = 2, codes: str = "all"):
    """Run every admissible bad case and combination on the actual function.

    A returned value is rejected only by ``rejected``. An exception of a ``rejects`` type (default
    ``ValueError``/``TypeError``, or a subclass) is a rejection; any other exception is a crash that
    the kit reports as ``adapter_exception``. ImportError remains an environment/adapter error.
    Mutation errors happen outside this call wrapper and remain adapter errors.
    """
    from .kit import feature_conformance

    rejects = tuple(rejects)

    def review(arguments):
        try:
            result = call(**arguments) if isinstance(arguments, dict) else call(*arguments)
        except ImportError:
            raise
        except rejects:
            return False
        return not (rejected(result) if rejected else False)

    return feature_conformance(features, lambda: dict(valid) if isinstance(valid, Mapping) else tuple(valid), review,
                               max_features=max_features, codes=codes)
