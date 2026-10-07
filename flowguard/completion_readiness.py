"""Private author-side completion-readiness producer.

This command delegates to the existing native completion planner used by the
full suite. It adapts the command-line envelope and writes bounded readiness
and evidence objects idempotently; it is not a fourth public FlowGuard
lifecycle operation and never launches the heavy validation DAG.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .completion_epoch import (
    COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
    COMPLETION_MAINTENANCE_UNIT_ID,
    normalize_completion_claim_scope,
    normalize_completion_maintenance_unit_id,
    normalize_completion_work_id,
)


class CompletionReadinessError(RuntimeError):
    """A readiness request cannot be independently proved current."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/prepare_flowguard_completion_readiness.py",
        description=(
            "Prepare one private, plan-bound completion-readiness envelope. "
            "This is an author-side producer, not a public FlowGuard lifecycle operation."
        ),
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--objective-change", default="")
    parser.add_argument(
        "--completion-work-id",
        help=(
            "Stable identity for this maintenance task. It owns one initial "
            "full attempt and at most one typed repair."
        ),
    )
    parser.add_argument(
        "--maintenance-unit-id",
        default=COMPLETION_MAINTENANCE_UNIT_ID,
        help="Stable maintenance namespace for the finite completion budget.",
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
        choices=("local_validation", "release"),
        default=COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
        help=(
            "Evidence boundary for the completion claim; ordinary completion "
            "uses local_validation and release must be explicit."
        ),
    )
    parser.add_argument(
        "--completion-objective-change",
        help=(
            "Named current OpenSpec change whose reviewed artifacts derive the "
            "explicit completion objective identity"
        ),
    )
    parser.add_argument("--completion-repair-link")
    parser.add_argument(
        "--repair-from-epoch",
        help=(
            "Aborted predecessor epoch whose typed repair admission is to be "
            "constructed in memory before readiness is written."
        ),
    )
    parser.add_argument(
        "--repair-regression-evidence",
        help="Source-bound targeted regression evidence for one repair admission.",
    )
    parser.add_argument("--receipt-dir")
    parser.add_argument("--model-receipt-dir")
    parser.add_argument(
        "--author-state-root",
        help=(
            "Existing persistent external SkillGuard author state. Required for "
            "release readiness and frozen into the readiness-to-full manifest."
        ),
    )
    parser.add_argument(
        "--model-parent-receipt",
        help=(
            "Exact typed current full-model parent artifact to verify through "
            "the read-only model child route; no historical scan is allowed."
        ),
    )
    parser.add_argument("--formal-root")
    parser.add_argument(
        "--shadow-root",
        help=(
            "Shadow skills root for an explicit release claim. Local functional "
            "validation intentionally does not require a shadow/install tree."
        ),
    )
    parser.add_argument("--installed-root")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--completion-run-manifest",
        help=(
            "Optional path for the immutable readiness-to-full invocation "
            "manifest; defaults to completion-run-manifest.json in output-dir."
        ),
    )
    parser.add_argument("--gate-timeout", type=float, default=900.0)
    parser.add_argument("--model-jobs", type=int, default=1)
    parser.add_argument("--model-timeout", type=float)
    parser.add_argument(
        "--require-executed-evidence",
        action="store_true",
        help=(
            "Freeze the readiness plan with the same strict native model-owner "
            "and direct-leaf evidence requirement used by the final parent."
        ),
    )
    parser.add_argument("--skillguard", default="all")
    parser.add_argument("--json", action="store_true")
    return parser


