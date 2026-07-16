"""Read-only, project-root-bounded adapters for specification providers."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from .behavior_plane import BCL_PLANE_DEVELOPMENT_PROCESS
from .spec_work_package import (
    SPEC_BINDING_DIRECT,
    SPEC_BINDING_INFRASTRUCTURE,
    SPEC_BINDING_SCOPED_OUT,
    SPEC_ORCHESTRATOR_REUSE_EXACT,
    SPEC_ORCHESTRATOR_REUSE_NEVER,
    SPEC_CHECK_KIND_COMMAND,
    SPEC_SNAPSHOT_POLICY_FROZEN,
    SPEC_VALIDATION_SCOPE_FULL,
    SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
    SPEC_PROVIDER_MODE_NATIVE,
    SPEC_PROVIDER_OPEN_SPEC,
    SPEC_PROVIDER_SPEC_KIT,
    SpecCheckDefinition,
    SpecObligation,
    SpecProviderRef,
    SpecTask,
    SpecTaskObligationBinding,
    SpecWorkPackage,
)


DEFAULT_SPEC_BINDINGS_PATH = Path(".flowguard/spec_provider_work_packages/bindings.json")

_OPEN_SPEC_TASK = re.compile(r"^\s*-\s*\[([ xX])\]\s+([0-9]+(?:\.[0-9]+)+)\s+(.+?)\s*$")
_SPEC_KIT_TASK = re.compile(r"^\s*-\s*\[([ xX])\]\s+(T[0-9]+)\s+(.+?)\s*$")


class SpecProviderError(ValueError):
    """Raised when provider artifacts are unavailable, malformed, or unbounded."""


def _orchestrator_reuse_policy(
    command: Sequence[str],
    *,
    provider_value: object = "",
    bridge_value: object = "",
) -> str:
    """Resolve provider policy, while failing safe for FlowGuard session wrappers."""

    explicit = str(provider_value or bridge_value or "")
    if explicit:
        return explicit
    if any(
        token in {"spec-session-begin", "spec-check-run", "spec-session-close"}
        for token in command
    ):
        return SPEC_ORCHESTRATOR_REUSE_NEVER
    return SPEC_ORCHESTRATOR_REUSE_EXACT


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


def _provider_report_state(change_root: Path) -> tuple[bool, bool, str, dict[str, Any]]:
    report_path = change_root / "verification-report.json"
    if not report_path.is_file():
        return False, False, "not_run", {"report_available": False, "report_current": False}
    try:
        report = _read_json_object(report_path)
    except SpecProviderError:
        return False, False, "invalid_report", {"report_available": True, "report_current": False}
    status = str(report.get("status", report.get("result", "unknown"))).casefold()
    freshness = report.get("freshness", {})
    stale = bool(report.get("stale", False)) or (
        bool(freshness.get("changed")) if isinstance(freshness, Mapping) else False
    )
    passed = status in {"pass", "passed", "ok", "success"} and not stale
    check_rows = report.get("checks", report.get("check_results", ()))
    if isinstance(check_rows, Mapping):
        report_check_ids = tuple(sorted(str(value) for value in check_rows))
    elif isinstance(check_rows, Sequence) and not isinstance(check_rows, (str, bytes)):
        report_check_ids = tuple(
            sorted(str(row.get("id", row.get("check_id", ""))) for row in check_rows if isinstance(row, Mapping))
        )
    else:
        report_check_ids = ()
    return passed, passed, status, {
        "report_available": True,
        "report_current": not stale,
        "report_check_ids": report_check_ids,
    }


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
        command_name = str(row.get("command", ""))
        command = (
            (command_name,) + tuple(str(value) for value in row.get("args", ()))
            if command_name
            else ()
        )
        expected = row.get("expected", {})
        expected_exit = int(expected.get("exit_code", 0)) if isinstance(expected, Mapping) else 0
        receipt_ref = row.get("receipt_ref", {})
        external_receipt_ref = tuple(
            sorted((str(key), str(value)) for key, value in receipt_ref.items())
        ) if isinstance(receipt_ref, Mapping) else ()
        validation_ids = tuple(str(value) for value in policy.get("validation_obligation_ids", ()))
        if not validation_ids:
            validation_ids = (f"validation:spec-check:{check_id}",)
        provider_dependencies = tuple(str(value) for value in row.get("depends_on_receipts", ()))
        bridge_dependencies = tuple(str(value) for value in policy.get("depends_on", ()))
        checks.append(
            SpecCheckDefinition(
                check_id=check_id,
                check_kind=str(row.get("kind", SPEC_CHECK_KIND_COMMAND)),
                command=command,
                required=bool(row.get("required", True)),
                obligation_ids=check_covers.get(check_id, ()),
                validation_obligation_ids=validation_ids,
                depends_on=tuple(dict.fromkeys(provider_dependencies + bridge_dependencies)),
                semantic_check_id=str(row.get("semantic_check_id", "")),
                execution_id=str(row.get("execution_id", "")),
                execution_owner=str(row.get("execution_owner", "")),
                consumer=str(row.get("consumer", "")),
                input_selectors=tuple(str(value) for value in row.get("input_selectors", ())),
                validation_scope=str(row.get("validation_scope", SPEC_VALIDATION_SCOPE_FULL)),
                snapshot_policy=str(row.get("snapshot_policy", SPEC_SNAPSHOT_POLICY_FROZEN)),
                toolchain_identity=str(row.get("toolchain_identity", "")),
                external_receipt_ref=external_receipt_ref,
                timeout_seconds=int(row.get("timeout_seconds", policy.get("timeout_seconds", 600))),
                cross_change_safe=bool(policy.get("cross_change_safe", False)),
                orchestrator_reuse_policy=_orchestrator_reuse_policy(
                    command,
                    provider_value=row.get("reuse_policy", ""),
                    bridge_value=policy.get("orchestrator_reuse_policy", ""),
                ),
                expected_exit_code=expected_exit,
            )
        )
    verified, archive_ready, provider_status, report_metadata = _provider_report_state(change_root)
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
            orchestrator_reuse_policy=_orchestrator_reuse_policy(
                tuple(str(value) for value in row.get("command", ())),
                provider_value=row.get("reuse_policy", ""),
                bridge_value=row.get("orchestrator_reuse_policy", ""),
            ),
            expected_exit_code=int(row.get("expected_exit_code", 0)),
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
    "SpecProviderError",
    "discover_spec_work_packages",
    "load_openspec_work_package",
    "load_speckit_work_package",
]
