"""Validate the FlowGuard skill suite at light, affected, or full repository scope.

The default ``light`` scope checks the current 15-member
inventory/compiler/SkillGuard check.  ``full`` is the release-facing
composition: every required child keeps its own stdout, stderr, and canonical
result artifact, and the parent uses FlowGuard's shared validation-result
semantics without turning a scoped or incomplete child into success.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.skill_contracts import (
    COMPILER_VERSION,
    ContractCompileFinding,
    ContractCompileReport,
    compile_skill_suite,
    route_registry_hash,
)
from flowguard.skill_suite import (
    FLOWGUARD_SKILL_ROOT,
    FLOWGUARD_SUITE_MAP,
    FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES,
    FLOWGUARD_CONSUMER_REQUIRED_MEMBER_FILES,
    SkillSuiteFinding,
    SkillSuiteMemberReport,
    SkillSuiteReport,
    discover_skill_ids,
    validate_skill_suite,
)
from flowguard.evidence_lifecycle import (
    EvidenceLifecycleError,
    ensure_new_run_directory,
    evidence_execution_lease,
    fingerprint_payload,
    publish_run,
    store_text_object,
    verify_text_object,
    write_json_atomic,
)
from flowguard.evidence_receipts import (
    evidence_storage_root,
    load_evidence_receipt,
    verify_evidence_receipt,
)
from flowguard.process_supervision import (
    SupervisedCommandResult,
    run_supervised,
    write_terminal_artifact,
)
from flowguard.validation_owner_execution import (
    ValidationOwnerResultIdentityRequirement,
    canonical_semantic_command,
    publish_supervised_validation_owner_result,
)
from flowguard.model_regressions import (
    ModelRegressionManifest,
    audit_selected_model_source_inventories,
)
from flowguard.validation_ownership import (
    OWNER_BLOCKED,
    OWNER_EXECUTE,
    OWNER_REUSE_CURRENT,
    VALIDATION_CLAIM_SCOPE_LOCAL,
    VALIDATION_CLAIM_SCOPE_RELEASE,
    GitQueryTimeout,
    ValidationOwnerContract,
    ValidationObservationFreshness,
    assert_validation_owner_receipt_integrity,
    build_owner_current,
    build_owner_receipt_context,
    build_validation_owner_plan,
    build_validation_parent_current,
    child_from_owner_receipt,
    dependency_receipt_bindings,
    find_reusable_parent_receipt,
    find_reusable_owner_receipt,
    owner_receipt_dependency_bindings,
    observe_validation_owners,
    refresh_validation_owner_observation_receipts,
    assert_validation_owner_observation_fresh,
    assert_validation_owner_observation_receipts_fresh,
    record_validation_owner_nonpass,
    save_parent_receipt,
    verify_parent_receipt,
)
from flowguard.validation_results import (
    SkippedValidation,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_FAIL,
    VALIDATION_STATUS_INTERNAL_ERROR,
    VALIDATION_STATUS_INVALID_INPUT,
    VALIDATION_STATUS_PARTIAL,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUSES,
    ValidationChildResult,
    ValidationResult,
    aggregate_status,
)
from flowguard.completion_epoch import (
    COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
    COMPLETION_CLAIM_SCOPE_RELEASE,
    COMPLETION_DEFAULT_WORK_ID,
    COMPLETION_MAINTENANCE_UNIT_ID,
    CompletionAuthorization,
    CompletionCycleReservation,
    CompletionCycleReservationError,
    CompletionEpochAdmissionError,
    CompletionEpochPlan,
    CompletionRepairLink,
    CompletionEpochReadiness,
    CompletionEpochTerminalLedger,
    load_completion_repair_admission_group,
    abort_full_producer,
    reserve_full_producer,
    settle_full_producer,
)
from flowguard.completion_run_manifest import (
    CompletionRunManifestError,
    build_manifest,
    compare_manifest,
    invocation_projection,
    load_manifest,
)
from flowguard.completion_objective import (
    CompletionObjectiveError,
    resolve_completion_objective,
)
from flowguard.observation_metrics import InvocationMetrics


FULL_CHILD_IDS = (
    "project_audit",
    "skill_suite_light",
    "skill_native_checks",
    "skill_self_governance",
    "model_regressions_full",
    "self_maintenance_review",
    "pytest",
    "openspec_strict",
    "distribution_check",
    "distribution_parity",
)

# Distribution is a release-tree concern.  It is not a functional producer
# for a local validation claim.  Keep the release inventory explicit so the
# local plan can omit those owners entirely instead of launching placeholder
# ``python -c`` children that only print ``not_applicable``.
RELEASE_ONLY_CHILD_IDS = frozenset(
    {
        "distribution_check",
        "distribution_parity",
    }
)

# A routine local functional claim needs the real behavior owners only.  The
# author self-governance/architecture review and OpenSpec/release projections
# remain explicit qualification work; including them here made every ordinary
# model/test change wait on a second governance graph.
LOCAL_FUNCTIONAL_CHILD_IDS = frozenset(
    {
        "skill_native_checks",
        "model_regressions_full",
        "pytest",
    }
)

_NON_BROAD_STATUSES = {
    "pass_with_gaps",
    "partial",
    "scoped",
    "not_run",
    "not-run",
    "skipped",
    "missing",
    "needs-review",
    "needs_review",
    "unresolved",
}


@dataclass(frozen=True)
class CommandOutcome:
    """Captured child process outcome before canonical status projection."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    payload: Mapping[str, Any] | None = None
    launch_error: str = ""
    supervision: SupervisedCommandResult | None = None


@dataclass(frozen=True)
class ChildSpec:
    child_id: str
    command: tuple[str, ...]
    input_patterns: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    dependency_owner_ids: tuple[str, ...] = ()
    resource_keys: tuple[str, ...] = ()
    resource_options: tuple[str, ...] = ()
    external_component_bindings: tuple[tuple[str, str], ...] = ()
    external_component_paths: tuple[tuple[str, str], ...] = ()
    result_identity_requirement: ValidationOwnerResultIdentityRequirement | None = None
    timeout_seconds: float = 900.0
    required_path: Path | None = None
    missing_reason: str = ""


def _canonical_flowguard_member_ids() -> tuple[str, ...]:
    payload = json.loads((SCRIPT_ROOT / FLOWGUARD_SUITE_MAP).read_text(encoding="utf-8"))
    members = payload.get("included_skills", ())
    return tuple(
        sorted(
            str(row.get("name", "")).strip()
            for row in members
            if isinstance(row, Mapping) and str(row.get("name", "")).strip()
        )
    )


def _external_tree_fingerprint(path: Path) -> str:
    if not path.is_dir():
        return fingerprint_payload({"state": "missing", "path_kind": "directory"})
    skill_root = path / ".agents" / "skills"
    scanned_root = skill_root if skill_root.is_dir() else path
    rows = []
    for member_id in _canonical_flowguard_member_ids():
        member_root = scanned_root / member_id
        if not member_root.is_dir():
            rows.append({"member_id": member_id, "state": "missing"})
            continue
        for file_path in sorted(
            (item for item in member_root.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(scanned_root).as_posix(),
        ):
            relative = file_path.relative_to(scanned_root).as_posix()
            if (
                ".git" in file_path.parts
                or "__pycache__" in file_path.parts
                or relative.endswith(".pyc")
            ):
                continue
            rows.append(
                {
                    "path": relative,
                    "sha256": (
                        "sha256:" + hashlib.sha256(file_path.read_bytes()).hexdigest()
                    ),
                }
            )
    return fingerprint_payload(rows)


LIGHT_SUITE_INDEX_SCHEMA = "flowguard.light_suite_index.v1"
LIGHT_SUITE_OPERATION_BUDGET = 256
LIGHT_SUITE_TIME_BUDGET_SECONDS = 30.0
_LIGHT_SUITE_CACHE_RELATIVE = Path(
    ".flowguard"
) / "work" / "flowguard" / "light-suite-index.json"


class _LightSuiteBudgetExceeded(ValueError):
    """A light read exceeded its explicit bounded-cost contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _LightSuiteCost:
    operation_budget: int
    time_budget_seconds: float
    operation_count: int = 0
    started_at: float = 0.0

    def __post_init__(self) -> None:
        self.started_at = time.perf_counter()

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.perf_counter() - self.started_at)

    def check(self) -> None:
        if self.operation_budget < 0:
            raise _LightSuiteBudgetExceeded(
                "light_suite_invalid_operation_budget",
                "light operation budget must be non-negative",
            )
        if not math.isfinite(self.time_budget_seconds) or self.time_budget_seconds < 0:
            raise _LightSuiteBudgetExceeded(
                "light_suite_invalid_time_budget",
                "light time budget must be finite and non-negative",
            )
        if self.operation_count > self.operation_budget:
            raise _LightSuiteBudgetExceeded(
                "light_suite_operation_budget_exceeded",
                "light suite bounded operation budget exceeded",
            )
        if self.elapsed_seconds > self.time_budget_seconds:
            raise _LightSuiteBudgetExceeded(
                "light_suite_time_budget_exceeded",
                "light suite bounded time budget exceeded",
            )

    def step(self, amount: int = 1) -> None:
        self.operation_count += max(0, int(amount))
        self.check()


def _light_cost_metrics(
    cost: _LightSuiteCost,
    *,
    status: str,
    cache_status: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "cache_status": cache_status,
        "operation_count": cost.operation_count,
        "operation_budget": cost.operation_budget,
        "elapsed_seconds": round(cost.elapsed_seconds, 6),
        "time_budget_seconds": cost.time_budget_seconds,
        # The compact route deliberately has no recursive tree walk.  The
        # source identity helper reads the finite declared member/file list.
        "rglob_passes": 0,
    }


def _light_read_bytes(
    path: Path,
    *,
    relative: str,
    cost: _LightSuiteCost,
) -> tuple[dict[str, Any], bytes | None]:
    """Read one explicit path and return a stable identity row.

    Light identity observation is intentionally a finite list of declared
    suite-map/member files.  It never falls back to a recursive tree walk.
    """

    cost.step()
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return {"path": relative, "state": "missing"}, None
    except OSError as exc:
        return {
            "path": relative,
            "state": "unreadable",
            "error": type(exc).__name__,
        }, None
    return {
        "path": relative,
        "state": "present",
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }, data


def _light_discovered_ids(path: Path, *, cost: _LightSuiteCost) -> tuple[str, ...]:
    """Discover only immediate member directories; never recurse."""

    cost.step()
    try:
        if not path.is_dir():
            return ()
        return tuple(
            sorted(
                child.name
                for child in path.iterdir()
                if child.is_dir() and (child / "SKILL.md").is_file()
            )
        )
    except OSError:
        return ("<unreadable>",)


def _light_safe_declared_dir(root: Path, declared_path: str) -> Path | None:
    """Resolve a suite-map path without allowing cache identity escape."""

    normalized = str(declared_path or "").replace("\\", "/")
    parts = normalized.split("/")
    if not normalized or any(part in {"", ".", ".."} for part in parts):
        return None
    candidate = root / Path(*parts)
    try:
        resolved = candidate.resolve()
        root_resolved = root.resolve()
    except OSError:
        return None
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None
    return candidate


def _light_projection_rows(
    root: Path,
    *,
    member_specs: Sequence[tuple[str, str]],
    required_files: Sequence[str],
    cost: _LightSuiteCost,
    projection_root: Path | None = None,
) -> dict[str, Any]:
    """Build a bounded explicit-file projection for source or installed state."""

    base = root if projection_root is None else projection_root
    skill_root = base / FLOWGUARD_SKILL_ROOT if projection_root is None else base
    discovered = _light_discovered_ids(skill_root, cost=cost)
    rows: list[dict[str, Any]] = []
    for skill_id, declared_path in member_specs:
        if projection_root is None:
            skill_dir = _light_safe_declared_dir(root, declared_path)
        else:
            skill_dir = _light_safe_declared_dir(skill_root, skill_id)
        if skill_dir is None:
            rows.append(
                {
                    "member_id": skill_id,
                    "state": "unsafe_declared_path",
                }
            )
            continue
        for relative in required_files:
            path = skill_dir / Path(*str(relative).replace("\\", "/").split("/"))
            label = (
                f"{declared_path}/{relative}"
                if projection_root is None
                else f"{skill_id}/{relative}"
            )
            descriptor, _data = _light_read_bytes(
                path,
                relative=label,
                cost=cost,
            )
            descriptor["member_id"] = skill_id
            rows.append(descriptor)
    return {
        "root": str(base.resolve()),
        "discovered_member_ids": list(discovered),
        "files": rows,
    }


def _light_suite_identity(
    root: Path,
    *,
    installed_root: str | Path | None,
    cost: _LightSuiteCost,
) -> dict[str, Any]:
    """Compute the cache identity using only declared, bounded inputs."""

    root_path = root.resolve()
    manifest_path = root_path / FLOWGUARD_SUITE_MAP
    manifest_row, manifest_bytes = _light_read_bytes(
        manifest_path,
        relative=FLOWGUARD_SUITE_MAP,
        cost=cost,
    )
    map_data: Mapping[str, Any] = {}
    if manifest_bytes is not None:
        try:
            decoded = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {}
        if isinstance(decoded, Mapping):
            map_data = decoded

    member_specs: list[tuple[str, str]] = []
    raw_members = map_data.get("included_skills", ())
    if isinstance(raw_members, list):
        for raw in raw_members:
            if not isinstance(raw, Mapping):
                continue
            skill_id = str(raw.get("name", "")).strip()
            if not skill_id:
                continue
            declared_path = str(
                raw.get("path") or f"{FLOWGUARD_SKILL_ROOT}/{skill_id}"
            )
            member_specs.append((skill_id, declared_path))

    source_projection = _light_projection_rows(
        root_path,
        member_specs=member_specs,
        required_files=FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES,
        cost=cost,
    )

    if installed_root is None:
        installed_projection = {"state": "not_supplied"}
    else:
        supplied = Path(installed_root).expanduser().resolve()
        installed_skill_root = (
            supplied / FLOWGUARD_SKILL_ROOT
            if (supplied / FLOWGUARD_SKILL_ROOT).is_dir()
            else supplied
        )
        installed_projection = _light_projection_rows(
            root_path,
            member_specs=member_specs,
            required_files=FLOWGUARD_CONSUMER_REQUIRED_MEMBER_FILES,
            cost=cost,
            projection_root=installed_skill_root,
        )

    cost.step()
    toolchain_fingerprint = fingerprint_payload(
        {
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": sys.version,
            "compiler_version": COMPILER_VERSION,
            "route_registry_hash": route_registry_hash(),
            "implementation_files": [
                _light_read_bytes(
                    root_path / relative,
                    relative=relative,
                    cost=cost,
                )[0]
                for relative in (
                    "flowguard/skill_suite.py",
                    "flowguard/skill_contracts.py",
                    "scripts/check_flowguard_skill_suite.py",
                )
            ],
        }
    )
    manifest_fingerprint = fingerprint_payload({"manifest": manifest_row})
    installed_projection_fingerprint = fingerprint_payload(installed_projection)
    source_observation_fingerprint = fingerprint_payload(
        {
            "source_root": str(root_path),
            "manifest": manifest_row,
            "source_projection": source_projection,
            "toolchain_fingerprint": toolchain_fingerprint,
            "installed_projection_fingerprint": installed_projection_fingerprint,
        }
    )
    return {
        "schema_version": LIGHT_SUITE_INDEX_SCHEMA,
        "source_root": str(root_path),
        "declared_member_ids": [skill_id for skill_id, _path in member_specs],
        "manifest_fingerprint": manifest_fingerprint,
        "toolchain_fingerprint": toolchain_fingerprint,
        "installed_projection_fingerprint": installed_projection_fingerprint,
        "source_observation_fingerprint": source_observation_fingerprint,
    }


def _light_suite_cache_path(root: Path) -> Path | None:
    """Return the one permitted work-cache path, without creating it."""

    flowguard_root = root / ".flowguard"
    try:
        if not flowguard_root.exists() or flowguard_root.is_symlink():
            return None
        path = root / _LIGHT_SUITE_CACHE_RELATIVE
        for parent in (
            root / ".flowguard",
            root / ".flowguard" / "work",
            root / ".flowguard" / "work" / "flowguard",
            path,
        ):
            if parent.exists() and parent.is_symlink():
                return None
        if path.exists() and not path.is_file():
            return None
        if path.parent.exists() and not path.parent.is_dir():
            return None
    except OSError:
        return None
    return path


def _inventory_from_light_cache(payload: Mapping[str, Any]) -> SkillSuiteReport:
    raw_members = payload.get("members", ())
    raw_findings = payload.get("findings", ())
    if not isinstance(raw_members, list) or not isinstance(raw_findings, list):
        raise ValueError("light suite cache inventory projection is malformed")
    members = tuple(
        SkillSuiteMemberReport(
            skill_id=str(row["skill_id"]),
            role=str(row.get("role", "")),
            owner=str(row.get("owner", "")),
            declared_path=str(row.get("declared_path", "")),
            repository_role=str(row.get("repository_role", "")),
            discovered=bool(row.get("discovered", False)),
            control_root_present=bool(row.get("control_root_present", False)),
            required_files=dict(row.get("required_files", {})),
            source_hash=str(row.get("source_hash", "")),
        )
        for row in raw_members
        if isinstance(row, Mapping) and row.get("skill_id")
    )
    findings = tuple(
        SkillSuiteFinding(
            code=str(row.get("code", "")),
            message=str(row.get("message", "")),
            member_id=str(row.get("member_id", "")),
            file_path=str(row.get("file_path", "")),
            metadata=dict(row.get("metadata", {}))
            if isinstance(row.get("metadata", {}), Mapping)
            else {},
        )
        for row in raw_findings
        if isinstance(row, Mapping)
    )
    return SkillSuiteReport(
        root=str(payload.get("root", "")),
        schema_version=str(payload.get("schema_version", "")),
        suite_name=str(payload.get("suite_name", "")),
        inventory_hash=str(payload.get("inventory_hash", "")),
        semantic_hash=str(payload.get("semantic_hash", "")),
        declared_member_ids=tuple(str(item) for item in payload.get("declared_member_ids", ())),
        discovered_member_ids=tuple(str(item) for item in payload.get("discovered_member_ids", ())),
        members=members,
        findings=findings,
        co_located_skill_ids=tuple(str(item) for item in payload.get("co_located_skill_ids", ())),
    )


def _compiler_from_light_cache(payload: Mapping[str, Any]) -> ContractCompileReport:
    raw_findings = payload.get("findings", ())
    if not isinstance(raw_findings, list):
        raise ValueError("light suite cache compiler projection is malformed")
    findings = tuple(
        ContractCompileFinding(
            code=str(row.get("code", "")),
            message=str(row.get("message", "")),
            skill_id=str(row.get("skill_id", "")),
            file_path=str(row.get("file_path", "")),
        )
        for row in raw_findings
        if isinstance(row, Mapping)
    )
    hashes = payload.get("contract_hashes", {})
    return ContractCompileReport(
        root=str(payload.get("root", "")),
        mode=str(payload.get("mode", "check")),
        member_ids=tuple(str(item) for item in payload.get("member_ids", ())),
        findings=findings,
        written_files=tuple(str(item) for item in payload.get("written_files", ())),
        contract_hashes=dict(hashes) if isinstance(hashes, Mapping) else {},
        compiler_version=str(payload.get("compiler_version", "")),
        route_registry_hash=str(payload.get("route_registry_hash", "")),
    )


def _load_light_suite_cache(
    path: Path | None,
    *,
    identity: Mapping[str, Any],
    cost: _LightSuiteCost,
) -> tuple[SkillSuiteReport | None, ContractCompileReport | None, str]:
    if path is None:
        return None, None, "disabled"
    if not path.is_file():
        return None, None, "miss"
    _descriptor, data = _light_read_bytes(
        path,
        relative=_LIGHT_SUITE_CACHE_RELATIVE.as_posix(),
        cost=cost,
    )
    if data is None:
        return None, None, "miss"
    try:
        decoded = json.loads(data.decode("utf-8"))
        if not isinstance(decoded, Mapping):
            raise ValueError("cache root is not an object")
        body = {key: value for key, value in decoded.items() if key != "cache_fingerprint"}
        if decoded.get("schema_version") != LIGHT_SUITE_INDEX_SCHEMA:
            raise ValueError("cache schema is not current")
        if fingerprint_payload(body) != decoded.get("cache_fingerprint"):
            raise ValueError("cache fingerprint mismatch")
        if dict(decoded.get("identity", {})) != dict(identity):
            return None, None, "stale"
        inventory = _inventory_from_light_cache(decoded["inventory"])
        compiler = _compiler_from_light_cache(decoded["compiler"])
        if Path(inventory.root).resolve() != Path(identity["source_root"]).resolve():
            raise ValueError("cached inventory root mismatch")
        if Path(compiler.root).resolve() != Path(identity["source_root"]).resolve():
            raise ValueError("cached compiler root mismatch")
        declared_ids = tuple(str(item) for item in identity.get("declared_member_ids", ()))
        if inventory.declared_member_ids != declared_ids:
            raise ValueError("cached inventory member identity mismatch")
        if compiler.member_ids != declared_ids:
            raise ValueError("cached compiler member identity mismatch")
    except (KeyError, OSError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None, None, "invalid"
    return inventory, compiler, "hit"


def _write_light_suite_cache(
    path: Path | None,
    *,
    identity: Mapping[str, Any],
    inventory: SkillSuiteReport,
    compiler: ContractCompileReport,
    cost: _LightSuiteCost,
) -> tuple[bool, str]:
    if path is None:
        return False, "disabled"
    cost.step()
    body = {
        "schema_version": LIGHT_SUITE_INDEX_SCHEMA,
        "identity": dict(identity),
        "inventory": inventory.to_dict(),
        "compiler": compiler.to_dict(),
    }
    payload = dict(body)
    payload["cache_fingerprint"] = fingerprint_payload(body)
    try:
        write_json_atomic(path, payload)
    except OSError as exc:
        return False, f"write_failed:{type(exc).__name__}"
    return True, "written"


def _light_budget_blocked_payload(
    *,
    selected: Sequence[str],
    reason: str,
    code: str,
    identity: Mapping[str, Any],
    cache_path: Path | None,
    cache_status: str,
    cost: _LightSuiteCost,
) -> dict[str, Any]:
    blockers = [f"{code}:{reason}"]
    metrics = _light_cost_metrics(cost, status="blocked", cache_status="blocked")
    return {
        "artifact_type": "flowguard_skill_suite_certification",
        "ok": False,
        "status": "blocked",
        "requested_members": list(selected),
        "passed_members": 0,
        "total_members": len(selected),
        "inventory_hash": "",
        "semantic_hash": "",
        "compiler_version": COMPILER_VERSION,
        "inventory": {},
        "compiler": {},
        "members": [],
        "blockers": blockers,
        "checks_run": [],
        "checks_not_run": ["light_currentness"],
        "skipped_checks": [],
        "author_subprocess_count": 0,
        "native_producer_count": 0,
        "input_manifest_lookup_count": 0,
        "receipt_lookup_count": 0,
        "light_suite_index": {
            "schema_version": LIGHT_SUITE_INDEX_SCHEMA,
            "cache_status": cache_status,
            "cache_path": str(cache_path) if cache_path else "",
            **dict(identity),
            "cost": metrics,
        },
        "cost_metrics": metrics,
        "claim_boundary": (
            "Light currentness was blocked by its explicit bounded-cost contract; "
            "no producer, lease, run directory, or authority write was started."
        ),
    }


def _model_regression_input_patterns(root: Path) -> tuple[str, ...]:
    """Use the manifest's exact owned inputs instead of scanning runtime stores."""

    manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
    patterns = {
        ".flowguard/models/regression-manifest.json",
        "flowguard/model_regressions.py",
        "scripts/run_flowguard_model_regressions.py",
    }
    if not manifest_path.is_file():
        return tuple(sorted(patterns))
    manifest = ModelRegressionManifest.load(root)
    for entry in manifest.entries:
        if not entry.excluded:
            patterns.update(entry.effective_input_patterns)
    for group in manifest.shared_input_groups:
        patterns.update(group.globs)
    return tuple(sorted(patterns))


def _skillguard_cli(value: str) -> Path:
    if value != "all":
        return Path(value).expanduser().resolve()
    return Path.home() / ".codex" / "skills" / "skillguard" / "scripts" / "skillguard.py"


def _run_json_command(command: list[str], cwd: Path) -> dict[str, Any]:
    """Run one light/affected child and expose its terminal JSON material."""

    outcome = _execute_command(tuple(command), cwd)
    return {
        "command": list(outcome.command),
        "exit_code": outcome.exit_code,
        "stdout": outcome.stdout,
        "stderr": outcome.stderr,
        "payload": dict(outcome.payload) if outcome.payload is not None else None,
    }


def _execute_command(
    command: Sequence[str],
    cwd: Path,
    timeout_seconds: float = 900.0,
    environment: Mapping[str, str] | None = None,
) -> CommandOutcome:
    """Run one child without a shell and retain all terminal material."""

    normalized = tuple(str(item) for item in command)
    try:
        child_environment = dict(os.environ)
        # Validation children must not create bytecode beneath the current
        # .flowguard role tree while they are inspecting it.  Such generated
        # caches are not governed inputs and would otherwise invalidate the
        # frozen layout between planning and final reconciliation.
        child_environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if environment:
            child_environment.update({str(key): str(value) for key, value in environment.items()})
        completed = run_supervised(
            normalized,
            cwd=cwd,
            environment=child_environment,
            timeout_seconds=timeout_seconds,
        )
    except (OSError, ValueError) as exc:
        return CommandOutcome(normalized, 2, stderr=str(exc), launch_error=f"{type(exc).__name__}: {exc}")
    if not completed.cleanup_confirmed:
        return CommandOutcome(
            normalized,
            70,
            stdout=completed.stdout,
            stderr=completed.stderr,
            launch_error="cleanup_unconfirmed",
            supervision=completed,
        )
    payload: Mapping[str, Any] | None = None
    if completed.stdout.strip():
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, Mapping):
            payload = dict(decoded)
    return CommandOutcome(
        normalized,
        completed.exit_code if completed.exit_code is not None else 70,
        completed.stdout,
        completed.stderr,
        payload,
        supervision=completed,
    )


