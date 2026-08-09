"""Implementation-blueprint closure and deterministic projection.

This module deliberately consumes an implementation inventory by protocol
(attribute or mapping access).  Discovery remains owned by
``implementation_inventory``; importing that module here would couple two
independent authorities and would make partial/affected-only consumers load a
repository scanner unnecessarily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import stat
import tempfile
from typing import Any, Iterable, Mapping, Sequence
import uuid
import warnings

from ._normalization import unique_sorted_strings as _tuple
from .evidence_receipts import fingerprint_value
from .export import to_jsonable
from .portable_model import canonical_json_bytes


BLUEPRINT_SCHEMA_VERSION = "1.2"

STATIC_COMPLETE = "complete"
STATIC_INCOMPLETE = "incomplete"
STATIC_STALE = "stale"
STATIC_BLOCKED = "blocked"
STATIC_STATUSES = frozenset(
    {STATIC_COMPLETE, STATIC_INCOMPLETE, STATIC_STALE, STATIC_BLOCKED}
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
BLUEPRINT_LAYER_IDS = (
    BLUEPRINT_LAYER_INVENTORY,
    BLUEPRINT_LAYER_TRACEABILITY,
    BLUEPRINT_LAYER_INDEPENDENT_SEMANTICS,
    BLUEPRINT_LAYER_MODEL_CODE_TEST,
    BLUEPRINT_LAYER_RESOURCE_ORACLE,
    BLUEPRINT_LAYER_STATIC,
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
    source_id: str
    source_owner_id: str
    source_content_fingerprint: str
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
            (
                self.semantic_spec_id,
                self.owner_id,
                self.artifact_id,
                self.artifact_fingerprint,
                self.source_id,
                self.source_owner_id,
                self.source_content_fingerprint,
            )
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
            "source_id": self.source_id,
            "source_owner_id": self.source_owner_id,
            "source_content_fingerprint": self.source_content_fingerprint,
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
    source_id: str
    source_owner_id: str
    source_content_fingerprint: str
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
        if not all(
            (
                self.oracle_id,
                self.owner_id,
                self.artifact_id,
                self.artifact_fingerprint,
                self.source_id,
                self.source_owner_id,
                self.source_content_fingerprint,
            )
        ):
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
            "source_id": self.source_id,
            "source_owner_id": self.source_owner_id,
            "source_content_fingerprint": self.source_content_fingerprint,
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
    consuming_behavior_ids: tuple[str, ...]
    consuming_model_ids: tuple[str, ...]
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
        object.__setattr__(
            self, "consuming_behavior_ids", _tuple(self.consuming_behavior_ids)
        )
        object.__setattr__(self, "consuming_model_ids", _tuple(self.consuming_model_ids))
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
            "consuming_behavior_ids": list(self.consuming_behavior_ids),
            "consuming_model_ids": list(self.consuming_model_ids),
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
    model_obligation_ids: tuple[str, ...]
    implementation_surface_id: str
    relation_kind: str
    owner_contract_id: str
    implementation_source_id: str
    implementation_owner_id: str
    implementation_content_fingerprint: str
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
            "model_obligation_ids",
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
        if not self.model_obligation_ids:
            raise BlueprintValidationError(
                "binding requires at least one exact model obligation identity"
            )
        if not all(
            (
                self.binding_id,
                self.model_element_id,
                self.implementation_surface_id,
                self.owner_contract_id,
                self.implementation_source_id,
                self.implementation_owner_id,
                self.implementation_content_fingerprint,
            )
        ):
            raise BlueprintValidationError("binding identity is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "model_element_id": self.model_element_id,
            "model_obligation_ids": list(self.model_obligation_ids),
            "implementation_surface_id": self.implementation_surface_id,
            "relation_kind": self.relation_kind,
            "owner_contract_id": self.owner_contract_id,
            "implementation_source_id": self.implementation_source_id,
            "implementation_owner_id": self.implementation_owner_id,
            "implementation_content_fingerprint": self.implementation_content_fingerprint,
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

    @cached_property
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
        """Exact obligations owned by direct implementation bindings.

        Supporting bindings keep the same obligation identities for
        traceability, but they do not become a second implementation owner.
        """

        return _tuple(
            obligation_id
            for binding in self.bindings
            if binding.relation_kind != "supports"
            for obligation_id in binding.model_obligation_ids
        )

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
    if disposition:
        return disposition == "model_implementation"
    return bool(
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

    bindings_by_surface: dict[str, list[ModelImplementationBinding]] = {}
    for binding in ordered_bindings:
        bindings_by_surface.setdefault(
            binding.implementation_surface_id,
            [],
        ).append(binding)

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
    declared_primary_models = set(primary_by_model) - required_models
    if declared_primary_models:
        findings.append(
            BlueprintFinding(
                "declared_model_element_unobserved",
                "Primary model declarations are absent from the independent required-model denominator.",
                tuple(sorted(declared_primary_models)),
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
    declared_primary_surfaces = {
        binding.implementation_surface_id
        for binding in ordered_bindings
        if binding.primary and not binding.delegating
    } - required_surfaces
    if declared_primary_surfaces:
        findings.append(
            BlueprintFinding(
                "declared_implementation_surface_unobserved",
                "Primary implementation bindings are absent from the independent required-surface denominator.",
                tuple(sorted(declared_primary_surfaces)),
                "blocked",
            )
        )

    referenced_spec_ids = {
        spec_id for binding in ordered_bindings for spec_id in binding.semantic_spec_ids
    }
    declared_spec_ids = set(spec_by_id) - referenced_spec_ids
    if declared_spec_ids:
        findings.append(
            BlueprintFinding(
                "declared_semantic_spec_unobserved",
                "Semantic specifications are declared but no observed binding consumes them.",
                tuple(sorted(declared_spec_ids)),
            )
        )
    referenced_oracle_ids = {
        oracle_id for binding in ordered_bindings for oracle_id in binding.oracle_ids
    }
    declared_oracle_ids = set(oracle_by_id) - referenced_oracle_ids
    if declared_oracle_ids:
        findings.append(
            BlueprintFinding(
                "declared_oracle_unobserved",
                "Oracles are declared but no observed binding consumes them.",
                tuple(sorted(declared_oracle_ids)),
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

        if binding.relation_kind == "supports":
            owner_surface_id = str(
                _value(
                    surface,
                    "owning_surface_id",
                    _value(surface, "supporting_owner_surface_id", ""),
                )
            )
            owner_bindings = tuple(
                candidate
                for candidate in bindings_by_surface.get(owner_surface_id, ())
                if candidate.relation_kind != "supports"
                and candidate.model_element_id == binding.model_element_id
                and candidate.owner_contract_id == binding.owner_contract_id
            )
            if len(owner_bindings) != 1:
                findings.append(
                    BlueprintFinding(
                        "supporting_obligation_owner_missing",
                        "Supporting binding does not resolve to one exact direct behavior obligation owner.",
                        (binding.binding_id, owner_surface_id),
                        "blocked",
                    )
                )
            elif (
                binding.model_obligation_ids
                != owner_bindings[0].model_obligation_ids
            ):
                findings.append(
                    BlueprintFinding(
                        "supporting_obligation_mismatch",
                        "Supporting binding obligation identities differ from its exact direct behavior owner.",
                        (
                            binding.binding_id,
                            owner_bindings[0].binding_id,
                            *binding.model_obligation_ids,
                        ),
                        "blocked",
                    )
                )

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
        if (
            not current_surface_fp
            or binding.implementation_content_fingerprint != current_surface_fp
        ):
            findings.append(
                BlueprintFinding(
                    "implementation_source_identity_mismatch",
                    "Binding implementation source content does not match the current observed surface.",
                    (
                        binding.binding_id,
                        binding.implementation_source_id,
                        binding.implementation_surface_id,
                    ),
                    "stale" if current_surface_fp else "blocked",
                )
            )
        observed_owner_id = str(_value(surface, "owner_id", ""))
        if observed_owner_id and observed_owner_id != binding.implementation_owner_id:
            findings.append(
                BlueprintFinding(
                    "implementation_source_owner_mismatch",
                    "Binding implementation owner differs from the independently observed surface owner.",
                    (
                        binding.binding_id,
                        binding.implementation_owner_id,
                        observed_owner_id,
                    ),
                    "blocked",
                )
            )

        referenced_specs = tuple(
            reference
            for spec_id in binding.semantic_spec_ids
            if (reference := spec_by_id.get(spec_id)) is not None
        )
        referenced_oracles = tuple(
            reference
            for oracle_id in binding.oracle_ids
            if (reference := oracle_by_id.get(oracle_id)) is not None
        )
        implementation_identity = (
            binding.implementation_source_id,
            binding.implementation_owner_id,
            binding.implementation_content_fingerprint,
        )
        certifies_surface_semantics = binding.relation_kind != "supports"
        for reference in referenced_specs:
            semantic_identity = (
                reference.source_id,
                reference.source_owner_id,
                reference.source_content_fingerprint,
            )
            if certifies_surface_semantics and (
                semantic_identity == implementation_identity
                or reference.source_id == binding.implementation_source_id
                or reference.source_content_fingerprint
                == binding.implementation_content_fingerprint
            ):
                findings.append(
                    BlueprintFinding(
                        "semantic_source_not_independent",
                        "Semantic specification source identity overlaps the implementation source identity.",
                        (
                            binding.binding_id,
                            reference.semantic_spec_id,
                            reference.source_id,
                            reference.source_owner_id,
                        ),
                        "blocked",
                    )
                )
        for reference in referenced_oracles:
            oracle_identity = (
                reference.source_id,
                reference.source_owner_id,
                reference.source_content_fingerprint,
            )
            if certifies_surface_semantics and (
                oracle_identity == implementation_identity
                or reference.source_id == binding.implementation_source_id
                or reference.source_content_fingerprint
                == binding.implementation_content_fingerprint
            ):
                findings.append(
                    BlueprintFinding(
                        "oracle_source_not_independent",
                        "Oracle source identity overlaps the implementation source identity.",
                        (
                            binding.binding_id,
                            reference.oracle_id,
                            reference.source_id,
                            reference.source_owner_id,
                        ),
                        "blocked",
                    )
                )
        for spec_reference in referenced_specs:
            for oracle_reference in referenced_oracles:
                if (
                    spec_reference.source_id == oracle_reference.source_id
                    or spec_reference.source_content_fingerprint
                    == oracle_reference.source_content_fingerprint
                ):
                    findings.append(
                        BlueprintFinding(
                            "semantic_oracle_source_not_independent",
                            "Semantic and oracle sources must retain distinct source and content identities.",
                            (
                                binding.binding_id,
                                spec_reference.semantic_spec_id,
                                oracle_reference.oracle_id,
                            ),
                            "blocked",
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

    @cached_property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


@dataclass(frozen=True)
class BlueprintLayerResult:
    layer_id: str
    status: str
    finding_codes: tuple[str, ...] = ()
    member_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.layer_id not in BLUEPRINT_LAYER_IDS:
            raise BlueprintValidationError(f"unknown blueprint layer: {self.layer_id}")
        if self.status not in STATIC_STATUSES:
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


_BLUEPRINT_MANIFEST_QUALIFICATION_TOKEN = object()
_BLUEPRINT_MANIFEST_QUALIFICATION_CLAIM_BOUNDARY = (
    "Static manifest identity, inventory, traceability, independent-semantics "
    "references, model-code-test bindings, resources, oracles, and current-"
    "fingerprint consistency only; this child report does not establish canonical "
    "target-system readiness, sufficient understanding, executed evidence, "
    "implementation admission, or release readiness."
)


@dataclass(frozen=True)
class BlueprintManifestQualificationReport:
    blueprint_id: str
    blueprint_fingerprint: str
    static_manifest_status: str
    layers: tuple[BlueprintLayerResult, ...]
    static_findings: tuple[BlueprintFinding, ...] = ()
    _derivation_token: object = field(
        default=None,
        repr=False,
        compare=False,
        kw_only=True,
    )

    @classmethod
    def _derived(cls, **values: Any) -> "BlueprintManifestQualificationReport":
        """Build the bounded child report from the private manifest qualifier."""

        return cls(
            _derivation_token=_BLUEPRINT_MANIFEST_QUALIFICATION_TOKEN,
            **values,
        )

    def __post_init__(self) -> None:
        if self._derivation_token is not _BLUEPRINT_MANIFEST_QUALIFICATION_TOKEN:
            raise BlueprintValidationError(
                "blueprint manifest qualification is derived by the private qualifier"
            )
        if not self.blueprint_id or not self.blueprint_fingerprint:
            raise BlueprintValidationError(
                "blueprint manifest qualification identity is incomplete"
            )
        if self.static_manifest_status not in STATIC_STATUSES:
            raise BlueprintValidationError(
                "blueprint manifest qualification status is invalid"
            )
        object.__setattr__(self, "static_findings", tuple(self.static_findings))
        object.__setattr__(self, "layers", tuple(self.layers))
        layer_ids = tuple(layer.layer_id for layer in self.layers)
        if layer_ids != BLUEPRINT_LAYER_IDS:
            raise BlueprintValidationError(
                "blueprint manifest qualification layers are not exact-current"
            )

    @property
    def static_manifest_ready(self) -> bool:
        return self.static_manifest_status == STATIC_COMPLETE

    @property
    def claim_boundary(self) -> str:
        return _BLUEPRINT_MANIFEST_QUALIFICATION_CLAIM_BOUNDARY

    def layer_status(self, layer_id: str) -> str:
        for layer in self.layers:
            if layer.layer_id == layer_id:
                return layer.status
        raise BlueprintValidationError(f"qualification has no layer: {layer_id}")

    @property
    def deepest_proven_layer(self) -> str:
        deepest = "none"
        for layer_id in BLUEPRINT_LAYER_IDS:
            if self.layer_status(layer_id) != STATIC_COMPLETE:
                break
            deepest = layer_id
        return deepest

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "static_manifest_status": self.static_manifest_status,
            "static_manifest_ready": self.static_manifest_ready,
            "static_findings": [finding.to_dict() for finding in self.static_findings],
            "layers": [layer.to_dict() for layer in self.layers],
            "deepest_proven_layer": self.deepest_proven_layer,
            "claim_boundary": self.claim_boundary,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprinted(self.to_dict())


def _qualify_blueprint_manifest(
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
    *,
    implementation_inventory: Any | None = None,
    current_observed_snapshot_fingerprint: str | None = None,
    current_semantic_mesh_fingerprint: str | None = None,
    current_test_inventory_fingerprint: str | None = None,
    current_model_test_alignment_report_fingerprint: str | None = None,
    current_portable_owner_fingerprints: Mapping[str, str] | None = None,
    current_resource_fingerprints: Mapping[str, str] | None = None,
    current_oracle_fingerprints: Mapping[str, str] | None = None,
) -> BlueprintManifestQualificationReport:
    """Derive bounded static-manifest consistency; never whole readiness."""

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
    for resource_item in manifest.resources:
        if resource_item.disposition != "current":
            continue
        missing_consumer_kinds: list[str] = []
        if not resource_item.consuming_behavior_ids:
            missing_consumer_kinds.append("behavior")
        if not resource_item.consuming_model_ids:
            missing_consumer_kinds.append("model")
        if missing_consumer_kinds:
            static_findings.append(
                BlueprintFinding(
                    "resource_consumer_binding_missing",
                    "Current blueprint resource lacks exact consuming behavior or model identities.",
                    (resource_item.resource_id, *missing_consumer_kinds),
                    "blocked",
                )
            )
        unknown_model_consumers = set(resource_item.consuming_model_ids) - set(
            binding_report.required_model_element_ids
        )
        if unknown_model_consumers:
            static_findings.append(
                BlueprintFinding(
                    "resource_model_consumer_unobserved",
                    "Resource references model consumers absent from the current binding denominator.",
                    (resource_item.resource_id, *tuple(sorted(unknown_model_consumers))),
                    "blocked",
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
    ordered_static_findings = tuple(
        sorted(static_findings, key=lambda item: (item.severity, item.code, item.member_ids))
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
        "declared_model_element_unobserved",
        "unbound_behavior_surface",
        "declared_implementation_surface_unobserved",
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
        "semantic_source_not_independent",
        "oracle_source_not_independent",
        "semantic_oracle_source_not_independent",
        "declared_semantic_spec_unobserved",
        "implementation_source_identity_mismatch",
        "implementation_source_owner_mismatch",
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
        "declared_oracle_unobserved",
        "oracle_dimensions_incomplete",
        "stale_oracle_reference",
        "required_resource_missing",
        "required_resource_kind_missing",
        "stale_resource_reference",
        "resource_consumer_binding_missing",
        "resource_model_consumer_unobserved",
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
    )

    return BlueprintManifestQualificationReport._derived(
        blueprint_id=manifest.blueprint_id,
        blueprint_fingerprint=manifest.fingerprint,
        static_manifest_status=static_status,
        layers=layers,
        static_findings=ordered_static_findings,
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
    resources: Sequence[BlueprintResourceReference],
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
    for resource in resources:
        groups.append(
            {
                resource.resource_id,
                *resource.consuming_behavior_ids,
                *resource.consuming_model_ids,
            }
        )
    advanced = True
    while advanced:
        advanced = False
        for group in groups:
            if closure.intersection(group) and not group.issubset(closure):
                closure.update(group)
                advanced = True
    resource_set = {resource.resource_id for resource in resources}
    return AffectedBlueprintNeighborhood(
        changed_member_ids=_tuple(changed),
        affected_binding_ids=_tuple(binding.binding_id for binding in bindings if binding.binding_id in closure),
        affected_model_element_ids=_tuple(binding.model_element_id for binding in bindings if binding.model_element_id in closure),
        affected_implementation_surface_ids=_tuple(binding.implementation_surface_id for binding in bindings if binding.implementation_surface_id in closure),
        affected_semantic_spec_ids=_tuple(spec_id for binding in bindings for spec_id in binding.semantic_spec_ids if spec_id in closure),
        affected_oracle_ids=_tuple(oracle_id for binding in bindings for oracle_id in binding.oracle_ids if oracle_id in closure),
        affected_resource_ids=_tuple(resource_set.intersection(closure)),
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
class CanonicalBlueprintProjection:
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
        explicit_member_ids = row.get("member_ids", ())
        if isinstance(explicit_member_ids, (list, tuple)):
            member_ids.extend(
                str(member_id) for member_id in explicit_member_ids if str(member_id)
            )
        for key in (
            "binding_id",
            "semantic_spec_id",
            "oracle_id",
            "behavior_block_id",
            "case_id",
            "contribution_id",
            "resource_id",
            "test_node_id",
            "node_id",
            "relation_id",
            "provider_id",
            "model_element_id",
            "member_id",
            "object_id",
            "behavior_shard_id",
            "inventory_id",
            "report_id",
            "evidence_id",
            "blueprint_id",
            "readiness_kind",
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


PROJECT_BLUEPRINT_PROJECTION_KINDS = (
    "affected_index",
    "behavior_model",
    "behavior_shards",
    "bindings",
    "identity",
    "implementation_inventory",
    "implementation_inventory_audit",
    "intent_lineage",
    "model_test_alignment",
    "normalized_index",
    "oracles",
    "project_definition",
    "project_evidence",
    "provider_evidence",
    "readiness",
    "resources",
    "semantics",
    "shared_objects",
    "test_inventory",
    "topology",
)


def project_canonical_software_blueprint(
    project_bundle: Any,
    *,
    previous_projection: CanonicalBlueprintProjection | None = None,
    affected_neighborhood: AffectedBlueprintNeighborhood | None = None,
) -> CanonicalBlueprintProjection:
    """Project every portable layer of one exact project-blueprint snapshot."""

    from .project_blueprint import ProjectBlueprintBundle

    if not isinstance(project_bundle, ProjectBlueprintBundle):
        raise BlueprintValidationError(
            "canonical project export requires the exact typed project blueprint bundle"
        )
    if not project_bundle.canonical_export_ready:
        raise BlueprintValidationError(
            "canonical project blueprint is missing export layers: "
            + ", ".join(project_bundle.canonical_export_blockers)
        )
    assert project_bundle.definition is not None
    assert project_bundle.project_evidence is not None
    assert project_bundle.frozen_target_evidence is not None
    assert project_bundle.behavior_report is not None
    assert project_bundle.model_test_alignment_report is not None
    assert project_bundle.topology_report is not None
    assert project_bundle.resource_inventory is not None
    assert project_bundle.intent_inventory is not None
    assert project_bundle.normalized_projection is not None
    assert project_bundle.normalized_affected_index is not None
    assert project_bundle.test_inventory is not None
    assert project_bundle.static_readiness is not None
    assert project_bundle.target_system_report is not None

    identity = {
        "schema_version": BLUEPRINT_SCHEMA_VERSION,
        "blueprint_id": project_bundle.manifest.blueprint_id,
        "projection_kind": "project_blueprint",
        "blueprint_fingerprint": project_bundle.fingerprint,
        "project_blueprint_fingerprint": project_bundle.fingerprint,
        "child_fingerprints": dict(project_bundle.canonical_child_fingerprints),
        "software_manifest_fingerprint": project_bundle.manifest.fingerprint,
        "software_manifest": project_bundle.manifest.to_dict(),
        "target_blueprint_fingerprint": project_bundle.target_system_report.fingerprint,
        "subject_revision": (
            project_bundle.target_system_report.descriptor.subject_revision
        ),
    }
    binding_report = {
        "report_id": project_bundle.manifest.binding_report_id,
        "report_fingerprint": project_bundle.binding_report.fingerprint,
        "member_ids": [
            project_bundle.manifest.binding_report_id,
            *(binding.binding_id for binding in project_bundle.binding_report.bindings),
            *project_bundle.binding_report.required_model_element_ids,
            *project_bundle.binding_report.required_implementation_surface_ids,
        ],
        "report": project_bundle.binding_report.to_dict(),
    }
    behavior_shards = tuple(
        dict(reference_shard)
        for _shard_id, reference_shard in project_bundle.normalized_shards
    )
    shared_objects = tuple(
        {"object_id": object_id, "value": value}
        for object_id, value in project_bundle.normalized_shared_objects
    )
    readiness = (
        {
            "readiness_kind": "static_manifest_qualification",
            **project_bundle.qualification.to_dict(),
        },
        {"readiness_kind": "static_blueprint", **project_bundle.static_readiness.to_dict()},
        {"readiness_kind": "target_system", **project_bundle.target_system_report.to_dict()},
        {"readiness_kind": "ledger", **project_bundle.readiness_ledger.to_dict()},
        {
            "readiness_kind": "understanding",
            **(
                project_bundle.understanding_summary.to_dict()
                if project_bundle.understanding_summary is not None
                else {}
            ),
        },
    )
    candidates = (
        _make_shard("identity", (identity,)),
        _make_shard("project_definition", (project_bundle.definition,)),
        _make_shard("project_evidence", (project_bundle.project_evidence,)),
        _make_shard("provider_evidence", (project_bundle.frozen_target_evidence,)),
        _make_shard("implementation_inventory", (project_bundle.inventory,)),
        _make_shard(
            "implementation_inventory_audit",
            (project_bundle.implementation_inventory_audit,),
        ),
        _make_shard("bindings", (binding_report,)),
        _make_shard("semantics", project_bundle.binding_report.semantic_specs),
        _make_shard("oracles", project_bundle.binding_report.oracles),
        _make_shard(
            "behavior_model",
            (project_bundle.behavior_report.to_normalized_reference_dict(),),
        ),
        _make_shard("behavior_shards", behavior_shards),
        _make_shard("topology", (project_bundle.topology_report,)),
        _make_shard(
            "model_test_alignment",
            (project_bundle.model_test_alignment_report,),
        ),
        _make_shard("test_inventory", (project_bundle.test_inventory,)),
        _make_shard("resources", (project_bundle.resource_inventory,)),
        _make_shard("intent_lineage", (project_bundle.intent_inventory,)),
        _make_shard("normalized_index", (project_bundle.normalized_projection,)),
        _make_shard(
            "affected_index",
            (project_bundle.normalized_affected_index,),
        ),
        _make_shard("shared_objects", shared_objects),
        _make_shard("readiness", readiness),
    )
    kinds = tuple(sorted(shard.kind for shard in candidates))
    expected_kinds = tuple(sorted(PROJECT_BLUEPRINT_PROJECTION_KINDS))
    if kinds != expected_kinds:
        raise BlueprintValidationError(
            "canonical project projection kinds are not exact-current"
        )

    old_by_kind = (
        {shard.kind: shard for shard in previous_projection.shards}
        if previous_projection is not None
        else {}
    )
    affected = (
        set(affected_neighborhood.all_member_ids)
        if affected_neighborhood is not None
        else set()
    )
    shards: list[BlueprintShard] = []
    reused: list[str] = []
    regenerated: list[str] = []
    for candidate in candidates:
        previous = old_by_kind.get(candidate.kind)
        category_affected = bool(affected.intersection(candidate.member_ids))
        if (
            previous is not None
            and previous.content_fingerprint == candidate.content_fingerprint
            and not category_affected
        ):
            shards.append(previous)
            reused.append(previous.shard_id)
        else:
            shards.append(candidate)
            regenerated.append(candidate.shard_id)
    return CanonicalBlueprintProjection(
        blueprint_fingerprint=project_bundle.fingerprint,
        shards=tuple(shards),
        reused_shard_ids=_tuple(reused),
        regenerated_shard_ids=_tuple(regenerated),
        affected_member_ids=_tuple(affected),
    )


PROJECT_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY = (
    "the exact ProjectBlueprintBundle identity and its canonical child fingerprints "
    "are rebound to all exact-current project shards; readiness remains the bundle result"
)


@dataclass(frozen=True)
class ProjectBlueprintMaterializationVerification:
    ok: bool
    status: str
    materialization: CanonicalBlueprintMaterialization
    findings: tuple[BlueprintFinding, ...] = ()
    claim_boundary: str = PROJECT_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "materialization_ok": self.ok,
            "materialization_status": self.status,
            "projection_fingerprint": self.materialization.projection.fingerprint,
            "tree_fingerprint": self.materialization.tree_fingerprint,
            "generic_claim_boundary": self.materialization.claim_boundary,
            "claim_boundary": self.claim_boundary,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def verify_materialized_project_blueprint_projection(
    output_root: str | Path,
    project_bundle: Any,
) -> ProjectBlueprintMaterializationVerification:
    """Rebind a generic disk projection to one exact project bundle."""

    expected = project_canonical_software_blueprint(project_bundle)
    materialization = load_canonical_blueprint_projection(output_root)
    actual = materialization.projection
    findings: list[BlueprintFinding] = []
    actual_by_kind = {shard.kind: shard for shard in actual.shards}
    expected_by_kind = {shard.kind: shard for shard in expected.shards}
    if tuple(sorted(actual_by_kind)) != tuple(
        sorted(PROJECT_BLUEPRINT_PROJECTION_KINDS)
    ):
        findings.append(
            BlueprintFinding(
                "project_projection_kind_set_mismatch",
                "Materialized project projection does not have the exact current shard set.",
                tuple(sorted(actual_by_kind)),
                "blocked",
            )
        )
    if actual.blueprint_fingerprint != project_bundle.fingerprint:
        findings.append(
            BlueprintFinding(
                "project_projection_blueprint_rebind_mismatch",
                "Projection envelope does not match the exact project bundle identity.",
                severity="blocked",
            )
        )
    if actual.fingerprint != expected.fingerprint:
        findings.append(
            BlueprintFinding(
                "project_projection_manifest_rebind_mismatch",
                "Materialized project manifest does not match the exact bundle projection.",
                severity="blocked",
            )
        )

    identity = actual_by_kind.get("identity")
    identity_payload = (
        identity.payload[0]
        if identity is not None and len(identity.payload) == 1
        else None
    )
    expected_children = dict(project_bundle.canonical_child_fingerprints)
    if not isinstance(identity_payload, Mapping) or any(
        (
            identity_payload.get("projection_kind") != "project_blueprint",
            identity_payload.get("blueprint_fingerprint")
            != project_bundle.fingerprint,
            identity_payload.get("project_blueprint_fingerprint")
            != project_bundle.fingerprint,
            identity_payload.get("child_fingerprints") != expected_children,
        )
    ):
        findings.append(
            BlueprintFinding(
                "project_projection_identity_rebind_mismatch",
                "Project identity shard is not derived from the exact bundle children.",
                severity="blocked",
            )
        )

    for kind in ("bindings", "semantics", "oracles", "readiness"):
        actual_shard = actual_by_kind.get(kind)
        expected_shard = expected_by_kind.get(kind)
        if (
            actual_shard is None
            or expected_shard is None
            or actual_shard.to_dict() != expected_shard.to_dict()
        ):
            findings.append(
                BlueprintFinding(
                    f"project_projection_{kind}_rebind_mismatch",
                    f"Project {kind} shard is not derived from the exact bundle child reports.",
                    (kind,),
                    "blocked",
                )
            )
    return ProjectBlueprintMaterializationVerification(
        ok=not findings,
        status="complete" if not findings else "blocked",
        materialization=materialization,
        findings=tuple(findings),
    )


@dataclass(frozen=True)
class BlueprintProjectionVerification:
    ok: bool
    status: str
    findings: tuple[BlueprintFinding, ...]
    projection_fingerprint: str | None = None


def verify_blueprint_projection(
    projection: CanonicalBlueprintProjection,
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


def _load_json_blueprint(path: str | Path, *, context: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BlueprintValidationError(
                    f"{context} contains duplicate JSON key: {key}"
                )
            result[key] = value
        return result

    def reject_non_finite(value: str) -> Any:
        raise BlueprintValidationError(
            f"{context} contains non-finite JSON number: {value}"
        )

    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite,
        )
    except (OSError, json.JSONDecodeError, BlueprintValidationError) as exc:
        raise BlueprintValidationError(f"cannot load {context}: {exc}") from exc
    if not isinstance(value, dict):
        raise BlueprintValidationError(f"{context} must be a JSON object")
    return value


def serialize_canonical_blueprint_projection(
    projection: CanonicalBlueprintProjection,
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


CANONICAL_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY = (
    "exact-current directory ownership, manifest shape, and content-addressed "
    "shard integrity only; target identity and readiness require a target-owned rebind"
)


@dataclass(frozen=True)
class _ProjectionTreeSnapshot:
    exists: bool
    directories: tuple[str, ...]
    files: tuple[tuple[str, str], ...]

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(
            {
                "exists": self.exists,
                "directories": list(self.directories),
                "files": [list(row) for row in self.files],
            }
        )


@dataclass(frozen=True)
class CanonicalBlueprintMaterialization:
    """Strict current-schema disk projection with a bounded generic claim."""

    projection: CanonicalBlueprintProjection
    materialized_shards: tuple[tuple[str, Mapping[str, Any]], ...]
    tree_fingerprint: str
    verification: BlueprintProjectionVerification
    claim_boundary: str = CANONICAL_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY

    def materialized_shard_map(self) -> dict[str, Mapping[str, Any]]:
        return dict(self.materialized_shards)

    def to_dict(self) -> dict[str, Any]:
        return {
            "materialization_ok": self.verification.ok,
            "materialization_status": self.verification.status,
            "claim_boundary": self.claim_boundary,
            "blueprint_fingerprint": self.projection.blueprint_fingerprint,
            "projection_fingerprint": self.projection.fingerprint,
            "tree_fingerprint": self.tree_fingerprint,
        }


def _path_exists_no_follow(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _is_reparse_stat(value: os.stat_result) -> bool:
    file_attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(file_attributes & reparse_flag)


def _projection_tree_snapshot(root: Path) -> _ProjectionTreeSnapshot:
    if not _path_exists_no_follow(root):
        return _ProjectionTreeSnapshot(False, (), ())
    try:
        root_stat = os.lstat(root)
    except OSError as exc:
        raise BlueprintValidationError(
            f"cannot inspect canonical projection root: {exc}"
        ) from exc
    if _is_reparse_stat(root_stat):
        raise BlueprintValidationError(
            "canonical projection tree cannot contain a reparse point"
        )
    if not stat.S_ISDIR(root_stat.st_mode):
        raise BlueprintValidationError(
            "canonical projection root must be a directory"
        )

    directories: list[str] = []
    files: list[tuple[str, str]] = []
    pending: list[tuple[Path, str]] = [(root, "")]
    try:
        while pending:
            directory, prefix = pending.pop()
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
            for entry in entries:
                relative = f"{prefix}/{entry.name}" if prefix else entry.name
                relative = PurePosixPath(relative).as_posix()
                entry_stat = entry.stat(follow_symlinks=False)
                if _is_reparse_stat(entry_stat):
                    raise BlueprintValidationError(
                        "canonical projection tree cannot contain a reparse point: "
                        + relative
                    )
                if stat.S_ISDIR(entry_stat.st_mode):
                    directories.append(relative)
                    pending.append((Path(entry.path), relative))
                    continue
                if not stat.S_ISREG(entry_stat.st_mode):
                    raise BlueprintValidationError(
                        "canonical projection tree contains an unsupported entry: "
                        + relative
                    )
                content = Path(entry.path).read_bytes()
                after_read = os.lstat(entry.path)
                if _is_reparse_stat(after_read) or not stat.S_ISREG(
                    after_read.st_mode
                ):
                    raise BlueprintValidationError(
                        "canonical projection file changed type while inspected: "
                        + relative
                    )
                files.append((relative, "sha256:" + hashlib.sha256(content).hexdigest()))
    except BlueprintValidationError:
        raise
    except OSError as exc:
        raise BlueprintValidationError(
            f"cannot inspect canonical projection tree: {exc}"
        ) from exc
    return _ProjectionTreeSnapshot(
        True,
        tuple(sorted(directories)),
        tuple(sorted(files)),
    )


def _owned_directory_paths(relative_files: Iterable[str]) -> tuple[str, ...]:
    directories: set[str] = set()
    for relative in relative_files:
        for parent in PurePosixPath(relative).parents:
            if parent != PurePosixPath("."):
                directories.add(parent.as_posix())
    return tuple(sorted(directories))


def _expected_projection_snapshot(files: Mapping[str, bytes]) -> _ProjectionTreeSnapshot:
    return _ProjectionTreeSnapshot(
        True,
        _owned_directory_paths(files),
        tuple(
            sorted(
                (
                    relative,
                    "sha256:" + hashlib.sha256(content).hexdigest(),
                )
                for relative, content in files.items()
            )
        ),
    )


def _require_exact_projection_tree(
    snapshot: _ProjectionTreeSnapshot,
    expected_relative_files: Iterable[str],
    *,
    context: str,
) -> None:
    expected_files = tuple(sorted(expected_relative_files))
    actual_files = tuple(relative for relative, _digest in snapshot.files)
    expected_directories = _owned_directory_paths(expected_files)
    if actual_files != expected_files or snapshot.directories != expected_directories:
        raise BlueprintValidationError(
            f"{context} contains unowned, missing, or non-canonical entries"
        )


def load_canonical_blueprint_projection(
    output_root: str | Path,
) -> CanonicalBlueprintMaterialization:
    """Load and verify one exact-current canonical projection from disk.

    This generic check deliberately does not license target identity, target
    readiness, or understanding-depth claims.  A target-specific compiler must
    rebind those claims to its typed inputs after this check succeeds.
    """

    requested_root = Path(output_root)
    snapshot = _projection_tree_snapshot(requested_root)
    if not snapshot.exists:
        raise BlueprintValidationError("canonical projection root does not exist")
    manifest_path = requested_root / "manifest.json"
    manifest = _load_json_blueprint(
        manifest_path,
        context="canonical projection manifest",
    )
    if set(manifest) != {
        "schema_version",
        "blueprint_fingerprint",
        "shards",
        "projection_fingerprint",
    } or manifest.get("schema_version") != BLUEPRINT_SCHEMA_VERSION:
        raise BlueprintValidationError(
            "canonical projection manifest is not exact-current"
        )
    rows = manifest.get("shards")
    if not isinstance(rows, list):
        raise BlueprintValidationError("canonical projection shard manifest is invalid")

    expected_relative_files = {"manifest.json"}
    shards: list[BlueprintShard] = []
    materialized: dict[str, Mapping[str, Any]] = {}
    manifest_row_keys = {
        "shard_id",
        "kind",
        "relative_path",
        "member_ids",
        "content_fingerprint",
    }
    shard_file_keys = {
        "schema_version",
        "shard_id",
        "kind",
        "relative_path",
        "member_ids",
        "payload",
        "content_fingerprint",
    }
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != manifest_row_keys:
            raise BlueprintValidationError(
                "canonical projection shard manifest row is not exact-current"
            )
        relative = row.get("relative_path")
        if not isinstance(relative, str) or not relative:
            raise BlueprintValidationError(
                "canonical projection shard path is invalid"
            )
        relative_path = PurePosixPath(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or not relative_path.parts
            or ":" in relative_path.parts[0]
            or relative.startswith(("\\", "//"))
        ):
            raise BlueprintValidationError(
                "canonical projection shard path escapes its projection root"
            )
        if relative in expected_relative_files:
            raise BlueprintValidationError(
                "canonical projection shard path is duplicated"
            )
        expected_relative_files.add(relative)
        shard_value = _load_json_blueprint(
            requested_root / relative_path,
            context="canonical projection shard",
        )
        if set(shard_value) != shard_file_keys or (
            shard_value.get("schema_version") != BLUEPRINT_SCHEMA_VERSION
        ):
            raise BlueprintValidationError(
                "canonical projection shard is not exact-current"
            )
        for key in manifest_row_keys:
            if shard_value.get(key) != row.get(key):
                raise BlueprintValidationError(
                    "canonical projection shard metadata disagrees with its manifest"
                )
        payload = shard_value.get("payload")
        member_ids = shard_value.get("member_ids")
        if not isinstance(payload, list) or not isinstance(member_ids, list):
            raise BlueprintValidationError(
                "canonical projection shard payload is invalid"
            )
        shard = BlueprintShard(
            shard_id=str(shard_value["shard_id"]),
            kind=str(shard_value["kind"]),
            relative_path=relative,
            member_ids=tuple(str(member_id) for member_id in member_ids),
            payload=tuple(payload),
            content_fingerprint=str(shard_value["content_fingerprint"]),
        )
        shards.append(shard)
        materialized[relative] = shard_value

    _require_exact_projection_tree(
        snapshot,
        expected_relative_files,
        context="canonical projection tree",
    )
    projection = CanonicalBlueprintProjection(
        blueprint_fingerprint=str(manifest.get("blueprint_fingerprint", "")),
        shards=tuple(shards),
    )
    expected_manifest = {
        **projection.manifest_dict(),
        "projection_fingerprint": projection.fingerprint,
    }
    if manifest != expected_manifest:
        raise BlueprintValidationError(
            "canonical projection manifest identity is inconsistent"
        )
    verification = verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=projection.blueprint_fingerprint,
        expected_projection_fingerprint=str(manifest["projection_fingerprint"]),
        materialized_shards=materialized,
    )
    if not verification.ok:
        raise BlueprintValidationError(
            "; ".join(finding.message for finding in verification.findings)
        )
    final_snapshot = _projection_tree_snapshot(requested_root)
    if final_snapshot != snapshot:
        raise BlueprintValidationError(
            "canonical projection changed while it was being verified"
        )
    return CanonicalBlueprintMaterialization(
        projection=projection,
        materialized_shards=tuple(sorted(materialized.items())),
        tree_fingerprint=final_snapshot.fingerprint,
        verification=verification,
    )


def _validated_existing_projection_snapshot(root: Path) -> _ProjectionTreeSnapshot:
    snapshot = _projection_tree_snapshot(root)
    if not snapshot.exists or (not snapshot.directories and not snapshot.files):
        return snapshot
    materialization = load_canonical_blueprint_projection(root)
    final_snapshot = _projection_tree_snapshot(root)
    if final_snapshot.fingerprint != materialization.tree_fingerprint:
        raise BlueprintValidationError(
            "existing canonical projection changed after verification"
        )
    return final_snapshot


def _cleanup_owned_tree(path: Path, *, context: str) -> bool:
    if not _path_exists_no_follow(path):
        return True
    try:
        shutil.rmtree(path)
    except OSError as exc:
        warnings.warn(
            f"{context} cleanup did not complete; preserved at {path}: {exc}",
            RuntimeWarning,
            stacklevel=3,
        )
        return False
    return True


def _restore_previous_projection(
    *,
    root: Path,
    backup: Path,
    expected_snapshot: _ProjectionTreeSnapshot,
    owned_collision_snapshot: _ProjectionTreeSnapshot | None = None,
) -> None:
    collision: Path | None = None
    collision_is_owned = False
    if _path_exists_no_follow(root):
        try:
            current = _projection_tree_snapshot(root)
        except BlueprintValidationError:
            current = None
        if current is not None and not current.directories and not current.files:
            root.rmdir()
        else:
            collision = root.parent / f".{root.name}.rollback-collision-{uuid.uuid4().hex}"
            os.replace(root, collision)
            collision_is_owned = (
                current is not None
                and owned_collision_snapshot is not None
                and current == owned_collision_snapshot
            )
    os.replace(backup, root)
    restored = _validated_existing_projection_snapshot(root)
    if restored != expected_snapshot:
        raise BlueprintValidationError(
            "previous canonical projection could not be restored exactly"
        )
    if collision is not None:
        if collision_is_owned:
            _cleanup_owned_tree(collision, context="failed activation")
        else:
            warnings.warn(
                "a concurrent output-root collision was preserved at " + str(collision),
                RuntimeWarning,
                stacklevel=3,
            )


def write_canonical_blueprint_projection(
    projection: CanonicalBlueprintProjection,
    output_root: str | Path,
) -> tuple[Path, ...]:
    """Stage, revalidate, and failure-atomically activate one projection."""

    requested_root = Path(output_root)
    if _path_exists_no_follow(requested_root):
        requested_stat = os.lstat(requested_root)
        if _is_reparse_stat(requested_stat):
            raise BlueprintValidationError(
                "blueprint output root cannot be a reparse point"
            )
    root = requested_root.resolve()
    if root.parent == root:
        raise BlueprintValidationError("blueprint output root is too broad")
    root.parent.mkdir(parents=True, exist_ok=True)
    initial_root_snapshot = _validated_existing_projection_snapshot(root)

    files = serialize_canonical_blueprint_projection(projection)
    expected_staging_snapshot = _expected_projection_snapshot(files)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{root.name}.staging-", dir=root.parent)
    ).resolve()
    backup = root.parent / f".{root.name}.backup-{uuid.uuid4().hex}"
    root_moved = False
    try:
        for relative, content in sorted(files.items()):
            target = (staging / PurePosixPath(relative)).resolve()
            if target != staging and staging not in target.parents:
                raise BlueprintValidationError(
                    "blueprint output path escapes its projection root"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        staged = load_canonical_blueprint_projection(staging)
        staged_snapshot = _projection_tree_snapshot(staging)
        if (
            staged.projection.fingerprint != projection.fingerprint
            or staged_snapshot != expected_staging_snapshot
        ):
            raise BlueprintValidationError(
                "staged canonical projection does not match its exact serialized input"
            )

        current_root_snapshot = _validated_existing_projection_snapshot(root)
        if current_root_snapshot != initial_root_snapshot:
            raise BlueprintValidationError(
                "existing canonical projection changed before activation"
            )
        current_staging_snapshot = _projection_tree_snapshot(staging)
        if current_staging_snapshot != staged_snapshot:
            raise BlueprintValidationError(
                "staged canonical projection changed before activation"
            )

        if initial_root_snapshot.exists:
            os.replace(root, backup)
            root_moved = True
            moved_snapshot = _validated_existing_projection_snapshot(backup)
            if moved_snapshot != initial_root_snapshot:
                raise BlueprintValidationError(
                    "existing canonical projection changed during activation"
                )
        final_staging_snapshot = _projection_tree_snapshot(staging)
        if final_staging_snapshot != staged_snapshot:
            raise BlueprintValidationError(
                "staged canonical projection changed at the activation boundary"
            )
        os.replace(staging, root)
    except Exception as error:
        rollback_error: Exception | None = None
        if root_moved and _path_exists_no_follow(backup):
            try:
                _restore_previous_projection(
                    root=root,
                    backup=backup,
                    expected_snapshot=initial_root_snapshot,
                    owned_collision_snapshot=(
                        staged_snapshot if "staged_snapshot" in locals() else None
                    ),
                )
                root_moved = False
            except Exception as exc:  # preserve backup on any incomplete rollback
                rollback_error = exc
        _cleanup_owned_tree(staging, context="staged projection")
        if rollback_error is not None:
            raise BlueprintValidationError(
                f"canonical projection activation failed ({error}); "
                f"rollback is incomplete and the prior tree is preserved at {backup}: "
                f"{rollback_error}"
            ) from rollback_error
        raise

    if root_moved:
        _cleanup_owned_tree(backup, context="activated projection backup")

    return tuple(root / relative for relative in sorted(files))


__all__ = [
    "AffectedBlueprintNeighborhood",
    "BLUEPRINT_SCHEMA_VERSION",
    "CANONICAL_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY",
    "PROJECT_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY",
    "BlueprintFinding",
    "CanonicalBlueprintMaterialization",
    "CanonicalBlueprintProjection",
    "BlueprintProjectionVerification",
    "BlueprintResourceReference",
    "BlueprintShard",
    "BlueprintValidationError",
    "ModelImplementationBinding",
    "ModelImplementationBindingReport",
    "OracleReference",
    "SemanticSpecReference",
    "SoftwareBlueprintManifest",
    "derive_affected_blueprint_neighborhood",
    "load_canonical_blueprint_projection",
    "PROJECT_BLUEPRINT_PROJECTION_KINDS",
    "ProjectBlueprintMaterializationVerification",
    "project_canonical_software_blueprint",
    "review_model_implementation_bindings",
    "serialize_canonical_blueprint_projection",
    "verify_blueprint_projection",
    "verify_materialized_project_blueprint_projection",
    "write_canonical_blueprint_projection",
]
