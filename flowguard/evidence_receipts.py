"""Immutable, freshness-derived evidence receipts for FlowGuard governance.

Receipts in this module are facts about one completed (or failed) producer
run.  They deliberately do not contain an authoritative ``current`` flag.
Freshness and claim eligibility are recomputed by
``verify_evidence_receipt`` against current repository inputs.

Current repository receipts belong under ``.flowguard/evidence/skill-suite``
by default.  They are environment-local evidence and must not be copied into
installed skill packages as universally current truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


EVIDENCE_RECEIPT_SCHEMA_VERSION = "1.0"
DEFAULT_EVIDENCE_DIRECTORY = Path(".flowguard/evidence/skill-suite")

INPUT_HASH_RAW = "raw"
INPUT_HASH_SEMANTIC = "semantic"
INPUT_HASH_BOTH = "both"
INPUT_HASH_POLICIES = {INPUT_HASH_RAW, INPUT_HASH_SEMANTIC, INPUT_HASH_BOTH}

RECEIPT_STATUS_PASS = "pass"
RECEIPT_STATUS_PASS_WITH_GAPS = "pass_with_gaps"
RECEIPT_STATUS_SCOPED = "scoped"
RECEIPT_STATUS_STALE = "stale"
RECEIPT_STATUS_FAIL = "fail"
RECEIPT_STATUS_BLOCKED = "blocked"
RECEIPT_STATUS_SKIPPED = "skipped"
RECEIPT_STATUS_NOT_RUN = "not_run"
RECEIPT_STATUS_PROGRESS_ONLY = "progress_only"
RECEIPT_STATUS_ERROR = "error"
RECEIPT_RESULT_STATUSES = {
    RECEIPT_STATUS_PASS,
    RECEIPT_STATUS_PASS_WITH_GAPS,
    RECEIPT_STATUS_SCOPED,
    RECEIPT_STATUS_STALE,
    RECEIPT_STATUS_FAIL,
    RECEIPT_STATUS_BLOCKED,
    RECEIPT_STATUS_SKIPPED,
    RECEIPT_STATUS_NOT_RUN,
    RECEIPT_STATUS_PROGRESS_ONLY,
    RECEIPT_STATUS_ERROR,
}

VERIFICATION_STATUS_INVALID = "invalid"
VERIFICATION_STATUS_STALE = "stale"

LEGACY_EVIDENCE_CLASSIFICATION = "unbound_historical_evidence"

SAFE_ENVIRONMENT_KEYS = frozenset(
    {
        "flowguard_version",
        "platform_machine",
        "platform_system",
        "python_implementation",
        "python_version",
    }
)

_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?<![A-Za-z0-9_])(?:[A-Z]:[\\/]|\\\\)[^\s\"']+")
_POSIX_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9_:.>/])/(?:[^\s\"']+)")
_SAFE_TOKEN = re.compile(r"^<[A-Z_]+(?::[0-9a-f]{12,64})?>(?:/[^\\]*)?$")
_SAFE_FILE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]+")


class ReceiptValidationError(ValueError):
    """Raised when data cannot form a canonical evidence receipt."""


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def fingerprint_value(value: Any) -> str:
    """Return a deterministic SHA-256 fingerprint for JSON-compatible data."""

    return _sha256(_canonical_json(value).encode("utf-8"))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    return tuple(str(value) for value in values)


def _unique_tuple(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ReceiptValidationError(f"value is not JSON compatible: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _parse_timestamp(value: str, field_name: str) -> datetime:
    if not value:
        raise ReceiptValidationError(f"{field_name} is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ReceiptValidationError(f"{field_name} must be an ISO-8601 timestamp") from exc


def _validate_identifier(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ReceiptValidationError(f"{field_name} is required")
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ReceiptValidationError(f"{field_name} contains an unsafe control character")


def _looks_absolute_path(value: str) -> bool:
    if _SAFE_TOKEN.match(value):
        return False
    return bool(_WINDOWS_ABSOLUTE_PATH.search(value) or _POSIX_ABSOLUTE_PATH.search(value))


def _normalized_root(path: str | os.PathLike[str] | None) -> str:
    if path is None:
        return ""
    return str(Path(path).expanduser().resolve()).replace("\\", "/").rstrip("/")


def _replace_root(text: str, root: str, token: str) -> str:
    if not root:
        return text
    variants = {root, root.replace("/", "\\")}
    result = text
    for variant in sorted(variants, key=len, reverse=True):
        result = re.sub(re.escape(variant), token, result, flags=re.IGNORECASE)
    return result


def tokenize_path(
    path: str | os.PathLike[str],
    *,
    workspace_root: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
    python_prefix: str | os.PathLike[str] | None = None,
) -> str:
    """Tokenize a path without preserving a raw private absolute path."""

    raw = str(path)
    if not raw:
        raise ReceiptValidationError("path is required")
    if _SAFE_TOKEN.match(raw.replace("\\", "/")):
        return raw.replace("\\", "/")

    candidate = raw.replace("\\", "/")
    workspace = _normalized_root(workspace_root)
    user_home = _normalized_root(home if home is not None else Path.home())
    prefix = _normalized_root(python_prefix if python_prefix is not None else sys.prefix)

    for root, token in (
        (workspace, "<WORKSPACE>"),
        (user_home, "<HOME>"),
        (prefix, "<PYTHON_PREFIX>"),
    ):
        if root and (candidate.casefold() == root.casefold() or candidate.casefold().startswith(root.casefold() + "/")):
            suffix = candidate[len(root) :].lstrip("/")
            return token if not suffix else f"{token}/{suffix}"

    if Path(raw).is_absolute() or re.match(r"(?i)^[A-Z]:[\\/]", raw) or raw.startswith("\\\\"):
        return f"<ABS_PATH:{hashlib.sha256(candidate.casefold().encode('utf-8')).hexdigest()[:16]}>"

    if ".." in Path(candidate).parts:
        return f"<REL_PATH:{hashlib.sha256(candidate.encode('utf-8')).hexdigest()[:16]}>"
    return candidate.lstrip("./") or "."


def _tokenize_command_part(
    part: str,
    *,
    workspace_root: str | os.PathLike[str] | None,
    home: str | os.PathLike[str] | None,
    python_prefix: str | os.PathLike[str] | None,
) -> str:
    result = str(part)
    roots = (
        (_normalized_root(workspace_root), "<WORKSPACE>"),
        (_normalized_root(home if home is not None else Path.home()), "<HOME>"),
        (_normalized_root(python_prefix if python_prefix is not None else sys.prefix), "<PYTHON_PREFIX>"),
    )
    for root, token in roots:
        result = _replace_root(result, root, token)
    if any(token in result for _, token in roots):
        result = result.replace("\\", "/")

    def replace_absolute(match: re.Match[str]) -> str:
        raw_path = match.group(0)
        digest = hashlib.sha256(raw_path.replace("\\", "/").casefold().encode("utf-8")).hexdigest()[:16]
        return f"<ABS_PATH:{digest}>"

    result = _WINDOWS_ABSOLUTE_PATH.sub(replace_absolute, result)
    result = _POSIX_ABSOLUTE_PATH.sub(replace_absolute, result)
    return result


def tokenize_command(
    command: str | Sequence[str],
    *,
    workspace_root: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
    python_prefix: str | os.PathLike[str] | None = None,
) -> tuple[str, ...]:
    """Return exact command arguments with absolute paths replaced by tokens."""

    if isinstance(command, str):
        try:
            parts = shlex.split(command, posix=os.name != "nt")
        except ValueError as exc:
            raise ReceiptValidationError("command has invalid quoting") from exc
    else:
        parts = [str(part) for part in command]
    if not parts:
        raise ReceiptValidationError("command is required")
    return tuple(
        _tokenize_command_part(
            part,
            workspace_root=workspace_root,
            home=home,
            python_prefix=python_prefix,
        )
        for part in parts
    )


def _semantic_bytes(data: bytes) -> bytes:
    """Normalize text line endings and JSON structure for semantic hashing."""

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text.encode("utf-8")
    return _canonical_json(parsed).encode("utf-8")


@dataclass(frozen=True)
class InputSnapshot:
    """Hashes for one watched artifact under an explicit comparison policy."""

    artifact_id: str
    path_token: str
    hash_policy: str
    raw_sha256: str = ""
    semantic_sha256: str = ""
    obligation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "path_token", str(self.path_token).replace("\\", "/"))
        object.__setattr__(self, "hash_policy", str(self.hash_policy))
        object.__setattr__(self, "raw_sha256", str(self.raw_sha256))
        object.__setattr__(self, "semantic_sha256", str(self.semantic_sha256))
        object.__setattr__(self, "obligation_ids", _unique_tuple(self.obligation_ids))
        _validate_identifier(self.artifact_id, "input snapshot artifact_id")
        if not self.path_token:
            raise ReceiptValidationError("input snapshot path_token is required")
        if _looks_absolute_path(self.path_token):
            raise ReceiptValidationError("input snapshot path must be tokenized")
        if self.hash_policy not in INPUT_HASH_POLICIES:
            raise ReceiptValidationError(f"unknown input hash policy: {self.hash_policy}")
        if self.hash_policy in {INPUT_HASH_RAW, INPUT_HASH_BOTH} and not self.raw_sha256:
            raise ReceiptValidationError("raw hash is required by input snapshot policy")
        if self.hash_policy in {INPUT_HASH_SEMANTIC, INPUT_HASH_BOTH} and not self.semantic_sha256:
            raise ReceiptValidationError("semantic hash is required by input snapshot policy")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InputSnapshot":
        return cls(
            artifact_id=str(data.get("artifact_id", "")),
            path_token=str(data.get("path_token", "")),
            hash_policy=str(data.get("hash_policy", "")),
            raw_sha256=str(data.get("raw_sha256", "")),
            semantic_sha256=str(data.get("semantic_sha256", "")),
            obligation_ids=_as_tuple(data.get("obligation_ids", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path_token": self.path_token,
            "hash_policy": self.hash_policy,
            "raw_sha256": self.raw_sha256,
            "semantic_sha256": self.semantic_sha256,
            "obligation_ids": list(self.obligation_ids),
        }


def snapshot_bytes(
    artifact_id: str,
    data: bytes,
    *,
    path_token: str,
    hash_policy: str = INPUT_HASH_BOTH,
    obligation_ids: Sequence[str] = (),
) -> InputSnapshot:
    return InputSnapshot(
        artifact_id=artifact_id,
        path_token=path_token,
        hash_policy=hash_policy,
        raw_sha256=_sha256(data),
        semantic_sha256=_sha256(_semantic_bytes(data)),
        obligation_ids=tuple(obligation_ids),
    )


def snapshot_file(
    artifact_id: str,
    path: str | os.PathLike[str],
    *,
    workspace_root: str | os.PathLike[str] | None = None,
    hash_policy: str = INPUT_HASH_BOTH,
    obligation_ids: Sequence[str] = (),
) -> InputSnapshot:
    path_obj = Path(path)
    return snapshot_bytes(
        artifact_id,
        path_obj.read_bytes(),
        path_token=tokenize_path(path_obj, workspace_root=workspace_root),
        hash_policy=hash_policy,
        obligation_ids=obligation_ids,
    )


@dataclass(frozen=True)
class EnvironmentFingerprint:
    """Hashed, allowlisted environment metadata with no user or host fields."""

    metadata: Mapping[str, str]
    fingerprint: str

    def __post_init__(self) -> None:
        normalized = {str(key): str(value) for key, value in self.metadata.items()}
        unknown = set(normalized) - SAFE_ENVIRONMENT_KEYS
        if unknown:
            raise ReceiptValidationError(f"unsafe environment metadata keys: {sorted(unknown)}")
        object.__setattr__(self, "metadata", MappingProxyType(dict(sorted(normalized.items()))))
        object.__setattr__(self, "fingerprint", str(self.fingerprint))
        if not self.fingerprint:
            raise ReceiptValidationError("environment fingerprint is required")

    def to_dict(self) -> dict[str, Any]:
        return {"metadata": dict(self.metadata), "fingerprint": self.fingerprint}


def build_environment_fingerprint(metadata: Mapping[str, Any]) -> EnvironmentFingerprint:
    normalized = {str(key): str(value) for key, value in metadata.items()}
    unknown = set(normalized) - SAFE_ENVIRONMENT_KEYS
    if unknown:
        raise ReceiptValidationError(f"unsafe environment metadata keys: {sorted(unknown)}")
    ordered = dict(sorted(normalized.items()))
    return EnvironmentFingerprint(ordered, fingerprint_value(ordered))


def capture_environment_fingerprint(*, flowguard_version: str = "") -> EnvironmentFingerprint:
    metadata = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
    }
    if flowguard_version:
        metadata["flowguard_version"] = str(flowguard_version)
    return build_environment_fingerprint(metadata)


@dataclass(frozen=True)
class ChildReceiptRequirement:
    """Exact child receipt and claim coverage required by a parent receipt."""

    receipt_id: str
    obligation_ids: tuple[str, ...]
    eligible_claim_scopes: tuple[str, ...]
    subject_id: str = ""
    expected_receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "obligation_ids", _unique_tuple(self.obligation_ids))
        object.__setattr__(self, "eligible_claim_scopes", _unique_tuple(self.eligible_claim_scopes))
        object.__setattr__(self, "subject_id", str(self.subject_id))
        object.__setattr__(self, "expected_receipt_fingerprint", str(self.expected_receipt_fingerprint))
        _validate_identifier(self.receipt_id, "child requirement receipt_id")
        if not self.obligation_ids:
            raise ReceiptValidationError("child requirement obligation_ids are required")
        if not self.eligible_claim_scopes:
            raise ReceiptValidationError("child requirement eligible_claim_scopes are required")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ChildReceiptRequirement":
        return cls(
            receipt_id=str(data.get("receipt_id", "")),
            obligation_ids=_as_tuple(data.get("obligation_ids", ())),
            eligible_claim_scopes=_as_tuple(data.get("eligible_claim_scopes", ())),
            subject_id=str(data.get("subject_id", "")),
            expected_receipt_fingerprint=str(data.get("expected_receipt_fingerprint", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "subject_id": self.subject_id,
            "obligation_ids": list(self.obligation_ids),
            "eligible_claim_scopes": list(self.eligible_claim_scopes),
            "expected_receipt_fingerprint": self.expected_receipt_fingerprint,
        }


@dataclass(frozen=True)
class ConsumedChildReceipt:
    receipt_id: str
    receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "receipt_fingerprint", str(self.receipt_fingerprint))
        _validate_identifier(self.receipt_id, "consumed child receipt_id")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConsumedChildReceipt":
        return cls(str(data.get("receipt_id", "")), str(data.get("receipt_fingerprint", "")))

    def to_dict(self) -> dict[str, str]:
        return {"receipt_id": self.receipt_id, "receipt_fingerprint": self.receipt_fingerprint}


@dataclass(frozen=True)
class EvidenceReceipt:
    """Canonical immutable facts emitted by one governance evidence producer."""

    receipt_id: str
    subject_id: str
    subject_kind: str
    producer_id: str
    producer_version: str
    claim_scope: str
    command: tuple[str, ...]
    working_directory_token: str
    started_at: str
    finished_at: str
    exit_code: int
    environment_fingerprint: str
    environment_metadata: Mapping[str, str]
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    input_snapshots: tuple[InputSnapshot, ...]
    proof_artifact_id: str
    proof_artifact_fingerprint: str
    result_status: str
    result_fingerprint: str
    covered_obligations: tuple[str, ...]
    required_child_receipts: tuple[ChildReceiptRequirement, ...] = ()
    consumed_child_receipts: tuple[ConsumedChildReceipt, ...] = ()
    supersedes_receipt_ids: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    claim_boundary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = EVIDENCE_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "receipt_id",
            "subject_id",
            "subject_kind",
            "producer_id",
            "producer_version",
            "claim_scope",
            "working_directory_token",
            "started_at",
            "finished_at",
            "environment_fingerprint",
            "contract_hash",
            "check_manifest_hash",
            "suite_map_hash",
            "proof_artifact_id",
            "proof_artifact_fingerprint",
            "result_status",
            "result_fingerprint",
            "claim_boundary",
            "schema_version",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        command = tokenize_command(self.command) if isinstance(self.command, str) else tuple(str(part) for part in self.command)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "working_directory_token", self.working_directory_token.replace("\\", "/"))
        object.__setattr__(self, "environment_metadata", MappingProxyType(dict(sorted((str(k), str(v)) for k, v in self.environment_metadata.items()))))
        object.__setattr__(
            self,
            "input_snapshots",
            tuple(
                item if isinstance(item, InputSnapshot) else InputSnapshot.from_dict(item)
                for item in self.input_snapshots
            ),
        )
        object.__setattr__(
            self,
            "required_child_receipts",
            tuple(
                item if isinstance(item, ChildReceiptRequirement) else ChildReceiptRequirement.from_dict(item)
                for item in self.required_child_receipts
            ),
        )
        object.__setattr__(
            self,
            "consumed_child_receipts",
            tuple(
                item
                if isinstance(item, ConsumedChildReceipt)
                else ConsumedChildReceipt(item)
                if isinstance(item, str)
                else ConsumedChildReceipt.from_dict(item)
                for item in self.consumed_child_receipts
            ),
        )
        object.__setattr__(self, "covered_obligations", _unique_tuple(self.covered_obligations))
        object.__setattr__(self, "supersedes_receipt_ids", _unique_tuple(self.supersedes_receipt_ids))
        object.__setattr__(self, "skipped_checks", _unique_tuple(self.skipped_checks))
        object.__setattr__(self, "blockers", _unique_tuple(self.blockers))
        object.__setattr__(self, "metadata", _freeze_json(self.metadata))
        self._validate()

    def _validate(self) -> None:
        if self.schema_version != EVIDENCE_RECEIPT_SCHEMA_VERSION:
            raise ReceiptValidationError(f"unsupported evidence receipt schema: {self.schema_version}")
        for name in (
            "receipt_id",
            "subject_id",
            "subject_kind",
            "producer_id",
            "producer_version",
            "claim_scope",
            "environment_fingerprint",
            "contract_hash",
            "check_manifest_hash",
            "suite_map_hash",
            "proof_artifact_id",
            "proof_artifact_fingerprint",
            "result_fingerprint",
            "claim_boundary",
        ):
            _validate_identifier(getattr(self, name), name)
        if not self.command:
            raise ReceiptValidationError("command is required")
        if any(_looks_absolute_path(part) for part in self.command):
            raise ReceiptValidationError("command contains an untokenized absolute path")
        if not self.working_directory_token:
            raise ReceiptValidationError("working_directory_token is required")
        if _looks_absolute_path(self.working_directory_token):
            raise ReceiptValidationError("working directory must be tokenized")
        unknown_environment_keys = set(self.environment_metadata) - SAFE_ENVIRONMENT_KEYS
        if unknown_environment_keys:
            raise ReceiptValidationError(f"unsafe environment metadata keys: {sorted(unknown_environment_keys)}")
        expected_environment = fingerprint_value(dict(self.environment_metadata))
        if self.environment_fingerprint != expected_environment:
            raise ReceiptValidationError("environment fingerprint does not match allowlisted metadata")
        started = _parse_timestamp(self.started_at, "started_at")
        finished = _parse_timestamp(self.finished_at, "finished_at")
        try:
            if finished < started:
                raise ReceiptValidationError("finished_at precedes started_at")
        except TypeError as exc:
            raise ReceiptValidationError("timestamps must use compatible timezone forms") from exc
        if not isinstance(self.exit_code, int) or isinstance(self.exit_code, bool):
            raise ReceiptValidationError("exit_code must be an integer")
        if self.result_status not in RECEIPT_RESULT_STATUSES:
            raise ReceiptValidationError(f"unknown result status: {self.result_status}")
        if not self.input_snapshots:
            raise ReceiptValidationError("input_snapshots are required")
        snapshot_ids = [snapshot.artifact_id for snapshot in self.input_snapshots]
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ReceiptValidationError("input snapshot artifact ids must be unique")
        if not self.covered_obligations:
            raise ReceiptValidationError("covered_obligations are required")
        metadata_text = _canonical_json(_thaw_json(self.metadata))
        if _looks_absolute_path(metadata_text):
            raise ReceiptValidationError("metadata contains an untokenized absolute path")
        requirement_ids = [requirement.receipt_id for requirement in self.required_child_receipts]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ReceiptValidationError("required child receipt ids must be unique")
        consumed_ids = [child.receipt_id for child in self.consumed_child_receipts]
        if len(consumed_ids) != len(set(consumed_ids)):
            raise ReceiptValidationError("consumed child receipt ids must be unique")

    @property
    def fingerprint(self) -> str:
        return receipt_fingerprint(self)

    @property
    def receipt_fingerprint(self) -> str:
        """Compatibility spelling for consumers that label the bound hash."""

        return self.fingerprint

    @property
    def covered_obligation_ids(self) -> tuple[str, ...]:
        return self.covered_obligations

    @property
    def consumed_child_receipt_ids(self) -> tuple[str, ...]:
        return tuple(child.receipt_id for child in self.consumed_child_receipts)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceReceipt":
        if "current" in data:
            raise ReceiptValidationError("authoritative current is forbidden; freshness is derived")
        allowed = {
            "schema_version",
            "receipt_id",
            "subject_id",
            "subject_kind",
            "producer_id",
            "producer_version",
            "claim_scope",
            "command",
            "working_directory_token",
            "started_at",
            "finished_at",
            "exit_code",
            "environment_fingerprint",
            "environment_metadata",
            "contract_hash",
            "check_manifest_hash",
            "suite_map_hash",
            "input_snapshots",
            "proof_artifact_id",
            "proof_artifact_fingerprint",
            "result_status",
            "result_fingerprint",
            "covered_obligations",
            "required_child_receipts",
            "consumed_child_receipts",
            "supersedes_receipt_ids",
            "skipped_checks",
            "blockers",
            "claim_boundary",
            "metadata",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ReceiptValidationError(f"unknown evidence receipt fields: {sorted(unknown)}")
        try:
            return cls(
                schema_version=str(data.get("schema_version", "")),
                receipt_id=str(data.get("receipt_id", "")),
                subject_id=str(data.get("subject_id", "")),
                subject_kind=str(data.get("subject_kind", "")),
                producer_id=str(data.get("producer_id", "")),
                producer_version=str(data.get("producer_version", "")),
                claim_scope=str(data.get("claim_scope", "")),
                command=tuple(str(part) for part in data.get("command", ())),
                working_directory_token=str(data.get("working_directory_token", "")),
                started_at=str(data.get("started_at", "")),
                finished_at=str(data.get("finished_at", "")),
                exit_code=data.get("exit_code"),
                environment_fingerprint=str(data.get("environment_fingerprint", "")),
                environment_metadata=data.get("environment_metadata", {}),
                contract_hash=str(data.get("contract_hash", "")),
                check_manifest_hash=str(data.get("check_manifest_hash", "")),
                suite_map_hash=str(data.get("suite_map_hash", "")),
                input_snapshots=tuple(InputSnapshot.from_dict(item) for item in data.get("input_snapshots", ())),
                proof_artifact_id=str(data.get("proof_artifact_id", "")),
                proof_artifact_fingerprint=str(data.get("proof_artifact_fingerprint", "")),
                result_status=str(data.get("result_status", "")),
                result_fingerprint=str(data.get("result_fingerprint", "")),
                covered_obligations=_as_tuple(data.get("covered_obligations", ())),
                required_child_receipts=tuple(
                    ChildReceiptRequirement.from_dict(item) for item in data.get("required_child_receipts", ())
                ),
                consumed_child_receipts=tuple(
                    ConsumedChildReceipt.from_dict(item) for item in data.get("consumed_child_receipts", ())
                ),
                supersedes_receipt_ids=_as_tuple(data.get("supersedes_receipt_ids", ())),
                skipped_checks=_as_tuple(data.get("skipped_checks", ())),
                blockers=_as_tuple(data.get("blockers", ())),
                claim_boundary=str(data.get("claim_boundary", "")),
                metadata=data.get("metadata", {}),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ReceiptValidationError):
                raise
            raise ReceiptValidationError(str(exc)) from exc

    @classmethod
    def from_json(cls, text: str) -> "EvidenceReceipt":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReceiptValidationError(f"invalid evidence receipt JSON: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ReceiptValidationError("evidence receipt JSON must be an object")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "subject_id": self.subject_id,
            "subject_kind": self.subject_kind,
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "claim_scope": self.claim_scope,
            "command": list(self.command),
            "working_directory_token": self.working_directory_token,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "environment_fingerprint": self.environment_fingerprint,
            "environment_metadata": dict(self.environment_metadata),
            "contract_hash": self.contract_hash,
            "check_manifest_hash": self.check_manifest_hash,
            "suite_map_hash": self.suite_map_hash,
            "input_snapshots": [snapshot.to_dict() for snapshot in self.input_snapshots],
            "proof_artifact_id": self.proof_artifact_id,
            "proof_artifact_fingerprint": self.proof_artifact_fingerprint,
            "result_status": self.result_status,
            "result_fingerprint": self.result_fingerprint,
            "covered_obligations": list(self.covered_obligations),
            "required_child_receipts": [requirement.to_dict() for requirement in self.required_child_receipts],
            "consumed_child_receipts": [child.to_dict() for child in self.consumed_child_receipts],
            "supersedes_receipt_ids": list(self.supersedes_receipt_ids),
            "skipped_checks": list(self.skipped_checks),
            "blockers": list(self.blockers),
            "claim_boundary": self.claim_boundary,
            "metadata": _thaw_json(self.metadata),
        }

    def to_json(self) -> str:
        return canonical_receipt_json(self)


def canonical_receipt_json(receipt: EvidenceReceipt) -> str:
    """Serialize a receipt in the exact canonical form used for fingerprints."""

    return _canonical_json(receipt.to_dict())


def receipt_fingerprint(receipt: EvidenceReceipt) -> str:
    return _sha256(canonical_receipt_json(receipt).encode("utf-8"))


@dataclass(frozen=True)
class ReceiptFinding:
    code: str
    message: str
    artifact_id: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "details", _freeze_json(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "artifact_id": self.artifact_id,
            "details": _thaw_json(self.details),
        }


@dataclass(frozen=True)
class ReceiptVerificationContext:
    """Independently observed current values used to verify one receipt."""

    input_snapshots: Mapping[str, InputSnapshot]
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    producer_id: str
    producer_version: str
    environment_fingerprint: str
    proof_artifact_fingerprint: str
    result_fingerprint: str
    command: tuple[str, ...] = ()
    working_directory_token: str = ""
    proof_artifact_id: str = ""
    required_obligation_ids: tuple[str, ...] = ()
    eligible_claim_scopes: tuple[str, ...] = ()
    child_receipts: Mapping[str, EvidenceReceipt] = field(default_factory=dict)
    child_verification_results: Mapping[str, "ReceiptVerificationResult"] = field(default_factory=dict)
    latest_child_receipt_ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_snapshots",
            MappingProxyType(
                {
                    str(key): value if isinstance(value, InputSnapshot) else InputSnapshot.from_dict(value)
                    for key, value in self.input_snapshots.items()
                }
            ),
        )
        for name in (
            "contract_hash",
            "check_manifest_hash",
            "suite_map_hash",
            "producer_id",
            "producer_version",
            "environment_fingerprint",
            "proof_artifact_fingerprint",
            "result_fingerprint",
            "working_directory_token",
            "proof_artifact_id",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        command = tokenize_command(self.command) if isinstance(self.command, str) else tuple(str(part) for part in self.command)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "required_obligation_ids", _unique_tuple(self.required_obligation_ids))
        object.__setattr__(self, "eligible_claim_scopes", _unique_tuple(self.eligible_claim_scopes))
        object.__setattr__(self, "child_receipts", MappingProxyType(dict(self.child_receipts)))
        object.__setattr__(self, "child_verification_results", MappingProxyType(dict(self.child_verification_results)))
        object.__setattr__(self, "latest_child_receipt_ids", MappingProxyType({str(k): str(v) for k, v in self.latest_child_receipt_ids.items()}))


@dataclass(frozen=True)
class ReceiptVerificationResult:
    receipt_id: str
    current: bool
    eligible: bool
    status: str
    findings: tuple[ReceiptFinding, ...]
    satisfied_obligations: tuple[str, ...]
    minimum_revalidation: tuple[str, ...]
    receipt_fingerprint: str = ""

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings)

    @property
    def ok(self) -> bool:
        return self.eligible and self.status == RECEIPT_STATUS_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "current": self.current,
            "eligible": self.eligible,
            "status": self.status,
            "finding_codes": list(self.finding_codes),
            "findings": [finding.to_dict() for finding in self.findings],
            "satisfied_obligations": list(self.satisfied_obligations),
            "minimum_revalidation": list(self.minimum_revalidation),
        }


_FRESHNESS_FINDING_PREFIXES = (
    "input_",
    "contract_",
    "check_manifest_",
    "suite_map_",
    "producer_",
    "environment_",
    "proof_artifact_",
    "result_fingerprint_",
    "command_",
    "working_directory_",
    "required_child_",
    "consumed_child_",
    "child_",
    "superseded_child",
    "unexpected_consumed_child",
    "verification_context_",
)


def _finding(code: str, message: str, artifact_id: str = "", **details: Any) -> ReceiptFinding:
    return ReceiptFinding(code, message, artifact_id, details)


def _compare_snapshot(expected: InputSnapshot, current: InputSnapshot) -> tuple[ReceiptFinding, ...]:
    findings: list[ReceiptFinding] = []
    if current.path_token != expected.path_token:
        findings.append(
            _finding(
                "input_path_token_mismatch",
                f"input path binding changed for {expected.artifact_id}",
                expected.artifact_id,
                expected=expected.path_token,
                actual=current.path_token,
            )
        )
    if current.hash_policy != expected.hash_policy:
        findings.append(
            _finding(
                "input_hash_policy_changed",
                f"input hash policy changed for {expected.artifact_id}",
                expected.artifact_id,
                expected=expected.hash_policy,
                actual=current.hash_policy,
            )
        )
    if current.obligation_ids != expected.obligation_ids:
        findings.append(
            _finding(
                "input_obligation_scope_mismatch",
                f"input obligation scope changed for {expected.artifact_id}",
                expected.artifact_id,
                expected=expected.obligation_ids,
                actual=current.obligation_ids,
            )
        )
    if expected.hash_policy in {INPUT_HASH_RAW, INPUT_HASH_BOTH} and expected.raw_sha256 != current.raw_sha256:
        findings.append(
            _finding(
                "input_raw_hash_mismatch",
                f"raw bytes changed for {expected.artifact_id}",
                expected.artifact_id,
                semantic_equal=expected.semantic_sha256 == current.semantic_sha256,
            )
        )
    if expected.hash_policy in {INPUT_HASH_SEMANTIC, INPUT_HASH_BOTH} and expected.semantic_sha256 != current.semantic_sha256:
        findings.append(
            _finding(
                "input_semantic_hash_mismatch",
                f"semantic content changed for {expected.artifact_id}",
                expected.artifact_id,
                raw_equal=expected.raw_sha256 == current.raw_sha256,
            )
        )
    return tuple(findings)


def proof_artifact_binding_findings(
    data: EvidenceReceipt | Mapping[str, Any],
    *,
    required_obligation_ids: Sequence[str] = (),
) -> tuple[ReceiptFinding, ...]:
    """Inspect whether a green result is bound to exact governance inputs.

    This accepts raw mappings so a known-bad unbound green report can be
    diagnosed without first being accepted as an ``EvidenceReceipt``.
    """

    raw = data.to_dict() if isinstance(data, EvidenceReceipt) else dict(data)
    findings: list[ReceiptFinding] = []
    required_fields = (
        "command",
        "working_directory_token",
        "producer_id",
        "producer_version",
        "result_status",
        "exit_code",
        "environment_fingerprint",
        "contract_hash",
        "check_manifest_hash",
        "suite_map_hash",
        "input_snapshots",
        "proof_artifact_id",
        "proof_artifact_fingerprint",
        "result_fingerprint",
    )
    missing = tuple(
        field_name
        for field_name in required_fields
        if field_name not in raw or raw.get(field_name) is None or raw.get(field_name) in ("", (), [])
    )
    if missing:
        findings.append(
            _finding(
                "proof_artifact_missing_binding",
                "proof artifact does not bind every required verification input",
                missing_fields=missing,
            )
        )
    malformed_snapshots: list[str] = []
    for item in raw.get("input_snapshots", ()) or ():
        if not isinstance(item, Mapping):
            malformed_snapshots.append("<non-object>")
            continue
        artifact_id = str(item.get("artifact_id", "<missing>"))
        policy = str(item.get("hash_policy", ""))
        if policy not in INPUT_HASH_POLICIES:
            malformed_snapshots.append(artifact_id)
            continue
        if policy in {INPUT_HASH_RAW, INPUT_HASH_BOTH} and not item.get("raw_sha256"):
            malformed_snapshots.append(artifact_id)
        elif policy in {INPUT_HASH_SEMANTIC, INPUT_HASH_BOTH} and not item.get("semantic_sha256"):
            malformed_snapshots.append(artifact_id)
    if malformed_snapshots:
        findings.append(
            _finding(
                "proof_artifact_malformed_input_binding",
                "proof artifact has input bindings without the hashes required by their policies",
                artifact_ids=tuple(malformed_snapshots),
            )
        )
    covered = set(_as_tuple(raw.get("covered_obligations", ())))
    if not covered:
        findings.append(
            _finding(
                "proof_artifact_missing_obligation_coverage",
                "proof artifact lists no covered obligation identifiers",
            )
        )
    required = set(_as_tuple(required_obligation_ids))
    missing_obligations = tuple(sorted(required - covered))
    if missing_obligations:
        findings.append(
            _finding(
                "proof_artifact_missing_required_obligation",
                "proof artifact does not cover every required obligation",
                missing_obligations=missing_obligations,
            )
        )
    if raw.get("result_status") == RECEIPT_STATUS_PASS and raw.get("exit_code") == 0 and findings:
        findings.append(
            _finding(
                "unbound_green_result",
                "a zero-exit passing command without complete bindings remains diagnostic only",
            )
        )
    return tuple(findings)


def _minimum_revalidation(receipt: EvidenceReceipt, findings: Sequence[ReceiptFinding]) -> tuple[str, ...]:
    actions: list[str] = []
    codes = {finding.code for finding in findings}
    snapshots = {snapshot.artifact_id: snapshot for snapshot in receipt.input_snapshots}
    child_requirements = {requirement.receipt_id: requirement for requirement in receipt.required_child_receipts}
    for finding in findings:
        if finding.code.startswith("input_") and finding.artifact_id:
            actions.append(f"refresh-input:{finding.artifact_id}")
            snapshot = snapshots.get(finding.artifact_id)
            if snapshot is not None:
                for obligation_id in snapshot.obligation_ids:
                    actions.append(f"revalidate-obligation:{obligation_id}")
        if finding.code.startswith(("required_child_", "child_", "superseded_child")):
            child_id = str(finding.details.get("receipt_id", ""))
            if child_id:
                actions.append(f"rerun-child:{child_id}")
                requirement = child_requirements.get(child_id)
                if requirement is not None:
                    for obligation_id in requirement.obligation_ids:
                        actions.append(f"revalidate-obligation:{obligation_id}")
    if any(
        code.startswith(
            (
                "input_",
                "contract_",
                "check_manifest_",
                "suite_map_",
                "producer_",
                "environment_",
                "proof_artifact_",
                "result_fingerprint_",
                "command_",
                "working_directory_",
            )
        )
        for code in codes
    ):
        for obligation_id in receipt.covered_obligations:
            actions.append(f"revalidate-obligation:{obligation_id}")
        actions.append(f"rerun-producer:{receipt.subject_id}")
    if any(code.startswith(("required_child_", "consumed_child_", "child_", "superseded_child", "unexpected_consumed_child")) for code in codes):
        actions.append(f"reconsume-children:{receipt.subject_id}")
        actions.append(f"rerun-parent:{receipt.subject_id}")
    return _unique_tuple(actions)


def minimum_revalidation(
    receipt: EvidenceReceipt,
    findings: Sequence[ReceiptFinding] | ReceiptVerificationResult,
) -> tuple[str, ...]:
    finding_values = findings.findings if isinstance(findings, ReceiptVerificationResult) else tuple(findings)
    return _minimum_revalidation(receipt, finding_values)


def verify_evidence_receipt(
    receipt: EvidenceReceipt | Mapping[str, Any],
    context: ReceiptVerificationContext | None,
) -> ReceiptVerificationResult:
    """Derive freshness, eligibility, status, and minimum revalidation."""

    try:
        canonical = receipt if isinstance(receipt, EvidenceReceipt) else EvidenceReceipt.from_dict(receipt)
    except ReceiptValidationError as exc:
        finding = _finding("invalid_receipt", str(exc))
        return ReceiptVerificationResult(
            receipt_id=str(receipt.get("receipt_id", "")) if isinstance(receipt, Mapping) else "",
            current=False,
            eligible=False,
            status=VERIFICATION_STATUS_INVALID,
            findings=(finding,),
            satisfied_obligations=(),
            minimum_revalidation=("recreate-receipt",),
        )

    if context is None:
        finding = _finding(
            "verification_context_missing",
            "freshness cannot be derived without independently observed current values",
        )
        return ReceiptVerificationResult(
            receipt_id=canonical.receipt_id,
            receipt_fingerprint=canonical.fingerprint,
            current=False,
            eligible=False,
            status=VERIFICATION_STATUS_STALE,
            findings=(finding,),
            satisfied_obligations=(),
            minimum_revalidation=(f"reverify:{canonical.subject_id}",),
        )

    findings: list[ReceiptFinding] = []
    satisfied = set(canonical.covered_obligations)

    for expected in canonical.input_snapshots:
        current_snapshot = context.input_snapshots.get(expected.artifact_id)
        if current_snapshot is None:
            findings.append(
                _finding(
                    "input_snapshot_missing",
                    f"current snapshot is missing for {expected.artifact_id}",
                    expected.artifact_id,
                )
            )
            continue
        findings.extend(_compare_snapshot(expected, current_snapshot))

    comparisons = (
        ("contract_hash", canonical.contract_hash, context.contract_hash),
        ("check_manifest_hash", canonical.check_manifest_hash, context.check_manifest_hash),
        ("suite_map_hash", canonical.suite_map_hash, context.suite_map_hash),
        ("producer_id", canonical.producer_id, context.producer_id),
        ("producer_version", canonical.producer_version, context.producer_version),
        ("environment_fingerprint", canonical.environment_fingerprint, context.environment_fingerprint),
        ("proof_artifact_fingerprint", canonical.proof_artifact_fingerprint, context.proof_artifact_fingerprint),
        ("result_fingerprint", canonical.result_fingerprint, context.result_fingerprint),
        ("working_directory_token", canonical.working_directory_token, context.working_directory_token),
        ("proof_artifact_id", canonical.proof_artifact_id, context.proof_artifact_id),
    )
    for field_name, expected, actual in comparisons:
        if not actual:
            findings.append(_finding(f"{field_name}_missing", f"current {field_name} is unavailable"))
        elif expected != actual:
            findings.append(
                _finding(
                    f"{field_name}_mismatch",
                    f"current {field_name} differs from the receipt binding",
                    expected=expected,
                    actual=actual,
                )
            )
    if not context.command:
        findings.append(_finding("command_missing", "current command binding is unavailable"))
    elif canonical.command != context.command:
        findings.append(
            _finding(
                "command_mismatch",
                "current command differs from the receipt binding",
                expected=canonical.command,
                actual=context.command,
            )
        )

    required_obligations = set(context.required_obligation_ids)
    missing_own_obligations = tuple(sorted(required_obligations - set(canonical.covered_obligations)))
    if missing_own_obligations:
        findings.append(
            _finding(
                "proof_artifact_missing_required_obligation",
                "receipt does not cover every required obligation",
                missing_obligations=missing_own_obligations,
            )
        )
        satisfied.difference_update(missing_own_obligations)

    if context.eligible_claim_scopes and canonical.claim_scope not in context.eligible_claim_scopes:
        findings.append(
            _finding(
                "claim_scope_ineligible",
                f"receipt claim scope {canonical.claim_scope!r} is not eligible",
                eligible_claim_scopes=context.eligible_claim_scopes,
            )
        )

    consumed = {item.receipt_id: item for item in canonical.consumed_child_receipts}
    required_ids = {requirement.receipt_id for requirement in canonical.required_child_receipts}
    for unexpected in sorted(set(consumed) - required_ids):
        findings.append(
            _finding(
                "unexpected_consumed_child_receipt",
                f"parent consumes undeclared child receipt {unexpected}",
                receipt_id=unexpected,
            )
        )

    for requirement in canonical.required_child_receipts:
        child = context.child_receipts.get(requirement.receipt_id)
        consumed_link = consumed.get(requirement.receipt_id)
        if consumed_link is None:
            findings.append(
                _finding(
                    "required_child_not_consumed",
                    f"required child receipt {requirement.receipt_id} was not consumed",
                    receipt_id=requirement.receipt_id,
                )
            )
        if child is None:
            findings.append(
                _finding(
                    "required_child_receipt_missing",
                    f"required child receipt {requirement.receipt_id} is unavailable",
                    receipt_id=requirement.receipt_id,
                )
            )
            continue

        latest_key = requirement.subject_id or child.subject_id
        latest_id = context.latest_child_receipt_ids.get(latest_key, "")
        if latest_id and latest_id != requirement.receipt_id:
            findings.append(
                _finding(
                    "superseded_child_receipt",
                    f"required child {requirement.receipt_id} was superseded by {latest_id}",
                    receipt_id=requirement.receipt_id,
                    latest_receipt_id=latest_id,
                )
            )
        for candidate in context.child_receipts.values():
            if requirement.receipt_id in candidate.supersedes_receipt_ids:
                findings.append(
                    _finding(
                        "superseded_child_receipt",
                        f"required child {requirement.receipt_id} was superseded by {candidate.receipt_id}",
                        receipt_id=requirement.receipt_id,
                        latest_receipt_id=candidate.receipt_id,
                    )
                )
                break

        actual_fingerprint = child.fingerprint
        if consumed_link is not None:
            if consumed_link.receipt_fingerprint and consumed_link.receipt_fingerprint != actual_fingerprint:
                findings.append(
                    _finding(
                        "consumed_child_fingerprint_mismatch",
                        f"consumed fingerprint for {requirement.receipt_id} does not match the child",
                        receipt_id=requirement.receipt_id,
                    )
                )
            if not consumed_link.receipt_fingerprint and not requirement.expected_receipt_fingerprint:
                findings.append(
                    _finding(
                        "consumed_child_fingerprint_missing",
                        f"consumed child {requirement.receipt_id} has no bound fingerprint",
                        receipt_id=requirement.receipt_id,
                    )
                )
        if requirement.expected_receipt_fingerprint and requirement.expected_receipt_fingerprint != actual_fingerprint:
            findings.append(
                _finding(
                    "required_child_fingerprint_mismatch",
                    f"required fingerprint for {requirement.receipt_id} changed",
                    receipt_id=requirement.receipt_id,
                )
            )
        missing_child_obligations = tuple(sorted(set(requirement.obligation_ids) - set(child.covered_obligations)))
        if missing_child_obligations:
            findings.append(
                _finding(
                    "child_obligation_missing",
                    f"child {requirement.receipt_id} does not cover required obligations",
                    receipt_id=requirement.receipt_id,
                    missing_obligations=missing_child_obligations,
                )
            )
        if child.claim_scope not in requirement.eligible_claim_scopes:
            findings.append(
                _finding(
                    "child_claim_scope_ineligible",
                    f"child {requirement.receipt_id} has ineligible claim scope {child.claim_scope!r}",
                    receipt_id=requirement.receipt_id,
                    eligible_claim_scopes=requirement.eligible_claim_scopes,
                )
            )
        child_result = context.child_verification_results.get(requirement.receipt_id)
        if child_result is None:
            findings.append(
                _finding(
                    "child_verification_result_missing",
                    f"child {requirement.receipt_id} has no independently derived verification result",
                    receipt_id=requirement.receipt_id,
                )
            )
        elif not child_result.current or not child_result.eligible or child_result.status != RECEIPT_STATUS_PASS:
            findings.append(
                _finding(
                    "child_receipt_not_current_pass",
                    f"child {requirement.receipt_id} is not a current exact pass",
                    receipt_id=requirement.receipt_id,
                    child_status=child_result.status,
                )
            )
        else:
            satisfied.update(requirement.obligation_ids)

    if canonical.skipped_checks:
        findings.append(
            _finding(
                "receipt_skipped_checks_visible",
                "receipt has skipped checks and cannot support a complete claim",
                skipped_checks=canonical.skipped_checks,
            )
        )
    if canonical.blockers:
        findings.append(
            _finding(
                "receipt_blockers_visible",
                "receipt has blockers and cannot support a complete claim",
                blockers=canonical.blockers,
            )
        )
    findings.extend(proof_artifact_binding_findings(canonical, required_obligation_ids=context.required_obligation_ids))
    # Preserve first occurrence order while preventing duplicate supersession reports.
    deduplicated: list[ReceiptFinding] = []
    seen_finding_keys: set[tuple[str, str, str]] = set()
    for finding in findings:
        key = (finding.code, finding.artifact_id, _canonical_json(_thaw_json(finding.details)))
        if key not in seen_finding_keys:
            deduplicated.append(finding)
            seen_finding_keys.add(key)
    findings = deduplicated

    freshness_failed = any(finding.code.startswith(_FRESHNESS_FINDING_PREFIXES) for finding in findings)
    current = not freshness_failed
    exact_pass = canonical.result_status == RECEIPT_STATUS_PASS and canonical.exit_code == 0
    eligible = (
        current
        and exact_pass
        and not canonical.skipped_checks
        and not canonical.blockers
        and not findings
        and required_obligations.issubset(satisfied)
    )
    if not current:
        status = VERIFICATION_STATUS_STALE
    elif canonical.result_status != RECEIPT_STATUS_PASS:
        status = canonical.result_status
    elif eligible:
        status = RECEIPT_STATUS_PASS
    else:
        status = RECEIPT_STATUS_BLOCKED
    return ReceiptVerificationResult(
        receipt_id=canonical.receipt_id,
        receipt_fingerprint=canonical.fingerprint,
        current=current,
        eligible=eligible,
        status=status,
        findings=tuple(findings),
        satisfied_obligations=tuple(sorted(satisfied)) if eligible else (),
        minimum_revalidation=_minimum_revalidation(canonical, findings),
    )


verify_receipt = verify_evidence_receipt


def evidence_storage_root(
    repository_root: str | os.PathLike[str] = ".",
    *,
    output_directory: str | os.PathLike[str] | None = None,
) -> Path:
    if output_directory is not None:
        result = Path(output_directory).expanduser().resolve()
    else:
        result = (Path(repository_root).expanduser().resolve() / DEFAULT_EVIDENCE_DIRECTORY).resolve()
    lowered = tuple(part.casefold() for part in result.parts)
    forbidden_pair = any(
        lowered[index : index + 2] in {(".agents", "skills"), (".codex", "skills")}
        for index in range(max(0, len(lowered) - 1))
    )
    if "site-packages" in lowered or forbidden_pair:
        raise ReceiptValidationError("current receipts cannot be stored inside an installed or distributable skill package")
    return result


def _receipt_filename(receipt_id: str) -> str:
    safe = (_SAFE_FILE_COMPONENT.sub("_", receipt_id).strip("._") or "receipt")[:96]
    digest = hashlib.sha256(receipt_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe}-{digest}.json"


def receipt_path(
    receipt_id: str,
    repository_root: str | os.PathLike[str] = ".",
    *,
    output_directory: str | os.PathLike[str] | None = None,
) -> Path:
    _validate_identifier(str(receipt_id), "receipt_id")
    return evidence_storage_root(repository_root, output_directory=output_directory) / _receipt_filename(str(receipt_id))


def save_evidence_receipt(
    receipt: EvidenceReceipt,
    repository_root: str | os.PathLike[str] = ".",
    *,
    output_directory: str | os.PathLike[str] | None = None,
) -> Path:
    """Atomically save a canonical receipt under the configured evidence root."""

    serialized = canonical_receipt_json(receipt)
    for private_root in (str(Path.home()), str(Path.home()).replace("\\", "/")):
        if private_root and private_root.casefold() in serialized.casefold():
            raise ReceiptValidationError("canonical receipt leaks a raw home path")
    if _looks_absolute_path(serialized):
        raise ReceiptValidationError("canonical receipt contains an untokenized absolute path")
    target = receipt_path(receipt.receipt_id, repository_root, output_directory=output_directory)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(serialized + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, target)
    return target


def load_evidence_receipt(
    path_or_receipt_id: str | os.PathLike[str],
    repository_root: str | os.PathLike[str] = ".",
    *,
    output_directory: str | os.PathLike[str] | None = None,
) -> EvidenceReceipt:
    candidate = Path(path_or_receipt_id)
    if candidate.exists():
        path = candidate
    else:
        path = receipt_path(str(path_or_receipt_id), repository_root, output_directory=output_directory)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptValidationError(f"cannot load evidence receipt {path.name}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ReceiptValidationError("evidence receipt JSON must be an object")
    receipt = EvidenceReceipt.from_dict(data)
    if path.name != _receipt_filename(receipt.receipt_id) and not candidate.exists():
        raise ReceiptValidationError("evidence receipt filename does not match receipt_id")
    return receipt


def list_evidence_receipts(
    repository_root: str | os.PathLike[str] = ".",
    *,
    output_directory: str | os.PathLike[str] | None = None,
) -> tuple[EvidenceReceipt, ...]:
    root = evidence_storage_root(repository_root, output_directory=output_directory)
    if not root.exists():
        return ()
    return tuple(load_evidence_receipt(path) for path in sorted(root.glob("*.json")))


def create_input_snapshot(
    artifact_id: str,
    *,
    path: str | os.PathLike[str] | None = None,
    data: bytes | None = None,
    path_token: str = "",
    workspace_root: str | os.PathLike[str] | None = None,
    hash_policy: str = INPUT_HASH_BOTH,
    obligation_ids: Sequence[str] = (),
) -> InputSnapshot:
    """Create a snapshot from exactly one file path or in-memory byte value."""

    if (path is None) == (data is None):
        raise ReceiptValidationError("provide exactly one of path or data")
    if path is not None:
        return snapshot_file(
            artifact_id,
            path,
            workspace_root=workspace_root,
            hash_policy=hash_policy,
            obligation_ids=obligation_ids,
        )
    if not path_token:
        raise ReceiptValidationError("path_token is required for an in-memory input snapshot")
    return snapshot_bytes(
        artifact_id,
        data or b"",
        path_token=path_token,
        hash_policy=hash_policy,
        obligation_ids=obligation_ids,
    )


# Short spellings are intentionally aliases, not alternate implementations.
save_receipt = save_evidence_receipt
load_receipt = load_evidence_receipt


@dataclass(frozen=True)
class LegacyEvidenceDiagnostic:
    """Privacy-safe diagnostic projection of an unbound historical report."""

    evidence_id: str
    source_token: str
    payload_fingerprint: str
    observed_status: str
    classification: str = LEGACY_EVIDENCE_CLASSIFICATION
    current: bool = False
    eligible: bool = False
    covered_obligations: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ("legacy_unbound_historical_evidence",)
    claim_boundary: str = "Historical diagnostic only; proves no current governance obligation."

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_token": self.source_token,
            "payload_fingerprint": self.payload_fingerprint,
            "observed_status": self.observed_status,
            "classification": self.classification,
            "current": self.current,
            "eligible": self.eligible,
            "covered_obligations": list(self.covered_obligations),
            "finding_codes": list(self.finding_codes),
            "claim_boundary": self.claim_boundary,
        }


def import_legacy_report(
    source: Mapping[str, Any] | str | os.PathLike[str],
    *,
    workspace_root: str | os.PathLike[str] | None = None,
) -> LegacyEvidenceDiagnostic:
    """Import legacy output as unbound diagnostic evidence, never current proof."""

    if isinstance(source, Mapping):
        payload = _canonical_json(dict(source)).encode("utf-8")
        source_token = "<IN_MEMORY_LEGACY_REPORT>"
        parsed = source
    else:
        path = Path(source)
        payload = path.read_bytes()
        source_token = tokenize_path(path, workspace_root=workspace_root)
        try:
            candidate = json.loads(payload.decode("utf-8"))
            parsed = candidate if isinstance(candidate, Mapping) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = {}
    payload_hash = _sha256(payload)
    observed = str(parsed.get("status", parsed.get("result_status", parsed.get("decision", "unknown"))))
    return LegacyEvidenceDiagnostic(
        evidence_id=f"legacy:{payload_hash.removeprefix('sha256:')[:16]}",
        source_token=source_token,
        payload_fingerprint=payload_hash,
        observed_status=observed,
    )


__all__ = [
    "ChildReceiptRequirement",
    "ConsumedChildReceipt",
    "DEFAULT_EVIDENCE_DIRECTORY",
    "EVIDENCE_RECEIPT_SCHEMA_VERSION",
    "EnvironmentFingerprint",
    "EvidenceReceipt",
    "INPUT_HASH_BOTH",
    "INPUT_HASH_POLICIES",
    "INPUT_HASH_RAW",
    "INPUT_HASH_SEMANTIC",
    "InputSnapshot",
    "LEGACY_EVIDENCE_CLASSIFICATION",
    "LegacyEvidenceDiagnostic",
    "RECEIPT_STATUS_BLOCKED",
    "RECEIPT_STATUS_ERROR",
    "RECEIPT_STATUS_FAIL",
    "RECEIPT_STATUS_NOT_RUN",
    "RECEIPT_STATUS_PASS",
    "RECEIPT_STATUS_PASS_WITH_GAPS",
    "RECEIPT_STATUS_PROGRESS_ONLY",
    "RECEIPT_STATUS_SCOPED",
    "RECEIPT_STATUS_SKIPPED",
    "RECEIPT_STATUS_STALE",
    "ReceiptFinding",
    "ReceiptValidationError",
    "ReceiptVerificationContext",
    "ReceiptVerificationResult",
    "SAFE_ENVIRONMENT_KEYS",
    "VERIFICATION_STATUS_INVALID",
    "VERIFICATION_STATUS_STALE",
    "build_environment_fingerprint",
    "canonical_receipt_json",
    "capture_environment_fingerprint",
    "create_input_snapshot",
    "evidence_storage_root",
    "fingerprint_value",
    "import_legacy_report",
    "list_evidence_receipts",
    "load_evidence_receipt",
    "load_receipt",
    "minimum_revalidation",
    "proof_artifact_binding_findings",
    "receipt_fingerprint",
    "receipt_path",
    "save_evidence_receipt",
    "save_receipt",
    "snapshot_bytes",
    "snapshot_file",
    "tokenize_command",
    "tokenize_path",
    "verify_evidence_receipt",
    "verify_receipt",
]