def _write_once(path: Path, payload: Mapping[str, Any]) -> None:
    data = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.is_symlink():
        raise CompletionReadinessError(f"readiness output must not be a symlink: {path}")
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CompletionReadinessError(f"cannot read existing readiness output: {path}") from exc
        if existing != data:
            raise CompletionReadinessError(f"readiness output already exists with different content: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def _validate_cached_readiness_identity(
    args: argparse.Namespace,
    *,
    root: Path,
    output_dir: Path,
    preflight_inputs: Mapping[str, Any],
    evidence: Mapping[str, Any],
    loaded_readiness: Any,
) -> tuple[Path, Mapping[str, Any]]:
    """Admit an immutable cached envelope only for its exact current inputs."""

    from ._completion_readiness_impl import (  # noqa: PLC0415
        CompletionReadinessError as NativeCompletionReadinessError,
        _assert_current_read_gate,
        _base_suite_args,
    )
    from .completion_epoch import COMPLETION_CYCLE_SCHEMA
    from .completion_objective import (
        CompletionObjectiveError,
        resolve_completion_objective,
    )
    from .evidence_lifecycle import fingerprint_payload
    from .evidence_receipts import fingerprint_value
    from scripts import check_flowguard_skill_suite as suite

    def blocked(detail: str) -> None:
        raise CompletionReadinessError(f"existing readiness is stale or invalid: {detail}")

    readiness_fingerprint = loaded_readiness.fingerprint
    if evidence.get("readiness_fingerprint") != readiness_fingerprint:
        blocked("readiness and evidence fingerprints differ")

    raw_manifest_path = evidence.get("completion_run_manifest_path")
    if not isinstance(raw_manifest_path, str) or not raw_manifest_path.strip():
        blocked("completion run manifest path is missing")
    manifest_candidate = Path(raw_manifest_path).expanduser()
    if manifest_candidate.is_symlink():
        blocked("completion run manifest must not be a symlink")
    manifest_path = manifest_candidate.resolve()
    expected_manifest_path = (
        Path(args.completion_run_manifest).expanduser().resolve()
        if getattr(args, "completion_run_manifest", "")
        else output_dir / "completion-run-manifest.json"
    )
    if root not in manifest_path.parents or manifest_path != expected_manifest_path:
        blocked("completion run manifest path differs from the current output contract")
    suite_args = _base_suite_args(args, root)
    suite_args.completion_run_manifest = str(manifest_path)
    receipt_root = (
        Path(suite_args.receipt_dir).expanduser().resolve()
        if suite_args.receipt_dir
        else root / ".flowguard" / "evidence" / "validation-owners"
    )
    manifest, _loaded_path, manifest_error, _manifest_differences = (
        suite._load_completion_run_manifest(suite_args, root, receipt_root)
    )
    if manifest_error or not isinstance(manifest, Mapping):
        blocked(f"completion run manifest cannot be verified: {manifest_error or 'invalid manifest'}")
    if manifest.get("manifest_fingerprint") != evidence.get(
        "completion_run_manifest_fingerprint"
    ):
        blocked("completion run manifest fingerprint differs from its evidence pointer")
    manifest_plan = manifest.get("plan")
    if not isinstance(manifest_plan, Mapping):
        blocked("completion run manifest plan is missing")
    if manifest_plan.get("readiness_fingerprint") != readiness_fingerprint:
        blocked("completion run manifest does not bind this readiness fingerprint")

    gate_map = evidence.get("gates")
    if not isinstance(gate_map, Mapping):
        blocked("completion readiness gates are missing")
    current_read = gate_map.get("current_read")
    owner_dag = gate_map.get("owner_dag")
    if not isinstance(current_read, Mapping) or not isinstance(owner_dag, Mapping):
        blocked("current-read or owner-DAG gate is missing")

    current_read_fields = (
        "schema_version",
        "gate_id",
        "command",
        "cwd",
        "exit_code",
        "terminal_reason",
        "cleanup_confirmed",
        "parsed",
    )
    if any(field not in current_read for field in current_read_fields):
        blocked("current-read gate semantic fields are incomplete")
    expected_read_command = [
        sys.executable,
        "-m",
        "flowguard",
        "read",
        "--root",
        str(root),
        "--request",
        str(root / ".flowguard" / "read-request.json"),
        "--json",
    ]
    read_semantic = {field: current_read[field] for field in current_read_fields}
    if (
        current_read.get("schema_version") != "flowguard.completion_readiness_gate.v1"
        or current_read.get("gate_id") != "current-read"
        or current_read.get("command") != expected_read_command
        or current_read.get("cwd") != str(root)
        or current_read.get("exit_code") != 0
        or current_read.get("cleanup_confirmed") is not True
        or not str(current_read.get("terminal_reason", "")).strip()
        or current_read.get("gate_fingerprint") != fingerprint_payload(read_semantic)
    ):
        blocked("current-read gate identity or fingerprint is invalid")

    owner_dag_fields = (
        "schema_version",
        "owner_plan_fingerprint",
        "parent_identity",
        "source_observation_fingerprint",
        "owner_ids",
        "dependency_edges",
        "current_read_gate_fingerprint",
    )
    if any(field not in owner_dag for field in owner_dag_fields):
        blocked("owner-DAG gate semantic fields are incomplete")
    owner_dag_semantic = {field: owner_dag[field] for field in owner_dag_fields}
    if (
        owner_dag.get("schema_version") != "flowguard.completion_readiness_owner_dag.v1"
        or owner_dag.get("current_read_gate_fingerprint")
        != current_read.get("gate_fingerprint")
        or owner_dag.get("gate_fingerprint") != fingerprint_payload(owner_dag_semantic)
        or owner_dag.get("gate_fingerprint")
        != loaded_readiness.owner_dag_freeze_receipt_fingerprint
    ):
        blocked("current-read gate is not bound to the accepted owner-DAG receipt")

    read_request = preflight_inputs.get("read_request")
    expected_head = (
        read_request.get("head_fingerprint")
        if isinstance(read_request, Mapping)
        else None
    )
    if not isinstance(expected_head, str) or not expected_head:
        blocked("current project read request has no authority head fingerprint")
    try:
        _assert_current_read_gate(
            current_read,
            read_request=read_request,
            expected_head_fingerprint=expected_head,
        )
    except NativeCompletionReadinessError as exc:
        blocked(f"current-read no longer matches the project preflight: {exc}")

    objective_name = str(
        getattr(args, "completion_objective_change", "")
        or getattr(args, "objective_change", "")
        or ""
    ).strip()
    if objective_name:
        current_objective = preflight_inputs.get("objective")
        if isinstance(current_objective, Mapping):
            current_objective_fingerprint = current_objective.get("fingerprint")
        else:
            try:
                current_objective_fingerprint = resolve_completion_objective(
                    root, objective_name
                ).fingerprint
            except (CompletionObjectiveError, OSError, ValueError, TypeError) as exc:
                blocked(f"current completion objective cannot be resolved: {exc}")
        if not isinstance(current_objective_fingerprint, str) or not current_objective_fingerprint:
            blocked("current completion objective fingerprint is missing")
    else:
        required_ids = suite._required_child_ids(suite._full_child_specs(suite_args, root))
        current_objective_fingerprint = fingerprint_value(
            {
                "schema_version": COMPLETION_CYCLE_SCHEMA,
                "required_terminal_action_ids": list(required_ids),
            }
        )
    if manifest_plan.get("completion_objective_fingerprint") != current_objective_fingerprint:
        blocked("completion objective fingerprint changed")

    # The cached gate proves an earlier observation.  Reuse the existing
    # full consumer's read-only planner to check current source, test,
    # toolchain, external roots, owner plan and completion admission.
    # plan_only never launches owners or publishes new evidence.
    suite_args.completion_readiness = str(output_dir / "readiness.json")
    suite_args.completion_run_manifest = str(manifest_path)
    suite_args.plan_only = True
    try:
        current_plan = suite.run_full_validation(suite_args)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        blocked(f"current full plan cannot be verified: {exc}")
    progress = current_plan.progress_summary
    admission = progress.get("completion_epoch_admission", {})
    if (
        current_plan.status != suite.VALIDATION_STATUS_PARTIAL
        or current_plan.scope != "full-plan-only"
        or current_plan.blockers
        or current_plan.counts.get("blocked") != 0
        or progress.get("completed") != 0
        or not isinstance(admission, Mapping)
        or admission.get("status") != "admitted"
        or admission.get("ok") is not True
        or admission.get("blockers") != []
        or progress.get("completion_readiness_fingerprint")
        != readiness_fingerprint
        or current_plan.artifact_paths
    ):
        blocked("current full plan does not admit the cached readiness")
    return manifest_path, manifest


