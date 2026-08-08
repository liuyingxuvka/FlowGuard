"""Manifest-owned, observable execution for repository FlowGuard models.

The manifest is the execution authority.  Filesystem discovery is used only
to prove that the manifest accounts for every local model in both directions.
Each child runs in its own process and receives an isolated artifact directory.
"""

from __future__ import annotations

import fnmatch
from contextlib import ExitStack
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping, Sequence

from .evidence_lifecycle import (
    evidence_execution_lease,
    ensure_new_run_directory,
    publish_run,
    store_text_object,
)
from .evidence_receipts import (
    RECEIPT_STATUS_PASS,
    VERIFICATION_STATUS_STALE,
    EvidenceReceipt,
    ReceiptVerificationResult,
    fingerprint_value,
    load_evidence_receipt,
    receipt_path as evidence_receipt_path,
    verify_evidence_receipt,
)
from .model_authority import (
    ModelInstanceRef,
    build_model_instance_ref,
)
from .model_purpose import ModelPurposeClosure, ModelPurposeError, validate_unique_model_instances
from .source_identity import source_file_fingerprint
from .process_supervision import (
    SupervisedCommandResult,
    run_supervised,
    write_terminal_artifact,
)
from .validation_owner_execution import (
    publish_supervised_validation_owner_result,
)

from .validation_results import (
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_CANCELLED,
    VALIDATION_STATUS_FAIL,
    VALIDATION_STATUS_INTERNAL_ERROR,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_TIMEOUT,
    ValidationChildResult,
    ValidationResult,
    aggregate_status,
)
from .validation_ownership import (
    OWNER_BLOCKED,
    OWNER_EXECUTE,
    OWNER_RECEIPT_KIND,
    OWNER_REUSE_CURRENT,
    ValidationOwnerContract,
    ValidationOwnerObservation,
    ValidationObservationFreshness,
    _assert_owner_receipt_integrity,
    assert_validation_owner_observation_fresh,
    assert_validation_owner_observation_receipts_fresh,
    build_child_bound_owner_receipt_context,
    build_owner_current,
    build_owner_current_from_observation,
    build_owner_receipt_context,
    child_from_owner_receipt,
    observe_validation_owners,
    plan_validation_owners,
    record_validation_owner_nonpass,
    refresh_validation_owner_observation_receipts,
    save_child_bound_owner_receipt,
    save_child_bound_owner_receipt_from_observation,
)


MANIFEST_SCHEMA = "flowguard.model_regression_manifest.v4"
MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA = (
    "flowguard.model_regression_parent_receipt.v2"
)
MODEL_REGRESSION_PARENT_ARTIFACT_TYPE = (
    "flowguard_model_regression_parent_receipt"
)
_MODEL_REGRESSION_PARENT_FIELDS = frozenset(
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
        "execution_receipt_id",
        "execution_receipt_fingerprint",
        "claim_boundary",
        "parent_receipt_fingerprint",
    }
)
_MODEL_REGRESSION_PARENT_CHILD_FIELDS = frozenset(
    {"model_id", "receipt_id", "receipt_fingerprint"}
)
TIER_RANK = {"fast": 0, "focused": 1, "full": 2}


class ModelRegressionManifestError(ValueError):
    """Raised when the checked-in model inventory is incomplete or invalid."""


class ModelRegressionEvidenceError(ValueError):
    """Raised when no unique exact-current full model evidence composition exists."""


class ModelRegressionParentNotCurrentError(ModelRegressionEvidenceError):
    """Raised when only structurally valid but stale parent wrappers remain."""


