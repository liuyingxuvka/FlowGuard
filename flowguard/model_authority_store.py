"""Durable project model authority, pointer-last activation, and audit."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import tempfile
import tomllib
from typing import Any, Iterable, Mapping

from .model_authority import (
    BOUNDARY_CONTRACT_OWNER_ROUTE,
    MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY,
    LIFECYCLE_ACTIVE,
    REVISION_ACCEPTED,
    ROLLBACK_RESULT_FORWARD_REPAIR,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    ModelActivationReceipt,
    AcceptedBoundaryContract,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackReceipt,
    ModelSystemSnapshot,
    canonical_fingerprint,
    load_accepted_boundary_contract,
    load_model_system_snapshot,
    validate_accepted_boundary_contract_for_snapshot,
    _reject_duplicate_json_keys,
    validate_activation_plan,
    validate_operational_rollback,
    write_content_addressed_snapshot,
)
from .model_intent_authority import (
    INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA,
    LEGACY_CURRENT_REVISION_SCHEMA,
    _bootstrap_source_audit,
    _build_current_intent_bootstrap_receipt_from_source,
    _validate_current_effective_intent_refinement_with_sources,
    bootstrap_current_effective_intent_view,
    validate_candidate_intent_source_input_bindings,
    validate_current_effective_intent_refinement,
    validate_current_effective_intent_view,
)
from .model_intent import ModelIntentSourceIdentity, verify_model_intent_sources
from .source_identity import CANONICAL_TEXT_SUFFIXES, functional_source_fingerprint
from .project_manifest import (
    ProjectManifestError,
    manifest_text_fingerprint,
    project_manifest_lock,
    read_manifest_text,
    replace_project_manifest_locked,
)
from .runtime_artifacts import classify_runtime_artifact


MODEL_AUTHORITY_SECTION = "model_authority"
MODEL_AUTHORITY_STATUS_PASS = "pass"
MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS = "pass_with_gaps"
MODEL_AUTHORITY_STATUS_BLOCKED = "blocked"
_SECTION_RE = re.compile(
    r"(?ms)^\[model_authority\]\s*\n.*?(?=^\[[^\]]+\]\s*$|\Z)"
)
_READ_PROJECTION_INDEX_SCHEMA = "flowguard.accepted_read_projection.v1"
_READ_PROJECTION_SHARD_SCHEMA = "flowguard.read_model_shard.v1"
_ACTIVATION_PROJECTION_ID_RE = re.compile(r"^activation:([0-9a-f]{64})$")


def _windows_io_path(path: Path) -> Path:
    """Use the Windows extended path form for deep staging artifacts."""

    if os.name != "nt":
        return path
    value = str(path)
    # Keep both sides of an atomic replace in the same Win32 namespace.  A
    # short temporary name can still be paired with a long destination; using
    # the extended form for both avoids WinError 3 on Windows when the parent
    # project path is already near MAX_PATH.
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value.lstrip("\\"))
    return Path("\\\\?\\" + value)


@dataclass(frozen=True)
class ModelAuthorityFinding:
    severity: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class ModelAuthorityAuditReport:
    root: str
    status: str
    observed_source_revision: str = ""
    observed_snapshot_fingerprint: str = ""
    live_snapshot_fingerprint: str = ""
    head_fingerprint: str = ""
    accepted_revision_schema: str = ""
    accepted_revision_fingerprint: str = ""
    current_effective_intent_view_fingerprint: str = ""
    active_intent_contribution_count: int = 0
    model_owner_denominator_count: int = 0
    owner_binding_count: int = 0
    intent_mode: str = ""
    coverage_status: str = ""
    declared_model_ids: tuple[str, ...] = ()
    materialized_model_ids: tuple[str, ...] = ()
    required_model_ids: tuple[str, ...] = ()
    covered_model_ids: tuple[str, ...] = ()
    missing_model_ids: tuple[str, ...] = ()
    unresolved_gap_ids: tuple[str, ...] = ()
    findings: tuple[ModelAuthorityFinding, ...] = ()
    claim_boundary: str = (
        "Authority audit identifies one observed model-system snapshot and its "
        "bounded coverage. It does not execute model, test, install, or release checks."
    )

    @property
    def ok(self) -> bool:
        return self.status in {
            MODEL_AUTHORITY_STATUS_PASS,
            MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "status": self.status,
            "ok": self.ok,
            "observed_source_revision": self.observed_source_revision,
            "observed_snapshot_fingerprint": (
                self.observed_snapshot_fingerprint
            ),
            "live_snapshot_fingerprint": self.live_snapshot_fingerprint,
            "head_fingerprint": self.head_fingerprint,
            "accepted_revision_schema": self.accepted_revision_schema,
            "accepted_revision_fingerprint": (
                self.accepted_revision_fingerprint
            ),
            "current_effective_intent_view_fingerprint": (
                self.current_effective_intent_view_fingerprint
            ),
            "active_intent_contribution_count": (
                self.active_intent_contribution_count
            ),
            "model_owner_denominator_count": (
                self.model_owner_denominator_count
            ),
            "owner_binding_count": self.owner_binding_count,
            "intent_mode": self.intent_mode,
            "coverage_status": self.coverage_status,
            "declared_model_ids": list(self.declared_model_ids),
            "materialized_model_ids": list(self.materialized_model_ids),
            "required_model_ids": list(self.required_model_ids),
            "covered_model_ids": list(self.covered_model_ids),
            "missing_model_ids": list(self.missing_model_ids),
            "unresolved_gap_ids": list(self.unresolved_gap_ids),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class CurrentModelAuthorityState:
    """One fully resolved current authority pointer and its typed producer."""

    head: ModelAuthorityHead
    snapshot: ModelSystemSnapshot
    accepted_revision: ModelRevisionSet | None
    transition_kind: str
    predecessor_head: ModelAuthorityHead | None = None
    activation_receipt: ModelActivationReceipt | None = None
    rollback_contract: ModelRollbackContract | None = None
    rollback_receipt: ModelRollbackReceipt | None = None
    verified_source_identities: tuple[ModelIntentSourceIdentity, ...] = ()
    current_sources_reverified: bool = False
    # Optional for historical/current snapshots that predate A05.  When
    # present it is loaded only through the snapshot's owner artifact ref; it
    # is never discovered from a candidate plan or a second pointer.
    accepted_boundary_contract: AcceptedBoundaryContract | None = None


# These statuses deliberately do not reuse the global audit result.  A light
# consumer read can prove that the saved pointer and its immutable ancestry are
# intact while a selected source file is stale; callers need both facts instead
# of one overloaded ``ok`` bit.
SELECTED_SOURCE_CURRENT = "current"
SELECTED_SOURCE_STALE = "stale"
SELECTED_SOURCE_UNAVAILABLE = "unavailable"
SELECTED_SOURCE_NOT_SELECTED = "not_selected"
EXECUTION_EVIDENCE_NOT_RUN = "not_run"


@dataclass(frozen=True)
class SelectedModelClosureRead:
    """A bounded, read-only view of one accepted model-owner closure.

    The object is intentionally a data result rather than a producer.  It
    never builds a live inventory, executes a runner, refreshes a receipt, or
    writes a cache.  ``selected_*`` fields identify the exact closure resolved
    from the accepted snapshot; ``as_of`` keeps that identity usable when a
    selected source is stale.
    """

    authority_integrity: str
    selected_source_currentness: str
    execution_evidence_status: str = EXECUTION_EVIDENCE_NOT_RUN
    snapshot_fingerprint: str = ""
    subject_revision: str = ""
    authority_head_fingerprint: str = ""
    accepted_revision_set_fingerprint: str = ""
    selected_model_ids: tuple[str, ...] = ()
    selected_models: tuple[Mapping[str, Any], ...] = ()
    selected_model_paths: tuple[str, ...] = ()
    selected_runner_paths: tuple[str, ...] = ()
    selected_input_paths: tuple[str, ...] = ()
    selected_intent_paths: tuple[str, ...] = ()
    selected_contract_paths: tuple[str, ...] = ()
    selected_intent_refs: tuple[Mapping[str, Any], ...] = ()
    selected_contract_refs: tuple[Mapping[str, Any], ...] = ()
    relations: tuple[Mapping[str, Any], ...] = ()
    as_of: Mapping[str, Any] = field(default_factory=dict)
    stale_obligations: tuple[str, ...] = ()
    stale_obligation_details: tuple[Mapping[str, Any], ...] = ()
    findings: tuple[Mapping[str, Any], ...] = ()
    read_paths: tuple[str, ...] = ()
    read_counts: tuple[tuple[str, int], ...] = ()
    producer_count: int = 0
    write_count: int = 0
    claim_boundary: str = (
        "Selected model navigation is an as-of read of one accepted authority "
        "closure. It proves no current execution, deep projection, release, or "
        "whole-system live inventory."
    )

    @property
    def ok(self) -> bool:
        return self.authority_integrity in {
            MODEL_AUTHORITY_STATUS_PASS,
            MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the current selected-read result."""

        as_of = dict(self.as_of)
        stale = list(self.stale_obligations)
        return {
            "authority_integrity": self.authority_integrity,
            "selected_source_currentness": self.selected_source_currentness,
            "execution_evidence_status": self.execution_evidence_status,
            "ok": self.ok,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "subject_revision": self.subject_revision,
            "authority_head_fingerprint": self.authority_head_fingerprint,
            "accepted_revision_set_fingerprint": self.accepted_revision_set_fingerprint,
            "selected_model_ids": list(self.selected_model_ids),
            "selected_models": [dict(item) for item in self.selected_models],
            "selected_model_paths": list(self.selected_model_paths),
            "selected_runner_paths": list(self.selected_runner_paths),
            "selected_input_paths": list(self.selected_input_paths),
            "selected_intent_paths": list(self.selected_intent_paths),
            "selected_contract_paths": list(self.selected_contract_paths),
            "selected_intent_refs": [dict(item) for item in self.selected_intent_refs],
            "selected_contract_refs": [dict(item) for item in self.selected_contract_refs],
            "relations": [dict(item) for item in self.relations],
            "as_of": as_of,
            "stale_obligations": stale,
            "stale_obligation_details": [
                dict(item) for item in self.stale_obligation_details
            ],
            "findings": [dict(item) for item in self.findings],
            "read_paths": list(self.read_paths),
            "read_counts": {path: count for path, count in self.read_counts},
            "producer_count": self.producer_count,
            "write_count": self.write_count,
            "claim_boundary": self.claim_boundary,
        }


class CurrentIntentSourceAuthorityError(ModelAuthorityError):
    """The accepted view is valid but one live source is not current or usable."""

    def __init__(self, message: str, *, finding_code: str) -> None:
        super().__init__(message)
        self.finding_code = finding_code


def _current_intent_source_finding_code(message: str) -> str:
    normalized = str(message).lower()
    if "missing or cannot be resolved" in normalized:
        return "current_intent_source_missing"
    if "fingerprint is stale" in normalized or "identities are stale" in normalized:
        return "current_intent_source_stale"
    return "current_intent_source_invalid"


def _relative_path(value: Any, field_name: str) -> str:
    raw = str(value or "").strip()
    posix = PurePosixPath(raw.replace("\\", "/"))
    windows = PureWindowsPath(raw)
    if (
        not raw
        or raw.startswith(("/", "\\"))
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
    ):
        raise ModelAuthorityError(f"{field_name} must be repository-relative")
    return posix.as_posix()


def _assert_current_authority_path(value: Any, field_name: str) -> str:
    """Reject working/candidate paths from a current authority graph."""

    normalized = _relative_path(value, field_name)
    classification = classify_runtime_artifact(normalized)
    if classification is None and not normalized.startswith(".flowguard/"):
        # Model input rows are normally .flowguard-rooted, but older typed
        # fixtures may omit that prefix.  Treat the canonical control-plane
        # spelling as the same authority boundary without weakening the
        # repository-relative path check above.
        classification = classify_runtime_artifact(f".flowguard/{normalized}")
    if classification is not None:
        raise ModelAuthorityError(
            f"{field_name} cannot reference non-authority path "
            f"{classification.relative_path} ({classification.kind})"
        )
    return normalized


def _assert_snapshot_current_paths(snapshot: ModelSystemSnapshot) -> None:
    """Check every model/runner/input edge, not only the manifest pointer."""

    for index, instance in enumerate(snapshot.model_instances):
        _assert_current_authority_path(
            instance.model_path,
            f"snapshot.model_instances[{index}].model_path",
        )
        _assert_current_authority_path(
            instance.runner_path,
            f"snapshot.model_instances[{index}].runner_path",
        )
        for input_index, input_ref in enumerate(instance.inputs):
            _assert_current_authority_path(
                input_ref.path,
                f"snapshot.model_instances[{index}].inputs[{input_index}].path",
            )


def _assert_revision_current_paths(revision_set: ModelRevisionSet) -> None:
    """Check source refs hidden behind an accepted revision pointer."""

    view = revision_set.current_effective_intent_view
    for index, contribution in enumerate(view.active_contributions):
        source_ref = str(contribution.source_ref or "").replace("\\", "/")
        try:
            classification = classify_runtime_artifact(source_ref)
            if classification is None and not source_ref.startswith(".flowguard/"):
                classification = classify_runtime_artifact(
                    f".flowguard/{source_ref}"
                )
        except ValueError:
            classification = None
        if classification is not None:
            _assert_current_authority_path(
                source_ref,
                f"accepted_revision.active_contributions[{index}].source_ref",
            )
    for index, identity in enumerate(view.verified_source_identities):
        source_ref = str(identity.source_ref or "").replace("\\", "/")
        try:
            classification = classify_runtime_artifact(source_ref)
            if classification is None and not source_ref.startswith(".flowguard/"):
                classification = classify_runtime_artifact(
                    f".flowguard/{source_ref}"
                )
        except ValueError:
            classification = None
        if classification is not None:
            _assert_current_authority_path(
                source_ref,
                f"accepted_revision.verified_source_identities[{index}].source_ref",
            )


