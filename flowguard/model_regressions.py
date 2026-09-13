"""Manifest-owned, observable execution for repository FlowGuard models.

The manifest is the execution authority.  Filesystem discovery is used only
to prove that the manifest accounts for every local model in both directions.
Each child runs in its own process and receives an isolated artifact directory.
"""

from __future__ import annotations

import fnmatch
from contextlib import ExitStack
import hashlib
import json
import math
import os
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping, Sequence

from .evidence_lifecycle import (
    evidence_execution_lease,
    ensure_new_run_directory,
    publish_run,
    store_text_object,
    write_json_atomic,
)
from .evidence_receipts import (
    RECEIPT_STATUS_PASS,
    VERIFICATION_STATUS_STALE,
    EvidenceReceipt,
    ReceiptVerificationResult,
    fingerprint_value,
    load_evidence_receipt,
    receipt_path as evidence_receipt_path,
    verify_evidence_receipt,
)
from .model_authority import (
    ModelInstanceRef,
    build_model_instance_ref,
)
from .model_purpose import ModelPurposeClosure, ModelPurposeError, validate_unique_model_instances
from .native_case_protocol import (
    NATIVE_CASE_RESULT_SCHEMA,
    NativeCaseProtocolError,
    NativeBindingVerification,
    NativeCaseBinding,
    NativeCaseVerification,
    NativeModelCaseContract,
    NativeModelCaseResult,
    fingerprint_payload,
    verify_native_case_bindings,
    verify_native_model_cases,
)
from .source_identity import functional_source_fingerprint, source_file_fingerprint
from .execution_profiles import ValidationExecutionPolicy
from .process_supervision import (
    SupervisedCommandResult,
    run_supervised,
    write_terminal_artifact,
)
from .validation_owner_execution import (
    publish_supervised_validation_owner_result,
)

from .validation_results import (
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_CANCELLED,
    VALIDATION_STATUS_FAIL,
    VALIDATION_STATUS_INTERNAL_ERROR,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_TIMEOUT,
    ValidationChildResult,
    ValidationResult,
    aggregate_status,
)
from .validation_ownership import (
    OWNER_BLOCKED,
    OWNER_EXECUTE,
    OWNER_RECEIPT_KIND,
    OWNER_REUSE_CURRENT,
    ValidationOwnerContract,
    ValidationOwnerObservation,
    ValidationObservationFreshness,
    _assert_owner_receipt_integrity,
    assert_validation_owner_observation_fresh,
    assert_validation_owner_observation_receipts_fresh,
    build_child_bound_owner_receipt_context,
    build_owner_current,
    build_owner_current_from_observation,
    build_owner_receipt_context,
    child_from_owner_receipt,
    filter_resolved_input_manifest,
    observe_validation_owners,
    record_validation_owner_nonpass,
    refresh_validation_owner_observation_receipts,
    save_child_bound_owner_receipt,
    save_child_bound_owner_receipt_from_observation,
)


MANIFEST_SCHEMA = "flowguard.model_regression_manifest.v4"
MODEL_EXECUTION_EVIDENCE_SCHEMA = "flowguard.model_execution_evidence.v1"
# Native model runners may print ordinary human-readable output.  The one
# machine-readable channel for behaviour-case evidence is an explicit marker;
# IDs are never reconstructed from model purpose declarations or from a
# parent summary.
EXECUTED_CASE_IDS_MARKER = "FLOWGUARD_EXECUTED_CASE_IDS="
# The marker is only a process-output locator.  A strict owner needs this
# producer-written, content-addressed envelope as the actual case evidence.
NATIVE_CASE_RESULT_ARTIFACT_NAME = "native-case-results.json"
MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA = (
    "flowguard.model_regression_parent_receipt.v2"
)
MODEL_REGRESSION_PARENT_ARTIFACT_TYPE = (
    "flowguard_model_regression_parent_receipt"
)
MODEL_REGRESSION_PARENT_CURRENT_SCHEMA = (
    "flowguard.model_regression_parent_current.v1"
)
# These owners have a semantic source inventory in addition to ordinary
# manifest/input-file identity.  The inventory is intentionally checked
# before any model producer is leased: a stale ledger is a source repair
# boundary, not a model-run failure to be discovered after spending the
# remaining owner budget.
_SEMANTIC_SOURCE_INVENTORY_OWNER_IDS = frozenset(
    {"behavior_commitment_ledger"}
)
_MODEL_REGRESSION_PARENT_FIELDS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "claim_scope",
        "tier",
        "status",
        "manifest_sha256",
        "selected_model_ids",
        "skipped_model_ids",
        "children",
        "execution_receipt_id",
        "execution_receipt_fingerprint",
        "claim_boundary",
        "parent_receipt_fingerprint",
    }
)
_MODEL_REGRESSION_PARENT_CURRENT_FIELDS = frozenset(
    {
        "artifact_type",
        "parent_receipt_fingerprint",
        "schema_version",
    }
)
_MODEL_REGRESSION_PARENT_CHILD_FIELDS = frozenset(
    {"model_id", "receipt_id", "receipt_fingerprint"}
)
TIER_RANK = {"fast": 0, "focused": 1, "full": 2}


class ModelRegressionManifestError(ValueError):
    """Raised when the checked-in model inventory is incomplete or invalid."""


class ModelRegressionEvidenceError(ValueError):
    """Raised when no unique exact-current full model evidence composition exists."""


class ModelRegressionParentNotCurrentError(ModelRegressionEvidenceError):
    """Raised when only structurally valid but stale parent wrappers remain."""


def audit_selected_model_source_inventories(
    root: str | Path,
    model_ids: Sequence[str],
) -> tuple[str, ...]:
    """Read-only preflight for model-owned semantic source inventories.

    The ordinary validation-owner observation compares declared input-file
    identities.  A semantic owner may additionally persist a derived source
    inventory inside its own authority artifact; changing one of the declared
    source surfaces does not necessarily change that artifact's bytes.  Such
    drift must block *before* any model owner is leased or executed.  This
    helper deliberately audits only the selected semantic owners and never
    refreshes or writes their inventories.
    """

    selected = {
        str(model_id).strip().removeprefix("model:")
        for model_id in model_ids
        if str(model_id).strip()
    }
    owner_ids = selected & _SEMANTIC_SOURCE_INVENTORY_OWNER_IDS
    if not owner_ids:
        return ()

    root_path = Path(root).resolve()
    ledger_path = (
        root_path
        / ".flowguard"
        / "behavior"
        / "inventory"
        / "ledger.json"
    )
    if ledger_path.is_symlink() or not ledger_path.is_file():
        return (
            "behavior_commitment_ledger: semantic source inventory authority is "
            f"missing or symlinked: {ledger_path}",
        )

    try:
        from .behavior_commitment import (
            audit_behavior_commitment_source_inventory,
            load_behavior_commitment_ledger,
        )

        ledger = load_behavior_commitment_ledger(ledger_path)
        audit = audit_behavior_commitment_source_inventory(ledger, root_path)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return (
            "behavior_commitment_ledger: semantic source inventory audit could "
            f"not complete ({type(exc).__name__}: {exc})",
        )

    if audit.ok:
        return ()
    codes = tuple(
        sorted(
            {
                str(finding.code).strip()
                for finding in audit.findings
                if str(finding.code).strip()
            }
        )
    )
    stored_revision = str(ledger.source_inventory_revision or "").strip()
    live_revision = str(audit.live_inventory_revision or "").strip()
    code_text = ",".join(codes) or "unknown"
    return (
        "behavior_commitment_ledger: semantic source inventory is not current "
        f"(findings={code_text}; stored={stored_revision or '<empty>'}; "
        f"live={live_revision or '<unavailable>'}); refresh the authored ledger "
        "inside a new CompletionEpoch before rerunning model owners",
    )


def parse_executed_case_ids(
    output: str,
    *,
    require_marker: bool = False,
) -> tuple[str, ...]:
    """Read the explicit native-runner case-id projection.

    A runner can emit arbitrary diagnostic text, but it must emit exactly one
    ``FLOWGUARD_EXECUTED_CASE_IDS=`` line when it claims dynamic case
    coverage.  The payload is a JSON array of literal case IDs.  This helper
    deliberately does not infer IDs from case declarations, output wording,
    counts, or a parent receipt.  A missing marker is therefore an honest
    empty projection unless the caller explicitly requires the marker.
    """

    if not isinstance(output, str):
        raise ModelRegressionEvidenceError(
            "native runner output must be text when parsing executed case ids"
        )
    payloads: list[Any] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.startswith(EXECUTED_CASE_IDS_MARKER):
            continue
        encoded = line[len(EXECUTED_CASE_IDS_MARKER) :].strip()
        if not encoded:
            raise ModelRegressionEvidenceError(
                "native runner executed-case marker has an empty payload"
            )
        try:
            payloads.append(json.loads(encoded))
        except json.JSONDecodeError as exc:
            raise ModelRegressionEvidenceError(
                "native runner executed-case marker is not valid JSON"
            ) from exc
    if not payloads:
        if require_marker:
            raise ModelRegressionEvidenceError(
                "native runner did not emit the explicit executed-case marker"
            )
        return ()
    if len(payloads) != 1:
        raise ModelRegressionEvidenceError(
            "native runner emitted duplicate executed-case markers"
        )
    raw_ids = payloads[0]
    if isinstance(raw_ids, Mapping):
        # Accept a JSON object only when its shape is exactly the documented
        # projection.  This makes it convenient for runners that print one
        # structured result object without accepting arbitrary nested claims.
        if set(raw_ids) != {"executed_case_ids"}:
            raise ModelRegressionEvidenceError(
                "native runner executed-case object has an unknown shape"
            )
        raw_ids = raw_ids["executed_case_ids"]
    if not isinstance(raw_ids, (list, tuple)):
        raise ModelRegressionEvidenceError(
            "native runner executed case ids must be a JSON array"
        )
    ids: list[str] = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ModelRegressionEvidenceError(
                "native runner executed case ids must be non-empty strings"
            )
        case_id = raw_id.strip()
        if case_id in ids:
            raise ModelRegressionEvidenceError(
                "native runner executed case ids contain a duplicate: " + case_id
            )
        ids.append(case_id)
    return tuple(ids)


def _coerce_executed_case_ids(value: Any, *, context: str) -> tuple[str, ...]:
    """Validate a stored native case projection without adding any IDs."""

    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ModelRegressionEvidenceError(
            f"{context} executed_case_ids must be an array"
        )
    result: list[str] = []
    for raw_id in value:
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ModelRegressionEvidenceError(
                f"{context} executed_case_ids must contain non-empty strings"
            )
        case_id = raw_id.strip()
        if case_id in result:
            raise ModelRegressionEvidenceError(
                f"{context} executed_case_ids contain a duplicate: {case_id}"
            )
        result.append(case_id)
    return tuple(result)


def _coerce_native_case_results(
    value: Any,
    *,
    context: str,
) -> tuple[NativeModelCaseResult, ...]:
    """Decode the persisted native result rows without manufacturing evidence.

    ``NativeModelCaseResult.to_dict`` includes the row schema marker while the
    protocol loader historically accepted the row fields without that marker.
    The model-regression boundary accepts the one current marker explicitly and
    otherwise delegates all field validation to ``NativeModelCaseResult``.
    This keeps the current envelope usable while rejecting unknown/legacy
    shapes instead of silently dropping fields.
    """

    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_results must be an array"
        )
    rows: list[NativeModelCaseResult] = []
    for index, raw in enumerate(value):
        if isinstance(raw, NativeModelCaseResult):
            rows.append(raw)
            continue
        if not isinstance(raw, Mapping):
            raise ModelRegressionEvidenceError(
                f"{context} native_case_results[{index}] must be an object"
            )
        payload = dict(raw)
        row_schema = payload.pop("schema_version", None)
        if row_schema not in (None, NATIVE_CASE_RESULT_SCHEMA):
            raise ModelRegressionEvidenceError(
                f"{context} native_case_results[{index}] has an unsupported schema"
            )
        try:
            rows.append(NativeModelCaseResult(**payload))
        except (NativeCaseProtocolError, TypeError, ValueError) as exc:
            raise ModelRegressionEvidenceError(
                f"{context} native_case_results[{index}] is invalid: {exc}"
            ) from exc
    identities = [(row.owner_id, row.source_case_id) for row in rows]
    if len(identities) != len(set(identities)):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_results contain duplicate owner/case identities"
        )
    return tuple(rows)


def _native_result_rows_equal(
    left: Sequence[NativeModelCaseResult],
    right: Sequence[NativeModelCaseResult],
) -> bool:
    """Compare canonical row payloads, independent of list ordering."""

    def key(row: NativeModelCaseResult) -> tuple[str, str, str]:
        return (row.owner_id, row.source_case_id, fingerprint_value(row.to_dict()))

    return tuple(sorted(key(row) for row in left)) == tuple(
        sorted(key(row) for row in right)
    )


def _resolve_native_raw_artifact(
    artifact_path: Path,
    raw_artifact_path: str,
) -> Path:
    """Resolve one raw result relative to its immutable envelope directory."""

    raw = Path(raw_artifact_path).expanduser()
    if not raw.is_absolute():
        raw = artifact_path.parent / raw
    return raw.resolve()


def _verify_native_case_result_rows(
    *,
    owner_id: str,
    marker_case_ids: Sequence[str],
    rows: Sequence[NativeModelCaseResult],
    artifact_path: Path | None,
) -> NativeCaseVerification:
    """Verify the producer envelope at the model-owner boundary.

    The complete contract comparison is performed by
    :func:`verify_native_model_cases` when a caller supplies the frozen native
    contracts.  This lower-level check still binds the envelope to the
    process marker, owner, raw result files, dimensions, and oracle rows.  A
    marker alone therefore can never make a strict owner complete.
    """

    expected_owner = str(owner_id)
    marker_ids = tuple(str(item) for item in marker_case_ids)
    marker_set = set(marker_ids)
    findings: list[str] = []
    missing: list[str] = []
    foreign: list[str] = []
    duplicate: list[str] = []
    seen: set[tuple[str, str]] = set()
    labels: list[str] = []

    if artifact_path is None:
        findings.append("native_result_artifact_missing")
    else:
        if artifact_path.is_symlink() or not artifact_path.is_file():
            findings.append("native_result_artifact_missing")

    for row in rows:
        identity = (row.owner_id, row.source_case_id)
        label = f"{row.owner_id}:{row.source_case_id}"
        labels.append(label)
        if identity in seen:
            duplicate.append(label)
            continue
        seen.add(identity)
        if row.owner_id != expected_owner:
            foreign.append(label)
            findings.append(f"native_result_owner_mismatch:{label}")
        if row.source_case_id not in marker_set:
            foreign.append(label)
            findings.append(f"native_result_not_marked:{label}")
        if row.outcome == "not_run":
            findings.append(f"native_result_not_run:{label}")

        observed_dimensions = set(row.executed_dimensions)
        oracle_dimensions = {
            str(item.get("dimension", "")).strip()
            for item in row.oracle_results
            if isinstance(item, Mapping)
        }
        if observed_dimensions != oracle_dimensions:
            findings.append(f"native_result_oracle_dimension_mismatch:{label}")
        for oracle in row.oracle_results:
            if not isinstance(oracle.get("oracle_member_id"), str) or not str(
                oracle.get("oracle_member_id")
            ).strip():
                findings.append(f"native_result_oracle_identity_missing:{label}")
            if "ok" in oracle and not isinstance(oracle.get("ok"), bool):
                findings.append(f"native_result_oracle_status_invalid:{label}")

        if artifact_path is not None:
            try:
                raw_path = _resolve_native_raw_artifact(
                    artifact_path,
                    row.raw_artifact_path,
                )
                artifact_root = artifact_path.resolve().parent
                if (
                    artifact_path.is_symlink()
                    or artifact_root not in raw_path.parents
                    or raw_path.is_symlink()
                    or not raw_path.is_file()
                ):
                    findings.append(f"native_result_raw_artifact_missing:{label}")
                else:
                    digest = _file_sha256(raw_path)
                    if digest != row.result_artifact_fingerprint:
                        findings.append(
                            f"native_result_raw_artifact_fingerprint_mismatch:{label}"
                        )
            except (OSError, ValueError) as exc:
                findings.append(
                    f"native_result_raw_artifact_invalid:{label}:{type(exc).__name__}"
                )

    result_keys = {(row.owner_id, row.source_case_id) for row in rows}
    for case_id in marker_ids:
        key = (expected_owner, case_id)
        if key not in result_keys:
            missing.append(f"{expected_owner}:{case_id}")
            findings.append(f"native_result_missing:{expected_owner}:{case_id}")
    if not rows:
        findings.append("native_result_rows_empty")
    if not marker_ids:
        findings.append("native_result_marker_empty")
    for item in duplicate:
        findings.append(f"native_result_duplicate:{item}")

    return NativeCaseVerification(
        ok=not findings and bool(rows) and bool(marker_ids),
        findings=tuple(dict.fromkeys(sorted(findings))),
        missing_case_ids=tuple(sorted(set(missing))),
        foreign_case_ids=tuple(sorted(set(foreign))),
        duplicate_case_ids=tuple(sorted(set(duplicate))),
        leaf_case_ids=tuple(sorted(set(labels))),
    )


def _load_native_case_result_artifact(
    path: str | Path,
    *,
    owner_id: str,
    marker_case_ids: Sequence[str],
) -> tuple[
    tuple[NativeModelCaseResult, ...],
    Path,
    str,
    NativeCaseVerification,
]:
    """Load and verify one current native result envelope."""

    artifact_path = Path(path).expanduser().resolve()
    if Path(path).expanduser().is_symlink() or not artifact_path.is_file():
        raise ModelRegressionEvidenceError(
            "native result artifact is missing or a symlink"
        )
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelRegressionEvidenceError(
            f"native result artifact is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, Mapping) or set(payload) != {
        "schema_version",
        "results",
    } or payload.get("schema_version") != NATIVE_CASE_RESULT_SCHEMA:
        raise ModelRegressionEvidenceError(
            "native result artifact envelope is not current"
        )
    rows = _coerce_native_case_results(
        payload.get("results"),
        context=str(artifact_path),
    )
    verification = _verify_native_case_result_rows(
        owner_id=owner_id,
        marker_case_ids=marker_case_ids,
        rows=rows,
        artifact_path=artifact_path,
    )
    return (
        rows,
        artifact_path,
        _file_sha256(artifact_path),
        verification,
    )


def _native_case_verification_from_payload(
    value: Any,
    *,
    context: str,
) -> NativeCaseVerification | None:
    """Decode an optional serialized verification projection for reuse."""

    if value in (None, ""):
        return None
    if not isinstance(value, Mapping):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_verification must be an object"
        )
    allowed_fields = {
        "schema_version",
        "ok",
        "status",
        "findings",
        "missing_case_ids",
        "foreign_case_ids",
        "duplicate_case_ids",
        "unasserted_dimensions",
        "aggregate_case_ids",
        "leaf_case_ids",
        "model_policy_pass",
        "implementation_boundary_pass",
    }
    unknown_fields = sorted(set(value) - allowed_fields)
    if unknown_fields:
        raise ModelRegressionEvidenceError(
            f"{context} native_case_verification has unknown fields: "
            + ", ".join(unknown_fields)
        )
    if value.get("schema_version") not in (None, NATIVE_CASE_RESULT_SCHEMA):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_verification has an unsupported schema"
        )
    bool_fields = {
        "ok",
        "model_policy_pass",
        "implementation_boundary_pass",
    }
    for name in bool_fields:
        if name in value and not isinstance(value[name], bool):
            raise ModelRegressionEvidenceError(
                f"{context} native_case_verification.{name} must be boolean"
            )
    def ids(name: str) -> tuple[str, ...]:
        return _coerce_executed_case_ids(
            value.get(name, ()),
            context=f"{context} native_case_verification.{name}",
        )
    return NativeCaseVerification(
        ok=bool(value.get("ok", False)),
        findings=ids("findings"),
        missing_case_ids=ids("missing_case_ids"),
        foreign_case_ids=ids("foreign_case_ids"),
        duplicate_case_ids=ids("duplicate_case_ids"),
        unasserted_dimensions=ids("unasserted_dimensions"),
        aggregate_case_ids=ids("aggregate_case_ids"),
        leaf_case_ids=ids("leaf_case_ids"),
        model_policy_pass=bool(value.get("model_policy_pass", False)),
        implementation_boundary_pass=bool(
            value.get("implementation_boundary_pass", False)
        ),
    )


def _native_case_bindings_from_payload(
    value: Any,
    *,
    context: str,
) -> tuple[NativeCaseBinding, ...]:
    """Decode the exact native-to-blueprint binding projection.

    Binding rows are part of the producer evidence envelope.  They are not
    reconstructed from a case name, source id, or the current blueprint: a
    missing/legacy/altered row must remain visible as an invalid reuse rather
    than silently acquiring a new mapping.
    """

    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_bindings must be an array"
        )
    allowed_fields = {
        "schema_version",
        "owner_id",
        "blueprint_case_id",
        "blueprint_source_case_id",
        "native_case_ids",
        "case_kind",
        "evidence_scope",
        "covered_dimensions",
        "expected_status",
        "expected_observed_status",
        "protected_failure_ids",
        "expected_finding_codes",
        "required_child_case_ids",
        "required_trace_labels",
        "mapping_fingerprint",
        "binding_fingerprint",
    }
    rows: list[NativeCaseBinding] = []
    for index, raw in enumerate(value):
        if isinstance(raw, NativeCaseBinding):
            row = raw
        else:
            if not isinstance(raw, Mapping):
                raise ModelRegressionEvidenceError(
                    f"{context} native_case_bindings[{index}] must be an object"
                )
            unknown = sorted(set(raw) - allowed_fields)
            if unknown:
                raise ModelRegressionEvidenceError(
                    f"{context} native_case_bindings[{index}] has unknown fields: "
                    + ", ".join(unknown)
                )
            payload = dict(raw)
            schema = payload.pop("schema_version", None)
            if schema not in (None, "flowguard.native_model_case_binding.v1"):
                raise ModelRegressionEvidenceError(
                    f"{context} native_case_bindings[{index}] has an unsupported schema"
                )
            declared_fingerprint = payload.pop("binding_fingerprint", None)
            try:
                row = NativeCaseBinding(**payload)
            except (NativeCaseProtocolError, TypeError, ValueError) as exc:
                raise ModelRegressionEvidenceError(
                    f"{context} native_case_bindings[{index}] is invalid: {exc}"
                ) from exc
            if declared_fingerprint not in (None, ""):
                if not isinstance(declared_fingerprint, str) or (
                    declared_fingerprint != row.fingerprint
                ):
                    raise ModelRegressionEvidenceError(
                        f"{context} native_case_bindings[{index}] fingerprint is stale"
                    )
        rows.append(row)
    identity = [(row.owner_id, row.blueprint_case_id) for row in rows]
    if len(identity) != len(set(identity)):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_bindings contain duplicate owner/blueprint identities"
        )
    return tuple(rows)


def _native_binding_verification_from_payload(
    value: Any,
    *,
    context: str,
) -> NativeBindingVerification | None:
    """Decode a persisted binding verification without repairing it."""

    if value in (None, ""):
        return None
    if not isinstance(value, Mapping):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_binding_verification must be an object"
        )
    allowed_fields = {
        "schema_version",
        "ok",
        "projected_case_ids",
        "missing_bindings",
        "foreign_native_case_ids",
        "duplicate_native_case_ids",
        "findings",
    }
    unknown = sorted(set(value) - allowed_fields)
    if unknown:
        raise ModelRegressionEvidenceError(
            f"{context} native_case_binding_verification has unknown fields: "
            + ", ".join(unknown)
        )
    schema = value.get("schema_version")
    if schema not in (None, "flowguard.native_model_case_binding.v1"):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_binding_verification has an unsupported schema"
        )
    if not isinstance(value.get("ok", False), bool):
        raise ModelRegressionEvidenceError(
            f"{context} native_case_binding_verification.ok must be boolean"
        )

    def ids(name: str) -> tuple[str, ...]:
        return _coerce_executed_case_ids(
            value.get(name, ()),
            context=f"{context} native_case_binding_verification.{name}",
        )

    return NativeBindingVerification(
        ok=bool(value.get("ok", False)),
        projected_case_ids=ids("projected_case_ids"),
        missing_bindings=ids("missing_bindings"),
        foreign_native_case_ids=ids("foreign_native_case_ids"),
        duplicate_native_case_ids=ids("duplicate_native_case_ids"),
        findings=ids("findings"),
    )


