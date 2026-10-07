"""Provider-neutral, bounded model path-quality decisions.

This module is an internal ModelMaturation kernel.  It deliberately exposes no
CLI or route and never mutates a model.  Ordinary reviews inspect normalized
model facts and return a compact result.  Deep comparison is admitted only for
a named finite candidate/rewrite boundary, after hard semantics and necessity
evidence are current.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, fields, replace
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence

PATH_QUALITY_SCHEMA_VERSION = "flowguard.model-path-quality.v2"

PATH_QUALITY_CONCLUSIONS = frozenset(
    {
        "single_clear_path",
        "preferred_within_candidates",
        "non_dominated_within_boundary",
        "minimum_within_exhausted_finite_set",
        "locally_irreducible_under_declared_rewrites",
        "unresolved",
    }
)

PATH_QUALITY_MODES = frozenset({"lightweight", "deep"})
PATH_OPTIMIZATION_DEPTHS = frozenset(
    {"lightweight", "deep_required", "deep_closed"}
)

HARD_SEMANTIC_DIMENSIONS = (
    "accepted_inputs",
    "rejected_inputs",
    "outputs",
    "terminal_states",
    "state_transitions",
    "field_transitions",
    "protected_errors",
    "recovery",
    "side_effects",
    "order",
    "retry",
    "timeout",
    "cancellation",
    "progress",
    "fairness",
    "permissions",
    "authority",
    "parent_interfaces",
    "child_interfaces",
    "intent",
    "behavior_commitments",
    "oracles",
    "evidence_obligations",
)

PATH_COST_DIMENSIONS = (
    "steps",
    "states",
    "transitions",
    "branches",
    "validations",
    "repeated_reads",
    "repeated_writes",
    "repeated_validations",
    "invalidated_outputs",
    "rework",
    "coordination",
    "side_effect_exposure",
    "latency",
    "token_count",
    "payload_bytes",
    "runtime_resources",
    "maintenance_complexity",
)

RETAINED_ELEMENT_KINDS = frozenset(
    {
        "state",
        "transition",
        "branch",
        "function_block",
        "field",
        "effect",
        "validation",
    }
)

NECESSITY_EVIDENCE_KINDS = frozenset(
    {
        "executable_counterexample",
        "executable_oracle",
        "native_model_check",
        "test_receipt",
        "external_observation",
    }
)

REWRITE_DISPOSITIONS = frozenset({"applied", "rejected"})

_EXACT_DEEP_REVIEW_TRIGGERS = frozenset(
    {
        "explicit_request",
        "multiple_hard_equivalent_candidates",
        "path_design_model_miss",
        "missing_necessity_witness",
        "high_cost_boundary",
        "release_critical_boundary",
        "material_states_growth",
        "material_transitions_growth",
        "material_branches_growth",
    }
)

_FACT_ROW_KINDS = (
    ("states", "state"),
    ("transitions", "transition"),
    ("branches", "branch"),
    ("function_blocks", "function_block"),
    ("fields", "field"),
    ("effects", "effect"),
    ("validations", "validation"),
)

_LIGHTWEIGHT_STRUCTURAL_KINDS = frozenset(
    {
        "unreachable_state",
        "unreachable_transition",
        "duplicate_transition",
        "behavior_irrelevant_state",
        "behavior_irrelevant_field",
        "pass_through_function_block",
        "unconsumed_output",
        "repeated_validation",
        "duplicate_current_owner",
        "no_progress_loop",
    }
)

_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_IMPROVEMENT_GAP_FAMILIES = _LIGHTWEIGHT_STRUCTURAL_KINDS | frozenset({
    "equivalent_responsibility_paths", "required_architecture_objective_unmet",
    "deep_review_required", "missing_necessity_witness", "cost_measurement_missing",
})


@dataclass(frozen=True)
class PathQualityGapProjection:
    """Derived diagnostics; never change the persisted v2 result identity."""

    result_fingerprint: str
    observation_gap_ids: tuple[str, ...]
    improvement_gap_ids: tuple[str, ...]

    @classmethod
    def from_result(cls, result: "PathQualityResult") -> "PathQualityGapProjection":
        gaps = set(result.finding_ids) | set(result.unresolved_ids)
        improvement = {gap for gap in gaps if gap.split(":", 1)[0] in _IMPROVEMENT_GAP_FAMILIES}
        return cls(result.fingerprint, tuple(sorted(gaps - improvement)), tuple(sorted(improvement)))


def _validate_json_value(value: Any, label: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} contains a non-finite number")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} contains a non-string object key")
            _validate_json_value(item, f"{label}.{key}")
        return
    raise ValueError(f"{label} is not a JSON value: {type(value).__name__}")


def _canonical_json_chunks(value: Any, *, indent: int | None = None) -> Iterable[str]:
    _validate_json_value(value)
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        indent=indent,
    )
    return encoder.iterencode(value)


def canonical_json(value: Any, *, indent: int | None = None) -> str:
    """Return one deterministic JSON projection for fingerprints and storage."""

    return "".join(_canonical_json_chunks(value, indent=indent))


def canonical_fingerprint(value: Any) -> str:
    digest = hashlib.sha256()
    for chunk in _canonical_json_chunks(value):
        digest.update(chunk.encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_fingerprint(value: Any, label: str, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    value = _require_string(value, label)
    if not _FINGERPRINT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a canonical sha256 fingerprint")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _optional_string(value: Any, label: str) -> str:
    if value in (None, ""):
        return ""
    return _require_string(value, label)


def _validate_optional_bool(row: Mapping[str, Any], name: str, label: str) -> None:
    if name in row:
        _require_bool(row[name], f"{label}.{name}")


def _canonical_ids(values: Iterable[str] | None, label: str) -> tuple[str, ...]:
    normalized = tuple(_require_string(value, label) for value in values or ())
    duplicates = tuple(value for value, count in Counter(normalized).items() if count > 1)
    if duplicates:
        raise ValueError(f"{label} contains duplicate ids: {', '.join(sorted(duplicates))}")
    return tuple(sorted(normalized))


def _canonical_string_pairs(
    value: Mapping[str, str] | Iterable[Sequence[str]] | None,
    label: str,
    *,
    allowed_keys: Iterable[str] | None = None,
) -> tuple[tuple[str, str], ...]:
    if value is None:
        rows: list[tuple[Any, Any]] = []
    elif isinstance(value, Mapping):
        rows = list(value.items())
    else:
        rows = []
        for row in value:
            if isinstance(row, str) or len(row) != 2:
                raise ValueError(f"{label} must contain key/value pairs")
            rows.append((row[0], row[1]))
    normalized = [
        (_require_string(key, f"{label} key"), _require_string(item, f"{label} value"))
        for key, item in rows
    ]
    keys = tuple(key for key, _ in normalized)
    if len(set(keys)) != len(keys):
        raise ValueError(f"{label} contains duplicate keys")
    if allowed_keys is not None:
        unknown = set(keys) - set(allowed_keys)
        if unknown:
            raise ValueError(f"{label} contains unknown keys: {', '.join(sorted(unknown))}")
    return tuple(sorted(normalized))


def _strict_record_mapping(
    value: Any,
    cls: type[Any],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    expected = {field.name for field in fields(cls)} | {"fingerprint"}
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} fields mismatch: missing={missing}, extra={extra}")
    return dict(value)


def _verify_projected_fingerprint(record: Any, projected: Mapping[str, Any], label: str) -> None:
    supplied = _require_fingerprint(projected["fingerprint"], f"{label} fingerprint")
    if record.fingerprint != supplied:
        raise ValueError(f"{label} fingerprint is stale")


class _CanonicalRecord:
    def identity_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    def to_json(self, *, indent: int | None = None) -> str:
        return canonical_json(self.to_dict(), indent=indent)


@dataclass(frozen=True)
class PathQualitySubject(_CanonicalRecord):
    """Exact current identities consumed by one path-quality decision."""

    model_id: str
    boundary_id: str
    model_fingerprint: str
    normalized_facts_fingerprint: str
    retained_element_inventory_fingerprint: str
    purpose_fingerprint: str
    intent_fingerprint: str
    obligation_fingerprint: str
    provider_fingerprint: str
    dependency_fingerprint: str
    code_fingerprint: str
    test_fingerprint: str
    oracle_fingerprint: str
    evidence_fingerprint: str
    currentness_id: str
    schema_version: str = PATH_QUALITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("model_id", "boundary_id", "currentness_id"):
            object.__setattr__(self, name, _require_string(getattr(self, name), name))
        for name in (
            "model_fingerprint",
            "normalized_facts_fingerprint",
            "retained_element_inventory_fingerprint",
            "purpose_fingerprint",
            "intent_fingerprint",
            "obligation_fingerprint",
            "provider_fingerprint",
            "dependency_fingerprint",
            "code_fingerprint",
            "test_fingerprint",
            "oracle_fingerprint",
            "evidence_fingerprint",
        ):
            object.__setattr__(self, name, _require_fingerprint(getattr(self, name), name))
        if self.schema_version != PATH_QUALITY_SCHEMA_VERSION:
            raise ValueError("path-quality subject requires the current schema")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "boundary_id": self.boundary_id,
            "model_fingerprint": self.model_fingerprint,
            "normalized_facts_fingerprint": self.normalized_facts_fingerprint,
            "retained_element_inventory_fingerprint": self.retained_element_inventory_fingerprint,
            "purpose_fingerprint": self.purpose_fingerprint,
            "intent_fingerprint": self.intent_fingerprint,
            "obligation_fingerprint": self.obligation_fingerprint,
            "provider_fingerprint": self.provider_fingerprint,
            "dependency_fingerprint": self.dependency_fingerprint,
            "code_fingerprint": self.code_fingerprint,
            "test_fingerprint": self.test_fingerprint,
            "oracle_fingerprint": self.oracle_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "currentness_id": self.currentness_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PathQualitySubject":
        data = _strict_record_mapping(value, cls, label="path-quality subject")
        record = cls(**{key: data[key] for key in data if key != "fingerprint"})
        _verify_projected_fingerprint(record, data, "path-quality subject")
        return record


@dataclass(frozen=True)
class PathCostVector(_CanonicalRecord):
    """Named current measurements; no scalar total or implicit zero exists."""

    measurement_id: str
    subject_fingerprint: str
    currentness_id: str
    steps: float | None = None
    states: float | None = None
    transitions: float | None = None
    branches: float | None = None
    validations: float | None = None
    repeated_reads: float | None = None
    repeated_writes: float | None = None
    repeated_validations: float | None = None
    invalidated_outputs: float | None = None
    rework: float | None = None
    coordination: float | None = None
    side_effect_exposure: float | None = None
    latency: float | None = None
    token_count: float | None = None
    payload_bytes: float | None = None
    runtime_resources: float | None = None
    maintenance_complexity: float | None = None
    measurement_units: tuple[tuple[str, str], ...] = ()
    measurement_evidence: tuple[tuple[str, str], ...] = ()
    current: bool = True
    schema_version: str = PATH_QUALITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("measurement_id", "currentness_id"):
            object.__setattr__(self, name, _require_string(getattr(self, name), name))
        object.__setattr__(
            self,
            "subject_fingerprint",
            _require_fingerprint(self.subject_fingerprint, "subject_fingerprint"),
        )
        measured: set[str] = set()
        for name in PATH_COST_DIMENSIONS:
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite non-negative number or null")
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"{name} must be a finite non-negative number or null")
            object.__setattr__(self, name, number)
            measured.add(name)
        units = _canonical_string_pairs(
            self.measurement_units,
            "measurement_units",
            allowed_keys=PATH_COST_DIMENSIONS,
        )
        evidence = _canonical_string_pairs(
            self.measurement_evidence,
            "measurement_evidence",
            allowed_keys=PATH_COST_DIMENSIONS,
        )
        for dimension, fingerprint in evidence:
            _require_fingerprint(fingerprint, f"measurement_evidence[{dimension}]")
        if set(dict(units)) != measured:
            raise ValueError("measurement_units must cover exactly the measured dimensions")
        if set(dict(evidence)) != measured:
            raise ValueError("measurement_evidence must cover exactly the measured dimensions")
        object.__setattr__(self, "measurement_units", units)
        object.__setattr__(self, "measurement_evidence", evidence)
        object.__setattr__(self, "current", _require_bool(self.current, "current"))
        if self.schema_version != PATH_QUALITY_SCHEMA_VERSION:
            raise ValueError("path cost vector requires the current schema")

    @property
    def measured_dimensions(self) -> tuple[str, ...]:
        return tuple(name for name in PATH_COST_DIMENSIONS if getattr(self, name) is not None)

    def value(self, dimension: str) -> float | None:
        if dimension not in PATH_COST_DIMENSIONS:
            raise ValueError(f"unknown path-cost dimension: {dimension}")
        return getattr(self, dimension)

    def identity_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "measurement_id": self.measurement_id,
            "subject_fingerprint": self.subject_fingerprint,
            "currentness_id": self.currentness_id,
        }
        payload.update({name: getattr(self, name) for name in PATH_COST_DIMENSIONS})
        payload.update(
            {
                "measurement_units": dict(self.measurement_units),
                "measurement_evidence": dict(self.measurement_evidence),
                "current": self.current,
            }
        )
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "PathCostVector":
        data = _strict_record_mapping(value, cls, label="path cost vector")
        if not isinstance(data["measurement_units"], Mapping):
            raise ValueError("measurement_units must be an object")
        if not isinstance(data["measurement_evidence"], Mapping):
            raise ValueError("measurement_evidence must be an object")
        kwargs = {key: data[key] for key in data if key != "fingerprint"}
        kwargs["measurement_units"] = tuple(data["measurement_units"].items())
        kwargs["measurement_evidence"] = tuple(data["measurement_evidence"].items())
        record = cls(**kwargs)
        _verify_projected_fingerprint(record, data, "path cost vector")
        return record


@dataclass(frozen=True)
class NecessityWitness(_CanonicalRecord):
    """Element-local proof of the obligation lost when the element is removed."""

    witness_id: str
    subject_fingerprint: str
    element_id: str
    element_kind: str
    obligation_id: str
    counterexample_id: str
    oracle_id: str
    evidence_fingerprint: str
    evidence_currentness_id: str
    evidence_kind: str = "executable_counterexample"
    depends_on_witness_ids: tuple[str, ...] = ()
    current: bool = True
    schema_version: str = PATH_QUALITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "witness_id",
            "element_id",
            "element_kind",
            "obligation_id",
            "counterexample_id",
            "oracle_id",
            "evidence_currentness_id",
            "evidence_kind",
        ):
            object.__setattr__(self, name, _require_string(getattr(self, name), name))
        object.__setattr__(
            self,
            "subject_fingerprint",
            _require_fingerprint(self.subject_fingerprint, "subject_fingerprint"),
        )
        object.__setattr__(
            self,
            "evidence_fingerprint",
            _require_fingerprint(self.evidence_fingerprint, "evidence_fingerprint"),
        )
        if self.element_kind not in RETAINED_ELEMENT_KINDS:
            raise ValueError(f"unsupported retained element kind: {self.element_kind}")
        if self.evidence_kind not in NECESSITY_EVIDENCE_KINDS:
            raise ValueError("necessity witness evidence cannot be self-description or path-quality output")
        if self.witness_id in {
            self.element_id,
            self.obligation_id,
            self.counterexample_id,
            self.oracle_id,
        }:
            raise ValueError("necessity witness cannot license itself")
        dependencies = _canonical_ids(
            self.depends_on_witness_ids,
            "depends_on_witness_ids",
        )
        object.__setattr__(self, "depends_on_witness_ids", dependencies)
        object.__setattr__(self, "current", _require_bool(self.current, "current"))
        if self.schema_version != PATH_QUALITY_SCHEMA_VERSION:
            raise ValueError("necessity witness requires the current schema")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "witness_id": self.witness_id,
            "subject_fingerprint": self.subject_fingerprint,
            "element_id": self.element_id,
            "element_kind": self.element_kind,
            "obligation_id": self.obligation_id,
            "counterexample_id": self.counterexample_id,
            "oracle_id": self.oracle_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "evidence_currentness_id": self.evidence_currentness_id,
            "evidence_kind": self.evidence_kind,
            "depends_on_witness_ids": list(self.depends_on_witness_ids),
            "current": self.current,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "NecessityWitness":
        data = _strict_record_mapping(value, cls, label="necessity witness")
        record = cls(**{key: data[key] for key in data if key != "fingerprint"})
        _verify_projected_fingerprint(record, data, "necessity witness")
        return record


@dataclass(frozen=True)
class PathCandidate(_CanonicalRecord):
    """One member of a declared finite hard-semantic comparison set."""

    candidate_id: str
    subject_fingerprint: str
    before_model_fingerprint: str
    after_model_fingerprint: str
    normalized_facts_fingerprint: str
    retained_element_inventory_fingerprint: str
    hard_semantics: tuple[tuple[str, str], ...]
    retained_elements: tuple[tuple[str, str], ...]
    necessity_witnesses: tuple[NecessityWitness, ...] = ()
    rewrite_rule_ids: tuple[str, ...] = ()
    affected_element_ids: tuple[str, ...] = ()
    required_validation_ids: tuple[str, ...] = ()
    evidence_fingerprints: tuple[str, ...] = ()
    cost: PathCostVector | None = None
    lane: str = "observed"
    current: bool = True
    schema_version: str = PATH_QUALITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _require_string(self.candidate_id, "candidate_id"))
        for name in (
            "subject_fingerprint",
            "before_model_fingerprint",
            "after_model_fingerprint",
            "normalized_facts_fingerprint",
            "retained_element_inventory_fingerprint",
        ):
            object.__setattr__(self, name, _require_fingerprint(getattr(self, name), name))
        semantics = _canonical_string_pairs(
            self.hard_semantics,
            "hard_semantics",
            allowed_keys=HARD_SEMANTIC_DIMENSIONS,
        )
        semantic_map = dict(semantics)
        missing = [name for name in HARD_SEMANTIC_DIMENSIONS if name not in semantic_map]
        if missing:
            raise ValueError(f"hard_semantics is incomplete: {', '.join(missing)}")
        for dimension, fingerprint in semantics:
            _require_fingerprint(fingerprint, f"hard_semantics[{dimension}]")
        object.__setattr__(
            self,
            "hard_semantics",
            tuple((name, semantic_map[name]) for name in HARD_SEMANTIC_DIMENSIONS),
        )
        retained = _canonical_string_pairs(
            self.retained_elements,
            "retained_elements",
        )
        for _, kind in retained:
            if kind not in RETAINED_ELEMENT_KINDS:
                raise ValueError(f"unsupported retained element kind: {kind}")
        object.__setattr__(self, "retained_elements", retained)
        if self.retained_element_inventory_fingerprint != canonical_fingerprint(dict(retained)):
            raise ValueError("retained element inventory fingerprint is stale")
        witnesses = tuple(sorted(self.necessity_witnesses, key=lambda row: row.witness_id))
        if any(not isinstance(row, NecessityWitness) for row in witnesses):
            raise ValueError("necessity_witnesses must contain NecessityWitness records")
        if len({row.witness_id for row in witnesses}) != len(witnesses):
            raise ValueError("necessity_witnesses contains duplicate witness ids")
        object.__setattr__(self, "necessity_witnesses", witnesses)
        for name in (
            "rewrite_rule_ids",
            "affected_element_ids",
            "required_validation_ids",
        ):
            object.__setattr__(self, name, _canonical_ids(getattr(self, name), name))
        evidence = _canonical_ids(self.evidence_fingerprints, "evidence_fingerprints")
        for fingerprint in evidence:
            _require_fingerprint(fingerprint, "evidence_fingerprints item")
        object.__setattr__(self, "evidence_fingerprints", evidence)
        if self.cost is not None:
            if not isinstance(self.cost, PathCostVector):
                raise ValueError("cost must be a PathCostVector or null")
            if self.cost.subject_fingerprint != self.after_model_fingerprint:
                raise ValueError("cost subject must equal the candidate after-model fingerprint")
        object.__setattr__(self, "lane", _require_string(self.lane, "lane"))
        if self.lane not in {"observed", "normative_target"}:
            raise ValueError("candidate lane must be observed or normative_target")
        object.__setattr__(self, "current", _require_bool(self.current, "current"))
        if self.schema_version != PATH_QUALITY_SCHEMA_VERSION:
            raise ValueError("path candidate requires the current schema")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "subject_fingerprint": self.subject_fingerprint,
            "before_model_fingerprint": self.before_model_fingerprint,
            "after_model_fingerprint": self.after_model_fingerprint,
            "normalized_facts_fingerprint": self.normalized_facts_fingerprint,
            "retained_element_inventory_fingerprint": self.retained_element_inventory_fingerprint,
            "hard_semantics": dict(self.hard_semantics),
            "retained_elements": dict(self.retained_elements),
            "necessity_witnesses": [row.to_dict() for row in self.necessity_witnesses],
            "rewrite_rule_ids": list(self.rewrite_rule_ids),
            "affected_element_ids": list(self.affected_element_ids),
            "required_validation_ids": list(self.required_validation_ids),
            "evidence_fingerprints": list(self.evidence_fingerprints),
            "cost": self.cost.to_dict() if self.cost is not None else None,
            "lane": self.lane,
            "current": self.current,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PathCandidate":
        data = _strict_record_mapping(value, cls, label="path candidate")
        if not isinstance(data["hard_semantics"], Mapping):
            raise ValueError("hard_semantics must be an object")
        if not isinstance(data["retained_elements"], Mapping):
            raise ValueError("retained_elements must be an object")
        if not isinstance(data["necessity_witnesses"], list):
            raise ValueError("necessity_witnesses must be an array")
        kwargs = {key: data[key] for key in data if key != "fingerprint"}
        kwargs["hard_semantics"] = tuple(data["hard_semantics"].items())
        kwargs["retained_elements"] = tuple(data["retained_elements"].items())
        kwargs["necessity_witnesses"] = tuple(
            NecessityWitness.from_dict(row) for row in data["necessity_witnesses"]
        )
        if data["cost"] is not None and not isinstance(data["cost"], Mapping):
            raise ValueError("cost must be an object or null")
        kwargs["cost"] = (
            PathCostVector.from_dict(data["cost"]) if data["cost"] is not None else None
        )
        record = cls(**kwargs)
        _verify_projected_fingerprint(record, data, "path candidate")
        return record


@dataclass(frozen=True)
class PathQualityResult(_CanonicalRecord):
    """Compact current result.  Candidate and witness bodies never live here."""

    result_id: str
    subject_fingerprint: str
    mode: str
    trigger_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    rewrite_rule_ids: tuple[str, ...]
    conclusion: str
    unresolved_ids: tuple[str, ...]
    selected_candidate_id: str
    selected_candidate_lane: str
    comparison_boundary_id: str
    candidate_set_fingerprint: str
    rewrite_set_fingerprint: str
    necessity_witness_set_fingerprint: str
    detail_evidence_fingerprint: str
    producer_id: str
    currentness_id: str
    candidate_set_exhausted: bool = False
    rewrite_set_exhausted: bool = False
    current: bool = True
    schema_version: str = PATH_QUALITY_SCHEMA_VERSION
    optimization_depth: str = "auto"
    cost_dimensions: tuple[str, ...] = ()
    cost_measurements: tuple[tuple[str, float], ...] = ()
    cost_detail_evidence_fingerprint: str = ""
    trigger_evidence_fingerprint: str = ""

    def __post_init__(self) -> None:
        for name in (
            "result_id",
            "mode",
            "conclusion",
            "producer_id",
            "currentness_id",
        ):
            object.__setattr__(self, name, _require_string(getattr(self, name), name))
        object.__setattr__(
            self,
            "subject_fingerprint",
            _require_fingerprint(self.subject_fingerprint, "subject_fingerprint"),
        )
        for name in ("trigger_ids", "finding_ids", "candidate_ids", "rewrite_rule_ids", "unresolved_ids"):
            object.__setattr__(self, name, _canonical_ids(getattr(self, name), name))
        invalid_triggers = tuple(
            trigger_id for trigger_id in self.trigger_ids if not _is_valid_deep_trigger(trigger_id)
        )
        if invalid_triggers:
            raise ValueError(
                "path-quality result contains unknown trigger ids: "
                + ", ".join(invalid_triggers)
            )
        for name in ("selected_candidate_id", "selected_candidate_lane", "comparison_boundary_id"):
            value = getattr(self, name)
            if value:
                _require_string(value, name)
        if self.selected_candidate_lane and self.selected_candidate_lane not in {
            "observed",
            "normative_target",
        }:
            raise ValueError("selected candidate lane must be observed or normative_target")
        if bool(self.selected_candidate_id) != bool(self.selected_candidate_lane):
            raise ValueError("selected candidate id and lane must be present together")
        for name in (
            "candidate_set_fingerprint",
            "rewrite_set_fingerprint",
        ):
            object.__setattr__(
                self,
                name,
                _require_fingerprint(getattr(self, name), name, optional=True),
            )
        for name in ("necessity_witness_set_fingerprint", "detail_evidence_fingerprint"):
            object.__setattr__(self, name, _require_fingerprint(getattr(self, name), name))
        if self.mode not in PATH_QUALITY_MODES:
            raise ValueError(f"unsupported path-quality mode: {self.mode}")
        depth = self.optimization_depth
        if depth == "auto":
            depth = (
                "deep_closed"
                if self.mode == "deep"
                else "deep_required"
                if self.trigger_ids
                else "lightweight"
            )
        elif self.mode == "deep" and depth == "lightweight":
            # A number of callers derive a deep counterexample from an
            # existing lightweight result with ``dataclasses.replace``.  The
            # mode change is the authoritative signal; carrying the old
            # lightweight depth across that transition would reject the
            # derived result before the actual deep-closure checks can report
            # the useful finding (for example, a normative candidate).
            depth = "deep_required" if self.trigger_ids else "deep_closed"
        if depth not in PATH_OPTIMIZATION_DEPTHS:
            raise ValueError(f"unsupported path-quality optimization depth: {depth}")
        if self.mode == "deep" and depth not in {"deep_required", "deep_closed"}:
            raise ValueError("deep path-quality results require deep_required or deep_closed depth")
        if self.mode == "lightweight" and self.trigger_ids and depth != "deep_required":
            raise ValueError("triggered lightweight results require deep_required depth")
        if self.mode == "lightweight" and not self.trigger_ids and depth != "lightweight":
            raise ValueError("untriggered lightweight results require lightweight depth")
        object.__setattr__(self, "optimization_depth", depth)
        dimensions = _canonical_ids(self.cost_dimensions, "cost_dimensions")
        unknown_dimensions = set(dimensions) - set(PATH_COST_DIMENSIONS)
        if unknown_dimensions:
            raise ValueError(
                "cost_dimensions contains unknown dimensions: "
                + ", ".join(sorted(unknown_dimensions))
            )
        object.__setattr__(self, "cost_dimensions", dimensions)
        measurements = tuple(self.cost_measurements)
        if measurements != tuple(sorted(measurements)):
            raise ValueError("cost_measurements must be canonical")
        if measurements and tuple(dimension for dimension, _value in measurements) != dimensions:
            raise ValueError("cost_measurements must match cost_dimensions")
        for dimension, value in measurements:
            if dimension not in PATH_COST_DIMENSIONS:
                raise ValueError(f"cost_measurements contains unknown dimension: {dimension}")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"cost_measurements.{dimension} must be numeric")
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(
                    f"cost_measurements.{dimension} must be finite and non-negative"
                )
        object.__setattr__(
            self,
            "cost_measurements",
            tuple((str(dimension), float(value)) for dimension, value in measurements),
        )
        object.__setattr__(
            self,
            "cost_detail_evidence_fingerprint",
            _require_fingerprint(
                self.cost_detail_evidence_fingerprint,
                "cost_detail_evidence_fingerprint",
                optional=True,
            ),
        )
        object.__setattr__(
            self,
            "trigger_evidence_fingerprint",
            _require_fingerprint(
                self.trigger_evidence_fingerprint,
                "trigger_evidence_fingerprint",
                optional=True,
            ),
        )
        if self.conclusion not in PATH_QUALITY_CONCLUSIONS:
            raise ValueError("path-quality conclusion must use bounded licensed vocabulary")
        for name in ("candidate_set_exhausted", "rewrite_set_exhausted", "current"):
            object.__setattr__(self, name, _require_bool(getattr(self, name), name))
        if self.schema_version != PATH_QUALITY_SCHEMA_VERSION:
            raise ValueError("path-quality result requires the current schema")
        if self.conclusion == "single_clear_path":
            if self.mode != "lightweight" or any(
                (
                    self.trigger_ids,
                    self.finding_ids,
                    self.candidate_ids,
                    self.rewrite_rule_ids,
                    self.unresolved_ids,
                    self.selected_candidate_id,
                    self.selected_candidate_lane,
                    self.comparison_boundary_id,
                    self.candidate_set_fingerprint,
                    self.rewrite_set_fingerprint,
                    self.candidate_set_exhausted,
                    self.rewrite_set_exhausted,
                )
            ):
                raise ValueError("single_clear_path must remain an ordinary compact result")
        if self.mode == "deep" and not self.trigger_ids:
            raise ValueError("deep path-quality result requires a current trigger")
        if self.mode == "deep" and not self.comparison_boundary_id:
            raise ValueError("deep path-quality result requires a comparison boundary")
        if self.conclusion == "unresolved" and not self.unresolved_ids:
            raise ValueError("unresolved path-quality result requires exact unresolved ids")
        if self.conclusion != "unresolved" and self.unresolved_ids:
            raise ValueError("resolved path-quality conclusion cannot retain unresolved ids")
        if self.candidate_ids and not self.candidate_set_fingerprint:
            raise ValueError("candidate ids require a candidate-set fingerprint")
        if self.rewrite_rule_ids and not self.rewrite_set_fingerprint:
            raise ValueError("rewrite ids require a rewrite-set fingerprint")
        if self.selected_candidate_id and self.selected_candidate_id not in self.candidate_ids:
            raise ValueError("selected candidate must belong to the declared candidate set")
        if self.conclusion in {
            "preferred_within_candidates",
            "minimum_within_exhausted_finite_set",
        } and not self.selected_candidate_id:
            raise ValueError("selected bounded conclusion requires one selected candidate")
        if self.conclusion in {
            "preferred_within_candidates",
            "minimum_within_exhausted_finite_set",
            "non_dominated_within_boundary",
        } and len(self.candidate_ids) < 2:
            raise ValueError("candidate comparison conclusion requires at least two candidates")
        if self.conclusion == "minimum_within_exhausted_finite_set" and not self.candidate_set_exhausted:
            raise ValueError("finite-set minimum requires an exhausted finite candidate set")
        if self.conclusion == "locally_irreducible_under_declared_rewrites" and not (
            self.rewrite_rule_ids and self.rewrite_set_exhausted
        ):
            raise ValueError("local irreducibility requires an exhausted declared rewrite set")
        if self.conclusion == "locally_irreducible_under_declared_rewrites" and len(self.candidate_ids) != 1:
            raise ValueError("local irreducibility requires one current observed candidate")

    @property
    def observation_gap_ids(self) -> tuple[str, ...]:
        return PathQualityGapProjection.from_result(self).observation_gap_ids

    @property
    def improvement_gap_ids(self) -> tuple[str, ...]:
        return PathQualityGapProjection.from_result(self).improvement_gap_ids

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "subject_fingerprint": self.subject_fingerprint,
            "mode": self.mode,
            "trigger_ids": list(self.trigger_ids),
            "finding_ids": list(self.finding_ids),
            "candidate_ids": list(self.candidate_ids),
            "rewrite_rule_ids": list(self.rewrite_rule_ids),
            "conclusion": self.conclusion,
            "unresolved_ids": list(self.unresolved_ids),
            "selected_candidate_id": self.selected_candidate_id,
            "selected_candidate_lane": self.selected_candidate_lane,
            "comparison_boundary_id": self.comparison_boundary_id,
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "rewrite_set_fingerprint": self.rewrite_set_fingerprint,
            "necessity_witness_set_fingerprint": self.necessity_witness_set_fingerprint,
            "detail_evidence_fingerprint": self.detail_evidence_fingerprint,
            "producer_id": self.producer_id,
            "currentness_id": self.currentness_id,
            "candidate_set_exhausted": self.candidate_set_exhausted,
            "rewrite_set_exhausted": self.rewrite_set_exhausted,
            "current": self.current,
            "optimization_depth": self.optimization_depth,
            "cost_dimensions": list(self.cost_dimensions),
            "cost_measurements": {
                dimension: value for dimension, value in self.cost_measurements
            },
            "cost_detail_evidence_fingerprint": self.cost_detail_evidence_fingerprint,
            "trigger_evidence_fingerprint": self.trigger_evidence_fingerprint,
        }

    def to_compact_dict(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_dict(cls, value: Any) -> "PathQualityResult":
        data = _strict_record_mapping(value, cls, label="path-quality result")
        kwargs = {key: data[key] for key in data if key != "fingerprint"}
        # The current v2 canonical projection serializes cost measurements as
        # an object keyed by dimension.  Normalize that projection back to the
        # ordered pair representation used by the dataclass before validation;
        # otherwise iterating the mapping treats each dimension name as a
        # multi-character tuple and raises an opaque unpacking error.
        measurements = kwargs.get("cost_measurements", ())
        if isinstance(measurements, Mapping):
            kwargs["cost_measurements"] = tuple(
                sorted((str(dimension), amount) for dimension, amount in measurements.items())
            )
        record = cls(**kwargs)
        _verify_projected_fingerprint(record, data, "path-quality result")
        return record


@dataclass(frozen=True)
class PathQualityMaterialGap:
    """One exact, consumer-neutral closure gap in compact path-quality material."""

    code: str
    model_id: str = ""
    subject_fingerprint: str = ""
    result_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _require_string(self.code, "code"))
        for name in ("model_id", "subject_fingerprint", "result_fingerprint"):
            value = getattr(self, name)
            if value:
                _require_string(value, name)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "model_id": self.model_id,
            "subject_fingerprint": self.subject_fingerprint,
            "result_fingerprint": self.result_fingerprint,
        }


@dataclass(frozen=True)
class PathQualityMaterialReview:
    """Canonical compact closure over a caller-declared model denominator.

    The review intentionally carries only exact subject/result records and their
    fingerprints.  Deep candidate bodies, rewrite bodies, and witness bodies
    remain with the path-quality producer.
    """

    required_model_ids: tuple[str, ...]
    subjects: tuple[PathQualitySubject, ...]
    results: tuple[PathQualityResult, ...]
    result_set_fingerprint: str
    verified_model_ids: tuple[str, ...] = ()
    gaps: tuple[PathQualityMaterialGap, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.gaps and self.verified_model_ids == self.required_model_ids

    @property
    def blocked_model_ids(self) -> tuple[str, ...]:
        verified = set(self.verified_model_ids)
        required = set(self.required_model_ids)
        globally_blocked = any(
            not gap.model_id or gap.model_id not in required for gap in self.gaps
        )
        gap_models = {gap.model_id for gap in self.gaps if gap.model_id}
        return tuple(
            model_id
            for model_id in self.required_model_ids
            if globally_blocked or model_id in gap_models or model_id not in verified
        )

    def to_compact_dict(self) -> dict[str, Any]:
        return {
            "required_model_ids": list(self.required_model_ids),
            "subject_fingerprints": [item.fingerprint for item in self.subjects],
            "result_fingerprints": [item.fingerprint for item in self.results],
            "result_set_fingerprint": self.result_set_fingerprint,
            "verified_model_ids": list(self.verified_model_ids),
            "blocked_model_ids": list(self.blocked_model_ids),
            "gaps": [item.to_dict() for item in self.gaps],
            "ok": self.ok,
        }


def normalize_path_quality_material(
    required_model_ids: Iterable[str] | None,
    subjects: Iterable[PathQualitySubject | Mapping[str, Any]] | None,
    results: Iterable[PathQualityResult | Mapping[str, Any]] | None,
) -> tuple[
    tuple[str, ...],
    tuple[PathQualitySubject, ...],
    tuple[PathQualityResult, ...],
]:
    """Normalize one exact denominator and its compact typed material."""

    required = _canonical_ids(required_model_ids, "required_model_ids")
    normalized_subjects = tuple(
        sorted(
            (
                item
                if isinstance(item, PathQualitySubject)
                else PathQualitySubject.from_dict(item)
                for item in subjects or ()
            ),
            key=lambda item: item.model_id,
        )
    )
    subject_ids = tuple(item.model_id for item in normalized_subjects)
    if len(subject_ids) != len(set(subject_ids)):
        raise ValueError("path-quality subjects must have unique model ids")
    normalized_results = tuple(
        sorted(
            (
                item
                if isinstance(item, PathQualityResult)
                else PathQualityResult.from_dict(item)
                for item in results or ()
            ),
            key=lambda item: item.subject_fingerprint,
        )
    )
    result_subjects = tuple(item.subject_fingerprint for item in normalized_results)
    if len(result_subjects) != len(set(result_subjects)):
        raise ValueError("path-quality results must have unique subject fingerprints")
    return required, normalized_subjects, normalized_results


def path_quality_result_set_fingerprint(
    required_model_ids: Iterable[str],
    subjects: Iterable[PathQualitySubject],
    results: Iterable[PathQualityResult],
) -> str:
    """Fingerprint only the denominator and compact subject/result identities."""

    required, normalized_subjects, normalized_results = normalize_path_quality_material(
        required_model_ids,
        subjects,
        results,
    )
    return canonical_fingerprint(
        {
            "required_model_ids": list(required),
            "subjects": [item.fingerprint for item in normalized_subjects],
            "results": [item.fingerprint for item in normalized_results],
        }
    )


def review_path_quality_material(
    required_model_ids: Iterable[str] | None,
    subjects: Iterable[PathQualitySubject | Mapping[str, Any]] | None,
    results: Iterable[PathQualityResult | Mapping[str, Any]] | None,
    *,
    expected_currentness_id: str = "",
    expected_model_fingerprints: Mapping[str, str] | None = None,
    require_exact_currentness: bool = False,
    require_exact_model_fingerprints: bool = False,
) -> PathQualityMaterialReview:
    """Validate exact-current compact material without re-evaluating path quality."""

    required, normalized_subjects, normalized_results = normalize_path_quality_material(
        required_model_ids,
        subjects,
        results,
    )
    expected_currentness_id = str(expected_currentness_id)
    expected_models = {
        str(model_id): str(fingerprint)
        for model_id, fingerprint in dict(expected_model_fingerprints or {}).items()
    }
    for model_id, fingerprint in expected_models.items():
        _require_string(model_id, "expected model id")
        _require_fingerprint(fingerprint, f"expected_model_fingerprints[{model_id}]")

    subjects_by_model = {item.model_id: item for item in normalized_subjects}
    results_by_subject = {item.subject_fingerprint: item for item in normalized_results}
    required_set = set(required)
    gaps: list[PathQualityMaterialGap] = []

    if required and require_exact_currentness and not expected_currentness_id:
        gaps.append(PathQualityMaterialGap("path_quality_expected_currentness_missing"))
    if required and require_exact_model_fingerprints:
        for model_id in sorted(required_set - set(expected_models)):
            gaps.append(
                PathQualityMaterialGap(
                    "path_quality_expected_model_fingerprint_missing",
                    model_id=model_id,
                )
            )
    for model_id in sorted(set(expected_models) - required_set):
        gaps.append(
            PathQualityMaterialGap(
                "path_quality_expected_model_fingerprint_extra",
                model_id=model_id,
            )
        )
    for model_id in sorted(required_set - set(subjects_by_model)):
        gaps.append(PathQualityMaterialGap("path_quality_subject_missing", model_id=model_id))
    for model_id in sorted(set(subjects_by_model) - required_set):
        subject = subjects_by_model[model_id]
        gaps.append(
            PathQualityMaterialGap(
                "path_quality_subject_extra",
                model_id=model_id,
                subject_fingerprint=subject.fingerprint,
            )
        )

    required_subject_fingerprints = {
        subjects_by_model[model_id].fingerprint
        for model_id in required
        if model_id in subjects_by_model
    }
    for subject_fingerprint in sorted(required_subject_fingerprints - set(results_by_subject)):
        subject = next(
            item for item in normalized_subjects if item.fingerprint == subject_fingerprint
        )
        gaps.append(
            PathQualityMaterialGap(
                "path_quality_result_missing",
                model_id=subject.model_id,
                subject_fingerprint=subject_fingerprint,
            )
        )
    for subject_fingerprint in sorted(set(results_by_subject) - required_subject_fingerprints):
        result = results_by_subject[subject_fingerprint]
        subject = next(
            (item for item in normalized_subjects if item.fingerprint == subject_fingerprint),
            None,
        )
        gaps.append(
            PathQualityMaterialGap(
                "path_quality_result_extra",
                model_id=subject.model_id if subject is not None else "",
                subject_fingerprint=subject_fingerprint,
                result_fingerprint=result.fingerprint,
            )
        )

    verified: list[str] = []
    for model_id in required:
        subject = subjects_by_model.get(model_id)
        if subject is None:
            continue
        model_gaps: list[PathQualityMaterialGap] = []
        expected_model_fingerprint = expected_models.get(model_id, "")
        if expected_model_fingerprint and subject.model_fingerprint != expected_model_fingerprint:
            model_gaps.append(
                PathQualityMaterialGap(
                    "path_quality_subject_model_fingerprint_mismatch",
                    model_id=model_id,
                    subject_fingerprint=subject.fingerprint,
                )
            )
        if expected_currentness_id and subject.currentness_id != expected_currentness_id:
            model_gaps.append(
                PathQualityMaterialGap(
                    "path_quality_subject_currentness_mismatch",
                    model_id=model_id,
                    subject_fingerprint=subject.fingerprint,
                )
            )
        result = results_by_subject.get(subject.fingerprint)
        if result is None:
            gaps.extend(model_gaps)
            continue
        if not result.current:
            model_gaps.append(
                PathQualityMaterialGap(
                    "path_quality_result_stale",
                    model_id=model_id,
                    subject_fingerprint=subject.fingerprint,
                    result_fingerprint=result.fingerprint,
                )
            )
        if result.currentness_id != subject.currentness_id or (
            expected_currentness_id and result.currentness_id != expected_currentness_id
        ):
            model_gaps.append(
                PathQualityMaterialGap(
                    "path_quality_result_currentness_mismatch",
                    model_id=model_id,
                    subject_fingerprint=subject.fingerprint,
                    result_fingerprint=result.fingerprint,
                )
            )
        if result.conclusion == "unresolved" or result.unresolved_ids:
            model_gaps.append(
                PathQualityMaterialGap(
                    "path_quality_result_unresolved",
                    model_id=model_id,
                    subject_fingerprint=subject.fingerprint,
                    result_fingerprint=result.fingerprint,
                )
            )
        if result.selected_candidate_lane == "normative_target":
            model_gaps.append(
                PathQualityMaterialGap(
                    "path_quality_normative_target_not_observed",
                    model_id=model_id,
                    subject_fingerprint=subject.fingerprint,
                    result_fingerprint=result.fingerprint,
                )
            )
        gaps.extend(model_gaps)
        if not model_gaps:
            verified.append(model_id)

    result_set_fingerprint = path_quality_result_set_fingerprint(
        required,
        normalized_subjects,
        normalized_results,
    )
    return PathQualityMaterialReview(
        required_model_ids=required,
        subjects=normalized_subjects,
        results=normalized_results,
        result_set_fingerprint=result_set_fingerprint,
        verified_model_ids=tuple(verified),
        gaps=tuple(gaps),
    )


def _facts_rows(model_facts: Mapping[str, Any], name: str) -> tuple[Mapping[str, Any], ...]:
    raw = model_facts.get(name, ())
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError(f"model_facts.{name} must be an array")
    rows: list[Mapping[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            rows.append({"id": item})
        elif isinstance(item, Mapping):
            rows.append(item)
        else:
            raise ValueError(f"model_facts.{name} rows must be strings or objects")
    return tuple(rows)


def _row_id(row: Mapping[str, Any], label: str) -> str:
    return _require_string(row.get("id"), f"{label}.id")


def _row_ids(row: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = row.get(name, ())
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a string or array of strings")
    return tuple(_require_string(item, name) for item in value)


def _normalized_model_facts(model_facts: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(model_facts, Mapping):
        raise ValueError("model_facts must be an object")
    projection = dict(model_facts)
    for name, kind in (*_FACT_ROW_KINDS, ("outputs", "output"), ("owners", "owner")):
        if name not in projection:
            continue
        rows = _facts_rows(model_facts, name)
        rows_by_id: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            row_id = _row_id(row, kind)
            if row_id in rows_by_id:
                raise ValueError(f"model_facts.{name} contains duplicate ids")
            rows_by_id[row_id] = row
        projection[name] = [dict(rows_by_id[row_id]) for row_id in sorted(rows_by_id)]
    for name in ("initial_state_ids", "terminal_state_ids"):
        if name in projection:
            projection[name] = list(_canonical_ids(_row_ids(model_facts, name), name))
    _validate_json_value(projection, "model_facts")
    return projection


def normalized_model_facts_fingerprint(model_facts: Mapping[str, Any]) -> str:
    """Fingerprint normalized facts without making provider row order authoritative."""

    normalized = _normalized_model_facts(model_facts)
    architecture = normalized.get("architecture")
    if isinstance(architecture, Mapping):
        normalized["architecture"] = {key: value for key, value in architecture.items() if key not in {"improvement_pointers", "scope_evidence"}}
    return canonical_fingerprint(normalized)


def derive_retained_elements(model_facts: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Derive the exact witness denominator from provider-neutral model facts."""

    retained: dict[str, str] = {}

    def add(element_id: str, kind: str) -> None:
        previous = retained.get(element_id)
        if previous is not None and previous != kind:
            raise ValueError(
                f"retained element id {element_id} is reused as both {previous} and {kind}"
            )
        retained[element_id] = kind

    rows_by_name: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for name, kind in _FACT_ROW_KINDS:
        rows = _facts_rows(model_facts, name)
        rows_by_name[name] = rows
        seen: set[str] = set()
        for row in rows:
            element_id = _row_id(row, kind)
            if element_id in seen:
                raise ValueError(f"model_facts.{name} contains duplicate ids")
            seen.add(element_id)
            add(element_id, kind)
    for row in (*rows_by_name.get("transitions", ()), *rows_by_name.get("function_blocks", ())):
        for element_id in (*_row_ids(row, "reads"), *_row_ids(row, "writes"), *_row_ids(row, "state_updates")):
            add(element_id, "field")
        for element_id in _row_ids(row, "effects"):
            add(element_id, "effect")
        for element_id in _row_ids(row, "validations"):
            add(element_id, "validation")
    return tuple(sorted(retained.items()))


