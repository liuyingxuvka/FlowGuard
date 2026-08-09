"""FlowGuard's current self-blueprint composition.

The generic inventory and blueprint modules remain project-neutral.  This
module binds those owners to FlowGuard's checked-in declarative boundary,
model-regression purpose closures, semantic mesh, and test oracles.  It is a
derived view of the observed model system, never a second authority pointer.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from functools import cached_property
import json
from pathlib import Path
import tomllib
from typing import Any, Mapping, Sequence

from .affected_blueprint_reader import (
    AffectedBlueprintReadResult,
    read_affected_blueprint,
)
from .evidence_receipts import fingerprint_value
from .blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyPort,
    BlueprintTopologyPortMapping,
    BlueprintTopologyProgressContract,
    BlueprintTopologyRelation,
    BlueprintTopologyReport,
    TOPOLOGY_ROOT_SENTINEL,
)
from .hierarchy import (
    EVIDENCE_CONFORMANCE_GREEN,
    ChildModelEvidence,
    ChildReattachmentContract,
)
from .implementation_blueprint import (
    BlueprintResourceReference,
    ModelImplementationBindingReport,
    OracleReference,
    SemanticSpecReference,
    SEMANTIC_AUTHORITY_IMPORTED_MODEL,
    SoftwareBlueprintManifest,
    BlueprintManifestQualificationReport,
)
from .implementation_inventory import (
    DynamicSelectorContract,
    IMPLEMENTATION_DISPOSITION_MODEL,
    IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
    IMPLEMENTATION_DISPOSITION_SUPPORTING,
    ImplementationFileDisposition,
    ImplementationDiscoveryResult,
    ImplementationInventoryAuditReport,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    build_implementation_surface_inventory,
    implementation_behavior_surface_ids,
    implementation_surface_key,
)
from .implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
    derive_static_dynamic_selector_contracts,
    discover_python_implementation_surfaces,
    project_python_implementation_observation,
)
from .model_revision_set import ModelRevisionSet
from .model_authority import REVISION_ACCEPTED
from .model_authority_store import (
    ModelAuthorityAuditReport,
    audit_model_authority,
)
from .model_test_alignment import ModelTestAlignmentReport
from .model_regressions import (
    CurrentModelRegressionParentEvidence,
    ModelRegressionEvidenceError,
    resolve_current_full_model_regression_parent,
)
from .source_identity import source_file_fingerprint
from .test_inventory import (
    TEST_DISPOSITION_REQUIRED,
    TEST_DISPOSITION_SUPPORTING,
    ProjectTestInventory,
    TestFileDisposition,
    TestNodeDisposition,
    build_project_test_inventory,
    review_project_test_inventory,
)
from .test_inventory_python import (
    PYTHON_AST_TEST_ADAPTER_ID,
    discover_python_test_file,
)
from .project_blueprint import (
    ProjectBlueprintDefinition,
    ProjectBlueprintEvidence,
    ProjectBlueprintOwner,
    ProjectEvidenceArtifact,
    PortableModelMemberCatalog,
    collect_project_blueprint_provider_results,
    derive_project_blueprint_readiness_ledger,
    freeze_project_blueprint_evidence,
    prepare_project_blueprint,
    project_surface_dimensions,
    _qualify_project_blueprint,
)
from .software_blueprint_readiness import (
    BEHAVIOR_CASE_DIMENSIONS,
    BEHAVIOR_DIMENSIONS,
    BehaviorBlueprintReport,
    BehaviorCaseContract,
    DelegatedAssertionHelper,
    IntentSourceAuthority,
    NormalizedBlueprintProjection,
    ObservedResourceMember,
    PortableBehaviorBinding,
    ProjectIntentContribution,
    ProjectIntentInventory,
    ProjectResourceInventory,
    StaticBlueprintReadinessReport,
)
from .target_system_blueprint import (
    BlueprintGapRef,
    BlueprintReadinessLedger,
    BlueprintUnderstandingSummary,
    ModelPathQualityBlueprintBinding,
    SOFTWARE_TARGET_PROFILE,
    TargetSystemBlueprintReport,
    TargetSystemProviderDeclaration,
)
from .validation_ownership import (
    filter_resolved_input_manifest,
    resolve_input_manifest,
)


SELF_BLUEPRINT_DEFINITION_SCHEMA = "flowguard.self_blueprint_definition.v5"
SELF_BLUEPRINT_BUILD_INPUT_IDENTITY_SCHEMA = (
    "flowguard.self_blueprint_build_input_identity.v2"
)
DEFAULT_SELF_BLUEPRINT_DEFINITION = (
    ".flowguard/authoritative_model_system/software_blueprint_definition.json"
)


class FlowGuardSelfBlueprintError(ValueError):
    """Raised when the checked-in self-blueprint definition cannot close."""


@dataclass(frozen=True)
class _ProviderDeclaredCompositeBehaviorContract:
    """One explicit, current provider contract for an owner-level behavior."""

    owner_id: str
    surface_key: str
    input_contract_id: str
    state_contract_id: str
    effect_contract_id: str
    output_contract_id: str
    completion_contract_id: str
    semantic_contract_id: str
    purpose_source_id: str
    purpose_source_owner_id: str
    model_path: str
    model_source_fingerprint: str
    runner_path: str
    runner_source_fingerprint: str
    purpose_declaration_fingerprint: str
    purpose_closure_fingerprint: str

    @classmethod
    def from_definition(
        cls,
        value: Any,
    ) -> "_ProviderDeclaredCompositeBehaviorContract":
        if not isinstance(value, Mapping):
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract must be an object"
            )
        required = {"owner_id", "surface_key", "contracts", "source_identity"}
        if set(value) != required:
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract fields are not exact-current"
            )
        contracts = value.get("contracts")
        if not isinstance(contracts, Mapping) or set(contracts) != {
            "input",
            "state",
            "effect",
            "output",
            "completion",
            "semantics",
        }:
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract dimensions are incomplete"
            )
        source = value.get("source_identity")
        if not isinstance(source, Mapping) or set(source) != {
            "purpose_source_id",
            "purpose_source_owner_id",
            "model_path",
            "model_source_fingerprint",
            "runner_path",
            "runner_source_fingerprint",
            "purpose_declaration_fingerprint",
            "purpose_closure_fingerprint",
        }:
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract source identity is incomplete"
            )
        raw_identity_values = (
            value.get("owner_id"),
            value.get("surface_key"),
            *(contracts.get(name) for name in (
                "input",
                "state",
                "effect",
                "output",
                "completion",
                "semantics",
            )),
            *(source.get(name) for name in (
                "purpose_source_id",
                "purpose_source_owner_id",
                "model_path",
                "model_source_fingerprint",
                "runner_path",
                "runner_source_fingerprint",
                "purpose_declaration_fingerprint",
                "purpose_closure_fingerprint",
            )),
        )
        if any(
            not isinstance(item, str) or not item.strip()
            for item in raw_identity_values
        ):
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract identity is incomplete"
            )
        contract = cls(
            owner_id=str(value.get("owner_id", "")).strip(),
            surface_key=str(value.get("surface_key", "")).strip(),
            input_contract_id=str(contracts.get("input", "")).strip(),
            state_contract_id=str(contracts.get("state", "")).strip(),
            effect_contract_id=str(contracts.get("effect", "")).strip(),
            output_contract_id=str(contracts.get("output", "")).strip(),
            completion_contract_id=str(contracts.get("completion", "")).strip(),
            semantic_contract_id=str(contracts.get("semantics", "")).strip(),
            purpose_source_id=str(source.get("purpose_source_id", "")).strip(),
            purpose_source_owner_id=str(
                source.get("purpose_source_owner_id", "")
            ).strip(),
            model_path=str(source.get("model_path", "")).replace("\\", "/").strip(),
            model_source_fingerprint=str(
                source.get("model_source_fingerprint", "")
            ).strip(),
            runner_path=str(source.get("runner_path", "")).replace("\\", "/").strip(),
            runner_source_fingerprint=str(
                source.get("runner_source_fingerprint", "")
            ).strip(),
            purpose_declaration_fingerprint=str(
                source.get("purpose_declaration_fingerprint", "")
            ).strip(),
            purpose_closure_fingerprint=str(
                source.get("purpose_closure_fingerprint", "")
            ).strip(),
        )
        dimension_ids = (
            contract.input_contract_id,
            contract.state_contract_id,
            contract.effect_contract_id,
            contract.output_contract_id,
            contract.completion_contract_id,
            contract.semantic_contract_id,
        )
        if len(set(dimension_ids)) != len(dimension_ids):
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract dimensions require independent identities"
            )
        if "#" not in contract.surface_key:
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract requires an exact surface_key"
            )
        return contract

    @cached_property
    def source_identity_fingerprint(self) -> str:
        return fingerprint_value(
            {
                "purpose_source_id": self.purpose_source_id,
                "purpose_source_owner_id": self.purpose_source_owner_id,
                "model_path": self.model_path,
                "model_source_fingerprint": self.model_source_fingerprint,
                "runner_path": self.runner_path,
                "runner_source_fingerprint": self.runner_source_fingerprint,
                "purpose_declaration_fingerprint": (
                    self.purpose_declaration_fingerprint
                ),
                "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
            }
        )

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(
            {
                "owner_id": self.owner_id,
                "surface_key": self.surface_key,
                "contracts": {
                    "input": self.input_contract_id,
                    "state": self.state_contract_id,
                    "effect": self.effect_contract_id,
                    "output": self.output_contract_id,
                    "completion": self.completion_contract_id,
                    "semantics": self.semantic_contract_id,
                },
                "source_identity_fingerprint": self.source_identity_fingerprint,
            }
        )


@dataclass(frozen=True)
class SelfBlueprintBuildInputIdentity:
    """Small exact identity for every input consumed by the self builder."""

    subject_revision: str
    model_authority_audit_fingerprint: str
    observed_snapshot_fingerprint: str
    accepted_revision_set_fingerprint: str
    definition_fingerprint: str
    boundary_fingerprint: str
    file_inventory_fingerprint: str
    file_count: int
    semantic_mesh_fingerprint: str
    activation_receipt_fingerprint: str
    model_regression_evidence_fingerprint: str
    provider_contract_fingerprint: str

    def __post_init__(self) -> None:
        for field_name in (
            "subject_revision",
            "model_authority_audit_fingerprint",
            "observed_snapshot_fingerprint",
            "accepted_revision_set_fingerprint",
            "definition_fingerprint",
            "boundary_fingerprint",
            "file_inventory_fingerprint",
            "semantic_mesh_fingerprint",
            "activation_receipt_fingerprint",
            "model_regression_evidence_fingerprint",
            "provider_contract_fingerprint",
        ):
            if not str(getattr(self, field_name, "")):
                raise FlowGuardSelfBlueprintError(
                    f"self-blueprint build input identity omits {field_name}"
                )
        if self.file_count < 1:
            raise FlowGuardSelfBlueprintError(
                "self-blueprint build input identity has no files"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_BLUEPRINT_BUILD_INPUT_IDENTITY_SCHEMA,
            "subject_revision": self.subject_revision,
            "model_authority_audit_fingerprint": (
                self.model_authority_audit_fingerprint
            ),
            "observed_snapshot_fingerprint": self.observed_snapshot_fingerprint,
            "accepted_revision_set_fingerprint": (
                self.accepted_revision_set_fingerprint
            ),
            "definition_fingerprint": self.definition_fingerprint,
            "boundary_fingerprint": self.boundary_fingerprint,
            "file_inventory_fingerprint": self.file_inventory_fingerprint,
            "file_count": self.file_count,
            "semantic_mesh_fingerprint": self.semantic_mesh_fingerprint,
            "activation_receipt_fingerprint": (
                self.activation_receipt_fingerprint
            ),
            "model_regression_evidence_fingerprint": (
                self.model_regression_evidence_fingerprint
            ),
            "provider_contract_fingerprint": self.provider_contract_fingerprint,
        }

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())


@dataclass(frozen=True)
class FlowGuardSelfBlueprintBundle:
    test_inventory: ProjectTestInventory
    inventory: ImplementationSurfaceInventory
    implementation_inventory_audit: ImplementationInventoryAuditReport
    binding_report: ModelImplementationBindingReport
    manifest: SoftwareBlueprintManifest
    qualification: BlueprintManifestQualificationReport
    model_test_alignment_report: ModelTestAlignmentReport
    topology_report: BlueprintTopologyReport
    behavior_report: BehaviorBlueprintReport
    resource_inventory: ProjectResourceInventory
    intent_inventory: ProjectIntentInventory
    normalized_projection: NormalizedBlueprintProjection
    static_readiness: StaticBlueprintReadinessReport
    target_system_report: TargetSystemBlueprintReport
    understanding_summary: BlueprintUnderstandingSummary
    normalized_shared_objects: tuple[tuple[str, Any], ...]
    normalized_shards: tuple[tuple[str, Any], ...] = ()
    build_input_identity: SelfBlueprintBuildInputIdentity | None = None
    # Keep the exact project bundle used to build this self view so the
    # existing canonical portable exporter can materialize one current self
    # DNA without rebuilding a second, weaker projection.
    project_bundle: Any | None = None

    @cached_property
    def readiness_ledger(self) -> BlueprintReadinessLedger:
        return derive_project_blueprint_readiness_ledger(self)

    @property
    def ok(self) -> bool:
        return self.readiness_ledger.ok

    @property
    def deepest_proven_layer(self) -> str:
        return self.readiness_ledger.deepest_proven_layer

    @property
    def first_gap(self) -> BlueprintGapRef | None:
        return self.readiness_ledger.first_gap

    @property
    def gap_count(self) -> int:
        return self.readiness_ledger.gap_count

    @property
    def implementation_admitted(self) -> bool:
        return self.readiness_ledger.implementation_admitted

    def affected_neighborhood(
        self,
        *,
        affected_surface_ids: Sequence[str] = (),
        affected_behavior_block_ids: Sequence[str] = (),
    ) -> AffectedBlueprintReadResult:
        affected_ids = tuple(
            sorted(
                {
                    *(str(item) for item in affected_surface_ids if str(item)),
                    *(
                        str(item)
                        for item in affected_behavior_block_ids
                        if str(item)
                    ),
                }
            )
        )
        return read_affected_blueprint(
            self.normalized_projection,
            affected_ids=affected_ids,
            load_shard=dict(self.normalized_shards).__getitem__,
            load_object=dict(self.normalized_shared_objects).__getitem__,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "inventory_fingerprint": self.inventory.inventory_fingerprint,
            "implementation_inventory_audit_fingerprint": (
                self.implementation_inventory_audit.fingerprint
            ),
            "test_inventory_fingerprint": self.test_inventory.inventory_fingerprint,
            "binding_report_fingerprint": self.binding_report.fingerprint,
            "blueprint_fingerprint": self.manifest.fingerprint,
            "qualification": self.qualification.to_dict(),
            "model_test_alignment_report_fingerprint": (
                self.model_test_alignment_report.fingerprint
            ),
            "topology_report_fingerprint": self.topology_report.fingerprint,
            "behavior_report_fingerprint": self.behavior_report.fingerprint,
            "resource_inventory_fingerprint": self.resource_inventory.fingerprint,
            "intent_inventory_fingerprint": self.intent_inventory.fingerprint,
            "normalized_projection_fingerprint": self.normalized_projection.fingerprint,
            "build_input_identity": (
                self.build_input_identity.to_dict()
                if self.build_input_identity is not None
                else None
            ),
            "static_readiness": self.static_readiness.to_dict(),
            "target_system_report": self.target_system_report.to_dict(),
            "understanding_summary": self.understanding_summary.to_dict(),
            "readiness_ledger": self.readiness_ledger.to_dict(),
            "counts": {
                "files": len(self.inventory.file_dispositions),
                "implementation_surfaces": len(self.inventory.surfaces),
                "test_nodes": len(self.test_inventory.nodes),
                "bindings": len(self.binding_report.bindings),
                "semantic_specs": len(self.binding_report.semantic_specs),
                "oracles": len(self.binding_report.oracles),
                "resources": len(self.manifest.resources),
                "behavior_blocks": len(self.behavior_report.contracts),
                "behavior_coverage_edges": len(
                    self.behavior_report.coverage_edges
                ),
                "normalized_shared_objects": len(self.normalized_shared_objects),
                "test_node_dispositions": len(
                    self.behavior_report.test_node_dispositions
                ),
            },
        }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowGuardSelfBlueprintError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FlowGuardSelfBlueprintError(f"{path} must contain a JSON object")
    return value


def load_flowguard_self_blueprint_definition(
    root: str | Path,
    *,
    relative_path: str = DEFAULT_SELF_BLUEPRINT_DEFINITION,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    path = (root_path / relative_path).resolve()
    try:
        path.relative_to(root_path)
    except ValueError as exc:
        raise FlowGuardSelfBlueprintError("self-blueprint definition escapes root") from exc
    value = _load_json_object(path)
    if value.get("schema_version") != SELF_BLUEPRINT_DEFINITION_SCHEMA:
        raise FlowGuardSelfBlueprintError("self-blueprint definition schema is not current")
    required = {
        "schema_version",
        "blueprint_id",
        "inventory_id",
        "boundary",
        "scan_python_patterns",
        "scoped_out_patterns",
        "bounded_dynamic_prefixes",
        "dynamic_allowances",
        "dynamic_selector_contracts",
        "composite_behavior_contracts",
        "owner_overrides",
        "resource_groups",
        "claim_boundary",
    }
    if set(value) != required:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint definition fields are not exact-current"
        )
    if value["dynamic_selector_contracts"] != []:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint v5 derives finite dynamic selector contracts from "
            "current provider observations; authored contract rows are forbidden"
        )
    return value


def _pattern_paths(
    manifest: Sequence[Mapping[str, str]],
    patterns: Sequence[str],
) -> set[str]:
    return {
        row["path"]
        for row in filter_resolved_input_manifest(manifest, tuple(patterns))
    }


def _boundary_from_definition(
    root: Path,
    definition: Mapping[str, Any],
    *,
    subject_revision: str,
    resolved_manifest: Sequence[Mapping[str, str]] | None = None,
) -> tuple[SoftwareBoundary, dict[str, str]]:
    manifest = tuple(
        resolved_manifest
        if resolved_manifest is not None
        else resolve_input_manifest(root, ("**/*", "*"))
    )
    raw = definition["boundary"]
    if not isinstance(raw, Mapping):
        raise FlowGuardSelfBlueprintError("boundary definition must be an object")
    group_names = (
        "production",
        "build",
        "config",
        "schema",
        "data",
        "asset",
        "migration",
        "test_oracle",
        "generated",
        "external",
    )
    pattern_groups = {
        name: tuple(str(item) for item in raw.get(f"{name}_patterns", ()))
        for name in group_names
    }
    boundary = SoftwareBoundary(
        boundary_id=str(raw["boundary_id"]),
        subject_revision=subject_revision,
        **{f"{name}_patterns": patterns for name, patterns in pattern_groups.items()},
    )
    categories: dict[str, str] = {}
    for name, patterns in pattern_groups.items():
        for path in _pattern_paths(manifest, patterns):
            if path in categories:
                raise FlowGuardSelfBlueprintError(
                    f"self-blueprint boundary category overlap: {path}"
                )
            categories[path] = name
    return boundary, categories


def _file_dispositions(
    root: Path,
    definition: Mapping[str, Any],
    categories: Mapping[str, str],
    *,
    resolved_manifest: Sequence[Mapping[str, str]] | None = None,
) -> tuple[ImplementationFileDisposition, ...]:
    manifest = tuple(
        resolved_manifest
        if resolved_manifest is not None
        else resolve_input_manifest(root, ("**/*", "*"))
    )
    scan_paths = _pattern_paths(
        manifest,
        tuple(definition["scan_python_patterns"]),
    )
    scoped_paths = _pattern_paths(
        manifest,
        tuple(definition["scoped_out_patterns"]),
    )
    rows: list[ImplementationFileDisposition] = []
    discovery_not_applicable_by_category = {
        "asset": (
            "non_executable_resource",
            "asset files are blueprint-owned resources and expose no internal code members",
        ),
        "build": (
            "declarative_no_internal_members",
            "non-Python build declarations expose no internal code members",
        ),
        "config": (
            "declarative_no_internal_members",
            "configuration declarations expose no internal code members",
        ),
        "data": (
            "non_executable_resource",
            "data files are blueprint-owned resources and expose no internal code members",
        ),
        "migration": (
            "declarative_no_internal_members",
            "current migration declarations expose no internal code members",
        ),
        "schema": (
            "declarative_no_internal_members",
            "schema declarations expose no internal code members",
        ),
        "test_oracle": (
            "independent_test_oracle_surface",
            "test-oracle files remain in the test DNA and are covered by the independent test inventory/provider",
        ),
    }
    for item in manifest:
        path = item["path"]
        category = categories.get(path, "")
        if not category:
            raise FlowGuardSelfBlueprintError(f"unclassified self-blueprint file: {path}")
        if path in scoped_paths:
            disposition = IMPLEMENTATION_DISPOSITION_SCOPED_OUT
            reason = "historical or superseded material is outside current blueprint authority"
        elif path in scan_paths:
            disposition = IMPLEMENTATION_DISPOSITION_MODEL
            reason = "current executable implementation is discovered and model-bound"
        else:
            disposition = IMPLEMENTATION_DISPOSITION_SUPPORTING
            reason = "current non-executable resource is owned by the blueprint"
        discovery_not_applicable_kind = ""
        discovery_not_applicable_reason = ""
        if disposition == IMPLEMENTATION_DISPOSITION_SUPPORTING:
            (
                discovery_not_applicable_kind,
                discovery_not_applicable_reason,
            ) = discovery_not_applicable_by_category.get(category, ("", ""))
        rows.append(
            ImplementationFileDisposition(
                path=path,
                category=category,
                content_fingerprint=item["sha256"],
                disposition=disposition,
                reason=reason,
                requires_adapter=path in scan_paths,
                adapter_id=(PYTHON_AST_IMPLEMENTATION_ADAPTER_ID if path in scan_paths else ""),
                discovery_not_applicable_kind=discovery_not_applicable_kind,
                discovery_not_applicable_reason=discovery_not_applicable_reason,
            )
        )
    return tuple(rows)


def _discover_surface_declarations(
    root: Path,
    files: Sequence[ImplementationFileDisposition],
    definition: Mapping[str, Any],
    entries: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, str],
    composite_contracts: Mapping[
        str, _ProviderDeclaredCompositeBehaviorContract
    ],
) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, tuple[str, ...]],
    tuple[DynamicSelectorContract, ...],
    dict[str, ImplementationDiscoveryResult],
]:
    discovered: list[ImplementationSurface] = []
    observations: dict[str, ImplementationDiscoveryResult] = {}
    for item in files:
        if not item.requires_adapter:
            continue
        result = discover_python_implementation_surfaces(
            root=root,
            file_disposition=item,
            surface_dispositions={},
        )
        observations[item.path] = result
        discovered.extend(result.surfaces)
    dispositions = {
        implementation_surface_key(surface.path, surface.symbol): (
            _self_surface_disposition(surface)
        )
        for surface in discovered
    }
    grouped: dict[str, list[ImplementationSurface]] = {}
    for surface in discovered:
        owner = _exact_owner_for_path(
            surface.path,
            entries=entries,
            overrides=overrides,
        )
        grouped.setdefault(owner, []).append(surface)
    supporting_owners: dict[str, str] = {}
    for owner, owner_surfaces in sorted(grouped.items()):
        contract = composite_contracts.get(owner)
        if contract is None:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner lacks an explicit composite contract: {owner}"
            )
        composite_surface = _exact_owner_composite_surface(
            owner,
            owner_surfaces,
            contract,
        )
        dispositions[
            implementation_surface_key(
                composite_surface.path,
                composite_surface.symbol,
            )
        ] = IMPLEMENTATION_DISPOSITION_MODEL
        behavior_surfaces = tuple(
            surface
            for surface in owner_surfaces
            if dispositions[
                implementation_surface_key(surface.path, surface.symbol)
            ]
            == IMPLEMENTATION_DISPOSITION_MODEL
        )
        if not behavior_surfaces:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner has no observed behavior surface: {owner}"
            )
        for surface in owner_surfaces:
            key = implementation_surface_key(surface.path, surface.symbol)
            if dispositions[key] == IMPLEMENTATION_DISPOSITION_SUPPORTING:
                supporting_owners[key] = composite_surface.surface_id
    bounded_prefixes = tuple(str(item) for item in definition["bounded_dynamic_prefixes"])
    exact_rows: dict[str, set[str]] = {}
    for row in definition["dynamic_allowances"]:
        if not isinstance(row, Mapping) or not row.get("rationale"):
            raise FlowGuardSelfBlueprintError(
                "every exact dynamic allowance requires a surface key and rationale"
            )
        exact_rows.setdefault(str(row["surface_key"]), set()).update(
            str(item) for item in row.get("operations", ())
        )
    allowances: dict[str, tuple[str, ...]] = {}
    for surface in discovered:
        key = implementation_surface_key(surface.path, surface.symbol)
        allowed = {
            operation
            for operation in surface.dynamic_operations
            if operation.startswith(bounded_prefixes)
        }
        allowed.update(exact_rows.get(key, set()))
        # A statically finite selector is owned by the generated exact-current
        # contract path.  It must not remain admitted through the weaker
        # historical allowance path as a second authority.
        allowed.difference_update(dict(surface.dynamic_selector_values))
        if allowed:
            allowances[key] = tuple(sorted(allowed))
    raw_contracts = definition["dynamic_selector_contracts"]
    if not isinstance(raw_contracts, list):
        raise FlowGuardSelfBlueprintError(
            "dynamic_selector_contracts must be a list"
        )
    if raw_contracts:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint finite dynamic selector contracts are derived from "
            "the current provider observation and cannot be duplicated in the "
            "authored definition"
        )
    dynamic_selector_contracts = tuple(
        contract
        for path in sorted(observations)
        for contract in derive_static_dynamic_selector_contracts(
            observations[path],
            supporting_owners=supporting_owners,
        )
    )
    projected_observations = {
        path: project_python_implementation_observation(
            observation,
            surface_dispositions=dispositions,
            supporting_owners=supporting_owners,
            dynamic_allowances=allowances,
            dynamic_selector_contracts=tuple(
                contract
                for contract in dynamic_selector_contracts
                if contract.surface_key.startswith(f"{path}#")
            ),
        )
        for path, observation in observations.items()
    }
    return (
        dispositions,
        supporting_owners,
        allowances,
        dynamic_selector_contracts,
        projected_observations,
    )


def _self_surface_disposition(surface: ImplementationSurface) -> str:
    """Classify one observed Python surface without removing it from the DNA."""

    normalized_path = surface.path.replace("\\", "/")
    if normalized_path.startswith(".flowguard/") and normalized_path.endswith(
        "/run_checks.py"
    ):
        return IMPLEMENTATION_DISPOSITION_SUPPORTING
    if normalized_path.startswith(".flowguard/") and normalized_path.endswith(
        "/model.py"
    ):
        return IMPLEMENTATION_DISPOSITION_SUPPORTING
    if surface.surface_kind in {"module", "class"}:
        return IMPLEMENTATION_DISPOSITION_SUPPORTING
    if surface.behavior_bearing:
        return IMPLEMENTATION_DISPOSITION_MODEL
    leaf = surface.symbol.rsplit(".", 1)[-1]
    if ".<locals>." in surface.symbol:
        return IMPLEMENTATION_DISPOSITION_SUPPORTING
    if surface.surface_kind not in {"function", "method", "entrypoint"}:
        return IMPLEMENTATION_DISPOSITION_SUPPORTING
    if leaf.startswith("_"):
        return IMPLEMENTATION_DISPOSITION_SUPPORTING
    return IMPLEMENTATION_DISPOSITION_MODEL


def _manifest_entries(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    value = _load_json_object(root / ".flowguard/model-regression-manifest.json")
    entries = {
        str(item["model_id"]): item
        for item in value.get("models", ())
        if isinstance(item, Mapping) and item.get("model_id")
    }
    return value, entries


def _exact_owner_for_path(
    path: str,
    *,
    entries: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, str],
) -> str:
    if path in overrides:
        owner = str(overrides[path])
        if owner not in entries:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner override is unknown: {path} -> {owner}"
            )
        return owner
    if path.startswith(".flowguard/") and len(path.split("/")) >= 3:
        owner = path.split("/", 2)[1]
        if owner in entries:
            return owner
    if path.startswith("flowguard/") and path.endswith(".py"):
        owner = Path(path).stem
        if owner in entries:
            return owner
    raise FlowGuardSelfBlueprintError(
        "self-blueprint implementation path has no exact declared model owner; "
        f"add one owner override: {path}"
    )


def _purpose_value(entry: Mapping[str, Any], key: str, default: Any) -> Any:
    purpose = entry.get("purpose_closure", {})
    return purpose.get(key, default) if isinstance(purpose, Mapping) else default


def _declared_owner_composite_contracts(
    definition: Mapping[str, Any],
    entries: Mapping[str, Mapping[str, Any]],
) -> dict[str, _ProviderDeclaredCompositeBehaviorContract]:
    """Validate the self provider's complete direct-current composite registry."""

    rows = definition.get("composite_behavior_contracts")
    if not isinstance(rows, list):
        raise FlowGuardSelfBlueprintError(
            "composite_behavior_contracts must be an exact array"
        )
    contracts: dict[str, _ProviderDeclaredCompositeBehaviorContract] = {}
    surface_owners: dict[str, str] = {}
    for raw in rows:
        contract = _ProviderDeclaredCompositeBehaviorContract.from_definition(raw)
        owner = contract.owner_id
        if owner not in entries:
            raise FlowGuardSelfBlueprintError(
                f"composite behavior contract declares a foreign owner: {owner}"
            )
        if owner in contracts:
            raise FlowGuardSelfBlueprintError(
                f"composite behavior contract owner is duplicated: {owner}"
            )
        prior_owner = surface_owners.get(contract.surface_key)
        if prior_owner is not None:
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract surface is shared across owners: "
                f"{contract.surface_key} -> {prior_owner},{owner}"
            )

        entry = entries[owner]
        purpose = entry.get("purpose_closure")
        if not isinstance(purpose, Mapping):
            raise FlowGuardSelfBlueprintError(
                f"composite behavior contract has no current purpose closure: {owner}"
            )
        runner_tokens = tuple(str(item) for item in entry.get("runner", ()))
        runner_path = next(
            (item.replace("\\", "/") for item in reversed(runner_tokens) if item.endswith(".py")),
            "",
        )
        expected_source_identity = {
            "purpose_source_id": (
                ".flowguard/model-regression-manifest.json"
                f"#model:{owner}:purpose-declaration"
            ),
            "purpose_source_owner_id": f"model-purpose-declaration:{owner}",
            "model_path": str(entry.get("model_path", "")).replace("\\", "/"),
            "model_source_fingerprint": str(purpose.get("model_sha256", "")),
            "runner_path": runner_path,
            "runner_source_fingerprint": str(purpose.get("runner_sha256", "")),
            "purpose_declaration_fingerprint": str(
                purpose.get("declaration_fingerprint", "")
            ),
            "purpose_closure_fingerprint": str(
                purpose.get("closure_fingerprint", "")
            ),
        }
        stale_fields = tuple(
            name
            for name, expected in expected_source_identity.items()
            if not expected or str(getattr(contract, name)) != expected
        )
        if stale_fields:
            raise FlowGuardSelfBlueprintError(
                "composite behavior contract source identity is stale or foreign: "
                f"{owner} fields={','.join(stale_fields)}"
            )
        contracts[owner] = contract
        surface_owners[contract.surface_key] = owner

    missing = tuple(sorted(set(entries) - set(contracts)))
    if missing:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint provider omits explicit composite behavior contracts: "
            + ",".join(missing)
        )
    return contracts


