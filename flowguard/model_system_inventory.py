"""Build one bounded model-system snapshot from existing FlowGuard owners."""

from __future__ import annotations

import hashlib
import json
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
    canonical_fingerprint,
    file_fingerprint,
)
from .model_regressions import (
    ModelRegressionEntry,
    ModelRegressionManifest,
    audit_manifest,
    build_regression_model_instance,
    input_inventory_fingerprint,
    resolve_entry_input_inventory,
)


class ModelSystemInventoryError(ValueError):
    """Raised when existing owner artifacts cannot form a bounded snapshot."""


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
) -> tuple[Path | None, tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    path = (
        root
        / ".flowguard"
        / "behavior_commitment_ledger"
        / "ledger.json"
    )
    if not path.is_file():
        return None, (), ()
    payload = _load_json_object(path)
    ledger = payload.get("ledger")
    if not isinstance(ledger, Mapping):
        raise ModelSystemInventoryError(
            "behavior commitment artifact has no ledger object"
        )
    commitments = tuple(
        item
        for item in ledger.get("commitments", ())
        if isinstance(item, Mapping)
    )
    surfaces = tuple(
        item
        for item in ledger.get("source_surfaces", ())
        if isinstance(item, Mapping)
    )
    return path, commitments, surfaces


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
    manifest_audit = audit_manifest(root_path, manifest)
    if not manifest_audit.ok:
        raise ModelSystemInventoryError(
            "model regression manifest is not authoritative: "
            + "; ".join(manifest_audit.errors)
        )
    entries = _available_entries(root_path, manifest)
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
    instances = tuple(
        build_regression_model_instance(
            root_path,
            entry,
            inventories[entry.model_id],
            subject_revision=subject_revision,
        )
        for entry in entries
    )
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

    ledger_path, commitments, surfaces = _commitment_records(root_path)
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

    surface_ids = tuple(
        str(item.get("surface_id", "")).strip()
        for item in surfaces
        if str(item.get("surface_id", "")).strip()
    )
    commitment_ids = tuple(
        str(item.get("commitment_id", "")).strip()
        for item in commitments
        if str(item.get("commitment_id", "")).strip()
    )
    available_ids = tuple(sorted(model_ids))
    absent_optional = tuple(
        sorted(
            entry.model_id
            for entry in manifest.entries
            if (
                entry.distribution_policy == "optional_local"
                and entry.model_id not in model_ids
            )
        )
    )
    dimensions = (
        CoverageDimension(
            "external_surfaces",
            required_ids=surface_ids,
            covered_ids=tuple(sorted(set(surface_ids) & linked_surface_ids)),
            unresolved_ids=tuple(
                sorted(set(surface_ids) - linked_surface_ids)
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
            required_ids=available_ids,
            covered_ids=available_ids,
            excluded_ids=absent_optional,
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
    )
    inventory_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "ledger_fingerprint": ledger_fingerprint,
        "model_instances": {
            entry.model_id: input_inventory_fingerprint(
                inventories[entry.model_id]
            )
            for entry in entries
        },
        "absent_optional_model_ids": list(absent_optional),
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
    "ModelSystemInventoryError",
    "build_manifest_model_system_snapshot",
]