def _parse_manifest(text: str) -> Mapping[str, Any]:
    try:
        payload = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ModelAuthorityError(f"invalid project manifest: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError("project manifest must be a TOML object")
    return payload


def _section(text: str) -> Mapping[str, Any]:
    payload = _parse_manifest(text)
    section = payload.get(MODEL_AUTHORITY_SECTION)
    if not isinstance(section, Mapping):
        raise ModelAuthorityError("project manifest has no model_authority section")
    return section


def _head_from_section(section: Mapping[str, Any]) -> ModelAuthorityHead:
    required = {
        "system_id",
        "observed_snapshot_path",
        "observed_snapshot_fingerprint",
        "subject_revision",
        "coverage_status",
        "generation",
        "accepted_revision_set_fingerprint",
        "previous_snapshot_fingerprint",
        "activation_receipt_fingerprint",
        "head_fingerprint",
    }
    missing = required - set(section)
    unknown = set(section) - required
    if missing:
        raise ModelAuthorityError(
            f"model_authority missing fields: {sorted(missing)}"
        )
    if unknown:
        raise ModelAuthorityError(
            f"model_authority has unknown fields: {sorted(unknown)}"
        )
    for field_name in required - {"generation"}:
        if not isinstance(section[field_name], str):
            raise ModelAuthorityError(
                f"model_authority {field_name} must be a TOML string"
            )
    if not isinstance(section["generation"], int) or isinstance(
        section["generation"], bool
    ):
        raise ModelAuthorityError(
            "model_authority generation must be a TOML integer"
        )
    head = ModelAuthorityHead(
        system_id=section["system_id"],
        snapshot_fingerprint=section["observed_snapshot_fingerprint"],
        subject_revision=section["subject_revision"],
        generation=section["generation"],
        accepted_revision_set_fingerprint=section[
            "accepted_revision_set_fingerprint"
        ],
        previous_snapshot_fingerprint=section[
            "previous_snapshot_fingerprint"
        ],
        activation_receipt_fingerprint=section[
            "activation_receipt_fingerprint"
        ],
    )
    if section["head_fingerprint"] != head.fingerprint:
        raise ModelAuthorityError("model authority head fingerprint is stale")
    return head


def render_model_authority_section(
    head: ModelAuthorityHead,
    *,
    snapshot_path: str,
    coverage_status: str,
) -> str:
    path = _relative_path(snapshot_path, "observed_snapshot_path")
    values = {
        "system_id": head.system_id,
        "observed_snapshot_path": path,
        "observed_snapshot_fingerprint": head.snapshot_fingerprint,
        "subject_revision": head.subject_revision,
        "coverage_status": str(coverage_status),
        "generation": head.generation,
        "accepted_revision_set_fingerprint": (
            head.accepted_revision_set_fingerprint
        ),
        "previous_snapshot_fingerprint": (
            head.previous_snapshot_fingerprint
        ),
        "activation_receipt_fingerprint": (
            head.activation_receipt_fingerprint
        ),
        "head_fingerprint": head.fingerprint,
    }
    return (
        "[model_authority]\n"
        f"system_id = {json.dumps(values['system_id'])}\n"
        "observed_snapshot_path = "
        f"{json.dumps(values['observed_snapshot_path'])}\n"
        "observed_snapshot_fingerprint = "
        f"{json.dumps(values['observed_snapshot_fingerprint'])}\n"
        f"subject_revision = {json.dumps(values['subject_revision'])}\n"
        f"coverage_status = {json.dumps(values['coverage_status'])}\n"
        f"generation = {values['generation']}\n"
        "accepted_revision_set_fingerprint = "
        f"{json.dumps(values['accepted_revision_set_fingerprint'])}\n"
        "previous_snapshot_fingerprint = "
        f"{json.dumps(values['previous_snapshot_fingerprint'])}\n"
        "activation_receipt_fingerprint = "
        f"{json.dumps(values['activation_receipt_fingerprint'])}\n"
        f"head_fingerprint = {json.dumps(values['head_fingerprint'])}\n"
    )


def replace_model_authority_section(
    manifest_text: str,
    section_text: str,
) -> str:
    base = _SECTION_RE.sub("", manifest_text).rstrip()
    return base + "\n\n" + section_text.strip() + "\n"


def _replace_authority_section_cas(
    manifest_path: Path,
    *,
    frozen_text: str,
    section_text: str,
) -> None:
    """Preserve peer sections and replace only the still-owned authority head."""

    fresh_text = read_manifest_text(manifest_path)
    if _section(fresh_text) != _section(frozen_text):
        raise ModelAuthorityError(
            "model authority section changed before pointer replacement"
        )
    fresh_fingerprint = manifest_text_fingerprint(fresh_text)
    replace_project_manifest_locked(
        manifest_path,
        replace_model_authority_section(fresh_text, section_text),
        expected_fingerprint=fresh_fingerprint,
    )


def _snapshot_path(root: Path, snapshot: ModelSystemSnapshot) -> str:
    digest = snapshot.fingerprint.split(":", 1)[1]
    return f".flowguard/models/authority/snapshots/{digest}.json"


def _write_immutable_json(
    root: Path,
    category: str,
    fingerprint: str,
    payload: Mapping[str, Any],
) -> Path:
    digest = fingerprint.split(":", 1)[1]
    path = root / ".flowguard" / "models" / "authority" / category / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    io_path = _windows_io_path(path)
    if io_path.exists():
        if io_path.read_text(encoding="utf-8") != text:
            raise ModelAuthorityError(
                f"immutable {category} path contains different bytes"
            )
        return path
    # The projection writers can run concurrently while independent owners
    # finish.  A shared ``<digest>.json.tmp`` lets one writer remove another
    # writer's temporary path between ``write`` and ``replace``.  Give every
    # immutable write its own same-directory temporary inode instead.
    descriptor, temporary_name = tempfile.mkstemp(
        # Keep the temporary basename short: bootstrap staging roots can
        # already approach Windows MAX_PATH before the content hash is added.
        # mkstemp supplies the collision-resistant suffix within this one
        # directory, so the hash does not need to be repeated in the name.
        prefix=".fg",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(_windows_io_path(temporary), _windows_io_path(path))
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return path


def _artifact_path(root: Path, category: str, fingerprint: str) -> Path:
    if not isinstance(fingerprint, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", fingerprint
    ):
        raise ModelAuthorityError(
            f"{category} fingerprint must be a canonical sha256 identity"
        )
    return (
        root
        / ".flowguard"
        / "models"
        / "authority"
        / category
        / f"{fingerprint.split(':', 1)[1]}.json"
    )


def _read_content_addressed_payload(
    root: Path,
    category: str,
    fingerprint: str,
    *,
    derived_fields: Iterable[str] = ("fingerprint",),
) -> Mapping[str, Any]:
    path = _artifact_path(root, category, fingerprint)
    try:
        payload = json.loads(
            _windows_io_path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError, ValueError) as exc:
        raise ModelAuthorityError(
            f"current {category} artifact is invalid: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ModelAuthorityError(
            f"current {category} artifact must be a JSON object"
        )
    if payload.get("fingerprint") != fingerprint:
        raise ModelAuthorityError(
            f"current {category} fingerprint does not match its path"
        )
    identity = {
        key: value
        for key, value in payload.items()
        if key not in set(derived_fields)
    }
    if canonical_fingerprint(identity) != fingerprint:
        raise ModelAuthorityError(
            f"current {category} content fingerprint is stale"
        )
    return payload


def _projection_model_id(instance: Any) -> str:
    model_id = str(getattr(instance, "logical_model_id", "") or "").strip()
    if not model_id:
        raise ModelAuthorityError("accepted read projection model has no logical_model_id")
    return model_id


def _projection_endpoint(
    endpoint: Any,
    *,
    instances_by_fingerprint: Mapping[str, Any],
) -> dict[str, str]:
    """Serialize one relation endpoint without expanding a neighbor model."""

    kind = str(getattr(endpoint, "endpoint_kind", "") or "")
    endpoint_id = str(getattr(endpoint, "endpoint_id", "") or "")
    fingerprint = str(getattr(endpoint, "fingerprint", "") or "")
    if kind == "model_instance":
        instance = instances_by_fingerprint.get(fingerprint)
        if instance is None:
            raise ModelAuthorityError(
                f"accepted read projection relation references unknown model fingerprint: {fingerprint}"
            )
        model_id = _projection_model_id(instance)
        if endpoint_id in {"", f"model:{model_id}"}:
            endpoint_id = f"model:{model_id}"
        return {
            "endpoint_kind": kind,
            "endpoint_id": endpoint_id,
            "model_id": model_id,
            "model_path": str(getattr(instance, "model_path", "")).replace("\\", "/"),
            "fingerprint": fingerprint,
            "owner_route": str(getattr(endpoint, "owner_route", "") or ""),
        }
    return {
        "endpoint_kind": kind,
        "endpoint_id": endpoint_id,
        "fingerprint": fingerprint,
        "owner_route": str(getattr(endpoint, "owner_route", "") or ""),
    }


def _projection_intent_refs(
    revision_set: ModelRevisionSet | None,
    model_id: str,
) -> tuple[dict[str, str], ...]:
    """Select only active intent identities owned by one model."""

    if revision_set is None:
        return ()
    view = revision_set.current_effective_intent_view
    identities = {
        str(getattr(item, "contribution_id", "")): item
        for item in getattr(view, "verified_source_identities", ())
    }
    rows: list[dict[str, str]] = []
    for contribution in getattr(view, "active_contributions", ()):
        owner = str(getattr(contribution, "logical_model_id", "") or "")
        owner = owner.removeprefix("model:")
        if owner != model_id:
            continue
        contribution_id = str(getattr(contribution, "contribution_id", "") or "")
        identity = identities.get(contribution_id)
        source_ref = str(
            getattr(identity, "source_ref", "")
            if identity is not None
            else getattr(contribution, "source_ref", "")
        ).replace("\\", "/")
        source_fingerprint = str(
            getattr(identity, "source_fingerprint", "")
            if identity is not None
            else getattr(contribution, "source_fingerprint", "")
        )
        authority_kind = str(
            getattr(identity, "authority_kind", "")
            if identity is not None
            else getattr(contribution, "source_kind", "")
        )
        rows.append(
            {
                "contribution_id": contribution_id,
                "authority_kind": authority_kind,
                "source_ref": source_ref,
                "source_fingerprint": source_fingerprint,
                "logical_model_id": model_id,
            }
        )
    return tuple(sorted(rows, key=lambda item: (item["contribution_id"], item["source_ref"])))


def _build_accepted_read_projection(
    head: ModelAuthorityHead,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet | None,
    *,
    transition_evidence: Mapping[str, Any] | None = None,
    inherited_evidence_revision_fingerprint: str = "",
) -> tuple[str, dict[str, Any], tuple[tuple[str, dict[str, Any]], ...]]:
    """Derive the one immutable selected-read index and its model shards.

    The projection is a transport view of the accepted candidate.  It has no
    independent current pointer: the activation receipt ID is derived from
    the index identity and the existing head points to that receipt.
    """

    instances = tuple(sorted(candidate_snapshot.model_instances, key=_projection_model_id))
    model_ids = tuple(_projection_model_id(item) for item in instances)
    if len(model_ids) != len(set(model_ids)):
        raise ModelAuthorityError("accepted read projection contains duplicate model IDs")
    by_fingerprint = {
        str(getattr(item, "fingerprint", "")): item for item in instances
    }
    by_model_id = { _projection_model_id(item): item for item in instances }
    boundary_rows: dict[tuple[str, str, str], dict[str, str]] = {}
    for endpoint in getattr(candidate_snapshot, "owner_artifact_refs", ()):
        if str(getattr(endpoint, "endpoint_kind", "")) != "boundary_contract":
            continue
        value = _projection_endpoint(endpoint, instances_by_fingerprint=by_fingerprint)
        boundary_rows[(value["endpoint_kind"], value["endpoint_id"], value["fingerprint"])] = value

    relations_by_model: dict[str, list[dict[str, Any]]] = {model_id: [] for model_id in model_ids}
    boundaries_by_model: dict[str, dict[tuple[str, str, str], dict[str, str]]] = {
        model_id: {} for model_id in model_ids
    }
    for relation in getattr(candidate_snapshot, "relations", ()):
        source = _projection_endpoint(
            getattr(relation, "source", None),
            instances_by_fingerprint=by_fingerprint,
        )
        target = _projection_endpoint(
            getattr(relation, "target", None),
            instances_by_fingerprint=by_fingerprint,
        )
        row = {
            "relation_id": str(getattr(relation, "relation_id", "") or ""),
            "kind": str(getattr(relation, "kind", "") or ""),
            "source": source,
            "target": target,
            "evidence_fingerprints": sorted(
                str(item) for item in getattr(relation, "evidence_fingerprints", ())
            ),
        }
        model_endpoints = {
            str(source.get("model_id", "")),
            str(target.get("model_id", "")),
        } & set(model_ids)
        for model_id in sorted(model_endpoints):
            relations_by_model[model_id].append(row)
            for endpoint in (source, target):
                if endpoint.get("endpoint_kind") != "model_instance":
                    key = (
                        str(endpoint.get("endpoint_kind", "")),
                        str(endpoint.get("endpoint_id", "")),
                        str(endpoint.get("fingerprint", "")),
                    )
                    boundaries_by_model[model_id][key] = endpoint

    for model_id in model_ids:
        boundaries_by_model[model_id].update(boundary_rows)

    shards: list[tuple[str, dict[str, Any]]] = []
    index_models: dict[str, dict[str, str]] = {}
    for model_id in model_ids:
        instance = by_model_id[model_id]
        source_paths: dict[str, str] = {}
        for path, expected in (
            (getattr(instance, "model_path", ""), getattr(instance, "model_sha256", "")),
            (getattr(instance, "runner_path", ""), getattr(instance, "runner_sha256", "")),
        ):
            if str(path).strip() and str(expected).strip():
                source_paths[str(path).replace("\\", "/")] = str(expected)
        for item in getattr(instance, "inputs", ()):
            path = str(getattr(item, "path", "") or "").replace("\\", "/")
            expected = str(getattr(item, "sha256", "") or "")
            if path and expected:
                previous = source_paths.get(path)
                if previous is not None and previous != expected:
                    raise ModelAuthorityError(
                        f"accepted read projection has conflicting source fingerprints: {path}"
                    )
                source_paths[path] = expected
        intent_refs = _projection_intent_refs(revision_set, model_id)
        for intent in intent_refs:
            if intent["authority_kind"] == "project_file" and intent["source_ref"]:
                source_paths[intent["source_ref"]] = intent["source_fingerprint"]
        contract_refs = tuple(
            dict(item)
            for item in sorted(
                boundaries_by_model[model_id].values(),
                key=lambda item: (
                    str(item.get("endpoint_kind", "")),
                    str(item.get("endpoint_id", "")),
                    str(item.get("fingerprint", "")),
                ),
            )
        )
        shard_identity: dict[str, Any] = {
            "schema": _READ_PROJECTION_SHARD_SCHEMA,
            "system_id": candidate_snapshot.system_id,
            "candidate_snapshot_fingerprint": candidate_snapshot.fingerprint,
            "logical_model_id": model_id,
            "model": _selected_model_mapping(instance),
            "intent_refs": [dict(item) for item in intent_refs],
            "relations": sorted(
                relations_by_model[model_id],
                key=lambda item: str(item.get("relation_id", "")),
            ),
            "boundary_nodes": list(contract_refs),
            "source_paths": dict(sorted(source_paths.items())),
        }
        shard_fingerprint = canonical_fingerprint(shard_identity)
        shard_payload = {**shard_identity, "fingerprint": shard_fingerprint}
        shards.append((shard_fingerprint, shard_payload))
        index_models[model_id] = {
            "model_path": str(getattr(instance, "model_path", "")).replace("\\", "/"),
            "model_fingerprint": str(getattr(instance, "fingerprint", "")),
            "shard_fingerprint": shard_fingerprint,
        }

    index_identity: dict[str, Any] = {
        "schema": _READ_PROJECTION_INDEX_SCHEMA,
        "system_id": candidate_snapshot.system_id,
        "candidate_snapshot_fingerprint": candidate_snapshot.fingerprint,
        "revision_set_fingerprint": str(
            getattr(revision_set, "fingerprint", "") or head.accepted_revision_set_fingerprint
        ),
        "expected_head_fingerprint": head.fingerprint,
        "previous_snapshot_fingerprint": head.snapshot_fingerprint,
        "subject_revision": candidate_snapshot.subject_revision,
        "next_generation": head.generation + 1,
        "coverage_status": candidate_snapshot.coverage_status,
        "unresolved_gap_count": len(candidate_snapshot.unresolved_gap_ids),
        "inherited_evidence_revision_fingerprint": inherited_evidence_revision_fingerprint,
        "transition_evidence": (
            dict(transition_evidence) if transition_evidence is not None else None
        ),
        "models": {model_id: index_models[model_id] for model_id in sorted(index_models)},
    }
    index_fingerprint = canonical_fingerprint(index_identity)
    return index_fingerprint, {**index_identity, "fingerprint": index_fingerprint}, tuple(shards)


def _persist_accepted_read_projection(
    root: Path,
    index_fingerprint: str,
    index_payload: Mapping[str, Any],
    shards: Iterable[tuple[str, Mapping[str, Any]]],
) -> None:
    """Persist immutable shards before their single index becomes reachable."""

    for fingerprint, payload in shards:
        _write_immutable_json(root, "read-model-shards", fingerprint, payload)
    _write_immutable_json(root, "read-projection-indexes", index_fingerprint, index_payload)


def _load_bound_read_projection(
    root: Path,
    head: ModelAuthorityHead,
) -> dict[str, Any]:
    """Load the only projection bound by the current activation receipt."""

    receipt = _load_activation_receipt(root, head.activation_receipt_fingerprint)
    match = _ACTIVATION_PROJECTION_ID_RE.fullmatch(receipt.receipt_id)
    if match is None:
        raise ModelAuthorityError(
            "current activation receipt is not bound to an accepted read projection"
        )
    index_fingerprint = f"sha256:{match.group(1)}"
    index = _read_content_addressed_payload(
        root,
        "read-projection-indexes",
        index_fingerprint,
    )
    expected = {
        "system_id": head.system_id,
        "candidate_snapshot_fingerprint": head.snapshot_fingerprint,
        "revision_set_fingerprint": head.accepted_revision_set_fingerprint,
        "expected_head_fingerprint": receipt.expected_head_fingerprint,
        "previous_snapshot_fingerprint": receipt.previous_snapshot_fingerprint,
        "subject_revision": head.subject_revision,
        "next_generation": head.generation,
    }
    for field_name, expected_value in expected.items():
        if index.get(field_name) != expected_value:
            raise ModelAuthorityError(
                f"accepted read projection {field_name} does not match current authority"
            )
    if receipt.system_id != head.system_id or receipt.next_generation != head.generation:
        raise ModelAuthorityError("current activation receipt is not bound to current head")
    if receipt.candidate_snapshot_fingerprint != head.snapshot_fingerprint:
        raise ModelAuthorityError("current activation candidate does not match current head")
    if receipt.revision_set_fingerprint != head.accepted_revision_set_fingerprint:
        raise ModelAuthorityError("current activation revision does not match current head")
    if receipt.subject_revision != head.subject_revision:
        raise ModelAuthorityError("current activation subject revision does not match current head")
    models = index.get("models")
    if not isinstance(models, Mapping) or not models:
        raise ModelAuthorityError("accepted read projection has no model index")
    return {
        "receipt": receipt,
        "index_fingerprint": index_fingerprint,
        "index": index,
    }


def _load_selected_read_shards(
    root: Path,
    projection: Mapping[str, Any],
    selected_model_ids: Iterable[str],
) -> tuple[Mapping[str, Any], ...]:
    """Load exactly the requested shard objects; never discover neighbors."""

    index = projection.get("index")
    models = index.get("models") if isinstance(index, Mapping) else None
    if not isinstance(models, Mapping):
        raise ModelAuthorityError("accepted read projection model index is invalid")
    rows: list[Mapping[str, Any]] = []
    for raw_model_id in selected_model_ids:
        model_id = str(raw_model_id).strip()
        row = models.get(model_id)
        if not isinstance(row, Mapping):
            raise ModelAuthorityError(f"selected model is not present in accepted read projection: {model_id}")
        fingerprint = str(row.get("shard_fingerprint", ""))
        shard = _read_content_addressed_payload(root, "read-model-shards", fingerprint)
        shard_model = shard.get("model")
        if not isinstance(shard_model, Mapping):
            raise ModelAuthorityError(
                f"selected read projection shard model is invalid: {model_id}"
            )
        if (
            shard.get("schema") != _READ_PROJECTION_SHARD_SCHEMA
            or shard.get("system_id") != index.get("system_id")
            or shard.get("candidate_snapshot_fingerprint")
            != index.get("candidate_snapshot_fingerprint")
            or shard.get("logical_model_id") != model_id
        ):
            raise ModelAuthorityError(f"selected read projection shard is not bound: {model_id}")
        if shard.get("fingerprint") != fingerprint:
            raise ModelAuthorityError(f"selected read projection shard fingerprint is stale: {model_id}")
        if shard_model.get("fingerprint") != row.get("model_fingerprint"):
            raise ModelAuthorityError(f"selected read projection model fingerprint is stale: {model_id}")
        rows.append(shard)
    return tuple(rows)


def _selected_json_value(value: Any) -> Any:
    """Return a JSON-friendly value without discovering additional paths."""

    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _selected_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_selected_json_value(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            str(key): _selected_json_value(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return value


def _selected_model_mapping(instance: Any) -> dict[str, Any]:
    """Serialize a typed model instance (or a narrow test double)."""

    value = _selected_json_value(instance)
    if isinstance(value, Mapping):
        return dict(value)
    return {
        "logical_model_id": str(getattr(instance, "logical_model_id", "")),
        "model_kind": str(getattr(instance, "model_kind", "")),
        "model_path": str(getattr(instance, "model_path", "")),
        "model_sha256": str(getattr(instance, "model_sha256", "")),
        "runner_path": str(getattr(instance, "runner_path", "")),
        "runner_sha256": str(getattr(instance, "runner_sha256", "")),
        "purpose_closure_fingerprint": str(
            getattr(instance, "purpose_closure_fingerprint", "")
        ),
        "inputs": _selected_json_value(getattr(instance, "inputs", ())),
        "fingerprint": str(getattr(instance, "fingerprint", "")),
    }


def _selected_endpoint_mapping(endpoint: Any) -> dict[str, Any]:
    value = _selected_json_value(endpoint)
    if isinstance(value, Mapping):
        return dict(value)
    return {
        "endpoint_kind": str(getattr(endpoint, "endpoint_kind", "")),
        "endpoint_id": str(getattr(endpoint, "endpoint_id", "")),
        "fingerprint": str(getattr(endpoint, "fingerprint", "")),
        "owner_route": str(getattr(endpoint, "owner_route", "")),
    }


def _selected_relation_mapping(relation: Any) -> dict[str, Any]:
    value = _selected_json_value(relation)
    if isinstance(value, Mapping):
        return dict(value)
    return {
        "relation_id": str(getattr(relation, "relation_id", "")),
        "kind": str(getattr(relation, "kind", "")),
        "source": _selected_endpoint_mapping(getattr(relation, "source", None)),
        "target": _selected_endpoint_mapping(getattr(relation, "target", None)),
        "evidence_fingerprints": list(
            getattr(relation, "evidence_fingerprints", ())
        ),
    }


def _selected_normalize_path(value: Any, field_name: str) -> str:
    """Normalize a selected path using the current-authority boundary."""

    return _assert_current_authority_path(value, field_name)


def _selected_reparse_point(path: Path) -> bool:
    """Reject symlink/reparse components before consuming selected bytes."""

    try:
        info = path.lstat()
    except OSError:
        return False
    attributes = int(getattr(info, "st_file_attributes", 0) or 0)
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return path.is_symlink() or bool(attributes & reparse_flag)


def _selected_file_bytes(root: Path, relative: str) -> bytes:
    """Read one exact repository-relative file after component validation."""

    candidate = root / relative
    cursor = root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        cursor = cursor / part
        if _selected_reparse_point(cursor):
            raise ModelAuthorityError(
                f"selected path contains a symlink or reparse point: {relative}"
            )
        try:
            info = cursor.lstat()
        except OSError as exc:
            raise ModelAuthorityError(
                f"selected path is unavailable: {relative}"
            ) from exc
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ModelAuthorityError(
                f"selected path component is not a directory: {relative}"
            )
        if index == len(parts) - 1 and not stat.S_ISREG(info.st_mode):
            raise ModelAuthorityError(
                f"selected path is not a regular file: {relative}"
            )
    try:
        # Keep this as the sole content read for the path.  In particular, do
        # not call source_file_fingerprint(), which would read it a second
        # time and defeat shared-input de-duplication.
        return candidate.read_bytes()
    except OSError as exc:
        raise ModelAuthorityError(
            f"selected path is unavailable: {relative}"
        ) from exc


def _selected_source_fingerprint(
    root: Path,
    relative: str,
    payload: bytes,
) -> str:
    """Match the fingerprint used when the model input was frozen.

    Model-instance inputs are created by ``build_model_instance_ref`` from
    ``functional_source_fingerprint``.  That projection intentionally
    ignores non-functional OpenSpec task checkbox and line-ending churn.  The
    projection reader must use the same identity; comparing those inputs with
    a raw byte hash falsely marks an otherwise current authority as stale.
    ``payload`` is retained for the ordinary source path fast path so the
    selected file is still read exactly once by the caller.
    """

    if (
        str(relative).replace("\\", "/").startswith("openspec/changes/")
        and str(relative).replace("\\", "/").endswith("/tasks.md")
    ):
        return functional_source_fingerprint(root, relative)

    canonical = payload
    if PurePosixPath(relative).suffix.casefold() in CANONICAL_TEXT_SUFFIXES:
        try:
            canonical = (
                payload.decode("utf-8")
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .encode("utf-8")
            )
        except UnicodeDecodeError:
            canonical = payload
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _selected_artifact_fingerprint(payload: bytes, *, category: str) -> str:
    """Validate a JSON authority object identity from already-read bytes."""

    try:
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ModelAuthorityError, ValueError) as exc:
        raise ModelAuthorityError(
            f"selected {category} artifact is invalid: {exc}"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise ModelAuthorityError(f"selected {category} artifact must be an object")
    fingerprint = parsed.get("fingerprint")
    if not isinstance(fingerprint, str):
        raise ModelAuthorityError(
            f"selected {category} artifact has no canonical fingerprint"
        )
    identity = {
        key: value for key, value in parsed.items() if key != "fingerprint"
    }
    if canonical_fingerprint(identity) != fingerprint:
        raise ModelAuthorityError(
            f"selected {category} artifact content fingerprint is stale"
        )
    return fingerprint


def _selected_path_relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ModelAuthorityError(
            f"selected authority artifact escapes project root: {path}"
        ) from exc


def _selected_source_status(
    *,
    root: Path,
    paths: Mapping[str, str],
    findings: list[dict[str, Any]],
    stale_details: list[dict[str, Any]],
    read_cache: dict[str, str],
    read_counts: dict[str, int],
) -> None:
    """Read selected source paths exactly once and record stale obligations."""

    for relative, expected in paths.items():
        try:
            normalized = _selected_normalize_path(relative, "selected_source.path")
            if normalized != relative:
                # The authority snapshot is canonical; a non-canonical spelling
                # is an integrity finding rather than a reason to probe a
                # second path that could be a lexical alias.
                raise ModelAuthorityError(
                    f"selected source path is not canonical: {relative}"
                )
            if normalized in read_cache:
                actual = read_cache[normalized]
            else:
                payload = _selected_file_bytes(root, normalized)
                actual = _selected_source_fingerprint(root, normalized, payload)
                read_cache[normalized] = actual
                read_counts[normalized] = read_counts.get(normalized, 0) + 1
        except (ModelAuthorityError, OSError, ValueError) as exc:
            code = "selected_source_unavailable"
            detail = {
                "code": code,
                "path": str(relative),
                "expected_fingerprint": str(expected),
                "message": str(exc),
            }
            findings.append(detail)
            stale_details.append(detail)
            continue
        if actual != str(expected):
            detail = {
                "code": "selected_source_stale",
                "path": normalized,
                "expected_fingerprint": str(expected),
                "observed_fingerprint": actual,
                "message": "selected source differs from the accepted authority map",
            }
            findings.append(detail)
            stale_details.append(detail)


def read_selected_model_closure(
    root: str | Path,
    *,
    selected_model_ids: Iterable[str] = (),
    selected_owner_ids: Iterable[str] = (),
    changed_paths: Iterable[str] = (),
    inventory_scope: str = "selected_owner_closure",
    head: ModelAuthorityHead | None = None,
    snapshot: ModelSystemSnapshot | None = None,
    authority_state: CurrentModelAuthorityState | None = None,
) -> SelectedModelClosureRead:
    """Read one exact model/input/runner/intent/contract closure.

    This is the local navigation reader used by light preflight.  It starts
    from explicit owner/model/path identities, follows only typed model
    relations and shared input paths, and never falls back to a repository
    search.  The optional ``head``/``snapshot``/``authority_state`` arguments
    let callers pass the single already-loaded authority pair; they are useful
    for avoiding duplicate reads and for narrow fixture tests.
    """

    root_path = Path(root).resolve()
    findings: list[dict[str, Any]] = []
    stale_details: list[dict[str, Any]] = []
    stale_obligations: list[str] = []
    read_cache: dict[str, str] = {}
    read_counts: dict[str, int] = {}
    state = authority_state
    loaded_head = head
    loaded_snapshot = snapshot
    if state is not None and loaded_head is None and loaded_snapshot is None:
        # A caller that already resolved the current state should not force a
        # second manifest/snapshot load just to obtain its exact pair.
        loaded_head = getattr(state, "head", None)
        loaded_snapshot = getattr(state, "snapshot", None)

    try:
        if (
            (loaded_head is None) != (loaded_snapshot is None)
            and (
                isinstance(loaded_head, ModelAuthorityHead)
                or isinstance(loaded_snapshot, ModelSystemSnapshot)
            )
        ):
            raise ModelAuthorityError(
                "selected closure requires both head and snapshot or neither"
            )
        if loaded_head is None and loaded_snapshot is None:
            loaded_head, loaded_snapshot = load_observed_model_system(root_path)
        # Real v5 authority receives the same integrity/ancestry validation as
        # a normal reader, but deliberately keeps current source revalidation
        # disabled.  The selected source reader below revalidates only the
        # exact files it consumes.  Narrow SimpleNamespace fixtures are kept
        # usable without inventing a fake transition chain.
        if state is None and isinstance(loaded_head, ModelAuthorityHead) and isinstance(
            loaded_snapshot, ModelSystemSnapshot
        ):
            state = load_current_model_authority_state(
                root_path,
                head=loaded_head,
                snapshot=loaded_snapshot,
                reverify_current_sources=False,
            )
        if loaded_snapshot is None:
            raise ModelAuthorityError("observed model snapshot is unavailable")
        if isinstance(loaded_snapshot, ModelSystemSnapshot):
            _assert_snapshot_current_paths(loaded_snapshot)
        elif not hasattr(loaded_snapshot, "model_instances"):
            raise ModelAuthorityError("observed model snapshot is not typed")
    except (ModelAuthorityError, ProjectManifestError, ValueError, OSError) as exc:
        message = str(exc)
        findings.append(
            {
                "code": "authority_integrity_blocked",
                "message": message,
                "severity": "blocked",
            }
        )
        return SelectedModelClosureRead(
            authority_integrity=MODEL_AUTHORITY_STATUS_BLOCKED,
            selected_source_currentness=SELECTED_SOURCE_UNAVAILABLE,
            execution_evidence_status=EXECUTION_EVIDENCE_NOT_RUN,
            findings=tuple(findings),
            stale_obligations=("authority_integrity:blocked",),
            stale_obligation_details=tuple(stale_details),
            producer_count=0,
            write_count=0,
        )

    snapshot_value = loaded_snapshot
    snapshot_fingerprint = str(getattr(snapshot_value, "fingerprint", ""))
    subject_revision = str(getattr(snapshot_value, "subject_revision", ""))
    head_fingerprint = str(getattr(loaded_head, "fingerprint", ""))
    revision_fingerprint = str(
        getattr(loaded_head, "accepted_revision_set_fingerprint", "")
    )
    as_of = {
        "subject_revision": subject_revision,
        "snapshot_fingerprint": snapshot_fingerprint,
        "authority_head_fingerprint": head_fingerprint,
        "accepted_revision_set_fingerprint": revision_fingerprint,
    }

    instances = tuple(getattr(snapshot_value, "model_instances", ()))
    by_fingerprint = {
        str(getattr(item, "fingerprint", "")): item for item in instances
    }

    def exact_owner_match(owner: str, instance: Any) -> bool:
        value = str(owner or "").strip()
        model_id = str(getattr(instance, "logical_model_id", ""))
        fingerprint = str(getattr(instance, "fingerprint", ""))
        model_path = str(getattr(instance, "model_path", ""))
        return value in {
            model_id,
            f"model:{model_id}",
            f"model-obligation:{model_id}",
            fingerprint,
            f"model-authority:{fingerprint}",
            model_path,
        }

    requested_ids = {
        str(value).strip().removeprefix("model:")
        for value in selected_model_ids
        if str(value).strip()
    }
    requested_owners = {
        str(value).strip() for value in selected_owner_ids if str(value).strip()
    }
    normalized_changed: set[str] = set()
    for index, value in enumerate(changed_paths):
        try:
            normalized_changed.add(
                _selected_normalize_path(value, f"changed_paths[{index}]")
            )
        except (ModelAuthorityError, ValueError) as exc:
            findings.append(
                {
                    "code": "changed_path_unsafe",
                    "path": str(value),
                    "message": str(exc),
                    "severity": "blocked",
                }
            )

    selected_fingerprints: set[str] = set()
    if inventory_scope == "broad_authority_inventory":
        selected_fingerprints.update(by_fingerprint)
    elif inventory_scope != "selected_owner_closure":
        findings.append(
            {
                "code": "selected_inventory_scope_invalid",
                "scope": str(inventory_scope),
                "message": "selected closure reader accepts only its typed selected or explicit broad scope",
                "severity": "blocked",
            }
        )
    else:
        for instance in instances:
            identity = str(getattr(instance, "logical_model_id", ""))
            if identity in requested_ids or any(
                exact_owner_match(owner, instance) for owner in requested_owners
            ):
                selected_fingerprints.add(str(getattr(instance, "fingerprint", "")))
                continue
            instance_paths = {
                str(getattr(instance, "model_path", "")).replace("\\", "/"),
                str(getattr(instance, "runner_path", "")).replace("\\", "/"),
            }
            instance_paths.update(
                str(getattr(item, "path", "")).replace("\\", "/")
                for item in getattr(instance, "inputs", ())
            )
            if normalized_changed & instance_paths:
                selected_fingerprints.add(str(getattr(instance, "fingerprint", "")))

    # Follow only declared model-to-model edges and exact shared-input paths.
    # The protocol intentionally uses one-hop relations for local navigation;
    # callers needing a deeper proof must ask the model mesh route explicitly.
    # A shared input makes another owner affected only when that exact input is
    # one of the caller's changed roots.  Merely sharing a stable manifest or
    # config input must not turn every owner into a selected closure.
    selected_inputs = {
        str(getattr(input_ref, "path", "")).replace("\\", "/")
        for instance in instances
        if str(getattr(instance, "fingerprint", "")) in selected_fingerprints
        for input_ref in getattr(instance, "inputs", ())
    } & normalized_changed
    if selected_inputs:
        for instance in instances:
            if str(getattr(instance, "fingerprint", "")) in selected_fingerprints:
                continue
            input_paths = {
                str(getattr(item, "path", "")).replace("\\", "/")
                for item in getattr(instance, "inputs", ())
            }
            if selected_inputs & input_paths:
                selected_fingerprints.add(str(getattr(instance, "fingerprint", "")))
    initial_model_fingerprints = set(selected_fingerprints)
    for relation in getattr(snapshot_value, "relations", ()):
        source = getattr(relation, "source", None)
        target = getattr(relation, "target", None)
        if (
            getattr(source, "endpoint_kind", "") != "model_instance"
            or getattr(target, "endpoint_kind", "") != "model_instance"
        ):
            continue
        source_fp = str(getattr(source, "fingerprint", ""))
        target_fp = str(getattr(target, "fingerprint", ""))
        if source_fp in initial_model_fingerprints:
            selected_fingerprints.add(target_fp)
        if target_fp in initial_model_fingerprints:
            selected_fingerprints.add(source_fp)

    if not selected_fingerprints and inventory_scope == "selected_owner_closure":
        findings.append(
            {
                "code": "selected_owner_not_resolved",
                "message": "no exact selected model, owner, or changed-path binding was supplied",
                "severity": "scoped",
            }
        )

    selected_instances = tuple(
        instance
        for instance in instances
        if str(getattr(instance, "fingerprint", "")) in selected_fingerprints
    )
    selected_models = tuple(
        _selected_model_mapping(instance) for instance in selected_instances
    )
    selected_model_ids_value = tuple(
        str(getattr(instance, "logical_model_id", "")) for instance in selected_instances
    )
    selected_model_paths = tuple(
        str(getattr(instance, "model_path", "")).replace("\\", "/")
        for instance in selected_instances
    )
    selected_runner_paths = tuple(
        str(getattr(instance, "runner_path", "")).replace("\\", "/")
        for instance in selected_instances
    )
    selected_input_paths = tuple(
        sorted(
            {
                str(getattr(item, "path", "")).replace("\\", "/")
                for instance in selected_instances
                for item in getattr(instance, "inputs", ())
            }
        )
    )

    expected_sources: dict[str, str] = {}

    def add_source(path: Any, expected: Any) -> None:
        relative = str(path or "").replace("\\", "/")
        if not relative:
            return
        expected_value = str(expected or "")
        # Typed current snapshots always carry a sha256 for every selected
        # model/runner/input.  Compact test doubles from older callers may
        # only carry an identity/path; keep those readable without claiming a
        # content check that has no declared expected fingerprint.
        if not expected_value:
            return
        if relative in expected_sources and expected_sources[relative] != expected_value:
            detail = {
                "code": "shared_source_fingerprint_conflict",
                "path": relative,
                "expected_fingerprints": sorted(
                    {expected_sources[relative], expected_value}
                ),
                "message": "one shared selected path has conflicting accepted fingerprints",
            }
            findings.append(detail)
            stale_details.append(detail)
        else:
            expected_sources.setdefault(relative, expected_value)

    for instance in selected_instances:
        add_source(
            getattr(instance, "model_path", ""),
            getattr(instance, "model_sha256", ""),
        )
        add_source(
            getattr(instance, "runner_path", ""),
            getattr(instance, "runner_sha256", ""),
        )
        for input_ref in getattr(instance, "inputs", ()):
            add_source(
                getattr(input_ref, "path", ""),
                getattr(input_ref, "sha256", ""),
            )

    selected_intent_refs: list[Mapping[str, Any]] = []
    selected_intent_paths: list[str] = []
    if state is not None:
        revision = getattr(state, "accepted_revision", None)
        view = getattr(revision, "current_effective_intent_view", None)
        for contribution in getattr(view, "active_contributions", ()):
            model_id = str(getattr(contribution, "logical_model_id", ""))
            if model_id.startswith("model:"):
                model_id = model_id.removeprefix("model:")
            if model_id not in set(selected_model_ids_value):
                continue
            contribution_id = str(getattr(contribution, "contribution_id", ""))
            source_ref = str(getattr(contribution, "source_ref", ""))
            source_fingerprint = str(getattr(contribution, "source_fingerprint", ""))
            authority_kind = str(getattr(contribution, "source_kind", ""))
            # The accepted source identities are the authority for whether a
            # contribution is a project file or an external WorkContext.  If
            # the compact fixture has no identity object, retain the exact
            # contribution fields without guessing a path from repository text.
            for identity in getattr(view, "verified_source_identities", ()):
                if str(getattr(identity, "contribution_id", "")) != contribution_id:
                    continue
                authority_kind = str(getattr(identity, "authority_kind", authority_kind))
                source_ref = str(getattr(identity, "source_ref", source_ref))
                source_fingerprint = str(
                    getattr(identity, "source_fingerprint", source_fingerprint)
                )
                break
            ref = {
                "contribution_id": contribution_id,
                "authority_kind": authority_kind,
                "source_ref": source_ref,
                "source_fingerprint": source_fingerprint,
                "logical_model_id": model_id,
            }
            selected_intent_refs.append(ref)
            if authority_kind == "project_file":
                selected_intent_paths.append(source_ref.replace("\\", "/"))
                add_source(source_ref, source_fingerprint)

    selected_contract_refs: list[Mapping[str, Any]] = []
    selected_contract_paths: list[str] = []
    relation_values: list[Mapping[str, Any]] = []
    selected_endpoint_keys: set[tuple[str, str, str]] = set()
    for relation in getattr(snapshot_value, "relations", ()):
        source = getattr(relation, "source", None)
        target = getattr(relation, "target", None)
        source_fp = str(getattr(source, "fingerprint", ""))
        target_fp = str(getattr(target, "fingerprint", ""))
        if not (
            getattr(source, "endpoint_kind", "") == "model_instance"
            and source_fp in selected_fingerprints
            or getattr(target, "endpoint_kind", "") == "model_instance"
            and target_fp in selected_fingerprints
        ):
            continue
        relation_values.append(_selected_relation_mapping(relation))
        for endpoint in (source, target):
            endpoint_kind = str(getattr(endpoint, "endpoint_kind", ""))
            endpoint_id = str(getattr(endpoint, "endpoint_id", ""))
            endpoint_fingerprint = str(getattr(endpoint, "fingerprint", ""))
            key = (endpoint_kind, endpoint_id, endpoint_fingerprint)
            if endpoint_kind == "boundary_contract":
                selected_endpoint_keys.add(key)

    # The accepted boundary contract is also a typed owner-artifact reference
    # on the snapshot.  Some historical snapshots do not attach it to a
    # model relation, so retain it for a non-empty selected closure without
    # discovering any contract-looking file.
    if selected_instances:
        for endpoint in getattr(snapshot_value, "owner_artifact_refs", ()):
            if getattr(endpoint, "endpoint_kind", "") != "boundary_contract":
                continue
            selected_endpoint_keys.add(
                (
                    "boundary_contract",
                    str(getattr(endpoint, "endpoint_id", "")),
                    str(getattr(endpoint, "fingerprint", "")),
                )
            )

    # A boundary contract is an immutable authority object.  Resolve it only
    # through the typed endpoint fingerprint; never search a directory for a
    # contract-looking file.  When the typed authority state already loaded
    # this exact artifact, reuse its parsed object and avoid a duplicate read.
    accepted_contract = getattr(state, "accepted_boundary_contract", None)
    for endpoint_kind, endpoint_id, endpoint_fingerprint in sorted(selected_endpoint_keys):
        if endpoint_kind != "boundary_contract":
            continue
        try:
            contract_path = _artifact_path(
                root_path,
                MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY,
                endpoint_fingerprint,
            )
            relative = _selected_path_relative_to_root(
                root_path, _windows_io_path(contract_path)
            )
            selected_contract_paths.append(relative)
            selected_contract_refs.append(
                {
                    "endpoint_kind": endpoint_kind,
                    "endpoint_id": endpoint_id,
                    "fingerprint": endpoint_fingerprint,
                    "path": relative,
                }
            )
            if accepted_contract is not None and str(
                getattr(accepted_contract, "fingerprint", "")
            ) == endpoint_fingerprint:
                continue
            payload = _selected_file_bytes(root_path, relative)
            read_counts[relative] = read_counts.get(relative, 0) + 1
            if _selected_artifact_fingerprint(
                payload,
                category=MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY,
            ) != endpoint_fingerprint:
                raise ModelAuthorityError(
                    "selected boundary contract fingerprint does not match endpoint"
                )
        except (ModelAuthorityError, OSError, ValueError) as exc:
            detail = {
                "code": "selected_contract_unavailable",
                "endpoint_id": endpoint_id,
                "fingerprint": endpoint_fingerprint,
                "message": str(exc),
            }
            findings.append(detail)
            stale_details.append(detail)

    _selected_source_status(
        root=root_path,
        paths=expected_sources,
        findings=findings,
        stale_details=stale_details,
        read_cache=read_cache,
        read_counts=read_counts,
    )

    # The saved map is still useful even when one selected source is stale.
    # Keep currentness as a separate claim and make execution explicit rather
    # than inferring it from a model/runner fingerprint.
    if stale_details:
        selected_currentness = SELECTED_SOURCE_STALE
        for detail in stale_details:
            path = detail.get("path") or detail.get("endpoint_id") or "selected"
            stale_obligations.append(
                f"{detail.get('code', 'selected_source_stale')}:{path}"
            )
    elif selected_instances:
        selected_currentness = SELECTED_SOURCE_CURRENT
    else:
        selected_currentness = SELECTED_SOURCE_NOT_SELECTED

    for gap in getattr(snapshot_value, "unresolved_gap_ids", ()):
        # Snapshot gaps are as-of obligations; they do not make a selected map
        # disappear and do not become an execution claim.
        stale_obligations.append(f"authority_gap:{gap}")

    authority_integrity = (
        MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS
        if tuple(getattr(snapshot_value, "unresolved_gap_ids", ()))
        else MODEL_AUTHORITY_STATUS_PASS
    )
    return SelectedModelClosureRead(
        authority_integrity=authority_integrity,
        selected_source_currentness=selected_currentness,
        execution_evidence_status=EXECUTION_EVIDENCE_NOT_RUN,
        snapshot_fingerprint=snapshot_fingerprint,
        subject_revision=subject_revision,
        authority_head_fingerprint=head_fingerprint,
        accepted_revision_set_fingerprint=revision_fingerprint,
        selected_model_ids=selected_model_ids_value,
        selected_models=selected_models,
        selected_model_paths=tuple(selected_model_paths),
        selected_runner_paths=tuple(selected_runner_paths),
        selected_input_paths=selected_input_paths,
        selected_intent_paths=tuple(dict.fromkeys(selected_intent_paths)),
        selected_contract_paths=tuple(dict.fromkeys(selected_contract_paths)),
        selected_intent_refs=tuple(selected_intent_refs),
        selected_contract_refs=tuple(selected_contract_refs),
        relations=tuple(relation_values),
        as_of=as_of,
        stale_obligations=tuple(dict.fromkeys(stale_obligations)),
        stale_obligation_details=tuple(stale_details),
        findings=tuple(findings),
        read_paths=tuple(sorted(set(read_cache) | set(read_counts))),
        read_counts=tuple(sorted(read_counts.items())),
        producer_count=0,
        write_count=0,
    )


def read_selected_model_projection(
    root: str | Path,
    *,
    head: ModelAuthorityHead,
    projection: Mapping[str, Any],
    selected_model_ids: Iterable[str],
) -> SelectedModelClosureRead:
    """Read selected models from the bound projection without ancestry loads.

    This is the production reader used by the compact public ``read`` route.
    The older snapshot-backed reader above remains an internal fixture and
    model-authority helper; it is never used by the public route once the
    projection is required.
    """

    root_path = Path(root).resolve()
    findings: list[dict[str, Any]] = []
    stale_details: list[dict[str, Any]] = []
    stale_obligations: list[str] = []
    read_cache: dict[str, str] = {}
    read_counts: dict[str, int] = {}
    requested = tuple(str(item).strip() for item in selected_model_ids)
    try:
        shards = _load_selected_read_shards(root_path, projection, requested)
    except (ModelAuthorityError, OSError, ValueError) as exc:
        return SelectedModelClosureRead(
            authority_integrity=MODEL_AUTHORITY_STATUS_BLOCKED,
            selected_source_currentness=SELECTED_SOURCE_UNAVAILABLE,
            execution_evidence_status=EXECUTION_EVIDENCE_NOT_RUN,
            authority_head_fingerprint=head.fingerprint,
            findings=(
                {
                    "code": "read_projection_invalid",
                    "severity": "blocked",
                    "message": str(exc),
                },
            ),
            stale_obligations=("read_projection_invalid",),
            producer_count=0,
            write_count=0,
        )

    index = projection["index"]
    selected_models: list[Mapping[str, Any]] = []
    selected_model_paths: list[str] = []
    selected_runner_paths: list[str] = []
    selected_input_paths: set[str] = set()
    selected_intent_refs: list[Mapping[str, Any]] = []
    selected_intent_paths: list[str] = []
    selected_contract_refs: list[Mapping[str, Any]] = []
    selected_contract_paths: list[str] = []
    relation_values: list[Mapping[str, Any]] = []
    relation_ids: set[str] = set()
    boundary_keys: set[tuple[str, str, str]] = set()
    expected_sources: dict[str, str] = {}
    for shard in shards:
        model = shard.get("model")
        if not isinstance(model, Mapping):
            findings.append(
                {
                    "code": "read_projection_model_invalid",
                    "severity": "blocked",
                    "message": f"model shard has no object body: {shard.get('logical_model_id')}",
                }
            )
            continue
        selected_models.append(dict(model))
        model_path = str(model.get("model_path", "")).replace("\\", "/")
        runner_path = str(model.get("runner_path", "")).replace("\\", "/")
        selected_model_paths.append(model_path)
        selected_runner_paths.append(runner_path)
        for input_ref in model.get("inputs", ()):
            if isinstance(input_ref, Mapping):
                path = str(input_ref.get("path", "")).replace("\\", "/")
                if path:
                    selected_input_paths.add(path)
        for item in shard.get("intent_refs", ()):
            if isinstance(item, Mapping):
                ref = dict(item)
                selected_intent_refs.append(ref)
                if str(ref.get("authority_kind", "")) == "project_file":
                    path = str(ref.get("source_ref", "")).replace("\\", "/")
                    if path:
                        selected_intent_paths.append(path)
        for path, expected in (
            shard.get("source_paths", {})
            if isinstance(shard.get("source_paths"), Mapping)
            else {}
        ).items():
            path_value = str(path).replace("\\", "/")
            expected_value = str(expected)
            if path_value in expected_sources and expected_sources[path_value] != expected_value:
                findings.append(
                    {
                        "code": "shared_source_fingerprint_conflict",
                        "path": path_value,
                        "severity": "blocked",
                        "message": "selected projection declares conflicting source fingerprints",
                    }
                )
            else:
                expected_sources[path_value] = expected_value
        for relation in shard.get("relations", ()):
            if not isinstance(relation, Mapping):
                continue
            relation_id = str(relation.get("relation_id", ""))
            if relation_id in relation_ids:
                continue
            relation_ids.add(relation_id)
            relation_values.append(dict(relation))
            for endpoint_name in ("source", "target"):
                endpoint = relation.get(endpoint_name)
                if isinstance(endpoint, Mapping) and endpoint.get("endpoint_kind") != "model_instance":
                    boundary_keys.add(
                        (
                            str(endpoint.get("endpoint_kind", "")),
                            str(endpoint.get("endpoint_id", "")),
                            str(endpoint.get("fingerprint", "")),
                        )
                    )
        for endpoint in shard.get("boundary_nodes", ()):
            if not isinstance(endpoint, Mapping):
                continue
            key = (
                str(endpoint.get("endpoint_kind", "")),
                str(endpoint.get("endpoint_id", "")),
                str(endpoint.get("fingerprint", "")),
            )
            if key not in boundary_keys:
                boundary_keys.add(key)
            selected_contract_refs.append(dict(endpoint))
            path = str(endpoint.get("path", "")).replace("\\", "/")
            if path:
                selected_contract_paths.append(path)

    _selected_source_status(
        root=root_path,
        paths=expected_sources,
        findings=findings,
        stale_details=stale_details,
        read_cache=read_cache,
        read_counts=read_counts,
    )
    if stale_details:
        selected_currentness = SELECTED_SOURCE_STALE
        for detail in stale_details:
            path = detail.get("path") or detail.get("endpoint_id") or "selected"
            stale_obligations.append(
                f"{detail.get('code', 'selected_source_stale')}:{path}"
            )
    else:
        selected_currentness = SELECTED_SOURCE_CURRENT
    stale_obligations.extend(
        f"authority_gap:{index.get('unresolved_gap_count')}"
        for _ in range(1 if int(index.get("unresolved_gap_count", 0) or 0) else 0)
    )
    authority_integrity = (
        MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS
        if int(index.get("unresolved_gap_count", 0) or 0)
        else MODEL_AUTHORITY_STATUS_PASS
    )
    as_of = {
        "subject_revision": str(index.get("subject_revision", "")),
        "snapshot_fingerprint": str(index.get("candidate_snapshot_fingerprint", "")),
        "authority_head_fingerprint": head.fingerprint,
        "accepted_revision_set_fingerprint": str(index.get("revision_set_fingerprint", "")),
        "read_projection_index_fingerprint": str(projection.get("index_fingerprint", "")),
    }
    return SelectedModelClosureRead(
        authority_integrity=(
            MODEL_AUTHORITY_STATUS_BLOCKED if any(
                item.get("severity") == "blocked" for item in findings
            ) else authority_integrity
        ),
        selected_source_currentness=selected_currentness,
        execution_evidence_status=EXECUTION_EVIDENCE_NOT_RUN,
        snapshot_fingerprint=str(index.get("candidate_snapshot_fingerprint", "")),
        subject_revision=str(index.get("subject_revision", "")),
        authority_head_fingerprint=head.fingerprint,
        accepted_revision_set_fingerprint=str(index.get("revision_set_fingerprint", "")),
        selected_model_ids=tuple(requested),
        selected_models=tuple(selected_models),
        selected_model_paths=tuple(selected_model_paths),
        selected_runner_paths=tuple(selected_runner_paths),
        selected_input_paths=tuple(sorted(selected_input_paths)),
        selected_intent_paths=tuple(dict.fromkeys(selected_intent_paths)),
        selected_contract_paths=tuple(dict.fromkeys(selected_contract_paths)),
        selected_intent_refs=tuple(selected_intent_refs),
        selected_contract_refs=tuple(selected_contract_refs),
        relations=tuple(relation_values),
        as_of=as_of,
        stale_obligations=tuple(dict.fromkeys(stale_obligations)),
        stale_obligation_details=tuple(stale_details),
        findings=tuple(findings),
        read_paths=tuple(sorted(set(read_cache) | set(read_counts))),
        read_counts=tuple(sorted(read_counts.items())),
        producer_count=0,
        write_count=0,
    )


def _payload_without_fingerprint(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        key: value for key, value in payload.items() if key != "fingerprint"
    }


def _load_snapshot_by_fingerprint(
    root: Path,
    fingerprint: str,
) -> ModelSystemSnapshot:
    path = _artifact_path(root, "snapshots", fingerprint)
    try:
        snapshot = load_model_system_snapshot(_windows_io_path(path))
    except (OSError, ModelAuthorityError, ValueError) as exc:
        raise ModelAuthorityError(
            f"authority ancestry snapshot is invalid: {exc}"
        ) from exc
    if snapshot.fingerprint != fingerprint:
        raise ModelAuthorityError(
            "authority ancestry snapshot does not match its content address"
        )
    _assert_snapshot_current_paths(snapshot)
    return snapshot


def _load_accepted_boundary_contract(
    root: Path,
    snapshot: ModelSystemSnapshot,
    accepted_revision_fingerprint: str,
) -> AcceptedBoundaryContract | None:
    """Resolve the A05 denominator from the current snapshot only.

    A missing endpoint is deliberately represented as ``None`` so old heads
    remain loadable and broad partitioned claims can fail closed at the mesh
    boundary.  A declared but malformed/foreign endpoint is a current
    authority error: silently treating it as absent would hide corruption.
    """

    refs = tuple(
        ref
        for ref in snapshot.owner_artifact_refs
        if ref.endpoint_kind == "boundary_contract"
    )
    if len(refs) > 1:
        raise ModelAuthorityError(
            "current model authority may declare at most one boundary contract"
        )
    if not refs:
        return None
    ref = refs[0]
    if ref.owner_route != BOUNDARY_CONTRACT_OWNER_ROUTE:
        raise ModelAuthorityError(
            "current boundary contract endpoint has a foreign owner route"
        )
    path = _artifact_path(
        root,
        MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY,
        ref.fingerprint,
    )
    try:
        contract = load_accepted_boundary_contract(_windows_io_path(path))
    except (OSError, ModelAuthorityError, ValueError) as exc:
        raise ModelAuthorityError(
            f"current boundary contract is invalid: {exc}"
        ) from exc
    if contract.fingerprint != ref.fingerprint:
        raise ModelAuthorityError(
            "current boundary contract does not match its endpoint fingerprint"
        )
    if contract.contract_id != ref.endpoint_id:
        raise ModelAuthorityError(
            "current boundary contract endpoint id does not match the artifact"
        )
    if contract.snapshot_fingerprint and contract.snapshot_fingerprint != snapshot.fingerprint:
        raise ModelAuthorityError(
            "current boundary contract names a different model-system snapshot"
        )
    if (
        contract.accepted_revision_set_fingerprint
        and contract.accepted_revision_set_fingerprint != accepted_revision_fingerprint
    ):
        raise ModelAuthorityError(
            "current boundary contract names a different accepted revision set"
        )
    if (
        contract.boundary_source_id != snapshot.coverage.boundary_id
        or contract.boundary_source_fingerprint != snapshot.coverage.fingerprint
    ):
        raise ModelAuthorityError(
            "current boundary contract names a different coverage boundary"
        )
    relation_ids = {relation.relation_id for relation in snapshot.relations}
    declared_relation_ids = {
        relation_id
        for values in contract.group_relation_ids.values()
        for relation_id in values
    }
    if not declared_relation_ids <= relation_ids:
        raise ModelAuthorityError(
            "current boundary contract references an unmaterialized authority relation"
        )
    try:
        validate_accepted_boundary_contract_for_snapshot(
            contract,
            snapshot,
            require_endpoint=True,
        )
    except ModelAuthorityError as exc:
        raise ModelAuthorityError(
            f"current boundary contract structural validation failed: {exc}"
        ) from exc
    return contract


def _load_activation_receipt(
    root: Path,
    fingerprint: str,
) -> ModelActivationReceipt:
    payload = _read_content_addressed_payload(
        root,
        "activations",
        fingerprint,
    )
    try:
        receipt = ModelActivationReceipt.from_dict(
            _payload_without_fingerprint(payload)
        )
    except ModelAuthorityError as exc:
        raise ModelAuthorityError(
            f"current activation receipt is invalid: {exc}"
        ) from exc
    if receipt.fingerprint != fingerprint:
        raise ModelAuthorityError(
            "current activation receipt fingerprint is stale"
        )
    return receipt


def _load_rollback_contract(
    root: Path,
    fingerprint: str,
) -> ModelRollbackContract:
    payload = _read_content_addressed_payload(
        root,
        "rollback-contracts",
        fingerprint,
    )
    try:
        contract = ModelRollbackContract.from_dict(
            _payload_without_fingerprint(payload)
        )
    except ModelAuthorityError as exc:
        raise ModelAuthorityError(
            f"current rollback contract is invalid: {exc}"
        ) from exc
    if contract.fingerprint != fingerprint:
        raise ModelAuthorityError(
            "current rollback contract fingerprint is stale"
        )
    return contract


def _load_rollback_receipt(
    root: Path,
    fingerprint: str,
) -> ModelRollbackReceipt:
    payload = _read_content_addressed_payload(
        root,
        "rollbacks",
        fingerprint,
    )
    try:
        receipt = ModelRollbackReceipt.from_dict(
            _payload_without_fingerprint(payload)
        )
    except ModelAuthorityError as exc:
        raise ModelAuthorityError(
            f"current rollback receipt is invalid: {exc}"
        ) from exc
    if receipt.fingerprint != fingerprint:
        raise ModelAuthorityError(
            "current rollback receipt fingerprint is stale"
        )
    return receipt


def _bootstrap_head_from_path(
    path: Path,
    *,
    expected_system_id: str,
) -> ModelAuthorityHead:
    fingerprint = f"sha256:{path.stem}"
    payload = _read_content_addressed_payload(
        # ``path`` is rooted at ``<project>/.flowguard/models/authority/bootstraps``;
        # the project root is four parents above the content-addressed file.
        # Passing ``.flowguard`` here makes every generation-one predecessor
        # invisible after the first activation and falsely blocks all lineage
        # replay.  Resolve the same project root used by every other authority
        # artifact loader.
        path.parents[4],
        "bootstraps",
        fingerprint,
    )
    required = {
        "schema",
        "system_id",
        "snapshot_fingerprint",
        "subject_revision",
        "evidence_fingerprint",
        "claim_boundary",
        "fingerprint",
    }
    if set(payload) != required or any(
        not isinstance(payload[name], str) for name in required
    ):
        raise ModelAuthorityError(
            "generation-one bootstrap has an invalid wire shape"
        )
    if (
        payload["schema"] != INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA
        or payload["system_id"] != expected_system_id
    ):
        raise ModelAuthorityError(
            "generation-one bootstrap belongs to another authority"
        )
    return ModelAuthorityHead(
        system_id=payload["system_id"],
        snapshot_fingerprint=payload["snapshot_fingerprint"],
        subject_revision=payload["subject_revision"],
        generation=1,
        accepted_revision_set_fingerprint=fingerprint,
        previous_snapshot_fingerprint="",
        activation_receipt_fingerprint=fingerprint,
    )


def _candidate_heads_for_generation(
    root: Path,
    *,
    system_id: str,
    generation: int,
) -> tuple[ModelAuthorityHead, ...]:
    mesh_root = root / ".flowguard" / "models" / "authority"
    activation_dir = mesh_root / "activations"
    activation_files = tuple(
        sorted(
            (
                path.name,
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in activation_dir.glob("*.json")
        )
    )
    candidates = [
        candidate
        for candidate in _indexed_activation_heads(
            str(root),
            system_id,
            activation_files,
        )
        if candidate.generation == generation
    ]
    for path in (mesh_root / "rollbacks").glob("*.json"):
        fingerprint = f"sha256:{path.stem}"
        try:
            receipt = _load_rollback_receipt(root, fingerprint)
            contract = _load_rollback_contract(
                root,
                receipt.contract_fingerprint,
            )
            snapshot = _load_snapshot_by_fingerprint(
                root,
                contract.to_snapshot_fingerprint,
            )
            if snapshot.system_id != system_id:
                continue
            candidates.append(
                ModelAuthorityHead(
                    system_id=snapshot.system_id,
                    snapshot_fingerprint=snapshot.fingerprint,
                    subject_revision=snapshot.subject_revision,
                    generation=generation,
                    accepted_revision_set_fingerprint=(
                        receipt.reverse_revision_set_fingerprint
                    ),
                    previous_snapshot_fingerprint=(
                        contract.from_snapshot_fingerprint
                    ),
                    activation_receipt_fingerprint=fingerprint,
                )
            )
        except ModelAuthorityError:
            continue
    return tuple(candidates)


@lru_cache(maxsize=16)
def _indexed_activation_heads(
    root_text: str,
    system_id: str,
    activation_files: tuple[tuple[str, int, int], ...],
) -> tuple[ModelAuthorityHead, ...]:
    """Parse each immutable activation receipt once per directory snapshot.

    Current-authority ancestry checks may ask for several predecessor
    generations during one audit, and the audit path itself can validate the
    same transition twice.  The old implementation re-read every historical
    activation file for each generation, making a long-lived authority chain
    quadratic in receipt count.  Content-addressed activation files are
    write-once; the file-name/size/mtime signature invalidates this bounded
    cache whenever the store changes, so no stale receipt can become an
    authority input merely through caching.
    """

    root = Path(root_text)
    candidates: list[ModelAuthorityHead] = []
    for name, _size, _mtime_ns in activation_files:
        path = (
            root
            / ".flowguard"
            / "models"
            / "authority"
            / "activations"
            / name
        )
        fingerprint = f"sha256:{path.stem}"
        try:
            receipt = _load_activation_receipt(root, fingerprint)
            if receipt.system_id != system_id:
                continue
            candidates.append(
                ModelAuthorityHead(
                    system_id=receipt.system_id,
                    snapshot_fingerprint=receipt.candidate_snapshot_fingerprint,
                    subject_revision=receipt.subject_revision,
                    generation=receipt.next_generation,
                    accepted_revision_set_fingerprint=receipt.revision_set_fingerprint,
                    previous_snapshot_fingerprint=receipt.previous_snapshot_fingerprint,
                    activation_receipt_fingerprint=fingerprint,
                )
            )
        except ModelAuthorityError:
            continue
    return tuple(candidates)


def _find_exact_predecessor_head(
    root: Path,
    *,
    system_id: str,
    generation: int,
    expected_fingerprint: str,
) -> ModelAuthorityHead:
    if generation < 1:
        raise ModelAuthorityError(
            "current transition has no valid predecessor generation"
        )
    if generation == 1:
        candidates: list[ModelAuthorityHead] = []
        for path in (
            root / ".flowguard" / "models" / "authority" / "bootstraps"
        ).glob("*.json"):
            try:
                candidate = _bootstrap_head_from_path(
                    path,
                    expected_system_id=system_id,
                )
            except ModelAuthorityError:
                continue
            if candidate.fingerprint == expected_fingerprint:
                candidates.append(candidate)
    else:
        candidates = [
            candidate
            for candidate in _candidate_heads_for_generation(
                root,
                system_id=system_id,
                generation=generation,
            )
            if candidate.fingerprint == expected_fingerprint
        ]
    if len(candidates) != 1:
        raise ModelAuthorityError(
            "current transition predecessor head is missing or ambiguous at "
            f"generation {generation}"
        )
    return candidates[0]


def _load_accepted_revision_set(
    root: Path,
    head: ModelAuthorityHead,
    snapshot: ModelSystemSnapshot,
) -> ModelRevisionSet | None:
    """Load the exact accepted revision behind a non-bootstrap authority head.

    Generation one is established by an immutable bootstrap receipt.  Every
    later head is established by a content-addressed accepted revision set and
    must remain readable under the current schema and invariants.  In
    particular, an old revision that copied one parent receipt into several
    native-owner leaves is not silently grandfathered into current authority.
    """

    if head.generation == 1:
        return None
    fingerprint = head.accepted_revision_set_fingerprint
    digest = fingerprint.split(":", 1)[1]
    path = (
        root
        / ".flowguard"
        / "models"
        / "authority"
        / "revisions"
        / f"{digest}.json"
    )
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
        revision_set = ModelRevisionSet.from_dict(payload)
    except (OSError, json.JSONDecodeError, ModelAuthorityError, ValueError) as exc:
        raise ModelAuthorityError(
            f"accepted revision-set artifact is invalid: {exc}"
        ) from exc
    if revision_set.fingerprint != fingerprint:
        raise ModelAuthorityError(
            "accepted revision-set artifact does not match the authority head"
        )
    if revision_set.status != REVISION_ACCEPTED:
        raise ModelAuthorityError(
            "authority head does not reference an accepted revision set"
        )
    if revision_set.candidate_snapshot_fingerprint != snapshot.fingerprint:
        raise ModelAuthorityError(
            "accepted revision-set candidate does not match the observed snapshot"
        )
    _assert_revision_current_paths(revision_set)
    validate_current_effective_intent_view(
        snapshot,
        revision_set.current_effective_intent_view,
    )
    return revision_set


def _accepted_revision_schema(
    root: Path,
    head: ModelAuthorityHead,
) -> str:
    """Return only the declared schema for audit observability.

    This does not validate or authorize the artifact.  The authoritative loader
    still performs strict current-schema and content-addressed validation.
    """

    if head.generation == 1:
        return INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA
    digest = head.accepted_revision_set_fingerprint.split(":", 1)[1]
    path = (
        root
        / ".flowguard"
        / "models"
        / "authority"
        / "revisions"
        / f"{digest}.json"
    )
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError):
        return ""
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("schema") or "").strip()


def _validate_current_typed_transition(
    root: Path,
    head: ModelAuthorityHead,
    snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
) -> CurrentModelAuthorityState:
    accepted_boundary_contract = _load_accepted_boundary_contract(
        root,
        snapshot,
        revision_set.fingerprint,
    )
    fingerprint = head.activation_receipt_fingerprint
    activation_path = _artifact_path(root, "activations", fingerprint)
    rollback_path = _artifact_path(root, "rollbacks", fingerprint)
    present = tuple(
        kind
        for kind, path in (
            ("activation", activation_path),
            ("rollback", rollback_path),
        )
        if path.is_file()
    )
    if len(present) != 1:
        raise ModelAuthorityError(
            "current authority head must have exactly one typed transition receipt"
        )

    if present[0] == "activation":
        receipt = _load_activation_receipt(root, fingerprint)
        predecessor = _find_exact_predecessor_head(
            root,
            system_id=head.system_id,
            generation=head.generation - 1,
            expected_fingerprint=receipt.expected_head_fingerprint,
        )
        base_snapshot = _load_snapshot_by_fingerprint(
            root,
            receipt.previous_snapshot_fingerprint,
        )
        _validate_revision_intent_activation(
            root,
            predecessor,
            base_snapshot,
            snapshot,
            revision_set,
            reverify_sources=False,
        )
        expected_head, expected_receipt = validate_activation_plan(
            predecessor,
            base_snapshot,
            snapshot,
            revision_set,
            live_candidate_snapshot=snapshot,
            receipt_id=receipt.receipt_id,
        )
        if expected_receipt != receipt or expected_head != head:
            raise ModelAuthorityError(
                "current activation receipt does not produce the exact authority head"
            )
        projection = _load_bound_read_projection(root, head)
        transition_evidence = projection["index"].get("transition_evidence")
        if transition_evidence is not None:
            if not isinstance(transition_evidence, Mapping) or set(transition_evidence) != {
                "kind",
                "rollback_receipt_fingerprint",
                "rollback_contract_fingerprint",
            }:
                raise ModelAuthorityError(
                    "current activation projection transition evidence is not exact"
                )
            if transition_evidence["kind"] != "rollback":
                raise ModelAuthorityError(
                    "current activation projection has an unsupported transition kind"
                )
            rollback_receipt_fingerprint = str(
                transition_evidence["rollback_receipt_fingerprint"]
            )
            rollback_contract_fingerprint = str(
                transition_evidence["rollback_contract_fingerprint"]
            )
            rollback_receipt = _load_rollback_receipt(
                root, rollback_receipt_fingerprint
            )
            rollback_contract = _load_rollback_contract(
                root, rollback_contract_fingerprint
            )
            if (
                rollback_receipt.contract_fingerprint
                != rollback_contract.fingerprint
                or rollback_receipt.reverse_revision_set_fingerprint
                != revision_set.fingerprint
                or rollback_receipt_fingerprint != rollback_receipt.fingerprint
                or rollback_contract_fingerprint != rollback_contract.fingerprint
            ):
                raise ModelAuthorityError(
                    "current rollback projection transition evidence is stale"
                )
            if rollback_contract.expected_head_fingerprint != predecessor.fingerprint:
                raise ModelAuthorityError(
                    "current rollback contract predecessor does not match activation"
                )
            rollback_base_snapshot = _load_snapshot_by_fingerprint(
                root, rollback_contract.from_snapshot_fingerprint
            )
            _validate_revision_intent_activation(
                root,
                predecessor,
                rollback_base_snapshot,
                snapshot,
                revision_set,
                reverify_sources=False,
            )
            expected_rollback = validate_operational_rollback(
                predecessor,
                rollback_contract,
                revision_set,
                completed_evidence_fingerprints=(
                    rollback_receipt.completed_evidence_fingerprints
                ),
                requested_result=rollback_receipt.result,
                receipt_id=rollback_receipt.receipt_id,
                reason=rollback_receipt.reason,
            )
            if expected_rollback != rollback_receipt:
                raise ModelAuthorityError(
                    "current rollback receipt is not exactly reproducible"
                )
            return CurrentModelAuthorityState(
                head=head,
                snapshot=snapshot,
                accepted_revision=revision_set,
                transition_kind="rollback",
                accepted_boundary_contract=accepted_boundary_contract,
                predecessor_head=predecessor,
                activation_receipt=receipt,
                rollback_contract=rollback_contract,
                rollback_receipt=rollback_receipt,
                verified_source_identities=(
                    revision_set.current_effective_intent_view.verified_source_identities
                ),
            )
        return CurrentModelAuthorityState(
            head=head,
            snapshot=snapshot,
            accepted_revision=revision_set,
            transition_kind="activation",
            accepted_boundary_contract=accepted_boundary_contract,
            predecessor_head=predecessor,
            activation_receipt=receipt,
            verified_source_identities=(
                revision_set.current_effective_intent_view.verified_source_identities
            ),
        )

    raise ModelAuthorityError(
        "current rollback transition is not bound to an accepted read projection"
    )


def load_current_model_authority_state(
    root: str | Path,
    *,
    head: ModelAuthorityHead | None = None,
    snapshot: ModelSystemSnapshot | None = None,
    allow_legacy_bootstrap_source: bool = False,
    reverify_current_sources: bool = False,
) -> CurrentModelAuthorityState:
    """Resolve one authority head through its exact immutable producer.

    Generation-one and v4 heads are accepted only as explicitly requested
    migration sources.  A normal current authority requires a v5 accepted
    revision, one typed activation or rollback receipt, its exact predecessor,
    and current source identities.
    """

    root_path = Path(root).resolve()
    if (head is None) != (snapshot is None):
        raise ModelAuthorityError(
            "current authority loading requires both head and snapshot or neither"
        )
    if head is None or snapshot is None:
        head, snapshot = load_observed_model_system(root_path)
    _assert_snapshot_current_paths(snapshot)

    schema = _accepted_revision_schema(root_path, head)
    if head.generation == 1 or schema == LEGACY_CURRENT_REVISION_SCHEMA:
        _bootstrap_source_audit(root_path, head, snapshot)
        if not allow_legacy_bootstrap_source:
            raise ModelAuthorityError(
                "current authority requires explicit intent bootstrap migration"
            )
        return CurrentModelAuthorityState(
            head=head,
            snapshot=snapshot,
            accepted_revision=None,
            transition_kind="legacy_bootstrap_source",
        )

    revision_set = _load_accepted_revision_set(
        root_path,
        head,
        snapshot,
    )
    if revision_set is None:
        raise ModelAuthorityError(
            "current authority unexpectedly lacks an accepted revision"
        )
    verified_sources = (
        revision_set.current_effective_intent_view.verified_source_identities
    )
    if reverify_current_sources:
        try:
            verified_sources = verify_model_intent_sources(
                root_path,
                revision_set.current_effective_intent_view.active_contributions,
            )
        except ModelAuthorityError as exc:
            raise CurrentIntentSourceAuthorityError(
                str(exc),
                finding_code=_current_intent_source_finding_code(str(exc)),
            ) from exc
        if (
            verified_sources
            != revision_set.current_effective_intent_view.verified_source_identities
        ):
            raise CurrentIntentSourceAuthorityError(
                "current effective intent source identities are stale",
                finding_code="current_intent_source_stale",
            )
    state = _validate_current_typed_transition(
        root_path,
        head,
        snapshot,
        revision_set,
    )
    return replace(
        state,
        verified_source_identities=verified_sources,
        current_sources_reverified=reverify_current_sources,
    )


def load_current_accepted_revision_set(
    root: str | Path,
    *,
    head: ModelAuthorityHead | None = None,
    snapshot: ModelSystemSnapshot | None = None,
) -> ModelRevisionSet | None:
    """Load the sole current v5 revision; legacy current schemas fail visibly."""

    root_path = Path(root).resolve()
    if (head is None) != (snapshot is None):
        raise ModelAuthorityError(
            "current revision loading requires both head and snapshot or neither"
        )
    state = load_current_model_authority_state(
        root_path,
        head=head,
        snapshot=snapshot,
    )
    return state.accepted_revision


def load_observed_model_system(
    root: str | Path,
) -> tuple[ModelAuthorityHead, ModelSystemSnapshot]:
    root_path = Path(root).resolve()
    text = read_manifest_text(root_path / ".flowguard" / "project.toml")
    return _load_observed_from_manifest_text(root_path, text)


def load_observed_model_head(root: str | Path) -> ModelAuthorityHead:
    """Read only the current manifest head for the bounded public reader."""

    root_path = Path(root).resolve()
    text = read_manifest_text(root_path / ".flowguard" / "project.toml")
    return _head_from_section(_section(text))


def _load_observed_from_manifest_text(
    root_path: Path,
    text: str,
) -> tuple[ModelAuthorityHead, ModelSystemSnapshot]:
    section = _section(text)
    # Reject a direct staging/workspace pointer before any snapshot or head
    # validation can accidentally treat it as current authority.
    _assert_current_authority_path(
        section.get("observed_snapshot_path"),
        "observed_snapshot_path",
    )
    head = _head_from_section(section)
    relative = _relative_path(
        section["observed_snapshot_path"],
        "observed_snapshot_path",
    )
    if classify_runtime_artifact(relative) is not None:
        raise ModelAuthorityError(
            "observed snapshot pointer cannot target a working or candidate path"
        )
    path = (root_path / relative).resolve()
    if root_path not in path.parents:
        raise ModelAuthorityError("observed snapshot escapes project root")
    snapshot = load_model_system_snapshot(path)
    if snapshot.fingerprint != head.snapshot_fingerprint:
        raise ModelAuthorityError("observed snapshot fingerprint mismatch")
    if snapshot.system_id != head.system_id:
        raise ModelAuthorityError("observed snapshot system id mismatch")
    if snapshot.subject_revision != head.subject_revision:
        raise ModelAuthorityError("observed snapshot subject revision mismatch")
    if snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION:
        raise ModelAuthorityError("authority head does not reference observed implementation")
    if snapshot.lifecycle != LIFECYCLE_ACTIVE:
        raise ModelAuthorityError("authority head snapshot is not active")
    _assert_snapshot_current_paths(snapshot)
    if section["coverage_status"] != snapshot.coverage_status:
        raise ModelAuthorityError("manifest coverage status is stale")
    return head, snapshot


def audit_model_authority(
    root: str | Path,
) -> ModelAuthorityAuditReport:
    root_path = Path(root).resolve()
    model_inventory = None
    try:
        head, snapshot = load_observed_model_system(root_path)
    except (ModelAuthorityError, ProjectManifestError, ValueError) as exc:
        inventory_fields: dict[str, tuple[str, ...]] = {}
        finding_code = "model_authority_invalid"
        if model_inventory is not None:
            inventory_fields = {
                "declared_model_ids": model_inventory.declared_ids,
                "materialized_model_ids": model_inventory.materialized_ids,
                "required_model_ids": model_inventory.required_ids,
                "covered_model_ids": model_inventory.covered_ids,
                "missing_model_ids": model_inventory.missing_ids,
            }
            if model_inventory.missing_ids:
                finding_code = "live_model_manifest_incomplete"
        return ModelAuthorityAuditReport(
            root=str(root_path),
            status=MODEL_AUTHORITY_STATUS_BLOCKED,
            **inventory_fields,
            findings=(
                ModelAuthorityFinding(
                    "blocked",
                    finding_code,
                    str(exc),
                ),
            ),
        )

    authority_findings: list[ModelAuthorityFinding] = []
    accepted_revision_schema = _accepted_revision_schema(root_path, head)
    current_effective_intent_view_fingerprint = ""
    active_intent_contribution_count = 0
    model_owner_denominator_count = 0
    owner_binding_count = 0
    intent_mode = "blocked"
    accepted_revision: ModelRevisionSet | None = None
    accepted_boundary_contract: AcceptedBoundaryContract | None = None
    is_legacy_source = (
        head.generation == 1
        or accepted_revision_schema == LEGACY_CURRENT_REVISION_SCHEMA
    )
    if not is_legacy_source:
        try:
            accepted_revision = _load_accepted_revision_set(
                root_path,
                head,
                snapshot,
            )
        except ModelAuthorityError as exc:
            authority_findings.append(
                ModelAuthorityFinding(
                    "blocked",
                    "accepted_revision_invalid",
                    str(exc),
                )
            )
    if is_legacy_source or accepted_revision is not None:
        try:
            current_state = load_current_model_authority_state(
                root_path,
                head=head,
                snapshot=snapshot,
                allow_legacy_bootstrap_source=True,
                reverify_current_sources=True,
            )
        except CurrentIntentSourceAuthorityError as exc:
            authority_findings.append(
                ModelAuthorityFinding(
                    "blocked",
                    exc.finding_code,
                    str(exc),
                )
            )
        except ModelAuthorityError as exc:
            finding_code = "current_authority_transition_invalid"
            if is_legacy_source:
                finding_code = "legacy_authority_ancestry_invalid"
            authority_findings.append(
                ModelAuthorityFinding(
                    "blocked",
                    finding_code,
                    str(exc),
                )
            )
        else:
            accepted_revision = current_state.accepted_revision
            accepted_boundary_contract = current_state.accepted_boundary_contract
            if accepted_revision is None:
                intent_mode = "bootstrap_required"
                authority_findings.append(
                    ModelAuthorityFinding(
                        "blocked",
                        "current_effective_intent_bootstrap_required",
                        "The audited legacy authority has no cumulative current "
                        "effective intent view; an explicit intent bootstrap is "
                        "required before the model authority can pass.",
                    )
                )
    if accepted_revision is not None:
        effective_view = accepted_revision.current_effective_intent_view
        current_effective_intent_view_fingerprint = effective_view.fingerprint
        active_intent_contribution_count = len(
            effective_view.active_contributions
        )
        model_owner_denominator_count = len(effective_view.model_owner_ids)
        owner_binding_count = len(effective_view.owner_bindings)
        # A v5 view may preserve its one-time bootstrap receipt as lineage, but
        # an accepted current authority can only be refined from here.
        intent_mode = "refine"

    intent_audit_fields: dict[str, Any] = {
        "accepted_revision_schema": accepted_revision_schema,
        "accepted_revision_fingerprint": (
            head.accepted_revision_set_fingerprint
        ),
        "current_effective_intent_view_fingerprint": (
            current_effective_intent_view_fingerprint
        ),
        "active_intent_contribution_count": active_intent_contribution_count,
        "model_owner_denominator_count": model_owner_denominator_count,
        "owner_binding_count": owner_binding_count,
        "intent_mode": intent_mode,
    }

    try:
        from .model_regressions import (
            ModelRegressionManifest,
            audit_intent_source_input_bindings,
        )
        from .model_system_inventory import (
            build_manifest_model_system_snapshot,
            inspect_manifest_model_inventory,
        )

        model_inventory = inspect_manifest_model_inventory(root_path)
        manifest_path = (
            root_path / ".flowguard" / "models" / "regression-manifest.json"
        )
        if accepted_revision is not None and manifest_path.is_file():
            live_manifest = ModelRegressionManifest.load(root_path)
            binding_errors = audit_intent_source_input_bindings(
                root_path,
                live_manifest,
                accepted_revision.current_effective_intent_view.active_contributions,
                accepted_revision.current_effective_intent_view.verified_source_identities,
            )
            authority_findings.extend(
                ModelAuthorityFinding(
                    "blocked",
                    "current_intent_model_input_binding_invalid",
                    message,
                )
                for message in binding_errors
            )
        live_snapshot = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=snapshot.snapshot_id,
            system_id=snapshot.system_id,
            subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
            lifecycle=LIFECYCLE_ACTIVE,
            accepted_boundary_contract=accepted_boundary_contract,
        )
    except (ModelAuthorityError, ProjectManifestError, ValueError) as exc:
        inventory_fields: dict[str, tuple[str, ...]] = {}
        finding_code = "model_authority_invalid"
        if model_inventory is not None:
            inventory_fields = {
                "declared_model_ids": model_inventory.declared_ids,
                "materialized_model_ids": model_inventory.materialized_ids,
                "required_model_ids": model_inventory.required_ids,
                "covered_model_ids": model_inventory.covered_ids,
                "missing_model_ids": model_inventory.missing_ids,
            }
            if model_inventory.missing_ids:
                finding_code = "live_model_manifest_incomplete"
        message = str(exc)
        if (
            "model regression manifest is not authoritative" in message
            or "fingerprint is stale" in message
        ):
            finding_code = "live_model_manifest_stale"
        return ModelAuthorityAuditReport(
            root=str(root_path),
            status=MODEL_AUTHORITY_STATUS_BLOCKED,
            observed_source_revision=snapshot.subject_revision,
            observed_snapshot_fingerprint=snapshot.fingerprint,
            head_fingerprint=head.fingerprint,
            **intent_audit_fields,
            coverage_status=snapshot.coverage_status,
            unresolved_gap_ids=snapshot.unresolved_gap_ids,
            **inventory_fields,
            findings=tuple(authority_findings) + (
                ModelAuthorityFinding(
                    "blocked",
                    finding_code,
                    message,
                ),
            ),
        )
    stale_findings: list[ModelAuthorityFinding] = list(authority_findings)
    if model_inventory.missing_ids:
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "live_model_manifest_incomplete",
                "live non-excluded model manifest is not fully materialized: "
                f"declared={list(model_inventory.declared_ids)}, "
                f"materialized={list(model_inventory.materialized_ids)}, "
                f"missing={list(model_inventory.missing_ids)}",
            )
        )
    stored_models = {
        item.logical_model_id: item.fingerprint
        for item in snapshot.model_instances
    }
    live_models = {
        item.logical_model_id: item.fingerprint
        for item in live_snapshot.model_instances
    }
    if stored_models != live_models:
        added = sorted(set(live_models) - set(stored_models))
        removed = sorted(set(stored_models) - set(live_models))
        changed = sorted(
            model_id
            for model_id in set(stored_models) & set(live_models)
            if stored_models[model_id] != live_models[model_id]
        )
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_model_inventory_stale",
                "stored observed model inventory differs from the live manifest: "
                f"added={added}, removed={removed}, changed={changed}",
            )
        )
    if snapshot.identity_payload() != live_snapshot.identity_payload():
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_source_inventory_stale",
                "stored observed snapshot does not exactly equal the fresh "
                f"canonical live re-observation {live_snapshot.fingerprint}",
            )
        )
    stored_dimensions = {
        item.dimension_id: item.to_dict()
        for item in snapshot.coverage.dimensions
    }
    live_dimensions = {
        item.dimension_id: item.to_dict()
        for item in live_snapshot.coverage.dimensions
    }
    changed_dimensions = sorted(
        dimension_id
        for dimension_id in set(stored_dimensions) | set(live_dimensions)
        if stored_dimensions.get(dimension_id)
        != live_dimensions.get(dimension_id)
    )
    if changed_dimensions:
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_coverage_dimensions_stale",
                "stored observed coverage differs from live owners in dimensions: "
                + ", ".join(changed_dimensions),
            )
        )
    stored_owner_refs = {
        (item.endpoint_kind, item.endpoint_id): item.fingerprint
        for item in snapshot.owner_artifact_refs
    }
    live_owner_refs = {
        (item.endpoint_kind, item.endpoint_id): item.fingerprint
        for item in live_snapshot.owner_artifact_refs
    }
    if stored_owner_refs != live_owner_refs:
        stale_findings.append(
            ModelAuthorityFinding(
                "blocked",
                "observed_owner_artifacts_stale",
                "stored owner-artifact identity set differs from current canonical owners",
            )
        )
    if stale_findings:
        return ModelAuthorityAuditReport(
            root=str(root_path),
            status=MODEL_AUTHORITY_STATUS_BLOCKED,
            observed_source_revision=snapshot.subject_revision,
            observed_snapshot_fingerprint=snapshot.fingerprint,
            live_snapshot_fingerprint=live_snapshot.fingerprint,
            head_fingerprint=head.fingerprint,
            **intent_audit_fields,
            coverage_status=snapshot.coverage_status,
            declared_model_ids=model_inventory.declared_ids,
            materialized_model_ids=model_inventory.materialized_ids,
            required_model_ids=model_inventory.required_ids,
            covered_model_ids=model_inventory.covered_ids,
            missing_model_ids=model_inventory.missing_ids,
            unresolved_gap_ids=snapshot.unresolved_gap_ids,
            findings=tuple(stale_findings),
        )
    status = (
        MODEL_AUTHORITY_STATUS_PASS
        if snapshot.coverage_status == "complete_within_declared_boundary"
        else MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS
    )
    findings = ()
    if status == MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS:
        findings = (
            ModelAuthorityFinding(
                "warning",
                "bounded_coverage_incomplete",
                "Observed authority is current but finite coverage retains explicit gaps.",
            ),
        )
    return ModelAuthorityAuditReport(
        root=str(root_path),
        status=status,
        observed_source_revision=snapshot.subject_revision,
        observed_snapshot_fingerprint=snapshot.fingerprint,
        live_snapshot_fingerprint=live_snapshot.fingerprint,
        head_fingerprint=head.fingerprint,
        **intent_audit_fields,
        coverage_status=snapshot.coverage_status,
        declared_model_ids=model_inventory.declared_ids,
        materialized_model_ids=model_inventory.materialized_ids,
        required_model_ids=model_inventory.required_ids,
        covered_model_ids=model_inventory.covered_ids,
        missing_model_ids=model_inventory.missing_ids,
        unresolved_gap_ids=snapshot.unresolved_gap_ids,
        findings=findings,
    )