def _exact_owner_composite_surface(
    owner: str,
    surfaces: Sequence[ImplementationSurface],
    contract: _ProviderDeclaredCompositeBehaviorContract,
) -> ImplementationSurface:
    """Resolve only the provider-declared exact observed composite surface."""

    if contract.owner_id != owner:
        raise FlowGuardSelfBlueprintError(
            "composite behavior contract belongs to another owner: "
            f"{contract.owner_id} -> {owner}"
        )
    candidates = tuple(
        surface
        for surface in surfaces
        if implementation_surface_key(surface.path, surface.symbol)
        == contract.surface_key
    )
    if len(candidates) != 1:
        raise FlowGuardSelfBlueprintError(
            "provider-declared composite behavior surface is missing, foreign, "
            f"or ambiguous: {owner} -> {contract.surface_key}"
        )
    return candidates[0]


def _project_owners(
    root: Path,
    inventory: ImplementationSurfaceInventory,
    entries: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, str],
    composite_contracts: Mapping[
        str, _ProviderDeclaredCompositeBehaviorContract
    ],
    test_inventory: ProjectTestInventory,
    intent_inventory: ProjectIntentInventory,
) -> tuple[ProjectBlueprintOwner, ...]:
    """Translate FlowGuard declarations into stable owner obligations.

    Source discovery is used only to locate implementation surfaces.  The
    semantic payload below comes from the checked-in model-purpose closure and
    its immutable fingerprints, so code observations cannot certify intent.
    """

    grouped: dict[str, list[ImplementationSurface]] = {}
    for surface in inventory.surfaces:
        owner = _exact_owner_for_path(
            surface.path,
            entries=entries,
            overrides=overrides,
        )
        grouped.setdefault(owner, []).append(surface)

    accepted_intent_sources_by_target: dict[
        str, set[tuple[str, str]]
    ] = {}
    for contribution in intent_inventory.contributions:
        if contribution.disposition != "accepted":
            continue
        for target_id in contribution.target_ids:
            accepted_intent_sources_by_target.setdefault(
                target_id, set()
            ).add(
                (
                    contribution.source_id,
                    contribution.source_fingerprint,
                )
            )

    behavior_surface_ids = set(implementation_behavior_surface_ids(inventory))
    owners: list[ProjectBlueprintOwner] = []
    for owner, owner_surfaces in sorted(grouped.items()):
        entry = entries[owner]
        composite_contract = composite_contracts.get(owner)
        if composite_contract is None:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner lacks an explicit composite contract: {owner}"
            )
        purpose = entry.get("purpose_closure", {})
        if not isinstance(purpose, Mapping):
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner purpose closure is missing: {owner}"
            )
        closure_fingerprint = str(purpose.get("closure_fingerprint", ""))
        if not closure_fingerprint:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner closure fingerprint is missing: {owner}"
            )
        model_element_id = f"model-obligation:{owner}"
        dimensions = {"input", "output", "error", "order", "retry", "timeout"}
        for surface in owner_surfaces:
            dimensions.update(project_surface_dimensions(surface))
        protected_failures = tuple(
            str(item) for item in purpose.get("protected_failure_ids", ())
        )
        semantics: dict[str, str] = {
            "input": (
                "admit only inputs inside the declared guarded purpose and claim boundary"
            ),
            "output": str(purpose.get("guarded_purpose", "")),
            "error": (
                "preserve protected failures="
                + ",".join(protected_failures or ("none_declared",))
            ),
            "order": "not_applicable unless the declared owner model contains ordered transitions",
            "retry": "not_applicable unless the declared owner model assigns retry ownership",
            "timeout": "not_applicable unless the declared owner model assigns timeout ownership",
            "completion": (
                "reach the declared owner terminal condition without hiding an incomplete or blocked outcome"
            ),
        }
        if "state_effect" in dimensions:
            semantics["state_effect"] = (
                "preserve state and effect boundaries licensed by the declared owner model"
            )
        if "decision" in dimensions:
            semantics["decision"] = (
                "distinguish every protected failure and decision branch in the declared owner model"
            )
        provenance = tuple(
            (key, str(purpose[key]))
            for key in (
                "model_sha256",
                "runner_sha256",
                "declaration_fingerprint",
                "closure_fingerprint",
            )
            if purpose.get(key)
        )
        provenance = tuple(
            sorted(
                {
                    *provenance,
                    (
                        "composite-provider-contract",
                        composite_contract.fingerprint,
                    ),
                    *accepted_intent_sources_by_target.get(
                        model_element_id, set()
                    ),
                }
            )
        )
        model_source_fingerprint = str(purpose.get("model_sha256", ""))
        declaration_fingerprint = str(
            purpose.get("declaration_fingerprint", "")
        )
        runner_source_fingerprint = str(purpose.get("runner_sha256", ""))
        runner_tokens = tuple(str(item) for item in entry.get("runner", ()))
        runner_source_id = next(
            (item for item in reversed(runner_tokens) if item.endswith(".py")),
            "",
        )
        if not (
            model_source_fingerprint
            and declaration_fingerprint
            and runner_source_fingerprint
            and runner_source_id
        ):
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint source identity is incomplete: {owner}"
            )
        semantic = SemanticSpecReference(
            semantic_spec_id=f"semantic-spec:model-owner:{owner}",
            owner_id=f"model:{owner}",
            artifact_id=f"model-purpose-declaration:{owner}",
            artifact_fingerprint=closure_fingerprint,
            source_id=composite_contract.purpose_source_id,
            source_owner_id=composite_contract.purpose_source_owner_id,
            source_content_fingerprint=(
                composite_contract.purpose_declaration_fingerprint
            ),
            covered_model_element_ids=(model_element_id,),
            covered_dimensions=tuple(sorted(dimensions)),
            semantics=tuple(semantics.items()),
            authority_kind=SEMANTIC_AUTHORITY_IMPORTED_MODEL,
            provenance_fingerprints=provenance,
        )
        failure_bindings = purpose.get("failure_bindings", ())
        oracle_semantics = {
            "input": "known_good_case=" + str(purpose.get("known_good_case_id", "")),
            "output": "evidence_checks=" + ",".join(
                str(item) for item in purpose.get("evidence_check_ids", ())
            ),
            "error": "known_bad_cases=" + ",".join(
                str(item.get("known_bad_case_id", ""))
                for item in failure_bindings
                if isinstance(item, Mapping)
            ),
            "order": "assert declared order when applicable; otherwise explicit not_applicable",
            "retry": "assert declared retry ownership when applicable; otherwise explicit not_applicable",
            "timeout": "assert declared timeout ownership when applicable; otherwise explicit not_applicable",
            "completion": (
                "assert the declared terminal condition and reject partial success substitution"
            ),
        }
        if "state_effect" in dimensions:
            oracle_semantics["state_effect"] = (
                "native owner checks preserve declared state and effect boundaries"
            )
        if "decision" in dimensions:
            oracle_semantics["decision"] = (
                "native owner checks distinguish declared protected failures"
            )
        oracle = OracleReference(
            oracle_id=f"oracle:model-regression:{owner}",
            owner_id=f"model:{owner}",
            artifact_id=f"native-runner:{owner}",
            artifact_fingerprint=closure_fingerprint,
            source_id=runner_source_id,
            source_owner_id=f"validation-owner:model:{owner}",
            source_content_fingerprint=runner_source_fingerprint,
            covered_model_element_ids=(model_element_id,),
            covered_dimensions=tuple(sorted(dimensions)),
            semantics=tuple(oracle_semantics.items()),
        )
        declared_test_patterns = tuple(
            str(item).replace("\\", "/")
            for item in entry.get("input_globs", ())
            if str(item).startswith("tests/")
        )
        owner_test_nodes = tuple(
            node
            for node in test_inventory.nodes
            if any(
                fnmatchcase(node.path, pattern)
                or node.path == pattern
                for pattern in declared_test_patterns
            )
            and node.disposition == TEST_DISPOSITION_REQUIRED
        )
        if owner_test_nodes:
            test_evidence = tuple(
                (node.node_id, node.structure_fingerprint)
                for node in owner_test_nodes
            )
        else:
            test_evidence = ()
        native_evidence = tuple(
            (
                str(evidence_id),
                str(purpose.get("runner_sha256", closure_fingerprint)),
            )
            for evidence_id in purpose.get("evidence_check_ids", ())
        )
        if not test_evidence and not native_evidence:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner has no exact evidence check: {owner}"
            )
        behavior_surfaces = tuple(
            surface
            for surface in owner_surfaces
            if surface.surface_id in behavior_surface_ids
        )
        if not behavior_surfaces:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner has no observed behavior surface: {owner}"
            )
        primary_surface = _exact_owner_composite_surface(
            owner,
            owner_surfaces,
            composite_contract,
        )
        known_good_case_id = str(purpose.get("known_good_case_id", ""))
        known_bad_case_ids = tuple(
            str(item.get("known_bad_case_id", ""))
            for item in failure_bindings
            if isinstance(item, Mapping) and item.get("known_bad_case_id")
        )
        transition_ids = tuple(
            item for item in (known_good_case_id, *known_bad_case_ids) if item
        )
        if not transition_ids:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner has no declared good/bad transition cases: {owner}"
            )
        portable_property_ids = (f"property:{owner}:declared-purpose",)
        portable_invariant_ids = (
            f"invariant:{owner}:{closure_fingerprint}",
        )
        portable_assumption_ids = (
            f"assumption:{purpose.get('task_intent_id', owner)}",
        )
        portable_guarantee_ids = (
            tuple(str(item) for item in purpose.get("evidence_check_ids", ()))
            or (f"guarantee:{owner}:declared-terminal",)
        )
        declared_cases: list[BehaviorCaseContract] = []
        checker_designs: dict[str, str] = {}
        portable_behavior_bindings: list[PortableBehaviorBinding] = []
        failure_by_case = {
            str(item.get("known_bad_case_id", "")): str(item.get("failure_id", ""))
            for item in failure_bindings
            if isinstance(item, Mapping)
            and item.get("known_bad_case_id")
            and item.get("failure_id")
        }
        for surface in behavior_surfaces:
            is_composite_surface = surface.surface_id == primary_surface.surface_id
            semantic_member_prefix = (
                f"semantic-member:{semantic.semantic_spec_id}:{surface.surface_id}"
            )
            input_field_mappings = tuple(
                (parameter, f"{semantic_member_prefix}:input:{parameter}")
                for parameter in surface.parameters
            )
            output_field_mappings = (
                (("return", f"{semantic_member_prefix}:output:return"),)
                if surface.returns_value
                else ()
            )
            state_fields = tuple(
                sorted(
                    (set(surface.state_reads) | set(surface.state_writes))
                    - set(surface.parameters)
                )
            )
            state_field_mappings = tuple(
                (field, f"{semantic_member_prefix}:state:{field}")
                for field in state_fields
            )
            behavior_block_id = f"behavior-block:{surface.surface_id}"
            portable_behavior_bindings.append(
                PortableBehaviorBinding(
                    binding_id=f"portable-binding:{surface.surface_id}",
                    behavior_block_id=behavior_block_id,
                    portable_model_id=f"portable-model:{owner}",
                    portable_model_fingerprint=closure_fingerprint,
                    implementation_fingerprint=surface.content_fingerprint,
                    transition_ids=(transition_ids if is_composite_surface else ()),
                    property_ids=portable_property_ids,
                    invariant_ids=portable_invariant_ids,
                    input_field_mappings=input_field_mappings,
                    output_field_mappings=output_field_mappings,
                    state_field_mappings=state_field_mappings,
                    assumption_ids=portable_assumption_ids,
                    guarantee_ids=portable_guarantee_ids,
                    protected_failure_ids=(
                        protected_failures if is_composite_surface else ()
                    ),
                    provider_fingerprints=tuple(
                        (
                            ("independent-owner-model", closure_fingerprint),
                            (
                                "implementation-observation",
                                surface.structure_fingerprint,
                            ),
                            (
                                "model-member-scope",
                                fingerprint_value(
                                    {
                                        "owner": owner,
                                        "surface_id": surface.surface_id,
                                        "composite_surface_id": (
                                            primary_surface.surface_id
                                        ),
                                        "scope": (
                                            "owner_composite"
                                            if is_composite_surface
                                            else "detailed_child"
                                        ),
                                        "owner_closure": closure_fingerprint,
                                    }
                                ),
                            ),
                        )
                        + ((
                            (
                                "provider-declared-composite",
                                composite_contract.fingerprint,
                            ),
                            (
                                "composite-input-contract",
                                composite_contract.input_contract_id,
                            ),
                            (
                                "composite-state-contract",
                                composite_contract.state_contract_id,
                            ),
                            (
                                "composite-effect-contract",
                                composite_contract.effect_contract_id,
                            ),
                            (
                                "composite-output-contract",
                                composite_contract.output_contract_id,
                            ),
                            (
                                "composite-completion-contract",
                                composite_contract.completion_contract_id,
                            ),
                            (
                                "composite-semantic-contract",
                                composite_contract.semantic_contract_id,
                            ),
                            (
                                "composite-source-identity",
                                composite_contract.source_identity_fingerprint,
                            ),
                        ) if is_composite_surface else ())
                    ),
                )
            )

            def add_declared_case(
                *,
                source_case_id: str,
                case_kind: str,
                rule_suffix: str,
                failure_id: str = "",
            ) -> None:
                case_id = (
                    f"behavior-case:{surface.surface_id}:{case_kind}:"
                    f"{source_case_id}"
                )
                checker_id = f"checker-design:{case_id}"
                checker_fingerprint = fingerprint_value(
                    {
                        "owner_closure": closure_fingerprint,
                        "surface_id": surface.surface_id,
                        "surface_structure": surface.structure_fingerprint,
                        "source_case_id": source_case_id,
                        "case_id": case_id,
                        "case_kind": case_kind,
                        "oracle_id": oracle.oracle_id,
                    }
                )
                checker_designs[checker_id] = checker_fingerprint
                declared_cases.append(
                    BehaviorCaseContract(
                        case_id=case_id,
                        behavior_block_id=behavior_block_id,
                        case_kind=case_kind,
                        input_values=tuple(
                            (
                                parameter,
                                f"rule:{semantic.semantic_spec_id}:{surface.surface_id}:"
                                f"input:{parameter}:{rule_suffix}",
                            )
                            for parameter in surface.parameters
                        ),
                        initial_state=tuple(
                            (
                                field,
                                f"rule:{semantic.semantic_spec_id}:{surface.surface_id}:"
                                f"state:{field}:{rule_suffix}",
                            )
                            for field in surface.state_reads
                            if field not in set(surface.parameters)
                        ),
                        expected_output=(
                            (
                                (
                                    "return",
                                    f"oracle:{oracle.oracle_id}:{surface.surface_id}:"
                                    f"{rule_suffix}:return",
                                ),
                            )
                            if surface.returns_value and not failure_id
                            else ()
                        ),
                        expected_state=tuple(
                            (
                                field,
                                f"oracle:{oracle.oracle_id}:{surface.surface_id}:"
                                f"{rule_suffix}:state:{field}",
                            )
                            for field in surface.state_writes
                            if field not in set(surface.parameters)
                        ),
                        expected_effects=(
                            () if failure_id else surface.side_effect_candidates
                        ),
                        expected_errors=((failure_id,) if failure_id else ()),
                        oracle_id=oracle.oracle_id,
                        case_evidence_id=checker_id,
                        case_evidence_fingerprint=checker_fingerprint,
                        value_mode="symbolic_contract",
                        protected_failure_ids=((failure_id,) if failure_id else ()),
                        parameter_case_id=case_id,
                        source_case_id=source_case_id,
                    )
                )
                for dimension in BEHAVIOR_CASE_DIMENSIONS[case_kind]:
                    member_id = f"{checker_id}:{dimension}"
                    checker_designs[member_id] = fingerprint_value(
                        {
                            "owner_closure": closure_fingerprint,
                            "surface_id": surface.surface_id,
                            "source_case_id": source_case_id,
                            "case_id": case_id,
                            "dimension": dimension,
                            "oracle_id": oracle.oracle_id,
                        }
                    )

            add_declared_case(
                source_case_id=known_good_case_id,
                case_kind="good",
                rule_suffix="accepted",
            )
            add_declared_case(
                source_case_id=f"boundary:{owner}:{closure_fingerprint}",
                case_kind="boundary",
                rule_suffix="boundary",
            )
            if is_composite_surface:
                for bad_case_id in known_bad_case_ids:
                    add_declared_case(
                        source_case_id=bad_case_id,
                        case_kind="bad",
                        rule_suffix=f"protected:{failure_by_case[bad_case_id]}",
                        failure_id=failure_by_case[bad_case_id],
                    )
        primary_binding = next(
            binding
            for binding in portable_behavior_bindings
            if binding.behavior_block_id
            == f"behavior-block:{primary_surface.surface_id}"
        )
        owners.append(
            ProjectBlueprintOwner(
                model_element_id=model_element_id,
                owner_id=f"model:{owner}",
                owner_contract_id=f"owner-contract:{owner}",
                model_fingerprint=closure_fingerprint,
                owner_contract_fingerprint=closure_fingerprint,
                portable_model_id=f"portable-model:{owner}",
                portable_model_fingerprint=closure_fingerprint,
                portable_transition_ids=transition_ids,
                portable_property_ids=portable_property_ids,
                portable_invariant_ids=portable_invariant_ids,
                portable_input_field_mappings=primary_binding.input_field_mappings,
                portable_output_field_mappings=primary_binding.output_field_mappings,
                portable_state_field_mappings=primary_binding.state_field_mappings,
                portable_assumption_ids=portable_assumption_ids,
                portable_guarantee_ids=portable_guarantee_ids,
                protected_failure_ids=protected_failures,
                portable_behavior_bindings=tuple(portable_behavior_bindings),
                implementation_surface_ids=tuple(
                    surface.surface_id for surface in owner_surfaces
                ),
                primary_surface_id=primary_surface.surface_id,
                semantic_specs=(semantic,),
                oracles=(oracle,),
                test_evidence_fingerprints=test_evidence,
                native_evidence_fingerprints=native_evidence,
                behavior_accepted=True,
                behavior_acceptance_evidence_fingerprints=tuple(
                    {
                        **dict(provenance),
                        "owner-contract": closure_fingerprint,
                        "semantic-spec": semantic.artifact_fingerprint,
                        "oracle": oracle.artifact_fingerprint,
                    }.items()
                ),
                behavior_case_contracts=tuple(declared_cases),
                checker_design_fingerprints=tuple(checker_designs.items()),
            )
        )
    return tuple(owners)


