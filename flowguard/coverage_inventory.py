"""Independent expected coverage inventory for FlowGuard exact-set review.

The inventory is derived from native WorkContext, UI, and field owners before
Behavior Commitment Ledger dispositions are considered. This prevents a
caller-selected ledger subset from proving its own completeness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .behavior_commitment import (
    BCL_DISPOSITION_DELEGATED,
    BCL_DISPOSITION_MODELED,
    BCL_DISPOSITION_SCOPED,
    BCL_SOURCE_AUTHORITY_OBSERVED,
    BCL_SOURCE_AUTHORITY_SUPPORTING,
    BCL_SOURCE_FIELD,
    BCL_SOURCE_WORK_CONTEXT,
    BehaviorSourceSurface,
)
from .export import to_jsonable


EXPECTED_COVERAGE_INVENTORY_SCHEMA = "flowguard.expected_coverage_inventory.v1"
EXPECTED_SOURCE_UI = "ui"
EXPECTED_SOURCE_FIELD = BCL_SOURCE_FIELD


def _wire_hash(value: Any) -> str:
    canonical = json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(item) for item in values if str(item))


@dataclass(frozen=True)
class ExpectedCoverageItem:
    item_id: str
    source_kind: str
    source_role: str
    source_system_id: str
    native_artifact_id: str
    native_owner_id: str
    content_ref: str
    content_fingerprint: str
    semantics_fingerprint: str
    discovery_evidence_ids: tuple[str, ...] = ()
    recommended_disposition: str = BCL_DISPOSITION_MODELED
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "item_id",
            "source_kind",
            "source_role",
            "source_system_id",
            "native_artifact_id",
            "native_owner_id",
            "content_ref",
            "content_fingerprint",
            "semantics_fingerprint",
            "recommended_disposition",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(
            self,
            "discovery_evidence_ids",
            _tuple(self.discovery_evidence_ids),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source_kind": self.source_kind,
            "source_role": self.source_role,
            "source_system_id": self.source_system_id,
            "native_artifact_id": self.native_artifact_id,
            "native_owner_id": self.native_owner_id,
            "content_ref": self.content_ref,
            "content_fingerprint": self.content_fingerprint,
            "semantics_fingerprint": self.semantics_fingerprint,
            "discovery_evidence_ids": list(self.discovery_evidence_ids),
            "recommended_disposition": self.recommended_disposition,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ExpectedCoverageInventory:
    inventory_id: str
    boundary: str
    revision: str
    items: tuple[ExpectedCoverageItem, ...]
    discovery_evidence_ids: tuple[str, ...]
    inventory_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "inventory_id", str(self.inventory_id))
        object.__setattr__(self, "boundary", str(self.boundary))
        object.__setattr__(self, "revision", str(self.revision))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(
            self,
            "discovery_evidence_ids",
            _tuple(self.discovery_evidence_ids),
        )
        expected = _wire_hash(self.identity_payload())
        fingerprint = str(self.inventory_fingerprint or expected)
        object.__setattr__(self, "inventory_fingerprint", fingerprint)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": EXPECTED_COVERAGE_INVENTORY_SCHEMA,
            "inventory_id": self.inventory_id,
            "boundary": self.boundary,
            "revision": self.revision,
            "items": [
                item.to_dict()
                for item in sorted(self.items, key=lambda row: row.item_id)
            ],
            "discovery_evidence_ids": list(self.discovery_evidence_ids),
        }

    def item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_expected_coverage_inventory",
            **self.identity_payload(),
            "inventory_fingerprint": self.inventory_fingerprint,
        }


@dataclass(frozen=True)
class ExpectedCoverageFinding:
    code: str
    message: str
    item_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "item_id": self.item_id,
        }


@dataclass(frozen=True)
class ExpectedCoverageReview:
    inventory: ExpectedCoverageInventory
    findings: tuple[ExpectedCoverageFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": "pass" if self.ok else "blocked",
            "inventory": self.inventory.to_dict(),
            "findings": [item.to_dict() for item in self.findings],
        }


def build_expected_coverage_inventory(
    inventory_id: str,
    *,
    boundary: str,
    revision: str,
    discovery_evidence_ids: Sequence[str],
    work_contexts: Sequence[Any] = (),
    ui_inventories: Sequence[Any] = (),
    field_plans: Sequence[Any] = (),
    additional_items: Sequence[
        ExpectedCoverageItem | Mapping[str, Any]
    ] = (),
) -> ExpectedCoverageInventory:
    """Derive one stable expected set from native owner inventories."""

    items: list[ExpectedCoverageItem] = []
    evidence_ids = _tuple(discovery_evidence_ids)

    for context in work_contexts:
        for artifact in context.artifacts:
            item_id = f"work-context:{context.context_id}:{artifact.artifact_id}"
            items.append(
                ExpectedCoverageItem(
                    item_id=item_id,
                    source_kind=BCL_SOURCE_WORK_CONTEXT,
                    source_role=(
                        "normative"
                        if context.subject_lane == "normative_target"
                        else "observed"
                        if context.subject_lane == "observed_implementation"
                        else "supporting"
                    ),
                    source_system_id=context.adapter_id,
                    native_artifact_id=artifact.artifact_id,
                    native_owner_id=context.native_owner_id,
                    content_ref=artifact.source_ref,
                    content_fingerprint=artifact.content_fingerprint,
                    semantics_fingerprint=_wire_hash(
                        {
                            "artifact_role": artifact.artifact_role,
                            "behavior_source_surface_ids": list(
                                context.behavior_source_surface_ids
                            ),
                        }
                    ),
                    discovery_evidence_ids=(
                        context.context_fingerprint,
                        *evidence_ids,
                    ),
                    recommended_disposition=BCL_DISPOSITION_MODELED,
                    metadata={
                        "artifact_role": artifact.artifact_role,
                        "context_id": context.context_id,
                        "subject_lane": context.subject_lane,
                    },
                )
            )

    for inventory in ui_inventories:
        for item in inventory.items:
            payload = item.to_dict()
            items.append(
                ExpectedCoverageItem(
                    item_id=f"ui:{inventory.inventory_id}:{item.item_id}",
                    source_kind=EXPECTED_SOURCE_UI,
                    source_role=BCL_SOURCE_AUTHORITY_OBSERVED,
                    source_system_id=inventory.inventory_id,
                    native_artifact_id=item.item_id,
                    native_owner_id=(
                        inventory.source_interaction_model_id
                        or inventory.source_visible_surface_id
                        or inventory.inventory_id
                    ),
                    content_ref=item.evidence_ref,
                    content_fingerprint=(
                        item.content_fingerprint or _wire_hash(payload)
                    ),
                    semantics_fingerprint=_wire_hash(
                        {
                            "item_kind": item.item_kind,
                            "state_id": item.state_id,
                            "mapped_control_id": item.mapped_control_id,
                            "mapped_display_id": item.mapped_display_id,
                            "mapped_visible_item_id": item.mapped_visible_item_id,
                            "observed_value": item.observed_value,
                        }
                    ),
                    discovery_evidence_ids=(
                        inventory.evidence_ref,
                        *getattr(inventory, "discovery_evidence_ids", ()),
                        *evidence_ids,
                    ),
                    recommended_disposition=BCL_DISPOSITION_DELEGATED,
                    metadata={
                        "inventory_revision": inventory.current_revision,
                        "item_kind": item.item_kind,
                    },
                )
            )
        for blindspot in inventory.scoped_blindspots:
            items.append(
                ExpectedCoverageItem(
                    item_id=(
                        f"ui:{inventory.inventory_id}:blindspot:"
                        f"{blindspot.blindspot_id}"
                    ),
                    source_kind=EXPECTED_SOURCE_UI,
                    source_role=BCL_SOURCE_AUTHORITY_SUPPORTING,
                    source_system_id=inventory.inventory_id,
                    native_artifact_id=blindspot.blindspot_id,
                    native_owner_id=inventory.inventory_id,
                    content_ref=inventory.evidence_ref,
                    content_fingerprint=_wire_hash(blindspot.to_dict()),
                    semantics_fingerprint=_wire_hash(
                        {
                            "blindspot_id": blindspot.blindspot_id,
                            "reason": blindspot.reason,
                        }
                    ),
                    discovery_evidence_ids=(
                        inventory.evidence_ref,
                        *getattr(inventory, "discovery_evidence_ids", ()),
                        *evidence_ids,
                    ),
                    recommended_disposition=BCL_DISPOSITION_SCOPED,
                )
            )

    for plan in field_plans:
        rows = {row.field_id: row for row in plan.fields}
        for field_id in plan.discovered_field_ids:
            row = rows.get(field_id)
            payload = (
                row.to_dict()
                if row is not None
                else {"field_id": field_id, "missing_row": True}
            )
            items.append(
                ExpectedCoverageItem(
                    item_id=f"field:{plan.mesh_id}:{field_id}",
                    source_kind=EXPECTED_SOURCE_FIELD,
                    source_role=BCL_SOURCE_AUTHORITY_SUPPORTING,
                    source_system_id=plan.mesh_id,
                    native_artifact_id=field_id,
                    native_owner_id=plan.mesh_id,
                    content_ref=";".join(
                        row.locations if row is not None else ()
                    ),
                    content_fingerprint=_wire_hash(payload),
                    semantics_fingerprint=_wire_hash(
                        {
                            "owner_id": getattr(row, "owner_id", ""),
                            "role": getattr(row, "role", ""),
                            "lifecycle": getattr(row, "lifecycle", ""),
                            "behavior_impacts": list(
                                getattr(row, "behavior_impacts", ())
                            ),
                            "readers": list(getattr(row, "reader_ids", ())),
                            "writers": list(getattr(row, "writer_ids", ())),
                            "default_semantics": getattr(
                                row, "default_semantics", ""
                            ),
                            "absence_semantics": getattr(
                                row, "absence_semantics", ""
                            ),
                            "serialization_semantics": getattr(
                                row, "serialization_semantics", ""
                            ),
                            "privacy_classification": getattr(
                                row, "privacy_classification", ""
                            ),
                            "coverage_disposition": getattr(
                                row, "coverage_disposition", ""
                            ),
                            "delegated_owner_id": getattr(
                                row, "delegated_owner_id", ""
                            ),
                            "projection": (
                                row.projection.to_dict()
                                if row is not None
                                and row.projection is not None
                                else None
                            ),
                        }
                    ),
                    discovery_evidence_ids=(
                        *getattr(plan, "discovery_evidence_ids", ()),
                        *getattr(row, "coverage_evidence_refs", ()),
                        *getattr(row, "disposition_evidence_refs", ()),
                        *evidence_ids,
                    ),
                    recommended_disposition=BCL_DISPOSITION_DELEGATED,
                    metadata={
                        "field_row_present": row is not None,
                        "behavior_bearing": bool(
                            getattr(row, "behavior_bearing", False)
                        ),
                    },
                )
            )

    for item in additional_items:
        items.append(
            item
            if isinstance(item, ExpectedCoverageItem)
            else ExpectedCoverageItem(**dict(item))
        )
    return ExpectedCoverageInventory(
        inventory_id=inventory_id,
        boundary=boundary,
        revision=revision,
        items=tuple(items),
        discovery_evidence_ids=evidence_ids,
    )


def review_expected_coverage_inventory(
    inventory: ExpectedCoverageInventory,
) -> ExpectedCoverageReview:
    findings: list[ExpectedCoverageFinding] = []
    if not inventory.inventory_id or not inventory.boundary or not inventory.revision:
        findings.append(
            ExpectedCoverageFinding(
                "expected_inventory_identity_missing",
                "expected inventory requires id, boundary, and revision",
            )
        )
    if not inventory.discovery_evidence_ids:
        findings.append(
            ExpectedCoverageFinding(
                "expected_inventory_discovery_evidence_missing",
                "expected inventory requires current native discovery evidence",
            )
        )
    if not inventory.items:
        findings.append(
            ExpectedCoverageFinding(
                "expected_inventory_empty",
                "declared non-empty coverage boundary discovered no items",
            )
        )
    seen: set[str] = set()
    for item in inventory.items:
        if not item.item_id or item.item_id in seen:
            findings.append(
                ExpectedCoverageFinding(
                    "expected_inventory_item_identity_invalid",
                    "expected item ids must be non-empty and unique",
                    item.item_id,
                )
            )
        seen.add(item.item_id)
        required = (
            item.source_kind,
            item.source_role,
            item.source_system_id,
            item.native_artifact_id,
            item.native_owner_id,
            item.content_fingerprint,
            item.semantics_fingerprint,
        )
        if not all(required):
            findings.append(
                ExpectedCoverageFinding(
                    "expected_inventory_item_incomplete",
                    "expected item lacks source, native owner, content, or semantic identity",
                    item.item_id,
                )
            )
        if not item.discovery_evidence_ids:
            findings.append(
                ExpectedCoverageFinding(
                    "expected_inventory_item_evidence_missing",
                    "expected item lacks native discovery evidence",
                    item.item_id,
                )
            )
    expected_fingerprint = _wire_hash(inventory.identity_payload())
    if inventory.inventory_fingerprint != expected_fingerprint:
        findings.append(
            ExpectedCoverageFinding(
                "expected_inventory_fingerprint_stale",
                "expected inventory fingerprint does not match current items",
            )
        )
    return ExpectedCoverageReview(inventory, tuple(findings))


def project_expected_item_to_behavior_surface(
    item: ExpectedCoverageItem,
    *,
    inventory_revision: str,
    coverage_disposition: str,
    commitment_id: str = "",
    business_intent_id: str = "",
    delegated_owner_inventory_id: str = "",
    delegation_relation_type: str = "",
    native_evidence_ids: Sequence[str] = (),
    scope_owner: str = "",
    scoped_out_reason: str = "",
    validation_boundary: str = "",
    rationale: str = "",
) -> BehaviorSourceSurface:
    """Materialize one explicit disposition without guessing semantic ownership."""

    is_scoped = coverage_disposition == BCL_DISPOSITION_SCOPED
    return BehaviorSourceSurface(
        surface_id=item.item_id,
        surface_kind=item.source_kind,
        label=item.native_artifact_id,
        source_ref=item.content_ref,
        source_system_id=item.source_system_id,
        native_artifact_id=item.native_artifact_id,
        content_fingerprint=item.content_fingerprint,
        inventory_revision=inventory_revision,
        discovery_evidence_ids=item.discovery_evidence_ids,
        source_authority_role=item.source_role,
        declared_semantics_fingerprint=item.semantics_fingerprint,
        coverage_disposition=coverage_disposition,
        delegated_owner_inventory_id=delegated_owner_inventory_id,
        delegation_relation_type=delegation_relation_type,
        native_evidence_ids=_tuple(native_evidence_ids),
        commitment_ids=(commitment_id,) if commitment_id else (),
        business_intent_ids=(
            (business_intent_id,) if business_intent_id else ()
        ),
        freshness_state="current",
        in_scope=not is_scoped,
        scoped_out_reason=scoped_out_reason,
        owner=scope_owner,
        validation_boundary=validation_boundary,
        rationale=rationale,
        metadata={
            "native_owner_id": item.native_owner_id,
            **dict(item.metadata),
        },
    )


__all__ = [
    "EXPECTED_COVERAGE_INVENTORY_SCHEMA",
    "EXPECTED_SOURCE_FIELD",
    "EXPECTED_SOURCE_UI",
    "ExpectedCoverageFinding",
    "ExpectedCoverageInventory",
    "ExpectedCoverageItem",
    "ExpectedCoverageReview",
    "build_expected_coverage_inventory",
    "project_expected_item_to_behavior_surface",
    "review_expected_coverage_inventory",
]
