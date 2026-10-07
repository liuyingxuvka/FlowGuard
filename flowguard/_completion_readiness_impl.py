"""Internal completion-readiness planner.

This module owns the native readiness planning logic.  The public
``flowguard.completion_readiness`` module owns the stable package/CLI wire
surface; the legacy script is only a compatibility wrapper.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from .completion_epoch import (
    COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
    COMPLETION_DEFAULT_WORK_ID,
    COMPLETION_MAINTENANCE_UNIT_ID,
    CompletionEpochPlan,
    CompletionEpochReadiness,
    CompletionEpochTerminalLedger,
    CompletionRepairAdmissionGroup,
    normalize_completion_claim_scope,
    normalize_completion_maintenance_unit_id,
    normalize_completion_work_id,
    produce_completion_repair_link,
)
from .completion_objective import (
    CompletionObjectiveError,
    require_archived_completion_objective,
    resolve_completion_objective,
)
from .completion_run_manifest import build_manifest, write_manifest
from .evidence_lifecycle import fingerprint_payload
from .model_authority import ModelAuthorityError
from .model_authority_store import (
    _load_bound_read_projection,
    _reject_duplicate_json_keys,
    load_current_model_authority_state,
    load_observed_model_head,
)
from .process_supervision import run_supervised
from .reverse_surface_owner_authority import load_current_reverse_surface_owner_authority
from .validation_ownership import (
    build_validation_owner_plan,
    build_validation_parent_current,
    observe_validation_owners,
)
from scripts import check_flowguard_skill_suite as suite


class CompletionReadinessError(RuntimeError):
    """A readiness input could not be independently proved current."""


def _is_reparse_point(path: Path) -> bool:
    """Check links and Windows reparse points without following the entry."""

    if path.is_symlink():
        return True
    try:
        details = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise CompletionReadinessError(
            f"completion_read_request_invalid: cannot inspect {path}: {exc}"
        ) from exc
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return bool(int(getattr(details, "st_file_attributes", 0)) & reparse_attribute)


def _validate_current_read_request(root: Path) -> dict[str, Any]:
    """Require the fixed project-audit request to select every current model."""

    path = root / ".flowguard" / "read-request.json"
    guard_root = path.parent
    if not guard_root.exists() and not guard_root.is_symlink():
        raise CompletionReadinessError(
            f"completion_read_request_missing: request directory is absent: {guard_root}"
        )
    try:
        if _is_reparse_point(guard_root) or not guard_root.is_dir():
            raise CompletionReadinessError(
                "completion_read_request_invalid: request directory must be a real, "
                "non-reparse directory"
            )
        if not path.exists() and not path.is_symlink():
            raise CompletionReadinessError(
                f"completion_read_request_missing: required project input is absent: {path}"
            )
        if _is_reparse_point(path) or not stat.S_ISREG(
            os.stat(path, follow_symlinks=False).st_mode
        ):
            raise CompletionReadinessError(
                "completion_read_request_invalid: fixed request must be a regular, "
                "non-symlink, non-reparse file"
            )
        raw = path.read_text(encoding="utf-8")
    except CompletionReadinessError:
        raise
    except (OSError, UnicodeError) as exc:
        raise CompletionReadinessError(
            f"completion_read_request_invalid: cannot read fixed request: {exc}"
        ) from exc
    try:
        request = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
    except ValueError as exc:
        raise CompletionReadinessError(
            f"completion_read_request_invalid: fixed request is not JSON: {exc}"
        ) from exc
    if not isinstance(request, Mapping) or set(request) != {
        "operation",
        "target_id",
        "scope",
    }:
        raise CompletionReadinessError(
            "completion_read_request_invalid: fields must be exactly operation, "
            "target_id, and scope"
        )
    if request.get("operation") != "read":
        raise CompletionReadinessError(
            "completion_read_request_invalid: operation must be read"
        )
    target_id = request.get("target_id")
    scope = request.get("scope")
    if not isinstance(target_id, str) or not target_id.strip():
        raise CompletionReadinessError(
            "completion_read_request_invalid: target_id must be a non-empty string"
        )
    if not isinstance(scope, list) or not scope or any(
        not isinstance(item, str) or not item.strip() for item in scope
    ):
        raise CompletionReadinessError(
            "completion_read_request_invalid: scope must be a non-empty model ID array"
        )
    if len(scope) != len(set(scope)):
        raise CompletionReadinessError(
            "completion_read_request_invalid: scope contains duplicate model IDs"
        )
    try:
        head = load_observed_model_head(root)
        projection = _load_bound_read_projection(root, head)
    except (ModelAuthorityError, OSError, ValueError, KeyError, TypeError) as exc:
        raise CompletionReadinessError(
            f"completion_read_request_invalid: current bound model index is unavailable: {exc}"
        ) from exc
    if target_id != head.system_id:
        raise CompletionReadinessError(
            "completion_read_request_target_mismatch: target_id does not match "
            "the current observed model head"
        )
    model_index = projection.get("index", {}).get("models")
    if not isinstance(model_index, Mapping) or not model_index:
        raise CompletionReadinessError(
            "completion_read_request_invalid: current bound model index is empty"
        )
    expected_scope = sorted(str(model_id) for model_id in model_index)
    if scope != expected_scope:
        raise CompletionReadinessError(
            "completion_read_request_scope_mismatch: scope must be the sorted, "
            "complete current bound model index"
        )
    return {
        "path": str(path),
        "target_id": target_id,
        "scope": list(scope),
        "head_fingerprint": head.fingerprint,
        "read_projection_index_fingerprint": str(
            projection.get("index_fingerprint", "")
        ),
    }


def _require_archived_completion_objective(
    root: Path,
    change_name: str,
) -> Any:
    """Resolve the named objective with the canonical resolver, then require archive state."""

    try:
        return require_archived_completion_objective(root, change_name)
    except CompletionObjectiveError as exc:
        raise CompletionReadinessError(str(exc)) from exc


def validate_preflight_inputs(
    args: argparse.Namespace,
    root: Path,
) -> dict[str, Any]:
    """Validate release state and fixed project input before owners or outputs."""

    claim_scope = normalize_completion_claim_scope(
        getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
    )
    author_state_value = getattr(args, "author_state_root", None)
    if claim_scope == "release" or (
        author_state_value is not None and str(author_state_value).strip()
    ):
        try:
            args.author_state_root = str(
                suite._validate_author_state_root(root, author_state_value)
            )
        except (OSError, ValueError, TypeError) as exc:
            raise CompletionReadinessError(str(exc)) from exc
    else:
        args.author_state_root = ""

    objective_name = str(
        getattr(args, "completion_objective_change", "")
        or getattr(args, "objective_change", "")
        or ""
    ).strip()
    objective = None
    if claim_scope == "release":
        if not objective_name:
            raise CompletionReadinessError(
                "completion_objective_missing: release readiness requires "
                "--completion-objective-change"
            )
        objective = _require_archived_completion_objective(root, objective_name)

    read_request = _validate_current_read_request(root)
    return {
        "claim_scope": claim_scope,
        "author_state_root": str(getattr(args, "author_state_root", "") or ""),
        "objective": objective.to_dict() if objective is not None else None,
        "read_request": read_request,
    }


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_value(value: Any) -> Any:
    """Return a JSON-safe bounded projection for a gate sidecar."""

    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _semantic_value(value: Any) -> Any:
    """Project gate output for identity without deleting business fields.

    OpenSpec emits ``durationMs`` diagnostics inside item records.  That field
    is execution timing, not gate meaning.  Only this exact field is removed;
    fields such as ``timestamp``, ``status``, ``subject`` and ``issues`` stay
    semantic because a domain payload may use them as business identity.
    """

    if isinstance(value, Mapping):
        return {
            str(key): _semantic_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) != "durationMs"
        }
    if isinstance(value, (list, tuple)):
        return [_semantic_value(item) for item in value]
    return value


def _json_ok(stdout: str, *, gate_id: str) -> dict[str, Any]:
    """Parse a native JSON result when available and reject explicit failure."""

    text = str(stdout or "").strip()
    if not text:
        raise CompletionReadinessError(f"{gate_id} produced no terminal output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CompletionReadinessError(
            f"{gate_id} did not produce the required JSON gate envelope"
        ) from exc
    if not isinstance(payload, Mapping):
        raise CompletionReadinessError(f"{gate_id} JSON gate envelope must be an object")
    for key in ("ok", "success"):
        if key in payload and payload[key] is False:
            raise CompletionReadinessError(f"{gate_id} reported {key}=false")
    status = str(payload.get("status", "")).strip().lower()
    if status in {"blocked", "fail", "failed", "error", "invalid", "partial", "not_run", "not-run"}:
        raise CompletionReadinessError(f"{gate_id} reported terminal status {status}")
    return {"format": "json", "payload": _canonical_value(payload)}


def _run_gate(root: Path, gate_id: str, command: Sequence[str], *, timeout: float) -> dict[str, Any]:
    """Run one bounded native gate and derive its content fingerprint."""

    result = run_supervised(command, cwd=root, timeout_seconds=timeout)
    if result.exit_code != 0:
        raise CompletionReadinessError(
            f"{gate_id} exited with {result.exit_code}: {result.stderr[-500:]}"
        )
    if not result.cleanup_confirmed or result.timed_out or result.cancelled or result.interrupted:
        raise CompletionReadinessError(
            f"{gate_id} did not settle cleanly ({result.terminal_reason})"
        )
    parsed = _json_ok(result.stdout, gate_id=gate_id)
    semantic = {
        "schema_version": "flowguard.completion_readiness_gate.v1",
        "gate_id": gate_id,
        "command": [str(item) for item in command],
        "cwd": str(root),
        "exit_code": result.exit_code,
        "terminal_reason": result.terminal_reason,
        "cleanup_confirmed": result.cleanup_confirmed,
        "parsed": _semantic_value(parsed),
    }
    diagnostics = {
        "stdout_sha256": _sha256_text(result.stdout),
        "stderr_sha256": _sha256_text(result.stderr),
        "elapsed_seconds": round(
            max(0.0, result.finished_at_epoch - result.started_at_epoch),
            6,
        ),
        "terminal_reason": result.terminal_reason,
    }
    return {
        **semantic,
        "diagnostics": diagnostics,
        "gate_fingerprint": fingerprint_payload(semantic),
    }


def _assert_current_read_gate(
    gate: Mapping[str, Any],
    *,
    read_request: Mapping[str, Any],
    expected_head_fingerprint: str,
) -> None:
    """Require the public read gate to cover the exact current full selection.

    The read response may paginate its detailed model map.  Its
    ``selected_source_currentness`` and ``selected_model_ids`` fields summarize
    the complete requested selection before that page projection, so this gate
    can verify the full currentness boundary without replaying every page.
    """

    parsed = gate.get("parsed")
    payload = parsed.get("payload") if isinstance(parsed, Mapping) else None
    if not isinstance(payload, Mapping):
        raise CompletionReadinessError(
            "current-read did not contain the public FlowGuard read result"
        )
    if payload.get("operation") != "read" or payload.get("status") != "pass":
        raise CompletionReadinessError(
            "current-read did not return a passing public read operation"
        )
    if payload.get("target_id") != read_request.get("target_id"):
        raise CompletionReadinessError(
            "current-read target differs from the preflighted project request"
        )
    expected_scope = read_request.get("scope")
    if (
        not isinstance(expected_scope, list)
        or payload.get("requested_model_ids") != expected_scope
        or payload.get("selected_model_ids") != expected_scope
    ):
        raise CompletionReadinessError(
            "current-read selection differs from the complete preflighted model scope"
        )
    if payload.get("authority_integrity") != "pass":
        raise CompletionReadinessError(
            "current-read authority integrity is not pass"
        )
    if payload.get("selected_source_currentness") != "current":
        raise CompletionReadinessError(
            "current-read selected source currentness is not current"
        )
    stale_obligations = payload.get("stale_obligations")
    if not isinstance(stale_obligations, list) or stale_obligations:
        raise CompletionReadinessError(
            "current-read has missing or non-empty stale obligations"
        )
    if payload.get("blockers") != []:
        raise CompletionReadinessError("current-read contains blockers")
    if payload.get("execution_evidence_status") != "not_run":
        raise CompletionReadinessError(
            "current-read must remain producer-free"
        )
    if payload.get("producer_count") != 0 or payload.get("write_count") != 0:
        raise CompletionReadinessError(
            "current-read must not start producers or write evidence"
        )
    if read_request.get("head_fingerprint") != expected_head_fingerprint:
        raise CompletionReadinessError(
            "current-read request authority changed after preflight"
        )
    as_of = payload.get("as_of")
    observed_head = (
        as_of.get("authority_head_fingerprint")
        if isinstance(as_of, Mapping)
        else None
    )
    if observed_head != expected_head_fingerprint:
        raise CompletionReadinessError(
            "current-read authority head differs from the frozen current authority"
        )


def _not_applicable_gate(gate_id: str, *, claim_scope: str) -> dict[str, Any]:
    """Record one explicitly out-of-scope gate without launching a producer.

    Local functional completion must not require a formal/shadow/installed
    release tree.  The readiness wire format still carries those historical
    fields, so represent their boundary as a deterministic non-applicable
    gate rather than inventing a green release receipt or running parity.
    """

    semantic = {
        "schema_version": "flowguard.completion_readiness_gate.v1",
        "gate_id": gate_id,
        "claim_scope": claim_scope,
        "status": "not_applicable",
        "claim_boundary": (
            "This gate is outside a local functional claim; no release-tree, "
            "installation, or parity producer was launched."
        ),
    }
    return {
        **semantic,
        "diagnostics": {"producer_invocations": 0, "terminal_reason": "not_applicable"},
        "gate_fingerprint": fingerprint_payload(semantic),
    }


def _base_suite_args(args: argparse.Namespace, root: Path) -> argparse.Namespace:
    values: list[str] = ["--scope", "full", "--root", str(root), "--plan-only"]
    if args.formal_root:
        values.extend(("--formal-root", str(args.formal_root)))
    if args.shadow_root:
        values.extend(("--shadow-root", str(args.shadow_root)))
    if args.installed_root:
        values.extend(("--installed-root", str(args.installed_root)))
    if args.receipt_dir:
        values.extend(("--receipt-dir", str(args.receipt_dir)))
    if getattr(args, "model_receipt_dir", None):
        values.extend(("--model-receipt-dir", str(args.model_receipt_dir)))
    if getattr(args, "model_parent_receipt", None):
        values.extend(("--model-parent-receipt", str(args.model_parent_receipt)))
    if getattr(args, "completion_run_manifest", None):
        values.extend(("--completion-run-manifest", str(args.completion_run_manifest)))
    if getattr(args, "author_state_root", None):
        values.extend(("--author-state-root", str(args.author_state_root)))
    if getattr(args, "completion_authorization", None):
        values.extend(("--completion-authorization", str(args.completion_authorization)))
    if args.completion_repair_link:
        values.extend(("--completion-repair-link", str(args.completion_repair_link)))
    objective_change = getattr(args, "completion_objective_change", "") or getattr(
        args, "objective_change", ""
    )
    if objective_change:
        values.extend(
            (
                "--completion-objective-change",
                str(objective_change),
            )
        )
    parsed = suite.build_parser().parse_args(values)
    parsed.skillguard = args.skillguard
    parsed.model_jobs = args.model_jobs
    parsed.model_timeout = args.model_timeout
    parsed.gate_timeout = args.gate_timeout
    parsed.require_executed_evidence = bool(
        getattr(args, "require_executed_evidence", False)
    )
    parsed.maintenance_unit_id = normalize_completion_maintenance_unit_id(
        getattr(args, "maintenance_unit_id", COMPLETION_MAINTENANCE_UNIT_ID)
    )
    parsed.completion_work_id = normalize_completion_work_id(
        getattr(args, "completion_work_id", COMPLETION_DEFAULT_WORK_ID)
    )
    parsed.claim_scope = normalize_completion_claim_scope(
        getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
    )
    parsed.completion_authorization = str(
        getattr(args, "completion_authorization", "") or ""
    )
    parsed.output_dir = str(root / ".flowguard" / "evidence" / "completion-readiness" / "__PLAN_ONLY__")
    return parsed


def _load_repair_regression_evidence(path_value: str | Path, root: Path) -> dict[str, Any]:
    """Load the source-bound targeted regression artifact without producing it."""

    path = Path(path_value).expanduser().resolve()
    if root not in path.parents:
        raise CompletionReadinessError(
            "--repair-regression-evidence must remain inside the repository root"
        )
    if path.is_symlink() or not path.is_file():
        raise CompletionReadinessError(
            "--repair-regression-evidence must be a regular non-symlink file"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompletionReadinessError(
            f"repair regression evidence is unreadable: {path}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise CompletionReadinessError("repair regression evidence must be a JSON object")
    scope = str(payload.get("scope", "")).strip().lower()
    if scope not in {"patch_regression", "targeted_patch_regression"}:
        raise CompletionReadinessError(
            "repair regression evidence scope must be patch_regression"
        )
    if "status" not in payload:
        raise CompletionReadinessError("repair regression evidence status is missing")
    status = str(payload.get("status", "")).strip().lower()
    if status not in {"pass", "passed", "success"}:
        raise CompletionReadinessError(
            f"repair regression evidence is not a pass: {status or 'missing'}"
        )
    if "exit_code" in payload and payload["exit_code"] != 0:
        raise CompletionReadinessError("repair regression evidence exit_code is not zero")
    if payload.get("cleanup_confirmed", True) is not True:
        raise CompletionReadinessError("repair regression evidence cleanup is not confirmed")
    if payload.get("skipped", False) is True:
        raise CompletionReadinessError("repair regression evidence is skipped")
    tested = payload.get("tested_input_manifest", payload.get("input_fingerprint"))
    if tested in (None, "", [], {}):
        raise CompletionReadinessError(
            "repair regression evidence is not bound to a tested input manifest"
        )
    return {str(key): value for key, value in payload.items()}


def _prepare_repair_admission(
    *,
    args: argparse.Namespace,
    root: Path,
    current_plan: CompletionEpochPlan,
    output_dir: Path,
) -> tuple[CompletionEpochPlan, CompletionEpochTerminalLedger, Path, Path]:
    """Construct one repair group/link in memory and bind the repaired plan.

    No reservation or terminal ledger is written here.  The full consumer
    reloads the same canonical group again before it claims the only remaining
    producer attempt.
    """

    previous_epoch_id = str(getattr(args, "repair_from_epoch", "") or "").strip()
    evidence_path = str(getattr(args, "repair_regression_evidence", "") or "").strip()
    if not previous_epoch_id or not evidence_path:
        raise CompletionReadinessError(
            "repair admission requires --repair-from-epoch and --repair-regression-evidence"
        )
    try:
        from scripts.prepare_completion_repair import (  # noqa: PLC0415
            prepare_completion_repair_admission,
        )

        result = prepare_completion_repair_admission(
            root=root,
            previous_epoch_id=previous_epoch_id,
            current_plan=current_plan,
            repair_regression_evidence=evidence_path,
            output_dir=output_dir,
            observation=getattr(args, "repair_observation", None),
            owner_plan=getattr(args, "repair_owner_plan", None),
        )
    except (OSError, TypeError, ValueError, KeyError, OverflowError) as exc:
        raise CompletionReadinessError(str(exc)) from exc
    return (
        result["repaired_plan"],
        result["previous_ledger"],
        Path(result["repair_link_path"]),
        Path(result["repair_group_path"]),
    )


def _freeze_plan(
    args: argparse.Namespace,
    root: Path,
) -> tuple[CompletionEpochPlan, Any, Any, Any, Path, Any | None]:
    specs = suite._full_child_specs(args, root)
    contracts = suite._owner_contracts(specs)
    receipt_root = (
        Path(args.receipt_dir).expanduser().resolve()
        if args.receipt_dir
        else root / ".flowguard" / "evidence" / "validation-owners"
    )
    external = {
        component_id: fingerprint
        for contract in contracts
        for component_id, fingerprint in contract.external_component_bindings
    }
    observation = observe_validation_owners(root, contracts, receipt_root=receipt_root)
    from .self_blueprint import validate_completion_source_prerequisites

    try:
        validate_completion_source_prerequisites(
            root,
            resolved_manifest=observation.repository_input_manifest,
            model_receipt_dir=getattr(args, "model_receipt_dir", None),
        )
    except (OSError, TypeError, ValueError) as exc:
        raise CompletionReadinessError(str(exc)) from exc
    owner_plan = build_validation_owner_plan(
        root,
        contracts,
        receipt_root=receipt_root,
        required_external_components=external,
        observation=observation,
        claim_scope=normalize_completion_claim_scope(
            getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
        ),
    )
    if owner_plan.blocked:
        reasons = "; ".join(
            f"{row.owner_id}:{row.reason}"
            for row in owner_plan.rows
            if row.disposition == "blocked"
        )
        raise CompletionReadinessError(f"owner plan is blocked: {reasons}")
    parent_current = build_validation_parent_current(
        root,
        owner_plan,
        frozen_validation_manifest=owner_plan.validation_input_manifest,
        frozen_release_tree_manifest=owner_plan.release_tree_manifest,
    )
    completion_epoch = suite._completion_epoch_plan(
        args=args,
        root=root,
        specs=specs,
        owner_plan=owner_plan,
        parent_current=parent_current,
        planning_observation=observation,
    )
    # The native suite planner is shared with legacy callers and may return a
    # plan using its compatibility defaults.  Bind the public completion
    # scope after the single native observation so the epoch and its cycle
    # budget use the explicit work identity supplied by this invocation.
    completion_epoch = replace(
        completion_epoch,
        maintenance_unit_id=normalize_completion_maintenance_unit_id(
            getattr(args, "maintenance_unit_id", COMPLETION_MAINTENANCE_UNIT_ID)
        ),
        completion_work_id=normalize_completion_work_id(
            getattr(args, "completion_work_id", COMPLETION_DEFAULT_WORK_ID)
        ),
        claim_scope=normalize_completion_claim_scope(
            getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
        ),
        # The compatibility suite planner currently derives its plan with
        # legacy/default scope fields.  Clear the derived cycle fields before
        # rebinding the explicit work identity; otherwise dataclasses.replace
        # would compare the old seed/cycle (for the legacy work id) with the
        # new work id and reject a valid first entry.  CompletionEpochPlan
        # deterministically re-derives both from maintenance unit + work id.
        completion_cycle_seed_fingerprint="",
        completion_cycle_id="",
    )
    completion_epoch, previous_ledger, repair_error = suite._apply_completion_repair(
        completion_epoch,
        args=args,
        root=root,
    )
    if repair_error:
        raise CompletionReadinessError(repair_error)
    if not completion_epoch.final_ready:
        raise CompletionReadinessError("completion epoch still has governed writes or is not final-ready")
    return (
        completion_epoch,
        owner_plan,
        parent_current,
        observation,
        receipt_root,
        previous_ledger,
    )


def produce(
    args: argparse.Namespace,
    *,
    preflight_inputs: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise CompletionReadinessError(f"root is not a directory: {root}")
    if preflight_inputs is None:
        preflight_inputs = validate_preflight_inputs(args, root)
    read_request = preflight_inputs.get("read_request")
    if not isinstance(read_request, Mapping):
        raise CompletionReadinessError(
            "current-read preflight did not preserve the exact project request"
        )
    claim_scope = normalize_completion_claim_scope(
        getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
    )
    if claim_scope == "release" and not args.shadow_root:
        raise CompletionReadinessError(
            "--shadow-root is required for an explicit release claim"
        )
    manifest_path = (
        Path(args.completion_run_manifest).expanduser().resolve()
        if getattr(args, "completion_run_manifest", "")
        else Path(args.output_dir).expanduser().resolve()
        / "completion-run-manifest.json"
    )
    if root not in manifest_path.parents and manifest_path != root:
        raise CompletionReadinessError(
            "--completion-run-manifest must remain inside the repository root"
        )
    # Freeze native consumers against the same manifest path that is written
    # after readiness and repair admission; no provisional manifest is created.
    args.completion_run_manifest = str(manifest_path)
    suite_args = _base_suite_args(args, root)
    (
        completion_epoch,
        owner_plan,
        parent_current,
        observation,
        receipt_root,
        previous_ledger,
    ) = _freeze_plan(suite_args, root)

    formal = (
        Path(args.formal_root).expanduser().resolve()
        if args.formal_root
        else root / ".agents" / "skills"
    )
    shadow = (
        Path(args.shadow_root).expanduser().resolve()
        if args.shadow_root
        else None
    )
    installed = (
        Path(args.installed_root).expanduser().resolve()
        if args.installed_root
        else Path.home() / ".codex" / "skills"
    )
    if claim_scope == "release" and (
        not formal.is_dir()
        or shadow is None
        or not shadow.is_dir()
        or not installed.is_dir()
    ):
        raise CompletionReadinessError(
            "formal, shadow, and installed roots must all exist for a release claim"
        )

    openspec = shutil.which("openspec") or "openspec"
    gates: dict[str, dict[str, Any]] = {}
    gates["openspec"] = _run_gate(
        root,
        "openspec-terminal",
        (openspec, "validate", "--all", "--strict", "--json", "--no-interactive"),
        timeout=args.gate_timeout,
    )
    if claim_scope == "release":
        assert shadow is not None
        gates["distribution_parity"] = _run_gate(
            root,
            "formal-shadow-installed-parity",
            (
                sys.executable,
                str(root / "scripts" / "install_flowguard_skills.py"),
                "parity",
                "--source",
                str(root),
                "--formal",
                str(formal),
                "--shadow",
                str(shadow),
                "--installed",
                str(installed),
                "--json",
            ),
            timeout=args.gate_timeout,
        )
    else:
        gates["distribution_parity"] = _not_applicable_gate(
            "formal-shadow-installed-parity",
            claim_scope=claim_scope,
        )

    authority_state = load_current_model_authority_state(root)
    authority_identity = {
        "activation_receipt_fingerprint": authority_state.head.activation_receipt_fingerprint,
        "head_fingerprint": authority_state.head.fingerprint,
        "revision_set_fingerprint": authority_state.accepted_revision.fingerprint if authority_state.accepted_revision else "",
        "snapshot_fingerprint": authority_state.snapshot.fingerprint,
    }
    reverse = load_current_reverse_surface_owner_authority(
        root,
        authority_identity=authority_identity,
    )
    reverse_body = {
        "schema_version": "flowguard.completion_readiness_reverse_gate.v1",
        "authority_identity": authority_identity,
        "authority_artifact_fingerprint": reverse["authority_artifact_fingerprint"],
        "discovery_fingerprint": reverse["discovery_fingerprint"],
        "discovered_surface_count": reverse["discovered_surface_count"],
        "owner_routes": reverse["owner_routes"],
        "owner_receipt_identities": reverse["owner_receipt_identities"],
    }
    gates["reverse_input"] = {
        **reverse_body,
        "gate_fingerprint": fingerprint_payload(reverse_body),
    }

    current_read = _run_gate(
        root,
        "current-read",
        (
            sys.executable,
            "-m",
            "flowguard",
            "read",
            "--root",
            str(root),
            "--request",
            str(root / ".flowguard" / "read-request.json"),
            "--json",
        ),
        timeout=args.gate_timeout,
    )
    _assert_current_read_gate(
        current_read,
        read_request=read_request,
        expected_head_fingerprint=authority_identity["head_fingerprint"],
    )
    owner_body = {
        "schema_version": "flowguard.completion_readiness_owner_dag.v1",
        "owner_plan_fingerprint": owner_plan.plan_fingerprint,
        "parent_identity": parent_current.parent_identity,
        "source_observation_fingerprint": observation.source_observation_fingerprint,
        "owner_ids": [contract.owner_id for contract in owner_plan.contracts],
        "dependency_edges": [
            [contract.owner_id, dependency]
            for contract in owner_plan.contracts
            for dependency in contract.dependency_owner_ids
        ],
        "current_read_gate_fingerprint": current_read["gate_fingerprint"],
    }
    gates["owner_dag"] = {**owner_body, "gate_fingerprint": fingerprint_payload(owner_body)}
    gates["current_read"] = current_read

    repair_link_path = ""
    repair_group_path = ""
    repair_from_epoch = str(getattr(args, "repair_from_epoch", "") or "").strip()
    repair_regression_evidence = str(
        getattr(args, "repair_regression_evidence", "") or ""
    ).strip()
    if repair_from_epoch or repair_regression_evidence:
        args.repair_observation = observation
        args.repair_owner_plan = owner_plan
        (
            completion_epoch,
            previous_ledger,
            repair_link_file,
            repair_group_file,
        ) = _prepare_repair_admission(
            args=args,
            root=root,
            current_plan=completion_epoch,
            output_dir=Path(args.output_dir).expanduser().resolve(),
        )
        repair_link_path = str(repair_link_file)
        repair_group_path = str(repair_group_file)
        # The manifest is the handoff to the full consumer.  Keep the exact
        # typed link path in memory; no new producer/ledger is started here.
        args.completion_repair_link = repair_link_path

    readiness = CompletionEpochReadiness.for_plan(
        completion_epoch,
        openspec_terminal_receipt_fingerprint=gates["openspec"]["gate_fingerprint"],
        external_roots_sync_receipt_fingerprint=gates["distribution_parity"]["gate_fingerprint"],
        formal_shadow_installed_sync_receipt_fingerprint=gates["distribution_parity"]["gate_fingerprint"],
        reverse_input_acceptance_receipt_fingerprint=gates["reverse_input"]["gate_fingerprint"],
        owner_dag_freeze_receipt_fingerprint=gates["owner_dag"]["gate_fingerprint"],
        previous_aborted_epoch_ledger_fingerprint=(
            previous_ledger.fingerprint if previous_ledger is not None else ""
        ),
    )
    manifest_specs = suite._full_child_specs(suite_args, root)
    manifest = build_manifest(
        args=args,
        root=root,
        receipt_root=receipt_root,
        specs=manifest_specs,
        owner_plan=owner_plan,
        completion_epoch=completion_epoch,
        canonicalize_command=suite.canonical_semantic_command,
        readiness_fingerprint=readiness.fingerprint,
    )
    written_manifest = write_manifest(manifest_path, manifest)
    evidence = {
        "schema_version": "flowguard.completion_readiness_evidence.v1",
        "readiness_fingerprint": readiness.fingerprint,
        "epoch_id": completion_epoch.epoch_id,
        "completion_cycle_id": completion_epoch.completion_cycle_id,
        "maintenance_unit_id": completion_epoch.maintenance_unit_id,
        "completion_work_id": completion_epoch.completion_work_id,
        "claim_scope": completion_epoch.claim_scope,
        "completion_epoch_attempt_index": completion_epoch.attempt_index,
        "plan_fingerprint": owner_plan.plan_fingerprint,
        "receipt_root": str(receipt_root),
        "completion_run_manifest_path": str(written_manifest),
        "completion_run_manifest_fingerprint": manifest["manifest_fingerprint"],
        "completion_repair_link_path": repair_link_path,
        "completion_repair_group_path": repair_group_path,
        "gates": gates,
        "claim_boundary": (
            "Pre-parent readiness only: each gate is independently terminal and current for the frozen epoch. "
            "This artifact does not claim that any full validation child or parent has executed."
        ),
    }
    return readiness.to_dict(), evidence



# Compatibility name retained for callers that imported the old helper.
ReadinessError = CompletionReadinessError

__all__ = ["CompletionReadinessError", "ReadinessError", "produce"]