def _flowguard_test_inventory(
    root: Path,
    *,
    subject_revision: str,
) -> ProjectTestInventory:
    patterns = ("tests/**/test_*.py", "tests/**/*_test.py")
    manifest = resolve_input_manifest(root, patterns)
    file_dispositions = tuple(
        TestFileDisposition(
            path=str(row["path"]),
            source_fingerprint=str(row["sha256"]),
            disposition=TEST_DISPOSITION_REQUIRED,
            reason="current declared project test source",
            adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
        )
        for row in manifest
    )
    discovery = build_project_test_inventory(
        root,
        inventory_id="test-inventory:flowguard:discovery",
        subject_revision=subject_revision,
        test_patterns=patterns,
        file_dispositions=file_dispositions,
        node_dispositions=(),
        discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file},
    )
    node_dispositions = tuple(
        TestNodeDisposition(
            node.pytest_nodeid,
            (
                TEST_DISPOSITION_REQUIRED
                if node.assertion_count
                else TEST_DISPOSITION_SUPPORTING
            ),
            reason=(
                "oracle-bearing current test node"
                if node.assertion_count
                else "assertion-free helper or orchestration node"
            ),
        )
        for node in discovery.nodes
    )
    inventory = build_project_test_inventory(
        root,
        inventory_id="test-inventory:flowguard:current",
        subject_revision=subject_revision,
        test_patterns=patterns,
        file_dispositions=file_dispositions,
        node_dispositions=node_dispositions,
        discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file},
    )
    audit = review_project_test_inventory(
        inventory,
        root=root,
        discovery_adapters={PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file},
    )
    if not audit.ok:
        codes = ",".join(finding.code for finding in audit.findings)
        raise FlowGuardSelfBlueprintError(
            f"FlowGuard project test inventory is not complete: {codes}"
        )
    return inventory