def bootstrap_model_authority(
    root: str | Path,
    snapshot: ModelSystemSnapshot,
    *,
    bootstrap_evidence_fingerprint: str,
) -> ModelAuthorityHead:
    if snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION:
        raise ModelAuthorityError("bootstrap snapshot must be observed implementation")
    if snapshot.lifecycle != LIFECYCLE_ACTIVE:
        raise ModelAuthorityError("bootstrap snapshot must be active")
    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        try:
            _section(current_text)
        except ModelAuthorityError:
            pass
        else:
            raise ModelAuthorityError(
                "project already has model authority; use a revision set"
            )
        # Do not create snapshots or bootstrap artifacts until the manifest
        # precondition has passed.  A rejected greenfield bootstrap must leave
        # no orphaned immutable objects behind.
        write_content_addressed_snapshot(root_path, snapshot)
        bootstrap_payload = {
            "schema": "flowguard.model_authority_bootstrap.v1",
            "system_id": snapshot.system_id,
            "snapshot_fingerprint": snapshot.fingerprint,
            "subject_revision": snapshot.subject_revision,
            "evidence_fingerprint": bootstrap_evidence_fingerprint,
            "claim_boundary": (
                "Bootstrap establishes the first observed authority pointer only; "
                "coverage gaps remain explicit and require later revision evidence."
            ),
        }
        bootstrap_fingerprint = canonical_fingerprint(bootstrap_payload)
        _write_immutable_json(
            root_path,
            "bootstraps",
            bootstrap_fingerprint,
            {**bootstrap_payload, "fingerprint": bootstrap_fingerprint},
        )
        head = ModelAuthorityHead(
            system_id=snapshot.system_id,
            snapshot_fingerprint=snapshot.fingerprint,
            subject_revision=snapshot.subject_revision,
            generation=1,
            accepted_revision_set_fingerprint=bootstrap_fingerprint,
            previous_snapshot_fingerprint="",
            activation_receipt_fingerprint=bootstrap_fingerprint,
        )
        section_text = render_model_authority_section(
            head,
            snapshot_path=_snapshot_path(root_path, snapshot),
            coverage_status=snapshot.coverage_status,
        )
        replace_project_manifest_locked(
            manifest_path,
            replace_model_authority_section(current_text, section_text),
            expected_fingerprint=manifest_text_fingerprint(current_text),
        )
    return head


