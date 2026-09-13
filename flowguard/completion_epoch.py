"""Frozen completion epochs for one-shot FlowGuard terminal validation.

The ordinary validation pipeline is intentionally mutable while source work is
in progress.  A completion epoch is the small boundary between that mutable
phase and the terminal full gate: it records the exact identities which are to
be validated, refuses admission while governed work remains, and prevents a
second full producer attempt for the same frozen identity.

This module is deliberately independent of OpenSpec and of any particular
validation producer.  It does not decide whether a model, test, reverse map,
or external tree is semantically acceptable; those owners provide the
fingerprints and boolean admission facts.  The terminal ledger is output-only
evidence and is never a source file or a task/checklist update.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Sequence
import uuid

from .evidence_receipts import fingerprint_value


COMPLETION_EPOCH_SCHEMA = "flowguard.completion_epoch.v2"
COMPLETION_EPOCH_ADMISSION_SCHEMA = "flowguard.completion_epoch_admission.v2"
COMPLETION_EPOCH_LEDGER_SCHEMA = "flowguard.completion_epoch_terminal_ledger.v2"
# Readiness v2 is intentionally a direct replacement for the earlier
# caller-authored shape.  A pre-run readiness receipt never carries a list of
# completed actions; those are producer output derived from independently
# verified child receipts after the full run settles.
COMPLETION_EPOCH_READINESS_SCHEMA = "flowguard.completion_epoch_readiness.v2"
COMPLETION_REPAIR_LINK_SCHEMA = "flowguard.completion_epoch_repair_link.v1"
COMPLETION_CYCLE_SCHEMA = "flowguard.completion_cycle.v1"
COMPLETION_CYCLE_RESERVATION_SCHEMA = "flowguard.completion_cycle_reservation.v1"
COMPLETION_REPAIR_GROUP_RECEIPT_SCHEMA = (
    "flowguard.completion_repair_group_receipt.v1"
)
# A repair link is only an admission token.  The full consumer must reload
# this content-addressed group and bind it to the predecessor ledger and the
# newly observed, unlinked plan before it may claim the second attempt.
COMPLETION_REPAIR_ADMISSION_GROUP_SCHEMA = (
    "flowguard.completion_repair_admission_group.v1"
)
COMPLETION_AUTHORIZATION_SCHEMA = "flowguard.completion_authorization.v1"

# Completion attempts are scoped independently from the mutable semantic
# objective.  The work id is the caller's stable identity for one maintenance
# unit; it is deliberately not derived from proposal bytes, an output
# directory, a snapshot id, or an epoch id.  Low-level callers that predate
# the public CLI may omit it and use the deterministic legacy sentinel, while
# the public completion entry points require an explicit id.
COMPLETION_MAINTENANCE_UNIT_ID = "unit:flowguard-suite"
COMPLETION_DEFAULT_WORK_ID = "legacy-completion-work"
COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION = "local_validation"
COMPLETION_CLAIM_SCOPE_RELEASE = "release"
COMPLETION_CLAIM_SCOPES = frozenset(
    {
        COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
        COMPLETION_CLAIM_SCOPE_RELEASE,
    }
)

EPOCH_ADMITTED = "admitted"
EPOCH_BLOCKED = "blocked"
EPOCH_FROZEN = "frozen"
EPOCH_TERMINAL_PASS = "terminal_pass"
EPOCH_ABORTED = "aborted"

EPOCH_LEDGER_ABSENT = "absent"
EPOCH_LEDGER_VALID = "valid"
EPOCH_LEDGER_INVALID = "invalid"

CYCLE_OPEN = "open"
CYCLE_REPAIR_REQUIRED = "repair_required"
CYCLE_TERMINAL_PASS = "terminal_pass"
CYCLE_EXHAUSTED = "exhausted"

# Reservation state is deliberately separate from the terminal ledger.  The
# reservation is the durable admission/ownership record written *before* a
# full producer starts; the ledger remains the immutable terminal result.  A
# reservation is never removed, including after an abort, so an interrupted
# or failed producer cannot look like a fresh attempt in a later process.
RESERVATION_ACTIVE = "active"
RESERVATION_SETTLED = "settled"
RESERVATION_ABORTED = "aborted"

RESERVATION_ABSENT = "absent"
RESERVATION_VALID = "valid"
RESERVATION_INVALID = "invalid"

# A completion cycle is deliberately finite.  A second full attempt is only
# available when a typed repair link exists; callers cannot turn a nonce into
# an unbounded retry budget.
MAX_COMPLETION_CYCLE_FULL_ATTEMPTS = 2

_TERMINAL_LEDGER_DIRECTORY = Path(".flowguard") / "evidence" / "completion-epochs"
_RESERVATION_DIRECTORY = _TERMINAL_LEDGER_DIRECTORY / "reservations"
_REPAIR_GROUP_DIRECTORY = (
    Path(".flowguard") / "evidence" / "completion-repair-groups"
)
_AUTHORIZATION_DIRECTORY = (
    Path(".flowguard") / "evidence" / "completion-authorizations"
)
_WINDOWS_DRIVE_ROOT_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


def _normalize_fingerprint(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"completion epoch {field_name} must be a string")
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"completion epoch {field_name} is required")
    return normalized


def _normalize_completion_work_id(value: Any, field_name: str = "completion_work_id") -> str:
    """Normalize the stable work identity without making it a filesystem path."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return COMPLETION_DEFAULT_WORK_ID
    if not isinstance(value, str):
        raise ValueError(f"completion epoch {field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        return COMPLETION_DEFAULT_WORK_ID
    if len(normalized) > 200 or any(
        character in normalized for character in ("/", "\\", "\x00", "\r", "\n", "\t")
    ):
        raise ValueError(
            f"completion epoch {field_name} must be a short non-path identifier"
        )
    return normalized


def _normalize_maintenance_unit_id(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return COMPLETION_MAINTENANCE_UNIT_ID
    if not isinstance(value, str):
        raise ValueError("completion epoch maintenance_unit_id must be a string")
    normalized = value.strip()
    if not normalized:
        return COMPLETION_MAINTENANCE_UNIT_ID
    if len(normalized) > 200 or any(
        character in normalized for character in ("/", "\\", "\x00", "\r", "\n", "\t")
    ):
        raise ValueError(
            "completion epoch maintenance_unit_id must be a short non-path identifier"
        )
    return normalized


def _normalize_claim_scope(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION
    if not isinstance(value, str):
        raise ValueError("completion epoch claim_scope must be a string")
    normalized = value.strip().lower()
    if normalized not in COMPLETION_CLAIM_SCOPES:
        raise ValueError(
            "completion epoch claim_scope must be local_validation or release"
        )
    return normalized


def normalize_completion_work_id(value: Any) -> str:
    """Public normalization for CLI and orchestration boundaries."""

    return _normalize_completion_work_id(value)


def normalize_completion_claim_scope(value: Any) -> str:
    """Public normalization for the local-validation/release claim boundary."""

    return _normalize_claim_scope(value)


def normalize_completion_maintenance_unit_id(value: Any) -> str:
    """Public normalization for the stable completion budget namespace."""

    return _normalize_maintenance_unit_id(value)


def _normalize_epoch_id(value: Any) -> str:
    """Accept only the current content-addressed epoch identity format."""

    normalized = _normalize_fingerprint(value, "epoch_id")
    algorithm, separator, digest = normalized.partition(":")
    if algorithm != "sha256" or not separator or len(digest) != 64:
        raise ValueError("completion epoch id must be a current sha256 fingerprint")
    if digest != digest.lower() or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("completion epoch id must contain a hexadecimal digest")
    return normalized


def _normalize_ids(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, SequenceABC):
        raise ValueError(f"completion epoch {field_name} must be a sequence of ids")
    if any(not isinstance(value, str) for value in values):
        raise ValueError(f"completion epoch {field_name} must contain only strings")
    raw_values = tuple(value.strip() for value in values)
    if any(not value for value in raw_values):
        raise ValueError(f"completion epoch {field_name} cannot contain empty ids")
    if len(set(raw_values)) != len(raw_values):
        raise ValueError(f"completion epoch {field_name} cannot contain duplicate ids")
    return raw_values


def _normalize_fingerprint_map(
    values: Mapping[Any, Any],
    field_name: str,
) -> dict[str, str]:
    """Normalize a small identity map without accepting opaque empty values."""

    if not isinstance(values, MappingABC):
        raise ValueError(f"completion epoch {field_name} must be a mapping")
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f"completion epoch {field_name} must contain only string keys and values")
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key or not normalized_value:
            raise ValueError(f"completion epoch {field_name} cannot contain empty keys or values")
        normalized[normalized_key] = normalized_value
    return dict(sorted(normalized.items()))


def _normalize_int(value: Any, field_name: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    """Accept JSON integer values without coercing strings or booleans."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"completion epoch {field_name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"completion epoch {field_name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"completion epoch {field_name} must be at most {maximum}")
    return value


def _strict_payload_keys(
    payload: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str] = set(),
    context: str,
) -> None:
    """Reject old fields and unknown fields instead of silently downgrading."""

    if not isinstance(payload, Mapping):
        raise ValueError(f"{context} payload must be an object")
    keys = {str(key) for key in payload}
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    if missing:
        raise ValueError(f"{context} payload missing required fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{context} payload contains unsupported fields: {', '.join(unknown)}")


def _canonical_json(payload: Mapping[str, Any] | Sequence[Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class CompletionAuthorization:
    """One explicit, visible authorization for a new same-work repair cycle.

    The work identity remains stable.  A new cycle is admitted only when a
    caller supplies this typed record, whose scope and bounded budget are
    checked against the current completion invocation.  Resource-policy
    changes are deliberately not part of this identity.
    """

    authorization_id: str
    maintenance_unit_id: str
    completion_work_id: str
    claim_scope: str
    scope_fingerprint: str
    total_budget_seconds: int = 7200
    max_full_attempts: int = MAX_COMPLETION_CYCLE_FULL_ATTEMPTS
    reason: str = ""
    issued_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = COMPLETION_AUTHORIZATION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authorization_id",
            _normalize_completion_work_id(self.authorization_id, "authorization_id"),
        )
        object.__setattr__(
            self,
            "maintenance_unit_id",
            _normalize_maintenance_unit_id(self.maintenance_unit_id),
        )
        object.__setattr__(
            self,
            "completion_work_id",
            _normalize_completion_work_id(self.completion_work_id),
        )
        object.__setattr__(self, "claim_scope", _normalize_claim_scope(self.claim_scope))
        object.__setattr__(
            self,
            "scope_fingerprint",
            _normalize_fingerprint(self.scope_fingerprint, "authorization scope_fingerprint"),
        )
        budget = _normalize_int(
            self.total_budget_seconds,
            "authorization total_budget_seconds",
            minimum=1,
            maximum=86400,
        )
        object.__setattr__(self, "total_budget_seconds", budget)
        attempts = _normalize_int(
            self.max_full_attempts,
            "authorization max_full_attempts",
            minimum=1,
            maximum=MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        )
        object.__setattr__(self, "max_full_attempts", attempts)
        reason = self.reason.strip() if isinstance(self.reason, str) else ""
        if not reason:
            raise ValueError("completion authorization reason is required")
        object.__setattr__(self, "reason", reason)
        issued_at = self.issued_at.strip() if isinstance(self.issued_at, str) else ""
        object.__setattr__(
            self,
            "issued_at",
            issued_at or datetime.now(timezone.utc).isoformat(),
        )
        if not isinstance(self.metadata, MappingABC):
            raise ValueError("completion authorization metadata must be an object")
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.schema_version != COMPLETION_AUTHORIZATION_SCHEMA:
            raise ValueError(
                "unsupported completion authorization schema: "
                f"{self.schema_version}"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "authorization_id": self.authorization_id,
            "maintenance_unit_id": self.maintenance_unit_id,
            "completion_work_id": self.completion_work_id,
            "claim_scope": self.claim_scope,
            "scope_fingerprint": self.scope_fingerprint,
            "total_budget_seconds": self.total_budget_seconds,
            "max_full_attempts": self.max_full_attempts,
            "reason": self.reason,
            "issued_at": self.issued_at,
            "metadata": dict(self.metadata),
        }
        if include_fingerprint:
            payload["authorization_fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionAuthorization":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "authorization_id",
                "maintenance_unit_id",
                "completion_work_id",
                "claim_scope",
                "scope_fingerprint",
                "total_budget_seconds",
                "max_full_attempts",
                "reason",
                "issued_at",
                "metadata",
            },
            optional={"authorization_fingerprint"},
            context="completion authorization",
        )
        authorization = cls(
            schema_version=payload["schema_version"],
            authorization_id=payload["authorization_id"],
            maintenance_unit_id=payload["maintenance_unit_id"],
            completion_work_id=payload["completion_work_id"],
            claim_scope=payload["claim_scope"],
            scope_fingerprint=payload["scope_fingerprint"],
            total_budget_seconds=payload["total_budget_seconds"],
            max_full_attempts=payload["max_full_attempts"],
            reason=payload["reason"],
            issued_at=payload["issued_at"],
            metadata=payload["metadata"],
        )
        declared = payload.get("authorization_fingerprint", "")
        if not isinstance(declared, str) or not declared.strip():
            raise ValueError("completion authorization fingerprint is required")
        if declared != authorization.fingerprint:
            raise ValueError("completion authorization fingerprint mismatch")
        return authorization

    def validate_for(
        self,
        *,
        maintenance_unit_id: str,
        completion_work_id: str,
        claim_scope: str,
    ) -> tuple[str, ...]:
        expected = (
            _normalize_maintenance_unit_id(maintenance_unit_id),
            _normalize_completion_work_id(completion_work_id),
            _normalize_claim_scope(claim_scope),
        )
        actual = (self.maintenance_unit_id, self.completion_work_id, self.claim_scope)
        blockers: list[str] = []
        if actual[0] != expected[0]:
            blockers.append("completion_authorization_maintenance_unit_mismatch")
        if actual[1] != expected[1]:
            blockers.append("completion_authorization_work_id_mismatch")
        if actual[2] != expected[2]:
            blockers.append("completion_authorization_claim_scope_mismatch")
        if self.max_full_attempts != MAX_COMPLETION_CYCLE_FULL_ATTEMPTS:
            blockers.append("completion_authorization_attempt_budget_mismatch")
        if self.total_budget_seconds != 7200:
            blockers.append("completion_authorization_total_budget_mismatch")
        return tuple(blockers)

    @classmethod
    def path_for(cls, repository_root: str | Path, fingerprint: str) -> Path:
        normalized = _normalize_fingerprint(fingerprint, "authorization_fingerprint")
        return Path(repository_root).expanduser().resolve() / _AUTHORIZATION_DIRECTORY / (
            "authorization-" + normalized.split(":", 1)[-1] + ".json"
        )

    def write(self, repository_root: str | Path) -> Path:
        path = self.path_for(repository_root, self.fingerprint)
        if path.is_symlink():
            raise ValueError(f"completion authorization path must not be a symlink: {path}")
        encoded = json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_text(encoding="utf-8") != encoded:
                raise ValueError(
                    "completion authorization already exists with different content"
                )
            return path
        path.write_text(encoded, encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "CompletionAuthorization":
        target = Path(path).expanduser().resolve()
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"completion authorization is missing or a symlink: {target}")
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"completion authorization cannot be read: {target}") from exc
        if not isinstance(payload, MappingABC):
            raise ValueError("completion authorization payload must be an object")
        return cls.from_dict(payload)


@dataclass(frozen=True)
class CompletionCycle:
    """Finite state for a completion cycle.

    ``cycle_id`` is derived from ``cycle_seed_fingerprint`` and the fixed
    maximum.  It is therefore an identity for one bounded repair cycle, not a
    caller-controlled nonce.  A cycle can contain at most two full attempts:
    the initial attempt and one typed repair attempt.
    """

    cycle_id: str
    cycle_seed_fingerprint: str
    maximum_full_attempts: int = MAX_COMPLETION_CYCLE_FULL_ATTEMPTS
    consumed_full_attempts: int = 0
    status: str = CYCLE_OPEN
    schema_version: str = COMPLETION_CYCLE_SCHEMA

    def __post_init__(self) -> None:
        seed = _normalize_fingerprint(
            self.cycle_seed_fingerprint,
            "cycle_seed_fingerprint",
        )
        object.__setattr__(self, "cycle_seed_fingerprint", seed)
        maximum = _normalize_int(
            self.maximum_full_attempts,
            "maximum_full_attempts",
            minimum=1,
            maximum=MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        )
        object.__setattr__(self, "maximum_full_attempts", maximum)
        consumed = _normalize_int(
            self.consumed_full_attempts,
            "consumed_full_attempts",
            minimum=0,
            maximum=maximum,
        )
        object.__setattr__(self, "consumed_full_attempts", consumed)
        status = str(self.status).strip()
        if status not in {
            CYCLE_OPEN,
            CYCLE_REPAIR_REQUIRED,
            CYCLE_TERMINAL_PASS,
            CYCLE_EXHAUSTED,
        }:
            raise ValueError(f"unsupported completion cycle status: {status}")
        if status == CYCLE_TERMINAL_PASS and consumed > maximum:
            raise ValueError("terminal completion cycle exceeds its finite budget")
        if status == CYCLE_OPEN and consumed != 0:
            raise ValueError("open completion cycle cannot have consumed attempts")
        if status == CYCLE_REPAIR_REQUIRED and not (0 < consumed < maximum):
            raise ValueError(
                "repair-required completion cycle must have an available attempt"
            )
        if status == CYCLE_EXHAUSTED and consumed != maximum:
            raise ValueError(
                "exhausted completion cycle must consume its entire finite budget"
            )
        if self.schema_version != COMPLETION_CYCLE_SCHEMA:
            raise ValueError(
                f"unsupported completion cycle schema: {self.schema_version}"
            )
        expected = self.derive_id(seed, maximum)
        cycle_id = str(self.cycle_id).strip()
        if not cycle_id:
            cycle_id = expected
        if cycle_id != expected:
            raise ValueError(
                "completion cycle id must be derived from its seed and budget"
            )
        object.__setattr__(self, "cycle_id", cycle_id)

    @staticmethod
    def derive_id(cycle_seed_fingerprint: str, maximum_full_attempts: int) -> str:
        seed = _normalize_fingerprint(
            cycle_seed_fingerprint,
            "cycle_seed_fingerprint",
        )
        maximum = _normalize_int(
            maximum_full_attempts,
            "maximum_full_attempts",
            minimum=1,
            maximum=MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        )
        return fingerprint_value(
            {
                "schema_version": COMPLETION_CYCLE_SCHEMA,
                "cycle_seed_fingerprint": seed,
                "maximum_full_attempts": maximum,
            }
        )

    @property
    def attempt_available(self) -> bool:
        return self.consumed_full_attempts < self.maximum_full_attempts

    def claim(self) -> "CompletionCycle":
        if self.status == CYCLE_TERMINAL_PASS:
            raise RuntimeError("terminal completion cycle cannot claim another attempt")
        if not self.attempt_available:
            raise RuntimeError("completion cycle full attempt budget exhausted")
        consumed = self.consumed_full_attempts + 1
        status = (
            CYCLE_EXHAUSTED
            if consumed == self.maximum_full_attempts
            else CYCLE_REPAIR_REQUIRED
        )
        return replace(
            self,
            consumed_full_attempts=consumed,
            status=status,
        )

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "cycle_id": self.cycle_id,
            "cycle_seed_fingerprint": self.cycle_seed_fingerprint,
            "maximum_full_attempts": self.maximum_full_attempts,
            "consumed_full_attempts": self.consumed_full_attempts,
            "status": self.status,
        }
        if include_fingerprint:
            payload["cycle_fingerprint"] = fingerprint_value(payload)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionCycle":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "cycle_id",
                "cycle_seed_fingerprint",
                "maximum_full_attempts",
                "consumed_full_attempts",
                "status",
            },
            optional={"cycle_fingerprint"},
            context="completion cycle",
        )
        cycle = cls(
            cycle_id=str(payload["cycle_id"]),
            cycle_seed_fingerprint=str(payload["cycle_seed_fingerprint"]),
            maximum_full_attempts=payload["maximum_full_attempts"],
            consumed_full_attempts=payload["consumed_full_attempts"],
            status=str(payload["status"]),
            schema_version=str(payload["schema_version"]),
        )
        declared = str(payload.get("cycle_fingerprint", "")).strip()
        if not declared:
            raise ValueError("completion cycle fingerprint is required")
        expected = fingerprint_value(cycle.to_dict(include_fingerprint=False))
        if declared != expected:
            raise ValueError("completion cycle fingerprint mismatch")
        return cycle


@dataclass(frozen=True)
class CompletionRepairLink:
    """Typed proof that a second attempt repairs a specific failed epoch."""

    completion_cycle_id: str
    previous_epoch_id: str
    previous_attempt_index: int
    repair_group_id: str
    failed_owner_ids: tuple[str, ...]
    repair_receipt_fingerprint: str
    changed_input_fingerprints: Mapping[str, str]
    schema_version: str = COMPLETION_REPAIR_LINK_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "completion_cycle_id",
            _normalize_epoch_id(self.completion_cycle_id),
        )
        object.__setattr__(
            self,
            "previous_epoch_id",
            _normalize_epoch_id(self.previous_epoch_id),
        )
        previous_attempt = _normalize_int(
            self.previous_attempt_index,
            "previous_attempt_index",
            minimum=0,
        )
        object.__setattr__(self, "previous_attempt_index", previous_attempt)
        object.__setattr__(
            self,
            "repair_group_id",
            _normalize_fingerprint(self.repair_group_id, "repair_group_id"),
        )
        failed_owner_ids = _normalize_ids(
            self.failed_owner_ids,
            "failed_owner_ids",
        )
        if not failed_owner_ids:
            raise ValueError("completion repair requires at least one failed owner")
        object.__setattr__(self, "failed_owner_ids", failed_owner_ids)
        object.__setattr__(
            self,
            "repair_receipt_fingerprint",
            _normalize_fingerprint(
                self.repair_receipt_fingerprint,
                "repair_receipt_fingerprint",
            ),
        )
        changed = _normalize_fingerprint_map(
            self.changed_input_fingerprints,
            "changed_input_fingerprints",
        )
        allowed = {
            "source_observation_fingerprint",
            "release_tree_fingerprint",
            "toolchain_environment_fingerprint",
            "owner_dag_fingerprint",
            "model_authority_fingerprint",
            "test_inventory_fingerprint",
            "completion_objective_fingerprint",
        }
        unknown = sorted(set(changed) - allowed)
        if unknown:
            raise ValueError(
                "completion repair changed_input_fingerprints contains unsupported "
                f"fields: {', '.join(unknown)}"
            )
        if not changed:
            raise ValueError(
                "completion repair requires at least one changed input fingerprint"
            )
        object.__setattr__(self, "changed_input_fingerprints", changed)
        if self.schema_version != COMPLETION_REPAIR_LINK_SCHEMA:
            raise ValueError(
                f"unsupported completion repair link schema: {self.schema_version}"
            )

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "completion_cycle_id": self.completion_cycle_id,
            "previous_epoch_id": self.previous_epoch_id,
            "previous_attempt_index": self.previous_attempt_index,
            "repair_group_id": self.repair_group_id,
            "failed_owner_ids": list(self.failed_owner_ids),
            "repair_receipt_fingerprint": self.repair_receipt_fingerprint,
            "changed_input_fingerprints": dict(self.changed_input_fingerprints),
        }
        if include_fingerprint:
            payload["repair_link_fingerprint"] = fingerprint_value(payload)
        return payload

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionRepairLink":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "completion_cycle_id",
                "previous_epoch_id",
                "previous_attempt_index",
                "repair_group_id",
                "failed_owner_ids",
                "repair_receipt_fingerprint",
                "changed_input_fingerprints",
            },
            optional={"repair_link_fingerprint"},
            context="completion repair link",
        )
        link = cls(
            completion_cycle_id=payload["completion_cycle_id"],
            previous_epoch_id=payload["previous_epoch_id"],
            previous_attempt_index=payload["previous_attempt_index"],
            repair_group_id=payload["repair_group_id"],
            failed_owner_ids=payload["failed_owner_ids"],
            repair_receipt_fingerprint=payload["repair_receipt_fingerprint"],
            changed_input_fingerprints=payload["changed_input_fingerprints"],
            schema_version=payload["schema_version"],
        )
        declared = payload.get("repair_link_fingerprint", "")
        if not isinstance(declared, str) or not declared.strip():
            raise ValueError("completion repair link fingerprint is required")
        if declared != link.fingerprint:
            raise ValueError("completion repair link fingerprint mismatch")
        return link

    def validate_for(
        self,
        previous_plan: "CompletionEpochPlan",
        current_plan: "CompletionEpochPlan",
        *,
        previous_ledger: "CompletionEpochTerminalLedger | None" = None,
    ) -> tuple[str, ...]:
        """Return blockers instead of treating an unproven repair as valid."""

        blockers: list[str] = []
        if previous_plan.epoch_id != self.previous_epoch_id:
            blockers.append("repair_previous_epoch_identity_mismatch")
        if previous_plan.full_producer_attempts != 1:
            blockers.append("repair_previous_epoch_was_not_claimed")
        if previous_ledger is None:
            blockers.append("repair_previous_terminal_ledger_missing")
        elif previous_ledger.epoch_id != previous_plan.epoch_id:
            blockers.append("repair_previous_terminal_ledger_identity_mismatch")
        elif previous_ledger.status != EPOCH_ABORTED:
            blockers.append("repair_previous_terminal_ledger_not_aborted")
        elif any(
            getattr(previous_ledger, field_name) != getattr(previous_plan, field_name)
            for field_name in (
                "source_observation_fingerprint",
                "release_tree_fingerprint",
                "toolchain_environment_fingerprint",
                "owner_dag_fingerprint",
                "fixed_owner_dag_fingerprint",
                "model_authority_fingerprint",
                "model_authority_head_fingerprint",
                "model_authority_snapshot_fingerprint",
                "test_inventory_fingerprint",
                "completion_objective_fingerprint",
                "completion_authorization_fingerprint",
                "completion_cycle_seed_fingerprint",
                "completion_cycle_id",
                "completion_cycle_max_attempts",
                "attempt_index",
                "full_producer_attempts",
                "maintenance_unit_id",
                "completion_work_id",
                "claim_scope",
            )
        ):
            blockers.append("repair_previous_terminal_ledger_plan_mismatch")
        elif tuple(previous_ledger.terminal_action_ids) != tuple(
            previous_plan.required_terminal_action_ids
        ):
            blockers.append("repair_previous_terminal_ledger_actions_mismatch")
        if current_plan.completion_cycle_id != self.completion_cycle_id:
            blockers.append("repair_completion_cycle_mismatch")
        if current_plan.maintenance_unit_id != previous_plan.maintenance_unit_id:
            blockers.append("repair_maintenance_unit_mismatch")
        if current_plan.completion_work_id != previous_plan.completion_work_id:
            blockers.append("repair_work_id_mismatch")
        if current_plan.claim_scope != previous_plan.claim_scope:
            blockers.append("repair_claim_scope_mismatch")
        if current_plan.attempt_index != self.previous_attempt_index + 1:
            blockers.append("repair_attempt_index_not_sequential")
        if current_plan.attempt_index >= current_plan.completion_cycle_max_attempts:
            blockers.append("repair_completion_cycle_budget_exhausted")
        if current_plan.epoch_id == self.previous_epoch_id:
            blockers.append("repair_did_not_create_new_epoch_identity")
        values = {
            "source_observation_fingerprint": current_plan.source_observation_fingerprint,
            "release_tree_fingerprint": current_plan.release_tree_fingerprint,
            "toolchain_environment_fingerprint": current_plan.toolchain_environment_fingerprint,
            "owner_dag_fingerprint": current_plan.owner_dag_fingerprint,
            "model_authority_fingerprint": current_plan.model_authority_fingerprint,
            "test_inventory_fingerprint": current_plan.test_inventory_fingerprint,
            "completion_objective_fingerprint": current_plan.completion_objective_fingerprint,
        }
        previous_values = {
            key: getattr(previous_plan, key)
            for key in values
        }
        actual_changed_keys = {
            key
            for key, fingerprint in values.items()
            if fingerprint != previous_values[key]
        }
        declared_changed_keys = set(self.changed_input_fingerprints)
        for key in sorted(actual_changed_keys - declared_changed_keys):
            blockers.append(f"repair_changed_input_undeclared:{key}")
        for key in sorted(declared_changed_keys - actual_changed_keys):
            blockers.append(f"repair_changed_input_not_changed:{key}")
        for key, fingerprint in self.changed_input_fingerprints.items():
            if values.get(key) != fingerprint:
                blockers.append(f"repair_current_input_fingerprint_mismatch:{key}")
        if not actual_changed_keys:
            blockers.append("repair_has_no_changed_governed_input")
        return tuple(dict.fromkeys(blockers))


def _normalize_json_object(value: Any, field_name: str) -> dict[str, Any]:
    """Return a deterministic JSON object for a typed repair sidecar.

    Repair admission is deliberately a data boundary.  Do not retain caller
    objects (or silently stringify arbitrary Python values) in the canonical
    group because doing so would make the content-addressed identity depend on
    process-local representations.
    """

    def normalize(item: Any, context: str) -> Any:
        if isinstance(item, MappingABC):
            result: dict[str, Any] = {}
            for key, child in item.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(f"completion repair {context} keys must be non-empty strings")
                result[key.strip()] = normalize(child, f"{context}.{key.strip()}")
            return dict(sorted(result.items()))
        if isinstance(item, (list, tuple)):
            return [normalize(child, f"{context}[]") for child in item]
        if isinstance(item, (str, int, float, bool)) or item is None:
            return item
        raise ValueError(f"completion repair {context} contains a non-JSON value")

    normalized = normalize(value, field_name)
    if not isinstance(normalized, dict):
        raise ValueError(f"completion repair {field_name} must be an object")
    return normalized


@dataclass(frozen=True)
class CompletionRepairAdmissionGroup:
    """Canonical, predecessor-bound admission facts for one repair attempt.

    This is intentionally not a terminal receipt.  ``producer_invocations``
    is fixed at zero and the targeted regression section only proves that the
    repair admission inputs were checked.  The full producer still has to
    execute (or prove an independently verified exact-current parent reuse)
    and write the normal terminal ledger.
    """

    repair_kind: str
    completion_cycle_id: str
    previous_epoch_id: str
    previous_attempt_index: int
    previous_full_producer_attempts: int
    previous_ledger_fingerprint: str
    current_unlinked_epoch_id: str
    current_plan_input_fingerprint: str
    current_input_fingerprints: Mapping[str, str]
    changed_input_fingerprints: Mapping[str, str]
    required_terminal_action_ids: tuple[str, ...]
    completed_terminal_action_ids: tuple[str, ...]
    failed_owner_ids: tuple[str, ...]
    reexecute_owner_ids: tuple[str, ...]
    owner_dispositions: Mapping[str, Any]
    targeted_regression_evidence: Mapping[str, Any]
    producer_invocations: int = 0
    schema_version: str = COMPLETION_REPAIR_ADMISSION_GROUP_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != COMPLETION_REPAIR_ADMISSION_GROUP_SCHEMA:
            raise ValueError(
                "unsupported completion repair admission group schema: "
                + str(self.schema_version)
            )
        if self.repair_kind != "attempt_admission":
            raise ValueError("completion repair admission group kind must be attempt_admission")
        for field_name in (
            "completion_cycle_id",
            "previous_epoch_id",
            "current_unlinked_epoch_id",
            "current_plan_input_fingerprint",
            "previous_ledger_fingerprint",
        ):
            if field_name.endswith("epoch_id") or field_name == "completion_cycle_id":
                value = _normalize_epoch_id(getattr(self, field_name))
            else:
                value = _normalize_fingerprint(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "previous_attempt_index",
            _normalize_int(self.previous_attempt_index, "previous_attempt_index", minimum=0),
        )
        object.__setattr__(
            self,
            "previous_full_producer_attempts",
            _normalize_int(
                self.previous_full_producer_attempts,
                "previous_full_producer_attempts",
                minimum=0,
                maximum=1,
            ),
        )
        if self.previous_full_producer_attempts != 1:
            raise ValueError("repair admission predecessor must record one producer attempt")
        object.__setattr__(
            self,
            "producer_invocations",
            _normalize_int(self.producer_invocations, "producer_invocations", minimum=0),
        )
        if self.producer_invocations != 0:
            raise ValueError("repair admission group must have zero producer invocations")
        for field_name in (
            "current_input_fingerprints",
            "changed_input_fingerprints",
        ):
            values = _normalize_fingerprint_map(getattr(self, field_name), field_name)
            if field_name == "changed_input_fingerprints":
                unknown = sorted(set(values) - set(_REPAIR_INPUT_FIELDS))
                if unknown:
                    raise ValueError(
                        "repair admission changed inputs contain unsupported fields: "
                        + ", ".join(unknown)
                    )
            object.__setattr__(self, field_name, values)
        for field_name in (
            "required_terminal_action_ids",
            "completed_terminal_action_ids",
            "failed_owner_ids",
            "reexecute_owner_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_ids(getattr(self, field_name), field_name),
            )
        required = set(self.required_terminal_action_ids)
        completed = set(self.completed_terminal_action_ids)
        failed = set(self.failed_owner_ids)
        reexecute = set(self.reexecute_owner_ids)
        if not completed.issubset(required):
            raise ValueError("repair admission completed actions contain foreign ids")
        if failed != required - completed:
            raise ValueError("repair admission failed owners do not match predecessor action set")
        if not reexecute.issubset(failed):
            raise ValueError("repair admission reexecute owners contain non-failed ids")
        dispositions = _normalize_json_object(
            self.owner_dispositions,
            "owner_dispositions",
        )
        if set(dispositions) != required:
            raise ValueError(
                "repair admission owner dispositions must cover required actions exactly"
            )
        for owner_id in failed:
            value = dispositions[owner_id]
            if isinstance(value, MappingABC):
                value = value.get("disposition", "")
            if str(value).strip().lower() in {"reuse", "reuse_current"}:
                raise ValueError(
                    "repair admission failed owner cannot be marked reuse_current: "
                    + owner_id
                )
        for owner_id in completed:
            value = dispositions[owner_id]
            if isinstance(value, MappingABC):
                value = value.get("disposition", "")
            if str(value).strip().lower() in {"execute", "reexecute"}:
                raise ValueError(
                    "repair admission completed owner cannot be marked reexecute: "
                    + owner_id
                )
        object.__setattr__(self, "owner_dispositions", dispositions)
        object.__setattr__(
            self,
            "targeted_regression_evidence",
            _normalize_json_object(
                self.targeted_regression_evidence,
                "targeted_regression_evidence",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repair_kind": self.repair_kind,
            "completion_cycle_id": self.completion_cycle_id,
            "previous_epoch_id": self.previous_epoch_id,
            "previous_attempt_index": self.previous_attempt_index,
            "previous_full_producer_attempts": self.previous_full_producer_attempts,
            "previous_ledger_fingerprint": self.previous_ledger_fingerprint,
            "current_unlinked_epoch_id": self.current_unlinked_epoch_id,
            "current_plan_input_fingerprint": self.current_plan_input_fingerprint,
            "current_input_fingerprints": dict(self.current_input_fingerprints),
            "changed_input_fingerprints": dict(self.changed_input_fingerprints),
            "required_terminal_action_ids": list(self.required_terminal_action_ids),
            "completed_terminal_action_ids": list(self.completed_terminal_action_ids),
            "failed_owner_ids": list(self.failed_owner_ids),
            "reexecute_owner_ids": list(self.reexecute_owner_ids),
            "owner_dispositions": dict(self.owner_dispositions),
            "targeted_regression_evidence": dict(self.targeted_regression_evidence),
            "producer_invocations": self.producer_invocations,
        }

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionRepairAdmissionGroup":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "repair_kind",
                "completion_cycle_id",
                "previous_epoch_id",
                "previous_attempt_index",
                "previous_full_producer_attempts",
                "previous_ledger_fingerprint",
                "current_unlinked_epoch_id",
                "current_plan_input_fingerprint",
                "current_input_fingerprints",
                "changed_input_fingerprints",
                "required_terminal_action_ids",
                "completed_terminal_action_ids",
                "failed_owner_ids",
                "reexecute_owner_ids",
                "owner_dispositions",
                "targeted_regression_evidence",
                "producer_invocations",
            },
            context="completion repair admission group",
        )
        return cls(
            schema_version=payload["schema_version"],
            repair_kind=payload["repair_kind"],
            completion_cycle_id=payload["completion_cycle_id"],
            previous_epoch_id=payload["previous_epoch_id"],
            previous_attempt_index=payload["previous_attempt_index"],
            previous_full_producer_attempts=payload["previous_full_producer_attempts"],
            previous_ledger_fingerprint=payload["previous_ledger_fingerprint"],
            current_unlinked_epoch_id=payload["current_unlinked_epoch_id"],
            current_plan_input_fingerprint=payload["current_plan_input_fingerprint"],
            current_input_fingerprints=payload["current_input_fingerprints"],
            changed_input_fingerprints=payload["changed_input_fingerprints"],
            required_terminal_action_ids=payload["required_terminal_action_ids"],
            completed_terminal_action_ids=payload["completed_terminal_action_ids"],
            failed_owner_ids=payload["failed_owner_ids"],
            reexecute_owner_ids=payload["reexecute_owner_ids"],
            owner_dispositions=payload["owner_dispositions"],
            targeted_regression_evidence=payload["targeted_regression_evidence"],
            producer_invocations=payload["producer_invocations"],
        )

    @classmethod
    def path_for(cls, repository_root: str | Path, group_id: str) -> Path:
        normalized = _normalize_fingerprint(group_id, "repair_group_id")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", normalized):
            raise ValueError("repair admission group id must be a sha256 fingerprint")
        root = Path(repository_root).expanduser().resolve()
        return root / _REPAIR_GROUP_DIRECTORY / (normalized.split(":", 1)[1] + ".json")


def load_completion_repair_admission_group(
    link: CompletionRepairLink,
    repository_root: str | Path,
    *,
    previous_ledger: "CompletionEpochTerminalLedger | None" = None,
    current_plan: "CompletionEpochPlan | None" = None,
) -> CompletionRepairAdmissionGroup:
    """Reload and bind the canonical repair group named by ``link``.

    The path supplied by a caller is never used here.  This prevents a
    copied/foreign sidecar from turning a valid-looking link into a second
    attempt.  The optional ledger and plan bindings are checked by the full
    consumer after it reconstructs both identities.
    """

    if not isinstance(link, CompletionRepairLink):
        raise TypeError("completion repair admission group requires a typed repair link")
    path = CompletionRepairAdmissionGroup.path_for(repository_root, link.repair_group_id)
    root = Path(repository_root).expanduser().resolve()
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError(
                "completion repair admission group path components must not be symlinks"
            )
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    if not path.exists():
        raise FileNotFoundError(f"completion repair admission group is missing: {path}")
    if root not in path.parents:
        raise ValueError("completion repair admission group escaped repository root")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"completion repair admission group is unreadable: {path}") from exc
    group = CompletionRepairAdmissionGroup.from_dict(payload)
    if group.fingerprint != link.repair_group_id:
        raise ValueError("completion repair admission group fingerprint does not match its address")
    if link.repair_receipt_fingerprint != group.fingerprint:
        raise ValueError("completion repair link does not bind the admission group fingerprint")
    if group.completion_cycle_id != link.completion_cycle_id:
        raise ValueError("completion repair admission group cycle mismatch")
    if group.previous_epoch_id != link.previous_epoch_id:
        raise ValueError("completion repair admission group predecessor mismatch")
    if group.previous_attempt_index != link.previous_attempt_index:
        raise ValueError("completion repair admission group attempt mismatch")
    if tuple(group.failed_owner_ids) != tuple(link.failed_owner_ids):
        raise ValueError("completion repair admission group failed-owner mismatch")
    if dict(group.changed_input_fingerprints) != dict(link.changed_input_fingerprints):
        raise ValueError("completion repair admission group changed-input mismatch")
    if previous_ledger is not None:
        if group.previous_ledger_fingerprint != previous_ledger.fingerprint:
            raise ValueError("completion repair admission group ledger mismatch")
        if group.previous_epoch_id != previous_ledger.epoch_id:
            raise ValueError("completion repair admission group ledger identity mismatch")
        if group.previous_attempt_index != previous_ledger.attempt_index:
            raise ValueError("completion repair admission group ledger attempt mismatch")
        if group.previous_full_producer_attempts != previous_ledger.full_producer_attempts:
            raise ValueError("completion repair admission group producer-count mismatch")
        if tuple(group.required_terminal_action_ids) != tuple(previous_ledger.terminal_action_ids):
            raise ValueError("completion repair admission group required-action mismatch")
        if tuple(group.completed_terminal_action_ids) != tuple(previous_ledger.completed_terminal_action_ids):
            raise ValueError("completion repair admission group completed-action mismatch")
    if current_plan is not None:
        current_values = {
            field_name: getattr(current_plan, field_name)
            for field_name in _REPAIR_INPUT_FIELDS
        }
        if group.current_unlinked_epoch_id != current_plan.epoch_id:
            raise ValueError("completion repair admission group current epoch mismatch")
        if group.current_plan_input_fingerprint != current_plan.epoch_id:
            raise ValueError("completion repair admission group current plan fingerprint mismatch")
        if dict(group.current_input_fingerprints) != current_values:
            raise ValueError("completion repair admission group current-input mismatch")
        if current_plan.attempt_index != 0 or current_plan.full_producer_attempts != 0:
            raise ValueError("completion repair admission group requires an unclaimed current plan")
        if current_plan.repair_link is not None:
            raise ValueError("completion repair admission group current plan already has a link")
        if tuple(group.required_terminal_action_ids) != tuple(current_plan.required_terminal_action_ids):
            raise ValueError("completion repair admission group current action mismatch")
    regression = group.targeted_regression_evidence
    scope = str(regression.get("scope", "")).strip().lower()
    if scope not in {"patch_regression", "targeted_patch_regression"}:
        raise ValueError("completion repair admission group regression scope is not patch_regression")
    if "status" not in regression:
        raise ValueError("completion repair admission group regression status is missing")
    status = str(regression.get("status", "")).strip().lower()
    if status not in {"pass", "passed", "success"}:
        raise ValueError("completion repair admission group regression is not a pass")
    if regression.get("exit_code", 0) != 0:
        raise ValueError("completion repair admission group regression exit code is not zero")
    if regression.get("cleanup_confirmed", True) is not True:
        raise ValueError("completion repair admission group regression cleanup is not confirmed")
    if regression.get("skipped", False) is True:
        raise ValueError("completion repair admission group regression is skipped")
    if regression.get("tested_input_manifest", regression.get("input_fingerprint")) in (
        None,
        "",
        [],
        {},
    ):
        raise ValueError("completion repair admission group regression has no tested input binding")
    return group


@dataclass(frozen=True)
class CompletionEpochReadiness:
    """Positive, current-only evidence required before full admission.

    This object describes what the frozen parent *must* cover.  It does not
    assert that any child has completed.  Completion is a terminal producer
    output and is derived from verified child evidence after the full run.
    """

    epoch_id: str
    completion_cycle_id: str
    source_observation_fingerprint: str
    release_tree_fingerprint: str
    toolchain_environment_fingerprint: str
    owner_dag_fingerprint: str
    model_authority_fingerprint: str
    test_inventory_fingerprint: str
    openspec_terminal_receipt_fingerprint: str
    external_roots_sync_receipt_fingerprint: str
    formal_shadow_installed_sync_receipt_fingerprint: str
    reverse_input_acceptance_receipt_fingerprint: str
    owner_dag_freeze_receipt_fingerprint: str
    required_terminal_action_ids: tuple[str, ...]
    completion_authorization_fingerprint: str = ""
    remaining_governed_write_ids: tuple[str, ...] = ()
    previous_aborted_epoch_id: str = ""
    previous_aborted_epoch_ledger_fingerprint: str = ""
    repair_link_fingerprint: str = ""
    schema_version: str = COMPLETION_EPOCH_READINESS_SCHEMA
    maintenance_unit_id: str = COMPLETION_MAINTENANCE_UNIT_ID
    completion_work_id: str = COMPLETION_DEFAULT_WORK_ID
    claim_scope: str = COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION

    def __post_init__(self) -> None:
        for field_name in (
            "source_observation_fingerprint",
            "release_tree_fingerprint",
            "toolchain_environment_fingerprint",
            "owner_dag_fingerprint",
            "model_authority_fingerprint",
            "test_inventory_fingerprint",
            "openspec_terminal_receipt_fingerprint",
            "external_roots_sync_receipt_fingerprint",
            "formal_shadow_installed_sync_receipt_fingerprint",
            "reverse_input_acceptance_receipt_fingerprint",
            "owner_dag_freeze_receipt_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_fingerprint(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "completion_cycle_id", _normalize_epoch_id(self.completion_cycle_id))
        object.__setattr__(self, "epoch_id", _normalize_epoch_id(self.epoch_id))
        authorization = self.completion_authorization_fingerprint
        if not isinstance(authorization, str):
            raise ValueError(
                "completion epoch readiness completion_authorization_fingerprint must be a string"
            )
        authorization = authorization.strip()
        if authorization:
            authorization = _normalize_fingerprint(
                authorization,
                "completion_authorization_fingerprint",
            )
        object.__setattr__(self, "completion_authorization_fingerprint", authorization)
        object.__setattr__(
            self,
            "maintenance_unit_id",
            _normalize_maintenance_unit_id(self.maintenance_unit_id),
        )
        object.__setattr__(
            self,
            "completion_work_id",
            _normalize_completion_work_id(self.completion_work_id),
        )
        object.__setattr__(self, "claim_scope", _normalize_claim_scope(self.claim_scope))
        object.__setattr__(
            self,
            "required_terminal_action_ids",
            _normalize_ids(
                self.required_terminal_action_ids,
                "required_terminal_action_ids",
            ),
        )
        object.__setattr__(
            self,
            "remaining_governed_write_ids",
            _normalize_ids(
                self.remaining_governed_write_ids,
                "remaining_governed_write_ids",
            ),
        )
        previous_epoch_id = self.previous_aborted_epoch_id
        if not isinstance(previous_epoch_id, str):
            raise ValueError(
                "completion epoch readiness previous_aborted_epoch_id must be a string"
            )
        previous_epoch_id = previous_epoch_id.strip()
        if previous_epoch_id:
            previous_epoch_id = _normalize_epoch_id(previous_epoch_id)
        object.__setattr__(self, "previous_aborted_epoch_id", previous_epoch_id)
        for field_name in (
            "previous_aborted_epoch_ledger_fingerprint",
            "repair_link_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"completion epoch readiness {field_name} must be a string")
            value = value.strip()
            if value:
                value = _normalize_fingerprint(value, field_name)
            object.__setattr__(self, field_name, value)
        if self.schema_version != COMPLETION_EPOCH_READINESS_SCHEMA:
            raise ValueError(
                f"unsupported completion epoch readiness schema: {self.schema_version}"
            )

    @classmethod
    def for_plan(
        cls,
        plan: "CompletionEpochPlan",
        *,
        openspec_terminal_receipt_fingerprint: str,
        external_roots_sync_receipt_fingerprint: str,
        formal_shadow_installed_sync_receipt_fingerprint: str,
        reverse_input_acceptance_receipt_fingerprint: str,
        owner_dag_freeze_receipt_fingerprint: str,
        required_terminal_action_ids: Sequence[str] | None = None,
        previous_aborted_epoch_ledger_fingerprint: str = "",
    ) -> "CompletionEpochReadiness":
        return cls(
            epoch_id=plan.epoch_id,
            completion_cycle_id=plan.completion_cycle_id,
            completion_authorization_fingerprint=plan.completion_authorization_fingerprint,
            maintenance_unit_id=plan.maintenance_unit_id,
            completion_work_id=plan.completion_work_id,
            claim_scope=plan.claim_scope,
            source_observation_fingerprint=plan.source_observation_fingerprint,
            release_tree_fingerprint=plan.release_tree_fingerprint,
            toolchain_environment_fingerprint=plan.toolchain_environment_fingerprint,
            owner_dag_fingerprint=plan.owner_dag_fingerprint,
            model_authority_fingerprint=plan.model_authority_fingerprint,
            test_inventory_fingerprint=plan.test_inventory_fingerprint,
            openspec_terminal_receipt_fingerprint=openspec_terminal_receipt_fingerprint,
            external_roots_sync_receipt_fingerprint=external_roots_sync_receipt_fingerprint,
            formal_shadow_installed_sync_receipt_fingerprint=formal_shadow_installed_sync_receipt_fingerprint,
            reverse_input_acceptance_receipt_fingerprint=reverse_input_acceptance_receipt_fingerprint,
            owner_dag_freeze_receipt_fingerprint=owner_dag_freeze_receipt_fingerprint,
            required_terminal_action_ids=(
                plan.required_terminal_action_ids
                if required_terminal_action_ids is None
                else tuple(required_terminal_action_ids)
            ),
            remaining_governed_write_ids=plan.remaining_governed_write_ids,
            previous_aborted_epoch_id=(
                plan.repair_link.previous_epoch_id
                if plan.repair_link is not None
                else ""
            ),
            previous_aborted_epoch_ledger_fingerprint=(
                previous_aborted_epoch_ledger_fingerprint
            ),
            repair_link_fingerprint=(
                plan.repair_link.fingerprint
                if plan.repair_link is not None
                else ""
            ),
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def validate_for(self, plan: "CompletionEpochPlan") -> tuple[str, ...]:
        blockers: list[str] = []
        expected = {
            "epoch_id": plan.epoch_id,
            "completion_cycle_id": plan.completion_cycle_id,
            "completion_authorization_fingerprint": plan.completion_authorization_fingerprint,
            "maintenance_unit_id": plan.maintenance_unit_id,
            "completion_work_id": plan.completion_work_id,
            "claim_scope": plan.claim_scope,
            "source_observation_fingerprint": plan.source_observation_fingerprint,
            "release_tree_fingerprint": plan.release_tree_fingerprint,
            "toolchain_environment_fingerprint": plan.toolchain_environment_fingerprint,
            "owner_dag_fingerprint": plan.owner_dag_fingerprint,
            "model_authority_fingerprint": plan.model_authority_fingerprint,
            "test_inventory_fingerprint": plan.test_inventory_fingerprint,
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                blockers.append(f"completion_readiness_{field_name}_mismatch")
        if self.remaining_governed_write_ids:
            blockers.append("completion_readiness_remaining_governed_writes")
        if tuple(self.remaining_governed_write_ids) != tuple(
            plan.remaining_governed_write_ids
        ):
            blockers.append("completion_readiness_remaining_governed_writes_mismatch")
        if tuple(self.required_terminal_action_ids) != tuple(
            plan.required_terminal_action_ids
        ):
            blockers.append("completion_readiness_required_terminal_actions_mismatch")
        if plan.attempt_index > 0:
            if plan.repair_link is None:
                blockers.append("completion_readiness_repair_link_missing")
            else:
                if self.previous_aborted_epoch_id != plan.repair_link.previous_epoch_id:
                    blockers.append(
                        "completion_readiness_previous_aborted_epoch_id_mismatch"
                    )
                if not self.previous_aborted_epoch_ledger_fingerprint:
                    blockers.append(
                        "completion_readiness_previous_aborted_epoch_ledger_missing"
                    )
                if self.repair_link_fingerprint != plan.repair_link.fingerprint:
                    blockers.append("completion_readiness_repair_link_mismatch")
        elif (
            self.previous_aborted_epoch_id
            or self.previous_aborted_epoch_ledger_fingerprint
            or self.repair_link_fingerprint
        ):
            blockers.append("completion_readiness_unexpected_repair_context")
        return tuple(dict.fromkeys(blockers))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "epoch_id": self.epoch_id,
            "completion_cycle_id": self.completion_cycle_id,
            "maintenance_unit_id": self.maintenance_unit_id,
            "completion_work_id": self.completion_work_id,
            "claim_scope": self.claim_scope,
            "source_observation_fingerprint": self.source_observation_fingerprint,
            "release_tree_fingerprint": self.release_tree_fingerprint,
            "toolchain_environment_fingerprint": self.toolchain_environment_fingerprint,
            "owner_dag_fingerprint": self.owner_dag_fingerprint,
            "model_authority_fingerprint": self.model_authority_fingerprint,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "openspec_terminal_receipt_fingerprint": self.openspec_terminal_receipt_fingerprint,
            "external_roots_sync_receipt_fingerprint": self.external_roots_sync_receipt_fingerprint,
            "formal_shadow_installed_sync_receipt_fingerprint": self.formal_shadow_installed_sync_receipt_fingerprint,
            "reverse_input_acceptance_receipt_fingerprint": self.reverse_input_acceptance_receipt_fingerprint,
            "owner_dag_freeze_receipt_fingerprint": self.owner_dag_freeze_receipt_fingerprint,
            "required_terminal_action_ids": list(self.required_terminal_action_ids),
            "remaining_governed_write_ids": list(self.remaining_governed_write_ids),
            "previous_aborted_epoch_id": self.previous_aborted_epoch_id,
            "previous_aborted_epoch_ledger_fingerprint": self.previous_aborted_epoch_ledger_fingerprint,
            "repair_link_fingerprint": self.repair_link_fingerprint,
        }
        if self.completion_authorization_fingerprint:
            payload[
                "completion_authorization_fingerprint"
            ] = self.completion_authorization_fingerprint
        if include_fingerprint:
            payload["readiness_fingerprint"] = fingerprint_value(payload)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionEpochReadiness":
        required = {
            "schema_version",
            "epoch_id",
            "completion_cycle_id",
            "maintenance_unit_id",
            "completion_work_id",
            "claim_scope",
            "source_observation_fingerprint",
            "release_tree_fingerprint",
            "toolchain_environment_fingerprint",
            "owner_dag_fingerprint",
            "model_authority_fingerprint",
            "test_inventory_fingerprint",
            "openspec_terminal_receipt_fingerprint",
            "external_roots_sync_receipt_fingerprint",
            "formal_shadow_installed_sync_receipt_fingerprint",
            "reverse_input_acceptance_receipt_fingerprint",
            "owner_dag_freeze_receipt_fingerprint",
            "required_terminal_action_ids",
            "remaining_governed_write_ids",
            "previous_aborted_epoch_id",
            "previous_aborted_epoch_ledger_fingerprint",
            "repair_link_fingerprint",
        }
        _strict_payload_keys(
            payload,
            required=required,
            optional={"readiness_fingerprint", "completion_authorization_fingerprint"},
            context="completion epoch readiness",
        )
        readiness = cls(
            **{
                key: payload[key]
                for key in required
                if key != "schema_version"
            },
            completion_authorization_fingerprint=str(
                payload.get("completion_authorization_fingerprint", "")
            ),
            schema_version=payload["schema_version"],
        )
        declared = payload.get("readiness_fingerprint", "")
        if not isinstance(declared, str) or not declared.strip():
            raise ValueError("completion epoch readiness fingerprint is required")
        if declared != readiness.fingerprint:
            raise ValueError("completion epoch readiness fingerprint mismatch")
        return readiness


@dataclass(frozen=True)
class CompletionEpochPlan:
    """The immutable identity of one possible terminal validation epoch.

    The fields are intentionally all explicit.  The plan may be created while
    source work is still mutable, but final admission is blocked until its
    ``remaining_governed_write_ids`` is empty and all other admission facts are
    true.  ``full_producer_attempts`` is execution state, not a source input;
    it is kept on the immutable value so callers can obtain a new value after
    claiming the one allowed attempt without mutating an existing plan.
    """

    source_observation_fingerprint: str
    release_tree_fingerprint: str
    toolchain_environment_fingerprint: str
    owner_dag_fingerprint: str = ""
    # Action lists and callers sometimes spell this identity explicitly as a
    # "fixed" DAG fingerprint.  Keep one canonical value while accepting that
    # public spelling at the boundary.
    fixed_owner_dag_fingerprint: str = ""
    model_authority_fingerprint: str = ""
    test_inventory_fingerprint: str = ""
    required_terminal_action_ids: tuple[str, ...] = ()
    remaining_governed_write_ids: tuple[str, ...] = ()
    # Separate names are accepted for callers which keep head and snapshot
    # identities independently.  ``model_authority_fingerprint`` remains the
    # canonical combined identity used in the epoch hash.
    model_authority_head_fingerprint: str = ""
    model_authority_snapshot_fingerprint: str = ""
    # A cycle is anchored to the stable maintenance unit/work id rather than
    # to a mutable objective or owner disposition.  This lets a repaired plan
    # keep the same finite retry budget while its source/model inputs or
    # reviewed objective legitimately change.
    completion_objective_fingerprint: str = ""
    # An explicit same-work authorization may open one new finite cycle after
    # an earlier cycle is exhausted.  Empty preserves the original cycle
    # identity for historical plans; a non-empty value must come from the
    # typed CompletionAuthorization record.
    completion_authorization_fingerprint: str = ""
    # The cycle identity is derived from the stable maintenance-unit/work-id
    # seed.  It is intentionally not a caller-controlled nonce: a repair may
    # change source inputs while remaining in the same finite cycle, but
    # changing objective text, output directories, or owner dispositions
    # cannot buy another full attempt.
    completion_cycle_seed_fingerprint: str = ""
    completion_cycle_id: str = ""
    completion_cycle_max_attempts: int = MAX_COMPLETION_CYCLE_FULL_ATTEMPTS
    attempt_index: int = 0
    repair_link: CompletionRepairLink | None = None
    full_producer_attempts: int = 0
    schema_version: str = COMPLETION_EPOCH_SCHEMA
    # These fields identify the maintenance unit and user task whose finite
    # producer budget is being consumed.  They are part of the epoch payload
    # (so a receipt cannot be relabelled) but the cycle seed below uses only
    # these stable scope fields, never the mutable objective or output path.
    maintenance_unit_id: str = COMPLETION_MAINTENANCE_UNIT_ID
    completion_work_id: str = COMPLETION_DEFAULT_WORK_ID
    claim_scope: str = COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION

    def __post_init__(self) -> None:
        for field_name in (
            "source_observation_fingerprint",
            "release_tree_fingerprint",
            "toolchain_environment_fingerprint",
        ):
            object.__setattr__(self, field_name, _normalize_fingerprint(getattr(self, field_name), field_name))

        object.__setattr__(
            self,
            "maintenance_unit_id",
            _normalize_maintenance_unit_id(self.maintenance_unit_id),
        )
        object.__setattr__(
            self,
            "completion_work_id",
            _normalize_completion_work_id(self.completion_work_id),
        )
        object.__setattr__(self, "claim_scope", _normalize_claim_scope(self.claim_scope))

        owner_dag = self.owner_dag_fingerprint
        fixed_owner_dag = self.fixed_owner_dag_fingerprint
        if not isinstance(owner_dag, str) or not isinstance(fixed_owner_dag, str):
            raise ValueError("completion epoch owner DAG fingerprints must be strings")
        owner_dag = owner_dag.strip()
        fixed_owner_dag = fixed_owner_dag.strip()
        if not owner_dag and fixed_owner_dag:
            owner_dag = fixed_owner_dag
        if owner_dag and fixed_owner_dag and owner_dag != fixed_owner_dag:
            raise ValueError(
                "completion epoch owner DAG fingerprints disagree"
            )
        object.__setattr__(
            self,
            "owner_dag_fingerprint",
            _normalize_fingerprint(owner_dag, "owner_dag_fingerprint"),
        )
        object.__setattr__(self, "fixed_owner_dag_fingerprint", owner_dag)

        model_fingerprint = self.model_authority_fingerprint
        head = self.model_authority_head_fingerprint
        snapshot = self.model_authority_snapshot_fingerprint
        if not isinstance(model_fingerprint, str):
            raise ValueError("completion epoch model_authority_fingerprint must be a string")
        if not isinstance(head, str) or not isinstance(snapshot, str):
            raise ValueError(
                "completion epoch model authority head/snapshot fingerprints must be strings"
            )
        model_fingerprint = model_fingerprint.strip()
        head = head.strip()
        snapshot = snapshot.strip()
        if not model_fingerprint and (head or snapshot):
            model_fingerprint = fingerprint_value({"head": head, "snapshot": snapshot})
        if not model_fingerprint:
            raise ValueError("completion epoch model_authority_fingerprint is required")
        if head or snapshot:
            expected_model = fingerprint_value({"head": head, "snapshot": snapshot})
            if model_fingerprint != expected_model:
                raise ValueError(
                    "completion epoch model authority fingerprints disagree"
                )
        object.__setattr__(self, "model_authority_fingerprint", model_fingerprint)
        object.__setattr__(self, "model_authority_head_fingerprint", head)
        object.__setattr__(self, "model_authority_snapshot_fingerprint", snapshot)
        object.__setattr__(self, "test_inventory_fingerprint", _normalize_fingerprint(self.test_inventory_fingerprint, "test_inventory_fingerprint"))
        object.__setattr__(
            self,
            "required_terminal_action_ids",
            _normalize_ids(self.required_terminal_action_ids, "required_terminal_action_ids"),
        )
        objective = self.completion_objective_fingerprint
        if not isinstance(objective, str):
            raise ValueError(
                "completion epoch completion_objective_fingerprint must be a string"
            )
        objective = objective.strip()
        if not objective:
            # The default keeps existing callers deterministic while avoiding
            # owner-DAG/disposition data.  A named objective can provide a
            # stronger cross-plan anchor through ``freeze``.
            objective = fingerprint_value(
                {
                    "schema_version": COMPLETION_CYCLE_SCHEMA,
                    "required_terminal_action_ids": list(
                        self.required_terminal_action_ids
                    ),
                }
            )
        else:
            objective = _normalize_fingerprint(
                objective,
                "completion_objective_fingerprint",
            )
        object.__setattr__(self, "completion_objective_fingerprint", objective)
        authorization = self.completion_authorization_fingerprint
        if not isinstance(authorization, str):
            raise ValueError(
                "completion epoch completion_authorization_fingerprint must be a string"
            )
        authorization = authorization.strip()
        if authorization:
            authorization = _normalize_fingerprint(
                authorization,
                "completion_authorization_fingerprint",
            )
        object.__setattr__(self, "completion_authorization_fingerprint", authorization)
        object.__setattr__(
            self,
            "remaining_governed_write_ids",
            _normalize_ids(self.remaining_governed_write_ids, "remaining_governed_write_ids"),
        )
        maximum_attempts = _normalize_int(
            self.completion_cycle_max_attempts,
            "completion_cycle_max_attempts",
            minimum=1,
            maximum=MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        )
        object.__setattr__(self, "completion_cycle_max_attempts", maximum_attempts)
        attempt_index = _normalize_int(
            self.attempt_index,
            "attempt_index",
            minimum=0,
        )
        if attempt_index >= maximum_attempts:
            raise ValueError(
                "completion epoch attempt_index is outside its finite cycle budget"
            )
        object.__setattr__(self, "attempt_index", attempt_index)
        cycle_seed_payload = {
            "schema_version": COMPLETION_CYCLE_SCHEMA,
            "maintenance_unit_id": self.maintenance_unit_id,
            "completion_work_id": self.completion_work_id,
        }
        if self.completion_authorization_fingerprint:
            cycle_seed_payload[
                "completion_authorization_fingerprint"
            ] = self.completion_authorization_fingerprint
        derived_cycle_seed = fingerprint_value(cycle_seed_payload)
        if not isinstance(self.completion_cycle_seed_fingerprint, str):
            raise ValueError(
                "completion epoch completion_cycle_seed_fingerprint must be a string"
            )
        supplied_seed = self.completion_cycle_seed_fingerprint.strip()
        if supplied_seed and supplied_seed != derived_cycle_seed:
            raise ValueError(
                "completion epoch cycle seed must be derived from the immutable "
                "maintenance unit/work id and any explicit authorization"
            )
        object.__setattr__(
            self,
            "completion_cycle_seed_fingerprint",
            derived_cycle_seed,
        )
        expected_cycle_id = CompletionCycle.derive_id(
            derived_cycle_seed,
            maximum_attempts,
        )
        if not isinstance(self.completion_cycle_id, str):
            raise ValueError("completion epoch completion_cycle_id must be a string")
        supplied_cycle_id = self.completion_cycle_id.strip()
        if supplied_cycle_id and supplied_cycle_id != expected_cycle_id:
            raise ValueError(
                "completion epoch cycle id must be derived from its cycle seed"
            )
        object.__setattr__(self, "completion_cycle_id", expected_cycle_id)
        if self.repair_link is not None and not isinstance(
            self.repair_link,
            CompletionRepairLink,
        ):
            raise ValueError("completion epoch repair_link must be a CompletionRepairLink")
        if attempt_index == 0 and self.repair_link is not None:
            raise ValueError(
                "initial completion epoch cannot contain a repair link"
            )
        if attempt_index > 0 and self.repair_link is None:
            raise ValueError(
                "repaired completion epoch requires a typed repair link"
            )
        if self.repair_link is not None:
            if self.repair_link.completion_cycle_id != expected_cycle_id:
                raise ValueError(
                    "completion epoch repair link cycle identity mismatch"
                )
            if self.repair_link.previous_attempt_index != attempt_index - 1:
                raise ValueError(
                    "completion epoch repair link attempt index mismatch"
                )
        attempts = _normalize_int(
            self.full_producer_attempts,
            "full_producer_attempts",
            minimum=0,
            maximum=1,
        )
        object.__setattr__(self, "full_producer_attempts", attempts)
        if self.schema_version != COMPLETION_EPOCH_SCHEMA:
            raise ValueError(f"unsupported completion epoch schema: {self.schema_version}")

    @property
    def identity_payload(self) -> dict[str, Any]:
        """Return exactly the source-bound identity used for ``epoch_id``."""

        return {
            "schema_version": self.schema_version,
            "maintenance_unit_id": self.maintenance_unit_id,
            "completion_work_id": self.completion_work_id,
            "claim_scope": self.claim_scope,
            "source_observation_fingerprint": self.source_observation_fingerprint,
            "release_tree_fingerprint": self.release_tree_fingerprint,
            "toolchain_environment_fingerprint": self.toolchain_environment_fingerprint,
            "owner_dag_fingerprint": self.owner_dag_fingerprint,
            "fixed_owner_dag_fingerprint": self.fixed_owner_dag_fingerprint,
            "model_authority_fingerprint": self.model_authority_fingerprint,
            "model_authority_head_fingerprint": self.model_authority_head_fingerprint,
            "model_authority_snapshot_fingerprint": self.model_authority_snapshot_fingerprint,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "completion_objective_fingerprint": self.completion_objective_fingerprint,
            **(
                {
                    "completion_authorization_fingerprint": self.completion_authorization_fingerprint
                }
                if self.completion_authorization_fingerprint
                else {}
            ),
            "required_terminal_action_ids": list(self.required_terminal_action_ids),
            "remaining_governed_write_ids": list(self.remaining_governed_write_ids),
            "completion_cycle_seed_fingerprint": self.completion_cycle_seed_fingerprint,
            "completion_cycle_id": self.completion_cycle_id,
            "completion_cycle_max_attempts": self.completion_cycle_max_attempts,
            "attempt_index": self.attempt_index,
            "repair_link": (
                self.repair_link.to_dict()
                if self.repair_link is not None
                else None
            ),
        }

    @property
    def epoch_id(self) -> str:
        return fingerprint_value(self.identity_payload)

    @property
    def plan_fingerprint(self) -> str:
        return self.epoch_id

    @property
    def final_ready(self) -> bool:
        return not self.remaining_governed_write_ids

    @property
    def full_attempt_available(self) -> bool:
        return (
            self.full_producer_attempts == 0
            and self.attempt_index < self.completion_cycle_max_attempts
        )

    @property
    def completion_cycle(self) -> CompletionCycle:
        return CompletionCycle(
            cycle_id=self.completion_cycle_id,
            cycle_seed_fingerprint=self.completion_cycle_seed_fingerprint,
            maximum_full_attempts=self.completion_cycle_max_attempts,
            consumed_full_attempts=self.attempt_index,
            status=(
                CYCLE_OPEN
                if self.attempt_index == 0
                else CYCLE_REPAIR_REQUIRED
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload,
            "epoch_id": self.epoch_id,
            "full_producer_attempts": self.full_producer_attempts,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionEpochPlan":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "epoch_id",
                "maintenance_unit_id",
                "completion_work_id",
                "claim_scope",
                "source_observation_fingerprint",
                "release_tree_fingerprint",
                "toolchain_environment_fingerprint",
                "owner_dag_fingerprint",
                "fixed_owner_dag_fingerprint",
                "model_authority_fingerprint",
                "model_authority_head_fingerprint",
                "model_authority_snapshot_fingerprint",
                "test_inventory_fingerprint",
                "completion_objective_fingerprint",
                "required_terminal_action_ids",
                "remaining_governed_write_ids",
                "completion_cycle_seed_fingerprint",
                "completion_cycle_id",
                "completion_cycle_max_attempts",
                "attempt_index",
                "repair_link",
                "full_producer_attempts",
            },
            optional={"completion_authorization_fingerprint"},
            context="completion epoch plan",
        )
        repair_payload = payload["repair_link"]
        if repair_payload is not None and not isinstance(repair_payload, Mapping):
            raise ValueError("completion epoch plan repair_link must be an object or null")
        plan = cls(
            source_observation_fingerprint=payload["source_observation_fingerprint"],
            release_tree_fingerprint=payload["release_tree_fingerprint"],
            toolchain_environment_fingerprint=payload["toolchain_environment_fingerprint"],
            maintenance_unit_id=payload["maintenance_unit_id"],
            completion_work_id=payload["completion_work_id"],
            claim_scope=payload["claim_scope"],
            owner_dag_fingerprint=payload["owner_dag_fingerprint"],
            fixed_owner_dag_fingerprint=payload["fixed_owner_dag_fingerprint"],
            model_authority_fingerprint=payload["model_authority_fingerprint"],
            test_inventory_fingerprint=payload["test_inventory_fingerprint"],
            required_terminal_action_ids=payload["required_terminal_action_ids"],
            remaining_governed_write_ids=payload["remaining_governed_write_ids"],
            model_authority_head_fingerprint=payload["model_authority_head_fingerprint"],
            model_authority_snapshot_fingerprint=payload["model_authority_snapshot_fingerprint"],
            completion_cycle_seed_fingerprint=payload["completion_cycle_seed_fingerprint"],
            completion_objective_fingerprint=payload["completion_objective_fingerprint"],
            completion_authorization_fingerprint=str(
                payload.get("completion_authorization_fingerprint", "")
            ),
            completion_cycle_id=payload["completion_cycle_id"],
            completion_cycle_max_attempts=payload["completion_cycle_max_attempts"],
            attempt_index=payload["attempt_index"],
            repair_link=(
                CompletionRepairLink.from_dict(repair_payload)
                if repair_payload is not None
                else None
            ),
            full_producer_attempts=payload["full_producer_attempts"],
            schema_version=payload["schema_version"],
        )
        declared_epoch_id = _normalize_epoch_id(payload["epoch_id"])
        if declared_epoch_id != plan.epoch_id:
            raise ValueError("completion epoch plan identity mismatch")
        return plan

    @classmethod
    def freeze(
        cls,
        *,
        source_observation_fingerprint: str,
        release_tree_fingerprint: str,
        toolchain_environment_fingerprint: str,
        owner_dag_fingerprint: str = "",
        fixed_owner_dag_fingerprint: str = "",
        model_authority_fingerprint: str = "",
        model_authority_head_fingerprint: str = "",
        model_authority_snapshot_fingerprint: str = "",
        completion_objective_fingerprint: str = "",
        test_inventory_fingerprint: str,
        required_terminal_action_ids: Sequence[str] = (),
        remaining_governed_write_ids: Sequence[str] = (),
        completion_cycle_seed_fingerprint: str = "",
        completion_cycle_id: str = "",
        completion_cycle_max_attempts: int = MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        attempt_index: int = 0,
        repair_link: CompletionRepairLink | None = None,
        completion_authorization_fingerprint: str = "",
        maintenance_unit_id: str = COMPLETION_MAINTENANCE_UNIT_ID,
        completion_work_id: str = COMPLETION_DEFAULT_WORK_ID,
        claim_scope: str = COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION,
    ) -> "CompletionEpochPlan":
        """Create a plan with an explicit frozen identity."""

        return cls(
            source_observation_fingerprint=source_observation_fingerprint,
            release_tree_fingerprint=release_tree_fingerprint,
            toolchain_environment_fingerprint=toolchain_environment_fingerprint,
            maintenance_unit_id=maintenance_unit_id,
            completion_work_id=completion_work_id,
            claim_scope=claim_scope,
            owner_dag_fingerprint=owner_dag_fingerprint,
            fixed_owner_dag_fingerprint=fixed_owner_dag_fingerprint,
            model_authority_fingerprint=model_authority_fingerprint,
            model_authority_head_fingerprint=model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=model_authority_snapshot_fingerprint,
            completion_objective_fingerprint=completion_objective_fingerprint,
            completion_authorization_fingerprint=completion_authorization_fingerprint,
            test_inventory_fingerprint=test_inventory_fingerprint,
            required_terminal_action_ids=tuple(required_terminal_action_ids),
            remaining_governed_write_ids=tuple(remaining_governed_write_ids),
            completion_cycle_seed_fingerprint=completion_cycle_seed_fingerprint,
            completion_cycle_id=completion_cycle_id,
            completion_cycle_max_attempts=completion_cycle_max_attempts,
            attempt_index=attempt_index,
            repair_link=repair_link,
        )

    def with_remaining_governed_writes(self, write_ids: Sequence[str]) -> "CompletionEpochPlan":
        """Return a new epoch identity after a mutable repair batch."""
        if self.full_producer_attempts:
            raise ValueError(
                "completion epoch cannot reset governed writes after a full producer attempt"
            )
        return replace(self, remaining_governed_write_ids=tuple(write_ids), full_producer_attempts=0)

    @classmethod
    def for_repair(
        cls,
        previous_plan: "CompletionEpochPlan",
        *,
        source_observation_fingerprint: str,
        release_tree_fingerprint: str,
        toolchain_environment_fingerprint: str,
        owner_dag_fingerprint: str = "",
        model_authority_fingerprint: str = "",
        model_authority_head_fingerprint: str = "",
        model_authority_snapshot_fingerprint: str = "",
        completion_objective_fingerprint: str = "",
        test_inventory_fingerprint: str,
        required_terminal_action_ids: Sequence[str] | None = None,
        remaining_governed_write_ids: Sequence[str] = (),
        repair_link: CompletionRepairLink,
    ) -> "CompletionEpochPlan":
        """Create the next finite-cycle epoch only from a typed repair link."""

        if previous_plan.full_producer_attempts != 1:
            raise ValueError(
                "completion repair requires a previously claimed full producer attempt"
            )
        if previous_plan.attempt_index + 1 >= previous_plan.completion_cycle_max_attempts:
            raise ValueError("completion repair completion cycle budget exhausted")
        actions = (
            previous_plan.required_terminal_action_ids
            if required_terminal_action_ids is None
            else tuple(required_terminal_action_ids)
        )
        if not model_authority_fingerprint and not (
            model_authority_head_fingerprint or model_authority_snapshot_fingerprint
        ):
            model_authority_fingerprint = previous_plan.model_authority_fingerprint
            model_authority_head_fingerprint = previous_plan.model_authority_head_fingerprint
            model_authority_snapshot_fingerprint = previous_plan.model_authority_snapshot_fingerprint
        repair_objective = (
            completion_objective_fingerprint.strip()
            if isinstance(completion_objective_fingerprint, str)
            and completion_objective_fingerprint.strip()
            else str(
                repair_link.changed_input_fingerprints.get(
                    "completion_objective_fingerprint",
                    previous_plan.completion_objective_fingerprint,
                )
            ).strip()
        )
        candidate = cls.freeze(
            source_observation_fingerprint=source_observation_fingerprint,
            release_tree_fingerprint=release_tree_fingerprint,
            toolchain_environment_fingerprint=toolchain_environment_fingerprint,
            maintenance_unit_id=previous_plan.maintenance_unit_id,
            completion_work_id=previous_plan.completion_work_id,
            claim_scope=previous_plan.claim_scope,
            # A typed repair link is the boundary that permits exactly one
            # second attempt.  The repaired attempt must still freeze the
            # *current* owner DAG: changing code or the validation graph is a
            # governed input and must be declared in changed_input_fingerprints
            # instead of being silently pinned to the failed attempt.
            owner_dag_fingerprint=(
                owner_dag_fingerprint.strip()
                if isinstance(owner_dag_fingerprint, str)
                and owner_dag_fingerprint.strip()
                else previous_plan.owner_dag_fingerprint
            ),
            model_authority_fingerprint=model_authority_fingerprint,
            model_authority_head_fingerprint=model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=model_authority_snapshot_fingerprint,
            completion_objective_fingerprint=repair_objective,
            completion_authorization_fingerprint=previous_plan.completion_authorization_fingerprint,
            test_inventory_fingerprint=test_inventory_fingerprint,
            required_terminal_action_ids=actions,
            remaining_governed_write_ids=remaining_governed_write_ids,
            completion_cycle_seed_fingerprint=previous_plan.completion_cycle_seed_fingerprint,
            completion_cycle_id=previous_plan.completion_cycle_id,
            completion_cycle_max_attempts=previous_plan.completion_cycle_max_attempts,
            attempt_index=previous_plan.attempt_index + 1,
            repair_link=repair_link,
        )
        blockers = repair_link.validate_for(previous_plan, candidate)
        # The previous terminal ledger is validated separately by
        # validate_repair; constructor-level checks still reject identity,
        # sequencing, and changed-input errors before any producer is started.
        blockers = tuple(
            blocker
            for blocker in blockers
            if blocker != "repair_previous_terminal_ledger_missing"
        )
        if blockers:
            raise ValueError("completion repair link invalid: " + ", ".join(blockers))
        return candidate

    def validate_repair(
        self,
        previous_plan: "CompletionEpochPlan",
        previous_ledger: "CompletionEpochTerminalLedger | None",
    ) -> tuple[str, ...]:
        if self.repair_link is None:
            return ("completion_repair_link_missing",)
        return self.repair_link.validate_for(
            previous_plan,
            self,
            previous_ledger=previous_ledger,
        )

    def claim_full_producer(self) -> "CompletionEpochPlan":
        """Claim the sole full producer attempt for this epoch.

        The returned plan is the claimed value.  A caller must retain it and
        pass it to its producer/ledger; the original plan remains unchanged.
        """

        if self.full_producer_attempts:
            raise RuntimeError("completion epoch full producer attempt already consumed")
        if self.attempt_index >= self.completion_cycle_max_attempts:
            raise RuntimeError("completion cycle full attempt budget exhausted")
        return replace(self, full_producer_attempts=1)

    # Readable aliases used by process owners and tests.
    begin_full_attempt = claim_full_producer
    claim_full_attempt = claim_full_producer

    def admit(
        self,
        *,
        readiness: CompletionEpochReadiness | None = None,
    ) -> "CompletionEpochAdmission":
        return CompletionEpochAdmission.evaluate(self, readiness=readiness)

    def assert_final_admitted(self, **kwargs: Any) -> "CompletionEpochAdmission":
        admission = self.admit(**kwargs)
        if not admission.ok:
            raise CompletionEpochAdmissionError(admission)
        return admission

    def assert_source_current(self, source_observation_fingerprint: str) -> None:
        if str(source_observation_fingerprint).strip() != self.source_observation_fingerprint:
            raise CompletionEpochSourceDriftError(
                self,
                str(source_observation_fingerprint).strip(),
            )


@dataclass(frozen=True)
class CompletionEpochAdmission:
    """Result of final-admission checks for one frozen plan."""

    epoch_id: str
    status: str
    blockers: tuple[str, ...] = ()
    remaining_governed_write_ids: tuple[str, ...] = ()
    checks: Mapping[str, bool] = field(default_factory=dict)
    plan: CompletionEpochPlan | None = field(default=None, compare=False, repr=False)
    schema_version: str = COMPLETION_EPOCH_ADMISSION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "epoch_id", str(self.epoch_id).strip())
        object.__setattr__(self, "status", str(self.status).strip())
        object.__setattr__(self, "blockers", _normalize_ids(self.blockers, "admission blockers"))
        object.__setattr__(self, "remaining_governed_write_ids", _normalize_ids(self.remaining_governed_write_ids, "remaining_governed_write_ids"))
        object.__setattr__(self, "checks", {str(key): bool(value) for key, value in sorted(self.checks.items())})
        if not self.epoch_id:
            raise ValueError("completion epoch admission epoch_id is required")
        if self.status not in {EPOCH_ADMITTED, EPOCH_BLOCKED}:
            raise ValueError(f"unsupported completion epoch admission status: {self.status}")
        if self.status == EPOCH_ADMITTED and self.blockers:
            raise ValueError("admitted completion epoch cannot have blockers")
        if self.status == EPOCH_BLOCKED and not self.blockers:
            raise ValueError("blocked completion epoch must expose blockers")
        if self.schema_version != COMPLETION_EPOCH_ADMISSION_SCHEMA:
            raise ValueError(f"unsupported completion epoch admission schema: {self.schema_version}")

    @property
    def ok(self) -> bool:
        return self.status == EPOCH_ADMITTED and not self.blockers

    @property
    def admitted(self) -> bool:
        return self.ok

    @classmethod
    def evaluate(
        cls,
        plan: CompletionEpochPlan,
        *,
        readiness: CompletionEpochReadiness | None = None,
    ) -> "CompletionEpochAdmission":
        checks = {
            "remaining_governed_writes_empty": not plan.remaining_governed_write_ids,
            "full_producer_attempt_available": plan.full_attempt_available,
            "completion_cycle_attempt_available": (
                plan.attempt_index < plan.completion_cycle_max_attempts
            ),
            "completion_readiness_current": False,
        }
        blockers: list[str] = []
        if plan.remaining_governed_write_ids:
            blockers.append("remaining_governed_writes")
        if not plan.full_attempt_available:
            blockers.append("full_producer_attempt_already_consumed")
        if plan.attempt_index >= plan.completion_cycle_max_attempts:
            blockers.append("completion_cycle_attempt_budget_exhausted")
        if readiness is None:
            blockers.append("completion_readiness_missing")
        elif not isinstance(readiness, CompletionEpochReadiness):
            blockers.append("completion_readiness_type_invalid")
        else:
            readiness_blockers = readiness.validate_for(plan)
            checks["completion_readiness_current"] = not readiness_blockers
            blockers.extend(readiness_blockers)
        return cls(
            epoch_id=plan.epoch_id,
            status=EPOCH_ADMITTED if not blockers else EPOCH_BLOCKED,
            blockers=tuple(blockers),
            remaining_governed_write_ids=plan.remaining_governed_write_ids,
            checks=checks,
            plan=plan,
        )

    # Alias for callers that naturally read this as a gate operation.
    admit = evaluate

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "epoch_id": self.epoch_id,
            "status": self.status,
            "ok": self.ok,
            "blockers": list(self.blockers),
            "remaining_governed_write_ids": list(self.remaining_governed_write_ids),
            "checks": dict(self.checks),
        }


class CompletionEpochAdmissionError(RuntimeError):
    """Raised when final validation is attempted before epoch admission."""

    def __init__(self, admission: CompletionEpochAdmission):
        self.admission = admission
        super().__init__(
            "completion epoch final admission blocked: "
            + ", ".join(admission.blockers)
        )


class CompletionEpochSourceDriftError(RuntimeError):
    """Raised when a frozen epoch's source identity changes before the gate."""

    def __init__(self, plan: CompletionEpochPlan, observed_fingerprint: str):
        self.plan = plan
        self.observed_fingerprint = observed_fingerprint
        super().__init__(
            "completion epoch source drift: "
            f"expected={plan.source_observation_fingerprint}, observed={observed_fingerprint}"
        )


@dataclass(frozen=True)
class CompletionEpochTerminalLedger:
    """Output-only terminal outcome for a frozen completion epoch."""

    epoch_id: str
    status: str
    terminal_action_ids: tuple[str, ...] = ()
    completed_terminal_action_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    source_observation_fingerprint: str = ""
    release_tree_fingerprint: str = ""
    toolchain_environment_fingerprint: str = ""
    owner_dag_fingerprint: str = ""
    fixed_owner_dag_fingerprint: str = ""
    model_authority_fingerprint: str = ""
    model_authority_head_fingerprint: str = ""
    model_authority_snapshot_fingerprint: str = ""
    test_inventory_fingerprint: str = ""
    completion_objective_fingerprint: str = ""
    completion_authorization_fingerprint: str = ""
    completion_cycle_seed_fingerprint: str = ""
    completion_cycle_id: str = ""
    completion_cycle_max_attempts: int = MAX_COMPLETION_CYCLE_FULL_ATTEMPTS
    attempt_index: int = 0
    repair_link_fingerprint: str = ""
    full_producer_attempts: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = COMPLETION_EPOCH_LEDGER_SCHEMA
    maintenance_unit_id: str = COMPLETION_MAINTENANCE_UNIT_ID
    completion_work_id: str = COMPLETION_DEFAULT_WORK_ID
    claim_scope: str = COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION

    def __post_init__(self) -> None:
        object.__setattr__(self, "epoch_id", _normalize_epoch_id(self.epoch_id))
        object.__setattr__(
            self,
            "maintenance_unit_id",
            _normalize_maintenance_unit_id(self.maintenance_unit_id),
        )
        object.__setattr__(
            self,
            "completion_work_id",
            _normalize_completion_work_id(self.completion_work_id),
        )
        object.__setattr__(self, "claim_scope", _normalize_claim_scope(self.claim_scope))
        if not isinstance(self.status, str):
            raise ValueError("completion epoch terminal ledger status must be a string")
        object.__setattr__(self, "status", self.status.strip())
        if self.status not in {EPOCH_TERMINAL_PASS, EPOCH_ABORTED, EPOCH_BLOCKED}:
            raise ValueError(f"unsupported completion epoch terminal status: {self.status}")
        object.__setattr__(self, "terminal_action_ids", _normalize_ids(self.terminal_action_ids, "terminal_action_ids"))
        object.__setattr__(self, "completed_terminal_action_ids", _normalize_ids(self.completed_terminal_action_ids, "completed_terminal_action_ids"))
        object.__setattr__(self, "blockers", _normalize_ids(self.blockers, "terminal blockers"))
        for field_name in (
            "source_observation_fingerprint",
            "release_tree_fingerprint",
            "toolchain_environment_fingerprint",
            "owner_dag_fingerprint",
            "model_authority_fingerprint",
            "test_inventory_fingerprint",
            "completion_cycle_seed_fingerprint",
            "completion_cycle_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_fingerprint(getattr(self, field_name), field_name),
        )
        object.__setattr__(self, "completion_cycle_id", _normalize_epoch_id(self.completion_cycle_id))
        objective = self.completion_objective_fingerprint
        if not isinstance(objective, str):
            raise ValueError(
                "completion epoch ledger completion_objective_fingerprint must be a string"
            )
        objective = objective.strip()
        if not objective:
            objective = fingerprint_value(
                {
                    "schema_version": COMPLETION_CYCLE_SCHEMA,
                    "required_terminal_action_ids": list(self.terminal_action_ids),
                }
            )
        else:
            objective = _normalize_fingerprint(
                objective,
                "completion_objective_fingerprint",
            )
        object.__setattr__(self, "completion_objective_fingerprint", objective)
        authorization = self.completion_authorization_fingerprint
        if not isinstance(authorization, str):
            raise ValueError(
                "completion epoch ledger completion_authorization_fingerprint must be a string"
            )
        authorization = authorization.strip()
        if authorization:
            authorization = _normalize_fingerprint(
                authorization,
                "completion_authorization_fingerprint",
            )
        object.__setattr__(self, "completion_authorization_fingerprint", authorization)
        if not isinstance(self.fixed_owner_dag_fingerprint, str):
            raise ValueError(
                "completion epoch ledger fixed owner DAG fingerprint must be a string"
            )
        fixed_owner_dag = self.fixed_owner_dag_fingerprint.strip()
        if not fixed_owner_dag:
            fixed_owner_dag = self.owner_dag_fingerprint
        if fixed_owner_dag != self.owner_dag_fingerprint:
            raise ValueError("completion epoch ledger owner DAG fingerprints disagree")
        object.__setattr__(self, "fixed_owner_dag_fingerprint", fixed_owner_dag)
        if not isinstance(self.model_authority_head_fingerprint, str) or not isinstance(
            self.model_authority_snapshot_fingerprint,
            str,
        ):
            raise ValueError(
                "completion epoch ledger model authority head/snapshot fingerprints must be strings"
            )
        model_head = self.model_authority_head_fingerprint.strip()
        model_snapshot = self.model_authority_snapshot_fingerprint.strip()
        if model_head or model_snapshot:
            expected_model = fingerprint_value(
                {"head": model_head, "snapshot": model_snapshot}
            )
            if expected_model != self.model_authority_fingerprint:
                raise ValueError(
                    "completion epoch ledger model authority fingerprints disagree"
                )
        object.__setattr__(self, "model_authority_head_fingerprint", model_head)
        object.__setattr__(
            self,
            "model_authority_snapshot_fingerprint",
            model_snapshot,
        )
        if not isinstance(self.repair_link_fingerprint, str):
            raise ValueError(
                "completion epoch ledger repair_link_fingerprint must be a string"
            )
        object.__setattr__(
            self,
            "repair_link_fingerprint",
            self.repair_link_fingerprint.strip(),
        )
        maximum_attempts = _normalize_int(
            self.completion_cycle_max_attempts,
            "completion_cycle_max_attempts",
            minimum=1,
            maximum=MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        )
        object.__setattr__(self, "completion_cycle_max_attempts", maximum_attempts)
        attempt_index = _normalize_int(
            self.attempt_index,
            "attempt_index",
            minimum=0,
        )
        if attempt_index < 0 or attempt_index >= maximum_attempts:
            raise ValueError(
                "completion epoch ledger attempt_index is outside its finite budget"
            )
        object.__setattr__(self, "attempt_index", attempt_index)
        attempts = _normalize_int(
            self.full_producer_attempts,
            "full_producer_attempts",
            minimum=0,
            maximum=1,
        )
        object.__setattr__(self, "full_producer_attempts", attempts)
        if self.status == EPOCH_TERMINAL_PASS:
            if self.blockers:
                raise ValueError("terminal pass ledger cannot contain blockers")
            if set(self.terminal_action_ids) - set(self.completed_terminal_action_ids):
                raise ValueError("terminal pass ledger is missing required actions")
        elif self.status == EPOCH_ABORTED:
            if not self.blockers:
                raise ValueError("aborted completion epoch requires a blocker")
            if attempts != 1:
                raise ValueError(
                    "aborted completion epoch requires one claimed full producer attempt"
                )
        elif self.status == EPOCH_BLOCKED and not self.blockers:
            raise ValueError("blocked completion epoch requires a blocker")
        if not isinstance(self.created_at, str):
            raise ValueError("completion epoch terminal ledger created_at must be a string")
        created_at = self.created_at.strip() or datetime.now(timezone.utc).isoformat()
        object.__setattr__(self, "created_at", created_at)
        if not isinstance(self.metadata, MappingABC):
            raise ValueError("completion epoch terminal ledger metadata must be an object")
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.schema_version != COMPLETION_EPOCH_LEDGER_SCHEMA:
            raise ValueError(f"unsupported completion epoch ledger schema: {self.schema_version}")

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "epoch_id": self.epoch_id,
            "maintenance_unit_id": self.maintenance_unit_id,
            "completion_work_id": self.completion_work_id,
            "claim_scope": self.claim_scope,
            "status": self.status,
            "terminal_action_ids": list(self.terminal_action_ids),
            "completed_terminal_action_ids": list(self.completed_terminal_action_ids),
            "blockers": list(self.blockers),
            "source_observation_fingerprint": self.source_observation_fingerprint,
            "release_tree_fingerprint": self.release_tree_fingerprint,
            "toolchain_environment_fingerprint": self.toolchain_environment_fingerprint,
            "owner_dag_fingerprint": self.owner_dag_fingerprint,
            "fixed_owner_dag_fingerprint": self.fixed_owner_dag_fingerprint,
            "model_authority_fingerprint": self.model_authority_fingerprint,
            "model_authority_head_fingerprint": self.model_authority_head_fingerprint,
            "model_authority_snapshot_fingerprint": self.model_authority_snapshot_fingerprint,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "completion_objective_fingerprint": self.completion_objective_fingerprint,
            "completion_cycle_seed_fingerprint": self.completion_cycle_seed_fingerprint,
            "completion_cycle_id": self.completion_cycle_id,
            "completion_cycle_max_attempts": self.completion_cycle_max_attempts,
            "attempt_index": self.attempt_index,
            "repair_link_fingerprint": self.repair_link_fingerprint,
            "full_producer_attempts": self.full_producer_attempts,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }
        if self.completion_authorization_fingerprint:
            payload[
                "completion_authorization_fingerprint"
            ] = self.completion_authorization_fingerprint
        if include_fingerprint:
            payload["ledger_fingerprint"] = fingerprint_value(payload)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionEpochTerminalLedger":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "epoch_id",
                "maintenance_unit_id",
                "completion_work_id",
                "claim_scope",
                "status",
                "terminal_action_ids",
                "completed_terminal_action_ids",
                "blockers",
                "source_observation_fingerprint",
                "release_tree_fingerprint",
                "toolchain_environment_fingerprint",
                "owner_dag_fingerprint",
                "fixed_owner_dag_fingerprint",
                "model_authority_fingerprint",
                "model_authority_head_fingerprint",
                "model_authority_snapshot_fingerprint",
                "test_inventory_fingerprint",
                "completion_objective_fingerprint",
                "completion_cycle_seed_fingerprint",
                "completion_cycle_id",
                "completion_cycle_max_attempts",
                "attempt_index",
                "repair_link_fingerprint",
                "full_producer_attempts",
                "created_at",
                "metadata",
            },
            optional={"ledger_fingerprint", "completion_authorization_fingerprint"},
            context="completion epoch terminal ledger",
        )
        ledger = cls(
            epoch_id=payload["epoch_id"],
            maintenance_unit_id=payload["maintenance_unit_id"],
            completion_work_id=payload["completion_work_id"],
            claim_scope=payload["claim_scope"],
            status=payload["status"],
            terminal_action_ids=payload["terminal_action_ids"],
            completed_terminal_action_ids=payload["completed_terminal_action_ids"],
            blockers=payload["blockers"],
            source_observation_fingerprint=payload["source_observation_fingerprint"],
            release_tree_fingerprint=payload["release_tree_fingerprint"],
            toolchain_environment_fingerprint=payload["toolchain_environment_fingerprint"],
            owner_dag_fingerprint=payload["owner_dag_fingerprint"],
            fixed_owner_dag_fingerprint=payload["fixed_owner_dag_fingerprint"],
            model_authority_fingerprint=payload["model_authority_fingerprint"],
            model_authority_head_fingerprint=payload["model_authority_head_fingerprint"],
            model_authority_snapshot_fingerprint=payload["model_authority_snapshot_fingerprint"],
            test_inventory_fingerprint=payload["test_inventory_fingerprint"],
            completion_objective_fingerprint=payload["completion_objective_fingerprint"],
            completion_authorization_fingerprint=str(
                payload.get("completion_authorization_fingerprint", "")
            ),
            completion_cycle_seed_fingerprint=payload["completion_cycle_seed_fingerprint"],
            completion_cycle_id=payload["completion_cycle_id"],
            completion_cycle_max_attempts=payload["completion_cycle_max_attempts"],
            attempt_index=payload["attempt_index"],
            repair_link_fingerprint=payload["repair_link_fingerprint"],
            full_producer_attempts=payload["full_producer_attempts"],
            created_at=payload["created_at"],
            metadata=payload["metadata"],
            schema_version=payload["schema_version"],
        )
        declared = payload.get("ledger_fingerprint", "")
        if not isinstance(declared, str) or not declared.strip():
            raise ValueError("completion epoch terminal ledger fingerprint is required")
        if declared != ledger.fingerprint:
            raise ValueError("completion epoch terminal ledger fingerprint mismatch")
        return ledger

    @classmethod
    def terminal_pass(
        cls,
        plan: CompletionEpochPlan,
        *,
        verified_child_action_ids: Sequence[str],
        metadata: Mapping[str, Any] | None = None,
    ) -> "CompletionEpochTerminalLedger":
        # A terminal pass is the single end-of-epoch settlement.  It must not
        # be constructible while the frozen plan still declares governed
        # writes.  Otherwise a caller could publish a green terminal receipt,
        # perform another repair batch, and accidentally reuse the old
        # freshness epoch.  Admission exposes the same blocker, but keeping
        # this invariant at the ledger boundary makes the output fail closed
        # even when a caller skips the convenience admission helper.
        if plan.remaining_governed_write_ids:
            raise ValueError(
                "terminal ledger cannot pass with remaining governed writes: "
                + ", ".join(plan.remaining_governed_write_ids)
            )
        # The producer must provide the set it derived from independently
        # verified child receipts.  The old optional argument let a caller
        # silently manufacture a green terminal row by copying the required
        # ids from the plan; that path is intentionally gone in readiness v2.
        completed = _normalize_ids(
            verified_child_action_ids,
            "verified_child_action_ids",
        )
        required = tuple(plan.required_terminal_action_ids)
        if set(completed) != set(required):
            missing = sorted(set(required) - set(completed))
            extra = sorted(set(completed) - set(required))
            details: list[str] = []
            if missing:
                details.append("missing required actions: " + ", ".join(missing))
            if extra:
                details.append("unexpected actions: " + ", ".join(extra))
            raise ValueError("terminal ledger child receipt set mismatch (" + "; ".join(details) + ")")
        return cls(
            epoch_id=plan.epoch_id,
            maintenance_unit_id=plan.maintenance_unit_id,
            completion_work_id=plan.completion_work_id,
            claim_scope=plan.claim_scope,
            status=EPOCH_TERMINAL_PASS,
            terminal_action_ids=plan.required_terminal_action_ids,
            completed_terminal_action_ids=completed,
            source_observation_fingerprint=plan.source_observation_fingerprint,
            release_tree_fingerprint=plan.release_tree_fingerprint,
            toolchain_environment_fingerprint=plan.toolchain_environment_fingerprint,
            owner_dag_fingerprint=plan.owner_dag_fingerprint,
            fixed_owner_dag_fingerprint=plan.fixed_owner_dag_fingerprint,
            model_authority_fingerprint=plan.model_authority_fingerprint,
            model_authority_head_fingerprint=plan.model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=plan.model_authority_snapshot_fingerprint,
            test_inventory_fingerprint=plan.test_inventory_fingerprint,
            completion_objective_fingerprint=plan.completion_objective_fingerprint,
            completion_authorization_fingerprint=plan.completion_authorization_fingerprint,
            completion_cycle_seed_fingerprint=plan.completion_cycle_seed_fingerprint,
            completion_cycle_id=plan.completion_cycle_id,
            completion_cycle_max_attempts=plan.completion_cycle_max_attempts,
            attempt_index=plan.attempt_index,
            repair_link_fingerprint=(
                plan.repair_link.fingerprint
                if plan.repair_link is not None
                else ""
            ),
            full_producer_attempts=plan.full_producer_attempts,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def terminal_pass_from_verified_children(
        cls,
        plan: CompletionEpochPlan,
        child_evidence: Mapping[str, Any] | Sequence[Any],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "CompletionEpochTerminalLedger":
        """Create a pass ledger only from independently verified child rows.

        ``child_evidence`` is intentionally a narrow producer boundary.  It
        may be a mapping keyed by action id or a sequence of rows/objects.  A
        row must expose an action id (``action_id``, ``child_id``,
        ``owner_id``, or ``subject_id``), a terminal pass status, and positive
        ``current`` and ``eligible`` verification facts.  Missing facts are a
        hard error; they are never interpreted as an implicit pass.

        This helper does not perform receipt-store I/O itself.  The native
        parent producer owns that verification and passes its resulting rows
        here, keeping receipt verification separate from completion-epoch
        bookkeeping.
        """

        if isinstance(child_evidence, MappingABC):
            rows: list[tuple[str, Any]] = [
                (str(action_id), value)
                for action_id, value in child_evidence.items()
            ]
        elif isinstance(child_evidence, SequenceABC) and not isinstance(
            child_evidence,
            (str, bytes, bytearray),
        ):
            rows = []
            for value in child_evidence:
                if isinstance(value, MappingABC):
                    action_id = (
                        value.get("action_id")
                        or value.get("child_id")
                        or value.get("owner_id")
                        or value.get("subject_id")
                    )
                else:
                    action_id = (
                        getattr(value, "action_id", None)
                        or getattr(value, "child_id", None)
                        or getattr(value, "owner_id", None)
                        or getattr(value, "subject_id", None)
                    )
                if not isinstance(action_id, str) or not action_id.strip():
                    raise ValueError(
                        "terminal child evidence requires an action id"
                    )
                rows.append((action_id, value))
        else:
            raise ValueError(
                "terminal child evidence must be a mapping or sequence"
            )

        action_ids: list[str] = []
        for action_id, value in rows:
            if isinstance(value, MappingABC):
                status = value.get("status")
                current = value.get("current")
                eligible = value.get("eligible")
                verification = value.get("verification")
            else:
                status = getattr(value, "status", None)
                current = getattr(value, "current", None)
                eligible = getattr(value, "eligible", None)
                verification = getattr(value, "verification", None)
            # Native verification result objects commonly sit under a
            # ``verification`` field and expose ``ok`` rather than repeating
            # current/eligible.  Positive values still have to be explicit.
            if verification is not None:
                if isinstance(verification, MappingABC):
                    if status is None:
                        status = verification.get("status")
                    if current is None:
                        current = verification.get("current")
                    if eligible is None:
                        eligible = verification.get("eligible")
                    if eligible is None and verification.get("ok") is True:
                        eligible = True
                else:
                    if status is None:
                        status = getattr(verification, "status", None)
                    if current is None:
                        current = getattr(verification, "current", None)
                    if eligible is None:
                        eligible = getattr(verification, "eligible", None)
                    if eligible is None and getattr(verification, "ok", False) is True:
                        eligible = True
            if status not in {"pass", EPOCH_TERMINAL_PASS}:
                raise ValueError(
                    f"terminal child evidence is not a terminal pass: {action_id}"
                )
            if current is not True:
                raise ValueError(
                    f"terminal child evidence is not independently current: {action_id}"
                )
            if eligible is not True:
                raise ValueError(
                    f"terminal child evidence is not eligible: {action_id}"
                )
            action_ids.append(action_id)

        return cls.terminal_pass(
            plan,
            verified_child_action_ids=action_ids,
            metadata=metadata,
        )

    @classmethod
    def aborted(
        cls,
        plan: CompletionEpochPlan,
        reason: str,
        *,
        completed_terminal_action_ids: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "CompletionEpochTerminalLedger":
        reason = str(reason).strip()
        if not reason:
            raise ValueError("aborted completion epoch requires a reason")
        if plan.full_producer_attempts != 1:
            raise ValueError(
                "aborted completion epoch requires one claimed full producer attempt"
            )
        completed = _normalize_ids(
            completed_terminal_action_ids,
            "completed_terminal_action_ids",
        )
        required = set(plan.required_terminal_action_ids)
        if not set(completed).issubset(required):
            unknown = sorted(set(completed) - required)
            raise ValueError(
                "aborted completion epoch contains foreign completed actions: "
                + ", ".join(unknown)
            )
        return cls(
            epoch_id=plan.epoch_id,
            maintenance_unit_id=plan.maintenance_unit_id,
            completion_work_id=plan.completion_work_id,
            claim_scope=plan.claim_scope,
            status=EPOCH_ABORTED,
            terminal_action_ids=plan.required_terminal_action_ids,
            completed_terminal_action_ids=completed,
            blockers=(reason,),
            source_observation_fingerprint=plan.source_observation_fingerprint,
            release_tree_fingerprint=plan.release_tree_fingerprint,
            toolchain_environment_fingerprint=plan.toolchain_environment_fingerprint,
            owner_dag_fingerprint=plan.owner_dag_fingerprint,
            fixed_owner_dag_fingerprint=plan.fixed_owner_dag_fingerprint,
            model_authority_fingerprint=plan.model_authority_fingerprint,
            model_authority_head_fingerprint=plan.model_authority_head_fingerprint,
            model_authority_snapshot_fingerprint=plan.model_authority_snapshot_fingerprint,
            test_inventory_fingerprint=plan.test_inventory_fingerprint,
            completion_objective_fingerprint=plan.completion_objective_fingerprint,
            completion_authorization_fingerprint=plan.completion_authorization_fingerprint,
            completion_cycle_seed_fingerprint=plan.completion_cycle_seed_fingerprint,
            completion_cycle_id=plan.completion_cycle_id,
            completion_cycle_max_attempts=plan.completion_cycle_max_attempts,
            attempt_index=plan.attempt_index,
            repair_link_fingerprint=(
                plan.repair_link.fingerprint
                if plan.repair_link is not None
                else ""
            ),
            full_producer_attempts=plan.full_producer_attempts,
            metadata=dict(metadata or {}),
        )

    @property
    def output_filename(self) -> str:
        """Stable one-ledger-per-epoch filename."""

        return f"epoch-{self.epoch_id.split(':', 1)[-1]}.json"

    @classmethod
    def load_for_plan(
        cls,
        plan: CompletionEpochPlan,
        repository_root: str | Path,
    ) -> "CompletionEpochLedgerLoadResult":
        root = Path(repository_root).expanduser().resolve()
        path = cls.path_for_epoch_id(plan.epoch_id, root)
        loaded = cls.load_for_epoch_id(plan.epoch_id, root)
        if not loaded.is_valid:
            return loaded
        ledger = loaded.ledger
        assert ledger is not None
        try:
            mismatches = {
                field_name: (getattr(ledger, field_name), getattr(plan, field_name))
                for field_name in (
                    "epoch_id",
                    "maintenance_unit_id",
                    "completion_work_id",
                    "claim_scope",
                    "source_observation_fingerprint",
                    "release_tree_fingerprint",
                    "toolchain_environment_fingerprint",
                    "owner_dag_fingerprint",
                    "fixed_owner_dag_fingerprint",
                    "model_authority_fingerprint",
                    "model_authority_head_fingerprint",
                    "model_authority_snapshot_fingerprint",
                    "test_inventory_fingerprint",
                    "completion_objective_fingerprint",
                    "completion_authorization_fingerprint",
                    "completion_cycle_seed_fingerprint",
                    "completion_cycle_id",
                    "completion_cycle_max_attempts",
                    "attempt_index",
                )
                if getattr(ledger, field_name) != getattr(plan, field_name)
            }
            # ``full_producer_attempts`` is mutable execution state, not part
            # of the frozen plan identity.  A fresh process commonly rebuilds
            # the same unclaimed plan (attempts=0) and must still be able to
            # consume the terminal receipt produced by the claimed plan
            # (attempts=1).  The ledger itself remains authoritative and its
            # terminal pass/abort invariants require the producer claim.
            if ledger.status in {EPOCH_TERMINAL_PASS, EPOCH_ABORTED} and ledger.full_producer_attempts != 1:
                mismatches["full_producer_attempts"] = (
                    ledger.full_producer_attempts,
                    "terminal ledger must record one claimed producer",
                )
            if tuple(ledger.terminal_action_ids) != tuple(plan.required_terminal_action_ids):
                mismatches["terminal_action_ids"] = (
                    ledger.terminal_action_ids,
                    plan.required_terminal_action_ids,
                )
            expected_repair_fingerprint = (
                plan.repair_link.fingerprint
                if plan.repair_link is not None
                else ""
            )
            if ledger.repair_link_fingerprint != expected_repair_fingerprint:
                mismatches["repair_link_fingerprint"] = (
                    ledger.repair_link_fingerprint,
                    expected_repair_fingerprint,
                )
            if plan.remaining_governed_write_ids:
                mismatches["remaining_governed_write_ids"] = (
                    "ledger terminal output",
                    plan.remaining_governed_write_ids,
                )
            if mismatches:
                raise ValueError(
                    "completion epoch terminal ledger plan identity mismatch: "
                    + ", ".join(sorted(mismatches))
                )
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            return CompletionEpochLedgerLoadResult.invalid(path, str(exc))
        return CompletionEpochLedgerLoadResult.valid(path, ledger)

    @classmethod
    def path_for_epoch_id(
        cls,
        epoch_id: str,
        repository_root: str | Path,
    ) -> Path:
        """Return the one canonical ledger path for an epoch identity."""

        normalized_epoch_id = _normalize_epoch_id(epoch_id)
        root = Path(repository_root).expanduser().resolve()
        return root / _TERMINAL_LEDGER_DIRECTORY / (
            "epoch-" + normalized_epoch_id.split(":", 1)[-1] + ".json"
        )

    @classmethod
    def load_for_epoch_id(
        cls,
        epoch_id: str,
        repository_root: str | Path,
    ) -> "CompletionEpochLedgerLoadResult":
        """Load a structurally valid ledger before binding it to a plan.

        This is intentionally narrower than ``load_for_plan``: it checks only
        the deterministic address and the current ledger schema/fingerprint.
        Callers that have a frozen plan MUST use ``load_for_plan`` as the
        final identity check.  The helper exists so a repair owner can first
        recover the prior epoch identity from a typed link and then rebuild
        the exact prior plan for that binding check.
        """

        root = Path(repository_root).expanduser().resolve()
        try:
            normalized_epoch_id = _normalize_epoch_id(epoch_id)
            path = cls.path_for_epoch_id(normalized_epoch_id, root)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            return CompletionEpochLedgerLoadResult.invalid(
                root / _TERMINAL_LEDGER_DIRECTORY / "<invalid-epoch-id>.json",
                str(exc),
            )
        # Check symlinks before ``exists``: a broken link has no target and
        # would otherwise be misclassified as a safe cache miss.
        if path.is_symlink():
            return CompletionEpochLedgerLoadResult.invalid(
                path,
                "completion epoch terminal ledger path must not be a symlink",
            )
        if not path.exists():
            return CompletionEpochLedgerLoadResult.absent(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            return CompletionEpochLedgerLoadResult.invalid(path, str(exc))
        try:
            if not isinstance(payload, Mapping):
                raise ValueError("completion epoch terminal ledger payload must be an object")
            ledger = cls.from_dict(payload)
            if ledger.epoch_id != normalized_epoch_id:
                raise ValueError(
                    "completion epoch terminal ledger epoch identity does not match its address"
                )
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            return CompletionEpochLedgerLoadResult.invalid(path, str(exc))
        return CompletionEpochLedgerLoadResult.valid(path, ledger)

    def write(self, repository_root: str | Path) -> Path:
        """Write this ledger below ``.flowguard/evidence`` only.

        The filename is content-addressed.  Existing identical output is
        reusable; different content at the same address is rejected.  No
        source, Git index, task file, or release input is touched.
        """

        root = Path(repository_root).expanduser().resolve()
        evidence_root = (root / _TERMINAL_LEDGER_DIRECTORY).resolve()
        if root not in evidence_root.parents:
            raise ValueError("completion epoch ledger evidence root escaped repository root")
        evidence_root.mkdir(parents=True, exist_ok=True)
        content = (_canonical_json(self.to_dict()) + b"\n")
        path = evidence_root / self.output_filename
        if path.is_symlink():
            raise ValueError("completion epoch terminal ledger path must not be a symlink")
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError("completion epoch terminal ledger content collision")
            return path
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=evidence_root
        )
        temporary = Path(temporary_name)
        try:
            with open(descriptor, "wb", closefd=True) as handle:
                handle.write(content)
                handle.flush()
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != content:
                    raise ValueError("completion epoch terminal ledger content collision")
        finally:
            temporary.unlink(missing_ok=True)
        return path

    persist = write
    save = write


@dataclass(frozen=True)
class CompletionEpochLedgerLoadResult:
    """Fail-closed result of loading the ledger for one exact plan.

    ``absent`` means no file exists at the deterministic address and is the
    only state which may permit a first attempt.  ``invalid`` means a file was
    present but unreadable, stale, malformed, or not bound to the plan; it
    must block a producer rather than being treated as a cache miss.
    """

    status: str
    path: str
    ledger: CompletionEpochTerminalLedger | None = None
    error: str = ""
    schema_version: str = COMPLETION_EPOCH_LEDGER_SCHEMA

    def __post_init__(self) -> None:
        status = str(self.status).strip()
        if status not in {
            EPOCH_LEDGER_ABSENT,
            EPOCH_LEDGER_VALID,
            EPOCH_LEDGER_INVALID,
        }:
            raise ValueError(f"unsupported completion epoch ledger load status: {status}")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "path", str(self.path).strip())
        error = str(self.error).strip()
        object.__setattr__(self, "error", error)
        if status == EPOCH_LEDGER_VALID:
            if self.ledger is None:
                raise ValueError("valid completion epoch ledger load requires a ledger")
            if error:
                raise ValueError("valid completion epoch ledger load cannot have an error")
        elif self.ledger is not None:
            raise ValueError("absent or invalid completion epoch load cannot expose a ledger")
        elif status == EPOCH_LEDGER_INVALID and not error:
            raise ValueError("invalid completion epoch ledger load requires an error")
        if self.schema_version != COMPLETION_EPOCH_LEDGER_SCHEMA:
            raise ValueError(
                f"unsupported completion epoch ledger load schema: {self.schema_version}"
            )

    @property
    def is_absent(self) -> bool:
        return self.status == EPOCH_LEDGER_ABSENT

    @property
    def is_valid(self) -> bool:
        return self.status == EPOCH_LEDGER_VALID and self.ledger is not None

    @property
    def is_invalid(self) -> bool:
        return self.status == EPOCH_LEDGER_INVALID

    @classmethod
    def absent(cls, path: str | Path) -> "CompletionEpochLedgerLoadResult":
        return cls(status=EPOCH_LEDGER_ABSENT, path=str(path))

    @classmethod
    def valid(
        cls,
        path: str | Path,
        ledger: CompletionEpochTerminalLedger,
    ) -> "CompletionEpochLedgerLoadResult":
        return cls(status=EPOCH_LEDGER_VALID, path=str(path), ledger=ledger)

    @classmethod
    def invalid(
        cls,
        path: str | Path,
        error: str,
    ) -> "CompletionEpochLedgerLoadResult":
        return cls(status=EPOCH_LEDGER_INVALID, path=str(path), error=str(error))


_REPAIR_INPUT_FIELDS = (
    "source_observation_fingerprint",
    "release_tree_fingerprint",
    "toolchain_environment_fingerprint",
    "owner_dag_fingerprint",
    "model_authority_fingerprint",
    "test_inventory_fingerprint",
    "completion_objective_fingerprint",
)
_REPAIR_EVIDENCE_FIELDS = {
    "artifact_fingerprint",
    "cleanup_confirmed",
    "input_fingerprint",
    "producer_invocations",
    "receipt_fingerprint",
    "receipt_id",
    "status",
}


def _write_repair_artifact_once(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Write one repair artifact idempotently without deleting prior evidence."""

    target = Path(path).expanduser().resolve()
    if target.is_symlink():
        raise ValueError(f"completion repair artifact must not be a symlink: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if target.exists():
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"cannot read existing completion repair artifact: {target}"
            ) from exc
        if existing != content:
            raise ValueError(
                f"completion repair artifact already exists with different content: {target}"
            )
        return
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _infer_repair_repository_root(group_path: Path) -> Path:
    """Infer a repository root only for the legacy output-path API."""

    resolved = group_path.resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate.name == ".flowguard":
            return candidate.parent
    # Existing callers historically supplied an arbitrary work path.  Its
    # parent is the narrowest useful scope for the compatibility alias and is
    # never used by the full consumer, which derives the canonical path from
    # the repository root it was given.
    return resolved.parent


def _repair_evidence_rows(
    evidence: Mapping[str, Any],
    *,
    failed_owner_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Validate producer-owned repair evidence and return a canonical copy."""

    if not isinstance(evidence, MappingABC):
        raise ValueError("completion repair evidence must be a mapping")
    if any(not isinstance(key, str) or not key.strip() for key in evidence):
        raise ValueError("completion repair evidence owner ids must be non-empty strings")
    expected_ids = tuple(sorted(failed_owner_ids))
    actual_ids = tuple(sorted(key.strip() for key in evidence))
    if actual_ids != expected_ids:
        missing = sorted(set(expected_ids) - set(actual_ids))
        extra = sorted(set(actual_ids) - set(expected_ids))
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ValueError(
            "completion repair evidence does not cover failed owners exactly"
            + (" (" + "; ".join(details) + ")" if details else "")
        )
    rows: dict[str, dict[str, Any]] = {}
    for owner_id in expected_ids:
        raw = evidence[owner_id]
        if not isinstance(raw, MappingABC):
            raise ValueError(f"completion repair evidence row must be an object: {owner_id}")
        keys = {str(key) for key in raw}
        if keys != _REPAIR_EVIDENCE_FIELDS:
            missing = sorted(_REPAIR_EVIDENCE_FIELDS - keys)
            unknown = sorted(keys - _REPAIR_EVIDENCE_FIELDS)
            details: list[str] = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if unknown:
                details.append("unknown=" + ",".join(unknown))
            raise ValueError(
                f"completion repair evidence fields are not exact-current: {owner_id}"
                + (" (" + "; ".join(details) + ")" if details else "")
            )
        if raw["status"] != "pass":
            raise ValueError(f"completion repair evidence is not a pass: {owner_id}")
        if isinstance(raw["producer_invocations"], bool) or raw["producer_invocations"] != 1:
            raise ValueError(
                f"completion repair evidence must have one producer invocation: {owner_id}"
            )
        if raw["cleanup_confirmed"] is not True:
            raise ValueError(
                f"completion repair evidence cleanup is not confirmed: {owner_id}"
            )
        receipt_id = raw["receipt_id"]
        if not isinstance(receipt_id, str) or not receipt_id.strip():
            raise ValueError(f"completion repair evidence receipt_id is required: {owner_id}")
        row: dict[str, Any] = {
            "artifact_fingerprint": _normalize_fingerprint(
                raw["artifact_fingerprint"],
                f"repair evidence {owner_id} artifact_fingerprint",
            ),
            "cleanup_confirmed": True,
            "input_fingerprint": _normalize_fingerprint(
                raw["input_fingerprint"],
                f"repair evidence {owner_id} input_fingerprint",
            ),
            "producer_invocations": 1,
            "receipt_fingerprint": _normalize_fingerprint(
                raw["receipt_fingerprint"],
                f"repair evidence {owner_id} receipt_fingerprint",
            ),
            "receipt_id": receipt_id.strip(),
            "status": "pass",
        }
        rows[owner_id] = row
    return rows


def produce_completion_repair_link(
    *,
    previous_plan: CompletionEpochPlan,
    current_plan: CompletionEpochPlan,
    previous_ledger: CompletionEpochTerminalLedger,
    repair_evidence: Mapping[str, Any] | None = None,
    repair_group_output_path: str | Path | None = None,
    link_output_path: str | Path | None = None,
    repository_root: str | Path | None = None,
    current_input_fingerprints: Mapping[str, str] | None = None,
    completed_terminal_action_ids: Sequence[str] | None = None,
    reexecute_owner_ids: Sequence[str] | None = None,
    owner_dispositions: Mapping[str, Any] | None = None,
    targeted_regression_evidence: Mapping[str, Any] | None = None,
) -> CompletionRepairLink:
    """Produce one typed repair link from independently verified evidence.

    ``current_plan`` is the newly frozen, *unclaimed* input plan (attempt
    index zero and no repair link).  The function derives both the failed
    action set and changed governed-input map; callers cannot forge either by
    supplying precomputed hashes.  It never reserves a producer, runs a
    check, changes source authority, or deletes working evidence.
    """

    if not isinstance(previous_plan, CompletionEpochPlan):
        raise TypeError("previous_plan must be a CompletionEpochPlan")
    if not isinstance(current_plan, CompletionEpochPlan):
        raise TypeError("current_plan must be a CompletionEpochPlan")
    if not isinstance(previous_ledger, CompletionEpochTerminalLedger):
        raise TypeError("previous_ledger must be a CompletionEpochTerminalLedger")
    if previous_plan.epoch_id != previous_ledger.epoch_id:
        raise ValueError("completion repair previous plan and ledger identity mismatch")
    if previous_plan.attempt_index != 0 or previous_plan.full_producer_attempts != 1:
        raise ValueError("completion repair predecessor must be the claimed initial attempt")
    if previous_ledger.status != EPOCH_ABORTED:
        raise ValueError("completion repair predecessor ledger must be aborted")
    if previous_ledger.full_producer_attempts != 1:
        raise ValueError("completion repair predecessor ledger must record one producer")
    if tuple(previous_ledger.terminal_action_ids) != tuple(
        previous_plan.required_terminal_action_ids
    ):
        raise ValueError("completion repair predecessor action set does not match its plan")
    required = set(previous_plan.required_terminal_action_ids)
    completed = set(previous_ledger.completed_terminal_action_ids)
    if not completed.issubset(required):
        raise ValueError("completion repair predecessor contains foreign completed actions")
    failed_owner_ids = tuple(sorted(required - completed))
    if not failed_owner_ids:
        raise ValueError("completion repair predecessor has no failed owner")
    if current_plan.attempt_index != 0 or current_plan.full_producer_attempts != 0:
        raise ValueError("completion repair current plan must be frozen and unclaimed")
    if current_plan.repair_link is not None:
        raise ValueError("completion repair current plan must not already contain a link")
    if current_plan.required_terminal_action_ids != previous_plan.required_terminal_action_ids:
        raise ValueError("completion repair current plan changes required terminal actions")
    if current_plan.maintenance_unit_id != previous_plan.maintenance_unit_id:
        raise ValueError("completion repair current plan changes maintenance unit")
    if current_plan.completion_work_id != previous_plan.completion_work_id:
        raise ValueError("completion repair current plan changes completion work id")
    if current_plan.claim_scope != previous_plan.claim_scope:
        raise ValueError("completion repair current plan changes claim scope")
    if current_plan.completion_cycle_id != previous_plan.completion_cycle_id:
        raise ValueError("completion repair current plan changes its completion cycle")
    if current_plan.completion_cycle_seed_fingerprint != previous_plan.completion_cycle_seed_fingerprint:
        raise ValueError("completion repair current plan changes its completion cycle seed")
    changed = {
        field_name: getattr(current_plan, field_name)
        for field_name in _REPAIR_INPUT_FIELDS
        if getattr(current_plan, field_name) != getattr(previous_plan, field_name)
    }
    if not changed:
        raise ValueError("completion repair requires at least one changed governed input")
    # The legacy helper accepts owner receipt rows.  New readiness callers can
    # instead provide a source-bound targeted regression artifact; the group
    # still records the exact predecessor failure set and never pretends that
    # this evidence is a terminal full pass.
    supplied_evidence = {} if repair_evidence is None else repair_evidence
    rows: dict[str, dict[str, Any]] = {}
    if supplied_evidence:
        rows = _repair_evidence_rows(
            supplied_evidence,
            failed_owner_ids=failed_owner_ids,
        )
    completed = (
        tuple(previous_ledger.completed_terminal_action_ids)
        if completed_terminal_action_ids is None
        else _normalize_ids(completed_terminal_action_ids, "completed_terminal_action_ids")
    )
    if set(completed) != set(previous_ledger.completed_terminal_action_ids):
        raise ValueError("completion repair completed actions do not match predecessor ledger")
    reexecute = (
        failed_owner_ids
        if reexecute_owner_ids is None
        else _normalize_ids(reexecute_owner_ids, "reexecute_owner_ids")
    )
    if not set(reexecute).issubset(set(failed_owner_ids)):
        raise ValueError("completion repair reexecute owners are not all failed owners")
    current_inputs = {
        field_name: getattr(current_plan, field_name)
        for field_name in _REPAIR_INPUT_FIELDS
    }
    if current_input_fingerprints is not None:
        supplied_current_inputs = _normalize_fingerprint_map(
            current_input_fingerprints,
            "current_input_fingerprints",
        )
        if supplied_current_inputs != current_inputs:
            raise ValueError(
                "completion repair current input fingerprints do not match the frozen plan"
            )
    dispositions = (
        {
            owner_id: ("reexecute" if owner_id in set(failed_owner_ids) else "reuse_current")
            for owner_id in previous_plan.required_terminal_action_ids
        }
        if owner_dispositions is None
        else owner_dispositions
    )
    regression = (
        {
            "schema_version": "flowguard.completion_repair_regression_evidence.v1",
            "scope": "targeted_patch_regression",
            "status": "pass",
            "exit_code": 0,
            "cleanup_confirmed": True,
            "tested_input_manifest": current_inputs,
            "owner_ids": list(failed_owner_ids),
            "receipt_ids": sorted(
                str(row["receipt_id"]) for row in rows.values()
            ),
            "producer_invocations": 0,
        }
        if targeted_regression_evidence is None
        else targeted_regression_evidence
    )
    group = CompletionRepairAdmissionGroup(
        repair_kind="attempt_admission",
        completion_cycle_id=previous_plan.completion_cycle_id,
        previous_epoch_id=previous_plan.epoch_id,
        previous_attempt_index=previous_plan.attempt_index,
        previous_full_producer_attempts=previous_plan.full_producer_attempts,
        previous_ledger_fingerprint=previous_ledger.fingerprint,
        current_unlinked_epoch_id=current_plan.epoch_id,
        current_plan_input_fingerprint=current_plan.epoch_id,
        current_input_fingerprints=(
            current_inputs
            if current_input_fingerprints is None
            else current_input_fingerprints
        ),
        changed_input_fingerprints=changed,
        required_terminal_action_ids=previous_plan.required_terminal_action_ids,
        completed_terminal_action_ids=completed,
        failed_owner_ids=failed_owner_ids,
        reexecute_owner_ids=reexecute,
        owner_dispositions=dispositions,
        targeted_regression_evidence=regression,
        producer_invocations=0,
    )
    repair_group_id = group.fingerprint
    repair_receipt_fingerprint = group.fingerprint
    link = CompletionRepairLink(
        completion_cycle_id=previous_plan.completion_cycle_id,
        previous_epoch_id=previous_plan.epoch_id,
        previous_attempt_index=previous_plan.attempt_index,
        repair_group_id=repair_group_id,
        failed_owner_ids=failed_owner_ids,
        repair_receipt_fingerprint=repair_receipt_fingerprint,
        changed_input_fingerprints=changed,
    )
    group_payload = group.to_dict()
    if repair_group_output_path is not None or repository_root is not None:
        requested_group_path = (
            Path(repair_group_output_path).expanduser().resolve()
            if repair_group_output_path is not None
            else None
        )
        inferred_root = (
            Path(repository_root).expanduser().resolve()
            if repository_root is not None
            else _infer_repair_repository_root(requested_group_path)
        )
        canonical_group_path = CompletionRepairAdmissionGroup.path_for(
            inferred_root,
            repair_group_id,
        )
        _write_repair_artifact_once(canonical_group_path, group_payload)
        # Keep the old helper's requested output as a non-authoritative
        # convenience copy.  Consumers always derive/reload the canonical
        # content-addressed path from the typed link above.
        if requested_group_path is not None and requested_group_path != canonical_group_path:
            _write_repair_artifact_once(requested_group_path, group_payload)
    if link_output_path is not None:
        _write_repair_artifact_once(link_output_path, link.to_dict())
    return link


def _optional_text(value: Any, field_name: str) -> str:
    """Normalize an optional wire string without coercing arbitrary values."""

    if not isinstance(value, str):
        raise ValueError(f"completion cycle reservation {field_name} must be a string")
    return value.strip()


def _repository_root_path(repository_root: str | Path) -> Path:
    root = Path(repository_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"completion cycle reservation repository root is not a directory: {root}")
    return root


def _repository_root_identity_aliases(repository_root: str | Path) -> tuple[str, ...]:
    """Return host and WSL spellings for one physical repository root.

    Completion reservations are durable across the Windows host and the
    user-level WSL formal runner.  Historical records contain the spelling
    that created them (for example ``D:\\FlowGuard_20260427``), while the
    formal runner sees ``/mnt/d/FlowGuard_20260427``.  Both are the same
    scope; accepting only one spelling would turn a settled reservation into
    a false store-corruption blocker.  Keep aliases narrow to an exact
    drive-letter/``/mnt`` conversion so unrelated roots never match.
    """

    root = _repository_root_path(repository_root)
    original = str(root).strip().rstrip("/\\")
    raw = original.replace("\\", "/").rstrip("/")
    aliases = {original, raw, original.casefold(), raw.casefold()}
    windows = _WINDOWS_DRIVE_ROOT_RE.match(raw)
    if windows:
        drive = windows.group("drive").lower()
        rest = windows.group("rest").lstrip("/")
        mounted = f"/mnt/{drive}/{rest}".rstrip("/")
        aliases.update({mounted, mounted.casefold()})
    else:
        mounted = re.match(
            r"^/mnt/(?P<drive>[A-Za-z])(?:/(?P<rest>.*))?$",
            raw,
        )
        if mounted:
            drive = mounted.group("drive").upper()
            rest = (mounted.group("rest") or "").lstrip("/")
            windows_slash = f"{drive}:/{rest}".rstrip("/")
            windows_backslash = f"{drive}:\\{rest}".rstrip("\\")
            aliases.update(
                {
                    windows_slash,
                    windows_backslash,
                    windows_slash.casefold(),
                    windows_backslash.casefold(),
                }
            )
    return tuple(sorted(aliases))


def _repository_root_fingerprints(repository_root: str | Path) -> frozenset[str]:
    root = _repository_root_path(repository_root)
    values = {
        # Preserve the legacy exact spelling used by already-settled
        # reservations, then add the normalized cross-host aliases.
        fingerprint_value({"repository_root": str(root)}),
        *(
            fingerprint_value({"repository_root": alias})
            for alias in _repository_root_identity_aliases(root)
        ),
    }
    return frozenset(values)


def _repository_root_fingerprint(repository_root: str | Path) -> str:
    root = _repository_root_path(repository_root)
    # The path is a scope binding, not part of the immutable completion epoch
    # identity.  A reservation stored in one repository must never be copied
    # into another repository and accepted there.
    return fingerprint_value({"repository_root": str(root)})


def _assert_no_symlink_components(root: Path, relative: Path) -> None:
    """Reject links in the reservation path before creating or reading it."""

    cursor = root
    for component in relative.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise ValueError(
                "completion cycle reservation path must not contain a symlink: "
                f"{cursor}"
            )


def _reservation_directory(repository_root: str | Path, *, create: bool) -> Path:
    root = _repository_root_path(repository_root)
    _assert_no_symlink_components(root, _RESERVATION_DIRECTORY)
    directory = root / _RESERVATION_DIRECTORY
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    elif not directory.exists():
        # A missing reservation store is the only valid ``absent`` state for
        # a first attempt.  Keep returning its deterministic path so callers
        # can distinguish a cache miss from a malformed existing record.
        return directory
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(
            "completion cycle reservation directory must be a real directory: "
            f"{directory}"
        )
    return directory


def _reservation_path_for_epoch_id(epoch_id: str, repository_root: str | Path) -> Path:
    normalized = _normalize_epoch_id(epoch_id)
    directory = _reservation_directory(repository_root, create=False)
    return directory / f"epoch-{normalized.split(':', 1)[-1]}.json"


def _reservation_lock_path(cycle_id: str, repository_root: str | Path) -> Path:
    normalized = _normalize_epoch_id(cycle_id)
    directory = _reservation_directory(repository_root, create=True)
    lock_directory = directory / "locks"
    if lock_directory.is_symlink():
        raise ValueError(
            "completion cycle reservation lock directory must not be a symlink"
        )
    lock_directory.mkdir(parents=True, exist_ok=True)
    return lock_directory / f"cycle-{normalized.split(':', 1)[-1]}.lock"


@contextmanager
def _reservation_store_lock(cycle_id: str, repository_root: str | Path):
    """Acquire a short, process-safe lock for one completion cycle.

    ``O_EXCL`` gives the create operation its cross-process atomic boundary.
    A lock left by an interrupted process is intentionally not reclaimed: the
    corresponding active reservation must be reviewed rather than silently
    retried.  Normal completion removes only this short-lived coordination
    marker; the reservation JSON itself remains durable evidence.
    """

    lock_path = _reservation_lock_path(cycle_id, repository_root)
    descriptor = None
    acquired = False
    try:
        try:
            descriptor = os.open(
                str(lock_path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            )
        except FileExistsError as exc:
            raise CompletionCycleReservationError(
                "completion_cycle_reservation_store_locked",
                "completion cycle reservation store is locked by another producer",
                path=lock_path,
            ) from exc
        acquired = True
        token = uuid.uuid4().hex.encode("ascii")
        os.write(descriptor, token)
        os.fsync(descriptor)
        yield lock_path
    finally:
        if descriptor is not None:
            os.close(descriptor)
        # A lock is only a short critical-section marker.  Do not mask a
        # producer/settlement exception if a best-effort normal cleanup fails.
        if acquired:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass


def _atomic_create_reservation(path: Path, content: bytes) -> None:
    """Create one reservation file without allowing a competing overwrite."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        raise FileExistsError(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with open(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace_reservation(path: Path, content: bytes) -> None:
    """Replace one owner-held reservation while preserving crash safety."""

    if path.is_symlink() or not path.exists():
        raise FileNotFoundError(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with open(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class CompletionCycleReservation:
    """Durable producer admission for one immutable completion epoch.

    The terminal ledger is immutable output.  This record is the persistent
    *before-producer* reservation that closes the cross-process race between
    two callers both observing an absent terminal ledger.  ``status=active``
    is deliberately not reclaimable after an interruption; the absence of
    cleanup proof is a blocker, not permission to start a second producer.
    """

    epoch_id: str
    plan_fingerprint: str
    cycle_id: str
    cycle_seed_fingerprint: str
    completion_objective_fingerprint: str
    completion_cycle_max_attempts: int
    required_terminal_action_ids: tuple[str, ...]
    attempt_index: int
    producer_id: str
    reservation_token: str
    status: str = RESERVATION_ACTIVE
    lease_id: str = ""
    started_at: str = ""
    terminal_at: str = ""
    cleanup_status: str = ""
    terminal_ledger_fingerprint: str = ""
    previous_epoch_id: str = ""
    repair_link_fingerprint: str = ""
    repository_root_fingerprint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = COMPLETION_CYCLE_RESERVATION_SCHEMA
    maintenance_unit_id: str = COMPLETION_MAINTENANCE_UNIT_ID
    completion_work_id: str = COMPLETION_DEFAULT_WORK_ID
    claim_scope: str = COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION

    def __post_init__(self) -> None:
        epoch_id = _normalize_epoch_id(self.epoch_id)
        cycle_id = _normalize_epoch_id(self.cycle_id)
        plan_fingerprint = _normalize_epoch_id(self.plan_fingerprint)
        if plan_fingerprint != epoch_id:
            raise ValueError(
                "completion cycle reservation plan_fingerprint must equal epoch_id"
            )
        object.__setattr__(self, "epoch_id", epoch_id)
        object.__setattr__(self, "cycle_id", cycle_id)
        object.__setattr__(self, "plan_fingerprint", plan_fingerprint)
        object.__setattr__(
            self,
            "maintenance_unit_id",
            _normalize_maintenance_unit_id(self.maintenance_unit_id),
        )
        object.__setattr__(
            self,
            "completion_work_id",
            _normalize_completion_work_id(self.completion_work_id),
        )
        object.__setattr__(self, "claim_scope", _normalize_claim_scope(self.claim_scope))
        for field_name in (
            "cycle_seed_fingerprint",
            "completion_objective_fingerprint",
            "repository_root_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_fingerprint(getattr(self, field_name), field_name),
            )
        maximum_attempts = _normalize_int(
            self.completion_cycle_max_attempts,
            "completion_cycle_max_attempts",
            minimum=1,
            maximum=MAX_COMPLETION_CYCLE_FULL_ATTEMPTS,
        )
        if CompletionCycle.derive_id(
            self.cycle_seed_fingerprint,
            maximum_attempts,
        ) != cycle_id:
            raise ValueError(
                "completion cycle reservation cycle identity is not derived from "
                "its seed and budget"
            )
        object.__setattr__(self, "completion_cycle_max_attempts", maximum_attempts)
        object.__setattr__(
            self,
            "required_terminal_action_ids",
            _normalize_ids(
                self.required_terminal_action_ids,
                "required_terminal_action_ids",
            ),
        )
        attempt_index = _normalize_int(
            self.attempt_index,
            "attempt_index",
            minimum=0,
            maximum=maximum_attempts - 1,
        )
        object.__setattr__(self, "attempt_index", attempt_index)
        producer_id = _optional_text(self.producer_id, "producer_id")
        token = _optional_text(self.reservation_token, "reservation_token")
        if not producer_id:
            raise ValueError("completion cycle reservation producer_id is required")
        if not token:
            raise ValueError("completion cycle reservation reservation_token is required")
        object.__setattr__(self, "producer_id", producer_id)
        object.__setattr__(self, "reservation_token", token)
        status = _optional_text(self.status, "status")
        if status not in {
            RESERVATION_ACTIVE,
            RESERVATION_SETTLED,
            RESERVATION_ABORTED,
        }:
            raise ValueError(f"unsupported completion cycle reservation status: {status}")
        object.__setattr__(self, "status", status)
        for field_name in (
            "lease_id",
            "started_at",
            "terminal_at",
            "cleanup_status",
            "terminal_ledger_fingerprint",
            "previous_epoch_id",
            "repair_link_fingerprint",
        ):
            value = _optional_text(getattr(self, field_name), field_name)
            if field_name == "previous_epoch_id" and value:
                value = _normalize_epoch_id(value)
            object.__setattr__(self, field_name, value)
        if not self.started_at:
            raise ValueError("completion cycle reservation started_at is required")
        if self.status == RESERVATION_ACTIVE:
            if self.terminal_at or self.cleanup_status or self.terminal_ledger_fingerprint:
                raise ValueError(
                    "active completion cycle reservation cannot contain terminal state"
                )
        else:
            if not self.terminal_at:
                raise ValueError(
                    "settled/aborted completion cycle reservation requires terminal_at"
                )
            if not self.cleanup_status:
                raise ValueError(
                    "settled/aborted completion cycle reservation requires cleanup_status"
                )
        if attempt_index == 0 and (self.previous_epoch_id or self.repair_link_fingerprint):
            raise ValueError(
                "initial completion cycle reservation cannot contain repair predecessor"
            )
        if attempt_index > 0 and not self.previous_epoch_id:
            raise ValueError(
                "repair completion cycle reservation requires previous_epoch_id"
            )
        if not isinstance(self.metadata, MappingABC):
            raise ValueError("completion cycle reservation metadata must be an object")
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.schema_version != COMPLETION_CYCLE_RESERVATION_SCHEMA:
            raise ValueError(
                "unsupported completion cycle reservation schema: "
                f"{self.schema_version}"
            )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "epoch_id": self.epoch_id,
            "plan_fingerprint": self.plan_fingerprint,
            "maintenance_unit_id": self.maintenance_unit_id,
            "completion_work_id": self.completion_work_id,
            "claim_scope": self.claim_scope,
            "cycle_id": self.cycle_id,
            "cycle_seed_fingerprint": self.cycle_seed_fingerprint,
            "completion_objective_fingerprint": self.completion_objective_fingerprint,
            "completion_cycle_max_attempts": self.completion_cycle_max_attempts,
            "required_terminal_action_ids": list(self.required_terminal_action_ids),
            "attempt_index": self.attempt_index,
            "producer_id": self.producer_id,
            "reservation_token": self.reservation_token,
            "status": self.status,
            "lease_id": self.lease_id,
            "started_at": self.started_at,
            "terminal_at": self.terminal_at,
            "cleanup_status": self.cleanup_status,
            "terminal_ledger_fingerprint": self.terminal_ledger_fingerprint,
            "previous_epoch_id": self.previous_epoch_id,
            "repair_link_fingerprint": self.repair_link_fingerprint,
            "repository_root_fingerprint": self.repository_root_fingerprint,
            "metadata": dict(self.metadata),
        }
        if include_fingerprint:
            payload["reservation_fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CompletionCycleReservation":
        _strict_payload_keys(
            payload,
            required={
                "schema_version",
                "epoch_id",
                "plan_fingerprint",
                "maintenance_unit_id",
                "completion_work_id",
                "claim_scope",
                "cycle_id",
                "cycle_seed_fingerprint",
                "completion_objective_fingerprint",
                "completion_cycle_max_attempts",
                "required_terminal_action_ids",
                "attempt_index",
                "producer_id",
                "reservation_token",
                "status",
                "lease_id",
                "started_at",
                "terminal_at",
                "cleanup_status",
                "terminal_ledger_fingerprint",
                "previous_epoch_id",
                "repair_link_fingerprint",
                "repository_root_fingerprint",
                "metadata",
            },
            optional={"reservation_fingerprint"},
            context="completion cycle reservation",
        )
        reservation = cls(
            epoch_id=payload["epoch_id"],
            plan_fingerprint=payload["plan_fingerprint"],
            maintenance_unit_id=payload["maintenance_unit_id"],
            completion_work_id=payload["completion_work_id"],
            claim_scope=payload["claim_scope"],
            cycle_id=payload["cycle_id"],
            cycle_seed_fingerprint=payload["cycle_seed_fingerprint"],
            completion_objective_fingerprint=payload["completion_objective_fingerprint"],
            completion_cycle_max_attempts=payload["completion_cycle_max_attempts"],
            required_terminal_action_ids=payload["required_terminal_action_ids"],
            attempt_index=payload["attempt_index"],
            producer_id=payload["producer_id"],
            reservation_token=payload["reservation_token"],
            status=payload["status"],
            lease_id=payload["lease_id"],
            started_at=payload["started_at"],
            terminal_at=payload["terminal_at"],
            cleanup_status=payload["cleanup_status"],
            terminal_ledger_fingerprint=payload["terminal_ledger_fingerprint"],
            previous_epoch_id=payload["previous_epoch_id"],
            repair_link_fingerprint=payload["repair_link_fingerprint"],
            repository_root_fingerprint=payload["repository_root_fingerprint"],
            metadata=payload["metadata"],
            schema_version=payload["schema_version"],
        )
        declared = payload.get("reservation_fingerprint", "")
        if not isinstance(declared, str) or not declared.strip():
            raise ValueError("completion cycle reservation fingerprint is required")
        if declared != reservation.fingerprint:
            raise ValueError("completion cycle reservation fingerprint mismatch")
        return reservation

    @classmethod
    def path_for_epoch_id(
        cls,
        epoch_id: str,
        repository_root: str | Path,
    ) -> Path:
        return _reservation_path_for_epoch_id(epoch_id, repository_root)

    @classmethod
    def load_for_epoch_id(
        cls,
        epoch_id: str,
        repository_root: str | Path,
    ) -> "CompletionCycleReservationLoadResult":
        root = _repository_root_path(repository_root)
        try:
            path = _reservation_path_for_epoch_id(epoch_id, root)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            return CompletionCycleReservationLoadResult.invalid(
                root / _RESERVATION_DIRECTORY / "<invalid-epoch-id>.json",
                str(exc),
            )
        if path.is_symlink():
            return CompletionCycleReservationLoadResult.invalid(
                path,
                "completion cycle reservation path must not be a symlink",
            )
        if not path.exists():
            return CompletionCycleReservationLoadResult.absent(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, MappingABC):
                raise ValueError("completion cycle reservation payload must be an object")
            reservation = cls.from_dict(payload)
            normalized = _normalize_epoch_id(epoch_id)
            if reservation.epoch_id != normalized:
                raise ValueError(
                    "completion cycle reservation epoch identity does not match its address"
                )
            expected_roots = _repository_root_fingerprints(root)
            if reservation.repository_root_fingerprint not in expected_roots:
                raise ValueError(
                    "completion cycle reservation repository identity mismatch"
                )
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError, OverflowError) as exc:
            return CompletionCycleReservationLoadResult.invalid(path, str(exc))
        return CompletionCycleReservationLoadResult.valid(path, reservation)

    @classmethod
    def load_for_plan(
        cls,
        plan: CompletionEpochPlan,
        repository_root: str | Path,
    ) -> "CompletionCycleReservationLoadResult":
        loaded = cls.load_for_epoch_id(plan.epoch_id, repository_root)
        if not loaded.is_valid or loaded.reservation is None:
            return loaded
        reservation = loaded.reservation
        mismatches: list[str] = []
        plan_fields = {
            "epoch_id": "epoch_id",
            "plan_fingerprint": "epoch_id",
            "maintenance_unit_id": "maintenance_unit_id",
            "completion_work_id": "completion_work_id",
            "claim_scope": "claim_scope",
            "cycle_id": "completion_cycle_id",
            "cycle_seed_fingerprint": "completion_cycle_seed_fingerprint",
            "completion_objective_fingerprint": "completion_objective_fingerprint",
            "completion_cycle_max_attempts": "completion_cycle_max_attempts",
            "attempt_index": "attempt_index",
        }
        for field_name in (
            "epoch_id",
            "plan_fingerprint",
            "maintenance_unit_id",
            "completion_work_id",
            "claim_scope",
            "cycle_id",
            "cycle_seed_fingerprint",
            "completion_objective_fingerprint",
            "completion_cycle_max_attempts",
            "attempt_index",
        ):
            expected = getattr(plan, plan_fields[field_name])
            if getattr(reservation, field_name) != expected:
                mismatches.append(field_name)
        if tuple(reservation.required_terminal_action_ids) != tuple(
            plan.required_terminal_action_ids
        ):
            mismatches.append("required_terminal_action_ids")
        expected_previous = (
            plan.repair_link.previous_epoch_id
            if plan.repair_link is not None
            else ""
        )
        if reservation.previous_epoch_id != expected_previous:
            mismatches.append("previous_epoch_id")
        expected_repair = (
            plan.repair_link.fingerprint if plan.repair_link is not None else ""
        )
        if reservation.repair_link_fingerprint != expected_repair:
            mismatches.append("repair_link_fingerprint")
        if mismatches:
            return cls._invalid_loaded(
                loaded.path,
                "completion cycle reservation plan identity mismatch: "
                + ", ".join(sorted(set(mismatches))),
            )
        return loaded

    @classmethod
    def _invalid_loaded(
        cls,
        path: str | Path,
        error: str,
    ) -> "CompletionCycleReservationLoadResult":
        return CompletionCycleReservationLoadResult.invalid(path, error)

    def write_new(self, repository_root: str | Path) -> Path:
        root = _repository_root_path(repository_root)
        expected_roots = _repository_root_fingerprints(root)
        if self.repository_root_fingerprint not in expected_roots:
            raise ValueError("completion cycle reservation repository identity mismatch")
        path = self.path_for_epoch_id(self.epoch_id, root)
        _atomic_create_reservation(path, _canonical_json(self.to_dict()) + b"\n")
        return path


class CompletionCycleReservationError(RuntimeError):
    """Fail-closed producer admission/settlement error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str | Path | None = None,
        blockers: Sequence[str] = (),
    ) -> None:
        self.code = str(code).strip() or "completion_cycle_reservation_blocked"
        self.path = str(path).strip() if path is not None else ""
        self.blockers = tuple(str(item).strip() for item in blockers if str(item).strip())
        super().__init__(f"{self.code}: {str(message).strip()}")


@dataclass(frozen=True)
class CompletionCycleReservationLoadResult:
    """Current reservation lookup, distinct from absent/invalid terminal ledger."""

    status: str
    path: str
    reservation: CompletionCycleReservation | None = None
    error: str = ""
    schema_version: str = COMPLETION_CYCLE_RESERVATION_SCHEMA

    def __post_init__(self) -> None:
        status = _optional_text(self.status, "load status")
        if status not in {
            RESERVATION_ABSENT,
            RESERVATION_VALID,
            RESERVATION_INVALID,
        }:
            raise ValueError(f"unsupported completion cycle reservation load status: {status}")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "path", _optional_text(self.path, "load path"))
        error = _optional_text(self.error, "load error")
        object.__setattr__(self, "error", error)
        if status == RESERVATION_VALID:
            if self.reservation is None:
                raise ValueError("valid completion cycle reservation requires a reservation")
            if error:
                raise ValueError("valid completion cycle reservation cannot have an error")
        elif self.reservation is not None:
            raise ValueError("absent/invalid reservation load cannot expose a reservation")
        elif status == RESERVATION_INVALID and not error:
            raise ValueError("invalid completion cycle reservation requires an error")
        if self.schema_version != COMPLETION_CYCLE_RESERVATION_SCHEMA:
            raise ValueError(
                "unsupported completion cycle reservation load schema: "
                f"{self.schema_version}"
            )

    @property
    def is_absent(self) -> bool:
        return self.status == RESERVATION_ABSENT

    @property
    def is_valid(self) -> bool:
        return self.status == RESERVATION_VALID and self.reservation is not None

    @property
    def is_invalid(self) -> bool:
        return self.status == RESERVATION_INVALID

    @classmethod
    def absent(cls, path: str | Path) -> "CompletionCycleReservationLoadResult":
        return cls(status=RESERVATION_ABSENT, path=str(path))

    @classmethod
    def valid(
        cls,
        path: str | Path,
        reservation: CompletionCycleReservation,
    ) -> "CompletionCycleReservationLoadResult":
        return cls(status=RESERVATION_VALID, path=str(path), reservation=reservation)

    @classmethod
    def invalid(
        cls,
        path: str | Path,
        error: str,
    ) -> "CompletionCycleReservationLoadResult":
        return cls(status=RESERVATION_INVALID, path=str(path), error=str(error))


def _cycle_history(
    plan: CompletionEpochPlan,
    repository_root: str | Path,
) -> tuple[tuple[str, Any], ...]:
    """Read current-cycle reservation and terminal history before admission."""

    root = _repository_root_path(repository_root)
    history: list[tuple[str, Any]] = []
    reservation_dir = _reservation_directory(root, create=False)
    if reservation_dir.exists():
        for path in sorted(reservation_dir.glob("epoch-*.json"), key=lambda item: item.name):
            if path.is_symlink():
                raise CompletionCycleReservationError(
                    "completion_cycle_reservation_store_invalid",
                    "reservation store contains a symlink",
                    path=path,
                )
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, MappingABC):
                    raise ValueError("reservation payload must be an object")
                # Historical reservations can predate the current identity
                # fields (for example ``completion_work_id`` and
                # ``claim_scope``).  They remain durable diagnostics, but an
                # unrelated cycle must not make a new work item impossible to
                # admit.  The cycle id is the minimum stable discriminator;
                # only a record that names this exact cycle is parsed as
                # current evidence.  Records with no usable cycle id still
                # fail closed because they cannot be safely attributed.
                raw_cycle_id = payload.get("cycle_id")
                if isinstance(raw_cycle_id, str) and raw_cycle_id.strip():
                    try:
                        normalized_cycle_id = _normalize_epoch_id(raw_cycle_id)
                    except (TypeError, ValueError, KeyError, OverflowError) as exc:
                        raise ValueError(
                            f"invalid reservation cycle_id: {exc}"
                        ) from exc
                    if normalized_cycle_id != plan.completion_cycle_id:
                        continue
                reservation = CompletionCycleReservation.from_dict(payload)
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError, OverflowError) as exc:
                # This is a current reservation store, so an unreadable entry
                # cannot be safely ignored: doing so would permit a cycle
                # budget bypass through a damaged record.
                raise CompletionCycleReservationError(
                    "completion_cycle_reservation_store_invalid",
                    f"invalid reservation record: {exc}",
                    path=path,
                ) from exc
            expected_name = (
                "epoch-"
                + reservation.epoch_id.split(":", 1)[-1]
                + ".json"
            )
            if path.name != expected_name:
                raise CompletionCycleReservationError(
                    "completion_cycle_reservation_store_invalid",
                    "reservation record identity does not match its address",
                    path=path,
                )
            if reservation.repository_root_fingerprint not in _repository_root_fingerprints(root):
                raise CompletionCycleReservationError(
                    "completion_cycle_reservation_store_invalid",
                    "reservation repository identity mismatch",
                    path=path,
                )
            if reservation.cycle_id == plan.completion_cycle_id:
                if (
                    reservation.maintenance_unit_id != plan.maintenance_unit_id
                    or reservation.completion_work_id != plan.completion_work_id
                    or reservation.claim_scope != plan.claim_scope
                    or
                    reservation.cycle_seed_fingerprint
                    != plan.completion_cycle_seed_fingerprint
                    or reservation.completion_cycle_max_attempts
                    != plan.completion_cycle_max_attempts
                ):
                    raise CompletionCycleReservationError(
                        "completion_cycle_reservation_store_invalid",
                        "matching reservation cycle identity is inconsistent with the plan",
                        path=path,
                    )
                history.append(("reservation", reservation))

    # Existing terminal ledgers are the migration/continuity source for a
    # cycle created before reservations existed.  Only entries that identify
    # this cycle are bound; unrelated historical ledgers remain outside this
    # plan's scope.  A matching but malformed entry is a blocker.
    ledger_dir = root / _TERMINAL_LEDGER_DIRECTORY
    if ledger_dir.is_dir() and not ledger_dir.is_symlink():
        for path in sorted(ledger_dir.glob("epoch-*.json"), key=lambda item: item.name):
            if path.is_symlink():
                raise CompletionCycleReservationError(
                    "completion_cycle_terminal_history_invalid",
                    "terminal history contains a symlink",
                    path=path,
                )
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                # We cannot attribute a malformed legacy path to a cycle until
                # its JSON identifies one, so leave unrelated history alone.
                # The exact current epoch is checked separately by
                # ``load_for_plan`` before producer admission.
                continue
            if not isinstance(payload, MappingABC):
                continue
            if payload.get("completion_cycle_id") != plan.completion_cycle_id:
                continue
            try:
                ledger = CompletionEpochTerminalLedger.from_dict(payload)
            except (TypeError, ValueError, KeyError, OverflowError) as exc:
                raise CompletionCycleReservationError(
                    "completion_cycle_terminal_history_invalid",
                    f"invalid matching terminal history: {exc}",
                    path=path,
                ) from exc
            if (
                ledger.maintenance_unit_id != plan.maintenance_unit_id
                or ledger.completion_work_id != plan.completion_work_id
                or ledger.claim_scope != plan.claim_scope
                or
                ledger.completion_cycle_seed_fingerprint
                != plan.completion_cycle_seed_fingerprint
                or ledger.completion_cycle_max_attempts
                != plan.completion_cycle_max_attempts
            ):
                raise CompletionCycleReservationError(
                    "completion_cycle_terminal_history_invalid",
                    "matching terminal history cycle identity is inconsistent with the plan",
                    path=path,
                )
            history.append(("ledger", ledger))
    return tuple(history)