def _flowguard_delegated_assertion_helpers(
    root: Path,
    test_inventory: ProjectTestInventory,
) -> tuple[DelegatedAssertionHelper, ...]:
    """Discover assert-like helpers at every lexical depth.

    A helper is identified by source path plus lexical qualified name.  The
    qualified identity prevents two nested helpers with the same leaf name
    from silently sharing evidence.  Function bodies are scanned without
    descending into nested definitions, so an outer helper cannot borrow an
    assertion that belongs to a nested helper.
    """

    callers_by_leaf: dict[str, list[str]] = {}
    test_nodes_by_path: dict[str, list[Any]] = {}
    for node in test_inventory.nodes:
        test_nodes_by_path.setdefault(node.path, []).append(node)
        for call in node.calls:
            callers_by_leaf.setdefault(call.rsplit(".", 1)[-1], []).append(
                node.node_id
            )

    source_paths = {row.path for row in test_inventory.nodes}
    source_paths.update(
        path.relative_to(root).as_posix()
        for path in root.glob("flowguard/**/*.py")
        if path.is_file()
    )
    records: list[tuple[str, str, str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def collect_functions(
        body: Sequence[ast.stmt],
        path: str,
        scope: tuple[str, ...] = (),
    ) -> None:
        for item in body:
            if isinstance(item, ast.ClassDef):
                collect_functions(item.body, path, (*scope, item.name))
                continue
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qualified_name = ".".join((*scope, item.name))
            if item.name.startswith("assert_"):
                helper_id = f"delegated-helper:{path}::{qualified_name}"
                records.append((helper_id, path, qualified_name, item))
            collect_functions(item.body, path, (*scope, item.name))

    for path in sorted(source_paths):
        source_path = root / path
        try:
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"),
                filename=path,
            )
        except (OSError, UnicodeError, SyntaxError):
            continue
        collect_functions(tree.body, path)

    by_path_and_qualified = {
        (path, qualified_name): helper_id
        for helper_id, path, qualified_name, _function in records
    }
    by_leaf: dict[str, list[str]] = {}
    for helper_id, _path, qualified_name, _function in records:
        by_leaf.setdefault(qualified_name.rsplit(".", 1)[-1], []).append(
            helper_id
        )

    def own_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef):
        pending = list(reversed(function.body))
        while pending:
            node = pending.pop()
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                continue
            yield node
            pending.extend(reversed(tuple(ast.iter_child_nodes(node))))

    def resolve_callee(path: str, qualified_name: str, leaf: str) -> str:
        scope = qualified_name.split(".")[:-1]
        for depth in range(len(scope), -1, -1):
            candidate_name = ".".join((*scope[:depth], leaf))
            candidate = by_path_and_qualified.get((path, candidate_name))
            if candidate:
                return candidate
        candidates = tuple(sorted(set(by_leaf.get(leaf, ()))))
        return candidates[0] if len(candidates) == 1 else leaf

    def owning_test_node(path: str, qualified_name: str, leaf: str) -> str:
        qualified_parts = qualified_name.split(".")
        matches: list[str] = []
        for node in test_nodes_by_path.get(path, ()):
            node_parts = str(node.node_id).split("::")[1:]
            if node_parts and qualified_parts[: len(node_parts)] == node_parts:
                matches.append(str(node.node_id))
        if matches:
            return sorted(matches, key=len, reverse=True)[0]
        callers = tuple(sorted(set(callers_by_leaf.get(leaf, ()))))
        return (
            callers[0]
            if callers
            else f"delegated-helper-library:{path}#{qualified_name}"
        )

    helpers: list[DelegatedAssertionHelper] = []
    for helper_id, path, qualified_name, function in records:
        leaf = qualified_name.rsplit(".", 1)[-1]
        terminal_members: list[tuple[str, str]] = []
        callee_ids: list[str] = []
        for node in own_nodes(function):
            terminal = False
            if isinstance(node, ast.Assert):
                terminal = True
            elif isinstance(node, ast.Raise):
                terminal = node.exc is not None
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    called = node.func.attr
                else:
                    called = ""
                if called.startswith("assert_") and called != leaf:
                    callee_ids.append(
                        resolve_callee(path, qualified_name, called)
                    )
                elif called in {"raises", "warns", "fail"} or called.startswith(
                    "assert"
                ):
                    terminal = True
            if not terminal:
                continue
            terminal_id = (
                f"delegated-terminal:{helper_id}:"
                f"{getattr(node, 'lineno', 0)}:{getattr(node, 'col_offset', 0)}"
            )
            terminal_members.append(
                (
                    terminal_id,
                    fingerprint_value(
                        {
                            "path": path,
                            "helper_id": helper_id,
                            "ast": ast.dump(
                                node,
                                annotate_fields=True,
                                include_attributes=False,
                            ),
                        }
                    ),
                )
            )
        if not terminal_members and not callee_ids:
            continue
        helpers.append(
            DelegatedAssertionHelper(
                helper_id=helper_id,
                test_node_id=owning_test_node(path, qualified_name, leaf),
                source_fingerprint=fingerprint_value(
                    {
                        "path": path,
                        "qualified_name": qualified_name,
                        "ast": ast.dump(
                            function,
                            annotate_fields=True,
                            include_attributes=False,
                        ),
                    }
                ),
                callee_member_ids=tuple(callee_ids),
                terminal_member_fingerprints=tuple(terminal_members),
            )
        )
    return tuple(sorted(helpers, key=lambda row: row.helper_id))


