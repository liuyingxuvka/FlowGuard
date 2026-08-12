"""Provider-neutral, bounded model path-quality decisions.

This module is an internal ModelMaturation kernel.  It deliberately exposes no
CLI or route and never mutates a model.  Ordinary reviews inspect normalized
model facts and return a compact result.  Deep comparison is admitted only for
a named finite candidate/rewrite boundary, after hard semantics and necessity
evidence are current.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, fields
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
        record = cls(**{key: data[key] for key in data if key != "fingerprint"})
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

    return canonical_fingerprint(_normalized_model_facts(model_facts))


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
    if canonical_fingerprint(normalized_facts) != subject.normalized_facts_fingerprint:
        intake_gaps.add("stale_normalized_model_facts")
    if canonical_fingerprint(dict(derived_retained)) != subject.retained_element_inventory_fingerprint:
        intake_gaps.add("stale_retained_element_inventory")
    if retained != derived_retained:
        intake_gaps.add("retained_element_inventory_mismatch")
    witness_gaps = validate_necessity_witnesses(
        subject,
        retained,
        necessity_witnesses,
        expected_currentness_id=currentness_id,
        active_obligation_ids=active_obligation_ids,
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
    detail_fingerprint = canonical_fingerprint(
        {
            "mode": "lightweight",
            "subject_fingerprint": subject.fingerprint,
            "model_facts": normalized_facts,
            "retained_elements": dict(retained),
            "witness_fingerprints": [
                row.fingerprint
                for row in sorted(necessity_witnesses, key=lambda item: item.witness_id)
            ],
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
        necessity_witness_set_fingerprint=_witness_set_fingerprint(necessity_witnesses),
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
    detail_fingerprint = canonical_fingerprint(
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
