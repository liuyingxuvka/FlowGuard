"""Provider-neutral target-system blueprint composition.

This module is intentionally thin. Providers contribute content-addressed
observations or independently governed authority; only the compiler joins
those results into layered blueprint readiness. It does not discover files or
execute a provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cached_property
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from .evidence_receipts import fingerprint_value
from .model_path_quality import PathQualityResult, PathQualitySubject
from .portable_model import canonical_json_bytes


TARGET_SYSTEM_BLUEPRINT_SCHEMA = "flowguard.target_system_blueprint.v3"
TARGET_SYSTEM_PROVIDER_SCHEMA = "flowguard.target_system_provider_result.v1"
TARGET_SYSTEM_PROVIDER_REGISTRY_SCHEMA = "flowguard.target_system_provider_registry.v1"
TARGET_SYSTEM_SNAPSHOT_SCHEMA = "flowguard.target_system_snapshot.v1"
TARGET_SYSTEM_LAYER_PLAN_SCHEMA = "flowguard.target_system_layer_plan.v1"
FROZEN_TARGET_SYSTEM_EVIDENCE_SCHEMA = "flowguard.frozen_target_system_evidence.v1"
BLUEPRINT_UNDERSTANDING_SCHEMA = "flowguard.blueprint_understanding_summary.v3"
TARGET_SYSTEM_PROVIDER_PROFILE_SCHEMA = "flowguard.target_system_provider_profile.v1"
TARGET_SYSTEM_PROVIDER_PROFILE_REGISTRY_SCHEMA = (
    "flowguard.target_system_provider_profile_registry.v1"
)
TARGET_SYSTEM_DNA_QUALIFICATION_SCHEMA = (
    "flowguard.target_system_dna_qualification.v1"
)
MODEL_PATH_QUALITY_BLUEPRINT_BINDING_SCHEMA = (
    "flowguard.model_path_quality_blueprint_binding.v1"
)

PROVIDER_ROLES = ("observation", "authority")
PROVIDER_STATUSES = ("current", "incomplete", "stale", "blocked", "not_applicable")
LAYER_STATUSES = ("pass", "incomplete", "stale", "blocked", "not_run")
PRE_CODE_STATUSES = ("ready", "incomplete", "stale", "blocked", "not_applicable")
DNA_QUALIFICATION_STATUSES = (
    "current",
    "stale",
    "candidate",
    "incomplete",
    "blocked",
    "unknown",
    "missing",
    "not_applicable",
)
EXECUTED_EVIDENCE_STATUSES = (
    "passed",
    "failed",
    "timeout",
    "skipped",
    "not_run",
    "running",
    "error",
    "incomplete",
    "stale",
    "blocked",
    "not_applicable",
)
MODEL_PATH_QUALITY_CHANGE_KINDS = frozenset(
    {"new", "materially_changed", "unchanged"}
)
MODEL_PATH_QUALITY_SUBJECT_LANES = frozenset(
    {"observed", "normative_target"}
)
_CANONICAL_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SOFTWARE_TARGET_PROFILE = "software"
NON_CODE_WORKFLOW_TARGET_PROFILE = "non_code_workflow"
SOFTWARE_BLUEPRINT_LAYER_ORDER = (
    "evidence_qualification",
    "implementation_inventory",
    "traceability",
    "independent_semantics",
    "model_code_test",
    "resource_oracle",
    "static_blueprint",
)
NON_CODE_WORKFLOW_LAYER_ORDER = (
    "evidence_qualification",
    "workflow_boundary",
    "workflow_actors",
    "workflow_inputs",
    "workflow_states",
    "workflow_transitions",
    "workflow_outputs",
    "workflow_resources",
    "workflow_intent",
    "workflow_verification",
)


class TargetSystemBlueprintError(ValueError):
    """Raised when a target-system blueprint input is not exact-current."""


@dataclass(frozen=True)
class ModelPathQualityBlueprintBinding:
    """One compact provider-neutral path-quality row consumed by a blueprint.

    The row embeds only the current subject and compact result records. Deep
    candidate, rewrite, and witness bodies remain with ModelMaturation and are
    addressed through ``detail_evidence_fingerprint``.
    """

    model_element_id: str
    subject_lane: str
    change_kind: str
    subject: PathQualitySubject
    result: PathQualityResult
    affected_topology_evidence_fingerprint: str = ""
    affected_topology_currentness_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "model_element_id",
            _text(self.model_element_id, "path-quality model element id"),
        )
        if self.subject_lane not in MODEL_PATH_QUALITY_SUBJECT_LANES:
            raise TargetSystemBlueprintError(
                "path-quality subject lane must be observed or normative_target"
            )
        if self.change_kind not in MODEL_PATH_QUALITY_CHANGE_KINDS:
            raise TargetSystemBlueprintError(
                "path-quality change kind must be new, materially_changed, or unchanged"
            )
        if not isinstance(self.subject, PathQualitySubject):
            raise TargetSystemBlueprintError(
                "path-quality blueprint binding requires a typed current subject"
            )
        if not isinstance(self.result, PathQualityResult):
            raise TargetSystemBlueprintError(
                "path-quality blueprint binding requires a typed compact result"
            )
        if self.subject.model_id != self.model_element_id:
            raise TargetSystemBlueprintError(
                "path-quality subject targets another blueprint model element"
            )
        if self.result.subject_fingerprint != self.subject.fingerprint:
            raise TargetSystemBlueprintError(
                "path-quality compact result targets another subject"
            )
        if self.result.currentness_id != self.subject.currentness_id:
            raise TargetSystemBlueprintError(
                "path-quality subject and result currentness differ"
            )
        topology_fingerprint = self.affected_topology_evidence_fingerprint
        topology_currentness = self.affected_topology_currentness_id
        if self.change_kind == "unchanged":
            if not _CANONICAL_FINGERPRINT_RE.fullmatch(topology_fingerprint):
                raise TargetSystemBlueprintError(
                    "unchanged path-quality reuse requires canonical affected-topology evidence"
                )
            if topology_currentness != self.subject.currentness_id:
                raise TargetSystemBlueprintError(
                    "unchanged path-quality reuse evidence is not exact-current"
                )
        elif topology_fingerprint or topology_currentness:
            raise TargetSystemBlueprintError(
                "new or materially changed path-quality rows cannot claim unchanged reuse evidence"
            )

    @property
    def schema_version(self) -> str:
        return MODEL_PATH_QUALITY_BLUEPRINT_BINDING_SCHEMA

    @property
    def detail_evidence_fingerprint(self) -> str:
        return self.result.detail_evidence_fingerprint

    @property
    def ready(self) -> bool:
        return (
            self.subject_lane == "observed"
            and self.result.current
            and self.result.conclusion != "unresolved"
            and self.result.selected_candidate_lane != "normative_target"
        )

    def _compact_identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_element_id": self.model_element_id,
            "subject_lane": self.subject_lane,
            "change_kind": self.change_kind,
            "subject": self.subject.to_dict(),
            "result": self.result.to_compact_dict(),
            "affected_topology_evidence_fingerprint": (
                self.affected_topology_evidence_fingerprint
            ),
            "affected_topology_currentness_id": (
                self.affected_topology_currentness_id
            ),
        }

    @cached_property
    def compact_current_fingerprint(self) -> str:
        return fingerprint_value(self._compact_identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._compact_identity_payload(),
            "compact_current_fingerprint": self.compact_current_fingerprint,
            "detail_evidence_fingerprint": self.detail_evidence_fingerprint,
            "ready": self.ready,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelPathQualityBlueprintBinding":
        row = _strict_object(
            value,
            fields=(
                "schema_version",
                "model_element_id",
                "subject_lane",
                "change_kind",
                "subject",
                "result",
                "affected_topology_evidence_fingerprint",
                "affected_topology_currentness_id",
                "compact_current_fingerprint",
                "detail_evidence_fingerprint",
                "ready",
            ),
            context="model path-quality blueprint binding",
        )
        if row["schema_version"] != MODEL_PATH_QUALITY_BLUEPRINT_BINDING_SCHEMA:
            raise TargetSystemBlueprintError(
                "model path-quality blueprint binding schema is not current"
            )
        try:
            binding = cls(
                model_element_id=str(row["model_element_id"]),
                subject_lane=str(row["subject_lane"]),
                change_kind=str(row["change_kind"]),
                subject=PathQualitySubject.from_dict(row["subject"]),
                result=PathQualityResult.from_dict(row["result"]),
                affected_topology_evidence_fingerprint=str(
                    row["affected_topology_evidence_fingerprint"]
                ),
                affected_topology_currentness_id=str(
                    row["affected_topology_currentness_id"]
                ),
            )
        except ValueError as exc:
            raise TargetSystemBlueprintError(
                f"model path-quality blueprint binding is invalid: {exc}"
            ) from exc
        if (
            row["compact_current_fingerprint"]
            != binding.compact_current_fingerprint
            or row["detail_evidence_fingerprint"]
            != binding.detail_evidence_fingerprint
            or row["ready"] is not binding.ready
        ):
            raise TargetSystemBlueprintError(
                "model path-quality blueprint binding projection is stale"
            )
        return binding


def model_path_quality_binding_set_fingerprint(
    bindings: Sequence[ModelPathQualityBlueprintBinding],
) -> str:
    """Fingerprint one sorted compact binding denominator, never deep bodies."""

    return fingerprint_value(
        [
            row.compact_current_fingerprint
            for row in sorted(bindings, key=lambda item: item.model_element_id)
        ]
    )


_BLUEPRINT_DERIVATION_TOKEN = object()


def _text(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise TargetSystemBlueprintError(f"{field_name} is required")
    return text


def _strings(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    rows = tuple(sorted({_text(value, field_name) for value in values}))
    return rows


def _pairs(
    values: Mapping[str, str] | Iterable[tuple[str, str]],
    field_name: str,
) -> tuple[tuple[str, str], ...]:
    rows = values.items() if isinstance(values, Mapping) else values
    normalized = tuple(
        sorted((_text(key, field_name), _text(value, field_name)) for key, value in rows)
    )
    if len(normalized) != len({key for key, _value in normalized}):
        raise TargetSystemBlueprintError(f"{field_name} contains duplicate identities")
    return normalized


def _strict_object(
    value: Any,
    *,
    fields: Sequence[str],
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TargetSystemBlueprintError(f"{context} must be an object")
    expected = set(fields)
    observed = set(value)
    if observed != expected:
        difference = sorted(observed ^ expected)
        raise TargetSystemBlueprintError(
            f"{context} fields differ from the current schema: {difference}"
        )
    return value


def _array(value: Any, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, list):
        raise TargetSystemBlueprintError(f"{field_name} must be an array")
    return tuple(value)


def _mapping_pairs(value: Any, field_name: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise TargetSystemBlueprintError(f"{field_name} must be an object")
    return tuple((str(key), str(item)) for key, item in value.items())


def _load_json_object(path: str | Path, context: str) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TargetSystemBlueprintError(f"cannot load {context}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise TargetSystemBlueprintError(f"{context} must be an object")
    return value


@dataclass(frozen=True)
class TargetSystemLayerPlan:
    """One frozen, profile-specific ordered target qualification plan."""

    plan_id: str
    target_profile: str
    layer_ids: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _text(self.plan_id, "layer plan id"))
        object.__setattr__(
            self,
            "target_profile",
            _text(self.target_profile, "layer plan target profile"),
        )
        object.__setattr__(
            self,
            "claim_boundary",
            _text(self.claim_boundary, "layer plan claim boundary"),
        )
        layers = tuple(_text(value, "layer plan layer") for value in self.layer_ids)
        if not layers or layers[0] != "evidence_qualification":
            raise TargetSystemBlueprintError(
                "layer plan must begin with evidence_qualification"
            )
        if len(layers) != len(set(layers)):
            raise TargetSystemBlueprintError("layer plan contains duplicate layers")
        object.__setattr__(self, "layer_ids", layers)

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_LAYER_PLAN_SCHEMA,
            "plan_id": self.plan_id,
            "target_profile": self.target_profile,
            "layer_ids": list(self.layer_ids),
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemLayerPlan":
        fields = (
            "schema_version",
            "plan_id",
            "target_profile",
            "layer_ids",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(value, fields=fields, context="target-system layer plan")
        if data["schema_version"] != TARGET_SYSTEM_LAYER_PLAN_SCHEMA:
            raise TargetSystemBlueprintError("target-system layer plan schema is not current")
        plan = cls(
            plan_id=data["plan_id"],
            target_profile=data["target_profile"],
            layer_ids=tuple(_array(data["layer_ids"], "layer plan layers")),
            claim_boundary=data["claim_boundary"],
        )
        if plan.fingerprint != _text(data["fingerprint"], "layer plan fingerprint"):
            raise TargetSystemBlueprintError("target-system layer plan fingerprint mismatch")
        return plan


CANONICAL_SOFTWARE_LAYER_PLAN = TargetSystemLayerPlan(
    plan_id="target-system-layer-plan:software:v1",
    target_profile=SOFTWARE_TARGET_PROFILE,
    layer_ids=SOFTWARE_BLUEPRINT_LAYER_ORDER,
    claim_boundary="Canonical software target qualification layers only.",
)
CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN = TargetSystemLayerPlan(
    plan_id="target-system-layer-plan:non-code-workflow:v1",
    target_profile=NON_CODE_WORKFLOW_TARGET_PROFILE,
    layer_ids=NON_CODE_WORKFLOW_LAYER_ORDER,
    claim_boundary="Canonical non-code workflow qualification layers only.",
)


@dataclass(frozen=True)
class TargetSystemDescriptor:
    """One bounded target, independent of language or artifact layout."""

    target_system_id: str
    target_kind: str
    target_profile: str
    subject_revision: str
    boundary_fingerprint: str
    required_observation_capabilities: tuple[str, ...]
    required_authority_capabilities: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_system_id", _text(self.target_system_id, "target_system_id"))
        object.__setattr__(self, "target_kind", _text(self.target_kind, "target_kind"))
        object.__setattr__(
            self,
            "target_profile",
            _text(self.target_profile, "target_profile"),
        )
        object.__setattr__(self, "subject_revision", _text(self.subject_revision, "subject_revision"))
        object.__setattr__(self, "boundary_fingerprint", _text(self.boundary_fingerprint, "boundary_fingerprint"))
        object.__setattr__(self, "claim_boundary", _text(self.claim_boundary, "claim_boundary"))
        object.__setattr__(
            self,
            "required_observation_capabilities",
            _strings(
                self.required_observation_capabilities,
                "required_observation_capability",
            ),
        )
        object.__setattr__(
            self,
            "required_authority_capabilities",
            _strings(
                self.required_authority_capabilities,
                "required_authority_capability",
            ),
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "target_system_id": self.target_system_id,
            "target_kind": self.target_kind,
            "target_profile": self.target_profile,
            "subject_revision": self.subject_revision,
            "boundary_fingerprint": self.boundary_fingerprint,
            "required_observation_capabilities": list(
                self.required_observation_capabilities
            ),
            "required_authority_capabilities": list(
                self.required_authority_capabilities
            ),
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemDescriptor":
        fields = (
            "target_system_id",
            "target_kind",
            "target_profile",
            "subject_revision",
            "boundary_fingerprint",
            "required_observation_capabilities",
            "required_authority_capabilities",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(
            value,
            fields=fields,
            context="target-system descriptor",
        )
        descriptor = cls(
            target_system_id=data["target_system_id"],
            target_kind=data["target_kind"],
            target_profile=data["target_profile"],
            subject_revision=data["subject_revision"],
            boundary_fingerprint=data["boundary_fingerprint"],
            required_observation_capabilities=tuple(
                _array(
                    data["required_observation_capabilities"],
                    "required observation capabilities",
                )
            ),
            required_authority_capabilities=tuple(
                _array(
                    data["required_authority_capabilities"],
                    "required authority capabilities",
                )
            ),
            claim_boundary=data["claim_boundary"],
        )
        if descriptor.fingerprint != _text(
            data["fingerprint"], "target-system descriptor fingerprint"
        ):
            raise TargetSystemBlueprintError(
                "target-system descriptor fingerprint mismatch"
            )
        return descriptor


@dataclass(frozen=True)
class ProviderCapabilityBinding:
    """Exact provider inputs and payloads supporting one declared capability."""

    capability_id: str
    input_ids: tuple[str, ...]
    payload_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capability_id",
            _text(self.capability_id, "provider capability binding"),
        )
        object.__setattr__(
            self,
            "input_ids",
            _strings(self.input_ids, "provider capability input"),
        )
        object.__setattr__(
            self,
            "payload_ids",
            _strings(self.payload_ids, "provider capability payload"),
        )
        if not self.input_ids or not self.payload_ids:
            raise TargetSystemBlueprintError(
                "provider capability binding requires inputs and payloads"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "input_ids": list(self.input_ids),
            "payload_ids": list(self.payload_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ProviderCapabilityBinding":
        fields = ("capability_id", "input_ids", "payload_ids")
        data = _strict_object(value, fields=fields, context="provider capability binding")
        return cls(
            capability_id=data["capability_id"],
            input_ids=tuple(_array(data["input_ids"], "provider capability input ids")),
            payload_ids=tuple(_array(data["payload_ids"], "provider capability payload ids")),
        )


@dataclass(frozen=True)
class TargetSystemProviderResult:
    """Content-addressed evidence from one observation or authority provider."""

    provider_id: str
    provider_role: str
    provider_kind: str
    provider_version: str
    target_system_id: str
    subject_revision: str
    capability_ids: tuple[str, ...]
    input_fingerprints: tuple[tuple[str, str], ...]
    payload_fingerprints: tuple[tuple[str, str], ...]
    capability_bindings: tuple[ProviderCapabilityBinding, ...]
    status: str = "current"
    findings: tuple[str, ...] = ()
    claim_boundary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))
        object.__setattr__(self, "provider_kind", _text(self.provider_kind, "provider_kind"))
        object.__setattr__(self, "provider_version", _text(self.provider_version, "provider_version"))
        object.__setattr__(self, "target_system_id", _text(self.target_system_id, "target_system_id"))
        object.__setattr__(self, "subject_revision", _text(self.subject_revision, "subject_revision"))
        object.__setattr__(self, "claim_boundary", _text(self.claim_boundary, "claim_boundary"))
        if self.provider_role not in PROVIDER_ROLES:
            raise TargetSystemBlueprintError(
                f"unknown provider role: {self.provider_role}"
            )
        if self.status not in PROVIDER_STATUSES:
            raise TargetSystemBlueprintError(f"unknown provider status: {self.status}")
        object.__setattr__(
            self,
            "capability_ids",
            _strings(self.capability_ids, "provider capability"),
        )
        if not self.capability_ids:
            raise TargetSystemBlueprintError("provider requires at least one capability")
        object.__setattr__(
            self,
            "input_fingerprints",
            _pairs(self.input_fingerprints, "provider input fingerprint"),
        )
        object.__setattr__(
            self,
            "payload_fingerprints",
            _pairs(self.payload_fingerprints, "provider payload fingerprint"),
        )
        object.__setattr__(
            self,
            "capability_bindings",
            tuple(sorted(self.capability_bindings, key=lambda row: row.capability_id)),
        )
        binding_ids = tuple(row.capability_id for row in self.capability_bindings)
        if len(binding_ids) != len(set(binding_ids)):
            raise TargetSystemBlueprintError(
                "provider capability bindings contain duplicate identities"
            )
        if set(binding_ids) - set(self.capability_ids):
            raise TargetSystemBlueprintError(
                "provider capability binding names an undeclared capability"
            )
        if self.status == "current" and not self.payload_fingerprints:
            raise TargetSystemBlueprintError(
                "current provider result requires a content-addressed payload"
            )
        object.__setattr__(self, "findings", _strings(self.findings, "provider finding"))

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_PROVIDER_SCHEMA,
            "provider_id": self.provider_id,
            "provider_role": self.provider_role,
            "provider_kind": self.provider_kind,
            "provider_version": self.provider_version,
            "target_system_id": self.target_system_id,
            "subject_revision": self.subject_revision,
            "capability_ids": list(self.capability_ids),
            "input_fingerprints": dict(self.input_fingerprints),
            "payload_fingerprints": dict(self.payload_fingerprints),
            "capability_bindings": [
                row.to_dict() for row in self.capability_bindings
            ],
            "status": self.status,
            "findings": list(self.findings),
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemProviderResult":
        fields = (
            "schema_version",
            "provider_id",
            "provider_role",
            "provider_kind",
            "provider_version",
            "target_system_id",
            "subject_revision",
            "capability_ids",
            "input_fingerprints",
            "payload_fingerprints",
            "capability_bindings",
            "status",
            "findings",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(value, fields=fields, context="target-system provider result")
        if data["schema_version"] != TARGET_SYSTEM_PROVIDER_SCHEMA:
            raise TargetSystemBlueprintError("target-system provider result schema is not current")
        result = cls(
            provider_id=data["provider_id"],
            provider_role=data["provider_role"],
            provider_kind=data["provider_kind"],
            provider_version=data["provider_version"],
            target_system_id=data["target_system_id"],
            subject_revision=data["subject_revision"],
            capability_ids=tuple(_array(data["capability_ids"], "provider capabilities")),
            input_fingerprints=_mapping_pairs(
                data["input_fingerprints"], "provider input fingerprints"
            ),
            payload_fingerprints=_mapping_pairs(
                data["payload_fingerprints"], "provider payload fingerprints"
            ),
            capability_bindings=tuple(
                ProviderCapabilityBinding.from_dict(item)
                for item in _array(
                    data["capability_bindings"], "provider capability bindings"
                )
            ),
            status=data["status"],
            findings=tuple(_array(data["findings"], "provider findings")),
            claim_boundary=data["claim_boundary"],
        )
        if result.fingerprint != _text(data["fingerprint"], "provider result fingerprint"):
            raise TargetSystemBlueprintError("target-system provider result fingerprint mismatch")
        return result


@dataclass(frozen=True)
class TargetSystemProviderDeclaration:
    """One exact provider identity admitted for one target blueprint."""

    provider_id: str
    provider_role: str
    provider_kind: str
    provider_version: str
    capability_ids: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _text(self.provider_id, "provider_id"))
        object.__setattr__(self, "provider_kind", _text(self.provider_kind, "provider_kind"))
        object.__setattr__(self, "provider_version", _text(self.provider_version, "provider_version"))
        object.__setattr__(self, "claim_boundary", _text(self.claim_boundary, "claim_boundary"))
        if self.provider_role not in PROVIDER_ROLES:
            raise TargetSystemBlueprintError("provider declaration role is not current")
        object.__setattr__(
            self,
            "capability_ids",
            _strings(self.capability_ids, "provider declaration capability"),
        )
        if not self.capability_ids:
            raise TargetSystemBlueprintError(
                "provider declaration requires at least one capability"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_role": self.provider_role,
            "provider_kind": self.provider_kind,
            "provider_version": self.provider_version,
            "capability_ids": list(self.capability_ids),
            "claim_boundary": self.claim_boundary,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemProviderDeclaration":
        fields = (
            "provider_id",
            "provider_role",
            "provider_kind",
            "provider_version",
            "capability_ids",
            "claim_boundary",
        )
        data = _strict_object(value, fields=fields, context="provider declaration")
        return cls(
            provider_id=data["provider_id"],
            provider_role=data["provider_role"],
            provider_kind=data["provider_kind"],
            provider_version=data["provider_version"],
            capability_ids=tuple(_array(data["capability_ids"], "provider declaration capabilities")),
            claim_boundary=data["claim_boundary"],
        )


@dataclass(frozen=True)
class TargetSystemProviderRegistry:
    """Content-addressed provider denominator for one compiler request."""

    registry_id: str
    declarations: tuple[TargetSystemProviderDeclaration, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "registry_id", _text(self.registry_id, "registry_id"))
        object.__setattr__(
            self,
            "declarations",
            tuple(sorted(self.declarations, key=lambda row: row.provider_id)),
        )
        provider_ids = tuple(row.provider_id for row in self.declarations)
        if not provider_ids or len(provider_ids) != len(set(provider_ids)):
            raise TargetSystemBlueprintError(
                "provider registry must contain unique provider identities"
            )

    @property
    def declaration_by_id(self) -> dict[str, TargetSystemProviderDeclaration]:
        return {row.provider_id: row for row in self.declarations}

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_PROVIDER_REGISTRY_SCHEMA,
            "registry_id": self.registry_id,
            "declarations": [row.to_dict() for row in self.declarations],
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemProviderRegistry":
        fields = ("schema_version", "registry_id", "declarations", "fingerprint")
        data = _strict_object(value, fields=fields, context="target-system provider registry")
        if data["schema_version"] != TARGET_SYSTEM_PROVIDER_REGISTRY_SCHEMA:
            raise TargetSystemBlueprintError("target-system provider registry schema is not current")
        registry = cls(
            registry_id=data["registry_id"],
            declarations=tuple(
                TargetSystemProviderDeclaration.from_dict(item)
                for item in _array(data["declarations"], "provider registry declarations")
            ),
        )
        if registry.fingerprint != _text(data["fingerprint"], "provider registry fingerprint"):
            raise TargetSystemBlueprintError("target-system provider registry fingerprint mismatch")
        return registry


@dataclass(frozen=True)
class TargetSystemProviderProfileDeclaration:
    """Provider-neutral profile ownership for one downstream target adapter.

    The declaration deliberately stores only the identity of the layer plan.
    The plan itself remains owned by ``TargetSystemLayerPlan`` and is supplied
    to the admission check, so a downstream provider cannot create a second
    layer-plan authority by embedding a private copy here.
    """

    provider_id: str
    target_profile: str
    target_kind: str
    layer_plan_id: str
    layer_plan_fingerprint: str
    owner_id: str
    claim_boundary: str

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "target_profile",
            "target_kind",
            "layer_plan_id",
            "layer_plan_fingerprint",
            "owner_id",
            "claim_boundary",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), f"provider profile {field_name}"),
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_PROVIDER_PROFILE_SCHEMA,
            "provider_id": self.provider_id,
            "target_profile": self.target_profile,
            "target_kind": self.target_kind,
            "layer_plan_id": self.layer_plan_id,
            "layer_plan_fingerprint": self.layer_plan_fingerprint,
            "owner_id": self.owner_id,
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemProviderProfileDeclaration":
        fields = (
            "schema_version",
            "provider_id",
            "target_profile",
            "target_kind",
            "layer_plan_id",
            "layer_plan_fingerprint",
            "owner_id",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(
            value,
            fields=fields,
            context="target-system provider profile declaration",
        )
        if data["schema_version"] != TARGET_SYSTEM_PROVIDER_PROFILE_SCHEMA:
            raise TargetSystemBlueprintError(
                "target-system provider profile declaration schema is not current"
            )
        declaration = cls(
            provider_id=data["provider_id"],
            target_profile=data["target_profile"],
            target_kind=data["target_kind"],
            layer_plan_id=data["layer_plan_id"],
            layer_plan_fingerprint=data["layer_plan_fingerprint"],
            owner_id=data["owner_id"],
            claim_boundary=data["claim_boundary"],
        )
        if declaration.fingerprint != _text(
            data["fingerprint"], "provider profile declaration fingerprint"
        ):
            raise TargetSystemBlueprintError(
                "target-system provider profile declaration fingerprint mismatch"
            )
        return declaration


@dataclass(frozen=True)
class TargetSystemProviderProfileRegistry:
    """Explicit downstream provider/profile ownership for one target scope."""

    registry_id: str
    declarations: tuple[TargetSystemProviderProfileDeclaration, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "registry_id", _text(self.registry_id, "profile registry id"))
        rows = tuple(
            sorted(self.declarations, key=lambda row: (row.provider_id, row.target_profile))
        )
        object.__setattr__(self, "declarations", rows)
        provider_ids = tuple(row.provider_id for row in rows)
        if not provider_ids or len(provider_ids) != len(set(provider_ids)):
            raise TargetSystemBlueprintError(
                "provider profile registry must contain unique provider identities"
            )
        profile_owner_pairs = tuple((row.target_profile, row.owner_id) for row in rows)
        if len(profile_owner_pairs) != len(set(profile_owner_pairs)):
            raise TargetSystemBlueprintError(
                "provider profile registry contains duplicate profile owners"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_PROVIDER_PROFILE_REGISTRY_SCHEMA,
            "registry_id": self.registry_id,
            "declarations": [row.to_dict() for row in self.declarations],
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemProviderProfileRegistry":
        fields = ("schema_version", "registry_id", "declarations", "fingerprint")
        data = _strict_object(
            value,
            fields=fields,
            context="target-system provider profile registry",
        )
        if data["schema_version"] != TARGET_SYSTEM_PROVIDER_PROFILE_REGISTRY_SCHEMA:
            raise TargetSystemBlueprintError(
                "target-system provider profile registry schema is not current"
            )
        registry = cls(
            registry_id=data["registry_id"],
            declarations=tuple(
                TargetSystemProviderProfileDeclaration.from_dict(item)
                for item in _array(data["declarations"], "profile registry declarations")
            ),
        )
        if registry.fingerprint != _text(
            data["fingerprint"], "profile registry fingerprint"
        ):
            raise TargetSystemBlueprintError(
                "target-system provider profile registry fingerprint mismatch"
            )
        return registry


def validate_target_system_provider_profiles(
    profile_registry: TargetSystemProviderProfileRegistry,
    provider_registry: TargetSystemProviderRegistry,
    layer_plans: Sequence[TargetSystemLayerPlan],
) -> None:
    """Validate profile ownership against existing provider and plan authorities.

    This is an admission check only.  It runs no provider, discovers no target,
    and does not manufacture a missing profile or layer plan.
    """

    plans_by_profile = {plan.target_profile: plan for plan in layer_plans}
    if len(plans_by_profile) != len(tuple(layer_plans)):
        raise TargetSystemBlueprintError("profile admission received duplicate layer plans")
    providers = provider_registry.declaration_by_id
    for declaration in profile_registry.declarations:
        if declaration.provider_id not in providers:
            raise TargetSystemBlueprintError(
                f"provider profile names an unregistered provider: {declaration.provider_id}"
            )
        provider = providers[declaration.provider_id]
        # The provider contract is target-neutral.  FlowGuard validates that a
        # provider declared a non-empty kind, but it must not become the owner
        # of a closed list such as ``software`` or ``workflow``.  Domain
        # adapters may introduce their own kinds without changing this core
        # admission boundary.
        if not declaration.target_kind.strip():
            raise TargetSystemBlueprintError(
                f"provider profile target kind is empty: {declaration.provider_id}"
            )
        plan = plans_by_profile.get(declaration.target_profile)
        if plan is None:
            raise TargetSystemBlueprintError(
                f"provider profile references an unknown target profile: {declaration.target_profile}"
            )
        if declaration.layer_plan_id != plan.plan_id:
            raise TargetSystemBlueprintError(
                f"provider profile layer plan id differs from current profile plan: {declaration.provider_id}"
            )
        if declaration.layer_plan_fingerprint != plan.fingerprint:
            raise TargetSystemBlueprintError(
                f"provider profile layer plan fingerprint is stale: {declaration.provider_id}"
            )
        if declaration.provider_id != provider.provider_id:
            raise TargetSystemBlueprintError(
                f"provider profile identity differs from provider registry: {declaration.provider_id}"
            )


@dataclass(frozen=True)
class TargetSystemDnaQualification:
    """Provider-neutral, non-reconstructive qualification of one layered DNA."""

    qualification_id: str
    target_system_id: str
    target_profile: str
    static_status: str
    semantic_status: str
    code_binding_status: str
    test_binding_status: str
    semantic_evidence_fingerprint: str
    code_binding_fingerprint: str
    test_binding_fingerprint: str
    reasons: tuple[str, ...] = ()
    claim_boundary: str = (
        "Qualification reports current evidence identities only; it does not run "
        "providers or reconstruct the target system."
    )

    def __post_init__(self) -> None:
        for field_name in (
            "qualification_id",
            "target_system_id",
            "target_profile",
            "semantic_evidence_fingerprint",
            "code_binding_fingerprint",
            "test_binding_fingerprint",
            "claim_boundary",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), f"DNA qualification {field_name}"),
            )
        for field_name in (
            "static_status",
            "semantic_status",
            "code_binding_status",
            "test_binding_status",
        ):
            status = str(getattr(self, field_name))
            if status not in DNA_QUALIFICATION_STATUSES:
                raise TargetSystemBlueprintError(
                    f"DNA qualification status is not current: {field_name}={status}"
                )
            object.__setattr__(self, field_name, status)
        object.__setattr__(self, "reasons", _strings(self.reasons, "DNA qualification reason"))

    @property
    def qualified(self) -> bool:
        return all(
            status == "current"
            for status in (
                self.static_status,
                self.semantic_status,
                self.code_binding_status,
                self.test_binding_status,
            )
        )

    @property
    def status(self) -> str:
        return "qualified" if self.qualified else "blocked"

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_DNA_QUALIFICATION_SCHEMA,
            "qualification_id": self.qualification_id,
            "target_system_id": self.target_system_id,
            "target_profile": self.target_profile,
            "static_status": self.static_status,
            "semantic_status": self.semantic_status,
            "code_binding_status": self.code_binding_status,
            "test_binding_status": self.test_binding_status,
            "semantic_evidence_fingerprint": self.semantic_evidence_fingerprint,
            "code_binding_fingerprint": self.code_binding_fingerprint,
            "test_binding_fingerprint": self.test_binding_fingerprint,
            "reasons": list(self.reasons),
            "status": self.status,
            "qualified": self.qualified,
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemDnaQualification":
        fields = (
            "schema_version",
            "qualification_id",
            "target_system_id",
            "target_profile",
            "static_status",
            "semantic_status",
            "code_binding_status",
            "test_binding_status",
            "semantic_evidence_fingerprint",
            "code_binding_fingerprint",
            "test_binding_fingerprint",
            "reasons",
            "status",
            "qualified",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(value, fields=fields, context="target-system DNA qualification")
        if data["schema_version"] != TARGET_SYSTEM_DNA_QUALIFICATION_SCHEMA:
            raise TargetSystemBlueprintError("target-system DNA qualification schema is not current")
        qualification = cls(
            qualification_id=data["qualification_id"],
            target_system_id=data["target_system_id"],
            target_profile=data["target_profile"],
            static_status=data["static_status"],
            semantic_status=data["semantic_status"],
            code_binding_status=data["code_binding_status"],
            test_binding_status=data["test_binding_status"],
            semantic_evidence_fingerprint=data["semantic_evidence_fingerprint"],
            code_binding_fingerprint=data["code_binding_fingerprint"],
            test_binding_fingerprint=data["test_binding_fingerprint"],
            reasons=tuple(_array(data["reasons"], "DNA qualification reasons")),
            claim_boundary=data["claim_boundary"],
        )
        if data["status"] != qualification.status or bool(data["qualified"]) != qualification.qualified:
            raise TargetSystemBlueprintError("target-system DNA qualification status projection mismatch")
        if qualification.fingerprint != _text(data["fingerprint"], "DNA qualification fingerprint"):
            raise TargetSystemBlueprintError("target-system DNA qualification fingerprint mismatch")
        return qualification


def qualify_target_system_dna(
    report: "TargetSystemBlueprintReport",
    *,
    qualification_id: str,
    semantic_status: str,
    semantic_evidence_fingerprint: str,
    semantic_binding_current: bool,
    code_binding_status: str,
    code_binding_fingerprint: str,
    test_binding_status: str,
    test_binding_fingerprint: str,
) -> TargetSystemDnaQualification:
    """Derive one honest qualification result from already-owned evidence."""

    reasons: list[str] = []
    static_status = "current" if report.ok else {
        "pass": "current",
        "incomplete": "incomplete",
        "stale": "stale",
        "blocked": "blocked",
        "not_applicable": "not_applicable",
    }.get(report.status, "unknown")
    if static_status != "current":
        reasons.append(f"static:{static_status}")
    raw_semantic = str(semantic_status).strip()
    if raw_semantic in {"current", "complete"} and semantic_binding_current and semantic_evidence_fingerprint:
        normalized_semantic = "current"
    elif raw_semantic in {"candidate", "candidate_defined_not_verified"}:
        normalized_semantic = "candidate"
        reasons.append("semantic:candidate_defined_not_verified")
    elif raw_semantic in DNA_QUALIFICATION_STATUSES:
        normalized_semantic = raw_semantic
        reasons.append(f"semantic:{raw_semantic}")
    else:
        normalized_semantic = "unknown"
        reasons.append(f"semantic:unknown:{raw_semantic or 'empty'}")
    if normalized_semantic == "current" and not semantic_binding_current:
        normalized_semantic = "stale"
        reasons.append("semantic:binding_not_current")
    code_status = str(code_binding_status or "unknown").strip()
    if code_status in {"complete", "pass"}:
        code_status = "current"
    if code_status not in DNA_QUALIFICATION_STATUSES:
        code_status = "unknown"
    if code_status != "current":
        reasons.append(f"code_binding:{code_status}")
    test_status = str(test_binding_status or "unknown").strip()
    if test_status in {"complete", "pass"}:
        test_status = "current"
    if test_status not in DNA_QUALIFICATION_STATUSES:
        test_status = "unknown"
    if test_status != "current":
        reasons.append(f"test_binding:{test_status}")
    return TargetSystemDnaQualification(
        qualification_id=qualification_id,
        target_system_id=report.descriptor.target_system_id,
        target_profile=report.target_profile,
        static_status=static_status,
        semantic_status=normalized_semantic,
        code_binding_status=code_status,
        test_binding_status=test_status,
        semantic_evidence_fingerprint=str(semantic_evidence_fingerprint or "missing"),
        code_binding_fingerprint=str(code_binding_fingerprint or "missing"),
        test_binding_fingerprint=str(test_binding_fingerprint or "missing"),
        reasons=tuple(sorted(set(reasons))),
    )


@dataclass(frozen=True)
class TargetSystemSnapshot:
    """Frozen descriptor and provider-result identities; it executes nothing."""

    snapshot_id: str
    target_system_id: str
    subject_revision: str
    descriptor_fingerprint: str
    registry_fingerprint: str
    provider_result_fingerprints: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(
            self,
            "target_system_id",
            _text(self.target_system_id, "target_system_id"),
        )
        object.__setattr__(
            self,
            "subject_revision",
            _text(self.subject_revision, "subject_revision"),
        )
        object.__setattr__(
            self,
            "descriptor_fingerprint",
            _text(self.descriptor_fingerprint, "descriptor_fingerprint"),
        )
        object.__setattr__(
            self,
            "registry_fingerprint",
            _text(self.registry_fingerprint, "registry_fingerprint"),
        )
        object.__setattr__(
            self,
            "provider_result_fingerprints",
            _pairs(
                self.provider_result_fingerprints,
                "snapshot provider result fingerprint",
            ),
        )
        if not self.provider_result_fingerprints:
            raise TargetSystemBlueprintError(
                "target-system snapshot requires provider result identities"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_SNAPSHOT_SCHEMA,
            "snapshot_id": self.snapshot_id,
            "target_system_id": self.target_system_id,
            "subject_revision": self.subject_revision,
            "descriptor_fingerprint": self.descriptor_fingerprint,
            "registry_fingerprint": self.registry_fingerprint,
            "provider_result_fingerprints": dict(
                self.provider_result_fingerprints
            ),
            "claim_boundary": (
                "Frozen target and provider identities only; creating a snapshot "
                "does not run providers or prove readiness."
            ),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetSystemSnapshot":
        fields = (
            "schema_version",
            "snapshot_id",
            "target_system_id",
            "subject_revision",
            "descriptor_fingerprint",
            "registry_fingerprint",
            "provider_result_fingerprints",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(value, fields=fields, context="target-system snapshot")
        if data["schema_version"] != TARGET_SYSTEM_SNAPSHOT_SCHEMA:
            raise TargetSystemBlueprintError("target-system snapshot schema is not current")
        expected_claim = (
            "Frozen target and provider identities only; creating a snapshot "
            "does not run providers or prove readiness."
        )
        if data["claim_boundary"] != expected_claim:
            raise TargetSystemBlueprintError("target-system snapshot claim boundary is not current")
        snapshot = cls(
            snapshot_id=data["snapshot_id"],
            target_system_id=data["target_system_id"],
            subject_revision=data["subject_revision"],
            descriptor_fingerprint=data["descriptor_fingerprint"],
            registry_fingerprint=data["registry_fingerprint"],
            provider_result_fingerprints=_mapping_pairs(
                data["provider_result_fingerprints"],
                "snapshot provider result fingerprints",
            ),
        )
        if snapshot.fingerprint != _text(data["fingerprint"], "target-system snapshot fingerprint"):
            raise TargetSystemBlueprintError("target-system snapshot fingerprint mismatch")
        return snapshot


@dataclass(frozen=True)
class FrozenTargetSystemEvidence:
    """Pre-established external inputs consumed by the blueprint compiler.

    Constructing this aggregate only freezes identities already supplied by a
    caller.  It deliberately does not run, discover, rebuild, or repair a
    provider result; cross-artifact drift remains visible to the compiler.
    """

    evidence_id: str
    layer_plan: TargetSystemLayerPlan
    provider_registry: TargetSystemProviderRegistry
    provider_results: tuple[TargetSystemProviderResult, ...]
    snapshot: TargetSystemSnapshot
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _text(self.evidence_id, "frozen evidence id"))
        object.__setattr__(
            self,
            "claim_boundary",
            _text(self.claim_boundary, "frozen evidence claim boundary"),
        )
        providers = tuple(self.provider_results)
        provider_ids = tuple(row.provider_id for row in providers)
        if not providers or len(provider_ids) != len(set(provider_ids)):
            raise TargetSystemBlueprintError(
                "frozen target-system evidence requires unique provider results"
            )
        object.__setattr__(self, "provider_results", providers)

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": FROZEN_TARGET_SYSTEM_EVIDENCE_SCHEMA,
            "evidence_id": self.evidence_id,
            "layer_plan": self.layer_plan.to_dict(),
            "provider_registry": self.provider_registry.to_dict(),
            "provider_results": [row.to_dict() for row in self.provider_results],
            "snapshot": self.snapshot.to_dict(),
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "FrozenTargetSystemEvidence":
        fields = (
            "schema_version",
            "evidence_id",
            "layer_plan",
            "provider_registry",
            "provider_results",
            "snapshot",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict_object(value, fields=fields, context="frozen target-system evidence")
        if data["schema_version"] != FROZEN_TARGET_SYSTEM_EVIDENCE_SCHEMA:
            raise TargetSystemBlueprintError("frozen target-system evidence schema is not current")
        frozen = cls(
            evidence_id=data["evidence_id"],
            layer_plan=TargetSystemLayerPlan.from_dict(data["layer_plan"]),
            provider_registry=TargetSystemProviderRegistry.from_dict(
                data["provider_registry"]
            ),
            provider_results=tuple(
                TargetSystemProviderResult.from_dict(item)
                for item in _array(data["provider_results"], "frozen provider results")
            ),
            snapshot=TargetSystemSnapshot.from_dict(data["snapshot"]),
            claim_boundary=data["claim_boundary"],
        )
        if frozen.fingerprint != _text(data["fingerprint"], "frozen evidence fingerprint"):
            raise TargetSystemBlueprintError("frozen target-system evidence fingerprint mismatch")
        return frozen


def serialize_target_system_layer_plan(plan: TargetSystemLayerPlan) -> bytes:
    return canonical_json_bytes(plan.to_dict())


def serialize_target_system_descriptor(descriptor: TargetSystemDescriptor) -> bytes:
    return canonical_json_bytes(descriptor.to_dict())


def load_target_system_descriptor(path: str | Path) -> TargetSystemDescriptor:
    return TargetSystemDescriptor.from_dict(
        _load_json_object(path, "target-system descriptor")
    )


def load_target_system_layer_plan(path: str | Path) -> TargetSystemLayerPlan:
    return TargetSystemLayerPlan.from_dict(_load_json_object(path, "target-system layer plan"))


def serialize_target_system_provider_result(result: TargetSystemProviderResult) -> bytes:
    return canonical_json_bytes(result.to_dict())


def load_target_system_provider_result(path: str | Path) -> TargetSystemProviderResult:
    return TargetSystemProviderResult.from_dict(
        _load_json_object(path, "target-system provider result")
    )


def serialize_target_system_provider_registry(registry: TargetSystemProviderRegistry) -> bytes:
    return canonical_json_bytes(registry.to_dict())


def load_target_system_provider_registry(path: str | Path) -> TargetSystemProviderRegistry:
    return TargetSystemProviderRegistry.from_dict(
        _load_json_object(path, "target-system provider registry")
    )


def serialize_target_system_provider_profile_registry(
    registry: TargetSystemProviderProfileRegistry,
) -> bytes:
    return canonical_json_bytes(registry.to_dict())


def load_target_system_provider_profile_registry(
    path: str | Path,
) -> TargetSystemProviderProfileRegistry:
    return TargetSystemProviderProfileRegistry.from_dict(
        _load_json_object(path, "target-system provider profile registry")
    )


def serialize_target_system_snapshot(snapshot: TargetSystemSnapshot) -> bytes:
    return canonical_json_bytes(snapshot.to_dict())


def load_target_system_snapshot(path: str | Path) -> TargetSystemSnapshot:
    return TargetSystemSnapshot.from_dict(_load_json_object(path, "target-system snapshot"))


def serialize_frozen_target_system_evidence(evidence: FrozenTargetSystemEvidence) -> bytes:
    return canonical_json_bytes(evidence.to_dict())


def load_frozen_target_system_evidence(path: str | Path) -> FrozenTargetSystemEvidence:
    return FrozenTargetSystemEvidence.from_dict(
        _load_json_object(path, "frozen target-system evidence")
    )


@dataclass(frozen=True)
class BlueprintGapRef:
    layer: str
    object_kind: str
    object_id: str
    status: str
    owner_id: str = ""
    evidence_ref: str = ""
    expected_fingerprint: str = ""
    observed_fingerprint: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "layer", _text(self.layer, "blueprint gap layer"))
        if self.status not in {"missing", "incomplete", "stale", "blocked", "not_run"}:
            raise TargetSystemBlueprintError(f"unknown blueprint gap status: {self.status}")
        object.__setattr__(self, "object_kind", _text(self.object_kind, "object_kind"))
        object.__setattr__(self, "object_id", _text(self.object_id, "object_id"))
        object.__setattr__(self, "message", _text(self.message, "message"))

    @property
    def gap_id(self) -> str:
        return "blueprint-gap:" + fingerprint_value(self.to_dict()).split(":", 1)[-1]

    def to_dict(self) -> dict[str, str]:
        return {
            "layer": self.layer,
            "object_kind": self.object_kind,
            "object_id": self.object_id,
            "status": self.status,
            "owner_id": self.owner_id,
            "evidence_ref": self.evidence_ref,
            "expected_fingerprint": self.expected_fingerprint,
            "observed_fingerprint": self.observed_fingerprint,
            "message": self.message,
        }


@dataclass(frozen=True)
class BlueprintNativeReportRef:
    """Exact native owner/report identity consumed by one readiness row."""

    owner_id: str
    report_id: str
    report_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text(self.owner_id, "native report owner"))
        object.__setattr__(self, "report_id", _text(self.report_id, "native report id"))
        object.__setattr__(
            self,
            "report_fingerprint",
            _text(self.report_fingerprint, "native report fingerprint"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "owner_id": self.owner_id,
            "report_id": self.report_id,
            "report_fingerprint": self.report_fingerprint,
        }


@dataclass(frozen=True)
class BlueprintLayerResult:
    layer: str
    status: str
    evidence_ids: tuple[str, ...] = ()
    gap_ids: tuple[str, ...] = ()
    native_reports: tuple[BlueprintNativeReportRef, ...] = ()
    pre_code_status: str = "not_applicable"
    executed_evidence_status: str = "not_applicable"
    implementation_admitted: bool = False
    _derivation_token: object = field(
        default=None,
        repr=False,
        compare=False,
        kw_only=True,
    )

    @classmethod
    def _derived(cls, **values: Any) -> "BlueprintLayerResult":
        """Build one compiler-owned row; public callers cannot assert status."""

        return cls(_derivation_token=_BLUEPRINT_DERIVATION_TOKEN, **values)

    def __post_init__(self) -> None:
        if self._derivation_token is not _BLUEPRINT_DERIVATION_TOKEN:
            raise TargetSystemBlueprintError(
                "blueprint layer results are derived by the native qualifier"
            )
        object.__setattr__(self, "layer", _text(self.layer, "blueprint layer"))
        if self.status not in LAYER_STATUSES:
            raise TargetSystemBlueprintError(f"unknown layer status: {self.status}")
        object.__setattr__(self, "evidence_ids", _strings(self.evidence_ids, "layer evidence"))
        object.__setattr__(self, "gap_ids", _strings(self.gap_ids, "layer gap"))
        object.__setattr__(
            self,
            "native_reports",
            tuple(
                sorted(
                    self.native_reports,
                    key=lambda row: (row.owner_id, row.report_id),
                )
            ),
        )
        native_ids = tuple(
            (row.owner_id, row.report_id) for row in self.native_reports
        )
        if len(native_ids) != len(set(native_ids)):
            raise TargetSystemBlueprintError(
                "blueprint layer contains duplicate native report identities"
            )
        if self.pre_code_status not in PRE_CODE_STATUSES:
            raise TargetSystemBlueprintError(
                f"unknown pre-code status: {self.pre_code_status}"
            )
        if self.executed_evidence_status not in EXECUTED_EVIDENCE_STATUSES:
            raise TargetSystemBlueprintError(
                "unknown executed-evidence status: "
                f"{self.executed_evidence_status}"
            )
        if not isinstance(self.implementation_admitted, bool):
            raise TargetSystemBlueprintError(
                "implementation_admitted must be a boolean"
            )
        if self.status == "pass" and self.gap_ids:
            raise TargetSystemBlueprintError("passing blueprint layer cannot contain gaps")
        if self.status != "pass" and not self.gap_ids:
            raise TargetSystemBlueprintError("non-passing blueprint layer requires a gap")
        if self.status != "pass" and self.implementation_admitted:
            raise TargetSystemBlueprintError(
                "a non-passing blueprint layer cannot admit implementation"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "gap_ids": list(self.gap_ids),
            "native_reports": [row.to_dict() for row in self.native_reports],
            "pre_code_status": self.pre_code_status,
            "executed_evidence_status": self.executed_evidence_status,
            "implementation_admitted": self.implementation_admitted,
        }


def _aggregate_status(
    statuses: Iterable[str],
    *,
    passing: frozenset[str],
    default: str,
) -> str:
    values = tuple(statuses)
    if not values:
        return default
    priority = (
        "blocked",
        "error",
        "failed",
        "timeout",
        "stale",
        "incomplete",
        "running",
        "skipped",
        "not_run",
    )
    for status in priority:
        if status in values:
            return status
    if all(status == "not_applicable" for status in values):
        return "not_applicable"
    for status in values:
        if status in passing:
            return status
    return values[0]


@dataclass(frozen=True)
class BlueprintReadinessLedger:
    """Canonical ordered readiness and admission decision for one exact scope."""

    target_profile: str
    rows: tuple[BlueprintLayerResult, ...]
    gaps: tuple[BlueprintGapRef, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "target_profile", _text(self.target_profile, "ledger target profile")
        )
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "gaps", tuple(self.gaps))
        if not self.rows:
            raise TargetSystemBlueprintError("readiness ledger requires ordered rows")
        layer_ids = tuple(row.layer for row in self.rows)
        if len(layer_ids) != len(set(layer_ids)):
            raise TargetSystemBlueprintError("readiness ledger contains duplicate layers")
        known_gap_ids = {row.gap_id for row in self.gaps}
        referenced_gap_ids = {
            gap_id for row in self.rows for gap_id in row.gap_ids
        }
        if known_gap_ids != referenced_gap_ids:
            raise TargetSystemBlueprintError(
                "readiness ledger gap references are not complete"
            )
        lower_pass = True
        for row in self.rows:
            if row.status == "pass" and not lower_pass:
                raise TargetSystemBlueprintError(
                    "readiness ledger cannot pass after an unresolved lower layer"
                )
            lower_pass = lower_pass and row.status == "pass"
        admitted_rows = tuple(row for row in self.rows if row.implementation_admitted)
        if admitted_rows and (
            self.target_profile != SOFTWARE_TARGET_PROFILE
            or admitted_rows != (self.rows[-1],)
            or not self.ok
        ):
            raise TargetSystemBlueprintError(
                "implementation admission must be the passing final software row"
            )

    @property
    def status(self) -> str:
        return self.rows[-1].status

    @property
    def ok(self) -> bool:
        return all(row.status == "pass" for row in self.rows)

    @property
    def deepest_proven_layer(self) -> str:
        deepest = ""
        for row in self.rows:
            if row.status != "pass":
                break
            deepest = row.layer
        return deepest

    @property
    def first_gap(self) -> BlueprintGapRef | None:
        if not self.gaps:
            return None
        layer_index = {row.layer: index for index, row in enumerate(self.rows)}
        return min(
            self.gaps,
            key=lambda row: (
                layer_index[row.layer],
                row.object_kind,
                row.object_id,
            ),
        )

    @property
    def gap_count(self) -> int:
        return len(self.gaps)

    @property
    def pre_code_status(self) -> str:
        return _aggregate_status(
            (row.pre_code_status for row in self.rows),
            passing=frozenset({"ready"}),
            default="not_applicable",
        )

    @property
    def executed_evidence_status(self) -> str:
        return _aggregate_status(
            (row.executed_evidence_status for row in self.rows),
            passing=frozenset({"passed"}),
            default="not_applicable",
        )

    @property
    def implementation_admitted(self) -> bool:
        return bool(self.rows[-1].implementation_admitted)

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "target_profile": self.target_profile,
            "rows": [row.to_dict() for row in self.rows],
            "gaps": [{"gap_id": row.gap_id, **row.to_dict()} for row in self.gaps],
            "status": self.status,
            "ok": self.ok,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_gap": (
                {"gap_id": self.first_gap.gap_id, **self.first_gap.to_dict()}
                if self.first_gap
                else None
            ),
            "gap_count": self.gap_count,
            "pre_code_status": self.pre_code_status,
            "executed_evidence_status": self.executed_evidence_status,
            "implementation_admitted": self.implementation_admitted,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class TargetSystemBlueprintReport:
    descriptor: TargetSystemDescriptor
    layer_plan: TargetSystemLayerPlan
    provider_results: tuple[TargetSystemProviderResult, ...]
    layers: tuple[BlueprintLayerResult, ...]
    gaps: tuple[BlueprintGapRef, ...]
    required_path_quality_model_ids: tuple[str, ...] = ()
    path_quality_bindings: tuple[ModelPathQualityBlueprintBinding, ...] = ()
    provider_registry_fingerprint: str = ""
    snapshot_fingerprint: str = ""
    scope: str = "whole"
    _derivation_token: object = field(
        default=None,
        repr=False,
        compare=False,
        kw_only=True,
    )

    @classmethod
    def _derived(cls, **values: Any) -> "TargetSystemBlueprintReport":
        """Build one compiler-owned report from verified frozen artifacts."""

        return cls(_derivation_token=_BLUEPRINT_DERIVATION_TOKEN, **values)

    def __post_init__(self) -> None:
        if self._derivation_token is not _BLUEPRINT_DERIVATION_TOKEN:
            raise TargetSystemBlueprintError(
                "target-system blueprint reports are derived by the native qualifier"
            )
        if self.scope not in {"affected", "whole"}:
            raise TargetSystemBlueprintError("blueprint report scope must be affected or whole")
        object.__setattr__(
            self,
            "provider_results",
            tuple(sorted(self.provider_results, key=lambda row: row.provider_id)),
        )
        object.__setattr__(
            self,
            "required_path_quality_model_ids",
            _strings(
                self.required_path_quality_model_ids,
                "required path-quality model id",
            ),
        )
        if any(
            not isinstance(row, ModelPathQualityBlueprintBinding)
            for row in self.path_quality_bindings
        ):
            raise TargetSystemBlueprintError(
                "target-system path-quality rows require current typed bindings"
            )
        object.__setattr__(
            self,
            "path_quality_bindings",
            tuple(
                sorted(
                    self.path_quality_bindings,
                    key=lambda row: (
                        row.model_element_id,
                        row.compact_current_fingerprint,
                    ),
                )
            ),
        )
        layer_index = {
            layer_id: index for index, layer_id in enumerate(self.layer_plan.layer_ids)
        }
        unknown_layers = {
            row.layer for row in (*self.layers, *self.gaps) if row.layer not in layer_index
        }
        if unknown_layers:
            raise TargetSystemBlueprintError(
                f"blueprint report contains layers absent from its plan: {sorted(unknown_layers)}"
            )
        object.__setattr__(
            self,
            "layers",
            tuple(sorted(self.layers, key=lambda row: layer_index[row.layer])),
        )
        object.__setattr__(
            self,
            "gaps",
            tuple(
                sorted(
                    self.gaps,
                    key=lambda row: (
                        layer_index[row.layer],
                        row.object_kind,
                        row.object_id,
                    ),
                )
            ),
        )
        if tuple(row.layer for row in self.layers) != self.layer_plan.layer_ids:
            raise TargetSystemBlueprintError(
                "blueprint report must contain every planned layer exactly once"
            )
        gap_ids = {row.gap_id for row in self.gaps}
        referenced = {gap_id for row in self.layers for gap_id in row.gap_ids}
        if gap_ids != referenced:
            raise TargetSystemBlueprintError("blueprint layer gap references are not complete")

    @property
    def status(self) -> str:
        return self.readiness_ledger.status

    @property
    def ok(self) -> bool:
        return self.readiness_ledger.ok

    @property
    def readiness_ledger(self) -> BlueprintReadinessLedger:
        return BlueprintReadinessLedger(
            target_profile=self.target_profile,
            rows=self.layers,
            gaps=self.gaps,
        )

    @property
    def target_profile(self) -> str:
        return self.layer_plan.target_profile

    @property
    def layer_plan_fingerprint(self) -> str:
        return self.layer_plan.fingerprint

    @property
    def deepest_proven_layer(self) -> str:
        return self.readiness_ledger.deepest_proven_layer

    @property
    def implementation_admitted(self) -> bool:
        return self.readiness_ledger.implementation_admitted

    @property
    def path_quality_result_set_fingerprint(self) -> str:
        return model_path_quality_binding_set_fingerprint(
            self.path_quality_bindings
        )

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_BLUEPRINT_SCHEMA,
            "descriptor": self.descriptor.to_dict(),
            "layer_plan": self.layer_plan.to_dict(),
            "target_profile": self.target_profile,
            "layer_plan_fingerprint": self.layer_plan_fingerprint,
            "provider_results": [row.to_dict() for row in self.provider_results],
            "provider_registry_fingerprint": self.provider_registry_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "required_path_quality_model_ids": list(
                self.required_path_quality_model_ids
            ),
            "path_quality_bindings": [
                row.to_dict() for row in self.path_quality_bindings
            ],
            "path_quality_result_set_fingerprint": (
                self.path_quality_result_set_fingerprint
            ),
            "layers": [row.to_dict() for row in self.layers],
            "readiness_ledger": self.readiness_ledger.to_dict(),
            "gaps": [{"gap_id": row.gap_id, **row.to_dict()} for row in self.gaps],
            "status": self.status,
            "ok": self.ok,
            "scope": self.scope,
            "deepest_proven_layer": self.deepest_proven_layer,
            "claim_boundary": (
                "Plan-specific target-system blueprint readiness only; provider completion does "
                "not prove factual correctness."
            ),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def validate_blueprint_native_reports(
    report: TargetSystemBlueprintReport,
    supplied_reports: Sequence[BlueprintNativeReportRef],
) -> BlueprintReadinessLedger:
    """Rebind a wrapper's child reports to the canonical ledger identities.

    The target report remains immutable.  A wrapper omission, substitution, or
    stale fingerprint is projected as an integrity gap at the first layer that
    consumes the expected native report, then the ordinary ordered-prefix rule
    blocks downstream admission.
    """

    base = report.readiness_ledger
    supplied = tuple(supplied_reports)
    supplied_by_identity = {
        (row.owner_id, row.report_id): row for row in supplied
    }
    if len(supplied_by_identity) != len(supplied):
        raise TargetSystemBlueprintError(
            "supplied wrapper reports contain duplicate native identities"
        )
    supplied_by_owner: dict[str, tuple[BlueprintNativeReportRef, ...]] = {}
    for row in supplied:
        supplied_by_owner.setdefault(row.owner_id, ())
        supplied_by_owner[row.owner_id] = (
            *supplied_by_owner[row.owner_id],
            row,
        )

    expected_locations: dict[tuple[str, str], str] = {}
    expected_refs: dict[tuple[str, str], BlueprintNativeReportRef] = {}
    for layer in base.rows[1:]:
        for expected in layer.native_reports:
            identity = (expected.owner_id, expected.report_id)
            expected_locations.setdefault(identity, layer.layer)
            previous = expected_refs.get(identity)
            if previous is not None and previous != expected:
                raise TargetSystemBlueprintError(
                    "canonical ledger reuses one native report identity with "
                    "different fingerprints"
                )
            expected_refs[identity] = expected

    integrity_gaps: list[BlueprintGapRef] = []
    for identity, expected in expected_refs.items():
        layer = expected_locations[identity]
        observed = supplied_by_identity.get(identity)
        if observed is None:
            same_owner = supplied_by_owner.get(expected.owner_id, ())
            integrity_gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind=(
                        "native_report_substitution"
                        if same_owner
                        else "native_report_omission"
                    ),
                    object_id=f"{expected.owner_id}:{expected.report_id}",
                    status="blocked",
                    owner_id=expected.owner_id,
                    expected_fingerprint=expected.report_fingerprint,
                    observed_fingerprint=(
                        same_owner[0].report_fingerprint if same_owner else ""
                    ),
                    message=(
                        "wrapper did not supply the exact native report identity "
                        "consumed by the canonical readiness ledger"
                    ),
                )
            )
            continue
        if observed.report_fingerprint != expected.report_fingerprint:
            integrity_gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind="native_report_fingerprint",
                    object_id=f"{expected.owner_id}:{expected.report_id}",
                    status="stale",
                    owner_id=expected.owner_id,
                    expected_fingerprint=expected.report_fingerprint,
                    observed_fingerprint=observed.report_fingerprint,
                    message=(
                        "wrapper supplied the expected native report identity with "
                        "a different fingerprint"
                    ),
                )
            )

    expected_identities = set(expected_refs)
    for identity, observed in supplied_by_identity.items():
        if identity in expected_identities:
            continue
        integrity_gaps.append(
            BlueprintGapRef(
                layer=base.rows[0].layer,
                object_kind="unexpected_native_report",
                object_id=f"{observed.owner_id}:{observed.report_id}",
                status="blocked",
                owner_id=observed.owner_id,
                observed_fingerprint=observed.report_fingerprint,
                message=(
                    "wrapper supplied a native report absent from the canonical "
                    "readiness ledger"
                ),
            )
        )
    if not integrity_gaps:
        return base

    gaps = list((*base.gaps, *integrity_gaps))
    rows: list[BlueprintLayerResult] = []
    lower_pass = True
    for base_row in base.rows:
        row = replace(base_row, implementation_admitted=False)
        row_gaps = tuple(gap for gap in gaps if gap.layer == row.layer)
        if row_gaps:
            if any(gap.status == "blocked" for gap in row_gaps):
                row_status = "blocked"
            elif any(gap.status == "stale" for gap in row_gaps):
                row_status = "stale"
            elif row.status == "not_run":
                row_status = "not_run"
            else:
                row_status = "incomplete"
            row = replace(
                row,
                status=(row_status if row.status == "pass" else row.status),
                gap_ids=tuple((*row.gap_ids, *(gap.gap_id for gap in row_gaps))),
            )
        if not lower_pass and row.status == "pass":
            dependency_gap = BlueprintGapRef(
                layer=row.layer,
                object_kind="lower_layer_dependency",
                object_id=rows[-1].layer,
                status="blocked",
                evidence_ref=rows[-1].layer,
                message=(
                    "a later blueprint layer cannot pass while a wrapper integrity "
                    "gap remains below it"
                ),
            )
            gaps.append(dependency_gap)
            row = replace(
                row,
                status="blocked",
                gap_ids=(dependency_gap.gap_id,),
            )
        rows.append(row)
        lower_pass = lower_pass and row.status == "pass"

    if (
        report.target_profile == SOFTWARE_TARGET_PROFILE
        and all(row.status == "pass" for row in rows)
    ):
        rows[-1] = replace(rows[-1], implementation_admitted=True)
    referenced = {gap_id for row in rows for gap_id in row.gap_ids}
    return BlueprintReadinessLedger(
        target_profile=report.target_profile,
        rows=tuple(rows),
        gaps=tuple(gap for gap in gaps if gap.gap_id in referenced),
    )


@dataclass(frozen=True)
class BlueprintUnderstandingSummary:
    scope: str
    target_system_id: str
    target_profile: str
    subject_revision: str
    descriptor_fingerprint: str
    blueprint_fingerprint: str
    layer_plan_id: str
    layer_plan_fingerprint: str
    layer_statuses: tuple[tuple[str, str], ...]
    status: str
    deepest_proven_layer: str
    first_gap: BlueprintGapRef | None
    gap_count: int
    implementation_admitted: bool
    affected_surface_ids: tuple[str, ...] = ()
    provider_fingerprints: tuple[tuple[str, str], ...] = ()
    required_path_quality_model_ids: tuple[str, ...] = ()
    path_quality_bindings: tuple[ModelPathQualityBlueprintBinding, ...] = ()

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": BLUEPRINT_UNDERSTANDING_SCHEMA,
            "scope": self.scope,
            "target_system_id": self.target_system_id,
            "target_profile": self.target_profile,
            "subject_revision": self.subject_revision,
            "descriptor_fingerprint": self.descriptor_fingerprint,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "layer_plan_id": self.layer_plan_id,
            "layer_plan_fingerprint": self.layer_plan_fingerprint,
            "layer_statuses": [
                {"layer": layer, "status": status}
                for layer, status in self.layer_statuses
            ],
            "status": self.status,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_gap": (
                {"gap_id": self.first_gap.gap_id, **self.first_gap.to_dict()}
                if self.first_gap
                else None
            ),
            "gap_count": self.gap_count,
            "implementation_admitted": self.implementation_admitted,
            "affected_ids": list(self.affected_surface_ids),
            "provider_fingerprints": dict(self.provider_fingerprints),
            "required_path_quality_model_ids": list(
                self.required_path_quality_model_ids
            ),
            "path_quality_bindings": [
                row.to_dict() for row in self.path_quality_bindings
            ],
            "path_quality_result_set_fingerprint": (
                model_path_quality_binding_set_fingerprint(
                    self.path_quality_bindings
                )
            ),
            "claim_boundary": (
                "Read-only compact projection of one canonical blueprint report; it does "
                "not run providers or validation owners."
            ),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def build_target_system_provider_registry(
    registry_id: str,
    declarations: Sequence[TargetSystemProviderDeclaration],
) -> TargetSystemProviderRegistry:
    """Freeze one direct-current provider denominator without loading providers."""

    return TargetSystemProviderRegistry(registry_id, tuple(declarations))


def capture_target_system_snapshot(
    snapshot_id: str,
    descriptor: TargetSystemDescriptor,
    registry: TargetSystemProviderRegistry,
    provider_results: Sequence[TargetSystemProviderResult],
) -> TargetSystemSnapshot:
    """Capture exact already-produced identities; this function performs no work."""

    return TargetSystemSnapshot(
        snapshot_id=snapshot_id,
        target_system_id=descriptor.target_system_id,
        subject_revision=descriptor.subject_revision,
        descriptor_fingerprint=descriptor.fingerprint,
        registry_fingerprint=registry.fingerprint,
        provider_result_fingerprints=tuple(
            (row.provider_id, row.fingerprint) for row in provider_results
        ),
    )


def _assemble_target_system_blueprint(
    descriptor: TargetSystemDescriptor,
    frozen_evidence: FrozenTargetSystemEvidence,
    *,
    downstream_layers: Sequence[BlueprintLayerResult],
    downstream_gaps: Sequence[BlueprintGapRef] = (),
    required_path_quality_model_ids: Sequence[str] = (),
    path_quality_bindings: Sequence[ModelPathQualityBlueprintBinding] = (),
    scope: str = "whole",
) -> TargetSystemBlueprintReport:
    """Compile only pre-established external evidence under one exact plan."""

    if scope not in {"affected", "whole"}:
        raise TargetSystemBlueprintError("blueprint scope must be affected or whole")
    plan = frozen_evidence.layer_plan
    provider_registry = frozen_evidence.provider_registry
    providers = frozen_evidence.provider_results
    snapshot = frozen_evidence.snapshot
    provider_ids = tuple(row.provider_id for row in providers)
    if len(provider_ids) != len(set(provider_ids)):
        raise TargetSystemBlueprintError("provider identities must be unique")
    gaps: list[BlueprintGapRef] = []
    required_path_ids = _strings(
        required_path_quality_model_ids,
        "required path-quality model id",
    )
    raw_path_bindings = tuple(path_quality_bindings)
    if any(
        not isinstance(row, ModelPathQualityBlueprintBinding)
        for row in raw_path_bindings
    ):
        raise TargetSystemBlueprintError(
            "target-system path-quality rows require current typed bindings"
        )
    supplied_path_bindings = tuple(
        sorted(
            raw_path_bindings,
            key=lambda row: (
                row.model_element_id,
                row.compact_current_fingerprint,
            ),
        )
    )
    path_layer = (
        "model_code_test"
        if "model_code_test" in plan.layer_ids
        else "workflow_verification"
        if "workflow_verification" in plan.layer_ids
        else "evidence_qualification"
    )
    path_binding_ids = tuple(
        row.model_element_id for row in supplied_path_bindings
    )
    duplicate_path_ids = tuple(
        sorted(
            model_id
            for model_id in set(path_binding_ids)
            if path_binding_ids.count(model_id) > 1
        )
    )
    for model_id in duplicate_path_ids:
        gaps.append(
            BlueprintGapRef(
                layer=path_layer,
                object_kind="model_path_quality_duplicate",
                object_id=model_id,
                status="blocked",
                message="required model has more than one compact path-quality owner",
            )
        )
    supplied_path_ids = set(path_binding_ids)
    for model_id in sorted(set(required_path_ids) - supplied_path_ids):
        gaps.append(
            BlueprintGapRef(
                layer=path_layer,
                object_kind="model_path_quality_missing",
                object_id=model_id,
                status="missing",
                message="required model has no current compact path-quality result",
            )
        )
    for model_id in sorted(supplied_path_ids - set(required_path_ids)):
        gaps.append(
            BlueprintGapRef(
                layer=path_layer,
                object_kind="model_path_quality_unobserved",
                object_id=model_id,
                status="blocked",
                message="path-quality result is absent from the required model denominator",
            )
        )
    for binding in supplied_path_bindings:
        if binding.model_element_id not in set(required_path_ids):
            continue
        if not binding.result.current:
            gaps.append(
                BlueprintGapRef(
                    layer=path_layer,
                    object_kind="model_path_quality_stale",
                    object_id=binding.model_element_id,
                    status="stale",
                    evidence_ref=binding.compact_current_fingerprint,
                    observed_fingerprint=binding.result.fingerprint,
                    message="required model path-quality result is not current",
                )
            )
        elif binding.subject_lane != "observed":
            gaps.append(
                BlueprintGapRef(
                    layer=path_layer,
                    object_kind="model_path_quality_normative_only",
                    object_id=binding.model_element_id,
                    status="blocked",
                    evidence_ref=binding.compact_current_fingerprint,
                    message="normative path-quality evidence cannot license observed readiness",
                )
            )
        elif binding.result.selected_candidate_lane == "normative_target":
            gaps.append(
                BlueprintGapRef(
                    layer=path_layer,
                    object_kind="model_path_quality_normative_selection",
                    object_id=binding.model_element_id,
                    status="blocked",
                    evidence_ref=binding.compact_current_fingerprint,
                    message="a normative candidate is not current observed behavior",
                )
            )
        elif binding.result.conclusion == "unresolved":
            gaps.append(
                BlueprintGapRef(
                    layer=path_layer,
                    object_kind="model_path_quality_unresolved",
                    object_id=binding.model_element_id,
                    status="blocked",
                    evidence_ref=binding.detail_evidence_fingerprint,
                    observed_fingerprint=binding.compact_current_fingerprint,
                    message=(
                        "required model path-quality result remains unresolved: "
                        + ",".join(binding.result.unresolved_ids)
                    ),
                )
            )
    if descriptor.target_profile != plan.target_profile:
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="target_profile",
                object_id=descriptor.target_profile,
                status="blocked",
                expected_fingerprint=descriptor.target_profile,
                observed_fingerprint=plan.target_profile,
                message="target descriptor profile differs from the frozen layer plan",
            )
        )
    canonical_plan = {
        SOFTWARE_TARGET_PROFILE: CANONICAL_SOFTWARE_LAYER_PLAN,
        NON_CODE_WORKFLOW_TARGET_PROFILE: CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
    }.get(descriptor.target_profile)
    if canonical_plan is None:
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="target_profile_plan_authority",
                object_id=descriptor.target_profile,
                status="blocked",
                observed_fingerprint=plan.fingerprint,
                message=(
                    "target profile has no current registered canonical layer-plan "
                    "authority"
                ),
            )
        )
    elif plan.fingerprint != canonical_plan.fingerprint:
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="target_profile_layer_plan",
                object_id=plan.plan_id,
                status="blocked",
                expected_fingerprint=canonical_plan.fingerprint,
                observed_fingerprint=plan.fingerprint,
                message=(
                    "frozen layer plan differs from the exact canonical plan for "
                    "the target profile"
                ),
            )
        )
    declarations = provider_registry.declaration_by_id
    for provider in providers:
        declaration = declarations.get(provider.provider_id)
        if declaration is None:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="provider_registration",
                    object_id=provider.provider_id,
                    status="blocked",
                    evidence_ref=provider.fingerprint,
                    message="provider result is absent from the frozen registry",
                )
            )
            continue
        if (
            provider.provider_role != declaration.provider_role
            or provider.provider_kind != declaration.provider_kind
            or provider.provider_version != declaration.provider_version
            or provider.capability_ids != declaration.capability_ids
        ):
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="provider_registration",
                    object_id=provider.provider_id,
                    status="blocked",
                    evidence_ref=provider.fingerprint,
                    expected_fingerprint=declaration.fingerprint,
                    observed_fingerprint=provider.fingerprint,
                    message="provider result identity or capabilities differ from the frozen registry",
                )
            )
    for provider_id in sorted(set(declarations) - set(provider_ids)):
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="provider_registration",
                object_id=provider_id,
                status="missing",
                expected_fingerprint=declarations[provider_id].fingerprint,
                message="registered provider has no result in the frozen evidence set",
            )
        )
    expected_results = {row.provider_id: row.fingerprint for row in providers}
    if (
        snapshot.target_system_id != descriptor.target_system_id
        or snapshot.subject_revision != descriptor.subject_revision
        or snapshot.descriptor_fingerprint != descriptor.fingerprint
        or snapshot.registry_fingerprint != provider_registry.fingerprint
        or dict(snapshot.provider_result_fingerprints) != expected_results
    ):
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="target_system_snapshot",
                object_id=snapshot.snapshot_id,
                status="stale",
                evidence_ref=snapshot.fingerprint,
                expected_fingerprint=descriptor.fingerprint,
                observed_fingerprint=snapshot.descriptor_fingerprint,
                message="target-system snapshot does not match the current descriptor, registry, and provider results",
            )
        )
    current_capabilities: dict[str, set[str]] = {role: set() for role in PROVIDER_ROLES}
    provider_evidence_ids: list[str] = []
    for provider in providers:
        provider_evidence_ids.append(provider.fingerprint)
        if provider.target_system_id != descriptor.target_system_id:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="provider_result",
                    object_id=provider.provider_id,
                    status="blocked",
                    evidence_ref=provider.fingerprint,
                    message="provider result targets another target system",
                )
            )
            continue
        if provider.subject_revision != descriptor.subject_revision:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="provider_result",
                    object_id=provider.provider_id,
                    status="stale",
                    evidence_ref=provider.fingerprint,
                    expected_fingerprint=descriptor.subject_revision,
                    observed_fingerprint=provider.subject_revision,
                    message="provider result targets another subject revision",
                )
            )
            continue
        if provider.status != "current":
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="provider_result",
                    object_id=provider.provider_id,
                    status=("blocked" if provider.status == "not_applicable" else provider.status),
                    evidence_ref=provider.fingerprint,
                    message=(
                        "provider result is not current: "
                        + provider.status
                        + ("; " + "; ".join(provider.findings) if provider.findings else "")
                    ),
                )
            )
            continue
        input_ids = {key for key, _value in provider.input_fingerprints}
        payload_ids = {key for key, _value in provider.payload_fingerprints}
        binding_by_capability = {
            row.capability_id: row for row in provider.capability_bindings
        }
        for capability in provider.capability_ids:
            binding = binding_by_capability.get(capability)
            if binding is None:
                gaps.append(
                    BlueprintGapRef(
                        layer="evidence_qualification",
                        object_kind="provider_capability_binding",
                        object_id=f"{provider.provider_id}:{capability}",
                        status="missing",
                        evidence_ref=provider.fingerprint,
                        message="provider capability has no exact input-to-payload binding",
                    )
                )
                continue
            missing_inputs = sorted(set(binding.input_ids) - input_ids)
            missing_payloads = sorted(set(binding.payload_ids) - payload_ids)
            if missing_inputs or missing_payloads:
                gaps.append(
                    BlueprintGapRef(
                        layer="evidence_qualification",
                        object_kind="provider_capability_lineage",
                        object_id=f"{provider.provider_id}:{capability}",
                        status="blocked",
                        evidence_ref=provider.fingerprint,
                        message=(
                            "provider capability binding references absent inputs or payloads: "
                            f"inputs={missing_inputs}, payloads={missing_payloads}"
                        ),
                    )
                )
                continue
            current_capabilities[provider.provider_role].add(capability)
    for role, required in (
        ("observation", descriptor.required_observation_capabilities),
        ("authority", descriptor.required_authority_capabilities),
    ):
        for capability in sorted(set(required) - current_capabilities[role]):
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind=f"{role}_provider_capability",
                    object_id=capability,
                    status="missing",
                    message=f"required {role} provider capability is missing",
                )
            )

    supplied_layers = tuple(downstream_layers)
    supplied_ids = tuple(row.layer for row in supplied_layers)
    duplicate_ids = sorted(
        {layer_id for layer_id in supplied_ids if supplied_ids.count(layer_id) > 1}
    )
    for layer_id in duplicate_ids:
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="duplicate_layer",
                object_id=layer_id,
                status="blocked",
                message="downstream evidence supplies the same planned layer more than once",
            )
        )
    planned_downstream = set(plan.layer_ids[1:])
    for layer_id in sorted(set(supplied_ids) - planned_downstream):
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="undeclared_layer",
                object_id=layer_id,
                status="blocked",
                message="downstream evidence names a layer absent from the frozen plan",
            )
        )
    for gap in downstream_gaps:
        if gap.layer in plan.layer_ids:
            gaps.append(gap)
        else:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="undeclared_gap_layer",
                    object_id=gap.layer,
                    status="blocked",
                    evidence_ref=gap.gap_id,
                    message="downstream gap names a layer absent from the frozen plan",
                )
            )

    for row in supplied_layers:
        if row.layer not in planned_downstream:
            continue
        if not row.native_reports:
            gaps.append(
                BlueprintGapRef(
                    layer=row.layer,
                    object_kind="native_report_identity",
                    object_id=row.layer,
                    status="blocked",
                    message=(
                        "planned readiness layer has no exact native owner/report "
                        "identity"
                    ),
                )
            )
        evidence_ids = set(row.evidence_ids)
        for native_report in row.native_reports:
            if native_report.report_fingerprint not in evidence_ids:
                gaps.append(
                    BlueprintGapRef(
                        layer=row.layer,
                        object_kind="native_report_evidence_binding",
                        object_id=(
                            f"{native_report.owner_id}:{native_report.report_id}"
                        ),
                        status="blocked",
                        owner_id=native_report.owner_id,
                        expected_fingerprint=native_report.report_fingerprint,
                        message=(
                            "native report fingerprint is absent from the layer's "
                            "exact evidence identities"
                        ),
                    )
                )
        if row.status == "pass" and row.pre_code_status not in {
            "ready",
            "not_applicable",
        }:
            gaps.append(
                BlueprintGapRef(
                    layer=row.layer,
                    object_kind="native_pre_code_status",
                    object_id=row.layer,
                    status=(
                        row.pre_code_status
                        if row.pre_code_status in {"blocked", "stale"}
                        else "incomplete"
                    ),
                    message="a passing layer carries a non-ready native design status",
                )
            )
        if row.implementation_admitted:
            gaps.append(
                BlueprintGapRef(
                    layer=row.layer,
                    object_kind="implementation_admission_owner",
                    object_id=row.layer,
                    status="blocked",
                    message=(
                        "downstream rows cannot self-assert implementation admission; "
                        "the canonical ordered ledger owns that decision"
                    ),
                )
            )

    provider_gaps = tuple(row for row in gaps if row.layer == "evidence_qualification")
    if provider_gaps:
        if any(row.status == "blocked" for row in provider_gaps):
            provider_status = "blocked"
        elif any(row.status == "stale" for row in provider_gaps):
            provider_status = "stale"
        elif any(row.status in {"missing", "incomplete"} for row in provider_gaps):
            provider_status = "incomplete"
        else:
            provider_status = "not_run"
        qualification = BlueprintLayerResult._derived(
            layer="evidence_qualification",
            status=provider_status,
            evidence_ids=tuple((*provider_evidence_ids, frozen_evidence.fingerprint)),
            gap_ids=tuple(row.gap_id for row in provider_gaps),
            native_reports=(
                BlueprintNativeReportRef(
                    owner_id="target-system-evidence-qualification",
                    report_id=frozen_evidence.evidence_id,
                    report_fingerprint=frozen_evidence.fingerprint,
                ),
            ),
            pre_code_status=(
                provider_status
                if provider_status in {"blocked", "stale", "incomplete"}
                else "incomplete"
            ),
            executed_evidence_status="not_applicable",
        )
    else:
        qualification = BlueprintLayerResult._derived(
            layer="evidence_qualification",
            status="pass",
            evidence_ids=tuple((*provider_evidence_ids, frozen_evidence.fingerprint)),
            native_reports=(
                BlueprintNativeReportRef(
                    owner_id="target-system-evidence-qualification",
                    report_id=frozen_evidence.evidence_id,
                    report_fingerprint=frozen_evidence.fingerprint,
                ),
            ),
            pre_code_status=(
                "not_applicable"
                if plan.target_profile == NON_CODE_WORKFLOW_TARGET_PROFILE
                else "ready"
            ),
            executed_evidence_status="not_applicable",
        )

    supplied: dict[str, BlueprintLayerResult] = {}
    for row in supplied_layers:
        if row.layer in planned_downstream and row.layer not in supplied:
            supplied[row.layer] = row
    layers: list[BlueprintLayerResult] = [qualification]
    lower_pass = qualification.status == "pass"
    known_gap_ids = {row.gap_id for row in gaps}
    for layer_name in plan.layer_ids[1:]:
        row = supplied.get(layer_name)
        if row is None:
            missing_gap = BlueprintGapRef(
                layer=layer_name,
                object_kind="required_layer",
                object_id=layer_name,
                status="missing",
                message="the frozen plan requires this layer but no result was supplied",
            )
            gaps.append(missing_gap)
            known_gap_ids.add(missing_gap.gap_id)
            row = BlueprintLayerResult._derived(
                layer=layer_name,
                status="incomplete",
                gap_ids=(missing_gap.gap_id,),
                pre_code_status="incomplete",
                executed_evidence_status="not_applicable",
            )
        layer_integrity_gap_ids = tuple(
            gap.gap_id for gap in gaps if gap.layer == layer_name
        )
        if layer_integrity_gap_ids:
            layer_integrity_gaps = tuple(
                gap for gap in gaps if gap.gap_id in set(layer_integrity_gap_ids)
            )
            if any(gap.status == "blocked" for gap in layer_integrity_gaps):
                integrity_status = "blocked"
            elif any(gap.status == "stale" for gap in layer_integrity_gaps):
                integrity_status = "stale"
            else:
                integrity_status = "incomplete"
            row = replace(
                row,
                status=(
                    integrity_status if row.status == "pass" else row.status
                ),
                gap_ids=tuple((*row.gap_ids, *layer_integrity_gap_ids)),
                implementation_admitted=False,
            )
        if row.status != "pass" and not set(row.gap_ids).issubset(known_gap_ids):
            missing_refs = sorted(set(row.gap_ids) - known_gap_ids)
            missing_record_gap = BlueprintGapRef(
                layer=layer_name,
                object_kind="missing_gap_record",
                object_id=",".join(missing_refs),
                status="blocked",
                message="layer result references gap identities that were not supplied",
            )
            gaps.append(missing_record_gap)
            known_gap_ids.add(missing_record_gap.gap_id)
            row = BlueprintLayerResult._derived(
                layer=layer_name,
                status="blocked",
                evidence_ids=row.evidence_ids,
                gap_ids=(missing_record_gap.gap_id,),
                native_reports=row.native_reports,
                pre_code_status=row.pre_code_status,
                executed_evidence_status=row.executed_evidence_status,
            )
        if not lower_pass and row.status == "pass":
            causal_gap = BlueprintGapRef(
                layer=layer_name,
                object_kind="lower_layer_dependency",
                object_id=layers[-1].layer,
                status="blocked",
                evidence_ref=layers[-1].layer,
                message="a later blueprint layer cannot pass while a required lower layer is unresolved",
            )
            gaps.append(causal_gap)
            row = BlueprintLayerResult._derived(
                layer=layer_name,
                status="blocked",
                evidence_ids=row.evidence_ids,
                gap_ids=(causal_gap.gap_id,),
                native_reports=row.native_reports,
                pre_code_status=row.pre_code_status,
                executed_evidence_status=row.executed_evidence_status,
            )
        layers.append(row)
        lower_pass = lower_pass and row.status == "pass"

    if (
        plan.target_profile == SOFTWARE_TARGET_PROFILE
        and all(row.status == "pass" for row in layers)
    ):
        layers[-1] = replace(layers[-1], implementation_admitted=True)

    referenced_gap_ids = {gap_id for row in layers for gap_id in row.gap_ids}
    gaps = [row for row in gaps if row.gap_id in referenced_gap_ids]
    return TargetSystemBlueprintReport._derived(
        descriptor=descriptor,
        layer_plan=plan,
        provider_results=providers,
        layers=tuple(layers),
        gaps=tuple(gaps),
        required_path_quality_model_ids=required_path_ids,
        path_quality_bindings=supplied_path_bindings,
        provider_registry_fingerprint=provider_registry.fingerprint,
        snapshot_fingerprint=snapshot.fingerprint,
        scope=scope,
    )


def project_blueprint_understanding(
    report: TargetSystemBlueprintReport,
    *,
    affected_surface_ids: Sequence[str] = (),
) -> BlueprintUnderstandingSummary:
    """Return a compact deterministic projection without executing work."""

    return BlueprintUnderstandingSummary(
        scope=report.scope,
        target_system_id=report.descriptor.target_system_id,
        target_profile=report.target_profile,
        subject_revision=report.descriptor.subject_revision,
        descriptor_fingerprint=report.descriptor.fingerprint,
        blueprint_fingerprint=report.fingerprint,
        layer_plan_id=report.layer_plan.plan_id,
        layer_plan_fingerprint=report.layer_plan_fingerprint,
        layer_statuses=tuple((row.layer, row.status) for row in report.layers),
        status=report.status,
        deepest_proven_layer=report.deepest_proven_layer,
        first_gap=report.gaps[0] if report.gaps else None,
        gap_count=len(report.gaps),
        implementation_admitted=report.implementation_admitted,
        affected_surface_ids=_strings(affected_surface_ids, "affected surface"),
        provider_fingerprints=tuple(
            (row.provider_id, row.fingerprint) for row in report.provider_results
        ),
        required_path_quality_model_ids=(
            report.required_path_quality_model_ids
        ),
        path_quality_bindings=report.path_quality_bindings,
    )


__all__ = [
    "BLUEPRINT_UNDERSTANDING_SCHEMA",
    "CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN",
    "CANONICAL_SOFTWARE_LAYER_PLAN",
    "FROZEN_TARGET_SYSTEM_EVIDENCE_SCHEMA",
    "MODEL_PATH_QUALITY_BLUEPRINT_BINDING_SCHEMA",
    "MODEL_PATH_QUALITY_CHANGE_KINDS",
    "MODEL_PATH_QUALITY_SUBJECT_LANES",
    "DNA_QUALIFICATION_STATUSES",
    "NON_CODE_WORKFLOW_LAYER_ORDER",
    "NON_CODE_WORKFLOW_TARGET_PROFILE",
    "SOFTWARE_BLUEPRINT_LAYER_ORDER",
    "SOFTWARE_TARGET_PROFILE",
    "TARGET_SYSTEM_DNA_QUALIFICATION_SCHEMA",
    "TARGET_SYSTEM_LAYER_PLAN_SCHEMA",
    "TARGET_SYSTEM_PROVIDER_PROFILE_REGISTRY_SCHEMA",
    "TARGET_SYSTEM_PROVIDER_PROFILE_SCHEMA",
    "BlueprintGapRef",
    "BlueprintNativeReportRef",
    "BlueprintReadinessLedger",
    "BlueprintUnderstandingSummary",
    "ModelPathQualityBlueprintBinding",
    "PROVIDER_ROLES",
    "ProviderCapabilityBinding",
    "TARGET_SYSTEM_BLUEPRINT_SCHEMA",
    "TARGET_SYSTEM_PROVIDER_SCHEMA",
    "TARGET_SYSTEM_PROVIDER_REGISTRY_SCHEMA",
    "TARGET_SYSTEM_SNAPSHOT_SCHEMA",
    "TargetSystemBlueprintError",
    "TargetSystemDescriptor",
    "TargetSystemLayerPlan",
    "FrozenTargetSystemEvidence",
    "TargetSystemProviderResult",
    "TargetSystemProviderDeclaration",
    "TargetSystemProviderRegistry",
    "TargetSystemProviderProfileDeclaration",
    "TargetSystemProviderProfileRegistry",
    "TargetSystemSnapshot",
    "build_target_system_provider_registry",
    "capture_target_system_snapshot",
    "load_frozen_target_system_evidence",
    "load_target_system_descriptor",
    "load_target_system_layer_plan",
    "load_target_system_provider_registry",
    "load_target_system_provider_profile_registry",
    "load_target_system_provider_result",
    "load_target_system_snapshot",
    "model_path_quality_binding_set_fingerprint",
    "project_blueprint_understanding",
    "serialize_frozen_target_system_evidence",
    "serialize_target_system_descriptor",
    "serialize_target_system_layer_plan",
    "serialize_target_system_provider_registry",
    "serialize_target_system_provider_profile_registry",
    "serialize_target_system_provider_result",
    "serialize_target_system_snapshot",
    "validate_blueprint_native_reports",
    "validate_target_system_provider_profiles",
    "TargetSystemDnaQualification",
    "qualify_target_system_dna",
]