def _resources(
    root: Path,
    definition: Mapping[str, Any],
    owners: Sequence[ProjectBlueprintOwner],
) -> tuple[BlueprintResourceReference, ...]:
    root_owners = tuple(
        owner
        for owner in owners
        if owner.owner_id == "model:authoritative_model_system"
    )
    if len(root_owners) != 1:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint resources require one exact authoritative root owner"
        )
    root_owner = root_owners[0]
    root_binding = next(
        (
            binding
            for binding in root_owner.portable_behavior_bindings
            if binding.behavior_block_id
            == f"behavior-block:{root_owner.primary_surface_id}"
        ),
        None,
    )
    if root_binding is None:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint resource root has no exact primary behavior binding"
        )
    consuming_behavior_ids = (root_binding.behavior_block_id,)
    consuming_model_ids = (root_owner.model_element_id,)
    rows: list[BlueprintResourceReference] = []
    for kind, patterns in sorted(dict(definition["resource_groups"]).items()):
        manifest = resolve_input_manifest(root, tuple(str(item) for item in patterns))
        if not manifest:
            raise FlowGuardSelfBlueprintError(f"required resource group is empty: {kind}")
        fingerprint = fingerprint_value(list(manifest))
        rows.append(
            BlueprintResourceReference(
                resource_id=f"resource:flowguard:{kind}",
                kind=str(kind),
                owner_id=root_owner.owner_id,
                artifact_id=f"resource-manifest:{kind}",
                purpose=f"describe the exact current {kind} resource boundary",
                lifecycle_role="blueprint_input",
                consuming_behavior_ids=consuming_behavior_ids,
                consuming_model_ids=consuming_model_ids,
                artifact_fingerprint=fingerprint,
                semantics=(
                    (
                        "requirement",
                        f"materialize the exact current {kind} resource manifest",
                    ),
                    (
                        "scope",
                        "the authoritative self-blueprint root consumes this grouped resource boundary",
                    ),
                ),
            )
        )
    return tuple(rows)


def _observed_resources(
    root: Path,
    definition: Mapping[str, Any],
    declarations: Sequence[BlueprintResourceReference],
    *,
    observed_snapshot_fingerprint: str,
) -> tuple[ObservedResourceMember, ...]:
    """Observe the resource denominator independently from declaration rows."""

    declarations_by_kind = {row.kind: row for row in declarations}
    rows: list[ObservedResourceMember] = []
    for kind, patterns in sorted(dict(definition["resource_groups"]).items()):
        manifest = resolve_input_manifest(
            root, tuple(str(item) for item in patterns)
        )
        if not manifest:
            raise FlowGuardSelfBlueprintError(
                f"required observed resource group is empty: {kind}"
            )
        declaration = declarations_by_kind.get(str(kind))
        if declaration is None:
            raise FlowGuardSelfBlueprintError(
                f"observed resource has no declared identity: {kind}"
            )
        rows.append(
            ObservedResourceMember(
                resource_id=declaration.resource_id,
                kind=declaration.kind,
                owner_id=declaration.owner_id,
                artifact_id=declaration.artifact_id,
                subject_revision=observed_snapshot_fingerprint,
                current_artifact_fingerprint=fingerprint_value(list(manifest)),
                provider_id="flowguard-resource-manifest-v1",
                capability_id="resource_inventory",
                payload_id="resource_inventory",
            )
        )
    return tuple(rows)


def _self_topology(
    *,
    semantic_mesh: Mapping[str, Any],
    owners: Sequence[ProjectBlueprintOwner],
    entries: Mapping[str, Mapping[str, Any]],
    inventory: ImplementationSurfaceInventory,
    model_regression_evidence: CurrentModelRegressionParentEvidence,
    activation_receipt_fingerprint: str,
) -> tuple[
    tuple[BlueprintTopologyNode, ...],
    tuple[BlueprintTopologyRelation, ...],
    tuple[ChildModelEvidence, ...],
    tuple[ChildReattachmentContract, ...],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
]:
    """Compile the semantic mesh against independently verified current evidence.

    The checked-in mesh owns topology declarations only.  It cannot certify its own
    children or feedback loops.  Child currentness comes from the unique exact-current
    full model-regression parent resolver, which independently reloads and verifies
    every leaf receipt.  Feedback progress comes either from the accepted authority
    activation receipt or from an exact declared set of those verified child leaves.
    """

    owner_by_model = {
        owner.model_element_id.removeprefix("model-obligation:"): owner
        for owner in owners
    }
    mesh_rows = {
        str(row.get("model_id", "")): row
        for row in semantic_mesh.get("models", ())
        if isinstance(row, Mapping) and row.get("model_id")
    }
    topology_root_id = "topology-root:flowguard-self"
    semantic_parent_rows = {
        str(row.get("parent_id", "")): row
        for row in semantic_mesh.get("semantic_parents", ())
        if isinstance(row, Mapping) and str(row.get("parent_id", ""))
    }
    if len(semantic_parent_rows) != len(
        tuple(semantic_mesh.get("semantic_parents", ()))
    ):
        raise FlowGuardSelfBlueprintError(
            "self-blueprint semantic parent identities are missing or duplicated"
        )
    semantic_relation_fingerprint = str(
        semantic_mesh.get("semantic_relation_fingerprint", "")
    )
    semantic_mesh_id = str(semantic_mesh.get("mesh_id", ""))
    semantic_mesh_status = str(semantic_mesh.get("semantic_model_status", ""))
    current_children = dict(
        model_regression_evidence.child_evidence_by_model_id
    )
    expected_child_ids = set(owner_by_model)
    declared_mesh_ids = set(mesh_rows)
    if declared_mesh_ids != expected_child_ids:
        missing = sorted(expected_child_ids - declared_mesh_ids)
        extra = sorted(declared_mesh_ids - expected_child_ids)
        raise FlowGuardSelfBlueprintError(
            "self-blueprint semantic mesh does not exactly match the owner "
            f"universe; missing={missing!r}, extra={extra!r}"
        )
    if set(current_children) != expected_child_ids:
        missing = sorted(expected_child_ids - set(current_children))
        extra = sorted(set(current_children) - expected_child_ids)
        raise FlowGuardSelfBlueprintError(
            "self-blueprint current model child evidence does not exactly match "
            f"the owner universe; missing={missing!r}, extra={extra!r}"
        )
    if not str(activation_receipt_fingerprint).strip():
        raise FlowGuardSelfBlueprintError(
            "self-blueprint feedback progress lacks the accepted activation receipt"
        )

    external_consumers = {
        str(consumer_id)
        for row in mesh_rows.values()
        for consumer_id in row.get("consumer_ids", ())
        if str(consumer_id).startswith("claim:")
    }
    relation_specs: list[tuple[str, str, str, str, str]] = []
    for parent_id in sorted(semantic_parent_rows):
        relation_specs.append(
            (
                f"topology:{parent_id}:{topology_root_id}",
                parent_id,
                topology_root_id,
                "delegates_to",
                "",
            )
        )
    for consumer_id in sorted(external_consumers):
        relation_specs.append(
            (
                f"topology:{consumer_id}:{topology_root_id}",
                consumer_id,
                topology_root_id,
                "delegates_to",
                "",
            )
        )
    for model_id, row in sorted(mesh_rows.items()):
        owner = owner_by_model[model_id]
        structural_parent_id = str(row.get("structural_parent_id", ""))
        if not structural_parent_id:
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint model has no structural parent: {model_id}"
            )
        relation_specs.append(
            (
                f"topology:{model_id}:{structural_parent_id}",
                owner.model_element_id,
                structural_parent_id,
                "child_to_parent",
                model_id,
            )
        )
        for parent_id in sorted(
            {
                str(item)
                for item in row.get("cross_boundary_parent_ids", ())
                if str(item)
            }
        ):
            relation_specs.append(
                (
                    f"topology:{model_id}:{parent_id}",
                    owner.model_element_id,
                    parent_id,
                    "cross_boundary_support",
                    model_id,
                )
            )
        for raw_consumer_id in sorted(
            {str(item) for item in row.get("consumer_ids", ()) if str(item)}
        ):
            consumer_id = raw_consumer_id
            if consumer_id.startswith("model:"):
                consumer_id = "model-obligation:" + consumer_id.removeprefix("model:")
            relation_specs.append(
                (
                    f"topology:{model_id}:{consumer_id}",
                    owner.model_element_id,
                    consumer_id,
                    "produces_for",
                    model_id,
                )
            )

    input_ports_by_node: dict[str, list[BlueprintTopologyPort]] = {}
    output_ports_by_node: dict[str, list[BlueprintTopologyPort]] = {}
    relation_rows: list[BlueprintTopologyRelation] = []
    current_relation_fingerprints: list[tuple[str, str]] = []
    child_evidence_ids = {
        model_id: child.receipt_id
        for model_id, child in sorted(current_children.items())
    }
    current_child_evidence_fingerprints = tuple(
        sorted(
            (
                child.receipt_id,
                child.receipt_fingerprint,
            )
            for child in current_children.values()
        )
    )
    if len(current_child_evidence_fingerprints) != len(
        {evidence_id for evidence_id, _fingerprint in current_child_evidence_fingerprints}
    ):
        raise FlowGuardSelfBlueprintError(
            "self-blueprint model owners do not have unique child receipt identities"
        )

    progress_by_relation: dict[str, BlueprintTopologyProgressContract] = {}
    current_progress_by_contract: dict[str, str] = {}
    declared_progress_relations: set[str] = set()
    known_relation_ids = {row[0] for row in relation_specs}
    for raw_progress in semantic_mesh.get("feedback_progress_contracts", ()):
        if not isinstance(raw_progress, Mapping):
            raise FlowGuardSelfBlueprintError(
                "self-blueprint feedback progress declaration must be an object"
            )
        relation_id = str(raw_progress.get("relation_id", "")).strip()
        contract_id = str(raw_progress.get("contract_id", "")).strip()
        contract_kind = str(raw_progress.get("contract_kind", "")).strip()
        source_kind = str(
            raw_progress.get("evidence_source_kind", "")
        ).strip()
        rationale = str(raw_progress.get("rationale", "")).strip()
        evidence_model_ids = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in raw_progress.get("evidence_model_ids", ())
                    if str(item).strip()
                }
            )
        )
        if (
            not relation_id
            or relation_id not in known_relation_ids
            or relation_id in declared_progress_relations
        ):
            raise FlowGuardSelfBlueprintError(
                "self-blueprint feedback progress relation is missing, foreign, "
                f"or duplicated: {relation_id!r}"
            )
        declared_progress_relations.add(relation_id)
        if source_kind == "accepted_model_authority_activation":
            if evidence_model_ids:
                raise FlowGuardSelfBlueprintError(
                    "authority-activation progress cannot borrow child model receipts"
                )
            progress_fingerprint = str(activation_receipt_fingerprint).strip()
        elif source_kind == "current_child_model_receipts":
            if not evidence_model_ids or any(
                model_id not in current_children for model_id in evidence_model_ids
            ):
                raise FlowGuardSelfBlueprintError(
                    "child-receipt progress omits or names a foreign model owner"
                )
            progress_fingerprint = fingerprint_value(
                {
                    "evidence_source_kind": source_kind,
                    "children": [
                        current_children[model_id].to_dict()
                        for model_id in evidence_model_ids
                    ],
                }
            )
        else:
            raise FlowGuardSelfBlueprintError(
                "self-blueprint feedback progress has an unknown evidence source: "
                f"{source_kind!r}"
            )
        prior_fingerprint = current_progress_by_contract.get(contract_id)
        if prior_fingerprint not in (None, progress_fingerprint):
            raise FlowGuardSelfBlueprintError(
                "one self-blueprint progress contract resolves to conflicting evidence"
            )
        current_progress_by_contract[contract_id] = progress_fingerprint
        progress_by_relation[relation_id] = BlueprintTopologyProgressContract(
            contract_id=contract_id,
            contract_kind=contract_kind,
            evidence_fingerprint=progress_fingerprint,
            rationale=rationale,
        )
    for relation_id, producer_id, consumer_id, relation_kind, model_id in relation_specs:
        row = mesh_rows.get(model_id, {})
        purpose = entries.get(model_id, {}).get("purpose_closure", {})
        if not isinstance(purpose, Mapping):
            purpose = {}
        relation_source = {
            "semantic_mesh_id": semantic_mesh_id,
            "semantic_relation_fingerprint": semantic_relation_fingerprint,
            "model_id": model_id,
            "structural_parent_id": str(
                row.get("structural_parent_id", "")
            ),
            "cross_boundary_parent_ids": sorted(
                str(item)
                for item in row.get("cross_boundary_parent_ids", ())
            ),
            "consumer_ids": sorted(str(item) for item in row.get("consumer_ids", ())),
            "producer_id": producer_id,
            "consumer_id": consumer_id,
            "relation_kind": relation_kind,
            "purpose_closure_fingerprint": str(
                purpose.get("closure_fingerprint", "")
            ),
        }
        schema_fingerprint = fingerprint_value(
            {"schema": "semantic-handoff", **relation_source}
        )
        relation_evidence = fingerprint_value(
            {"evidence": "checked-in-semantic-relation", **relation_source}
        )
        producer_output_id = f"output:{relation_id}"
        consumer_input_id = f"input:{relation_id}"
        schema_id = f"schema:{relation_id}"
        output_ports_by_node.setdefault(producer_id, []).append(
            BlueprintTopologyPort(
                port_id=producer_output_id,
                schema_id=schema_id,
                schema_fingerprint=schema_fingerprint,
            )
        )
        input_ports_by_node.setdefault(consumer_id, []).append(
            BlueprintTopologyPort(
                port_id=consumer_input_id,
                schema_id=schema_id,
                schema_fingerprint=schema_fingerprint,
            )
        )
        relation_rows.append(
            BlueprintTopologyRelation(
                relation_id=relation_id,
                producer_id=producer_id,
                consumer_id=consumer_id,
                relation_kind=relation_kind,
                interface_mappings=(
                    BlueprintTopologyPortMapping(
                        producer_output_id=producer_output_id,
                        consumer_input_id=consumer_input_id,
                    ),
                ),
                evidence_fingerprint=relation_evidence,
                consumed_child_evidence_id=(
                    child_evidence_ids[model_id]
                    if relation_kind == "child_to_parent"
                    else ""
                ),
                consumed_runtime_path_evidence_ids=(),
                progress_contract=progress_by_relation.get(relation_id),
                rationale=(
                    "typed projection of the exact checked-in semantic parent relation"
                    if relation_kind == "child_to_parent"
                    else (
                        "typed projection of an exact non-structural cross-boundary semantic relation"
                        if relation_kind == "cross_boundary_support"
                        else "typed projection of the exact checked-in semantic consumer relation"
                    )
                ),
            )
        )
        current_relation_fingerprints.append((relation_id, relation_evidence))

    nodes: dict[str, BlueprintTopologyNode] = {
        topology_root_id: BlueprintTopologyNode(
            node_id=topology_root_id,
            disposition="connected",
            structural_role="root",
            purpose="own the sole structural root of FlowGuard's current self topology",
            structural_parent_id=TOPOLOGY_ROOT_SENTINEL,
            input_ports=tuple(input_ports_by_node.get(topology_root_id, ())),
        )
    }
    for parent_id, parent in sorted(semantic_parent_rows.items()):
        nodes[parent_id] = BlueprintTopologyNode(
            node_id=parent_id,
            disposition="connected",
            structural_role="child",
            purpose=str(parent.get("purpose", "semantic parent")),
            structural_parent_id=topology_root_id,
            input_ports=tuple(input_ports_by_node.get(parent_id, ())),
            output_ports=tuple(output_ports_by_node.get(parent_id, ())),
        )

    surface_by_id = {row.surface_id: row for row in inventory.surfaces}
    child_models: list[ChildModelEvidence] = []
    reattachment_contracts: list[ChildReattachmentContract] = []
    for model_id, owner in sorted(owner_by_model.items()):
        row = mesh_rows.get(model_id, {})
        owned_surfaces = tuple(
            surface_by_id[surface_id]
            for surface_id in owner.implementation_surface_ids
            if surface_id in surface_by_id
        )
        state_owned = tuple(
            sorted(
                {
                    f"state:{surface.surface_id}:{field_id}"
                    for surface in owned_surfaces
                    for field_id in (*surface.state_reads, *surface.state_writes)
                }
            )
        )
        side_effects_owned = tuple(
            sorted(
                {
                    f"effect:{surface.surface_id}:{effect_id}"
                    for surface in owned_surfaces
                    for effect_id in surface.side_effect_candidates
                }
            )
        )
        input_ports = tuple(input_ports_by_node.get(owner.model_element_id, ()))
        output_ports = tuple(output_ports_by_node.get(owner.model_element_id, ()))
        nodes[owner.model_element_id] = BlueprintTopologyNode(
            node_id=owner.model_element_id,
            disposition=str(row.get("disposition", "scoped_out")),
            structural_role="child",
            purpose=str(
                row.get(
                    "rationale",
                    "model exists in the current owner inventory but is absent from the semantic mesh",
                )
            ),
            structural_parent_id=str(row.get("structural_parent_id", "")),
            cross_boundary_parent_ids=tuple(
                str(value)
                for value in row.get("cross_boundary_parent_ids", ())
            ),
            implementation_surface_ids=owner.implementation_surface_ids,
            input_ports=input_ports,
            output_ports=output_ports,
            state_owned=state_owned,
            side_effects_owned=side_effects_owned,
        )
        purpose = entries.get(model_id, {}).get("purpose_closure", {})
        if not isinstance(purpose, Mapping):
            purpose = {}
        child_evidence_id = child_evidence_ids[model_id]
        child = ChildModelEvidence(
            model_id=owner.model_element_id,
            evidence_id=child_evidence_id,
            risk_boundary=str(purpose.get("claim_boundary", "")),
            functions_owned=owner.implementation_surface_ids,
            inputs_accepted=tuple(port.port_id for port in input_ports),
            outputs_emitted=tuple(port.port_id for port in output_ports),
            state_owned=state_owned,
            side_effects_owned=side_effects_owned,
            functional_areas=tuple(
                item
                for item in (
                    str(row.get("structural_parent_id", "")),
                    *(
                        str(value)
                        for value in row.get(
                            "cross_boundary_parent_ids", ()
                        )
                    ),
                )
                if item
            ),
            invariants_owned=owner.portable_invariant_ids,
            contracts_in=owner.portable_assumption_ids,
            contracts_out=owner.portable_guarantee_ids,
            evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            evidence_current=True,
            not_run_checks=(),
            validation_evidence=(child_evidence_id,),
            runtime_path_evidence_ids=(),
        )
        child_models.append(child)
        reattachment_contracts.append(
            ChildReattachmentContract(
                child_model_id=owner.model_element_id,
                consumed_evidence_id=child_evidence_id,
                consumed_runtime_path_evidence_ids=(),
                expected_inputs=child.inputs_accepted,
                expected_outputs=child.outputs_emitted,
                expected_state_owned=child.state_owned,
                expected_side_effects_owned=child.side_effects_owned,
                expected_contracts_out=child.contracts_out,
                rationale=(
                    "current reattachment consumes this child's independently verified "
                    "model-owner receipt; the full parent proves only composition"
                ),
            )
        )

    for consumer_id in sorted(external_consumers):
        nodes[consumer_id] = BlueprintTopologyNode(
            node_id=consumer_id,
            disposition="intentional_leaf",
            structural_role="external",
            purpose="terminal claim consumer outside the model-owner inventory",
            structural_parent_id=topology_root_id,
            input_ports=tuple(input_ports_by_node.get(consumer_id, ())),
            output_ports=tuple(output_ports_by_node.get(consumer_id, ())),
        )

    # Mapped schemas are identical, so portable refinement receipts are not needed.
    # Child and feedback evidence remain external to the semantic declaration: the
    # mesh supplies topology, while current receipts and authority activation supply
    # proof.
    return (
        tuple(nodes.values()),
        tuple(relation_rows),
        tuple(child_models),
        tuple(reattachment_contracts),
        tuple(current_relation_fingerprints),
        (),
        tuple(sorted(current_progress_by_contract.items())),
        current_child_evidence_fingerprints,
    )