def _semantic_transition_signature(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _require_string(row.get("source"), "transition.source"),
        _require_string(row.get("target"), "transition.target"),
        _optional_string(row.get("trigger"), "transition.trigger"),
        _optional_string(row.get("guard"), "transition.guard"),
        tuple(sorted(_row_ids(row, "outputs"))),
        tuple(sorted(_row_ids(row, "state_updates"))),
        tuple(sorted(_row_ids(row, "effects"))),
        tuple(sorted(_row_ids(row, "errors"))),
    )


def _strongly_connected_components(
    nodes: Sequence[str],
    outgoing: Mapping[str, Sequence[str]],
) -> tuple[tuple[str, ...], ...]:
    """Iterative Kosaraju traversal with O(V + E) indexed work."""

    reverse: dict[str, list[str]] = {node: [] for node in nodes}
    for source in nodes:
        for target in outgoing.get(source, ()):
            if target in reverse:
                reverse[target].append(source)
    visited: set[str] = set()
    order: list[str] = []
    for root in nodes:
        if root in visited:
            continue
        stack: list[tuple[str, bool]] = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            for target in reversed(tuple(outgoing.get(node, ()))):
                if target not in visited:
                    stack.append((target, False))
    components: list[tuple[str, ...]] = []
    assigned: set[str] = set()
    for root in reversed(order):
        if root in assigned:
            continue
        component: list[str] = []
        stack = [root]
        assigned.add(root)
        while stack:
            node = stack.pop()
            component.append(node)
            for target in reverse.get(node, ()):
                if target not in assigned:
                    assigned.add(target)
                    stack.append(target)
        components.append(tuple(sorted(component)))
    return tuple(sorted(components))


