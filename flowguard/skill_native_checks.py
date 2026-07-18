"""Independent native-check child receipt producer for FlowGuard skills."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

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
    snapshot_file,
    tokenize_command,
    tokenize_path,
)
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


def _package_version() -> str:
    try:
        return importlib_metadata.version("flowguard")
    except importlib_metadata.PackageNotFoundError:
        return "0+local"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


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
        candidate = (root / part).resolve()
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


def _input_snapshots(
    root: Path,
    skill_id: str,
    command_parts: Sequence[str],
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
    paths.extend(_command_input_paths(root, command_parts))
    unique_paths = tuple(dict.fromkeys(path for path in paths if path.is_file()))
    snapshots = [
        snapshot_file(
            f"file:{path.relative_to(root).as_posix()}",
            path,
            workspace_root=root,
            hash_policy=INPUT_HASH_BOTH,
            obligation_ids=obligation_ids,
        )
        for path in unique_paths
    ]
    return tuple(snapshots)


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
    timeout_seconds: float = 300.0,
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
    command_parts = _check_command(native_checks[0]) if native_checks else (
        "python",
        "scripts/run_flowguard_skill_native_checks.py",
        "--member",
        skill_id,
    )
    snapshots = _input_snapshots(root, skill_id, command_parts, covered_obligations)
    evidence_root = evidence_storage_root(root, output_directory=output_directory)
    proof_path = evidence_root / "proofs" / f"{skill_id}.json"
    log_path = evidence_root / "logs" / f"{skill_id}.log"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    runs: list[NativeCheckRun] = []
    log_sections: list[str] = []
    blockers = list(binding_blockers)
    for check in native_checks:
        declared = _check_command(check)
        started_at = _now()
        stdout = ""
        stderr = ""
        timed_out = False
        try:
            completed = subprocess.run(
                _execution_command(declared),
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            timed_out = True
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            blockers.append(f"native_check_timeout:{check.get('binding_id', '')}")
        finished_at = _now()
        status = RECEIPT_STATUS_PASS if exit_code == 0 and not timed_out else RECEIPT_STATUS_FAIL
        run = NativeCheckRun(
            binding_id=str(check.get("check_id", "")),
            command=tokenize_command(declared, workspace_root=root),
            exit_code=exit_code,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            stdout_sha256=_sha256_bytes(stdout.encode("utf-8", errors="replace")),
            stderr_sha256=_sha256_bytes(stderr.encode("utf-8", errors="replace")),
            timed_out=timed_out,
        )
        runs.append(run)
        log_sections.extend(
            (
                f"=== {run.binding_id} stdout ===\n{_sanitize_log(stdout, root)}",
                f"=== {run.binding_id} stderr ===\n{_sanitize_log(stderr, root)}",
            )
        )
        if exit_code != 0:
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
    existing = tuple(
        item.receipt_id
        for item in list_evidence_receipts(root, output_directory=output_directory)
        if item.subject_id == skill_id
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
) -> ReceiptVerificationContext | None:
    """Recompute a child context from current files and proof artifacts."""

    if receipt.producer_id != PRODUCER_ID:
        return None
    root = Path(repository_root).resolve()
    skill_dir = root / SKILL_ROOT / receipt.subject_id
    try:
        source = _read_json(skill_dir / CONTRACT_SOURCE_FILE)
        contract = _read_json(skill_dir / COMPILED_CONTRACT_FILE)
        manifest = _read_json(skill_dir / CHECK_MANIFEST_FILE)
        _read_json(root / SUITE_MAP_PATH)
        suite_inventory_hash = validate_skill_suite(root).inventory_hash
        proof_token = str(receipt.metadata.get("proof_artifact_path_token", ""))
        proof_path = _resolve_workspace_token(root, proof_token)
        if proof_path is None:
            return None
        proof = _read_json(proof_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    current_snapshots = {}
    for expected in receipt.input_snapshots:
        path = _resolve_workspace_token(root, expected.path_token)
        if path is not None and path.is_file():
            current_snapshots[expected.artifact_id] = snapshot_file(
                expected.artifact_id,
                path,
                workspace_root=root,
                hash_policy=expected.hash_policy,
                obligation_ids=expected.obligation_ids,
            )
    checks, _, blockers = _validate_binding(source, contract, manifest)
    if not checks or blockers:
        return None
    current_command = tokenize_command(_check_command(checks[0]), workspace_root=root)
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _package_version(),
        }
    )
    umbrella = f"flowguard.skill_contract.{receipt.subject_id}.deep"
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
