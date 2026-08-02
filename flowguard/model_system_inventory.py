"""Build one bounded model-system snapshot from existing FlowGuard owners."""

from __future__ import annotations

import hashlib
from importlib import import_module
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .model_authority import (
    LIFECYCLE_ACTIVE,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    CoverageDimension,
    CoverageUniverse,
    ModelRelation,
    ModelSystemSnapshot,
    build_model_instance_ref,
    canonical_fingerprint,
    file_fingerprint,
)
from .model_regressions import (
    ModelRegressionEntry,
    ModelRegressionManifest,
    audit_manifest,
    input_inventory_fingerprint,
    resolve_entry_input_inventory,
)
from .behavior_commitment import (
    BehaviorCommitmentLedger,
    load_behavior_commitment_ledger,
    review_behavior_commitment_ledger,
)


class ModelSystemInventoryError(ValueError):
    """Raised when existing owner artifacts cannot form a bounded snapshot."""


@dataclass(frozen=True)
class ManifestModelInventory:
    """Exact declared/materialized membership at one live manifest boundary."""

    declared_ids: tuple[str, ...]
    materialized_ids: tuple[str, ...]
    required_ids: tuple[str, ...]
    covered_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return (
            self.declared_ids
            == self.materialized_ids
            == self.required_ids
            == self.covered_ids
            and not self.missing_ids
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "declared_ids": list(self.declared_ids),
            "materialized_ids": list(self.materialized_ids),
            "required_ids": list(self.required_ids),
            "covered_ids": list(self.covered_ids),
            "missing_ids": list(self.missing_ids),
            "complete": self.complete,
        }


@dataclass(frozen=True)
class AffectedAuthorityComponent:
    """One independently inventoried behavior/model/source/evidence relation set."""

    component_id: str
    source_surface_id: str
    behavior_commitment_id: str
    model_owner_ids: tuple[str, ...]
    primary_source_owner: str
    evidence_owner_ids: tuple[str, ...]
    runtime_entry_ids: tuple[str, ...]
    model_relations: tuple[tuple[str, str], ...]
    relation_types: tuple[str, ...]
    affected_sibling_ids: tuple[str, ...]
    gap_ids: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AffectedAuthorityComponent":
        required = {
            "component_id",
            "source_surface_id",
            "behavior_commitment_id",
            "model_owner_ids",
            "primary_source_owner",
            "evidence_owner_ids",
            "runtime_entry_ids",
            "model_relations",
            "relation_types",
            "affected_sibling_ids",
            "gap_ids",
        }
        if set(value) != required:
            raise ModelSystemInventoryError(
                "affected authority component fields differ from the current schema: "
                f"{sorted(set(value) ^ required)}"
            )
        raw_relations = value["model_relations"]
        if not isinstance(raw_relations, list):
            raise ModelSystemInventoryError("affected authority model_relations must be an array")
        relations: list[tuple[str, str]] = []
        for relation in raw_relations:
            if not isinstance(relation, Mapping) or set(relation) != {"kind", "target_model_id"}:
                raise ModelSystemInventoryError("affected authority model relation is not exact current format")
            relations.append((str(relation["kind"]), str(relation["target_model_id"])))
        return cls(
            component_id=str(value["component_id"]),
            source_surface_id=str(value["source_surface_id"]),
            behavior_commitment_id=str(value["behavior_commitment_id"]),
            model_owner_ids=_string_values(value["model_owner_ids"]),
            primary_source_owner=str(value["primary_source_owner"]),
            evidence_owner_ids=_string_values(value["evidence_owner_ids"]),
            runtime_entry_ids=_string_values(value["runtime_entry_ids"]),
            model_relations=tuple(relations),
            relation_types=_string_values(value["relation_types"]),
            affected_sibling_ids=_string_values(value["affected_sibling_ids"]),
            gap_ids=_string_values(value["gap_ids"]),
        )


@dataclass(frozen=True)
class AffectedAuthorityInventory:
    inventory_id: str
    claim_boundary: str
    components: tuple[AffectedAuthorityComponent, ...]
    artifact_path: str
    fingerprint: str


