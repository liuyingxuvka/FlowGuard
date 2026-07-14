"""Exact spec-check sessions, immutable receipts, and safe result reuse."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
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
    ChildReceiptRequirement,
    ConsumedChildReceipt,
    INPUT_HASH_BOTH,
    INPUT_HASH_SEMANTIC,
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
    load_evidence_receipt,
    save_evidence_receipt,
    snapshot_file,
    snapshot_bytes,
    tokenize_command,
    tokenize_path,
    verify_evidence_receipt,
)
from .proof_artifact import (
    PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
    PROOF_ARTIFACT_STATUS_PASSED,
    ProofArtifactRef,
)
from .spec_providers import (
    load_openspec_canonical_checks,
    load_openspec_work_package,
    load_speckit_work_package,
    normalize_provider_task_definition_bytes,
)
from .spec_work_package import (
    SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS,
    SPEC_SNAPSHOT_FROZEN_REQUIRED,
    SPEC_SNAPSHOT_LIVE_SCOPED,
    SPEC_SNAPSHOT_POLICIES,
    SpecWorkPackage,
    review_spec_work_package,
)
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
SPEC_EVIDENCE_ROOT_ENV = "FLOWGUARD_SPEC_EVIDENCE_ROOT"
SPEC_RECEIPT_SCHEMA = "spec-check-receipt.v1"
SPEC_SESSION_SCHEMA = "spec-work-package-session.v1"
SPEC_MANIFEST_SCHEMA = "spec-governed-input-manifest.v1"
SPEC_TOOLCHAIN_SCHEMA = "spec-toolchain-snapshot.v1"
SPEC_PORTABLE_RECEIPT_SCHEMA = "portable-receipt-envelope.v1"
SPEC_PORTABLE_SOURCE_MANIFEST_SCHEMA = "portable-source-manifest.v1"
SPEC_PORTABLE_RECEIPT_PROTOCOL = 1
SPEC_EVIDENCE_ROOT_TOKEN = "<SPEC_EVIDENCE>"

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


_EVIDENCE_REF = re.compile(r"^<[A-Z][A-Z0-9_]*_EVIDENCE>/(.+)$")


def _is_evidence_ref(value: str) -> bool:
    match = _EVIDENCE_REF.fullmatch(str(value))
    if match is None:
        return False
    relative = match.group(1)
    return bool(relative) and "\\" not in relative and ".." not in relative.split("/")


def _project_root(root: str | Path) -> Path:
    candidate = Path(root).expanduser().resolve()
    if not candidate.is_dir():
        raise ValueError(f"project root does not exist: {candidate}")
    return candidate


def _evidence_root(root: Path) -> Path:
    configured = os.environ.get("FLOWGUARD_SPEC_EVIDENCE_ROOT", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            raise ValueError("FLOWGUARD_SPEC_EVIDENCE_ROOT must be an absolute persistent path")
        return candidate.resolve()
    return root / SPEC_EVIDENCE_ROOT


def _evidence_token(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        evidence_root = _evidence_root(root).resolve()
        try:
            relative = resolved.relative_to(evidence_root)
        except ValueError as exc:
            raise ValueError("evidence path is outside both source and configured evidence roots") from exc
        return f"<SPEC_EVIDENCE>/{relative.as_posix()}"


def _resolve_evidence_token(root: Path, path_token: str) -> Path:
    match = _EVIDENCE_REF.fullmatch(path_token)
    if match is not None:
        if not _is_evidence_ref(path_token):
            raise ValueError("evidence path token is unsafe")
        path = (_evidence_root(root) / match.group(1)).resolve()
        path.relative_to(_evidence_root(root).resolve())
        return path
    path = (root / path_token).resolve()
    path.relative_to(root)
    return path


def _portable_evidence_token(root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(_evidence_root(root).resolve())
    return f"{SPEC_EVIDENCE_ROOT_TOKEN}/{relative.as_posix()}"


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
        return path.suffix.casefold() in {".md", ".yaml", ".yml", ".json"}
    if top in {"flowguard", "examples", "scripts", "tests"}:
        return path.suffix.casefold() == ".py"
    if top == "docs":
        return path.suffix.casefold() in {".md", ".json", ".yaml", ".yml"}
    return False


def _normalize_input_patterns(input_paths: Sequence[str]) -> tuple[str, ...]:
    patterns: list[str] = []
    for raw_value in input_paths:
        value = str(raw_value).strip().replace("\\", "/")
        if not value:
            continue
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"input scope escapes project root: {value}")
        patterns.append(value.removeprefix("./"))
    return tuple(dict.fromkeys(patterns))


def _path_matches_input_scope(path_token: str, input_paths: Sequence[str]) -> bool:
    patterns = _normalize_input_patterns(input_paths)
    if not patterns:
        return True
    normalized = path_token.replace("\\", "/")
    return any(re.fullmatch(_globstar_pattern(pattern), normalized) is not None for pattern in patterns)


def _globstar_pattern(pattern: str) -> str:
    """Compile slash-stable, case-sensitive globstar semantics.

    ``**/`` matches zero or more complete directory levels, ``**`` matches
    zero or more characters across separators, and ``*``/``?`` never cross a
    slash.  The policy is intentionally case-sensitive on every platform so a
    cache identity does not change between Windows and POSIX hosts.
    """

    normalized = str(pattern).replace("\\", "/")
    output: list[str] = []
    index = 0
    while index < len(normalized):
        character = normalized[index]
        if character == "*":
            if index + 1 < len(normalized) and normalized[index + 1] == "*":
                index += 2
                if index < len(normalized) and normalized[index] == "/":
                    output.append("(?:.*/)?")
                    index += 1
                else:
                    output.append(".*")
                continue
            output.append("[^/]*")
        elif character == "?":
            output.append("[^/]")
        else:
            output.append(re.escape(character))
        index += 1
    return "".join(output)


def discover_governed_input_paths(
    root: str | Path,
    *,
    input_paths: Sequence[str] = (),
) -> tuple[Path, ...]:
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
                and not (".skillguard" in lowered)
            ]
            candidates.extend(current_path / name for name in filenames)
    patterns = _normalize_input_patterns(input_paths)
    paths = tuple(
        sorted(
            (
                path
                for path in candidates
                if path.is_file()
                and _is_governed_path(project_root, path)
                and _path_matches_input_scope(path.relative_to(project_root).as_posix(), patterns)
            ),
            key=lambda item: item.relative_to(project_root).as_posix(),
        )
    )
    if not paths:
        if patterns:
            raise ValueError(
                "declared spec-check input scope matched no governed source inputs: "
                + ",".join(patterns)
            )
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
    input_paths: Sequence[str] = (),
    normalize_provider_tasks: bool = False,
) -> SpecInputManifest:
    project_root = _project_root(root)
    paths = discover_governed_input_paths(project_root, input_paths=input_paths)

    def snapshot(path: Path) -> InputSnapshot:
        relative = path.relative_to(project_root).as_posix()
        if normalize_provider_tasks and (
            relative.startswith("openspec/changes/") or relative.startswith("specs/")
        ) and path.name == "tasks.md":
            return snapshot_bytes(
                f"source:{relative}",
                normalize_provider_task_definition_bytes(path.read_bytes()),
                path_token=tokenize_path(path, workspace_root=project_root),
                hash_policy=INPUT_HASH_SEMANTIC,
                obligation_ids=obligation_ids,
            )
        return snapshot_file(
            f"source:{relative}",
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


@dataclass(frozen=True)
class SpecToolchainSnapshot:
    fingerprint: str
    metadata: Mapping[str, str]
    schema_version: str = SPEC_TOOLCHAIN_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "fingerprint", str(self.fingerprint))
        object.__setattr__(self, "metadata", dict(sorted((str(k), str(v)) for k, v in self.metadata.items())))
        if self.schema_version != SPEC_TOOLCHAIN_SCHEMA:
            raise ValueError(f"unsupported toolchain snapshot schema: {self.schema_version}")
        if self.fingerprint != fingerprint_value(dict(self.metadata)):
            raise ValueError("toolchain snapshot fingerprint does not match metadata")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SpecToolchainSnapshot":
        return cls(
            fingerprint=str(value.get("fingerprint", "")),
            metadata=value.get("metadata", {}),
            schema_version=str(value.get("schema_version", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "metadata": dict(self.metadata),
        }


def capture_spec_toolchain_snapshot(package: SpecWorkPackage) -> SpecToolchainSnapshot:
    metadata = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "flowguard_version": _version("flowguard"),
        "provider_id": package.provider.provider_id,
        "provider_version": package.provider.provider_version,
        "provider_schema_version": package.provider.schema_version,
        "provider_adapter_version": package.provider.adapter_version,
    }
    return SpecToolchainSnapshot(fingerprint=fingerprint_value(metadata), metadata=metadata)


_PROVIDER_LOCAL_TOOLCHAIN_FIELDS = frozenset(
    {
        "provider_id",
        "provider_version",
        "provider_schema_version",
        "provider_adapter_version",
    }
)


def project_execution_toolchain_snapshot(
    snapshot: SpecToolchainSnapshot,
    *,
    cross_change_safe: bool,
) -> SpecToolchainSnapshot:
    """Project the toolchain identity actually consumed by one physical owner.

    Provider adapter/schema metadata belongs to a consumer projection.  A
    declared cross-change-safe FlowGuard owner does not execute that adapter,
    so coupling those fields to its execution identity would make a provider
    task/contract edit spuriously rerun the physical check.
    """

    if not cross_change_safe:
        return snapshot
    metadata = {
        key: value
        for key, value in snapshot.metadata.items()
        if key not in _PROVIDER_LOCAL_TOOLCHAIN_FIELDS
    }
    return SpecToolchainSnapshot(fingerprint=fingerprint_value(metadata), metadata=metadata)


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


def _manifest_subset(
    manifest: SpecInputManifest,
    input_paths: Sequence[str],
) -> SpecInputManifest:
    patterns = _normalize_input_patterns(input_paths)
    if not patterns:
        return manifest
    snapshots = tuple(
        item
        for item in manifest.snapshots
        if item.artifact_id.startswith("source:")
        and _path_matches_input_scope(item.artifact_id.removeprefix("source:"), patterns)
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
    return _evidence_token(root, path)


def _load_manifest(root: Path, path_token: str) -> SpecInputManifest:
    path = _resolve_evidence_token(root, path_token)
    return SpecInputManifest.from_dict(_read_json(path))


def _session_pointer_path(root: Path, provider_id: str, work_package_id: str) -> Path:
    identity = f"{provider_id}:{work_package_id}"
    return _evidence_root(root) / "sessions" / f"{_safe_component(identity)}.json"


def _session_record_path(root: Path, session_id: str, stage: str) -> Path:
    # Session ids already live inside the immutable record.  A bounded
    # content-addressed directory keeps persistent evidence usable below long
    # Windows project roots without creating a second lookup authority.
    session_component = f"session-{hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:24]}"
    return _evidence_root(root) / "sessions" / "history" / session_component / f"{stage}.json"


def _save_immutable_session_record(root: Path, session_id: str, stage: str, value: Mapping[str, Any]) -> str:
    path = _session_record_path(root, session_id, stage)
    if path.exists():
        if _read_json(path) != dict(value):
            raise ValueError(f"immutable spec session {stage} record already exists with different content")
    else:
        _atomic_json(path, value)
    return _evidence_token(root, path)


def _load_package(root: Path, provider_id: str, work_package_id: str) -> SpecWorkPackage:
    if provider_id == "openspec":
        return load_openspec_work_package(root, work_package_id)
    if provider_id == "speckit":
        return load_speckit_work_package(root, work_package_id)
    raise ValueError(f"unsupported spec provider: {provider_id}")


def _load_owner_checks(root: Path, provider_id: str, work_package_id: str) -> tuple[Any, ...]:
    package = _load_package(root, provider_id, work_package_id)
    if provider_id == "openspec":
        canonical = load_openspec_canonical_checks(root, work_package_id)
        if canonical:
            external_ids = {
                check.check_id for check in package.checks if check.kind == "receipt" and check.external_receipt_ref
            }
            canonical_ids = {check.check_id for check in canonical}
            if external_ids != canonical_ids:
                missing = sorted(external_ids - canonical_ids)
                extra = sorted(canonical_ids - external_ids)
                raise ValueError(
                    f"canonical FlowGuard owner/external receipt mismatch: missing={missing},extra={extra}"
                )
            return canonical
    return tuple(
        check
        for check in package.checks
        if check.kind != "receipt" and check.execution_owner_id == "flowguard.spec_check_cache"
    )


def _dependent_check_closure(checks: Sequence[Any], seed_ids: Sequence[str]) -> tuple[str, ...]:
    """Return the deterministic reverse dependency closure for minimum revalidation."""

    reverse: dict[str, set[str]] = {check.check_id: set() for check in checks}
    for check in checks:
        for upstream in (*check.depends_on, *check.dependency_input_ids, *check.child_check_ids):
            reverse.setdefault(str(upstream), set()).add(check.check_id)
    closure = set(str(value) for value in seed_ids if str(value))
    pending = list(sorted(closure))
    while pending:
        upstream = pending.pop(0)
        for downstream in sorted(reverse.get(upstream, ())):
            if downstream in closure:
                continue
            closure.add(downstream)
            pending.append(downstream)
    return tuple(sorted(closure))


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
    snapshot_policy: str = SPEC_SNAPSHOT_LIVE_SCOPED
    toolchain_fingerprint: str = ""
    toolchain_snapshot: Mapping[str, Any] = field(default_factory=dict)
    minimum_revalidation: tuple[str, ...] = ()
    archive_ready: bool = False

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
            "snapshot_policy": self.snapshot_policy,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "toolchain_snapshot": dict(self.toolchain_snapshot),
            "minimum_revalidation": list(self.minimum_revalidation),
            "archive_ready": self.archive_ready,
        }


def begin_spec_session(
    root: str | Path,
    provider_id: str,
    work_package_id: str,
    *,
    snapshot_policy: str = SPEC_SNAPSHOT_LIVE_SCOPED,
) -> SpecSessionResult:
    project_root = _project_root(root)
    if snapshot_policy not in SPEC_SNAPSHOT_POLICIES:
        raise ValueError(f"unsupported spec snapshot policy: {snapshot_policy}")
    if snapshot_policy == SPEC_SNAPSHOT_FROZEN_REQUIRED and not os.environ.get(
        "FLOWGUARD_SPEC_EVIDENCE_ROOT", ""
    ).strip():
        raise ValueError(
            "frozen-required sessions need FLOWGUARD_SPEC_EVIDENCE_ROOT so receipts survive disposable snapshots"
        )
    package = _load_package(project_root, provider_id, work_package_id)
    _load_owner_checks(project_root, provider_id, work_package_id)
    review = review_spec_work_package(package)
    raw_manifest = capture_spec_input_manifest(project_root)
    raw_manifest_path = _save_manifest(project_root, raw_manifest)
    manifest = capture_spec_input_manifest(project_root, normalize_provider_tasks=True)
    manifest_path = _save_manifest(project_root, manifest)
    toolchain = capture_spec_toolchain_snapshot(package)
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
        "begin_raw_manifest_path": raw_manifest_path,
        "begin_raw_fingerprint": raw_manifest.fingerprint,
        "snapshot_policy": snapshot_policy,
        "toolchain_snapshot": toolchain.to_dict(),
        "toolchain_fingerprint": toolchain.fingerprint,
        "post_manifest_path": "",
        "post_fingerprint": "",
        "changed_inputs": {"added": [], "removed": [], "changed": []},
        "check_results": {},
        "blockers": list(blockers),
        "minimum_revalidation": [],
        "archive_ready": False,
        "snapshot_manifest_id": manifest.fingerprint,
        "persistent_evidence_store": bool(os.environ.get("FLOWGUARD_SPEC_EVIDENCE_ROOT", "").strip()),
    }
    begin_record_path = _evidence_token(
        project_root, _session_record_path(project_root, session_id, "begin")
    )
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
        snapshot_policy=snapshot_policy,
        toolchain_fingerprint=toolchain.fingerprint,
        toolchain_snapshot=toolchain.to_dict(),
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
    execution_id: str = ""
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
    input_paths: tuple[str, ...] = ()
    input_fingerprint: str = ""
    snapshot_policy: str = SPEC_SNAPSHOT_LIVE_SCOPED
    toolchain_fingerprint: str = ""
    dependency_receipt_fingerprints: Mapping[str, str] = field(default_factory=dict)
    minimum_revalidation: tuple[str, ...] = ()
    parent_check_id: str = ""
    child_receipt_ids: tuple[str, ...] = ()
    uncovered_coverage_ids: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.state in {SPEC_CHECK_STATE_EXECUTED, SPEC_CHECK_STATE_REUSED_CURRENT} and self.terminal_status == SPEC_TERMINAL_PASS

    @property
    def semantic_check_id(self) -> str:
        return self.semantic_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SPEC_RECEIPT_SCHEMA,
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "check_id": self.check_id,
            "semantic_id": self.semantic_id,
            "semantic_check_id": self.semantic_check_id,
            "state": self.state,
            "terminal_status": self.terminal_status,
            "ok": self.ok,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "execution_key": self.execution_key,
            "execution_id": self.execution_id,
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
            "input_paths": list(self.input_paths),
            "input_fingerprint": self.input_fingerprint,
            "snapshot_policy": self.snapshot_policy,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "dependency_receipt_fingerprints": dict(self.dependency_receipt_fingerprints),
            "minimum_revalidation": list(self.minimum_revalidation),
            "parent_check_id": self.parent_check_id,
            "child_receipt_ids": list(self.child_receipt_ids),
            "uncovered_coverage_ids": list(self.uncovered_coverage_ids),
        }


@dataclass(frozen=True)
class PortableSpecReceiptEnvelope:
    """Portable, path-tokenized reference to one immutable canonical receipt."""

    receipt_id: str
    receipt_fingerprint: str
    provider_id: str
    work_package_id: str
    check_id: str
    semantic_check_id: str
    execution_id: str
    execution_key: str
    source_manifest_id: str
    source_manifest_ref: str
    source_manifest_hash: str
    source_hash_policy: Mapping[str, Any]
    source_fingerprint: str
    toolchain_fingerprint: str
    result_fingerprint: str
    termination_fingerprint: str
    snapshot_policy: str
    coverage_ids: tuple[str, ...] = ()
    validation_obligation_ids: tuple[str, ...] = ()
    sidecar_refs: Mapping[str, str] = field(default_factory=dict)
    sidecar_hashes: Mapping[str, str] = field(default_factory=dict)
    child_receipt_refs: tuple[str, ...] = ()
    child_receipt_hashes: Mapping[str, str] = field(default_factory=dict)
    root_token: str = SPEC_EVIDENCE_ROOT_TOKEN
    protocol_version: int = SPEC_PORTABLE_RECEIPT_PROTOCOL
    schema_version: str = SPEC_PORTABLE_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != SPEC_PORTABLE_RECEIPT_SCHEMA:
            raise ValueError(f"unsupported portable receipt envelope schema: {self.schema_version}")
        if self.protocol_version != SPEC_PORTABLE_RECEIPT_PROTOCOL:
            raise ValueError(f"unsupported portable receipt envelope protocol: {self.protocol_version}")
        if self.root_token != SPEC_EVIDENCE_ROOT_TOKEN:
            raise ValueError("portable receipt envelope must use the canonical evidence root token")
        if not isinstance(self.source_hash_policy, Mapping) or not self.source_hash_policy:
            raise ValueError("portable receipt envelope needs an explicit source hash policy")
        required = (
            self.receipt_id,
            self.receipt_fingerprint,
            self.provider_id,
            self.work_package_id,
            self.check_id,
            self.semantic_check_id,
            self.execution_id,
            self.execution_key,
            self.source_manifest_id,
            self.source_manifest_ref,
            self.source_manifest_hash,
            self.source_hash_policy,
            self.source_fingerprint,
            self.toolchain_fingerprint,
            self.result_fingerprint,
            self.termination_fingerprint,
            self.snapshot_policy,
        )
        if any(not str(value) for value in required):
            raise ValueError("portable receipt envelope identity is incomplete")
        digest_values = (
            self.receipt_id,
            self.receipt_fingerprint,
            self.execution_key,
            self.source_manifest_id,
            self.source_manifest_hash,
            self.source_fingerprint,
            self.toolchain_fingerprint,
            self.result_fingerprint,
            self.termination_fingerprint,
            *self.sidecar_hashes.values(),
        )
        if any(re.fullmatch(r"sha256:[0-9a-f]{64}", str(value)) is None for value in digest_values):
            raise ValueError("portable receipt envelope contains a non-canonical sha256 digest")
        if not _is_evidence_ref(self.source_manifest_ref):
            raise ValueError("portable source manifest must use the evidence-root token")
        object.__setattr__(self, "source_hash_policy", dict(self.source_hash_policy))
        object.__setattr__(self, "coverage_ids", tuple(sorted(set(str(value) for value in self.coverage_ids))))
        object.__setattr__(
            self,
            "validation_obligation_ids",
            tuple(sorted(set(str(value) for value in self.validation_obligation_ids))),
        )
        if not self.validation_obligation_ids:
            raise ValueError("portable receipt envelope needs validation obligation coverage")
        object.__setattr__(self, "sidecar_refs", dict(sorted((str(k), str(v)) for k, v in self.sidecar_refs.items())))
        object.__setattr__(self, "sidecar_hashes", dict(sorted((str(k), str(v)) for k, v in self.sidecar_hashes.items())))
        object.__setattr__(
            self,
            "child_receipt_refs",
            tuple(sorted(set(str(value) for value in self.child_receipt_refs))),
        )
        object.__setattr__(
            self,
            "child_receipt_hashes",
            dict(sorted((str(ref), str(digest)) for ref, digest in self.child_receipt_hashes.items())),
        )
        if any(not _is_evidence_ref(value) for value in self.sidecar_refs.values()):
            raise ValueError("portable receipt envelope sidecars must use evidence-root tokens")
        if set(self.sidecar_refs) != {"stdout", "stderr", "result", "termination"}:
            raise ValueError("portable receipt envelope must contain exactly four canonical sidecars")
        if set(self.sidecar_hashes) != set(self.sidecar_refs):
            raise ValueError("portable receipt sidecar refs and hashes must have identical roles")
        if any(not _is_evidence_ref(value) for value in self.child_receipt_refs):
            raise ValueError("portable child receipt references must use evidence-root tokens")
        if set(self.child_receipt_refs) != set(self.child_receipt_hashes):
            raise ValueError("portable child receipt refs and hashes must have identical identities")
        if any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
            for digest in self.child_receipt_hashes.values()
        ):
            raise ValueError("portable child receipt hash is non-canonical")
        if self.snapshot_policy not in {"live", "frozen"}:
            raise ValueError("portable receipt envelope snapshot_policy must be live or frozen")

    def identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "protocol_version": self.protocol_version,
            "root_token": self.root_token,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "check_id": self.check_id,
            "semantic_check_id": self.semantic_check_id,
            "execution_id": self.execution_id,
            "execution_key": self.execution_key,
            "source_manifest_id": self.source_manifest_id,
            "source_manifest_ref": self.source_manifest_ref,
            "source_manifest_hash": self.source_manifest_hash,
            "source_hash_policy": self.source_hash_policy,
            "source_fingerprint": self.source_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "termination_fingerprint": self.termination_fingerprint,
            "snapshot_policy": self.snapshot_policy,
            "coverage_ids": list(self.coverage_ids),
            "validation_obligation_ids": list(self.validation_obligation_ids),
            "sidecar_refs": dict(self.sidecar_refs),
            "sidecar_hashes": dict(self.sidecar_hashes),
            "child_receipt_refs": list(self.child_receipt_refs),
            "child_receipt_hashes": dict(self.child_receipt_hashes),
        }

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.identity_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_dict(), "envelope_fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PortableSpecReceiptEnvelope":
        allowed = {
            "schema_version", "protocol_version", "root_token", "receipt_id",
            "receipt_fingerprint", "provider_id", "work_package_id", "check_id",
            "semantic_check_id", "execution_id", "execution_key", "source_manifest_id",
            "source_manifest_ref", "source_manifest_hash", "source_hash_policy",
            "source_fingerprint", "toolchain_fingerprint", "result_fingerprint",
            "termination_fingerprint", "snapshot_policy", "sidecar_refs", "sidecar_hashes",
            "child_receipt_refs", "child_receipt_hashes", "coverage_ids", "validation_obligation_ids", "envelope_fingerprint",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown portable receipt envelope fields: {sorted(unknown)}")
        envelope = cls(
            schema_version=str(value.get("schema_version", "")),
            protocol_version=int(value.get("protocol_version", 0)),
            root_token=str(value.get("root_token", "")),
            receipt_id=str(value.get("receipt_id", "")),
            receipt_fingerprint=str(value.get("receipt_fingerprint", "")),
            provider_id=str(value.get("provider_id", "")),
            work_package_id=str(value.get("work_package_id", "")),
            check_id=str(value.get("check_id", "")),
            semantic_check_id=str(value.get("semantic_check_id", "")),
            execution_id=str(value.get("execution_id", "")),
            execution_key=str(value.get("execution_key", "")),
            source_manifest_id=str(value.get("source_manifest_id", "")),
            source_manifest_ref=str(value.get("source_manifest_ref", "")),
            source_manifest_hash=str(value.get("source_manifest_hash", "")),
            source_hash_policy=value.get("source_hash_policy", {}),
            source_fingerprint=str(value.get("source_fingerprint", "")),
            toolchain_fingerprint=str(value.get("toolchain_fingerprint", "")),
            result_fingerprint=str(value.get("result_fingerprint", "")),
            termination_fingerprint=str(value.get("termination_fingerprint", "")),
            snapshot_policy=str(value.get("snapshot_policy", "")),
            coverage_ids=tuple(str(item) for item in value.get("coverage_ids", ())),
            validation_obligation_ids=tuple(
                str(item) for item in value.get("validation_obligation_ids", ())
            ),
            sidecar_refs=value.get("sidecar_refs", {}),
            sidecar_hashes=value.get("sidecar_hashes", {}),
            child_receipt_refs=tuple(str(item) for item in value.get("child_receipt_refs", ())),
            child_receipt_hashes=value.get("child_receipt_hashes", {}),
        )
        if str(value.get("envelope_fingerprint", "")) != envelope.fingerprint:
            raise ValueError("portable receipt envelope fingerprint mismatch")
        return envelope


@dataclass(frozen=True)
class SpecReceiptConsumptionResult:
    receipt_id: str
    envelope_fingerprint: str
    current: bool
    eligible: bool
    findings: tuple[str, ...] = ()
    minimum_revalidation: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.current and self.eligible and not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "spec-receipt-consumption.v1",
            "receipt_id": self.receipt_id,
            "envelope_fingerprint": self.envelope_fingerprint,
            "current": self.current,
            "eligible": self.eligible,
            "ok": self.ok,
            "findings": list(self.findings),
            "minimum_revalidation": list(self.minimum_revalidation),
        }


@dataclass(frozen=True)
class SpecProviderCloseReview:
    provider_id: str
    work_package_id: str
    session_id: str
    archive_ready: bool
    findings: tuple[str, ...] = ()
    minimum_revalidation: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.archive_ready and not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "spec-provider-close-review.v1",
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "session_id": self.session_id,
            "archive_ready": self.archive_ready,
            "ok": self.ok,
            "findings": list(self.findings),
            "minimum_revalidation": list(self.minimum_revalidation),
            "claim_boundary": "Read-only post-report reconciliation; this does not execute checks or mutate provider state.",
        }


def _record_check_result(root: Path, result: SpecCheckExecutionResult) -> None:
    session = _load_session(root, result.provider_id, result.work_package_id)
    rows = dict(session.get("check_results", {}))
    previous = rows.get(result.check_id, {})
    rows[result.check_id] = result.to_dict()
    minimum_revalidation = list(session.get("minimum_revalidation", ()))
    minimum_revalidation.extend(result.minimum_revalidation)
    previous_fingerprint = str(previous.get("receipt_fingerprint", "")) if isinstance(previous, Mapping) else ""
    receipt_changed = bool(previous_fingerprint) and previous_fingerprint != result.receipt_fingerprint
    if receipt_changed or (isinstance(previous, Mapping) and bool(previous.get("ok", False)) and not result.ok):
        owner_checks = _load_owner_checks(root, result.provider_id, result.work_package_id)
        downstream = _dependent_check_closure(owner_checks, (result.check_id,))
        minimum_revalidation.extend(downstream)
        for check_id in downstream:
            if check_id == result.check_id or not isinstance(rows.get(check_id), Mapping):
                continue
            stale_row = dict(rows[check_id])
            stale_row.update(
                {
                    "state": SPEC_CHECK_STATE_STALE,
                    "terminal_status": SPEC_TERMINAL_BLOCKED,
                    "ok": False,
                    "blockers": list(
                        dict.fromkeys(
                            (*stale_row.get("blockers", ()), f"upstream_receipt_changed:{result.check_id}")
                        )
                    ),
                    "minimum_revalidation": list(
                        dict.fromkeys((*stale_row.get("minimum_revalidation", ()), check_id))
                    ),
                }
            )
            rows[check_id] = stale_row
    session["check_results"] = rows
    session["minimum_revalidation"] = list(dict.fromkeys(minimum_revalidation))
    _save_session(root, result.provider_id, result.work_package_id, session)


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _tool_fingerprint(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    declared_toolchain_identity: str = "",
) -> tuple[dict[str, str], str]:
    tokens = tuple(str(value) for value in command)
    metadata = {
        "python": platform.python_version(),
        "flowguard": _version("flowguard"),
    }
    if declared_toolchain_identity:
        metadata["declared_toolchain_identity"] = declared_toolchain_identity
    executable = shutil.which(tokens[0]) if tokens else None
    if executable:
        try:
            metadata["command_entry_sha256"] = _sha256_bytes(Path(executable).read_bytes())
        except OSError:
            metadata["command_entry_sha256"] = "unreadable"
        metadata["command_entry_name"] = Path(executable).name
    script_index = 0
    for token in tokens[1:]:
        if not token.casefold().endswith(".py"):
            continue
        candidate = Path(token)
        if not candidate.is_absolute() and cwd is not None:
            candidate = cwd / candidate
        if candidate.is_file():
            metadata[f"script_{script_index}_sha256"] = _sha256_bytes(candidate.read_bytes())
            script_index += 1
    if "-m" in tokens:
        try:
            module_name = tokens[tokens.index("-m") + 1]
            spec = importlib.util.find_spec(module_name)
            if spec is not None and spec.origin and Path(spec.origin).is_file():
                metadata["module_entry_sha256"] = _sha256_bytes(Path(spec.origin).read_bytes())
        except (IndexError, ImportError, OSError, ValueError):
            metadata["module_entry_sha256"] = "unavailable"
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
    toolchain_fingerprint: str,
    snapshot_policy: str,
    input_paths: Sequence[str],
    dependency_receipt_fingerprints: Mapping[str, str],
    execution_owner_id: str,
    declared_toolchain_identity: str,
) -> dict[str, Any]:
    scope = {"cross_change_safe": bool(cross_change_safe)}
    if not cross_change_safe:
        scope.update({"provider_id": provider_id, "work_package_id": work_package_id})
    return {
        "semantic_id": semantic_id,
        "semantic_check_id": semantic_id,
        "execution_owner_id": execution_owner_id,
        "check_id_role": check_id if not cross_change_safe else "consumer-local",
        "command": list(command),
        "working_directory_token": working_directory_token,
        "expected_exit_code": expected_exit_code,
        "timeout_seconds": timeout_seconds,
        "validation_obligation_ids": sorted(set(validation_obligation_ids)),
        "coverage": (
            ["consumer-local"]
            if cross_change_safe
            else sorted(set(coverage))
        ),
        "input_fingerprint": input_fingerprint,
        "environment_fingerprint": environment_fingerprint,
        "tool_fingerprint": tool_fingerprint,
        "declared_toolchain_identity": declared_toolchain_identity,
        "toolchain_fingerprint": toolchain_fingerprint,
        "snapshot_policy": snapshot_policy,
        "input_paths": sorted(set(input_paths)),
        "dependency_receipt_fingerprints": dict(sorted(dependency_receipt_fingerprints.items())),
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
    metadata = receipt.to_dict()["metadata"]
    result_files = metadata.get("result_files", {})
    if not isinstance(result_files, Mapping):
        return ""
    try:
        stdout_path = _resolve_evidence_token(root, str(result_files.get("stdout", "")))
        stderr_path = _resolve_evidence_token(root, str(result_files.get("stderr", "")))
        stdout = stdout_path.read_bytes()
        stderr = stderr_path.read_bytes()
    except (OSError, ValueError):
        return ""
    terminal_status = str(metadata.get("terminal_status", ""))
    return _result_fingerprint(receipt.exit_code, terminal_status, stdout, stderr)


def _portable_envelope_path(root: Path, receipt_id: str) -> Path:
    return _evidence_root(root) / "envelopes" / f"{_safe_component(receipt_id)}.json"


def _portable_receipt_ref_path(root: Path, provider_id: str, work_package_id: str, check_id: str) -> Path:
    components = (provider_id, work_package_id, check_id)
    if any(re.fullmatch(r"[A-Za-z0-9._-]+", value) is None for value in components):
        raise ValueError("portable receipt ref identity contains an unsafe path component")
    return (
        _evidence_root(root)
        / "portable-refs"
        / provider_id
        / work_package_id
        / f"{check_id}.json"
    )


def _portable_source_hash_policy() -> dict[str, Any]:
    return {
        "version": 2,
        "algorithm": "sha256",
        "task_checkbox_normalization": "markdown-checkbox-state-v1",
        "output_classifier_version": "verification-generated-output-v2",
    }


def _portable_source_files(manifest: SpecInputManifest) -> dict[str, str]:
    return {
        snapshot.artifact_id.removeprefix("source:"): (
            snapshot.semantic_sha256
            if snapshot.artifact_id.endswith("/tasks.md")
            and (
                snapshot.artifact_id.startswith("source:openspec/changes/")
                or snapshot.artifact_id.startswith("source:specs/")
            )
            else snapshot.raw_sha256
        )
        for snapshot in manifest.snapshots
    }


def _portable_receipt_semantic_identity(
    *,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    semantic_check_id: str,
    execution_id: str,
    execution_key: str,
    source_manifest_id: str,
    source_manifest_hash: str,
    source_hash_policy: Mapping[str, Any],
    source_fingerprint: str,
    toolchain_fingerprint: str,
    result_fingerprint: str,
    termination_fingerprint: str,
    snapshot_policy: str,
    coverage_ids: Sequence[str],
    validation_obligation_ids: Sequence[str],
    sidecar_hashes: Mapping[str, str],
    child_receipts: Sequence[tuple[str, str]],
) -> tuple[str, str]:
    """Derive time/path/run-independent portable receipt identity."""

    payload = {
        "provider_id": provider_id,
        "work_package_id": work_package_id,
        "check_id": check_id,
        "semantic_check_id": semantic_check_id,
        "execution_id": execution_id,
        "execution_key": execution_key,
        "source_manifest_id": source_manifest_id,
        "source_manifest_hash": source_manifest_hash,
        "source_hash_policy": dict(source_hash_policy),
        "source_fingerprint": source_fingerprint,
        "toolchain_fingerprint": toolchain_fingerprint,
        "result_fingerprint": result_fingerprint,
        "termination_fingerprint": termination_fingerprint,
        "snapshot_policy": snapshot_policy,
        "coverage_ids": sorted(set(str(value) for value in coverage_ids)),
        "validation_obligation_ids": sorted(
            set(str(value) for value in validation_obligation_ids)
        ),
        "result_sidecar_hashes": {
            name: str(sidecar_hashes[name])
            for name in ("stdout", "stderr", "result", "termination")
            if name in sidecar_hashes
        },
        "child_receipts": [
            {"receipt_id": receipt_id, "receipt_fingerprint": receipt_fingerprint}
            for receipt_id, receipt_fingerprint in sorted(child_receipts)
        ],
    }
    receipt_id = fingerprint_value(
        {"schema_version": SPEC_PORTABLE_RECEIPT_SCHEMA, "semantic_identity": payload}
    )
    receipt_fingerprint = fingerprint_value({"receipt_id": receipt_id, **payload})
    return receipt_id, receipt_fingerprint


def _save_portable_source_manifest(root: Path, manifest: SpecInputManifest) -> tuple[str, str, str]:
    files = _portable_source_files(manifest)
    manifest_id = fingerprint_value(
        {"source_hash_policy": _portable_source_hash_policy(), "files": dict(sorted(files.items()))}
    )
    value: dict[str, Any] = {
        "schema_version": SPEC_PORTABLE_SOURCE_MANIFEST_SCHEMA,
        "source_hash_policy": _portable_source_hash_policy(),
        "manifest_id": manifest_id,
        "files": dict(sorted(files.items())),
    }
    manifest_hash = _sha256_bytes(_canonical_json(value).encode("utf-8"))
    path = (
        _evidence_root(root)
        / "portable-source-manifests"
        / f"{manifest_id.removeprefix('sha256:')}.json"
    )
    if path.exists():
        if _read_json(path) != value:
            raise ValueError("immutable portable source manifest already contains different content")
    else:
        _atomic_json(path, value)
    return _portable_evidence_token(root, path), manifest_hash, manifest_id


def _portable_envelope_for_receipt(root: Path, receipt: EvidenceReceipt) -> PortableSpecReceiptEnvelope:
    metadata = receipt.to_dict()["metadata"]
    result_files = metadata.get("result_files", {})
    if not isinstance(result_files, Mapping):
        result_files = {}
    sidecar_refs = dict(
        (str(name), _portable_evidence_token(root, _resolve_evidence_token(root, str(path_token))))
        for name, path_token in result_files.items()
        if str(path_token) and str(name) in {"stdout", "stderr", "result", "termination"}
    )
    sidecar_hashes: dict[str, str] = {}
    for name, path_token in sidecar_refs.items():
        sidecar_hashes[name] = _sha256_bytes(_resolve_evidence_token(root, path_token).read_bytes())
    child_refs: list[str] = []
    child_hashes: dict[str, str] = {}
    child_semantic_receipts: list[tuple[str, str]] = []
    for child in receipt.consumed_child_receipts:
        child_envelope_path = _portable_envelope_path(root, child.receipt_id)
        child_ref = _portable_evidence_token(root, child_envelope_path)
        child_refs.append(child_ref)
        child_hashes[child_ref] = _sha256_bytes(child_envelope_path.read_bytes())
        child_envelope = PortableSpecReceiptEnvelope.from_dict(_read_json(child_envelope_path))
        child_semantic_receipts.append(
            (child_envelope.receipt_id, child_envelope.receipt_fingerprint)
        )
    internal_source_manifest_ref = str(
        metadata.get("check_post_manifest_path", metadata.get("begin_manifest_path", ""))
    )
    if not internal_source_manifest_ref:
        raise ValueError("portable receipt needs an immutable source manifest reference")
    source_manifest = _load_manifest(root, internal_source_manifest_ref)
    source_manifest_ref, source_manifest_hash, source_manifest_id = _save_portable_source_manifest(
        root, source_manifest
    )
    source_fingerprint = fingerprint_value(
        dict(sorted(_portable_source_files(source_manifest).items()))
    )
    wire_snapshot_policy = (
        "frozen"
        if metadata.get("snapshot_policy") == SPEC_SNAPSHOT_FROZEN_REQUIRED
        else "live"
    )
    portable_receipt_id, portable_receipt_fingerprint = _portable_receipt_semantic_identity(
        provider_id=str(metadata.get("provider_id", "")),
        work_package_id=str(metadata.get("work_package_id", "")),
        check_id=str(metadata.get("check_id", "")),
        semantic_check_id=str(metadata.get("semantic_check_id", receipt.subject_id)),
        execution_id=str(metadata.get("execution_id", "")),
        execution_key=str(metadata.get("execution_key", "")),
        source_manifest_id=source_manifest_id,
        source_manifest_hash=source_manifest_hash,
        source_hash_policy=_portable_source_hash_policy(),
        source_fingerprint=source_fingerprint,
        toolchain_fingerprint=str(metadata.get("toolchain_fingerprint", "")),
        result_fingerprint=receipt.result_fingerprint,
        termination_fingerprint=str(metadata.get("termination_fingerprint", "")),
        snapshot_policy=wire_snapshot_policy,
        coverage_ids=tuple(str(value) for value in metadata.get("coverage", ())),
        validation_obligation_ids=receipt.covered_obligations,
        sidecar_hashes=sidecar_hashes,
        child_receipts=child_semantic_receipts,
    )
    return PortableSpecReceiptEnvelope(
        receipt_id=portable_receipt_id,
        receipt_fingerprint=portable_receipt_fingerprint,
        provider_id=str(metadata.get("provider_id", "")),
        work_package_id=str(metadata.get("work_package_id", "")),
        check_id=str(metadata.get("check_id", "")),
        semantic_check_id=str(metadata.get("semantic_check_id", receipt.subject_id)),
        execution_id=str(metadata.get("execution_id", "")),
        execution_key=str(metadata.get("execution_key", "")),
        source_manifest_id=source_manifest_id,
        source_manifest_ref=source_manifest_ref,
        source_manifest_hash=source_manifest_hash,
        source_hash_policy=_portable_source_hash_policy(),
        source_fingerprint=source_fingerprint,
        toolchain_fingerprint=str(metadata.get("toolchain_fingerprint", "")),
        result_fingerprint=receipt.result_fingerprint,
        termination_fingerprint=str(metadata.get("termination_fingerprint", "")),
        snapshot_policy=wire_snapshot_policy,
        coverage_ids=tuple(str(value) for value in metadata.get("coverage", ())),
        validation_obligation_ids=receipt.covered_obligations,
        sidecar_refs=sidecar_refs,
        sidecar_hashes=sidecar_hashes,
        child_receipt_refs=tuple(child_refs),
        child_receipt_hashes=child_hashes,
    )


def _save_portable_receipt_ref(
    root: Path,
    *,
    envelope: PortableSpecReceiptEnvelope,
    envelope_path: Path,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    coverage_ids: Sequence[str] | None = None,
) -> None:
    """Publish one consumer-local pointer without copying the owner receipt."""

    envelope_token = _portable_evidence_token(root, envelope_path)
    pointer = {
        "schema_version": "portable-receipt-ref.v1",
        "protocol_version": SPEC_PORTABLE_RECEIPT_PROTOCOL,
        "root_token": SPEC_EVIDENCE_ROOT_TOKEN,
        "provider_id": provider_id,
        "work_package_id": work_package_id,
        "check_id": check_id,
        "semantic_check_id": envelope.semantic_check_id,
        "execution_id": envelope.execution_id,
        "envelope_ref": envelope_token,
        "envelope_fingerprint": envelope.fingerprint,
        "receipt_id": envelope.receipt_id,
        "receipt_fingerprint": envelope.receipt_fingerprint,
        "coverage_ids": sorted(
            set(
                envelope.coverage_ids
                if coverage_ids is None
                else (str(value) for value in coverage_ids)
            )
        ),
    }
    _atomic_json(
        _portable_receipt_ref_path(root, provider_id, work_package_id, check_id),
        pointer,
    )


def _save_portable_envelope(root: Path, receipt: EvidenceReceipt) -> PortableSpecReceiptEnvelope:
    envelope = _portable_envelope_for_receipt(root, receipt)
    path = _portable_envelope_path(root, receipt.receipt_id)
    if path.exists():
        existing = PortableSpecReceiptEnvelope.from_dict(_read_json(path))
        if existing.to_dict() != envelope.to_dict():
            raise ValueError("immutable portable receipt envelope already contains different content")
    else:
        _atomic_json(path, envelope.to_dict())
    _save_portable_receipt_ref(
        root,
        envelope=envelope,
        envelope_path=path,
        provider_id=envelope.provider_id,
        work_package_id=envelope.work_package_id,
        check_id=envelope.check_id,
    )
    return envelope


def _load_portable_envelope(root: Path, receipt_id: str) -> PortableSpecReceiptEnvelope:
    path = _portable_envelope_path(root, receipt_id)
    if not path.is_file():
        raise ValueError(f"portable receipt envelope is unavailable: {receipt_id}")
    return PortableSpecReceiptEnvelope.from_dict(_read_json(path))


def _load_portable_receipt_ref(
    root: Path,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    *,
    ref_path: str = "",
) -> tuple[str, PortableSpecReceiptEnvelope]:
    pointer_path = (
        _resolve_evidence_token(root, ref_path)
        if ref_path
        else _portable_receipt_ref_path(root, provider_id, work_package_id, check_id)
    )
    if not pointer_path.is_file():
        raise ValueError(f"portable receipt ref is unavailable: {check_id}")
    pointer = _read_json(pointer_path)
    allowed = {
        "schema_version", "protocol_version", "root_token", "provider_id",
        "work_package_id", "check_id", "semantic_check_id", "execution_id",
        "envelope_ref", "envelope_fingerprint", "receipt_id", "receipt_fingerprint",
        "coverage_ids",
    }
    if set(pointer) != allowed:
        raise ValueError("portable receipt ref contains unknown or missing fields")
    if pointer.get("schema_version") != "portable-receipt-ref.v1":
        raise ValueError("unsupported portable receipt ref schema")
    if pointer.get("protocol_version") != SPEC_PORTABLE_RECEIPT_PROTOCOL:
        raise ValueError("unsupported portable receipt ref protocol")
    if pointer.get("root_token") != SPEC_EVIDENCE_ROOT_TOKEN:
        raise ValueError("portable receipt ref root token mismatch")
    pointer_coverage = pointer.get("coverage_ids")
    if (
        not isinstance(pointer_coverage, list)
        or len(pointer_coverage) != len(set(pointer_coverage))
        or any(not isinstance(value, str) or not value for value in pointer_coverage)
    ):
        raise ValueError("portable receipt ref coverage_ids are not canonical")
    for field_name in ("envelope_fingerprint", "receipt_id", "receipt_fingerprint"):
        if re.fullmatch(r"sha256:[0-9a-f]{64}", str(pointer.get(field_name, ""))) is None:
            raise ValueError(f"portable receipt ref {field_name} is not canonical")
    envelope_path = _resolve_evidence_token(root, str(pointer.get("envelope_ref", "")))
    envelope = PortableSpecReceiptEnvelope.from_dict(_read_json(envelope_path))
    if pointer.get("envelope_fingerprint") != envelope.fingerprint:
        raise ValueError("portable receipt ref envelope fingerprint mismatch")
    if pointer.get("receipt_id") != envelope.receipt_id:
        raise ValueError("portable receipt ref receipt identity mismatch")
    if pointer.get("receipt_fingerprint") != envelope.receipt_fingerprint:
        raise ValueError("portable receipt ref receipt fingerprint mismatch")
    if (
        pointer.get("provider_id"),
        pointer.get("work_package_id"),
        pointer.get("check_id"),
    ) != (provider_id, work_package_id, check_id):
        raise ValueError("portable receipt ref stable identity mismatch")
    if pointer.get("semantic_check_id") != envelope.semantic_check_id:
        raise ValueError("portable receipt ref semantic identity mismatch")
    if pointer.get("execution_id") != envelope.execution_id:
        raise ValueError("portable receipt ref execution identity mismatch")
    if provider_id in {"openspec", "speckit"}:
        declared_consumer = next(
            (
                item
                for item in _load_package(root, provider_id, work_package_id).checks
                if item.check_id == check_id
            ),
            None,
        )
        consumer_coverage = (
            set((*declared_consumer.obligation_ids, *declared_consumer.coverage_ids))
            if declared_consumer is not None
            else set()
        )
    else:
        # A foreign provider's portable ref is its physical owner ref rather
        # than a local spec-consumer projection, so its exact coverage remains
        # bound to the immutable owner envelope.
        consumer_coverage = set(envelope.coverage_ids)
    if set(pointer_coverage) != consumer_coverage:
        raise ValueError("portable receipt ref consumer coverage identity mismatch")

    source_manifest_value = _read_json(
        _resolve_evidence_token(root, envelope.source_manifest_ref)
    )
    unknown_manifest_fields = set(source_manifest_value) - {
        "schema_version", "source_hash_policy", "manifest_id", "files"
    }
    if unknown_manifest_fields:
        raise ValueError(
            f"unknown portable source manifest fields: {sorted(unknown_manifest_fields)}"
        )
    if source_manifest_value.get("schema_version") != SPEC_PORTABLE_SOURCE_MANIFEST_SCHEMA:
        raise ValueError("unsupported portable source manifest schema")
    if source_manifest_value.get("source_hash_policy") != _portable_source_hash_policy():
        raise ValueError("unsupported portable source hash policy")
    files = source_manifest_value.get("files", {})
    if not isinstance(files, Mapping):
        raise ValueError("portable source manifest files must be a path/hash map")
    portable_files = dict(sorted((str(path), str(digest)) for path, digest in files.items()))
    if any(
        re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        for digest in portable_files.values()
    ):
        raise ValueError("portable source manifest contains a non-canonical digest")
    expected_manifest_id = fingerprint_value(
        {"source_hash_policy": _portable_source_hash_policy(), "files": portable_files}
    )
    if source_manifest_value.get("manifest_id") != expected_manifest_id:
        raise ValueError("portable source manifest self identity mismatch")
    if envelope.source_manifest_id != expected_manifest_id:
        raise ValueError("portable source manifest identity mismatch")
    if envelope.source_manifest_hash != _sha256_bytes(
        _canonical_json(source_manifest_value).encode("utf-8")
    ):
        raise ValueError("portable source manifest content hash mismatch")
    if envelope.source_fingerprint != fingerprint_value(portable_files):
        raise ValueError("portable source fingerprint mismatch")
    for path_token, expected_hash in portable_files.items():
        source_path = (root / path_token).resolve()
        try:
            source_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("portable source path escapes the project root") from exc
        if not source_path.is_file():
            raise ValueError(f"portable source file is unavailable: {path_token}")
        source_bytes = source_path.read_bytes()
        if path_token.endswith("/tasks.md") and (
            path_token.startswith("openspec/changes/") or path_token.startswith("specs/")
        ):
            source_bytes = normalize_provider_task_definition_bytes(source_bytes)
        if _sha256_bytes(source_bytes) != expected_hash:
            raise ValueError(f"portable source file is stale: {path_token}")

    for role, sidecar_ref in envelope.sidecar_refs.items():
        observed_hash = _sha256_bytes(
            _resolve_evidence_token(root, sidecar_ref).read_bytes()
        )
        if observed_hash != envelope.sidecar_hashes.get(role):
            raise ValueError(f"portable sidecar content hash mismatch: {role}")

    child_receipts: list[tuple[str, str]] = []
    for child_ref in envelope.child_receipt_refs:
        child_path = _resolve_evidence_token(root, child_ref)
        if _sha256_bytes(child_path.read_bytes()) != envelope.child_receipt_hashes.get(child_ref):
            raise ValueError("portable child receipt content hash mismatch")
        child = PortableSpecReceiptEnvelope.from_dict(_read_json(child_path))
        child_receipts.append((child.receipt_id, child.receipt_fingerprint))
    expected_receipt_id, expected_receipt_fingerprint = _portable_receipt_semantic_identity(
        provider_id=envelope.provider_id,
        work_package_id=envelope.work_package_id,
        check_id=envelope.check_id,
        semantic_check_id=envelope.semantic_check_id,
        execution_id=envelope.execution_id,
        execution_key=envelope.execution_key,
        source_manifest_id=envelope.source_manifest_id,
        source_manifest_hash=envelope.source_manifest_hash,
        source_hash_policy=envelope.source_hash_policy,
        source_fingerprint=envelope.source_fingerprint,
        toolchain_fingerprint=envelope.toolchain_fingerprint,
        result_fingerprint=envelope.result_fingerprint,
        termination_fingerprint=envelope.termination_fingerprint,
        snapshot_policy=envelope.snapshot_policy,
        coverage_ids=envelope.coverage_ids,
        validation_obligation_ids=envelope.validation_obligation_ids,
        sidecar_hashes=envelope.sidecar_hashes,
        child_receipts=child_receipts,
    )
    if envelope.receipt_id != expected_receipt_id:
        raise ValueError("portable receipt semantic identity mismatch")
    if envelope.receipt_fingerprint != expected_receipt_fingerprint:
        raise ValueError("portable receipt semantic fingerprint mismatch")
    return envelope.receipt_id, envelope


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


def _stored_spec_receipt_review(
    root: Path,
    receipt_id: str,
    *,
    seen: tuple[str, ...] = (),
) -> tuple[SpecReceiptConsumptionResult, EvidenceReceipt | None, Any | None]:
    findings: list[str] = []
    minimum: list[str] = []
    if receipt_id in seen:
        result = SpecReceiptConsumptionResult(
            receipt_id,
            "",
            False,
            False,
            ("receipt_child_cycle",),
            (f"recreate-receipt:{receipt_id}",),
        )
        return result, None, None
    try:
        envelope = _load_portable_envelope(root, receipt_id)
        receipt = load_evidence_receipt(
            receipt_id,
            root,
            output_directory=_receipt_directory(root),
        )
    except (OSError, ValueError) as exc:
        result = SpecReceiptConsumptionResult(
            receipt_id,
            "",
            False,
            False,
            (f"portable_receipt_unavailable:{type(exc).__name__}",),
            (f"recreate-receipt:{receipt_id}",),
        )
        return result, None, None

    metadata = receipt.to_dict()["metadata"]
    internal_snapshot_policy = (
        SPEC_SNAPSHOT_FROZEN_REQUIRED
        if envelope.snapshot_policy == "frozen"
        else SPEC_SNAPSHOT_LIVE_SCOPED
    )
    identity_pairs = (
        ("provider_id", envelope.provider_id, metadata.get("provider_id")),
        ("work_package_id", envelope.work_package_id, metadata.get("work_package_id")),
        ("check_id", envelope.check_id, metadata.get("check_id")),
        ("semantic_check_id", envelope.semantic_check_id, metadata.get("semantic_check_id")),
        ("execution_id", envelope.execution_id, metadata.get("execution_id")),
        ("execution_key", envelope.execution_key, metadata.get("execution_key")),
        ("toolchain_fingerprint", envelope.toolchain_fingerprint, metadata.get("toolchain_fingerprint")),
        ("result_fingerprint", envelope.result_fingerprint, receipt.result_fingerprint),
        ("termination_fingerprint", envelope.termination_fingerprint, metadata.get("termination_fingerprint")),
        ("snapshot_policy", internal_snapshot_policy, metadata.get("snapshot_policy")),
    )
    for name, expected, observed in identity_pairs:
        if str(expected) != str(observed):
            findings.append(f"portable_envelope_{name}_mismatch")
    expected_receipt_id = fingerprint_value(
        {
            "kind": receipt.subject_kind,
            "execution_id": envelope.execution_id,
            "execution_key": envelope.execution_key,
            "result_fingerprint": envelope.result_fingerprint,
            "termination_fingerprint": envelope.termination_fingerprint,
            "run_id": str(metadata.get("run_id", "")),
        }
    )
    if receipt.receipt_id != expected_receipt_id:
        findings.append("portable_receipt_id_content_binding_mismatch")
    if tuple(sorted(receipt.covered_obligations)) != envelope.validation_obligation_ids:
        findings.append("portable_validation_coverage_mismatch")
    if tuple(sorted(str(value) for value in metadata.get("coverage", ()))) != envelope.coverage_ids:
        findings.append("portable_declared_coverage_mismatch")
    portable_files: dict[str, str] = {}
    try:
        source_manifest_bytes = _resolve_evidence_token(root, envelope.source_manifest_ref).read_bytes()
        source_manifest_value = json.loads(source_manifest_bytes.decode("utf-8"))
        if not isinstance(source_manifest_value, Mapping):
            raise ValueError("portable source manifest must be an object")
        unknown_manifest_fields = set(source_manifest_value) - {
            "schema_version", "source_hash_policy", "manifest_id", "files"
        }
        if unknown_manifest_fields:
            raise ValueError(
                f"unknown portable source manifest fields: {sorted(unknown_manifest_fields)}"
            )
        if source_manifest_value.get("schema_version") != SPEC_PORTABLE_SOURCE_MANIFEST_SCHEMA:
            raise ValueError("unsupported portable source manifest schema")
        if source_manifest_value.get("source_hash_policy") != _portable_source_hash_policy():
            raise ValueError("unsupported portable source hash policy")
        files = source_manifest_value.get("files", {})
        if not isinstance(files, Mapping):
            raise ValueError("portable source manifest files must be a path/hash map")
        portable_files = dict(sorted((str(path), str(digest)) for path, digest in files.items()))
        if any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest)) is None
            for digest in files.values()
        ):
            raise ValueError("portable source manifest contains a non-canonical digest")
        expected_manifest_id = fingerprint_value(
            {
                "source_hash_policy": _portable_source_hash_policy(),
                "files": dict(sorted((str(path), str(digest)) for path, digest in files.items())),
            }
        )
        canonical_manifest_hash = _sha256_bytes(_canonical_json(source_manifest_value).encode("utf-8"))
        if canonical_manifest_hash != envelope.source_manifest_hash:
            findings.append("portable_source_manifest_hash_mismatch")
        if source_manifest_value.get("manifest_id") != expected_manifest_id:
            findings.append("portable_source_manifest_self_identity_mismatch")
        if expected_manifest_id != envelope.source_manifest_id:
            findings.append("portable_source_manifest_identity_mismatch")
        if fingerprint_value(portable_files) != envelope.source_fingerprint:
            findings.append("portable_source_fingerprint_mismatch")
        if envelope.source_hash_policy != _portable_source_hash_policy():
            findings.append("portable_source_hash_policy_unsupported")
    except (OSError, ValueError, json.JSONDecodeError):
        findings.append("portable_source_manifest_unavailable")
    for name, path_token in envelope.sidecar_refs.items():
        try:
            observed_hash = _sha256_bytes(_resolve_evidence_token(root, path_token).read_bytes())
        except (OSError, ValueError):
            findings.append(f"portable_sidecar_unavailable:{name}")
            continue
        if observed_hash != envelope.sidecar_hashes.get(name):
            findings.append(f"portable_sidecar_hash_mismatch:{name}")

    try:
        package = _load_package(root, envelope.provider_id, envelope.work_package_id)
        owner_checks = _load_owner_checks(root, envelope.provider_id, envelope.work_package_id)
        declared = next((row for row in owner_checks if row.check_id == envelope.check_id), None)
        if declared is None:
            raise ValueError("declared check is unavailable")
        current_toolchain = project_execution_toolchain_snapshot(
            capture_spec_toolchain_snapshot(package),
            cross_change_safe=bool(declared.cross_change_safe),
        )
        current_scope = capture_spec_input_manifest(
            root,
            input_paths=declared.input_paths,
            normalize_provider_tasks=True,
        )
    except (OSError, ValueError) as exc:
        findings.append(f"portable_current_context_unavailable:{type(exc).__name__}")
        result = SpecReceiptConsumptionResult(
            receipt_id,
            envelope.fingerprint,
            False,
            False,
            tuple(dict.fromkeys(findings)),
            (envelope.check_id or f"recreate-receipt:{receipt_id}",),
        )
        return result, receipt, None

    if declared.semantic_check_id != envelope.semantic_check_id:
        findings.append("portable_semantic_check_id_not_declared")
    if declared.execution_id != envelope.execution_id:
        findings.append("portable_execution_id_not_current")
    if set(declared.validation_obligation_ids) != set(envelope.validation_obligation_ids):
        findings.append("portable_required_validation_coverage_missing")
    if set((*declared.obligation_ids, *declared.coverage_ids)) != set(envelope.coverage_ids):
        findings.append("portable_required_coverage_missing")
    if current_toolchain.fingerprint != envelope.toolchain_fingerprint:
        findings.append("portable_toolchain_not_current")
    if portable_files and dict(sorted(_portable_source_files(current_scope).items())) != portable_files:
        findings.append("portable_source_manifest_not_current")
    if envelope.snapshot_policy == "frozen" and not os.environ.get(
        "FLOWGUARD_SPEC_EVIDENCE_ROOT", ""
    ).strip():
        findings.append("portable_receipt_not_in_persistent_evidence_store")

    validation_ids = tuple(receipt.covered_obligations)
    current_manifest = _manifest_with_obligations(current_scope, validation_ids)
    child_receipts: dict[str, EvidenceReceipt] = {}
    child_reviews: dict[str, Any] = {}
    child_semantic_receipts: list[tuple[str, str]] = []
    for child in receipt.consumed_child_receipts:
        child_result, child_receipt, child_review = _stored_spec_receipt_review(
            root,
            child.receipt_id,
            seen=(*seen, receipt_id),
        )
        if child_receipt is not None:
            child_receipts[child.receipt_id] = child_receipt
            child_ref = _portable_evidence_token(
                root, _portable_envelope_path(root, child.receipt_id)
            )
            if child_ref not in envelope.child_receipt_refs:
                findings.append(f"portable_child_receipt_ref_missing:{child.receipt_id}")
            try:
                child_envelope_path = _resolve_evidence_token(root, child_ref)
                if _sha256_bytes(child_envelope_path.read_bytes()) != envelope.child_receipt_hashes.get(child_ref):
                    findings.append(f"portable_child_receipt_hash_mismatch:{child.receipt_id}")
                child_envelope = PortableSpecReceiptEnvelope.from_dict(
                    _read_json(child_envelope_path)
                )
                if (
                    child_envelope.check_id != str(child_receipt.to_dict()["metadata"].get("check_id", ""))
                ):
                    findings.append(f"portable_child_receipt_identity_mismatch:{child.receipt_id}")
                child_semantic_receipts.append(
                    (child_envelope.receipt_id, child_envelope.receipt_fingerprint)
                )
            except (OSError, ValueError):
                findings.append(f"portable_child_envelope_unavailable:{child.receipt_id}")
        if child_review is not None:
            child_reviews[child.receipt_id] = child_review
        if not child_result.ok:
            findings.append(f"portable_child_receipt_not_current:{child.receipt_id}")
            minimum.extend(child_result.minimum_revalidation)

    expected_portable_receipt_id, expected_portable_receipt_fingerprint = (
        _portable_receipt_semantic_identity(
            provider_id=envelope.provider_id,
            work_package_id=envelope.work_package_id,
            check_id=envelope.check_id,
            semantic_check_id=envelope.semantic_check_id,
            execution_id=envelope.execution_id,
            execution_key=envelope.execution_key,
            source_manifest_id=envelope.source_manifest_id,
            source_manifest_hash=envelope.source_manifest_hash,
            source_hash_policy=envelope.source_hash_policy,
            source_fingerprint=envelope.source_fingerprint,
            toolchain_fingerprint=envelope.toolchain_fingerprint,
            result_fingerprint=envelope.result_fingerprint,
            termination_fingerprint=envelope.termination_fingerprint,
            snapshot_policy=envelope.snapshot_policy,
            coverage_ids=envelope.coverage_ids,
            validation_obligation_ids=envelope.validation_obligation_ids,
            sidecar_hashes=envelope.sidecar_hashes,
            child_receipts=child_semantic_receipts,
        )
    )
    if envelope.receipt_id != expected_portable_receipt_id:
        findings.append("portable_receipt_id_semantic_mismatch")
    if envelope.receipt_fingerprint != expected_portable_receipt_fingerprint:
        findings.append("portable_receipt_fingerprint_semantic_mismatch")

    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _version("flowguard"),
        }
    )
    if receipt.subject_kind == "spec_check_aggregate":
        coverage = tuple(sorted(str(value) for value in metadata.get("coverage", ())))
        expected_execution_key = fingerprint_value(
            {
                "execution_id": declared.execution_id,
                "child_receipts": sorted(
                    (item.receipt_id, item.receipt_fingerprint)
                    for item in receipt.consumed_child_receipts
                ),
                "coverage": list(coverage),
            }
        )
        expected_result = fingerprint_value(
            {
                "terminal_status": SPEC_TERMINAL_PASS,
                "child_receipts": sorted(
                    (item.receipt_id, item.receipt_fingerprint)
                    for item in receipt.consumed_child_receipts
                ),
                "coverage": list(coverage),
            }
        )
        expected_termination = fingerprint_value(
            {"terminal_status": SPEC_TERMINAL_PASS, "exit_code": 0, "aggregated": True}
        )
        definition_hash = declared.execution_id
        suite_map_hash = fingerprint_value({"coverage": list(coverage)})
    else:
        stored_tool_versions = metadata.get("tool_versions", {})
        current_command_for_tool = receipt.command
        if isinstance(stored_tool_versions, Mapping) and stored_tool_versions.get("command_entry_name"):
            current_command_for_tool = (
                str(stored_tool_versions["command_entry_name"]),
                *receipt.command[1:],
            )
        tools, tools_hash = _tool_fingerprint(
            current_command_for_tool,
            cwd=root,
            declared_toolchain_identity=declared.toolchain_identity,
        )
        dependency_fingerprints = {
            str(key): str(value)
            for key, value in dict(metadata.get("dependency_receipt_fingerprints", {})).items()
        }
        coverage = tuple(sorted(str(value) for value in metadata.get("coverage", ())))
        definition = _definition(
            provider_id=envelope.provider_id,
            work_package_id=envelope.work_package_id,
            check_id=envelope.check_id,
            semantic_id=declared.semantic_check_id,
            command=receipt.command,
            working_directory_token=receipt.working_directory_token,
            expected_exit_code=int(metadata.get("expected_exit_code", declared.expected_exit_code)),
            timeout_seconds=metadata.get("timeout_seconds", declared.timeout_seconds),
            cross_change_safe=bool(metadata.get("cross_change_safe", declared.cross_change_safe)),
            validation_obligation_ids=validation_ids,
            coverage=coverage,
            input_fingerprint=current_scope.fingerprint,
            environment_fingerprint=environment.fingerprint,
            tool_fingerprint=tools_hash,
            toolchain_fingerprint=current_toolchain.fingerprint,
            snapshot_policy=internal_snapshot_policy,
            input_paths=declared.input_paths,
            dependency_receipt_fingerprints=dependency_fingerprints,
            execution_owner_id=declared.execution_owner_id,
            declared_toolchain_identity=declared.toolchain_identity,
        )
        stored_definition = metadata.get("execution_definition", {})
        if not isinstance(stored_definition, Mapping) or dict(stored_definition) != definition:
            findings.append("portable_execution_definition_not_current")
        expected_execution_key = fingerprint_value(definition)
        definition_hash = fingerprint_value({key: value for key, value in definition.items() if key != "input_fingerprint"})
        suite_map_hash = fingerprint_value(
            {
                "validation_obligations": list(validation_ids),
                "coverage": (
                    "consumer-local"
                    if bool(metadata.get("cross_change_safe", declared.cross_change_safe))
                    else list(coverage)
                ),
            }
        )
        expected_result = _result_files_fingerprint(root, receipt)
        terminal_status = str(metadata.get("terminal_status", ""))
        expected_termination = fingerprint_value(
            {
                "terminal_status": terminal_status,
                "exit_code": receipt.exit_code,
                "expected_exit_code": int(metadata.get("expected_exit_code", declared.expected_exit_code)),
                "timed_out": terminal_status == SPEC_TERMINAL_TIMEOUT,
                "blocked": terminal_status == SPEC_TERMINAL_BLOCKED,
                "process_tree_cleanup_confirmed": bool(
                    metadata.get("process_tree_cleanup_confirmed", False)
                ),
            }
        )
        del tools

    if expected_execution_key != envelope.execution_key:
        findings.append("portable_execution_key_not_current")
    if expected_result != envelope.result_fingerprint:
        findings.append("portable_result_sidecars_not_current")
    if expected_termination != envelope.termination_fingerprint:
        findings.append("portable_termination_not_current")
    for content_name, expected_fingerprint in (
        ("result", envelope.result_fingerprint),
        ("termination", envelope.termination_fingerprint),
    ):
        path_token = envelope.sidecar_refs.get(content_name, "")
        if not path_token:
            findings.append(f"portable_identity_sidecar_missing:{content_name}")
            continue
        try:
            value = _read_json(_resolve_evidence_token(root, path_token))
        except (OSError, ValueError):
            findings.append(f"portable_identity_sidecar_invalid:{content_name}")
            continue
        if fingerprint_value(value) != expected_fingerprint:
            findings.append(f"portable_identity_sidecar_fingerprint_mismatch:{content_name}")

    context = ReceiptVerificationContext(
        input_snapshots={item.artifact_id: item for item in current_manifest.snapshots},
        contract_hash=definition_hash,
        check_manifest_hash=definition_hash,
        suite_map_hash=suite_map_hash,
        producer_id="flowguard.spec_check_cache",
        producer_version=_version("flowguard"),
        environment_fingerprint=environment.fingerprint,
        proof_artifact_fingerprint=expected_result,
        result_fingerprint=expected_result,
        command=receipt.command,
        working_directory_token=receipt.working_directory_token,
        proof_artifact_id=receipt.proof_artifact_id,
        required_obligation_ids=validation_ids,
        eligible_claim_scopes=(SPEC_CHECK_CLAIM_SCOPE,),
        child_receipts=child_receipts,
        child_verification_results=child_reviews,
    )
    canonical_review = verify_evidence_receipt(receipt, context)
    findings.extend(canonical_review.finding_codes)
    minimum.extend(canonical_review.minimum_revalidation)
    if findings:
        minimum.append(envelope.check_id)
    result = SpecReceiptConsumptionResult(
        receipt_id,
        envelope.fingerprint,
        canonical_review.current and not findings,
        canonical_review.eligible and receipt.result_status == RECEIPT_STATUS_PASS,
        tuple(dict.fromkeys(findings)),
        tuple(dict.fromkeys(value for value in minimum if value)),
    )
    return result, receipt, canonical_review


def consume_spec_receipt(
    root: str | Path,
    *,
    receipt_id: str = "",
    provider_id: str = "",
    work_package_id: str = "",
    check_id: str = "",
    portable_ref: str = "",
) -> SpecReceiptConsumptionResult:
    """Purely read and independently reverify one canonical FlowGuard receipt."""

    project_root = _project_root(root)
    resolved_receipt_id = str(receipt_id)
    if portable_ref:
        if not (provider_id and work_package_id and check_id):
            raise ValueError("portable-ref requires provider/work-package/check-id identity")
        expected_ref = _portable_evidence_token(
            project_root,
            _portable_receipt_ref_path(project_root, provider_id, work_package_id, check_id),
        )
        if portable_ref != expected_ref:
            raise ValueError("portable receipt ref token does not match the declared stable identity")
    if not resolved_receipt_id:
        if not (provider_id and work_package_id and check_id):
            raise ValueError("receipt-id or provider/work-package/check-id is required")
        try:
            _, _ = _load_portable_receipt_ref(
                project_root,
                provider_id,
                work_package_id,
                check_id,
            )
            session = _load_session(project_root, provider_id, work_package_id)
            row = session.get("check_results", {}).get(check_id, {})
            if not isinstance(row, Mapping) or not str(row.get("receipt_id", "")):
                raise ValueError("internal owner observation receipt is unavailable")
            resolved_receipt_id = str(row["receipt_id"])
        except ValueError:
            return SpecReceiptConsumptionResult(
                "",
                "",
                False,
                False,
                (f"required_receipt_missing:{check_id}",),
                (check_id,),
            )
    result, _, _ = _stored_spec_receipt_review(project_root, resolved_receipt_id)
    return result


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
    execution_id: str,
    toolchain_fingerprint: str,
    snapshot_policy: str,
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
            "execution_id",
            "semantic_check_id",
            "toolchain_fingerprint",
            "snapshot_policy",
            "stdout_sha256",
            "stderr_sha256",
            "termination_fingerprint",
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
        if metadata.get("execution_id") != execution_id:
            stale_reasons.append("receipt_execution_id_mismatch")
            continue
        if metadata.get("toolchain_fingerprint") != toolchain_fingerprint:
            stale_reasons.append("receipt_toolchain_fingerprint_mismatch")
            continue
        if metadata.get("snapshot_policy") != snapshot_policy:
            stale_reasons.append("receipt_snapshot_policy_mismatch")
            continue
        result_files = metadata.get("result_files", {})
        try:
            stdout = _resolve_evidence_token(root, str(result_files["stdout"])).read_bytes()
            stderr = _resolve_evidence_token(root, str(result_files["stderr"])).read_bytes()
        except (KeyError, OSError, TypeError):
            stale_reasons.append("receipt_result_files_missing")
            continue
        if metadata.get("stdout_sha256") != _sha256_bytes(stdout):
            stale_reasons.append("receipt_stdout_hash_mismatch")
            continue
        if metadata.get("stderr_sha256") != _sha256_bytes(stderr):
            stale_reasons.append("receipt_stderr_hash_mismatch")
            continue
        expected_receipt_id = fingerprint_value(
            {
                "kind": "spec_check_execution",
                "execution_id": execution_id,
                "execution_key": execution_key,
                "result_fingerprint": receipt.result_fingerprint,
                "termination_fingerprint": str(metadata.get("termination_fingerprint", "")),
                "run_id": str(metadata.get("run_id", "")),
            }
        )
        if receipt.receipt_id != expected_receipt_id:
            stale_reasons.append("receipt_id_content_binding_mismatch")
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
            if pid > 0:
                if _pid_alive(pid):
                    raise RuntimeError("identical spec check is already executing")
            elif age <= self.stale_after_seconds:
                # A malformed or identity-free lock cannot be proven abandoned
                # until its bounded recovery window has elapsed.
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
        "stdout": _evidence_token(root, stdout_path),
        "stderr": _evidence_token(root, stderr_path),
    }


def _write_execution_identity_sidecars(
    root: Path,
    result_paths: Mapping[str, str],
    result_value: Mapping[str, Any],
    termination_value: Mapping[str, Any],
) -> dict[str, str]:
    output = _resolve_evidence_token(root, str(result_paths["stdout"])).parent
    result_path = output / "result.json"
    termination_path = output / "termination.json"
    _atomic_json(result_path, result_value)
    _atomic_json(termination_path, termination_value)
    return {
        **dict(result_paths),
        "result": _evidence_token(root, result_path),
        "termination": _evidence_token(root, termination_path),
    }


class _ProcessTreeTimeout(subprocess.TimeoutExpired):
    def __init__(self, *args, cleanup_confirmed: bool, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cleanup_confirmed = bool(cleanup_confirmed)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> bool:
    """Terminate the complete check process tree and confirm the owner exited."""

    if process.poll() is not None:
        return True
    if os.name == "nt":
        try:
            killer = subprocess.Popen(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            killer.wait(timeout=10)
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            import signal

            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=3)
        except (OSError, subprocess.SubprocessError):
            try:
                import signal

                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                try:
                    process.kill()
                except OSError:
                    pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        return False
    return process.poll() is not None


def _run_command_tree(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[bytes]:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    child_environment = dict(os.environ)
    # The persistent evidence root belongs to this orchestration process.  A
    # nested test/project must resolve its own evidence boundary instead of
    # reading or writing the parent's receipts.
    child_environment.pop(SPEC_EVIDENCE_ROOT_ENV, None)
    process = subprocess.Popen(
        [str(value) for value in command],
        cwd=cwd,
        env=child_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        cleanup_confirmed = _terminate_process_tree(process)
        try:
            final_stdout, final_stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            final_stdout, final_stderr = b"", b""
            cleanup_confirmed = False
        raise _ProcessTreeTimeout(
            command,
            timeout_seconds,
            output=(exc.output or b"") + (final_stdout or b""),
            stderr=(exc.stderr or b"") + (final_stderr or b""),
            cleanup_confirmed=cleanup_confirmed,
        ) from exc
    return subprocess.CompletedProcess(command, int(process.returncode or 0), stdout, stderr)


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
    requested_dependency_ids = tuple(dict.fromkeys(str(value) for value in depends_on if str(value)))
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
    owner_checks = _load_owner_checks(project_root, provider_id, work_package_id)
    declared_check = next((item for item in owner_checks if item.check_id == check_id), None)
    if declared_check is None:
        raise ValueError(f"check is not declared by the provider work package: {check_id}")
    if declared_check.execution_owner_id != "flowguard.spec_check_cache":
        raise ValueError(
            f"check is not owned by the canonical FlowGuard executor: {check_id}"
        )
    dependency_ids = tuple(
        dict.fromkeys(
            (
                *declared_check.depends_on,
                *declared_check.dependency_input_ids,
                *requested_dependency_ids,
            )
        )
    )
    semantic_check_id = declared_check.semantic_check_id or semantic_id
    execution_id = declared_check.execution_id
    session_snapshot_policy = str(session.get("snapshot_policy", SPEC_SNAPSHOT_LIVE_SCOPED))
    snapshot_policy = (
        SPEC_SNAPSHOT_FROZEN_REQUIRED
        if session_snapshot_policy == SPEC_SNAPSHOT_FROZEN_REQUIRED
        or declared_check.snapshot_policy == SPEC_SNAPSHOT_FROZEN_REQUIRED
        else SPEC_SNAPSHOT_LIVE_SCOPED
    )
    input_paths = declared_check.input_paths
    begin_toolchain = project_execution_toolchain_snapshot(
        SpecToolchainSnapshot.from_dict(session.get("toolchain_snapshot", {})),
        cross_change_safe=bool(declared_check.cross_change_safe),
    )
    current_toolchain = project_execution_toolchain_snapshot(
        capture_spec_toolchain_snapshot(package),
        cross_change_safe=bool(declared_check.cross_change_safe),
    )
    if cross_change_safe and not declared_check.cross_change_safe:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_check_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            blockers=("cross_change_safe_not_authorized_by_provider",),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
            execution_id=execution_id,
            input_paths=input_paths,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=begin_toolchain.fingerprint,
            minimum_revalidation=(check_id,),
        )
        _record_check_result(project_root, result)
        return result
    if session.get("state") != "begun":
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_check_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            dependency_ids=dependency_ids,
            blockers=("spec_session_not_active",),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
            execution_id=execution_id,
            input_paths=input_paths,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=begin_toolchain.fingerprint,
        )
        return result
    recorded = session.get("check_results", {})
    unsatisfied = tuple(
        dependency
        for dependency in dependency_ids
        if not isinstance(recorded.get(dependency), Mapping)
        or not bool(recorded[dependency].get("ok", False))
        or not str(recorded[dependency].get("receipt_fingerprint", ""))
    )
    if unsatisfied:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_check_id,
            SPEC_CHECK_STATE_NOT_RUN,
            SPEC_TERMINAL_NOT_RUN_DEPENDENCY,
            dependency_ids=dependency_ids,
            blockers=tuple(f"dependency_not_passed:{item}" for item in unsatisfied),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
            execution_id=execution_id,
            input_paths=input_paths,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=begin_toolchain.fingerprint,
            minimum_revalidation=(check_id,),
        )
        _record_check_result(project_root, result)
        return result

    begin = _load_manifest(project_root, str(session["begin_manifest_path"]))
    # A frozen session freezes *when* scoped evidence may be admitted; it does
    # not widen every check to the whole repository.  Execution identity and
    # minimum revalidation therefore always use the declaration's exact scope.
    begin_scope = _manifest_subset(begin, input_paths)
    current_scope = capture_spec_input_manifest(
        project_root, input_paths=input_paths, normalize_provider_tasks=True
    )
    source_changed = current_scope.fingerprint != begin_scope.fingerprint
    toolchain_changed = current_toolchain.fingerprint != begin_toolchain.fingerprint
    if source_changed or toolchain_changed:
        changes = _manifest_changes(begin_scope, current_scope)
        reasons = tuple(f"session_input_{kind}:{item}" for kind, items in changes.items() for item in items)
        if toolchain_changed:
            reasons += ("session_toolchain_changed",)
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_check_id,
            SPEC_CHECK_STATE_STALE,
            SPEC_TERMINAL_BLOCKED,
            dependency_ids=dependency_ids,
            blockers=(("session_inputs_changed_before_check",) if source_changed else ())
            + (("session_toolchain_changed_before_check",) if toolchain_changed else ()),
            stale_reasons=reasons,
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=str(session.get("begin_fingerprint", "")),
            execution_id=execution_id,
            input_paths=input_paths,
            input_fingerprint=current_scope.fingerprint,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=begin_toolchain.fingerprint,
            minimum_revalidation=(check_id,),
        )
        _record_check_result(project_root, result)
        return result
    current = _manifest_with_obligations(current_scope, validation_obligation_ids)
    # Ordering dependencies gate execution but do not implicitly redefine the
    # physical result.  Only explicitly declared dependency inputs participate
    # in the execution key; the parent aggregation still binds the complete
    # child receipt set for release/closure claims.
    dependency_receipt_fingerprints = {
        dependency: str(recorded[dependency]["receipt_fingerprint"])
        for dependency in declared_check.dependency_input_ids
    }

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
    tools, tools_hash = _tool_fingerprint(
        command,
        cwd=cwd,
        declared_toolchain_identity=declared_check.toolchain_identity,
    )
    validation_ids = tuple(sorted(set(str(value) for value in validation_obligation_ids)))
    coverage_ids = tuple(
        sorted(
            set(
                str(value)
                for value in (
                    *declared_check.obligation_ids,
                    *declared_check.coverage_ids,
                    *coverage,
                )
                if str(value)
            )
        )
    )
    definition = _definition(
        provider_id=provider_id,
        work_package_id=work_package_id,
        check_id=check_id,
        semantic_id=semantic_check_id,
        command=command_tokens,
        working_directory_token=cwd_token,
        expected_exit_code=expected_exit_code,
        timeout_seconds=timeout_seconds,
        cross_change_safe=cross_change_safe,
        validation_obligation_ids=validation_ids,
        coverage=coverage_ids,
        input_fingerprint=current_scope.fingerprint,
        environment_fingerprint=environment.fingerprint,
        tool_fingerprint=tools_hash,
        toolchain_fingerprint=begin_toolchain.fingerprint,
        snapshot_policy=snapshot_policy,
        input_paths=input_paths,
        dependency_receipt_fingerprints=dependency_receipt_fingerprints,
        execution_owner_id=declared_check.execution_owner_id,
        declared_toolchain_identity=declared_check.toolchain_identity,
    )
    execution_key = fingerprint_value(definition)
    definition_hash = fingerprint_value({key: value for key, value in definition.items() if key != "input_fingerprint"})
    suite_map_hash = fingerprint_value(
        {
            "validation_obligations": validation_ids,
            "coverage": ("consumer-local" if cross_change_safe else coverage_ids),
        }
    )
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
        execution_id=execution_id,
        toolchain_fingerprint=begin_toolchain.fingerprint,
        snapshot_policy=snapshot_policy,
    )
    if reusable is not None:
        reusable_envelope_path = _portable_envelope_path(project_root, reusable.receipt_id)
        reusable_envelope = _load_portable_envelope(project_root, reusable.receipt_id)
        _save_portable_receipt_ref(
            project_root,
            envelope=reusable_envelope,
            envelope_path=reusable_envelope_path,
            provider_id=provider_id,
            work_package_id=work_package_id,
            check_id=check_id,
            coverage_ids=coverage_ids,
        )
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_check_id,
            SPEC_CHECK_STATE_REUSED_CURRENT,
            SPEC_TERMINAL_PASS,
            receipt_id=reusable.receipt_id,
            receipt_fingerprint=reusable.fingerprint,
            execution_key=execution_key,
            execution_id=execution_id,
            exit_code=reusable.exit_code,
            dependency_ids=dependency_ids,
            consumer_id=consumer_id,
            result_paths=dict(reusable.metadata).get("result_files", {}),
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=begin_scope.fingerprint,
            check_post_fingerprint=current_scope.fingerprint,
            input_paths=input_paths,
            input_fingerprint=current_scope.fingerprint,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=begin_toolchain.fingerprint,
            dependency_receipt_fingerprints=dependency_receipt_fingerprints,
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
                execution_id=execution_id,
                toolchain_fingerprint=begin_toolchain.fingerprint,
                snapshot_policy=snapshot_policy,
            )
            if reusable is not None:
                reusable_envelope_path = _portable_envelope_path(project_root, reusable.receipt_id)
                reusable_envelope = _load_portable_envelope(project_root, reusable.receipt_id)
                _save_portable_receipt_ref(
                    project_root,
                    envelope=reusable_envelope,
                    envelope_path=reusable_envelope_path,
                    provider_id=provider_id,
                    work_package_id=work_package_id,
                    check_id=check_id,
                    coverage_ids=coverage_ids,
                )
                result = SpecCheckExecutionResult(
                    provider_id,
                    work_package_id,
                    check_id,
                    semantic_check_id,
                    SPEC_CHECK_STATE_REUSED_CURRENT,
                    SPEC_TERMINAL_PASS,
                    receipt_id=reusable.receipt_id,
                    receipt_fingerprint=reusable.fingerprint,
                    execution_key=execution_key,
                    execution_id=execution_id,
                    exit_code=reusable.exit_code,
                    dependency_ids=dependency_ids,
                    consumer_id=consumer_id,
                    result_paths=dict(reusable.metadata).get("result_files", {}),
                    session_id=str(session.get("session_id", "")),
                    begin_fingerprint=begin_scope.fingerprint,
                    check_post_fingerprint=current_scope.fingerprint,
                    input_paths=input_paths,
                    input_fingerprint=current_scope.fingerprint,
                    snapshot_policy=snapshot_policy,
                    toolchain_fingerprint=begin_toolchain.fingerprint,
                    dependency_receipt_fingerprints=dependency_receipt_fingerprints,
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
            process_tree_cleanup_confirmed = True
            try:
                completed = _run_command_tree(
                    command,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                )
                stdout = completed.stdout or b""
                stderr = completed.stderr or b""
                exit_code = int(completed.returncode)
                terminal_status = SPEC_TERMINAL_PASS if exit_code == expected_exit_code else SPEC_TERMINAL_FAIL
            except _ProcessTreeTimeout as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                exit_code = -1
                terminal_status = SPEC_TERMINAL_TIMEOUT
                blockers.append("check_timeout")
                process_tree_cleanup_confirmed = exc.cleanup_confirmed
                if not process_tree_cleanup_confirmed:
                    terminal_status = SPEC_TERMINAL_BLOCKED
                    blockers.append("process_tree_cleanup_unconfirmed")
            except OSError as exc:
                stderr = str(exc).encode("utf-8", errors="replace")
                exit_code = -1
                terminal_status = SPEC_TERMINAL_ERROR
                blockers.append("check_execution_error")
            finished_at = _utc_now()
            duration = time.monotonic() - started_clock
            after = capture_spec_input_manifest(
                project_root,
                input_paths=input_paths,
                normalize_provider_tasks=True,
            )
            check_post_manifest_path = _save_manifest(project_root, after)
            changes = _manifest_changes(current_scope, after)
            mutated = any(changes.values())
            if mutated:
                terminal_status = SPEC_TERMINAL_BLOCKED
                blockers.append("check_input_changed_during_run")
            run_id = uuid.uuid4().hex
            result_paths = _write_output_files(project_root, execution_key, run_id, stdout, stderr)
            stdout_hash = _sha256_bytes(stdout)
            stderr_hash = _sha256_bytes(stderr)
            result_value = {
                "exit_code": exit_code,
                "terminal_status": terminal_status,
                "stdout_sha256": stdout_hash,
                "stderr_sha256": stderr_hash,
            }
            result_hash = fingerprint_value(result_value)
            termination_value = {
                "terminal_status": terminal_status,
                "exit_code": exit_code,
                "expected_exit_code": expected_exit_code,
                "timed_out": terminal_status == SPEC_TERMINAL_TIMEOUT,
                "blocked": terminal_status == SPEC_TERMINAL_BLOCKED,
                "process_tree_cleanup_confirmed": process_tree_cleanup_confirmed,
            }
            termination_hash = fingerprint_value(termination_value)
            result_paths = _write_execution_identity_sidecars(
                project_root,
                result_paths,
                result_value,
                termination_value,
            )
            receipt_status = {
                SPEC_TERMINAL_PASS: RECEIPT_STATUS_PASS,
                SPEC_TERMINAL_FAIL: RECEIPT_STATUS_FAIL,
                SPEC_TERMINAL_TIMEOUT: RECEIPT_STATUS_ERROR,
                SPEC_TERMINAL_BLOCKED: RECEIPT_STATUS_BLOCKED,
                SPEC_TERMINAL_ERROR: RECEIPT_STATUS_ERROR,
            }[terminal_status]
            receipt_id = fingerprint_value(
                {
                    "kind": "spec_check_execution",
                    "execution_id": execution_id,
                    "execution_key": execution_key,
                    "result_fingerprint": result_hash,
                    "termination_fingerprint": termination_hash,
                    "run_id": run_id,
                }
            )
            receipt = EvidenceReceipt(
                receipt_id=receipt_id,
                subject_id=semantic_check_id,
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
                    "provider_id": provider_id,
                    "work_package_id": work_package_id,
                    "check_id": check_id,
                    "execution_key": execution_key,
                    "execution_definition": definition,
                    "execution_id": execution_id,
                    "semantic_id": semantic_check_id,
                    "semantic_check_id": semantic_check_id,
                    "cross_change_safe": cross_change_safe,
                    "timeout_seconds": timeout_seconds,
                    "expected_exit_code": expected_exit_code,
                    "coverage": list(coverage_ids),
                    "tool_versions": tools,
                    "tool_fingerprint": tools_hash,
                    "toolchain_fingerprint": begin_toolchain.fingerprint,
                    "snapshot_policy": snapshot_policy,
                    "input_paths": list(input_paths),
                    "input_fingerprint": current_scope.fingerprint,
                    "dependency_receipt_fingerprints": dependency_receipt_fingerprints,
                    "terminal_status": terminal_status,
                    "stdout_sha256": stdout_hash,
                    "stderr_sha256": stderr_hash,
                    "termination_fingerprint": termination_hash,
                    "run_id": run_id,
                    "process_tree_cleanup_confirmed": process_tree_cleanup_confirmed,
                    "result_files": result_paths,
                    "changed_inputs": changes,
                    "recovered_abandoned_lock": lock.recovered_path,
                    "session_id": str(session.get("session_id", "")),
                    "snapshot_manifest_id": str(session.get("snapshot_manifest_id", begin.fingerprint)),
                    "begin_manifest_path": str(session.get("begin_manifest_path", "")),
                    "begin_fingerprint": begin_scope.fingerprint,
                    "session_begin_fingerprint": begin.fingerprint,
                    "check_post_manifest_path": check_post_manifest_path,
                    "check_post_fingerprint": after.fingerprint,
                    "command_fingerprint": fingerprint_value(list(command_tokens)),
                },
            )
            save_evidence_receipt(receipt, project_root, output_directory=_receipt_directory(project_root))
            _save_portable_envelope(project_root, receipt)
            state = SPEC_CHECK_STATE_EXECUTED if terminal_status == SPEC_TERMINAL_PASS else SPEC_CHECK_STATE_BLOCKED
            result = SpecCheckExecutionResult(
                provider_id,
                work_package_id,
                check_id,
                semantic_check_id,
                state,
                terminal_status,
                receipt_id=receipt.receipt_id,
                receipt_fingerprint=receipt.fingerprint,
                execution_key=execution_key,
                execution_id=execution_id,
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
                begin_fingerprint=begin_scope.fingerprint,
                check_post_fingerprint=after.fingerprint,
                input_paths=input_paths,
                input_fingerprint=current_scope.fingerprint,
                snapshot_policy=snapshot_policy,
                toolchain_fingerprint=begin_toolchain.fingerprint,
                dependency_receipt_fingerprints=dependency_receipt_fingerprints,
                minimum_revalidation=((check_id,) if mutated else ()),
            )
            _record_check_result(project_root, result)
            return result
    except RuntimeError as exc:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            semantic_check_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            execution_key=execution_key,
            execution_id=execution_id,
            dependency_ids=dependency_ids,
            blockers=(str(exc),),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=begin_scope.fingerprint,
            check_post_fingerprint=current_scope.fingerprint,
            input_paths=input_paths,
            input_fingerprint=current_scope.fingerprint,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=begin_toolchain.fingerprint,
            dependency_receipt_fingerprints=dependency_receipt_fingerprints,
            minimum_revalidation=(check_id,),
        )
        _record_check_result(project_root, result)
        return result


def aggregate_spec_check_receipts(
    root: str | Path,
    *,
    provider_id: str,
    work_package_id: str,
    check_id: str,
    child_receipt_ids: Sequence[str] = (),
) -> SpecCheckExecutionResult:
    """Aggregate current child receipts without reexecuting their covered work."""

    project_root = _project_root(root)
    session = _load_session(project_root, provider_id, work_package_id)
    package = _load_package(project_root, provider_id, work_package_id)
    owner_checks = _load_owner_checks(project_root, provider_id, work_package_id)
    declared = next((item for item in owner_checks if item.check_id == check_id), None)
    if declared is None:
        raise ValueError(f"check is not declared by the provider work package: {check_id}")
    if declared.execution_mode != SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS:
        raise ValueError("receipt aggregation requires an aggregate-child-receipts check")
    recorded = session.get("check_results", {})
    blockers: list[str] = []
    revalidation_seeds: list[str] = []
    expected_child_receipts: dict[str, str] = {}
    for child_id in declared.child_check_ids:
        row = recorded.get(child_id, {})
        if not isinstance(row, Mapping) or not bool(row.get("ok", False)) or not str(row.get("receipt_id", "")):
            blockers.append(f"aggregate_child_check_result_missing:{child_id}")
            revalidation_seeds.append(child_id)
            continue
        expected_child_receipts[child_id] = str(row["receipt_id"])
    resolved_ids = tuple(dict.fromkeys(str(value) for value in child_receipt_ids if str(value)))
    expected_ids = tuple(expected_child_receipts.get(child_id, "") for child_id in declared.child_check_ids)
    expected_ids = tuple(value for value in expected_ids if value)
    if not resolved_ids:
        resolved_ids = expected_ids
    elif set(resolved_ids) != set(expected_ids) or len(resolved_ids) != len(expected_ids):
        blockers.append("aggregate_child_receipt_set_not_declared")
        revalidation_seeds.extend(declared.child_check_ids)
    receipts: list[EvidenceReceipt] = []
    for child_id in declared.child_check_ids:
        receipt_id = expected_child_receipts.get(child_id, "")
        if not receipt_id or receipt_id not in resolved_ids:
            continue
        child_review, receipt, _ = _stored_spec_receipt_review(project_root, receipt_id)
        if receipt is None:
            blockers.append(f"child_receipt_unavailable:{child_id}")
            revalidation_seeds.append(child_id)
            continue
        if str(dict(receipt.metadata).get("check_id", "")) != child_id:
            blockers.append(f"child_receipt_not_declared_child:{child_id}:{receipt_id}")
            revalidation_seeds.append(child_id)
            continue
        if not child_review.ok or receipt.result_status != RECEIPT_STATUS_PASS or receipt.blockers:
            blockers.append(f"child_receipt_not_current_pass:{child_id}:{receipt_id}")
            revalidation_seeds.extend(child_review.minimum_revalidation or (child_id,))
            continue
        receipts.append(receipt)
    snapshot_policy = str(session.get("snapshot_policy", SPEC_SNAPSHOT_LIVE_SCOPED))
    begin_fingerprint = str(session.get("begin_fingerprint", ""))
    toolchain_fingerprint = str(session.get("toolchain_fingerprint", ""))
    begin_manifest = _load_manifest(project_root, str(session["begin_manifest_path"]))
    begin_scope = _manifest_subset(begin_manifest, declared.input_paths)
    current_scope = capture_spec_input_manifest(
        project_root,
        input_paths=declared.input_paths,
        normalize_provider_tasks=True,
    )
    if current_scope.fingerprint != begin_scope.fingerprint:
        blockers.append(f"aggregate_source_scope_stale:{check_id}")
        revalidation_seeds.append(check_id)
    covered: set[str] = set()
    declared_by_id = {item.check_id: item for item in owner_checks}
    for receipt in receipts:
        metadata = dict(receipt.metadata)
        covered.update(receipt.covered_obligations)
        receipt_check_id = str(metadata.get("check_id", ""))
        current_child = declared_by_id.get(receipt_check_id)
        if current_child is not None:
            covered.update(current_child.coverage_ids)
        if snapshot_policy == SPEC_SNAPSHOT_FROZEN_REQUIRED and (
            metadata.get("snapshot_policy") != SPEC_SNAPSHOT_FROZEN_REQUIRED
        ):
            blockers.append(f"child_receipt_frozen_snapshot_mismatch:{receipt.receipt_id}")
    # Child receipts cover the provider-facing obligations.  The parent's own
    # validation obligation is satisfied by the aggregation step itself and is
    # therefore not required from a child.
    required_coverage = set(declared.coverage_ids)
    uncovered = tuple(sorted(required_coverage - covered))
    if uncovered:
        blockers.extend(f"uncovered_remainder:{item}" for item in uncovered)
        revalidation_seeds.append(check_id)
    execution_id = declared.execution_id
    execution_key = fingerprint_value(
        {
            "execution_id": execution_id,
            "child_receipts": sorted((item.receipt_id, item.fingerprint) for item in receipts),
            "coverage": sorted(required_coverage),
        }
    )
    consumer_id = f"consumer:{provider_id}:{work_package_id}:{check_id}"
    if blockers:
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            declared.semantic_check_id,
            SPEC_CHECK_STATE_BLOCKED,
            SPEC_TERMINAL_BLOCKED,
            execution_key=execution_key,
            execution_id=execution_id,
            blockers=tuple(blockers),
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=begin_scope.fingerprint,
            check_post_fingerprint=begin_scope.fingerprint,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=toolchain_fingerprint,
            minimum_revalidation=tuple(dict.fromkeys((*revalidation_seeds, check_id))),
            parent_check_id=check_id,
            child_receipt_ids=resolved_ids,
            uncovered_coverage_ids=uncovered,
        )
        _record_check_result(project_root, result)
        return result
    expected_child_bindings = sorted((item.receipt_id, item.fingerprint) for item in receipts)
    for existing in reversed(
        list_evidence_receipts(project_root, output_directory=_receipt_directory(project_root))
    ):
        if existing.subject_kind != "spec_check_aggregate" or existing.result_status != RECEIPT_STATUS_PASS:
            continue
        metadata = dict(existing.metadata)
        if metadata.get("execution_key") != execution_key:
            continue
        consumed = sorted(
            (item.receipt_id, item.receipt_fingerprint)
            for item in existing.consumed_child_receipts
        )
        if consumed != expected_child_bindings:
            continue
        existing_review, _, _ = _stored_spec_receipt_review(project_root, existing.receipt_id)
        if not existing_review.ok:
            continue
        result = SpecCheckExecutionResult(
            provider_id,
            work_package_id,
            check_id,
            declared.semantic_check_id,
            SPEC_CHECK_STATE_REUSED_CURRENT,
            SPEC_TERMINAL_PASS,
            receipt_id=existing.receipt_id,
            receipt_fingerprint=existing.fingerprint,
            execution_key=execution_key,
            execution_id=execution_id,
            exit_code=existing.exit_code,
            consumer_id=consumer_id,
            session_id=str(session.get("session_id", "")),
            begin_fingerprint=begin_scope.fingerprint,
            check_post_fingerprint=begin_scope.fingerprint,
            snapshot_policy=snapshot_policy,
            toolchain_fingerprint=toolchain_fingerprint,
            parent_check_id=check_id,
            child_receipt_ids=resolved_ids,
        )
        _record_check_result(project_root, result)
        return result
    aggregate_result_value = {
        "terminal_status": SPEC_TERMINAL_PASS,
        "child_receipts": sorted((item.receipt_id, item.fingerprint) for item in receipts),
        "coverage": sorted(required_coverage),
    }
    aggregate_result_fingerprint = fingerprint_value(aggregate_result_value)
    termination_value = {"terminal_status": SPEC_TERMINAL_PASS, "exit_code": 0, "aggregated": True}
    termination_fingerprint = fingerprint_value(termination_value)
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _version("flowguard"),
        }
    )
    begin = begin_scope
    begin_manifest_path = _save_manifest(project_root, begin_scope)
    validation_ids = tuple(sorted(set(declared.validation_obligation_ids)))
    aggregate_run_id = uuid.uuid4().hex
    aggregate_result_paths = _write_output_files(
        project_root, execution_key, aggregate_run_id, b"", b""
    )
    aggregate_result_paths = _write_execution_identity_sidecars(
        project_root,
        aggregate_result_paths,
        aggregate_result_value,
        termination_value,
    )
    aggregate_receipt_id = fingerprint_value(
        {
            "kind": "spec_check_aggregate",
            "execution_id": execution_id,
            "execution_key": execution_key,
            "result_fingerprint": aggregate_result_fingerprint,
            "termination_fingerprint": termination_fingerprint,
            "run_id": aggregate_run_id,
        }
    )
    receipt = EvidenceReceipt(
        receipt_id=aggregate_receipt_id,
        subject_id=declared.semantic_check_id,
        subject_kind="spec_check_aggregate",
        producer_id="flowguard.spec_check_cache",
        producer_version=_version("flowguard"),
        claim_scope=SPEC_CHECK_CLAIM_SCOPE,
        command=("aggregate-child-receipts",),
        working_directory_token="<WORKSPACE>",
        started_at=_utc_now(),
        finished_at=_utc_now(),
        exit_code=0,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=execution_id,
        check_manifest_hash=execution_id,
        suite_map_hash=fingerprint_value({"coverage": sorted(required_coverage)}),
        input_snapshots=_manifest_with_obligations(begin_scope, validation_ids).snapshots,
        proof_artifact_id=f"spec-check-proof:{execution_key.removeprefix('sha256:')}",
        proof_artifact_fingerprint=aggregate_result_fingerprint,
        result_status=RECEIPT_STATUS_PASS,
        result_fingerprint=aggregate_result_fingerprint,
        covered_obligations=validation_ids,
        required_child_receipts=tuple(
            ChildReceiptRequirement(
                item.receipt_id,
                item.covered_obligations or tuple(str(value) for value in dict(item.metadata).get("coverage", ())),
                (SPEC_CHECK_CLAIM_SCOPE,),
                subject_id=item.subject_id,
                expected_receipt_fingerprint=item.fingerprint,
            )
            for item in receipts
        ),
        consumed_child_receipts=tuple(
            ConsumedChildReceipt(item.receipt_id, item.fingerprint) for item in receipts
        ),
        claim_boundary="Parent aggregation consumes exact child receipts and executes no covered child command.",
        metadata={
            "schema_version": SPEC_RECEIPT_SCHEMA,
            "provider_id": provider_id,
            "work_package_id": work_package_id,
            "check_id": check_id,
            "semantic_check_id": declared.semantic_check_id,
            "execution_id": execution_id,
            "execution_key": execution_key,
            "snapshot_policy": snapshot_policy,
            "snapshot_manifest_id": str(session.get("snapshot_manifest_id", begin_fingerprint)),
            "session_begin_fingerprint": begin_fingerprint,
            "input_fingerprint": begin_scope.fingerprint,
            "begin_manifest_path": begin_manifest_path,
            "toolchain_fingerprint": toolchain_fingerprint,
            "termination_fingerprint": termination_fingerprint,
            "terminal_status": SPEC_TERMINAL_PASS,
            "result_files": aggregate_result_paths,
            "run_id": aggregate_run_id,
            "child_receipt_ids": list(resolved_ids),
            "coverage": sorted(required_coverage),
            "uncovered_coverage_ids": [],
        },
    )
    save_evidence_receipt(receipt, project_root, output_directory=_receipt_directory(project_root))
    _save_portable_envelope(project_root, receipt)
    result = SpecCheckExecutionResult(
        provider_id,
        work_package_id,
        check_id,
        declared.semantic_check_id,
        SPEC_CHECK_STATE_EXECUTED,
        SPEC_TERMINAL_PASS,
        receipt_id=receipt.receipt_id,
        receipt_fingerprint=receipt.fingerprint,
        execution_key=execution_key,
        execution_id=execution_id,
        exit_code=0,
        consumer_id=consumer_id,
        session_id=str(session.get("session_id", "")),
        begin_fingerprint=begin_scope.fingerprint,
        check_post_fingerprint=begin_scope.fingerprint,
        snapshot_policy=snapshot_policy,
        toolchain_fingerprint=toolchain_fingerprint,
        parent_check_id=check_id,
        child_receipt_ids=resolved_ids,
    )
    _record_check_result(project_root, result)
    return result


def close_spec_session(root: str | Path, provider_id: str, work_package_id: str) -> SpecSessionResult:
    project_root = _project_root(root)
    session = _load_session(project_root, provider_id, work_package_id)
    begin = _load_manifest(project_root, str(session["begin_manifest_path"]))
    post = capture_spec_input_manifest(project_root, normalize_provider_tasks=True)
    post_path = _save_manifest(project_root, post)
    execution_changes = _manifest_changes(begin, post)
    raw_begin = _load_manifest(
        project_root,
        str(session.get("begin_raw_manifest_path", session["begin_manifest_path"])),
    )
    raw_post = capture_spec_input_manifest(project_root)
    changes = _manifest_changes(raw_begin, raw_post)
    package = _load_package(project_root, provider_id, work_package_id)
    owner_checks = _load_owner_checks(project_root, provider_id, work_package_id)
    review = review_spec_work_package(package)
    snapshot_policy = str(session.get("snapshot_policy", SPEC_SNAPSHOT_LIVE_SCOPED))
    begin_toolchain = SpecToolchainSnapshot.from_dict(session.get("toolchain_snapshot", {}))
    post_toolchain = capture_spec_toolchain_snapshot(package)
    check_results = session.get("check_results", {})
    excluded = {"check.session.begin", "check.session.close"}
    required_checks = {
        item.check_id
        for item in owner_checks
        if item.required
        and item.check_id not in excluded
        and item.kind != "receipt"
        and item.execution_owner_id == "flowguard.spec_check_cache"
    }
    missing = sorted(required_checks - set(check_results))
    nonpassing = sorted(
        check_id
        for check_id in required_checks & set(check_results)
        if not isinstance(check_results.get(check_id), Mapping) or not bool(check_results[check_id].get("ok", False))
    )
    minimum_revalidation = list(session.get("minimum_revalidation", ()))
    blockers: list[str] = []
    if snapshot_policy == SPEC_SNAPSHOT_FROZEN_REQUIRED and begin.fingerprint != post.fingerprint:
        blockers.append("session_inputs_changed")
        minimum_revalidation.extend(sorted(required_checks))
    if begin_toolchain.fingerprint != post_toolchain.fingerprint:
        blockers.append("session_toolchain_changed")
        minimum_revalidation.extend(sorted(required_checks))
    for check_id in sorted(required_checks & set(check_results)):
        row = check_results.get(check_id)
        if not isinstance(row, Mapping):
            continue
        declared = next(item for item in owner_checks if item.check_id == check_id)
        scoped_begin = _manifest_subset(begin, declared.input_paths)
        scoped_current = capture_spec_input_manifest(
            project_root,
            input_paths=declared.input_paths,
            normalize_provider_tasks=True,
        )
        if (
            row.get("begin_fingerprint") != scoped_begin.fingerprint
            or row.get("check_post_fingerprint") != scoped_current.fingerprint
        ):
            blockers.append(f"required_check_scope_stale:{check_id}")
            minimum_revalidation.append(check_id)
        if snapshot_policy == SPEC_SNAPSHOT_FROZEN_REQUIRED and row.get(
            "snapshot_policy"
        ) != SPEC_SNAPSHOT_FROZEN_REQUIRED:
            blockers.append(f"required_check_not_on_frozen_snapshot:{check_id}")
            minimum_revalidation.append(check_id)
        expected_check_toolchain = project_execution_toolchain_snapshot(
            post_toolchain,
            cross_change_safe=bool(declared.cross_change_safe),
        )
        if row.get("toolchain_fingerprint") != expected_check_toolchain.fingerprint:
            blockers.append(f"required_check_toolchain_stale:{check_id}")
            minimum_revalidation.append(check_id)
        if bool(row.get("ok", False)) and str(row.get("receipt_id", "")):
            receipt_review = consume_spec_receipt(
                project_root,
                receipt_id=str(row["receipt_id"]),
            )
            if not receipt_review.ok:
                blockers.append(f"required_check_receipt_stale:{check_id}")
                minimum_revalidation.extend(receipt_review.minimum_revalidation or (check_id,))
    if not review.ok:
        blockers.extend(review.finding_codes)
    blockers.extend(f"required_check_missing:{check_id}" for check_id in missing)
    blockers.extend(f"required_check_not_passed:{check_id}" for check_id in nonpassing)
    minimum_revalidation.extend(missing)
    minimum_revalidation.extend(nonpassing)
    minimum_revalidation = list(
        _dependent_check_closure(owner_checks, tuple(dict.fromkeys(minimum_revalidation)))
    )
    state = "closed" if not blockers else "blocked"
    # Provider report and task completion are produced after execution closes.
    # Archive readiness is derived only by the separate read-only post-report
    # review, preventing a close-inside-report dependency cycle.
    archive_ready = False
    session.update(
        {
            "state": state,
            "finished_at": _utc_now(),
            "post_manifest_path": post_path,
            "post_fingerprint": post.fingerprint,
            "changed_inputs": changes,
            "execution_changed_inputs": execution_changes,
            "blockers": blockers,
            "minimum_revalidation": minimum_revalidation,
            "archive_ready": archive_ready,
            "post_toolchain_snapshot": post_toolchain.to_dict(),
        }
    )
    close_record = dict(session)
    close_record_path = _evidence_token(
        project_root,
        _session_record_path(project_root, str(session["session_id"]), "close"),
    )
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
        snapshot_policy=snapshot_policy,
        toolchain_fingerprint=begin_toolchain.fingerprint,
        toolchain_snapshot=begin_toolchain.to_dict(),
        minimum_revalidation=tuple(minimum_revalidation),
        archive_ready=archive_ready,
    )


def review_spec_provider_close(
    root: str | Path,
    provider_id: str,
    work_package_id: str,
) -> SpecProviderCloseReview:
    """Reconcile a closed execution session with the later provider report, read-only."""

    project_root = _project_root(root)
    session = _load_session(project_root, provider_id, work_package_id)
    package = _load_package(project_root, provider_id, work_package_id)
    owner_checks = _load_owner_checks(project_root, provider_id, work_package_id)
    findings: list[str] = []
    minimum: list[str] = []
    if session.get("state") != "closed" or session.get("blockers"):
        findings.append("execution_session_not_closed")
    if session.get("snapshot_policy") != SPEC_SNAPSHOT_FROZEN_REQUIRED:
        findings.append("execution_session_not_frozen")
    if not package.provider_verified:
        findings.append("provider_full_report_not_current")
    if not package.provider_archive_ready:
        findings.append("provider_archive_not_ready")
    incomplete_tasks = tuple(task.task_id for task in package.tasks if not task.completed)
    if incomplete_tasks:
        findings.extend(f"provider_task_incomplete:{task_id}" for task_id in incomplete_tasks)
    required_checks = tuple(
        check.check_id
        for check in owner_checks
        if check.required
        and check.check_id not in {"check.session.begin", "check.session.close"}
        and check.kind != "receipt"
        and check.execution_owner_id == "flowguard.spec_check_cache"
    )
    check_results = session.get("check_results", {})
    for check_id in required_checks:
        row = check_results.get(check_id, {})
        if not isinstance(row, Mapping) or not bool(row.get("ok", False)):
            findings.append(f"required_check_not_passed:{check_id}")
            minimum.append(check_id)
            continue
        receipt_id = str(row.get("receipt_id", ""))
        if not receipt_id:
            findings.append(f"required_receipt_missing:{check_id}")
            minimum.append(check_id)
            continue
        receipt_review = consume_spec_receipt(project_root, receipt_id=receipt_id)
        if not receipt_review.ok:
            findings.append(f"required_receipt_not_current:{check_id}")
            minimum.extend(receipt_review.minimum_revalidation or (check_id,))
    report_rows = package.metadata.get("report_check_rows", {})
    if not isinstance(report_rows, Mapping):
        report_rows = {}
    for external_check in (
        check for check in package.checks if check.kind == "receipt" and check.external_receipt_ref
    ):
        report_row = report_rows.get(external_check.check_id, {})
        if not isinstance(report_row, Mapping):
            findings.append(f"provider_external_receipt_row_missing:{external_check.check_id}")
            continue
        expected_ref = str(external_check.external_receipt_ref.get("ref_path", ""))
        external_provider_id = str(external_check.external_receipt_ref.get("provider_id", ""))
        external_work_package_id = str(
            external_check.external_receipt_ref.get("work_package_id", "")
        )
        try:
            receipt_id, envelope = _load_portable_receipt_ref(
                project_root,
                external_provider_id,
                external_work_package_id,
                external_check.check_id,
                ref_path=expected_ref,
            )
        except (OSError, ValueError):
            findings.append(f"provider_external_receipt_ref_missing:{external_check.check_id}")
            minimum.append(external_check.check_id)
            continue
        expected_values = {
            "semantic_check_id": envelope.semantic_check_id,
            "execution_owner": f"{envelope.provider_id}:{envelope.execution_id}",
            "snapshot_policy": envelope.snapshot_policy,
            "toolchain_identity": envelope.toolchain_fingerprint,
            "source_hash_policy": dict(envelope.source_hash_policy),
            "accounting": "aggregated",
        }
        for field_name, expected in expected_values.items():
            if report_row.get(field_name) != expected:
                findings.append(
                    f"provider_external_receipt_binding_mismatch:{external_check.check_id}:{field_name}"
                )
        dependencies = report_row.get("depends_on_receipt_ids", ())
        if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)) or list(
            dependencies
        ) != [receipt_id]:
            findings.append(
                f"provider_external_receipt_binding_mismatch:{external_check.check_id}:depends_on_receipt_ids"
            )
        if set(external_check.obligation_ids) != set(envelope.coverage_ids):
            findings.append(f"provider_external_receipt_coverage_mismatch:{external_check.check_id}")
        if set(report_row.get("covers", ())) != set(external_check.obligation_ids):
            findings.append(f"provider_report_coverage_mismatch:{external_check.check_id}")
    report_failures = package.metadata.get("report_check_failures", ())
    if report_failures:
        findings.extend(f"provider_report:{value}" for value in report_failures)
    minimum = list(_dependent_check_closure(owner_checks, tuple(dict.fromkeys(minimum))))
    return SpecProviderCloseReview(
        provider_id=provider_id,
        work_package_id=work_package_id,
        session_id=str(session.get("session_id", "")),
        archive_ready=not findings,
        findings=tuple(dict.fromkeys(findings)),
        minimum_revalidation=tuple(minimum),
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
    "SPEC_PORTABLE_RECEIPT_PROTOCOL",
    "SPEC_PORTABLE_RECEIPT_SCHEMA",
    "SPEC_PORTABLE_SOURCE_MANIFEST_SCHEMA",
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
    "PortableSpecReceiptEnvelope",
    "SpecProviderCloseReview",
    "SpecReceiptConsumptionResult",
    "SpecSessionResult",
    "begin_spec_session",
    "aggregate_spec_check_receipts",
    "capture_spec_input_manifest",
    "close_spec_session",
    "consume_spec_receipt",
    "discover_governed_input_paths",
    "run_spec_check",
    "review_spec_provider_close",
    "spec_receipt_to_proof_artifact",
    "verified_spec_receipt_to_reuse_ticket",
]
