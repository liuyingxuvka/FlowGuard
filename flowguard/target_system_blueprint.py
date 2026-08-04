"""Provider-neutral target-system blueprint composition.

This module is intentionally thin. Providers contribute content-addressed
observations or independently governed authority; only the compiler joins
those results into layered blueprint readiness. It does not discover files or
execute a provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .evidence_receipts import fingerprint_value


TARGET_SYSTEM_BLUEPRINT_SCHEMA = "flowguard.target_system_blueprint.v1"
TARGET_SYSTEM_PROVIDER_SCHEMA = "flowguard.target_system_provider_result.v1"
TARGET_SYSTEM_PROVIDER_REGISTRY_SCHEMA = "flowguard.target_system_provider_registry.v1"
TARGET_SYSTEM_SNAPSHOT_SCHEMA = "flowguard.target_system_snapshot.v1"
BLUEPRINT_UNDERSTANDING_SCHEMA = "flowguard.blueprint_understanding_summary.v1"

PROVIDER_ROLES = ("observation", "authority")
PROVIDER_STATUSES = ("current", "incomplete", "stale", "blocked", "not_applicable")
LAYER_STATUSES = ("pass", "incomplete", "stale", "blocked", "not_run")
BLUEPRINT_LAYER_ORDER = (
    "evidence_qualification",
    "implementation_inventory",
    "traceability",
    "independent_semantics",
    "model_code_test",
    "resource_oracle",
    "static_blueprint",
)


class TargetSystemBlueprintError(ValueError):
    """Raised when a target-system blueprint input is not exact-current."""


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


@dataclass(frozen=True)
class TargetSystemDescriptor:
    """One bounded target, independent of language or artifact layout."""

    target_system_id: str
    target_kind: str
    subject_revision: str
    boundary_fingerprint: str
    required_observation_capabilities: tuple[str, ...]
    required_authority_capabilities: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_system_id", _text(self.target_system_id, "target_system_id"))
        object.__setattr__(self, "target_kind", _text(self.target_kind, "target_kind"))
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
        if self.layer not in BLUEPRINT_LAYER_ORDER:
            raise TargetSystemBlueprintError(f"unknown blueprint layer: {self.layer}")
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
class BlueprintLayerResult:
    layer: str
    status: str
    evidence_ids: tuple[str, ...] = ()
    gap_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.layer not in BLUEPRINT_LAYER_ORDER:
            raise TargetSystemBlueprintError(f"unknown blueprint layer: {self.layer}")
        if self.status not in LAYER_STATUSES:
            raise TargetSystemBlueprintError(f"unknown layer status: {self.status}")
        object.__setattr__(self, "evidence_ids", _strings(self.evidence_ids, "layer evidence"))
        object.__setattr__(self, "gap_ids", _strings(self.gap_ids, "layer gap"))
        if self.status == "pass" and self.gap_ids:
            raise TargetSystemBlueprintError("passing blueprint layer cannot contain gaps")
        if self.status != "pass" and not self.gap_ids:
            raise TargetSystemBlueprintError("non-passing blueprint layer requires a gap")

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "gap_ids": list(self.gap_ids),
        }


@dataclass(frozen=True)
class TargetSystemBlueprintReport:
    descriptor: TargetSystemDescriptor
    provider_results: tuple[TargetSystemProviderResult, ...]
    layers: tuple[BlueprintLayerResult, ...]
    gaps: tuple[BlueprintGapRef, ...]
    provider_registry_fingerprint: str = ""
    snapshot_fingerprint: str = ""
    scope: str = "whole"

    def __post_init__(self) -> None:
        if self.scope not in {"affected", "whole"}:
            raise TargetSystemBlueprintError("blueprint report scope must be affected or whole")
        object.__setattr__(
            self,
            "provider_results",
            tuple(sorted(self.provider_results, key=lambda row: row.provider_id)),
        )
        object.__setattr__(
            self,
            "layers",
            tuple(sorted(self.layers, key=lambda row: BLUEPRINT_LAYER_ORDER.index(row.layer))),
        )
        object.__setattr__(
            self,
            "gaps",
            tuple(sorted(self.gaps, key=lambda row: (BLUEPRINT_LAYER_ORDER.index(row.layer), row.object_kind, row.object_id))),
        )
        if tuple(row.layer for row in self.layers) != BLUEPRINT_LAYER_ORDER:
            raise TargetSystemBlueprintError("blueprint report must contain every ordered layer exactly once")
        gap_ids = {row.gap_id for row in self.gaps}
        referenced = {gap_id for row in self.layers for gap_id in row.gap_ids}
        if gap_ids != referenced:
            raise TargetSystemBlueprintError("blueprint layer gap references are not complete")

    @property
    def status(self) -> str:
        return self.layers[-1].status

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    @property
    def deepest_proven_layer(self) -> str:
        deepest = ""
        for row in self.layers:
            if row.status != "pass":
                break
            deepest = row.layer
        return deepest

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_SYSTEM_BLUEPRINT_SCHEMA,
            "descriptor": self.descriptor.to_dict(),
            "provider_results": [row.to_dict() for row in self.provider_results],
            "provider_registry_fingerprint": self.provider_registry_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "layers": [row.to_dict() for row in self.layers],
            "gaps": [{"gap_id": row.gap_id, **row.to_dict()} for row in self.gaps],
            "status": self.status,
            "ok": self.ok,
            "scope": self.scope,
            "deepest_proven_layer": self.deepest_proven_layer,
            "claim_boundary": (
                "Static target-system blueprint readiness only; provider completion does "
                "not prove factual correctness."
            ),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class BlueprintUnderstandingSummary:
    scope: str
    target_system_id: str
    subject_revision: str
    descriptor_fingerprint: str
    blueprint_fingerprint: str
    layer_statuses: tuple[tuple[str, str], ...]
    deepest_proven_layer: str
    first_gap: BlueprintGapRef | None
    gap_count: int
    affected_surface_ids: tuple[str, ...] = ()
    provider_fingerprints: tuple[tuple[str, str], ...] = ()

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": BLUEPRINT_UNDERSTANDING_SCHEMA,
            "scope": self.scope,
            "target_system_id": self.target_system_id,
            "subject_revision": self.subject_revision,
            "descriptor_fingerprint": self.descriptor_fingerprint,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "layer_statuses": dict(self.layer_statuses),
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_gap": (
                {"gap_id": self.first_gap.gap_id, **self.first_gap.to_dict()}
                if self.first_gap
                else None
            ),
            "gap_count": self.gap_count,
            "affected_surface_ids": list(self.affected_surface_ids),
            "provider_fingerprints": dict(self.provider_fingerprints),
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


def compile_target_system_blueprint(
    descriptor: TargetSystemDescriptor,
    provider_results: Sequence[TargetSystemProviderResult],
    *,
    downstream_layers: Sequence[BlueprintLayerResult],
    downstream_gaps: Sequence[BlueprintGapRef] = (),
    provider_registry: TargetSystemProviderRegistry | None = None,
    snapshot: TargetSystemSnapshot | None = None,
    scope: str = "whole",
) -> TargetSystemBlueprintReport:
    """Compile current provider evidence and already-reviewed generic layers.

    Downstream layers come from the native behavior/resource/test reviewers;
    this function validates their order and prevents provider or revision gaps
    from being hidden by a later passing result.
    """

    providers = tuple(provider_results)
    provider_ids = tuple(row.provider_id for row in providers)
    if len(provider_ids) != len(set(provider_ids)):
        raise TargetSystemBlueprintError("provider identities must be unique")
    gaps = list(downstream_gaps)
    if scope == "whole" and provider_registry is None:
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="provider_registry",
                object_id=descriptor.target_system_id,
                status="missing",
                message="whole-target qualification requires a frozen provider registry",
            )
        )
    if scope == "whole" and snapshot is None:
        gaps.append(
            BlueprintGapRef(
                layer="evidence_qualification",
                object_kind="target_system_snapshot",
                object_id=descriptor.target_system_id,
                status="missing",
                message="whole-target qualification requires a frozen provider-result snapshot",
            )
        )
    if provider_registry is not None:
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
                    message="registered provider has no result in the frozen snapshot",
                )
            )
    if snapshot is not None:
        expected_results = {row.provider_id: row.fingerprint for row in providers}
        if (
            snapshot.target_system_id != descriptor.target_system_id
            or snapshot.subject_revision != descriptor.subject_revision
            or snapshot.descriptor_fingerprint != descriptor.fingerprint
            or (
                provider_registry is not None
                and snapshot.registry_fingerprint != provider_registry.fingerprint
            )
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

    provider_gaps = tuple(row for row in gaps if row.layer == "evidence_qualification")
    if provider_gaps:
        status_order = {"missing": "incomplete", "incomplete": "incomplete", "stale": "stale", "blocked": "blocked", "not_run": "not_run"}
        provider_status = "incomplete"
        if any(row.status == "blocked" for row in provider_gaps):
            provider_status = "blocked"
        elif any(row.status == "stale" for row in provider_gaps):
            provider_status = "stale"
        else:
            provider_status = status_order[provider_gaps[0].status]
        qualification = BlueprintLayerResult(
            layer="evidence_qualification",
            status=provider_status,
            evidence_ids=tuple(provider_evidence_ids),
            gap_ids=tuple(row.gap_id for row in provider_gaps),
        )
    else:
        qualification = BlueprintLayerResult(
            layer="evidence_qualification",
            status="pass",
            evidence_ids=tuple(provider_evidence_ids),
        )

    supplied = {row.layer: row for row in downstream_layers}
    if "evidence_qualification" in supplied:
        raise TargetSystemBlueprintError(
            "evidence qualification is owned by the target-system compiler"
        )
    expected_downstream = set(BLUEPRINT_LAYER_ORDER[1:])
    if set(supplied) != expected_downstream:
        raise TargetSystemBlueprintError(
            "downstream layers must contain every non-provider layer exactly once"
        )
    layers: list[BlueprintLayerResult] = [qualification]
    lower_pass = qualification.status == "pass"
    for layer_name in BLUEPRINT_LAYER_ORDER[1:]:
        row = supplied[layer_name]
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
            row = BlueprintLayerResult(
                layer=layer_name,
                status="blocked",
                evidence_ids=row.evidence_ids,
                gap_ids=(causal_gap.gap_id,),
            )
        layers.append(row)
        lower_pass = lower_pass and row.status == "pass"

    referenced_gap_ids = {gap_id for row in layers for gap_id in row.gap_ids}
    gaps = [row for row in gaps if row.gap_id in referenced_gap_ids]
    return TargetSystemBlueprintReport(
        descriptor=descriptor,
        provider_results=providers,
        layers=tuple(layers),
        gaps=tuple(gaps),
        provider_registry_fingerprint=(
            provider_registry.fingerprint if provider_registry is not None else ""
        ),
        snapshot_fingerprint=(snapshot.fingerprint if snapshot is not None else ""),
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
        subject_revision=report.descriptor.subject_revision,
        descriptor_fingerprint=report.descriptor.fingerprint,
        blueprint_fingerprint=report.fingerprint,
        layer_statuses=tuple((row.layer, row.status) for row in report.layers),
        deepest_proven_layer=report.deepest_proven_layer,
        first_gap=report.gaps[0] if report.gaps else None,
        gap_count=len(report.gaps),
        affected_surface_ids=_strings(affected_surface_ids, "affected surface"),
        provider_fingerprints=tuple(
            (row.provider_id, row.fingerprint) for row in report.provider_results
        ),
    )


__all__ = [
    "BLUEPRINT_LAYER_ORDER",
    "BLUEPRINT_UNDERSTANDING_SCHEMA",
    "BlueprintGapRef",
    "BlueprintLayerResult",
    "BlueprintUnderstandingSummary",
    "PROVIDER_ROLES",
    "ProviderCapabilityBinding",
    "TARGET_SYSTEM_BLUEPRINT_SCHEMA",
    "TARGET_SYSTEM_PROVIDER_SCHEMA",
    "TARGET_SYSTEM_PROVIDER_REGISTRY_SCHEMA",
    "TARGET_SYSTEM_SNAPSHOT_SCHEMA",
    "TargetSystemBlueprintError",
    "TargetSystemBlueprintReport",
    "TargetSystemDescriptor",
    "TargetSystemProviderResult",
    "TargetSystemProviderDeclaration",
    "TargetSystemProviderRegistry",
    "TargetSystemSnapshot",
    "build_target_system_provider_registry",
    "capture_target_system_snapshot",
    "compile_target_system_blueprint",
    "project_blueprint_understanding",
]
