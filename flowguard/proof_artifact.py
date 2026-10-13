"""Shared proof artifact references for FlowGuard evidence consumers.

Review helpers do not execute project commands. They consume proof artifact
references produced by command runners, replay adapters, or project-specific
evidence collectors and decide whether a confidence claim is supported by a
fresh external artifact instead of a caller-declared status string alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .export import to_jsonable


PROOF_ARTIFACT_STATUS_PASSED = "passed"
PROOF_ARTIFACT_STATUS_FAILED = "failed"
PROOF_ARTIFACT_STATUS_SKIPPED = "skipped"
PROOF_ARTIFACT_STATUS_STALE = "stale"
PROOF_ARTIFACT_STATUS_NOT_RUN = "not_run"
PROOF_ARTIFACT_STATUS_RUNNING = "running"
PROOF_ARTIFACT_STATUS_PROGRESS_ONLY = "progress_only"
PROOF_ARTIFACT_STATUS_ERROR = "error"

PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT = "external_contract"
PROOF_ARTIFACT_SCOPE_INTERNAL_PATH = "internal_path"
PROOF_ARTIFACT_SCOPE_MIXED = "mixed"
PROOF_ARTIFACT_SCOPE_UNKNOWN = "unknown"

PASSING_PROOF_ARTIFACT_STATUSES = {PROOF_ARTIFACT_STATUS_PASSED}
NON_PASSING_PROOF_ARTIFACT_STATUSES = {
    PROOF_ARTIFACT_STATUS_FAILED,
    PROOF_ARTIFACT_STATUS_SKIPPED,
    PROOF_ARTIFACT_STATUS_STALE,
    PROOF_ARTIFACT_STATUS_NOT_RUN,
    PROOF_ARTIFACT_STATUS_RUNNING,
    PROOF_ARTIFACT_STATUS_PROGRESS_ONLY,
    PROOF_ARTIFACT_STATUS_ERROR,
}
EXTERNAL_PROOF_ARTIFACT_SCOPES = {
    PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
    PROOF_ARTIFACT_SCOPE_MIXED,
}

# A ``sha256:`` prefix is only a label.  It is not evidence that a digest was
# ever calculated.  All paths which are allowed to license a current claim
# use the strict form below and recompute the digest from the referenced
# bytes/receipt.
SHA256_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def is_sha256_fingerprint(value: Any) -> bool:
    """Return whether *value* is a canonical lowercase SHA-256 fingerprint."""

    return isinstance(value, str) and bool(SHA256_FINGERPRINT_RE.fullmatch(value))


def sha256_fingerprint(data: bytes) -> str:
    """Hash bytes using the one wire spelling accepted by evidence gates."""

    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _path_for_read(value: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser()


def _receipt_field(receipt: Mapping[str, Any], *names: str) -> Any:
    """Read one receipt fact across the small native receipt dialects.

    ``EvidenceReceipt`` uses ``producer_id`` and ``result_status`` while
    lightweight native adapters often call the same facts ``owner_id`` and
    ``terminal``.  This helper only reads aliases; it never treats a caller
    supplied status as proof of a receipt.
    """

    for name in names:
        if name in receipt:
            return receipt[name]
    metadata = receipt.get("metadata")
    if isinstance(metadata, Mapping):
        for name in names:
            if name in metadata:
                return metadata[name]
    return None


def _command_tokens(value: Any) -> tuple[str, ...]:
    """Normalize receipt/reference command shapes for exact comparison."""

    if isinstance(value, (tuple, list)):
        return tuple(str(item) for item in value)
    if isinstance(value, str):
        try:
            return tuple(shlex.split(value, posix=True))
        except ValueError:
            return (value,)
    return ()


def proof_artifact_integrity_gap_codes(
    artifact: "ProofArtifactRef | None",
    *,
    expected_receipt_id: str = "",
    expected_receipt_fingerprint: str = "",
    expected_owner_id: str = "",
    expected_source_fingerprint: str = "",
    expected_model_fingerprint: str = "",
    expected_toolchain_fingerprint: str = "",
    expected_environment_fingerprint: str = "",
    expected_result_fingerprint: str = "",
    expected_reuse_identity: str = "",
    require_receipt: bool = True,
    require_cleanup_confirmation: bool = True,
    require_canonical_receipt: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Independently verify the material behind one proof reference.

    This is intentionally a read-only verifier.  It opens the result and
    receipt paths, recomputes their hashes, parses the receipt, and compares
    the producer/source/model/toolchain/environment/terminal/cleanup facts
    with the frozen expected values.  A status string or a hash-shaped string
    supplied by the caller cannot make this function pass.  When
    ``expected_reuse_identity`` is present, the producer receipt must repeat
    that exact native-owner unit identity; a non-empty caller field alone is
    not reuse authority.
    """

    if artifact is None:
        return (("proof_artifact_missing", "proof artifact reference is missing"),)

    gaps: list[tuple[str, str]] = []

    def add(code: str, message: str) -> None:
        gaps.append((code, message))

    # Result material -----------------------------------------------------
    result_path = _path_for_read(artifact.result_path)
    actual_result_fingerprint = ""
    if result_path is None:
        add("proof_result_path_missing", "proof artifact has no result path")
    elif not result_path.is_file():
        add("proof_result_path_missing", f"proof result path does not exist: {artifact.result_path}")
    else:
        expected_result = expected_result_fingerprint.strip() or artifact.result_fingerprint.strip()
        if not expected_result:
            # Existing callers use a path-keyed map.  Keep that form while
            # refusing an ambiguous map with multiple unrelated hashes.
            expected_result = (
                artifact.artifact_fingerprints.get("result", "")
                or artifact.artifact_fingerprints.get(artifact.result_path, "")
                or artifact.artifact_fingerprints.get(result_path.as_posix(), "")
            )
        if not is_sha256_fingerprint(expected_result):
            add(
                "proof_result_fingerprint_invalid",
                "proof result fingerprint is not a canonical SHA-256 digest",
            )
        else:
            try:
                actual_result = sha256_fingerprint(result_path.read_bytes())
                actual_result_fingerprint = actual_result
            except OSError as exc:
                add("proof_result_path_unreadable", f"proof result path cannot be read: {exc}")
            else:
                if actual_result != expected_result:
                    add(
                        "proof_result_hash_mismatch",
                        "proof result bytes do not match the declared fingerprint",
                    )
                if expected_result_fingerprint and actual_result != expected_result_fingerprint:
                    add(
                        "proof_result_expected_hash_mismatch",
                        "proof result bytes do not match the frozen expected fingerprint",
                    )

    # Receipt material ----------------------------------------------------
    receipt_path = _path_for_read(artifact.receipt_path)
    if receipt_path is None:
        if require_receipt:
            add("proof_receipt_missing", "a canonical producer receipt path is required")
        return tuple(dict.fromkeys(gaps))
    if not receipt_path.is_file():
        add("proof_receipt_path_missing", f"producer receipt path does not exist: {artifact.receipt_path}")
        return tuple(dict.fromkeys(gaps))

    try:
        raw_receipt = receipt_path.read_bytes()
        receipt = json.loads(raw_receipt.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add("proof_receipt_unreadable", f"producer receipt cannot be loaded: {exc}")
        return tuple(dict.fromkeys(gaps))
    if not isinstance(receipt, Mapping):
        add("proof_receipt_malformed", "producer receipt must be a JSON object")
        return tuple(dict.fromkeys(gaps))

    canonical_hash = sha256_fingerprint(_canonical_json_bytes(receipt))
    declared_receipt_hash = artifact.receipt_fingerprint.strip()
    if not is_sha256_fingerprint(declared_receipt_hash):
        add("proof_receipt_fingerprint_invalid", "producer receipt fingerprint is not canonical")
    elif canonical_hash != declared_receipt_hash:
        add("proof_receipt_hash_mismatch", "producer receipt canonical hash does not match the reference")
    if expected_receipt_fingerprint and canonical_hash != expected_receipt_fingerprint:
        add("proof_receipt_expected_hash_mismatch", "producer receipt does not match the frozen expected hash")

    receipt_id = str(_receipt_field(receipt, "receipt_id", "id") or "")
    expected_receipt = expected_receipt_id.strip() or artifact.receipt_id.strip()
    if require_receipt and not expected_receipt:
        add("proof_receipt_expected_identity_missing", "proof artifact has no frozen receipt identity")
    if require_receipt and not receipt_id:
        add("proof_receipt_identity_missing", "producer receipt has no stable receipt id")
    elif expected_receipt and receipt_id != expected_receipt:
        add("proof_receipt_identity_mismatch", "producer receipt id does not match the evidence id")

    # A full EvidenceReceipt is the only receipt authority for current
    # execution claims.  Diagnostic/native adapters may still be inspected by
    # callers that explicitly leave ``require_canonical_receipt`` false, but
    # strict UI/runtime/DNA lanes must not accept that smaller dialect.
    canonical_receipt_error: Exception | None = None
    canonical_receipt = None  # experiment: EvidenceReceipt ledger removed
    canonical_receipt_error = ValueError("canonical EvidenceReceipt ledger removed")
    receipt_view: Mapping[str, Any] = (
        canonical_receipt.to_dict() if canonical_receipt is not None else receipt
    )
    if canonical_receipt is not None:
        if canonical_receipt.fingerprint != canonical_hash:
            add("proof_receipt_canonical_model_mismatch", "parsed receipt canonical fingerprint differs from its JSON")
    elif require_canonical_receipt:
        add(
            "proof_receipt_canonical_required",
            "strict current evidence requires a valid canonical EvidenceReceipt",
        )
    elif "schema_version" in receipt:
        add(
            "proof_receipt_canonical_model_invalid",
            f"declared canonical receipt cannot be validated: {canonical_receipt_error}",
        )

    expected_facts = {
        "owner": expected_owner_id or artifact.execution_owner_id,
        "source": expected_source_fingerprint or artifact.source_fingerprint,
        "model": expected_model_fingerprint or artifact.model_fingerprint,
        "toolchain": expected_toolchain_fingerprint or artifact.toolchain_fingerprint,
        "environment": expected_environment_fingerprint or artifact.environment_fingerprint,
    }
    declared_reference_facts = {
        "owner": artifact.execution_owner_id,
        "source": artifact.source_fingerprint,
        "model": artifact.model_fingerprint,
        "toolchain": artifact.toolchain_fingerprint,
        "environment": artifact.environment_fingerprint,
        "result": artifact.result_fingerprint
        or artifact.artifact_fingerprints.get("result", ""),
        "receipt": artifact.receipt_id,
    }
    expected_reference_facts = {
        "owner": expected_owner_id,
        "source": expected_source_fingerprint,
        "model": expected_model_fingerprint,
        "toolchain": expected_toolchain_fingerprint,
        "environment": expected_environment_fingerprint,
        "result": expected_result_fingerprint,
        "receipt": expected_receipt_id,
    }
    for name, expected in expected_reference_facts.items():
        declared = declared_reference_facts[name]
        if expected and declared and str(declared) != str(expected):
            add(
                f"proof_reference_{name}_mismatch",
                f"proof reference {name} identity does not match the frozen value",
            )
    actual_facts = {
        "owner": _receipt_field(receipt_view, "producer_id", "owner_id", "execution_owner_id"),
        "source": _receipt_field(receipt_view, "source_fingerprint", "subject_fingerprint"),
        "model": _receipt_field(receipt_view, "model_fingerprint", "model_revision_fingerprint"),
        "toolchain": _receipt_field(receipt_view, "toolchain_fingerprint", "toolchain"),
        "environment": _receipt_field(receipt_view, "environment_fingerprint"),
    }
    for name, expected in expected_facts.items():
        if expected:
            if actual_facts[name] in (None, ""):
                add(f"proof_receipt_{name}_missing", f"producer receipt has no {name} identity")
            elif str(actual_facts[name]) != str(expected):
                add(f"proof_receipt_{name}_mismatch", f"producer receipt {name} identity does not match the frozen value")
        elif require_receipt:
            if actual_facts[name] in (None, ""):
                add(f"proof_receipt_{name}_missing", f"producer receipt has no {name} identity")
        if name != "owner" and actual_facts[name] not in (None, "") and not is_sha256_fingerprint(str(actual_facts[name])):
            add(f"proof_receipt_{name}_invalid", f"producer receipt {name} identity is not a canonical fingerprint")

    result_status = str(_receipt_field(receipt_view, "result_status", "status", "terminal") or "")
    exit_code = _receipt_field(receipt_view, "exit_code")
    terminal_state = _receipt_field(receipt_view, "terminal_state", "terminal")
    receipt_command = _receipt_field(receipt_view, "command", "command_tokens")
    if require_receipt:
        if receipt_command in (None, "", (), []):
            add("proof_receipt_command_missing", "producer receipt has no executed command identity")
        elif _command_tokens(receipt_command) != _command_tokens(artifact.command):
            add("proof_receipt_command_mismatch", "producer receipt command does not match the proof reference")
    elif receipt_command not in (None, "", (), []) and artifact.command:
        if _command_tokens(receipt_command) != _command_tokens(artifact.command):
            add("proof_receipt_command_mismatch", "producer receipt command does not match the proof reference")

    if expected_reuse_identity:
        receipt_reuse_identity = _receipt_field(
            receipt_view,
            "reuse_identity",
            "reuse_unit_identity",
            "execution_unit_identity",
        )
        if receipt_reuse_identity in (None, ""):
            add(
                "proof_receipt_reuse_identity_missing",
                "producer receipt has no exact reuse identity",
            )
        elif str(receipt_reuse_identity) != str(expected_reuse_identity):
            add(
                "proof_receipt_reuse_identity_mismatch",
                "producer receipt reuse identity does not match the reused result",
            )
    receipt_result_fingerprint = _receipt_field(receipt_view, "result_fingerprint")
    if receipt_result_fingerprint not in (None, ""):
        expected_result = expected_result_fingerprint or artifact.result_fingerprint
        if not expected_result:
            expected_result = (
                artifact.artifact_fingerprints.get("result", "")
                or artifact.artifact_fingerprints.get(artifact.result_path, "")
            )
        if expected_result and str(receipt_result_fingerprint) != expected_result:
            add(
                "proof_receipt_result_fingerprint_mismatch",
                "producer receipt result fingerprint does not match the result artifact",
            )
        if not is_sha256_fingerprint(str(receipt_result_fingerprint)):
            add(
                "proof_receipt_result_fingerprint_invalid",
                "producer receipt result fingerprint is not canonical",
            )
        if actual_result_fingerprint and str(receipt_result_fingerprint) != actual_result_fingerprint:
            add(
                "proof_receipt_result_hash_mismatch",
                "producer receipt result fingerprint does not match the result bytes",
            )
    elif require_receipt:
        add(
            "proof_receipt_result_fingerprint_missing",
            "producer receipt has no result fingerprint bound to the terminal result",
        )
    if artifact.terminal_state and str(terminal_state or "") != artifact.terminal_state:
        add("proof_receipt_terminal_mismatch", "producer receipt terminal state differs from the reference")
    status_values = tuple(
        value.casefold()
        for value in (result_status, str(terminal_state or ""))
        if value
    )
    if not status_values:
        add("proof_receipt_terminal_missing", "producer receipt has no terminal state")
    elif any(
        value
        not in {"pass", "passed", "success", "completed", "terminal_success"}
        for value in status_values
    ):
        add("proof_receipt_terminal_not_success", "producer receipt is not a terminal success")
    if exit_code in (None, ""):
        if require_receipt:
            add("proof_receipt_exit_missing", "producer receipt has no terminal exit code")
    elif isinstance(exit_code, bool):
        add("proof_receipt_exit_invalid", "producer receipt exit code is not an integer")
    else:
        try:
            normalized_exit_code = int(exit_code)
        except (TypeError, ValueError):
            add("proof_receipt_exit_invalid", "producer receipt exit code is not an integer")
        else:
            if normalized_exit_code != 0:
                add("proof_receipt_nonzero_exit", "producer receipt exit code is not zero")

    cleanup_state = _receipt_field(receipt_view, "cleanup_state", "cleanup", "cleanup_status")
    cleanup_verified = _receipt_field(receipt_view, "cleanup_verified", "descendants_zero", "cleanup_confirmed")
    if artifact.cleanup_state and cleanup_state not in (None, "") and str(cleanup_state) != artifact.cleanup_state:
        add("proof_receipt_cleanup_mismatch", "producer receipt cleanup state differs from the reference")
    if artifact.cleanup_verified is False or str(cleanup_state).lower() in {"cleanup-unconfirmed", "unconfirmed", "unknown", "timeout"}:
        add("proof_receipt_cleanup_unconfirmed", "producer receipt explicitly records unconfirmed cleanup")
    elif require_cleanup_confirmation and not (
        cleanup_verified is True
        or str(cleanup_verified).lower() in {"true", "confirmed", "clean", "zero", "zero_descendants"}
        or str(cleanup_state).lower() in {"confirmed", "clean", "settled", "zero_descendants"}
    ):
        add("proof_receipt_cleanup_unconfirmed", "producer receipt lacks confirmed descendant cleanup")

    return tuple(dict.fromkeys(gaps))


# Short aliases make the verifier discoverable to native adapters without
# creating a second evidence authority.
verify_proof_artifact = proof_artifact_integrity_gap_codes
verify_proof_artifact_ref = proof_artifact_integrity_gap_codes


def _as_str_map(values: Mapping[str, Any] | None) -> dict[str, str]:
    if not values:
        return {}
    return {str(key): str(value) for key, value in values.items()}


@dataclass(frozen=True)
class ProofArtifactRef:
    """One concrete proof artifact produced by a validation command or replay."""

    artifact_id: str
    producer_route: str = ""
    command: str = ""
    result_path: str = ""
    result_status: str = PROOF_ARTIFACT_STATUS_NOT_RUN
    exit_code: int | None = None
    started_at: str = ""
    finished_at: str = ""
    subject_id: str = ""
    subject_fingerprint: str = ""
    artifact_fingerprints: Mapping[str, str] = field(default_factory=dict)
    covered_obligation_ids: tuple[str, ...] = ()
    assertion_scope: str = PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT
    current: bool = True
    route_evidence_current: bool = True
    progress_only: bool = False
    stale_reasons: tuple[str, ...] = ()
    route_gap_codes: tuple[str, ...] = ()
    # The result reference above is not a producer receipt.  Current claims
    # require the separate immutable receipt and its execution identities.
    receipt_id: str = ""
    receipt_path: str = ""
    receipt_fingerprint: str = ""
    execution_owner_id: str = ""
    source_fingerprint: str = ""
    model_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    result_fingerprint: str = ""
    terminal_state: str = ""
    cleanup_state: str = ""
    cleanup_verified: bool | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "producer_route", str(self.producer_route))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "result_path", str(self.result_path))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "started_at", str(self.started_at))
        object.__setattr__(self, "finished_at", str(self.finished_at))
        object.__setattr__(self, "subject_id", str(self.subject_id))
        object.__setattr__(self, "subject_fingerprint", str(self.subject_fingerprint))
        object.__setattr__(self, "artifact_fingerprints", _as_str_map(self.artifact_fingerprints))
        object.__setattr__(self, "covered_obligation_ids", _as_tuple(self.covered_obligation_ids))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))
        object.__setattr__(self, "route_gap_codes", _as_tuple(self.route_gap_codes))
        for name in (
            "receipt_id",
            "receipt_path",
            "receipt_fingerprint",
            "execution_owner_id",
            "source_fingerprint",
            "model_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
            "result_fingerprint",
            "terminal_state",
            "cleanup_state",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        if self.cleanup_verified is not None and not isinstance(self.cleanup_verified, bool):
            raise TypeError("cleanup_verified must be a boolean or None")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_external_scope(self) -> bool:
        return self.assertion_scope in EXTERNAL_PROOF_ARTIFACT_SCOPES

    def material_gap_codes(self) -> tuple[str, ...]:
        """Return missing or malformed material required for current evidence.

        Construction remains additive-compatible, but a caller-authored
        ``passed``/``current`` pair is deliberately insufficient.  A current
        proof must identify what ran, where its terminal result lives, when it
        ran, and the exact subject whose content was checked.
        """

        gaps: list[str] = []
        required_text = {
            "proof_artifact_missing_id": self.artifact_id,
            "proof_artifact_missing_producer_route": self.producer_route,
            "proof_artifact_missing_command": self.command,
            "proof_artifact_missing_result_path": self.result_path,
            "proof_artifact_missing_started_at": self.started_at,
            "proof_artifact_missing_finished_at": self.finished_at,
            "proof_artifact_missing_subject": self.subject_id,
            "proof_artifact_missing_subject_fingerprint": self.subject_fingerprint,
        }
        gaps.extend(code for code, value in required_text.items() if not value.strip())
        if self.exit_code is None:
            gaps.append("proof_artifact_missing_exit_code")
        for code, value in (
            ("proof_artifact_invalid_started_at", self.started_at),
            ("proof_artifact_invalid_finished_at", self.finished_at),
        ):
            if value:
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    gaps.append(code)
        if self.subject_fingerprint and not is_sha256_fingerprint(self.subject_fingerprint):
            gaps.append("proof_artifact_invalid_subject_fingerprint")
        if not self.artifact_fingerprints:
            gaps.append("proof_artifact_missing_fingerprint")
        elif any(not is_sha256_fingerprint(value) for value in self.artifact_fingerprints.values()):
            gaps.append("proof_artifact_invalid_fingerprint")
        if self.result_fingerprint and not is_sha256_fingerprint(self.result_fingerprint):
            gaps.append("proof_artifact_invalid_result_fingerprint")
        if self.receipt_fingerprint and not is_sha256_fingerprint(self.receipt_fingerprint):
            gaps.append("proof_artifact_invalid_receipt_fingerprint")
        return tuple(dict.fromkeys(gaps))

    def has_current_pass(self) -> bool:
        return (
            self.result_status in PASSING_PROOF_ARTIFACT_STATUSES
            and self.current
            and self.route_evidence_current
            and not self.progress_only
            and not self.stale_reasons
            and not self.route_gap_codes
            and self.exit_code == 0
            and not self.material_gap_codes()
        )

    def covers_any(self, obligation_ids: Sequence[str]) -> bool:
        required = {str(value) for value in obligation_ids if str(value)}
        if not required:
            return True
        return bool(required & set(self.covered_obligation_ids))

    def covers_all(self, obligation_ids: Sequence[str]) -> bool:
        """Return whether every requested obligation is bound by this artifact."""

        required = {str(value) for value in obligation_ids if str(value)}
        if not required:
            return True
        return required.issubset(set(self.covered_obligation_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "producer_route": self.producer_route,
            "command": self.command,
            "result_path": self.result_path,
            "result_status": self.result_status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "subject_id": self.subject_id,
            "subject_fingerprint": self.subject_fingerprint,
            "artifact_fingerprints": dict(self.artifact_fingerprints),
            "covered_obligation_ids": list(self.covered_obligation_ids),
            "assertion_scope": self.assertion_scope,
            "current": self.current,
            "route_evidence_current": self.route_evidence_current,
            "progress_only": self.progress_only,
            "stale_reasons": list(self.stale_reasons),
            "route_gap_codes": list(self.route_gap_codes),
            "receipt_path": self.receipt_path,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "execution_owner_id": self.execution_owner_id,
            "source_fingerprint": self.source_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "terminal_state": self.terminal_state,
            "cleanup_state": self.cleanup_state,
            "cleanup_verified": self.cleanup_verified,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def coerce_proof_artifact_ref(value: ProofArtifactRef | Mapping[str, Any] | None) -> ProofArtifactRef | None:
    """Return a `ProofArtifactRef` from an existing instance or mapping."""

    if value is None or isinstance(value, ProofArtifactRef):
        return value
    data = dict(value)
    aliases = {
        "producer_receipt_id": "receipt_id",
        "producer_receipt_path": "receipt_path",
        "producer_receipt_fingerprint": "receipt_fingerprint",
    }
    for alias, canonical in aliases.items():
        if canonical not in data and alias in data:
            data[canonical] = data[alias]
        data.pop(alias, None)
    return ProofArtifactRef(**data)


def proof_artifact_gap_codes(
    artifact: ProofArtifactRef | None,
    *,
    declared_status: str = "",
    required_obligation_ids: Sequence[str] = (),
    require_result_path: bool = False,
    require_fingerprints: bool = False,
    require_external_scope: bool = False,
    require_verifiable_material: bool = False,
    require_receipt: bool = False,
    require_cleanup_confirmation: bool = True,
    expected_receipt_id: str = "",
    expected_receipt_fingerprint: str = "",
    expected_owner_id: str = "",
    expected_source_fingerprint: str = "",
    expected_model_fingerprint: str = "",
    expected_toolchain_fingerprint: str = "",
    expected_environment_fingerprint: str = "",
    expected_result_fingerprint: str = "",
    expected_reuse_identity: str = "",
    require_canonical_receipt: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Return normalized gap codes explaining why a proof artifact is not usable."""

    if artifact is None:
        return (("missing_proof_artifact", "evidence has no proof artifact reference"),)

    gaps: list[tuple[str, str]] = []
    if declared_status and artifact.result_status != declared_status:
        gaps.append(
            (
                "proof_artifact_status_mismatch",
                f"declared status {declared_status} does not match proof artifact status {artifact.result_status}",
            )
        )
    if artifact.result_status not in PASSING_PROOF_ARTIFACT_STATUSES:
        gaps.append(("proof_artifact_not_passing", f"proof artifact status is {artifact.result_status}"))
    if artifact.exit_code not in (None, 0):
        gaps.append(("proof_artifact_nonzero_exit", f"proof artifact exit code is {artifact.exit_code}"))
    if not artifact.current or artifact.stale_reasons or not artifact.route_evidence_current:
        gaps.append(("stale_proof_artifact", "proof artifact or its route evidence is stale"))
    if artifact.progress_only:
        gaps.append(("progress_only_proof_artifact", "proof artifact is progress-only"))
    if artifact.route_gap_codes:
        gaps.append(("proof_artifact_route_gap_visible", "proof artifact route still has unresolved gaps"))
    if require_verifiable_material or require_receipt:
        material_messages = {
            "proof_artifact_missing_id": "proof artifact has no stable identity",
            "proof_artifact_missing_producer_route": "proof artifact has no producer route",
            "proof_artifact_missing_command": "proof artifact has no executed command",
            "proof_artifact_missing_result_path": "proof artifact has no terminal result path",
            "proof_artifact_missing_started_at": "proof artifact has no start timestamp",
            "proof_artifact_missing_finished_at": "proof artifact has no finish timestamp",
            "proof_artifact_invalid_started_at": "proof artifact start timestamp is not ISO-8601",
            "proof_artifact_invalid_finished_at": "proof artifact finish timestamp is not ISO-8601",
            "proof_artifact_missing_subject": "proof artifact has no evidence subject",
            "proof_artifact_missing_subject_fingerprint": "proof artifact subject has no fingerprint",
            "proof_artifact_missing_exit_code": "proof artifact has no terminal exit code",
            "proof_artifact_invalid_subject_fingerprint": "proof artifact subject fingerprint is not sha256",
            "proof_artifact_missing_fingerprint": "proof artifact has no artifact fingerprints",
            "proof_artifact_invalid_fingerprint": "proof artifact contains a non-sha256 fingerprint",
            "proof_artifact_invalid_result_fingerprint": "proof artifact result fingerprint is not canonical",
            "proof_artifact_invalid_receipt_fingerprint": "proof artifact receipt fingerprint is not canonical",
        }
        for code in artifact.material_gap_codes():
            gaps.append((code, material_messages.get(code, "proof artifact contains malformed material")))
        integrity_required = require_verifiable_material or require_receipt
        if integrity_required:
            integrity_messages = {
                "proof_result_path_missing": "proof result path is missing or does not exist",
                "proof_result_path_unreadable": "proof result path cannot be read",
                "proof_result_fingerprint_invalid": "proof result fingerprint is not canonical",
                "proof_result_hash_mismatch": "proof result bytes do not match their fingerprint",
                "proof_result_expected_hash_mismatch": "proof result bytes do not match the expected fingerprint",
                "proof_receipt_missing": "canonical producer receipt is missing",
                "proof_receipt_path_missing": "canonical producer receipt path does not exist",
                "proof_receipt_unreadable": "canonical producer receipt cannot be loaded",
                "proof_receipt_malformed": "canonical producer receipt is malformed",
                "proof_receipt_fingerprint_invalid": "producer receipt fingerprint is not canonical",
                "proof_receipt_hash_mismatch": "producer receipt canonical hash does not match",
                "proof_receipt_expected_hash_mismatch": "producer receipt does not match the expected hash",
                "proof_receipt_expected_identity_missing": "proof artifact receipt identity is not frozen",
                "proof_receipt_identity_missing": "producer receipt identity is missing",
                "proof_receipt_identity_mismatch": "producer receipt identity does not match",
                "proof_receipt_canonical_required": "strict current evidence requires a valid canonical EvidenceReceipt",
                "proof_receipt_canonical_model_mismatch": "parsed producer receipt is not canonical",
                "proof_receipt_canonical_model_invalid": "declared producer receipt is not a valid canonical receipt",
                "proof_receipt_command_missing": "producer receipt command is missing",
                "proof_receipt_command_mismatch": "producer receipt command does not match",
                "proof_receipt_exit_missing": "producer receipt exit code is missing",
                "proof_receipt_exit_invalid": "producer receipt exit code is not an integer",
                "proof_receipt_reuse_identity_missing": "producer receipt reuse identity is missing",
                "proof_receipt_reuse_identity_mismatch": "producer receipt reuse identity does not match",
                "proof_reference_owner_mismatch": "proof reference owner does not match",
                "proof_reference_source_mismatch": "proof reference source does not match",
                "proof_reference_model_mismatch": "proof reference model does not match",
                "proof_reference_toolchain_mismatch": "proof reference toolchain does not match",
                "proof_reference_environment_mismatch": "proof reference environment does not match",
                "proof_reference_result_mismatch": "proof reference result does not match",
                "proof_reference_receipt_mismatch": "proof reference receipt identity does not match",
                "proof_receipt_owner_missing": "producer receipt owner is missing",
                "proof_receipt_source_missing": "producer receipt source is missing",
                "proof_receipt_model_missing": "producer receipt model is missing",
                "proof_receipt_toolchain_missing": "producer receipt toolchain is missing",
                "proof_receipt_environment_missing": "producer receipt environment is missing",
                "proof_receipt_owner_mismatch": "producer receipt owner does not match",
                "proof_receipt_source_mismatch": "producer receipt source does not match",
                "proof_receipt_model_mismatch": "producer receipt model does not match",
                "proof_receipt_toolchain_mismatch": "producer receipt toolchain does not match",
                "proof_receipt_environment_mismatch": "producer receipt environment does not match",
                "proof_receipt_source_invalid": "producer receipt source is not canonical",
                "proof_receipt_model_invalid": "producer receipt model is not canonical",
                "proof_receipt_toolchain_invalid": "producer receipt toolchain is not canonical",
                "proof_receipt_environment_invalid": "producer receipt environment is not canonical",
                "proof_receipt_result_fingerprint_mismatch": "producer receipt result fingerprint does not match",
                "proof_receipt_result_hash_mismatch": "producer receipt result fingerprint does not match the result bytes",
                "proof_receipt_result_fingerprint_invalid": "producer receipt result fingerprint is not canonical",
                "proof_receipt_result_fingerprint_missing": "producer receipt has no result fingerprint",
                "proof_receipt_result_hash_mismatch": "producer receipt result fingerprint does not match result bytes",
                "proof_receipt_terminal_missing": "producer receipt terminal state is missing",
                "proof_receipt_terminal_not_success": "producer receipt is not terminal success",
                "proof_receipt_terminal_mismatch": "producer receipt terminal state does not match",
                "proof_receipt_nonzero_exit": "producer receipt exit code is non-zero",
                "proof_receipt_cleanup_mismatch": "producer receipt cleanup state does not match",
                "proof_receipt_cleanup_unconfirmed": "producer receipt cleanup is not confirmed",
            }
            for code, message in proof_artifact_integrity_gap_codes(
                artifact,
                expected_receipt_id=expected_receipt_id,
                expected_receipt_fingerprint=expected_receipt_fingerprint,
                expected_owner_id=expected_owner_id,
                expected_source_fingerprint=expected_source_fingerprint,
                expected_model_fingerprint=expected_model_fingerprint,
                expected_toolchain_fingerprint=expected_toolchain_fingerprint,
                expected_environment_fingerprint=expected_environment_fingerprint,
                expected_result_fingerprint=expected_result_fingerprint,
                expected_reuse_identity=expected_reuse_identity,
                require_receipt=require_receipt,
                require_cleanup_confirmation=require_cleanup_confirmation,
                require_canonical_receipt=require_canonical_receipt,
            ):
                gaps.append((code, integrity_messages.get(code, message)))
    if require_result_path and not artifact.result_path:
        gaps.append(("proof_artifact_missing_result_path", "proof artifact has no result path"))
    if require_fingerprints and not artifact.artifact_fingerprints:
        gaps.append(("proof_artifact_missing_fingerprint", "proof artifact has no artifact fingerprints"))
    if required_obligation_ids and not artifact.covers_all(required_obligation_ids):
        gaps.append(("proof_artifact_missing_obligation", "proof artifact does not cover required obligations"))
    if require_external_scope and not artifact.has_external_scope():
        gaps.append(("proof_artifact_internal_path_only", "proof artifact does not exercise the external contract"))
    return tuple(gaps)
