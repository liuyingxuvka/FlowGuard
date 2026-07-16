"""Exact spec-check sessions, immutable receipts, and safe result reuse."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence_receipts import (
    INPUT_HASH_BOTH,
    RECEIPT_STATUS_BLOCKED,
    RECEIPT_STATUS_ERROR,
    RECEIPT_STATUS_FAIL,
    RECEIPT_STATUS_PASS,
    EvidenceReceipt,
    InputSnapshot,
    ReceiptVerificationContext,
    build_environment_fingerprint,
    fingerprint_value,
    list_evidence_receipts,
    save_evidence_receipt,
    snapshot_file,
    tokenize_command,
    tokenize_path,
    verify_evidence_receipt,
)
from .proof_artifact import (
    PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
    PROOF_ARTIFACT_STATUS_PASSED,
    ProofArtifactRef,
)
from .spec_providers import load_openspec_work_package, load_speckit_work_package
from .spec_work_package import SpecWorkPackage, review_spec_work_package
from .test_reuse import TestResultReuseTicket


SPEC_CHECK_STATE_EXECUTED = "executed"
SPEC_CHECK_STATE_REUSED_CURRENT = "reused-current"
SPEC_CHECK_STATE_STALE = "stale"
SPEC_CHECK_STATE_NOT_RUN = "not-run"
SPEC_CHECK_STATE_BLOCKED = "blocked"
SPEC_CHECK_STATES = (
    SPEC_CHECK_STATE_EXECUTED,
    SPEC_CHECK_STATE_REUSED_CURRENT,
    SPEC_CHECK_STATE_STALE,
    SPEC_CHECK_STATE_NOT_RUN,
    SPEC_CHECK_STATE_BLOCKED,
)

SPEC_TERMINAL_PASS = "pass"
SPEC_TERMINAL_FAIL = "fail"
SPEC_TERMINAL_TIMEOUT = "timeout"
SPEC_TERMINAL_BLOCKED = "blocked"
SPEC_TERMINAL_ERROR = "error"
SPEC_TERMINAL_NOT_RUN_DEPENDENCY = "not_run_due_to_dependency"

SPEC_CHECK_CLAIM_SCOPE = "spec_check_execution"
SPEC_EVIDENCE_ROOT = Path(".flowguard/evidence/spec-work-packages")
SPEC_RECEIPT_SCHEMA = "spec-check-receipt.v1"
SPEC_SESSION_SCHEMA = "spec-work-package-session.v1"
SPEC_MANIFEST_SCHEMA = "spec-governed-input-manifest.v1"

_ROOT_FILES = {
    "AGENTS.md",
    "CHANGELOG.md",
    "README.md",
    "pyproject.toml",
}
_SOURCE_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json"}
_ALWAYS_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}
_FLOWGUARD_DERIVED_PARTS = {"evidence", "run_artifacts", "run-artifacts", "release"}
_OPENSPEC_DERIVED_PARTS = {"verification-receipts"}
_SKILLGUARD_SOURCE_FILES = {
    "contract-source.json",
    "compiled-contract.json",
    "check-manifest.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _safe_component(value: str) -> str:
    stem = "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{stem[:80].strip('._') or 'item'}-{digest}"


def _project_root(root: str | Path) -> Path:
    candidate = Path(root).expanduser().resolve()
    if not candidate.is_dir():
        raise ValueError(f"project root does not exist: {candidate}")
    return candidate


def _evidence_root(root: Path) -> Path:
    return root / SPEC_EVIDENCE_ROOT


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _is_governed_path(root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root)
    except ValueError:
        return False
    if not path.is_file() or path.is_symlink():
        return False
    parts = relative.parts
    lowered = tuple(part.casefold() for part in parts)
    if any(part in _ALWAYS_EXCLUDED_PARTS for part in lowered):
        return False
    if relative.name == "verification-report.json":
        return False
    if len(parts) == 1:
        return relative.name in _ROOT_FILES
    top = lowered[0]
    if top == ".flowguard":
        if len(lowered) > 1 and lowered[1] in _FLOWGUARD_DERIVED_PARTS:
            return False
        # Model runners commonly materialize these files beside their model.
        # They are outputs, never source topology; counting them as inputs makes
        # a validation run invalidate its own begin snapshot.
        if relative.name.casefold() in {"result.json", "report.json"}:
            return False
        if relative.name in {
            "full_unittest_exit.txt",
            "full_unittest_pid.txt",
            "full_unittest_stderr.txt",
            "full_unittest_stdout.txt",
        }:
            return False
        return path.suffix.casefold() in _SOURCE_SUFFIXES
    if top == ".agents":
        if len(lowered) < 3 or lowered[1] != "skills":
            return False
        if ".skillguard" in lowered:
            return relative.name in _SKILLGUARD_SOURCE_FILES
        return path.suffix.casefold() in {".md", ".py", ".yaml", ".yml", ".json"}
    if top == "openspec":
        if any(part in _OPENSPEC_DERIVED_PARTS for part in lowered):
            return False
        return path.suffix.casefold() in {".md", ".yaml", ".yml", ".json"}
    if top in {"flowguard", "examples", "scripts", "tests"}:
        return path.suffix.casefold() == ".py"
    if top == "docs":
        return path.suffix.casefold() in {".md", ".json", ".yaml", ".yml"}
    return False


def discover_governed_input_paths(root: str | Path) -> tuple[Path, ...]:
    """Expand canonical source inputs while excluding all known derived state."""

    project_root = _project_root(root)
    candidates: list[Path] = [project_root / name for name in _ROOT_FILES]
    for top_name in ("flowguard", "examples", "scripts", "tests", "docs", "openspec", ".flowguard", ".agents"):
        top = project_root / top_name
        if not top.is_dir():
            continue
        for current, directories, filenames in os.walk(top, followlinks=False):
            current_path = Path(current)
            try:
                relative = current_path.relative_to(project_root)
            except ValueError:
                directories[:] = []
                continue
            lowered = tuple(part.casefold() for part in relative.parts)
            directories[:] = [
                name
                for name in directories
                if name.casefold() not in _ALWAYS_EXCLUDED_PARTS
                and not (
                    lowered and lowered[0] == ".flowguard" and name.casefold() in _FLOWGUARD_DERIVED_PARTS
                )
                and not (
                    lowered and lowered[0] == "openspec" and name.casefold() in _OPENSPEC_DERIVED_PARTS
                )
                and not (".skillguard" in lowered)
            ]
            candidates.extend(current_path / name for name in filenames)
    paths = tuple(
        sorted(
            (path for path in candidates if path.is_file() and _is_governed_path(project_root, path)),
            key=lambda item: item.relative_to(project_root).as_posix(),
        )
    )
    if not paths:
        raise ValueError("no governed source inputs were discovered")
    return paths


@dataclass(frozen=True)
class SpecInputManifest:
    fingerprint: str
    snapshots: tuple[InputSnapshot, ...]
    created_at: str = ""
    schema_version: str = SPEC_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "fingerprint", str(self.fingerprint))
        object.__setattr__(self, "snapshots", tuple(self.snapshots))
        object.__setattr__(self, "created_at", str(self.created_at))
        if self.schema_version != SPEC_MANIFEST_SCHEMA:
            raise ValueError(f"unsupported input manifest schema: {self.schema_version}")
        expected = fingerprint_value([snapshot.to_dict() for snapshot in self.snapshots])
        if self.fingerprint != expected:
            raise ValueError("input manifest fingerprint does not match snapshots")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SpecInputManifest":
        return cls(
            fingerprint=str(value.get("fingerprint", "")),
            snapshots=tuple(InputSnapshot.from_dict(item) for item in value.get("snapshots", ())),
            created_at=str(value.get("created_at", "")),
            schema_version=str(value.get("schema_version", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }


def capture_spec_input_manifest(
    root: str | Path,
    *,
    obligation_ids: Sequence[str] = (),
) -> SpecInputManifest:
    project_root = _project_root(root)
    paths = discover_governed_input_paths(project_root)

    def snapshot(path: Path) -> InputSnapshot:
        return snapshot_file(
            f"source:{path.relative_to(project_root).as_posix()}",
            path,
            workspace_root=project_root,
            hash_policy=INPUT_HASH_BOTH,
            obligation_ids=obligation_ids,
        )

    workers = min(16, max(1, (os.cpu_count() or 4) * 2))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        snapshots = tuple(executor.map(snapshot, paths))
    return SpecInputManifest(
        fingerprint=fingerprint_value([snapshot.to_dict() for snapshot in snapshots]),
        snapshots=snapshots,
        created_at=_utc_now(),
    )


def _manifest_with_obligations(
    manifest: SpecInputManifest,
    obligation_ids: Sequence[str],
) -> SpecInputManifest:
    obligations = tuple(dict.fromkeys(str(value) for value in obligation_ids if str(value)))
    snapshots = tuple(
        InputSnapshot(
            artifact_id=item.artifact_id,
            path_token=item.path_token,
            hash_policy=item.hash_policy,
            raw_sha256=item.raw_sha256,
            semantic_sha256=item.semantic_sha256,
            obligation_ids=obligations,
        )
        for item in manifest.snapshots
    )
    return SpecInputManifest(
        fingerprint=fingerprint_value([item.to_dict() for item in snapshots]),
        snapshots=snapshots,
        created_at=manifest.created_at,
    )


def _manifest_changes(before: SpecInputManifest, after: SpecInputManifest) -> dict[str, list[str]]:
    before_rows = {item.artifact_id: item for item in before.snapshots}
    after_rows = {item.artifact_id: item for item in after.snapshots}
    return {
        "added": sorted(set(after_rows) - set(before_rows)),
        "removed": sorted(set(before_rows) - set(after_rows)),
        "changed": sorted(
            key
            for key in set(before_rows) & set(after_rows)
            if before_rows[key].to_dict() != after_rows[key].to_dict()
        ),
    }


def _save_manifest(root: Path, manifest: SpecInputManifest) -> str:
    path = _evidence_root(root) / "manifests" / f"{manifest.fingerprint.removeprefix('sha256:')}.json"
    if path.exists():
        existing = SpecInputManifest.from_dict(_read_json(path))
        if existing.fingerprint != manifest.fingerprint:
            raise ValueError("immutable manifest path contains different content")
    else:
        _atomic_json(path, manifest.to_dict())
    return path.relative_to(root).as_posix()


def _load_manifest(root: Path, path_token: str) -> SpecInputManifest:
    path = (root / path_token).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("manifest path escapes project root") from exc
    return SpecInputManifest.from_dict(_read_json(path))


def _session_pointer_path(root: Path, provider_id: str, work_package_id: str) -> Path:
    identity = f"{provider_id}:{work_package_id}"
    return _evidence_root(root) / "sessions" / f"{_safe_component(identity)}.json"


def _session_record_path(root: Path, session_id: str, stage: str) -> Path:
    return _evidence_root(root) / "sessions" / "history" / _safe_component(session_id) / f"{stage}.json"


def _save_immutable_session_record(root: Path, session_id: str, stage: str, value: Mapping[str, Any]) -> str:
    path = _session_record_path(root, session_id, stage)
    if path.exists():
        if _read_json(path) != dict(value):
            raise ValueError(f"immutable spec session {stage} record already exists with different content")
    else:
        _atomic_json(path, value)
    return path.relative_to(root).as_posix()


def _load_package(root: Path, provider_id: str, work_package_id: str) -> SpecWorkPackage:
    if provider_id == "openspec":
        return load_openspec_work_package(root, work_package_id)
    if provider_id == "speckit":
        return load_speckit_work_package(root, work_package_id)
    raise ValueError(f"unsupported spec provider: {provider_id}")


@dataclass(frozen=True)
class SpecSessionResult:
    provider_id: str
    work_package_id: str
    session_id: str
    state: str
    begin_fingerprint: str
    post_fingerprint: str = ""
    begin_manifest_path: str = ""
    post_manifest_path: str = ""
    begin_record_path: str = ""
    close_record_path: str = ""
    changed_inputs: Mapping[str, Sequence[str]] = field(default_factory=dict)
    check_states: Mapping[str, str] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.state in {"begun", "closed"} and not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SPEC_SESSION_SCHEMA,
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "session_id": self.session_id,
            "state": self.state,
            "ok": self.ok,
            "begin_fingerprint": self.begin_fingerprint,
            "post_fingerprint": self.post_fingerprint,
            "begin_manifest_path": self.begin_manifest_path,
            "post_manifest_path": self.post_manifest_path,
            "begin_record_path": self.begin_record_path,
            "close_record_path": self.close_record_path,
            "changed_inputs": {key: list(value) for key, value in self.changed_inputs.items()},
            "check_states": dict(self.check_states),
            "blockers": list(self.blockers),
        }


def begin_spec_session(root: str | Path, provider_id: str, work_package_id: str) -> SpecSessionResult:
    project_root = _project_root(root)
    package = _load_package(project_root, provider_id, work_package_id)
    review = review_spec_work_package(package)
    manifest = capture_spec_input_manifest(project_root)
    manifest_path = _save_manifest(project_root, manifest)
    session_id = f"session:{provider_id}:{work_package_id}:{uuid.uuid4().hex}"
    blockers = () if review.ok else tuple(review.finding_codes)
    value = {
        "schema_version": SPEC_SESSION_SCHEMA,
        "provider_id": provider_id,
        "work_package_id": work_package_id,
        "change_id": package.change_id,
        "session_id": session_id,
        "state": "begun" if not blockers else "blocked",
        "started_at": _utc_now(),
        "begin_manifest_path": manifest_path,
        "begin_fingerprint": manifest.fingerprint,
        "post_manifest_path": "",
        "post_fingerprint": "",
        "changed_inputs": {"added": [], "removed": [], "changed": []},
        "check_results": {},
        "blockers": list(blockers),
    }
    begin_record_path = _session_record_path(project_root, session_id, "begin").relative_to(project_root).as_posix()
    value["begin_record_path"] = begin_record_path
    value["close_record_path"] = ""
    _save_immutable_session_record(project_root, session_id, "begin", value)
    _atomic_json(_session_pointer_path(project_root, provider_id, work_package_id), value)
    return SpecSessionResult(
        provider_id=provider_id,
        work_package_id=work_package_id,
        session_id=session_id,
        state=str(value["state"]),
        begin_fingerprint=manifest.fingerprint,
        begin_manifest_path=manifest_path,
        begin_record_path=begin_record_path,
        blockers=blockers,
    )


def _load_session(root: Path, provider_id: str, work_package_id: str) -> dict[str, Any]:
    path = _session_pointer_path(root, provider_id, work_package_id)
    if not path.is_file():
        raise ValueError("no active spec session; run spec-session-begin first")
    value = _read_json(path)
    if value.get("schema_version") != SPEC_SESSION_SCHEMA:
        raise ValueError("unsupported spec session schema")
    if value.get("provider_id") != provider_id or value.get("work_package_id") != work_package_id:
        raise ValueError("spec session identity mismatch")
    return value


def _save_session(root: Path, provider_id: str, work_package_id: str, value: Mapping[str, Any]) -> None:
    _atomic_json(_session_pointer_path(root, provider_id, work_package_id), value)


@dataclass(frozen=True)
class SpecCheckExecutionResult:
    provider_id: str
    work_package_id: str
    check_id: str
    semantic_id: str
    state: str
    terminal_status: str
    receipt_id: str = ""
    receipt_fingerprint: str = ""
    execution_key: str = ""
    exit_code: int | None = None
    duration_seconds: float = 0.0
    dependency_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    stale_reasons: tuple[str, ...] = ()
    consumer_id: str = ""
    result_paths: Mapping[str, str] = field(default_factory=dict)
    session_id: str = ""
    begin_fingerprint: str = ""
    check_post_fingerprint: str = ""

    @property
    def ok(self) -> bool:
        return self.state in {SPEC_CHECK_STATE_EXECUTED, SPEC_CHECK_STATE_REUSED_CURRENT} and self.terminal_status == SPEC_TERMINAL_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SPEC_RECEIPT_SCHEMA,
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "check_id": self.check_id,
            "semantic_id": self.semantic_id,
            "state": self.state,
            "terminal_status": self.terminal_status,
            "ok": self.ok,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "execution_key": self.execution_key,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "dependency_ids": list(self.dependency_ids),
            "blockers": list(self.blockers),
            "stale_reasons": list(self.stale_reasons),
            "consumer_id": self.consumer_id,
            "result_paths": dict(self.result_paths),
            "session_id": self.session_id,
            "begin_fingerprint": self.begin_fingerprint,
            "check_post_fingerprint": self.check_post_fingerprint,
        }


def _record_check_result(root: Path, result: SpecCheckExecutionResult) -> None:
    session = _load_session(root, result.provider_id, result.work_package_id)
    rows = dict(session.get("check_results", {}))
    rows[result.check_id] = result.to_dict()
    session["check_results"] = rows
    _save_session(root, result.provider_id, result.work_package_id, session)


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _tool_fingerprint(command: Sequence[str]) -> tuple[dict[str, str], str]:
    tokens = tuple(str(value) for value in command)
    metadata = {
        "python": platform.python_version(),
        "flowguard": _version("flowguard"),
    }
    lowered = {value.casefold() for value in tokens}
    if "pytest" in lowered or any("pytest" in value for value in lowered):
        metadata["pytest"] = _version("pytest")
    if tokens and Path(tokens[0]).name.casefold().startswith("openspec"):
        try:
            observed = subprocess.run(
                [tokens[0], "--version"],
                cwd=None,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            metadata["openspec"] = (observed.stdout or observed.stderr).strip()[:120] or "unknown"
        except (OSError, subprocess.SubprocessError):
            metadata["openspec"] = "unavailable"
    return metadata, fingerprint_value(metadata)


def _definition(
    *,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    semantic_id: str,
    command: Sequence[str],
    working_directory_token: str,
    expected_exit_code: int,
    timeout_seconds: int,
    cross_change_safe: bool,
    validation_obligation_ids: Sequence[str],
    coverage: Sequence[str],
    input_fingerprint: str,
    environment_fingerprint: str,
    tool_fingerprint: str,
) -> dict[str, Any]:
    scope = {"cross_change_safe": bool(cross_change_safe)}
    if not cross_change_safe:
        scope.update({"provider_id": provider_id, "work_package_id": work_package_id})
    return {
        "semantic_id": semantic_id,
        "check_id_role": check_id if not cross_change_safe else "consumer-local",
        "command": list(command),
        "working_directory_token": working_directory_token,
        "expected_exit_code": expected_exit_code,
        "timeout_seconds": timeout_seconds,
        "validation_obligation_ids": sorted(set(validation_obligation_ids)),
        "coverage": sorted(set(coverage)),
        "input_fingerprint": input_fingerprint,
        "environment_fingerprint": environment_fingerprint,
        "tool_fingerprint": tool_fingerprint,
        "mutation_policy": "governed-inputs-must-be-unchanged",
        "scope": scope,
    }


def _result_fingerprint(exit_code: int, terminal_status: str, stdout: bytes, stderr: bytes) -> str:
    return fingerprint_value(
        {
            "exit_code": exit_code,
            "terminal_status": terminal_status,
            "stdout_sha256": _sha256_bytes(stdout),
            "stderr_sha256": _sha256_bytes(stderr),
        }
    )


def _result_files_fingerprint(root: Path, receipt: EvidenceReceipt) -> str:
    metadata = dict(receipt.metadata)
    result_files = metadata.get("result_files", {})
    if not isinstance(result_files, Mapping):
        return ""
    try:
        stdout_path = (root / str(result_files.get("stdout", ""))).resolve()
        stderr_path = (root / str(result_files.get("stderr", ""))).resolve()
        stdout_path.relative_to(root)
        stderr_path.relative_to(root)
        stdout = stdout_path.read_bytes()
        stderr = stderr_path.read_bytes()
    except (OSError, ValueError):
        return ""
    terminal_status = str(metadata.get("terminal_status", ""))
    return _result_fingerprint(receipt.exit_code, terminal_status, stdout, stderr)


def _receipt_context(
    root: Path,
    receipt: EvidenceReceipt,
    *,
    manifest: SpecInputManifest,
    definition_hash: str,
    suite_map_hash: str,
    producer_version: str,
    environment_fingerprint: str,
    command: tuple[str, ...],
    working_directory_token: str,
    validation_obligation_ids: tuple[str, ...],
) -> ReceiptVerificationContext:
    result_fingerprint = _result_files_fingerprint(root, receipt)
    return ReceiptVerificationContext(
        input_snapshots={item.artifact_id: item for item in manifest.snapshots},
        contract_hash=definition_hash,
        check_manifest_hash=definition_hash,
        suite_map_hash=suite_map_hash,
        producer_id="flowguard.spec_check_cache",
        producer_version=producer_version,
        environment_fingerprint=environment_fingerprint,
        proof_artifact_fingerprint=result_fingerprint,
        result_fingerprint=result_fingerprint,
        command=command,
        working_directory_token=working_directory_token,
        proof_artifact_id=receipt.proof_artifact_id,
        required_obligation_ids=validation_obligation_ids,
        eligible_claim_scopes=(SPEC_CHECK_CLAIM_SCOPE,),
    )


def _receipt_directory(root: Path) -> Path:
    return _evidence_root(root) / "receipts"


def _find_reusable_receipt(
    root: Path,
    *,
    execution_key: str,
    manifest: SpecInputManifest,
    definition_hash: str,
    suite_map_hash: str,
    producer_version: str,
    environment_fingerprint: str,
    command: tuple[str, ...],
    working_directory_token: str,
    validation_obligation_ids: tuple[str, ...],
) -> tuple[EvidenceReceipt | None, tuple[str, ...]]:
    stale_reasons: list[str] = []
    for receipt in reversed(list_evidence_receipts(root, output_directory=_receipt_directory(root))):
        metadata = dict(receipt.metadata)
        if metadata.get("execution_key") != execution_key:
            continue
        required_session_fields = (
            "session_id",
            "begin_manifest_path",
            "begin_fingerprint",
            "check_post_manifest_path",
            "check_post_fingerprint",
            "command_fingerprint",
            "tool_fingerprint",
        )
        missing_session_fields = tuple(
            field_name for field_name in required_session_fields if not str(metadata.get(field_name, ""))
        )
        if missing_session_fields:
            stale_reasons.extend(f"receipt_binding_missing:{field_name}" for field_name in missing_session_fields)
            continue
        if metadata.get("begin_fingerprint") != metadata.get("check_post_fingerprint"):
            stale_reasons.append("receipt_session_fingerprint_mismatch")
            continue
        context = _receipt_context(
            root,
            receipt,
            manifest=manifest,
            definition_hash=definition_hash,
            suite_map_hash=suite_map_hash,
            producer_version=producer_version,
            environment_fingerprint=environment_fingerprint,
            command=command,
            working_directory_token=working_directory_token,
            validation_obligation_ids=validation_obligation_ids,
        )
        review = verify_evidence_receipt(receipt, context)
        if review.ok:
            return receipt, ()
        stale_reasons.extend(review.finding_codes)
    return None, tuple(dict.fromkeys(stale_reasons))


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # On Windows ``os.kill(pid, 0)`` is not a POSIX-style probe: Python
        # delegates non-CTRL signals to TerminateProcess.  Query the process
        # handle instead so lock inspection can never terminate a peer.
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        except (AttributeError, OSError, ValueError):
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class _ExecutionLock:
    def __init__(self, root: Path, execution_key: str, *, stale_after_seconds: int = 14400) -> None:
        self.path = _evidence_root(root) / "locks" / f"{execution_key.removeprefix('sha256:')}.lock"
        self.stale_after_seconds = stale_after_seconds
        self.recovered_path = ""

    def __enter__(self) -> "_ExecutionLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                existing = _read_json(self.path)
                pid = int(existing.get("pid", 0))
                age = time.time() - self.path.stat().st_mtime
            except (OSError, ValueError):
                pid, age = 0, self.stale_after_seconds + 1
            if _pid_alive(pid) or age <= self.stale_after_seconds:
                raise RuntimeError("identical spec check is already executing")
            abandoned = self.path.with_suffix(f".abandoned-{int(time.time())}.json")
            os.replace(self.path, abandoned)
            self.recovered_path = abandoned.name
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"pid": os.getpid(), "started_at": _utc_now(), "recovered": self.recovered_path}, handle, sort_keys=True)
            handle.write("\n")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _write_output_files(root: Path, execution_key: str, run_id: str, stdout: bytes, stderr: bytes) -> dict[str, str]:
    output = _evidence_root(root) / "outputs" / execution_key.removeprefix("sha256:") / run_id
    output.mkdir(parents=True, exist_ok=False)
    stdout_path = output / "stdout.log"
    stderr_path = output / "stderr.log"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    return {
        "stdout": stdout_path.relative_to(root).as_posix(),
        "stderr": stderr_path.relative_to(root).as_posix(),
    }


def run_spec_check(
    root: str | Path,
    *,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    semantic_id: str,
    command: Sequence[str],
    validation_obligation_ids: Sequence[str],
    coverage: Sequence[str] = (),
    depends_on: Sequence[str] = (),
    timeout_seconds: int = 1800,
    expected_exit_code: int = 0,
    cross_change_safe: bool = False,
    working_directory: str | Path = ".",
) -> SpecCheckExecutionResult:
    """Execute once or consume one independently reverified immutable receipt."""

    project_root = _project_root(root)
    consumer_id = f"consumer:{provider_id}:{work_package_id}:{check_id}"
    dependency_ids = tuple(dict.fromkeys(str(value) for value in depends_on if str(value)))
    if not command:
        raise ValueError("spec check command is required")
    if not semantic_id:
        raise ValueError("semantic_id is required")
    if not validation_obligation_ids:
        raise ValueError("validation_obligation_ids are required")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    session = _load_session(project_root, provider_id, work_package_id)
    package = _load_package(project_root, provider_id, work_package_id)
    declared_check = next((item for item in package.checks if item.check_id == check_id), None)
    if declared_check is None:
        raise ValueError(f"check is not declared by the provider work package: {check_id}")
    if cross_change_safe and not declared_check.cross_change_safe:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            blockers=("cross_change_safe_not_authorized_by_provider",),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
        )
        _record_check_result(project_root, result)
        return result
    if session.get("state") != "begun":
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            dependency_ids=dependency_ids,
            blockers=("spec_session_not_active",),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
        )
        return result
    recorded = session.get("check_results", {})
    unsatisfied = tuple(
        dependency
        for dependency in dependency_ids
        if not isinstance(recorded.get(dependency), Mapping) or not bool(recorded[dependency].get("ok", False))
    )
    if unsatisfied:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_id,
            SPEC_CHECK_STATE_NOT_RUN,
            SPEC_TERMINAL_NOT_RUN_DEPENDENCY,
            dependency_ids=dependency_ids,
            blockers=tuple(f"dependency_not_passed:{item}" for item in unsatisfied),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
        )
        _record_check_result(project_root, result)
        return result

    begin = _load_manifest(project_root, str(session["begin_manifest_path"]))
    session_current = capture_spec_input_manifest(project_root)
    if session_current.fingerprint != begin.fingerprint:
        changes = _manifest_changes(begin, session_current)
        reasons = tuple(f"session_input_{kind}:{item}" for kind, items in changes.items() for item in items)
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_id,
            SPEC_CHECK_STATE_STALE,
            SPEC_TERMINAL_BLOCKED,
            dependency_ids=dependency_ids,
            blockers=("session_inputs_changed_before_check",),
            stale_reasons=reasons,
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
        )
        _record_check_result(project_root, result)
        return result
    current = _manifest_with_obligations(session_current, validation_obligation_ids)

    cwd = Path(working_directory)
    if not cwd.is_absolute():
        cwd = project_root / cwd
    cwd = cwd.resolve()
    try:
        cwd.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("spec check working directory escapes project root") from exc
    command_tokens = tokenize_command(command, workspace_root=project_root)
    cwd_token = tokenize_path(cwd, workspace_root=project_root)
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _version("flowguard"),
        }
    )
    tools, tools_hash = _tool_fingerprint(command)
    validation_ids = tuple(sorted(set(str(value) for value in validation_obligation_ids)))
    coverage_ids = tuple(sorted(set(str(value) for value in coverage if str(value))))
    definition = _definition(
        provider_id=provider_id,
        work_package_id=work_package_id,
        check_id=check_id,
        semantic_id=semantic_id,
        command=command_tokens,
        working_directory_token=cwd_token,
        expected_exit_code=expected_exit_code,
        timeout_seconds=timeout_seconds,
        cross_change_safe=cross_change_safe,
        validation_obligation_ids=validation_ids,
        coverage=coverage_ids,
        input_fingerprint=session_current.fingerprint,
        environment_fingerprint=environment.fingerprint,
        tool_fingerprint=tools_hash,
    )
    execution_key = fingerprint_value(definition)
    definition_hash = fingerprint_value({key: value for key, value in definition.items() if key != "input_fingerprint"})
    suite_map_hash = fingerprint_value({"validation_obligations": validation_ids, "coverage": coverage_ids})
    producer_version = _version("flowguard")
    reusable, stale_reasons = _find_reusable_receipt(
        project_root,
        execution_key=execution_key,
        manifest=current,
        definition_hash=definition_hash,
        suite_map_hash=suite_map_hash,
        producer_version=producer_version,
        environment_fingerprint=environment.fingerprint,
        command=command_tokens,
        working_directory_token=cwd_token,
        validation_obligation_ids=validation_ids,
    )
    if reusable is not None:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_id,
            SPEC_CHECK_STATE_REUSED_CURRENT,
            SPEC_TERMINAL_PASS,
            receipt_id=reusable.receipt_id,
            receipt_fingerprint=reusable.fingerprint,
            execution_key=execution_key,
            exit_code=reusable.exit_code,
            dependency_ids=dependency_ids,
            consumer_id=consumer_id,
            result_paths=dict(reusable.metadata).get("result_files", {}),
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=begin.fingerprint,
            check_post_fingerprint=session_current.fingerprint,
        )
        _record_check_result(project_root, result)
        return result

    try:
        with _ExecutionLock(project_root, execution_key) as lock:
            # Another process may have completed while this process acquired the lock.
            reusable, refreshed_stale = _find_reusable_receipt(
                project_root,
                execution_key=execution_key,
                manifest=current,
                definition_hash=definition_hash,
                suite_map_hash=suite_map_hash,
                producer_version=producer_version,
                environment_fingerprint=environment.fingerprint,
                command=command_tokens,
                working_directory_token=cwd_token,
                validation_obligation_ids=validation_ids,
            )
            if reusable is not None:
                result = SpecCheckExecutionResult(
                    provider_id,
                    work_package_id,
                    check_id,
                    semantic_id,
                    SPEC_CHECK_STATE_REUSED_CURRENT,
                    SPEC_TERMINAL_PASS,
                    receipt_id=reusable.receipt_id,
                    receipt_fingerprint=reusable.fingerprint,
                    execution_key=execution_key,
                    exit_code=reusable.exit_code,
                    dependency_ids=dependency_ids,
                    consumer_id=consumer_id,
                    result_paths=dict(reusable.metadata).get("result_files", {}),
                    session_id=str(session.get("session_id", "")),
                    begin_fingerprint=begin.fingerprint,
                    check_post_fingerprint=session_current.fingerprint,
                )
                _record_check_result(project_root, result)
                return result
            stale_reasons = tuple(dict.fromkeys(stale_reasons + refreshed_stale))
            started_at = _utc_now()
            started_clock = time.monotonic()
            terminal_status = SPEC_TERMINAL_ERROR
            exit_code = -1
            stdout = b""
            stderr = b""
            blockers: list[str] = []
            try:
                completed = subprocess.run(
                    [str(value) for value in command],
                    cwd=cwd,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                stdout = completed.stdout or b""
                stderr = completed.stderr or b""
                exit_code = int(completed.returncode)
                terminal_status = SPEC_TERMINAL_PASS if exit_code == expected_exit_code else SPEC_TERMINAL_FAIL
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                exit_code = -1
                terminal_status = SPEC_TERMINAL_TIMEOUT
                blockers.append("check_timeout")
            except OSError as exc:
                stderr = str(exc).encode("utf-8", errors="replace")
                exit_code = -1
                terminal_status = SPEC_TERMINAL_ERROR
                blockers.append("check_execution_error")
            finished_at = _utc_now()
            duration = time.monotonic() - started_clock
            after = capture_spec_input_manifest(project_root)
            check_post_manifest_path = _save_manifest(project_root, after)
            changes = _manifest_changes(session_current, after)
            mutated = any(changes.values())
            if mutated:
                terminal_status = SPEC_TERMINAL_BLOCKED
                blockers.append("check_input_changed_during_run")
            run_id = uuid.uuid4().hex
            result_paths = _write_output_files(project_root, execution_key, run_id, stdout, stderr)
            result_hash = _result_fingerprint(exit_code, terminal_status, stdout, stderr)
            receipt_status = {
                SPEC_TERMINAL_PASS: RECEIPT_STATUS_PASS,
                SPEC_TERMINAL_FAIL: RECEIPT_STATUS_FAIL,
                SPEC_TERMINAL_TIMEOUT: RECEIPT_STATUS_ERROR,
                SPEC_TERMINAL_BLOCKED: RECEIPT_STATUS_BLOCKED,
                SPEC_TERMINAL_ERROR: RECEIPT_STATUS_ERROR,
            }[terminal_status]
            receipt = EvidenceReceipt(
                receipt_id=f"spec-check:{execution_key.removeprefix('sha256:')[:20]}:{run_id}",
                subject_id=semantic_id,
                subject_kind="spec_check_execution",
                producer_id="flowguard.spec_check_cache",
                producer_version=producer_version,
                claim_scope=SPEC_CHECK_CLAIM_SCOPE,
                command=command_tokens,
                working_directory_token=cwd_token,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                environment_fingerprint=environment.fingerprint,
                environment_metadata=environment.metadata,
                contract_hash=definition_hash,
                check_manifest_hash=definition_hash,
                suite_map_hash=suite_map_hash,
                input_snapshots=current.snapshots,
                proof_artifact_id=f"spec-check-proof:{execution_key.removeprefix('sha256:')}",
                proof_artifact_fingerprint=result_hash,
                result_status=receipt_status,
                result_fingerprint=result_hash,
                covered_obligations=validation_ids,
                blockers=tuple(blockers),
                claim_boundary=(
                    "Execution receipt for stable validation obligations only; provider-specific tasks and archive state "
                    "are attached through consumer bindings."
                ),
                metadata={
                    "schema_version": SPEC_RECEIPT_SCHEMA,
                    "execution_key": execution_key,
                    "semantic_id": semantic_id,
                    "cross_change_safe": cross_change_safe,
                    "coverage": list(coverage_ids),
                    "tool_versions": tools,
                    "tool_fingerprint": tools_hash,
                    "terminal_status": terminal_status,
                    "result_files": result_paths,
                    "changed_inputs": changes,
                    "recovered_abandoned_lock": lock.recovered_path,
                    "session_id": str(session.get("session_id", "")),
                    "begin_manifest_path": str(session.get("begin_manifest_path", "")),
                    "begin_fingerprint": begin.fingerprint,
                    "check_post_manifest_path": check_post_manifest_path,
                    "check_post_fingerprint": after.fingerprint,
                    "command_fingerprint": fingerprint_value(list(command_tokens)),
                },
            )
            save_evidence_receipt(receipt, project_root, output_directory=_receipt_directory(project_root))
            state = SPEC_CHECK_STATE_EXECUTED if terminal_status == SPEC_TERMINAL_PASS else SPEC_CHECK_STATE_BLOCKED
            result = SpecCheckExecutionResult(
                provider_id,
                work_package_id,
                check_id,
                semantic_id,
                state,
                terminal_status,
                receipt_id=receipt.receipt_id,
                receipt_fingerprint=receipt.fingerprint,
                execution_key=execution_key,
                exit_code=exit_code,
                duration_seconds=duration,
                dependency_ids=dependency_ids,
                blockers=tuple(blockers),
                stale_reasons=tuple(
                    dict.fromkeys(
                        stale_reasons
                        + tuple(f"input_{kind}:{item}" for kind, items in changes.items() for item in items)
                    )
                ),
                consumer_id=consumer_id,
                result_paths=result_paths,
                session_id=str(session.get("session_id", "")),
                begin_fingerprint=begin.fingerprint,
                check_post_fingerprint=after.fingerprint,
            )
            _record_check_result(project_root, result)
            return result
    except RuntimeError as exc:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            execution_key=execution_key,
            dependency_ids=dependency_ids,
            blockers=(str(exc),),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=begin.fingerprint,
            check_post_fingerprint=session_current.fingerprint,
        )
        _record_check_result(project_root, result)
        return result


def close_spec_session(root: str | Path, provider_id: str, work_package_id: str) -> SpecSessionResult:
    project_root = _project_root(root)
    session = _load_session(project_root, provider_id, work_package_id)
    begin = _load_manifest(project_root, str(session["begin_manifest_path"]))
    post = capture_spec_input_manifest(project_root)
    post_path = _save_manifest(project_root, post)
    changes = _manifest_changes(begin, post)
    package = _load_package(project_root, provider_id, work_package_id)
    review = review_spec_work_package(package)
    check_results = session.get("check_results", {})
    excluded = {"check.session.begin", "check.session.close"}
    required_checks = {item.check_id for item in package.checks if item.required and item.check_id not in excluded}
    missing = sorted(required_checks - set(check_results))
    nonpassing = sorted(
        check_id
        for check_id in required_checks & set(check_results)
        if not isinstance(check_results.get(check_id), Mapping) or not bool(check_results[check_id].get("ok", False))
    )
    incomplete_tasks = tuple(task.task_id for task in package.tasks if not task.completed)
    blockers: list[str] = []
    if begin.fingerprint != post.fingerprint:
        blockers.append("session_inputs_changed")
    if not review.ok:
        blockers.extend(review.finding_codes)
    blockers.extend(f"required_check_missing:{check_id}" for check_id in missing)
    blockers.extend(f"required_check_not_passed:{check_id}" for check_id in nonpassing)
    blockers.extend(f"provider_task_incomplete:{task_id}" for task_id in incomplete_tasks)
    state = "closed" if not blockers else "blocked"
    session.update(
        {
            "state": state,
            "finished_at": _utc_now(),
            "post_manifest_path": post_path,
            "post_fingerprint": post.fingerprint,
            "changed_inputs": changes,
            "blockers": blockers,
        }
    )
    close_record = dict(session)
    close_record_path = _session_record_path(
        project_root, str(session["session_id"]), "close"
    ).relative_to(project_root).as_posix()
    close_record["close_record_path"] = close_record_path
    session["close_record_path"] = close_record_path
    _save_immutable_session_record(project_root, str(session["session_id"]), "close", close_record)
    _save_session(project_root, provider_id, work_package_id, session)
    return SpecSessionResult(
        provider_id=provider_id,
        work_package_id=work_package_id,
        session_id=str(session["session_id"]),
        state=state,
        begin_fingerprint=begin.fingerprint,
        post_fingerprint=post.fingerprint,
        begin_manifest_path=str(session.get("begin_manifest_path", "")),
        post_manifest_path=post_path,
        begin_record_path=str(session.get("begin_record_path", "")),
        close_record_path=close_record_path,
        changed_inputs=changes,
        check_states={key: str(value.get("state", "")) for key, value in check_results.items() if isinstance(value, Mapping)},
        blockers=tuple(blockers),
    )


def spec_receipt_to_proof_artifact(receipt: EvidenceReceipt, *, result_path: str = "") -> ProofArtifactRef:
    """Project an immutable receipt; the receipt remains the freshness authority."""

    metadata = dict(receipt.metadata)
    return ProofArtifactRef(
        artifact_id=receipt.proof_artifact_id,
        producer_route=receipt.producer_id,
        command=" ".join(receipt.command),
        result_path=result_path,
        result_status=PROOF_ARTIFACT_STATUS_PASSED if receipt.result_status == RECEIPT_STATUS_PASS else receipt.result_status,
        exit_code=receipt.exit_code,
        started_at=receipt.started_at,
        finished_at=receipt.finished_at,
        artifact_fingerprints={
            "receipt": receipt.fingerprint,
            "result": receipt.result_fingerprint,
            "inputs": fingerprint_value([item.to_dict() for item in receipt.input_snapshots]),
            "session_begin": str(metadata.get("begin_fingerprint", "")),
            "session_post": str(metadata.get("check_post_fingerprint", "")),
            "command": str(metadata.get("command_fingerprint", "")),
            "tool": str(metadata.get("tool_fingerprint", "")),
            "environment": receipt.environment_fingerprint,
        },
        covered_obligation_ids=receipt.covered_obligations,
        assertion_scope=PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
        current=False,
        route_evidence_current=False,
        metadata={
            "receipt_id": receipt.receipt_id,
            "session_id": str(metadata.get("session_id", "")),
            "begin_manifest_path": str(metadata.get("begin_manifest_path", "")),
            "check_post_manifest_path": str(metadata.get("check_post_manifest_path", "")),
            "requires_independent_receipt_verification": True,
        },
    )


def verified_spec_receipt_to_reuse_ticket(
    receipt: EvidenceReceipt,
    context: ReceiptVerificationContext,
    *,
    evidence_id: str,
) -> TestResultReuseTicket:
    """Create a reuse ticket only after exact independent receipt verification."""

    review = verify_evidence_receipt(receipt, context)
    if not review.ok:
        raise ValueError(f"spec receipt is not reusable: {','.join(review.finding_codes)}")
    input_fingerprint = fingerprint_value([item.to_dict() for item in receipt.input_snapshots])
    metadata = dict(receipt.metadata)
    return TestResultReuseTicket(
        evidence_id=evidence_id,
        previous_evidence_id=receipt.receipt_id,
        reason="Exact immutable spec-check receipt independently reverified against current inputs.",
        same_output_proof_id=receipt.proof_artifact_id,
        command_fingerprint=fingerprint_value(list(receipt.command)),
        test_source_fingerprint=input_fingerprint,
        tested_artifact_fingerprint=input_fingerprint,
        dependency_fingerprints={
            "receipt": receipt.fingerprint,
            "session_begin": str(metadata.get("begin_fingerprint", "")),
            "session_post": str(metadata.get("check_post_fingerprint", "")),
            "tool": str(metadata.get("tool_fingerprint", "")),
        },
        environment_fingerprint=receipt.environment_fingerprint,
        result_fingerprint=receipt.result_fingerprint,
        covered_obligation_ids=receipt.covered_obligations,
        metadata={
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.fingerprint,
            "session_id": str(metadata.get("session_id", "")),
            "begin_manifest_path": str(metadata.get("begin_manifest_path", "")),
            "check_post_manifest_path": str(metadata.get("check_post_manifest_path", "")),
        },
    )


__all__ = [
    "SPEC_CHECK_CLAIM_SCOPE",
    "SPEC_CHECK_STATE_BLOCKED",
    "SPEC_CHECK_STATE_EXECUTED",
    "SPEC_CHECK_STATE_NOT_RUN",
    "SPEC_CHECK_STATE_REUSED_CURRENT",
    "SPEC_CHECK_STATE_STALE",
    "SPEC_CHECK_STATES",
    "SPEC_EVIDENCE_ROOT",
    "SPEC_MANIFEST_SCHEMA",
    "SPEC_RECEIPT_SCHEMA",
    "SPEC_SESSION_SCHEMA",
    "SPEC_TERMINAL_BLOCKED",
    "SPEC_TERMINAL_ERROR",
    "SPEC_TERMINAL_FAIL",
    "SPEC_TERMINAL_NOT_RUN_DEPENDENCY",
    "SPEC_TERMINAL_PASS",
    "SPEC_TERMINAL_TIMEOUT",
    "SpecCheckExecutionResult",
    "SpecInputManifest",
    "SpecSessionResult",
    "begin_spec_session",
    "capture_spec_input_manifest",
    "close_spec_session",
    "discover_governed_input_paths",
    "run_spec_check",
    "spec_receipt_to_proof_artifact",
    "verified_spec_receipt_to_reuse_ticket",
]