@dataclass(frozen=True)
class ModelRegressionEntry:
    model_id: str
    model_path: str
    runner: tuple[str, ...]
    tier: str
    timeout_seconds: float
    shard_safe: bool
    mutation_policy: str
    input_globs: tuple[str, ...]
    intent_source_inputs: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    exclusion_reason: str = ""
    distribution_policy: str = "required_public"
    absence_reason: str = ""
    model_kind: str = "executable_workflow"
    purpose_closure: ModelPurposeClosure | None = None
    shard_safety_proof: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ModelRegressionEntry":
        allowed = {
            "model_id",
            "model_path",
            "runner",
            "tier",
            "timeout_seconds",
            "shard_safe",
            "mutation_policy",
            "input_globs",
            "intent_source_inputs",
            "expected_artifacts",
            "exclusion_reason",
            "distribution_policy",
            "absence_reason",
            "model_kind",
            "purpose_closure",
            "shard_safety_proof",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ModelRegressionManifestError(
                "unknown model entry fields: " + ", ".join(unknown)
            )
        runner = payload.get("runner", ())
        if isinstance(runner, str):
            runner = (runner,)
        raw_purpose = payload.get("purpose_closure")
        purpose = ModelPurposeClosure.from_dict(raw_purpose) if isinstance(raw_purpose, Mapping) else None
        return cls(
            model_id=str(payload.get("model_id", "")),
            model_path=str(payload.get("model_path", "")),
            runner=tuple(str(item) for item in runner),
            tier=str(payload.get("tier", "")),
            timeout_seconds=float(payload.get("timeout_seconds", 0)),
            shard_safe=bool(payload.get("shard_safe", False)),
            mutation_policy=str(payload.get("mutation_policy", "")),
            input_globs=tuple(str(item) for item in payload.get("input_globs", ())),
            intent_source_inputs=tuple(
                str(item) for item in payload.get("intent_source_inputs", ())
            ),
            expected_artifacts=tuple(str(item) for item in payload.get("expected_artifacts", ())),
            exclusion_reason=str(payload.get("exclusion_reason", "")),
            distribution_policy=str(payload.get("distribution_policy", "required_public")),
            absence_reason=str(payload.get("absence_reason", "")),
            model_kind=str(
                payload.get("model_kind", "executable_workflow")
            ),
            purpose_closure=purpose,
            shard_safety_proof=dict(payload.get("shard_safety_proof", {})),
        )

    @property
    def excluded(self) -> bool:
        return bool(self.exclusion_reason)

    @property
    def effective_input_patterns(self) -> tuple[str, ...]:
        """Return authored selectors plus exact local intent-source inputs."""

        return tuple(dict.fromkeys((*self.input_globs, *self.intent_source_inputs)))

    def command(self, *, root: Path) -> tuple[str, ...]:
        values = {"python": sys.executable, "root": str(root)}
        return tuple(item.format(**values) for item in self.runner)


@dataclass(frozen=True)
class SharedInputGroup:
    component_id: str
    globs: tuple[str, ...]
    consumers: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SharedInputGroup":
        allowed = {"component_id", "globs", "consumers"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ModelRegressionManifestError(
                "unknown shared input group fields: " + ", ".join(unknown)
            )
        return cls(
            component_id=str(payload.get("component_id", "")),
            globs=tuple(str(item) for item in payload.get("globs", ())),
            consumers=tuple(str(item) for item in payload.get("consumers", ())),
        )


@dataclass(frozen=True)
class ModelRegressionManifest:
    path: Path
    entries: tuple[ModelRegressionEntry, ...]
    governed_input_globs: tuple[str, ...]
    snapshot_only_input_globs: tuple[str, ...]
    shared_input_groups: tuple[SharedInputGroup, ...]

    @classmethod
    def load(cls, root: str | Path = ".", *, path: str | Path | None = None) -> "ModelRegressionManifest":
        root_path = Path(root).resolve()
        manifest_path = Path(path).resolve() if path else root_path / ".flowguard" / "models" / "regression-manifest.json"
        if not manifest_path.is_file():
            raise ModelRegressionManifestError(f"missing model regression manifest: {manifest_path}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegressionManifestError(f"cannot read model regression manifest: {exc}") from exc
        if payload.get("schema_version") != MANIFEST_SCHEMA:
            raise ModelRegressionManifestError(f"unsupported manifest schema: {payload.get('schema_version')!r}")
        allowed = {
            "schema_version",
            "models",
            "governed_input_globs",
            "snapshot_only_input_globs",
            "shared_input_groups",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ModelRegressionManifestError(
                "unknown manifest fields: " + ", ".join(unknown)
            )
        entries = tuple(ModelRegressionEntry.from_dict(item) for item in payload.get("models", ()))
        return cls(
            path=manifest_path,
            entries=entries,
            governed_input_globs=tuple(
                str(item) for item in payload.get("governed_input_globs", ())
            ),
            snapshot_only_input_globs=tuple(
                str(item)
                for item in payload.get("snapshot_only_input_globs", ())
            ),
            shared_input_groups=tuple(
                SharedInputGroup.from_dict(item)
                for item in payload.get("shared_input_groups", ())
            ),
        )

    def shared_patterns_for(self, model_id: str) -> tuple[str, ...]:
        return tuple(
            pattern
            for group in self.shared_input_groups
            if model_id in group.consumers
            for pattern in group.globs
        )

    def owner_projection_fingerprint(
        self,
        entry: ModelRegressionEntry,
    ) -> str:
        """Project only the manifest semantics consumed by one model owner."""

        purpose = (
            entry.purpose_closure.to_dict()
            if entry.purpose_closure is not None
            else None
        )
        entry_payload = {
            "model_id": entry.model_id,
            "model_path": entry.model_path,
            "runner": list(entry.runner),
            "tier": entry.tier,
            "shard_safe": entry.shard_safe,
            "mutation_policy": entry.mutation_policy,
            "input_globs": list(entry.input_globs),
            "intent_source_inputs": list(entry.intent_source_inputs),
            "expected_artifacts": list(entry.expected_artifacts),
            "exclusion_reason": entry.exclusion_reason,
            "distribution_policy": entry.distribution_policy,
            "absence_reason": entry.absence_reason,
            "model_kind": entry.model_kind,
            "purpose_closure": purpose,
            "shard_safety_proof": dict(entry.shard_safety_proof),
        }
        shared_groups = tuple(
            {
                "component_id": group.component_id,
                "globs": list(group.globs),
            }
            for group in sorted(
                self.shared_input_groups,
                key=lambda item: item.component_id,
            )
            if entry.model_id in group.consumers
        )
        return fingerprint_value(
            {
                "schema_version": MANIFEST_SCHEMA,
                "entry": entry_payload,
                "governed_input_globs": list(self.governed_input_globs),
                "snapshot_only_input_globs": list(
                    self.snapshot_only_input_globs
                ),
                "shared_input_groups": shared_groups,
            }
        )


@dataclass(frozen=True)
class ManifestAudit:
    ok: bool
    discovered_model_ids: tuple[str, ...]
    registered_model_ids: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "discovered_model_ids": list(self.discovered_model_ids),
            "registered_model_ids": list(self.registered_model_ids),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ModelImpactMap:
    owners_by_path: Mapping[str, tuple[str, ...]]
    governed_paths: tuple[str, ...]
    snapshot_only_paths: tuple[str, ...]
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def audit_intent_source_input_bindings(
    root: str | Path,
    manifest: ModelRegressionManifest,
    contributions: Sequence[Any],
    source_identities: Sequence[Any] = (),
) -> tuple[str, ...]:
    """Compare active local intent sources with exact owner-local inputs.

    WorkContext artifacts deliberately remain on their typed external identity
    path.  This comparison owns only direct project files and never treats a
    broad authored glob as an intent-owner binding.
    """

    from .model_intent import (
        ModelIntentContribution,
        ModelIntentSourceIdentity,
    )

    root_path = Path(root).resolve()
    items = tuple(contributions)
    identities = tuple(source_identities)
    errors: list[str] = []
    if any(not isinstance(item, ModelIntentContribution) for item in items):
        return ("intent-source input review requires typed contributions",)
    if identities and any(
        not isinstance(item, ModelIntentSourceIdentity) for item in identities
    ):
        return ("intent-source input review requires typed source identities",)

    contribution_by_id = {item.contribution_id: item for item in items}
    if len(contribution_by_id) != len(items):
        errors.append("intent-source input review has duplicate contribution ids")
    identity_by_id = {item.contribution_id: item for item in identities}
    if identities and len(identity_by_id) != len(identities):
        errors.append("intent-source input review has duplicate source identities")
    if identities and set(identity_by_id) != set(contribution_by_id):
        errors.append(
            "intent-source input review contribution/source denominator differs"
        )

    entries = {entry.model_id: entry for entry in manifest.entries}
    expected_by_owner: dict[str, set[str]] = {
        owner: set() for owner in entries
    }
    for contribution in items:
        raw_owner = contribution.logical_model_id
        if not raw_owner.startswith("model:"):
            errors.append(
                f"{contribution.contribution_id}: logical model owner is not exact: {raw_owner}"
            )
            continue
        owner = raw_owner.split("model:", 1)[1]
        if not owner or owner not in entries:
            errors.append(
                f"{contribution.contribution_id}: unknown logical model owner: {raw_owner}"
            )
            continue
        identity = identity_by_id.get(contribution.contribution_id)
        if identity is not None:
            if identity.authority_kind == "work_context":
                continue
            path = identity.resolved_project_ref
        elif contribution.work_context_id:
            continue
        else:
            path = contribution.source_ref
        expected_by_owner[owner].add(path)

    for owner, entry in sorted(entries.items()):
        actual_rows = tuple(entry.intent_source_inputs)
        actual = set(actual_rows)
        if len(actual) != len(actual_rows):
            errors.append(f"{owner}: duplicate exact intent-source inputs")
        expected = expected_by_owner[owner]
        for path in sorted(expected - actual):
            errors.append(f"{owner}: missing intent-source input: {path}")
        for path in sorted(actual - expected):
            errors.append(f"{owner}: extra intent-source input: {path}")
        for path in sorted(actual):
            candidate = (root_path / Path(*PurePosixPath(path).parts)).resolve()
            try:
                candidate.relative_to(root_path)
            except ValueError:
                errors.append(f"{owner}: intent-source input escapes repository: {path}")
                continue
            if not candidate.is_file():
                errors.append(f"{owner}: intent-source input is not a file: {path}")
    return tuple(errors)


def _resolve_relative_files(
    root: Path,
    patterns: Sequence[str],
) -> tuple[str, ...]:
    values: set[str] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                values.add(resolved.relative_to(root).as_posix())
            except ValueError as exc:
                raise ModelRegressionManifestError(
                    f"impact-map input escapes repository: {path}"
                ) from exc
    return tuple(sorted(values))


def _glob_covers_relative_path(relative_path: str, pattern: str) -> bool:
    """Check one already-known path against a glob without walking its tree.

    Snapshot-only selectors commonly contain ``**`` and may cover a very large
    historical evidence tree.  Impact-map collision checks only need to know
    whether a governed path is also selected by one of those patterns, so the
    check is intentionally symbolic and never materializes the snapshot tree.
    The second variant gives ``**/`` its normal zero-directory meaning.
    """

    normalized_path = str(relative_path).replace("\\", "/")
    normalized_pattern = str(pattern).replace("\\", "/")
    variants = {normalized_pattern}
    if "/**/" in normalized_pattern:
        variants.add(normalized_pattern.replace("/**/", "/"))
    return any(fnmatch.fnmatchcase(normalized_path, item) for item in variants)


def compile_model_impact_map(
    root: str | Path,
    manifest: ModelRegressionManifest,
) -> ModelImpactMap:
    """Compile exact local/shared ownership and fail closed on unknown inputs."""

    root_path = Path(root).resolve()
    errors: list[str] = []
    registered = {entry.model_id for entry in manifest.entries}
    if not manifest.governed_input_globs:
        errors.append("governed_input_globs must not be empty")
    component_ids = [item.component_id for item in manifest.shared_input_groups]
    for duplicate in sorted(
        {item for item in component_ids if component_ids.count(item) > 1}
    ):
        errors.append(f"duplicate shared component_id: {duplicate}")
    for group in manifest.shared_input_groups:
        if not group.component_id or not group.globs or not group.consumers:
            errors.append(
                "shared input group requires component_id, globs, and consumers"
            )
        for consumer in sorted(set(group.consumers) - registered):
            errors.append(
                f"{group.component_id}: unknown shared-input consumer: {consumer}"
            )
    governed = _resolve_relative_files(
        root_path,
        manifest.governed_input_globs,
    )
    # Do not recursively enumerate historical evidence just to check whether
    # a current governed source accidentally overlaps a snapshot selector.
    # The governed set is already finite; symbolic matching preserves the
    # collision guarantee while keeping the audit bounded.
    overlap = sorted(
        path
        for path in governed
        if any(
            _glob_covers_relative_path(path, pattern)
            for pattern in manifest.snapshot_only_input_globs
        )
    )
    errors.extend(
        f"impact path is both governed and snapshot-only: {path}"
        for path in overlap
    )
    owners: dict[str, set[str]] = {}
    for entry in manifest.entries:
        for path in _resolve_relative_files(
            root_path,
            entry.effective_input_patterns,
        ):
            owners.setdefault(path, set()).add(entry.model_id)
    for group in manifest.shared_input_groups:
        for path in _resolve_relative_files(root_path, group.globs):
            owners.setdefault(path, set()).update(group.consumers)
    for path in sorted(set(governed) - set(owners)):
        errors.append(f"governed model input has no declared owner: {path}")
    return ModelImpactMap(
        owners_by_path={
            path: tuple(sorted(values)) for path, values in sorted(owners.items())
        },
        governed_paths=governed,
        snapshot_only_paths=(),
        errors=tuple(errors),
    )


@dataclass(frozen=True)
class ModelRunResult:
    model_id: str
    status: str
    exit_code: int | None
    seconds: float
    command: tuple[str, ...]
    stdout_path: str
    stderr_path: str
    receipt_path: str
    artifact_paths: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()
    message: str = ""
    model_instance_id: str = ""
    model_kind: str = ""
    model_instance_fingerprint: str = ""
    input_inventory_fingerprint: str = ""
    input_inventory: tuple[Mapping[str, str], ...] = ()
    artifact_fingerprints: Mapping[str, str] = field(default_factory=dict)
    purpose_closure_fingerprint: str = ""
    purpose_claim_boundary: str = ""
    stdout: Mapping[str, Any] = field(default_factory=dict, compare=False)
    stderr: Mapping[str, Any] = field(default_factory=dict, compare=False)
    execution_disposition: str = "execute"
    producer_invocations: int = 1
    receipt_fingerprint: str = ""
    supervision: SupervisedCommandResult | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    # Execution policy is diagnostic/reuse-compatibility evidence only.  It
    # is deliberately not part of the model functional projection or owner
    # identity.  The observed duration is retained so a later tightened
    # supervisor budget can demote only the affected leaf instead of making
    # the whole model parent stale.
    resource_policy_fingerprint: str = ""
    # This is populated only from the native runner's explicit machine
    # projection.  It is intentionally not derived from purpose declarations
    # or parent counts.  Keep it after ``supervision`` so adding this optional
    # projection does not shift the historical positional constructor API.
    executed_case_ids: tuple[str, ...] = ()
    # Strict model evidence is producer-written native case rows, not the
    # stdout marker above.  These fields are optional for legacy/non-strict
    # model runs and are retained in the child receipt for exact reuse.
    native_case_results: tuple[NativeModelCaseResult, ...] = ()
    native_case_result_artifact_path: str = ""
    native_case_result_artifact_fingerprint: str = ""
    native_case_verification: NativeCaseVerification | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "native_case_results",
            _coerce_native_case_results(
                self.native_case_results,
                context=f"model result {self.model_id}",
            ),
        )
        if self.native_case_verification is not None and not isinstance(
            self.native_case_verification, NativeCaseVerification
        ):
            raise TypeError("model result native_case_verification must be a NativeCaseVerification")
        object.__setattr__(
            self,
            "native_case_result_artifact_path",
            str(self.native_case_result_artifact_path),
        )
        object.__setattr__(
            self,
            "native_case_result_artifact_fingerprint",
            str(self.native_case_result_artifact_fingerprint),
        )

    @property
    def ok(self) -> bool:
        return self.status == VALIDATION_STATUS_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "seconds": self.seconds,
            "command": list(self.command),
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "receipt_path": self.receipt_path,
            "artifact_paths": list(self.artifact_paths),
            "finding_codes": list(self.finding_codes),
            "message": self.message,
            "model_instance_id": self.model_instance_id,
            "model_kind": self.model_kind,
            "model_instance_fingerprint": self.model_instance_fingerprint,
            "input_inventory_fingerprint": self.input_inventory_fingerprint,
            "input_inventory": [dict(item) for item in self.input_inventory],
            "artifact_fingerprints": dict(self.artifact_fingerprints),
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
            "purpose_claim_boundary": self.purpose_claim_boundary,
            "stdout": dict(self.stdout),
            "stderr": dict(self.stderr),
            "execution_disposition": self.execution_disposition,
            "producer_invocations": self.producer_invocations,
            "receipt_fingerprint": self.receipt_fingerprint,
            "resource_policy_fingerprint": self.resource_policy_fingerprint,
            "executed_case_ids": list(self.executed_case_ids),
            "native_case_results": [
                row.to_dict() for row in self.native_case_results
            ],
            "native_case_result_artifact_path": (
                self.native_case_result_artifact_path
            ),
            "native_case_result_artifact_fingerprint": (
                self.native_case_result_artifact_fingerprint
            ),
            "native_case_verification": (
                self.native_case_verification.to_dict()
                if self.native_case_verification is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ModelRegressionReport:
    root: str
    tier: str
    output_dir: str
    audit: ManifestAudit
    results: tuple[ModelRunResult, ...]
    selected_model_ids: tuple[str, ...]
    skipped_model_ids: tuple[str, ...]
    unavailable_optional_model_ids: tuple[str, ...] = ()
    mutation_paths: tuple[str, ...] = ()
    started_at_epoch: float = 0.0
    finished_at_epoch: float = 0.0
    command: str = "flowguard-model-regressions"
    parent_claim_scope: str = "scoped"
    parent_receipt_path: str = ""
    parent_receipt_fingerprint: str = ""
    initial_observation_seconds: float = 0.0
    receipt_reconciliation_seconds: float = 0.0
    final_freshness_seconds: float = 0.0
    parent_composition_seconds: float = 0.0
    per_leaf_source_current_rebuild_count: int = 0
    per_leaf_receipt_store_scan_count: int = 0
    receipt_reconciliation_count: int = 0
    initial_observation_fingerprint: str = ""
    final_freshness_fingerprint: str = ""

    @property
    def status(self) -> str:
        if not self.audit.ok or self.mutation_paths:
            return VALIDATION_STATUS_BLOCKED
        children = tuple(
            ValidationChildResult(
                child_id=item.model_id,
                status=item.status,
                summary=item.message,
                receipt_id=item.receipt_path,
                artifact_paths=item.artifact_paths,
                claim_boundary="This child receipt covers only the declared model runner invocation.",
                payload={},
            )
            for item in self.results
        )
        return aggregate_status(children, required_child_ids=self.selected_model_ids)

    @property
    def ok(self) -> bool:
        return self.status == VALIDATION_STATUS_PASS

    def to_validation_result(self) -> ValidationResult:
        counts = {
            "registered": len(self.audit.registered_model_ids),
            "selected": len(self.selected_model_ids),
            "passed": sum(item.ok for item in self.results),
            "failed": sum(not item.ok for item in self.results),
            "skipped": len(self.skipped_model_ids),
            "unavailable_optional": len(self.unavailable_optional_model_ids),
            "executed": sum(item.execution_disposition == "execute" for item in self.results),
            "reused": sum(item.execution_disposition == "reuse_current" for item in self.results),
            "producer_invocations": sum(item.producer_invocations for item in self.results),
        }
        children = tuple(
            ValidationChildResult(
                child_id=item.model_id,
                status=item.status,
                summary=item.message,
                receipt_id=item.receipt_path,
                artifact_paths=(item.stdout_path, item.stderr_path, item.receipt_path, *item.artifact_paths),
                claim_boundary="This child receipt covers only the declared model runner invocation.",
                payload={
                    "exit_code": item.exit_code,
                    "seconds": item.seconds,
                    "finding_codes": list(item.finding_codes),
                    "model_instance_id": item.model_instance_id,
                    "model_instance_fingerprint": item.model_instance_fingerprint,
                    "input_inventory_fingerprint": item.input_inventory_fingerprint,
                    "execution_disposition": item.execution_disposition,
                    "receipt_fingerprint": item.receipt_fingerprint,
                    "executed_case_ids": list(item.executed_case_ids),
                    "native_case_result_artifact_path": (
                        item.native_case_result_artifact_path
                    ),
                    "native_case_result_artifact_fingerprint": (
                        item.native_case_result_artifact_fingerprint
                    ),
                    "native_case_verification": (
                        item.native_case_verification.to_dict()
                        if item.native_case_verification is not None
                        else None
                    ),
                },
            )
            for item in self.results
        )
        failures = tuple(
            {"code": item.finding_codes[0] if item.finding_codes else "model_failed", "message": f"{item.model_id}: {item.message}"}
            for item in self.results
            if not item.ok
        )
        blockers = tuple({"code": "manifest_audit", "message": item} for item in self.audit.errors) + tuple(
            {"code": "tracked_mutation", "message": item} for item in self.mutation_paths
        )
        claim = (
            "Full-tier success covers every required-public model and every available optional-local model registered in the current manifest."
            if self.parent_claim_scope == "full"
            else (
                f"{self.tier.title()}-tier success is scoped feedback and does "
                "not support a full-model release claim."
            )
        )
        return ValidationResult(
            command=self.command,
            status=self.status,
            scope="model-regression-manifest",
            tier=self.tier,
            counts=counts,
            failures=failures,
            blockers=blockers,
            residual_risk=(
                *(() if self.tier == "full" else ("Models assigned to broader tiers were not executed.",)),
                *(
                    ("Optional local-only models were absent and are not public release requirements.",)
                    if self.unavailable_optional_model_ids
                    else ()
                ),
            ),
            claim_boundary=claim,
            progress_summary={
                "started_at_epoch": self.started_at_epoch,
                "finished_at_epoch": self.finished_at_epoch,
                "elapsed_seconds": round(max(0.0, self.finished_at_epoch - self.started_at_epoch), 3),
            },
            artifact_paths=(str(Path(self.output_dir) / "report.json"),),
            children=children,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = self.to_validation_result().to_dict()
        payload.update(
            {
                "root": self.root,
                "output_dir": self.output_dir,
                "manifest_audit": self.audit.to_dict(),
                "selected_model_ids": list(self.selected_model_ids),
                "skipped_model_ids": list(self.skipped_model_ids),
                "unavailable_optional_model_ids": list(self.unavailable_optional_model_ids),
                "mutation_paths": list(self.mutation_paths),
                "parent_claim_scope": self.parent_claim_scope,
                "parent_receipt_path": self.parent_receipt_path,
                "parent_receipt_fingerprint": self.parent_receipt_fingerprint,
                "validation_observation": {
                    "initial_fingerprint": self.initial_observation_fingerprint,
                    "final_freshness_fingerprint": (
                        self.final_freshness_fingerprint
                    ),
                    "complete_observation_count": (
                        2 if self.final_freshness_fingerprint else 1
                    ),
                    "initial_seconds": self.initial_observation_seconds,
                    "receipt_reconciliation_seconds": (
                        self.receipt_reconciliation_seconds
                    ),
                    "final_freshness_seconds": self.final_freshness_seconds,
                    "parent_composition_seconds": self.parent_composition_seconds,
                    "per_leaf_source_current_rebuild_count": (
                        self.per_leaf_source_current_rebuild_count
                    ),
                    "per_leaf_receipt_store_scan_count": (
                        self.per_leaf_receipt_store_scan_count
                    ),
                    "receipt_reconciliation_count": (
                        self.receipt_reconciliation_count
                    ),
                },
                "results": [item.to_dict() for item in self.results],
            }
        )
        return payload


@dataclass(frozen=True)
class CurrentModelRegressionChildEvidence:
    """One independently verified current model-owner leaf receipt."""

    model_id: str
    receipt_id: str
    receipt_fingerprint: str
    model_instance_id: str = ""
    model_instance_fingerprint: str = ""
    input_inventory_fingerprint: str = ""
    purpose_closure_fingerprint: str = ""
    # Explicit IDs reported by this model's native runner.  These are kept
    # separate from the parent composition so a parent can never manufacture
    # a case execution claim for a child.
    executed_case_ids: tuple[str, ...] = ()
    # Exact native-to-blueprint projections are persisted alongside the raw
    # producer IDs.  The parent resolver must round-trip these fields rather
    # than deriving them from a current blueprint or from case-name aliases.
    executed_behavior_case_ids: tuple[str, ...] = ()
    native_case_bindings: tuple[NativeCaseBinding, ...] = ()
    native_case_binding_verification: NativeBindingVerification | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    receipt: EvidenceReceipt | None = field(default=None, compare=False, repr=False)
    verification: ReceiptVerificationResult | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    native_case_results: tuple[NativeModelCaseResult, ...] = ()
    native_case_result_artifact_path: str = ""
    native_case_result_artifact_fingerprint: str = ""
    native_case_verification: NativeCaseVerification | None = field(
        default=None,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "receipt_fingerprint", str(self.receipt_fingerprint))
        if any(
            not isinstance(item, str) or not item.strip()
            for item in self.executed_case_ids
        ):
            raise ModelRegressionEvidenceError(
                f"executed case ids for model child must be non-empty strings: {self.model_id}"
            )
        object.__setattr__(
            self,
            "executed_case_ids",
            tuple(item.strip() for item in self.executed_case_ids),
        )
        if len(self.executed_case_ids) != len(set(self.executed_case_ids)):
            raise ModelRegressionEvidenceError(
                f"duplicate executed case ids for model child: {self.model_id}"
            )
        object.__setattr__(
            self,
            "executed_behavior_case_ids",
            _coerce_executed_case_ids(
                self.executed_behavior_case_ids,
                context=f"model child {self.model_id}",
            ),
        )
        typed_bindings: list[NativeCaseBinding] = []
        for index, binding in enumerate(self.native_case_bindings):
            if not isinstance(binding, NativeCaseBinding):
                raise TypeError(
                    f"model child native_case_bindings[{index}] must be a NativeCaseBinding"
                )
            if binding.owner_id != self.model_id and binding.owner_id != f"model:{self.model_id}":
                raise ModelRegressionEvidenceError(
                    f"model child native case binding owner mismatch: {self.model_id}"
                )
            typed_bindings.append(binding)
        object.__setattr__(self, "native_case_bindings", tuple(typed_bindings))
        if self.native_case_binding_verification is not None and not isinstance(
            self.native_case_binding_verification, NativeBindingVerification
        ):
            raise TypeError(
                "model child native_case_binding_verification must be a NativeBindingVerification"
            )
        object.__setattr__(
            self,
            "native_case_results",
            _coerce_native_case_results(
                self.native_case_results,
                context=f"model child {self.model_id}",
            ),
        )
        if self.native_case_verification is not None and not isinstance(
            self.native_case_verification, NativeCaseVerification
        ):
            raise TypeError(
                "model child native_case_verification must be a NativeCaseVerification"
            )
        object.__setattr__(
            self,
            "native_case_result_artifact_path",
            str(self.native_case_result_artifact_path),
        )
        object.__setattr__(
            self,
            "native_case_result_artifact_fingerprint",
            str(self.native_case_result_artifact_fingerprint),
        )
        if self.receipt is not None and not isinstance(self.receipt, EvidenceReceipt):
            raise TypeError("model child receipt must be an EvidenceReceipt")
        if self.verification is not None and not isinstance(
            self.verification, ReceiptVerificationResult
        ):
            raise TypeError("model child verification must be a ReceiptVerificationResult")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "model_instance_id": self.model_instance_id,
            "model_instance_fingerprint": self.model_instance_fingerprint,
            "input_inventory_fingerprint": self.input_inventory_fingerprint,
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
            "executed_case_ids": list(self.executed_case_ids),
            "executed_behavior_case_ids": list(self.executed_behavior_case_ids),
            "native_case_results": [
                row.to_dict() for row in self.native_case_results
            ],
            "native_case_result_artifact_path": (
                self.native_case_result_artifact_path
            ),
            "native_case_result_artifact_fingerprint": (
                self.native_case_result_artifact_fingerprint
            ),
            "native_case_verification": (
                self.native_case_verification.to_dict()
                if self.native_case_verification is not None
                else None
            ),
            "native_case_bindings": [
                row.to_dict() for row in self.native_case_bindings
            ],
            "native_case_binding_verification": (
                self.native_case_binding_verification.to_dict()
                if self.native_case_binding_verification is not None
                else None
            ),
        }


@dataclass(frozen=True)
class CurrentModelRegressionParentEvidence:
    """The unique current full parent plus its independently verified leaves."""

    manifest_fingerprint: str
    parent_artifact_path: str
    parent_artifact_fingerprint: str
    parent_execution_receipt_id: str
    parent_execution_receipt_fingerprint: str
    children: tuple[CurrentModelRegressionChildEvidence, ...]
    claim_boundary: str = (
        "The parent proves only the exact current full/full/pass composition. "
        "Every child identity remains independently owned by its model receipt."
    )

    @property
    def child_evidence_by_model_id(
        self,
    ) -> Mapping[str, CurrentModelRegressionChildEvidence]:
        return {item.model_id: item for item in self.children}

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "parent_artifact_path": self.parent_artifact_path,
            "parent_artifact_fingerprint": self.parent_artifact_fingerprint,
            "parent_execution_receipt_id": self.parent_execution_receipt_id,
            "parent_execution_receipt_fingerprint": (
                self.parent_execution_receipt_fingerprint
            ),
            "children": [item.to_dict() for item in self.children],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class ModelOwnerExecutionEvidence:
    """One model-owner leaf and its explicit native case projection.

    The receipt and verification objects are in-memory handles to the exact
    immutable leaf resolved by ``resolve_current_full_model_regression_parent``.
    They are deliberately excluded from ``to_dict``; serialization carries
    only their immutable identities and the native case IDs.
    """

    owner_id: str
    model_id: str
    receipt_id: str = ""
    receipt_fingerprint: str = ""
    executed_case_ids: tuple[str, ...] = ()
    required_case_ids: tuple[str, ...] = ()
    execution_disposition: str = "execute"
    receipt: EvidenceReceipt | None = field(default=None, compare=False, repr=False)
    verification: ReceiptVerificationResult | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    finding_codes: tuple[str, ...] = ()
    # ``native_case_results_required`` is set by strict consumers (or when a
    # frozen native contract mapping is supplied).  Legacy model-owner
    # projections remain readable, but they cannot satisfy that gate.
    native_case_results_required: bool = False
    native_case_results: tuple[NativeModelCaseResult, ...] = ()
    native_case_result_artifact_path: str = ""
    native_case_result_artifact_fingerprint: str = ""
    native_case_verification: NativeCaseVerification | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    # Raw producer IDs and validated blueprint projections are separate
    # evidence surfaces.  The latter is populated only by the exact binding
    # verifier; it is never derived by splitting or suffix-matching a raw ID.
    executed_behavior_case_ids: tuple[str, ...] = ()
    native_case_bindings: tuple[NativeCaseBinding, ...] = ()
    native_case_binding_verification: NativeBindingVerification | None = field(
        default=None,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        for name in ("owner_id", "model_id", "receipt_id", "receipt_fingerprint", "execution_disposition"):
            object.__setattr__(self, name, str(getattr(self, name)))
        for name in (
            "executed_case_ids",
            "executed_behavior_case_ids",
            "required_case_ids",
            "finding_codes",
        ):
            values = tuple(
                str(item).strip()
                for item in getattr(self, name)
                if str(item).strip()
            )
            if len(values) != len(set(values)):
                raise ModelRegressionEvidenceError(
                    f"duplicate {name} for model owner: {self.owner_id}"
                )
            object.__setattr__(self, name, values)
        typed_bindings: list[NativeCaseBinding] = []
        for index, binding in enumerate(self.native_case_bindings):
            if not isinstance(binding, NativeCaseBinding):
                raise TypeError(
                    f"model owner native_case_bindings[{index}] must be a NativeCaseBinding"
                )
            if binding.owner_id != self.owner_id:
                raise ModelRegressionEvidenceError(
                    f"model owner native case binding owner mismatch: {self.owner_id}"
                )
            typed_bindings.append(binding)
        object.__setattr__(self, "native_case_bindings", tuple(typed_bindings))
        if self.native_case_binding_verification is not None and not isinstance(
            self.native_case_binding_verification, NativeBindingVerification
        ):
            raise TypeError(
                "model owner native_case_binding_verification must be a NativeBindingVerification"
            )
        if not isinstance(self.native_case_results_required, bool):
            raise TypeError(
                "model owner native_case_results_required must be a boolean"
            )
        object.__setattr__(
            self,
            "native_case_results",
            _coerce_native_case_results(
                self.native_case_results,
                context=f"model owner {self.owner_id}",
            ),
        )
        if self.native_case_verification is not None and not isinstance(
            self.native_case_verification, NativeCaseVerification
        ):
            raise TypeError(
                "model owner native_case_verification must be a NativeCaseVerification"
            )
        object.__setattr__(
            self,
            "native_case_result_artifact_path",
            str(self.native_case_result_artifact_path),
        )
        object.__setattr__(
            self,
            "native_case_result_artifact_fingerprint",
            str(self.native_case_result_artifact_fingerprint),
        )
        if self.receipt is not None and not isinstance(self.receipt, EvidenceReceipt):
            raise TypeError("model owner receipt must be an EvidenceReceipt")
        if self.verification is not None and not isinstance(
            self.verification, ReceiptVerificationResult
        ):
            raise TypeError("model owner verification must be a ReceiptVerificationResult")

    @property
    def missing_case_ids(self) -> tuple[str, ...]:
        executed = set(
            self.executed_behavior_case_ids
            if self.native_case_bindings
            else self.executed_case_ids
        )
        return tuple(case_id for case_id in self.required_case_ids if case_id not in executed)

    @property
    def foreign_case_ids(self) -> tuple[str, ...]:
        if not self.required_case_ids:
            return ()
        if self.native_case_bindings:
            # Binding verifier findings are the authoritative raw foreign and
            # duplicate inventory.  Do not treat raw producer IDs as
            # blueprint aliases here.
            if self.native_case_binding_verification is not None:
                return tuple(
                    self.native_case_binding_verification.foreign_native_case_ids
                )
            return ()
        required = set(self.required_case_ids)
        return tuple(case_id for case_id in self.executed_case_ids if case_id not in required)

    @property
    def receipt_is_direct_leaf(self) -> bool:
        if self.receipt is None:
            return False
        return not bool(
            self.receipt.required_child_receipts or self.receipt.consumed_child_receipts
        ) and self.receipt.subject_kind == OWNER_RECEIPT_KIND

    @property
    def receipt_is_current_pass(self) -> bool:
        expected_subject = f"validation-owner:{self.owner_id}"
        expected_obligation = f"model-regression:{self.model_id}"
        return bool(
            self.receipt_is_direct_leaf
            and self.receipt_id == self.receipt.receipt_id
            and self.receipt_fingerprint == self.receipt.fingerprint
            and self.receipt.subject_kind == OWNER_RECEIPT_KIND
            and self.receipt.subject_id == expected_subject
            and self.receipt.producer_id == expected_subject
            and self.receipt.result_status == RECEIPT_STATUS_PASS
            and self.receipt.exit_code == 0
            and self.receipt.claim_scope == "full"
            and self.receipt.covered_obligations == (expected_obligation,)
            and not self.receipt.skipped_checks
            and not self.receipt.blockers
            and self.verification is not None
            and self.verification.receipt_id == self.receipt.receipt_id
            and self.verification.receipt_fingerprint == self.receipt.fingerprint
            and self.verification.ok
        )

    def matches_case_id(self, *candidate_ids: str) -> bool:
        """Return true only for an exact validated blueprint case ID.

        Legacy owner projections without a binding table retain exact raw-ID
        behavior for compatibility.  Once bindings are present, only the
        verifier's projected blueprint IDs are consulted; a source ID,
        parameter ID, or suffix can never substitute for the projection.
        """

        executed = set(
            self.executed_behavior_case_ids
            if self.native_case_bindings
            else self.executed_case_ids
        )
        return any(
            str(candidate).strip() in executed
            for candidate in candidate_ids
            if str(candidate).strip()
        )

    @property
    def native_case_protocol_complete(self) -> bool:
        """Whether the owner has independently verified native result rows."""

        return bool(
            self.native_case_results
            and self.native_case_result_artifact_path
            and self.native_case_result_artifact_fingerprint.startswith(
                "sha256:"
            )
            and self.native_case_verification is not None
            and self.native_case_verification.ok
            and (
                not self.native_case_bindings
                or (
                    self.native_case_binding_verification is not None
                    and self.native_case_binding_verification.ok
                )
            )
        )

    @property
    def complete(self) -> bool:
        return bool(
            not self.missing_case_ids
            and self.receipt_is_current_pass
            and not self.finding_codes
            and (
                not self.native_case_results_required
                or self.native_case_protocol_complete
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_EXECUTION_EVIDENCE_SCHEMA,
            "owner_id": self.owner_id,
            "model_id": self.model_id,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "executed_case_ids": list(self.executed_case_ids),
            "executed_behavior_case_ids": list(self.executed_behavior_case_ids),
            "required_case_ids": list(self.required_case_ids),
            "execution_disposition": self.execution_disposition,
            "finding_codes": list(self.finding_codes),
            "receipt_is_direct_leaf": self.receipt_is_direct_leaf,
            "receipt_is_current_pass": self.receipt_is_current_pass,
            "missing_case_ids": list(self.missing_case_ids),
            "foreign_case_ids": list(self.foreign_case_ids),
            "native_case_results_required": self.native_case_results_required,
            "native_case_results": [
                row.to_dict() for row in self.native_case_results
            ],
            "native_case_result_artifact_path": (
                self.native_case_result_artifact_path
            ),
            "native_case_result_artifact_fingerprint": (
                self.native_case_result_artifact_fingerprint
            ),
            "native_case_verification": (
                self.native_case_verification.to_dict()
                if self.native_case_verification is not None
                else None
            ),
            "native_case_bindings": [
                item.to_dict() for item in self.native_case_bindings
            ],
            "native_case_binding_verification": (
                self.native_case_binding_verification.to_dict()
                if self.native_case_binding_verification is not None
                else None
            ),
            "complete": self.complete,
        }


@dataclass(frozen=True)
class ModelRegressionExecutionEvidencePackage:
    """Leaf-owned model case evidence consumed by the blueprint builders."""

    manifest_fingerprint: str
    owners: tuple[ModelOwnerExecutionEvidence, ...]
    coverage_edge_count: int = 0
    validation_owner_contracts: tuple[Any, ...] = ()
    claim_boundary: str = (
        "Only native model-owner case IDs and independently verified direct leaf receipts; "
        "the model parent is composition metadata and never a leaf."
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "owners", tuple(sorted(self.owners, key=lambda row: row.owner_id)))
        if any(not isinstance(row, ModelOwnerExecutionEvidence) for row in self.owners):
            raise TypeError("model execution package owners must be typed leaf evidence")
        owner_ids = tuple(row.owner_id for row in self.owners)
        if len(owner_ids) != len(set(owner_ids)):
            raise ModelRegressionEvidenceError("model execution package has duplicate owner leaves")
        if isinstance(self.coverage_edge_count, bool) or int(self.coverage_edge_count) < 0:
            raise ValueError("coverage_edge_count must be a non-negative integer")
        object.__setattr__(self, "coverage_edge_count", int(self.coverage_edge_count))
        object.__setattr__(self, "validation_owner_contracts", tuple(self.validation_owner_contracts))
        object.__setattr__(self, "claim_boundary", str(self.claim_boundary))

    @property
    def owner_count(self) -> int:
        return len(self.owners)

    @property
    def planned_case_count(self) -> int:
        return sum(len(row.required_case_ids) for row in self.owners)

    @property
    def executed_case_count(self) -> int:
        return sum(len(row.executed_case_ids) for row in self.owners)

    @property
    def missing_case_ids(self) -> tuple[str, ...]:
        return tuple(
            f"{row.owner_id}:{case_id}"
            for row in self.owners
            for case_id in row.missing_case_ids
        )

    @property
    def foreign_case_ids(self) -> tuple[str, ...]:
        return tuple(
            f"{row.owner_id}:{case_id}"
            for row in self.owners
            for case_id in row.foreign_case_ids
        )

    @property
    def receipt_gap_count(self) -> int:
        return sum(not row.receipt_is_current_pass for row in self.owners)

    @property
    def native_case_protocol_gap_count(self) -> int:
        return sum(
            row.native_case_results_required
            and not row.native_case_protocol_complete
            for row in self.owners
        )

    @property
    def status(self) -> str:
        if not self.owners:
            return "not_run"
        return "passed" if all(row.complete for row in self.owners) else "blocked"

    @property
    def complete(self) -> bool:
        return self.status == "passed"

    def owner(self, owner_id: str) -> ModelOwnerExecutionEvidence | None:
        key = str(owner_id)
        return next((row for row in self.owners if row.owner_id == key), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_EXECUTION_EVIDENCE_SCHEMA,
            "manifest_fingerprint": self.manifest_fingerprint,
            "owners": [row.to_dict() for row in self.owners],
            "coverage_edge_count": self.coverage_edge_count,
            "validation_owner_contracts": [
                row.to_dict() if hasattr(row, "to_dict") else dict(row)
                for row in self.validation_owner_contracts
            ],
            "owner_count": self.owner_count,
            "planned_case_count": self.planned_case_count,
            "executed_case_count": self.executed_case_count,
            "missing_case_ids": list(self.missing_case_ids),
            "foreign_case_ids": list(self.foreign_case_ids),
            "receipt_gap_count": self.receipt_gap_count,
            "native_case_protocol_gap_count": self.native_case_protocol_gap_count,
            "status": self.status,
            "complete": self.complete,
            "claim_boundary": self.claim_boundary,
        }


def build_model_regression_execution_evidence(
    parent_evidence: CurrentModelRegressionParentEvidence,
    *,
    required_case_ids_by_owner: Mapping[str, Sequence[str]] | None = None,
    required_case_ids_by_model: Mapping[str, Sequence[str]] | None = None,
    native_case_contracts_by_owner: Mapping[
        str, Sequence[NativeModelCaseContract]
    ] | None = None,
    native_case_bindings_by_owner: Mapping[
        str, Sequence[NativeCaseBinding]
    ] | None = None,
    require_native_case_results: bool = False,
    coverage_edge_count: int = 0,
    validation_owner_contracts: Sequence[Any] = (),
) -> ModelRegressionExecutionEvidencePackage:
    """Bind exact blueprint case identities to current model-owner leaves.

    ``required_case_ids_by_owner`` is supplied by the independently materialized
    blueprint.  The helper never fills a missing native ID from that mapping;
    it only compares the mapping with IDs present in each child result.
    ``require_native_case_results`` turns on the strict producer-result gate;
    under that gate a marker-only or empty result is incomplete.  When the
    optional native contract mapping is supplied, each row is additionally
    checked by ``verify_native_model_cases`` against its exact leaf/aggregate
    contract.  A binding mapping is a second, independent gate: raw producer
    IDs are projected onto blueprint IDs only after exact rows, dimensions,
    oracles, and aggregate children pass.  Legacy callers can continue to
    project marker IDs without claiming native protocol completion.
    """

    if not isinstance(parent_evidence, CurrentModelRegressionParentEvidence):
        raise TypeError("parent_evidence must be CurrentModelRegressionParentEvidence")
    if required_case_ids_by_owner is not None and required_case_ids_by_model is not None:
        raise ValueError("provide only one required case-id mapping")
    raw_mapping = required_case_ids_by_owner
    if raw_mapping is None and required_case_ids_by_model is not None:
        raw_mapping = {
            f"model:{str(model_id).removeprefix('model:')}": values
            for model_id, values in dict(required_case_ids_by_model).items()
        }
    if not isinstance(require_native_case_results, bool):
        raise TypeError("require_native_case_results must be a boolean")
    contract_mapping: dict[str, tuple[NativeModelCaseContract, ...]] = {}
    for raw_owner_id, raw_contracts in dict(
        native_case_contracts_by_owner or {}
    ).items():
        owner_id = str(raw_owner_id)
        if isinstance(raw_contracts, (str, bytes)):
            raise ModelRegressionEvidenceError(
                f"native case contracts for {owner_id} must be an array"
            )
        typed_contracts: list[NativeModelCaseContract] = []
        for index, contract in enumerate(raw_contracts):
            if not isinstance(contract, NativeModelCaseContract):
                raise ModelRegressionEvidenceError(
                    f"native case contract {owner_id}[{index}] is not typed"
                )
            if contract.owner_id != owner_id:
                raise ModelRegressionEvidenceError(
                    f"native case contract owner mismatch: {owner_id}[{index}]"
                )
            typed_contracts.append(contract)
        contract_mapping[owner_id] = tuple(typed_contracts)
    binding_mapping: dict[str, tuple[NativeCaseBinding, ...]] = {}
    for raw_owner_id, raw_bindings in dict(
        native_case_bindings_by_owner or {}
    ).items():
        owner_id = str(raw_owner_id)
        if isinstance(raw_bindings, (str, bytes)):
            raise ModelRegressionEvidenceError(
                f"native case bindings for {owner_id} must be an array"
            )
        typed_bindings: list[NativeCaseBinding] = []
        for index, binding in enumerate(raw_bindings):
            if not isinstance(binding, NativeCaseBinding):
                raise ModelRegressionEvidenceError(
                    f"native case binding {owner_id}[{index}] is not typed"
                )
            if binding.owner_id != owner_id:
                raise ModelRegressionEvidenceError(
                    f"native case binding owner mismatch: {owner_id}[{index}]"
                )
            typed_bindings.append(binding)
        binding_mapping[owner_id] = tuple(typed_bindings)
    if raw_mapping is None:
        if binding_mapping:
            raw_mapping = {
                owner_id: tuple(
                    binding.blueprint_case_id for binding in bindings
                )
                for owner_id, bindings in binding_mapping.items()
            }
        else:
            raw_mapping = {
                owner_id: tuple(contract.source_case_id for contract in contracts)
                for owner_id, contracts in contract_mapping.items()
            }
    if raw_mapping is None:
        raw_mapping = {}
    required = {
        str(owner_id): tuple(
            dict.fromkeys(str(case_id) for case_id in values if str(case_id))
        )
        for owner_id, values in dict(raw_mapping).items()
    }
    strict_native = bool(
        require_native_case_results or contract_mapping or binding_mapping
    )
    children = parent_evidence.child_evidence_by_model_id
    owners: list[ModelOwnerExecutionEvidence] = []
    for owner_id, case_ids in sorted(required.items()):
        model_id = owner_id.removeprefix("model:")
        child = children.get(model_id)
        if child is None:
            owners.append(
                ModelOwnerExecutionEvidence(
                    owner_id=owner_id,
                    model_id=model_id,
                    required_case_ids=case_ids,
                    native_case_results_required=strict_native,
                    finding_codes=("model_owner_child_missing",),
                )
            )
            continue
        findings: list[str] = []
        if child.receipt_id == parent_evidence.parent_execution_receipt_id:
            findings.append("model_parent_receipt_used_as_leaf")
        if child.receipt_fingerprint == parent_evidence.parent_execution_receipt_fingerprint:
            findings.append("model_parent_fingerprint_used_as_leaf")
        if child.receipt is None:
            findings.append("model_owner_receipt_missing")
        if child.verification is None:
            findings.append("model_owner_verification_missing")
        native_results = child.native_case_results
        native_path = child.native_case_result_artifact_path
        native_fingerprint = child.native_case_result_artifact_fingerprint
        native_verification = child.native_case_verification
        binding_verification: NativeBindingVerification | None = None
        binding_rows = binding_mapping.get(owner_id, ())
        if strict_native and not case_ids:
            findings.append("native_case_expected_case_ids_empty")
        if strict_native and not native_path:
            findings.append("native_case_result_artifact_missing")
        if strict_native and not native_fingerprint:
            findings.append("native_case_result_artifact_fingerprint_missing")
        if native_path:
            try:
                loaded_rows, loaded_path, loaded_fp, loaded_verification = (
                    _load_native_case_result_artifact(
                        native_path,
                        owner_id=owner_id,
                        marker_case_ids=child.executed_case_ids,
                    )
                )
                if native_results and not _native_result_rows_equal(
                    native_results, loaded_rows
                ):
                    findings.append("native_case_results_artifact_mismatch")
                if native_fingerprint and native_fingerprint != loaded_fp:
                    findings.append(
                        "native_case_result_artifact_fingerprint_mismatch"
                    )
                native_results = loaded_rows
                native_path = str(loaded_path)
                native_fingerprint = loaded_fp if native_fingerprint else ""
                native_verification = loaded_verification
            except ModelRegressionEvidenceError as exc:
                findings.append("native_case_results_invalid")
                native_verification = NativeCaseVerification(
                    ok=False,
                    findings=(str(exc),),
                )
        elif native_results:
            native_verification = NativeCaseVerification(
                ok=False,
                findings=("native_result_artifact_missing",),
            )
        if strict_native and not native_results:
            findings.append("native_case_results_missing")
        if native_verification is not None and not native_verification.ok:
            findings.append("native_case_results_invalid")
        contract_rows = contract_mapping.get(owner_id, ())
        if binding_rows:
            binding_ids = tuple(binding.blueprint_case_id for binding in binding_rows)
            if set(binding_ids) != set(case_ids):
                findings.append("native_case_binding_inventory_mismatch")
            if native_results:
                try:
                    binding_verification = verify_native_case_bindings(
                        binding_rows,
                        native_results,
                    )
                except (NativeCaseProtocolError, TypeError, ValueError) as exc:
                    binding_verification = NativeBindingVerification(
                        ok=False,
                        findings=(f"binding_verifier_error:{type(exc).__name__}:{exc}",),
                    )
                if not binding_verification.ok:
                    findings.extend(
                        f"native_case_binding:{item}"
                        for item in binding_verification.findings
                    )
            else:
                binding_verification = NativeBindingVerification(
                    ok=False,
                    missing_bindings=tuple(binding_ids),
                    findings=("binding_native_results_missing",),
                )
            if native_verification is None or not contract_rows:
                # A binding-only owner still receives a strict protocol
                # verification object.  It carries the binding gate's
                # findings rather than manufacturing a native contract pass.
                native_verification = NativeCaseVerification(
                    ok=bool(binding_verification and binding_verification.ok),
                    findings=(
                        tuple(binding_verification.findings)
                        if binding_verification is not None
                        else ("binding_verification_missing",)
                    ),
                    missing_case_ids=(
                        tuple(binding_verification.missing_bindings)
                        if binding_verification is not None
                        else tuple(binding_ids)
                    ),
                    foreign_case_ids=(
                        tuple(binding_verification.foreign_native_case_ids)
                        if binding_verification is not None
                        else ()
                    ),
                    duplicate_case_ids=(
                        tuple(binding_verification.duplicate_native_case_ids)
                        if binding_verification is not None
                        else ()
                    ),
                    leaf_case_ids=(
                        tuple(binding_verification.projected_case_ids)
                        if binding_verification is not None
                        else ()
                    ),
                )
                if not native_verification.ok:
                    findings.append("native_case_results_invalid")
        if contract_rows:
            contract_ids = tuple(row.source_case_id for row in contract_rows)
            expected_contract_ids = (
                {
                    native_id
                    for binding in binding_rows
                    for native_id in binding.native_case_ids
                }
                if binding_rows
                else set(case_ids)
            )
            if set(contract_ids) != expected_contract_ids:
                findings.append("native_case_contract_inventory_mismatch")
            if native_results:
                contract_verification = verify_native_model_cases(
                    contract_rows,
                    native_results,
                    require_current_inputs=True,
                )
                if binding_verification is not None:
                    native_verification = replace(
                        contract_verification,
                        ok=(
                            contract_verification.ok
                            and binding_verification.ok
                        ),
                        findings=tuple(
                            dict.fromkeys(
                                (
                                    *contract_verification.findings,
                                    *binding_verification.findings,
                                )
                            )
                        ),
                    )
                else:
                    native_verification = contract_verification
                if not contract_verification.ok:
                    findings.extend(
                        f"native_case_protocol:{item}"
                        for item in contract_verification.findings
                    )
                if binding_verification is not None and not binding_verification.ok:
                    findings.extend(
                        f"native_case_binding:{item}"
                        for item in binding_verification.findings
                    )
            else:
                findings.append("native_case_results_missing")
        owners.append(
            ModelOwnerExecutionEvidence(
                owner_id=owner_id,
                model_id=model_id,
                receipt_id=child.receipt_id,
                receipt_fingerprint=child.receipt_fingerprint,
                executed_case_ids=child.executed_case_ids,
                executed_behavior_case_ids=(
                    binding_verification.projected_case_ids
                    if binding_verification is not None
                    else ()
                ),
                required_case_ids=case_ids,
                execution_disposition="reuse_current",
                receipt=child.receipt,
                verification=child.verification,
                finding_codes=tuple(dict.fromkeys(findings)),
                native_case_results_required=strict_native,
                native_case_results=native_results,
                native_case_result_artifact_path=native_path,
                native_case_result_artifact_fingerprint=native_fingerprint,
                native_case_verification=native_verification,
                native_case_bindings=binding_rows,
                native_case_binding_verification=binding_verification,
            )
        )
    return ModelRegressionExecutionEvidencePackage(
        manifest_fingerprint=parent_evidence.manifest_fingerprint,
        owners=tuple(owners),
        coverage_edge_count=coverage_edge_count,
        validation_owner_contracts=tuple(validation_owner_contracts),
    )


ProgressCallback = Callable[[Mapping[str, Any]], None]


def discover_model_directories(root: str | Path = ".") -> tuple[Path, ...]:
    root_path = Path(root).resolve()
    base = root_path / ".flowguard" / "models" / "owners"
    if not base.is_dir():
        return ()
    return tuple(sorted(path.parent for path in base.glob("*/model.py") if path.is_file()))


def _model_id(root: Path, directory: Path) -> str:
    return directory.relative_to(root / ".flowguard" / "models" / "owners").as_posix()


def audit_manifest(root: str | Path, manifest: ModelRegressionManifest) -> ManifestAudit:
    root_path = Path(root).resolve()
    discovered = tuple(_model_id(root_path, item) for item in discover_model_directories(root_path))
    registered = tuple(item.model_id for item in manifest.entries)
    errors: list[str] = []
    duplicates = sorted({item for item in registered if registered.count(item) > 1})
    errors.extend(f"duplicate model_id: {item}" for item in duplicates)
    closures = tuple(item.purpose_closure for item in manifest.entries if item.purpose_closure is not None)
    try:
        validate_unique_model_instances(closures)
    except ModelPurposeError as exc:
        errors.append(str(exc))
    errors.extend(f"unregistered model directory: {item}" for item in sorted(set(discovered) - set(registered)))
    by_id = {item.model_id: item for item in manifest.entries}
    errors.extend(
        f"manifest required-public model missing from filesystem: {item}"
        for item in sorted(set(registered) - set(discovered))
        if by_id[item].distribution_policy == "required_public"
    )
    try:
        impact_map = compile_model_impact_map(root_path, manifest)
        errors.extend(impact_map.errors)
    except ModelRegressionManifestError as exc:
        errors.append(str(exc))
    for entry in manifest.entries:
        purpose = entry.purpose_closure
        if purpose is None:
            errors.append(f"{entry.model_id}: missing purpose_closure")
        elif purpose.reusable_model_type_id != entry.model_id:
            errors.append(f"{entry.model_id}: purpose reusable_model_type_id does not match model_id")
        elif not purpose.model_instance_id.startswith(f"regression:{entry.model_id}:"):
            errors.append(
                f"{entry.model_id}: purpose model_instance_id is not scoped to its logical regression model"
            )
        elif tuple(
            evidence_id
            for evidence_id in purpose.evidence_check_ids
            if evidence_id.startswith("check:model-regression:")
        ) != (f"check:model-regression:{entry.model_id}",):
            errors.append(
                f"{entry.model_id}: purpose requires one exact logical model-regression evidence identity"
            )
        expected_model_path = f".flowguard/models/owners/{entry.model_id}/model.py"
        expected_runner_path = f".flowguard/verification/owners/{entry.model_id}/run_checks.py"
        if not entry.model_id or entry.model_path != expected_model_path:
            errors.append(f"{entry.model_id or '<empty>'}: model_path must match model_id")
        elif not (root_path / entry.model_path).is_file() and entry.distribution_policy == "required_public":
            errors.append(f"{entry.model_id}: model_path does not exist")
        if len(entry.runner) < 2 or entry.runner[1] != expected_runner_path:
            errors.append(f"{entry.model_id or '<empty>'}: runner must use the current verification owner path")
        if entry.tier not in TIER_RANK:
            errors.append(f"{entry.model_id}: invalid tier {entry.tier!r}")
        if entry.timeout_seconds <= 0:
            errors.append(f"{entry.model_id}: timeout_seconds must be positive")
        if entry.mutation_policy not in {"none", "isolated_output", "mutating"}:
            errors.append(f"{entry.model_id}: invalid mutation_policy {entry.mutation_policy!r}")
        if entry.shard_safety_proof:
            proof = entry.shard_safety_proof
            if entry.mutation_policy != "isolated_output":
                errors.append(
                    f"{entry.model_id}: shard_safety_proof requires isolated_output mutation policy"
                )
            if proof.get("schema_version") != "flowguard.model_shard_safety_contract.v1":
                errors.append(f"{entry.model_id}: invalid shard_safety_proof schema")
            if int(proof.get("parallel_copies", 0)) < 2:
                errors.append(f"{entry.model_id}: shard_safety_proof requires at least two parallel copies")
            if proof.get("output_isolation") != "FLOWGUARD_OUTPUT_DIR":
                errors.append(f"{entry.model_id}: shard_safety_proof must bind FLOWGUARD_OUTPUT_DIR")
            if proof.get("shared_mutation_policy") != "zero_repository_mutation":
                errors.append(f"{entry.model_id}: shard_safety_proof must reject repository mutation")
            required_checks = {
                "serial_parallel_semantic_equivalence",
                "disjoint_artifact_ownership",
                "stable_input_inventory",
                "zero_repository_mutation",
            }
            declared_checks = {str(item) for item in proof.get("required_checks", ())}
            missing_checks = sorted(required_checks - declared_checks)
            if missing_checks:
                errors.append(
                    f"{entry.model_id}: shard_safety_proof missing checks: {', '.join(missing_checks)}"
                )
        if entry.shard_safe and entry.model_id == "harden_ui_content_visibility_validation":
            if not entry.shard_safety_proof:
                errors.append(
                    f"{entry.model_id}: shard-safe UI aggregate requires executable shard_safety_proof"
                )
        if entry.distribution_policy not in {"required_public", "optional_local"}:
            errors.append(f"{entry.model_id}: invalid distribution_policy {entry.distribution_policy!r}")
        if entry.distribution_policy == "optional_local" and len(entry.absence_reason.strip()) < 12:
            errors.append(f"{entry.model_id}: optional-local absence reason is not reviewable")
        if not entry.input_globs:
            errors.append(f"{entry.model_id}: input_globs must not be empty")
        elif entry.distribution_policy == "required_public":
            unresolved_patterns = tuple(
                pattern
                for pattern in entry.input_globs
                if not any(path.is_file() for path in root_path.glob(pattern))
            )
            errors.extend(
                f"{entry.model_id}: input_glob resolves no files: {pattern}"
                for pattern in unresolved_patterns
            )
        intent_paths = tuple(entry.intent_source_inputs)
        duplicate_intent_paths = tuple(
            sorted(
                path
                for path in set(intent_paths)
                if intent_paths.count(path) > 1
            )
        )
        errors.extend(
            f"{entry.model_id}: duplicate intent_source_input: {path}"
            for path in duplicate_intent_paths
        )
        for intent_path in intent_paths:
            normalized = intent_path.replace("\\", "/")
            pure = PurePosixPath(normalized)
            windows = PureWindowsPath(intent_path)
            if (
                not intent_path
                or intent_path != normalized
                or intent_path.startswith(("/", "\\"))
                or pure.is_absolute()
                or windows.is_absolute()
                or bool(windows.drive)
                or ".." in pure.parts
                or any(token in intent_path for token in ("*", "?", "[", "]"))
            ):
                errors.append(
                    f"{entry.model_id}: unsafe intent_source_input: {intent_path}"
                )
                continue
            resolved_intent = (root_path / Path(*pure.parts)).resolve()
            try:
                resolved_intent.relative_to(root_path)
            except ValueError:
                errors.append(
                    f"{entry.model_id}: intent_source_input escapes repository: {intent_path}"
                )
                continue
            if (
                entry.distribution_policy == "required_public"
                and not resolved_intent.is_file()
            ):
                errors.append(
                    f"{entry.model_id}: intent_source_input is not a file: {intent_path}"
                )
        if entry.excluded:
            if entry.runner:
                errors.append(f"{entry.model_id}: excluded entry must not define a runner")
            if len(entry.exclusion_reason.strip()) < 12:
                errors.append(f"{entry.model_id}: exclusion reason is not reviewable")
        else:
            if not entry.runner:
                errors.append(f"{entry.model_id}: missing runner")
            elif len(entry.runner) < 2 or entry.runner[0] != "{python}":
                errors.append(f"{entry.model_id}: runner must start with {{python}} and a repository-relative script")
            else:
                runner_path = root_path / entry.runner[1]
                if not runner_path.is_file() and entry.distribution_policy == "required_public":
                    errors.append(f"{entry.model_id}: runner does not exist: {entry.runner[1]}")
                elif purpose is not None and (root_path / entry.model_path).is_file() and runner_path.is_file():
                    try:
                        purpose.validate_current_files(root_path, model_path=entry.model_path, runner_path=entry.runner[1])
                    except ModelPurposeError as exc:
                        errors.append(f"{entry.model_id}: {exc}")
    return ManifestAudit(not errors, discovered, registered, tuple(errors))


def parse_shard(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        number_text, total_text = value.split("/", 1)
        number, total = int(number_text), int(total_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError("shard must use N/M with 1 <= N <= M") from exc
    if number < 1 or total < 1 or number > total:
        raise ValueError("shard must use N/M with 1 <= N <= M")
    return number, total


def select_entries(
    manifest: ModelRegressionManifest,
    *,
    tier: str,
    model_patterns: Sequence[str] = (),
    shard: str | None = None,
) -> tuple[ModelRegressionEntry, ...]:
    if tier not in TIER_RANK:
        raise ValueError(f"unsupported tier: {tier}")
    # The current manifest lives at ``.flowguard/models/regression-manifest.json``.
    # Resolve the project root from the manifest's ``.flowguard`` anchor rather
    # than assuming the older one-level layout.  Keeping this derived from the
    # actual path prevents a direct-current layout rewrite from silently
    # selecting zero models (and therefore producing no model receipts).
    try:
        flowguard_root = manifest.path.parents[1]
        if flowguard_root.name != ".flowguard":
            raise ValueError
        root = flowguard_root.parent
    except (IndexError, ValueError):
        root = manifest.path.parents[2]
    selected = [
        entry
        for entry in manifest.entries
        if not entry.excluded and TIER_RANK[entry.tier] <= TIER_RANK[tier]
        and (root / entry.model_path).is_file()
        and len(entry.runner) >= 2
        and (root / entry.runner[1]).is_file()
    ]
    if model_patterns:
        selected = [
            entry
            for entry in selected
            if any(fnmatch.fnmatchcase(entry.model_id, pattern) for pattern in model_patterns)
        ]
    selected.sort(key=lambda item: item.model_id)
    parsed = parse_shard(shard)
    if parsed:
        number, total = parsed
        selected = [entry for index, entry in enumerate(selected) if index % total == number - 1]
    return tuple(selected)


def _safe_artifact_dir(output_dir: Path, model_id: str) -> Path:
    digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:10]
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in model_id)
    path = (output_dir / f"{safe_name}-{digest}").resolve()
    if output_dir.resolve() not in path.parents:
        raise ValueError(f"unsafe model artifact path: {model_id}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _shard_safety_proof_dir(output_dir: Path, model_id: str) -> Path:
    """Keep nested shard-proof paths bounded while receipts retain model ids."""

    proof_root = (output_dir / "shard-safety").resolve()
    digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:16]
    path = (proof_root / f"p-{digest}").resolve()
    if proof_root not in path.parents:
        raise ValueError(f"unsafe shard-safety proof path: {model_id}")
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_entry_input_inventory(
    root: str | Path,
    entry: ModelRegressionEntry,
    *,
    additional_patterns: Sequence[str] = (),
    _pattern_cache: dict[str, tuple[Path, ...]] | None = None,
    _fingerprint_cache: dict[str, str] | None = None,
) -> tuple[dict[str, str], ...]:
    """Resolve manifest selectors to the exact immutable input inventory.

    ``additional_patterns`` is used by the model-system snapshot builder for
    manifest-declared shared components.  Shared infrastructure (for example
    the native case projection protocol) is a real input of every listed
    consumer; omitting it lets the model snapshot stay unchanged while that
    infrastructure evolves, breaking the living-model freshness guarantee.
    The parameter is explicit so small standalone/test manifests retain their
    historical inventory unless they declare the shared selectors themselves.
    """

    root_path = Path(root).resolve()
    inventory: dict[str, str] = {}
    pending_fingerprints: dict[str, Path] = {}
    patterns = tuple(
        dict.fromkeys(
            pattern
            for pattern in (
                *entry.effective_input_patterns,
                *additional_patterns,
            )
            if str(pattern).strip()
        )
    )
    for pattern in patterns:
        if _pattern_cache is not None and pattern in _pattern_cache:
            paths = _pattern_cache[pattern]
        else:
            paths = tuple(root_path.glob(pattern))
            if _pattern_cache is not None:
                _pattern_cache[pattern] = paths
        for path in paths:
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ModelRegressionManifestError(
                    f"{entry.model_id}: input resolves outside repository: {path}"
                ) from exc
            if _fingerprint_cache is not None and relative in _fingerprint_cache:
                inventory[relative] = _fingerprint_cache[relative]
            else:
                # Resolve each exact source path once and hash independent files
                # concurrently.  The fingerprints remain canonical SHA-256
                # values and the final inventory is still sorted below; this
                # only removes avoidable Windows per-file I/O serialization.
                pending_fingerprints.setdefault(relative, resolved)

    if pending_fingerprints:
        max_workers = min(8, len(pending_fingerprints))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(source_file_fingerprint, path): relative
                for relative, path in pending_fingerprints.items()
            }
            for future in as_completed(futures):
                relative = futures[future]
                fingerprint = future.result()
                inventory[relative] = fingerprint
                if _fingerprint_cache is not None:
                    _fingerprint_cache[relative] = fingerprint
    return tuple(
        {"path": path, "sha256": inventory[path]}
        for path in sorted(inventory)
    )


def _entry_input_inventory_from_observation(
    entry: ModelRegressionEntry,
    observation: ValidationOwnerObservation,
    *,
    additional_patterns: Sequence[str] = (),
) -> tuple[dict[str, str], ...]:
    """Project one model's inputs from the already-frozen repository view."""

    return filter_resolved_input_manifest(
        observation.repository_input_manifest,
        tuple(
            dict.fromkeys(
                (
                    *entry.effective_input_patterns,
                    *(str(item) for item in additional_patterns if str(item).strip()),
                )
            )
        ),
    )


def input_inventory_fingerprint(
    inventory: Sequence[Mapping[str, str]],
) -> str:
    encoded = json.dumps(
        [dict(item) for item in inventory],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_fingerprints(paths: Sequence[str]) -> dict[str, str]:
    return {
        str(index): _file_sha256(Path(path))
        for index, path in enumerate(paths)
        if Path(path).is_file()
    }


def build_regression_model_instance(
    root: str | Path,
    entry: ModelRegressionEntry,
    inventory: Sequence[Mapping[str, str]],
) -> ModelInstanceRef:
    """Build the canonical model instance used by snapshots and receipts."""

    root_path = Path(root).resolve()
    runner_path = entry.runner[1] if len(entry.runner) >= 2 else ""
    if entry.purpose_closure is None:
        raise ModelRegressionManifestError(
            f"{entry.model_id}: canonical model instance requires purpose closure"
        )
    return build_model_instance_ref(
        root_path,
        logical_model_id=entry.model_id,
        model_kind=entry.model_kind,
        model_path=entry.model_path,
        runner_path=runner_path,
        purpose_closure_fingerprint=(
            entry.purpose_closure.closure_fingerprint
        ),
        input_paths=tuple(item["path"] for item in inventory),
    )


def model_instance_fingerprint(
    root: str | Path,
    entry: ModelRegressionEntry,
    inventory: Sequence[Mapping[str, str]],
) -> str:
    """Compatibility-free projection of the canonical instance fingerprint."""

    return build_regression_model_instance(root, entry, inventory).fingerprint


def _run_entry(
    root: Path,
    entry: ModelRegressionEntry,
    output_dir: Path,
    *,
    timeout_override: float | None,
    cancel_event: threading.Event,
    progress: ProgressCallback | None,
    input_inventory: Sequence[Mapping[str, str]] | None = None,
    require_executed_case_ids: bool = False,
    selected_owner_ids: Sequence[str] = (),
) -> ModelRunResult:
    started = time.monotonic()
    if input_inventory is None:
        input_inventory = resolve_entry_input_inventory(root, entry)
    inventory_fingerprint = input_inventory_fingerprint(input_inventory)
    instance = build_regression_model_instance(
        root,
        entry,
        input_inventory,
    )
    instance_fingerprint = instance.fingerprint
    artifact_dir = _safe_artifact_dir(output_dir, entry.model_id)
    command = entry.command(root=root)
    timeout = timeout_override if timeout_override is not None else entry.timeout_seconds
    resource_policy_fingerprint = fingerprint_value(
        {
            "schema": "flowguard.model_resource_policy.v1",
            "timeout_seconds": float(timeout),
        }
    )
    if progress:
        progress({"event": "started", "model_id": entry.model_id, "timeout_seconds": timeout})
    env = dict(os.environ)
    # The parent validation pass may use a private ``GIT_INDEX_FILE`` so the
    # tracked-source view is frozen and isolated from the live checkout.  Do
    # not propagate that path into a model producer: several legitimate model
    # cases create temporary Git repositories, and Git would then overwrite
    # the parent's index with the temporary repository's empty index.  The
    # producer must use its own repository-local Git context; the parent keeps
    # the isolated index for its read-only observation/freshness checks.
    env.pop("GIT_INDEX_FILE", None)
    existing_pythonpath = env.get("PYTHONPATH", "")
    source_pythonpath = str(root)
    if existing_pythonpath:
        source_pythonpath = source_pythonpath + os.pathsep + existing_pythonpath
    env.update(
        {
            "FLOWGUARD_OUTPUT_DIR": str(artifact_dir),
            # Native producers may enrich their rows from the one checked-in
            # exact source->native mapping registry.  The project root is an
            # explicit input identity; no producer is allowed to discover a
            # sibling checkout or infer a registry from its output path.
            "FLOWGUARD_PROJECT_ROOT": str(root),
            "FLOWGUARD_MODEL_ID": entry.model_id,
            # Native case producers bind every row to the exact observed
            # inputs and source/tool identities.  The values are passed as
            # environment facts so the owner script cannot silently fall
            # back to a guessed or parent-level fingerprint.
            "FLOWGUARD_INPUT_FINGERPRINT": inventory_fingerprint,
            "FLOWGUARD_MODEL_FINGERPRINT": entry.purpose_closure.model_sha256,
            "FLOWGUARD_CODE_FINGERPRINT": fingerprint_payload(
                {"model": entry.purpose_closure.model_sha256, "inputs": inventory_fingerprint}
            ),
            "FLOWGUARD_TEST_FINGERPRINT": entry.purpose_closure.runner_sha256,
            "FLOWGUARD_TOOLCHAIN_FINGERPRINT": fingerprint_payload(
                {"python": sys.version, "executable": sys.executable}
            ),
            "FLOWGUARD_ENVIRONMENT_FINGERPRINT": fingerprint_payload(
                {"platform": sys.platform, "cwd": str(root)}
            ),
            # Aggregate model runners use this explicit projection to avoid
            # relaunching a child owner already claimed by the outer plan.
            # It is deliberately comma-separated, matching
            # validation_ownership.selected_owner_ids().
            "FLOWGUARD_SELECTED_OWNER_IDS": ",".join(
                sorted({str(item).strip() for item in selected_owner_ids if str(item).strip()})
            ),
            # Model runners validate the selected repository snapshot, not an
            # unrelated editable/wheel installation that happens to be active
            # in the launching Python environment.
            "PYTHONPATH": source_pythonpath,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            # Native model execution must not create bytecode inside the
            # authoritative .flowguard tree.  Keep an explicit external cache
            # prefix (normally supplied by the launcher) so imports remain
            # fast without creating __pycache__ entries in the project layout.
            "PYTHONPYCACHEPREFIX": env.get(
                "PYTHONPYCACHEPREFIX",
                str(root / "work" / "pycache" / "flowguard-model-runs"),
            ),
        }
    )
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    status = VALIDATION_STATUS_INTERNAL_ERROR
    finding_codes: tuple[str, ...] = ("model.internal_error",)
    message = "model runner did not reach a terminal state"
    supervised = None
    executed_case_ids: tuple[str, ...] = ()
    native_case_results: tuple[NativeModelCaseResult, ...] = ()
    native_case_result_artifact_path = ""
    native_case_result_artifact_fingerprint = ""
    native_case_verification: NativeCaseVerification | None = None
    native_case_error: str = ""
    try:
        supervised = run_supervised(
            command,
            cwd=root,
            environment=env,
            timeout_seconds=timeout,
            cancel_event=cancel_event,
        )
        stdout = supervised.stdout
        stderr = supervised.stderr
        try:
            executed_case_ids = parse_executed_case_ids(
                stdout,
                require_marker=require_executed_case_ids,
            )
        except ModelRegressionEvidenceError as exc:
            # A malformed or missing explicit projection is an execution
            # failure under the strict gate.  We retain the terminal output
            # for diagnosis but never manufacture a case list.
            executed_case_ids = ()
            status = VALIDATION_STATUS_BLOCKED
            finding_codes = ("model.executed_case_ids_invalid",)
            message = str(exc)
        exit_code = supervised.exit_code
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_terminal_artifact(
            artifact_dir / "supervisor-terminal.json",
            supervised,
        )
        native_result_candidate = artifact_dir / NATIVE_CASE_RESULT_ARTIFACT_NAME
        if native_result_candidate.exists() or require_executed_case_ids:
            try:
                (
                    native_case_results,
                    native_result_path,
                    native_case_result_artifact_fingerprint,
                    native_case_verification,
                ) = _load_native_case_result_artifact(
                    native_result_candidate,
                    owner_id=f"model:{entry.model_id}",
                    marker_case_ids=executed_case_ids,
                )
                native_case_result_artifact_path = str(native_result_path)
                if not native_case_verification.ok:
                    native_case_error = "; ".join(
                        native_case_verification.findings
                    ) or "native result rows failed verification"
            except ModelRegressionEvidenceError as exc:
                native_case_error = str(exc)
                native_case_verification = NativeCaseVerification(
                    ok=False,
                    findings=(native_case_error,),
                )
                if native_result_candidate.is_file() and not native_result_candidate.is_symlink():
                    native_case_result_artifact_path = str(
                        native_result_candidate.resolve()
                    )
                    try:
                        native_case_result_artifact_fingerprint = _file_sha256(
                            native_result_candidate
                        )
                    except OSError:
                        native_case_result_artifact_fingerprint = ""
        if not supervised.cleanup_confirmed:
            status = VALIDATION_STATUS_INTERNAL_ERROR
            finding_codes = ("model.cleanup_unconfirmed",)
            message = "runner process-tree cleanup could not be confirmed"
        elif supervised.cancelled or supervised.interrupted:
            status = VALIDATION_STATUS_CANCELLED
            finding_codes = ("model.cancelled",)
            message = "cancelled after confirmed process-tree cleanup"
        elif supervised.timed_out:
            status = VALIDATION_STATUS_TIMEOUT
            finding_codes = ("model.timeout",)
            message = f"runner exceeded {timeout:g} seconds and its process tree was terminated"
        elif status == VALIDATION_STATUS_BLOCKED:
            # Keep the explicit case-evidence failure above; a zero process
            # exit cannot override a missing native projection.
            pass
        elif exit_code == 0:
            status = VALIDATION_STATUS_PASS
            finding_codes = ()
            message = "runner and its contained process tree completed successfully"
        else:
            status = VALIDATION_STATUS_FAIL
            finding_codes = ("model.nonzero_exit",)
            message = f"runner exited with code {exit_code}"
        if native_case_error:
            native_code = (
                "model.native_case_results_missing"
                if "missing" in native_case_error.lower()
                else "model.native_case_results_invalid"
            )
            finding_codes = tuple(dict.fromkeys((*finding_codes, native_code)))
            if require_executed_case_ids or status == VALIDATION_STATUS_PASS:
                status = VALIDATION_STATUS_BLOCKED
            message = (
                f"{message}; native case result evidence is not current: "
                f"{native_case_error}"
            )
    except (OSError, ValueError) as exc:
        status = VALIDATION_STATUS_INTERNAL_ERROR
        finding_codes = ("model.launch_error",)
        message = str(exc)
        stderr = repr(exc)
    # The orchestrator owns its stdout/stderr/receipt directory. A child may
    # legitimately replace its isolated FLOWGUARD_OUTPUT_DIR while producing
    # artifacts, so restore the parent-owned directory before retaining logs.
    artifact_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_tail_chars = 0 if status == VALIDATION_STATUS_PASS else 4000
    stdout_descriptor = store_text_object(
        output_dir,
        stdout,
        tail_chars=diagnostic_tail_chars,
    )
    stderr_descriptor = store_text_object(
        output_dir,
        stderr,
        tail_chars=diagnostic_tail_chars,
    )
    stdout_path = (output_dir / str(stdout_descriptor["object_path"])).resolve()
    stderr_path = (output_dir / str(stderr_descriptor["object_path"])).resolve()
    expected_paths = tuple(str((artifact_dir / item).resolve()) for item in entry.expected_artifacts)
    missing = tuple(path for path in expected_paths if not Path(path).exists())
    if status == VALIDATION_STATUS_PASS and missing:
        status = VALIDATION_STATUS_FAIL
        finding_codes = ("model.expected_artifact_missing",)
        message = "missing expected artifacts: " + ", ".join(missing)
    result_artifact_paths = list(expected_paths)
    if native_case_result_artifact_path:
        native_path = str(Path(native_case_result_artifact_path).resolve())
        if native_path not in result_artifact_paths:
            result_artifact_paths.append(native_path)
        for native_row in native_case_results:
            try:
                raw_path = _resolve_native_raw_artifact(
                    Path(native_path),
                    native_row.raw_artifact_path,
                )
            except (OSError, ValueError):
                continue
            if raw_path.is_file() and not raw_path.is_symlink():
                raw_text = str(raw_path)
                if raw_text not in result_artifact_paths:
                    result_artifact_paths.append(raw_text)
    result_artifact_paths_tuple = tuple(result_artifact_paths)
    elapsed_seconds = round(time.monotonic() - started, 3)
    result = ModelRunResult(
        model_id=entry.model_id,
        status=status,
        exit_code=exit_code,
        seconds=elapsed_seconds,
        command=command,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        receipt_path="",
        artifact_paths=result_artifact_paths_tuple,
        finding_codes=finding_codes,
        message=message,
        model_instance_id=entry.purpose_closure.model_instance_id if entry.purpose_closure else "",
        model_kind=instance.model_kind,
        model_instance_fingerprint=instance_fingerprint,
        input_inventory_fingerprint=inventory_fingerprint,
        input_inventory=input_inventory,
        artifact_fingerprints=_artifact_fingerprints(result_artifact_paths_tuple),
        purpose_closure_fingerprint=(entry.purpose_closure.closure_fingerprint if entry.purpose_closure else ""),
        purpose_claim_boundary=entry.purpose_closure.claim_boundary if entry.purpose_closure else "",
        stdout=stdout_descriptor,
        stderr=stderr_descriptor,
        executed_case_ids=executed_case_ids,
        native_case_results=native_case_results,
        native_case_result_artifact_path=native_case_result_artifact_path,
        native_case_result_artifact_fingerprint=(
            native_case_result_artifact_fingerprint
        ),
        native_case_verification=native_case_verification,
        supervision=supervised,
        resource_policy_fingerprint=resource_policy_fingerprint,
    )
    if progress:
        progress({"event": "finished", "model_id": entry.model_id, "status": status, "seconds": elapsed_seconds})
    return result


def _tracked_paths(root: Path) -> tuple[Path, ...]:
    """Return the repository's tracked files for the mutation guard.

    The mutation guard only needs to detect edits to governed source files.
    Enumerating ``--others`` here made every model run walk the entire
    untracked evidence/output tree (which can contain thousands of receipts),
    so a run could spend minutes in Git before executing its first model.  The
    run itself already owns its output directory and receipt files; those are
    not source mutations.  Keep the boundary to the Git index and let the
    status probe below inspect only tracked paths.
    """
    git = shutil.which("git")
    if not git:
        return ()
    try:
        completed = subprocess.run(
            [git, "ls-files", "-z", "--cached"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return ()
    if completed.returncode != 0:
        return ()
    output_only_prefixes = (
        ".flowguard/models/authority/snapshots/",
        ".flowguard/models/authority/revisions/",
        ".flowguard/models/authority/activations/",
        ".flowguard/models/authority/rollbacks/",
        ".flowguard/models/authority/bootstraps/",
    )
    paths: list[Path] = []
    for item in completed.stdout.split(b"\0"):
        if not item:
            continue
        relative = item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        # Historical/current authority artifacts are immutable evidence outputs
        # owned by the later model-revision activation step.  They are not
        # governed model source and can be tens of megabytes in one checkout;
        # excluding them keeps the mutation boundary focused on source inputs
        # while project.toml and the live model/verification files remain in it.
        if relative.startswith(output_only_prefixes):
            continue
        paths.append(root / relative)
    return tuple(paths)


def _snapshot(paths: Sequence[Path]) -> dict[str, str]:
    def fingerprint(path: Path) -> tuple[str, str]:
        # ``Path.resolve`` performs a filesystem realpath walk for every
        # tracked path.  A full model plan can contain thousands of tracked
        # files and Windows may spend minutes resolving reparse-heavy paths.
        # The caller already constructed each path from one absolute project
        # root, so a lexical absolute key is sufficient for the mutation
        # comparison and does not weaken the source-input fingerprints.
        key = os.path.normcase(os.path.abspath(os.fspath(path)))
        try:
            stat = os.stat(path, follow_symlinks=False)
        except OSError:
            return key, "<missing>"
        if not stat_module.S_ISREG(stat.st_mode):
            return key, "<non-file>"
        # Owner input manifests separately carry exact SHA-256 identities for
        # every governed model/runner input.  The repository-wide mutation
        # guard only needs a bounded change detector for the frozen tracked
        # path set; filesystem metadata avoids opening thousands of historical
        # documentation/evidence files (which is unusually slow on Windows)
        # while still catching additions, removals, rewrites, and mode changes.
        return key, (
            f"size={stat.st_size};mtime_ns={stat.st_mtime_ns};"
            f"ctime_ns={getattr(stat, 'st_ctime_ns', 0)};mode={stat.st_mode}"
        )

    ordered = tuple(paths)
    if len(ordered) < 16:
        pairs = tuple(fingerprint(path) for path in ordered)
    else:
        with ThreadPoolExecutor(
            max_workers=min(8, len(ordered)),
            thread_name_prefix="flowguard-source-snapshot",
        ) as executor:
            pairs = tuple(executor.map(fingerprint, ordered))
    return dict(pairs)


def _relative_snapshot(snapshot: Mapping[str, str], root: Path) -> dict[str, str]:
    """Normalize a tracked-path snapshot to the same keys as owner manifests.

    The functional owner manifest uses repository-relative POSIX paths while
    the bounded tracked-file guard naturally snapshots absolute filesystem
    keys.  Joining the two projections under one key space prevents a changed
    tracked file from being reported twice and keeps the mutation report
    stable for callers and tests.
    """

    root_key = os.path.normcase(os.path.abspath(os.fspath(root)))
    result: dict[str, str] = {}
    for raw_path, fingerprint in snapshot.items():
        try:
            relative = os.path.relpath(raw_path, root_key).replace("\\", "/")
        except (OSError, ValueError):
            relative = str(raw_path).replace("\\", "/")
        result[relative] = str(fingerprint)
    return result


def _git_worktree_snapshot(root: Path, paths: Sequence[Path]) -> dict[str, str] | None:
    """Return a bounded metadata snapshot of the already-frozen tracked paths.

    Earlier versions asked Git for a worktree status before every model and
    after the last model.  On this repository that status walk can block on a
    large, concurrently changing worktree even when untracked paths are
    explicitly disabled.  ``paths`` was obtained from the index at the
    execution boundary, so hashing those exact paths directly preserves the
    mutation-guard claim without consulting the live worktree again.  Exact
    SHA-256 identities remain in the owner input manifests; this global guard
    deliberately uses metadata so it does not open thousands of slow files.
    """

    del root  # retained in the signature for callers and test seams
    return _snapshot(paths)


def _mutation_paths(before: Mapping[str, str], after: Mapping[str, str], root: Path) -> tuple[str, ...]:
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    values: list[str] = []
    for item in changed:
        try:
            values.append(Path(item).relative_to(root).as_posix())
        except ValueError:
            values.append(item)
    return tuple(values)


def _input_manifest_snapshot(
    input_manifest: Sequence[Mapping[str, str]],
) -> dict[str, str]:
    """Project one frozen functional input manifest for mutation checking.

    Model owners already freeze the exact functional source inventory during
    planning.  Re-enumerating every tracked checkout path for the mutation
    guard is both broader than the claim and extremely slow on Windows.  The
    manifest projection is exact for the selected model closure and excludes
    non-source projection tokens by construction.
    """

    result: dict[str, str] = {}
    for item in input_manifest:
        path = str(item.get("path", "")).replace("\\", "/")
        if not path or path.startswith("<projection:") or path.startswith("<external:"):
            continue
        result[path] = str(item.get("sha256", ""))
    return result


def _governed_owner_input_manifest(
    owner_currents: Sequence[object],
    *,
    base_manifest: Sequence[Mapping[str, str]] = (),
) -> tuple[Mapping[str, str], ...]:
    """Return the exact source projection from one completed owner observation.

    ``ValidationObservationFreshness.owner_currents`` is the post-run, bounded
    source observation already produced by the owner planner.  The mutation
    guard must compare against that projection rather than performing a second
    repository-wide scan.  Keep the helper deliberately duck-typed so this
    module does not create a validation-ownership import cycle; each current
    owns an ``input_manifest`` sequence with the same ``path``/``sha256``
    records used by the initial observation.
    """

    # Keep parent-only projections (for example the regression manifest
    # itself) from the initial observation.  Owner currents describe leaf
    # contracts, while the parent contract may contribute additional inputs
    # that are intentionally not repeated in every leaf current.
    records: list[Mapping[str, str]] = [
        dict(item) for item in base_manifest if isinstance(item, Mapping)
    ]
    for current in owner_currents:
        manifest = getattr(current, "input_manifest", ())
        if not isinstance(manifest, Sequence) or isinstance(manifest, (str, bytes)):
            continue
        for item in manifest:
            if isinstance(item, Mapping):
                records.append(dict(item))
    return tuple(records)


def _model_owner_contract(
    root: Path,
    manifest: ModelRegressionManifest,
    entry: ModelRegressionEntry,
) -> ValidationOwnerContract:
    return ValidationOwnerContract(
        owner_id=f"model:{entry.model_id}",
        command=entry.command(root=root),
        input_patterns=tuple(
            dict.fromkeys(
                (
                    *entry.effective_input_patterns,
                    *(
                        pattern
                        for pattern in manifest.shared_patterns_for(
                            entry.model_id
                        )
                        if pattern
                        != ".flowguard/models/regression-manifest.json"
                    ),
                )
            )
        ),
        obligation_ids=(f"model-regression:{entry.model_id}",),
        projected_inputs=(
            (
                f"model-regression-manifest:{entry.model_id}",
                manifest.owner_projection_fingerprint(entry),
            ),
        ),
    )


def _model_parent_owner_contract(
    manifest: ModelRegressionManifest,
    entries: Sequence[ModelRegressionEntry],
    *,
    claim_scope: str,
    tier: str,
) -> ValidationOwnerContract:
    """Return the exact composition contract for one model parent run.

    The tier and claim scope are projected into the native contract even when
    two selections happen to contain the same model ids.  A scoped execution
    therefore cannot be relabeled as a full parent by rewriting its wrapper.
    """

    selected_model_ids = tuple(entry.model_id for entry in entries)
    selection_fingerprint = fingerprint_value(
        {
            "manifest_sha256": functional_source_fingerprint(
                manifest.path.parent.parent.parent,
                ".flowguard/models/regression-manifest.json",
            ),
            "selected_model_ids": list(selected_model_ids),
            "claim_scope": claim_scope,
            "tier": tier,
        }
    )
    return ValidationOwnerContract(
        owner_id="model-regression-parent",
        command=(
            "flowguard-model-regression-parent",
            "--tier",
            tier,
            "--claim-scope",
            claim_scope,
        ),
        input_patterns=(
            ".flowguard/models/regression-manifest.json",
            "flowguard/model_regressions.py",
            "flowguard/evidence_receipts.py",
            "flowguard/validation_ownership.py",
        ),
        projected_inputs=(
            ("model-parent-selection", selection_fingerprint),
        ),
        obligation_ids=(
            f"model-regression-parent:{selection_fingerprint}",
        ),
        resource_keys=("model-regression-parent",),
    )


def _model_result_from_reused_child(
    entry: ModelRegressionEntry,
    child: ValidationChildResult,
    *,
    require_native_case_results: bool = False,
) -> ModelRunResult:
    raw = child.payload.get("model_result")
    if not isinstance(raw, Mapping):
        raise ValueError(f"model receipt proof is missing result: {entry.model_id}")
    native_results: tuple[NativeModelCaseResult, ...] = ()
    native_path = str(raw.get("native_case_result_artifact_path", ""))
    native_fingerprint = str(
        raw.get("native_case_result_artifact_fingerprint", "")
    )
    declared_native_fingerprint = native_fingerprint
    native_verification: NativeCaseVerification | None = None
    native_findings: list[str] = []
    raw_native_present = "native_case_results" in raw
    try:
        if raw_native_present:
            native_results = _coerce_native_case_results(
                raw.get("native_case_results"),
                context=f"model receipt proof {entry.model_id}",
            )
        # A normal local model-parent composition already verifies the
        # immutable owner receipt and its proof fingerprint. Re-opening and
        # hashing every absolute native-case-results artifact here adds a
        # second deep filesystem walk after the producer has published the
        # signed native projection; on a long-lived Windows evidence store
        # that turns ordinary reuse into minutes of redundant I/O. The strict
        # execution-evidence route still revalidates the artifact (and
        # receipts that omit the embedded projection still need to be read).
        # Keep the artifact identity/path in the reused result for audit and
        # release consumers, but do not make the local functional reuse path
        # re-open it.
        verify_native_artifact = require_native_case_results or not raw_native_present
        if native_path and verify_native_artifact:
            (
                loaded_rows,
                loaded_path,
                loaded_fingerprint,
                loaded_verification,
            ) = _load_native_case_result_artifact(
                native_path,
                owner_id=f"model:{entry.model_id}",
                marker_case_ids=_coerce_executed_case_ids(
                    raw.get("executed_case_ids", ()),
                    context=f"model receipt proof {entry.model_id}",
                ),
            )
            if native_results and not _native_result_rows_equal(
                native_results, loaded_rows
            ):
                native_findings.append("native_case_results_artifact_mismatch")
            if declared_native_fingerprint and declared_native_fingerprint != loaded_fingerprint:
                native_findings.append(
                    "native_case_result_artifact_fingerprint_mismatch"
                )
            native_results = loaded_rows
            native_path = str(loaded_path)
            native_fingerprint = (
                loaded_fingerprint if declared_native_fingerprint else ""
            )
            native_verification = loaded_verification
        elif not native_path and (native_results or require_native_case_results):
            native_findings.append("native_case_result_artifact_missing")
        if require_native_case_results and not native_results:
            native_findings.append("native_case_results_missing")
        if require_native_case_results and not declared_native_fingerprint:
            native_findings.append(
                "native_case_result_artifact_fingerprint_missing"
            )
        if require_native_case_results and not native_verification:
            native_findings.append("native_case_results_invalid")
        elif native_verification is not None and not native_verification.ok:
            native_findings.append("native_case_results_invalid")
    except ModelRegressionEvidenceError as exc:
        native_findings.append("native_case_results_invalid")
        native_verification = NativeCaseVerification(
            ok=False,
            findings=(str(exc),),
        )
    status = str(raw.get("status", ""))
    finding_codes = [str(item) for item in raw.get("finding_codes", ())]
    if native_findings:
        finding_codes.extend(native_findings)
        status = VALIDATION_STATUS_BLOCKED
    return ModelRunResult(
        model_id=entry.model_id,
        status=status,
        exit_code=raw.get("exit_code"),
        seconds=0.0,
        command=tuple(str(item) for item in raw.get("command", ())),
        stdout_path=str(raw.get("stdout_path", "")),
        stderr_path=str(raw.get("stderr_path", "")),
        receipt_path=child.receipt_id,
        artifact_paths=tuple(str(item) for item in raw.get("artifact_paths", ())),
        finding_codes=tuple(dict.fromkeys(finding_codes)),
        message=(
            "reused independently verified exact-current terminal receipt"
            if not native_findings
            else "reused receipt lacks current native case result evidence: "
            + ", ".join(dict.fromkeys(native_findings))
        ),
        model_instance_id=str(raw.get("model_instance_id", "")),
        model_kind=str(raw.get("model_kind", "")),
        model_instance_fingerprint=str(raw.get("model_instance_fingerprint", "")),
        input_inventory_fingerprint=str(raw.get("input_inventory_fingerprint", "")),
        input_inventory=tuple(
            dict(item) for item in raw.get("input_inventory", ())
            if isinstance(item, Mapping)
        ),
        artifact_fingerprints=dict(raw.get("artifact_fingerprints", {})),
        purpose_closure_fingerprint=str(raw.get("purpose_closure_fingerprint", "")),
        purpose_claim_boundary=str(raw.get("purpose_claim_boundary", "")),
        stdout=dict(raw.get("stdout", {})),
        stderr=dict(raw.get("stderr", {})),
        execution_disposition=OWNER_REUSE_CURRENT,
        producer_invocations=0,
        receipt_fingerprint=str(
            child.payload.get("owner_receipt_fingerprint", "")
        ),
        resource_policy_fingerprint=str(
            raw.get("resource_policy_fingerprint", "")
        ),
        executed_case_ids=_coerce_executed_case_ids(
            raw.get("executed_case_ids", ()),
            context=f"model receipt proof {entry.model_id}",
        ),
        native_case_results=native_results,
        native_case_result_artifact_path=native_path,
        native_case_result_artifact_fingerprint=native_fingerprint,
        native_case_verification=native_verification,
    )


def _demote_policy_incompatible_model_rows(
    plan_rows: Sequence[Any],
    reusable_receipts: Mapping[str, EvidenceReceipt],
    entries_by_owner: Mapping[str, ModelRegressionEntry],
    *,
    receipt_root: Path,
    timeout_override: float | None,
) -> tuple[Any, ...]:
    """Demote only leaves that cannot satisfy a newly tightened budget.

    Supervisor budgets are intentionally absent from the functional owner
    identity.  That lets a budget increase reuse a valid functional result.
    A budget decrease still has one local compatibility condition: a prior
    successful producer that took longer than the new cap could not have
    satisfied the current execution policy.  The condition is evaluated from
    the immutable producer payload and demotes only that owner row.  Missing
    or malformed duration evidence is treated as unknown for that leaf, never
    as a reason to rerun the whole manifest.
    """

    refreshed: list[Any] = []
    for row in plan_rows:
        if row.disposition != OWNER_REUSE_CURRENT:
            refreshed.append(row)
            continue
        entry = entries_by_owner.get(row.owner_id)
        receipt = reusable_receipts.get(row.owner_id)
        if entry is None or receipt is None:
            refreshed.append(
                replace(
                    row,
                    disposition=OWNER_EXECUTE,
                    reason="execution policy compatibility evidence is missing",
                    receipt_id="",
                    receipt_fingerprint="",
                )
            )
            continue
        budget = (
            float(timeout_override)
            if timeout_override is not None
            else float(entry.timeout_seconds)
        )
        reason = ""
        findings = row.findings
        try:
            child = child_from_owner_receipt(receipt, receipt_root)
            raw = child.payload.get("model_result")
            if not isinstance(raw, Mapping):
                reason = "execution policy duration evidence is missing"
            elif str(raw.get("status", "")) != VALIDATION_STATUS_PASS:
                reason = "prior model result is not a passing terminal result"
            else:
                observed = float(raw.get("seconds"))
                if not math.isfinite(observed) or observed < 0:
                    reason = "execution policy duration evidence is invalid"
                elif observed > budget:
                    reason = (
                        "resource_incompatible: current supervisor budget is below "
                        "prior observed duration"
                    )
                    findings = tuple(
                        dict.fromkeys((*row.findings, "resource_incompatible"))
                    )
        except (OSError, TypeError, ValueError, KeyError):
            reason = "execution policy duration evidence is unreadable"
        if reason:
            refreshed.append(
                replace(
                    row,
                    disposition=OWNER_EXECUTE,
                    reason=reason,
                    receipt_id="",
                    receipt_fingerprint="",
                    findings=findings,
                )
            )
        else:
            refreshed.append(row)
    return tuple(refreshed)


def _demote_model_identity_mismatches(
    plan_rows: Sequence[Any],
    reusable_receipts: Mapping[str, EvidenceReceipt],
    entries_by_owner: Mapping[str, ModelRegressionEntry],
    *,
    root_path: Path,
    manifest: ModelRegressionManifest,
    planning_observation: ValidationOwnerObservation,
    receipt_root: Path,
) -> tuple[Any, ...]:
    """Demote leaves whose producer identity predates the canonical inventory.

    The owner contract already makes declared shared selectors functional
    inputs.  A historical producer receipt can therefore be source-current at
    the generic owner layer while its nested model result still carries the
    old, entry-only inventory (the pre-shared-input projection).  Reusing that
    result would make the model parent and the live model snapshot disagree on
    the model-instance fingerprint.  Demote only that leaf so one bounded
    producer run repairs the projection; resource-policy changes remain
    intentionally outside this functional identity check.
    """

    refreshed: list[Any] = []
    for row in plan_rows:
        if row.disposition != OWNER_REUSE_CURRENT:
            refreshed.append(row)
            continue
        entry = entries_by_owner.get(row.owner_id)
        receipt = reusable_receipts.get(row.owner_id)
        reason = ""
        try:
            if entry is None or receipt is None or entry.purpose_closure is None:
                reason = "canonical model identity inputs are missing"
            else:
                child = child_from_owner_receipt(receipt, receipt_root)
                raw = child.payload.get("model_result")
                if not isinstance(raw, Mapping):
                    reason = "model result identity evidence is missing"
                else:
                    inventory = _entry_input_inventory_from_observation(
                        entry,
                        planning_observation,
                        additional_patterns=manifest.shared_patterns_for(
                            entry.model_id
                        ),
                    )
                    expected_inventory = input_inventory_fingerprint(inventory)
                    expected_instance = build_regression_model_instance(
                        root_path,
                        entry,
                        inventory,
                    )
                    expected_purpose = entry.purpose_closure.closure_fingerprint
                    if raw.get("input_inventory_fingerprint") != expected_inventory:
                        reason = "model result input inventory is not current"
                    elif raw.get("model_instance_fingerprint") != expected_instance.fingerprint:
                        reason = "model result instance fingerprint is not current"
                    elif raw.get("purpose_closure_fingerprint") != expected_purpose:
                        reason = "model result purpose closure is not current"
        except (OSError, TypeError, ValueError, KeyError):
            reason = "model result identity evidence is unreadable"
        if reason:
            refreshed.append(
                replace(
                    row,
                    disposition=OWNER_EXECUTE,
                    reason=reason,
                    receipt_id="",
                    receipt_fingerprint="",
                )
            )
        else:
            refreshed.append(row)
    return tuple(refreshed)


def _persist_model_owner_result(
    root: Path,
    receipt_root: Path,
    current: Any,
    result: ModelRunResult,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    started_at: str,
    source_freshness: ValidationObservationFreshness,
) -> ModelRunResult:
    child = ValidationChildResult(
        child_id=current.contract.owner_id,
        status=result.status,
        summary=result.message,
        receipt_id=Path(result.receipt_path).name,
        artifact_paths=(
            result.stdout_path,
            result.stderr_path,
            *(item for item in (result.receipt_path,) if item),
            *result.artifact_paths,
        ),
        claim_boundary=(
            result.purpose_claim_boundary
            or "One manifest-owned model runner and its exact declared inputs."
        ),
        payload={"model_result": result.to_dict()},
    )
    if result.status == VALIDATION_STATUS_PASS:
        if result.supervision is None:
            raise ValueError(
                f"passing model owner lacks supervised producer evidence: {result.model_id}"
            )
        publication = publish_supervised_validation_owner_result(
            current,
            result.supervision,
            root,
            receipt_root,
            all_contracts=all_contracts,
            child_id=child.child_id,
            evidence_context={"model_result": result.to_dict()},
            summary=child.summary,
            claim_boundary=child.claim_boundary,
            source_freshness=source_freshness,
        )
        if not publication.ok or publication.receipt is None:
            raise ValueError(
                f"passing model owner publication blocked: {publication.blocker}"
            )
        receipt = publication.receipt
    else:
        receipt = record_validation_owner_nonpass(
            current,
            child,
            root,
            receipt_root,
            all_contracts=all_contracts,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    path = evidence_receipt_path(
        receipt.receipt_id,
        root,
        output_directory=receipt_root,
    )
    return replace(
        result,
        receipt_path=str(path),
        execution_disposition=OWNER_EXECUTE,
        producer_invocations=1,
        receipt_fingerprint=receipt.fingerprint,
    )


def _execute_pending_models(
    *,
    root_path: Path,
    pending: Sequence[ModelRegressionEntry],
    jobs: int,
    timeout: float | None,
    output_path: Path,
    receipt_root: Path,
    currents: Mapping[str, Any],
    contracts: Sequence[ValidationOwnerContract],
    planning_observation: ValidationOwnerObservation,
    cancel: threading.Event,
    progress: ProgressCallback | None,
    input_inventories: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
    shared_patterns_by_model: Mapping[str, Sequence[str]] | None = None,
    require_executed_case_ids: bool = False,
) -> tuple[list[ModelRunResult], ValidationObservationFreshness]:
    """Preflight every model resource lease, then execute the frozen set."""

    results: list[ModelRunResult] = []
    selected_owner_projection = tuple(
        sorted(
            {
                str(contract.owner_id).strip()
                for contract in contracts
                if str(contract.owner_id).strip().startswith("model:")
            }
        )
    )
    lease_payloads: dict[str, dict[str, Any]] = {}
    with ExitStack() as leases:
        for entry in pending:
            owner_id = f"model:{entry.model_id}"
            current = currents[owner_id]
            lease_payloads[entry.model_id] = leases.enter_context(
                evidence_execution_lease(
                    receipt_root / "leases",
                    owner_id=owner_id,
                    resource_key=owner_id,
                    execution_key=current.owner_identity,
                    plan_id=f"model-owner-plan:{current.owner_identity}",
                )
            )

        if jobs > 1:
            from .shard_safety import prove_model_shard_safety

            for entry in pending:
                if not entry.shard_safety_proof:
                    continue
                proof_dir = _shard_safety_proof_dir(output_path, entry.model_id)
                proof = prove_model_shard_safety(
                    root_path,
                    entry,
                    output_dir=proof_dir,
                    timeout=timeout,
                    additional_patterns=(
                        (shared_patterns_by_model or {}).get(entry.model_id, ())
                    ),
                )
                if not proof["ok"]:
                    raise ValueError(
                        f"parallel execution proof failed for {entry.model_id}; "
                        f"see {proof_dir / 'result.json'}"
                    )

        if jobs == 1:
            completed: list[tuple[ModelRegressionEntry, str, ModelRunResult]] = []
            for entry in pending:
                owner_started_at = datetime.now(timezone.utc).isoformat()
                result = _run_entry(
                    root_path,
                    entry,
                    output_path,
                    timeout_override=timeout,
                    cancel_event=cancel,
                    progress=progress,
                    input_inventory=(input_inventories or {}).get(entry.model_id),
                    require_executed_case_ids=require_executed_case_ids,
                    # Each model-regression child is its own execution owner.
                    # Propagating the complete same-level selection into every
                    # process made aggregate owners (for example UI content
                    # visibility) mistake siblings for already-produced
                    # receipts and fail before their actual callback ran.
                    # Nested owner guards still receive the current owner as
                    # the outer claim; same-level receipts are reconciled by
                    # the parent composition below.
                    selected_owner_ids=(f"model:{entry.model_id}",),
                )
                completed.append((entry, owner_started_at, result))
                if cancel.is_set():
                    break
        else:
            completed = []
            with ThreadPoolExecutor(
                max_workers=jobs,
                thread_name_prefix="flowguard-model",
            ) as executor:
                futures = {
                    executor.submit(
                        _run_entry,
                        root_path,
                        entry,
                        output_path,
                        timeout_override=timeout,
                        cancel_event=cancel,
                        progress=progress,
                        input_inventory=(input_inventories or {}).get(entry.model_id),
                        require_executed_case_ids=require_executed_case_ids,
                        selected_owner_ids=(f"model:{entry.model_id}",),
                    ): (
                        entry,
                        datetime.now(timezone.utc).isoformat(),
                    )
                    for entry in pending
                }
                for future in as_completed(futures):
                    entry, owner_started_at = futures[future]
                    completed.append((entry, owner_started_at, future.result()))

        source_freshness = assert_validation_owner_observation_fresh(
            planning_observation,
            root_path,
            receipt_root,
        )
        fresh_currents = source_freshness.current_by_owner
        for entry, owner_started_at, result in completed:
            if "model.cleanup_unconfirmed" in result.finding_codes:
                lease = lease_payloads[entry.model_id]
                lease["_preserve_residual"] = True
                terminal_path = (
                    _safe_artifact_dir(output_path, entry.model_id)
                    / "supervisor-terminal.json"
                )
                if terminal_path.is_file():
                    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
                    lease["incident_episode_token"] = str(
                        terminal.get("episode_token", lease["lease_token"])
                    )
                continue
            results.append(
                _persist_model_owner_result(
                    root_path,
                    receipt_root,
                    fresh_currents[f"model:{entry.model_id}"],
                    result,
                    all_contracts=contracts,
                    started_at=owner_started_at,
                    source_freshness=source_freshness,
                )
            )
    return results, source_freshness


def _write_model_parent_receipt(
    root: Path,
    manifest: ModelRegressionManifest,
    receipt_root: Path,
    report: ModelRegressionReport,
    *,
    planning_observation: ValidationOwnerObservation,
    source_freshness: ValidationObservationFreshness,
) -> tuple[
    str,
    str,
    ValidationOwnerObservation,
    ValidationObservationFreshness,
    float,
]:
    """Compose exact child-owner receipts into one scoped/full model parent."""

    composition_started_at = time.perf_counter()

    children: list[dict[str, str]] = []
    loaded_children: dict[str, EvidenceReceipt] = {}
    for result in report.results:
        if not result.receipt_path or not result.receipt_fingerprint:
            continue
        path = (
            evidence_receipt_path(
                result.receipt_path,
                root,
                output_directory=receipt_root,
            )
            if result.receipt_path.startswith("receipt:")
            else Path(result.receipt_path)
        )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"model parent child receipt is unreadable: {result.model_id}"
            ) from exc
        child_receipt = EvidenceReceipt.from_dict(payload)
        if child_receipt.fingerprint != result.receipt_fingerprint:
            raise ValueError(
                f"model parent child fingerprint changed: {result.model_id}"
            )
        if child_receipt.subject_id != f"validation-owner:model:{result.model_id}":
            raise ValueError(
                f"model parent child subject changed: {result.model_id}"
            )
        loaded_children[result.model_id] = child_receipt
        children.append(
            {
                "model_id": result.model_id,
                "receipt_id": child_receipt.receipt_id,
                "receipt_fingerprint": result.receipt_fingerprint,
            }
        )
    children.sort(key=lambda row: row["model_id"])
    execution_receipt_id = ""
    execution_receipt_fingerprint = ""
    composition_observation = planning_observation
    freshness = ValidationObservationFreshness.not_run(planning_observation)
    if report.ok:
        entries_by_id = {entry.model_id: entry for entry in manifest.entries}
        try:
            selected_entries = tuple(
                entries_by_id[model_id]
                for model_id in report.selected_model_ids
            )
        except KeyError as exc:
            raise ValueError(
                f"passing model parent selects an unknown model: {exc.args[0]}"
            ) from exc
        child_contracts = tuple(
            _model_owner_contract(root, manifest, entry)
            for entry in selected_entries
        )
        if child_contracts != planning_observation.contracts:
            raise ValueError(
                "model parent selection differs from the frozen owner observation"
            )
        composition_observation = refresh_validation_owner_observation_receipts(
            planning_observation,
            root,
            receipt_root,
            tuple(loaded_children[entry.model_id] for entry in selected_entries),
        )
        rows = composition_observation.rows
        child_currents = composition_observation.current_by_owner
        reusable = composition_observation.receipt_by_owner
        observed_verifications = composition_observation.verification_by_owner
        noncurrent = tuple(
            row.owner_id
            for row in rows
            if row.disposition != OWNER_REUSE_CURRENT
        )
        if noncurrent:
            raise ValueError(
                "passing model parent child evidence is not exact-current: "
                + ", ".join(noncurrent)
        )
        exact_children: list[EvidenceReceipt] = []
        child_verifications: list[ReceiptVerificationResult] = []
        for entry in selected_entries:
            owner_id = f"model:{entry.model_id}"
            child = reusable[owner_id]
            loaded = loaded_children.get(entry.model_id)
            if loaded is None or loaded.fingerprint != child.fingerprint:
                raise ValueError(
                    f"passing model parent child changed: {entry.model_id}"
                )
            verification = observed_verifications[owner_id]
            if not verification.ok:
                raise ValueError(
                    f"passing model parent child is not current: {entry.model_id}"
                )
            exact_children.append(child)
            child_verifications.append(verification)

        parent_contract = _model_parent_owner_contract(
            manifest,
            selected_entries,
            claim_scope=report.parent_claim_scope,
            tier=report.tier,
        )
        parent_current = build_owner_current_from_observation(
            root,
            parent_contract,
            all_contracts=(parent_contract,),
            observation=composition_observation,
        )
        freshness = assert_validation_owner_observation_receipts_fresh(
            planning_observation,
            composition_observation,
            source_freshness,
            root,
            receipt_root,
            additional_receipt_subject_ids=(
                "validation-owner:model-regression-parent",
            ),
        )

        if (
            report.parent_claim_scope == "full"
            and report.tier == "full"
            and not report.skipped_model_ids
        ):
            manifest_fingerprint = functional_source_fingerprint(
                manifest.path.parent.parent.parent,
                ".flowguard/models/regression-manifest.json",
            )
            parent_dir = receipt_root / "model-parents"
            report_child_identities = {
                (
                    model_id,
                    receipt.receipt_id,
                    receipt.fingerprint,
                )
                for model_id, receipt in loaded_children.items()
            }
            matching_current_wrappers: list[
                tuple[Path, Mapping[str, Any]]
            ] = []
            try:
                current_parent_path = _current_model_parent_artifact_path(
                    parent_dir
                )
            except ModelRegressionParentNotCurrentError:
                # First composition has no head yet.  Never search the
                # append-only parent store for a substitute.
                current_parent_path = None
            if current_parent_path is not None:
                (
                    candidate_payload,
                    candidate_selected,
                    candidate_skipped,
                    _candidate_children,
                ) = _read_model_parent_artifact(current_parent_path)
                if (
                    candidate_payload["claim_scope"] == "full"
                    and candidate_payload["tier"] == "full"
                    and candidate_payload["status"] == RECEIPT_STATUS_PASS
                    and candidate_payload["manifest_sha256"]
                    == manifest_fingerprint
                    and candidate_selected
                    == tuple(report.selected_model_ids)
                    and not candidate_skipped
                    and {
                        (
                            row["model_id"],
                            row["receipt_id"],
                            row["receipt_fingerprint"],
                        )
                        for row in _candidate_children
                    }
                    == report_child_identities
                ):
                    matching_current_wrappers.append(
                        (current_parent_path, candidate_payload)
                    )
            if matching_current_wrappers:
                verified_wrappers: list[tuple[Path, Mapping[str, Any]]] = []
                for candidate_path, candidate_payload in matching_current_wrappers:
                    try:
                        execution = load_evidence_receipt(
                            str(candidate_payload["execution_receipt_id"]),
                            root,
                            output_directory=receipt_root,
                        )
                        _assert_owner_receipt_integrity(execution)
                    except (OSError, ValueError) as exc:
                        raise ValueError(
                            "matching model parent execution receipt is invalid: "
                            f"{candidate_path.name}: {exc}"
                        ) from exc
                    if execution.fingerprint != str(
                        candidate_payload["execution_receipt_fingerprint"]
                    ):
                        raise ValueError(
                            "matching model parent execution fingerprint changed: "
                            + candidate_path.name
                        )
                    context = build_child_bound_owner_receipt_context(
                        parent_current,
                        execution,
                        root,
                        receipt_root,
                        child_receipts=tuple(exact_children),
                        child_verification_results=tuple(child_verifications),
                    )
                    result = verify_evidence_receipt(execution, context)
                    if result.ok:
                        verified_wrappers.append(
                            (candidate_path, candidate_payload)
                        )
                    elif result.status != VERIFICATION_STATUS_STALE:
                        raise ValueError(
                            "matching model parent execution is invalid: "
                            + ", ".join(item.code for item in result.findings)
                        )
                if len(verified_wrappers) > 1:
                    raise ValueError(
                        "ambiguous exact-current full model parent artifacts: "
                        + ", ".join(path.name for path, _payload in verified_wrappers)
                    )
                if verified_wrappers:
                    current_path, current_payload = verified_wrappers[0]
                    return (
                        str(current_path),
                        str(current_payload["parent_receipt_fingerprint"]),
                        composition_observation,
                        freshness,
                        max(0.0, time.perf_counter() - composition_started_at),
                    )

        parent_execution, parent_verification = (
            save_child_bound_owner_receipt_from_observation(
            parent_current,
            tuple(f"model:{entry.model_id}" for entry in selected_entries),
            root,
            receipt_root,
            observation=composition_observation,
            freshness=freshness,
            started_at=datetime.fromtimestamp(
                report.started_at_epoch,
                tz=timezone.utc,
            ).isoformat(),
            finished_at=datetime.fromtimestamp(
                report.finished_at_epoch,
                tz=timezone.utc,
            ).isoformat(),
            evidence_context={
                "manifest_sha256": functional_source_fingerprint(
                    manifest.path.parent.parent.parent,
                    ".flowguard/models/regression-manifest.json",
                ),
                "selected_model_ids": list(report.selected_model_ids),
                "skipped_model_ids": list(report.skipped_model_ids),
                "claim_scope": report.parent_claim_scope,
                "tier": report.tier,
                "status": report.status,
            },
            claim_boundary=(
                "One exact model-regression parent composition over the named "
                "tier, selection, and canonical child receipts."
            ),
        ))
        if not parent_verification.ok:
            raise ValueError(
                "saved model parent execution receipt is not exact-current"
            )
        execution_receipt_id = parent_execution.receipt_id
        execution_receipt_fingerprint = parent_execution.fingerprint

    payload: dict[str, Any] = {
        "artifact_type": MODEL_REGRESSION_PARENT_ARTIFACT_TYPE,
        "schema_version": MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA,
        "claim_scope": report.parent_claim_scope,
        "tier": report.tier,
        "status": report.status,
        "manifest_sha256": functional_source_fingerprint(
            manifest.path.parent.parent.parent,
            ".flowguard/models/regression-manifest.json",
        ),
        "selected_model_ids": list(report.selected_model_ids),
        "skipped_model_ids": list(report.skipped_model_ids),
        "children": children,
        "execution_receipt_id": execution_receipt_id,
        "execution_receipt_fingerprint": execution_receipt_fingerprint,
        "claim_boundary": (
            "Full model-regression confidence over the exact current manifest."
            if report.parent_claim_scope == "full"
            else (
                "Scoped model-regression evidence only; this parent cannot "
                "support release or full-model confidence."
            )
        ),
    }
    identity = fingerprint_value(payload)
    payload["parent_receipt_fingerprint"] = identity
    parent_dir = receipt_root / "model-parents"
    parent_dir.mkdir(parents=True, exist_ok=True)
    path = parent_dir / (identity.split(":", 1)[1] + ".json")
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("content-addressed model parent receipt collision")
    if not path.exists():
        path.write_bytes(encoded)
    if (
        len(children) != len(report.selected_model_ids)
        or tuple(row["model_id"] for row in children)
        != tuple(sorted(report.selected_model_ids))
    ):
        if report.ok:
            raise ValueError("passing model parent does not compose every selected owner")
    return (
        str(path),
        identity,
        composition_observation,
        freshness,
        max(0.0, time.perf_counter() - composition_started_at),
    )


def _reject_duplicate_model_parent_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelRegressionEvidenceError(
                f"duplicate model parent JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite_model_parent_number(value: str) -> Any:
    raise ModelRegressionEvidenceError(
        f"non-finite model parent JSON number: {value}"
    )


def _model_parent_string_array(
    value: Any,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ModelRegressionEvidenceError(
            f"model parent {field_name} must be an array of non-empty strings"
        )
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ModelRegressionEvidenceError(
            f"model parent {field_name} must not contain duplicates"
        )
    return result


def _model_parent_children(
    value: Any,
) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ModelRegressionEvidenceError(
            "model parent children must be an array"
        )
    rows: list[Mapping[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ModelRegressionEvidenceError(
                f"model parent child {index} must be an object"
            )
        if set(item) != _MODEL_REGRESSION_PARENT_CHILD_FIELDS:
            raise ModelRegressionEvidenceError(
                "model parent child fields do not match the current schema"
            )
        if any(
            not isinstance(item[name], str) or not item[name]
            for name in _MODEL_REGRESSION_PARENT_CHILD_FIELDS
        ):
            raise ModelRegressionEvidenceError(
                "model parent child fields must be non-empty strings"
            )
        rows.append(
            {name: item[name] for name in _MODEL_REGRESSION_PARENT_CHILD_FIELDS}
        )
    model_ids = tuple(row["model_id"] for row in rows)
    if len(model_ids) != len(set(model_ids)):
        raise ModelRegressionEvidenceError(
            "model parent children must identify unique models"
        )
    return tuple(rows)


def _current_model_parent_artifact_path(parent_dir: Path) -> Path:
    """Resolve the one current parent artifact named by the typed head.

    The parent store is append-only evidence.  It is intentionally not a
    discovery surface: walking every historical JSON file and then trying to
    decide which one is current creates both repeated observations and an
    ambiguity loop after a source change.  The composer writes this small
    mutable head only after the content-addressed parent artifact is complete;
    consumers follow that exact path and validate the artifact itself.
    """

    head_path = parent_dir / "CURRENT.json"
    if head_path.is_symlink() or not head_path.is_file():
        raise ModelRegressionParentNotCurrentError(
            f"current model parent head is missing: {head_path}"
        )
    try:
        payload = json.loads(
            head_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_model_parent_keys,
            parse_constant=_reject_nonfinite_model_parent_number,
        )
    except (OSError, json.JSONDecodeError, ModelRegressionEvidenceError) as exc:
        raise ModelRegressionEvidenceError(
            f"cannot load current model parent head: {head_path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ModelRegressionEvidenceError(
            f"current model parent head must be an object: {head_path}"
        )
    if set(payload) != _MODEL_REGRESSION_PARENT_CURRENT_FIELDS:
        missing = sorted(_MODEL_REGRESSION_PARENT_CURRENT_FIELDS - set(payload))
        unknown = sorted(set(payload) - _MODEL_REGRESSION_PARENT_CURRENT_FIELDS)
        raise ModelRegressionEvidenceError(
            "current model parent head fields do not match the current schema: "
            f"missing={missing}, unknown={unknown}"
        )
    if payload["schema_version"] != MODEL_REGRESSION_PARENT_CURRENT_SCHEMA:
        raise ModelRegressionEvidenceError(
            "current model parent head schema is not current"
        )
    if payload["artifact_type"] != MODEL_REGRESSION_PARENT_ARTIFACT_TYPE:
        raise ModelRegressionEvidenceError(
            "current model parent head has an unexpected artifact type"
        )
    fingerprint = payload["parent_receipt_fingerprint"]
    if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
        raise ModelRegressionEvidenceError(
            "current model parent head fingerprint is malformed"
        )
    digest = fingerprint.split(":", 1)[1]
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ModelRegressionEvidenceError(
            "current model parent head fingerprint is malformed"
        )
    expected_name = digest + ".json"
    artifact_path = parent_dir / expected_name
    try:
        artifact_path.relative_to(parent_dir)
    except ValueError as exc:
        raise ModelRegressionEvidenceError(
            "current model parent head escapes its receipt directory"
        ) from exc
    if artifact_path.is_symlink() or not artifact_path.is_file():
        raise ModelRegressionParentNotCurrentError(
            "current model parent artifact named by the head is missing: "
            + str(artifact_path)
        )
    return artifact_path


def _read_model_parent_artifact(
    path: Path,
) -> tuple[
    Mapping[str, Any],
    tuple[str, ...],
    tuple[str, ...],
    tuple[Mapping[str, str], ...],
]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_model_parent_keys,
            parse_constant=_reject_nonfinite_model_parent_number,
        )
    except (OSError, json.JSONDecodeError, ModelRegressionEvidenceError) as exc:
        raise ModelRegressionEvidenceError(
            f"cannot load model parent artifact {path.name}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ModelRegressionEvidenceError(
            f"model parent artifact must be an object: {path.name}"
        )
    if set(payload) != _MODEL_REGRESSION_PARENT_FIELDS:
        missing = sorted(_MODEL_REGRESSION_PARENT_FIELDS - set(payload))
        unknown = sorted(set(payload) - _MODEL_REGRESSION_PARENT_FIELDS)
        raise ModelRegressionEvidenceError(
            "model parent artifact fields do not match the current schema: "
            f"missing={missing}, unknown={unknown}"
        )
    for field_name in (
        "artifact_type",
        "schema_version",
        "claim_scope",
        "tier",
        "status",
        "manifest_sha256",
        "execution_receipt_id",
        "execution_receipt_fingerprint",
        "claim_boundary",
        "parent_receipt_fingerprint",
    ):
        if not isinstance(payload[field_name], str):
            raise ModelRegressionEvidenceError(
                f"model parent {field_name} must be a string"
            )
    if payload["artifact_type"] != MODEL_REGRESSION_PARENT_ARTIFACT_TYPE:
        raise ModelRegressionEvidenceError(
            f"unexpected artifact in model parent store: {path.name}"
        )
    if payload["schema_version"] != MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA:
        raise ModelRegressionEvidenceError(
            f"non-current model parent schema remains in store: {path.name}"
        )
    selected_ids = _model_parent_string_array(
        payload["selected_model_ids"],
        "selected_model_ids",
    )
    skipped_ids = _model_parent_string_array(
        payload["skipped_model_ids"],
        "skipped_model_ids",
    )
    children = _model_parent_children(payload["children"])
    declared_fingerprint = payload["parent_receipt_fingerprint"]
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key != "parent_receipt_fingerprint"
    }
    if fingerprint_value(identity_payload) != declared_fingerprint:
        raise ModelRegressionEvidenceError(
            f"model parent artifact fingerprint is stale: {path.name}"
        )
    if not declared_fingerprint.startswith("sha256:"):
        raise ModelRegressionEvidenceError(
            f"model parent artifact fingerprint is malformed: {path.name}"
        )
    expected_name = declared_fingerprint.split(":", 1)[1] + ".json"
    if path.name != expected_name:
        raise ModelRegressionEvidenceError(
            f"model parent artifact filename does not match identity: {path.name}"
        )
    return payload, selected_ids, skipped_ids, children


def _exact_model_result_identity(
    raw: Mapping[str, Any],
    field_name: str,
    expected: str,
    *,
    model_id: str,
) -> str:
    value = raw.get(field_name)
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or value != expected:
        raise ModelRegressionEvidenceError(
            f"model child result {field_name} is not current: {model_id}"
        )
    return value


def resolve_current_full_model_regression_parent(
    root: str | Path = ".",
    *,
    receipt_dir: str | Path | None = None,
) -> CurrentModelRegressionParentEvidence:
    """Resolve one unique, exact-current full model parent without executing.

    Historical parent artifacts are retained, but only the artifact named by
    the typed ``model-parents/CURRENT.json`` head is eligible.  That exact
    artifact must be a ``full/full/pass`` composition with zero skipped models
    and the complete current manifest selection.  The aggregate never
    substitutes for its leaves: each declared model receipt is verified once
    against its current contract and then supplied to the parent verification
    context as a real child.
    """

    root_path = Path(root).resolve()
    receipt_root = (
        Path(receipt_dir).resolve()
        if receipt_dir is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    manifest = ModelRegressionManifest.load(root_path)
    audit = audit_manifest(root_path, manifest)
    if not audit.ok:
        raise ModelRegressionEvidenceError(
            "current model-regression manifest is invalid: "
            + "; ".join(audit.errors)
        )
    entries = select_entries(manifest, tier="full")
    source_inventory_errors = audit_selected_model_source_inventories(
        root_path,
        (entry.model_id for entry in entries),
    )
    if source_inventory_errors:
        raise ModelRegressionEvidenceError(
            "current model semantic source inventory is not exact-current: "
            + "; ".join(source_inventory_errors)
        )
    selected_ids = tuple(entry.model_id for entry in entries)
    manifest_fingerprint = functional_source_fingerprint(
        root_path,
        ".flowguard/models/regression-manifest.json",
    )
    parent_dir = receipt_root / "model-parents"
    try:
        parent_path = _current_model_parent_artifact_path(parent_dir)
    except ModelRegressionParentNotCurrentError as exc:
        raise ModelRegressionParentNotCurrentError(
            "no exact-current full model parent artifact is named by the "
            "current head"
        ) from exc
    payload, declared_selected, skipped_ids, declared_children = (
        _read_model_parent_artifact(parent_path)
    )
    if (
        payload["claim_scope"] != "full"
        or payload["tier"] != "full"
        or payload["status"] != RECEIPT_STATUS_PASS
        or payload["manifest_sha256"] != manifest_fingerprint
        or declared_selected != selected_ids
        or skipped_ids
    ):
        raise ModelRegressionParentNotCurrentError(
            "current model parent head does not name an exact-current "
            "full/full/pass artifact for the current manifest"
        )
    candidate_model_ids = tuple(row["model_id"] for row in declared_children)
    if candidate_model_ids != tuple(sorted(selected_ids)):
        raise ModelRegressionEvidenceError(
            "model parent children do not cover the current full manifest exactly"
        )
    candidate_execution_id = payload["execution_receipt_id"]
    candidate_execution_fingerprint = payload["execution_receipt_fingerprint"]
    if not candidate_execution_id or not candidate_execution_fingerprint:
        raise ModelRegressionEvidenceError(
            "passing full model parent lacks its canonical execution receipt"
        )
    if any(
        row["receipt_id"] == candidate_execution_id
        or row["receipt_fingerprint"] == candidate_execution_fingerprint
        for row in declared_children
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt cannot claim itself as a child"
        )
    for row in declared_children:
        model_id = row["model_id"]
        try:
            candidate_receipt = load_evidence_receipt(
                row["receipt_id"],
                root_path,
                output_directory=receipt_root,
            )
            _assert_owner_receipt_integrity(candidate_receipt)
        except (OSError, ValueError) as exc:
            raise ModelRegressionEvidenceError(
                "model parent child receipt is missing or invalid: "
                f"{model_id}: {exc}"
            ) from exc
        if candidate_receipt.fingerprint != row["receipt_fingerprint"]:
            raise ModelRegressionEvidenceError(
                "model parent child fingerprint does not match the "
                f"canonical receipt: {model_id}"
            )
        if candidate_receipt.subject_id != f"validation-owner:model:{model_id}":
            raise ModelRegressionEvidenceError(
                "model parent child subject does not match its model: "
                + model_id
            )
    contracts = tuple(
        _model_owner_contract(root_path, manifest, entry) for entry in entries
    )
    # The immutable parent names the exact leaf IDs.  Observe those IDs once;
    # never rescan the append-only receipt store or retry the observation for a
    # historical candidate.
    try:
        planning_observation = observe_validation_owners(
            root_path,
            contracts,
            receipt_root=receipt_root,
            receipt_ids=tuple(sorted(row["receipt_id"] for row in declared_children)),
        )
    except (OSError, ValueError) as exc:
        raise ModelRegressionParentNotCurrentError(
            "current model parent child evidence is not exact-current"
        ) from exc
    noncurrent = tuple(
        f"{row.owner_id} ({row.reason})"
        for row in planning_observation.rows
        if row.disposition != OWNER_REUSE_CURRENT
    )
    if noncurrent:
        raise ModelRegressionParentNotCurrentError(
            "current model parent child evidence is not exact-current: "
            + ", ".join(noncurrent)
        )
    currents = planning_observation.current_by_owner
    reusable = planning_observation.receipt_by_owner

    # Leaf identity equality is necessary but not sufficient for parent
    # currentness.  Parent-only inputs (the manifest, aggregation code, receipt
    # verifier, or ownership rules) can change while every leaf remains
    # reusable.  Verify the one head-named parent execution against those
    # leaves.  A stale parent is retained as history; malformed or invalid
    # evidence still blocks instead of being renewed over.
    exact_children_for_parent: list[EvidenceReceipt] = []
    child_verifications_for_parent: list[ReceiptVerificationResult] = []
    for model_id in selected_ids:
        owner_id = f"model:{model_id}"
        receipt = reusable[owner_id]
        context = build_owner_receipt_context(
            currents[owner_id],
            receipt,
            receipt_root,
        )
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ModelRegressionEvidenceError(
                f"model child failed independent current verification: {model_id}: "
                + ", ".join(item.code for item in verification.findings)
            )
        exact_children_for_parent.append(receipt)
        child_verifications_for_parent.append(verification)

    parent_contract_for_filter = _model_parent_owner_contract(
        manifest,
        entries,
        claim_scope="full",
        tier="full",
    )
    parent_current_for_filter = build_owner_current(
        root_path,
        parent_contract_for_filter,
        all_contracts=(parent_contract_for_filter,),
    )
    expected_child_identities_for_parent = {
        (item.receipt_id, item.fingerprint)
        for item in exact_children_for_parent
    }
    candidate_execution_id = payload["execution_receipt_id"]
    candidate_execution_fingerprint = payload["execution_receipt_fingerprint"]
    try:
        candidate_execution = load_evidence_receipt(
            candidate_execution_id,
            root_path,
            output_directory=receipt_root,
        )
        _assert_owner_receipt_integrity(candidate_execution)
    except (OSError, ValueError) as exc:
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is unavailable or invalid: "
            f"{exc}"
        ) from exc
    if (
        candidate_execution.fingerprint != candidate_execution_fingerprint
        or candidate_execution.subject_id
        != "validation-owner:model-regression-parent"
        or candidate_execution.subject_kind != OWNER_RECEIPT_KIND
        or candidate_execution.producer_id != "validation-owner:model-regression-parent"
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution identity does not match its canonical receipt"
        )
    if any(
        item.receipt_id == candidate_execution.receipt_id
        for item in (
            *candidate_execution.required_child_receipts,
            *candidate_execution.consumed_child_receipts,
        )
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt cannot require or consume itself"
        )
    if (
        candidate_execution.result_status != RECEIPT_STATUS_PASS
        or candidate_execution.exit_code != 0
        or candidate_execution.claim_scope != "full"
        or candidate_execution.covered_obligations
        != parent_contract_for_filter.obligation_ids
        or candidate_execution.skipped_checks
        or candidate_execution.blockers
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is not terminal full exact-obligation pass"
        )
    required_child_identities = {
        (item.receipt_id, item.expected_receipt_fingerprint)
        for item in candidate_execution.required_child_receipts
    }
    consumed_child_identities = {
        (item.receipt_id, item.receipt_fingerprint)
        for item in candidate_execution.consumed_child_receipts
    }
    if (
        required_child_identities != expected_child_identities_for_parent
        or consumed_child_identities != expected_child_identities_for_parent
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt does not compose the exact current children"
        )
    try:
        candidate_context = build_child_bound_owner_receipt_context(
            parent_current_for_filter,
            candidate_execution,
            root_path,
            receipt_root,
            child_receipts=tuple(exact_children_for_parent),
            child_verification_results=tuple(child_verifications_for_parent),
        )
    except ValueError as exc:
        raise ModelRegressionEvidenceError(
            f"model parent child-bound context is invalid: {exc}"
        ) from exc
    candidate_verification = verify_evidence_receipt(
        candidate_execution,
        candidate_context,
    )
    if not candidate_verification.ok:
        finding_codes = ", ".join(
            item.code for item in candidate_verification.findings
        )
        if candidate_verification.status == VERIFICATION_STATUS_STALE:
            raise ModelRegressionParentNotCurrentError(
                "current model parent execution is stale: " + finding_codes
            )
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is invalid: " + finding_codes
        )
    if tuple(row["model_id"] for row in declared_children) != tuple(
        sorted(selected_ids)
    ):
        raise ModelRegressionEvidenceError(
            "model parent children do not cover the current full manifest exactly"
        )
    execution_receipt_id = payload["execution_receipt_id"]
    execution_receipt_fingerprint = payload["execution_receipt_fingerprint"]
    if not execution_receipt_id or not execution_receipt_fingerprint:
        raise ModelRegressionEvidenceError(
            "passing full model parent lacks its canonical execution receipt"
        )
    if any(
        row["receipt_id"] == execution_receipt_id
        or row["receipt_fingerprint"] == execution_receipt_fingerprint
        for row in declared_children
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt cannot claim itself as a child"
        )

    declared_receipts: dict[str, EvidenceReceipt] = {}
    for row in declared_children:
        model_id = row["model_id"]
        try:
            declared_receipt = load_evidence_receipt(
                row["receipt_id"],
                root_path,
                output_directory=receipt_root,
            )
            _assert_owner_receipt_integrity(declared_receipt)
        except (OSError, ValueError) as exc:
            raise ModelRegressionEvidenceError(
                f"model parent child receipt is missing or invalid: {model_id}: {exc}"
            ) from exc
        if declared_receipt.fingerprint != row["receipt_fingerprint"]:
            raise ModelRegressionEvidenceError(
                f"model parent child fingerprint does not match the canonical receipt: {model_id}"
            )
        if declared_receipt.subject_id != f"validation-owner:model:{model_id}":
            raise ModelRegressionEvidenceError(
                f"model parent child subject does not match its model: {model_id}"
            )
        declared_receipts[model_id] = declared_receipt

    declared_by_model = {
        row["model_id"]: row for row in declared_children
    }
    entries_by_model = {entry.model_id: entry for entry in entries}
    exact_children: list[EvidenceReceipt] = []
    child_verifications: list[ReceiptVerificationResult] = []
    child_evidence: list[CurrentModelRegressionChildEvidence] = []
    for model_id in selected_ids:
        owner_id = f"model:{model_id}"
        receipt = reusable.get(owner_id)
        declared = declared_by_model.get(model_id)
        declared_receipt = declared_receipts.get(model_id)
        if receipt is None or declared is None or declared_receipt is None:
            raise ModelRegressionEvidenceError(
                f"model parent child is missing: {model_id}"
            )
        if (
            declared["receipt_id"] != receipt.receipt_id
            or declared["receipt_fingerprint"] != receipt.fingerprint
            or declared_receipt.receipt_id != receipt.receipt_id
            or declared_receipt.fingerprint != receipt.fingerprint
        ):
            raise ModelRegressionEvidenceError(
                f"model parent child identity is not exact-current: {model_id}"
            )
        expected_obligations = (f"model-regression:{model_id}",)
        if (
            receipt.subject_id != f"validation-owner:model:{model_id}"
            or receipt.subject_kind != OWNER_RECEIPT_KIND
            or receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.claim_scope != "full"
            or receipt.covered_obligations != expected_obligations
            or receipt.skipped_checks
            or receipt.blockers
        ):
            raise ModelRegressionEvidenceError(
                f"model child is not a terminal full exact-obligation pass: {model_id}"
            )
        if str(receipt.metadata.get("publication_kind", "")) != "supervised_producer":
            raise ModelRegressionEvidenceError(
                f"model child is not a direct supervised producer receipt: {model_id}"
            )
        if receipt.required_child_receipts or receipt.consumed_child_receipts:
            raise ModelRegressionEvidenceError(
                f"model child receipt cannot be an aggregate: {model_id}"
            )
        context = build_owner_receipt_context(
            currents[owner_id],
            receipt,
            receipt_root,
        )
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ModelRegressionEvidenceError(
                f"model child failed independent current verification: {model_id}: "
                + ", ".join(item.code for item in verification.findings)
            )
        child_result = child_from_owner_receipt(receipt, receipt_root)
        if (
            child_result.child_id != f"model:{model_id}"
            or child_result.status != VALIDATION_STATUS_PASS
            or child_result.payload.get("nested_receipt_id")
        ):
            raise ModelRegressionEvidenceError(
                f"model child proof is not a direct terminal result: {model_id}"
            )
        raw_result = child_result.payload.get("model_result")
        if not isinstance(raw_result, Mapping):
            raise ModelRegressionEvidenceError(
                f"model child proof is missing its model result: {model_id}"
            )
        if (
            raw_result.get("model_id") != model_id
            or raw_result.get("status") != VALIDATION_STATUS_PASS
            or raw_result.get("ok") is not True
            or raw_result.get("exit_code") != 0
        ):
            raise ModelRegressionEvidenceError(
                f"model child proof result is not terminal pass: {model_id}"
            )
        entry = entries_by_model[model_id]
        inventory = _entry_input_inventory_from_observation(
            entry,
            planning_observation,
            additional_patterns=manifest.shared_patterns_for(model_id),
        )
        expected_model_instance = build_regression_model_instance(
            root_path,
            entry,
            inventory,
        )
        expected_input_inventory = input_inventory_fingerprint(inventory)
        expected_purpose = (
            entry.purpose_closure.closure_fingerprint
            if entry.purpose_closure is not None
            else ""
        )
        native_case_results: tuple[NativeModelCaseResult, ...] = ()
        native_case_result_artifact_path = str(
            raw_result.get("native_case_result_artifact_path", "")
        )
        native_case_result_artifact_fingerprint = str(
            raw_result.get("native_case_result_artifact_fingerprint", "")
        )
        native_case_verification: NativeCaseVerification | None = None
        if "native_case_results" in raw_result:
            native_case_results = _coerce_native_case_results(
                raw_result.get("native_case_results"),
                context=f"model child proof {model_id}",
            )
        if native_case_result_artifact_path:
            (
                loaded_native_rows,
                loaded_native_path,
                loaded_native_fingerprint,
                loaded_native_verification,
            ) = _load_native_case_result_artifact(
                native_case_result_artifact_path,
                owner_id=f"model:{model_id}",
                marker_case_ids=_coerce_executed_case_ids(
                    raw_result.get("executed_case_ids", ()),
                    context=f"model child proof {model_id}",
                ),
            )
            if native_case_results and not _native_result_rows_equal(
                native_case_results, loaded_native_rows
            ):
                raise ModelRegressionEvidenceError(
                    f"model child native result artifact disagrees with its receipt: {model_id}"
                )
            if (
                native_case_result_artifact_fingerprint
                and native_case_result_artifact_fingerprint
                != loaded_native_fingerprint
            ):
                raise ModelRegressionEvidenceError(
                    f"model child native result artifact fingerprint is stale: {model_id}"
                )
            native_case_results = loaded_native_rows
            native_case_result_artifact_path = str(loaded_native_path)
            # Preserve the producer-declared envelope fingerprint.  A reader
            # may compute a digest to compare it, but strict reuse must not
            # repair an old receipt that omitted that identity by filling it
            # from the current file.
            if not native_case_result_artifact_fingerprint:
                native_case_result_artifact_fingerprint = ""
            native_case_verification = loaded_native_verification
        elif native_case_results:
            native_case_verification = NativeCaseVerification(
                ok=False,
                findings=("native_result_artifact_missing",),
            )
        serialized_native_verification = _native_case_verification_from_payload(
            raw_result.get("native_case_verification"),
            context=f"model child proof {model_id}",
        )
        if serialized_native_verification is not None:
            if (
                native_case_verification is not None
                and serialized_native_verification.to_dict()
                != native_case_verification.to_dict()
            ):
                raise ModelRegressionEvidenceError(
                    f"model child native verification disagrees with its artifact: {model_id}"
                )
            native_case_verification = serialized_native_verification
        executed_behavior_case_ids = _coerce_executed_case_ids(
            raw_result.get("executed_behavior_case_ids", ()),
            context=f"model child proof {model_id}",
        )
        native_case_bindings = _native_case_bindings_from_payload(
            raw_result.get("native_case_bindings", ()),
            context=f"model child proof {model_id}",
        )
        native_case_binding_verification = _native_binding_verification_from_payload(
            raw_result.get("native_case_binding_verification"),
            context=f"model child proof {model_id}",
        )
        child_evidence.append(
            CurrentModelRegressionChildEvidence(
                model_id=model_id,
                receipt_id=receipt.receipt_id,
                receipt_fingerprint=receipt.fingerprint,
                model_instance_id=_exact_model_result_identity(
                    raw_result,
                    "model_instance_id",
                    entry.purpose_closure.model_instance_id
                    if entry.purpose_closure is not None
                    else "",
                    model_id=model_id,
                ),
                model_instance_fingerprint=_exact_model_result_identity(
                    raw_result,
                    "model_instance_fingerprint",
                    expected_model_instance.fingerprint,
                    model_id=model_id,
                ),
                input_inventory_fingerprint=_exact_model_result_identity(
                    raw_result,
                    "input_inventory_fingerprint",
                    expected_input_inventory,
                    model_id=model_id,
                ),
                purpose_closure_fingerprint=_exact_model_result_identity(
                    raw_result,
                    "purpose_closure_fingerprint",
                    expected_purpose,
                    model_id=model_id,
                ),
                executed_case_ids=_coerce_executed_case_ids(
                    raw_result.get("executed_case_ids", ()),
                    context=f"model child proof {model_id}",
                ),
                executed_behavior_case_ids=executed_behavior_case_ids,
                native_case_bindings=native_case_bindings,
                native_case_binding_verification=native_case_binding_verification,
                native_case_results=native_case_results,
                native_case_result_artifact_path=native_case_result_artifact_path,
                native_case_result_artifact_fingerprint=(
                    native_case_result_artifact_fingerprint
                ),
                native_case_verification=native_case_verification,
                receipt=receipt,
                verification=verification,
            )
        )
        exact_children.append(receipt)
        child_verifications.append(verification)

    try:
        parent_execution = load_evidence_receipt(
            execution_receipt_id,
            root_path,
            output_directory=receipt_root,
        )
        _assert_owner_receipt_integrity(parent_execution)
    except (OSError, ValueError) as exc:
        raise ModelRegressionEvidenceError(
            f"model parent execution receipt is unavailable or invalid: {exc}"
        ) from exc
    if (
        parent_execution.fingerprint != execution_receipt_fingerprint
        or parent_execution.subject_id
        != "validation-owner:model-regression-parent"
        or parent_execution.subject_kind != OWNER_RECEIPT_KIND
        or parent_execution.producer_id
        != "validation-owner:model-regression-parent"
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution identity does not match its canonical receipt"
        )
    if any(
        item.receipt_id == parent_execution.receipt_id
        for item in (
            *parent_execution.required_child_receipts,
            *parent_execution.consumed_child_receipts,
        )
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt cannot require or consume itself"
        )

    parent_contract = _model_parent_owner_contract(
        manifest,
        entries,
        claim_scope="full",
        tier="full",
    )
    if (
        parent_execution.result_status != RECEIPT_STATUS_PASS
        or parent_execution.exit_code != 0
        or parent_execution.claim_scope != "full"
        or parent_execution.covered_obligations
        != parent_contract.obligation_ids
        or parent_execution.skipped_checks
        or parent_execution.blockers
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is not terminal full exact-obligation pass"
        )
    expected_child_identities = {
        (item.receipt_id, item.fingerprint) for item in exact_children
    }
    required_child_identities = {
        (item.receipt_id, item.expected_receipt_fingerprint)
        for item in parent_execution.required_child_receipts
    }
    consumed_child_identities = {
        (item.receipt_id, item.receipt_fingerprint)
        for item in parent_execution.consumed_child_receipts
    }
    if (
        required_child_identities != expected_child_identities
        or consumed_child_identities != expected_child_identities
    ):
        raise ModelRegressionEvidenceError(
            "model parent execution receipt does not compose the exact current children"
        )
    parent_current = build_owner_current(
        root_path,
        parent_contract,
        all_contracts=(parent_contract,),
    )
    try:
        parent_context = build_child_bound_owner_receipt_context(
            parent_current,
            parent_execution,
            root_path,
            receipt_root,
            child_receipts=tuple(exact_children),
            child_verification_results=tuple(child_verifications),
        )
    except ValueError as exc:
        raise ModelRegressionEvidenceError(
            f"model parent child-bound context is invalid: {exc}"
        ) from exc
    parent_verification = verify_evidence_receipt(
        parent_execution,
        parent_context,
    )
    if not parent_verification.ok:
        raise ModelRegressionEvidenceError(
            "model parent execution receipt is not an exact-current full composition: "
            + ", ".join(item.code for item in parent_verification.findings)
        )

    return CurrentModelRegressionParentEvidence(
        manifest_fingerprint=manifest_fingerprint,
        parent_artifact_path=str(parent_path),
        parent_artifact_fingerprint=payload["parent_receipt_fingerprint"],
        parent_execution_receipt_id=parent_execution.receipt_id,
        parent_execution_receipt_fingerprint=parent_execution.fingerprint,
        children=tuple(child_evidence),
    )


def run_manifest_regressions(
    root: str | Path = ".",
    *,
    tier: str = "fast",
    model_patterns: Sequence[str] = (),
    shard: str | None = None,
    jobs: int = 1,
    timeout: float | None = None,
    output_dir: str | Path | None = None,
    cancel_event: threading.Event | None = None,
    progress: ProgressCallback | None = None,
    allow_mutating: bool = False,
    command: str = "flowguard-model-regressions",
    reuse_current: bool = True,
    receipt_dir: str | Path | None = None,
    require_executed_case_ids: bool = False,
    authority_kind: str = "standalone",
    parent_scope: str = "",
) -> ModelRegressionReport:
    """Run the manifest once and publish its terminal run in one scope.

    ``model-regressions`` is also used as a child of the full validation
    composition.  In that mode its output directory lives beside the other
    child outputs, whose ``CURRENT.json`` is owned by the composition and is
    typed as ``child``.  Making the authority kind explicit prevents a child
    model run from trying to replace a pre-existing child/parent head with a
    standalone head (the old implicit default caused a false closure failure
    after all model evidence had already been reused).
    """
    root_path = Path(root).resolve()
    # ``ModelRegressionEntry.timeout_seconds`` is retained as authored
    # resource metadata, but it is not the functional owner identity and it
    # must not silently impose a shorter cap than the current project policy.
    # When a project has a current execution-policy table, use its model-owner
    # budget as the default for every leaf.  An explicit CLI ``timeout`` stays
    # an intentional one-run override.  Small standalone fixtures without a
    # project policy keep their entry-local cap so their bounded timeout tests
    # remain deterministic.
    effective_timeout = timeout
    project_policy_path = root_path / ".flowguard" / "project.toml"
    if effective_timeout is None and project_policy_path.is_file():
        effective_timeout = ValidationExecutionPolicy.from_project(
            root_path
        ).owner_timeout("model_regressions_full")
    if authority_kind not in {"standalone", "child", "parent"}:
        raise ValueError(
            "authority_kind must be standalone, child, or parent"
        )
    if authority_kind == "child" and (
        not parent_scope or parent_scope != parent_scope.strip()
    ):
        raise ValueError(
            "child model-regression evidence requires one normalized parent_scope"
        )
    if authority_kind != "child" and parent_scope:
        raise ValueError(
            "parent_scope is only valid for child model-regression evidence"
        )
    manifest = ModelRegressionManifest.load(root_path)
    audit = audit_manifest(root_path, manifest)
    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    if timeout is not None and timeout <= 0:
        raise ValueError("timeout must be positive")
    selected = select_entries(manifest, tier=tier, model_patterns=model_patterns, shard=shard)
    source_inventory_errors = audit_selected_model_source_inventories(
        root_path,
        (entry.model_id for entry in selected),
    )
    complete_selected = select_entries(manifest, tier="full")
    parent_claim_scope = (
        "full"
        if tier == "full"
        and not model_patterns
        and shard is None
        and tuple(entry.model_id for entry in selected)
        == tuple(entry.model_id for entry in complete_selected)
        else "scoped"
    )
    if any(entry.mutation_policy == "mutating" for entry in selected) and not allow_mutating:
        blocked = tuple(entry.model_id for entry in selected if entry.mutation_policy == "mutating")
        audit = ManifestAudit(
            False,
            audit.discovered_model_ids,
            audit.registered_model_ids,
            audit.errors + tuple(f"mutating model blocked by default: {item}" for item in blocked),
        )
    if source_inventory_errors:
        audit = ManifestAudit(
            False,
            audit.discovered_model_ids,
            audit.registered_model_ids,
            audit.errors + source_inventory_errors,
        )
    receipt_root = (
        Path(receipt_dir).resolve()
        if receipt_dir is not None
        else root_path / ".flowguard" / "evidence" / "model-owner-receipts"
    )
    contracts = tuple(
        _model_owner_contract(root_path, manifest, entry) for entry in selected
    )
    parent_contract = _model_parent_owner_contract(
        manifest,
        selected,
        claim_scope=parent_claim_scope,
        tier=tier,
    )
    planning_observation = observe_validation_owners(
        root_path,
        contracts,
        receipt_root=receipt_root,
        additional_input_patterns=parent_contract.input_patterns,
        prefer_latest_model_receipt=True,
    )
    plan_rows = planning_observation.rows
    currents = planning_observation.current_by_owner
    reusable_receipts = planning_observation.receipt_by_owner
    if require_executed_case_ids:
        # A legacy current receipt without the strict producer envelope is
        # stale for this execution mode.  Reclassify only that owner for one
        # bounded fresh run; never promote the old receipt or run all owners
        # merely because one case projection is missing.
        refreshed_rows = []
        for row in plan_rows:
            if row.disposition != OWNER_REUSE_CURRENT:
                refreshed_rows.append(row)
                continue
            stale_native = False
            try:
                child = child_from_owner_receipt(
                    reusable_receipts[row.owner_id], receipt_root
                )
                # ``child_from_owner_receipt`` returns the generic validation
                # child envelope.  The native projection is owned by its
                # nested ``model_result`` payload; reading attributes from the
                # envelope itself used to raise ``AttributeError`` and
                # incorrectly demote every strict current receipt to a fresh
                # producer run.  Keep this check read-only and inspect the
                # persisted producer fields exactly as the reuse converter
                # does below.
                raw_child = child.payload.get("model_result")
                if not isinstance(raw_child, Mapping):
                    stale_native = True
                    raw_child = {}
                stale_native = not (
                    raw_child.get("executed_case_ids")
                    and raw_child.get("native_case_results")
                    and raw_child.get("native_case_result_artifact_path")
                    and raw_child.get("native_case_result_artifact_fingerprint")
                )
                if not stale_native:
                    # Presence of a native envelope is not enough for reuse.
                    # A previous producer may have published a receipt whose
                    # absolute artifact path was later replaced by another
                    # run (or whose contents were moved back under the same
                    # path).  Validate the persisted artifact and its
                    # declared fingerprint now, before classifying the owner
                    # as ``reuse_current``.  This keeps a broken receipt from
                    # poisoning the full parent and demotes only this owner
                    # to one bounded producer execution.
                    loaded_rows, _loaded_path, loaded_fingerprint, loaded_verification = (
                        _load_native_case_result_artifact(
                            str(raw_child["native_case_result_artifact_path"]),
                            owner_id=row.owner_id,
                            marker_case_ids=_coerce_executed_case_ids(
                                raw_child.get("executed_case_ids", ()),
                                context=f"strict reuse preflight {row.owner_id}",
                            ),
                        )
                    )
                    declared_rows = _coerce_native_case_results(
                        raw_child.get("native_case_results"),
                        context=f"strict reuse preflight {row.owner_id}",
                    )
                    stale_native = (
                        not loaded_verification.ok
                        or not _native_result_rows_equal(declared_rows, loaded_rows)
                        or str(raw_child["native_case_result_artifact_fingerprint"])
                        != loaded_fingerprint
                    )
            except Exception:
                stale_native = True
            if stale_native:
                refreshed_rows.append(
                    replace(
                        row,
                        disposition=OWNER_EXECUTE,
                        reason="current receipt lacks strict native case evidence",
                        receipt_id="",
                        receipt_fingerprint="",
                    )
                )
            else:
                refreshed_rows.append(row)
        plan_rows = tuple(refreshed_rows)
        reusable_receipts = {
            owner_id: receipt
            for owner_id, receipt in reusable_receipts.items()
            if any(
                current_row.owner_id == owner_id
                and current_row.disposition == OWNER_REUSE_CURRENT
                for current_row in plan_rows
            )
        }
    if not reuse_current:
        plan_rows = tuple(
            replace(
                row,
                disposition=OWNER_EXECUTE,
                reason="caller explicitly requested fresh execution",
                receipt_id="",
                receipt_fingerprint="",
            )
            if row.disposition == OWNER_REUSE_CURRENT
            else row
            for row in plan_rows
        )
        reusable_receipts = {}
    blocked_rows = tuple(
        row for row in plan_rows if row.disposition == OWNER_BLOCKED
    )
    if blocked_rows:
        audit = ManifestAudit(
            False,
            audit.discovered_model_ids,
            audit.registered_model_ids,
            audit.errors
            + tuple(
                f"validation owner blocked for {row.owner_id}: {row.reason}"
                for row in blocked_rows
            ),
        )
    entries_by_owner = {
        f"model:{entry.model_id}": entry for entry in selected
    }
    # Resource-policy changes do not alter functional currentness, but a
    # tightened cap can make one previously passing producer incompatible
    # with the current execution policy.  Demote only those leaves before
    # constructing reused results; unrelated current receipts remain reusable.
    plan_rows = _demote_policy_incompatible_model_rows(
        plan_rows,
        reusable_receipts,
        entries_by_owner,
        receipt_root=receipt_root,
        timeout_override=effective_timeout,
    )
    plan_rows = _demote_model_identity_mismatches(
        plan_rows,
        reusable_receipts,
        entries_by_owner,
        root_path=root_path,
        manifest=manifest,
        planning_observation=planning_observation,
        receipt_root=receipt_root,
    )
    reusable_receipts = {
        owner_id: receipt
        for owner_id, receipt in reusable_receipts.items()
        if any(
            row.owner_id == owner_id and row.disposition == OWNER_REUSE_CURRENT
            for row in plan_rows
        )
    }
    reused_results: dict[str, ModelRunResult] = {}
    if audit.ok:
        for row in plan_rows:
            if row.disposition != OWNER_REUSE_CURRENT:
                continue
            entry = entries_by_owner[row.owner_id]
            child = child_from_owner_receipt(
                reusable_receipts[row.owner_id],
                receipt_root,
            )
            reusable = _model_result_from_reused_child(
                entry,
                child,
                require_native_case_results=require_executed_case_ids,
            )
            reused_results[entry.model_id] = reusable
            if progress:
                progress(
                    {
                        "event": "reused",
                        "model_id": entry.model_id,
                        "status": reusable.status,
                        "seconds": 0.0,
                    }
                )
    pending = tuple(
        entries_by_owner[row.owner_id]
        for row in plan_rows
        if row.disposition == OWNER_EXECUTE
    )
    input_inventories = {
        entry.model_id: _entry_input_inventory_from_observation(
            entry,
            planning_observation,
            additional_patterns=manifest.shared_patterns_for(entry.model_id),
        )
        for entry in pending
    }
    if jobs > 1 and any(not entry.shard_safe for entry in pending):
        unsafe = tuple(entry.model_id for entry in pending if not entry.shard_safe)
        raise ValueError("parallel execution includes non-shard-safe models: " + ", ".join(unsafe))
    if output_dir is None:
        output_path = Path(tempfile.mkdtemp(prefix="flowguard-model-regressions-"))
    else:
        output_path = Path(output_dir).resolve()
    ensure_new_run_directory(output_path)
    cancel = cancel_event or threading.Event()
    # The owner observation already froze the exact functional source
    # manifest for this selection.  Keep that as the semantic projection, and
    # add one bounded metadata snapshot of the indexed tracked paths.  The
    # latter is intentionally not a second source-freshness scan: it exists
    # only to catch a producer writing a governed tracked file that is outside
    # the selected model owner inputs.  It also preserves the fail-closed
    # mutation guard for native producers that are deliberately broad.
    tracked_paths = _tracked_paths(root_path)
    tracked_before = (
        _relative_snapshot(_snapshot(tracked_paths), root_path)
        if tracked_paths
        else {}
    )
    before = _input_manifest_snapshot(
        planning_observation.repository_input_manifest
    )
    before.update(tracked_before)
    started_at = time.time()
    results: list[ModelRunResult] = list(reused_results.values())
    source_freshness = ValidationObservationFreshness.not_run(
        planning_observation
    )
    if audit.ok:
        executed_results, source_freshness = _execute_pending_models(
                root_path=root_path,
                pending=pending,
                jobs=jobs,
                timeout=effective_timeout,
                output_path=output_path,
                receipt_root=receipt_root,
                currents=currents,
                contracts=contracts,
                planning_observation=planning_observation,
                cancel=cancel,
                progress=progress,
                input_inventories=input_inventories,
                shared_patterns_by_model={
                    entry.model_id: manifest.shared_patterns_for(entry.model_id)
                    for entry in pending
                },
                require_executed_case_ids=require_executed_case_ids,
            )
        results.extend(executed_results)
    results.sort(key=lambda item: item.model_id)
    if source_freshness.ok and source_freshness.owner_currents:
        # ``assert_validation_owner_observation_fresh`` has already completed
        # the one bounded post-run source observation and owns these exact
        # current manifests.  Reusing them avoids a second Git/hash pass that
        # can time out after a long leaf run and falsely report every source as
        # mutated.
        after = _input_manifest_snapshot(
            _governed_owner_input_manifest(
                source_freshness.owner_currents,
                base_manifest=planning_observation.repository_input_manifest,
            )
        )
    else:
        # No producer ran (or the observation was already blocked), so there
        # is no new source state to compare.  Preserve the original snapshot;
        # the report's own owner/audit status remains authoritative.
        after = before
    if tracked_paths:
        after = dict(after)
        after.update(
            _relative_snapshot(_snapshot(tracked_paths), root_path)
        )
    mutations = _mutation_paths(before, after, root_path)
    selected_ids = tuple(entry.model_id for entry in selected)
    unavailable_optional_ids = tuple(
        entry.model_id
        for entry in manifest.entries
        if entry.distribution_policy == "optional_local"
        and (
            not (root_path / entry.model_path).is_file()
            or len(entry.runner) < 2
            or not (root_path / entry.runner[1]).is_file()
        )
    )
    completed_ids = {item.model_id for item in results}
    skipped_ids = tuple(item for item in selected_ids if item not in completed_ids)
    report = ModelRegressionReport(
        root=str(root_path),
        tier=tier,
        output_dir=str(output_path),
        audit=audit,
        results=tuple(results),
        selected_model_ids=selected_ids,
        skipped_model_ids=skipped_ids,
        unavailable_optional_model_ids=unavailable_optional_ids,
        mutation_paths=mutations,
        started_at_epoch=started_at,
        finished_at_epoch=time.time(),
        command=command,
        parent_claim_scope=parent_claim_scope,
    )
    (
        parent_path,
        parent_fingerprint,
        composition_observation,
        final_freshness,
        parent_composition_seconds,
    ) = _write_model_parent_receipt(
        root_path,
        manifest,
        receipt_root,
        report,
        planning_observation=planning_observation,
        source_freshness=source_freshness,
    )
    report = replace(
        report,
        parent_receipt_path=parent_path,
        parent_receipt_fingerprint=parent_fingerprint,
        initial_observation_seconds=planning_observation.observation_seconds,
        receipt_reconciliation_seconds=(
            composition_observation.observation_seconds
        ),
        final_freshness_seconds=final_freshness.observation_seconds,
        parent_composition_seconds=parent_composition_seconds,
        per_leaf_source_current_rebuild_count=0,
        per_leaf_receipt_store_scan_count=0,
        receipt_reconciliation_count=(1 if final_freshness.ok else 0),
        initial_observation_fingerprint=(
            composition_observation.observation_fingerprint
        ),
        final_freshness_fingerprint=(
            final_freshness.final_observation_fingerprint
        ),
    )
    report_path = output_path / "report.json"
    _write_json(report_path, report.to_dict())
    publish_run(
        output_path,
        kind="model-simulator" if command == "flowguard-simulator" else "model-regressions",
        status=report.status,
        result_path=report_path,
        started_at_epoch=report.started_at_epoch,
        finished_at_epoch=report.finished_at_epoch,
        authority_kind=authority_kind,
        parent_scope=parent_scope,
    )
    if (
        report.parent_claim_scope == "full"
        and report.tier == "full"
        and not report.skipped_model_ids
        and report.ok
    ):
        # Publish the mutable current head last, after the parent artifact,
        # terminal run manifest, and report have all been written.  Historical
        # content-addressed parents are never scanned by consumers.
        write_json_atomic(
            receipt_root / "model-parents" / "CURRENT.json",
            {
                "artifact_type": MODEL_REGRESSION_PARENT_ARTIFACT_TYPE,
                "parent_receipt_fingerprint": report.parent_receipt_fingerprint,
                "schema_version": MODEL_REGRESSION_PARENT_CURRENT_SCHEMA,
            },
        )
    return report


__all__ = [
    "MANIFEST_SCHEMA",
    "MODEL_EXECUTION_EVIDENCE_SCHEMA",
    "EXECUTED_CASE_IDS_MARKER",
    "NATIVE_CASE_RESULT_ARTIFACT_NAME",
    "MODEL_REGRESSION_PARENT_ARTIFACT_TYPE",
    "MODEL_REGRESSION_PARENT_CURRENT_SCHEMA",
    "MODEL_REGRESSION_PARENT_RECEIPT_SCHEMA",
    "CurrentModelRegressionChildEvidence",
    "CurrentModelRegressionParentEvidence",
    "ModelOwnerExecutionEvidence",
    "ModelRegressionExecutionEvidencePackage",
    "ManifestAudit",
    "ModelImpactMap",
    "ModelRegressionEvidenceError",
    "ModelRegressionEntry",
    "ModelRegressionManifest",
    "ModelRegressionManifestError",
    "ModelRegressionReport",
    "ModelRunResult",
    "audit_intent_source_input_bindings",
    "audit_selected_model_source_inventories",
    "audit_manifest",
    "build_regression_model_instance",
    "compile_model_impact_map",
    "discover_model_directories",
    "input_inventory_fingerprint",
    "model_instance_fingerprint",
    "parse_executed_case_ids",
    "build_model_regression_execution_evidence",
    "parse_shard",
    "resolve_current_full_model_regression_parent",
    "resolve_entry_input_inventory",
    "run_manifest_regressions",
    "select_entries",
]