def prepare_initial_model_authority_staging(
    root: str | Path,
    *,
    staging_root: str | Path,
    snapshot_id: str,
    bootstrap_evidence_fingerprint: str,
    system_id: str = "",
    accepted_boundary_contract: AcceptedBoundaryContract | None = None,
) -> tuple[ModelSystemSnapshot, ModelSystemSnapshot, ModelAuthorityHead]:
    """Create the private generation-one base for first current adoption.

    The returned tuple is ``(complete_candidate, pending_base, gen1_head)``.
    The target root is only read; the staging root receives the deliberately
    incomplete pending snapshot.  A later normal revision build must close
    every ``initial_current_intent_unaccepted:<model>`` gap before activation.
    """

    root_path = Path(root).resolve()
    staging_path = Path(staging_root).resolve()
    if root_path == staging_path:
        raise ModelAuthorityError(
            "initial authority staging root must be isolated from target root"
        )
    target_manifest = root_path / ".flowguard" / "project.toml"
    staging_manifest = staging_path / ".flowguard" / "project.toml"
    if not target_manifest.is_file() or not staging_manifest.is_file():
        raise ModelAuthorityError(
            "initial authority requires target and staging project manifests"
        )
    target_text = read_manifest_text(target_manifest)
    staging_text = read_manifest_text(staging_manifest)
    if _SECTION_RE.search(target_text) is not None:
        raise ModelAuthorityError(
            "initial authority target already has a model_authority section"
        )
    if _SECTION_RE.search(staging_text) is not None:
        raise ModelAuthorityError(
            "initial authority staging already has a model_authority section"
        )
    if target_text != staging_text:
        raise ModelAuthorityError(
            "initial authority staging manifest is not the frozen target manifest"
        )

    from .model_system_inventory import (
        build_initial_intent_pending_snapshot,
        build_manifest_model_system_snapshot,
    )

    candidate = build_manifest_model_system_snapshot(
        staging_path,
        snapshot_id=snapshot_id,
        **({"system_id": system_id} if system_id else {}),
        accepted_boundary_contract=accepted_boundary_contract,
    )
    pending = build_initial_intent_pending_snapshot(candidate)
    head = bootstrap_model_authority(
        staging_path,
        pending,
        bootstrap_evidence_fingerprint=bootstrap_evidence_fingerprint,
    )
    return candidate, pending, head


