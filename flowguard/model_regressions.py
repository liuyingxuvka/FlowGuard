"""Manifest-owned, observable execution for repository FlowGuard models.

The manifest is the execution authority.  Filesystem discovery is used only
to prove that the manifest accounts for every local model in both directions.
Each child runs in its own process and receives an isolated artifact directory.
"""

from __future__ import annotations

import fnmatch
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
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .evidence_lifecycle import ensure_new_run_directory, publish_run, store_text_object
from .evidence_receipts import (
    fingerprint_value,
    receipt_path as evidence_receipt_path,
)
from .model_authority import (
    ModelInstanceRef,
    build_model_instance_ref,
)
from .model_purpose import ModelPurposeClosure, ModelPurposeError, validate_unique_model_instances
from .source_identity import source_file_fingerprint

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
    OWNER_REUSE_CURRENT,
    ValidationOwnerContract,
    child_from_owner_receipt,
    plan_validation_owners,
    save_owner_receipt,
)


MANIFEST_SCHEMA = "flowguard.model_regression_manifest.v3"
TIER_RANK = {"fast": 0, "focused": 1, "full": 2}
class ModelRegressionManifestError(ValueError):
    """Raised when the checked-in model inventory is incomplete or invalid."""


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
        for path in _resolve_relative_files(root_path, entry.input_globs):
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
            if self.tier == "full"
            else f"{self.tier.title()}-tier success is scoped feedback and does not support a full-model release claim."
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
                "results": [item.to_dict() for item in self.results],
            }
        )
        return payload


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_entry_input_inventory(
    root: str | Path,
    entry: ModelRegressionEntry,
) -> tuple[dict[str, str], ...]:
    """Resolve manifest selectors to the exact immutable input inventory."""

    root_path = Path(root).resolve()
    inventory: dict[str, str] = {}
    for pattern in entry.input_globs:
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


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


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
    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    status = VALIDATION_STATUS_INTERNAL_ERROR
    finding_codes: tuple[str, ...] = ("model.internal_error",)
    message = "model runner did not reach a terminal state"
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        while True:
            if cancel_event.is_set():
                _terminate_process(process)
                stdout, stderr = process.communicate()
                status = VALIDATION_STATUS_CANCELLED
                finding_codes = ("model.cancelled",)
                message = "cancelled before terminal runner completion"
                break
            elapsed = time.monotonic() - started
            if elapsed > timeout:
                _terminate_process(process)
                stdout, stderr = process.communicate()
                status = VALIDATION_STATUS_TIMEOUT
                finding_codes = ("model.timeout",)
                message = f"runner exceeded {timeout:g} seconds"
                break
            try:
                stdout, stderr = process.communicate(timeout=min(0.2, max(0.01, timeout - elapsed)))
            except subprocess.TimeoutExpired:
                continue
            exit_code = process.returncode
            if exit_code == 0:
                status = VALIDATION_STATUS_PASS
                finding_codes = ()
                message = "runner completed successfully"
            else:
                status = VALIDATION_STATUS_FAIL
                finding_codes = ("model.nonzero_exit",)
                message = f"runner exited with code {exit_code}"
            break
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
                    *entry.input_globs,
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
    started_at: str,
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
    receipt = save_owner_receipt(
        current,
        child,
        root,
        receipt_root,
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
    plan_rows, currents, reusable_receipts = plan_validation_owners(
        root_path,
        contracts,
        receipt_root=receipt_root,
    )
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
    if jobs > 1:
        # A declaration alone cannot authorize parallel execution for an
        # isolated-output aggregate. Execute its bound serial/parallel proof
        # inside this validation owner before launching the shard pool.
        from .shard_safety import prove_model_shard_safety

        for entry in pending:
            if not entry.shard_safety_proof:
                continue
            proof = prove_model_shard_safety(
                root_path,
                entry,
                output_dir=output_path / "shard-safety" / entry.model_id,
            )
            if not proof["ok"]:
                raise ValueError(
                    f"parallel execution proof failed for {entry.model_id}; "
                    f"see {output_path / 'shard-safety' / entry.model_id / 'result.json'}"
                )
    cancel = cancel_event or threading.Event()
    tracked = _tracked_paths(root_path)
    before = _snapshot(tracked)
    started_at = time.time()
    results: list[ModelRunResult] = list(reused_results.values())
    if audit.ok:
        if jobs == 1:
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
                results.append(
                    _persist_model_owner_result(
                        root_path,
                        receipt_root,
                        currents[f"model:{entry.model_id}"],
                        result,
                        started_at=owner_started_at,
                    )
                )
                if cancel.is_set():
                    break
        else:
            with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="flowguard-model") as executor:
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
                    results.append(
                        _persist_model_owner_result(
                            root_path,
                            receipt_root,
                            currents[f"model:{entry.model_id}"],
                            future.result(),
                            started_at=owner_started_at,
                        )
                    )
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
    "ManifestAudit",
    "ModelImpactMap",
    "ModelRegressionEntry",
    "ModelRegressionManifest",
    "ModelRegressionManifestError",
    "ModelRegressionReport",
    "ModelRunResult",
    "audit_manifest",
    "build_regression_model_instance",
    "compile_model_impact_map",
    "discover_model_directories",
    "input_inventory_fingerprint",
    "model_instance_fingerprint",
    "parse_shard",
    "resolve_entry_input_inventory",
    "run_manifest_regressions",
    "select_entries",
]