def load_affected_authority_inventory(
    root: str | Path,
) -> AffectedAuthorityInventory | None:
    """Load the independent affected-path inventory when the project declares one."""

    root_path = Path(root).resolve()
    path = root_path / ".flowguard" / "authoritative_model_system" / "affected_authority_inventory.json"
    if not path.is_file():
        return None
    payload = _load_json_object(path)
    required = {
        "artifact_type",
        "schema_version",
        "inventory_id",
        "claim_boundary",
        "components",
    }
    if set(payload) != required:
        raise ModelSystemInventoryError(
            "affected authority inventory fields differ from the current schema"
        )
    if payload["artifact_type"] != "flowguard_affected_authority_inventory":
        raise ModelSystemInventoryError("affected authority inventory artifact type is invalid")
    if payload["schema_version"] != "flowguard.affected_authority_inventory.v1":
        raise ModelSystemInventoryError("affected authority inventory schema is not current")
    raw_components = payload["components"]
    if not isinstance(raw_components, list) or not raw_components:
        raise ModelSystemInventoryError("affected authority inventory requires components")
    components = tuple(AffectedAuthorityComponent.from_mapping(item) for item in raw_components)
    component_ids = tuple(item.component_id for item in components)
    if len(component_ids) != len(set(component_ids)):
        raise ModelSystemInventoryError("affected authority component ids must be unique")
    return AffectedAuthorityInventory(
        inventory_id=str(payload["inventory_id"]),
        claim_boundary=str(payload["claim_boundary"]),
        components=components,
        artifact_path=path.relative_to(root_path).as_posix(),
        fingerprint=file_fingerprint(path),
    )


def _stable_id(prefix: str, value: Any) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._:/-]+", "-", str(value).strip())
    normalized = normalized.strip("-")
    if not normalized:
        normalized = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{normalized}"