def _native_evidence_artifacts(
    entries: Mapping[str, Mapping[str, Any]],
) -> tuple[ProjectEvidenceArtifact, ...]:
    artifacts: list[ProjectEvidenceArtifact] = []
    for owner, entry in sorted(entries.items()):
        purpose = entry.get("purpose_closure", {})
        runner = next(
            (
                str(item)
                for item in entry.get("runner", ())
                if str(item) != "{python}"
            ),
            "",
        )
        if not runner or not isinstance(purpose, Mapping):
            raise FlowGuardSelfBlueprintError(
                f"self-blueprint owner native evidence is incomplete: {owner}"
            )
        for evidence_id in purpose.get("evidence_check_ids", ()):
            artifacts.append(
                ProjectEvidenceArtifact(
                    evidence_id=str(evidence_id),
                    artifact_path=runner,
                    artifact_fingerprint=str(purpose.get("runner_sha256", "")),
                    kind="native_model_check",
                )
            )
    return tuple(artifacts)


def _load_self_accepted_revision(
    root: Path,
    *,
    observed_snapshot_fingerprint: str,
    authority: Mapping[str, Any],
) -> ModelRevisionSet:
    """Load the sole accepted revision consumed by every self projection."""

    revision_fingerprint = str(
        authority.get("accepted_revision_set_fingerprint", "")
    )
    revision_digest = revision_fingerprint.removeprefix("sha256:")
    if (
        not revision_fingerprint.startswith("sha256:")
        or len(revision_digest) != 64
        or any(character not in "0123456789abcdef" for character in revision_digest)
    ):
        raise FlowGuardSelfBlueprintError(
            "FlowGuard self-blueprint has no canonical accepted revision"
        )
    revision_path = (
        root
        / ".flowguard/model-mesh/revisions"
        / f"{revision_digest}.json"
    )
    try:
        revision = ModelRevisionSet.from_dict(_load_json_object(revision_path))
    except ValueError as exc:
        raise FlowGuardSelfBlueprintError(
            f"canonical accepted revision is invalid: {exc}"
        ) from exc
    if revision.fingerprint != revision_fingerprint:
        raise FlowGuardSelfBlueprintError(
            "accepted revision-set fingerprint does not match canonical authority"
        )
    if revision.status != REVISION_ACCEPTED:
        raise FlowGuardSelfBlueprintError(
            "canonical authority does not reference an accepted revision set"
        )
    if (
        not observed_snapshot_fingerprint
        or revision.candidate_snapshot_fingerprint
        != observed_snapshot_fingerprint
    ):
        raise FlowGuardSelfBlueprintError(
            "accepted revision does not match the observed model snapshot"
        )
    return revision


def _self_intent_inventory(
    root: Path,
    *,
    observed_snapshot_fingerprint: str,
    model_target_ids: Sequence[str],
    authority: Mapping[str, Any],
    accepted_revision: ModelRevisionSet | None = None,
) -> ProjectIntentInventory:
    """Project the complete current-effective intent view to exact model owners.

    The accepted revision's delta remains useful revision evidence, but it is
    not the current design inventory.  Self qualification therefore consumes
    only ``current_effective_intent_view`` and preserves its independently
    derived model-owner denominator and contribution bindings without trying
    to infer owners from target words, changed relations, history, or a root
    model.
    """

    revision = accepted_revision
    if revision is None:
        revision = _load_self_accepted_revision(
            root,
            observed_snapshot_fingerprint=observed_snapshot_fingerprint,
            authority=authority,
        )
    if (
        revision.fingerprint
        != str(authority.get("accepted_revision_set_fingerprint", ""))
        or revision.status != REVISION_ACCEPTED
        or revision.candidate_snapshot_fingerprint
        != observed_snapshot_fingerprint
    ):
        raise FlowGuardSelfBlueprintError(
            "supplied accepted revision does not match current self authority"
        )
    view = revision.current_effective_intent_view
    if view is None or not view.complete:
        raise FlowGuardSelfBlueprintError(
            "canonical accepted revision has no complete current effective intent view"
        )
    if view.candidate_snapshot_fingerprint != observed_snapshot_fingerprint:
        raise FlowGuardSelfBlueprintError(
            "current effective intent view does not match the observed model snapshot"
        )

    raw_model_target_ids = tuple(
        str(target_id).strip()
        for target_id in model_target_ids
        if str(target_id).strip()
    )
    if (
        not raw_model_target_ids
        or len(raw_model_target_ids) != len(set(raw_model_target_ids))
        or any(
            not target_id.startswith("model-obligation:")
            for target_id in raw_model_target_ids
        )
    ):
        raise FlowGuardSelfBlueprintError(
            "self-blueprint model-owner denominator is empty, duplicated, or untyped"
        )
    manifest_model_target_ids = tuple(sorted(raw_model_target_ids))
    manifest_model_target_set = set(manifest_model_target_ids)

    owner_binding_by_id: dict[str, Any] = {}
    contribution_binding_by_id: dict[str, Any] = {}
    for binding in view.owner_bindings:
        owner_id = str(binding.model_owner_id).strip()
        logical_model_id = str(binding.logical_model_id).strip().removeprefix(
            "model:"
        )
        expected_owner_id = f"model-obligation:{logical_model_id}"
        if not logical_model_id or owner_id != expected_owner_id:
            raise FlowGuardSelfBlueprintError(
                "current effective intent uses a cross-owner or root fallback "
                f"binding: {owner_id or '<missing>'} -> "
                f"{logical_model_id or '<missing>'}"
            )
        if owner_id in owner_binding_by_id:
            raise FlowGuardSelfBlueprintError(
                "current effective intent duplicates one model-owner binding: "
                f"{owner_id}"
            )
        owner_binding_by_id[owner_id] = binding
        contribution_ids = tuple(
            str(contribution_id).strip()
            for contribution_id in binding.contribution_ids
            if str(contribution_id).strip()
        )
        if not contribution_ids:
            raise FlowGuardSelfBlueprintError(
                "current effective intent model owner has no direct current "
                f"design contribution: {owner_id}"
            )
        for contribution_id in contribution_ids:
            if contribution_id in contribution_binding_by_id:
                raise FlowGuardSelfBlueprintError(
                    "current effective intent contribution binds more than one "
                    f"model owner: {contribution_id}"
                )
            contribution_binding_by_id[contribution_id] = binding

    view_model_target_ids = tuple(
        sorted(str(owner_id).strip() for owner_id in view.model_owner_ids)
    )
    binding_model_target_ids = tuple(sorted(owner_binding_by_id))
    if (
        view_model_target_ids != manifest_model_target_ids
        or binding_model_target_ids != manifest_model_target_ids
    ):
        view_model_target_set = set(view_model_target_ids)
        binding_model_target_set = set(binding_model_target_ids)
        raise FlowGuardSelfBlueprintError(
            "current effective intent owner denominator does not exactly match "
            "the current self-blueprint model manifest; "
            "view_missing="
            f"{sorted(manifest_model_target_set - view_model_target_set)!r}, "
            "view_extra="
            f"{sorted(view_model_target_set - manifest_model_target_set)!r}, "
            "binding_missing="
            f"{sorted(manifest_model_target_set - binding_model_target_set)!r}, "
            "binding_extra="
            f"{sorted(binding_model_target_set - manifest_model_target_set)!r}"
        )
    required_model_target_ids = view_model_target_ids

    active_contributions = tuple(view.active_contributions)
    active_contribution_ids = tuple(
        str(contribution.contribution_id) for contribution in active_contributions
    )
    if (
        not active_contributions
        or len(active_contribution_ids) != len(set(active_contribution_ids))
    ):
        raise FlowGuardSelfBlueprintError(
            "current effective intent view has no unique active contributions"
        )
    source_by_contribution_id = {
        str(source.contribution_id): source
        for source in view.verified_source_identities
    }
    if (
        len(source_by_contribution_id)
        != len(tuple(view.verified_source_identities))
        or set(source_by_contribution_id) != set(active_contribution_ids)
        or set(contribution_binding_by_id) != set(active_contribution_ids)
    ):
        raise FlowGuardSelfBlueprintError(
            "current effective intent view does not bind every active contribution "
            "to exactly one verified source and one model owner"
        )

    contributions: list[ProjectIntentContribution] = []
    source_authorities: list[IntentSourceAuthority] = []
    for contribution in active_contributions:
        contribution_id = str(contribution.contribution_id)
        if contribution.decision_state != "accepted":
            raise FlowGuardSelfBlueprintError(
                "current effective intent contains a contribution that is not "
                f"accepted: {contribution_id}"
            )
        binding = contribution_binding_by_id[contribution_id]
        logical_model_id = str(contribution.logical_model_id).strip().removeprefix(
            "model:"
        )
        expected_owner_id = f"model-obligation:{logical_model_id}"
        if (
            not logical_model_id
            or str(contribution.unresolved_owner_id).strip()
            or binding.logical_model_id != logical_model_id
            or binding.model_owner_id != expected_owner_id
        ):
            raise FlowGuardSelfBlueprintError(
                "current effective intent contribution is cross-bound or uses a "
                f"fallback owner: {contribution_id} -> {binding.model_owner_id}"
            )
        source = source_by_contribution_id[contribution_id]
        if (
            source.source_ref != contribution.source_ref
            or source.source_fingerprint != contribution.source_fingerprint
            or source.native_owner_id != contribution.native_owner_id
        ):
            raise FlowGuardSelfBlueprintError(
                "current effective intent verified source does not match its "
                f"active contribution: {contribution_id}"
            )
        exact_targets = (expected_owner_id,)
        source_owner_id = (
            source.native_owner_id
            or contribution.native_owner_id
            or "flowguard-model-intent-v1"
        )
        expectation_id = f"expectation:{contribution_id}"
        expectation_fingerprint = fingerprint_value(
            {
                "current_effective_intent_view_fingerprint": view.fingerprint,
                "contribution_fingerprint": contribution.fingerprint,
                "verified_source_identity_fingerprint": source.fingerprint,
                "owner_binding_fingerprint": binding.fingerprint,
                "disposition": "accepted",
            }
        )
        contributions.append(
            ProjectIntentContribution(
                contribution_id=contribution_id,
                source_kind=contribution.source_kind,
                source_id=source.source_ref,
                source_owner_id=source_owner_id,
                source_fingerprint=source.source_fingerprint,
                expectation_id=expectation_id,
                expectation_fingerprint=expectation_fingerprint,
                disposition="accepted",
                target_ids=exact_targets,
                rationale=contribution.rationale,
            )
        )
        source_authorities.append(
            IntentSourceAuthority(
                source_kind=contribution.source_kind,
                source_id=source.source_ref,
                source_owner_id=source_owner_id,
                subject_revision=observed_snapshot_fingerprint,
                current_source_fingerprint=source.source_fingerprint,
                expectation_id=expectation_id,
                current_expectation_fingerprint=expectation_fingerprint,
                target_ids=exact_targets,
                provider_id="flowguard-model-intent-v1",
                capability_id="intent_lineage",
                payload_id="intent_lineage",
            )
        )
    if not contributions:
        raise FlowGuardSelfBlueprintError(
            "FlowGuard self-blueprint canonical revision has no admitted intent"
        )
    return ProjectIntentInventory(
        inventory_id="intent-inventory:flowguard:self",
        subject_revision=observed_snapshot_fingerprint,
        observed_subject_revision=observed_snapshot_fingerprint,
        contributions=tuple(contributions),
        source_authorities=tuple(source_authorities),
        authority_provider_capabilities=(
            ("flowguard-model-intent-v1", "intent_lineage"),
        ),
        required_model_target_ids=required_model_target_ids,
    )