def produce(args: argparse.Namespace) -> dict[str, Any]:
    """Run the existing native readiness planner and publish one envelope."""

    root = Path(args.root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not root.is_dir():
        raise CompletionReadinessError(f"root is not a directory: {root}")
    if root not in output_dir.parents and output_dir != root:
        raise CompletionReadinessError("--output-dir must remain inside the repository root")
    if output_dir.is_symlink():
        raise CompletionReadinessError("--output-dir must not be a symlink")
    raw_work_id = getattr(args, "completion_work_id", None)
    if not isinstance(raw_work_id, str) or not raw_work_id.strip():
        raise CompletionReadinessError(
            "--completion-work-id is required; readiness must re-enter a registered work budget"
        )
    try:
        args.completion_work_id = normalize_completion_work_id(raw_work_id)
        args.maintenance_unit_id = normalize_completion_maintenance_unit_id(
            getattr(args, "maintenance_unit_id", COMPLETION_MAINTENANCE_UNIT_ID)
        )
        args.claim_scope = normalize_completion_claim_scope(
            getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
        )
    except ValueError as exc:
        raise CompletionReadinessError(str(exc)) from exc
    repair_from = str(getattr(args, "repair_from_epoch", "") or "").strip()
    repair_evidence = str(getattr(args, "repair_regression_evidence", "") or "").strip()
    if bool(repair_from) != bool(repair_evidence):
        raise CompletionReadinessError(
            "--repair-from-epoch and --repair-regression-evidence must be supplied together"
        )
    if repair_from and getattr(args, "completion_repair_link", None):
        raise CompletionReadinessError(
            "--repair-from-epoch/--repair-regression-evidence cannot be combined with --completion-repair-link"
        )

    # Check current release-only state and fixed request inputs before either
    # reusing an old envelope or entering the native plan/gate path.  A cached
    # pass must not bypass current admission.
    from ._completion_readiness_impl import (  # noqa: PLC0415
        CompletionReadinessError as NativeCompletionReadinessError,
        validate_preflight_inputs,
    )

    try:
        preflight_inputs = validate_preflight_inputs(args, root)
    except (NativeCompletionReadinessError, OSError, ValueError, TypeError) as exc:
        raise CompletionReadinessError(str(exc)) from exc

    # A completed readiness envelope is an immutable handoff.  Reopening the
    # same output directory must consume that envelope instead of rerunning
    # producer-free gates (which could otherwise create a second observation
    # or a different duration/raw-output fingerprint).
    readiness_path = output_dir / "readiness.json"
    evidence_path = output_dir / "readiness.evidence.json"
    if readiness_path.exists() and evidence_path.exists():
        if readiness_path.is_symlink() or evidence_path.is_symlink():
            raise CompletionReadinessError("existing readiness outputs must not be symlinks")
        try:
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CompletionReadinessError("existing readiness envelope is unreadable") from exc
        if not isinstance(readiness, Mapping) or not isinstance(evidence, Mapping):
            raise CompletionReadinessError("existing readiness envelope must contain objects")
        try:
            from .completion_epoch import CompletionEpochReadiness  # noqa: PLC0415

            loaded_readiness = CompletionEpochReadiness.from_dict(readiness)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            raise CompletionReadinessError("existing readiness object is invalid") from exc
        expected_scope = (
            args.claim_scope,
            args.completion_work_id,
        )
        actual_scope = (
            loaded_readiness.claim_scope,
            loaded_readiness.completion_work_id,
        )
        if actual_scope != expected_scope:
            raise CompletionReadinessError(
                "existing readiness belongs to a different completion work or claim scope"
            )
        evidence_scope = (
            str(evidence.get("claim_scope", "")).strip().lower(),
            str(evidence.get("completion_work_id", "")).strip(),
        )
        if evidence_scope != expected_scope:
            raise CompletionReadinessError(
                "existing readiness evidence belongs to a different completion work or claim scope"
            )
        try:
            cached_manifest_path, _cached_manifest = _validate_cached_readiness_identity(
                args,
                root=root,
                output_dir=output_dir,
                preflight_inputs=preflight_inputs,
                evidence=evidence,
                loaded_readiness=loaded_readiness,
            )
        except CompletionReadinessError:
            raise
        return {
            "status": "pass",
            "readiness": dict(readiness),
            "evidence": dict(evidence),
            "readiness_path": str(readiness_path),
            "evidence_path": str(evidence_path),
            "completion_run_manifest_path": str(cached_manifest_path),
            "completion_run_manifest_fingerprint": str(
                evidence.get("completion_run_manifest_fingerprint", "")
            ),
            "objective_change": str(getattr(args, "objective_change", "") or ""),
            "claim_boundary": (
                "Readiness is a pre-parent gate. It does not claim that any full "
                "validation child or parent has executed."
            ),
        }

    # The package owns the effective planner.  The private script is only an
    # entry wrapper and is deliberately not a second implementation.
    from ._completion_readiness_impl import (  # noqa: PLC0415
        CompletionReadinessError as NativeCompletionReadinessError,
        produce as native_produce,
    )

    try:
        readiness, evidence = native_produce(args, preflight_inputs=preflight_inputs)
    except NativeCompletionReadinessError as exc:
        raise CompletionReadinessError(str(exc)) from exc
    readiness_path = output_dir / "readiness.json"
    evidence_path = output_dir / "readiness.evidence.json"
    _write_once(readiness_path, readiness)
    _write_once(evidence_path, evidence)
    return {
        "status": "pass",
        "readiness": readiness,
        "evidence": evidence,
        "readiness_path": str(readiness_path),
        "evidence_path": str(evidence_path),
        "completion_run_manifest_path": str(
            evidence.get("completion_run_manifest_path", "")
        ),
        "completion_run_manifest_fingerprint": str(
            evidence.get("completion_run_manifest_fingerprint", "")
        ),
        "objective_change": str(getattr(args, "objective_change", "") or ""),
        "claim_boundary": (
            "Readiness is a pre-parent gate. It does not claim that any full "
            "validation child or parent has executed."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = produce(args)
    except (CompletionReadinessError, OSError, ValueError, TypeError) as exc:
        result = {"status": "blocked", "error": f"{type(exc).__name__}: {exc}"}
        print(
            json.dumps(result, ensure_ascii=False, sort_keys=True)
            if args.json
            else f"status: blocked\nerror: {result['error']}"
        )
        return 1
    print(
        json.dumps(result, ensure_ascii=False, sort_keys=True)
        if args.json
        else f"status: pass\nreadiness: {result['readiness_path']}"
    )
    return 0


__all__ = ["CompletionReadinessError", "build_parser", "main", "produce"]
