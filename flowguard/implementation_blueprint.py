"""Implementation-blueprint closure and deterministic projection.

This module deliberately consumes an implementation inventory by protocol
(attribute or mapping access).  Discovery remains owned by
``implementation_inventory``; importing that module here would couple two
independent authorities and would make partial/affected-only consumers load a
repository scanner unnecessarily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .evidence_receipts import fingerprint_value
from .export import to_jsonable
from .portable_model import canonical_json_bytes


BLUEPRINT_SCHEMA_VERSION = "1.0"

STATIC_COMPLETE = "complete"
STATIC_INCOMPLETE = "incomplete"
STATIC_STALE = "stale"
STATIC_BLOCKED = "blocked"
STATIC_STATUSES = frozenset(
    {STATIC_COMPLETE, STATIC_INCOMPLETE, STATIC_STALE, STATIC_BLOCKED}
)

RECONSTRUCTION_NOT_RUN = "not_run"
RECONSTRUCTION_PASS = "pass"
RECONSTRUCTION_FAIL = "fail"
RECONSTRUCTION_BLOCKED = "blocked"
RECONSTRUCTION_STATUSES = frozenset(
    {
        RECONSTRUCTION_NOT_RUN,
        RECONSTRUCTION_PASS,
        RECONSTRUCTION_FAIL,
        RECONSTRUCTION_BLOCKED,
    }
)

SEMANTIC_DIMENSIONS = frozenset(
    {
        "input",
        "output",
        "state_effect",
        "error",
        "order",
        "retry",
        "timeout",
        "decision",
        "completion",
    }
)
SEMANTIC_AUTHORITY_DECLARED_BEHAVIOR = "declared_behavior"
SEMANTIC_AUTHORITY_IMPORTED_MODEL = "imported_model"
SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE = "observed_candidate"
SEMANTIC_AUTHORITY_KINDS = frozenset(
    {
        SEMANTIC_AUTHORITY_DECLARED_BEHAVIOR,
        SEMANTIC_AUTHORITY_IMPORTED_MODEL,
        SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE,
    }
)

BLUEPRINT_LAYER_INVENTORY = "inventory"
BLUEPRINT_LAYER_TRACEABILITY = "traceability"
BLUEPRINT_LAYER_INDEPENDENT_SEMANTICS = "independent_semantics"
BLUEPRINT_LAYER_MODEL_CODE_TEST = "model_code_test"
BLUEPRINT_LAYER_RESOURCE_ORACLE = "resource_oracle"
BLUEPRINT_LAYER_STATIC = "static_blueprint"
BLUEPRINT_LAYER_EMPIRICAL = "empirical_reconstruction"
BLUEPRINT_LAYER_IDS = (
    BLUEPRINT_LAYER_INVENTORY,
    BLUEPRINT_LAYER_TRACEABILITY,
    BLUEPRINT_LAYER_INDEPENDENT_SEMANTICS,
    BLUEPRINT_LAYER_MODEL_CODE_TEST,
    BLUEPRINT_LAYER_RESOURCE_ORACLE,
    BLUEPRINT_LAYER_STATIC,
    BLUEPRINT_LAYER_EMPIRICAL,
)
RELATION_KINDS = frozenset(
    {
        "implements",
        "supports",
        "calls",
        "adapts",
        "exposes",
        "reads",
        "writes",
        "serializes",
        "migrates",
        "validates",
        "builds",
        "loads",
    }
)
RESOURCE_KINDS = frozenset(
    {
        "build",
        "runtime",
        "dependency",
        "configuration",
        "schema",
        "data",
        "asset",
        "migration",
        "external_service",
        "verification",
    }
)
RESOURCE_DISPOSITIONS = frozenset({"current", "external", "scoped_out"})

_FORBIDDEN_SOURCE_KEYS = frozenset(
    {"source_text", "source_code", "production_source", "raw_source"}
)
_SECRET_KEY_FRAGMENTS = ("password", "secret", "private_key", "access_token")


class BlueprintValidationError(ValueError):
    """Raised when data cannot form a bounded canonical blueprint."""


def _tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _pairs(values: Mapping[str, str] | Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    items = values.items() if isinstance(values, Mapping) else values
    return tuple(sorted((str(key), str(value)) for key, value in items))


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _canonical_dict(value: Any) -> dict[str, Any]:
    raw = value.to_dict() if hasattr(value, "to_dict") else to_jsonable(value)
    if not isinstance(raw, Mapping):
        raise BlueprintValidationError("blueprint member must export a mapping")
    return {str(key): to_jsonable(item) for key, item in raw.items()}


def _contains_forbidden_key(value: Any, forbidden: frozenset[str]) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in forbidden or _contains_forbidden_key(child, forbidden):
                return True
    elif isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_forbidden_key(child, forbidden) for child in value)
    return False


def _contains_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in _SECRET_KEY_FRAGMENTS):
                return True
            if _contains_secret(child):
                return True
    elif isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_secret(child) for child in value)
    return False


def _fingerprinted(payload: Mapping[str, Any]) -> str:
    return fingerprint_value(to_jsonable(payload))


@dataclass(frozen=True)
class BlueprintFinding:
    code: str
    message: str
    member_ids: tuple[str, ...] = ()
    severity: str = "incomplete"

    def __post_init__(self) -> None:
        if self.severity not in {"incomplete", "stale", "blocked"}:
            raise BlueprintValidationError(f"invalid finding severity: {self.severity}")
        object.__setattr__(self, "member_ids", _tuple(self.member_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "member_ids": list(self.member_ids),
            "severity": self.severity,
        }


@dataclass(frozen=True)
class SemanticSpecReference:
    semantic_spec_id: str
    owner_id: str
    artifact_id: str
    artifact_fingerprint: str
    covered_model_element_ids: tuple[str, ...]
    covered_dimensions: tuple[str, ...]
    semantics: tuple[tuple[str, str], ...]
    authority_kind: str = SEMANTIC_AUTHORITY_DECLARED_BEHAVIOR
    provenance_fingerprints: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "covered_model_element_ids", _tuple(self.covered_model_element_ids)
        )
        object.__setattr__(self, "covered_dimensions", _tuple(self.covered_dimensions))
        object.__setattr__(self, "semantics", _pairs(self.semantics))
        object.__setattr__(
            self,
            "provenance_fingerprints",
            _pairs(self.provenance_fingerprints),
        )
        if self.authority_kind not in SEMANTIC_AUTHORITY_KINDS:
            raise BlueprintValidationError(
                f"unknown semantic authority kind: {self.authority_kind}"
            )
        if self.authority_kind != SEMANTIC_AUTHORITY_OBSERVED_CANDIDATE and not self.provenance_fingerprints:
            raise BlueprintValidationError(
                "independent semantic specification requires provenance fingerprints"
            )
        unknown = set(self.covered_dimensions) - SEMANTIC_DIMENSIONS
        if unknown:
            raise BlueprintValidationError(f"unknown semantic dimensions: {sorted(unknown)}")
        if not all(
            (self.semantic_spec_id, self.owner_id, self.artifact_id, self.artifact_fingerprint)
        ):
            raise BlueprintValidationError("semantic specification identity is incomplete")
        semantic_payload = dict(self.semantics)
        missing = set(self.covered_dimensions) - set(semantic_payload)
        if missing:
            raise BlueprintValidationError(
                f"semantic specification lacks source-independent content: {sorted(missing)}"
            )
        if _contains_forbidden_key(semantic_payload, _FORBIDDEN_SOURCE_KEYS):
            raise BlueprintValidationError("semantic specification must not embed production source")
        if _contains_secret(semantic_payload):
            raise BlueprintValidationError("semantic specification must not embed secrets")

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_spec_id": self.semantic_spec_id,
            "owner_id": self.owner_id,
            "artifact_id": self.artifact_id,
            "artifact_fingerprint": self.artifact_fingerprint,
            "covered_model_element_ids": list(self.covered_model_element_ids),
            "covered_dimensions": list(self.covered_dimensions),
            "semantics": dict(self.semantics),
            "authority_kind": self.authority_kind,
            "provenance_fingerprints": dict(self.provenance_fingerprints),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


@dataclass(frozen=True)
class OracleReference:
    oracle_id: str
    owner_id: str
    artifact_id: str
    artifact_fingerprint: str
    covered_model_element_ids: tuple[str, ...]
    covered_dimensions: tuple[str, ...]
    semantics: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "covered_model_element_ids", _tuple(self.covered_model_element_ids)
        )
        object.__setattr__(self, "covered_dimensions", _tuple(self.covered_dimensions))
        object.__setattr__(self, "semantics", _pairs(self.semantics))
        unknown = set(self.covered_dimensions) - SEMANTIC_DIMENSIONS
        if unknown:
            raise BlueprintValidationError(f"unknown oracle dimensions: {sorted(unknown)}")
        if not all((self.oracle_id, self.owner_id, self.artifact_id, self.artifact_fingerprint)):
            raise BlueprintValidationError("oracle identity is incomplete")
        oracle_payload = dict(self.semantics)
        missing = set(self.covered_dimensions) - set(oracle_payload)
        if missing:
            raise BlueprintValidationError(
                f"oracle lacks executable or inspectable expectations: {sorted(missing)}"
            )
        if _contains_forbidden_key(oracle_payload, _FORBIDDEN_SOURCE_KEYS):
            raise BlueprintValidationError("oracle must not embed production source")
        if _contains_secret(oracle_payload):
            raise BlueprintValidationError("oracle must not embed secrets")

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "owner_id": self.owner_id,
            "artifact_id": self.artifact_id,
            "artifact_fingerprint": self.artifact_fingerprint,
            "covered_model_element_ids": list(self.covered_model_element_ids),
            "covered_dimensions": list(self.covered_dimensions),
            "semantics": dict(self.semantics),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


@dataclass(frozen=True)
class BlueprintResourceReference:
    resource_id: str
    kind: str
    owner_id: str
    artifact_id: str
    purpose: str
    lifecycle_role: str
    disposition: str = "current"
    artifact_fingerprint: str | None = None
    rationale: str | None = None
    semantics: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.resource_id,
                self.owner_id,
                self.artifact_id,
                self.purpose,
                self.lifecycle_role,
            )
        ):
            raise BlueprintValidationError(
                "resource identity, purpose, and lifecycle role are required"
            )
        if self.kind not in RESOURCE_KINDS:
            raise BlueprintValidationError(f"unknown blueprint resource kind: {self.kind}")
        if self.disposition not in RESOURCE_DISPOSITIONS:
            raise BlueprintValidationError(
                f"unknown blueprint resource disposition: {self.disposition}"
            )
        if self.disposition == "current" and not self.artifact_fingerprint:
            raise BlueprintValidationError("current resource requires a fingerprint")
        if self.disposition != "current" and not self.rationale:
            raise BlueprintValidationError(
                "external or scoped resource requires an explicit rationale"
            )
        object.__setattr__(self, "semantics", _pairs(self.semantics))
        if self.disposition == "current" and not self.semantics:
            raise BlueprintValidationError(
                "current resource requires source-independent blueprint semantics"
            )
        if _contains_secret(dict(self.semantics)):
            raise BlueprintValidationError("resource semantics must not embed secrets")

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "owner_id": self.owner_id,
            "artifact_id": self.artifact_id,
            "purpose": self.purpose,
            "lifecycle_role": self.lifecycle_role,
            "disposition": self.disposition,
            "artifact_fingerprint": self.artifact_fingerprint,
            "rationale": self.rationale,
            "semantics": dict(self.semantics),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


@dataclass(frozen=True)
class ModelImplementationBinding:
    binding_id: str
    model_element_id: str
    implementation_surface_id: str
    relation_kind: str
    owner_contract_id: str
    semantic_spec_ids: tuple[str, ...]
    oracle_ids: tuple[str, ...]
    required_dimensions: tuple[str, ...] = ("input", "output", "error")
    consumer_surface_ids: tuple[str, ...] = ()
    test_evidence_ids: tuple[str, ...] = ()
    test_evidence_fingerprints: tuple[tuple[str, str], ...] = ()
    primary: bool = True
    delegating: bool = False
    model_fingerprint: str | None = None
    implementation_fingerprint: str | None = None
    owner_contract_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.relation_kind not in RELATION_KINDS:
            raise BlueprintValidationError(f"unknown binding relation: {self.relation_kind}")
        for name in (
            "semantic_spec_ids",
            "oracle_ids",
            "required_dimensions",
            "consumer_surface_ids",
            "test_evidence_ids",
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        object.__setattr__(
            self,
            "test_evidence_fingerprints",
            _pairs(self.test_evidence_fingerprints),
        )
        unknown = set(self.required_dimensions) - SEMANTIC_DIMENSIONS
        if unknown:
            raise BlueprintValidationError(f"unknown required dimensions: {sorted(unknown)}")
        if not all(
            (
                self.binding_id,
                self.model_element_id,
                self.implementation_surface_id,
                self.owner_contract_id,
            )
        ):
            raise BlueprintValidationError("binding identity is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "model_element_id": self.model_element_id,
            "implementation_surface_id": self.implementation_surface_id,
            "relation_kind": self.relation_kind,
            "owner_contract_id": self.owner_contract_id,
            "semantic_spec_ids": list(self.semantic_spec_ids),
            "oracle_ids": list(self.oracle_ids),
            "required_dimensions": list(self.required_dimensions),
            "consumer_surface_ids": list(self.consumer_surface_ids),
            "test_evidence_ids": list(self.test_evidence_ids),
            "test_evidence_fingerprints": dict(self.test_evidence_fingerprints),
            "primary": self.primary,
            "delegating": self.delegating,
            "model_fingerprint": self.model_fingerprint,
            "implementation_fingerprint": self.implementation_fingerprint,
            "owner_contract_fingerprint": self.owner_contract_fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


@dataclass(frozen=True)
class ModelImplementationBindingReport:
    inventory_id: str
    inventory_fingerprint: str
    required_model_element_ids: tuple[str, ...]
    required_implementation_surface_ids: tuple[str, ...]
    bound_model_element_ids: tuple[str, ...]
    bound_implementation_surface_ids: tuple[str, ...]
    bindings: tuple[ModelImplementationBinding, ...]
    semantic_specs: tuple[SemanticSpecReference, ...]
    oracles: tuple[OracleReference, ...]
    findings: tuple[BlueprintFinding, ...]
    status: str

    def __post_init__(self) -> None:
        if self.status not in STATIC_STATUSES:
            raise BlueprintValidationError(f"invalid binding report status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BLUEPRINT_SCHEMA_VERSION,
            "inventory_id": self.inventory_id,
            "inventory_fingerprint": self.inventory_fingerprint,
            "required_model_element_ids": list(self.required_model_element_ids),
            "required_implementation_surface_ids": list(
                self.required_implementation_surface_ids
            ),
            "bound_model_element_ids": list(self.bound_model_element_ids),
            "bound_implementation_surface_ids": list(
                self.bound_implementation_surface_ids
            ),
            "implementation_surface_ids": list(self.implementation_surface_ids),
            "model_obligation_ids": list(self.model_obligation_ids),
            "semantic_spec_ids": list(self.semantic_spec_ids),
            "oracle_ids": list(self.oracle_ids),
            "test_evidence_ids": list(self.test_evidence_ids),
            "bindings": [binding.to_dict() for binding in self.bindings],
            "semantic_specs": [reference.to_dict() for reference in self.semantic_specs],
            "oracles": [reference.to_dict() for reference in self.oracles],
            "findings": [finding.to_dict() for finding in self.findings],
            "status": self.status,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())

    @property
    def ok(self) -> bool:
        return self.status == STATIC_COMPLETE

    @property
    def implementation_surface_ids(self) -> tuple[str, ...]:
        """All inventory surfaces required by this closure report."""

        return self.required_implementation_surface_ids

    @property
    def model_obligation_ids(self) -> tuple[str, ...]:
        """All model obligations required by this closure report."""

        return self.required_model_element_ids

    @property
    def semantic_spec_ids(self) -> tuple[str, ...]:
        return tuple(reference.semantic_spec_id for reference in self.semantic_specs)

    @property
    def oracle_ids(self) -> tuple[str, ...]:
        return tuple(reference.oracle_id for reference in self.oracles)

    @property
    def test_evidence_ids(self) -> tuple[str, ...]:
        return _tuple(
            test_id
            for binding in self.bindings
            for test_id in binding.test_evidence_ids
        )


def _surface_id(surface: Any) -> str:
    return str(_value(surface, "surface_id", _value(surface, "item_id", _value(surface, "id", ""))))


def _surface_requires_binding(surface: Any) -> bool:
    disposition = str(_value(surface, "disposition", ""))
    terminal = disposition in {"generated", "external", "scoped_out", "dead_retire"}
    return not terminal and bool(
        _value(surface, "behavior_bearing", False)
        or _value(surface, "externally_meaningful", False)
        or _value(surface, "public", False)
        or _value(surface, "state_write_ids", ())
        or _value(surface, "state_writes", ())
        or _value(surface, "effect_ids", ())
        or _value(surface, "side_effect_candidates", ())
        or _value(surface, "dynamic_operations", ())
        or _value(surface, "writes", ())
        or _value(surface, "effects", ())
    )


def _status_from_findings(findings: Sequence[BlueprintFinding]) -> str:
    severities = {finding.severity for finding in findings}
    if "blocked" in severities:
        return STATIC_BLOCKED
    if "stale" in severities:
        return STATIC_STALE
    if "incomplete" in severities:
        return STATIC_INCOMPLETE
    return STATIC_COMPLETE


def review_model_implementation_bindings(
    inventory: Any,
    *,
    required_model_element_ids: Iterable[str],
    bindings: Sequence[ModelImplementationBinding],
    semantic_specs: Sequence[SemanticSpecReference],
    oracles: Sequence[OracleReference],
    required_implementation_surface_ids: Iterable[str] | None = None,
    current_model_fingerprints: Mapping[str, str] | None = None,
    current_contract_fingerprints: Mapping[str, str] | None = None,
    current_semantic_spec_fingerprints: Mapping[str, str] | None = None,
    current_oracle_fingerprints: Mapping[str, str] | None = None,
    current_test_evidence_fingerprints: Mapping[str, str] | None = None,
) -> ModelImplementationBindingReport:
    """Review the independent inventory against model bindings in both directions."""

    inventory_id = str(_value(inventory, "inventory_id", _value(inventory, "id", "")))
    inventory_fingerprint = str(_value(inventory, "fingerprint", ""))
    surfaces = tuple(_value(inventory, "surfaces", _value(inventory, "items", ())))
    surface_by_id = {_surface_id(surface): surface for surface in surfaces if _surface_id(surface)}
    required_models = set(_tuple(required_model_element_ids))
    if required_implementation_surface_ids is None:
        required_surfaces = {
            surface_id
            for surface_id, surface in surface_by_id.items()
            if _surface_requires_binding(surface)
            or str(_value(surface, "disposition", "")) == "model_implementation"
        }
    else:
        required_surfaces = set(_tuple(required_implementation_surface_ids))

    ordered_bindings = tuple(sorted(bindings, key=lambda item: item.binding_id))
    ordered_specs = tuple(sorted(semantic_specs, key=lambda item: item.semantic_spec_id))
    ordered_oracles = tuple(sorted(oracles, key=lambda item: item.oracle_id))
    spec_by_id = {item.semantic_spec_id: item for item in ordered_specs}
    oracle_by_id = {item.oracle_id: item for item in ordered_oracles}
    findings: list[BlueprintFinding] = []

    if not inventory_id or not inventory_fingerprint:
        findings.append(
            BlueprintFinding(
                "inventory_identity_missing",
                "Independent implementation inventory identity or fingerprint is missing.",
                severity="blocked",
            )
        )

    binding_ids = [binding.binding_id for binding in ordered_bindings]
    duplicate_ids = sorted({value for value in binding_ids if binding_ids.count(value) > 1})
    if duplicate_ids:
        findings.append(
            BlueprintFinding(
                "duplicate_binding_identity",
                "Binding identities must be unique.",
                tuple(duplicate_ids),
                "blocked",
            )
        )

    if current_semantic_spec_fingerprints is not None:
        for reference in ordered_specs:
            if (
                reference.artifact_fingerprint
                != current_semantic_spec_fingerprints.get(reference.semantic_spec_id)
            ):
                findings.append(
                    BlueprintFinding(
                        "stale_semantic_specification",
                        "Semantic specification reference is not current.",
                        (reference.semantic_spec_id,),
                        "stale",
                    )
                )
    if current_oracle_fingerprints is not None:
        for reference in ordered_oracles:
            if reference.artifact_fingerprint != current_oracle_fingerprints.get(
                reference.oracle_id
            ):
                findings.append(
                    BlueprintFinding(
                        "stale_oracle_reference",
                        "Oracle reference is not current.",
                        (reference.oracle_id,),
                        "stale",
                    )
                )

    primary_by_model: dict[str, list[ModelImplementationBinding]] = {}
    for binding in ordered_bindings:
        if binding.primary and not binding.delegating:
            primary_by_model.setdefault(binding.model_element_id, []).append(binding)
    for model_id in sorted(required_models):
        owners = primary_by_model.get(model_id, [])
        if not owners:
            findings.append(
                BlueprintFinding(
                    "missing_primary_implementation",
                    "Required model obligation has no current primary implementation.",
                    (model_id,),
                )
            )
        elif len(owners) > 1:
            findings.append(
                BlueprintFinding(
                    "duplicate_primary_implementation",
                    "Multiple non-delegating implementations claim primary ownership.",
                    (model_id, *(item.binding_id for item in owners)),
                    "blocked",
                )
            )

    bound_surface_ids = {binding.implementation_surface_id for binding in ordered_bindings}
    for surface_id in sorted(required_surfaces - bound_surface_ids):
        findings.append(
            BlueprintFinding(
                "unbound_behavior_surface",
                "Behavior-bearing implementation surface has no model or owner binding.",
                (surface_id,),
                "blocked",
            )
        )

    for binding in ordered_bindings:
        surface = surface_by_id.get(binding.implementation_surface_id)
        if surface is None:
            findings.append(
                BlueprintFinding(
                    "missing_inventory_surface",
                    "Binding refers to a surface absent from the independent inventory.",
                    (binding.binding_id, binding.implementation_surface_id),
                    "blocked",
                )
            )
            continue

        missing_specs = set(binding.semantic_spec_ids) - set(spec_by_id)
        missing_oracles = set(binding.oracle_ids) - set(oracle_by_id)
        if missing_specs:
            findings.append(
                BlueprintFinding(
                    "missing_semantic_reference",
                    "Binding lacks a current source-independent semantic specification.",
                    (binding.binding_id, *missing_specs),
                )
            )
        if missing_oracles:
            findings.append(
                BlueprintFinding(
                    "missing_oracle_reference",
                    "Binding lacks an applicable current oracle.",
                    (binding.binding_id, *missing_oracles),
                )
            )
        if not binding.test_evidence_ids:
            findings.append(
                BlueprintFinding(
                    "model_test_binding_missing",
                    "Binding has no exact project test evidence identity.",
                    (binding.binding_id,),
                )
            )
        declared_test_fingerprints = dict(binding.test_evidence_fingerprints)
        missing_test_fingerprints = set(binding.test_evidence_ids) - set(
            declared_test_fingerprints
        )
        if missing_test_fingerprints:
            findings.append(
                BlueprintFinding(
                    "test_evidence_fingerprint_missing",
                    "Binding test identities require exact source or evidence fingerprints.",
                    (binding.binding_id, *missing_test_fingerprints),
                )
            )
        if current_test_evidence_fingerprints is not None:
            stale_test_ids = tuple(
                sorted(
                    test_id
                    for test_id in binding.test_evidence_ids
                    if declared_test_fingerprints.get(test_id)
                    != current_test_evidence_fingerprints.get(test_id)
                )
            )
            if stale_test_ids:
                findings.append(
                    BlueprintFinding(
                        "stale_test_evidence_binding",
                        "Binding consumes a non-current test source or evidence fingerprint.",
                        (binding.binding_id, *stale_test_ids),
                        "stale",
                    )
                )

        spec_dimensions: set[str] = set()
        oracle_dimensions: set[str] = set()
        for spec_id in binding.semantic_spec_ids:
            reference = spec_by_id.get(spec_id)
            if reference and binding.model_element_id in reference.covered_model_element_ids:
                spec_dimensions.update(reference.covered_dimensions)
        for oracle_id in binding.oracle_ids:
            reference = oracle_by_id.get(oracle_id)
            if reference and binding.model_element_id in reference.covered_model_element_ids:
                oracle_dimensions.update(reference.covered_dimensions)
        required_dimensions = set(binding.required_dimensions)
        if _surface_requires_binding(surface) and (
            _value(surface, "state_write_ids", ())
            or _value(surface, "state_writes", ())
            or _value(surface, "effect_ids", ())
            or _value(surface, "side_effect_candidates", ())
            or _value(surface, "dynamic_operations", ())
            or _value(surface, "writes", ())
            or _value(surface, "effects", ())
        ):
            required_dimensions.add("state_effect")
        missing_semantics = required_dimensions - spec_dimensions
        missing_oracle_dimensions = required_dimensions - oracle_dimensions
        if missing_semantics:
            findings.append(
                BlueprintFinding(
                    "semantic_dimensions_incomplete",
                    "Semantic specifications do not cover every required behavior dimension.",
                    (binding.binding_id, *missing_semantics),
                )
            )
        independent_dimensions: set[str] = set()
        for spec_id in binding.semantic_spec_ids:
            reference = spec_by_id.get(spec_id)
            if (
                reference
                and reference.authority_kind
                in {
                    SEMANTIC_AUTHORITY_DECLARED_BEHAVIOR,
                    SEMANTIC_AUTHORITY_IMPORTED_MODEL,
                }
                and binding.model_element_id in reference.covered_model_element_ids
            ):
                independent_dimensions.update(reference.covered_dimensions)
        missing_independent = required_dimensions - independent_dimensions
        if missing_independent:
            findings.append(
                BlueprintFinding(
                    "source_observation_not_independent",
                    "Production-source observations cannot independently certify intended semantics.",
                    (binding.binding_id, *missing_independent),
                )
            )
        if missing_oracle_dimensions:
            findings.append(
                BlueprintFinding(
                    "oracle_dimensions_incomplete",
                    "Oracles do not cover every required behavior dimension.",
                    (binding.binding_id, *missing_oracle_dimensions),
                )
            )

        current_surface_fp = str(
            _value(
                surface,
                "fingerprint",
                _value(
                    surface,
                    "content_fingerprint",
                    _value(surface, "source_fingerprint", ""),
                ),
            )
        )
        if binding.implementation_fingerprint and current_surface_fp and (
            binding.implementation_fingerprint != current_surface_fp
        ):
            findings.append(
                BlueprintFinding(
                    "stale_implementation_binding",
                    "Binding consumes a non-current implementation fingerprint.",
                    (binding.binding_id, binding.implementation_surface_id),
                    "stale",
                )
            )
        if current_model_fingerprints is not None and (
            binding.model_fingerprint != current_model_fingerprints.get(binding.model_element_id)
        ):
            findings.append(
                BlueprintFinding(
                    "stale_model_binding",
                    "Binding consumes a non-current model fingerprint.",
                    (binding.binding_id, binding.model_element_id),
                    "stale",
                )
            )
        if current_contract_fingerprints is not None and (
            binding.owner_contract_fingerprint
            != current_contract_fingerprints.get(binding.owner_contract_id)
        ):
            findings.append(
                BlueprintFinding(
                    "stale_owner_contract",
                    "Binding consumes a non-current owner-contract fingerprint.",
                    (binding.binding_id, binding.owner_contract_id),
                    "stale",
                )
            )

    # Supporting helpers remain internal, but they must lead to one owner.
    for surface_id, surface in sorted(surface_by_id.items()):
        if str(_value(surface, "disposition", "")) != "supporting":
            continue
        supporting_owner = str(
            _value(
                surface,
                "supporting_owner_surface_id",
                _value(surface, "owning_surface_id", _value(surface, "owner_surface_id", "")),
            )
        )
        helper_bindings = [
            binding
            for binding in ordered_bindings
            if binding.implementation_surface_id == surface_id
        ]
        if not supporting_owner and not helper_bindings:
            findings.append(
                BlueprintFinding(
                    "orphan_supporting_surface",
                    "Supporting implementation has no realization path to a unique owner.",
                    (surface_id,),
                    "blocked",
                )
            )

    # Discovery blockers are facts of the independent denominator, not caller summaries.
    for name, code in (
        ("hidden_writer_ids", "hidden_state_or_effect_writer"),
        ("unresolved_surface_ids", "unresolved_implementation_surface"),
        ("parse_failure_ids", "implementation_parse_failure"),
    ):
        values = _tuple(_value(inventory, name, ()))
        if values:
            findings.append(
                BlueprintFinding(
                    code,
                    "Independent discovery contains an unresolved implementation blocker.",
                    values,
                    "blocked",
                )
            )

    for surface_id, surface in sorted(surface_by_id.items()):
        if str(_value(surface, "disposition", "")) == "unresolved":
            findings.append(
                BlueprintFinding(
                    "unresolved_implementation_surface",
                    "Independent discovery left an implementation surface unresolved.",
                    (surface_id,),
                    "blocked",
                )
            )
    for finding in tuple(_value(inventory, "findings", ())):
        severity = str(_value(finding, "severity", ""))
        if severity in {"blocker", "blocked", "error"}:
            finding_id = str(
                _value(finding, "surface_id", _value(finding, "path", _value(finding, "code", "")))
            )
            findings.append(
                BlueprintFinding(
                    "implementation_inventory_blocker",
                    str(_value(finding, "message", "Independent discovery reported a blocker.")),
                    (finding_id,) if finding_id else (),
                    "blocked",
                )
            )

    return ModelImplementationBindingReport(
        inventory_id=inventory_id,
        inventory_fingerprint=inventory_fingerprint,
        required_model_element_ids=_tuple(required_models),
        required_implementation_surface_ids=_tuple(required_surfaces),
        bound_model_element_ids=_tuple(binding.model_element_id for binding in ordered_bindings),
        bound_implementation_surface_ids=_tuple(bound_surface_ids),
        bindings=ordered_bindings,
        semantic_specs=ordered_specs,
        oracles=ordered_oracles,
        findings=tuple(sorted(findings, key=lambda item: (item.severity, item.code, item.member_ids))),
        status=_status_from_findings(findings),
    )


@dataclass(frozen=True)
class SoftwareBlueprintManifest:
    blueprint_id: str
    observed_snapshot_id: str
    observed_snapshot_fingerprint: str
    inventory_id: str
    inventory_fingerprint: str
    binding_report_id: str
    binding_report_fingerprint: str
    semantic_mesh_id: str
    semantic_mesh_fingerprint: str
    test_inventory_id: str
    test_inventory_fingerprint: str
    model_test_alignment_report_id: str
    model_test_alignment_report_fingerprint: str
    portable_owner_fingerprints: tuple[tuple[str, str], ...]
    resources: tuple[BlueprintResourceReference, ...]
    oracles: tuple[OracleReference, ...]
    required_resource_ids: tuple[str, ...] = ()
    required_resource_kinds: tuple[str, ...] = ()
    required_oracle_ids: tuple[str, ...] = ()
    excluded_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "portable_owner_fingerprints", _pairs(self.portable_owner_fingerprints)
        )
        object.__setattr__(self, "resources", tuple(sorted(self.resources, key=lambda item: item.resource_id)))
        object.__setattr__(self, "oracles", tuple(sorted(self.oracles, key=lambda item: item.oracle_id)))
        for name in ("required_resource_ids", "required_resource_kinds", "required_oracle_ids", "excluded_source_ids"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        unknown_kinds = set(self.required_resource_kinds) - RESOURCE_KINDS
        if unknown_kinds:
            raise BlueprintValidationError(f"unknown required resource kinds: {sorted(unknown_kinds)}")
        identities = (
            self.blueprint_id,
            self.observed_snapshot_id,
            self.observed_snapshot_fingerprint,
            self.inventory_id,
            self.inventory_fingerprint,
            self.binding_report_id,
            self.binding_report_fingerprint,
            self.semantic_mesh_id,
            self.semantic_mesh_fingerprint,
            self.test_inventory_id,
            self.test_inventory_fingerprint,
            self.model_test_alignment_report_id,
            self.model_test_alignment_report_fingerprint,
        )
        if not all(identities):
            raise BlueprintValidationError("blueprint manifest authority identity is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BLUEPRINT_SCHEMA_VERSION,
            "blueprint_id": self.blueprint_id,
            "observed_snapshot_id": self.observed_snapshot_id,
            "observed_snapshot_fingerprint": self.observed_snapshot_fingerprint,
            "inventory_id": self.inventory_id,
            "inventory_fingerprint": self.inventory_fingerprint,
            "binding_report_id": self.binding_report_id,
            "binding_report_fingerprint": self.binding_report_fingerprint,
            "semantic_mesh_id": self.semantic_mesh_id,
            "semantic_mesh_fingerprint": self.semantic_mesh_fingerprint,
            "test_inventory_id": self.test_inventory_id,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "model_test_alignment_report_id": self.model_test_alignment_report_id,
            "model_test_alignment_report_fingerprint": self.model_test_alignment_report_fingerprint,
            "portable_owner_fingerprints": dict(self.portable_owner_fingerprints),
            "resources": [resource.to_dict() for resource in self.resources],
            "oracles": [oracle.to_dict() for oracle in self.oracles],
            "required_resource_ids": list(self.required_resource_ids),
            "required_resource_kinds": list(self.required_resource_kinds),
            "required_oracle_ids": list(self.required_oracle_ids),
            "excluded_source_ids": list(self.excluded_source_ids),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


@dataclass(frozen=True)
class ReconstructionEvidence:
    receipt_id: str
    blueprint_fingerprint: str
    environment_fingerprint: str
    isolated_environment: bool
    source_access_policy: str
    covered_oracle_ids: tuple[str, ...]
    evidence_fingerprint: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "covered_oracle_ids", _tuple(self.covered_oracle_ids))
        if self.status not in {RECONSTRUCTION_PASS, RECONSTRUCTION_FAIL, RECONSTRUCTION_BLOCKED}:
            raise BlueprintValidationError("a supplied reconstruction receipt cannot be not_run")

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "isolated_environment": self.isolated_environment,
            "source_access_policy": self.source_access_policy,
            "covered_oracle_ids": list(self.covered_oracle_ids),
            "evidence_fingerprint": self.evidence_fingerprint,
            "status": self.status,
        }


@dataclass(frozen=True)
class BlueprintLayerResult:
    layer_id: str
    status: str
    finding_codes: tuple[str, ...] = ()
    member_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.layer_id not in BLUEPRINT_LAYER_IDS:
            raise BlueprintValidationError(f"unknown blueprint layer: {self.layer_id}")
        allowed = RECONSTRUCTION_STATUSES if self.layer_id == BLUEPRINT_LAYER_EMPIRICAL else STATIC_STATUSES
        if self.status not in allowed:
            raise BlueprintValidationError(
                f"invalid status for blueprint layer {self.layer_id}: {self.status}"
            )
        object.__setattr__(self, "finding_codes", _tuple(self.finding_codes))
        object.__setattr__(self, "member_ids", _tuple(self.member_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "status": self.status,
            "finding_codes": list(self.finding_codes),
            "member_ids": list(self.member_ids),
        }


@dataclass(frozen=True)
class SoftwareBlueprintQualificationReport:
    blueprint_id: str
    blueprint_fingerprint: str
    static_status: str
    empirical_status: str
    static_findings: tuple[BlueprintFinding, ...] = ()
    empirical_findings: tuple[BlueprintFinding, ...] = ()
    reconstruction_required: bool = False
    layers: tuple[BlueprintLayerResult, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "static_findings", tuple(self.static_findings))
        object.__setattr__(self, "empirical_findings", tuple(self.empirical_findings))
        object.__setattr__(self, "layers", tuple(self.layers))
        layer_ids = tuple(layer.layer_id for layer in self.layers)
        if layer_ids and layer_ids != BLUEPRINT_LAYER_IDS:
            raise BlueprintValidationError("blueprint qualification layers are not exact-current")

    @property
    def ok(self) -> bool:
        return self.static_status == STATIC_COMPLETE and (
            not self.reconstruction_required or self.empirical_status == RECONSTRUCTION_PASS
        )

    @property
    def claim_text(self) -> str:
        if self.static_status == STATIC_COMPLETE and self.empirical_status == RECONSTRUCTION_NOT_RUN:
            return "blueprint complete; reconstruction not run"
        if self.static_status == STATIC_COMPLETE and self.empirical_status == RECONSTRUCTION_PASS:
            return "blueprint complete; reconstruction verified"
        return f"blueprint {self.static_status}; reconstruction {self.empirical_status}"

    def layer_status(self, layer_id: str) -> str:
        for layer in self.layers:
            if layer.layer_id == layer_id:
                return layer.status
        raise BlueprintValidationError(f"qualification has no layer: {layer_id}")

    @property
    def deepest_proven_layer(self) -> str:
        deepest = "none"
        for layer_id in BLUEPRINT_LAYER_IDS[:-1]:
            if self.layer_status(layer_id) != STATIC_COMPLETE:
                break
            deepest = layer_id
        return deepest

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "static_status": self.static_status,
            "empirical_status": self.empirical_status,
            "static_findings": [finding.to_dict() for finding in self.static_findings],
            "empirical_findings": [finding.to_dict() for finding in self.empirical_findings],
            "reconstruction_required": self.reconstruction_required,
            "layers": [layer.to_dict() for layer in self.layers],
            "deepest_proven_layer": self.deepest_proven_layer,
            "ok": self.ok,
            "claim_text": self.claim_text,
        }

    def to_static_dict(self) -> dict[str, Any]:
        """Project ordinary static qualification without specialist execution state."""

        return {
            "blueprint_id": self.blueprint_id,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "static_status": self.static_status,
            "static_findings": [finding.to_dict() for finding in self.static_findings],
            "layers": [
                layer.to_dict()
                for layer in self.layers
                if layer.layer_id != BLUEPRINT_LAYER_EMPIRICAL
            ],
            "deepest_proven_layer": self.deepest_proven_layer,
            "ok": self.static_status == STATIC_COMPLETE,
            "claim_text": f"blueprint {self.static_status}",
        }

    @property
    def static_fingerprint(self) -> str:
        return _fingerprinted(self.to_static_dict())

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


def qualify_software_blueprint(
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
    *,
    implementation_inventory: Any | None = None,
    reconstruction_evidence: ReconstructionEvidence | None = None,
    reconstruction_required: bool = False,
    current_observed_snapshot_fingerprint: str | None = None,
    current_semantic_mesh_fingerprint: str | None = None,
    current_test_inventory_fingerprint: str | None = None,
    current_model_test_alignment_report_fingerprint: str | None = None,
    current_portable_owner_fingerprints: Mapping[str, str] | None = None,
    current_resource_fingerprints: Mapping[str, str] | None = None,
    current_oracle_fingerprints: Mapping[str, str] | None = None,
) -> SoftwareBlueprintQualificationReport:
    """Qualify static closure without implicitly scheduling reconstruction."""

    static_findings = list(binding_report.findings)
    if implementation_inventory is not None:
        current_inventory_fingerprint = str(
            _value(
                implementation_inventory,
                "inventory_fingerprint",
                _value(implementation_inventory, "fingerprint", ""),
            )
        )
        if current_inventory_fingerprint != manifest.inventory_fingerprint:
            static_findings.append(
                BlueprintFinding(
                    "stale_inventory_artifact",
                    "Supplied implementation inventory does not match the blueprint manifest.",
                    (manifest.inventory_id,),
                    "stale",
                )
            )
    if manifest.inventory_id != binding_report.inventory_id or (
        manifest.inventory_fingerprint != binding_report.inventory_fingerprint
    ):
        static_findings.append(
            BlueprintFinding(
                "stale_inventory_reference",
                "Manifest and binding report do not consume the same inventory.",
                (manifest.inventory_id, binding_report.inventory_id),
                "stale",
            )
        )
    if manifest.binding_report_fingerprint != binding_report.fingerprint:
        static_findings.append(
            BlueprintFinding(
                "stale_binding_report_reference",
                "Manifest does not bind the current binding report fingerprint.",
                (manifest.binding_report_id,),
                "stale",
            )
        )
    if (
        current_observed_snapshot_fingerprint is not None
        and manifest.observed_snapshot_fingerprint
        != current_observed_snapshot_fingerprint
    ):
        static_findings.append(
            BlueprintFinding(
                "stale_observed_model_snapshot",
                "Blueprint does not derive from the current observed model-system snapshot.",
                (manifest.observed_snapshot_id,),
                "stale",
            )
        )
    if (
        current_semantic_mesh_fingerprint is not None
        and manifest.semantic_mesh_fingerprint != current_semantic_mesh_fingerprint
    ):
        static_findings.append(
            BlueprintFinding(
                "stale_semantic_mesh",
                "Blueprint does not consume the current semantic mesh.",
                (manifest.semantic_mesh_id,),
                "stale",
            )
        )
    if (
        current_test_inventory_fingerprint is not None
        and manifest.test_inventory_fingerprint != current_test_inventory_fingerprint
    ):
        static_findings.append(
            BlueprintFinding(
                "stale_test_inventory",
                "Blueprint does not consume the current project test inventory.",
                (manifest.test_inventory_id,),
                "stale",
            )
        )
    if (
        current_model_test_alignment_report_fingerprint is not None
        and manifest.model_test_alignment_report_fingerprint
        != current_model_test_alignment_report_fingerprint
    ):
        static_findings.append(
            BlueprintFinding(
                "stale_model_test_alignment_report",
                "Blueprint does not consume the current model-code-test alignment report.",
                (manifest.model_test_alignment_report_id,),
                "stale",
            )
        )
    if current_portable_owner_fingerprints is not None:
        for owner_id, owner_fingerprint in manifest.portable_owner_fingerprints:
            if owner_fingerprint != current_portable_owner_fingerprints.get(owner_id):
                static_findings.append(
                    BlueprintFinding(
                        "stale_portable_owner",
                        "Portable model/system reference is not current.",
                        (owner_id,),
                        "stale",
                    )
                )

    resource_by_id = {resource.resource_id: resource for resource in manifest.resources}
    resource_kinds = {resource.kind for resource in manifest.resources}
    missing_resource_ids = set(manifest.required_resource_ids) - set(resource_by_id)
    missing_resource_kinds = set(manifest.required_resource_kinds) - resource_kinds
    if missing_resource_ids:
        static_findings.append(
            BlueprintFinding(
                "required_resource_missing",
                "A required blueprint resource is omitted.",
                tuple(missing_resource_ids),
                "blocked",
            )
        )
    if missing_resource_kinds:
        static_findings.append(
            BlueprintFinding(
                "required_resource_kind_missing",
                "A required blueprint resource kind is omitted.",
                tuple(missing_resource_kinds),
                "blocked",
            )
        )
    if current_resource_fingerprints is not None:
        for resource_item in manifest.resources:
            if resource_item.disposition != "current":
                continue
            if resource_item.artifact_fingerprint != current_resource_fingerprints.get(
                resource_item.resource_id
            ):
                static_findings.append(
                    BlueprintFinding(
                        "stale_resource_reference",
                        "Blueprint resource reference is not current.",
                        (resource_item.resource_id,),
                        "stale",
                    )
                )
    oracle_ids = {oracle.oracle_id for oracle in manifest.oracles}
    missing_oracle_ids = set(manifest.required_oracle_ids) - oracle_ids
    if missing_oracle_ids:
        static_findings.append(
            BlueprintFinding(
                "required_oracle_missing",
                "A required blueprint oracle is omitted.",
                tuple(missing_oracle_ids),
                "blocked",
            )
        )
    if current_oracle_fingerprints is not None:
        for oracle_item in manifest.oracles:
            if oracle_item.artifact_fingerprint != current_oracle_fingerprints.get(
                oracle_item.oracle_id
            ):
                static_findings.append(
                    BlueprintFinding(
                        "stale_oracle_reference",
                        "Blueprint oracle reference is not current.",
                        (oracle_item.oracle_id,),
                        "stale",
                    )
                )

    static_status = _status_from_findings(static_findings)
    empirical_findings: list[BlueprintFinding] = []
    empirical_status = RECONSTRUCTION_NOT_RUN
    if reconstruction_evidence is not None:
        empirical_status = reconstruction_evidence.status
        if reconstruction_evidence.blueprint_fingerprint != manifest.fingerprint:
            empirical_status = RECONSTRUCTION_BLOCKED
            empirical_findings.append(
                BlueprintFinding(
                    "reconstruction_blueprint_mismatch",
                    "Reconstruction receipt belongs to a different blueprint fingerprint.",
                    (reconstruction_evidence.receipt_id,),
                    "blocked",
                )
            )
        if not reconstruction_evidence.isolated_environment:
            empirical_status = RECONSTRUCTION_BLOCKED
            empirical_findings.append(
                BlueprintFinding(
                    "reconstruction_not_isolated",
                    "Reconstruction evidence does not declare an isolated environment.",
                    (reconstruction_evidence.receipt_id,),
                    "blocked",
                )
            )
        if not reconstruction_evidence.source_access_policy:
            empirical_status = RECONSTRUCTION_BLOCKED
            empirical_findings.append(
                BlueprintFinding(
                    "source_access_policy_missing",
                    "Reconstruction evidence lacks its source-access policy.",
                    (reconstruction_evidence.receipt_id,),
                    "blocked",
                )
            )
        missing_covered = set(manifest.required_oracle_ids) - set(
            reconstruction_evidence.covered_oracle_ids
        )
        if missing_covered:
            empirical_status = RECONSTRUCTION_BLOCKED
            empirical_findings.append(
                BlueprintFinding(
                    "reconstruction_oracle_coverage_missing",
                    "Reconstruction evidence omits required oracles.",
                    tuple(missing_covered),
                    "blocked",
                )
            )
        if not reconstruction_evidence.environment_fingerprint or not reconstruction_evidence.evidence_fingerprint:
            empirical_status = RECONSTRUCTION_BLOCKED
            empirical_findings.append(
                BlueprintFinding(
                    "reconstruction_evidence_identity_missing",
                    "Reconstruction environment or evidence fingerprint is missing.",
                    (reconstruction_evidence.receipt_id,),
                    "blocked",
                )
            )

    ordered_static_findings = tuple(
        sorted(static_findings, key=lambda item: (item.severity, item.code, item.member_ids))
    )
    ordered_empirical_findings = tuple(
        sorted(empirical_findings, key=lambda item: (item.severity, item.code, item.member_ids))
    )

    inventory_codes = {
        "inventory_identity_missing",
        "stale_inventory_artifact",
        "stale_inventory_reference",
        "implementation_inventory_blocker",
        "hidden_state_or_effect_writer",
        "unresolved_implementation_surface",
        "implementation_parse_failure",
    }
    traceability_codes = {
        "duplicate_binding_identity",
        "missing_primary_implementation",
        "duplicate_primary_implementation",
        "unbound_behavior_surface",
        "missing_inventory_surface",
        "orphan_supporting_surface",
        "stale_implementation_binding",
        "stale_model_binding",
        "stale_owner_contract",
        "stale_binding_report_reference",
    }
    semantic_codes = {
        "missing_semantic_reference",
        "semantic_dimensions_incomplete",
        "source_observation_not_independent",
        "stale_semantic_specification",
        "stale_semantic_mesh",
        "stale_observed_model_snapshot",
    }
    test_codes = {
        "model_test_binding_missing",
        "test_evidence_fingerprint_missing",
        "stale_test_evidence_binding",
        "stale_test_inventory",
        "stale_model_test_alignment_report",
    }
    resource_codes = {
        "missing_oracle_reference",
        "oracle_dimensions_incomplete",
        "stale_oracle_reference",
        "required_resource_missing",
        "required_resource_kind_missing",
        "stale_resource_reference",
        "required_oracle_missing",
        "stale_portable_owner",
    }

    def layer_result(layer_id: str, codes: set[str]) -> BlueprintLayerResult:
        selected = tuple(item for item in ordered_static_findings if item.code in codes)
        return BlueprintLayerResult(
            layer_id=layer_id,
            status=_status_from_findings(selected),
            finding_codes=tuple(item.code for item in selected),
            member_ids=tuple(member for item in selected for member in item.member_ids),
        )

    layers = (
        layer_result(BLUEPRINT_LAYER_INVENTORY, inventory_codes),
        layer_result(BLUEPRINT_LAYER_TRACEABILITY, traceability_codes),
        layer_result(BLUEPRINT_LAYER_INDEPENDENT_SEMANTICS, semantic_codes),
        layer_result(BLUEPRINT_LAYER_MODEL_CODE_TEST, test_codes),
        layer_result(BLUEPRINT_LAYER_RESOURCE_ORACLE, resource_codes),
        BlueprintLayerResult(
            BLUEPRINT_LAYER_STATIC,
            static_status,
            tuple(item.code for item in ordered_static_findings),
            tuple(member for item in ordered_static_findings for member in item.member_ids),
        ),
        BlueprintLayerResult(
            BLUEPRINT_LAYER_EMPIRICAL,
            empirical_status,
            tuple(item.code for item in ordered_empirical_findings),
            tuple(member for item in ordered_empirical_findings for member in item.member_ids),
        ),
    )

    return SoftwareBlueprintQualificationReport(
        blueprint_id=manifest.blueprint_id,
        blueprint_fingerprint=manifest.fingerprint,
        static_status=static_status,
        empirical_status=empirical_status,
        static_findings=ordered_static_findings,
        empirical_findings=ordered_empirical_findings,
        reconstruction_required=reconstruction_required,
        layers=layers,
    )


@dataclass(frozen=True)
class AffectedBlueprintNeighborhood:
    changed_member_ids: tuple[str, ...]
    affected_binding_ids: tuple[str, ...]
    affected_model_element_ids: tuple[str, ...]
    affected_implementation_surface_ids: tuple[str, ...]
    affected_semantic_spec_ids: tuple[str, ...]
    affected_oracle_ids: tuple[str, ...]
    affected_resource_ids: tuple[str, ...]

    @property
    def all_member_ids(self) -> tuple[str, ...]:
        return _tuple(
            (*self.changed_member_ids, *self.affected_binding_ids, *self.affected_model_element_ids,
             *self.affected_implementation_surface_ids, *self.affected_semantic_spec_ids,
             *self.affected_oracle_ids, *self.affected_resource_ids)
        )


def derive_affected_blueprint_neighborhood(
    bindings: Sequence[ModelImplementationBinding],
    *,
    changed_member_ids: Iterable[str],
    resource_ids: Iterable[str] = (),
) -> AffectedBlueprintNeighborhood:
    """Compute the smallest transitive binding neighborhood for changed identities."""

    changed = set(_tuple(changed_member_ids))
    closure = set(changed)
    groups: list[set[str]] = []
    for binding in bindings:
        groups.append(
            {
                binding.binding_id,
                binding.model_element_id,
                binding.implementation_surface_id,
                binding.owner_contract_id,
                *binding.semantic_spec_ids,
                *binding.oracle_ids,
                *binding.consumer_surface_ids,
            }
        )
    advanced = True
    while advanced:
        advanced = False
        for group in groups:
            if closure.intersection(group) and not group.issubset(closure):
                closure.update(group)
                advanced = True
    resource_set = set(_tuple(resource_ids))
    return AffectedBlueprintNeighborhood(
        changed_member_ids=_tuple(changed),
        affected_binding_ids=_tuple(binding.binding_id for binding in bindings if binding.binding_id in closure),
        affected_model_element_ids=_tuple(binding.model_element_id for binding in bindings if binding.model_element_id in closure),
        affected_implementation_surface_ids=_tuple(binding.implementation_surface_id for binding in bindings if binding.implementation_surface_id in closure),
        affected_semantic_spec_ids=_tuple(spec_id for binding in bindings for spec_id in binding.semantic_spec_ids if spec_id in closure),
        affected_oracle_ids=_tuple(oracle_id for binding in bindings for oracle_id in binding.oracle_ids if oracle_id in closure),
        affected_resource_ids=_tuple(resource_set.intersection(changed)),
    )


@dataclass(frozen=True)
class BlueprintShard:
    shard_id: str
    kind: str
    relative_path: str
    member_ids: tuple[str, ...]
    payload: tuple[dict[str, Any], ...]
    content_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_ids", _tuple(self.member_ids))
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or ":" in path.parts[0]
            or self.relative_path.startswith(("\\", "//"))
        ):
            raise BlueprintValidationError("blueprint shard path escapes its projection root")
        if _contains_forbidden_key(self.payload, _FORBIDDEN_SOURCE_KEYS):
            raise BlueprintValidationError("production source text is excluded from blueprint shards")
        expected = fingerprint_value(to_jsonable(list(self.payload)))
        if self.content_fingerprint != expected:
            raise BlueprintValidationError("blueprint shard content fingerprint mismatch")
        expected_id = f"{self.kind}:{self.content_fingerprint}"
        if self.shard_id != expected_id:
            raise BlueprintValidationError("blueprint shard identity is not content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "kind": self.kind,
            "relative_path": self.relative_path,
            "member_ids": list(self.member_ids),
            "payload": list(self.payload),
            "content_fingerprint": self.content_fingerprint,
        }


@dataclass(frozen=True)
class SoftwareBlueprintProjection:
    blueprint_fingerprint: str
    shards: tuple[BlueprintShard, ...]
    reused_shard_ids: tuple[str, ...] = ()
    regenerated_shard_ids: tuple[str, ...] = ()
    affected_member_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "shards", tuple(sorted(self.shards, key=lambda item: item.kind)))
        for name in ("reused_shard_ids", "regenerated_shard_ids", "affected_member_ids"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))

    def manifest_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BLUEPRINT_SCHEMA_VERSION,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "shards": [
                {
                    "shard_id": shard.shard_id,
                    "kind": shard.kind,
                    "relative_path": shard.relative_path,
                    "member_ids": list(shard.member_ids),
                    "content_fingerprint": shard.content_fingerprint,
                }
                for shard in self.shards
            ],
        }

    @property
    def fingerprint(self) -> str:
        # Reuse/regeneration provenance does not alter canonical projection identity.
        return _fingerprinted(self.manifest_dict())


def _make_shard(kind: str, members: Sequence[Any]) -> BlueprintShard:
    payload_rows = [_canonical_dict(member) for member in members]
    payload_rows.sort(key=lambda value: fingerprint_value(value))
    payload = tuple(payload_rows)
    digest = fingerprint_value(list(payload))
    member_ids: list[str] = []
    for row in payload:
        for key in (
            "binding_id", "semantic_spec_id", "oracle_id", "resource_id", "blueprint_id"
        ):
            if row.get(key):
                member_ids.append(str(row[key]))
                break
    return BlueprintShard(
        shard_id=f"{kind}:{digest}",
        kind=kind,
        relative_path=f"shards/{kind}-{digest.removeprefix('sha256:')}.json",
        member_ids=_tuple(member_ids),
        payload=payload,
        content_fingerprint=digest,
    )


def project_software_blueprint(
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
    *,
    implementation_inventory: Any,
    previous_projection: SoftwareBlueprintProjection | None = None,
    affected_neighborhood: AffectedBlueprintNeighborhood | None = None,
) -> SoftwareBlueprintProjection:
    """Create a canonical projection, reusing exact unaffected content shards."""

    inventory_fingerprint = str(
        _value(
            implementation_inventory,
            "inventory_fingerprint",
            _value(implementation_inventory, "fingerprint", ""),
        )
    )
    if inventory_fingerprint != manifest.inventory_fingerprint:
        raise BlueprintValidationError(
            "blueprint projection inventory does not match the manifest fingerprint"
        )
    candidates = (
        _make_shard("identity", (manifest,)),
        _make_shard("inventory", (implementation_inventory,)),
        _make_shard("bindings", binding_report.bindings),
        _make_shard("semantics", binding_report.semantic_specs),
        _make_shard("oracles", manifest.oracles),
        _make_shard("resources", manifest.resources),
        _make_shard("gaps", binding_report.findings),
    )
    old_by_kind = {
        shard.kind: shard for shard in previous_projection.shards
    } if previous_projection is not None else {}
    affected = set(affected_neighborhood.all_member_ids) if affected_neighborhood else set()
    shards: list[BlueprintShard] = []
    reused: list[str] = []
    regenerated: list[str] = []
    for candidate in candidates:
        previous = old_by_kind.get(candidate.kind)
        category_affected = bool(affected.intersection(candidate.member_ids))
        if previous is not None and previous.content_fingerprint == candidate.content_fingerprint and not category_affected:
            shards.append(previous)
            reused.append(previous.shard_id)
        else:
            shards.append(candidate)
            regenerated.append(candidate.shard_id)
    return SoftwareBlueprintProjection(
        blueprint_fingerprint=manifest.fingerprint,
        shards=tuple(shards),
        reused_shard_ids=_tuple(reused),
        regenerated_shard_ids=_tuple(regenerated),
        affected_member_ids=_tuple(affected),
    )


@dataclass(frozen=True)
class BlueprintProjectionVerification:
    ok: bool
    status: str
    findings: tuple[BlueprintFinding, ...]
    projection_fingerprint: str | None = None


def verify_blueprint_projection(
    projection: SoftwareBlueprintProjection,
    *,
    expected_blueprint_fingerprint: str | None = None,
    expected_projection_fingerprint: str | None = None,
    materialized_shards: Mapping[str, Mapping[str, Any]] | None = None,
) -> BlueprintProjectionVerification:
    """Fail closed on missing, escaped, tampered, or non-canonical shards."""

    findings: list[BlueprintFinding] = []
    if expected_blueprint_fingerprint is not None and (
        projection.blueprint_fingerprint != expected_blueprint_fingerprint
    ):
        findings.append(
            BlueprintFinding(
                "projection_blueprint_mismatch",
                "Projection belongs to a different blueprint fingerprint.",
                severity="stale",
            )
        )
    if (
        expected_projection_fingerprint is not None
        and projection.fingerprint != expected_projection_fingerprint
    ):
        findings.append(
            BlueprintFinding(
                "projection_reexport_mismatch",
                "Re-exported canonical projection identity does not match the expected identity.",
                severity="stale",
            )
        )
    kinds = [shard.kind for shard in projection.shards]
    if len(kinds) != len(set(kinds)):
        findings.append(
            BlueprintFinding(
                "duplicate_projection_shard_kind",
                "Projection has more than one shard for a canonical kind.",
                tuple(kinds),
                "blocked",
            )
        )
    for shard in projection.shards:
        try:
            BlueprintShard(**{
                "shard_id": shard.shard_id,
                "kind": shard.kind,
                "relative_path": shard.relative_path,
                "member_ids": shard.member_ids,
                "payload": shard.payload,
                "content_fingerprint": shard.content_fingerprint,
            })
        except BlueprintValidationError as error:
            findings.append(
                BlueprintFinding(
                    "invalid_projection_shard",
                    str(error),
                    (shard.shard_id,),
                    "blocked",
                )
            )
            continue
        if materialized_shards is not None:
            materialized = materialized_shards.get(shard.relative_path)
            if materialized is None:
                findings.append(
                    BlueprintFinding(
                        "projection_shard_missing",
                        "A manifest shard is missing from the supplied projection.",
                        (shard.shard_id,),
                        "blocked",
                    )
                )
            else:
                payload = materialized.get("payload") if isinstance(materialized, Mapping) else None
                if fingerprint_value(to_jsonable(payload)) != shard.content_fingerprint:
                    findings.append(
                        BlueprintFinding(
                            "projection_shard_tampered",
                            "A materialized shard does not match its content fingerprint.",
                            (shard.shard_id,),
                            "blocked",
                        )
                    )

    if materialized_shards is not None:
        expected_paths = {shard.relative_path for shard in projection.shards}
        unexpected_paths = set(materialized_shards) - expected_paths
        if unexpected_paths:
            findings.append(
                BlueprintFinding(
                    "unexpected_projection_shard",
                    "Materialized projection contains a shard absent from the canonical manifest.",
                    tuple(unexpected_paths),
                    "blocked",
                )
            )

    status = _status_from_findings(findings)
    return BlueprintProjectionVerification(
        ok=not findings,
        status=status,
        findings=tuple(findings),
        projection_fingerprint=projection.fingerprint if not findings else None,
    )


def _strict_payload(
    value: Any,
    *,
    context: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BlueprintValidationError(f"{context} must be a JSON object")
    data = {str(key): item for key, item in value.items()}
    missing = required - set(data)
    unexpected = set(data) - required - optional
    if missing or unexpected:
        raise BlueprintValidationError(
            f"{context} fields are not current: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    return data


def _require_blueprint_schema(data: Mapping[str, Any], *, context: str) -> None:
    if data.get("schema_version") != BLUEPRINT_SCHEMA_VERSION:
        raise BlueprintValidationError(
            f"{context} requires schema_version {BLUEPRINT_SCHEMA_VERSION!r}"
        )


def _finding_from_dict(value: Any) -> BlueprintFinding:
    data = _strict_payload(
        value,
        context="blueprint finding",
        required=frozenset({"code", "message", "member_ids", "severity"}),
    )
    return BlueprintFinding(
        code=str(data["code"]),
        message=str(data["message"]),
        member_ids=tuple(str(item) for item in data["member_ids"]),
        severity=str(data["severity"]),
    )


def _semantic_spec_from_dict(value: Any) -> SemanticSpecReference:
    data = _strict_payload(
        value,
        context="semantic specification reference",
        required=frozenset(
            {
                "semantic_spec_id",
                "owner_id",
                "artifact_id",
                "artifact_fingerprint",
                "covered_model_element_ids",
                "covered_dimensions",
                "semantics",
                "authority_kind",
                "provenance_fingerprints",
            }
        ),
    )
    provenance = data["provenance_fingerprints"]
    if not isinstance(provenance, Mapping):
        raise BlueprintValidationError(
            "semantic specification provenance fingerprints must be a JSON object"
        )
    return SemanticSpecReference(
        semantic_spec_id=str(data["semantic_spec_id"]),
        owner_id=str(data["owner_id"]),
        artifact_id=str(data["artifact_id"]),
        artifact_fingerprint=str(data["artifact_fingerprint"]),
        covered_model_element_ids=tuple(
            str(item) for item in data["covered_model_element_ids"]
        ),
        covered_dimensions=tuple(str(item) for item in data["covered_dimensions"]),
        semantics=tuple(
            (str(key), str(item))
            for key, item in _strict_payload(
                data["semantics"],
                context="semantic specification semantics",
                required=frozenset(str(item) for item in data["covered_dimensions"]),
            ).items()
        ),
        authority_kind=str(data["authority_kind"]),
        provenance_fingerprints=tuple(
            (str(key), str(item)) for key, item in provenance.items()
        ),
    )


def _oracle_from_dict(value: Any) -> OracleReference:
    data = _strict_payload(
        value,
        context="oracle reference",
        required=frozenset(
            {
                "oracle_id",
                "owner_id",
                "artifact_id",
                "artifact_fingerprint",
                "covered_model_element_ids",
                "covered_dimensions",
                "semantics",
            }
        ),
    )
    return OracleReference(
        oracle_id=str(data["oracle_id"]),
        owner_id=str(data["owner_id"]),
        artifact_id=str(data["artifact_id"]),
        artifact_fingerprint=str(data["artifact_fingerprint"]),
        covered_model_element_ids=tuple(
            str(item) for item in data["covered_model_element_ids"]
        ),
        covered_dimensions=tuple(str(item) for item in data["covered_dimensions"]),
        semantics=tuple(
            (str(key), str(item))
            for key, item in _strict_payload(
                data["semantics"],
                context="oracle semantics",
                required=frozenset(str(item) for item in data["covered_dimensions"]),
            ).items()
        ),
    )


def _resource_from_dict(value: Any) -> BlueprintResourceReference:
    data = _strict_payload(
        value,
        context="blueprint resource reference",
        required=frozenset(
            {
                "resource_id",
                "kind",
                "owner_id",
                "artifact_id",
                "purpose",
                "lifecycle_role",
                "disposition",
                "artifact_fingerprint",
                "rationale",
                "semantics",
            }
        ),
    )
    semantics = data["semantics"]
    if not isinstance(semantics, Mapping):
        raise BlueprintValidationError("resource semantics must be a JSON object")
    return BlueprintResourceReference(
        resource_id=str(data["resource_id"]),
        kind=str(data["kind"]),
        owner_id=str(data["owner_id"]),
        artifact_id=str(data["artifact_id"]),
        purpose=str(data["purpose"]),
        lifecycle_role=str(data["lifecycle_role"]),
        disposition=str(data["disposition"]),
        artifact_fingerprint=(
            None
            if data["artifact_fingerprint"] is None
            else str(data["artifact_fingerprint"])
        ),
        rationale=None if data["rationale"] is None else str(data["rationale"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
    )


def _binding_from_dict(value: Any) -> ModelImplementationBinding:
    data = _strict_payload(
        value,
        context="model implementation binding",
        required=frozenset(
            {
                "binding_id",
                "model_element_id",
                "implementation_surface_id",
                "relation_kind",
                "owner_contract_id",
                "semantic_spec_ids",
                "oracle_ids",
                "required_dimensions",
                "consumer_surface_ids",
                "test_evidence_ids",
                "test_evidence_fingerprints",
                "primary",
                "delegating",
                "model_fingerprint",
                "implementation_fingerprint",
                "owner_contract_fingerprint",
            }
        ),
    )
    return ModelImplementationBinding(
        binding_id=str(data["binding_id"]),
        model_element_id=str(data["model_element_id"]),
        implementation_surface_id=str(data["implementation_surface_id"]),
        relation_kind=str(data["relation_kind"]),
        owner_contract_id=str(data["owner_contract_id"]),
        semantic_spec_ids=tuple(str(item) for item in data["semantic_spec_ids"]),
        oracle_ids=tuple(str(item) for item in data["oracle_ids"]),
        required_dimensions=tuple(str(item) for item in data["required_dimensions"]),
        consumer_surface_ids=tuple(str(item) for item in data["consumer_surface_ids"]),
        test_evidence_ids=tuple(str(item) for item in data["test_evidence_ids"]),
        test_evidence_fingerprints=tuple(
            (str(key), str(item))
            for key, item in _strict_payload(
                data["test_evidence_fingerprints"],
                context="binding test evidence fingerprints",
                required=frozenset(str(item) for item in data["test_evidence_ids"]),
            ).items()
        ),
        primary=bool(data["primary"]),
        delegating=bool(data["delegating"]),
        model_fingerprint=(
            None if data["model_fingerprint"] is None else str(data["model_fingerprint"])
        ),
        implementation_fingerprint=(
            None
            if data["implementation_fingerprint"] is None
            else str(data["implementation_fingerprint"])
        ),
        owner_contract_fingerprint=(
            None
            if data["owner_contract_fingerprint"] is None
            else str(data["owner_contract_fingerprint"])
        ),
    )


def model_implementation_binding_report_from_dict(
    value: Any,
) -> ModelImplementationBindingReport:
    required = frozenset(
        {
            "schema_version",
            "inventory_id",
            "inventory_fingerprint",
            "required_model_element_ids",
            "required_implementation_surface_ids",
            "bound_model_element_ids",
            "bound_implementation_surface_ids",
            "implementation_surface_ids",
            "model_obligation_ids",
            "semantic_spec_ids",
            "oracle_ids",
            "test_evidence_ids",
            "bindings",
            "semantic_specs",
            "oracles",
            "findings",
            "status",
        }
    )
    data = _strict_payload(value, context="binding report", required=required)
    _require_blueprint_schema(data, context="binding report")
    report = ModelImplementationBindingReport(
        inventory_id=str(data["inventory_id"]),
        inventory_fingerprint=str(data["inventory_fingerprint"]),
        required_model_element_ids=tuple(
            str(item) for item in data["required_model_element_ids"]
        ),
        required_implementation_surface_ids=tuple(
            str(item) for item in data["required_implementation_surface_ids"]
        ),
        bound_model_element_ids=tuple(
            str(item) for item in data["bound_model_element_ids"]
        ),
        bound_implementation_surface_ids=tuple(
            str(item) for item in data["bound_implementation_surface_ids"]
        ),
        bindings=tuple(_binding_from_dict(item) for item in data["bindings"]),
        semantic_specs=tuple(
            _semantic_spec_from_dict(item) for item in data["semantic_specs"]
        ),
        oracles=tuple(_oracle_from_dict(item) for item in data["oracles"]),
        findings=tuple(_finding_from_dict(item) for item in data["findings"]),
        status=str(data["status"]),
    )
    derived = {
        "implementation_surface_ids": list(report.implementation_surface_ids),
        "model_obligation_ids": list(report.model_obligation_ids),
        "semantic_spec_ids": list(report.semantic_spec_ids),
        "oracle_ids": list(report.oracle_ids),
        "test_evidence_ids": list(report.test_evidence_ids),
    }
    for key, expected in derived.items():
        if data[key] != expected:
            raise BlueprintValidationError(f"binding report derived field mismatch: {key}")
    return report


def software_blueprint_manifest_from_dict(value: Any) -> SoftwareBlueprintManifest:
    data = _strict_payload(
        value,
        context="software blueprint manifest",
        required=frozenset(
            {
                "schema_version",
                "blueprint_id",
                "observed_snapshot_id",
                "observed_snapshot_fingerprint",
                "inventory_id",
                "inventory_fingerprint",
                "binding_report_id",
                "binding_report_fingerprint",
                "semantic_mesh_id",
                "semantic_mesh_fingerprint",
                "test_inventory_id",
                "test_inventory_fingerprint",
                "model_test_alignment_report_id",
                "model_test_alignment_report_fingerprint",
                "portable_owner_fingerprints",
                "resources",
                "oracles",
                "required_resource_ids",
                "required_resource_kinds",
                "required_oracle_ids",
                "excluded_source_ids",
            }
        ),
    )
    _require_blueprint_schema(data, context="software blueprint manifest")
    portable = data["portable_owner_fingerprints"]
    if not isinstance(portable, Mapping):
        raise BlueprintValidationError("portable owner fingerprints must be a JSON object")
    return SoftwareBlueprintManifest(
        blueprint_id=str(data["blueprint_id"]),
        observed_snapshot_id=str(data["observed_snapshot_id"]),
        observed_snapshot_fingerprint=str(data["observed_snapshot_fingerprint"]),
        inventory_id=str(data["inventory_id"]),
        inventory_fingerprint=str(data["inventory_fingerprint"]),
        binding_report_id=str(data["binding_report_id"]),
        binding_report_fingerprint=str(data["binding_report_fingerprint"]),
        semantic_mesh_id=str(data["semantic_mesh_id"]),
        semantic_mesh_fingerprint=str(data["semantic_mesh_fingerprint"]),
        test_inventory_id=str(data["test_inventory_id"]),
        test_inventory_fingerprint=str(data["test_inventory_fingerprint"]),
        model_test_alignment_report_id=str(data["model_test_alignment_report_id"]),
        model_test_alignment_report_fingerprint=str(
            data["model_test_alignment_report_fingerprint"]
        ),
        portable_owner_fingerprints=tuple(
            (str(key), str(item)) for key, item in portable.items()
        ),
        resources=tuple(_resource_from_dict(item) for item in data["resources"]),
        oracles=tuple(_oracle_from_dict(item) for item in data["oracles"]),
        required_resource_ids=tuple(str(item) for item in data["required_resource_ids"]),
        required_resource_kinds=tuple(
            str(item) for item in data["required_resource_kinds"]
        ),
        required_oracle_ids=tuple(str(item) for item in data["required_oracle_ids"]),
        excluded_source_ids=tuple(str(item) for item in data["excluded_source_ids"]),
    )


def reconstruction_evidence_from_dict(value: Any) -> ReconstructionEvidence:
    data = _strict_payload(
        value,
        context="reconstruction evidence",
        required=frozenset(
            {
                "receipt_id",
                "blueprint_fingerprint",
                "environment_fingerprint",
                "isolated_environment",
                "source_access_policy",
                "covered_oracle_ids",
                "evidence_fingerprint",
                "status",
            }
        ),
    )
    return ReconstructionEvidence(
        receipt_id=str(data["receipt_id"]),
        blueprint_fingerprint=str(data["blueprint_fingerprint"]),
        environment_fingerprint=str(data["environment_fingerprint"]),
        isolated_environment=bool(data["isolated_environment"]),
        source_access_policy=str(data["source_access_policy"]),
        covered_oracle_ids=tuple(str(item) for item in data["covered_oracle_ids"]),
        evidence_fingerprint=str(data["evidence_fingerprint"]),
        status=str(data["status"]),
    )


def _load_json_blueprint(path: str | Path, *, context: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BlueprintValidationError(f"cannot load {context}: {exc}") from exc
    if not isinstance(value, dict):
        raise BlueprintValidationError(f"{context} must be a JSON object")
    return value


def load_model_implementation_binding_report(
    path: str | Path,
) -> ModelImplementationBindingReport:
    return model_implementation_binding_report_from_dict(
        _load_json_blueprint(path, context="binding report")
    )


def load_software_blueprint_manifest(path: str | Path) -> SoftwareBlueprintManifest:
    return software_blueprint_manifest_from_dict(
        _load_json_blueprint(path, context="software blueprint manifest")
    )


def load_reconstruction_evidence(path: str | Path) -> ReconstructionEvidence:
    return reconstruction_evidence_from_dict(
        _load_json_blueprint(path, context="reconstruction evidence")
    )


def serialize_software_blueprint_projection(
    projection: SoftwareBlueprintProjection,
) -> dict[str, bytes]:
    """Return canonical projection files without writing them."""

    files = {
        "manifest.json": canonical_json_bytes(
            {
                **projection.manifest_dict(),
                "projection_fingerprint": projection.fingerprint,
            }
        )
        + b"\n"
    }
    for shard in projection.shards:
        files[shard.relative_path] = canonical_json_bytes(
            {
                "schema_version": BLUEPRINT_SCHEMA_VERSION,
                **shard.to_dict(),
            }
        ) + b"\n"
    return files


def write_software_blueprint_projection(
    projection: SoftwareBlueprintProjection,
    output_root: str | Path,
) -> tuple[Path, ...]:
    """Explicitly materialize and verify one bounded canonical projection."""

    root = Path(output_root).resolve()
    files = serialize_software_blueprint_projection(projection)
    written: list[Path] = []
    for relative, content in sorted(files.items()):
        target = (root / PurePosixPath(relative)).resolve()
        if target != root and root not in target.parents:
            raise BlueprintValidationError("blueprint output path escapes its projection root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(target)

    materialized: dict[str, Mapping[str, Any]] = {}
    shard_root = root / "shards"
    existing_shards = sorted(shard_root.glob("*.json")) if shard_root.exists() else []
    expected_paths = {shard.relative_path for shard in projection.shards}
    for target in existing_shards:
        relative = target.relative_to(root).as_posix()
        materialized[relative] = _load_json_blueprint(target, context="projection shard")
    if set(materialized) != expected_paths:
        raise BlueprintValidationError("materialized projection contains missing or stale shards")
    verification = verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=projection.blueprint_fingerprint,
        expected_projection_fingerprint=projection.fingerprint,
        materialized_shards=materialized,
    )
    if not verification.ok:
        raise BlueprintValidationError(
            "; ".join(finding.message for finding in verification.findings)
        )
    return tuple(written)


__all__ = [
    "AffectedBlueprintNeighborhood",
    "BLUEPRINT_SCHEMA_VERSION",
    "BlueprintFinding",
    "BlueprintProjectionVerification",
    "BlueprintResourceReference",
    "BlueprintShard",
    "BlueprintValidationError",
    "ModelImplementationBinding",
    "ModelImplementationBindingReport",
    "OracleReference",
    "ReconstructionEvidence",
    "SemanticSpecReference",
    "SoftwareBlueprintManifest",
    "SoftwareBlueprintProjection",
    "SoftwareBlueprintQualificationReport",
    "derive_affected_blueprint_neighborhood",
    "load_model_implementation_binding_report",
    "load_reconstruction_evidence",
    "load_software_blueprint_manifest",
    "model_implementation_binding_report_from_dict",
    "project_software_blueprint",
    "qualify_software_blueprint",
    "reconstruction_evidence_from_dict",
    "review_model_implementation_bindings",
    "serialize_software_blueprint_projection",
    "software_blueprint_manifest_from_dict",
    "verify_blueprint_projection",
    "write_software_blueprint_projection",
]
