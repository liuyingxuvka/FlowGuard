"""Independent native-check child receipt producer for FlowGuard skills."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import sys
import tempfile
from dataclasses import dataclass
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
    evidence_storage_root,
    fingerprint_value,
    list_evidence_receipts,
    save_evidence_receipt,
    snapshot_bytes,
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


PRODUCER_ID = "flowguard.skill_native_checks"
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
        paths.update(_command_input_paths(root, _check_command(check)))
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
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


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
            raw = str(member).strip()
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
                        raw = str(member).replace("\\", "/")
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
) -> tuple[Any, ...]:
    skill_dir = root / SKILL_ROOT / skill_id
    paths = [
        skill_dir / "SKILL.md",
        skill_dir / "agents/openai.yaml",
        skill_dir / CONTRACT_SOURCE_FILE,
        skill_dir / COMPILED_CONTRACT_FILE,
        skill_dir / CHECK_MANIFEST_FILE,
    ]
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
            else snapshot_bytes(
                f"file:{path.relative_to(root).as_posix()}",
                b"<missing>",
                path_token=tokenize_path(path, workspace_root=root),
                hash_policy=INPUT_HASH_BOTH,
                obligation_ids=obligation_ids,
            )
        )
        for path in unique_paths
    ]
    snapshots.extend(_selector_snapshots(root, native_checks, obligation_ids))
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
                or field_name in projected
            ) and declared.get(field_name, ()) != projected.get(field_name, ()):
                blockers.append(f"native_binding_input_identity_mismatch:{check_id}:{field_name}")
        if projected is not None:
            for component_id in projected.get("input_component_ids", ()):
                if str(component_id) not in component_ids:
                    blockers.append(
                        f"native_input_component_unknown:{check_id}:{component_id}"
                    )
            for selector in projected.get("input_selectors", ()):
                if not isinstance(selector, Mapping):
                    blockers.append(f"native_input_selector_invalid:{check_id}")
                    continue
                kind = str(selector.get("kind", ""))
                if kind == "role" and str(selector.get("role", "")) not in component_roles:
                    blockers.append(
                        f"native_input_role_unknown:{check_id}:{selector.get('role', '')}"
                    )
                if kind in {"component", "input_component"}:
                    component_id = str(selector.get("component_id", selector.get("id", "")))
                    if component_id not in component_ids:
                        blockers.append(
                            f"native_input_component_unknown:{check_id}:{component_id}"
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


def run_native_skill_check(
    repository_root: str | Path,
    skill_id: str,
    *,
    output_directory: str | Path | None = None,
    timeout_seconds: float = 900.0,
) -> NativeSkillReceiptResult:
    """Execute declared native bindings and emit one immutable child receipt."""

    root = Path(repository_root).resolve()
    skill_dir = root / SKILL_ROOT / skill_id
    source_path = skill_dir / CONTRACT_SOURCE_FILE
    contract_path = skill_dir / COMPILED_CONTRACT_FILE
    manifest_path = skill_dir / CHECK_MANIFEST_FILE
    source = _read_json(source_path)
    contract = _read_json(contract_path)
    manifest = _read_json(manifest_path)
    _read_json(root / SUITE_MAP_PATH)
    suite_inventory_hash = validate_skill_suite(root).inventory_hash
    native_checks, contract_obligations, binding_blockers = _validate_binding(source, contract, manifest)
    umbrella = f"flowguard.skill_contract.{skill_id}.deep"
    covered_obligations = tuple(dict.fromkeys((umbrella,) + contract_obligations))
    command_parts = (
        "python",
        "scripts/run_flowguard_skill_native_checks.py",
        "--member",
        skill_id,
    )
    snapshots = _input_snapshots(root, skill_id, native_checks, covered_obligations)
    evidence_root = evidence_storage_root(root, output_directory=output_directory)
    proof_path = evidence_root / "proofs" / f"{skill_id}.json"
    log_path = evidence_root / "logs" / f"{skill_id}.log"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    execution_root = _native_execution_workspace(evidence_root, skill_id)

    runs: list[NativeCheckRun] = []
    log_sections: list[str] = []
    blockers = list(binding_blockers)
    for check in native_checks:
        declared = _check_command(check)
        check_id = str(check.get("check_id", "native-check")).strip() or "native-check"
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
        completed = run_supervised(
            _execution_command(declared),
            cwd=root,
            timeout_seconds=timeout_seconds,
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
        "suite_map_hash": suite_inventory_hash,
        "covered_obligations": list(covered_obligations),
        "runs": [item.to_dict() for item in runs],
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
        suite_map_hash=suite_inventory_hash,
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
            "proof_artifact_path_token": tokenize_path(proof_path, workspace_root=root),
            "log_path_token": tokenize_path(log_path, workspace_root=root),
            "native_execution_workspace_path_token": tokenize_path(
                execution_root,
                workspace_root=root,
            ),
            "output_isolation": "FLOWGUARD_OUTPUT_DIR",
            "native_binding_ids": [item.binding_id for item in runs],
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

    ``validate_skill_suite`` is an intentionally complete source walk.  A
    resume run may verify many historical receipts, but the suite hash is a
    single current input shared by every member.  Accepting the caller's
    already-validated hash keeps that finite observation from repeating the
    same repository walk once per receipt; omitting it preserves the direct
    API's original self-contained behavior.
    """

    if receipt.producer_id != PRODUCER_ID:
        return None
    root = Path(repository_root).resolve()
    skill_dir = root / SKILL_ROOT / receipt.subject_id
    try:
        source = _read_json(skill_dir / CONTRACT_SOURCE_FILE)
        contract = _read_json(skill_dir / COMPILED_CONTRACT_FILE)
        manifest = _read_json(skill_dir / CHECK_MANIFEST_FILE)
        _read_json(root / SUITE_MAP_PATH)
        if suite_inventory_hash is None:
            suite_inventory_hash = validate_skill_suite(root).inventory_hash
        proof_token = str(receipt.metadata.get("proof_artifact_path_token", ""))
        proof_path = _resolve_workspace_token(root, proof_token)
        if proof_path is None:
            return None
        proof = _read_json(proof_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    checks, contract_obligations, blockers = _validate_binding(source, contract, manifest)
    if not checks or blockers:
        return None
    umbrella = f"flowguard.skill_contract.{receipt.subject_id}.deep"
    current_required = _input_snapshots(
        root,
        receipt.subject_id,
        checks,
        tuple(dict.fromkeys((umbrella,) + contract_obligations)),
    )
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
        suite_map_hash=suite_inventory_hash,
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
    )


__all__ = [
    "NativeCheckRun",
    "NativeSkillReceiptResult",
    "PRODUCER_ID",
    "build_current_native_receipt_context",
    "run_native_skill_check",
]
