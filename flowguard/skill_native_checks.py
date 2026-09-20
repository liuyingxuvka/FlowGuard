"""Independent native-check child receipt producer for FlowGuard skills."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shlex
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._hashing import sha256_bytes as _sha256_bytes
from ._package_identity import flowguard_package_version as _package_version
from .evidence_receipts import (
    EvidenceReceipt,
    INPUT_HASH_BOTH,
    RECEIPT_STATUS_BLOCKED,
    RECEIPT_STATUS_FAIL,
    RECEIPT_STATUS_PASS,
    ReceiptVerificationContext,
    build_environment_fingerprint,
    compare_input_snapshots,
    evidence_storage_root,
    fingerprint_value,
    list_evidence_receipts,
    save_evidence_receipt,
    snapshot_bytes,
    snapshot_missing,
    snapshot_file,
    tokenize_command,
    tokenize_path,
)
from .process_supervision import run_supervised
from .skill_suite import validate_skill_suite
from .skill_contracts import (
    CHECK_MANIFEST_FILE,
    COMPILED_CONTRACT_FILE,
    CONTRACT_SOURCE_FILE,
)
from .pytest_shards import (
    pytest_leaf_key,
    pytest_leaf_plan_fingerprint,
    validate_pytest_leaf_plan,
)


PRODUCER_ID = "flowguard.skill_native_checks"
NATIVE_IDENTITY_VERSION = "2"
PROOF_SCHEMA = "flowguard.skill_native_check_proof.v1"
SUITE_MAP_PATH = Path(".skillguard/flowguard-suite/suite-map.json")
SKILL_ROOT = Path(".agents/skills")
_ABSOLUTE_PATH = re.compile(r"(?i)(?:[A-Z]:[\\/]|\\\\)[^\s\"']+")
# A few Windows consumers still reject paths near the legacy MAX_PATH
# boundary, even when the Python process itself is long-path aware. Keep
# retained native evidence comfortably below that boundary while preserving
# readable names for ordinary short roots.
_NATIVE_PATH_BUDGET = 220


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _native_checks(
    source: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Resolve current target-native bindings to compiled command checks."""

    binding_ids = tuple(
        str(item.get("check_id", ""))
        for item in source.get("native_check_bindings", ())
        if isinstance(item, Mapping)
    )
    checks_by_id = {
        str(item.get("check_id", "")): dict(item)
        for item in manifest.get("checks", ())
        if isinstance(item, Mapping)
    }
    impact_plan = manifest.get("content_impact_plan")
    if isinstance(impact_plan, Mapping):
        for check in checks_by_id.values():
            check.setdefault("content_impact_plan", impact_plan)
    return tuple(checks_by_id[item] for item in binding_ids if item in checks_by_id)


def _split_command(command: str) -> tuple[str, ...]:
    try:
        parts = tuple(shlex.split(command, posix=os.name != "nt"))
    except ValueError as exc:
        raise ValueError(f"invalid native command quoting: {command}") from exc
    if not parts:
        raise ValueError("native command is empty")
    return parts


def _check_command(check: Mapping[str, Any]) -> tuple[str, ...]:
    command = str(check.get("command", "")).strip()
    args = check.get("args", ())
    if not command or not isinstance(args, Sequence) or isinstance(args, (str, bytes)):
        raise ValueError(f"invalid current check command: {check.get('check_id', '<unknown>')}")
    return (command, *(str(item) for item in args))


def _execution_command(parts: Sequence[str]) -> tuple[str, ...]:
    values = tuple(str(item) for item in parts)
    if values and values[0].casefold() in {"python", "python3", "py"}:
        return (sys.executable,) + values[1:]
    return values


def _command_uses_pytest(command_parts: Sequence[str]) -> bool:
    return any(str(part).casefold().split("::", 1)[0] == "pytest" for part in command_parts)


