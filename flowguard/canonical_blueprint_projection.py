"""Canonical provider-neutral target-system blueprint projection.

This module adds no blueprint envelope, writer, or qualification authority.
It mechanically projects the exact descriptor, frozen provider evidence,
native report set, and compiler-owned qualification report into the existing
content-addressed ``CanonicalBlueprintProjection`` / ``BlueprintShard`` format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence_receipts import fingerprint_value
from .implementation_blueprint import (
    BLUEPRINT_SCHEMA_VERSION,
    BlueprintFinding,
    BlueprintValidationError,
    CanonicalBlueprintMaterialization,
    CanonicalBlueprintProjection,
    _make_shard,
    load_canonical_blueprint_projection,
    verify_blueprint_projection,
)
from .target_native_qualification import (
    TargetBlueprintNativeReportSet,
    qualify_target_system_from_native_reports,
)
from .target_system_blueprint import (
    FrozenTargetSystemEvidence,
    TargetSystemBlueprintReport,
    TargetSystemDescriptor,
)


TARGET_SYSTEM_BLUEPRINT_PROJECTION_KINDS = (
    "identity",
    "native_reports",
    "provider_evidence",
    "readiness",
)

TARGET_SYSTEM_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY = (
    "the exact descriptor, frozen provider evidence and layer plan, complete "
    "native report set, and compiler-owned qualification are rebound to the "
    "materialized target projection; readiness remains exactly the compiler result"
)


@dataclass(frozen=True)
class TargetSystemBlueprintMaterializationVerification:
    ok: bool
    status: str
    model_readiness_status: str
    materialization: CanonicalBlueprintMaterialization
    findings: tuple[BlueprintFinding, ...] = ()
    claim_boundary: str = TARGET_SYSTEM_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "materialization_ok": self.ok,
            "materialization_status": self.status,
            "model_readiness_status": self.model_readiness_status,
            "projection_fingerprint": self.materialization.projection.fingerprint,
            "tree_fingerprint": self.materialization.tree_fingerprint,
            "generic_claim_boundary": self.materialization.claim_boundary,
            "claim_boundary": self.claim_boundary,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def _exact_member_ids(
    descriptor: TargetSystemDescriptor,
    frozen_evidence: FrozenTargetSystemEvidence,
    native_report_set: TargetBlueprintNativeReportSet,
    qualification: TargetSystemBlueprintReport,
) -> tuple[str, ...]:
    values = {
        descriptor.target_system_id,
        descriptor.subject_revision,
        frozen_evidence.evidence_id,
        frozen_evidence.layer_plan.plan_id,
        frozen_evidence.provider_registry.registry_id,
        frozen_evidence.snapshot.snapshot_id,
        native_report_set.observed_model.model_id,
        native_report_set.authority_model.model_id,
        *(row.provider_id for row in frozen_evidence.provider_results),
        *(row.member_id for row in native_report_set.members),
        *(
            f"{row.evidence_role}:{row.member_kind}:{row.member_id}"
            for row in native_report_set.members
        ),
        *(row.receipt_id for row in native_report_set.execution_receipts),
        *(row.layer for row in qualification.layers),
        *(row.gap_id for row in qualification.gaps),
    }
    return tuple(sorted(value for value in values if value))


def _blueprint_source_fingerprint(
    descriptor: TargetSystemDescriptor,
    frozen_evidence: FrozenTargetSystemEvidence,
    native_report_set: TargetBlueprintNativeReportSet,
    qualification: TargetSystemBlueprintReport,
) -> str:
    return fingerprint_value(
        {
            "schema_version": BLUEPRINT_SCHEMA_VERSION,
            "projection_kind": "target_system_blueprint",
            "descriptor_fingerprint": descriptor.fingerprint,
            "frozen_evidence_fingerprint": frozen_evidence.fingerprint,
            "native_report_set_fingerprint": native_report_set.fingerprint,
            "qualification_fingerprint": qualification.fingerprint,
        }
    )


def canonical_target_system_blueprint_projection(
    descriptor: TargetSystemDescriptor,
    frozen_evidence: FrozenTargetSystemEvidence,
    native_report_set: TargetBlueprintNativeReportSet,
    qualification: TargetSystemBlueprintReport,
) -> CanonicalBlueprintProjection:
    """Project one already-qualified target through the sole projection kernel.

    The native qualifier is rerun only as a deterministic integrity comparison;
    it executes no provider or validation owner and writes no artifact.  This
    prevents a report derived from different native inputs from being attached
    to an otherwise well-formed export.
    """

    if not isinstance(descriptor, TargetSystemDescriptor):
        raise BlueprintValidationError(
            "canonical target export requires a typed target descriptor"
        )
    if not isinstance(frozen_evidence, FrozenTargetSystemEvidence):
        raise BlueprintValidationError(
            "canonical target export requires typed frozen provider evidence"
        )
    if not isinstance(native_report_set, TargetBlueprintNativeReportSet):
        raise BlueprintValidationError(
            "canonical target export requires a typed native report set"
        )
    if not isinstance(qualification, TargetSystemBlueprintReport):
        raise BlueprintValidationError(
            "canonical target export requires the compiler-owned qualification"
        )
    if qualification.scope != "whole":
        raise BlueprintValidationError(
            "canonical target export requires whole-target qualification"
        )

    expected = qualify_target_system_from_native_reports(
        descriptor,
        frozen_evidence,
        native_report_set,
    )
    if (
        expected.fingerprint != qualification.fingerprint
        or expected.to_dict() != qualification.to_dict()
    ):
        raise BlueprintValidationError(
            "target qualification differs from the exact native export inputs"
        )

    blueprint_fingerprint = _blueprint_source_fingerprint(
        descriptor,
        frozen_evidence,
        native_report_set,
        qualification,
    )
    member_ids = _exact_member_ids(
        descriptor,
        frozen_evidence,
        native_report_set,
        qualification,
    )
    identity: dict[str, Any] = {
        "blueprint_id": (
            f"target-system-blueprint:{descriptor.target_system_id}:"
            f"{descriptor.subject_revision}"
        ),
        "projection_kind": "target_system_blueprint",
        "blueprint_fingerprint": blueprint_fingerprint,
        "target_system_id": descriptor.target_system_id,
        "target_kind": descriptor.target_kind,
        "target_profile": descriptor.target_profile,
        "subject_revision": descriptor.subject_revision,
        "descriptor_fingerprint": descriptor.fingerprint,
        "frozen_evidence_fingerprint": frozen_evidence.fingerprint,
        "native_report_set_fingerprint": native_report_set.fingerprint,
        "qualification_fingerprint": qualification.fingerprint,
        "member_ids": list(member_ids),
        "descriptor": descriptor.to_dict(),
    }
    provider_evidence: dict[str, Any] = {
        "evidence_id": frozen_evidence.evidence_id,
        "frozen_evidence_fingerprint": frozen_evidence.fingerprint,
        "target_profile": frozen_evidence.layer_plan.target_profile,
        "layer_plan_id": frozen_evidence.layer_plan.plan_id,
        "layer_plan_fingerprint": frozen_evidence.layer_plan.fingerprint,
        "provider_registry_fingerprint": (
            frozen_evidence.provider_registry.fingerprint
        ),
        "snapshot_fingerprint": frozen_evidence.snapshot.fingerprint,
        "member_ids": [
            frozen_evidence.evidence_id,
            frozen_evidence.layer_plan.plan_id,
            frozen_evidence.provider_registry.registry_id,
            frozen_evidence.snapshot.snapshot_id,
            *(row.provider_id for row in frozen_evidence.provider_results),
        ],
        "frozen_evidence": frozen_evidence.to_dict(),
    }
    native_reports: dict[str, Any] = {
        "report_id": (
            "target-native-report-set:"
            + native_report_set.fingerprint.removeprefix("sha256:")
        ),
        "native_report_set_fingerprint": native_report_set.fingerprint,
        "observed_model_fingerprint": native_report_set.observed_model.fingerprint,
        "authority_model_fingerprint": native_report_set.authority_model.fingerprint,
        "member_ids": [
            *(row.member_id for row in native_report_set.members),
            *(
                f"{row.evidence_role}:{row.member_kind}:{row.member_id}"
                for row in native_report_set.members
            ),
            *(row.receipt_id for row in native_report_set.execution_receipts),
        ],
        "native_report_set": native_report_set.to_dict(),
    }
    readiness: dict[str, Any] = {
        "readiness_kind": "target_system",
        "report_id": (
            "target-system-qualification:"
            + qualification.fingerprint.removeprefix("sha256:")
        ),
        "qualification_fingerprint": qualification.fingerprint,
        "readiness_fingerprint": qualification.readiness_ledger.fingerprint,
        "model_readiness_status": qualification.status,
        "deepest_proven_layer": qualification.deepest_proven_layer,
        "gap_count": qualification.readiness_ledger.gap_count,
        "member_ids": [
            *(row.layer for row in qualification.layers),
            *(row.gap_id for row in qualification.gaps),
        ],
        "qualification": qualification.to_dict(),
        "readiness": qualification.readiness_ledger.to_dict(),
    }
    shards = (
        _make_shard("identity", (identity,)),
        _make_shard("provider_evidence", (provider_evidence,)),
        _make_shard("native_reports", (native_reports,)),
        _make_shard("readiness", (readiness,)),
    )
    if tuple(sorted(row.kind for row in shards)) != tuple(
        sorted(TARGET_SYSTEM_BLUEPRINT_PROJECTION_KINDS)
    ):
        raise BlueprintValidationError(
            "canonical target projection kinds are not exact-current"
        )
    projection = CanonicalBlueprintProjection(
        blueprint_fingerprint=blueprint_fingerprint,
        shards=shards,
        regenerated_shard_ids=tuple(row.shard_id for row in shards),
        affected_member_ids=member_ids,
    )
    verification = verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=blueprint_fingerprint,
        expected_projection_fingerprint=projection.fingerprint,
    )
    if not verification.ok:
        raise BlueprintValidationError(
            "; ".join(row.message for row in verification.findings)
        )
    return projection


def verify_materialized_target_system_blueprint_projection(
    output_root: str | Path,
    descriptor: TargetSystemDescriptor,
    frozen_evidence: FrozenTargetSystemEvidence,
    native_report_set: TargetBlueprintNativeReportSet,
    qualification: TargetSystemBlueprintReport,
) -> TargetSystemBlueprintMaterializationVerification:
    """Rebind a generic disk projection to the exact compiler-owned target inputs."""

    expected = canonical_target_system_blueprint_projection(
        descriptor,
        frozen_evidence,
        native_report_set,
        qualification,
    )
    materialization = load_canonical_blueprint_projection(output_root)
    actual = materialization.projection
    findings: list[BlueprintFinding] = []
    if actual.blueprint_fingerprint != expected.blueprint_fingerprint:
        findings.append(
            BlueprintFinding(
                "target_projection_blueprint_rebind_mismatch",
                "Materialized blueprint identity is not derived from the exact target inputs.",
                severity="blocked",
            )
        )
    if actual.fingerprint != expected.fingerprint:
        findings.append(
            BlueprintFinding(
                "target_projection_manifest_rebind_mismatch",
                "Materialized manifest and shards do not match the exact target projection.",
                severity="blocked",
            )
        )
    actual_by_kind = {shard.kind: shard for shard in actual.shards}
    expected_by_kind = {shard.kind: shard for shard in expected.shards}
    if tuple(sorted(actual_by_kind)) != tuple(
        sorted(TARGET_SYSTEM_BLUEPRINT_PROJECTION_KINDS)
    ):
        findings.append(
            BlueprintFinding(
                "target_projection_kind_set_mismatch",
                "Materialized target projection does not have the exact current shard set.",
                tuple(sorted(actual_by_kind)),
                "blocked",
            )
        )
    for kind, expected_shard in sorted(expected_by_kind.items()):
        actual_shard = actual_by_kind.get(kind)
        if actual_shard is None or actual_shard.to_dict() != expected_shard.to_dict():
            findings.append(
                BlueprintFinding(
                    "target_projection_shard_rebind_mismatch",
                    "Materialized target shard is not a function of the exact compiler inputs.",
                    (kind,),
                    "blocked",
                )
            )
    return TargetSystemBlueprintMaterializationVerification(
        ok=not findings,
        status="complete" if not findings else "blocked",
        model_readiness_status=qualification.status,
        materialization=materialization,
        findings=tuple(findings),
    )


__all__ = [
    "TARGET_SYSTEM_BLUEPRINT_MATERIALIZATION_CLAIM_BOUNDARY",
    "TARGET_SYSTEM_BLUEPRINT_PROJECTION_KINDS",
    "TargetSystemBlueprintMaterializationVerification",
    "canonical_target_system_blueprint_projection",
    "verify_materialized_target_system_blueprint_projection",
]