def _reservation_cycle_blockers(
    plan: CompletionEpochPlan,
    history: Sequence[tuple[str, Any]],
) -> tuple[str, ...]:
    """Return finite-cycle blockers without changing any persistent state."""

    blockers: list[str] = []
    matching = [
        value
        for kind, value in history
        if kind == "reservation" and value.epoch_id == plan.epoch_id
    ]
    if matching:
        current = matching[0]
        if current.status == RESERVATION_ACTIVE:
            blockers.append("completion_cycle_reservation_active")
        else:
            blockers.append("completion_cycle_attempt_already_settled")
        return tuple(blockers)

    same_attempt = [
        value
        for _kind, value in history
        if getattr(value, "attempt_index", None) == plan.attempt_index
    ]
    if same_attempt:
        blockers.append("completion_cycle_attempt_already_consumed")

    if plan.attempt_index == 0:
        # A source change with the same completion objective must not reset the
        # initial attempt counter.  Any prior current-cycle evidence consumes
        # this slot, including historical ledgers written before reservations.
        if history:
            blockers.append("completion_cycle_initial_attempt_already_consumed")
    elif plan.attempt_index >= plan.completion_cycle_max_attempts:
        blockers.append("completion_cycle_attempt_budget_exhausted")
    else:
        repair_link = plan.repair_link
        if repair_link is None:
            blockers.append("completion_cycle_repair_link_missing")
            return tuple(dict.fromkeys(blockers))
        previous = [
            value
            for _kind, value in history
            if getattr(value, "epoch_id", None) == repair_link.previous_epoch_id
            and getattr(value, "attempt_index", None) == plan.attempt_index - 1
        ]
        if not previous:
            blockers.append("completion_cycle_previous_attempt_missing")
        else:
            previous_statuses = {
                getattr(value, "status", "") for value in previous
            }
            if RESERVATION_ACTIVE in previous_statuses:
                blockers.append("completion_cycle_previous_attempt_active")
            # A second attempt is only a typed repair of an aborted first
            # attempt.  A terminal pass can never be reopened.
            if EPOCH_TERMINAL_PASS in previous_statuses or RESERVATION_SETTLED in previous_statuses:
                # ``settled`` is a positive reservation status, whereas an
                # aborted terminal ledger is the only valid repair predecessor.
                if not any(
                    getattr(value, "status", "") == EPOCH_ABORTED
                    for _kind, value in history
                    if getattr(value, "epoch_id", None) == repair_link.previous_epoch_id
                ):
                    blockers.append("completion_cycle_previous_attempt_not_aborted")
            if not any(
                getattr(value, "status", "") == EPOCH_ABORTED
                for _kind, value in history
                if getattr(value, "epoch_id", None) == repair_link.previous_epoch_id
            ):
                blockers.append("completion_cycle_previous_attempt_aborted_ledger_missing")
    return tuple(dict.fromkeys(blockers))