def _self_path_quality_bindings(
    revision: ModelRevisionSet,
    *,
    observed_snapshot_fingerprint: str,
    owners: Sequence[ProjectBlueprintOwner],
) -> tuple[ModelPathQualityBlueprintBinding, ...]:
    """Project accepted current path evidence onto blueprint owner identities.

    The accepted revision remains authoritative.  This function only replaces
    the provider-local logical model id and model-instance fingerprint with the
    equivalent blueprint model-obligation id and its owner closure fingerprint.
    Compact conclusions and referenced deep-evidence identities are preserved.
    """

    if (
        revision.status != REVISION_ACCEPTED
        or revision.candidate_snapshot_fingerprint
        != observed_snapshot_fingerprint
    ):
        raise FlowGuardSelfBlueprintError(
            "path-quality revision is not the accepted observed snapshot"
        )
    required_ids = tuple(revision.required_path_quality_model_ids)
    if (
        not required_ids
        or required_ids != tuple(sorted(required_ids))
        or len(required_ids) != len(set(required_ids))
    ):
        raise FlowGuardSelfBlueprintError(
            "accepted path-quality denominator is empty, duplicated, or non-canonical"
        )

    subjects_by_model = {
        subject.model_id: subject for subject in revision.path_quality_subjects
    }
    results_by_subject = {
        result.subject_fingerprint: result
        for result in revision.path_quality_results
    }
    if (
        len(subjects_by_model) != len(tuple(revision.path_quality_subjects))
        or len(results_by_subject) != len(tuple(revision.path_quality_results))
        or set(subjects_by_model) != set(required_ids)
        or set(results_by_subject)
        != {subjects_by_model[model_id].fingerprint for model_id in required_ids}
    ):
        raise FlowGuardSelfBlueprintError(
            "accepted path-quality material is missing, duplicated, or foreign"
        )

    owner_by_model_element_id = {
        owner.model_element_id: owner for owner in owners
    }
    expected_owner_ids = {
        f"model-obligation:{logical_model_id}"
        for logical_model_id in required_ids
    }
    if (
        len(owner_by_model_element_id) != len(tuple(owners))
        or set(owner_by_model_element_id) != expected_owner_ids
    ):
        raise FlowGuardSelfBlueprintError(
            "accepted path-quality denominator does not exactly match blueprint owners"
        )

    added_ids = set(revision.added_ids)
    fingerprint_changed_ids = set(revision.fingerprint_changed_ids)
    bindings: list[ModelPathQualityBlueprintBinding] = []
    for logical_model_id in required_ids:
        subject = subjects_by_model[logical_model_id]
        result = results_by_subject[subject.fingerprint]
        if (
            subject.currentness_id != observed_snapshot_fingerprint
            or result.currentness_id != observed_snapshot_fingerprint
            or not result.current
            or result.conclusion == "unresolved"
            or result.unresolved_ids
            or result.selected_candidate_lane == "normative_target"
        ):
            raise FlowGuardSelfBlueprintError(
                "accepted path-quality row is stale or unresolved: "
                f"{logical_model_id}"
            )

        model_element_id = f"model-obligation:{logical_model_id}"
        owner = owner_by_model_element_id[model_element_id]
        instance_object_id = f"model_instance:model:{logical_model_id}"
        is_added = instance_object_id in added_ids
        is_fingerprint_changed = (
            instance_object_id in fingerprint_changed_ids
        )
        if is_added and is_fingerprint_changed:
            raise FlowGuardSelfBlueprintError(
                "accepted revision classifies one model instance as both added "
                f"and fingerprint-changed: {logical_model_id}"
            )
        if is_added:
            change_kind = "new"
        elif is_fingerprint_changed:
            change_kind = "materially_changed"
        else:
            change_kind = "unchanged"

        try:
            projected_subject = replace(
                subject,
                model_id=model_element_id,
                model_fingerprint=owner.model_fingerprint,
                currentness_id=observed_snapshot_fingerprint,
            )
            projected_result = replace(
                result,
                subject_fingerprint=projected_subject.fingerprint,
                currentness_id=observed_snapshot_fingerprint,
            )
        except ValueError as exc:
            raise FlowGuardSelfBlueprintError(
                "accepted path-quality row cannot be projected onto its exact "
                f"blueprint owner: {logical_model_id}: {exc}"
            ) from exc
        if (
            projected_result.detail_evidence_fingerprint
            != result.detail_evidence_fingerprint
        ):
            raise FlowGuardSelfBlueprintError(
                "provider-neutral path-quality projection lost detail evidence"
            )
        unchanged = change_kind == "unchanged"
        try:
            bindings.append(
                ModelPathQualityBlueprintBinding(
                    model_element_id=model_element_id,
                    subject_lane="observed",
                    change_kind=change_kind,
                    subject=projected_subject,
                    result=projected_result,
                    affected_topology_evidence_fingerprint=(
                        revision.affected_closure_fingerprint if unchanged else ""
                    ),
                    affected_topology_currentness_id=(
                        observed_snapshot_fingerprint if unchanged else ""
                    ),
                )
            )
        except ValueError as exc:
            raise FlowGuardSelfBlueprintError(
                "accepted path-quality binding is not exact-current: "
                f"{logical_model_id}: {exc}"
            ) from exc
    return tuple(bindings)


def _require_current_model_authority(
    root: Path,
) -> ModelAuthorityAuditReport:
    """Require the self-blueprint to consume current, revision-backed authority."""

    report = audit_model_authority(root)
    if report.ok:
        return report
    details = "; ".join(
        f"{finding.code}: {finding.message}"
        for finding in report.findings
    ) or "model authority audit returned no terminal finding"
    raise FlowGuardSelfBlueprintError(
        "FlowGuard self-blueprint model authority is not exact-current: "
        + details
    )


def _self_blueprint_provider_contract_fingerprint() -> str:
    return fingerprint_value(
        {
            "implementation_provider": PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
            "test_provider": PYTHON_AST_TEST_ADAPTER_ID,
            "resource_provider": "flowguard-resource-manifest-v1",
            "model_authority_provider": "flowguard-observed-model-system-v1",
            "model_purpose_provider": "flowguard-model-purpose-closure-v1",
            "intent_provider": "flowguard-model-intent-v1",
            "portable_model_provider": "flowguard-portable-model-v1",
            "member_scope_provider": "flowguard-owner-composite-member-scope-v1",
            "definition_schema": SELF_BLUEPRINT_DEFINITION_SCHEMA,
        }
    )


def _consumed_self_blueprint_build_input_identity(
    *,
    authority_report: ModelAuthorityAuditReport,
    authority: Mapping[str, Any],
    definition: Mapping[str, Any],
    boundary: SoftwareBoundary,
    files: Sequence[ImplementationFileDisposition],
    semantic_mesh: Mapping[str, Any],
    model_regression_evidence: CurrentModelRegressionParentEvidence,
) -> SelfBlueprintBuildInputIdentity:
    subject_revision = str(authority.get("subject_revision", ""))
    observed_snapshot_fingerprint = str(
        authority.get("observed_snapshot_fingerprint", "")
    )
    accepted_revision_set_fingerprint = str(
        authority.get("accepted_revision_set_fingerprint", "")
    )
    activation_receipt_fingerprint = str(
        authority.get("activation_receipt_fingerprint", "")
    )
    if not all(
        (
            subject_revision,
            observed_snapshot_fingerprint,
            accepted_revision_set_fingerprint,
            activation_receipt_fingerprint,
        )
    ):
        raise FlowGuardSelfBlueprintError(
            "observed model authority build inputs are incomplete"
        )
    return SelfBlueprintBuildInputIdentity(
        subject_revision=subject_revision,
        model_authority_audit_fingerprint=fingerprint_value(
            authority_report.to_dict()
        ),
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        accepted_revision_set_fingerprint=accepted_revision_set_fingerprint,
        definition_fingerprint=fingerprint_value(definition),
        boundary_fingerprint=boundary.fingerprint,
        file_inventory_fingerprint=fingerprint_value(
            [row.to_dict() for row in files]
        ),
        file_count=len(files),
        semantic_mesh_fingerprint=fingerprint_value(semantic_mesh),
        activation_receipt_fingerprint=activation_receipt_fingerprint,
        model_regression_evidence_fingerprint=fingerprint_value(
            model_regression_evidence.to_dict()
        ),
        provider_contract_fingerprint=(
            _self_blueprint_provider_contract_fingerprint()
        ),
    )


def capture_flowguard_self_blueprint_build_input_identity(
    root: str | Path,
) -> SelfBlueprintBuildInputIdentity:
    """Recompute exact builder inputs without materializing the full blueprint.

    The file inventory uses the same boundary classifier and content hashes as
    the real builder.  Excluded content-addressed model artifacts remain bound
    through the independently audited authority head and accepted revision.
    """

    root_path = Path(root).resolve()
    authority_report = _require_current_model_authority(root_path)
    definition = load_flowguard_self_blueprint_definition(root_path)
    project_path = root_path / ".flowguard/project.toml"
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    authority = project.get("model_authority", {})
    if not isinstance(authority, Mapping):
        raise FlowGuardSelfBlueprintError(
            "observed model authority section must be a mapping"
        )
    subject_revision = str(authority.get("subject_revision", ""))
    observed_snapshot_fingerprint = str(
        authority.get("observed_snapshot_fingerprint", "")
    )
    accepted_revision_set_fingerprint = str(
        authority.get("accepted_revision_set_fingerprint", "")
    )
    if not all(
        (
            subject_revision,
            observed_snapshot_fingerprint,
            accepted_revision_set_fingerprint,
        )
    ):
        raise FlowGuardSelfBlueprintError(
            "observed model authority build inputs are incomplete"
        )
    resolved_manifest = resolve_input_manifest(root_path, ("**/*", "*"))
    boundary, categories = _boundary_from_definition(
        root_path,
        definition,
        subject_revision=subject_revision,
        resolved_manifest=resolved_manifest,
    )
    files = _file_dispositions(
        root_path,
        definition,
        categories,
        resolved_manifest=resolved_manifest,
    )
    semantic_mesh = _load_json_object(
        root_path
        / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    )
    try:
        model_regression_evidence = resolve_current_full_model_regression_parent(
            root_path
        )
    except ModelRegressionEvidenceError as exc:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint build-input capture lacks independently verified "
            f"current model evidence: {exc}"
        ) from exc
    return _consumed_self_blueprint_build_input_identity(
        authority_report=authority_report,
        authority=authority,
        definition=definition,
        boundary=boundary,
        files=files,
        semantic_mesh=semantic_mesh,
        model_regression_evidence=model_regression_evidence,
    )


