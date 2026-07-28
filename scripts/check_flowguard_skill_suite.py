"""Validate the FlowGuard skill suite at static or full repository scope.

The default ``static`` scope checks the current 15-member
inventory/compiler/SkillGuard check.  ``full`` is the release-facing
composition: every required child keeps its own stdout, stderr, and canonical
result artifact, and the parent uses FlowGuard's shared validation-result
semantics without turning a scoped or incomplete child into success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.skill_contracts import compile_skill_suite
from flowguard.skill_suite import FLOWGUARD_SKILL_ROOT, validate_skill_suite
from flowguard.evidence_lifecycle import (
    EvidenceLifecycleError,
    ensure_new_run_directory,
    evidence_execution_lease,
    fingerprint_payload,
    publish_run,
    store_text_object,
)
from flowguard.validation_ownership import (
    OWNER_BLOCKED,
    OWNER_EXECUTE,
    OWNER_REUSE_CURRENT,
    ValidationOwnerContract,
    ValidationOwnerPlanRow,
    build_owner_current,
    child_from_owner_receipt,
    find_reusable_owner_receipt,
    plan_validation_owners,
    save_owner_receipt,
    save_parent_receipt,
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


FULL_CHILD_IDS = (
    "project_audit",
    "skill_suite_static",
    "skill_self_governance",
    "model_regressions_full",
    "pytest",
    "openspec_strict",
    "distribution_check",
    "distribution_parity",
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


@dataclass(frozen=True)
class ChildSpec:
    child_id: str
    command: tuple[str, ...]
    input_patterns: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    required_path: Path | None = None
    missing_reason: str = ""


def _skillguard_cli(value: str) -> Path:
    if value != "all":
        return Path(value).expanduser().resolve()
    return Path.home() / ".codex" / "skills" / "skillguard" / "scripts" / "skillguard.py"


def _run_json_command(command: list[str], cwd: Path) -> dict[str, Any]:
    """Run one static-scope child and expose its terminal JSON material."""

    outcome = _execute_command(tuple(command), cwd)
    return {
        "command": list(outcome.command),
        "exit_code": outcome.exit_code,
        "stdout": outcome.stdout,
        "stderr": outcome.stderr,
        "payload": dict(outcome.payload) if outcome.payload is not None else None,
    }


def _execute_command(command: Sequence[str], cwd: Path) -> CommandOutcome:
    """Run one child without a shell and retain all terminal material."""

    normalized = tuple(str(item) for item in command)
    try:
        completed = subprocess.run(
            normalized,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CommandOutcome(normalized, 2, stderr=str(exc), launch_error=f"{type(exc).__name__}: {exc}")
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
        completed.returncode,
        completed.stdout,
        completed.stderr,
        payload,
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


def run_static_suite(
    root: Path,
    *,
    skillguard: str = "all",
    members: Sequence[str] = (),
) -> dict[str, Any]:
    """Run the inventory/compiler/SkillGuard 15-member surface."""

    inventory = validate_skill_suite(root)
    compiler = compile_skill_suite(root, write=False)
    selected = tuple(members) if members else inventory.declared_member_ids
    cli = _skillguard_cli(skillguard)
    member_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
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
                "static": [
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
            results = {name: _run_json_command(command, root) for name, command in commands.items()}
            static_ok = results["static"]["exit_code"] == 0 and (results["static"]["payload"] or {}).get("decision") == "pass"
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
                    "ok": static_ok and contract_ok and depth_ok,
                    "static_ok": static_ok,
                    "contract_ok": contract_ok,
                    "depth_ok": depth_ok,
                    "depth_classification": depth_payload.get("depth_classification", "unavailable"),
                    "expected_depth_classifications": sorted(expected_depth_classes),
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
        "skipped_checks": [] if cli.is_file() else ["SkillGuard static/contract/depth"],
        "residual_risk": [
            "Static contract-currentness does not execute declared FlowGuard native commands or prove future AI behavior."
        ],
        "claim_boundary": (
            "Pass certifies current prompt and target-declared contract structure for 15 members only; "
            "native receipt and parent self-governance gates remain separate."
        ),
    }


def _write_static_result(
    payload: Mapping[str, Any],
    output_dir: str | None,
) -> tuple[str, str, str]:
    if output_dir:
        run_dir = Path(output_dir).expanduser().resolve()
    else:
        run_dir = Path(
            tempfile.mkdtemp(prefix="flowguard-skill-suite-static-")
        ).resolve()
    ensure_new_run_directory(run_dir)
    result_path = run_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    publish_run(
        run_dir,
        kind="skill-suite-static",
        status=str(payload.get("status", "blocked")),
        result_path=result_path,
    )
    result_sha256 = "sha256:" + hashlib.sha256(result_path.read_bytes()).hexdigest()
    return run_dir.name, str(result_path), result_sha256


def _print_static(
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
                    "scope": "static",
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
                f"finding: {row.get('skill_id')}: static={row.get('static_ok')} "
                f"contract={row.get('contract_ok')} depth={row.get('depth_classification')}"
            )


def _full_child_specs(args: argparse.Namespace, root: Path) -> tuple[ChildSpec, ...]:
    formal = Path(args.formal_root).expanduser().resolve() if args.formal_root else root
    shadow = Path(args.shadow_root).expanduser().resolve() if args.shadow_root else None
    installed = (
        Path(args.installed_root).expanduser().resolve()
        if args.installed_root
        else Path.home() / ".codex" / "skills"
    )
    self_script = root / "scripts" / "check_flowguard_self_governance.py"
    model_script = root / "scripts" / "run_flowguard_model_regressions.py"
    distribution_script = root / "scripts" / "install_flowguard_skills.py"

    static_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--scope",
        "static",
        "--root",
        str(root),
        "--skillguard",
        args.skillguard,
        "--output-dir",
        str(Path(args.output_dir).expanduser().resolve() / "static-suite"),
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
        str(Path(args.output_dir).expanduser().resolve() / "model-regressions")
        if args.output_dir
        else str(root / ".flowguard" / "evidence" / "model-regressions"),
        "--json",
    ]
    if args.model_timeout is not None:
        model_command.extend(("--timeout", str(args.model_timeout)))

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

    return (
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
            "skill_suite_static",
            tuple(static_command),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/skill_contracts.py",
                "flowguard/skill_suite.py",
                "scripts/check_flowguard_skill_suite.py",
            ),
            ("validation:skill_suite_static",),
        ),
        ChildSpec(
            "skill_self_governance",
            (
                sys.executable,
                str(self_script),
                "--root",
                str(root),
                "--output-directory",
                str(root / ".flowguard" / "evidence" / "skill-suite"),
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
            required_path=self_script,
            missing_reason="self-governance checker is required for full closure",
        ),
        ChildSpec(
            "model_regressions_full",
            tuple(model_command),
            (
                ".flowguard/model-regression-manifest.json",
                ".flowguard/**/*.py",
                ".flowguard/**/*.json",
                "flowguard/model_*.py",
                "flowguard/source_identity.py",
                "flowguard/validation_results.py",
                "scripts/run_flowguard_model_regressions.py",
            ),
            ("validation:model_regressions_full",),
            required_path=model_script,
            missing_reason="manifest model-regression runner is required for full closure",
        ),
        ChildSpec(
            "pytest",
            (sys.executable, "-m", "pytest"),
            (
                "flowguard/**/*.py",
                "scripts/**/*.py",
                "tests/**/*.py",
                ".flowguard/model-regression-manifest.json",
                "pyproject.toml",
            ),
            ("validation:pytest",),
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
            (
                sys.executable,
                str(distribution_script),
                "check",
                "--source",
                str(formal),
                "--target",
                str(installed),
                "--json",
            ),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/distribution_sync.py",
                "flowguard/skill_suite.py",
                "scripts/install_flowguard_skills.py",
            ),
            ("validation:distribution_check",),
            required_path=distribution_script,
            missing_reason="distribution checker is required for full closure",
        ),
        ChildSpec(
            "distribution_parity",
            tuple(parity_command),
            (
                ".agents/skills/**/*",
                ".skillguard/**/*",
                "flowguard/distribution_sync.py",
                "flowguard/skill_suite.py",
                "scripts/install_flowguard_skills.py",
            ),
            ("validation:distribution_parity",),
            required_path=distribution_script if shadow is not None else None,
            missing_reason=(
                "--shadow-root is required to prove formal/shadow/installed complete-tree parity"
                if shadow is None
                else "distribution parity checker is required for full closure"
            ),
        ),
    )


def _owner_contracts(specs: Sequence[ChildSpec]) -> tuple[ValidationOwnerContract, ...]:
    def identity_command(command: Sequence[str]) -> tuple[str, ...]:
        values = list(command)
        for index, value in enumerate(values[:-1]):
            if value in {"--output-dir", "--output-directory", "--receipt-dir"}:
                values[index + 1] = "<EVIDENCE_RUN>"
        return tuple(values)

    return tuple(
        ValidationOwnerContract(
            owner_id=spec.child_id,
            command=identity_command(spec.command),
            input_patterns=spec.input_patterns,
            obligation_ids=spec.obligation_ids,
        )
        for spec in specs
    )


def _status_from_outcome(outcome: CommandOutcome) -> str:
    if outcome.launch_error:
        return VALIDATION_STATUS_BLOCKED
    payload = outcome.payload or {}
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


def _run_full_child(spec: ChildSpec, root: Path, output_dir: Path, index: int) -> ValidationChildResult:
    child_dir = output_dir / f"{index:02d}-{spec.child_id}"
    if spec.child_id == "distribution_parity" and spec.required_path is None:
        return _blocked_child(spec, spec.missing_reason, child_dir)
    if spec.required_path is not None and not spec.required_path.is_file():
        return _blocked_child(spec, f"{spec.missing_reason}: {spec.required_path}", child_dir)

    outcome = _execute_command(spec.command, root)
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
    return ValidationChildResult(
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
        },
    )


def _output_directory(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.mkdtemp(prefix=f"flowguard-unified-validation-{timestamp}-")).resolve()


def run_full_validation(args: argparse.Namespace) -> ValidationResult:
    root = Path(args.root).resolve()
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
    plan_rows, currents, reusable = plan_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
    )
    plan_payload = {
        "schema_version": "flowguard.validation_owner_plan.v1",
        "status": (
            "blocked"
            if any(item.disposition == OWNER_BLOCKED for item in plan_rows)
            else "ready"
        ),
        "rows": [item.to_dict() for item in plan_rows],
        "counts": {
            disposition: sum(item.disposition == disposition for item in plan_rows)
            for disposition in (OWNER_EXECUTE, OWNER_REUSE_CURRENT, OWNER_BLOCKED)
        },
        "claim_boundary": (
            "The owner plan decides execution only; it is not terminal validation evidence."
        ),
    }
    plan_id = fingerprint_payload(
        {
            "schema_version": plan_payload["schema_version"],
            "rows": plan_payload["rows"],
        }
    )
    plan_payload["plan_id"] = plan_id
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
            ),
            residual_risk=("No validation producer executed in plan-only mode.",),
            claim_boundary=(
                "Plan-only output classifies owners but cannot support validation or release closure."
            ),
            progress_summary={"completed": 0, "total": len(specs)},
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
    children: list[ValidationChildResult] = []
    owner_receipts: dict[str, Any] = {}
    plan_by_owner = {item.owner_id: item for item in plan_rows}
    for index, spec in enumerate(specs, start=1):
        plan_row = plan_by_owner[spec.child_id]
        print(
            f"START {spec.child_id} disposition={plan_row.disposition} ({index}/{len(specs)})",
            file=sys.stderr,
            flush=True,
        )
        try:
            if plan_row.disposition == OWNER_BLOCKED:
                child = _blocked_child(spec, plan_row.reason, output_dir / f"{index:02d}-{spec.child_id}")
            elif plan_row.disposition == OWNER_REUSE_CURRENT:
                receipt = reusable[spec.child_id]
                child = child_from_owner_receipt(receipt, receipt_root)
                owner_receipts[spec.child_id] = receipt
            else:
                current = currents[spec.child_id]
                try:
                    with evidence_execution_lease(
                        receipt_root,
                        owner_id=current.contract.owner_id,
                        execution_key=current.owner_identity,
                        plan_id=plan_id,
                    ):
                        locked_current = build_owner_current(
                            root,
                            current.contract,
                            all_contracts=contracts,
                        )
                        if locked_current.owner_identity != current.owner_identity:
                            child = _blocked_child(
                                spec,
                                "owner inputs changed after the frozen plan; re-plan explicitly",
                                output_dir / f"{index:02d}-{spec.child_id}",
                            )
                        else:
                            receipt, _verification = find_reusable_owner_receipt(
                                locked_current,
                                root,
                                receipt_root,
                            )
                            if receipt is not None:
                                child = child_from_owner_receipt(receipt, receipt_root)
                                owner_receipts[spec.child_id] = receipt
                            else:
                                child_started = datetime.now(timezone.utc).isoformat()
                                child = _run_full_child(spec, root, output_dir, index)
                                receipt = save_owner_receipt(
                                    locked_current,
                                    child,
                                    root,
                                    receipt_root,
                                    started_at=child_started,
                                    finished_at=datetime.now(timezone.utc).isoformat(),
                                )
                                owner_receipts[spec.child_id] = receipt
                                child = ValidationChildResult(
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
                                )
                except EvidenceLifecycleError as exc:
                    child = _blocked_child(
                        spec,
                        str(exc),
                        output_dir / f"{index:02d}-{spec.child_id}",
                    )
        except Exception as exc:  # keep an internal child failure visible and continue composition
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
        print(f"DONE {spec.child_id} status={child.status} ({index}/{len(specs)})", file=sys.stderr, flush=True)

    status = aggregate_status(children, required_child_ids=FULL_CHILD_IDS)
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
    skipped = tuple(
        SkippedValidation(
            child.child_id,
            child.summary or "required child did not run",
            "Full/release closure is unavailable.",
            True,
        )
        for child in children
        if child.status == VALIDATION_STATUS_BLOCKED and "not executed" in child.claim_boundary.lower()
    )
    parent_path = output_dir / "result.json"
    parent_receipt = None
    if status == VALIDATION_STATUS_PASS and len(owner_receipts) == len(specs):
        parent_receipt = save_parent_receipt(
            root,
            receipt_root,
            contracts=contracts,
            plan_rows=plan_rows,
            child_receipts=tuple(owner_receipts[spec.child_id] for spec in specs),
            status=status,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
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
            "required": len(FULL_CHILD_IDS),
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
            "Full pass requires exact pass from project adoption, all 15 static/deep skill contracts, "
            "receipt-bound self-governance, manifest full models, pytest, strict OpenSpec, and complete "
            "formal/shadow/installed distribution checks for one frozen owner plan; exact-current prior receipts may be reused."
        ),
        progress_summary={
            "completed": len(children),
            "total": len(FULL_CHILD_IDS),
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
                    / len(FULL_CHILD_IDS)
                ),
                3,
            ),
            "parent_receipt_id": parent_receipt.receipt_id if parent_receipt else "",
            "parent_receipt_fingerprint": parent_receipt.fingerprint if parent_receipt else "",
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
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("static", "full"), default="static")
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument(
        "--skillguard",
        default="all",
        help="'all' for installed SkillGuard or an explicit skillguard.py path",
    )
    parser.add_argument("--member", action="append", default=[], help="Static scope only; repeat to select members")
    parser.add_argument("--output-dir", help="Full-scope parent and child artifact directory")
    parser.add_argument(
        "--receipt-dir",
        help="Persistent native owner receipt/proof store; defaults under .flowguard/evidence",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Freeze and print execute/reuse_current/blocked owner dispositions without running producers",
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
    if args.scope == "static":
        payload = run_static_suite(
            Path(args.root).resolve(),
            skillguard=args.skillguard,
            members=args.member,
        )
        run_id, result_path, result_sha256 = _write_static_result(
            payload,
            args.output_dir,
        )
        _print_static(
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
        invalid_reason = "--member is static-only; full scope always requires all 15 members"
    if invalid_reason:
        result = _command_error(VALIDATION_STATUS_INVALID_INPUT, invalid_reason, scope="full")
        print(
            result.terminal_json_text()
            if args.json
            else result.format_text(full=args.full)
        )
        return result.exit_code
    try:
        result = run_full_validation(args)
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