def _v2_contract_projection(
    skill_id: str,
    compiler: Any,
    depth_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one shared V2 parity proof without recompiling the target twice."""

    depth_payload = depth_result.get("payload") if isinstance(depth_result, Mapping) else None
    payload = dict(depth_payload) if isinstance(depth_payload, Mapping) else {}
    expected_hash = str(getattr(compiler, "contract_hashes", {}).get(skill_id, ""))
    actual_hash = str(payload.get("contract_hash") or "")
    authority = str(payload.get("authority_decision") or "")
    ok = bool(
        getattr(compiler, "ok", False)
        and expected_hash
        and actual_hash == expected_hash
        and depth_result.get("exit_code") == 0
        and payload.get("decision") == "pass"
        and authority == "current"
    )
    return {
        "command": [
            "flowguard.compile_skill_suite",
            "+",
            "skillguard check-depth",
        ],
        "exit_code": 0 if ok else 1,
        "stdout": "",
        "stderr": "",
        "execution_mode": "shared-v2-parity",
        "payload": {
            "decision": "pass" if ok else "fail",
            "authority_decision": authority,
            "contract_hash": actual_hash,
            "expected_contract_hash": expected_hash,
            "manifest_hash": str(payload.get("manifest_hash") or ""),
            "claim_boundary": (
                "This projection reuses the current-only FlowGuard parity reader and SkillGuard depth proof; "
                "it does not claim target execution depth."
            ),
        },
    }


def run_light_suite(
    root: Path,
    *,
    skillguard: str = "all",
    members: Sequence[str] = (),
    installed_root: str | Path | None = None,
    operation_budget: int = LIGHT_SUITE_OPERATION_BUDGET,
    time_budget_seconds: float = LIGHT_SUITE_TIME_BUDGET_SECONDS,
    allow_cache_write: bool = False,
) -> dict[str, Any]:
    """Read the compact currentness surface without starting a producer.

    The historical implementation called SkillGuard once or twice per member
    from this public light entry.  That made an ordinary map/currentness read
    behave like author qualification.  Light now consumes the in-process
    inventory/compiler projection only; the author checks live in
    :func:`run_author_skill_assurance` and are invoked by their own full-suite
    owner.
    """

    del skillguard  # retained in the public signature for caller compatibility
    root_path = Path(root).resolve()
    selected_hint = tuple(str(item) for item in members)
    cost = _LightSuiteCost(
        operation_budget=int(operation_budget),
        time_budget_seconds=float(time_budget_seconds),
    )
    cache_path = _light_suite_cache_path(root_path)
    identity: dict[str, Any] = {}
    cache_status = "disabled" if cache_path is None else "miss"
    try:
        cost.check()
        identity = _light_suite_identity(
            root_path,
            installed_root=installed_root,
            cost=cost,
        )
        inventory, compiler, cache_status = _load_light_suite_cache(
            cache_path,
            identity=identity,
            cost=cost,
        )
        if inventory is None or compiler is None:
            cost.step()
            # Private-inventory discovery intentionally belongs to the
            # author-assurance/full owner.  Light validates the canonical map
            # and its finite required-file projection without repeating the
            # recursive source scan on every read.
            inventory = validate_skill_suite(
                root_path,
                check_private_inventories=False,
            )
            cost.step()
            compiler = compile_skill_suite(
                root_path,
                write=False,
                inventory=inventory,
            )
            if allow_cache_write:
                cache_written, cache_write_status = _write_light_suite_cache(
                    cache_path,
                    identity=identity,
                    inventory=inventory,
                    compiler=compiler,
                    cost=cost,
                )
                if cache_written:
                    cache_status = "miss_written"
                elif cache_write_status not in {"disabled"}:
                    cache_status = cache_write_status
            else:
                cache_status = "miss_not_written" if cache_path is not None else "disabled"
        cost.check()
    except _LightSuiteBudgetExceeded as exc:
        return _light_budget_blocked_payload(
            selected=selected_hint,
            reason=str(exc),
            code=exc.code,
            identity=identity,
            cache_path=cache_path,
            cache_status=cache_status,
            cost=cost,
        )
    selected = tuple(members) if members else inventory.declared_member_ids
    inventory_members = {
        member.skill_id: member
        for member in getattr(inventory, "members", ())
    }
    compiler_findings_all = tuple(getattr(compiler, "findings", ()))
    compiler_findings = {
        skill_id: tuple(
            finding
            for finding in compiler_findings_all
            if finding.skill_id in {"", skill_id}
        )
        for skill_id in selected
    }
    member_rows: list[dict[str, Any]] = []
    for skill_id in selected:
        member = inventory_members.get(skill_id)
        light_ok = bool(member is not None and member.ok)
        contract_ok = bool(
            skill_id in compiler.contract_hashes
            and not compiler_findings.get(skill_id)
        )
        member_rows.append(
            {
                "skill_id": skill_id,
                "ok": light_ok and contract_ok,
                "light_ok": light_ok,
                "contract_ok": contract_ok,
                "depth_ok": False,
                "depth_classification": "not_run",
                "author_assurance_status": "not_run",
                "results": {},
            }
        )

    blockers: list[str] = []
    if not inventory.ok:
        blockers.extend(
            f"inventory:{finding.code}:{finding.member_id or finding.file_path}"
            for finding in inventory.findings
        )
    if not compiler.ok:
        blockers.extend(
            f"contract:{finding.code}:{finding.skill_id or finding.file_path}"
            for finding in compiler_findings_all
        )
    if len(member_rows) != len(selected):
        blockers.append("light_member_projection_incomplete")
    ok = not blockers and all(row["ok"] for row in member_rows)
    return {
        "artifact_type": "flowguard_skill_suite_certification",
        "ok": ok,
        "status": "pass" if ok else "blocked",
        "inventory_hash": inventory.inventory_hash,
        "semantic_hash": inventory.semantic_hash,
        "compiler_version": compiler.compiler_version,
        "route_registry_hash": compiler.route_registry_hash,
        "requested_members": list(selected),
        "passed_members": sum(bool(row["ok"]) for row in member_rows),
        "total_members": len(selected),
        "inventory": inventory.to_dict(),
        "compiler": compiler.to_dict(),
        "members": member_rows,
        "blockers": blockers,
        "checks_run": ["layout_shape", "adoption_pointer", "contract_parity"],
        "checks_not_run": [
            "author_check_skill",
            "author_check_depth",
            "author_check_contract",
            "native_owner",
            "model_regression",
            "pytest",
            "release_parity",
        ],
        "skipped_checks": [
            "author SkillGuard checks are not part of light currentness"
        ],
        "author_subprocess_count": 0,
        "native_producer_count": 0,
        "input_manifest_lookup_count": len(selected),
        "receipt_lookup_count": 0,
        "light_suite_index": {
            "schema_version": LIGHT_SUITE_INDEX_SCHEMA,
            "cache_status": cache_status,
            "cache_path": str(cache_path) if cache_path else "",
            **identity,
            "cost": _light_cost_metrics(
                cost,
                status="pass" if ok else "blocked",
                cache_status=cache_status,
            ),
        },
        "cost_metrics": _light_cost_metrics(
            cost,
            status="pass" if ok else "blocked",
            cache_status=cache_status,
        ),
        "residual_risk": [
            "Light proves only current suite shape and compiled contract identity; it does not execute SkillGuard, native owners, model regressions, tests, or release parity."
        ],
        "claim_boundary": (
            "Pass certifies compact currentness and source/compiled contract identity for the selected members only; "
            "author qualification, native receipts, parent self-governance, and release evidence remain not_run."
        ),
    }


def run_author_skill_assurance(
    root: Path,
    *,
    skillguard: str = "all",
    members: Sequence[str] = (),
) -> dict[str, Any]:
    """Run the existing 15-member author qualification checks.

    This is intentionally not a fourth public execution profile.  It is the
    target-owned author-assurance producer consumed by the existing full child
    owner.  Keeping it separate lets routine ``light`` reads remain zero
    producer while preserving the exact SkillGuard check/depth semantics for
    qualification.
    """

    inventory = validate_skill_suite(root)
    compiler = compile_skill_suite(root, write=False)
    selected = tuple(members) if members else inventory.declared_member_ids
    cli = _skillguard_cli(skillguard)
    member_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    author_subprocess_count = 0
    if not cli.is_file():
        blockers.append(f"SkillGuard CLI is missing: {cli}")
    else:
        for skill_id in selected:
            target = root / FLOWGUARD_SKILL_ROOT / skill_id
            source_path = target / ".skillguard" / "contract-source.json"
            try:
                source_payload = json.loads(source_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                source_payload = {}
            is_v2 = source_payload.get("schema_version") == "skillguard.contract_source.v2"
            commands = {
                "light": [
                    sys.executable,
                    str(cli),
                    "check-skill",
                    "--target",
                    str(target),
                    "--repository-root",
                    str(root),
                    "--output",
                    "-",
                ],
                "depth": [
                    sys.executable,
                    str(cli),
                    "check-depth",
                    "--target",
                    str(target),
                    "--target-root",
                    str(root),
                    "--output",
                    "-",
                ],
            }
            if not is_v2:
                commands["contract"] = [
                    sys.executable,
                    str(cli),
                    "check-contract",
                    "--target",
                    str(target),
                    "--target-root",
                    str(root),
                    "--output",
                    "-",
                ]
            author_subprocess_count += len(commands)
            results = {name: _run_json_command(command, root) for name, command in commands.items()}
            light_ok = results["light"]["exit_code"] == 0 and (results["light"]["payload"] or {}).get("decision") == "pass"
            depth_payload = results["depth"]["payload"] or {}
            if is_v2:
                results["contract"] = _v2_contract_projection(skill_id, compiler, results["depth"])
            contract_ok = results["contract"]["exit_code"] == 0 and (results["contract"]["payload"] or {}).get("decision") == "pass"
            expected_depth_classes = (
                {"declared-contract-current"}
                if source_payload.get("schema_version") == "skillguard.contract_source.v2"
                else {"deep-pass"}
            )
            depth_ok = (
                results["depth"]["exit_code"] == 0
                and depth_payload.get("depth_classification") in expected_depth_classes
            )
            member_rows.append(
                {
                    "skill_id": skill_id,
                    "ok": light_ok and contract_ok and depth_ok,
                    "light_ok": light_ok,
                    "contract_ok": contract_ok,
                    "depth_ok": depth_ok,
                    "depth_classification": depth_payload.get("depth_classification", "unavailable"),
                    "expected_depth_classifications": sorted(expected_depth_classes),
                    "author_assurance_status": "pass" if light_ok and contract_ok and depth_ok else "blocked",
                    "results": results,
                }
            )

    ok = inventory.ok and compiler.ok and not blockers and len(member_rows) == len(selected) and all(
        row["ok"] for row in member_rows
    )
    return {
        "artifact_type": "flowguard_skill_suite_certification",
        "ok": ok,
        "status": "pass" if ok else "blocked",
        "scope": "author_assurance",
        "inventory_hash": inventory.inventory_hash,
        "semantic_hash": inventory.semantic_hash,
        "compiler_version": compiler.compiler_version,
        "route_registry_hash": compiler.route_registry_hash,
        "requested_members": list(selected),
        "passed_members": sum(bool(row["ok"]) for row in member_rows),
        "total_members": len(selected),
        "inventory": inventory.to_dict(),
        "compiler": compiler.to_dict(),
        "members": member_rows,
        "blockers": blockers,
        "checks_run": ["author_check_skill", "author_check_depth", "author_check_contract"],
        "checks_not_run": ["native_owner", "model_regression", "pytest", "release_parity"],
        "skipped_checks": [] if cli.is_file() else ["SkillGuard author checks"],
        "author_subprocess_count": author_subprocess_count,
        "native_producer_count": 0,
        "input_manifest_lookup_count": len(selected),
        "receipt_lookup_count": 0,
        "residual_risk": [
            "Author assurance certifies the current 15-member SkillGuard checks only; native receipts, parent self-governance, model, test, and release gates remain separate."
        ],
        "claim_boundary": (
            "Pass certifies the current author-side SkillGuard check/depth/contract surface for the selected members; "
            "it is not a light currentness result or whole-system release proof."
        ),
    }


def _affected_blocked_payload(
    *,
    reason: str,
    impact_plan: Any | None = None,
) -> dict[str, Any]:
    """Return a terminal affected result without starting a producer."""

    return {
        "artifact_type": "flowguard_skill_suite_certification",
        "ok": False,
        "status": "blocked",
        "scope": "affected",
        "requested_members": list(getattr(impact_plan, "affected_member_ids", ())),
        "passed_members": 0,
        "total_members": len(getattr(impact_plan, "affected_member_ids", ())),
        "inventory": {},
        "compiler": {},
        "inventory_hash": "",
        "semantic_hash": "",
        "compiler_version": "",
        "members": [],
        "blockers": [reason],
        "skipped_checks": [],
        "residual_risk": [
            "No affected owner producer started because the machine impact plan was not executable."
        ],
        "claim_boundary": (
            "Affected scope proves only an exact machine impact plan and its selected "
            "owners; it never falls back to light or full validation."
        ),
        "impact_plan": impact_plan.to_dict() if impact_plan is not None else None,
    }


def _affected_native_runner(root: Path, owner_id: str) -> tuple[Path | None, str]:
    """Resolve one explicitly owned native model/test runner.

    An affected plan is a selector, not permission to invoke the light suite.
    The only executable authority is the checked-in owner runner under
    ``.flowguard/verification/owners`` (or the explicit hyphenated satellite
    spelling mapped to its underscore route).  We never search the repository
    or choose a similarly named script: an absent/ambiguous route is a
    terminal blocker with zero producer work.
    """

    owner = str(owner_id).strip()
    if not owner or owner != owner_id:
        return None, "owner id is empty or not normalized"
    if any(token in owner for token in ("/", "\\", "..")):
        return None, "owner id is not a safe native route identifier"
    route_names = [owner]
    if owner.startswith("model:"):
        route_names.append(owner.removeprefix("model:"))
    if owner.startswith("flowguard-"):
        route_names.append(owner.removeprefix("flowguard-").replace("-", "_"))
    candidates: list[Path] = []
    owners_root = (root / ".flowguard" / "verification" / "owners").resolve()
    for route_name in dict.fromkeys(route_names):
        candidate = (owners_root / route_name / "run_checks.py").resolve()
        try:
            candidate.relative_to(owners_root)
        except ValueError:
            return None, f"{owner}: native runner escapes owner root"
        if candidate.is_file() and not candidate.is_symlink():
            candidates.append(candidate)
    if len(candidates) != 1:
        if not candidates:
            return None, f"{owner}: native owner runner is missing"
        return None, f"{owner}: native owner runner is ambiguous"
    return candidates[0], ""


def _verify_affected_native_result_artifact(
    owner_work: Path,
    owner_id: str,
) -> tuple[bool, tuple[Any, ...], tuple[str, ...]]:
    """Validate one producer-owned native case envelope.

    A successful process exit or a human-readable ``result.json`` is not
    behavior evidence.  Affected execution therefore requires the same
    minimum boundary as model-regression execution: a current envelope,
    non-empty typed rows, complete dimension/oracle projections, and raw
    artifacts whose bytes match their declared fingerprints and stay inside
    the retained owner workspace.
    """

    from flowguard.native_case_protocol import (
        NativeCaseProtocolError,
        load_native_model_case_results,
    )

    artifact = owner_work / "native-case-results.json"
    if artifact.is_symlink() or not artifact.is_file():
        return False, (), ("native_case_result_artifact_missing",)
    findings: list[str] = []
    try:
        rows = load_native_model_case_results(artifact)
    except (OSError, UnicodeError, ValueError, NativeCaseProtocolError) as exc:
        return False, (), (
            f"native_case_result_artifact_invalid:{type(exc).__name__}",
        )
    if not rows:
        findings.append("native_case_result_rows_empty")
    seen: set[tuple[str, str]] = set()
    root_resolved = owner_work.resolve()
    for row in rows:
        identity = (row.owner_id, row.source_case_id)
        if identity in seen:
            findings.append(f"native_case_result_duplicate:{row.source_case_id}")
        seen.add(identity)
        if row.owner_id != owner_id:
            findings.append(f"native_case_result_owner_mismatch:{row.source_case_id}")
        if row.outcome == "not_run":
            findings.append(f"native_case_result_not_run:{row.source_case_id}")
        dimensions = set(row.executed_dimensions)
        oracle_dimensions = {
            str(item.get("dimension", "")).strip()
            for item in row.oracle_results
            if isinstance(item, Mapping)
        }
        if not dimensions or dimensions != oracle_dimensions:
            findings.append(
                f"native_case_result_dimensions_unverified:{row.source_case_id}"
            )
        if any(
            not isinstance(item, Mapping)
            or not isinstance(item.get("oracle_member_id"), str)
            or not str(item.get("oracle_member_id")).strip()
            for item in row.oracle_results
        ):
            findings.append(
                f"native_case_result_oracle_unverified:{row.source_case_id}"
            )
        raw = Path(row.raw_artifact_path).expanduser()
        if not raw.is_absolute():
            raw = artifact.parent / raw
        try:
            raw_resolved = raw.resolve()
            if (
                raw.is_symlink()
                or raw_resolved == root_resolved
                or root_resolved not in raw_resolved.parents
                or not raw_resolved.is_file()
            ):
                findings.append(
                    f"native_case_result_raw_artifact_missing:{row.source_case_id}"
                )
            else:
                digest = "sha256:" + hashlib.sha256(
                    raw_resolved.read_bytes()
                ).hexdigest()
                if digest != row.result_artifact_fingerprint:
                    findings.append(
                        "native_case_result_raw_artifact_fingerprint_mismatch:"
                        + row.source_case_id
                    )
        except (OSError, ValueError):
            findings.append(
                f"native_case_result_raw_artifact_invalid:{row.source_case_id}"
            )
    return not findings, rows, tuple(dict.fromkeys(findings))


def _run_affected_native_owner(
    root: Path,
    owner_id: str,
    *,
    work_root: Path,
    selected_owner_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Run one current native owner in an isolated, retained work directory."""

    runner, blocker = _affected_native_runner(root, owner_id)
    if runner is None:
        return {
            "skill_id": owner_id,
            "status": VALIDATION_STATUS_BLOCKED,
            "ok": False,
            "native_ok": False,
            "execution_disposition": OWNER_BLOCKED,
            "native_status": "blocked",
            "structural_status": "not_run",
            "interaction_status": "not_run",
            "blockers": [blocker],
            "results": {},
        }
    work_root_path = Path(work_root).expanduser()
    try:
        work_root_resolved = work_root_path.resolve()
        expected_work_root = (
            (root / "work" / "flowguard" / "runtime-closure-20260904" / "affected-native")
            .resolve()
        )
        work_root_resolved.relative_to(expected_work_root)
    except (OSError, ValueError):
        return {
            "skill_id": owner_id,
            "status": VALIDATION_STATUS_BLOCKED,
            "ok": False,
            "native_ok": False,
            "execution_disposition": OWNER_BLOCKED,
            "native_status": "blocked",
            "structural_status": "not_run",
            "interaction_status": "not_run",
            "blockers": ["affected native work root is outside the controlled task workspace"],
            "results": {},
        }
    if work_root_path.is_symlink() or work_root_resolved.is_symlink():
        return {
            "skill_id": owner_id,
            "status": VALIDATION_STATUS_BLOCKED,
            "ok": False,
            "native_ok": False,
            "execution_disposition": OWNER_BLOCKED,
            "native_status": "blocked",
            "structural_status": "not_run",
            "interaction_status": "not_run",
            "blockers": ["affected native work root is a symlink/reparse point"],
            "results": {},
        }
    work_root_path.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in owner_id)
    owner_work = Path(
        tempfile.mkdtemp(
            prefix=f"{safe}-{hashlib.sha256(owner_id.encode('utf-8')).hexdigest()[:10]}-",
            dir=str(work_root_resolved),
        )
    ).resolve()
    environment = dict(os.environ)
    existing_pythonpath = environment.get("PYTHONPATH", "")
    pythonpath = str(root)
    if existing_pythonpath:
        pythonpath += os.pathsep + existing_pythonpath
    environment.update(
        {
            "FLOWGUARD_OUTPUT_DIR": str(owner_work),
            "FLOWGUARD_OWNER_ID": owner_id,
            "FLOWGUARD_AFFECTED_OWNER_ID": owner_id,
            # Nested owner launchers use this explicit plan projection to
            # return a reuse-required row instead of starting a child that is
            # already selected by the same affected execution.  An empty
            # projection preserves standalone runner behavior.
            "FLOWGUARD_SELECTED_OWNER_IDS": ",".join(
                sorted(
                    {
                        str(item).strip()
                        for item in selected_owner_ids
                        if str(item).strip()
                    }
                )
            ),
            "PYTHONPATH": pythonpath,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPYCACHEPREFIX": environment.get(
                "PYTHONPYCACHEPREFIX",
                str(root / "work" / "pycache" / "flowguard-affected-runs"),
            ),
        }
    )
    command = (sys.executable, "-B", str(runner))
    supervised: SupervisedCommandResult | None = None
    launch_error = ""
    try:
        supervised = run_supervised(
            command,
            cwd=root,
            environment=environment,
            timeout_seconds=900.0,
        )
    except (OSError, ValueError) as exc:
        launch_error = f"{type(exc).__name__}: {exc}"

    payload: Mapping[str, Any] | None = None
    result_path = owner_work / "result.json"
    if result_path.is_file() and not result_path.is_symlink():
        try:
            decoded = json.loads(result_path.read_text(encoding="utf-8"))
            if isinstance(decoded, Mapping):
                payload = dict(decoded)
            else:
                launch_error = "native owner result.json is not an object"
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            launch_error = f"native owner result.json is invalid: {type(exc).__name__}"
    if supervised is None:
        return {
            "skill_id": owner_id,
            "status": VALIDATION_STATUS_BLOCKED,
            "ok": False,
            "native_ok": False,
            "execution_disposition": OWNER_EXECUTE,
            "native_status": "blocked",
            "structural_status": "not_run",
            "interaction_status": "not_run",
            "blockers": [launch_error or "native owner did not start"],
            "results": {
                "native": {
                    "command": command,
                    "exit_code": 2,
                    "stdout": "",
                    "stderr": launch_error,
                    "payload": {},
                    "launch_error": launch_error,
                    "artifact_path": str(result_path),
                }
            },
        }
    outcome = CommandOutcome(
        command=command,
        exit_code=int(supervised.exit_code),
        stdout=supervised.stdout,
        stderr=supervised.stderr,
        payload=payload,
        launch_error=launch_error,
        supervision=supervised,
    )
    status = _status_from_outcome(outcome)
    if not supervised.cleanup_confirmed:
        status = VALIDATION_STATUS_BLOCKED
        launch_error = "native owner process-tree cleanup could not be confirmed"
    if launch_error:
        status = VALIDATION_STATUS_BLOCKED
    native_ok = status == VALIDATION_STATUS_PASS
    blockers = []
    if launch_error:
        blockers.append(launch_error)
    native_artifact_ok, native_rows, native_findings = (
        _verify_affected_native_result_artifact(owner_work, owner_id)
    )
    if not native_artifact_ok:
        native_ok = False
        status = VALIDATION_STATUS_BLOCKED
        blockers.extend(native_findings)
    if payload is None:
        # Human-readable output remains useful diagnosis, but it cannot stand
        # in for the strict producer-owned native case envelope.
        payload = {
            "status": status,
            "ok": native_ok,
            "native_result_artifact": (
                str(owner_work / "native-case-results.json")
                if native_artifact_ok
                else "not_provided"
            ),
        }
    return {
        "skill_id": owner_id,
        "status": status,
        "ok": native_ok,
        "native_ok": native_ok,
        "execution_disposition": OWNER_EXECUTE,
        "native_status": "pass" if native_ok else status,
        "structural_status": "not_run",
        "interaction_status": "not_run",
        "blockers": blockers,
        "results": {
            "native": {
                "command": command,
                "exit_code": int(supervised.exit_code),
                "stdout": supervised.stdout,
                "stderr": supervised.stderr,
                "payload": payload,
                "launch_error": launch_error,
                "artifact_path": str(result_path) if result_path.is_file() else "",
                "native_case_result_artifact": str(
                    owner_work / "native-case-results.json"
                ),
                "native_case_result_count": len(native_rows),
                "native_case_findings": list(native_findings),
                "cleanup_confirmed": bool(supervised.cleanup_confirmed),
                "terminal_reason": str(supervised.terminal_reason),
            }
        },
        "native_work_dir": str(owner_work),
    }


def _verified_affected_reuse_row(
    root: Path,
    owner_row: Any,
) -> tuple[dict[str, Any] | None, str]:
    """Project one affected reuse row from its canonical immutable receipt.

    ``AffectedImpactPlan`` is a selector and is intentionally not a receipt
    store.  Keep the runner fail-closed as well as the plan builder: a plan
    loaded from disk must not turn an arbitrary id/hash pair into a synthetic
    passing member row.  The owner current itself is built while the plan is
    created; this second check validates the immutable receipt bytes, subject,
    proof, terminal status, and the identity frozen in that plan row.
    """

    owner_id = str(getattr(owner_row, "owner_id", "")).strip()
    receipt_id = str(getattr(owner_row, "receipt_id", "")).strip()
    receipt_fingerprint = str(getattr(owner_row, "receipt_fingerprint", "")).strip()
    if (
        not owner_id
        or not receipt_id
        or not receipt_fingerprint
        or any(character in receipt_id for character in ("/", "\\"))
        or Path(receipt_id).is_absolute()
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", receipt_fingerprint)
    ):
        return None, f"{owner_id or '<empty>'}: receipt identity is malformed"

    receipt_root = (root / ".flowguard" / "evidence" / "validation-owners").resolve()
    try:
        receipt = load_evidence_receipt(
            receipt_id,
            root,
            output_directory=receipt_root,
        )
    except (OSError, TypeError, ValueError) as exc:
        return None, f"{owner_id}: canonical receipt is unavailable ({type(exc).__name__})"
    if receipt.fingerprint != receipt_fingerprint:
        return None, f"{owner_id}: canonical receipt fingerprint mismatch"
    if receipt.subject_id != f"validation-owner:{owner_id}":
        return None, f"{owner_id}: canonical receipt subject mismatch"
    try:
        assert_validation_owner_receipt_integrity(receipt)
    except (TypeError, ValueError) as exc:
        return None, f"{owner_id}: canonical receipt integrity failed ({exc})"

    expected_owner_identity = str(getattr(owner_row, "owner_identity", "")).strip()
    actual_owner_identity = str(receipt.metadata.get("owner_identity", "")).strip()
    if not expected_owner_identity or actual_owner_identity != expected_owner_identity:
        return None, f"{owner_id}: canonical receipt owner identity is stale"
    if (
        receipt.result_status != VALIDATION_STATUS_PASS
        or receipt.exit_code != 0
        or receipt.skipped_checks
        or receipt.blockers
        or not receipt.covered_obligations
    ):
        return None, f"{owner_id}: canonical receipt is not a complete passing coverage receipt"

    proof_relpath = str(receipt.metadata.get("proof_relpath", "")).strip()
    proof_path = (receipt_root / proof_relpath).resolve() if proof_relpath else None
    if (
        proof_path is None
        or receipt_root not in proof_path.parents
        or not proof_path.is_file()
    ):
        return None, f"{owner_id}: canonical receipt proof is missing or escapes the store"
    proof_fingerprint = "sha256:" + hashlib.sha256(proof_path.read_bytes()).hexdigest()
    if (
        proof_fingerprint != receipt.proof_artifact_fingerprint
        or proof_fingerprint != receipt.result_fingerprint
    ):
        return None, f"{owner_id}: canonical receipt proof fingerprint mismatch"
    try:
        child = child_from_owner_receipt(receipt, receipt_root)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, f"{owner_id}: canonical receipt proof is invalid ({type(exc).__name__})"
    if child.status != VALIDATION_STATUS_PASS or child.receipt_id != receipt.receipt_id:
        return None, f"{owner_id}: canonical receipt proof is not a passing owner result"
    return (
        {
            "skill_id": owner_id,
            "ok": True,
            "light_ok": True,
            "contract_ok": True,
            "depth_ok": True,
            "depth_classification": "reused-current",
            "expected_depth_classifications": ["reused-current"],
            "execution_disposition": OWNER_REUSE_CURRENT,
            "results": {
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
                "proof_artifact_fingerprint": proof_fingerprint,
                "covered_obligations": list(receipt.covered_obligations),
                "claim_boundary": receipt.claim_boundary,
                "child": {
                    "child_id": child.child_id,
                    "status": child.status,
                    "summary": child.summary,
                    "payload": dict(child.payload),
                },
            },
        },
        "",
    )


