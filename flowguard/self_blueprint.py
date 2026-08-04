"""FlowGuard's current self-blueprint composition.

The generic inventory and blueprint modules remain project-neutral.  This
module binds those owners to FlowGuard's checked-in declarative boundary,
model-regression purpose closures, semantic mesh, and test oracles.  It is a
derived view of the observed model system, never a second authority pointer.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase
import json
from pathlib import Path
import tomllib
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value
from .blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyRelation,
    BlueprintTopologyReport,
)
from .implementation_blueprint import (
    BlueprintResourceReference,
    ModelImplementationBindingReport,
    OracleReference,
    SemanticSpecReference,
    SEMANTIC_AUTHORITY_IMPORTED_MODEL,
    SoftwareBlueprintManifest,
    SoftwareBlueprintQualificationReport,
)
from .implementation_inventory import (
    IMPLEMENTATION_DISPOSITION_MODEL,
    IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
    IMPLEMENTATION_DISPOSITION_SUPPORTING,
    ImplementationFileDisposition,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    build_implementation_surface_inventory,
    implementation_surface_key,
)
from .implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
    discover_python_implementation_surfaces,
)
from .model_revision_set import ModelRevisionSet
from .model_test_alignment import ModelTestAlignmentReport
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
    build_project_blueprint,
    project_surface_dimensions,
)
from .software_blueprint_readiness import (
    AffectedBlueprintNeighborhood,
    BehaviorBlueprintReport,
    BehaviorCaseContract,
    DelegatedAssertionHelper,
    NormalizedBlueprintProjection,
    ProjectIntentContribution,
    ProjectIntentInventory,
    ProjectResourceInventory,
    StaticBlueprintReadinessReport,
    load_affected_behavior_neighborhood,
)
from .target_system_blueprint import (
    BlueprintUnderstandingSummary,
    TargetSystemBlueprintReport,
)
from .validation_ownership import resolve_input_manifest


SELF_BLUEPRINT_DEFINITION_SCHEMA = "flowguard.self_blueprint_definition.v1"
DEFAULT_SELF_BLUEPRINT_DEFINITION = (
    ".flowguard/authoritative_model_system/software_blueprint_definition.json"
)


class FlowGuardSelfBlueprintError(ValueError):
    """Raised when the checked-in self-blueprint definition cannot close."""


@dataclass(frozen=True)
class FlowGuardSelfBlueprintBundle:
    test_inventory: ProjectTestInventory
    inventory: ImplementationSurfaceInventory
    binding_report: ModelImplementationBindingReport
    manifest: SoftwareBlueprintManifest
    qualification: SoftwareBlueprintQualificationReport
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

    @property
    def ok(self) -> bool:
        return (
            self.qualification.static_status == "complete"
            and self.behavior_report.complete
            and self.static_readiness.status == "ready"
            and self.target_system_report.ok
        )

    def affected_neighborhood(
        self,
        *,
        affected_surface_ids: Sequence[str] = (),
        affected_behavior_block_ids: Sequence[str] = (),
    ) -> AffectedBlueprintNeighborhood:
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
            "test_inventory_fingerprint": self.test_inventory.inventory_fingerprint,
            "binding_report_fingerprint": self.binding_report.fingerprint,
            "blueprint_fingerprint": self.manifest.fingerprint,
            "qualification": self.qualification.to_static_dict(),
            "model_test_alignment_report_fingerprint": (
                self.model_test_alignment_report.fingerprint
            ),
            "topology_report_fingerprint": self.topology_report.fingerprint,
            "behavior_report_fingerprint": self.behavior_report.fingerprint,
            "resource_inventory_fingerprint": self.resource_inventory.fingerprint,
            "intent_inventory_fingerprint": self.intent_inventory.fingerprint,
            "normalized_projection_fingerprint": self.normalized_projection.fingerprint,
            "static_readiness": self.static_readiness.to_dict(),
            "target_system_report": self.target_system_report.to_dict(),
            "understanding_summary": self.understanding_summary.to_dict(),
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
        "owner_overrides",
        "resource_groups",
        "claim_boundary",
    }
    if set(value) != required:
        raise FlowGuardSelfBlueprintError(
            "self-blueprint definition fields are not exact-current"
        )
    return value


def _pattern_paths(root: Path, patterns: Sequence[str]) -> set[str]:
    return {row["path"] for row in resolve_input_manifest(root, tuple(patterns))}


def _boundary_from_definition(
    root: Path,
    definition: Mapping[str, Any],
    *,
    subject_revision: str,
) -> tuple[SoftwareBoundary, dict[str, str]]:
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
        for path in _pattern_paths(root, patterns):
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
) -> tuple[ImplementationFileDisposition, ...]:
    manifest = resolve_input_manifest(root, ("**/*", "*"))
    scan_paths = _pattern_paths(root, tuple(definition["scan_python_patterns"]))
    scoped_paths = _pattern_paths(root, tuple(definition["scoped_out_patterns"]))
    rows: list[ImplementationFileDisposition] = []
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
        rows.append(
            ImplementationFileDisposition(
                path=path,
                category=category,
                content_fingerprint=item["sha256"],
                disposition=disposition,
                reason=reason,
                requires_adapter=path in scan_paths,
                adapter_id=(PYTHON_AST_IMPLEMENTATION_ADAPTER_ID if path in scan_paths else ""),
            )
        )
    return tuple(rows)


def _discover_surface_declarations(
    root: Path,
    files: Sequence[ImplementationFileDisposition],
    definition: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    discovered: list[ImplementationSurface] = []
    for item in files:
        if not item.requires_adapter:
            continue
        result = discover_python_implementation_surfaces(
            root=root,
            file_disposition=item,
            surface_dispositions={},
        )
        discovered.extend(result.surfaces)
    dispositions = {
        implementation_surface_key(surface.path, surface.symbol):
        IMPLEMENTATION_DISPOSITION_MODEL
        for surface in discovered
    }
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
        if allowed:
            allowances[key] = tuple(sorted(allowed))
    return dispositions, allowances


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


def _project_owners(
    root: Path,
    inventory: ImplementationSurfaceInventory,
    entries: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, str],
    test_inventory: ProjectTestInventory,
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

    owners: list[ProjectBlueprintOwner] = []
    for owner, owner_surfaces in sorted(grouped.items()):
        entry = entries[owner]
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
        semantic = SemanticSpecReference(
            semantic_spec_id=f"semantic-spec:model-owner:{owner}",
            owner_id=f"model:{owner}",
            artifact_id=str(entry.get("model_path", f"model:{owner}")),
            artifact_fingerprint=closure_fingerprint,
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
        primary_surface = min(
            owner_surfaces,
            key=lambda surface: (
                0 if surface.path.startswith("flowguard/") else 1,
                0 if not surface.symbol.rsplit(".", 1)[-1].startswith("_") else 1,
                0 if surface.behavior_bearing else 1,
                surface.path,
                surface.symbol,
            ),
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
        semantic_member_prefix = f"semantic-member:{semantic.semantic_spec_id}"
        input_field_mappings = tuple(
            (parameter, f"{semantic_member_prefix}:input:{parameter}")
            for parameter in primary_surface.parameters
        )
        output_field_mappings = (
            (("return", f"{semantic_member_prefix}:output:return"),)
            if primary_surface.returns_value
            else ()
        )
        state_field_mappings = tuple(
            (field, f"{semantic_member_prefix}:state:{field}")
            for field in sorted(
                (
                    set(primary_surface.state_reads)
                    | set(primary_surface.state_writes)
                )
                - set(primary_surface.parameters)
            )
        )
        behavior_block_id = f"behavior-block:{primary_surface.surface_id}"
        declared_cases: list[BehaviorCaseContract] = []
        checker_designs: dict[str, str] = {}

        def add_declared_case(
            *,
            case_id: str,
            case_kind: str,
            rule_suffix: str,
            failure_id: str = "",
        ) -> None:
            checker_id = f"checker-design:{case_id}"
            checker_fingerprint = fingerprint_value(
                {
                    "owner_closure": closure_fingerprint,
                    "case_id": case_id,
                    "case_kind": case_kind,
                    "oracle_id": oracle.oracle_id,
                }
            )
            checker_designs[checker_id] = checker_fingerprint
            declared_case = BehaviorCaseContract(
                case_id=case_id,
                behavior_block_id=behavior_block_id,
                case_kind=case_kind,
                input_values=tuple(
                    (
                        parameter,
                        f"rule:{semantic.semantic_spec_id}:input:{parameter}:{rule_suffix}",
                    )
                    for parameter in primary_surface.parameters
                ),
                initial_state=tuple(
                    (
                        field,
                        f"rule:{semantic.semantic_spec_id}:state:{field}:{rule_suffix}",
                    )
                    for field in primary_surface.state_reads
                ),
                expected_output=(
                    (("return", f"oracle:{oracle.oracle_id}:{rule_suffix}:return"),)
                    if primary_surface.returns_value and not failure_id
                    else ()
                ),
                expected_state=tuple(
                    (
                        field,
                        f"oracle:{oracle.oracle_id}:{rule_suffix}:state:{field}",
                    )
                    for field in primary_surface.state_writes
                ),
                expected_effects=(
                    () if failure_id else primary_surface.side_effect_candidates
                ),
                expected_errors=((failure_id,) if failure_id else ()),
                oracle_id=oracle.oracle_id,
                case_evidence_id=checker_id,
                case_evidence_fingerprint=checker_fingerprint,
                value_mode="symbolic_contract",
                protected_failure_ids=((failure_id,) if failure_id else ()),
                parameter_case_id=case_id,
            )
            declared_cases.append(declared_case)
            dimensions_by_kind = {
                "good": ("input", "state", "output", "effect", "order", "completion"),
                "boundary": ("input", "state", "output", "retry", "timeout", "completion"),
                "bad": ("input", "state", "effect", "error", "decision", "completion"),
            }
            for dimension in dimensions_by_kind[case_kind]:
                member_id = f"{checker_id}:{dimension}"
                checker_designs[member_id] = fingerprint_value(
                    {
                        "owner_closure": closure_fingerprint,
                        "case_id": case_id,
                        "dimension": dimension,
                        "oracle_id": oracle.oracle_id,
                    }
                )

        add_declared_case(
            case_id=known_good_case_id,
            case_kind="good",
            rule_suffix="accepted",
        )
        add_declared_case(
            case_id=f"boundary:{owner}:{closure_fingerprint}",
            case_kind="boundary",
            rule_suffix="boundary",
        )
        failure_by_case = {
            str(item.get("known_bad_case_id", "")): str(item.get("failure_id", ""))
            for item in failure_bindings
            if isinstance(item, Mapping)
            and item.get("known_bad_case_id")
            and item.get("failure_id")
        }
        for bad_case_id in known_bad_case_ids:
            add_declared_case(
                case_id=bad_case_id,
                case_kind="bad",
                rule_suffix=f"protected:{failure_by_case[bad_case_id]}",
                failure_id=failure_by_case[bad_case_id],
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
                portable_property_ids=(
                    protected_failures
                    or (f"property:{owner}:declared-success",)
                ),
                portable_invariant_ids=(
                    f"invariant:{owner}:{closure_fingerprint}",
                ),
                portable_input_field_mappings=input_field_mappings,
                portable_output_field_mappings=output_field_mappings,
                portable_state_field_mappings=state_field_mappings,
                portable_assumption_ids=(
                    f"assumption:{purpose.get('task_intent_id', owner)}",
                ),
                portable_guarantee_ids=(
                    tuple(str(item) for item in purpose.get("evidence_check_ids", ()))
                    or (f"guarantee:{owner}:declared-terminal",)
                ),
                protected_failure_ids=protected_failures,
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
    """Discover explicit current assert-like helper call graphs for self-audit."""

    callers_by_leaf: dict[str, list[str]] = {}
    for node in test_inventory.nodes:
        for call in node.calls:
            callers_by_leaf.setdefault(call.rsplit(".", 1)[-1], []).append(
                node.node_id
            )
    helpers: list[DelegatedAssertionHelper] = []
    source_paths = {row.path for row in test_inventory.nodes}
    source_paths.update(
        path.relative_to(root).as_posix()
        for path in root.glob("flowguard/**/*.py")
        if path.is_file()
    )
    for path in sorted(source_paths):
        source_path = root / path
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=path)
        except (OSError, UnicodeError, SyntaxError):
            continue
        for item in tree.body:
            candidates = (
                tuple(
                    child
                    for child in item.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                if isinstance(item, ast.ClassDef)
                else (item,)
            )
            for function in candidates:
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not function.name.startswith("assert_"):
                    continue
                helper_id = function.name
                terminal_members: list[tuple[str, str]] = []
                callee_ids: list[str] = []
                for node in ast.walk(function):
                    if isinstance(node, ast.Assert):
                        terminal_id = (
                            f"delegated-terminal:{path}:{function.name}:"
                            f"{getattr(node, 'lineno', 0)}:{getattr(node, 'col_offset', 0)}"
                        )
                        terminal_members.append(
                            (
                                terminal_id,
                                fingerprint_value(
                                    {
                                        "path": path,
                                        "helper": function.name,
                                        "ast": ast.dump(
                                            node,
                                            annotate_fields=True,
                                            include_attributes=False,
                                        ),
                                    }
                                ),
                            )
                        )
                    if isinstance(node, ast.Raise):
                        exception = node.exc
                        if isinstance(exception, ast.Call):
                            exception = exception.func
                        assertion_error = (
                            isinstance(exception, ast.Name)
                            and exception.id == "AssertionError"
                        ) or (
                            isinstance(exception, ast.Attribute)
                            and exception.attr == "AssertionError"
                        )
                        if assertion_error:
                            terminal_id = (
                                f"delegated-terminal:{path}:{function.name}:"
                                f"{getattr(node, 'lineno', 0)}:{getattr(node, 'col_offset', 0)}"
                            )
                            terminal_members.append(
                                (
                                    terminal_id,
                                    fingerprint_value(
                                        {
                                            "path": path,
                                            "helper": function.name,
                                            "ast": ast.dump(
                                                node,
                                                annotate_fields=True,
                                                include_attributes=False,
                                            ),
                                        }
                                    ),
                                )
                            )
                    if not isinstance(node, ast.Call):
                        continue
                    if isinstance(node.func, ast.Name):
                        called = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        called = node.func.attr
                    else:
                        called = ""
                    if called.startswith("assert_") and called != function.name:
                        callee_ids.append(called)
                    elif called in {"raises", "warns", "fail"} or called.startswith(
                        "assert"
                    ):
                        terminal_id = (
                            f"delegated-terminal:{path}:{function.name}:"
                            f"{getattr(node, 'lineno', 0)}:{getattr(node, 'col_offset', 0)}"
                        )
                        terminal_members.append(
                            (
                                terminal_id,
                                fingerprint_value(
                                    {
                                        "path": path,
                                        "helper": function.name,
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
                callers = tuple(sorted(set(callers_by_leaf.get(function.name, ()))))
                helpers.append(
                    DelegatedAssertionHelper(
                        helper_id=helper_id,
                        test_node_id=(
                            callers[0]
                            if callers
                            else f"delegated-helper-library:{path}#{function.name}"
                        ),
                        source_fingerprint=fingerprint_value(
                            {
                                "path": path,
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
    return tuple(helpers)


def _resources(
    root: Path,
    definition: Mapping[str, Any],
) -> tuple[BlueprintResourceReference, ...]:
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
                owner_id="blueprint:flowguard",
                artifact_id=f"resource-manifest:{kind}",
                purpose=f"describe the exact current {kind} resource boundary",
                lifecycle_role="blueprint_input",
                artifact_fingerprint=fingerprint,
                semantics=(("requirement", f"materialize the exact current {kind} resource manifest"),),
            )
        )
    return tuple(rows)


def _self_topology(
    *,
    semantic_mesh: Mapping[str, Any],
    owners: Sequence[ProjectBlueprintOwner],
    entries: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[BlueprintTopologyNode, ...], tuple[BlueprintTopologyRelation, ...]]:
    """Compile the semantic mesh into exact output-to-input handoff rows."""

    owner_by_model = {
        owner.model_element_id.removeprefix("model-obligation:"): owner
        for owner in owners
    }
    nodes: dict[str, BlueprintTopologyNode] = {}
    for parent in semantic_mesh.get("semantic_parents", ()):
        if not isinstance(parent, Mapping):
            continue
        parent_id = str(parent.get("parent_id", ""))
        if parent_id:
            nodes[parent_id] = BlueprintTopologyNode(
                node_id=parent_id,
                disposition="connected",
                purpose=str(parent.get("purpose", "semantic parent")),
            )
    mesh_rows = {
        str(row.get("model_id", "")): row
        for row in semantic_mesh.get("models", ())
        if isinstance(row, Mapping) and row.get("model_id")
    }
    for model_id, owner in sorted(owner_by_model.items()):
        row = mesh_rows.get(model_id, {})
        nodes[owner.model_element_id] = BlueprintTopologyNode(
            node_id=owner.model_element_id,
            disposition=str(row.get("disposition", "scoped_out")),
            purpose=str(
                row.get(
                    "rationale",
                    "model exists in the current owner inventory but is absent from the semantic mesh",
                )
            ),
            implementation_surface_ids=owner.implementation_surface_ids,
        )
    external_consumers = {
        str(consumer_id)
        for row in mesh_rows.values()
        for consumer_id in row.get("consumer_ids", ())
        if str(consumer_id).startswith("claim:")
    }
    for consumer_id in sorted(external_consumers):
        nodes[consumer_id] = BlueprintTopologyNode(
            node_id=consumer_id,
            disposition="intentional_leaf",
            purpose="terminal claim consumer outside the model-owner inventory",
        )

    relations: list[BlueprintTopologyRelation] = []
    for model_id, row in sorted(mesh_rows.items()):
        owner = owner_by_model.get(model_id)
        if owner is None:
            continue
        purpose = entries.get(model_id, {}).get("purpose_closure", {})
        if not isinstance(purpose, Mapping):
            purpose = {}
        output_ids = tuple(
            str(item) for item in purpose.get("evidence_check_ids", ()) if str(item)
        ) or (f"model-output:{model_id}:declared-terminal",)
        relation_evidence = fingerprint_value(
            {
                "semantic_mesh_fingerprint": semantic_mesh.get(
                    "semantic_relation_fingerprint", ""
                ),
                "model_id": model_id,
                "purpose_closure_fingerprint": purpose.get("closure_fingerprint", ""),
            }
        )
        consumers: list[tuple[str, str]] = []
        consumers.extend(
            (str(parent_id), "child_to_parent")
            for parent_id in row.get("parent_ids", ())
        )
        for raw_consumer_id in row.get("consumer_ids", ()):
            consumer_id = str(raw_consumer_id)
            if consumer_id.startswith("model:"):
                consumer_id = "model-obligation:" + consumer_id.removeprefix("model:")
            consumers.append((consumer_id, "produces_for"))
        for consumer_id, relation_kind in consumers:
            if consumer_id not in nodes:
                continue
            relations.append(
                BlueprintTopologyRelation(
                    relation_id=f"topology:{model_id}:{consumer_id}",
                    producer_id=owner.model_element_id,
                    consumer_id=consumer_id,
                    relation_kind=relation_kind,
                    interface_mappings=tuple(
                        (
                            f"output:{model_id}:{output_id}",
                            f"input:{consumer_id}:{output_id}",
                        )
                        for output_id in output_ids
                    ),
                    evidence_fingerprint=relation_evidence,
                    rationale="the declared consumer receives this model's exact terminal output identity",
                )
            )
    return tuple(nodes.values()), tuple(relations)


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


def _self_intent_inventory(
    root: Path,
    *,
    subject_revision: str,
    model_target_ids: Sequence[str],
    authority: Mapping[str, Any],
) -> ProjectIntentInventory:
    """Project the canonical accepted revision intent to exact blueprint targets."""

    revision_fingerprint = str(
        authority.get("accepted_revision_set_fingerprint", "")
    )
    if not revision_fingerprint.startswith("sha256:"):
        raise FlowGuardSelfBlueprintError(
            "FlowGuard self-blueprint has no canonical accepted intent revision"
        )
    revision_path = (
        root
        / ".flowguard/model-mesh/revisions"
        / f"{revision_fingerprint.split(':', 1)[1]}.json"
    )
    revision = ModelRevisionSet.from_dict(_load_json_object(revision_path))
    if revision.fingerprint != revision_fingerprint:
        raise FlowGuardSelfBlueprintError(
            "accepted revision-set fingerprint does not match canonical intent authority"
        )
    review = revision.intent_review
    if not review.ok:
        raise FlowGuardSelfBlueprintError(
            "canonical accepted intent review contains unresolved findings"
        )
    disposition_by_id = {
        row.contribution_id: row for row in review.dispositions
    }
    target_set = set(model_target_ids)
    contributions: list[ProjectIntentContribution] = []
    for contribution in review.contributions:
        disposition = disposition_by_id.get(contribution.contribution_id)
        if disposition is None:
            raise FlowGuardSelfBlueprintError(
                "canonical intent contribution has no exact disposition"
            )
        target_tokens = {
            contribution.logical_model_id,
            *contribution.target_obligation_ids,
            *contribution.target_state_ids,
            *contribution.target_transition_ids,
            *contribution.target_invariant_ids,
            *contribution.target_relation_ids,
            *contribution.target_output_ids,
        }
        exact_targets = tuple(
            sorted(
                target_id
                for target_id in target_set
                if _intent_target_matches(target_id, target_tokens)
            )
        )
        projected_disposition = disposition.disposition
        if projected_disposition not in {
            "accepted",
            "superseded",
            "rejected",
            "scoped_out",
            "blocked",
        }:
            projected_disposition = "blocked"
        if not exact_targets:
            projected_disposition = "blocked"
        contributions.append(
            ProjectIntentContribution(
                contribution_id=contribution.contribution_id,
                source_kind=contribution.source_kind,
                source_id=contribution.source_ref,
                source_fingerprint=contribution.source_fingerprint,
                disposition=projected_disposition,
                target_ids=exact_targets,
                rationale=(
                    disposition.reason
                    if exact_targets
                    else "canonical intent has no exact current blueprint target"
                ),
            )
        )
    if not contributions:
        raise FlowGuardSelfBlueprintError(
            "FlowGuard self-blueprint canonical revision has no admitted intent"
        )
    return ProjectIntentInventory(
        inventory_id="intent-inventory:flowguard:self",
        subject_revision=subject_revision,
        canonical_review_fingerprint=review.fingerprint,
        contributions=tuple(contributions),
    )


def _intent_target_matches(target_id: str, target_tokens: set[str]) -> bool:
    """Match exact typed identities for one canonical blueprint owner."""

    canonical_target = str(target_id)
    model_owner_id = canonical_target.removeprefix("model-obligation:")
    normalized_tokens = {str(item) for item in target_tokens if str(item)}
    exact_aliases = {
        canonical_target,
        model_owner_id,
        f"model:{model_owner_id}",
        f"model_instance:model:{model_owner_id}",
    }
    return not exact_aliases.isdisjoint(normalized_tokens)


def build_flowguard_self_blueprint(
    root: str | Path,
) -> FlowGuardSelfBlueprintBundle:
    root_path = Path(root).resolve()
    definition = load_flowguard_self_blueprint_definition(root_path)
    project = tomllib.loads((root_path / ".flowguard/project.toml").read_text(encoding="utf-8"))
    authority = project.get("model_authority", {})
    subject_revision = str(authority.get("subject_revision", ""))
    if not subject_revision:
        raise FlowGuardSelfBlueprintError("observed model authority subject revision is missing")
    boundary, categories = _boundary_from_definition(
        root_path,
        definition,
        subject_revision=subject_revision,
    )
    files = _file_dispositions(root_path, definition, categories)
    surface_dispositions, dynamic_allowances = _discover_surface_declarations(
        root_path,
        files,
        definition,
    )
    inventory = build_implementation_surface_inventory(
        root_path,
        boundary,
        inventory_id=str(definition["inventory_id"]),
        file_dispositions=files,
        surface_dispositions=surface_dispositions,
        dynamic_allowances=dynamic_allowances,
        discovery_adapters={
            PYTHON_AST_IMPLEMENTATION_ADAPTER_ID: discover_python_implementation_surfaces
        },
        claim_boundary=str(definition["claim_boundary"]),
    )
    _manifest_payload, entries = _manifest_entries(root_path)
    test_inventory = _flowguard_test_inventory(
        root_path,
        subject_revision=subject_revision,
    )
    overrides = {
        str(key): str(value)
        for key, value in dict(definition["owner_overrides"]).items()
    }
    owners = _project_owners(
        root_path,
        inventory,
        entries,
        overrides,
        test_inventory,
    )
    resources = _resources(root_path, definition)
    semantic_mesh_path = root_path / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    semantic_mesh_fingerprint = source_file_fingerprint(semantic_mesh_path)
    semantic_mesh = _load_json_object(semantic_mesh_path)
    topology_nodes, topology_relations = _self_topology(
        semantic_mesh=semantic_mesh,
        owners=owners,
        entries=entries,
    )
    portable_owner_fingerprints = (
        (
            "portable:compositional-verification-kernel",
            str(_purpose_value(entries["compositional_verification_kernel"], "closure_fingerprint", "")),
        ),
    )
    observed_snapshot_fingerprint = str(authority.get("observed_snapshot_fingerprint", ""))
    intent_inventory = _self_intent_inventory(
        root_path,
        subject_revision=subject_revision,
        model_target_ids=tuple(owner.model_element_id for owner in owners),
        authority=authority,
    )
    project_definition = ProjectBlueprintDefinition(
        blueprint_id=str(definition["blueprint_id"]),
        inventory_id=str(definition["inventory_id"]),
        boundary=boundary,
        file_dispositions=files,
        surface_dispositions=tuple(surface_dispositions.items()),
        supporting_owners=(),
        dynamic_allowances=tuple(dynamic_allowances.items()),
        owners=owners,
        claim_boundary=str(definition["claim_boundary"]),
        target_kind="software",
        observation_providers=(
            (
                PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                ("implementation_inventory",),
            ),
            (PYTHON_AST_TEST_ADAPTER_ID, ("test_inventory",)),
            ("flowguard-resource-manifest-v1", ("resource_inventory",)),
        ),
        authority_providers=(
            (
                "flowguard-observed-model-system-v1",
                ("model_authority", "model_topology"),
            ),
            (
                "flowguard-model-purpose-closure-v1",
                ("behavior_semantics", "oracle_inventory"),
            ),
            ("flowguard-model-intent-v1", ("intent_lineage",)),
            ("flowguard-portable-model-v1", ("portable_behavior",)),
        ),
    )
    project_evidence = ProjectBlueprintEvidence(
        observed_snapshot_id=str(authority.get("observed_snapshot_path", "")),
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        semantic_mesh_id="flowguard-whole-system-understanding-v1",
        semantic_mesh_fingerprint=semantic_mesh_fingerprint,
        portable_owner_fingerprints=portable_owner_fingerprints,
        portable_member_catalogs=tuple(
            PortableModelMemberCatalog(
                portable_model_id=owner.portable_model_id,
                portable_model_fingerprint=owner.portable_model_fingerprint,
                transition_ids=owner.portable_transition_ids,
                property_ids=owner.portable_property_ids,
                invariant_ids=owner.portable_invariant_ids,
                input_field_ids=tuple(
                    member_id
                    for _field, member_id in owner.portable_input_field_mappings
                ),
                output_field_ids=tuple(
                    member_id
                    for _field, member_id in owner.portable_output_field_mappings
                ),
                state_field_ids=tuple(
                    member_id
                    for _field, member_id in owner.portable_state_field_mappings
                ),
                assumption_ids=owner.portable_assumption_ids,
                guarantee_ids=owner.portable_guarantee_ids,
            )
            for owner in owners
        ),
        resources=resources,
        test_inventory=test_inventory,
        topology_nodes=topology_nodes,
        topology_relations=topology_relations,
        native_evidence_artifacts=_native_evidence_artifacts(entries),
    )
    delegated_assertion_helpers = _flowguard_delegated_assertion_helpers(
        root_path,
        test_inventory,
    )
    bundle = build_project_blueprint(
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
        intent_inventory=intent_inventory,
        topology_fingerprint=semantic_mesh_fingerprint,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints={
            row.helper_id: row.source_fingerprint
            for row in delegated_assertion_helpers
        },
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
    return FlowGuardSelfBlueprintBundle(
        test_inventory=test_inventory,
        inventory=bundle.inventory,
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
    )


__all__ = [
    "DEFAULT_SELF_BLUEPRINT_DEFINITION",
    "SELF_BLUEPRINT_DEFINITION_SCHEMA",
    "FlowGuardSelfBlueprintBundle",
    "FlowGuardSelfBlueprintError",
    "build_flowguard_self_blueprint",
    "load_flowguard_self_blueprint_definition",
]
