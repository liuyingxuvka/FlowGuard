"""Project-neutral composition of an inspectable target-system blueprint.

The builder joins independently declared model semantics, discovered code or
workflow surfaces, exact test/checker design, intent, and owned resources.  It
is read-only with respect to the target project.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .implementation_blueprint import (
    BlueprintResourceReference,
    ModelImplementationBinding,
    ModelImplementationBindingReport,
    OracleReference,
    SemanticSpecReference,
    SoftwareBlueprintManifest,
    SoftwareBlueprintQualificationReport,
    qualify_software_blueprint,
    review_model_implementation_bindings,
)
from .implementation_inventory import (
    DiscoveryAdapter,
    ImplementationFileDisposition,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    build_implementation_surface_inventory,
)
from .test_inventory import (
    ProjectTestInventory,
    TestDiscoveryAdapter,
    review_project_test_inventory,
)
from .source_identity import source_file_fingerprint
from .evidence_receipts import fingerprint_value
from .model_test_alignment import (
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    ModelTestAlignmentReport,
    TestEvidence,
    review_model_test_alignment,
)
from .blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyRelation,
    BlueprintTopologyReport,
    review_blueprint_topology,
)
from .software_blueprint_readiness import (
    BEHAVIOR_DIMENSIONS,
    AffectedBlueprintNeighborhood,
    BehaviorCaseContract,
    BehaviorBlockContract,
    BehaviorBlueprintReport,
    BehaviorCoverageEdge,
    BehaviorDimensionContract,
    CoverageExecutionEvidence,
    DelegatedAssertionHelper,
    NormalizedBlueprintProjection,
    ProjectIntentInventory,
    ProjectResourceInventory,
    ProjectResourceMember,
    ProjectTestNodeDisposition,
    PortableBehaviorBinding,
    ReadinessFinding,
    StaticBlueprintReadinessReport,
    SupportingSurfaceRelation,
    normalize_behavior_blueprint,
    load_affected_behavior_neighborhood,
    review_behavior_blueprint,
    review_static_blueprint_readiness,
)
from .target_system_blueprint import (
    BlueprintGapRef,
    BlueprintLayerResult,
    BlueprintUnderstandingSummary,
    ProviderCapabilityBinding,
    TargetSystemBlueprintReport,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    compile_target_system_blueprint,
    project_blueprint_understanding,
)


PROJECT_BLUEPRINT_DEFINITION_SCHEMA = "flowguard.project_blueprint_definition.v4"


class ProjectBlueprintError(ValueError):
    """Raised when a project blueprint declaration is not exact-current."""


def _pairs(value: Mapping[str, str] | Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    rows = value.items() if isinstance(value, Mapping) else value
    return tuple(sorted((str(key), str(item)) for key, item in rows))


def _provider_declarations(
    value: Mapping[str, Sequence[str]] | Sequence[tuple[str, Sequence[str]]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    rows = value.items() if isinstance(value, Mapping) else value
    normalized = tuple(
        sorted(
            (
                str(provider_id).strip(),
                tuple(sorted({str(item).strip() for item in capabilities if str(item).strip()})),
            )
            for provider_id, capabilities in rows
        )
    )
    if any(not provider_id or not capabilities for provider_id, capabilities in normalized):
        raise ProjectBlueprintError(
            "project blueprint providers require identity and capabilities"
        )
    if len(normalized) != len({provider_id for provider_id, _capabilities in normalized}):
        raise ProjectBlueprintError("project blueprint provider identity is duplicated")
    return normalized


def project_surface_dimensions(surface: ImplementationSurface) -> tuple[str, ...]:
    # Deep project blueprints make lifecycle dimensions explicit even when the
    # owning model declares them not applicable; silence is not closure.
    dimensions = {"input", "output", "error", "order", "retry", "timeout", "completion"}
    if surface.state_writes or surface.side_effect_candidates or surface.dynamic_operations:
        dimensions.add("state_effect")
    if surface.calls or surface.dynamic_operations:
        dimensions.add("decision")
    return tuple(sorted(dimensions))


def _project_behavior_surface_ids(
    inventory: ImplementationSurfaceInventory,
    definition: "ProjectBlueprintDefinition",
) -> set[str]:
    """Return only independently declared behavior owners.

    Source discovery may reveal thousands of functions and helpers, but it
    cannot promote every observed symbol into an independently intended model
    block.  The declared primary is the behavior owner; the remaining exact
    surfaces stay visible through supporting ownership relations.
    """

    required = set(inventory.required_surface_ids)
    return {
        owner.primary_surface_id
        for owner in definition.owners
        if owner.primary_surface_id in required
    }


@dataclass(frozen=True)
class ProjectBlueprintOwner:
    """One stable model obligation and its exact code/test realization."""

    model_element_id: str
    owner_id: str
    owner_contract_id: str
    model_fingerprint: str
    owner_contract_fingerprint: str
    portable_model_id: str
    portable_model_fingerprint: str
    portable_transition_ids: tuple[str, ...]
    portable_property_ids: tuple[str, ...]
    portable_invariant_ids: tuple[str, ...]
    portable_input_field_mappings: tuple[tuple[str, str], ...]
    portable_output_field_mappings: tuple[tuple[str, str], ...]
    portable_state_field_mappings: tuple[tuple[str, str], ...]
    portable_assumption_ids: tuple[str, ...]
    portable_guarantee_ids: tuple[str, ...]
    protected_failure_ids: tuple[str, ...]
    implementation_surface_ids: tuple[str, ...]
    primary_surface_id: str
    semantic_specs: tuple[SemanticSpecReference, ...]
    oracles: tuple[OracleReference, ...]
    test_evidence_fingerprints: tuple[tuple[str, str], ...]
    native_evidence_fingerprints: tuple[tuple[str, str], ...]
    behavior_accepted: bool
    behavior_acceptance_evidence_fingerprints: tuple[tuple[str, str], ...]
    behavior_case_contracts: tuple[BehaviorCaseContract, ...] = ()
    checker_design_fingerprints: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "model_element_id",
            "owner_id",
            "owner_contract_id",
            "model_fingerprint",
            "owner_contract_fingerprint",
            "portable_model_id",
            "portable_model_fingerprint",
            "primary_surface_id",
        ):
            if not getattr(self, field_name):
                raise ProjectBlueprintError(f"project owner {field_name} is required")
        object.__setattr__(
            self,
            "implementation_surface_ids",
            tuple(sorted(set(self.implementation_surface_ids))),
        )
        object.__setattr__(self, "semantic_specs", tuple(self.semantic_specs))
        object.__setattr__(self, "oracles", tuple(self.oracles))
        object.__setattr__(
            self,
            "behavior_case_contracts",
            tuple(sorted(self.behavior_case_contracts, key=lambda row: row.case_id)),
        )
        object.__setattr__(
            self,
            "test_evidence_fingerprints",
            _pairs(self.test_evidence_fingerprints),
        )
        object.__setattr__(
            self,
            "native_evidence_fingerprints",
            _pairs(self.native_evidence_fingerprints),
        )
        object.__setattr__(
            self,
            "protected_failure_ids",
            tuple(sorted(set(self.protected_failure_ids))),
        )
        for field_name in (
            "portable_transition_ids",
            "portable_property_ids",
            "portable_invariant_ids",
            "portable_assumption_ids",
            "portable_guarantee_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(set(getattr(self, field_name)))),
            )
        for field_name in (
            "portable_input_field_mappings",
            "portable_output_field_mappings",
            "portable_state_field_mappings",
            "behavior_acceptance_evidence_fingerprints",
            "checker_design_fingerprints",
        ):
            object.__setattr__(self, field_name, _pairs(getattr(self, field_name)))
        if not (
            self.portable_transition_ids
            and self.portable_property_ids
            and self.portable_invariant_ids
            and self.portable_assumption_ids
            and self.portable_guarantee_ids
        ):
            raise ProjectBlueprintError(
                "project owner requires an exact portable model member catalog"
            )
        if self.behavior_accepted and not self.behavior_acceptance_evidence_fingerprints:
            raise ProjectBlueprintError(
                "accepted project behavior requires explicit acceptance evidence"
            )
        checker_by_id = dict(self.checker_design_fingerprints)
        for case in self.behavior_case_contracts:
            if checker_by_id.get(case.case_evidence_id) != case.case_evidence_fingerprint:
                raise ProjectBlueprintError(
                    "project behavior case requires an exact declared checker design"
                )
        if self.primary_surface_id not in self.implementation_surface_ids:
            raise ProjectBlueprintError("primary surface must belong to its project owner")
        if not self.semantic_specs:
            raise ProjectBlueprintError("project owner requires declared/imported semantics")
        if not self.oracles:
            raise ProjectBlueprintError("project owner requires at least one oracle")
        if not self.test_evidence_fingerprints and not self.native_evidence_fingerprints:
            raise ProjectBlueprintError(
                "project owner requires a real test node or native evidence member"
            )

    @property
    def test_evidence_ids(self) -> tuple[str, ...]:
        return tuple(key for key, _value in self.test_evidence_fingerprints)

    @property
    def native_evidence_ids(self) -> tuple[str, ...]:
        return tuple(key for key, _value in self.native_evidence_fingerprints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_element_id": self.model_element_id,
            "owner_id": self.owner_id,
            "owner_contract_id": self.owner_contract_id,
            "model_fingerprint": self.model_fingerprint,
            "owner_contract_fingerprint": self.owner_contract_fingerprint,
            "portable_model_id": self.portable_model_id,
            "portable_model_fingerprint": self.portable_model_fingerprint,
            "portable_transition_ids": list(self.portable_transition_ids),
            "portable_property_ids": list(self.portable_property_ids),
            "portable_invariant_ids": list(self.portable_invariant_ids),
            "portable_input_field_mappings": dict(self.portable_input_field_mappings),
            "portable_output_field_mappings": dict(self.portable_output_field_mappings),
            "portable_state_field_mappings": dict(self.portable_state_field_mappings),
            "portable_assumption_ids": list(self.portable_assumption_ids),
            "portable_guarantee_ids": list(self.portable_guarantee_ids),
            "protected_failure_ids": list(self.protected_failure_ids),
            "implementation_surface_ids": list(self.implementation_surface_ids),
            "primary_surface_id": self.primary_surface_id,
            "semantic_specs": [row.to_dict() for row in self.semantic_specs],
            "oracles": [row.to_dict() for row in self.oracles],
            "test_evidence_fingerprints": dict(self.test_evidence_fingerprints),
            "native_evidence_fingerprints": dict(self.native_evidence_fingerprints),
            "behavior_accepted": self.behavior_accepted,
            "behavior_acceptance_evidence_fingerprints": dict(
                self.behavior_acceptance_evidence_fingerprints
            ),
            "behavior_case_contracts": [
                row.to_dict() for row in self.behavior_case_contracts
            ],
            "checker_design_fingerprints": dict(
                self.checker_design_fingerprints
            ),
        }


@dataclass(frozen=True)
class ProjectEvidenceArtifact:
    """One non-pytest evidence producer verified from the current project."""

    evidence_id: str
    artifact_path: str
    artifact_fingerprint: str
    kind: str

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_id",
            "artifact_path",
            "artifact_fingerprint",
            "kind",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ProjectBlueprintError(
                    f"project evidence artifact {field_name} is required"
                )
        normalized = self.artifact_path.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise ProjectBlueprintError("project evidence artifact path must be bounded")
        object.__setattr__(self, "artifact_path", normalized)

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "artifact_path": self.artifact_path,
            "artifact_fingerprint": self.artifact_fingerprint,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class PortableModelMemberCatalog:
    """Independent current member inventory for one portable model authority."""

    portable_model_id: str
    portable_model_fingerprint: str
    transition_ids: tuple[str, ...]
    property_ids: tuple[str, ...]
    invariant_ids: tuple[str, ...]
    input_field_ids: tuple[str, ...]
    output_field_ids: tuple[str, ...]
    state_field_ids: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    guarantee_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.portable_model_id or not self.portable_model_fingerprint:
            raise ProjectBlueprintError("portable member catalog identity is incomplete")
        for field_name in (
            "transition_ids", "property_ids", "invariant_ids", "input_field_ids",
            "output_field_ids", "state_field_ids", "assumption_ids", "guarantee_ids",
        ):
            object.__setattr__(
                self, field_name, tuple(sorted(set(getattr(self, field_name))))
            )
        if not (
            self.transition_ids
            and self.property_ids
            and self.invariant_ids
            and self.assumption_ids
            and self.guarantee_ids
        ):
            raise ProjectBlueprintError(
                "portable member catalog lacks required behavioral members"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "portable_model_id": self.portable_model_id,
            "portable_model_fingerprint": self.portable_model_fingerprint,
            "transition_ids": list(self.transition_ids),
            "property_ids": list(self.property_ids),
            "invariant_ids": list(self.invariant_ids),
            "input_field_ids": list(self.input_field_ids),
            "output_field_ids": list(self.output_field_ids),
            "state_field_ids": list(self.state_field_ids),
            "assumption_ids": list(self.assumption_ids),
            "guarantee_ids": list(self.guarantee_ids),
        }


@dataclass(frozen=True)
class ProjectBlueprintDefinition:
    blueprint_id: str
    inventory_id: str
    boundary: SoftwareBoundary
    file_dispositions: tuple[ImplementationFileDisposition, ...]
    surface_dispositions: tuple[tuple[str, str], ...]
    supporting_owners: tuple[tuple[str, str], ...]
    dynamic_allowances: tuple[tuple[str, tuple[str, ...]], ...]
    owners: tuple[ProjectBlueprintOwner, ...]
    claim_boundary: str
    target_kind: str
    observation_providers: tuple[tuple[str, tuple[str, ...]], ...]
    authority_providers: tuple[tuple[str, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if not (
            self.blueprint_id
            and self.inventory_id
            and self.claim_boundary
            and self.target_kind
        ):
            raise ProjectBlueprintError("project blueprint identity is incomplete")
        object.__setattr__(self, "file_dispositions", tuple(self.file_dispositions))
        object.__setattr__(self, "surface_dispositions", _pairs(self.surface_dispositions))
        object.__setattr__(self, "supporting_owners", _pairs(self.supporting_owners))
        object.__setattr__(
            self,
            "dynamic_allowances",
            tuple(
                sorted(
                    (str(key), tuple(sorted(set(values))))
                    for key, values in self.dynamic_allowances
                )
            ),
        )
        object.__setattr__(self, "owners", tuple(sorted(self.owners, key=lambda row: row.model_element_id)))
        object.__setattr__(
            self,
            "observation_providers",
            _provider_declarations(self.observation_providers),
        )
        object.__setattr__(
            self,
            "authority_providers",
            _provider_declarations(self.authority_providers),
        )
        if not self.observation_providers or not self.authority_providers:
            raise ProjectBlueprintError(
                "project blueprint requires observation and authority providers"
            )
        provider_ids = {
            provider_id
            for provider_id, _capabilities in (
                self.observation_providers + self.authority_providers
            )
        }
        if len(provider_ids) != len(
            self.observation_providers + self.authority_providers
        ):
            raise ProjectBlueprintError(
                "provider identity cannot own observation and authority roles simultaneously"
            )
        model_ids = [row.model_element_id for row in self.owners]
        if len(model_ids) != len(set(model_ids)):
            raise ProjectBlueprintError("project blueprint contains duplicate model owners")
        claimed_surfaces = [
            surface_id for row in self.owners for surface_id in row.implementation_surface_ids
        ]
        if len(claimed_surfaces) != len(set(claimed_surfaces)):
            raise ProjectBlueprintError("implementation surface is claimed by multiple owners")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROJECT_BLUEPRINT_DEFINITION_SCHEMA,
            "target_kind": self.target_kind,
            "observation_providers": {
                provider_id: list(capabilities)
                for provider_id, capabilities in self.observation_providers
            },
            "authority_providers": {
                provider_id: list(capabilities)
                for provider_id, capabilities in self.authority_providers
            },
            "blueprint_id": self.blueprint_id,
            "inventory_id": self.inventory_id,
            "boundary": self.boundary.to_dict(),
            "file_dispositions": [row.to_dict() for row in self.file_dispositions],
            "surface_dispositions": dict(self.surface_dispositions),
            "supporting_owners": dict(self.supporting_owners),
            "dynamic_allowances": {
                key: list(values) for key, values in self.dynamic_allowances
            },
            "owners": [row.to_dict() for row in self.owners],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class ProjectBlueprintEvidence:
    observed_snapshot_id: str
    observed_snapshot_fingerprint: str
    semantic_mesh_id: str
    semantic_mesh_fingerprint: str
    portable_owner_fingerprints: tuple[tuple[str, str], ...]
    portable_member_catalogs: tuple[PortableModelMemberCatalog, ...]
    resources: tuple[BlueprintResourceReference, ...]
    test_inventory: ProjectTestInventory
    topology_nodes: tuple[BlueprintTopologyNode, ...]
    topology_relations: tuple[BlueprintTopologyRelation, ...]
    native_evidence_artifacts: tuple[ProjectEvidenceArtifact, ...] = ()

    def __post_init__(self) -> None:
        identities = (
            self.observed_snapshot_id,
            self.observed_snapshot_fingerprint,
            self.semantic_mesh_id,
            self.semantic_mesh_fingerprint,
        )
        if not all(identities):
            raise ProjectBlueprintError("project blueprint evidence identity is incomplete")
        object.__setattr__(
            self,
            "portable_owner_fingerprints",
            _pairs(self.portable_owner_fingerprints),
        )
        object.__setattr__(
            self,
            "portable_member_catalogs",
            tuple(sorted(self.portable_member_catalogs, key=lambda row: row.portable_model_id)),
        )
        catalog_ids = tuple(row.portable_model_id for row in self.portable_member_catalogs)
        if len(catalog_ids) != len(set(catalog_ids)):
            raise ProjectBlueprintError("portable member catalog identity is duplicated")
        object.__setattr__(self, "resources", tuple(sorted(self.resources, key=lambda row: row.resource_id)))
        object.__setattr__(
            self,
            "topology_nodes",
            tuple(sorted(self.topology_nodes, key=lambda row: row.node_id)),
        )
        object.__setattr__(
            self,
            "topology_relations",
            tuple(sorted(self.topology_relations, key=lambda row: row.relation_id)),
        )
        object.__setattr__(
            self,
            "native_evidence_artifacts",
            tuple(sorted(self.native_evidence_artifacts, key=lambda row: row.evidence_id)),
        )
        evidence_ids = tuple(row.evidence_id for row in self.native_evidence_artifacts)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ProjectBlueprintError("project native evidence identity is not unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_snapshot_id": self.observed_snapshot_id,
            "observed_snapshot_fingerprint": self.observed_snapshot_fingerprint,
            "semantic_mesh_id": self.semantic_mesh_id,
            "semantic_mesh_fingerprint": self.semantic_mesh_fingerprint,
            "portable_owner_fingerprints": dict(self.portable_owner_fingerprints),
            "portable_member_catalogs": [
                row.to_dict() for row in self.portable_member_catalogs
            ],
            "resources": [row.to_dict() for row in self.resources],
            "test_inventory": self.test_inventory.to_dict(),
            "topology_nodes": [row.to_dict() for row in self.topology_nodes],
            "topology_relations": [row.to_dict() for row in self.topology_relations],
            "native_evidence_artifacts": [
                row.to_dict() for row in self.native_evidence_artifacts
            ],
        }


def project_blueprint_document(
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
) -> dict[str, Any]:
    """Return the canonical strict document consumed by the read-only CLI."""

    return {**definition.to_dict(), "evidence": evidence.to_dict()}


@dataclass(frozen=True)
class ProjectBlueprintBundle:
    inventory: ImplementationSurfaceInventory
    binding_report: ModelImplementationBindingReport
    manifest: SoftwareBlueprintManifest
    qualification: SoftwareBlueprintQualificationReport
    model_test_alignment_report: ModelTestAlignmentReport | None = None
    topology_report: BlueprintTopologyReport | None = None
    behavior_report: BehaviorBlueprintReport | None = None
    resource_inventory: ProjectResourceInventory | None = None
    intent_inventory: ProjectIntentInventory | None = None
    normalized_projection: NormalizedBlueprintProjection | None = None
    static_readiness: StaticBlueprintReadinessReport | None = None
    target_system_report: TargetSystemBlueprintReport | None = None
    understanding_summary: BlueprintUnderstandingSummary | None = None
    normalized_shared_objects: tuple[tuple[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return bool(
            self.qualification.static_status == "complete"
            and self.static_readiness is not None
            and self.static_readiness.status == "ready"
            and self.target_system_report is not None
            and self.target_system_report.ok
        )

    def affected_neighborhood(
        self,
        *,
        affected_surface_ids: Sequence[str] = (),
        affected_behavior_block_ids: Sequence[str] = (),
    ) -> AffectedBlueprintNeighborhood:
        if self.normalized_projection is None or self.behavior_report is None:
            raise ProjectBlueprintError("project bundle has no normalized behavior blueprint")
        return load_affected_behavior_neighborhood(
            self.normalized_projection,
            self.behavior_report,
            dict(self.normalized_shared_objects),
            affected_surface_ids=affected_surface_ids,
            affected_behavior_block_ids=affected_behavior_block_ids,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "inventory_fingerprint": self.inventory.inventory_fingerprint,
            "binding_report_fingerprint": self.binding_report.fingerprint,
            "blueprint_fingerprint": self.manifest.fingerprint,
            "qualification": self.qualification.to_static_dict(),
            "model_test_alignment_report": (
                self.model_test_alignment_report.to_dict()
                if self.model_test_alignment_report
                else None
            ),
            "topology_report": (
                self.topology_report.to_dict() if self.topology_report else None
            ),
            "behavior_report": (
                self.behavior_report.to_dict() if self.behavior_report else None
            ),
            "resource_inventory": (
                self.resource_inventory.to_dict() if self.resource_inventory else None
            ),
            "intent_inventory": (
                self.intent_inventory.to_dict() if self.intent_inventory else None
            ),
            "normalized_projection": (
                self.normalized_projection.to_dict() if self.normalized_projection else None
            ),
            "static_readiness": (
                self.static_readiness.to_dict()
                if self.static_readiness
                else None
            ),
            "target_system_report": (
                self.target_system_report.to_dict()
                if self.target_system_report
                else None
            ),
            "understanding_summary": (
                self.understanding_summary.to_dict()
                if self.understanding_summary
                else None
            ),
            "counts": {
                "files": len(self.inventory.file_dispositions),
                "implementation_surfaces": len(self.inventory.surfaces),
                "model_obligations": len(self.binding_report.required_model_element_ids),
                "bindings": len(self.binding_report.bindings),
                "semantic_specs": len(self.binding_report.semantic_specs),
                "test_evidence": len(self.binding_report.test_evidence_ids),
                "oracles": len(self.binding_report.oracles),
                "resources": len(self.manifest.resources),
                "normalized_shared_objects": len(self.normalized_shared_objects),
                "behavior_blocks": (
                    len(self.behavior_report.contracts)
                    if self.behavior_report
                    else 0
                ),
                "behavior_coverage_edges": (
                    len(self.behavior_report.coverage_edges)
                    if self.behavior_report
                    else 0
                ),
            },
        }


def _project_model_test_alignment(
    *,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    inventory: ImplementationSurfaceInventory,
    binding_report: ModelImplementationBindingReport,
) -> ModelTestAlignmentReport:
    """Build the real static model/code/test alignment review.

    This review deliberately leaves execution as ``not_run``.  Its purpose in
    a blueprint is to prove that a checker design names the exact model owner,
    code contract, and test/native member.  Runtime success remains a separate
    receipt-backed claim.
    """

    surface_by_id = {row.surface_id: row for row in inventory.surfaces}
    owner_by_model = {row.model_element_id: row for row in definition.owners}
    bindings_by_model: dict[str, list[ModelImplementationBinding]] = {}
    for binding in binding_report.bindings:
        bindings_by_model.setdefault(binding.model_element_id, []).append(binding)

    obligations: list[ModelObligation] = []
    code_contracts: list[CodeContract] = []
    code_ids_by_model: dict[str, tuple[str, ...]] = {}
    for model_element_id, owner in sorted(owner_by_model.items()):
        owner_bindings = tuple(bindings_by_model.get(model_element_id, ()))
        obligations.append(
            ModelObligation(
                obligation_id=model_element_id,
                obligation_type="behavior_contract",
                description=f"exact declared behavior owned by {owner.owner_id}",
                required=True,
                required_test_kinds=("happy_path",),
                allow_shared_evidence=True,
                allow_shared_implementation=len(owner_bindings) > 1,
                error_paths=owner.protected_failure_ids,
            )
        )
        current_code_ids: list[str] = []
        for binding in owner_bindings:
            surface = surface_by_id.get(binding.implementation_surface_id)
            if surface is None:
                continue
            code_id = f"code-contract:{binding.binding_id}"
            current_code_ids.append(code_id)
            code_contracts.append(
                CodeContract(
                    code_contract_id=code_id,
                    path=surface.path,
                    symbol=surface.symbol,
                    surface_type=surface.surface_kind,
                    role="owner",
                    implements_obligations=(model_element_id,),
                    external_inputs=surface.parameters,
                    external_outputs=("return",) if surface.returns_value else (),
                    state_reads=surface.state_reads,
                    state_writes=surface.state_writes,
                    side_effects=surface.side_effect_candidates,
                    error_paths=surface.raised_errors,
                )
            )
        code_ids_by_model[model_element_id] = tuple(current_code_ids)

    test_node_by_id = {row.node_id: row for row in evidence.test_inventory.nodes}
    artifact_by_id = {row.evidence_id: row for row in evidence.native_evidence_artifacts}
    evidence_owners: dict[str, set[str]] = {}
    for owner in definition.owners:
        for evidence_id in owner.test_evidence_ids + owner.native_evidence_ids:
            evidence_owners.setdefault(evidence_id, set()).add(owner.model_element_id)
    test_evidence: list[TestEvidence] = []
    for evidence_id, model_ids in sorted(evidence_owners.items()):
        node = test_node_by_id.get(evidence_id)
        artifact = artifact_by_id.get(evidence_id)
        code_ids = tuple(
            sorted(
                {
                    code_id
                    for model_id in model_ids
                    for code_id in code_ids_by_model.get(model_id, ())
                }
            )
        )
        test_evidence.append(
            TestEvidence(
                evidence_id=evidence_id,
                test_name=(node.pytest_nodeid if node is not None else evidence_id),
                path=(node.path if node is not None else (artifact.artifact_path if artifact else "")),
                command="declared checker design; execution receipt is separate",
                result_status="not_run",
                evidence_current=True,
                test_kind="happy_path",
                covered_obligations=tuple(sorted(model_ids)),
                covered_code_contracts=code_ids,
                assertion_scope="external_contract",
                evidence_role="primary",
            )
        )
    return review_model_test_alignment(
        ModelTestAlignmentPlan(
            model_id=definition.blueprint_id,
            obligations=tuple(obligations),
            code_contracts=tuple(code_contracts),
            test_evidence=tuple(test_evidence),
            allow_orphan_tests=True,
            require_implementation_blueprint=True,
            implementation_binding_report=binding_report,
        )
    )


def _behavior_dimension(
    surface: ImplementationSurface,
    owner: ProjectBlueprintOwner,
    dimension: str,
) -> BehaviorDimensionContract:
    semantic = owner.semantic_specs[0]
    semantics = dict(semantic.semantics)
    source_key = {
        "state": "state_effect",
        "effect": "state_effect",
        "completion": "output",
    }.get(dimension, dimension)
    applicability = {
        "input": True,
        "state": bool(surface.state_reads or surface.state_writes),
        "output": True,
        "effect": bool(surface.side_effect_candidates or surface.dynamic_operations),
        "error": True,
        "decision": bool(surface.calls or surface.dynamic_operations),
        "order": bool(surface.calls),
        "retry": not semantics.get("retry", "").startswith("not_applicable"),
        "timeout": not semantics.get("timeout", "").startswith("not_applicable"),
        "completion": True,
    }[dimension]
    observed_facts = {
        "input": "parameters=" + ",".join(surface.parameters or ("none",)),
        "state": (
            "reads="
            + ",".join(surface.state_reads or ("none",))
            + ";writes="
            + ",".join(surface.state_writes or ("none",))
        ),
        "output": f"returns_value={str(surface.returns_value).lower()}",
        "effect": "effects="
        + ",".join(
            tuple(surface.side_effect_candidates)
            + tuple(surface.dynamic_operations)
            or ("none",)
        ),
        "error": "raised_errors=" + ",".join(surface.raised_errors or ("none",)),
        "decision": "calls=" + ",".join(surface.calls or ("none",)),
        "order": "ordered_calls=" + ",".join(surface.calls or ("none",)),
        "retry": "owner_retry_rule=" + semantics.get("retry", "missing"),
        "timeout": "owner_timeout_rule=" + semantics.get("timeout", "missing"),
        "completion": (
            f"returns_value={str(surface.returns_value).lower()};"
            + "errors="
            + ",".join(surface.raised_errors or ("none",))
        ),
    }[dimension]
    if applicability:
        owner_rule = semantics.get(source_key, "")
        if not owner_rule:
            owner_rule = "missing-independent-owner-rule"
        value = (
            f"surface={surface.path}#{surface.symbol}; {observed_facts}; "
            f"independent_owner_rule={owner_rule}"
        )
        disposition = "modeled"
        rationale = (
            "the exact current surface facts are bound to one independently accepted owner rule"
        )
    else:
        value = (
            f"surface={surface.path}#{surface.symbol}; {observed_facts}; not applicable: "
            f"the exact surface inventory and independent owner rule declare no {dimension} behavior"
        )
        disposition = "not_applicable"
        rationale = "typed absence is explicit; silence does not close the dimension"
    provenance = dict(semantic.provenance_fingerprints)
    provenance["owner-contract"] = owner.owner_contract_fingerprint
    return BehaviorDimensionContract(
        dimension=dimension,
        disposition=disposition,
        semantics=value,
        rationale=rationale,
        provenance_fingerprints=tuple(provenance.items()),
        semantic_rule_ids=(
            f"semantic-rule:{semantic.semantic_spec_id}:{dimension}",
        ),
        applicability_surface_ids=owner.implementation_surface_ids,
    )


def _resource_inventory(
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
) -> ProjectResourceInventory:
    kind_to_category = {
        "verification": "behavioral_oracle",
    }
    members: list[ProjectResourceMember] = []
    present: set[str] = set()
    for resource in evidence.resources:
        category = kind_to_category.get(resource.kind, resource.kind)
        present.add(category)
        disposition = resource.disposition
        if disposition not in {"current", "external", "scoped_out"}:
            disposition = "blocked"
        members.append(
            ProjectResourceMember(
                member_id=resource.resource_id,
                category=category,
                category_disposition=disposition,
                category_evidence_fingerprint=resource.fingerprint,
                resource_reference=(resource if disposition != "blocked" else None),
                rationale=(
                    "independently discovered current project resource"
                    if disposition == "current"
                    else str(resource.rationale or "declared non-current resource boundary")
                ),
            )
        )
    for category in (
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
    ):
        if category in present:
            continue
        if category == "external_service" and not definition.boundary.external_patterns:
            rationale = "the independently declared target boundary contains no external-service pattern"
            scoped_reference = BlueprintResourceReference(
                resource_id="resource:external-service:none-declared",
                kind="external_service",
                owner_id=definition.blueprint_id,
                artifact_id="target-boundary:external-patterns",
                purpose="preserve the explicit absence of an external-service dependency",
                lifecycle_role="not_applicable",
                disposition="scoped_out",
                rationale=rationale,
            )
            members.append(
                ProjectResourceMember(
                    member_id=scoped_reference.resource_id,
                    category=category,
                    category_disposition="scoped_out",
                    category_evidence_fingerprint=fingerprint_value(
                        definition.boundary.to_dict()
                    ),
                    resource_reference=scoped_reference,
                    rationale=rationale,
                )
            )
        else:
            members.append(
                ProjectResourceMember(
                    member_id=f"resource:missing:{category}",
                    category=category,
                    category_disposition="blocked",
                    category_evidence_fingerprint=fingerprint_value(
                        {
                            "boundary": definition.boundary.to_dict(),
                            "missing_category": category,
                        }
                    ),
                    resource_reference=None,
                    rationale="independent resource discovery found no terminal member for this category",
                )
            )
    return ProjectResourceInventory(
        inventory_id=f"resource-inventory:{definition.blueprint_id}",
        boundary_fingerprint=fingerprint_value(definition.boundary.to_dict()),
        members=tuple(members),
        discovery_fingerprints=(
            ("implementation-manifest", fingerprint_value([row.to_dict() for row in definition.file_dispositions])),
            ("software-boundary", fingerprint_value(definition.boundary.to_dict())),
        ),
    )


def _behavior_readiness(
    *,
    inventory: ImplementationSurfaceInventory,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
    intent_inventory: ProjectIntentInventory,
    model_test_alignment_report: ModelTestAlignmentReport,
    topology_report: BlueprintTopologyReport,
    delegated_assertion_helpers: Sequence[DelegatedAssertionHelper] = (),
    delegated_helper_fingerprints: Mapping[str, str] | None = None,
) -> tuple[
    BehaviorBlueprintReport,
    ProjectResourceInventory,
    NormalizedBlueprintProjection,
    StaticBlueprintReadinessReport,
    tuple[tuple[str, Any], ...],
]:
    owner_by_surface = {
        surface_id: owner
        for owner in definition.owners
        for surface_id in owner.implementation_surface_ids
    }
    behavior_ids = _project_behavior_surface_ids(inventory, definition)
    behavior_surfaces = tuple(
        row
        for row in inventory.surfaces
        if row.surface_id in behavior_ids
    )
    supporting_surfaces = tuple(
        row
        for row in inventory.surfaces
        if row.surface_id in set(inventory.required_surface_ids)
        and row.surface_id not in behavior_ids
        and row.surface_kind not in {"module", "class"}
    )
    contracts: list[BehaviorBlockContract] = []
    portable_bindings: list[PortableBehaviorBinding] = []
    case_contracts: list[BehaviorCaseContract] = []
    behavior_by_surface: dict[str, BehaviorBlockContract] = {}
    for surface in behavior_surfaces:
        owner = owner_by_surface.get(surface.surface_id)
        if owner is None:
            continue
        semantic = owner.semantic_specs[0]
        behavior_block_id = f"behavior-block:{surface.surface_id}"
        portable_binding_id = f"portable-binding:{surface.surface_id}"
        contract = BehaviorBlockContract(
            behavior_block_id=behavior_block_id,
            implementation_surface_id=surface.surface_id,
            model_element_id=owner.model_element_id,
            owner_contract_id=owner.owner_contract_id,
            owner_id=owner.owner_id,
            function_relation="Input x State -> Set(Output x State)",
            dimensions=tuple(
                _behavior_dimension(surface, owner, dimension)
                for dimension in BEHAVIOR_DIMENSIONS
            ),
            semantic_spec_ids=tuple(row.semantic_spec_id for row in owner.semantic_specs),
            oracle_ids=tuple(row.oracle_id for row in owner.oracles),
            portable_binding_ids=(portable_binding_id,),
            protected_failure_ids=owner.protected_failure_ids,
            accepted=owner.behavior_accepted,
            acceptance_evidence_fingerprints=(
                owner.behavior_acceptance_evidence_fingerprints
            ),
            source_fingerprint=surface.content_fingerprint,
        )
        contracts.append(contract)
        behavior_by_surface[surface.surface_id] = contract
        expected_input_fields = set(surface.parameters)
        expected_output_fields = {"return"} if surface.returns_value else set()
        expected_state_fields = (
            set(surface.state_reads) | set(surface.state_writes)
        ) - set(surface.parameters)
        declared_field_sets = (
            (
                "input",
                {field for field, _member in owner.portable_input_field_mappings},
                expected_input_fields,
            ),
            (
                "output",
                {field for field, _member in owner.portable_output_field_mappings},
                expected_output_fields,
            ),
            (
                "state",
                {field for field, _member in owner.portable_state_field_mappings},
                expected_state_fields,
            ),
        )
        for field_kind, declared_fields, expected_fields in declared_field_sets:
            if declared_fields != expected_fields:
                raise ProjectBlueprintError(
                    f"portable {field_kind} mapping differs from the exact primary "
                    f"surface fields for {surface.surface_id}: "
                    f"missing={sorted(expected_fields - declared_fields)} "
                    f"unexpected={sorted(declared_fields - expected_fields)}"
                )
        portable_bindings.append(
            PortableBehaviorBinding(
                binding_id=portable_binding_id,
                behavior_block_id=behavior_block_id,
                portable_model_id=owner.portable_model_id,
                portable_model_fingerprint=owner.portable_model_fingerprint,
                implementation_fingerprint=surface.content_fingerprint,
                transition_ids=owner.portable_transition_ids,
                property_ids=owner.portable_property_ids,
                invariant_ids=owner.portable_invariant_ids,
                input_field_mappings=owner.portable_input_field_mappings,
                output_field_mappings=owner.portable_output_field_mappings,
                state_field_mappings=owner.portable_state_field_mappings,
                assumption_ids=owner.portable_assumption_ids,
                guarantee_ids=owner.portable_guarantee_ids,
                protected_failure_ids=owner.protected_failure_ids,
                provider_fingerprints=(
                    ("independent-owner-model", owner.model_fingerprint),
                    ("implementation-observation", surface.structure_fingerprint),
                ),
            )
        )
        declared_cases = tuple(owner.behavior_case_contracts)
        if any(case.behavior_block_id != behavior_block_id for case in declared_cases):
            raise ProjectBlueprintError(
                f"declared behavior cases target another block for {owner.owner_id}"
            )
        if any(case.oracle_id not in contract.oracle_ids for case in declared_cases):
            raise ProjectBlueprintError(
                f"declared behavior cases target another oracle for {owner.owner_id}"
            )
        case_contracts.extend(declared_cases)

    planned_checker_fingerprints = {
        checker_id: checker_fingerprint
        for owner in definition.owners
        for checker_id, checker_fingerprint in owner.checker_design_fingerprints
    }

    supporting_relations: list[SupportingSurfaceRelation] = []
    surface_by_id = {row.surface_id: row for row in inventory.surfaces}
    for surface in supporting_surfaces:
        candidate = behavior_by_surface.get(surface.owning_surface_id)
        ancestor_id = surface.parent_surface_id
        visited: set[str] = set()
        while candidate is None and ancestor_id and ancestor_id not in visited:
            visited.add(ancestor_id)
            candidate = behavior_by_surface.get(ancestor_id)
            ancestor = surface_by_id.get(ancestor_id)
            ancestor_id = ancestor.parent_surface_id if ancestor is not None else ""
        if candidate is None:
            declared_owner = owner_by_surface.get(surface.surface_id)
            if declared_owner is not None:
                candidate = behavior_by_surface.get(declared_owner.primary_surface_id)
        if candidate is None:
            helper_leaf = surface.symbol.rsplit(".", 1)[-1]
            helper_owner = owner_by_surface.get(surface.surface_id)
            call_candidates = tuple(
                behavior_by_surface[row.surface_id]
                for row in behavior_surfaces
                if helper_owner is not None
                and owner_by_surface.get(row.surface_id) is not None
                and owner_by_surface[row.surface_id].owner_id == helper_owner.owner_id
                and any(
                    call == surface.symbol
                    or call == helper_leaf
                    or call.endswith("." + helper_leaf)
                    for call in row.calls
                )
            )
            if len(call_candidates) == 1:
                candidate = call_candidates[0]
        if candidate is not None:
            relation_kind = (
                "calls"
                if surface.owning_surface_id or surface.parent_surface_id
                else "delegates"
            )
            supporting_relations.append(
                SupportingSurfaceRelation(
                    supporting_surface_id=surface.surface_id,
                    behavior_block_id=candidate.behavior_block_id,
                    relation_kind=relation_kind,
                    evidence_id=f"supporting-edge:{surface.surface_id}:{candidate.behavior_block_id}",
                    evidence_fingerprint=surface.structure_fingerprint,
                    rationale="current discovered parent/owning-surface evidence binds one exact behavior owner",
                )
            )

    coverage: list[BehaviorCoverageEdge] = []
    coverage_execution: list[CoverageExecutionEvidence] = []
    test_node_by_id = {row.node_id: row for row in evidence.test_inventory.nodes}
    owner_by_id = {row.owner_id: row for row in definition.owners}
    cases_by_block: dict[str, list[BehaviorCaseContract]] = {}
    for case in case_contracts:
        cases_by_block.setdefault(case.behavior_block_id, []).append(case)
    for contract in contracts:
        owner = owner_by_id[contract.owner_id]
        if owner.native_evidence_fingerprints:
            test_node_id, member_fingerprint = owner.native_evidence_fingerprints[0]
            oracle_member_id = test_node_id
            evidence_role = "native_model_check"
        else:
            real_nodes = tuple(
                test_node_by_id[test_id]
                for test_id in owner.test_evidence_ids
                if test_id in test_node_by_id and test_node_by_id[test_id].assertions
            )
            if not real_nodes:
                continue
            node = real_nodes[0]
            assertion = node.assertions[0]
            test_node_id = node.node_id
            oracle_member_id = assertion.assertion_id
            member_fingerprint = assertion.structure_fingerprint
            evidence_role = "real_test_assertion"
        dimensions_by_case_kind = {
            "good": ("input", "state", "output", "effect", "order", "completion"),
            "boundary": ("input", "state", "output", "retry", "timeout", "completion"),
            "bad": ("input", "state", "effect", "error", "decision", "completion"),
        }
        for case in cases_by_block.get(contract.behavior_block_id, ()):
            for dimension in dimensions_by_case_kind[case.case_kind]:
                coverage_id = (
                    f"coverage:{contract.behavior_block_id}:{case.case_id}:{dimension}"
                )
                dimension_member_id = f"{case.case_evidence_id}:{dimension}"
                dimension_member_fingerprint = planned_checker_fingerprints.get(
                    dimension_member_id
                )
                if dimension_member_fingerprint is None:
                    continue
                coverage.append(
                    BehaviorCoverageEdge(
                        coverage_id=coverage_id,
                        behavior_block_id=contract.behavior_block_id,
                        implementation_surface_id=contract.implementation_surface_id,
                        model_obligation_id=contract.model_element_id,
                        semantic_spec_id=contract.semantic_spec_ids[0],
                        owner_contract_id=contract.owner_contract_id,
                        test_node_id=test_node_id,
                        oracle_member_id=dimension_member_id,
                        oracle_member_fingerprint=dimension_member_fingerprint,
                        case_id=case.case_id,
                        covered_dimensions=(dimension,),
                        evidence_role="planned_checker",
                        oracle_id=contract.oracle_ids[0],
                    )
                )
                coverage_execution.append(
                    CoverageExecutionEvidence(
                        coverage_id=coverage_id,
                        execution_owner_id=f"execution-owner:{contract.owner_id}",
                        disposition="not_run",
                    )
                )
    owner_ids_by_test: dict[str, list[str]] = {}
    for owner in definition.owners:
        for test_id in owner.test_evidence_ids:
            owner_ids_by_test.setdefault(test_id, []).append(owner.owner_id)
    coverage_by_test: dict[str, tuple[BehaviorCoverageEdge, ...]] = {}
    for test_node_id in {row.test_node_id for row in coverage}:
        coverage_by_test[test_node_id] = tuple(
            row for row in coverage if row.test_node_id == test_node_id
        )
    contract_owner_by_block = {
        row.behavior_block_id: row.owner_id for row in contracts
    }
    test_dispositions: list[ProjectTestNodeDisposition] = []
    required_node_ids = set(evidence.test_inventory.required_node_ids)
    for node in evidence.test_inventory.nodes:
        if node.node_id not in required_node_ids:
            continue
        node_coverage = coverage_by_test.get(node.node_id, ())
        coverage_ids = tuple(sorted(row.coverage_id for row in node_coverage))
        owner_ids = tuple(
            sorted(
                {
                    contract_owner_by_block[row.behavior_block_id]
                    for row in node_coverage
                }
                | set(owner_ids_by_test.get(node.node_id, ()))
            )
        )
        if coverage_ids and len(owner_ids) <= 1:
            disposition = "behavior_coverage"
            rationale = (
                "the current test node owns exact behavior case/oracle coverage edges; "
                "its execution disposition remains separate"
            )
        elif coverage_ids:
            disposition = "cross_owner_integration"
            rationale = (
                "the current test node owns exact coverage edges for several behavior owners"
            )
        else:
            disposition = "supporting"
            coverage_ids = ()
            rationale = (
                "the project regression is current supporting evidence, but its declared "
                "owner scope is not precise enough to certify one behavior block"
            )
        test_dispositions.append(
            ProjectTestNodeDisposition(
                test_node_id=node.node_id,
                disposition=disposition,
                owner_ids=owner_ids,
                coverage_ids=coverage_ids,
                rationale=rationale,
            )
        )
    behavior_report = review_behavior_blueprint(
        inventory_fingerprint=inventory.inventory_fingerprint,
        required_behavior_surface_ids=tuple(row.surface_id for row in behavior_surfaces),
        supporting_surface_ids=tuple(row.surface_id for row in supporting_surfaces),
        contracts=tuple(contracts),
        portable_bindings=tuple(portable_bindings),
        case_contracts=tuple(case_contracts),
        supporting_relations=tuple(supporting_relations),
        coverage_edges=tuple(coverage),
        coverage_execution_evidence=tuple(coverage_execution),
        test_node_dispositions=tuple(test_dispositions),
        required_test_node_ids=evidence.test_inventory.required_node_ids,
        test_nodes=evidence.test_inventory.nodes,
        native_member_fingerprints=dict(
            artifact_pair
            for owner in definition.owners
            for artifact_pair in owner.native_evidence_fingerprints
        ),
        planned_checker_fingerprints=planned_checker_fingerprints,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints=delegated_helper_fingerprints,
        expected_portable_fingerprints={
            catalog.portable_model_id: catalog.portable_model_fingerprint
            for catalog in evidence.portable_member_catalogs
        },
        expected_portable_members={
            catalog.portable_model_id: {
                "transition_ids": catalog.transition_ids,
                "property_ids": catalog.property_ids,
                "invariant_ids": catalog.invariant_ids,
                "input_field_ids": catalog.input_field_ids,
                "output_field_ids": catalog.output_field_ids,
                "state_field_ids": catalog.state_field_ids,
                "assumption_ids": catalog.assumption_ids,
                "guarantee_ids": catalog.guarantee_ids,
            }
            for catalog in evidence.portable_member_catalogs
        },
        supporting_surface_fingerprints={
            row.surface_id: row.structure_fingerprint
            for row in supporting_surfaces
        },
    )
    resource_inventory = _resource_inventory(definition, evidence)
    shared_objects: dict[str, Any] = {}
    for owner in definition.owners:
        shared_objects[owner.owner_id] = {
            "kind": "behavior_owner",
            "model_element_id": owner.model_element_id,
            "model_fingerprint": owner.model_fingerprint,
        }
        shared_objects[owner.owner_contract_id] = {
            "kind": "owner_contract",
            "owner_id": owner.owner_id,
            "fingerprint": owner.owner_contract_fingerprint,
        }
        for semantic in owner.semantic_specs:
            shared_objects[semantic.semantic_spec_id] = semantic.to_dict()
        for oracle in owner.oracles:
            shared_objects[oracle.oracle_id] = oracle.to_dict()
    for row in evidence.test_inventory.nodes:
        shared_objects[row.node_id] = row.to_dict()
        for assertion in row.assertions:
            shared_objects[assertion.assertion_id] = assertion.to_dict()
        for marker in row.parameterization_markers:
            shared_objects[marker.marker_id] = marker.to_dict()
            for case_id in marker.case_ids:
                shared_objects[f"case:{marker.marker_id}:{case_id}"] = {
                    "kind": "test_case",
                    "marker_id": marker.marker_id,
                    "case_id": case_id,
                    "test_node_id": row.node_id,
                }
    for row in portable_bindings:
        shared_objects[row.binding_id] = {
            "kind": "portable_behavior_binding",
            **row.to_dict(),
        }
    for checker_id, checker_fingerprint in planned_checker_fingerprints.items():
        shared_objects[checker_id] = {
            "kind": "declared_checker_design",
            "fingerprint": checker_fingerprint,
        }
    for row in case_contracts:
        shared_objects[row.case_id] = {
            "kind": "behavior_case_contract",
            **row.to_dict(),
        }
    for row in coverage:
        shared_objects[row.coverage_id] = {
            "kind": "behavior_coverage_edge",
            **row.to_dict(),
        }
    for row in coverage_execution:
        if row.receipt_id:
            shared_objects[row.receipt_id] = {
                "kind": "terminal_execution_receipt",
                "fingerprint": row.receipt_fingerprint,
                "disposition": row.disposition,
            }
    for artifact in evidence.native_evidence_artifacts:
        shared_objects[artifact.evidence_id] = {
            "kind": "native_evidence_artifact",
            **artifact.to_dict(),
        }
    for row in resource_inventory.members:
        shared_objects[row.member_id] = row.to_dict()
    for row in intent_inventory.contributions:
        shared_objects[row.contribution_id] = row.to_dict()
    shared_objects[
        f"model-test-alignment:{model_test_alignment_report.fingerprint}"
    ] = {
        "kind": "model_test_alignment_report",
        **model_test_alignment_report.to_dict(),
    }
    shared_objects[f"blueprint-topology:{topology_report.topology_id}"] = {
        "kind": "blueprint_topology_report",
        **topology_report.to_dict(),
    }
    for row in evidence.topology_nodes:
        shared_objects[f"topology-node:{row.node_id}"] = {
            "kind": "blueprint_topology_node",
            **row.to_dict(),
        }
    for row in evidence.topology_relations:
        shared_objects[f"topology-relation:{row.relation_id}"] = {
            "kind": "blueprint_topology_relation",
            **row.to_dict(),
        }
    for row in evidence.topology_nodes:
        shared_objects[f"topology-index:{row.node_id}"] = {
            "kind": "blueprint_topology_index",
            "node_object_id": f"topology-node:{row.node_id}",
            "relation_object_ids": sorted(
                f"topology-relation:{relation.relation_id}"
                for relation in evidence.topology_relations
                if row.node_id in (relation.producer_id, relation.consumer_id)
            ),
        }
    for owner in definition.owners:
        shared_objects[
            f"model-test-alignment-owner:{owner.model_element_id}"
        ] = {
            "kind": "model_test_alignment_owner",
            "model_test_alignment_report_fingerprint": (
                model_test_alignment_report.fingerprint
            ),
            "implementation_binding_report_fingerprint": (
                model_test_alignment_report.implementation_binding_report_fingerprint
            ),
            "pre_code_status": model_test_alignment_report.pre_code_status,
            "executed_evidence_status": (
                model_test_alignment_report.executed_evidence_status
            ),
            "test_evidence_ids": list(owner.test_evidence_ids),
            "native_evidence_ids": list(owner.native_evidence_ids),
        }
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        shared_objects=shared_objects,
        source_projection=binding_report.to_dict(),
    )
    readiness = review_static_blueprint_readiness(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        resource_inventory=resource_inventory,
        intent_inventory=intent_inventory,
        topology_fingerprint=topology_report.fingerprint,
        normalized_projection_fingerprint=projection.fingerprint,
        topology_findings=tuple(
            ReadinessFinding(
                row.code,
                row.message,
                row.subject_ids,
                "blocked",
            )
            for row in topology_report.findings
        ),
    )
    return (
        behavior_report,
        resource_inventory,
        projection,
        readiness,
        tuple(sorted(shared_objects.items())),
    )


def _target_system_blueprint_report(
    *,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    inventory: ImplementationSurfaceInventory,
    binding_report: ModelImplementationBindingReport,
    model_test_alignment_report: ModelTestAlignmentReport,
    topology_report: BlueprintTopologyReport,
    manifest: SoftwareBlueprintManifest,
    qualification: SoftwareBlueprintQualificationReport,
    behavior_report: BehaviorBlueprintReport,
    resource_inventory: ProjectResourceInventory,
    intent_inventory: ProjectIntentInventory,
    readiness: StaticBlueprintReadinessReport,
) -> TargetSystemBlueprintReport:
    """Compose project-native reviewers under one provider-neutral result."""

    descriptor = TargetSystemDescriptor(
        target_system_id=f"target-system:{definition.blueprint_id}",
        target_kind=definition.target_kind,
        subject_revision=evidence.observed_snapshot_fingerprint,
        boundary_fingerprint=fingerprint_value(definition.boundary.to_dict()),
        required_observation_capabilities=(
            "implementation_inventory",
            "resource_inventory",
            "test_inventory",
        ),
        required_authority_capabilities=(
            "behavior_semantics",
            "intent_lineage",
            "model_authority",
            "model_topology",
            "oracle_inventory",
            "portable_behavior",
        ),
        claim_boundary=definition.claim_boundary,
    )
    portable_fingerprint = fingerprint_value(
        {
            "owners": dict(evidence.portable_owner_fingerprints),
            "member_catalogs": [
                row.to_dict() for row in evidence.portable_member_catalogs
            ],
        }
    )
    payload_fingerprints = {
        "implementation_inventory": inventory.inventory_fingerprint,
        "resource_inventory": resource_inventory.fingerprint,
        "test_inventory": evidence.test_inventory.inventory_fingerprint,
        "behavior_semantics": behavior_report.fingerprint,
        "intent_lineage": intent_inventory.fingerprint,
        "model_authority": evidence.observed_snapshot_fingerprint,
        "model_topology": topology_report.fingerprint,
        "oracle_inventory": fingerprint_value(
            [row.to_dict() for row in binding_report.oracles]
        ),
        "portable_behavior": portable_fingerprint,
    }
    providers: list[TargetSystemProviderResult] = []
    for role, declarations in (
        ("observation", definition.observation_providers),
        ("authority", definition.authority_providers),
    ):
        for provider_id, capabilities in declarations:
            missing_payloads = tuple(
                capability
                for capability in capabilities
                if capability not in payload_fingerprints
            )
            providers.append(
                TargetSystemProviderResult(
                    provider_id=provider_id,
                    provider_role=role,
                    provider_kind=provider_id,
                    provider_version="declared-current",
                    target_system_id=descriptor.target_system_id,
                    subject_revision=descriptor.subject_revision,
                    capability_ids=capabilities,
                    input_fingerprints=(
                        ("boundary", descriptor.boundary_fingerprint),
                        ("definition", fingerprint_value(definition.to_dict())),
                    ),
                    payload_fingerprints=tuple(
                        (capability, payload_fingerprints[capability])
                        for capability in capabilities
                        if capability in payload_fingerprints
                    ),
                    capability_bindings=tuple(
                        ProviderCapabilityBinding(
                            capability_id=capability,
                            input_ids=("boundary", "definition"),
                            payload_ids=(capability,),
                        )
                        for capability in capabilities
                        if capability in payload_fingerprints
                    ),
                    status=("incomplete" if missing_payloads else "current"),
                    findings=tuple(
                        f"provider capability has no canonical payload: {capability}"
                        for capability in missing_payloads
                    ),
                    claim_boundary=definition.claim_boundary,
                )
            )

    gaps: list[BlueprintGapRef] = []
    layers: list[BlueprintLayerResult] = []

    def add_layer(
        layer: str,
        passed: bool,
        evidence_ids: Sequence[str],
        *,
        object_kind: str,
        object_id: str,
        message: str,
        status: str = "incomplete",
    ) -> None:
        if passed:
            layers.append(
                BlueprintLayerResult(
                    layer=layer,
                    status="pass",
                    evidence_ids=tuple(evidence_ids),
                )
            )
            return
        gap = BlueprintGapRef(
            layer=layer,
            object_kind=object_kind,
            object_id=object_id,
            status=status,
            evidence_ref=(evidence_ids[0] if evidence_ids else ""),
            message=message,
        )
        gaps.append(gap)
        layers.append(
            BlueprintLayerResult(
                layer=layer,
                status=(status if status in {"stale", "blocked"} else "incomplete"),
                evidence_ids=tuple(evidence_ids),
                gap_ids=(gap.gap_id,),
            )
        )

    add_layer(
        "implementation_inventory",
        True,
        (inventory.inventory_fingerprint,),
        object_kind="implementation_inventory",
        object_id=inventory.inventory_id,
        message="implementation inventory is incomplete",
    )
    add_layer(
        "traceability",
        binding_report.ok and topology_report.ok,
        (binding_report.fingerprint, topology_report.fingerprint),
        object_kind="model_implementation_binding_report",
        object_id=f"binding-report:{binding_report.fingerprint}",
        message="model-to-implementation traceability is incomplete",
        status=("blocked" if not binding_report.ok else "incomplete"),
    )
    semantic_complete = bool(behavior_report.contracts) and all(
        row.accepted for row in behavior_report.contracts
    ) and not any(
        row.code
        in {
            "behavior_contract_missing",
            "behavior_contract_unaccepted",
            "same_source_semantic_oracle_circularity",
            "generic_semantics_reused_across_blocks",
            "portable_behavior_binding_missing",
            "portable_behavior_binding_stale",
        }
        for row in behavior_report.findings
    )
    add_layer(
        "independent_semantics",
        semantic_complete,
        (behavior_report.fingerprint,),
        object_kind="behavior_semantics",
        object_id=behavior_report.fingerprint,
        message="one or more behavior blocks lack independent exact semantics",
    )
    add_layer(
        "model_code_test",
        behavior_report.complete
        and model_test_alignment_report.pre_code_status == "ready"
        and model_test_alignment_report.implementation_binding_report_fingerprint
        == binding_report.fingerprint,
        (
            behavior_report.fingerprint,
            binding_report.fingerprint,
            model_test_alignment_report.fingerprint,
        ),
        object_kind="behavior_coverage",
        object_id=behavior_report.fingerprint,
        message="exact model-code-test behavior coverage is incomplete",
        status=(
            "blocked"
            if any(row.severity == "blocked" for row in behavior_report.findings)
            else "incomplete"
        ),
    )
    resource_oracle_complete = resource_inventory.complete and intent_inventory.complete
    add_layer(
        "resource_oracle",
        resource_oracle_complete,
        (resource_inventory.fingerprint, intent_inventory.fingerprint),
        object_kind="resource_intent_oracle_closure",
        object_id=manifest.blueprint_id,
        message="resource, intent, or oracle closure is incomplete",
        status=("blocked" if not resource_inventory.complete else "incomplete"),
    )
    static_ready = qualification.static_status == "complete" and readiness.status == "ready"
    add_layer(
        "static_blueprint",
        static_ready,
        (manifest.fingerprint, readiness.fingerprint),
        object_kind="static_blueprint",
        object_id=manifest.blueprint_id,
        message="canonical static target-system blueprint is not ready",
        status=(
            readiness.status
            if readiness.status in {"stale", "blocked"}
            else "incomplete"
        ),
    )
    registry = build_target_system_provider_registry(
        f"provider-registry:{definition.blueprint_id}",
        tuple(
            TargetSystemProviderDeclaration(
                provider_id=row.provider_id,
                provider_role=row.provider_role,
                provider_kind=row.provider_kind,
                provider_version=row.provider_version,
                capability_ids=row.capability_ids,
                claim_boundary=row.claim_boundary,
            )
            for row in providers
        ),
    )
    snapshot = capture_target_system_snapshot(
        f"target-system-snapshot:{definition.blueprint_id}:{descriptor.subject_revision}",
        descriptor,
        registry,
        tuple(providers),
    )
    return compile_target_system_blueprint(
        descriptor,
        tuple(providers),
        downstream_layers=tuple(layers),
        downstream_gaps=tuple(gaps),
        provider_registry=registry,
        snapshot=snapshot,
    )


def build_project_blueprint(
    root: str | Path,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    *,
    discovery_adapters: Mapping[str, DiscoveryAdapter],
    test_discovery_adapters: Mapping[str, TestDiscoveryAdapter],
    implementation_inventory: ImplementationSurfaceInventory | None = None,
    intent_inventory: ProjectIntentInventory | None = None,
    topology_fingerprint: str = "",
    delegated_assertion_helpers: Sequence[DelegatedAssertionHelper] = (),
    delegated_helper_fingerprints: Mapping[str, str] | None = None,
) -> ProjectBlueprintBundle:
    """Build and qualify one in-memory project blueprint without target writes."""

    root_path = Path(root).resolve()
    if implementation_inventory is None:
        inventory = build_implementation_surface_inventory(
            root_path,
            definition.boundary,
            inventory_id=definition.inventory_id,
            file_dispositions=definition.file_dispositions,
            surface_dispositions=dict(definition.surface_dispositions),
            supporting_owners=dict(definition.supporting_owners),
            dynamic_allowances=dict(definition.dynamic_allowances),
            discovery_adapters=discovery_adapters,
            claim_boundary=definition.claim_boundary,
        )
    else:
        inventory = implementation_inventory
        if inventory.inventory_id != definition.inventory_id:
            raise ProjectBlueprintError("supplied inventory identity does not match definition")
        if inventory.boundary != definition.boundary:
            raise ProjectBlueprintError("supplied inventory boundary does not match definition")
        if inventory.file_dispositions != definition.file_dispositions:
            raise ProjectBlueprintError("supplied inventory file manifest does not match definition")
        if inventory.claim_boundary != definition.claim_boundary:
            raise ProjectBlueprintError("supplied inventory claim boundary does not match definition")
    test_audit = review_project_test_inventory(
        evidence.test_inventory,
        root=root_path,
        discovery_adapters=test_discovery_adapters,
    )
    if not test_audit.ok:
        codes = ",".join(row.code for row in test_audit.findings)
        raise ProjectBlueprintError(
            f"project test inventory is not exact-current: {codes}"
        )
    surface_by_id = {row.surface_id: row for row in inventory.surfaces}
    bindings: list[ModelImplementationBinding] = []
    semantic_specs: list[SemanticSpecReference] = []
    oracles: list[OracleReference] = []
    current_models: dict[str, str] = {}
    current_contracts: dict[str, str] = {}
    current_tests = {
        row.node_id: row.structure_fingerprint
        for row in evidence.test_inventory.nodes
    }
    for artifact in evidence.native_evidence_artifacts:
        if artifact.evidence_id in current_tests:
            raise ProjectBlueprintError(
                "project evidence identity collides with a test node"
            )
        current_path = (root_path / artifact.artifact_path).resolve()
        try:
            current_path.relative_to(root_path)
        except ValueError as exc:
            raise ProjectBlueprintError(
                "project evidence artifact escapes the root"
            ) from exc
        if not current_path.is_file():
            raise ProjectBlueprintError(
                f"project evidence artifact is missing: {artifact.artifact_path}"
            )
        if source_file_fingerprint(current_path) != artifact.artifact_fingerprint:
            raise ProjectBlueprintError(
                f"project evidence artifact is stale: {artifact.artifact_path}"
            )
        current_tests[artifact.evidence_id] = artifact.artifact_fingerprint
    behavior_surface_ids = _project_behavior_surface_ids(inventory, definition)
    for owner in definition.owners:
        current_models[owner.model_element_id] = owner.model_fingerprint
        current_contracts[owner.owner_contract_id] = owner.owner_contract_fingerprint
        owner_behavior_ids = tuple(
            sorted(set(owner.implementation_surface_ids) & behavior_surface_ids)
        )
        primary_behavior_id = (
            owner.primary_surface_id
            if owner.primary_surface_id in owner_behavior_ids
            else (owner_behavior_ids[0] if owner_behavior_ids else "")
        )
        for surface_id in owner_behavior_ids:
            surface = surface_by_id.get(surface_id)
            dimensions = project_surface_dimensions(surface) if surface is not None else ("input", "output", "error")
            primary = surface_id == primary_behavior_id
            source_semantic = owner.semantic_specs[0]
            behavior_dimensions = tuple(
                _behavior_dimension(surface, owner, dimension)
                for dimension in BEHAVIOR_DIMENSIONS
            )
            semantic_payload = {
                row.dimension: row.semantics
                for row in behavior_dimensions
                if row.dimension in set(dimensions)
            }
            if "state_effect" in dimensions:
                semantic_payload["state_effect"] = next(
                    row.semantics
                    for row in behavior_dimensions
                    if row.dimension in {"state", "effect"}
                    and row.disposition == "modeled"
                )
            semantic_id = f"semantic-spec:{owner.model_element_id}:{surface_id}"
            semantic_fingerprint = fingerprint_value(
                {
                    "owner_semantic_fingerprint": source_semantic.artifact_fingerprint,
                    "surface_id": surface_id,
                    "dimensions": semantic_payload,
                }
            )
            semantic_specs.append(
                SemanticSpecReference(
                    semantic_spec_id=semantic_id,
                    owner_id=owner.owner_id,
                    artifact_id=f"{source_semantic.artifact_id}#{surface_id}",
                    artifact_fingerprint=semantic_fingerprint,
                    covered_model_element_ids=(owner.model_element_id,),
                    covered_dimensions=tuple(sorted(semantic_payload)),
                    semantics=tuple(semantic_payload.items()),
                    authority_kind=source_semantic.authority_kind,
                    provenance_fingerprints=tuple(
                        {
                            **dict(source_semantic.provenance_fingerprints),
                            "owner-contract": owner.owner_contract_fingerprint,
                            "surface-structure": surface.structure_fingerprint,
                        }.items()
                    ),
                )
            )
            source_oracle = owner.oracles[0]
            oracle_payload = {
                dimension: dict(source_oracle.semantics).get(
                    {
                        "completion": "output",
                    }.get(dimension, dimension),
                    f"inspect the accepted {dimension} contract for {surface.symbol}",
                )
                for dimension in dimensions
            }
            oracle_id = f"oracle:{owner.model_element_id}:{surface_id}"
            oracle_fingerprint = fingerprint_value(
                {
                    "owner_oracle_fingerprint": source_oracle.artifact_fingerprint,
                    "surface_id": surface_id,
                    "dimensions": oracle_payload,
                }
            )
            oracles.append(
                OracleReference(
                    oracle_id=oracle_id,
                    owner_id=source_oracle.owner_id,
                    artifact_id=f"{source_oracle.artifact_id}#{surface_id}",
                    artifact_fingerprint=oracle_fingerprint,
                    covered_model_element_ids=(owner.model_element_id,),
                    covered_dimensions=tuple(sorted(oracle_payload)),
                    semantics=tuple(oracle_payload.items()),
                )
            )
            current_owner_evidence = (
                owner.test_evidence_fingerprints
                + owner.native_evidence_fingerprints
            )
            bindings.append(
                ModelImplementationBinding(
                    binding_id=f"binding:{owner.model_element_id}:{surface_id}",
                    model_element_id=owner.model_element_id,
                    implementation_surface_id=surface_id,
                    relation_kind="implements",
                    owner_contract_id=owner.owner_contract_id,
                    semantic_spec_ids=(semantic_id,),
                    oracle_ids=(oracle_id,),
                    required_dimensions=dimensions,
                    test_evidence_ids=tuple(
                        evidence_id for evidence_id, _fingerprint in current_owner_evidence
                    ),
                    test_evidence_fingerprints=current_owner_evidence,
                    primary=primary,
                    model_fingerprint=owner.model_fingerprint,
                    implementation_fingerprint=(surface.content_fingerprint if surface else None),
                    owner_contract_fingerprint=owner.owner_contract_fingerprint,
                )
            )

    binding_report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=tuple(row.model_element_id for row in definition.owners),
        required_implementation_surface_ids=tuple(sorted(behavior_surface_ids)),
        bindings=tuple(bindings),
        semantic_specs=tuple(semantic_specs),
        oracles=tuple(oracles),
        current_model_fingerprints=current_models,
        current_contract_fingerprints=current_contracts,
        current_semantic_spec_fingerprints={row.semantic_spec_id: row.artifact_fingerprint for row in semantic_specs},
        current_oracle_fingerprints={row.oracle_id: row.artifact_fingerprint for row in oracles},
        current_test_evidence_fingerprints=current_tests,
    )
    model_test_alignment_report = _project_model_test_alignment(
        definition=definition,
        evidence=evidence,
        inventory=inventory,
        binding_report=binding_report,
    )
    topology_report = review_blueprint_topology(
        topology_id=evidence.semantic_mesh_id,
        nodes=evidence.topology_nodes,
        relations=evidence.topology_relations,
        required_owner_ids=tuple(
            owner.model_element_id for owner in definition.owners
        ),
        required_surface_ids_by_owner={
            owner.model_element_id: owner.implementation_surface_ids
            for owner in definition.owners
        },
    )
    manifest = SoftwareBlueprintManifest(
        blueprint_id=definition.blueprint_id,
        observed_snapshot_id=evidence.observed_snapshot_id,
        observed_snapshot_fingerprint=evidence.observed_snapshot_fingerprint,
        inventory_id=inventory.inventory_id,
        inventory_fingerprint=inventory.inventory_fingerprint,
        binding_report_id=f"binding-report:{binding_report.fingerprint}",
        binding_report_fingerprint=binding_report.fingerprint,
        semantic_mesh_id=evidence.semantic_mesh_id,
        semantic_mesh_fingerprint=evidence.semantic_mesh_fingerprint,
        test_inventory_id=evidence.test_inventory.inventory_id,
        test_inventory_fingerprint=evidence.test_inventory.inventory_fingerprint,
        model_test_alignment_report_id=(
            f"model-test-alignment:{model_test_alignment_report.fingerprint}"
        ),
        model_test_alignment_report_fingerprint=(
            model_test_alignment_report.fingerprint
        ),
        portable_owner_fingerprints=evidence.portable_owner_fingerprints,
        resources=evidence.resources,
        oracles=tuple(oracles),
        required_resource_ids=tuple(row.resource_id for row in evidence.resources),
        required_resource_kinds=tuple(row.kind for row in evidence.resources),
        required_oracle_ids=tuple(row.oracle_id for row in oracles),
        excluded_source_ids=tuple(
            row.path for row in inventory.file_dispositions if row.category == "production"
        ),
    )
    qualification = qualify_software_blueprint(
        manifest,
        binding_report,
        implementation_inventory=inventory,
        current_observed_snapshot_fingerprint=evidence.observed_snapshot_fingerprint,
        current_semantic_mesh_fingerprint=evidence.semantic_mesh_fingerprint,
        current_test_inventory_fingerprint=evidence.test_inventory.inventory_fingerprint,
        current_model_test_alignment_report_fingerprint=(
            model_test_alignment_report.fingerprint
        ),
        current_portable_owner_fingerprints=dict(evidence.portable_owner_fingerprints),
        current_resource_fingerprints={row.resource_id: str(row.artifact_fingerprint) for row in evidence.resources},
        current_oracle_fingerprints={row.oracle_id: row.artifact_fingerprint for row in oracles},
    )
    current_intent = intent_inventory or ProjectIntentInventory(
        inventory_id=f"intent-inventory:{definition.blueprint_id}:missing",
        subject_revision=evidence.observed_snapshot_fingerprint,
        canonical_review_fingerprint=fingerprint_value(
            {"status": "missing", "blueprint_id": definition.blueprint_id}
        ),
        contributions=(),
    )
    (
        behavior_report,
        resource_inventory,
        projection,
        readiness,
        normalized_shared_objects,
    ) = _behavior_readiness(
        inventory=inventory,
        definition=definition,
        evidence=evidence,
        manifest=manifest,
        binding_report=binding_report,
        intent_inventory=current_intent,
        model_test_alignment_report=model_test_alignment_report,
        topology_report=topology_report,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints=delegated_helper_fingerprints,
    )
    target_system_report = _target_system_blueprint_report(
        definition=definition,
        evidence=evidence,
        inventory=inventory,
        binding_report=binding_report,
        model_test_alignment_report=model_test_alignment_report,
        topology_report=topology_report,
        manifest=manifest,
        qualification=qualification,
        behavior_report=behavior_report,
        resource_inventory=resource_inventory,
        intent_inventory=current_intent,
        readiness=readiness,
    )
    understanding_summary = project_blueprint_understanding(
        target_system_report,
        affected_surface_ids=tuple(sorted(behavior_surface_ids)),
    )
    return ProjectBlueprintBundle(
        inventory=inventory,
        binding_report=binding_report,
        manifest=manifest,
        qualification=qualification,
        model_test_alignment_report=model_test_alignment_report,
        topology_report=topology_report,
        behavior_report=behavior_report,
        resource_inventory=resource_inventory,
        intent_inventory=current_intent,
        normalized_projection=projection,
        static_readiness=readiness,
        target_system_report=target_system_report,
        understanding_summary=understanding_summary,
        normalized_shared_objects=normalized_shared_objects,
    )


def _exact_object(value: Any, *, fields: set[str], context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectBlueprintError(f"{context} must be a JSON object")
    missing = fields - set(value)
    unexpected = set(value) - fields
    if missing or unexpected:
        raise ProjectBlueprintError(
            f"{context} fields are not exact-current: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    return value


def _semantic_from_document(value: Any) -> SemanticSpecReference:
    fields = {
        "semantic_spec_id", "owner_id", "artifact_id", "artifact_fingerprint",
        "covered_model_element_ids", "covered_dimensions", "semantics",
        "authority_kind", "provenance_fingerprints",
    }
    row = _exact_object(value, fields=fields, context="project semantic specification")
    semantics = _exact_object(
        row["semantics"], fields=set(str(item) for item in row["covered_dimensions"]),
        context="project semantic payload",
    )
    provenance = row["provenance_fingerprints"]
    if not isinstance(provenance, Mapping):
        raise ProjectBlueprintError("semantic provenance fingerprints must be an object")
    return SemanticSpecReference(
        semantic_spec_id=str(row["semantic_spec_id"]), owner_id=str(row["owner_id"]),
        artifact_id=str(row["artifact_id"]), artifact_fingerprint=str(row["artifact_fingerprint"]),
        covered_model_element_ids=tuple(str(item) for item in row["covered_model_element_ids"]),
        covered_dimensions=tuple(str(item) for item in row["covered_dimensions"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
        authority_kind=str(row["authority_kind"]),
        provenance_fingerprints=tuple((str(key), str(item)) for key, item in provenance.items()),
    )


def _oracle_from_document(value: Any) -> OracleReference:
    fields = {
        "oracle_id", "owner_id", "artifact_id", "artifact_fingerprint",
        "covered_model_element_ids", "covered_dimensions", "semantics",
    }
    row = _exact_object(value, fields=fields, context="project oracle")
    semantics = _exact_object(
        row["semantics"], fields=set(str(item) for item in row["covered_dimensions"]),
        context="project oracle payload",
    )
    return OracleReference(
        oracle_id=str(row["oracle_id"]), owner_id=str(row["owner_id"]),
        artifact_id=str(row["artifact_id"]), artifact_fingerprint=str(row["artifact_fingerprint"]),
        covered_model_element_ids=tuple(str(item) for item in row["covered_model_element_ids"]),
        covered_dimensions=tuple(str(item) for item in row["covered_dimensions"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
    )


def _behavior_case_from_document(value: Any) -> BehaviorCaseContract:
    fields = {
        "case_id", "behavior_block_id", "case_kind", "input_values",
        "initial_state", "expected_output", "expected_state", "expected_effects",
        "expected_errors", "oracle_id", "case_evidence_id",
        "case_evidence_fingerprint", "value_mode", "protected_failure_ids",
        "parameter_case_id",
    }
    row = _exact_object(value, fields=fields, context="project behavior case")
    mapping_names = (
        "input_values", "initial_state", "expected_output", "expected_state"
    )
    if any(not isinstance(row[name], Mapping) for name in mapping_names):
        raise ProjectBlueprintError("project behavior case value fields must be objects")
    return BehaviorCaseContract(
        case_id=str(row["case_id"]),
        behavior_block_id=str(row["behavior_block_id"]),
        case_kind=str(row["case_kind"]),
        input_values=tuple((str(key), str(item)) for key, item in row["input_values"].items()),
        initial_state=tuple((str(key), str(item)) for key, item in row["initial_state"].items()),
        expected_output=tuple((str(key), str(item)) for key, item in row["expected_output"].items()),
        expected_state=tuple((str(key), str(item)) for key, item in row["expected_state"].items()),
        expected_effects=tuple(str(item) for item in row["expected_effects"]),
        expected_errors=tuple(str(item) for item in row["expected_errors"]),
        oracle_id=str(row["oracle_id"]),
        case_evidence_id=str(row["case_evidence_id"]),
        case_evidence_fingerprint=str(row["case_evidence_fingerprint"]),
        value_mode=str(row["value_mode"]),
        protected_failure_ids=tuple(str(item) for item in row["protected_failure_ids"]),
        parameter_case_id=str(row["parameter_case_id"]),
    )


def _resource_from_document(value: Any) -> BlueprintResourceReference:
    fields = {
        "resource_id", "kind", "owner_id", "artifact_id", "purpose",
        "lifecycle_role", "disposition", "artifact_fingerprint", "rationale",
        "semantics",
    }
    row = _exact_object(value, fields=fields, context="project resource")
    semantics = row["semantics"]
    if not isinstance(semantics, Mapping):
        raise ProjectBlueprintError("project resource semantics must be an object")
    return BlueprintResourceReference(
        resource_id=str(row["resource_id"]), kind=str(row["kind"]),
        owner_id=str(row["owner_id"]), artifact_id=str(row["artifact_id"]),
        purpose=str(row["purpose"]), lifecycle_role=str(row["lifecycle_role"]),
        disposition=str(row["disposition"]),
        artifact_fingerprint=(None if row["artifact_fingerprint"] is None else str(row["artifact_fingerprint"])),
        rationale=None if row["rationale"] is None else str(row["rationale"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
    )


def _evidence_artifact_from_document(value: Any) -> ProjectEvidenceArtifact:
    fields = {"evidence_id", "artifact_path", "artifact_fingerprint", "kind"}
    row = _exact_object(value, fields=fields, context="project evidence artifact")
    return ProjectEvidenceArtifact(
        evidence_id=str(row["evidence_id"]),
        artifact_path=str(row["artifact_path"]),
        artifact_fingerprint=str(row["artifact_fingerprint"]),
        kind=str(row["kind"]),
    )


def _topology_node_from_document(value: Any) -> BlueprintTopologyNode:
    fields = {"node_id", "disposition", "purpose", "implementation_surface_ids"}
    row = _exact_object(value, fields=fields, context="blueprint topology node")
    return BlueprintTopologyNode(
        node_id=str(row["node_id"]),
        disposition=str(row["disposition"]),
        purpose=str(row["purpose"]),
        implementation_surface_ids=tuple(
            str(item) for item in row["implementation_surface_ids"]
        ),
    )


def _portable_catalog_from_document(value: Any) -> PortableModelMemberCatalog:
    fields = {
        "portable_model_id", "portable_model_fingerprint", "transition_ids",
        "property_ids", "invariant_ids", "input_field_ids", "output_field_ids",
        "state_field_ids", "assumption_ids", "guarantee_ids",
    }
    row = _exact_object(value, fields=fields, context="portable member catalog")
    return PortableModelMemberCatalog(
        portable_model_id=str(row["portable_model_id"]),
        portable_model_fingerprint=str(row["portable_model_fingerprint"]),
        transition_ids=tuple(str(item) for item in row["transition_ids"]),
        property_ids=tuple(str(item) for item in row["property_ids"]),
        invariant_ids=tuple(str(item) for item in row["invariant_ids"]),
        input_field_ids=tuple(str(item) for item in row["input_field_ids"]),
        output_field_ids=tuple(str(item) for item in row["output_field_ids"]),
        state_field_ids=tuple(str(item) for item in row["state_field_ids"]),
        assumption_ids=tuple(str(item) for item in row["assumption_ids"]),
        guarantee_ids=tuple(str(item) for item in row["guarantee_ids"]),
    )


def _topology_relation_from_document(value: Any) -> BlueprintTopologyRelation:
    fields = {
        "relation_id", "producer_id", "consumer_id", "relation_kind",
        "interface_mappings", "evidence_fingerprint", "rationale",
    }
    row = _exact_object(value, fields=fields, context="blueprint topology relation")
    mappings: list[tuple[str, str]] = []
    for raw_mapping in row["interface_mappings"]:
        mapping = _exact_object(
            raw_mapping,
            fields={"producer_output_id", "consumer_input_id"},
            context="blueprint topology interface mapping",
        )
        mappings.append(
            (
                str(mapping["producer_output_id"]),
                str(mapping["consumer_input_id"]),
            )
        )
    return BlueprintTopologyRelation(
        relation_id=str(row["relation_id"]),
        producer_id=str(row["producer_id"]),
        consumer_id=str(row["consumer_id"]),
        relation_kind=str(row["relation_kind"]),
        interface_mappings=tuple(mappings),
        evidence_fingerprint=str(row["evidence_fingerprint"]),
        rationale=str(row["rationale"]),
    )


def load_project_blueprint_document(
    path: str | Path,
) -> tuple[ProjectBlueprintDefinition, ProjectBlueprintEvidence]:
    """Load one strict current project-blueprint JSON document for CLI adapters."""

    document_path = Path(path)
    try:
        value = json.loads(document_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectBlueprintError(f"cannot load {document_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectBlueprintError("project blueprint document must be a JSON object")
    if value.get("schema_version") != PROJECT_BLUEPRINT_DEFINITION_SCHEMA:
        raise ProjectBlueprintError("project blueprint document schema is not current")
    fields = {
        "schema_version", "target_kind", "observation_providers",
        "authority_providers", "blueprint_id", "inventory_id", "boundary",
        "file_dispositions", "surface_dispositions", "supporting_owners",
        "dynamic_allowances", "owners", "evidence", "claim_boundary",
    }
    row = _exact_object(value, fields=fields, context="project blueprint document")
    owners: list[ProjectBlueprintOwner] = []
    owner_fields = {
        "model_element_id", "owner_id", "owner_contract_id", "model_fingerprint",
        "owner_contract_fingerprint", "portable_model_id",
        "portable_model_fingerprint", "portable_transition_ids",
        "portable_property_ids", "portable_invariant_ids",
        "portable_input_field_mappings", "portable_output_field_mappings",
        "portable_state_field_mappings", "portable_assumption_ids",
        "portable_guarantee_ids", "protected_failure_ids",
        "implementation_surface_ids", "primary_surface_id",
        "semantic_specs", "oracles", "test_evidence_fingerprints",
        "native_evidence_fingerprints", "behavior_accepted",
        "behavior_acceptance_evidence_fingerprints",
        "behavior_case_contracts", "checker_design_fingerprints",
    }
    for raw_owner in row["owners"]:
        owner = _exact_object(raw_owner, fields=owner_fields, context="project blueprint owner")
        tests = owner["test_evidence_fingerprints"]
        if not isinstance(tests, Mapping):
            raise ProjectBlueprintError("test evidence fingerprints must be an object")
        native_evidence = owner["native_evidence_fingerprints"]
        if not isinstance(native_evidence, Mapping):
            raise ProjectBlueprintError("native evidence fingerprints must be an object")
        checker_designs = owner["checker_design_fingerprints"]
        if not isinstance(checker_designs, Mapping):
            raise ProjectBlueprintError("checker design fingerprints must be an object")
        portable_mapping_names = (
            "portable_input_field_mappings",
            "portable_output_field_mappings",
            "portable_state_field_mappings",
            "behavior_acceptance_evidence_fingerprints",
        )
        if any(not isinstance(owner[name], Mapping) for name in portable_mapping_names):
            raise ProjectBlueprintError(
                "portable field mappings and acceptance evidence must be objects"
            )
        owners.append(ProjectBlueprintOwner(
            model_element_id=str(owner["model_element_id"]), owner_id=str(owner["owner_id"]),
            owner_contract_id=str(owner["owner_contract_id"]),
            model_fingerprint=str(owner["model_fingerprint"]),
            owner_contract_fingerprint=str(owner["owner_contract_fingerprint"]),
            portable_model_id=str(owner["portable_model_id"]),
            portable_model_fingerprint=str(owner["portable_model_fingerprint"]),
            portable_transition_ids=tuple(str(item) for item in owner["portable_transition_ids"]),
            portable_property_ids=tuple(str(item) for item in owner["portable_property_ids"]),
            portable_invariant_ids=tuple(str(item) for item in owner["portable_invariant_ids"]),
            portable_input_field_mappings=tuple(
                (str(key), str(item)) for key, item in owner["portable_input_field_mappings"].items()
            ),
            portable_output_field_mappings=tuple(
                (str(key), str(item)) for key, item in owner["portable_output_field_mappings"].items()
            ),
            portable_state_field_mappings=tuple(
                (str(key), str(item)) for key, item in owner["portable_state_field_mappings"].items()
            ),
            portable_assumption_ids=tuple(str(item) for item in owner["portable_assumption_ids"]),
            portable_guarantee_ids=tuple(str(item) for item in owner["portable_guarantee_ids"]),
            protected_failure_ids=tuple(
                str(item) for item in owner["protected_failure_ids"]
            ),
            implementation_surface_ids=tuple(str(item) for item in owner["implementation_surface_ids"]),
            primary_surface_id=str(owner["primary_surface_id"]),
            semantic_specs=tuple(_semantic_from_document(item) for item in owner["semantic_specs"]),
            oracles=tuple(_oracle_from_document(item) for item in owner["oracles"]),
            test_evidence_fingerprints=tuple((str(key), str(item)) for key, item in tests.items()),
            native_evidence_fingerprints=tuple(
                (str(key), str(item)) for key, item in native_evidence.items()
            ),
            behavior_accepted=bool(owner["behavior_accepted"]),
            behavior_acceptance_evidence_fingerprints=tuple(
                (str(key), str(item))
                for key, item in owner["behavior_acceptance_evidence_fingerprints"].items()
            ),
            behavior_case_contracts=tuple(
                _behavior_case_from_document(item)
                for item in owner["behavior_case_contracts"]
            ),
            checker_design_fingerprints=tuple(
                (str(key), str(item)) for key, item in checker_designs.items()
            ),
        ))
    for mapping_name in (
        "surface_dispositions",
        "supporting_owners",
        "dynamic_allowances",
        "observation_providers",
        "authority_providers",
    ):
        if not isinstance(row[mapping_name], Mapping):
            raise ProjectBlueprintError(f"{mapping_name} must be an object")
    definition = ProjectBlueprintDefinition(
        blueprint_id=str(row["blueprint_id"]), inventory_id=str(row["inventory_id"]),
        boundary=SoftwareBoundary.from_dict(row["boundary"]),
        file_dispositions=tuple(ImplementationFileDisposition.from_dict(item) for item in row["file_dispositions"]),
        surface_dispositions=tuple((str(key), str(item)) for key, item in row["surface_dispositions"].items()),
        supporting_owners=tuple((str(key), str(item)) for key, item in row["supporting_owners"].items()),
        dynamic_allowances=tuple((str(key), tuple(str(value) for value in item)) for key, item in row["dynamic_allowances"].items()),
        owners=tuple(owners),
        claim_boundary=str(row["claim_boundary"]),
        target_kind=str(row["target_kind"]),
        observation_providers=tuple(
            (str(key), tuple(str(value) for value in item))
            for key, item in row["observation_providers"].items()
        ),
        authority_providers=tuple(
            (str(key), tuple(str(value) for value in item))
            for key, item in row["authority_providers"].items()
        ),
    )
    evidence_fields = {
        "observed_snapshot_id", "observed_snapshot_fingerprint", "semantic_mesh_id",
        "semantic_mesh_fingerprint", "portable_owner_fingerprints",
        "portable_member_catalogs", "resources",
        "test_inventory", "topology_nodes", "topology_relations",
        "native_evidence_artifacts",
    }
    raw_evidence = _exact_object(row["evidence"], fields=evidence_fields, context="project blueprint evidence")
    portable = raw_evidence["portable_owner_fingerprints"]
    if not isinstance(portable, Mapping):
        raise ProjectBlueprintError("portable owner fingerprints must be an object")
    evidence = ProjectBlueprintEvidence(
        observed_snapshot_id=str(raw_evidence["observed_snapshot_id"]),
        observed_snapshot_fingerprint=str(raw_evidence["observed_snapshot_fingerprint"]),
        semantic_mesh_id=str(raw_evidence["semantic_mesh_id"]),
        semantic_mesh_fingerprint=str(raw_evidence["semantic_mesh_fingerprint"]),
        portable_owner_fingerprints=tuple((str(key), str(item)) for key, item in portable.items()),
        portable_member_catalogs=tuple(
            _portable_catalog_from_document(item)
            for item in raw_evidence["portable_member_catalogs"]
        ),
        resources=tuple(_resource_from_document(item) for item in raw_evidence["resources"]),
        test_inventory=ProjectTestInventory.from_dict(raw_evidence["test_inventory"]),
        topology_nodes=tuple(
            _topology_node_from_document(item)
            for item in raw_evidence["topology_nodes"]
        ),
        topology_relations=tuple(
            _topology_relation_from_document(item)
            for item in raw_evidence["topology_relations"]
        ),
        native_evidence_artifacts=tuple(
            _evidence_artifact_from_document(item)
            for item in raw_evidence["native_evidence_artifacts"]
        ),
    )
    return definition, evidence


__all__ = [
    "PROJECT_BLUEPRINT_DEFINITION_SCHEMA",
    "ProjectBlueprintBundle",
    "ProjectBlueprintDefinition",
    "ProjectBlueprintError",
    "ProjectBlueprintEvidence",
    "ProjectEvidenceArtifact",
    "PortableModelMemberCatalog",
    "ProjectBlueprintOwner",
    "build_project_blueprint",
    "load_project_blueprint_document",
    "project_blueprint_document",
    "project_surface_dimensions",
]