def run_affected_suite(
    root: Path,
    *,
    impact_plan: Any,
    skillguard: str = "all",
    members: Sequence[str] = (),
) -> dict[str, Any]:
    """Execute exactly the owners named by one current affected plan."""

    from flowguard.affected_blueprint_reader import AffectedImpactPlan
    from flowguard.validation_ownership import validate_affected_impact_plan

    if not isinstance(impact_plan, AffectedImpactPlan):
        raise ValueError("affected scope requires a current AffectedImpactPlan")
    try:
        plan = validate_affected_impact_plan(
            impact_plan,
            selected_member_ids=tuple(members or ()),
        )
    except (TypeError, ValueError) as exc:
        return _affected_blocked_payload(reason=str(exc), impact_plan=impact_plan)

    # Affected plans may target a skill satellite or a manifest-owned model
    # owner.  Both sets are canonical declarations; do not discover arbitrary
    # directories at execution time.
    declared_ids = set(_canonical_flowguard_member_ids())
    try:
        from flowguard.model_regressions import ModelRegressionManifest

        # Model-regression contracts use the typed ``model:<id>`` owner
        # identity, while the manifest itself names the route as ``<id>``.
        # An affected plan is allowed to carry either spelling, but the
        # native runner and its result envelope must retain the typed form.
        # Register both spellings at the admission boundary instead of
        # rejecting a valid model owner before its exact native runner can
        # execute.
        for entry in ModelRegressionManifest.load(root).entries:
            if entry.excluded:
                continue
            model_id = str(entry.model_id)
            declared_ids.add(model_id)
            declared_ids.add(f"model:{model_id}")
    except (OSError, TypeError, ValueError):
        # A skill-only project need not carry a model manifest.  The exact
        # affected plan remains executable for its declared skill owners.
        pass
    declared = tuple(sorted(declared_ids))
    unknown_members = sorted(set(plan.affected_member_ids) - set(declared))
    if unknown_members:
        return _affected_blocked_payload(
            reason="affected impact plan names unknown skill owners: " + ", ".join(unknown_members),
            impact_plan=plan,
        )
    owner_rows = {row.owner_id: row for row in plan.owner_rows}
    execute_ids = tuple(
        owner_id
        for owner_id in plan.affected_member_ids
        if owner_rows[owner_id].disposition == OWNER_EXECUTE
    )
    reuse_ids = tuple(
        owner_id
        for owner_id in plan.affected_member_ids
        if owner_rows[owner_id].disposition == OWNER_REUSE_CURRENT
    )
    if any(row.disposition == OWNER_BLOCKED for row in plan.owner_rows):
        return _affected_blocked_payload(
            reason="affected impact plan contains a blocked owner disposition",
            impact_plan=plan,
        )

    reused_rows: list[dict[str, Any]] = []
    reuse_blockers: list[str] = []
    for owner_id in reuse_ids:
        reused_row, blocker = _verified_affected_reuse_row(
            root,
            owner_rows[owner_id],
        )
        if reused_row is None:
            reuse_blockers.append(blocker)
        else:
            reused_rows.append(reused_row)
    if reuse_blockers:
        blocked = _affected_blocked_payload(
            reason="affected reuse receipt verification failed",
            impact_plan=plan,
        )
        blocked["blockers"].extend(reuse_blockers)
        return blocked

    executed_rows: list[dict[str, Any]] = []
    native_blockers: list[str] = []
    if execute_ids:
        native_work_root = (
            root
            / "work"
            / "flowguard"
            / "runtime-closure-20260904"
            / "affected-native"
        ).resolve()
        native_work_root.mkdir(parents=True, exist_ok=True)
        for owner_id in execute_ids:
            row = _run_affected_native_owner(
                root,
                owner_id,
                work_root=native_work_root,
                selected_owner_ids=execute_ids,
            )
            executed_rows.append(row)
            native_blockers.extend(str(item) for item in row.get("blockers", ()))
    executed_payload = {
        "inventory_hash": plan.source_fingerprint,
        "semantic_hash": plan.model_fingerprint,
        "compiler_version": plan.test_fingerprint,
        "inventory": {
            "source_fingerprint": plan.source_fingerprint,
            "changed_components": [
                {"component_id": component_id, "fingerprint": fingerprint}
                for component_id, fingerprint in plan.changed_components
            ],
        },
        "compiler": {
            "owner_fingerprint": plan.owner_fingerprint,
            "native_execution": True,
        },
        "blockers": native_blockers,
        "skipped_checks": [],
        "residual_risk": [
            "Affected native execution does not prove unaffected owners, installation, release, or whole-system closure.",
        ],
        "members": executed_rows,
        "ok": all(bool(row.get("ok")) for row in executed_rows),
        "status": "pass" if all(bool(row.get("ok")) for row in executed_rows) else "blocked",
        "native_execution": {
            "executed_owner_ids": list(execute_ids),
            "reused_owner_ids": list(reuse_ids),
            "structural_owner_ids": [],
            "interaction_owner_ids": [],
        },
    }
    member_rows = sorted(
        [*executed_rows, *reused_rows],
        key=lambda row: str(row.get("skill_id", "")),
    )
    all_ok = bool(executed_payload.get("ok", True)) and len(member_rows) == len(plan.affected_member_ids) and all(
        bool(row.get("ok")) for row in member_rows
    )
    return {
        "artifact_type": "flowguard_skill_suite_certification",
        "ok": all_ok,
        "status": "pass" if all_ok else "blocked",
        "scope": "affected",
        "requested_members": list(plan.affected_member_ids),
        "passed_members": sum(bool(row.get("ok")) for row in member_rows),
        "total_members": len(plan.affected_member_ids),
        "inventory_hash": executed_payload.get("inventory_hash", ""),
        "semantic_hash": executed_payload.get("semantic_hash", ""),
        "compiler_version": executed_payload.get("compiler_version", ""),
        "route_registry_hash": executed_payload.get("route_registry_hash", ""),
        "inventory": executed_payload.get("inventory", {}),
        "compiler": executed_payload.get("compiler", {}),
        "members": member_rows,
        "blockers": list(executed_payload.get("blockers", ())),
        "skipped_checks": list(executed_payload.get("skipped_checks", ())),
        "residual_risk": [
            "Affected scope does not prove unaffected owners, installation, release, or whole-system closure."
        ],
        "claim_boundary": (
            "This result proves only the exact current affected impact plan and its "
            "terminal owner rows; it cannot support a full or release claim."
        ),
        "impact_plan": plan.to_dict(),
        "native_execution": executed_payload.get("native_execution", {
            "executed_owner_ids": list(execute_ids),
            "reused_owner_ids": list(reuse_ids),
            "structural_owner_ids": [],
            "interaction_owner_ids": [],
        }),
        "affected_owner_dispositions": {
            owner_id: owner_rows[owner_id].disposition
            for owner_id in plan.affected_member_ids
        },
    }


