"""Immutable readiness-to-full invocation manifest.

The completion-readiness command and the full validation command both derive
their plans from the same native planner, but callers historically had to
repeat a long list of invocation arguments.  This module adds one small,
content-addressed envelope for that invocation.  It is execution evidence
for one completion epoch, not a second authority or model source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .completion_epoch import (
    COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
    COMPLETION_DEFAULT_WORK_ID,
    COMPLETION_MAINTENANCE_UNIT_ID,
    normalize_completion_claim_scope,
    normalize_completion_maintenance_unit_id,
    normalize_completion_work_id,
)
from .evidence_lifecycle import fingerprint_payload


COMPLETION_RUN_MANIFEST_SCHEMA = "flowguard.completion_run_manifest.v1"


class CompletionRunManifestError(ValueError):
    """A completion-run manifest is missing, malformed, or inconsistent."""


def _path_value(value: Any) -> str:
    if not value:
        return ""
    return str(Path(str(value)).expanduser().resolve())


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _objective_name(args: Any) -> str:
    return str(
        getattr(args, "completion_objective_change", "")
        or getattr(args, "objective_change", "")
        or ""
    ).strip()


def _work_id(args: Any) -> str:
    return normalize_completion_work_id(
        getattr(args, "completion_work_id", COMPLETION_DEFAULT_WORK_ID)
    )


def _maintenance_unit_id(args: Any) -> str:
    value = getattr(args, "maintenance_unit_id", COMPLETION_MAINTENANCE_UNIT_ID)
    return normalize_completion_maintenance_unit_id(value)


def _claim_scope(args: Any) -> str:
    return normalize_completion_claim_scope(
        getattr(args, "claim_scope", COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION)
    )


def invocation_projection(*, args: Any, root: Path, receipt_root: Path) -> dict[str, Any]:
    """Return invocation fields that readiness and full must agree on.

    ``output_dir`` is intentionally absent.  It is an execution-record
    location and must never create a new semantic completion epoch.
    """

    model_receipt_dir = getattr(args, "model_receipt_dir", "") or (
        root / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    return {
        "root": _path_value(root),
        "completion_objective_change": _objective_name(args),
        "maintenance_unit_id": _maintenance_unit_id(args),
        "completion_work_id": _work_id(args),
        "claim_scope": _claim_scope(args),
        "receipt_dir": _path_value(receipt_root),
        "model_receipt_dir": _path_value(model_receipt_dir),
        "formal_root": _path_value(getattr(args, "formal_root", "")),
        "shadow_root": _path_value(getattr(args, "shadow_root", "")),
        "installed_root": _path_value(getattr(args, "installed_root", "")),
        "model_jobs": int(getattr(args, "model_jobs", 1) or 1),
        "model_timeout": getattr(args, "model_timeout", None),
        "gate_timeout": float(getattr(args, "gate_timeout", 900.0) or 900.0),
        "require_executed_evidence": bool(
            getattr(args, "require_executed_evidence", False)
        ),
        "skillguard": str(getattr(args, "skillguard", "all") or "all"),
        "completion_repair_link": _path_value(
            getattr(args, "completion_repair_link", "")
        ),
        "completion_authorization": _path_value(
            getattr(args, "completion_authorization", "")
        ),
    }


def build_manifest(
    *,
    args: Any,
    root: Path,
    receipt_root: Path,
    specs: Sequence[Any],
    owner_plan: Any,
    completion_epoch: Any,
    canonicalize_command: Any,
    readiness_fingerprint: str = "",
) -> dict[str, Any]:
    """Build one deterministic manifest from a frozen native plan."""

    child_commands = [
        {
            "child_id": str(spec.child_id),
            "command": [
                str(item)
                for item in canonicalize_command(
                    spec.command,
                    resource_options=getattr(spec, "resource_options", ()),
                )
            ],
        }
        for spec in specs
    ]
    invocation = invocation_projection(
        args=args,
        root=root,
        receipt_root=receipt_root,
    )
    epoch_work_id = normalize_completion_work_id(
        getattr(completion_epoch, "completion_work_id", _work_id(args))
    )
    epoch_unit_id = normalize_completion_maintenance_unit_id(
        getattr(completion_epoch, "maintenance_unit_id", _maintenance_unit_id(args))
    )
    epoch_claim_scope = normalize_completion_claim_scope(
        getattr(completion_epoch, "claim_scope", _claim_scope(args))
    )
    for field_name, invocation_value, epoch_value in (
        ("maintenance_unit_id", invocation["maintenance_unit_id"], epoch_unit_id),
        ("completion_work_id", invocation["completion_work_id"], epoch_work_id),
        ("claim_scope", invocation["claim_scope"], epoch_claim_scope),
    ):
        if invocation_value != epoch_value:
            raise CompletionRunManifestError(
                f"completion run manifest {field_name} does not match the frozen epoch"
            )
    plan = {
        "epoch_id": str(completion_epoch.epoch_id),
        "completion_cycle_id": str(completion_epoch.completion_cycle_id),
        "maintenance_unit_id": epoch_unit_id,
        "completion_work_id": epoch_work_id,
        "claim_scope": epoch_claim_scope,
        "completion_authorization_fingerprint": str(
            getattr(completion_epoch, "completion_authorization_fingerprint", "")
        ),
        "completion_objective_fingerprint": str(
            completion_epoch.completion_objective_fingerprint
        ),
        "source_observation_fingerprint": str(
            completion_epoch.source_observation_fingerprint
        ),
        "release_tree_fingerprint": str(
            completion_epoch.release_tree_fingerprint
        ),
        "toolchain_environment_fingerprint": str(
            completion_epoch.toolchain_environment_fingerprint
        ),
        "owner_dag_fingerprint": str(completion_epoch.owner_dag_fingerprint),
        "model_authority_fingerprint": str(
            completion_epoch.model_authority_fingerprint
        ),
        "test_inventory_fingerprint": str(
            completion_epoch.test_inventory_fingerprint
        ),
        "owner_plan_fingerprint": str(owner_plan.plan_fingerprint),
        "required_terminal_action_ids": [
            str(item) for item in completion_epoch.required_terminal_action_ids
        ],
        "remaining_governed_write_ids": [
            str(item) for item in completion_epoch.remaining_governed_write_ids
        ],
        "repair_link_fingerprint": str(
            completion_epoch.repair_link.fingerprint
            if completion_epoch.repair_link is not None
            else ""
        ),
        "readiness_fingerprint": str(readiness_fingerprint or ""),
        "child_semantic_commands": child_commands,
    }
    payload = {
        "schema_version": COMPLETION_RUN_MANIFEST_SCHEMA,
        "claim_boundary": (
            "This manifest freezes one completion invocation between readiness "
            "and full validation. It is not model authority, source authority, "
            "or terminal validation evidence."
        ),
        "invocation": invocation,
        "plan": plan,
    }
    payload["manifest_fingerprint"] = fingerprint_payload(payload)
    return payload


def validate_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CompletionRunManifestError("completion run manifest must be an object")
    if payload.get("schema_version") != COMPLETION_RUN_MANIFEST_SCHEMA:
        raise CompletionRunManifestError(
            "unsupported completion run manifest schema"
        )
    for key in ("invocation", "plan", "manifest_fingerprint"):
        if key not in payload:
            raise CompletionRunManifestError(
                f"completion run manifest field is missing: {key}"
            )
    invocation = payload["invocation"]
    plan = payload["plan"]
    if not isinstance(invocation, Mapping) or not isinstance(plan, Mapping):
        raise CompletionRunManifestError(
            "completion run manifest invocation and plan must be objects"
        )
    declared = payload.get("manifest_fingerprint")
    expected = fingerprint_payload(
        {key: value for key, value in payload.items() if key != "manifest_fingerprint"}
    )
    if declared != expected:
        raise CompletionRunManifestError(
            "completion run manifest fingerprint mismatch"
        )
    return dict(payload)


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path).expanduser()
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise CompletionRunManifestError(
            f"completion run manifest is missing or a symlink: {manifest_path}"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompletionRunManifestError(
            f"completion run manifest cannot be read: {manifest_path}: {exc}"
        ) from exc
    return validate_manifest(payload)


def write_manifest(path: str | Path, payload: Mapping[str, Any]) -> Path:
    raw_path = Path(path).expanduser()
    if raw_path.is_symlink():
        raise CompletionRunManifestError(
            f"completion run manifest output must not be a symlink: {raw_path}"
        )
    manifest_path = raw_path.resolve()
    checked = validate_manifest(payload)
    encoded = json.dumps(
        checked,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if manifest_path.exists():
        try:
            existing = manifest_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CompletionRunManifestError(
                f"completion run manifest output cannot be read: {manifest_path}"
            ) from exc
        if existing != encoded:
            raise CompletionRunManifestError(
                f"completion run manifest already exists with different content: {manifest_path}"
            )
        return manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(encoded, encoding="utf-8")
    return manifest_path


def _diff_values(
    expected: Any,
    actual: Any,
    *,
    prefix: str,
    differences: list[dict[str, Any]],
) -> None:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        keys = sorted(set(expected) | set(actual), key=str)
        for key in keys:
            key_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected or key not in actual:
                differences.append(
                    {
                        "field": key_prefix,
                        "readiness": expected.get(key),
                        "full": actual.get(key),
                    }
                )
                continue
            _diff_values(
                expected[key],
                actual[key],
                prefix=key_prefix,
                differences=differences,
            )
        return
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        if list(expected) != list(actual):
            differences.append(
                {"field": prefix, "readiness": expected, "full": actual}
            )
        return
    if expected != actual:
        differences.append(
            {"field": prefix, "readiness": expected, "full": actual}
        )


def compare_manifest(
    readiness_manifest: Mapping[str, Any],
    full_manifest: Mapping[str, Any],
    *,
    ignore_fields: Sequence[str] = (),
) -> tuple[dict[str, Any], ...]:
    """Compare frozen fields and return deterministic field-level differences."""

    differences: list[dict[str, Any]] = []
    ignored = set(ignore_fields)
    expected = _canonical(readiness_manifest)
    actual = _canonical(full_manifest)
    for field in ignored:
        cursor_expected: Any = expected
        cursor_actual: Any = actual
        parts = field.split(".")
        for part in parts[:-1]:
            if not isinstance(cursor_expected, Mapping) or not isinstance(cursor_actual, Mapping):
                break
            cursor_expected = cursor_expected.get(part)
            cursor_actual = cursor_actual.get(part)
        else:
            if isinstance(cursor_expected, dict) and isinstance(cursor_actual, dict):
                cursor_expected.pop(parts[-1], None)
                cursor_actual.pop(parts[-1], None)
    _diff_values(expected, actual, prefix="", differences=differences)
    return tuple(differences)


__all__ = [
    "COMPLETION_RUN_MANIFEST_SCHEMA",
    "CompletionRunManifestError",
    "build_manifest",
    "compare_manifest",
    "invocation_projection",
    "load_manifest",
    "validate_manifest",
    "write_manifest",
]
