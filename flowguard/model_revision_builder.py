"""Build one accepted current model revision without activating authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .evidence_receipts import (
    RECEIPT_STATUS_PASS,
    EvidenceReceipt,
    fingerprint_value,
)
from .model_authority import (
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    ModelAuthorityError,
    ModelSystemSnapshot,
)
from .model_authority_store import load_observed_model_system
from .model_regressions import (
    ModelRegressionManifest,
    _model_owner_contract,
    audit_manifest,
    select_entries,
)
from .model_revision_set import (
    ModelRevisionSet,
    RevisionEvidenceRef,
    RevisionRemovalDisposition,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from .model_system_inventory import build_manifest_model_system_snapshot
from .project_manifest import project_manifest_lock
from .source_identity import source_file_fingerprint
from .validation_ownership import (
    OWNER_REUSE_CURRENT,
    plan_validation_owners,
)


MODEL_REVISION_BUILD_REPORT_SCHEMA = "flowguard.model_revision_build_report.v1"
MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA = (
    "flowguard.model_regression_parent_receipt.v1"
)
MODEL_REGRESSION_PARENT_ARTIFACT_TYPE = (
    "flowguard_model_regression_parent_receipt"
)
_PARENT_FIELDS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "claim_scope",
        "tier",
        "status",
        "manifest_sha256",
        "selected_model_ids",
        "skipped_model_ids",
        "children",
        "claim_boundary",
        "parent_receipt_fingerprint",
    }
)
_CHILD_FIELDS = frozenset(
    {"model_id", "receipt_id", "receipt_fingerprint"}
)


@dataclass(frozen=True)
class ModelRevisionBuildReport:
    root: str
    parent_receipt_path: str
    parent_receipt_fingerprint: str
    observed_head_fingerprint: str
    candidate_snapshot_path: str
    candidate_snapshot_fingerprint: str
    revision_set_path: str
    revision_set_fingerprint: str
    revision_set_id: str
    task_id: str
    snapshot_id: str
    affected_owner_routes: tuple[str, ...]
    affected_id_count: int
    status: str = "pass"
    schema: str = MODEL_REVISION_BUILD_REPORT_SCHEMA
    claim_boundary: str = (
        "Generation proves one accepted current-format candidate/revision pair "
        "against the exact supplied full model-regression parent receipt. It "
        "does not execute models, activate authority, update the observed head, "
        "or prove release readiness."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "root": self.root,
            "parent_receipt_path": self.parent_receipt_path,
            "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
            "observed_head_fingerprint": self.observed_head_fingerprint,
            "candidate_snapshot_path": self.candidate_snapshot_path,
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "revision_set_path": self.revision_set_path,
            "revision_set_fingerprint": self.revision_set_fingerprint,
            "revision_set_id": self.revision_set_id,
            "task_id": self.task_id,
            "snapshot_id": self.snapshot_id,
            "affected_owner_routes": list(self.affected_owner_routes),
            "affected_id_count": self.affected_id_count,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class _VerifiedModelParent:
    fingerprint: str
    receipt_id: str
    obligation_ids: tuple[str, ...]
    toolchain_fingerprint: str
    environment_fingerprint: str


def _reject_duplicate_json_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelAuthorityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError) as exc:
        raise ModelAuthorityError(f"cannot load JSON artifact {path}: {exc}") from exc


def load_revision_removal_dispositions(
    path: str | Path,
) -> tuple[RevisionRemovalDisposition, ...]:
    """Load the current typed removal-disposition array with no legacy reader."""

    source = Path(path).resolve()
    payload = _read_json(source)
    if not isinstance(payload, list):
        raise ModelAuthorityError("removal dispositions must be a JSON array")
    return tuple(RevisionRemovalDisposition.from_dict(item) for item in payload)


def _string_array(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ModelAuthorityError(f"{field_name} must be an array of strings")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ModelAuthorityError(f"{field_name} must not contain duplicates")
    return result


def _parent_children(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ModelAuthorityError("model parent children must be an array")
    rows: list[Mapping[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ModelAuthorityError(
                f"model parent child {index} must be an object"
            )
        if set(item) != _CHILD_FIELDS:
            raise ModelAuthorityError(
                "model parent child fields must match the current schema exactly"
            )
        row = {name: str(item[name]) for name in _CHILD_FIELDS}
        if any(not value for value in row.values()):
            raise ModelAuthorityError("model parent child fields must be non-empty")
        rows.append(row)
    model_ids = tuple(row["model_id"] for row in rows)
    if len(model_ids) != len(set(model_ids)):
        raise ModelAuthorityError("model parent children must identify unique models")
    return tuple(rows)


def _aggregate_fingerprint(
    schema: str,
    parent_fingerprint: str,
    rows: Iterable[Mapping[str, Any]],
) -> str:
    return fingerprint_value(
        {
            "schema": schema,
            "parent_receipt_fingerprint": parent_fingerprint,
            "children": list(rows),
        }
    )


def _verify_model_parent_receipt(
    root: Path,
    parent_receipt_path: Path,
    receipt_root: Path,
) -> _VerifiedModelParent:
    payload = _read_json(parent_receipt_path)
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError("model parent receipt must be a JSON object")
    if set(payload) != _PARENT_FIELDS:
        missing = sorted(_PARENT_FIELDS - set(payload))
        unknown = sorted(set(payload) - _PARENT_FIELDS)
        raise ModelAuthorityError(
            "model parent receipt fields do not match the current schema: "
            f"missing={missing}, unknown={unknown}"
        )
    if payload["artifact_type"] != MODEL_REGRESSION_PARENT_ARTIFACT_TYPE:
        raise ModelAuthorityError("artifact is not a model-regression parent receipt")
    if payload["schema_version"] != MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA:
        raise ModelAuthorityError("model parent receipt schema is not current")
    if (
        payload["claim_scope"] != "full"
        or payload["tier"] != "full"
        or payload["status"] != RECEIPT_STATUS_PASS
    ):
        raise ModelAuthorityError(
            "model parent receipt must be terminal pass with full claim scope and tier"
        )
    skipped_ids = _string_array(payload["skipped_model_ids"], "skipped_model_ids")
    if skipped_ids:
        raise ModelAuthorityError("full model parent receipt contains skipped models")

    declared_fingerprint = str(payload["parent_receipt_fingerprint"])
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key != "parent_receipt_fingerprint"
    }
    if fingerprint_value(identity_payload) != declared_fingerprint:
        raise ModelAuthorityError("model parent receipt fingerprint is stale")

    manifest = ModelRegressionManifest.load(root)
    audit = audit_manifest(root, manifest)
    if not audit.ok:
        raise ModelAuthorityError(
            "current model-regression manifest is invalid: "
            + "; ".join(audit.errors)
        )
    if str(payload["manifest_sha256"]) != source_file_fingerprint(manifest.path):
        raise ModelAuthorityError("model parent receipt manifest fingerprint is stale")
    entries = select_entries(manifest, tier="full")
    selected_ids = tuple(entry.model_id for entry in entries)
    if _string_array(payload["selected_model_ids"], "selected_model_ids") != selected_ids:
        raise ModelAuthorityError(
            "model parent selected ids do not equal the current full manifest"
        )
    children = _parent_children(payload["children"])
    children_by_model = {row["model_id"]: row for row in children}
    if tuple(row["model_id"] for row in children) != tuple(sorted(selected_ids)):
        raise ModelAuthorityError(
            "model parent children do not cover the current full manifest exactly"
        )

    contracts = tuple(_model_owner_contract(root, manifest, entry) for entry in entries)
    rows, _currents, reusable = plan_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
    )
    noncurrent = tuple(
        row.owner_id for row in rows if row.disposition != OWNER_REUSE_CURRENT
    )
    if noncurrent:
        raise ModelAuthorityError(
            "model parent child evidence is not exact-current for owners: "
            + ", ".join(noncurrent)
        )

    verified_children: list[tuple[str, EvidenceReceipt]] = []
    obligations: list[str] = []
    for model_id in selected_ids:
        owner_id = f"model:{model_id}"
        receipt = reusable[owner_id]
        declared = children_by_model[model_id]
        if (
            declared["receipt_id"] != receipt.receipt_id
            or declared["receipt_fingerprint"] != receipt.fingerprint
        ):
            raise ModelAuthorityError(
                f"model parent child is not the exact current receipt: {model_id}"
            )
        expected_obligations = (f"model-regression:{model_id}",)
        if (
            receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.claim_scope != "full"
            or receipt.covered_obligations != expected_obligations
            or receipt.skipped_checks
            or receipt.blockers
        ):
            raise ModelAuthorityError(
                f"model parent child is not terminal full exact-obligation pass: {model_id}"
            )
        verified_children.append((model_id, receipt))
        obligations.extend(receipt.covered_obligations)

    toolchain_rows = (
        {
            "model_id": model_id,
            "receipt_fingerprint": receipt.fingerprint,
            "producer_id": receipt.producer_id,
            "producer_version": receipt.producer_version,
            "contract_hash": receipt.contract_hash,
            "check_manifest_hash": receipt.check_manifest_hash,
            "suite_map_hash": receipt.suite_map_hash,
            "command": list(receipt.command),
        }
        for model_id, receipt in verified_children
    )
    environment_rows = (
        {
            "model_id": model_id,
            "receipt_fingerprint": receipt.fingerprint,
            "environment_fingerprint": receipt.environment_fingerprint,
            "environment_metadata": dict(receipt.environment_metadata),
        }
        for model_id, receipt in verified_children
    )
    digest = declared_fingerprint.split(":", 1)[1]
    return _VerifiedModelParent(
        fingerprint=declared_fingerprint,
        receipt_id=f"receipt:model-regression-parent:{digest}",
        obligation_ids=tuple(obligations),
        toolchain_fingerprint=_aggregate_fingerprint(
            "flowguard.model_revision_evidence_toolchain.v1",
            declared_fingerprint,
            toolchain_rows,
        ),
        environment_fingerprint=_aggregate_fingerprint(
            "flowguard.model_revision_evidence_environment.v1",
            declared_fingerprint,
            environment_rows,
        ),
    )


def _content_addressed_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_content_addressed_pair(
    output_root: Path,
    candidate: ModelSystemSnapshot,
    revision: ModelRevisionSet,
) -> tuple[Path, Path]:
    candidate_path = (
        output_root
        / "snapshots"
        / f"{candidate.fingerprint.split(':', 1)[1]}.json"
    )
    revision_path = (
        output_root
        / "revisions"
        / f"{revision.fingerprint.split(':', 1)[1]}.json"
    )
    artifacts = (
        (candidate_path, _content_addressed_bytes(candidate.to_dict())),
        (revision_path, _content_addressed_bytes(revision.to_dict())),
    )
    for path, encoded in artifacts:
        if path.exists() and path.read_bytes() != encoded:
            raise ModelAuthorityError(
                f"content-addressed model revision path contains different bytes: {path}"
            )
    temporary_paths: list[Path] = []
    created_paths: list[Path] = []
    try:
        for path, encoded in artifacts:
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            if temporary.exists():
                raise ModelAuthorityError(
                    f"model revision temporary path already exists: {temporary}"
                )
            temporary.write_bytes(encoded)
            temporary_paths.append(temporary)
        for path, _encoded in artifacts:
            temporary = path.with_suffix(".json.tmp")
            if temporary in temporary_paths:
                temporary.replace(path)
                created_paths.append(path)
    except Exception:
        for path in reversed(created_paths):
            if path.exists():
                path.unlink()
        raise
    finally:
        for temporary in temporary_paths:
            if temporary.exists():
                temporary.unlink()
    return candidate_path, revision_path


def build_current_model_revision(
    root: str | Path,
    *,
    model_parent_receipt: str | Path,
    revision_set_id: str,
    task_id: str,
    snapshot_id: str,
    receipt_root: str | Path | None = None,
    output_root: str | Path | None = None,
    removal_dispositions: Iterable[RevisionRemovalDisposition] = (),
    decision_reason: str = (
        "The exact-current terminal-pass full model-regression parent receipt "
        "covers every affected native owner."
    ),
) -> ModelRevisionBuildReport:
    """Build and persist one accepted revision while leaving authority untouched."""

    root_path = Path(root).resolve()
    parent_path = Path(model_parent_receipt).resolve()
    receipt_store = (
        Path(receipt_root).resolve()
        if receipt_root is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    destination = (
        Path(output_root).resolve()
        if output_root is not None
        else root_path / ".flowguard" / "model-mesh"
    )
    dispositions = tuple(removal_dispositions)
    if any(not isinstance(item, RevisionRemovalDisposition) for item in dispositions):
        raise ModelAuthorityError(
            "removal dispositions must be current typed RevisionRemovalDisposition records"
        )

    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        head, base = load_observed_model_system(root_path)
        verified_parent = _verify_model_parent_receipt(
            root_path,
            parent_path,
            receipt_store,
        )
        candidate = build_manifest_model_system_snapshot(
            root_path,
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
        ids_by_owner: dict[str, list[str]] = {}
        for affected_id, owner_route in closure.owner_bindings:
            ids_by_owner.setdefault(owner_route, []).append(affected_id)
        required = tuple(
            RevisionEvidenceRef(
                receipt_id=verified_parent.receipt_id,
                receipt_fingerprint=verified_parent.fingerprint,
                owner_route=owner_route,
                subject_fingerprint=candidate.fingerprint,
                obligation_ids=verified_parent.obligation_ids,
                affected_closure_fingerprint=closure.fingerprint,
                covered_affected_ids=tuple(ids_by_owner[owner_route]),
                candidate_snapshot_fingerprint=candidate.fingerprint,
                toolchain_fingerprint=verified_parent.toolchain_fingerprint,
                environment_fingerprint=(
                    verified_parent.environment_fingerprint
                ),
                status=REVISION_EVIDENCE_REQUIRED,
                current=True,
                eligible=True,
            )
            for owner_route in sorted(ids_by_owner)
        )
        proposed = ModelRevisionSet(
            revision_set_id=revision_set_id,
            task_id=task_id,
            expected_head_fingerprint=head.fingerprint,
            base_snapshot_fingerprint=base.fingerprint,
            candidate_snapshot_fingerprint=candidate.fingerprint,
            members=diff.members,
            affected_closure_ids=closure.affected_ids,
            affected_closure_fingerprint=closure.fingerprint,
            affected_edge_ids=closure.edge_ids,
            affected_owner_bindings=closure.owner_bindings,
            snapshot_diff_fingerprint=diff.fingerprint,
            changed_root_ids=diff.changed_root_ids,
            changed_relation_ids=diff.changed_relation_ids,
            changed_source_surface_ids=diff.changed_source_surface_ids,
            changed_commitment_ids=diff.changed_commitment_ids,
            changed_field_ids=diff.changed_field_ids,
            changed_side_effect_ids=diff.changed_side_effect_ids,
            changed_contract_ids=diff.changed_contract_ids,
            changed_test_ids=diff.changed_test_ids,
            changed_system_property_ids=diff.changed_system_property_ids,
            changed_coverage_ids=diff.changed_coverage_ids,
            changed_gap_ids=diff.changed_gap_ids,
            changed_owner_artifact_ids=diff.changed_owner_artifact_ids,
            added_ids=diff.added_ids,
            removed_ids=diff.removed_ids,
            fingerprint_changed_ids=diff.fingerprint_changed_ids,
            removal_dispositions=dispositions,
            required_evidence_refs=required,
        )
        accepted = proposed.accept(
            (
                replace(item, status=REVISION_EVIDENCE_PASS)
                for item in required
            ),
            reason=decision_reason,
        )
        final_head, _final_base = load_observed_model_system(root_path)
        if final_head.fingerprint != head.fingerprint:
            raise ModelAuthorityError(
                "observed authority head changed during revision generation"
            )
        final_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        if final_candidate.identity_payload() != candidate.identity_payload():
            raise ModelAuthorityError(
                "live model inputs changed during revision generation"
            )
        candidate_path, revision_path = _write_content_addressed_pair(
            destination,
            candidate,
            accepted,
        )

    return ModelRevisionBuildReport(
        root=str(root_path),
        parent_receipt_path=str(parent_path),
        parent_receipt_fingerprint=verified_parent.fingerprint,
        observed_head_fingerprint=head.fingerprint,
        candidate_snapshot_path=str(candidate_path),
        candidate_snapshot_fingerprint=candidate.fingerprint,
        revision_set_path=str(revision_path),
        revision_set_fingerprint=accepted.fingerprint,
        revision_set_id=accepted.revision_set_id,
        task_id=accepted.task_id,
        snapshot_id=candidate.snapshot_id,
        affected_owner_routes=tuple(sorted(ids_by_owner)),
        affected_id_count=len(closure.affected_ids),
    )


__all__ = [
    "MODEL_REVISION_BUILD_REPORT_SCHEMA",
    "ModelRevisionBuildReport",
    "build_current_model_revision",
    "load_revision_removal_dispositions",
]