def bootstrap_initial_current_model_authority(
    root: str | Path,
    *,
    staging_root: str | Path,
    expected_absent_manifest_fingerprint: str,
    snapshot_id: str,
    bootstrap_evidence_fingerprint: str,
    model_parent_receipt: str | Path,
    receipt_root: str | Path | None,
    revision_set_id: str,
    task_id: str,
    system_id: str = "",
    current_design_intent_contributions: Iterable[Any],
    legacy_entry_dispositions: Iterable[Any] = (),
    intent_receipt_id: str,
    intent_rationale: str,
    intent_claim_boundary: str,
    native_owner_contracts: Iterable[Any] = (),
    native_owner_receipts: Iterable[Any] = (),
    native_owner_verification_results: Iterable[Any] = (),
    accepted_boundary_contract: AcceptedBoundaryContract | None = None,
    path_quality_subjects: Iterable[Any] = (),
    path_quality_results: Iterable[Any] = (),
    no_declared_intent_rationale_id: str = "",
    no_declared_intent_evidence_fingerprints: Iterable[tuple[str, str]] = (),
    no_declared_intent_rationale: str = "",
    decision_reason: str = "",
) -> dict[str, Any]:
    """Complete one finite first-adoption transaction and publish it once.

    This is the public orchestration owner for the initial-current route.  It
    deliberately composes existing parent/owner/revision/activation APIs; it
    does not execute a second author-wide suite or provide a generation-one
    success path.  Any failure leaves the target manifest without authority
    and retains staging diagnostics for inspection.
    """

    root_path = Path(root).resolve()
    staging_path = Path(staging_root).resolve()
    if not re.fullmatch(
        r"sha256:[0-9a-f]{64}", str(expected_absent_manifest_fingerprint)
    ):
        raise ModelAuthorityError(
            "expected absent manifest fingerprint must be sha256"
        )
    from .model_intent_authority import build_current_intent_bootstrap_receipt
    from .model_revision_builder import build_current_model_revision
    from .model_authority import ModelRevisionSet, load_model_system_snapshot

    candidate, _pending, _gen1_head = prepare_initial_model_authority_staging(
        root_path,
        staging_root=staging_path,
        snapshot_id=snapshot_id,
        bootstrap_evidence_fingerprint=bootstrap_evidence_fingerprint,
        system_id=system_id,
        accepted_boundary_contract=accepted_boundary_contract,
    )
    design = tuple(current_design_intent_contributions)
    legacy = tuple(legacy_entry_dispositions)
    sources = verify_model_intent_sources(staging_path, design)
    intent_receipt = build_current_intent_bootstrap_receipt(
        staging_path,
        receipt_id=intent_receipt_id,
        candidate_snapshot=candidate,
        current_design_contributions=design,
        rationale=intent_rationale,
        legacy_entry_dispositions=legacy,
        claim_boundary=intent_claim_boundary,
    )
    # The source verification above is intentionally explicit.  The official
    # revision builder repeats and binds it to the candidate, so a caller
    # cannot smuggle a ``verified`` boolean into this route.
    if not sources and design:
        raise ModelAuthorityError(
            "initial current intent sources could not be verified"
        )

    # A first-current request should be usable from the public orchestration
    # entry point without requiring the caller to manually manufacture the
    # native-owner aggregate after the private generation-one staging step.
    # The aggregate producer is intentionally evidence-only: it consumes the
    # already executed model-parent receipt and never starts another model
    # runner.  A partially supplied bundle is rejected rather than silently
    # completed from a second source, so the one-owner/one-bundle contract
    # remains explicit.
    supplied_owner_parts = (
        tuple(native_owner_contracts),
        tuple(native_owner_receipts),
        tuple(native_owner_verification_results),
    )
    native_owner_contracts, native_owner_receipts, native_owner_verification_results = (
        supplied_owner_parts
    )
    if any(supplied_owner_parts) and not all(supplied_owner_parts):
        raise ModelAuthorityError(
            "initial current native owner evidence must provide contracts, "
            "receipts, and verification results together"
        )
    if not any(supplied_owner_parts):
        from .model_revision_owner_evidence import (
            produce_model_revision_owner_evidence,
        )

        # Keep this aggregate in the private work area, outside the canonical
        # leaf receipt store.  It is retained as diagnostic evidence and is
        # never treated as another authority or receipt store.
        native_bundle_path = (
            staging_path
            / "work"
            / "initial-current"
            / "native-owner-evidence.json"
        )
        native_report = produce_model_revision_owner_evidence(
            staging_path,
            model_parent_receipt=model_parent_receipt,
            snapshot_id=snapshot_id,
            receipt_root=receipt_root,
            output_path=native_bundle_path,
            accepted_boundary_contract=accepted_boundary_contract,
        )
        native_bundle = native_report.bundle
        native_owner_contracts = native_bundle.contracts
        native_owner_receipts = native_bundle.receipts
        native_owner_verification_results = native_bundle.verification_results

    build_report = build_current_model_revision(
        staging_path,
        model_parent_receipt=model_parent_receipt,
        revision_set_id=revision_set_id,
        task_id=task_id,
        snapshot_id=snapshot_id,
        receipt_root=receipt_root,
        current_design_intent_contributions=design,
        effective_intent_bootstrap_receipt=intent_receipt,
        native_owner_contracts=tuple(native_owner_contracts),
        native_owner_receipts=tuple(native_owner_receipts),
        native_owner_verification_results=tuple(native_owner_verification_results),
        accepted_boundary_contract=accepted_boundary_contract,
        path_quality_subjects=tuple(path_quality_subjects),
        path_quality_results=tuple(path_quality_results),
        no_declared_intent_rationale_id=no_declared_intent_rationale_id,
        no_declared_intent_evidence_fingerprints=tuple(
            no_declared_intent_evidence_fingerprints
        ),
        no_declared_intent_rationale=no_declared_intent_rationale,
        decision_reason=(decision_reason or intent_claim_boundary),
    )
    if str(getattr(build_report, "status", "")) != "pass":
        raise ModelAuthorityError(
            "initial current revision is incomplete; no target pointer was written"
        )
    candidate_path = Path(build_report.candidate_snapshot_path)
    revision_path = Path(build_report.revision_set_path)
    final_candidate = load_model_system_snapshot(candidate_path)
    revision = ModelRevisionSet.from_dict(
        json.loads(revision_path.read_text(encoding="utf-8"))
    )
    stage_head, activation_receipt = activate_model_revision_set(
        staging_path,
        final_candidate,
        revision,
    )
    if stage_head.generation != 2:
        raise ModelAuthorityError(
            "initial current staging activation did not produce generation two"
        )
    rebuild_report = rebuild_model_authority(
        root_path,
        staging_root=staging_path,
        expected_absent_manifest_fingerprint=expected_absent_manifest_fingerprint,
        target_system_id=stage_head.system_id,
        target_generation=2,
    )
    final_head, final_snapshot = load_observed_model_system(root_path)
    final_state = load_current_model_authority_state(root_path)
    if final_head.generation != 2 or final_state.accepted_revision is None:
        raise ModelAuthorityError(
            "initial current publication did not produce a readable v5 authority"
        )
    return {
        "status": "pass",
        "staging_head": stage_head.to_dict(),
        "activation_receipt": activation_receipt.to_dict(),
        "build_report": build_report.to_dict(),
        "rebuild_report": rebuild_report,
        "head": final_head.to_dict(),
        "snapshot": final_snapshot.to_dict(),
        "current_revision_fingerprint": final_state.accepted_revision.fingerprint,
        "claim_boundary": (
            "The target now exposes one readable generation-two current model "
            "authority assembled from this consumer's finite declared models; "
            "author-wide SkillGuard qualification is outside this transaction."
        ),
    }


