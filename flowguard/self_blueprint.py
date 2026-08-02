"""FlowGuard's current self-blueprint composition.

The generic inventory and blueprint modules remain project-neutral.  This
module binds those owners to FlowGuard's checked-in declarative boundary,
model-regression purpose closures, semantic mesh, and test oracles.  It is a
derived view of the observed model system, never a second authority pointer.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tomllib
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value
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
from .source_identity import source_file_fingerprint
from .validation_ownership import resolve_input_manifest


SELF_BLUEPRINT_DEFINITION_SCHEMA = "flowguard.self_blueprint_definition.v1"
DEFAULT_SELF_BLUEPRINT_DEFINITION = (
    ".flowguard/authoritative_model_system/software_blueprint_definition.json"
)


class FlowGuardSelfBlueprintError(ValueError):
    """Raised when the checked-in self-blueprint definition cannot close."""


@dataclass(frozen=True)
class FlowGuardSelfBlueprintBundle:
    inventory: ImplementationSurfaceInventory
    binding_report: ModelImplementationBindingReport
    manifest: SoftwareBlueprintManifest
    qualification: SoftwareBlueprintQualificationReport

    @property
    def ok(self) -> bool:
        return self.qualification.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "inventory_fingerprint": self.inventory.inventory_fingerprint,
            "binding_report_fingerprint": self.binding_report.fingerprint,
            "blueprint_fingerprint": self.manifest.fingerprint,
            "qualification": self.qualification.to_dict(),
            "counts": {
                "files": len(self.inventory.file_dispositions),
                "implementation_surfaces": len(self.inventory.surfaces),
                "bindings": len(self.binding_report.bindings),
                "semantic_specs": len(self.binding_report.semantic_specs),
                "oracles": len(self.binding_report.oracles),
                "resources": len(self.manifest.resources),
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
            reason = "historical or superseded material is outside current reconstruction authority"
        elif path in scan_paths:
            disposition = IMPLEMENTATION_DISPOSITION_MODEL
            reason = "current executable implementation is discovered and model-bound"
        else:
            disposition = IMPLEMENTATION_DISPOSITION_SUPPORTING
            reason = "current non-executable reconstruction resource is owned by the blueprint"
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


def _owner_for_path(
    path: str,
    *,
    model_ids: set[str],
    overrides: Mapping[str, str],
) -> str:
    if path in overrides:
        owner = str(overrides[path])
    elif path.startswith(".flowguard/") and len(path.split("/")) >= 3:
        owner = path.split("/", 2)[1]
    elif path.startswith("flowguard/") and path.endswith(".py"):
        owner = Path(path).stem
    elif path.startswith("scripts/"):
        owner = "development_process_flow"
    else:
        owner = "authoritative_model_system"
    return owner if owner in model_ids else "authoritative_model_system"


def _surface_dimensions(surface: ImplementationSurface) -> tuple[str, ...]:
    values = {"input", "output", "error"}
    if surface.state_writes or surface.side_effect_candidates or surface.dynamic_operations:
        values.add("state_effect")
    if surface.calls or surface.dynamic_operations:
        values.add("decision")
    return tuple(sorted(values))


def _purpose_value(entry: Mapping[str, Any], key: str, default: Any) -> Any:
    purpose = entry.get("purpose_closure", {})
    return purpose.get(key, default) if isinstance(purpose, Mapping) else default


def _binding_closure(
    inventory: ImplementationSurfaceInventory,
    entries: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, str],
) -> ModelImplementationBindingReport:
    model_ids = set(entries)
    grouped: dict[str, list[ImplementationSurface]] = {}
    owner_by_surface: dict[str, str] = {}
    for surface in inventory.surfaces:
        owner = _owner_for_path(
            surface.path,
            model_ids=model_ids,
            overrides=overrides,
        )
        grouped.setdefault(owner, []).append(surface)
        owner_by_surface[surface.surface_id] = owner

    model_element_ids = {
        surface.surface_id: f"model-element:{surface.surface_id}"
        for surface in inventory.surfaces
    }
    semantic_specs: list[SemanticSpecReference] = []
    semantic_fingerprints: dict[str, str] = {}
    for surface in inventory.surfaces:
        owner = owner_by_surface[surface.surface_id]
        entry = entries[owner]
        dimensions = _surface_dimensions(surface)
        semantic_payload: dict[str, str] = {
            "input": "parameters=" + ",".join(surface.parameters or ("none",)),
            "output": (
                f"returns_value={str(surface.returns_value).lower()}; owner_purpose="
                + str(_purpose_value(entry, "guarded_purpose", "declared owner behavior"))
            ),
            "error": (
                "raised_errors=" + ",".join(surface.raised_errors or ("none_observed",))
                + "; protected_failures="
                + ",".join(_purpose_value(entry, "protected_failure_ids", ()))
            ),
        }
        if "state_effect" in dimensions:
            semantic_payload["state_effect"] = (
                "writes=" + ",".join(surface.state_writes or ("none",))
                + "; effects="
                + ",".join(surface.side_effect_candidates or ("none",))
                + "; dynamic_protocols="
                + ",".join(surface.dynamic_operations or ("none",))
            )
        if "decision" in dimensions:
            semantic_payload["decision"] = (
                "calls=" + ",".join(surface.calls or ("none",))
                + "; bounded_dynamic="
                + ",".join(surface.dynamic_operations or ("none",))
            )
        spec_id = f"semantic-spec:{surface.surface_id}"
        fingerprint = fingerprint_value(
            {
                "owner": owner,
                "owner_closure": _purpose_value(entry, "closure_fingerprint", ""),
                "surface_structure": surface.structure_fingerprint,
                "semantics": semantic_payload,
            }
        )
        semantic_fingerprints[spec_id] = fingerprint
        semantic_specs.append(
            SemanticSpecReference(
                semantic_spec_id=spec_id,
                owner_id=f"model:{owner}",
                artifact_id=f"semantic-contract:{owner}:{surface.surface_id}",
                artifact_fingerprint=fingerprint,
                covered_model_element_ids=(model_element_ids[surface.surface_id],),
                covered_dimensions=dimensions,
                semantics=tuple(semantic_payload.items()),
            )
        )

    oracles: list[OracleReference] = []
    oracle_fingerprints: dict[str, str] = {}
    for owner, surfaces in sorted(grouped.items()):
        entry = entries[owner]
        dimensions = sorted(
            {dimension for surface in surfaces for dimension in _surface_dimensions(surface)}
        )
        purpose = entry.get("purpose_closure", {})
        failure_bindings = purpose.get("failure_bindings", ()) if isinstance(purpose, Mapping) else ()
        semantics = {
            "input": "known_good_case=" + str(_purpose_value(entry, "known_good_case_id", "")),
            "output": "evidence_checks=" + ",".join(_purpose_value(entry, "evidence_check_ids", ())),
            "error": "known_bad_cases=" + ",".join(
                str(item.get("known_bad_case_id", ""))
                for item in failure_bindings
                if isinstance(item, Mapping)
            ),
        }
        if "state_effect" in dimensions:
            semantics["state_effect"] = "native runner checks declared state and side-effect boundaries"
        if "decision" in dimensions:
            semantics["decision"] = "native runner distinguishes every declared protected failure"
        oracle_id = f"oracle:model-regression:{owner}"
        fingerprint = str(_purpose_value(entry, "closure_fingerprint", ""))
        oracle_fingerprints[oracle_id] = fingerprint
        oracles.append(
            OracleReference(
                oracle_id=oracle_id,
                owner_id=f"model:{owner}",
                artifact_id=f"native-runner:{owner}",
                artifact_fingerprint=fingerprint,
                covered_model_element_ids=tuple(
                    model_element_ids[surface.surface_id] for surface in surfaces
                ),
                covered_dimensions=tuple(dimensions),
                semantics=tuple(semantics.items()),
            )
        )

    bindings: list[ModelImplementationBinding] = []
    model_fingerprints: dict[str, str] = {}
    contract_fingerprints: dict[str, str] = {}
    for surface in inventory.surfaces:
        owner = owner_by_surface[surface.surface_id]
        closure_fingerprint = str(
            _purpose_value(entries[owner], "closure_fingerprint", "")
        )
        model_id = model_element_ids[surface.surface_id]
        contract_id = f"owner-contract:{owner}"
        model_fingerprints[model_id] = closure_fingerprint
        contract_fingerprints[contract_id] = closure_fingerprint
        bindings.append(
            ModelImplementationBinding(
                binding_id=f"binding:{surface.surface_id}",
                model_element_id=model_id,
                implementation_surface_id=surface.surface_id,
                relation_kind="implements",
                owner_contract_id=contract_id,
                semantic_spec_ids=(f"semantic-spec:{surface.surface_id}",),
                oracle_ids=(f"oracle:model-regression:{owner}",),
                required_dimensions=_surface_dimensions(surface),
                model_fingerprint=closure_fingerprint,
                implementation_fingerprint=surface.content_fingerprint,
                owner_contract_fingerprint=closure_fingerprint,
            )
        )
    return review_model_implementation_bindings(
        inventory,
        required_model_element_ids=tuple(model_element_ids.values()),
        required_implementation_surface_ids=inventory.required_surface_ids,
        bindings=tuple(bindings),
        semantic_specs=tuple(semantic_specs),
        oracles=tuple(oracles),
        current_model_fingerprints=model_fingerprints,
        current_contract_fingerprints=contract_fingerprints,
        current_semantic_spec_fingerprints=semantic_fingerprints,
        current_oracle_fingerprints=oracle_fingerprints,
    )


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
                artifact_fingerprint=fingerprint,
                semantics=(("requirement", f"materialize the exact current {kind} resource manifest"),),
            )
        )
    return tuple(rows)


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
    binding_report = _binding_closure(
        inventory,
        entries,
        {str(key): str(value) for key, value in dict(definition["owner_overrides"]).items()},
    )
    resources = _resources(root_path, definition)
    semantic_mesh_path = root_path / ".flowguard/authoritative_model_system/semantic_model_mesh.json"
    semantic_mesh_fingerprint = source_file_fingerprint(semantic_mesh_path)
    portable_owner_fingerprints = (
        (
            "portable:compositional-verification-kernel",
            str(_purpose_value(entries["compositional_verification_kernel"], "closure_fingerprint", "")),
        ),
    )
    observed_snapshot_fingerprint = str(authority.get("observed_snapshot_fingerprint", ""))
    manifest = SoftwareBlueprintManifest(
        blueprint_id=str(definition["blueprint_id"]),
        observed_snapshot_id=str(authority.get("observed_snapshot_path", "")),
        observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        inventory_id=inventory.inventory_id,
        inventory_fingerprint=inventory.inventory_fingerprint,
        binding_report_id=f"binding-report:{binding_report.fingerprint}",
        binding_report_fingerprint=binding_report.fingerprint,
        semantic_mesh_id="flowguard-whole-system-understanding-v1",
        semantic_mesh_fingerprint=semantic_mesh_fingerprint,
        portable_owner_fingerprints=portable_owner_fingerprints,
        resources=resources,
        oracles=binding_report.oracles,
        required_resource_ids=tuple(item.resource_id for item in resources),
        required_resource_kinds=tuple(item.kind for item in resources),
        required_oracle_ids=tuple(item.oracle_id for item in binding_report.oracles),
        excluded_source_ids=tuple(
            item.path
            for item in inventory.file_dispositions
            if item.category == "production"
        ),
    )
    qualification = qualify_software_blueprint(
        manifest,
        binding_report,
        implementation_inventory=inventory,
        current_observed_snapshot_fingerprint=observed_snapshot_fingerprint,
        current_semantic_mesh_fingerprint=semantic_mesh_fingerprint,
        current_portable_owner_fingerprints=dict(portable_owner_fingerprints),
        current_resource_fingerprints={
            item.resource_id: str(item.artifact_fingerprint) for item in resources
        },
        current_oracle_fingerprints={
            item.oracle_id: item.artifact_fingerprint for item in binding_report.oracles
        },
    )
    return FlowGuardSelfBlueprintBundle(
        inventory=inventory,
        binding_report=binding_report,
        manifest=manifest,
        qualification=qualification,
    )


__all__ = [
    "DEFAULT_SELF_BLUEPRINT_DEFINITION",
    "SELF_BLUEPRINT_DEFINITION_SCHEMA",
    "FlowGuardSelfBlueprintBundle",
    "FlowGuardSelfBlueprintError",
    "build_flowguard_self_blueprint",
    "load_flowguard_self_blueprint_definition",
]
