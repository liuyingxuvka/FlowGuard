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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .evidence_lifecycle import ensure_new_run_directory, publish_run, store_text_object
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


MANIFEST_SCHEMA = "flowguard.model_regression_manifest.v2"
RECEIPT_SCHEMA = "flowguard.model_regression_receipt.v3"
TIER_RANK = {"fast": 0, "focused": 1, "full": 2}
TERMINAL_STATUSES = {
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_FAIL,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_TIMEOUT,
    VALIDATION_STATUS_CANCELLED,
    VALIDATION_STATUS_INTERNAL_ERROR,
}


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

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ModelRegressionEntry":
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
        )

    @property
    def excluded(self) -> bool:
        return bool(self.exclusion_reason)

    def command(self, *, root: Path) -> tuple[str, ...]:
        values = {"python": sys.executable, "root": str(root)}
        return tuple(item.format(**values) for item in self.runner)


@dataclass(frozen=True)
class ModelRegressionManifest:
    path: Path
    entries: tuple[ModelRegressionEntry, ...]

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
        entries = tuple(ModelRegressionEntry.from_dict(item) for item in payload.get("models", ()))
        return cls(path=manifest_path, entries=entries)


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
    subject_revision: str = ""
    model_instance_fingerprint: str = ""
    input_inventory_fingerprint: str = ""
    input_inventory: tuple[Mapping[str, str], ...] = ()
    purpose_closure_fingerprint: str = ""
    purpose_claim_boundary: str = ""
    stdout: Mapping[str, Any] = field(default_factory=dict, compare=False)
    stderr: Mapping[str, Any] = field(default_factory=dict, compare=False)

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
            "subject_revision": self.subject_revision,
            "model_instance_fingerprint": self.model_instance_fingerprint,
            "input_inventory_fingerprint": self.input_inventory_fingerprint,
            "input_inventory": [dict(item) for item in self.input_inventory],
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
            "purpose_claim_boundary": self.purpose_claim_boundary,
            "stdout": dict(self.stdout),
            "stderr": dict(self.stderr),
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


def repository_subject_revision(
    root: str | Path,
    inventory: Sequence[Mapping[str, str]],
) -> str:
    """Return one reviewable revision identity for the exact worktree inputs."""

    root_path = Path(root).resolve()
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_path,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        completed = None
    if completed is not None and completed.returncode == 0:
        head = completed.stdout.strip()
        if len(head) == 40:
            return f"git:{head}"
    return f"unversioned:{input_inventory_fingerprint(inventory)}"


def build_regression_model_instance(
    root: str | Path,
    entry: ModelRegressionEntry,
    inventory: Sequence[Mapping[str, str]],
    *,
    subject_revision: str | None = None,
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
        subject_revision=subject_revision
        or repository_subject_revision(root_path, inventory),
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
    receipt_path = artifact_dir / "receipt.json"
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
    stdout_descriptor = store_text_object(output_dir, stdout)
    stderr_descriptor = store_text_object(output_dir, stderr)
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
        receipt_path=str(receipt_path),
        artifact_paths=expected_paths,
        finding_codes=finding_codes,
        message=message,
        model_instance_id=entry.purpose_closure.model_instance_id if entry.purpose_closure else "",
        model_kind=instance.model_kind,
        subject_revision=instance.subject_revision,
        model_instance_fingerprint=instance_fingerprint,
        input_inventory_fingerprint=inventory_fingerprint,
        input_inventory=input_inventory,
        purpose_closure_fingerprint=(entry.purpose_closure.closure_fingerprint if entry.purpose_closure else ""),
        purpose_claim_boundary=entry.purpose_closure.claim_boundary if entry.purpose_closure else "",
        stdout=stdout_descriptor,
        stderr=stderr_descriptor,
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "receipt_id": hashlib.sha256(
            json.dumps(
                {
                    "model_id": entry.model_id,
                    "model_instance_fingerprint": instance_fingerprint,
                    "command": command,
                    "status": status,
                    "started": started,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "model_id": entry.model_id,
        "status": status,
        "terminal": status in TERMINAL_STATUSES,
        "repository_root": str(root),
        "source_precedence": "repository_root_before_existing_pythonpath",
        "exit_code": exit_code,
        "seconds": elapsed_seconds,
        "finding_codes": list(finding_codes),
        "input_globs": list(entry.input_globs),
        "input_inventory": [dict(item) for item in input_inventory],
        "input_inventory_fingerprint": inventory_fingerprint,
        "model_instance_id": result.model_instance_id,
        "model_kind": result.model_kind,
        "subject_revision": result.subject_revision,
        "model_instance": instance.to_dict(),
        "model_instance_fingerprint": instance_fingerprint,
        "purpose_closure_fingerprint": result.purpose_closure_fingerprint,
        "protected_failure_ids": list(entry.purpose_closure.protected_failure_ids) if entry.purpose_closure else [],
        "known_good_case_id": entry.purpose_closure.known_good_case_id if entry.purpose_closure else "",
        "known_bad_case_ids": [item.known_bad_case_id for item in entry.purpose_closure.failure_bindings] if entry.purpose_closure else [],
        "native_oracle_ids": [item.oracle_id for item in entry.purpose_closure.failure_bindings] if entry.purpose_closure else [],
        "artifact_paths": [str(stdout_path), str(stderr_path), *expected_paths],
        "stdout": stdout_descriptor,
        "stderr": stderr_descriptor,
        "claim_boundary": result.purpose_claim_boundary or "Current invocation of one manifest-owned model runner only.",
    }
    _write_json(receipt_path, receipt)
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
    if jobs > 1 and any(not entry.shard_safe for entry in selected):
        unsafe = tuple(entry.model_id for entry in selected if not entry.shard_safe)
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
    results: list[ModelRunResult] = []
    if audit.ok:
        if jobs == 1:
            for entry in selected:
                results.append(
                    _run_entry(
                        root_path,
                        entry,
                        output_path,
                        timeout_override=timeout,
                        cancel_event=cancel,
                        progress=progress,
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
                    ): entry
                    for entry in selected
                }
                for future in as_completed(futures):
                    results.append(future.result())
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
    "ModelRegressionEntry",
    "ModelRegressionManifest",
    "ModelRegressionManifestError",
    "ModelRegressionReport",
    "ModelRunResult",
    "audit_manifest",
    "build_regression_model_instance",
    "discover_model_directories",
    "input_inventory_fingerprint",
    "model_instance_fingerprint",
    "parse_shard",
    "repository_subject_revision",
    "resolve_entry_input_inventory",
    "run_manifest_regressions",
    "select_entries",
]