def _raw_authority_section(text: str) -> str:
    match = _SECTION_RE.search(text)
    if match is None:
        raise ModelAuthorityError("project manifest has no model authority section")
    return match.group(0)


def _copy_rebuild_artifact(
    staging_root: Path,
    target_root: Path,
    category: str,
    fingerprint: str,
) -> Path:
    source = _artifact_path(staging_root, category, fingerprint)
    target = _artifact_path(target_root, category, fingerprint)
    source_io = _windows_io_path(source)
    target_io = _windows_io_path(target)
    if not source_io.is_file():
        raise ModelAuthorityError(
            f"rebuild package is missing current {category} artifact: {fingerprint}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = source_io.read_bytes()
    if target_io.exists():
        if target_io.read_bytes() != source_bytes:
            raise ModelAuthorityError(
                f"immutable {category} target contains different bytes: {fingerprint}"
            )
    else:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".fg",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(source_bytes)
            os.replace(_windows_io_path(temporary), target_io)
        except BaseException:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise
    return target


def _collect_rebuild_reachable_artifacts(
    staging_root: Path,
    head: ModelAuthorityHead,
    snapshot: ModelSystemSnapshot,
) -> set[tuple[str, str]]:
    """Collect the complete immutable predecessor chain for a rebuild.

    A current authority may be several generations past its bootstrap.  The
    old rebuild implementation copied only the current head, its immediate
    snapshot, and treated that predecessor's accepted revision as a bootstrap
    artifact.  That is only correct for a generation-two package.  For a
    generation-three-or-later package the predecessor is itself established
    by a revision and a transition receipt, and the chain must be walked until
    the real generation-one bootstrap is reached.

    The traversal reuses the normal current-authority loader for each exact
    head, so it does not infer ancestry from filenames or copy unrelated mesh
    objects.  Rollback transitions retain their contract and receipt as well.
    """

    reachable: set[tuple[str, str]] = set()
    seen_heads: set[str] = set()
    current_head = head
    current_snapshot = snapshot
    while True:
        if current_head.fingerprint in seen_heads:
            raise ModelAuthorityError(
                "staging rebuild package contains a cyclic authority ancestry"
            )
        seen_heads.add(current_head.fingerprint)
        reachable.add(("snapshots", current_head.snapshot_fingerprint))

        if current_head.generation == 1:
            reachable.add(
                ("bootstraps", current_head.accepted_revision_set_fingerprint)
            )
            break

        reachable.add(
            ("revisions", current_head.accepted_revision_set_fingerprint)
        )
        transition_fingerprint = current_head.activation_receipt_fingerprint
        activation_path = _artifact_path(
            staging_root, "activations", transition_fingerprint
        )
        rollback_path = _artifact_path(
            staging_root, "rollbacks", transition_fingerprint
        )
        if activation_path.is_file() and not rollback_path.is_file():
            reachable.add(("activations", transition_fingerprint))
            projection = _load_bound_read_projection(staging_root, current_head)
            index = projection["index"]
            reachable.add(("read-projection-indexes", projection["index_fingerprint"]))
            models = index.get("models") if isinstance(index, Mapping) else None
            if not isinstance(models, Mapping):
                raise ModelAuthorityError(
                    "staging accepted read projection has no model index"
                )
            for row in models.values():
                if not isinstance(row, Mapping):
                    raise ModelAuthorityError(
                        "staging accepted read projection model row is invalid"
                    )
                shard_fingerprint = str(row.get("shard_fingerprint", ""))
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", shard_fingerprint):
                    raise ModelAuthorityError(
                        "staging accepted read projection shard fingerprint is invalid"
                    )
                reachable.add(("read-model-shards", shard_fingerprint))
            transition_evidence = index.get("transition_evidence")
            if isinstance(transition_evidence, Mapping) and transition_evidence.get(
                "kind"
            ) == "rollback":
                reachable.add(
                    (
                        "rollbacks",
                        str(transition_evidence["rollback_receipt_fingerprint"]),
                    )
                )
                reachable.add(
                    (
                        "rollback-contracts",
                        str(transition_evidence["rollback_contract_fingerprint"]),
                    )
                )
        elif rollback_path.is_file() and not activation_path.is_file():
            raise ModelAuthorityError(
                "staging rollback transition is not bound to an accepted read projection"
            )
        else:
            raise ModelAuthorityError(
                "staging authority transition is missing or ambiguous at "
                f"generation {current_head.generation}"
            )

        state = load_current_model_authority_state(
            staging_root,
            head=current_head,
            snapshot=current_snapshot,
        )
        if state.accepted_boundary_contract is not None:
            reachable.add(
                (
                    MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY,
                    state.accepted_boundary_contract.fingerprint,
                )
            )
        predecessor = state.predecessor_head
        if predecessor is None:
            raise ModelAuthorityError(
                "staging rebuild package has no exact predecessor at "
                f"generation {current_head.generation}"
            )
        current_head = predecessor
        current_snapshot = _load_snapshot_by_fingerprint(
            staging_root, predecessor.snapshot_fingerprint
        )
    return reachable


def rebuild_model_authority(
    root: str | Path,
    *,
    staging_root: str | Path,
    expected_old_section_fingerprint: str = "",
    expected_absent_manifest_fingerprint: str = "",
    target_system_id: str = "",
    target_generation: int = 2,
) -> dict[str, Any]:
    """Replace an existing authority with a verified current-only package.

    The target's old authority is treated as opaque raw section bytes for CAS
    only.  All semantic reads happen in the isolated staging root, which must
    already contain a current generation-one -> accepted current-v5 lineage.
    """

    root_path = Path(root).resolve()
    staging_path = Path(staging_root).resolve()
    if root_path == staging_path:
        raise ModelAuthorityError("rebuild staging root must be isolated from target root")
    old_fingerprint = str(expected_old_section_fingerprint or "")
    absent_fingerprint = str(expected_absent_manifest_fingerprint or "")
    if bool(old_fingerprint) == bool(absent_fingerprint):
        raise ModelAuthorityError(
            "exactly one of expected_old_section_fingerprint or "
            "expected_absent_manifest_fingerprint is required"
        )
    if old_fingerprint and not re.fullmatch(r"sha256:[0-9a-f]{64}", old_fingerprint):
        raise ModelAuthorityError("expected old authority section fingerprint must be sha256")
    if absent_fingerprint and not re.fullmatch(
        r"sha256:[0-9a-f]{64}", absent_fingerprint
    ):
        raise ModelAuthorityError(
            "expected absent manifest fingerprint must be sha256"
        )
    if target_generation < 2:
        raise ModelAuthorityError("current-only rebuild generation must be at least two")
    target_manifest = root_path / ".flowguard" / "project.toml"
    staging_manifest = staging_path / ".flowguard" / "project.toml"
    stage_head, stage_snapshot = load_observed_model_system(staging_path)
    if stage_head.generation != target_generation:
        raise ModelAuthorityError(
            f"staging current generation must be {target_generation}, got {stage_head.generation}"
        )
    if target_system_id and stage_head.system_id != target_system_id:
        raise ModelAuthorityError("staging system_id does not match requested target system_id")
    if stage_head.generation < 2:
        raise ModelAuthorityError("staging root is not a current v5 rebuild package")
    stage_state = load_current_model_authority_state(staging_path)
    if stage_state.accepted_revision is None:
        raise ModelAuthorityError("staging root does not contain an accepted current revision")
    if stage_state.accepted_revision.schema != "flowguard.model_revision_set.v5":
        raise ModelAuthorityError("staging rebuild package must use current revision schema v5")
    if stage_snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION:
        raise ModelAuthorityError("staging rebuild package must be observed implementation")
    if stage_snapshot.lifecycle != LIFECYCLE_ACTIVE:
        raise ModelAuthorityError("staging rebuild package must be active")

    from .model_system_inventory import build_manifest_model_system_snapshot

    live_target = build_manifest_model_system_snapshot(
        root_path,
        snapshot_id=stage_snapshot.snapshot_id,
        system_id=stage_snapshot.system_id,
        subject_lane=stage_snapshot.subject_lane,
        lifecycle=stage_snapshot.lifecycle,
        accepted_boundary_contract=stage_state.accepted_boundary_contract,
    )
    if live_target.identity_payload() != stage_snapshot.identity_payload():
        raise ModelAuthorityError(
            "target current source does not exactly match the staging rebuild package"
        )

    predecessor = stage_state.predecessor_head
    if predecessor is None:
        raise ModelAuthorityError("staging rebuild package has no exact predecessor")
    activation = stage_state.activation_receipt
    if activation is None:
        raise ModelAuthorityError("staging rebuild package has no activation receipt")
    reachable = _collect_rebuild_reachable_artifacts(
        staging_path,
        stage_head,
        stage_snapshot,
    )
    section_text = render_model_authority_section(
        stage_head,
        snapshot_path=_snapshot_path(root_path, stage_snapshot),
        coverage_status=stage_snapshot.coverage_status,
    )
    transaction_id = canonical_fingerprint(
        {
            "old_section": old_fingerprint,
            "absent_manifest": absent_fingerprint,
            "new_head": stage_head.fingerprint,
            "staging_snapshot": stage_snapshot.fingerprint,
        }
    )
    manifest_path = target_manifest
    with project_manifest_lock(manifest_path):
        old_text = read_manifest_text(manifest_path)
        if old_fingerprint:
            old_section = _raw_authority_section(old_text)
            if manifest_text_fingerprint(old_section) != old_fingerprint:
                raise ModelAuthorityError(
                    "target authority section changed before rebuild"
                )
        else:
            if _SECTION_RE.search(old_text) is not None:
                raise ModelAuthorityError(
                    "target manifest gained model authority before initial rebuild"
                )
            if manifest_text_fingerprint(old_text) != absent_fingerprint:
                raise ModelAuthorityError(
                    "target manifest changed before initial authority rebuild"
                )

        for category, fingerprint in sorted(reachable):
            _copy_rebuild_artifact(staging_path, root_path, category, fingerprint)

        new_text = replace_model_authority_section(old_text, section_text)
        replace_project_manifest_locked(
            manifest_path,
            new_text,
            expected_fingerprint=manifest_text_fingerprint(old_text),
        )
        try:
            post_head, post_snapshot = load_observed_model_system(root_path)
            if post_head != stage_head or post_snapshot.identity_payload() != stage_snapshot.identity_payload():
                raise ModelAuthorityError("post-rebuild authority pointer does not match staging head")
            post_state = load_current_model_authority_state(root_path)
            if post_state.accepted_revision is None:
                raise ModelAuthorityError("post-rebuild authority is not current")
        except Exception:
            current_text = read_manifest_text(manifest_path)
            if current_text != new_text:
                raise ModelAuthorityError(
                    "rebuild recovery required: peer changed manifest after pointer replacement"
                )
            replace_project_manifest_locked(
                manifest_path,
                old_text,
                expected_fingerprint=manifest_text_fingerprint(current_text),
            )
            raise

        # Historical/candidate immutable objects are evidence, not temporary
        # files.  A pointer transaction must never delete them as a side
        # effect of becoming current; explicit cleanup is a separate,
        # user-directed operation with its own retention receipt.
        mesh_root = root_path / ".flowguard" / "models" / "authority"
        retained_unreachable: list[str] = []
        if mesh_root.exists():
            for path in sorted(mesh_root.rglob("*.json")):
                category = path.parent.name
                fingerprint = f"sha256:{path.stem}"
                if (category, fingerprint) not in reachable:
                    retained_unreachable.append(str(path))

    return {
        "status": "pass",
        "transaction_id": transaction_id,
        "system_id": stage_head.system_id,
        "generation": stage_head.generation,
        "revision_schema": stage_state.accepted_revision.schema,
        "snapshot_fingerprint": stage_head.snapshot_fingerprint,
        "retired_objects_removed": False,
        "retained_unreachable_artifacts": retained_unreachable,
    }


def _validate_revision_intent_activation(
    root: Path,
    current_head: ModelAuthorityHead,
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
    *,
    reverify_sources: bool = True,
    current_state: CurrentModelAuthorityState | None = None,
) -> None:
    """Require an exact reproducible intent lineage before pointer movement."""

    if current_state is not None:
        if (
            current_state.head != current_head
            or current_state.snapshot != base_snapshot
        ):
            raise ModelAuthorityError(
                "current authority state does not match the activation base"
            )

    if revision_set.expected_head_fingerprint != current_head.fingerprint:
        raise ModelAuthorityError(
            "model authority head changed; rebase the revision before activation"
        )
    if revision_set.base_snapshot_fingerprint != base_snapshot.fingerprint:
        raise ModelAuthorityError(
            "revision base snapshot does not match the current authority"
        )
    if (
        revision_set.candidate_snapshot_fingerprint
        != candidate_snapshot.fingerprint
    ):
        raise ModelAuthorityError(
            "revision candidate snapshot does not match the activation candidate"
        )
    effective_view = revision_set.current_effective_intent_view

    def validate_candidate_owner_inputs() -> None:
        if reverify_sources:
            from .model_regressions import (
                ModelRegressionManifest,
                audit_intent_source_input_bindings,
            )

            manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
            if not manifest_path.is_file():
                return
            live_manifest = ModelRegressionManifest.load(root)
            binding_errors = audit_intent_source_input_bindings(
                root,
                live_manifest,
                effective_view.active_contributions,
                effective_view.verified_source_identities,
            )
            if binding_errors:
                raise ModelAuthorityError(
                    "activation intent-source model-input binding is incomplete: "
                    + "; ".join(binding_errors)
                )
        validate_candidate_intent_source_input_bindings(
            candidate_snapshot,
            effective_view.active_contributions,
            effective_view.verified_source_identities,
        )

    if effective_view.bootstrap_receipt is not None:
        if (
            current_state is not None
            and current_state.transition_kind != "legacy_bootstrap_source"
        ):
            raise ModelAuthorityError(
                "effective intent bootstrap requires the exact audited legacy source"
            )
        receipt = effective_view.bootstrap_receipt
        rebuilt_receipt = _build_current_intent_bootstrap_receipt_from_source(
            root,
            source_head=current_head,
            source_snapshot=base_snapshot,
            receipt_id=receipt.receipt_id,
            candidate_snapshot=candidate_snapshot,
            current_design_contributions=effective_view.active_contributions,
            verified_source_identities=(
                None
                if reverify_sources
                else effective_view.verified_source_identities
            ),
            rationale=receipt.rationale,
            legacy_entry_dispositions=receipt.legacy_entry_dispositions,
            claim_boundary=receipt.claim_boundary,
        )
        if rebuilt_receipt != receipt:
            raise ModelAuthorityError(
                "effective intent bootstrap receipt is stale or foreign"
            )
        verified_sources = (
            verify_model_intent_sources(
                root,
                effective_view.active_contributions,
            )
            if reverify_sources
            else effective_view.verified_source_identities
        )
        rebuilt_view = bootstrap_current_effective_intent_view(
            candidate_snapshot,
            effective_view.active_contributions,
            verified_sources,
            rebuilt_receipt,
        )
        if rebuilt_view != effective_view:
            raise ModelAuthorityError(
                "effective intent bootstrap view is not exactly reproducible"
            )
        if reverify_sources:
            validate_candidate_owner_inputs()
        return

    current_revision = (
        current_state.accepted_revision
        if current_state is not None
        else _load_accepted_revision_set(
            root,
            current_head,
            base_snapshot,
        )
    )
    if current_revision is None:
        raise ModelAuthorityError(
            "the first current intent revision requires an explicit bootstrap receipt"
        )
    if reverify_sources:
        validate_current_effective_intent_refinement(
            root,
            base_view=current_revision.current_effective_intent_view,
            candidate_snapshot=candidate_snapshot,
            revision_contributions=revision_set.intent_contributions,
            revision_dispositions=revision_set.intent_dispositions,
            candidate_view=effective_view,
        )
    else:
        _validate_current_effective_intent_refinement_with_sources(
            root,
            base_view=current_revision.current_effective_intent_view,
            candidate_snapshot=candidate_snapshot,
            revision_contributions=revision_set.intent_contributions,
            revision_dispositions=revision_set.intent_dispositions,
            candidate_view=effective_view,
            verified_source_identities=(
                effective_view.verified_source_identities
            ),
        )
    if reverify_sources:
        validate_candidate_owner_inputs()


def activate_model_revision_set(
    root: str | Path,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
) -> tuple[ModelAuthorityHead, ModelActivationReceipt]:
    """Persist immutable records and update the sole pointer last under one lock."""

    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        current_head, base_snapshot = _load_observed_from_manifest_text(
            root_path,
            current_text,
        )
        current_state = load_current_model_authority_state(
            root_path,
            head=current_head,
            snapshot=base_snapshot,
            allow_legacy_bootstrap_source=(
                revision_set.current_effective_intent_view.bootstrap_receipt
                is not None
            ),
            # A refining revision is allowed to replace a source whose stored
            # fingerprint is stale precisely because that source changed.
            # Rechecking the complete base inventory here would reject every
            # legitimate supersession before its transition can be replayed.
            # _validate_revision_intent_activation independently reverifies
            # the folded candidate inventory, so retained stale sources still
            # fail while explicit current replacements can proceed.
            reverify_current_sources=False,
        )
        _validate_revision_intent_activation(
            root_path,
            current_head,
            base_snapshot,
            candidate_snapshot,
            revision_set,
            current_state=current_state,
        )
        from .model_system_inventory import (
            build_manifest_model_system_snapshot,
        )

        candidate_boundary_contract = _load_accepted_boundary_contract(
            root_path,
            candidate_snapshot,
            "",
        )

        live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
            accepted_boundary_contract=candidate_boundary_contract,
        )
        projection_fingerprint, projection_payload, projection_shards = (
            _build_accepted_read_projection(
                current_head,
                candidate_snapshot,
                revision_set,
            )
        )
        generated_receipt_id = "activation:" + projection_fingerprint.split(":", 1)[1]
        next_head, receipt = validate_activation_plan(
            current_head,
            base_snapshot,
            candidate_snapshot,
            revision_set,
            live_candidate_snapshot=live_candidate,
            receipt_id=generated_receipt_id,
        )
        write_content_addressed_snapshot(root_path, candidate_snapshot)
        _write_immutable_json(
            root_path,
            "revisions",
            revision_set.fingerprint,
            revision_set.to_dict(),
        )
        _persist_accepted_read_projection(
            root_path,
            projection_fingerprint,
            projection_payload,
            projection_shards,
        )
        _write_immutable_json(
            root_path,
            "activations",
            receipt.fingerprint,
            {**receipt.to_dict(), "fingerprint": receipt.fingerprint},
        )
        final_live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
            accepted_boundary_contract=candidate_boundary_contract,
        )
        if (
            final_live_candidate.identity_payload()
            != candidate_snapshot.identity_payload()
        ):
            raise ModelAuthorityError(
                "live candidate changed before pointer replacement"
            )
        _validate_revision_intent_activation(
            root_path,
            current_head,
            base_snapshot,
            final_live_candidate,
            revision_set,
            current_state=current_state,
        )
        section_text = render_model_authority_section(
            next_head,
            snapshot_path=_snapshot_path(root_path, candidate_snapshot),
            coverage_status=candidate_snapshot.coverage_status,
        )
        _replace_authority_section_cas(
            manifest_path,
            frozen_text=current_text,
            section_text=section_text,
        )
    return next_head, receipt


