"""Read-only, project-root-bounded adapters for specification providers."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from .behavior_plane import BCL_PLANE_DEVELOPMENT_PROCESS
from .spec_work_package import (
    SPEC_BINDING_DIRECT,
    SPEC_BINDING_INFRASTRUCTURE,
    SPEC_BINDING_SCOPED_OUT,
    SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
    SPEC_PROVIDER_MODE_NATIVE,
    SPEC_PROVIDER_OPEN_SPEC,
    SPEC_PROVIDER_SPEC_KIT,
    SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS,
    SPEC_SNAPSHOT_LIVE_SCOPED,
    SpecCheckDefinition,
    SpecObligation,
    SpecProviderRef,
    SpecTask,
    SpecTaskObligationBinding,
    SpecWorkPackage,
)


DEFAULT_SPEC_BINDINGS_PATH = Path(".flowguard/spec_provider_work_packages/bindings.json")

PROVIDER_SOURCE_HASH_PROTOCOL_V2 = "openspec-verification-report.v2"
PROVIDER_SOURCE_HASH_PROTOCOL_V3 = "openspec-verification-report.v3"
PROVIDER_SOURCE_HASH_ADAPTER_VERSION = "1.0"
PROVIDER_HASH_POLICY_RAW = "raw-sha256"
PROVIDER_HASH_POLICY_TASK_DEFINITION = "provider-task-definition-v1"

_OPEN_SPEC_TASK = re.compile(r"^\s*-\s*\[([ xX])\]\s+([0-9]+(?:\.[0-9]+)+)\s+(.+?)\s*$")
_SPEC_KIT_TASK = re.compile(r"^\s*-\s*\[([ xX])\]\s+(T[0-9]+)\s+(.+?)\s*$")


class SpecProviderError(ValueError):
    """Raised when provider artifacts are unavailable, malformed, or unbounded."""


@lru_cache(maxsize=4)
def _provider_version(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        return "unavailable"
    try:
        completed = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (completed.stdout or completed.stderr).strip()[:120] or "unknown"


def _root(root: str | Path) -> Path:
    candidate = Path(root).expanduser().resolve()
    if not candidate.is_dir():
        raise SpecProviderError(f"project root does not exist: {candidate}")
    return candidate


def _bounded(root: Path, path: str | Path, *, must_exist: bool = True) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.expanduser().resolve(strict=must_exist)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SpecProviderError("spec provider path escapes the project root") from exc
    return resolved


def _token(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecProviderError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise SpecProviderError(f"{path.name} must contain a JSON object")
    return value


def _read_yaml_object(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SpecProviderError(
            "OpenSpec verification-contract parsing requires the optional 'spec-providers' dependency (PyYAML)."
        ) from exc
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SpecProviderError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise SpecProviderError(f"{path.name} must contain a YAML object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_provider_task_definition_bytes(data: bytes) -> bytes:
    """Mirror OpenSpec markdown-checkbox-state-v1 byte semantics exactly."""

    text = data.decode("utf-8")
    normalized = re.sub(
        r"(?m)^(\s*-\s+\[)[ xX](\]\s+)",
        r"\1 \2",
        text,
    )
    return normalized.encode("utf-8")


def provider_source_sha256(path: Path, hash_policy: str) -> str:
    data = path.read_bytes()
    if hash_policy == PROVIDER_HASH_POLICY_RAW:
        payload = data
    elif hash_policy == PROVIDER_HASH_POLICY_TASK_DEFINITION:
        payload = normalize_provider_task_definition_bytes(data)
    else:
        raise SpecProviderError(f"unsupported provider source hash policy: {hash_policy}")
    return hashlib.sha256(payload).hexdigest()


def _task_rows(path: Path, pattern: re.Pattern[str], root: Path) -> tuple[SpecTask, ...]:
    tasks: list[SpecTask] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = pattern.match(line)
        if match is None:
            continue
        completed, task_id, title = match.groups()
        metadata: dict[str, Any] = {"line": line_number}
        if pattern is _SPEC_KIT_TASK:
            parallel = "[P]" in title
            story = re.search(r"\[(US[0-9]+)\]", title)
            metadata.update({"parallel": parallel, "user_story_id": story.group(1) if story else ""})
        tasks.append(
            SpecTask(
                task_id=task_id,
                title=title,
                completed=completed.casefold() == "x",
                source_ref=f"{_token(root, path)}:{line_number}",
                metadata=metadata,
            )
        )
    if not tasks:
        raise SpecProviderError(f"no provider tasks were discovered in {_token(root, path)}")
    return tuple(tasks)


def _binding_config(root: Path, provider_id: str, work_package_id: str, path: str | Path | None) -> dict[str, Any]:
    config_path = _bounded(root, path or DEFAULT_SPEC_BINDINGS_PATH, must_exist=False)
    if not config_path.is_file():
        return {}
    data = _read_json_object(config_path)
    for row in data.get("packages", ()):
        if not isinstance(row, Mapping):
            continue
        if str(row.get("provider_id", "")) == provider_id and str(row.get("work_package_id", "")) == work_package_id:
            return dict(row)
    return {}


def _expand_bindings(
    tasks: Sequence[SpecTask],
    obligations: Sequence[SpecObligation],
    checks: Sequence[SpecCheckDefinition],
    config: Mapping[str, Any],
) -> tuple[SpecTaskObligationBinding, ...]:
    obligation_checks = {item.obligation_id: set(item.check_ids) for item in obligations}
    rows: list[SpecTaskObligationBinding] = []
    matched_tasks: set[str] = set()
    for index, raw_rule in enumerate(config.get("task_binding_rules", ())):
        if not isinstance(raw_rule, Mapping):
            continue
        exact = {str(value) for value in raw_rule.get("task_ids", ())}
        prefix = str(raw_rule.get("task_prefix", ""))
        selected = [task for task in tasks if task.task_id in exact or (prefix and task.task_id.startswith(prefix))]
        obligation_ids = tuple(str(value) for value in raw_rule.get("obligation_ids", ()))
        configured_checks = {str(value) for value in raw_rule.get("check_ids", ())}
        for obligation_id in obligation_ids:
            configured_checks.update(obligation_checks.get(obligation_id, set()))
        binding_kind = str(raw_rule.get("binding_kind", SPEC_BINDING_DIRECT))
        for task in selected:
            matched_tasks.add(task.task_id)
            rows.append(
                SpecTaskObligationBinding(
                    binding_id=f"binding:{task.task_id}:{index + 1}",
                    task_ids=(task.task_id,),
                    obligation_ids=obligation_ids,
                    check_ids=tuple(sorted(configured_checks)),
                    binding_kind=binding_kind,
                    owner_id=str(raw_rule.get("owner_id", "")),
                    reason=str(raw_rule.get("reason", "")),
                )
            )
    for index, raw_rule in enumerate(config.get("infrastructure_bindings", ())):
        if not isinstance(raw_rule, Mapping):
            continue
        obligation_ids = tuple(str(value) for value in raw_rule.get("obligation_ids", ()))
        configured_checks = {str(value) for value in raw_rule.get("check_ids", ())}
        for obligation_id in obligation_ids:
            configured_checks.update(obligation_checks.get(obligation_id, set()))
        rows.append(
            SpecTaskObligationBinding(
                binding_id=str(raw_rule.get("binding_id", f"infrastructure:{index + 1}")),
                task_ids=tuple(str(value) for value in raw_rule.get("task_ids", ())),
                obligation_ids=obligation_ids,
                check_ids=tuple(sorted(configured_checks)),
                binding_kind=str(raw_rule.get("binding_kind", SPEC_BINDING_INFRASTRUCTURE)),
                owner_id=str(raw_rule.get("owner_id", "")),
                reason=str(raw_rule.get("reason", "")),
            )
        )
    # An explicit default rule is useful for provider-administrative tasks, but
    # never silently scopes a task out.
    default = config.get("unmatched_task_binding")
    if isinstance(default, Mapping):
        for task in tasks:
            if task.task_id in matched_tasks:
                continue
            rows.append(
                SpecTaskObligationBinding(
                    binding_id=f"binding:{task.task_id}:default",
                    task_ids=(task.task_id,),
                    obligation_ids=tuple(str(value) for value in default.get("obligation_ids", ())),
                    check_ids=tuple(str(value) for value in default.get("check_ids", ())),
                    binding_kind=str(default.get("binding_kind", SPEC_BINDING_SCOPED_OUT)),
                    owner_id=str(default.get("owner_id", "")),
                    reason=str(default.get("reason", "")),
                )
            )
    return tuple(rows)


def _provider_report_state(
    project_root: Path,
    change_root: Path,
    contract_path: Path,
) -> tuple[bool, bool, str, dict[str, Any]]:
    report_path = change_root / "verification-report.json"
    if not report_path.is_file():
        return False, False, "not_run", {"report_available": False, "report_current": False}
    try:
        report = _read_json_object(report_path)
    except SpecProviderError:
        return False, False, "invalid_report", {"report_available": True, "report_current": False}
    status = str(report.get("status", report.get("result", "unknown"))).casefold()
    freshness = report.get("freshness", {})
    declared_stale = bool(report.get("stale", False)) or (
        bool(freshness.get("changed")) if isinstance(freshness, Mapping) else False
    )
    legacy_wire_detected = any(
        key in report for key in ("sourceHashes", "sourceHashPolicy", "contractHash", "reportProtocolVersion")
    )
    source_hashes = report.get("source_hashes", {})
    source_hash_policy = report.get("source_hash_policy", {})
    if not isinstance(source_hash_policy, Mapping):
        source_hash_policy = {}
    expected_policy = {
        "version": 2,
        "algorithm": "sha256",
        "task_checkbox_normalization": "markdown-checkbox-state-v1",
        "output_classifier_version": "verification-generated-output-v2",
    }
    source_policy_current = all(source_hash_policy.get(key) == value for key, value in expected_policy.items())
    run = report.get("run", {})
    if not isinstance(run, Mapping):
        run = {}
    report_protocol_version = report.get("report_protocol_version")
    run_protocol_version = run.get("protocol_version")
    protocol_family = "v3" if report_protocol_version == 3 and run_protocol_version == 3 else "legacy_or_unsupported"
    protocol_current = protocol_family == "v3" and source_policy_current and not legacy_wire_detected
    adapter_current = protocol_current
    validation_mode = str(run.get("validation_mode", ""))
    snapshot_manifest_id = str(run.get("snapshot_manifest_id", ""))
    full_frozen_run = validation_mode == "full" and bool(
        re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot_manifest_id)
    )
    mismatched_paths: list[str] = []
    missing_paths: list[str] = []
    unsafe_paths: list[str] = []
    source_hashes_present = isinstance(source_hashes, Mapping) and bool(source_hashes)
    if isinstance(source_hashes, Mapping):
        for raw_path, expected_value in source_hashes.items():
            path_token = str(raw_path).replace("\\", "/")
            candidate = (project_root / path_token).resolve()
            try:
                candidate.relative_to(project_root)
            except ValueError:
                unsafe_paths.append(path_token)
                continue
            if not candidate.is_file():
                missing_paths.append(path_token)
                continue
            if isinstance(expected_value, Mapping):
                expected_hash = expected_value.get("sha256", expected_value.get("hash", ""))
            else:
                expected_hash = expected_value
            hash_policy = (
                PROVIDER_HASH_POLICY_TASK_DEFINITION
                if candidate.name.casefold() == "tasks.md"
                else PROVIDER_HASH_POLICY_RAW
            )
            if not source_policy_current:
                mismatched_paths.append(path_token)
                continue
            expected_token = str(expected_hash)
            if re.fullmatch(r"sha256:[0-9a-f]{64}", expected_token) is None:
                mismatched_paths.append(path_token)
                continue
            expected = expected_token.removeprefix("sha256:")
            try:
                observed = provider_source_sha256(candidate, hash_policy)
            except SpecProviderError:
                mismatched_paths.append(path_token)
                continue
            if observed.casefold() != expected:
                mismatched_paths.append(path_token)
    recorded_contract_hash = str(report.get("contract_hash", ""))
    contract_hash_current = bool(re.fullmatch(r"sha256:[0-9a-f]{64}", recorded_contract_hash)) and (
        _sha256_file(contract_path) == recorded_contract_hash.removeprefix("sha256:")
    )
    check_rows = report.get("checks", report.get("check_results", ()))
    if isinstance(check_rows, Mapping):
        normalized_rows = {
            str(check_id): row if isinstance(row, Mapping) else {}
            for check_id, row in check_rows.items()
        }
    elif isinstance(check_rows, Sequence) and not isinstance(check_rows, (str, bytes)):
        normalized_rows = {
            str(row.get("id", row.get("check_id", ""))): row
            for row in check_rows
            if isinstance(row, Mapping) and str(row.get("id", row.get("check_id", "")))
        }
    else:
        normalized_rows = {}
    report_check_ids = tuple(sorted(normalized_rows))
    try:
        contract = _read_yaml_object(contract_path)
    except SpecProviderError:
        contract = {}
    declared_checks = {
        str(row.get("id", "")): row
        for row in contract.get("checks", ())
        if isinstance(row, Mapping) and str(row.get("id", ""))
    }
    required_check_ids = tuple(
        sorted(check_id for check_id, row in declared_checks.items() if bool(row.get("required", True)))
    )
    check_failures: list[str] = []
    for check_id in required_check_ids:
        row = normalized_rows.get(check_id)
        declaration = declared_checks[check_id]
        if not isinstance(row, Mapping):
            check_failures.append(f"required_check_missing:{check_id}")
            continue
        row_status = str(row.get("status", row.get("result", ""))).casefold()
        if row_status not in {"pass", "passed", "ok", "success"}:
            check_failures.append(f"required_check_not_passed:{check_id}")
        receipt_projection = isinstance(declaration.get("receipt_ref"), Mapping)
        required_fields = {
            "semantic_check_id": row.get("semantic_check_id"),
            "execution_key": row.get("execution_key"),
            "receipt_id": row.get("receipt_id"),
            "result_hash": row.get("result_hash"),
            "toolchain_identity": row.get("toolchain_identity"),
            "accounting": row.get("accounting"),
        }
        if receipt_projection:
            required_fields.update(
                {
                    "execution_owner": row.get("execution_owner"),
                    "depends_on_receipt_ids": row.get("depends_on_receipt_ids"),
                }
            )
        else:
            required_fields.update(
                {
                    "execution_id": row.get("execution_id"),
                    "input_hashes": row.get("input_hashes"),
                    "portable_receipt_ref": row.get("portable_receipt_ref"),
                    "envelope_fingerprint": row.get("envelope_fingerprint"),
                    "source_manifest_id": row.get("source_manifest_id"),
                    "source_manifest_hash": row.get("source_manifest_hash"),
                }
            )
        for field_name, value in required_fields.items():
            if value in (None, "", {}, []):
                check_failures.append(f"required_check_field_missing:{check_id}:{field_name}")
        digest_fields = ["execution_key", "receipt_id", "result_hash"]
        if not receipt_projection:
            digest_fields.extend(["envelope_fingerprint", "source_manifest_id", "source_manifest_hash"])
        for digest_field in digest_fields:
            if re.fullmatch(r"sha256:[0-9a-f]{64}", str(row.get(digest_field, ""))) is None:
                check_failures.append(f"required_check_digest_noncanonical:{check_id}:{digest_field}")
        if receipt_projection:
            dependencies = row.get("depends_on_receipt_ids", ())
            if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)) or any(
                re.fullmatch(r"sha256:[0-9a-f]{64}", str(value)) is None
                for value in dependencies
            ):
                check_failures.append(f"required_check_receipt_dependencies_invalid:{check_id}")
            if row.get("accounting") != "aggregated":
                check_failures.append(f"required_check_receipt_accounting_invalid:{check_id}")
        if row.get("snapshot_policy") != "frozen":
            check_failures.append(f"required_check_snapshot_policy_not_frozen:{check_id}")
        if row.get("snapshot_manifest_id") != snapshot_manifest_id:
            check_failures.append(f"required_check_snapshot_manifest_mismatch:{check_id}")
        if row.get("source_hash_policy") != source_hash_policy:
            check_failures.append(f"required_check_source_hash_policy_mismatch:{check_id}")
        if not isinstance(declaration.get("receipt_ref"), Mapping):
            for report_field, contract_field in (
                ("semantic_check_id", "semantic_check_id"),
                ("execution_id", "execution_id"),
                ("toolchain_identity", "toolchain_identity"),
            ):
                declared_value = declaration.get(contract_field)
                if declared_value and row.get(report_field) != declared_value:
                    check_failures.append(f"required_check_declaration_mismatch:{check_id}:{report_field}")
    report_current = bool(
        not declared_stale
        and source_hashes_present
        and protocol_current
        and adapter_current
        and full_frozen_run
        and not mismatched_paths
        and not missing_paths
        and not unsafe_paths
        and contract_hash_current
        and not check_failures
    )
    passed = status in {"pass", "passed", "ok", "success"} and report_current
    return passed, passed, status, {
        "report_available": True,
        "report_current": report_current,
        "report_source_hashes_present": source_hashes_present,
        "report_protocol_version": run_protocol_version,
        "report_protocol_family": protocol_family,
        "report_legacy_wire_detected": legacy_wire_detected,
        "report_validation_mode": validation_mode,
        "report_snapshot_manifest_id": snapshot_manifest_id,
        "report_full_frozen_run": full_frozen_run,
        "report_source_hash_policy": dict(source_hash_policy),
        "report_source_hash_protocol_current": protocol_current,
        "report_source_hash_adapter_version": PROVIDER_SOURCE_HASH_ADAPTER_VERSION,
        "report_source_hash_adapter_current": adapter_current,
        "report_source_hashes_verified": source_hashes_present and not (
            mismatched_paths or missing_paths or unsafe_paths
        ),
        "report_source_hash_mismatches": sorted(mismatched_paths),
        "report_source_hash_missing": sorted(missing_paths),
        "report_source_hash_unsafe": sorted(unsafe_paths),
        "report_contract_hash_current": contract_hash_current,
        "report_check_ids": report_check_ids,
        "report_check_rows": {check_id: dict(row) for check_id, row in normalized_rows.items()},
        "report_required_check_ids": list(required_check_ids),
        "report_check_failures": check_failures,
    }


def _canonical_check_definitions(config: Mapping[str, Any]) -> tuple[SpecCheckDefinition, ...]:
    checks: list[SpecCheckDefinition] = []
    for row in config.get("canonical_checks", ()):
        if not isinstance(row, Mapping):
            continue
        check_id = str(row.get("check_id", ""))
        command = tuple(str(value) for value in row.get("command", ()))
        execution_mode = str(row.get("execution_mode", "direct"))
        if not check_id:
            raise SpecProviderError("canonical FlowGuard check_id is required")
        if execution_mode == "direct" and not command:
            raise SpecProviderError(f"canonical FlowGuard owner command is missing: {check_id}")
        input_paths = tuple(str(value) for value in row.get("input_paths", ()))
        if bool(row.get("cross_change_safe", False)):
            provider_lifecycle_inputs = tuple(
                value
                for value in input_paths
                if value.replace("\\", "/").lstrip("./").startswith(
                    ("openspec/changes/", "openspec/specs/")
                )
            )
            if provider_lifecycle_inputs:
                raise SpecProviderError(
                    "cross-change-safe owner cannot consume provider lifecycle inputs: "
                    f"{check_id}:" + ",".join(provider_lifecycle_inputs)
                )
        checks.append(
            SpecCheckDefinition(
                check_id=check_id,
                command=command,
                required=bool(row.get("required", True)),
                obligation_ids=tuple(str(value) for value in row.get("covers", ())),
                validation_obligation_ids=tuple(str(value) for value in row.get("validation_obligation_ids", ())),
                depends_on=tuple(str(value) for value in row.get("depends_on", ())),
                timeout_seconds=int(row.get("timeout_seconds", 600)),
                cross_change_safe=bool(row.get("cross_change_safe", False)),
                expected_exit_code=int(row.get("expected_exit_code", 0)),
                semantic_check_id=str(row.get("semantic_check_id", check_id)),
                execution_owner_id="flowguard.spec_check_cache",
                input_paths=input_paths,
                dependency_input_ids=tuple(
                    str(value) for value in row.get("dependency_input_ids", ())
                ),
                snapshot_policy=str(row.get("snapshot_policy", "frozen-required")),
                execution_mode=execution_mode,
                parent_check_id=str(row.get("parent_check_id", "")),
                child_check_ids=tuple(str(value) for value in row.get("child_check_ids", ())),
                coverage_ids=tuple(str(value) for value in row.get("coverage_ids", ())),
                kind="command",
                declared_execution_id=str(row.get("execution_id", "")),
                validation_scope=str(row.get("validation_scope", "focused")),
                toolchain_identity=str(row.get("toolchain_identity", "flowguard-python-v1")),
            )
        )
    return tuple(checks)


def _bind_canonical_checks_to_contract(
    canonical_checks: Sequence[SpecCheckDefinition],
    raw_checks: Sequence[Mapping[str, Any]],
) -> tuple[SpecCheckDefinition, ...]:
    # A receipt-only provider contract may consume an owner receipt produced by
    # another tool without assigning FlowGuard a second execution owner.  In
    # that case the package can still carry task/obligation bindings while
    # intentionally declaring no canonical FlowGuard checks.  Once any
    # canonical owner is declared, however, the exact-set check below remains
    # fail-closed so partial ownership cannot be hidden.
    if not canonical_checks:
        return ()
    external_rows = {
        str(row.get("id", "")): row
        for row in raw_checks
        if row.get("kind") == "receipt" and isinstance(row.get("receipt_ref"), Mapping)
    }
    canonical_ids = {check.check_id for check in canonical_checks}
    if set(external_rows) != canonical_ids:
        raise SpecProviderError(
            "canonical FlowGuard owners must exactly match OpenSpec external receipt rows"
        )
    projected: list[SpecCheckDefinition] = []
    for check in canonical_checks:
        row = external_rows[check.check_id]
        semantic_check_id = str(row.get("semantic_check_id", ""))
        if semantic_check_id != check.semantic_check_id:
            raise SpecProviderError(
                f"canonical owner semantic_check_id mismatch: {check.check_id}"
            )
        if str(row.get("execution_id", "")) != check.execution_id:
            raise SpecProviderError(
                f"canonical owner execution_id mismatch: {check.check_id}"
            )
        covers = tuple(str(value) for value in row.get("covers", ()))
        if not covers:
            raise SpecProviderError(f"external receipt covers are required: {check.check_id}")
        projected.append(replace(check, obligation_ids=covers, coverage_ids=covers))
    projected_by_id = {check.check_id: check for check in projected}
    for check in projected:
        if check.execution_mode != SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS:
            continue
        unknown_children = tuple(
            child_id for child_id in check.child_check_ids if child_id not in projected_by_id
        )
        if unknown_children:
            raise SpecProviderError(
                f"aggregate check has undeclared children: {check.check_id}:"
                + ",".join(unknown_children)
            )
        child_coverage = {
            coverage_id
            for child_id in check.child_check_ids
            for coverage_id in projected_by_id[child_id].coverage_ids
        }
        uncovered = tuple(sorted(set(check.coverage_ids) - child_coverage))
        if uncovered:
            raise SpecProviderError(
                f"aggregate check coverage must be provided by declared children: {check.check_id}:"
                + ",".join(uncovered)
            )
    return tuple(projected)


def load_openspec_canonical_checks(
    root: str | Path,
    change_id: str,
    *,
    bindings_path: str | Path | None = None,
) -> tuple[SpecCheckDefinition, ...]:
    project_root = _root(root)
    config = _binding_config(project_root, SPEC_PROVIDER_OPEN_SPEC, str(change_id), bindings_path)
    contract_path = _bounded(
        project_root,
        Path("openspec/changes") / str(change_id) / "verification-contract.yaml",
    )
    contract = _read_yaml_object(contract_path)
    raw_checks = tuple(row for row in contract.get("checks", ()) if isinstance(row, Mapping))
    return _bind_canonical_checks_to_contract(_canonical_check_definitions(config), raw_checks)


def load_openspec_work_package(
    root: str | Path,
    change_id: str,
    *,
    bindings_path: str | Path | None = None,
) -> SpecWorkPackage:
    """Load one OpenSpec change without mutating provider state."""

    project_root = _root(root)
    change_name = str(change_id).strip()
    if not change_name or "/" in change_name or "\\" in change_name or change_name in {".", ".."}:
        raise SpecProviderError("OpenSpec change id is unsafe")
    change_root = _bounded(project_root, Path("openspec/changes") / change_name)
    if "archive" in {part.casefold() for part in change_root.parts}:
        raise SpecProviderError("archived OpenSpec changes are not active work packages")
    tasks_path = _bounded(project_root, change_root / "tasks.md")
    contract_path = _bounded(project_root, change_root / "verification-contract.yaml")
    tasks = _task_rows(tasks_path, _OPEN_SPEC_TASK, project_root)
    contract = _read_yaml_object(contract_path)
    raw_obligations = [row for row in contract.get("obligations", ()) if isinstance(row, Mapping)]
    raw_checks = [row for row in contract.get("checks", ()) if isinstance(row, Mapping)]
    check_covers = {
        str(row.get("id", "")): tuple(str(value) for value in row.get("covers", ()))
        for row in raw_checks
    }
    config = _binding_config(project_root, SPEC_PROVIDER_OPEN_SPEC, change_name, bindings_path)
    check_policies = {
        str(row.get("check_id", "")): dict(row)
        for row in config.get("check_policies", ())
        if isinstance(row, Mapping)
    }
    obligations = tuple(
        SpecObligation(
            obligation_id=str(row.get("id", "")),
            source_ref=str(row.get("source", "")),
            claim=str(row.get("claim", "")),
            required=bool(row.get("required", True)),
            check_ids=tuple(str(value) for value in row.get("evidence", ())),
            flowguard_obligation_ids=tuple(
                str(value)
                for value in config.get("flowguard_obligation_map", {}).get(str(row.get("id", "")), ())
            ),
        )
        for row in raw_obligations
    )
    checks: list[SpecCheckDefinition] = []
    for row in raw_checks:
        check_id = str(row.get("id", ""))
        policy = check_policies.get(check_id, {})
        input_scope = row.get("input_scope", {})
        if not isinstance(input_scope, Mapping):
            input_scope = {}
        policy_input_scope = policy.get("input_scope", {})
        if isinstance(policy_input_scope, Mapping):
            input_scope = {**dict(input_scope), **dict(policy_input_scope)}
        kind = str(row.get("kind", ""))
        command_name = str(row.get("command", ""))
        command = (
            (command_name,) + tuple(str(value) for value in row.get("args", ()))
            if command_name
            else ()
        )
        default_execution_owner = (
            "openspec.verification"
            if "spec-receipt-consume" in command
            else "flowguard.spec_check_cache"
        )
        expected = row.get("expected", {})
        expected_exit = int(expected.get("exit_code", 0)) if isinstance(expected, Mapping) else 0
        validation_ids = tuple(str(value) for value in policy.get("validation_obligation_ids", ()))
        if not validation_ids:
            validation_ids = (f"validation:spec-check:{check_id}",)
        checks.append(
            SpecCheckDefinition(
                check_id=check_id,
                command=command,
                required=bool(row.get("required", True)),
                obligation_ids=check_covers.get(check_id, ()),
                validation_obligation_ids=validation_ids,
                depends_on=tuple(
                    str(value)
                    for value in policy.get("depends_on", row.get("depends_on_receipts", ()))
                ),
                timeout_seconds=int(policy.get("timeout_seconds", row.get("timeout_seconds", 600) or 600)),
                cross_change_safe=bool(policy.get("cross_change_safe", False)),
                expected_exit_code=expected_exit,
                semantic_check_id=str(
                    policy.get("semantic_check_id", row.get("semantic_check_id", row.get("execution_id", check_id)))
                ),
                execution_owner_id=str(
                    policy.get(
                        "execution_owner_id",
                        row.get("execution_owner_id", default_execution_owner),
                    )
                ),
                input_paths=tuple(
                    str(value)
                    for value in input_scope.get(
                        "paths", policy.get("input_paths", row.get("input_selectors", row.get("input_paths", ())))
                    )
                ),
                dependency_input_ids=tuple(
                    str(value)
                    for value in input_scope.get(
                        "dependency_ids",
                        policy.get("dependency_input_ids", ()),
                    )
                ),
                snapshot_policy=str(
                    input_scope.get(
                        "snapshot_policy",
                        policy.get("snapshot_policy", row.get("snapshot_policy", "live-scoped")),
                    )
                ),
                execution_mode=str(policy.get("execution_mode", row.get("execution_mode", "direct"))),
                parent_check_id=str(policy.get("parent_check_id", row.get("parent_check_id", ""))),
                child_check_ids=tuple(
                    str(value)
                    for value in policy.get("child_check_ids", row.get("child_check_ids", ()))
                ),
                coverage_ids=tuple(
                    str(value) for value in policy.get("coverage_ids", row.get("coverage", ()))
                ),
                kind=kind,
                declared_execution_id=str(policy.get("execution_id", row.get("execution_id", ""))),
                receipt_owner_check_id=str(
                    policy.get("execution_owner", row.get("execution_owner", ""))
                ),
                external_receipt_ref=(
                    row.get("receipt_ref", {})
                    if isinstance(row.get("receipt_ref", {}), Mapping)
                    else {}
                ),
                consumer_ids=(
                    (str(policy.get("consumer", row.get("consumer", ""))),)
                    if str(policy.get("consumer", row.get("consumer", "")))
                    else ()
                ),
                validation_scope=str(
                    policy.get("validation_scope", row.get("validation_scope", "full"))
                ),
                toolchain_identity=str(
                    policy.get("toolchain_identity", row.get("toolchain_identity", ""))
                ),
            )
        )
    canonical_checks = _bind_canonical_checks_to_contract(
        _canonical_check_definitions(config), raw_checks
    )
    verified, archive_ready, provider_status, report_metadata = _provider_report_state(
        project_root, change_root, contract_path
    )
    provider = SpecProviderRef(
        provider_id=SPEC_PROVIDER_OPEN_SPEC,
        root_token="openspec",
        mode=SPEC_PROVIDER_MODE_NATIVE if shutil.which("openspec") else SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
        provider_version=_provider_version("openspec"),
        schema_version=str(contract.get("contract_version", "")),
        diagnostics=() if shutil.which("openspec") else ("openspec_cli_unavailable_artifact_only",),
    )
    bindings = _expand_bindings(tasks, obligations, checks, config)
    return SpecWorkPackage(
        provider=provider,
        work_package_id=change_name,
        change_id=change_name,
        behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        tasks=tasks,
        obligations=obligations,
        checks=tuple(checks),
        bindings=bindings,
        artifact_refs=(
            _token(project_root, tasks_path),
            _token(project_root, contract_path),
        ),
        provider_status=provider_status,
        provider_verified=verified,
        provider_archive_ready=archive_ready,
        target_commitment_ids=tuple(str(value) for value in config.get("target_commitment_ids", ())),
        typed_relation_ids=tuple(str(value) for value in config.get("typed_relation_ids", ())),
        metadata={
            "binding_source": str(DEFAULT_SPEC_BINDINGS_PATH).replace("\\", "/") if config else "",
            "provider_contract_version": contract.get("contract_version", ""),
            "required_obligation_count": sum(1 for item in obligations if item.required),
            "required_check_count": sum(1 for item in checks if item.required),
            "canonical_check_ids": [item.check_id for item in canonical_checks],
            "canonical_check_semantics": {
                item.check_id: item.semantic_check_id for item in canonical_checks
            },
            "provider_report_path": _token(project_root, change_root / "verification-report.json")
            if (change_root / "verification-report.json").is_file()
            else "",
            **report_metadata,
        },
    )


def load_speckit_work_package(
    root: str | Path,
    feature_id: str,
    *,
    bindings_path: str | Path | None = None,
) -> SpecWorkPackage:
    """Load a Spec Kit artifact set; CLI absence is an explicit artifact-only mode."""

    project_root = _root(root)
    marker = _bounded(project_root, ".specify")
    if not marker.is_dir():
        raise SpecProviderError("Spec Kit marker .specify is unavailable")
    feature_name = str(feature_id).strip()
    if not feature_name or "/" in feature_name or "\\" in feature_name or feature_name in {".", ".."}:
        raise SpecProviderError("Spec Kit feature id is unsafe")
    feature_root = _bounded(project_root, Path("specs") / feature_name)
    tasks_path = _bounded(project_root, feature_root / "tasks.md")
    tasks = _task_rows(tasks_path, _SPEC_KIT_TASK, project_root)
    config = _binding_config(project_root, SPEC_PROVIDER_SPEC_KIT, feature_name, bindings_path)
    obligations = tuple(
        SpecObligation(
            obligation_id=str(row.get("obligation_id", "")),
            source_ref=str(row.get("source_ref", "")),
            claim=str(row.get("claim", "")),
            required=bool(row.get("required", True)),
            check_ids=tuple(str(value) for value in row.get("check_ids", ())),
            flowguard_obligation_ids=tuple(str(value) for value in row.get("flowguard_obligation_ids", ())),
        )
        for row in config.get("obligations", ())
        if isinstance(row, Mapping)
    )
    checks = tuple(
        SpecCheckDefinition(
            check_id=str(row.get("check_id", "")),
            command=tuple(str(value) for value in row.get("command", ())),
            required=bool(row.get("required", True)),
            obligation_ids=tuple(str(value) for value in row.get("obligation_ids", ())),
            validation_obligation_ids=tuple(str(value) for value in row.get("validation_obligation_ids", ())),
            depends_on=tuple(str(value) for value in row.get("depends_on", ())),
            timeout_seconds=int(row.get("timeout_seconds", 600)),
            cross_change_safe=bool(row.get("cross_change_safe", False)),
            expected_exit_code=int(row.get("expected_exit_code", 0)),
            semantic_check_id=str(row.get("semantic_check_id", row.get("check_id", ""))),
            execution_owner_id=str(row.get("execution_owner_id", "flowguard.spec_check_cache")),
            input_paths=tuple(str(value) for value in row.get("input_paths", ())),
            dependency_input_ids=tuple(str(value) for value in row.get("dependency_input_ids", ())),
            snapshot_policy=str(row.get("snapshot_policy", SPEC_SNAPSHOT_LIVE_SCOPED)),
            execution_mode=str(row.get("execution_mode", "direct")),
            parent_check_id=str(row.get("parent_check_id", "")),
            child_check_ids=tuple(str(value) for value in row.get("child_check_ids", ())),
            coverage_ids=tuple(str(value) for value in row.get("coverage_ids", ())),
        )
        for row in config.get("checks", ())
        if isinstance(row, Mapping)
    )
    provider = SpecProviderRef(
        provider_id=SPEC_PROVIDER_SPEC_KIT,
        root_token=".specify",
        mode=SPEC_PROVIDER_MODE_NATIVE if shutil.which("specify") else SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
        provider_version=_provider_version("specify"),
        schema_version="artifact-v1",
        diagnostics=() if shutil.which("specify") else ("speckit_cli_unavailable_artifact_only",),
    )
    checklist_paths = tuple(sorted((feature_root / "checklists").rglob("*.md"))) if (feature_root / "checklists").is_dir() else ()
    return SpecWorkPackage(
        provider=provider,
        work_package_id=feature_name,
        change_id=feature_name,
        tasks=tasks,
        obligations=obligations,
        checks=checks,
        bindings=_expand_bindings(tasks, obligations, checks, config),
        artifact_refs=tuple(
            _token(project_root, path)
            for path in (feature_root / "spec.md", feature_root / "plan.md", tasks_path, *checklist_paths)
            if path.is_file()
        ),
        provider_status="active",
        metadata={
            "speckit_workflow_runs_derived": ".specify/workflows/runs",
            "checklist_count": len(checklist_paths),
        },
    )


def discover_spec_work_packages(
    root: str | Path,
    *,
    provider_id: str = "auto",
    change_id: str = "",
    bindings_path: str | Path | None = None,
) -> tuple[SpecWorkPackage, ...]:
    """Discover active provider artifacts under exactly one project root."""

    project_root = _root(root)
    providers = (SPEC_PROVIDER_OPEN_SPEC, SPEC_PROVIDER_SPEC_KIT) if provider_id == "auto" else (provider_id,)
    packages: list[SpecWorkPackage] = []
    for provider in providers:
        if provider == SPEC_PROVIDER_OPEN_SPEC:
            changes_root = _bounded(project_root, "openspec/changes", must_exist=False)
            if not changes_root.is_dir():
                if provider_id != "auto":
                    raise SpecProviderError("OpenSpec provider artifacts are unavailable")
                continue
            names = (change_id,) if change_id else tuple(
                path.name for path in sorted(changes_root.iterdir()) if path.is_dir() and path.name != "archive"
            )
            packages.extend(
                load_openspec_work_package(project_root, name, bindings_path=bindings_path)
                for name in names
                if name
            )
        elif provider == SPEC_PROVIDER_SPEC_KIT:
            if not (project_root / ".specify").is_dir():
                if provider_id != "auto":
                    raise SpecProviderError("Spec Kit marker .specify is unavailable")
                continue
            features_root = _bounded(project_root, "specs", must_exist=False)
            names = (change_id,) if change_id else tuple(
                path.name for path in sorted(features_root.iterdir()) if path.is_dir()
            ) if features_root.is_dir() else ()
            packages.extend(
                load_speckit_work_package(project_root, name, bindings_path=bindings_path)
                for name in names
                if name
            )
        else:
            raise SpecProviderError(f"unsupported spec provider: {provider}")
    return tuple(packages)


__all__ = [
    "DEFAULT_SPEC_BINDINGS_PATH",
    "PROVIDER_HASH_POLICY_RAW",
    "PROVIDER_HASH_POLICY_TASK_DEFINITION",
    "PROVIDER_SOURCE_HASH_ADAPTER_VERSION",
    "PROVIDER_SOURCE_HASH_PROTOCOL_V2",
    "PROVIDER_SOURCE_HASH_PROTOCOL_V3",
    "SpecProviderError",
    "discover_spec_work_packages",
    "load_openspec_work_package",
    "load_openspec_canonical_checks",
    "load_speckit_work_package",
    "normalize_provider_task_definition_bytes",
    "provider_source_sha256",
]
