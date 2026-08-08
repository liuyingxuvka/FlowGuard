"""Supervised execution for one validation-owner leaf receipt.

This module is the only library path that turns a command episode into a
validation-owner leaf receipt.  A caller may describe the semantic evidence
context, but it cannot publish a passing receipt unless the configured command
has actually reached a clean, zero-exit terminal state under process-tree
supervision and the owner inputs remain unchanged through publication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence_receipts import (
    EvidenceReceipt,
    ReceiptVerificationResult,
    fingerprint_value,
)
from .process_supervision import (
    SupervisedCommandResult,
    _is_authentic_supervised_result,
    run_supervised,
)
from .validation_ownership import (
    ValidationObservationFreshness,
    ValidationOwnerContract,
    ValidationOwnerCurrent,
    _prepare_owner_receipt,
    _publish_prepared_owner_receipt,
    _verify_prepared_owner_receipt,
    build_owner_current,
    find_reusable_owner_receipt,
)
from .validation_results import ValidationChildResult


VALIDATION_OWNER_EXECUTION_SCHEMA = (
    "flowguard.supervised_validation_owner_execution.v2"
)
VALIDATION_OWNER_RESULT_IDENTITY_SCHEMA = (
    "flowguard.validation_owner_result_identity.v1"
)

_EVIDENCE_RUN_TOKEN = "<EVIDENCE_RUN>"
_EVIDENCE_OUTPUT_OPTIONS = frozenset(
    {"--output-dir", "--output-directory", "--receipt-dir"}
)


def _is_canonical_sha256(value: str) -> bool:
    prefix, separator, digest = str(value).partition(":")
    return bool(
        prefix == "sha256"
        and separator
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


@dataclass(frozen=True)
class ValidationOwnerResultIdentityRequirement:
    """Declare an exact typed identity projection from producer JSON output."""

    projection_id: str
    source_path: tuple[str, ...]
    fingerprint_fields: tuple[str, ...]
    content_fingerprint_field: str = ""

    def __post_init__(self) -> None:
        projection_id = str(self.projection_id).strip()
        source_path = tuple(str(item).strip() for item in self.source_path)
        fingerprint_fields = tuple(
            str(item).strip() for item in self.fingerprint_fields
        )
        content_fingerprint_field = str(self.content_fingerprint_field).strip()
        if not projection_id or not source_path or not fingerprint_fields:
            raise ValueError(
                "result identity requirement needs projection id, source path, "
                "and fingerprint fields"
            )
        if any(not item for item in (*source_path, *fingerprint_fields)):
            raise ValueError("result identity path and field names cannot be empty")
        if len(set(fingerprint_fields)) != len(fingerprint_fields):
            raise ValueError("result identity fingerprint fields must be unique")
        if (
            content_fingerprint_field
            and content_fingerprint_field not in fingerprint_fields
        ):
            raise ValueError(
                "content fingerprint field must be one projected fingerprint field"
            )
        object.__setattr__(self, "projection_id", projection_id)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "fingerprint_fields", fingerprint_fields)
        object.__setattr__(
            self,
            "content_fingerprint_field",
            content_fingerprint_field,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": VALIDATION_OWNER_RESULT_IDENTITY_SCHEMA,
            "projection_id": self.projection_id,
            "source_path": list(self.source_path),
            "fingerprint_fields": list(self.fingerprint_fields),
            "content_fingerprint_field": self.content_fingerprint_field,
        }

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())


def _validated_result_identity_projection(
    supervised: SupervisedCommandResult,
    requirement: ValidationOwnerResultIdentityRequirement | None,
) -> tuple[dict[str, Any] | None, str]:
    """Project required identities from attested stdout with no alternate source."""

    if requirement is None:
        return None, ""
    try:
        payload = json.loads(supervised.stdout)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, "validation_owner_result_identity_invalid_json"
    if not isinstance(payload, Mapping):
        return None, "validation_owner_result_identity_invalid_json_object"
    source: Any = payload
    traversed: list[str] = []
    for component in requirement.source_path:
        traversed.append(component)
        if not isinstance(source, Mapping) or component not in source:
            return (
                None,
                "validation_owner_result_identity_missing_path:"
                + ".".join(traversed),
            )
        source = source[component]
    if not isinstance(source, Mapping):
        return (
            None,
            "validation_owner_result_identity_invalid_object:"
            + ".".join(requirement.source_path),
        )

    projected: dict[str, str] = {}
    for field_name in requirement.fingerprint_fields:
        field_path = ".".join((*requirement.source_path, field_name))
        if field_name not in source:
            return None, "validation_owner_result_identity_missing:" + field_path
        value = str(source[field_name])
        if not _is_canonical_sha256(value):
            return None, "validation_owner_result_identity_invalid:" + field_path
        projected[field_name] = value

    if requirement.content_fingerprint_field:
        field_name = requirement.content_fingerprint_field
        content = dict(source)
        declared = str(content.pop(field_name))
        actual = fingerprint_value(content)
        if declared != actual:
            return (
                None,
                "validation_owner_result_identity_mismatch:"
                + ".".join((*requirement.source_path, field_name)),
            )

    return (
        {
            "schema_version": VALIDATION_OWNER_RESULT_IDENTITY_SCHEMA,
            "projection_id": requirement.projection_id,
            "source_path": list(requirement.source_path),
            **projected,
        },
        "",
    )


def _utc_timestamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _execution_payload(result: SupervisedCommandResult) -> dict[str, Any]:
    """Project terminal evidence without persisting raw output or host paths."""

    return {
        "schema_version": VALIDATION_OWNER_EXECUTION_SCHEMA,
        "episode_token": result.episode_token,
        "command_fingerprint": fingerprint_value(list(result.command)),
        "cwd_fingerprint": fingerprint_value(result.cwd),
        "exit_code": result.exit_code,
        "terminal_reason": result.terminal_reason,
        "timed_out": result.timed_out,
        "cancelled": result.cancelled,
        "interrupted": result.interrupted,
        "termination_stage": result.termination_stage,
        "cleanup_confirmed": result.cleanup_confirmed,
        "root_process_id": result.root_process_id,
        "root_process_running": result.root_process_running,
        "containment_query_succeeded": result.containment_query_succeeded,
        "contained_process_ids_before_cleanup": list(
            result.contained_process_ids_before_cleanup
        ),
        "descendant_process_ids": list(result.descendant_process_ids),
        "stdout_fingerprint": fingerprint_value(result.stdout),
        "stderr_fingerprint": fingerprint_value(result.stderr),
    }


def _matches_contract_command_template(
    contract_command: Sequence[str],
    executed_command: Sequence[str],
) -> bool:
    """Match one exact command, allowing only declared evidence-path slots.

    Full validation uses a stable ``<EVIDENCE_RUN>`` token so a current leaf
    receipt can be reused when only the retained run-artifact directory
    changes.  The token is not a general wildcard: it is valid only as the
    absolute path value immediately following one of the three evidence-output
    options.  Every executable, mode, input, and behavioral argument remains
    byte-for-byte bound to the frozen contract.
    """

    expected = tuple(str(item) for item in contract_command)
    observed = tuple(str(item) for item in executed_command)
    if len(expected) != len(observed):
        return False
    for index, (contract_value, executed_value) in enumerate(
        zip(expected, observed, strict=True)
    ):
        if contract_value == _EVIDENCE_RUN_TOKEN:
            if index == 0 or expected[index - 1] not in _EVIDENCE_OUTPUT_OPTIONS:
                return False
            if not Path(executed_value).is_absolute():
                return False
            continue
        if contract_value != executed_value:
            return False
    return True


@dataclass(frozen=True)
class ValidationOwnerExecutionResult:
    """Terminal command result plus receipt evidence, when publication is safe."""

    supervised: SupervisedCommandResult
    receipt: EvidenceReceipt | None = None
    verification: ReceiptVerificationResult | None = None
    blocker: str = ""

    @property
    def ok(self) -> bool:
        return bool(
            self.supervised.ok
            and self.receipt is not None
            and self.verification is not None
            and self.verification.ok
            and not self.blocker
        )


def publish_supervised_validation_owner_result(
    current: ValidationOwnerCurrent,
    supervised: SupervisedCommandResult,
    root: str | Path,
    receipt_root: str | Path,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    child_id: str,
    evidence_context: Mapping[str, Any],
    summary: str,
    claim_boundary: str,
    result_identity_requirement: (
        ValidationOwnerResultIdentityRequirement | None
    ) = None,
    source_freshness: ValidationObservationFreshness | None = None,
) -> ValidationOwnerExecutionResult:
    """Publish one producer-attested exact owner command as a passing leaf.

    A serialized terminal artifact, caller-constructed result, changed command,
    changed working directory, surviving descendant, or stale input cannot be
    converted into a passing receipt through this API.
    """

    root_path = Path(root).resolve()
    contracts = tuple(all_contracts)
    if not _is_authentic_supervised_result(supervised):
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker="supervised_result_not_producer_attested",
        )
    if not _matches_contract_command_template(
        current.contract.command,
        supervised.command,
    ):
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker="supervised_command_contract_mismatch",
        )
    if Path(supervised.cwd).resolve() != root_path:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker="supervised_cwd_contract_mismatch",
        )
    if supervised.descendant_process_ids:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker="supervised_descendants_not_empty",
        )
    if not supervised.ok:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker=f"supervised_command_not_green:{supervised.terminal_reason}",
        )

    result_identity_projection, identity_blocker = (
        _validated_result_identity_projection(
            supervised,
            result_identity_requirement,
        )
    )
    if identity_blocker:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker=identity_blocker,
        )

    if source_freshness is None:
        refreshed_after_execution = build_owner_current(
            root_path,
            current.contract,
            all_contracts=contracts,
        )
    else:
        observed_current = source_freshness.current_by_owner.get(
            current.contract.owner_id
        )
        if (
            not source_freshness.ok
            or observed_current is None
            or observed_current.contract != current.contract
            or observed_current.owner_identity != current.owner_identity
        ):
            return ValidationOwnerExecutionResult(
                supervised=supervised,
                blocker="validation_owner_source_observation_mismatch",
            )
        refreshed_after_execution = observed_current
    if refreshed_after_execution.owner_identity != current.owner_identity:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker="validation_owner_inputs_changed_during_execution",
        )

    normalized_evidence_context = dict(evidence_context)
    reserved_context_keys = {
        "supervised_execution",
        "result_identity_projection",
    }
    collision = sorted(reserved_context_keys.intersection(normalized_evidence_context))
    if collision:
        raise ValueError(
            "evidence_context cannot replace producer-owned authority: "
            + ", ".join(collision)
        )
    producer_evidence: dict[str, Any] = {
        "supervised_execution": _execution_payload(supervised),
    }
    if result_identity_projection is not None:
        producer_evidence["result_identity_projection"] = (
            result_identity_projection
        )
    child = ValidationChildResult(
        child_id=str(child_id),
        status="pass",
        summary=str(summary),
        claim_boundary=str(claim_boundary),
        payload={
            **producer_evidence,
            **normalized_evidence_context,
        },
    )
    prepared = _prepare_owner_receipt(
        refreshed_after_execution,
        child,
        receipt_root,
        started_at=_utc_timestamp(supervised.started_at_epoch),
        finished_at=_utc_timestamp(supervised.finished_at_epoch),
        publication_kind="supervised_producer",
    )
    prepared_verification = _verify_prepared_owner_receipt(
        refreshed_after_execution,
        prepared,
    )
    if not prepared_verification.ok:
        raise ValueError(
            "prepared supervised validation owner receipt is not exact-current: "
            + ", ".join(prepared_verification.finding_codes)
        )

    refreshed_at_publication = (
        refreshed_after_execution
        if source_freshness is not None
        else build_owner_current(
            root_path,
            current.contract,
            all_contracts=contracts,
        )
    )
    if refreshed_at_publication.owner_identity != current.owner_identity:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            blocker="validation_owner_inputs_changed_before_publication",
        )
    receipt = _publish_prepared_owner_receipt(
        prepared,
        root_path,
        receipt_root,
    )
    if source_freshness is not None:
        return ValidationOwnerExecutionResult(
            supervised=supervised,
            receipt=receipt,
            verification=prepared_verification,
        )
    canonical, verification = find_reusable_owner_receipt(
        refreshed_at_publication,
        root_path,
        receipt_root,
    )
    if (
        canonical is None
        or verification is None
        or canonical.receipt_id != receipt.receipt_id
        or canonical.fingerprint != receipt.fingerprint
        or not verification.ok
    ):
        raise ValueError(
            "supervised validation owner receipt failed immediate canonical verification"
        )
    return ValidationOwnerExecutionResult(
        supervised=supervised,
        receipt=receipt,
        verification=verification,
    )


def execute_validation_owner_command(
    current: ValidationOwnerCurrent,
    root: str | Path,
    receipt_root: str | Path,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    child_id: str,
    evidence_context: Mapping[str, Any],
    summary: str,
    claim_boundary: str,
    grace_seconds: float = 3.0,
    environment: Mapping[str, str] | None = None,
    cancel_event: Any | None = None,
    result_identity_requirement: (
        ValidationOwnerResultIdentityRequirement | None
    ) = None,
) -> ValidationOwnerExecutionResult:
    """Execute one exact owner and publish only its clean terminal pass."""

    root_path = Path(root).resolve()
    contracts = tuple(all_contracts)
    refreshed_before = build_owner_current(
        root_path,
        current.contract,
        all_contracts=contracts,
    )
    if refreshed_before.owner_identity != current.owner_identity:
        raise ValueError("validation owner inputs changed before command execution")
    supervised = run_supervised(
        current.contract.command,
        cwd=root_path,
        timeout_seconds=current.contract.timeout_seconds,
        grace_seconds=grace_seconds,
        environment=environment,
        cancel_event=cancel_event,
    )
    return publish_supervised_validation_owner_result(
        current,
        supervised,
        root_path,
        receipt_root,
        all_contracts=contracts,
        child_id=child_id,
        evidence_context=evidence_context,
        summary=summary,
        claim_boundary=claim_boundary,
        result_identity_requirement=result_identity_requirement,
    )


__all__ = [
    "VALIDATION_OWNER_EXECUTION_SCHEMA",
    "VALIDATION_OWNER_RESULT_IDENTITY_SCHEMA",
    "ValidationOwnerExecutionResult",
    "ValidationOwnerResultIdentityRequirement",
    "execute_validation_owner_command",
    "publish_supervised_validation_owner_result",
]
