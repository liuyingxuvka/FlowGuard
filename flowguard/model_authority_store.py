"""Durable project model authority, pointer-last activation, and audit."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tomllib
from typing import Any, Iterable, Mapping

from .model_authority import (
    LIFECYCLE_ACTIVE,
    ROLLBACK_RESULT_FORWARD_REPAIR,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    ModelActivationReceipt,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackReceipt,
    ModelSystemSnapshot,
    canonical_fingerprint,
    load_model_system_snapshot,
    validate_activation_plan,
    validate_operational_rollback,
    write_content_addressed_snapshot,
)
from .project_manifest import (
    ProjectManifestError,
    project_manifest_lock,
    read_manifest_text,
    replace_project_manifest_locked,
)


MODEL_AUTHORITY_SECTION = "model_authority"
MODEL_AUTHORITY_STATUS_PASS = "pass"
MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS = "pass_with_gaps"
MODEL_AUTHORITY_STATUS_BLOCKED = "blocked"
_SECTION_RE = re.compile(
    r"(?ms)^\[model_authority\]\s*\n.*?(?=^\[[^\]]+\]\s*$|\Z)"
)


@dataclass(frozen=True)
class ModelAuthorityFinding:
    severity: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class ModelAuthorityAuditReport:
    root: str
    status: str
    observed_source_revision: str = ""
    observed_snapshot_fingerprint: str = ""
    live_snapshot_fingerprint: str = ""
    head_fingerprint: str = ""
    coverage_status: str = ""
    declared_model_ids: tuple[str, ...] = ()
    materialized_model_ids: tuple[str, ...] = ()
    required_model_ids: tuple[str, ...] = ()
    covered_model_ids: tuple[str, ...] = ()
    missing_model_ids: tuple[str, ...] = ()
    unresolved_gap_ids: tuple[str, ...] = ()
    findings: tuple[ModelAuthorityFinding, ...] = ()
    claim_boundary: str = (
        "Authority audit identifies one observed model-system snapshot and its "
        "bounded coverage. It does not execute model, test, install, or release checks."
    )

    @property
    def ok(self) -> bool:
        return self.status in {
            MODEL_AUTHORITY_STATUS_PASS,
            MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "status": self.status,
            "ok": self.ok,
            "observed_source_revision": self.observed_source_revision,
            "observed_snapshot_fingerprint": (
                self.observed_snapshot_fingerprint
            ),
            "live_snapshot_fingerprint": self.live_snapshot_fingerprint,
            "head_fingerprint": self.head_fingerprint,
            "coverage_status": self.coverage_status,
            "declared_model_ids": list(self.declared_model_ids),
            "materialized_model_ids": list(self.materialized_model_ids),
            "required_model_ids": list(self.required_model_ids),
            "covered_model_ids": list(self.covered_model_ids),
            "missing_model_ids": list(self.missing_model_ids),
            "unresolved_gap_ids": list(self.unresolved_gap_ids),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
        }


def _relative_path(value: Any, field_name: str) -> str:
    raw = str(value or "").strip()
    posix = PurePosixPath(raw.replace("\\", "/"))
    windows = PureWindowsPath(raw)
    if (
        not raw
        or raw.startswith(("/", "\\"))
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
    ):
        raise ModelAuthorityError(f"{field_name} must be repository-relative")
    return posix.as_posix()


def _parse_manifest(text: str) -> Mapping[str, Any]:
    try:
        payload = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ModelAuthorityError(f"invalid project manifest: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError("project manifest must be a TOML object")
    return payload


def _section(text: str) -> Mapping[str, Any]:
    payload = _parse_manifest(text)
    section = payload.get(MODEL_AUTHORITY_SECTION)
    if not isinstance(section, Mapping):
        raise ModelAuthorityError("project manifest has no model_authority section")
    return section


def _head_from_section(section: Mapping[str, Any]) -> ModelAuthorityHead:
    required = {
        "system_id",
        "observed_snapshot_path",
        "observed_snapshot_fingerprint",
        "subject_revision",
        "coverage_status",
        "generation",
        "accepted_revision_set_fingerprint",
        "previous_snapshot_fingerprint",
        "activation_receipt_fingerprint",
        "head_fingerprint",
    }
    missing = required - set(section)
    unknown = set(section) - required
    if missing:
        raise ModelAuthorityError(
            f"model_authority missing fields: {sorted(missing)}"
        )
    if unknown:
        raise ModelAuthorityError(
            f"model_authority has unknown fields: {sorted(unknown)}"
        )
    head = ModelAuthorityHead(
        system_id=section["system_id"],
        snapshot_fingerprint=section["observed_snapshot_fingerprint"],
        subject_revision=section["subject_revision"],
        generation=section["generation"],
        accepted_revision_set_fingerprint=section[
            "accepted_revision_set_fingerprint"
        ],
        previous_snapshot_fingerprint=section[
            "previous_snapshot_fingerprint"
        ],
        activation_receipt_fingerprint=section[
            "activation_receipt_fingerprint"
        ],
    )
    if section["head_fingerprint"] != head.fingerprint:
        raise ModelAuthorityError("model authority head fingerprint is stale")
    return head


def render_model_authority_section(
    head: ModelAuthorityHead,
    *,
    snapshot_path: str,
    coverage_status: str,
) -> str:
    path = _relative_path(snapshot_path, "observed_snapshot_path")
    values = {
        "system_id": head.system_id,
        "observed_snapshot_path": path,
        "observed_snapshot_fingerprint": head.snapshot_fingerprint,
        "subject_revision": head.subject_revision,
        "coverage_status": str(coverage_status),
        "generation": head.generation,
        "accepted_revision_set_fingerprint": (
            head.accepted_revision_set_fingerprint
        ),
        "previous_snapshot_fingerprint": (
            head.previous_snapshot_fingerprint
        ),
        "activation_receipt_fingerprint": (
            head.activation_receipt_fingerprint
        ),
        "head_fingerprint": head.fingerprint,
    }
    return (
        "[model_authority]\n"
        f"system_id = {json.dumps(values['system_id'])}\n"
        "observed_snapshot_path = "
        f"{json.dumps(values['observed_snapshot_path'])}\n"
        "observed_snapshot_fingerprint = "
        f"{json.dumps(values['observed_snapshot_fingerprint'])}\n"
        f"subject_revision = {json.dumps(values['subject_revision'])}\n"
        f"coverage_status = {json.dumps(values['coverage_status'])}\n"
        f"generation = {values['generation']}\n"
        "accepted_revision_set_fingerprint = "
        f"{json.dumps(values['accepted_revision_set_fingerprint'])}\n"
        "previous_snapshot_fingerprint = "
        f"{json.dumps(values['previous_snapshot_fingerprint'])}\n"
        "activation_receipt_fingerprint = "
        f"{json.dumps(values['activation_receipt_fingerprint'])}\n"
        f"head_fingerprint = {json.dumps(values['head_fingerprint'])}\n"
    )


def replace_model_authority_section(
    manifest_text: str,
    section_text: str,
) -> str:
    base = _SECTION_RE.sub("", manifest_text).rstrip()
    return base + "\n\n" + section_text.strip() + "\n"


def _snapshot_path(root: Path, snapshot: ModelSystemSnapshot) -> str:
    digest = snapshot.fingerprint.split(":", 1)[1]
    return f".flowguard/model-mesh/snapshots/{digest}.json"


def _write_immutable_json(
    root: Path,
    category: str,
    fingerprint: str,
    payload: Mapping[str, Any],
) -> Path:
    digest = fingerprint.split(":", 1)[1]
    path = root / ".flowguard" / "model-mesh" / category / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ModelAuthorityError(
                f"immutable {category} path contains different bytes"
            )
        return path
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    return path


def load_observed_model_system(
    root: str | Path,
) -> tuple[ModelAuthorityHead, ModelSystemSnapshot]:
    root_path = Path(root).resolve()
    text = read_manifest_text(root_path / ".flowguard" / "project.toml")
    return _load_observed_from_manifest_text(root_path, text)


def _load_observed_from_manifest_text(
    root_path: Path,
    text: str,
) -> tuple[ModelAuthorityHead, ModelSystemSnapshot]:
    section = _section(text)
    head = _head_from_section(section)
    relative = _relative_path(
        section["observed_snapshot_path"],
        "observed_snapshot_path",
    )
    path = (root_path / relative).resolve()
    if root_path not in path.parents:
        raise ModelAuthorityError("observed snapshot escapes project root")
    snapshot = load_model_system_snapshot(path)
    if snapshot.fingerprint != head.snapshot_fingerprint:
        raise ModelAuthorityError("observed snapshot fingerprint mismatch")
    if snapshot.system_id != head.system_id:
        raise ModelAuthorityError("observed snapshot system id mismatch")
    if snapshot.subject_revision != head.subject_revision:
        raise ModelAuthorityError("observed snapshot subject revision mismatch")
    if snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION:
        raise ModelAuthorityError("authority head does not reference observed implementation")
    if snapshot.lifecycle != LIFECYCLE_ACTIVE:
        raise ModelAuthorityError("authority head snapshot is not active")
    if section["coverage_status"] != snapshot.coverage_status:
        raise ModelAuthorityError("manifest coverage status is stale")
    return head, snapshot


def audit_model_authority(
    root: str | Path,
) -> ModelAuthorityAuditReport:
    root_path = Path(root).resolve()
    model_inventory = None
    try:
        head, snapshot = load_observed_model_system(root_path)
        from .model_system_inventory import (
            build_manifest_model_system_snapshot,
            inspect_manifest_model_inventory,
        )

        model_inventory = inspect_manifest_model_inventory(root_path)
        live_snapshot = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=snapshot.snapshot_id,
            system_id=snapshot.system_id,
            subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
            lifecycle=LIFECYCLE_ACTIVE,
        )
    except (ModelAuthorityError, ProjectManifestError, ValueError) as exc:
        inventory_fields: dict[str, tuple[str, ...]] = {}
        finding_code = "model_authority_invalid"
        if model_inventory is not None:
            inventory_fields = {
                "declared_model_ids": model_inventory.declared_ids,
                "materialized_model_ids": model_inventory.materialized_ids,
                "required_model_ids": model_inventory.required_ids,
                "covered_model_ids": model_inventory.covered_ids,
                "missing_model_ids": model_inventory.missing_ids,
            }
            if model_inventory.missing_ids:
                finding_code = "live_model_manifest_incomplete"
        return ModelAuthorityAuditReport(
            root=str(root_path),
            status=MODEL_AUTHORITY_STATUS_BLOCKED,
            **inventory_fields,
            findings=(
                ModelAuthorityFinding(
                    "blocked",
                    finding_code,
                    str(exc),
                ),
            ),
        )
    stale_findings: list[ModelAuthorityFinding] = []
    if model_inventory.missing_ids:
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "live_model_manifest_incomplete",
                "live non-excluded model manifest is not fully materialized: "
                f"declared={list(model_inventory.declared_ids)}, "
                f"materialized={list(model_inventory.materialized_ids)}, "
                f"missing={list(model_inventory.missing_ids)}",
            )
        )
    stored_models = {
        item.logical_model_id: item.fingerprint
        for item in snapshot.model_instances
    }
    live_models = {
        item.logical_model_id: item.fingerprint
        for item in live_snapshot.model_instances
    }
    if stored_models != live_models:
        added = sorted(set(live_models) - set(stored_models))
        removed = sorted(set(stored_models) - set(live_models))
        changed = sorted(
            model_id
            for model_id in set(stored_models) & set(live_models)
            if stored_models[model_id] != live_models[model_id]
        )
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_model_inventory_stale",
                "stored observed model inventory differs from the live manifest: "
                f"added={added}, removed={removed}, changed={changed}",
            )
        )
    if snapshot.identity_payload() != live_snapshot.identity_payload():
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_source_inventory_stale",
                "stored observed snapshot does not exactly equal the fresh "
                f"canonical live reconstruction {live_snapshot.fingerprint}",
            )
        )
    stored_dimensions = {
        item.dimension_id: item.to_dict()
        for item in snapshot.coverage.dimensions
    }
    live_dimensions = {
        item.dimension_id: item.to_dict()
        for item in live_snapshot.coverage.dimensions
    }
    changed_dimensions = sorted(
        dimension_id
        for dimension_id in set(stored_dimensions) | set(live_dimensions)
        if stored_dimensions.get(dimension_id)
        != live_dimensions.get(dimension_id)
    )
    if changed_dimensions:
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_coverage_dimensions_stale",
                "stored observed coverage differs from live owners in dimensions: "
                + ", ".join(changed_dimensions),
            )
        )
    stored_owner_refs = {
        (item.endpoint_kind, item.endpoint_id): item.fingerprint
        for item in snapshot.owner_artifact_refs
    }
    live_owner_refs = {
        (item.endpoint_kind, item.endpoint_id): item.fingerprint
        for item in live_snapshot.owner_artifact_refs
    }
    if stored_owner_refs != live_owner_refs:
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_owner_artifacts_stale",
                "stored owner-artifact identity set differs from current canonical owners",
            )
        )
    if stale_findings:
        return ModelAuthorityAuditReport(
            root=str(root_path),
            status=MODEL_AUTHORITY_STATUS_BLOCKED,
            observed_source_revision=snapshot.subject_revision,
            observed_snapshot_fingerprint=snapshot.fingerprint,
            live_snapshot_fingerprint=live_snapshot.fingerprint,
            head_fingerprint=head.fingerprint,
            coverage_status=snapshot.coverage_status,
            declared_model_ids=model_inventory.declared_ids,
            materialized_model_ids=model_inventory.materialized_ids,
            required_model_ids=model_inventory.required_ids,
            covered_model_ids=model_inventory.covered_ids,
            missing_model_ids=model_inventory.missing_ids,
            unresolved_gap_ids=snapshot.unresolved_gap_ids,
            findings=tuple(stale_findings),
        )
    status = (
        MODEL_AUTHORITY_STATUS_PASS
        if snapshot.coverage_status == "complete_within_declared_boundary"
        else MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS
    )
    findings = ()
    if status == MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS:
        findings = (
            ModelAuthorityFinding(
                "warning",
                "bounded_coverage_incomplete",
                "Observed authority is current but finite coverage retains explicit gaps.",
            ),
        )
    return ModelAuthorityAuditReport(
        root=str(root_path),
        status=status,
        observed_source_revision=snapshot.subject_revision,
        observed_snapshot_fingerprint=snapshot.fingerprint,
        live_snapshot_fingerprint=live_snapshot.fingerprint,
        head_fingerprint=head.fingerprint,
        coverage_status=snapshot.coverage_status,
        declared_model_ids=model_inventory.declared_ids,
        materialized_model_ids=model_inventory.materialized_ids,
        required_model_ids=model_inventory.required_ids,
        covered_model_ids=model_inventory.covered_ids,
        missing_model_ids=model_inventory.missing_ids,
        unresolved_gap_ids=snapshot.unresolved_gap_ids,
        findings=findings,
    )


def bootstrap_model_authority(
    root: str | Path,
    snapshot: ModelSystemSnapshot,
    *,
    bootstrap_evidence_fingerprint: str,
) -> ModelAuthorityHead:
    if snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION:
        raise ModelAuthorityError("bootstrap snapshot must be observed implementation")
    if snapshot.lifecycle != LIFECYCLE_ACTIVE:
        raise ModelAuthorityError("bootstrap snapshot must be active")
    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard" / "project.toml"
    write_content_addressed_snapshot(root_path, snapshot)
    bootstrap_payload = {
        "schema": "flowguard.model_authority_bootstrap.v1",
        "system_id": snapshot.system_id,
        "snapshot_fingerprint": snapshot.fingerprint,
        "subject_revision": snapshot.subject_revision,
        "evidence_fingerprint": bootstrap_evidence_fingerprint,
        "claim_boundary": (
            "Bootstrap establishes the first observed authority pointer only; "
            "coverage gaps remain explicit and require later revision evidence."
        ),
    }
    bootstrap_fingerprint = canonical_fingerprint(bootstrap_payload)
    _write_immutable_json(
        root_path,
        "bootstraps",
        bootstrap_fingerprint,
        {**bootstrap_payload, "fingerprint": bootstrap_fingerprint},
    )
    head = ModelAuthorityHead(
        system_id=snapshot.system_id,
        snapshot_fingerprint=snapshot.fingerprint,
        subject_revision=snapshot.subject_revision,
        generation=1,
        accepted_revision_set_fingerprint=bootstrap_fingerprint,
        previous_snapshot_fingerprint="",
        activation_receipt_fingerprint=bootstrap_fingerprint,
    )
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        try:
            _section(current_text)
        except ModelAuthorityError:
            pass
        else:
            raise ModelAuthorityError(
                "project already has model authority; use a revision set"
            )
        section_text = render_model_authority_section(
            head,
            snapshot_path=_snapshot_path(root_path, snapshot),
            coverage_status=snapshot.coverage_status,
        )
        replace_project_manifest_locked(
            manifest_path,
            replace_model_authority_section(current_text, section_text),
        )
    return head


def activate_model_revision_set(
    root: str | Path,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
    *,
    receipt_id: str,
) -> tuple[ModelAuthorityHead, ModelActivationReceipt]:
    """Persist immutable records and update the sole pointer last under one lock."""

    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        current_head, base_snapshot = _load_observed_from_manifest_text(
            root_path,
            current_text,
        )
        from .model_system_inventory import (
            build_manifest_model_system_snapshot,
        )

        live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
        )
        next_head, receipt = validate_activation_plan(
            current_head,
            base_snapshot,
            candidate_snapshot,
            revision_set,
            live_candidate_snapshot=live_candidate,
            receipt_id=receipt_id,
        )
        write_content_addressed_snapshot(root_path, candidate_snapshot)
        _write_immutable_json(
            root_path,
            "revisions",
            revision_set.fingerprint,
            revision_set.to_dict(),
        )
        _write_immutable_json(
            root_path,
            "activations",
            receipt.fingerprint,
            {**receipt.to_dict(), "fingerprint": receipt.fingerprint},
        )
        final_live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
        )
        if (
            final_live_candidate.identity_payload()
            != candidate_snapshot.identity_payload()
        ):
            raise ModelAuthorityError(
                "live candidate changed before pointer replacement"
            )
        section_text = render_model_authority_section(
            next_head,
            snapshot_path=_snapshot_path(root_path, candidate_snapshot),
            coverage_status=candidate_snapshot.coverage_status,
        )
        replace_project_manifest_locked(
            manifest_path,
            replace_model_authority_section(current_text, section_text),
        )
    return next_head, receipt


def rollback_observed_model_system(
    root: str | Path,
    contract: ModelRollbackContract,
    candidate_snapshot: ModelSystemSnapshot,
    reverse_revision_set: ModelRevisionSet,
    *,
    completed_evidence_fingerprints: Iterable[str],
    requested_result: str,
    receipt_id: str,
    reason: str,
) -> tuple[ModelAuthorityHead, ModelRollbackReceipt]:
    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        current_head, current_snapshot = _load_observed_from_manifest_text(
            root_path,
            current_text,
        )
        receipt = validate_operational_rollback(
            current_head,
            contract,
            reverse_revision_set,
            completed_evidence_fingerprints=completed_evidence_fingerprints,
            requested_result=requested_result,
            receipt_id=receipt_id,
            reason=reason,
        )
        if requested_result == ROLLBACK_RESULT_FORWARD_REPAIR:
            raise ModelAuthorityError(
                "forward repair preserves the current head until a new revision activates"
            )
        if candidate_snapshot.fingerprint != contract.to_snapshot_fingerprint:
            raise ModelAuthorityError("rollback target snapshot is stale")
        if (
            candidate_snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION
            or candidate_snapshot.lifecycle != LIFECYCLE_ACTIVE
        ):
            raise ModelAuthorityError("rollback target is not an active observed snapshot")
        from .model_system_inventory import (
            build_manifest_model_system_snapshot,
        )

        live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
        )
        next_head, _ = validate_activation_plan(
            current_head,
            current_snapshot,
            candidate_snapshot,
            reverse_revision_set,
            live_candidate_snapshot=live_candidate,
            receipt_id=f"reverse-activation:{receipt_id}",
        )
        write_content_addressed_snapshot(root_path, candidate_snapshot)
        _write_immutable_json(
            root_path,
            "rollback-contracts",
            contract.fingerprint,
            {**contract.to_dict(), "fingerprint": contract.fingerprint},
        )
        _write_immutable_json(
            root_path,
            "revisions",
            reverse_revision_set.fingerprint,
            reverse_revision_set.to_dict(),
        )
        _write_immutable_json(
            root_path,
            "rollbacks",
            receipt.fingerprint,
            {**receipt.to_dict(), "fingerprint": receipt.fingerprint},
        )
        next_head = replace(
            next_head,
            accepted_revision_set_fingerprint=reverse_revision_set.fingerprint,
            activation_receipt_fingerprint=receipt.fingerprint,
        )
        final_live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
        )
        if (
            final_live_candidate.identity_payload()
            != candidate_snapshot.identity_payload()
        ):
            raise ModelAuthorityError(
                "restored live state changed before rollback pointer replacement"
            )
        section_text = render_model_authority_section(
            next_head,
            snapshot_path=_snapshot_path(root_path, candidate_snapshot),
            coverage_status=candidate_snapshot.coverage_status,
        )
        replace_project_manifest_locked(
            manifest_path,
            replace_model_authority_section(current_text, section_text),
        )
    return next_head, receipt


__all__ = [
    "MODEL_AUTHORITY_STATUS_BLOCKED",
    "MODEL_AUTHORITY_STATUS_PASS",
    "MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS",
    "ModelAuthorityAuditReport",
    "ModelAuthorityFinding",
    "activate_model_revision_set",
    "audit_model_authority",
    "bootstrap_model_authority",
    "load_observed_model_system",
    "render_model_authority_section",
    "replace_model_authority_section",
    "rollback_observed_model_system",
]