def reserve_full_producer(
    plan: CompletionEpochPlan,
    repository_root: str | Path,
    *,
    producer_id: str = "flowguard.full-validation",
    lease_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> tuple[CompletionEpochPlan, CompletionCycleReservation]:
    """Atomically reserve one full producer for ``plan``.

    The caller must invoke this immediately before starting the full producer.
    It returns the in-memory claimed plan plus the durable reservation.  A
    second process, even with a different output directory, receives a typed
    ``CompletionCycleReservationError`` and must not create a run directory.
    """

    if not isinstance(plan, CompletionEpochPlan):
        raise TypeError("reserve_full_producer requires a CompletionEpochPlan")
    if plan.full_producer_attempts:
        raise CompletionCycleReservationError(
            "completion_cycle_plan_already_claimed",
            "completion epoch plan already contains a producer claim",
        )
    if not plan.full_attempt_available:
        raise CompletionCycleReservationError(
            "completion_cycle_attempt_budget_exhausted",
            "completion cycle has no available full producer attempt",
        )
    producer_id = _optional_text(producer_id, "producer_id")
    lease_id = _optional_text(lease_id, "lease_id")
    if not producer_id:
        raise ValueError("producer_id is required")
    root = _repository_root_path(repository_root)
    root_fingerprint = _repository_root_fingerprint(root)
    existing_ledger = CompletionEpochTerminalLedger.load_for_plan(plan, root)
    if existing_ledger.is_invalid:
        raise CompletionCycleReservationError(
            "completion_epoch_terminal_ledger_invalid",
            existing_ledger.error or "terminal ledger is invalid",
            path=existing_ledger.path,
        )
    if existing_ledger.is_valid:
        raise CompletionCycleReservationError(
            "completion_epoch_terminal_already_recorded",
            "completion epoch already has a terminal ledger",
            path=existing_ledger.path,
        )

    try:
        with _reservation_store_lock(plan.completion_cycle_id, root):
            # Re-check all state after entering the atomic critical section.
            existing_ledger = CompletionEpochTerminalLedger.load_for_plan(plan, root)
            if existing_ledger.is_invalid:
                raise CompletionCycleReservationError(
                    "completion_epoch_terminal_ledger_invalid",
                    existing_ledger.error or "terminal ledger is invalid",
                    path=existing_ledger.path,
                )
            if existing_ledger.is_valid:
                raise CompletionCycleReservationError(
                    "completion_epoch_terminal_already_recorded",
                    "completion epoch already has a terminal ledger",
                    path=existing_ledger.path,
                )
            history = _cycle_history(plan, root)
            blockers = _reservation_cycle_blockers(
                plan,
            history,
        )
            if blockers:
                raise CompletionCycleReservationError(
                    blockers[0],
                    ", ".join(blockers),
                    path=CompletionCycleReservation.path_for_epoch_id(plan.epoch_id, root),
                    blockers=blockers,
                )
            now = datetime.now(timezone.utc).isoformat()
            repair_link = plan.repair_link
            reservation = CompletionCycleReservation(
                epoch_id=plan.epoch_id,
                plan_fingerprint=plan.epoch_id,
                maintenance_unit_id=plan.maintenance_unit_id,
                completion_work_id=plan.completion_work_id,
                claim_scope=plan.claim_scope,
                cycle_id=plan.completion_cycle_id,
                cycle_seed_fingerprint=plan.completion_cycle_seed_fingerprint,
                completion_objective_fingerprint=plan.completion_objective_fingerprint,
                completion_cycle_max_attempts=plan.completion_cycle_max_attempts,
                required_terminal_action_ids=plan.required_terminal_action_ids,
                attempt_index=plan.attempt_index,
                producer_id=producer_id,
                reservation_token=uuid.uuid4().hex,
                lease_id=lease_id,
                started_at=now,
                previous_epoch_id=repair_link.previous_epoch_id if repair_link else "",
                repair_link_fingerprint=repair_link.fingerprint if repair_link else "",
                repository_root_fingerprint=root_fingerprint,
                metadata=dict(metadata or {}),
            )
            try:
                reservation.write_new(root)
            except FileExistsError as exc:
                raise CompletionCycleReservationError(
                    "completion_cycle_reservation_race_lost",
                    "another producer reserved this completion epoch",
                    path=reservation.path_for_epoch_id(plan.epoch_id, root),
                ) from exc
    except CompletionCycleReservationError:
        raise
    except (OSError, TypeError, ValueError, KeyError, OverflowError) as exc:
        raise CompletionCycleReservationError(
            "completion_cycle_reservation_store_invalid",
            str(exc),
        ) from exc
    return plan.claim_full_producer(), reservation


def _settle_full_producer(
    reservation: CompletionCycleReservation,
    repository_root: str | Path,
    *,
    status: str,
    terminal_ledger_fingerprint: str = "",
    lease_id: str = "",
    cleanup_status: str = "confirmed",
    metadata: Mapping[str, Any] | None = None,
) -> CompletionCycleReservation:
    if not isinstance(reservation, CompletionCycleReservation):
        raise TypeError("settle_full_producer requires a CompletionCycleReservation")
    status = _optional_text(status, "status")
    if status not in {RESERVATION_SETTLED, RESERVATION_ABORTED}:
        raise ValueError("settlement status must be settled or aborted")
    root = _repository_root_path(repository_root)
    lease_id = _optional_text(lease_id, "lease_id") or reservation.lease_id
    cleanup_status = _optional_text(cleanup_status, "cleanup_status")
    if not cleanup_status:
        raise ValueError("cleanup_status is required")
    ledger_fingerprint = _optional_text(
        terminal_ledger_fingerprint,
        "terminal_ledger_fingerprint",
    )
    with _reservation_store_lock(reservation.cycle_id, root):
        loaded = CompletionCycleReservation.load_for_epoch_id(reservation.epoch_id, root)
        if loaded.is_invalid:
            raise CompletionCycleReservationError(
                "completion_cycle_reservation_invalid",
                loaded.error,
                path=loaded.path,
            )
        if loaded.is_absent or loaded.reservation is None:
            raise CompletionCycleReservationError(
                "completion_cycle_reservation_missing",
                "cannot settle a reservation that is not persisted",
                path=loaded.path,
            )
        current = loaded.reservation
        if current.reservation_token != reservation.reservation_token:
            raise CompletionCycleReservationError(
                "completion_cycle_reservation_owner_mismatch",
                "reservation token does not belong to this producer",
                path=loaded.path,
            )
        if current.status != RESERVATION_ACTIVE:
            if (
                current.status == status
                and (
                    not ledger_fingerprint
                    or current.terminal_ledger_fingerprint == ledger_fingerprint
                )
            ):
                return current
            raise CompletionCycleReservationError(
                "completion_cycle_reservation_already_terminal",
                "completion cycle reservation is already terminal",
                path=loaded.path,
            )
        settled = replace(
            current,
            status=status,
            lease_id=lease_id,
            terminal_at=datetime.now(timezone.utc).isoformat(),
            cleanup_status=cleanup_status,
            terminal_ledger_fingerprint=ledger_fingerprint,
            metadata={**dict(current.metadata), **dict(metadata or {})},
        )
        _atomic_replace_reservation(loaded.path and Path(loaded.path), _canonical_json(settled.to_dict()) + b"\n")
        return settled


def settle_full_producer(
    reservation: CompletionCycleReservation,
    repository_root: str | Path,
    *,
    status: str = RESERVATION_SETTLED,
    terminal_ledger_fingerprint: str = "",
    lease_id: str = "",
    cleanup_status: str = "confirmed",
    metadata: Mapping[str, Any] | None = None,
) -> CompletionCycleReservation:
    """Settle a successful full producer without deleting its reservation."""

    return _settle_full_producer(
        reservation,
        repository_root,
        status=status,
        terminal_ledger_fingerprint=terminal_ledger_fingerprint,
        lease_id=lease_id,
        cleanup_status=cleanup_status,
        metadata=metadata,
    )


def abort_full_producer(
    reservation: CompletionCycleReservation,
    repository_root: str | Path,
    *,
    terminal_ledger_fingerprint: str = "",
    lease_id: str = "",
    cleanup_status: str = "confirmed",
    metadata: Mapping[str, Any] | None = None,
) -> CompletionCycleReservation:
    """Record an aborted full producer; the durable reservation remains."""

    return _settle_full_producer(
        reservation,
        repository_root,
        status=RESERVATION_ABORTED,
        terminal_ledger_fingerprint=terminal_ledger_fingerprint,
        lease_id=lease_id,
        cleanup_status=cleanup_status,
        metadata=metadata,
    )


# ``clear`` is intentionally a semantic alias, not a deletion operation.  It
# is useful to callers that already use the word for closing an execution
# lease, while preserving the fail-closed historical reservation record.
clear_full_producer_reservation = abort_full_producer
reserve_completion_cycle = reserve_full_producer
settle_completion_cycle_reservation = settle_full_producer
load_full_producer_reservation = CompletionCycleReservation.load_for_plan
load_completion_cycle_reservation = CompletionCycleReservation.load_for_plan


__all__ = [
    "COMPLETION_EPOCH_ADMISSION_SCHEMA",
    "COMPLETION_EPOCH_LEDGER_SCHEMA",
    "COMPLETION_EPOCH_READINESS_SCHEMA",
    "COMPLETION_EPOCH_SCHEMA",
    "COMPLETION_CYCLE_SCHEMA",
    "COMPLETION_CYCLE_RESERVATION_SCHEMA",
    "COMPLETION_REPAIR_LINK_SCHEMA",
    "COMPLETION_REPAIR_GROUP_RECEIPT_SCHEMA",
    "COMPLETION_REPAIR_ADMISSION_GROUP_SCHEMA",
    "COMPLETION_AUTHORIZATION_SCHEMA",
    "COMPLETION_MAINTENANCE_UNIT_ID",
    "COMPLETION_DEFAULT_WORK_ID",
    "COMPLETION_CLAIM_SCOPE_LOCAL_VALIDATION",
    "COMPLETION_CLAIM_SCOPE_RELEASE",
    "COMPLETION_CLAIM_SCOPES",
    "MAX_COMPLETION_CYCLE_FULL_ATTEMPTS",
    "EPOCH_ABORTED",
    "EPOCH_ADMITTED",
    "EPOCH_BLOCKED",
    "EPOCH_LEDGER_ABSENT",
    "EPOCH_LEDGER_INVALID",
    "EPOCH_LEDGER_VALID",
    "EPOCH_TERMINAL_PASS",
    "CYCLE_EXHAUSTED",
    "CYCLE_OPEN",
    "CYCLE_REPAIR_REQUIRED",
    "CYCLE_TERMINAL_PASS",
    "RESERVATION_ACTIVE",
    "RESERVATION_SETTLED",
    "RESERVATION_ABORTED",
    "RESERVATION_ABSENT",
    "RESERVATION_VALID",
    "RESERVATION_INVALID",
    "CompletionEpochAdmission",
    "CompletionAuthorization",
    "CompletionEpochAdmissionError",
    "CompletionEpochLedgerLoadResult",
    "CompletionEpochPlan",
    "CompletionEpochReadiness",
    "CompletionEpochSourceDriftError",
    "CompletionEpochTerminalLedger",
    "CompletionCycle",
    "CompletionCycleReservation",
    "CompletionCycleReservationError",
    "CompletionCycleReservationLoadResult",
    "CompletionRepairLink",
    "CompletionRepairAdmissionGroup",
    "load_completion_repair_admission_group",
    "produce_completion_repair_link",
    "normalize_completion_work_id",
    "normalize_completion_claim_scope",
    "normalize_completion_maintenance_unit_id",
    "reserve_full_producer",
    "settle_full_producer",
    "abort_full_producer",
    "clear_full_producer_reservation",
    "reserve_completion_cycle",
    "settle_completion_cycle_reservation",
    "load_full_producer_reservation",
    "load_completion_cycle_reservation",
]