def _pytest_configuration_paths(
    root: Path,
    command_parts: Sequence[str],
) -> tuple[Path, ...]:
    """Return pytest's selected config and ancestor conftest boundary."""

    paths: set[Path] = {root / name for name in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")}
    values = tuple(str(item) for item in command_parts)
    for index, value in enumerate(values):
        raw_config = ""
        if value in {"-c", "--config-file"} and index + 1 < len(values):
            raw_config = values[index + 1]
        elif value.startswith("--config-file="):
            raw_config = value.split("=", 1)[1]
        if raw_config:
            config_path = (root / raw_config).resolve()
            try:
                config_path.relative_to(root)
            except ValueError:
                continue
            paths.add(config_path)

    selected_paths = _command_input_paths(root, command_parts)
    if not selected_paths:
        selected_paths = (root,)
    for selected in selected_paths:
        anchor = selected if selected.is_dir() else selected.parent
        try:
            relatives = anchor.relative_to(root).parts
        except ValueError:
            continue
        ancestors = [root.joinpath(*relatives[:index]) for index in range(len(relatives) + 1)]
        for ancestor in ancestors:
            paths.add(ancestor / "conftest.py")
    return tuple(sorted(paths))


def _native_environment_snapshots(
    native_checks: Sequence[Mapping[str, Any]],
    obligation_ids: Sequence[str],
) -> tuple[Any, ...]:
    snapshots: list[Any] = []
    for check in native_checks:
        try:
            command = _check_command(check)
        except ValueError:
            continue
        if not _command_uses_pytest(command):
            continue
        for name in (
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            "PYTHONPATH",
            "PYTHONHASHSEED",
        ):
            artifact_id = f"environment:{name}"
            path_token = f"environment/{name}"
            if name in os.environ:
                snapshots.append(
                    snapshot_bytes(
                        artifact_id,
                        os.environ[name].encode("utf-8"),
                        path_token=path_token,
                        hash_policy=INPUT_HASH_BOTH,
                        obligation_ids=obligation_ids,
                    )
                )
            else:
                snapshots.append(
                    snapshot_missing(
                        artifact_id,
                        path_token=path_token,
                        hash_policy=INPUT_HASH_BOTH,
                        obligation_ids=obligation_ids,
                    )
                )
    return tuple(dict((item.artifact_id, item) for item in snapshots).values())


def _pytest_distribution_version() -> str:
    try:
        return importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError:
        try:
            import pytest  # type: ignore[import-not-found]

            return str(pytest.__version__)
        except (ImportError, AttributeError) as exc:
            raise ValueError("pytest_version_unavailable") from exc


def _pytest_plugin_version(module_name: str, pytest_version: str) -> str:
    if module_name == "pytest" or module_name.startswith("_pytest"):
        return pytest_version
    package_name = module_name.split(".", 1)[0]
    distributions = importlib.metadata.packages_distributions().get(package_name, ())
    for distribution_name in distributions:
        try:
            return importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "local"


def _pytest_identity_plan(
    root: Path,
    command_parts: Sequence[str],
    *,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    """Collect one pytest plan and bind the selected runtime identity."""

    executable_command = list(_execution_command(command_parts))
    if "--collect-only" not in executable_command:
        executable_command.append("--collect-only")
    if "-q" not in executable_command and "--quiet" not in executable_command:
        executable_command.append("-q")
    if "--trace-config" not in executable_command:
        executable_command.append("--trace-config")
    completed = run_supervised(
        tuple(executable_command),
        cwd=root,
        timeout_seconds=max(1.0, min(120.0, float(timeout_seconds))),
        grace_seconds=3.0,
        environment=dict(os.environ),
    )
    if not completed.ok:
        raise ValueError(
            f"pytest_identity_collection_failed:{completed.terminal_reason}:{completed.exit_code}"
        )
    output = "\n".join(
        value
        for value in (completed.stdout, completed.stderr)
        if isinstance(value, str)
    )
    nodeids = tuple(
        sorted(
            {
                line.strip()
                for line in output.splitlines()
                if "::" in line
                and not line.lstrip().startswith(("PLUGIN", "<", "="))
                and " " not in line.strip()
            }
        )
    )
    plugin_names = {
        match.group(1)
        for match in re.finditer(
            r"PLUGIN registered: <(?:module )?'([^']+)'", output
        )
    }
    for raw in os.environ.get("PYTEST_PLUGINS", "").replace(";", ",").split(","):
        if raw.strip():
            plugin_names.add(raw.strip())
    pytest_version = _pytest_distribution_version()
    plugins = tuple(
        {
            "name": name,
            "version": _pytest_plugin_version(name, pytest_version),
        }
        for name in sorted(plugin_names)
    )
    configuration_paths = tuple(
        tokenize_path(path, workspace_root=root)
        for path in _pytest_configuration_paths(root, command_parts)
    )
    normalized_argv = tokenize_command(
        tuple(executable_command), workspace_root=root
    )
    return {
        "identity_version": NATIVE_IDENTITY_VERSION,
        "argv": list(normalized_argv),
        "pytest_version": pytest_version,
        "python_environment": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": tokenize_path(Path(sys.executable), workspace_root=root),
            "prefix": tokenize_path(Path(sys.prefix), workspace_root=root),
            "base_prefix": tokenize_path(Path(sys.base_prefix), workspace_root=root),
        },
        "working_root": "<WORKSPACE>",
        "configuration_paths": list(configuration_paths),
        "nodeids": list(nodeids),
        "plugins": [dict(item) for item in plugins],
    }


def _pytest_identity_plans(
    root: Path,
    native_checks: Sequence[Mapping[str, Any]],
    *,
    timeout_seconds: float,
) -> dict[str, Mapping[str, Any]]:
    """Collect each distinct declared pytest identity once."""

    plans: dict[str, Mapping[str, Any]] = {}
    for check in native_checks:
        command = _check_command(check)
        if not _command_uses_pytest(command):
            continue
        key = fingerprint_value(tokenize_command(command, workspace_root=root))
        if key not in plans:
            plans[key] = _pytest_identity_plan(
                root,
                command,
                timeout_seconds=timeout_seconds,
            )
    return plans


def _pytest_identity_snapshots(
    root: Path,
    native_checks: Sequence[Mapping[str, Any]],
    obligation_ids: Sequence[str],
    *,
    timeout_seconds: float,
    plans: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Any, ...]:
    selected_plans = dict(
        plans
        if plans is not None
        else _pytest_identity_plans(
            root,
            native_checks,
            timeout_seconds=timeout_seconds,
        )
    )
    snapshots: list[Any] = []
    for key, plan in sorted(selected_plans.items()):
        payload = json.dumps(
            plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        snapshots.append(
            snapshot_bytes(
                f"pytest:plan:{key[:24]}",
                payload,
                path_token=f"pytest-plan/{key[:24]}.json",
                hash_policy=INPUT_HASH_BOTH,
                obligation_ids=obligation_ids,
            )
        )
    return tuple(snapshots)


def _shared_pytest_leaf_rows(
    *,
    repository_root: Path,
    native_checks: Sequence[Mapping[str, Any]],
    pytest_plans: Mapping[str, Mapping[str, Any]],
    pytest_leaf_plan: Mapping[str, Any] | None,
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    """Resolve exact current passing leaves for each native binding.

    A parent may consume a leaf only when the supplied frozen table has the
    same node id and complete runtime identity.  A failed, not-run, old-scope,
    or differently instrumented leaf simply returns no reusable rows and the
    ordinary native child remains responsible for execution.
    """

    if not isinstance(pytest_leaf_plan, Mapping):
        return {}
    if pytest_leaf_plan.get("schema_version") != "flowguard.pytest_leaf_plan.v1":
        return {}
    if pytest_leaf_plan.get("plan_hash") != pytest_leaf_plan_fingerprint(
        pytest_leaf_plan
    ):
        return {}
    if not validate_pytest_leaf_plan(pytest_leaf_plan).get("ok"):
        return {}
    leaves = [
        row
        for row in pytest_leaf_plan.get("leaves", ())
        if isinstance(row, Mapping)
    ]
    by_key = {
        str(row.get("leaf_key", "")): row
        for row in leaves
        if str(row.get("leaf_key", ""))
    }
    matches: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for check in native_checks:
        command = _check_command(check)
        if not _command_uses_pytest(command):
            continue
        key = fingerprint_value(
            tokenize_command(command, workspace_root=repository_root)
        )
        plan = pytest_plans.get(key)
        if plan is None:
            continue
        nodeids = tuple(str(value) for value in plan.get("nodeids", ()))
        # The plan identity is an exact caller contract.  Native checks can
        # reuse it only when the frozen leaf row was built from this same
        # interpreter/config/args/input/timeout/plugin/instrumentation tuple.
        identity = dict(plan)
        identity.setdefault(
            "timeout_seconds", float(check.get("timeout_seconds", 0) or 0)
        )
        identity.setdefault("timeout_result", "not_observed")
        rows: list[Mapping[str, Any]] = []
        for nodeid in nodeids:
            leaf = by_key.get(pytest_leaf_key(nodeid, identity))
            if (
                leaf is None
                or leaf.get("status") != "pass"
                or leaf.get("scope", "current") != "current"
                or not leaf.get("evidence_refs")
            ):
                rows = []
                break
            rows.append(leaf)
        if rows and nodeids:
            matches[str(check.get("check_id", ""))] = tuple(rows)
    return matches


def _sanitize_log(text: str, repository_root: Path, *, limit: int = 40000) -> str:
    value = text[-limit:]
    for raw, token in (
        (str(repository_root), "<WORKSPACE>"),
        (str(repository_root).replace("\\", "/"), "<WORKSPACE>"),
        (str(Path.home()), "<HOME>"),
        (str(Path.home()).replace("\\", "/"), "<HOME>"),
        (str(sys.prefix), "<PYTHON_PREFIX>"),
        (str(sys.prefix).replace("\\", "/"), "<PYTHON_PREFIX>"),
    ):
        if raw:
            value = re.sub(re.escape(raw), token, value, flags=re.IGNORECASE)
    return _ABSOLUTE_PATH.sub("<ABS_PATH>", value).replace("\r\n", "\n").replace("\r", "\n")


def _command_input_paths(root: Path, command_parts: Sequence[str]) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for part in command_parts[1:]:
        if part.startswith("-"):
            continue
        # Pytest node ids are executable file inputs with an optional
        # ``::test_name`` suffix.  Receipt identity must bind the file, not
        # silently ignore the whole argument because the node id is not a
        # filesystem path.
        path_part = part.split("::", 1)[0]
        candidate = (root / path_part).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            paths.add(candidate)
            if candidate.name == "run_checks.py":
                model = candidate.with_name("model.py")
                if model.is_file():
                    paths.add(model)
        elif candidate.is_dir():
            paths.update(path for path in candidate.rglob("*.py") if path.is_file())
    return tuple(sorted(paths))


def _declared_native_input_paths(
    root: Path,
    native_checks: Sequence[Mapping[str, Any]],
) -> tuple[Path, ...]:
    """Resolve every exact command and path selector consumed by one child owner."""

    paths: set[Path] = set()
    for check in native_checks:
        command = _check_command(check)
        paths.update(_command_input_paths(root, command))
        if _command_uses_pytest(command):
            paths.update(_pytest_configuration_paths(root, command))
        for candidate in _selector_input_paths(root, check, native_checks):
            paths.add(candidate)
    producer_paths = (
        Path(__file__).resolve(),
        root / "scripts" / "run_flowguard_skill_native_checks.py",
    )
    for path in producer_paths:
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        paths.add(path.resolve())
    return tuple(sorted(paths))


def _impact_components(
    native_checks: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Return the current content-impact components declared by the checks."""

    for check in native_checks:
        plan = check.get("content_impact_plan")
        if isinstance(plan, Mapping):
            components = plan.get("components", ())
            if isinstance(components, Sequence) and not isinstance(components, (str, bytes)):
                return tuple(item for item in components if isinstance(item, Mapping))
    return ()


def _safe_selector_path(root: Path, raw_path: str) -> Path | None:
    raw = str(raw_path).strip().replace("\\", "/")
    if not raw or raw.startswith(("/", "\\")) or re.match(r"(?i)^[A-Z]:", raw):
        return None
    if any(part == ".." for part in raw.split("/")):
        return None
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


_VALID_SELECTOR_KINDS = frozenset({"path", "role", "component", "input_component"})


def _explicitly_optional(value: Mapping[str, Any]) -> bool:
    return value.get("optional") is True or value.get("required") is False


def _selector_path_blockers(
    root: Path,
    raw_path: str,
    *,
    check_id: str,
    label: str,
    optional: bool,
    expected_type: str = "",
) -> list[str]:
    blockers: list[str] = []
    raw = str(raw_path).strip().replace("\\", "/")
    candidate = _safe_selector_path(root, raw)
    if candidate is None:
        return [f"native_input_path_invalid:{check_id}:{raw_path!s}"]
    wildcard = any(token in raw for token in ("*", "?", "["))
    if wildcard:
        try:
            matches = tuple(root.glob(raw))
        except (OSError, ValueError):
            matches = ()
        matches = tuple(match for match in matches if match.resolve().is_file() or match.resolve().is_dir())
        if not matches and not optional:
            blockers.append(f"native_input_path_missing:{check_id}:{label}")
        candidates = matches
    else:
        if not candidate.exists():
            if not optional:
                blockers.append(f"native_input_path_missing:{check_id}:{label}")
            return blockers
        candidates = (candidate,)
    expected = expected_type.strip().casefold()
    if expected in {"dir", "directory"}:
        if any(not item.is_dir() for item in candidates):
            blockers.append(f"native_input_path_type_mismatch:{check_id}:{label}:directory")
    elif expected == "file":
        if any(not item.is_file() for item in candidates):
            blockers.append(f"native_input_path_type_mismatch:{check_id}:{label}:file")
    return blockers


def _selector_validation_blockers(
    root: Path,
    check: Mapping[str, Any],
    *,
    component_ids: set[str],
    component_roles: set[str],
    components: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    """Validate selector shape and confinement before any expensive work."""

    blockers: list[str] = []
    check_id = str(check.get("check_id", "native-check"))
    selectors = check.get("input_selectors", ())
    if selectors is None:
        selectors = ()
    if not isinstance(selectors, Sequence) or isinstance(selectors, (str, bytes)):
        blockers.append(f"native_input_selector_invalid:{check_id}:input_selectors")
        selectors = ()
    component_values = check.get("input_component_ids", ())
    if component_values is None:
        component_values = ()
    if not isinstance(component_values, Sequence) or isinstance(component_values, (str, bytes)):
        blockers.append(f"native_input_component_invalid:{check_id}")
        component_values = ()

    for component_id in component_values:
        value = str(component_id).strip()
        if not value or value not in component_ids:
            blockers.append(f"native_input_component_unknown:{check_id}:{value}")

    for selector in selectors:
        if not isinstance(selector, Mapping):
            blockers.append(f"native_input_selector_invalid:{check_id}")
            continue
        kind = selector.get("kind")
        if not isinstance(kind, str) or not kind.strip() or kind.strip() not in _VALID_SELECTOR_KINDS:
            blockers.append(f"native_input_selector_kind_invalid:{check_id}:{kind!s}")
            continue
        kind = kind.strip()
        if kind == "path":
            raw_path = selector.get("path")
            if not isinstance(raw_path, str) or _safe_selector_path(root, raw_path) is None:
                blockers.append(f"native_input_path_invalid:{check_id}:{raw_path!s}")
            else:
                blockers.extend(
                    _selector_path_blockers(
                        root,
                        raw_path,
                        check_id=check_id,
                        label=raw_path,
                        optional=_explicitly_optional(selector),
                        expected_type=str(
                            selector.get("path_type", selector.get("expected_type", ""))
                        ),
                    )
                )
        elif kind == "role":
            role = selector.get("role")
            if not isinstance(role, str) or not role.strip() or role.strip() not in component_roles:
                blockers.append(f"native_input_role_unknown:{check_id}:{role!s}")
        else:
            component_id = selector.get("component_id", selector.get("id", ""))
            if not isinstance(component_id, str) or not component_id.strip() or component_id.strip() not in component_ids:
                blockers.append(f"native_input_component_unknown:{check_id}:{component_id!s}")
    by_id = {
        str(item.get("component_id", "")): item
        for item in components
        if str(item.get("component_id", ""))
    }
    by_role: dict[str, list[Mapping[str, Any]]] = {}
    for component in components:
        role = str(component.get("role", "")).strip()
        if role:
            by_role.setdefault(role, []).append(component)

    selected_components: list[Mapping[str, Any]] = []
    for selector in selectors:
        kind = str(selector.get("kind", "")).strip()
        if kind == "role":
            selected_components.extend(
                by_role.get(str(selector.get("role", "")).strip(), ())
            )
        elif kind in {"component", "input_component"}:
            component = by_id.get(
                str(selector.get("component_id", selector.get("id", ""))).strip()
            )
            if component is not None:
                selected_components.append(component)
    for component in selected_components:
        members = component.get("member_paths", ())
        if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
            continue
        for member in members:
            member_spec = member if isinstance(member, Mapping) else {"path": member}
            raw_member = member_spec.get("path", member_spec.get("member_path", ""))
            if not isinstance(raw_member, str) or not raw_member.strip():
                blockers.append(f"native_input_member_invalid:{check_id}:{raw_member!s}")
                continue
            blockers.extend(
                _selector_path_blockers(
                    root,
                    raw_member,
                    check_id=check_id,
                    label=raw_member,
                    optional=(
                        _explicitly_optional(component)
                        or _explicitly_optional(member_spec)
                    ),
                    expected_type=str(
                        member_spec.get(
                            "path_type", member_spec.get("expected_type", "")
                        )
                    ),
                )
            )
    return blockers


def _selector_input_paths(
    root: Path,
    check: Mapping[str, Any],
    all_checks: Sequence[Mapping[str, Any]],
) -> tuple[Path, ...]:
    """Resolve path, role, and component selectors without a broad fallback."""

    components = _impact_components(all_checks)
    by_id = {
        str(item.get("component_id", "")): item
        for item in components
        if str(item.get("component_id", ""))
    }
    by_role: dict[str, list[Mapping[str, Any]]] = {}
    for component in components:
        role = str(component.get("role", "")).strip()
        if role:
            by_role.setdefault(role, []).append(component)

    raw_selectors: list[Mapping[str, Any]] = [
        item
        for item in check.get("input_selectors", ())
        if isinstance(item, Mapping)
    ]
    for component_id in check.get("input_component_ids", ()):
        raw_selectors.append({"kind": "component", "component_id": str(component_id)})

    paths: set[Path] = set()

    def add_member_paths(component: Mapping[str, Any]) -> None:
        members = component.get("member_paths", ())
        if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
            return
        for member in members:
            member_spec = member if isinstance(member, Mapping) else {"path": member}
            raw = str(
                member_spec.get("path", member_spec.get("member_path", ""))
            ).strip()
            if any(token in raw for token in ("*", "?", "[")):
                for match in root.glob(raw.replace("\\", "/")):
                    resolved = match.resolve()
                    try:
                        resolved.relative_to(root)
                    except ValueError:
                        continue
                    if resolved.is_file():
                        paths.add(resolved)
                continue
            candidate = _safe_selector_path(root, raw)
            if candidate is None:
                continue
            if candidate.is_dir():
                paths.update(path.resolve() for path in candidate.rglob("*") if path.is_file())
            else:
                # Retain an absent member as an explicit missing input so a
                # later creation changes the receipt instead of going
                # unnoticed.
                paths.add(candidate)

    for selector in raw_selectors:
        kind = str(selector.get("kind", "")).strip()
        if kind == "path":
            raw = str(selector.get("path", "")).strip()
            candidate = _safe_selector_path(root, raw)
            if candidate is None:
                continue
            if any(token in raw for token in ("*", "?", "[")):
                for match in root.glob(raw.replace("\\", "/")):
                    resolved = match.resolve()
                    try:
                        resolved.relative_to(root)
                    except ValueError:
                        continue
                    if resolved.is_file():
                        paths.add(resolved)
            elif candidate.is_dir():
                paths.update(path.resolve() for path in candidate.rglob("*") if path.is_file())
            else:
                paths.add(candidate)
        elif kind == "role":
            for component in by_role.get(str(selector.get("role", "")).strip(), ()):
                add_member_paths(component)
        elif kind in {"component", "input_component"}:
            component = by_id.get(str(selector.get("component_id", selector.get("id", ""))))
            if component is not None:
                add_member_paths(component)
    return tuple(sorted(paths))


def _selector_snapshots(
    root: Path,
    native_checks: Sequence[Mapping[str, Any]],
    obligation_ids: Sequence[str],
) -> tuple[Any, ...]:
    """Bind selector expansion (including empty/new/deleted cases) to a receipt."""

    components = _impact_components(native_checks)
    by_id = {
        str(item.get("component_id", "")): item
        for item in components
        if str(item.get("component_id", ""))
    }
    by_role: dict[str, list[Mapping[str, Any]]] = {}
    for component in components:
        role = str(component.get("role", "")).strip()
        if role:
            by_role.setdefault(role, []).append(component)

    snapshots: list[Any] = []
    for check in native_checks:
        selectors = [
            item
            for item in check.get("input_selectors", ())
            if isinstance(item, Mapping)
        ]
        selectors.extend(
            {"kind": "component", "component_id": str(value)}
            for value in check.get("input_component_ids", ())
        )
        for selector in selectors:
            kind = str(selector.get("kind", "")).strip()
            components_for_selector: tuple[Mapping[str, Any], ...] = ()
            if kind == "role":
                components_for_selector = tuple(
                    by_role.get(str(selector.get("role", "")).strip(), ())
                )
            elif kind in {"component", "input_component"}:
                component = by_id.get(
                    str(selector.get("component_id", selector.get("id", "")))
                )
                components_for_selector = (component,) if component is not None else ()

            resolved: set[str] = set()
            if kind == "path":
                raw = str(selector.get("path", "")).strip().replace("\\", "/")
                if raw and not re.match(r"(?i)^[A-Z]:", raw) and not raw.startswith(("/", "\\")):
                    for match in root.glob(raw) if any(token in raw for token in ("*", "?", "[")) else ():
                        if match.is_file():
                            resolved.add(match.resolve().relative_to(root).as_posix())
                    if not any(token in raw for token in ("*", "?", "[")):
                        candidate = _safe_selector_path(root, raw)
                        if candidate is not None:
                            if candidate.is_dir():
                                resolved.update(
                                    path.resolve().relative_to(root).as_posix()
                                    for path in candidate.rglob("*")
                                    if path.is_file()
                                )
                            else:
                                resolved.add(candidate.relative_to(root).as_posix())
            for component in components_for_selector:
                members = component.get("member_paths", ())
                if isinstance(members, Sequence) and not isinstance(members, (str, bytes)):
                    for member in members:
                        member_spec = member if isinstance(member, Mapping) else {"path": member}
                        raw = str(
                            member_spec.get(
                                "path", member_spec.get("member_path", "")
                            )
                        ).replace("\\", "/")
                        for match in root.glob(raw) if any(token in raw for token in ("*", "?", "[")) else ():
                            if match.is_file():
                                resolved.add(match.resolve().relative_to(root).as_posix())
                        if not any(token in raw for token in ("*", "?", "[")):
                            candidate = _safe_selector_path(root, raw)
                            if candidate is not None:
                                if candidate.is_dir():
                                    resolved.update(
                                        path.resolve().relative_to(root).as_posix()
                                        for path in candidate.rglob("*")
                                        if path.is_file()
                                    )
                                else:
                                    resolved.add(candidate.relative_to(root).as_posix())
            selector_bytes = json.dumps(
                {"selector": dict(selector), "resolved_paths": sorted(resolved)},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            selector_digest = hashlib.sha256(
                json.dumps(dict(selector), sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:24]
            snapshots.append(
                snapshot_bytes(
                    f"selector:{selector_digest}",
                    selector_bytes,
                    path_token=f"selector/{selector_digest}.json",
                    hash_policy=INPUT_HASH_BOTH,
                    obligation_ids=obligation_ids,
                )
            )
    return tuple(snapshots)


def _input_snapshots(
    root: Path,
    skill_id: str,
    native_checks: Sequence[Mapping[str, Any]],
    obligation_ids: Sequence[str],
    *,
    include_selector_inputs: bool = True,
    extra_snapshots: Sequence[Any] = (),
) -> tuple[Any, ...]:
    skill_dir = root / SKILL_ROOT / skill_id
    paths = [
        skill_dir / "SKILL.md",
        skill_dir / "agents/openai.yaml",
        skill_dir / CONTRACT_SOURCE_FILE,
        skill_dir / COMPILED_CONTRACT_FILE,
        skill_dir / CHECK_MANIFEST_FILE,
    ]
    if include_selector_inputs:
        paths.extend(_declared_native_input_paths(root, native_checks))
    unique_paths = tuple(dict.fromkeys(paths))
    snapshots = [
        (
            snapshot_file(
                f"file:{path.relative_to(root).as_posix()}",
                path,
                workspace_root=root,
                hash_policy=INPUT_HASH_BOTH,
                obligation_ids=obligation_ids,
            )
            if path.is_file()
            else snapshot_missing(
                f"file:{path.relative_to(root).as_posix()}",
                path_token=tokenize_path(path, workspace_root=root),
                hash_policy=INPUT_HASH_BOTH,
                obligation_ids=obligation_ids,
            )
        )
        for path in unique_paths
    ]
    if include_selector_inputs:
        snapshots.extend(_selector_snapshots(root, native_checks, obligation_ids))
        snapshots.extend(_native_environment_snapshots(native_checks, obligation_ids))
    snapshots.extend(extra_snapshots)
    return tuple(dict((item.artifact_id, item) for item in snapshots).values())


def _native_execution_workspace(evidence_root: Path, skill_id: str) -> Path:
    """Create one retained, owner-local workspace for a native invocation.

    Native owner launchers may emit structured evidence through the
    ``FLOWGUARD_OUTPUT_DIR`` contract.  Leaving that variable unset makes a
    launcher fall back to its process cwd (the repository root), after which
    the producer would recursively inspect the whole checkout on its next
    pass.  Keep each invocation under the evidence root, but give it a fresh
    directory so a rerun cannot accidentally consume a previous invocation's
    JSON as if it were current output.  These workspaces are intentionally
    retained; cleanup is a separate, explicit lifecycle action.
    """

    safe_skill = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(skill_id)).strip(".-") or "skill"
    execution_root = (evidence_root / "check-executions" / safe_skill).resolve()
    if len(str(execution_root)) >= _NATIVE_PATH_BUDGET:
        # The full owner id remains in the receipt/proof. The filesystem
        # component only needs to remain stable and safely bounded.
        short_skill = hashlib.sha256(str(skill_id).encode("utf-8")).hexdigest()[:12]
        execution_root = (evidence_root / "check-executions" / f"s-{short_skill}").resolve()
    try:
        execution_root.relative_to(evidence_root.resolve())
    except ValueError as exc:
        raise ValueError("native execution workspace escapes the evidence root") from exc
    if execution_root.exists() and execution_root.is_symlink():
        raise ValueError("native execution workspace cannot be a symlink")
    execution_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="run-", dir=str(execution_root))).resolve()


def _native_check_prefix(execution_root: Path, check_id: str) -> str:
    """Choose a readable check prefix without exhausting Windows path space."""

    safe_check = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(check_id)).strip(".-") or "native-check"
    candidate = str(execution_root / f"{safe_check}-")
    # Reserve room for tempfile's random suffix and a normal child artifact
    # name. Long check ids use a stable digest instead of failing mkdir.
    if len(candidate) + 32 <= _NATIVE_PATH_BUDGET:
        return f"{safe_check}-"
    digest = hashlib.sha256(str(check_id).encode("utf-8")).hexdigest()[:12]
    return f"c-{digest}-"


def _validate_binding(
    root: Path,
    source: Mapping[str, Any],
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...], tuple[str, ...]]:
    native_checks = _native_checks(source, manifest)
    blockers: list[str] = []
    raw_bindings = tuple(
        dict(item)
        for item in source.get("native_check_bindings", ())
        if isinstance(item, Mapping)
    )
    binding_ids = tuple(str(item.get("check_id", "")) for item in raw_bindings)
    if not raw_bindings or not native_checks:
        blockers.append("current_native_check_missing")
    if any(not value for value in binding_ids) or len(set(binding_ids)) != len(binding_ids):
        blockers.append("native_binding_identity_invalid")
    owner = str(source.get("native_route_owner", ""))
    for binding in raw_bindings:
        check_id = str(binding.get("check_id", ""))
        if binding.get("authority") != "target-native":
            blockers.append(f"native_binding_authority_invalid:{check_id}")
        if str(binding.get("owner_id", "")) != owner:
            blockers.append(f"native_binding_owner_mismatch:{check_id}")

    source_checks = {
        str(item.get("check_id", "")): item
        for item in source.get("checks", ())
        if isinstance(item, Mapping)
    }
    manifest_checks = {
        str(item.get("check_id", "")): item
        for item in manifest.get("checks", ())
        if isinstance(item, Mapping)
    }
    impact_plan = manifest.get("content_impact_plan")
    components = (
        tuple(item for item in impact_plan.get("components", ()) if isinstance(item, Mapping))
        if isinstance(impact_plan, Mapping)
        and isinstance(impact_plan.get("components", ()), Sequence)
        and not isinstance(impact_plan.get("components", ()), (str, bytes))
        else ()
    )
    component_ids = {
        str(item.get("component_id", ""))
        for item in components
        if str(item.get("component_id", ""))
    }
    component_roles = {
        str(item.get("role", ""))
        for item in components
        if str(item.get("role", ""))
    }
    for check_id in binding_ids:
        declared = source_checks.get(check_id)
        projected = manifest_checks.get(check_id)
        if declared is None:
            blockers.append(f"native_binding_not_in_contract_source:{check_id}")
            continue
        if declared.get("kind") != "command":
            blockers.append(f"native_binding_not_command:{check_id}")
        if projected is None:
            blockers.append(f"native_binding_not_in_check_manifest:{check_id}")
        elif (
            projected.get("command") != declared.get("command")
            or projected.get("args", ()) != declared.get("args", ())
        ):
            blockers.append(f"native_binding_manifest_mismatch:{check_id}")
        for field_name in ("input_selectors", "input_component_ids"):
            if (
                field_name in declared
                or (projected is not None and field_name in projected)
            ) and declared.get(field_name, ()) != (
                projected.get(field_name, ()) if projected is not None else ()
            ):
                blockers.append(f"native_binding_input_identity_mismatch:{check_id}:{field_name}")
        blockers.extend(
            _selector_validation_blockers(
                root,
                declared,
                component_ids=component_ids,
                component_roles=component_roles,
                components=components,
            )
        )
        if projected is not None:
            blockers.extend(
                _selector_validation_blockers(
                    root,
                    projected,
                    component_ids=component_ids,
                    component_roles=component_roles,
                    components=components,
                )
            )
    required_obligations = tuple(
        str(item.get("obligation_id", ""))
        for item in contract.get("obligations", ())
        if isinstance(item, Mapping)
        and bool(item.get("required", True))
        and str(item.get("obligation_id", ""))
        and set(str(value) for value in item.get("required_check_ids", ())).intersection(binding_ids)
    )
    if binding_ids and not required_obligations:
        blockers.append("native_binding_covers_no_required_obligation")
    if contract.get("skill_id") != source.get("skill_id"):
        blockers.append("compiled_contract_skill_mismatch")
    if manifest.get("skill_id") != source.get("skill_id"):
        blockers.append("check_manifest_skill_mismatch")
    if manifest.get("contract_hash") != contract.get("contract_hash"):
        blockers.append("check_manifest_contract_hash_mismatch")
    return native_checks, required_obligations, tuple(dict.fromkeys(blockers))


@dataclass(frozen=True)
class NativeCheckRun:
    binding_id: str
    command: tuple[str, ...]
    exit_code: int
    status: str
    started_at: str
    finished_at: str
    stdout_sha256: str
    stderr_sha256: str
    timed_out: bool = False
    cancelled: bool = False
    interrupted: bool = False
    cleanup_confirmed: bool = True
    terminal_reason: str = "process_exit"
    descendant_process_ids: tuple[int, ...] = ()
    reused_shared_leaf: bool = False
    shared_leaf_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "command": list(self.command),
            "exit_code": self.exit_code,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "interrupted": self.interrupted,
            "cleanup_confirmed": self.cleanup_confirmed,
            "terminal_reason": self.terminal_reason,
            "descendant_process_ids": list(self.descendant_process_ids),
            "reused_shared_leaf": self.reused_shared_leaf,
            "shared_leaf_ids": list(self.shared_leaf_ids),
        }


@dataclass(frozen=True)
class NativeSkillReceiptResult:
    skill_id: str
    receipt: EvidenceReceipt
    proof_path: Path
    log_path: Path
    runs: tuple[NativeCheckRun, ...]

    @property
    def ok(self) -> bool:
        return self.receipt.result_status == RECEIPT_STATUS_PASS and self.receipt.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "ok": self.ok,
            "status": self.receipt.result_status,
            "receipt_id": self.receipt.receipt_id,
            "receipt_fingerprint": self.receipt.fingerprint,
            "proof_path_token": self.receipt.metadata.get("proof_artifact_path_token", ""),
            "log_path_token": self.receipt.metadata.get("log_path_token", ""),
            "runs": [item.to_dict() for item in self.runs],
            "blockers": list(self.receipt.blockers),
        }


@dataclass(frozen=True)
class NativeSuiteContext:
    """One invocation-local suite observation shared by native owners."""

    repository_root: str
    selected_members: tuple[str, ...]
    inventory_hash: str
    semantic_hash: str
    private_inventory_checked: bool
    member_semantic_hashes: Mapping[str, str] = field(default_factory=dict)
    member_inventory_hashes: Mapping[str, str] = field(default_factory=dict)
    member_input_paths: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def member_semantic_hash(self, skill_id: str) -> str:
        try:
            return str(self.member_semantic_hashes[str(skill_id)])
        except KeyError as exc:
            raise ValueError(
                f"native suite context missing member projection: {skill_id}"
            ) from exc

    def member_inventory_hash(self, skill_id: str) -> str:
        try:
            return str(self.member_inventory_hashes[str(skill_id)])
        except KeyError as exc:
            raise ValueError(
                f"native suite context missing member raw projection: {skill_id}"
            ) from exc


def _semantic_file_bytes(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _member_suite_projections(
    root: Path,
    report: Any,
    selected_members: Sequence[str],
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[str, ...]]]:
    """Build member-local raw and newline-normalized suite projections once."""

    report_members = {
        str(member.skill_id): member
        for member in getattr(report, "members", ())
        if str(getattr(member, "skill_id", ""))
    }
    semantic_hashes: dict[str, str] = {}
    inventory_hashes: dict[str, str] = {}
    input_paths: dict[str, tuple[str, ...]] = {}
    suite_policy = {
        "schema_version": str(getattr(report, "schema_version", "")),
        "suite_name": str(getattr(report, "suite_name", "")),
    }
    for raw_skill_id in selected_members:
        skill_id = str(raw_skill_id)
        member = report_members.get(skill_id)
        if member is None:
            raise ValueError(f"native suite context member is not declared: {skill_id}")
        declared_path = str(member.declared_path).replace("\\", "/")
        required_files = tuple(sorted(str(path) for path in member.required_files))
        file_rows: list[dict[str, Any]] = []
        raw_file_rows: list[dict[str, Any]] = []
        paths: list[str] = []
        for relative in required_files:
            candidate = (root / Path(declared_path) / relative).resolve()
            try:
                token = candidate.relative_to(root).as_posix()
            except ValueError as exc:
                raise ValueError(
                    f"native suite member path escapes repository: {skill_id}:{relative}"
                ) from exc
            paths.append(token)
            if candidate.is_file():
                raw = candidate.read_bytes()
                raw_hash = fingerprint_value({"bytes": raw.hex()})
                semantic_hash = fingerprint_value(
                    {"bytes": _semantic_file_bytes(raw).hex()}
                )
                exists = True
            else:
                raw_hash = ""
                semantic_hash = ""
                exists = False
            file_rows.append(
                {"path": token, "exists": exists, "semantic_hash": semantic_hash}
            )
            raw_file_rows.append(
                {"path": token, "exists": exists, "raw_hash": raw_hash}
            )
        member_identity = {
            "skill_id": skill_id,
            "role": str(member.role),
            "owner": str(member.owner),
            "declared_path": declared_path,
            "repository_role": str(member.repository_role),
            "required_files": required_files,
        }
        semantic_hashes[skill_id] = fingerprint_value(
            {"suite_policy": suite_policy, "member": member_identity, "files": file_rows}
        )
        inventory_hashes[skill_id] = fingerprint_value(
            {"suite_policy": suite_policy, "member": member_identity, "files": raw_file_rows}
        )
        input_paths[skill_id] = tuple(paths)
    return semantic_hashes, inventory_hashes, input_paths


def prepare_native_suite_context(
    repository_root: str | Path,
    selected_members: Sequence[str],
    *,
    check_private_inventories: bool = False,
) -> NativeSuiteContext:
    """Observe the current suite once for a coordinator invocation."""

    root = Path(repository_root).resolve()
    members = tuple(dict.fromkeys(str(item) for item in selected_members if str(item)))
    report = validate_skill_suite(
        root,
        check_private_inventories=check_private_inventories,
    )
    member_semantic_hashes, member_inventory_hashes, member_input_paths = (
        _member_suite_projections(root, report, members)
    )
    return NativeSuiteContext(
        repository_root=str(root),
        selected_members=members,
        inventory_hash=str(report.inventory_hash),
        semantic_hash=str(report.semantic_hash),
        private_inventory_checked=bool(check_private_inventories),
        member_semantic_hashes=member_semantic_hashes,
        member_inventory_hashes=member_inventory_hashes,
        member_input_paths=member_input_paths,
    )


def run_native_skill_check(
    repository_root: str | Path,
    skill_id: str,
    *,
    output_directory: str | Path | None = None,
    timeout_seconds: float = 900.0,
    deadline: float | None = None,
    keep_going: bool = False,
    suite_context: NativeSuiteContext | None = None,
    pytest_leaf_plan: Mapping[str, Any] | None = None,
    pytest_leaf_plan_path: str | Path | None = None,
) -> NativeSkillReceiptResult:
    """Execute declared native bindings and emit one immutable child receipt."""

    root = Path(repository_root).resolve()
    invocation_started = time.monotonic()
    invocation_deadline = (
        float(deadline)
        if deadline is not None
        else invocation_started + max(0.0, float(timeout_seconds))
    )
    skill_dir = root / SKILL_ROOT / skill_id
    source_path = skill_dir / CONTRACT_SOURCE_FILE
    contract_path = skill_dir / COMPILED_CONTRACT_FILE
    manifest_path = skill_dir / CHECK_MANIFEST_FILE
    source = _read_json(source_path)
    contract = _read_json(contract_path)
    manifest = _read_json(manifest_path)
    native_checks, contract_obligations, binding_blockers = _validate_binding(
        root, source, contract, manifest
    )
    umbrella = f"flowguard.skill_contract.{skill_id}.deep"
    covered_obligations = tuple(dict.fromkeys((umbrella,) + contract_obligations))
    command_parts = (
        "python",
        "scripts/run_flowguard_skill_native_checks.py",
        "--member",
        skill_id,
    )
    evidence_root = evidence_storage_root(root, output_directory=output_directory)
    proof_path = evidence_root / "proofs" / f"{skill_id}.json"
    log_path = evidence_root / "logs" / f"{skill_id}.log"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    execution_root = _native_execution_workspace(evidence_root, skill_id)

    runs: list[NativeCheckRun] = []
    log_sections: list[str] = []
    blockers = list(binding_blockers)
    input_revalidation: list[str] = []
    suite_inventory_hash = ""
    suite_semantic_hash = ""
    suite_member_inventory_hash = ""
    suite_member_semantic_hash = ""
    snapshots: tuple[Any, ...] = ()
    pytest_identity_snapshots: tuple[Any, ...] = ()
    pytest_identity_plans: dict[str, Mapping[str, Any]] = {}
    shared_pytest_leaf_rows: dict[str, tuple[Mapping[str, Any], ...]] = {}
    shared_pytest_leaf_refs: list[dict[str, Any]] = []
    pytest_leaf_plan_snapshots: tuple[Any, ...] = ()
    if pytest_leaf_plan_path is not None:
        try:
            plan_path = Path(pytest_leaf_plan_path).expanduser().resolve()
            plan_path.relative_to(root)
            if plan_path.is_symlink() or not plan_path.is_file():
                raise OSError("pytest leaf plan path is missing or unsafe")
            pytest_leaf_plan_snapshots = (
                snapshot_file(
                    "pytest-leaf-plan",
                    plan_path,
                    workspace_root=root,
                    hash_policy=INPUT_HASH_BOTH,
                    obligation_ids=covered_obligations,
                ),
            )
        except (OSError, ValueError):
            blockers.append("pytest_leaf_plan_input_invalid")
    if blockers:
        blockers.append("native_checks_preflight_blocked")
        snapshots = _input_snapshots(
            root,
            skill_id,
            (),
            covered_obligations,
            include_selector_inputs=False,
        )
    elif invocation_deadline <= time.monotonic():
        blockers.append("native_checks_not_run_due_to_budget")
    else:
        try:
            if suite_context is not None:
                if suite_context.repository_root != str(root):
                    raise ValueError("native suite context belongs to another repository")
                if skill_id not in suite_context.selected_members:
                    raise ValueError("native suite context does not include this member")
                suite_inventory_hash = suite_context.inventory_hash
                suite_semantic_hash = suite_context.semantic_hash
                suite_member_inventory_hash = suite_context.member_inventory_hash(skill_id)
                suite_member_semantic_hash = suite_context.member_semantic_hash(skill_id)
            else:
                suite_context = prepare_native_suite_context(
                    root,
                    (skill_id,),
                    check_private_inventories=True,
                )
                suite_inventory_hash = suite_context.inventory_hash
                suite_semantic_hash = suite_context.semantic_hash
                suite_member_inventory_hash = suite_context.member_inventory_hash(skill_id)
                suite_member_semantic_hash = suite_context.member_semantic_hash(skill_id)
            pytest_identity_plans = _pytest_identity_plans(
                root,
                native_checks,
                timeout_seconds=max(1.0, min(float(timeout_seconds), 120.0)),
            )
            pytest_identity_snapshots = _pytest_identity_snapshots(
                root,
                native_checks,
                covered_obligations,
                timeout_seconds=max(1.0, min(float(timeout_seconds), 120.0)),
                plans=pytest_identity_plans,
            )
            shared_pytest_leaf_rows = _shared_pytest_leaf_rows(
                repository_root=root,
                native_checks=native_checks,
                pytest_plans=pytest_identity_plans,
                pytest_leaf_plan=pytest_leaf_plan,
            )
            for rows in shared_pytest_leaf_rows.values():
                for row in rows:
                    shared_pytest_leaf_refs.append(
                        {
                            "leaf_id": str(row.get("leaf_id", "")),
                            "leaf_key": str(row.get("leaf_key", "")),
                            "nodeid": str(row.get("nodeid", "")),
                            "evidence_refs": list(row.get("evidence_refs", ())),
                        }
                    )
            snapshots = _input_snapshots(
                root,
                skill_id,
                native_checks,
                covered_obligations,
                extra_snapshots=(
                    *pytest_identity_snapshots,
                    *pytest_leaf_plan_snapshots,
                ),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"native_preflight_error:{type(exc).__name__}")

    if not suite_inventory_hash:
        # Evidence receipts require an identity for every declared input even
        # when strict preflight prevents observing the suite.  This is a
        # diagnostic identity, never a current suite hash and never eligible
        # for pass-receipt reuse.
        suite_inventory_hash = _sha256_bytes(
            f"native-suite-not-scanned:{skill_id}:{'|'.join(blockers)}".encode("utf-8")
        )
    if not suite_member_semantic_hash:
        suite_member_semantic_hash = fingerprint_value(
            {
                "native_suite_member_not_scanned": skill_id,
                "blockers": tuple(dict.fromkeys(blockers)),
            }
        )
    if not suite_member_inventory_hash:
        suite_member_inventory_hash = suite_member_semantic_hash
    if not snapshots:
        snapshots = _input_snapshots(
            root,
            skill_id,
            (),
            covered_obligations,
            include_selector_inputs=False,
        )

    for check in native_checks if not blockers else ():
        remaining = invocation_deadline - time.monotonic()
        if remaining <= 0.0:
            blockers.append("native_checks_not_run_due_to_budget")
            blockers.extend(
                f"native_check_not_run_after_budget:{item.get('check_id', '')}"
                for item in native_checks[len(runs) :]
            )
            break
        declared = _check_command(check)
        check_id = str(check.get("check_id", "native-check")).strip() or "native-check"
        shared_rows = shared_pytest_leaf_rows.get(check_id, ())
        if shared_rows:
            now = _now()
            reused_run = NativeCheckRun(
                binding_id=check_id,
                command=tokenize_command(declared, workspace_root=root),
                exit_code=0,
                status=RECEIPT_STATUS_PASS,
                started_at=now,
                finished_at=now,
                stdout_sha256=_sha256_bytes(b""),
                stderr_sha256=_sha256_bytes(b""),
                cleanup_confirmed=True,
                terminal_reason="reused_shared_leaf",
                reused_shared_leaf=True,
                shared_leaf_ids=tuple(
                    str(row.get("leaf_id", "")) for row in shared_rows
                ),
            )
            runs.append(reused_run)
            log_sections.append(
                f"=== {check_id} shared pytest leaf reuse ===\n"
                + json.dumps(
                    {
                        "leaf_ids": list(reused_run.shared_leaf_ids),
                        "nodeids": [
                            str(row.get("nodeid", "")) for row in shared_rows
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            continue
        check_workspace = Path(
            tempfile.mkdtemp(
                prefix=_native_check_prefix(execution_root, check_id),
                dir=str(execution_root),
            )
        ).resolve()
        started_at = _now()
        stdout = ""
        stderr = ""
        child_environment = dict(os.environ)
        # Native checks may create temporary Git repositories.  An outer
        # completion/readiness invocation can set a private index for its
        # read-only source snapshot; passing that same path to a temporary
        # repository lets Git truncate the parent's index and makes the final
        # freshness gate falsely report a changed authority.  Keep the
        # private index in the coordinator only.
        child_environment.pop("GIT_INDEX_FILE", None)
        child_environment.update(
            {
                "FLOWGUARD_OUTPUT_DIR": str(check_workspace),
                "FLOWGUARD_OWNER_ID": skill_id,
                "FLOWGUARD_NATIVE_CHECK_ID": check_id,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        effective_timeout = max(0.0, float(timeout_seconds))
        declared_timeout = check.get("timeout_seconds")
        if declared_timeout is not None:
            try:
                declared_timeout_value = float(declared_timeout)
            except (TypeError, ValueError):
                declared_timeout_value = 0.0
            if declared_timeout_value > 0.0:
                effective_timeout = min(effective_timeout, declared_timeout_value)
        completed = run_supervised(
            _execution_command(declared),
            cwd=root,
            timeout_seconds=min(effective_timeout, remaining),
            grace_seconds=3.0,
            environment=child_environment,
        )
        exit_code = (
            int(completed.exit_code)
            if completed.exit_code is not None
            else 124
            if completed.timed_out
            else 125
        )
        stdout = completed.stdout if isinstance(completed.stdout, str) else completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr if isinstance(completed.stderr, str) else completed.stderr.decode("utf-8", errors="replace")
        if completed.timed_out:
            blockers.append(f"native_check_timeout:{check.get('check_id', '')}")
        if completed.cancelled:
            blockers.append(f"native_check_cancelled:{check.get('check_id', '')}")
        if completed.interrupted:
            blockers.append(f"native_check_interrupted:{check.get('check_id', '')}")
        if not completed.cleanup_confirmed:
            blockers.append(f"native_check_cleanup_unconfirmed:{check.get('check_id', '')}")
        if completed.terminal_reason != "process_exit":
            blockers.append(
                f"native_check_terminal:{check.get('check_id', '')}:{completed.terminal_reason}"
            )
        finished_at = _now()
        status = RECEIPT_STATUS_PASS if completed.ok else RECEIPT_STATUS_FAIL
        run = NativeCheckRun(
            binding_id=str(check.get("check_id", "")),
            command=tokenize_command(declared, workspace_root=root),
            exit_code=exit_code,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            stdout_sha256=_sha256_bytes(stdout.encode("utf-8", errors="replace")),
            stderr_sha256=_sha256_bytes(stderr.encode("utf-8", errors="replace")),
            timed_out=completed.timed_out,
            cancelled=completed.cancelled,
            interrupted=completed.interrupted,
            cleanup_confirmed=completed.cleanup_confirmed,
            terminal_reason=completed.terminal_reason,
            descendant_process_ids=tuple(completed.descendant_process_ids),
        )
        runs.append(run)
        log_sections.extend(
            (
                f"=== {run.binding_id} stdout ===\n{_sanitize_log(stdout, root)}",
                f"=== {run.binding_id} stderr ===\n{_sanitize_log(stderr, root)}",
            )
        )
        if not completed.ok:
            blockers.append(f"native_check_failed:{run.binding_id}:exit={exit_code}")
            hard_stop = (
                completed.cancelled
                or completed.interrupted
                or not completed.cleanup_confirmed
                or completed.terminal_reason in {"cancelled", "interrupted", "cleanup_unconfirmed"}
            )
            if hard_stop or not keep_going:
                remaining_checks = native_checks[len(runs) :]
                reason = "terminal" if hard_stop else "failure"
                blockers.append(f"native_checks_stopped_after_{reason}:{run.binding_id}")
                blockers.extend(
                    f"native_check_not_run_after_{reason}:{item.get('check_id', '')}"
                    for item in remaining_checks
                )
                break

    if runs:
        try:
            final_snapshots = _input_snapshots(
                root,
                skill_id,
                native_checks,
                covered_obligations,
                extra_snapshots=(
                    *pytest_identity_snapshots,
                    *pytest_leaf_plan_snapshots,
                ),
            )
            initial_by_id = {item.artifact_id: item for item in snapshots}
            final_by_id = {item.artifact_id: item for item in final_snapshots}
            if set(initial_by_id) != set(final_by_id):
                input_revalidation.append("selection_boundary")
            for artifact_id in sorted(set(initial_by_id) & set(final_by_id)):
                findings = compare_input_snapshots(
                    initial_by_id[artifact_id], final_by_id[artifact_id]
                )
                if findings:
                    input_revalidation.extend(
                        f"{artifact_id}:{finding.code}" for finding in findings
                    )
            if input_revalidation:
                blockers.append(
                    "input_changed_during_execution:"
                    + ",".join(dict.fromkeys(input_revalidation))
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            input_revalidation.append(f"observation:{type(exc).__name__}")
            blockers.append(
                "input_changed_during_execution:postflight_observation_unavailable"
            )

    if runs and suite_context is not None and suite_member_semantic_hash:
        # Re-observe the selected member after execution.  This is deliberately
        # a new context: the admission cache must not mask a mid-run change.
        try:
            postflight_context = prepare_native_suite_context(
                root,
                (skill_id,),
                check_private_inventories=suite_context.private_inventory_checked,
            )
            if postflight_context.inventory_hash != suite_inventory_hash:
                input_revalidation.append("suite_map_raw_hash_mismatch")
            if (
                postflight_context.member_inventory_hash(skill_id)
                != suite_member_inventory_hash
            ):
                input_revalidation.append("suite_member_raw_hash_mismatch")
            if (
                postflight_context.member_semantic_hash(skill_id)
                != suite_member_semantic_hash
            ):
                input_revalidation.append("suite_member_semantic_hash_mismatch")
            if any(
                item.endswith("hash_mismatch") for item in input_revalidation
            ):
                blockers.append(
                    "input_changed_during_execution:"
                    + ",".join(dict.fromkeys(input_revalidation))
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            input_revalidation.append(f"suite_observation:{type(exc).__name__}")
            blockers.append(
                "input_changed_during_execution:postflight_suite_observation_unavailable"
            )

    if not runs:
        blockers.append("native_checks_not_run")
    result_status = RECEIPT_STATUS_PASS if runs and not blockers and all(item.exit_code == 0 for item in runs) else (
        RECEIPT_STATUS_BLOCKED if binding_blockers or not runs else RECEIPT_STATUS_FAIL
    )
    aggregate_exit = 0 if result_status == RECEIPT_STATUS_PASS else next(
        (item.exit_code for item in runs if item.exit_code != 0),
        2,
    )
    log_path.write_text("\n\n".join(log_sections) + "\n", encoding="utf-8", newline="\n")
    proof = {
        "schema_version": PROOF_SCHEMA,
        "skill_id": skill_id,
        "producer_id": PRODUCER_ID,
        "producer_version": _package_version(),
        "output_isolation": "FLOWGUARD_OUTPUT_DIR",
        "execution_workspace_path_token": tokenize_path(execution_root, workspace_root=root),
        "contract_hash": str(contract.get("contract_hash", "")),
        "check_manifest_hash": fingerprint_value(manifest),
        # The legacy field remains the owner-local semantic projection so a
        # sibling member change does not invalidate this member's receipt.
        "suite_map_hash": suite_member_semantic_hash,
        "suite_inventory_hash": suite_inventory_hash,
        "suite_semantic_hash": suite_semantic_hash,
        "suite_member_inventory_hash": suite_member_inventory_hash,
        "suite_member_semantic_hash": suite_member_semantic_hash,
        "covered_obligations": list(covered_obligations),
        "runs": [item.to_dict() for item in runs],
        "pytest_leaf_plan_hash": (
            str(pytest_leaf_plan.get("plan_hash", ""))
            if isinstance(pytest_leaf_plan, Mapping)
            else ""
        ),
        "pytest_leaf_plan_path_token": (
            tokenize_path(Path(pytest_leaf_plan_path).resolve(), workspace_root=root)
            if pytest_leaf_plan_path is not None
            else ""
        ),
        "pytest_leaf_references": shared_pytest_leaf_refs,
        "result_status": result_status,
        "exit_code": aggregate_exit,
        "blockers": list(dict.fromkeys(blockers)),
        "log_sha256": _sha256_bytes(log_path.read_bytes()),
    }
    proof_path.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    proof_fingerprint = fingerprint_value(proof)
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _package_version(),
        }
    )
    # Supersession is scoped to this owner.  Reading the unfiltered append-only
    # store here made a multi-owner run rescan and deserialize every historical
    # receipt once per owner, turning a bounded pass into quadratic I/O as the
    # store grew.  The subject-indexed reader preserves the same immutable
    # identity/filename/schema validation while limiting observation to this
    # exact owner.
    existing = tuple(
        item.receipt_id
        for item in list_evidence_receipts(
            root,
            output_directory=output_directory,
            subject_ids=(skill_id,),
        )
    )
    receipt_id = f"receipt:{skill_id}:{proof_fingerprint.split(':', 1)[-1][:24]}"
    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        subject_id=skill_id,
        subject_kind="flowguard_skill_native_check",
        producer_id=PRODUCER_ID,
        producer_version=_package_version(),
        claim_scope="full" if result_status == RECEIPT_STATUS_PASS else "diagnostic",
        command=tokenize_command(command_parts, workspace_root=root),
        working_directory_token="<WORKSPACE>",
        started_at=min((item.started_at for item in runs), default=_now()),
        finished_at=max((item.finished_at for item in runs), default=_now()),
        exit_code=aggregate_exit,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=str(contract.get("contract_hash", "")),
        check_manifest_hash=fingerprint_value(manifest),
        suite_map_hash=suite_member_semantic_hash,
        input_snapshots=snapshots,
        proof_artifact_id=f"proof:native-skill:{skill_id}",
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=result_status,
        result_fingerprint=proof_fingerprint,
        covered_obligations=covered_obligations,
        supersedes_receipt_ids=existing,
        blockers=tuple(dict.fromkeys(blockers)),
        claim_boundary=(
            "This receipt proves the declared owner-specific native command and current deep contract inputs for one "
            "FlowGuard skill; parent, distribution, installation, release, and future-agent claims remain separate."
        ),
        metadata={
            "native_identity_version": NATIVE_IDENTITY_VERSION,
            "proof_artifact_path_token": tokenize_path(proof_path, workspace_root=root),
            "log_path_token": tokenize_path(log_path, workspace_root=root),
            "native_execution_workspace_path_token": tokenize_path(
                execution_root,
                workspace_root=root,
            ),
            "output_isolation": "FLOWGUARD_OUTPUT_DIR",
            "native_binding_ids": [item.binding_id for item in runs],
            "input_revalidation": list(dict.fromkeys(input_revalidation)),
            "suite_inventory_hash": suite_inventory_hash,
            "suite_semantic_hash": suite_semantic_hash,
            "suite_member_inventory_hash": suite_member_inventory_hash,
            "suite_member_semantic_hash": suite_member_semantic_hash,
            "suite_member_input_paths": list(
                suite_context.member_input_paths.get(skill_id, ())
                if suite_context is not None
                else ()
            ),
        },
    )
    save_evidence_receipt(receipt, root, output_directory=output_directory)
    return NativeSkillReceiptResult(skill_id, receipt, proof_path, log_path, tuple(runs))


def _resolve_workspace_token(root: Path, token: str) -> Path | None:
    prefix = "<WORKSPACE>/"
    if not token.startswith(prefix) or "*" in token:
        return None
    candidate = (root / token[len(prefix) :]).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def build_current_native_receipt_context(
    receipt: EvidenceReceipt,
    repository_root: str | Path,
    *,
    suite_inventory_hash: str | None = None,
) -> ReceiptVerificationContext | None:
    """Recompute a child context from current files and proof artifacts.

    The suite map's raw hash remains available as provenance, while the
    receipt comparison uses the selected member's normalized projection.  A
    fresh context is built for every post-run verification so sibling changes
    are scoped correctly and no admission cache can hide a current change.
    """

    if receipt.producer_id != PRODUCER_ID:
        return None
    root = Path(repository_root).resolve()
    skill_dir = root / SKILL_ROOT / receipt.subject_id
    try:
        source = _read_json(skill_dir / CONTRACT_SOURCE_FILE)
        contract = _read_json(skill_dir / COMPILED_CONTRACT_FILE)
        manifest = _read_json(skill_dir / CHECK_MANIFEST_FILE)
        suite_context = prepare_native_suite_context(
            root,
            (receipt.subject_id,),
            check_private_inventories=True,
        )
        if suite_inventory_hash is not None and suite_inventory_hash != suite_context.inventory_hash:
            return None
        suite_inventory_hash = suite_context.inventory_hash
        suite_member_semantic_hash = suite_context.member_semantic_hash(
            receipt.subject_id
        )
        proof_token = str(receipt.metadata.get("proof_artifact_path_token", ""))
        proof_path = _resolve_workspace_token(root, proof_token)
        if proof_path is None:
            return None
        proof = _read_json(proof_path)
        leaf_plan_path: Path | None = None
        leaf_plan_token = str(proof.get("pytest_leaf_plan_path_token", ""))
        if leaf_plan_token:
            leaf_plan_path = _resolve_workspace_token(root, leaf_plan_token)
            if leaf_plan_path is None or leaf_plan_path.is_symlink() or not leaf_plan_path.is_file():
                return None
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    checks, contract_obligations, blockers = _validate_binding(
        root, source, contract, manifest
    )
    if not checks or blockers:
        return None
    umbrella = f"flowguard.skill_contract.{receipt.subject_id}.deep"
    required_obligations = tuple(dict.fromkeys((umbrella,) + contract_obligations))
    leaf_plan_snapshots = (
        (
            snapshot_file(
                "pytest-leaf-plan",
                leaf_plan_path,
                workspace_root=root,
                hash_policy=INPUT_HASH_BOTH,
                obligation_ids=required_obligations,
            ),
        )
        if leaf_plan_path is not None
        else ()
    )
    try:
        current_required = _input_snapshots(
            root,
            receipt.subject_id,
            checks,
            required_obligations,
            extra_snapshots=(
                *_pytest_identity_snapshots(
                    root,
                    checks,
                    required_obligations,
                    timeout_seconds=30.0,
                ),
                *leaf_plan_snapshots,
            ),
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if {item.artifact_id for item in current_required} != {
        item.artifact_id for item in receipt.input_snapshots
    }:
        return None
    current_snapshots = {item.artifact_id: item for item in current_required}
    current_command = tokenize_command(
        (
            "python",
            "scripts/run_flowguard_skill_native_checks.py",
            "--member",
            receipt.subject_id,
        ),
        workspace_root=root,
    )
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _package_version(),
        }
    )
    return ReceiptVerificationContext(
        input_snapshots=current_snapshots,
        contract_hash=str(contract.get("contract_hash", "")),
        check_manifest_hash=fingerprint_value(manifest),
        suite_map_hash=suite_member_semantic_hash,
        producer_id=PRODUCER_ID,
        producer_version=_package_version(),
        environment_fingerprint=environment.fingerprint,
        proof_artifact_fingerprint=fingerprint_value(proof),
        result_fingerprint=fingerprint_value(proof),
        command=current_command,
        working_directory_token="<WORKSPACE>",
        proof_artifact_id=f"proof:native-skill:{receipt.subject_id}",
        required_obligation_ids=(umbrella,),
        eligible_claim_scopes=("full",),
        receipt_identity_version=NATIVE_IDENTITY_VERSION,
    )


__all__ = [
    "NativeCheckRun",
    "NativeSuiteContext",
    "NativeSkillReceiptResult",
    "PRODUCER_ID",
    "build_current_native_receipt_context",
    "prepare_native_suite_context",
    "run_native_skill_check",
]
