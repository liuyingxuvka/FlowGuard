"""Produce exact native-owner evidence for one model revision candidate.

The full model-regression parent remains a parent.  This module verifies its
real model-owner children, maps the affected revision closure to the native
semantic owners, and emits one distinct child-bound validation-owner receipt
per affected owner.  It never runs model regressions or activates authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .evidence_receipts import (
    RECEIPT_STATUS_PASS,
    EvidenceReceipt,
    ReceiptVerificationResult,
    fingerprint_value,
    load_evidence_receipt,
    verify_evidence_receipt,
)
from .model_authority import ModelAuthorityError, ModelSystemSnapshot
from .model_authority_store import load_observed_model_system
from .model_revision_builder import (
    _VerifiedModelParent,
    _parent_children,
    _read_json,
    _verify_model_parent_receipt,
)
from .model_revision_set import (
    RevisionAffectedClosure,
    RevisionSnapshotDiff,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from .model_system_inventory import build_manifest_model_system_snapshot
from .project_manifest import project_manifest_lock
from .validation_ownership import (
    OWNER_RECEIPT_KIND,
    OWNER_RECEIPT_SCOPE,
    ValidationOwnerContract,
    ValidationOwnerObservation,
    ValidationObservationFreshness,
    _assert_owner_receipt_integrity,
    assert_validation_owner_observation_fresh,
    build_child_bound_owner_receipt_context,
    build_owner_current_from_observation,
    save_child_bound_owner_receipt_from_observation,
)


MODEL_REVISION_OWNER_EVIDENCE_REPORT_SCHEMA = (
    "flowguard.model_revision_owner_evidence_report.v1"
)
NATIVE_OWNER_BINDINGS_SCHEMA = "flowguard.native_owner_model_bindings.v1"
NATIVE_OWNER_BINDINGS_RELATIVE_PATH = ".flowguard/native-owner-bindings.json"


@dataclass(frozen=True)
class NativeOwnerModelBinding:
    """One semantic owner route and the model children that prove its lane."""

    owner_route: str
    model_ids: tuple[str, ...]
    protected_failure_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        owner_route = str(self.owner_route).strip()
        model_ids = tuple(
            sorted({str(item).strip() for item in self.model_ids if str(item).strip()})
        )
        protected_failure_ids = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in self.protected_failure_ids
                    if str(item).strip()
                }
            )
        )
        if not owner_route or not model_ids:
            raise ValueError("native owner route and model ids are required")
        object.__setattr__(self, "owner_route", owner_route)
        object.__setattr__(self, "model_ids", model_ids)
        object.__setattr__(self, "protected_failure_ids", protected_failure_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_route": self.owner_route,
            "model_ids": list(self.model_ids),
            "protected_failure_ids": list(self.protected_failure_ids),
        }


@dataclass(frozen=True)
class NativeOwnerModelEvidencePlan:
    """Exact model children one affected native owner must consume.

    ``semantic_model_ids`` anchors the owner's own FlowGuard lane.  The
    independently derived ``referenced_changed_model_ids`` closes over every
    changed *current* model/model-instance named by that owner's affected
    closure. ``removed_referenced_model_ids`` keeps removed model identities
    explicit without requiring a nonexistent current child to certify its own
    retirement.  The resulting ``required_model_ids`` must be the exact union
    of the semantic lane and current referenced models: neither a convenient
    single lane receipt nor an unrelated global run is sufficient.  Removal
    lifecycle authority remains separately mandatory in the revision builder.
    """

    owner_route: str
    affected_ids: tuple[str, ...]
    semantic_model_ids: tuple[str, ...]
    referenced_changed_model_ids: tuple[str, ...]
    removed_referenced_model_ids: tuple[str, ...]
    required_model_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        owner_route = str(self.owner_route).strip()
        if not owner_route:
            raise ValueError("native owner evidence plan requires an owner route")

        def normalized(values: Sequence[str]) -> tuple[str, ...]:
            return tuple(
                sorted({str(item).strip() for item in values if str(item).strip()})
            )

        affected_ids = normalized(self.affected_ids)
        semantic_model_ids = normalized(self.semantic_model_ids)
        referenced_changed_model_ids = normalized(
            self.referenced_changed_model_ids
        )
        removed_referenced_model_ids = normalized(
            self.removed_referenced_model_ids
        )
        required_model_ids = normalized(self.required_model_ids)
        if not affected_ids or not semantic_model_ids or not required_model_ids:
            raise ValueError(
                "native owner evidence plan requires affected ids and model ids"
            )
        expected_required = tuple(
            sorted(set(semantic_model_ids) | set(referenced_changed_model_ids))
        )
        if required_model_ids != expected_required:
            raise ValueError(
                "native owner evidence plan must require every semantic and "
                "current referenced changed model"
            )
        if set(removed_referenced_model_ids).intersection(required_model_ids):
            raise ValueError(
                "removed referenced models cannot require current model children"
            )
        object.__setattr__(self, "owner_route", owner_route)
        object.__setattr__(self, "affected_ids", affected_ids)
        object.__setattr__(self, "semantic_model_ids", semantic_model_ids)
        object.__setattr__(
            self,
            "referenced_changed_model_ids",
            referenced_changed_model_ids,
        )
        object.__setattr__(
            self,
            "removed_referenced_model_ids",
            removed_referenced_model_ids,
        )
        object.__setattr__(self, "required_model_ids", required_model_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_route": self.owner_route,
            "affected_ids": list(self.affected_ids),
            "semantic_model_ids": list(self.semantic_model_ids),
            "referenced_changed_model_ids": list(
                self.referenced_changed_model_ids
            ),
            "removed_referenced_model_ids": list(
                self.removed_referenced_model_ids
            ),
            "required_model_ids": list(self.required_model_ids),
        }


def _load_native_owner_model_bindings(
    root: Path,
    snapshot: ModelSystemSnapshot,
) -> dict[str, NativeOwnerModelBinding]:
    """Load and validate the target project's current owner declaration.

    The public FlowGuard runtime deliberately has no product-owned model map.
    A target project declares its current model denominator and semantic owner
    bindings; FlowGuard only checks exactness and evidence identity.
    """

    path = root / NATIVE_OWNER_BINDINGS_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelAuthorityError(
            f"current native owner declaration is required: {NATIVE_OWNER_BINDINGS_RELATIVE_PATH}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelAuthorityError(
            f"current native owner declaration is unreadable: {path}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError("native owner declaration must be a JSON object")
    required = {
        "schema",
        "system_id",
        "candidate_model_ids",
        "bindings",
        "claim_boundary",
    }
    if set(payload) != required:
        raise ModelAuthorityError(
            "native owner declaration fields are not exact: "
            f"missing={sorted(required - set(payload))}; "
            f"unknown={sorted(set(payload) - required)}"
        )
    if payload["schema"] != NATIVE_OWNER_BINDINGS_SCHEMA:
        raise ModelAuthorityError(
            f"native owner declaration schema must be {NATIVE_OWNER_BINDINGS_SCHEMA}"
        )
    if str(payload["system_id"]) != snapshot.system_id:
        raise ModelAuthorityError(
            "native owner declaration system_id does not match the current snapshot"
        )
    declared_model_ids = tuple(
        sorted(
            {
                str(item).strip()
                for item in payload["candidate_model_ids"]
                if str(item).strip()
            }
        )
    )
    actual_model_ids = tuple(
        sorted(item.logical_model_id for item in snapshot.model_instances)
    )
    if declared_model_ids != actual_model_ids:
        raise ModelAuthorityError(
            "native owner declaration model denominator is not exact: "
            f"missing={sorted(set(actual_model_ids) - set(declared_model_ids))}; "
            f"extra={sorted(set(declared_model_ids) - set(actual_model_ids))}"
        )
    rows: dict[str, NativeOwnerModelBinding] = {}
    from .model_regressions import ModelRegressionManifest

    manifest = ModelRegressionManifest.load(root)
    manifest_entries = {entry.model_id: entry for entry in manifest.entries}
    raw_bindings = payload["bindings"]
    if not isinstance(raw_bindings, list):
        raise ModelAuthorityError("native owner declaration bindings must be an array")
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise ModelAuthorityError("native owner declaration binding must be an object")
        allowed = {"owner_route", "model_ids", "protected_failure_ids"}
        if set(raw) != allowed:
            raise ModelAuthorityError("native owner declaration binding fields are not exact")
        binding = NativeOwnerModelBinding(
            owner_route=str(raw["owner_route"]),
            model_ids=tuple(str(item) for item in raw["model_ids"]),
            protected_failure_ids=tuple(
                str(item) for item in raw["protected_failure_ids"]
            ),
        )
        if binding.owner_route in rows:
            raise ModelAuthorityError(
                f"native owner declaration duplicates route: {binding.owner_route}"
            )
        missing_models = sorted(set(binding.model_ids) - set(actual_model_ids))
        if missing_models:
            raise ModelAuthorityError(
                f"native owner declaration names foreign models for {binding.owner_route}: {missing_models}"
            )
        if not binding.protected_failure_ids:
            raise ModelAuthorityError(
                f"native owner declaration requires protected failures for {binding.owner_route}"
            )
        for model_id in binding.model_ids:
            entry = manifest_entries.get(model_id)
            if entry is None or entry.purpose_closure is None:
                raise ModelAuthorityError(
                    f"native owner declaration model has no current purpose closure: {model_id}"
                )
            missing_failures = sorted(
                set(binding.protected_failure_ids)
                - set(entry.purpose_closure.protected_failure_ids)
            )
            if missing_failures:
                raise ModelAuthorityError(
                    f"native owner declaration protected failures are not owned by {model_id}: {missing_failures}"
                )
        rows[binding.owner_route] = binding
    expected_routes = set(_candidate_native_owner_route_universe(snapshot))
    if set(rows) != expected_routes:
        raise ModelAuthorityError(
            "native owner declaration route set is not exact: "
            f"missing={sorted(expected_routes - set(rows))}; "
            f"extra={sorted(set(rows) - expected_routes)}"
        )
    return rows


@dataclass(frozen=True)
class ModelRevisionOwnerEvidenceBundle:
    """Strict wire bundle consumed directly by ``model-revision-build``."""

    contracts: tuple[ValidationOwnerContract, ...]
    receipts: tuple[EvidenceReceipt, ...]
    verification_results: tuple[ReceiptVerificationResult, ...]

    def __post_init__(self) -> None:
        contract_owners = tuple(item.owner_id for item in self.contracts)
        receipt_owners = tuple(
            item.subject_id.removeprefix("validation-owner:")
            for item in self.receipts
        )
        result_ids = tuple(item.receipt_id for item in self.verification_results)
        receipt_ids = tuple(item.receipt_id for item in self.receipts)
        if len(contract_owners) != len(set(contract_owners)):
            raise ValueError("native owner evidence contracts must be unique")
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("native owner evidence receipts must be unique")
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("native owner evidence verifications must be unique")
        if contract_owners != receipt_owners:
            raise ValueError(
                "native owner evidence contracts and receipts must have exact order"
            )
        if receipt_ids != result_ids:
            raise ValueError(
                "native owner evidence receipts and verifications must have exact order"
            )

    def to_dict(self) -> dict[str, Any]:
        # This exact three-field surface is already the strict
        # model-revision-build input contract.
        return {
            "contracts": [item.to_dict() for item in self.contracts],
            "receipts": [item.to_dict() for item in self.receipts],
            "verification_results": [
                item.to_dict() for item in self.verification_results
            ],
        }


@dataclass(frozen=True)
class ModelRevisionOwnerEvidenceReport:
    root: str
    output_path: str
    parent_receipt_path: str
    parent_receipt_fingerprint: str
    observed_head_fingerprint: str
    candidate_snapshot_fingerprint: str
    snapshot_diff_fingerprint: str
    affected_closure_fingerprint: str
    affected_owner_routes: tuple[str, ...]
    owner_receipt_ids: tuple[str, ...]
    bundle: ModelRevisionOwnerEvidenceBundle
    initial_observation_fingerprint: str = ""
    final_freshness_fingerprint: str = ""
    initial_observation_seconds: float = 0.0
    final_freshness_seconds: float = 0.0
    status: str = RECEIPT_STATUS_PASS
    schema: str = MODEL_REVISION_OWNER_EVIDENCE_REPORT_SCHEMA
    claim_boundary: str = (
        "This report proves one exact-current full model-regression parent was "
        "recomposed into distinct current native-owner receipts over one frozen "
        "candidate closure. It does not rerun models, activate model authority, "
        "or prove release readiness."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "root": self.root,
            "output_path": self.output_path,
            "parent_receipt_path": self.parent_receipt_path,
            "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
            "observed_head_fingerprint": self.observed_head_fingerprint,
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "snapshot_diff_fingerprint": self.snapshot_diff_fingerprint,
            "affected_closure_fingerprint": self.affected_closure_fingerprint,
            "affected_owner_routes": list(self.affected_owner_routes),
            "owner_receipt_ids": list(self.owner_receipt_ids),
            "validation_observation": {
                "initial_fingerprint": self.initial_observation_fingerprint,
                "final_freshness_fingerprint": (
                    self.final_freshness_fingerprint
                ),
                "initial_seconds": self.initial_observation_seconds,
                "final_freshness_seconds": self.final_freshness_seconds,
                "complete_observation_count": 2,
            },
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class VerifiedModelRevisionOwnerEvidence:
    """Independently re-derived current evidence consumed by revision build."""

    bundle: ModelRevisionOwnerEvidenceBundle
    parent_receipt_fingerprint: str
    observed_head_fingerprint: str
    candidate_snapshot_fingerprint: str
    snapshot_diff_fingerprint: str
    affected_closure_fingerprint: str
    validation_observation: ValidationOwnerObservation
    freshness: ValidationObservationFreshness
    mapped_children: Mapping[str, tuple["_MappedModelChild", ...]]
    owner_currents: Mapping[str, Any]
    parent_receipt_path: str
    receipt_root: str


@dataclass(frozen=True)
class _FrozenRevisionInputs:
    observed_head_fingerprint: str
    base_snapshot: ModelSystemSnapshot
    candidate_snapshot: ModelSystemSnapshot
    snapshot_diff: RevisionSnapshotDiff
    affected_closure: RevisionAffectedClosure


@dataclass(frozen=True)
class _MappedModelChild:
    model_id: str
    contract: ValidationOwnerContract
    receipt: EvidenceReceipt
    verification: ReceiptVerificationResult


def _bindings_by_owner(
    snapshot: ModelSystemSnapshot | None = None,
    *,
    root: Path | None = None,
) -> dict[str, NativeOwnerModelBinding]:
    if snapshot is None or root is None:
        raise ModelAuthorityError(
            "native owner declaration requires both current snapshot and project root"
        )
    return _load_native_owner_model_bindings(root, snapshot)


def _candidate_native_owner_route_universe(
    snapshot: ModelSystemSnapshot,
) -> tuple[str, ...]:
    """Derive every native-owner route the current candidate can emit.

    Relation and owner-artifact endpoints carry their own semantic route, while
    model instances are always validated by Model-Test Alignment.  Canonical
    diff, relation, coverage, and system wrappers without an endpoint route are
    owned by ModelMesh.  This is a candidate capability denominator, not an
    affected-work selector: evidence generation still runs only the exact
    affected routes.
    """

    routes = {"model_mesh_maintenance", "model_test_alignment"}
    routes.update(item.owner_route for item in snapshot.owner_artifact_refs)
    for relation in snapshot.relations:
        for endpoint in (relation.source, relation.target):
            routes.add(
                "model_test_alignment"
                if endpoint.endpoint_kind == "model_instance"
                else endpoint.owner_route
            )
    return tuple(sorted(routes))


def _freeze_revision_inputs(root: Path, snapshot_id: str) -> _FrozenRevisionInputs:
    head, base = load_observed_model_system(root)
    candidate = build_manifest_model_system_snapshot(
        root,
        snapshot_id=snapshot_id,
        system_id=base.system_id,
        subject_lane=base.subject_lane,
        lifecycle=base.lifecycle,
    )
    diff = derive_revision_snapshot_diff(base, candidate)
    closure = derive_revision_affected_closure(base, candidate, diff)
    if not closure.affected_ids:
        raise ModelAuthorityError(
            "current manifest does not differ from the observed model authority"
        )
    return _FrozenRevisionInputs(
        observed_head_fingerprint=head.fingerprint,
        base_snapshot=base,
        candidate_snapshot=candidate,
        snapshot_diff=diff,
        affected_closure=closure,
    )


def _assert_frozen_revision_inputs(
    root: Path,
    snapshot_id: str,
    frozen: _FrozenRevisionInputs,
) -> None:
    current = _freeze_revision_inputs(root, snapshot_id)
    comparisons = (
        (
            "observed authority head",
            frozen.observed_head_fingerprint,
            current.observed_head_fingerprint,
        ),
        (
            "base snapshot",
            frozen.base_snapshot.fingerprint,
            current.base_snapshot.fingerprint,
        ),
        (
            "candidate snapshot",
            frozen.candidate_snapshot.fingerprint,
            current.candidate_snapshot.fingerprint,
        ),
        (
            "snapshot diff",
            frozen.snapshot_diff.fingerprint,
            current.snapshot_diff.fingerprint,
        ),
        (
            "affected closure",
            frozen.affected_closure.fingerprint,
            current.affected_closure.fingerprint,
        ),
    )
    changed = tuple(name for name, expected, actual in comparisons if expected != actual)
    if changed:
        raise ModelAuthorityError(
            "frozen model revision inputs changed before evidence output: "
            + ", ".join(changed)
        )


def _affected_ids_by_owner(
    closure: RevisionAffectedClosure,
) -> dict[str, tuple[str, ...]]:
    rows: dict[str, list[str]] = {}
    for affected_id, owner_route in closure.owner_bindings:
        rows.setdefault(owner_route, []).append(affected_id)
    return {
        owner_route: tuple(sorted(affected_ids))
        for owner_route, affected_ids in sorted(rows.items())
    }


def _affected_id_references_model(
    affected_id: str,
    model_id: str,
) -> bool:
    """Recognize canonical model endpoints without prefix-name collisions."""

    endpoint = f"model_instance:model:{model_id}"
    start = 0
    while True:
        index = affected_id.find(endpoint, start)
        if index < 0:
            break
        end = index + len(endpoint)
        if end == len(affected_id) or affected_id[end : end + 2] == "--":
            return True
        start = index + 1
    return affected_id in {
        f"root:model:{model_id}",
        f"parent_closure:purpose:{model_id}",
        f"model_relation:relation:model-realizes-purpose:{model_id}",
        f"model_relation:relation:system-contains:{model_id}",
    }


def _derive_native_owner_model_plans(
    frozen: _FrozenRevisionInputs,
    bindings: Mapping[str, NativeOwnerModelBinding],
) -> dict[str, NativeOwnerModelEvidencePlan]:
    affected_by_owner = _affected_ids_by_owner(frozen.affected_closure)
    current_changed_model_ids = tuple(
        sorted(
            {
                member.member_id
                for member in frozen.snapshot_diff.members
                if member.operation != "remove"
            }
        )
    )
    removed_changed_model_ids = tuple(
        sorted(
            {
                member.member_id
                for member in frozen.snapshot_diff.members
                if member.operation == "remove"
            }
        )
    )
    plans: dict[str, NativeOwnerModelEvidencePlan] = {}
    for owner_route, affected_ids in sorted(affected_by_owner.items()):
        binding = bindings[owner_route]
        referenced = tuple(
            model_id
            for model_id in current_changed_model_ids
            if any(
                _affected_id_references_model(affected_id, model_id)
                for affected_id in affected_ids
            )
        )
        removed_referenced = tuple(
            model_id
            for model_id in removed_changed_model_ids
            if any(
                _affected_id_references_model(affected_id, model_id)
                for affected_id in affected_ids
            )
        )
        required = tuple(sorted(set(binding.model_ids) | set(referenced)))
        plans[owner_route] = NativeOwnerModelEvidencePlan(
            owner_route=owner_route,
            affected_ids=affected_ids,
            semantic_model_ids=binding.model_ids,
            referenced_changed_model_ids=referenced,
            removed_referenced_model_ids=removed_referenced,
            required_model_ids=required,
        )
    return plans


def _validate_native_owner_model_plans(
    frozen: _FrozenRevisionInputs,
    bindings: Mapping[str, NativeOwnerModelBinding],
    plans: Mapping[str, NativeOwnerModelEvidencePlan],
) -> None:
    """Independently reject omitted, foreign, or drifted owner-model coverage."""

    affected_by_owner = _affected_ids_by_owner(frozen.affected_closure)
    current_changed_model_ids = tuple(
        sorted(
            {
                member.member_id
                for member in frozen.snapshot_diff.members
                if member.operation != "remove"
            }
        )
    )
    removed_changed_model_ids = tuple(
        sorted(
            {
                member.member_id
                for member in frozen.snapshot_diff.members
                if member.operation == "remove"
            }
        )
    )
    if set(plans) != set(affected_by_owner):
        missing = sorted(set(affected_by_owner).difference(plans))
        foreign = sorted(set(plans).difference(affected_by_owner))
        raise ModelAuthorityError(
            "native owner evidence plan routes are not exact: "
            f"missing={missing}, foreign={foreign}"
        )
    for owner_route, affected_ids in affected_by_owner.items():
        binding = bindings[owner_route]
        referenced = tuple(
            model_id
            for model_id in current_changed_model_ids
            if any(
                _affected_id_references_model(affected_id, model_id)
                for affected_id in affected_ids
            )
        )
        removed_referenced = tuple(
            model_id
            for model_id in removed_changed_model_ids
            if any(
                _affected_id_references_model(affected_id, model_id)
                for affected_id in affected_ids
            )
        )
        expected_required = tuple(
            sorted(set(binding.model_ids) | set(referenced))
        )
        actual = plans[owner_route]
        if (
            actual.owner_route != owner_route
            or actual.affected_ids != affected_ids
            or actual.semantic_model_ids != binding.model_ids
            or actual.referenced_changed_model_ids != referenced
            or actual.removed_referenced_model_ids != removed_referenced
            or actual.required_model_ids != expected_required
        ):
            missing_models = sorted(
                set(expected_required).difference(actual.required_model_ids)
            )
            foreign_models = sorted(
                set(actual.required_model_ids).difference(
                    expected_required
                )
            )
            raise ModelAuthorityError(
                "native owner evidence plan does not bind every affected "
                f"model instance for {owner_route}: "
                f"missing={missing_models}, foreign={foreign_models}"
            )


def _load_parent_children(
    parent_receipt_path: Path,
) -> dict[str, Mapping[str, str]]:
    payload = _read_json(parent_receipt_path)
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError("model parent receipt must be a JSON object")
    children = _parent_children(payload.get("children"))
    return {row["model_id"]: row for row in children}


def _collect_mapped_model_children(
    root: Path,
    receipt_root: Path,
    parent_receipt_path: Path,
    frozen: _FrozenRevisionInputs,
    *,
    verified_parent: _VerifiedModelParent | None = None,
) -> tuple[
    dict[str, NativeOwnerModelEvidencePlan],
    dict[str, tuple[_MappedModelChild, ...]],
    str,
    ValidationOwnerObservation,
]:
    current_parent = verified_parent or _verify_model_parent_receipt(
        root, parent_receipt_path, receipt_root
    )
    parent_children = _load_parent_children(parent_receipt_path)
    affected_by_owner = _affected_ids_by_owner(frozen.affected_closure)
    bindings = _bindings_by_owner(frozen.candidate_snapshot, root=root)
    candidate_routes = _candidate_native_owner_route_universe(
        frozen.candidate_snapshot
    )
    missing_candidate_bindings = tuple(
        sorted(set(candidate_routes).difference(bindings))
    )
    if missing_candidate_bindings:
        raise ModelAuthorityError(
            "missing native owner model mapping in current candidate route "
            "universe: " + ", ".join(missing_candidate_bindings)
        )
    missing_bindings = tuple(
        sorted(set(affected_by_owner).difference(bindings))
    )
    if missing_bindings:
        raise ModelAuthorityError(
            "missing native owner model mapping: " + ", ".join(missing_bindings)
        )
    plans = _derive_native_owner_model_plans(frozen, bindings)
    _validate_native_owner_model_plans(frozen, bindings, plans)

    available_model_ids = set(current_parent.contracts_by_model)
    candidate_model_ids = {
        item.logical_model_id for item in frozen.candidate_snapshot.model_instances
    }
    required_model_ids = tuple(
        sorted(
            {
                model_id
                for owner_route in sorted(affected_by_owner)
                for model_id in plans[owner_route].required_model_ids
            }
        )
    )
    missing_manifest_models = tuple(
        sorted(set(required_model_ids).difference(available_model_ids))
    )
    if missing_manifest_models:
        raise ModelAuthorityError(
            "native owner mapped model is absent from the current full manifest: "
            + ", ".join(missing_manifest_models)
        )
    missing_candidate_models = tuple(
        sorted(set(required_model_ids).difference(candidate_model_ids))
    )
    if missing_candidate_models:
        raise ModelAuthorityError(
            "native owner mapped model is absent from candidate semantics: "
            + ", ".join(missing_candidate_models)
        )
    missing_parent_models = tuple(
        sorted(set(required_model_ids).difference(parent_children))
    )
    if missing_parent_models:
        raise ModelAuthorityError(
            "native owner mapped model is absent from the full parent: "
            + ", ".join(missing_parent_models)
        )

    mapped: dict[str, tuple[_MappedModelChild, ...]] = {}
    for owner_route in sorted(affected_by_owner):
        children: list[_MappedModelChild] = []
        for model_id in plans[owner_route].required_model_ids:
            owner_id = f"model:{model_id}"
            receipt = current_parent.receipts_by_model[model_id]
            parent_child = parent_children[model_id]
            if (
                parent_child["receipt_id"] != receipt.receipt_id
                or parent_child["receipt_fingerprint"] != receipt.fingerprint
            ):
                raise ModelAuthorityError(
                    f"full parent mapped child is not exact current: {model_id}"
                )
            if (
                receipt.subject_id != f"validation-owner:model:{model_id}"
                or receipt.subject_kind != OWNER_RECEIPT_KIND
                or receipt.producer_id != receipt.subject_id
                or receipt.claim_scope != OWNER_RECEIPT_SCOPE
                or receipt.result_status != RECEIPT_STATUS_PASS
                or receipt.exit_code != 0
                or receipt.skipped_checks
                or receipt.blockers
            ):
                raise ModelAuthorityError(
                    f"mapped model child is not a terminal exact full leaf: {model_id}"
                )
            verification = current_parent.verifications_by_model[model_id]
            if not verification.ok:
                raise ModelAuthorityError(
                    f"mapped model child failed currentness verification: {model_id}"
                )
            children.append(
                _MappedModelChild(
                    model_id=model_id,
                    contract=current_parent.contracts_by_model[model_id],
                    receipt=receipt,
                    verification=verification,
                )
            )
        mapped[owner_route] = tuple(children)
    return (
        plans,
        mapped,
        current_parent.fingerprint,
        current_parent.observation,
    )


def _producer_command(
    root: Path,
    parent_receipt_path: Path,
    receipt_root: Path,
    snapshot_id: str,
) -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "flowguard",
        "model-revision-owner-evidence",
        "--root",
        str(root),
        "--model-parent-receipt",
        str(parent_receipt_path),
        "--snapshot-id",
        snapshot_id,
        "--receipt-root",
        str(receipt_root),
    )


def _owner_contracts(
    root: Path,
    parent_receipt_path: Path,
    receipt_root: Path,
    snapshot_id: str,
    frozen: _FrozenRevisionInputs,
    plans: Mapping[str, NativeOwnerModelEvidencePlan],
    mapped_children: Mapping[str, Sequence[_MappedModelChild]],
    parent_receipt_fingerprint: str,
) -> tuple[ValidationOwnerContract, ...]:
    affected_by_owner = _affected_ids_by_owner(frozen.affected_closure)
    binding_fingerprint = fingerprint_value(
        [plans[owner].to_dict() for owner in sorted(affected_by_owner)]
    )
    command = _producer_command(
        root,
        parent_receipt_path,
        receipt_root,
        snapshot_id,
    )
    contracts: list[ValidationOwnerContract] = []
    for owner_route in sorted(affected_by_owner):
        affected_ids = affected_by_owner[owner_route]
        projected_inputs = [
            ("model-revision:observed-head", frozen.observed_head_fingerprint),
            ("model-revision:base", frozen.base_snapshot.fingerprint),
            ("model-revision:candidate", frozen.candidate_snapshot.fingerprint),
            ("model-revision:diff", frozen.snapshot_diff.fingerprint),
            ("model-revision:closure", frozen.affected_closure.fingerprint),
            ("model-revision:owner-model-map", binding_fingerprint),
            ("model-regression:parent", parent_receipt_fingerprint),
            (
                f"model-revision:affected-owner:{owner_route}",
                fingerprint_value(
                    {"owner_route": owner_route, "affected_ids": list(affected_ids)}
                ),
            ),
        ]
        projected_inputs.extend(
            (
                f"model-regression:child:{child.model_id}",
                child.receipt.fingerprint,
            )
            for child in mapped_children[owner_route]
        )
        contracts.append(
            ValidationOwnerContract(
                owner_id=owner_route,
                command=command,
                input_patterns=(),
                obligation_ids=affected_ids,
                projected_inputs=tuple(projected_inputs),
                resource_keys=(f"model-revision-owner:{owner_route}",),
                timeout_seconds=60.0,
            )
        )
    return tuple(contracts)


def _assert_exact_aggregate_children(
    receipt: EvidenceReceipt,
    children: Sequence[_MappedModelChild],
    *,
    owner_route: str,
) -> None:
    """Require the aggregate to consume exactly the current mapped leaves."""

    ordered = tuple(sorted(children, key=lambda item: item.receipt.receipt_id))
    expected_requirements = tuple(
        (
            item.receipt.receipt_id,
            item.receipt.subject_id,
            item.receipt.covered_obligations,
            (OWNER_RECEIPT_SCOPE,),
            item.receipt.fingerprint,
        )
        for item in ordered
    )
    actual_requirements = tuple(
        (
            item.receipt_id,
            item.subject_id,
            item.obligation_ids,
            item.eligible_claim_scopes,
            item.expected_receipt_fingerprint,
        )
        for item in receipt.required_child_receipts
    )
    if actual_requirements != expected_requirements:
        raise ModelAuthorityError(
            "native owner aggregate does not require the exact current model "
            f"children: {owner_route}"
        )
    expected_consumed = tuple(
        (item.receipt.receipt_id, item.receipt.fingerprint) for item in ordered
    )
    actual_consumed = tuple(
        (item.receipt_id, item.receipt_fingerprint)
        for item in receipt.consumed_child_receipts
    )
    if actual_consumed != expected_consumed:
        raise ModelAuthorityError(
            "native owner aggregate does not consume the exact current model "
            f"children: {owner_route}"
        )
    metadata_child_ids = tuple(receipt.metadata.get("child_receipt_ids", ()))
    if metadata_child_ids != tuple(item[0] for item in expected_consumed):
        raise ModelAuthorityError(
            "native owner aggregate child metadata is stale or incomplete: "
            f"{owner_route}"
        )


def _assert_parent_artifact_fingerprint(
    parent_path: Path,
    expected_fingerprint: str,
) -> None:
    payload = _read_json(parent_path)
    if (
        not isinstance(payload, Mapping)
        or str(payload.get("parent_receipt_fingerprint", ""))
        != expected_fingerprint
        or fingerprint_value(
            {
                key: value
                for key, value in payload.items()
                if key != "parent_receipt_fingerprint"
            }
        )
        != expected_fingerprint
    ):
        raise ModelAuthorityError("model parent artifact identity changed")


def verify_model_revision_owner_evidence_bundle(
    root: str | Path,
    *,
    model_parent_receipt: str | Path,
    snapshot_id: str,
    bundle: ModelRevisionOwnerEvidenceBundle,
    receipt_root: str | Path | None = None,
    verified_parent: _VerifiedModelParent | None = None,
) -> VerifiedModelRevisionOwnerEvidence:
    """Re-derive bundle currentness instead of trusting caller projections.

    Revision build uses this consumer-side verification even when the bundle was
    just produced locally.  Contracts are reconstructed from the frozen current
    candidate, aggregate receipts must be the exact canonical-store objects, and
    every supplied verification result must equal a fresh
    :func:`verify_evidence_receipt` result over the current contract, proof,
    environment, input snapshot, and exact mapped model children.
    """

    root_path = Path(root).resolve()
    parent_path = Path(model_parent_receipt).resolve()
    receipt_store = (
        Path(receipt_root).resolve()
        if receipt_root is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    if not snapshot_id:
        raise ModelAuthorityError("candidate snapshot id is required")

    frozen = _freeze_revision_inputs(root_path, snapshot_id)
    (
        plans,
        mapped_children,
        parent_fingerprint,
        validation_observation,
    ) = _collect_mapped_model_children(
        root_path,
        receipt_store,
        parent_path,
        frozen,
        verified_parent=verified_parent,
    )
    expected_contracts = _owner_contracts(
        root_path,
        parent_path,
        receipt_store,
        snapshot_id,
        frozen,
        plans,
        mapped_children,
        parent_fingerprint,
    )
    if bundle.contracts != expected_contracts:
        raise ModelAuthorityError(
            "native owner evidence contracts do not match the independently "
            "derived current contracts"
        )
    if len(bundle.receipts) != len(expected_contracts):
        raise ModelAuthorityError(
            "native owner evidence must contain one canonical receipt per current owner"
        )

    currents = {
        contract.owner_id: build_owner_current_from_observation(
            root_path,
            contract,
            all_contracts=expected_contracts,
            observation=validation_observation,
        )
        for contract in expected_contracts
    }
    canonical_receipts: list[EvidenceReceipt] = []
    derived_results: list[ReceiptVerificationResult] = []
    for contract, supplied_receipt, supplied_result in zip(
        expected_contracts,
        bundle.receipts,
        bundle.verification_results,
        strict=True,
    ):
        owner_route = contract.owner_id
        try:
            canonical = load_evidence_receipt(
                supplied_receipt.receipt_id,
                root_path,
                output_directory=receipt_store,
            )
            _assert_owner_receipt_integrity(canonical)
        except (OSError, ValueError) as exc:
            raise ModelAuthorityError(
                "native owner receipt is absent from or invalid in the canonical "
                f"store: {owner_route}: {exc}"
            ) from exc
        if canonical.fingerprint != supplied_receipt.fingerprint:
            raise ModelAuthorityError(
                "supplied native owner receipt differs from the canonical store: "
                f"{owner_route}"
            )
        if canonical.covered_obligations != contract.obligation_ids:
            raise ModelAuthorityError(
                "canonical native owner receipt does not cover its exact current "
                f"contract: {owner_route}"
            )
        owner_children = mapped_children[owner_route]
        _assert_exact_aggregate_children(
            canonical,
            owner_children,
            owner_route=owner_route,
        )
        if str(canonical.metadata.get("owner_identity", "")) != currents[
            owner_route
        ].owner_identity:
            raise ModelAuthorityError(
                "canonical native owner receipt owner identity is stale: "
                f"{owner_route}"
            )
        context = build_child_bound_owner_receipt_context(
            currents[owner_route],
            canonical,
            root_path,
            receipt_store,
            child_receipts=tuple(item.receipt for item in owner_children),
            child_verification_results=tuple(
                item.verification for item in owner_children
            ),
        )
        derived = verify_evidence_receipt(canonical, context)
        if not derived.ok:
            raise ModelAuthorityError(
                "canonical native owner receipt failed independent currentness "
                f"verification: {owner_route}: "
                + ", ".join(item.code for item in derived.findings)
            )
        if supplied_result.to_dict() != derived.to_dict():
            raise ModelAuthorityError(
                "supplied native owner verification does not equal the "
                f"independently derived result: {owner_route}"
            )
        canonical_receipts.append(canonical)
        derived_results.append(derived)

    _assert_frozen_revision_inputs(root_path, snapshot_id, frozen)
    try:
        freshness = assert_validation_owner_observation_fresh(
            validation_observation,
            root_path,
            receipt_store,
            additional_receipt_subject_ids=(
                "validation-owner:model-regression-parent",
                *(
                    f"validation-owner:{contract.owner_id}"
                    for contract in expected_contracts
                ),
            ),
        )
    except ValueError as exc:
        raise ModelAuthorityError(str(exc)) from exc
    _assert_parent_artifact_fingerprint(parent_path, parent_fingerprint)

    final_receipts: list[EvidenceReceipt] = []
    for contract, earlier_receipt in zip(
        expected_contracts,
        canonical_receipts,
        strict=True,
    ):
        try:
            reloaded = load_evidence_receipt(
                earlier_receipt.receipt_id,
                root_path,
                output_directory=receipt_store,
            )
            _assert_owner_receipt_integrity(reloaded)
        except (OSError, ValueError) as exc:
            raise ModelAuthorityError(
                "native owner receipt disappeared from or became invalid in "
                f"the canonical store: {contract.owner_id}: {exc}"
            ) from exc
        if reloaded.fingerprint != earlier_receipt.fingerprint:
            raise ModelAuthorityError(
                "native owner receipt changed in the canonical store during "
                f"independent verification: {contract.owner_id}"
            )
        final_receipts.append(reloaded)

    verified_bundle = ModelRevisionOwnerEvidenceBundle(
        contracts=expected_contracts,
        receipts=tuple(final_receipts),
        verification_results=tuple(derived_results),
    )
    return VerifiedModelRevisionOwnerEvidence(
        bundle=verified_bundle,
        parent_receipt_fingerprint=parent_fingerprint,
        observed_head_fingerprint=frozen.observed_head_fingerprint,
        candidate_snapshot_fingerprint=frozen.candidate_snapshot.fingerprint,
        snapshot_diff_fingerprint=frozen.snapshot_diff.fingerprint,
        affected_closure_fingerprint=frozen.affected_closure.fingerprint,
        validation_observation=validation_observation,
        freshness=freshness,
        mapped_children=mapped_children,
        owner_currents=currents,
        parent_receipt_path=str(parent_path),
        receipt_root=str(receipt_store),
    )


def assert_verified_model_revision_owner_evidence_current(
    root: str | Path,
    verified: VerifiedModelRevisionOwnerEvidence,
) -> ValidationObservationFreshness:
    """Recheck identities for an already verified bundle without rebuilding it."""

    root_path = Path(root).resolve()
    receipt_store = Path(verified.receipt_root).resolve()
    try:
        freshness = assert_validation_owner_observation_fresh(
            verified.validation_observation,
            root_path,
            receipt_store,
            additional_receipt_subject_ids=(
                "validation-owner:model-regression-parent",
                *(
                    receipt.subject_id
                    for receipt in verified.bundle.receipts
                ),
            ),
        )
    except ValueError as exc:
        raise ModelAuthorityError(str(exc)) from exc
    _assert_parent_artifact_fingerprint(
        Path(verified.parent_receipt_path),
        verified.parent_receipt_fingerprint,
    )
    for receipt in verified.bundle.receipts:
        try:
            reloaded = load_evidence_receipt(
                receipt.receipt_id,
                root_path,
                output_directory=receipt_store,
            )
            _assert_owner_receipt_integrity(reloaded)
        except (OSError, ValueError) as exc:
            raise ModelAuthorityError(
                "native owner evidence disappeared before revision publication: "
                f"{receipt.subject_id}: {exc}"
            ) from exc
        if reloaded.fingerprint != receipt.fingerprint:
            raise ModelAuthorityError(
                "native owner evidence changed before revision publication: "
                + receipt.subject_id
            )
    return freshness


def _timestamp_key(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _write_strict_bundle(
    output_path: Path,
    bundle: ModelRevisionOwnerEvidenceBundle,
) -> None:
    encoded = (
        json.dumps(
            bundle.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError:
        if output_path.read_bytes() != encoded:
            raise ModelAuthorityError(
                "native owner evidence output already exists with different content"
            )


def produce_model_revision_owner_evidence(
    root: str | Path,
    *,
    model_parent_receipt: str | Path,
    snapshot_id: str,
    output_path: str | Path,
    receipt_root: str | Path | None = None,
) -> ModelRevisionOwnerEvidenceReport:
    """Create a strict owner-evidence bundle without executing model checks."""

    root_path = Path(root).resolve()
    parent_path = Path(model_parent_receipt).resolve()
    receipt_store = (
        Path(receipt_root).resolve()
        if receipt_root is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    destination = Path(output_path).resolve()
    if not snapshot_id:
        raise ModelAuthorityError("candidate snapshot id is required")
    if destination.is_dir():
        raise ModelAuthorityError("native owner evidence output must be a file")

    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        frozen = _freeze_revision_inputs(root_path, snapshot_id)
        (
            plans,
            mapped_children,
            parent_fingerprint,
            validation_observation,
        ) = _collect_mapped_model_children(
            root_path,
            receipt_store,
            parent_path,
            frozen,
        )
        contracts = _owner_contracts(
            root_path,
            parent_path,
            receipt_store,
            snapshot_id,
            frozen,
            plans,
            mapped_children,
            parent_fingerprint,
        )

        # Rebuild the revision semantics once, then perform one fresh identity
        # comparison over the already verified model children.  No native child
        # verifier is repeated here.
        _assert_frozen_revision_inputs(root_path, snapshot_id, frozen)
        try:
            freshness = assert_validation_owner_observation_fresh(
                validation_observation,
                root_path,
                receipt_store,
                additional_receipt_subject_ids=(
                    "validation-owner:model-regression-parent",
                ),
            )
        except ValueError as exc:
            raise ModelAuthorityError(str(exc)) from exc
        _assert_parent_artifact_fingerprint(parent_path, parent_fingerprint)

        currents = {
            contract.owner_id: build_owner_current_from_observation(
                root_path,
                contract,
                all_contracts=contracts,
                observation=validation_observation,
            )
            for contract in contracts
        }
        receipts: list[EvidenceReceipt] = []
        verifications: list[ReceiptVerificationResult] = []
        for contract in contracts:
            owner_children = mapped_children[contract.owner_id]
            child_receipts = tuple(item.receipt for item in owner_children)
            started_at = min(
                child_receipts,
                key=lambda item: _timestamp_key(item.started_at),
            ).started_at
            finished_at = max(
                child_receipts,
                key=lambda item: _timestamp_key(item.finished_at),
            ).finished_at
            receipt, verification = save_child_bound_owner_receipt_from_observation(
                currents[contract.owner_id],
                tuple(f"model:{item.model_id}" for item in owner_children),
                root_path,
                receipt_store,
                observation=validation_observation,
                freshness=freshness,
                started_at=started_at,
                finished_at=finished_at,
                evidence_context={
                    "observed_head_fingerprint": frozen.observed_head_fingerprint,
                    "base_snapshot_fingerprint": frozen.base_snapshot.fingerprint,
                    "candidate_snapshot_fingerprint": (
                        frozen.candidate_snapshot.fingerprint
                    ),
                    "snapshot_diff_fingerprint": frozen.snapshot_diff.fingerprint,
                    "affected_closure_fingerprint": (
                        frozen.affected_closure.fingerprint
                    ),
                    "parent_receipt_fingerprint": parent_fingerprint,
                    "owner_route": contract.owner_id,
                    "affected_ids": list(contract.obligation_ids),
                    "semantic_model_ids": list(
                        plans[contract.owner_id].semantic_model_ids
                    ),
                    "referenced_changed_model_ids": list(
                        plans[contract.owner_id].referenced_changed_model_ids
                    ),
                    "removed_referenced_model_ids": list(
                        plans[
                            contract.owner_id
                        ].removed_referenced_model_ids
                    ),
                    "required_model_ids": list(
                        plans[contract.owner_id].required_model_ids
                    ),
                },
                claim_boundary=(
                    "One native model-system owner over its exact affected closure "
                    "ids, composed from real current model child receipts. The "
                    "aggregate is not another model execution and cannot replace "
                    "the full model-regression parent."
                ),
            )
            receipts.append(receipt)
            verifications.append(verification)

        bundle = ModelRevisionOwnerEvidenceBundle(
            contracts=contracts,
            receipts=tuple(receipts),
            verification_results=tuple(verifications),
        )
        # Publication is content addressed.  Reload only the newly written
        # aggregates; their child semantics were already verified in the one
        # frozen observation and the final freshness boundary above.
        for contract, receipt in zip(
            bundle.contracts,
            bundle.receipts,
            strict=True,
        ):
            try:
                reloaded = load_evidence_receipt(
                    receipt.receipt_id,
                    root_path,
                    output_directory=receipt_store,
                )
                _assert_owner_receipt_integrity(reloaded)
            except (OSError, ValueError) as exc:
                raise ModelAuthorityError(
                    f"native owner aggregate publication failed: {contract.owner_id}: {exc}"
                ) from exc
            if reloaded.fingerprint != receipt.fingerprint:
                raise ModelAuthorityError(
                    f"native owner aggregate changed after publication: {contract.owner_id}"
                )
        _write_strict_bundle(destination, bundle)

    return ModelRevisionOwnerEvidenceReport(
        root=str(root_path),
        output_path=str(destination),
        parent_receipt_path=str(parent_path),
        parent_receipt_fingerprint=parent_fingerprint,
        observed_head_fingerprint=frozen.observed_head_fingerprint,
        candidate_snapshot_fingerprint=frozen.candidate_snapshot.fingerprint,
        snapshot_diff_fingerprint=frozen.snapshot_diff.fingerprint,
        affected_closure_fingerprint=frozen.affected_closure.fingerprint,
        affected_owner_routes=tuple(item.owner_id for item in bundle.contracts),
        owner_receipt_ids=tuple(item.receipt_id for item in bundle.receipts),
        bundle=bundle,
        initial_observation_fingerprint=(
            validation_observation.observation_fingerprint
        ),
        final_freshness_fingerprint=freshness.final_observation_fingerprint,
        initial_observation_seconds=validation_observation.observation_seconds,
        final_freshness_seconds=freshness.observation_seconds,
    )


__all__ = [
    "MODEL_REVISION_OWNER_EVIDENCE_REPORT_SCHEMA",
    "NATIVE_OWNER_BINDINGS_RELATIVE_PATH",
    "NATIVE_OWNER_BINDINGS_SCHEMA",
    "ModelRevisionOwnerEvidenceBundle",
    "ModelRevisionOwnerEvidenceReport",
    "NativeOwnerModelBinding",
    "NativeOwnerModelEvidencePlan",
    "VerifiedModelRevisionOwnerEvidence",
    "assert_verified_model_revision_owner_evidence_current",
    "produce_model_revision_owner_evidence",
    "verify_model_revision_owner_evidence_bundle",
]