def _write_light_result(
    payload: Mapping[str, Any],
    output_dir: str | None,
    *,
    authority_kind: str = "standalone",
    parent_scope: str = "",
) -> tuple[str, str, str]:
    if output_dir:
        run_dir = Path(output_dir).expanduser().resolve()
    else:
        run_dir = Path(
            tempfile.mkdtemp(prefix="flowguard-skill-suite-light-")
        ).resolve()
    ensure_new_run_directory(run_dir)
    compact_payload = _compact_light_payload(payload, run_dir)
    result_path = run_dir / "result.json"
    result_path.write_text(
        json.dumps(compact_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    publish_run(
        run_dir,
        kind="skill-suite-light",
        status=str(compact_payload.get("status", "blocked")),
        result_path=result_path,
        authority_kind=authority_kind,
        parent_scope=parent_scope,
    )
    result_sha256 = "sha256:" + hashlib.sha256(result_path.read_bytes()).hexdigest()
    return run_dir.name, str(result_path), result_sha256


def _content_addressed_detail(
    run_dir: Path,
    payload: Mapping[str, Any],
    *,
    prefix: str,
) -> str:
    """Write one compact detail object and verify its content address."""

    encoded = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    path = run_dir / "details" / f"{prefix}-{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise EvidenceLifecycleError(f"light detail content collision: {path}")
    else:
        # Use bytes so the content address is stable on Windows; text writes
        # may translate LF to CRLF and invalidate the digest we just derived.
        path.write_bytes(encoded.encode("utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise EvidenceLifecycleError(f"light detail fingerprint mismatch: {path}")
    return path.relative_to(run_dir).as_posix()


def _compact_light_payload(payload: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Project a light/affected result without duplicating parsed streams.

    Complete stdout/stderr are retained only as content-addressed compressed
    objects.  Decision rows carry fingerprints and one detail reference; the
    full parsed command payload is kept in the detail object, outside the
    terminal/result parent projection.
    """

    stream_descriptors: dict[str, dict[str, Any]] = {}

    def stream_ref(text_value: Any, *, media_type: str) -> dict[str, Any]:
        text_value = str(text_value or "")
        logical_sha = "sha256:" + hashlib.sha256(text_value.encode("utf-8")).hexdigest()
        descriptor = stream_descriptors.get(logical_sha)
        if descriptor is None:
            descriptor = store_text_object(
                run_dir,
                text_value,
                media_type=media_type,
                tail_chars=0,
            )
            stream_descriptors[logical_sha] = descriptor
        if not verify_text_object(run_dir, descriptor):
            raise EvidenceLifecycleError(
                "light content-addressed stream is missing or hash-mismatched"
            )
        return {
            "logical_sha256": descriptor["logical_sha256"],
            "storage_sha256": descriptor["storage_sha256"],
            "object_path": descriptor["object_path"],
            "logical_bytes": descriptor["logical_bytes"],
            "storage_bytes": descriptor["storage_bytes"],
        }

    compact_members: list[dict[str, Any]] = []
    for row in payload.get("members", ()):
        if not isinstance(row, Mapping):
            raise EvidenceLifecycleError("light member row is not an object")
        details: list[dict[str, Any]] = []
        for name, result in sorted((row.get("results") or {}).items()):
            if not isinstance(result, Mapping):
                raise EvidenceLifecycleError(f"light result row is not an object: {name}")
            command = tuple(str(item) for item in result.get("command", ()))
            result_payload = result.get("payload")
            detail = {
                "name": str(name),
                "exit_code": int(result.get("exit_code", 2)),
                "command_fingerprint": fingerprint_payload({"command": list(command)}),
                "payload_fingerprint": fingerprint_payload(
                    result_payload if isinstance(result_payload, Mapping) else {}
                ),
                "stdout": stream_ref(
                    result.get("stdout", ""),
                    media_type=(
                        "application/json; charset=utf-8"
                        if isinstance(result_payload, Mapping)
                        else "text/plain; charset=utf-8"
                    ),
                ),
                "stderr": stream_ref(
                    result.get("stderr", ""),
                    media_type="text/plain; charset=utf-8",
                ),
                "payload_keys": sorted(result_payload) if isinstance(result_payload, Mapping) else [],
            }
            details.append(detail)
        detail_ref = _content_addressed_detail(
            run_dir,
            {"skill_id": str(row.get("skill_id", "")), "results": details},
            prefix="member",
        )
        all_command_fingerprints = tuple(item["command_fingerprint"] for item in details)
        all_payload_fingerprints = tuple(item["payload_fingerprint"] for item in details)
        compact_members.append(
            {
                "skill_id": str(row.get("skill_id", "")),
                "status": "pass" if bool(row.get("ok")) else "blocked",
                "native_status": str(row.get("native_status", "not_run")),
                "native_ok": bool(row.get("native_ok", False)),
                "structural_status": str(row.get("structural_status", "not_run")),
                "interaction_status": str(row.get("interaction_status", "not_run")),
                "light_status": "pass" if bool(row.get("light_ok")) else "blocked",
                "contract_status": "pass" if bool(row.get("contract_ok")) else "blocked",
                "depth_status": "pass" if bool(row.get("depth_ok")) else "blocked",
                "depth_classification": str(row.get("depth_classification", "unavailable")),
                "command_fingerprint": fingerprint_payload({"commands": list(all_command_fingerprints)}),
                "payload_fingerprint": fingerprint_payload({"payloads": list(all_payload_fingerprints)}),
                "artifact_ref": detail_ref,
                "native_work_dir": str(row.get("native_work_dir", "")),
            }
        )

    inventory_value = payload.get("inventory")
    compiler_value = payload.get("compiler")
    inventory_detail_ref = _content_addressed_detail(
        run_dir,
        inventory_value if isinstance(inventory_value, Mapping) else {},
        prefix="inventory",
    )
    compiler_detail_ref = _content_addressed_detail(
        run_dir,
        compiler_value if isinstance(compiler_value, Mapping) else {},
        prefix="compiler",
    )
    inventory_status = "pass" if bool(payload.get("inventory_hash")) else "blocked"
    compiler_status = "pass" if bool(payload.get("compiler_version")) else "blocked"
    compact = {
        "artifact_type": payload.get("artifact_type", "flowguard_skill_suite_certification"),
        "schema_version": "flowguard.skill_suite_light_result.v2",
        "ok": bool(payload.get("ok")),
        "status": str(payload.get("status", "blocked")),
        "scope": str(payload.get("scope", "light")),
        "requested_members": list(payload.get("requested_members", ())),
        "passed_members": int(payload.get("passed_members", 0)),
        "total_members": int(payload.get("total_members", 0)),
        "inventory": {
            "count": int(payload.get("total_members", 0)),
            "status": inventory_status,
            "fingerprint": str(payload.get("inventory_hash", "")),
            "detail_ref": inventory_detail_ref,
        },
        "compiler": {
            "count": int(payload.get("total_members", 0)),
            "status": compiler_status,
            "fingerprint": str(payload.get("semantic_hash", "")),
            "detail_ref": compiler_detail_ref,
        },
        "members": compact_members,
        "blockers": list(payload.get("blockers", ())),
        "skipped_checks": list(payload.get("skipped_checks", ())),
        "residual_risk": list(payload.get("residual_risk", ())),
        "claim_boundary": str(payload.get("claim_boundary", "")),
    }
    # Preserve explicit profile/mode fields when an entry supplied them, but
    # never synthesize one from a parsed child payload.
    for field_name in (
        "execution_profile",
        "modeling_mode",
        "selection_reason",
        "closed_obligations",
        "not_run_obligations",
        "escalation_triggers",
        "execution_profile_decision",
        "execution_profile_claim_boundary",
        "execution_profile_admitted",
        "execution_profile_status",
        "execution_profile_ok",
    ):
        if field_name in payload:
            compact[field_name] = payload[field_name]
    # Verify every detail reference before returning the parent projection.
    for ref in [inventory_detail_ref, compiler_detail_ref, *(row["artifact_ref"] for row in compact_members)]:
        detail_path = run_dir / ref
        if not detail_path.is_file() or hashlib.sha256(detail_path.read_bytes()).hexdigest() != Path(ref).stem.rsplit("-", 1)[-1]:
            raise EvidenceLifecycleError(f"light detail reference is missing or hash-mismatched: {ref}")
    return compact


def _print_light(
    payload: Mapping[str, Any],
    *,
    as_json: bool,
    run_id: str = "",
    result_path: str = "",
    result_sha256: str = "",
) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "schema_version": "flowguard.validation_terminal.v1",
                    "command": "check-flowguard-skill-suite",
                    "scope": str(payload.get("scope") or "light"),
                    "status": payload.get("status", "blocked"),
                    "ok": bool(payload.get("ok")),
                    "counts": {
                        "passed": int(payload.get("passed_members", 0)),
                        "total": int(payload.get("total_members", 0)),
                    },
                    "run_id": run_id,
                    "result_path": result_path,
                    "result_sha256": result_sha256,
                    "failed_member_ids": [
                        str(row.get("skill_id"))
                        for row in payload.get("members", ())
                        if not row.get("ok")
                    ],
                    "blockers": list(payload.get("blockers", ())),
                    "skipped_checks": list(
                        payload.get("skipped_checks", ())
                    ),
                    "claim_boundary": payload.get("claim_boundary", ""),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    print("status: pass" if payload.get("ok") else "status: blocked")
    print(f"members: {payload.get('passed_members', 0)}/{payload.get('total_members', 0)}")
    for blocker in payload.get("blockers", ()):
        print(f"blocker: {blocker}")
    for row in payload.get("members", ()):
        if not row.get("ok"):
            print(
                f"finding: {row.get('skill_id')}: profile={payload.get('scope', 'light')} "
                f"light={row.get('light_ok')} "
                f"contract={row.get('contract_ok')} depth={row.get('depth_classification')}"
            )


def _full_child_specs(args: argparse.Namespace, root: Path) -> tuple[ChildSpec, ...]:
    from flowguard.execution_profiles import ValidationExecutionPolicy

    resource_policy = ValidationExecutionPolicy.from_project(root)
    native_owner_timeout = resource_policy.owner_timeout("skill_native_checks")
    model_owner_timeout = resource_policy.owner_timeout("model_regressions_full")
    self_maintenance_timeout = resource_policy.owner_timeout(
        "self_maintenance_review"
    )
    pytest_owner_timeout = resource_policy.owner_timeout("pytest")
    claim_scope = str(
        getattr(args, "claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE)
    ).strip().lower()
    formal = Path(args.formal_root).expanduser().resolve() if args.formal_root else root
    shadow = Path(args.shadow_root).expanduser().resolve() if args.shadow_root else None
    installed = (
        Path(args.installed_root).expanduser().resolve()
        if args.installed_root
        else Path.home() / ".codex" / "skills"
    )
    self_script = root / "scripts" / "check_flowguard_self_governance.py"
    author_assurance_script = root / "scripts" / "check_flowguard_author_skill_assurance.py"
    native_script = root / "scripts" / "run_flowguard_skill_native_checks.py"
    model_script = root / "scripts" / "run_flowguard_model_regressions.py"
    pytest_shard_script = root / "scripts" / "run_flowguard_pytest_shards.py"
    distribution_script = root / "scripts" / "install_flowguard_skills.py"
    native_receipt_root = evidence_storage_root(root)
    # Model owner receipts are a persistent, independently addressed evidence
    # store.  They must not move with the retained outer run-artifact
    # directory: doing so makes every new full invocation observe an empty
    # model store and re-run all model producers.  The explicit option lets
    # readiness and full validation share a caller-selected store; the default
    # matches the model-regression and self-blueprint standalone defaults.
    model_receipt_root = (
        Path(args.model_receipt_dir).expanduser().resolve()
        if getattr(args, "model_receipt_dir", None)
        else root / ".flowguard" / "evidence" / "model-owner-receipts"
    )

    self_blueprint_command = [
        sys.executable,
        "-m",
        "flowguard",
        "flowguard-self-blueprint-check",
        "--root",
        str(root),
        "--include-architecture-reduction",
        "--compact",
        "--json",
    ]
    if getattr(args, "require_executed_evidence", False):
        self_blueprint_command.append("--require-executed-evidence")
    self_blueprint_command.extend(("--model-receipt-dir", str(model_receipt_root)))

    child_output_root = (
        Path(args.output_dir).expanduser().resolve()
        if getattr(args, "output_dir", None)
        else root / ".flowguard" / "evidence" / "validation-child-artifacts"
    )

    author_assurance_command = [
        sys.executable,
        str(author_assurance_script),
        "--root",
        str(root),
        "--skillguard",
        args.skillguard,
        "--output-dir",
        str(child_output_root / "light-suite"),
        "--authority-kind",
        "child",
        "--parent-scope",
        "full-validation",
        "--json",
    ]
    model_command = [
        sys.executable,
        str(model_script),
        "--root",
        str(root),
        "--tier",
        "full",
        "--jobs",
        str(args.model_jobs),
        "--output-dir",
        # Keep the model producer's terminal run in its own child scope.  If
        # the producer publishes CURRENT.json directly beside the outer full
        # validation result, the later parent publication would have to
        # replace a child head with a parent head and the whole closure would
        # fail after all model work had completed.  The extra ``run`` level
        # gives the child its own scope while retaining all artifacts under
        # the single bounded validation output tree.
        str(Path(args.output_dir).expanduser().resolve() / "model-regressions" / "run")
        if args.output_dir
        else str(root / ".flowguard" / "evidence" / "model-regressions" / "run"),
        "--receipt-dir",
        str(model_receipt_root),
        "--json",
        "--authority-kind",
        "child",
        "--parent-scope",
        "full-validation",
    ]
    if args.model_timeout is not None:
        model_command.extend(("--timeout", str(args.model_timeout)))
    if getattr(args, "model_parent_receipt", None):
        model_command.extend(("--model-parent-receipt", str(args.model_parent_receipt)))
    if getattr(args, "require_executed_evidence", False):
        model_command.append("--require-executed-evidence")

    if claim_scope == VALIDATION_CLAIM_SCOPE_LOCAL:
        # Local functional validation deliberately does not make a release
        # claim.  Keep the required child identity terminal and receipt-bound,
        # but use a deterministic N/A producer that performs no tree scan and
        # consumes no formal/shadow/installed roots.  Release scope below still
        # requires the complete three-tree parity command.
        parity_command = [
            sys.executable,
            "-c",
            (
                "import json; print(json.dumps({"
                "'status':'pass',"
                "'parity_status':'not_applicable',"
                "'claim_boundary':'Local validation omits release-tree parity; "
                "no formal, shadow, or installed distribution claim was made.',"
                "'producer_invocations':0"
                "}, sort_keys=True))"
            ),
        ]
        parity_required_path = Path(sys.executable)
        parity_external_component_paths: tuple[tuple[str, str], ...] = ()
        parity_missing_reason = (
            "local validation intentionally omits formal/shadow/installed parity"
        )
    else:
        parity_command = [
            sys.executable,
            str(distribution_script),
            "parity",
            "--source",
            str(root),
            "--formal",
            str(formal),
            "--installed",
            str(installed),
            "--json",
        ]
        if shadow is not None:
            parity_command.extend(("--shadow", str(shadow)))
        parity_required_path = distribution_script if shadow is not None else None
        parity_external_component_paths = tuple(
            (component_id, str(component_root))
            for component_id, component_root in (
                ("formal-consumer-tree", formal),
                ("installed-consumer-tree", installed),
                *((
                    ("shadow-consumer-tree", shadow),
                ) if shadow is not None else ()),
            )
        )
        parity_missing_reason = (
            "--shadow-root is required to prove formal/shadow/installed complete-tree parity"
        )

    if claim_scope == VALIDATION_CLAIM_SCOPE_LOCAL:
        # A local functional validation deliberately has no consumer-tree
        # claim.  Do not point the distribution checker at the author source
        # as both source and target: that is an invalid projection and makes
        # every local completion stop on the distribution check before the
        # actual model/test closure is considered.  Keep the required owner
        # terminal and explicit, but make its non-applicable boundary a
        # zero-producer result just like local distribution parity.
        distribution_command = [
            sys.executable,
            "-c",
            (
                "import json; print(json.dumps({"
                "'status':'pass',"
                "'distribution_status':'not_applicable',"
                "'claim_boundary':'Local validation omits consumer-tree distribution; "
                "source and target projection were not launched.',"
                "'producer_invocations':0"
                "}, sort_keys=True))"
            ),
        ]
        distribution_external_component_paths: tuple[tuple[str, str], ...] = ()
        distribution_required_path = Path(sys.executable)
        distribution_missing_reason = (
            "local validation intentionally omits consumer-tree distribution"
        )
    else:
        distribution_command = [
            sys.executable,
            str(distribution_script),
            "check",
            "--source",
            str(formal),
            "--target",
            str(installed),
            "--json",
        ]
        distribution_external_component_paths = (
            ("installed-consumer-tree", str(installed)),
        )
        distribution_required_path = distribution_script
        distribution_missing_reason = "distribution checker is required for full closure"

    pytest_resume_output = str(
        getattr(args, "pytest_resume_output", "") or ""
    ).strip()

    specs = (
        ChildSpec(
            "project_audit",
            (sys.executable, "-m", "flowguard", "project-audit", "--root", str(root), "--json"),
            (
                "AGENTS.md",
                ".flowguard/project.toml",
                ".agents/skills/**/*",
                "flowguard/project_adoption.py",
                "flowguard/skill_suite.py",
            ),
            ("validation:project_audit",),
        ),
        ChildSpec(
            "skill_suite_light",
            tuple(author_assurance_command),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/skill_contracts.py",
                "flowguard/skill_suite.py",
                "flowguard/self_maintenance.py",
                "scripts/check_flowguard_skill_suite.py",
                "scripts/check_flowguard_author_skill_assurance.py",
            ),
            ("validation:skill_suite_light",),
        ),
        ChildSpec(
            "skill_native_checks",
            (
                sys.executable,
                str(native_script),
                "--root",
                str(root),
                "--output-dir",
                str(native_receipt_root),
                "--resume",
                "--json",
            ),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/evidence_receipts.py",
                "flowguard/process_supervision.py",
                "flowguard/skill_native_checks.py",
                "scripts/run_flowguard_skill_native_checks.py",
            ),
            ("validation:skill_native_checks",),
            resource_keys=("resource:validation-native-receipts",),
            required_path=native_script,
            # The fifteen target-owned native checks execute serially.  A
            # single check may use the full native timeout, so the supervisor
            # must not terminate the batch at the per-check default boundary.
            timeout_seconds=native_owner_timeout,
            missing_reason=(
                "skill-native check producer is required before "
                "self-governance can consume current child receipts"
            ),
        ),
        ChildSpec(
            "skill_self_governance",
            (
                sys.executable,
                str(self_script),
                "--root",
                str(root),
                "--output-directory",
                str(native_receipt_root),
                "--json",
            ),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/evidence_receipts.py",
                "flowguard/skill_native_checks.py",
                "flowguard/skill_self_governance.py",
                "scripts/check_flowguard_self_governance.py",
            ),
            ("validation:skill_self_governance",),
            dependency_owner_ids=("skill_native_checks",),
            resource_keys=("resource:validation-native-receipts",),
            required_path=self_script,
            missing_reason="self-governance checker is required for full closure",
        ),
        ChildSpec(
            "model_regressions_full",
            tuple(model_command),
            _model_regression_input_patterns(root),
            ("validation:model_regressions_full",),
            required_path=model_script,
            missing_reason="manifest model-regression runner is required for full closure",
            # A child model run may need to rebuild its exact-current source
            # inventory before it can consume the persistent 49-model receipt
            # set and execute only the affected owners.  The outer default
            # (900 s) was shorter than that bounded preflight on a busy
            # Windows checkout, so it converted a slow-but-live owner into a
            # false timeout.  Keep the owner finite, but give it the same
            # one-hour ceiling as the full model parent.
            timeout_seconds=model_owner_timeout,
            resource_options=("--timeout",),
        ),
        ChildSpec(
            "self_maintenance_review",
            tuple(self_blueprint_command),
            (
                "AGENTS.md",
                "CHANGELOG.md",
                "LICENSE",
                "README.md",
                "ROADMAP.md",
                ".agents/**/*",
                ".flowguard/models/owners/**/*.py",
                ".flowguard/verification/owners/**/*.py",
                ".flowguard/models/owners/authoritative_model_system/**/*",
                ".flowguard/models/regression-manifest.json",
                ".flowguard/project.toml",
                ".github/**/*",
                ".skillguard/**/*",
                "assets/**/*",
                "docs/**/*",
                "examples/**/*",
                "flowguard/**/*",
                "openspec/**/*",
                "pyproject.toml",
                "scripts/**/*",
                "tests/**/*",
            ),
            (
                "validation:self_blueprint",
                "validation:architecture_reduction_review",
            ),
            result_identity_requirement=ValidationOwnerResultIdentityRequirement(
                projection_id=(
                    "flowguard.self_maintenance_review."
                    "architecture_reduction_identity"
                ),
                source_path=("architecture_reduction_review",),
                fingerprint_fields=(
                    "review_fingerprint",
                    "projection_fingerprint",
                ),
                content_fingerprint_field="projection_fingerprint",
            ),
            dependency_owner_ids=("model_regressions_full",),
            timeout_seconds=self_maintenance_timeout,
        ),
        ChildSpec(
            "pytest",
            (
                sys.executable,
                str(pytest_shard_script),
                "--root",
                str(root),
                "--shards",
                "4",
                "--collect-timeout",
                str(resource_policy.collection_timeout_seconds),
                "--shard-timeout",
                str(resource_policy.pytest_shard_timeout_seconds),
                "--run-timeout",
                str(pytest_owner_timeout),
                "--parallel-shards",
                "4",
                "--json",
                *(
                    ("--resume-output", pytest_resume_output)
                    if pytest_resume_output
                    else ()
                ),
            ),
            (
                "flowguard/**/*.py",
                "scripts/**/*.py",
                "tests/**/*.py",
                ".flowguard/models/regression-manifest.json",
                "pyproject.toml",
            ),
            ("validation:pytest",),
            timeout_seconds=pytest_owner_timeout,
            resource_options=(
                "--collect-timeout",
                "--shard-timeout",
                "--run-timeout",
            ),
        ),
        ChildSpec(
            "openspec_strict",
            (shutil.which("openspec") or "openspec", "validate", "--all", "--strict"),
            (
                "openspec/**/*.md",
                "openspec/**/*.yaml",
                "openspec/**/*.yml",
                "openspec/**/*.json",
            ),
            ("validation:openspec_strict",),
        ),
        ChildSpec(
            "distribution_check",
            tuple(distribution_command),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/consumer-suite-authority.json",
                "flowguard/distribution_sync.py",
                "flowguard/skill_suite.py",
                "scripts/install_flowguard_skills.py",
            ),
            ("validation:distribution_check",),
            external_component_paths=distribution_external_component_paths,
            required_path=distribution_required_path,
            missing_reason=distribution_missing_reason,
        ),
        ChildSpec(
            "distribution_parity",
            tuple(parity_command),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/consumer-suite-authority.json",
                "flowguard/distribution_sync.py",
                "flowguard/skill_suite.py",
                "scripts/install_flowguard_skills.py",
            ),
            ("validation:distribution_parity",),
            external_component_paths=parity_external_component_paths,
            required_path=parity_required_path,
            missing_reason=parity_missing_reason,
        ),
    )
    if claim_scope == VALIDATION_CLAIM_SCOPE_LOCAL:
        # Local validation closes functional model/test/process obligations.
        # Author assurance, self-governance, OpenSpec, and release-tree
        # projections are separate qualification claims. They must not appear
        # as zero-producer placeholder owners in the local owner DAG or
        # completion budget.
        return tuple(
            spec for spec in specs if spec.child_id in LOCAL_FUNCTIONAL_CHILD_IDS
        )
    return specs


def _required_child_ids(specs: Sequence[ChildSpec]) -> tuple[str, ...]:
    """Return the exact terminal owner set for one frozen child plan."""

    result = tuple(spec.child_id for spec in specs)
    if len(result) != len(set(result)):
        raise ValueError("full validation child owners must be unique")
    return result


def _completion_epoch_plan(
    *,
    args: argparse.Namespace,
    root: Path,
    specs: Sequence[ChildSpec],
    owner_plan: Any,
    parent_current: Any,
    planning_observation: Any,
) -> CompletionEpochPlan:
    """Build the one frozen completion identity for a full invocation."""

    test_inventory = [
        {
            "child_id": spec.child_id,
            "command": list(canonical_semantic_command(spec.command)),
            "obligation_ids": list(spec.obligation_ids),
            "input_patterns": list(spec.input_patterns),
        }
        for spec in specs
    ]
    remaining = tuple(
        str(item).strip()
        for item in getattr(args, "remaining_governed_write_ids", ())
        if str(item).strip()
    )
    objective_fingerprint = ""
    objective_change = str(
        getattr(args, "completion_objective_change", "") or ""
    ).strip()
    if objective_change:
        objective_fingerprint = resolve_completion_objective(
            root,
            objective_change,
        ).fingerprint
    authorization = None
    authorization_path = str(
        getattr(args, "completion_authorization", "") or ""
    ).strip()
    if authorization_path:
        candidate_path = Path(authorization_path).expanduser().resolve()
        if root not in candidate_path.parents and candidate_path != root:
            raise ValueError(
                "--completion-authorization must remain inside the repository root"
            )
        authorization = CompletionAuthorization.load(candidate_path)
        blockers = authorization.validate_for(
            maintenance_unit_id=getattr(args, "maintenance_unit_id", None),
            completion_work_id=getattr(args, "completion_work_id", None),
            claim_scope=getattr(args, "claim_scope", None),
        )
        if blockers:
            raise ValueError(
                "completion authorization is not bound to this work: "
                + ",".join(blockers)
            )
    return CompletionEpochPlan.freeze(
        # The full observation fingerprint includes the receipt inventory and
        # owner dispositions.  Those remain inputs to reuse/stale checks, but
        # receipts created by this producer must not reopen the semantic
        # completion epoch.  Freeze the source-only projection instead.
        source_observation_fingerprint=planning_observation.source_observation_fingerprint,
        release_tree_fingerprint=owner_plan.release_tree_manifest_fingerprint,
        toolchain_environment_fingerprint=parent_current.environment_fingerprint,
        owner_dag_fingerprint=owner_plan.plan_fingerprint,
        model_authority_fingerprint=fingerprint_payload(
            {"parent_identity": parent_current.parent_identity}
        ),
        completion_objective_fingerprint=objective_fingerprint,
        test_inventory_fingerprint=fingerprint_payload({"children": test_inventory}),
        required_terminal_action_ids=_required_child_ids(specs),
        remaining_governed_write_ids=remaining,
        maintenance_unit_id=getattr(args, "maintenance_unit_id", None),
        completion_work_id=getattr(args, "completion_work_id", None),
        claim_scope=getattr(args, "claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE),
        completion_authorization_fingerprint=(
            authorization.fingerprint if authorization is not None else ""
        ),
        completion_cycle_max_attempts=(
            authorization.max_full_attempts
            if authorization is not None
            else 2
        ),
    )


def _completion_epoch_admission(
    plan: CompletionEpochPlan,
    args: argparse.Namespace,
    *,
    readiness: CompletionEpochReadiness | None = None,
    readiness_error: str = "",
) -> Any:
    """Project one positive completion-readiness receipt into the epoch gate.

    The final gate intentionally does not infer readiness from omitted flags.
    A caller must supply a current, terminal ``CompletionEpochReadiness``
    object whose identities match this frozen plan.  Negative switches remain
    diagnostic inputs for the command surface, but cannot make an absent
    receipt current.
    """

    admission = plan.admit(readiness=readiness)
    diagnostic_blockers: list[str] = []
    if bool(getattr(args, "openspec_unarchived", False)):
        diagnostic_blockers.append("openspec_not_archived")
    if bool(getattr(args, "external_roots_unsynced", False)):
        diagnostic_blockers.append("external_roots_not_synchronized")
    if bool(getattr(args, "reverse_input_unaccepted", False)):
        diagnostic_blockers.append("reverse_input_not_accepted")
    if bool(getattr(args, "owner_dag_not_frozen", False)):
        diagnostic_blockers.append("owner_dag_not_frozen")
    if readiness_error:
        diagnostic_blockers.append(str(readiness_error))
    if diagnostic_blockers:
        # Preserve the typed admission result while making a malformed or
        # unreadable readiness artifact distinguishable from a missing one.
        blockers = tuple(
            dict.fromkeys((*diagnostic_blockers, *admission.blockers))
        )
        admission = replace(
            admission,
            status="blocked",
            blockers=blockers,
        )
    return admission


def _load_completion_readiness(
    args: argparse.Namespace,
    plan: CompletionEpochPlan,
) -> tuple[CompletionEpochReadiness | None, str]:
    """Load a caller-supplied readiness receipt without executing producers.

    ``run_full_validation`` is also used directly by focused tests and by
    orchestration callers.  Those callers may pass a typed readiness object
    directly through ``args.completion_readiness``; the CLI passes a path to a
    canonical JSON receipt.  No default/synthetic readiness is manufactured.
    """

    supplied = getattr(args, "completion_readiness", None)
    if isinstance(supplied, CompletionEpochReadiness):
        blockers = supplied.validate_for(plan)
        return supplied, (blockers[0] if blockers else "")
    if isinstance(supplied, Mapping):
        try:
            readiness = CompletionEpochReadiness.from_dict(supplied)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            return None, f"completion_readiness_invalid:{type(exc).__name__}:{exc}"
        blockers = readiness.validate_for(plan)
        return readiness, (blockers[0] if blockers else "")
    if not supplied:
        return None, ""
    supplied_path = Path(str(supplied)).expanduser()
    if supplied_path.is_symlink():
        return None, (
            f"completion_readiness_invalid:{supplied_path}:symlink_not_allowed"
        )
    path = supplied_path.resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        readiness = CompletionEpochReadiness.from_dict(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError, OverflowError) as exc:
        return None, f"completion_readiness_invalid:{path}:{type(exc).__name__}:{exc}"
    blockers = readiness.validate_for(plan)
    return readiness, (blockers[0] if blockers else "")


def _load_completion_repair_link(
    args: argparse.Namespace,
) -> tuple[CompletionRepairLink | None, str]:
    """Load one current typed repair link without manufacturing a retry token.

    Repair is deliberately opt-in and path-addressed.  A missing option means
    an initial completion attempt; a present but malformed artifact is a
    blocker.  The link's previous epoch identity is later used to resolve the
    canonical terminal ledger below ``.flowguard/evidence``.
    """

    supplied = getattr(args, "completion_repair_link", None)
    if isinstance(supplied, CompletionRepairLink):
        return supplied, ""
    if isinstance(supplied, Mapping):
        try:
            return CompletionRepairLink.from_dict(supplied), ""
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            return None, f"completion_repair_link_invalid:{type(exc).__name__}:{exc}"
    if not supplied:
        return None, ""
    supplied_path = Path(str(supplied)).expanduser()
    if supplied_path.is_symlink():
        return None, (
            f"completion_repair_link_invalid:{supplied_path}:symlink_not_allowed"
        )
    path = supplied_path.resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        link = CompletionRepairLink.from_dict(payload)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        KeyError,
        OverflowError,
    ) as exc:
        return None, f"completion_repair_link_invalid:{path}:{type(exc).__name__}:{exc}"
    return link, ""


def _reconstruct_previous_completion_plan(
    ledger: Any,
) -> tuple[CompletionEpochPlan | None, str]:
    """Recover the exact initial plan identity carried by an aborted ledger.

    The terminal ledger is the only persisted completion-epoch source.  It
    carries every current-schema identity needed to rebuild the previous
    initial plan; no historical v1 reader or guessed source value is allowed.
    A second repair of an already repaired epoch is intentionally rejected by
    the two-attempt cycle bound because the prior typed link is not replayed.
    """

    if ledger.status != "aborted":
        return None, "completion_repair_previous_ledger_not_aborted"
    if ledger.attempt_index != 0:
        return None, "completion_repair_previous_ledger_not_initial_attempt"
    if ledger.full_producer_attempts != 1:
        return None, "completion_repair_previous_ledger_not_claimed"
    if ledger.repair_link_fingerprint:
        return None, "completion_repair_previous_ledger_has_repair_link"
    try:
        previous = CompletionEpochPlan.freeze(
            source_observation_fingerprint=ledger.source_observation_fingerprint,
            release_tree_fingerprint=ledger.release_tree_fingerprint,
            toolchain_environment_fingerprint=ledger.toolchain_environment_fingerprint,
            owner_dag_fingerprint=ledger.owner_dag_fingerprint,
            fixed_owner_dag_fingerprint=ledger.fixed_owner_dag_fingerprint,
            model_authority_fingerprint=ledger.model_authority_fingerprint,
            model_authority_head_fingerprint=ledger.model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=ledger.model_authority_snapshot_fingerprint,
            test_inventory_fingerprint=ledger.test_inventory_fingerprint,
            required_terminal_action_ids=ledger.terminal_action_ids,
            remaining_governed_write_ids=(),
            completion_cycle_seed_fingerprint=ledger.completion_cycle_seed_fingerprint,
            completion_cycle_id=ledger.completion_cycle_id,
            completion_cycle_max_attempts=ledger.completion_cycle_max_attempts,
            completion_objective_fingerprint=ledger.completion_objective_fingerprint,
            completion_authorization_fingerprint=getattr(
                ledger, "completion_authorization_fingerprint", ""
            ),
            attempt_index=ledger.attempt_index,
            maintenance_unit_id=getattr(ledger, "maintenance_unit_id", None),
            completion_work_id=getattr(ledger, "completion_work_id", None),
            claim_scope=getattr(ledger, "claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE),
        )
        previous = replace(previous, full_producer_attempts=1)
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        return None, f"completion_repair_previous_plan_invalid:{type(exc).__name__}:{exc}"
    if previous.epoch_id != ledger.epoch_id:
        return None, "completion_repair_previous_plan_identity_mismatch"
    return previous, ""


def _verified_completion_child_evidence(
    *,
    specs: Sequence[ChildSpec],
    children: Sequence[ValidationChildResult],
    owner_receipts: Mapping[str, Any],
    parent_current: Any,
    receipt_root: Path,
) -> dict[str, dict[str, Any]]:
    """Derive terminal child facts from the exact owner receipts just verified.

    Completion settlement must consume independently verified child evidence;
    copying the frozen action list into the ledger would let a caller
    manufacture a green terminal row.  The full producer has already frozen
    the owner currents, so this helper verifies each published receipt against
    that same snapshot without rebuilding source currentness.
    """

    children_by_id = {child.child_id: child for child in children}
    rows: dict[str, dict[str, Any]] = {}
    owner_currents = getattr(parent_current.owner_plan, "owner_currents", {})
    for spec in specs:
        child = children_by_id.get(spec.child_id)
        receipt = owner_receipts.get(spec.child_id)
        current = owner_currents.get(spec.child_id)
        if child is None or child.status != VALIDATION_STATUS_PASS:
            raise ValueError(
                f"terminal child evidence is not a terminal pass: {spec.child_id}"
            )
        if receipt is None or current is None:
            raise ValueError(
                f"terminal child evidence is missing its owner receipt: {spec.child_id}"
            )
        context = build_owner_receipt_context(current, receipt, receipt_root)
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ValueError(
                f"terminal child evidence failed independent verification: {spec.child_id}"
            )
        rows[spec.child_id] = {
            "status": verification.status,
            "current": verification.current,
            "eligible": verification.eligible,
            "verification": verification.to_dict(),
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.fingerprint,
        }
    return rows


def _verified_completed_completion_child_action_ids(
    *,
    specs: Sequence[ChildSpec],
    children: Sequence[ValidationChildResult],
    owner_receipts: Mapping[str, Any],
    parent_current: Any,
    receipt_root: Path,
) -> tuple[str, ...]:
    """Project independently verified pass owners for an aborted epoch.

    An aborted full run is not a green parent, but a successful child receipt
    remains useful repair evidence.  Verify each pass child against the same
    frozen owner current used by the parent and retain only those exact ids.
    Failed, blocked, missing, or unverifiable children are intentionally left
    out so a typed repair link must still cover them.  This is a bounded
    projection over the already materialized child/receipt maps; it does not
    rescan source files or search historical evidence.
    """

    children_by_id = {child.child_id: child for child in children}
    owner_currents = getattr(parent_current.owner_plan, "owner_currents", {})
    completed: list[str] = []
    for spec in specs:
        child = children_by_id.get(spec.child_id)
        receipt = owner_receipts.get(spec.child_id)
        current = owner_currents.get(spec.child_id)
        if (
            child is None
            or child.status != VALIDATION_STATUS_PASS
            or receipt is None
            or current is None
        ):
            continue
        try:
            context = build_owner_receipt_context(current, receipt, receipt_root)
            verification = verify_evidence_receipt(receipt, context)
        except (OSError, TypeError, ValueError, KeyError):
            continue
        if verification.ok and verification.current and verification.eligible:
            completed.append(spec.child_id)
    return tuple(sorted(set(completed)))


def _verified_completion_parent_evidence(
    *,
    parent: Any,
    parent_verification: Any,
    parent_current: Any,
    root: Path,
    receipt_root: Path,
) -> dict[str, dict[str, Any]]:
    """Project independently verified leaf facts from an exact parent reuse.

    ``verify_parent_receipt(..., integrity_only=True)`` verifies the parent
    proof and every required child against the frozen parent current.  The
    terminal ledger still needs one explicit row per required action, so the
    child receipts are projected here and checked once more against the same
    frozen owner currents.  No source manifest or receipt-history scan is
    performed by this projection.
    """

    if not getattr(parent_verification, "ok", False):
        raise ValueError("reusable parent is not independently verified")
    owner_currents = getattr(parent_current.owner_plan, "owner_currents", {})
    rows: dict[str, dict[str, Any]] = {}
    for requirement in getattr(parent, "required_child_receipts", ()):
        child = load_evidence_receipt(
            requirement.receipt_id,
            root,
            output_directory=receipt_root,
        )
        expected_fingerprint = str(
            getattr(requirement, "expected_receipt_fingerprint", "")
        )
        if expected_fingerprint and child.fingerprint != expected_fingerprint:
            raise ValueError(
                f"reusable parent child receipt fingerprint mismatch: {requirement.receipt_id}"
            )
        prefix = "validation-owner:"
        if not child.subject_id.startswith(prefix):
            raise ValueError(
                f"reusable parent child subject is not a validation owner: {child.subject_id}"
            )
        owner_id = child.subject_id[len(prefix) :]
        if not owner_id or owner_id in rows:
            raise ValueError("reusable parent child action ids are not unique")
        current = owner_currents.get(owner_id)
        if current is None:
            raise ValueError(
                f"reusable parent child current is missing: {owner_id}"
            )
        context = build_owner_receipt_context(current, child, receipt_root)
        verification = verify_evidence_receipt(child, context)
        if not verification.ok:
            raise ValueError(
                f"reusable parent child failed independent verification: {owner_id}"
            )
        rows[owner_id] = {
            "status": verification.status,
            "current": verification.current,
            "eligible": verification.eligible,
            "verification": verification.to_dict(),
            "receipt_id": child.receipt_id,
            "receipt_fingerprint": child.fingerprint,
        }
    return rows


def _reused_full_validation_result(
    *,
    reusable_parent: Any,
    completion_epoch: CompletionEpochPlan,
    terminal_ledger: Any,
    terminal_ledger_path: Path,
    readiness: CompletionEpochReadiness | None,
    planning_started_epoch: float,
) -> ValidationResult:
    """Return the zero-producer result for an exact current parent."""

    required_child_ids = tuple(completion_epoch.required_terminal_action_ids)

    return ValidationResult(
        command="check-flowguard-skill-suite",
        status=VALIDATION_STATUS_PASS,
        scope="full",
        tier="release",
        counts={
            "passed": len(required_child_ids),
            "executed": 0,
            "reused": len(required_child_ids),
            "blocked": 0,
            "required": len(required_child_ids),
            "total": len(required_child_ids),
        },
        evidence=(
            {
                "subject_id": reusable_parent.subject_id,
                "receipt_id": reusable_parent.receipt_id,
                "receipt_fingerprint": reusable_parent.fingerprint,
                "execution_disposition": OWNER_REUSE_CURRENT,
            },
        ),
        claim_boundary=(
            "An independently verified exact-current validation-parent:full "
            "was reused before any readiness producer, child producer, lease, "
            "or run artifact."
        ),
        progress_summary={
            "completed": len(required_child_ids),
            "total": len(required_child_ids),
            "producer_invocations": 0,
            "avoided_producer_invocations": len(required_child_ids),
            "estimated_work_avoided_fraction": 1.0,
            "elapsed_seconds": round(
                max(0.0, time.time() - planning_started_epoch),
                3,
            ),
            "parent_receipt_id": reusable_parent.receipt_id,
            "parent_receipt_fingerprint": reusable_parent.fingerprint,
            "completion_epoch_id": completion_epoch.epoch_id,
            "completion_epoch_ledger_status": terminal_ledger.status,
            "completion_epoch_ledger_path": str(terminal_ledger_path),
            "completion_cycle_id": completion_epoch.completion_cycle_id,
            "completion_epoch_attempt_index": completion_epoch.attempt_index,
            "completion_repair_link_fingerprint": (
                completion_epoch.repair_link.fingerprint
                if completion_epoch.repair_link is not None
                else ""
            ),
            "completion_readiness_fingerprint": (
                readiness.fingerprint if readiness is not None else ""
            ),
        },
        artifact_paths=(),
    )


def _reused_local_validation_result(
    *,
    reusable_parent: Any,
    required_child_ids: Sequence[str],
    planning_started_epoch: float,
) -> ValidationResult:
    """Return a read-only local result for an exact current parent.

    Local functional closure deliberately has no completion epoch, readiness,
    or repair identity.  The immutable validation-parent receipt is the sole
    reusable authority for this bounded claim; reading it must not create a
    new output directory, lease, receipt, or producer.
    """

    required = tuple(str(item) for item in required_child_ids)
    return ValidationResult(
        command="check-flowguard-skill-suite",
        status=VALIDATION_STATUS_PASS,
        scope="full",
        tier="local",
        counts={
            "passed": len(required),
            "executed": 0,
            "reused": len(required),
            "blocked": 0,
            "required": len(required),
            "total": len(required),
        },
        evidence=(
            {
                "subject_id": reusable_parent.subject_id,
                "receipt_id": reusable_parent.receipt_id,
                "receipt_fingerprint": reusable_parent.fingerprint,
                "execution_disposition": OWNER_REUSE_CURRENT,
            },
        ),
        claim_boundary=(
            "An independently verified exact-current local functional parent was "
            "reused before any producer, lease, run directory, or pointer write."
        ),
        progress_summary={
            "completed": len(required),
            "total": len(required),
            "required_child_ids": list(required),
            "producer_invocations": 0,
            "avoided_producer_invocations": len(required),
            "estimated_work_avoided_fraction": 1.0,
            "elapsed_seconds": round(
                max(0.0, time.time() - planning_started_epoch),
                3,
            ),
            "parent_receipt_id": reusable_parent.receipt_id,
            "parent_receipt_fingerprint": reusable_parent.fingerprint,
            "claim_scope": VALIDATION_CLAIM_SCOPE_LOCAL,
        },
        artifact_paths=(),
    )


def run_local_functional_validation(args: argparse.Namespace) -> ValidationResult:
    """Run one finite model/native/test parent without completion ceremony.

    This is the normal local closure path.  It freezes the selected functional
    owner graph once, executes only ``execute`` rows, composes one parent
    receipt, and returns.  A later exact-current invocation reuses that parent
    before allocating any run directory or lease.  Release-tree, installation,
    self-maintenance, OpenSpec, and repair/readiness owners belong to the
    explicit release path and are intentionally absent here.
    """

    planning_started_epoch = time.time()
    root = Path(args.root).resolve()
    local_args = argparse.Namespace(**vars(args))
    local_args.claim_scope = VALIDATION_CLAIM_SCOPE_LOCAL
    base_specs = _full_child_specs(local_args, root)
    specs = tuple(
        spec for spec in base_specs if spec.child_id in LOCAL_FUNCTIONAL_CHILD_IDS
    )
    required_child_ids = _required_child_ids(specs)
    if not required_child_ids:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="local",
            counts={"passed": 0, "executed": 0, "reused": 0, "blocked": 0, "required": 0, "total": 0},
            blockers=(
                {"code": "local_functional_owner_set_empty", "message": "no local functional owner is declared"},
            ),
            claim_boundary="A local functional claim cannot close without a finite native owner set.",
        )

    contracts = _owner_contracts(specs)
    receipt_root = (
        Path(args.receipt_dir).expanduser().resolve()
        if args.receipt_dir
        else root / ".flowguard" / "evidence" / "validation-owners"
    )
    required_external_components = {
        component_id: fingerprint
        for contract in contracts
        for component_id, fingerprint in contract.external_component_bindings
    }
    metrics = InvocationMetrics()
    metrics.observe("per_leaf_source_current_rebuild_count", 0)
    metrics.observe("per_leaf_receipt_store_scan_count", 0)
    planning_observation = observe_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
        metrics=metrics,
    )
    owner_plan = build_validation_owner_plan(
        root,
        contracts,
        receipt_root=receipt_root,
        required_external_components=required_external_components,
        observation=planning_observation,
        metrics=metrics,
        claim_scope=VALIDATION_CLAIM_SCOPE_LOCAL,
    )
    plan_rows = owner_plan.rows
    blocked_rows = tuple(
        {
            "code": "owner_plan_blocked",
            "child_id": row.owner_id,
            "message": row.reason,
        }
        for row in plan_rows
        if row.disposition == OWNER_BLOCKED
    )
    if blocked_rows:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="local",
            counts={
                "passed": 0,
                "executed": 0,
                "reused": sum(row.disposition == OWNER_REUSE_CURRENT for row in plan_rows),
                "blocked": len(blocked_rows),
                "required": len(required_child_ids),
                "total": len(required_child_ids),
            },
            blockers=blocked_rows,
            claim_boundary="The local owner plan blocked before any producer or lease was started.",
            progress_summary={"producer_invocations": 0, "reuse": 0, "required_child_ids": list(required_child_ids)},
        )
    parent_current = build_validation_parent_current(
        root,
        owner_plan,
        frozen_validation_manifest=owner_plan.validation_input_manifest,
        frozen_release_tree_manifest=owner_plan.release_tree_manifest,
    )

    if args.plan_only:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_PARTIAL,
            scope="local-plan-only",
            tier="local",
            counts={
                "passed": sum(row.disposition == OWNER_REUSE_CURRENT for row in plan_rows),
                "executed": 0,
                "reused": sum(row.disposition == OWNER_REUSE_CURRENT for row in plan_rows),
                "blocked": sum(row.disposition == OWNER_BLOCKED for row in plan_rows),
                "required": len(required_child_ids),
                "total": len(required_child_ids),
            },
            blockers=tuple(
                {
                    "code": "owner_plan_blocked",
                    "child_id": row.owner_id,
                    "message": row.reason,
                }
                for row in plan_rows
                if row.disposition == OWNER_BLOCKED
            ),
            residual_risk=(
                "No local functional producer executed in plan-only mode; "
                "owner dispositions were only audited.",
            ),
            claim_boundary=(
                "Local plan-only output classifies functional owners but cannot "
                "support a closure claim.",
            ),
            progress_summary={
                "completed": 0,
                "total": len(required_child_ids),
                "required_child_ids": list(required_child_ids),
                "producer_invocations": 0,
                "claim_scope": VALIDATION_CLAIM_SCOPE_LOCAL,
                "parent_identity": parent_current.parent_identity,
            },
            artifact_paths=(),
        )

    reusable_parent, parent_verification = find_reusable_parent_receipt(
        parent_current,
        root,
        receipt_root,
    )
    if reusable_parent is not None and parent_verification is not None and parent_verification.ok:
        return _reused_local_validation_result(
            reusable_parent=reusable_parent,
            required_child_ids=required_child_ids,
            planning_started_epoch=planning_started_epoch,
        )
    if args.reuse_only:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="local",
            counts={"passed": 0, "executed": 0, "reused": 0, "blocked": 0, "required": len(required_child_ids), "total": len(required_child_ids)},
            blockers=(
                {
                    "code": "local_reuse_only_parent_unavailable",
                    "message": "no exact-current local functional parent receipt is available",
                },
            ),
            claim_boundary="Reuse-only never creates a run directory, lease, receipt, or producer.",
            progress_summary={"producer_invocations": 0, "reuse": 0, "required_child_ids": list(required_child_ids)},
        )

    requested_output = args.output_dir
    output_dir = _output_directory(requested_output) if requested_output else _temporary_validation_root()
    ensure_new_run_directory(output_dir)
    children: list[ValidationChildResult]
    owner_receipts: dict[str, Any]
    source_freshness: Any
    try:
        children, owner_receipts, source_freshness = _execute_full_owner_plan(
            root=root,
            specs=specs,
            owner_plan=owner_plan,
            parent_current=parent_current,
            receipt_root=receipt_root,
            output_dir=output_dir,
            planning_observation=planning_observation,
            metrics=metrics,
        )
    except Exception as exc:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="local",
            counts={"passed": 0, "executed": 0, "reused": 0, "blocked": 1, "required": len(required_child_ids), "total": len(required_child_ids)},
            blockers=(
                {
                    "code": "local_functional_parent_execution_error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "output_directory": str(output_dir),
                },
            ),
            claim_boundary="The bounded local producer failed before a parent receipt was published; no retry was started.",
            progress_summary={"producer_invocations": 0, "output_directory": str(output_dir)},
            artifact_paths=(str(output_dir),),
        )
    status = aggregate_status(children, required_child_ids=required_child_ids)
    if any(child.status == VALIDATION_STATUS_PARTIAL for child in children):
        status = VALIDATION_STATUS_BLOCKED
    failures = tuple(
        {"code": "required_child_failed", "child_id": child.child_id, "message": child.summary}
        for child in children
        if child.status == VALIDATION_STATUS_FAIL
    )
    blockers = tuple(
        {"code": "required_child_not_pass", "child_id": child.child_id, "status": child.status, "message": child.summary}
        for child in children
        if child.status not in {VALIDATION_STATUS_PASS, VALIDATION_STATUS_FAIL}
    )
    parent_receipt = None
    if status == VALIDATION_STATUS_PASS and len(owner_receipts) == len(specs):
        parent_receipt = save_parent_receipt(
            root,
            receipt_root,
            parent_current=parent_current,
            child_receipts=tuple(owner_receipts[spec.child_id] for spec in specs),
            status=status,
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
            source_freshness=source_freshness,
        )
        verification = verify_parent_receipt(
            parent_receipt,
            root,
            receipt_root,
            parent_current=parent_current,
            integrity_only=True,
        )
        if not verification.ok:
            status = VALIDATION_STATUS_BLOCKED
            blockers += ({"code": "local_parent_receipt_verification_failed", "message": "published parent failed integrity verification"},)
    result = ValidationResult(
        command="check-flowguard-skill-suite",
        status=status,
        scope="full",
        tier="local",
        counts={
            "passed": sum(child.status == VALIDATION_STATUS_PASS for child in children),
            "executed": sum(child.payload.get("execution_disposition") == OWNER_EXECUTE for child in children),
            "reused": sum(child.payload.get("execution_disposition") == OWNER_REUSE_CURRENT for child in children),
            "blocked": sum(child.status == VALIDATION_STATUS_BLOCKED for child in children),
            "required": len(required_child_ids),
            "total": len(children),
        },
        evidence=tuple(
            {
                "child_id": child.child_id,
                "status": child.status,
                "receipt_id": child.receipt_id,
                "receipt_fingerprint": child.payload.get("owner_receipt_fingerprint", ""),
                "execution_disposition": child.payload.get("execution_disposition", OWNER_BLOCKED),
                "artifact_paths": list(child.artifact_paths),
            }
            for child in children
        ),
        failures=failures,
        blockers=blockers,
        skipped_checks=_pytest_skipped_checks(children),
        residual_risk=(
            "Local functional closure does not prove installation, consumer parity, release, or self-maintenance projection.",
        ),
        claim_boundary=(
            "This local result proves only the frozen model/native/test owner set; "
            "release and author-governance claims remain explicit separate operations."
        ),
        progress_summary={
            "completed": len(children),
            "total": len(required_child_ids),
            "required_child_ids": list(required_child_ids),
            "output_directory": str(output_dir),
            "receipt_root": str(receipt_root),
            "producer_invocations": sum(child.payload.get("execution_disposition") == OWNER_EXECUTE for child in children),
            "avoided_producer_invocations": sum(child.payload.get("execution_disposition") == OWNER_REUSE_CURRENT for child in children),
            "parent_receipt_id": parent_receipt.receipt_id if parent_receipt else "",
            "parent_receipt_fingerprint": parent_receipt.fingerprint if parent_receipt else "",
            "source_freshness_fingerprint": getattr(source_freshness, "final_observation_fingerprint", ""),
            "metrics": metrics.snapshot(),
        },
        artifact_paths=(str(output_dir / "result.json"), str(output_dir / "owner-plan.json")),
        children=tuple(children),
    )
    (output_dir / "owner-plan.json").write_text(
        json.dumps({**owner_plan.to_dict(), "required_child_ids": list(required_child_ids)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "result.json").write_text(result.to_json_text() + "\n", encoding="utf-8")
    # Local functional closure has its authoritative current pointer in the
    # content-addressed validation-parent receipt/index store.  Do not also
    # advance the shared lifecycle scope under ``.flowguard/evidence``: that
    # scope may contain standalone child runs, and mixing a standalone head
    # with a parent head is precisely the false late-stage closure failure we
    # are eliminating.  Retain the immutable run manifest, but leave the
    # shared lifecycle pointer untouched for this local claim.
    publish_run(
        output_dir,
        kind="full-validation-local",
        status=result.status,
        result_path=output_dir / "result.json",
        authority_kind="parent",
        update_head=False,
    )
    return result


def _apply_completion_repair(
    plan: CompletionEpochPlan,
    *,
    args: argparse.Namespace,
    root: Path,
) -> tuple[CompletionEpochPlan, Any | None, str]:
    """Derive the next finite-cycle plan from an aborted epoch and link.

    The returned plan is still unclaimed.  The caller must pass its positive
    readiness receipt, then claim the producer exactly once immediately before
    execution.  Invalid repair state is returned as a blocker rather than
    raising or silently falling back to a fresh initial epoch.
    """

    repair_link, link_error = _load_completion_repair_link(args)
    if link_error:
        return plan, None, link_error
    if repair_link is None:
        return plan, None, ""

    try:
        loaded = CompletionEpochTerminalLedger.load_for_epoch_id(
            repair_link.previous_epoch_id,
            root,
        )
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        return (
            plan,
            None,
            "completion_repair_previous_terminal_ledger_invalid:"
            f"{type(exc).__name__}:{exc}",
        )
    if loaded.is_absent:
        return plan, None, "completion_repair_previous_terminal_ledger_missing"
    if loaded.is_invalid:
        return plan, None, (
            "completion_repair_previous_terminal_ledger_invalid:"
            + loaded.error
        )
    previous_ledger = loaded.ledger
    if previous_ledger is None:
        return plan, None, "completion_repair_previous_terminal_ledger_missing"
    if previous_ledger.epoch_id != repair_link.previous_epoch_id:
        return plan, None, "completion_repair_previous_terminal_ledger_identity_mismatch"
    previous_plan, previous_error = _reconstruct_previous_completion_plan(
        previous_ledger
    )
    if previous_error or previous_plan is None:
        return plan, None, previous_error or "completion_repair_previous_plan_missing"

    # Rebind through the same strict plan loader used by the normal current
    # epoch path.  Structural validity alone is not enough for a repair.
    bound = CompletionEpochTerminalLedger.load_for_plan(previous_plan, root)
    if not bound.is_valid or bound.ledger is None:
        return plan, None, (
            "completion_repair_previous_terminal_ledger_binding_invalid:"
            + (bound.error or bound.status)
        )

    # A link is only a pointer/admission claim.  Reload the canonical,
    # content-addressed group named by that link and bind it to both the
    # predecessor ledger and this newly observed unlinked plan before the
    # second epoch is even constructed.  The caller-provided link directory
    # is intentionally not trusted here.
    try:
        load_completion_repair_admission_group(
            repair_link,
            root,
            previous_ledger=previous_ledger,
            current_plan=plan,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError, KeyError, OverflowError) as exc:
        return (
            plan,
            previous_ledger,
            "completion_repair_admission_group_invalid:"
            f"{type(exc).__name__}:{exc}",
        )

    try:
        repaired = CompletionEpochPlan.for_repair(
            previous_plan,
            source_observation_fingerprint=plan.source_observation_fingerprint,
            release_tree_fingerprint=plan.release_tree_fingerprint,
            toolchain_environment_fingerprint=plan.toolchain_environment_fingerprint,
            owner_dag_fingerprint=plan.owner_dag_fingerprint,
            model_authority_fingerprint=plan.model_authority_fingerprint,
            model_authority_head_fingerprint=plan.model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=plan.model_authority_snapshot_fingerprint,
            test_inventory_fingerprint=plan.test_inventory_fingerprint,
            required_terminal_action_ids=plan.required_terminal_action_ids,
            remaining_governed_write_ids=plan.remaining_governed_write_ids,
            repair_link=repair_link,
        )
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        return plan, previous_ledger, f"completion_repair_invalid:{type(exc).__name__}:{exc}"

    repair_blockers = repaired.validate_repair(previous_plan, previous_ledger)
    if repair_blockers:
        return (
            plan,
            previous_ledger,
            "completion_repair_invalid:" + ",".join(repair_blockers),
        )
    return repaired, previous_ledger, ""


def _owner_contracts(specs: Sequence[ChildSpec]) -> tuple[ValidationOwnerContract, ...]:
    contracts: list[ValidationOwnerContract] = []
    for spec in specs:
        # Dependencies are semantic evidence edges, never an implicit list
        # order.  Unrelated owners must remain independently reusable and
        # schedulable; only a producer whose receipt is consumed declares an
        # edge (currently native checks -> self-governance and model
        # regressions -> self-maintenance).
        dependencies = spec.dependency_owner_ids
        contracts.append(
            ValidationOwnerContract(
                owner_id=spec.child_id,
                command=canonical_semantic_command(
                    spec.command,
                    resource_options=spec.resource_options,
                ),
                input_patterns=spec.input_patterns,
                obligation_ids=spec.obligation_ids,
                projected_inputs=(
                    (
                        "result_identity_requirement",
                        spec.result_identity_requirement.fingerprint,
                    ),
                )
                if spec.result_identity_requirement is not None
                else (),
                dependency_owner_ids=dependencies,
                resource_keys=spec.resource_keys
                or (f"resource:validation-owner:{spec.child_id}",),
                resource_argv_options=spec.resource_options,
                external_component_bindings=(
                    spec.external_component_bindings
                    or tuple(
                        (
                            component_id,
                            _external_tree_fingerprint(Path(component_path)),
                        )
                        for component_id, component_path in spec.external_component_paths
                    )
                ),
            )
        )
    return tuple(contracts)


def _status_from_outcome(outcome: CommandOutcome) -> str:
    if outcome.launch_error:
        return VALIDATION_STATUS_BLOCKED
    payload = outcome.payload or {}
    # A structured producer may expose a detailed ``pytest_execution``
    # projection even when the aggregate owner is blocked by an unmet host
    # capability (for example, Windows reparse/symlink support).  Inspect the
    # aggregate status before the testcase projection so a clean executable
    # subset plus typed not-run capability rows remains ``blocked`` rather
    # than being misclassified as a test failure merely because the process
    # uses a non-zero diagnostic exit code.  This preserves the broad-claim
    # boundary: blocked is still non-pass and cannot settle a green parent.
    aggregate_status = str(payload.get("status", "")).strip().lower()
    if aggregate_status == VALIDATION_STATUS_BLOCKED:
        return VALIDATION_STATUS_BLOCKED
    pytest_execution = payload.get("pytest_execution")
    if isinstance(pytest_execution, Mapping):
        # JUnit is producer output, not a caller-authored assertion.  A strict
        # XPASS is a real test failure even when pytest itself exits zero; an
        # expected XFAIL remains visible in the structured projection.  A
        # failing testcase must remain a failure even when the same run has a
        # required skip; required skips are a partial-coverage condition, not
        # a downgrade of an actual failed child.
        if (
            int(pytest_execution.get("xpassed", 0) or 0) > 0
            or int(pytest_execution.get("failed", 0) or 0) > 0
            or int(pytest_execution.get("errors", 0) or 0) > 0
            or outcome.exit_code != 0
        ):
            return VALIDATION_STATUS_FAIL
        skip_details = pytest_execution.get("skip_details", ())
        if isinstance(skip_details, Sequence) and not isinstance(
            skip_details, (str, bytes)
        ):
            for item in skip_details:
                if not isinstance(item, Mapping) or item.get("required", True):
                    return VALIDATION_STATUS_PARTIAL
    raw_status = str(payload.get("status", "")).strip().lower()
    if raw_status == VALIDATION_STATUS_PASS:
        if outcome.exit_code != 0 or payload.get("ok") is False:
            return VALIDATION_STATUS_FAIL
        if payload.get("failures"):
            return VALIDATION_STATUS_FAIL
        if payload.get("blockers"):
            return VALIDATION_STATUS_BLOCKED
        if payload.get("broad_success") is False:
            return VALIDATION_STATUS_PARTIAL
        skipped = payload.get("skipped_checks", ())
        if isinstance(skipped, Sequence) and not isinstance(skipped, (str, bytes)):
            for item in skipped:
                if not isinstance(item, Mapping) or item.get("required", True):
                    return VALIDATION_STATUS_PARTIAL
        pytest_execution = payload.get("pytest_execution")
        if isinstance(pytest_execution, Mapping) and pytest_execution.get(
            "optional_metadata_unverified"
        ):
            # JUnit has no governed optional/waived vocabulary.  Retain the
            # producer annotation for diagnosis, but do not let it waive a
            # required owner case without an independent current TestMesh
            # disposition.
            if any(
                isinstance(item, Mapping) and item.get("required") is False
                for item in pytest_execution.get("skip_details", ())
            ):
                return VALIDATION_STATUS_PARTIAL
        nested = payload.get("children", ())
        if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
            for item in nested:
                if isinstance(item, Mapping) and str(item.get("status", "")).lower() != VALIDATION_STATUS_PASS:
                    return VALIDATION_STATUS_PARTIAL
        return VALIDATION_STATUS_PASS
    if raw_status in _NON_BROAD_STATUSES:
        if raw_status in {"not_run", "not-run", "skipped", "missing", "needs-review", "needs_review", "unresolved"}:
            return VALIDATION_STATUS_BLOCKED
        return VALIDATION_STATUS_PARTIAL
    if raw_status in VALIDATION_STATUSES:
        return raw_status

    decision = str(payload.get("decision", "")).strip().lower()
    if decision == "pass":
        return VALIDATION_STATUS_PASS if outcome.exit_code == 0 else VALIDATION_STATUS_FAIL
    if decision in _NON_BROAD_STATUSES:
        return VALIDATION_STATUS_PARTIAL
    if decision:
        return VALIDATION_STATUS_FAIL
    if "ok" in payload:
        if payload.get("ok") is not True or outcome.exit_code != 0 or payload.get("failures"):
            return VALIDATION_STATUS_FAIL
        if payload.get("blockers"):
            return VALIDATION_STATUS_BLOCKED
        return VALIDATION_STATUS_PASS
    return VALIDATION_STATUS_PASS if outcome.exit_code == 0 else VALIDATION_STATUS_FAIL


def _pytest_junit_projection(
    path: Path,
    *,
    nodeid_manifest: Path | None = None,
    require_exact_nodeids: bool = False,
) -> dict[str, Any] | None:
    """Read one run-local pytest JUnit report into bounded native evidence.

    The report is produced by pytest itself through ``PYTEST_ADDOPTS`` in
    ``_run_full_child``.  We retain exact testcase identities and skip reasons
    so the parent can project the child's real skips instead of manufacturing
    an empty ``skipped_checks`` list.  JUnit does not standardise node-id
    attributes.  Governed full runs therefore provide an exact node-id
    collection from a run-local recorder; the direct helper keeps its
    historical classname/name fallback unless ``require_exact_nodeids`` is
    requested.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    root_tag = root.tag.rsplit("}", 1)[-1]
    if root_tag not in {"testsuite", "testsuites"}:
        return None
    cases = tuple(root.iter("testcase"))
    recorded_nodeids: tuple[str, ...] = ()
    if nodeid_manifest is not None:
        if nodeid_manifest.is_symlink() or not nodeid_manifest.is_file():
            return None
        try:
            manifest_payload = json.loads(nodeid_manifest.read_text(encoding="utf-8"))
            if not isinstance(manifest_payload, Mapping):
                return None
            raw_nodeids = manifest_payload.get("nodeids")
            if not isinstance(raw_nodeids, list) or not raw_nodeids:
                return None
            recorded_nodeids = tuple(
                item.strip()
                for item in raw_nodeids
                if isinstance(item, str) and item.strip()
            )
            if len(recorded_nodeids) != len(raw_nodeids) or len(set(recorded_nodeids)) != len(recorded_nodeids):
                return None
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
    elif require_exact_nodeids:
        return None
    if not cases:
        try:
            declared_tests = root.attrib.get("tests")
            if declared_tests is not None and int(declared_tests) != 0:
                return None
        except (TypeError, ValueError):
            return None
        # An empty collection is still a meaningful producer result.  Keep the
        # zero counters explicit; the normal pytest exit/status checks decide
        # whether an empty suite is acceptable for the owner.
        return {
            "schema_version": "flowguard.pytest_execution.v1",
            "selected": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [],
            "node_ids": [],
            "optional_metadata_unverified": False,
        }

    passed = failed = errors = skipped = xfailed = xpassed = 0
    skip_details: list[dict[str, Any]] = []
    optional_metadata_unverified = False
    node_ids: set[str] = set()
    ordered_node_ids: list[str] = []
    if recorded_nodeids and len(recorded_nodeids) != len(cases):
        return None
    for index, case in enumerate(cases):
        explicit_node_id = next(
            (
                str(case.attrib.get(name, "")).strip()
                for name in ("nodeid", "node_id", "pytest_nodeid")
                if str(case.attrib.get(name, "")).strip()
            ),
            "",
        )
        classname = str(case.attrib.get("classname", "")).strip()
        name = str(case.attrib.get("name", "")).strip()
        node_id = explicit_node_id
        if not node_id and recorded_nodeids:
            # The recorder's report order is the exact execution order.  No
            # classname/name reconstruction is used for a governed run.
            node_id = recorded_nodeids[index]
        if not node_id and not require_exact_nodeids:
            node_id = f"{classname}::{name}" if classname and name else name or classname
        # A generated placeholder cannot be joined to the static inventory;
        # reject it instead of guessing a node id.
        if not node_id or node_id in node_ids:
            return None
        node_ids.add(node_id)
        ordered_node_ids.append(node_id)
        outcome_children = [
            child
            for child in case
            if child.tag.rsplit("}", 1)[-1] in {"failure", "error", "skipped"}
        ]
        if len(outcome_children) > 1:
            return None
        child = outcome_children[0] if outcome_children else None
        tag = child.tag.rsplit("}", 1)[-1] if child is not None else ""
        child_type = str(child.attrib.get("type", "")) if child is not None else ""
        child_message = str(child.attrib.get("message", "")) if child is not None else ""
        child_text = (child.text or "").strip() if child is not None else ""
        marker_text = " ".join((tag, child_type, child_message, child_text)).lower()
        if tag == "skipped":
            if "xfail" in marker_text:
                xfailed += 1
            else:
                skipped += 1
                reason = child_message or child_text or "pytest skipped this node"
                required_value = str(child.attrib.get("required", "")).strip().lower() if child is not None else ""
                optional_value = str(child.attrib.get("optional", "")).strip().lower() if child is not None else ""
                # Native pytest has no governed required/optional vocabulary.
                # Preserve an annotation for diagnosis, but mark it
                # unverified: only an independent current TestMesh disposition
                # may waive a required owner case.
                if required_value or optional_value:
                    optional_metadata_unverified = True
                required = not (
                    required_value in {"0", "false", "no", "optional"}
                    or optional_value in {"1", "true", "yes"}
                )
                skip_details.append(
                    {
                        "node_id": node_id,
                        "reason": reason,
                        "required": required,
                        "impact": "pytest node was not executed",
                        "owner_id": "pytest",
                        "claim_boundary": "Pytest child evidence only; broad closure requires zero required skips.",
                    }
                )
        elif tag == "failure":
            if "xpass" in marker_text:
                xpassed += 1
            else:
                failed += 1
        elif tag == "error":
            errors += 1
        else:
            passed += 1

    # Compare producer-declared aggregate counts with the concrete testcase
    # projection.  JUnit producers differ on whether an expected xfail is
    # included in ``skipped``; accept either representation but reject every
    # other contradiction (especially a false zero).
    declared = root.attrib
    for field_name, actual in (
        ("tests", len(cases)),
        ("failures", failed),
        ("errors", errors),
    ):
        raw = declared.get(field_name)
        if raw is not None:
            try:
                if int(raw) != actual:
                    return None
            except (TypeError, ValueError):
                return None
    raw_skipped = declared.get("skipped")
    if raw_skipped is not None:
        try:
            declared_skipped = int(raw_skipped)
        except (TypeError, ValueError):
            return None
        if declared_skipped not in {skipped, skipped + xfailed}:
            return None
    return {
        "schema_version": "flowguard.pytest_execution.v1",
        "selected": len(cases),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "skip_details": skip_details,
        "node_ids": ordered_node_ids,
        "optional_metadata_unverified": optional_metadata_unverified,
    }


def _pytest_skipped_checks(children: Sequence[ValidationChildResult]) -> tuple[SkippedValidation, ...]:
    """Project every producer-reported skip into the parent result.

    Child-local payloads are the only source of truth.  In particular, an
    absent/empty projection is not treated as proof that pytest had no skips.
    The identity includes the child id so two owners cannot collapse distinct
    nodes into one parent check.
    """

    projected: dict[tuple[str, str], SkippedValidation] = {}
    for child in children:
        payload = child.payload if isinstance(child.payload, Mapping) else {}
        pytest_execution = payload.get("pytest_execution")
        details = (
            pytest_execution.get("skip_details", ())
            if isinstance(pytest_execution, Mapping)
            else ()
        )
        if isinstance(details, Sequence) and not isinstance(details, (str, bytes)):
            for item in details:
                if not isinstance(item, Mapping):
                    continue
                node_id = str(item.get("node_id", "")).strip()
                if not node_id:
                    continue
                reason = str(item.get("reason", "pytest skipped this node")).strip()
                check_id = f"{child.child_id}:{node_id}"
                required = bool(item.get("required", True))
                if isinstance(pytest_execution, Mapping) and pytest_execution.get(
                    "optional_metadata_unverified"
                ):
                    required = True
                projected[(check_id, reason)] = SkippedValidation(
                    check_id=check_id,
                    reason=reason,
                    impact=str(item.get("impact", "pytest node was not executed")),
                    required=required,
                )
        # Preserve structured skips from non-pytest children too.  They are
        # already producer output and must not disappear at the parent.
        direct = payload.get("skipped_checks", ())
        if isinstance(direct, Sequence) and not isinstance(direct, (str, bytes)):
            for item in direct:
                if isinstance(item, Mapping):
                    check_id = str(item.get("check_id", "")).strip()
                    if not check_id:
                        continue
                    reason = str(item.get("reason", "")).strip()
                    key = (f"{child.child_id}:{check_id}", reason)
                    projected[key] = SkippedValidation(
                        check_id=key[0],
                        reason=reason or "producer skipped this check",
                        impact=str(item.get("impact", "producer-reported skip")),
                        required=bool(item.get("required", True)),
                    )
    return tuple(projected[key] for key in sorted(projected))


def _summary(child_id: str, status: str, outcome: CommandOutcome) -> str:
    payload = outcome.payload or {}
    detail = payload.get("summary") or payload.get("message") or payload.get("claim_boundary")
    if detail:
        return str(detail).replace("\n", " ")[:400]
    if outcome.launch_error:
        return outcome.launch_error[:400]
    return f"{child_id} exited {outcome.exit_code} with status {status}"


def _write_child_artifacts(
    child_dir: Path,
    *,
    child_id: str,
    status: str,
    outcome: CommandOutcome,
) -> tuple[str, str, str]:
    child_dir.mkdir(parents=True, exist_ok=True)
    run_dir = child_dir.parent
    result_path = child_dir / "result.json"
    diagnostic_tail_chars = 0 if status == VALIDATION_STATUS_PASS else 4000
    stdout = store_text_object(
        run_dir,
        outcome.stdout,
        media_type=(
            "application/json; charset=utf-8"
            if outcome.payload is not None
            else "text/plain; charset=utf-8"
        ),
        tail_chars=diagnostic_tail_chars,
    )
    stderr = store_text_object(
        run_dir,
        outcome.stderr,
        tail_chars=diagnostic_tail_chars,
    )
    payload = dict(outcome.payload) if outcome.payload is not None else None
    result_payload = {
        "schema_version": "flowguard.unified_validation_child.v2",
        "child_id": child_id,
        "status": status,
        "exit_code": outcome.exit_code,
        "command": list(outcome.command),
        "launch_error": outcome.launch_error,
        "stdout": stdout,
        "stderr": stderr,
        "payload_sha256": fingerprint_payload(payload),
        "payload_keys": sorted(payload) if payload is not None else [],
        "claim_boundary": "Complete child streams are retained once as compressed objects; parsed payload content is not duplicated here.",
    }
    result_path.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return (
        str((run_dir / stdout["object_path"]).resolve()),
        str((run_dir / stderr["object_path"]).resolve()),
        str(result_path),
    )


def _blocked_child(spec: ChildSpec, reason: str, child_dir: Path) -> ValidationChildResult:
    outcome = CommandOutcome(spec.command, 2, stderr=reason, launch_error=reason)
    paths = _write_child_artifacts(
        child_dir,
        child_id=spec.child_id,
        status=VALIDATION_STATUS_BLOCKED,
        outcome=outcome,
    )
    return ValidationChildResult(
        spec.child_id,
        VALIDATION_STATUS_BLOCKED,
        reason,
        artifact_paths=paths,
        claim_boundary="Required child was not executed and supplies no closure evidence.",
        payload={"missing_reason": reason, "command": list(spec.command)},
    )


def _run_full_child(
    spec: ChildSpec,
    root: Path,
    output_dir: Path,
    index: int,
) -> tuple[ValidationChildResult, SupervisedCommandResult | None]:
    child_dir = output_dir / f"{index:02d}-{spec.child_id}"
    if spec.child_id == "distribution_parity" and spec.required_path is None:
        return _blocked_child(spec, spec.missing_reason, child_dir), None
    if spec.required_path is not None and not spec.required_path.is_file():
        return (
            _blocked_child(spec, f"{spec.missing_reason}: {spec.required_path}", child_dir),
            None,
        )

    # The current pytest owner is a native finite-shard runner.  Its wrapper
    # owns collection, per-shard JUnit/node-id receipts, and exact aggregation
    # so the parent consumes one bounded JSON observation.  Keep the legacy
    # direct-JUnit path for callers that still supply a direct pytest command
    # in composition fixtures or older integrations.
    is_sharded_pytest = (
        spec.child_id == "pytest"
        and any("run_flowguard_pytest_shards.py" in str(item) for item in spec.command)
    )
    junit_path = (
        child_dir / "pytest-junit.xml"
        if spec.child_id == "pytest" and not is_sharded_pytest
        else None
    )
    nodeid_manifest_path = (
        child_dir / "pytest-nodeids.json"
        if spec.child_id == "pytest" and not is_sharded_pytest
        else None
    )
    if junit_path is not None or is_sharded_pytest:
        child_dir.mkdir(parents=True, exist_ok=True)
    child_environment: dict[str, str] | None = None
    if is_sharded_pytest:
        # This path is child-local evidence.  It is carried only through the
        # environment so the frozen owner command remains independent of a
        # particular validation run directory.
        child_environment = {
            "FLOWGUARD_PYTEST_SHARDS_DIR": str(
                (child_dir / "pytest-shards").resolve()
            ),
        }
    elif junit_path is not None:
        # ``PYTEST_ADDOPTS`` is parsed with shell-style escaping even on
        # Windows.  A native backslash path would therefore lose its
        # separators and pytest would silently create a mangled file in the
        # project root.  Keep the run-local report path absolute but use
        # forward slashes for the environment transport; pathlib still
        # resolves and reads the same file afterwards.
        option = f"--junit-xml={junit_path.resolve().as_posix()}"
        recorder_option = "-p flowguard.pytest_nodeid_recorder"
        previous_pytest_addopts = os.environ.get("PYTEST_ADDOPTS", "").strip()
        # Keep this child-local.  ``run_supervised`` receives a complete
        # merged environment and no concurrent owner can observe a temporary
        # mutation of the parent process environment.
        child_environment = {
            "PYTEST_ADDOPTS": (
                f"{previous_pytest_addopts} {shlex.quote(option)} {recorder_option}".strip()
                if previous_pytest_addopts
                else f"{shlex.quote(option)} {recorder_option}"
            ),
            "FLOWGUARD_PYTEST_NODEIDS": str(nodeid_manifest_path.resolve()),
        }
    # Keep the historical three-argument call for non-pytest children.  Apart
    # from avoiding an unnecessary ``None`` keyword, this preserves the
    # narrow command-runner seam used by composition tests and alternate
    # runners.  Only pytest needs the child-local report environment.
    runner_supports_environment = True
    if child_environment is not None:
        runner_for_signature = _execute_command
        # ``unittest.mock`` replaces the module function with a permissive
        # ``(*args, **kwargs)`` proxy while its side effect may still expose a
        # narrow historical signature.  Inspect that concrete side effect so
        # the pytest-only environment does not break alternate command-runner
        # seams used by callers and composition tests.
        side_effect = getattr(_execute_command, "side_effect", None)
        if callable(side_effect):
            runner_for_signature = side_effect
        try:
            runner_signature = inspect.signature(runner_for_signature)
        except (TypeError, ValueError):
            runner_signature = None
        if runner_signature is not None:
            runner_supports_environment = (
                "environment" in runner_signature.parameters
                or any(
                    parameter.kind is inspect.Parameter.VAR_KEYWORD
                    for parameter in runner_signature.parameters.values()
                )
            )
    if child_environment is None or not runner_supports_environment:
        outcome = _execute_command(spec.command, root, spec.timeout_seconds)
    else:
        outcome = _execute_command(
            spec.command,
            root,
            spec.timeout_seconds,
            environment=child_environment,
        )
    if junit_path is not None and runner_supports_environment:
        pytest_projection = _pytest_junit_projection(
            junit_path,
            nodeid_manifest=nodeid_manifest_path,
            require_exact_nodeids=True,
        )
        if pytest_projection is not None:
            outcome = replace(
                outcome,
                payload={
                    **dict(outcome.payload or {}),
                    "pytest_execution": pytest_projection,
                },
            )
        else:
            # Exit zero without a complete, parseable JUnit result cannot
            # establish selected-node coverage.  Preserve the native output
            # but force a fail-closed child status.
            outcome = replace(
                outcome,
                exit_code=outcome.exit_code if outcome.exit_code != 0 else 2,
                launch_error="pytest_junit_missing_or_malformed",
            )
    if outcome.supervision is not None:
        terminal = outcome.supervision.to_dict()
        terminal_path = child_dir / "supervisor-terminal.json"
        terminal_path.parent.mkdir(parents=True, exist_ok=True)
        terminal_path.write_text(
            json.dumps(terminal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
    status = _status_from_outcome(outcome)
    paths = _write_child_artifacts(child_dir, child_id=spec.child_id, status=status, outcome=outcome)
    payload = dict(outcome.payload) if outcome.payload is not None else {}
    claim_boundary = str(payload.get("claim_boundary", "Current child command and retained artifacts only."))
    receipt_id = str(
        payload.get("receipt_id")
        or payload.get("self_governance_receipt_hash")
        or payload.get("run_id")
        or ""
    )
    return (
        ValidationChildResult(
            spec.child_id,
            status,
            _summary(spec.child_id, status, outcome),
            receipt_id=receipt_id,
            artifact_paths=paths,
            claim_boundary=claim_boundary,
            payload={
                "command": list(outcome.command),
                "exit_code": outcome.exit_code,
                "launch_error": outcome.launch_error,
                "payload_sha256": fingerprint_payload(payload),
                "payload_keys": sorted(payload),
                **(
                    {"pytest_execution": dict(payload["pytest_execution"])}
                    if isinstance(payload.get("pytest_execution"), Mapping)
                    else {}
                ),
                **(
                    {"pytest_junit_path": str(junit_path.resolve())}
                    if junit_path is not None and junit_path.is_file()
                    else {}
                ),
                **(
                    {"pytest_nodeid_manifest_path": str(nodeid_manifest_path.resolve())}
                    if nodeid_manifest_path is not None and nodeid_manifest_path.is_file()
                    else {}
                ),
                **(
                    {
                        "pytest_shards_path": str(
                            (child_dir / "pytest-shards").resolve()
                        )
                    }
                    if is_sharded_pytest and (child_dir / "pytest-shards").is_dir()
                    else {}
                ),
            },
        ),
        outcome.supervision,
    )


def _finalize_full_child(
    *,
    spec: ChildSpec,
    child: ValidationChildResult,
    supervised: SupervisedCommandResult | None,
    locked_current: Any,
    root: Path,
    receipt_root: Path,
    all_contracts: Sequence[Any],
    started_at: str,
    dependency_receipts: Mapping[str, Any] | None = None,
    lease_payload: dict[str, Any] | None = None,
    source_freshness: ValidationObservationFreshness | None = None,
) -> tuple[ValidationChildResult, Any | None]:
    """Publish exactly one owner result after its producer has finished.

    The project-admission child is deliberately allowed to run before the
    full validation lease set is acquired.  Keeping the publication logic in
    one helper ensures that this read-only admission still gets the same
    supervised owner receipt and fail-closed non-pass handling as every other
    child.
    """

    if child.payload.get("launch_error") == "cleanup_unconfirmed":
        if lease_payload is not None:
            lease_payload["_preserve_residual"] = True
            terminal_path = Path(child.artifact_paths[2]).parent / "supervisor-terminal.json"
            if terminal_path.is_file():
                terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
                lease_payload["incident_episode_token"] = str(
                    terminal.get("episode_token", lease_payload["lease_token"])
                )
        return child, None

    if child.status == VALIDATION_STATUS_PASS:
        if supervised is None:
            raise ValueError(
                f"passing validation child lacks supervised producer: {spec.child_id}"
            )
        dependency_receipts = dependency_receipts or {}
        expected_dependencies = set(spec.dependency_owner_ids)
        if set(dependency_receipts) != expected_dependencies:
            raise ValueError(
                "validation child dependency receipts are not exact: "
                f"{spec.child_id} expected={sorted(expected_dependencies)} "
                f"actual={sorted(dependency_receipts)}"
            )
        evidence_context = {"validation_child": child.to_dict()}
        if expected_dependencies:
            evidence_context["dependency_receipt_bindings"] = [
                {
                    "owner_id": owner_id,
                    "receipt_id": receipt_id,
                    "receipt_fingerprint": fingerprint,
                }
                for owner_id, receipt_id, fingerprint in dependency_receipt_bindings(
                    dependency_receipts
                )
            ]
        publication = publish_supervised_validation_owner_result(
            locked_current,
            supervised,
            root,
            receipt_root,
            all_contracts=all_contracts,
            child_id=child.child_id,
            evidence_context=evidence_context,
            summary=child.summary,
            claim_boundary=child.claim_boundary,
            result_identity_requirement=spec.result_identity_requirement,
            source_freshness=source_freshness,
        )
        if not publication.ok or publication.receipt is None:
            raise ValueError(
                "supervised validation child publication blocked: "
                + publication.blocker
            )
        receipt = publication.receipt
        return (
            ValidationChildResult(
                child_id=child.child_id,
                status=child.status,
                summary=child.summary,
                receipt_id=receipt.receipt_id,
                artifact_paths=child.artifact_paths,
                claim_boundary=child.claim_boundary,
                payload={
                    **dict(child.payload),
                    "execution_disposition": OWNER_EXECUTE,
                    "owner_receipt_fingerprint": receipt.fingerprint,
                },
            ),
            receipt,
        )

    receipt = record_validation_owner_nonpass(
        locked_current,
        child,
        root,
        receipt_root,
        all_contracts=all_contracts,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
        source_freshness=source_freshness,
    )
    return (
        ValidationChildResult(
            child_id=child.child_id,
            status=child.status,
            summary=child.summary,
            receipt_id=receipt.receipt_id,
            artifact_paths=child.artifact_paths,
            claim_boundary=child.claim_boundary,
            payload={
                **dict(child.payload),
                "execution_disposition": OWNER_EXECUTE,
                "owner_receipt_fingerprint": receipt.fingerprint,
            },
        ),
        receipt,
    )


def _output_directory(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.mkdtemp(prefix=f"flowguard-unified-validation-{timestamp}-")).resolve()


def _execute_full_owner_plan(
    *,
    root: Path,
    specs: Sequence[ChildSpec],
    owner_plan: Any,
    parent_current: Any,
    receipt_root: Path,
    output_dir: Path,
    planning_observation: Any,
    metrics: InvocationMetrics | None = None,
) -> tuple[list[ValidationChildResult], dict[str, Any], ValidationObservationFreshness]:
    """Hold the parent and every executing owner lease for the complete episode."""

    children: list[ValidationChildResult] = []
    owner_receipts: dict[str, Any] = {}
    plan_by_owner = {item.owner_id: item for item in owner_plan.rows}
    lease_payloads: dict[str, dict[str, Any]] = {}

    # Freeze the one source observation before the first producer can publish
    # a receipt.  Leaf publication consumes this exact observation and is
    # therefore independent: a later sibling timeout cannot erase an earlier
    # successful leaf.  The old implementation queued every publication until
    # the end of the producer batch, which discarded all earlier successes when
    # the final sibling timed out.
    if metrics is not None:
        metrics.inc("source_freshness_checks")
    source_freshness = assert_validation_owner_observation_fresh(
        planning_observation,
        root,
        receipt_root,
    )

    # Project admission is a read-only current-layout gate.  It must run
    # before this parent creates its own validation leases: leases are
    # intentionally visible under the current evidence tree and therefore
    # would make an otherwise current layout look stale to the admission
    # audit.  No other child starts until this gate has produced its normal
    # owner result (or an explicit blocked/non-pass result).
    project_spec = next(
        (spec for spec in specs if spec.child_id == "project_audit"),
        None,
    )
    if project_spec is not None:
        project_index = next(
            index
            for index, spec in enumerate(specs, start=1)
            if spec.child_id == project_spec.child_id
        )
        project_row = plan_by_owner[project_spec.child_id]
        print(
            f"START {project_spec.child_id} disposition={project_row.disposition} "
            f"({project_index}/{len(specs)})",
            file=sys.stderr,
            flush=True,
        )
        project_child: ValidationChildResult
        project_receipt: Any | None = None
        try:
            project_current = owner_plan.owner_currents.get(project_spec.child_id)
            if project_row.disposition == OWNER_BLOCKED:
                project_child = _blocked_child(
                    project_spec,
                    project_row.reason,
                    output_dir / f"{project_index:02d}-{project_spec.child_id}",
                )
            elif project_row.disposition == OWNER_REUSE_CURRENT:
                project_receipt = owner_plan.reusable_receipts[project_spec.child_id]
                project_child = child_from_owner_receipt(project_receipt, receipt_root)
            elif project_current is None:
                project_child = _blocked_child(
                    project_spec,
                    "project admission owner current is missing from the frozen plan",
                    output_dir / f"{project_index:02d}-{project_spec.child_id}",
                )
            else:
                # The owner plan already contains the frozen current.  Do not
                # rebuild it or rescan the receipt store here; publication
                # consumes the single source observation frozen above.
                locked_current = project_current
                project_receipt = owner_plan.reusable_receipts.get(
                    project_spec.child_id
                )
                if project_receipt is not None:
                    project_child = child_from_owner_receipt(
                        project_receipt,
                        receipt_root,
                    )
                else:
                    project_started = datetime.now(timezone.utc).isoformat()
                    project_child, supervised = _run_full_child(
                        project_spec,
                        root,
                        output_dir,
                        project_index,
                    )
                    project_child, project_receipt = _finalize_full_child(
                        spec=project_spec,
                        child=project_child,
                        supervised=supervised,
                        locked_current=locked_current,
                        root=root,
                        receipt_root=receipt_root,
                        all_contracts=owner_plan.contracts,
                        started_at=project_started,
                        dependency_receipts={},
                        lease_payload=None,
                        source_freshness=source_freshness,
                    )
                    if metrics is not None and project_receipt is not None:
                        metrics.inc("leaf_publications")
            children.append(project_child)
            if project_receipt is not None:
                owner_receipts[project_spec.child_id] = project_receipt
        except Exception as exc:
            child_dir = output_dir / f"{project_index:02d}-{project_spec.child_id}"
            outcome = CommandOutcome(
                project_spec.command,
                70,
                stderr=f"{type(exc).__name__}: {exc}",
                launch_error=f"{type(exc).__name__}: {exc}",
            )
            paths = _write_child_artifacts(
                child_dir,
                child_id=project_spec.child_id,
                status=VALIDATION_STATUS_INTERNAL_ERROR,
                outcome=outcome,
            )
            children.append(
                ValidationChildResult(
                    project_spec.child_id,
                    VALIDATION_STATUS_INTERNAL_ERROR,
                    outcome.launch_error,
                    artifact_paths=paths,
                    claim_boundary="Child crashed; no closure claim is available.",
                    payload={"exception": outcome.launch_error},
                )
            )
        print(
            f"DONE {project_spec.child_id} status={children[-1].status} "
            f"({project_index}/{len(specs)})",
            file=sys.stderr,
            flush=True,
        )

    with ExitStack() as leases:
        leases.enter_context(
            evidence_execution_lease(
                receipt_root / "leases",
                owner_id="validation-parent:full",
                resource_key="validation-parent:full",
                execution_key=parent_current.parent_identity,
                plan_id=owner_plan.plan_fingerprint,
            )
        )
        for spec in specs:
            row = plan_by_owner[spec.child_id]
            if row.disposition != OWNER_EXECUTE:
                continue
            current = owner_plan.owner_currents[spec.child_id]
            lease_payloads[spec.child_id] = leases.enter_context(
                evidence_execution_lease(
                    receipt_root / "leases",
                    owner_id=current.contract.owner_id,
                    resource_key=(
                        current.contract.resource_keys[0]
                        if current.contract.resource_keys
                        else current.contract.owner_id
                    ),
                    execution_key=current.owner_identity,
                    plan_id=owner_plan.plan_fingerprint,
                )
            )

        if (
            build_validation_parent_current(
                root,
                owner_plan,
                frozen_validation_manifest=owner_plan.validation_input_manifest,
                frozen_release_tree_manifest=owner_plan.release_tree_manifest,
            ).parent_identity
            != parent_current.parent_identity
        ):
            raise ValueError("full validation identity changed after lease preflight")

        for index, spec in enumerate(specs, start=1):
            if spec.child_id == "project_audit":
                continue
            plan_row = plan_by_owner[spec.child_id]
            print(
                f"START {spec.child_id} disposition={plan_row.disposition} ({index}/{len(specs)})",
                file=sys.stderr,
                flush=True,
            )
            try:
                should_publish = False
                supervised = None
                locked_current = None
                child_started = ""
                current = owner_plan.owner_currents.get(spec.child_id)
                current_external = tuple(
                    (
                        component_id,
                        _external_tree_fingerprint(Path(component_path)),
                    )
                    for component_id, component_path in spec.external_component_paths
                )
                dependency_failures = tuple(
                    dependency_id
                    for dependency_id in (
                        current.contract.dependency_owner_ids
                        if current is not None
                        else ()
                    )
                    if not any(
                        child.child_id == dependency_id
                        and child.status == VALIDATION_STATUS_PASS
                        for child in children
                    )
                )
                dependency_receipts = {
                    dependency_id: owner_receipts[dependency_id]
                    for dependency_id in (
                        current.contract.dependency_owner_ids
                        if current is not None
                        else ()
                    )
                    if dependency_id in owner_receipts
                }
                if dependency_failures:
                    child = _blocked_child(
                        spec,
                        "dependency owners did not pass: "
                        + ", ".join(dependency_failures),
                        output_dir / f"{index:02d}-{spec.child_id}",
                    )
                elif (
                    current is not None
                    and current_external
                    and current_external != current.contract.external_component_bindings
                ):
                    child = _blocked_child(
                        spec,
                        "external component identity changed after owner-plan freeze",
                        output_dir / f"{index:02d}-{spec.child_id}",
                    )
                elif plan_row.disposition == OWNER_BLOCKED:
                    child = _blocked_child(
                        spec,
                        plan_row.reason,
                        output_dir / f"{index:02d}-{spec.child_id}",
                    )
                elif plan_row.disposition == OWNER_REUSE_CURRENT:
                    receipt = owner_plan.reusable_receipts[spec.child_id]
                    dependency_reuse_valid = (
                        current is not None
                        and set(dependency_receipts)
                        == set(current.contract.dependency_owner_ids)
                        and owner_receipt_dependency_bindings(
                            receipt,
                            receipt_root,
                        )
                        == dependency_receipt_bindings(dependency_receipts)
                    )
                    if dependency_reuse_valid:
                        child = child_from_owner_receipt(receipt, receipt_root)
                        owner_receipts[spec.child_id] = receipt
                    else:
                        # Planning normally makes this row executable when a
                        # dependency is absent or has a different receipt.  A
                        # second guard here protects against a dependency
                        # receipt changing between planning and execution and
                        # prevents a stale consumer from being reused.
                        current = owner_plan.owner_currents[spec.child_id]
                        locked_current = current
                        child_started = datetime.now(timezone.utc).isoformat()
                        child, supervised = _run_full_child(
                            spec,
                            root,
                            output_dir,
                            index,
                        )
                        should_publish = True
                else:
                    current = owner_plan.owner_currents[spec.child_id]
                    # The frozen owner current is the execution identity.  The
                    # source observation was already checked once before the
                    # first producer; publish this leaf immediately.
                    locked_current = current
                    child_started = datetime.now(timezone.utc).isoformat()
                    child, supervised = _run_full_child(
                        spec,
                        root,
                        output_dir,
                        index,
                    )
                    should_publish = True
                if should_publish:
                    if locked_current is None:
                        raise ValueError(
                            f"executed validation child lacks publication context: {spec.child_id}"
                        )
                    child, receipt = _finalize_full_child(
                        spec=spec,
                        child=child,
                        supervised=supervised,
                        locked_current=locked_current,
                        root=root,
                        receipt_root=receipt_root,
                        all_contracts=owner_plan.contracts,
                        started_at=child_started,
                        dependency_receipts=dependency_receipts,
                        lease_payload=lease_payloads.get(spec.child_id),
                        source_freshness=source_freshness,
                    )
                    if metrics is not None and receipt is not None:
                        metrics.inc("leaf_publications")
                    if receipt is not None:
                        owner_receipts[spec.child_id] = receipt
            except Exception as exc:
                child_dir = output_dir / f"{index:02d}-{spec.child_id}"
                outcome = CommandOutcome(
                    spec.command,
                    70,
                    stderr=f"{type(exc).__name__}: {exc}",
                    launch_error=f"{type(exc).__name__}: {exc}",
                )
                paths = _write_child_artifacts(
                    child_dir,
                    child_id=spec.child_id,
                    status=VALIDATION_STATUS_INTERNAL_ERROR,
                    outcome=outcome,
                )
                child = ValidationChildResult(
                    spec.child_id,
                    VALIDATION_STATUS_INTERNAL_ERROR,
                    outcome.launch_error,
                    artifact_paths=paths,
                    claim_boundary="Child crashed; no closure claim is available.",
                    payload={"exception": outcome.launch_error},
                )
            children.append(child)
            print(
                f"DONE {spec.child_id} status={child.status} ({index}/{len(specs)})",
                file=sys.stderr,
                flush=True,
            )

        if (
            build_validation_parent_current(
                root,
                owner_plan,
                frozen_validation_manifest=owner_plan.validation_input_manifest,
                frozen_release_tree_manifest=owner_plan.release_tree_manifest,
            ).parent_identity
            != parent_current.parent_identity
        ):
            raise ValueError("full validation inputs drifted before parent composition")
    return children, owner_receipts, source_freshness


def _path_is_within(root: Path, candidate: Path) -> bool:
    """Return whether ``candidate`` is contained by ``root`` after resolve."""

    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _completion_run_manifest_path(
    args: argparse.Namespace,
    root: Path,
) -> tuple[Path | None, bool]:
    """Resolve the one manifest associated with a CLI readiness input.

    The explicit option wins.  For the normal action-list command, the
    manifest is discovered beside ``readiness.json`` (or from its evidence
    sidecar) so callers do not need a second path that can drift.  The boolean
    says whether a manifest is required for this invocation; direct unit tests
    that pass a typed readiness object intentionally keep the compatibility
    path and do not need a filesystem manifest.
    """

    explicit = getattr(args, "completion_run_manifest", None)
    if explicit:
        return Path(str(explicit)).expanduser().resolve(), True

    supplied = getattr(args, "completion_readiness", None)
    if not isinstance(supplied, (str, Path)) or not str(supplied).strip():
        return None, False
    readiness_path = Path(str(supplied)).expanduser().resolve()
    evidence_path = readiness_path.with_name("readiness.evidence.json")
    if evidence_path.is_file() and not evidence_path.is_symlink():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            evidence = {}
        evidence_manifest = (
            evidence.get("completion_run_manifest_path")
            if isinstance(evidence, Mapping)
            else None
        )
        if evidence_manifest:
            return Path(str(evidence_manifest)).expanduser().resolve(), True
    return readiness_path.parent / "completion-run-manifest.json", True


def _load_completion_run_manifest(
    args: argparse.Namespace,
    root: Path,
    receipt_root: Path,
) -> tuple[dict[str, Any] | None, Path | None, str, tuple[dict[str, Any], ...]]:
    """Load and validate the immutable readiness-to-full invocation envelope."""

    path, required = _completion_run_manifest_path(args, root)
    if not required or path is None:
        return None, None, "", ()
    if not _path_is_within(root, path):
        return None, path, "completion_run_manifest_outside_root", ()
    try:
        manifest = load_manifest(path)
    except CompletionRunManifestError as exc:
        code = (
            "completion_run_manifest_missing"
            if not path.is_file()
            else "completion_run_manifest_invalid"
        )
        return None, path, f"{code}:{exc}", ()
    manifest_invocation = manifest.get("invocation", {})
    # The public readiness command historically called this field
    # ``--objective-change`` while the full command used
    # ``--completion-objective-change``.  When the full caller omits the
    # latter, consume the frozen name from the manifest; an explicitly supplied
    # name is still compared and cannot silently drift.
    manifest_objective = (
        str(manifest_invocation.get("completion_objective_change", ""))
        if isinstance(manifest_invocation, Mapping)
        else ""
    )
    if manifest_objective and not str(
        getattr(args, "completion_objective_change", "")
        or getattr(args, "objective_change", "")
    ).strip():
        setattr(args, "completion_objective_change", manifest_objective)
    expected_invocation = invocation_projection(
        args=args,
        root=root,
        receipt_root=receipt_root,
    )
    differences = compare_manifest(
        {"invocation": manifest.get("invocation", {})},
        {"invocation": expected_invocation},
    )
    if differences:
        return None, path, "completion_run_manifest_invocation_mismatch", differences
    return manifest, path, "", ()


def _completion_run_manifest_blocked_result(
    code: str,
    message: str,
    *,
    path: Path | None = None,
    differences: Sequence[Mapping[str, Any]] = (),
    required_child_ids: Sequence[str] = FULL_CHILD_IDS,
) -> ValidationResult:
    blocker: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        blocker["path"] = str(path)
    if differences:
        blocker["differences"] = [dict(item) for item in differences]
    return ValidationResult(
        command="check-flowguard-skill-suite",
        status=VALIDATION_STATUS_BLOCKED,
        scope="full",
        tier="release",
        counts={
            "passed": 0,
            "required": len(tuple(required_child_ids)),
            "total": len(tuple(required_child_ids)),
        },
        blockers=(blocker,),
        claim_boundary=(
            "The completion-run manifest was absent, invalid, or inconsistent; "
            "no owner observation, lease, run directory, receipt, or producer "
            "attempt was started."
        ),
        progress_summary={
            "completion_run_manifest_path": str(path) if path is not None else "",
            "producer_invocations": 0,
            "reuse": 0,
        },
        artifact_paths=(),
    )


def run_full_validation(args: argparse.Namespace) -> ValidationResult:
    # The ordinary full invocation is the finite functional closure.  The
    # historical readiness/epoch/repair machinery remains available only when
    # a caller explicitly supplies one of those legacy completion artifacts;
    # it must never be entered implicitly by a normal model/test run.  Release
    # identity is consumed later by release_verification.py from this parent,
    # so no release-tree or self-referential freshness loop belongs here.
    explicit_completion_controls = any(
        bool(getattr(args, field_name, None))
        for field_name in (
            "completion_readiness",
            "completion_run_manifest",
            "completion_repair_link",
            "completion_authorization",
            "completion_objective_change",
        )
    )
    # A bare ``--scope full`` is intentionally the finite local functional
    # parent.  Once a caller supplies any full-authority input (formal,
    # shadow, installed, or explicit reuse-only), however, it has selected
    # the release/authoritative composition and must stay on that route.  Do
    # not silently downgrade a requested full claim to a local three-owner
    # pass when a full preflight is malformed or stale.
    explicit_full_authority_inputs = any(
        bool(getattr(args, field_name, None))
        for field_name in (
            "formal_root",
            "shadow_root",
            "installed_root",
            "completion_readiness",
            "completion_run_manifest",
            "completion_repair_link",
            "completion_authorization",
            "completion_objective_change",
            "reuse_only",
        )
    )
    if not explicit_completion_controls and not explicit_full_authority_inputs:
        functional_args = argparse.Namespace(**vars(args))
        functional_args.claim_scope = VALIDATION_CLAIM_SCOPE_LOCAL
        return run_local_functional_validation(functional_args)

    planning_started_epoch = time.time()
    root = Path(args.root).resolve()
    # The pytest child owns path-sensitive capability qualification.  It
    # collects the finite node inventory first, runs ordinary core nodes when
    # possible, and reports required path nodes as typed blocked/not-run rows
    # when the host lacks symlink/reparse capability.  The parent must observe
    # that child result and remain fail-closed for a broad claim; it must not
    # stop every unrelated owner before the owner plan exists.
    requested_output = args.output_dir
    planning_args = argparse.Namespace(**vars(args))
    planning_args.output_dir = requested_output or str(
        root / ".flowguard" / "evidence" / "full-validation" / "__EVIDENCE_RUN__"
    )
    specs = _full_child_specs(planning_args, root)
    contracts = _owner_contracts(specs)
    receipt_root = (
        Path(args.receipt_dir).expanduser().resolve()
        if args.receipt_dir
        else root / ".flowguard" / "evidence" / "validation-owners"
    )
    (
        completion_run_manifest,
        completion_run_manifest_path,
        completion_run_manifest_error,
        completion_run_manifest_differences,
    ) = _load_completion_run_manifest(args, root, receipt_root)
    required_child_ids = _required_child_ids(specs)
    if completion_run_manifest_error:
        error_code = completion_run_manifest_error.split(":", 1)[0]
        return _completion_run_manifest_blocked_result(
            error_code,
            completion_run_manifest_error,
            path=completion_run_manifest_path,
            differences=completion_run_manifest_differences,
            required_child_ids=required_child_ids,
        )
    required_external_components = {
        component_id: fingerprint
        for contract in contracts
        for component_id, fingerprint in contract.external_component_bindings
    }
    metrics = InvocationMetrics()
    # These counters are explicit proof points for the batched path: owner
    # publication must consume the shared observation and never rebuild a
    # source current or scan the receipt store once per leaf.
    metrics.observe("per_leaf_source_current_rebuild_count", 0)
    metrics.observe("per_leaf_receipt_store_scan_count", 0)
    # Freeze one invocation-local source/receipt observation.  The owner plan
    # below projects from this value instead of independently observing each
    # owner; publication receives the same observation's current identities.
    planning_observation = observe_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
        metrics=metrics,
    )
    owner_plan = build_validation_owner_plan(
        root,
        contracts,
        receipt_root=receipt_root,
        required_external_components=required_external_components,
        observation=planning_observation,
        metrics=metrics,
        claim_scope=getattr(args, "claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE),
    )
    # A model owner can persist a semantic source inventory whose derived
    # identity is not represented by the inventory file's own bytes.  Detect
    # that drift before completion-epoch admission; otherwise the full owner
    # plan would spend the remaining producer budget only to discover the
    # same stale ledger inside the native model runner.
    try:
        model_manifest = ModelRegressionManifest.load(root)
    except (OSError, TypeError, ValueError):
        semantic_source_inventory_blockers = ()
    else:
        semantic_source_inventory_blockers = (
            audit_selected_model_source_inventories(
                root,
                (
                    entry.model_id
                    for entry in model_manifest.entries
                    if not entry.excluded
                ),
            )
        )
    if semantic_source_inventory_blockers:
        owner_plan = replace(
            owner_plan,
            rows=tuple(
                replace(
                    row,
                    disposition=OWNER_BLOCKED,
                    reason="; ".join(
                        item
                        for item in (
                            row.reason,
                            *semantic_source_inventory_blockers,
                        )
                        if item
                    ),
                    receipt_id="",
                    receipt_fingerprint="",
                )
                if row.owner_id == "model_regressions_full"
                else row
                for row in owner_plan.rows
            ),
        )
    missing_specs = {
        spec.child_id: (
            spec.missing_reason
            if spec.child_id == "distribution_parity" and args.shadow_root is None
            else f"{spec.missing_reason}: {spec.required_path}"
        )
        for spec in specs
        if (
            (
                spec.child_id == "distribution_parity"
                and args.shadow_root is None
                and getattr(args, "claim_scope", VALIDATION_CLAIM_SCOPE_RELEASE)
                == VALIDATION_CLAIM_SCOPE_RELEASE
            )
            or (
                spec.required_path is not None
                and not spec.required_path.is_file()
            )
        )
    }
    if missing_specs:
        owner_plan = replace(
            owner_plan,
            rows=tuple(
                replace(
                    row,
                    disposition=OWNER_BLOCKED,
                    reason=missing_specs[row.owner_id],
                    receipt_id="",
                    receipt_fingerprint="",
                )
                if row.owner_id in missing_specs
                else row
                for row in owner_plan.rows
            ),
        )
    parent_current = (
        None
        if owner_plan.blocked
        else build_validation_parent_current(
            root,
            owner_plan,
            frozen_validation_manifest=owner_plan.validation_input_manifest,
            frozen_release_tree_manifest=owner_plan.release_tree_manifest,
        )
    )
    plan_rows = owner_plan.rows
    plan_payload = {
        **owner_plan.to_dict(),
        "status": (
            "blocked"
            if any(item.disposition == OWNER_BLOCKED for item in plan_rows)
            else "ready"
        ),
        "counts": {
            disposition: sum(item.disposition == disposition for item in plan_rows)
            for disposition in (OWNER_EXECUTE, OWNER_REUSE_CURRENT, OWNER_BLOCKED)
        },
        "claim_boundary": (
            "The owner plan decides execution only; it is not terminal validation evidence."
        ),
    }
    plan_id = owner_plan.plan_fingerprint
    plan_payload["plan_id"] = plan_id
    completion_epoch = None
    completion_epoch_previous_ledger = None
    completion_repair_error = ""
    readiness = None
    readiness_error = ""
    epoch_admission = None
    existing_epoch_ledger = None
    completion_cycle_reservation = None
    reusable_parent = None
    parent_verification = None
    completion_reuse_error = ""
    if parent_current is not None:
        try:
            completion_epoch = _completion_epoch_plan(
                args=args,
                root=root,
                specs=specs,
                owner_plan=owner_plan,
                parent_current=parent_current,
                planning_observation=planning_observation,
            )
        except CompletionObjectiveError as exc:
            return ValidationResult(
                command="check-flowguard-skill-suite",
                status=VALIDATION_STATUS_BLOCKED,
                scope="full",
                tier="release",
                counts=plan_payload["counts"],
                blockers=(
                    {
                        "code": exc.code,
                        "message": str(exc),
                    },
                ),
                claim_boundary=(
                    "The explicit completion objective could not be independently "
                    "resolved; no readiness admission, lease, receipt, or producer "
                    "attempt was started."
                ),
                progress_summary={
                    "producer_invocations": 0,
                    "reuse": 0,
                },
                artifact_paths=(),
            )
        (
            completion_epoch,
            completion_epoch_previous_ledger,
            completion_repair_error,
        ) = _apply_completion_repair(
            completion_epoch,
            args=args,
            root=root,
        )

        if completion_run_manifest is not None:
            expected_completion_run_manifest = build_manifest(
                args=args,
                root=root,
                receipt_root=receipt_root,
                specs=specs,
                owner_plan=owner_plan,
                completion_epoch=completion_epoch,
                canonicalize_command=canonical_semantic_command,
            )
            manifest_differences = compare_manifest(
                completion_run_manifest,
                expected_completion_run_manifest,
                # Readiness necessarily knows its own readiness receipt; the
                # full command verifies that receipt separately after loading
                # it.  Output directories are already removed from the
                # invocation projection and semantic commands.
                ignore_fields=(
                    "manifest_fingerprint",
                    "plan.readiness_fingerprint",
                ),
            )
            if manifest_differences:
                return _completion_run_manifest_blocked_result(
                    "completion_run_manifest_plan_mismatch",
                    "completion-run manifest does not match the frozen full plan",
                    path=completion_run_manifest_path,
                    differences=manifest_differences,
                    required_child_ids=required_child_ids,
                )

        # Resolve the output-only epoch ledger before any readiness input.  A
        # valid exact-current parent is already terminal evidence; requiring a
        # caller-authored readiness receipt first would turn a no-op rerun into
        # another freshness loop.  The ledger is still fail-closed: an
        # invalid/aborted row prevents reuse or a second producer attempt.
        existing_epoch_ledger = CompletionEpochTerminalLedger.load_for_plan(
            completion_epoch,
            root,
        )
        reuse_allowed = (
            not args.plan_only
            and not completion_repair_error
            and completion_epoch.final_ready
            and not any(
                bool(getattr(args, field_name, False))
                for field_name in (
                    "openspec_unarchived",
                    "external_roots_unsynced",
                    "reverse_input_unaccepted",
                    "owner_dag_not_frozen",
                )
            )
        )
        if (
            reuse_allowed
            and existing_epoch_ledger.is_valid
            and existing_epoch_ledger.ledger is not None
            and existing_epoch_ledger.ledger.status != "terminal_pass"
        ):
            # Keep the later typed blocker projection, but do not spend a
            # parent/child verification walk when this epoch is already
            # terminally non-passing.
            reuse_allowed = False
        if reuse_allowed and not existing_epoch_ledger.is_invalid:
            reusable_parent, parent_verification = find_reusable_parent_receipt(
                parent_current,
                root,
                receipt_root,
            )
            if (
                reusable_parent is not None
                and parent_verification is not None
                and parent_verification.ok
            ):
                try:
                    if existing_epoch_ledger.is_valid:
                        terminal_ledger = existing_epoch_ledger.ledger
                        assert terminal_ledger is not None
                        # The existing ledger is immutable output for this
                        # exact epoch.  Reuse it verbatim; never reseal the
                        # same address with a new timestamp/metadata.
                        return _reused_full_validation_result(
                            reusable_parent=reusable_parent,
                            completion_epoch=completion_epoch,
                            terminal_ledger=terminal_ledger,
                            terminal_ledger_path=Path(existing_epoch_ledger.path),
                            readiness=None,
                            planning_started_epoch=planning_started_epoch,
                        )
                    if args.reuse_only:
                        completion_reuse_error = (
                            "completion_reuse_only_terminal_ledger_missing"
                        )
                        raise ValueError(completion_reuse_error)
                    child_evidence = _verified_completion_parent_evidence(
                        parent=reusable_parent,
                        parent_verification=parent_verification,
                        parent_current=parent_current,
                        root=root,
                        receipt_root=receipt_root,
                    )
                    terminal_ledger = CompletionEpochTerminalLedger.terminal_pass_from_verified_children(
                        completion_epoch,
                        child_evidence,
                        metadata={
                            "execution_disposition": OWNER_REUSE_CURRENT,
                            "parent_receipt_id": reusable_parent.receipt_id,
                            "parent_receipt_fingerprint": reusable_parent.fingerprint,
                        },
                    )
                    terminal_ledger_path = terminal_ledger.write(root)
                except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    completion_reuse_error = (
                        "completion_reuse_child_evidence_invalid:"
                        f"{type(exc).__name__}:{exc}"
                    )
                else:
                    return _reused_full_validation_result(
                        reusable_parent=reusable_parent,
                        completion_epoch=completion_epoch,
                        terminal_ledger=terminal_ledger,
                        terminal_ledger_path=terminal_ledger_path,
                        readiness=None,
                        planning_started_epoch=planning_started_epoch,
                    )
        if args.reuse_only:
            return ValidationResult(
                command="check-flowguard-skill-suite",
                status=VALIDATION_STATUS_BLOCKED,
                scope="full",
                tier="release",
                counts=plan_payload["counts"],
                blockers=(
                    {
                        "code": "completion_reuse_only_parent_unavailable",
                        "message": completion_reuse_error
                        or "no exact-current terminal parent receipt is available for reuse-only",
                        "epoch_id": completion_epoch.epoch_id,
                    },
                ),
                claim_boundary=(
                    "Reuse-only never creates a lease, run directory, receipt, readiness artifact, or producer attempt."
                ),
                progress_summary={
                    "completion_epoch_id": completion_epoch.epoch_id,
                    "completion_epoch_ledger_status": existing_epoch_ledger.status,
                    "completion_epoch_ledger_path": existing_epoch_ledger.path,
                    "producer_invocations": 0,
                    "reuse": 0,
                },
                artifact_paths=(),
            )
        readiness, readiness_error = _load_completion_readiness(args, completion_epoch)
        if not readiness_error and completion_run_manifest is not None:
            manifest_readiness_fingerprint = str(
                (completion_run_manifest.get("plan") or {}).get(
                    "readiness_fingerprint", ""
                )
            )
            if readiness is None:
                readiness_error = "completion_run_manifest_readiness_missing"
            elif manifest_readiness_fingerprint != readiness.fingerprint:
                readiness_error = "completion_run_manifest_readiness_fingerprint_mismatch"
        if (
            not readiness_error
            and readiness is not None
            and completion_epoch_previous_ledger is not None
            and readiness.previous_aborted_epoch_ledger_fingerprint
            != completion_epoch_previous_ledger.fingerprint
        ):
            readiness_error = (
                "completion_readiness_previous_aborted_epoch_ledger_mismatch"
            )
        if completion_repair_error:
            readiness_error = ":".join(
                item
                for item in (completion_repair_error, readiness_error)
                if item
            )
        if completion_reuse_error:
            readiness_error = ":".join(
                item
                for item in (completion_reuse_error, readiness_error)
                if item
            )
        epoch_admission = _completion_epoch_admission(
            completion_epoch,
            args,
            readiness=readiness,
            readiness_error=readiness_error,
        )
    if args.plan_only:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_PARTIAL,
            scope="full-plan-only",
            tier="release",
            counts=plan_payload["counts"],
            blockers=tuple(
                {
                    "code": "owner_plan_blocked",
                    "child_id": item.owner_id,
                    "message": item.reason,
                }
                for item in plan_rows
                if item.disposition == OWNER_BLOCKED
            )
            + tuple(
                {
                    "code": blocker,
                    "message": blocker,
                    "epoch_id": completion_epoch.epoch_id,
                }
                for blocker in (epoch_admission.blockers if epoch_admission is not None else ())
            ),
            residual_risk=(
                "No validation producer executed in plan-only mode; readiness and owner dispositions were only audited.",
            ),
            claim_boundary=(
                "Plan-only output classifies owners and checks positive completion readiness but cannot support validation or release closure."
            ),
            progress_summary={
                "completed": 0,
                "total": len(specs),
                "completion_epoch_id": (
                    completion_epoch.epoch_id if completion_epoch is not None else ""
                ),
                "completion_epoch_admission": (
                    epoch_admission.to_dict() if epoch_admission is not None else {}
                ),
                "completion_readiness_fingerprint": (
                    readiness.fingerprint if readiness is not None else ""
                ),
                "completion_cycle_id": (
                    completion_epoch.completion_cycle_id
                    if completion_epoch is not None
                    else ""
                ),
                "completion_epoch_attempt_index": (
                    completion_epoch.attempt_index
                    if completion_epoch is not None
                    else 0
                ),
                "completion_repair_link_fingerprint": (
                    completion_epoch.repair_link.fingerprint
                    if completion_epoch is not None
                    and completion_epoch.repair_link is not None
                    else ""
                ),
            },
            artifact_paths=(),
        )
    if parent_current is None:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="release",
            counts=plan_payload["counts"],
            blockers=tuple(
                {
                    "code": "owner_plan_blocked",
                    "child_id": item.owner_id,
                    "message": item.reason,
                }
                for item in plan_rows
                if item.disposition == OWNER_BLOCKED
            ),
            claim_boundary=(
                "The complete owner plan blocked before any lease, producer, "
                "receipt, run artifact, or current pointer was created."
            ),
            artifact_paths=(),
        )

    if completion_epoch is None or epoch_admission is None or not epoch_admission.ok:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="release",
            counts=plan_payload["counts"],
            blockers=tuple(
                {
                    "code": blocker,
                    "message": blocker,
                    "epoch_id": completion_epoch.epoch_id,
                }
                for blocker in epoch_admission.blockers
            ),
            residual_risk=(
                "Completion epoch final admission is output-only and did not execute a producer.",
            ),
            claim_boundary=(
                "No full producer may start while governed writes or required external/currentness gates remain open."
            ),
            progress_summary={
                "completion_epoch_id": completion_epoch.epoch_id,
                "completion_epoch_admission": epoch_admission.to_dict(),
                "completion_cycle_id": completion_epoch.completion_cycle_id,
                "completion_epoch_attempt_index": completion_epoch.attempt_index,
                "completion_repair_link_fingerprint": (
                    completion_epoch.repair_link.fingerprint
                    if completion_epoch.repair_link is not None
                    else ""
                ),
                "completion_readiness_fingerprint": (
                    readiness.fingerprint if readiness is not None else ""
                ),
                "completed": 0,
                "total": len(required_child_ids),
            },
            artifact_paths=(),
        )

    if not existing_epoch_ledger.is_absent:
        if existing_epoch_ledger.is_invalid:
            return ValidationResult(
                command="check-flowguard-skill-suite",
                status=VALIDATION_STATUS_BLOCKED,
                scope="full",
                tier="release",
                counts=plan_payload["counts"],
                blockers=(
                    {
                        "code": "completion_epoch_ledger_invalid",
                        "message": existing_epoch_ledger.error,
                        "epoch_id": completion_epoch.epoch_id,
                        "path": existing_epoch_ledger.path,
                    },
                ),
                claim_boundary=(
                    "A present but unreadable or stale completion epoch ledger blocks before any producer, lease, or run artifact."
                ),
                progress_summary={
                    "completion_epoch_id": completion_epoch.epoch_id,
                    "completion_epoch_ledger_status": existing_epoch_ledger.status,
                    "completion_epoch_ledger_path": existing_epoch_ledger.path,
                    "completion_cycle_id": completion_epoch.completion_cycle_id,
                    "completion_epoch_attempt_index": completion_epoch.attempt_index,
                    "completion_repair_link_fingerprint": (
                        completion_epoch.repair_link.fingerprint
                        if completion_epoch.repair_link is not None
                        else ""
                    ),
                    "completed": 0,
                    "total": len(required_child_ids),
                },
                artifact_paths=(),
            )
        existing_ledger = existing_epoch_ledger.ledger
        # An existing terminal ledger is authoritative for this frozen epoch.
        # A successful parent should have been reused above; an
        # aborted/blocked ledger must never trigger a second producer attempt.
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="release",
            counts=plan_payload["counts"],
            blockers=(
                {
                    "code": "completion_epoch_terminal_already_recorded",
                    "message": "completion epoch already has a terminal ledger; create a new epoch after source repair",
                    "epoch_id": completion_epoch.epoch_id,
                    "ledger_status": existing_ledger.status if existing_ledger else existing_epoch_ledger.status,
                },
            ),
            claim_boundary=(
                "A completion epoch permits at most one full producer attempt and cannot be retried after terminal output."
            ),
            progress_summary={
                "completion_epoch_id": completion_epoch.epoch_id,
                "completion_epoch_ledger_status": (
                    existing_ledger.status if existing_ledger else existing_epoch_ledger.status
                ),
                "completion_cycle_id": completion_epoch.completion_cycle_id,
                "completion_epoch_attempt_index": completion_epoch.attempt_index,
                "completion_repair_link_fingerprint": (
                    completion_epoch.repair_link.fingerprint
                    if completion_epoch.repair_link is not None
                    else ""
                ),
                "completed": 0,
                "total": len(required_child_ids),
            },
            artifact_paths=(),
        )
    try:
        completion_epoch, completion_cycle_reservation = reserve_full_producer(
            completion_epoch,
            root,
            producer_id="check-flowguard-skill-suite",
            lease_id="validation-parent:full",
            metadata={
                "scope": "full",
                "required_child_count": len(required_child_ids),
            },
        )
    except CompletionCycleReservationError as exc:
        return ValidationResult(
            command="check-flowguard-skill-suite",
            status=VALIDATION_STATUS_BLOCKED,
            scope="full",
            tier="release",
            counts=plan_payload["counts"],
            blockers=(
                {
                    "code": exc.code,
                    "message": str(exc),
                    "epoch_id": completion_epoch.epoch_id,
                    "path": exc.path,
                    "blockers": list(exc.blockers),
                },
            ),
            claim_boundary=(
                "The persistent completion-cycle reservation rejected a second, "
                "concurrent, stale, or over-budget full producer attempt."
            ),
            progress_summary={
                "completion_epoch_id": completion_epoch.epoch_id,
                "completion_cycle_id": completion_epoch.completion_cycle_id,
                "completion_cycle_reservation_path": exc.path,
                "producer_invocations": 0,
                "reuse": 0,
            },
            artifact_paths=(),
        )

    output_dir = _output_directory(requested_output)
    ensure_new_run_directory(output_dir)
    # Child commands must write beneath the same retained run directory even
    # when the caller lets the parent choose a temporary output location.
    args.output_dir = str(output_dir)
    specs = _full_child_specs(args, root)
    plan_path = output_dir / "owner-plan.json"
    plan_path.write_text(
        json.dumps(plan_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    started_at = datetime.now(timezone.utc).isoformat()
    started_epoch = time.time()
    try:
        children, owner_receipts, source_freshness = _execute_full_owner_plan(
            root=root,
            specs=specs,
            owner_plan=owner_plan,
            parent_current=parent_current,
            receipt_root=receipt_root,
            output_dir=output_dir,
            planning_observation=planning_observation,
            metrics=metrics,
        )
    except Exception as exc:
        # A producer can fail before the normal child aggregation path (for
        # example, when a stale evidence lease is discovered while starting a
        # child).  Do not leave the completion reservation active: that would
        # turn an infrastructure/setup failure into a permanent false
        # "already running" blocker.  Publish an explicit aborted ledger and
        # settle the reservation before returning the typed failure.  No
        # partial child is promoted to completed evidence here; a later typed
        # repair must re-qualify any affected owner explicitly.
        failure_message = (
            "full validation producer raised before parent composition: "
            f"{type(exc).__name__}: {exc}"
        )
        aborted_ledger = CompletionEpochTerminalLedger.aborted(
            completion_epoch,
            failure_message,
            completed_terminal_action_ids=(),
            metadata={
                "execution_disposition": OWNER_EXECUTE,
                "child_count": 0,
                "producer_exception_type": type(exc).__name__,
                "producer_exception": str(exc),
                "cleanup_status": "confirmed",
            },
        )
        aborted_ledger_path = str(aborted_ledger.write(root))
        completion_cycle_reservation = abort_full_producer(
            completion_cycle_reservation,
            root,
            terminal_ledger_fingerprint=aborted_ledger.fingerprint,
            cleanup_status="confirmed",
            metadata={
                "terminal_status": aborted_ledger.status,
                "terminal_ledger_path": aborted_ledger_path,
                "producer_exception_type": type(exc).__name__,
            },
        )
        parent_path = output_dir / "result.json"
        failure_status = (
            VALIDATION_STATUS_BLOCKED
            if isinstance(exc, GitQueryTimeout)
            else VALIDATION_STATUS_INTERNAL_ERROR
        )
        failure_blockers = (failure_message,) if failure_status == VALIDATION_STATUS_BLOCKED else ()
        failure_rows = (failure_message,) if failure_status != VALIDATION_STATUS_BLOCKED else ()
        result = ValidationResult(
            command="check-flowguard-skill-suite",
            status=failure_status,
            scope="full",
            tier="release",
            counts={
                "passed": 0,
                "executed": 0,
                "reused": 0,
                "blocked": 0,
                "required": len(required_child_ids),
                "total": 0,
            },
            failures=failure_rows,
            blockers=failure_blockers,
            claim_boundary=(
                "The full producer failed before parent composition. Its completion "
                "epoch was durably aborted and its reservation settled; no partial "
                "child was promoted to current completion evidence."
            ),
            progress_summary={
                "completed": 0,
                "total": len(required_child_ids),
                "output_directory": str(output_dir),
                "completion_epoch_id": completion_epoch.epoch_id,
                "completion_epoch_ledger_status": aborted_ledger.status,
                "completion_epoch_ledger_path": aborted_ledger_path,
                "completion_cycle_reservation_path": str(
                    CompletionCycleReservation.path_for_epoch_id(
                        completion_epoch.epoch_id,
                        root,
                    )
                ),
                "completion_cycle_reservation_status": completion_cycle_reservation.status,
                "producer_invocations": 0,
                "avoided_producer_invocations": 0,
                "exception_type": type(exc).__name__,
            },
            artifact_paths=(str(parent_path), str(plan_path)),
        )
        parent_path.write_text(result.to_json_text() + "\n", encoding="utf-8")
        publish_run(
            output_dir,
            kind="full-validation",
            status=result.status,
            result_path=parent_path,
            authority_kind="parent",
        )
        return result
    fresh_external = {
        contract.owner_id: contract.external_component_bindings
        for contract in _owner_contracts(_full_child_specs(args, root))
    }
    frozen_external = {
        contract.owner_id: contract.external_component_bindings
        for contract in owner_plan.contracts
    }
    if fresh_external != frozen_external:
        raise ValueError(
            "external component identities drifted before parent composition"
        )

    status = aggregate_status(children, required_child_ids=required_child_ids)
    # A complete release parent is unavailable when the project admission
    # audit is non-pass or when any required child only produced a partial
    # result.  Unrelated owners still execute (and their receipts remain
    # reusable), but the parent must stay visibly blocked until the gate is
    # closed.  Hard failures remain failures when no closure blocker exists;
    # dependency-induced blocked children therefore keep the parent blocked.
    project_audit = next(
        (child for child in children if child.child_id == "project_audit"),
        None,
    )
    if project_audit is not None and project_audit.status != VALIDATION_STATUS_PASS:
        status = VALIDATION_STATUS_BLOCKED
    elif any(child.status == VALIDATION_STATUS_PARTIAL for child in children):
        status = VALIDATION_STATUS_BLOCKED
    publication_observation = planning_observation
    publication_freshness = source_freshness
    if status == VALIDATION_STATUS_PASS and len(owner_receipts) == len(specs):
        # Reconcile all newly written owner receipts in one bounded store read
        # after the producer batch.  No owner is allowed to rebuild source
        # currentness or independently scan the receipt store here.
        metrics.inc("receipt_batch_refreshes")
        publication_observation = refresh_validation_owner_observation_receipts(
            planning_observation,
            root,
            receipt_root,
            tuple(owner_receipts[spec.child_id] for spec in specs),
        )
        publication_freshness = assert_validation_owner_observation_receipts_fresh(
            planning_observation,
            publication_observation,
            source_freshness,
            root,
            receipt_root,
        )
    failures = tuple(
        {"code": "required_child_failed", "child_id": child.child_id, "message": child.summary}
        for child in children
        if child.status == VALIDATION_STATUS_FAIL
    )
    blockers = tuple(
        {
            "code": "required_child_not_broad_pass",
            "child_id": child.child_id,
            "status": child.status,
            "message": child.summary,
        }
        for child in children
        if child.status not in {VALIDATION_STATUS_PASS, VALIDATION_STATUS_FAIL}
    )
    # Never infer a clean pytest run from a zero exit code or a compact child
    # result.  The child producer's structured projection is the sole source
    # for parent skip rows, including the exact node id and reason.
    skipped = _pytest_skipped_checks(children)
    parent_path = output_dir / "result.json"
    parent_receipt = None
    completion_epoch_terminal_ledger = None
    completion_epoch_terminal_ledger_path = ""
    if status == VALIDATION_STATUS_PASS and len(owner_receipts) == len(specs):
        parent_receipt = save_parent_receipt(
            root,
            receipt_root,
            parent_current=parent_current,
            child_receipts=tuple(owner_receipts[spec.child_id] for spec in specs),
            status=status,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            source_freshness=source_freshness,
        )
        parent_verification = verify_parent_receipt(
            parent_receipt,
            root,
            receipt_root,
            parent_current=parent_current,
            integrity_only=True,
        )
        if not parent_verification.ok:
            raise ValueError("published validation parent failed verification")
        child_evidence = _verified_completion_child_evidence(
            specs=specs,
            children=children,
            owner_receipts=owner_receipts,
            parent_current=parent_current,
            receipt_root=receipt_root,
        )
        completion_epoch_terminal_ledger = CompletionEpochTerminalLedger.terminal_pass_from_verified_children(
            completion_epoch,
            child_evidence,
            metadata={
                "execution_disposition": OWNER_EXECUTE,
                "parent_receipt_id": parent_receipt.receipt_id,
                "parent_receipt_fingerprint": parent_receipt.fingerprint,
            },
        )
        completion_epoch_terminal_ledger_path = str(
            completion_epoch_terminal_ledger.write(root)
        )
    else:
        # A producer that did not reach a complete parent is terminal for this
        # epoch too.  Recording an output-only abort prevents a timeout,
        # interruption, or partial failure from being silently retried against
        # the same frozen identities.  Preserve only independently verified
        # pass children so a later typed repair can target the actual failed
        # owners instead of repeating every child in the run.
        completed_terminal_action_ids = _verified_completed_completion_child_action_ids(
            specs=specs,
            children=children,
            owner_receipts=owner_receipts,
            parent_current=parent_current,
            receipt_root=receipt_root,
        )
        completion_epoch_terminal_ledger = CompletionEpochTerminalLedger.aborted(
            completion_epoch,
            f"full validation ended with status {status}",
            completed_terminal_action_ids=completed_terminal_action_ids,
            metadata={
                "execution_disposition": OWNER_EXECUTE,
                "child_count": len(children),
                "completed_terminal_action_ids": list(
                    completed_terminal_action_ids
                ),
            },
        )
        completion_epoch_terminal_ledger_path = str(
            completion_epoch_terminal_ledger.write(root)
        )
    if completion_cycle_reservation is not None:
        # Persist the terminal producer state only after the immutable ledger
        # has been written.  If this process is interrupted before this point,
        # the durable ``active`` reservation intentionally blocks a retry.
        if completion_epoch_terminal_ledger.status == "terminal_pass":
            completion_cycle_reservation = settle_full_producer(
                completion_cycle_reservation,
                root,
                terminal_ledger_fingerprint=completion_epoch_terminal_ledger.fingerprint,
                cleanup_status="confirmed",
                metadata={
                    "terminal_status": completion_epoch_terminal_ledger.status,
                    "terminal_ledger_path": completion_epoch_terminal_ledger_path,
                },
            )
        else:
            completion_cycle_reservation = abort_full_producer(
                completion_cycle_reservation,
                root,
                terminal_ledger_fingerprint=completion_epoch_terminal_ledger.fingerprint,
                cleanup_status="confirmed",
                metadata={
                    "terminal_status": completion_epoch_terminal_ledger.status,
                    "terminal_ledger_path": completion_epoch_terminal_ledger_path,
                },
            )
    result = ValidationResult(
        command="check-flowguard-skill-suite",
        status=status,
        scope="full",
        tier="release",
        counts={
            "passed": sum(child.status == VALIDATION_STATUS_PASS for child in children),
            "executed": sum(
                child.payload.get("execution_disposition") == OWNER_EXECUTE
                for child in children
            ),
            "reused": sum(
                child.payload.get("execution_disposition") == OWNER_REUSE_CURRENT
                for child in children
            ),
            "blocked": sum(child.status == VALIDATION_STATUS_BLOCKED for child in children),
            "required": len(required_child_ids),
            "total": len(children),
        },
        evidence=tuple(
            {
                "child_id": child.child_id,
                "status": child.status,
                "receipt_id": child.receipt_id,
                "receipt_fingerprint": child.payload.get("owner_receipt_fingerprint", ""),
                "execution_disposition": child.payload.get("execution_disposition", OWNER_BLOCKED),
                "artifact_paths": list(child.artifact_paths),
            }
            for child in children
        ),
        failures=failures,
        blockers=blockers,
        skipped_checks=skipped,
        residual_risk=(
            "The parent composes only independently verified owner receipts for one frozen content identity.",
            "Remote publication and post-publication verification remain separate release gates.",
        ),
        claim_boundary=(
            "Full pass requires exact pass from project adoption, all 15 light/deep skill contracts, "
            "receipt-bound self-governance, manifest full models, pytest, strict OpenSpec, and complete "
            "formal/shadow/installed distribution checks for one frozen owner plan; exact-current prior receipts may be reused."
        ),
        progress_summary={
            "completed": len(children),
            "total": len(required_child_ids),
            "output_directory": str(output_dir),
            "owner_plan_path": str(plan_path),
            "receipt_root": str(receipt_root),
            "elapsed_seconds": round(max(0.0, time.time() - started_epoch), 3),
            "producer_invocations": sum(
                child.payload.get("execution_disposition") == OWNER_EXECUTE
                for child in children
            ),
            "avoided_producer_invocations": sum(
                child.payload.get("execution_disposition") == OWNER_REUSE_CURRENT
                for child in children
            ),
            "estimated_work_avoided_fraction": round(
                (
                    sum(
                        child.payload.get("execution_disposition") == OWNER_REUSE_CURRENT
                        for child in children
                    )
                    / len(required_child_ids)
                ),
                3,
            ),
            "source_observation_fingerprint": planning_observation.source_observation_fingerprint,
            "source_freshness_fingerprint": source_freshness.final_observation_fingerprint,
            "publication_freshness_fingerprint": publication_freshness.final_observation_fingerprint,
            "metrics": metrics.snapshot(),
            "per_leaf_source_current_rebuild_count": 0,
            "per_leaf_receipt_store_scan_count": 0,
            "receipt_batch_refreshes": metrics.snapshot()["counters"].get("receipt_batch_refreshes", 0),
            "parent_receipt_id": parent_receipt.receipt_id if parent_receipt else "",
            "parent_receipt_fingerprint": parent_receipt.fingerprint if parent_receipt else "",
            "completion_epoch_id": completion_epoch.epoch_id,
            "completion_epoch_ledger_status": (
                completion_epoch_terminal_ledger.status
                if completion_epoch_terminal_ledger is not None
                else ""
            ),
            "completion_epoch_ledger_path": completion_epoch_terminal_ledger_path,
            "completion_cycle_reservation_path": (
                str(
                    CompletionCycleReservation.path_for_epoch_id(
                        completion_epoch.epoch_id,
                        root,
                    )
                )
                if completion_cycle_reservation is not None
                else ""
            ),
            "completion_cycle_reservation_status": (
                completion_cycle_reservation.status
                if completion_cycle_reservation is not None
                else ""
            ),
            "completion_cycle_id": completion_epoch.completion_cycle_id,
            "completion_epoch_attempt_index": completion_epoch.attempt_index,
            "completion_repair_link_fingerprint": (
                completion_epoch.repair_link.fingerprint
                if completion_epoch.repair_link is not None
                else ""
            ),
            "completion_readiness_fingerprint": (
                readiness.fingerprint if readiness is not None else ""
            ),
        },
        artifact_paths=(str(parent_path), str(plan_path)),
        children=tuple(children),
    )
    parent_path.write_text(result.to_json_text() + "\n", encoding="utf-8")
    publish_run(
        output_dir,
        kind="full-validation",
        status=result.status,
        result_path=parent_path,
        authority_kind="parent",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("light", "affected", "full"),
        default="light",
        help=(
            "Execution depth: light=currentness/layout, affected=exact changed members, "
            "full=all declared owners; affected never falls back."
        ),
    )
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument(
        "--skillguard",
        default="all",
        help="'all' for installed SkillGuard or an explicit skillguard.py path",
    )
    parser.add_argument("--member", action="append", default=[], help="Affected profile member selection; repeat to select members")
    parser.add_argument(
        "--impact-plan",
        help=(
            "Current AffectedImpactPlan JSON for --scope affected; the plan "
            "is the sole source of changed-member and owner disposition truth."
        ),
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Exact changed path used for light/affected profile admission; repeat as needed.",
    )
    parser.add_argument(
        "--light-operation-budget",
        type=int,
        default=LIGHT_SUITE_OPERATION_BUDGET,
        help="Maximum bounded logical operations for one light read.",
    )
    parser.add_argument(
        "--light-time-budget",
        type=float,
        default=LIGHT_SUITE_TIME_BUDGET_SECONDS,
        help="Maximum seconds for one light read; no recursive refresh is attempted.",
    )
    parser.add_argument(
        "--allow-light-cache-write",
        action="store_true",
        help=(
            "Explicitly allow the author-side light invocation to write its "
            "private work cache; routine/read-only light remains write-free."
        ),
    )
    parser.add_argument(
        "--operation-kind",
        choices=("read_only", "change", "qualification"),
        help=(
            "Typed task fact used for profile admission. If omitted, light is "
            "read-only and affected is a change; no producer is selected from prose."
        ),
    )
    parser.add_argument("--output-dir", help="Full-scope parent and child artifact directory")
    parser.add_argument(
        "--pytest-resume-output",
        default="",
        help=(
            "Explicit prior pytest-shards directory whose exact terminal "
            "shards may be reused once during a bounded repair."
        ),
    )
    parser.add_argument(
        "--completion-objective-change",
        "--objective-change",
        help=(
            "Named current OpenSpec change whose reviewed artifacts derive the "
            "explicit completion objective identity"
        ),
    )
    parser.add_argument(
        "--maintenance-unit-id",
        default=COMPLETION_MAINTENANCE_UNIT_ID,
        help=(
            "Stable maintenance namespace for the finite completion budget; "
            "it is never derived from output paths or mutable task text."
        ),
    )
    parser.add_argument(
        "--completion-work-id",
        default=COMPLETION_DEFAULT_WORK_ID,
        help=(
            "Stable work identity for one completion item; changing reports, "
            "pointers, or descriptions does not create a new identity."
        ),
    )
    parser.add_argument(
        "--completion-authorization",
        help=(
            "Explicit typed same-work authorization for one new finite "
            "completion cycle; the artifact must be inside the repository."
        ),
    )
    parser.add_argument(
        "--claim-scope",
        choices=(
            COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
            COMPLETION_CLAIM_SCOPE_RELEASE,
        ),
        # ``full`` remains an explicit qualification profile for the existing
        # release command. Routine callers select the bounded local functional
        # profile explicitly; it never inherits the release epoch.
        default=COMPLETION_CLAIM_SCOPE_RELEASE,
        help=(
            "Functional local validation or explicit release claim. Release "
            "is the full-suite default; local validation omits ReleaseTreeManifest."
        ),
    )
    parser.add_argument(
        "--authority-kind",
        choices=("standalone", "child"),
        default="standalone",
        help="Light/affected evidence authority; full validation supplies child explicitly.",
    )
    parser.add_argument(
        "--parent-scope",
        default="",
        help="Required parent scope identity when light/affected evidence is a full-validation child.",
    )
    parser.add_argument(
        "--receipt-dir",
        help="Persistent native owner receipt/proof store; defaults under .flowguard/evidence",
    )
    parser.add_argument(
        "--model-receipt-dir",
        help=(
            "Persistent model-owner receipt/proof store shared by readiness, "
            "full model regression, and self-blueprint; defaults under "
            ".flowguard/evidence/model-owner-receipts"
        ),
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Freeze and print execute/reuse_current/blocked owner dispositions without running producers",
    )
    parser.add_argument(
        "--reuse-only",
        action="store_true",
        help=(
            "Reuse one exact-current terminal parent only; if none exists, "
            "return blocked without creating a run directory, receipt, lease, or producer."
        ),
    )
    parser.add_argument(
        "--completion-readiness",
        "--readiness",
        dest="completion_readiness",
        help=(
            "Current positive completion-readiness JSON receipt. Full scope blocks "
            "when this receipt is absent, malformed, or stale."
        ),
    )
    parser.add_argument(
        "--completion-run-manifest",
        dest="completion_run_manifest",
        help=(
            "Immutable readiness-to-full invocation manifest. When omitted, "
            "full scope discovers completion-run-manifest.json beside the "
            "readiness receipt."
        ),
    )
    parser.add_argument(
        "--completion-repair-link",
        "--repair-link",
        dest="completion_repair_link",
        help=(
            "Current-schema typed repair-link JSON for one previously aborted "
            "completion epoch. The prior terminal ledger is resolved at its "
            "canonical evidence path; malformed or missing repair state blocks."
        ),
    )
    parser.add_argument(
        "--formal-root",
        "--formal",
        dest="formal_root",
        help="Formal repository or formal .agents/skills tree",
    )
    parser.add_argument(
        "--shadow-root",
        "--shadow",
        dest="shadow_root",
        help="Shadow repository or shadow .agents/skills tree (required for full parity)",
    )
    parser.add_argument(
        "--installed-root",
        "--installed",
        dest="installed_root",
        help="Installed skills tree; defaults to ~/.codex/skills",
    )
    parser.add_argument(
        "--model-jobs",
        "--jobs",
        dest="model_jobs",
        type=int,
        default=1,
        help="Full model-regression concurrency",
    )
    parser.add_argument(
        "--model-timeout",
        "--timeout",
        dest="model_timeout",
        type=float,
        help="Per-model timeout override in seconds",
    )
    parser.add_argument(
        "--model-parent-receipt",
        dest="model_parent_receipt",
        help=(
            "Exact typed current full-model parent artifact for the read-only "
            "model child route; no historical parent discovery is allowed."
        ),
    )
    parser.add_argument(
        "--gate-timeout",
        type=float,
        default=900.0,
        help="Readiness gate timeout identity; must match the frozen manifest",
    )
    parser.add_argument(
        "--require-executed-evidence",
        action="store_true",
        help=(
            "Require native model-owner case IDs and direct leaf receipts in "
            "the model and self-blueprint children."
        ),
    )
    parser.add_argument(
        "--remaining-governed-write-id",
        dest="remaining_governed_write_ids",
        action="append",
        default=[],
        help="Governed source write still open; blocks full completion admission",
    )
    parser.add_argument(
        "--openspec-unarchived",
        action="store_true",
        help="Declare that an OpenSpec change remains unarchived; blocks final admission",
    )
    parser.add_argument(
        "--external-roots-unsynced",
        action="store_true",
        help="Declare formal/shadow/installed roots unsynchronized; blocks final admission",
    )
    parser.add_argument(
        "--reverse-input-unaccepted",
        action="store_true",
        help="Declare reverse semantic input unaccepted; blocks final admission",
    )
    parser.add_argument(
        "--owner-dag-not-frozen",
        action="store_true",
        help="Declare owner DAG not frozen; blocks final admission",
    )
    parser.add_argument("--json", action="store_true", help="Print stable machine-readable JSON")
    parser.add_argument("--full", action="store_true", help="Expand human summary; result semantics do not change")
    return parser


def _command_error(status: str, message: str, *, scope: str) -> ValidationResult:
    field = "blockers" if status == VALIDATION_STATUS_INVALID_INPUT else "failures"
    return ValidationResult(
        command="check-flowguard-skill-suite",
        status=status,
        scope=scope,
        counts={"passed": 0, "required": len(FULL_CHILD_IDS) if scope == "full" else 0, "total": 0},
        blockers=(message,) if field == "blockers" else (),
        failures=(message,) if field == "failures" else (),
        claim_boundary="Validation did not execute because command setup was not valid or could not be initialized.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.scope in {"light", "affected"}:
        from flowguard.execution_profiles import select_execution_profile

        # Read/validate the machine impact plan before profile admission, but
        # do not execute its owners until the single typed profile decision is
        # admitted.  This keeps a malformed or contradictory request at zero
        # producer work and prevents the old "run, then label" behaviour.
        impact_plan = None
        impact_error = ""
        if args.scope == "affected":
            from flowguard.affected_blueprint_reader import AffectedBlueprintReadError, AffectedImpactPlan

            if not args.impact_plan:
                impact_error = "--scope affected requires a current --impact-plan receipt; it never falls back to light or full"
            else:
                try:
                    impact_path = Path(args.impact_plan).expanduser().resolve()
                    impact_payload = json.loads(impact_path.read_text(encoding="utf-8"))
                    impact_plan = AffectedImpactPlan.from_dict(impact_payload)
                except (AffectedBlueprintReadError, OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    impact_error = f"affected impact plan invalid: {type(exc).__name__}: {exc}"

        operation_kind = args.operation_kind or (
            "read_only" if args.scope == "light" else "change"
        )
        changed_paths = tuple(
            ((impact_plan.to_dict().get("changed_paths") or ()) if impact_plan is not None else ())
            if args.scope == "affected"
            else (getattr(args, "changed_path", ()) or ())
        )
        profile_decision = select_execution_profile(
            args.scope,
            operation_kind=operation_kind,
            modeling_mode=("read_only_audit" if args.scope == "light" else "model_first_change"),
            changed_paths=changed_paths,
        )

        if impact_error:
            payload = (
                _affected_blocked_payload(reason=impact_error, impact_plan=impact_plan)
                if args.scope == "affected"
                else {
                    "artifact_type": "flowguard_skill_suite_certification",
                    "ok": False,
                    "status": "blocked",
                    "scope": "light",
                    "requested_members": [],
                    "passed_members": 0,
                    "total_members": 0,
                    "inventory": {},
                    "compiler": {},
                    "inventory_hash": "",
                    "semantic_hash": "",
                    "members": [],
                    "blockers": [impact_error],
                    "checks_run": [],
                    "checks_not_run": ["light_currentness"],
                    "skipped_checks": [],
                    "claim_boundary": "Light profile was not admitted; no currentness producer ran.",
                }
            )
        elif not profile_decision.ok:
            reason = "execution profile admission blocked: " + ", ".join(
                profile_decision.escalation_triggers
            )
            payload = (
                _affected_blocked_payload(reason=reason, impact_plan=impact_plan)
                if args.scope == "affected"
                else {
                    "artifact_type": "flowguard_skill_suite_certification",
                    "ok": False,
                    "status": "blocked",
                    "scope": "light",
                    "requested_members": [],
                    "passed_members": 0,
                    "total_members": 0,
                    "inventory": {},
                    "compiler": {},
                    "inventory_hash": "",
                    "semantic_hash": "",
                    "members": [],
                    "blockers": [reason],
                    "checks_run": [],
                    "checks_not_run": ["light_currentness"],
                    "skipped_checks": [],
                    "claim_boundary": "Light profile was not admitted; no currentness producer ran.",
                }
            )
        elif args.scope == "affected":
            payload = run_affected_suite(
                Path(args.root).resolve(),
                impact_plan=impact_plan,
                skillguard=args.skillguard,
                members=args.member,
            )
        else:
            payload = run_light_suite(
                Path(args.root).resolve(),
                skillguard=args.skillguard,
                members=args.member,
                installed_root=args.installed_root,
                operation_budget=args.light_operation_budget,
                time_budget_seconds=args.light_time_budget,
                allow_cache_write=args.allow_light_cache_write,
            )

        payload["scope"] = args.scope
        payload.setdefault(
            "claim_boundary",
            "Light/affected contract checks never claim full model, receipt, installation, or release currentness; "
            "affected selection is exact and has no run-all fallback.",
        )
        # Keep producer status/ok authoritative.  A profile decision describes
        # admission and claim depth; it must never turn a failed producer into
        # a pass merely because the selected entry profile itself was valid.
        profile_payload = profile_decision.to_dict()
        payload["execution_profile"] = profile_payload["execution_profile"]
        payload["modeling_mode"] = profile_payload["modeling_mode"]
        payload["selection_reason"] = profile_payload["selection_reason"]
        payload["closed_obligations"] = profile_payload["closed_obligations"]
        payload["not_run_obligations"] = profile_payload["not_run_obligations"]
        payload["escalation_triggers"] = profile_payload["escalation_triggers"]
        payload["execution_profile_decision"] = profile_payload
        payload["execution_profile_claim_boundary"] = profile_payload["claim_boundary"]
        payload["execution_profile_admitted"] = profile_decision.admitted
        payload["execution_profile_status"] = profile_decision.status
        payload["execution_profile_ok"] = profile_decision.ok
        # A machine impact plan is the source of truth for affected selection;
        # profile admission is diagnostic and cannot widen or shrink it.
        if args.output_dir or args.scope == "affected" or args.authority_kind == "child":
            run_id, result_path, result_sha256 = _write_light_result(
                payload,
                args.output_dir,
                authority_kind=args.authority_kind,
                parent_scope=args.parent_scope,
            )
        else:
            # Routine light is a stdout-only currentness read.  It must not
            # create a run directory, lease, CURRENT pointer, or receipt.
            run_id = result_path = result_sha256 = ""
        _print_light(
            payload,
            as_json=args.json,
            run_id=run_id,
            result_path=result_path,
            result_sha256=result_sha256,
        )
        return 0 if payload["ok"] else 1
    invalid_reason = ""
    if args.model_jobs < 1:
        invalid_reason = "--model-jobs must be at least 1"
    elif args.model_timeout is not None and args.model_timeout <= 0:
        invalid_reason = "--model-timeout must be positive"
    elif args.member:
        invalid_reason = "--member is light/affected-only; full scope always requires all declared members"
    elif args.authority_kind != "standalone" or args.parent_scope:
        invalid_reason = "--authority-kind and --parent-scope are light/affected-only"
    if invalid_reason:
        result = _command_error(VALIDATION_STATUS_INVALID_INPUT, invalid_reason, scope="full")
        print(
            result.terminal_json_text()
            if args.json
            else result.format_text(full=args.full)
        )
        return result.exit_code
    # Full is the qualification profile.  Admit the typed operation before
    # constructing the owner observation or acquiring any completion lease;
    # an ordinary change or read-only audit must use its matching shallower
    # profile and can never silently escalate into the full producer graph.
    from flowguard.execution_profiles import (
        EXECUTION_PROFILE_FULL,
        OPERATION_KIND_QUALIFICATION,
        select_execution_profile,
    )

    full_profile_decision = select_execution_profile(
        EXECUTION_PROFILE_FULL,
        operation_kind=args.operation_kind or OPERATION_KIND_QUALIFICATION,
        modeling_mode="layered_boundary_proof",
        # Readiness/epoch admission owns the actual freeze evidence.  These
        # flags only validate the profile/operation pairing here; passing them
        # avoids duplicating readiness inference before the full owner runs.
        governed_writes_frozen=True,
        projections_frozen=True,
        openspec_frozen=True,
        owner_dag_frozen=True,
        reverse_input_frozen=True,
    )
    if not full_profile_decision.ok:
        result = _command_error(
            VALIDATION_STATUS_BLOCKED,
            "execution profile admission blocked: "
            + ", ".join(full_profile_decision.escalation_triggers),
            scope="full",
        )
        print(
            result.terminal_json_text()
            if args.json
            else result.format_text(full=args.full)
        )
        return result.exit_code
    try:
        result = (
            run_local_functional_validation(args)
            if args.claim_scope == COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION
            else run_full_validation(args)
        )
    except GitQueryTimeout as exc:
        # A bounded source observation is a typed gate failure, not an
        # internal exception and never a reason to launch a producer or fall
        # back to an unbounded filesystem walk.
        result = _command_error(
            VALIDATION_STATUS_BLOCKED,
            json.dumps(
                {
                    "code": exc.code,
                    "query_category": exc.query_category,
                    "elapsed_seconds": exc.elapsed_seconds,
                    "cleanup_confirmed": exc.cleanup_confirmed,
                    "terminal_reason": exc.terminal_reason,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            scope="full",
        )
    except (OSError, ValueError) as exc:
        result = _command_error(
            VALIDATION_STATUS_INTERNAL_ERROR,
            f"{type(exc).__name__}: {exc}",
            scope="full",
        )
    if args.json:
        result_path = Path(result.artifact_paths[0]) if result.artifact_paths else None
        result_sha256 = (
            "sha256:" + hashlib.sha256(result_path.read_bytes()).hexdigest()
            if result_path is not None and result_path.is_file()
            else ""
        )
        print(
            result.terminal_json_text(
                run_id=result_path.parent.name if result_path is not None else "",
                result_path=str(result_path) if result_path is not None else "",
                result_sha256=result_sha256,
            )
        )
    else:
        print(result.format_text(full=args.full))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
