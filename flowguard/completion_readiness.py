"""Canonical public completion-readiness command.

The public command owns the stable wire/output surface. Its gate planner is
the existing native completion planner used by the full suite; this module
adapts the command-line envelope and writes the bounded readiness and
evidence objects idempotently. It never launches the heavy validation DAG.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .completion_epoch import (
    COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
    normalize_completion_claim_scope,
    normalize_completion_work_id,
)


class CompletionReadinessError(RuntimeError):
    """A readiness request cannot be independently proved current."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m flowguard completion-readiness",
        description=(
            "Build one canonical, read-only completion-readiness envelope. "
            "No heavy producer or completion attempt is started."
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
        return {
            "status": "pass",
            "readiness": dict(readiness),
            "evidence": dict(evidence),
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

    # The package owns the effective planner.  The legacy script is only a
    # compatibility wrapper and is deliberately not part of this authority
    # path, so an old helper cannot silently become a second implementation.
    from ._completion_readiness_impl import (  # noqa: PLC0415
        CompletionReadinessError as NativeCompletionReadinessError,
        produce as native_produce,
    )

    try:
        readiness, evidence = native_produce(args)
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