def rollback_observed_model_system(
    root: str | Path,
    contract: ModelRollbackContract,
    candidate_snapshot: ModelSystemSnapshot,
    reverse_revision_set: ModelRevisionSet,
    *,
    completed_evidence_fingerprints: Iterable[str],
    requested_result: str,
    receipt_id: str,
    reason: str,
) -> tuple[ModelAuthorityHead, ModelRollbackReceipt]:
    root_path = Path(root).resolve()
    manifest_path = root_path / ".flowguard" / "project.toml"
    with project_manifest_lock(manifest_path):
        current_text = read_manifest_text(manifest_path)
        current_head, current_snapshot = _load_observed_from_manifest_text(
            root_path,
            current_text,
        )
        current_state = load_current_model_authority_state(
            root_path,
            head=current_head,
            snapshot=current_snapshot,
            reverify_current_sources=True,
        )
        current_revision = current_state.accepted_revision
        if current_revision is None:
            raise ModelAuthorityError(
                "operational rollback requires a current v5 intent authority"
            )
        _validate_revision_intent_activation(
            root_path,
            current_head,
            current_snapshot,
            candidate_snapshot,
            reverse_revision_set,
            current_state=current_state,
        )
        receipt = validate_operational_rollback(
            current_head,
            contract,
            reverse_revision_set,
            completed_evidence_fingerprints=completed_evidence_fingerprints,
            requested_result=requested_result,
            receipt_id=receipt_id,
            reason=reason,
        )
        if requested_result == ROLLBACK_RESULT_FORWARD_REPAIR:
            raise ModelAuthorityError(
                "forward repair preserves the current head until a new revision activates"
            )
        if candidate_snapshot.fingerprint != contract.to_snapshot_fingerprint:
            raise ModelAuthorityError("rollback target snapshot is stale")
        if (
            candidate_snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION
            or candidate_snapshot.lifecycle != LIFECYCLE_ACTIVE
        ):
            raise ModelAuthorityError("rollback target is not an active observed snapshot")
        from .model_system_inventory import (
            build_manifest_model_system_snapshot,
        )

        candidate_boundary_contract = _load_accepted_boundary_contract(
            root_path,
            candidate_snapshot,
            "",
        )

        live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
            accepted_boundary_contract=candidate_boundary_contract,
        )
        projection_fingerprint, projection_payload, projection_shards = (
            _build_accepted_read_projection(
                current_head,
                candidate_snapshot,
                reverse_revision_set,
                transition_evidence={
                    "kind": "rollback",
                    "rollback_receipt_fingerprint": receipt.fingerprint,
                    "rollback_contract_fingerprint": contract.fingerprint,
                },
            )
        )
        generated_receipt_id = "activation:" + projection_fingerprint.split(":", 1)[1]
        next_head, activation_receipt = validate_activation_plan(
            current_head,
            current_snapshot,
            candidate_snapshot,
            reverse_revision_set,
            live_candidate_snapshot=live_candidate,
            receipt_id=generated_receipt_id,
        )
        write_content_addressed_snapshot(root_path, candidate_snapshot)
        _write_immutable_json(
            root_path,
            "rollback-contracts",
            contract.fingerprint,
            {**contract.to_dict(), "fingerprint": contract.fingerprint},
        )
        _write_immutable_json(
            root_path,
            "revisions",
            reverse_revision_set.fingerprint,
            reverse_revision_set.to_dict(),
        )
        _persist_accepted_read_projection(
            root_path,
            projection_fingerprint,
            projection_payload,
            projection_shards,
        )
        _write_immutable_json(
            root_path,
            "rollbacks",
            receipt.fingerprint,
            {**receipt.to_dict(), "fingerprint": receipt.fingerprint},
        )
        _write_immutable_json(
            root_path,
            "activations",
            activation_receipt.fingerprint,
            {**activation_receipt.to_dict(), "fingerprint": activation_receipt.fingerprint},
        )
        final_live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
            accepted_boundary_contract=candidate_boundary_contract,
        )
        if (
            final_live_candidate.identity_payload()
            != candidate_snapshot.identity_payload()
        ):
            raise ModelAuthorityError(
                "restored live state changed before rollback pointer replacement"
            )
        _validate_revision_intent_activation(
            root_path,
            current_head,
            current_snapshot,
            final_live_candidate,
            reverse_revision_set,
            current_state=current_state,
        )
        section_text = render_model_authority_section(
            next_head,
            snapshot_path=_snapshot_path(root_path, candidate_snapshot),
            coverage_status=candidate_snapshot.coverage_status,
        )
        _replace_authority_section_cas(
            manifest_path,
            frozen_text=current_text,
            section_text=section_text,
        )
    return next_head, receipt


__all__ = [
    "EXECUTION_EVIDENCE_NOT_RUN",
    "MODEL_AUTHORITY_STATUS_BLOCKED",
    "MODEL_AUTHORITY_STATUS_PASS",
    "MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS",
    "CurrentModelAuthorityState",
    "ModelAuthorityAuditReport",
    "ModelAuthorityFinding",
    "SELECTED_SOURCE_CURRENT",
    "SELECTED_SOURCE_NOT_SELECTED",
    "SELECTED_SOURCE_STALE",
    "SELECTED_SOURCE_UNAVAILABLE",
    "SelectedModelClosureRead",
    "activate_model_revision_set",
    "audit_model_authority",
    "bootstrap_model_authority",
    "prepare_initial_model_authority_staging",
    "bootstrap_initial_current_model_authority",
    "rebuild_model_authority",
    "load_current_accepted_revision_set",
    "load_current_model_authority_state",
    "load_observed_model_head",
    "load_observed_model_system",
    "read_selected_model_closure",
    "read_selected_model_projection",
    "render_model_authority_section",
    "replace_model_authority_section",
    "rollback_observed_model_system",
]