def _load_json_object(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelSystemInventoryError(
            f"cannot load model-system owner artifact {path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ModelSystemInventoryError(
            f"model-system owner artifact must be an object: {path}"
        )
    return payload


def _available_entries(
    root: Path,
    manifest: ModelRegressionManifest,
) -> tuple[ModelRegressionEntry, ...]:
    return tuple(
        entry
        for entry in manifest.entries
        if (
            not entry.excluded
            and (root / entry.model_path).is_file()
            and len(entry.runner) >= 2
            and (root / entry.runner[1]).is_file()
        )
    )


def inspect_manifest_model_inventory(
    root: str | Path,
    manifest: ModelRegressionManifest | None = None,
) -> ManifestModelInventory:
    """Return exact live membership without treating distribution as coverage."""

    root_path = Path(root).resolve()
    current_manifest = manifest or ModelRegressionManifest.load(root_path)
    declared_ids = tuple(
        sorted(
            entry.model_id
            for entry in current_manifest.entries
            if not entry.excluded
        )
    )
    materialized_ids = tuple(
        sorted(
            entry.model_id
            for entry in _available_entries(root_path, current_manifest)
        )
    )
    missing_ids = tuple(sorted(set(declared_ids) - set(materialized_ids)))
    return ManifestModelInventory(
        declared_ids=declared_ids,
        materialized_ids=materialized_ids,
        required_ids=declared_ids,
        covered_ids=materialized_ids,
        missing_ids=missing_ids,
    )


def _materialization_gap_error(
    error: str,
    *,
    missing_ids: set[str],
) -> bool:
    return any(
        error
        == f"manifest required-public model missing from filesystem: {model_id}"
        or error == f"{model_id}: model_path does not exist"
        or error.startswith(f"{model_id}: runner does not exist:")
        or error.startswith(f"{model_id}: input_glob resolves no files:")
        for model_id in missing_ids
    )


def _owner_model_id(
    owner: Any,
    *,
    path_to_model_id: Mapping[str, str],
    model_ids: set[str],
) -> str:
    normalized = str(owner or "").replace("\\", "/")
    if normalized in path_to_model_id:
        return path_to_model_id[normalized]
    match = re.search(r"\.flowguard/([^/]+)/model\.py", normalized)
    if match and match.group(1) in model_ids:
        return match.group(1)
    if normalized.startswith("model:") and normalized.split(":", 1)[1] in model_ids:
        return normalized.split(":", 1)[1]
    return ""


def _commitment_records(
    root: Path,
) -> tuple[Path | None, BehaviorCommitmentLedger | None]:
    path = (
        root
        / ".flowguard"
        / "behavior_commitment_ledger"
        / "ledger.json"
    )
    if not path.is_file():
        return None, None
    try:
        ledger = load_behavior_commitment_ledger(path)
    except (OSError, ValueError) as exc:
        raise ModelSystemInventoryError(
            f"behavior commitment artifact is not exact current format: {exc}"
        ) from exc
    return path, ledger


def _evidence_values(
    commitment: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...]:
    evidence = commitment.get("evidence")
    if not isinstance(evidence, Mapping):
        return ()
    values = evidence.get(field_name, ())
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    return tuple(str(value) for value in values if str(value).strip())


def _string_values(
    value: Any,
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _runtime_entry_available(value: str) -> bool:
    parts = tuple(part for part in str(value).split(".") if part)
    if len(parts) < 2 or parts[0] != "flowguard":
        return False
    try:
        current: Any = import_module(parts[0])
    except ImportError:
        return False
    for part in parts[1:]:
        if not hasattr(current, part):
            return False
        current = getattr(current, part)
    return callable(current) or isinstance(current, type)


def build_manifest_model_system_snapshot(
    root: str | Path,
    *,
    snapshot_id: str,
    system_id: str = "flowguard",
    subject_lane: str = SUBJECT_OBSERVED_IMPLEMENTATION,
    lifecycle: str = LIFECYCLE_ACTIVE,
    subject_revision: str = "",
) -> ModelSystemSnapshot:
    """Join the regression manifest and existing native owners into one snapshot."""

    root_path = Path(root).resolve()
    manifest = ModelRegressionManifest.load(root_path)
    model_inventory = inspect_manifest_model_inventory(root_path, manifest)
    manifest_audit = audit_manifest(root_path, manifest)
    non_materialization_errors = tuple(
        error
        for error in manifest_audit.errors
        if not _materialization_gap_error(
            error,
            missing_ids=set(model_inventory.missing_ids),
        )
    )
    if non_materialization_errors:
        raise ModelSystemInventoryError(
            "model regression manifest is not authoritative: "
            + "; ".join(non_materialization_errors)
        )
    materialized = set(model_inventory.materialized_ids)
    entries = tuple(
        entry for entry in manifest.entries if entry.model_id in materialized
    )
    if not entries:
        raise ModelSystemInventoryError("no available manifest model instances")
    inventories = {
        entry.model_id: resolve_entry_input_inventory(root_path, entry)
        for entry in entries
    }
    if not subject_revision:
        combined_by_path = {
            item["path"]: item["sha256"]
            for entry in entries
            for item in inventories[entry.model_id]
        }
        combined_inventory = tuple(
            {
                "path": path,
                "sha256": combined_by_path[path],
            }
            for path in sorted(combined_by_path)
        )
        subject_revision = (
            "source-inventory:"
            + input_inventory_fingerprint(combined_inventory).split(":", 1)[1]
        )
    instances = []
    for entry in entries:
        if entry.purpose_closure is None:
            raise ModelSystemInventoryError(
                f"{entry.model_id}: canonical model instance requires purpose closure"
            )
        instances.append(
            build_model_instance_ref(
                root_path,
                logical_model_id=entry.model_id,
                model_kind=entry.model_kind,
                model_path=entry.model_path,
                runner_path=entry.runner[1],
                purpose_closure_fingerprint=(
                    entry.purpose_closure.closure_fingerprint
                ),
                input_paths=tuple(
                    item["path"] for item in inventories[entry.model_id]
                ),
            )
        )
    instances = tuple(instances)
    by_id = {item.logical_model_id: item for item in instances}
    model_ids = set(by_id)
    path_to_model_id = {
        item.model_path.replace("\\", "/"): item.logical_model_id
        for item in instances
    }
    manifest_fingerprint = file_fingerprint(manifest.path)
    root_owner = AuthorityEndpointRef(
        endpoint_kind="parent_closure",
        endpoint_id=f"system:{system_id}:model-regression-manifest",
        fingerprint=manifest_fingerprint,
        owner_route="model_mesh_maintenance",
    )
    owner_refs: list[AuthorityEndpointRef] = [root_owner]
    relations: list[ModelRelation] = []
    owner_ref_keys: set[tuple[str, str]] = {
        (root_owner.endpoint_kind, root_owner.endpoint_id)
    }
    relation_keys: set[tuple[str, str, str, str, str]] = set()

    def bind_owner_artifact(
        *,
        model_endpoint: AuthorityEndpointRef,
        endpoint_kind: str,
        endpoint_id: str,
        owner_route: str,
        relation_kind: str,
        value: str,
        evidence_fingerprints: tuple[str, ...],
    ) -> None:
        endpoint = AuthorityEndpointRef(
            endpoint_kind=endpoint_kind,
            endpoint_id=endpoint_id,
            fingerprint=canonical_fingerprint(
                {
                    "endpoint_kind": endpoint_kind,
                    "endpoint_id": endpoint_id,
                    "value": value,
                }
            ),
            owner_route=owner_route,
        )
        owner_key = (endpoint.endpoint_kind, endpoint.endpoint_id)
        if owner_key not in owner_ref_keys:
            owner_refs.append(endpoint)
            owner_ref_keys.add(owner_key)
        relation_key = (
            relation_kind,
            model_endpoint.endpoint_kind,
            model_endpoint.endpoint_id,
            endpoint.endpoint_kind,
            endpoint.endpoint_id,
        )
        if relation_key in relation_keys:
            return
        relation_keys.add(relation_key)
        relations.append(
            ModelRelation(
                relation_id=_stable_id(
                    f"relation:model-{relation_kind}-{endpoint_kind}",
                    (
                        f"{model_endpoint.endpoint_kind}:"
                        f"{model_endpoint.endpoint_id}->"
                        f"{endpoint.endpoint_kind}:{endpoint.endpoint_id}"
                    ),
                ),
                kind=relation_kind,
                source=(
                    endpoint
                    if relation_kind == "validates"
                    else model_endpoint
                ),
                target=(
                    model_endpoint
                    if relation_kind == "validates"
                    else endpoint
                ),
                evidence_fingerprints=evidence_fingerprints,
            )
        )

    purpose_covered: list[str] = []
    test_required: list[str] = []
    for entry in entries:
        instance = by_id[entry.model_id]
        model_endpoint = AuthorityEndpointRef(
            endpoint_kind="model_instance",
            endpoint_id=f"model:{entry.model_id}",
            fingerprint=instance.fingerprint,
            owner_route="model_regression_manifest",
        )
        relations.append(
            ModelRelation(
                relation_id=f"relation:system-contains:{entry.model_id}",
                kind="contains",
                source=root_owner,
                target=model_endpoint,
                evidence_fingerprints=(manifest_fingerprint,),
            )
        )
        if entry.purpose_closure is None:
            continue
        purpose_endpoint = AuthorityEndpointRef(
            endpoint_kind="parent_closure",
            endpoint_id=f"purpose:{entry.model_id}",
            fingerprint=entry.purpose_closure.closure_fingerprint,
            owner_route="model_test_alignment",
        )
        owner_refs.append(purpose_endpoint)
        relations.append(
            ModelRelation(
                relation_id=f"relation:model-realizes-purpose:{entry.model_id}",
                kind="realizes",
                source=model_endpoint,
                target=purpose_endpoint,
                evidence_fingerprints=(
                    entry.purpose_closure.closure_fingerprint,
                ),
            )
        )
        purpose_covered.append(f"contract:purpose:{entry.model_id}")
        test_required.extend(entry.purpose_closure.evidence_check_ids)

    ledger_path, behavior_ledger = _commitment_records(root_path)
    commitments = tuple(
        item.to_dict() for item in behavior_ledger.commitments
    ) if behavior_ledger is not None else ()
    surfaces = tuple(
        item.to_dict() for item in behavior_ledger.source_surfaces
    ) if behavior_ledger is not None else ()
    ledger_review = (
        review_behavior_commitment_ledger(behavior_ledger)
        if behavior_ledger is not None
        else None
    )
    surfaces_by_id = {
        str(item.get("surface_id", "")).strip(): item
        for item in surfaces
        if str(item.get("surface_id", "")).strip()
    }
    linked_commitments: set[str] = set()
    linked_surface_ids: set[str] = set()
    fields_required: list[str] = []
    fields_covered: list[str] = []
    contracts_required: list[str] = list(purpose_covered)
    contracts_covered: list[str] = list(purpose_covered)
    tests_covered: list[str] = list(test_required)
    ledger_fingerprint = (
        file_fingerprint(ledger_path) if ledger_path is not None else ""
    )
    for commitment in commitments:
        commitment_id = str(commitment.get("commitment_id", "")).strip()
        if not commitment_id:
            continue
        commitment_endpoint = AuthorityEndpointRef(
            endpoint_kind="behavior_commitment",
            endpoint_id=commitment_id,
            fingerprint=canonical_fingerprint(dict(commitment)),
            owner_route="behavior_commitment_ledger",
        )
        owner_refs.append(commitment_endpoint)
        owner_ref_keys.add(
            (
                commitment_endpoint.endpoint_kind,
                commitment_endpoint.endpoint_id,
            )
        )
        for surface_id in _string_values(
            commitment.get("source_surface_ids")
        ):
            surface_record = surfaces_by_id.get(surface_id)
            if surface_record is None:
                continue
            surface_endpoint = AuthorityEndpointRef(
                endpoint_kind="external_surface",
                endpoint_id=surface_id,
                fingerprint=canonical_fingerprint(dict(surface_record)),
                owner_route="behavior_commitment_ledger",
            )
            surface_owner_key = (
                surface_endpoint.endpoint_kind,
                surface_endpoint.endpoint_id,
            )
            if surface_owner_key not in owner_ref_keys:
                owner_refs.append(surface_endpoint)
                owner_ref_keys.add(surface_owner_key)
            surface_relation_key = (
                "produces_for",
                surface_endpoint.endpoint_kind,
                surface_endpoint.endpoint_id,
                commitment_endpoint.endpoint_kind,
                commitment_endpoint.endpoint_id,
            )
            if surface_relation_key not in relation_keys:
                relation_keys.add(surface_relation_key)
                relations.append(
                    ModelRelation(
                        relation_id=_stable_id(
                            "relation:surface-produces-for-commitment",
                            f"{surface_id}->{commitment_id}",
                        ),
                        kind="produces_for",
                        source=surface_endpoint,
                        target=commitment_endpoint,
                        evidence_fingerprints=(
                            commitment_endpoint.fingerprint,
                            *((ledger_fingerprint,) if ledger_fingerprint else ()),
                        ),
                    )
                )
        owner_id = _owner_model_id(
            commitment.get("primary_owner_model_id"),
            path_to_model_id=path_to_model_id,
            model_ids=model_ids,
        )
        model_endpoint: AuthorityEndpointRef | None = None
        if owner_id:
            instance = by_id[owner_id]
            model_endpoint = AuthorityEndpointRef(
                endpoint_kind="model_instance",
                endpoint_id=f"model:{owner_id}",
                fingerprint=instance.fingerprint,
                owner_route="model_regression_manifest",
            )
            relations.append(
                ModelRelation(
                    relation_id=_stable_id(
                        "relation:model-realizes-commitment",
                        commitment_id,
                    ),
                    kind="realizes",
                    source=model_endpoint,
                    target=commitment_endpoint,
                    evidence_fingerprints=(
                        commitment_endpoint.fingerprint,
                        *((ledger_fingerprint,) if ledger_fingerprint else ()),
                    ),
                )
            )
            linked_commitments.add(commitment_id)
            linked_surface_ids.update(
                _string_values(commitment.get("source_surface_ids"))
            )
        for endpoint_kind, values in (
            (
                "field_inventory",
                _string_values(commitment.get("state_writes")),
            ),
            (
                "side_effect_inventory",
                _string_values(commitment.get("side_effects")),
            ),
        ):
            for value in values:
                field_id = _stable_id("field-or-effect", value)
                fields_required.append(field_id)
                if model_endpoint is not None:
                    fields_covered.append(field_id)
                    bind_owner_artifact(
                        model_endpoint=model_endpoint,
                        endpoint_kind=endpoint_kind,
                        endpoint_id=field_id,
                        owner_route="field_lifecycle_mesh",
                        relation_kind="realizes",
                        value=value,
                        evidence_fingerprints=(
                            commitment_endpoint.fingerprint,
                            *((ledger_fingerprint,) if ledger_fingerprint else ()),
                        ),
                    )
        for value in _evidence_values(commitment, "code_contract_ids"):
            contract_id = _stable_id("contract", value)
            contracts_required.append(contract_id)
            if model_endpoint is not None:
                contracts_covered.append(contract_id)
                bind_owner_artifact(
                    model_endpoint=model_endpoint,
                    endpoint_kind="code_contract",
                    endpoint_id=contract_id,
                    owner_route="model_test_alignment",
                    relation_kind="realizes",
                    value=value,
                    evidence_fingerprints=(
                        commitment_endpoint.fingerprint,
                        *((ledger_fingerprint,) if ledger_fingerprint else ()),
                    ),
                )
        for value in _evidence_values(commitment, "test_evidence_ids"):
            test_id = _stable_id("test", value)
            test_required.append(test_id)
            if model_endpoint is not None:
                tests_covered.append(test_id)
                bind_owner_artifact(
                    model_endpoint=model_endpoint,
                    endpoint_kind="test_evidence",
                    endpoint_id=test_id,
                    owner_route="test_mesh_maintenance",
                    relation_kind="validates",
                    value=value,
                    evidence_fingerprints=(
                        commitment_endpoint.fingerprint,
                        *((ledger_fingerprint,) if ledger_fingerprint else ()),
                    ),
                )

    affected_inventory = load_affected_authority_inventory(root_path)
    affected_required_ids: list[str] = []
    affected_covered_ids: list[str] = []
    affected_unresolved_ids: list[str] = []
    if affected_inventory is not None:
        inventory_endpoint = AuthorityEndpointRef(
            endpoint_kind="source_owner",
            endpoint_id=f"inventory:{affected_inventory.inventory_id}",
            fingerprint=affected_inventory.fingerprint,
            owner_route="authoritative_model_system",
        )
        owner_refs.append(inventory_endpoint)
        owner_ref_keys.add((inventory_endpoint.endpoint_kind, inventory_endpoint.endpoint_id))
        commitment_ids_present = {
            str(item.get("commitment_id", "")).strip()
            for item in commitments
            if str(item.get("commitment_id", "")).strip()
        }
        for component in affected_inventory.components:
            affected_required_ids.append(component.component_id)
            issues: list[str] = []
            if not component.model_owner_ids:
                issues.append("model_owner_missing")
            unknown_models = tuple(
                sorted(set(component.model_owner_ids) - model_ids)
            )
            if unknown_models:
                issues.extend(f"unknown_model:{item}" for item in unknown_models)
            source_path = root_path / component.primary_source_owner
            if not source_path.is_file():
                issues.append("primary_source_missing")
            missing_evidence = tuple(
                path
                for path in component.evidence_owner_ids
                if not (root_path / path).is_file()
            )
            if (not component.evidence_owner_ids or missing_evidence) and not component.gap_ids:
                issues.extend(
                    ("evidence_owner_missing",)
                    if not component.evidence_owner_ids
                    else tuple(f"evidence_owner_missing:{item}" for item in missing_evidence)
                )
            if not component.runtime_entry_ids:
                issues.append("runtime_entry_missing")
            invalid_runtime_entries = tuple(
                entry
                for entry in component.runtime_entry_ids
                if not _runtime_entry_available(entry)
            )
            issues.extend(
                f"runtime_entry_unavailable:{entry}"
                for entry in invalid_runtime_entries
            )
            if component.behavior_commitment_id not in commitment_ids_present:
                issues.append("behavior_commitment_missing")
            source_record = surfaces_by_id.get(component.source_surface_id)
            if source_record is None:
                issues.append("source_surface_missing")
            elif (
                str(source_record.get("source_ref", "")) != component.primary_source_owner
                or component.behavior_commitment_id
                not in _string_values(source_record.get("commitment_ids"))
            ):
                issues.append("source_surface_owner_mismatch")
            declared_relation_types = set(component.relation_types)
            actual_relation_types = {
                "implements",
                "validates",
                "invokes",
                "affects",
                *(kind for kind, _target in component.model_relations),
            }
            if not actual_relation_types.issubset(declared_relation_types):
                issues.append("declared_relation_types_incomplete")
            unknown_siblings = tuple(
                sorted(set(component.affected_sibling_ids) - model_ids)
            )
            if unknown_siblings:
                issues.extend(f"unknown_sibling:{item}" for item in unknown_siblings)
            for relation_kind, target_model_id in component.model_relations:
                if relation_kind not in {"refines", "consumes", "depends_on"}:
                    issues.append(f"unsupported_component_relation:{relation_kind}")
                if target_model_id not in model_ids:
                    issues.append(f"unknown_relation_target:{target_model_id}")

            if issues:
                affected_unresolved_ids.extend(
                    f"{component.component_id}:{issue}" for issue in sorted(set(issues))
                )
                continue

            affected_covered_ids.append(component.component_id)
            primary_model_id = component.model_owner_ids[0]
            primary_model = by_id[primary_model_id]
            model_endpoint = AuthorityEndpointRef(
                endpoint_kind="model_instance",
                endpoint_id=f"model:{primary_model_id}",
                fingerprint=primary_model.fingerprint,
                owner_route="model_regression_manifest",
            )
            source_endpoint = AuthorityEndpointRef(
                endpoint_kind="source_owner",
                endpoint_id=f"source:{component.primary_source_owner}",
                fingerprint=file_fingerprint(source_path),
                owner_route="affected_authority_inventory",
            )
            source_key = (source_endpoint.endpoint_kind, source_endpoint.endpoint_id)
            if source_key not in owner_ref_keys:
                owner_refs.append(source_endpoint)
                owner_ref_keys.add(source_key)
            relations.append(
                ModelRelation(
                    relation_id=_stable_id("relation:source-implements-model", component.component_id),
                    kind="implements",
                    source=source_endpoint,
                    target=model_endpoint,
                    evidence_fingerprints=(affected_inventory.fingerprint, source_endpoint.fingerprint),
                )
            )
            for evidence_owner in component.evidence_owner_ids:
                evidence_path = root_path / evidence_owner
                evidence_endpoint = AuthorityEndpointRef(
                    endpoint_kind="test_evidence",
                    endpoint_id=f"evidence:{evidence_owner}",
                    fingerprint=file_fingerprint(evidence_path),
                    owner_route="affected_authority_inventory",
                )
                evidence_key = (evidence_endpoint.endpoint_kind, evidence_endpoint.endpoint_id)
                if evidence_key not in owner_ref_keys:
                    owner_refs.append(evidence_endpoint)
                    owner_ref_keys.add(evidence_key)
                relations.append(
                    ModelRelation(
                        relation_id=_stable_id(
                            "relation:evidence-validates-model",
                            f"{component.component_id}:{evidence_owner}",
                        ),
                        kind="validates",
                        source=evidence_endpoint,
                        target=model_endpoint,
                        evidence_fingerprints=(affected_inventory.fingerprint, evidence_endpoint.fingerprint),
                    )
                )
            for runtime_entry in component.runtime_entry_ids:
                runtime_endpoint = AuthorityEndpointRef(
                    endpoint_kind="runtime_entry",
                    endpoint_id=f"runtime:{runtime_entry}",
                    fingerprint=canonical_fingerprint({"runtime_entry": runtime_entry}),
                    owner_route="affected_authority_inventory",
                )
                runtime_key = (runtime_endpoint.endpoint_kind, runtime_endpoint.endpoint_id)
                if runtime_key not in owner_ref_keys:
                    owner_refs.append(runtime_endpoint)
                    owner_ref_keys.add(runtime_key)
                relations.append(
                    ModelRelation(
                        relation_id=_stable_id(
                            "relation:model-invokes-runtime",
                            f"{component.component_id}:{runtime_entry}",
                        ),
                        kind="invokes",
                        source=model_endpoint,
                        target=runtime_endpoint,
                        evidence_fingerprints=(affected_inventory.fingerprint,),
                    )
                )
            for sibling_id in component.affected_sibling_ids:
                sibling_endpoint = AuthorityEndpointRef(
                    endpoint_kind="model_instance",
                    endpoint_id=f"model:{sibling_id}",
                    fingerprint=by_id[sibling_id].fingerprint,
                    owner_route="model_regression_manifest",
                )
                relations.append(
                    ModelRelation(
                        relation_id=_stable_id(
                            "relation:model-affects-sibling",
                            f"{component.component_id}:{sibling_id}",
                        ),
                        kind="affects",
                        source=model_endpoint,
                        target=sibling_endpoint,
                        evidence_fingerprints=(affected_inventory.fingerprint,),
                    )
                )
            for relation_kind, target_model_id in component.model_relations:
                target_endpoint = AuthorityEndpointRef(
                    endpoint_kind="model_instance",
                    endpoint_id=f"model:{target_model_id}",
                    fingerprint=by_id[target_model_id].fingerprint,
                    owner_route="model_regression_manifest",
                )
                relations.append(
                    ModelRelation(
                        relation_id=_stable_id(
                            f"relation:model-{relation_kind}-model",
                            f"{component.component_id}:{target_model_id}",
                        ),
                        kind=relation_kind,
                        source=model_endpoint,
                        target=target_endpoint,
                        evidence_fingerprints=(affected_inventory.fingerprint,),
                    )
                )

    surface_ids = tuple(
        str(item.get("surface_id", "")).strip()
        for item in surfaces
        if str(item.get("surface_id", "")).strip()
    )
    declared_surface_ids = (
        behavior_ledger.expected_source_surface_ids
        if behavior_ledger is not None and behavior_ledger.expected_source_surface_ids
        else surface_ids
    )
    affected_surface_ids = (
        tuple(item.source_surface_id for item in affected_inventory.components)
        if affected_inventory is not None
        else ()
    )
    expected_surface_ids = tuple(sorted(set(declared_surface_ids) | set(affected_surface_ids)))
    commitment_ids = tuple(
        str(item.get("commitment_id", "")).strip()
        for item in commitments
        if str(item.get("commitment_id", "")).strip()
    )
    dimensions_list = [
        CoverageDimension(
            "external_surfaces",
            required_ids=expected_surface_ids,
            covered_ids=tuple(
                sorted(
                    set(expected_surface_ids)
                    & set(surface_ids)
                    & linked_surface_ids
                )
            ),
            unresolved_ids=tuple(
                sorted(
                    (set(expected_surface_ids) - linked_surface_ids)
                    | (set(surface_ids) - set(expected_surface_ids))
                    | (
                        set(
                            ledger_review.missing_source_surface_ids
                            if ledger_review is not None
                            else ()
                        )
                    )
                    | (
                        set(
                            ledger_review.unexpected_source_surface_ids
                            if ledger_review is not None
                            else ()
                        )
                    )
                )
            ),
        ),
        CoverageDimension(
            "behavior_commitments",
            required_ids=commitment_ids,
            covered_ids=tuple(sorted(linked_commitments)),
            unresolved_ids=tuple(
                sorted(set(commitment_ids) - linked_commitments)
            ),
        ),
        CoverageDimension(
            "model_instances",
            required_ids=model_inventory.required_ids,
            covered_ids=model_inventory.covered_ids,
            unresolved_ids=model_inventory.missing_ids,
        ),
        CoverageDimension(
            "fields_state_side_effects",
            required_ids=tuple(sorted(set(fields_required))),
            covered_ids=tuple(sorted(set(fields_covered))),
            unresolved_ids=tuple(
                sorted(set(fields_required) - set(fields_covered))
            ),
        ),
        CoverageDimension(
            "code_contracts",
            required_ids=tuple(sorted(set(contracts_required))),
            covered_ids=tuple(sorted(set(contracts_covered))),
            unresolved_ids=tuple(
                sorted(set(contracts_required) - set(contracts_covered))
            ),
        ),
        CoverageDimension(
            "tests_evidence",
            required_ids=tuple(sorted(set(test_required))),
            covered_ids=tuple(sorted(set(tests_covered))),
            unresolved_ids=tuple(
                sorted(set(test_required) - set(tests_covered))
            ),
        ),
    ]
    dimensions_list.append(
        CoverageDimension(
            "affected_authority_relations",
            required_ids=tuple(sorted(affected_required_ids)),
            covered_ids=tuple(sorted(affected_covered_ids)),
            unresolved_ids=tuple(sorted(affected_unresolved_ids)),
        )
    )
    dimensions = tuple(dimensions_list)
    inventory_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "ledger_fingerprint": ledger_fingerprint,
        "behavior_source_inventory_fingerprint": (
            behavior_ledger.source_inventory_fingerprint
            if behavior_ledger is not None
            else ""
        ),
        "behavior_source_inventory_revision": (
            behavior_ledger.source_inventory_revision
            if behavior_ledger is not None
            else ""
        ),
        "affected_authority_inventory_fingerprint": (
            affected_inventory.fingerprint if affected_inventory is not None else ""
        ),
        "expected_behavior_source_ids": list(expected_surface_ids),
        "model_instances": {
            entry.model_id: input_inventory_fingerprint(
                inventories[entry.model_id]
            )
            for entry in entries
        },
        "model_inventory": model_inventory.to_dict(),
    }
    coverage = CoverageUniverse(
        boundary_id=f"{system_id}:manifest-ledger-owner-boundary",
        source_inventory_fingerprint=canonical_fingerprint(
            inventory_payload
        ),
        dimensions=dimensions,
        claim_boundary=(
            "Coverage is exhaustive only for the current regression manifest, "
            "the current behavior-commitment ledger, their resolved model inputs, "
            "and their declared contract and test references."
        ),
    )
    unresolved_gap_ids = tuple(
        sorted(
            {
                _stable_id(
                    f"gap:{dimension.dimension_id}",
                    value,
                )
                for dimension in dimensions
                for value in (
                    *dimension.missing_ids,
                    *dimension.unresolved_ids,
                )
            }
        )
    )
    root_id = (
        "authoritative_model_system"
        if "authoritative_model_system" in by_id
        else sorted(by_id)[0]
    )
    return ModelSystemSnapshot(
        snapshot_id=snapshot_id,
        system_id=system_id,
        subject_lane=subject_lane,
        lifecycle=lifecycle,
        subject_revision=subject_revision,
        root_instance_fingerprints=(by_id[root_id].fingerprint,),
        model_instances=instances,
        relations=tuple(relations),
        coverage=coverage,
        owner_artifact_refs=tuple(owner_refs),
        unresolved_gap_ids=unresolved_gap_ids,
        claim_boundary=(
            "This snapshot is the sole finite project model-system view assembled "
            "from existing regression, ModelMesh, BehaviorCommitmentLedger, "
            "Model-Test Alignment, and TestMesh owner artifacts. Unresolved gaps "
            "remain explicit and cannot support a full-coverage claim."
        ),
    )


__all__ = [
    "AffectedAuthorityComponent",
    "AffectedAuthorityInventory",
    "ManifestModelInventory",
    "ModelSystemInventoryError",
    "build_manifest_model_system_snapshot",
    "inspect_manifest_model_inventory",
    "load_affected_authority_inventory",
]