def find_lightweight_findings(model_facts: Mapping[str, Any]) -> tuple[str, ...]:
    """Inspect normalized provider facts without synthesizing alternate paths.

    The accepted facts are language-neutral arrays named ``states``,
    ``transitions``, ``fields``, ``function_blocks``, ``outputs``,
    ``validations``, and ``owners``.  Rows use stable ``id`` values and optional
    semantic lists/flags; no source-language field is required.
    """

    if not isinstance(model_facts, Mapping):
        raise ValueError("model_facts must be an object")
    findings: set[str] = set()
    retained_inventory = derive_retained_elements(model_facts)
    if not retained_inventory:
        findings.add("provider_fact_missing:model_elements")
    states = _facts_rows(model_facts, "states")
    transitions = _facts_rows(model_facts, "transitions")
    fields_rows = _facts_rows(model_facts, "fields")
    blocks = _facts_rows(model_facts, "function_blocks")
    outputs = _facts_rows(model_facts, "outputs")
    validations = _facts_rows(model_facts, "validations")
    owners = _facts_rows(model_facts, "owners")

    state_by_id = {_row_id(row, "state"): row for row in states}
    if len(state_by_id) != len(states):
        raise ValueError("model_facts.states contains duplicate ids")
    for state_id, row in state_by_id.items():
        for name in ("initial", "terminal", "behaviorally_relevant"):
            _validate_optional_bool(row, name, f"state[{state_id}]")
    transition_by_id = {_row_id(row, "transition"): row for row in transitions}
    if len(transition_by_id) != len(transitions):
        raise ValueError("model_facts.transitions contains duplicate ids")
    initial = set(_row_ids(model_facts, "initial_state_ids"))
    initial.update(state_id for state_id, row in state_by_id.items() if row.get("initial") is True)
    terminal = set(_row_ids(model_facts, "terminal_state_ids"))
    terminal.update(state_id for state_id, row in state_by_id.items() if row.get("terminal") is True)
    if state_by_id and not initial:
        findings.add("provider_fact_missing:initial_state")
    unknown_initial = initial - set(state_by_id)
    for state_id in unknown_initial:
        findings.add(f"provider_fact_invalid:initial_state:{state_id}")
    for state_id in sorted(terminal - set(state_by_id)):
        findings.add(f"provider_fact_invalid:terminal_state:{state_id}")

    outgoing: dict[str, list[str]] = {state_id: [] for state_id in state_by_id}
    for transition_id, row in transition_by_id.items():
        for name in ("bounded_retry", "external_wait"):
            _validate_optional_bool(row, name, f"transition[{transition_id}]")
        source = _require_string(row.get("source"), f"transition[{transition_id}].source")
        target = _require_string(row.get("target"), f"transition[{transition_id}].target")
        if source not in state_by_id or target not in state_by_id:
            findings.add(f"unreachable_transition:{transition_id}")
            continue
        outgoing[source].append(target)

    reachable: set[str] = set()
    queue: deque[str] = deque(sorted(initial & set(state_by_id)))
    while queue:
        state_id = queue.popleft()
        if state_id in reachable:
            continue
        reachable.add(state_id)
        queue.extend(target for target in outgoing[state_id] if target not in reachable)
    for state_id in sorted(set(state_by_id) - reachable):
        findings.add(f"unreachable_state:{state_id}")
    for transition_id, row in transition_by_id.items():
        if row.get("source") not in reachable:
            findings.add(f"unreachable_transition:{transition_id}")

    transition_signatures: dict[tuple[Any, ...], str] = {}
    for transition_id in sorted(transition_by_id):
        signature = _semantic_transition_signature(transition_by_id[transition_id])
        if signature in transition_signatures:
            findings.add(
                f"duplicate_transition:{transition_signatures[signature]}:{transition_id}"
            )
        else:
            transition_signatures[signature] = transition_id

    for state_id, row in state_by_id.items():
        if row.get("behaviorally_relevant") is False:
            findings.add(f"behavior_irrelevant_state:{state_id}")

    derived_reads: Counter[str] = Counter()
    derived_writes: Counter[str] = Counter()
    for row in (*transitions, *blocks):
        derived_reads.update(_row_ids(row, "reads"))
        derived_writes.update(_row_ids(row, "writes"))
    field_ids: set[str] = set()
    for row in fields_rows:
        field_id = _row_id(row, "field")
        if field_id in field_ids:
            raise ValueError("model_facts.fields contains duplicate ids")
        field_ids.add(field_id)
        for name in ("observable", "behaviorally_relevant", "declared"):
            _validate_optional_bool(row, name, f"field[{field_id}]")
        reads = _row_ids(row, "reads_by")
        writes = _row_ids(row, "writes_by")
        observable = row.get("observable") is True
        relevant = row.get("behaviorally_relevant")
        if relevant is False or (
            relevant is not True
            and not observable
            and not reads
            and derived_reads[field_id] == 0
            and (writes or derived_writes[field_id] > 0 or row.get("declared") is True)
        ):
            findings.add(f"behavior_irrelevant_field:{field_id}")

    block_ids: set[str] = set()
    for row in blocks:
        block_id = _row_id(row, "function_block")
        if block_id in block_ids:
            raise ValueError("model_facts.function_blocks contains duplicate ids")
        block_ids.add(block_id)
        _validate_optional_bool(row, "pass_through", f"function_block[{block_id}]")
        inputs = _row_ids(row, "inputs")
        block_outputs = _row_ids(row, "outputs")
        unchanged_value = inputs == block_outputs and bool(inputs)
        unchanged_state = row.get("state_input", "") == row.get("state_output", "")
        protected_work = any(
            _row_ids(row, name)
            for name in ("reads", "writes", "effects", "state_updates", "errors", "validations")
        )
        if row.get("pass_through") is True or (
            unchanged_value and unchanged_state and not protected_work and not row.get("guard")
        ):
            findings.add(f"pass_through_function_block:{block_id}")

    declared_consumers: Counter[str] = Counter()
    declared_producers: Counter[str] = Counter()
    for row in blocks:
        declared_consumers.update(_row_ids(row, "inputs"))
        declared_producers.update(_row_ids(row, "outputs"))
    for row in transitions:
        declared_producers.update(_row_ids(row, "outputs"))
    output_ids: set[str] = set()
    for row in outputs:
        output_id = _row_id(row, "output")
        if output_id in output_ids:
            raise ValueError("model_facts.outputs contains duplicate ids")
        output_ids.add(output_id)
        _validate_optional_bool(row, "terminal", f"output[{output_id}]")
        consumers = _row_ids(row, "consumer_ids")
        if (
            row.get("terminal") is True
            and not row.get("producer_id")
            and declared_producers[output_id] == 0
        ):
            findings.add(f"provider_fact_missing:output_producer:{output_id}")
        if not consumers and declared_consumers[output_id] == 0 and row.get("terminal") is not True:
            findings.add(f"unconsumed_output:{output_id}")

    validation_signatures: dict[tuple[str, str, str, str], str] = {}
    validation_ids: set[str] = set()
    for row in validations:
        validation_id = _row_id(row, "validation")
        if validation_id in validation_ids:
            raise ValueError("model_facts.validations contains duplicate ids")
        validation_ids.add(validation_id)
        signature = tuple(
            _require_string(row.get(name), f"validation[{validation_id}].{name}")
            for name in ("obligation_id", "oracle_id", "subject_fingerprint", "evidence_boundary_id")
        )
        if signature in validation_signatures:
            findings.add(
                f"repeated_validation:{validation_signatures[signature]}:{validation_id}"
            )
        else:
            validation_signatures[signature] = validation_id

    owner_signatures: dict[tuple[str, str], str] = {}
    owner_ids: set[str] = set()
    for row in owners:
        owner_id = _row_id(row, "owner")
        if owner_id in owner_ids:
            raise ValueError("model_facts.owners contains duplicate ids")
        owner_ids.add(owner_id)
        current_value = row.get("current", True)
        _require_bool(current_value, f"owner[{owner_id}].current")
        if not current_value:
            continue
        signature = (
            _require_string(row.get("intent_id"), f"owner[{owner_id}].intent_id"),
            _require_string(row.get("boundary_id"), f"owner[{owner_id}].boundary_id"),
        )
        if signature in owner_signatures:
            findings.add(f"duplicate_current_owner:{owner_signatures[signature]}:{owner_id}")
        else:
            owner_signatures[signature] = owner_id

    reachable_nodes = tuple(sorted(reachable))
    reachable_outgoing = {
        state_id: tuple(target for target in outgoing[state_id] if target in reachable)
        for state_id in reachable_nodes
    }
    for component in _strongly_connected_components(reachable_nodes, reachable_outgoing):
        cyclic = len(component) > 1 or any(
            state_id in reachable_outgoing.get(state_id, ()) for state_id in component
        )
        if not cyclic:
            continue
        component_set = set(component)
        component_transitions = [
            row
            for row in transitions
            if row.get("source") in component_set and row.get("target") in component_set
        ]
        protected_progress = bool(component_set & terminal) or any(
            row.get("progress_measure")
            or row.get("bounded_retry") is True
            or row.get("external_wait") is True
            for row in component_transitions
        )
        if not protected_progress:
            findings.add("no_progress_loop:" + ",".join(component))

    architecture = model_facts.get("architecture", {})
    if architecture:
        if not isinstance(architecture, Mapping):
            raise ValueError("model_facts.architecture must be typed object")
        findings.update(_canonical_ids(architecture.get("finding_ids", ()), "architecture finding_ids"))
        findings.update(_canonical_ids(architecture.get("improvement_gap_ids", ()), "architecture improvement_gap_ids"))
    return tuple(sorted(findings))


def _canonical_retained_elements(
    retained_elements: Mapping[str, str] | Iterable[Sequence[str]] | None,
) -> tuple[tuple[str, str], ...]:
    rows = _canonical_string_pairs(retained_elements, "retained_elements")
    for _, kind in rows:
        if kind not in RETAINED_ELEMENT_KINDS:
            raise ValueError(f"unsupported retained element kind: {kind}")
    return rows