def _validate_self_blueprint_materialization_invariants(bundle: Any) -> None:
    """Fail if the real self model grows by cross-product or loses a surface."""

    inventory = bundle.inventory
    behavior_report = bundle.behavior_report
    required_surface_ids = set(inventory.required_surface_ids)
    classified_required_ids = {
        surface.surface_id
        for surface in inventory.surfaces
        if surface.disposition
        in {
            IMPLEMENTATION_DISPOSITION_MODEL,
            IMPLEMENTATION_DISPOSITION_SUPPORTING,
        }
    }
    if required_surface_ids != classified_required_ids:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint required surfaces are not exactly partitioned into "
            "behavior and supporting dispositions"
        )
    expected_behavior_ids = set(implementation_behavior_surface_ids(inventory))
    contract_by_surface = {
        contract.implementation_surface_id: contract
        for contract in behavior_report.contracts
    }
    if set(contract_by_surface) != expected_behavior_ids:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint behavior contracts do not exactly match behavior surfaces"
        )
    expected_supporting_ids = {
        surface.surface_id
        for surface in inventory.surfaces
        if surface.surface_id in required_surface_ids
        and surface.surface_id not in expected_behavior_ids
    }
    if set(behavior_report.supporting_surface_ids) != expected_supporting_ids:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint supporting behavior denominator is not exact-current"
        )
    surface_by_id = {
        surface.surface_id: surface for surface in inventory.surfaces
    }
    relations_by_surface: dict[str, list[Any]] = {}
    for relation in behavior_report.supporting_relations:
        relations_by_surface.setdefault(
            relation.supporting_surface_id, []
        ).append(relation)
    if set(relations_by_surface) != expected_supporting_ids or any(
        len(relations_by_surface[surface_id]) != 1
        or relations_by_surface[surface_id][0].behavior_block_id
        != f"behavior-block:{surface_by_id[surface_id].owning_surface_id}"
        for surface_id in expected_supporting_ids
    ):
        raise FlowGuardSelfBlueprintError(
            "self-blueprint supporting relations do not match exact provider owners"
        )
    for contract in behavior_report.contracts:
        if len(contract.dimensions) != len(BEHAVIOR_DIMENSIONS) or any(
            dimension.applicability_surface_ids
            != (contract.implementation_surface_id,)
            for dimension in contract.dimensions
        ):
            raise FlowGuardSelfBlueprintError(
                "self-blueprint behavior dimension applicability is not block-local"
            )
    cases_by_block: dict[str, list[BehaviorCaseContract]] = {}
    for case in behavior_report.case_contracts:
        cases_by_block.setdefault(case.behavior_block_id, []).append(case)
    expected_case_count = 0
    for contract in behavior_report.contracts:
        cases = cases_by_block.get(contract.behavior_block_id, [])
        kinds = [case.case_kind for case in cases]
        expected_count = 2 + len(contract.protected_failure_ids)
        expected_case_count += expected_count
        protected_failures = {
            failure_id
            for case in cases
            if case.case_kind == "bad"
            for failure_id in case.protected_failure_ids
        }
        if (
            len(cases) != expected_count
            or kinds.count("good") != 1
            or kinds.count("boundary") != 1
            or kinds.count("bad") != len(contract.protected_failure_ids)
            or protected_failures != set(contract.protected_failure_ids)
            or any(
                case.parameter_case_id != case.case_id or not case.source_case_id
                for case in cases
            )
        ):
            raise FlowGuardSelfBlueprintError(
                "self-blueprint case materialization is not block-local and exact"
            )
    if len(behavior_report.case_contracts) != expected_case_count:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint case count is not the sum of block-local obligations"
        )
    if len(behavior_report.coverage_edges) != 6 * expected_case_count:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint coverage count is not linear in block-local cases"
        )
    coverage_ids = {
        row.coverage_id for row in behavior_report.coverage_edges
    }
    stored_coverage_ids = {
        str(object_id)
        for object_id, payload in bundle.normalized_shared_objects
        if isinstance(payload, Mapping)
        and payload.get("kind") == "behavior_coverage_edge"
    }
    shard_coverage_ids = {
        str(coverage_id)
        for _shard_id, payload in bundle.normalized_shards
        if isinstance(payload, Mapping)
        for coverage_id in payload.get("coverage_ids", ())
    }
    if not (coverage_ids == stored_coverage_ids == shard_coverage_ids):
        raise FlowGuardSelfBlueprintError(
            "self-blueprint normalized coverage ownership is not exact"
        )


def build_flowguard_self_blueprint(
    root: str | Path,
) -> FlowGuardSelfBlueprintBundle:
    root_path = Path(root).resolve()
    authority_report = _require_current_model_authority(root_path)
    definition = load_flowguard_self_blueprint_definition(root_path)
    project = tomllib.loads((root_path / ".flowguard/project.toml").read_text(encoding="utf-8"))
    authority = project.get("model_authority", {})
    subject_revision = str(authority.get("subject_revision", ""))
    if not subject_revision:
        raise FlowGuardSelfBlueprintError("observed model authority subject revision is missing")
    observed_snapshot_fingerprint = str(
        authority.get("observed_snapshot_fingerprint", "")
    ).strip()
    if not observed_snapshot_fingerprint:
        raise FlowGuardSelfBlueprintError(
            "observed model authority snapshot fingerprint is missing"
        )
    resolved_manifest = resolve_input_manifest(root_path, ("**/*", "*"))
    boundary, categories = _boundary_from_definition(
        root_path,
        definition,
        subject_revision=subject_revision,
        resolved_manifest=resolved_manifest,
    )
    files = _file_dispositions(
        root_path,
        definition,
        categories,
        resolved_manifest=resolved_manifest,
    )
    _manifest_payload, entries = _manifest_entries(root_path)
    accepted_revision = _load_self_accepted_revision(
        root_path,
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        authority=authority,
    )
    overrides = {
        str(key): str(value)
        for key, value in dict(definition["owner_overrides"]).items()
    }
    composite_contracts = _declared_owner_composite_contracts(
        definition,
        entries,
    )
    (
        surface_dispositions,
        supporting_owners,
        dynamic_allowances,
        dynamic_selector_contracts,
        implementation_observations,
    ) = _discover_surface_declarations(
        root_path,
        files,
        definition,
        entries,
        overrides,
        composite_contracts,
    )
    inventory = build_implementation_surface_inventory(
        root_path,
        boundary,
        inventory_id=str(definition["inventory_id"]),
        file_dispositions=files,
        surface_dispositions=surface_dispositions,
        supporting_owners=supporting_owners,
        dynamic_allowances=dynamic_allowances,
        discovery_results=implementation_observations,
        resolved_manifest=resolved_manifest,
        claim_boundary=str(definition["claim_boundary"]),
    )
    test_inventory = _flowguard_test_inventory(
        root_path,
        subject_revision=subject_revision,
    )
    intent_inventory = _self_intent_inventory(
        root_path,
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        model_target_ids=tuple(
            f"model-obligation:{model_id}"
            for model_id in sorted(entries)
        ),
        authority=authority,
        accepted_revision=accepted_revision,
    )
    owners = _project_owners(
        root_path,
        inventory,
        entries,
        overrides,
        composite_contracts,
        test_inventory,
        intent_inventory,
    )
    resources = _resources(root_path, definition, owners)
    observed_resources = _observed_resources(
        root_path,
        definition,
        resources,
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
    )
    path_quality_bindings = _self_path_quality_bindings(
        accepted_revision,
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        owners=owners,
    )
    semantic_mesh_path = root_path / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    semantic_mesh = _load_json_object(semantic_mesh_path)
    try:
        model_regression_evidence = resolve_current_full_model_regression_parent(
            root_path
        )
    except ModelRegressionEvidenceError as exc:
        raise FlowGuardSelfBlueprintError(
            "FlowGuard self-blueprint lacks one unique exact-current full model "
            f"parent with independently verified children: {exc}"
        ) from exc
    build_input_identity = _consumed_self_blueprint_build_input_identity(
        authority_report=authority_report,
        authority=authority,
        definition=definition,
        boundary=boundary,
        files=files,
        semantic_mesh=semantic_mesh,
        model_regression_evidence=model_regression_evidence,
    )
    (
        topology_nodes,
        topology_relations,
        topology_child_models,
        topology_reattachment_contracts,
        current_relation_evidence_fingerprints,
        current_refinement_fingerprints,
        current_progress_evidence_fingerprints,
        current_child_evidence_fingerprints,
    ) = _self_topology(
        semantic_mesh=semantic_mesh,
        owners=owners,
        entries=entries,
        inventory=inventory,
        model_regression_evidence=model_regression_evidence,
        activation_receipt_fingerprint=str(
            authority.get("activation_receipt_fingerprint", "")
        ),
    )
    portable_owner_fingerprints = (
        (
            "portable:compositional-verification-kernel",
            str(_purpose_value(entries["compositional_verification_kernel"], "closure_fingerprint", "")),
        ),
    )
    project_definition = ProjectBlueprintDefinition(
        blueprint_id=str(definition["blueprint_id"]),
        inventory_id=str(definition["inventory_id"]),
        boundary=boundary,
        file_dispositions=files,
        surface_dispositions=tuple(surface_dispositions.items()),
        supporting_owners=tuple(supporting_owners.items()),
        dynamic_allowances=tuple(dynamic_allowances.items()),
        dynamic_selector_contracts=dynamic_selector_contracts,
        owners=owners,
        claim_boundary=str(definition["claim_boundary"]),
        target_kind="software",
        target_profile=SOFTWARE_TARGET_PROFILE,
        observation_providers=(
            TargetSystemProviderDeclaration(
                provider_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                provider_role="observation",
                provider_kind="python_ast_implementation_inventory",
                provider_version="1",
                capability_ids=("implementation_inventory",),
                claim_boundary="FlowGuard Python implementation surfaces only.",
            ),
            TargetSystemProviderDeclaration(
                provider_id=PYTHON_AST_TEST_ADAPTER_ID,
                provider_role="observation",
                provider_kind="python_ast_test_inventory",
                provider_version="1",
                capability_ids=("test_inventory",),
                claim_boundary="FlowGuard Python test nodes only.",
            ),
            TargetSystemProviderDeclaration(
                provider_id="flowguard-resource-manifest-v1",
                provider_role="observation",
                provider_kind="declared_resource_inventory",
                provider_version="1",
                capability_ids=("resource_inventory",),
                claim_boundary="FlowGuard declared resource inventory only.",
            ),
        ),
        authority_providers=(
            TargetSystemProviderDeclaration(
                provider_id="flowguard-observed-model-system-v1",
                provider_role="authority",
                provider_kind="observed_model_system",
                provider_version="1",
                capability_ids=("model_authority", "model_topology"),
                claim_boundary="Current observed FlowGuard model authority only.",
            ),
            TargetSystemProviderDeclaration(
                provider_id="flowguard-model-purpose-closure-v1",
                provider_role="authority",
                provider_kind="model_purpose_closure",
                provider_version="1",
                capability_ids=("behavior_semantics", "oracle_inventory"),
                claim_boundary="Accepted FlowGuard behavior semantics and oracles only.",
            ),
            TargetSystemProviderDeclaration(
                provider_id="flowguard-model-intent-v1",
                provider_role="authority",
                provider_kind="model_intent_lineage",
                provider_version="1",
                capability_ids=("intent_lineage",),
                claim_boundary="Current FlowGuard intent lineage only.",
            ),
            TargetSystemProviderDeclaration(
                provider_id="flowguard-portable-model-v1",
                provider_role="authority",
                provider_kind="portable_model_kernel",
                provider_version="1",
                capability_ids=("portable_behavior",),
                claim_boundary="Current portable FlowGuard behavior kernel only.",
            ),
        ),
    )
    project_evidence = ProjectBlueprintEvidence(
        observed_snapshot_id=str(authority.get("observed_snapshot_path", "")),
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        semantic_mesh_id="flowguard-whole-system-understanding-v1",
        portable_owner_fingerprints=portable_owner_fingerprints,
        portable_member_catalogs=tuple(
            PortableModelMemberCatalog(
                portable_model_id=owner.portable_model_id,
                portable_model_fingerprint=owner.portable_model_fingerprint,
                transition_ids=owner.portable_transition_ids,
                property_ids=owner.portable_property_ids,
                invariant_ids=owner.portable_invariant_ids,
                input_field_ids=tuple(
                    sorted(
                        {
                            member_id
                            for binding in owner.portable_behavior_bindings
                            for _field, member_id in binding.input_field_mappings
                        }
                    )
                ),
                output_field_ids=tuple(
                    sorted(
                        {
                            member_id
                            for binding in owner.portable_behavior_bindings
                            for _field, member_id in binding.output_field_mappings
                        }
                    )
                ),
                state_field_ids=tuple(
                    sorted(
                        {
                            member_id
                            for binding in owner.portable_behavior_bindings
                            for _field, member_id in binding.state_field_mappings
                        }
                    )
                ),
                assumption_ids=owner.portable_assumption_ids,
                guarantee_ids=owner.portable_guarantee_ids,
                protected_failure_ids=owner.protected_failure_ids,
            )
            for owner in owners
        ),
        resources=resources,
        observed_resources=observed_resources,
        intent_inventory=intent_inventory,
        test_inventory=test_inventory,
        topology_nodes=topology_nodes,
        topology_relations=topology_relations,
        child_models=topology_child_models,
        reattachment_contracts=topology_reattachment_contracts,
        current_relation_evidence_fingerprints=(
            current_relation_evidence_fingerprints
        ),
        current_refinement_fingerprints=current_refinement_fingerprints,
        current_progress_evidence_fingerprints=(
            current_progress_evidence_fingerprints
        ),
        current_child_evidence_fingerprints=(
            current_child_evidence_fingerprints
        ),
        native_evidence_artifacts=_native_evidence_artifacts(entries),
        path_quality_bindings=path_quality_bindings,
    )
    delegated_assertion_helpers = _flowguard_delegated_assertion_helpers(
        root_path,
        test_inventory,
    )
    preparation = prepare_project_blueprint(
        root_path,
        project_definition,
        project_evidence,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
        },
        test_discovery_adapters={
            PYTHON_AST_TEST_ADAPTER_ID: discover_python_test_file
        },
        implementation_inventory=inventory,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints={
            row.helper_id: row.source_fingerprint
            for row in delegated_assertion_helpers
        },
    )
    provider_results = collect_project_blueprint_provider_results(preparation)
    frozen_target_evidence = freeze_project_blueprint_evidence(
        preparation, provider_results
    )
    bundle = _qualify_project_blueprint(
        preparation,
        frozen_target_evidence,
        affected_surface_ids=tuple(
            row.surface_id
            for row in preparation.inventory.surfaces
            if row.disposition == IMPLEMENTATION_DISPOSITION_MODEL
        ),
    )
    if not all(
        (
            bundle.behavior_report,
            bundle.resource_inventory,
            bundle.intent_inventory,
            bundle.normalized_projection,
            bundle.static_readiness,
            bundle.target_system_report,
            bundle.understanding_summary,
        )
    ):
        raise FlowGuardSelfBlueprintError(
            "project-neutral builder did not produce behavior readiness artifacts"
        )
    _validate_self_blueprint_materialization_invariants(bundle)
    return FlowGuardSelfBlueprintBundle(
        test_inventory=test_inventory,
        inventory=bundle.inventory,
        implementation_inventory_audit=bundle.implementation_inventory_audit,
        binding_report=bundle.binding_report,
        manifest=bundle.manifest,
        qualification=bundle.qualification,
        model_test_alignment_report=bundle.model_test_alignment_report,
        topology_report=bundle.topology_report,
        behavior_report=bundle.behavior_report,
        resource_inventory=bundle.resource_inventory,
        intent_inventory=bundle.intent_inventory,
        normalized_projection=bundle.normalized_projection,
        static_readiness=bundle.static_readiness,
        target_system_report=bundle.target_system_report,
        understanding_summary=bundle.understanding_summary,
        normalized_shared_objects=bundle.normalized_shared_objects,
        normalized_shards=bundle.normalized_shards,
        build_input_identity=build_input_identity,
        project_bundle=bundle,
    )


__all__ = [
    "DEFAULT_SELF_BLUEPRINT_DEFINITION",
    "SELF_BLUEPRINT_BUILD_INPUT_IDENTITY_SCHEMA",
    "SELF_BLUEPRINT_DEFINITION_SCHEMA",
    "FlowGuardSelfBlueprintBundle",
    "FlowGuardSelfBlueprintError",
    "SelfBlueprintBuildInputIdentity",
    "build_flowguard_self_blueprint",
    "capture_flowguard_self_blueprint_build_input_identity",
    "load_flowguard_self_blueprint_definition",
]