@dataclass(frozen=True)
class ModelRegressionEntry:
    model_id: str
    model_path: str
    runner: tuple[str, ...]
    tier: str
    timeout_seconds: float
    shard_safe: bool
    mutation_policy: str
    input_globs: tuple[str, ...]
    intent_source_inputs: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    exclusion_reason: str = ""
    distribution_policy: str = "required_public"
    absence_reason: str = ""
    model_kind: str = "executable_workflow"
    purpose_closure: ModelPurposeClosure | None = None
    shard_safety_proof: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ModelRegressionEntry":
        allowed = {
            "model_id",
            "model_path",
            "runner",
            "tier",
            "timeout_seconds",
            "shard_safe",
            "mutation_policy",
            "input_globs",
            "intent_source_inputs",
            "expected_artifacts",
            "exclusion_reason",
            "distribution_policy",
            "absence_reason",
            "model_kind",
            "purpose_closure",
            "shard_safety_proof",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ModelRegressionManifestError(
                "unknown model entry fields: " + ", ".join(unknown)
            )
        runner = payload.get("runner", ())
        if isinstance(runner, str):
            runner = (runner,)
        raw_purpose = payload.get("purpose_closure")
        purpose = ModelPurposeClosure.from_dict(raw_purpose) if isinstance(raw_purpose, Mapping) else None
        return cls(
            model_id=str(payload.get("model_id", "")),
            model_path=str(payload.get("model_path", "")),
            runner=tuple(str(item) for item in runner),
            tier=str(payload.get("tier", "")),
            timeout_seconds=float(payload.get("timeout_seconds", 0)),
            shard_safe=bool(payload.get("shard_safe", False)),
            mutation_policy=str(payload.get("mutation_policy", "")),
            input_globs=tuple(str(item) for item in payload.get("input_globs", ())),
            intent_source_inputs=tuple(
                str(item) for item in payload.get("intent_source_inputs", ())
            ),
            expected_artifacts=tuple(str(item) for item in payload.get("expected_artifacts", ())),
            exclusion_reason=str(payload.get("exclusion_reason", "")),
            distribution_policy=str(payload.get("distribution_policy", "required_public")),
            absence_reason=str(payload.get("absence_reason", "")),
            model_kind=str(
                payload.get("model_kind", "executable_workflow")
            ),
            purpose_closure=purpose,
            shard_safety_proof=dict(payload.get("shard_safety_proof", {})),
        )

    @property
    def excluded(self) -> bool:
        return bool(self.exclusion_reason)

    @property
    def effective_input_patterns(self) -> tuple[str, ...]:
        """Return authored selectors plus exact local intent-source inputs."""

        return tuple(dict.fromkeys((*self.input_globs, *self.intent_source_inputs)))

    def command(self, *, root: Path) -> tuple[str, ...]:
        values = {"python": sys.executable, "root": str(root)}
        return tuple(item.format(**values) for item in self.runner)


@dataclass(frozen=True)
class SharedInputGroup:
    component_id: str
    globs: tuple[str, ...]
    consumers: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SharedInputGroup":
        allowed = {"component_id", "globs", "consumers"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ModelRegressionManifestError(
                "unknown shared input group fields: " + ", ".join(unknown)
            )
        return cls(
            component_id=str(payload.get("component_id", "")),
            globs=tuple(str(item) for item in payload.get("globs", ())),
            consumers=tuple(str(item) for item in payload.get("consumers", ())),
        )


@dataclass(frozen=True)
class ModelRegressionManifest:
    path: Path
    entries: tuple[ModelRegressionEntry, ...]
    governed_input_globs: tuple[str, ...]
    snapshot_only_input_globs: tuple[str, ...]
    shared_input_groups: tuple[SharedInputGroup, ...]

    @classmethod
    def load(cls, root: str | Path = ".", *, path: str | Path | None = None) -> "ModelRegressionManifest":
        root_path = Path(root).resolve()
        manifest_path = Path(path).resolve() if path else root_path / ".flowguard" / "model-regression-manifest.json"
        if not manifest_path.is_file():
            raise ModelRegressionManifestError(f"missing model regression manifest: {manifest_path}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegressionManifestError(f"cannot read model regression manifest: {exc}") from exc
        if payload.get("schema_version") != MANIFEST_SCHEMA:
            raise ModelRegressionManifestError(f"unsupported manifest schema: {payload.get('schema_version')!r}")
        allowed = {
            "schema_version",
            "models",
            "governed_input_globs",
            "snapshot_only_input_globs",
            "shared_input_groups",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ModelRegressionManifestError(
                "unknown manifest fields: " + ", ".join(unknown)
            )
        entries = tuple(ModelRegressionEntry.from_dict(item) for item in payload.get("models", ()))
        return cls(
            path=manifest_path,
            entries=entries,
            governed_input_globs=tuple(
                str(item) for item in payload.get("governed_input_globs", ())
            ),
            snapshot_only_input_globs=tuple(
                str(item)
                for item in payload.get("snapshot_only_input_globs", ())
            ),
            shared_input_groups=tuple(
                SharedInputGroup.from_dict(item)
                for item in payload.get("shared_input_groups", ())
            ),
        )

    def shared_patterns_for(self, model_id: str) -> tuple[str, ...]:
        return tuple(
            pattern
            for group in self.shared_input_groups
            if model_id in group.consumers
            for pattern in group.globs
        )

    def owner_projection_fingerprint(
        self,
        entry: ModelRegressionEntry,
    ) -> str:
        """Project only the manifest semantics consumed by one model owner."""

        purpose = (
            entry.purpose_closure.to_dict()
            if entry.purpose_closure is not None
            else None
        )
        entry_payload = {
            "model_id": entry.model_id,
            "model_path": entry.model_path,
            "runner": list(entry.runner),
            "tier": entry.tier,
            "timeout_seconds": entry.timeout_seconds,
            "shard_safe": entry.shard_safe,
            "mutation_policy": entry.mutation_policy,
            "input_globs": list(entry.input_globs),
            "intent_source_inputs": list(entry.intent_source_inputs),
            "expected_artifacts": list(entry.expected_artifacts),
            "exclusion_reason": entry.exclusion_reason,
            "distribution_policy": entry.distribution_policy,
            "absence_reason": entry.absence_reason,
            "model_kind": entry.model_kind,
            "purpose_closure": purpose,
            "shard_safety_proof": dict(entry.shard_safety_proof),
        }
        shared_groups = tuple(
            {
                "component_id": group.component_id,
                "globs": list(group.globs),
            }
            for group in sorted(
                self.shared_input_groups,
                key=lambda item: item.component_id,
            )
            if entry.model_id in group.consumers
        )
        return fingerprint_value(
            {
                "schema_version": MANIFEST_SCHEMA,
                "entry": entry_payload,
                "governed_input_globs": list(self.governed_input_globs),
                "snapshot_only_input_globs": list(
                    self.snapshot_only_input_globs
                ),
                "shared_input_groups": shared_groups,
            }
        )


@dataclass(frozen=True)
class ManifestAudit:
    ok: bool
    discovered_model_ids: tuple[str, ...]
    registered_model_ids: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "discovered_model_ids": list(self.discovered_model_ids),
            "registered_model_ids": list(self.registered_model_ids),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ModelImpactMap:
    owners_by_path: Mapping[str, tuple[str, ...]]
    governed_paths: tuple[str, ...]
    snapshot_only_paths: tuple[str, ...]
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def audit_intent_source_input_bindings(
    root: str | Path,
    manifest: ModelRegressionManifest,
    contributions: Sequence[Any],
    source_identities: Sequence[Any] = (),
) -> tuple[str, ...]:
    """Compare active local intent sources with exact owner-local inputs.

    WorkContext artifacts deliberately remain on their typed external identity
    path.  This comparison owns only direct project files and never treats a
    broad authored glob as an intent-owner binding.
    """

    from .model_intent import (
        ModelIntentContribution,
        ModelIntentSourceIdentity,
    )

    root_path = Path(root).resolve()
    items = tuple(contributions)
    identities = tuple(source_identities)
    errors: list[str] = []
    if any(not isinstance(item, ModelIntentContribution) for item in items):
        return ("intent-source input review requires typed contributions",)
    if identities and any(
        not isinstance(item, ModelIntentSourceIdentity) for item in identities
    ):
        return ("intent-source input review requires typed source identities",)

    contribution_by_id = {item.contribution_id: item for item in items}
    if len(contribution_by_id) != len(items):
        errors.append("intent-source input review has duplicate contribution ids")
    identity_by_id = {item.contribution_id: item for item in identities}
    if identities and len(identity_by_id) != len(identities):
        errors.append("intent-source input review has duplicate source identities")
    if identities and set(identity_by_id) != set(contribution_by_id):
        errors.append(
            "intent-source input review contribution/source denominator differs"
        )

    entries = {entry.model_id: entry for entry in manifest.entries}
    expected_by_owner: dict[str, set[str]] = {
        owner: set() for owner in entries
    }
    for contribution in items:
        raw_owner = contribution.logical_model_id
        if not raw_owner.startswith("model:"):
            errors.append(
                f"{contribution.contribution_id}: logical model owner is not exact: {raw_owner}"
            )
            continue
        owner = raw_owner.split("model:", 1)[1]
        if not owner or owner not in entries:
            errors.append(
                f"{contribution.contribution_id}: unknown logical model owner: {raw_owner}"
            )
            continue
        identity = identity_by_id.get(contribution.contribution_id)
        if identity is not None:
            if identity.authority_kind == "work_context":
                continue
            path = identity.resolved_project_ref
        elif contribution.work_context_id:
            continue
        else:
            path = contribution.source_ref
        expected_by_owner[owner].add(path)

    for owner, entry in sorted(entries.items()):
        actual_rows = tuple(entry.intent_source_inputs)
        actual = set(actual_rows)
        if len(actual) != len(actual_rows):
            errors.append(f"{owner}: duplicate exact intent-source inputs")
        expected = expected_by_owner[owner]
        for path in sorted(expected - actual):
            errors.append(f"{owner}: missing intent-source input: {path}")
        for path in sorted(actual - expected):
            errors.append(f"{owner}: extra intent-source input: {path}")
        for path in sorted(actual):
            candidate = (root_path / Path(*PurePosixPath(path).parts)).resolve()
            try:
                candidate.relative_to(root_path)
            except ValueError:
                errors.append(f"{owner}: intent-source input escapes repository: {path}")
                continue
            if not candidate.is_file():
                errors.append(f"{owner}: intent-source input is not a file: {path}")
    return tuple(errors)


def _resolve_relative_files(
    root: Path,
    patterns: Sequence[str],
) -> tuple[str, ...]:
    values: set[str] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                values.add(resolved.relative_to(root).as_posix())
            except ValueError as exc:
                raise ModelRegressionManifestError(
                    f"impact-map input escapes repository: {path}"
                ) from exc
    return tuple(sorted(values))


def compile_model_impact_map(
    root: str | Path,
    manifest: ModelRegressionManifest,
) -> ModelImpactMap:
    """Compile exact local/shared ownership and fail closed on unknown inputs."""

    root_path = Path(root).resolve()
    errors: list[str] = []
    registered = {entry.model_id for entry in manifest.entries}
    if not manifest.governed_input_globs:
        errors.append("governed_input_globs must not be empty")
    component_ids = [item.component_id for item in manifest.shared_input_groups]
    for duplicate in sorted(
        {item for item in component_ids if component_ids.count(item) > 1}
    ):
        errors.append(f"duplicate shared component_id: {duplicate}")
    for group in manifest.shared_input_groups:
        if not group.component_id or not group.globs or not group.consumers:
            errors.append(
                "shared input group requires component_id, globs, and consumers"
            )
        for consumer in sorted(set(group.consumers) - registered):
            errors.append(
                f"{group.component_id}: unknown shared-input consumer: {consumer}"
            )
    governed = _resolve_relative_files(
        root_path,
        manifest.governed_input_globs,
    )
    snapshot_only = _resolve_relative_files(
        root_path,
        manifest.snapshot_only_input_globs,
    )
    overlap = sorted(set(governed) & set(snapshot_only))
    errors.extend(
        f"impact path is both governed and snapshot-only: {path}"
        for path in overlap
    )
    owners: dict[str, set[str]] = {}
    for entry in manifest.entries:
        for path in _resolve_relative_files(
            root_path,
            entry.effective_input_patterns,
        ):
            owners.setdefault(path, set()).add(entry.model_id)
    for group in manifest.shared_input_groups:
        for path in _resolve_relative_files(root_path, group.globs):
            owners.setdefault(path, set()).update(group.consumers)
    for path in sorted(set(governed) - set(owners)):
        errors.append(f"governed model input has no declared owner: {path}")
    return ModelImpactMap(
        owners_by_path={
            path: tuple(sorted(values)) for path, values in sorted(owners.items())
        },
        governed_paths=governed,
        snapshot_only_paths=snapshot_only,
        errors=tuple(errors),
    )


@dataclass(frozen=True)
class ModelRunResult:
    model_id: str
    status: str
    exit_code: int | None
    seconds: float
    command: tuple[str, ...]
    stdout_path: str
    stderr_path: str
    receipt_path: str
    artifact_paths: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()
    message: str = ""
    model_instance_id: str = ""
    model_kind: str = ""
    model_instance_fingerprint: str = ""
    input_inventory_fingerprint: str = ""
    input_inventory: tuple[Mapping[str, str], ...] = ()
    artifact_fingerprints: Mapping[str, str] = field(default_factory=dict)
    purpose_closure_fingerprint: str = ""
    purpose_claim_boundary: str = ""
    stdout: Mapping[str, Any] = field(default_factory=dict, compare=False)
    stderr: Mapping[str, Any] = field(default_factory=dict, compare=False)
    execution_disposition: str = "execute"
    producer_invocations: int = 1
    receipt_fingerprint: str = ""
    supervision: SupervisedCommandResult | None = field(
        default=None,
        compare=False,
        repr=False,
    )

    @property
    def ok(self) -> bool:
        return self.status == VALIDATION_STATUS_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "seconds": self.seconds,
            "command": list(self.command),
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "receipt_path": self.receipt_path,
            "artifact_paths": list(self.artifact_paths),
            "finding_codes": list(self.finding_codes),
            "message": self.message,
            "model_instance_id": self.model_instance_id,
            "model_kind": self.model_kind,
            "model_instance_fingerprint": self.model_instance_fingerprint,
            "input_inventory_fingerprint": self.input_inventory_fingerprint,
            "input_inventory": [dict(item) for item in self.input_inventory],
            "artifact_fingerprints": dict(self.artifact_fingerprints),
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
            "purpose_claim_boundary": self.purpose_claim_boundary,
            "stdout": dict(self.stdout),
            "stderr": dict(self.stderr),
            "execution_disposition": self.execution_disposition,
            "producer_invocations": self.producer_invocations,
            "receipt_fingerprint": self.receipt_fingerprint,
        }


@dataclass(frozen=True)
class ModelRegressionReport:
    root: str
    tier: str
    output_dir: str
    audit: ManifestAudit
    results: tuple[ModelRunResult, ...]
    selected_model_ids: tuple[str, ...]
    skipped_model_ids: tuple[str, ...]
    unavailable_optional_model_ids: tuple[str, ...] = ()
    mutation_paths: tuple[str, ...] = ()
    started_at_epoch: float = 0.0
    finished_at_epoch: float = 0.0
    command: str = "flowguard-model-regressions"
    parent_claim_scope: str = "scoped"
    parent_receipt_path: str = ""
    parent_receipt_fingerprint: str = ""
    initial_observation_seconds: float = 0.0
    receipt_reconciliation_seconds: float = 0.0
    final_freshness_seconds: float = 0.0
    parent_composition_seconds: float = 0.0
    per_leaf_source_current_rebuild_count: int = 0
    per_leaf_receipt_store_scan_count: int = 0
    receipt_reconciliation_count: int = 0
    initial_observation_fingerprint: str = ""
    final_freshness_fingerprint: str = ""

    @property
    def status(self) -> str:
        if not self.audit.ok or self.mutation_paths:
            return VALIDATION_STATUS_BLOCKED
        children = tuple(
            ValidationChildResult(
                child_id=item.model_id,
                status=item.status,
                summary=item.message,
                receipt_id=item.receipt_path,
                artifact_paths=item.artifact_paths,
                claim_boundary="This child receipt covers only the declared model runner invocation.",
                payload={},
            )
            for item in self.results
        )
        return aggregate_status(children, required_child_ids=self.selected_model_ids)

    @property
    def ok(self) -> bool:
        return self.status == VALIDATION_STATUS_PASS

    def to_validation_result(self) -> ValidationResult:
        counts = {
            "registered": len(self.audit.registered_model_ids),
            "selected": len(self.selected_model_ids),
            "passed": sum(item.ok for item in self.results),
            "failed": sum(not item.ok for item in self.results),
            "skipped": len(self.skipped_model_ids),
            "unavailable_optional": len(self.unavailable_optional_model_ids),
            "executed": sum(item.execution_disposition == "execute" for item in self.results),
            "reused": sum(item.execution_disposition == "reuse_current" for item in self.results),
            "producer_invocations": sum(item.producer_invocations for item in self.results),
        }
        children = tuple(
            ValidationChildResult(
                child_id=item.model_id,
                status=item.status,
                summary=item.message,
                receipt_id=item.receipt_path,
                artifact_paths=(item.stdout_path, item.stderr_path, item.receipt_path, *item.artifact_paths),
                claim_boundary="This child receipt covers only the declared model runner invocation.",
                payload={
                    "exit_code": item.exit_code,
                    "seconds": item.seconds,
                    "finding_codes": list(item.finding_codes),
                    "model_instance_id": item.model_instance_id,
                    "model_instance_fingerprint": item.model_instance_fingerprint,
                    "input_inventory_fingerprint": item.input_inventory_fingerprint,
                    "execution_disposition": item.execution_disposition,
                    "receipt_fingerprint": item.receipt_fingerprint,
                },
            )
            for item in self.results
        )
        failures = tuple(
            {"code": item.finding_codes[0] if item.finding_codes else "model_failed", "message": f"{item.model_id}: {item.message}"}
            for item in self.results
            if not item.ok
        )
        blockers = tuple({"code": "manifest_audit", "message": item} for item in self.audit.errors) + tuple(
            {"code": "tracked_mutation", "message": item} for item in self.mutation_paths
        )
        claim = (
            "Full-tier success covers every required-public model and every available optional-local model registered in the current manifest."
            if self.parent_claim_scope == "full"
            else (
                f"{self.tier.title()}-tier success is scoped feedback and does "
                "not support a full-model release claim."
            )
        )
        return ValidationResult(
            command=self.command,
            status=self.status,
            scope="model-regression-manifest",
            tier=self.tier,
            counts=counts,
            failures=failures,
            blockers=blockers,
            residual_risk=(
                *(() if self.tier == "full" else ("Models assigned to broader tiers were not executed.",)),
                *(
                    ("Optional local-only models were absent and are not public release requirements.",)
                    if self.unavailable_optional_model_ids
                    else ()
                ),
            ),
            claim_boundary=claim,
            progress_summary={
                "started_at_epoch": self.started_at_epoch,
                "finished_at_epoch": self.finished_at_epoch,
                "elapsed_seconds": round(max(0.0, self.finished_at_epoch - self.started_at_epoch), 3),
            },
            artifact_paths=(str(Path(self.output_dir) / "report.json"),),
            children=children,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = self.to_validation_result().to_dict()
        payload.update(
            {
                "root": self.root,
                "output_dir": self.output_dir,
                "manifest_audit": self.audit.to_dict(),
                "selected_model_ids": list(self.selected_model_ids),
                "skipped_model_ids": list(self.skipped_model_ids),
                "unavailable_optional_model_ids": list(self.unavailable_optional_model_ids),
                "mutation_paths": list(self.mutation_paths),
                "parent_claim_scope": self.parent_claim_scope,
                "parent_receipt_path": self.parent_receipt_path,
                "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
                "validation_observation": {
                    "initial_fingerprint": self.initial_observation_fingerprint,
                    "final_freshness_fingerprint": (
                        self.final_freshness_fingerprint
                    ),
                    "complete_observation_count": (
                        2 if self.final_freshness_fingerprint else 1
                    ),
                    "initial_seconds": self.initial_observation_seconds,
                    "receipt_reconciliation_seconds": (
                        self.receipt_reconciliation_seconds
                    ),
                    "final_freshness_seconds": self.final_freshness_seconds,
                    "parent_composition_seconds": self.parent_composition_seconds,
                    "per_leaf_source_current_rebuild_count": (
                        self.per_leaf_source_current_rebuild_count
                    ),
                    "per_leaf_receipt_store_scan_count": (
                        self.per_leaf_receipt_store_scan_count
                    ),
                    "receipt_reconciliation_count": (
                        self.receipt_reconciliation_count
                    ),
                },
                "results": [item.to_dict() for item in self.results],
            }
        )
        return payload


@dataclass(frozen=True)
class CurrentModelRegressionChildEvidence:
    """One independently verified current model-owner leaf receipt."""

    model_id: str
    receipt_id: str
    receipt_fingerprint: str
    model_instance_id: str = ""
    model_instance_fingerprint: str = ""
    input_inventory_fingerprint: str = ""
    purpose_closure_fingerprint: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "model_instance_id": self.model_instance_id,
            "model_instance_fingerprint": self.model_instance_fingerprint,
            "input_inventory_fingerprint": self.input_inventory_fingerprint,
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
        }


@dataclass(frozen=True)
class CurrentModelRegressionParentEvidence:
    """The unique current full parent plus its independently verified leaves."""

    manifest_fingerprint: str
    parent_artifact_path: str
    parent_artifact_fingerprint: str
    parent_execution_receipt_id: str
    parent_execution_receipt_fingerprint: str
    children: tuple[CurrentModelRegressionChildEvidence, ...]
    claim_boundary: str = (
        "The parent proves only the exact current full/full/pass composition. "
        "Every child identity remains independently owned by its model receipt."
    )

    @property
    def child_evidence_by_model_id(
        self,
    ) -> Mapping[str, CurrentModelRegressionChildEvidence]:
        return {item.model_id: item for item in self.children}

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "parent_artifact_path": self.parent_artifact_path,
            "parent_artifact_fingerprint": self.parent_artifact_fingerprint,
            "parent_execution_receipt_id": self.parent_execution_receipt_id,
            "parent_execution_receipt_fingerprint": (
                self.parent_execution_receipt_fingerprint
            ),
            "children": [item.to_dict() for item in self.children],
            "claim_boundary": self.claim_boundary,
        }


ProgressCallback = Callable[[Mapping[str, Any]], None]


def discover_model_directories(root: str | Path = ".") -> tuple[Path, ...]:
    root_path = Path(root).resolve()
    base = root_path / ".flowguard"
    if not base.is_dir():
        return ()
    return tuple(sorted(path.parent for path in base.rglob("model.py") if path.is_file()))


def _model_id(root: Path, directory: Path) -> str:
    return directory.relative_to(root / ".flowguard").as_posix()


def audit_manifest(root: str | Path, manifest: ModelRegressionManifest) -> ManifestAudit:
    root_path = Path(root).resolve()
    discovered = tuple(_model_id(root_path, item) for item in discover_model_directories(root_path))
    registered = tuple(item.model_id for item in manifest.entries)
    errors: list[str] = []
    duplicates = sorted({item for item in registered if registered.count(item) > 1})
    errors.extend(f"duplicate model_id: {item}" for item in duplicates)
    closures = tuple(item.purpose_closure for item in manifest.entries if item.purpose_closure is not None)
    try:
        validate_unique_model_instances(closures)
    except ModelPurposeError as exc:
        errors.append(str(exc))
    errors.extend(f"unregistered model directory: {item}" for item in sorted(set(discovered) - set(registered)))
    by_id = {item.model_id: item for item in manifest.entries}
    errors.extend(
        f"manifest required-public model missing from filesystem: {item}"
        for item in sorted(set(registered) - set(discovered))
        if by_id[item].distribution_policy == "required_public"
    )
    try:
        impact_map = compile_model_impact_map(root_path, manifest)
        errors.extend(impact_map.errors)
    except ModelRegressionManifestError as exc:
        errors.append(str(exc))
    for entry in manifest.entries:
        purpose = entry.purpose_closure
        if purpose is None:
            errors.append(f"{entry.model_id}: missing purpose_closure")
        elif purpose.reusable_model_type_id != entry.model_id:
            errors.append(f"{entry.model_id}: purpose reusable_model_type_id does not match model_id")
        elif not purpose.model_instance_id.startswith(f"regression:{entry.model_id}:"):
            errors.append(
                f"{entry.model_id}: purpose model_instance_id is not scoped to its logical regression model"
            )
        elif tuple(
            evidence_id
            for evidence_id in purpose.evidence_check_ids
            if evidence_id.startswith("check:model-regression:")
        ) != (f"check:model-regression:{entry.model_id}",):
            errors.append(
                f"{entry.model_id}: purpose requires one exact logical model-regression evidence identity"
            )
        if not entry.model_id or entry.model_path != f".flowguard/{entry.model_id}/model.py":
            errors.append(f"{entry.model_id or '<empty>'}: model_path must match model_id")
        elif not (root_path / entry.model_path).is_file() and entry.distribution_policy == "required_public":
            errors.append(f"{entry.model_id}: model_path does not exist")
        if entry.tier not in TIER_RANK:
            errors.append(f"{entry.model_id}: invalid tier {entry.tier!r}")
        if entry.timeout_seconds <= 0:
            errors.append(f"{entry.model_id}: timeout_seconds must be positive")
        if entry.mutation_policy not in {"none", "isolated_output", "mutating"}:
            errors.append(f"{entry.model_id}: invalid mutation_policy {entry.mutation_policy!r}")
        if entry.shard_safety_proof:
            proof = entry.shard_safety_proof
            if entry.mutation_policy != "isolated_output":
                errors.append(
                    f"{entry.model_id}: shard_safety_proof requires isolated_output mutation policy"
                )
            if proof.get("schema_version") != "flowguard.model_shard_safety_contract.v1":
                errors.append(f"{entry.model_id}: invalid shard_safety_proof schema")
            if int(proof.get("parallel_copies", 0)) < 2:
                errors.append(f"{entry.model_id}: shard_safety_proof requires at least two parallel copies")
            if proof.get("output_isolation") != "FLOWGUARD_OUTPUT_DIR":
                errors.append(f"{entry.model_id}: shard_safety_proof must bind FLOWGUARD_OUTPUT_DIR")
            if proof.get("shared_mutation_policy") != "zero_repository_mutation":
                errors.append(f"{entry.model_id}: shard_safety_proof must reject repository mutation")
            required_checks = {
                "serial_parallel_semantic_equivalence",
                "disjoint_artifact_ownership",
                "stable_input_inventory",
                "zero_repository_mutation",
            }
            declared_checks = {str(item) for item in proof.get("required_checks", ())}
            missing_checks = sorted(required_checks - declared_checks)
            if missing_checks:
                errors.append(
                    f"{entry.model_id}: shard_safety_proof missing checks: {', '.join(missing_checks)}"
                )
        if entry.shard_safe and entry.model_id == "harden_ui_content_visibility_validation":
            if not entry.shard_safety_proof:
                errors.append(
                    f"{entry.model_id}: shard-safe UI aggregate requires executable shard_safety_proof"
                )
        if entry.distribution_policy not in {"required_public", "optional_local"}:
            errors.append(f"{entry.model_id}: invalid distribution_policy {entry.distribution_policy!r}")
        if entry.distribution_policy == "optional_local" and len(entry.absence_reason.strip()) < 12:
            errors.append(f"{entry.model_id}: optional-local absence reason is not reviewable")
        if not entry.input_globs:
            errors.append(f"{entry.model_id}: input_globs must not be empty")
        elif entry.distribution_policy == "required_public":
            unresolved_patterns = tuple(
                pattern
                for pattern in entry.input_globs
                if not any(path.is_file() for path in root_path.glob(pattern))
            )
            errors.extend(
                f"{entry.model_id}: input_glob resolves no files: {pattern}"
                for pattern in unresolved_patterns
            )
        intent_paths = tuple(entry.intent_source_inputs)
        duplicate_intent_paths = tuple(
            sorted(
                path
                for path in set(intent_paths)
                if intent_paths.count(path) > 1
            )
        )
        errors.extend(
            f"{entry.model_id}: duplicate intent_source_input: {path}"
            for path in duplicate_intent_paths
        )
        for intent_path in intent_paths:
            normalized = intent_path.replace("\\", "/")
            pure = PurePosixPath(normalized)
            windows = PureWindowsPath(intent_path)
            if (
                not intent_path
                or intent_path != normalized
                or intent_path.startswith(("/", "\\"))
                or pure.is_absolute()
                or windows.is_absolute()
                or bool(windows.drive)
                or ".." in pure.parts
                or any(token in intent_path for token in ("*", "?", "[", "]"))
            ):
                errors.append(
                    f"{entry.model_id}: unsafe intent_source_input: {intent_path}"
                )
                continue
            resolved_intent = (root_path / Path(*pure.parts)).resolve()
            try:
                resolved_intent.relative_to(root_path)
            except ValueError:
                errors.append(
                    f"{entry.model_id}: intent_source_input escapes repository: {intent_path}"
                )
                continue
            if (
                entry.distribution_policy == "required_public"
                and not resolved_intent.is_file()
            ):
                errors.append(
                    f"{entry.model_id}: intent_source_input is not a file: {intent_path}"
                )
        if entry.excluded:
            if entry.runner:
                errors.append(f"{entry.model_id}: excluded entry must not define a runner")
            if len(entry.exclusion_reason.strip()) < 12:
                errors.append(f"{entry.model_id}: exclusion reason is not reviewable")
        else:
            if not entry.runner:
                errors.append(f"{entry.model_id}: missing runner")
            elif len(entry.runner) < 2 or entry.runner[0] != "{python}":
                errors.append(f"{entry.model_id}: runner must start with {{python}} and a repository-relative script")
            else:
                runner_path = root_path / entry.runner[1]
                if not runner_path.is_file() and entry.distribution_policy == "required_public":
                    errors.append(f"{entry.model_id}: runner does not exist: {entry.runner[1]}")
                elif purpose is not None and (root_path / entry.model_path).is_file() and runner_path.is_file():
                    try:
                        purpose.validate_current_files(root_path, model_path=entry.model_path, runner_path=entry.runner[1])
                    except ModelPurposeError as exc:
                        errors.append(f"{entry.model_id}: {exc}")
    return ManifestAudit(not errors, discovered, registered, tuple(errors))


def parse_shard(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        number_text, total_text = value.split("/", 1)
        number, total = int(number_text), int(total_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError("shard must use N/M with 1 <= N <= M") from exc
    if number < 1 or total < 1 or number > total:
        raise ValueError("shard must use N/M with 1 <= N <= M")
    return number, total


def select_entries(
    manifest: ModelRegressionManifest,
    *,
    tier: str,
    model_patterns: Sequence[str] = (),
    shard: str | None = None,
) -> tuple[ModelRegressionEntry, ...]:
    if tier not in TIER_RANK:
        raise ValueError(f"unsupported tier: {tier}")
    root = manifest.path.parents[1]
    selected = [
        entry
        for entry in manifest.entries
        if not entry.excluded and TIER_RANK[entry.tier] <= TIER_RANK[tier]
        and (root / entry.model_path).is_file()
        and len(entry.runner) >= 2
        and (root / entry.runner[1]).is_file()
    ]
    if model_patterns:
        selected = [
            entry
            for entry in selected
            if any(fnmatch.fnmatchcase(entry.model_id, pattern) for pattern in model_patterns)
        ]
    selected.sort(key=lambda item: item.model_id)
    parsed = parse_shard(shard)
    if parsed:
        number, total = parsed
        selected = [entry for index, entry in enumerate(selected) if index % total == number - 1]
    return tuple(selected)


def _safe_artifact_dir(output_dir: Path, model_id: str) -> Path:
    digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:10]
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in model_id)
    path = (output_dir / f"{safe_name}-{digest}").resolve()
    if output_dir.resolve() not in path.parents:
        raise ValueError(f"unsafe model artifact path: {model_id}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _shard_safety_proof_dir(output_dir: Path, model_id: str) -> Path:
    """Keep nested shard-proof paths bounded while receipts retain model ids."""

    proof_root = (output_dir / "shard-safety").resolve()
    digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:16]
    path = (proof_root / f"p-{digest}").resolve()
    if proof_root not in path.parents:
        raise ValueError(f"unsafe shard-safety proof path: {model_id}")
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_entry_input_inventory(
    root: str | Path,
    entry: ModelRegressionEntry,
) -> tuple[dict[str, str], ...]:
    """Resolve manifest selectors to the exact immutable input inventory."""

    root_path = Path(root).resolve()
    inventory: dict[str, str] = {}
    for pattern in entry.effective_input_patterns:
        for path in root_path.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ModelRegressionManifestError(
                    f"{entry.model_id}: input resolves outside repository: {path}"
                ) from exc
            inventory[relative] = source_file_fingerprint(resolved)
    return tuple(
        {"path": path, "sha256": inventory[path]}
        for path in sorted(inventory)
    )


def input_inventory_fingerprint(
    inventory: Sequence[Mapping[str, str]],
) -> str:
    encoded = json.dumps(
        [dict(item) for item in inventory],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_fingerprints(paths: Sequence[str]) -> dict[str, str]:
    return {
        str(index): _file_sha256(Path(path))
        for index, path in enumerate(paths)
        if Path(path).is_file()
    }


def build_regression_model_instance(
    root: str | Path,
    entry: ModelRegressionEntry,
    inventory: Sequence[Mapping[str, str]],
) -> ModelInstanceRef:
    """Build the canonical model instance used by snapshots and receipts."""

    root_path = Path(root).resolve()
    runner_path = entry.runner[1] if len(entry.runner) >= 2 else ""
    if entry.purpose_closure is None:
        raise ModelRegressionManifestError(
            f"{entry.model_id}: canonical model instance requires purpose closure"
        )
    return build_model_instance_ref(
        root_path,
        logical_model_id=entry.model_id,
        model_kind=entry.model_kind,
        model_path=entry.model_path,
        runner_path=runner_path,
        purpose_closure_fingerprint=(
            entry.purpose_closure.closure_fingerprint
        ),
        input_paths=tuple(item["path"] for item in inventory),
    )


def model_instance_fingerprint(
    root: str | Path,
    entry: ModelRegressionEntry,
    inventory: Sequence[Mapping[str, str]],
) -> str:
    """Compatibility-free projection of the canonical instance fingerprint."""

    return build_regression_model_instance(root, entry, inventory).fingerprint


def _run_entry(
    root: Path,
    entry: ModelRegressionEntry,
    output_dir: Path,
    *,
    timeout_override: float | None,
    cancel_event: threading.Event,
    progress: ProgressCallback | None,
) -> ModelRunResult:
    started = time.monotonic()
    input_inventory = resolve_entry_input_inventory(root, entry)
    inventory_fingerprint = input_inventory_fingerprint(input_inventory)
    instance = build_regression_model_instance(
        root,
        entry,
        input_inventory,
    )
    instance_fingerprint = instance.fingerprint
    artifact_dir = _safe_artifact_dir(output_dir, entry.model_id)
    command = entry.command(root=root)
    timeout = timeout_override if timeout_override is not None else entry.timeout_seconds
    if progress:
        progress({"event": "started", "model_id": entry.model_id, "timeout_seconds": timeout})
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    source_pythonpath = str(root)
    if existing_pythonpath:
        source_pythonpath = source_pythonpath + os.pathsep + existing_pythonpath
    env.update(
        {
            "FLOWGUARD_OUTPUT_DIR": str(artifact_dir),
            "FLOWGUARD_MODEL_ID": entry.model_id,
            # Model runners validate the selected repository snapshot, not an
            # unrelated editable/wheel installation that happens to be active
            # in the launching Python environment.
            "PYTHONPATH": source_pythonpath,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    status = VALIDATION_STATUS_INTERNAL_ERROR
    finding_codes: tuple[str, ...] = ("model.internal_error",)
    message = "model runner did not reach a terminal state"
    supervised = None
    try:
        supervised = run_supervised(
            command,
            cwd=root,
            environment=env,
            timeout_seconds=timeout,
            cancel_event=cancel_event,
        )
        stdout = supervised.stdout
        stderr = supervised.stderr
        exit_code = supervised.exit_code
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_terminal_artifact(
            artifact_dir / "supervisor-terminal.json",
            supervised,
        )
        if not supervised.cleanup_confirmed:
            status = VALIDATION_STATUS_INTERNAL_ERROR
            finding_codes = ("model.cleanup_unconfirmed",)
            message = "runner process-tree cleanup could not be confirmed"
        elif supervised.cancelled or supervised.interrupted:
            status = VALIDATION_STATUS_CANCELLED
            finding_codes = ("model.cancelled",)
            message = "cancelled after confirmed process-tree cleanup"
        elif supervised.timed_out:
            status = VALIDATION_STATUS_TIMEOUT
            finding_codes = ("model.timeout",)
            message = f"runner exceeded {timeout:g} seconds and its process tree was terminated"
        elif exit_code == 0:
            status = VALIDATION_STATUS_PASS
            finding_codes = ()
            message = "runner and its contained process tree completed successfully"
        else:
            status = VALIDATION_STATUS_FAIL
            finding_codes = ("model.nonzero_exit",)
            message = f"runner exited with code {exit_code}"
    except (OSError, ValueError) as exc:
        status = VALIDATION_STATUS_INTERNAL_ERROR
        finding_codes = ("model.launch_error",)
        message = str(exc)
        stderr = repr(exc)
    # The orchestrator owns its stdout/stderr/receipt directory. A child may
    # legitimately replace its isolated FLOWGUARD_OUTPUT_DIR while producing
    # artifacts, so restore the parent-owned directory before retaining logs.
    artifact_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_tail_chars = 0 if status == VALIDATION_STATUS_PASS else 4000
    stdout_descriptor = store_text_object(
        output_dir,
        stdout,
        tail_chars=diagnostic_tail_chars,
    )
    stderr_descriptor = store_text_object(
        output_dir,
        stderr,
        tail_chars=diagnostic_tail_chars,
    )
    stdout_path = (output_dir / str(stdout_descriptor["object_path"])).resolve()
    stderr_path = (output_dir / str(stderr_descriptor["object_path"])).resolve()
    expected_paths = tuple(str((artifact_dir / item).resolve()) for item in entry.expected_artifacts)
    missing = tuple(path for path in expected_paths if not Path(path).exists())
    if status == VALIDATION_STATUS_PASS and missing:
        status = VALIDATION_STATUS_FAIL
        finding_codes = ("model.expected_artifact_missing",)
        message = "missing expected artifacts: " + ", ".join(missing)
    elapsed_seconds = round(time.monotonic() - started, 3)
    result = ModelRunResult(
        model_id=entry.model_id,
        status=status,
        exit_code=exit_code,
        seconds=elapsed_seconds,
        command=command,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        receipt_path="",
        artifact_paths=expected_paths,
        finding_codes=finding_codes,
        message=message,
        model_instance_id=entry.purpose_closure.model_instance_id if entry.purpose_closure else "",
        model_kind=instance.model_kind,
        model_instance_fingerprint=instance_fingerprint,
        input_inventory_fingerprint=inventory_fingerprint,
        input_inventory=input_inventory,
        artifact_fingerprints=_artifact_fingerprints(expected_paths),
        purpose_closure_fingerprint=(entry.purpose_closure.closure_fingerprint if entry.purpose_closure else ""),
        purpose_claim_boundary=entry.purpose_closure.claim_boundary if entry.purpose_closure else "",
        stdout=stdout_descriptor,
        stderr=stderr_descriptor,
        supervision=supervised,
    )
    if progress:
        progress({"event": "finished", "model_id": entry.model_id, "status": status, "seconds": elapsed_seconds})
    return result


def _tracked_paths(root: Path) -> tuple[Path, ...]:
    git = shutil.which("git")
    if not git:
        return ()
    try:
        completed = subprocess.run(
            [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return ()
    if completed.returncode != 0:
        return ()
    return tuple(
        root / item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    )


def _snapshot(paths: Sequence[Path]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in paths:
        key = str(path.resolve())
        if not path.is_file():
            snapshot[key] = "<missing>"
            continue
        snapshot[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _mutation_paths(before: Mapping[str, str], after: Mapping[str, str], root: Path) -> tuple[str, ...]:
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    values: list[str] = []
    for item in changed:
        try:
            values.append(Path(item).relative_to(root).as_posix())
        except ValueError:
            values.append(item)
    return tuple(values)


def _model_owner_contract(
    root: Path,
    manifest: ModelRegressionManifest,
    entry: ModelRegressionEntry,
) -> ValidationOwnerContract:
    return ValidationOwnerContract(
        owner_id=f"model:{entry.model_id}",
        command=entry.command(root=root),
        input_patterns=tuple(
            dict.fromkeys(
                (
                    *entry.effective_input_patterns,
                    *(
                        pattern
                        for pattern in manifest.shared_patterns_for(
                            entry.model_id
                        )
                        if pattern
                        != ".flowguard/model-regression-manifest.json"
                    ),
                )
            )
        ),
        obligation_ids=(f"model-regression:{entry.model_id}",),
        projected_inputs=(
            (
                f"model-regression-manifest:{entry.model_id}",
                manifest.owner_projection_fingerprint(entry),
            ),
        ),
    )


def _model_parent_owner_contract(
    manifest: ModelRegressionManifest,
    entries: Sequence[ModelRegressionEntry],
    *,
    claim_scope: str,
    tier: str,
) -> ValidationOwnerContract:
    """Return the exact composition contract for one model parent run.

    The tier and claim scope are projected into the native contract even when
    two selections happen to contain the same model ids.  A scoped execution
    therefore cannot be relabeled as a full parent by rewriting its wrapper.
    """

    selected_model_ids = tuple(entry.model_id for entry in entries)
    selection_fingerprint = fingerprint_value(
        {
            "manifest_sha256": source_file_fingerprint(manifest.path),
            "selected_model_ids": list(selected_model_ids),
            "claim_scope": claim_scope,
            "tier": tier,
        }
    )
    return ValidationOwnerContract(
        owner_id="model-regression-parent",
        command=(
            "flowguard-model-regression-parent",
            "--tier",
            tier,
            "--claim-scope",
            claim_scope,
        ),
        input_patterns=(
            ".flowguard/model-regression-manifest.json",
            "flowguard/model_regressions.py",
            "flowguard/evidence_receipts.py",
            "flowguard/validation_ownership.py",
        ),
        projected_inputs=(
            ("model-parent-selection", selection_fingerprint),
        ),
        obligation_ids=(
            f"model-regression-parent:{selection_fingerprint}",
        ),
        resource_keys=("model-regression-parent",),
    )


def _model_result_from_reused_child(
    entry: ModelRegressionEntry,
    child: ValidationChildResult,
) -> ModelRunResult:
    raw = child.payload.get("model_result")
    if not isinstance(raw, Mapping):
        raise ValueError(f"model receipt proof is missing result: {entry.model_id}")
    return ModelRunResult(
        model_id=entry.model_id,
        status=str(raw.get("status", "")),
        exit_code=raw.get("exit_code"),
        seconds=0.0,
        command=tuple(str(item) for item in raw.get("command", ())),
        stdout_path=str(raw.get("stdout_path", "")),
        stderr_path=str(raw.get("stderr_path", "")),
        receipt_path=child.receipt_id,
        artifact_paths=tuple(str(item) for item in raw.get("artifact_paths", ())),
        finding_codes=tuple(str(item) for item in raw.get("finding_codes", ())),
        message="reused independently verified exact-current terminal receipt",
        model_instance_id=str(raw.get("model_instance_id", "")),
        model_kind=str(raw.get("model_kind", "")),
        model_instance_fingerprint=str(raw.get("model_instance_fingerprint", "")),
        input_inventory_fingerprint=str(raw.get("input_inventory_fingerprint", "")),
        input_inventory=tuple(
            dict(item) for item in raw.get("input_inventory", ())
            if isinstance(item, Mapping)
        ),
        artifact_fingerprints=dict(raw.get("artifact_fingerprints", {})),
        purpose_closure_fingerprint=str(raw.get("purpose_closure_fingerprint", "")),
        purpose_claim_boundary=str(raw.get("purpose_claim_boundary", "")),
        stdout=dict(raw.get("stdout", {})),
        stderr=dict(raw.get("stderr", {})),
        execution_disposition=OWNER_REUSE_CURRENT,
        producer_invocations=0,
        receipt_fingerprint=str(
            child.payload.get("owner_receipt_fingerprint", "")
        ),
    )


def _persist_model_owner_result(
    root: Path,
    receipt_root: Path,
    current: Any,
    result: ModelRunResult,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    started_at: str,
    source_freshness: ValidationObservationFreshness,
) -> ModelRunResult:
    child = ValidationChildResult(
        child_id=current.contract.owner_id,
        status=result.status,
        summary=result.message,
        receipt_id=Path(result.receipt_path).name,
        artifact_paths=(
            result.stdout_path,
            result.stderr_path,
            *(item for item in (result.receipt_path,) if item),
            *result.artifact_paths,
        ),
        claim_boundary=(
            result.purpose_claim_boundary
            or "One manifest-owned model runner and its exact declared inputs."
        ),
        payload={"model_result": result.to_dict()},
    )
    if result.status == VALIDATION_STATUS_PASS:
        if result.supervision is None:
            raise ValueError(
                f"passing model owner lacks supervised producer evidence: {result.model_id}"
            )
        publication = publish_supervised_validation_owner_result(
            current,
            result.supervision,
            root,
            receipt_root,
            all_contracts=all_contracts,
            child_id=child.child_id,
            evidence_context={"model_result": result.to_dict()},
            summary=child.summary,
            claim_boundary=child.claim_boundary,
            source_freshness=source_freshness,
        )
        if not publication.ok or publication.receipt is None:
            raise ValueError(
                f"passing model owner publication blocked: {publication.blocker}"
            )
        receipt = publication.receipt
    else:
        receipt = record_validation_owner_nonpass(
            current,
            child,
            root,
            receipt_root,
            all_contracts=all_contracts,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    path = evidence_receipt_path(
        receipt.receipt_id,
        root,
        output_directory=receipt_root,
    )
    return replace(
        result,
        receipt_path=str(path),
        execution_disposition=OWNER_EXECUTE,
        producer_invocations=1,
        receipt_fingerprint=receipt.fingerprint,
    )


def _execute_pending_models(
    *,
    root_path: Path,
    pending: Sequence[ModelRegressionEntry],
    jobs: int,
    timeout: float | None,
    output_path: Path,
    receipt_root: Path,
    currents: Mapping[str, Any],
    contracts: Sequence[ValidationOwnerContract],
    planning_observation: ValidationOwnerObservation,
    cancel: threading.Event,
    progress: ProgressCallback | None,
) -> tuple[list[ModelRunResult], ValidationObservationFreshness]:
    """Preflight every model resource lease, then execute the frozen set."""

    results: list[ModelRunResult] = []
    lease_payloads: dict[str, dict[str, Any]] = {}
    with ExitStack() as leases:
        for entry in pending:
            owner_id = f"model:{entry.model_id}"
            current = currents[owner_id]
            lease_payloads[entry.model_id] = leases.enter_context(
                evidence_execution_lease(
                    receipt_root / "leases",
                    owner_id=owner_id,
                    resource_key=owner_id,
                    execution_key=current.owner_identity,
                    plan_id=f"model-owner-plan:{current.owner_identity}",
                )
            )

        if jobs > 1:
            from .shard_safety import prove_model_shard_safety

            for entry in pending:
                if not entry.shard_safety_proof:
                    continue
                proof_dir = _shard_safety_proof_dir(output_path, entry.model_id)
                proof = prove_model_shard_safety(
                    root_path,
                    entry,
                    output_dir=proof_dir,
                )
                if not proof["ok"]:
                    raise ValueError(
                        f"parallel execution proof failed for {entry.model_id}; "
                        f"see {proof_dir / 'result.json'}"
                    )

        if jobs == 1:
            completed: list[tuple[ModelRegressionEntry, str, ModelRunResult]] = []
            for entry in pending:
                owner_started_at = datetime.now(timezone.utc).isoformat()
                result = _run_entry(
                    root_path,
                    entry,
                    output_path,
                    timeout_override=timeout,
                    cancel_event=cancel,
                    progress=progress,
                )
                completed.append((entry, owner_started_at, result))
                if cancel.is_set():
                    break
        else:
            completed = []
            with ThreadPoolExecutor(
                max_workers=jobs,
                thread_name_prefix="flowguard-model",
            ) as executor:
                futures = {
                    executor.submit(
                        _run_entry,
                        root_path,
                        entry,
                        output_path,
                        timeout_override=timeout,
                        cancel_event=cancel,
                        progress=progress,
                    ): (
                        entry,
                        datetime.now(timezone.utc).isoformat(),
                    )
                    for entry in pending
                }
                for future in as_completed(futures):
                    entry, owner_started_at = futures[future]
                    completed.append((entry, owner_started_at, future.result()))

        source_freshness = assert_validation_owner_observation_fresh(
            planning_observation,
            root_path,
            receipt_root,
        )
        fresh_currents = source_freshness.current_by_owner
        for entry, owner_started_at, result in completed:
            if "model.cleanup_unconfirmed" in result.finding_codes:
                lease = lease_payloads[entry.model_id]
                lease["_preserve_residual"] = True
                terminal_path = (
                    _safe_artifact_dir(output_path, entry.model_id)
                    / "supervisor-terminal.json"
                )
                if terminal_path.is_file():
                    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
                    lease["incident_episode_token"] = str(
                        terminal.get("episode_token", lease["lease_token"])
                    )
                continue
            results.append(
                _persist_model_owner_result(
                    root_path,
                    receipt_root,
                    fresh_currents[f"model:{entry.model_id}"],
                    result,
                    all_contracts=contracts,
                    started_at=owner_started_at,
                    source_freshness=source_freshness,
                )
            )
    return results, source_freshness


def _write_model_parent_receipt(
    root: Path,
    manifest: ModelRegressionManifest,
    receipt_root: Path,
    report: ModelRegressionReport,
    *,
    planning_observation: ValidationOwnerObservation,
    source_freshness: ValidationObservationFreshness,
) -> tuple[
    str,
    str,
    ValidationOwnerObservation,
    ValidationObservationFreshness,
    float,
]:
    """Compose exact child-owner receipts into one scoped/full model parent."""

    composition_started_at = time.perf_counter()

    children: list[dict[str, str]] = []
    loaded_children: dict[str, EvidenceReceipt] = {}
    for result in report.results:
        if not result.receipt_path or not result.receipt_fingerprint:
            continue
        path = (
            evidence_receipt_path(
                result.receipt_path,
                root,
                output_directory=receipt_root,
            )
            if result.receipt_path.startswith("receipt:")
            else Path(result.receipt_path)
        )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"model parent child receipt is unreadable: {result.model_id}"
            ) from exc
        child_receipt = EvidenceReceipt.from_dict(payload)
        if child_receipt.fingerprint != result.receipt_fingerprint:
            raise ValueError(
                f"model parent child fingerprint changed: {result.model_id}"
            )
        if child_receipt.subject_id != f"validation-owner:model:{result.model_id}":
            raise ValueError(
                f"model parent child subject changed: {result.model_id}"
            )
        loaded_children[result.model_id] = child_receipt
        children.append(
            {
                "model_id": result.model_id,
                "receipt_id": child_receipt.receipt_id,
                "receipt_fingerprint": result.receipt_fingerprint,
            }
        )
    children.sort(key=lambda row: row["model_id"])
    execution_receipt_id = ""
    execution_receipt_fingerprint = ""
    composition_observation = planning_observation
    freshness = ValidationObservationFreshness.not_run(planning_observation)
    if report.ok:
        entries_by_id = {entry.model_id: entry for entry in manifest.entries}
        try:
            selected_entries = tuple(
                entries_by_id[model_id]
                for model_id in report.selected_model_ids
            )
        except KeyError as exc:
            raise ValueError(
                f"passing model parent selects an unknown model: {exc.args[0]}"
            ) from exc
        child_contracts = tuple(
            _model_owner_contract(root, manifest, entry)
            for entry in selected_entries
        )
        if child_contracts != planning_observation.contracts:
            raise ValueError(
                "model parent selection differs from the frozen owner observation"
            )
        composition_observation = refresh_validation_owner_observation_receipts(
            planning_observation,
            root,
            receipt_root,
            tuple(loaded_children[entry.model_id] for entry in selected_entries),
        )
        rows = composition_observation.rows
        child_currents = composition_observation.current_by_owner
        reusable = composition_observation.receipt_by_owner
        observed_verifications = composition_observation.verification_by_owner
        noncurrent = tuple(
            row.owner_id
            for row in rows
            if row.disposition != OWNER_REUSE_CURRENT
        )
        if noncurrent:
            raise ValueError(
                "passing model parent child evidence is not exact-current: "
                + ", ".join(noncurrent)
        )
        exact_children: list[EvidenceReceipt] = []
        child_verifications: list[ReceiptVerificationResult] = []
        for entry in selected_entries:
            owner_id = f"model:{entry.model_id}"
            child = reusable[owner_id]
            loaded = loaded_children.get(entry.model_id)
            if loaded is None or loaded.fingerprint != child.fingerprint:
                raise ValueError(
                    f"passing model parent child changed: {entry.model_id}"
                )
            verification = observed_verifications[owner_id]
            if not verification.ok:
                raise ValueError(
                    f"passing model parent child is not current: {entry.model_id}"
                )
            exact_children.append(child)
            child_verifications.append(verification)

        parent_contract = _model_parent_owner_contract(
            manifest,
            selected_entries,
            claim_scope=report.parent_claim_scope,
            tier=report.tier,
        )
        parent_current = build_owner_current_from_observation(
            root,
            parent_contract,
            all_contracts=(parent_contract,),
            observation=composition_observation,
        )
        freshness = assert_validation_owner_observation_receipts_fresh(
            planning_observation,
            composition_observation,
            source_freshness,
            root,
            receipt_root,
            additional_receipt_subject_ids=(
                "validation-owner:model-regression-parent",
            ),
        )

        if (
            report.parent_claim_scope == "full"
            and report.tier == "full"
            and not report.skipped_model_ids
        ):
            manifest_fingerprint = source_file_fingerprint(manifest.path)
            parent_dir = receipt_root / "model-parents"
            report_child_identities = {
                (
                    model_id,
                    receipt.receipt_id,
                    receipt.fingerprint,
                )
                for model_id, receipt in loaded_children.items()
            }
            matching_current_wrappers: list[
                tuple[Path, Mapping[str, Any]]
            ] = []
            for candidate_path in _current_model_parent_artifact_paths(
                parent_dir
            ):
                (
                    candidate_payload,
                    candidate_selected,
                    candidate_skipped,
                    _candidate_children,
                ) = _read_model_parent_artifact(candidate_path)
                if (
                    candidate_payload["claim_scope"] == "full"
                    and candidate_payload["tier"] == "full"
                    and candidate_payload["status"] == RECEIPT_STATUS_PASS
                    and candidate_payload["manifest_sha256"]
                    == manifest_fingerprint
                    and candidate_selected
                    == tuple(report.selected_model_ids)
                    and not candidate_skipped
                    and {
                        (
                            row["model_id"],
                            row["receipt_id"],
                            row["receipt_fingerprint"],
                        )
                        for row in _candidate_children
                    }
                    == report_child_identities
                ):
                    matching_current_wrappers.append(
                        (candidate_path, candidate_payload)
                    )
            if matching_current_wrappers:
                verified_wrappers: list[tuple[Path, Mapping[str, Any]]] = []
                for candidate_path, candidate_payload in matching_current_wrappers:
                    try:
                        execution = load_evidence_receipt(
                            str(candidate_payload["execution_receipt_id"]),
                            root,
                            output_directory=receipt_root,
                        )
                        _assert_owner_receipt_integrity(execution)
                    except (OSError, ValueError) as exc:
                        raise ValueError(
                            "matching model parent execution receipt is invalid: "
                            f"{candidate_path.name}: {exc}"
                        ) from exc
                    if execution.fingerprint != str(
                        candidate_payload["execution_receipt_fingerprint"]
                    ):
                        raise ValueError(
                            "matching model parent execution fingerprint changed: "
                            + candidate_path.name
                        )
                    context = build_child_bound_owner_receipt_context(
                        parent_current,
                        execution,
                        root,
                        receipt_root,
                        child_receipts=tuple(exact_children),
                        child_verification_results=tuple(child_verifications),
                    )
                    result = verify_evidence_receipt(execution, context)
                    if result.ok:
                        verified_wrappers.append(
                            (candidate_path, candidate_payload)
                        )
                    elif result.status != VERIFICATION_STATUS_STALE:
                        raise ValueError(
                            "matching model parent execution is invalid: "
                            + ", ".join(item.code for item in result.findings)
                        )
                if len(verified_wrappers) > 1:
                    raise ValueError(
                        "ambiguous exact-current full model parent artifacts: "
                        + ", ".join(path.name for path, _payload in verified_wrappers)
                    )
                if verified_wrappers:
                    current_path, current_payload = verified_wrappers[0]
                    return (
                        str(current_path),
                        str(current_payload["parent_receipt_fingerprint"]),
                        composition_observation,
                        freshness,
                        max(0.0, time.perf_counter() - composition_started_at),
                    )

        parent_execution, parent_verification = (
            save_child_bound_owner_receipt_from_observation(
            parent_current,
            tuple(f"model:{entry.model_id}" for entry in selected_entries),
            root,
            receipt_root,
            observation=composition_observation,
            freshness=freshness,
            started_at=datetime.fromtimestamp(
                report.started_at_epoch,
                tz=timezone.utc,
            ).isoformat(),
            finished_at=datetime.fromtimestamp(
                report.finished_at_epoch,
                tz=timezone.utc,
            ).isoformat(),
            evidence_context={
                "manifest_sha256": source_file_fingerprint(manifest.path),
                "selected_model_ids": list(report.selected_model_ids),
                "skipped_model_ids": list(report.skipped_model_ids),
                "claim_scope": report.parent_claim_scope,
                "tier": report.tier,
                "status": report.status,
            },
            claim_boundary=(
                "One exact model-regression parent composition over the named "
                "tier, selection, and canonical child receipts."
            ),
        ))
        if not parent_verification.ok:
            raise ValueError(
                "saved model parent execution receipt is not exact-current"
            )
        execution_receipt_id = parent_execution.receipt_id
        execution_receipt_fingerprint = parent_execution.fingerprint

    payload: dict[str, Any] = {
        "artifact_type": MODEL_REGRESSION_PARENT_ARTIFACT_TYPE,
        "schema_version": MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA,
        "claim_scope": report.parent_claim_scope,
        "tier": report.tier,
        "status": report.status,
        "manifest_sha256": source_file_fingerprint(manifest.path),
        "selected_model_ids": list(report.selected_model_ids),
        "skipped_model_ids": list(report.skipped_model_ids),
        "children": children,
        "execution_receipt_id": execution_receipt_id,
        "execution_receipt_fingerprint": execution_receipt_fingerprint,
        "claim_boundary": (
            "Full model-regression confidence over the exact current manifest."
            if report.parent_claim_scope == "full"
            else (
                "Scoped model-regression evidence only; this parent cannot "
                "support release or full-model confidence."
            )
        ),
    }
    identity = fingerprint_value(payload)
    payload["parent_receipt_fingerprint"] = identity
    parent_dir = receipt_root / "model-parents"
    parent_dir.mkdir(parents=True, exist_ok=True)
    path = parent_dir / (identity.split(":", 1)[1] + ".json")
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("content-addressed model parent receipt collision")
    if not path.exists():
        path.write_bytes(encoded)
    if (
        len(children) != len(report.selected_model_ids)
        or tuple(row["model_id"] for row in children)
        != tuple(sorted(report.selected_model_ids))
    ):
        if report.ok:
            raise ValueError("passing model parent does not compose every selected owner")
    return (
        str(path),
        identity,
        composition_observation,
        freshness,
        max(0.0, time.perf_counter() - composition_started_at),
    )


def _reject_duplicate_model_parent_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelRegressionEvidenceError(
                f"duplicate model parent JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite_model_parent_number(value: str) -> Any:
    raise ModelRegressionEvidenceError(
        f"non-finite model parent JSON number: {value}"
    )


def _model_parent_string_array(
    value: Any,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ModelRegressionEvidenceError(
            f"model parent {field_name} must be an array of non-empty strings"
        )
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ModelRegressionEvidenceError(
            f"model parent {field_name} must not contain duplicates"
        )
    return result


def _model_parent_children(
    value: Any,
) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ModelRegressionEvidenceError(
            "model parent children must be an array"
        )
    rows: list[Mapping[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ModelRegressionEvidenceError(
                f"model parent child {index} must be an object"
            )
        if set(item) != _MODEL_REGRESSION_PARENT_CHILD_FIELDS:
            raise ModelRegressionEvidenceError(
                "model parent child fields do not match the current schema"
            )
        if any(
            not isinstance(item[name], str) or not item[name]
            for name in _MODEL_REGRESSION_PARENT_CHILD_FIELDS
        ):
            raise ModelRegressionEvidenceError(
                "model parent child fields must be non-empty strings"
            )
        rows.append(
            {name: item[name] for name in _MODEL_REGRESSION_PARENT_CHILD_FIELDS}
        )
    model_ids = tuple(row["model_id"] for row in rows)
    if len(model_ids) != len(set(model_ids)):
        raise ModelRegressionEvidenceError(
            "model parent children must identify unique models"
        )
    return tuple(rows)


def _current_model_parent_artifact_paths(parent_dir: Path) -> tuple[Path, ...]:
    """Return current-format authority candidates, excluding retired history.

    This is schema classification only, not a legacy reader: v1 artifacts remain
    immutable historical evidence and are never parsed as current authority.  Any
    malformed or unknown-format artifact in the active store remains a visible
    blocker.
    """

    current: list[Path] = []
    for path in sorted(parent_dir.glob("*.json")) if parent_dir.is_dir() else ():
        try:
            header = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_model_parent_keys,
                parse_constant=_reject_nonfinite_model_parent_number,
            )
        except (OSError, json.JSONDecodeError, ModelRegressionEvidenceError) as exc:
            raise ModelRegressionEvidenceError(
                f"cannot classify model parent artifact {path.name}: {exc}"
            ) from exc
        if not isinstance(header, Mapping) or not isinstance(
            header.get("schema_version"), str
        ):
            raise ModelRegressionEvidenceError(
                f"model parent artifact has no schema identity: {path.name}"
            )
        schema_version = header["schema_version"]
        if schema_version == MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA:
            current.append(path)
        elif schema_version == "flowguard.model_regression_parent_receipt.v1":
            continue
        else:
            raise ModelRegressionEvidenceError(
                "unknown model parent schema remains in the active store: "
                f"{path.name}"
            )
    return tuple(current)


def _read_model_parent_artifact(
    path: Path,
) -> tuple[
    Mapping[str, Any],
    tuple[str, ...],
    tuple[str, ...],
    tuple[Mapping[str, str], ...],
]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_model_parent_keys,
            parse_constant=_reject_nonfinite_model_parent_number,
        )
    except (OSError, json.JSONDecodeError, ModelRegressionEvidenceError) as exc:
        raise ModelRegressionEvidenceError(
            f"cannot load model parent artifact {path.name}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ModelRegressionEvidenceError(
            f"model parent artifact must be an object: {path.name}"
        )
    if set(payload) != _MODEL_REGRESSION_PARENT_FIELDS:
        missing = sorted(_MODEL_REGRESSION_PARENT_FIELDS - set(payload))
        unknown = sorted(set(payload) - _MODEL_REGRESSION_PARENT_FIELDS)
        raise ModelRegressionEvidenceError(
            "model parent artifact fields do not match the current schema: "
            f"missing={missing}, unknown={unknown}"
        )
    for field_name in (
        "artifact_type",
        "schema_version",
        "claim_scope",
        "tier",
        "status",
        "manifest_sha256",
        "execution_receipt_id",
        "execution_receipt_fingerprint",
        "claim_boundary",
        "parent_receipt_fingerprint",
    ):
        if not isinstance(payload[field_name], str):
            raise ModelRegressionEvidenceError(
                f"model parent {field_name} must be a string"
            )
    if payload["artifact_type"] != MODEL_REGRESSION_PARENT_ARTIFACT_TYPE:
        raise ModelRegressionEvidenceError(
            f"unexpected artifact in model parent store: {path.name}"
        )
    if payload["schema_version"] != MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA:
        raise ModelRegressionEvidenceError(
            f"non-current model parent schema remains in store: {path.name}"
        )
    selected_ids = _model_parent_string_array(
        payload["selected_model_ids"],
        "selected_model_ids",
    )
    skipped_ids = _model_parent_string_array(
        payload["skipped_model_ids"],
        "skipped_model_ids",
    )
    children = _model_parent_children(payload["children"])
    declared_fingerprint = payload["parent_receipt_fingerprint"]
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key != "parent_receipt_fingerprint"
    }
    if fingerprint_value(identity_payload) != declared_fingerprint:
        raise ModelRegressionEvidenceError(
            f"model parent artifact fingerprint is stale: {path.name}"
        )
    if not declared_fingerprint.startswith("sha256:"):
        raise ModelRegressionEvidenceError(
            f"model parent artifact fingerprint is malformed: {path.name}"
        )
    expected_name = declared_fingerprint.split(":", 1)[1] + ".json"
    if path.name != expected_name:
        raise ModelRegressionEvidenceError(
            f"model parent artifact filename does not match identity: {path.name}"
        )
    return payload, selected_ids, skipped_ids, children


def _exact_model_result_identity(
    raw: Mapping[str, Any],
    field_name: str,
    expected: str,
    *,
    model_id: str,
) -> str:
    value = raw.get(field_name)
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or value != expected:
        raise ModelRegressionEvidenceError(
            f"model child result {field_name} is not current: {model_id}"
        )
    return value


def resolve_current_full_model_regression_parent(
    root: str | Path = ".",
    *,
    receipt_dir: str | Path | None = None,
) -> CurrentModelRegressionParentEvidence:
    """Resolve one unique, exact-current full model parent without executing.

    Historical parent artifacts are retained, but only an exact current-format
    ``full/full/pass`` artifact with zero skipped models and the complete
    current manifest selection is eligible.  The aggregate never substitutes
    for its leaves: every model owner receipt is independently rediscovered,
    verified against its current contract, and then supplied to the parent
    verification context as a real child.
    """

    root_path = Path(root).resolve()
    receipt_root = (
        Path(receipt_dir).resolve()
        if receipt_dir is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    manifest = ModelRegressionManifest.load(root_path)
    audit = audit_manifest(root_path, manifest)
    if not audit.ok:
        raise ModelRegressionEvidenceError(
            "current model-regression manifest is invalid: "
            + "; ".join(audit.errors)
        )
    entries = select_entries(manifest, tier="full")
    selected_ids = tuple(entry.model_id for entry in entries)
    manifest_fingerprint = source_file_fingerprint(manifest.path)
    parent_dir = receipt_root / "model-parents"
    candidates: list[
        tuple[
            Path,
            Mapping[str, Any],
            tuple[Mapping[str, str], ...],
        ]
    ] = []
    for path in _current_model_parent_artifact_paths(parent_dir):
        payload, declared_selected, skipped_ids, children = (
            _read_model_parent_artifact(path)
        )
        if (
            payload["claim_scope"] == "full"
            and payload["tier"] == "full"
            and payload["status"] == RECEIPT_STATUS_PASS
            and payload["manifest_sha256"] == manifest_fingerprint
            and declared_selected == selected_ids
            and not skipped_ids
        ):
            candidates.append((path, payload, children))
    if not candidates:
        raise ModelRegressionEvidenceError(
            "no exact-current full/full/pass model parent artifact with zero "
            "skipped models matches the current manifest"
        )
    for _candidate_path, candidate_payload, candidate_children in candidates:
        candidate_model_ids = tuple(
            row["model_id"] for row in candidate_children
        )
        if candidate_model_ids != tuple(sorted(selected_ids)):
            raise ModelRegressionEvidenceError(
                "model parent children do not cover the current full manifest exactly"
            )
        candidate_execution_id = candidate_payload["execution_receipt_id"]
        candidate_execution_fingerprint = candidate_payload[
            "execution_receipt_fingerprint"
        ]
        if not candidate_execution_id or not candidate_execution_fingerprint:
            raise ModelRegressionEvidenceError(
                "passing full model parent lacks its canonical execution receipt"
            )
        if any(
            row["receipt_id"] == candidate_execution_id
            or row["receipt_fingerprint"] == candidate_execution_fingerprint
            for row in candidate_children
        ):
            raise ModelRegressionEvidenceError(
                "model parent execution receipt cannot claim itself as a child"
            )
        for row in candidate_children:
            model_id = row["model_id"]
            try:
                candidate_receipt = load_evidence_receipt(
                    row["receipt_id"],
                    root_path,
                    output_directory=receipt_root,
                )
                _assert_owner_receipt_integrity(candidate_receipt)
            except (OSError, ValueError) as exc:
                raise ModelRegressionEvidenceError(
                    "model parent child receipt is missing or invalid: "
                    f"{model_id}: {exc}"
                ) from exc
            if candidate_receipt.fingerprint != row["receipt_fingerprint"]:
                raise ModelRegressionEvidenceError(
                    "model parent child fingerprint does not match the "
                    f"canonical receipt: {model_id}"
                )
            if (
                candidate_receipt.subject_id
                != f"validation-owner:model:{model_id}"
            ):
                raise ModelRegressionEvidenceError(
                    "model parent child subject does not match its model: "
                    + model_id
                )
    contracts = tuple(
        _model_owner_contract(root_path, manifest, entry) for entry in entries
    )
    plan_rows, currents, reusable = plan_validation_owners(
        root_path,
        contracts,
        receipt_root=receipt_root,
    )
    noncurrent = tuple(
        f"{row.owner_id} ({row.reason})"
        for row in plan_rows
        if row.disposition != OWNER_REUSE_CURRENT
    )
    if noncurrent:
        raise ModelRegressionEvidenceError(
            "model parent child evidence is not exact-current: "
            + ", ".join(noncurrent)
        )
    exact_child_identities = {
        (
            model_id,
            reusable[f"model:{model_id}"].receipt_id,
            reusable[f"model:{model_id}"].fingerprint,
        )
        for model_id in selected_ids
    }
    candidates = [
        (path, payload, children)
        for path, payload, children in candidates
        if {
            (
                row["model_id"],
                row["receipt_id"],
                row["receipt_fingerprint"],
            )
            for row in children
        }
        == exact_child_identities
    ]
    if not candidates:
        raise ModelRegressionEvidenceError(
            "no exact-current full model parent artifact composes the current "
            "leaf receipt identities"
        )

    # Leaf identity equality is necessary but not sufficient for parent
    # currentness.  Parent-only inputs (the manifest, aggregation code, receipt
    # verifier, or ownership rules) can change while every leaf remains
    # reusable.  Verify the canonical parent execution for every leaf-matching
    # wrapper before applying the 0/1/>1 cardinality rule.  A merely stale
    # parent is retained as history; malformed or invalid evidence still
    # blocks instead of being renewed over.
    exact_children_for_parent: list[EvidenceReceipt] = []
    child_verifications_for_parent: list[ReceiptVerificationResult] = []
    for model_id in selected_ids:
        owner_id = f"model:{model_id}"
        receipt = reusable[owner_id]
        context = build_owner_receipt_context(
            currents[owner_id],
            receipt,
            receipt_root,
        )
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ModelRegressionEvidenceError(
                f"model child failed independent current verification: {model_id}: "
                + ", ".join(item.code for item in verification.findings)
            )
        exact_children_for_parent.append(receipt)
        child_verifications_for_parent.append(verification)

    parent_contract_for_filter = _model_parent_owner_contract(
        manifest,
        entries,
        claim_scope="full",
        tier="full",
    )
    parent_current_for_filter = build_owner_current(
        root_path,
        parent_contract_for_filter,
        all_contracts=(parent_contract_for_filter,),
    )
    expected_child_identities_for_parent = {
        (item.receipt_id, item.fingerprint)
        for item in exact_children_for_parent
    }
    current_candidates: list[
        tuple[
            Path,
            Mapping[str, Any],
            tuple[Mapping[str, str], ...],
        ]
    ] = []
    stale_candidate_findings: list[str] = []
    for candidate_path, candidate_payload, candidate_children in candidates:
        candidate_execution_id = candidate_payload["execution_receipt_id"]
        candidate_execution_fingerprint = candidate_payload[
            "execution_receipt_fingerprint"
        ]
        try:
            candidate_execution = load_evidence_receipt(
                candidate_execution_id,
                root_path,
                output_directory=receipt_root,
            )
            _assert_owner_receipt_integrity(candidate_execution)
        except (OSError, ValueError) as exc:
            raise ModelRegressionEvidenceError(
                "model parent execution receipt is unavailable or invalid: "
                f"{exc}"
            ) from exc
        if (
            candidate_execution.fingerprint
            != candidate_execution_fingerprint
            or candidate_execution.subject_id
            != "validation-owner:model-regression-parent"
            or candidate_execution.subject_kind != OWNER_RECEIPT_KIND
            or candidate_execution.producer_id
            != "validation-owner:model-regression-parent"
        ):
            raise ModelRegressionEvidenceError(
                "model parent execution identity does not match its canonical receipt"
            )
        if any(
            item.receipt_id == candidate_execution.receipt_id
            for item in (
                *candidate_execution.required_child_receipts,
                *candidate_execution.consumed_child_receipts,
            )
        ):
            raise ModelRegressionEvidenceError(
                "model parent execution receipt cannot require or consume itself"
            )
        if (
            candidate_execution.result_status != RECEIPT_STATUS_PASS
            or candidate_execution.exit_code != 0
            or candidate_execution.claim_scope != "full"
            or candidate_execution.covered_obligations
            != parent_contract_for_filter.obligation_ids
            or candidate_execution.skipped_checks
            or candidate_execution.blockers
        ):
            raise ModelRegressionEvidenceError(
                "model parent execution receipt is not terminal full "
                "exact-obligation pass"
            )
        required_child_identities = {
            (item.receipt_id, item.expected_receipt_fingerprint)
            for item in candidate_execution.required_child_receipts
        }
        consumed_child_identities = {
            (item.receipt_id, item.receipt_fingerprint)
            for item in candidate_execution.consumed_child_receipts
        }
        if (
            required_child_identities != expected_child_identities_for_parent
            or consumed_child_identities != expected_child_identities_for_parent
        ):
            raise ModelRegressionEvidenceError(
                "model parent execution receipt does not compose the exact "
                "current children"
            )
        try:
            candidate_context = build_child_bound_owner_receipt_context(
                parent_current_for_filter,
                candidate_execution,
                root_path,
                receipt_root,
                child_receipts=tuple(exact_children_for_parent),
                child_verification_results=tuple(
                    child_verifications_for_parent
                ),
            )
        except ValueError as exc:
            raise ModelRegressionEvidenceError(
                f"model parent child-bound context is invalid: {exc}"
            ) from exc
        candidate_verification = verify_evidence_receipt(
            candidate_execution,
            candidate_context,
        )
        if candidate_verification.ok:
            current_candidates.append(
                (candidate_path, candidate_payload, candidate_children)
            )
            continue
        finding_codes = ", ".join(
            item.code for item in candidate_verification.findings
        )
        if candidate_verification.status == VERIFICATION_STATUS_STALE:
            stale_candidate_findings.append(
                f"{candidate_path.name}: {finding_codes}"
            )
            continue
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is invalid: " + finding_codes
        )

    candidates = current_candidates
    if not candidates:
        detail = "; ".join(stale_candidate_findings)
        raise ModelRegressionParentNotCurrentError(
            "no exact-current full model parent execution composes the current "
            "leaves"
            + (f": {detail}" if detail else "")
        )
    if len(candidates) > 1:
        raise ModelRegressionEvidenceError(
            "ambiguous exact-current full model parent artifacts: "
            + ", ".join(path.name for path, _payload, _children in candidates)
        )

    parent_path, payload, declared_children = candidates[0]
    if tuple(row["model_id"] for row in declared_children) != tuple(
        sorted(selected_ids)
    ):
        raise ModelRegressionEvidenceError(
            "model parent children do not cover the current full manifest exactly"
        )
    execution_receipt_id = payload["execution_receipt_id"]
    execution_receipt_fingerprint = payload["execution_receipt_fingerprint"]
    if not execution_receipt_id or not execution_receipt_fingerprint:
        raise ModelRegressionEvidenceError(
            "passing full model parent lacks its canonical execution receipt"
        )
    if any(
        row["receipt_id"] == execution_receipt_id
        or row["receipt_fingerprint"] == execution_receipt_fingerprint
        for row in declared_children
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt cannot claim itself as a child"
        )

    declared_receipts: dict[str, EvidenceReceipt] = {}
    for row in declared_children:
        model_id = row["model_id"]
        try:
            declared_receipt = load_evidence_receipt(
                row["receipt_id"],
                root_path,
                output_directory=receipt_root,
            )
            _assert_owner_receipt_integrity(declared_receipt)
        except (OSError, ValueError) as exc:
            raise ModelRegressionEvidenceError(
                f"model parent child receipt is missing or invalid: {model_id}: {exc}"
            ) from exc
        if declared_receipt.fingerprint != row["receipt_fingerprint"]:
            raise ModelRegressionEvidenceError(
                f"model parent child fingerprint does not match the canonical receipt: {model_id}"
            )
        if declared_receipt.subject_id != f"validation-owner:model:{model_id}":
            raise ModelRegressionEvidenceError(
                f"model parent child subject does not match its model: {model_id}"
            )
        declared_receipts[model_id] = declared_receipt

    declared_by_model = {
        row["model_id"]: row for row in declared_children
    }
    entries_by_model = {entry.model_id: entry for entry in entries}
    exact_children: list[EvidenceReceipt] = []
    child_verifications: list[ReceiptVerificationResult] = []
    child_evidence: list[CurrentModelRegressionChildEvidence] = []
    for model_id in selected_ids:
        owner_id = f"model:{model_id}"
        receipt = reusable.get(owner_id)
        declared = declared_by_model.get(model_id)
        declared_receipt = declared_receipts.get(model_id)
        if receipt is None or declared is None or declared_receipt is None:
            raise ModelRegressionEvidenceError(
                f"model parent child is missing: {model_id}"
            )
        if (
            declared["receipt_id"] != receipt.receipt_id
            or declared["receipt_fingerprint"] != receipt.fingerprint
            or declared_receipt.receipt_id != receipt.receipt_id
            or declared_receipt.fingerprint != receipt.fingerprint
        ):
            raise ModelRegressionEvidenceError(
                f"model parent child identity is not exact-current: {model_id}"
            )
        expected_obligations = (f"model-regression:{model_id}",)
        if (
            receipt.subject_id != f"validation-owner:model:{model_id}"
            or receipt.subject_kind != OWNER_RECEIPT_KIND
            or receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.claim_scope != "full"
            or receipt.covered_obligations != expected_obligations
            or receipt.skipped_checks
            or receipt.blockers
        ):
            raise ModelRegressionEvidenceError(
                f"model child is not a terminal full exact-obligation pass: {model_id}"
            )
        if str(receipt.metadata.get("publication_kind", "")) != "supervised_producer":
            raise ModelRegressionEvidenceError(
                f"model child is not a direct supervised producer receipt: {model_id}"
            )
        if receipt.required_child_receipts or receipt.consumed_child_receipts:
            raise ModelRegressionEvidenceError(
                f"model child receipt cannot be an aggregate: {model_id}"
            )
        context = build_owner_receipt_context(
            currents[owner_id],
            receipt,
            receipt_root,
        )
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ModelRegressionEvidenceError(
                f"model child failed independent current verification: {model_id}: "
                + ", ".join(item.code for item in verification.findings)
            )
        child_result = child_from_owner_receipt(receipt, receipt_root)
        if (
            child_result.child_id != f"model:{model_id}"
            or child_result.status != VALIDATION_STATUS_PASS
            or child_result.payload.get("nested_receipt_id")
        ):
            raise ModelRegressionEvidenceError(
                f"model child proof is not a direct terminal result: {model_id}"
            )
        raw_result = child_result.payload.get("model_result")
        if not isinstance(raw_result, Mapping):
            raise ModelRegressionEvidenceError(
                f"model child proof is missing its model result: {model_id}"
            )
        if (
            raw_result.get("model_id") != model_id
            or raw_result.get("status") != VALIDATION_STATUS_PASS
            or raw_result.get("ok") is not True
            or raw_result.get("exit_code") != 0
        ):
            raise ModelRegressionEvidenceError(
                f"model child proof result is not terminal pass: {model_id}"
            )
        entry = entries_by_model[model_id]
        inventory = resolve_entry_input_inventory(root_path, entry)
        expected_model_instance = build_regression_model_instance(
            root_path,
            entry,
            inventory,
        )
        expected_input_inventory = input_inventory_fingerprint(inventory)
        expected_purpose = (
            entry.purpose_closure.closure_fingerprint
            if entry.purpose_closure is not None
            else ""
        )
        child_evidence.append(
            CurrentModelRegressionChildEvidence(
                model_id=model_id,
                receipt_id=receipt.receipt_id,
                receipt_fingerprint=receipt.fingerprint,
                model_instance_id=_exact_model_result_identity(
                    raw_result,
                    "model_instance_id",
                    entry.purpose_closure.model_instance_id
                    if entry.purpose_closure is not None
                    else "",
                    model_id=model_id,
                ),
                model_instance_fingerprint=_exact_model_result_identity(
                    raw_result,
                    "model_instance_fingerprint",
                    expected_model_instance.fingerprint,
                    model_id=model_id,
                ),
                input_inventory_fingerprint=_exact_model_result_identity(
                    raw_result,
                    "input_inventory_fingerprint",
                    expected_input_inventory,
                    model_id=model_id,
                ),
                purpose_closure_fingerprint=_exact_model_result_identity(
                    raw_result,
                    "purpose_closure_fingerprint",
                    expected_purpose,
                    model_id=model_id,
                ),
            )
        )
        exact_children.append(receipt)
        child_verifications.append(verification)

    try:
        parent_execution = load_evidence_receipt(
            execution_receipt_id,
            root_path,
            output_directory=receipt_root,
        )
        _assert_owner_receipt_integrity(parent_execution)
    except (OSError, ValueError) as exc:
        raise ModelRegressionEvidenceError(
            f"model parent execution receipt is unavailable or invalid: {exc}"
        ) from exc
    if (
        parent_execution.fingerprint != execution_receipt_fingerprint
        or parent_execution.subject_id
        != "validation-owner:model-regression-parent"
        or parent_execution.subject_kind != OWNER_RECEIPT_KIND
        or parent_execution.producer_id
        != "validation-owner:model-regression-parent"
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution identity does not match its canonical receipt"
        )
    if any(
        item.receipt_id == parent_execution.receipt_id
        for item in (
            *parent_execution.required_child_receipts,
            *parent_execution.consumed_child_receipts,
        )
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt cannot require or consume itself"
        )

    parent_contract = _model_parent_owner_contract(
        manifest,
        entries,
        claim_scope="full",
        tier="full",
    )
    if (
        parent_execution.result_status != RECEIPT_STATUS_PASS
        or parent_execution.exit_code != 0
        or parent_execution.claim_scope != "full"
        or parent_execution.covered_obligations
        != parent_contract.obligation_ids
        or parent_execution.skipped_checks
        or parent_execution.blockers
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is not terminal full exact-obligation pass"
        )
    expected_child_identities = {
        (item.receipt_id, item.fingerprint) for item in exact_children
    }
    required_child_identities = {
        (item.receipt_id, item.expected_receipt_fingerprint)
        for item in parent_execution.required_child_receipts
    }
    consumed_child_identities = {
        (item.receipt_id, item.receipt_fingerprint)
        for item in parent_execution.consumed_child_receipts
    }
    if (
        required_child_identities != expected_child_identities
        or consumed_child_identities != expected_child_identities
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt does not compose the exact current children"
        )
    parent_current = build_owner_current(
        root_path,
        parent_contract,
        all_contracts=(parent_contract,),
    )
    try:
        parent_context = build_child_bound_owner_receipt_context(
            parent_current,
            parent_execution,
            root_path,
            receipt_root,
            child_receipts=tuple(exact_children),
            child_verification_results=tuple(child_verifications),
        )
    except ValueError as exc:
        raise ModelRegressionEvidenceError(
            f"model parent child-bound context is invalid: {exc}"
        ) from exc
    parent_verification = verify_evidence_receipt(
        parent_execution,
        parent_context,
    )
    if not parent_verification.ok:
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is not an exact-current full composition: "
            + ", ".join(item.code for item in parent_verification.findings)
        )

    return CurrentModelRegressionParentEvidence(
        manifest_fingerprint=manifest_fingerprint,
        parent_artifact_path=str(parent_path),
        parent_artifact_fingerprint=payload["parent_receipt_fingerprint"],
        parent_execution_receipt_id=parent_execution.receipt_id,
        parent_execution_receipt_fingerprint=parent_execution.fingerprint,
        children=tuple(child_evidence),
    )


def run_manifest_regressions(
    root: str | Path = ".",
    *,
    tier: str = "fast",
    model_patterns: Sequence[str] = (),
    shard: str | None = None,
    jobs: int = 1,
    timeout: float | None = None,
    output_dir: str | Path | None = None,
    cancel_event: threading.Event | None = None,
    progress: ProgressCallback | None = None,
    allow_mutating: bool = False,
    command: str = "flowguard-model-regressions",
    reuse_current: bool = True,
    receipt_dir: str | Path | None = None,
) -> ModelRegressionReport:
    root_path = Path(root).resolve()
    manifest = ModelRegressionManifest.load(root_path)
    audit = audit_manifest(root_path, manifest)
    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    if timeout is not None and timeout <= 0:
        raise ValueError("timeout must be positive")
    selected = select_entries(manifest, tier=tier, model_patterns=model_patterns, shard=shard)
    complete_selected = select_entries(manifest, tier="full")
    parent_claim_scope = (
        "full"
        if tier == "full"
        and not model_patterns
        and shard is None
        and tuple(entry.model_id for entry in selected)
        == tuple(entry.model_id for entry in complete_selected)
        else "scoped"
    )
    if any(entry.mutation_policy == "mutating" for entry in selected) and not allow_mutating:
        blocked = tuple(entry.model_id for entry in selected if entry.mutation_policy == "mutating")
        audit = ManifestAudit(
            False,
            audit.discovered_model_ids,
            audit.registered_model_ids,
            audit.errors + tuple(f"mutating model blocked by default: {item}" for item in blocked),
        )
    receipt_root = (
        Path(receipt_dir).resolve()
        if receipt_dir is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    contracts = tuple(
        _model_owner_contract(root_path, manifest, entry) for entry in selected
    )
    planning_observation = observe_validation_owners(
        root_path,
        contracts,
        receipt_root=receipt_root,
    )
    plan_rows = planning_observation.rows
    currents = planning_observation.current_by_owner
    reusable_receipts = planning_observation.receipt_by_owner
    if not reuse_current:
        plan_rows = tuple(
            replace(
                row,
                disposition=OWNER_EXECUTE,
                reason="caller explicitly requested fresh execution",
                receipt_id="",
                receipt_fingerprint="",
            )
            if row.disposition == OWNER_REUSE_CURRENT
            else row
            for row in plan_rows
        )
        reusable_receipts = {}
    blocked_rows = tuple(
        row for row in plan_rows if row.disposition == OWNER_BLOCKED
    )
    if blocked_rows:
        audit = ManifestAudit(
            False,
            audit.discovered_model_ids,
            audit.registered_model_ids,
            audit.errors
            + tuple(
                f"validation owner blocked for {row.owner_id}: {row.reason}"
                for row in blocked_rows
            ),
        )
    entries_by_owner = {
        f"model:{entry.model_id}": entry for entry in selected
    }
    reused_results: dict[str, ModelRunResult] = {}
    if audit.ok:
        for row in plan_rows:
            if row.disposition != OWNER_REUSE_CURRENT:
                continue
            entry = entries_by_owner[row.owner_id]
            child = child_from_owner_receipt(
                reusable_receipts[row.owner_id],
                receipt_root,
            )
            reusable = _model_result_from_reused_child(entry, child)
            reused_results[entry.model_id] = reusable
            if progress:
                progress(
                    {
                        "event": "reused",
                        "model_id": entry.model_id,
                        "status": reusable.status,
                        "seconds": 0.0,
                    }
                )
    pending = tuple(
        entries_by_owner[row.owner_id]
        for row in plan_rows
        if row.disposition == OWNER_EXECUTE
    )
    if jobs > 1 and any(not entry.shard_safe for entry in pending):
        unsafe = tuple(entry.model_id for entry in pending if not entry.shard_safe)
        raise ValueError("parallel execution includes non-shard-safe models: " + ", ".join(unsafe))
    if output_dir is None:
        output_path = Path(tempfile.mkdtemp(prefix="flowguard-model-regressions-"))
    else:
        output_path = Path(output_dir).resolve()
    ensure_new_run_directory(output_path)
    cancel = cancel_event or threading.Event()
    tracked = _tracked_paths(root_path)
    before = _snapshot(tracked)
    started_at = time.time()
    results: list[ModelRunResult] = list(reused_results.values())
    source_freshness = ValidationObservationFreshness.not_run(
        planning_observation
    )
    if audit.ok:
        executed_results, source_freshness = _execute_pending_models(
                root_path=root_path,
                pending=pending,
                jobs=jobs,
                timeout=timeout,
                output_path=output_path,
                receipt_root=receipt_root,
                currents=currents,
                contracts=contracts,
                planning_observation=planning_observation,
                cancel=cancel,
                progress=progress,
            )
        results.extend(executed_results)
    results.sort(key=lambda item: item.model_id)
    after = _snapshot(tracked)
    mutations = _mutation_paths(before, after, root_path)
    selected_ids = tuple(entry.model_id for entry in selected)
    unavailable_optional_ids = tuple(
        entry.model_id
        for entry in manifest.entries
        if entry.distribution_policy == "optional_local"
        and (
            not (root_path / entry.model_path).is_file()
            or len(entry.runner) < 2
            or not (root_path / entry.runner[1]).is_file()
        )
    )
    completed_ids = {item.model_id for item in results}
    skipped_ids = tuple(item for item in selected_ids if item not in completed_ids)
    report = ModelRegressionReport(
        root=str(root_path),
        tier=tier,
        output_dir=str(output_path),
        audit=audit,
        results=tuple(results),
        selected_model_ids=selected_ids,
        skipped_model_ids=skipped_ids,
        unavailable_optional_model_ids=unavailable_optional_ids,
        mutation_paths=mutations,
        started_at_epoch=started_at,
        finished_at_epoch=time.time(),
        command=command,
        parent_claim_scope=parent_claim_scope,
    )
    (
        parent_path,
        parent_fingerprint,
        composition_observation,
        final_freshness,
        parent_composition_seconds,
    ) = _write_model_parent_receipt(
        root_path,
        manifest,
        receipt_root,
        report,
        planning_observation=planning_observation,
        source_freshness=source_freshness,
    )
    report = replace(
        report,
        parent_receipt_path=parent_path,
        parent_receipt_fingerprint=parent_fingerprint,
        initial_observation_seconds=planning_observation.observation_seconds,
        receipt_reconciliation_seconds=(
            composition_observation.observation_seconds
        ),
        final_freshness_seconds=final_freshness.observation_seconds,
        parent_composition_seconds=parent_composition_seconds,
        per_leaf_source_current_rebuild_count=0,
        per_leaf_receipt_store_scan_count=0,
        receipt_reconciliation_count=(1 if final_freshness.ok else 0),
        initial_observation_fingerprint=(
            composition_observation.observation_fingerprint
        ),
        final_freshness_fingerprint=(
            final_freshness.final_observation_fingerprint
        ),
    )
    report_path = output_path / "report.json"
    _write_json(report_path, report.to_dict())
    publish_run(
        output_path,
        kind="model-simulator" if command == "flowguard-simulator" else "model-regressions",
        status=report.status,
        result_path=report_path,
        started_at_epoch=report.started_at_epoch,
        finished_at_epoch=report.finished_at_epoch,
    )
    return report


__all__ = [
    "MANIFEST_SCHEMA",
    "MODEL_REGRESSION_PARENT_ARTIFACT_TYPE",
    "MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA",
    "CurrentModelRegressionChildEvidence",
    "CurrentModelRegressionParentEvidence",
    "ManifestAudit",
    "ModelImpactMap",
    "ModelRegressionEvidenceError",
    "ModelRegressionEntry",
    "ModelRegressionManifest",
    "ModelRegressionManifestError",
    "ModelRegressionReport",
    "ModelRunResult",
    "audit_intent_source_input_bindings",
    "audit_manifest",
    "build_regression_model_instance",
    "compile_model_impact_map",
    "discover_model_directories",
    "input_inventory_fingerprint",
    "model_instance_fingerprint",
    "parse_shard",
    "resolve_current_full_model_regression_parent",
    "resolve_entry_input_inventory",
    "run_manifest_regressions",
    "select_entries",
]