def validate_necessity_witnesses(
    subject: PathQualitySubject,
    retained_elements: Mapping[str, str] | Iterable[Sequence[str]] | None,
    witnesses: Sequence[NecessityWitness],
    *,
    expected_currentness_id: str = "",
    active_obligation_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Return exact witness gaps; an empty tuple is the acceptance proof."""

    if not isinstance(subject, PathQualitySubject):
        raise ValueError("subject must be a PathQualitySubject")
    subject_fingerprint = subject.fingerprint
    retained = dict(_canonical_retained_elements(retained_elements))
    witness_rows = tuple(witnesses)
    if any(not isinstance(row, NecessityWitness) for row in witness_rows):
        raise ValueError("witnesses must contain NecessityWitness records")
    expected_currentness_id = expected_currentness_id or subject.currentness_id
    if expected_currentness_id:
        _require_string(expected_currentness_id, "expected_currentness_id")
    gaps: set[str] = set()
    if active_obligation_ids is None:
        if retained:
            gaps.add("active_obligation_inventory_missing")
        active: set[str] = set()
    else:
        active_rows = _canonical_ids(active_obligation_ids, "active_obligation_ids")
        active = set(active_rows)
        if canonical_fingerprint(list(active_rows)) != subject.obligation_fingerprint:
            gaps.add("active_obligation_inventory_mismatch")
    by_id: dict[str, NecessityWitness] = {}
    by_element: dict[str, list[NecessityWitness]] = {}
    for witness in witness_rows:
        if witness.witness_id in by_id:
            gaps.add(f"duplicate_witness_id:{witness.witness_id}")
        by_id[witness.witness_id] = witness
        by_element.setdefault(witness.element_id, []).append(witness)
        if witness.element_id not in retained:
            gaps.add(f"unexpected_witness_element:{witness.element_id}")
        elif retained[witness.element_id] != witness.element_kind:
            gaps.add(f"witness_element_kind_mismatch:{witness.element_id}")
        if witness.subject_fingerprint != subject_fingerprint:
            gaps.add(f"stale_witness_subject:{witness.witness_id}")
        if not witness.current:
            gaps.add(f"stale_witness:{witness.witness_id}")
        if expected_currentness_id and witness.evidence_currentness_id != expected_currentness_id:
            gaps.add(f"stale_witness_evidence:{witness.witness_id}")
        if active_obligation_ids is not None and witness.obligation_id not in active:
            gaps.add(f"inactive_witness_obligation:{witness.witness_id}")
    for element_id in retained:
        rows = by_element.get(element_id, ())
        if not rows:
            gaps.add(f"missing_necessity_witness:{element_id}")
        elif len(rows) > 1:
            gaps.add(f"duplicate_necessity_witness:{element_id}")

    dependency_graph: dict[str, tuple[str, ...]] = {}
    for witness in witness_rows:
        dependency_graph[witness.witness_id] = witness.depends_on_witness_ids
        for dependency in witness.depends_on_witness_ids:
            if dependency not in by_id:
                gaps.add(f"missing_witness_dependency:{witness.witness_id}:{dependency}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(witness_id: str, path: tuple[str, ...]) -> None:
        if witness_id in visiting:
            cycle = path[path.index(witness_id) :] if witness_id in path else (witness_id,)
            gaps.add("circular_witness:" + ",".join(sorted(set(cycle))))
            return
        if witness_id in visited:
            return
        visiting.add(witness_id)
        for dependency in dependency_graph.get(witness_id, ()):
            if dependency in dependency_graph:
                visit(dependency, (*path, dependency))
        visiting.remove(witness_id)
        visited.add(witness_id)

    for witness_id in sorted(dependency_graph):
        visit(witness_id, (witness_id,))
    return tuple(sorted(gaps))


def collect_deep_review_triggers(
    finding_ids: Iterable[str] = (),
    *,
    explicit_request: bool = False,
    declared_candidate_count: int = 0,
    prior_counts: Mapping[str, int] | None = None,
    current_counts: Mapping[str, int] | None = None,
    growth_thresholds: Mapping[str, int] | None = None,
    path_design_model_miss: bool = False,
    missing_necessity_witness: bool = False,
    high_cost_boundary: bool = False,
    release_critical_boundary: bool = False,
    measured_costs: Mapping[str, float] | None = None,
    cost_thresholds: Mapping[str, float] | None = None,
) -> tuple[str, ...]:
    """Return exact affected-model triggers; it never creates candidates."""

    triggers: set[str] = set()
    if explicit_request:
        triggers.add("explicit_request")
    if (
        isinstance(declared_candidate_count, bool)
        or not isinstance(declared_candidate_count, int)
        or declared_candidate_count < 0
    ):
        raise ValueError("declared_candidate_count must be a non-negative integer")
    if declared_candidate_count > 1:
        triggers.add("multiple_hard_equivalent_candidates")
    for finding in finding_ids:
        finding = _require_string(finding, "finding_id")
        kind = finding.split(":", 1)[0]
        if kind in _LIGHTWEIGHT_STRUCTURAL_KINDS:
            triggers.add(f"structural:{kind}")
    prior = dict(prior_counts or {})
    current = dict(current_counts or {})
    thresholds = dict(growth_thresholds or {})
    for dimension in ("states", "transitions", "branches"):
        if dimension not in thresholds:
            continue
        values = (prior.get(dimension, 0), current.get(dimension, 0), thresholds[dimension])
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise ValueError(f"{dimension} growth values must be non-negative integers")
        if values[1] - values[0] > values[2]:
            triggers.add(f"material_{dimension}_growth")
    measured = dict(measured_costs or {})
    cost_limits = dict(cost_thresholds or {})
    for dimension, value in measured.items():
        if dimension not in PATH_COST_DIMENSIONS:
            raise ValueError(f"measured_costs contains unknown dimension: {dimension}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"measured_costs.{dimension} must be numeric")
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"measured_costs.{dimension} must be finite and non-negative")
    for dimension, threshold in cost_limits.items():
        if dimension not in PATH_COST_DIMENSIONS:
            raise ValueError(f"cost_thresholds contains unknown dimension: {dimension}")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ValueError(f"cost_thresholds.{dimension} must be numeric")
        if not math.isfinite(float(threshold)) or float(threshold) < 0:
            raise ValueError(f"cost_thresholds.{dimension} must be finite and non-negative")
        if dimension in measured and float(measured[dimension]) >= float(threshold):
            triggers.add("high_cost_boundary")
    if path_design_model_miss:
        triggers.add("path_design_model_miss")
    if missing_necessity_witness:
        triggers.add("missing_necessity_witness")
    if high_cost_boundary:
        triggers.add("high_cost_boundary")
    if release_critical_boundary:
        triggers.add("release_critical_boundary")
    return tuple(sorted(triggers))


def _is_valid_deep_trigger(trigger_id: str) -> bool:
    if trigger_id in _EXACT_DEEP_REVIEW_TRIGGERS:
        return True
    if not trigger_id.startswith("structural:"):
        return False
    return trigger_id.removeprefix("structural:") in _LIGHTWEIGHT_STRUCTURAL_KINDS


def _witness_set_fingerprint(witnesses: Iterable[NecessityWitness]) -> str:
    return canonical_fingerprint(
        [row.fingerprint for row in sorted(witnesses, key=lambda item: item.witness_id)]
    )


def lightweight_path_review(
    subject: PathQualitySubject,
    model_facts: Mapping[str, Any],
    *,
    retained_elements: Mapping[str, str] | Iterable[Sequence[str]] | None = None,
    necessity_witnesses: Sequence[NecessityWitness] = (),
    active_obligation_ids: Iterable[str] | None = None,
    explicit_deep_request: bool = False,
    declared_candidate_count: int = 0,
    prior_counts: Mapping[str, int] | None = None,
    current_counts: Mapping[str, int] | None = None,
    growth_thresholds: Mapping[str, int] | None = None,
    path_design_model_miss: bool = False,
    high_cost_boundary: bool = False,
    release_critical_boundary: bool = False,
    measured_costs: Mapping[str, float] | None = None,
    cost_thresholds: Mapping[str, float] | None = None,
    cost_evidence: Mapping[str, str] | Iterable[Sequence[str]] | None = None,
    trigger_evidence: Mapping[str, str] | Iterable[Sequence[str]] | None = None,
    trigger_currentness_id: str = "",
    producer_id: str = "model_maturation",
    detail_collector: list[PathQualityArchitectureDetail] | None = None,
) -> PathQualityResult:
    """Run the ordinary deterministic review and return only a compact result."""

    if not isinstance(subject, PathQualitySubject):
        raise ValueError("subject must be a PathQualitySubject")
    currentness_id = subject.currentness_id
    normalized_facts = _normalized_model_facts(model_facts)
    findings = find_lightweight_findings(normalized_facts)
    derived_retained = derive_retained_elements(normalized_facts)
    retained = (
        derived_retained
        if retained_elements is None
        else _canonical_retained_elements(retained_elements)
    )
    intake_gaps: set[str] = set()
    architecture = normalized_facts.get("architecture", {})
    intake_gaps.update(_canonical_ids(architecture.get("observation_gap_ids", ()), "architecture observation_gap_ids"))
    if normalized_model_facts_fingerprint(normalized_facts) != subject.normalized_facts_fingerprint:
        intake_gaps.add("stale_normalized_model_facts")
    if canonical_fingerprint(dict(derived_retained)) != subject.retained_element_inventory_fingerprint:
        intake_gaps.add("stale_retained_element_inventory")
    if retained != derived_retained:
        intake_gaps.add("retained_element_inventory_mismatch")
    # Ordinary path review proves native structural coverage and source
    # currentness.  A per-element necessity witness is an explicit candidate
    # comparison concern; accepting one here would manufacture a second proof
    # obligation for every state/field and inflate normal changes.
    witness_gaps = (
        validate_necessity_witnesses(
            subject,
            retained,
            necessity_witnesses,
            expected_currentness_id=currentness_id,
            active_obligation_ids=active_obligation_ids,
        )
        if explicit_deep_request
        else ()
    )
    measured = {
        str(dimension): float(value)
        for dimension, value in dict(measured_costs or {}).items()
    }
    cost_thresholds_value = {
        str(dimension): float(value)
        for dimension, value in dict(cost_thresholds or {}).items()
    }
    cost_evidence_rows = dict(_canonical_string_pairs(cost_evidence, "cost_evidence"))
    for dimension, fingerprint in cost_evidence_rows.items():
        _require_fingerprint(fingerprint, f"cost_evidence[{dimension}]")
    for dimension in measured:
        if dimension not in cost_evidence_rows:
            intake_gaps.add(f"cost_measurement_evidence_missing:{dimension}")
    triggers = collect_deep_review_triggers(
        findings,
        explicit_request=explicit_deep_request,
        declared_candidate_count=declared_candidate_count,
        prior_counts=prior_counts,
        current_counts=current_counts,
        growth_thresholds=growth_thresholds,
        path_design_model_miss=path_design_model_miss,
        missing_necessity_witness=any(
            gap.startswith("missing_necessity_witness:") for gap in witness_gaps
        ),
        high_cost_boundary=high_cost_boundary,
        release_critical_boundary=release_critical_boundary,
        measured_costs=measured,
        cost_thresholds=cost_thresholds_value,
    )
    trigger_evidence_rows = dict(
        _canonical_string_pairs(trigger_evidence, "trigger_evidence")
    )
    for trigger_id, fingerprint in trigger_evidence_rows.items():
        _require_fingerprint(fingerprint, f"trigger_evidence[{trigger_id}]")
    if set(trigger_evidence_rows) != set(triggers):
        if triggers:
            intake_gaps.add("deep_trigger_evidence_incomplete")
    if triggers:
        current_trigger_id = trigger_currentness_id or currentness_id
        if current_trigger_id != currentness_id:
            intake_gaps.add("deep_trigger_evidence_stale")
    unresolved = tuple(sorted(set(findings) | set(witness_gaps) | intake_gaps))
    if triggers and not unresolved:
        unresolved = tuple(f"deep_review_required:{trigger}" for trigger in triggers)
    conclusion = "unresolved" if unresolved else "single_clear_path"
    detail = PathQualityArchitectureDetail(
        {
            "mode": "lightweight",
            "subject_fingerprint": subject.fingerprint,
            "model_facts": normalized_facts,
            "retained_elements": dict(retained),
            "witness_fingerprints": (
                [
                    row.fingerprint
                    for row in sorted(necessity_witnesses, key=lambda item: item.witness_id)
                ]
                if explicit_deep_request
                else []
            ),
            "finding_ids": findings,
            "trigger_ids": triggers,
            "trigger_evidence": trigger_evidence_rows,
            "trigger_currentness_id": trigger_currentness_id or currentness_id,
            "measured_costs": measured,
            "cost_thresholds": cost_thresholds_value,
            "cost_evidence": cost_evidence_rows,
            "unresolved_ids": unresolved,
        }
    )
    detail_fingerprint = detail.fingerprint
    if detail_collector is not None:
        detail_collector.append(detail)
    result_id = f"path-quality:{subject.model_id}:{detail_fingerprint[-16:]}"
    return PathQualityResult(
        result_id=result_id,
        subject_fingerprint=subject.fingerprint,
        mode="lightweight",
        trigger_ids=triggers,
        finding_ids=findings,
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion=conclusion,
        unresolved_ids=unresolved,
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=(
            _witness_set_fingerprint(necessity_witnesses)
            if explicit_deep_request
            else _witness_set_fingerprint(())
        ),
        detail_evidence_fingerprint=detail_fingerprint,
        producer_id=producer_id,
        currentness_id=currentness_id,
        optimization_depth="auto",
        cost_dimensions=tuple(sorted(measured)),
        cost_measurements=tuple(sorted(measured.items())),
        cost_detail_evidence_fingerprint=(
            canonical_fingerprint(
                {
                    "measurements": measured,
                    "thresholds": cost_thresholds_value,
                    "evidence": cost_evidence_rows,
                }
            )
            if measured
            else ""
        ),
        trigger_evidence_fingerprint=(
            canonical_fingerprint(
                {
                    "trigger_ids": triggers,
                    "evidence": trigger_evidence_rows,
                    "currentness_id": trigger_currentness_id or currentness_id,
                }
            )
            if triggers
            else ""
        ),
    )


def hard_semantic_mismatches(
    baseline: PathCandidate,
    candidate: PathCandidate,
) -> tuple[str, ...]:
    """Return exact hard dimensions that differ; cost is never inspected here."""

    left = dict(baseline.hard_semantics)
    right = dict(candidate.hard_semantics)
    return tuple(
        dimension
        for dimension in HARD_SEMANTIC_DIMENSIONS
        if left[dimension] != right[dimension]
    )


def compare_cost_vectors(
    left: PathCostVector,
    right: PathCostVector,
    required_dimensions: Iterable[str],
) -> str:
    """Return Pareto relation: dominates, dominated, equal, tradeoff, incomparable."""

    dimensions = _canonical_ids(required_dimensions, "required_cost_dimensions")
    if not dimensions:
        return "incomparable"
    if any(dimension not in PATH_COST_DIMENSIONS for dimension in dimensions):
        raise ValueError("required_cost_dimensions contains an unknown dimension")
    if not left.current or not right.current:
        return "incomparable"
    left_units = dict(left.measurement_units)
    right_units = dict(right.measurement_units)
    for dimension in dimensions:
        if (
            left.value(dimension) is None
            or right.value(dimension) is None
            or left_units.get(dimension) != right_units.get(dimension)
        ):
            return "incomparable"
    left_better = False
    right_better = False
    for dimension in dimensions:
        left_value = left.value(dimension)
        right_value = right.value(dimension)
        assert left_value is not None and right_value is not None
        left_better = left_better or left_value < right_value
        right_better = right_better or right_value < left_value
    if left_better and not right_better:
        return "dominates"
    if right_better and not left_better:
        return "dominated"
    if not left_better and not right_better:
        return "equal"
    return "tradeoff"


def _comparison_gaps(
    subject: PathQualitySubject,
    baseline: PathCandidate,
    candidates: Sequence[PathCandidate],
    required_cost_dimensions: tuple[str, ...],
    active_obligation_ids: tuple[str, ...],
) -> tuple[str, ...]:
    gaps: set[str] = set()
    candidate_ids = [row.candidate_id for row in candidates]
    for candidate_id, count in Counter(candidate_ids).items():
        if count > 1:
            gaps.add(f"duplicate_candidate_id:{candidate_id}")
    for candidate in candidates:
        if candidate.subject_fingerprint != subject.fingerprint:
            gaps.add(f"stale_candidate_subject:{candidate.candidate_id}")
        if candidate.before_model_fingerprint != subject.model_fingerprint:
            gaps.add(f"stale_candidate_before_model:{candidate.candidate_id}")
        if not candidate.current:
            gaps.add(f"stale_candidate:{candidate.candidate_id}")
        if not candidate.required_validation_ids:
            gaps.add(f"candidate_validation_missing:{candidate.candidate_id}")
        if not candidate.evidence_fingerprints:
            gaps.add(f"candidate_evidence_missing:{candidate.candidate_id}")
        if candidate.rewrite_rule_ids and not candidate.affected_element_ids:
            gaps.add(f"rewrite_affected_elements_missing:{candidate.candidate_id}")
        for dimension in hard_semantic_mismatches(baseline, candidate):
            if candidate.lane == "normative_target":
                gaps.add(f"normative_target_semantic_change:{candidate.candidate_id}:{dimension}")
            else:
                gaps.add(f"hard_semantic_mismatch:{candidate.candidate_id}:{dimension}")
        gaps.update(
            validate_necessity_witnesses(
                subject,
                candidate.retained_elements,
                candidate.necessity_witnesses,
                expected_currentness_id=subject.currentness_id,
                active_obligation_ids=active_obligation_ids,
            )
        )
        if len(candidates) > 1:
            if candidate.cost is None:
                gaps.add(f"cost_vector_missing:{candidate.candidate_id}")
                continue
            if not candidate.cost.current:
                gaps.add(f"cost_vector_stale:{candidate.candidate_id}")
            if candidate.cost.currentness_id != subject.currentness_id:
                gaps.add(f"cost_vector_currentness_mismatch:{candidate.candidate_id}")
            for dimension in required_cost_dimensions:
                if candidate.cost.value(dimension) is None:
                    gaps.add(f"cost_measurement_missing:{candidate.candidate_id}:{dimension}")
    if len(candidates) > 1 and not required_cost_dimensions:
        gaps.add("comparison_dimensions_missing")
    if len(candidates) > 1 and required_cost_dimensions:
        for index, left in enumerate(candidates):
            if left.cost is None:
                continue
            for right in candidates[index + 1 :]:
                if right.cost is None:
                    continue
                if compare_cost_vectors(left.cost, right.cost, required_cost_dimensions) == "incomparable":
                    gaps.add(f"cost_vectors_incomparable:{left.candidate_id}:{right.candidate_id}")
    return tuple(sorted(gaps))


def evaluate_deep_path_review(
    subject: PathQualitySubject,
    candidates: Sequence[PathCandidate],
    *,
    baseline_candidate_id: str,
    trigger_ids: Iterable[str],
    trigger_evidence: Mapping[str, str] | Iterable[Sequence[str]],
    trigger_currentness_id: str,
    comparison_boundary_id: str,
    required_cost_dimensions: Iterable[str] = (),
    active_obligation_ids: Iterable[str] | None = None,
    candidate_set_exhausted: bool = False,
    expected_candidate_ids: Iterable[str] = (),
    candidate_exhaustion_evidence_fingerprint: str = "",
    candidate_exhaustion_currentness_id: str = "",
    rewrite_rule_ids: Iterable[str] = (),
    rewrite_dispositions: Mapping[str, str] | Iterable[Sequence[str]] | None = None,
    rewrite_evidence: Mapping[str, str] | Iterable[Sequence[str]] | None = None,
    rewrite_set_exhausted: bool = False,
    rewrite_currentness_id: str = "",
    choice_required: bool = False,
    producer_id: str = "model_maturation",
    detail_collector: list[PathQualityArchitectureDetail] | None = None,
) -> PathQualityResult:
    """Compare only the caller-declared finite hard-equivalent candidate set."""

    if not isinstance(subject, PathQualitySubject):
        raise ValueError("subject must be a PathQualitySubject")
    triggers = _canonical_ids(trigger_ids, "trigger_ids")
    if not triggers:
        raise ValueError("deep review requires at least one current trigger")
    invalid_triggers = tuple(trigger for trigger in triggers if not _is_valid_deep_trigger(trigger))
    if invalid_triggers:
        raise ValueError(f"deep review contains unknown triggers: {', '.join(invalid_triggers)}")
    comparison_boundary_id = _require_string(comparison_boundary_id, "comparison_boundary_id")
    baseline_candidate_id = _require_string(baseline_candidate_id, "baseline_candidate_id")
    producer_id = _require_string(producer_id, "producer_id")
    currentness_id = subject.currentness_id
    trigger_currentness_id = _require_string(trigger_currentness_id, "trigger_currentness_id")
    for name, value in (
        ("candidate_set_exhausted", candidate_set_exhausted),
        ("rewrite_set_exhausted", rewrite_set_exhausted),
        ("choice_required", choice_required),
    ):
        _require_bool(value, name)
    if not isinstance(candidate_exhaustion_currentness_id, str):
        raise ValueError("candidate_exhaustion_currentness_id must be a string")
    if not isinstance(rewrite_currentness_id, str):
        raise ValueError("rewrite_currentness_id must be a string")
    trigger_evidence_rows = dict(_canonical_string_pairs(trigger_evidence, "trigger_evidence"))
    for trigger_id, fingerprint in trigger_evidence_rows.items():
        _require_fingerprint(fingerprint, f"trigger_evidence[{trigger_id}]")
    required_dimensions = _canonical_ids(required_cost_dimensions, "required_cost_dimensions")
    if any(dimension not in PATH_COST_DIMENSIONS for dimension in required_dimensions):
        raise ValueError("required_cost_dimensions contains an unknown dimension")
    raw_rows = tuple(candidates)
    if any(not isinstance(row, PathCandidate) for row in raw_rows):
        raise ValueError("candidates must contain PathCandidate records")
    rows = tuple(sorted(raw_rows, key=lambda row: row.candidate_id))
    active_obligations = _canonical_ids(active_obligation_ids, "active_obligation_ids")
    candidate_by_id = {row.candidate_id: row for row in rows}
    gaps: set[str] = set()
    if set(trigger_evidence_rows) != set(triggers):
        gaps.add("trigger_evidence_incomplete")
    if trigger_currentness_id != subject.currentness_id:
        gaps.add("trigger_evidence_stale")
    baseline = candidate_by_id.get(baseline_candidate_id)
    if baseline is None:
        gaps.add(f"baseline_candidate_missing:{baseline_candidate_id}")
        baseline = rows[0] if rows else None
    observed_ids = tuple(row.candidate_id for row in rows if row.lane == "observed")
    if observed_ids != (baseline_candidate_id,):
        gaps.add("observed_baseline_not_unique")
    if baseline is not None:
        if baseline.lane != "observed":
            gaps.add(f"baseline_not_observed:{baseline_candidate_id}")
        if baseline.after_model_fingerprint != subject.model_fingerprint:
            gaps.add(f"baseline_not_current_model:{baseline_candidate_id}")
        if baseline.normalized_facts_fingerprint != subject.normalized_facts_fingerprint:
            gaps.add(f"baseline_facts_mismatch:{baseline_candidate_id}")
        if (
            baseline.retained_element_inventory_fingerprint
            != subject.retained_element_inventory_fingerprint
        ):
            gaps.add(f"baseline_retained_inventory_mismatch:{baseline_candidate_id}")
    expected_ids = _canonical_ids(expected_candidate_ids, "expected_candidate_ids")
    candidate_exhaustion_evidence_fingerprint = _require_fingerprint(
        candidate_exhaustion_evidence_fingerprint,
        "candidate_exhaustion_evidence_fingerprint",
        optional=True,
    )
    if candidate_set_exhausted:
        if expected_ids != tuple(row.candidate_id for row in rows):
            gaps.add("candidate_inventory_incomplete")
        if not candidate_exhaustion_evidence_fingerprint:
            gaps.add("candidate_exhaustion_evidence_missing")
        if candidate_exhaustion_currentness_id != subject.currentness_id:
            gaps.add("candidate_exhaustion_evidence_stale")
    rewrite_ids = _canonical_ids(rewrite_rule_ids, "rewrite_rule_ids")
    dispositions = dict(_canonical_string_pairs(rewrite_dispositions, "rewrite_dispositions"))
    rewrite_evidence_rows = dict(_canonical_string_pairs(rewrite_evidence, "rewrite_evidence"))
    for rule_id, fingerprint in rewrite_evidence_rows.items():
        _require_fingerprint(fingerprint, f"rewrite_evidence[{rule_id}]")
    if set(dispositions) - set(rewrite_ids) or set(rewrite_evidence_rows) - set(rewrite_ids):
        gaps.add("rewrite_set_contains_undeclared_rule")
    if any(status not in REWRITE_DISPOSITIONS for status in dispositions.values()):
        gaps.add("rewrite_disposition_invalid")
    if rewrite_set_exhausted:
        if not rewrite_ids:
            gaps.add("exhausted_rewrite_set_missing")
        if set(dispositions) != set(rewrite_ids):
            gaps.add("rewrite_disposition_incomplete")
        if set(rewrite_evidence_rows) != set(rewrite_ids):
            gaps.add("rewrite_evidence_incomplete")
        if rewrite_currentness_id != subject.currentness_id:
            gaps.add("rewrite_evidence_stale")
    candidate_rewrite_ids = {
        rule_id for row in rows for rule_id in row.rewrite_rule_ids
    }
    if candidate_rewrite_ids - set(rewrite_ids):
        gaps.add("candidate_contains_undeclared_rewrite")
    for rule_id, disposition in dispositions.items():
        if disposition != "applied":
            continue
        mapped_rows = [row for row in rows if rule_id in row.rewrite_rule_ids]
        if not mapped_rows:
            gaps.add(f"applied_rewrite_candidate_missing:{rule_id}")
        elif all(row.candidate_id == baseline_candidate_id for row in mapped_rows):
            gaps.add(f"applied_rewrite_not_separate_from_baseline:{rule_id}")
    if baseline is not None:
        gaps.update(
            _comparison_gaps(
                subject,
                baseline,
                rows,
                required_dimensions,
                active_obligations,
            )
        )
    elif not rows:
        gaps.add("candidate_set_empty")

    selected_candidate_id = ""
    conclusion = "unresolved"
    if (
        not gaps
        and len(rows) == 1
        and rewrite_set_exhausted
        and set(dispositions.values()) == {"rejected"}
    ):
        conclusion = "locally_irreducible_under_declared_rewrites"
    elif not gaps and len(rows) > 1:
        dominating = []
        for left in rows:
            assert left.cost is not None
            if all(
                left.candidate_id == right.candidate_id
                or (
                    right.cost is not None
                    and compare_cost_vectors(left.cost, right.cost, required_dimensions) == "dominates"
                )
                for right in rows
            ):
                dominating.append(left.candidate_id)
        if len(dominating) == 1:
            selected_candidate_id = dominating[0]
            conclusion = (
                "minimum_within_exhausted_finite_set"
                if candidate_set_exhausted
                else "preferred_within_candidates"
            )
        elif choice_required:
            gaps.add("non_dominated_choice_unresolved")
        else:
            conclusion = "non_dominated_within_boundary"
    elif not gaps:
        gaps.add("deep_candidate_comparison_incomplete")

    if gaps:
        conclusion = "unresolved"
        selected_candidate_id = ""
    candidate_payloads = [row.to_dict() for row in rows]
    candidate_set_fingerprint = (
        canonical_fingerprint([row["fingerprint"] for row in candidate_payloads])
        if rows
        else ""
    )
    rewrite_set_fingerprint = canonical_fingerprint(
        {
            "rule_ids": rewrite_ids,
            "dispositions": dispositions,
            "evidence": rewrite_evidence_rows,
        }
    ) if rewrite_ids else ""
    witnesses = tuple(row for candidate in rows for row in candidate.necessity_witnesses)
    detail = PathQualityArchitectureDetail(
        {
            "mode": "deep",
            "subject_fingerprint": subject.fingerprint,
            "trigger_ids": triggers,
            "trigger_evidence": trigger_evidence_rows,
            "trigger_currentness_id": trigger_currentness_id,
            "comparison_boundary_id": comparison_boundary_id,
            "baseline_candidate_id": baseline_candidate_id,
            "required_cost_dimensions": required_dimensions,
            "active_obligation_ids": active_obligations,
            "candidate_set_exhausted": candidate_set_exhausted,
            "expected_candidate_ids": expected_ids,
            "candidate_exhaustion_evidence_fingerprint": candidate_exhaustion_evidence_fingerprint,
            "candidate_exhaustion_currentness_id": candidate_exhaustion_currentness_id,
            "candidates": candidate_payloads,
            "rewrite_rule_ids": rewrite_ids,
            "rewrite_dispositions": dispositions,
            "rewrite_evidence": rewrite_evidence_rows,
            "rewrite_set_exhausted": rewrite_set_exhausted,
            "rewrite_currentness_id": rewrite_currentness_id,
            "choice_required": choice_required,
            "conclusion": conclusion,
            "selected_candidate_id": selected_candidate_id,
            "unresolved_ids": sorted(gaps),
        }
    )
    detail_fingerprint = detail.fingerprint
    if detail_collector is not None:
        detail_collector.append(detail)
    result_id = f"path-quality:{subject.model_id}:{detail_fingerprint[-16:]}"
    return PathQualityResult(
        result_id=result_id,
        subject_fingerprint=subject.fingerprint,
        mode="deep",
        trigger_ids=triggers,
        finding_ids=(),
        candidate_ids=tuple(sorted({row.candidate_id for row in rows})),
        rewrite_rule_ids=rewrite_ids,
        conclusion=conclusion,
        unresolved_ids=tuple(sorted(gaps)),
        selected_candidate_id=selected_candidate_id,
        selected_candidate_lane=(
            candidate_by_id[selected_candidate_id].lane if selected_candidate_id else ""
        ),
        comparison_boundary_id=comparison_boundary_id,
        candidate_set_fingerprint=candidate_set_fingerprint,
        rewrite_set_fingerprint=rewrite_set_fingerprint,
        necessity_witness_set_fingerprint=_witness_set_fingerprint(witnesses),
        detail_evidence_fingerprint=detail_fingerprint,
        producer_id=producer_id,
        currentness_id=currentness_id,
        candidate_set_exhausted=candidate_set_exhausted,
        rewrite_set_exhausted=rewrite_set_exhausted,
        optimization_depth="deep_closed" if not gaps else "deep_required",
        cost_dimensions=required_dimensions,
        cost_detail_evidence_fingerprint=(
            canonical_fingerprint(
                {
                    "candidate_cost_fingerprints": [
                        row.cost.fingerprint
                        for row in rows
                        if row.cost is not None
                    ],
                    "required_dimensions": list(required_dimensions),
                    "currentness_id": currentness_id,
                }
            )
            if required_dimensions
            else ""
        ),
        trigger_evidence_fingerprint=canonical_fingerprint(
            {
                "trigger_ids": list(triggers),
                "trigger_evidence": trigger_evidence_rows,
                "currentness_id": trigger_currentness_id,
            }
        ),
    )


def bounded_conclusion_text(result: PathQualityResult) -> str:
    """Render only the licensed boundary; never upgrades it to universal best."""

    if not isinstance(result, PathQualityResult):
        raise ValueError("result must be a PathQualityResult")
    messages = {
        "single_clear_path": "one clear current path in the affected model",
        "preferred_within_candidates": "preferred within the declared comparable candidates",
        "non_dominated_within_boundary": "non-dominated within the declared comparison boundary",
        "minimum_within_exhausted_finite_set": "minimum within the exhausted named finite candidate set",
        "locally_irreducible_under_declared_rewrites": "locally irreducible under the declared exhausted rewrite rules",
        "unresolved": "unresolved at the declared model boundary",
    }
    return messages[result.conclusion]


__all__ = [
    "HARD_SEMANTIC_DIMENSIONS",
    "NECESSITY_EVIDENCE_KINDS",
    "PATH_COST_DIMENSIONS",
    "PATH_OPTIMIZATION_DEPTHS",
    "PATH_QUALITY_CONCLUSIONS",
    "PATH_QUALITY_SCHEMA_VERSION",
    "NecessityWitness",
    "PathCandidate",
    "PathCostVector",
    "PathQualityMaterialGap",
    "PathQualityMaterialReview",
    "PathQualityResult",
    "PathQualitySubject",
    "bounded_conclusion_text",
    "collect_deep_review_triggers",
    "derive_retained_elements",
    "evaluate_deep_path_review",
    "lightweight_path_review",
    "normalize_path_quality_material",
    "normalized_model_facts_fingerprint",
    "path_quality_result_set_fingerprint",
    "review_path_quality_material",
]


# Pure graph compilers shared by public declaration and the self adapter.
@dataclass(frozen=True)
class DeclaredGraphProjection:
    provider_kind: str
    facts: Mapping[str, Any]
    element_groundings: Mapping[str, Mapping[str, Any]]
    source_refs: tuple[str, ...]
    gaps: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(
            {
                "provider_kind": self.provider_kind,
                "facts": dict(self.facts),
                "element_groundings": {
                    key: dict(value)
                    for key, value in sorted(self.element_groundings.items())
                },
                "source_refs": list(self.source_refs),
                "gaps": list(self.gaps),
            }
        )


def _stable(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._:/-]+", "-", str(value).strip()).strip("-")
    return text or canonical_fingerprint({"value": str(value)})[-16:]


def _sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, Sequence):
        return ()
    return tuple(str(item) for item in value if str(item))


def _type_name(value: Any) -> str:
    if isinstance(value, tuple):
        return "|".join(sorted(_type_name(item) for item in value))
    return str(getattr(value, "__qualname__", getattr(value, "__name__", value)))


def _declared_workflow_projection(
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
    workflows: Sequence[Workflow],
    invariants: Sequence[Invariant],
) -> DeclaredGraphProjection:
    from .core import block_name

    states: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    field_uses: dict[str, dict[str, set[str]]] = {}
    effect_ids: set[str] = set()
    groundings: dict[str, Mapping[str, Any]] = {}

    validation_ids: list[str] = []
    for invariant in invariants:
        validation_id = f"validation:{entry.model_id}:invariant:{_stable(invariant.name)}"
        validation_ids.append(validation_id)
        validations.append(
            {
                "id": validation_id,
                "obligation_id": f"obligation:native-invariant:{entry.model_id}:{_stable(invariant.name)}",
                "oracle_id": f"oracle:native-invariant:{entry.model_id}:{_stable(invariant.name)}",
                "subject_fingerprint": instance.fingerprint,
                "evidence_boundary_id": f"native-runner:{entry.model_id}",
            }
        )
        groundings[validation_id] = {
            "kind": "native_invariant_binding",
            "invariant_name": invariant.name,
            "invariant_description": invariant.description,
            "runner_fingerprint": instance.runner_sha256,
        }

    for workflow_index, workflow in enumerate(workflows):
        signature = canonical_fingerprint(
            {
                "name": workflow.name,
                "blocks": [block_name(block) for block in workflow.blocks],
            }
        )[-12:]
        workflow_id = (
            f"workflow:{entry.model_id}:{_stable(workflow.name)}:"
            f"{workflow_index}:{signature}"
        )
        state_ids = tuple(
            f"state:{workflow_id}:{index}" for index in range(len(workflow.blocks) + 1)
        )
        for index, state_id in enumerate(state_ids):
            states.append(
                {
                    "id": state_id,
                    "initial": index == 0,
                    "terminal": index == len(state_ids) - 1,
                    "behaviorally_relevant": True,
                }
            )
            groundings[state_id] = {
                "kind": "executable_workflow_state",
                "workflow_id": workflow_id,
                "position": index,
                "workflow_fingerprint": signature,
            }
        for index, block in enumerate(workflow.blocks):
            name = block_name(block)
            block_id = f"function-block:{workflow_id}:{index}:{_stable(name)}"
            transition_id = f"transition:{workflow_id}:{index}:{_stable(name)}"
            output_id = f"output:{workflow_id}:{index}:{_stable(name)}"
            reads = tuple(
                f"field:{entry.model_id}:{_stable(item)}"
                for item in _sequence(getattr(block, "reads", ()))
            )
            writes = tuple(
                f"field:{entry.model_id}:{_stable(item)}"
                for item in _sequence(getattr(block, "writes", ()))
            )
            effects = tuple(
                f"effect:{entry.model_id}:{_stable(item)}"
                for item in _sequence(getattr(block, "effects", ()))
            )
            for field_id in reads:
                field_uses.setdefault(field_id, {"reads": set(), "writes": set()})[
                    "reads"
                ].add(block_id)
            for field_id in writes:
                field_uses.setdefault(field_id, {"reads": set(), "writes": set()})[
                    "writes"
                ].add(block_id)
            effect_ids.update(effects)
            attached_validations = tuple(validation_ids) if index == len(workflow.blocks) - 1 else ()
            prior_output = (
                f"external-input:{workflow_id}"
                if index == 0
                else f"output:{workflow_id}:{index - 1}:{_stable(block_name(workflow.blocks[index - 1]))}"
            )
            blocks.append(
                {
                    "id": block_id,
                    "inputs": [prior_output],
                    "outputs": [output_id],
                    "reads": list(reads),
                    "writes": list(writes),
                    "effects": list(effects),
                    "validations": list(attached_validations),
                    "state_input": state_ids[index],
                    "state_output": state_ids[index + 1],
                    "pass_through": bool(getattr(block, "pass_through", False)),
                    "accepted_input": _type_name(
                        getattr(
                            block,
                            "accepted_input_type",
                            getattr(block, "accepted_input_types", "any"),
                        )
                    ),
                }
            )
            transitions.append(
                {
                    "id": transition_id,
                    "source": state_ids[index],
                    "target": state_ids[index + 1],
                    "trigger": _type_name(
                        getattr(
                            block,
                            "accepted_input_type",
                            getattr(block, "accepted_input_types", "any"),
                        )
                    ),
                    "guard": "flowguard-block-acceptance",
                    "outputs": [output_id],
                    "reads": list(reads),
                    "writes": list(writes),
                    "effects": list(effects),
                    "validations": list(attached_validations),
                    "function_block_ids": [block_id],
                }
            )
            outputs.append(
                {
                    "id": output_id,
                    "producer_id": transition_id,
                    "consumer_ids": (
                        []
                        if index == len(workflow.blocks) - 1
                        else [
                            f"function-block:{workflow_id}:{index + 1}:"
                            f"{_stable(block_name(workflow.blocks[index + 1]))}"
                        ]
                    ),
                    "terminal": index == len(workflow.blocks) - 1,
                }
            )
            relation = {
                "kind": "executable_workflow_block_relation",
                "workflow_id": workflow_id,
                "position": index,
                "block_name": name,
                "block_type": type(block).__qualname__,
                "source_state_id": state_ids[index],
                "target_state_id": state_ids[index + 1],
                "runner_fingerprint": instance.runner_sha256,
            }
            groundings[block_id] = relation
            groundings[transition_id] = {**relation, "kind": "executable_workflow_transition"}

    fields = [
        {
            "id": field_id,
            "reads_by": sorted(uses["reads"]),
            "writes_by": sorted(uses["writes"]),
            "observable": bool(uses["writes"]),
            "behaviorally_relevant": True,
            "declared": True,
        }
        for field_id, uses in sorted(field_uses.items())
    ]
    for row in fields:
        groundings[row["id"]] = {
            "kind": "explicit_function_block_field_contract",
            "reads_by": row["reads_by"],
            "writes_by": row["writes_by"],
            "model_fingerprint": instance.fingerprint,
        }
    effects = [{"id": effect_id} for effect_id in sorted(effect_ids)]
    for effect_id in effect_ids:
        groundings[effect_id] = {
            "kind": "explicit_function_block_effect_contract",
            "model_fingerprint": instance.fingerprint,
        }
    facts = {
        "provider_kind": "flowguard.executable-workflow-structure.v1",
        "states": states,
        "initial_state_ids": [row["id"] for row in states if row["initial"]],
        "terminal_state_ids": [row["id"] for row in states if row["terminal"]],
        "transitions": transitions,
        "function_blocks": blocks,
        "fields": fields,
        "effects": effects,
        "validations": validations,
        "outputs": outputs,
        "owners": [],
    }
    return DeclaredGraphProjection(
        provider_kind="flowguard.executable-workflow-structure.v1",
        facts=facts,
        element_groundings=groundings,
        source_refs=(entry.model_path, entry.runner[1]),
    )


def _declared_contract_export_projection(
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
    exported: Mapping[str, Any],
) -> DeclaredGraphProjection:
    steps = exported.get("steps")
    routes = exported.get("routes")
    obligations = exported.get("obligations")
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"contract export has no steps: {entry.model_id}")
    if not isinstance(routes, list) or not routes:
        raise ValueError(f"contract export has no routes: {entry.model_id}")
    if not isinstance(obligations, list):
        raise ValueError(f"contract export obligations are invalid: {entry.model_id}")
    step_by_id = {str(row.get("step_id", "")): row for row in steps if isinstance(row, Mapping)}
    if "" in step_by_id or len(step_by_id) != len(steps):
        raise ValueError(f"contract export step identities are invalid: {entry.model_id}")
    blocks: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    groundings: dict[str, Mapping[str, Any]] = {}
    obligation_ids_by_step: dict[str, list[str]] = {}
    for raw in obligations:
        if not isinstance(raw, Mapping):
            raise ValueError(f"contract export obligation row is invalid: {entry.model_id}")
        obligation_id = str(raw.get("obligation_id", ""))
        invariant_id = str(raw.get("invariant_id", ""))
        owner_step_ids = tuple(str(item) for item in raw.get("owner_step_ids", ()))
        if not obligation_id or not invariant_id or not owner_step_ids:
            raise ValueError(f"contract export obligation is incomplete: {entry.model_id}")
        validation_id = f"validation:{entry.model_id}:contract:{_stable(obligation_id)}"
        validations.append(
            {
                "id": validation_id,
                "obligation_id": obligation_id,
                "oracle_id": invariant_id,
                "subject_fingerprint": instance.fingerprint,
                "evidence_boundary_id": f"contract-export:{entry.model_id}",
            }
        )
        groundings[validation_id] = {
            "kind": "exported_contract_obligation",
            "obligation_id": obligation_id,
            "invariant_id": invariant_id,
            "owner_step_ids": list(owner_step_ids),
        }
        for step_id in owner_step_ids:
            if step_id not in step_by_id:
                raise ValueError(
                    f"contract export obligation references an unknown step: {entry.model_id}:{step_id}"
                )
            obligation_ids_by_step.setdefault(step_id, []).append(validation_id)
    route_terminal_steps = {
        str(raw.get(name, ""))
        for raw in routes
        if isinstance(raw, Mapping)
        for name in ("success_terminal_step_id", "blocked_terminal_step_id")
        if str(raw.get(name, ""))
    }
    for index, (step_id, raw) in enumerate(sorted(step_by_id.items())):
        prerequisites = tuple(str(item) for item in raw.get("prerequisite_step_ids", ()))
        if any(item not in step_by_id for item in prerequisites):
            raise ValueError(
                f"contract export prerequisite references an unknown step: {entry.model_id}:{step_id}"
            )
        block_id = f"function-block:{entry.model_id}:contract:{_stable(step_id)}"
        output_id = f"output:{entry.model_id}:contract:{_stable(step_id)}"
        inputs = (
            [f"output:{entry.model_id}:contract:{_stable(item)}" for item in prerequisites]
            or [f"external-input:{entry.model_id}:{_stable(str(raw.get('route_id', 'route')))}"]
        )
        blocks.append(
            {
                "id": block_id,
                "inputs": inputs,
                "outputs": [output_id],
                "validations": obligation_ids_by_step.get(step_id, ()),
                "state_input": "",
                "state_output": f"contract-step-state:{_stable(step_id)}",
                "pass_through": False,
                "action_kind": str(raw.get("action_kind", "native")),
            }
        )
        outputs.append(
            {
                "id": output_id,
                "producer_id": block_id,
                "consumer_ids": [
                    f"function-block:{entry.model_id}:contract:{_stable(candidate_id)}"
                    for candidate_id, candidate in step_by_id.items()
                    if step_id in tuple(str(item) for item in candidate.get("prerequisite_step_ids", ()))
                ],
                "terminal": step_id in route_terminal_steps,
            }
        )
        groundings[block_id] = {
            "kind": "exported_contract_step",
            "step_id": step_id,
            "route_id": str(raw.get("route_id", "")),
            "action_kind": str(raw.get("action_kind", "")),
            "terminal_kind": str(raw.get("terminal_kind", "")),
            "prerequisite_step_ids": list(prerequisites),
            "contract_fingerprint": canonical_fingerprint(dict(exported)),
            "position": index,
        }
    facts = {
        "provider_kind": "flowguard.executable-contract-export.v1",
        "states": [],
        "initial_state_ids": [],
        "terminal_state_ids": [],
        "transitions": [],
        "function_blocks": blocks,
        "fields": [],
        "effects": [],
        "validations": validations,
        "outputs": outputs,
        "owners": [],
        "export_schema_version": str(exported.get("schema_version", "")),
        "export_model_id": str(exported.get("model_id", "")),
        "export_parent_model_id": str(exported.get("parent_model_id", "")),
    }
    return DeclaredGraphProjection(
        provider_kind="flowguard.executable-contract-export.v1",
        facts=facts,
        element_groundings=groundings,
        source_refs=(entry.model_path, entry.runner[1]),
    )


DECLARED_PATH_QUALITY_SOURCE_SCHEMA = "flowguard.declared_path_quality_source.v1"
PATH_QUALITY_ARCHITECTURE_DETAIL_SCHEMA = "flowguard.path_quality_architecture_detail.v1"
ARCHITECTURE_HARD_DIMENSION_PROJECTION = {
    "input": ("accepted_inputs", "rejected_inputs"), "output": ("outputs",),
    "state_effect": ("state_transitions", "field_transitions", "side_effects", "parent_interfaces", "child_interfaces"),
    "error": ("protected_errors", "recovery"), "order": ("order",), "retry": ("retry",),
    "timeout": ("timeout", "cancellation"), "decision": ("permissions", "authority", "intent", "behavior_commitments"),
    "completion": ("terminal_states", "progress", "fairness", "oracles", "evidence_obligations"),
}


def _exact_object(value, names, label):
    if not isinstance(value, Mapping) or set(value) != set(names):
        raise ValueError(f"{label} fields must be exact: {sorted(names)}")
    _validate_json_value(value, label)
    return dict(value)


def _json_copy(value):
    return json.loads(canonical_json(value))


@dataclass(frozen=True)
class ResponsibilitySemanticEvidenceBinding:
    hard_dimension_id: str
    input_class_id: str
    semantic_spec_id: str
    oracle_id: str
    native_case_binding_fingerprint: str
    owner_receipt_id: str
    owner_receipt_fingerprint: str
    owner_id: str
    source_case_ids: tuple[str, ...]
    evidence_scope: str

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name == "source_case_ids":
                object.__setattr__(self, item.name, _canonical_ids(value, item.name))
                if not value:
                    raise ValueError("semantic proof source cases missing")
            elif item.name.endswith("fingerprint"):
                _require_fingerprint(value, item.name)
            else:
                _require_string(value, item.name)
        if self.hard_dimension_id not in HARD_SEMANTIC_DIMENSIONS:
            raise ValueError("unknown hard semantic dimension")
        if self.evidence_scope not in {"model_policy", "implementation_boundary"}:
            raise ValueError("unsupported semantic evidence scope")

    def to_dict(self):
        return {f.name: list(getattr(self, f.name)) if f.name == "source_case_ids" else getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, value):
        return cls(**_exact_object(value, (f.name for f in fields(cls)), "semantic evidence binding"))


@dataclass(frozen=True)
class ArchitectureResponsibilityFact:
    responsibility_id: str
    model_id: str
    element_ids: tuple[str, ...]
    owner_id: str
    boundary_id: str
    layer_id: str
    applicable_input_class_ids: tuple[str, ...]
    hard_semantics: Mapping[str, Any]
    mechanism_id: str
    mechanism_fingerprint: str
    owner_code_contract_id: str
    owner_code_contract_fingerprint: str
    semantic_spec_ids: tuple[str, ...]
    semantic_spec_fingerprints: tuple[str, ...]
    oracle_ids: tuple[str, ...]
    implementation_binding_fingerprint: str
    source_refs: tuple[Mapping[str, str], ...]
    evidence_fingerprints: tuple[str, ...] = ()
    semantic_evidence_bindings: tuple[ResponsibilitySemanticEvidenceBinding, ...] = ()

    def __post_init__(self):
        for name in ("responsibility_id", "model_id", "owner_id", "boundary_id", "layer_id", "mechanism_id", "owner_code_contract_id"):
            _require_string(getattr(self, name), name)
        for name in ("mechanism_fingerprint", "owner_code_contract_fingerprint", "implementation_binding_fingerprint"):
            _require_fingerprint(getattr(self, name), name)
        for name in ("element_ids", "applicable_input_class_ids", "semantic_spec_ids", "oracle_ids", "semantic_spec_fingerprints", "evidence_fingerprints"):
            object.__setattr__(self, name, _canonical_ids(getattr(self, name), name))
        if not self.element_ids or not self.applicable_input_class_ids:
            raise ValueError("unknown_responsibility_context")
        _exact_object(self.hard_semantics, HARD_SEMANTIC_DIMENSIONS, "hard semantics")
        object.__setattr__(self, "hard_semantics", _json_copy(self.hard_semantics))
        object.__setattr__(self, "source_refs", tuple(_source_ref_dict(x) for x in self.source_refs))
        object.__setattr__(self, "semantic_evidence_bindings", tuple(x if isinstance(x, ResponsibilitySemanticEvidenceBinding) else ResponsibilitySemanticEvidenceBinding.from_dict(x) for x in self.semantic_evidence_bindings))

    def to_dict(self):
        return {f.name: [x.to_dict() for x in self.semantic_evidence_bindings] if f.name == "semantic_evidence_bindings" else _json_copy(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, value):
        return cls(**_exact_object(value, (f.name for f in fields(cls)), "architecture responsibility"))


def _source_ref_dict(value):
    from .model_authority import ModelInputRef
    if isinstance(value, ModelInputRef):
        return {"path": value.path, "source_fingerprint": value.sha256}
    row = _exact_object(value, ("path", "source_fingerprint"), "declared source ref")
    checked = ModelInputRef(row["path"], row["source_fingerprint"])
    return {"path": checked.path, "source_fingerprint": checked.sha256}


_SCOPE_FIELDS = ("claim_scope", "implementation_inventory_id", "implementation_inventory_fingerprint", "binding_report_fingerprint", "claimed_surface_ids", "covered_surface_ids", "coverage_gap_ids")


@dataclass(frozen=True)
class DeclaredPathQualitySource(_CanonicalRecord):
    model_id: str
    model_instance_fingerprint: str
    subject_lane: str
    graph_scope: str
    provider_kind: str
    source_refs: tuple[Mapping[str, str], ...]
    model_facts: Mapping[str, Any]
    element_groundings: Mapping[str, Mapping[str, Any]]
    declared_element_ids: tuple[str, ...]
    scope_coverage: Mapping[str, Any]
    schema: str = DECLARED_PATH_QUALITY_SOURCE_SCHEMA

    def __post_init__(self):
        _require_string(self.model_id, "model_id")
        _require_fingerprint(self.model_instance_fingerprint, "model_instance_fingerprint")
        _require_string(self.provider_kind, "provider_kind")
        if self.schema != DECLARED_PATH_QUALITY_SOURCE_SCHEMA or self.subject_lane not in {"observed_implementation", "normative_target"} or self.graph_scope not in {"model_behavior", "native_check_contract"}:
            raise ValueError("declared source schema/lane/scope invalid")
        refs = tuple(_source_ref_dict(x) for x in self.source_refs)
        if not refs or len({x["path"] for x in refs}) != len(refs):
            raise ValueError("declared_source_missing")
        object.__setattr__(self, "source_refs", tuple(sorted(refs, key=lambda x: x["path"])))
        facts = _normalized_model_facts(self.model_facts)
        object.__setattr__(self, "model_facts", _json_copy(facts))
        object.__setattr__(self, "declared_element_ids", _canonical_ids(self.declared_element_ids, "declared_element_ids"))
        if self.declared_element_ids != tuple(x for x, _ in derive_retained_elements(facts)):
            raise ValueError("declared_denominator_mismatch")
        if set(self.element_groundings) != set(self.declared_element_ids):
            raise ValueError("grounding_missing")
        source_map = {x["path"]: x["source_fingerprint"] for x in refs}
        for element, grounding in self.element_groundings.items():
            if not isinstance(grounding, Mapping) or grounding.get("source_fingerprint") != source_map.get(grounding.get("source_ref")):
                raise ValueError(f"declared_source_identity_mismatch:{element}")
        object.__setattr__(self, "element_groundings", _json_copy(self.element_groundings))
        scope = _exact_object(self.scope_coverage, _SCOPE_FIELDS, "scope coverage")
        if scope["claim_scope"] not in {"declared_model", "software_architecture"}:
            raise ValueError("scope coverage claim invalid")
        for name in ("claimed_surface_ids", "covered_surface_ids", "coverage_gap_ids"):
            scope[name] = list(_canonical_ids(scope[name], name))
        for name in ("implementation_inventory_fingerprint", "binding_report_fingerprint"):
            _require_fingerprint(scope[name], name, optional=True)
        object.__setattr__(self, "scope_coverage", scope)
        for raw in facts.get("responsibilities", ()):
            fact = ArchitectureResponsibilityFact.from_dict(raw)
            # Same-episode receipts are admitted after producer completion only.
            if fact.semantic_evidence_bindings or fact.evidence_fingerprints:
                raise ValueError("declaration cannot self-attest receipt evidence")
        def reject_receipt(value):
            if isinstance(value, Mapping):
                if {"owner_receipt_id", "owner_receipt_fingerprint"} & set(value):
                    raise ValueError("declaration cannot embed episode receipt")
                for item in value.values(): reject_receipt(item)
            elif isinstance(value, (tuple, list)):
                for item in value: reject_receipt(item)
        # The typed responsibility empty fields are allowed; receipt-valued data is not.
        for raw in facts.get("responsibilities", ()):
            for binding in raw.get("semantic_evidence_bindings", ()): reject_receipt(binding)
        reject_receipt(self.element_groundings)

    def identity_payload(self):
        return {f.name: _json_copy(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, value):
        names = {f.name for f in fields(cls)}
        row = _exact_object(value, names | {"fingerprint"}, "declared path quality source")
        fp = row.pop("fingerprint")
        result = cls(**row)
        if result.fingerprint != fp:
            raise ValueError("declared_source_identity_mismatch")
        return result


def compile_declared_path_quality_source(*, model_id, model_instance_fingerprint, source_refs, subject_lane="observed_implementation", graph_scope="model_behavior", provider_kind="flowguard.executable-workflow-structure.v1", model_facts=None, workflows=(), invariants=(), contract_export=None, scope_coverage=None, element_groundings=None, declared_contracts=None):
    """Data-only complete declared graph compiler. No imports, discovery or execution."""
    refs = tuple(_source_ref_dict(x) for x in source_refs)
    if declared_contracts is not None:
        if model_facts is not None or workflows or contract_export is not None or graph_scope != "native_check_contract":
            raise ValueError("declared contract inputs require exact native_check_contract scope")
        from dataclasses import is_dataclass, asdict
        def data(value):
            if hasattr(value, "to_dict"): return data(value.to_dict())
            if is_dataclass(value): return data(asdict(value))
            if isinstance(value, Mapping): return {str(k): data(v) for k, v in value.items()}
            if isinstance(value, (tuple, list)): return [data(v) for v in value]
            if isinstance(value, (set, frozenset)): return sorted(data(v) for v in value)
            if value is None or isinstance(value, (str, bool, int, float)): return value
            raise ValueError("declared contract contains non-data value")
        rows = data(declared_contracts)
        if not isinstance(rows, Mapping) or not rows:
            raise ValueError("declared_source_missing")
        model_facts = {"function_blocks": [{"id": f"function-block:{model_id}:contract:{key}", "contract": value} for key, value in sorted(rows.items())]}
        element_groundings = {f"function-block:{model_id}:contract:{key}": {"kind": "explicit_native_check_contract", "contract_id": key, "contract": value} for key, value in sorted(rows.items())}
        provider_kind = "flowguard.native-check-contract.v1"
    if model_facts is None:
        from types import SimpleNamespace
        if not refs:
            raise ValueError("declared_source_missing")
        entry = SimpleNamespace(model_id=model_id, model_path=refs[0]["path"], runner=("python", refs[-1]["path"]))
        instance = SimpleNamespace(fingerprint=model_instance_fingerprint, runner_sha256=refs[-1]["source_fingerprint"])
        if workflows and contract_export is not None:
            raise ValueError("ambiguous declared graph provider")
        if workflows:
            projection = _declared_workflow_projection(entry, instance, workflows, invariants)
        elif contract_export is not None:
            projection = _declared_contract_export_projection(entry, instance, contract_export)
        else:
            raise ValueError("declared_source_missing")
        facts = dict(projection.facts)
        provider_kind = projection.provider_kind
        raw_groundings = projection.element_groundings
    else:
        facts = dict(model_facts)
        raw_groundings = element_groundings or {}
    for name, _ in _FACT_ROW_KINDS:
        facts.setdefault(name, [])
    facts.setdefault("outputs", [])
    facts.setdefault("owners", [])
    facts.setdefault("responsibilities", [])
    retained = derive_retained_elements(facts)
    default_ref = refs[0] if refs else None
    groundings = {}
    for element_id, kind in retained:
        # Explicit model_facts intake requires element-local groundings; workflows
        # have an exact structural relation supplied by the shared compiler.
        raw = raw_groundings.get(element_id)
        if raw is None:
            raise ValueError(f"grounding_missing:{element_id}")
        groundings[element_id] = {"source_ref": default_ref["path"], "source_fingerprint": default_ref["source_fingerprint"], **dict(raw)}
    scope = scope_coverage or {"claim_scope": "declared_model", "implementation_inventory_id": "", "implementation_inventory_fingerprint": "", "binding_report_fingerprint": "", "claimed_surface_ids": [], "covered_surface_ids": [], "coverage_gap_ids": []}
    return DeclaredPathQualitySource(model_id, model_instance_fingerprint, subject_lane, graph_scope, provider_kind, refs, facts, groundings, tuple(x for x, _ in retained), scope)


def verify_declared_path_quality_source(source, model_instance, *, current_source_refs=None):
    """Verify against independently selected current instance and exact input universe."""
    if not isinstance(source, DeclaredPathQualitySource):
        return ("declared_source_missing",)
    gaps = set()
    if source.model_id != model_instance.logical_model_id or source.model_instance_fingerprint != model_instance.fingerprint:
        gaps.add("declared_source_identity_mismatch")
    actual = {x.path: x.sha256 for x in model_instance.inputs}
    if current_source_refs is not None:
        actual = {x["path"]: x["source_fingerprint"] for x in map(_source_ref_dict, current_source_refs)}
    for ref in source.source_refs:
        if actual.get(ref["path"]) != ref["source_fingerprint"]:
            gaps.add("declared_source_identity_mismatch")
    for key in (name for name, _ in _FACT_ROW_KINDS):
        if key not in source.model_facts:
            gaps.add(f"provider_fact_missing:{key}")
    return tuple(sorted(gaps))


def verify_declared_source_scope_coverage(source, *, implementation_inventory=None, binding_report=None, root=None):
    scope = source.scope_coverage
    if scope["claim_scope"] == "declared_model":
        return ()
    if source.graph_scope == "native_check_contract" or implementation_inventory is None or binding_report is None:
        return ("implementation_scope_coverage_missing",)
    from .implementation_inventory import review_implementation_surface_inventory
    review = review_implementation_surface_inventory(implementation_inventory, root=root)
    gaps = set()
    if not review.ok or not binding_report.ok:
        gaps.add("implementation_scope_coverage_missing")
    if root is None:
        gaps.add("implementation_scope_coverage_stale")
    if (scope["implementation_inventory_id"] != implementation_inventory.inventory_id or scope["implementation_inventory_fingerprint"] != implementation_inventory.fingerprint or scope["binding_report_fingerprint"] != binding_report.fingerprint or binding_report.inventory_fingerprint != implementation_inventory.fingerprint):
        gaps.add("implementation_scope_coverage_stale")
    from .implementation_blueprint import review_model_implementation_bindings
    repeated = review_model_implementation_bindings(implementation_inventory,
        required_model_element_ids=binding_report.required_model_element_ids,
        bindings=binding_report.bindings, semantic_specs=binding_report.semantic_specs,
        oracles=binding_report.oracles)
    if not repeated.ok or repeated.fingerprint != binding_report.fingerprint:
        gaps.add("implementation_scope_coverage_missing")
    required = set(binding_report.required_implementation_surface_ids)
    if set(scope["claimed_surface_ids"]) != required or set(scope["covered_surface_ids"]) != required or scope["coverage_gap_ids"]:
        gaps.add("implementation_scope_omission")
    return tuple(sorted(gaps))

@dataclass(frozen=True, init=False)
class ResponsibilitySemanticEvidenceReview:
    responsibility_fingerprint: str
    semantic_content_fingerprint: str
    evidence_scope: str
    gap_ids: tuple[str, ...]
    admitted_binding_fingerprints: tuple[str, ...] = ()
    admitted_relation_ids: tuple[str, ...] = ()

    def __new__(cls, *args, **kwargs):
        raise TypeError("ResponsibilitySemanticEvidenceReview is created only by evidence verification")

    @property
    def ready(self):
        return not self.gap_ids and bool(self.admitted_binding_fingerprints)


def _responsibility_semantic_review(fact_fingerprint, semantic_fingerprint, evidence_scope, gap_ids, binding_fingerprints=(), relation_ids=()):
    review = object.__new__(ResponsibilitySemanticEvidenceReview)
    for name, value in (("responsibility_fingerprint", fact_fingerprint), ("semantic_content_fingerprint", semantic_fingerprint), ("evidence_scope", evidence_scope), ("gap_ids", tuple(gap_ids)), ("admitted_binding_fingerprints", tuple(binding_fingerprints)), ("admitted_relation_ids", tuple(relation_ids))):
        object.__setattr__(review, name, value)
    return review


def verify_responsibility_semantic_evidence(fact, *, binding_report=None, implementation_inventory=None, code_contracts=(), native_contracts=(), native_results=(), native_bindings=(), receipts=(), receipt_contexts=None, raw_artifact_root=None, current_source_fingerprints=None, current_native_identities=None, native_input_class_ids=None, observed_source_inputs=(), required_evidence_scope="implementation_boundary", read_context=None):
    """Consume original independent source/native/receipt evidence without producers."""
    from .evidence_receipts import verify_evidence_receipt
    from .native_case_protocol import verify_native_model_cases, verify_native_case_bindings
    fact = fact if isinstance(fact, ArchitectureResponsibilityFact) else ArchitectureResponsibilityFact.from_dict(fact)
    gaps = set()
    fp = canonical_fingerprint(fact.to_dict())
    if binding_report is not None and implementation_inventory is not None:
        from .implementation_blueprint import review_model_implementation_bindings
        repeated = review_model_implementation_bindings(implementation_inventory,
            required_model_element_ids=binding_report.required_model_element_ids,
            bindings=binding_report.bindings, semantic_specs=binding_report.semantic_specs,
            oracles=binding_report.oracles)
        if not repeated.ok or repeated.fingerprint != binding_report.fingerprint:
            gaps.add("responsibility_semantics_evidence_missing")
    else:
        gaps.add("responsibility_semantics_evidence_missing")
    bindings = {x.fingerprint: x for x in getattr(binding_report, "bindings", ())}
    implementation = bindings.get(fact.implementation_binding_fingerprint)
    contracts = {x.code_contract_id: x for x in code_contracts}
    contract = contracts.get(fact.owner_code_contract_id)
    source_fps = dict(current_source_fingerprints or {})
    observed_fps = {}
    for value in observed_source_inputs:
        source = _exact_object(value, ("path", "sha256"), "observed production source")
        checked = _source_ref_dict({"path": source["path"], "source_fingerprint": source["sha256"]})
        if checked["path"] in observed_fps:
            raise ValueError("duplicate observed production source")
        observed_fps[checked["path"]] = checked["source_fingerprint"]
    if binding_report is None or not binding_report.ok or implementation is None or contract is None:
        gaps.add("responsibility_semantics_evidence_missing")
    else:
        if (implementation.owner_contract_id != contract.code_contract_id or implementation.owner_contract_fingerprint != fact.owner_code_contract_fingerprint or canonical_fingerprint(contract.to_dict()) != fact.owner_code_contract_fingerprint or implementation.implementation_owner_id != fact.owner_id or implementation.model_element_id not in fact.element_ids or not contract.path or not contract.symbol or source_fps.get(contract.path) != implementation.implementation_content_fingerprint or observed_fps.get(contract.path) != implementation.implementation_content_fingerprint or not set(implementation.model_obligation_ids) <= set(contract.implements_obligations)):
            gaps.add("responsibility_native_binding_invalid")
    specs = {x.semantic_spec_id: x for x in getattr(binding_report, "semantic_specs", ())}
    oracles = {x.oracle_id: x for x in getattr(binding_report, "oracles", ())}
    content = {}
    for spec_id in fact.semantic_spec_ids:
        spec = specs.get(spec_id)
        if spec is None or spec.fingerprint not in fact.semantic_spec_fingerprints or spec.authority_kind == "observed_candidate" or not spec.provenance_fingerprints or not set(fact.element_ids) <= set(spec.covered_model_element_ids):
            gaps.add("responsibility_source_not_independent")
            continue
        for dimension, serialized in spec.semantics:
            try:
                def unique(pairs):
                    out = {}
                    for k, v in pairs:
                        if k in out: raise ValueError("duplicate semantic key")
                        out[k] = v
                    return out
                row = json.loads(serialized, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
                _exact_object(row, ("schema", "dimension", "input_class_ids", "hard_dimensions"), "hard semantic source")
                if row["schema"] != "flowguard.architecture_hard_semantics.v1" or row["dimension"] != dimension or set(row["input_class_ids"]) != set(fact.applicable_input_class_ids):
                    raise ValueError("semantic context mismatch")
                _exact_object(row["hard_dimensions"], ARCHITECTURE_HARD_DIMENSION_PROJECTION[dimension], "hard dimension map")
                for hard, value in row["hard_dimensions"].items():
                    if not isinstance(value, Mapping) or not value or (set(value) == {"not_applicable"} and not value["not_applicable"]):
                        raise ValueError("hard semantic content must be explicit independently sourced contract or justified not_applicable")
                    if hard in content and content[hard] != value:
                        raise ValueError("contradictory semantic content")
                    content[hard] = value
            except (ValueError, KeyError, TypeError):
                gaps.add("responsibility_source_not_independent")
    if {specs[x].fingerprint for x in fact.semantic_spec_ids if x in specs} != set(fact.semantic_spec_fingerprints):
        gaps.add("responsibility_source_not_independent")
    if set(content) != set(HARD_SEMANTIC_DIMENSIONS) or content != dict(fact.hard_semantics) or len(fact.semantic_spec_ids) != len(fact.semantic_spec_fingerprints):
        gaps.add("responsibility_semantics_evidence_missing")
    receipt_by_id = {x.receipt_id: x for x in receipts}
    native_by_fp = {x.fingerprint: x for x in native_bindings}
    rows_by_key = {(x.owner_id, x.source_case_id): x for x in native_results}
    contract_by_key = {(x.owner_id, x.source_case_id): x for x in native_contracts}
    if (len(receipt_by_id) != len(receipts) or len(native_by_fp) != len(native_bindings)
            or len(rows_by_key) != len(native_results) or len(contract_by_key) != len(native_contracts)):
        gaps.add("responsibility_native_binding_invalid")
    admitted = []
    expected = {(dimension, cls) for dimension in HARD_SEMANTIC_DIMENSIONS for cls in fact.applicable_input_class_ids}
    actual = set()
    receipt_reviews, native_reviews, binding_reviews, observation_reviews = {}, {}, {}, {}
    for proof in fact.semantic_evidence_bindings:
        pair = (proof.hard_dimension_id, proof.input_class_id)
        if pair in actual or pair not in expected or proof.owner_id != fact.owner_id or proof.semantic_spec_id not in fact.semantic_spec_ids or proof.oracle_id not in fact.oracle_ids or proof.evidence_scope != required_evidence_scope:
            gaps.add("responsibility_native_binding_invalid")
        actual.add(pair)
        receipt = receipt_by_id.get(proof.owner_receipt_id)
        native_binding = native_by_fp.get(proof.native_case_binding_fingerprint)
        oracle = oracles.get(proof.oracle_id)
        if receipt is None or native_binding is None or oracle is None:
            gaps.add("responsibility_semantics_evidence_missing")
            continue
        context = (receipt_contexts or {}).get(receipt.receipt_id)
        if context is None or not (context.receipt_store_repository_root or context.receipt_store_output_directory):
            gaps.add("responsibility_native_binding_invalid")
        if receipt.receipt_id not in receipt_reviews:
            receipt_reviews[receipt.receipt_id] = verify_evidence_receipt(receipt, context, read_context=read_context)
        verification = receipt_reviews[receipt.receipt_id]
        if not verification.current or not verification.eligible or receipt.fingerprint != proof.owner_receipt_fingerprint or receipt.producer_id != f"validation-owner:{proof.owner_id}" or receipt.subject_id != f"validation-owner:{proof.owner_id}" or receipt.exit_code != 0 or receipt.result_status != "pass" or receipt.blockers or receipt.skipped_checks or native_binding.owner_id != proof.owner_id or native_binding.evidence_scope != required_evidence_scope or set(native_binding.native_case_ids) != set(proof.source_case_ids):
            gaps.add("responsibility_native_binding_invalid")
        if contract is not None and not set(contract.relation_code_obligation_ids) <= set(receipt.covered_obligations):
            gaps.add("responsibility_native_binding_invalid")
        rows = [rows_by_key[key] for key in ((proof.owner_id, case) for case in proof.source_case_ids) if key in rows_by_key]
        native = [contract_by_key[key] for key in ((proof.owner_id, case) for case in proof.source_case_ids) if key in contract_by_key]
        if len(rows) != len(proof.source_case_ids) or len(native) != len(rows) or raw_artifact_root is None:
            gaps.add("responsibility_native_binding_invalid")
            continue
        row_key = tuple((row.owner_id, row.source_case_id) for row in rows)
        if row_key not in native_reviews:
            native_reviews[row_key] = verify_native_model_cases(native, rows, raw_artifact_root=raw_artifact_root, read_context=read_context)
        if native_binding.fingerprint not in binding_reviews:
            binding_reviews[native_binding.fingerprint] = verify_native_case_bindings((native_binding,), rows)
        a = native_reviews[row_key]
        b = binding_reviews[native_binding.fingerprint]
        if not a.ok or not b.ok:
            gaps.add("responsibility_native_binding_invalid")
        semantic_dimension = next(k for k, values in ARCHITECTURE_HARD_DIMENSION_PROJECTION.items() if proof.hard_dimension_id in values)
        if semantic_dimension not in oracle.covered_dimensions or not set(fact.element_ids) <= set(oracle.covered_model_element_ids):
            gaps.add("responsibility_native_binding_invalid")
        for row in rows:
            key = (row.owner_id, row.source_case_id)
            identity = (current_native_identities or {}).get(key, {})
            identity_fields = {"input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint", "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint"}
            if set(identity) != identity_fields or any(getattr(row, name) != identity[name] for name in identity_fields) or proof.input_class_id not in (native_input_class_ids or {}).get(key, ()):
                gaps.add("responsibility_native_binding_invalid")
            oracle_content = dict(oracle.semantics).get(semantic_dimension)
            try:
                oracle_row = json.loads(oracle_content)
                if oracle_row.get("hard_dimensions", {}).get(proof.hard_dimension_id) != content.get(proof.hard_dimension_id) or proof.input_class_id not in oracle_row.get("input_class_ids", ()):
                    gaps.add("responsibility_native_binding_invalid")
            except (ValueError, TypeError):
                gaps.add("responsibility_native_binding_invalid")
            observation_key = key, receipt.receipt_id
            if observation_key not in observation_reviews:
                observation_reviews[observation_key] = (_receipt_binds_native_result(receipt, context, row, read_context=read_context)
                    and _responsibility_native_observation_matches(fact, row, raw_artifact_root, observed_fps, read_context=read_context))
            # The native execution and owner receipt have independently
            # defined environment schemas. Both must verify against their
            # own current identity and original proof; their hashes differ.
            if not any(x.get("oracle_member_id") == proof.oracle_id for x in row.oracle_results) or not observation_reviews[observation_key]:
                gaps.add("responsibility_native_binding_invalid")
        admitted.append(canonical_fingerprint(proof.to_dict()))
    if actual != expected:
        gaps.add("responsibility_semantics_evidence_missing")
    return _responsibility_semantic_review(fp, canonical_fingerprint(content), required_evidence_scope, tuple(sorted(gaps)), tuple(sorted(admitted)) if not gaps else (), tuple(contract.relation_ids) if contract is not None and not gaps else ())


def _responsibility_native_observation_matches(fact, result, root, observed_fps, *, read_context=None):
    """Join exact named hard checks and producer-observed source pins."""
    from pathlib import Path
    try:
        raw_root = Path(root).resolve()
        path = Path(result.raw_artifact_path)
        if not path.is_absolute():
            path = raw_root / path
        if path.is_symlink() or not path.resolve().is_relative_to(raw_root):
            return False
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate native observation key")
                value[key] = item
            return value
        raw = json.loads((read_context.artifact_bytes(path.absolute().relative_to(read_context.root).as_posix()).decode("utf-8") if read_context is not None else path.read_text(encoding="utf-8")), object_pairs_hook=unique,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        material = raw.get("architecture_material", {})
        source_rows = material.get("observed_source_inputs", ())
        pinned = {}
        for value in source_rows:
            value = _exact_object(value, ("path", "sha256"), "native observed source")
            if value["path"] in pinned:
                return False
            pinned[value["path"]] = value["sha256"]
        if not observed_fps or any(pinned.get(path) != fingerprint for path, fingerprint in observed_fps.items()):
            return False
        member = fact.owner_id + ":" + result.source_case_id + ":input"
        inputs = [row for row in result.oracle_results if row["dimension"] == "input" and row["oracle_member_id"] == member]
        if len(inputs) != 1 or inputs[0].get("ok") is not True:
            return False
        checks = inputs[0].get("observed", {}).get("semantic_checks")
        if not isinstance(checks, list):
            return False
        # Raw evidence must actually contain this same observed check set.
        pending, found = [raw], False
        while pending:
            value = pending.pop()
            if isinstance(value, Mapping):
                if value.get("semantic_checks") == checks:
                    found = True
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        if not found:
            return False
        expected = {(hard, context) for hard in HARD_SEMANTIC_DIMENSIONS for context in fact.applicable_input_class_ids}
        actual = set()
        for value in checks:
            value = _exact_object(value, ("check_id", "responsibility_id", "hard_dimension_id", "input_class_id", "args", "observed", "expected", "status"), "native semantic check")
            if value["responsibility_id"] != fact.responsibility_id:
                continue
            key = (value["hard_dimension_id"], value["input_class_id"])
            check_id = "semantic-check:" + fact.responsibility_id + ":" + key[0] + ":" + key[1]
            if key not in expected or key in actual or value["check_id"] != check_id or value["status"] != "pass" or value["expected"] != fact.hard_semantics[key[0]]:
                return False
            if any(not isinstance(value[name], Mapping) or not value[name] for name in ("args", "observed")):
                return False
            actual.add(key)
        return actual == expected
    except (OSError, TypeError, ValueError, KeyError, AttributeError):
        return False


def derive_architecture_relation_candidates(responsibilities, *, semantic_reviews=(), licensed_adapter_pairs=(), canonical_relation_handoffs=(), objectives=()):
    """Index finite admitted contexts; retain conflicts without a Cartesian scan."""
    if tuple(licensed_adapter_pairs) or tuple(canonical_relation_handoffs):
        raise ValueError("architecture_handoff_evidence_unknown: independent current handoff verification is required")
    reviews = {x.responsibility_fingerprint: x for x in semantic_reviews}
    ready, context_index, related_index, variant_index = {}, {}, {}, {}
    gaps, relations, findings, rewrites = set(), {}, set(), {}
    fingerprints, declarations = {}, {}
    for value in responsibilities:
        row = value if isinstance(value, ArchitectureResponsibilityFact) else ArchitectureResponsibilityFact.from_dict(value)
        identifier = row.responsibility_id
        if identifier in fingerprints:
            if declarations[identifier] != row:
                raise ValueError("duplicate or conflicting responsibility identity: " + identifier)
            continue
        fingerprint = canonical_fingerprint(row.to_dict())
        fingerprints[identifier] = fingerprint
        declarations[identifier] = row
        review = reviews.get(fingerprint)
        if review is None or not review.ready:
            gaps.add("responsibility_semantics_evidence_missing:" + identifier)
            continue
        ready[identifier] = row
        semantic = review.semantic_content_fingerprint
        variant_index.setdefault((row.boundary_id, row.mechanism_id, semantic), []).append(identifier)
        for context in row.applicable_input_class_ids:
            context_index.setdefault((context, semantic), []).append(identifier)
            related_index.setdefault(("cohort", row.boundary_id, row.mechanism_id, context), []).append(identifier)
            for relation in review.admitted_relation_ids:
                related_index.setdefault(("relation", relation, context), []).append(identifier)

    def add_pair(left_id, right_id, kind, semantic=""):
        pair = tuple(sorted((left_id, right_id)))
        if pair[0] == pair[1] or (kind, pair) in relations:
            return
        left, right = (ready[key] for key in pair)
        overlap = set(left.applicable_input_class_ids) & set(right.applicable_input_class_ids)
        if kind == "duplicate_boundary":
            if left.owner_code_contract_id == right.owner_code_contract_id:
                return
            if any(reviews[fingerprints[key]].evidence_scope != "implementation_boundary" for key in pair):
                gaps.add("responsibility_semantics_evidence_missing:" + ":".join(pair))
                return
        remaining = [{"responsibility_id": row.responsibility_id,
                      "input_class_ids": sorted(set(row.applicable_input_class_ids) - overlap)}
                     for row in (left, right)]
        relation_id = "architecture-relation:" + kind + ":" + canonical_fingerprint(pair)[-16:]
        result = {"relation_id": relation_id, "kind": kind, "responsibility_ids": list(pair),
                  "element_ids": sorted(set(left.element_ids) | set(right.element_ids)),
                  "input_class_ids": sorted(overlap), "remaining_contexts": remaining}
        if kind == "false_friend":
            result["hard_mismatch_ids"] = sorted(key for key in HARD_SEMANTIC_DIMENSIONS
                                               if left.hard_semantics[key] != right.hard_semantics[key])
        else:
            result["semantic_content_fingerprint"] = semantic
        relations[(kind, pair)] = result
        if kind == "duplicate_boundary":
            findings.add("equivalent_responsibility_paths:" + ":".join(pair))
            rewrites[pair] = {"rewrite_rule_id": "share-primary:" + relation_id,
                              "responsibility_ids": list(pair), "owner_ids": sorted({left.owner_id, right.owner_id}),
                              "applicable_input_class_ids": sorted(overlap), "remaining_contexts": remaining,
                              "lane": "normative_target"}

    for (_, semantic), members in sorted(context_index.items()):
        by_contract = {}
        for identifier in sorted(set(members)):
            by_contract.setdefault(ready[identifier].owner_code_contract_id, identifier)
        selected = sorted(by_contract.values())
        if selected:
            for identifier in selected[1:]:
                add_pair(selected[0], identifier, "duplicate_boundary", semantic)
    for (_, _, semantic), members in sorted(variant_index.items()):
        ordered = sorted(set(members))
        if ordered:
            primary = ordered[0]
            for identifier in ordered[1:]:
                if not set(ready[primary].applicable_input_class_ids) & set(ready[identifier].applicable_input_class_ids):
                    add_pair(primary, identifier, "legitimate_variant", semantic)
    for members in related_index.values():
        ordered = sorted(set(members))
        if ordered:
            primary = ordered[0]
            for identifier in ordered[1:]:
                if dict(ready[primary].hard_semantics) != dict(ready[identifier].hard_semantics):
                    add_pair(primary, identifier, "false_friend")
    from .model_intent import BoundArchitectureObjective
    for bound in objectives:
        if not isinstance(bound, BoundArchitectureObjective):
            raise ValueError("architecture objective requires independently bound source")
        objective = bound.objective
        if objective.constraint_kind != "shared_mechanism":
            continue
        primary_ids = sorted(key for key, row in ready.items()
                             if row.owner_code_contract_id == objective.constraint_values["canonical_owner_code_contract_id"])
        if primary_ids:
            primary = primary_ids[0]
            for identifier in objective.responsibility_ids:
                if identifier in ready and set(ready[primary].applicable_input_class_ids) & set(ready[identifier].applicable_input_class_ids) and dict(ready[primary].hard_semantics) != dict(ready[identifier].hard_semantics):
                    add_pair(primary, identifier, "false_friend")
    return {"relations": [relations[key] for key in sorted(relations)],
            "finding_ids": sorted(findings), "rewrite_candidates": [rewrites[key] for key in sorted(rewrites)],
            "observation_gap_ids": sorted(gaps)}


def evaluate_architecture_objectives(objectives, responsibilities, *, code_contracts=(), current_delegation_relation_ids=(), delegation_evidence_bindings=None, measurements=None, measurement_evidence=None, binding_report=None, implementation_inventory=None, semantic_reviews=(), native_materials=None, current_source_fingerprints=None, effective_intent_view=None, root=None, read_context=None):
    """Finite normative direction; never rewrite faithful observed graph facts."""
    from .model_intent import BoundArchitectureObjective
    facts = {x.responsibility_id: x for x in responsibilities}
    contracts = {x.code_contract_id: x for x in code_contracts}
    gaps, improvements, suggestions, satisfied, missing_inputs = set(), set(), [], [], []
    for bound in objectives:
        if not isinstance(bound, BoundArchitectureObjective):
            raise ValueError("architecture objective requires independently bound source")
        obj = bound.objective
        scoped = [facts[x] for x in obj.responsibility_ids if x in facts]
        if len(scoped) != len(obj.responsibility_ids) or not set(obj.model_ids) <= {x.model_id for x in facts.values()} or any(not set(obj.applicable_input_class_ids) <= set(x.applicable_input_class_ids) for x in scoped):
            gaps.add(f"architecture_objective_scope_unknown:{obj.objective_id}")
            continue
        values = obj.constraint_values
        action = ""
        if obj.constraint_kind == "unique_owner":
            violated = any(x.owner_id != values["owner_id"] for x in scoped)
            action = "assign_required_owner"
        elif obj.constraint_kind == "allowed_layers":
            violated = any(x.layer_id not in values["layer_ids"] for x in scoped)
            action = "relocate_responsibility"
        elif obj.constraint_kind == "shared_mechanism":
            primary = contracts.get(values["canonical_owner_code_contract_id"])
            verified = dict(delegation_evidence_bindings or {})
            required_relations = set(values["required_delegation_relation_ids"])
            primary_rows = [x for x in facts.values() if x.owner_code_contract_id == values["canonical_owner_code_contract_id"] and x.mechanism_id == values["canonical_mechanism_id"] and x.mechanism_fingerprint == values["mechanism_fingerprint"]]
            violated = primary is None or not primary_rows or primary.delegates_to_code_contract_id != "" or not required_relations <= set(current_delegation_relation_ids)
            for fact in scoped:
                contract = contracts.get(fact.owner_code_contract_id)
                proofs = verified.get(fact.responsibility_id, ())
                # Booleans or same caller hashes are never receipt admission.
                verified_relations = {relation for relation, review in proofs if isinstance(review, ResponsibilitySemanticEvidenceReview) and review.ready and review.evidence_scope == "implementation_boundary" and review.responsibility_fingerprint == canonical_fingerprint(fact.to_dict()) and relation in review.admitted_relation_ids}
                violated |= contract is None or contract.delegates_to_code_contract_id != values["canonical_owner_code_contract_id"] or not contract.delegation_only or contract.independent_business_authority or bool(contract.state_writes or contract.side_effects) or not (set(contract.relation_ids) & required_relations) <= verified_relations or not (set(contract.relation_ids) & required_relations)
            action = "delegate_to_canonical_primary"
        elif obj.constraint_kind == "functional_obligations":
            missing, violated = _functional_objective_evidence(bound, scoped, contracts,
                binding_report=binding_report, implementation_inventory=implementation_inventory,
                semantic_reviews=semantic_reviews, native_materials=native_materials,
                current_source_fingerprints=current_source_fingerprints,
                effective_intent_view=effective_intent_view, root=root, read_context=read_context)
            if missing:
                missing_inputs.extend(missing)
                gaps.update("functional_objective_evidence_missing:" + obj.objective_id + ":" + row["reference_id"] for row in missing)
                continue
            action = "satisfy_required_functional_obligations"
        else:
            # A semantic review proves behavior, not a measurement value/unit.
            # PathCostVector validates data shape but supplies no independent
            # measurement admission. Retain explicit goals as unknown until
            # that evidence boundary exists; never accept scalar self-attestation.
            gaps.add(f"cost_measurement_missing:{obj.objective_id}")
            continue
        if violated:
            if obj.required:
                improvements.add(f"required_architecture_objective_unmet:{obj.objective_id}")
            suggestions.append({"objective_id": obj.objective_id, "responsibility_ids": list(obj.responsibility_ids), "owner_id": obj.native_owner_id, "action": action, "lane": "normative_target", "source_ref": bound.source_ref, "source_fingerprint": bound.source_fingerprint})
        else:
            satisfied.append(obj.objective_id)
    return {"observation_gap_ids": sorted(gaps), "improvement_gap_ids": sorted(improvements), "suggestions": suggestions, "satisfied_objective_ids": sorted(satisfied), "architecture_objective_status": "no_declared_architecture_objective" if not objectives else "blocked" if gaps or improvements else "satisfied", "missing_inputs": sorted(missing_inputs, key=canonical_json)}


def _functional_objective_evidence(bound, scoped, contracts, *, binding_report, implementation_inventory,
                                   semantic_reviews, native_materials, current_source_fingerprints,
                                   effective_intent_view, root, read_context=None):
    """Authenticate current function targets independently of native pass status."""
    from .model_intent_authority import CurrentEffectiveIntentView
    from .implementation_blueprint import review_model_implementation_bindings
    from .implementation_inventory import review_implementation_surface_inventory
    goal, missing = bound.objective, []
    def need(kind, reference, owner=goal.native_owner_id):
        missing.append(_missing_input(kind, reference, next_owner_id=owner))
    contribution = None
    if isinstance(effective_intent_view, CurrentEffectiveIntentView) and effective_intent_view.fingerprint == bound.effective_intent_view_fingerprint:
        contribution = next((row for row in effective_intent_view.active_contributions if row.contribution_id == bound.contribution_id), None)
        identity = next((row for row in effective_intent_view.verified_source_identities if row.contribution_id == bound.contribution_id), None)
        if contribution is None or identity is None or identity.fingerprint != bound.source_identity_fingerprint or identity.source_fingerprint != bound.source_fingerprint or identity.source_ref != bound.source_ref:
            contribution = None
        elif identity.authority_kind == "project_file" and root is not None:
            from pathlib import Path
            from .source_identity import assert_current_source_path, source_file_fingerprint
            from .model_intent import ArchitectureObjectiveSource
            try:
                relative = assert_current_source_path(identity.resolved_project_ref or identity.source_ref)
                source_root = Path(root).resolve()
                path = source_root / relative
                if path.is_symlink() or not path.resolve().is_relative_to(source_root) or source_file_fingerprint(path) != identity.source_fingerprint:
                    raise ValueError("functional target source is not current")
                source = ArchitectureObjectiveSource.from_source_bytes(path.read_bytes())
                original = [row for row in source.objectives if row.objective_id == goal.objective_id]
                if len(original) != 1 or original[0].to_dict() != goal.to_dict():
                    raise ValueError("functional target differs from original source")
            except (OSError, ValueError, TypeError):
                contribution = None
        else:
            # A copied bound record does not license a new target. WorkContext
            # providers must supply their original-source consumer boundary.
            contribution = None
    required = set(goal.constraint_values["required_obligation_ids"])
    if contribution is None or goal.objective_id not in contribution.target_invariant_ids or not required <= set(contribution.target_obligation_ids):
        need("objective_source", goal.objective_id)
    if binding_report is None or implementation_inventory is None:
        need("model_binding", goal.objective_id)
    else:
        inventory_review = review_implementation_surface_inventory(implementation_inventory, root=root)
        repeated = review_model_implementation_bindings(implementation_inventory,
            required_model_element_ids=binding_report.required_model_element_ids, bindings=binding_report.bindings,
            semantic_specs=binding_report.semantic_specs, oracles=binding_report.oracles)
        if not inventory_review.ok or not repeated.ok or repeated.fingerprint != binding_report.fingerprint:
            need("model_binding", goal.objective_id)
    reviews = {row.responsibility_fingerprint: row for row in semantic_reviews}
    available, retained = set(), set()
    for fact in scoped:
        code = contracts.get(fact.owner_code_contract_id)
        review = reviews.get(canonical_fingerprint(fact.to_dict()))
        if review is None or not review.ready or review.evidence_scope != "implementation_boundary":
            need("semantic_source", fact.responsibility_id, fact.owner_id)
        bindings = [row for row in getattr(binding_report, "bindings", ()) if row.fingerprint == fact.implementation_binding_fingerprint]
        if code is None or canonical_fingerprint(code.to_dict()) != fact.owner_code_contract_fingerprint or len(bindings) != 1:
            need("model_binding", fact.owner_code_contract_id, fact.owner_id)
            continue
        binding = bindings[0]
        if binding.owner_contract_id != code.code_contract_id or binding.implementation_owner_id != fact.owner_id or binding.model_element_id not in fact.element_ids or (current_source_fingerprints or {}).get(code.path) != binding.implementation_content_fingerprint:
            need("current_source", code.path or code.code_contract_id, fact.owner_id)
            continue
        available.add(code.code_contract_id)
        retained.update(set(code.implements_obligations) & set(binding.model_obligation_ids))
        if not required & set(code.implements_obligations) <= set(code.relation_code_obligation_ids):
            need("model_binding", code.code_contract_id, fact.owner_id)
    for identifier in set(goal.constraint_values["required_code_contract_ids"]) - available:
        need("model_binding", identifier)
    for identifier in required - retained:
        need("outcome_binding", identifier)
    material = dict(native_materials or {})
    allowed = {"native_contracts", "native_bindings", "native_results", "receipts", "receipt_contexts", "raw_artifact_root", "current_native_identities"}
    if set(material) - allowed:
        raise ValueError("unknown functional objective native material")
    # A goal requires its declared cases, not every other owner's unrelated
    # obligations. Keep each selected original binding intact so its complete
    # member matrix, original result and receipt still undergo strict checks.
    required_pairs = {(row["owner_id"], row["source_case_id"])
                      for row in goal.constraint_values["native_case_pairs"]}
    material["native_bindings"] = tuple(binding for binding in material.get("native_bindings", ())
        if any((binding.owner_id, case) in required_pairs for case in binding.native_case_ids))
    refs, native_missing = verify_architecture_native_case_refs(**material, required_obligation_ids=tuple(sorted(required)), read_context=read_context)
    missing.extend(native_missing)
    admitted = {(row["owner_id"], row["source_case_id"]): row for row in refs}
    results = {(row.owner_id, row.source_case_id): row for row in material.get("native_results", ())}
    violated = False
    for pair in goal.constraint_values["native_case_pairs"]:
        key = pair["owner_id"], pair["source_case_id"]
        if key not in admitted or key not in results:
            need("native_result", pair["source_case_id"], pair["owner_id"])
        else:
            violated |= results[key].observed_status != pair["satisfied_observed_status"]
    return tuple({canonical_json(row): row for row in missing}[key] for key in sorted({canonical_json(row) for row in missing})), violated

@dataclass(frozen=True)
class PathQualityArchitectureDetail(_CanonicalRecord):
    body: Mapping[str, Any]
    schema: str = PATH_QUALITY_ARCHITECTURE_DETAIL_SCHEMA

    def __post_init__(self):
        if self.schema != PATH_QUALITY_ARCHITECTURE_DETAIL_SCHEMA or not isinstance(self.body, Mapping):
            raise ValueError("architecture detail schema/body invalid")
        common = {"mode", "subject_fingerprint", "trigger_ids", "trigger_evidence", "trigger_currentness_id", "unresolved_ids"}
        light = common | {"model_facts", "retained_elements", "witness_fingerprints", "finding_ids", "measured_costs", "cost_thresholds", "cost_evidence"}
        deep = common | {"comparison_boundary_id", "baseline_candidate_id", "required_cost_dimensions", "active_obligation_ids", "candidate_set_exhausted", "expected_candidate_ids", "candidate_exhaustion_evidence_fingerprint", "candidate_exhaustion_currentness_id", "candidates", "rewrite_rule_ids", "rewrite_dispositions", "rewrite_evidence", "rewrite_set_exhausted", "rewrite_currentness_id", "choice_required", "conclusion", "selected_candidate_id"}
        expected = light if self.body.get("mode") == "lightweight" else deep if self.body.get("mode") == "deep" else set()
        if not expected or set(self.body) != expected:
            raise ValueError("architecture detail body fields must be exact for review mode")
        _validate_json_value(self.body, "architecture detail body")
        _require_fingerprint(self.body["subject_fingerprint"], "subject_fingerprint")
        if "model_facts" in self.body:
            architecture = self.body["model_facts"].get("architecture")
            if architecture is not None:
                allowed = {"schema", "declared_source_fingerprint", "effective_intent_view_fingerprint", "objective_refs", "responsibilities", "semantic_evidence_bindings", "relations", "finding_ids", "suggestions", "observation_gap_ids", "improvement_gap_ids", "facts_scope", "scope_coverage", "source_refs", "improvement_pointers", "scope_evidence"}
                if not isinstance(architecture, Mapping) or set(architecture) - allowed:
                    raise ValueError("architecture detail contains unknown architecture fields")
                for name in ("declared_source_fingerprint", "effective_intent_view_fingerprint"):
                    if name in architecture: _require_fingerprint(architecture[name], name)
                for raw in architecture.get("responsibilities", ()):
                    ArchitectureResponsibilityFact.from_dict(raw)
                for raw in architecture.get("semantic_evidence_bindings", ()):
                    ResponsibilitySemanticEvidenceBinding.from_dict(raw)
                for raw in architecture.get("improvement_pointers", ()):
                    ArchitectureImprovementPointer.from_dict(raw)
                if architecture.get("scope_evidence") is not None:
                    validate_architecture_scope_evidence_shape(architecture["scope_evidence"])
        object.__setattr__(self, "body", _json_copy(self.body))

    def identity_payload(self):
        return {"schema": self.schema, "body": self.body}

    @classmethod
    def from_dict(cls, value):
        row = _exact_object(value, ("schema", "body", "fingerprint"), "architecture detail")
        result = cls(row["body"], row["schema"])
        if row["fingerprint"] != result.fingerprint:
            raise ValueError("architecture_detail_identity_mismatch")
        return result

    def binding_errors(self, subject, result):
        gaps = set()
        if self.fingerprint != result.detail_evidence_fingerprint or self.body["subject_fingerprint"] != subject.fingerprint or result.subject_fingerprint != subject.fingerprint or result.currentness_id != subject.currentness_id or self.body["mode"] != result.mode or tuple(self.body["unresolved_ids"]) != result.unresolved_ids:
            gaps.add("architecture_detail_identity_mismatch")
        if self.body["mode"] == "lightweight":
            facts = self.body["model_facts"]
            architecture = facts.get("architecture", {})
            if normalized_model_facts_fingerprint(facts) != subject.normalized_facts_fingerprint or canonical_fingerprint(self.body["retained_elements"]) != subject.retained_element_inventory_fingerprint or tuple(self.body["finding_ids"]) != result.finding_ids:
                gaps.add("architecture_detail_identity_mismatch")
            if architecture.get("effective_intent_view_fingerprint", subject.intent_fingerprint) != subject.intent_fingerprint:
                gaps.add("effective_intent_identity_mismatch")
            for pointer in architecture.get("improvement_pointers", ()):
                observed = pointer["observed_subject_fingerprints"]
                if subject.model_id in pointer["model_ids"] and observed.get(subject.model_id) != subject.fingerprint:
                    gaps.add("architecture_pointer_subject_identity_mismatch")
            scope = architecture.get("scope_evidence")
            if scope is not None and scope["subject_fingerprint"] != subject.fingerprint:
                gaps.add("architecture_scope_subject_identity_mismatch")
        return tuple(sorted(gaps))


_NATIVE_REF_FIELDS = (
    "owner_id", "source_case_id", "callable_ref", "result_selector", "oracle_member_ids",
    "contract_fingerprint", "native_case_binding_fingerprint", "blueprint_case_id",
    "blueprint_source_case_id", "mapping_fingerprint", "result_artifact_fingerprint",
    "owner_receipt_id", "owner_receipt_fingerprint", "input_fingerprint", "model_fingerprint",
    "code_fingerprint", "test_fingerprint", "oracle_fingerprint", "toolchain_fingerprint",
    "environment_fingerprint",
)
_MISSING_INPUT_KINDS = frozenset(("semantic_source", "context_proof", "model_binding", "native_contract", "native_binding", "native_result", "owner_receipt", "current_source", "objective_source", "boundary_manifest", "outcome_binding", "compromise_source"))


def _canonical_object_rows(values, names, label):
    rows = [_exact_object(value, names, label) for value in values]
    identities = [canonical_json(row) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError(f"duplicate {label}")
    return tuple(rows[index] for index in sorted(range(len(rows)), key=identities.__getitem__))


@dataclass(frozen=True)
class ArchitectureActionTarget:
    """A current, finite code location; it is never execution authority."""

    operation: str
    path: str
    symbol: str
    source_fingerprint: str
    code_contract_id: str
    code_contract_fingerprint: str
    surface_id: str
    owner_id: str
    requires_owner_admission: bool
    retained_obligation_ids: tuple[str, ...]

    def __post_init__(self):
        if self.operation not in {"review_shared_mechanism", "supply_evidence", "repair_goal_source", "add_model_obligation", "revisit_compromise"}:
            raise ValueError("architecture action operation invalid")
        ref = _source_ref_dict({"path": self.path, "source_fingerprint": self.source_fingerprint})
        if ref["path"] != self.path:
            raise ValueError("architecture action path must be canonical")
        _require_string(self.symbol, "architecture action symbol")
        for name in ("code_contract_id", "code_contract_fingerprint", "surface_id", "owner_id"):
            if not isinstance(getattr(self, name), str):
                raise ValueError("architecture action optional identity must be a string")
        if bool(self.code_contract_id) != bool(self.code_contract_fingerprint):
            raise ValueError("architecture action contract identity incomplete")
        if self.code_contract_id:
            _require_fingerprint(self.code_contract_fingerprint, "architecture action contract")
            _require_string(self.surface_id, "architecture action surface")
        elif self.operation not in {"add_model_obligation", "repair_goal_source"}:
            raise ValueError("architecture action requires a current code contract")
        if self.operation == "add_model_obligation":
            _require_string(self.surface_id, "unbound architecture action surface")
        _require_bool(self.requires_owner_admission, "requires_owner_admission")
        if self.requires_owner_admission != (self.owner_id == ""):
            raise ValueError("architecture action unknown owner admission must be explicit")
        if self.code_contract_id and not self.owner_id:
            raise ValueError("bound architecture action owner missing")
        object.__setattr__(self, "retained_obligation_ids", _canonical_ids(self.retained_obligation_ids, "action retained obligations"))

    def to_dict(self):
        return {f.name: list(getattr(self, f.name)) if f.name == "retained_obligation_ids" else getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, value):
        return cls(**_exact_object(value, (f.name for f in fields(cls)), "architecture action target"))


@dataclass(frozen=True)
class ArchitectureImprovementPointer(_CanonicalRecord):
    """A strict action reference, never a receipt or an acceptance authority."""

    pointer_id: str
    kind: str
    status: str
    lane: str
    model_ids: tuple[str, ...]
    responsibility_ids: tuple[str, ...]
    affected_element_ids: tuple[str, ...]
    applicable_input_class_ids: tuple[str, ...]
    remaining_contexts: tuple[Mapping[str, Any], ...]
    observed_subject_fingerprints: Mapping[str, str]
    source_refs: tuple[Mapping[str, str], ...]
    objective_refs: tuple[Mapping[str, Any], ...]
    retained_obligation_ids: tuple[str, ...]
    native_case_refs: tuple[Mapping[str, Any], ...]
    missing_input_refs: tuple[Mapping[str, str], ...]
    next_owner_ids: tuple[str, ...]
    revisit_triggers: tuple[Mapping[str, str], ...]
    action_targets: tuple[ArchitectureActionTarget, ...] = ()

    def __post_init__(self):
        if self.kind not in {"duplicate_candidate", "goal_mismatch", "model_gap", "temporary_compromise"} or self.status not in {"candidate", "needs_evidence", "deferred"} or self.lane != "normative_target":
            raise ValueError("architecture pointer kind/status/lane invalid")
        for name in ("model_ids", "responsibility_ids", "affected_element_ids", "applicable_input_class_ids", "retained_obligation_ids", "next_owner_ids"):
            object.__setattr__(self, name, _canonical_ids(getattr(self, name), name))
        if not self.model_ids:
            raise ValueError("architecture pointer must name its actual model")
        contexts = _canonical_object_rows(self.remaining_contexts, ("responsibility_id", "input_class_ids"), "remaining context")
        if len({row["responsibility_id"] for row in contexts}) != len(contexts):
            raise ValueError("duplicate remaining responsibility context")
        for row in contexts:
            _require_string(row["responsibility_id"], "responsibility_id")
            row["input_class_ids"] = list(_canonical_ids(row["input_class_ids"], "input class ids"))
            if row["responsibility_id"] not in self.responsibility_ids or set(row["input_class_ids"]) & set(self.applicable_input_class_ids):
                raise ValueError("remaining context is outside responsibility or overlaps candidate")
        object.__setattr__(self, "remaining_contexts", contexts)
        if not isinstance(self.observed_subject_fingerprints, Mapping) or set(self.observed_subject_fingerprints) - set(self.model_ids):
            raise ValueError("observed subjects must identify pointer models")
        for value in self.observed_subject_fingerprints.values():
            _require_fingerprint(value, "observed subject")
        object.__setattr__(self, "observed_subject_fingerprints", dict(sorted(self.observed_subject_fingerprints.items())))
        if self.status != "needs_evidence" and set(self.observed_subject_fingerprints) != set(self.model_ids):
            raise ValueError("qualified architecture pointer requires every current subject")
        refs = tuple(_source_ref_dict(value) for value in self.source_refs)
        if len({row["path"] for row in refs}) != len(refs):
            raise ValueError("duplicate pointer source ref")
        object.__setattr__(self, "source_refs", tuple(sorted(refs, key=lambda row: row["path"])))
        from .model_intent import ArchitectureObjective, BoundArchitectureObjective
        objectives = []
        for value in self.objective_refs:
            row = _exact_object(value, (f.name for f in fields(BoundArchitectureObjective)), "bound objective")
            bound = BoundArchitectureObjective(ArchitectureObjective.from_dict(row.pop("objective")), **row)
            objectives.append(bound.to_dict())
        object.__setattr__(self, "objective_refs", tuple(sorted(objectives, key=canonical_json)))
        natives = _canonical_object_rows(self.native_case_refs, _NATIVE_REF_FIELDS, "native case ref")
        for row in natives:
            for name, value in row.items():
                if name == "oracle_member_ids":
                    row[name] = list(_canonical_ids(value, name))
                    if not row[name]: raise ValueError("native oracle members missing")
                elif name.endswith("fingerprint"):
                    _require_fingerprint(value, name, optional=name == "mapping_fingerprint")
                else:
                    _require_string(value, name)
        object.__setattr__(self, "native_case_refs", natives)
        missing = _canonical_object_rows(self.missing_input_refs, ("kind", "model_id", "responsibility_id", "reference_id", "next_owner_id"), "missing input")
        for row in missing:
            if row["kind"] not in _MISSING_INPUT_KINDS or any(not isinstance(value, str) for value in row.values()) or not row["reference_id"]:
                raise ValueError("missing input kind/reference invalid")
        if missing and self.status != "needs_evidence":
            raise ValueError("missing evidence cannot yield a qualified pointer")
        object.__setattr__(self, "missing_input_refs", missing)
        triggers = _canonical_object_rows(self.revisit_triggers, ("trigger_id", "source_ref", "source_fingerprint", "condition_ref"), "revisit trigger")
        for row in triggers:
            for name in ("trigger_id", "source_ref", "condition_ref"): _require_string(row[name], name)
            _require_fingerprint(row["source_fingerprint"], "trigger source")
        object.__setattr__(self, "revisit_triggers", triggers)
        targets = tuple(row if isinstance(row, ArchitectureActionTarget) else ArchitectureActionTarget.from_dict(row) for row in self.action_targets)
        wires = [row.to_dict() for row in targets]
        identities = [canonical_json(row) for row in wires]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate architecture action target")
        refs_by_path = {row["path"]: row["source_fingerprint"] for row in self.source_refs}
        for target in targets:
            if refs_by_path.get(target.path) != target.source_fingerprint or not set(target.retained_obligation_ids) <= set(self.retained_obligation_ids):
                raise ValueError("architecture action target source or retained obligations differ")
            if target.owner_id and target.owner_id not in self.next_owner_ids:
                raise ValueError("architecture action target owner differs")
        object.__setattr__(self, "action_targets", tuple(targets[index] for index in sorted(range(len(targets)), key=identities.__getitem__)))
        expected = "architecture-pointer:" + canonical_fingerprint({f.name: [row.to_dict() for row in self.action_targets] if f.name == "action_targets" else _json_copy(getattr(self, f.name)) for f in fields(self) if f.name != "pointer_id"})[7:]
        if not self.pointer_id:
            object.__setattr__(self, "pointer_id", expected)
        elif self.pointer_id != expected:
            raise ValueError("architecture_pointer_identity_mismatch")

    def identity_payload(self):
        return {f.name: [row.to_dict() for row in self.action_targets] if f.name == "action_targets" else _json_copy(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, value):
        row = _exact_object(value, {f.name for f in fields(cls)} | {"fingerprint"}, "architecture improvement pointer")
        fingerprint = row.pop("fingerprint")
        _require_string(row["pointer_id"], "pointer_id")
        result = cls(**row)
        if result.fingerprint != fingerprint:
            raise ValueError("architecture_pointer_identity_mismatch")
        return result


def verify_architecture_action_targets(pointer, *, implementation_inventory=None, binding_report=None, code_contracts=(), current_source_fingerprints=None):
    """Recheck accepted locations against independent current scope; no reads."""
    pointer = pointer if isinstance(pointer, ArchitectureImprovementPointer) else ArchitectureImprovementPointer.from_dict(pointer)
    surfaces = {row.surface_id: row for row in getattr(implementation_inventory, "surfaces", ())}
    contracts = {row.code_contract_id: row for row in code_contracts}
    bindings = tuple(getattr(binding_report, "bindings", ()))
    current = dict(current_source_fingerprints or {})
    for target in pointer.action_targets:
        if current.get(target.path) != target.source_fingerprint:
            raise ValueError("architecture_action_target_source_stale")
        if target.operation == "repair_goal_source":
            goals = [row for row in pointer.objective_refs if row["source_ref"] == target.path and row["source_fingerprint"] == target.source_fingerprint and row["objective"]["objective_id"] == target.symbol and row["objective"]["native_owner_id"] == target.owner_id]
            if len(goals) != 1 or target.code_contract_id or target.surface_id:
                raise ValueError("architecture_action_target_goal_foreign")
            continue
        surface = surfaces.get(target.surface_id)
        if surface is None or (surface.path, surface.symbol, surface.content_fingerprint) != (target.path, target.symbol, target.source_fingerprint):
            raise ValueError("architecture_action_target_surface_foreign")
        if not target.code_contract_id:
            if target.operation != "add_model_obligation" or target.owner_id or not target.requires_owner_admission:
                raise ValueError("architecture_action_target_unbound_owner_invalid")
            continue
        matched = [row for row in bindings if row.implementation_surface_id == target.surface_id and row.owner_contract_id == target.code_contract_id and row.owner_contract_fingerprint == target.code_contract_fingerprint and row.implementation_owner_id == target.owner_id and row.implementation_content_fingerprint == target.source_fingerprint]
        if len(matched) != 1:
            raise ValueError("architecture_action_target_binding_foreign")
        obligations = set(matched[0].model_obligation_ids)
        contract = contracts.get(target.code_contract_id)
        if contract is not None:
            if (contract.path, contract.symbol, canonical_fingerprint(contract.to_dict())) != (target.path, target.symbol, target.code_contract_fingerprint):
                raise ValueError("architecture_action_target_contract_stale")
            obligations.update(contract.implements_obligations)
            obligations.update(contract.relation_code_obligation_ids)
        if not obligations <= set(target.retained_obligation_ids):
            raise ValueError("architecture_action_target_obligations_missing")
    return True


def _bound_architecture_action_target(fact, contract, bindings, inventory, current, operation):
    if contract is None or canonical_fingerprint(contract.to_dict()) != fact.owner_code_contract_fingerprint:
        return None
    matched = [row for row in bindings if row.fingerprint == fact.implementation_binding_fingerprint and row.implementation_owner_id == fact.owner_id and row.owner_contract_id == contract.code_contract_id and row.owner_contract_fingerprint == fact.owner_code_contract_fingerprint]
    if len(matched) != 1:
        return None
    binding = matched[0]
    surfaces = {row.surface_id: row for row in getattr(inventory, "surfaces", ())}
    surface = surfaces.get(binding.implementation_surface_id)
    if surface is None or (surface.path, surface.symbol, surface.content_fingerprint) != (contract.path, contract.symbol, binding.implementation_content_fingerprint) or current.get(contract.path) != surface.content_fingerprint:
        return None
    obligations = tuple(sorted(set(binding.model_obligation_ids) | set(contract.implements_obligations) | set(contract.relation_code_obligation_ids)))
    return ArchitectureActionTarget(operation, contract.path, contract.symbol, surface.content_fingerprint, contract.code_contract_id, fact.owner_code_contract_fingerprint, surface.surface_id, fact.owner_id, False, obligations)


def _missing_input(kind, reference_id, *, model_id="", responsibility_id="", next_owner_id=""):
    return {"kind": kind, "model_id": model_id, "responsibility_id": responsibility_id, "reference_id": reference_id, "next_owner_id": next_owner_id}


def _load_receipt_native_results(receipt, context, *, read_context=None):
    """Authenticate one original owner wrapper/envelope, preserving all rows."""
    from pathlib import Path
    base = context.receipt_store_output_directory
    relative = receipt.metadata.get("proof_relpath", "")
    if not base or not isinstance(relative, str) or not relative: return None
    root = Path(base).resolve()
    lexical = root / relative
    path = lexical.resolve()
    if lexical.is_symlink() or not path.is_relative_to(root) or not path.is_file(): return None
    try:
        raw = read_context.artifact_bytes(lexical.absolute().relative_to(read_context.root).as_posix()) if read_context is not None else path.read_bytes()
        if "sha256:" + hashlib.sha256(raw).hexdigest() != receipt.proof_artifact_fingerprint: return None
        proof = json.loads(raw)
        row = proof.get("child", {}).get("payload", {}).get("model_result", {})
        # Native fingerprints belong to the original producer's envelope;
        # receipt snapshots are owner-observation hashes, a different domain.
        native_fp = row.get("native_case_result_artifact_fingerprint")
        from .model_regressions import _load_native_case_result_artifact, _coerce_native_case_results, _native_result_rows_equal
        artifact = Path(row.get("native_case_result_artifact_path", ""))
        if not artifact.is_absolute(): artifact = Path(context.receipt_store_repository_root or base) / artifact
        owner = receipt.subject_id.removeprefix("validation-owner:")
        rows, _, artifact_fp, verification = _load_native_case_result_artifact(artifact, owner_id=owner, marker_case_ids=row.get("executed_case_ids", ()), read_context=read_context)
        declared = _coerce_native_case_results(row.get("native_case_results"), context="architecture owner receipt")
        if (row.get("model_id") not in {owner, owner.removeprefix("model:")}
                or native_fp != artifact_fp or not verification.ok or not _native_result_rows_equal(declared, rows)):
            return None
        return {"rows": {(item.owner_id, item.source_case_id): item for item in rows}, "input_fingerprint": row.get("input_inventory_fingerprint")}
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def _receipt_binds_native_result(receipt, context, result, *, read_context=None):
    """The single-row pure consumer; bulk callers share the loaded material."""
    material = _load_receipt_native_results(receipt, context, read_context=read_context)
    row = material["rows"].get((result.owner_id, result.source_case_id)) if material else None
    return bool(row is not None and row.to_dict() == result.to_dict() and material["input_fingerprint"] == result.input_fingerprint)


def verify_architecture_native_case_refs(*, native_contracts=(), native_bindings=(), native_results=(), receipts=(), receipt_contexts=None, raw_artifact_root=None, current_native_identities=None, required_obligation_ids=(), read_context=None):
    """Consume independently verified original native material; no producers."""
    from .native_case_protocol import verify_native_model_cases, verify_native_case_bindings
    from .evidence_receipts import verify_evidence_receipt
    native_contracts, native_bindings, native_results, receipts = map(tuple, (native_contracts, native_bindings, native_results, receipts))
    contracts = {(row.owner_id, row.source_case_id): row for row in native_contracts}
    results = {(row.owner_id, row.source_case_id): row for row in native_results}
    if len(contracts) != len(tuple(native_contracts)) or len(results) != len(tuple(native_results)):
        raise ValueError("duplicate native architecture evidence identity")
    refs, missing = [], []
    binding_reviews, receipt_reviews, receipt_material = {}, {}, {}
    for binding in native_bindings:
        binding_fp = binding.fingerprint
        if binding_fp not in binding_reviews:
            rows = tuple(results[(binding.owner_id, item)] for item in binding.native_case_ids if (binding.owner_id, item) in results)
            plans = tuple(contracts[(binding.owner_id, item)] for item in binding.native_case_ids if (binding.owner_id, item) in contracts)
            # Original receipt envelopes authenticate raw artifacts once below.
            # These two pure matrix checks apply once to the whole binding.
            binding_reviews[binding_fp] = (len(rows) == len(plans) == len(binding.native_case_ids)
                and verify_native_model_cases(plans, rows).ok and verify_native_case_bindings((binding,), rows).ok)
        for case in binding.native_case_ids:
            key = (binding.owner_id, case)
            contract, result = contracts.get(key), results.get(key)
            if contract is None or contract.case_kind == "aggregate":
                missing.append(_missing_input("native_contract", case, next_owner_id=binding.owner_id)); continue
            if result is None or raw_artifact_root is None:
                missing.append(_missing_input("native_result", case, next_owner_id=binding.owner_id)); continue
            identity = (current_native_identities or {}).get(key)
            names = {"input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint", "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint"}
            if not isinstance(identity, Mapping) or set(identity) != names or any(identity[name] != getattr(result, name) for name in names):
                missing.append(_missing_input("current_source", case, next_owner_id=binding.owner_id)); continue
            from pathlib import Path
            raw_root = Path(raw_artifact_root).resolve()
            raw_path = Path(result.raw_artifact_path)
            if not raw_path.is_absolute(): raw_path = raw_root / raw_path
            if not binding_reviews[binding_fp] or raw_path.is_symlink() or not raw_path.resolve().is_relative_to(raw_root):
                missing.append(_missing_input("native_result", case, next_owner_id=binding.owner_id)); continue
            eligible = []
            for receipt in receipts:
                context = (receipt_contexts or {}).get(receipt.receipt_id)
                if context is None or not (context.receipt_store_repository_root or context.receipt_store_output_directory): continue
                if receipt.producer_id != f"validation-owner:{binding.owner_id}" or receipt.subject_id != f"validation-owner:{binding.owner_id}": continue
                receipt_fp = receipt.fingerprint
                if receipt_fp not in receipt_reviews:
                    receipt_reviews[receipt_fp] = verify_evidence_receipt(receipt, context, read_context=read_context)
                    receipt_material[receipt_fp] = _load_receipt_native_results(receipt, context, read_context=read_context) if receipt_reviews[receipt_fp].current and receipt_reviews[receipt_fp].eligible else None
                verification = receipt_reviews[receipt_fp]
                original = receipt_material[receipt_fp]
                observed = original["rows"].get(key) if original else None
                if (verification.current and verification.eligible and receipt.result_status == "pass" and receipt.exit_code == 0 and not receipt.blockers and not receipt.skipped_checks
                        and observed is not None and observed.to_dict() == result.to_dict()
                        and original["input_fingerprint"] == result.input_fingerprint and set(required_obligation_ids) <= set(receipt.covered_obligations)):
                    eligible.append(receipt)
            if len(eligible) != 1:
                missing.append(_missing_input("owner_receipt", case, next_owner_id=binding.owner_id)); continue
            receipt = eligible[0]
            refs.append({"owner_id": contract.owner_id, "source_case_id": contract.source_case_id, "callable_ref": contract.callable_ref, "result_selector": contract.result_selector, "oracle_member_ids": sorted(contract.oracle_member_ids), "contract_fingerprint": contract.fingerprint,
                "native_case_binding_fingerprint": binding.fingerprint, "blueprint_case_id": binding.blueprint_case_id, "blueprint_source_case_id": binding.blueprint_source_case_id, "mapping_fingerprint": binding.mapping_fingerprint,
                "result_artifact_fingerprint": result.result_artifact_fingerprint, "owner_receipt_id": receipt.receipt_id, "owner_receipt_fingerprint": receipt.fingerprint, **{name: getattr(result, name) for name in sorted(names)}})
    return tuple(sorted(refs, key=canonical_json)), tuple({canonical_json(row): row for row in missing}[key] for key in sorted({canonical_json(row) for row in missing}))


def derive_architecture_model_gaps(source, *, implementation_inventory, binding_report, root=None):
    """Reverse an independent finite surface denominator into model gaps."""
    from .implementation_blueprint import review_model_implementation_bindings
    from .implementation_inventory import review_implementation_surface_inventory
    inventory_review = review_implementation_surface_inventory(implementation_inventory, root=root)
    repeated = review_model_implementation_bindings(implementation_inventory, required_model_element_ids=binding_report.required_model_element_ids, bindings=binding_report.bindings, semantic_specs=binding_report.semantic_specs, oracles=binding_report.oracles)
    bound = {row.implementation_surface_id for row in binding_report.bindings}
    surfaces = {row.surface_id: row for row in implementation_inventory.surfaces}
    gaps = []
    for surface_id in sorted(set(repeated.required_implementation_surface_ids) - bound):
        row = surfaces[surface_id]
        registered = [{"path": item.path, "source_fingerprint": item.content_fingerprint} for item in implementation_inventory.file_dispositions if item.path == row.path]
        gaps.append({"gap_id": "model_surface_unbound:" + surface_id, "model_id": source.model_id, "surface_id": surface_id, "affected_element_ids": [], "required_input": "model_obligation_for:" + surface_id, "owner_boundary": row.path + "#" + row.symbol, "next_owner_id": "", "affected_claim_scope": source.scope_coverage["claim_scope"], "source_refs": registered})
    declared_gaps = verify_declared_source_scope_coverage(source, implementation_inventory=implementation_inventory, binding_report=binding_report, root=root)
    if not inventory_review.ok or repeated.fingerprint != binding_report.fingerprint or declared_gaps:
        gaps.append({"gap_id": "model_coverage_evidence_invalid", "model_id": source.model_id, "surface_id": "", "affected_element_ids": [], "required_input": "current_inventory_and_reverse_bindings", "owner_boundary": implementation_inventory.boundary.boundary_id, "next_owner_id": "", "affected_claim_scope": source.scope_coverage["claim_scope"]})
    from .model_maturation import ModelMaturationSignal, MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION
    for gap in gaps:
        signal = ModelMaturationSignal(gap["gap_id"], MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION, model_id=source.model_id,
            required_input=gap["required_input"], owner_boundary=gap["owner_boundary"], affected_claim_scope=gap["affected_claim_scope"],
            evidence_fingerprint=implementation_inventory.fingerprint, description="The independent implementation denominator has no admitted model closure.",
            metadata={"implementation_inventory_fingerprint": implementation_inventory.fingerprint, "binding_report_fingerprint": binding_report.fingerprint})
        gap["maturation_signal"] = signal.to_dict()
    return tuple(gaps)


def parse_architecture_binding_report(value):
    """Strict current wire parser used by scope consumers; no freshness claim."""
    from .implementation_blueprint import ModelImplementationBindingReport, ModelImplementationBinding, SemanticSpecReference, OracleReference, BlueprintFinding, BLUEPRINT_SCHEMA_VERSION
    names = {f.name for f in fields(ModelImplementationBindingReport)} | {"schema_version", "implementation_surface_ids", "model_obligation_ids", "semantic_spec_ids", "oracle_ids", "test_evidence_ids"}
    row = _exact_object(value, names, "implementation binding report")
    if row["schema_version"] != BLUEPRINT_SCHEMA_VERSION: raise ValueError("binding report schema invalid")
    values = {f.name: row[f.name] for f in fields(ModelImplementationBindingReport)}
    for name, cls in (("bindings", ModelImplementationBinding), ("semantic_specs", SemanticSpecReference), ("oracles", OracleReference), ("findings", BlueprintFinding)):
        values[name] = tuple(cls(**_exact_object(raw, (f.name for f in fields(cls)), name)) for raw in row[name])
    result = ModelImplementationBindingReport(**values)
    if canonical_fingerprint(result.to_dict()) != canonical_fingerprint(row): raise ValueError("binding report derived identity mismatch")
    return result


def validate_architecture_scope_evidence_shape(value):
    """Validate exact frozen proof data, never authenticate receipts/freshness."""
    from .implementation_inventory import SoftwareBoundary, ImplementationSurfaceInventory
    from .portable_model import canonical_identity
    names = ("schema", "claim_boundary", "boundary", "inventory", "resolved_manifest_rows", "binding_report", "source_refs", "subject_fingerprint", "producer_owner_id", "producer_receipt_id", "producer_receipt_fingerprint", "producer_input_fingerprint")
    row = _exact_object(value, names, "architecture scope evidence")
    if row["schema"] != "flowguard.architecture_scope_evidence.v1" or row["claim_boundary"] != "complete_within_authenticated_frozen_boundary": raise ValueError("scope evidence schema/claim invalid")
    boundary = SoftwareBoundary.from_dict(row["boundary"])
    inventory = ImplementationSurfaceInventory.from_dict(row["inventory"])
    report = parse_architecture_binding_report(row["binding_report"])
    if boundary != inventory.boundary or report.inventory_fingerprint != inventory.fingerprint or report.inventory_id != inventory.inventory_id: raise ValueError("scope inventory identity mismatch")
    manifest = tuple(_exact_object(raw, ("path", "sha256"), "manifest row") for raw in row["resolved_manifest_rows"])
    if len({raw["path"] for raw in manifest}) != len(manifest) or list(manifest) != sorted(manifest, key=lambda raw: raw["path"]): raise ValueError("scope manifest must be exact canonical paths")
    for raw in manifest: _source_ref_dict({"path": raw["path"], "source_fingerprint": raw["sha256"]})
    if canonical_identity(list(manifest)) != inventory.manifest_fingerprint: raise ValueError("scope manifest identity mismatch")
    refs = tuple(_source_ref_dict(raw) for raw in row["source_refs"])
    if not refs or len({raw["path"] for raw in refs}) != len(refs): raise ValueError("scope source refs missing/duplicate")
    for name in ("subject_fingerprint", "producer_receipt_fingerprint", "producer_input_fingerprint"): _require_fingerprint(row[name], name)
    for name in ("producer_owner_id", "producer_receipt_id"): _require_string(row[name], name)
    return _json_copy(row)


def derive_architecture_improvement_pointers(*, responsibilities=(), subjects=(), objectives=(), relations=None, objective_evaluation=None, semantic_reviews=(), code_contracts=(), binding_report=None, native_materials=None, model_gaps=(), compromises=(), implementation_inventory=None, current_source_fingerprints=None, read_context=None):
    """Join finite current material into precise suggestions without executing it."""
    facts = {row.responsibility_id: row for row in responsibilities}
    subject_by_id = {row.model_id: row for row in subjects}
    reviews = {row.responsibility_fingerprint: row for row in semantic_reviews}
    contracts = {row.code_contract_id: row for row in code_contracts}
    objective_by_id = {row.objective.objective_id: row for row in objectives}
    material = dict(native_materials or {})
    allowed = {"native_contracts", "native_bindings", "native_results", "receipts", "receipt_contexts", "raw_artifact_root", "current_native_identities", "code_contracts"}
    if set(material) - allowed: raise ValueError("unknown native architecture material")
    requests = []
    relation_view = relations if relations is not None else derive_architecture_relation_candidates(tuple(facts.values()), semantic_reviews=semantic_reviews)
    for row in relation_view.get("relations", ()):
        if row["kind"] == "duplicate_boundary":
            requests.append(("duplicate_candidate", row["responsibility_ids"], row.get("input_class_ids", ()), row.get("remaining_contexts", ()), (), (), ()))
    for row in (objective_evaluation or {}).get("suggestions", ()):
        bound = objective_by_id.get(row["objective_id"])
        requests.append(("goal_mismatch", row["responsibility_ids"], bound.objective.applicable_input_class_ids if bound else (), (), (bound,) if bound else (), (), ()))
    requested_goals = {item.objective.objective_id for request in requests for item in request[4]}
    evaluation = objective_evaluation or {}
    for objective in objectives:
        goal = objective.objective
        if goal.objective_id not in requested_goals and any(goal.objective_id in gap for gap in (*evaluation.get("observation_gap_ids", ()), *evaluation.get("improvement_gap_ids", ()))):
            goal_missing = tuple(dict(row) for row in evaluation.get("missing_inputs", ())
                if "functional_objective_evidence_missing:" + goal.objective_id + ":" + row["reference_id"]
                in evaluation.get("observation_gap_ids", ()))
            if not goal_missing:
                # An unknown scope/context is not proof that the normative
                # source is absent. Preserve exact source failures only when
                # the objective evaluator actually returned that missing row.
                goal_missing = (_missing_input("context_proof", goal.objective_id,
                                              next_owner_id=goal.native_owner_id),)
            requests.append(("goal_mismatch", goal.responsibility_ids, goal.applicable_input_class_ids, (), (objective,), goal_missing, ()))
    # Missing semantic context is actionable even when no relation is admitted.
    for fact in facts.values():
        review = reviews.get(canonical_fingerprint(fact.to_dict()))
        if review is None or not review.ready or review.evidence_scope != "implementation_boundary":
            requests.append(("duplicate_candidate", (fact.responsibility_id,), fact.applicable_input_class_ids, (), (), (_missing_input("context_proof", fact.responsibility_id, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id),), ()))
    for gap in model_gaps:
        requests.append(("model_gap", (), (), (), (), (_missing_input("model_binding", gap["required_input"], model_id=gap["model_id"], next_owner_id=gap.get("next_owner_id", "")),), (gap,)))
    for row in compromises:
        requests.append(("temporary_compromise", row["responsibility_ids"], row["applicable_input_class_ids"], (), tuple(objective_by_id[x] for x in row["objective_ids"]), (), (row,)))
    pointers = []
    for kind, ids, classes, remaining, bound, initial_missing, annotations in requests:
        scoped = [facts[key] for key in ids if key in facts]
        models = {row.model_id for row in scoped} | {row["model_id"] for row in annotations if "model_id" in row} | {model for objective in bound for model in objective.objective.model_ids}
        missing = list(initial_missing)
        for responsibility in set(ids) - set(facts):
            missing.append(_missing_input("model_binding", responsibility, responsibility_id=responsibility, next_owner_id=bound[0].objective.native_owner_id if bound else ""))
        elements = {key for row in scoped for key in row.element_ids}
        owners = {row.owner_id for row in scoped}
        obligations = set()
        action_targets = []
        current_sources = dict(current_source_fingerprints or {})
        bindings = tuple(binding_report.bindings) if binding_report is not None else ()
        for fact in scoped:
            subject = subject_by_id.get(fact.model_id)
            if subject is None:
                missing.append(_missing_input("current_source", fact.model_id, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id))
            contract = contracts.get(fact.owner_code_contract_id)
            if contract is None or canonical_fingerprint(contract.to_dict()) != fact.owner_code_contract_fingerprint:
                missing.append(_missing_input("model_binding", fact.owner_code_contract_id, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id))
            else:
                obligations.update(contract.relation_code_obligation_ids)
                obligations.update(contract.implements_obligations)
            matching = [row for row in bindings if row.fingerprint == fact.implementation_binding_fingerprint and set(fact.element_ids) <= {row.model_element_id} and row.implementation_owner_id == fact.owner_id]
            if len(matching) != 1:
                missing.append(_missing_input("model_binding", fact.implementation_binding_fingerprint, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id))
            else: obligations.update(matching[0].model_obligation_ids)
            review = reviews.get(canonical_fingerprint(fact.to_dict()))
            if review is None or not review.ready or review.evidence_scope != "implementation_boundary":
                missing.append(_missing_input("semantic_source", fact.responsibility_id, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id))
        for fact in scoped:
            operation = {"duplicate_candidate": "review_shared_mechanism", "goal_mismatch": "supply_evidence", "temporary_compromise": "revisit_compromise"}.get(kind)
            if operation:
                target = _bound_architecture_action_target(fact, contracts.get(fact.owner_code_contract_id), bindings, implementation_inventory, current_sources, operation)
                if target is None:
                    missing.append(_missing_input("current_source", fact.owner_code_contract_id, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id))
                else:
                    action_targets.append(target)
                    obligations.update(target.retained_obligation_ids)
        for objective in bound:
            owners.add(objective.objective.native_owner_id)
            for model in objective.objective.model_ids:
                subject = subject_by_id.get(model)
                if subject is None or subject.intent_fingerprint != objective.effective_intent_view_fingerprint:
                    missing.append(_missing_input("objective_source", objective.objective.objective_id, model_id=model, next_owner_id=objective.objective.native_owner_id))
        for row in annotations:
            obligations.update(row.get("functional_impact", {}).get("obligation_ids", ()))
            elements.update(row.get("element_ids", ()))
            owners.update(row.get("next_owner_ids", ()))
        selected_native = tuple(row for row in material.get("native_bindings", ()) if row.evidence_scope == "implementation_boundary" and row.owner_id in owners and (row.blueprint_case_id in {b.binding_id for b in bindings if b.model_element_id in elements} or row.blueprint_source_case_id in elements or set(row.protected_failure_ids) & obligations))
        # Exact semantic bindings are an additional selector, never a guessed
        # oracle/case name or a newly invented gate.
        proof_fps = {proof.native_case_binding_fingerprint for row in scoped for proof in row.semantic_evidence_bindings}
        selected_native += tuple(row for row in material.get("native_bindings", ()) if row.evidence_scope == "implementation_boundary" and row.fingerprint in proof_fps and row not in selected_native)
        native_refs = ()
        if not selected_native and scoped:
            for fact in scoped: missing.append(_missing_input("native_binding", fact.implementation_binding_fingerprint, model_id=fact.model_id, responsibility_id=fact.responsibility_id, next_owner_id=fact.owner_id))
        elif selected_native:
            payload = {key: value for key, value in material.items() if key != "code_contracts"}
            payload["native_bindings"] = selected_native
            native_refs, native_missing = verify_architecture_native_case_refs(**payload, required_obligation_ids=tuple(sorted(obligations)), read_context=read_context)
            missing.extend(native_missing)
        source_refs = {row["path"]: row for fact in scoped for row in fact.source_refs}
        for annotation in annotations:
            for row in annotation.get("source_refs", ()):
                checked = _source_ref_dict(row)
                source_refs[checked["path"]] = checked
            if kind == "model_gap" and not annotation.get("source_refs"):
                missing.append(_missing_input("boundary_manifest", annotation["required_input"], model_id=annotation["model_id"], next_owner_id=annotation.get("next_owner_id", "")))
        for objective in bound: source_refs[objective.source_ref] = {"path": objective.source_ref, "source_fingerprint": objective.source_fingerprint}
        if kind == "model_gap":
            surfaces = {row.surface_id: row for row in getattr(implementation_inventory, "surfaces", ())}
            for annotation in annotations:
                surface = surfaces.get(annotation.get("surface_id", ""))
                if surface is not None and annotation.get("owner_boundary") == surface.path + "#" + surface.symbol and source_refs.get(surface.path, {}).get("source_fingerprint") == surface.content_fingerprint and current_sources.get(surface.path) == surface.content_fingerprint:
                    # A required surface without an admitted binding has no owner.
                    action_targets.append(ArchitectureActionTarget("add_model_obligation", surface.path, surface.symbol, surface.content_fingerprint, "", "", surface.surface_id, "", True, ()))
        if kind == "goal_mismatch":
            for objective in bound:
                goal = objective.objective
                for identifier in goal.constraint_values.get("required_code_contract_ids", ()):
                    if any(row.code_contract_id == identifier for row in action_targets):
                        continue
                    code = contracts.get(identifier)
                    exact = [row for row in bindings if row.owner_contract_id == identifier and code is not None and row.owner_contract_fingerprint == canonical_fingerprint(code.to_dict())]
                    surfaces = {row.surface_id: row for row in getattr(implementation_inventory, "surfaces", ())}
                    if len(exact) != 1:
                        continue
                    binding = exact[0]
                    surface = surfaces.get(binding.implementation_surface_id)
                    if surface is None or (surface.path, surface.symbol, surface.content_fingerprint) != (code.path, code.symbol, binding.implementation_content_fingerprint) or current_sources.get(code.path) != surface.content_fingerprint:
                        continue
                    preserved = tuple(sorted(set(binding.model_obligation_ids) | set(code.implements_obligations) | set(code.relation_code_obligation_ids)))
                    action_targets.append(ArchitectureActionTarget("supply_evidence", code.path, code.symbol, surface.content_fingerprint, identifier, canonical_fingerprint(code.to_dict()), surface.surface_id, binding.implementation_owner_id, False, preserved))
                    obligations.update(preserved)
                    owners.add(binding.implementation_owner_id)
                source_missing = any(row["kind"] == "objective_source" and row["reference_id"] in {goal.objective_id, objective.source_ref} for row in initial_missing)
                if source_missing and current_sources.get(objective.source_ref) == objective.source_fingerprint:
                    action_targets.append(ArchitectureActionTarget("repair_goal_source", objective.source_ref, goal.objective_id, objective.source_fingerprint, "", "", "", goal.native_owner_id, False, ()))
        authenticated_targets = []
        for target in action_targets:
            source = {"path": target.path, "source_fingerprint": target.source_fingerprint}
            existing = source_refs.get(target.path)
            if existing is not None and existing != source:
                missing.append(_missing_input("current_source", target.path,
                    next_owner_id=target.owner_id))
                continue
            # The inventory, binding and current bytes authenticated this
            # exact action location independently of the responsibility's
            # other source refs. Retain its own provenance on the pointer.
            source_refs[target.path] = source
            authenticated_targets.append(target)
        action_targets = authenticated_targets
        triggers = tuple(trigger for row in annotations for trigger in row.get("revisit_triggers", ()))
        status = "needs_evidence" if missing else "deferred" if kind == "temporary_compromise" else "candidate"
        pointer = ArchitectureImprovementPointer("", kind, status, "normative_target", tuple(sorted(models)), tuple(ids), tuple(sorted(elements)), tuple(classes), tuple(remaining),
            {model: subject_by_id[model].fingerprint for model in models if model in subject_by_id}, tuple(source_refs.values()), tuple(row.to_dict() for row in bound), tuple(sorted(obligations)), native_refs,
            tuple({canonical_json(row): row for row in missing}.values()), tuple(sorted(owners | {row["next_owner_id"] for row in missing if row["next_owner_id"]})), triggers, tuple({canonical_json(row.to_dict()): row for row in action_targets}.values()))
        pointers.append(pointer)
    return tuple({row.pointer_id: row for row in pointers}[key] for key in sorted({row.pointer_id for row in pointers}))
